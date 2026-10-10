#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_camera.py — PROVA dos comandos de CÂMARA v2 (TERCEIRA-PESSOA).

Contrato v2 (migração de 2026-10-10; a janela 3D mostra SÓ o 3D e TODOS os controlos ficam no site):

  · ficheiro de controlo `out/controle_vento.json`, bloco `"camera"` = `{"azimute", "elevacao", "distancia",
    "seq"}` — SEM `alvo` (escrita atómica, merge parcial: nunca toca em `loop`/`reiniciar`/vento);
    `seq` incrementado a CADA comando pelo servidor (como o `dinamico.seq`);
  · ALVO SEMPRE NO DRONE (`sim_view.seguir_drone`, a CADA frame): `viewer.cam.lookat =
    body(CAM_CORPO).xpos + CAM_OFFSET` — COLA EXACTA (o mesmo estado do corpo dá sempre o mesmo `lookat`;
    sem suavização = sem lag). `CAM_CORPO` = corpo do drone por NOME; `CAM_OFFSET` somado elemento a
    elemento (hoje [0, 0, 0] = centro do corpo);
  · `aplicar_camera` escreve SÓ `azimuth`/`elevation`/`distance` (ORBITAR/zoom) — NUNCA o `lookat`:
    entre comandos o rato do viewer fica LIVRE (ângulos/distância sobrevivem) e o PAN do rato é
    SOBREPOSTO pelo seguimento (num orbitar 3ª-pessoa o alvo não sai do drone);
  · `POST /api/camera` (8.ª rota, validador `validar_camera`): corpo = SUBCONJUNTO de
    `{azimute, elevacao, distancia}` + alias `distandia` → `distancia`; `seq` do corpo é IGNORADO (o
    servidor carimba o seu); `{}` e `{"seq": n}` são ACEITES (200) — DECISÃO documentada no `INTERFACE.md`;
    campo PRESENTE com `null`, chave DESCONHECIDA (incl. o `alvo` do contrato v1) ou valor fora de faixa
    → 400 com mensagem clara. Faixas: `azimute` finito (mod 360), `elevacao` ∈ [−90, 90]°, `distancia`
    ∈ ]0, 20] m;
  · telemetria JSONL com a 19.ª chave `"camera"` = `{azimute, elevacao, distancia, alvo}` da câmara REAL
    (`alvo` = `lookat` real = drone+offset), ou `null` sem viewer; `camera_padrao` = `CAM_PADRAO`
    (SEM `alvo`) e `camera_atual` na API;
  · REPOR VISTA = enviar os valores de `camera_padrao` como um comando normal (sem mecanismos extra);
  · contrato de FICHEIRO (runner `_ler_camera`): o bloco tem de ser COMPLETO (3 valores) e chaves
    desconhecidas (ex. `alvo` de ficheiros v1) são ignoradas em silêncio — o HTTP recusa (400), o
    runner tolera (ficheiros velhos não rebentam): assimetria INTENCIONAL, testada nos dois lados.

Este script prova, por comando, cada ponto do contrato:

  (a) o ALVO SEGUE O DRONE ENQUANTO ELE SE MOVE PELA FÍSICA (empuxo comandado pela política; sem
      teleporte): `lookat == body(CAM_CORPO).xpos + CAM_OFFSET` a CADA frame — provado em cada escrita
      (colagem exacta a 1e-9, sem lag) por um `lookat` instrumentado que tira o snapshot do drone no
      próprio instante da escrita (mesmo fio do `mj_step`: sem corrida);
  (b) `azimute`/`elevacao`/`distancia` aplicam-se por MUDANÇA DE ASSINATURA (uma vez) e ficam
      PRESERVADOS entre comandos (a mudança externa tipo «rato» sobrevive); o PAN do rato é SOBREPOSTO
      pelo seguimento; um `seq` novo com os mesmos valores RE-APLICA;
  (c) validação: `null` presente e chaves desconhecidas (incl. `alvo`) → 400; subconjuntos → 200;
      faixas; alias `distandia`; `{}` e `{"seq": n}` ACEITES (200, `seq` ignorado) — decisão documentada;
  (d) rajada fria de 40 ligações × 3 rondas → 120/120 servidas E aplicadas, sem resets e sem JSON partido;
  (e) telemetria: `"camera"` = `{azimute, elevacao, distancia, alvo}` com `alvo` = lookat REAL =
      drone+offset (ou `null` sem viewer); `camera_padrao`/`camera_atual` coerentes; REPOR VISTA =
      `CAM_PADRAO`;
  (f) contrato de ficheiro: bloco completo aceite; `alvo` de ficheiro v1 ignorado em silêncio;
  (g) NÃO-TAUTOLOGIA por mutação (cópias staged em $TMPDIR via `--fontes`): seguimento removido,
      colado a posição velha, assinatura sem `seq` (§2) e validação removida (§1) têm de FALHAR.

Quatro camadas (§1 in-process → §2 ciclo real com viewer falso → §3 servidor real por HTTP → §4 mutação):

  §1 PEÇAS — constantes `CAM_PADRAO` (iguais nos dois módulos, SEM `alvo`, iguais ao
     `mjv_defaultFreeCamera(model)` nos 3 valores), `aplicar_camera` (3 escritas, nunca o `lookat`),
     `seguir_drone` (fórmula exacta; offset provado com valor não-nulo), `camera_real`, a CONVENÇÃO DE
     SINAIS ângulo→direção provada contra a pose real da câmara (`MjvScene.camera`), os validadores
     (`validar_camera` do site, `_ler_camera` do runner) e o merge parcial do `escrever_controlo`;
  §2 CICLO REAL — `sim_view.correr` a sério (`HoverEnv` + política de ação mutável, fator-tempo 0) com um
     VIEWER FALSO INSTRUMENTADO: seguimento por escrita enquanto o drone se move, rato preservado,
     PAN sobreposto, `seq`/REPOR VISTA/ficheiro v1 e a telemetria; + uma corrida SEM viewer (d);
  §3 SERVIDOR REAL — `sim_site.py` + runner reais (`--sem-janela`, porta 8561): BURST FRIO de 40
     ligações simultâneas × 3 rondas (120/120 servidos e aplicados — a fila do `listen()` tem de levar
     um burst inteiro; com o default 5 do stdlib perdiam-se comandos), as 8 rotas, os 400 do (c) —
     incl. a DECISÃO `{}`/`seq` —, o merge do (f), `camera_padrao`/`camera_atual` do (e) e a telemetria
     real do runner;
  §4 MUTAÇÃO — o MESMO §1/§2 contra cópias mutadas (`--fontes`): têm de FALHAR (g).

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_camera.py            # tudo
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_camera.py --sem-http  # §1+§2
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_camera.py --so-ciclo  # §2
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_camera.py --so-pecas  # §1
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_camera.py --fontes DIR  # outras fontes

`--fontes DIR` (como no `teste_arranque_loop.py`) corre o MESMO teste contra `env.py` + `sim_view.py` +
`sim_site.py` de OUTRA pasta — é o que o §4 usa para provar que as mutações FALHAM (e serve para comparar
com fontes de antes de um reparo). Sem modelo treinado nenhum, o §3 FALHA ALTO (exit 1) em vez de saltar em
silêncio o que o cabeçalho promete (`--sem-http` salta-o de propósito).

Exit 0 = todas as checagens passam; 1 = alguma falha (diz qual e mostra o diagnóstico).
"""
from __future__ import annotations

import argparse
import atexit
import errno
import json
import os
import re
import select
import shutil
import signal
import socket
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
    """Fontes alternativas de `origem` (podem estar FORA do repo) copiadas para `_AQUI/.fontes_antes`.

    Os módulos procuram o `pyproject.toml` acima deles, por isso uma pasta fora da árvore do laboratório não
    serve: a cópia é estagiada DENTRO da árvore (removida no fim do processo) e entra PRIMEIRO no `sys.path`.
    Uma pasta que JÁ esteja na árvore (as cópias mutadas do §4) usa-se tal e qual.
    """
    if _RAIZ in origem.parents:
        return origem
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


# As fontes alternativas entram PRIMEIRO no `sys.path` (a ordem do `insert(0, …)` é invertida).
_FONTES = _pasta_fontes(sys.argv[1:])
for _caminho in (_RAIZ, _AQUI, _FONTES):
    if _caminho is not None:
        sys.path.insert(0, str(_caminho))

from lab import mjkit  # noqa: F401, I001  (define MUJOCO_GL=egl ANTES do `import mujoco`, como no sim_view)

import mujoco
import numpy as np

import env as modulo_env
import sim_site
import sim_view

ESPERA_S = 60.0           # limite genérico das esperas (a máquina pode estar ocupada com builds do front)
JANELA_S = 30.0           # limite das folgas/observações do §2 (fator-tempo 0: o ciclo roda a milhares de Hz)
FATOR_TEMPO = 1.0         # §3: ritmo do runner real (1 = tempo real; a câmara não mexe na física)
PORTA_HTTP = 8561         # §3: porta do servidor de teste (a do laboratório para testes)
TOL_CAM = 1e-9            # colagem exacta do seguimento (mesma expressão aritmética nos dois lados)
TOL_REPOUSO = 2e-3        # comparações cruzadas em repouso (telemetria arredondada a 6 casas + folga)
LIMIAR_MOV = 0.25         # m — deslocamento mínimo do drone para a janela de movimento ser prova de movimento
PANO_S = 5.0              # limite da espera do «PAN sobreposto» (a kHz basta ms; curto para morrer rápido)


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


def _espera(predicado, limite: float, _o_que: str) -> bool:
    """Espera (relógio) até `predicado()`; `False` se o limite estourar."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < limite:
        if predicado():
            return True
        time.sleep(0.002)
    return False


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


