#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/sim_view.py — runner da simulação: janela MuJoCo LIMPA + telemetria JSONL.

Uma janela e mais nada: `mujoco.viewer.launch_passive` com `show_left_ui=False, show_right_ui=False` e ZERO
overlay (nunca se chama `set_texts`/`set_figures`; `clear_texts()` no arranque garante o ecrã limpo). Toda a
informação — métricas, vento, reiniciar, loop — vive no SITE (`sim_site.py` + `site/dist/`), que fala com
este processo por DOIS FICHEIROS:

  · CONTROLO (o site escreve, sempre atómico tmp+os.replace)
      out/controle_vento.json = {"vel": 0..5, "azimute": 0..360, "elevacao": -90..90, "ativo": bool,
                                 "reiniciar": int, "loop": bool, "t": float}
    Lido a CADA passo de decisão (assinatura mtime_ns+tamanho: um ficheiro reescrito é sempre visto):
      - vento → `env.definir_vento(vel, azimute, elevacao)` (com `ativo: false` → vento 0);
      - `reiniciar` → contador; quando MUDA é um REINICIAR (1.º contador visto é linha de base; um contador
        ≥ 1 que apareça sem ficheiro prévio é um REINICIAR já pedido — mesma regra do net_probe/dashboard);
      - `loop` → `true` (PADRÃO desde a ronda 7) mantém o rollout CONTÍNUO: no fim do episódio faz reset e
        segue (ep+1, passo 0) sem congelar nem pedir nada; `false` é opt-in e volta ao comportamento antigo
        (a física PARA e só um REINICIAR retoma). Campo ausente = não mexe; `--sem-loop` no CLI é o mesmo.
  · TELEMETRIA (escrita AQUI, ~10 Hz = 1 linha JSON por amostra; 1 Hz com o episódio parado)
      out/sim_telemetria.jsonl = {"t","estado","loop","ep","passo","retorno","z","dist_xy","yaw_err",
                                  "vento_vel","vento_azim","vento_vec","vento_modo","obs":[16],"act":[4],
                                  "ctrl":[4],"h1":[64],"h2":[64]}
    `t` = tempo de SIMULAÇÃO do episódio (s, volta a 0 em cada reset); `estado` = "a_correr" |
    "episodio_terminado" (este SÓ com `loop: false` e o episódio acabado — com o contínuo a transição é
    invisível e o estado mantém-se "a_correr"); `loop` = modo em vigor no runner (aditivo); `obs`/`act`/`ctrl`
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
`nenhum | rajadas | frente | dryden | rajada_agora`:
  · `rajadas`/`dryden` → `env.definir_vento_dinamico({modo, **params})` (os MESMOS modos e a mesma
    validação do treino: `p`/`duracao`/`u_max`, `sigma`/`L`/`u_max`/`v_min`); `u_max = 0` fica inerte.
    Trocar de modo/ligar/desligar é imediato (o env re-planeia o resto do episódio);
  · `frente` aceita DOIS formatos de `params` (contrato final): (a) `vel`/`azimute`/`elevacao` = degrau
    IMEDIATO do vento base (`definir_vento`, validado com as faixas do vento base, sem passar pelo
    `env.valida_vento_dinamico`) — é o que o site manda quando o dono muda o vento no modo `frente`;
    (b) `u_max`/`t_s` = degrau em curso do env, ao instante `t_s` do modo, como sempre;
  · `rajada_agora` → rajada DIRIGIDA one-shot (o env não tem rajadas dirigidas): `params` = `u` [0, 5] m/s,
    `azimute` [0, 360)°, `elevacao` ±90°, `duracao` (passos de decisão, 25 por omissão). O envelope é
    `sin(π·k/(N+1))` — o MESMO do modo `rajadas` do env — somado ao vento base em vigor e escrito no
    `opt.wind` passo a passo com `definir_vento` (nada de forças mágicas); no fim volta ao vento base;
  · `nenhum` (ou `ativo: false`) → inerte: `definir_vento_dinamico(None)` e a rajada em curso é cortada (o
    vento base em vigor mantém-se). O campo `"vel"/"azimute"/"elevacao"` continua a mandar no vento BASE e
    pode mudar a qualquer instante, com ou sem dinâmica.
