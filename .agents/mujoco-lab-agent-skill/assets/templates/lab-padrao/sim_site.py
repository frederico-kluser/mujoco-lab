#!/usr/bin/env python3
"""sim_site.py — UM COMANDO arranca o padrão do laboratório: runner + servidor + site (`padrao-simulacao-clean-site`).

    uv run --group hover-rl python <exp>/sim_site.py                 # janela 3D LIMPA + site em http://127.0.0.1:8080
    uv run --group hover-rl python <exp>/sim_site.py --sem-janela    # só site + API (validação, sem janela nenhuma)
    uv run --group hover-rl python <exp>/sim_site.py --model out/melhor_modelo.zip --port 0

O que este ficheiro faz:
  1. arranca o RUNNER (`sim_view.py`) como SUBPROCESSO — é ele que abre a janela limpa e escreve a telemetria;
  2. serve o SITE (`site/dist/`) e a API JSON que o site consome (só stdlib: `http.server`);
  3. imprime o URL no terminal e abre o browser.

Janela MuJoCo 100% clean: a janela mostra SÓ a simulação 3D (o runner nunca chama `set_texts`/`set_figures`).
TODAS as métricas e TODOS os controlos ficam no site: vento em tempo real, REINICIAR (é o ÚNICO caminho de
reinício) e LOOP (desligado por omissão — sem ciclo automático).

API (5 rotas — é o CONTRATO, não mudar ao copiar o template):
  · `GET  /api/sim`          → `{"estado","ep","passo","retorno","vento":{vel,azimute,elevacao,ativo},"linhas":[…]}`
                               com as ≤200 últimas amostras da telemetria (`linhas` traz o registo completo);
  · `GET  /api/state`        → resumo (acima sem `linhas` + `modelo_nome`, `sim_vivo`, `contador_reiniciar`, `loop`);
  · `POST /api/vento`        → `{"vel","azimute","elevacao"}` (qualquer subconjunto; faixas 0–5 m/s, 0–360°,
                               −90–90°) → 200 · 400 se fora da faixa;
  · `POST /api/reiniciar`    → incrementa `reiniciar` no controlo → `{"contador": n}` (reinício pelo site);
  · `POST /api/loop`         → `{"ativo": bool}` liga/desliga o auto-reset no fim do episódio.
Estados honestos: 400 (valor/faixa inválida) · 404 (rota/asset/path traversal) · 500. Sem websockets: o site
faz polling a `GET /api/sim` a ~2,9 Hz.

Pré-requisito do site (uma vez): `cd site && npm install && npm run build` (ver `site/LEIAME.md`). Se o
`dist/` não existir, o servidor serve uma página a dizer exatamente isso — e o resto (API) funciona na mesma.

ADAPTAR: nada aqui. O que é do teu robô está em `env.py`, `sim_view.py` (as 3 métricas) e `site/src/lib/sim.ts`.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_AQUI = Path(__file__).resolve().parent
SITE_DIST = _AQUI / "site" / "dist"
SITE_FONTES = _AQUI / "site"
CONTROLO_OMISSAO = _AQUI / "out" / "controle_vento.json"
TELEMETRIA_OMISSAO = _AQUI / "out" / "sim_telemetria.jsonl"
RUNNER = _AQUI / "sim_view.py"
MAX_LINHAS = 200                       # teto de amostras devolvidas por `GET /api/sim`
FAIXAS = {"vel": (0.0, 5.0), "azimute": (0.0, 360.0), "elevacao": (-90.0, 90.0)}
TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css",
         ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
         ".woff2": "font/woff2", ".woff": "font/woff", ".map": "application/json", ".txt": "text/plain; charset=utf-8"}


# ------------------------------------------------------------------------------------ utilidades (só stdlib)
def escrever_atomico(caminho: Path, dados: dict) -> None:
    """Escrita ATÓMICA (tmp + `os.replace`): o runner nunca lê um ficheiro a meio (contrato do controlo)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, caminho)


