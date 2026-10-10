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
  · `GET  /api/sim`               → `{"estado","loop","ep","passo","retorno","vento":{...},"linhas":[…]}` com
                                    as ≤200 últimas amostras da telemetria (objetos JSON, já parseados), mais
                                    `modelo`/`modelo_nome`, `vento_dinamico` (o que foi pedido),
                                    `vento_atual` (vetor vx,vy,vz + polar + modo, lido da telemetria),
                                    `camera_padrao` (valores de `CAM_PADRAO` = os de
                                    `mjv_defaultFreeCamera(model)`, só `{azimute, elevacao, distancia}`
                                    (SEM `alvo`: a câmara é terceira-pessoa e o alvo é sempre o drone) — o
                                    REPOR VISTA do site envia-os como comando normal) e `camera_atual`
                                    (`{azimute, elevacao, distancia, alvo:[x,y,z]}` da câmara REAL lida da
                                    telemetria — `alvo` = `lookat` real = drone+offset —, ou `null` sem
                                    dados);
                                    `loop` = modo EFETIVO do runner (o default é SEM REINÍCIO: a física
                                    continua no estado em que ficou e só um REINICIAR recomeça;
                                    `--com-loop`/`loop:true` = CONTÍNUO, reinicia sozinho no fim);
  · `GET  /api/state`             → resumo (acima + `modelo`/`modelo_nome`/`modelo_motivo`, `sim_vivo`,
                                    `pid`, `porta`, caminhos, nº de amostras, idade da última amostra,
                                    `camera_padrao`/`camera_atual`) e o
                                    painel `rpi5` (specs oficiais citadas + inferência medida no proxy +
                                    uso ao vivo: decisoes/s da telemetria × p50 ÷ 20 ms);
  · `POST /api/vento-dinamico`    → `{"modo": "nenhum"|"rajadas"|"aleatoria"|"frente"|"dryden"|
                                    "rajada_agora", "params": {...}, "ativo": bool}` — vento DINÂMICO ao vivo,
                                    SEM reiniciar o episódio. `rajadas`/`aleatoria`/`dryden` (e o `frente` do
                                    formato (b)) são validados pelo próprio `env.py` (`ValueError` → 400; no
                                    `aleatoria` só `p`/`duracao` têm semântica, a amostragem usa as faixas
                                    disponíveis: 0–5 m/s, 0–360°, ±90°); o `frente` aceita
                                    ainda o formato (a) `params = {vel, azimute, elevacao}` = degrau
                                    IMEDIATO do vento base (validado aqui com as faixas do `POST /api/vento`
                                    e escrito também no topo do controlo); `rajada_agora` é uma rajada
                                    dirigida one-shot (`u`, `azimute`, `elevacao`, `duracao`);
                                    `nenhum`/`ativo:false` desliga;
  · `POST /api/vento`             → `{"vel","azimute","elevacao"}` (qualquer subconjunto; faixas 0-5 m/s,
                                    0-360°, −90..90°; NaN/inf → 400) e escreve o controlo;
  · `POST /api/parar`             → **PARAR VENTO**, numa só escrita atómica: vento base a 0 (mantém
                                    azimute/elevação) **e** vento dinâmico em `nenhum` (`seq` novo). É o
                                    caminho que garante que, depois de parar, não fica nenhuma rajada ativa
                                    nem pendente e o `opt.wind` é exatamente o vento base comandado (0 m/s);
  · `POST /api/reiniciar`         → incrementa `reiniciar` no controlo → `{"contador": n}`: reset MANUAL,
                                    válido em qualquer estado (a correr, com o episódio terminado sem
                                    reinício, ou no meio de um episódio) — é o ÚNICO reset que existe;
  · `POST /api/loop`              → `{"ativo": bool}` liga/desliga o contínuo a quente. `false` = SEM
                                    REINÍCIO: no fim do episódio a física CONTINUA (nunca reinicia sozinha
                                    e nunca congela) até um REINICIAR. O PADRÃO no arranque é `false` (SEM
                                    REINÍCIO, pedido do dono em 2026-10-09); o arranque é AUTORITATIVO e
                                    corrige o `loop` que estiver no ficheiro de controlo, e a partir daí só
                                    este POST o muda (sticky);
  · `POST /api/camera`            → `{"azimute","elevacao","distancia"}` (qualquer subconjunto — até `{}`;
                                    SEM `alvo` — a câmara é TERCEIRA-PESSOA e o alvo é SEMPRE o drone —;
                                    o `seq` do corpo é IGNORADO e o servidor carimba sempre o seu a cada
                                    pedido, como o `dinamico.seq`;
                                    alias `distandia` é aceite e mapeado para `distancia`) ORBITA/zooma a
                                    CÂMARA da janela 3D: azimute finito (normalizado mod 360), elevacao
                                    [-90,90]°, distancia ]0,20] m (fora das faixas → 400 com o motivo).
                                    Um campo PRESENTE com valor `null` → **400** (`null` não é «ausente»)
                                    e uma chave DESCONHECIDA (ex. `alvo`) → **400** (mensagem clara):
                                    só a AUSÊNCIA do campo completa do bloco em vigor. Só APRESENTAÇÃO:
                                    não toca na física nem em nenhum comando. O runner aplica os 3 valores
                                    ao `viewer.cam` UMA VEZ por mudança de assinatura (seq+valores) — entre
                                    comandos o rato orbita/zooma livre (o PAN é intencionalmente sobreposto
                                    pelo seguimento do drone) — e o `lookat` segue o drone A CADA FRAME
                                    (`body("cf2").xpos` + offset constante); sem viewer ignora sem erro.
                                    REPOR VISTA = enviar os valores de `camera_padrao` como um comando
                                    normal.

São 9 rotas `/api/*` no total (2 GET + 7 POST); a 9.ª, `POST /api/bateria`
`{"acao": "recarregar"|"nova"}`, é da planta REAL (recarregar fecha o ciclo com desgaste; nova = pack novo).

O ficheiro de controlo (o site escreve, o runner lê a cada passo de decisão) e a telemetria (o runner
escreve, o site lê) estão descritos no cabeçalho do `sim_view.py` — o ARRANQUE escreve sempre o `loop`
decidido pela linha de comandos (default `false`; `--com-loop` liga o contínuo), preservando o resto do
ficheiro, e responde aos POSTs com escritas ATÓMICAS que fazem MERGE sobre o que já lá está: uma escrita
parcial nunca toca em `loop` nem em `reiniciar` (ver `escrever_controlo`). Depois do arranque, o `loop` e o
contador `reiniciar` EFETIVOS vivem em MEMÓRIA no servidor (`Servidor.memorizados`): se o ficheiro for
apagado ou corrompido durante a execução, a próxima escrita recria-o com esses valores — nunca com os de
`CONTROLO_INICIAL` (ver `_comandos_memorizados`).

FIABILIDADE sob POSTs concorrentes (o servidor é `ThreadingHTTPServer`, uma thread por pedido):

  · a fila de ligações do `listen()` é `FILA_LIGACOES = 64` (`ServidorHTTP`), não o 5 do stdlib: com 5, um
    burst frio de 40 ligações simultâneas deixava POSTs por servir (comandos do dono perdidos ou atrasados
    segundos) — ver a constante e o `teste_camera.py` (§3, burst 40 × 3 rondas);
  · o temporário da escrita atómica tem nome ÚNICO POR ESCRITA (`nome_temporario`: pid + thread + contador);
    com um nome partilhado, dois POSTs simultâneos disputavam o mesmo ficheiro e o segundo `os.replace`
    devolvia **HTTP 500** — um PARAR que falha não para rajada nenhuma;
  · cada pedido faz o seu ler-modificar-escrever sob a MESMA trava (`trava_controlo`): um POST concorrente
    nunca reverte o resultado de outro (nem o contador de REINICIAR se perde);
  · falha de escrita não deixa `.tmp` órfãos.
