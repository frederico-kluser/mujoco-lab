#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_arranque_loop.py — PROVA do arranque SEM REINÍCIO (dono, 2026-10-09).

Pedido do dono (2026-10-09): o simulador ARRANCA sempre com o loop DESLIGADO e «SEM REINÍCIO» ativo — isto é,
o toggle `CONTÍNUO | SEM REINÍCIO` nasce no estado SEM REINÍCIO. A semântica (registada, confirmada):

  · `loop: true`  = **CONTÍNUO**: no fim do episódio o runner faz reset e segue (ep+1, passo 0) sem parar a
    física;
  · `loop: false` = **SEM REINÍCIO**: a física NUNCA para nem reinicia — no fim do episódio continua a
    integrar no estado em que ficou (`passo`/`t` crescem para lá do fim do episódio e o `retorno` fica fixo)
    e SÓ o REINICIAR (contador atómico no ficheiro de controlo) recomeça;
  · o `loop` é **STICKY**: o ARRANQUE é autoritativo e corrige o `loop` que estiver no ficheiro; depois
    disso, só o `POST /api/loop` do site o muda — escritas parciais (vento, dinâmica) nunca lhe tocam.

Este script prova, por comando, as cinco coisas pedidas:

  (a) ARRANQUE EM FRESCO (sem ficheiro de controlo): o ficheiro nasce com `loop: false` e o episódio NÃO se
      auto-reinicia — depois de fechar, o `passo`/`t` continuam a crescer, o `ep` fica no mesmo e o `retorno`
      congela; o REINICIAR é o único reset (e funciona);
  (b) ARRANQUE COM `loop: true` VELHO: o arranque corrige o ficheiro para `false` (preservando vento,
      dinâmica e — sobretudo — o contador `reiniciar`) e corre SEM REINÍCIO;
  (c) DEPOIS DO ARRANQUE o CONTÍNUO liga-se pelo site (`POST /api/loop`) e é STICKY: a escrita parcial
      seguinte (`POST /api/vento`) não lhe toca e o runner passa mesmo a auto-reiniciar; desligar volta a
      SEM REINÍCIO. Apagar (ou corromper) o ficheiro de controlo a meio é a mesma coisa — a recriação leva o
      `loop` do último POST e o contador `reiniciar` efetivos (§3e, com o servidor real);
  (d) As FLAGS: `--com-loop` (alias antigo `--loop`) liga o CONTÍNUO — no runner e no site, que o repassa ao
      filho — e corrige um `loop: false` velho; `--sem-loop` é o mesmo que a omissão (explícito e
      idempotente) e corrige um `loop: true` velho; as duas juntas são recusadas.
  (e) CORRIDA DE ARRANQUE (defeito medido, 2026-10-09): um `POST /api/loop` feito ASSIM QUE a porta do
      servidor responde — com o runner ainda a arrancar (e aqui com um atraso ARTIFICIAL imposto ao runner,
      para a janela ficar larga e determinística) — NUNCA é revertido pelo `fixar_loop`, e o CONTINÚO fica
      mesmo em vigor (o runner auto-reinicia). O site carimba a escrita de arranque (`loop_arranque`) e
      passa o token ao filho; o POST limpa o carimbo e o runner respeita-o (ver `sim_view.fixar_loop`).

Três camadas, para a prova ser barata e mesmo assim ponta a ponta:

  §1 PEÇAS — as funções do arranque (`loop_do_arranque`, `fixar_loop`, `nome_temporario`, os dois argparse e
     o `comando_do_runner`) exercitadas directamente, sem simulação;
  §2 CICLO REAL — `sim_view.correr` a correr a sério (`HoverEnv` + política de ação nula, sem modelo
     treinado) no fio principal e as checagens num fio auxiliar: prova no CONTADOR DA FÍSICA
     (`env.passos`/`env.data.time`) que SEM REINÍCIO não há reset nenhum (nem um) e que com `--com-loop` há
     auto-reset;
  §3 SERVIDOR REAL — `sim_site.py` + runner + API a sério (3 arranques: fresco, ficheiro velho com
     `loop: true`, e `--com-loop`), com `POST /api/reiniciar`, `POST /api/loop` e `POST /api/vento`, mais o
     §3e: o ficheiro de controlo APAGADO e CORROMPIDO a meio da execução (a escrita parcial que o recria não
     pode tocar no `loop` nem no contador `reiniciar`);
  §4 FRONT REAL — o BUNDLE de `site/dist` servido pelo `sim_site.py` num Chrome headless, lido no DOM por
     CDP: o toggle CONTINUIDADE mostra **SEM REINÍCIO ativo no arranque** e muda mesmo quando o backend muda
     (`POST /api/loop`) — o controlo negativo que separa «UI a espelhar o backend» de «fallback do React».
  §5 CORRIDA DE ARRANQUE — o servidor real, mas com o POST de `loop` disparado no instante em que a porta
     responde, 3 corridas, cada uma com um atraso artificial imposto ao runner (para a janela de arranque
     ser larga e determinística): o `loop` nunca volta a `false`, o runner diz que RESPEITOU o POST e o modo
     efetivo é o CONTÍNUO (auto-reset provado na telemetria).

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_arranque_loop.py             # tudo
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_arranque_loop.py --sem-http  # §1+§2
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_arranque_loop.py --sem-navegador
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_arranque_loop.py --fator-tempo 3
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_arranque_loop.py --fontes "$TMPDIR/snap"

`--fontes DIR` (como no `teste_parar_vento.py`) corre o MESMO teste contra as fontes de OUTRA pasta —
`env.py` + `sim_view.py` + `sim_site.py` copiados para `_AQUI/.fontes_antes` (apagada no fim, sem lixo): é a
prova de que o §5 FALHAVA antes do reparo (basta guardar os três ficheiros de antes numa pasta de `$TMPDIR`).
Como essa cópia é SÓ CÓDIGO, o modelo do runner (o `out/` com os `.zip`) é procurado automaticamente na
árvore do laboratório — e, se não houver modelo nenhum, o teste FALHA ALTO (exit 1) em vez de saltar em
silêncio o §3/§4/§5, que o cabeçalho promete.