def _burst_frio(porta: int, n: int = 40) -> list[str]:
    """Burst FRIO de `n` ligações simultâneas com `POST /api/camera`; devolve o resultado por ligação.

    É o cenário medido pelo verificador independente (2026-10-09): 40 ligações de UMA VEZ contra um
    servidor que ainda não recebeu pedidos. Os `n` connects não-bloqueantes saem num laço apertado (os
    SYNs seguem-se sem esperas — um burst de verdade, pior caso da fila do `listen()`) e cada POST é
    enviado NO INSTANTE em que a sua ligação completa (como o browser faz; é o que apanha a janela de
    overflow da fila). «Servido» = chega a linha de resposta HTTP; ligação perdida/resetada/sem resposta
    é uma FALHA — um comando do dono que nunca chega. Cada resposta lê-se até ao EOF e o corpo tem de ser
    JSON válido (nada de JSON partido a meio de um burst). Usa sockets crus (sem `urllib`) para dominar os
    instantes. Devolve `n` resultados: `HTTP 200 … json:ok`, `HTTP 400 …`, `… json:FALHA` ou `TipoExcecao: …`.
    """
    pedidos = [b"POST /api/camera HTTP/1.0\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n"
               b"Content-Length: " + str(len(c)).encode() + b"\r\n\r\n" + c
               for c in (f'{{"azimute": {float(i)}}}'.encode() for i in range(n))]
    resultados: list[str | None] = [None] * n
    pendentes: dict = {}
    t0 = time.perf_counter()
    for i in range(n):
        ligacao = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ligacao.setblocking(False)
        ligacao.connect_ex(("127.0.0.1", porta))
        pendentes[ligacao] = {"i": i, "enviado": False, "buffer": b""}
    while pendentes and time.perf_counter() - t0 < 15.0:
        escrever = [s for s, e in pendentes.items() if not e["enviado"]]
        ler = [s for s, e in pendentes.items() if e["enviado"]]
        prontas_leitura, prontas_escrita, _ = select.select(ler, escrever, [], 0.2)
        for ligacao in prontas_escrita:
            estado = pendentes.pop(ligacao)
            erro_so = ligacao.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if erro_so:
                resultados[estado["i"]] = f"{errno.errorcode.get(erro_so, erro_so)} no connect"
                ligacao.close()
                continue
            try:
                ligacao.sendall(pedidos[estado["i"]])
            except OSError as erro:                       # reset/pipe: a ligacao MORREU — comando perdido
                resultados[estado["i"]] = f"{type(erro).__name__}: {erro}"
                ligacao.close()
                continue
            pendentes[ligacao] = {**estado, "enviado": True}
        for ligacao in prontas_leitura:
            estado = pendentes.pop(ligacao)
            try:
                bocado = ligacao.recv(65536)
            except OSError as erro:                       # ConnectionResetError do lado do cliente
                resultados[estado["i"]] = f"{type(erro).__name__}: {erro}"
                ligacao.close()
                continue
            if not bocado:                                # EOF: a resposta acabou — analisa o que há
                resultados[estado["i"]] = _resultado_burst(estado["buffer"])
                ligacao.close()
                continue
            pendentes[ligacao] = {**estado, "buffer": estado["buffer"] + bocado}
    for ligacao, estado in pendentes.items():
        resultados[estado["i"]] = "ligacao perdeu-se (sem resposta ate ao prazo)"
        ligacao.close()
    return [r if r is not None else "sem resposta (EOF apos o pedido)" for r in resultados]


def _resultado_burst(buffer: bytes) -> str:
    """`HTTP 200 … json:ok` de uma resposta completa (ou `json:FALHA` quando o corpo não é JSON)."""
    if b"\r\n" not in buffer:
        return "sem linha de resposta HTTP"
    cabecalhos, _, corpo = buffer.partition(b"\r\n\r\n")
    estado = cabecalhos.split(b"\r\n", 1)[0].decode("latin-1") \
        .replace("HTTP/1.0", "HTTP").replace("HTTP/1.1", "HTTP")
    try:
        json.loads(corpo.decode("utf-8"))
        return f"{estado} json:ok"
    except (UnicodeDecodeError, ValueError) as erro:
        return f"{estado} json:{type(erro).__name__} ({corpo[:40]!r})"


def _modelo_do_teste() -> tuple[Path | None, str]:
    """`(caminho, motivo)` do modelo do §3 — o mesmo que o site escolheria para o runner.

    Mesmo desvio do `teste_arranque_loop.py`: as fontes do `--fontes` são SÓ CÓDIGO, por isso o `out/` com
    os modelos procura-se também na árvore do laboratório; sem modelo NENHUM devolve `(None, motivo)` e
    quem chama FALHA ALTO em vez de saltar o §3.
    """
    tentativas: list[str] = []
    try:
        return sim_site.modelo_por_omissao()
    except SystemExit as erro:
        tentativas.append(f"fontes em teste ({sim_site.__file__}): {erro}")
    if _FONTES is not None:
        original = sim_site._AQUI
        try:
            sim_site._AQUI = _AQUI
            modelo, motivo = sim_site.modelo_por_omissao()
            return modelo, f"{motivo} · procurado na ARVORE ({_AQUI / 'out'})"
        except SystemExit as erro:
            tentativas.append(f"arvore ({_AQUI}): {erro}")
        finally:
            sim_site._AQUI = original
    return None, " | ".join(tentativas)


# ------------------------------------------------------------------------------- utilidades de câmara
def _valores3_de(cam) -> dict:
    """`{azimute, elevacao, distancia}` de um `cam` (real ou falso) — o comando de ORBITAR/zoom (v2)."""
    return {"azimute": float(cam.azimuth), "elevacao": float(cam.elevation), "distancia": float(cam.distance)}


def _lookat_de(cam) -> list[float]:
    """`[x, y, z]` do `lookat` (alvo REAL da câmara)."""
    return [float(cam.lookat[i]) for i in range(3)]


def _perto(a, b, tol: float = TOL_CAM) -> bool:
    """Duas listas de 3 (ou dois blocos de 3 valores) dizem os mesmos números até `tol`?"""
    if isinstance(a, dict):
        return all(abs(float(a[k]) - float(b[k])) <= tol for k in ("azimute", "elevacao", "distancia"))
    return len(a) == len(b) and all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def _dist(a, b) -> float:
    """Distância euclidiana entre duas posições de 3."""
    return float(np.linalg.norm(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)))


def _pos_drone(data) -> list[float]:
    """`body(CAM_CORPO).xpos + CAM_OFFSET` — a fórmula do `seguir_drone`, tal e qual o código a faz."""
    corpo = data.body(sim_view.CAM_CORPO)
    return [float(corpo.xpos[i]) + float(sim_view.CAM_OFFSET[i]) for i in range(3)]


class _CamMinima:
    """Objeto mínimo com os atributos que `aplicar_camera`/`seguir_drone`/`camera_real` usam."""

    def __init__(self) -> None:
        self.azimuth = 0.0
        self.elevation = 0.0
        self.distance = 0.0
        self.lookat = [0.0, 0.0, 0.0]


# ==================================================================================================== §1
def _captura_default(modelo) -> dict:
    """Os 3 valores de ORBITAR/zoom que `mjv_defaultFreeCamera(modelo)` dá ao `MjvCamera` (sem `alvo`)."""
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(modelo, cam)
    return _valores3_de(cam)


def _checa_sinais(c: Checagens) -> None:
    """A convenção de sinais ângulo→direção provada contra a pose REAL da câmara (`MjvScene.camera`).

    Fórmula documentada no `INTERFACE.md` (§4.4): `pos = alvo − d·f(azim, elev)` com
    `f = [cos(elev)·cos(azim), cos(elev)·sin(azim), sin(elev)]` (graus→rad; azim 0° olha para +x, 90° para
    +y; elev POSITIVO põe a câmara ABAIXO do alvo a olhar para cima, −90° = por cima a olhar para baixo).
    Cada pose do `mjv_updateScene` traz DOIS olhos (câmara estéreo): a MÉDIA dos dois é a pose mono, e é
    ela que tem de bater com a fórmula — `MjvScene.camera[0]` isolado tem o desvio do olho esquerdo.
    """
    xml = "<mujoco><worldbody><body pos='0 0 1'><geom size='.1'/></body></worldbody></mujoco>"
    modelo = mujoco.MjModel.from_xml_string(xml)
    dados = mujoco.MjData(modelo)
    opt, pert = mujoco.MjvOption(), mujoco.MjvPerturb()
    cena = mujoco.MjvScene(modelo, maxgeom=100)
    cam = mujoco.MjvCamera()
    casos = [(0.0, 0.0, 1.0, [0.0, 0.0, 0.0]), (90.0, 0.0, 2.0, [0.0, 0.0, 0.0]),
             (37.0, 23.0, 2.5, [1.0, 2.0, 3.0]), (123.0, -12.0, 7.0, [0.5, -1.0, 2.0]),
             (300.0, 60.0, 0.4, [0.0, 0.0, 1.0]), (271.5, -89.0, 3.3, [-2.0, 1.0, 0.5])]
    pior = 0.0
    for azim, elev, dist, alvo in casos:
        cam.azimuth, cam.elevation, cam.distance = azim, elev, dist
        cam.lookat[:] = np.asarray(alvo, dtype=float)
        mujoco.mjv_updateScene(modelo, dados, opt, pert, cam, mujoco.mjtCatBit.mjCAT_ALL, cena)
        media = np.mean([np.asarray(k.pos, dtype=float) for k in cena.camera], axis=0)
        a, e = np.radians(azim), np.radians(elev)
        f = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
        pior = max(pior, float(np.abs(media - (np.asarray(alvo) - dist * f)).max()))
    c.ok("[§1] convencao de sinais: pos = alvo − d·f(azim,elev), f = [cos e·cos a, cos e·sin a, sin e]",
         pior < 1e-6, f"pior desvio {pior:.2e} m sobre {len(casos)} poses (media dos 2 olhos estereo)")


