#!/usr/bin/env python3
"""sim_view.py — runner do padrão do laboratório `padrao-simulacao-clean-site`: janela LIMPA + telemetria.

Uma janela e mais nada: `mujoco.viewer.launch_passive` com `show_left_ui=False, show_right_ui=False` e ZERO
overlay (nunca se chama `set_texts`/`set_figures`; `clear_texts()` no arranque garante o ecrã limpo). TODAS as
métricas e TODOS os controlos ficam no SITE (`sim_site.py` + `site/`), que lê a telemetria e escreve o ficheiro
de controlo. Quem arranca isto é o `sim_site.py` (um comando arranca runner + servidor + site).

    uv run --group hover-rl python <exp>/sim_view.py                  # janela limpa + telemetria (uso normal: via sim_site.py)
    uv run --group hover-rl python <exp>/sim_view.py --sem-janela --max-segundos 3   # sem janela nenhuma (validação)
    uv run --group hover-rl python <exp>/sim_view.py --model out/melhor_modelo.zip   # com a política treinada

Contrato (NÃO mudar ao copiar o template — o site depende dele):
  · `out/sim_telemetria.jsonl` — 1 linha JSON por amostra (~10 Hz a correr; 1 Hz com o episódio parado), com as
    chaves POR ESTA ORDEM (15 + 2): t, estado, ep, passo, retorno, theta, erro, omega, vento_vel, vento_azim,
    vento_vec[], vento_modo, obs[], act[], ctrl[], h1[], h2[]. `estado` ∈ {"a_correr", "pausado",
    "episodio_terminado"}. `vento_vec` é o vector (vx,vy,vz m/s) do vento que a FÍSICA leva e `vento_modo` o
    modo dinâmico em vigor ("nenhum"/"rajadas"/"frente"/"dryden").
  · `out/controle_vento.json` — {vel, azimute, elevacao, ativo, reiniciar, loop, dinamico:{modo,params,ativo,
    seq}, t}, lido a CADA passo de decisão (vigia mtime_ns+tamanho) e escrito pelo site de forma ATÓMICA
    (`os.replace`).
  · SEM CICLO AUTOMÁTICO: no fim do episódio a física CONGELA e espera. Só recomeça com o REINICIAR do site
    (o campo `reiniciar` é um CONTADOR: qualquer valor novo = um pedido) ou com o `loop` ligado.

VENTO DINÂMICO AO VIVO (bloco `dinamico` do controlo, SEM reiniciar o episódio): `{"modo": ..., "params":
{...}, "ativo": bool, "seq": int}` com `modo` num de `nenhum | rajadas | frente | dryden | rajada_agora`:
  · `rajadas`/`dryden` → `env.definir_vento_dinamico({modo, **params})` — os MESMOS modos e a MESMA validação
    do treino (`p`/`duracao`/`u_max`, `sigma`/`L`/`u_max`/`v_min`); `u_max = 0` fica inerte;
  · `frente` aceita DOIS formatos: `{vel, azimute, elevacao}` = degrau IMEDIATO do vento base (validado com as
    faixas do vento base, é o que o site manda quando o dono mexe nos sliders) e `{u_max, t_s}` = degrau em
    curso do env ao instante `t_s`;
  · `rajada_agora` → rajada DIRIGIDA one-shot aplicada AQUI (o env não tem rajadas dirigidas): `params` =
    `u` [0, 5] m/s, `azimute`, `elevacao`, `duracao` (passos de decisão, 25 por omissão), somada ao vento base
    em vigor com o MESMO envelope `sin(π·k/(N+1))` do modo `rajadas` (nada de forças mágicas);
  · `nenhum` (ou `ativo: false`) → inerte: volta ao vento base.
A assinatura do bloco (`modo`+`params`+`ativo`+`seq`) evita re-disparos: reescrever o ficheiro com o mesmo
bloco não faz nada — o site incrementa o `seq` para disparar outra rajada igual.

Teclado (foco na janela): ESPAÇO pausa/retoma · Q ou Esc fecha. Não há mais teclas: o vento e o REINICIAR são
do site — é o que mantém a janela 100% limpa.

ADAPTAR ao teu robô: (a) `env.py` (modelo/física/observação/recompensa); (b) a linha `amostra()` se quiseres
outras 3 métricas no painel (renomeia `theta`/`erro`/`omega` — e o mesmo em `site/src/lib/sim.ts`); (c) o
ficheiro de política (`--model`). O que NÃO muda: as chaves/ordem da telemetria, o ficheiro de controlo, o
congelamento no fim do episódio e o REINICIAR por contador.
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
from typing import Any

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

# Ordem intencional (I001 desligado nesta linha): o `mjkit` define MUJOCO_GL=egl ANTES de `import mujoco`.

import env as env_mod
import numpy as np

CONTROLO_OMISSAO = _AQUI / "out" / "controle_vento.json"
TELEMETRIA_OMISSAO = _AQUI / "out" / "sim_telemetria.jsonl"
PERIODO_AMOSTRA = 0.1     # s de tempo SIMULADO entre amostras a correr (= 10 Hz a 50 Hz de decisão).
# Determinístico de propósito: com o MESMO rollout a telemetria é sempre igual, corra a 1× ou sem travão
# (`--fator-tempo 0`). Um relógio de parede daria ficheiros diferentes em máquinas diferentes.
PERIODO_PARADO = 1.0      # s de PAREDE entre batimentos com o episódio congelado/pausado (prova de vida:
# aí o tempo simulado não anda, por isso a cadência só pode ser de parede)
PRECISAO = 6              # casas decimais (linhas pequenas e legíveis)
VEL_MAX = env_mod.VENTO_VEL_MAX            # m/s — teto do contrato (o mesmo do env.py)
AZIM_MAX, ELEV_MAX = 360.0, 90.0           # graus — faixas do contrato
# vento DINÂMICO ao vivo: 3 modos são do `env.py`, `rajada_agora` é um one-shot dirigido aplicado AQUI e
# `nenhum` é inerte (ver o cabeçalho do módulo).
MODOS_DINAMICOS = ("nenhum", "rajadas", "frente", "dryden", "rajada_agora")
MODOS_DINAMICOS_ENV = env_mod.VENTO_DINAMICO_MODOS        # os que o `env.definir_vento_dinamico` conhece
FRENTE_BASE, FRENTE_ENV = ("vel", "azimute", "elevacao"), ("u_max", "t_s")   # os 2 formatos do `frente`
RAJADA_DURACAO_PADRAO = 25       # passos de decisão (0,5 s a 50 Hz) — duração da rajada one-shot
RAJADA_U_PADRAO = 3.0            # m/s — amplitude da rajada one-shot quando `u` não vem nos params
RAJADA_U_MAX = VEL_MAX           # m/s — teto do contrato para a rajada one-shot
# Conteúdo de arranque do ficheiro de controlo (o site edita-o; a chave `dinamico` é o vento ao vivo)
CONTROLO_INICIAL = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False, "reiniciar": 0,
                    "loop": False, "dinamico": {"modo": "nenhum", "params": {}, "ativo": False, "seq": 0},
                    "t": 0.0}


# ------------------------------------------------------------------------------------- ficheiro de controlo
def escrever_atomico(caminho: Path, dados: dict) -> None:
    """Escrita ATÓMICA (tmp + `os.replace`): quem lê nunca vê um ficheiro a meio — é o que o site usa."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, caminho)


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
    reiniciar: int | None = None        # None = campo ausente: não mexe no contador
    loop: bool | None = None            # None = campo ausente: não mexe no modo
    dinamico: Dinamico | None = None    # None = campo ausente: não mexe no vento dinâmico
    t: float | None = None


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
    if isinstance(duracao, bool) or not isinstance(duracao, int) or int(duracao) < 1:
        raise ValueError(f"`dinamico.params.duracao` tem de ser um inteiro ≥ 1 passos de decisão "
                         f"(recebido {duracao!r})")
    return {"u": u, "azimute": _numero(params, "azimute", 0.0) % AZIM_MAX,
            "elevacao": min(ELEV_MAX, max(-ELEV_MAX, _numero(params, "elevacao", 0.0))),
            "duracao": int(duracao)}


