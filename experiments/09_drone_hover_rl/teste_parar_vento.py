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

Este script é também a prova de FIABILIDADE do PARAR — dois defeitos PRÉ-EXISTENTES (não regressões da
correção acima) que faziam o PARAR falhar no uso real:

  (1) **POSTs concorrentes → HTTP 500.** O servidor é `ThreadingHTTPServer` e o temporário da escrita
      atómica tinha o MESMO nome em todas as threads (`.{nome}.tmp{pid}`): dois POSTs simultâneos
      disputavam o ficheiro e o segundo `os.replace` rebentava com `FileNotFoundError` → 500 (e um PARAR
      que devolve 500 não para rajada nenhuma). A prova in-process corre SEMPRE (120 escritas simultâneas
      na mesma função do servidor; medido com o código de antes: 59 falhas e o contador de REINICIAR a
      perder incrementos — 0 falhas e contador exato com o de agora) e o `--http` acrescenta ~100 pares de
      POSTs concorrentes (`rajada_agora`/`nenhum`/`parar`/`reiniciar`/`loop`) contra o servidor REAL, com um
      leitor em paralelo a fazer `json.loads` ao ficheiro — 0 HTTP 500, 0 JSON partido, `loop`/`reiniciar`
      intactos, 0 `.tmp` órfãos;
  (2) **corrida do debounce do front → o modo voltava a ligar-se.** O live-apply dos params é um
      `setTimeout` de ~300 ms que só era cancelado quando o `modoContinuo` mudava (o que depende do
      polling). Um clique dentro dessa janela deixava sair `{modo:"rajadas", ativo:true, params}` DEPOIS do
      `POST /api/parar`, e o servidor+runner honravam-no. Pior: só o PARAR VENTO invalidava os applies
      pendentes — o PARAR DINÂMICO e o toggle PARADO não, e por isso o modo VOLTAVA 0,3–0,7 s depois de
      parar (medido: o controlo fica `nenhum` e volta a `rajadas/ativo` com os params editados). O
      `--navegador` dirige o FRONT real (bundle de `site/dist`) num Chrome headless por CDP, com o servidor
      real: liga RAJADAS, edita um param (o que agenda o apply), espera a janela pedida
      (0/50/100/300/600/1000 ms) e clica o controlo de paragem do cenário — os TRÊS caminhos (`PARAGENS`:
      PARAR VENTO, PARAR DINÂMICO e o toggle PARADO) — amostrando o estado do servidor durante 2,6 s com o
      poll do site a correr. Imprime os POSTs que o front mandou, com o instante relativo à edição — é aí
      que se vê o defeito (no código de antes: `/api/parar` aos 4 ms e `/api/vento-dinamico {modo:rajadas}`
      aos 300 ms) e a correção (nenhum POST de apply depois da paragem). Cada janela corre também SEM a
      paragem (controlo positivo): aí o apply TEM de aparecer com o `p` novo, senão o cenário da paragem não
      estaria a testar nada.

  (3) **paragens de OUTRO cliente (multi-cliente).** As defesas locais (época/cancelamento/bloqueio de
      `site/src/lib/paragem.ts`) são estado de MÓDULO por *realm*: uma paragem vinda de outro cliente — um
      `POST /api/parar` cru (sem browser nenhum) ou o botão PARAR DINÂMICO de uma **2.ª aba real** — não
      lhes toca, e o poll do site (~350 ms + o atraso da resposta) chega sempre depois do debounce de
      300 ms. Medido: a aba A edita um parâmetro, a paragem externa acontece aos ~100 ms, e o debounce
      local dispara aos ~300 ms com os params editados — o servidor fica outra vez `rajadas/ativo` (física
      em rajadas) durante ≥2,5 s. A correção é REVALIDAR ao disparar: antes de escrever, o front confirma
      no servidor (`GET /api/state`, barato) que o modo que ia religar ainda está ativo; se não estiver, o
      apply é suprimido e o painel DIZ que a edição não foi aplicada (nenhum estado morto sem feedback). O
      canal `BroadcastChannel` (paragem de outra aba) complementa — cancela já os temporizadores pendentes
      e faz o painel reler o servidor — mas não é a garantia (um POST cru não passa por canal nenhum).
      O mesmo sítio tinha o **painel preso**: depois de uma paragem LOCAL + um religamento feito por OUTRO
      cliente, o bloqueio do live-apply nunca era levantado (a adoção do modo vindo do poll não o limpava, e
      clicar no modo já pressionado é um no-op do base-ui): editar um campo mudava só o estado do React,
      não saía POST nenhum e o servidor ficava com o valor antigo, sem feedback. Agora o bloqueio é
      levantado pela leitura FRESCA do servidor. Os cenários `--navegador` cobrem os dois (paragem crua a
      0/100/200 ms, 2.ª aba a 0/100 ms, e o painel preso) e a prova de NÃO-TAUTOLOGIA corre-os com o front
      MUTADO (`--mutacao`: desliga a revalidação → os cenários de paragem externa falham; desliga o
      desbloqueio remoto → o cenário do painel preso falha).

`--legado [REV]` materializa as fontes de `env.py`/`sim_view.py`/`sim_site.py` dessa revisão do git (padrão
`HEAD`, ou seja o código de antes da correção) e corre o MESMO teste contra elas — é a prova repetível do
bug, com um comando e sem tocar na árvore de trabalho. `--fontes DIR` faz o mesmo com uma pasta de fontes
(pode estar FORA do repo: é estagiada dentro da árvore e apagada no fim), e `--front DIR` troca as fontes do
FRONT (`controlos.tsx`/`use-sim.ts`/`App.tsx`/`lib/paragem.ts`), compila o site com elas, corre a prova
`--navegador` e repõe+recompila no fim — é a prova do defeito (2)/(3) contra o front de antes, num comando.

Exit 0 = todas as checagens passam; 1 = alguma falha (diz qual e mostra o diagnóstico).
"""
from __future__ import annotations

import argparse
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
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
SITE = _AQUI / "site"                       # o front (React + vite) que o sim_site.py serve de `site/dist`
# Ficheiros do front que as defesas tocam — os que `--front` troca e repõe (prova do código de antes) e os
# que a prova de mutação (`--mutacao`) reescreve. `lib/paragem.ts` é o módulo das paragens (época/bloqueio/
# revalidação): a defesa multi-cliente vive lá.
FRONT_RELATIVOS = ("src/components/sim/controlos.tsx", "src/hooks/use-sim.ts", "src/App.tsx",
                   "src/lib/paragem.ts")


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

BASE_PADRAO = {"vel": 3.0, "azimute": 90.0, "elevacao": 0.0}     # vento base dos cenários (m/s, graus)
BASE_ZERO = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0}
NENHUM = {"modo": "nenhum", "ativo": False}
TOL = 1e-12                       # tolerância da física (`opt.wind` vs vento base comandado, em memória)
TOL_TELE = 2e-6                   # a telemetria arredonda a 6 casas: 1e-6 + folga de arredondamento
TOL_APOS_CLIQUE_MS = 50           # folga do «apply depois do clique» (fila de POSTs do front, ver abaixo)
PARAR_ATOMICO = hasattr(sim_site, "validar_parar")   # rota nova; sem ela emula-se o PARAR VENTO antigo

# Os TRÊS caminhos de paragem do front (o defeito era os dois últimos não invalidarem o apply pendente):
#   · "vento"    — botão PARAR VENTO (`POST /api/parar`: dinâmica desligada + vento base a 0) — já correto;
#   · "dinamico" — botão PARAR DINÂMICO (`POST /api/vento-dinamico {modo:"nenhum", ativo:false}`);
#   · "parado"   — a opção PARADO do toggle do modo contínuo (o MESMO corpo, noutro controlo).
PARAGENS = ("vento", "dinamico", "parado")
ROTULO_PARAGEM = {"vento": "PARAR VENTO", "dinamico": "PARAR DINÂMICO", "parado": "toggle PARADO"}
# Modos em que o painel faz live-apply dos params (é o apply que não pode sobreviver a uma paragem).
MODOS_ATIVOS = ("rajadas", "aleatoria", "dryden")
# Todos os modos dinâmicos: se a telemetria acabar num destes, a física continua a fazer dinâmica.
MODOS_DINAMICOS = MODOS_ATIVOS + ("rajada_agora", "frente")


def _envio_apply_ativo(envio: dict) -> bool:
    """O POST registado no browser é um apply de um modo CONTÍNUO ativo (`{modo, ativo: true}`)?"""
    if "/api/vento-dinamico" not in str(envio.get("url", "")):
        return False
    try:
        corpo = json.loads(envio.get("corpo") or "{}")
    except (TypeError, ValueError):
        return False
    return corpo.get("ativo") is True and corpo.get("modo") in MODOS_ATIVOS


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
        self.args = sim_view.analisar_argumentos(["--sem-janela", "--fator-tempo", f"{fator_tempo:g}",
                                                 "--max-segundos", f"{max_segundos:g}"])
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
    import contextlib
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

    Aqui a mistura é `rajada_agora` · `nenhum` · `parar` · `reiniciar` · `loop`, dois a dois em barreira
    (mesmo instante), com um LEITOR em paralelo a fazer `json.loads` ao ficheiro a cada volta — é ele que
    prova que o ficheiro nunca aparece meio-escrito. No fim contam-se as escritas: o contador `reiniciar`
    tem de subir EXATAMENTE o número de POSTs de reinício (nenhum se perde) e o `loop` fica no que foi
    pedido — sem a trava do ler-modificar-escrever, um POST de vento revertia o incremento do outro.
    """
    relatorio: list[str] = []
    mistura = ("rajada", "nenhum", "parar", "reiniciar", "loop")
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