def checa_pecas(pasta: Path) -> Checagens:
    """§1: as peças do contrato de câmara v2, sem simulação (constantes, seguimento, validadores, merge)."""
    c = Checagens("§1 pecas do contrato de camera v2 (in-process, sem simulacao)")
    _titulo(c.titulo)

    iguais = sim_view.CAM_PADRAO == sim_site.CAM_PADRAO
    sem_alvo = set(sim_view.CAM_PADRAO) == {"azimute", "elevacao", "distancia"}
    c.ok("[§1] CAM_PADRAO e igual em sim_view.py e sim_site.py e tem SÓ {azimute, elevacao, distancia} "
         "(SEM alvo — contrato v2: o alvo e sempre o drone)",
         iguais and sem_alvo,
         f"sim_view={sim_view.CAM_PADRAO} · sim_site={sim_site.CAM_PADRAO}")

    env_teste = modulo_env.HoverEnv(helices=True)     # o modelo do runner por omissão (com hélices)
    default = _captura_default(env_teste.model)
    desvio_az = abs((default["azimute"] - sim_view.CAM_PADRAO["azimute"] + 180.0) % 360.0 - 180.0)
    desvio = max(desvio_az, abs(default["elevacao"] - sim_view.CAM_PADRAO["elevacao"]),
                 abs(default["distancia"] - sim_view.CAM_PADRAO["distancia"]))
    c.ok("[§1] CAM_PADRAO == mjv_defaultFreeCamera(model) capturado nos 3 valores (default explicito; "
         "azimute modulo 360) — o lookat do default NAO faz parte do contrato (e do drone)",
         desvio <= 1e-12,
         f"pior desvio {desvio:.2e} · capturado={default} · CAM_PADRAO={sim_view.CAM_PADRAO} "
         f"(azimute {default['azimute']} ≡ {sim_view.CAM_PADRAO['azimute']}: a mesma pose, o contrato "
         "normaliza mod 360)")

    cam_min = _CamMinima()
    cam_min.lookat = [7.0, 7.0, 7.0]                  # sentinela: a aplicação NÃO pode escrever o lookat
    sim_view.aplicar_camera(cam_min, {"azimute": 10.0, "elevacao": -20.0, "distancia": 3.5})
    c.ok("[§1] aplicar_camera escreve SÓ azimuth/elevation/distance (3 escritas) e NUNCA o lookat "
         "(o alvo e do seguir_drone)",
         (cam_min.azimuth, cam_min.elevation, cam_min.distance) == (10.0, -20.0, 3.5)
         and cam_min.lookat == [7.0, 7.0, 7.0],
         f"cam = {cam_min.azimuth}, {cam_min.elevation}, {cam_min.distance} · lookat={cam_min.lookat}")

    c.ok("[§1] camera_real le a camara real {azimute, elevacao, distancia, alvo=lookat} e devolve None "
         "sem camara (honestidade)",
         sim_view.camera_real(cam_min) == {"azimute": 10.0, "elevacao": -20.0, "distancia": 3.5,
                                           "alvo": [7.0, 7.0, 7.0]}
         and sim_view.camera_real(None) is None,
         f"camera_real={sim_view.camera_real(cam_min)} · sem cam={sim_view.camera_real(None)!r}")

    original_offset = sim_view.CAM_OFFSET
    try:
        sim_view.CAM_OFFSET = (0.1, -0.2, 0.3)        # offset NAO-nulo: prova que o termo entra na conta
        cam_seg = _CamMinima()
        escrito = sim_view.seguir_drone(cam_seg, env_teste.data)
        esperado = _pos_drone(env_teste.data)
        c.ok("[§1] seguir_drone: lookat == body(CAM_CORPO).xpos + CAM_OFFSET (corpo por NOME; offset "
             "somado elemento a elemento — provado com offset nao-nulo)",
             _perto(cam_seg.lookat, esperado, 1e-12) and _perto(escrito, esperado, 1e-12),
             f"lookat={cam_seg.lookat} · esperado={esperado} · CAM_CORPO={sim_view.CAM_CORPO!r}")
        c.ok("[§1] seguir_drone devolve o alvo escrito (o que sai na telemetria) e None sem cam "
             "sem erro (honestidade)",
             _perto(escrito, cam_seg.lookat, 1e-12) and sim_view.seguir_drone(None, env_teste.data) is None,
             f"devolvido={escrito} · sem cam={sim_view.seguir_drone(None, env_teste.data)!r}")
    finally:
        sim_view.CAM_OFFSET = original_offset

    _checa_sinais(c)

    base = {"vel": 3.0, "azimute": 90.0, "elevacao": -10.0, "ativo": True, "reiniciar": 7, "loop": True,
            "dinamico": {"modo": "nenhum", "params": {}, "ativo": False, "seq": 4}}
    r1 = sim_site.validar_camera({"azimute": 400.0, "elevacao": -15.0, "distancia": 2.5}, base)
    c.ok("[§1] validar_camera normaliza o azimute mod 360 e carimba o 1.º `seq` = 1",
         r1["camera"] == {"azimute": 40.0, "elevacao": -15.0, "distancia": 2.5, "seq": 1},
         f"bloco={r1['camera']}")

    so_az = sim_site.validar_camera({"azimute": 200.0}, r1)
    sem_bloco = sim_site.validar_camera({"azimute": 1.0}, {})
    c.ok("[§1] subconjunto de campos mantem o resto do bloco em vigor (sem bloco nenhum, CAM_PADRAO)",
         so_az["camera"] == {"azimute": 200.0, "elevacao": -15.0, "distancia": 2.5, "seq": 2}
         and sem_bloco["camera"]["distancia"] == sim_site.CAM_PADRAO["distancia"]
         and sem_bloco["camera"]["elevacao"] == sim_site.CAM_PADRAO["elevacao"],
         f"bloco={so_az['camera']} · sem bloco={sem_bloco['camera']}")

    r2 = sim_site.validar_camera({"azimute": 200.0, "seq": 99}, so_az)
    r3 = sim_site.validar_camera({}, r2)
    r4 = sim_site.validar_camera({"seq": "x"}, r3)
    c.ok("[§1] `seq` incrementa a CADA pedido (como `dinamico.seq`) e o `seq` do corpo e IGNORADO "
         "(mesmo lixo: e um aviso do cliente, nao um campo do bloco)",
         [r2["camera"]["seq"], r3["camera"]["seq"], r4["camera"]["seq"]] == [3, 4, 5]
         and r2["camera"]["azimute"] == 200.0,
         f"seqs={[r2['camera']['seq'], r3['camera']['seq'], r4['camera']['seq']]} (corpo mandava 99/'x')")

    campos3 = ("azimute", "elevacao", "distancia")
    c.ok("[§1] DECISAO v2: `{}` e `{\"seq\": n}` sao ACEITES (200) — subconjunto vazio / `seq` do corpo "
         "completam do bloco em vigor com seq do SERVIDOR novo (excecao documentada no INTERFACE.md)",
         all(r3["camera"][k] == r2["camera"][k] for k in campos3)
         and all(r4["camera"][k] == r3["camera"][k] for k in campos3)
         and r3["camera"]["seq"] == r2["camera"]["seq"] + 1 and r4["camera"]["seq"] == r3["camera"]["seq"] + 1,
         f"{{}}->{r3['camera']} · {{seq:x}}->{r4['camera']}")

    recusas = [({"alvo": [0, 0, 1]}, "desconhecidas"), ({"alvo": None}, "desconhecidas"),
               ({"outra": 1}, "desconhecidas"), ({"distancia": 0.0}, "distancia"),
               ({"distancia": -1.0}, "distancia"), ({"distancia": 20.5}, "distancia"),
               ({"elevacao": 91.0}, "elevacao"), ({"elevacao": -91.0}, "elevacao"),
               ({"azimute": float("inf")}, "finito"), ({"azimute": "x"}, "finito"),
               ({"distancia": 1.0, "distandia": 2.0}, "escolha um")]
    falhou, mensagens = True, []
    for corpo, marca in recusas:
        try:
            sim_site.validar_camera(corpo, r3)
            falhou, mensagens = False, mensagens + [f"{corpo} ACEITE"]
        except ValueError as erro:
            mensagens.append(f"{marca}: {erro}")
            if marca not in str(erro):
                falhou = False
    c.ok("[§1] validar_camera recusa CHAVE DESCONHECIDA (alvo do contrato v1 incluido), ambiguidade "
         "distancia+distandia, distancia<=0 (>20), elevacao fora de [-90,90] e nao-finitos (400 claro)",
         falhou, " | ".join(mensagens))

    alias = sim_site.validar_camera({"distandia": 1.75, "azimute": 10.0}, r3)
    dup = None
    try:
        sim_site.validar_camera({"distancia": 1.0, "distandia": 2.0}, r3)
    except ValueError as erro:
        dup = str(erro)
    c.ok("[§1] alias `distandia` e aceite e mapeado para `distancia`; `distancia` + `distandia` juntos "
         "-> 400 (ambiguo: escolha um)",
         alias["camera"]["distancia"] == 1.75 and alias["camera"]["azimute"] == 10.0
         and dup is not None and "escolha um" in dup,
         f"alias={alias['camera']} · dup={dup}")

    nulos = [({"azimute": None}, "azimute"), ({"elevacao": None}, "elevacao"),
             ({"distancia": None}, "distancia")]
    falhou_nulo, mensagens = True, []
    for corpo, marca in nulos:
        try:
            sim_site.validar_camera(corpo, r3)
            falhou_nulo, mensagens = False, mensagens + [f"{corpo} ACEITE"]
        except ValueError as erro:
            mensagens.append(f"{marca}: {erro}")
            if "nulo" not in str(erro):
                falhou_nulo = False
    vazio = sim_site.validar_camera({}, r3)["camera"]                # AUSENCIA: completa do bloco em vigor
    so_seq = sim_site.validar_camera({"seq": None}, r3)["camera"]    # `seq` do corpo: continua IGNORADO
    completas = (all(vazio[cc] == r3["camera"][cc] for cc in campos3)
                 and all(so_seq[cc] == r3["camera"][cc] for cc in campos3)
                 and vazio["seq"] == so_seq["seq"] == r3["camera"]["seq"] + 1)
    c.ok("[§1] campo PRESENTE com valor null e recusado (400 com `nulo`) — null NAO e ausente; so a "
         "AUSENCIA completa do bloco em vigor (e o `seq` do corpo, mesmo null, continua ignorado)",
         falhou_nulo and completas, " | ".join(mensagens))

    ficheiro = pasta / "pecas_controle.json"
    sim_site.escrever_controlo(ficheiro, {**base, "dinamico": base["dinamico"]})
    registo = sim_site.escrever_controlo(ficheiro, sim_site.validar_camera(
        {"azimute": 10.0, "elevacao": 0.0, "distancia": 1.0}, {}))
    intocados = all(registo[campo] == base[campo] for campo in ("vel", "azimute", "elevacao", "ativo",
                                                               "reiniciar", "loop", "dinamico"))
    c.ok("[§1] escrita PARCIAL de camera nunca toca em loop/reiniciar/vento/dinamica (merge atomico)",
         intocados and registo["camera"]["seq"] == 1,
         f"vel={registo['vel']} loop={registo['loop']!r} reiniciar={registo['reiniciar']!r} "
         f"dinamico={registo['dinamico']} camera.seq={registo['camera']['seq']}")

    bom = sim_view.ler_registo({"camera": {"azimute": 400.0, "elevacao": -30.0, "distancia": 2.5, "seq": 3}})
    v1_bloco = sim_view.ler_registo({"camera": {"azimute": 5.0, "elevacao": 0.0, "distancia": 1.0,
                                                "alvo": [0.0, 0.0, 0.5], "seq": 9}})
    c.ok("[§1] ler_registo (runner): bloco COMPLETO aceite (azimute mod 360, seq); num ficheiro v1 o "
         "`alvo` e outras chaves sao IGNORADAS em silencio (assimetria com o HTTP, que recusa)",
         bom.camera is not None and bom.camera.azimute == 40.0 and bom.camera.seq == 3
         and v1_bloco.camera is not None and v1_bloco.camera.distancia == 1.0 and v1_bloco.camera.seq == 9
         and sim_view.ler_registo({}).camera is None,
         f"bloco={bom.camera} · v1 com alvo={v1_bloco.camera}")

    mau = 0
    for corpo in ({"camera": {"azimute": 0.0, "elevacao": 100.0, "distancia": 1.0}},
                  {"camera": {"azimute": 0.0, "elevacao": 0.0, "distancia": 0.0}},
                  {"camera": {"azimute": 0.0, "elevacao": 0.0}},
                  {"camera": {"azimute": 0.0, "elevacao": 0.0, "distancia": 1.0, "seq": -1}},
                  {"camera": "x"}):
        try:
            sim_view.ler_registo(corpo)
        except ValueError:
            mau += 1
    c.ok("[§1] ler_registo recusa bloco incompleto, faixas más e `seq` invalido (ValueError)",
         mau == 5, f"{mau}/5 recusas")
    return c


