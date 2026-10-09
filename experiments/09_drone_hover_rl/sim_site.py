#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/sim_site.py — UM COMANDO: janela MuJoCo limpa + site com métricas e controlos.

Arranca tudo o que o dono precisa numa só linha:

  1. `sim_view.py` como SUBPROCESSO (o seu próprio grupo de processos; SIGTERM/SIGKILL limpos no fim) — é ele
     que abre a janela 100% limpa (só o 3D) e escreve a telemetria;
  2. um servidor HTTP local (só stdlib, `ThreadingHTTPServer`) que serve o SITE (`site/dist/`, com os assets
     em `/assets/...`) e a API que o site consome;
  3. o URL no terminal e o browser aberto (`xdg-open`; `--sem-browser` desliga).

    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py                 # 1 comando
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py --sem-janela     # só site + API
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py --port 0         # porta livre

API (JSON; todas as escritas são ATÓMICAS: tmp + `os.replace` no ficheiro de controlo):
  · `GET  /`                      → `site/dist/index.html` (ou a mensagem "corra npm run build em site/");
                                    qualquer caminho que não seja ficheiro cai no index (rotas do site);
  · `GET  /assets/...`            → ficheiros de `site/dist/` (sem sair da pasta: path traversal é 404);
  · `GET  /api/sim`               → `{"estado","ep","passo","retorno","vento":{...},"linhas":[…]}` com as
                                    ≤200 últimas amostras da telemetria (objetos JSON, já parseados), mais
                                    `modelo`/`modelo_nome` (aditivos: o cabeçalho do site mostra o .zip);
  · `GET  /api/state`             → resumo (acima + `modelo`/`modelo_nome`/`modelo_motivo`, `sim_vivo`,
                                    `pid`, `porta`, caminhos, nº de amostras, idade da última amostra);
  · `POST /api/vento`             → `{"vel","azimute","elevacao"}` (qualquer subconjunto; faixas 0-5 m/s,
                                    0-360°, −90..90°; NaN/inf → 400) e escreve o controlo;
  · `POST /api/reiniciar`         → incrementa `reiniciar` no controlo → `{"contador": n}` (é o ÚNICO
                                    caminho para recomeçar o episódio: o runner não tem auto-loop);
  · `POST /api/loop`              → `{"ativo": bool}` liga/desliga o auto-reset no fim do episódio.