A assinatura do bloco (`modo`+`params`+`ativo`+`seq`) evita re-disparos: reescrever o ficheiro com o mesmo
bloco não faz nada — o site incrementa o `seq` quando quer disparar outra rajada igual. A telemetria mostra
`vento_vec` (vx,vy,vz m/s, o vento que a física leva) e `vento_modo` (modo em vigor) em cada amostra.

CONTÍNUO POR OMISSÃO (ronda 7, preferência do dono): quando o episódio termina (`terminated` OU `truncated`)
faz reset e SEGUE — ep+1, passo 0 — sem congelar, sem mensagem de erro e sem pedir nada. A transição é
INVISÍVEL para quem trabalha: o vento base, o modo dinâmico e uma rajada one-shot a meio ATRAVESSAM o reset
(`Controlo.reaplicar` volta a escrever o controlo em vigor logo depois do `env.reset`, porque o ficheiro de
controlo é a fonte); o `seq` do bloco dinâmico não muda, logo nada é re-disparado por engano.
`loop: false` no controlo (ou `--sem-loop`) é OPT-IN e mantém o comportamento antigo: a física PARA no fim do
episódio, o estado passa a "episodio_terminado" e só um REINICIAR do site retoma (o processo continua vivo:
lê o controlo, mantém a janela a responder e escreve um batimento por segundo na telemetria). O contador
`reiniciar` funciona em QUALQUER estado — é um reset manual, mesmo com o episódio a correr.

    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_view.py                    # janela limpa
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_view.py --fator-tempo 0.5  # metade da velocidade
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_view.py --sem-janela --max-segundos 20
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py                    # 1 comando: janela + site

Teclado (foco na janela): ESPAÇO pausa/retoma · Q ou Esc fecha. Não há mais teclas: o vento e o REINICIAR
são do site (é o que mantém a janela 100% limpa).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

# Ordem intencional (por isso o I001 fica desligado nesta linha): o `mjkit` define MUJOCO_GL=egl ANTES de
# `import mujoco`. O viewer (GLFW) não depende disso — ver o cabeçalho do `lab/mjkit.py`.
from lab import mjkit  # noqa: F401, I001
from env import HoverEnv

import numpy as np

# ---------------------------------------------------------------------------------------------- constantes
CONTROLO_OMISSAO = _AQUI / "out" / "controle_vento.json"
TELEMETRIA_OMISSAO = _AQUI / "out" / "sim_telemetria.jsonl"
FATOR_TEMPO_OMISSAO = 1.0        # 1 = tempo real; 0 = sem travão (o mais rápido possível); 2 = 2x mais rápido
PERIODO_AMOSTRA = 0.1            # s — cadência da telemetria a correr (~10 Hz)
PERIODO_PARADO = 1.0             # s — cadência com o episódio terminado (batimento, o estado não muda)
PERIODO_OCIO = 0.02              # s — ritmo do ciclo quando não há física (pausa/parado): 1 passo de decisão
VEL_MAX, AZIM_MAX, ELEV_MAX = 5.0, 360.0, 90.0      # faixas do contrato do controlo
PRECISAO = 6                     # casas decimais na telemetria (linhas pequenas e legíveis)
TECLA_ESPACO, TECLA_Q, TECLA_ESC = 32, 81, 256      # códigos GLFW entregues pelo viewer
# vento DINÂMICO ao vivo (ver o cabeçalho do módulo): 3 modos são do `env.py`, `rajada_agora` é um one-shot
# dirigido aplicado AQUI (o env não tem rajadas dirigidas) e `nenhum` é inerte.
MODOS_DINAMICOS = ("nenhum", "rajadas", "frente", "dryden", "rajada_agora")
MODOS_DINAMICOS_ENV = ("rajadas", "frente", "dryden")
FRENTE_BASE, FRENTE_ENV = ("vel", "azimute", "elevacao"), ("u_max", "t_s")   # os 2 formatos do `frente`
RAJADA_DURACAO_PADRAO = 25       # passos de decisão (0,5 s a 50 Hz) — duração da rajada one-shot
RAJADA_U_PADRAO = 3.0            # m/s — amplitude da rajada one-shot quando `u` não vem nos params
RAJADA_U_MAX = 5.0               # m/s — teto do contrato para a rajada one-shot


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
class Registo:
    """Conteúdo validado do ficheiro de controlo (vento base + comandos de episódio + vento dinâmico)."""

    vel: float = 0.0
    azimute: float = 0.0
    elevacao: float = 0.0
    ativo: bool = True
    reiniciar: int | None = None     # None = campo ausente: não mexe no contador
    loop: bool | None = None         # None = campo ausente: não mexe no modo
    dinamico: Dinamico | None = None  # None = campo ausente: não mexe no vento dinâmico


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


