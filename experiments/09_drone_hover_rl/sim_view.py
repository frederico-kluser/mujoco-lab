#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/sim_view.py — runner da simulação: janela MuJoCo LIMPA + telemetria JSONL.

Uma janela e mais nada: `mujoco.viewer.launch_passive` com `show_left_ui=False, show_right_ui=False` e ZERO
overlay (nunca se chama `set_texts`/`set_figures`; `clear_texts()` no arranque garante o ecrã limpo). Toda a
informação — métricas, vento, reiniciar, loop — vive no SITE (`sim_site.py` + `site/dist/`), que fala com
este processo por DOIS FICHEIROS:

  · CONTROLO (o site escreve, sempre atómico tmp+os.replace)
      out/controle_vento.json = {"vel": 0..5, "azimute": 0..360, "elevacao": -90..90, "ativo": bool,
                                 "reiniciar": int, "loop": bool, "camera": {...}, "t": float}
    Lido a CADA passo de decisão (assinatura mtime_ns+tamanho: um ficheiro reescrito é sempre visto):
      - vento → `env.definir_vento(vel, azimute, elevacao)` (com `ativo: false` → vento 0);
      - `reiniciar` → contador; quando MUDA é um REINICIAR (1.º contador visto é linha de base; um contador
        ≥ 1 que apareça sem ficheiro prévio é um REINICIAR já pedido — mesma regra do net_probe/dashboard).
        É o ÚNICO caminho para recomeçar um episódio, e vale em QUALQUER estado;
      - `loop` → `true` mantém o rollout CONTÍNUO: no fim do episódio faz reset e segue (ep+1, passo 0) sem
        congelar nem pedir nada; `false` (PADRÃO, pedido do dono em 2026-10-09) é SEM REINÍCIO: no fim do
        episódio a física CONTINUA a integrar no estado em que ficou (nunca reinicia sozinha e NUNCA congela)
        e só um REINICIAR recomeça. Campo ausente = não mexe. O ARRANQUE é AUTORITATIVO: quem decide é o CLI
        (`--com-loop` → CONTÍNUO; omissão ou `--sem-loop` → SEM REINÍCIO), nunca um `loop` velho deixado no
        ficheiro por uma sessão anterior — `fixar_loop` corrige o ficheiro já antes de o vigia ler a linha de
        base, para o site mostrar o estado verdadeiro (`--com-loop` vence um `loop: false` velho tal como o
        `--sem-loop` vence um `loop: true`). Autoridade com um LIMITE explícito: um `POST /api/loop` feito
        DURANTE o arranque (a janela em que este processo ainda importa o torch/SB3) é a última palavra do
        dono e NUNCA é revertido — o site carimba a escrita de arranque com um token (`loop_arranque`) e
        passa-o ao filho na variável `ENV_LOOP_ARRANQUE`; se o carimbo já não for o do arranque, escreveu um
        POST e o `fixar_loop` respeita-o (ver `fixar_loop`). Depois do arranque, quem muda o `loop` é o
        `POST /api/loop` do site — é a semântica sticky, e as escritas parciais do vento nunca lhe tocam.
  · TELEMETRIA (escrita AQUI, ~10 Hz = 1 linha JSON por amostra, SEMPRE — não há batimento lento)
      out/sim_telemetria.jsonl = {"t","estado","loop","ep","passo","retorno","z","dist_xy","yaw_err",
                                  "vento_vel","vento_azim","vento_vec","vento_modo","obs":[16],"act":[4],
                                  "ctrl":[4],"h1":[64],"h2":[64],"camera":{...}|null}
    `t` = tempo de SIMULAÇÃO do episódio (s, volta a 0 em cada reset); `estado` = "a_correr" |
    "episodio_terminado" (este SÓ com `loop: false` e o episódio acabado; com o contínuo a transição é
    invisível e o estado mantém-se "a_correr"). ATENÇÃO à semântica desde a ronda 11: `episodio_terminado`
    diz que o EPISÓDIO fechou (não houve reinício), NÃO que a física parou — com `loop: false` o
    `passo`/`t` continuam a crescer e o `retorno` fica congelado no valor do episódio terminado;
    `loop` = modo em vigor no runner (aditivo); `obs`/`act`/`ctrl`
    na MESMA linha que `h1`/`h2` (ativações da MLP por forward hooks
    nos `nn.Linear`, a mesma técnica do net_probe: `h1` = saída da 1.ª Linear, `h2` = da 2.ª); `act` é a ação
    de política (Box(-1,1)⁴) e `ctrl` o comando FÍSICO que ela produziu (`data.ctrl` = [empuxo N, mx, my, mz
    N·m], via `env.acao_para_ctrl`/`aplicar_acao`) — o site mostra o `ctrl` do backend sem o derivar da ação.
    Coerência (ver `amostra`): `ctrl == acao_para_ctrl(act)` nas linhas com `passo > 0` (ação aplicada); nas
    linhas de arranque/reinício (`passo == 0`, `t == 0`) valem `act == ctrl == [0,0,0,0]`, porque o `reset`
    zera o `data.ctrl` e não houve ação nenhuma (não se inventa ali um `ctrl` que o simulador não aplicou).
    Cada linha é escrita com `flush` para o site a ver sem esperar; no fim do episódio escreve-se LOGO uma
    linha de evento (não se espera pelos 0,1 s).

VENTO DINÂMICO AO VIVO (campo `"dinamico"` do controlo, sem reset nenhum — a política continua a voar):
`{"dinamico": {"modo": ..., "params": {...}, "ativo": bool, "seq": int}}`, com `modo` num de
`nenhum | rajadas | aleatoria | frente | dryden | rajada_agora`:
  · `rajadas`/`aleatoria`/`dryden` → `env.definir_vento_dinamico({modo, **params})` (os MESMOS modos e a
    mesma validação do treino: `p`/`duracao`/`u_max` nos dois primeiros — em `aleatoria` só `p`/`duracao`
    têm semântica — e `sigma`/`L`/`u_max`/`v_min` no dryden); `u_max = 0` fica inerte;
    Trocar de modo/ligar/desligar é imediato (o env re-planeia o resto do episódio);
  · `frente` aceita DOIS formatos de `params` (contrato final): (a) `vel`/`azimute`/`elevacao` = degrau
    IMEDIATO do vento base (`definir_vento`, validado com as faixas do vento base, sem passar pelo
    `env.valida_vento_dinamico`) — é o que o site manda quando o dono muda o vento no modo `frente`;
    (b) `u_max`/`t_s` = degrau em curso do env, ao instante `t_s` do modo, como sempre;
  · `rajada_agora` → rajada DIRIGIDA one-shot (o env não tem rajadas dirigidas): `params` = `u` [0, 5] m/s,
    `azimute` [0, 360)°, `elevacao` ±90°, `duracao` (passos de decisão, 25 por omissão). O envelope é
    `sin(π·k/(N+1))` — o MESMO do modo `rajadas` do env — somado ao vento base em vigor e escrito no
    `opt.wind` passo a passo com `definir_vento` (nada de forças mágicas); no fim volta ao vento base;
  · `nenhum` (ou `ativo: false`) → PARAR: corta a rajada one-shot em curso, desliga o modo do env (o que
    também limpa o estado dele: rajada/turbulência/frente) e reescreve em `opt.wind` o vento BASE do
    controlo em vigor. Depois de um PARAR não fica NADA ativo nem pendente (nem no slot da rajada, nem no
    env, nem um restauro de base por fazer). O campo `"vel"/"azimute"/"elevacao"` continua a mandar no vento
    BASE e pode mudar a qualquer instante, com ou sem dinâmica; o `POST /api/parar` do site manda as duas
    coisas na MESMA escrita (vento base a 0 + dinâmica desligada) — é o botão PARAR VENTO.
A assinatura do bloco (`modo`+`params`+`ativo`+`seq`) evita re-disparos: reescrever o ficheiro com o mesmo
bloco não faz nada — o site incrementa o `seq` quando quer disparar outra rajada igual. A telemetria mostra
`vento_vec` (vx,vy,vz m/s, o vento que a física leva) e `vento_modo` (modo em vigor) em cada amostra.

CÂMARA DA JANELA 3D — ESTILO TERCEIRA-PESSOA DE JOGO (campo `"camera"` do controlo — APRESENTAÇÃO pura:
nunca toca na física). A câmara ORBITE SEMPRE o drone: o ALVO (`lookat`) é o corpo do drone e não há
comando nenhum de alvo (pedido do dono, 2026-10-10: «rotacionar em torno do drone, sempre num efeito meio
terceira-pessoa como jogos»). O bloco manda só no ORBITAR/zoom:
`{"camera": {"azimute": graus, "elevacao": graus, "distancia": m, "seq": int}}`  (SEM `alvo`)
  · ALVO SEMPRE NO DRONE (`seguir_drone`, a cada frame): `viewer.cam.lookat = data.body(CAM_CORPO).xpos +
    CAM_OFFSET` (offset constante, hoje [0, 0, 0]) — COLA EXACTA, atualizada a CADA frame (antes de cada
    `viewer.sync` e de cada linha de telemetria). Escolha documentada: cola exata em vez de seguimento
    suavizado — é determinística (o mesmo frame dá sempre o mesmo `lookat`), prova-se a 1e-9 no
    `teste_camera.py` (§2) e mantém a honestidade da telemetria (`camera.alvo` = `lookat` real =
    drone+offset SEM lag); uma suavização tipo jogo pôr-ia o `alvo` atrás do drone e enfraqueceria as
    duas coisas. É isso que dá o efeito terceira-pessoa: o drone fica sempre ao centro e a câmara orbita;
  · `azimute`/`elevacao`/`distancia` aplicam-se ao `viewer.cam` (`cam.azimuth`/`elevation`/`distance`) UMA
    VEZ por MUDANÇA DE ASSINATURA (`seq` + valores) e PRESERVAM-SE entre comandos: o RATO da janela
    continua a poder orbitar (muda `azimuth`/`elevation`) e a fazer zoom (muda `distance`) e esses valores
    sobrevivem até ao próximo comando de câmara. O PAN do rato (que mexe no `lookat`) é
    INTENCIONALMENTE SOBREPOSTO pelo seguimento — num orbitar terceira-pessoa o alvo não sai do drone
    (documentado também no `INTERFACE.md` §3.5/§4.4);
  · faixas do contrato: `azimute` finito (normalizado mod 360), `elevacao` ∈ [-90, 90], `distancia` ∈ ]0, 20]
    (a UI usa 0,1–10) e `seq` inteiro ≥ 0 que o SERVIDOR incrementa a CADA comando (como o `dinamico.seq`
    — é o que faz re-aplicar valores iguais); fora disto o registo é ignorado com aviso e o que estava em
    vigor fica. Chaves DESCONHECIDAS do bloco (ex. um `alvo` de ficheiros do contrato v1) são ignoradas em
    silêncio — ficheiros velhos não rebentam;
  · SEM viewer (`--sem-janela`, testes) o bloco é IGNORADO sem erro (e o seguimento também) e a telemetria
    publica `"camera": null`; um «viewer falso» de teste (objeto com `sync/is_running/lock/m/viewport` e
    `.cam`) recebe os valores nos atributos `.cam` do objeto;
  · no ARRANQUE aplica-se `CAM_PADRAO` (`{azimute, elevacao, distancia}` = os valores de
    `mjv_defaultFreeCamera(model)` deste modelo, SEM alvo — o default fica EXPLÍCITO e idêntico ao de
    hoje) e a telemetria publica a câmara REAL em cada amostra: `"camera" = {azimute, elevacao, distancia,
    alvo:[x,y,z]}` (a 19.ª chave; `alvo` = o `lookat` REAL = drone+offset) ou `null`;
  · REPOR VISTA = enviar os valores de `CAM_PADRAO` como um comando normal (não há mecanismos extra).

SEM REINÍCIO POR OMISSÃO (pedido do dono, 2026-10-09): `loop` nasce DESLIGADO, por isso um arranque sem
`--com-loop` corre SEM REINÍCIO — no fim do episódio a física continua a integrar (`env.step` a 50 Hz) no
estado em que ficou, para sempre (se caiu, fica onde a física o deixou; se pairava, continua a pairar), com a
telemetria ao ritmo normal e sem auto-reset nenhum. O estado passa a "episodio_terminado" (o EPISÓDIO fechou)
e o `retorno` fica no valor com que ele fechou; `passo`/`t` continuam a crescer, o que prova que não houve
reset. Só o REINICIAR do site recomeça — o contador `reiniciar` funciona em QUALQUER estado (a correr,
terminado ou a meio de um episódio). `--max-segundos` e `--max-episodios` continuam a terminar o processo
(são flags explícitas, não auto-loop).

MODO CONTÍNUO (`loop: true`, ou `--com-loop` no arranque): quando o episódio termina (`terminated` OU
`truncated`) faz reset e SEGUE — ep+1, passo 0 — sem congelar, sem mensagem de erro e sem pedir nada. A
transição é INVISÍVEL para quem trabalha: o vento base, o modo dinâmico e uma rajada one-shot a meio
ATRAVESSAM o reset (`Controlo.reaplicar` volta a escrever o controlo em vigor logo depois do `env.reset`,
porque o ficheiro de controlo é a fonte); o `seq` do bloco dinâmico não muda, logo nada é re-disparado por
engano. Depois do arranque, ligar/desligar o contínuo é só `POST /api/loop` no site.

    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_view.py                    # janela limpa
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_view.py --fator-tempo 0.5  # metade da velocidade
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_view.py --sem-janela --max-segundos 20
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py                    # 1 comando: janela + site