def _params_frente(params: dict) -> tuple[str, dict]:
    """Params do modo `frente` → `("base"|"env", params)`: aceita os DOIS formatos do contrato.

    · formato (a) `{"vel", "azimute", "elevacao"}` → degrau IMEDIATO do vento base (`definir_vento`),
      validado AQUI com as faixas do vento base (as mesmas do `POST /api/vento`) — NÃO passa pelo
      `env.valida_vento_dinamico`, que espera `u_max`/`t_s` e recusaria estas chaves (é o formato que o site
      manda quando o dono mexe nos sliders com o modo `frente` ligado);
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
    `env.definir_vento_dinamico` (as mesmas regras do treino: não se duplicam aqui).
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
        params = _params_frente(params)[1]      # valida os 2 formatos e guarda os params normalizados
    return Dinamico(modo, params, (modo != "nenhum") if ativo is None else bool(ativo), seq)


def ler_registo(dados: Any) -> Registo:
    """Ficheiro de controlo → `Registo` validado.

    `vel` ∈ [0, 5] m/s e finita; `azimute` reduzido a [0, 360); `elevacao` cortada a [−90, 90]; `ativo`
    booleano (predefinido `True`); `reiniciar` inteiro ≥ 0, `loop` booleano e `dinamico` um bloco
    `{modo, params, ativo, seq}`, todos OPCIONAIS (`None` = «não mexe»). Fora disto é `ValueError` e o vento
    (e o modo) anterior fica em vigor — um ficheiro inválido nunca mata o ciclo.
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
                   _numero(dados, "t", 0.0) if "t" in dados else None)


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
        self.rajada: dict | None = None         # rajada one-shot em curso: {vec, k, n}
        self.rajada_concluida = False           # a última rajada one-shot já terminou (modo volta a "nenhum")
        self._assinatura: tuple[int, int] | None = None
        self._assinatura_dinamica: str | None = None
        self._avisos: set[str] = set()
        self._le_contador_inicial()

    def _le_contador_inicial(self) -> None:
        """Linha de base do contador (sem aplicar vento nenhum): o que o ficheiro já tiver no arranque."""
        try:
            registo = ler_registo(json.loads(self.caminho.read_text(encoding="utf-8")))
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

    def verifica(self, env) -> Registo | None:
        """Um passo de decisão: aplica o vento/modo se o ficheiro mudou; devolve o registo (ou `None`)."""
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

    def _aplica(self, env, registo: Registo) -> None:
        """`ativo` → vento base pedido; inativo → ar parado. A seguir trata o bloco `dinamico`."""
        if registo.ativo:
            env.definir_vento(registo.vel, registo.azimute, registo.elevacao)
        else:
            env.definir_vento(0.0, 0.0, 0.0)
        self._aplica_dinamico(env, registo.dinamico)
        self.n_ventos += 1
        self.ultimo = registo
        print(f"[sim] vento base -> {registo.vel:.2f} m/s @ {registo.azimute:.1f}°"
              + (f" (elev {registo.elevacao:+.1f}°)" if registo.elevacao else "")
              + ("" if registo.ativo else " [desligado]"), flush=True)

    def _aplica_base(self, env, registo: Registo | None = None) -> None:
        """Reescreve o VENTO BASE do registo em vigor (o que a rajada one-shot soma); não toca no modo."""
        r = registo if registo is not None else self.ultimo
        if r is None:
            return
        env.definir_vento(r.vel, r.azimute, r.elevacao) if r.ativo else env.definir_vento(0.0, 0.0, 0.0)

    def _aplica_dinamico(self, env, din: Dinamico | None) -> None:
        """Liga/desliga/reconfigura o vento dinâmico quando o bloco `dinamico` MUDA (sem reset nenhum).

        · `nenhum`/`ativo: false` → `env.definir_vento_dinamico(None)` (volta ao vento base) e a rajada
          one-shot em curso é cancelada;
        · `rajadas`/`dryden` → `env.definir_vento_dinamico({modo, **params})` (quem valida os parâmetros é o
          env: `ValueError` → aviso e mantém-se o modo anterior);
        · `frente` aceita DOIS formatos (ver `_params_frente`): `{vel, azimute, elevacao}` = degrau IMEDIATO
          do vento base (`_aplica_degrau`, sem passar pelo env) e `{u_max, t_s}` = modo em curso do env;
        · `rajada_agora` → arranca uma rajada DIRIGIDA one-shot (o env não tem rajadas dirigidas): o envelope
          é escrito AQUI, passo a passo, por cima do vento base em vigor (`passo_rajada`).
        A assinatura do bloco evita re-disparos: reescrever o ficheiro com o MESMO bloco não faz nada (o site
        muda o `seq` quando quer disparar outra vez).
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
            print("[sim] vento dinâmico -> nenhum (só o vento base)", flush=True)
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
        print(f"[sim] vento dinâmico -> {din.modo} {config}", flush=True)

    def _aplica_degrau(self, env, params: dict) -> None:
        """`frente` formato (a): degrau IMEDIATO do vento base, sem passar pelo validador do env.

        Desliga a camada dinâmica do env (para não ficar turbulência de um modo anterior a somar ao degrau) e
        escreve o vento base já: a física do passo seguinte leva com ele (é o `definir_vento`, o mesmo caminho
        do `vel`/`azimute`/`elevacao` do controlo — nada de forças mágicas).
        """
        env.definir_vento_dinamico(None)
        env.definir_vento(float(params["vel"]), float(params["azimute"]), float(params["elevacao"]))
        print(f"[sim] frente -> degrau imediato do vento base: {params['vel']:.2f} m/s @ "
              f"{params['azimute']:.1f}°"
              + (f" (elev {params['elevacao']:+.1f}°)" if params["elevacao"] else ""), flush=True)

    def _inicia_rajada(self, env, din: Dinamico) -> None:
        """Arranca a rajada one-shot: vector dirigido + envelope `sin(π·k/(N+1))` (o mesmo do env)."""
        p = din.params
        self.rajada = {"u": float(p["u"]), "vec": env_mod.vetor_vento(float(p["u"]), float(p["azimute"]),
                                                                     float(p["elevacao"])),
                       "k": 0, "n": int(p["duracao"]), "azimute": float(p["azimute"]),
                       "elevacao": float(p["elevacao"])}
        print(f"[sim] rajada_agora -> u {p['u']:.2f} m/s @ {p['azimute']:.1f}° (elev {p['elevacao']:+.1f}°), "
              f"{p['duracao']} passos", flush=True)

    def passo_rajada(self, env) -> bool:
        """Avança a rajada one-shot UM passo de decisão (vento BASE + rajada·envelope); `True` se escreveu.

        Chamado ANTES de cada `env.step`, para a física do passo já levar com a rajada (o `step` reescreve o
        vento do passo a partir do base + modo, e o `qfrc_applied` da rajada é reposto aqui). No fim do
        envelope volta ao vento base em vigor. Não mexe no modo dinâmico do env (composição: base+rajada+modo).
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
        envelope = math.sin(math.pi * self.rajada["k"] / (self.rajada["n"] + 1.0))
        total = self._vetor_base() + self.rajada["vec"] * envelope
        env.definir_vento(float(np.linalg.norm(total)), env_mod.azimute_graus(total),
                          float(np.degrees(np.arcsin(np.clip(total[2] / max(1e-12, np.linalg.norm(total)),
                                                            -1.0, 1.0)))))
        return True

    def cancelar_rajada(self, env) -> None:
        """Corta a rajada one-shot (fim de episódio/reinício) e volta ao vento base."""
        if self.rajada is None:
            return
        self.rajada = None
        self._aplica_base(env)

    def modo_efetivo(self) -> str:
        """Modo de vento dinâmico EM VIGOR agora (o que a telemetria publica em `vento_modo`).

        `rajada_agora` só enquanto a rajada one-shot decorre: depois de terminar o modo em vigor é `nenhum`
        (o vento voltou ao base), mesmo que o bloco do controlo continue a dizer `rajada_agora`.
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
        return env_mod.vetor_vento(r.vel, r.azimute, r.elevacao)

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

    def consumir_reinicio(self) -> bool:
        """Consome o pedido de REINICIAR (devolve `True` uma vez por contador novo)."""
        if not self.pedido_reinicio:
            return False
        self.pedido_reinicio = False
        self.n_reinicios += 1
        return True

    def _aviso(self, texto: str) -> None:
        if texto not in self._avisos:                # uma vez por texto: o ciclo nunca fica aos gritos
            self._avisos.add(texto)
            print(f"[sim] aviso: {texto}", flush=True)


# ----------------------------------------------------------------------------------------------- telemetria
class Telemetria:
    """Escritor JSONL da telemetria: 1 linha por amostra + eventos, com `flush` (o site lê por polling)."""

    def __init__(self, caminho: Path, truncar: bool = False) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.n_linhas = 0
        self._ficheiro = self.caminho.open("w" if truncar else "a", encoding="utf-8")
        self._ultima = 0.0            # parede
        self._ultimo_t = 0.0          # simulado

    def escrever(self, linha: dict) -> None:
        self._ficheiro.write(json.dumps(linha, separators=(",", ":")) + "\n")
        self._ficheiro.flush()
        self.n_linhas += 1
        self._ultima = time.perf_counter()
        self._ultimo_t = float(linha.get("t", self._ultimo_t))

    def talvez_amostra(self, linha: dict, *, t_sim: float | None = None, periodo: float = PERIODO_AMOSTRA,
                       forcar: bool = False) -> bool:
        """Escreve se passou `periodo` desde a última (em tempo SIMULADO se `t_sim` for dado, senão de PAREDE).

        `forcar` escreve sempre (é o que os EVENTOS usam: arranque, reinício, fim de episódio).
        """
        if not forcar:
            decorrido = (float(t_sim) - self._ultimo_t) if t_sim is not None else (time.perf_counter() - self._ultima)
            if decorrido < periodo:
                return False
        self.escrever(linha)
        return True

    def fechar(self) -> None:
        try:
            self._ficheiro.close()
        except OSError:
            pass


# --------------------------------------------------------------------------------------------- política
class Politica:
    """Ação a aplicar: a política PPO treinada (`--model`) ou a ação NULA (`ctrl = τ_trim`, o equilíbrio no alvo).

    Com política, `h1`/`h2` são as ativações das duas camadas escondidas da MLP (o site desenha-as); sem
    política vão VAZIAS — o site mostra «—» em vez de inventar números.
    """

    def __init__(self, caminho: Path | None, env) -> None:
        self.caminho = Path(caminho) if caminho else None
        self.modelo = None
        self.nome = "trim (ação nula)"
        if self.caminho is not None:
            from stable_baselines3 import (
                PPO,  # import local: o runner também corre sem SB3 instalado
            )

            self.modelo = PPO.load(self.caminho, device="cpu")
            self.nome = f"PPO {self.caminho.name}"
        self.env = env

    def acao(self, obs) -> np.ndarray:
        if self.modelo is None:
            return np.zeros(env_mod.N_ACT, dtype=np.float32)
        acao, _ = self.modelo.predict(obs, deterministic=True)
        return np.asarray(acao, dtype=np.float32).reshape(-1)[: env_mod.N_ACT]

    def ativacoes(self, obs) -> tuple[list[float], list[float]]:
        """(h1, h2) da MLP da política — vazio quando não há política (nada de números inventados)."""
        if self.modelo is None:
            return [], []
        import torch

        rede = self.modelo.policy.mlp_extractor.policy_net
        camadas = [c for c in rede if isinstance(c, torch.nn.Linear)]
        saidas: list[list[float]] = []

        def guarda(_modulo, _entradas, saida) -> None:
            saidas.append([round(float(v), PRECISAO) for v in saida.detach().reshape(-1)])

        handles = [c.register_forward_hook(guarda) for c in camadas[:2]]
        try:
            with torch.no_grad():
                rede(torch.as_tensor(np.asarray(obs, dtype=np.float32)).reshape(1, -1))
        finally:
            for h in handles:
                h.remove()
        return (saidas[0] if saidas else []), (saidas[1] if len(saidas) > 1 else [])


# ----------------------------------------------------------------------------------------------- estado/ciclo
@dataclass
class Estado:
    """Estado do rollout que a telemetria publica (uma linha por amostra)."""

    ep: int = 1
    retorno: float = 0.0
    completos: int = 0
    congelado: bool = False      # episódio terminado: a física está PARADA à espera de REINICIAR
    pausado: bool = False
    loop: bool = False
    obs: np.ndarray | None = None
    acao: np.ndarray | None = None
    h1: list[float] = field(default_factory=list)
    h2: list[float] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def nome_estado(self) -> str:
        if self.congelado:
            return "episodio_terminado"
        return "pausado" if self.pausado else "a_correr"


def _lista(v, n: int) -> list[float]:
    """Vetor → lista JSON de tamanho n (zeros se não houver) — o site nunca recebe `null` no meio de um vetor."""
    if v is None:
        return [0.0] * n
    return [round(float(x), PRECISAO) for x in np.asarray(v, dtype=float).reshape(-1)[:n]]


def amostra(env, est: Estado, controlo: Controlo | None = None) -> dict:
    """Uma linha de telemetria com as chaves (e a ordem) do contrato. ADAPTAR: as 3 métricas do painel.

    INVARIANTE (a única que se promete): nas linhas com AÇÃO APLICADA (`passo > 0`) vale
    `ctrl == acao_para_ctrl(act)`. Nas linhas de ARRANQUE/REINÍCIO (`passo == 0`, `t == 0`) `act == ctrl == []`
    porque o `reset()` ainda não aplicou ação NENHUMA — zeros é "nenhuma ação" (verdadeiro), não se inventa um
    comando que o simulador não aplicou.

    `vento_vec` é o vector (vx,vy,vz m/s) do vento que a FÍSICA leva (o `env.vento_vec`), e `vento_modo` o
    modo dinâmico em vigor — o `controlo` só é preciso para saber se uma rajada one-shot está a decorrer
    (esse modo é do runner, não do env).
    """
    vel, azim = env.vento_polar()
    vec = np.asarray(env.vento_vec, dtype=float).reshape(3)
    if est.acao is None:
        act: list[float] = []
        ctrl: list[float] = []
    else:
        act = _lista(est.acao, env_mod.N_ACT)
        ctrl = [round(env.acao_para_ctrl(est.acao), PRECISAO)]
    modo = controlo.modo_efetivo() if controlo is not None else str(env.vento_modo)
    return {
        "t": round(float(env.data.time), PRECISAO),
        "estado": est.nome_estado,
        "ep": int(est.ep),
        "passo": int(env.passos),
        "retorno": round(float(est.retorno), PRECISAO),
        "theta": round(float(est.info.get("theta", env.theta)), PRECISAO),
        "erro": round(float(est.info.get("erro", env.erro)), PRECISAO),
        "omega": round(float(est.info.get("omega", env.omega)), PRECISAO),
        "vento_vel": round(vel, PRECISAO),
        "vento_azim": round(azim, PRECISAO),
        "vento_vec": [round(float(v), PRECISAO) for v in vec],
        "vento_modo": modo,
        "obs": _lista(est.obs, env_mod.N_OBS),
        "act": act,
        "ctrl": ctrl,
        "h1": list(est.h1),
        "h2": list(est.h2),
    }


class Ritmo:
    """Trava de tempo real: `--fator-tempo 1` = tempo real, 0,5 = metade, 2 = o dobro, 0 = sem travão.

    A base é RE-BASEADA em cada `reset()` (bug real do experimento 09: depois de uma espera, o episódio
    reiniciado corria ~9× porque o relógio de parede tinha continuado a andar).
    """

    def __init__(self, fator: float) -> None:
        self.fator = float(fator)
        self.base_parede = time.perf_counter()
        self.base_sim = 0.0

    def re_base(self, t_sim: float) -> None:
        self.base_parede = time.perf_counter()
        self.base_sim = float(t_sim)

    def espera(self, t_sim: float) -> None:
        if self.fator <= 0:
            return
        restante = (self.base_parede + (float(t_sim) - self.base_sim) / self.fator) - time.perf_counter()
        if restante > 0:
            time.sleep(restante)


class Teclas:
    """Teclado MÍNIMO da janela limpa: ESPAÇO pausa/retoma, Q/Esc fecha. O resto é do site."""

    def __init__(self) -> None:
        self.fechar = False
        self.pausado = False

    def ao_teclar(self, codigo: int) -> None:
        c = chr(codigo) if 0 <= codigo < 0x110000 else ""
        if c in ("Q", "q") or codigo == 256:          # Q · Esc (GLFW_KEY_ESCAPE = 256)
            self.fechar = True
        elif codigo == 32:                            # ESPAÇO
            self.pausado = not self.pausado
            print(f"[sim] {'PAUSA' if self.pausado else 'RETOMA'}", flush=True)


def _nova_amostra(env, est: Estado, politica: Politica, controlo: Controlo, telemetria: Telemetria,
                  forcar: bool) -> None:
    """Escreve a linha de telemetria no ritmo certo (o `h1`/`h2` só se calculam quando se vai escrever)."""
    if est.acao is not None and not est.h1 and politica.modelo is not None:
        est.h1, est.h2 = politica.ativacoes(est.obs)
    if est.congelado or est.pausado:                  # parado: batimento de PAREDE (o tempo simulado não anda)
        telemetria.talvez_amostra(amostra(env, est, controlo), periodo=PERIODO_PARADO, forcar=forcar)
    else:                                             # a correr: cadência em tempo SIMULADO (determinística)
        telemetria.talvez_amostra(amostra(env, est, controlo), t_sim=float(env.data.time), forcar=forcar)


def correr(env, politica: Politica, controlo: Controlo, telemetria: Telemetria, est: Estado, args, viewer=None,
           teclas: Teclas | None = None) -> int:
    """Ciclo principal: leitura do controlo, ação, `mj_step` (dentro do `env.step`), telemetria e PARAGEM no fim.

    Com o episódio terminado a física CONGELA (não se dá `mj_step` nenhum) e só o REINICIAR do site (ou o
    `loop`) recomeça — o `reset()` explícito é o único caminho de reinício. Devolve o exit code.
    """
    ritmo = Ritmo(args.fator_tempo)
    t_limite = float(args.max_segundos) if args.max_segundos > 0 else None
    ep_limite = int(args.max_episodios) if args.max_episodios > 0 else None
    est.obs, info = env.reset(seed=args.seed)
    est.info = info
    est.retorno = 0.0
    ritmo.re_base(env.data.time)
    telemetria.escrever(amostra(env, est, controlo))  # linha de evento do arranque (passo 0, sem ação)
    print(f"[sim] arranque: ep 1 · política {politica.nome} · fator-tempo {args.fator_tempo}", flush=True)

    def vivo() -> bool:
        if teclas is not None and (teclas.fechar or not viewer.is_running()):
            return False
        if t_limite is not None and env.data.time >= t_limite:
            return False
        return not (ep_limite is not None and est.completos >= ep_limite)

    while vivo():
        controlo.verifica(env)
        if controlo.loop is not None:
            est.loop = bool(controlo.loop)
        if teclas is not None:
            est.pausado = teclas.pausado

        # 1) REINICIAR do site: o ÚNICO caminho de reinício explícito
        if controlo.consumir_reinicio():
            controlo.cancelar_rajada(env)         # a rajada one-shot não atravessa episódios
            est.ep += 1
            est.retorno = 0.0
            est.congelado = False
            est.obs, info = env.reset(seed=args.seed + est.ep)
            est.info, est.acao, est.h1, est.h2 = info, None, [], []
            ritmo.re_base(env.data.time)
            telemetria.escrever(amostra(env, est, controlo))   # evento: episódio novo, passo 0
            print(f"[sim] REINICIAR → ep {est.ep} (t={env.data.time:.3f} s)", flush=True)

        # 2) congelado/pausado: SEM física — janela viva, batimento na telemetria e travão pelo BATIMENTO
        if est.congelado or est.pausado:
            if telemetria.talvez_amostra(amostra(env, est, controlo), periodo=PERIODO_PARADO):
                ritmo.re_base(env.data.time)          # o tempo parado não conta para o ritmo
            if viewer is not None:
                with viewer.lock():
                    viewer.sync()
                time.sleep(1.0 / 60.0)
            continue

        # 3) passo de decisão: política → ação → física (env.step faz os `decimacao` mj_step)
        controlo.passo_rajada(env)            # rajada one-shot (se houver) no vento do passo que começa
        est.acao = politica.acao(est.obs)
        est.h1, est.h2 = politica.ativacoes(est.obs)
        est.obs, recompensa, terminado, truncado, info = env.step(est.acao)
        est.info = info
        est.retorno += float(recompensa)
        _nova_amostra(env, est, politica, controlo, telemetria, forcar=False)
        if viewer is not None:
            with viewer.lock():
                viewer.sync()
        ritmo.espera(env.data.time)

        # 4) fim de episódio: CONGELA e espera (sem auto-reset; só o site reinicia, ou o LOOP ligado)
        if terminado or truncado:
            est.completos += 1
            est.congelado = True
            est.info = {**info, "motivo": "terminou" if terminado else "teto de passos"}
            telemetria.escrever(amostra(env, est, controlo))   # evento imediato (não espera pelos 0,1 s)
            print(f"[sim] ep {est.ep} terminou ({est.info['motivo']}) em {env.passos} passos · "
                  f"retorno {est.retorno:.3f} · θ={np.degrees(env.theta):+.2f}°", flush=True)
            if est.loop:
                controlo.cancelar_rajada(env)
                est.ep += 1
                est.retorno = 0.0
                est.congelado = False
                est.obs, info = env.reset(seed=args.seed + est.ep)
                est.info, est.acao, est.h1, est.h2 = info, None, [], []
                ritmo.re_base(env.data.time)
                telemetria.escrever(amostra(env, est, controlo))
    print(f"[sim] fim: {telemetria.n_linhas} linhas de telemetria em {telemetria.caminho} · "
          f"{controlo.n_ventos} ventos aplicados · {controlo.n_reinicios} reinícios · {est.completos} episódios",
          flush=True)
    return 0


def correr_com_janela(env, politica: Politica, controlo: Controlo, telemetria: Telemetria, est: Estado, args) -> int:
    """Abre a janela LIMPA (`show_left_ui=False`, `show_right_ui=False`, zero overlay) e corre o ciclo."""
    import mujoco.viewer as mjviewer

    teclas = Teclas()
    with mjviewer.launch_passive(env.model, env.data, key_callback=teclas.ao_teclar,
                                show_left_ui=False, show_right_ui=False) as viewer:
        viewer.clear_texts()                          # garante zero overlay (nunca se usa set_texts)
        print("[sim] janela limpa: ESPAÇO pausa/retoma · Q ou Esc fecha · controlos e métricas no SITE",
              flush=True)
        return correr(env, politica, controlo, telemetria, est, args, viewer=viewer, teclas=teclas)


def analisar_argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Runner do padrão 'simulação CLEAN + site': janela MuJoCo limpa + telemetria JSONL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Quem arranca isto é o `sim_site.py` (um comando: runner + servidor + site).\n"
                "Controlo: out/controle_vento.json · telemetria: out/sim_telemetria.jsonl\n"
                "SEM auto-reset: no fim do episódio a física congela até o site pedir REINICIAR."))
    p.add_argument("--model", type=Path, default=None, metavar="CAMINHO.zip",
                   help="política PPO (Stable-Baselines3) a pilotar; por omissão a ação nula (ctrl = τ_trim)")
    p.add_argument("--sem-janela", action="store_true",
                   help="rollout SEM viewer (nenhum import de mujoco.viewer/glfw): só telemetria + controlo")
    p.add_argument("--controlo", type=Path, default=CONTROLO_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro de controlo JSON (vento/REINICIAR/LOOP); padrão: {CONTROLO_OMISSAO.name} em out/")
    p.add_argument("--telemetria", type=Path, default=TELEMETRIA_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro JSONL de telemetria (~10 Hz); padrão: {TELEMETRIA_OMISSAO.name} em out/")
    p.add_argument("--fator-tempo", type=float, default=1.0, metavar="F",
                   help="ritmo: 1 = tempo real (padrão), 0,5 = metade, 2 = dobro, 0 = sem travão")
    p.add_argument("--loop", action="store_true", help="arranca com auto-reset no fim do episódio (o normal é OFF)")
    p.add_argument("--seed", type=int, default=0, help="semente do reset (o episódio N usa seed+N)")
    p.add_argument("--max-segundos", type=float, default=0.0, metavar="S", help="pára ao fim de S segundos de simulação (0 = sem limite)")
    p.add_argument("--max-episodios", type=int, default=0, metavar="N", help="pára ao fim de N episódios (0 = sem limite)")
    p.add_argument("--truncar-telemetria", action="store_true", help="começa a telemetria do zero (por omissão continua em append)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = analisar_argumentos(argv)
    env = env_mod.novo_env(seed=args.seed)
    est = Estado(loop=bool(args.loop))
    politica = Politica(args.model, env)
    controlo = Controlo(args.controlo)
    telemetria = Telemetria(args.telemetria, truncar=args.truncar_telemetria)
    if not args.controlo.exists():                    # cria o ficheiro com os valores de arranque (o site edita-o)
        escrever_atomico(args.controlo, CONTROLO_INICIAL | {"loop": bool(args.loop)})
    print(f"[sim] controlo: {args.controlo} · telemetria: {args.telemetria}", flush=True)
    if os.environ.get("DISPLAY") is None and not args.sem_janela:
        print("[sim] aviso: sem DISPLAY — a janela pode não abrir (usa --sem-janela para validar)", flush=True)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        if args.sem_janela:
            return correr(env, politica, controlo, telemetria, est, args)
        return correr_com_janela(env, politica, controlo, telemetria, est, args)
    finally:
        telemetria.fechar()


if __name__ == "__main__":
    sys.exit(main())
