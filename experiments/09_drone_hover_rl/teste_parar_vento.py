#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_parar_vento.py — PROVA do PARAR: nenhuma rajada sobrevive ao clique.

O dono relatou: «podemos mandar rajadas mas na hora de parar só paramos a última». O mecanismo REAL (medido,
não suposto) é este:

  · existe UM só slot de rajada dirigida (`Controlo.rajada`): cada `rajada_agora` SUBSTITUI a anterior, logo
    «várias rajadas em simultâneo» nunca existiu — o que continuava a atuar depois do PARAR eram (i) as
    rajadas dos MODOS CONTÍNUOS (`rajadas`/`aleatoria`/`dryden`, que o env gera sozinho) e (ii) a rajada
    one-shot que estava a meio: o botão **PARAR VENTO** só fazia `POST /api/vento {vel: 0}`, que escreve o
    vento BASE e **não toca no bloco `dinamico`** — o runner continuava a escrever o envelope em
    `model.opt.wind` e a telemetria continuava a mostrar `vento_modo = rajada_agora|rajadas|...`;
  · além disso, o PARAR DINÂMICO deixava estado no env (`_rajada_k`/`_rajada_n`/`_rajada_vec`/`_turb`) e o
    restauro do vento base usava o registo ANTERIOR do controlo (um PARAR que também mexe no vento escrevia
    a base velha em `opt.wind`).

Este script corre o ciclo REAL do runner (`sim_view.correr`, com uma política de ação nula — não precisa de
nenhum modelo), escreve os comandos pela MESMA via do servidor (`sim_site.validar_vento`/
`validar_vento_dinamico`/`validar_parar` + `escrever_controlo`, com o `seq` a subir) e verifica, DEPOIS do
PARAR:

  (a) não resta nenhuma rajada ativa nem pendente — slot do runner, estado do env (`_rajada_*`, `_turb`,
      `_frente_*`), modo dinâmico e vento base do env (nada de restauros por fazer);
  (b) o vento aplicado (`model.opt.wind`) é EXATAMENTE o vento base comandado (0 m/s no PARAR VENTO), no
      passo e em todas as amostras da telemetria;
  (c) a telemetria não mostra mais envelope de rajada depois do PARAR (`vento_modo == "nenhum"` e
      `vento_vec` == base em todas as amostras seguintes).

O PARAR é testado em qualquer ponto do ciclo (início/meio/fim da rajada), com mistura de `rajada_agora` e
modos contínuos, e com os dois botões: PARAR DINÂMICO (`modo: nenhum`) e PARAR VENTO (`POST /api/parar`, que
além de desligar a dinâmica põe o vento base a 0).

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_parar_vento.py
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_parar_vento.py --http --navegador
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_parar_vento.py --mutacao
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_parar_vento.py --legado   # FALHA (bug)

COCKPIT (contrato r13, 2026-10-12) — o PARAR que o dono tem hoje. O painel de vento antigo (18 botões, 8
campos) saiu do site; o vento são TRÊS botões (`POST /api/vento-simples {ligado, intensidade, aleatorio,
direcao}`, gerador `vento_natural.py`) e pára-se pelo interruptor VENTO / tecla V (`{ligado: false}`) ou por
`POST /api/parar` (desliga os dois contratos). A garantia é a mesma — nenhuma rajada sobrevive —, medida
agora também para esse vento:

  · ao nível do runner (`CENARIOS_SIMPLES`): depois da paragem a rajada, a turbulência e a deriva de direção
    do gerador morrem NO PASSO SEGUINTE (o vetor passa a ser `w·[cos d, sin d, 0]` exato), a intensidade só
    DESCE pela rampa de 1.ª ordem (τ = 0,6 s) — conferida amostra a amostra pela fórmula fechada
    `|v_j| = |v_i|·e^(−Δk·Δt/τ)` — e passa a zero EXATO quando ela cai abaixo do resíduo; o vento do
    contrato antigo que estivesse por baixo NÃO volta; e, se o contrato antigo retomar a autoridade com os
    3 botões a soprar, desligá-los a seguir não faz reaparecer vento nenhum (o «vento fantasma» medido a
    2026-10-12: a rampa congelada do gerador voltava a 4,84 m/s — `correr_cenario_autoridade`);
  · `--http`: as duas paragens pelo servidor real;
  · `--navegador`: o COCKPIT real num Chrome headless — o envio do slider da intensidade (pendente no
    emissor, e largado DEPOIS da paragem) não ressuscita o vento, nem quando quem pára é OUTRO cliente; e o
    interruptor adota o que o servidor diz quando outro cliente liga o vento;
  · `--mutacao`: cada garantia do backend e cada defesa do front desligada (em CÓPIAS em `$TMPDIR`: as
    fontes pelo `--fontes`, o site compilado à parte) tem de fazer falhar os cenários dela.

O que SAIU com o painel antigo (a decisão é do dono: «três botões» e «não quero opções»), um ponto cada:
  · a matriz `--navegador` dos botões PARAR VENTO / PARAR DINÂMICO / toggle PARADO × a corrida do debounce
    de 300 ms do `campo-rajadas-p` — esses controlos foram apagados (`controlos.tsx`); substitui-a a matriz
    do cockpit (interruptor / tecla V × o envio pendente do slider), aqui mesmo;
  · a paragem por uma 2.ª ABA real e o aviso «outra aba» (`BroadcastChannel`) — o cockpit não tem canal
    entre abas: outra aba é só mais um cliente HTTP, coberto pelo POST cru que o interruptor dela mandaria;
  · as mutações `sem-revalidacao` / `sem-desbloqueio-remoto` de `lib/paragem.ts` (defesas do live-apply do
    painel antigo, que o cockpit não usa) — substituem-nas as três mutações de `lib/cockpit.ts`;
  · `--front DIR` e `--atraso-poll` (compilar o painel antigo na árvore / atrasar o poll do `/api/sim`) —
    substitui-os `--dist DIR` (servir outro bundle já compilado, sem tocar na árvore).
A lógica pura do painel novo (emissor «o último vence», corpos parciais, adoção) prova-se em
`site/testes/cockpit.mts`; o contrato do servidor/runner em `teste_cockpit.py` §1–§4.

Este script é também a prova de FIABILIDADE do PARAR:

  (1) **POSTs concorrentes → HTTP 500.** O servidor é `ThreadingHTTPServer` e o temporário da escrita
      atómica tinha o MESMO nome em todas as threads (`.{nome}.tmp{pid}`): dois POSTs simultâneos
      disputavam o ficheiro e o segundo `os.replace` rebentava com `FileNotFoundError` → 500 (e um PARAR
      que devolve 500 não para rajada nenhuma). A prova in-process corre SEMPRE (120 escritas simultâneas
      na mesma função do servidor; medido com o código de antes: 59 falhas e o contador de REINICIAR a
      perder incrementos — 0 falhas e contador exato com o de agora) e o `--http` acrescenta ~100 pares de
      POSTs concorrentes (`rajada_agora`/`nenhum`/`parar`/`reiniciar`/`loop`/`vento-simples`) contra o
      servidor REAL, com um leitor em paralelo a fazer `json.loads` ao ficheiro — 0 HTTP 500, 0 JSON
      partido, `loop`/`reiniciar` intactos, 0 `.tmp` órfãos;
  (2) **um envio atrasado do front religava o vento** (no painel antigo: o debounce de 300 ms do
      live-apply dos params). No cockpit o envio que pode chegar depois da paragem é o do slider da
      intensidade: `--navegador` arrasta-o (um envio fica pendente no emissor), pára pelo caminho do
      cenário (`PARAGENS`: interruptor VENTO, tecla V) 0/50/100/300 ms depois, larga o slider 150 ms
      DEPOIS da paragem e amostra o servidor durante 2,6 s; imprime os POSTs que o front mandou com o
      instante relativo à edição. Cada janela corre também SEM paragem (controlo positivo): aí a
      intensidade arrastada TEM de chegar ao servidor;
  (3) **paragens de OUTRO cliente (multi-cliente).** Um `POST /api/parar` cru (ou o `{ligado: false}` que o
      interruptor de outra aba manda) com o painel local a meio de um arrasto: o servidor fica parado e o
      painel adota-o. A defesa do cockpit é estrutural — o painel manda SÓ o que mudou —, e a mutação que
      o põe a mandar o estado inteiro faz o cenário falhar. O mesmo sítio tinha o **painel preso**; a
      versão do cockpit é o **interruptor desatualizado** (paragem local + religamento por outro cliente).

`--legado [REV]` materializa as fontes de `env.py`/`sim_view.py`/`sim_site.py` dessa revisão do git (padrão
`HEAD`, ou seja o código de antes da correção) e corre o MESMO teste contra elas — é a prova repetível do
bug, com um comando e sem tocar na árvore de trabalho. `--fontes DIR` faz o mesmo com uma pasta de fontes
(pode estar FORA do repo: é estagiada dentro da árvore e apagada no fim). Fontes de antes do r13 não têm o
vento dos 3 botões: os cenários dele são saltados com um aviso (`TEM_SIMPLES`).

Exit 0 = todas as checagens passam; 1 = alguma falha (diz qual e mostra o diagnóstico).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
SITE = _AQUI / "site"                       # o front (React + vite) que o sim_site.py serve de `site/dist`
# O ficheiro do front onde vivem as defesas do vento do cockpit (emissor «o último vence», corpos parciais,
# adoção do servidor): é o que a prova de mutação (`--mutacao`) adultera — numa CÓPIA, nunca na árvore.
FRONT_COCKPIT = "src/lib/cockpit.ts"


def _estagiar_fontes(origem: Path) -> Path:
    """Fontes alternativas DENTRO da árvore do laboratório (os módulos procuram o `pyproject.toml` acima).

    Uma pasta fora do repo (ex.: a cópia pré-fix em `$TMPDIR`) é copiada para `_AQUI/.fontes_antes/`, que é
    apagada no fim do processo — é o que permite guardar as fontes de antes em `$TMPDIR` e na mesma correr
    o teste contra elas.
    """
    if _RAIZ in origem.parents:
        return origem
    import atexit
    import shutil

    destino = _AQUI / ".fontes_antes"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    for nome in ("env.py", "sim_view.py", "sim_site.py"):
        shutil.copyfile(origem / nome, destino / nome)
    atexit.register(shutil.rmtree, destino, ignore_errors=True)
    print(f"[teste] fontes de {origem} estagiadas em {destino} (apagadas no fim)")
    return destino


def _pasta_fontes(argv: list[str]) -> Path | None:
    """Fontes alternativas pedidas na linha de comandos, ANTES dos imports (têm de vencer as da árvore).

    `--legado [REV]` (revisão do git, `HEAD` por omissão) materializa `env.py`/`sim_view.py`/`sim_site.py`
    dessa revisão numa pasta DENTRO da árvore do laboratório — os módulos procuram o `pyproject.toml` acima
    deles, logo uma pasta fora do repo não serve — e é apagada no fim do processo. É a prova do bug: o mesmo
    teste, com o código de antes da correção.
    """
    pedido = None
    for i, arg in enumerate(argv):
        if arg == "--legado":
            pedido = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else "HEAD"
        elif arg.startswith("--legado="):
            pedido = arg.split("=", 1)[1]
        elif arg == "--fontes" and i + 1 < len(argv):
            return _estagiar_fontes(Path(argv[i + 1]).expanduser().resolve())
        elif arg.startswith("--fontes="):
            return _estagiar_fontes(Path(arg.split("=", 1)[1]).expanduser().resolve())
    if pedido is None:
        return None
    import atexit
    import shutil

    pasta = _AQUI / ".fontes_legado"
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True)
    for nome in ("env.py", "sim_view.py", "sim_site.py"):
        fonte = f"{_REPO_RELATIVO}/{nome}"
        try:
            conteudo = subprocess.run(["git", "-C", str(_RAIZ), "show", f"{pedido}:{fonte}"],
                                      capture_output=True, check=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as erro:
            raise SystemExit(f"[teste] --legado {pedido}: não consegui ler {fonte} do git ({erro})") from erro
        (pasta / nome).write_bytes(conteudo)
    atexit.register(shutil.rmtree, pasta, ignore_errors=True)
    print(f"[teste] fontes do git {pedido} materializadas em {pasta} (apagadas no fim)")
    return pasta


_REPO_RELATIVO = _AQUI.relative_to(_RAIZ).as_posix()
# As fontes alternativas vêm PRIMEIRO: é o que permite correr este teste contra o código de uma revisão
# antiga sem tocar na árvore de trabalho. (A ordem do `insert(0, …)` é invertida, por isso a lista vai da
# MENOS para a MAIS prioritária.)
_FONTES = _pasta_fontes(sys.argv[1:])
for _caminho in (_RAIZ, _AQUI, _FONTES):
    if _caminho is not None:
        sys.path.insert(0, str(_caminho))

from lab import mjkit  # noqa: F401, I001  (define MUJOCO_GL=egl ANTES do `import mujoco`, como no sim_view)

import numpy as np

import env as modulo_env
import sim_site
import sim_view

try:                                        # o gerador do vento dos 3 botões (r13) — fontes antigas não o têm
    import vento_natural
except ImportError:                         # pragma: no cover  (só com `--legado` de antes do r13)
    vento_natural = None

BASE_PADRAO = {"vel": 3.0, "azimute": 90.0, "elevacao": 0.0}     # vento base dos cenários (m/s, graus)
BASE_ZERO = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0}
NENHUM = {"modo": "nenhum", "ativo": False}
TOL = 1e-12                       # tolerância da física (`opt.wind` vs vento base comandado, em memória)
TOL_TELE = 2e-6                   # a telemetria arredonda a 6 casas: 1e-6 + folga de arredondamento
TOL_RAMPA = 5e-6                  # norma de um vetor arredondado a 6 casas, prevista a partir de outra igual
TOL_APOS_CLIQUE_MS = 50           # folga do «POST depois da paragem» (um envio que já ia em voo)
PARAR_ATOMICO = hasattr(sim_site, "validar_parar")   # rota nova; sem ela emula-se o PARAR VENTO antigo
# r13: o vento dos 3 botões (`POST /api/vento-simples` + gerador). Fontes de antes do r13 não o têm.
TEM_SIMPLES = hasattr(sim_site, "validar_vento_simples") and vento_natural is not None

# As DUAS paragens do cockpit (r13) — as duas mandam `POST /api/vento-simples {ligado: false}`:
#   · "interruptor" — o interruptor VENTO da janela Vento (`data-testid="vento-ligado"`);
#   · "tecla_v"     — a tecla V (o mesmo controlo, sem abrir janela nenhuma).
PARAGENS = ("interruptor", "tecla_v")
ROTULO_PARAGEM = {"interruptor": "interruptor VENTO", "tecla_v": "tecla V"}
# Todos os modos dinâmicos do contrato antigo: se a telemetria acabar num destes, a física faz dinâmica.
MODOS_DINAMICOS = ("rajadas", "aleatoria", "dryden", "rajada_agora", "frente")
# Prova `--http` (esperas pelo relógio do RUNNER — amostras de telemetria —, com um teto de parede largo):
ESPERA_HTTP_S = 60.0              # teto de parede de cada espera (a máquina pode estar ocupada)
ATRASO_MAX_AMOSTRAS = 3           # a paragem tem de estar na física até à 3.ª amostra (~0,3 s) depois do 200
AMOSTRAS_PARADO = 12              # amostras seguidas LIMPAS exigidas depois da paragem (~1,2 s de telemetria)
# Prova `--navegador` (tempos de parede do browser):
LARGAR_MS = 150                   # o slider é largado 150 ms DEPOIS da paragem (o envio final do gesto)
ADOCAO_MS = 8000                  # o painel adota o servidor em ≤ 1,5 s de carência + a sondagem de 1 Hz
ZERO_MS = 40000                   # teto para a rampa de desligar (≈ 5 s de simulação) chegar a zero


# ---------------------------------------------------------------------------------------------- utilidades
def vetor_base(corpo: dict) -> np.ndarray:
    """Vector (m/s, mundo) do vento BASE comandado (convenção polar do `env.definir_vento`)."""
    if not corpo.get("ativo", True):
        return np.zeros(3)
    vel, azim, elev = float(corpo["vel"]), float(corpo["azimute"]), float(corpo["elevacao"])
    r = np.radians
    return np.array([vel * np.cos(r(elev)) * np.cos(r(azim)), vel * np.cos(r(elev)) * np.sin(r(azim)),
                     vel * np.sin(r(elev))])


def linhas_telemetria(caminho: Path) -> list[dict]:
    """Amostras VÁLIDAS da telemetria (ignora uma última linha a meio de uma escrita)."""
    try:
        texto = Path(caminho).read_text(encoding="utf-8")
    except OSError:
        return []
    linhas = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            linhas.append(json.loads(linha))
        except ValueError:
            continue
    return linhas