Teclado (foco na janela): ESPAÇO pausa/retoma · Q ou Esc fecha. Não há mais teclas: o vento, a CÂMARA e o
REINICIAR são do site (é o que mantém a janela 100% limpa); o rato do viewer continua livre entre comandos
de câmara.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

# Ordem intencional (por isso o I001 fica desligado nesta linha): o `mjkit` define MUJOCO_GL=egl ANTES de
# `import mujoco`. O viewer (GLFW) não depende disso — ver o cabeçalho do `lab/mjkit.py`.
from lab import mjkit  # noqa: F401, I001
from lab import crazyflie as cf
from env import HoverEnv
from env_real import OBS_ATOR_DIM, DroneRealEnv

import numpy as np

# ---------------------------------------------------------------------------------------------- constantes
CONTROLO_OMISSAO = _AQUI / "out" / "controle_vento.json"
TELEMETRIA_OMISSAO = _AQUI / "out" / "sim_telemetria.jsonl"
# Controlo de um ficheiro NOVO (só se ele não existir; o `loop` entra à parte, com a intenção do CLI — ver
# `fixar_loop`): os mesmos campos iniciais do `sim_site.py`, sem `loop` nem `t`.
CONTROLO_INICIAL = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False, "reiniciar": 0}
# Carimbo do arranque (ver `fixar_loop`): o SITE escreve-o no ficheiro de controlo ao fixar o `loop` inicial e
# passa o mesmo token ao runner pela variável de ambiente `ENV_LOOP_ARRANQUE`. É um canal INTERNO site→runner
# (o mesmo nome existe no `sim_site.py`), não configuração do dono: serve para o runner distinguir «o ficheiro
# ainda diz o que o site escreveu no arranque» de «alguém o mudou depois» (um `POST /api/loop`, que vence).
CAMPO_ARRANQUE = "loop_arranque"
ENV_LOOP_ARRANQUE = "DRONE_LOOP_ARRANQUE"
FATOR_TEMPO_OMISSAO = 1.0        # 1 = tempo real; 0 = sem travão (o mais rápido possível); 2 = 2x mais rápido
PERIODO_AMOSTRA = 0.1            # s — cadência da telemetria a correr (~10 Hz)
PERIODO_OCIO = 0.02              # s — ritmo do ciclo quando não há física (pausa): 1 passo de decisão
VEL_MAX, AZIM_MAX, ELEV_MAX = 5.0, 360.0, 90.0      # faixas do contrato do controlo
PRECISAO = 6                     # casas decimais na telemetria (linhas pequenas e legíveis)
TECLA_ESPACO, TECLA_Q, TECLA_ESC = 32, 81, 256      # códigos GLFW entregues pelo viewer
# vento DINÂMICO ao vivo (ver o cabeçalho do módulo): 4 modos são do `env.py`, `rajada_agora` é um one-shot
# dirigido aplicado AQUI (o env não tem rajadas dirigidas) e `nenhum` é inerte.
MODOS_DINAMICOS = ("nenhum", "rajadas", "aleatoria", "frente", "dryden", "rajada_agora")
MODOS_DINAMICOS_ENV = ("rajadas", "aleatoria", "frente", "dryden")
FRENTE_BASE, FRENTE_ENV = ("vel", "azimute", "elevacao"), ("u_max", "t_s")   # os 2 formatos do `frente`
RAJADA_DURACAO_PADRAO = 25       # passos de decisão (0,5 s a 50 Hz) — duração da rajada one-shot
RAJADA_U_PADRAO = 3.0            # m/s — amplitude da rajada one-shot quando `u` não vem nos params
RAJADA_U_MAX = 5.0               # m/s — teto do contrato para a rajada one-shot
# CÂMARA da janela 3D (só apresentação, estilo TERCEIRA-PESSOA): `CAM_PADRAO` são os valores de ARRANQUE
# do viewer — `mujoco.mjv_defaultFreeCamera(model, cam)` para o modelo deste experimento (as hélices
# visíveis são a configuração por omissão do `sim_view.py`, e elas entram no `model.stat` que define
# `distance`/`lookat`), SEM `alvo` (contrato v2: o alvo é SEMPRE o drone — ver `seguir_drone`). O `azimute`
# vem já NORMALIZADO mod 360 (340.0 ≡ −20.0 do `mjv_defaultFreeCamera`: a MESMA pose) porque é assim que o
# contrato normaliza os comandos — assim o REPOR VISTA faz ida-e-volta EXACTA (os mesmos valores no
# `camera_padrao`, no ficheiro, no `viewer.cam` e no `camera_atual`). Constante EXPLÍCITA, aplicada no
# arranque, para o default ser o mesmo em todo o lado — runner, `camera_padrao` da API e REPOR VISTA do
# site — e o `teste_camera.py` garante que continua igual ao que o `mjv_defaultFreeCamera` devolve (se o
# modelo mudar, o teste aponta-o em vez de divergir em silêncio).
CAM_PADRAO = {"azimute": 340.0, "elevacao": -20.0, "distancia": 0.27471697907043846}
CAM_DIST_MAX = 20.0              # m — teto do contrato para a `distancia` (a UI usa 0,1–10)
# ALVO da câmara terceira-pessoa (`seguir_drone`): o CORPO do drone + um offset constante SOMADO a
# `xpos` (elemento a elemento, frame MUNDO — com o offset nulo de hoje, [0, 0, 0], o alvo é o centro do
# corpo). `CAM_OFFSET` documentado e testável (o `teste_camera.py` §2 compara `lookat` com
# `body(CAM_CORPO).xpos + CAM_OFFSET` em cada frame). Mudar o offset
# muda só o ponto olhado — a física nunca é tocada (a câmara é apresentação).
CAM_CORPO = "cf2"                # nome do corpo do drone no cf2.xml (acesso por NOME, nunca por índice);
#                                  na planta REAL o `main` troca-o para "drone" (corpo do modelo gerado)
PASTA_BATERIA = _AQUI / "out" / "bateria"   # estado PERSISTENTE de cada pack (desgaste + carga) — planta real
ACOES_BATERIA = ("recarregar", "nova")      # comando `bateria` do controlo: fecha o ciclo / troca de pack
CAM_OFFSET = (0.0, 0.0, 0.0)     # m — SOMADO elemento a elemento a body(CAM_CORPO).xpos (frame MUNDO)


# ---------------------------------------------------------------------------------------------- controlo
@dataclass
class Dinamico:
    """Bloco `"dinamico"` do controlo: `{modo, params, ativo, seq}` (o `seq` é do site, para re-disparos)."""

    modo: str = "nenhum"
    params: dict = field(default_factory=dict)
    ativo: bool = False
    seq: int | None = None

    def assinatura(self) -> str:
        """Assinatura estável do bloco: só uma MUDANÇA dela (re)dispara um modo/rajada."""
        return json.dumps({"modo": self.modo, "params": self.params, "ativo": self.ativo, "seq": self.seq},
                          sort_keys=True)


@dataclass
class Camera:
    """Bloco `"camera"` do controlo: `{azimute, elevacao, distancia, seq}` (só APRESENTAÇÃO, 3.ª pessoa).

    É o comando de ORBITAR/zoom da janela 3D (nunca toca na física e nunca manda no alvo — o alvo é SEMPRE
    o drone, ver `seguir_drone`): o `seq` é do SERVIDOR, incrementado a cada comando, e entra na
    assinatura — o runner aplica o bloco UMA VEZ por mudança de assinatura.
    """

    azimute: float = 0.0
    elevacao: float = 0.0
    distancia: float = 1.0
    seq: int | None = None

    def assinatura(self) -> str:
        """Assinatura estável do bloco (`seq` + valores): só uma MUDANÇA dela (re)aplica a câmara."""
        return json.dumps({"azimute": self.azimute, "elevacao": self.elevacao,
                           "distancia": self.distancia, "seq": self.seq}, sort_keys=True)

    def valores(self) -> dict:
        """Os valores do bloco no formato de `CAM_PADRAO` (para `aplicar_camera`)."""
        return {"azimute": self.azimute, "elevacao": self.elevacao, "distancia": self.distancia}


@dataclass
class Registo:
    """Conteúdo validado do ficheiro de controlo (vento base + comandos de episódio + vento dinâmico)."""

    vel: float = 0.0
    azimute: float = 0.0
    elevacao: float = 0.0
    ativo: bool = True
    reiniciar: int | None = None     # None = campo ausente: não mexe no contador
    loop: bool | None = None         # None = campo ausente: não mexe no modo
    dinamico: Dinamico | None = None  # None = campo ausente: não mexe no vento dinâmico
    camera: Camera | None = None     # None = campo ausente: não mexe na câmara


def _numero(dados: dict, campo: str, predefinido: float) -> float:
    """Campo numérico finito do registo (`ValueError` descritivo se não o for)."""
    valor = dados.get(campo, predefinido)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(float(valor)):
        raise ValueError(f"`{campo}` tem de ser um número finito (recebido {valor!r})")
    return float(valor)


def _booleano(dados: dict, campo: str) -> bool | None:
    """Campo booleano opcional do registo (tolera 0/1 escrito à mão); `None` se ausente."""
    valor = dados.get(campo)
    if valor is None:
        return None
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, int) and valor in (0, 1):
        return bool(valor)
    raise ValueError(f"`{campo}` tem de ser booleano (recebido {valor!r})")


def _params_rajada_agora(params: dict) -> dict:
    """Valida/normaliza os params da rajada one-shot: `u` [0, 5] m/s, `azimute` [0, 360)°, `elevacao` ±90°."""
    desconhecidas = set(params) - {"u", "azimute", "elevacao", "duracao"}
    if desconhecidas:
        raise ValueError(f"`dinamico.params` (rajada_agora) tem chaves desconhecidas {sorted(desconhecidas)} "
                         "— aceita ['azimute', 'duracao', 'elevacao', 'u']")
    u = _numero(params, "u", RAJADA_U_PADRAO)
    if not 0.0 <= u <= RAJADA_U_MAX:
        raise ValueError(f"`dinamico.params.u` tem de estar em [0, {RAJADA_U_MAX}] m/s (recebido {u!r})")
    duracao = params.get("duracao", RAJADA_DURACAO_PADRAO)
    if isinstance(duracao, bool) or not isinstance(duracao, (int,)) or int(duracao) < 1:
        raise ValueError(f"`dinamico.params.duracao` tem de ser um inteiro ≥ 1 passos de decisão "
                         f"(recebido {duracao!r})")
    return {"u": u, "azimute": _numero(params, "azimute", 0.0) % AZIM_MAX,
            "elevacao": min(ELEV_MAX, max(-ELEV_MAX, _numero(params, "elevacao", 0.0))),
            "duracao": int(duracao)}


def _params_frente(params: dict) -> tuple[str, dict]:
    """Params do modo `frente` → `("base"|"env", params)`: aceita os DOIS formatos do contrato.

    · formato (a) `{"vel", "azimute", "elevacao"}` → degrau IMEDIATO do vento base (`definir_vento`),
      validado AQUI com as faixas do vento base (as mesmas do `POST /api/vento`: `vel` [0, 5] m/s,
      `azimute` [0, 360]°, `elevacao` ±90°) — NÃO passa pelo `env.valida_vento_dinamico`, que espera
      `u_max`/`t_s` e recusaria estas chaves (o site manda este formato para um degrau imediato). Campo
      ausente vale 0 (o site manda sempre os três: o que não vem lá mantém o vento base em vigor);
    · formato (b) `{"u_max", "t_s"}` (ou sem params) → modo em curso do env (`t_s` = instante do degrau
      dentro do modo), como sempre: quem valida é o `env.definir_vento_dinamico`.
    Chaves desconhecidas ou mistura dos dois formatos → `ValueError`. O `"modo"` dentro dos `params` (o
    `env.valida_vento_dinamico` devolve-o e o site guarda-o tal e qual) é tolerado quando diz "frente".
    """
    limpos = dict(params)
    if limpos.get("modo") == "frente":                   # params normalizados do env trazem o `modo` dentro
        limpos.pop("modo")
    desconhecidas = set(limpos) - set(FRENTE_BASE) - set(FRENTE_ENV)
    if desconhecidas:
        raise ValueError(f"`dinamico.params` (frente) tem chaves desconhecidas {sorted(desconhecidas)} — aceita "
                         f"{list(FRENTE_BASE)} (degrau imediato do vento base) ou {list(FRENTE_ENV)} "
                         "(modo em curso do env)")
    da_base = [c for c in FRENTE_BASE if c in limpos]
    do_env = [c for c in FRENTE_ENV if c in limpos]
    if da_base and do_env:
        raise ValueError(f"`dinamico.params` (frente) não pode misturar os dois formatos: {da_base} são um "
                         f"degrau imediato do vento base e {do_env} o modo em curso do env")
    if not da_base:
        return "env", dict(params)                       # (b): sem params = defaults do env
    vel = _numero(limpos, "vel", 0.0)
    if not 0.0 <= vel <= VEL_MAX:
        raise ValueError(f"`dinamico.params.vel` tem de estar em [0, {VEL_MAX}] m/s (recebido {vel!r})")
    azimute = _numero(limpos, "azimute", 0.0)
    if not 0.0 <= azimute <= AZIM_MAX:
        raise ValueError(f"`dinamico.params.azimute` tem de estar em [0, {AZIM_MAX}] graus (recebido {azimute!r})")
    elevacao = _numero(limpos, "elevacao", 0.0)
    if not -ELEV_MAX <= elevacao <= ELEV_MAX:
        raise ValueError(f"`dinamico.params.elevacao` tem de estar em [-{ELEV_MAX}, {ELEV_MAX}] graus "
                         f"(recebido {elevacao!r})")
    return "base", {"vel": vel, "azimute": azimute, "elevacao": elevacao}