def ler_registo(dados) -> Registo:
    """Ficheiro de controlo → `Registo` validado (mesmas regras do net_probe/dashboard).

    `vel` ∈ [0, 5] e finita; `azimute` reduzido a [0, 360); `elevacao` cortada a [-90, 90]; `ativo` booleano
    (predefinido `True`, como no contrato v2); `reiniciar` inteiro ≥ 0, `loop` booleano e `dinamico` um bloco
    `{modo, params, ativo, seq}`, todos OPCIONAIS (`None` = «não mexe»). Fora disto é `ValueError` e o vento
    anterior fica em vigor.
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
                   _booleano(dados, "loop"), _ler_dinamico(dados.get("dinamico")))


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
        self._assinatura: tuple[int, int] | None = None
        self._avisos: set[str] = set()
        self._le_contador_inicial()

    def _le_contador_inicial(self) -> None:
        """Linha de base do contador (sem aplicar vento nenhum): o que o ficheiro já tiver no arranque."""
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            registo = ler_registo(dados)
        except (OSError, ValueError):
            return                                  # sem ficheiro (ou inválido): a linha de base fica None
        self.reiniciar, self.loop = registo.reiniciar, registo.loop

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
            registo = ler_registo(json.loads(self.caminho.read_text(encoding="utf-8")))
        except (OSError, ValueError) as erro:
            self._aviso(f"controlo ignorado ({erro}) — mantenho o vento anterior")
            return None
        self._actualiza_comandos(registo)
        self._aplica(env, registo)
        return registo

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

        A seguir trata o bloco `dinamico` (vento ao vivo): ver `_aplica_dinamico`.
        """
        self._aplica_base(env, registo)
        self._aplica_dinamico(env, registo.dinamico)
        self.n_ventos += 1
        self.ultimo = registo
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

        · `nenhum`/`ativo: false` → `env.definir_vento_dinamico(None)` (volta ao vento base) e a rajada
          one-shot em curso é cancelada;
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
            if self.rajada is not None:
                self.rajada = None
                self._aplica_base(env)
            env.definir_vento_dinamico(None)
            print("[sim] vento dinamico -> nenhum (so o vento base)", flush=True)
            return
        if din.modo == "rajada_agora":
            self._inicia_rajada(env, din)
            return
        self.rajada = None                              # mudar de modo cancela a rajada one-shot
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
        """Corta a rajada one-shot (só quando a física PARA: com o episódio congelado não avança) e volta
        ao vento base. Um RESET de episódio NÃO corta a rajada — ver `reaplicar`."""
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
    """Escritor JSONL da telemetria: 1 linha por amostra, ~10 Hz (1 Hz com o episódio parado) + eventos.

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


def _lista(vetor, n: int) -> list[float]:
    """Vector → lista JSON de `n` floats arredondados (zeros se o vector não tiver o tamanho esperado)."""
    a = np.asarray(vetor if vetor is not None else np.zeros(n), dtype=float).reshape(-1)
    if a.size != n:
        a = np.zeros(n)
    return [round(float(v), PRECISAO) for v in a]


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
    congelado: bool = False          # episódio terminado: a física está PARADA à espera de REINICIAR
    pausado: bool = False
    loop: bool = True                # CONTÍNUO por omissão (o `loop:false` do controlo/`--sem-loop` congela)
    vento_modo: str = "nenhum"       # modo dinâmico EM VIGOR (para a telemetria): nenhum/rajadas/...
    obs: np.ndarray | None = None
    acao: np.ndarray | None = None
    h1: np.ndarray | None = None
    h2: np.ndarray | None = None
    info: dict | None = None


def amostra(env: HoverEnv, est: Estado) -> dict:
    """Uma linha de telemetria com as chaves (e a ordem) do contrato.

    `ctrl` é o comando FÍSICO que a ação produziu — `data.ctrl` = [empuxo N, mx, my, mz N·m], escrito pelo
    `env.aplicar_acao` — para o site não ter de o derivar da ação e o poder rotular "ctrl do backend".
    Aditivo: as chaves antigas ficam na mesma ordem.

    INVARIANTE (a única que se promete): `ctrl == acao_para_ctrl(act)` nas linhas com AÇÃO APLICADA, ou seja
    `passo > 0` — são as que saem de um `env.step`, e o `data.ctrl` é exactamente o comando que a física usou.
    Nas linhas de ARRANQUE (a 1.ª do processo) e de REINÍCIO (episódio novo, `--loop`), que têm `passo == 0`
    e `t == 0`, vale `act == ctrl == [0, 0, 0, 0]`: o `env.reset()` zera o `data.ctrl` e ainda NÃO houve ação
    nenhuma. Aí a identidade NÃO se aplica — e não se inventa um `ctrl` que o simulador não aplicou: zeros é
    "nenhuma ação" (verdadeiro), enquanto `acao_para_ctrl([0,0,0,0])` = `[mg, 0, 0, 0]` = "ação nula" (o
    hover com 0,26487 N), que é outra coisa. Para separar as duas, basta `passo > 0`.
    """
    info = est.info if est.info else {}
    vento_vel, vento_azim = _vento_polar(env)
    return {
        "t": round(float(env.data.time), PRECISAO),
        "estado": "episodio_terminado" if est.congelado else "a_correr",
        "loop": bool(est.loop),                         # CONTÍNUO por omissão (aditivo ao contrato)
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
        "obs": _lista(est.obs, 16),
        "act": _lista(est.acao, 4),
        "ctrl": _lista(env.data.ctrl, 4),
        "h1": _lista(est.h1, 64),
        "h2": _lista(est.h2, 64),
    }


def _reiniciar(env: HoverEnv, est: Estado, sonda: Sonda, seed: int, ep: int | None = None) -> None:
    """`env.reset` (+ limpeza dos hooks) e volta ao estado "a correr"; `ep` só muda quando é episódio novo."""
    est.obs, est.info = env.reset(seed=seed)
    est.acao = np.zeros(4)
    est.h1, est.h2 = np.zeros(64), np.zeros(64)
    est.retorno = 0.0
    est.congelado = False
    sonda.limpar()
    if ep is not None:
        est.ep = ep


def correr(env: HoverEnv, politica, controlo: Controlo, telemetria: Telemetria, sonda: Sonda, args,
          viewer=None, teclas: Teclas | None = None) -> int:
    """Ciclo principal (serve a janela e o modo `--sem-janela`): passos de decisão a 50 Hz com o ritmo de
    `--fator-tempo`, leitura do controlo em cada passo, telemetria a ~10 Hz e PARAGEM no fim do episódio.

    Devolve 0. `viewer=None` → sem janela (nenhum import de GLFW/GL é feito aqui). Um `viewer` falso (testes)
    só precisa de `sync()`, `is_running()`, `lock()`, `m` e `viewport` — nunca se lhe toca no texto/figuras.
    """
    est = Estado(loop=not getattr(args, "sem_loop", False), congelado=False)
    _reiniciar(env, est, sonda, args.seed, ep=1)
    telemetria.escrever(amostra(env, est))               # linha de evento do arranque
    print(f"[sim] rollout: ep 1 comecou (seed {args.seed}, vento {_vento_polar(env)[0]:.2f} m/s); "
          + ("CONTINUO: no fim do episodio reinicia sozinho (ep+1, passo 0)"
             if est.loop else
             "loop:false -> a fisica PARA no fim do episodio e so um REINICIAR a retoma"), flush=True)
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
            print(f"[sim] loop {'ligado' if est.loop else 'desligado'} pelo controlo", flush=True)
        if controlo.consumir_reinicio():
            novo_ep = est.ep + 1 if (env.passos > 0 or est.congelado) else est.ep
            _reiniciar(env, est, sonda, args.seed + novo_ep - 1, ep=novo_ep)
            controlo.reaplicar(env)                      # o reset não apaga o que o dono pediu
            est.vento_modo = controlo.modo_efetivo()
            telemetria.escrever(amostra(env, est))       # evento: episódio novo, passo 0
            print(f"[sim] REINICIAR: ep {est.ep} comecou (passo 0, retorno 0)", flush=True)
        est.vento_modo = controlo.modo_efetivo()         # o modo em vigor já vai nesta amostra

        # 2) com o episódio terminado (ou em pausa) não há física: janela viva + batimento na telemetria
        if est.congelado or est.pausado:
            if viewer is not None:
                viewer.sync()
            telemetria.talvez_amostra(amostra(env, est),
                                      PERIODO_PARADO if est.congelado else PERIODO_AMOSTRA)
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
        est.retorno += float(recompensa)
        telemetria.talvez_amostra(amostra(env, est))
        if terminado or truncado:
            motivo = "caiu/capotou" if terminado else "tempo"
            est.completos += 1
            fim = f"ep {est.ep} terminou ({motivo}, retorno {est.retorno:+.3f})"
            if args.max_episodios and est.completos >= args.max_episodios:
                print(f"[sim] {fim} -> --max-episodios {args.max_episodios} atingido (nao arranca outro)",
                      flush=True)
                break
            if est.loop:                                 # CONTÍNUO (padrão; `--loop`/`loop:true`)
                print(f"[sim] {fim} -> auto-reset continuo (ep {est.ep + 1}, passo 0)", flush=True)
                _reiniciar(env, est, sonda, args.seed + est.ep, ep=est.ep + 1)
                controlo.reaplicar(env)                  # a transição é INVISÍVEL: o controlo volta a valer
                est.vento_modo = controlo.modo_efetivo()
                telemetria.escrever(amostra(env, est))
            else:
                est.congelado = True                     # `loop:false`: a física PARA aqui
                controlo.cancelar_rajada(env)            # com a física parada a rajada não avança: corta-se
                est.vento_modo = controlo.modo_efetivo()
                telemetria.escrever(amostra(env, est))   # evento imediato (não espera pelos 0,1 s)
                print(f"[sim] {fim} - loop:false: a fisica esta PARADA; um REINICIAR retoma o episodio",
                      flush=True)
        if viewer is not None:
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
                      args) -> int:
    """Abre a janela LIMPA (`show_left_ui=False`, `show_right_ui=False`, zero overlay) e corre o ciclo."""
    from mujoco import viewer as mjviewer  # import tardio: o modo --sem-janela não carrega GLFW/GL

    teclas = Teclas()
    viewer = None
    try:
        with mjviewer.launch_passive(env.model, env.data, key_callback=teclas.ao_teclar,
                                     show_left_ui=False, show_right_ui=False) as viewer:
            viewer.clear_texts()                         # garante zero overlay (nunca se usa set_texts)
            return correr(env, politica, controlo, telemetria, sonda, args, viewer=viewer, teclas=teclas)
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
            "\"dinamico\"} (lido a cada passo de decisão) e --telemetria JSONL a ~10 Hz (1 Hz com o episódio\n"
            "parado). `dinamico` = {modo: nenhum|rajadas|frente|dryden|rajada_agora, params, ativo, seq}:\n"
            "`frente` aceita {vel,azimute,elevacao} (degrau IMEDIATO do vento base) ou {u_max,t_s} (degrau em\n"
            "curso do env); `rajada_agora` = {u,azimute,elevacao,duracao} (one-shot dirigido).\n"
            "\n"
            "Sem auto-loop por omissão: NÃO — desde a ronda 7 o rollout é CONTÍNUO (no fim do episódio\n"
            "reinicia sozinho, ep+1, sem congelar). `loop:false` no controlo ou --sem-loop mantêm o\n"
            "comportamento antigo (física PARADA à espera de um REINICIAR)."
        ),
    )
    p.add_argument("--model", type=Path, default=None,
                   help="modelo do Stable-Baselines3 (.zip); por omissão, por ordem: o modelo da última "
                        "validação com sucesso (out/avaliacao_vento/*.json) -> vento_*/final.zip mais recente "
                        "(sem _seed) -> vento_*_seed*/final.zip -> runs/*/final.zip -> best_model.zip")
    p.add_argument("--sem-janela", action="store_true",
                   help="rollout SEM viewer (nenhum import de mujoco.viewer/glfw): escreve a telemetria e o "
                        "vento/REINICIAR funcionam na mesma — é o modo dos testes")
    p.add_argument("--controlo", type=Path, default=CONTROLO_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro JSON de controlo (vento + reiniciar + loop); padrão: {CONTROLO_OMISSAO}")
    p.add_argument("--telemetria", type=Path, default=TELEMETRIA_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro JSONL de telemetria (~10 Hz); padrão: {TELEMETRIA_OMISSAO}")
    p.add_argument("--fator-tempo", type=_fator_de_tempo, default=FATOR_TEMPO_OMISSAO, metavar="F",
                   help="ritmo do rollout: 1 = tempo real (PADRÃO), 2 = 2x mais rápido, 0.5 = metade, "
                        "0 = sem travão (o mais rápido possível)")
    p.add_argument("--loop", action="store_true",
                   help="auto-reset no fim de cada episódio — JÁ É O PADRÃO (CONTÍNUO); a flag fica aceite "
                        "por compatibilidade. O campo `loop` do controlo liga/desliga isto a quente")
    p.add_argument("--sem-loop", action="store_true",
                   help="desliga o contínuo: no fim do episódio a física PARA e só um REINICIAR (do site) "
                        "retoma — é o comportamento antigo, agora opt-in (`loop: false` no controlo faz o mesmo)")
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
    env = HoverEnv()
    politica = carregar_politica(caminho)
    controlo = Controlo(args.controlo)
    telemetria = Telemetria(args.telemetria, truncar=args.truncar_telemetria)
    sonda = Sonda(politica.policy)
    modo = "--sem-janela (sem viewer)" if args.sem_janela else (
        "janela limpa (show_left_ui=False, show_right_ui=False, sem set_texts/set_figures)")
    ritmo = f"{args.fator_tempo:g}x o tempo real" if args.fator_tempo > 0 else "sem travao (o mais rapido)"
    print(f"[sim] modelo: {caminho} ({motivo})")
    print(f"[sim] controlo: {_relativo(args.controlo)} | telemetria: {_relativo(args.telemetria)}")
    print(f"[sim] modo: {modo} | ritmo: {ritmo} | "
          f"loop: {'ligado (continuo, padrao)' if not args.sem_loop else 'desligado (--sem-loop: espera REINICIAR)'}",
          flush=True)
    try:
        if args.sem_janela:
            return correr(env, politica, controlo, telemetria, sonda, args)
        return correr_com_janela(env, politica, controlo, telemetria, sonda, args)
    finally:
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