class PoliticaNula:
    """Política de ação nula (empuxo de hover): o teste não precisa de nenhum modelo treinado."""

    @staticmethod
    def predict(_obs, deterministic=True):  # assinatura do SB3
        return np.zeros(4, dtype=np.float32), None


class SondaNula:
    """Sonda sem hooks: só tem de responder ao que o `correr` lhe pede."""

    @staticmethod
    def escondidas():
        return np.zeros(64), np.zeros(64)

    @staticmethod
    def limpar():
        return None

    @staticmethod
    def fechar():
        return None


# ---------------------------------------------------------------------------------------------- banco de ensaio
class Banco:
    """O ciclo REAL do `sim_view.correr` numa thread + comandos escritos pela via do servidor."""

    def __init__(self, pasta: Path, fator_tempo: float = 2.0, max_segundos: float = 600.0) -> None:
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.controlo_caminho = self.pasta / "controle_vento.json"
        self.telemetria_caminho = self.pasta / "sim_telemetria.jsonl"
        for caminho in (self.controlo_caminho, self.telemetria_caminho):
            caminho.unlink(missing_ok=True)
        # `loop: false`: o teste não quer auto-resets a meio (o REINICIAR explícito é testado num cenário).
        sim_site.escrever_controlo(self.controlo_caminho, {**sim_site.CONTROLO_INICIAL, "loop": False})
        self.env = modulo_env.HoverEnv()
        self.controlo = sim_view.Controlo(self.controlo_caminho)
        self.telemetria = sim_view.Telemetria(self.telemetria_caminho, truncar=True)
        argv = ["--sem-janela", "--fator-tempo", f"{fator_tempo:g}", "--max-segundos", f"{max_segundos:g}"]
        # SEM os módulos de câmara (`--sem-fpv`): a prova é do VENTO. Este runner corre num fio que fica vivo
        # até ao fim do processo, e os fios de render das câmaras (EGL) apanhados a meio de um quadro pelo
        # `exit` rebentavam com SIGSEGV DEPOIS de o teste dizer «N/N OK» (medido: exit 139, `mjr_readPixels`
        # contra o fecho do EGL); de caminho, o stream deixa de se escrever em `out/fpv`, a pasta do dono.
        try:
            with contextlib.redirect_stderr(io.StringIO()):       # o argparse escreve o uso em stderr
                self.args = sim_view.analisar_argumentos([*argv, "--sem-fpv"])
        except SystemExit:                    # fontes de antes do módulo FPV (`--legado`): não há câmara
            self.args = sim_view.analisar_argumentos(argv)
        self.falha: list[str] = []
        self.thread = threading.Thread(target=self._correr, name="sim-view", daemon=True)

    def _correr(self) -> None:
        try:
            codigo = sim_view.correr(self.env, PoliticaNula(), self.controlo, self.telemetria, SondaNula(),
                                     self.args)
            if codigo != 0:
                self.falha.append(f"o ciclo do runner saiu com {codigo}")
        except BaseException as erro:  # noqa: BLE001  (uma falha no ciclo tem de aparecer no relatório)
            self.falha.append(f"{type(erro).__name__}: {erro}")

    def arrancar(self) -> None:
        self.thread.start()
        self.esperar(lambda: self.env.passos >= 2, 30.0, "o ciclo do runner arrancar")

    def parar(self) -> None:
        self.telemetria.fechar()

    # ------------------------------------------------------------------ comandos (pela via do servidor)
    def _escrever(self, novo: dict) -> None:
        """Escreve o controlo (atómico, como o site) e espera que o runner o APLIQUE (passo de decisão)."""
        antes = self.controlo.n_ventos
        sim_site.escrever_controlo(self.controlo_caminho, novo)
        self.esperar(lambda: self.controlo.n_ventos > antes, 30.0, "o runner aplicar o controlo")

    def comandar_vento(self, corpo: dict) -> dict:
        novo = sim_site.validar_vento(corpo, sim_site.ler_controlo(self.controlo_caminho))
        self._escrever(novo)
        return novo

    def comandar_dinamico(self, corpo: dict) -> dict:
        novo = sim_site.validar_vento_dinamico(corpo, sim_site.ler_controlo(self.controlo_caminho))
        self._escrever(novo)
        return novo

    def comandar_parar(self) -> dict:
        """PARAR VENTO: `POST /api/parar` (vento 0 + dinâmica off, atómico).

        Num código ANTIGO (sem a rota) emula exatamente o que o site fazia antes: `POST /api/vento
        {vel: 0}` — é justamente o que deixava as rajadas do modo contínuo (e a one-shot a meio) a atuar.
        """
        atual = sim_site.ler_controlo(self.controlo_caminho)
        if PARAR_ATOMICO:
            novo = sim_site.validar_parar(atual)
        else:
            novo = sim_site.validar_vento({"vel": 0.0, "azimute": atual.get("azimute", 0.0),
                                           "elevacao": atual.get("elevacao", 0.0)}, atual)
        self._escrever(novo)
        return novo

    def comandar_vento_simples(self, corpo: dict) -> dict:
        """`POST /api/vento-simples` (r13): os 3 botões — qualquer subconjunto, pela via do servidor."""
        novo = sim_site.validar_vento_simples(corpo, sim_site.ler_controlo(self.controlo_caminho))
        self._escrever(novo)
        return novo

    def comandar_reiniciar(self) -> dict:
        atual = sim_site.ler_controlo(self.controlo_caminho)
        novo = {**atual, "reiniciar": int(atual.get("reiniciar", 0) or 0) + 1}
        self._escrever(novo)
        return novo

    def limpar(self) -> None:
        """Estado limpo para o cenário seguinte: PARAR VENTO (o que houver) **e** dinâmica desligada."""
        self.comandar_parar()
        self.comandar_dinamico(dict(NENHUM))

    # ------------------------------------------------------------------ esperas
    def esperar(self, predicado, limite: float, o_que: str) -> None:
        """Espera (relógio) até `predicado()`; `SystemExit` claro se o limite estourar."""
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < limite:
            if self.falha:
                raise SystemExit(f"o ciclo do runner morreu: {self.falha[0]}")
            if predicado():
                return
            time.sleep(0.004)
        raise SystemExit(f"tempo esgotado à espera de {o_que}")

    def esperar_passos(self, n: int, limite: float = 90.0) -> None:
        """Deixa correr `n` passos de decisão (re-baseia se um REINICIAR puser o contador a 0)."""
        inicio = self.env.passos
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < limite:
            if self.falha:
                raise SystemExit(f"o ciclo do runner morreu: {self.falha[0]}")
            atual = self.env.passos
            if atual < inicio:                 # houve um REINICIAR: o `passo` voltou a 0
                inicio = atual
            elif atual >= inicio + n:
                return
            time.sleep(0.004)
        raise SystemExit(f"tempo esgotado à espera de {n} passos de decisão")

    # ------------------------------------------------------------------ leituras
    def residuos(self) -> dict:
        """Estado que NÃO pode sobreviver a um PARAR (slot do runner + estado do env + base em vigor)."""
        return {
            "rajada_runner": self.controlo.rajada,
            "rajada_concluida": self.controlo.rajada_concluida,
            "modo_pedido": None if self.controlo.dinamico is None else self.controlo.dinamico.modo,
            "modo_pedido_ativo": None if self.controlo.dinamico is None else self.controlo.dinamico.ativo,
            "modo_env": None if self.env.vento_dinamico is None else self.env.vento_dinamico["modo"],
            "env_rajada_k": self.env._rajada_k,
            "env_rajada_n": self.env._rajada_n,
            "env_rajada_vec": np.round(self.env._rajada_vec, 12).tolist(),
            "env_turb": np.round(self.env._turb, 12).tolist(),
            "env_frente_vec": np.round(self.env._frente_vec, 12).tolist(),
            "base_env": np.round(self.env._base_vento, 12).tolist(),
            "opt_wind": np.round(self.env.vento_atual, 12).tolist(),
        }

    def residuos_gerador(self) -> dict:
        """Estado do gerador do vento dos 3 botões (r13) que NÃO pode sobreviver a uma paragem."""
        g = self.controlo.gerador_vento
        return {"ligado": g.ligado, "em_rajada": g.em_rajada, "w": float(g._w),
                "turb": np.round(g._turb, 12).tolist(), "deriva": float(g._deriva),
                "vetor": np.round(g.vetor, 12).tolist()}


# ---------------------------------------------------------------------------------------------- cenários
@dataclass
class Cenario:
    """Um cenário: comandos enviados (com `seq` a subir) e em que ponto do ciclo se carrega no PARAR."""

    nome: str
    comandos: list[tuple]              # ("vento"|"dinamico"|"reiniciar"|"passos", corpo|None, n_passos)
    base: dict = field(default_factory=lambda: dict(BASE_PADRAO))
    fase: str = "meio"                 # inicio | meio | fim — fase da ÚLTIMA rajada quando o PARAR chega
    parar_vento: bool = False          # True = POST /api/parar (vento 0 + dinâmica off)
    rajada_fase: tuple | None = None   # (duração,) da última rajada one-shot, para medir a fase


def rajada(u: float = 5.0, azimute: float = 0.0, duracao: int = 300, elevacao: float = 0.0) -> dict:
    return {"modo": "rajada_agora", "ativo": True,
            "params": {"u": u, "azimute": azimute, "elevacao": elevacao, "duracao": duracao}}


def continuo(modo: str, **params) -> dict:
    return {"modo": modo, "ativo": True, "params": params}


CENARIOS = [
    # (1-3) três rajadas one-shot seguidas (seq a subir) e o PARAR em cada ponto do ciclo da última
    Cenario("PARAR DINAMICO no INICIO da 3.ª rajada (3 rajadas one-shot)",
            [("vento", BASE_PADRAO, 3), ("dinamico", rajada(duracao=40), 45),
             ("dinamico", rajada(duracao=40), 45), ("dinamico", rajada(duracao=300), 0)],
            fase="inicio", rajada_fase=(300,)),
    Cenario("PARAR DINAMICO no MEIO da 3.ª rajada (3 rajadas one-shot)",
            [("vento", BASE_PADRAO, 3), ("dinamico", rajada(duracao=40), 45),
             ("dinamico", rajada(duracao=40), 45), ("dinamico", rajada(duracao=300), 0)],
            fase="meio", rajada_fase=(300,)),
    Cenario("PARAR DINAMICO no FIM da 3.ª rajada (já concluída)",
            [("vento", BASE_PADRAO, 3), ("dinamico", rajada(duracao=40), 45),
             ("dinamico", rajada(duracao=40), 45), ("dinamico", rajada(duracao=40), 0)],
            fase="fim", rajada_fase=(40,)),
    # (4-8) mistura de rajada dirigida com os modos CONTÍNUOS (as rajadas «que continuam a atuar»)
    Cenario("RAJADAS contínuo + rajada one-shot + PARAR DINAMICO a meio",
            [("vento", BASE_PADRAO, 3),
             ("dinamico", continuo("rajadas", p=1.0, duracao=40, u_max=4.0), 60),
             ("dinamico", rajada(duracao=300), 0)],
            fase="meio", rajada_fase=(300,)),
    Cenario("ALEATORIA contínua + 2 rajadas one-shot + PARAR DINAMICO",
            [("vento", BASE_PADRAO, 3),
             ("dinamico", continuo("aleatoria", p=1.0, duracao=30), 40),
             ("dinamico", rajada(duracao=40), 45), ("dinamico", rajada(duracao=300), 0)],
            fase="meio", rajada_fase=(300,)),
    Cenario("DRYDEN + rajada one-shot + PARAR DINAMICO (limpa a turbulência)",
            [("vento", BASE_PADRAO, 3),
             ("dinamico", continuo("dryden", sigma=1.5, L=5.0, u_max=5.0, v_min=1.0), 60),
             ("dinamico", rajada(duracao=300), 0)],
            fase="meio", rajada_fase=(300,)),
    Cenario("FRENTE (degrau imediato) + rajada one-shot + PARAR DINAMICO (base fica no degrau)",
            [("vento", BASE_PADRAO, 3),
             ("dinamico", {"modo": "frente", "ativo": True,
                           "params": {"vel": 4.0, "azimute": 0.0, "elevacao": 0.0}}, 20),
             ("dinamico", rajada(duracao=300), 0)],
            base={"vel": 4.0, "azimute": 0.0, "elevacao": 0.0}, fase="meio", rajada_fase=(300,)),
    Cenario("FRENTE (modo do env: u_max/t_s) + rajada one-shot + PARAR DINAMICO",
            [("vento", BASE_PADRAO, 3),
             ("dinamico", continuo("frente", u_max=3.0, t_s=0.2), 40),
             ("dinamico", rajada(duracao=300), 0)],
            fase="meio", rajada_fase=(300,)),
    # (9-12) o PARAR VENTO (o botão que só mexia no vento base) tem de limpar TUDO e zerar o vento
    Cenario("PARAR VENTO a meio da 3.ª rajada one-shot (vento base -> 0)",
            [("vento", BASE_PADRAO, 3), ("dinamico", rajada(duracao=40), 45),
             ("dinamico", rajada(duracao=40), 45), ("dinamico", rajada(duracao=300), 0)],
            base=BASE_ZERO, fase="meio", rajada_fase=(300,), parar_vento=True),
    Cenario("PARAR VENTO no INICIO da rajada (vento base -> 0)",
            [("vento", BASE_PADRAO, 3), ("dinamico", rajada(duracao=300), 0)],
            base=BASE_ZERO, fase="inicio", rajada_fase=(300,), parar_vento=True),
    Cenario("PARAR VENTO com o modo RAJADAS contínuo ativo (vento base -> 0)",
            [("vento", BASE_PADRAO, 3),
             ("dinamico", continuo("rajadas", p=1.0, duracao=40, u_max=4.0), 60)],
            base=BASE_ZERO, fase="meio", parar_vento=True),
    Cenario("PARAR VENTO com DRYDEN ativo (vento base -> 0)",
            [("vento", BASE_PADRAO, 3),
             ("dinamico", continuo("dryden", sigma=1.5, L=5.0, u_max=5.0, v_min=1.0), 60)],
            base=BASE_ZERO, fase="meio", parar_vento=True),
    # (13-14) casos de borda: REINICIAR a meio (reset + reaplicar) e PARAR sem dinâmica nenhuma
    Cenario("REINICIAR a meio da rajada e só depois PARAR DINAMICO",
            [("vento", BASE_PADRAO, 3), ("dinamico", rajada(duracao=300), 20),
             ("reiniciar", None, 5)],
            fase="meio", rajada_fase=(300,)),
    Cenario("PARAR VENTO sem dinâmica nenhuma (idempotente, vento base -> 0)",
            [("vento", BASE_PADRAO, 3), ("passos", None, 10)],
            base=BASE_ZERO, fase="meio", parar_vento=True),
]