O ficheiro de controlo (o site escreve, o runner lê a cada passo de decisão) e a telemetria (o runner
escreve, o site lê) estão descritos no cabeçalho do `sim_view.py` — este processo só os toca para os criar
(se faltarem) e para responder aos POSTs.
"""
from __future__ import annotations

import argparse
import json
import math
import mimetypes
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
SIM_VIEW = _AQUI / "sim_view.py"
DIST = _AQUI / "site" / "dist"
INDEX = DIST / "index.html"
CONTROLO_OMISSAO = _AQUI / "out" / "controle_vento.json"
TELEMETRIA_OMISSAO = _AQUI / "out" / "sim_telemetria.jsonl"

VEL_MAX, AZIM_MAX, ELEV_MAX = 5.0, 360.0, 90.0     # faixas do contrato (as mesmas do sim_view.py)
CONTROLO_INICIAL = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False, "reiniciar": 0,
                    "loop": False}
MAX_LINHAS = 200                                   # teto de amostras devolvidas por `GET /api/sim`
MAX_CORPO = 64 * 1024                              # teto do corpo de um POST (64 kB chega e sobra)
MAX_LEITURA = 4 * 1024 * 1024                      # bytes lidos do fim da telemetria por pedido
MENSAGEM_SEM_DIST = (
    "site/dist/index.html nao existe — corra `npm run build` em {pasta} (ou `npm install && npm run build`) "
    "e recarregue esta pagina."
)


# ---------------------------------------------------------------------------------------------- ficheiros
def _absoluto(caminho) -> Path:
    """Caminho absoluto (resolvido contra o cwd do SITE, não o do runner) — `--controlo`/`--telemetria`.

    O runner é lançado com `cwd=experiments/09_drone_hover_rl` (para o MUJOCO_LOG.TXT ficar na pasta do
    experimento), por isso um caminho relativo tem de ser fixado aqui: senão o site lia/escrevia num sítio e
    o filho noutro, e a telemetria nunca aparecia na API.
    """
    alvo = Path(caminho).expanduser()
    return alvo if alvo.is_absolute() else (Path.cwd() / alvo).resolve()


def ler_controlo(caminho: Path) -> dict:
    """Controlo em vigor (tolerante: ficheiro ausente/ilegível → valores iniciais do contrato)."""
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            return {**CONTROLO_INICIAL, **dados}
    except (OSError, ValueError):
        pass
    return dict(CONTROLO_INICIAL)


def escrever_controlo(caminho: Path, dados: dict) -> dict:
    """Escreve o controlo de forma ATÓMICA (tmp no mesmo diretório + `os.replace`) e carimba `t`."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    registo = {**CONTROLO_INICIAL, **dados, "t": time.time()}
    tmp = caminho.with_name(f".{caminho.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(registo, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, caminho)                       # troca atómica: o runner nunca lê meio ficheiro
    return registo


def ultimas_linhas(caminho: Path, n: int = MAX_LINHAS) -> list[dict]:
    """Últimas `n` amostras VÁLIDAS da telemetria (lê só o fim do ficheiro; ignora linhas truncadas)."""
    try:
        with Path(caminho).open("rb") as ficheiro:
            ficheiro.seek(0, os.SEEK_END)
            tamanho = ficheiro.tell()
            ficheiro.seek(max(0, tamanho - MAX_LEITURA))
            bruto = ficheiro.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    linhas = []
    for linha in bruto.splitlines():
        linha = linha.strip()
        if not linha.startswith("{"):
            continue                                # 1.ª linha pode estar cortada a meio: ignora-se
        try:
            amostra = json.loads(linha)
        except ValueError:
            continue
        if isinstance(amostra, dict):
            linhas.append(amostra)
    return linhas[-n:]


def resumo_telemetria(caminho: Path) -> dict:
    """`(estado, ep, passo, retorno, nº de amostras na janela, t da última)` a partir do fim da telemetria."""
    linhas = ultimas_linhas(caminho, MAX_LINHAS)
    if not linhas:
        return {"estado": "desconhecido", "ep": 0, "passo": 0, "retorno": 0.0, "linhas": 0, "t": None}
    ultima = linhas[-1]
    return {"estado": str(ultima.get("estado", "desconhecido")), "ep": int(ultima.get("ep", 0) or 0),
            "passo": int(ultima.get("passo", 0) or 0), "retorno": float(ultima.get("retorno", 0.0) or 0.0),
            "linhas": len(linhas), "t": ultima.get("t")}


# ---------------------------------------------------------------------------------------------- validação
def _numero_finito(dados: dict, campo: str) -> float | None:
    """Campo numérico finito do POST; `None` se ausente. `ValueError` se não for número finito (NaN/inf)."""
    if campo not in dados or dados[campo] is None:
        return None
    valor = dados[campo]
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(float(valor)):
        raise ValueError(f"`{campo}` tem de ser um número finito (recebido {valor!r})")
    return float(valor)


def validar_vento(dados, atual: dict) -> dict:
    """`POST /api/vento` → controlo novo (vel/azimute/elevacao validados; o resto do ficheiro fica igual).

    Qualquer subconjunto dos três pode vir no corpo; o que não vem mantém o valor em vigor. `ativo` é
    opcional (por omissão liga-se quando `vel > 0` e desliga-se com `vel == 0`) — é o que faz
    `{"vel": 0}` ser "parar o vento" sem precisar de um campo extra.
    """
    if not isinstance(dados, dict):
        raise ValueError("o corpo tem de ser um objeto JSON")  # noqa: TRY004
    novos = {}
    for campo, teto in (("vel", VEL_MAX), ("azimute", AZIM_MAX), ("elevacao", ELEV_MAX)):
        valor = _numero_finito(dados, campo)
        if valor is None:
            continue
        if campo == "vel" and not 0.0 <= valor <= VEL_MAX:
            raise ValueError(f"`vel` tem de estar em [0, {VEL_MAX}] m/s (recebido {valor!r})")
        if campo == "azimute" and not 0.0 <= valor <= AZIM_MAX:
            raise ValueError(f"`azimute` tem de estar em [0, {AZIM_MAX}] graus (recebido {valor!r})")
        if campo == "elevacao" and not -ELEV_MAX <= valor <= ELEV_MAX:
            raise ValueError(f"`elevacao` tem de estar em [-{ELEV_MAX}, {ELEV_MAX}] graus (recebido {valor!r})")
        novos[campo] = valor
    if not novos:
        raise ValueError("indique pelo menos um de `vel`, `azimute` ou `elevacao`")
    vel = float(novos.get("vel", atual.get("vel", 0.0)))
    ativo = dados.get("ativo")
    if ativo is not None and not isinstance(ativo, bool):
        raise ValueError(f"`ativo` tem de ser booleano (recebido {ativo!r})")
    return {**atual, **novos, "ativo": (vel > 0.0) if ativo is None else ativo}


# ---------------------------------------------------------------------------------------------- servidor
class Servidor:
    """Estado partilhado entre os pedidos: caminhos, processo do runner, modelo e a porta em uso."""

    def __init__(self, controlo: Path, telemetria: Path, host: str, porta: int, verboso: bool = False,
                 filho: subprocess.Popen | None = None, modelo: Path | None = None,
                 motivo: str = ""):
        self.controlo = Path(controlo)
        self.telemetria = Path(telemetria)
        self.host = host
        self.porta = porta
        self.verboso = verboso
        self.filho = filho
        self.modelo = Path(modelo) if modelo is not None else None    # o .zip que o runner carregou
        self.modelo_motivo = motivo or ""                             # porquê este modelo (auditoria)

    @property
    def modelo_nome(self) -> str | None:
        """`pasta/ficheiro.zip` do modelo (o que o cabeçalho do site mostra), ou `None` sem modelo."""
        if self.modelo is None:
            return None
        pasta = self.modelo.parent.name
        return f"{pasta}/{self.modelo.name}" if pasta else self.modelo.name

    @property
    def sim_vivo(self) -> bool:
        return self.filho is not None and self.filho.poll() is None


class Handler(BaseHTTPRequestHandler):
    """Rotas da API + ficheiros de `site/dist/` (sem dependências externas)."""

    servidor: Servidor            # injetado por `criar_handler` (atributo de classe)
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ utilidades de resposta
    def _enviar(self, codigo: int, corpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")     # um `npm run build` novo aparece logo
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def _json(self, codigo: int, dados) -> None:
        self._enviar(codigo, json.dumps(dados, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def _erro(self, codigo: int, mensagem: str) -> None:
        self._json(codigo, {"erro": mensagem, "codigo": codigo})

    def log_message(self, formato: str, *args) -> None:   # assinatura do BaseHTTPRequestHandler
        if self.servidor.verboso:
            print(f"[site] {self.address_string()} {formato % args}", flush=True)

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:                             # assinatura do BaseHTTPRequestHandler
        rota = self.path.split("?", 1)[0]
        try:
            if rota == "/api/sim":
                self._api_sim()
            elif rota == "/api/state":
                self._api_state()
            elif rota.startswith("/api/"):
                self._erro(404, f"rota desconhecida: {rota}")
            else:
                self._estatico(rota)
        except Exception as erro:  # noqa: BLE001  (nenhum pedido pode matar o servidor)
            self._erro(500, f"erro interno: {erro}")

    def _api_sim(self) -> None:
        """`GET /api/sim`: estado do episódio + vento em vigor + as últimas amostras da telemetria.

        `modelo`/`modelo_nome` são ADITIVOS ao contrato original: o site aceita qualquer um deles (no topo ou
        dentro de `probe`) e mostra-o no cabeçalho sem precisar de outro pedido.
        """
        resumo = resumo_telemetria(self.servidor.telemetria)
        controlo = ler_controlo(self.servidor.controlo)
        self._json(200, {
            "estado": resumo["estado"],
            "ep": resumo["ep"],
            "passo": resumo["passo"],
            "retorno": resumo["retorno"],
            "vento": {campo: controlo.get(campo) for campo in ("vel", "azimute", "elevacao", "ativo")},
            "modelo": None if self.servidor.modelo is None else str(self.servidor.modelo),
            "modelo_nome": self.servidor.modelo_nome,
            "linhas": ultimas_linhas(self.servidor.telemetria),
        })

    def _api_state(self) -> None:
        """`GET /api/state`: resumo curto (sem as amostras) para o cabeçalho do site, com o MODELO em uso."""
        resumo = resumo_telemetria(self.servidor.telemetria)
        controlo = ler_controlo(self.servidor.controlo)
        filho = self.servidor.filho
        idade = None if resumo["t"] is None else round(time.time() - _mtime(self.servidor.telemetria), 3)
        self._json(200, {
            "estado": resumo["estado"],
            "ep": resumo["ep"],
            "passo": resumo["passo"],
            "retorno": resumo["retorno"],
            "vento": {campo: controlo.get(campo) for campo in ("vel", "azimute", "elevacao", "ativo")},
            "modelo": None if self.servidor.modelo is None else str(self.servidor.modelo),
            "modelo_nome": self.servidor.modelo_nome,
            "modelo_motivo": self.servidor.modelo_motivo,
            "loop": bool(controlo.get("loop", False)),
            "reiniciar": int(controlo.get("reiniciar", 0) or 0),
            "sim_vivo": self.servidor.sim_vivo,
            "pid": None if filho is None else filho.pid,
            "porta": self.servidor.porta,
            "controlo": str(self.servidor.controlo),
            "telemetria": str(self.servidor.telemetria),
            "amostras": resumo["linhas"],
            "idade_telemetria_s": idade,
            "site_pronto": INDEX.is_file(),
        })

    def _estatico(self, rota: str) -> None:
        """Serve `site/dist/`; sem `index.html` devolve a mensagem de `npm run build` (200, texto simples)."""
        if not INDEX.is_file():
            corpo = MENSAGEM_SEM_DIST.format(pasta=DIST.parent).encode("utf-8")
            self._enviar(200, corpo, "text/plain; charset=utf-8")
            return
        caminho = urllib.parse.unquote(rota)
        if ".." in caminho.split("/"):
            self._erro(404, f"caminho inválido: {rota}")     # traversal: 404 explícito, nunca sai da pasta
            return
        alvo = _ficheiro_do_site(caminho)
        if alvo is None:
            if caminho.startswith("/assets/") or "." in Path(caminho).name:
                self._erro(404, f"não existe: {caminho}")    # asset em falta: 404 (o site tem de o saber)
                return
            alvo = INDEX                                     # rotas do site (SPA): cai no index
        try:
            corpo = alvo.read_bytes()
        except OSError as erro:
            self._erro(404, f"não consegui ler {alvo.name}: {erro}")
            return
        tipo = mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/json"):
            tipo += "; charset=utf-8"
        self._enviar(200, corpo, tipo)

    # ------------------------------------------------------------------ POST
    def do_POST(self) -> None:                            # assinatura do BaseHTTPRequestHandler
        rota = self.path.split("?", 1)[0]
        try:
            dados = self._ler_corpo()
            if rota == "/api/vento":
                self._post_vento(dados)
            elif rota == "/api/reiniciar":
                self._post_reiniciar()
            elif rota == "/api/loop":
                self._post_loop(dados)
            else:
                self._erro(404, f"rota desconhecida: {rota}")
        except _PedidoInvalido as erro:
            self._erro(400, str(erro))
        except Exception as erro:  # noqa: BLE001  (nenhum pedido pode matar o servidor)
            self._erro(500, f"erro interno: {erro}")

    def _ler_corpo(self):
        """Corpo do pedido já em JSON (objeto vazio se vier vazio; `_PedidoInvalido` se não for JSON)."""
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise _PedidoInvalido("Content-Length inválido") from None
        if tamanho < 0 or tamanho > MAX_CORPO:
            raise _PedidoInvalido(f"corpo com {tamanho} bytes (máximo {MAX_CORPO})")
        if tamanho == 0:
            return {}
        bruto = self.rfile.read(tamanho)
        try:
            return json.loads(bruto.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as erro:
            raise _PedidoInvalido(f"corpo não é JSON válido: {erro}") from None

    def _post_vento(self, dados) -> None:
        """Valida as faixas, escreve o controlo (atómico) e devolve o vento que ficou em vigor."""
        atual = ler_controlo(self.servidor.controlo)
        try:
            novo = validar_vento(dados, atual)
        except ValueError as erro:
            self._erro(400, str(erro))
            return
        registo = escrever_controlo(self.servidor.controlo, novo)
        print(f"[site] vento: {registo['vel']:.2f} m/s @ {registo['azimute']:.1f} deg"
              f" (elev {registo['elevacao']:+.1f}, {'ativo' if registo['ativo'] else 'desligado'})", flush=True)
        self._json(200, {"ok": True, "vento": {campo: registo[campo] for campo in
                                               ("vel", "azimute", "elevacao", "ativo")}})

    def _post_reiniciar(self) -> None:
        """Incrementa o contador `reiniciar`: é o ÚNICO caminho para recomeçar o episódio (sem auto-loop)."""
        atual = ler_controlo(self.servidor.controlo)
        contador = int(atual.get("reiniciar", 0) or 0) + 1
        escrever_controlo(self.servidor.controlo, {**atual, "reiniciar": contador})
        print(f"[site] REINICIAR pedido (contador {contador})", flush=True)
        self._json(200, {"contador": contador})

    def _post_loop(self, dados) -> None:
        """Liga/desliga o auto-reset no fim do episódio (`{"ativo": bool}`)."""
        if not isinstance(dados, dict):
            self._erro(400, "o corpo tem de ser um objeto JSON")
            return
        ativo = dados.get("ativo", dados.get("loop"))
        if not isinstance(ativo, bool):
            self._erro(400, f"`ativo` tem de ser booleano (recebido {ativo!r})")
            return
        atual = ler_controlo(self.servidor.controlo)
        escrever_controlo(self.servidor.controlo, {**atual, "loop": ativo})
        print(f"[site] loop {'ligado' if ativo else 'desligado'}", flush=True)
        self._json(200, {"ok": True, "loop": ativo})


class _PedidoInvalido(Exception):
    """Corpo/parâmetros maus → HTTP 400."""


def _ficheiro_do_site(rota: str) -> Path | None:
    """Ficheiro de `site/dist/` correspondente à rota, ou `None` (404/SPA). Nunca sai da pasta do site."""
    relativo = rota.lstrip("/") or "index.html"
    if relativo.endswith("/"):
        relativo += "index.html"
    alvo = (DIST / relativo).resolve()
    if not alvo.is_relative_to(DIST.resolve()) or not alvo.is_file():
        return None
    return alvo


def _mtime(caminho: Path) -> float:
    try:
        return Path(caminho).stat().st_mtime
    except OSError:
        return time.time()


def criar_handler(servidor: Servidor):
    """Classe de handler já com o estado do servidor ligado (o `BaseHTTPRequestHandler` não tem __init__ extra)."""
    return type("HandlerLigado", (Handler,), {"servidor": servidor})


def abrir_servidor(host: str, porta: int, servidor: Servidor) -> ThreadingHTTPServer:
    """`ThreadingHTTPServer` na porta pedida (0 = livre), tentando as 10 seguintes se estiver ocupada."""
    tentativas = [porta] if porta == 0 else [porta + i for i in range(11)]
    for tentativa in tentativas:
        try:
            httpd = ThreadingHTTPServer((host, tentativa), criar_handler(servidor))
        except OSError as erro:
            if porta == 0 or tentativa == tentativas[-1]:
                raise SystemExit(f"[site] não consegui abrir {host}:{tentativa} ({erro}) — escolha outra "
                                 f"--port") from erro
            continue
        if tentativa != porta:
            print(f"[site] porta {porta} ocupada: fico na {tentativa}", flush=True)
        servidor.porta = int(httpd.server_address[1])
        httpd.daemon_threads = True
        return httpd
    raise SystemExit("[site] não consegui abrir nenhuma porta")      # inalcançável (o ciclo já saiu)


# ---------------------------------------------------------------------------------------------- runner
def _mais_recente(caminhos) -> Path | None:
    """Ficheiro mais recente de `caminhos` (empate desfeito pelo nome, para ser determinístico)."""
    ficheiros = [p for p in caminhos if p.is_file()]
    return max(ficheiros, key=lambda p: (p.stat().st_mtime_ns, str(p))) if ficheiros else None


def _modelo_validado(out: Path) -> tuple[Path, str] | None:
    """Modelo da ÚLTIMA validação COM SUCESSO em `out/avaliacao_vento/*.json` que ainda exista em disco.

    Os relatórios do `avaliar_vento.py`/`avaliar_denso.py` gravam
    `{"modelo": ..., "n_pass": ..., "n_total": ..., "satisfatorio": bool}` (o `modelo` é relativo à raiz do
    laboratório). Só contam os `satisfatorio: true` (ou `n_pass == n_total`): uma validação que correu MAL
    não promove ninguém. É a melhor pista que existe em disco sobre qual política voa bem — foi o que o dono
    validou (ex.: `vento_r9_polir_vento3/final.zip`, 16/16).
    """
    registos = sorted((out / "avaliacao_vento").glob("*.json"),
                      key=lambda p: p.stat().st_mtime_ns, reverse=True)
    for registo in registos:
        try:
            dados = json.loads(registo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(dados, dict) or not isinstance(dados.get("modelo"), str) or not dados["modelo"]:
            continue
        n_pass, n_total, ok = dados.get("n_pass"), dados.get("n_total"), dados.get("satisfatorio")
        if ok is None:
            ok = (isinstance(n_pass, int) and isinstance(n_total, int) and n_total > 0
                  and n_pass == n_total)
        if not ok:
            continue
        caminho = Path(dados["modelo"])
        if not caminho.is_absolute():
            caminho = _RAIZ / caminho       # os relatórios gravam caminhos relativos à raiz do laboratório
        if caminho.is_file():
            resumo = f"{n_pass}/{n_total}" if isinstance(n_pass, int) and isinstance(n_total, int) else "ok"
            return caminho, f"validacao mais recente ({registo.name}: {resumo})"
    return None


def modelo_por_omissao() -> tuple[Path, str]:
    """`(caminho, motivo)` do modelo por omissão — a ordem de preferência é a MESMA do `sim_view.py`.

    1. o modelo da ÚLTIMA validação com sucesso em `out/avaliacao_vento/*.json` que exista em disco
       (é a política validada pelo dono — ex.: `vento_r9_polir_vento3/final.zip`, 16/16);
    2. `out/vento_*/final.zip` mais recente SEM `_seed` no nome (os "polir/curr" treinados com vento);
    3. `out/vento_*_seed*/final.zip` mais recente (as séries com sementes);
    4. `out/runs/*/final.zip` mais recente;
    5. um `best_model.zip` qualquer (`out/vento_*/` ou `out/runs/*/`) — último recurso;
    6. `SystemExit` com mensagem clara se não houver nada.

    Nunca se escolhe um `best_model.zip` de `out/runs/*/` enquanto existir um `final.zip` de `out/vento_*/`
    (era isso que punha a política fraca antiga a voar e o drone a "sumir" logo no arranque).
    """
    out = _AQUI / "out"
    validado = _modelo_validado(out)
    if validado is not None:
        return validado
    vento = sorted(out.glob("vento_*/final.zip"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    candidato = _mais_recente(p for p in vento if "_seed" not in p.parent.name)
    if candidato is not None:
        return candidato, "vento_*/final.zip mais recente (sem _seed)"
    candidato = _mais_recente(vento)
    if candidato is not None:
        return candidato, "vento_*_seed*/final.zip mais recente"
    candidato = _mais_recente((out / "runs").glob("*/final.zip"))
    if candidato is not None:
        return candidato, "runs/*/final.zip mais recente"
    candidato = _mais_recente(list((out / "runs").glob("*/best_model.zip"))
                              + list(out.glob("vento_*/best_model.zip")))
    if candidato is not None:
        return candidato, "best_model.zip mais recente (ultimo recurso)"
    raise SystemExit(f"[site] nenhum modelo em {out} (avaliacao_vento/*.json, vento_*/final.zip, "
                     "runs/*/final.zip, best_model.zip) — treine primeiro (train.py) ou indique --model "
                     "CAMINHO")


def escolher_modelo(args) -> tuple[Path, str]:
    """`(caminho absoluto, motivo)` do modelo a usar: `--model` explícito manda; senão o por omissão."""
    if args.model is not None:
        return _absoluto(args.model), "explicito (--model)"
    return modelo_por_omissao()


def comando_do_runner(args, modelo: Path | None = None) -> list[str]:
    """Linha de comandos do `sim_view.py` (o `--sem-janela` do site é repassado ao filho).

    O `--model` vai SEMPRE explícito: é o caminho que o site já resolveu (e anuncia na API), para o runner
    carregar exactamente o mesmo ficheiro que o site diz estar a correr.
    """
    comando = [sys.executable, str(SIM_VIEW), "--controlo", str(args.controlo),
               "--telemetria", str(args.telemetria)]
    alvo = modelo if modelo is not None else args.model
    if alvo is not None:
        comando += ["--model", str(alvo)]
    if args.sem_janela:
        comando.append("--sem-janela")
    if args.fator_tempo is not None:
        comando += ["--fator-tempo", f"{args.fator_tempo:g}"]
    if args.loop:
        comando.append("--loop")
    return comando


def lancar_runner(args, modelo: Path | None = None) -> subprocess.Popen:
    """Arranca o `sim_view.py` no seu PRÓPRIO grupo de processos (para o SIGTERM apanhar tudo)."""
    comando = comando_do_runner(args, modelo)
    print(f"[site] runner: {' '.join(comando)}", flush=True)
    return subprocess.Popen(comando, cwd=str(_AQUI), start_new_session=True)   # herda stdout/stderr


def terminar_runner(filho: subprocess.Popen | None, limite: float = 5.0) -> None:
    """SIGTERM ao grupo do runner (SIGKILL se ele não sair em `limite` s) — sempre sem deixar órfãos."""
    if filho is None or filho.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(filho.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        filho.terminate()
    try:
        filho.wait(timeout=limite)
        print(f"[site] runner terminou (exit {filho.returncode})", flush=True)
        return
    except subprocess.TimeoutExpired:
        print("[site] runner não saiu com SIGTERM: SIGKILL", flush=True)
    try:
        os.killpg(os.getpgid(filho.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        filho.kill()
    try:
        filho.wait(timeout=limite)
    except subprocess.TimeoutExpired:
        print("[site] aviso: runner resistiu ao SIGKILL", file=sys.stderr, flush=True)


def abrir_browser(url: str) -> None:
    """`xdg-open URL` (sem bloquear); aviso claro se não houver abridor."""
    abridor = shutil.which("xdg-open")
    if abridor is None:
        print(f"[site] xdg-open não existe: abra {url} à mão", file=sys.stderr, flush=True)
        return
    try:
        subprocess.Popen([abridor, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        print(f"[site] browser aberto em {url}", flush=True)
    except OSError as erro:
        print(f"[site] não consegui abrir o browser ({erro}): abra {url} à mão", file=sys.stderr, flush=True)


def analisar_argumentos(argv=None) -> argparse.Namespace:
    """Argumentos do comando único (os do runner são repassados tal e qual)."""
    p = argparse.ArgumentParser(
        description="UM COMANDO: janela MuJoCo limpa (sim_view.py) + site com métricas e controlos "
                    "(site/dist/) + API local. O vento e o REINICIAR vão pelo ficheiro de controlo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("API: GET /api/sim · GET /api/state · POST /api/vento {vel,azimute,elevacao} · "
                "POST /api/reiniciar · POST /api/loop {\"ativo\": bool}\n"
                "SIGINT/SIGTERM: fecha o servidor e mata o runner (exit 0)."),
    )
    p.add_argument("--model", type=Path, default=None,
                   help="modelo do Stable-Baselines3 (.zip) para o runner; por omissão o site escolhe por "
                        "esta ordem: o modelo da última validação com sucesso (out/avaliacao_vento/*.json) "
                        "-> vento_*/final.zip mais recente (sem _seed) -> vento_*_seed*/final.zip -> "
                        "runs/*/final.zip -> best_model.zip; passa-o explícito ao runner e anuncia-o "
                        "(com o motivo) em /api/state e /api/sim")
    p.add_argument("--sem-janela", action="store_true",
                   help="só site + API (o runner corre sem viewer: nada de GLFW/GL) — é o modo dos testes")
    p.add_argument("--port", type=int, default=8080, metavar="PORTA",
                   help="porta do site; 0 = uma porta livre escolhida pelo sistema (padrão: 8080; se estiver "
                        "ocupada tenta as 10 seguintes)")
    p.add_argument("--host", default="127.0.0.1",
                   help="interface onde servir o site (padrão: 127.0.0.1, só a máquina local)")
    p.add_argument("--controlo", type=Path, default=CONTROLO_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro de controlo (vento/reiniciar/loop); padrão: {CONTROLO_OMISSAO}")
    p.add_argument("--telemetria", type=Path, default=TELEMETRIA_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro JSONL de telemetria do runner; padrão: {TELEMETRIA_OMISSAO}")
    p.add_argument("--fator-tempo", type=float, default=None, metavar="F",
                   help="ritmo do runner (1 = tempo real; 0 = sem travão); por omissão usa o do sim_view.py")
    p.add_argument("--loop", action="store_true", help="arranca o runner com auto-reset no fim do episódio")
    p.add_argument("--sem-browser", action="store_true", help="não abre o browser (o URL sai na mesma)")
    p.add_argument("--verboso", action="store_true", help="mostra cada pedido HTTP no terminal")
    return p.parse_args(argv)


def main(argv=None) -> int:
    """Arranca o runner + o servidor e fica à espera de SIGINT/SIGTERM (exit 0)."""
    args = analisar_argumentos(argv)
    if not SIM_VIEW.is_file():
        raise SystemExit(f"[site] falta o runner: {SIM_VIEW}")
    # O runner corre com cwd=experiments/09_drone_hover_rl: um caminho RELATIVO dado ao site (--controlo,
    # --telemetria, --model) tem de ser resolvido AQUI, senão o site lia/escrevia num sítio e o filho noutro.
    args.controlo = _absoluto(args.controlo)
    args.telemetria = _absoluto(args.telemetria)
    if not INDEX.is_file():
        print(f"[site] aviso: {MENSAGEM_SEM_DIST.format(pasta=DIST.parent)}", flush=True)
    if not args.controlo.exists():
        # o `loop` inicial segue o CLI: se o ficheiro nascesse com `loop: false`, desligava logo o `--loop`
        escrever_controlo(args.controlo, {**CONTROLO_INICIAL, "loop": bool(args.loop)})
        print(f"[site] controlo criado: {args.controlo} (loop={bool(args.loop)})", flush=True)

    # o runner corre com cwd=experiments/09_drone_hover_rl: `--model` relativo resolve-se contra o cwd do SITE
    modelo, motivo = escolher_modelo(args)
    if not modelo.is_file():
        raise SystemExit(f"[site] modelo inexistente: {modelo}")
    print(f"[site] modelo: {modelo} ({motivo})", flush=True)   # diz SEMPRE qual escolheu e porquê
    filho = lancar_runner(args, modelo)
    servidor = Servidor(args.controlo, args.telemetria, args.host, args.port, args.verboso, filho, modelo,
                        motivo)
    httpd = abrir_servidor(args.host, args.port, servidor)
    url = f"http://{args.host}:{servidor.porta}/"
    print(f"[site] runner pid {filho.pid} | controlo {args.controlo} | telemetria {args.telemetria}",
          flush=True)
    print(f"[site] site em {url} (Ctrl+C fecha)", flush=True)

    parar = threading.Event()

    def ao_sinal(_sinal, _frame):
        parar.set()

    for sinal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sinal, ao_sinal)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    if not args.sem_browser:
        abrir_browser(url)

    avisado = False
    try:
        while not parar.wait(0.2):
            if not avisado and filho.poll() is not None:
                print(f"[site] aviso: o runner terminou (exit {filho.returncode}) — o site continua a servir "
                      f"o que já está na telemetria", flush=True)
                avisado = True
    finally:
        print("[site] a fechar (servidor + runner)...", flush=True)
        httpd.shutdown()
        httpd.server_close()
        terminar_runner(filho)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # `stdout` fechou do outro lado (ex.: `| head`): sair sem traceback e sem o aviso de flush
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