Exit 0 = todas as checagens passam; 1 = alguma falha (diz qual e mostra o diagnóstico).
"""
from __future__ import annotations

import argparse
import atexit
import contextlib
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Self

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def _estagiar_fontes(origem: Path) -> Path:
    """Fontes alternativas de `origem` (pode estar FORA do repo) copiadas para `_AQUI/.fontes_antes`.

    Os módulos procuram o `pyproject.toml` acima deles, por isso uma pasta fora da árvore do laboratório não
    serve: a cópia é estagiada DENTRO da árvore (`_AQUI/.fontes_antes`, removida no fim do processo) e entra
    PRIMEIRO no `sys.path`. É o que permite guardar as fontes de antes em `$TMPDIR` e correr este teste — o
    MESMO teste, sem uma linha de diferença — contra elas (a prova §5 de que a corrida de arranque falhava
    antes do reparo). Mesma ideia do `--fontes` do `teste_parar_vento.py`.
    """
    if _RAIZ in origem.parents:
        return origem                                    # já está na árvore: usa-se tal e qual
    faltam = [nome for nome in ("env.py", "sim_view.py", "sim_site.py") if not (origem / nome).is_file()]
    if faltam:
        raise SystemExit(f"[teste] --fontes {origem}: faltam {', '.join(faltam)}")
    destino = _AQUI / ".fontes_antes"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    for nome in ("env.py", "sim_view.py", "sim_site.py"):
        shutil.copyfile(origem / nome, destino / nome)
    atexit.register(shutil.rmtree, destino, ignore_errors=True)
    print(f"[teste] fontes de {origem} estagiadas em {destino} (apagadas no fim)")
    return destino


def _pasta_fontes(argv: list[str]) -> Path | None:
    """`--fontes DIR` / `--fontes=DIR`: fontes alternativas pedidas ANTES dos imports (vencem as da árvore)."""
    for i, arg in enumerate(argv):
        if arg == "--fontes" and i + 1 < len(argv):
            return _estagiar_fontes(Path(argv[i + 1]).expanduser().resolve())
        if arg.startswith("--fontes="):
            return _estagiar_fontes(Path(arg.split("=", 1)[1]).expanduser().resolve())
    return None


# As fontes alternativas entram PRIMEIRO no `sys.path` — a ordem do `insert(0, …)` é invertida, por isso a
# lista vai da MENOS para a MAIS prioritária.
_FONTES = _pasta_fontes(sys.argv[1:])
for _caminho in (_RAIZ, _AQUI, _FONTES):
    if _caminho is not None:
        sys.path.insert(0, str(_caminho))

# O servidor do §3/§5 é lançado por CAMINHO: com `--fontes` tem de ser o da pasta estagiada (senão o teste
# media a árvore, não as fontes de antes) — e o `sim_view.py` que ELE lança vem de lá sozinho.
_SIM_SITE = (_FONTES or _AQUI) / "sim_site.py"

from lab import mjkit  # noqa: F401, I001  (define MUJOCO_GL=egl ANTES do `import mujoco`, como no sim_view)

import numpy as np

import env as modulo_env
import sim_site
import sim_view

ARRANQUE_S = 180.0        # limite para o servidor real dizer o URL
ESPERA_S = 120.0          # limite genérico das esperas do §3 (a máquina pode estar ocupada)
JANELA_S = 60.0           # limite das observações do §2 (fator-tempo 0: um episódio em ~0,1 s)
FATOR_TEMPO = 3.0         # §3: 3x o tempo real — um episódio de 500 passos fecha em ~3,4 s
PORTA_NAVEGADOR = 8441    # §4: porta do servidor que serve o front ao Chrome (a do laboratório para testes)
PORTA_CORRIDA = 8463      # §5: porta do servidor da corrida de arranque (a do laboratório para testes)
ATRASO_RUNNER = 4.0       # §5: atraso ARTIFICIAL do arranque do runner (s) — alarga a janela do defeito
PRAZO_CORRIDA = 15.0      # §5: teto da espera pelo modo efetivo (atraso + imports + fim do 1.º episódio)
CORRIDAS = 3              # §5: corridas do cenário (≥ 3, pedido do dono)
# Controlo VELHO (o que uma sessão anterior deixou no disco): `loop: true` + contador de REINICIAR + vento.
BASE_VELHO = {"vel": 3.0, "azimute": 90.0, "elevacao": 0.0, "ativo": True, "reiniciar": 7, "loop": True,
              "dinamico": {"modo": "nenhum", "params": {}, "ativo": False, "seq": 1}}
# Casos das flags: (nome, argv, o que o arranque tem de decidir).
CASOS_FLAG = (("(omissao)", [], False), ("--sem-loop", ["--sem-loop"], False),
              ("--com-loop", ["--com-loop"], True), ("--loop (alias)", ["--loop"], True))


# Carimbo do arranque: o nome vem das fontes em teste (as de ANTES do reparo não o têm — e é isso mesmo que
# o §5 mede); sem ele, `dados.get(...)` é sempre `None` e nenhuma checagem rebenta com AttributeError.
_CARIMBO = getattr(sim_site, "CAMPO_ARRANQUE", "loop_arranque")


# ------------------------------------------------------------------------------------------------ checagens
class Checagens:
    """Acumulador de checagens: imprime UMA linha por checagem (com o detalhe medido) e guarda as falhas."""

    def __init__(self, titulo: str) -> None:
        self.titulo = titulo
        self.linhas: list[str] = []
        self.falhas: list[str] = []

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.linhas.append(nome)
        if not cond:
            self.falhas.append(nome)
        print(f"        [{'OK  ' if cond else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""),
              flush=True)
        return bool(cond)


def _titulo(titulo: str) -> None:
    print(f"\n[teste] {titulo}", flush=True)


def _linha_de(linhas: list[str], marca: str) -> str:
    """Primeira linha do stdout do servidor que contém `marca` (o que ele disse, tal e qual)."""
    return next((linha for linha in linhas if marca in linha), "<sem essa linha no stdout>")


# ---------------------------------------------------------------------------------------- utilidades HTTP
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


def _t(estado: dict) -> float:
    """`t` de simulação da ÚLTIMA amostra de `/api/sim` (o resumo do topo não traz o `t`)."""
    linhas = estado.get("linhas") or []
    return float(linhas[-1].get("t", 0.0)) if linhas else 0.0


def _modelo_do_teste() -> tuple[Path | None, str]:
    """`(caminho, motivo)` do modelo do §3/§4/§5 — o mesmo que o site escolheria para o runner.

    As fontes estagiadas por `--fontes` são SÓ CÓDIGO (`env.py` + `sim_view.py` + `sim_site.py`): o `out/`
    com os modelos fica na ÁRVORE do laboratório. Sem este desvio, o `modelo_por_omissao` das fontes
    estagiadas procurava `.fontes_antes/out`, não achava nada e o §3/§5 eram SALTADOS em silêncio (com um
    AVISO e exit 0) — apesar de o cabeçalho prometer que é essa a via que prova o §5 (defeito medido). Aqui
    procura-se no sítio natural das fontes em teste e, se elas não trouxerem `out/`, na árvore; sem modelo
    NENHUM devolve `(None, motivo)` e quem chama FALHA ALTO em vez de saltar provas prometidas.
    """
    tentativas: list[str] = []
    try:
        return sim_site.modelo_por_omissao()
    except SystemExit as erro:
        tentativas.append(f"fontes em teste ({sim_site.__file__}): {erro}")
    if _FONTES is not None:
        # `modelo_por_omissao` resolve os modelos a partir do `_AQUI` do MÓDULO: apontado à árvore durante a
        # escolha, é o `out/` do laboratório que serve (o `_RAIZ` das fontes estagiadas já é o mesmo, e as
        # fontes são uma cópia do código). O `_AQUI` original é reposto logo a seguir, sempre.
        original = sim_site._AQUI                     # desvio temporário, reposto no `finally`
        try:
            sim_site._AQUI = _AQUI
            modelo, motivo = sim_site.modelo_por_omissao()
            return modelo, (f"{motivo} · procurado na ARVORE ({_AQUI / 'out'}): as fontes do `--fontes` só "
                            "trazem codigo")
        except SystemExit as erro:
            tentativas.append(f"arvore ({_AQUI}): {erro}")
        finally:
            sim_site._AQUI = original
    return None, " | ".join(tentativas)


# ==================================================================================================== §1
def checa_pecas(pasta: Path) -> Checagens:
    """§1: as peças do arranque (sem simulação) — é aqui que o default `false` tem de estar declarado."""
    c = Checagens("§1 pecas do arranque (in-process, sem simulacao)")
    _titulo(c.titulo)

    c.ok("default SEM REINICIO nas duas pecas (`sim_site.CONTROLO_INICIAL`, `sim_view.Estado`, "
         "`loop_em_vigor` sem dados)",
         sim_site.CONTROLO_INICIAL.get("loop") is False and sim_view.Estado().loop is False
         and sim_site.loop_em_vigor({}, {}) is False,
         f"CONTROLO_INICIAL.loop={sim_site.CONTROLO_INICIAL.get('loop')!r} · "
         f"Estado().loop={sim_view.Estado().loop!r} · loop_em_vigor({{}},{{}})="
         f"{sim_site.loop_em_vigor({}, {})!r}")

    visto_runner = {nome: sim_view.loop_do_arranque(sim_view.analisar_argumentos(["--sem-janela", *argv]))
                    for nome, argv, _alvo in CASOS_FLAG}
    c.ok("runner: omissao/`--sem-loop` -> SEM REINICIO; `--com-loop` e o alias `--loop` -> CONTINUO",
         visto_runner == {nome: alvo for nome, _argv, alvo in CASOS_FLAG},
         f"loop_do_arranque = {visto_runner}")

    visto_site = {nome: sim_site.analisar_argumentos(["--sem-browser", *argv]).com_loop
                  for nome, argv, _alvo in CASOS_FLAG}
    c.ok("site: `--com-loop`/`--loop` ligam o continuo; a omissao e o `--sem-loop` nao",
         visto_site == {nome: alvo for nome, _argv, alvo in CASOS_FLAG}, f"com_loop = {visto_site}")

    recusados = []
    for modulo, argv in ((sim_view, ["--sem-janela", "--com-loop", "--sem-loop"]),
                         (sim_site, ["--sem-browser", "--com-loop", "--sem-loop"])):
        try:
            with contextlib.redirect_stderr(io.StringIO()):     # o argparse escreve o uso em stderr
                modulo.analisar_argumentos(argv)
            recusados.append(f"{modulo.__name__}: aceitou as duas flags!")
        except SystemExit as erro:
            recusados.append(f"{modulo.__name__}: exit {erro.code}")
    c.ok("`--com-loop` e `--sem-loop` sao mutuamente exclusivas (erro de uso, exit 2)",
         all("exit 2" in linha for linha in recusados), " · ".join(recusados))

    padrao = sim_site.comando_do_runner(sim_site.analisar_argumentos(["--sem-browser"]))
    pedido = sim_site.comando_do_runner(sim_site.analisar_argumentos(["--sem-browser", "--com-loop"]))
    explicito = sim_site.comando_do_runner(sim_site.analisar_argumentos(["--sem-browser", "--sem-loop"]))
    c.ok("linha de comandos do runner sempre EXPLICITA (`--sem-loop` por omissao; `--com-loop` com a flag)",
         "--sem-loop" in padrao and "--com-loop" not in padrao
         and "--com-loop" in pedido and "--sem-loop" not in pedido and "--sem-loop" in explicito,
         f"omissao -> {padrao[-1]} · --com-loop -> {pedido[-1]} · --sem-loop -> {explicito[-1]}")

    velho = pasta / "pecas_velho.json"
    velho.write_text(json.dumps({**BASE_VELHO, "t": 123.0}) + "\n", encoding="utf-8")
    antes = json.loads(velho.read_text(encoding="utf-8"))
    corrigiu = sim_view.fixar_loop(velho, False)
    depois = json.loads(velho.read_text(encoding="utf-8"))
    preservado = all(depois.get(chave) == valor for chave, valor in antes.items() if chave not in ("loop", "t"))
    c.ok("`fixar_loop(false)` corrige um `loop: true` velho e preserva vento, dinamica e `reiniciar`",
         corrigiu is True and depois.get("loop") is False and preservado
         and depois.get("reiniciar") == 7 and isinstance(depois.get("t"), float),
         f"loop {antes.get('loop')!r} -> {depois.get('loop')!r} · reiniciar={depois.get('reiniciar')!r} · "
         f"vel={depois.get('vel')!r} · dinamico={'dinamico' in depois} · t={depois.get('t')!r}")

    congelado = json.loads(velho.read_text(encoding="utf-8"))
    c.ok("`fixar_loop` e idempotente (a 2.a chamada nao toca no ficheiro)",
         sim_view.fixar_loop(velho, False) is False
         and json.loads(velho.read_text(encoding="utf-8")) == congelado,
         f"2.a chamada devolveu {sim_view.fixar_loop(velho, False)!r} e o ficheiro ficou igual")

    novo = pasta / "pecas_novo.json"
    novo.unlink(missing_ok=True)
    criou = sim_view.fixar_loop(novo, False)
    dados = json.loads(novo.read_text(encoding="utf-8"))
    c.ok("`fixar_loop` num ficheiro AUSENTE cria-o com `loop: false` e os campos do contrato",
         criou is True and dados.get("loop") is False and dados.get("vel") == 0.0
         and dados.get("ativo") is False and dados.get("reiniciar") == 0, f"ficheiro criado = {dados}")

    c.ok("`fixar_loop(true)` tambem e autoritativo (corrige um `loop: false` velho, como o `--com-loop`)",
         sim_view.fixar_loop(velho, True) is True
         and json.loads(velho.read_text(encoding="utf-8")).get("loop") is True
         and sim_view.fixar_loop(velho, False) is True, "false -> true -> false, com o ficheiro a segui-lo")

    nomes = {str(sim_view.nome_temporario(velho)) for _ in range(3)}
    nomes |= {str(sim_site.nome_temporario(velho)) for _ in range(3)}
    orfaos = sorted(p.name for p in pasta.glob(".*.tmp*"))
    c.ok("temporario da escrita atomica com nome UNICO por escrita (view e site) e 0 `.tmp` orfaos",
         len(nomes) == 6 and not orfaos, f"{len(nomes)} nomes distintos · orfaos={orfaos}")

    sim_site.escrever_controlo(velho, {"vel": 2.5})
    dados = json.loads(velho.read_text(encoding="utf-8"))
    c.ok("escrita parcial (vento) NAO toca em `loop` nem em `reiniciar` (sticky)",
         dados.get("loop") is False and dados.get("reiniciar") == 7 and dados.get("vel") == 2.5,
         f"loop={dados.get('loop')!r} · reiniciar={dados.get('reiniciar')!r} · vel={dados.get('vel')!r}")

    tem_handshake = (hasattr(sim_view, "token_do_arranque") and hasattr(sim_view, "CAMPO_ARRANQUE")
                     and hasattr(sim_view, "ENV_LOOP_ARRANQUE") and hasattr(sim_site, "CAMPO_ARRANQUE")
                     and hasattr(sim_site, "ENV_LOOP_ARRANQUE"))
    c.ok("handshake do arranque presente nas duas pecas com os MESMOS nomes (carimbo + variavel de ambiente)",
         tem_handshake and sim_view.CAMPO_ARRANQUE == sim_site.CAMPO_ARRANQUE == "loop_arranque"
         and sim_view.ENV_LOOP_ARRANQUE == sim_site.ENV_LOOP_ARRANQUE,
         "carimbo/variavel AUSENTES nestas fontes (anteriores ao reparo)" if not tem_handshake else
         f"sim_view: {sim_view.CAMPO_ARRANQUE!r}/{sim_view.ENV_LOOP_ARRANQUE!r} · "
         f"sim_site: {sim_site.CAMPO_ARRANQUE!r}/{sim_site.ENV_LOOP_ARRANQUE!r}")
    if not tem_handshake:                                # fontes de ANTES do reparo: o §5 mede o defeito
        c.ok("[CORRIDA] com estas fontes o `fixar_loop` nao tem como distinguir um POST de um valor velho: a "
             "corrida de arranque (defeito) nao pode ser respeitada por construcao", False,
             "sem `loop_arranque`/`DRONE_LOOP_ARRANQUE` nas pecas — ver o §5 (falha esperada nas fontes de "
             "antes do reparo)")
        return c

    c.ok("`token_do_arranque`: le a variavel do site e da `None` num arranque DIRECTO (sem handshake)",
         sim_view.token_do_arranque({sim_view.ENV_LOOP_ARRANQUE: "abc"}) == "abc"
         and sim_view.token_do_arranque({}) is None
         and sim_view.token_do_arranque({sim_view.ENV_LOOP_ARRANQUE: ""}) is None
         and sim_view.token_do_arranque() is None,
         f"com token={sim_view.token_do_arranque({sim_view.ENV_LOOP_ARRANQUE: 'abc'})!r} · sem variavel="
         f"{sim_view.token_do_arranque({})!r} · ambiente real={sim_view.token_do_arranque()!r}")

    # A CORRIDA DE ARRANQUE nas pecas (o §5 prova-a ponta a ponta): o site carimba o ficheiro no arranque
    # (loop: false + token), o dono faz POST /api/loop (loop: true + carimbo limpo) e o runner arranca DEPOIS
    # disso — com o MESMO token da escrita de arranque. Esse runner nunca pode reverter o POST.
    corrida = pasta / "pecas_corrida.json"
    token = "token-do-arranque-1"
    sim_site.escrever_controlo(corrida, {**sim_site.CONTROLO_INICIAL, "reiniciar": 7, "vel": 3.0,
                                         "loop": False, sim_site.CAMPO_ARRANQUE: token})
    carimbado = json.loads(corrida.read_text(encoding="utf-8"))
    sim_site.escrever_controlo(corrida, {"loop": True, sim_site.CAMPO_ARRANQUE: None})   # POST /api/loop
    pos_post = json.loads(corrida.read_text(encoding="utf-8"))
    c.ok("`POST /api/loop` (o do site) LIMPA o carimbo do arranque e mantem o resto (vento/dinamica/contador)",
         pos_post.get("loop") is True and pos_post.get(sim_site.CAMPO_ARRANQUE) is None
         and pos_post.get("reiniciar") == 7 and pos_post.get("vel") == 3.0
         and carimbado.get(sim_site.CAMPO_ARRANQUE) == token,
         f"antes: loop={carimbado.get('loop')!r} carimbo={carimbado.get(sim_site.CAMPO_ARRANQUE)!r} · "
         f"depois: loop={pos_post.get('loop')!r} carimbo={pos_post.get(sim_site.CAMPO_ARRANQUE)!r} · "
         f"reiniciar={pos_post.get('reiniciar')!r}")

    corrigiu_corrida = sim_view.fixar_loop(corrida, False, token)
    depois_corrida = json.loads(corrida.read_text(encoding="utf-8"))
    c.ok("[CORRIDA] `fixar_loop(sem-loop, token do arranque)` NAO reverte o `loop: true` escrito por um POST "
         "posterior ao arranque do site",
         corrigiu_corrida is False and depois_corrida.get("loop") is True
         and depois_corrida.get(sim_site.CAMPO_ARRANQUE) is None
         and depois_corrida.get("reiniciar") == 7,
         f"devolveu {corrigiu_corrida!r} · ficheiro={depois_corrida}")

    c.ok("[CORRIDA] o mesmo ficheiro num arranque DIRECTO (sem token) continua a ser corrigido — a "
         "autoridade do arranque so cede a um POST",
         sim_view.fixar_loop(corrida, False) is True
         and json.loads(corrida.read_text(encoding="utf-8")).get("loop") is False,
         f"loop=True -> {json.loads(corrida.read_text(encoding='utf-8')).get('loop')!r} "
         "(ficheiro voltou a ser corrigido)")

    intacto = pasta / "pecas_intacto.json"
    sim_site.escrever_controlo(intacto, {**sim_site.CONTROLO_INICIAL, sim_site.CAMPO_ARRANQUE: token})
    bytes_antes = intacto.read_bytes()
    c.ok("[CORRIDA] com o carimbo ainda do arranque o runner nao escreve nada (o ficheiro do site fica "
         "byte a byte igual: sem `t` novo, sem tocar em vento/`reiniciar`)",
         sim_view.fixar_loop(intacto, False, token) is False and intacto.read_bytes() == bytes_antes,
         f"ficheiro={json.loads(intacto.read_text(encoding='utf-8'))} · igual={intacto.read_bytes() == bytes_antes}")

    c.ok("[CORRIDA] carimbo de OUTRA sessao (nao o meu) tambem e respeitado — o fail-safe nunca reverte um "
         "valor que o site nao acabou de escrever",
         sim_view.fixar_loop(corrida, True, "outro-token") is False
         and json.loads(corrida.read_text(encoding="utf-8")).get("loop") is False,
         f"ficheiro.loop={json.loads(corrida.read_text(encoding='utf-8')).get('loop')!r} "
         "(o `fixar_loop` devolveu False e nao escreveu)")
    return c


# ==================================================================================================== §2
class PoliticaNula:
    """Política de ação nula: o §2 não precisa de nenhum modelo treinado."""

    @staticmethod
    def predict(_obs, deterministic=True):          # assinatura do SB3
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


class Ciclo:
    """O ciclo REAL do `sim_view.correr` no FIO PRINCIPAL + as checagens num fio auxiliar.

    O `correr` só instala os handlers de SIGINT/SIGTERM na main thread (fora dela o `signal.signal` rebenta
    com `ValueError` e é ignorado), por isso é ali que ele vive; o fio das checagens termina-o com um
    SIGTERM ao PRÓPRIO processo — exatamente o caminho do Ctrl+C/SIGTERM do uso real (exit 0).
    """

    def __init__(self, pasta: Path, nome: str, com_loop: bool, ficheiro_velho: dict | None) -> None:
        self.controlo_caminho = pasta / f"{nome}_controle.json"
        self.telemetria_caminho = pasta / f"{nome}_telemetria.jsonl"
        for caminho in (self.controlo_caminho, self.telemetria_caminho):
            caminho.unlink(missing_ok=True)
        if ficheiro_velho is not None:
            self.controlo_caminho.write_text(json.dumps(ficheiro_velho) + "\n", encoding="utf-8")
        self.env = modulo_env.HoverEnv()
        self.args = sim_view.analisar_argumentos(["--sem-janela", "--fator-tempo", "0"]
                                                 + (["--com-loop"] if com_loop else ["--sem-loop"]))
        # o MESMO arranque do `main`: o CLI decide e o ficheiro de controlo é corrigido (o §3 prova-o ponta
        # a ponta, com o processo a sério).
        self.corrigiu = sim_view.fixar_loop(self.controlo_caminho, sim_view.loop_do_arranque(self.args))
        self.controlo = sim_view.Controlo(self.controlo_caminho)
        self.telemetria = sim_view.Telemetria(self.telemetria_caminho, truncar=True)
        self.codigo: int | None = None
        self.erro: str | None = None

    def correr(self, c: Checagens, caso) -> None:
        """Corre o caso de checagens num fio auxiliar e o ciclo no fio principal; devolve o exit do ciclo."""
        falha: list[str] = []

        def trabalho() -> None:
            try:
                caso(self, c)
            except BaseException as erro:            # noqa: BLE001  (uma falha do caso tem de aparecer)
                falha.append(f"{type(erro).__name__}: {erro}")
            finally:
                os.kill(os.getpid(), signal.SIGTERM)         # fecha o ciclo no fio principal (handler dele)

        fio = threading.Thread(target=trabalho, name="checagens", daemon=True)
        fio.start()
        try:
            self.codigo = sim_view.correr(self.env, PoliticaNula(), self.controlo, self.telemetria,
                                          SondaNula(), self.args)
        except BaseException as erro:                # noqa: BLE001
            self.erro = f"{type(erro).__name__}: {erro}"
        fio.join(timeout=30.0)
        self.telemetria.fechar()
        if falha:
            c.ok(f"[§2] as checagens do caso de {self.controlo_caminho.name} correram ate ao fim", False,
                 falha[0])
        if self.erro is not None or self.codigo != 0:
            c.ok("[§2] o ciclo do runner terminou com exit 0", False,
                 f"erro={self.erro!r} · codigo={self.codigo!r}")


def _observa(env, alvo_passos: int | None = None, alvo_quedas: int | None = None,
             limite: float = JANELA_S) -> tuple[int, int, int]:
    """Acompanha `env.passos` (leituras de ~1 ms) e devolve `(quedas, maximo, n_leituras)`.

    Uma «queda» é o contador da física a DIMINUIR: é o sinal inequívoco de um reset (`env.reset` repõe
    `passos = 0`). Com o fator-tempo 0 um episódio de 500 passos corre em ~0,1 s, por isso a leitura de 1 ms
    vê dezenas de amostras por episódio — uma queda não passa despercebida.
    """
    t0 = time.perf_counter()
    anterior = env.passos
    quedas, maximo, n = 0, anterior, 0
    while time.perf_counter() - t0 < limite:
        atual = env.passos
        if atual < anterior:
            quedas += 1
        maximo = max(maximo, atual)
        anterior = atual
        n += 1
        if alvo_passos is not None and atual >= alvo_passos:
            break
        if alvo_quedas is not None and quedas >= alvo_quedas:
            break
        time.sleep(0.001)
    return quedas, maximo, n


def _espera(predicado, limite: float, _o_que: str) -> bool:
    """Espera (relógio) até `predicado()`; `False` se o limite estourar."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < limite:
        if predicado():
            return True
        time.sleep(0.002)
    return False