def ler_controlo(caminho: Path) -> dict:
    """Conteúdo atual do ficheiro de controlo (ou os valores de arranque, se ainda não existir/estiver inválido)."""
    base = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False, "reiniciar": 0, "loop": False, "t": 0.0}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return base
    base.update({k: v for k, v in dados.items() if k in base})
    return base


def ultimas_linhas(caminho: Path, n: int = MAX_LINHAS) -> list[dict]:
    """As ≤n últimas linhas JSON VÁLIDAS da telemetria (lê o ficheiro inteiro mas guarda só a cauda)."""
    try:
        with caminho.open("r", encoding="utf-8", errors="replace") as fh:
            cauda = deque(fh, maxlen=n)
    except OSError:
        return []
    linhas = []
    for linha in cauda:
        if not linha.startswith("{"):
            continue
        try:
            linhas.append(json.loads(linha))
        except ValueError:
            continue                                   # linha a meio de escrita: ignora, não inventa
    return linhas


def porta_livre(host: str, porta: int, tentativas: int = 20) -> int:
    """Primeira porta livre a partir de `porta` (0 = o sistema escolhe) — evita o "porta ocupada" no arranque."""
    if porta == 0:
        with socket.socket() as s:
            s.bind((host, 0))
            return int(s.getsockname()[1])
    for p in range(porta, porta + tentativas):
        with socket.socket() as s:
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    raise SystemExit(f"Erro: nenhuma porta livre em {host}:{porta}–{porta + tentativas} — Solução: use --port 0")