# ==================================================================================================== §2
class PoliticaAcao:
    """Política de ação CONSTANTE mutável: o §2 move o drone pela FÍSICA (empuxo/momentos), sem teleporte.

    Ação [-1,1]⁴ do `HoverEnv`: `a[0]` = empuxo (0 = hover = mg, −1 = motores fora), `a[1:]` = momentos.
    Quem escreve algoritmos é o dono — aqui só se comanda um valor constante para a física levar o drone.
    """

    def __init__(self) -> None:
        self.acao = np.zeros(4, dtype=np.float32)

    def predict(self, _obs, deterministic=True):      # assinatura do SB3
        return self.acao.copy(), None


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


class _LookatContador(list):
    """`lookat` de 3 floats que REGISTA cada escrita e tira o snapshot do drone NO MESMO INSTANTE.

    É a prova da colagem `lookat == body(CAM_CORPO).xpos + CAM_OFFSET` A CADA ESCRITA: as escritas do
    `seguir_drone` vêm do MESMO fio que faz o `mj_step` (ninguém passa o estado pelo meio), por isso o
    snapshot lido no próprio `__setitem__` é exactamente o `xpos` que o `seguir_drone` usou — igualdade
    exacta (1e-9), sem corrida e sem tolerância de movimento. Escritas de OUTRO fio (o «rato»/PAN do
    dono, ou o próprio teste) contam-se à parte: são o PAN que o seguimento sobrepõe.
    """

    def __init__(self, dono: CamInstrumentada, pos_drone, fio_sim: int) -> None:
        super().__init__([0.0, 0.0, 0.0])
        self._dono, self._pos_drone, self._fio_sim = dono, pos_drone, fio_sim
        self.seguimento = 0              # escritas do fio do simulador (o `seguir_drone`)
        self.seguimento_ruim = 0         # dessas, escritas que NAO batem com drone+offset
        self.pior = 0.0                  # pior desvio da invariante (para o detalhe)
        self.pan = 0                     # escritas de outros fios («rato»/teste)

    def __setitem__(self, indice, valor):            # assinatura do list
        self._dono._contar("lookat")
        if threading.get_ident() == self._fio_sim:
            self.seguimento += 1
            desvio = abs(float(valor) - self._pos_drone()[indice])
            self.pior = max(self.pior, desvio)
            if desvio > TOL_CAM:
                self.seguimento_ruim += 1
        else:
            self.pan += 1
        super().__setitem__(indice, valor)


class CamInstrumentada:
    """`MjvCamera` falso instrumentado: conta as escritas de ORBITAR/zoom e vigia CADA escrita do `lookat`.

    As escritas dos 3 atributos custam 1 cada por aplicação (o `aplicar_camera` v2 escreve só esses);
    uma aplicação a cada frame/re-leitura empurra a contagem para cima e o teste FALHA. O `lookat` é do
    `seguir_drone` a cada frame — vigiado pelo `_LookatContador` (invariante por escrita).
    """

    def __init__(self, pos_drone) -> None:
        self.__dict__["_escritas"] = {}
        self.__dict__["lookat"] = _LookatContador(self, pos_drone, threading.get_ident())
        self.__dict__["azimuth"] = 0.0
        self.__dict__["elevation"] = 0.0
        self.__dict__["distance"] = 0.0

    def _contar(self, nome: str) -> None:
        self._escritas[nome] = self._escritas.get(nome, 0) + 1

    def __setattr__(self, nome, valor):              # assinatura do objecto
        self._contar(nome)
        self.__dict__[nome] = valor

    def escritas(self, nome: str) -> int:
        """Escritas do atributo `nome` (`azimuth`/`elevation`/`distance`/`lookat`) até agora."""
        return self._escritas.get(nome, 0)


class ViewerFalso:
    """«Viewer falso» do contrato: `sync/is_running/lock/m/viewport` + `.cam` (instrumentado)."""

    def __init__(self, pos_drone) -> None:
        self.cam = CamInstrumentada(pos_drone)
        self.m = object()
        self.viewport = None

    def sync(self) -> None:
        return None

    def is_running(self) -> bool:
        return True

    def lock(self) -> Self:
        return self