def caso_sem_reinicio(ciclo: Ciclo, c: Checagens) -> None:
    """§2a: SEM REINÍCIO — o episódio fecha e a física continua; só o REINICIAR reseta."""
    env = ciclo.env
    limite = env.max_passos
    _espera(lambda: env.passos >= 1, 30.0, "o ciclo arrancar")
    c.ok("[§2] arranque SEM REINICIO corrigiu o `loop: true` velho do ficheiro (autoritativo)",
         ciclo.corrigiu is True
         and json.loads(ciclo.controlo_caminho.read_text(encoding="utf-8")).get("loop") is False,
         f"fixou={ciclo.corrigiu!r} · ficheiro={json.loads(ciclo.controlo_caminho.read_text())!r}")

    quedas, maximo, n = _observa(env, alvo_passos=limite + 40)
    c.ok(f"[§2] fim de episodio SEM auto-reinicio: `passos` passou {limite} (max {maximo}) sem NENHUMA queda",
         quedas == 0 and maximo > limite,
         f"{n} leituras de `env.passos` · quedas={quedas} · max={maximo} · t={env.data.time:.3f} s")

    t_antes = env.data.time
    cresceu = _espera(lambda: env.data.time > t_antes + 0.5, 30.0, "o t crescer")
    c.ok("[§2] com o episodio fechado o `t` da fisica CONTINUA a crescer (nunca para nem reinicia)",
         cresceu and env.passos > limite,
         f"t {t_antes:.3f} -> {env.data.time:.3f} s · passos={env.passos} · estado do ficheiro: "
         f"reiniciar={sim_site.ler_controlo_bruto(ciclo.controlo_caminho).get('reiniciar')!r}")

    p0 = env.passos
    contador = int(sim_site.ler_controlo_bruto(ciclo.controlo_caminho).get("reiniciar", 0) or 0)
    sim_site.escrever_controlo(ciclo.controlo_caminho, {"reiniciar": contador + 1})
    resetou = _espera(lambda: env.passos < limite and env.data.time < 2.0, 30.0, "o REINICIAR resetar")
    c.ok("[§2] SO o REINICIAR reseta (contador atomico -> `passos` a 0 e `t` de volta ao inicio)",
         resetou and ciclo.controlo.n_reinicios >= 1,
         f"passos {p0} -> {env.passos} · t={env.data.time:.3f} s · reinicios vistos="
         f"{ciclo.controlo.n_reinicios}")