def _ler_dinamico(bruto) -> Dinamico | None:
    """`"dinamico"` do controlo → `Dinamico` validado (`None` se o campo não vier).

    Valida só a ESTRUTURA (modo conhecido, `params` objeto, `ativo` booleano, `seq` inteiro), as faixas do
    `rajada_agora` e os DOIS formatos do `frente` (o (a) é nosso: degrau imediato do vento base). Nos
    `rajadas`/`dryden` — e no `frente` do formato (b) — quem valida os parâmetros é o PRÓPRIO
    `env.definir_vento_dinamico` (mesmas regras do treino — não se duplicam aqui).
    """
    if bruto is None:
        return None
    if not isinstance(bruto, dict):
        raise ValueError("`dinamico` tem de ser um objeto JSON {modo, params, ativo}")  # noqa: TRY004
    modo = bruto.get("modo", "nenhum")
    if modo not in MODOS_DINAMICOS:
        raise ValueError(f"`dinamico.modo` tem de ser um de {MODOS_DINAMICOS} (recebido {modo!r})")
    params = bruto.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("`dinamico.params` tem de ser um objeto JSON")  # noqa: TRY004
    ativo = _booleano(bruto, "ativo")
    seq = bruto.get("seq")
    if seq is not None and (isinstance(seq, bool) or not isinstance(seq, int)):
        raise ValueError(f"`dinamico.seq` tem de ser um inteiro (recebido {seq!r})")
    if modo == "rajada_agora":
        params = _params_rajada_agora(params)
    elif modo == "frente":
        params = _params_frente(params)[1]          # valida os 2 formatos e guarda os params normalizados
    return Dinamico(modo, params, (modo != "nenhum") if ativo is None else bool(ativo), seq)


def _ler_camera(bruto) -> Camera | None:
    """`"camera"` do controlo → `Camera` validada (`None` se o campo não vier).

    Faixas do contrato: `azimute` finito (normalizado mod 360), `elevacao` ∈ [-90, 90] e `distancia` ∈
    ]0, 20] ESTRITOS (fora → `ValueError`, como o `dinamico`) e `seq` inteiro ≥ 0 opcional (faz parte da
    assinatura). Os três valores são OBRIGATÓRIOS: o bloco é sempre completo — quem o escreve é o
    `validar_camera` do site (que completa os campos ausentes a partir do bloco em vigor) ou a mão, e um
    bloco a meio dizia menos do que a câmara que se aplica. NÃO há `alvo` (contrato v2: o alvo é SEMPRE o
    drone) e chaves DESCONHECIDAS do bloco são ignoradas em silêncio — um ficheiro velho do contrato v1
    (com `alvo: [x,y,z]`) ou um bloco com lixo não rebenta o registo: o runner ignora o que não conhece e
    aplica o resto.
    """
    if bruto is None:
        return None
    if not isinstance(bruto, dict):
        raise ValueError("`camera` tem de ser um objeto JSON {azimute, elevacao, distancia}")  # noqa: TRY004
    faltam = [campo for campo in ("azimute", "elevacao", "distancia") if campo not in bruto]
    if faltam:
        raise ValueError(f"`camera` tem de trazer os campos {sorted(faltam)} (bloco completo)")
    azimute = _numero(bruto, "azimute", 0.0) % AZIM_MAX
    elevacao = _numero(bruto, "elevacao", 0.0)
    if not -ELEV_MAX <= elevacao <= ELEV_MAX:
        raise ValueError(f"`camera.elevacao` tem de estar em [{-ELEV_MAX}, {ELEV_MAX}] graus "
                         f"(recebido {elevacao!r})")
    distancia = _numero(bruto, "distancia", 0.0)
    if not 0.0 < distancia <= CAM_DIST_MAX:
        raise ValueError(f"`camera.distancia` tem de estar em ]0, {CAM_DIST_MAX}] m (recebido {distancia!r})")
    seq = bruto.get("seq")
    if seq is not None and (isinstance(seq, bool) or not isinstance(seq, int) or seq < 0):
        raise ValueError(f"`camera.seq` tem de ser um inteiro ≥ 0 (recebido {seq!r})")
    return Camera(azimute, elevacao, distancia, seq)


def ler_registo(dados) -> Registo:
    """Ficheiro de controlo → `Registo` validado (mesmas regras do net_probe/dashboard).

    `vel` ∈ [0, 5] e finita; `azimute` reduzido a [0, 360); `elevacao` cortada a [-90, 90]; `ativo` booleano
    (predefinido `True`, como no contrato v2); `reiniciar` inteiro ≥ 0, `loop` booleano, `dinamico` um bloco
    `{modo, params, ativo, seq}` e `camera` um bloco `{azimute, elevacao, distancia, seq}`
    (`_ler_camera`), todos OPCIONAIS (`None` = «não mexe»). Chaves DESCONHECIDAS do ficheiro (e do bloco
    `camera` — ex. o `alvo` do contrato v1) são ignoradas em silêncio: ficheiros velhos não rebentam. Fora
    das faixas é `ValueError` e o vento anterior fica em vigor.
    """
    if not isinstance(dados, dict):
        raise ValueError("o ficheiro não é um objeto JSON")  # noqa: TRY004  (conteúdo, não um tipo errado)
    vel = _numero(dados, "vel", 0.0)
    if not 0.0 <= vel <= VEL_MAX:
        raise ValueError(f"`vel` tem de estar em [0, {VEL_MAX}] m/s (recebido {vel!r})")
    azimute = _numero(dados, "azimute", 0.0) % AZIM_MAX
    elevacao = min(ELEV_MAX, max(-ELEV_MAX, _numero(dados, "elevacao", 0.0)))
    ativo = _booleano(dados, "ativo")
    reiniciar = dados.get("reiniciar")
    if reiniciar is not None:
        if isinstance(reiniciar, bool) or not isinstance(reiniciar, int) or reiniciar < 0:
            raise ValueError(f"`reiniciar` tem de ser um inteiro ≥ 0 (recebido {reiniciar!r})")
        reiniciar = int(reiniciar)
    return Registo(vel, azimute, elevacao, True if ativo is None else ativo, reiniciar,
                   _booleano(dados, "loop"), _ler_dinamico(dados.get("dinamico")),
                   _ler_camera(dados.get("camera")))


def ler_controlo_bruto(caminho: Path) -> dict:
    """Conteúdo do ficheiro de controlo TAL E QUAL (`{}` se não existir ou não for um objeto JSON).

    Não inventa chaves nenhumas: ausência é ausência. É o que permite a `fixar_loop` preservar tudo o que
    o dono/site escreveu (o `reiniciar` incluído) e nunca ressuscitar um `loop` que não está lá.
    """
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


# Contador monotónico do nome do temporário (ver `nome_temporario`): nunca se repete dentro do processo.
_TMP_CONTADOR = itertools.count(1)


def nome_temporario(caminho: Path) -> Path:
    """Nome do ficheiro temporário da escrita atómica: ÚNICO POR ESCRITA (igual ao do `sim_site.py`).

    O nome antigo (`.{nome}.tmp{pid}`) era o MESMO em todas as escritas do processo: duas escritas
    simultâneas (o site é um `ThreadingHTTPServer`) disputavam o mesmo temporário e o segundo `os.replace`
    falhava com `FileNotFoundError`. Com pid + thread + contador, cada escrita tem o seu nome e o
    `os.replace` nunca disputa nada — e nenhum `.tmp` fica órfão.
    """
    return caminho.with_name(f".{caminho.name}.tmp.{os.getpid()}.{threading.get_ident()}."
                             f"{next(_TMP_CONTADOR)}")


def loop_do_arranque(args) -> bool:
    """`loop` com que o ARRANQUE corre — decisão do CLI, nunca do ficheiro de controlo.

    Pedido do dono (2026-10-09): o processo nasce SEM REINÍCIO. Só `--com-loop` (alias: `--loop`) liga o
    contínuo; a omissão e o `--sem-loop` dão `false` (o `--sem-loop` fica aceite como pedido explícito e
    idempotente). O ficheiro não participa da decisão: um `loop: true` velho de uma sessão anterior é
    corrigido por `fixar_loop` (semântica sticky — o arranque corrige, depois só o `POST /api/loop` muda) e,
    mesmo que essa escrita falhe (pasta só de leitura), o rollout arranca no modo decidido AQUI.
    """
    return bool(getattr(args, "com_loop", False))


def token_do_arranque(ambiente=None) -> str | None:
    """Token da escrita de arranque do SITE (`ENV_LOOP_ARRANQUE`), ou `None` num arranque DIRECTO do runner.

    O site carimba o ficheiro de controlo com este token quando fixa o `loop` inicial e passa-o ao filho pelo
    ambiente (ver `fixar_loop`). Sem ele — `sim_view.py` lançado à mão, sem site pelo meio — não há handshake
    nenhum e o runner é autoritativo como sempre foi.
    """
    fonte = os.environ if ambiente is None else ambiente
    return fonte.get(ENV_LOOP_ARRANQUE) or None


