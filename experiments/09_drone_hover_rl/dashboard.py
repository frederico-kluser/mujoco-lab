#!/usr/bin/env python3
"""dashboard.py — UI web LOCAL do experimento 09 (drone hover RL): "clicar para treinar" + rede ao vivo.

Servidor de ficheiros/estado, NUNCA treina dentro do processo (GIL): todo o trabalho pesado vive em
subprocessos — `train.py` (treino PPO) e `net_probe.py` (a rede a correr, sem viewer). O servidor só lê
ficheiros e faz `Popen`/`SIGTERM`. Só biblioteca padrão (`http.server`, `json`, `subprocess`, `threading`);
a página é uma string embutida (HTML+CSS+JS vanilla, SEM CDN — funciona offline). `numpy` é importado
lazy e só para ler `evaluations.npz` (já é dependência do projeto; nenhuma dependência nova).

    uv run --group hover-rl python experiments/09_drone_hover_rl/dashboard.py          # porta livre, anuncia o URL
    uv run --group hover-rl python experiments/09_drone_hover_rl/dashboard.py --port 8765 --out "$TMPDIR/runs"

CONVENÇÃO DE FICHEIROS (os runs vivem sob `<--out>`; default `experiments/09_drone_hover_rl/out/`)
    <out>/<run>/train_log.jsonl    1 linha JSON por avaliação/registo do treino (o `train.py` escreve-a)
    <out>/<run>/train_stdout.log   stdout+stderr do `train.py` (o painel rich vive aqui; a UI mostra a cauda)
    <out>/<run>/best_model.zip     checkpoint da política (a dropdown da rede ao vivo lista estes)
    <out>/<run>/evaluations.npz    avaliações do SB3 (lido por `GET /api/evals`)
    <--net-out>                    JSONL da sonda (default `out/net.jsonl`, escrito pelo `net_probe.py`)
    <--vento-out>                  controlo de VENTO ao vivo (default `out/controle_vento.json`; o painel
                                   «VENTO» escreve-o e o `net_probe.py` vigia-o a cada passo de decisão)
O varrimento aceita os DOIS layouts — `<out>/<run>/…` (o que o botão ▶ usa) e `<out>/runs/<run>/…` (o
default do `train.py`: `out/runs/seed<seed>`, dois níveis) — e também `--out` apontado a `out/runs`.

API (todas as respostas são JSON; os handlers são curtos e nunca bloqueiam à espera de um processo)
    GET  /                     página única (HTML embutido)
    GET  /api/state            {train, log[≤200], stdout[≤120], runs[], probe, vento, servidor}
    GET  /api/run?run=NOME     séries do run (t, mean_ret, mean_z) p/ as curvas; `max` limita os pontos
    GET  /api/net              última linha do JSONL da sonda + {probe: {running, pid, ...}}
    GET  /api/evals?run=NOME   `evaluations.npz` do run como listas JSON
    GET  /api/vento            estado atual do controlo de vento (o ficheiro + mtime/idade + sonda)
    POST /api/start            {timesteps, seed, n_envs, out_dir?, extra?} → Popen do train.py
    POST /api/stop             SIGTERM ao processo de treino (deixa os checkpoints); SIGKILL após 8 s
    POST /api/net/start        {model, interval?, fator_tempo?} → Popen do net_probe.py (com `--controlo`;
                               `fator_tempo` 1 = tempo real, 0 = o mais rápido possível)
    POST /api/net/stop         SIGTERM ao net_probe.py
    POST /api/vento            {vel 0–5 m/s, azimute 0–360°, elevacao −90–90°, ativo?} → escreve o
                               controlo de vento (tmp + rename ATÓMICO) que o `net_probe.py` aplica;
                               400 se algum valor não for numérico ou sair da faixa.

VENTO AO VIVO (o painel «VENTO» da UI): o dashboard só ESCREVE o ficheiro; quem empurra o drone é o
`net_probe.py`, que o vigia por mtime a cada passo de decisão e chama `env.definir_vento(...)`. Assim a
física e a rede continuam 100 % no subprocesso (nada de simulação dentro do servidor) e o mesmo ficheiro
serve qualquer consumidor externo. Azimute 0° → +x, 90° → +y; «PARAR VENTO» grava `ativo: false` (vento 0).

INTEGRAÇÃO COM O `train.py` (ele é de outra peça; aqui não se assume mais do que isto): a linha de comando é
montada com os flags que o `--help` do `train.py` ACEITAR (`--timesteps`, `--seed`, `--n-envs`/`--n_envs`,
`--out-dir`/`--out`…; o `--help` corre UMA vez por servidor e demora uns segundos — importa o torch); o run-dir
vai SEMPRE também nas variáveis de ambiente `HOVER_OUT_DIR` e `HOVER_RL_OUT_DIR`, para o caso de o `train.py`
não ter flag de saída. Se o `train.py` não existir, o `POST /api/start` responde 400 com erro limpo
("integração de treino pendente") e o resto da UI (curvas, rede ao vivo, runs antigos) continua a funcionar.
O processo arranca no diretório da raiz do laboratório (cwd = raiz, MUJOCO_GL=egl, PYTHONUNBUFFERED=1,
PYTHONPATH com raiz + pasta do experimento) e o `--train-py` permite apontar a outro treinador (útil em teste).
"""
from __future__ import annotations

import argparse
import errno
import json
import math
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
TRAIN_PY = _AQUI / "train.py"
PROBE_PY = _AQUI / "net_probe.py"
OUT_PADRAO = _AQUI / "out"
NET_PADRAO = OUT_PADRAO / "net.jsonl"
CONTROLO_PADRAO = OUT_PADRAO / "controle_vento.json"   # controlo de vento ao vivo (lido pelo net_probe.py)

# faixas do painel «VENTO» (contrato v2): validam-se no POST /api/vento e desenham-se nos sliders da UI
VENTO_VEL = (0.0, 5.0)         # m/s
VENTO_AZIMUTE = (0.0, 360.0)   # graus (azimute 0° → +x, 90° → +y)
VENTO_ELEVACAO = (-90.0, 90.0)  # graus (positivo → componente +z)

# limites do corpo dos pedidos: acima de LIMITE_CORPO responde-se 413 e o corpo é DESCARTADO do socket
# (sem isso, em HTTP/1.1 keep-alive os bytes sobrantes seriam lidos como o pedido SEGUINTE — «414 URI Too Long»).
# Acima de LIMITE_DESCARTE não vale a pena ler: fecha-se a ligação (a resposta leva `Connection: close`).
LIMITE_CORPO = 1_048_576       # 1 MiB — folgado para os JSON pequenos desta API
LIMITE_DESCARTE = 8 * 1024 * 1024

# faixa VÁLIDA do alvo do `HoverEnv` (`alvo_z`): ESPELHA ALVO_Z_MIN/ALVO_Z_MAX de env.py — o dashboard não
# importa o env (traria mujoco/gymnasium para o servidor). Validar aqui recusa cedo o pedido, em vez de lançar
# a sonda para ela morrer com ValueError (a UI nem expõe `alvo_z`; é o `POST /api/net/start` que o aceita).
ALVO_Z_MIN = 0.10              # m
ALVO_Z_MAX = 2.90              # m

# chaves aceites no train_log.jsonl (o `train.py` é de outra peça: aceitamos os nomes SB3/plotext/PT)
CHAVES_T = ("t", "timesteps", "total_timesteps", "step", "passos", "n_steps", "tempo", "iteracao")
CHAVES_RET = ("mean_ret", "mean_reward", "ep_rew_mean", "reward", "retorno", "r", "recompensa")
CHAVES_Z = ("mean_z", "z", "mean_dist_z", "dist_z", "z_medio", "altura")
MARCA = ("train_log.jsonl", "train_stdout.log", "best_model.zip", "evaluations.npz", "last_model.zip")


class ErroAPI(Exception):
    """Erro de pedido com código HTTP (a resposta sai como JSON `{"erro": ...}`)."""

    def __init__(self, codigo: int, mensagem: str):
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem


# ------------------------------------------------------------------------------------------- utilidades
def _numero(objeto, chaves) -> float | None:
    """Primeiro campo numérico finito entre `chaves` (ou None)."""
    if not isinstance(objeto, dict):
        return None
    for k in chaves:
        v = objeto.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        if math.isfinite(v):
            return float(v)
    return None


def _normaliza(linha: dict) -> dict:
    """Linha do train_log.jsonl → {t, mean_ret, mean_z} + a linha crua (`cru`) para o painel de log."""
    return {"t": _numero(linha, CHAVES_T), "mean_ret": _numero(linha, CHAVES_RET),
            "mean_z": _numero(linha, CHAVES_Z), "cru": linha}


def _vento_validado(corpo: dict) -> dict:
    """Corpo do `POST /api/vento` → {vel, azimute, elevacao, ativo} validado (ErroAPI 400 se inválido).

    Faixas do painel: `vel` ∈ [0, 5] m/s · `azimute` ∈ [0, 360]° · `elevacao` ∈ [−90, 90]° (default 0). Um
    corpo sem nenhum dos quatro campos é recusado (provável engano do cliente); campos em falta valem os
    defaults (`azimute`/`elevacao` = 0, `ativo` = true), para `{"ativo": false}` — o «PARAR VENTO» — bastar.
    """
    if not isinstance(corpo, dict) or not any(k in corpo for k in ("vel", "azimute", "elevacao", "ativo")):
        raise ErroAPI(400, "corpo sem campos de vento (esperava `vel`, `azimute`, `elevacao` e/ou `ativo`)")

    def numero(campo: str, predefinido: float) -> float:
        if campo not in corpo or corpo[campo] is None:
            return predefinido
        v = corpo[campo]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ErroAPI(400, f"`{campo}` tem de ser um número (recebido {v!r})")
        if not math.isfinite(float(v)):
            raise ErroAPI(400, f"`{campo}` tem de ser finito (recebido {v!r})")
        return float(v)

    ativo = corpo.get("ativo", True)
    if isinstance(ativo, bool):
        pass
    elif isinstance(ativo, int) and ativo in (0, 1):
        ativo = bool(ativo)
    else:
        raise ErroAPI(400, f"`ativo` tem de ser booleano (recebido {ativo!r})")

    valores = {"vel": numero("vel", 0.0), "azimute": numero("azimute", 0.0), "elevacao": numero("elevacao", 0.0)}
    for campo, (minimo, maximo) in (("vel", VENTO_VEL), ("azimute", VENTO_AZIMUTE),
                                     ("elevacao", VENTO_ELEVACAO)):
        valor = valores[campo]
        if not (minimo <= valor <= maximo):
            raise ErroAPI(400, f"`{campo}` fora da faixa [{minimo:g}, {maximo:g}] (recebido {valor:g})")
    return {**valores, "ativo": bool(ativo)}


def _loop_validado(corpo: dict) -> bool:
    """`{"ativo": <bool>}` do `POST /api/loop` → bool (400 se faltar ou não for booleano)."""
    if not isinstance(corpo, dict) or "ativo" not in corpo:
        raise ErroAPI(400, "falta o campo `ativo` (true = LOOP ligado, false = para no fim do episódio)")
    ativo = corpo["ativo"]
    if isinstance(ativo, bool):
        return ativo
    if isinstance(ativo, int) and ativo in (0, 1):        # tolera 0/1 de clientes simples
        return bool(ativo)
    raise ErroAPI(400, f"`ativo` tem de ser booleano (recebido {ativo!r})")


def _ler_jsonl(caminho: Path, limite: int | None = None) -> list[tuple[dict | None, str]]:
    """[(objeto|None, linha crua)] de um JSONL; linhas não-JSON ficam com objeto None (não rebenta nada)."""
    if not caminho.is_file():
        return []
    saida: list[tuple[dict | None, str]] = []
    try:
        with open(caminho, "r", encoding="utf-8", errors="replace") as f:
            for linha in f:
                linha = linha.rstrip("\n")
                if not linha.strip():
                    continue
                try:
                    objeto = json.loads(linha)
                    objeto = objeto if isinstance(objeto, dict) else {"valor": objeto}
                except json.JSONDecodeError:
                    objeto = None
                saida.append((objeto, linha))
    except OSError:
        return []
    return saida[-limite:] if limite else saida


def _cauda(caminho: Path, n: int) -> list[str]:
    """Últimas `n` linhas de um ficheiro de texto (lê o fim do ficheiro, não o ficheiro todo)."""
    if not caminho.is_file():
        return []
    try:
        with open(caminho, "rb") as f:
            f.seek(0, os.SEEK_END)
            tamanho = f.tell()
            bloco = min(tamanho, 262_144)
            f.seek(tamanho - bloco)
            dados = f.read(bloco)
    except OSError:
        return []
    linhas = dados.decode("utf-8", errors="replace").splitlines()
    return linhas[-n:]


def _ultima_json(caminho: Path, bloco: int = 131_072) -> dict | None:
    """Última linha JSON de um ficheiro (lê só o fim; devolve None se vazio/ilegível)."""
    if not caminho.is_file():
        return None
    try:
        with open(caminho, "rb") as f:
            f.seek(0, os.SEEK_END)
            tamanho = f.tell()
            if tamanho == 0:
                return None
            f.seek(max(0, tamanho - bloco))
            linhas = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for linha in reversed(linhas):
        if not linha.strip():
            continue
        try:
            objeto = json.loads(linha)
        except json.JSONDecodeError:
            continue
        return objeto if isinstance(objeto, dict) else {"valor": objeto}
    return None