def caso_com_loop(ciclo: Ciclo, c: Checagens) -> None:
    """§2d: `--com-loop` — o fim do episódio auto-reinicia, sem nenhum REINICIAR."""
    env = ciclo.env
    _espera(lambda: env.passos >= 1, 30.0, "o ciclo arrancar")
    c.ok("[§2] `--com-loop` corrigiu o `loop: false` velho do ficheiro (autoritativo nos dois sentidos)",
         ciclo.corrigiu is True
         and json.loads(ciclo.controlo_caminho.read_text(encoding="utf-8")).get("loop") is True,
         f"fixou={ciclo.corrigiu!r} · ficheiro={json.loads(ciclo.controlo_caminho.read_text())!r}")

    quedas, maximo, n = _observa(env, alvo_quedas=2)
    c.ok("[§2] CONTINUO: o fim do episodio auto-reinicia (o contador da fisica volta a 0, >= 2 vezes) sem "
         "nenhum REINICIAR",
         quedas >= 2 and maximo >= 1,
         f"{n} leituras · quedas(auto-resets)={quedas} · max passos={maximo} · "
         f"reiniciar no ficheiro={sim_site.ler_controlo_bruto(ciclo.controlo_caminho).get('reiniciar')!r}")
    c.ok("[§2] o auto-reset nao mexe no contador `reiniciar` (quem reinicia e o runner, nao o dono)",
         sim_site.ler_controlo_bruto(ciclo.controlo_caminho).get("reiniciar") == 0
         and ciclo.controlo.n_reinicios == 0,
         f"reiniciar={sim_site.ler_controlo_bruto(ciclo.controlo_caminho).get('reiniciar')!r} · "
         f"reinicios vistos={ciclo.controlo.n_reinicios}")


def checa_ciclo(pasta: Path) -> Checagens:
    """§2: o ciclo REAL do runner (sem modelo), nos dois modos — COM e SEM REINÍCIO."""
    c = Checagens("§2 ciclo REAL do runner (HoverEnv + politica nula, fator-tempo 0)")
    _titulo(c.titulo)
    Ciclo(pasta, "ciclo_sem", com_loop=False, ficheiro_velho={**BASE_VELHO, "reiniciar": 0}
          ).correr(c, caso_sem_reinicio)
    Ciclo(pasta, "ciclo_com", com_loop=True, ficheiro_velho={**BASE_VELHO, "loop": False, "reiniciar": 0}
          ).correr(c, caso_com_loop)
    return c