class Ciclo:
    """O ciclo REAL do `sim_view.correr` no FIO PRINCIPAL + o roteiro de checagens num fio auxiliar.

    (Igual ao `teste_arranque_loop.Ciclo`: só a main thread instala os handlers de sinal; o fio das
    checagens termina o ciclo com um SIGTERM ao PRÓPRIO processo — o caminho do Ctrl+C real, exit 0.)
    """

    def __init__(self, pasta: Path, nome: str, com_viewer: bool = True,
                 controlo_inicial: dict | None = None) -> None:
        self.controlo_caminho = pasta / f"{nome}_controle.json"
        self.telemetria_caminho = pasta / f"{nome}_telemetria.jsonl"
        for caminho in (self.controlo_caminho, self.telemetria_caminho):
            caminho.unlink(missing_ok=True)
        if controlo_inicial is not None:
            self.controlo_caminho.write_text(json.dumps(controlo_inicial) + "\n", encoding="utf-8")
        self.env = modulo_env.HoverEnv()
        self.args = sim_view.analisar_argumentos(["--sem-janela", "--fator-tempo", "0", "--sem-loop"])
        self.controlo = sim_view.Controlo(self.controlo_caminho)
        self.telemetria = sim_view.Telemetria(self.telemetria_caminho, truncar=True)
        self.politica = PoliticaAcao()
        self.viewer = ViewerFalso(lambda: _pos_drone(self.env.data)) if com_viewer else None
        self.codigo: int | None = None
        self.erro: str | None = None

    def correr(self, c: Checagens, caso) -> None:
        """Corre o `caso` (roteiro) num fio auxiliar e o ciclo no fio principal; termina com exit 0."""
        falha: list[str] = []

        def trabalho() -> None:
            try:
                caso(self, c)
            except BaseException as erro:            # noqa: BLE001  (uma falha do caso tem de aparecer)
                falha.append(f"{type(erro).__name__}: {erro}")
            finally:
                os.kill(os.getpid(), signal.SIGTERM)         # fecha o ciclo no fio principal

        fio = threading.Thread(target=trabalho, name="roteiro", daemon=True)
        fio.start()
        try:
            self.codigo = sim_view.correr(self.env, self.politica, self.controlo, self.telemetria,
                                          SondaNula(), self.args, viewer=self.viewer)
        except BaseException as erro:                # noqa: BLE001
            self.erro = f"{type(erro).__name__}: {erro}"
        fio.join(timeout=30.0)
        self.telemetria.fechar()
        if falha:
            c.ok(f"[§2] o roteiro do caso {self.controlo_caminho.name} correu ate ao fim", False, falha[0])
        c.ok("[§2] o ciclo do runner terminou com exit 0 (sem viewer nao ha erro nenhum)",
             self.erro is None and self.codigo == 0, f"erro={self.erro!r} · codigo={self.codigo!r}")

    def linhas(self) -> list[dict]:
        """Linhas da telemetria já escritas (para as checagens de conteúdo)."""
        try:
            return [json.loads(l) for l in self.telemetria_caminho.read_text(encoding="utf-8").splitlines()
                    if l.strip().startswith("{")]
        except OSError:
            return []

    def comando(self, corpo: dict) -> dict:
        """POST /api/camera in-process: o MESMO caminho do servidor (`validar_camera` + `escrever_controlo`)."""
        novo = sim_site.validar_camera(corpo, sim_site.ler_controlo(self.controlo_caminho))
        return sim_site.escrever_controlo(self.controlo_caminho, novo)


def _aplicado3(cam, valores: dict) -> bool:
    """O `cam` tem EXACTAMENTE estes 3 valores de ORBITAR/zoom (até TOL_CAM)?"""
    return _perto(_valores3_de(cam), valores)


def _attrs(cam: CamInstrumentada) -> tuple[int, int, int]:
    """Contagem de escritas (`azimuth`, `elevation`, `distance`) — 1 cada por aplicação."""
    return tuple(cam.escritas(n) for n in ("azimuth", "elevation", "distance"))