def _amostrar(valores: list, max_pontos: int) -> list:
    """Downsample por passo inteiro (mantém o primeiro e o último ponto) para respostas pequenas."""
    n = len(valores)
    if n <= max_pontos or max_pontos <= 2:
        return valores
    passo = max(1, n // max_pontos)
    recortado = valores[::passo]
    if recortado and recortado[-1] != valores[-1]:
        recortado.append(valores[-1])
    return recortado


def _contar_linhas(caminho: Path, anterior: tuple[int, int]) -> tuple[int, int]:
    """Estado (tamanho, linhas) de um ficheiro em APPEND — conta só o que cresceu desde `anterior`."""
    if not caminho.is_file():
        return (0, 0)
    try:
        tamanho = caminho.stat().st_size
        linhas, inicio = anterior[1], anterior[0]
        if tamanho < inicio:                      # o ficheiro foi truncado (sonda nova) → recontar
            linhas, inicio = 0, 0
        if tamanho == inicio:
            return (tamanho, linhas)
        with open(caminho, "rb") as f:
            f.seek(inicio)
            linhas += f.read(tamanho - inicio).count(b"\n")
        return (tamanho, linhas)
    except OSError:
        return anterior


# ------------------------------------------------------------------------------------------- estado
class Estado:
    """Estado do dashboard: processos lançados (treino/sonda), runs em disco e leitura de ficheiros."""

    def __init__(self, out_dir: Path, net_jsonl: Path, train_py: Path | None = None,
                 controlo_vento: Path | None = None) -> None:
        self.out_dir = out_dir
        self.net_jsonl = net_jsonl
        self.train_py = Path(train_py) if train_py is not None else TRAIN_PY
        self.controlo_vento = Path(controlo_vento) if controlo_vento is not None else CONTROLO_PADRAO
        self.trava = threading.RLock()
        self.proc: subprocess.Popen | None = None
        self.proc_log: object | None = None
        self.cmd: list[str] = []
        self.out_run: Path | None = None
        self.iniciado: float | None = None          # monotonic
        self.iniciado_wall: float | None = None     # epoch (comparado com mtime dos ficheiros)
        self.saida: int | None = None
        self.duracao: float | None = None
        self.flags: list[str] = []
        self.flags_omitidas: list[str] = []
        self.probe: subprocess.Popen | None = None
        self.probe_log: object | None = None
        self.probe_cmd: list[str] = []
        self.probe_modelo: str | None = None
        self.probe_iniciado: float | None = None
        self.probe_saida: int | None = None
        self._flags_cache: set[str] | None = None
        self._flags_sondado = False
        self._contagem = (0, 0)                     # (tamanho, linhas) do JSONL da sonda

    # ------------------------------------------------------------------ processos
    def _env(self, extra: dict | None = None) -> dict:
        """Ambiente do filho: headless, sem buffer, `lab`/`env` importáveis e o run-dir em variáveis."""
        env = dict(os.environ)
        env["MUJOCO_GL"] = env.get("MUJOCO_GL", "egl")
        env["PYTHONUNBUFFERED"] = "1"
        caminhos = [str(_RAIZ), str(_AQUI)]
        if env.get("PYTHONPATH"):
            caminhos.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(caminhos)
        if self.out_run is not None:
            env["HOVER_OUT_DIR"] = str(self.out_run)
            env["HOVER_RL_OUT_DIR"] = str(self.out_run)
        if extra:
            env.update(extra)
        return env

    def _flags_train(self) -> set[str] | None:
        """Flags que o `train.py --help` aceita (uma vez por servidor); None se o help falhar."""
        if self._flags_sondado:
            return self._flags_cache
        aceitas: set[str] | None = None
        try:
            r = subprocess.run([sys.executable, str(self.train_py), "--help"], capture_output=True,
                               text=True, timeout=45, cwd=str(_RAIZ), check=False)
            texto = (r.stdout or "") + (r.stderr or "")
            achadas = set(re.findall(r"--[A-Za-z0-9][A-Za-z0-9_-]*", texto))
            aceitas = achadas or None
        except (OSError, subprocess.SubprocessError):
            aceitas = None
        self._flags_cache, self._flags_sondado = aceitas, True
        return aceitas

    def _cmd_treino(self, timesteps: int, seed: int, n_envs: int, runs_dir: Path, extra: str) -> list[str]:
        """Linha de comando do train.py: só passa os flags que ele reconhece (candidatos por parâmetro)."""
        candidatos = (("timesteps", ("--timesteps", "--total-timesteps", "--passos"), str(timesteps)),
                      ("seed", ("--seed", "--semente"), str(seed)),
                      ("n_envs", ("--n-envs", "--n_envs", "--nenvs", "--num-envs"), str(n_envs)),
                      ("out_dir", ("--out-dir", "--out_dir", "--outdir", "--out", "--saida"), str(runs_dir)))
        aceitas = self._flags_train()
        cmd = [sys.executable, str(self.train_py)]
        self.flags, self.flags_omitidas = [], []
        for nome, opcoes, valor in candidatos:
            if aceitas is None:                       # help indisponível: usa o 1.º candidato de cada
                escolhido = opcoes[0]
            else:
                escolhido = next((o for o in opcoes if o in aceitas), None)
            if escolhido is None:
                self.flags_omitidas.append(f"{nome} (nenhum de {'/'.join(opcoes)} no --help)")
                continue
            cmd += [escolhido, valor]
            self.flags.append(f"{escolhido}={valor}")
        if extra:
            cmd += shlex.split(extra)
        return cmd

    def iniciar_treino(self, corpo: dict) -> dict:
        """Lança o `train.py` em subprocesso (stdout → train_stdout.log do run). Devolve o descritor do run."""
        with self.trava:
            if self.proc is not None and self.proc.poll() is None:
                raise ErroAPI(409, f"já há um treino a correr (pid {self.proc.pid}); para-o primeiro")
            if not self.train_py.is_file():
                raise ErroAPI(400, f"train.py ainda não existe nesta pasta ({self.train_py.name} em falta): "
                                   "integração de treino pendente — a UI e a sondagem da rede funcionam já")
            try:
                timesteps = int(corpo.get("timesteps", 200_000))
                seed = int(corpo.get("seed", 0))
                n_envs = int(corpo.get("n_envs", 8))
            except (TypeError, ValueError):
                raise ErroAPI(400, "timesteps/seed/n_envs têm de ser inteiros") from None
            if timesteps <= 0 or n_envs <= 0:
                raise ErroAPI(400, "timesteps e n_envs têm de ser > 0")

            if corpo.get("out_dir"):
                runs_dir = Path(str(corpo["out_dir"])).expanduser()
            else:
                runs_dir = self.out_dir / f"run_{time.strftime('%Y%m%d_%H%M%S')}_seed{seed}"
            runs_dir = runs_dir.resolve()
            if runs_dir == _RAIZ:
                raise ErroAPI(400, "out_dir não pode ser a raiz do laboratório")
            runs_dir.mkdir(parents=True, exist_ok=True)

            self.out_run = runs_dir
            cmd = self._cmd_treino(timesteps, seed, n_envs, runs_dir, str(corpo.get("extra", "")).strip())
            log = open(runs_dir / "train_stdout.log", "w", encoding="utf-8")   # noqa: SIM115  (vive com o filho)
            try:
                proc = subprocess.Popen(cmd, cwd=str(_RAIZ), env=self._env(), stdout=log,
                                        stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as erro:
                log.close()
                self.out_run = None
                raise ErroAPI(500, f"não consegui lançar o train.py: {erro}") from erro
            self.proc, self.proc_log = proc, log
            self.cmd = cmd
            self.iniciado = time.monotonic()
            self.iniciado_wall = time.time()
            self.saida, self.duracao = None, None
            threading.Thread(target=self._vigiar, args=(proc, log), daemon=True).start()
            return {"pid": proc.pid, "cmd": cmd, "out_dir": str(runs_dir), "flags": self.flags,
                    "flags_omitidas": self.flags_omitidas}

    def parar_treino(self) -> dict:
        """SIGTERM (depois SIGKILL) ao grupo do treino — os checkpoints em disco ficam."""
        with self.trava:
            proc = self.proc
            if proc is None or proc.poll() is not None:
                return {"ok": False, "erro": "não há treino a correr"}
            pid = proc.pid
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                proc.terminate()
            threading.Thread(target=self._forcar_saida, args=(proc,), daemon=True).start()
            return {"ok": True, "pid": pid, "sinal": "SIGTERM", "nota": "SIGKILL após 8 s se não sair"}

    def _forcar_saida(self, proc: subprocess.Popen, espera: float = 8.0) -> None:
        try:
            proc.wait(timeout=espera)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()

    def _vigiar(self, proc: subprocess.Popen, log) -> None:
        """Fecha o ficheiro de stdout e guarda o exit code quando o filho morre (natural ou morto)."""
        proc.wait()
        with self.trava:
            if self.proc is proc:
                self.saida = proc.returncode
                self.duracao = (time.monotonic() - self.iniciado) if self.iniciado else None
        try:
            log.close()
        except OSError:
            pass

    def iniciar_probe(self, corpo: dict) -> dict:
        """Lança o `net_probe.py` (a rede a correr sem viewer) para o modelo pedido."""
        with self.trava:
            if self.probe is not None and self.probe.poll() is None:
                raise ErroAPI(409, f"a sonda já está a correr (pid {self.probe.pid}); para-a primeiro")
            if not PROBE_PY.is_file():
                raise ErroAPI(500, f"{PROBE_PY.name} não existe")
            bruto = str(corpo.get("model", "")).strip()
            if not bruto:
                raise ErroAPI(400, "falta o campo `model` (caminho do .zip da política)")
            modelo = Path(bruto).expanduser()
            if not modelo.is_absolute():
                modelo = (_RAIZ / modelo).resolve()
            if not modelo.is_file():
                raise ErroAPI(400, f"modelo não encontrado: {modelo}")
            try:
                intervalo = float(corpo.get("interval", 0.2))
            except (TypeError, ValueError):
                raise ErroAPI(400, "`interval` tem de ser um número (segundos)") from None
            if not math.isfinite(intervalo):
                raise ErroAPI(400, "`interval` tem de ser um número finito (segundos)")
            alvo_z: float | None = None
            if corpo.get("alvo_z") is not None:
                try:                                              # "abc"/""/null → 400 limpo, nunca 500
                    alvo_z = float(corpo["alvo_z"])
                except (TypeError, ValueError):
                    raise ErroAPI(400, "`alvo_z` tem de ser um número (metros)") from None
                if not math.isfinite(alvo_z):
                    raise ErroAPI(400, "`alvo_z` tem de ser um número finito (metros)")
                if not ALVO_Z_MIN <= alvo_z <= ALVO_Z_MAX:        # a mesma faixa que o HoverEnv aceita
                    raise ErroAPI(400, f"`alvo_z` fora da faixa [{ALVO_Z_MIN:g}, {ALVO_Z_MAX:g}] m "
                                       f"(recebido {alvo_z:g}) — é a faixa válida do alvo do HoverEnv")
            try:                                                  # ritmo da sonda: 1 = tempo real (default da UI)
                fator_tempo = float(corpo.get("fator_tempo", 1.0))
            except (TypeError, ValueError):
                raise ErroAPI(400, "`fator_tempo` tem de ser um número (1 = tempo real, 0 = sem travão)") from None
            if not math.isfinite(fator_tempo) or fator_tempo < 0.0:
                raise ErroAPI(400, "`fator_tempo` tem de ser finito e ≥ 0 (0 = o mais rápido possível)")
            self.net_jsonl.parent.mkdir(parents=True, exist_ok=True)
            self.controlo_vento.parent.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(PROBE_PY), "--model", str(modelo), "--out", str(self.net_jsonl),
                   "--interval", str(max(0.02, intervalo)), "--controlo", str(self.controlo_vento),
                   "--fator-tempo", f"{fator_tempo:g}"]
            if alvo_z is not None:
                cmd += ["--alvo-z", f"{alvo_z:g}"]
            log = open(self.out_dir / "probe_stdout.log", "w", encoding="utf-8")   # noqa: SIM115
            try:
                proc = subprocess.Popen(cmd, cwd=str(_RAIZ), env=self._env(), stdout=log,
                                        stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as erro:
                log.close()
                raise ErroAPI(500, f"não consegui lançar o net_probe.py: {erro}") from erro
            self.probe, self.probe_log = proc, log
            self.probe_cmd = cmd
            self.probe_modelo = str(modelo)
            self.probe_iniciado = time.monotonic()
            self.probe_saida = None
            threading.Thread(target=self._vigiar_probe, args=(proc, log), daemon=True).start()
            return {"pid": proc.pid, "cmd": cmd, "model": str(modelo), "out": str(self.net_jsonl),
                    "controlo": str(self.controlo_vento), "fator_tempo": fator_tempo}

    def parar_probe(self) -> dict:
        with self.trava:
            proc = self.probe
            if proc is None or proc.poll() is not None:
                return {"ok": False, "erro": "a sonda não está a correr"}
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                proc.terminate()
            threading.Thread(target=self._forcar_saida, args=(proc, 4.0), daemon=True).start()
            return {"ok": True, "pid": proc.pid, "sinal": "SIGTERM"}

    def _vigiar_probe(self, proc: subprocess.Popen, log) -> None:
        proc.wait()
        with self.trava:
            if self.probe is proc:
                self.probe_saida = proc.returncode
        try:
            log.close()
        except OSError:
            pass

    def encerrar(self) -> None:
        """Mata os filhos ao sair (SIGTERM; SIGKILL após 3 s) — nada fica órfão."""
        for proc in (self.probe, self.proc):
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    proc.kill()
        for proc in (self.probe, self.proc):
            if proc is not None:
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()

    # ------------------------------------------------------------------ runs em disco
    def _info_run(self, pasta: Path, nome: str | None = None) -> dict:
        linhas = _ler_jsonl(pasta / "train_log.jsonl")
        normalizadas = [_normaliza(o) for o, _ in linhas if o is not None]
        ultimo = next((n for n in reversed(normalizadas) if n["mean_ret"] is not None), None)
        ultimo_z = next((n for n in reversed(normalizadas) if n["mean_z"] is not None), None)
        modelos = sorted(str(p) for p in pasta.glob("*.zip"))
        if (pasta / "best_model.zip").exists():                     # o preferido fica à frente na dropdown
            modelos.sort(key=lambda s: (not s.endswith("best_model.zip"), s))
        mtime = max([pasta.stat().st_mtime] + [p.stat().st_mtime for p in pasta.glob("*") if p.is_file()],
                    default=0.0)
        melhor = max((n["mean_ret"] for n in normalizadas if n["mean_ret"] is not None), default=None)
        return {"nome": nome or pasta.name, "dir": str(pasta), "mtime": mtime,
                "n_linhas": len(linhas), "mean_ret": ultimo["mean_ret"] if ultimo else None,
                "t": ultimo["t"] if ultimo else None,
                "mean_z": ultimo_z["mean_z"] if ultimo_z else None,
                "melhor_mean_ret": melhor, "modelos": modelos,
                "tem_evals": (pasta / "evaluations.npz").is_file(),
                "tem_stdout": (pasta / "train_stdout.log").is_file(),
                "ativo": self.out_run is not None and pasta == self.out_run}

    def candidatos_runs(self) -> list[tuple[Path, str | None]]:
        """[(pasta, nome|None)] dos runs em disco — aceita os DOIS layouts e apontar à pasta `runs`.

        O `train.py` escreve em `<--out>/runs/seed<seed>` (dois níveis: é o layout do default
        `OUT_PADRAO = out/`), a UI/`/api/start` escreve em `<--out>/<run>` (um nível). Varrem-se as
        subpastas de `--out` e as de `<--out>/runs` (ou só estas, se o `--out` já FOR a pasta `runs`),
        mais o próprio `--out` (nome `(out)`, quando tem `train_log.jsonl`), sem duplicar pastas:
        `--out <out>` e `--out <out>/runs` dão exatamente os mesmos runs.
        """
        base = self.out_dir
        if not base.is_dir():
            return []
        raizes = [base] if base.name == "runs" else [base, base / "runs"]
        vistas: set[Path] = set()
        saida: list[tuple[Path, str | None]] = []
        for raiz in raizes:
            if not raiz.is_dir():
                continue
            for pasta in sorted(raiz.iterdir()):
                chave = pasta.resolve()
                if not pasta.is_dir() or chave in vistas:
                    continue
                if not any((pasta / m).exists() for m in MARCA):
                    continue
                vistas.add(chave)
                saida.append((pasta, None))
        if (base / "train_log.jsonl").exists() and base.resolve() not in vistas:
            saida.append((base, "(out)"))                          # treino a escrever direto em out/
        return saida

    def runs(self) -> list[dict]:
        saida = [self._info_run(pasta, nome=nome) for pasta, nome in self.candidatos_runs()]
        saida.sort(key=lambda r: r["mtime"], reverse=True)
        return saida

    def run_ativo(self) -> Path | None:
        """Run do treino em curso; se o `train.py` ignorou o out-dir, adota o run mexido desde o arranque."""
        with self.trava:
            if self.out_run is not None and (self.out_run / "train_log.jsonl").exists():
                return self.out_run
            if self.iniciado_wall is not None:
                for r in self.runs():
                    if r["mtime"] >= self.iniciado_wall - 2.0 and r["n_linhas"] > 0:
                        return Path(r["dir"])
            return self.out_run

    def resolver_run(self, nome: str) -> Path:
        """Nome de run → pasta descoberta em `--out` (recusa caminhos que saiam de lá)."""
        base = self.out_dir.resolve()
        if not nome:
            ativo = self.run_ativo()
            if ativo is None:
                raise ErroAPI(404, "não há run ativo (nem nenhum run no out-dir)")
            return ativo
        if nome == "(out)":
            return base
        for pasta, rotulo in self.candidatos_runs():               # `<out>/<run>` e `<out>/runs/<run>`
            if (rotulo or pasta.name) == nome:
                return pasta.resolve()
        pasta = (base / nome).resolve()
        if base != pasta and base not in pasta.parents:
            raise ErroAPI(400, "nome de run inválido")
        if not pasta.is_dir():
            raise ErroAPI(404, f"run não encontrado: {nome}")
        return pasta

    def serie(self, pasta: Path, max_pontos: int = 1500) -> dict:
        linhas = [_normaliza(o) for o, _ in _ler_jsonl(pasta / "train_log.jsonl") if o is not None]
        t = [n["t"] for n in linhas]
        ret = [n["mean_ret"] for n in linhas]
        z = [n["mean_z"] for n in linhas]
        return {"nome": pasta.name if pasta != self.out_dir else "(out)", "dir": str(pasta),
                "n_linhas": len(linhas), "t": _amostrar(t, max_pontos),
                "mean_ret": _amostrar(ret, max_pontos), "mean_z": _amostrar(z, max_pontos),
                "ultimo": next((n for n in reversed(linhas) if n["mean_ret"] is not None), None)}

    # ------------------------------------------------------------------ respostas da API
    def estado_treino(self) -> dict:
        with self.trava:
            proc, ativo = self.proc, self.run_ativo()
            vivo = proc is not None and proc.poll() is None
            return {"running": bool(vivo), "pid": proc.pid if proc is not None else None,
                    "cmd": self.cmd, "out_dir": str(ativo) if ativo else None,
                    "run": ativo.name if ativo else None,
                    "iniciado_ha": (time.monotonic() - self.iniciado) if (vivo and self.iniciado) else None,
                    "duracao": self.duracao, "returncode": self.saida,
                    "stdout_log": str(ativo / "train_stdout.log") if ativo else None,
                    "flags": self.flags, "flags_omitidas": self.flags_omitidas,
                    "train_py": self.train_py.is_file(), "train_py_caminho": str(self.train_py)}

    def run_para_painel(self, nome: str | None = None) -> Path | None:
        """Run cujo log/stdout o painel mostra: treino a correr > run pedido (`?run=`) > o mais recente."""
        with self.trava:
            if self.out_run is not None and self.proc is not None and self.proc.poll() is None:
                return self.out_run                      # treino a correr agora: o painel segue-o
        if nome:
            try:
                return self.resolver_run(nome)
            except ErroAPI:
                return None
        ativo = self.run_ativo()
        if ativo is not None and any((ativo / m).exists() for m in ("train_log.jsonl", "train_stdout.log")):
            return ativo
        runs = self.runs()
        return Path(runs[0]["dir"]) if runs else ativo

    def estado(self, run: str | None = None, limite_log: int = 200, limite_stdout: int = 120) -> dict:
        painel = self.run_para_painel(run)
        log = []
        if painel is not None:
            for objeto, cru in _ler_jsonl(painel / "train_log.jsonl", limite=limite_log):
                log.append(_normaliza(objeto) if objeto is not None else {"t": None, "mean_ret": None,
                                                                          "mean_z": None, "cru": None,
                                                                          "cru_texto": cru})
        return {"servidor": {"raiz": str(_RAIZ), "out_dir": str(self.out_dir), "net": str(self.net_jsonl),
                             "controlo_vento": str(self.controlo_vento),
                             "train_py": self.train_py.is_file(), "probe_py": PROBE_PY.is_file(),
                             "hora": time.time()},
                "train": self.estado_treino(), "log": log,
                "run_painel": painel.name if painel is not None else None,
                "stdout": _cauda(painel / "train_stdout.log", limite_stdout) if painel else [],
                "runs": self.runs(), "probe": self.estado_probe(), "vento": self.estado_vento()}

    def estado_probe(self) -> dict:
        with self.trava:
            proc = self.probe
            vivo = proc is not None and proc.poll() is None
            self._contagem = _contar_linhas(self.net_jsonl, self._contagem)
            return {"running": bool(vivo), "pid": proc.pid if proc is not None else None,
                    "modelo": self.probe_modelo, "cmd": self.probe_cmd,
                    "out": str(self.net_jsonl), "returncode": self.probe_saida,
                    "iniciado_ha": (time.monotonic() - self.probe_iniciado) if (vivo and self.probe_iniciado)
                    else None,
                    "n_linhas": self._contagem[1], **self.estado_episodio()}

    def estado_rede(self) -> dict:
        linha = _ultima_json(self.net_jsonl)
        mtime = self.net_jsonl.stat().st_mtime if self.net_jsonl.is_file() else None
        return {"disponivel": linha is not None, "linha": linha, "caminho": str(self.net_jsonl),
                "mtime": mtime, "idade": (time.time() - mtime) if mtime else None, "probe": self.estado_probe()}

    # ------------------------------------------------------------------ vento ao vivo
    def estado_vento(self) -> dict:
        """Estado do controlo de vento (o ficheiro que o `net_probe.py` vigia) + caminho/mtime/idade.

        Nunca levanta: um ficheiro ausente é o estado NEUTRO (0 m/s, inativo — ninguém pediu vento ainda) e um
        ficheiro ilegível devolve o motivo em `erro` (a UI mostra-o; o `net_probe.py` mantém o vento em vigor).
        Inclui os COMANDOS de episódio: `reiniciar` (contador; muda → a sonda reinicia o episódio) e `loop`
        (true = auto-reset no fim). Ausentes no ficheiro valem 0 e false — é o modo SEM LOOP por omissão.
        """
        dados = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False, "t": None,
                 "reiniciar": 0, "loop": False}
        erro = None
        mtime = None
        try:                                     # o ficheiro é trocado por `os.replace`: lê-se sob try (corrida)
            mtime = self.controlo_vento.stat().st_mtime
            bruto = json.loads(self.controlo_vento.read_text(encoding="utf-8"))
            if not isinstance(bruto, dict):
                erro = "o ficheiro não é um objeto JSON"
            else:
                for campo in ("vel", "azimute", "elevacao", "t"):
                    v = bruto.get(campo)
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
                        dados[campo] = float(v)
                dados["ativo"] = bool(bruto.get("ativo", False))
                n = bruto.get("reiniciar")
                if isinstance(n, int) and not isinstance(n, bool) and n >= 0:
                    dados["reiniciar"] = int(n)
                if isinstance(bruto.get("loop"), bool):
                    dados["loop"] = bool(bruto["loop"])
        except FileNotFoundError:
            pass                                 # ainda não houve vento: estado NEUTRO (0 m/s, inativo)
        except (OSError, json.JSONDecodeError) as falha:
            erro = f"{type(falha).__name__}: {falha}"
        return {"existe": mtime is not None, "erro": erro, "caminho": str(self.controlo_vento), "mtime": mtime,
                "idade": (time.time() - mtime) if mtime else None, **dados}

    def _escrever_controlo(self, **alteracoes) -> dict:
        """Lê-modifica-escreve o ficheiro de controlo de forma ATÓMICA (tmp no mesmo diretório + `os.replace`).

        O `net_probe.py` compara `(mtime_ns, tamanho)` a cada passo de decisão: o rename garante que ele só vê
        o ficheiro já completo (nunca um JSON a meio). Parte SEMPRE do estado atual, para um comando de
        episódio (`reiniciar`/`loop`) não apagar o vento em vigor nem o vento apagar o contador.
        """
        with self.trava:                         # RLock: quem chama pode já ter o lock (aplicar_vento)
            atual = self.estado_vento()
            registro = {"vel": float(atual.get("vel") or 0.0), "azimute": float(atual.get("azimute") or 0.0),
                        "elevacao": float(atual.get("elevacao") or 0.0), "ativo": bool(atual.get("ativo")),
                        "reiniciar": int(atual.get("reiniciar") or 0), "loop": bool(atual.get("loop")),
                        **alteracoes, "t": time.time()}
            self.controlo_vento.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.controlo_vento.with_name(
                f".{self.controlo_vento.name}.tmp.{os.getpid()}.{threading.get_ident()}")
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(registro, fh, ensure_ascii=False)
                    fh.write("\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, self.controlo_vento)
            except OSError as erro:
                tmp.unlink(missing_ok=True)
                raise ErroAPI(500, f"não consegui escrever o controlo de vento em "
                                   f"{self.controlo_vento}: {erro}") from erro
            estado = self.estado_vento()
            estado["registro"] = registro
            return estado

    def aplicar_vento(self, corpo: dict) -> dict:
        """Grava o vento pedido pelo painel (valida as faixas; 400 se inválido) sem mexer nos comandos."""
        return self._escrever_controlo(**_vento_validado(corpo))

    def reiniciar_episodio(self) -> dict:
        """Botão «↻ REINICIAR»: incrementa o contador `reiniciar` (a sonda vê a mudança e faz `env.reset`).

        O incremento é lido-modificado-escrito sob o lock: dois cliques seguidos dão 1 e 2 (nunca o mesmo
        valor, que a sonda não distinguiria).
        """
        with self.trava:
            contador = int(self.estado_vento().get("reiniciar") or 0) + 1
            estado = self._escrever_controlo(reiniciar=contador)
        estado["mensagem"] = f"reinício pedido (contador {contador})"
        return estado

    def definir_loop(self, ativo: bool) -> dict:
        """Toggle «LOOP»: liga/desliga o auto-reset no fim do episódio (campo `loop` do ficheiro)."""
        estado = self._escrever_controlo(loop=bool(ativo))
        estado["mensagem"] = ("LOOP ligado: a sonda reinicia sozinha no fim do episódio" if ativo
                              else "LOOP desligado: a sonda para no fim do episódio e espera pelo REINICIAR")
        return estado

    def estado_episodio(self) -> dict:
        """O que a sonda está a fazer com o EPISÓDIO, lido da última linha do JSONL (sem estado extra).

        A convenção é a da linha de evento do `net_probe.py`: se a última linha tem `evento == "fim_episodio"`,
        a sonda está EM ESPERA (sem loop) e a UI pede o «↻ REINICIAR».
        """
        linha = _ultima_json(self.net_jsonl)
        if not isinstance(linha, dict) or linha.get("evento") != "fim_episodio":
            return {"espera": False, "motivo": None, "episodio": None, "fim_em": None}
        return {"espera": True, "motivo": linha.get("motivo"), "episodio": linha.get("episodio"),
                "fim_em": linha.get("t")}

    def evals(self, pasta: Path) -> dict:
        arquivo = pasta / "evaluations.npz"
        if not arquivo.is_file():
            raise ErroAPI(404, f"sem evaluations.npz no run {pasta.name}")
        # numpy entra só aqui (import lazy): é o único ponto que lê arrays; não é dependência nova do projeto
        try:
            import numpy as np
        except ImportError as erro:                               # pragma: no cover
            raise ErroAPI(501, f"numpy indisponível para ler o .npz: {erro}") from erro

        def _lista(a):
            v = np.asarray(a, dtype=float)
            if v.ndim > 1:                                        # results (n_evals, n_envs) → média por eval
                v = v.mean(axis=tuple(range(1, v.ndim)))
            return [None if not math.isfinite(float(x)) else round(float(x), 6) for x in v.ravel()]

        with np.load(arquivo, allow_pickle=False) as dados:
            arrays = {k: _lista(dados[k]) for k in dados.files}
        return {"nome": pasta.name, "dir": str(pasta), "chaves": list(arrays), "arrays": arrays}


# ------------------------------------------------------------------------------------------- HTTP
class Manipulador(BaseHTTPRequestHandler):
    """Handlers curtos: leem ficheiros/estado e devolvem JSON; nunca correm treino no servidor."""

    protocol_version = "HTTP/1.1"
    server_version = "hover-dashboard/1.0"
    timeout = 30                       # cliente que estola a meio do corpo não prende a thread do servidor

    # ------------------------------------------------------------------ helpers de resposta
    def _corpo(self, dados: bytes, tipo: str, codigo: int = 200) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        if self.close_connection:      # corpo não drenado (413 enorme) ou pedido pediu para fechar: avisar
            self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(dados)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, objeto, codigo: int = 200) -> None:
        texto = json.dumps(objeto, ensure_ascii=False, allow_nan=False, default=str)
        self._corpo(texto.encode("utf-8"), "application/json; charset=utf-8", codigo)

    def _html(self, texto: str) -> None:
        self._corpo(texto.encode("utf-8"), "text/html; charset=utf-8")

    def _erro(self, codigo: int, mensagem: str) -> None:
        self._json({"ok": False, "erro": mensagem}, codigo)

    @property
    def estado(self) -> Estado:
        return self.server.estado                          # type: ignore[attr-defined]

    def _query(self) -> dict:
        return parse_qs(urlparse(self.path).query)

    def _comprimento_corpo(self) -> int:
        """`Content-Length` declarado no pedido (0 se ausente/ilegível) — não lê nada do socket."""
        try:
            return max(0, int(self.headers.get("Content-Length", "0") or 0))
        except ValueError:
            return 0

    def _descartar_corpo(self, n: int) -> None:
        """Lê e descarta `n` bytes do corpo do pedido, para o pedido SEGUINTE ficar alinhado na ligação.

        Necessário sempre que se responde sem consumir o corpo (413, ou rotas que o ignoram): em keep-alive os
        bytes sobrantes seriam interpretados como uma nova linha de pedido. Acima de `LIMITE_DESCARTE` não se
        drena — seria pior que fechar — e marca-se a ligação para FECHAR (a resposta leva `Connection: close`).
        """
        if n > LIMITE_DESCARTE:
            self.close_connection = True
            return
        restante = n
        while restante > 0:
            pedaco = self.rfile.read(min(65536, restante))
            if not pedaco:                              # cliente fechou (ou mentiu no Content-Length)
                self.close_connection = True
                return
            restante -= len(pedaco)

    def _corpo_json(self) -> dict:
        n = self._comprimento_corpo()
        if n <= 0:
            return {}
        if n > LIMITE_CORPO:
            # 413 com o corpo AINDA no socket desalinharia a ligação: em HTTP/1.1 keep-alive os bytes que
            # sobram são lidos como o pedido SEGUINTE (o JSON gigante vira "414 Request-URI Too Long").
            # Descarta-se o corpo primeiro e só depois se responde 413.
            self._descartar_corpo(n)
            raise ErroAPI(413, "corpo do pedido demasiado grande")
        bruto = self.rfile.read(n)
        try:
            dados = json.loads(bruto.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as erro:
            raise ErroAPI(400, f"JSON inválido no corpo: {erro}") from erro
        if not isinstance(dados, dict):
            raise ErroAPI(400, "o corpo tem de ser um objeto JSON")
        return dados

    def log_message(self, formato: str, *args) -> None:
        if getattr(self.server, "verboso", False):
            sys.stderr.write(f"[dashboard] {self.address_string()} {formato % args}\n")

    # ------------------------------------------------------------------ rotas
    def do_GET(self) -> None:                              # (nome exigido pelo http.server)
        rota = urlparse(self.path)
        try:
            if rota.path in ("/", "/index.html"):
                return self._html(PAGINA)
            if rota.path == "/api/state":
                return self._json(self.estado.estado(self._query().get("run", [None])[0]))
            if rota.path == "/api/net":
                return self._json(self.estado.estado_rede())
            if rota.path == "/api/vento":
                return self._json({"ok": True, "probe": self.estado.estado_probe(),
                                   **self.estado.estado_vento()})
            if rota.path == "/api/run":
                q = self._query()
                try:
                    max_pontos = min(20_000, max(10, int(q.get("max", ["1500"])[0])))
                except ValueError:
                    max_pontos = 1500
                pasta = self.estado.resolver_run(q.get("run", [""])[0])
                return self._json(self.estado.serie(pasta, max_pontos))
            if rota.path == "/api/evals":
                pasta = self.estado.resolver_run(self._query().get("run", [""])[0])
                return self._json(self.estado.evals(pasta))
            if rota.path == "/api/health":
                return self._json({"ok": True, "hora": time.time()})
            if rota.path == "/favicon.ico":
                return self._corpo(b"", "image/x-icon", 204)
            return self._erro(404, f"rota desconhecida: {rota.path}")
        except ErroAPI as erro:
            return self._erro(erro.codigo, erro.mensagem)
        except Exception as erro:                          # noqa: BLE001  (nunca derrubar o servidor)
            return self._erro(500, f"erro interno: {type(erro).__name__}: {erro}")

    def do_POST(self) -> None:                             # (nome exigido pelo http.server)
        rota = urlparse(self.path)
        try:
            if rota.path == "/api/start":
                return self._json({"ok": True, **self.estado.iniciar_treino(self._corpo_json())})
            if rota.path == "/api/stop":
                self._descartar_corpo(self._comprimento_corpo())   # rota sem corpo: não deixar bytes no socket
                return self._json(self.estado.parar_treino())
            if rota.path == "/api/net/start":
                return self._json({"ok": True, **self.estado.iniciar_probe(self._corpo_json())})
            if rota.path == "/api/net/stop":
                self._descartar_corpo(self._comprimento_corpo())   # idem
                return self._json(self.estado.parar_probe())
            if rota.path == "/api/vento":
                return self._json({"ok": True, "probe": self.estado.estado_probe(),
                                   **self.estado.aplicar_vento(self._corpo_json())})
            if rota.path == "/api/reiniciar":
                self._descartar_corpo(self._comprimento_corpo())   # rota sem corpo: não deixar bytes no socket
                return self._json({"ok": True, "probe": self.estado.estado_probe(),
                                   **self.estado.reiniciar_episodio()})
            if rota.path == "/api/loop":
                return self._json({"ok": True, **self.estado.definir_loop(_loop_validado(self._corpo_json()))})
            return self._erro(404, f"rota desconhecida: {rota.path}")
        except ErroAPI as erro:
            return self._erro(erro.codigo, erro.mensagem)
        except Exception as erro:                          # noqa: BLE001
            return self._erro(500, f"erro interno: {type(erro).__name__}: {erro}")


class Servidor(ThreadingHTTPServer):
    """ThreadingHTTPServer com o estado partilhado e threads daemon (sai limpo com Ctrl+C)."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, endereco, estado: Estado, verboso: bool = False) -> None:
        self.estado = estado
        self.verboso = verboso
        super().__init__(endereco, Manipulador)


# ------------------------------------------------------------------------------------------- página
PAGINA = r"""<!doctype html>
<html lang="pt-PT">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Drone Hover RL — treinar e ver a rede</title>
<style>
  :root{
    --fundo:#080c14; --painel:#0e1522; --painel2:#131c2c; --borda:#1e2a3d; --texto:#dbe7f5;
    --suave:#8195b0; --azul:#38bdf8; --verde:#34d399; --ambar:#fbbf24; --vermelho:#f87171;
    --mono:ui-monospace,SFMono-Regular,"JetBrains Mono","Fira Code",Menlo,Consolas,monospace;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  }
  *{box-sizing:border-box}
  body{margin:0;background:radial-gradient(1200px 700px at 15% -10%,#132038 0%,var(--fundo) 55%) fixed;
       color:var(--texto);font-family:var(--sans);font-size:14px;line-height:1.45}
  header{display:flex;flex-wrap:wrap;gap:14px;align-items:center;justify-content:space-between;
         padding:16px 22px;border-bottom:1px solid var(--borda);background:#0a111ccc;backdrop-filter:blur(6px);
         position:sticky;top:0;z-index:9}
  h1{font-size:17px;margin:0;letter-spacing:.2px}
  h1 small{color:var(--suave);font-weight:400;font-size:12px;margin-left:8px}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--suave);margin:0 0 10px}
  main{padding:18px 22px 60px;display:flex;flex-direction:column;gap:18px;max-width:1500px;margin:0 auto}
  .grelha{display:grid;grid-template-columns:minmax(320px,1fr) minmax(320px,1.6fr);gap:18px;align-items:start}
  @media (max-width:1000px){.grelha{grid-template-columns:1fr}}
  section{background:linear-gradient(180deg,var(--painel) 0%,#0c131f 100%);border:1px solid var(--borda);
          border-radius:12px;padding:16px}
  .linha{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
  label.campo{display:flex;flex-direction:column;gap:4px;font-size:11px;color:var(--suave);
              text-transform:uppercase;letter-spacing:.08em}
  input,select{background:#0a1220;border:1px solid var(--borda);color:var(--texto);border-radius:8px;
               padding:7px 9px;font-family:var(--mono);font-size:13px;min-width:92px}
  input:focus,select:focus{outline:1px solid var(--azul);border-color:var(--azul)}
  input[type=range]{padding:0;border:0;background:transparent;min-width:110px;height:22px;cursor:pointer;
                    accent-color:var(--azul)}
  .par{display:flex;align-items:center;gap:9px;flex-wrap:nowrap}
  .par input[type=number]{flex:0 0 84px}
  .par input[type=range]{flex:1 1 auto}
  .unid{flex:0 0 42px;color:var(--suave);font-family:var(--mono);font-size:11px}
  .item.sem-barra .nome{flex:1 1 auto;color:var(--texto)}
  .item.sem-barra .val{flex:0 0 auto;min-width:76px;text-align:right}
  button{border-radius:9px;border:1px solid var(--borda);background:#16233a;color:var(--texto);
         padding:9px 14px;font-size:13px;font-weight:600;cursor:pointer;transition:.15s}
  button:hover:not(:disabled){background:#1d2f4d;border-color:#2b3f5e}
  button:disabled{opacity:.45;cursor:not-allowed}
  button.primario{background:linear-gradient(180deg,#1d6fa5,#14507a);border-color:#2b7fb8}
  button.primario:hover:not(:disabled){background:linear-gradient(180deg,#2482bf,#175d8d)}
  button.perigo{background:linear-gradient(180deg,#8f2f36,#6d2129);border-color:#a83b43}
  button.rede{background:linear-gradient(180deg,#1c6d55,#14503f);border-color:#2a8a6c}
  .pilula{display:inline-flex;align-items:center;gap:7px;padding:4px 11px;border-radius:999px;
          font-size:12px;font-family:var(--mono);border:1px solid var(--borda);background:#0d1728}
  .pilula b{font-weight:600}
  .ponto{width:8px;height:8px;border-radius:50%;background:var(--suave);box-shadow:0 0 8px currentColor}
  .on .ponto{background:var(--verde);color:var(--verde);animation:pulsa 1.4s infinite}
  .off .ponto{background:#475569;color:transparent}
  .erro .ponto{background:var(--vermelho);color:var(--vermelho)}
  @keyframes pulsa{50%{opacity:.35}}
  .meta{font-family:var(--mono);font-size:11.5px;color:var(--suave);word-break:break-all;margin-top:10px}
  .meta b{color:var(--texto);font-weight:500}
  svg{display:block;width:100%;height:auto;overflow:visible}
  .legenda{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px;font-size:12px;font-family:var(--mono)}
  .legenda span{display:inline-flex;align-items:center;gap:6px;color:var(--suave)}
  .amostra{width:16px;height:3px;border-radius:2px;display:inline-block}
  pre#log{margin:0;background:#070b12;border:1px solid var(--borda);border-radius:9px;padding:11px;
          font-family:var(--mono);font-size:11.5px;max-height:260px;overflow:auto;white-space:pre-wrap;
          color:#a9c0da}
  table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:11.5px}
  th,td{text-align:left;padding:5px 7px;border-bottom:1px solid #16202f}
  th{color:var(--suave);font-weight:500;text-transform:uppercase;letter-spacing:.06em;font-size:10.5px}
  tr.sel td{background:#122036}
  td.num{text-align:right}
  .lista{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:4px 12px;font-family:var(--mono);font-size:11.5px}
  .item{display:flex;align-items:center;gap:7px}
  .item .nome{flex:0 0 62px;color:var(--suave)}
  .item .barra{flex:1;height:6px;border-radius:3px;background:#16202f;overflow:hidden}
  .item .barra i{display:block;height:100%;width:0;background:linear-gradient(90deg,#1d4ed8,#38bdf8)}
  .item .val{flex:0 0 58px;text-align:right;color:var(--texto)}
  .aviso{margin-top:10px;font-size:12px;font-family:var(--mono);color:var(--ambar);min-height:17px}
  .aviso.mau{color:var(--vermelho)}
  .aviso.bom{color:var(--verde)}
  .nota{color:var(--suave);font-size:11.5px;margin-top:8px}
  details summary{cursor:pointer;color:var(--suave);font-size:12px;font-family:var(--mono)}
  /* ---------------------------------------------------------------- melhorias UX (auditoria) */
  button{min-height:34px}                       /* alvo mínimo (Fitts): nada abaixo disto */
  button.primario,button.rede,button.perigo,button.reiniciar{min-height:40px;padding:10px 16px}
  .nav{display:flex;gap:10px;font-family:var(--mono);font-size:11.5px}
  .nav a{color:var(--suave);text-decoration:none;border-bottom:1px dotted #2b3f5e;padding:2px 0;min-height:24px}
  .nav a:hover{color:var(--azul)}
  #guia{display:flex;flex-wrap:wrap;gap:10px;align-items:center;border-radius:10px;padding:11px 14px;
        border:1px solid var(--borda);background:#0d1728;font-size:13px}
  #guia .selo{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.1em;
              padding:3px 9px;border-radius:999px;border:1px solid var(--borda);color:var(--suave)}
  #guia.espera{border-color:#b45309;background:#1b1408}
  #guia.espera .selo{border-color:#b45309;color:var(--ambar)}
  #guia.vivo{border-color:#1d6fa5}
  #guia.vivo .selo{border-color:#2b7fb8;color:var(--azul)}
  #guia b{color:#fff}
  .grupo-episodio{display:flex;flex-wrap:wrap;gap:10px;align-items:center;border:1px dashed var(--borda);
                  border-radius:10px;padding:10px 12px;background:#0c1421}
  .grupo-episodio .rotulo{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.1em;
                          color:var(--suave)}
  button.reiniciar{background:linear-gradient(180deg,#a16207,#7c4a06);border-color:#c2830f;color:#fff}
  button.reiniciar:hover:not(:disabled){background:linear-gradient(180deg,#b87208,#8f5607)}
  .interruptor{display:inline-flex;align-items:center;gap:8px;min-height:34px;padding:4px 10px;border-radius:9px;
               border:1px solid var(--borda);background:#16233a;cursor:pointer;font-size:12.5px;font-weight:600}
  .interruptor input{min-width:auto;width:16px;height:16px;accent-color:var(--ambar);cursor:pointer}
  .selo-estado{font-family:var(--mono);font-size:11.5px;padding:4px 10px;border-radius:999px;border:1px solid var(--borda);
               background:#0a1220;color:var(--suave)}
  .selo-estado.espera{color:var(--ambar);border-color:#b45309}
  .selo-estado.vivo{color:var(--verde);border-color:#2a8a6c}
  #toasts{position:fixed;right:16px;bottom:16px;z-index:40;display:flex;flex-direction:column;gap:8px;
          max-width:min(460px,90vw)}
  .toast{border:1px solid var(--borda);border-left:3px solid var(--azul);background:#0e1522ee;border-radius:9px;
         padding:10px 12px;font-size:12.5px;font-family:var(--mono);box-shadow:0 8px 22px #0008;
         display:flex;gap:10px;align-items:center;animation:entra .18s ease-out}
  .toast.bom{border-left-color:var(--verde)} .toast.mau{border-left-color:var(--vermelho)}
  .toast button{min-height:24px;padding:2px 9px;font-size:11.5px}
  @keyframes entra{from{opacity:0;transform:translateY(6px)}}
  details.bloco{border:1px solid var(--borda);border-radius:9px;padding:8px 11px;background:#0b1320;margin-top:10px}
  details.bloco[open]{background:#0d1728}
  details.bloco summary{font-size:11.5px}
  details.bloco summary:hover{color:var(--azul)}
  .avancado{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:10px}
  section.destaque{border-color:#1d3a57;box-shadow:inset 3px 0 0 #1d6fa5}
</style>
</head>
<body>
<header>
  <h1>Drone Hover RL <small>experiments/09_drone_hover_rl — dashboard local (só stdlib, offline)</small></h1>
  <nav class="nav">
    <a href="#sec-rede">rede ao vivo</a><a href="#sec-vento">vento</a><a href="#sec-curvas">curvas</a>
    <a href="#sec-log">log</a>
  </nav>
  <div class="linha">
    <span class="pilula off" id="pilula-servidor"><i class="ponto"></i><b>servidor</b> <span id="srv">a ligar…</span></span>
    <span class="pilula off" id="pilula-treino"><i class="ponto"></i><b>treino</b> <span id="tre">parado</span></span>
    <span class="pilula off" id="pilula-rede"><i class="ponto"></i><b>rede</b> <span id="rde">parada</span></span>
    <span class="pilula off" id="pilula-vento"><i class="ponto"></i><b>vento</b> <span id="vento-topo">—</span></span>
  </div>
</header>
<main>
  <div class="aviso mau" id="erros-js" style="display:none"></div>
  <div id="guia">
    <span class="selo" id="guia-selo">a ligar</span>
    <span id="guia-texto">à espera do servidor…</span>
    <span class="linha" style="margin-left:auto">
      <button class="reiniciar" id="bt-guia-reiniciar" title="reinicia o episódio da sonda (contador `reiniciar`)">↻ REINICIAR</button>
      <label class="interruptor" title="LOOP ligado: a sonda reinicia sozinha no fim do episódio">
        <input type="checkbox" id="ck-guia-loop"> LOOP</label>
    </span>
  </div>
  <div class="grelha">
    <section id="sec-treino">
      <h2>1 · Treinar (subprocesso)</h2>
      <div class="linha">
        <label class="campo">timesteps<input id="ts" type="number" value="200000" step="1024" min="1024"></label>
        <button class="primario" id="bt-treinar">▶ Treinar</button>
        <button class="perigo" id="bt-parar" disabled>■ Parar treino</button>
      </div>
      <details class="bloco">
        <summary>avançado (seed, n_envs, out-dir)</summary>
        <div class="avancado">
          <label class="campo">seed<input id="seed" type="number" value="0" step="1"></label>
          <label class="campo">n_envs<input id="nenvs" type="number" value="8" step="1" min="1"></label>
          <label class="campo">out-dir (opcional)<input id="outdir" type="text" placeholder="auto: out/run_…_seedN" style="min-width:210px"></label>
        </div>
      </details>
      <div class="meta" id="meta-treino">—</div>
      <div class="aviso" id="aviso"></div>
      <details class="bloco">
        <summary>como funciona o treino</summary>
        <div class="nota">O treino corre em <b>subprocesso</b> (nunca dentro do servidor: GIL) e faz <b>loop</b> de
          episódios (é RL — ao contrário da sonda, o treino não espera por REINICIAR). O stdout/stderr vai para
          <span style="font-family:var(--mono)">train_stdout.log</span> do run — secção 6.</div>
      </details>
    </section>
    <section id="sec-runs">
      <h2>2 · Runs em disco (multi-seed / multi-IA)</h2>
      <div class="linha" style="margin-bottom:10px">
        <label class="campo">run ativo (curvas)<select id="runSel"></select></label>
        <label class="campo">amostra<input id="amostra" type="number" value="1200" step="100" min="50"></label>
        <label class="campo">overlay<select id="overlay">
          <option value="1">todos os runs</option><option value="0">só o ativo</option></select></label>
      </div>
      <div style="overflow:auto;max-height:190px"><table id="tab-runs"><thead><tr>
        <th>run</th><th class="num">linhas</th><th class="num">mean_ret</th><th class="num">mean_z</th>
        <th>best_model.zip</th><th>evals</th></tr></thead><tbody></tbody></table></div>
    </section>
  </div>

  <section id="sec-curvas">
    <h2>3 · Curvas do treino (SVG desenhado em JS, sem libs)</h2>
    <div style="display:grid;grid-template-columns:1fr;gap:16px">
      <div>
        <div style="font-family:var(--mono);font-size:12px;color:var(--suave);margin-bottom:4px">mean_ret ↑ (recompensa média)</div>
        <svg id="g-ret" viewBox="0 0 1000 220"></svg>
      </div>
      <div>
        <div style="font-family:var(--mono);font-size:12px;color:var(--suave);margin-bottom:4px">mean_z (altura média, m — alvo 1,0)</div>
        <svg id="g-z" viewBox="0 0 1000 220"></svg>
      </div>
    </div>
    <div class="legenda" id="legenda"></div>
    <div class="linha" style="margin-top:12px">
      <button id="bt-evals">▤ evals do run ativo (evaluations.npz)</button>
      <span class="nota" id="meta-evals" style="margin:0">—</span>
    </div>
    <div class="nota" id="nota-curvas">sem dados: aparece uma curva por run logo que exista
      <span style="font-family:var(--mono)">train_log.jsonl</span>.</div>
  </section>

  <section id="sec-rede" class="destaque">
    <h2>4 · Rede ao vivo — MLP [16, 64, 64, 4] (obs → ação)</h2>
    <div class="linha" style="margin-bottom:12px">
      <label class="campo">política (.zip)<select id="modelos" style="min-width:280px"></select></label>
      <label class="campo">ritmo da sonda<select id="ritmo">
        <option value="1" selected>1× (tempo real — vê-se a corrigir)</option>
        <option value="2">2×</option><option value="4">4×</option>
        <option value="0">máximo (sem travão)</option></select></label>
      <button class="rede" id="bt-rede">▶ Rede ao vivo</button>
      <button class="perigo" id="bt-rede-parar" disabled>■ Parar rede</button>
      <span class="pilula off" id="pilula-linha"><i class="ponto"></i><b>linha</b> <span id="idade">—</span></span>
    </div>
    <div class="grupo-episodio">
      <span class="rotulo">episódio</span>
      <button class="reiniciar" id="bt-reiniciar" title="incrementa o contador `reiniciar` do ficheiro de controlo: a sonda vê a mudança e faz env.reset()">↻ REINICIAR</button>
      <label class="interruptor" title="LOOP ligado: a sonda reinicia sozinha no fim do episódio (é o que o treino faz sempre)">
        <input type="checkbox" id="ck-loop"> LOOP automático</label>
      <span class="selo-estado" id="estado-episodio">sem sonda</span>
      <span class="nota" style="margin:0">SEM LOOP (por omissão) o episódio acaba, a física para e a sonda espera
        por <b>↻ REINICIAR</b>; o treino continua a fazer loop.</span>
    </div>
    <div class="grelha" style="grid-template-columns:minmax(420px,2fr) minmax(300px,1fr)">
      <div>
        <svg id="rede" viewBox="0 0 1020 560"></svg>
        <div class="legenda">
          <span><i class="amostra" style="background:#1e293b"></i>|a| baixa</span>
          <span><i class="amostra" style="background:#2f6fa8"></i>média</span>
          <span><i class="amostra" style="background:#fbbf24"></i>|a| alta</span>
          <span>arestas acesas = nós mais ativos da camada</span>
        </div>
      </div>
      <div>
        <div style="font-family:var(--mono);font-size:12px;color:var(--suave);margin-bottom:6px">output · ação (4,) — <b>média crua</b> da política (sem tanh)</div>
        <div class="lista" id="lista-act"></div>
        <div style="font-family:var(--mono);font-size:12px;color:var(--suave);margin:14px 0 6px">estado ao vivo · info do env (altura, deriva, guinada e vento)</div>
        <div class="lista" id="lista-estado"></div>
        <div class="meta" id="meta-rede">—</div>
        <details class="bloco">
          <summary>detalhes da rede (obs 16, h1/h2 e legenda)</summary>
          <div style="font-family:var(--mono);font-size:12px;color:var(--suave);margin:6px 0">input · obs (16,)</div>
          <div class="lista" id="lista-obs"></div>
          <div class="nota">Δp = (p−p_alvo) · rpy = atitude/π · v = velocidade no corpo · ω = giro/10 · a_prev = ação anterior.
            h1/h2 são as <b>saídas das camadas Linear</b> (pré-tanh) apanhadas por forward hooks no
            <span style="font-family:var(--mono)">net_probe.py</span>; a intensidade da cor é |valor| normalizado por camada.
            A saída (4,) é a <b>média gaussiana crua</b> da política
            (<span style="font-family:var(--mono)">squash_output=False</span>, sem tanh — |act| pode passar de 1):
            o corte ao intervalo do atuador é feito pelo env, ao aplicar a ação. O <b>estado ao vivo</b> vem do
            <span style="font-family:var(--mono)">info</span> do env medido no MESMO instante da obs (inclui
            <span style="font-family:var(--mono)">yaw_err</span> em rad e o vento em vigor
            <span style="font-family:var(--mono)">vento_vel</span>/<span style="font-family:var(--mono)">vento_azim</span>);
            a secção 5 escreve o vento e esta mostra o drone a corrigir.</div>
        </details>
      </div>
    </div>
  </section>

  <section id="sec-vento">
    <h2>5 · Vento ao vivo — o painel escreve, o net_probe.py aplica (física real, sem teleporte)</h2>
    <div class="grelha" style="grid-template-columns:minmax(380px,1.3fr) minmax(300px,1fr)">
      <div>
        <div class="linha" style="margin-bottom:10px">
          <label class="campo" style="flex:1 1 280px">força · vel (0–5 m/s)
            <span class="par">
              <input type="range" id="v-vel-r" min="0" max="5" step="0.05" value="0">
              <input type="number" id="v-vel" min="0" max="5" step="0.05" value="0">
            </span>
          </label>
        </div>
        <div class="linha" style="margin-bottom:10px">
          <label class="campo" style="flex:1 1 280px">direção · azimute (0–360°; 0° = +x, 90° = +y)
            <span class="par">
              <input type="range" id="v-az-r" min="0" max="360" step="1" value="0">
              <input type="number" id="v-az" min="0" max="360" step="1" value="0">
            </span>
          </label>
        </div>
        <div class="linha" style="margin-bottom:12px">
          <label class="campo" style="flex:1 1 280px">elevação (−90..90°; 0 = horizontal, 90 = a soprar para cima)
            <span class="par">
              <input type="range" id="v-el-r" min="-90" max="90" step="1" value="0">
              <input type="number" id="v-el" min="-90" max="90" step="1" value="0">
            </span>
          </label>
        </div>
        <div class="linha">
          <button class="primario" id="bt-vento">APLICAR VENTO</button>
          <button class="perigo" id="bt-vento-parar">PARAR VENTO</button>
          <span class="nota" style="margin:0">atalhos de azimute (só mudam o número; falta APLICAR):</span>
          <button id="bt-vento-x">+x 0°</button>
          <button id="bt-vento-y">+y 90°</button>
          <button id="bt-vento-mx">−x 180°</button>
          <button id="bt-vento-my">−y 270°</button>
        </div>
        <details class="bloco">
          <summary>como funciona o vento ao vivo</summary>
          <div class="nota">O botão grava <span style="font-family:var(--mono)">controle_vento.json</span> (tmp +
            rename atómico) e o <span style="font-family:var(--mono)">net_probe.py</span> verifica-o a CADA passo
            de decisão e chama <span style="font-family:var(--mono)">env.definir_vento(vel, azimute, elevação)</span>
            — o drone deriva pela física do fluido e a rede (secção 4) reage. «PARAR VENTO» grava
            <span style="font-family:var(--mono)">ativo:false</span> → vento 0 m/s (e aparece um atalho para
            <b>repor</b> o vento anterior). Os atalhos de azimute só mudam o azimute: falta carregar em
            <b>APLICAR VENTO</b>.</div>
        </details>
        <div class="aviso" id="aviso-vento"></div>
      </div>
      <div>
        <div style="font-family:var(--mono);font-size:12px;color:var(--suave);margin-bottom:6px">
          vento ao vivo · JSONL da sonda (vento_vel, vento_azim, yaw_err, dist_xy)</div>
        <div class="lista" id="lista-vento"></div>
        <div class="meta" id="meta-vento">—</div>
      </div>
    </div>
  </section>

  <section id="sec-log">
    <h2>6 · Log do treino (cauda de train_stdout.log)</h2>
    <div class="linha" style="margin-bottom:8px">
      <label class="linha" style="gap:6px;color:var(--suave);font-size:12px;min-height:34px;cursor:pointer">
        <input type="checkbox" id="seguir" checked style="min-width:auto"> seguir o fim</label>
      <span class="nota" id="nome-log" style="margin:0">—</span>
    </div>
    <pre id="log">(sem stdout ainda)</pre>
  </section>
</main>
<div id="toasts" aria-live="polite"></div>
<script>
"use strict";
const $ = (id) => document.getElementById(id);
const CORES = ["#38bdf8","#f472b6","#a3e635","#fbbf24","#c084fc","#34d399","#fb7185","#60a5fa",
               "#facc15","#4ade80","#e879f9","#22d3ee"];
const ROT_ENTRADA = ["Δx","Δy","Δz","φ roll","θ pitch","ψ yaw","vx","vy","vz","ωx","ωy","ωz",
                     "a₀ empuxo","a₁ τx","a₂ τy","a₃ τz"];
const ROT_SAIDA = ["empuxo","τx","τy","τz"];
/* estado do env mostrado ao vivo (chave do JSONL, unidade, casas decimais) — os 3 novos do contrato v2 */
const ROT_ESTADO = [["z","m",3],["dist_xy","m",3],["yaw_err","rad",3],["vento_vel","m/s",2],
                    ["vento_azim","°",1],["no_alvo","",0]];
const ROT_VENTO = [["vento_vel","m/s",2],["vento_azim","°",1],["yaw_err","rad",3],["dist_xy","m",3]];
const TOPO = [16, 64, 64, 4];
const cacheCurvas = new Map();      // dir → {mtime, serie}
const ventoUI = { preso: false };   // true enquanto o dono mexe nos sliders (o servidor não os pisa)
let estadoAtual = null, ultimoNet = null, tNet = 0;

async function pedir(url, opcoes) {
  try {
    const r = await fetch(url, opcoes);
    const texto = await r.text();
    let dados = null;
    try { dados = JSON.parse(texto); } catch (e) { dados = { erro: texto.slice(0, 300) }; }
    return { ok: r.ok, codigo: r.status, dados };
  } catch (e) { return { ok: false, codigo: 0, dados: { erro: String(e) } }; }
}
function aviso(texto, mau) {
  const el = $("aviso");
  el.textContent = texto || "";
  el.className = "aviso" + (texto ? (mau ? " mau" : " bom") : "");
}
function fmt(v, casas) { return (typeof v !== "number" || !isFinite(v)) ? "—" : v.toFixed(casas ?? 2); }
function pilula(id, ligada, texto, erro) {
  const el = $(id);
  el.className = "pilula " + (erro ? "erro" : (ligada ? "on" : "off"));
  el.querySelector("span").textContent = texto;
}
function idade(s) {
  if (typeof s !== "number" || !isFinite(s)) return "—";
  if (s < 1.5) return "agora";
  if (s < 90) return "há " + s.toFixed(0) + " s";
  return "há " + (s / 60).toFixed(1) + " min";
}

/* ------------------------------------------------------------------ feedback imediato (toasts) */
function toast(texto, tipo, acao) {            // tipo: "bom" | "mau" | "" · acao: {rotulo, fn} opcional
  const caixa = $("toasts");
  if (!caixa) return;
  const el = document.createElement("div");
  el.className = "toast " + (tipo || "");
  const span = document.createElement("span");
  span.textContent = texto;
  el.appendChild(span);
  if (acao) {
    const b = document.createElement("button");
    b.textContent = acao.rotulo;
    b.onclick = () => { acao.fn(); el.remove(); };
    el.appendChild(b);
  }
  const x = document.createElement("button");
  x.textContent = "×"; x.title = "fechar";
  x.onclick = () => el.remove();
  el.appendChild(x);
  caixa.appendChild(el);
  setTimeout(() => el.remove(), acao ? 12000 : 5000);
  while (caixa.children.length > 4) caixa.firstChild.remove();
}
async function ocupado(botao, fn) {            // desativa durante o pedido (evita duplo clique)
  if (!botao) return fn();
  const antes = botao.disabled;
  botao.disabled = true;
  try { return await fn(); } finally { botao.disabled = antes; }
}

/* ------------------------------------------------------------------ ações */
async function iniciar() {
  const corpo = { timesteps: +$("ts").value, seed: +$("seed").value, n_envs: +$("nenvs").value };
  const od = $("outdir").value.trim();
  if (od) corpo.out_dir = od;
  const r = await ocupado($("bt-treinar"), () => pedir("/api/start", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) }));
  if (r.ok) aviso("treino lançado · pid " + r.dados.pid + " · " + r.dados.out_dir
                  + (r.dados.flags_omitidas && r.dados.flags_omitidas.length
                     ? " · flags omitidas: " + r.dados.flags_omitidas.join(", ") : ""), false);
  else aviso("não arrancou (" + r.codigo + "): " + (r.dados.erro || "erro"), true);
  toast(r.ok ? "treino lançado · pid " + r.dados.pid + " → " + r.dados.out_dir
             : "o treino não arrancou (" + r.codigo + "): " + (r.dados.erro || "erro"), r.ok ? "bom" : "mau");
  poll();
}
async function parar() {
  const b = $("bt-parar");
  if (b.dataset.confirmar !== "1") {           // ação destrutiva: segundo clique confirma (C.1.4.01)
    b.dataset.confirmar = "1";
    b.textContent = "■ confirmar paragem?";
    toast("parar o treino interrompe o run a meio (o que já foi gravado fica no disco) — clica outra vez para confirmar", "", null);
    setTimeout(() => { if (b.dataset.confirmar === "1") { b.dataset.confirmar = ""; b.textContent = "■ Parar treino"; } }, 5000);
    return;
  }
  b.dataset.confirmar = ""; b.textContent = "■ Parar treino";
  const r = await ocupado(b, () => pedir("/api/stop", { method: "POST" }));
  aviso(r.ok ? "SIGTERM enviado ao pid " + r.dados.pid : "nada a parar: " + (r.dados.erro || ""), !r.ok);
  toast(r.ok ? "treino parado (SIGTERM para o pid " + r.dados.pid + ")" : "nada a parar", r.ok ? "bom" : "mau");
  poll();
}
async function iniciarRede() {
  const modelo = $("modelos").value;
  if (!modelo) { aviso("não há best_model.zip em nenhum run — treina primeiro", true); return; }
  const r = await ocupado($("bt-rede"), () => pedir("/api/net/start", { method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: modelo, interval: 0.2, fator_tempo: +$("ritmo").value }) }));
  aviso(r.ok ? "sonda lançada · pid " + r.dados.pid + " · ritmo " + fmt(r.dados.fator_tempo, 0) + "× → "
               + r.dados.out : "sonda falhou: " + (r.dados.erro || ""), !r.ok);
  toast(r.ok ? "sonda lançada · pid " + r.dados.pid + " · ritmo " + fmt(r.dados.fator_tempo, 0) + "×"
             : "a sonda não arrancou (" + r.codigo + "): " + (r.dados.erro || "erro"), r.ok ? "bom" : "mau");
  poll();
}
async function pararRede() {
  const r = await ocupado($("bt-rede-parar"), () => pedir("/api/net/stop", { method: "POST" }));
  aviso(r.ok ? "sonda parada (pid " + r.dados.pid + ")" : "sonda já parada", !r.ok);
  toast(r.ok ? "sonda parada (pid " + r.dados.pid + ")" : "a sonda já estava parada", r.ok ? "bom" : "");
  poll();
}

/* ------------------------------------------- episódio (sem loop por omissão): ↻ REINICIAR + LOOP */
async function reiniciarEpisodio(botao) {
  const r = await ocupado(botao, () => pedir("/api/reiniciar", { method: "POST" }));
  if (r.ok) {
    toast("«" + (r.dados.mensagem || "reinício pedido") + "» — a sonda faz env.reset() no passo seguinte"
          + (r.dados.probe && r.dados.probe.running ? "" : " (mas a sonda está PARADA: clica ▶ Rede ao vivo)"),
          r.dados.probe && r.dados.probe.running ? "bom" : "");
  } else {
    toast("não consegui reiniciar (" + r.codigo + "): " + (r.dados.erro || "erro"), "mau");
  }
  poll();
}
async function alternarLoop(ligado, caixa) {
  const r = await ocupado(null, () => pedir("/api/loop", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ativo: !!ligado }) }));
  if (!r.ok) {
    if (caixa) caixa.checked = !ligado;        // o servidor recusou: não mentir no controlo
    toast("não consegui mudar o LOOP (" + r.codigo + "): " + (r.dados.erro || "erro"), "mau");
  } else {
    toast(r.dados.mensagem || ("LOOP " + (ligado ? "ligado" : "desligado")), "bom");
  }
  poll();
}

/* ------------------------------------------------------------------ vento ao vivo (painel 5) */
function erroJS(texto) {                       // visível só se algo rebentar (o dump-dom verifica-o)
  const el = $("erros-js");
  if (!el) return;
  el.style.display = "block";
  el.textContent = "erro de JS: " + texto;
}
window.addEventListener("error", (e) => erroJS((e.message || e.type) + " @" + (e.filename || "?") + ":" + (e.lineno || 0)));
window.addEventListener("unhandledrejection", (e) => erroJS("promessa rejeitada: " + ((e.reason && e.reason.message) || e.reason)));

function ligarPar(numId, ranId) {              // slider ⇄ número, sem realimentar o servidor
  const num = $(numId), ran = $(ranId);
  num.addEventListener("input", () => { ran.value = num.value; ventoUI.preso = true; });
  ran.addEventListener("input", () => { num.value = ran.value; ventoUI.preso = true; });
}
function lerVentoUI() {
  return { vel: +$("v-vel").value, azimute: +$("v-az").value, elevacao: +$("v-el").value };
}
function escreverVentoUI(v) {                  // estado do servidor → controlos (só se o dono não mexeu)
  const pares = [["v-vel", "v-vel-r", v.vel, 5], ["v-az", "v-az-r", v.azimute, 360],
                 ["v-el", "v-el-r", v.elevacao, 90]];
  for (const [numId, ranId, valor, maximo] of pares) {
    const t = (typeof valor === "number" && isFinite(valor)) ? Math.max(-maximo, Math.min(maximo, valor)) : 0;
    $(numId).value = String(t);
    $(ranId).value = String(t);
  }
}
async function aplicarVento(corpo) {
  const anterior = { ...lerVentoUI(), ativo: true };     // para o «↩ repor» (desfazer do PARAR VENTO)
  const r = await pedir("/api/vento", { method: "POST", headers: { "Content-Type": "application/json" },
                                        body: JSON.stringify(corpo) });
  const el = $("aviso-vento");
  if (r.ok) {
    ventoUI.preso = false;
    el.className = "aviso bom";
    el.textContent = (r.dados.ativo
      ? "vento aplicado: " + fmt(r.dados.vel, 2) + " m/s · azimute " + fmt(r.dados.azimute, 1)
        + "° · elevação " + fmt(r.dados.elevacao, 1) + "°"
      : "vento PARADO (ativo=false → 0 m/s)")
      + " · escrito em " + (r.dados.caminho || "?");
    toast(el.textContent, "bom", r.dados.ativo ? null : {
      rotulo: "↩ repor " + fmt(anterior.vel, 1) + " m/s",
      fn: () => aplicarVento(anterior) });
  } else {
    el.className = "aviso mau";
    el.textContent = "vento recusado (" + r.codigo + "): " + (r.dados.erro || "erro");
    toast(el.textContent, "mau");
  }
  poll();
}
function atalhoAzimute(graus) {
  $("v-az").value = String(graus); $("v-az-r").value = String(graus); ventoUI.preso = true;
}

/* ------------------------------------------------------------------ gráficos SVG */
function grafico(svg, series, opcoes) {
  const W = 1000, H = 220, M = { e: 62, d: 16, t: 14, b: 26 };
  const uteis = series.filter(s => s.y.some(v => v !== null && isFinite(v)));
  if (!uteis.length) {
    svg.innerHTML = '<rect width="' + W + '" height="' + H + '" fill="#0a1220" rx="8"/>'
      + '<text x="' + (W / 2) + '" y="' + (H / 2) + '" fill="#4a5b73" font-size="14" text-anchor="middle"'
      + ' font-family="monospace">' + (opcoes.vazio || "sem dados") + '</text>';
    return false;
  }
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const s of uteis) {
    for (let i = 0; i < s.y.length; i++) {
      const v = s.y[i]; if (v === null || !isFinite(v)) continue;
      const x = (s.x[i] === null || !isFinite(s.x[i])) ? i : s.x[i];
      if (x < x0) x0 = x; if (x > x1) x1 = x;
      if (v < y0) y0 = v; if (v > y1) y1 = v;
    }
  }
  if (Number.isFinite(opcoes.base)) { y0 = Math.min(y0, opcoes.base); y1 = Math.max(y1, opcoes.base); }
  if (x1 <= x0) x1 = x0 + 1;
  if (y1 <= y0) { y1 = y0 + 1; }
  const folga = (y1 - y0) * 0.08; y0 -= folga; y1 += folga;
  const px = (x) => M.e + (x - x0) / (x1 - x0) * (W - M.e - M.d);
  const py = (y) => H - M.b - (y - y0) / (y1 - y0) * (H - M.t - M.b);
  const partes = ['<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="#0a1220" rx="8"/>'];
  for (let i = 0; i <= 4; i++) {                       // grelha horizontal + rótulos de y
    const v = y0 + (y1 - y0) * i / 4, y = py(v);
    partes.push('<line x1="' + M.e + '" y1="' + y.toFixed(1) + '" x2="' + (W - M.d) + '" y2="' + y.toFixed(1)
      + '" stroke="#16202f" stroke-width="1"/>');
    partes.push('<text x="' + (M.e - 6) + '" y="' + (y + 3.5).toFixed(1) + '" fill="#5b6d86" font-size="10"'
      + ' text-anchor="end" font-family="monospace">' + v.toFixed(Math.abs(v) < 10 ? 2 : 1) + '</text>');
  }
  for (let i = 0; i <= 4; i++) {                       // grelha vertical + rótulos de x (t, passos)
    const v = x0 + (x1 - x0) * i / 4, x = px(v);
    partes.push('<line x1="' + x.toFixed(1) + '" y1="' + M.t + '" x2="' + x.toFixed(1) + '" y2="' + (H - M.b)
      + '" stroke="#111a27" stroke-width="1"/>');
    partes.push('<text x="' + x.toFixed(1) + '" y="' + (H - 9) + '" fill="#5b6d86" font-size="10"'
      + ' text-anchor="middle" font-family="monospace">' + (Math.abs(v) >= 10000 ? (v / 1000).toFixed(0) + "k" : v.toFixed(0)) + '</text>');
  }
  if (Number.isFinite(opcoes.base)) partes.push('<line x1="' + M.e + '" y1="' + py(opcoes.base).toFixed(1) + '" x2="'
    + (W - M.d) + '" y2="' + py(opcoes.base).toFixed(1) + '" stroke="#475569" stroke-dasharray="4 4"/>');
  for (const s of uteis) {
    let d = "", aberto = false;
    for (let i = 0; i < s.y.length; i++) {
      const v = s.y[i], xv = (s.x[i] === null || !isFinite(s.x[i])) ? i : s.x[i];
      if (v === null || !isFinite(v)) { aberto = false; continue; }
      d += (aberto ? "L" : "M") + px(xv).toFixed(1) + " " + py(v).toFixed(1) + " ";
      aberto = true;
    }
    partes.push('<path d="' + d + '" fill="none" stroke="' + s.cor + '" stroke-width="' + (s.grosso ? 2.2 : 1.15)
      + '" stroke-opacity="' + (s.grosso ? 0.98 : 0.55) + '" stroke-linejoin="round"/>');
  }
  svg.innerHTML = partes.join("");
  return true;
}

/* ------------------------------------------------------------------ rede MLP */
const rede = { nos: [], arestas: [], refsObs: [], refsAct: [], refsEstado: [], refsVento: [], montada: false,
               x: [170, 430, 690, 930] };
function corNos(v, maxAbs) {
  const t = Math.max(0, Math.min(1, Math.abs(v) / Math.max(maxAbs, 1e-6)));
  return "hsl(" + (212 - 168 * t).toFixed(0) + ",88%," + (17 + 45 * t).toFixed(0) + "%)";
}
function montarRede() {
  if (rede.montada) return;
  const W = 1020, H = 560, topo = 34, base = H - 26, partes = [];
  const raio = [7, 3.1, 3.1, 8.5];
  const ys = TOPO.map((n) => Array.from({ length: n }, (_, i) => topo + (base - topo) * (n === 1 ? 0.5 : i / (n - 1))));
  const pares = [[0, 1, 6], [1, 2, 7], [2, 3, 4]];
  for (const [a, b, k] of pares) {
    for (let i = 0; i < TOPO[a]; i++) {
      for (let j = 0; j < k; j++) {
        const jj = Math.round((k === 1 ? 0.5 : j / (k - 1)) * (TOPO[b] - 1));
        partes.push('<line data-camada="' + a + '" data-s="' + i + '" x1="' + rede.x[a] + '" y1="' + ys[a][i].toFixed(1)
          + '" x2="' + rede.x[b] + '" y2="' + ys[b][jj].toFixed(1) + '" stroke="#7dd3fc" stroke-width="0.6"'
          + ' stroke-opacity="0.05"/>');
      }
    }
  }
  partes.push('<g id="g-nos"></g>');
  $("rede").innerHTML = partes.join("");
  const g = $("rede").querySelector("#g-nos"), grupos = [];
  for (let c = 0; c < TOPO.length; c++) {
    const lista = [];
    for (let i = 0; i < TOPO[c]; i++) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      el.setAttribute("cx", rede.x[c]); el.setAttribute("cy", ys[c][i].toFixed(1));
      el.setAttribute("r", raio[c]); el.setAttribute("fill", "#16202f");
      el.setAttribute("stroke", "#243449"); el.setAttribute("stroke-width", "0.6");
      g.appendChild(el); lista.push(el);
    }
    grupos.push(lista);
  }
  rede.nos = grupos;
  const titulos = ["obs 16", "h1 64 (Linear+tanh)", "h2 64 (Linear+tanh)", "ação 4 (média crua)"];
  for (let c = 0; c < 4; c++) {
    const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
    t.setAttribute("x", rede.x[c]); t.setAttribute("y", 18); t.setAttribute("fill", "#8195b0");
    t.setAttribute("font-size", "11"); t.setAttribute("text-anchor", "middle");
    t.setAttribute("font-family", "monospace"); t.textContent = titulos[c];
    g.parentNode.appendChild(t);
  }
  for (let i = 0; i < TOPO[0]; i++) {
    const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
    t.setAttribute("x", rede.x[0] - 13); t.setAttribute("y", (ys[0][i] + 3).toFixed(1));
    t.setAttribute("fill", "#7f93ad"); t.setAttribute("font-size", "9.5");
    t.setAttribute("text-anchor", "end"); t.setAttribute("font-family", "monospace");
    t.textContent = ROT_ENTRADA[i] || ("in" + i);
    g.parentNode.appendChild(t);
  }
  for (let i = 0; i < TOPO[3]; i++) {
    const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
    t.setAttribute("x", rede.x[3] + 14); t.setAttribute("y", (ys[3][i] + 3).toFixed(1));
    t.setAttribute("fill", "#fbbf24"); t.setAttribute("font-size", "10.5");
    t.setAttribute("font-family", "monospace"); t.textContent = ROT_SAIDA[i] || ("out" + i);
    g.parentNode.appendChild(t);
  }
  rede.arestas = Array.from($("rede").querySelectorAll("line[data-s]"));
  const obs = $("lista-obs"), act = $("lista-act");
  rede.refsObs = ROT_ENTRADA.map((nome) => itemLista(obs, nome));
  rede.refsAct = ROT_SAIDA.map((nome) => itemLista(act, nome));
  rede.refsEstado = ROT_ESTADO.map(([chave, unidade]) => itemValor($("lista-estado"), chave, unidade));
  rede.refsVento = ROT_VENTO.map(([chave, unidade]) => itemValor($("lista-vento"), chave, unidade));
  rede.montada = true;
}
function itemLista(pai, nome) {
  const div = document.createElement("div"); div.className = "item";
  const n = document.createElement("span"); n.className = "nome"; n.textContent = nome;
  const b = document.createElement("span"); b.className = "barra"; const i = document.createElement("i");
  b.appendChild(i);
  const v = document.createElement("span"); v.className = "val"; v.textContent = "—";
  div.append(n, b, v); pai.appendChild(div);
  return { barra: i, valor: v };
}
function pintarLista(refs, valores) {
  const maxAbs = Math.max(1e-6, ...valores.map((v) => Math.abs(v || 0)));
  refs.forEach((ref, i) => {
    const v = valores[i];
    const ok = typeof v === "number" && isFinite(v);
    ref.valor.textContent = ok ? v.toFixed(3) : "—";
    ref.barra.style.width = ok ? (100 * Math.abs(v) / maxAbs).toFixed(1) + "%" : "0%";
  });
}
function itemValor(pai, nome, unidade) {       // linha nome↔valor (sem barra): unidades mistas
  const div = document.createElement("div"); div.className = "item sem-barra";
  const n = document.createElement("span"); n.className = "nome"; n.textContent = nome;
  const v = document.createElement("span"); v.className = "val"; v.textContent = "—";
  const u = document.createElement("span"); u.className = "unid"; u.textContent = unidade || "";
  div.append(n, v, u); pai.appendChild(div);
  return { valor: v };
}
function pintarValores(refs, linha, chaves) {  // chaves = [[chave, unidade, casas], …]
  refs.forEach((ref, i) => {
    const [chave, , casas] = chaves[i];
    const v = linha ? linha[chave] : null;
    if (typeof v === "boolean") { ref.valor.textContent = v ? "sim" : "não"; return; }
    const ok = typeof v === "number" && isFinite(v);
    ref.valor.textContent = ok ? v.toFixed(casas) : "—";
  });
}
function pintarCamada(camada, valores) {
  const nos = rede.nos[camada], maxAbs = Math.max(1e-6, ...valores.map((v) => Math.abs(v || 0)));
  nos.forEach((el, i) => el.setAttribute("fill", corNos(valores[i] || 0, maxAbs)));
  return valores.map((v, i) => [Math.abs(v || 0), i]).sort((a, b) => b[0] - a[0]).slice(0, 5).map((p) => p[1]);
}
function atualizarRede(linha) {
  montarRede();
  if (!linha) {
    for (const camada of rede.nos) camada.forEach((el) => el.setAttribute("fill", "#16202f"));
    for (const linhaEl of rede.arestas) linhaEl.setAttribute("stroke-opacity", "0.05");
    pintarLista(rede.refsObs, []); pintarLista(rede.refsAct, []);
    pintarValores(rede.refsEstado, null, ROT_ESTADO); pintarValores(rede.refsVento, null, ROT_VENTO);
    $("meta-rede").textContent = "sem amostras — clica em «rede ao vivo ▶» para lançar a sonda";
    return;
  }
  const obs = linha.obs || [], h1 = linha.h1 || [], h2 = linha.h2 || [], act = linha.act || [];
  const topo = [obs.length, h1.length, h2.length, act.length];
  const ativos = [pintarCamada(0, obs), pintarCamada(1, h1), pintarCamada(2, h2), pintarCamada(3, act)];
  const conjunto = ativos.map((a) => new Set(a));
  for (const el of rede.arestas) {
    const c = +el.dataset.camada;
    el.setAttribute("stroke-opacity", conjunto[c].has(+el.dataset.s) ? "0.5" : "0.05");
  }
  pintarLista(rede.refsObs, obs); pintarLista(rede.refsAct, act);
  pintarValores(rede.refsEstado, linha, ROT_ESTADO); pintarValores(rede.refsVento, linha, ROT_VENTO);
  $("meta-rede").textContent = "t=" + fmt(linha.t, 2) + " s · z=" + fmt(linha.z, 3) + " m · dist_xy="
    + fmt(linha.dist_xy, 3) + " m · yaw_err=" + fmt(linha.yaw_err, 3) + " rad · vento="
    + fmt(linha.vento_vel, 2) + " m/s @ " + fmt(linha.vento_azim, 1) + "° · no_alvo="
    + (linha.no_alvo ? "sim" : "não")
    + " · topologia " + topo.join("→") + (topo.join() === TOPO.join() ? " ✓" : " (≠ [16,64,64,4])");
}

/* ------------------------------------------------------------------ painel de runs */
function preencherRuns(runs, ativo) {
  const tbody = $("tab-runs").querySelector("tbody");
  const nomes = runs.map((r) => r.nome).join("|");
  if (tbody.dataset.nomes !== nomes) {
    tbody.dataset.nomes = nomes;
    tbody.innerHTML = runs.map((r) => '<tr data-nome="' + r.nome + '"><td>' + r.nome + '</td><td class="num">'
      + r.n_linhas + '</td><td class="num">' + fmt(r.mean_ret, 2) + '</td><td class="num">' + fmt(r.mean_z, 3)
      + '</td><td>' + (r.modelos.some((m) => m.endsWith("best_model.zip")) ? "✓" : "—") + '</td><td>'
      + (r.tem_evals ? "✓" : "—") + '</td></tr>').join("");
    for (const tr of tbody.querySelectorAll("tr")) {
      tr.onclick = () => { $("runSel").value = tr.dataset.nome; desenharCurvas(); };
    }
  }
  const sel = $("runSel"), escolhido = sel.value;
  const opcoes = runs.map((r) => '<option value="' + r.nome + '">' + r.nome + "  (" + fmt(r.mean_ret, 1) + ")</option>").join("");
  if (sel.dataset.opcoes !== opcoes) {
    sel.dataset.opcoes = opcoes; sel.innerHTML = opcoes;
    sel.value = runs.some((r) => r.nome === escolhido) ? escolhido : (ativo || (runs[0] && runs[0].nome) || "");
  }
  const mod = $("modelos"), modelos = [];
  for (const r of runs) for (const m of r.modelos) if (!modelos.includes(m)) modelos.push(m);
  const chave = modelos.join("|");
  if (mod.dataset.modelos !== chave) {
    const antes = mod.value;
    mod.dataset.modelos = chave;
    mod.innerHTML = modelos.length
      ? modelos.map((m) => '<option value="' + m + '">' + m.replace(/^.*\/out\//, "") + "</option>").join("")
      : '<option value="">(sem .zip em nenhum run)</option>';
    if (modelos.includes(antes)) mod.value = antes;
  }
  $("bt-rede").disabled = modelos.length === 0;
  for (const tr of tbody.querySelectorAll("tr")) tr.className = (tr.dataset.nome === sel.value) ? "sel" : "";
}

/* ------------------------------------------------------------------ curvas */
async function serieDe(run, maxPontos) {
  const r = await pedir("/api/run?max=" + maxPontos + "&run=" + encodeURIComponent(run.nome));
  if (!r.ok) return null;
  const xs = (r.dados.t || []).map((v, i) => (typeof v === "number" && isFinite(v)) ? v : i);
  return { nome: run.nome, dir: r.dados.dir, t: xs, ret: r.dados.mean_ret || [], z: r.dados.mean_z || [],
           mtime: run.mtime, n: r.dados.n_linhas };
}
async function desenharCurvas() {
  if (!estadoAtual) return;
  const runs = estadoAtual.runs || [], sel = $("runSel").value || estadoAtual.train.run;
  const overlay = $("overlay").value === "1", maxPontos = Math.max(50, +$("amostra").value || 1200);
  const alvos = runs.filter((r) => overlay ? true : r.nome === sel).slice(0, 14);
  /* O run ativo pode viver FORA do --out do dashboard (treino lançado com out_dir noutro sítio): nesse caso
     não há série legível para ele. Só se tenta o run em falta quando não há mais nada para desenhar. */
  const foraDoOut = !!sel && !runs.some((r) => r.nome === sel);
  if (foraDoOut && !alvos.length) alvos.unshift({ nome: sel, mtime: 0 });
  const series = [];
  for (let i = 0; i < alvos.length; i++) {
    const run = alvos[i], chave = run.nome + "@" + run.mtime;
    let s = cacheCurvas.get(run.nome);
    if (!s || s.mtime !== run.mtime || s.max !== maxPontos) {
      s = await serieDe(run, maxPontos);
      if (s) { s.max = maxPontos; cacheCurvas.set(run.nome, s); }
    }
    if (!s) continue;
    const grosso = run.nome === sel, cor = grosso ? "#38bdf8" : CORES[i % CORES.length];
    series.push({ nome: run.nome, cor, grosso, x: s.t, y: s.ret });
  }
  grafico($("g-ret"), series, { vazio: "sem train_log.jsonl — treina para ver curvas" });
  grafico($("g-z"), series.map((s) => ({ ...s, y: (cacheCurvas.get(s.nome) || {}).z || [] })),
          { base: 1.0, vazio: "sem mean_z no log (o alvo é 1,0 m)" });
  $("legenda").innerHTML = series.map((s) => '<span><i class="amostra" style="background:' + s.cor + '"></i>'
    + s.nome + (s.grosso ? " (ativo)" : "") + '</span>').join("");
  const cacheAtivo = cacheCurvas.get(sel);
  const n = (cacheAtivo && typeof cacheAtivo.n === "number") ? cacheAtivo.n : 0;   // 0 se não houver série
  $("nota-curvas").textContent = series.length
    ? series.length + " run(s) desenhado(s) · " + n + " registos no run ativo"
      + (foraDoOut ? " (fora do out deste dashboard)" : "") + " · 1 curva por run (multi-seed/multi-IA)"
    : "sem dados: aparece uma curva por run logo que exista train_log.jsonl.";
}

/* ------------------------------------------------------------------ evals do SB3 */
async function verEvals() {
  const run = $("runSel").value;
  if (!run) { $("meta-evals").textContent = "sem run selecionado"; return; }
  const r = await pedir("/api/evals?run=" + encodeURIComponent(run));
  if (!r.ok) { $("meta-evals").textContent = "sem evaluations.npz: " + (r.dados.erro || r.codigo); return; }
  const a = r.dados.arrays || {};
  const partes = Object.keys(a).slice(0, 6).map((k) => {
    const vals = (a[k] || []).filter((v) => v !== null);
    const ultimo = vals.length ? vals[vals.length - 1] : null;
    const media = vals.length ? vals.reduce((s, v) => s + v, 0) / vals.length : null;
    return k + "[" + (a[k] || []).length + "] último=" + fmt(ultimo, 3) + " média=" + fmt(media, 3);
  });
  $("meta-evals").textContent = r.dados.nome + " · " + (partes.join("  ·  ") || "sem arrays");
}

/* ------------------------------------------------------------------ guia «o que fazer agora» */
function atualizarGuia(pr, tr, linha, loop) {
  const guia = $("guia"), selo = $("guia-selo"), texto = $("guia-texto");
  if (!guia) return;
  const vivo = !!pr.running, espera = !!pr.espera;
  let classe = "", s = "pronta", t = "";
  if (vivo && espera) {
    classe = "espera"; s = "episódio terminado";
    t = "a sonda parou no fim do episódio (" + (pr.motivo || "?") + ", nº " + (pr.episodio ?? "?")
      + ") e a física está congelada — clica <b>↻ REINICIAR</b> para começar outro episódio"
      + " (ou liga <b>LOOP</b> para ela reiniciar sozinha).";
  } else if (vivo) {
    classe = "vivo"; s = "a correr";
    t = "sonda pid " + pr.pid + " · " + (pr.n_linhas || 0) + " linhas · vento e reinício chegam à física em ~0,02 s"
      + (linha ? " · ao vivo: t=" + fmt(linha.t, 1) + " s, z=" + fmt(linha.z, 2) + " m, deriva=" + fmt(linha.dist_xy, 3) + " m" : "")
      + (loop ? " · <b>LOOP ligado</b> (reinicia sozinha no fim)" : " · <b>sem loop</b> (para no fim e espera)");
  } else if (tr && tr.running) {
    s = "a treinar"; t = "treino a correr (pid " + tr.pid + ", " + fmt(tr.iniciado_ha, 0)
      + " s) — para ver a rede a corrigir em paralelo, escolhe uma política e clica <b>▶ Rede ao vivo</b>.";
  } else if (linha) {
    s = "sonda parada"; t = "há amostras no JSONL mas a sonda não está a correr — clica <b>▶ Rede ao vivo</b> para continuar a ver.";
  } else {
    t = "escolhe a política (.zip) na secção 4 e clica <b>▶ Rede ao vivo</b>; depois muda o vento na secção 5 e vê o drone a corrigir.";
  }
  guia.className = classe;
  selo.textContent = s;
  texto.innerHTML = t;
}

/* ------------------------------------------------------------------ polling */
async function poll() {
  const escolhido = $("runSel").value;
  const [est, net] = await Promise.all([
    pedir("/api/state" + (escolhido ? "?run=" + encodeURIComponent(escolhido) : "")), pedir("/api/net")]);
  if (!est.ok) { pilula("pilula-servidor", false, "erro " + est.codigo, true); return; }
  const d = est.dados; estadoAtual = d;
  pilula("pilula-servidor", true, "out: " + d.servidor.out_dir.split("/").slice(-1)[0] + (d.servidor.train_py ? "" : " · train.py em falta"));
  const tr = d.train;
  pilula("pilula-treino", tr.running, tr.running ? ("pid " + tr.pid + " · " + fmt(tr.iniciado_ha, 0) + " s")
    : (tr.returncode === null ? "parado" : "terminou (exit " + tr.returncode + ")"), tr.returncode !== null && tr.returncode !== 0 && !tr.running);
  $("bt-parar").disabled = !tr.running;
  $("bt-treinar").disabled = tr.running;
  $("meta-treino").innerHTML = "estado: <b>" + (tr.running ? "a treinar" : "parado") + "</b> · pid: <b>"
    + (tr.pid ?? "—") + "</b> · run: <b>" + (tr.run ?? "—") + "</b><br>out_dir: " + (tr.out_dir ?? "—")
    + "<br>cmd: " + (tr.cmd && tr.cmd.length ? tr.cmd.join(" ") : "—")
    + (tr.flags_omitidas && tr.flags_omitidas.length ? "<br>flags omitidas: " + tr.flags_omitidas.join(" · ") : "");
  preencherRuns(d.runs || [], tr.run);
  const log = $("log"), seguir = $("seguir").checked;
  log.textContent = (d.stdout && d.stdout.length) ? d.stdout.join("\n") : "(sem stdout ainda)";
  if (seguir) log.scrollTop = log.scrollHeight;
  $("nome-log").textContent = tr.stdout_log
    || (d.run_painel ? d.run_painel + "/train_stdout.log" : "—");
  const pr = d.probe || {};
  pilula("pilula-rede", pr.running, pr.running ? ("pid " + pr.pid + " · " + (pr.n_linhas || 0) + " linhas") : "parada");
  $("bt-rede-parar").disabled = !pr.running;
  if (net.ok) {
    const linha = net.dados.linha; ultimoNet = linha; tNet = Date.now();
    pilula("pilula-linha", !!linha, linha ? ("t=" + fmt(linha.t, 1) + " s · z=" + fmt(linha.z, 2) + " m") : "sem amostras");
    atualizarRede(linha);
  }
  /* episódio: estado da sonda (espera/reinício/loop) — o guia no topo diz o que fazer agora */
  const linhaNet = (net.ok && net.dados.linha) ? net.dados.linha : null;
  const seloEp = $("estado-episodio");
  if (seloEp) {
    if (!pr.running) { seloEp.className = "selo-estado"; seloEp.textContent = "sem sonda a correr"; }
    else if (pr.espera) {
      seloEp.className = "selo-estado espera";
      seloEp.textContent = "episódio " + (pr.episodio ?? "?") + " terminou (" + (pr.motivo || "?")
        + ") — clica ↻ REINICIAR";
    } else {
      seloEp.className = "selo-estado vivo";
      seloEp.textContent = "episódio a correr" + (d.vento && d.vento.loop ? " (LOOP)" : " (sem loop)");
    }
  }
  const ckLoop = $("ck-loop"), ckGuia = $("ck-guia-loop");
  if (ckLoop) ckLoop.checked = !!d.vento && !!d.vento.loop;
  if (ckGuia) ckGuia.checked = !!d.vento && !!d.vento.loop;
  atualizarGuia(pr, tr, linhaNet, !!d.vento && !!d.vento.loop);
  /* painel 5 · vento: o estado vem do /api/state e os valores AO VIVO da última linha do JSONL */
  const vt = d.vento || {}, vl = (net.ok && net.dados.linha) ? net.dados.linha : null;
  pilula("pilula-vento", !!vt.ativo, vt.ativo
    ? (fmt(vt.vel, 1) + " m/s @ " + fmt(vt.azimute, 0) + "°") : "parado", !!vt.erro);
  if (!ventoUI.preso) escreverVentoUI(vt);
  $("meta-vento").innerHTML = "controlo: <b>" + (vt.ativo ? "ligado" : "parado") + "</b> · pedido: <b>"
    + fmt(vt.vel, 2) + " m/s @ " + fmt(vt.azimute, 1) + "° · elev " + fmt(vt.elevacao, 1) + "°</b> · ficheiro "
    + (vt.existe ? "escrito " + idade(vt.idade) : "ainda não escrito")
    + (vt.erro ? " · <span style=\"color:var(--vermelho)\">" + vt.erro + "</span>" : "")
    + "<br>ficheiro: " + (vt.caminho || "—")
    + "<br>aplicação: " + (pr.running ? "sonda pid " + pr.pid + " a correr · " + (pr.n_linhas || 0) + " linhas"
                                      : "sonda PARADA — o ficheiro só chega à física com a rede ao vivo")
    + (vl ? " · ao vivo: <b>" + fmt(vl.vento_vel, 2) + " m/s @ " + fmt(vl.vento_azim, 1) + "°</b>" : "");
  await desenharCurvas();
}
montarRede();
$("bt-treinar").onclick = iniciar;
$("bt-parar").onclick = parar;
$("bt-rede").onclick = iniciarRede;
$("bt-rede-parar").onclick = pararRede;
/* episódio: ↻ REINICIAR (contador) e LOOP (auto-reset) — o mesmo par no guia do topo e na secção 4 */
$("bt-reiniciar").onclick = () => reiniciarEpisodio($("bt-reiniciar"));
$("bt-guia-reiniciar").onclick = () => reiniciarEpisodio($("bt-guia-reiniciar"));
$("ck-loop").onchange = (e) => alternarLoop(e.target.checked, e.target);
$("ck-guia-loop").onchange = (e) => alternarLoop(e.target.checked, e.target);
window.addEventListener("keydown", (e) => {           // atalhos: R reinicia o episódio, L alterna o LOOP
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const alvo = e.target && e.target.tagName;
  if (alvo === "INPUT" || alvo === "SELECT" || alvo === "TEXTAREA") return;
  if (e.key === "r" || e.key === "R") reiniciarEpisodio($("bt-reiniciar"));
  if (e.key === "l" || e.key === "L") alternarLoop(!$("ck-loop").checked, $("ck-loop"));
});
/* vento: sliders ⇄ números, aplicar/parar e atalhos de azimute (+x, +y, −x, −y) */
ligarPar("v-vel", "v-vel-r"); ligarPar("v-az", "v-az-r"); ligarPar("v-el", "v-el-r");
$("bt-vento").onclick = () => aplicarVento({ ...lerVentoUI(), ativo: true });
$("bt-vento-parar").onclick = () => aplicarVento({ vel: 0, azimute: 0, elevacao: 0, ativo: false });
$("bt-vento-x").onclick = () => atalhoAzimute(0);
$("bt-vento-y").onclick = () => atalhoAzimute(90);
$("bt-vento-mx").onclick = () => atalhoAzimute(180);
$("bt-vento-my").onclick = () => atalhoAzimute(270);
$("bt-evals").onclick = verEvals;
$("overlay").onchange = desenharCurvas;
$("amostra").onchange = desenharCurvas;
poll();
setInterval(poll, 2000);
setInterval(() => { if (!ultimoNet) return;
  $("idade").textContent = idade((Date.now() - tNet) / 1000); }, 1000);
</script>
</body>
</html>
"""


# ------------------------------------------------------------------------------------------- main
def argumentos(argv=None):
    p = argparse.ArgumentParser(
        description="UI web local do experimento 09 (clicar para treinar + rede neural ao vivo). Só stdlib.",
        epilog="Ctrl+C fecha o servidor e mata os subprocessos que ele lançou (treino e sonda).")
    p.add_argument("--host", default="127.0.0.1", help="interface (default: 127.0.0.1 — só local)")
    p.add_argument("--port", type=int, default=0, help="porta TCP (default: 0 = o SO escolhe uma livre)")
    p.add_argument("--out", default=str(OUT_PADRAO),
                   help=f"pasta dos runs (default: {OUT_PADRAO}); descobre <out>/<run> e <out>/runs/<run>")
    p.add_argument("--net-out", default=str(NET_PADRAO),
                   help=f"JSONL da sonda da rede (default: {NET_PADRAO})")
    p.add_argument("--vento-out", default=str(CONTROLO_PADRAO),
                   help="ficheiro de controlo de vento ao vivo: o painel «VENTO» escreve-o e o net_probe.py "
                        f"vigia-o a cada passo de decisão (default: {CONTROLO_PADRAO})")
    p.add_argument("--train-py", default=str(TRAIN_PY),
                   help="script de treino lançado pelo botão ▶ (default: train.py desta pasta)")
    p.add_argument("--verboso", action="store_true", help="escreve os pedidos HTTP no stderr")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = argumentos(argv)
    estado = Estado(out_dir=Path(args.out).expanduser().resolve(),
                    net_jsonl=Path(args.net_out).expanduser().resolve(),
                    train_py=Path(args.train_py).expanduser().resolve(),
                    controlo_vento=Path(args.vento_out).expanduser().resolve())
    estado.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        servidor = Servidor((args.host, args.port), estado, verboso=args.verboso)
    except OSError as erro:                                  # porta ocupada, sem permissão, host inválido…
        if erro.errno == errno.EADDRINUSE:
            print(f"[ERRO] porta {args.port} já em uso", file=sys.stderr, flush=True)
        else:
            print(f"[ERRO] não consegui abrir {args.host}:{args.port}: {erro.strerror or erro}",
                  file=sys.stderr, flush=True)
        return 2
    porta = servidor.server_address[1]
    print(f"dashboard: http://{args.host}:{porta}/  · out={estado.out_dir} · net={estado.net_jsonl}", flush=True)
    print(f"dashboard: controlo de vento={estado.controlo_vento} · "
          f"treinador {estado.train_py.name} "
          f"{'presente' if estado.train_py.is_file() else 'EM FALTA (integração de treino pendente)'}"
          f" · net_probe.py {'presente' if PROBE_PY.is_file() else 'EM FALTA'}", flush=True)

    def _parar(_sinal, _frame):
        threading.Thread(target=servidor.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _parar)
    signal.signal(signal.SIGTERM, _parar)
    try:
        servidor.serve_forever(poll_interval=0.4)
    finally:
        estado.encerrar()
        servidor.server_close()
        print("dashboard: fechado (subprocessos terminados)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