# ==================================================================================================== §3
class Servidor:
    """`sim_site.py` a SÉRIO (subprocesso no seu grupo) com o URL lido do stdout e as linhas guardadas."""

    def __init__(self, pasta: Path, nome: str, modelo: Path, fator_tempo: float,
                 flags: tuple[str, ...] = (), controlo_inicial: dict | None = None,
                 porta: int = 0, ambiente: dict | None = None) -> None:
        self.controlo = pasta / f"{nome}_controle.json"
        self.telemetria = pasta / f"{nome}_telemetria.jsonl"
        for caminho in (self.controlo, self.telemetria):
            caminho.unlink(missing_ok=True)
        self.controlo_inicial = controlo_inicial
        self.flags = flags
        self.modelo, self.fator_tempo = modelo, fator_tempo
        self.porta = porta
        self.ambiente = ambiente                         # variáveis EXTRA do site (herdadas pelo runner)
        self.linhas: list[str] = []
        self.url: str | None = None
        self.processo: subprocess.Popen | None = None

    def __enter__(self) -> Self:
        if self.controlo_inicial is not None:            # o que uma sessão anterior deixou no disco
            self.controlo.write_text(json.dumps(self.controlo_inicial) + "\n", encoding="utf-8")
        comando = [sys.executable, str(_SIM_SITE), "--sem-browser", "--sem-janela",
                   "--port", str(self.porta), "--controlo", str(self.controlo),
                   "--telemetria", str(self.telemetria),
                   "--fator-tempo", f"{self.fator_tempo:g}", "--model", str(self.modelo), *self.flags]
        ambiente = None if self.ambiente is None else {**os.environ, **self.ambiente}
        self.processo = subprocess.Popen(comando, cwd=str(_AQUI), stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, start_new_session=True,
                                         env=ambiente)
        threading.Thread(target=self._ler, name=f"stdout-{self.controlo.stem}", daemon=True).start()
        t0 = time.perf_counter()
        while self.url is None and time.perf_counter() - t0 < ARRANQUE_S:
            if self.processo.poll() is not None:
                break
            time.sleep(0.05)
        if self.url is None:
            raise SystemExit("[teste] o sim_site.py nao arrancou: " + " | ".join(self.linhas[-4:]))
        return self

    def __exit__(self, *_excecao) -> None:
        if self.processo is None or self.processo.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(self.processo.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            self.processo.terminate()
        try:
            self.processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.processo.kill()

    def _ler(self) -> None:
        for linha in self.processo.stdout or ():
            self.linhas.append(linha.rstrip("\n"))
            if self.url is None:
                achado = re.search(r"(http://[\d.]+:\d+/)", linha)
                if achado:
                    self.url = achado.group(1).rstrip("/")

    def get(self, rota: str) -> dict:
        return _get(self.url, rota)

    def post(self, rota: str, corpo: dict | None = None) -> tuple[int, dict]:
        return _post(self.url, rota, corpo)

    def esperar(self, predicado, limite: float = ESPERA_S) -> dict | None:
        """Espera (relógio) até `predicado(estado)` com o `/api/sim`; devolve o estado ou `None`."""
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < limite:
            try:
                estado = self.get("/api/sim")
            except (urllib.error.URLError, OSError, ValueError):
                time.sleep(0.05)
                continue
            if predicado(estado):
                return estado
            time.sleep(0.05)
        return None


def _fresco(c: Checagens, pasta: Path, modelo: Path, fator_tempo: float, limite: int) -> None:
    """§3a: arranque EM FRESCO (sem ficheiro de controlo) — e §3c: ligar o CONTÍNUO pelo site."""
    with Servidor(pasta, "fresco", modelo, fator_tempo) as s:
        dados = sim_site.ler_controlo_bruto(s.controlo)
        criado = any("controlo:" in linha and "ficheiro criado" in linha for linha in s.linhas)
        c.ok("[§3a] arranque em fresco: o site criou o controlo com `loop: false` (SEM REINICIO)",
             dados.get("loop") is False and dados.get("reiniciar") == 0 and criado,
             f"ficheiro={dados} · stdout: {_linha_de(s.linhas, 'controlo:')}")

        inicial = s.esperar(lambda e: e["loop"] is False and e["passo"] > 0)
        c.ok("[§3a] `/api/sim` publica `loop: false` desde o arranque (modo EFETIVO do runner)",
             inicial is not None,
             f"loop={None if inicial is None else inicial['loop']!r} · "
             f"passo={None if inicial is None else inicial['passo']}")

        fim = s.esperar(lambda e: e["estado"] == "episodio_terminado" and e["passo"] > limite)
        depois = None if fim is None else s.esperar(
            lambda e: e["passo"] >= fim["passo"] + 40 and _t(e) > _t(fim))
        c.ok("[§3a] depois de o episodio fechar o `passo`/`t` continuam a crescer, `ep` fica em 1 e o "
             "`retorno` congela (nem reinicia nem para)",
             fim is not None and depois is not None and depois["ep"] == 1 and depois["loop"] is False
             and depois["retorno"] == fim["retorno"],
             f"fim: passo={None if fim is None else fim['passo']} t={None if fim is None else _t(fim):.2f} "
             f"ep={None if fim is None else fim['ep']} · "
             f"depois: passo={None if depois is None else depois['passo']} "
             f"t={None if depois is None else _t(depois):.2f} "
             f"retorno={None if depois is None else depois['retorno']!r}")

        codigo, corpo = s.post("/api/reiniciar")
        novo = s.esperar(lambda e: e["ep"] == 2 and e["passo"] < limite and e["estado"] == "a_correr")
        c.ok("[§3a] REINICIAR (`POST /api/reiniciar`) e o UNICO reset: o ep 2 arranca com `passo` a 0",
             codigo == 200 and corpo.get("contador") == 1 and novo is not None
             and sim_site.ler_controlo_bruto(s.controlo).get("reiniciar") == 1,
             f"HTTP {codigo} {corpo} · ep={None if novo is None else novo['ep']} · "
             f"passo={None if novo is None else novo['passo']}")

        codigo, corpo = s.post("/api/loop", {"ativo": True})
        ligado = s.esperar(lambda e: e["loop"] is True)
        c.ok("[§3c] `POST /api/loop {ativo:true}` liga o CONTINUO (ficheiro e API a dizer o mesmo)",
             codigo == 200 and corpo.get("loop") is True
             and sim_site.ler_controlo_bruto(s.controlo).get("loop") is True and ligado is not None,
             f"HTTP {codigo} {corpo} · ficheiro.loop="
             f"{sim_site.ler_controlo_bruto(s.controlo).get('loop')!r} · API.loop="
             f"{None if ligado is None else ligado['loop']!r}")

        codigo, _ = s.post("/api/vento", {"vel": 2.0})
        dados = sim_site.ler_controlo_bruto(s.controlo)
        estado = s.get("/api/sim")
        c.ok("[§3c] STICKY: `POST /api/vento` (escrita parcial) nao mexe no `loop` nem no `reiniciar`",
             codigo == 200 and dados.get("loop") is True and dados.get("reiniciar") == 1
             and dados.get("vel") == 2.0 and estado["loop"] is True,
             f"HTTP {codigo} · loop={dados.get('loop')!r} · reiniciar={dados.get('reiniciar')!r} · "
             f"vel={dados.get('vel')!r} · API.loop={estado['loop']!r}")

        auto = s.esperar(lambda e: e["ep"] >= 3)
        c.ok("[§3c] com o CONTINUO ligado o runner auto-reinicia (ep 3) sem nenhum REINICIAR",
             auto is not None and sim_site.ler_controlo_bruto(s.controlo).get("reiniciar") == 1,
             f"ep={None if auto is None else auto['ep']} · reiniciar="
             f"{sim_site.ler_controlo_bruto(s.controlo).get('reiniciar')!r}")

        codigo, corpo = s.post("/api/loop", {"ativo": False})
        sem = s.esperar(lambda e: e["ep"] == 3 and e["passo"] > limite
                        and e["estado"] == "episodio_terminado")
        c.ok("[§3c] desligar o CONTINUO volta a SEM REINICIO (o ep 3 fecha e NAO reinicia)",
             codigo == 200 and corpo.get("loop") is False and sem is not None,
             f"HTTP {codigo} {corpo} · ep={None if sem is None else sem['ep']} · "
             f"passo={None if sem is None else sem['passo']} · "
             f"estado={None if sem is None else sem['estado']!r}")


def _velho(c: Checagens, pasta: Path, modelo: Path, fator_tempo: float, limite: int) -> None:
    """§3b: arranque com um `loop: true` VELHO no ficheiro (+ §3d: o site repassa `--sem-loop`)."""
    with Servidor(pasta, "velho", modelo, fator_tempo, controlo_inicial={**BASE_VELHO, "t": 0.0}) as s:
        dados = sim_site.ler_controlo_bruto(s.controlo)
        c.ok("[§3b] arranque com `loop: true` velho: corrigido para `false`, com vento/dinamica/`reiniciar` "
             "INTACTOS",
             dados.get("loop") is False and dados.get("reiniciar") == 7 and dados.get("vel") == 3.0
             and dados.get("azimute") == 90.0 and dados.get("dinamico") == BASE_VELHO["dinamico"],
             f"loop True -> {dados.get('loop')!r} · reiniciar={dados.get('reiniciar')!r} · "
             f"vel={dados.get('vel')!r} · dinamico={dados.get('dinamico')!r} · stdout: "
             f"{_linha_de(s.linhas, 'controlo:')}")

        cmd = _linha_de(s.linhas, "runner:")
        c.ok("[§3d] o site repassa o modo ao runner (omissao -> `--sem-loop` na linha de comandos do filho)",
             "--sem-loop" in cmd and "--com-loop" not in cmd, f"stdout: {cmd}")

        estado = s.esperar(lambda e: e["loop"] is False and e["passo"] > 0)
        c.ok("[§3b] `/api/sim` publica `loop: false` (o modo EFETIVO, nao o pedido velho do ficheiro)",
             estado is not None, f"API.loop={None if estado is None else estado['loop']!r}")

        fim = s.esperar(lambda e: e["estado"] == "episodio_terminado" and e["passo"] > limite)
        c.ok("[§3b] o episodio NAO se auto-reinicia: `ep` continua 1 e o `passo` passa o limite",
             fim is not None and fim["ep"] == 1,
             f"ep={None if fim is None else fim['ep']} · passo={None if fim is None else fim['passo']} · "
             f"t={None if fim is None else _t(fim):.2f}")

        codigo, corpo = s.post("/api/reiniciar")
        novo = s.esperar(lambda e: e["ep"] == 2 and e["passo"] < limite)
        c.ok("[§3b] e o REINICIAR continua a funcionar (contador 7 -> 8, ep 2)",
             codigo == 200 and corpo.get("contador") == 8 and novo is not None,
             f"HTTP {codigo} {corpo} · ep={None if novo is None else novo['ep']}")


def _com_loop(c: Checagens, pasta: Path, modelo: Path, fator_tempo: float, limite: int) -> None:
    """§3d: `--com-loop` no site — corrige o ficheiro, chega ao runner e faz auto-reset."""
    inicial = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False, "reiniciar": 5, "loop": False}
    with Servidor(pasta, "comloop", modelo, fator_tempo, flags=("--com-loop",),
                  controlo_inicial=inicial) as s:
        dados = sim_site.ler_controlo_bruto(s.controlo)
        cmd = _linha_de(s.linhas, "runner:")
        c.ok("[§3d] `--com-loop` no site: corrige o ficheiro (`loop: false` -> `true`) e vai ao runner",
             dados.get("loop") is True and dados.get("reiniciar") == 5
             and "--com-loop" in cmd and "--sem-loop" not in cmd,
             f"ficheiro.loop={dados.get('loop')!r} · reiniciar={dados.get('reiniciar')!r} · stdout: {cmd}")

        estado = s.esperar(lambda e: e["loop"] is True and e["passo"] > 0)
        c.ok("[§3d] `/api/sim` publica `loop: true` (CONTINUO) no arranque",
             estado is not None, f"API.loop={None if estado is None else estado['loop']!r}")

        auto = s.esperar(lambda e: e["ep"] >= 2)
        c.ok("[§3d] o CONTINUO auto-reinicia sem nenhum REINICIAR (o contador fica em 5)",
             auto is not None and limite > 0
             and sim_site.ler_controlo_bruto(s.controlo).get("reiniciar") == 5,
             f"ep={None if auto is None else auto['ep']} · reiniciar="
             f"{sim_site.ler_controlo_bruto(s.controlo).get('reiniciar')!r}")