def fixar_loop(caminho: Path, loop: bool, arranque: str | None = None) -> bool:
    """Fixou o `loop` no ficheiro? (escrita ATÓMICA; `False` = já lá estava, foi respeitado ou não deu).

    No arranque a intenção do CLI é AUTORITATIVA e o ficheiro de controlo é corrigido para dizer o mesmo:
    `--sem-loop` (ou a omissão, que agora é SEM REINÍCIO) vence um `loop: true` velho e `--com-loop` vence um
    `loop: false` velho — para o site mostrar o estado VERDADEIRO (e não o pedido antigo) a correcção
    escreve-se no próprio ficheiro de controlo, e o runner não guarda um modo escondido só para si. Escreve
    apenas quando é preciso (chave ausente ou com outro valor) e PRESERVA todas as outras chaves, `reiniciar`
    em primeiro lugar: é isso que impede um reset por engano no arranque. Falha de escrita (pasta só de
    leitura) é um aviso, nunca uma excepção — o runner arranca na mesma com o modo pedido na linha de
    comandos.

    CORRIDA DE ARRANQUE (defeito medido, 2026-10-09) — `arranque` é o token do handshake do site:

    · o site escreve o `loop` inicial no ficheiro ANTES de lançar este processo e carimba-o com um token
      próprio (`CAMPO_ARRANQUE`, ver `sim_site.py`); o token chega aqui pela variável `ENV_LOOP_ARRANQUE`;
    · este processo pode demorar segundos a arrancar (import do SB3/torch com cache fria) e nessa janela um
      `POST /api/loop` LEGÍTIMO do dono pode mudar o `loop`. Esse POST limpa o carimbo (o valor já não é o do
      arranque do site) — e é por isso que, com `arranque` definido, o `fixar_loop` NÃO escreve nada quando o
      carimbo do ficheiro já não é o do arranque: a mudança do dono vence, sem depender de nenhum tempo;
    · o valor que o site escreveu é exactamente o que o CLI deste processo pede (`comando_do_runner` repassa
      o MESMO modo), por isso o caso «carimbo ainda é o meu» cai no `return False` de «já diz o que o CLI
      quer» e o ficheiro fica intocado;
    · sem token (`arranque=None`, arranque directo do runner) não há POST nenhum a proteger: mantém-se a
      autoridade antiga — um `loop: true` velho de outra sessão é corrigido para `false` (e vice-versa).
    """
    caminho = Path(caminho)
    dados = ler_controlo_bruto(caminho)
    if arranque is not None and dados.get(CAMPO_ARRANQUE) != arranque:
        print("[sim] controlo: `loop` mudado DEPOIS do arranque do site (POST /api/loop) — respeita-se o "
              f"valor do ficheiro ({dados.get('loop')!r})", flush=True)
        return False                                     # o pedido do dono vence o default do arranque
    if not dados:                                        # ficheiro ausente/ilegível: nasce completo
        dados = dict(CONTROLO_INICIAL)
    elif dados.get("loop") is bool(loop):
        return False                                     # já diz o que o CLI quer: não se toca no ficheiro
    dados["loop"] = bool(loop)
    dados["t"] = time.time()                             # carimbo da escrita (informativo, como no site)
    tmp = nome_temporario(caminho)
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(dados, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(tmp, caminho)                         # troca atómica: o vigia nunca lê meio ficheiro
    except OSError as erro:
        tmp.unlink(missing_ok=True)                      # sem `.tmp` órfãos quando a escrita falha
        print(f"[sim] aviso: não consegui fixar `loop={bool(loop)}` em {caminho} ({erro}) — sigo com o "
              "modo da linha de comandos", file=sys.stderr, flush=True)
        return False
    return True


class Controlo:
    """Vigia o ficheiro de controlo (assinatura mtime_ns+tamanho) e tradu-lo em vento + comandos.

    Verificado a CADA passo de decisão: uma escrita atómica do site chega à física no passo seguinte. Sem
    ficheiro, mantém-se o vento em vigor (o arranque é em ar parado). Um ficheiro inválido é ignorado com um
    aviso (uma vez por texto) — o ciclo nunca morre por causa do controlo.
    """

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self.reiniciar: int | None = None       # último contador visto (None = ainda nenhum)
        self.loop: bool | None = None           # último modo pedido (None = nunca pedido)
        self.pedido_reinicio = False            # há um REINICIAR por consumir
        self.n_ventos = 0
        self.n_reinicios = 0
        self.ultimo: Registo | None = None
        self.dinamico: Dinamico | None = None   # último bloco `dinamico` APLICADO
        self.rajada: dict | None = None         # rajada one-shot em curso: {u, vec, k, n}
        self.rajada_concluida = False           # a última rajada one-shot já terminou (modo volta a "nenhum")
        self._assinatura_dinamica: str | None = None
        self.cam = None                         # alvo da câmara (`viewer.cam`); None = sem viewer: ignora
        self.camera: Camera | None = None       # último bloco `camera` APLICADO
        self.n_cameras = 0                      # aplicações de câmara feitas (contador de auditoria)
        self._assinatura_camera: str | None = None
        self._assinatura: tuple[int, int] | None = None
        self._avisos: set[str] = set()
        self.bateria_seq: int | None = None     # `seq` do último comando de bateria visto (linha de base)
        self.pedido_bateria: str | None = None  # "recarregar" | "nova" por consumir
        self._le_contador_inicial()

    def _le_contador_inicial(self) -> None:
        """Linha de base do contador (sem aplicar vento nenhum): o que o ficheiro já tiver no arranque."""
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            registo = ler_registo(dados)
        except (OSError, ValueError):
            return                                  # sem ficheiro (ou inválido): a linha de base fica None
        self.reiniciar, self.loop = registo.reiniciar, registo.loop
        bloco = dados.get("bateria") if isinstance(dados, dict) else None
        if isinstance(bloco, dict) and isinstance(bloco.get("seq"), int):
            self.bateria_seq = int(bloco["seq"])    # comando velho do ficheiro: linha de base, não se repete

    def ligar_camera(self, cam) -> None:
        """Liga o alvo da câmara (`viewer.cam`; `None` = sem viewer). Só apresentação: ignora sem erro.

        Um bloco `camera` sem `cam` (runner `--sem-janela`, testes) nunca é aplicado — e a telemetria
        publica `"camera": null`, que é a verdade.
        """
        self.cam = cam

    def aplicar_padrao(self) -> None:
        """Aplica `CAM_PADRAO` (orbitar/zoom) ao `viewer.cam` (o default EXPLÍCITO do arranque) e conta-o.

        É o que o `correr` faz antes de qualquer amostra: a janela começa exactamente no default
        `mjv_defaultFreeCamera` (mesmo que o viewer já lá chegasse sozinho, o valor é explícito e igual em
        todo o lado). Não fica «comando» nenhum pendente: o ficheiro de controlo continua a ser a fonte e,
        se trouxer um bloco `camera`, a primeira leitura sobrepõe-se a este default. O `lookat` não se toca
        aqui — é do `seguir_drone` (alvo sempre no drone).
        """
        if self.cam is None:
            return
        aplicar_camera(self.cam, CAM_PADRAO)
        self.n_cameras += 1

    def _assinatura_do_ficheiro(self) -> tuple[int, int] | None:
        """(mtime_ns, tamanho) do ficheiro — `None` se não existe (ou desapareceu)."""
        try:
            st = self.caminho.stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def verifica(self, env: HoverEnv) -> Registo | None:
        """Um passo de decisão: aplica o vento se o ficheiro mudou; devolve o registo aplicado (ou `None`).

        Os comandos (`reiniciar`/`loop`) são lidos na mesma passagem e ficam no próprio objecto; um contador
        novo levanta `pedido_reinicio` (consumido com `consumir_reinicio()`).
        """
        assinatura = self._assinatura_do_ficheiro()
        if assinatura == self._assinatura:
            return None
        self._assinatura = assinatura                # marca já: um ficheiro inválido não é relido sempre
        if assinatura is None:
            return None                              # sem ficheiro: mantém o vento em vigor
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            registo = ler_registo(dados)
        except (OSError, ValueError) as erro:
            self._aviso(f"controlo ignorado ({erro}) — mantenho o vento anterior")
            return None
        self._actualiza_comandos(registo)
        self._comando_bateria(dados.get("bateria"))
        self._aplica(env, registo)
        return registo

    def _comando_bateria(self, bloco) -> None:
        """Bloco `{"bateria": {"acao": "recarregar"|"nova", "seq": int}}`: um `seq` NOVO dispara a ação uma
        vez (o site incrementa-o a cada clique); blocos inválidos são ignorados com aviso."""
        if bloco is None:
            return
        if (not isinstance(bloco, dict) or bloco.get("acao") not in ACOES_BATERIA
                or isinstance(bloco.get("seq"), bool) or not isinstance(bloco.get("seq"), int)):
            self._aviso(f"bloco `bateria` inválido ignorado ({bloco!r}) — esperado "
                        f"{{acao: {'|'.join(ACOES_BATERIA)}, seq: int}}")
            return
        if bloco["seq"] != self.bateria_seq:
            self.bateria_seq = int(bloco["seq"])
            self.pedido_bateria = str(bloco["acao"])
            print(f"[sim] BATERIA: {bloco['acao']} pedido (seq {bloco['seq']})", flush=True)

    def consumir_bateria(self) -> str | None:
        """Devolve (e esquece) o comando de bateria pendente."""
        acao, self.pedido_bateria = self.pedido_bateria, None
        return acao

    def _actualiza_comandos(self, registo: Registo) -> None:
        """Regra do contador: 1.º visto = linha de base; ≥ 1 sem ficheiro prévio = REINICIAR já pedido."""
        if registo.loop is not None:
            self.loop = bool(registo.loop)
        if registo.reiniciar is None:
            return
        if self.reiniciar is None:
            if registo.reiniciar > 0:                # o ficheiro nasceu já com um REINICIAR pedido
                self.pedido_reinicio = True
                print(f"[sim] REINICIAR pedido (contador {registo.reiniciar}, sem linha de base)", flush=True)
        elif registo.reiniciar != self.reiniciar:
            self.pedido_reinicio = True
            print(f"[sim] REINICIAR pedido (contador {self.reiniciar} -> {registo.reiniciar})", flush=True)
        self.reiniciar = int(registo.reiniciar)

    def _aplica(self, env: HoverEnv, registo: Registo) -> None:
        """`ativo` → `definir_vento(vel, azimute, elevacao)`; inativo → `definir_vento(0, 0, 0)`.

        A seguir trata o bloco `dinamico` (vento ao vivo): ver `_aplica_dinamico`. O `ultimo` é fixado ANTES
        do bloco dinâmico: um PARAR (ou a troca de modo) restaura o vento base a partir DESTE registo, e com a
        ordem antiga restaurava o anterior (um PARAR que também mexe no vento — o do botão PARAR VENTO —
        escrevia a base velha em `opt.wind`).
        """
        self.ultimo = registo
        self._aplica_base(env, registo)
        self._aplica_dinamico(env, registo.dinamico)
        self._aplica_camera(registo)                     # apresentação: 1x por mudança de assinatura
        self.n_ventos += 1                               # o controlo está APLICADO (contador de auditoria)
        print(f"[sim] vento -> {registo.vel:.2f} m/s @ {registo.azimute:.1f} deg"
              + (f" (elev {registo.elevacao:+.1f} deg)" if registo.elevacao else "")
              + ("" if registo.ativo else " [desligado]"), flush=True)

    def _aplica_base(self, env: HoverEnv, registo: Registo | None = None) -> None:
        """Escreve o VENTO BASE do registo em vigor (`definir_vento`); não toca no vento dinâmico."""
        r = registo if registo is not None else self.ultimo
        if r is None:
            return
        if r.ativo:
            env.definir_vento(r.vel, r.azimute, r.elevacao)
        else:
            env.definir_vento(0.0, 0.0, 0.0)

    def _aplica_dinamico(self, env: HoverEnv, din: Dinamico | None) -> None:
        """Liga/desliga/reconfigura o vento dinâmico quando o bloco `dinamico` MUDA (sem reset nenhum).

        · `nenhum`/`ativo: false` → `_para_dinamica`: PARA tudo (ver o docstring dele) — é o PARAR DINÂMICO e
          a metade «vento dinâmico» do PARAR VENTO;
        · `rajadas`/`dryden` → `env.definir_vento_dinamico({modo, **params})` (quem valida os parâmetros é
          o env: `ValueError` → aviso e mantém-se o modo anterior);
        · `frente` aceita DOIS formatos (ver `_params_frente`): `{vel, azimute, elevacao}` = degrau
          IMEDIATO do vento base (`_aplica_degrau`, sem passar pelo env) e `{u_max, t_s}` = modo em curso
          do env (como os anteriores);
        · `rajada_agora` → arranca uma rajada DIRIGIDA one-shot (o env não tem rajadas dirigidas): o
          envelope é escrito no vento BASE passo a passo por `passo_rajada`, por cima do base em vigor.
        A assinatura do bloco evita re-disparos: reescrever o ficheiro com o MESMO bloco não faz nada (o
        site muda o `seq` quando quer disparar outra vez).
        """
        assinatura = "nenhum" if din is None else din.assinatura()
        if assinatura == self._assinatura_dinamica:
            return
        self._assinatura_dinamica = assinatura
        self.dinamico = din
        self.rajada_concluida = False            # bloco novo: uma rajada one-shot pode voltar a disparar
        if din is None or not din.ativo or din.modo == "nenhum":
            self._para_dinamica(env)
            return
        if din.modo == "rajada_agora":
            self._inicia_rajada(env, din)
            return
        self.cancelar_rajada(env)                       # mudar de modo cancela a rajada one-shot
        formato, params = _params_frente(din.params) if din.modo == "frente" else ("env", din.params)
        if formato == "base":
            self._aplica_degrau(env, params)            # `frente` (a): degrau imediato do vento base
            return
        try:
            config = env.definir_vento_dinamico({"modo": din.modo, **params})
        except ValueError as erro:
            self._aviso(f"vento dinamico '{din.modo}' recusado pelo env: {erro} — mantenho o anterior")
            return
        print(f"[sim] vento dinamico -> {din.modo} {config}", flush=True)

    def _para_dinamica(self, env: HoverEnv) -> None:
        """PARA o vento dinâmico por completo: é o caminho de `nenhum`/`ativo: false` (PARAR DINÂMICO) e o
        que o PARAR VENTO usa (além de zerar o vento base no controlo).

        Depois disto NÃO fica nada ativo nem pendente: o slot da rajada one-shot é cortado, o vento base do
        controlo em vigor é reescrito em `opt.wind` (é a fonte — o PARAR devolve exatamente o vento base
        comandado, que pode ser 0 no PARAR VENTO) e o modo do env é desligado, o que também limpa o estado
        dele (rajada/turbulência/frente em curso). É idempotente: repetir o PARAR não muda nada.
        """
        self.rajada = None
        self.rajada_concluida = False
        self._aplica_base(env)                       # `self.ultimo` já é o registo em vigor (ver `_aplica`)
        env.definir_vento_dinamico(None)
        print("[sim] vento dinamico -> nenhum (so o vento base)", flush=True)

    def _aplica_camera(self, registo: Registo) -> None:
        """Aplica o bloco `camera` ao `viewer.cam` UMA VEZ por mudança de assinatura (seq + valores).

        Só os 3 valores de ORBITAR/zoom (`azimuth`/`elevation`/`distance`) — o `lookat` NÃO: ele é do
        `seguir_drone`, que o põe no drone a cada frame (3.ª pessoa contínua). Nunca a cada frame: reescrever
        o ficheiro com o MESMO bloco (ex. uma mudança de vento que faça o `escrever_controlo` reescrever
        tudo) não toca na câmara — é isso que preserva o RATO do viewer entre comandos (o dono pode
        orbitar/zoom; só o próximo comando de câmara manda — o PAN é na mesma sobreposto pelo seguimento).
        Um `seq` novo com os mesmos valores muda a assinatura e RE-APLICA (é o contrato do servidor). Sem
        `cam` (sem viewer) ignora sem erro. É APRESENTAÇÃO: não mexe em nada da física — e por isso também
        NÃO é reaplicado nos resets (`reaplicar` não passa por aqui).
        """
        cam, bloco = self.cam, registo.camera
        if cam is None or bloco is None:
            return
        assinatura = bloco.assinatura()
        if assinatura == self._assinatura_camera:
            return
        self._assinatura_camera = assinatura
        self.camera = bloco
        aplicar_camera(cam, bloco.valores())
        self.n_cameras += 1
        print(f"[sim] camera (3a pessoa) -> az {bloco.azimute:.1f} deg, elev {bloco.elevacao:.1f} deg, "
              f"distancia {bloco.distancia:.2f} m (seq {bloco.seq}) — alvo segue o drone", flush=True)

    def _aplica_degrau(self, env: HoverEnv, params: dict) -> None:
        """`frente` formato (a): degrau IMEDIATO do vento base, sem passar pelo validador do env.

        Desliga a camada dinâmica do env (para não ficar turbulência de um modo anterior a somar ao degrau)
        e escreve o vento base já: a física do passo seguinte leva com ele (é o `definir_vento`, o mesmo
        caminho do `vel`/`azimute`/`elevacao` do controlo — nada de forças mágicas).
        """
        env.definir_vento_dinamico(None)
        env.definir_vento(float(params["vel"]), float(params["azimute"]), float(params["elevacao"]))
        print(f"[sim] frente -> degrau imediato do vento base: {params['vel']:.2f} m/s @ "
              f"{params['azimute']:.1f} deg"
              + (f" (elev {params['elevacao']:+.1f} deg)" if params["elevacao"] else ""), flush=True)

    def _inicia_rajada(self, env: HoverEnv, din: Dinamico) -> None:
        """Arranca a rajada one-shot: vector dirigido + envelope `sin(pi·k/(N+1))` (o do env)."""
        p = din.params
        vetor = _vetor_vento(float(p["u"]), float(p["azimute"]), float(p["elevacao"]))
        self.rajada = {"u": float(p["u"]), "vec": vetor, "k": 0, "n": int(p["duracao"]),
                       "azimute": float(p["azimute"]), "elevacao": float(p["elevacao"])}
        print(f"[sim] rajada_agora -> u {p['u']:.2f} m/s @ {p['azimute']:.1f} deg (elev {p['elevacao']:+.1f}), "
              f"{p['duracao']} passos", flush=True)

    def passo_rajada(self, env: HoverEnv) -> bool:
        """Avança a rajada one-shot UM passo de decisão (venta BASE + rajada·envelope); `True` se escreveu.

        Chamado antes de cada `env.step` (o `env` escreve `opt.wind` no início do passo, a partir do vento
        base que aqui fica) — logo a física do passo já leva com a rajada. No fim do envelope volta ao vento
        base em vigor. Não mexe no modo dinâmico do env (composição: base+rajada+modo).
        """
        if self.rajada is None:
            return False
        self.rajada["k"] += 1
        if self.rajada["k"] > self.rajada["n"]:
            self.rajada = None
            self.rajada_concluida = True         # o modo em vigor volta a "nenhum" (a rajada já passou)
            self._aplica_base(env)
            print("[sim] rajada_agora terminou: volta ao vento base", flush=True)
            return True
        env_k = math.sin(math.pi * self.rajada["k"] / (self.rajada["n"] + 1.0))
        total = self._vetor_base() + self.rajada["vec"] * env_k
        env.definir_vento(*_polar_do_vetor(total))
        return True

    def cancelar_rajada(self, env: HoverEnv) -> None:
        """Corta a rajada one-shot e volta ao vento base em vigor.

        Usado quando o bloco dinâmico TROCA de modo com uma rajada a meio (o `rajada_agora` não sobrevive a
        outra ordem) e pelo `_para_dinamica` (PARAR). Um RESET de episódio também NÃO corta a rajada — ver
        `reaplicar`.
        """
        if self.rajada is None:
            return
        self.rajada = None
        self._aplica_base(env)

    def reaplicar(self, env: HoverEnv) -> None:
        """Volta a escrever o controlo EM VIGOR depois de um `env.reset` (transição de episódio invisível).

        O ficheiro de controlo é a FONTE: um reset não pode apagar o que o dono pediu. Reaplica o vento
        base, o modo dinâmico (degrau do `frente` incluído) e RE-ARMA uma rajada one-shot que tenha sido
        pedida e ainda não tenha corrido (ex.: foi pedida com a física parada ou caiu a meio de um reset) —
        sem isto, mexer no vento em tempo real "perdia-se" no reset seguinte. Uma rajada já CONCLUÍDA não
        volta a disparar (o `seq` novo no controlo é que manda).
        """
        self._aplica_base(env)
        din = self.dinamico
        if din is None or not din.ativo or din.modo == "nenhum":
            env.definir_vento_dinamico(None)
            return
        if din.modo == "rajada_agora":
            if self.rajada is None and not self.rajada_concluida:
                self._inicia_rajada(env, din)            # re-arma a rajada perdida
            return
        formato, params = _params_frente(din.params) if din.modo == "frente" else ("env", din.params)
        if formato == "base":
            self._aplica_degrau(env, params)
            return
        try:
            env.definir_vento_dinamico({"modo": din.modo, **params})
        except ValueError as erro:                       # já validado quando o bloco entrou: não deve correr
            self._aviso(f"vento dinamico '{din.modo}' recusado no reset: {erro}")

    def modo_efetivo(self) -> str:
        """Modo de vento dinâmico EM VIGOR agora (o que a telemetria publica em `vento_modo`).

        `rajada_agora` só enquanto a rajada one-shot está a decorrer: depois de terminar o modo em vigor é
        `nenhum` (o vento já voltou ao base), mesmo que o bloco do controlo continue a dizer `rajada_agora`.
        """
        if self.rajada is not None:
            return "rajada_agora"
        if self.dinamico is None or not self.dinamico.ativo:
            return "nenhum"
        if self.dinamico.modo == "rajada_agora":
            return "nenhum" if self.rajada_concluida else "rajada_agora"
        return self.dinamico.modo

    def _vetor_base(self) -> np.ndarray:
        """Vector do vento BASE em vigor (m/s, mundo) — o que a rajada one-shot soma."""
        r = self.ultimo
        if r is None or not r.ativo:
            return np.zeros(3)
        return _vetor_vento(r.vel, r.azimute, r.elevacao)

    def consumir_reinicio(self) -> bool:
        """`True` uma única vez por cada REINICIAR pedido (o pedido é limpo ao consumir)."""
        if not self.pedido_reinicio:
            return False
        self.pedido_reinicio = False
        self.n_reinicios += 1
        return True

    def _aviso(self, mensagem: str) -> None:
        """Aviso em stdout, uma vez por texto (um ficheiro inválido não inunda o terminal a 50 Hz)."""
        if mensagem not in self._avisos:
            self._avisos.add(mensagem)
            print(f"[sim] aviso: {mensagem}", flush=True)


# ---------------------------------------------------------------------------------------------- hooks MLP
class Sonda:
    """Forward hooks nos `nn.Linear` da política: `h1`/`h2` = 1.ª/2.ª camada escondida (pré-tanh).

    Mesma técnica (e mesma ordem) do `net_probe.py`: `mlp_extractor.policy_net` primeiro, `action_net` no fim.
    """

    def __init__(self, politica) -> None:
        self.saidas: dict[int, np.ndarray] = {}
        self._handles = []
        lineares = self._lineares(politica)
        if len(lineares) < 2:
            raise SystemExit(f"[sim] a política só tem {len(lineares)} camadas Linear (esperava 2 escondidas "
                             "+ a cabeça de ação) — a telemetria desenha h1/h2 da MLP [16, 64, 64, 4]")
        for i, camada in enumerate(lineares):
            self._handles.append(camada.register_forward_hook(self._hook(i)))

    @staticmethod
    def _lineares(politica) -> list:
        """Todos os `nn.Linear` na ordem política: primeiro `policy_net`, depois `action_net`."""
        if not hasattr(politica, "mlp_extractor") or not hasattr(politica.mlp_extractor, "policy_net"):
            raise SystemExit("[sim] a política não tem `mlp_extractor.policy_net` — só se sonda MlpPolicy")
        modulos = [m for m in politica.mlp_extractor.policy_net.modules() if m.__class__.__name__ == "Linear"]
        modulos += [m for m in politica.action_net.modules() if m.__class__.__name__ == "Linear"]
        return modulos

    def _hook(self, i: int):
        def guardar(_modulo, _entrada, saida):
            self.saidas[i] = np.asarray(saida.detach().cpu().numpy()[0])   # 1.ª amostra do batch
        return guardar

    def escondidas(self) -> tuple[np.ndarray, np.ndarray]:
        """`(h1, h2)` da última passagem; zeros (16→64) se ainda não houve forward."""
        ordem = sorted(self.saidas)
        if len(ordem) < 2:
            return np.zeros(64), np.zeros(64)
        return self.saidas[ordem[0]], self.saidas[ordem[1]]

    def limpar(self) -> None:
        """Esquece as ativações (chamado no reset: a 1.ª linha do episódio não mostra o forward anterior)."""
        self.saidas.clear()

    def fechar(self) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()


# ---------------------------------------------------------------------------------------------- telemetria
class Telemetria:
    """Escritor JSONL da telemetria: 1 linha por amostra, ~10 Hz (sempre — não há batimento lento) + eventos.

    Abre em modo `"a"` (cada arranque continua o ficheiro: o site vê o histórico todo) e escreve com `flush`
    para não haver atraso de buffer. `talvez_amostra` decide pelo relógio; `evento` escreve sempre (é o que
    marca o fim de um episódio sem esperar pelos 0,1 s).
    """

    def __init__(self, caminho: Path, truncar: bool = False) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._ficheiro = self.caminho.open("w" if truncar else "a", encoding="utf-8")
        self.n_linhas = 0
        self._t_ultima = 0.0

    def escrever(self, amostra: dict) -> None:
        """Uma linha JSON (chaves por ordem fixa) já com `flush`."""
        self._ficheiro.write(json.dumps(amostra, separators=(",", ":")) + "\n")
        self._ficheiro.flush()
        self.n_linhas += 1
        self._t_ultima = time.perf_counter()

    def talvez_amostra(self, amostra: dict, periodo: float = PERIODO_AMOSTRA) -> bool:
        """Escreve se já passou `periodo` desde a última linha; devolve se escreveu."""
        agora = time.perf_counter()
        if agora - self._t_ultima < periodo:
            return False
        self.escrever(amostra)
        return True

    def fechar(self) -> None:
        try:
            self._ficheiro.close()
        except OSError:
            pass


class GestorBateria:
    """Planta REAL: o pack FÍSICO persiste — entre REINICIARs (pousar e voltar a descolar não o carrega) e
    entre sessões (`out/bateria/<pack>.json`: desgaste + ciclo em curso + carga).

    `recarregar` fecha o ciclo (aplica o desgaste do `ModeloBateria.recarregar`: SoH, ciclos, R) e põe o pack
    a 100 %; `nova` troca por um pack NOVO (SoH 100 %, 0 ciclos). O SoC ESTIMADO é o que o RPi saberia:
    OCV medido em repouso no arranque/recarga + contagem de Coulomb com a corrente MEDIDA (monitor INA226)
    sobre a capacidade NOMINAL (o software de bordo não conhece o desgaste — por isso diverge do real
    quando o pack envelhece, como num drone a sério).
    """

    CAMPOS = ("soc", "v_rc", "temp", "soc_inicio", "ah_ciclo", "wh_ciclo", "t_ciclo", "soma_c_dt",
              "soma_t_dt", "i_pico", "v_min")

    def __init__(self, env: DroneRealEnv, pasta: Path = PASTA_BATERIA) -> None:
        from lab import drone_rpi as dr
        self.env = env
        self.dr = dr
        self.pack_id = env.hw.bateria.id
        self.caminho = Path(pasta) / f"{self.pack_id}.json"
        self.desgaste = dr.EstadoDesgaste.carregar(self.caminho, self.pack_id)
        env.planta.bat.desgaste = self.desgaste
        self.ciclo = None
        try:
            bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
            if bruto.get("pack_id") == self.pack_id and isinstance(bruto.get("ciclo"), dict):
                self.ciclo = {k: float(v) for k, v in bruto["ciclo"].items() if k in self.CAMPOS}
        except (OSError, ValueError, AttributeError):
            pass
        self.i_media = 0.0
        self.soc_estimado = 1.0
        self.ultimo_ciclo: dict | None = None

    def restaurar(self) -> None:
        """Depois do 1.º reset: repõe a carga/ciclo do pack guardados (se houver) e calibra o SoC estimado."""
        if self.ciclo:
            self.env._repor_bateria(self.ciclo)
        self._calibrar_estimativa()

    def _calibrar_estimativa(self) -> None:
        b = self.env.planta.bat
        s, v = b.b.celula.curva
        v_cel = self.env.planta.monitor.tensao / b.b.s or b.v_celula
        self.soc_estimado = float(np.interp(v_cel, v, s))      # OCV em repouso → SoC (curva invertida)

    def passo(self, dt: float) -> None:
        """A cada passo de decisão: média móvel da corrente (autonomia) e Coulomb com a corrente MEDIDA."""
        pl = self.env.planta
        self.i_media += 0.02 * (pl.i_total - self.i_media)
        cap = pl.bat.b.capacidade_ah * 3600.0
        self.soc_estimado = max(0.0, self.soc_estimado - pl.monitor.corrente * dt / cap)

    def gravar(self) -> None:
        b = self.env.planta.bat
        dados = {**self.desgaste.para_dict(), "ciclo": {k: float(getattr(b, k)) for k in self.CAMPOS},
                 "build": self.env.hw.nome, "gravado_em": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_name(f".{self.caminho.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.caminho)

    def comando(self, acao: str) -> dict:
        """`recarregar` (fecha o ciclo com desgaste) ou `nova` (pack novo). Grava sempre."""
        b = self.env.planta.bat
        if acao == "nova":
            self.desgaste = self.dr.EstadoDesgaste(pack_id=self.pack_id)
            b.desgaste = self.desgaste
            b.reiniciar(1.0)
            self.ultimo_ciclo = {"acao": "nova", "soh": 1.0}
        else:
            r = b.recarregar(1.0)
            self.ultimo_ciclo = {"acao": "recarregar", **{k: float(v) for k, v in r.items()}}
        self.env.planta.v_bus = b.v
        self.soc_estimado = 1.0
        self.gravar()
        return self.ultimo_ciclo

    def telemetria(self) -> dict:
        from lab.drone_rpi.componentes import v_pouso_celula
        pl = self.env.planta
        b = pl.bat
        t = b.telemetria(self.i_media if self.i_media > 0.05 else None)
        aut = t["autonomia_min"]
        t["autonomia_min"] = None if not math.isfinite(aut) else round(aut, 2)
        t.update({"soc_estimado": round(self.soc_estimado, 5), "s": b.b.s, "p_paralelo": b.b.p,
                  "quimica": b.b.quimica, "capacidade_ah": b.b.capacidade_ah, "pack_id": self.pack_id,
                  "v_pouso_celula": v_pouso_celula(b.b.celula), "v_corte_celula": b.b.celula.v_corte,
                  "v_medida": round(pl.monitor.tensao, 4), "i_medida": round(pl.monitor.corrente, 4),
                  "i_media": round(self.i_media, 4), "ultimo_ciclo": self.ultimo_ciclo})
        return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in t.items()}


def campos_planta_real(env: DroneRealEnv, gestor: GestorBateria | None) -> dict:
    """Campos ADITIVOS da telemetria na planta real (o site mostra-os nos blocos Bateria/Motores/Hardware)."""
    pl = env.planta
    m = pl.prop
    w_max = pl.omega_max_atual()
    t_max = pl.hw.kf * w_max ** 2
    t_max_cheia = pl.hw.empuxo_max(pl.hw.bateria.v_cheia)
    pw = pl.potencias()
    est = env.estimador
    return {
        "bateria": gestor.telemetria() if gestor is not None else pl.bat.telemetria(),
        "motores": {"rpm": _lista(m.omega * 60.0 / (2.0 * math.pi), 4), "duty": _lista(m.duty, 4),
                    "empuxo_n": _lista(m.empuxo, 4), "i_fase": _lista(m.i_fase, 4),
                    "omega_max_rpm": round(w_max * 60.0 / (2.0 * math.pi), 2), "t_max_n": round(t_max, 5),
                    "t_max_frac": round(t_max / t_max_cheia, 5) if t_max_cheia > 0 else None,
                    "armado": bool(m.armado), "brownout": bool(pl.brownout)},
        "potencia": {"motores": round(pw["motores"], 4), "eletronica": round(pw["eletronica"], 4),
                     "bec_perdas": round(pw["bec_perdas"], 4), "total": round(pw["total"], 4),
                     "consumidores_5v": {k: round(v, 4) for k, v in pw["consumidores_5v"].items()}},
        "aero": {"kappa_t": _lista(pl.kappa_t, 4), "altura_rotores": _lista(pl.altura_rotores, 4)},
        "estimador": {k: round(float(getattr(est, k)), PRECISAO) for k in
                      ("roll", "pitch", "psi", "h", "vz", "vx", "vy", "x", "y")},
    }


def _lista(vetor, n: int) -> list[float]:
    """Vector → lista JSON de `n` floats arredondados (zeros se o vector não tiver o tamanho esperado)."""
    a = np.asarray(vetor if vetor is not None else np.zeros(n), dtype=float).reshape(-1)
    if a.size != n:
        a = np.zeros(n)
    return [round(float(v), PRECISAO) for v in a]


def aplicar_camera(cam, valores: dict) -> None:
    """Escreve os valores de ORBITAR/zoom nos atributos de `cam` (`viewer.cam` ou o `.cam` de um falso).

    São 3 escritas (`azimuth`, `elevation`, `distance`) — e NUNCA o `lookat`: o alvo da câmara é SEMPRE o
    drone e só o `seguir_drone` o escreve (a cada frame). É por isso que o rato ainda pode orbitar/zoom
    entre comandos (estes 3 atributos) mas o PAN é sempre sobreposto pelo seguimento.
    """
    cam.azimuth = float(valores["azimute"])
    cam.elevation = float(valores["elevacao"])
    cam.distance = float(valores["distancia"])


def seguir_drone(cam, data) -> list[float] | None:
    """`cam.lookat = data.body(CAM_CORPO).xpos + CAM_OFFSET` — ALVO SEMPRE NO DRONE, a cada frame.

    É o seguimento TERCEIRA-PESSOA (só apresentação: não toca na física): a câmara orbita o drone e ele
    fica sempre ao centro da imagem, mesmo quando a física o leva (vento/empuxo) ou quando o rato faz PAN
    (o PAN é intencionalmente sobreposto por aqui). COLA EXACTA e determinística — o mesmo estado do corpo
    dá sempre o mesmo `lookat`, provável a 1e-9 no `teste_camera.py` §2 (uma suavização tipo jogo ficaria
    documentada aqui, com a sua constante, se algum dia for de preferir — hoje o contrato promete
    `camera.alvo` = `lookat` real = drone+offset SEM lag). Escreve o `lookat` elemento a elemento para
    servir quer o `np.ndarray` do `MjvCamera` quer uma lista de um objeto de teste. Sem `cam` (sem viewer)
    devolve `None` sem erro. Devolve o alvo escrito (3 floats) — é o que sai na telemetria.
    """
    if cam is None:
        return None
    corpo = data.body(CAM_CORPO)
    alvo = [float(corpo.xpos[i]) + float(CAM_OFFSET[i]) for i in range(3)]
    for i in range(3):
        cam.lookat[i] = alvo[i]
    return alvo


def camera_real(cam) -> dict | None:
    """`{azimute, elevacao, distancia, alvo:[x,y,z]}` da câmara REAL (`cam` = `viewer.cam`), ou `None`.

    É a 19.ª chave da telemetria (`"camera"`): o que o viewer está mesmo a mostrar — os ângulos/zoom
    incluem arrastos do rato feitos entre comandos e o `alvo` é o `lookat` REAL (= drone+offset, escrito a
    cada frame pelo `seguir_drone`). Sem câmara (sem viewer) devolve `None`, que vira `null` na linha: sem
    dados não se inventa câmara nenhuma.
    """
    if cam is None:
        return None
    alvo = cam.lookat
    return {"azimute": round(float(cam.azimuth), PRECISAO), "elevacao": round(float(cam.elevation), PRECISAO),
            "distancia": round(float(cam.distance), PRECISAO),
            "alvo": [round(float(alvo[i]), PRECISAO) for i in range(3)]}


def _vetor_vento(vel: float, azimute_graus: float, elevacao_graus: float) -> np.ndarray:
    """Vector de vento (m/s, frame mundo) da convenção do `env.definir_vento` (azimute 0° = +x)."""
    azim, elev = math.radians(azimute_graus), math.radians(elevacao_graus)
    return float(vel) * np.array([math.cos(elev) * math.cos(azim), math.cos(elev) * math.sin(azim),
                                  math.sin(elev)])


def _polar_do_vetor(v) -> tuple[float, float, float]:
    """`(vel, azimute, elevação)` em m/s e GRAUS do vector CARTESIANO (inversa de `_vetor_vento`)."""
    w = np.asarray(v, dtype=float).reshape(3)
    vel = float(np.linalg.norm(w))
    if vel == 0.0:
        return 0.0, 0.0, 0.0
    elevacao = round(float(np.degrees(np.arcsin(np.clip(w[2] / vel, -1.0, 1.0)))), 9)
    azimute = round(float(np.degrees(np.arctan2(w[1], w[0]))), 9) % AZIM_MAX
    return vel, azimute, elevacao


def _vento_polar(env: HoverEnv) -> tuple[float, float]:
    """`(vel, azimute)` em m/s e graus do vento ATIVO (`env.vento_atual`; azimute 0° → +x, 90° → +y)."""
    v = np.asarray(env.vento_atual, dtype=float).reshape(3)
    vel = float(np.linalg.norm(v))
    if vel == 0.0:
        return 0.0, 0.0
    return vel, round(float(np.degrees(np.arctan2(v[1], v[0]))), PRECISAO) % AZIM_MAX


# ---------------------------------------------------------------------------------------------- teclado
class Teclas:
    """Estado do `key_callback` do viewer: ESPAÇO pausa/retoma, Q/Esc fecha (nada mais — sem HUD)."""

    def __init__(self) -> None:
        self.pausa = False
        self.fechar = False

    def ao_teclar(self, tecla: int) -> None:
        if tecla == TECLA_ESPACO:
            self.pausa = not self.pausa
        elif tecla in (TECLA_Q, TECLA_ESC):
            self.fechar = True


# ---------------------------------------------------------------------------------------------- ciclo
@dataclass
class Estado:
    """Estado do rollout que a telemetria publica (uma linha por amostra)."""

    ep: int = 1
    retorno: float = 0.0
    completos: int = 0               # episódios já terminados nesta sessão
    fim_episodio: bool = False       # o episódio em curso FECHOU e não houve reinício (loop desligado):
    #                                  a física CONTINUA a integrar no estado em que ficou — nada de congelar
    pausado: bool = False
    loop: bool = False               # SEM REINÍCIO por omissão (2026-10-09); `--com-loop`/`loop:true` liga
    vento_modo: str = "nenhum"       # modo dinâmico EM VIGOR (para a telemetria): nenhum/rajadas/...
    obs: np.ndarray | None = None
    acao: np.ndarray | None = None
    h1: np.ndarray | None = None
    h2: np.ndarray | None = None
    info: dict | None = None


def amostra(env: HoverEnv, est: Estado, cam=None, gestor: GestorBateria | None = None) -> dict:
    """Uma linha de telemetria com as chaves (e a ordem) do contrato.

    `ctrl` é o comando FÍSICO que a ação produziu — `data.ctrl` = [empuxo N, mx, my, mz N·m], escrito pelo
    `env.aplicar_acao` — para o site não ter de o derivar da ação e o poder rotular "ctrl do backend".
    `cam` (o `viewer.cam`) traz a 19.ª chave, `"camera"`: a câmara REAL da janela (`null` sem viewer).
    Aditivo: as chaves antigas ficam na mesma ordem.

    INVARIANTE (a única que se promete): `ctrl == acao_para_ctrl(act)` nas linhas com AÇÃO APLICADA, ou seja
    `passo > 0` — são as que saem de um `env.step`, e o `data.ctrl` é exactamente o comando que a física usou.
    Nas linhas de ARRANQUE (a 1.ª do processo) e de REINÍCIO (episódio novo, `--com-loop`), que têm `passo == 0`
    e `t == 0`, vale `act == ctrl == [0, 0, 0, 0]`: o `env.reset()` zera o `data.ctrl` e ainda NÃO houve ação
    nenhuma. Aí a identidade NÃO se aplica — e não se inventa um `ctrl` que o simulador não aplicou: zeros é
    "nenhuma ação" (verdadeiro), enquanto `acao_para_ctrl([0,0,0,0])` = `[mg, 0, 0, 0]` = "ação nula" (o
    hover com 0,26487 N), que é outra coisa. Para separar as duas, basta `passo > 0`.
    """
    info = est.info if est.info else {}
    vento_vel, vento_azim = _vento_polar(env)
    real = isinstance(env, DroneRealEnv)
    linha = {
        "t": round(float(env.data.time), PRECISAO),
        "estado": "episodio_terminado" if est.fim_episodio else "a_correr",
        "loop": bool(est.loop),                         # modo em vigor (SEM REINÍCIO por omissão; aditivo)
        "ep": int(est.ep),
        "passo": int(env.passos),
        "retorno": round(float(est.retorno), PRECISAO),
        "z": round(float(info.get("z", 0.0)), PRECISAO),
        "dist_xy": round(float(info.get("dist_xy", 0.0)), PRECISAO),
        "yaw_err": round(float(info.get("yaw_err", 0.0)), PRECISAO),
        "vento_vel": round(vento_vel, PRECISAO),
        "vento_azim": round(vento_azim, PRECISAO),
        "vento_vec": _lista(env.vento_atual, 3),        # [vx, vy, vz] m/s — o vento que a física leva
        "vento_modo": str(est.vento_modo or "nenhum"),  # modo dinâmico em vigor (aditivo)
        "obs": (_lista(None if est.obs is None else np.asarray(est.obs)[:OBS_ATOR_DIM], OBS_ATOR_DIM)
                if real else _lista(est.obs, 16)),      # real: SÓ a parte do ator (sensores + estimação)
        "act": _lista(est.acao, 4),
        "ctrl": _lista(env.data.ctrl[:4] if real else env.data.ctrl, 4),   # real: empuxo de cada rotor (N)
        "h1": _lista(est.h1, 64),
        "h2": _lista(est.h2, 64),
        "camera": camera_real(cam),                 # 19.ª chave: câmara REAL da janela (null sem viewer)
        "planta": "real" if real else "cf2",        # aditivo: o site escolhe os blocos/rótulos certos
    }
    if real:
        linha.update(campos_planta_real(env, gestor))
    return linha


def _reiniciar(env: HoverEnv, est: Estado, sonda: Sonda, seed: int, ep: int | None = None,
               manter_bateria: bool = True) -> None:
    """`env.reset` (+ limpeza dos hooks) e volta ao estado "a correr"; `ep` só muda quando é episódio novo.

    Planta real: o pack MANTÉM-SE (SoC/temperatura/ciclo) — pousar e descolar de novo não carrega a bateria;
    só o comando `bateria` (recarregar/nova) a muda."""
    if isinstance(env, DroneRealEnv):
        est.obs, est.info = env.reset(seed=seed, options={"manter_bateria": bool(manter_bateria)})
    else:
        est.obs, est.info = env.reset(seed=seed)
    est.acao = np.zeros(4)
    est.h1, est.h2 = np.zeros(64), np.zeros(64)
    est.retorno = 0.0
    est.fim_episodio = False
    sonda.limpar()
    if ep is not None:
        est.ep = ep


def correr(env: HoverEnv, politica, controlo: Controlo, telemetria: Telemetria, sonda: Sonda, args,
          viewer=None, teclas: Teclas | None = None, gestor: GestorBateria | None = None) -> int:
    """Ciclo principal (serve a janela e o modo `--sem-janela`): passos de decisão a 50 Hz com o ritmo de
    `--fator-tempo`, leitura do controlo em cada passo e telemetria a ~10 Hz — SEMPRE, sem batimento lento.

    O fim de episódio NUNCA pára a física: com `loop` ligado (`--com-loop`/`loop:true`) faz reset e segue
    (ep+1, passo 0); sem `loop`
    continua a integrar no estado em que ficou (`estado = "episodio_terminado"`, retorno congelado no valor
    do episódio) até um REINICIAR explícito. Os únicos casos sem `env.step` são a PAUSA pelo ESPAÇO (ação
    explícita na janela) e os `break` de `--max-segundos`/`--max-episodios` (flags explícitas).

    Devolve 0. `viewer=None` → sem janela (nenhum import de GLFW/GL é feito aqui). Um `viewer` falso (testes)
    só precisa de `sync()`, `is_running()`, `lock()`, `m`, `viewport` e — para a câmara terceira-pessoa —
    `cam` (o ORBITAR/zoom escreve-se nos atributos `.cam` e o `lookat` segue o drone a cada frame, ver
    `seguir_drone`; sem `.cam` a câmara ignora-se e a telemetria publica
    `null`). Nunca se toca no texto/figuras.
    """
    est = Estado(loop=loop_do_arranque(args))           # CLI autoritativo no arranque (ver `fixar_loop`)
    # CÂMARA (só apresentação, TERCEIRA-PESSOA): o ALVO é SEMPRE o drone — `seguir_drone` escreve o
    # `lookat` a cada frame (= `body(CAM_CORPO).xpos + CAM_OFFSET`), antes de cada `viewer.sync` e de cada
    # linha de telemetria. O ARRANQUE do ORBITAR/zoom é explícito: aplica-se `CAM_PADRAO` (os valores de
    # `mjv_defaultFreeCamera`, sem alvo) antes de qualquer amostra. Sem viewer (ou sem `.cam`) ignora-se
    # tudo sem erro; depois, cada comando do controlo aplica os 3 valores UMA VEZ por mudança de assinatura
    # (ver `Controlo._aplica_camera`) e o rato fica livre entre comandos (orbitar/zoom sobrevivem; o PAN é
    # sobreposto pelo seguimento).
    cam = getattr(viewer, "cam", None)
    controlo.ligar_camera(cam)
    controlo.aplicar_padrao()                          # CAM_PADRAO no arranque (conta como aplicação)
    _reiniciar(env, est, sonda, args.seed, ep=1, manter_bateria=False)
    if gestor is not None:
        gestor.restaurar()                             # o pack continua com a carga/ciclo da sessão anterior
        est.obs = env.observacao()
        est.info = env._info()
    t_gravar = time.perf_counter()
    # ANIMAÇÃO VISUAL das hélices (só apresentação, FORA do `mj_step`): a pose dos 4 geoms é reescrita antes
    # de cada render a partir do wrench comandado — no-op se o modelo não tiver as hélices (`--sem-helices`).
    helices = cf.Helices(env.model)

    def publica() -> dict:
        """Linha de telemetria com o seguimento 3.ª-pessoa já atualizado (`camera.alvo` = drone+offset)."""
        seguir_drone(cam, env.data)
        return amostra(env, est, cam, gestor)

    telemetria.escrever(publica())                              # linha de evento do arranque
    print(f"[sim] rollout: ep 1 comecou (seed {args.seed}, vento {_vento_polar(env)[0]:.2f} m/s); "
          + ("CONTINUO: no fim do episodio reinicia sozinho (ep+1, passo 0)"
             if est.loop else
             "SEM REINICIO (loop desligado): no fim do episodio a fisica CONTINUA no estado em que ficou; "
             "so um REINICIAR recomeca"), flush=True)
    proximo = time.perf_counter()
    t_ini = proximo
    terminar = False

    def parar(*_args):
        nonlocal terminar
        terminar = True

    for sinal in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sinal, parar)
        except ValueError:                               # não estamos na main thread: sem sinais
            pass

    while not terminar:
        if teclas is not None:
            if teclas.fechar:
                break
            est.pausado = bool(teclas.pausa)
        if viewer is not None and not viewer.is_running():
            break

        # 1) controlo do site: vento + REINICIAR + modo loop (a cada passo de decisão, como o dashboard)
        registo = controlo.verifica(env)
        if registo is not None and registo.loop is not None:
            est.loop = bool(registo.loop)
            print(f"[sim] loop {'ligado (continuo)' if est.loop else 'desligado (sem reinicio)'} pelo controlo",
                  flush=True)
        if controlo.consumir_reinicio():
            novo_ep = est.ep + 1 if (env.passos > 0 or est.fim_episodio) else est.ep
            _reiniciar(env, est, sonda, args.seed + novo_ep - 1, ep=novo_ep)
            controlo.reaplicar(env)                      # o reset não apaga o que o dono pediu
            est.vento_modo = controlo.modo_efetivo()
            telemetria.escrever(publica())                    # evento: episódio novo, passo 0
            print(f"[sim] REINICIAR: ep {est.ep} comecou (passo 0, retorno 0)", flush=True)
        est.vento_modo = controlo.modo_efetivo()         # o modo em vigor já vai nesta amostra
        acao_bateria = controlo.consumir_bateria()
        if acao_bateria is not None:
            if gestor is None:
                print("[sim] comando de bateria ignorado: esta planta (cf2) não tem bateria", flush=True)
            else:
                r = gestor.comando(acao_bateria)
                est.obs = env.observacao()
                telemetria.escrever(publica())               # evento imediato: o site vê o pack novo
                print(f"[sim] BATERIA: {acao_bateria} — SoH {100 * gestor.desgaste.soh:.2f} % · "
                      f"{gestor.desgaste.ciclos_eq:.2f} ciclos eq. · {r}", flush=True)
        if gestor is not None and time.perf_counter() - t_gravar > 30.0:
            gestor.gravar()                                  # o pack sobrevive a um fecho abrupto
            t_gravar = time.perf_counter()

        # 2) em PAUSA (ESPAÇO na janela) não há física: janela viva + telemetria a ~10 Hz. O fim do episódio
        #    NÃO cai aqui: sem `loop` a física continua a integrar (é o requisito do dono).
        if est.pausado:
            helices.atualizar(env.model, env.data, 0.0)       # pausa: sem tempo → hélices congeladas
            if viewer is not None:
                seguir_drone(cam, env.data)                   # 3.ª pessoa: alvo no drone, a cada frame
                viewer.sync()
            telemetria.talvez_amostra(publica(), PERIODO_AMOSTRA)
            if args.max_segundos and time.perf_counter() - t_ini >= args.max_segundos:
                print("[sim] --max-segundos atingido", flush=True)
                break
            time.sleep(PERIODO_OCIO)
            proximo = time.perf_counter()
            continue

        # 3) passo de decisão: rede -> ação -> física (10 passos de física a 500 Hz)
        controlo.passo_rajada(env)                       # rajada one-shot: base+envelope DESTE passo
        try:
            acao, _estado = politica.predict(est.obs, deterministic=True)
            est.acao = np.asarray(acao, dtype=float).reshape(4)
            est.h1, est.h2 = sonda.escondidas()
            est.obs, recompensa, terminado, truncado, est.info = env.step(est.acao)
        except RuntimeError as erro:                     # sanidade do HoverEnv: estado divergiu
            print(f"[sim] a simulacao divergiu ({erro}) — use definir_vento com um valor sao pelo site",
                  file=sys.stderr, flush=True)
            return 1
        if gestor is not None:
            gestor.passo(env.dt_decisao)                 # corrente média + SoC estimado (Coulomb medido)
        if not est.fim_episodio:                         # com o episódio fechado sem reinício não se somam
            est.retorno += float(recompensa)             # recompensas de um episódio que já acabou
        telemetria.talvez_amostra(publica())
        if terminado or truncado:
            fim = f"ep {est.ep} terminou"
            if not est.fim_episodio:                     # 1.ª vez que se vê o fim DESTE episódio
                motivo = "caiu/capotou" if terminado else "tempo"
                est.fim_episodio = True
                est.completos += 1
                fim = f"ep {est.ep} terminou ({motivo}, retorno {est.retorno:+.3f})"
                if args.max_episodios and est.completos >= args.max_episodios:
                    print(f"[sim] {fim} -> --max-episodios {args.max_episodios} atingido (nao arranca outro)",
                          flush=True)
                    break
                if not est.loop:                         # SEM REINÍCIO: a física continua, ninguém reinicia
                    telemetria.escrever(publica())               # evento imediato (não espera pelos 0,1 s)
                    print(f"[sim] {fim} - loop desligado (SEM REINICIO): a fisica CONTINUA no estado em que "
                          "ficou; so um REINICIAR recomeca", flush=True)
            if est.loop:                                 # CONTÍNUO (`--com-loop`/`loop:true`)
                print(f"[sim] {fim} -> auto-reset continuo (ep {est.ep + 1}, passo 0)", flush=True)
                _reiniciar(env, est, sonda, args.seed + est.ep, ep=est.ep + 1)
                controlo.reaplicar(env)                  # a transição é INVISÍVEL: o controlo volta a valer
                est.vento_modo = controlo.modo_efetivo()
                telemetria.escrever(publica())
        helices.atualizar(env.model, env.data, env.dt_decisao)   # animação VISUAL (fora do `mj_step`)
        if viewer is not None:
            seguir_drone(cam, env.data)                           # 3.ª pessoa: alvo no drone, a cada frame
            viewer.sync()

        # 4) ritmo: 1 passo de decisão por dt_decisao/fator_tempo (0 = sem travão, o mais rápido possível)
        if args.fator_tempo > 0.0:
            proximo += env.dt_decisao / args.fator_tempo
            resto = proximo - time.perf_counter()
            if resto > 0:
                time.sleep(resto)
            else:
                proximo = time.perf_counter()
        if args.max_segundos and time.perf_counter() - t_ini >= args.max_segundos:
            print("[sim] --max-segundos atingido", flush=True)
            break
    print(f"[sim] fim: {telemetria.n_linhas} linhas de telemetria em {telemetria.caminho}", flush=True)
    return 0


def esperar_fecho(viewer, limite: float = 2.0) -> float:
    """Espera que a thread do viewer termine antes de o processo sair; devolve os segundos esperados.

    Medido nesta máquina (mujoco 3.15, KDE Wayland): sair logo a seguir a fechar a janela corre o
    `glfw.terminate()` do `atexit` AO MESMO TEMPO que a thread do viewer destroi o contexto GLFW — SIGSEGV
    intermitente no FIM do processo. Esperar que o `Handle` perca a referência ao simulador elimina a
    corrida; o limite garante que isto nunca pendura.
    """
    t0 = time.perf_counter()
    while getattr(viewer, "m", None) is not None and time.perf_counter() - t0 < limite:
        time.sleep(0.05)
    return time.perf_counter() - t0


def correr_com_janela(env: HoverEnv, politica, controlo: Controlo, telemetria: Telemetria, sonda: Sonda,
                      args, gestor: GestorBateria | None = None) -> int:
    """Abre a janela LIMPA (`show_left_ui=False`, `show_right_ui=False`, zero overlay) e corre o ciclo."""
    from mujoco import viewer as mjviewer  # import tardio: o modo --sem-janela não carrega GLFW/GL

    teclas = Teclas()
    viewer = None
    try:
        with mjviewer.launch_passive(env.model, env.data, key_callback=teclas.ao_teclar,
                                     show_left_ui=False, show_right_ui=False) as viewer:
            viewer.clear_texts()                         # garante zero overlay (nunca se usa set_texts)
            return correr(env, politica, controlo, telemetria, sonda, args, viewer=viewer, teclas=teclas,
                          gestor=gestor)
    except KeyboardInterrupt:
        return 0
    finally:
        if viewer is not None:
            esperar_fecho(viewer)


# ---------------------------------------------------------------------------------------------- CLI
def _fator_de_tempo(texto: str) -> float:
    """`--fator-tempo` → float finito ≥ 0 (0 = sem travão, 1 = tempo real)."""
    try:
        valor = float(str(texto).strip())
    except ValueError as erro:
        raise argparse.ArgumentTypeError(f"esperado um número (recebido {texto!r})") from erro
    if not math.isfinite(valor) or valor < 0.0:
        raise argparse.ArgumentTypeError(f"tem de ser finito e ≥ 0 (recebido {texto!r}; 0 = sem travão)")
    return valor


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
    """Política da PLANTA REAL (o drone do dono) — tem precedência: `out/real_*/{final,best_model}.zip` com o
    `hardware.json` ao lado (as peças com que foi treinada), o mais recente; `None` se ainda não há."""
    candidatos = [p for p in list(out.glob("real_*/final.zip")) + list(out.glob("real_*/best_model.zip"))
                  if (p.parent / "hardware.json").is_file()]
    melhor = _mais_recente(p for p in candidatos if p.name == "final.zip") or _mais_recente(candidatos)
    if melhor is None:
        return None
    return melhor, f"planta REAL ({melhor.parent.name}/{melhor.name} + hardware.json)"


def ambiente_para(politica, caminho: Path, sem_helices: bool = False):
    """(env, gestor) certos para a política: planta REAL se for o ator-crítico assimétrico (`_n_ator`),
    com o build/modo de ação do `hardware.json` do modelo; senão o `HoverEnv` histórico do Crazyflie."""
    global CAM_CORPO, CAM_PADRAO
    if hasattr(politica.policy, "_n_ator"):
        from env_real import build_do_hardware
        hw_json = Path(caminho).parent / "hardware.json"
        dados = json.loads(hw_json.read_text(encoding="utf-8")) if hw_json.is_file() else {}
        build, motivo = build_do_hardware(dados)
        print(f"[sim] peças da política: {motivo}", flush=True)
        env = DroneRealEnv(build=build, modo_acao=dados.get("modo_acao", "ctbr"), aleatorizar=False)
        CAM_CORPO = "drone"
        CAM_PADRAO = camera_padrao_do_modelo(env.model)
        return env, GestorBateria(env)
    return HoverEnv(helices=not sem_helices), None


def camera_padrao_do_modelo(model) -> dict:
    """Valores de `mjv_defaultFreeCamera(model)` (orbitar/zoom de arranque) no formato do contrato."""
    import mujoco
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, cam)
    return {"azimute": float(cam.azimuth) % 360.0, "elevacao": float(cam.elevation),
            "distancia": float(cam.distance)}