def checa_http(pasta: Path, modelo: Path | None, fator_tempo: float) -> tuple[bool, list[str]]:
    """Ponta a ponta pelo SERVIDOR real (`sim_site.py` + runner + POSTs), como o site faz.

    Cobre o que o teste ao nível do runner não cobre: a rota `POST /api/parar` a passar pelo HTTP, com o
    `seq` a subir no ficheiro de controlo e o vento a chegar à física do runner.
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
        relatorio.append(f"servidor real em {base_url}")

        # 1) vento base 3 m/s @ 90 + 4 rajadas (3 dirigidas + 1 modo contínuo), com o seq a subir
        if _post(base_url, "/api/vento", {"vel": 3.0, "azimute": 90.0, "elevacao": 0.0})[0] != 200:
            return False, relatorio + ["POST /api/vento recusado"]
        for corpo in (rajada(duracao=400), rajada(duracao=400),
                      continuo("rajadas", p=1.0, duracao=50, u_max=4.0), rajada(duracao=400)):
            codigo, resposta = _post(base_url, "/api/vento-dinamico", corpo)
            if codigo != 200:
                return False, relatorio + [f"POST /api/vento-dinamico recusado ({codigo}): {resposta}"]
        time.sleep(1.0)
        estado = _get(base_url, "/api/sim")
        pedido = sim_site.ler_controlo(controlo).get("dinamico", {})
        relatorio.append(f"antes do PARAR: modo={estado['vento_atual']['modo']} · vento em vigor="
                         f"{estado['vento_atual']['vel']:.3f} m/s · pedido={pedido.get('modo')} "
                         f"(seq={pedido.get('seq')})")

        # 2) PARAR VENTO pelo HTTP (uma rota, uma escrita atómica)
        codigo, corpo = _post(base_url, "/api/parar")
        if codigo != 200:
            return False, relatorio + [f"POST /api/parar devolveu {codigo}: {corpo}"]
        linha_parar = len(linhas_telemetria(telemetria))
        time.sleep(2.0)
        amostras = linhas_telemetria(telemetria)[linha_parar:]
        estado = _get(base_url, "/api/sim")
        pior = max((float(np.linalg.norm(np.array(a["vento_vec"], dtype=float))) for a in amostras),
                   default=float("inf"))
        modos = sorted({str(a.get("vento_modo")) for a in amostras})
        ok = (len(amostras) >= 3 and pior <= TOL_TELE and modos == ["nenhum"]
              and float(estado["vento"]["vel"]) == 0.0 and estado["vento"]["ativo"] is False
              and estado["vento_dinamico"]["modo"] == "nenhum"
              and estado["vento_dinamico"]["ativo"] is False
              and float(estado["vento_atual"]["vel"]) == 0.0 and estado["vento_atual"]["modo"] == "nenhum")
        relatorio.append(f"depois do PARAR VENTO: {len(amostras)} amostras · modos={modos} · "
                         f"pior ‖vento_vec‖={pior:.3e} m/s · API vento={estado['vento']} · "
                         f"dinamico={estado['vento_dinamico']}")
        if not ok:
            return False, relatorio + ["o PARAR VENTO pelo HTTP deixou vento/rajada a atuar"]

        # 3) PARAR DINAMICO com vento base: o vento tem de voltar EXATAMENTE ao base comandado
        if _post(base_url, "/api/vento", {"vel": 3.0, "azimute": 90.0, "elevacao": 0.0})[0] != 200:
            return False, relatorio + ["POST /api/vento recusado (2.ª volta)"]
        if _post(base_url, "/api/vento-dinamico", rajada(u=5.0, duracao=400))[0] != 200:
            return False, relatorio + ["POST /api/vento-dinamico recusado (2.ª volta)"]
        time.sleep(0.8)
        if _post(base_url, "/api/vento-dinamico", {"modo": "nenhum", "ativo": False})[0] != 200:
            return False, relatorio + ["POST /api/vento-dinamico (nenhum) recusado"]
        linha_parar = len(linhas_telemetria(telemetria))
        time.sleep(2.0)
        amostras = linhas_telemetria(telemetria)[linha_parar:]
        base = np.array([0.0, 3.0, 0.0])
        pior = max((float(np.linalg.norm(np.array(a["vento_vec"], dtype=float) - base)) for a in amostras),
                   default=float("inf"))
        modos = sorted({str(a.get("vento_modo")) for a in amostras})
        estado = _get(base_url, "/api/sim")
        ok = (len(amostras) >= 3 and pior <= TOL_TELE and modos == ["nenhum"]
              and abs(float(estado["vento_atual"]["vel"]) - 3.0) <= TOL_TELE)
        relatorio.append(f"depois do PARAR DINAMICO: {len(amostras)} amostras · modos={modos} · "
                         f"pior desvio do vento base={pior:.3e} m/s · vento_atual={estado['vento_atual']}")
        if not ok:
            return False, relatorio + ["o PARAR DINAMICO pelo HTTP deixou vento/rajada a atuar"]

        # 4) DEFEITO (1): tempestade de POSTs concorrentes (500 / JSON partido / comandos perdidos)
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


# ------------------------------------------------------------------ defeito (2): corrida do debounce do front
# Driver CDP mínimo (sem dependências: `WebSocket` global do Node ≥ 22 + o endpoint HTTP do Chrome). O
# trabalho todo acontece DENTRO da página servida pelo `sim_site.py` (o front real, o bundle de `site/dist`):
# clica nos botões verdadeiros, escreve nos campos verdadeiros (setter nativo + evento `input`, que é o que
# o React escuta) e lê o estado pelo `GET /api/sim` do próprio servidor.
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
        return
      }
    })
  })
}

// Tudo o que se passa na página: a sequência de cada cenário (editar um param = agendar o live-apply de
// ~300 ms; esperar a janela pedida; clicar o controlo de paragem do cenário — PARAR VENTO, PARAR DINÂMICO
// ou a opção PARADO do toggle; amostrar o estado do servidor durante 2,6 s).
const NA_PAGINA = async (args) => {
  const espera = (ms) => new Promise((r) => setTimeout(r, ms))
  const porTeste = (id) => document.querySelector(`[data-testid="${id}"]`)
  const opcaoModo = (texto) => {
    const grupo = document.querySelector('[aria-label="modo dinâmico contínuo"]')
    if (!grupo) return null
    const opcoes = Array.from(grupo.querySelectorAll("button"))
    return opcoes.find((b) => b.textContent.trim() === texto) || null
  }
  // É a opção que está PRESSIONADA no toggle? (base-ui marca `aria-pressed`/`data-pressed`). É o que diz se
  // o painel acha que o modo contínuo está ligado — com o poll atrasado ele pode estar desatualizado, e um
  // clique em PARADO só manda o comando se o modo em vigor (para o painel) ainda for o RAJADAS.
  const opcaoPressionada = (texto) => {
    const b = opcaoModo(texto)
    if (!b) return false
    return b.getAttribute("aria-pressed") === "true" || b.getAttribute("data-pressed") === "true"
  }
  // O controlo de paragem do cenário, como o utilizador o vê.
  const alvoParagem = (tipo) => {
    if (tipo === "vento") return porTeste("botao-parar-vento")
    if (tipo === "dinamico") return porTeste("botao-parar-dinamico")
    if (tipo === "parado") return opcaoModo("PARADO")
    return null
  }
  // O alvo está UTILIZÁVEL? (os botões ficam desativados enquanto há um POST em voo; o toggle só troca se
  // o alvo for diferente do modo que o painel mostra)
  const alvoLivre = (tipo, el) => {
    if (!el) return false
    if (tipo === "parado") return opcaoPressionada("RAJADAS")
    return !el.disabled
  }
  // O polling do PRÓPRIO site conta-se aqui: prova que a corrida foi testada com o poll a correr.
  const buscar = window.fetch.bind(window)   // referência para a AMOSTRAGEM (nunca atrasada)
  let polls = 0
  let atrasarPoll = 0                       // ms de atraso na RESPOSTA do `/api/sim` (por cenário)
  let ultimoPoll = null                     // último `vento_dinamico` que o PAINEL recebeu (diagnóstico)
  const envios = []                         // os POSTs que o FRONT manda (vê-se aqui o apply atrasado)
  // POLL LENTO: o cancelamento do apply agendado (debounce de ~300 ms) depende do POLLING, por isso é o
  // tempo que a resposta do `GET /api/sim` leva a chegar ao painel que decide se o apply escapa. Medido
  // nesta máquina: com a telemetria no teto de 4 MB que o `/api/sim` lê do fim, o pedido custa ~65 ms só
  // de parsing — e o site faz o poll a cada 350 ms; numa máquina/browser carregado (ou com o runner a
  // competir pelo GIL) passa disso com folga. Aqui o atraso é explícito e determinístico, aplicado à
  // resposta (o pedido sai já): nenhuma resposta que já reflita o PARAR chega ao painel antes de o
  // temporizador de ~300 ms do apply disparar.
  window.fetch = async (...a) => {
    const url = String(a[0])
    if (url.includes("/api/")) {
      const opcoes = a[1] || {}
      if (String(opcoes.method || "GET").toUpperCase() === "POST") {
        envios.push({ t: performance.now(), url: url.slice(url.indexOf("/api/")), corpo: opcoes.body || null })
      }
    }
    const resposta = await buscar(...a)
    if (atrasarPoll > 0 && url.includes("/api/sim")) {
      polls += 1
      resposta
        .clone()
        .json()
        .then((j) => {
          ultimoPoll = { t: Math.round(performance.now()), din: (j || {}).vento_dinamico || null }
        })
        .catch(() => {})
      await espera(atrasarPoll)
    }
    return resposta
  }
  const escreverCampo = (id, valor) => {
    const el = porTeste(`campo-${id}`)
    if (!el) throw new Error(`o campo ${id} não está no DOM`)
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set
    setter.call(el, String(valor))
    el.dispatchEvent(new Event("input", { bubbles: true }))
  }
  // Amostra pelo `/api/state` (curto, sem as amostras da telemetria): o `/api/sim` é justamente o pedido
  // que a prova atrasa para simular o poll lento, e a amostragem não pode ficar presa atrás dele.
  const lerEstado = async () => {
    const resposta = await buscar("/api/state", { cache: "no-store" })
    if (!resposta.ok) throw new Error(`GET /api/state devolveu ${resposta.status}`)
    const j = await resposta.json()
    const din = j.vento_dinamico || {}
    const atual = j.vento_atual || {}
    return {
      modo: din.modo === undefined ? null : din.modo,
      ativo: din.ativo === true,
      p: (din.params || {}).p === undefined ? null : (din.params || {}).p,
      seq: din.seq === undefined ? null : din.seq,
      vento_modo: atual.modo === undefined ? null : atual.modo,
      vento_vel: atual.vel === undefined ? null : atual.vel,
    }
  }
  const esperar = async (predicado, limite) => {
    const t0 = performance.now()
    while (performance.now() - t0 < limite) {
      if (await predicado()) return true
      await espera(40)
    }
    return false
  }
  const pronto = () =>
    esperar(async () => {
      const botao = porTeste("botao-parar-vento")
      return !!botao && !botao.disabled && !!opcaoModo("RAJADAS")
    }, args.prontidaoMs)
  if (!(await pronto())) throw new Error("o painel de controlos não ficou pronto (site/dist desatualizado?)")

  // O painel só sabe do estado novo quando o POLLING volta (~350 ms): clicar no modo antes disso é um
  // no-op (o `trocarModo` vê o modo antigo e sai). Por isso os cliques repetem-se até o SERVIDOR confirmar.
  const garantirParado = async () => {
    for (let t = 0; t < 120; t++) {
      const botao = porTeste("botao-parar-vento")
      if (botao && !botao.disabled) botao.click()
      if ((await lerEstado()).modo === "nenhum") return true
      await espera(80)
    }
    return false
  }
  const garantirModo = async (texto) => {
    const alvo = texto.toLowerCase()
    for (let t = 0; t < 120; t++) {
      const opcao = opcaoModo(texto)
      if (opcao) opcao.click()
      if ((await lerEstado()).modo === alvo) return true
      await espera(80)
    }
    return false
  }

  // Deixa o painel ASSENTAR antes da edição: com o poll atrasado, as respostas do PARAR (que ainda dizem
  // «nenhum») chegam até `atrasoPollMs` depois do clique e, se caírem depois da edição, apagam a linha de
  // base dos params e o apply agendado nunca sai — o cenário passaria sem testar nada.
  const assentar = async () => {
    for (let tentativa = 0; tentativa < 4; tentativa++) {
      if (!(await garantirParado())) return false
      if (!(await garantirModo("RAJADAS"))) return false
      // 1) todas as respostas atrasadas do PARAR (que ainda dizem «nenhum») têm de chegar ANTES da
      //    edição, senão apagariam a linha de base dos params e o apply agendado nunca sairia;
      await espera(args.atrasoPollMs + 350)
      // 2) o painel dos params entra com animação (`AnimatePresence mode="wait"`): dá-se-lhe tempo. O
      //    toggle tem de mostrar o RAJADAS PRESSIONADO — é ele que diz que o painel julga o modo ligado
      //    (sem isso, um clique no PARADO seria um no-op e o cenário não testaria paragem nenhuma).
      const campo = await esperar(async () => !!porTeste("campo-rajadas-p"), args.prontidaoMs)
      if (campo && opcaoPressionada("RAJADAS") && (await lerEstado()).modo === "rajadas") return true
      await espera(120)
    }
    return false
  }

  const resultados = []
  for (const cenario of args.cenarios) {
    const onde = `janela ${cenario.delta} ms / ${cenario.paragem ? `PARAR ${cenario.paragem}` : "controlo"}`
    // O atraso do poll só corre nos cenários do PARAR (é a condição que abre a janela do defeito); nos
    // controlos fica desligado para o painel estar sempre em dia e a edição agendar mesmo o apply.
    atrasarPoll = cenario.paragem ? args.atrasoPollMs : 0
    if (!(await assentar())) {
      const estado = await lerEstado()
      const ultimos = envios.slice(-6).map((e) => `${Math.round(e.t - performance.now())}:${e.url}`)
      throw new Error(`${onde}: não consegui deixar o painel em RAJADAS (servidor: modo=${estado.modo} ` +
        `ativo=${estado.ativo}; campo=${!!porTeste("campo-rajadas-p")}; ` +
        `RAJADAS pressionado=${opcaoPressionada("RAJADAS")}; polls=${polls}; ` +
        `último poll do painel=${JSON.stringify(ultimoPoll)}; POSTs recentes=${ultimos.join(" ")})`)
    }
    const tParado = performance.now()
    const tModo = performance.now()
    if (!(await esperar(async () => !!porTeste("campo-rajadas-p"), args.prontidaoMs)))
      throw new Error(`${onde}: o painel dos params de rajadas não apareceu`)
    // O painel desativa o controlo de paragem enquanto tem um POST em voo (o `emCurso`): espera-se que
    // fique livre ANTES da edição, para o clique da janela medida ser um clique de utilizador a sério.
    if (!(await esperar(async () => alvoLivre("vento", alvoParagem("vento")), 5000)))
      throw new Error(`${onde}: o botão PARAR VENTO ficou preso em «a enviar»`)
    escreverCampo("rajadas-p", cenario.p)                       // agenda o live-apply (≈300 ms)
    const tEdicao = performance.now()
    await espera(cenario.delta)
    let desativado = false
    if (cenario.paragem) {
      if (!alvoParagem(cenario.paragem)) throw new Error(`${onde}: o controlo de paragem não está no DOM`)
      // O apply pode disparar exactamente na janela do clique e deixar o controlo em «a enviar»: espera-se
      // uns ms que ele fique livre (é o que o utilizador faria). O instante REAL do clique vai no
      // relatório, logo a janela medida não se perde; se nunca ficar livre, o evento vai na mesma (direto).
      const livre = await esperar(
        () => alvoLivre(cenario.paragem, alvoParagem(cenario.paragem)),
        1500
      )
      desativado = !livre
      const alvo = alvoParagem(cenario.paragem)
      if (livre) alvo.click()
      else alvo.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    }
    const tClique = performance.now()
    const amostras = []
    while (performance.now() - tClique < args.janelaMs) {
      amostras.push(Object.assign({ t: Math.round(performance.now() - tClique) }, await lerEstado()))
      await espera(50)
    }
    resultados.push(
      Object.assign({}, cenario, {
        esperaAplicacaoMs: Math.round(tClique - tEdicao),
        botaoDesativado: desativado,
        amostras: amostras,
        envios: envios
          .filter((e) => e.t >= tEdicao - 2000 && e.t <= tClique + args.janelaMs)
          .map((e) => Object.assign({}, e, { t: Math.round(e.t - tEdicao) })),
        marcos: { parado: Math.round(tParado - tEdicao), modo: Math.round(tModo - tEdicao) },
      })
    )
  }
  return { polls: polls, cenarios: resultados }
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
        timeout: args.tempoLimiteMs || 240000,
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


def checa_navegador(pasta: Path, modelo: Path | None, fator_tempo: float, deltas: tuple[int, ...],
                    porta: int = 8431, atraso_poll_ms: int = 500) -> tuple[bool, list[str]]:
    """Ponta a ponta com o SERVIDOR real + o FRONT real num Chrome headless: o apply atrasado não volta.

    O defeito: o live-apply dos params do painel é um `setTimeout` de ~300 ms que só era cancelado quando o
    `modoContinuo` mudava — o que depende do polling (350 ms) mais o ida-e-volta do POST. Um clique dentro
    dessa janela deixava sair `{modo:"rajadas",ativo:true,params}` DEPOIS da paragem e o servidor+runner
    honravam-no: o modo voltava a `rajadas` depois de parar. Só o PARAR VENTO invalidava o apply pendente;
    o PARAR DINÂMICO e o toggle PARADO ficavam de fora (era por aí que o modo VOLTava 0,3–0,7 s depois).

    Cada cenário liga o modo RAJADAS, EDITA um param (o que agenda o apply), espera a janela pedida
    (0/50/100/300/600/1000 ms) e clica o controlo de paragem do cenário — os TRÊS caminhos (`PARAGENS`):
    PARAR VENTO, PARAR DINÂMICO e o toggle PARADO. Depois amostra o `GET /api/state` durante 2,6 s. O
    invariante, igual para os três: (i) a partir da primeira amostra em `nenhum`/inativo, NENHUMA amostra
    pode voltar a um modo ativo; (ii) nenhum POST de apply contínuo pode SAIR do front depois do clique;
    (iii) no fim a dinâmica está desligada (e, no PARAR VENTO, o vento é 0). Cada janela corre também SEM
    paragem (o controlo positivo), SEMPRE DEPOIS dos três cenários de paragem da mesma janela: além de
    provar que o apply agendado sai aos ~300 ms com o `p` novo (senão o cenário da paragem podia passar por
    não haver apply nenhum), prova que um comando NOVO do utilizador volta a armar o live-apply depois de
    uma paragem — é o «depois de parar, um comando novo funciona normalmente».

    O contador de polling da página vai no resultado: a corrida é testada com o poll do site a correr.
    """
    relatorio: list[str] = []
    node = _binario(("node",))
    chrome = _binario(("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"))
    if node is None or chrome is None:
        return False, [f"esta prova precisa do node e do Chrome (node={node!r}, chrome={chrome!r})"]
    if not (SITE / "dist" / "index.html").is_file():
        return False, [f"{SITE / 'dist' / 'index.html'} não existe — corra `npm run build` em {SITE}"]

    pasta.mkdir(parents=True, exist_ok=True)
    controlo, telemetria = pasta / "nav_controle.json", pasta / "nav_telemetria.jsonl"
    for caminho in (controlo, telemetria):
        caminho.unlink(missing_ok=True)
    driver = pasta / "driver_cdp.mjs"
    driver.write_text(_DRIVER_CDP, encoding="utf-8")

    comando = [sys.executable, str(_AQUI / "sim_site.py"), "--sem-browser", "--sem-janela",
               "--port", str(porta), "--controlo", str(controlo), "--telemetria", str(telemetria),
               "--fator-tempo", f"{fator_tempo:g}"]
    if modelo is not None:
        comando += ["--model", str(modelo)]
    servidor = subprocess.Popen(comando, cwd=str(_AQUI), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, start_new_session=True)
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
            return False, relatorio + [(f"não consegui arrancar o sim_site.py na porta {porta} "
                                        "(porta ocupada?)")]
        relatorio.append(f"servidor real em {base_url} · controlo/telemetria em {pasta} · "
                         f"atraso do poll (GET /api/sim) no browser: {atraso_poll_ms} ms")

        perfil = pasta / "chrome-perfil"
        shutil.rmtree(perfil, ignore_errors=True)
        navegador = subprocess.Popen(
            [chrome, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={perfil}",
             "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--disable-dev-shm-usage",
             "--remote-allow-origins=*", base_url + "/"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        porta_cdp = _esperar_devtools(perfil, navegador, 30.0)
        if porta_cdp is None:
            return False, relatorio + ["o Chrome não abriu a porta de depuração (CDP)"]

        cenarios = [{"delta": int(delta), "p": round(0.2 + 0.03 * i, 3), "paragem": paragem}
                    for i, (delta, paragem) in enumerate((d, p) for d in deltas
                                                         for p in PARAGENS + (None,))]
        argumentos = {"cenarios": cenarios, "janelaMs": 2600, "prontidaoMs": 30000,
                      "tempoLimiteMs": 600000, "atrasoPollMs": int(atraso_poll_ms)}
        try:
            resultado = subprocess.run([node, str(driver), str(porta_cdp), base_url, json.dumps(argumentos)],
                                       capture_output=True, text=True, timeout=420, check=False)
        except subprocess.TimeoutExpired:
            return False, relatorio + ["o driver do navegador não terminou em 420 s"]
        if resultado.returncode != 0:
            return False, relatorio + [(f"o driver do navegador falhou ({resultado.returncode}):\n"
                                        f"{(resultado.stderr or resultado.stdout)[-2000:]}")]
        dados = json.loads(resultado.stdout)
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

    falhas: list[str] = []
    for cenario in dados["cenarios"]:
        amostras = cenario["amostras"]
        paragem = cenario.get("paragem")
        rotulo = (f"{ROTULO_PARAGEM[paragem]} depois de {cenario['esperaAplicacaoMs']} ms "
                  f"(janela {cenario['delta']} ms)" if paragem
                  else f"controlo sem PARAR (janela {cenario['delta']} ms)")
        if not amostras:
            falhas.append(f"{rotulo}: nenhuma amostra")
            continue
        ultima = amostras[-1]
        modos = sorted({str(a["modo"]) for a in amostras})
        if paragem:
            primeiro = next((i for i, a in enumerate(amostras) if a["modo"] == "nenhum" and not a["ativo"]),
                            None)
            voltou = primeiro is not None and any(a["modo"] != "nenhum" or a["ativo"]
                                                  for a in amostras[primeiro:])
            # A prova DIRETA de que o debounce morreu com o clique: nenhum POST de apply de um modo
            # contínuo pode SAIR do front depois do instante do clique (a época/cancelamento/bloqueio).
            # A folga de 50 ms cobre o ida-e-volta da fila de POSTs: um apply que já estava em voo antes do
            # clique pode só sair uns ms depois — e a fila garante que o PARAR é a ÚLTIMA escrita.
            atrasados = [e for e in cenario.get("envios", [])
                         if e["t"] > cenario["esperaAplicacaoMs"] + TOL_APOS_CLIQUE_MS
                         and _envio_apply_ativo(e)]
            # PARAR VENTO também põe o vento base a 0; os outros dois só desligam a dinâmica. Para os três
            # o invariante é o mesmo: depois da paragem a física não pode estar a fazer dinâmica nenhuma.
            base_ok = (ultima["vento_modo"] == "nenhum" and ultima["vento_vel"] is not None
                       and abs(float(ultima["vento_vel"])) <= TOL_TELE) if paragem == "vento" \
                else ultima["vento_modo"] not in MODOS_DINAMICOS
            ok = (primeiro is not None and not voltou and not atrasados
                  and ultima["modo"] == "nenhum" and not ultima["ativo"] and base_ok)
            if primeiro is None:
                falhas.append(f"{rotulo}: o PARAR nunca chegou ao servidor (nenhuma amostra em "
                              f"nenhum/inativo) — o controlo «{ROTULO_PARAGEM[paragem]}» não parou nada")
            elif voltou:
                falhas.append(f"{rotulo}: o modo VOLTOU a ativar depois do PARAR "
                              f"(amostras={[(a['t'], a['modo'], a['ativo']) for a in amostras[:14]]})")
            elif atrasados:
                falhas.append(f"{rotulo}: o front mandou um apply dinâmico DEPOIS do PARAR "
                              f"(POSTs={[(e['t'], e['url'], e['corpo']) for e in atrasados]})")
            elif not base_ok:
                falhas.append(f"{rotulo}: a dinâmica continua a atuar depois do PARAR "
                              f"(vento_modo={ultima['vento_modo']!r} vento={ultima['vento_vel']})")
        else:
            ok = (ultima["modo"] == "rajadas" and ultima["ativo"] and ultima["p"] is not None
                  and abs(float(ultima["p"]) - cenario["p"]) <= 1e-9)
            if not ok:
                falhas.append(f"{rotulo}: o apply agendado NÃO chegou (p={ultima['p']!r} != "
                              f"{cenario['p']}) — o cenário do PARAR não estaria a testar nada")
        relatorio.append(f"janela {cenario['delta']:>4} ms · "
                         f"{(ROTULO_PARAGEM[paragem] if paragem else 'controlo'):<22}"
                         f" · aplicação aos {cenario['esperaAplicacaoMs']} ms · {len(amostras)} amostras · "
                         f"modos vistos={modos} · fim: modo={ultima['modo']!r} p={ultima['p']!r} "
                         f"(pedido {cenario['p']}) vento_modo="
                         f"{ultima['vento_modo']!r} vento={ultima['vento_vel']}"
                         + (" · (controlo desativado no clique: evento direto)"
                            if cenario.get("botaoDesativado") else ""))
    for cenario in dados["cenarios"]:
        if cenario.get("envios"):
            paragem = cenario.get("paragem")
            relatorio.append(f"POSTs do front na janela {cenario['delta']} ms / "
                             f"{ROTULO_PARAGEM[paragem] if paragem else 'controlo'} (ms desde a edição; "
                             f"PARADO aos {cenario['marcos']['parado']}, RAJADAS aos "
                             f"{cenario['marcos']['modo']}): "
                             + " · ".join(f"{e['t']}:{e['url']} {e['corpo']}" for e in cenario["envios"]))
    for falha in falhas:
        relatorio.append(f"FALHOU: {falha}")
    relatorio.append(f"polling do site durante a prova: {dados['polls']} GET /api/sim")
    if dados["polls"] < 10:
        falhas.append(f"o polling do site quase não correu ({dados['polls']} pedidos): a corrida não foi "
                      "testada com o poll a correr")
    return not falhas, relatorio


# ------------------------------------------- defeito (3): paragens de OUTRO cliente (multi-cliente)
# As três defesas locais (época, cancelamento, bloqueio) são estado de MÓDULO por *realm*: uma paragem
# feita por OUTRO cliente — um `POST /api/parar` cru, sem browser nenhum, ou o botão de uma 2.ª ABA real —
# não lhes toca, e o poll do site (~350 ms + o atraso da resposta) chega sempre depois do debounce de
# 300 ms. Medido: a aba A edita um parâmetro, outro cliente para aos ~100 ms, e o debounce local dispara
# aos ~300 ms com os params editados: o servidor fica outra vez `rajadas/ativo` (física em rajadas) durante
# ≥2,5 s.
#
# A defesa é REVALIDAR ao disparar: antes de escrever, o front confirma no servidor (leitura barata de
# `/api/state`) que o modo que ia religar ainda está ativo; se já não estiver, o apply é suprimido e o
# painel di-lo ao utilizador. O canal `BroadcastChannel` (paragem de outra aba) complementa — cancela já os
# temporizadores pendentes — mas não é a garantia: um `POST` cru não passa por canal nenhum.
#
# O SEGUNDO defeito medido vive no mesmo sítio: depois de uma paragem LOCAL + um religamento feito por
# OUTRO cliente, o BLOQUEIO do live-apply ficava preso (só um comando contínuo LOCAL o limpava e clicar no
# modo já pressionado é um no-op do base-ui): editar um campo mudava só o estado do React, não saía POST
# nenhum e o servidor ficava com o valor antigo — sem feedback nenhum.
_MULTI_AJUDANTE = r'''
(args) => {
  const espera = (ms) => new Promise((r) => setTimeout(r, ms))
  const porTeste = (id) => document.querySelector(`[data-testid="${id}"]`)
  const grupoModo = () => document.querySelector('[aria-label="modo dinâmico contínuo"]')
  const opcaoModo = (texto) => {
    const grupo = grupoModo()
    if (!grupo) return null
    return Array.from(grupo.querySelectorAll("button")).find((b) => b.textContent.trim() === texto) || null
  }
  const pressionada = (texto) => {
    const b = opcaoModo(texto)
    if (!b) return false
    return b.getAttribute("aria-pressed") === "true" || b.getAttribute("data-pressed") === "true"
  }
  // Instrumentação: os POSTs do FRONT (é aí que se vê o apply atrasado) e o atraso do `GET /api/sim` (o
  // poll lento é a condição que abre a janela do defeito: sem ele o painel cancelaria o debounce a tempo).
  const buscar = window.fetch.bind(window)
  const envios = []
  const marcas = {}
  let polls = 0
  window.fetch = async (...a) => {
    const url = String(a[0])
    const opcoes = a[1] || {}
    if (url.includes("/api/") && String(opcoes.method || "GET").toUpperCase() === "POST") {
      envios.push({ t: performance.now(), url: url.slice(url.indexOf("/api/")), corpo: opcoes.body || null })
    }
    const resposta = await buscar(...a)
    if (args.atrasoPollMs > 0 && url.includes("/api/sim")) {
      polls += 1
      await espera(args.atrasoPollMs)
    }
    return resposta
  }
  const lerEstado = async () => {
    const resposta = await buscar("/api/state", { cache: "no-store" })
    if (!resposta.ok) throw new Error(`GET /api/state devolveu ${resposta.status}`)
    const j = await resposta.json()
    const din = j.vento_dinamico || {}
    const atual = j.vento_atual || {}
    return {
      modo: din.modo === undefined ? null : din.modo,
      ativo: din.ativo === true,
      p: (din.params || {}).p === undefined ? null : (din.params || {}).p,
      vento_modo: atual.modo === undefined ? null : atual.modo,
      vento_vel: atual.vel === undefined ? null : atual.vel,
    }
  }
  const esperar = async (predicado, limite) => {
    const t0 = performance.now()
    while (performance.now() - t0 < limite) {
      if (await predicado()) return true
      await espera(40)
    }
    return false
  }
  const escreverCampo = (id, valor) => {
    const el = porTeste(`campo-${id}`)
    if (!el) throw new Error(`o campo ${id} não está no DOM`)
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set
    setter.call(el, String(valor))
    el.dispatchEvent(new Event("input", { bubbles: true }))
  }
  // O painel como o DONO o vê: modo pressionado, valor no campo, avisos de «não aplicado» e toasts.
  const painel = () => ({
    rajadas: pressionada("RAJADAS"),
    parado: pressionada("PARADO"),
    aleatoria: pressionada("ALEATORIA"),
    dryden: pressionada("DRYDEN"),
    campoP: porTeste("campo-rajadas-p") ? porTeste("campo-rajadas-p").value : null,
    suprimido: porTeste("apply-suprimido") ? porTeste("apply-suprimido").textContent : null,
    selo: porTeste("estado-dinamico") ? porTeste("estado-dinamico").textContent.trim() : null,
    avisos: Array.from(document.querySelectorAll('[aria-label="fechar aviso"]')).map(
      (b) => (b.parentElement ? b.parentElement.textContent : "")
    ),
  })
  const garantirParado = async () => {
    for (let t = 0; t < 120; t++) {
      const botao = porTeste("botao-parar-vento")
      if (botao && !botao.disabled) botao.click()
      if ((await lerEstado()).modo === "nenhum") return true
      await espera(80)
    }
    return false
  }
  const garantirModo = async (texto) => {
    const alvo = texto.toLowerCase()
    for (let t = 0; t < 250; t++) {
      if ((await lerEstado()).modo === alvo) return true
      clicarModo(texto)
      await espera(60)
    }
    return false
  }
  // Clicar no modo JÁ PRESSIONADO é um no-op do base-ui (`trocarModo` sai quando o alvo é o modo que ele
  // julga em vigor): com o poll atrasado o painel mostra o modo antigo e um clique desses não fazia NADA —
  // o servidor nunca ficava no modo pedido. O clique só sai quando o painel já não mostra o alvo pressionado.
  const clicarModo = (texto) => {
    const b = opcaoModo(texto)
    if (!b) return false
    if (pressionada(texto)) return false
    b.click()
    return true
  }
  // Deixa o painel ASSENTAR em RAJADAS (servidor confirmado, campo à vista, RAJADAS pressionado) — como o
  // `assentar()` da matriz: com o poll atrasado, as respostas do PARAR (que ainda dizem «nenhum») têm de
  // chegar ANTES da edição, senão o cenário passaria sem testar nada.
  const preparar = async () => {
    if (!(await esperar(() => !!porTeste("botao-parar-vento"), args.prontidaoMs))) {
      return { ok: false, motivo: "o painel de controlos não ficou pronto (site/dist desatualizado?)" }
    }
    for (let tentativa = 0; tentativa < 4; tentativa++) {
      if (!(await garantirParado())) return { ok: false, motivo: "não consegui deixar o servidor PARADO" }
      if (!(await garantirModo("RAJADAS"))) return { ok: false, motivo: "não consegui ligar RAJADAS" }
      await espera(args.atrasoPollMs + 350)
      const pronto = await esperar(
        async () => !!porTeste("campo-rajadas-p") && pressionada("RAJADAS") && (await lerEstado()).modo === "rajadas",
        args.prontidaoMs
      )
      if (pronto) {
        envios.length = 0
        return { ok: true, t: performance.now(), estado: await lerEstado(), painel: painel() }
      }
      await espera(120)
    }
    return { ok: false, motivo: "o painel não ficou em RAJADAS com os params à vista" }
  }
  // Edita um parâmetro: agenda o live-apply do painel (≈300 ms). Devolve o instante da edição.
  // O painel dos params entra com animação (`AnimatePresence mode="wait"`): espera-se que o campo esteja
  // no DOM antes de escrever (logo a seguir a uma adoção do modo ele ainda pode estar a entrar).
  const editar = async (valor, limite) => {
    const pronto = await esperar(() => !!porTeste("campo-rajadas-p"), limite || 15000)
    if (!pronto) throw new Error("o campo rajadas-p não apareceu no painel")
    escreverCampo("rajadas-p", valor)
    return performance.now()
  }
  const marcar = (nome) => {
    marcas[nome] = performance.now()
    return { nome: nome, t: marcas[nome] }
  }
  // Paragem LOCAL pelo painel da própria aba (o clique a sério) + confirmação do servidor.
  const pararLocal = async (tipo) => {
    const t = performance.now()
    for (let i = 0; i < 120; i++) {
      const alvo = tipo === "dinamico" ? porTeste("botao-parar-dinamico") : porTeste("botao-parar-vento")
      if (alvo && !alvo.disabled) alvo.click()
      if ((await lerEstado()).modo === "nenhum") {
        const adotou = await esperar(() => painel().parado, args.prontidaoMs)
        return { t: t, tConfirmado: performance.now(), adotou: adotou, estado: await lerEstado(), painel: painel() }
      }
      await espera(80)
    }
    return { t: t, tConfirmado: null, adotou: false, estado: await lerEstado(), painel: painel() }
  }
  // O painel ADOTA o modo que OUTRO cliente ligou (vem no poll): é aqui que ele ficava preso.
  const esperarAdocao = async (texto, modo, limite) => {
    const ok = await esperar(
      async () => pressionada(texto) && (await lerEstado()).modo === modo && (await lerEstado()).ativo,
      limite
    )
    return { ok: ok, t: performance.now(), estado: await lerEstado(), painel: painel() }
  }
  // Amostra o servidor durante `ms` (cada amostra é um `GET /api/state` curto) e devolve o painel no fim.
  const recolher = async (ms) => {
    const t0 = performance.now()
    const amostras = []
    while (performance.now() - t0 < ms) {
      amostras.push(Object.assign({ t: Math.round(performance.now() - t0) }, await lerEstado()))
      await espera(50)
    }
    marcas.recolha = t0
    return {
      amostras: amostras,
      painel: painel(),
      polls: polls,
      marcas: marcas,
      envios: envios.map((e) => Object.assign({}, e, { t: Math.round(e.t) })),
      tFim: performance.now(),
    }
  }
  return { lerEstado, preparar, editar, marcar, pararLocal, esperarAdocao, recolher, painel }
}
'''

# A 2.ª ABA (o «outro cliente» a sério): só precisa de carregar o bundle e de clicar o botão de paragem.
_MULTI_ABA_B = r'''
(() => {
  const espera = (ms) => new Promise((r) => setTimeout(r, ms))
  const botao = () => document.querySelector('[data-testid="botao-parar-dinamico"]')
  return {
    pronto: async (limite) => {
      const t0 = performance.now()
      while (performance.now() - t0 < limite) {
        if (botao()) return true
        await espera(50)
      }
      return false
    },
    pararDinamico: () => {
      const b = botao()
      if (!b) return { clicou: false, motivo: "o botão PARAR DINÂMICO não está no DOM" }
      const t = performance.now()
      b.click()
      return { clicou: true, t: t, desativado: b.disabled === true }
    },
  }
})()
'''

_DRIVER_CDP_MULTI = r'''
const [, , portaArg, urlBase, argsArg] = process.argv
const args = JSON.parse(argsArg)
const espera = (ms) => new Promise((r) => setTimeout(r, ms))

async function listaAlvos() {
  return await (await fetch(`http://127.0.0.1:${portaArg}/json/list`)).json()
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
        return
      }
    })
  })
}

async function alvoDoSite() {
  for (let i = 0; i < 200; i++) {
    try {
      const pagina = (await listaAlvos()).find(
        (t) => t.type === "page" && String(t.url).startsWith(urlBase) && t.webSocketDebuggerUrl
      )
      if (pagina) return pagina.webSocketDebuggerUrl
    } catch (erro) {
      /* a porta ainda não abriu */
    }
    await espera(100)
  }
  throw new Error("não encontrei a página do site no Chrome (CDP)")
}

// Abre uma ABA NOVA da mesma origem (o `site/dist` do servidor real): é o front limpo, sem instrumentação
// nenhuma da matriz, e serve de «outro cliente» quando o cenário pede uma 2.ª aba a sério.
// O `/json/new` deste Chrome IGNORA o `url=` (abre `about:blank`): a navegação é feita por CDP a seguir.
async function abrirAba(navegarAte) {
  let alvo = null
  for (const metodo of ["PUT", "GET"]) {
    try {
      const resposta = await fetch(`http://127.0.0.1:${portaArg}/json/new`, { method: metodo })
      if (!resposta.ok) continue
      alvo = await resposta.json()
      if (alvo && alvo.webSocketDebuggerUrl) break
    } catch (erro) {
      /* método não suportado: tenta o seguinte */
    }
  }
  if (alvo === null || !alvo.webSocketDebuggerUrl) {
    // último recurso: a aba que o Chrome abriu no arranque (já está no site)
    return await ligar(await alvoDoSite())
  }
  const ligacao = await ligar(alvo.webSocketDebuggerUrl)
  await ligacao.comando("Runtime.enable")
  await ligacao.comando("Page.enable")
  await ligacao.comando("Page.navigate", { url: navegarAte })
  return ligacao
}

// A aba só serve quando o painel de controlos está no DOM (o bundle carregou e o React montou).
async function esperarPainel(ligacao, limite) {
  const t0 = Date.now()
  while (Date.now() - t0 < limite) {
    try {
      const pronto = await avaliar(
        ligacao,
        `!!document.querySelector('[data-testid="botao-parar-vento"]')`,
        15000
      )
      if (pronto === true) return true
    } catch (erro) {
      /* contexto destruído pela navegação: tenta outra vez */
    }
    await espera(100)
  }
  return false
}

async function paraFrente(ligacao) {
  try {
    await ligacao.comando("Page.bringToFront")   // aba visível: os temporizadores (debounce) não são travados
  } catch (erro) {
    /* sem o domínio Page: segue */
  }
}

async function avaliar(ligacao, expressao, tempoLimiteMs) {
  const resposta = await ligacao.comando("Runtime.evaluate", {
    expression: expressao,
    awaitPromise: true,
    returnByValue: true,
    timeout: tempoLimiteMs || 120000,
  })
  if (resposta.exceptionDetails) {
    const detalhe = resposta.exceptionDetails.exception || {}
    throw new Error(`na página: ${detalhe.description || resposta.exceptionDetails.text}`)
  }
  return resposta.result.value
}

// Espera (do lado do NODE, sem browser) que o SERVIDOR confirme a paragem: é o que separa a ação externa da
// janela de amostragem — a partir daí nenhuma amostra pode voltar a um modo ativo.
async function esperarServidorParado(limite) {
  const t0 = Date.now()
  while (Date.now() - t0 < limite) {
    try {
      const resposta = await fetch(urlBase + "/api/state", { cache: "no-store" })
      const j = await resposta.json()
      const din = j.vento_dinamico || {}
      if (din.modo === "nenhum" && din.ativo !== true) return Date.now() - t0
    } catch (erro) {
      /* servidor ocupado: tenta outra vez */
    }
    await espera(20)
  }
  return null
}

try {
  // A ABA DO PAINEL é a que o Chrome abriu no arranque (fresca, sem instrumentação nenhuma).
  const ligacaoA = await ligar(await alvoDoSite())
  await ligacaoA.comando("Runtime.enable")
  await ligacaoA.comando("Page.enable")
  await paraFrente(ligacaoA)
  if (!(await esperarPainel(ligacaoA, 60000))) throw new Error("a aba do painel não carregou o site")
  await avaliar(ligacaoA, `window.__args = ${JSON.stringify(args)}; null`)
  await avaliar(ligacaoA, `window.__prova = (${args.ajudante})(${JSON.stringify(args)}); null`)

  let ligacaoB = null
  if (args.cenarios.some((c) => c.tipo === "aba")) {
    ligacaoB = await abrirAba(urlBase + "/")
    await ligacaoB.comando("Runtime.enable")
    if (!(await esperarPainel(ligacaoB, 60000))) throw new Error("a 2.ª aba não carregou o site")
    const pronto = await avaliar(ligacaoB, `window.__provaB = ${args.abaB}; window.__provaB.pronto(5000)`, 30000)
    if (!pronto) throw new Error("a 2.ª aba não ficou pronta (bundle do site não carregou)")
    await paraFrente(ligacaoA)   // a aba do painel volta à frente (é ela que tem o debounce)
  }

  const resultados = []
  for (const cenario of args.cenarios) {
    const r = Object.assign({}, cenario)
    if (cenario.tipo === "preso") {
      r.preparo = await avaliar(ligacaoA, `__prova.preparar()`, 120000)
      if (!r.preparo.ok) {   // sem o painel em RAJADAS não se mede nada: o Python reporta o motivo
        resultados.push(r)
        continue
      }
      r.paragemLocal = await avaliar(ligacaoA, `__prova.pararLocal("dinamico")`, 120000)
      const marca = await avaliar(ligacaoA, `__prova.marcar("religamento")`)
      const corpo = { modo: "rajadas", ativo: true, params: { p: args.pReligado, duracao: 20, u_max: 1.5 } }
      const resposta = await fetch(urlBase + "/api/vento-dinamico", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      })
      r.religamento = { http: resposta.status, corpo: corpo, t: marca.t }
      r.adocao = await avaliar(ligacaoA, `__prova.esperarAdocao("RAJADAS", "rajadas", 20000)`, 60000)
      if (!r.adocao.ok) {    // o painel não adotou: o Python reporta (é um defeito de estado honesto)
        resultados.push(r)
        continue
      }
      r.tEdicao = await avaliar(ligacaoA, `__prova.editar(${cenario.p})`)
      r.fim = await avaliar(ligacaoA, `__prova.recolher(${args.janelaMs})`, 180000)
      resultados.push(r)
      continue
    }
    r.preparo = await avaliar(ligacaoA, `__prova.preparar()`, 120000)
    if (!r.preparo.ok) {
      resultados.push(r)
      continue
    }
    r.tEdicao = await avaliar(ligacaoA, `__prova.editar(${cenario.p})`)
    await espera(cenario.delta)
    const marca = await avaliar(ligacaoA, `__prova.marcar("externa")`)
    r.tExterna = marca.t
    if (cenario.tipo === "cru") {
      // OUTRO CLIENTE, sem browser nenhum: um `POST /api/parar` cru, como um script/curl faria.
      const resposta = await fetch(urlBase + "/api/parar", { method: "POST" })
      r.externa = { tipo: "cru", http: resposta.status, t: marca.t }
    } else if (cenario.tipo === "aba") {
      // 2.ª ABA REAL: o MESMO botão do painel, clicado noutra aba do mesmo browser.
      r.externa = { tipo: "aba", clique: await avaliar(ligacaoB, `__provaB.pararDinamico()`, 60000), t: marca.t }
    } else {
      throw new Error(`cenário externo desconhecido: ${cenario.tipo}`)
    }
    r.esperaParagemMs = await esperarServidorParado(8000)
    r.fim = await avaliar(ligacaoA, `__prova.recolher(${args.janelaMs})`, 180000)
    resultados.push(r)
  }
  ligacaoA.ws.close()
  if (ligacaoB) ligacaoB.ws.close()
  process.stdout.write(JSON.stringify({ cenarios: resultados }))
} catch (erro) {
  process.stderr.write(String((erro && erro.stack) || erro) + "\n")
  process.exit(2)
}
'''


def cenarios_multicliente(quais: tuple[str, ...] = ()) -> list[dict]:
    """Cenários multi-cliente: paragem externa (cru / 2.ª aba) e o painel preso (religamento remoto)."""
    todos = [
        {"nome": "POST /api/parar cru (outro cliente) logo após a edição", "tipo": "cru", "delta": 0, "p": 0.31},
        {"nome": "POST /api/parar cru 100 ms após a edição", "tipo": "cru", "delta": 100, "p": 0.33},
        {"nome": "POST /api/parar cru 200 ms após a edição", "tipo": "cru", "delta": 200, "p": 0.35},
        {"nome": "PARAR DINÂMICO numa 2.ª aba real, logo após a edição", "tipo": "aba", "delta": 0, "p": 0.37},
        {"nome": "PARAR DINÂMICO numa 2.ª aba real 100 ms após a edição", "tipo": "aba", "delta": 100, "p": 0.39},
        {"nome": "painel preso: paragem LOCAL + religamento por outro cliente", "tipo": "preso", "delta": 0, "p": 0.41},
    ]
    if not quais:
        return todos
    return [c for c in todos if c["tipo"] in quais]


def checa_multicliente(pasta: Path, modelo: Path | None, fator_tempo: float, porta: int = 8481,
                       atraso_poll_ms: int = 500, quais: tuple[str, ...] = (),
                       janela_ms: int = 2600) -> tuple[bool, list[str]]:
    """Ponta a ponta com o SERVIDOR real + o FRONT real: paragens de OUTRO cliente e o painel preso.

    Dois invariantes, medidos como o dono os vê:

    (a) **paragem externa** (`POST /api/parar` cru, sem browser nenhum; e o botão PARAR DINÂMICO de uma 2.ª
        ABA real): com a aba A em RAJADAS e o debounce do live-apply agendado (edição + 0/100/200 ms), o
        servidor tem de ficar em `nenhum` e NÃO PODE voltar a um modo ativo em nenhuma das amostras dos
        2,6 s seguintes — e nenhum POST de apply pode sair do front depois da paragem. No caso cru o painel
        ainda tem de DIZER que a edição não foi aplicada (`apply-suprimido`); no caso da 2.ª aba, o aviso
        cross-tab chega à aba A.
    (b) **painel preso**: paragem LOCAL pelo painel + religamento do modo por OUTRO cliente (POST cru) + o
        painel adota o modo (poll) + edição local de um parâmetro ⇒ o POST tem de SAIR e o servidor tem de
        ficar com o valor editado. Sem isto o campo mostrava o valor novo e o servidor ficava com o antigo.

    A prova de não-tautologia corre com o front mutado (`--mutacao`): desligada a revalidação, (a) falha;
    desligado o desbloqueio pela adoção do servidor, (b) falha.
    """
    relatorio: list[str] = []
    cenarios = cenarios_multicliente(quais)
    if not cenarios:
        return True, relatorio + ["nenhum cenário multi-cliente pedido"]
    node = _binario(("node",))
    chrome = _binario(("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"))
    if node is None or chrome is None:
        return False, relatorio + [f"esta prova precisa do node e do Chrome (node={node!r}, chrome={chrome!r})"]
    if not (SITE / "dist" / "index.html").is_file():
        return False, relatorio + [f"{SITE / 'dist' / 'index.html'} não existe — corra `npm run build` em {SITE}"]

    pasta.mkdir(parents=True, exist_ok=True)
    controlo, telemetria = pasta / "multi_controle.json", pasta / "multi_telemetria.jsonl"
    for caminho in (controlo, telemetria):
        caminho.unlink(missing_ok=True)
    driver = pasta / "driver_cdp_multi.mjs"
    driver.write_text(_DRIVER_CDP_MULTI, encoding="utf-8")

    comando = [sys.executable, str(_AQUI / "sim_site.py"), "--sem-browser", "--sem-janela",
               "--port", str(porta), "--controlo", str(controlo), "--telemetria", str(telemetria),
               "--fator-tempo", f"{fator_tempo:g}"]
    if modelo is not None:
        comando += ["--model", str(modelo)]
    servidor = subprocess.Popen(comando, cwd=str(_AQUI), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, start_new_session=True)
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
            return False, relatorio + [(f"não consegui arrancar o sim_site.py na porta {porta} "
                                        "(porta ocupada?)")]
        relatorio.append(f"servidor real em {base_url} · 2 abas do site (a do painel e a do «outro "
                         f"cliente») · atraso do poll (GET /api/sim) na aba do painel: {atraso_poll_ms} ms")

        perfil = pasta / "chrome-perfil-multi"
        shutil.rmtree(perfil, ignore_errors=True)
        navegador = subprocess.Popen(
            [chrome, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={perfil}",
             "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--disable-dev-shm-usage",
             "--remote-allow-origins=*", base_url + "/"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        porta_cdp = _esperar_devtools(perfil, navegador, 30.0)
        if porta_cdp is None:
            return False, relatorio + ["o Chrome não abriu a porta de depuração (CDP)"]

        argumentos = {"cenarios": cenarios, "janelaMs": janela_ms, "prontidaoMs": 30000,
                      "atrasoPollMs": int(atraso_poll_ms), "pReligado": 0.5,
                      "ajudante": _MULTI_AJUDANTE.strip(), "abaB": _MULTI_ABA_B.strip()}
        try:
            resultado = subprocess.run([node, str(driver), str(porta_cdp), base_url,
                                        json.dumps(argumentos)],
                                       capture_output=True, text=True, timeout=600, check=False)
        except subprocess.TimeoutExpired:
            return False, relatorio + ["o driver multi-cliente não terminou em 600 s"]
        if resultado.returncode != 0:
            return False, relatorio + [(f"o driver multi-cliente falhou ({resultado.returncode}):\n"
                                        f"{(resultado.stderr or resultado.stdout)[-2000:]}")]
        dados = json.loads(resultado.stdout)
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

    falhas: list[str] = []
    for cenario in dados["cenarios"]:
        nome = cenario["nome"]
        preparo = cenario.get("preparo") or {}
        if not preparo.get("ok"):
            falhas.append(f"{nome}: o painel não ficou em RAJADAS antes do cenário "
                          f"({preparo.get('motivo')})")
            continue
        fim = cenario["fim"]
        amostras = fim["amostras"]
        painel = fim["painel"]
        envios = fim["envios"]
        if cenario["tipo"] == "preso":
            local = cenario.get("paragemLocal") or {}
            adocao = cenario.get("adocao") or {}
            religamento = cenario.get("religamento") or {}
            # O POST local saiu e o painel adotou o PARADO; o religamento é de OUTRO cliente (POST cru).
            if local.get("tConfirmado") is None:
                falhas.append(f"{nome}: a paragem LOCAL não chegou ao servidor")
                continue
            if religamento.get("http") != 200:
                falhas.append(f"{nome}: o religamento por outro cliente devolveu HTTP "
                              f"{religamento.get('http')}")
                continue
            if not adocao.get("ok"):
                falhas.append(f"{nome}: o painel não adotou o modo religado por outro cliente "
                              f"(estado={adocao.get('estado')}, painel={adocao.get('painel')})")
                continue
            ultima = amostras[-1] if amostras else {}
            editados = [e for e in envios
                        if e["t"] >= cenario["tEdicao"] - TOL_APOS_CLIQUE_MS and _envio_apply_ativo(e)]
            ok_painel = painel["rajadas"] and painel["suprimido"] is None
            if ultima.get("modo") != "rajadas" or ultima.get("ativo") is not True:
                falhas.append(f"{nome}: o modo não ficou ativo depois da edição "
                              f"(servidor={ultima.get('modo')}/{ultima.get('ativo')})")
            elif ultima.get("p") is None or abs(float(ultima["p"]) - cenario["p"]) > 1e-9:
                falhas.append(f"{nome}: o PAINEL ESTÁ PRESO — a edição (p={cenario['p']}) não chegou ao "
                              f"servidor (p no servidor={ultima.get('p')!r}; POSTs de apply depois da "
                              f"edição: {[(e['t'], e['url']) for e in editados]})")
            elif not editados:
                falhas.append(f"{nome}: nenhum POST de apply saiu do painel depois da edição")
            elif not ok_painel:
                falhas.append(f"{nome}: o painel não mostra o modo ativo ({painel})")
            relatorio.append(f"· {nome} · paragem local aos {round(local['tConfirmado'] - local['t'])} ms · "
                             f"religamento (HTTP {religamento['http']}) · adoção do painel aos "
                             f"{round(adocao['t'] - religamento['t'])} ms · edição p={cenario['p']} -> "
                             f"servidor p={ultima.get('p')!r} · {len(amostras)} amostras · "
                             f"POST de apply aos "
                             f"{[round(e['t'] - cenario['tEdicao']) for e in editados]} ms depois da edição")
            continue
        # (a) paragem EXTERNA com um apply agendado pendente
        externa = cenario["externa"]
        primeiro = next((i for i, a in enumerate(amostras) if a["modo"] == "nenhum" and not a["ativo"]), None)
        voltou = [a for a in amostras if a["modo"] != "nenhum" or a["ativo"]]
        atrasados = [e for e in envios
                     if e["t"] > cenario["tExterna"] + TOL_APOS_CLIQUE_MS and _envio_apply_ativo(e)]
        ultima = amostras[-1] if amostras else {}
        base_ok = (ultima.get("vento_modo") == "nenhum" and ultima.get("vento_vel") is not None
                   and abs(float(ultima["vento_vel"])) <= TOL_TELE) if externa["tipo"] == "cru" \
            else ultima.get("vento_modo") not in MODOS_DINAMICOS
        painel_ok = painel["parado"] and not painel["rajadas"]
        aviso_ok = (painel["suprimido"] is not None) if externa["tipo"] == "cru" \
            else any("outra aba" in str(a) for a in painel["avisos"])
        if cenario["esperaParagemMs"] is None:
            falhas.append(f"{nome}: a paragem EXTERNA nunca chegou ao servidor (nenhuma amostra em "
                          f"nenhum/inativo) — o «outro cliente» não parou nada")
        elif primeiro is None or voltou:
            falhas.append(f"{nome}: o modo VOLTOU a ativar depois da paragem externa — o debounce local "
                          f"ressuscitou-o (amostras={[(a['t'], a['modo'], a['ativo']) for a in amostras[:12]]}, "
                          f"POSTs de apply depois da paragem="
                          f"{[(e['t'] - cenario['tExterna'], e['corpo']) for e in atrasados]})")
        elif atrasados:
            falhas.append(f"{nome}: o front mandou um apply dinâmico DEPOIS da paragem externa "
                          f"(POSTs={[(e['t'] - cenario['tExterna'], e['url'], e['corpo']) for e in atrasados]})")
        elif not base_ok:
            falhas.append(f"{nome}: a dinâmica continua a atuar depois da paragem externa "
                          f"(vento_modo={ultima.get('vento_modo')!r} vento={ultima.get('vento_vel')})")
        elif not painel_ok:
            falhas.append(f"{nome}: o painel não reflete o servidor depois da paragem externa "
                          f"(painel={painel})")
        elif not aviso_ok:
            falhas.append(f"{nome}: o utilizador não foi avisado de que a edição não foi aplicada "
                          f"(aviso de «não aplicado»={painel['suprimido']!r}; avisos={painel['avisos']})")
        else:
            relatorio.append(
                f"· {nome} · paragem {'crua' if externa['tipo'] == 'cru' else 'na 2.ª aba'} aos "
                f"{round(cenario['tExterna'] - cenario['tEdicao'])} ms depois da edição · servidor parado "
                f"em {cenario['esperaParagemMs']} ms · {len(amostras)} amostras TODAS inativas "
                f"({round(amostras[-1]['t'] / 1000, 2)} s) · 0 POSTs de apply depois da paragem · "
                f"painel: PARADO={painel['parado']} RAJADAS={painel['rajadas']} "
                f"aviso={'sim' if aviso_ok else 'NÃO'} · {fim['polls']} polls atrasados do site")
    for cenario in dados["cenarios"]:
        fim = cenario.get("fim") or {}
        if fim.get("envios"):
            relatorio.append(f"POSTs do front · {cenario['nome']}: "
                             + " · ".join(f"{round(e['t'] - cenario['tEdicao'])}ms:{e['url']} {e['corpo']}"
                                          for e in fim["envios"]))
    for falha in falhas:
        relatorio.append(f"FALHOU: {falha}")
    return not falhas, relatorio


# ------------------------------------------------------- prova de NÃO-TAUTOLOGIA (mutação do front)
# Uma prova nova pode estar verde por não medir nada. Aqui desliga-se UMA defesa de cada vez, nas fontes do
# front, compila-se o site com elas e correm-se os MESMOS cenários: eles TÊM de FALHAR (o cenário que fica
# verde é o que não estava a medir a defesa). A troca é textual e CONFERIDA (se a linha já não existir,
# aborta em vez de fingir que mutou).
MUTACOES_FRONT = (
    ("sem-revalidacao", "src/lib/paragem.ts",
     "        estado = await leitor()",
     "        estado = { modo: opcoes.modo, ativo: true }",
     ("cru", "aba"),
     "a revalidação passa a dizer sempre «ativo»: o apply volta a ressuscitar o modo que OUTRO cliente parou"),
    ("sem-desbloqueio-remoto", "src/lib/paragem.ts",
     "  if (emitidoEm >= instanteParagem) bloqueado = false",
     "  if (emitidoEm >= instanteParagem && emitidoEm < 0) bloqueado = false",
     ("preso",),
     "o bloqueio do live-apply deixa de ser levantado pela adoção do modo vindo do servidor (painel preso)"),
)


def escrever_front_mutado(destino: Path, arquivo: str, alvo: str, troca: str) -> Path:
    """Copia as fontes do front para `destino` com UMA linha trocada (a mutação), conferindo a troca."""
    destino.mkdir(parents=True, exist_ok=True)
    for rel in FRONT_RELATIVOS:
        conteudo = (SITE / rel).read_text(encoding="utf-8")
        if rel == arquivo:
            if alvo not in conteudo:
                raise SystemExit(f"[teste] mutação impossível: a linha {alvo!r} já não está em {rel} "
                                 "(o front mudou? atualize MUTACOES_FRONT)")
            conteudo = conteudo.replace(alvo, troca, 1)
        (destino / Path(rel).name).write_text(conteudo, encoding="utf-8")
    return destino


def prova_mutacao(pasta: Path, modelo: Path, fator_tempo: float, porta: int, atraso_poll: int,
                  janela_ms: int) -> tuple[bool, list[str]]:
    """Corre os cenários multi-cliente com o front MUTADO (uma defesa desligada) e espera que FALHEM.

    Devolve `(ok, relatorio)`: `ok` = todas as mutações fizeram o cenário correspondente falhar (prova de
    que o cenário mede mesmo a defesa) e o front da árvore voltou a compilar no fim.
    """
    import tempfile

    relatorio: list[str] = []
    falhas: list[str] = []
    raiz_mutacoes = Path(tempfile.mkdtemp(prefix="front_mutado_", dir=str(pasta)))
    for nome, arquivo, alvo, troca, quais, descricao in MUTACOES_FRONT:
        destino = escrever_front_mutado(raiz_mutacoes / nome, arquivo, alvo, troca)
        relatorio.append(f"· mutação «{nome}» ({arquivo}: {alvo.strip()} -> {troca.strip()}) — {descricao}")
        with _fontes_front(destino):
            ok, linhas = checa_multicliente(pasta, modelo, fator_tempo, porta, atraso_poll, quais, janela_ms)
        for linha in linhas:
            if linha.startswith(("FALHOU:", "·")):
                relatorio.append(f"    {linha}")
        if ok:
            falhas.append(f"mutação «{nome}»: os cenários {list(quais)} continuaram VERDES com a defesa "
                          "desligada — o teste não está a medir essa defesa (tautologia)")
            relatorio.append(f"    PROVA FALHOU: com «{nome}» os cenários deviam falhar e passaram")
        else:
            relatorio.append(f"    prova OK: com «{nome}» os cenários {list(quais)} FALHARAM como esperado")
    shutil.rmtree(raiz_mutacoes, ignore_errors=True)
    for falha in falhas:
        relatorio.append(f"FALHOU: {falha}")
    return not falhas, relatorio


def _fontes_front(front: Path | None):
    """Contexto que compila o site com as fontes de OUTRA pasta (o front de antes da correção).

    Copia `controlos.tsx`/`use-sim.ts`/`App.tsx`/`paragem.ts` (`FRONT_RELATIVOS`) da pasta indicada para a
    árvore, corre `npm run build`, devolve o controle e no fim REPÕE as fontes da árvore e volta a compilar.
    É a prova dos defeitos (2)/(3): o MESMO teste, contra o front de antes. `front=None` = árvore de
    trabalho (não compila nada). A pasta tem de trazer as QUATRO fontes (as defesas multi-cliente vivem em
    `lib/paragem.ts`); para a mutação automática use `--mutacao`, que as escreve sozinho.
    """
    import contextlib

    @contextlib.contextmanager
    def contexto():
        if front is None:
            yield
            return
        originais = {rel: (SITE / rel).read_bytes() for rel in FRONT_RELATIVOS}
        try:
            for rel in FRONT_RELATIVOS:
                alternativo = front / Path(rel).name
                if not alternativo.is_file():
                    raise SystemExit(f"[teste] --front {front}: falta {alternativo.name} (a pasta tem de "
                                     f"trazer as fontes {[Path(r).name for r in FRONT_RELATIVOS]})")
                shutil.copyfile(alternativo, SITE / rel)
            codigo, saida = _compilar_site()
            if codigo != 0:
                raise SystemExit(f"[teste] npm run build falhou com as fontes de {front}:\n{saida[-1500:]}")
            yield
        finally:
            for rel, conteudo in originais.items():
                (SITE / rel).write_bytes(conteudo)
            codigo, saida = _compilar_site()
            if codigo != 0:
                raise SystemExit(f"[teste] ATENÇÃO: repus as fontes mas o npm run build falhou:\n"
                                 f"{saida[-1500:]}")

    return contexto()


def _compilar_site() -> tuple[int, str]:
    """`npm run build` em `site/` (tsc -b + vite). Devolve `(código, saída)`. Não precisa de `~/.secrets`:
    o `node_modules/` já está instalado (só o `npm install` do registo privado é que precisa)."""
    npm = _binario(("npm",))
    if npm is None:
        return 1, "npm não encontrado"
    if not (SITE / "node_modules").is_dir():
        return 1, f"{SITE / 'node_modules'} não existe — corra `npm install` em {SITE}"
    feito = subprocess.run([npm, "run", "build"], cwd=str(SITE), capture_output=True, text=True,
                           timeout=600, check=False)
    return feito.returncode, (feito.stdout or "") + (feito.stderr or "")


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
                   help="acrescenta a prova ponta a ponta com o FRONT real num Chrome headless: os TRÊS "
                        "caminhos de paragem (PARAR VENTO, PARAR DINÂMICO e o toggle PARADO) não podem "
                        "deixar um apply atrasado reativar o modo; janelas 0/50/100/300/600/1000 ms + "
                        "controlo positivo; e os cenários MULTI-CLIENTE (paragem por `POST /api/parar` cru, "
                        "paragem por uma 2.ª aba real, religamento remoto + edição local); precisa de node, "
                        "Chrome e `npm run build` feito")
    p.add_argument("--so-multi", action="store_true",
                   help="salta a matriz de janelas × caminhos da prova --navegador e corre só os cenários "
                        "multi-cliente (é o que a prova de mutação usa)")
    p.add_argument("--mutacao", action="store_true",
                   help="prova de NÃO-TAUTOLOGIA: corre os cenários multi-cliente com o front da árvore e "
                        "depois com cada defesa NOVA desligada (fontes mutadas, compiladas e repostas no "
                        "fim) — cada mutação TEM de fazer falhar os cenários dela (implica --navegador "
                        "--so-multi)")
    p.add_argument("--janela-multi", type=int, default=2600, metavar="MS",
                   help="janela de amostragem dos cenários multi-cliente, em ms (padrão: 2600)")
    p.add_argument("--front", type=Path, default=None, metavar="DIR",
                   help="pasta com controlos.tsx/use-sim.ts/App.tsx/lib/paragem.ts (o front de ANTES da "
                        "correção): compila o site com eles, corre as provas de navegador e "
                        "repõe+recompila no fim — é a prova dos defeitos (2)/(3) com um comando")
    p.add_argument("--sem-cenarios", action="store_true",
                   help="salta os cenários ao nível do runner (útil para repetir só as provas --http / "
                        "--navegador)")
    p.add_argument("--atraso-poll", type=int, default=500, metavar="MS",
                   help="atraso imposto à RESPOSTA do `GET /api/sim` do site na prova --navegador (padrão: "
                        "500 ms). É o que torna o defeito determinístico: o cancelamento do apply "
                        "agendado depende do POLLING, e com o poll instantâneo do loopback a janela tem "
                        "~10 ms (o defeito escapa quase sempre)")
    p.add_argument("--deltas", default="0,50,100,300,600,1000", metavar="MS,MS,…",
                   help="janelas da prova --navegador, em ms (padrão: 0,50,100,300,600,1000) — cada janela "
                        "corre os TRÊS caminhos de paragem e o controlo positivo")
    p.add_argument("--porta", type=int, default=8481,
                   help="porta do servidor das provas de navegador (padrão: 8481)")
    p.add_argument("--model", type=Path, default=None, help="modelo para a prova --http (padrão: o do site)")
    p.add_argument("--pasta", type=Path, default=None, metavar="DIR",
                   help="onde escrever controlo/telemetria do teste (padrão: pasta temporária)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = analisar_argumentos(argv)
    if args.mutacao:                 # a prova de mutação corre os cenários multi contra o front mutado
        args.navegador = True
        args.so_multi = True
    if args.navegador and args.front is not None and args.mutacao:
        raise SystemExit("[teste] --front e --mutacao juntos não fazem sentido: a mutação escreve as "
                         "próprias fontes")
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
    if not args.sem_cenarios:
        print(f"[teste] {len(CENARIOS)} cenários ao nível do runner (ciclo REAL do sim_view.correr)\n")

    banco = Banco(pasta, fator_tempo=args.fator_tempo)
    banco.arrancar()
    falhas: list[str] = []
    try:
        for cen in (() if args.sem_cenarios else CENARIOS):
            try:
                relatorio = correr_cenario(banco, cen)
            except SystemExit as erro:                    # espera estourada: conta como falha do cenário
                print(f"[FALHA] {cen.nome}\n        {erro}")
                falhas.append(f"{cen.nome}: {erro}")
                continue
            ruins = [nome for nome, ok in relatorio["checagens"].items() if not ok]
            print(f"[{'OK  ' if not ruins else 'FALHA'}] {relatorio['nome']}")
            print(f"        base comandada = {relatorio['base']} · modos depois do PARAR = "
                  f"{relatorio['modos']} · pior desvio = {relatorio['pior_desvio']:.3e} m/s · "
                  f"{relatorio['amostras']} amostras de telemetria")
            if ruins:
                for nome in ruins:
                    print(f"        · FALHOU: {nome}")
                print(f"        resíduos: {json.dumps(relatorio['residuos'], default=str)}")
                falhas.append(f"{relatorio['nome']}: {', '.join(ruins)}")
    finally:
        banco.parar()

    total = 0 if args.sem_cenarios else len(CENARIOS)
    total += 1
    print("\n[teste] defeito (1) — escritas concorrentes na mesma via do servidor (in-process)")
    ok_conc, linhas = checa_concorrencia_inprocess(pasta)
    for linha in linhas:
        print(f"        {linha}")
    print(f"[{'OK  ' if ok_conc else 'FALHA'}] escritas concorrentes sem 500/JSON partido/comando perdido")
    if not ok_conc:
        falhas.append("concorrência in-process")
    modelo = args.model
    if (args.http or args.navegador) and modelo is None:
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
            print(f"[{'OK  ' if ok else 'FALHA'}] PARAR pelo HTTP + tempestade de POSTs concorrentes")
            if not ok:
                falhas.append("ponta a ponta pelo HTTP / concorrência")
    if args.navegador and not args.so_multi:
        deltas = tuple(int(v) for v in str(args.deltas).replace(" ", "").split(",") if v != "")
        print(f"\n[teste] ponta a ponta com o FRONT real num Chrome headless (janelas {list(deltas)} ms × "
              f"{len(PARAGENS)} caminhos de paragem + controlo, atraso do poll {args.atraso_poll} ms)")
        if modelo is None:
            print("        AVISO: sem modelo — o runner não corre e a telemetria não existe; salto")
        else:
            total += 1
            print(f"        fontes do front: {args.front if args.front is not None else 'árvore de trabalho'}")
            with _fontes_front(args.front):
                ok, relatorio = checa_navegador(pasta, modelo, args.fator_tempo, deltas, args.porta,
                                                args.atraso_poll)
            for linha in relatorio:
                print(f"        {linha}")
            print(f"[{'OK  ' if ok else 'FALHA'}] nenhum apply atrasado reativa o modo depois de PARAR VENTO / "
                  "PARAR DINÂMICO / PARADO")
            if not ok:
                falhas.append("corrida do debounce do front (--navegador)")
    if args.navegador:
        print(f"\n[teste] MULTI-CLIENTE: paragem por OUTRO cliente (POST /api/parar cru e PARAR DINÂMICO "
              f"numa 2.ª aba real) com um apply agendado, e o painel preso (religamento remoto + edição "
              f"local), atraso do poll {args.atraso_poll} ms, janela {args.janela_multi} ms")
        if modelo is None:
            print("        AVISO: sem modelo — o runner não corre e a telemetria não existe; salto")
        else:
            print(f"        fontes do front: {args.front if args.front is not None else 'árvore de trabalho'}")
            total += 1
            with _fontes_front(args.front):
                ok, relatorio = checa_multicliente(pasta, modelo, args.fator_tempo, args.porta,
                                                   args.atraso_poll, (), args.janela_multi)
            for linha in relatorio:
                print(f"        {linha}")
            print(f"[{'OK  ' if ok else 'FALHA'}] uma paragem de OUTRO cliente mata o apply pendente e o "
                  "painel volta a aplicar depois de um religamento remoto")
            if not ok:
                falhas.append("paragens multi-cliente / painel preso (--navegador)")
    if args.mutacao:
        print("\n[teste] NÃO-TAUTOLOGIA (mutação do front): cada defesa NOVA desligada tem de fazer FALHAR "
              "os cenários que ela protege")
        if modelo is None:
            print("        AVISO: sem modelo — salto a prova de mutação")
        else:
            total += 1
            ok, relatorio = prova_mutacao(pasta, modelo, args.fator_tempo, args.porta, args.atraso_poll,
                                          args.janela_multi)
            for linha in relatorio:
                print(f"        {linha}")
            print(f"[{'OK  ' if ok else 'FALHA'}] os cenários multi-cliente medem mesmo as defesas novas "
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