def roteiro_com_viewer(ciclo: Ciclo, c: Checagens) -> None:
    """§2a–g: comandos de câmara, SEGUIMENTO 3ª-pessoa e telemetria no ciclo real (viewer falso)."""
    cam: CamInstrumentada = ciclo.viewer.cam
    arrancou = _espera(lambda: ciclo.controlo.n_cameras >= 1, JANELA_S, "a aplicacao do arranque")
    c.ok("[§2] ARRANQUE aplica CAM_PADRAO ao viewer.cam (3 escritas de orbitar/zoom; o lookat NAO e "
         "da aplicacao — e do seguimento)",
         arrancou and ciclo.controlo.n_cameras == 1 and _attrs(cam) == (1, 1, 1)
         and _aplicado3(cam, sim_view.CAM_PADRAO),
         f"aplicacoes={ciclo.controlo.n_cameras} · escritas attrs={_attrs(cam)} · cam={_valores3_de(cam)}")

    comando_a = {"azimute": 30.0, "elevacao": -15.0, "distancia": 3.0}
    antes = _attrs(cam)
    ciclo.comando(comando_a)
    aplicou = _espera(lambda: ciclo.controlo.n_cameras >= 2, JANELA_S, "a aplicacao do comando")
    time.sleep(0.3)                                        # folga: milhares de passos com o MESMO ficheiro
    c.ok("[§2] (a) comando aplica-se EXATAMENTE UMA VEZ por mudanca de assinatura (3 escritas certas, "
         "lookat intocado pela aplicacao)",
         aplicou and ciclo.controlo.n_cameras == 2 and _attrs(cam) == tuple(a + 1 for a in antes)
         and _aplicado3(cam, comando_a),
         f"aplicacoes={ciclo.controlo.n_cameras} · escritas attrs {antes} -> {_attrs(cam)} · "
         f"cam={_valores3_de(cam)}")

    n_ventos = ciclo.controlo.n_ventos
    attrs_antes = _attrs(cam)
    sim_site.escrever_controlo(ciclo.controlo_caminho, {"vel": 0.0})   # escrita PARCIAL de vento
    _espera(lambda: ciclo.controlo.n_ventos > n_ventos, JANELA_S, "o vento ser aplicado")
    time.sleep(0.3)
    c.ok("[§2] (a/c) reescrita do ficheiro SEM bloco de camera novo (vento) NAO re-aplica a camara",
         ciclo.controlo.n_cameras == 2 and _attrs(cam) == attrs_antes and _aplicado3(cam, comando_a),
         f"aplicacoes={ciclo.controlo.n_cameras} · escritas attrs={_attrs(cam)} · "
         f"ventos={ciclo.controlo.n_ventos}")

    # (e1) TELEMETRIA EM REPOUSO (drone parado: valores cruzados exactos, sem corrida de leitura)
    linhas = ciclo.linhas()
    esperado = _pos_drone(ciclo.env.data)
    ultima = linhas[-1] if linhas else {}
    camera = ultima.get("camera")
    chave_ok = bool(linhas) and all(len(l) == 19 and list(l)[-1] == "camera" for l in linhas)
    bloco_ok = (isinstance(camera, dict)
                and set(camera) == {"azimute", "elevacao", "distancia", "alvo"}
                and isinstance(camera["alvo"], list) and len(camera["alvo"]) == 3)
    alvo_ok = (bloco_ok and _perto(camera["alvo"], esperado, TOL_REPOUSO)
               and _perto(camera["alvo"], _lookat_de(cam), TOL_REPOUSO)
               and _perto(camera, _valores3_de(cam), TOL_REPOUSO))
    c.ok("[§2] TELEMETRIA em repouso: 19 chaves, `camera` por ultima = {azimute, elevacao, distancia, "
         "alvo} com alvo = lookat REAL = drone+offset (sem viewer seria null)",
         chave_ok and bloco_ok and alvo_ok,
         f"{len(linhas)} linhas · camera={camera} · esperado alvo={esperado}")

    # (b) «RATO»: mudanças EXTERNAS em azimute/elevacao/distancia PRESERVADAS entre comandos
    cam.azimuth, cam.elevation, cam.distance = 111.0, 22.0, 9.5            # o «rato» do dono
    rato = _valores3_de(cam)
    escritas_rato = _attrs(cam)
    n_ventos = ciclo.controlo.n_ventos
    sim_site.escrever_controlo(ciclo.controlo_caminho, {"vel": 0.0})      # outra escrita parcial pelo meio
    _espera(lambda: ciclo.controlo.n_ventos > n_ventos, JANELA_S, "o vento ser aplicado (2)")
    time.sleep(0.3)
    c.ok("[§2] (b) mudanca EXTERNA do cam («rato») em azimute/elevacao/distancia e PRESERVADA entre "
         "comandos (so o lookat e do seguimento)",
         _aplicado3(cam, rato) and _attrs(cam) == escritas_rato,
         f"cam={_valores3_de(cam)} (esperado {rato}) · escritas attrs={escritas_rato}")

    # PAN do rato → SOBREPOSTO pelo seguimento (3ª-pessoa: o alvo não sai do drone)
    pan_antes, seg_antes = cam.lookat.pan, cam.lookat.seguimento
    cam.lookat[0], cam.lookat[1], cam.lookat[2] = -4.0, -3.0, -2.0
    reposto = _espera(lambda: cam.lookat.seguimento > seg_antes
                      and _perto(_lookat_de(cam), _pos_drone(ciclo.env.data), TOL_REPOUSO),
                      PANO_S, "o PAN ser sobreposto pelo seguimento")
    c.ok("[§2] PAN do rato e SOBREPOSTO pelo seguimento (o lookat volta ao drone no frame seguinte)",
         reposto and cam.lookat.pan == pan_antes + 3 and cam.lookat.seguimento > seg_antes,
         f"lookat={_lookat_de(cam)} · drone+offset={_pos_drone(ciclo.env.data)} · "
         f"escritas pan={cam.lookat.pan} · seguimento={cam.lookat.seguimento}")

    # (b) `seq` novo com os MESMOS valores → RE-APLICA (assinatura = seq + valores; o servidor carimba)
    antes = _attrs(cam)
    ciclo.comando(comando_a)                                  # mesmos valores; o POST carimba seq novo
    reapplicou = _espera(lambda: ciclo.controlo.n_cameras >= 3, JANELA_S, "o re-aplicar do seq novo")
    time.sleep(0.3)
    c.ok("[§2] (b) `seq` NOVO com os MESMOS valores RE-APLICA (assinatura = seq + valores)",
         reapplicou and ciclo.controlo.n_cameras == 3 and _attrs(cam) == tuple(a + 1 for a in antes)
         and _aplicado3(cam, comando_a),
         f"aplicacoes={ciclo.controlo.n_cameras} · escritas attrs {antes} -> {_attrs(cam)}")

    # (g) REPOR VISTA = enviar os valores de CAM_PADRAO como um comando normal
    antes = _attrs(cam)
    ciclo.comando(dict(sim_view.CAM_PADRAO))
    reposto_vista = _espera(lambda: ciclo.controlo.n_cameras >= 4, JANELA_S, "o REPOR VISTA")
    time.sleep(0.3)
    c.ok("[§2] (g) REPOR VISTA = enviar os valores de CAM_PADRAO como comando normal restaura a camara",
         reposto_vista and ciclo.controlo.n_cameras == 4 and _attrs(cam) == tuple(a + 1 for a in antes)
         and _aplicado3(cam, sim_view.CAM_PADRAO),
         f"cam={_valores3_de(cam)}")

    # (f) contrato de FICHEIRO: bloco v1 COM `alvo` escrito à mão aplica os 3 valores (`alvo` ignorado)
    sim_site.escrever_controlo(ciclo.controlo_caminho,
                               {"camera": {"azimute": 5.0, "elevacao": 5.0, "distancia": 1.0,
                                           "alvo": [0.0, 0.0, 0.0], "seq": 9}})
    aplicou = _espera(lambda: ciclo.controlo.n_cameras >= 5, JANELA_S, "o bloco de ficheiro v1")
    c.ok("[§2] (f) bloco de FICHEIRO v1 (com `alvo`) escrito à mao aplica os 3 valores — o runner "
         "ignora as chaves que nao conhece",
         aplicou and _aplicado3(cam, {"azimute": 5.0, "elevacao": 5.0, "distancia": 1.0}),
         f"cam={_valores3_de(cam)}")

    # (a) MOVIMENTO REAL pela física + SEGUIMENTO a cada frame + telemetria que acompanha. O episódio
    # anterior já se acabou (quad sem estabilização: capota sozinho pela física) — REINICIAR põe o drone
    # inteiro e pousado, e o empuxo constante da política leva-o DE VERDADE (sem teleporte).
    ciclo.politica.acao[:] = (0.35, 0.0, 0.0, 0.0)   # empuxo acima do hover: a FISICA leva o drone
    bruto = sim_site.ler_controlo_bruto(ciclo.controlo_caminho)
    sim_site.escrever_controlo(ciclo.controlo_caminho,
                               {"reiniciar": int(bruto.get("reiniciar") or 0) + 1})
    reiniciou = _espera(lambda: any(l.get("passo") == 0 and l.get("ep", 1) >= 2 for l in ciclo.linhas()),
                        JANELA_S, "o REINICIAR do episodio")
    pos0 = _pos_drone(ciclo.env.data)
    moveu = _espera(lambda: _dist(_pos_drone(ciclo.env.data), pos0) >= LIMIAR_MOV, JANELA_S,
                    "o drone mover-se pela fisica")
    seg0, ruim0 = cam.lookat.seguimento, cam.lookat.seguimento_ruim
    linhas_antes = ciclo.linhas()
    time.sleep(0.05)                                       # janela de observacao com o drone A MOVER-SE
    seg1, ruim1 = cam.lookat.seguimento, cam.lookat.seguimento_ruim
    deslocamento = _dist(_pos_drone(ciclo.env.data), pos0)
    c.ok("[§2] MOVIMENTO pela fisica (REINICIAR + empuxo pela politica; sem teleporte): o drone "
         "deslocou-se de facto",
         reiniciou and moveu and deslocamento >= LIMIAR_MOV,
         f"reiniciou={reiniciou} · deslocamento {deslocamento:.3f} m (limiar {LIMIAR_MOV} m) · "
         f"pos0={pos0} -> {_pos_drone(ciclo.env.data)}")
    c.ok("[§2] SEGUIMENTO 3a pessoa: lookat == body(CAM_CORPO).xpos + CAM_OFFSET a CADA frame (colagem "
         "exacta, sem lag) enquanto o drone se move pela fisica",
         moveu and seg1 - seg0 >= 50 and ruim1 == 0,
         f"{seg1 - seg0} escritas de seguimento na janela · {ruim1 - ruim0} fora da colagem · "
         f"pior desvio {cam.lookat.pior:.2e} m (tol {TOL_CAM:.0e})")

    _espera(lambda: len(ciclo.linhas()) > len(linhas_antes), JANELA_S, "uma linha nova de telemetria")
    linhas_depois = ciclo.linhas()
    alvo_ini = (linhas_antes[-1].get("camera") or {}).get("alvo") if linhas_antes else None
    alvo_fim = (linhas_depois[-1].get("camera") or {}).get("alvo") if linhas_depois else None
    cresceu = (isinstance(alvo_ini, list) and isinstance(alvo_fim, list)
               and _dist(alvo_fim, alvo_ini) >= 0.5 * LIMIAR_MOV)
    c.ok("[§2] TELEMETRIA em movimento: o `camera.alvo` das linhas acompanha o drone (desloca-se com ele)",
         cresceu, f"alvo {alvo_ini} -> {alvo_fim}")


def roteiro_sem_viewer(ciclo: Ciclo, c: Checagens) -> None:
    """§2d: SEM viewer — um bloco de câmara no controlo não faz mal nenhum e a telemetria diz `null`."""
    _espera(lambda: len(ciclo.linhas()) >= 2, JANELA_S, "a telemetria correr")
    ciclo.comando({"azimute": 45.0, "elevacao": -30.0, "distancia": 4.0})
    time.sleep(0.3)
    linhas = ciclo.linhas()
    c.ok("[§2] (d) SEM viewer: o bloco de camera e ignorado sem erro e a telemetria publica "
         "`camera: null` (nada se inventa)",
         len(linhas) >= 2 and all(l.get("camera") is None and len(l) == 19 for l in linhas)
         and ciclo.controlo.n_cameras == 0,
         f"{len(linhas)} linhas com camera null · aplicacoes de camara={ciclo.controlo.n_cameras}")


def checa_ciclo(pasta: Path) -> Checagens:
    """§2: o ciclo REAL do runner — com viewer falso instrumentado e depois sem viewer."""
    c = Checagens("§2 ciclo REAL do runner (HoverEnv + politica de acao, viewer falso, fator-tempo 0)")
    _titulo(c.titulo)
    Ciclo(pasta, "com_viewer").correr(c, roteiro_com_viewer)
    Ciclo(pasta, "sem_viewer", com_viewer=False).correr(c, roteiro_sem_viewer)
    return c