def modelo_por_omissao() -> tuple[Path, str]:
    """`(caminho, motivo)` do modelo por omissão — a ordem de preferência é a MESMA do `sim_site.py`.

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
    raise SystemExit(f"[sim] nenhum modelo em {out} (avaliacao_vento/*.json, vento_*/final.zip, "
                     "runs/*/final.zip, best_model.zip) — treine primeiro (train.py) ou indique --model "
                     "CAMINHO")


def carregar_politica(caminho: Path):
    """PPO do Stable-Baselines3 em CPU; `SystemExit` com mensagem clara se o ficheiro não for um zip de PPO."""
    from stable_baselines3 import PPO
    try:
        return PPO.load(str(caminho), device="cpu")
    except Exception as erro:
        raise SystemExit(f"[sim] não consegui carregar {caminho} como PPO do Stable-Baselines3: {erro}") from erro


def analisar_argumentos(argv=None) -> argparse.Namespace:
    """Argumentos do runner (o modelo por omissão é descoberto em `out/runs/*/`)."""
    p = argparse.ArgumentParser(
        description="Runner da simulação do hover: janela MuJoCo 100% limpa (sem HUD nem figuras) + "
                    "telemetria JSONL para o site; o vento e o REINICIAR chegam pelo ficheiro de controlo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Teclado (foco na janela): ESPACO pausa/retoma · Q ou Esc fecha.\n"
            "\n"
            "Ficheiros: --controlo {\"vel\",\"azimute\",\"elevacao\",\"ativo\",\"reiniciar\",\"loop\",\"t\",\n"
            "\"dinamico\",\"camera\"} (lido a cada passo de decisão) e --telemetria JSONL a ~10 Hz, sempre\n"
            "(não há batimento lento). `dinamico` = {modo: nenhum|rajadas|aleatoria|frente|dryden|rajada_agora, params,\n"
            "ativo, seq}: `rajadas` = {p,duracao,u_max} e `aleatoria` = {p,duracao} (direção e força\n"
            "re-sorteadas a cada rajada em 0–5 m/s, 0–360° e ±90°, misturadas com o vento base pelo envelope);\n"
            "`frente` aceita {vel,azimute,elevacao} (degrau IMEDIATO do vento base) ou {u_max,t_s} (degrau em\n"
            "curso do env); `rajada_agora` = {u,azimute,elevacao,duracao} (one-shot dirigido).\n"
            "`camera` = {azimute,elevacao,distancia,seq} (SEM alvo): a CÂMARA da janela 3D é TERCEIRA-\n"
            "PESSOA — o alvo (lookat) segue SEMPRE o drone a cada frame (body(cf2).xpos + offset constante)\n"
            "e o bloco manda só no ORBITAR/zoom, aplicado UMA VEZ por mudança de assinatura (seq+valores) —\n"
            "entre comandos o rato orbita/zoom livre (o PAN é sobreposto pelo seguimento); sem viewer\n"
            "ignora-se sem erro.\n"
            "\n"
            "LOOP: o padrão é SEM REINÍCIO (pedido do dono, 2026-10-09): no fim do episódio a física CONTINUA\n"
            "a integrar no estado em que ficou (nunca reinicia sozinha e nunca congela) e só um REINICIAR\n"
            "recomeça. `--com-loop` (alias `--loop`) liga o CONTÍNUO — no fim do episódio reinicia sozinho,\n"
            "ep+1, sem congelar; o `--sem-loop` é o mesmo que a omissão (explícito e idempotente). O ARRANQUE\n"
            "É AUTORITATIVO nos dois sentidos: a flag vence o que estiver no ficheiro de controlo (`loop:\n"
            "true` velho é corrigido para `false` e vice-versa), para o site mostrar o estado verdadeiro;\n"
            "um `POST /api/loop` feito DURANTE o arranque vence sempre (o site carimba a escrita de arranque\n"
            "e o runner respeita o que já não tiver esse carimbo). Depois disso quem o muda é o POST\n"
            "/api/loop do site — a semântica é sticky. Escritas parciais no controlo (sem\n"
            "`loop`/`reiniciar`) não mexem nesses campos."
        ),
    )
    p.add_argument("--model", type=Path, default=None,
                   help="modelo do Stable-Baselines3 (.zip); por omissão, por ordem: o modelo da última "
                        "validação com sucesso (out/avaliacao_vento/*.json) -> vento_*/final.zip mais recente "
                        "(sem _seed) -> vento_*_seed*/final.zip -> runs/*/final.zip -> best_model.zip")
    p.add_argument("--sem-janela", action="store_true",
                   help="rollout SEM viewer (nenhum import de mujoco.viewer/glfw): escreve a telemetria e o "
                        "vento/REINICIAR funcionam na mesma — é o modo dos testes")
    p.add_argument("--sem-helices", action="store_true",
                   help="desliga a ANIMAÇÃO VISUAL das hélices (por omissão as 4 hélices giram na janela 3D, "
                        "com velocidade proporcional ao empuxo comandado de cada rotor). Não muda NADA da "
                        "física: com a animação a simulação dá exactamente o mesmo (run.py §10)")
    p.add_argument("--controlo", type=Path, default=CONTROLO_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro JSON de controlo (vento + reiniciar + loop); padrão: {CONTROLO_OMISSAO}")
    p.add_argument("--telemetria", type=Path, default=TELEMETRIA_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro JSONL de telemetria (~10 Hz); padrão: {TELEMETRIA_OMISSAO}")
    p.add_argument("--fator-tempo", type=_fator_de_tempo, default=FATOR_TEMPO_OMISSAO, metavar="F",
                   help="ritmo do rollout: 1 = tempo real (PADRÃO), 2 = 2x mais rápido, 0.5 = metade, "
                        "0 = sem travão (o mais rápido possível)")
    grupo_loop = p.add_mutually_exclusive_group()
    grupo_loop.add_argument("--com-loop", "--loop", dest="com_loop", action="store_true",
                            help="CONTÍNUO: auto-reset no fim de cada episódio (ep+1, passo 0). NÃO é o "
                                 "padrão; é AUTORITATIVO no arranque e vence um `loop: false` velho do "
                                 "ficheiro, que fica corrigido para `true` (o site mostra o estado "
                                 "verdadeiro) — mas nunca reverte um `POST /api/loop` do dono feito "
                                 "durante o arranque. `--loop` é o alias antigo desta flag")
    grupo_loop.add_argument("--sem-loop", action="store_true",
                            help="SEM REINÍCIO (já é o PADRÃO; a flag fica aceite como pedido explícito e "
                                 "idempotente): no fim do episódio a física CONTINUA no estado em que ficou "
                                 "(nunca reinicia sozinha e nunca congela) e só um REINICIAR (do site) "
                                 "recomeça. No arranque vence um `loop: true` velho do ficheiro, que é "
                                 "corrigido para `false` (o site passa a mostrar o estado verdadeiro) — mas "
                                 "nunca reverte um `POST /api/loop` do dono feito durante o arranque")
    p.add_argument("--seed", type=int, default=0,
                   help="semente do reset — o episódio N usa seed + N - 1 (padrão: 0)")
    p.add_argument("--max-segundos", type=float, default=0.0, metavar="S",
                   help="sai (exit 0) ao fim de S segundos de relógio; 0 = sem limite (padrão: 0)")
    p.add_argument("--max-episodios", type=int, default=0, metavar="N",
                   help="sai (exit 0) quando o episódio N acabar; 0 = sem limite (padrão: 0)")
    p.add_argument("--truncar-telemetria", action="store_true",
                   help="começa a telemetria do zero (por omissão o ficheiro é continuado, em modo append)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    """Carrega o modelo e a política e entra no ciclo (janela limpa ou `--sem-janela`)."""
    args = analisar_argumentos(argv)
    if args.model is not None:
        caminho, motivo = args.model, "explicito (--model)"
    else:
        caminho, motivo = modelo_por_omissao()          # diz SEMPRE qual escolheu e porquê
    if not caminho.is_file():
        raise SystemExit(f"[sim] modelo inexistente: {caminho}")
    politica = carregar_politica(caminho)
    env, gestor = ambiente_para(politica, caminho, args.sem_helices)   # planta real ou cf2, pela política
    # ARRANQUE AUTORITATIVO (pedido do dono, 2026-10-09): quem decide o `loop` é o CLI — `--com-loop` liga o
    # contínuo, a omissão e o `--sem-loop` arrancam SEM REINÍCIO — e o ficheiro de controlo é corrigido para
    # dizer o mesmo (o site mostra o estado verdadeiro; semântica sticky: depois só o `POST /api/loop` muda).
    # O `correr` lê a decisão do próprio CLI (`loop_do_arranque`), por isso uma falha a escrever o ficheiro
    # não muda o modo do rollout. Só depois disto é que o vigia lê a linha de base (contador e modo).
    # `token_do_arranque()` é o handshake com o site: se ele já escreveu o ficheiro e me passou o token, um
    # `loop` que já não tenha esse carimbo foi mudado por um POST durante esta janela — e o `fixar_loop`
    # respeita-o (nunca o reverte; ver o docstring dele).
    loop_inicial = loop_do_arranque(args)
    corrigido = fixar_loop(args.controlo, loop_inicial, token_do_arranque())
    controlo = Controlo(args.controlo)
    telemetria = Telemetria(args.telemetria, truncar=args.truncar_telemetria)
    sonda = Sonda(politica.policy)
    modo = "--sem-janela (sem viewer)" if args.sem_janela else (
        "janela limpa (show_left_ui=False, show_right_ui=False, sem set_texts/set_figures)")
    ritmo = f"{args.fator_tempo:g}x o tempo real" if args.fator_tempo > 0 else "sem travao (o mais rapido)"
    print(f"[sim] modelo: {caminho} ({motivo})")
    if gestor is not None:
        print(f"[sim] planta REAL: build '{env.hw.nome}' · {env.massa * 1000:.0f} g · ação {env.modo_acao} · "
              f"pack {gestor.pack_id} (SoH {100 * gestor.desgaste.soh:.2f} %, {gestor.desgaste.ciclos_eq:.2f} "
              f"ciclos eq.; estado em {_relativo(gestor.caminho)})", flush=True)
    print(f"[sim] controlo: {_relativo(args.controlo)} | telemetria: {_relativo(args.telemetria)}")
    if corrigido:
        print(f"[sim] controlo: `loop` fixado em {loop_inicial} "
              f"({'--com-loop' if loop_inicial else 'arranque SEM REINICIO (padrao; --sem-loop)'} vence o "
              "valor velho do ficheiro)", flush=True)
    print(f"[sim] modo: {modo} | ritmo: {ritmo} | "
          f"loop: {'ligado (continuo)' if loop_inicial else 'desligado (SEM REINICIO: fisica continua)'}",
          flush=True)
    if gestor is not None:                             # planta real: discos de hélice, sem animação visual
        print("[sim] helices: discos visuais da planta real (sem animacao; a rotacao REAL de cada motor — "
              "omega/rpm da propulsao — sai na telemetria e no painel dos motores)", flush=True)
    else:
        print("[sim] helices: "
              + ("SEM animacao (--sem-helices): a malha das helices fica como no upstream"
                 if args.sem_helices else
                 f"animacao VISUAL ligada — |omega| = {cf.ESCALA_VISUAL:.1f}·sqrt(t_i) rad/s "
                 f"({cf.REVOLUCOES_VISUAIS:g} rev/s no empuxo maximo por rotor, ~1/100 da rotacao real; "
                 "fora do mj_step, a fisica nao muda)"), flush=True)
    try:
        if args.sem_janela:
            return correr(env, politica, controlo, telemetria, sonda, args, gestor=gestor)
        return correr_com_janela(env, politica, controlo, telemetria, sonda, args, gestor=gestor)
    finally:
        if gestor is not None:
            gestor.gravar()
        sonda.fechar()
        telemetria.fechar()


def _relativo(caminho: Path) -> str:
    """Caminho relativo à raiz do laboratório quando possível (leitura mais curta nos logs)."""
    try:
        return str(Path(caminho).relative_to(_RAIZ))
    except ValueError:
        return str(caminho)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # `stdout` fechou do outro lado (ex.: `| head`): sair sem traceback e sem o aviso de flush
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