"""
from __future__ import annotations

import argparse
import itertools
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
sys.path[:0] = [str(_RAIZ), str(_AQUI)]      # para o `env.valida_vento_dinamico` (importado só quando usado)
SIM_VIEW = _AQUI / "sim_view.py"
DIST = _AQUI / "site" / "dist"
INDEX = DIST / "index.html"
CONTROLO_OMISSAO = _AQUI / "out" / "controle_vento.json"
TELEMETRIA_OMISSAO = _AQUI / "out" / "sim_telemetria.jsonl"

VEL_MAX, AZIM_MAX, ELEV_MAX = 5.0, 360.0, 90.0     # faixas do contrato (as mesmas do sim_view.py)
MODOS_DINAMICOS = ("nenhum", "rajadas", "aleatoria", "frente", "dryden", "rajada_agora")   # modos do vento ao vivo
MODOS_DINAMICOS_ENV = ("rajadas", "aleatoria", "frente", "dryden")   # os que o `env.definir_vento_dinamico` conhece
FRENTE_BASE, FRENTE_ENV = ("vel", "azimute", "elevacao"), ("u_max", "t_s")   # os 2 formatos do `frente`
RAJADA_DURACAO_PADRAO = 25        # passos de decisão — duração da rajada one-shot
RAJADA_U_PADRAO = 3.0             # m/s — amplitude da rajada one-shot sem `u` nos params
RAJADA_U_MAX = 5.0                # m/s — teto do contrato para a rajada one-shot
# CÂMARA da janela 3D (só apresentação, TERCEIRA-PESSOA): `CAM_PADRAO` são os valores de ARRANQUE do
# viewer (`mujoco.mjv_defaultFreeCamera(model, cam)` para o modelo deste experimento — o runner aplica-os
# no arranque, e esta cópia publica-os como `camera_padrao` para o site poder REPOR a vista), SEM `alvo`
# (contrato v2: o alvo da câmara é SEMPRE o drone — quem o escreve é o `seguir_drone` do runner). O
# `azimute` vem já normalizado mod 360 (340.0 ≡ −20.0 do `mjv_defaultFreeCamera`: a MESMA pose) para o
# REPOR fazer ida-e-volta exacta pelo contrato. As duas constantes (`sim_view.CAM_PADRAO` e esta) são
# idênticas DE PROPÓSITO: o site nunca importa MuJoCo, e o `teste_camera.py` prova as duas iguais entre si
# e iguais ao que o `mjv_defaultFreeCamera` devolve (módulo 360 no azimute).
CAM_PADRAO = {"azimute": 340.0, "elevacao": -20.0, "distancia": 0.27471697907043846}
CAM_DIST_MAX = 20.0               # m — teto do contrato para a `distancia` (a UI usa 0,1–10)
# painel RPi 5: o relatório do `deploy.py` (proxy x86 de 1 core do A76) fica AQUI e é lido a cada pedido
BENCHMARK_OMISSAO = _AQUI / "out" / "deploy_r10" / "deploy.json"
BUDGET_US = 20_000.0              # 50 Hz = 20 ms (o `periodo_us` do deploy.py)
NUCLEOS_SOC = 4                   # 4x Cortex-A76 no BCM2712
RPI5_SPECS = {
    "soc": "Broadcom BCM2712",
    "cpu": "4x Cortex-A76 @ 2,4 GHz (512 kB L2/nucleo + 2 MB L3)",
    "ram": "LPDDR4X-4267, 1-16 GB (variante)",
    "gpu": "VideoCore VII",
    "alimentacao": "5 V / 5 A (27 W); pico ~12 W",
    "throttle": "termico 80 -> 85 graus C (corte de 2,4 -> 1,5 GHz)",
    "alvo_hz": 50,
    "budget_ms": 20,
    "nucleos": NUCLEOS_SOC,
    "jitter_so": {"standard_ms_pior_caso": 9.4, "preempt_rt_us_max": 225,
                  "nota": "o jitter do SO e o gargalo real a 50 Hz: 9,4 ms de pior caso no kernel "
                          "standard vs 20 ms de periodo (PREEMPT_RT desce a <=225 us)"},
    "inferencia_publicada": {"modelo": "small CNN (ONNX Runtime, 1 core A76)",
                             "fp32_ms": 0.194, "int8_ms": 0.143, "fator_int8": 1.36,
                             "fator_int8_sdot": 1.83,
                             "nucleos_ort_default": "intra_op = nucleos fisicos; XNNPACK EP = 1"},
    "fonte": "Raspberry Pi 5 Product Brief (RP-008348-DS) + medicoes publicadas no A76",
    "nota": "specs do ALVO (Raspberry Pi 5); a imagem que o dono tem num B+ de 2014 nao tem estes numeros",
}
CONTROLO_INICIAL = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False, "reiniciar": 0,
                    "loop": False}       # SEM REINÍCIO por omissão (pedido do dono, 2026-10-09):
                                         # o episódio NÃO reinicia sozinho no fim — a física continua e só
                                         # um REINICIAR recomeça. `--com-loop` liga o CONTÍNUO no arranque.
# Chaves de COMANDO do controlo: só mudam por ação explícita (`POST /api/loop` / `POST /api/reiniciar`) e
# nunca são inventadas por uma leitura/escrita parcial — ver `ler_controlo` e `escrever_controlo`.
COMANDOS = ("loop", "reiniciar")
# CARIMBO DO ARRANQUE (corrida de arranque, 2026-10-09): o site escreve o `loop` inicial ANTES de lançar o
# runner, mas o runner demora segundos a importar (SB3/torch) e nessa janela o dono pode mudar o modo pelo
# `POST /api/loop`. Sem uma marca, o `fixar_loop` do runner revertia esse pedido legítimo («vence o valor
# velho»). Com ela, o ficheiro diz de quem é o valor: o arranque carimba `loop_arranque` com um token único e
# passa o MESMO token ao filho pela variável de ambiente; o POST limpa o carimbo. O runner só corrige o
# ficheiro quando o carimbo ainda é o dele (e aí o valor já é o do arranque, nada a escrever); sem carimbo
# nenhum — um POST — o `fixar_loop` respeita o valor e nunca o reverte (ver `sim_view.fixar_loop`).
# Os dois nomes têm de ser IGUAIS aos do `sim_view.py` (é o handshake; há uma checagem no teste do arranque).
CAMPO_ARRANQUE = "loop_arranque"
ENV_LOOP_ARRANQUE = "DRONE_LOOP_ARRANQUE"
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


def ler_controlo_bruto(caminho: Path) -> dict:
    """Conteúdo do ficheiro de controlo TAL E QUAL (`{}` se não existir ou não for um objeto JSON).

    É a base do merge de `escrever_controlo`: ausência é ausência — não se inventa ali um `loop: true` nem
    um `reiniciar: 0` que o dono não escreveu.
    """
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _comandos_memorizados(base: dict, lido: dict, memorizados: dict | None) -> dict:
    """Preenche as chaves de COMANDO que FALTAM com o último valor conhecido pelo SERVIDOR (`memorizados`).

    O ficheiro de controlo era a única memória do site: apagado (ou corrompido) durante a execução e reescrito
    logo a seguir por uma escrita parcial, ele renascia de `CONTROLO_INICIAL` — `loop: false` e
    `reiniciar: 0` — e o runner regressava a SEM REINÍCIO **sem nenhum `POST /api/loop`** (defeito medido,
    2026-10-09; o contrato diz que depois do arranque só o `POST /api/loop` muda o `loop`). Em RUNTIME a
    recriação passa a devolver o estado EFETIVO em memória; só o ARRANQUE é autoritativo (`main`).
    Um valor que o ficheiro TENHA (mesmo que escrito à mão) continua a mandar: a memória só cobre ausência.
    """
    if not memorizados:
        return base
    return {**base, **{chave: memorizados[chave] for chave in COMANDOS
                       if chave not in lido and chave in memorizados}}


def ler_controlo(caminho: Path, memorizados: dict | None = None) -> dict:
    """Controlo em vigor (tolerante): o que está no ficheiro + os PADRÕES DE VENTO do contrato.

    Ficheiro ausente/ilegível → `CONTROLO_INICIAL`. As chaves de COMANDO (`loop`, `reiniciar`) NÃO são
    inventadas quando o ficheiro existe: ausência é ausência — é o que impede uma escrita parcial de
    ressuscitar `loop: true` ou de contar um REINICIAR que ninguém pediu. Quem lê usa `.get(campo, padrão)`.
    `memorizados` (o servidor em execução) é a única excepção: sem a chave no ficheiro, vale o último valor
    que o site fixou em memória — ver `_comandos_memorizados`.
    """
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            base = {**{chave: valor for chave, valor in CONTROLO_INICIAL.items() if chave not in COMANDOS},
                    **dados}
            return _comandos_memorizados(base, dados, memorizados)
    except (OSError, ValueError):
        pass
    return _comandos_memorizados(dict(CONTROLO_INICIAL), {}, memorizados)


# ------------------------------------------------------------------- fiabilidade do controlo (concorrência)
# O servidor é um `ThreadingHTTPServer`: cada POST corre na sua thread, em paralelo com os outros. Estas duas
# peças são o que faz uma escrita concorrente ser segura (ver `escrever_controlo`).
_TRAVA_CONTROLO = threading.RLock()     # ler+modificar+escrever o controlo é INDIVISÍVEL dentro do processo
_TMP_CONTADOR = itertools.count(1)      # contador monotónico: o nome do temporário nunca se repete


def nome_temporario(caminho: Path) -> Path:
    """Nome do ficheiro temporário da escrita atómica: ÚNICO POR ESCRITA.

    `pid` + thread + contador monotónico. O nome antigo (`.{nome}.tmp{pid}`) era o MESMO para todas as
    threads do servidor: dois POSTs simultâneos escreviam no mesmo temporário e o segundo `os.replace`
    falhava com `FileNotFoundError` → HTTP 500 (o pedido perdia-se, mesmo com o ficheiro de controlo
    intacto). Único por escrita, o `os.replace` nunca disputa o mesmo nome.
    """
    return caminho.with_name(f".{caminho.name}.tmp.{os.getpid()}.{threading.get_ident()}."
                             f"{next(_TMP_CONTADOR)}")


def trava_controlo() -> threading.RLock:
    """Trava (reentrante) que torna ATÓMICO o ler-modificar-escrever de um pedido.

    Quem lê o controlo para decidir o que escrever (`POST /api/vento`, `/api/vento-dinamico`, `/api/parar`,
    `/api/reiniciar`, `/api/loop`) envolve as duas operações nesta trava: sem ela, dois pedidos podiam ler o
    mesmo estado e o último a escrever revertia o do outro — um REINICIAR a perder o incremento por causa de
    um POST de vento concorrente, ou o contrário. `escrever_controlo` usa a MESMA trava, por isso envolver
    uma chamada a mais é seguro.
    """
    return _TRAVA_CONTROLO


def escrever_controlo(caminho: Path, dados: dict, memorizados: dict | None = None) -> dict:
    """Escreve o controlo de forma ATÓMICA (tmp no mesmo diretório + `os.replace`) e carimba `t`.

    O merge parte do FICHEIRO (ou de `CONTROLO_INICIAL` só quando ele ainda não existe) e sobrepõe-lhe
    `dados`: uma escrita PARCIAL — como as do `POST /api/vento` e `/api/vento-dinamico` — nunca reescreve
    `loop` nem `reiniciar` com valores por omissão. Era por aqui que uma mudança de vento re-ligava o loop
    e/ou mexia no contador de reinícios sem ninguém pedir.

    `memorizados` é a memória do SERVIDOR em execução (`Servidor.memorizados`, semeada pelo arranque): se o
    ficheiro for apagado ou ficar corrompido durante a execução, a recriação leva o `loop` e o `reiniciar`
    EFETIVOS — não os valores de arranque — e a memória fica actualizada com o que foi escrito. Sem ela
    (`None`: arranque, testes in-process) o comportamento é o de sempre.

    FIABILIDADE sob concorrência (o servidor é `ThreadingHTTPServer`: cada POST corre na sua thread):

    · o nome do temporário é ÚNICO POR ESCRITA (`nome_temporario`: pid + thread + contador monotónico).
      Com um nome partilhado (era `.{nome}.tmp{pid}`) dois POSTs simultâneos escreviam o MESMO ficheiro e o
      segundo `os.replace` rebentava com `FileNotFoundError` → **HTTP 500** — e um PARAR que devolve 500
      não para rajada nenhuma. O ficheiro nunca ficava meio-escrito (o rename é atómico), mas o pedido
      falhava;
    · a leitura+escrita do merge correm sob a MESMA trava (`_TRAVA_CONTROLO`, reentrante): sem ela dois
      pedidos podiam ler o mesmo estado e o último a escrever revertia o do outro — um REINICIAR concorrente
      com um POST de vento perdia o incremento do contador. Com a trava, cada escrita é um
      ler-modificar-escrever indivisível dentro do processo;
    · falha de escrita não deixa lixo: o temporário é apagado antes de a excepção subir (0 `.tmp` órfãos).
    """
    caminho = Path(caminho)
    with _TRAVA_CONTROLO:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        lido = ler_controlo_bruto(caminho) if caminho.is_file() else {}
        atual = dict(lido) if lido else dict(CONTROLO_INICIAL)     # ausente/ilegível/vazio: nasce completo
        atual = _comandos_memorizados(atual, lido, memorizados)    # RUNTIME: comandos EFETIVOS em memória
        registo = {**atual, **dados, "t": time.time()}
        tmp = nome_temporario(caminho)
        try:
            tmp.write_text(json.dumps(registo, separators=(",", ":")) + "\n", encoding="utf-8")
            os.replace(tmp, caminho)               # troca atómica: o runner nunca lê meio ficheiro
        except OSError:
            tmp.unlink(missing_ok=True)            # sem `.tmp` órfãos quando a escrita falha
            raise
        if memorizados is not None:
            memorizados.update({chave: registo[chave] for chave in COMANDOS if chave in registo})
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


def _camera_da_amostra(camera) -> dict | None:
    """Bloco `"camera"` de uma amostra da telemetria → `{azimute, elevacao, distancia, alvo}` ou `None`.

    O `alvo` da TELEMETRIA mantém-se (é o estado REAL: `lookat` = drone+offset, escrito a cada frame pelo
    `seguir_drone` do runner) — só o COMANDO é que não tem `alvo` (contrato v2). Só passa o que a amostra
    trouxer (e no formato do contrato): `null`/ausente/malformado → `None` — sem dados a API publica
    `null`, nunca um valor inventado.
    """
    if not isinstance(camera, dict):
        return None
    alvo = camera.get("alvo")
    if not isinstance(alvo, list) or len(alvo) != 3:
        return None
    return {"azimute": camera.get("azimute"), "elevacao": camera.get("elevacao"),
            "distancia": camera.get("distancia"), "alvo": list(alvo)}


def resumo_telemetria(caminho: Path) -> dict:
    """Resumo do fim da telemetria: estado/ep/passo/retorno + o VENTO EM VIGOR da última amostra.

    `loop` vem do runner quando ele o publica (é o modo EFETIVO); sem telemetria fica `None` e quem
    responde usa o do controlo (`loop_em_vigor`). `camera_atual` é a câmara REAL da última amostra (a 19.ª
    chave `"camera"`); sem telemetria — ou sem viewer no runner — fica `None` (a API publica `null`, e
    não se inventa câmara nenhuma).
    """
    linhas = ultimas_linhas(caminho, MAX_LINHAS)
    if not linhas:
        return {"estado": "desconhecido", "ep": 0, "passo": 0, "retorno": 0.0, "linhas": 0, "t": None,
                "loop": None, "vento_vec": None, "vento_vel": None, "vento_azim": None, "vento_modo": None,
                "camera_atual": None}
    ultima = linhas[-1]
    vec = ultima.get("vento_vec")
    loop = ultima.get("loop")
    camera = ultima.get("camera")
    return {"estado": str(ultima.get("estado", "desconhecido")), "ep": int(ultima.get("ep", 0) or 0),
            "passo": int(ultima.get("passo", 0) or 0), "retorno": float(ultima.get("retorno", 0.0) or 0.0),
            "linhas": len(linhas), "t": ultima.get("t"),
            "loop": None if loop is None else bool(loop),
            "vento_vec": [float(v) for v in vec] if isinstance(vec, list) and len(vec) == 3 else None,
            "vento_vel": float(ultima.get("vento_vel", 0.0) or 0.0),
            "vento_azim": float(ultima.get("vento_azim", 0.0) or 0.0),
            "vento_modo": str(ultima.get("vento_modo", "nenhum") or "nenhum"),
            "camera_atual": _camera_da_amostra(camera)}


def loop_em_vigor(resumo: dict, controlo: dict) -> bool:
    """`loop` em vigor: o que o RUNNER publica na telemetria (efetivo) e, sem ela, o do controlo.

    O controlo é o PEDIDO; a telemetria é o que o runner está mesmo a fazer (pode diferir se o runner foi
    arrancado com `--com-loop`). O `/api/state` e o `/api/sim` publicam este valor. Sem nenhum dos dois, o
    padrão é SEM REINÍCIO (`false`, como no arranque do runner e do site).
    """
    valor = resumo.get("loop")
    return bool(controlo.get("loop", False)) if valor is None else bool(valor)


def vento_do_controlo(controlo: dict) -> dict:
    """Bloco `vento_dinamico` do controlo em vigor (o que o site pediu): `{modo, params, ativo}`."""
    din = controlo.get("dinamico")
    if not isinstance(din, dict):
        return {"modo": "nenhum", "params": {}, "ativo": False}
    return {"modo": str(din.get("modo", "nenhum")), "params": din.get("params") or {},
            "ativo": bool(din.get("ativo", False))}


def vento_em_vigor(resumo: dict, controlo: dict) -> dict:
    """Vento que a FÍSICA leva agora: vector (vx,vy,vz) + polar + modo dinâmico em vigor.

    Vem da ÚLTIMA amostra da telemetria (é o `model.opt.wind` do runner, incluindo rajadas/turbulência); sem
    telemetria cai no vento BASE pedido no controlo, para a API nunca ficar sem resposta.
    """
    vec = resumo.get("vento_vec")
    if vec is None:
        din = vento_do_controlo(controlo)
        base = [float(controlo.get("vel", 0.0) or 0.0), float(controlo.get("azimute", 0.0) or 0.0),
                float(controlo.get("elevacao", 0.0) or 0.0)]
        if din["ativo"] and din["modo"] == "frente" and "vel" in din["params"]:
            # `frente` (a): degrau imediato do vento base — sem telemetria é ele que manda (o topo do
            # controlo só o tem se a escrita veio do site; um ficheiro à mão pode trazer só o bloco).
            base = [float(din["params"]["vel"]), float(din["params"]["azimute"]),
                    float(din["params"]["elevacao"])]
        vel, azim, elev = base
        if not controlo.get("ativo", True) and not (din["ativo"] and din["modo"] == "frente"):
            vel = 0.0
        cos_e, az = math.cos(math.radians(elev)), math.radians(azim)
        vec = [vel * cos_e * math.cos(az), vel * cos_e * math.sin(az), vel * math.sin(math.radians(elev))]
        return {"vec": [round(v, 6) for v in vec], "vel": round(vel, 6), "azimute": round(azim % 360.0, 6),
                "elevacao": round(elev, 6), "modo": din["modo"] if din["ativo"] else "nenhum",
                "fonte": "controlo (sem telemetria)"}
    norma = math.sqrt(sum(v * v for v in vec))
    elev = 0.0 if norma == 0.0 else math.degrees(math.asin(max(-1.0, min(1.0, vec[2] / norma))))
    return {"vec": [round(v, 6) for v in vec], "vel": round(norma, 6),
            "azimute": round(math.degrees(math.atan2(vec[1], vec[0])) % 360.0, 6) if norma else 0.0,
            "elevacao": round(elev, 6), "modo": str(resumo.get("vento_modo") or "nenhum"),
            "fonte": "telemetria (runner)"}


def ler_benchmark(caminho: Path | None = None) -> dict | None:
    """Relatório do `deploy.py` (JSON) — `None` se não existir/for ilegível (a API continua a funcionar)."""
    alvo = Path(caminho) if caminho is not None else BENCHMARK_OMISSAO
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(dados, dict):
        return None
    dados["_caminho"] = str(alvo)          # de ONDE veio (o painel mostra o JSON certo, não o histórico)
    return dados


def mesma_coisa(a, b) -> bool:
    """Os dois caminhos apontam para o MESMO ficheiro? Relativos são resolvidos contra a pasta do experimento
    E contra a raiz do repositório (a primeira base em que o ficheiro existe).

    O relatório do `deploy.py` grava o caminho do modelo RELATIVO à pasta onde correu — `out/.../final.zip` se
    correu no experimento, `experiments/09_drone_hover_rl/out/...` se correu na raiz —, não ao cwd de quem lê
    a API: sem isto, `modelo_coincide` dizia `false` para o mesmo modelo.
    """
    def resolver(caminho) -> Path:
        c = Path(str(caminho))
        if c.is_absolute():
            return c.resolve()
        candidatos = [_AQUI / c, _RAIZ / c]
        return next((x for x in candidatos if x.exists()), candidatos[0]).resolve()
    return resolver(a) == resolver(b)


def _medido(valor, casas: int, divisor: float = 1.0) -> float | None:
    """Número medido > 0 arredondado (÷ `divisor`), ou `None` quando não houve medição (0/ausente/inválido)."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return round(v / divisor, casas) if math.isfinite(v) and v > 0 else None