def _recriacao(c: Checagens, pasta: Path, modelo: Path, fator_tempo: float, limite: int) -> None:
    """§3e: ficheiro de controlo APAGADO e CORROMPIDO a meio da execução (o contrato é STICKY).

    Defeito medido (2026-10-09): o `sim_site.py` recriava o ficheiro a partir de `CONTROLO_INICIAL`
    (`loop: false`, `reiniciar: 0`) e o runner regressava a SEM REINÍCIO **sem nenhum `POST /api/loop`**.
    O contrato: depois do arranque só o `POST /api/loop` muda o `loop` e as escritas parciais nunca tocam em
    `loop`/`reiniciar` — o ficheiro é a VIA, não a autoridade; apagado/corrompido, quem manda é a memória do
    servidor (semeada pelo arranque e actualizada por cada POST).
    """
    with Servidor(pasta, "recriacao", modelo, fator_tempo) as s:
        inicial = s.esperar(lambda e: e["loop"] is False and e["passo"] > 0)
        c.ok("[§3e] ponto de partida: arranque SEM REINICIO (`loop: false`) e a fisica a correr",
             inicial is not None,
             f"loop={None if inicial is None else inicial['loop']!r} · "
             f"passo={None if inicial is None else inicial['passo']}")

        codigo_loop, _ = s.post("/api/loop", {"ativo": True})       # o ULTIMO POST antes do estrago
        ligado = s.esperar(lambda e: e["loop"] is True)
        codigo_rei, corpo_rei = s.post("/api/reiniciar")            # contador 1: tem de sobreviver ao estrago
        novo_ep = s.esperar(lambda e: e["ep"] == 2 and e["estado"] == "a_correr" and e["passo"] < limite)
        contador = sim_site.ler_controlo_bruto(s.controlo).get("reiniciar")
        c.ok("[§3e] antes do estrago: `POST /api/loop {ativo:true}` (CONTINUO) + `POST /api/reiniciar` "
             "(contador 1) estao em vigor",
             codigo_loop == 200 and ligado is not None and codigo_rei == 200
             and corpo_rei.get("contador") == 1 and contador == 1 and novo_ep is not None,
             f"loop: HTTP {codigo_loop} -> API.loop="
             f"{None if ligado is None else ligado['loop']!r} · reiniciar: HTTP {codigo_rei} {corpo_rei} · "
             f"ep={None if novo_ep is None else novo_ep['ep']} · ficheiro.reiniciar={contador!r}")

        # 1) o ficheiro DESAPARECE a meio da execucao e chega uma escrita PARCIAL (vento)
        s.controlo.unlink()
        codigo_v, _ = s.post("/api/vento", {"vel": 2.0})
        voltou = _espera(lambda: s.controlo.is_file(), 10.0, "o site recriar o ficheiro")
        dados = sim_site.ler_controlo_bruto(s.controlo)
        c.ok("[§3e] ficheiro APAGADO em execucao + escrita parcial: a recriacao leva o `loop` do ULTIMO POST "
             "(true) e o `reiniciar` preservado (1) — nunca `CONTROLO_INICIAL` (`false`/0)",
             codigo_v == 200 and voltou and dados.get("loop") is True and dados.get("reiniciar") == 1
             and dados.get("vel") == 2.0,
             f"HTTP {codigo_v} · ficheiro recriado={dados}")

        auto = s.esperar(lambda e: e["ep"] >= 3 and e["loop"] is True)
        c.ok("[§3e] e o runner NAO regrediu a SEM REINICIO: continua a auto-reiniciar (ep 3) sem nenhum "
             "REINICIAR novo",
             auto is not None and sim_site.ler_controlo_bruto(s.controlo).get("reiniciar") == 1,
             f"ep={None if auto is None else auto['ep']} · API.loop="
             f"{None if auto is None else auto['loop']!r} · ficheiro.reiniciar="
             f"{sim_site.ler_controlo_bruto(s.controlo).get('reiniciar')!r}")

        # 2) o ficheiro fica CORROMPIDO a meio da execucao e chega outra escrita PARCIAL
        s.controlo.write_text("{isto nao e JSON", encoding="utf-8")
        codigo_c, _ = s.post("/api/vento", {"vel": 1.0})
        dados_c = sim_site.ler_controlo_bruto(s.controlo)
        c.ok("[§3e] ficheiro CORROMPIDO em execucao + escrita parcial: o `loop`/`reiniciar` efetivos "
             "sobrevivem na recriacao (o vento novo entra, os comandos nao mudam)",
             codigo_c == 200 and dados_c.get("loop") is True and dados_c.get("reiniciar") == 1
             and dados_c.get("vel") == 1.0,
             f"HTTP {codigo_c} · ficheiro recriado={dados_c}")

        codigo_r2, corpo_r2 = s.post("/api/reiniciar")
        c.ok("[§3e] depois do estrago o contador continua a subir do valor PRESERVADO (1 -> 2): um REINICIAR "
             "manual nao volta ao 0 nem e ignorado pelo runner",
             codigo_r2 == 200 and corpo_r2.get("contador") == 2,
             f"HTTP {codigo_r2} {corpo_r2} · ficheiro.reiniciar="
             f"{sim_site.ler_controlo_bruto(s.controlo).get('reiniciar')!r}")


def checa_servidor(pasta: Path, modelo: Path, fator_tempo: float) -> Checagens:
    """§3: ponta a ponta pelo `sim_site.py` REAL — quatro arranques (fresco, ficheiro velho, `--com-loop`,
    e o §3e do ficheiro apagado/corrompido a meio da execução)."""
    c = Checagens("§3 ponta a ponta pelo SERVIDOR real (sim_site.py + runner + API)")
    _titulo(c.titulo)
    limite = int(modulo_env.HoverEnv().max_passos)
    _fresco(c, pasta, modelo, fator_tempo, limite)
    _velho(c, pasta, modelo, fator_tempo, limite)
    _com_loop(c, pasta, modelo, fator_tempo, limite)
    _recriacao(c, pasta, modelo, fator_tempo, limite)
    return c


# ==================================================================================================== §5
# CORRIDA DE ARRANQUE (defeito medido, 2026-10-09): o `POST /api/loop` disparado no instante em que a porta
# responde chega ao ficheiro de controlo ANTES de o runner (que ainda está a importar o SB3/torch) decidir o
# modo de arranque. Sem handshake, o `fixar_loop` do runner revertia esse pedido legítimo («vence o valor
# velho»). Aqui a janela é alargada DE PROPÓSITO — um `sitecustomize.py` (via `PYTHONPATH`) atrasa SÓ o
# arranque do `sim_view.py` — para o cenário ser determinístico em vez de depender da cache do torch.
_SITECUSTOMIZE = '''"""Atraso ARTIFICIAL do arranque do sim_view.py (só do §5 do teste_arranque_loop.py).

Injetado por `PYTHONPATH` (o `site` do CPython importa `sitecustomize` no arranque): NÃO é código do
laboratório, é a forma de alargar a janela da corrida de arranque sem tocar no simulador. Só dorme quando o
programa lançado é o `sim_view.py` — o site (`sim_site.py`) arranca a tempo e a porta responde depressa,
que é o que o teste precisa de medir.
"""
import sys
import time

if any(argumento.endswith("sim_view.py") for argumento in sys.argv):
    time.sleep(float(__import__("os").environ.get("ATRASO_RUNNER_S", "0") or 0))
'''