# ==================================================================================================== §3
class Servidor:
    """`sim_site.py` a SÉRIO (subprocesso no seu grupo) com o URL lido do stdout e as linhas guardadas."""

    def __init__(self, pasta: Path, nome: str, modelo: Path, porta: int = PORTA_HTTP) -> None:
        self.controlo = pasta / f"{nome}_controle.json"
        self.telemetria = pasta / f"{nome}_telemetria.jsonl"
        for caminho in (self.controlo, self.telemetria):
            caminho.unlink(missing_ok=True)
        self.modelo, self.porta = modelo, porta
        self.linhas: list[str] = []
        self.url: str | None = None
        self.processo: subprocess.Popen | None = None

    def __enter__(self) -> Self:
        comando = [sys.executable, str((_FONTES or _AQUI) / "sim_site.py"), "--sem-browser", "--sem-janela",
                   "--port", str(self.porta), "--controlo", str(self.controlo),
                   "--telemetria", str(self.telemetria), "--fator-tempo", f"{FATOR_TEMPO:g}",
                   "--model", str(self.modelo)]
        self.processo = subprocess.Popen(comando, cwd=str(_AQUI), stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
        threading.Thread(target=self._ler, name=f"stdout-{self.controlo.stem}", daemon=True).start()
        t0 = time.perf_counter()
        while self.url is None and time.perf_counter() - t0 < ESPERA_S:
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


def checa_http(pasta: Path, modelo: Path) -> Checagens:
    """§3: servidor real (`--sem-janela`, porta 8561) — burst, rotas, validação v2 e publicação honesta."""
    c = Checagens(f"§3 servidor REAL (sim_site.py + runner --sem-janela, porta {PORTA_HTTP})")
    _titulo(c.titulo)
    with Servidor(pasta, "http", modelo) as s:
        # BURST FRIO: o PRIMEIRO tráfego do servidor são 40 ligações de uma vez (×3 rondas) — o cenário
        # medido pelo verificador independente (fila do `listen()`; o default do stdlib, 5, deixava POSTs
        # por servir e ligações a demorar segundos: um comando do dono que não chega).
        porta = int(s.url.rsplit(":", 1)[1])
        antes_burst = sim_site.ler_controlo_bruto(s.controlo)
        seq_antes = antes_burst.get("camera", {}).get("seq", 0)
        servidos, json_ok, tempos = 0, 0, []
        for _ronda in range(3):
            t0 = time.perf_counter()
            for resultado in _burst_frio(porta, 40):
                servidos += resultado.startswith("HTTP")
                json_ok += "json:ok" in resultado
            tempos.append(time.perf_counter() - t0)
        depois_burst = sim_site.ler_controlo_bruto(s.controlo)
        seq_depois = depois_burst.get("camera", {}).get("seq", 0)
        sem_resets = depois_burst.get("reiniciar") == antes_burst.get("reiniciar") \
            and s.processo.poll() is None
        c.ok("[§3] burst FRIO de 40 ligações × 3 rondas: 120/120 POSTs servidos E aplicados, sem resets "
             "e sem JSON partido (fila do listen >= 40: nenhum comando do dono se perde)",
             servidos == 120 and json_ok == 120 and seq_depois == seq_antes + 120 and sem_resets,
             f"{servidos}/120 servidos · {json_ok}/120 JSON valido · camera.seq {seq_antes} -> "
             f"{seq_depois} · reiniciar={depois_burst.get('reiniciar')!r} · "
             f"rondas em {[f'{t:.2f}s' for t in tempos]}")

        apanhou = s.esperar(lambda e: e["passo"] > 0)
        c.ok("[§3] o runner real arrancou e publica telemetria (a camara nao mexe na fisica)",
             apanhou is not None, f"passo={None if apanhou is None else apanhou['passo']}")

        rotas = [("/api/sim", "GET", None), ("/api/state", "GET", None), ("/api/vento", "POST",
                 {"vel": 1.0}), ("/api/vento-dinamico", "POST", {"modo": "nenhum"}), ("/api/parar", "POST",
                 None), ("/api/reiniciar", "POST", None), ("/api/loop", "POST", {"ativo": False}),
                 ("/api/camera", "POST", {"azimute": 10.0})]
        codigos = []
        for rota, metodo, corpo in rotas:
            if metodo == "GET":
                s.get(rota)
                codigos.append(200)
            else:
                codigos.append(s.post(rota, corpo)[0])
        codigo_404, _ = s.post("/api/nao_existe", {})
        c.ok("[§3] as 8 rotas respondem (2 GET + 6 POST, /api/camera incluida) e rota desconhecida e 404",
             codigos == [200] * 8 and codigo_404 == 404, f"codigos={codigos} · 404={codigo_404}")

        recusas = [({"alvo": [0, 0, 1]}, "desconhecidas"), ({"alvo": None}, "desconhecidas"),
                   ({"outra": 1}, "desconhecidas"), ({"distancia": 0.0}, "distancia"),
                   ({"distancia": 20.5}, "distancia"), ({"elevacao": 95.0}, "elevacao"),
                   ({"azimute": float("inf")}, "finito"),
                   ({"distancia": 1.0, "distandia": 2.0}, "escolha um")]
        bom = True
        detalhes = []
        for corpo, marca in recusas:
            codigo, resposta = s.post("/api/camera", corpo)
            bom = bom and codigo == 400 and marca in str(resposta.get("erro", ""))
            detalhes.append(f"{codigo} {resposta.get('erro', '')[:50]}")
        c.ok("[§3] (c) POST /api/camera recusa CHAVE DESCONHECIDA (alvo v1 incluido), ambiguidade "
             "distancia+distandia, distancia<=0 (>20) e elevacao fora de [-90,90] com 400 claro",
             bom, " | ".join(detalhes))

        nulos = [({"azimute": None}, "nulo"), ({"elevacao": None}, "nulo"), ({"distancia": None}, "nulo")]
        bom_nulo, detalhes = True, []
        for corpo, marca in nulos:
            codigo, resposta = s.post("/api/camera", corpo)
            bom_nulo = bom_nulo and codigo == 400 and marca in str(resposta.get("erro", ""))
            detalhes.append(f"{codigo} {resposta.get('erro', '')[:50]}")
        codigo_ausente, _ = s.post("/api/camera", {"azimute": 45.0})
        c.ok("[§3] (c) campos PRESENTES com null -> 400 (mensagem `nulo`; null NAO e ausente) e a "
             "AUSENCIA continua a completar do bloco em vigor (200)",
             bom_nulo and codigo_ausente == 200, " | ".join(detalhes))

        base = s.post("/api/camera", {"azimute": 33.0, "elevacao": -12.0, "distancia": 2.5})[1]["camera"]
        codigos_dec, blocos = [], []
        for corpo in ({}, {"seq": 7}, {"seq": None}):
            codigo, resposta = s.post("/api/camera", corpo)
            codigos_dec.append(codigo)
            blocos.append(resposta.get("camera", {}))
        dec_ok = (codigos_dec == [200, 200, 200] and len(blocos) == 3
                  and all(b.get("azimute") == 33.0 and b.get("elevacao") == -12.0
                          and b.get("distancia") == 2.5 for b in blocos)
                  and [b.get("seq") for b in blocos] == [base["seq"] + 1, base["seq"] + 2,
                                                         base["seq"] + 3])
        c.ok("[§3] (c) DECISAO v2: `{}` e `{\"seq\": n}` sao ACEITES (200) — subconjunto vazio / `seq` do "
             "corpo IGNORADO (o servidor carimba o seu; valores mantidos)",
             dec_ok, f"codigos={codigos_dec} · seqs {[b.get('seq') for b in blocos]} "
             f"(base {base['seq']}) · blocos={blocos}")

        cod_alias, r_alias = s.post("/api/camera", {"distandia": 1.75})
        cod_dup, r_dup = s.post("/api/camera", {"distancia": 1.0, "distandia": 2.0})
        c.ok("[§3] (c) alias `distandia` aceite e mapeado para `distancia`; os dois juntos -> 400 "
             "(ambiguo: escolha um)",
             cod_alias == 200 and r_alias.get("camera", {}).get("distancia") == 1.75
             and cod_dup == 400 and "escolha um" in str(r_dup.get("erro", "")),
             f"alias HTTP {cod_alias} dist={r_alias.get('camera', {}).get('distancia')} · "
             f"dup HTTP {cod_dup} {r_dup.get('erro', '')[:50]}")

        bloco1 = s.post("/api/camera", {"azimute": 33.0, "elevacao": -12.0, "distancia": 2.5})[1]["camera"]
        bloco2 = s.post("/api/camera", {"azimute": 33.0})[1]["camera"]
        c.ok("[§3] (b) o `seq` incrementa a cada pedido no SERVIDOR e subconjuntos mantêm o resto do "
             "bloco em vigor",
             bloco2["seq"] == bloco1["seq"] + 1 and bloco2["azimute"] == 33.0
             and bloco2["elevacao"] == bloco1["elevacao"] and bloco2["distancia"] == bloco1["distancia"],
             f"seqs={bloco1['seq']} -> {bloco2['seq']} · bloco2={bloco2}")

        s.post("/api/vento", {"vel": 3.0, "azimute": 90.0})
        s.post("/api/loop", {"ativo": True})
        s.post("/api/reiniciar")
        antes = sim_site.ler_controlo_bruto(s.controlo)
        s.post("/api/camera", {"azimute": 200.0, "elevacao": 10.0, "distancia": 5.0})
        depois = sim_site.ler_controlo_bruto(s.controlo)
        intocados = all(depois.get(campo) == antes.get(campo)
                        for campo in ("vel", "azimute", "elevacao", "ativo", "loop", "reiniciar",
                                      "dinamico"))
        resumo_antes = {k: antes.get(k) for k in ("vel", "loop", "reiniciar")}
        resumo_depois = {k: depois.get(k) for k in ("vel", "loop", "reiniciar")}
        c.ok("[§3] (f) escritas de camera nunca tocam em loop/reiniciar/vento/dinamica (HTTP, merge)",
             intocados and antes.get("reiniciar", 0) >= 1
             and depois.get("reiniciar") == antes.get("reiniciar") and depois.get("loop") is True,
             f"antes={resumo_antes} depois={resumo_depois} "
             f"camera.seq={depois.get('camera', {}).get('seq')}")

        estado = s.get("/api/state")
        sim = s.get("/api/sim")
        padrao_igual = (estado.get("camera_padrao") == sim_site.CAM_PADRAO == sim.get("camera_padrao")
                        and set(sim_site.CAM_PADRAO) == {"azimute", "elevacao", "distancia"})
        c.ok("[§3] (e) `camera_padrao` == CAM_PADRAO (SEM alvo) publicado em GET /api/state e GET /api/sim",
             padrao_igual, f"state={estado.get('camera_padrao')}")
        c.ok("[§3] (e) `camera_atual` e honesto: null sem viewer na telemetria (nunca um valor inventado)",
             estado.get("camera_atual") is None and sim.get("camera_atual") is None,
             f"state.camera_atual={estado.get('camera_atual')!r} · sim.camera_atual={sim.get('camera_atual')!r}")

        fim = s.esperar(lambda e: e["passo"] > 20)
        linhas = sim_site.ultimas_linhas(s.telemetria, 200)
        c.ok("[§3] (e) a telemetria do runner real tem 19 chaves com `camera` por ultima (null sem viewer)",
             fim is not None and len(linhas) >= 5
             and all(len(l) == 19 and list(l)[-1] == "camera" and l.get("camera") is None for l in linhas),
             f"{len(linhas)} linhas · ultimas chaves={list(linhas[-1])[-2:] if linhas else None}")

        s.post("/api/loop", {"ativo": False})
        padrao = s.get("/api/state")["camera_padrao"]
        seq_antes = sim_site.ler_controlo_bruto(s.controlo).get("camera", {}).get("seq", 0)
        codigo, resposta = s.post("/api/camera", dict(padrao))
        ficheiro = sim_site.ler_controlo_bruto(s.controlo).get("camera", {})
        c.ok("[§3] (g) REPOR VISTA pela API: mandar os valores de `camera_padrao` como comando normal "
             "escreve o bloco (seq novo) e o runner segue sem erro",
             codigo == 200 and resposta.get("camera", {}).get("seq") == seq_antes + 1
             and all(ficheiro.get(k) == padrao[k] for k in ("azimute", "elevacao", "distancia"))
             and s.processo.poll() is None,
             f"HTTP {codigo} seq {seq_antes} -> {resposta.get('camera', {}).get('seq')} · "
             f"ficheiro={ficheiro}")
    return c


# ==================================================================================================== §4
MUTACOES = (
    ("m1-seguimento-removido", "sim_view.py",
     "    corpo = data.body(CAM_CORPO)",
     "    return None  # MUTACAO",
     "--so-ciclo", ("SEGUIMENTO",)),
    ("m2-posicao-velha", "sim_view.py",
     "        cam.lookat[i] = alvo[i]",
     "        cam.lookat[i] = cam.lookat[i]  # MUTACAO",
     "--so-ciclo", ("SEGUIMENTO",)),
    ("m3-assinatura-sem-seq", "sim_view.py",
     '"distancia": self.distancia, "seq": self.seq}, sort_keys=True)',
     '"distancia": self.distancia}, sort_keys=True)',
     "--so-ciclo", ("RE-APLICA",)),
    ("m4-validacao-desconhecidas", "sim_site.py",
     'desconhecidas = set(dados) - {"azimute", "elevacao", "distancia", "distandia", "seq"}',
     "desconhecidas = set()  # MUTACAO",
     "--so-pecas", ("DESCONHECIDA",)),
    ("m5-validacao-null", "sim_site.py",
     "        if campo in campos and campos[campo] is None:",
     "        if False:  # MUTACAO",
     "--so-pecas", ("nulo",)),
)


def _fontes_mutadas(pasta: Path, nome: str, ficheiro: str, antigo: str, novo: str) -> Path:
    """Cópia das fontes em teste com UMA mutação aplicada (apagada no fim do processo)."""
    destino = pasta / f"fontes_{nome}"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    for nome_f in ("env.py", "sim_view.py", "sim_site.py"):
        shutil.copyfile((_FONTES or _AQUI) / nome_f, destino / nome_f)
    codigo = (destino / ficheiro).read_text(encoding="utf-8")
    if codigo.count(antigo) != 1:
        raise SystemExit(f"[teste] mutação {nome}: o alvo aparece {codigo.count(antigo)}x (esperava 1) — "
                         f"o {ficheiro} mudou? ({antigo[:60]!r}…)")
    (destino / ficheiro).write_text(codigo.replace(antigo, novo), encoding="utf-8")
    return destino


def checa_mutacao(pasta: Path) -> Checagens:
    """§4: as MUTAÇÕES do contrato têm de fazer o §1/§2 FALHAR — a prova de não-tautologia (g).

    Cada mutação corre numa cópia das fontes (`--fontes`) com o MESMO §1 ou §2, num processo separado: se
    o teste fosse tautológico («o alvo segue sempre», «a validação nunca apanha nada»), as mutações
    passariam. Todas as cópias ficam em $TMPDIR (a `pasta` do teste) e são apagadas no fim.
    """
    c = Checagens("§4 nao-tautologia: mutacoes do contrato tem de fazer o §1/§2 FALHAR")
    _titulo(c.titulo)
    for nome, ficheiro, antigo, novo, modo, esperadas in MUTACOES:
        destino = _fontes_mutadas(pasta, nome, ficheiro, antigo, novo)
        processo = subprocess.run([sys.executable, str(_AQUI / "teste_camera.py"), "--fontes", str(destino),
                                   modo, "--pasta", str(pasta / f"corrida_{nome}")],
                                  capture_output=True, text=True, cwd=str(_AQUI),
                                  check=False)
        falhas = [linha.strip() for linha in processo.stdout.splitlines() if "FALHA]" in linha]
        apanhou = [marca for marca in esperadas if any(marca in linha for linha in falhas)]
        c.ok(f"[§4] mutação {nome} ({ficheiro}): {modo} FALHA (o teste nao e tautologico)",
             processo.returncode != 0 and bool(apanhou),
             f"exit {processo.returncode} · falhas={[l[:70] for l in falhas[:4]]} · "
             f"marcas apanhadas={apanhou}")
        shutil.rmtree(destino, ignore_errors=True)
    return c


# ---------------------------------------------------------------------------------------------- main
def analisar_argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Prova dos comandos de CÂMARA v2 (TERCEIRA-PESSOA): alvo segue o drone a cada frame "
                    "(lookat = body(CAM_CORPO).xpos + CAM_OFFSET), orbitar/zoom aplicado 1x por mudança "
                    "de assinatura e preservado (rato livre; PAN sobreposto), validação 400 para "
                    "null/chaves desconhecidas ({} e {seq:n} aceites — decisão documentada), burst frio "
                    "de 40, telemetria `camera` = {azimute, elevacao, distancia, alvo} e REPOR VISTA — "
                    "com prova de não-tautologia por mutação.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sem-http", action="store_true",
                   help="salta o §3 (servidor real) e o §4 (mutações): corre §1 + §2")
    p.add_argument("--so-ciclo", action="store_true",
                   help="corre SÓ o §2 (é o que as mutações do §4 no sim_view.py usam)")
    p.add_argument("--so-pecas", action="store_true",
                   help="corre SÓ o §1 (é o que as mutações do §4 no sim_site.py usam)")
    p.add_argument("--sem-mutacao", action="store_true", help="salta o §4 (as mutações)")
    p.add_argument("--model", type=Path, default=None,
                   help="modelo do runner para o §3; por omissão o mesmo que o site escolheria")
    p.add_argument("--fontes", type=Path, default=None, metavar="DIR",
                   help="pasta com env.py/sim_view.py/sim_site.py alternativos (importados ANTES da árvore)")
    p.add_argument("--pasta", type=Path, default=None,
                   help="onde escrever os controlos/telemetrias do teste (padrão: pasta temporária)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = analisar_argumentos(argv)
    pasta = args.pasta
    if pasta is None:
        pasta = Path(tempfile.mkdtemp(prefix="teste_camera_"))
    pasta.mkdir(parents=True, exist_ok=True)
    print(f"[teste] ficheiros do teste: {pasta}")
    print(f"[teste] fontes: {_FONTES or _AQUI} (env.py + sim_view.py + sim_site.py)")

    checagens: list[Checagens] = []
    if args.so_ciclo:
        checagens.append(checa_ciclo(pasta))
    elif args.so_pecas:
        checagens.append(checa_pecas(pasta))
    else:
        checagens.append(checa_pecas(pasta))
        checagens.append(checa_ciclo(pasta))
        if args.sem_http:
            print("\n[teste] --sem-http: salto o §3 (servidor real) — pedido EXPLICITO na linha de comando")
        else:
            modelo = args.model
            if modelo is None:
                modelo, motivo = _modelo_do_teste()
                if modelo is None:
                    print(f"\n[teste] FALHA: o §3 precisa de um modelo e o cabecalho promete-o — {motivo}")
                    print("[teste] indique --model CAMINHO (ou use --sem-http para o saltar DE PROPOSITO)")
                    return 1
                print(f"\n[teste] modelo do runner: {modelo} ({motivo})")
            checagens.append(checa_http(pasta, modelo))
            if args.sem_mutacao:
                print("\n[teste] --sem-mutacao: salto o §4 (provas de nao-tautologia)")
            else:
                checagens.append(checa_mutacao(pasta))

    total = sum(len(ch.linhas) for ch in checagens)
    falhas = [falha for ch in checagens for falha in ch.falhas]
    print(f"\n[teste] {total - len(falhas)}/{total} checagens OK")
    if falhas:
        print("[teste] FALHAS:")
        for falha in falhas:
            print(f"  · {falha}")
        return 1
    print("[teste] a camera v2 (3a pessoa) obedece ao contrato: o alvo segue o drone a cada frame "
          "(lookat = drone+offset), orbitar/zoom 1x por assinatura com rato livre (PAN sobreposto), "
          "validacao 400 (null/chaves desconhecidas; {} e {seq:n} aceites), burst frio servido e "
          "REPOR VISTA por comando normal")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