class Servidor:
    """Estado do servidor: caminhos, processo do runner, modelo em uso e métricas de sessão."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.controlo = Path(args.controlo)
        self.telemetria = Path(args.telemetria)
        self.dist = SITE_DIST
        self.modelo = Path(args.model) if args.model else None
        self.modelo_nome = self.modelo.name if self.modelo else "trim (sem política)"
        self.modelo_motivo = "política indicada em --model" if self.modelo else "sem --model: ação nula (ctrl = τ_trim)"
        self.runner: subprocess.Popen | None = None
        self.t_inicio = time.time()
        self.verboso = bool(args.verboso)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ runner
    def arrancar_runner(self) -> None:
        """Arranca o `sim_view.py` como subprocesso (mesmo interpretador) e devolve já o controlo."""
        cmd = [sys.executable, str(RUNNER), "--controlo", str(self.controlo), "--telemetria", str(self.telemetria),
               "--fator-tempo", str(self.args.fator_tempo), "--seed", str(self.args.seed)]
        if self.args.sem_janela:
            cmd.append("--sem-janela")
        if self.args.model:
            cmd += ["--model", str(self.args.model)]
        if self.args.loop:
            cmd.append("--loop")
        if not self.controlo.exists():
            escrever_atomico(self.controlo, {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False,
                                             "reiniciar": 0, "loop": bool(self.args.loop), "t": 0.0})
        print(f"[site] runner: {' '.join(cmd[1:])}", flush=True)
        self.runner = subprocess.Popen(cmd, cwd=str(_AQUI))

    def runner_vivo(self) -> bool:
        return self.runner is not None and self.runner.poll() is None

    def parar_runner(self) -> None:
        """Termina o runner (SIGTERM → espera 5 s → SIGKILL): sem processos órfãos ao fechar o servidor."""
        if self.runner is None or self.runner.poll() is not None:
            return
        self.runner.terminate()
        try:
            self.runner.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self.runner.kill()
        print("[site] runner terminado", flush=True)

    # ------------------------------------------------------------------ leituras/escritas do contrato
    def estado_atual(self) -> dict:
        linhas = ultimas_linhas(self.telemetria)
        ultima = linhas[-1] if linhas else {}
        controlo = ler_controlo(self.controlo)
        return {
            "estado": ultima.get("estado", "sem_dados"),
            "ep": ultima.get("ep", 0),
            "passo": ultima.get("passo", 0),
            "retorno": ultima.get("retorno", 0.0),
            "vento": {"vel": controlo["vel"], "azimute": controlo["azimute"], "elevacao": controlo["elevacao"],
                      "ativo": bool(controlo["ativo"])},
            "vento_em_vigor": {"vel": ultima.get("vento_vel", 0.0), "azimute": ultima.get("vento_azim", 0.0)},
            "contador_reiniciar": int(controlo["reiniciar"]),
            "loop": bool(controlo["loop"]),
            "modelo": str(self.modelo) if self.modelo else None,
            "modelo_nome": self.modelo_nome,
            "modelo_motivo": self.modelo_motivo,
            "sim_vivo": self.runner_vivo(),
            "n_linhas": len(linhas),
            "ups": round((time.time() - self.t_inicio), 1),
        }

    def definir_vento(self, corpo: dict) -> dict:
        """`POST /api/vento`: valida as faixas, MESCLA com o controlo atual e escreve-o de forma atómica."""
        if not isinstance(corpo, dict):
            raise TypeError("esperava um objeto JSON {vel, azimute, elevacao}")
        atual = ler_controlo(self.controlo)
        for campo in ("vel", "azimute", "elevacao"):
            if campo not in corpo or corpo[campo] is None:
                continue
            valor = float(corpo[campo])                  # ValueError → 400 (o handler traduz)
            lo, hi = FAIXAS[campo]
            if not lo <= valor <= hi:
                raise ValueError(f"'{campo}' fora da faixa {lo}–{hi}: {valor}")
            atual[campo] = valor
        atual["ativo"] = bool(corpo.get("ativo", True))
        atual["t"] = round(time.time(), 3)
        escrever_atomico(self.controlo, atual)
        return {"vento": {"vel": atual["vel"], "azimute": atual["azimute"], "elevacao": atual["elevacao"],
                          "ativo": atual["ativo"]}}

    def reiniciar(self) -> dict:
        """`POST /api/reiniciar`: o CONTADOR é o mecanismo (o runner vê o valor novo e faz `env.reset()`)."""
        atual = ler_controlo(self.controlo)
        atual["reiniciar"] = int(atual["reiniciar"]) + 1
        atual["t"] = round(time.time(), 3)
        escrever_atomico(self.controlo, atual)
        print(f"[site] REINICIAR → contador {atual['reiniciar']}", flush=True)
        return {"contador": atual["reiniciar"]}

    def definir_loop(self, corpo: dict) -> dict:
        """`POST /api/loop`: liga/desliga o auto-reset no fim do episódio (por omissão está OFF)."""
        if not isinstance(corpo, dict) or "ativo" not in corpo:
            raise TypeError("esperava {\"ativo\": bool}")
        if not isinstance(corpo["ativo"], bool):
            raise TypeError(f"'ativo' tem de ser booleano: {corpo['ativo']!r}")
        atual = ler_controlo(self.controlo)
        atual["loop"] = corpo["ativo"]
        atual["t"] = round(time.time(), 3)
        escrever_atomico(self.controlo, atual)
        print(f"[site] LOOP {'ligado' if corpo['ativo'] else 'desligado'}", flush=True)
        return {"loop": atual["loop"]}


# ---------------------------------------------------------------------------------------------- HTTP
def _pagina_sem_site(motivo: str) -> bytes:
    """Página honesta quando o `dist/` não existe: diz o comando exato que falta (não finge um site)."""
    return f"""<!doctype html><html lang="pt"><head><meta charset="utf-8"><title>site por construir</title>