def _pasta_atraso(pasta: Path, atraso: float) -> Path | None:
    """`sitecustomize.py` que atrasa o runner em `atraso` s (ou `None` se `atraso <= 0`)."""
    if atraso <= 0:
        return None
    destino = pasta / "atraso_runner"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "sitecustomize.py").write_text(_SITECUSTOMIZE, encoding="utf-8")
    return destino


def _ultima_amostra(caminho: Path) -> dict:
    """Última amostra VÁLIDA da telemetria (`{}` se ainda não há nenhuma) — leitura local, sem HTTP."""
    linhas = sim_site.ultimas_linhas(caminho, 4)
    return linhas[-1] if linhas else {}


def _vigia_loop(servidor: Servidor, prazo: float) -> tuple[bool, int, float]:
    """Vigia o ficheiro durante a janela de arranque: `(viu_false?, n_leituras, t_ate_parar)`.

    Para quando (a) o ficheiro diz `loop: false` — a reversão do defeito, que devolve logo o testemunho — ou
    (b) o runner já está a publicar telemetria com `loop: true` e `passo > 0`, prova de que a decisão de
    arranque já foi tomada e o modo EFETIVO é o CONTÍNUO pedido pelo POST.
    """
    inicio = time.perf_counter()
    leituras = 0
    while time.perf_counter() - inicio < prazo:
        if sim_site.ler_controlo_bruto(servidor.controlo).get("loop") is False:
            return True, leituras, time.perf_counter() - inicio
        amostra = _ultima_amostra(servidor.telemetria)
        if amostra.get("loop") is True and int(amostra.get("passo", 0) or 0) > 0:
            return False, leituras, time.perf_counter() - inicio
        leituras += 1
        time.sleep(0.02)
    return False, leituras, time.perf_counter() - inicio


def _corrida(c: Checagens, pasta: Path, modelo: Path, fator_tempo: float, limite: int, indice: int,
             porta: int, atraso: float) -> None:
    """Uma corrida do §5: POST de loop logo que a porta responde e vigia até o runner estar em CONTINÚO."""
    rotulo = f"[§5.{indice}]"
    atraso_dir = _pasta_atraso(pasta, atraso)
    ambiente = None if atraso_dir is None else {"PYTHONPATH": str(atraso_dir),
                                                "ATRASO_RUNNER_S": f"{atraso:g}"}
    with Servidor(pasta, f"corrida{indice}", modelo, fator_tempo, porta=porta, ambiente=ambiente) as s:
        t0 = time.perf_counter()
        codigo, corpo = s.post("/api/loop", {"ativo": True})      # ASSIM QUE a porta responde
        t_post = time.perf_counter() - t0
        ficheiro = sim_site.ler_controlo_bruto(s.controlo)
        c.ok(f"{rotulo} `POST /api/loop {{ativo:true}}` imediatamente apos a porta responder: 200 e o "
             f"ficheiro fica `loop: true` com o carimbo do arranque limpo",
             codigo == 200 and corpo.get("loop") is True and ficheiro.get("loop") is True
             and ficheiro.get(_CARIMBO) is None,
             f"HTTP {codigo} {corpo} · t+{t_post:.2f}s · ficheiro.loop={ficheiro.get('loop')!r} · "
             f"carimbo={ficheiro.get(_CARIMBO)!r}")

        revertido, leituras, t_vigia = _vigia_loop(s, PRAZO_CORRIDA)
        if revertido:
            c.ok(f"{rotulo} o runner NUNCA reverte o `loop` para `false` durante o arranque", False,
                 f"o ficheiro voltou a `loop: false` {t_vigia:.2f}s depois do POST ({leituras} leituras) — "
                 f"stdout do runner: {_linha_de(s.linhas, 'fixado')}")
            return
        c.ok(f"{rotulo} o runner NAO reverteu o `loop` para `false` na janela de arranque (vigia de "
             f"{leituras} leituras ate a telemetria publicar o modo efetivo)",
             ficheiro.get("loop") is True, f"t+{t_vigia:.2f}s · prazo={PRAZO_CORRIDA:g}s")

        estado = s.esperar(lambda e: e["loop"] is True and e["passo"] > 0, limite=PRAZO_CORRIDA)
        c.ok(f"{rotulo} `/api/sim` publica `loop: true` (modo EFETIVO do runner, nao o default do arranque)",
             estado is not None,
             f"API.loop={None if estado is None else estado['loop']!r} · "
             f"passo={None if estado is None else estado['passo']}")

        respeitou = any("mudado DEPOIS do arranque do site" in linha for linha in s.linhas)
        fixou = any("fixado em" in linha for linha in s.linhas)
        c.ok(f"{rotulo} o runner diz no stdout que RESPEITOU o POST (e nao ha nenhuma linha de «fixado em … "
             f"vence o valor velho»)",
             respeitou and not fixou,
             f"respeitou={respeitou} · fixou={fixou} · stdout: {_linha_de(s.linhas, 'mudado DEPOIS')}")

        auto = s.esperar(lambda e: e["ep"] >= 2, limite=PRAZO_CORRIDA)
        final = sim_site.ler_controlo_bruto(s.controlo)
        c.ok(f"{rotulo} o CONTINUO pedido no POST esta mesmo em vigor: o runner auto-reinicia (ep 2) sem "
             f"nenhum REINICIAR e o ficheiro continua `loop: true`",
             auto is not None and final.get("loop") is True
             and final.get(_CARIMBO) is None
             and sim_site.ler_controlo_bruto(s.controlo).get("reiniciar") in (0, None),
             f"ep={None if auto is None else auto['ep']} · ficheiro.loop={final.get('loop')!r} · "
             f"carimbo={final.get(_CARIMBO)!r} · reiniciar={final.get('reiniciar')!r}")

        if atraso > 0:
            tempo_ate_publicar = t_vigia + t_post
            c.ok(f"{rotulo} o atraso artificial do runner esteve mesmo ativo (a 1.a amostra de telemetria "
                 f"chegou {tempo_ate_publicar:.2f}s depois do POST: >= atraso {atraso:g}s)",
                 tempo_ate_publicar >= atraso * 0.8,
                 f"POST a t+{t_post:.2f}s · modo efetivo a t+{tempo_ate_publicar:.2f}s")


def checa_corrida(pasta: Path, modelo: Path, fator_tempo: float, porta: int,
                  atraso: float) -> Checagens:
    """§5: a corrida de arranque, 3x contra o servidor real (o mesmo cenário, com o runner atrasado)."""
    c = Checagens("§5 corrida de arranque (POST de loop durante o arranque, 3 corridas)")
    _titulo(c.titulo)
    limite = int(modulo_env.HoverEnv().max_passos)
    print(f"[teste] §5: {CORRIDAS} corridas · porta {porta} · atraso artificial do runner {atraso:g}s",
          flush=True)
    for indice in range(1, CORRIDAS + 1):
        _corrida(c, pasta, modelo, fator_tempo, limite, indice, porta, atraso)
    return c