def correr_cenario(banco: Banco, cen: Cenario) -> dict:
    """Corre um cenário e devolve o relatório (com as checagens (a), (b) e (c) já avaliadas)."""
    banco.limpar()
    banco.comandar_vento(cen.base)
    banco.esperar_passos(3)
    for tipo, corpo, passos in cen.comandos:
        if tipo == "vento":
            banco.comandar_vento(corpo)
        elif tipo == "dinamico":
            banco.comandar_dinamico(corpo)
        elif tipo == "reiniciar":
            banco.comandar_reiniciar()
        if passos:
            banco.esperar_passos(passos)
    # ponto do ciclo em que o PARAR chega
    n = cen.rajada_fase[0] if cen.rajada_fase else 0
    if cen.fase == "inicio" and n:
        banco.esperar(lambda: banco.controlo.rajada is not None and banco.controlo.rajada["k"] >= 2,
                      15.0, "a rajada arrancar (k = 2)")
    elif cen.fase == "meio" and n:
        banco.esperar(lambda: banco.controlo.rajada is not None
                      and banco.controlo.rajada["k"] >= max(1, n // 2), 30.0,
                      f"a rajada chegar ao meio (k ≈ {n // 2})")
    elif cen.fase == "fim" and n:
        banco.esperar(lambda: banco.controlo.rajada is None, 30.0, "a rajada concluir o envelope")
    # ---- o PARAR (é este o objeto do teste)
    if cen.parar_vento:
        banco.comandar_parar()
    else:
        banco.comandar_dinamico(dict(NENHUM))
    linha_parar = len(linhas_telemetria(banco.telemetria_caminho))
    passo_parar = banco.env.passos
    # ---- e a física continua: nada pode voltar
    banco.esperar_passos(120, limite=90.0)
    amostras = linhas_telemetria(banco.telemetria_caminho)[linha_parar:]
    base = vetor_base(cen.base)
    residuos = banco.residuos()
    desvios = [float(np.linalg.norm(np.array(a["vento_vec"], dtype=float) - base)) for a in amostras
               if isinstance(a.get("vento_vec"), list)]
    modos = sorted({str(a.get("vento_modo")) for a in amostras})
    pior = max(desvios) if desvios else float("inf")
    # (a) nada ativo nem pendente
    checagens_a = {
        "slot da rajada vazio": residuos["rajada_runner"] is None,
        "nenhuma rajada pendente de re-arme": residuos["rajada_concluida"] is False,
        "modo pedido inativo": residuos["modo_pedido"] == "nenhum" and residuos["modo_pedido_ativo"] is False,
        "modo do env desligado": residuos["modo_env"] is None,
        "env sem rajada": (residuos["env_rajada_k"] == 0 and residuos["env_rajada_n"] == 0
                           and not any(residuos["env_rajada_vec"])),
        "env sem turbulência": not any(residuos["env_turb"]),
        "env sem frente": not any(residuos["env_frente_vec"]),
        "vento base do env == comandado (sem restauro pendente)":
            bool(np.allclose(residuos["base_env"], base, atol=TOL)),
    }
    # (b) vento aplicado == vento base comandado, no passo e em toda a telemetria
    checagens_b = {
        "opt.wind == vento base comandado (fim do cenário)":
            bool(np.allclose(banco.env.vento_atual, base, atol=TOL)),
        "vento_vec == base em todas as amostras depois do PARAR": bool(desvios) and pior <= TOL_TELE,
        "vento_vel == ‖base‖ em todas as amostras":
            all(abs(float(a.get("vento_vel", 0.0)) - float(np.linalg.norm(base))) <= TOL_TELE
                for a in amostras),
    }
    # (c) a telemetria não mostra mais envelope de rajada
    checagens_c = {
        "vento_modo == nenhum em todas as amostras depois do PARAR": modos == ["nenhum"],
        "há amostras de telemetria depois do PARAR": len(amostras) >= 3,
    }
    return {"nome": cen.nome, "checagens": {**checagens_a, **checagens_b, **checagens_c},
            "residuos": residuos, "modos": modos, "pior_desvio": pior, "amostras": len(amostras),
            "passo_parar": passo_parar, "base": np.round(base, 9).tolist()}


# ------------------------------------------------------------------ cenários do vento dos 3 botões (r13)
@dataclass
class CenarioSimples:
    """Um cenário do cockpit: o vento dos 3 botões a soprar e a paragem que o dono tem (r13)."""

    nome: str
    simples: dict                      # o bloco dos 3 botões, LIGADO, que vai ser parado
    antes: list[tuple] = field(default_factory=list)   # contrato antigo a soprar ANTES de os 3 botões mandarem
    parar: str = "desligar"            # desligar = POST /api/vento-simples {ligado:false} · parar = POST /api/parar
    a_meio_de_rajada: bool = False     # só pára quando o gerador tem uma rajada «1 − cos» em curso


CENARIOS_SIMPLES = [
    CenarioSimples("3 BOTOES constante 3 m/s @ 90 -> DESLIGAR (interruptor VENTO / tecla V)",
                   {"ligado": True, "intensidade": 3.0, "aleatorio": False, "direcao": 90.0}),
    CenarioSimples("3 BOTOES aleatorio 4 m/s @ 200 -> DESLIGAR a meio de uma RAJADA do gerador",
                   {"ligado": True, "intensidade": 4.0, "aleatorio": True, "direcao": 200.0},
                   a_meio_de_rajada=True),
    CenarioSimples("3 BOTOES aleatorio 5 m/s @ 45 -> PARAR VENTO (POST /api/parar) a meio de uma RAJADA",
                   {"ligado": True, "intensidade": 5.0, "aleatorio": True, "direcao": 45.0},
                   parar="parar", a_meio_de_rajada=True),
    CenarioSimples("contrato antigo a soprar (3 m/s + RAJADAS continuas) + 3 BOTOES por cima -> DESLIGAR "
                   "(o vento antigo NAO volta)",
                   {"ligado": True, "intensidade": 2.0, "aleatorio": True, "direcao": 0.0},
                   antes=[("vento", BASE_PADRAO, 3),
                          ("dinamico", continuo("rajadas", p=1.0, duracao=40, u_max=4.0), 40)]),
]


def correr_cenario_simples(banco: Banco, cen: CenarioSimples) -> dict:
    """Corre um cenário dos 3 botões e devolve o relatório, com as checagens (a), (b) e (c) já avaliadas.

    Depois da paragem o gerador ESQUECE a rajada, a turbulência e a deriva (o vetor passa a ser
    `w·[cos d, sin d, 0]` exato) e a intensidade desce pela rampa de 1.ª ordem até ao resíduo, onde passa a
    zero EXATO. Confere-se pela FÓRMULA FECHADA, amostra a amostra e pelo contador de passos da telemetria
    (não pelo relógio): entre duas amostras a `Δk` passos de decisão, `|v_j| = |v_i|·e^(−Δk·Δt/τ)` — uma
    rajada ou um resto de turbulência a somar-se partiam esta igualdade — e o zero aparece na 1.ª amostra em
    que a rampa prevista cai abaixo do resíduo (`t_zero = τ·ln(w/resíduo)` depois da paragem).
    """
    banco.limpar()
    banco.comandar_vento(BASE_ZERO)
    banco.esperar_passos(3)
    for tipo, corpo, passos in cen.antes:
        if tipo == "vento":
            banco.comandar_vento(corpo)
        elif tipo == "dinamico":
            banco.comandar_dinamico(corpo)
        if passos:
            banco.esperar_passos(passos)
    gerador = banco.controlo.gerador_vento
    dt = float(banco.env.dt_decisao)
    tau, residuo = float(vento_natural.TAU_RAMPA_S), float(vento_natural.RESIDUO)
    banco.comandar_vento_simples(cen.simples)                      # LIGAR: os 3 botões passam a mandar
    banco.esperar_passos(int(4.0 * tau / dt))                      # a rampa sobe (98 % ao fim de 4 τ)
    if cen.a_meio_de_rajada:
        banco.esperar(lambda: gerador.em_rajada, 120.0, "uma rajada do gerador dos 3 botões começar")
    rajada_no_parar = bool(gerador.em_rajada)
    w_antes = float(gerador._w)
    vento_antes = float(np.linalg.norm(banco.env.vento_atual))
    modo_antes = banco.controlo.modo_efetivo()
    # ---- a PARAGEM (é este o objeto do teste)
    if cen.parar == "parar":
        banco.comandar_parar()
    else:
        banco.comandar_vento_simples({"ligado": False})
    linha_parar = len(linhas_telemetria(banco.telemetria_caminho))
    t_zero = tau * float(np.log(max(w_antes, residuo) / residuo))  # fórmula fechada da rampa a descer
    banco.esperar_passos(int((t_zero + 1.5) / dt), limite=180.0)   # a rampa toda + 1,5 s já em zero
    amostras = linhas_telemetria(banco.telemetria_caminho)[linha_parar:]
    direcao = np.radians(float(cen.simples["direcao"]))
    eixo = np.array([np.cos(direcao), np.sin(direcao), 0.0])
    vetores = [np.array(a["vento_vec"], dtype=float) for a in amostras if isinstance(a.get("vento_vec"), list)]
    normas = [float(np.linalg.norm(v)) for v in vetores]
    fora_do_eixo = max((float(np.linalg.norm(v - n * eixo)) for v, n in zip(vetores, normas)), default=np.inf)
    modos = sorted({str(a.get("vento_modo")) for a in amostras})
    primeiro_zero = next((i for i, n in enumerate(normas) if n == 0.0), None)
    t_medido = (float(amostras[primeiro_zero]["t"]) - float(amostras[0]["t"])
                if primeiro_zero is not None else float("inf"))
    # a rampa pela fórmula fechada: cada amostra prevista a partir da anterior, pelo nº de passos entre elas
    passos = [int(a["passo"]) for a in amostras if isinstance(a.get("vento_vec"), list)]
    previstas = [n * float(np.exp(-(pj - pi) * dt / tau))
                 for n, pi, pj in zip(normas, passos, passos[1:])]         # previsão de normas[1:]
    vivas = [(obtida, prevista) for obtida, prevista in zip(normas[1:], previstas) if obtida > 0.0]
    erro_rampa = max((abs(obtida - prevista) for obtida, prevista in vivas), default=float("inf"))
    zero_na_hora = (primeiro_zero is not None and primeiro_zero >= 1
                    and previstas[primeiro_zero - 1] < residuo + TOL_RAMPA)
    residuos, ger = banco.residuos(), banco.residuos_gerador()
    # (a) nada ativo nem pendente — no gerador dos 3 botões, no slot do runner e no env
    checagens_a = {
        "gerador desligado, sem rajada, sem turbulência e sem deriva":
            ger["ligado"] is False and ger["em_rajada"] is False and not any(ger["turb"])
            and ger["deriva"] == 0.0,
        "gerador em zero EXATO (rampa acabada: w = 0 e vetor = 0)": ger["w"] == 0.0 and not any(ger["vetor"]),
        "slot da rajada do contrato antigo vazio": residuos["rajada_runner"] is None,
        "modo do env desligado e env sem rajada/turbulência/frente":
            residuos["modo_env"] is None and residuos["env_rajada_k"] == 0 and residuos["env_rajada_n"] == 0
            and not any(residuos["env_rajada_vec"]) and not any(residuos["env_turb"])
            and not any(residuos["env_frente_vec"]),
        "vento base do env == 0 (o vento antigo não voltou)": not any(residuos["base_env"]),
    }
    # (b) o vento que a física leva: só o da rampa, sempre a descer, até zero exato
    checagens_b = {
        "o cenário é válido: o vento soprava antes da paragem"
        + (" e havia uma rajada em curso" if cen.a_meio_de_rajada else ""):
            vento_antes > 0.5 and w_antes > 0.9 * float(cen.simples["intensidade"])
            and (rajada_no_parar or not cen.a_meio_de_rajada),
        "depois da paragem o vetor é w·[cos d, sin d, 0] em TODAS as amostras (sem rajada, turbulência, "
        "vertical nem deriva)": bool(vetores) and fora_do_eixo <= 2 * TOL_TELE,
        "a intensidade só DESCE (nenhuma amostra acima da anterior nem do valor de antes)":
            bool(normas) and normas[0] <= w_antes + TOL_TELE
            and all(b <= a + TOL_TELE for a, b in pairwise(normas)),
        "a rampa é a de 1.ª ordem EXATA: |v_j| = |v_i|·e^(−Δk·Δt/τ) entre TODAS as amostras (nada se soma)":
            len(vivas) >= 8 and erro_rampa <= TOL_RAMPA,
        "passa a zero EXATO quando a rampa prevista cai abaixo do resíduo, e FICA em zero":
            zero_na_hora and all(n == 0.0 for n in normas[primeiro_zero:])
            and len(normas) - primeiro_zero >= 3,
        "opt.wind == 0 (fim do cenário)": bool(np.allclose(banco.env.vento_atual, 0.0, atol=TOL)),
    }
    # (c) a telemetria não mostra mais o modo «natural» (nem nenhum modo dinâmico antigo)
    checagens_c = {
        "vento_modo == nenhum em todas as amostras depois da paragem": modos == ["nenhum"],
        "há amostras de telemetria ao longo da rampa": len(amostras) >= 10,
    }
    return {"nome": cen.nome, "checagens": {**checagens_a, **checagens_b, **checagens_c},
            "residuos": {**residuos, "gerador": ger}, "modos": modos, "amostras": len(amostras),
            "antes": f"{vento_antes:.3f} m/s (w = {w_antes:.3f}, modo {modo_antes}, rajada em curso = "
                     f"{rajada_no_parar})",
            "t_zero": t_zero, "t_medido": t_medido, "fora_do_eixo": float(fora_do_eixo),
            "erro_rampa": float(erro_rampa), "vivas": len(vivas)}


NOME_AUTORIDADE = ("3 BOTOES a soprar -> o contrato antigo retoma a autoridade (POST /api/vento) -> DESLIGAR "
                   "os 3 botoes (nenhum vento reaparece)")


def correr_cenario_autoridade(banco: Banco) -> dict:
    """O contrato antigo retoma a autoridade com os 3 botões a soprar e SÓ DEPOIS o dono os desliga.

    Defeito medido (2026-10-12, «vento fantasma»): um POST do contrato antigo tira o bloco `vento_simples`
    do controlo e daí em diante ninguém avança o gerador — o nível da rampa ficava CONGELADO no valor a que
    soprava. Quando o bloco voltava (mesmo com `ligado: false`: o dono a DESLIGAR), o 1.º passo escrevia
    esse nível velho: medido 4,84 m/s a aparecer do nada e a levar ~5 s a morrer. Corrigido no backend com
    o `VentoNatural.repor()`; a contraprova (`--mutacao`) repõe o código de antes e este cenário TEM de falhar.
    """
    banco.limpar()
    banco.comandar_vento(BASE_ZERO)
    banco.esperar_passos(3)
    gerador = banco.controlo.gerador_vento
    dt, tau = float(banco.env.dt_decisao), float(vento_natural.TAU_RAMPA_S)
    intensidade = 5.0
    banco.comandar_vento_simples({"ligado": True, "intensidade": intensidade, "aleatorio": False,
                                  "direcao": 0.0})
    banco.esperar_passos(int(4.0 * tau / dt))                      # os 3 botões a soprar (98 % ao fim de 4 τ)
    w_a_soprar = float(gerador._w)
    banco.comandar_vento(BASE_ZERO)                                # contrato antigo: vento 0, o bloco SAI
    banco.esperar_passos(25)
    vento_no_antigo = float(np.linalg.norm(banco.env.vento_atual))
    bloco_saiu = banco.controlo.vento_simples is None
    # ---- a PARAGEM: o dono desliga os 3 botões (o bloco volta ao ficheiro, desligado)
    banco.comandar_vento_simples({"ligado": False})
    linha_parar = len(linhas_telemetria(banco.telemetria_caminho))
    banco.esperar_passos(100, limite=90.0)
    amostras = linhas_telemetria(banco.telemetria_caminho)[linha_parar:]
    normas = [float(np.linalg.norm(np.array(a["vento_vec"], dtype=float))) for a in amostras
              if isinstance(a.get("vento_vec"), list)]
    modos = sorted({str(a.get("vento_modo")) for a in amostras})
    residuos, ger = banco.residuos(), banco.residuos_gerador()
    checagens = {
        "o cenário é válido: os 3 botões sopravam, o POST antigo tirou o bloco e o vento ficou a 0":
            w_a_soprar > 0.9 * intensidade and bloco_saiu and vento_no_antigo == 0.0,
        "DESLIGAR não faz reaparecer vento: TODAS as amostras a zero EXATO (a rampa velha não volta)":
            len(normas) >= 5 and max(normas) == 0.0,
        "gerador em zero EXATO, sem nada pendente (w = 0, vetor = 0, sem rajada/turbulência/deriva)":
            ger["w"] == 0.0 and not any(ger["vetor"]) and ger["em_rajada"] is False
            and not any(ger["turb"]) and ger["deriva"] == 0.0,
        "opt.wind == 0 e vento base do env == 0 (fim do cenário)":
            bool(np.allclose(banco.env.vento_atual, 0.0, atol=TOL)) and not any(residuos["base_env"]),
        "vento_modo == nenhum em todas as amostras depois da paragem": modos == ["nenhum"],
    }
    return {"nome": NOME_AUTORIDADE, "checagens": checagens, "residuos": {**residuos, "gerador": ger},
            "linha": f"os 3 botões sopravam {w_a_soprar:.3f} m/s · com o contrato antigo: {vento_no_antigo:.3f} "
                     f"m/s · depois de DESLIGAR: máx {max(normas, default=float('nan')):.3f} m/s em "
                     f"{len(normas)} amostras · modos = {modos}"}


# ---------------------------------------------------------------------------------------------- HTTP (ponta a ponta)
def _post(base_url: str, rota: str, corpo: dict | None = None) -> tuple[int, dict]:
    dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
    pedido = urllib.request.Request(base_url + rota, data=dados, method="POST",
                                    headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=10) as resposta:
            return resposta.status, json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        try:
            return erro.code, json.loads(erro.read().decode("utf-8"))
        except ValueError:
            return erro.code, {"erro": "<corpo não-JSON>"}


def _get(base_url: str, rota: str) -> dict:
    with urllib.request.urlopen(base_url + rota, timeout=10) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


# ------------------------------------------------------------------ defeito (1): POSTs concorrentes
def _tmp_orfaos(caminho: Path) -> list[str]:
    """Temporários da escrita atómica deixados para trás na pasta do controlo (tem de ser 0)."""
    return sorted(p.name for p in caminho.parent.glob(f".{caminho.name}.tmp*"))


def checa_concorrencia_inprocess(pasta: Path, escritas: int = 120) -> tuple[bool, list[str]]:
    """`escritas` escritas SIMULTÂNEAS na MESMA via do servidor (`sim_site.escrever_controlo`), sem HTTP.

    É a medida direta do defeito (1): com o temporário de nome partilhado (`tmp{pid}`), duas threads
    disputavam o mesmo ficheiro e o segundo `os.replace` rebentava com `FileNotFoundError` (medido: 44–56
    de 120 falhas); com o nome único por escrita, 0. Verifica também o JSON final, o merge de comandos e a
    ausência de `.tmp` órfãos. Corre SEMPRE (não precisa de servidor nem de modelo).
    """
    controlo = pasta / "inprocess_controle.json"
    controlo.unlink(missing_ok=True)
    sim_site.escrever_controlo(controlo, {**sim_site.CONTROLO_INICIAL, "loop": False, "reiniciar": 0})
    falhas: list[tuple[str, str]] = []
    trava = threading.Lock()
    # O REINICIAR é um ler-modificar-escrever: quem o faz tem de o fazer sob a trava do servidor
    # (`trava_controlo`), como os handlers do `sim_site.py` fazem. Sem ela, o incremento perde-se — e num
    # código antigo (sem `trava_controlo`) é mesmo isso que se mede.
    trava_controlo = getattr(sim_site, "trava_controlo", contextlib.nullcontext)

    def escrever(i: int) -> None:
        try:
            if i % 4 == 3:                                   # um REINICIAR concorrente com o vento
                with trava_controlo():
                    atual = sim_site.ler_controlo(controlo)
                    sim_site.escrever_controlo(controlo, {**atual,
                                                          "reiniciar": int(atual.get("reiniciar", 0) or 0) + 1})
            elif i % 2 == 0:
                sim_site.escrever_controlo(controlo, {"vel": 1.0, "ativo": True})
            else:
                sim_site.escrever_controlo(controlo, {"dinamico": {"modo": "nenhum", "params": {},
                                                                   "ativo": False, "seq": i}})
        except Exception as erro:  # noqa: BLE001  (é isto que o teste mede)
            with trava:
                falhas.append((type(erro).__name__, str(erro)))

    fios = [threading.Thread(target=escrever, args=(i,), name=f"escrita-{i}") for i in range(escritas)]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join()
    try:
        final = json.loads(controlo.read_text(encoding="utf-8"))
        json_ok = isinstance(final, dict)
    except ValueError as erro:
        final, json_ok = {}, False
        falhas.append(("JSON", f"ficheiro de controlo partido: {erro}"))
    orfaos = _tmp_orfaos(controlo)
    esperados = sum(1 for i in range(escritas) if i % 4 == 3)
    ok = (not falhas and json_ok and final.get("loop") is False
          and int(final.get("reiniciar", 0) or 0) == esperados and not orfaos
          and "vel" in final and isinstance(final.get("dinamico"), dict))
    relatorio = [(f"{escritas} escritas concorrentes na MESMA função do servidor: {len(falhas)} falhas · "
                  f"reiniciar={final.get('reiniciar')} (esperado {esperados}) · loop={final.get('loop')!r} · "
                  f"{len(orfaos)} .tmp órfãos")]
    if falhas:
        relatorio.append(f"primeiras falhas: {[f'{tipo}: {msg[:120]}' for tipo, msg in falhas[:3]]}")
    return ok, relatorio


def checa_concorrencia(base_url: str, controlo: Path, pares: int = 100) -> tuple[bool, list[str]]:
    """`pares` pares de POSTs SIMULTÂNEOS no servidor real: nenhum 500, nenhum JSON partido, comandos sãos.

    O defeito: o nome do temporário da escrita atómica era o MESMO para todas as threads
    (`.{nome}.tmp{pid}`), por isso dois POSTs simultâneos disputavam o ficheiro e o segundo `os.replace`
    rebentava com `FileNotFoundError` → **HTTP 500**. Um PARAR que devolve 500 não para rajada nenhuma.

    Aqui a mistura é `rajada_agora` · `nenhum` · `parar` · `reiniciar` · `loop` (+ `vento-simples`, a rota
    dos 3 botões do r13, quando as fontes a têm), dois a dois em barreira
    (mesmo instante), com um LEITOR em paralelo a fazer `json.loads` ao ficheiro a cada volta — é ele que
    prova que o ficheiro nunca aparece meio-escrito. No fim contam-se as escritas: o contador `reiniciar`
    tem de subir EXATAMENTE o número de POSTs de reinício (nenhum se perde) e o `loop` fica no que foi
    pedido — sem a trava do ler-modificar-escrever, um POST de vento revertia o incremento do outro.
    """
    relatorio: list[str] = []
    mistura = ("rajada", "nenhum", "parar", "reiniciar", "loop") + (("simples",) if TEM_SIMPLES else ())
    falhas: list[tuple[int, str]] = []
    trava = threading.Lock()

    def registar(codigo: int, detalhe: str) -> None:
        with trava:
            falhas.append((codigo, detalhe))

    def disparar(rota: str) -> None:
        try:
            if rota == "rajada":
                codigo, resposta = _post(base_url, "/api/vento-dinamico", rajada(duracao=200))
            elif rota == "nenhum":
                codigo, resposta = _post(base_url, "/api/vento-dinamico", dict(NENHUM))
            elif rota == "parar":
                codigo, resposta = _post(base_url, "/api/parar")
            elif rota == "reiniciar":
                codigo, resposta = _post(base_url, "/api/reiniciar")
            elif rota == "simples":
                codigo, resposta = _post(base_url, "/api/vento-simples", {"intensidade": 1.0})
            else:
                codigo, resposta = _post(base_url, "/api/loop", {"ativo": False})
        except Exception as erro:  # noqa: BLE001  (rede/JSON: conta como falha do pedido)
            registar(0, f"POST {rota}: {type(erro).__name__}: {erro}")
            return
        if codigo != 200:
            registar(codigo, f"POST {rota} -> HTTP {codigo} {resposta}")

    # estado de partida conhecido: `loop: false` (idempotente) e o contador de reinícios lido agora
    _post(base_url, "/api/loop", {"ativo": False})
    time.sleep(0.2)
    reiniciar_antes = int(sim_site.ler_controlo(controlo).get("reiniciar", 0) or 0)

    # leitor contínuo: prova que o ficheiro nunca é visto a meio (a escrita é um rename atómico)
    parar_leitura = threading.Event()
    leituras = {"n": 0}

    def leitor() -> None:
        while not parar_leitura.is_set():
            try:
                json.loads(controlo.read_text(encoding="utf-8"))
                leituras["n"] += 1
            except FileNotFoundError:
                pass
            except ValueError as erro:
                registar(0, f"JSON partido no controlo: {erro}")
            except OSError:
                pass

    fio_leitor = threading.Thread(target=leitor, name="leitor-controlo", daemon=True)
    fio_leitor.start()
    t0 = time.perf_counter()
    try:
        for i in range(pares):
            barreira = threading.Barrier(2)
            rotas = (mistura[i % len(mistura)], mistura[(i + 2) % len(mistura)])
            def em_par(rota: str, portao=barreira) -> None:
                portao.wait()                             # os dois pedidos do par saem no MESMO instante
                disparar(rota)

            fios = [threading.Thread(target=em_par, args=(rota,), name=f"post-{i}-{rota}") for rota in rotas]
            for fio in fios:
                fio.start()
            for fio in fios:
                fio.join()
    finally:
        parar_leitura.set()
        fio_leitor.join(timeout=5)
    duracao = time.perf_counter() - t0

    reiniciar_depois = int(sim_site.ler_controlo(controlo).get("reiniciar", 0) or 0)
    esperados_reiniciar = sum(1 for i in range(pares) for r in (mistura[i % len(mistura)],
                                                                mistura[(i + 2) % len(mistura)])
                              if r == "reiniciar")
    final = sim_site.ler_controlo(controlo)
    orfaos = _tmp_orfaos(controlo)
    erros500 = [d for c, d in falhas if c == 500]
    outros = [d for c, d in falhas if c != 500]
    modos_validos = getattr(sim_site, "MODOS_DINAMICOS", ("nenhum", "rajadas", "aleatoria", "frente",
                                                          "dryden", "rajada_agora"))
    contrato_ok = (isinstance(final.get("dinamico"), dict) and final["dinamico"].get("modo") in
                   modos_validos and isinstance(final.get("t"), float)
                   and "loop" in final and "reiniciar" in final)
    ok = (not falhas and reiniciar_depois - reiniciar_antes == esperados_reiniciar
          and final.get("loop") is False and not orfaos and contrato_ok and leituras["n"] > 50)
    relatorio.append(f"{pares} pares de POSTs concorrentes ({2 * pares} pedidos em {duracao:.1f} s): "
                     f"{len(erros500)} HTTP 500, {len(outros)} outros erros, {leituras['n']} leituras do "
                     f"ficheiro durante a tempestade, {len(orfaos)} .tmp órfãos")
    relatorio.append(f"comandos intactos: reiniciar {reiniciar_antes} -> {reiniciar_depois} "
                     f"(esperado +{esperados_reiniciar}) · loop={final.get('loop')!r} · "
                     f"dinamico={final.get('dinamico', {}).get('modo')!r}")
    if falhas:
        relatorio.append(f"primeiras falhas: {[d for _, d in falhas[:3]]}")
    return ok, relatorio


def _amostras_depois(telemetria: Path, linha: int, minimo: int, limite: float = ESPERA_HTTP_S) -> list[dict]:
    """Amostras de telemetria escritas DEPOIS da linha `linha` — espera até haver `minimo` (o relógio que
    conta é o do runner, que escreve ~10 amostras por segundo, não um `sleep` de parede)."""
    t0 = time.perf_counter()
    amostras = linhas_telemetria(telemetria)[linha:]
    while len(amostras) < minimo and time.perf_counter() - t0 < limite:
        time.sleep(0.1)
        amostras = linhas_telemetria(telemetria)[linha:]
    return amostras


def _esperar_estado(base_url: str, predicado, limite: float = ESPERA_HTTP_S) -> dict | None:
    """Sonda o `GET /api/state` até `predicado(estado)`; devolve o estado ou `None` (limite esgotado)."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < limite:
        estado = _get(base_url, "/api/state")
        if predicado(estado):
            return estado
        time.sleep(0.1)
    return None


def _limpas_desde(amostras: list[dict], limpa) -> tuple[int | None, list[dict]]:
    """`(i, amostras[i:])` da 1.ª amostra LIMPA (já com a paragem aplicada), ou `(None, [])`.

    Entre o `200` do POST e o passo de decisão em que o runner lê o ficheiro de controlo podem sair
    amostras ainda com o vento antigo (o runner vigia o ficheiro a cada passo; a telemetria sai a ~10 Hz).
    O invariante não é «zero amostras sujas», é o do dono: a paragem chega DEPRESSA (`ATRASO_MAX_AMOSTRAS`)
    e, uma vez limpa, NUNCA mais volta — quem chama exige as duas coisas.
    """
    primeiro = next((i for i, a in enumerate(amostras) if limpa(a)), None)
    return primeiro, ([] if primeiro is None else amostras[primeiro:])


def _checa_paragem_simples(base_url: str, telemetria: Path, rota: str, corpo: dict | None,
                           bloco: dict) -> tuple[bool, list[str]]:
    """r13: liga o vento dos 3 botões (com aleatoriedade), pára-o por `rota` e mede a paragem.

    Depois da paragem: `vento_modo` passa a `nenhum` e nunca mais é `natural`; o vento só DESCE (nenhuma
    rajada o volta a subir) na direção pedida, sem componente vertical (a turbulência acabou); chega a zero
    EXATO e fica em zero; e o bloco guardado fica `ligado: false` com as preferências intactas.
    """
    relatorio: list[str] = []
    codigo, resposta = _post(base_url, "/api/vento-simples", bloco)
    if codigo != 200:
        return False, [f"POST /api/vento-simples recusado ({codigo}): {resposta}"]
    soprar = _esperar_estado(base_url, lambda e: e["vento_atual"]["modo"] == "natural"
                             and float(e["vento_atual"]["vel"]) > 0.5 * bloco["intensidade"])
    if soprar is None:
        return False, [f"o vento dos 3 botões não chegou a soprar ({_get(base_url, '/api/state')['vento_atual']})"]
    relatorio.append(f"3 botões LIGADOS ({bloco['intensidade']:g} m/s @ {bloco['direcao']:g}°, aleatório): "
                     f"modo={soprar['vento_atual']['modo']} · vento em vigor={soprar['vento_atual']['vel']:.3f} m/s")
    codigo, resposta = _post(base_url, rota, corpo)
    if codigo != 200:
        return False, relatorio + [f"POST {rota} devolveu {codigo}: {resposta}"]
    linha_parar = len(linhas_telemetria(telemetria))
    # a rampa de desligar leva τ·ln(W/resíduo) ≈ 5 s de SIMULAÇÃO: espera-se pelo zero, não por um relógio
    parado = _esperar_estado(base_url, lambda e: float(e["vento_atual"]["vel"]) == 0.0, 4 * ESPERA_HTTP_S)
    amostras = _amostras_depois(telemetria, linha_parar, 0)
    amostras = _amostras_depois(telemetria, linha_parar, len(amostras) + AMOSTRAS_PARADO)
    primeiro, limpas = _limpas_desde(amostras, lambda a: a.get("vento_modo") == "nenhum")
    normas = [float(np.linalg.norm(a["vento_vec"])) for a in limpas]
    direcao = np.array([np.cos(np.radians(bloco["direcao"])), np.sin(np.radians(bloco["direcao"])), 0.0])
    fora = max((float(np.linalg.norm(np.array(a["vento_vec"], dtype=float) - n * direcao))
                for a, n in zip(limpas, normas)), default=float("inf"))
    desce = all(b <= a + TOL_TELE for a, b in pairwise(normas))
    zeros = [n for n in normas if n == 0.0]
    cauda_zero = bool(normas) and all(n == 0.0 for n in normas[-AMOSTRAS_PARADO:])
    estado = _get(base_url, "/api/sim")
    simples = estado.get("vento_simples") or {}
    ok = (parado is not None and primeiro is not None and primeiro <= ATRASO_MAX_AMOSTRAS
          and all(a.get("vento_modo") == "nenhum" for a in limpas) and desce and fora <= 2 * TOL_TELE
          and cauda_zero and simples.get("ligado") is False
          and simples.get("intensidade") == bloco["intensidade"] and simples.get("aleatorio") is True
          and simples.get("direcao") == bloco["direcao"]
          and float(estado["vento_atual"]["vel"]) == 0.0 and estado["vento_atual"]["modo"] == "nenhum")
    relatorio.append(f"depois de POST {rota}{'' if corpo is None else ' ' + json.dumps(corpo)}: {len(amostras)} "
                     f"amostras · limpa à {primeiro}.ª · modos={sorted({str(a.get('vento_modo')) for a in limpas})} "
                     f"· só desce={desce} ({normas[0] if normas else float('nan'):.3f} → "
                     f"{normas[-1] if normas else float('nan'):.3f} m/s) · desvio da direção pedida "
                     f"(turbulência/vertical)={fora:.2e} m/s · {len(zeros)} amostras em zero exato · "
                     f"guardado={simples}")
    if not ok:
        relatorio.append(f"a paragem do vento dos 3 botões por {rota} deixou vento/rajada a atuar")
    return ok, relatorio


def checa_http(pasta: Path, modelo: Path | None, fator_tempo: float) -> tuple[bool, list[str]]:
    """Ponta a ponta pelo SERVIDOR real (`sim_site.py` + runner + POSTs), como o site faz.

    Cobre o que o teste ao nível do runner não cobre: as rotas a passar pelo HTTP, com o `seq` a subir no
    ficheiro de controlo e o vento a chegar à física do runner — o PARAR do contrato antigo
    (`POST /api/parar`, `POST /api/vento-dinamico {nenhum}`) e as DUAS paragens do cockpit (r13):
    `POST /api/vento-simples {ligado: false}` (o interruptor VENTO / a tecla V) e o `POST /api/parar`.
    """
    relatorio: list[str] = []
    controlo, telemetria = pasta / "http_controle.json", pasta / "http_telemetria.jsonl"
    for caminho in (controlo, telemetria):
        caminho.unlink(missing_ok=True)
    comando = [sys.executable, str(_AQUI / "sim_site.py"), "--sem-browser", "--sem-janela", "--port", "0",
               "--controlo", str(controlo), "--telemetria", str(telemetria),
               "--fator-tempo", f"{fator_tempo:g}"]
    if modelo is not None:
        comando += ["--model", str(modelo)]
    processo = subprocess.Popen(comando, cwd=str(_AQUI), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, start_new_session=True)
    base_url = None
    try:
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 120:
            linha = processo.stdout.readline()
            if not linha:
                break
            achado = re.search(r"(http://[\d.]+:\d+/)", linha)
            if achado:
                base_url = achado.group(1).rstrip("/")
                break
        if base_url is None:
            return False, ["não consegui arrancar o sim_site.py (sem URL no stdout)"]
        # A porta responde ANTES de o runner (que ainda importa o torch e carrega o modelo) publicar a 1.ª
        # amostra: sem esta espera os POSTs caíam num simulador que ainda não corria e o «antes do PARAR»
        # era lido do ficheiro de controlo, não da física.
        arranque = _esperar_estado(base_url, lambda e: int(e.get("passo") or 0) > 0, 180.0)
        if arranque is None:
            return False, [f"servidor real em {base_url}, mas o runner não publicou telemetria em 180 s"]
        relatorio.append(f"servidor real em {base_url} · runner a correr (passo {arranque['passo']}, "
                         f"controlador {(arranque.get('controlador') or {}).get('modo')!r})")

        # 1) vento base 3 m/s @ 90 + 4 rajadas (3 dirigidas + 1 modo contínuo), com o seq a subir
        if _post(base_url, "/api/vento", {"vel": 3.0, "azimute": 90.0, "elevacao": 0.0})[0] != 200:
            return False, relatorio + ["POST /api/vento recusado"]
        for corpo in (rajada(duracao=400), rajada(duracao=400),
                      continuo("rajadas", p=1.0, duracao=50, u_max=4.0), rajada(duracao=400)):
            codigo, resposta = _post(base_url, "/api/vento-dinamico", corpo)
            if codigo != 200:
                return False, relatorio + [f"POST /api/vento-dinamico recusado ({codigo}): {resposta}"]
        # … e a rajada tem de estar MESMO a atuar na física (telemetria do runner) antes de se parar
        estado = _esperar_estado(base_url, lambda e: e["vento_atual"]["modo"] in MODOS_DINAMICOS
                                 and e["vento_atual"].get("fonte", "").startswith("telemetria"))
        pedido = sim_site.ler_controlo(controlo).get("dinamico", {})
        if estado is None:
            return False, relatorio + [(f"a rajada pedida (seq={pedido.get('seq')}) nunca chegou à física: "
                                        f"{_get(base_url, '/api/state')['vento_atual']}")]
        relatorio.append(f"antes do PARAR: modo={estado['vento_atual']['modo']} · vento em vigor="
                         f"{estado['vento_atual']['vel']:.3f} m/s ({estado['vento_atual'].get('fonte')}) · "
                         f"pedido={pedido.get('modo')} (seq={pedido.get('seq')})")

        # 2) PARAR VENTO pelo HTTP (uma rota, uma escrita atómica)
        codigo, corpo = _post(base_url, "/api/parar")
        if codigo != 200:
            return False, relatorio + [f"POST /api/parar devolveu {codigo}: {corpo}"]
        linha_parar = len(linhas_telemetria(telemetria))
        amostras = _amostras_depois(telemetria, linha_parar, ATRASO_MAX_AMOSTRAS + AMOSTRAS_PARADO)
        primeiro, limpas = _limpas_desde(
            amostras, lambda a: a.get("vento_modo") == "nenhum"
            and float(np.linalg.norm(np.array(a["vento_vec"], dtype=float))) <= TOL_TELE)
        estado = _get(base_url, "/api/sim")
        pior = max((float(np.linalg.norm(np.array(a["vento_vec"], dtype=float))) for a in limpas),
                   default=float("inf"))
        modos = sorted({str(a.get("vento_modo")) for a in limpas})
        ok = (primeiro is not None and primeiro <= ATRASO_MAX_AMOSTRAS and len(limpas) >= AMOSTRAS_PARADO
              and pior <= TOL_TELE and modos == ["nenhum"]
              and float(estado["vento"]["vel"]) == 0.0 and estado["vento"]["ativo"] is False
              and estado["vento_dinamico"]["modo"] == "nenhum"
              and estado["vento_dinamico"]["ativo"] is False
              and float(estado["vento_atual"]["vel"]) == 0.0 and estado["vento_atual"]["modo"] == "nenhum")
        relatorio.append(f"depois do PARAR VENTO: {len(amostras)} amostras · limpa à {primeiro}.ª · "
                         f"{len(limpas)} seguidas com modos={modos} · pior ‖vento_vec‖={pior:.3e} m/s · API "
                         f"vento={estado['vento']} · dinamico={estado['vento_dinamico']}")
        if not ok:
            return False, relatorio + ["o PARAR VENTO pelo HTTP deixou vento/rajada a atuar"]

        # 3) PARAR DINAMICO com vento base: o vento tem de voltar EXATAMENTE ao base comandado
        if _post(base_url, "/api/vento", {"vel": 3.0, "azimute": 90.0, "elevacao": 0.0})[0] != 200:
            return False, relatorio + ["POST /api/vento recusado (2.ª volta)"]
        if _post(base_url, "/api/vento-dinamico", rajada(u=5.0, duracao=400))[0] != 200:
            return False, relatorio + ["POST /api/vento-dinamico recusado (2.ª volta)"]
        if _esperar_estado(base_url, lambda e: e["vento_atual"]["modo"] == "rajada_agora") is None:
            return False, relatorio + ["a rajada da 2.ª volta nunca chegou à física"]
        if _post(base_url, "/api/vento-dinamico", {"modo": "nenhum", "ativo": False})[0] != 200:
            return False, relatorio + ["POST /api/vento-dinamico (nenhum) recusado"]
        linha_parar = len(linhas_telemetria(telemetria))
        amostras = _amostras_depois(telemetria, linha_parar, ATRASO_MAX_AMOSTRAS + AMOSTRAS_PARADO)
        base = np.array([0.0, 3.0, 0.0])
        primeiro, limpas = _limpas_desde(
            amostras, lambda a: a.get("vento_modo") == "nenhum"
            and float(np.linalg.norm(np.array(a["vento_vec"], dtype=float) - base)) <= TOL_TELE)
        pior = max((float(np.linalg.norm(np.array(a["vento_vec"], dtype=float) - base)) for a in limpas),
                   default=float("inf"))
        modos = sorted({str(a.get("vento_modo")) for a in limpas})
        estado = _get(base_url, "/api/sim")
        ok = (primeiro is not None and primeiro <= ATRASO_MAX_AMOSTRAS and len(limpas) >= AMOSTRAS_PARADO
              and pior <= TOL_TELE and modos == ["nenhum"]
              and abs(float(estado["vento_atual"]["vel"]) - 3.0) <= TOL_TELE)
        relatorio.append(f"depois do PARAR DINAMICO: {len(amostras)} amostras · limpa à {primeiro}.ª · "
                         f"{len(limpas)} seguidas com modos={modos} · pior desvio do vento base={pior:.3e} "
                         f"m/s · vento_atual={estado['vento_atual']}")
        if not ok:
            return False, relatorio + ["o PARAR DINAMICO pelo HTTP deixou vento/rajada a atuar"]

        # 4) r13 — as paragens do COCKPIT: o interruptor VENTO / tecla V e o PARAR (desliga os dois)
        if TEM_SIMPLES:
            for rota, corpo in (("/api/vento-simples", {"ligado": False}), ("/api/parar", None)):
                ok, linhas = _checa_paragem_simples(
                    base_url, telemetria, rota, corpo,
                    {"ligado": True, "intensidade": 3.0, "aleatorio": True, "direcao": 90.0})
                relatorio += linhas
                if not ok:
                    return False, relatorio
        else:
            relatorio.append("(estas fontes não têm o vento dos 3 botões: as paragens do cockpit não se medem)")

        # 5) DEFEITO (1): tempestade de POSTs concorrentes (500 / JSON partido / comandos perdidos)
        ok_conc, linhas = checa_concorrencia(base_url, controlo)
        relatorio += linhas
        return ok_conc, relatorio
    finally:
        try:
            os.killpg(os.getpgid(processo.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            processo.terminate()
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            processo.kill()


# ------------------------------------------------------------------ o COCKPIT (r13) num browser a sério
# Driver CDP mínimo (sem dependências: `WebSocket` global do Node ≥ 22 + o endpoint HTTP do Chrome). O
# trabalho todo acontece DENTRO da página servida pelo `sim_site.py` (o front real: o bundle de `site/dist`,
# ou o de `--dist`): abre a janela Vento pela tecla 3, clica no interruptor verdadeiro, arrasta o slider
# verdadeiro (setter nativo + evento `input`, que é o que o React escuta; `pointerup` = largar) e lê o
# estado pelo `GET /api/state` do próprio servidor. O «outro cliente» dos cenários multi-cliente é um
# `fetch` CRU à API (a referência guardada ANTES da instrumentação: não passa pelos controlos do cockpit
# nem entra na lista de POSTs do front).
_DRIVER_CDP = r'''
const [, , portaArg, urlBase, argsArg] = process.argv
const args = JSON.parse(argsArg)

async function listaAlvos() {
  return await (await fetch(`http://127.0.0.1:${portaArg}/json/list`)).json()
}

// Só serve um alvo que JÁ esteja no URL do site: o Chrome abre primeiro um `about:blank` e navega (ligar ao
// alvo errado dá «Execution context was destroyed» a meio da prova).
async function urlDoAlvo() {
  let vistos = []
  for (let i = 0; i < 200; i++) {
    try {
      vistos = await listaAlvos()
      const pagina = vistos.find((t) => t.type === "page" && String(t.url).startsWith(urlBase))
      if (pagina && pagina.webSocketDebuggerUrl) return pagina.webSocketDebuggerUrl
    } catch (erro) {
      /* a porta ainda não abriu */
    }
    await new Promise((r) => setTimeout(r, 100))
  }
  throw new Error(`não encontrei a página do site no Chrome (CDP): ${JSON.stringify(vistos)}`)
}

function ligar(url) {
  return new Promise((resolver, rejeitar) => {
    const ws = new WebSocket(url)
    const pendentes = new Map()
    let id = 0
    const comando = (method, params) => {
      id += 1
      const meu = id
      return new Promise((res, rej) => {
        pendentes.set(meu, { res, rej })
        ws.send(JSON.stringify({ id: meu, method, params: params || {} }))
      })
    }
    ws.addEventListener("open", () => resolver({ ws, comando }))
    ws.addEventListener("error", () => rejeitar(new Error("falha no WebSocket do CDP")))
    ws.addEventListener("message", (evento) => {
      const msg = JSON.parse(evento.data)
      const pendente = pendentes.get(msg.id)
      if (pendente) {
        pendentes.delete(msg.id)
        if (msg.error) pendente.rej(new Error(JSON.stringify(msg.error)))
        else pendente.res(msg.result)
      }
    })
  })
}

// Tudo o que se passa na página. Cada cenário: deixar o vento LIGADO e a soprar; ARRASTAR o slider da
// intensidade duas vezes seguidas (a 1.ª sai já, a 2.ª fica PENDENTE no emissor do painel — ≤ 10 Hz); esperar
// a janela pedida; PARAR (o interruptor, a tecla V, ou OUTRO cliente); largar o slider 150 ms DEPOIS (o
// envio final do gesto — o «apply atrasado» do cockpit); amostrar o servidor durante a janela.
const NA_PAGINA = async (args) => {
  const espera = (ms) => new Promise((r) => setTimeout(r, ms))
  const q = (id) => document.querySelector(`[data-testid="${id}"]`)
  const tecla = (tipo, key, code, keyCode) =>
    window.dispatchEvent(new KeyboardEvent(tipo, { key, code, keyCode, bubbles: true, cancelable: true }))
  const buscar = window.fetch.bind(window)     // a API CRUA: a amostragem e o «outro cliente»
  const envios = []                            // os POSTs que o FRONT manda (é aqui que se vê um apply atrasado)
  window.fetch = async (...a) => {
    const url = String(a[0])
    const opcoes = a[1] || {}
    if (url.includes("/api/") && String(opcoes.method || "GET").toUpperCase() === "POST") {
      envios.push({ t: performance.now(), url: url.slice(url.indexOf("/api/")), corpo: opcoes.body || null })
    }
    return buscar(...a)
  }
  const cru = async (rota, corpo) => {
    const resposta = await buscar(rota, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    })
    return resposta.status
  }
  const lerEstado = async () => {
    const resposta = await buscar("/api/state", { cache: "no-store" })
    if (!resposta.ok) throw new Error(`GET /api/state devolveu ${resposta.status}`)
    const j = await resposta.json()
    const simples = j.vento_simples || {}
    const atual = j.vento_atual || {}
    return {
      ligado: simples.ligado === undefined ? null : simples.ligado,
      intensidade: simples.intensidade === undefined ? null : simples.intensidade,
      vento_modo: atual.modo === undefined ? null : atual.modo,
      vento_vel: atual.vel === undefined ? null : atual.vel,
      antigo: (j.vento_dinamico || {}).modo || null,
    }
  }
  const esperar = async (predicado, limite, passo = 40) => {
    const t0 = performance.now()
    while (performance.now() - t0 < limite) {
      if (await predicado()) return true
      await espera(passo)
    }
    return false
  }
  // O painel como o DONO o vê: o interruptor, o valor do slider e os avisos (toasts).
  const painel = () => {
    const interruptor = q("vento-ligado")
    const slider = q("vento-intensidade")
    return {
      ligado: interruptor ? interruptor.getAttribute("data-ligado") === "sim" : null,
      intensidade: slider ? Number(slider.value) : null,
      avisos: Array.from(document.querySelectorAll('[aria-label="fechar aviso"]')).map((b) =>
        b.parentElement ? b.parentElement.textContent : ""
      ),
    }
  }
  const arrastar = (valor) => {
    const el = q("vento-intensidade")
    if (!el) throw new Error("o slider da intensidade não está no DOM")
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set
    setter.call(el, String(valor))
    el.dispatchEvent(new Event("input", { bubbles: true }))
  }
  const largar = () => {
    const el = q("vento-intensidade")
    if (el) el.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerId: 1 }))
  }
  const parar = async (tipo) => {
    if (tipo === "interruptor") q("vento-ligado").click()
    else if (tipo === "tecla_v") {
      tecla("keydown", "v", "KeyV", 86)
      tecla("keyup", "v", "KeyV", 86)
    } else if (tipo === "cru_parar") return await cru("/api/parar")
    else if (tipo === "cru_simples") return await cru("/api/vento-simples", { ligado: false })
    else throw new Error(`paragem desconhecida: ${tipo}`)
    return null
  }

  // ---- o cockpit pronto e a janela Vento aberta (tecla 3)
  if (!(await esperar(() => !!q("cockpit") && !!q("hud") && q("hud").getAttribute("data-vivo") === "sim",
                      args.prontidaoMs, 200)))
    throw new Error("o cockpit não ficou pronto: HUD sem ligação (site/dist desatualizado? runner parado?)")
  if (!q("janela-vento")) {
    tecla("keydown", "3", "Digit3", 51)
    tecla("keyup", "3", "Digit3", 51)
  }
  if (!(await esperar(() => !!q("vento-ligado") && !!q("vento-intensidade"), 15000)))
    throw new Error("a janela Vento não abriu com a tecla 3 (interruptor e slider fora do DOM)")
  const antigos = {
    pararVento: !!q("botao-parar-vento"),
    pararDinamico: !!q("botao-parar-dinamico"),
    modos: !!document.querySelector('[aria-label="modo dinâmico contínuo"]'),
  }

  // Deixa o vento LIGADO a `intensidade`, a soprar de facto, e o painel quieto (sem POST em voo nem
  // gesto recente: senão o cenário seguinte herdava envios do anterior).
  const assentar = async (intensidade) => {
    for (let tentativa = 0; tentativa < 3; tentativa++) {
      // o painel tem de mostrar o que o SERVIDOR tem (a adoção leva 1,5 s de carência + a sondagem de 1 Hz)
      await esperar(async () => painel().ligado === (await lerEstado()).ligado, 6000, 150)
      if (painel().ligado !== true) q("vento-ligado").click()
      arrastar(intensidade)
      largar()
      const ok = await esperar(async () => {
        const e = await lerEstado()
        return e.ligado === true && e.intensidade === intensidade && e.vento_vel !== null &&
          e.vento_vel > 0.6 * intensidade
      }, args.prontidaoMs, 100)
      await espera(450)                       // nenhum envio pendente do preparo (o emissor limita a 10 Hz)
      if (ok && painel().ligado === true) return true
    }
    return false
  }

  const resultados = []
  for (const cenario of args.cenarios) {
    const onde = cenario.nome
    if (!(await assentar(cenario.base))) {
      const estado = await lerEstado()
      throw new Error(`${onde}: não consegui deixar o vento LIGADO a ${cenario.base} m/s ` +
        `(servidor=${JSON.stringify(estado)}; painel=${JSON.stringify(painel())})`)
    }
    const saida = Object.assign({}, cenario, { antes: await lerEstado() })

    if (cenario.tipo === "desatualizado") {
      // paragem LOCAL + religamento por OUTRO cliente: o painel tem de ADOTAR o que o servidor diz e o
      // clique seguinte tem de fazer o que o dono VÊ (desligar), não o contrário
      q("vento-ligado").click()
      saida.paragemLocal = await esperar(async () => (await lerEstado()).ligado === false, 8000)
      saida.religamentoHttp = await cru("/api/vento-simples", { ligado: true, intensidade: cenario.religada })
      const tRelig = performance.now()
      saida.adotou = await esperar(() => {
        const p = painel()
        return p.ligado === true && p.intensidade === cenario.religada
      }, args.adocaoMs, 100)
      saida.adocaoMs = Math.round(performance.now() - tRelig)
      saida.painelAdotado = painel()
      const tEdicao = performance.now()
      arrastar(cenario.p)
      largar()
      saida.edicaoChegou = await esperar(async () => {
        const e = await lerEstado()
        return e.ligado === true && e.intensidade === cenario.p
      }, 8000)
      saida.depoisDaEdicao = await lerEstado()
      await espera(300)
      q("vento-ligado").click()               // o dono vê LIGADO e desliga
      saida.cliqueDesligou = await esperar(async () => (await lerEstado()).ligado === false, 8000)
      saida.fim = await lerEstado()
      saida.painelFim = painel()
      saida.envios = envios.filter((e) => e.t >= tEdicao - 50).map((e) =>
        Object.assign({}, e, { t: Math.round(e.t - tEdicao) }))
      resultados.push(saida)
      continue
    }

    // ---- o gesto: dois arrastos seguidos (o 2.º fica pendente no emissor) e a paragem na janela pedida
    arrastar(cenario.intermedia)
    arrastar(cenario.p)
    const tEdicao = performance.now()
    await espera(cenario.delta)
    if (cenario.paragem) saida.paragemHttp = await parar(cenario.paragem)
    const tParagem = performance.now()
    let largou = false
    const amostras = []
    while (performance.now() - tParagem < args.janelaMs) {
      if (!largou && performance.now() - tParagem >= args.largarMs) {
        largar()                              // o envio FINAL do slider chega DEPOIS da paragem
        largou = true
      }
      amostras.push(Object.assign({ t: Math.round(performance.now() - tParagem) }, await lerEstado()))
      await espera(50)
    }
    saida.esperaParagemMs = Math.round(tParagem - tEdicao)
    saida.amostras = amostras
    saida.painel = painel()
    if (cenario.paragem && cenario.externa) {
      // paragem de OUTRO cliente: o painel tem de acabar a dizer o que o servidor diz (DESLIGADO)
      saida.painelRefletiu = await esperar(() => painel().ligado === false, args.adocaoMs, 100)
      saida.adocaoMs = Math.round(performance.now() - tParagem)
      saida.painel = painel()
    }
    if (cenario.paragem && amostras.length > 0 && amostras[amostras.length - 1].ligado === false) {
      // a FÍSICA: o vento desce em rampa e chega a zero EXATO (o relógio é o do simulador: espera-se por
      // ele). Com o servidor ainda LIGADO no fim da janela o cenário já falhou: não há zero por que esperar.
      saida.chegouAZero = await esperar(async () => {
        const e = await lerEstado()
        amostras.push(Object.assign({ t: Math.round(performance.now() - tParagem) }, e))
        return e.ligado === false && e.vento_vel === 0
      }, args.zeroMs, 150)
      saida.zeroMs = Math.round(performance.now() - tParagem)
    }
    saida.fim = await lerEstado()
    saida.envios = envios
      .filter((e) => e.t >= tEdicao - 50)
      .map((e) => Object.assign({}, e, { t: Math.round(e.t - tEdicao) }))
    resultados.push(saida)
  }
  return { antigos: antigos, cenarios: resultados }
}

try {
  const alvo = await urlDoAlvo()
  const ligacao = await ligar(alvo)
  await ligacao.comando("Runtime.enable")
  const expressao = `(${NA_PAGINA.toString()})(${JSON.stringify(args)})`
  let resposta = null
  for (let tentativa = 1; tentativa <= 3; tentativa++) {
    try {
      resposta = await ligacao.comando("Runtime.evaluate", {
        expression: expressao,
        awaitPromise: true,
        returnByValue: true,
        timeout: args.tempoLimiteMs || 600000,
      })
      break
    } catch (erro) {
      const texto = String((erro && erro.message) || erro)
      if (tentativa === 3 || !/context|destroyed|navigat/i.test(texto)) throw erro
      await new Promise((r) => setTimeout(r, 500))
    }
  }
  ligacao.ws.close()
  if (resposta.exceptionDetails) {
    const detalhe = resposta.exceptionDetails.exception || {}
    throw new Error(`na página: ${detalhe.description || resposta.exceptionDetails.text}`)
  }
  process.stdout.write(JSON.stringify(resposta.result.value))
} catch (erro) {
  process.stderr.write(String((erro && erro.stack) || erro) + "\n")
  process.exit(2)
}
'''


def _binario(alternativas: tuple[str, ...]) -> str | None:
    """Primeiro executável disponível da lista (ou `None`)."""
    for nome in alternativas:
        achado = shutil.which(nome)
        if achado:
            return achado
    return None


def _esperar_devtools(perfil: Path, processo, limite: float) -> int | None:
    """Porta CDP que o Chrome escolheu (o ficheiro `DevToolsActivePort` do perfil), ou `None`."""
    t0 = time.perf_counter()
    ficheiro = perfil / "DevToolsActivePort"
    while time.perf_counter() - t0 < limite:
        if processo.poll() is not None:
            return None
        try:
            primeira = ficheiro.read_text(encoding="utf-8").splitlines()[0].strip()
            if primeira.isdigit():
                return int(primeira)
        except (OSError, IndexError, ValueError):
            pass
        time.sleep(0.1)
    return None


def _comando_do_site(dist: Path | None, argumentos: list[str]) -> list[str]:
    """Linha de comandos do `sim_site.py` — com o front de `dist` em vez do `site/dist` da árvore, se dado.

    Servir outro bundle NÃO toca na árvore: o servidor é o mesmo módulo, lançado por um `-c` que só lhe
    troca as duas constantes do sítio dos ficheiros estáticos (`DIST`/`INDEX`) antes do `main`. É o que
    deixa a prova de mutação compilar o front adulterado numa CÓPIA em `$TMPDIR` (o `site/` do dono, que
    pode estar a ser servido por outra sessão, nunca é reescrito).
    """
    if dist is None:
        return [sys.executable, str(_AQUI / "sim_site.py"), *argumentos]
    codigo = ("import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); import sim_site; "
              "sim_site.DIST = Path(sys.argv[2]); sim_site.INDEX = sim_site.DIST / 'index.html'; "
              "sys.exit(sim_site.main(sys.argv[3:]))")
    return [sys.executable, "-c", codigo, str(_FONTES or _AQUI), str(dist), *argumentos]


def _correr_no_cockpit(pasta: Path, nome: str, modelo: Path | None, fator_tempo: float, porta: int,
                       cenarios: list[dict], janela_ms: int, dist: Path | None) -> tuple[dict | None, list[str]]:
    """Servidor real + Chrome headless + driver: corre `cenarios` no cockpit e devolve `(dados, relatório)`.

    `dados` é `None` quando a prova não chegou a correr (o relatório diz porquê). O `--controlador` fica no
    padrão do site (`auto`): é o cockpit tal como o dono o abre, e o vento não depende de quem pilota.
    """
    relatorio: list[str] = []
    node = _binario(("node",))
    chrome = _binario(("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"))
    if node is None or chrome is None:
        return None, [f"esta prova precisa do node e do Chrome (node={node!r}, chrome={chrome!r})"]
    indice = (dist or SITE / "dist") / "index.html"
    if not indice.is_file():
        return None, [f"{indice} não existe — corra `npm run build` em {SITE}"]

    pasta.mkdir(parents=True, exist_ok=True)
    controlo, telemetria = pasta / f"{nome}_controle.json", pasta / f"{nome}_telemetria.jsonl"
    for caminho in (controlo, telemetria):
        caminho.unlink(missing_ok=True)
    driver = pasta / "driver_cockpit.mjs"
    driver.write_text(_DRIVER_CDP, encoding="utf-8")

    argumentos = ["--sem-browser", "--sem-janela", "--port", str(porta), "--controlo", str(controlo),
                  "--telemetria", str(telemetria), "--fator-tempo", f"{fator_tempo:g}"]
    if modelo is not None:
        argumentos += ["--model", str(modelo)]
    servidor = subprocess.Popen(_comando_do_site(dist, argumentos), cwd=str(_AQUI), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, start_new_session=True)
    navegador = None
    try:
        base_url = None
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 120:
            linha = servidor.stdout.readline()
            if not linha:
                break
            achado = re.search(r"(http://[\d.]+:\d+/)", linha)
            if achado:
                base_url = achado.group(1).rstrip("/")
                break
        if base_url is None:
            return None, [f"não consegui arrancar o sim_site.py na porta {porta} (porta ocupada?)"]
        relatorio.append(f"servidor real em {base_url} · front: {indice.parent} · controlo/telemetria em {pasta}")

        perfil = pasta / f"chrome-perfil-{nome}"
        shutil.rmtree(perfil, ignore_errors=True)
        navegador = subprocess.Popen(
            [chrome, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={perfil}",
             "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--disable-dev-shm-usage",
             "--window-size=1366,768", "--remote-allow-origins=*", base_url + "/"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        porta_cdp = _esperar_devtools(perfil, navegador, 30.0)
        if porta_cdp is None:
            return None, relatorio + ["o Chrome não abriu a porta de depuração (CDP)"]
        argumentos_driver = {"cenarios": cenarios, "janelaMs": int(janela_ms), "largarMs": LARGAR_MS,
                             "prontidaoMs": 90000, "adocaoMs": ADOCAO_MS, "zeroMs": ZERO_MS,
                             "tempoLimiteMs": 900000}
        try:
            resultado = subprocess.run([node, str(driver), str(porta_cdp), base_url,
                                        json.dumps(argumentos_driver)],
                                       capture_output=True, text=True, timeout=900, check=False)
        except subprocess.TimeoutExpired:
            return None, relatorio + ["o driver do navegador não terminou em 900 s"]
        if resultado.returncode != 0:
            return None, relatorio + [(f"o driver do navegador falhou ({resultado.returncode}):\n"
                                       f"{(resultado.stderr or resultado.stdout)[-2000:]}")]
        (pasta / f"{nome}_dados.json").write_text(resultado.stdout, encoding="utf-8")   # o diagnóstico cru
        return json.loads(resultado.stdout), relatorio
    finally:
        for processo in (navegador, servidor):
            if processo is None:
                continue
            try:
                os.killpg(os.getpgid(processo.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                processo.terminate()
            try:
                processo.wait(timeout=10)
            except subprocess.TimeoutExpired:
                processo.kill()


def _envio_liga(envio: dict) -> bool:
    """O POST registado no browser LIGA vento? (`/api/vento-simples` com `ligado: true`, ou qualquer POST
    aos endpoints do contrato antigo — o cockpit não os usa e eles tiravam a autoridade aos 3 botões)."""
    url = str(envio.get("url", ""))
    if url.startswith(("/api/vento-dinamico", "/api/vento")) and not url.startswith("/api/vento-simples"):
        return True
    if not url.startswith("/api/vento-simples"):
        return False
    try:
        corpo = json.loads(envio.get("corpo") or "{}")
    except (TypeError, ValueError):
        return False
    return corpo.get("ligado") is True


def _envio_desliga(envio: dict) -> bool:
    if not str(envio.get("url", "")).startswith("/api/vento-simples"):
        return False
    try:
        return json.loads(envio.get("corpo") or "{}").get("ligado") is False
    except (TypeError, ValueError):
        return False


def _avaliar_paragem(cenario: dict) -> tuple[str | None, str]:
    """`(falha | None, linha de relatório)` de um cenário de PARAGEM (local ou de outro cliente).

    O invariante, igual para todos os caminhos: (i) a paragem CHEGA ao servidor (há uma amostra com
    `vento_simples.ligado = false`); (ii) a partir daí NENHUMA amostra volta a `ligado = true`; (iii) nenhum
    POST que ligue vento SAI do front depois da paragem — o envio final do slider (largado 150 ms depois)
    leva só a intensidade; (iv) a edição não se perde (a intensidade do servidor é a do slider); (v) o vento
    que a física leva chega a zero EXATO (espera-se por ele: o relógio é o do simulador, com um teto de
    parede largo) e, do seu máximo em diante, só DESCE — o máximo pode vir uns instantes depois do `200`,
    enquanto o runner não lê o ficheiro de controlo; (vi) numa paragem de OUTRO cliente o painel acaba a
    mostrar DESLIGADO (adota o servidor).
    """
    nome, amostras, fim = cenario["nome"], cenario.get("amostras") or [], cenario.get("fim") or {}
    envios = cenario.get("envios") or []
    if not amostras:
        return f"{nome}: nenhuma amostra", f"· {nome}: nenhuma amostra"
    primeiro = next((i for i, a in enumerate(amostras) if a["ligado"] is False), None)
    voltou = primeiro is not None and any(a["ligado"] is not False for a in amostras[primeiro:])
    depois = [e for e in envios if e["t"] > cenario["esperaParagemMs"] + TOL_APOS_CLIQUE_MS]
    atrasados = [e for e in depois if _envio_liga(e)]
    velocidades = [float(a["vento_vel"]) for a in amostras[primeiro or 0:] if a["vento_vel"] is not None]
    pico = velocidades.index(max(velocidades)) if velocidades else 0
    subiu = any(b > a + 0.05 for a, b in pairwise(velocidades[pico:]))
    linha = (f"· {nome} · paragem aos {cenario['esperaParagemMs']} ms da edição · {len(amostras)} amostras · "
             f"servidor desligado aos {amostras[primeiro]['t'] if primeiro is not None else '—'} ms · fim: "
             f"ligado={fim.get('ligado')!r} intensidade={fim.get('intensidade')!r} (slider {cenario['p']}) "
             f"vento={fim.get('vento_vel')} m/s modo={fim.get('vento_modo')!r} · POSTs do front depois: "
             f"{[(e['t'], e['corpo']) for e in depois]}")
    if primeiro is None:
        return (f"{nome}: a paragem NUNCA chegou ao servidor (nenhuma amostra com `ligado: false`; "
                f"POSTs do front={[(e['t'], e['url'], e['corpo']) for e in envios]})"), linha
    if voltou or fim.get("ligado") is not False:
        return (f"{nome}: o vento VOLTOU a ligar depois da paragem "
                f"(amostras={[(a['t'], a['ligado']) for a in amostras[primeiro:primeiro + 14]]}, "
                f"POSTs do front depois={[(e['t'], e['corpo']) for e in depois]})"), linha
    if atrasados:
        return (f"{nome}: o front mandou um POST que LIGA vento depois da paragem "
                f"({[(e['t'], e['url'], e['corpo']) for e in atrasados]})"), linha
    if not cenario.get("externa") and not any(_envio_desliga(e) for e in envios):
        return f"{nome}: o painel não mandou `ligado: false` (POSTs={[(e['t'], e['corpo']) for e in envios]})", linha
    if fim.get("intensidade") is None or abs(float(fim["intensidade"]) - cenario["p"]) > 1e-9:
        return (f"{nome}: a edição perdeu-se — o slider ficou em {cenario['p']} m/s e o servidor em "
                f"{fim.get('intensidade')!r}"), linha
    if cenario.get("chegouAZero") is not True or fim.get("vento_vel") != 0:
        return (f"{nome}: o vento não chegou a zero em {ZERO_MS / 1000:g} s de parede "
                f"(fim: {fim.get('vento_vel')} m/s; velocidades={velocidades[::8][:14]})"), linha
    if subiu or fim.get("vento_modo") != "nenhum":
        return (f"{nome}: o vento voltou a SUBIR depois da paragem (modo={fim.get('vento_modo')!r}; "
                f"velocidades desde o máximo={velocidades[pico:][::4][:16]})"), linha
    if cenario.get("externa") and cenario.get("painelRefletiu") is not True:
        return (f"{nome}: o painel NÃO adotou a paragem de outro cliente em {ADOCAO_MS / 1000:g} s — continua a "
                f"mostrar {cenario.get('painel')}"), linha
    return None, linha + f" · zero exato aos {cenario.get('zeroMs')} ms" \
        + (f" · painel em DESLIGADO aos {cenario.get('adocaoMs')} ms" if cenario.get("externa") else "")


def cenarios_matriz(deltas: tuple[int, ...]) -> list[dict]:
    """A matriz do cockpit: cada janela × as DUAS paragens (interruptor, tecla V) + o controlo positivo."""
    cenarios, i = [], 0
    for delta in deltas:
        for paragem in (*PARAGENS, None):
            i += 1
            p = round(1.0 + 0.1 * i, 1)
            nome = (f"{ROTULO_PARAGEM[paragem]} {delta} ms depois de arrastar a intensidade" if paragem
                    else f"controlo SEM paragem (janela {delta} ms)")
            cenarios.append({"nome": nome, "tipo": "matriz", "delta": int(delta), "paragem": paragem,
                             "base": 3.0, "intermedia": round(p + 1.5, 1), "p": p, "externa": False})
    return cenarios


def checa_navegador(pasta: Path, modelo: Path | None, fator_tempo: float, deltas: tuple[int, ...],
                    porta: int = 8481, dist: Path | None = None) -> tuple[bool, list[str]]:
    """Ponta a ponta com o SERVIDOR real + o COCKPIT real num Chrome headless: o vento parado não volta.

    No cockpit (r13) o vento pára-se pelo interruptor VENTO da janela Vento ou pela tecla V — os dois mandam
    `POST /api/vento-simples {ligado: false}`. O que podia ressuscitá-lo é o envio do SLIDER da intensidade:
    arrastar manda no máximo a ~10 Hz (o resto fica PENDENTE no emissor do painel) e largar manda o valor
    final. Cada cenário arrasta o slider (deixando um envio pendente), espera a janela pedida
    (0/50/100/300 ms), pára pelo caminho do cenário e larga o slider 150 ms DEPOIS — ver `_avaliar_paragem`
    para o invariante. Cada janela corre também SEM paragem (o controlo positivo): aí a intensidade
    arrastada TEM de chegar ao servidor com o vento ligado, senão os cenários de paragem não estariam a
    testar envio nenhum.
    """
    cenarios = cenarios_matriz(deltas)
    dados, relatorio = _correr_no_cockpit(pasta, "nav", modelo, fator_tempo, porta, cenarios, 2600, dist)
    if dados is None:
        return False, relatorio
    falhas: list[str] = []
    antigos = dados.get("antigos") or {}
    relatorio.append(f"controlos do painel antigo no DOM: {antigos} (o cockpit não os tem)")
    if any(antigos.values()):
        falhas.append(f"o front servido ainda tem controlos do painel de vento antigo: {antigos}")
    for cenario in dados["cenarios"]:
        if cenario.get("paragem"):
            falha, linha = _avaliar_paragem(cenario)
        else:
            fim = cenario.get("fim") or {}
            ok = (fim.get("ligado") is True and fim.get("intensidade") is not None
                  and abs(float(fim["intensidade"]) - cenario["p"]) <= 1e-9)
            falha = None if ok else (f"{cenario['nome']}: a intensidade arrastada NÃO chegou ao servidor "
                                     f"(fim={fim}, slider {cenario['p']}) — os cenários de paragem não "
                                     f"estariam a testar envio nenhum")
            linha = (f"· {cenario['nome']} · fim: ligado={fim.get('ligado')!r} intensidade="
                     f"{fim.get('intensidade')!r} (slider {cenario['p']}) · POSTs do front: "
                     f"{[(e['t'], e['corpo']) for e in cenario.get('envios') or []]}")
        relatorio.append(linha)
        if falha:
            falhas.append(falha)
    for falha in falhas:
        relatorio.append(f"FALHOU: {falha}")
    return not falhas, relatorio


def cenarios_multicliente(quais: tuple[str, ...] = ()) -> list[dict]:
    """Cenários multi-cliente: paragem por OUTRO cliente (POST cru) e o interruptor desatualizado."""
    todos = [
        {"nome": "POST /api/parar cru (outro cliente) logo após arrastar", "tipo": "externa",
         "paragem": "cru_parar", "delta": 0, "p": 2.3},
        {"nome": "POST /api/parar cru 100 ms após arrastar", "tipo": "externa",
         "paragem": "cru_parar", "delta": 100, "p": 2.5},
        {"nome": "POST /api/vento-simples {ligado:false} cru (o que o interruptor de outra aba manda)",
         "tipo": "externa", "paragem": "cru_simples", "delta": 0, "p": 2.7},
        {"nome": "interruptor desatualizado: paragem LOCAL + religamento por outro cliente",
         "tipo": "desatualizado", "paragem": None, "delta": 0, "p": 2.9, "religada": 1.5},
    ]
    for cenario in todos:
        cenario.update({"base": 3.0, "intermedia": round(cenario["p"] + 1.5, 1),
                        "externa": cenario["tipo"] == "externa"})
    return [c for c in todos if not quais or c["tipo"] in quais]


def checa_multicliente(pasta: Path, modelo: Path | None, fator_tempo: float, porta: int = 8481,
                       quais: tuple[str, ...] = (), janela_ms: int = 2600,
                       dist: Path | None = None) -> tuple[bool, list[str]]:
    """Ponta a ponta com o SERVIDOR real + o COCKPIT real: paragens de OUTRO cliente e o interruptor desatualizado.

    (a) **paragem externa** (`POST /api/parar` cru, e `POST /api/vento-simples {ligado:false}` cru — o que o
        interruptor de outra aba manda): com o painel a meio de um arrasto (um envio pendente) e o slider
        largado 150 ms depois da paragem, o servidor fica `ligado: false` e NÃO volta a ligar em nenhuma
        amostra da janela; nenhum POST que ligue vento sai do front; e o painel acaba a mostrar DESLIGADO.
        A defesa do cockpit é mandar SÓ o que mudou (`{intensidade}`): o envio do slider nunca leva o
        `ligado` que o painel ainda julga em vigor.
    (b) **interruptor desatualizado**: paragem LOCAL + religamento por OUTRO cliente ⇒ o painel ADOTA o que
        o servidor diz (LIGADO, com a intensidade nova), uma edição local chega ao servidor e o clique
        seguinte DESLIGA (faz o que o dono vê). Sem a adoção o interruptor mentia: mostrava DESLIGADO com o
        vento a soprar e o clique «ligava» o que já estava ligado.

    A prova de não-tautologia corre-os com o front MUTADO (`--mutacao`).
    """
    cenarios = cenarios_multicliente(quais)
    if not cenarios:
        return True, ["nenhum cenário multi-cliente pedido"]
    dados, relatorio = _correr_no_cockpit(pasta, "multi", modelo, fator_tempo, porta, cenarios, janela_ms, dist)
    if dados is None:
        return False, relatorio
    falhas: list[str] = []
    for cenario in dados["cenarios"]:
        nome = cenario["nome"]
        if cenario["tipo"] == "externa":
            if cenario.get("paragemHttp") != 200:
                falha, linha = f"{nome}: a paragem do outro cliente devolveu HTTP {cenario.get('paragemHttp')}", f"· {nome}"
            else:
                falha, linha = _avaliar_paragem(cenario)
        else:
            fim, depois = cenario.get("fim") or {}, cenario.get("depoisDaEdicao") or {}
            linha = (f"· {nome} · paragem local={cenario.get('paragemLocal')} · religamento HTTP "
                     f"{cenario.get('religamentoHttp')} · painel adotou em {cenario.get('adocaoMs')} ms → "
                     f"{cenario.get('painelAdotado')} · edição p={cenario['p']} → servidor "
                     f"{depois.get('intensidade')!r} · clique final → ligado={fim.get('ligado')!r} · POSTs do "
                     f"front: {[(e['t'], e['corpo']) for e in cenario.get('envios') or []]}")
            falha = None
            if cenario.get("paragemLocal") is not True:
                falha = f"{nome}: a paragem LOCAL não chegou ao servidor"
            elif cenario.get("religamentoHttp") != 200:
                falha = f"{nome}: o religamento por outro cliente devolveu HTTP {cenario.get('religamentoHttp')}"
            elif cenario.get("adotou") is not True:
                falha = (f"{nome}: o INTERRUPTOR MENTE — o painel não adotou o vento religado por outro "
                         f"cliente em {ADOCAO_MS / 1000:g} s (painel={cenario.get('painelAdotado')}, servidor "
                         f"ligado a {cenario['religada']} m/s)")
            elif cenario.get("edicaoChegou") is not True:
                falha = (f"{nome}: a edição local (p={cenario['p']}) não chegou ao servidor "
                         f"(servidor={depois})")
            elif cenario.get("cliqueDesligou") is not True or fim.get("ligado") is not False:
                falha = (f"{nome}: o clique no interruptor (que mostrava LIGADO) não desligou o vento "
                         f"(servidor={fim}, painel={cenario.get('painelFim')})")
        relatorio.append(linha)
        if falha:
            falhas.append(falha)
    for falha in falhas:
        relatorio.append(f"FALHOU: {falha}")
    return not falhas, relatorio


# ------------------------------------------------------- prova de NÃO-TAUTOLOGIA (mutação do front)
# Uma prova nova pode estar verde por não medir nada. Aqui desliga-se UMA defesa de cada vez no front do
# cockpit (`site/src/lib/cockpit.ts`), compila-se o site e correm-se os MESMOS cenários: eles TÊM de FALHAR
# (o cenário que fica verde é o que não estava a medir a defesa). A troca é textual e CONFERIDA (se o texto
# já não existir, aborta em vez de fingir que mutou). O front mutado é compilado numa CÓPIA em `$TMPDIR`
# (`site/` sem `node_modules`, que entra por ligação simbólica) e servido de lá: a árvore não é tocada.
MUTACOES_FRONT = (
    ("estado-inteiro",
     "    if (final) this.emissor.largar(corpo)\n    else this.emissor.pedir(corpo)\n",
     ("    const inteiro = { ligado: this.valor.ligado, intensidade: this.valor.intensidade,\n"
      "      aleatorio: this.valor.aleatorio, direcao: this.valor.direcao }\n"
      "    if (final) this.emissor.largar(inteiro)\n    else this.emissor.pedir(inteiro)\n"),
     "multi", ("externa",),
     ("o painel passa a mandar o estado INTEIRO em vez de só o que mudou: o envio do slider leva o `ligado: "
      "true` que o painel ainda julga em vigor e ressuscita o vento que OUTRO cliente parou")),
    ("sem-adocao",
     "      v.conhecido &&\n      v.ligado === bloco.ligado &&\n",
     "      v.conhecido ||\n      v.ligado === bloco.ligado &&\n",
     "multi", ("desatualizado",),
     ("o painel deixa de adotar o que o servidor diz depois da 1.ª leitura: o interruptor fica a mentir "
      "quando outro cliente liga o vento")),
    ("fundir-perde-o-ultimo",
     "      fundir: (pendente, novo) => ({ ...pendente, ...novo }),\n",
     "      fundir: (pendente) => pendente,\n",
     "matriz", (0, 50),
     ("o emissor do painel deixa cair o gesto MAIS RECENTE quando há um envio pendente: o `ligado: false` "
      "da paragem perde-se atrás da intensidade arrastada")),
)


def construir_front(destino: Path, mutacao: tuple | None = None) -> tuple[Path | None, str]:
    """Compila o front numa CÓPIA (`destino/site`) — adulterado por `mutacao` se dada. `(dist | None, saída)`.

    Copia `site/` sem `node_modules` nem `dist` (o `node_modules` entra por ligação simbólica) e corre o
    `vite build` da cópia (sem o `tsc -b`: uma mutação não tem de passar no verificador de tipos para o
    bundle existir). A árvore de trabalho não é tocada.
    """
    vite = SITE / "node_modules" / ".bin" / "vite"
    if not vite.is_file():
        return None, f"{vite} não existe — corra `npm install` em {SITE}"
    copia = destino / "site"
    shutil.rmtree(destino, ignore_errors=True)
    shutil.copytree(SITE, copia, ignore=shutil.ignore_patterns("node_modules", "dist", ".vite*"))
    (copia / "node_modules").symlink_to(SITE / "node_modules", target_is_directory=True)
    if mutacao is not None:
        _nome, alvo, troca = mutacao[:3]
        fonte = copia / FRONT_COCKPIT
        conteudo = fonte.read_text(encoding="utf-8")
        if conteudo.count(alvo) != 1:
            raise SystemExit(f"[teste] mutação impossível: o texto {alvo!r} aparece {conteudo.count(alvo)}x em "
                             f"{FRONT_COCKPIT} (o front mudou? atualize MUTACOES_FRONT)")
        fonte.write_text(conteudo.replace(alvo, troca, 1), encoding="utf-8")
    feito = subprocess.run([str(copia / "node_modules" / ".bin" / "vite"), "build", "--configLoader", "runner"],
                           cwd=str(copia), capture_output=True, text=True, timeout=600, check=False)
    saida = (feito.stdout or "") + (feito.stderr or "")
    dist = copia / "dist"
    if feito.returncode != 0 or not (dist / "index.html").is_file():
        return None, saida
    return dist, saida


def prova_mutacao(pasta: Path, modelo: Path, fator_tempo: float, porta: int,
                  janela_ms: int) -> tuple[bool, list[str]]:
    """Corre os cenários do cockpit com o front MUTADO (uma defesa desligada) e espera que FALHEM.

    Primeiro o CONTROLO: o front da árvore compilado pela MESMA via (cópia + `vite build`) tem de passar os
    cenários que as mutações vão partir — senão uma falha vinha da via de compilação e não da mutação.
    Devolve `(ok, relatorio)`: `ok` = o controlo passou e todas as mutações fizeram os cenários delas falhar.
    """
    import tempfile

    relatorio: list[str] = []
    falhas: list[str] = []
    raiz = Path(tempfile.mkdtemp(prefix="front_mutado_", dir=str(pasta)))

    def correr(dist: Path, grupo: str, quais: tuple) -> tuple[bool, list[str]]:
        if grupo == "multi":
            return checa_multicliente(pasta, modelo, fator_tempo, porta, quais, janela_ms, dist)
        return checa_navegador(pasta, modelo, fator_tempo, quais, porta, dist)

    try:
        dist, saida = construir_front(raiz / "controlo")
        if dist is None:
            return False, [f"o `vite build` da cópia SEM mutação falhou:\n{saida[-1500:]}"]
        for grupo, quais in sorted({(m[3], m[4]) for m in MUTACOES_FRONT}, key=str):
            ok, linhas = correr(dist, grupo, quais)
            relatorio.append(f"· controlo (cópia SEM mutação) · {grupo} {list(quais)}: "
                             f"{'passa' if ok else 'FALHA'}")
            if not ok:
                relatorio += [f"    {linha}" for linha in linhas if linha.startswith("FALHOU:")]
                falhas.append(f"controlo: a cópia SEM mutação falhou os cenários {grupo} {list(quais)} — as "
                              "falhas das mutações não provariam nada")
        for nome, alvo, troca, grupo, quais, descricao in MUTACOES_FRONT:
            dist, saida = construir_front(raiz / nome, (nome, alvo, troca))
            relatorio.append(f"· mutação «{nome}» ({FRONT_COCKPIT}) — {descricao}")
            if dist is None:
                falhas.append(f"mutação «{nome}»: o `vite build` falhou")
                relatorio.append(f"    o `vite build` falhou:\n{saida[-800:]}")
                continue
            ok, linhas = correr(dist, grupo, quais)
            relatorio += [f"    {linha}" for linha in linhas if linha.startswith("FALHOU:")]
            if ok:
                falhas.append(f"mutação «{nome}»: os cenários {grupo} {list(quais)} continuaram VERDES com a "
                              "defesa desligada — o teste não está a medir essa defesa (tautologia)")
                relatorio.append(f"    PROVA FALHOU: com «{nome}» os cenários deviam falhar e passaram")
            else:
                relatorio.append(f"    prova OK: com «{nome}» os cenários {grupo} {list(quais)} FALHARAM "
                                 "como esperado")
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
    for falha in falhas:
        relatorio.append(f"FALHOU: {falha}")
    return not falhas, relatorio


# ------------------------------------------------- prova de NÃO-TAUTOLOGIA (mutação do backend, r13)
# Os cenários dos 3 botões ao nível do runner também têm de ter dentes: cada mutação desliga UMA garantia
# do backend numa CÓPIA das fontes (`$TMPDIR`, usada pelo `--fontes`) e o cenário indicado TEM de falhar.
MUTACOES_BACKEND = (
    ("parar-sem-os-3-botoes", "sim_site.py",
     '        novo["vento_simples"] = {**simples, "ligado": False, "seq": int(simples.get("seq", 0) or 0) + 1}\n',
     "        pass\n",
     "PARAR VENTO (POST /api/parar)",
     "o `POST /api/parar` deixa de desligar o vento dos 3 botões (só pára o contrato antigo)"),
    ("3-botoes-sem-neutralizar-o-antigo", "sim_view.py",
     "            registo = replace(registo, vel=0.0, ativo=False, dinamico=None)\n",
     "            registo = replace(registo)\n",
     "o vento antigo NAO volta",
     "com os 3 botões no ficheiro o vento do contrato antigo continua a soprar por baixo"),
    ("sem-repor-o-gerador", "sim_view.py",
     "            self.gerador_vento.repor()\n",
     "            self.gerador_vento.definir(False, 0.0, False, 0.0)\n",
     "o contrato antigo retoma a autoridade",
     ("o código de ANTES da correção do «vento fantasma»: quando o bloco sai o gerador só é desligado, e a "
      "rampa congelada reaparece quando o bloco volta")),
)


def prova_mutacao_backend(pasta: Path, fator_tempo: float) -> tuple[bool, list[str]]:
    """Corre os cenários dos 3 botões (`--so-simples`) contra fontes MUTADAS e espera que FALHEM.

    Primeiro o CONTROLO — uma cópia SEM mutação tem de passar (exit 0), senão as falhas vinham da via
    (`--fontes`) e não da mutação —, depois cada mutação: exit ≠ 0 E a linha `[FALHA]` do cenário indicado.
    """
    import tempfile

    relatorio: list[str] = []
    falhas: list[str] = []
    raiz = Path(tempfile.mkdtemp(prefix="backend_mutado_", dir=str(pasta)))
    origem = _FONTES or _AQUI

    def correr(nome: str, ficheiro: str | None = None, alvo: str = "", troca: str = ""):
        destino = raiz / nome
        destino.mkdir(parents=True)
        for fonte in ("env.py", "sim_view.py", "sim_site.py"):
            conteudo = (origem / fonte).read_text(encoding="utf-8")
            if fonte == ficheiro:
                if conteudo.count(alvo) != 1:
                    raise SystemExit(f"[teste] mutação impossível: o texto {alvo!r} aparece "
                                     f"{conteudo.count(alvo)}x em {fonte} (o backend mudou? atualize "
                                     "MUTACOES_BACKEND)")
                conteudo = conteudo.replace(alvo, troca, 1)
            (destino / fonte).write_text(conteudo, encoding="utf-8")
        return subprocess.run([sys.executable, str(Path(__file__).resolve()), "--fontes", str(destino),
                               "--so-simples", "--fator-tempo", f"{fator_tempo:g}",
                               "--pasta", str(raiz / f"corrida_{nome}")],
                              capture_output=True, text=True, timeout=900, check=False)

    try:
        controlo = correr("controlo")
        relatorio.append(f"· controlo (cópia SEM mutação, --so-simples): exit {controlo.returncode}")
        if controlo.returncode != 0:
            falhas.append("controlo: a cópia SEM mutação falhou os cenários dos 3 botões — as falhas das "
                          "mutações não provariam nada")
            relatorio += [f"    {linha}" for linha in controlo.stdout.splitlines() if "FALH" in linha][:8]
        for nome, ficheiro, alvo, troca, marca, descricao in MUTACOES_BACKEND:
            feito = correr(nome, ficheiro, alvo, troca)
            apanhou = [linha.strip() for linha in feito.stdout.splitlines()
                       if linha.startswith("[FALHA]") and marca in linha]
            relatorio.append(f"· mutação «{nome}» ({ficheiro}) — {descricao}: exit {feito.returncode} · "
                             f"{len(apanhou)} cenário(s) com «{marca}» em FALHA")
            if feito.returncode == 0 or not apanhou:
                falhas.append(f"mutação «{nome}»: o cenário «{marca}» continuou VERDE com a garantia "
                              "desligada — o teste não a mede (tautologia)")
            else:
                relatorio.append(f"    prova OK: {apanhou[0][:150]}")
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
    for falha in falhas:
        relatorio.append(f"FALHOU: {falha}")
    return not falhas, relatorio


# ---------------------------------------------------------------------------------------------- main
def analisar_argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Prova que o PARAR (DINÂMICO e VENTO) não deixa nenhuma rajada ativa nem pendente e "
                    "devolve o vento ao vento base comandado.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="`--fontes DIR` corre o MESMO teste contra as fontes de outra revisão (ex.: o código anterior "
               "à correção) — é a prova do bug.",
    )
    p.add_argument("--fontes", type=Path, default=None, metavar="DIR",
                   help="pasta com env.py/sim_view.py/sim_site.py alternativos (importados ANTES da árvore "
                        "de trabalho; a pasta tem de estar DENTRO do laboratório)")
    p.add_argument("--legado", nargs="?", const="HEAD", default=None, metavar="REV",
                   help="corre o teste contra as fontes de uma revisão do git (padrão: HEAD) — é a prova do "
                        "bug, um comando")
    p.add_argument("--fator-tempo", type=float, default=2.0, metavar="F",
                   help="ritmo do ciclo do runner (2 = 2x o tempo real; padrão: 2)")
    p.add_argument("--http", action="store_true",
                   help="acrescenta a prova ponta a ponta pelo servidor real (sim_site.py + POSTs; precisa "
                        "de um modelo em out/) e a tempestade de ~100 pares de POSTs concorrentes "
                        "(0 HTTP 500 / 0 JSON partido / comandos intactos / 0 .tmp órfãos)")
    p.add_argument("--navegador", action="store_true",
                   help="acrescenta a prova ponta a ponta com o COCKPIT real num Chrome headless: as DUAS "
                        "paragens (interruptor VENTO e tecla V) não podem deixar o envio pendente do slider "
                        "da intensidade religar o vento; janelas 0/50/100/300 ms + controlo positivo; e os "
                        "cenários MULTI-CLIENTE (paragem por `POST /api/parar` e `POST /api/vento-simples` "
                        "crus, e o interruptor desatualizado); precisa de node, Chrome e `npm run build` "
                        "feito")
    p.add_argument("--so-multi", action="store_true",
                   help="salta a matriz de janelas × paragens da prova --navegador e corre só os cenários "
                        "multi-cliente")
    p.add_argument("--mutacao", action="store_true",
                   help="prova de NÃO-TAUTOLOGIA, em CÓPIAS em $TMPDIR (a árvore não é tocada): (i) o "
                        "backend com uma garantia do vento dos 3 botões desligada tem de fazer falhar o "
                        "cenário do runner que a mede; (ii) o front do cockpit compilado sem mutação "
                        "(controlo) e depois com cada defesa desligada — cada mutação TEM de fazer falhar "
                        "os cenários de browser dela")
    p.add_argument("--janela-multi", type=int, default=2600, metavar="MS",
                   help="janela de amostragem dos cenários multi-cliente, em ms (padrão: 2600)")
    p.add_argument("--dist", type=Path, default=None, metavar="DIR",
                   help="pasta de um bundle do site JÁ compilado (com index.html) a servir nas provas "
                        "--navegador em vez de site/dist — é a prova contra outro front, sem tocar na árvore")
    p.add_argument("--sem-cenarios", action="store_true",
                   help="salta os cenários ao nível do runner (útil para repetir só as provas --http / "
                        "--navegador)")
    p.add_argument("--so-simples", action="store_true",
                   help="dos cenários ao nível do runner corre SÓ os do vento dos 3 botões (r13) — é o que "
                        "a contraprova do backend (--mutacao) usa")
    p.add_argument("--deltas", default="0,50,100,300", metavar="MS,MS,…",
                   help="janelas da prova --navegador, em ms (padrão: 0,50,100,300) — cada janela corre as "
                        "DUAS paragens e o controlo positivo")
    p.add_argument("--porta", type=int, default=8481,
                   help="porta do servidor das provas de navegador (padrão: 8481)")
    p.add_argument("--model", type=Path, default=None, help="modelo para a prova --http (padrão: o do site)")
    p.add_argument("--pasta", type=Path, default=None, metavar="DIR",
                   help="onde escrever controlo/telemetria do teste (padrão: pasta temporária)")
    return p.parse_args(argv)


def _imprimir_cenario(relatorio: dict, linha: str, falhas: list[str]) -> None:
    """Imprime o veredicto de um cenário do runner (e os resíduos, se falhou) e acumula a falha."""
    ruins = [nome for nome, ok in relatorio["checagens"].items() if not ok]
    print(f"[{'OK  ' if not ruins else 'FALHA'}] {relatorio['nome']}")
    print(f"        {linha}")
    if ruins:
        for nome in ruins:
            print(f"        · FALHOU: {nome}")
        print(f"        resíduos: {json.dumps(relatorio['residuos'], default=str)}")
        falhas.append(f"{relatorio['nome']}: {', '.join(ruins)}")


def main(argv=None) -> int:
    args = analisar_argumentos(argv)
    if args.mutacao and args.dist is not None:
        raise SystemExit("[teste] --dist e --mutacao juntos não fazem sentido: a mutação compila os "
                         "próprios bundles")
    if args.dist is not None and not (args.dist / "index.html").is_file():
        raise SystemExit(f"[teste] --dist {args.dist}: falta o index.html (não é um bundle compilado)")
    if args.fontes is not None:
        faltam = [nome for nome in ("env.py", "sim_view.py", "sim_site.py")
                  if not (args.fontes / nome).is_file()]
        if faltam:
            raise SystemExit(f"[teste] --fontes {args.fontes}: faltam {faltam}")
        print(f"[teste] fontes: {_FONTES} (env.py/sim_view.py/sim_site.py desta pasta)")
        if not PARAR_ATOMICO:
            print("[teste] (estas fontes não têm `validar_parar`: o PARAR VENTO é emulado com o "
                  "`POST /api/vento {vel: 0}` antigo)")
    else:
        print("[teste] fontes: árvore de trabalho do laboratório")

    pasta = args.pasta
    if pasta is None:
        import tempfile
        pasta = Path(tempfile.mkdtemp(prefix="teste_parar_vento_"))
    print(f"[teste] ficheiros do teste: {pasta}")
    # o pack de bateria dos servidores lançados aqui (planta real) vive na pasta do TESTE, a não ser que
    # venha definido de fora: a prova não gasta o pack persistente do dono (`out/bateria/`)
    os.environ.setdefault("DRONE_PASTA_BATERIA", str(Path(pasta) / "bateria"))
    simples = [] if (args.sem_cenarios or not TEM_SIMPLES) else CENARIOS_SIMPLES
    antigos = [] if (args.sem_cenarios or args.so_simples) else CENARIOS
    if not args.sem_cenarios:
        print(f"[teste] {len(antigos)} cenários do contrato antigo + {len(simples) + (1 if simples else 0)} do "
              f"vento dos 3 botões (r13), ao nível do runner (ciclo REAL do sim_view.correr)"
              + ("" if TEM_SIMPLES else " — estas fontes não têm o vento dos 3 botões: saltados") + "\n")

    banco = Banco(pasta, fator_tempo=args.fator_tempo)
    banco.arrancar()
    falhas: list[str] = []
    try:
        for cen in antigos:
            try:
                relatorio = correr_cenario(banco, cen)
            except SystemExit as erro:                    # espera estourada: conta como falha do cenário
                print(f"[FALHA] {cen.nome}\n        {erro}")
                falhas.append(f"{cen.nome}: {erro}")
                continue
            _imprimir_cenario(relatorio,
                              f"base comandada = {relatorio['base']} · modos depois do PARAR = "
                              f"{relatorio['modos']} · pior desvio = {relatorio['pior_desvio']:.3e} m/s · "
                              f"{relatorio['amostras']} amostras de telemetria", falhas)
        for cen in simples:
            try:
                relatorio = correr_cenario_simples(banco, cen)
            except SystemExit as erro:
                print(f"[FALHA] {cen.nome}\n        {erro}")
                falhas.append(f"{cen.nome}: {erro}")
                continue
            _imprimir_cenario(relatorio,
                              f"antes: {relatorio['antes']} · depois: modos = {relatorio['modos']} · fora do "
                              f"eixo pedido = {relatorio['fora_do_eixo']:.1e} m/s · rampa e^(−t/τ): erro "
                              f"máx {relatorio['erro_rampa']:.1e} m/s em {relatorio['vivas']} amostras · "
                              f"zero exato ~{relatorio['t_medido']:.2f} s depois (fórmula "
                              f"{relatorio['t_zero']:.2f} s) · {relatorio['amostras']} amostras", falhas)
        if simples:
            try:
                relatorio = correr_cenario_autoridade(banco)
                _imprimir_cenario(relatorio, relatorio["linha"], falhas)
            except SystemExit as erro:
                print(f"[FALHA] {NOME_AUTORIDADE}\n        {erro}")
                falhas.append(f"{NOME_AUTORIDADE}: {erro}")
    finally:
        banco.parar()

    total = len(antigos) + len(simples) + (1 if simples else 0) + 1
    print("\n[teste] defeito (1) — escritas concorrentes na mesma via do servidor (in-process)")
    ok_conc, linhas = checa_concorrencia_inprocess(pasta)
    for linha in linhas:
        print(f"        {linha}")
    print(f"[{'OK  ' if ok_conc else 'FALHA'}] escritas concorrentes sem 500/JSON partido/comando perdido")
    if not ok_conc:
        falhas.append("concorrência in-process")
    modelo = args.model
    if (args.http or args.navegador or args.mutacao) and modelo is None:
        try:
            modelo, motivo = sim_site.modelo_por_omissao()
            print(f"\n[teste] modelo do runner: {modelo} ({motivo})")
        except SystemExit as erro:
            print(f"\n[teste] AVISO: {erro} — salto as provas que precisam do runner")
            modelo = None
    if args.http:
        print("\n[teste] ponta a ponta pelo servidor real (sim_site.py + POSTs + POSTs concorrentes)")
        if modelo is None:
            print("        AVISO: sem modelo — salto a prova --http")
        else:
            total += 1
            ok, relatorio = checa_http(pasta, modelo, args.fator_tempo)
            for linha in relatorio:
                print(f"        {linha}")
            print(f"[{'OK  ' if ok else 'FALHA'}] PARAR pelo HTTP (contrato antigo + 3 botões) + tempestade "
                  "de POSTs concorrentes")
            if not ok:
                falhas.append("ponta a ponta pelo HTTP / concorrência")
    front = "site/dist da árvore de trabalho" if args.dist is None else str(args.dist)
    if args.navegador and not args.so_multi:
        deltas = tuple(int(v) for v in str(args.deltas).replace(" ", "").split(",") if v != "")
        print(f"\n[teste] ponta a ponta com o COCKPIT real num Chrome headless (janelas {list(deltas)} ms × "
              f"{len(PARAGENS)} paragens + controlo; o slider é largado {LARGAR_MS} ms depois da paragem)")
        if modelo is None:
            print("        AVISO: sem modelo — o runner não corre e a telemetria não existe; salto")
        else:
            total += 1
            print(f"        front: {front}")
            ok, relatorio = checa_navegador(pasta, modelo, args.fator_tempo, deltas, args.porta, args.dist)
            for linha in relatorio:
                print(f"        {linha}")
            print(f"[{'OK  ' if ok else 'FALHA'}] nenhum envio atrasado do painel religa o vento depois do "
                  "interruptor VENTO / da tecla V")
            if not ok:
                falhas.append("envio pendente do slider depois da paragem (--navegador)")
    if args.navegador:
        print(f"\n[teste] MULTI-CLIENTE: paragem por OUTRO cliente (POST /api/parar e POST /api/vento-simples "
              f"crus) a meio de um arrasto, e o interruptor desatualizado (religamento por outro cliente), "
              f"janela {args.janela_multi} ms")
        if modelo is None:
            print("        AVISO: sem modelo — o runner não corre e a telemetria não existe; salto")
        else:
            print(f"        front: {front}")
            total += 1
            ok, relatorio = checa_multicliente(pasta, modelo, args.fator_tempo, args.porta, (),
                                               args.janela_multi, args.dist)
            for linha in relatorio:
                print(f"        {linha}")
            print(f"[{'OK  ' if ok else 'FALHA'}] uma paragem de OUTRO cliente não é desfeita pelo painel e o "
                  "interruptor adota o que o servidor diz")
            if not ok:
                falhas.append("paragens multi-cliente / interruptor desatualizado (--navegador)")
    if args.mutacao and TEM_SIMPLES:
        print("\n[teste] NÃO-TAUTOLOGIA (mutação do backend, em CÓPIAS): cada garantia do vento dos 3 botões "
              "desligada tem de fazer FALHAR o cenário do runner que a mede")
        total += 1
        ok, relatorio = prova_mutacao_backend(Path(pasta), args.fator_tempo)
        for linha in relatorio:
            print(f"        {linha}")
        print(f"[{'OK  ' if ok else 'FALHA'}] os cenários dos 3 botões medem mesmo as garantias do backend "
              "(mutação → falha)")
        if not ok:
            falhas.append("prova de não-tautologia (mutação do backend)")
    if args.mutacao:
        print("\n[teste] NÃO-TAUTOLOGIA (mutação do front, numa CÓPIA): cada defesa desligada tem de fazer "
              "FALHAR os cenários que ela protege")
        if modelo is None:
            print("        AVISO: sem modelo — salto a prova de mutação")
        else:
            total += 1
            ok, relatorio = prova_mutacao(pasta, modelo, args.fator_tempo, args.porta, args.janela_multi)
            for linha in relatorio:
                print(f"        {linha}")
            print(f"[{'OK  ' if ok else 'FALHA'}] os cenários do cockpit medem mesmo as defesas do front "
                  "(mutação → falha)")
            if not ok:
                falhas.append("prova de não-tautologia (mutação do front)")

    print(f"\n[teste] {total - len(falhas)}/{total} verificações OK")
    if falhas:
        print("[teste] FALHAS:")
        for falha in falhas:
            print(f"  · {falha}")
        return 1
    print("[teste] nenhuma rajada sobrevive ao PARAR e o vento fica exatamente no vento base comandado")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