<style>body{{background:#0e1420;color:#e6ebf5;font:16px/1.6 ui-monospace,monospace;margin:8vh auto;max-width:60rem;padding:0 2rem}}
code{{background:#1b2536;padding:.2rem .4rem;border-radius:.3rem}}h1{{color:#ffa24a}}</style></head><body>
<h1>O site ainda não está construído</h1>
<p>{motivo}</p>
<p>A API (5 rotas) está a funcionar: <code>GET /api/sim</code>, <code>GET /api/state</code>,
<code>POST /api/vento</code>, <code>POST /api/reiniciar</code>, <code>POST /api/loop</code>.</p>
<pre>cd site
source ~/.secrets      # MOTION_TOKEN do registry @motionplus (ver .npmrc)
node ensure-setup.mjs  # instala o que falta
npm run build          # gera dist/ que este servidor serve</pre>
<p>Passo a passo completo: <code>site/LEIAME.md</code>.</p></body></html>""".encode()


class Handler(BaseHTTPRequestHandler):
    """Handler HTTP: 5 rotas de API + ficheiros do `site/dist/` (SPA). Estado no `Servidor` injetado."""

    server_version = "lab-padrao-sim-site/1.0"
    servidor: Servidor            # injetado por `criar_handler` (o BaseHTTPRequestHandler não aceita __init__ extra)

    # ------------------------------------------------------------------ respostas
    def _responde(self, corpo: bytes, tipo: str = "application/json", codigo: int = 200) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def _json(self, obj: Any, codigo: int = 200) -> None:
        self._responde(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode(), "application/json", codigo)

    def _erro(self, codigo: int, mensagem: str) -> None:
        self._json({"erro": mensagem, "codigo": codigo}, codigo)

    def log_message(self, formato: str, *args) -> None:      # ruído do BaseHTTPRequestHandler
        if self.servidor.verboso:
            print(f"[site] {self.address_string()} {formato % args}", flush=True)

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:                                 # assinatura do BaseHTTPRequestHandler
        rota = self.path.split("?", 1)[0]
        try:
            if rota == "/api/sim":
                estado = self.servidor.estado_atual()
                estado["linhas"] = ultimas_linhas(self.servidor.telemetria)
                self._json(estado)
            elif rota == "/api/state":
                self._json(self.servidor.estado_atual())
            elif rota.startswith("/api/"):
                self._erro(404, f"rota desconhecida: {rota}")
            else:
                self._estatico(rota)
        except Exception as erro:                             # noqa: BLE001 — a API nunca derruba o servidor
            self._erro(500, f"erro interno: {erro!r}")

    def do_HEAD(self) -> None:
        self.do_GET()

    def _estatico(self, rota: str) -> None:
        """Serve `site/dist/<rota>`; sem `dist/` devolve a página de instruções; rotas do SPA caem no index."""
        caminho = urllib.parse.unquote(rota)
        relativo = Path(caminho.lstrip("/") or "index.html")
        if ".." in relativo.parts:
            self._erro(404, f"caminho inválido: {rota}")      # traversal: 404 explícito, nunca sai da pasta
            return
        if not self.servidor.dist.is_dir():
            self._responde(_pagina_sem_site(f"pasta esperada: {self.servidor.dist}"), "text/html; charset=utf-8", 200)
            return
        alvo = self.servidor.dist / relativo
        if not alvo.is_file():
            if relativo.suffix and relativo.suffix not in (".html",):
                self._erro(404, f"asset não encontrado: {rota}")
                return
            alvo = self.servidor.dist / "index.html"          # rotas do site (SPA)
        try:
            corpo = alvo.read_bytes()
        except OSError as erro:
            self._erro(404, f"não consegui ler {alvo.name}: {erro}")
            return
        self._responde(corpo, TIPOS.get(alvo.suffix, "application/octet-stream"))

    # ------------------------------------------------------------------ POST
    def do_POST(self) -> None:                                # assinatura do BaseHTTPRequestHandler
        rota = self.path.split("?", 1)[0]
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho > 1 << 20:
                self._erro(400, "corpo demasiado grande (limite 1 MiB)")
                return
            bruto = self.rfile.read(tamanho) if tamanho else b"{}"
            try:
                corpo = json.loads(bruto.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError) as erro:
                self._erro(400, f"JSON inválido: {erro}")
                return
            if rota == "/api/vento":
                self._json(self.servidor.definir_vento(corpo))
            elif rota == "/api/reiniciar":
                self._json(self.servidor.reiniciar())
            elif rota == "/api/loop":
                self._json(self.servidor.definir_loop(corpo))
            else:
                self._erro(404, f"rota desconhecida: {rota}")
        except (ValueError, TypeError) as erro:               # valor/faixa/tipo inválido → 400 (estado honesto)
            self._erro(400, str(erro))
        except Exception as erro:                             # noqa: BLE001
            self._erro(500, f"erro interno: {erro!r}")


def criar_handler(servidor: Servidor):
    """Classe de handler já com o estado do servidor ligado (o `BaseHTTPRequestHandler` não tem `__init__` extra)."""
    return type("HandlerLigado", (Handler,), {"servidor": servidor})


# ---------------------------------------------------------------------------------------------- CLI
def analisar_argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="UM comando: arranca o runner (`sim_view.py`), o servidor do site e a API JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("API: GET /api/sim · GET /api/state · POST /api/vento {vel,azimute,elevacao} · "
                "POST /api/reiniciar · POST /api/loop {\"ativo\": bool}\n"
                "Pré-requisito do site: cd site && npm install && npm run build (ver site/LEIAME.md)."))
    p.add_argument("--model", type=Path, default=None, metavar="CAMINHO.zip",
                   help="política PPO (Stable-Baselines3) a pilotar; sem isto a ação é nula (ctrl = τ_trim)")
    p.add_argument("--sem-janela", action="store_true",
                   help="NÃO abre a janela 3D: só site + API + telemetria (validação sem janelas)")
    p.add_argument("--port", type=int, default=8080, metavar="PORTA",
                   help="porta do site (padrão 8080; se estiver ocupada tenta a seguinte; 0 = livre)")
    p.add_argument("--host", default="127.0.0.1", help="interface de escuta (padrão 127.0.0.1: só a tua máquina)")
    p.add_argument("--controlo", type=Path, default=CONTROLO_OMISSAO, metavar="CAMINHO",
                   help="ficheiro de controlo JSON (vento/REINICIAR/LOOP)")
    p.add_argument("--telemetria", type=Path, default=TELEMETRIA_OMISSAO, metavar="CAMINHO",
                   help="ficheiro JSONL da telemetria que o site lê por polling")
    p.add_argument("--fator-tempo", type=float, default=1.0, metavar="F",
                   help="ritmo do runner: 1 = tempo real (padrão), 0,5 = metade, 2 = dobro, 0 = sem travão")
    p.add_argument("--seed", type=int, default=0, help="semente do reset (o episódio N usa seed+N)")
    p.add_argument("--loop", action="store_true", help="arranca o runner com auto-reset no fim do episódio")
    p.add_argument("--sem-browser", action="store_true", help="não abre o browser (o URL sai na mesma)")
    p.add_argument("--verboso", action="store_true", help="mostra cada pedido HTTP no terminal")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = analisar_argumentos(argv)
    if not RUNNER.exists():
        print(f"Erro: runner não encontrado: {RUNNER} — Solução: corre a partir do experimento (pasta com sim_view.py)",
              file=sys.stderr)
        return 1
    porta = porta_livre(args.host, args.port)
    servidor = Servidor(args)
    httpd = ThreadingHTTPServer((args.host, porta), criar_handler(servidor))
    url = f"http://{args.host}:{porta}/"
    print(f"[site] site em {url}", flush=True)
    if not SITE_DIST.is_dir():
        print(f"[site] aviso: {SITE_DIST} não existe — o site mostra as instruções de build "
              f"(cd site && npm install && npm run build; ver site/LEIAME.md)", flush=True)
    servidor.arrancar_runner()

    def fechar(*_args) -> None:
        print("\n[site] a fechar: servidor + runner", flush=True)
        servidor.parar_runner()
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, fechar)
    signal.signal(signal.SIGTERM, fechar)
    if not args.sem_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        servidor.parar_runner()
    return 0


if __name__ == "__main__":
    sys.exit(main())