# ==================================================================================================== §4
# Driver CDP mínimo (sem dependências: o `WebSocket` global do Node ≥ 22 + o endpoint HTTP do Chrome). O
# trabalho acontece DENTRO da página servida pelo `sim_site.py` (o BUNDLE real de `site/dist`): lê o DOM do
# toggle CONTINUIDADE (o grupo tem `aria-label` próprio; a opção ATIVA é a que tem `aria-pressed="true"`) e
# diz se o front já recebeu dados da API («API ligada»). O Python chama-o uma vez por leitura.
_DRIVER_CDP = r'''
const [, , portaArg, urlBase] = process.argv

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
    } catch (erro) { /* a porta ainda nao abriu */ }
    await new Promise((r) => setTimeout(r, 100))
  }
  throw new Error(`nao encontrei a pagina do site no Chrome (CDP): ${JSON.stringify(vistos)}`)
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

const LEITURA = `(() => {
  const grupo = document.querySelector('[aria-label^="continuidade"]')
  if (!grupo) return JSON.stringify({pronto: false})
  const opcoes = Array.from(grupo.querySelectorAll('button')).map((b) => ({
    texto: b.textContent.trim(), ativo: b.getAttribute('aria-pressed') === 'true',
  }))
  const ativo = opcoes.find((o) => o.ativo)
  const corpo = document.body ? document.body.innerText : ''
  return JSON.stringify({pronto: true, opcoes, ativo: ativo ? ativo.texto : null,
                         apiLigada: corpo.includes('API ligada')})
})()`

const alvo = await urlDoAlvo()
const { comando } = await ligar(alvo)
await comando("Runtime.enable")
for (let i = 0; i < 240; i++) {
  const resultado = await comando("Runtime.evaluate", { expression: LEITURA, returnByValue: true })
  const texto = resultado.result && resultado.result.value
  if (texto && JSON.parse(texto).pronto) {
    console.log(texto)
    process.exit(0)
  }
  await new Promise((r) => setTimeout(r, 250))
}
console.log("DRIVER: o toggle CONTINUIDADE nao apareceu na pagina")
process.exit(1)
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


def _ler_toggle(node: str, driver: Path, porta_cdp: int, url: str, limite: float = 60.0) -> dict:
    """Uma leitura do DOM do toggle pelo driver CDP: `{pronto, opcoes, ativo, apiLigada}`."""
    resultado = subprocess.run([node, str(driver), str(porta_cdp), url], capture_output=True, text=True,
                               timeout=limite, check=False)
    if resultado.returncode != 0:
        raise SystemExit(f"[teste] o driver CDP falhou ({resultado.returncode}): "
                         f"{(resultado.stderr or resultado.stdout)[-800:]}")
    return json.loads(resultado.stdout)


def _esperar_toggle(node: str, driver: Path, porta_cdp: int, url: str, predicado,
                    limite: float = 30.0) -> dict | None:
    """Espera (relógio) até uma leitura do DOM satisfazer `predicado`; devolve a leitura ou `None`."""
    t0 = time.perf_counter()
    leitura = None
    while time.perf_counter() - t0 < limite:
        leitura = _ler_toggle(node, driver, porta_cdp, url)
        if predicado(leitura):
            return leitura
        time.sleep(0.2)
    return None


def checa_navegador(pasta: Path, modelo: Path, fator_tempo: float,
                    porta: int = PORTA_NAVEGADOR) -> Checagens:
    """§4: o FRONT real (bundle de `site/dist`) servido pelo `sim_site.py`, lido no DOM por CDP.

    É a prova de que o UI mostra **SEM REINÍCIO como estado ATIVO no arranque**. E, para não ser uma leitura
    estática do fallback do React, inclui o **controlo negativo**: `POST /api/loop {ativo:true}` liga o
    CONTÍNUO e o DOM **muda** para CONTÍNUO ativo; desligar volta a SEM REINÍCIO — o UI espelha o backend.
    """
    c = Checagens("§4 front real num Chrome headless (DOM/CDP): SEM REINICIO ativo no arranque")
    _titulo(c.titulo)
    node = _binario(("node",))
    chrome = _binario(("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"))
    dist = _AQUI / "site" / "dist" / "index.html"
    if node is None or chrome is None or not dist.is_file():
        c.ok("[§4] prova do DOM: node + Chrome + `site/dist/index.html` (npm run build) disponiveis", False,
             f"node={node!r} · chrome={chrome!r} · dist existe={dist.is_file()}")
        return c
    driver = pasta / "driver_continuidade.mjs"
    driver.write_text(_DRIVER_CDP, encoding="utf-8")
    with Servidor(pasta, "navegador", modelo, fator_tempo, porta=porta) as s:
        perfil = pasta / "chrome-perfil"
        shutil.rmtree(perfil, ignore_errors=True)
        navegador = subprocess.Popen(
            [chrome, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={perfil}",
             "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--disable-dev-shm-usage",
             "--remote-allow-origins=*", s.url + "/"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            porta_cdp = _esperar_devtools(perfil, navegador, 30.0)
            if porta_cdp is None:
                c.ok("[§4] o Chrome abriu a porta de depuracao (CDP)", False, "sem DevToolsActivePort")
                return c
            print(f"        servidor real em {s.url} · CDP na porta {porta_cdp} · driver {driver.name}",
                  flush=True)

            ligado = _esperar_toggle(node, driver, porta_cdp, s.url,
                                     lambda leitura: leitura.get("apiLigada") is True, 60.0)
            api = s.get("/api/sim")
            c.ok("[§4] o front recebeu dados da API e o toggle CONTINUIDADE mostra SEM REINICIO ATIVO",
                 ligado is not None and ligado.get("ativo") == "SEM REINÍCIO" and api["loop"] is False,
                 f"ativo={None if ligado is None else ligado.get('ativo')!r} · "
                 f"opcoes={None if ligado is None else ligado.get('opcoes')} · API.loop={api['loop']!r}")

            codigo, corpo = s.post("/api/loop", {"ativo": True})
            mudou = _esperar_toggle(node, driver, porta_cdp, s.url,
                                    lambda leitura: leitura.get("ativo") == "CONTÍNUO", 30.0)
            api = s.get("/api/sim")
            c.ok("[§4] `POST /api/loop {ativo:true}` muda o DOM para CONTINUO ativo (o UI espelha o backend)",
                 codigo == 200 and mudou is not None and api["loop"] is True,
                 f"HTTP {codigo} {corpo} · ativo={None if mudou is None else mudou.get('ativo')!r} · "
                 f"API.loop={api['loop']!r}")

            codigo, corpo = s.post("/api/loop", {"ativo": False})
            voltou = _esperar_toggle(node, driver, porta_cdp, s.url,
                                     lambda leitura: leitura.get("ativo") == "SEM REINÍCIO", 30.0)
            c.ok("[§4] desligar volta a SEM REINICIO ativo no DOM (o estado que o arranque deixa)",
                 codigo == 200 and voltou is not None,
                 f"HTTP {codigo} {corpo} · ativo={None if voltou is None else voltou.get('ativo')!r}")
        finally:
            if navegador.poll() is None:
                try:
                    os.killpg(os.getpgid(navegador.pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    navegador.terminate()
                try:
                    navegador.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    navegador.kill()
    return c


# =================================================================================================== main
def analisar_argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Prova que o simulador arranca com o loop DESLIGADO (SEM REINICIO): o ficheiro de "
                    "controlo nasce/corrige-se para `loop: false`, o episodio nao se auto-reinicia e so o "
                    "REINICIAR reseta; `--com-loop`/`POST /api/loop` ligam o CONTÍNUO (sticky).",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sem-http", action="store_true",
                   help="salta o §3 (o servidor real): corre so as pecas e o ciclo do runner, sem modelo")
    p.add_argument("--sem-navegador", action="store_true",
                   help="salta o §4 (o FRONT real num Chrome headless por CDP)")
    p.add_argument("--model", type=Path, default=None,
                   help="modelo do runner para o §3/§4; por omissao o mesmo que o site escolheria")
    p.add_argument("--fator-tempo", type=float, default=FATOR_TEMPO, metavar="F",
                   help=f"ritmo do runner no §3/§4 (padrao: {FATOR_TEMPO:g} = 3x o tempo real)")
    p.add_argument("--porta-navegador", type=int, default=PORTA_NAVEGADOR, metavar="PORTA",
                   help=f"porta do servidor do §4 (padrao: {PORTA_NAVEGADOR}; 0 = livre)")
    p.add_argument("--porta-corrida", type=int, default=PORTA_CORRIDA, metavar="PORTA",
                   help=f"porta do servidor do §5 (padrao: {PORTA_CORRIDA}; 0 = livre)")
    p.add_argument("--atraso-runner", type=float, default=ATRASO_RUNNER, metavar="S",
                   help=f"atraso ARTIFICIAL imposto ao arranque do runner no §5 (padrao: {ATRASO_RUNNER:g}s; "
                        "0 = sem atraso, a janela fica so com o tempo real de import)")
    p.add_argument("--fontes", type=Path, default=None, metavar="DIR",
                   help="pasta com env.py/sim_view.py/sim_site.py alternativos (importados ANTES da arvore "
                        "e usados pelo servidor do §3/§5): e a prova de que o §5 FALHAVA antes do reparo")
    p.add_argument("--pasta", type=Path, default=None,
                   help="onde escrever os controlos/telemetrias do teste (padrao: pasta temporaria)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = analisar_argumentos(argv)
    pasta = args.pasta
    if pasta is None:
        pasta = Path(tempfile.mkdtemp(prefix="teste_arranque_loop_"))
    pasta.mkdir(parents=True, exist_ok=True)
    print(f"[teste] ficheiros do teste: {pasta}")
    if _FONTES is not None and _FONTES != _AQUI:
        print(f"[teste] fontes: {_FONTES} (env.py + sim_view.py + sim_site.py desta pasta — as de ANTES do "
              f"reparo; o §3/§5 lancam o servidor DAQUI)")
    else:
        print("[teste] fontes: arvore de trabalho do laboratorio (sim_view.py + sim_site.py + env.py)")

    checagens = [checa_pecas(pasta), checa_ciclo(pasta)]
    if args.sem_http:
        print("\n[teste] --sem-http: salto o §3 e o §5 (servidores reais) — pedido EXPLICITO na linha de comando")
    else:
        modelo = args.model
        if modelo is None:
            modelo, motivo = _modelo_do_teste()
            if modelo is None:
                print(f"\n[teste] FALHA: o §3/§4/§5 precisam de um modelo e o cabecalho promete-os — {motivo}")
                print("[teste] indique --model CAMINHO (ou use --sem-http para os saltar DE PROPOSITO)")
                return 1
            print(f"\n[teste] modelo do runner: {modelo} ({motivo})")
        if modelo is not None:
            checagens.append(checa_servidor(pasta, modelo, args.fator_tempo))
            checagens.append(checa_corrida(pasta, modelo, args.fator_tempo, args.porta_corrida,
                                           args.atraso_runner))
            if args.sem_navegador:
                print("\n[teste] --sem-navegador: salto o §4 (front real no Chrome)")
            else:
                checagens.append(checa_navegador(pasta, modelo, args.fator_tempo, args.porta_navegador))

    total = sum(len(c.linhas) for c in checagens)
    falhas = [falha for c in checagens for falha in c.falhas]
    print(f"\n[teste] {total - len(falhas)}/{total} checagens OK")
    if falhas:
        print("[teste] FALHAS:")
        for falha in falhas:
            print(f"  · {falha}")
        return 1
    print("[teste] o simulador arranca SEM REINICIO (loop desligado), o ficheiro velho e corrigido, um POST "
          "/api/loop durante o arranque NUNCA e revertido e o CONTINUO so liga pelo POST /api/loop")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