def bloco_rpi5(bench: dict | None, decisoes_s: float, modelo_em_uso=None) -> dict:
    """Painel RPi 5: specs fixas + inferência medida (benchmark) + uso calculado AO VIVO.

    `uso.fracao_budget = p50_us · decisoes_s / 20000` (a fórmula do contrato: decisões/s reais × latência ÷
    período de 20 ms a 50 Hz) e `pct_budget` é a mesma coisa em %; `pct_cpu_equivalente` reparte-a pelos 4
    núcleos do BCM2712 (a inferência do proxy é single-thread: `nucleos_multi_ia = 1`). Sem benchmark,
    `fonte = "sem benchmark"` e os campos de inferência vêm a `None` — o painel mostra "sem dados".
    `inferencia.modelo_coincide` diz se o modelo MEDIDO é o mesmo que o runner está a carregar (o painel
    estima o custo do que corre, não de outro `.zip`).
    """
    jitter, publicada = RPI5_SPECS["jitter_so"], RPI5_SPECS["inferencia_publicada"]
    uso = {"decisoes_s": round(float(decisoes_s), 3), "latencia_estimada_us": None, "fracao_budget": None,
           "pct_budget": None, "pct_cpu_equivalente": None, "nucleos_multi_ia": 1,
           "pct_periodo": None,          # p50 do NOSSO MLP por decisão, em % do período de 20 ms
           "pct_periodo_publicado_cnn": round(100.0 * publicada["fp32_ms"] * 1000.0 / BUDGET_US, 3),
           "jitter_ms_standard": jitter["standard_ms_pior_caso"],
           "jitter_us_preempt_rt": jitter["preempt_rt_us_max"],
           "gargalo": "jitter do SO a 50 Hz (9,4 ms de pior caso no kernel standard) — a inferência do "
                      "nosso MLP usa <1% do período de 20 ms",
           "nota": "p50 (proxy x86 de 1 core A76) x decisoes/s medidas na telemetria / 20 ms (50 Hz)"}
    if not bench:
        return {"specs": dict(RPI5_SPECS), "inferencia": None, "uso": uso, "fonte": "sem benchmark",
                "benchmark": str(BENCHMARK_OMISSAO)}
    b = bench.get("benchmark") or {}
    p50 = float(b.get("p50_us") or 0.0)
    onnx = bench.get("onnx") or {}
    int8 = bench.get("int8") or {}
    fracao = p50 * float(decisoes_s) / BUDGET_US
    uso.update({"latencia_estimada_us": round(p50, 3), "fracao_budget": round(fracao, 6),
                "pct_budget": round(100.0 * fracao, 3),
                "pct_cpu_equivalente": round(100.0 * fracao / NUCLEOS_SOC, 3),
                "pct_periodo": round(100.0 * p50 / BUDGET_US, 4)})
    inferencia = {
        "p50_us": round(p50, 3), "p99_us": round(float(b.get("p99_us") or 0.0), 3),
        "max_us": round(float(b.get("max_us") or 0.0), 3),
        "modelo_kb": round(float(onnx.get("bytes") or 0) / 1024.0, 2),   # ONNX fp32 (o que corre no RPi)
        # int8 só se foi MEDIDO (`deploy.py --int8`); sem medição é `None` e o painel mostra «—», não «×0,00»
        "int8_fator": _medido(int8.get("fator_p50"), 4),                 # p50 fp32 / p50 int8 (medido)
        "int8_kb": _medido((int8.get("info") or {}).get("bytes"), 2, 1024.0),
        "int8_reducao_tamanho": _medido((int8.get("info") or {}).get("reducao_tamanho"), 4),
        "inferencias_s": round(float(b.get("inferencias_s") or 0.0), 1),
        "threads": b.get("threads"), "n": b.get("n"), "cabe_50hz": b.get("cabe_50hz"),
        "modelo": (bench.get("modelo") or {}).get("caminho"),
        "modelo_coincide": None,        # preenchido por `bloco_rpi5` com o modelo que o runner carregou
        "json": bench.get("_caminho", str(BENCHMARK_OMISSAO)),
        "gerado_em": bench.get("gerado_em"), "cpu_benchmark": bench.get("cpu"),
        "veredicto": bench.get("veredicto"),
    }
    modelo_bench = inferencia["modelo"]
    if modelo_em_uso is not None and modelo_bench:
        inferencia["modelo_coincide"] = mesma_coisa(modelo_bench, modelo_em_uso)
    return {"specs": dict(RPI5_SPECS), "inferencia": inferencia, "uso": uso,
            "fonte": "proxy x86 calibrado (1 núcleo do A76; não é o RPi)", "benchmark": inferencia["json"]}


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
    """Estado partilhado entre os pedidos: caminhos, processo do runner, modelo, porta e os COMANDOS.

    `memorizados` é o que o SERVIDOR sabe do `loop` e do contador `reiniciar` desde o arranque (semeado no
    `main` com o que ele próprio escreveu). É a autoridade em RUNTIME: se o ficheiro de controlo for apagado
    ou corrompido, a escrita que o recria leva estes valores em vez dos de `CONTROLO_INICIAL` — ver
    `_comandos_memorizados`.
    """

    def __init__(self, controlo: Path, telemetria: Path, host: str, porta: int, verboso: bool = False,
                 filho: subprocess.Popen | None = None, modelo: Path | None = None,
                 motivo: str = "", memorizados: dict | None = None):
        self.controlo = Path(controlo)
        self.telemetria = Path(telemetria)
        self.host = host
        self.porta = porta
        self.verboso = verboso
        self.filho = filho
        self.modelo = Path(modelo) if modelo is not None else None    # o .zip que o runner carregou
        self.modelo_motivo = motivo or ""                             # porquê este modelo (auditoria)
        self.memorizados = dict(memorizados or {})                    # `loop`/`reiniciar` efetivos (runtime)
        self.hardware = hardware_do_modelo(self.modelo)               # planta real: peças do modelo em uso
        self._ritmo = {"t": None, "passo": None, "valor": 0.0}       # decisoes/s medidos entre pedidos
        self._bench = {"t": 0.0, "dados": None}                      # cache do relatório do deploy.py

    def medir_ritmo(self, passo: int) -> float:
        """Decisões/s REAIS medidas na telemetria: Δpasso / Δtempo-de-parede entre pedidos (EMA 0,3).

        O painel faz polling ao `/api/state`, logo cada pedido dá uma amostra; com o episódio parado o Δpasso
        é 0 e a taxa cai para 0 (é a verdade: não há decisões). Sem duas amostras ainda → 0.
        """
        agora, amostra = time.time(), self._ritmo
        valor = amostra["valor"]
        if amostra["t"] is not None and agora - amostra["t"] >= 0.2:
            delta_t = agora - amostra["t"]
            taxa = (int(passo) - int(amostra["passo"])) / delta_t if delta_t > 0 else 0.0
            valor = taxa if amostra["valor"] == 0.0 else 0.7 * amostra["valor"] + 0.3 * max(0.0, taxa)
        amostra.update({"t": agora, "passo": int(passo), "valor": valor})
        return valor

    def benchmark(self, max_idade: float = 5.0) -> dict | None:
        """Relatório do `deploy.py` (cache de `max_idade` s: o painel não relê o JSON a cada pedido).

        Prefere o `deploy_report.json` que o `deploy.py` grava AO LADO do modelo em uso (a política da planta
        real tem o seu, com a entrada (1, 21)); sem ele, o relatório histórico `BENCHMARK_OMISSAO`."""
        agora = time.time()
        if self._bench["dados"] is None or agora - self._bench["t"] >= max_idade:
            proprio = None if self.modelo is None else Path(self.modelo).parent / "deploy_report.json"
            dados = ler_benchmark(proprio) if proprio is not None and proprio.is_file() else None
            self._bench = {"t": agora, "dados": dados if dados is not None else ler_benchmark()}
        return self._bench["dados"]

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
        controlo = ler_controlo(self.servidor.controlo, self.servidor.memorizados)
        self._json(200, {
            "estado": resumo["estado"],
            "ep": resumo["ep"],
            "passo": resumo["passo"],
            "retorno": resumo["retorno"],
            "loop": loop_em_vigor(resumo, controlo),    # efetivo: o runner publica-o na telemetria
            "reiniciar": int(controlo.get("reiniciar", 0) or 0),
            "vento": {campo: controlo.get(campo) for campo in ("vel", "azimute", "elevacao", "ativo")},
            "vento_dinamico": vento_do_controlo(controlo),
            "vento_atual": vento_em_vigor(resumo, controlo),
            "camera_padrao": camera_padrao_para(self.servidor.hardware),   # REPOR VISTA = mandar estes
            "camera_atual": resumo["camera_atual"],    # câmara REAL da telemetria (ou null sem dados)
            "modelo": None if self.servidor.modelo is None else str(self.servidor.modelo),
            "modelo_nome": self.servidor.modelo_nome,
            "planta": "real" if self.servidor.hardware else "cf2",
            "linhas": ultimas_linhas(self.servidor.telemetria),
        })

    def _api_state(self) -> None:
        """`GET /api/state`: resumo curto (sem as amostras) para o cabeçalho do site, com o MODELO em uso."""
        resumo = resumo_telemetria(self.servidor.telemetria)
        controlo = ler_controlo(self.servidor.controlo, self.servidor.memorizados)
        filho = self.servidor.filho
        idade = None if resumo["t"] is None else round(time.time() - _mtime(self.servidor.telemetria), 3)
        self._json(200, {
            "estado": resumo["estado"],
            "ep": resumo["ep"],
            "passo": resumo["passo"],
            "retorno": resumo["retorno"],
            "vento": {campo: controlo.get(campo) for campo in ("vel", "azimute", "elevacao", "ativo")},
            "vento_dinamico": vento_do_controlo(controlo),
            "vento_atual": vento_em_vigor(resumo, controlo),
            "camera_padrao": camera_padrao_para(self.servidor.hardware),   # REPOR VISTA = mandar estes
            "camera_atual": resumo["camera_atual"],    # câmara REAL da telemetria (ou null sem dados)
            "planta": "real" if self.servidor.hardware else "cf2",
            "hardware": resumo_hardware(self.servidor.hardware),
            "rpi5": bloco_rpi5(self.servidor.benchmark(),
                               self.servidor.medir_ritmo(resumo["passo"]), self.servidor.modelo),
            "modelo": None if self.servidor.modelo is None else str(self.servidor.modelo),
            "modelo_nome": self.servidor.modelo_nome,
            "modelo_motivo": self.servidor.modelo_motivo,
            "loop": loop_em_vigor(resumo, controlo),    # efetivo: telemetria do runner (default SEM REINICIO)
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
            elif rota == "/api/parar":
                self._post_parar()
            elif rota == "/api/reiniciar":
                self._post_reiniciar()
            elif rota == "/api/vento-dinamico":
                self._post_vento_dinamico(dados)
            elif rota == "/api/loop":
                self._post_loop(dados)
            elif rota == "/api/camera":
                self._post_camera(dados)
            elif rota == "/api/bateria":
                self._post_bateria(dados)
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
        """Valida as faixas, escreve o controlo (atómico) e devolve o vento que ficou em vigor.

        A leitura que serve de base à validação e a escrita correm sob a MESMA trava: dois POSTs simultâneos
        não podem perder um o resultado do outro (ver `trava_controlo`).
        """
        with trava_controlo():
            atual = ler_controlo(self.servidor.controlo, self.servidor.memorizados)
            try:
                novo = validar_vento(dados, atual)
            except ValueError as erro:
                self._erro(400, str(erro))
                return
            registo = escrever_controlo(self.servidor.controlo, novo, self.servidor.memorizados)
        print(f"[site] vento: {registo['vel']:.2f} m/s @ {registo['azimute']:.1f} deg"
              f" (elev {registo['elevacao']:+.1f}, {'ativo' if registo['ativo'] else 'desligado'})", flush=True)
        self._json(200, {"ok": True, "vento": {campo: registo[campo] for campo in
                                               ("vel", "azimute", "elevacao", "ativo")}})

    def _post_vento_dinamico(self, dados) -> None:
        """Liga/reconfigura/desliga o vento DINÂMICO ao vivo (sem reiniciar o episódio): 200/400.

        A validação é a do `env.py` para os modos que ele conhece (mesmas regras do treino), a do contrato
        para o `rajada_agora` e a do `/api/vento` para o `frente` do formato (a) (`{vel,azimute,elevacao}` =
        degrau imediato do vento base, que passa também a ser o vento base do controlo); as faixas más saem
        em 400 com a mensagem do validador. Leitura+escrita sob a mesma trava (ver `trava_controlo`).
        """
        with trava_controlo():
            atual = ler_controlo(self.servidor.controlo, self.servidor.memorizados)
            try:
                novo = validar_vento_dinamico(dados, atual)
            except ValueError as erro:
                self._erro(400, str(erro))
                return
            except ImportError as erro:                  # env.py indisponível: não é culpa do pedido
                self._erro(500, f"não consegui validar os modos dinâmicos (env.py): {erro}")
                return
            registo = escrever_controlo(self.servidor.controlo, novo, self.servidor.memorizados)
        din = registo["dinamico"]
        print(f"[site] vento dinamico: {din['modo']} {din['params']} ativo={din['ativo']} "
              f"(seq {din['seq']})", flush=True)
        if din["modo"] == "frente" and "vel" in din["params"]:
            print(f"[site] frente = degrau imediato do vento base: {registo['vel']:.2f} m/s @ "
                  f"{registo['azimute']:.1f} deg (elev {registo['elevacao']:+.1f}, "
                  f"{'ativo' if registo['ativo'] else 'desligado'})", flush=True)
        self._json(200, {"ok": True, "vento_dinamico": din, "vento_base": {"vel": registo["vel"],
                      "azimute": registo["azimute"], "elevacao": registo["elevacao"],
                      "ativo": registo["ativo"]}})

    def _post_parar(self) -> None:
        """PARAR VENTO: vento base a 0 + dinâmica desligada, numa ÚNICA escrita atómica do controlo.

        Um só pedido, uma só escrita: não há instante em que o vento esteja parado com a dinâmica ainda
        ligada (ou vice-versa) e não há corrida entre dois POSTs. Depois dele não resta nenhuma rajada
        ativa nem pendente e o `opt.wind` do runner fica exatamente no vento base comandado (0 m/s).
        Leitura+escrita sob a mesma trava (ver `trava_controlo`) — é o que impede um POST concorrente de
        reverter o PARAR (ou o PARAR de reverter o POST).
        """
        with trava_controlo():
            atual = ler_controlo(self.servidor.controlo, self.servidor.memorizados)
            registo = escrever_controlo(self.servidor.controlo, validar_parar(atual),
                                        self.servidor.memorizados)
        din = registo["dinamico"]
        print(f"[site] PARAR: vento 0 m/s (azimute {registo['azimute']:.1f} deg, elev "
              f"{registo['elevacao']:+.1f}) + vento dinamico {din['modo']} (seq {din['seq']})", flush=True)
        self._json(200, {"ok": True, "vento": {campo: registo[campo] for campo in
                                               ("vel", "azimute", "elevacao", "ativo")},
                         "vento_dinamico": din})

    def _post_reiniciar(self) -> None:
        """Incrementa o contador `reiniciar`: é o ÚNICO caminho para recomeçar um episódio (e vale em
        qualquer estado — a correr, com o episódio terminado sem reinício, ou a meio).

        O incremento é lido e escrito sob a mesma trava: sem isso, um POST de vento concorrente que tivesse
        lido o controlo antes podia escrever depois e reverter o contador (perdia-se o REINICIAR).
        """
        with trava_controlo():
            atual = ler_controlo(self.servidor.controlo, self.servidor.memorizados)
            contador = int(atual.get("reiniciar", 0) or 0) + 1
            escrever_controlo(self.servidor.controlo, {**atual, "reiniciar": contador},
                              self.servidor.memorizados)
        print(f"[site] REINICIAR pedido (contador {contador})", flush=True)
        self._json(200, {"contador": contador})

    def _post_loop(self, dados) -> None:
        """Liga/desliga o auto-reset no fim do episódio (`{"ativo": bool}`).

        `true` = CONTÍNUO (o runner reinicia sozinho, ep+1); `false` = SEM REINÍCIO (o runner deixa o
        episódio fechar e CONTINUA a física no estado em que ficou — não congela; só um REINICIAR recomeça).
        """
        if not isinstance(dados, dict):
            self._erro(400, "o corpo tem de ser um objeto JSON")
            return
        ativo = dados.get("ativo", dados.get("loop"))
        if not isinstance(ativo, bool):
            self._erro(400, f"`ativo` tem de ser booleano (recebido {ativo!r})")
            return
        with trava_controlo():                          # leitura+escrita indivisíveis (ver `trava_controlo`)
            atual = ler_controlo(self.servidor.controlo, self.servidor.memorizados)
            # Limpa o CARIMBO DO ARRANQUE: o `loop` deixa de ser o valor que o site escreveu no arranque e
            # passa a ser uma escolha do dono — é esta marca que faz o `fixar_loop` do runner (que pode ainda
            # estar a importar o SB3/torch) respeitar o POST em vez de o reverter (ver `CAMPO_ARRANQUE`).
            escrever_controlo(self.servidor.controlo, {**atual, "loop": ativo, CAMPO_ARRANQUE: None},
                              self.servidor.memorizados)
        print(f"[site] loop {'ligado (continuo)' if ativo else 'desligado (sem reinicio)'}", flush=True)
        self._json(200, {"ok": True, "loop": ativo})

    def _post_bateria(self, dados) -> None:
        """Comando de BATERIA da planta real (`recarregar` | `nova`): 200 `{ok, bateria}` / 400."""
        with trava_controlo():
            atual = ler_controlo(self.servidor.controlo, self.servidor.memorizados)
            try:
                novo = validar_bateria(dados, atual)
            except ValueError as erro:
                self._erro(400, str(erro))
                return
            registo = escrever_controlo(self.servidor.controlo, novo, self.servidor.memorizados)
        print(f"[site] bateria: {registo['bateria']['acao']} (seq {registo['bateria']['seq']})", flush=True)
        self._json(200, {"ok": True, "bateria": registo["bateria"]})

    def _post_camera(self, dados) -> None:
        """Move a CÂMARA da janela 3D (só apresentação: não toca na física nem em comandos): 200/400.

        O corpo é o objeto `camera` sem `seq` (qualquer subconjunto dos campos); o `seq` é incrementado
        AQUI, a cada pedido, e o bloco segue para o ficheiro de controlo por `escrever_controlo` (merge:
        nunca toca em `loop`/`reiniciar`/vento/dinâmico). Leitura+escrita sob a mesma trava (ver
        `trava_controlo`) — um POST de vento concorrente não reverte o de câmara nem o contrário.
        """
        with trava_controlo():
            atual = ler_controlo(self.servidor.controlo, self.servidor.memorizados)
            try:
                novo = validar_camera(dados, atual, camera_padrao_para(self.servidor.hardware))
            except ValueError as erro:
                self._erro(400, str(erro))
                return
            registo = escrever_controlo(self.servidor.controlo, novo, self.servidor.memorizados)
        cam = registo["camera"]
        print(f"[site] camera (3a pessoa): az {cam['azimute']:.1f} deg, elev {cam['elevacao']:+.1f} deg, "
              f"distancia {cam['distancia']:.2f} m (seq {cam['seq']}) — alvo segue o drone", flush=True)
        self._json(200, {"ok": True, "camera": cam})


def validar_bateria(dados, atual: dict) -> dict:
    """`POST /api/bateria` → bloco `{"bateria": {"acao", "seq"}}` (o `seq` é do SERVIDOR, +1 por pedido).

    `acao` = `recarregar` (fecha o ciclo do pack: aplica o desgaste e volta a 100 %) ou `nova` (pack NOVO:
    SoH 100 %, 0 ciclos). Só a planta REAL tem bateria — no cf2 o runner ignora o comando com aviso.
    """
    if not isinstance(dados, dict):
        raise ValueError("o corpo tem de ser um objeto JSON")  # noqa: TRY004  (contrato: 400 por ValueError)
    acao = dados.get("acao")
    if acao not in ACOES_BATERIA:
        raise ValueError(f"`acao` tem de ser uma de {list(ACOES_BATERIA)} (recebido {acao!r})")
    anterior = atual.get("bateria") if isinstance(atual.get("bateria"), dict) else {}
    seq = int(anterior.get("seq", 0) or 0) + 1
    return {"bateria": {"acao": acao, "seq": seq}}


def hardware_do_modelo(modelo: Path | None) -> dict | None:
    """`hardware.json` ao lado do modelo (planta real: peças, derivados e DR com que foi treinado) — ou `None`."""
    if modelo is None:
        return None
    caminho = Path(modelo).parent / "hardware.json"
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def camera_padrao_para(hardware: dict | None) -> dict:
    """Câmara de arranque do modelo em uso: a do cf2 (`CAM_PADRAO`) ou, na planta real, a do modelo GERADO
    das peças (`mjv_defaultFreeCamera`, o mesmo que o runner aplica — import tardio, só nesse caso)."""
    if not hardware:
        return dict(CAM_PADRAO)
    chave = hardware.get("build")
    if chave not in _CAM_REAL:
        try:
            for caminho in (str(_RAIZ), str(_AQUI)):
                if caminho not in sys.path:
                    sys.path.insert(0, caminho)
            import mujoco
            from env_real import build_do_hardware

            from lab import drone_rpi as dr
            model, _ = dr.carregar(dr.hardware(build_do_hardware(hardware)[0]))
            cam = mujoco.MjvCamera()
            mujoco.mjv_defaultFreeCamera(model, cam)
            _CAM_REAL[chave] = {"azimute": float(cam.azimuth) % 360.0, "elevacao": float(cam.elevation),
                                "distancia": float(cam.distance)}
        except Exception:  # noqa: BLE001 — sem o lab (ou build apagado) fica o default do cf2
            _CAM_REAL[chave] = dict(CAM_PADRAO)
    return dict(_CAM_REAL[chave])


_CAM_REAL: dict = {}
ACOES_BATERIA = ("recarregar", "nova")
_VALIDADOR_ENV = None


def _validador_env():
    """`env.valida_vento_dinamico` importado à primeira utilização (o site é stdlib até aqui).

    Importar o `env.py` puxa o MuJoCo para o processo do SITE: é o preço de validar os modos dinâmicos com
    as MESMAS regras do treino/runner, em vez de duplicar faixas aqui (uma divergência daria 200 na API e um
    aviso no runner). Só acontece quando alguém usa o vento dinâmico; sem ele o site nunca importa MuJoCo.
    """
    global _VALIDADOR_ENV
    if _VALIDADOR_ENV is None:
        from env import valida_vento_dinamico  # import tardio (pesado): ver o docstring
        _VALIDADOR_ENV = valida_vento_dinamico
    return _VALIDADOR_ENV


def _params_rajada_agora(params: dict) -> dict:
    """Params da rajada one-shot: `u` [0, 5] m/s, `azimute` [0, 360)°, `elevacao` ±90°, `duracao` ≥ 1.

    Gémea da do `sim_view.py` (o runner valida outra vez ao aplicar; aqui serve para o 400 da API).
    """
    desconhecidas = set(params) - {"u", "azimute", "elevacao", "duracao"}
    if desconhecidas:
        raise ValueError(f"`params` (rajada_agora) tem chaves desconhecidas {sorted(desconhecidas)} — aceita "
                         "['azimute', 'duracao', 'elevacao', 'u']")
    u = params.get("u", RAJADA_U_PADRAO)
    if isinstance(u, bool) or not isinstance(u, (int, float)) or not math.isfinite(float(u)):
        raise ValueError(f"`params.u` tem de ser um número finito (recebido {u!r})")
    if not 0.0 <= float(u) <= RAJADA_U_MAX:
        raise ValueError(f"`params.u` tem de estar em [0, {RAJADA_U_MAX}] m/s (recebido {u!r})")
    saida = {"u": float(u)}
    for campo, minimo, maximo in (("azimute", 0.0, AZIM_MAX), ("elevacao", -ELEV_MAX, ELEV_MAX)):
        valor = params.get(campo, 0.0)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(float(valor)):
            raise ValueError(f"`params.{campo}` tem de ser um número finito (recebido {valor!r})")
        if not minimo <= float(valor) <= maximo:
            raise ValueError(f"`params.{campo}` tem de estar em [{minimo}, {maximo}] (recebido {valor!r})")
        saida[campo] = float(valor) % AZIM_MAX if campo == "azimute" else float(valor)
    duracao = params.get("duracao", RAJADA_DURACAO_PADRAO)
    if isinstance(duracao, bool) or not isinstance(duracao, int) or int(duracao) < 1:
        raise ValueError(f"`params.duracao` tem de ser um inteiro ≥ 1 passos de decisão (recebido {duracao!r})")
    saida["duracao"] = int(duracao)
    return saida


def _params_frente(params: dict, atual: dict) -> tuple[dict, dict | None]:
    """Params do modo `frente` → `(params, vento_base_novo|None)`: aceita os DOIS formatos do contrato.

    · formato (a) `{"vel", "azimute", "elevacao"}` → degrau IMEDIATO do vento base: validado com as MESMAS
      faixas do `POST /api/vento` (`vel` [0, 5] m/s, `azimute` [0, 360]°, `elevacao` ±90°) e devolvido
      também como vento BASE do controlo (`vel`/`azimute`/`elevacao`/`ativo`) — assim o estado do site, o
      ficheiro e a física dizem o mesmo, e o degrau é o vento base que fica depois de um `nenhum`. Campo
      ausente mantém o valor em vigor (como no `/api/vento`), para `{"azimute": 270}` ser só uma viragem;
      NÃO passa pelo validador do env (que espera `u_max`/`t_s` e recusaria estas chaves);
    · formato (b) `{"u_max", "t_s"}` (ou sem params) → modo em curso do env: quem valida é o `env.py`.
    Chaves desconhecidas ou mistura dos dois formatos → `ValueError` (o POST responde 400). O `"modo"` lá
    dentro é tolerado quando diz "frente": é o que o `env.valida_vento_dinamico` devolve e o site guarda, e
    o site/frontend pode reenviar os params lidos do `/api/sim` tal e qual (ida-e-volta).
    """
    limpos = dict(params)
    if limpos.get("modo") == "frente":
        limpos.pop("modo")
    desconhecidas = set(limpos) - set(FRENTE_BASE) - set(FRENTE_ENV)
    if desconhecidas:
        raise ValueError(f"`params` (frente) tem chaves desconhecidas {sorted(desconhecidas)} — aceita "
                         f"{list(FRENTE_BASE)} (degrau imediato do vento base) ou {list(FRENTE_ENV)} "
                         "(modo em curso do env)")
    da_base = [campo for campo in FRENTE_BASE if campo in limpos]
    do_env = [campo for campo in FRENTE_ENV if campo in limpos]
    if da_base and do_env:
        raise ValueError(f"`params` (frente) não pode misturar os dois formatos: {da_base} são um degrau "
                         f"imediato do vento base e {do_env} o modo em curso do env")
    if not da_base:
        return dict(params), None                        # (b): sem params = defaults do env
    novos = {}
    for campo, minimo, maximo in (("vel", 0.0, VEL_MAX), ("azimute", 0.0, AZIM_MAX),
                                  ("elevacao", -ELEV_MAX, ELEV_MAX)):
        valor = _numero_finito(params, campo)
        if valor is None:
            valor = float(atual.get(campo, 0.0) or 0.0)  # ausente = mantém o vento base em vigor
        if not minimo <= valor <= maximo:
            raise ValueError(f"`params.{campo}` tem de estar em [{minimo}, {maximo}] (recebido {valor!r})")
        novos[campo] = valor
    return novos, {**novos, "ativo": novos["vel"] > 0.0}


def validar_parar(atual: dict) -> dict:
    """`POST /api/parar` → controlo novo: vento base a 0 E vento dinâmico desligado, numa só escrita.

    É o botão **PARAR VENTO**: uma única escrita ATÓMICA (indivisível) resolve as duas metades — o vento
    base passa a 0 (mantendo azimute/elevação guardados) e o bloco `dinamico` passa a `nenhum` com `seq`
    novo (a assinatura muda, logo o runner reage e o `_para_dinamica` corta rajada/modo/restauros). Sem
    isto, um `POST /api/vento {vel: 0}` deixava as rajadas do modo contínuo (e a rajada one-shot em curso)
    a atuar depois do PARAR — o runner continuava a escrever o envelope no `opt.wind`.
    """
    anterior = atual.get("dinamico")
    seq = int(anterior.get("seq", 0) or 0) + 1 if isinstance(anterior, dict) else 1
    return {**atual, "vel": 0.0, "ativo": False,
            "dinamico": {"modo": "nenhum", "params": {}, "ativo": False, "seq": seq}}


def validar_vento_dinamico(dados, atual: dict) -> dict:
    """`POST /api/vento-dinamico` → controlo novo, com o bloco `dinamico` validado (ValueError → 400).

    Os modos do env (`rajadas`/`aleatoria`/`dryden`, e o `frente` do formato (b)) passam pelo
    `valida_vento_dinamico` do PRÓPRIO `env.py` (params normalizados com os defaults do treino; em
    `aleatoria` o dict normalizado traz só `p`/`duracao` — os restantes são aceites e validados, mas
    ignorados); o `frente` do formato (a)
    (`vel`/`azimute`/`elevacao`) é um degrau imediato do vento base e é validado aqui (as faixas do
    `/api/vento`), escrevendo também o vento BASE do controlo; o `rajada_agora` (one-shot dirigido, que o
    env não tem) é validado aqui; `nenhum` não leva params. O `seq` é incrementado a CADA pedido: é o que
    permite disparar duas rajadas iguais seguidas (o runner só (re)age quando a assinatura do bloco muda).
    """
    if not isinstance(dados, dict):
        raise ValueError("o corpo tem de ser um objeto JSON")  # noqa: TRY004
    modo = dados.get("modo")
    if modo is None:
        raise ValueError(f"indique `modo`, um de {list(MODOS_DINAMICOS)}")
    if modo not in MODOS_DINAMICOS:
        raise ValueError(f"`modo` tem de ser um de {list(MODOS_DINAMICOS)} (recebido {modo!r})")
    params = dados.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("`params` tem de ser um objeto JSON")  # noqa: TRY004
    ativo = dados.get("ativo", modo != "nenhum")
    if not isinstance(ativo, bool):
        raise ValueError(f"`ativo` tem de ser booleano (recebido {ativo!r})")  # noqa: TRY004
    base_novo = None
    if modo == "frente":                                 # 2 formatos: degrau imediato OU modo do env
        params, base_novo = _params_frente(params, atual)
        if base_novo is None:                            # formato (b): quem valida é o `env.py`
            params = _validador_env()({"modo": modo, **params}) or {}
    elif modo in MODOS_DINAMICOS_ENV:
        params = _validador_env()({"modo": modo, **params}) or {}
    elif modo == "rajada_agora":
        params = _params_rajada_agora(params)
    else:
        params = {}
    anterior = atual.get("dinamico")
    seq = int(anterior.get("seq", 0) or 0) + 1 if isinstance(anterior, dict) else 1
    novo = {**atual, "dinamico": {"modo": modo, "params": params, "ativo": bool(ativo), "seq": seq}}
    if base_novo is not None:
        novo.update(base_novo)                           # o degrau do `frente` passa a ser o vento base
    return novo


def validar_camera(dados, atual: dict, padrao: dict | None = None) -> dict:
    """`POST /api/camera` → controlo novo, com o bloco `camera` validado (ValueError → 400).

    CONTRATO v2 (câmara TERCEIRA-PESSOA): o corpo é o objeto `camera` do ORBITAR/zoom e NÃO tem `alvo` —
    o alvo da câmara é SEMPRE o drone (o runner escreve o `lookat` a cada frame, ver `sim_view.seguir_drone`).
    Campos aceites: `azimute`, `elevacao`, `distancia` (e o alias `distandia` → `distancia`, a grafia que
    já apareceu no front; os dois juntos → 400, é ambíguo) e `seq`, que é do SERVIDOR: incrementado a CADA
    pedido (como o `dinamico.seq`; é o que faz o runner re-aplicar valores iguais) e, quando vem no corpo,
    IGNORADO (o site pode reenviar um bloco lido tal e qual). Qualquer subconjunto é aceito: o que **não
    vem** mantém o valor do bloco em vigor (ou, sem bloco, o `padrao` = a câmara de arranque DO MODELO EM USO
    — `camera_padrao_para`; sem ele, o `CAM_PADRAO` do cf2: medido em 2026-10-10, completar o 1.º comando
    do drone real com a distância do Crazyflie, 0,27 m, punha a câmara dentro do drone). Recusas com 400 e
    mensagem clara: campo **PRESENTE com valor `null`** (`null` não é «ausente» — só a AUSÊNCIA completa
    do bloco em vigor), **chave desconhecida** (incluindo o `alvo` do contrato v1: campo desconhecido é
    erro, nunca silêncio) e valores fora das faixas — `azimute` finito (normalizado mod 360), `elevacao`
    [-90, 90]°, `distancia` ]0, 20] m. A escrita é depois MERGE (`escrever_controlo`): uma escrita de
    câmara nunca toca no vento, no `loop`, no `reiniciar` nem no bloco `dinamico`.
    """
    if not isinstance(dados, dict):
        raise ValueError("o corpo tem de ser um objeto JSON")  # noqa: TRY004
    desconhecidas = set(dados) - {"azimute", "elevacao", "distancia", "distandia", "seq"}
    if desconhecidas:
        raise ValueError(f"`camera` tem chaves desconhecidas {sorted(desconhecidas)} — aceita "
                         "['azimute', 'distancia', 'elevacao'] (e o alias 'distandia' → 'distancia'; sem "
                         "`seq`: o servidor incrementa-o)")
    if "distandia" in dados and "distancia" in dados:
        raise ValueError("`camera` trouxe `distancia` E o alias `distandia` — escolha um (são o mesmo "
                         "campo)")
    campos = dict(dados)
    if "distandia" in campos:
        campos["distancia"] = campos.pop("distandia")   # alias do front → nome do contrato
    for campo in ("azimute", "elevacao", "distancia"):
        if campo in campos and campos[campo] is None:
            raise ValueError(f"`{campo}` presente com valor nulo — um campo presente tem de ter um valor "
                             "válido; para manter o valor do bloco em vigor, OMITA o campo")
    novos = {}
    for campo, minimo, maximo, normalizar in (("azimute", None, None, True),
                                              ("elevacao", -ELEV_MAX, ELEV_MAX, False),
                                              ("distancia", None, CAM_DIST_MAX, False)):
        valor = _numero_finito(campos, campo)
        if valor is None:
            continue                                     # ausente: mantém o valor em vigor
        if campo == "distancia" and not 0.0 < valor <= CAM_DIST_MAX:
            raise ValueError(f"`distancia` tem de estar em ]0, {CAM_DIST_MAX}] m (recebido {valor!r})")
        if minimo is not None and not minimo <= valor <= maximo:
            raise ValueError(f"`{campo}` tem de estar em [{minimo}, {maximo}] (recebido {valor!r})")
        novos[campo] = valor % AZIM_MAX if normalizar else valor
    anterior = atual.get("camera") if isinstance(atual.get("camera"), dict) else {}
    try:
        base = {**(padrao if padrao is not None else CAM_PADRAO),
                **{campo: anterior[campo] for campo in ("azimute", "elevacao", "distancia")
                   if campo in anterior}}
        bloco = {"azimute": float(base["azimute"]), "elevacao": float(base["elevacao"]),
                 "distancia": float(base["distancia"]), **novos}
    except (TypeError, ValueError) as erro:
        raise ValueError(f"bloco `camera` em vigor ilegível ({erro}) — indique os valores todos no "
                         "pedido") from erro
    if not all(math.isfinite(v) for v in (bloco["azimute"], bloco["elevacao"], bloco["distancia"])):
        raise ValueError(f"bloco `camera` em vigor tem valores não finitos ({bloco}) — indique os valores "
                         "todos no pedido")
    seq = int(anterior.get("seq", 0) or 0) + 1
    return {**atual, "camera": {**bloco, "seq": seq}}


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


# FILA DE LIGAÇÕES do servidor HTTP. O default do `socketserver` (`request_queue_size = 5`) deixa um
# burst FRIO de ligações simultâneas sem servir: com 40 ligações de uma vez, as que não cabiam na fila
# do `listen(5)` perdiam-se (medido com o código de antes: 26–39 de 40 servidos por ronda, ligações com
# `ConnectionResetError` ou sem resposta nenhuma do lado do cliente, e as que passavam demoravam segundos
# — os SYNs retransmitidos) — um POST perdido é um comando do dono que NUNCA chega ao simulador. 64 dá
# folga ao burst de 40 provado nos testes (`teste_camera.py`, §3: 40 ligações × 3 rondas, 40/40 sempre).
FILA_LIGACOES = 64


class ServidorHTTP(ThreadingHTTPServer):
    """`ThreadingHTTPServer` com a fila de ligações do laboratório (`request_queue_size`, não o 5 do stdlib)."""

    request_queue_size = FILA_LIGACOES


def abrir_servidor(host: str, porta: int, servidor: Servidor) -> ThreadingHTTPServer:
    """`ServidorHTTP` na porta pedida (0 = livre), tentando as 10 seguintes se estiver ocupada."""
    tentativas = [porta] if porta == 0 else [porta + i for i in range(11)]
    for tentativa in tentativas:
        try:
            httpd = ServidorHTTP((host, tentativa), criar_handler(servidor))
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


def modelo_real_por_omissao(out: Path) -> tuple[Path, str] | None:
    """Política da PLANTA REAL (o drone do dono) — tem precedência (a MESMA regra do `sim_view.py`):
    `out/real_*/{final,best_model}.zip` com o `hardware.json` ao lado, o mais recente."""
    candidatos = [p for p in list(out.glob("real_*/final.zip")) + list(out.glob("real_*/best_model.zip"))
                  if (p.parent / "hardware.json").is_file()]
    melhor = _mais_recente(p for p in candidatos if p.name == "final.zip") or _mais_recente(candidatos)
    if melhor is None:
        return None
    return melhor, f"planta REAL ({melhor.parent.name}/{melhor.name} + hardware.json)"


def resumo_hardware(hardware: dict | None) -> dict | None:
    """O essencial do `hardware.json` para o site (bloco Hardware): build, peças, massa, T/W, pairagem, autonomia."""
    if not hardware:
        return None
    d = hardware.get("derivados", {})
    p = hardware.get("pecas", {})
    ph = d.get("pairagem_v_nominal", {})

    def nome(peca):
        return f"{peca.get('fabricante', '')} {peca.get('modelo', '')}".strip() if isinstance(peca, dict) else None

    return {"build": hardware.get("build"), "modo_acao": hardware.get("modo_acao"),
            "motor": nome(p.get("motor")), "helice": nome(p.get("helice")), "celula": nome(p.get("celula")),
            "frame": nome(p.get("frame")), "esc": nome(p.get("esc")),
            "bateria": d.get("bateria"), "massa_total_g": d.get("massa_total_g"), "t_w": d.get("t_w_cheia"),
            "omega_max_rpm": d.get("omega_max_cheia_rpm"), "p_pairagem_w": ph.get("p_total"),
            "g_por_w": ph.get("g_por_w"), "autonomia_min": d.get("autonomia_min"),
            "kf": d.get("kf"), "kq": d.get("kq"), "origem_kf_kq": d.get("origem_kf_kq"),
            "dr": hardware.get("domain_randomization") is not None,
            # a semântica da AÇÃO com que a política voa (o site mostra os setpoints com ESTES valores)
            "taxa_max": _taxa_max_ctbr(), "coletivo_max_peso": 2.0}


def _taxa_max_ctbr() -> list[float] | None:
    """Setpoints de taxa máximos do modo ctbr (`env_real.TAXA_MAX`, rad/s) — a mesma fonte do ambiente."""
    try:
        from env_real import TAXA_MAX
    except Exception:  # noqa: BLE001 — o resumo é acessório: sem o env (cf2/teste) fica `None` e o site usa o seu
        return None
    return [round(float(v), 6) for v in TAXA_MAX]


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
    real = modelo_real_por_omissao(out)
    if real is not None:
        return real
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
    carregar exactamente o mesmo ficheiro que o site diz estar a correr. O modo de continuidade vai também
    SEMPRE explícito — `--com-loop` com `--com-loop` no site e `--sem-loop` em todos os outros casos (o
    padrão é SEM REINÍCIO) —, para o runner e o ficheiro de controlo dizerem ambos o que o dono pediu.
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
    if args.com_loop:
        comando.append("--com-loop")                    # CONTÍNUO: liga o auto-reset no arranque
    else:
        comando.append("--sem-loop")                    # SEM REINÍCIO: explícito (é o padrão do runner)
    return comando


def lancar_runner(args, modelo: Path | None = None, arranque: str | None = None) -> subprocess.Popen:
    """Arranca o `sim_view.py` no seu PRÓPRIO grupo de processos (para o SIGTERM apanhar tudo).

    `arranque` é o token do carimbo do arranque (`CAMPO_ARRANQUE`) que o site acabou de escrever no ficheiro
    de controlo: vai no AMBIENTE do filho (`ENV_LOOP_ARRANQUE`) e é o handshake que impede o `fixar_loop` de
    reverter um `POST /api/loop` feito durante o arranque (ver o cabeçalho do `sim_view.fixar_loop`).
    """
    comando = comando_do_runner(args, modelo)
    ambiente = None if arranque is None else {**os.environ, ENV_LOOP_ARRANQUE: str(arranque)}
    print(f"[site] runner: {' '.join(comando)}", flush=True)
    return subprocess.Popen(comando, cwd=str(_AQUI), start_new_session=True, env=ambiente)  # herda stdout/stderr


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
        epilog=("API (9 rotas): GET /api/sim · GET /api/state · POST /api/vento {vel,azimute,elevacao} · "
                "POST /api/bateria {acao: recarregar|nova} (planta real) · "
                "POST /api/vento-dinamico {modo,params?,ativo?} — `frente` aceita {vel,azimute,elevacao} "
                "(degrau IMEDIATO do vento base) OU {u_max,t_s} (degrau em curso do env); "
                "POST /api/parar (vento 0 + dinâmica desligada, atómico) · "
                "POST /api/reiniciar · POST /api/loop {\"ativo\": bool} · "
                "POST /api/camera {azimute,elevacao,distancia} (câmara da janela 3D, contrato v2: SEM "
                "`alvo` — o alvo é SEMPRE o drone — e o `seq` do corpo é IGNORADO porque o servidor "
                "carimba sempre o seu; só apresentação)\n"
                "SEM REINÍCIO por omissão (pedido do dono, 2026-10-09): no fim do episódio a física CONTINUA\n"
                "no estado em que ficou (nunca reinicia sozinha e nunca congela) e só um REINICIAR\n"
                "(POST /api/reiniciar) recomeça. `--com-loop` (alias `--loop`) liga o CONTÍNUO no arranque; o\n"
                "`--sem-loop` é o mesmo que a omissão (explícito e idempotente). O ARRANQUE é AUTORITATIVO: a\n"
                "flag vence o `loop` que estiver no ficheiro e corrige-o — depois disso só o POST /api/loop o\n"
                "muda (sticky). Escritas parciais no controlo não tocam em `loop` nem em `reiniciar`.\n"
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
    grupo_loop = p.add_mutually_exclusive_group()
    grupo_loop.add_argument("--com-loop", "--loop", dest="com_loop", action="store_true",
                            help="CONTÍNUO: o runner arranca com `--com-loop` (auto-reset no fim do episódio, "
                                 "ep+1). NÃO é o padrão. É AUTORITATIVO no arranque: vence um `loop: false` "
                                 "velho do ficheiro, que fica corrigido para `true`. `--loop` é o alias antigo")
    grupo_loop.add_argument("--sem-loop", action="store_true",
                            help="SEM REINÍCIO (já é o PADRÃO; a flag fica aceite como pedido explícito e "
                                 "idempotente): o runner arranca com `--sem-loop` e o arranque corrige para "
                                 "`false` um `loop: true` velho do ficheiro; no fim do episódio a física "
                                 "CONTINUA no estado em que ficou e um REINICIAR recomeça")
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
    # ARRANQUE AUTORITATIVO (pedido do dono, 2026-10-09): o `loop` do arranque é SEM REINÍCIO (default) ou
    # CONTÍNUO (`--com-loop`), e o ficheiro de controlo passa a dizer o mesmo MESMO QUE JÁ EXISTA — um
    # `loop: true` velho de uma sessão anterior não sobrevive ao arranque. `escrever_controlo` faz merge
    # sobre o que lá está (ou sobre `CONTROLO_INICIAL` se faltar), por isso uma escrita de `{"loop": ...}`
    # só toca no `loop`: vento, dinâmica e — sobretudo — o contador `reiniciar` ficam intactos. Depois
    # disto só o `POST /api/loop` muda o modo (semântica sticky); o runner repete a correcção por si
    # (`fixar_loop`), para um arranque directo do `sim_view.py` valer o mesmo.
    # O carimbo `loop_arranque` (token único desta sessão, gerado aqui) viaja no ficheiro E no ambiente do
    # filho: é o que impede o runner — que pode levar segundos a importar — de reverter um `POST /api/loop`
    # feito pelo dono entretanto (ver `CAMPO_ARRANQUE` e `sim_view.fixar_loop`).
    loop_inicial = bool(args.com_loop)
    token_arranque = os.urandom(8).hex()
    antes = ler_controlo_bruto(args.controlo).get("loop")
    arranque = escrever_controlo(args.controlo, {"loop": loop_inicial, CAMPO_ARRANQUE: token_arranque})
    # A memória do servidor nasce do que ESTE arranque acabou de escrever (o arranque é autoritativo): é ela
    # que sobrevive a um ficheiro de controlo apagado/corrompido durante a execução (ver `Servidor.memorizados`).
    memorizados = {chave: arranque[chave] for chave in COMANDOS if chave in arranque}
    print(f"[site] controlo: {args.controlo} (loop={loop_inicial}"
          + (f", corrigido de {antes!r}" if isinstance(antes, bool) and antes != loop_inicial
             else (", ficheiro criado" if not isinstance(antes, bool) else ", ja estava"))
          + ("; SEM REINICIO por omissao" if not loop_inicial else "; CONTINUO (--com-loop)") + ")", flush=True)

    # o runner corre com cwd=experiments/09_drone_hover_rl: `--model` relativo resolve-se contra o cwd do SITE
    modelo, motivo = escolher_modelo(args)
    if not modelo.is_file():
        raise SystemExit(f"[site] modelo inexistente: {modelo}")
    print(f"[site] modelo: {modelo} ({motivo})", flush=True)   # diz SEMPRE qual escolheu e porquê
    filho = lancar_runner(args, modelo, token_arranque)
    servidor = Servidor(args.controlo, args.telemetria, args.host, args.port, args.verboso, filho, modelo,
                        motivo, memorizados)
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
