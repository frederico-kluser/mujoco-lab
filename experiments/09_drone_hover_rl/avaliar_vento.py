#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/avaliar_vento.py — a cascata clássica C++ (núcleo) CONTRA O VENTO: antes × depois × RL.

A fase 1 (B0/B: `avaliar_classico.py`, `avaliar_nucleo.py`) mediu a cascata SEM VENTO. Aqui mede-se a FASE 2: o mesmo
núcleo de firmware C++ (`sitl.DroneRealEnvNucleo(modo_nucleo="cascata")`, o controlador que o site voa por omissão) com
vento, contra a política RL de voo de referência (`out/real_1950_voo_final/final.zip`, a mesma da B0), na MESMA planta
(build do `hardware.json` da política), com as MESMAS sementes de avaliação (5000…5011) e a MESMA realização de vento
para todos.

VARIANTES
  `cascata`       o núcleo C++ com a Config que `sitl.config_de_hardware(...)` dá HOJE (o padrão do site): observador de
                  perturbação no laço de velocidade + velocidade do fluxo sem a rotação do corpo;
  `cascata_fase1` o MESMO núcleo com isso desligado (`GANHOS_FASE1`) — o «antes», no mesmo binário e na mesma corrida
                  (conferido contra o código da fase 1: 1584 métricas iguais a 1e-11, o ruído do simulador entre processos);
  `cascata_vz_antiga` a cascata de 2026-10-12 (com o observador de perturbação) e o laço VERTICAL de antes
                  (`GANHOS_VERTICAL_ANTIGA`) — o antes × depois da vertical de 2026-10-13;
  `rl`            a política RL no `DroneRealEnv` (FC + estimador de bordo em Python, como na B0);
  `python`        o protótipo de referência (`controlo_classico.py`) com os ganhos de hoje — só para conferir C++ ≡ Python
                  com vento (`--variantes cascata,python`).

REGIMES (`REGIMES`; a corrida publicada usa `REGIMES_PUBLICADOS`; todos × as mesmas sementes)
  pairar 30 s    `calmo` · vento CONSTANTE `const_W_<direção>` de 1 a 5 m/s (`lado`; a 3 e 5 m/s também `frente` = de proa,
                 `subida` = diagonal com ar ascendente +30° e `descida` = lateral com ar descendente −30°) — o vento já
                 sopra na DESCOLAGEM · vento ALEATÓRIO `natural_W`: o gerador do cockpit, `vento_natural.VentoNatural`
                 (média W de lado + turbulência + rajadas 1 − cos + direção a deambular), com a semente do episódio;
  degrau         a pairar em ar parado, o vento LIGA-SE aos 12 s (`definir_vento`) — pico de desvio e tempo de recuperação;
  seguimento     plano WASDQE aleatório do env (20 s) em ar parado, com vento constante e com vento aleatório;
  comando        degrau de velocidade 0 → 1 m/s (o da B0): a resposta ao piloto não pode piorar.
  Os modos dinâmicos do PRÓPRIO env (`dryden_*` = `turbulencia_de(W)`, `rajadas_*`, `aleatoria_*`, `frente_*`) continuam
  definidos (`--so`, `--todos`): o processo de vento do env (`_passo_vento`) é aí avançado com um gerador próprio
  (`VentoPareado`) para a série de vento não depender de quantos números a planta de cada variante já consumiu.

MÉTRICAS por episódio (a verdade do simulador só serve para MEDIR): ‖xy‖ mediana/p95/RMS/máx. na janela e máx. do voo todo
(inclui a descolagem), |Δz| RMS/máx., inclinação RMS/máx., desvio de rumo, fração de passos de 2 ms com um motor saturado,
o que o estimador erra (velocidade, atitude, odometria), o estado da cascata (integral, aceleração pedida, saturação da
inclinação) e a perturbação aerodinâmica VERDADEIRA (força específica no plano do corpo, rodada para o mundo).
Agregado por regime × variante: média, desvio-padrão, mediana e PIOR semente; quedas contadas à parte. ENVELOPE por
família de regimes (`FAMILIAS`) e o TETO do slider do cockpit (`recomendacao_site`).

CALIBRAÇÃO (`--calibrar`, sementes 9000…9007, núcleo C++; `out/vento_classico/calibracao.json`) — o que decidiu cada escolha:
  · banda do observador ω_c/razão: K_att (razão 2,5) → pico do degrau de vento de 3 m/s 42 cm; ω_c/1,5 → 29 cm; ω_c (o
    padrão) → 21 cm e recuperação em 3,7 s; 1,4·ω_c → 16 cm mas com mais agitação da inclinação em ar parado (0,46° vs
    0,37° RMS) e o degrau de comando a assentar mais tarde (1,23 vs 0,85 s); fase 1: 149 cm e 14 s;
  · o atraso da medida no modelo (τ_vel): sem ele o sobressinal do degrau de comando é 10,2 % (com: 2,6 %);
  · o braço e o alinhamento do fluxo no estimador: sem eles 11,3 % (com: 2,6 %); sozinhos, sem observador, não rejeitam
    vento nenhum (pico 150 cm);
  · em ar parado o observador MELHORA a pairagem (‖xy‖ RMS 5,1 → 3,1 cm): também anula o passeio da atitude estimada.
O que foi MEDIDO e NÃO ficou (protótipo Python, mesmas sementes de calibração):
  · observador pelo ACELERÓMETRO (força específica x, y do corpo filtrada — o laço exterior do INDI): o ruído de vibração
    entra na inclinação e a pairagem em ar parado PIORA (5,1 → 6,8 cm) com rejeição pior do que a do observador de
    velocidade (pico 21 cm mas 12 s a recuperar); a fusão dos dois dá o melhor degrau de vento (10–12 cm) à custa de
    16–20 % de sobressinal no comando;
  · observador VERTICAL (mesma estrutura sobre v_z): segura a altitude num ar descendente de 2 m/s (|Δz| 27 → 2 cm) mas
    troca-a por deriva horizontal quando o empuxo satura (5 m/s a −30°: ‖xy‖ RMS 25 → 160–180 cm; turbulência `dryden`
    do env a 5 m/s: 47 → 58–60 cm) e piora o degrau de subida (sobressinal 10,8 → 16–25 %). A vertical ficou a da fase 1.

REGRAS DE HONESTIDADE
  · calibração ≠ avaliação: as escolhas do controlador saem de fórmulas da planta e foram conferidas nas sementes de
    CALIBRAÇÃO 9000…; as de avaliação 5000…5011 não afinam nada;
  · resultados novos SÓ em `out/vento_classico/` (os JSON publicados da fase 1 não são tocados);
  · MEDIDO = números desta corrida; os critérios de «aceitável» estão em `CRITERIO` (constantes, fixadas antes de medir).

    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_vento.py --rapido
    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_vento.py            # grava out/vento_classico/avaliacao.json
    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_vento.py --calibrar
    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_vento.py --so 'const_5|natural' --variantes cascata
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]
from lab import mjkit  # noqa: F401, I001

import numpy as np

import avaliar_classico as ac
import avaliar_nucleo as an
import sitl
import vento_natural

SAIDA_JSON = _AQUI / "out" / "vento_classico" / "avaliacao.json"
SEMENTES_AVALIACAO = ac.SEMENTES_AVALIACAO          # 5000…5011 (as da B0)
SEMENTES_CALIBRACAO = ac.SEMENTES_CALIBRACAO        # 9000…9007 — NUNCA entram na avaliação
SAL_VENTO = 0x7E                                    # o gerador do vento é default_rng([seed, SAL_VENTO])
T_HOVER, JANELA_HOVER = 30.0, (10.0, 30.0)          # s — como a B0
T_DEGRAU, T_LIGA = 30.0, 12.0                       # s — o vento liga-se aos 12 s (o drone já paira há 10 s)
T_SEGUIMENTO, T0_SEGUIMENTO = 20.0, ac.JANELA_SEGUIMENTO_T0
BANDA_RECUPERACAO_M = 0.10                          # «recuperou» = voltou a ficar a < 10 cm do ponto que segurava
JOBS_MAX = 8                                        # processos em paralelo no máximo (a máquina é partilhada)

# o «antes»: a Config da fase 1 no MESMO núcleo — sem observador de perturbação e com a velocidade do fluxo do estimador
# como estava (sem o braço ao CM nem o alinhamento com o giroscópio). Conferido bit a bit contra o código da fase 1.
# a lei da FASE 1 no núcleo de hoje: sem observador de perturbação nem correção do fluxo (2026-10-12) e com o laço
# vertical de antes de 2026-10-13 (razão 4, integral k²/4, sem modelo de seguimento, teto do coletivo 1,8)
GANHOS_FASE1: dict = {"w_pert": 0.0, "braco_fluxo": 0.0, "atraso_fluxo": 0,
                      "razao_vz": 4.0, "razao_integral_z": 4.0, "tau_modelo_z": 0.0, "coletivo_teto": 1.8}
# só a VERTICAL de antes (o observador de perturbação fica): a cascata publicada em 2026-10-12, para o antes × depois
GANHOS_VERTICAL_ANTIGA: dict = {"razao_vz": 4.0, "razao_integral_z": 4.0, "tau_modelo_z": 0.0, "coletivo_teto": 1.8}

# critério de «voo aceitável» (para o ENVELOPE): 100 % de sobrevivência E, na pior semente, a pairar…
CRITERIO = {"xy_max": 0.50,        # m — desvio horizontal máximo na janela de pairagem (¼ do entre-eixos de 1,95 m)
            "xy_max_voo": 1.00,    # m — idem no voo TODO (a descolagem contra o vento incluída)
            "dz_max": 0.30}        # m — desvio de altitude máximo na janela

DIRECOES = {"frente": (180.0, 0.0), "lado": (90.0, 0.0), "subida": (45.0, 30.0), "descida": (270.0, -30.0)}
INTENSIDADES = (1.0, 2.0, 3.0, 4.0, 5.0)


# ------------------------------------------------------------------------------------------------ a «aleatoriedade»
SIGMA_REL_TURBULENCIA = 0.2      # σ/W da turbulência recomendada (Dryden de baixa altitude: σ_u = 2·σ_w = 0,2·W₂₀)
L_TURBULENCIA_M = 8.0            # m — escala de comprimento longitudinal de Dryden a 1 m de altura (7,84 m, arredondada)
ALTURA_REFERENCIA_M = 1.0        # m — a altura a que o drone paira (`alvo_z`)
PES_POR_METRO = 1.0 / 0.3048


def dryden_baixa_altitude(h_m: float) -> tuple[float, float]:
    """(σ_u/σ_w, L_u [m]) do modelo de turbulência de Dryden de BAIXA ALTITUDE (MIL-F-8785C §3.7.3 / MIL-HDBK-1797,
    h < 1000 ft; h em pés nas fórmulas): σ_w = 0,1·W₂₀, σ_u/σ_w = 1/(0,177 + 0,000823·h)^0,4 e
    L_u = h/(0,177 + 0,000823·h)^1,2. A 1 m: σ_u = 1,99·σ_w = 0,199·W₂₀ e L_u = 7,84 m."""
    h = float(h_m) * PES_POR_METRO
    base = 0.177 + 0.000823 * h
    return 1.0 / base ** 0.4, (h / base ** 1.2) / PES_POR_METRO


def turbulencia_de(w: float, sigma_rel: float = SIGMA_REL_TURBULENCIA, L: float = L_TURBULENCIA_M) -> dict:
    """O dict de `definir_vento_dinamico` da TURBULÊNCIA para um vento médio `w` [m/s] — a «aleatoriedade» do site:

        {"modo": "dryden", "sigma": 0,2·W, "L": 8,0, "u_max": 1,6·W, "v_min": 1,0}

    Dryden de baixa altitude (`dryden_baixa_altitude`): junto ao solo σ_u = σ_v = 2·σ_w = 0,2·W₂₀ — uma intensidade de
    turbulência de 20 % do vento médio (terreno aberto e plano; 30 % é o caso de terreno rugoso, medido à parte como
    `dryden30_*`) — e L_u = 7,84 m ≈ 8 m à altura de pairagem (1 m). O modo `dryden` do env é um processo de
    Ornstein–Uhlenbeck por componente, α = exp(−Δt·V/L), V = max(W, v_min): é EXATAMENTE o filtro de Dryden longitudinal
    (1.ª ordem, constante de tempo L/V) e aproxima os transversais (2.ª ordem) pelo mesmo; a componente vertical leva o
    mesmo σ (na norma é metade): conservador. `u_max` = W + 3σ só corta a cauda de 0,3 % (a norma do vento satura aí).
    """
    sigma = max(sigma_rel * float(w), 1e-3)
    return {"modo": "dryden", "sigma": sigma, "L": float(L), "u_max": float(w) + 3.0 * sigma, "v_min": 1.0}


def rajadas_de(w: float, amp_rel: float = 0.5, L: float = L_TURBULENCIA_M, intervalo_s: float = 8.0) -> dict:
    """RAJADAS discretas para um vento médio `w`: meia-onda de seno (≈ «1 − cos» da MIL-F-8785C) de amplitude
    U[0, amp_rel·W] (fator de rajada até 1 + amp_rel) e comprimento L ⇒ duração L/W [s]; uma a cada `intervalo_s` s em média."""
    w = max(float(w), 1e-3)
    dur = max(1, round(L / max(w, 1.0) / 0.02))
    return {"modo": "rajadas", "p": min(1.0, 0.02 / intervalo_s), "duracao": int(dur), "u_max": amp_rel * w}


def _regimes() -> dict:
    r: dict = {"calmo": {"tarefa": "hover"}}
    for w in INTENSIDADES:
        for nome, (az, el) in DIRECOES.items():
            r[f"const_{w:g}_{nome}"] = {"tarefa": "hover", "base": (w, az, el), "w": w}
    for w in INTENSIDADES:
        r[f"degrau_{w:g}_lado"] = {"tarefa": "degrau", "liga": (w, 90.0, 0.0), "w": w}
    for w in (3.0, 5.0):
        r[f"degrau_{w:g}_subida"] = {"tarefa": "degrau", "liga": (w, 45.0, 30.0), "w": w}
        r[f"frente_{w:g}"] = {"tarefa": "degrau", "dinamico": {"modo": "frente", "t_s": T_LIGA, "u_max": w}, "w": w}
    for w in INTENSIDADES:
        r[f"dryden_{w:g}"] = {"tarefa": "hover", "base": (w, 90.0, 0.0), "dinamico": turbulencia_de(w), "w": w}
    for w in (3.0, 4.0, 5.0):
        r[f"dryden30_{w:g}"] = {"tarefa": "hover", "base": (w, 90.0, 0.0), "dinamico": turbulencia_de(w, 0.3), "w": w}
        r[f"rajadas_{w:g}"] = {"tarefa": "hover", "base": (w, 90.0, 0.0), "dinamico": rajadas_de(w), "w": w}
        r[f"rajadas_curtas_{w:g}"] = {"tarefa": "hover", "base": (w, 90.0, 0.0), "w": w,
                                      "dinamico": {"modo": "rajadas", "p": 0.02, "duracao": 10, "u_max": w}}
    for w in (0.0, 3.0, 5.0):
        r[f"aleatoria_{w:g}"] = {"tarefa": "hover", "base": (w, 90.0, 0.0) if w else None, "w": w,
                                 "dinamico": {"modo": "aleatoria", "p": 0.02, "duracao": 10}}
        r[f"aleatoria_longa_{w:g}"] = {"tarefa": "hover", "base": (w, 90.0, 0.0) if w else None, "w": w,
                                       "dinamico": {"modo": "aleatoria", "p": 0.02, "duracao": 50}}
    r["seg_calmo"] = {"tarefa": "seguimento"}
    for w in INTENSIDADES:
        r[f"seg_const_{w:g}"] = {"tarefa": "seguimento", "base": (w, 90.0, 0.0), "w": w}
    for w in (3.0, 5.0):
        r[f"seg_dryden_{w:g}"] = {"tarefa": "seguimento", "base": (w, 90.0, 0.0), "dinamico": turbulencia_de(w), "w": w}
    # degrau de COMANDO (0 → 1 m/s em frente aos 6 s; o da B0): a resposta ao piloto não pode piorar com o observador
    r["cmd_frente"] = {"tarefa": "comando", "comando": V_COMANDO}
    r["cmd_frente_3"] = {"tarefa": "comando", "comando": V_COMANDO, "base": (3.0, 90.0, 0.0), "w": 3.0}
    # degrau de SUBIDA (0 → 0,7 m/s, o da B0): a janela é curta porque o ToF só mede até 3,6 m (teto de altitude 3,24 m)
    r["cmd_subida"] = {"tarefa": "comando", "comando": V_SUBIDA, "janela": JANELA_SUBIDA}
    # o vento ALEATÓRIO do cockpit: o gerador `vento_natural.VentoNatural` (intensidade W, aleatoriedade LIGADA — média W
    # de lado + turbulência + rajadas 1 − cos + direção a deambular), com a semente do episódio; liga-se aos 0 s (rampa)
    for w in INTENSIDADES:
        r[f"natural_{w:g}"] = {"tarefa": "hover", "natural": (w, 90.0), "w": w}
    for w in (3.0, 5.0):
        r[f"seg_natural_{w:g}"] = {"tarefa": "seguimento", "natural": (w, 90.0), "w": w}
    return r


V_COMANDO = (1.0, 0.0, 0.0)                        # m/s — o degrau de velocidade «frente» da B0
T_COMANDO, JANELA_COMANDO = 6.0, 8.0               # s — instante do degrau e janela de medida (como `ac.DEGRAUS`)
V_SUBIDA, JANELA_SUBIDA = (0.0, 0.0, 0.7), 3.0     # m/s, s — o degrau de subida da B0 (1 m → 3,1 m, abaixo do teto do ToF)
REGIMES = _regimes()
REGIMES_RAPIDOS = ("calmo", "const_3_lado", "const_5_lado", "degrau_3_lado", "natural_3", "seg_const_3", "cmd_frente")
# a corrida PUBLICADA (`out/vento_classico/avaliacao.json`): o que o cockpit oferece — vento constante e aleatório
# (`natural_*`) de 1 a 5 m/s — mais as direções com componente vertical, o degrau de vento, o seguimento e o comando.
# Os modos dinâmicos do env (`dryden_*`, `rajadas_*`, `aleatoria_*`, `frente_*`) continuam disponíveis com `--so`.
REGIMES_PUBLICADOS = ("calmo", *(f"const_{w:g}_lado" for w in INTENSIDADES), *(f"natural_{w:g}" for w in INTENSIDADES),
                      *(f"const_{w:g}_{d}" for w in (3.0, 5.0) for d in ("frente", "subida", "descida")), "const_4_descida",
                      "degrau_3_lado", "degrau_5_lado", "seg_calmo", "seg_const_3", "seg_natural_3", "seg_natural_5",
                      "cmd_frente")
# a varredura de CALIBRAÇÃO (`--calibrar`): variantes do núcleo (ganhos_kw) × regimes, nas sementes 9000…
REGIMES_CALIBRACAO = ("calmo", "cmd_frente", "seg_calmo", "degrau_3_lado", "const_5_lado", "dryden_3", "dryden_5", "seg_const_3")
VARIANTES_CALIBRACAO = {
    "fase 1 (sem observador; fluxo como estava)": GANHOS_FASE1,
    "padrão (banda ω_c; modelo com atraso; braço + alinhamento do fluxo)": {},
    "banda K_att (razão 2,5)": {"razao_pert": 2.5},
    "banda ω_c/1,5": {"razao_pert": 1.5},
    "banda 1,4·ω_c (razão 0,7)": {"razao_pert": 0.7},
    "sem o atraso da medida no modelo (τ_vel = 0)": {"tau_vel": 0.0},
    "sem braço nem alinhamento do fluxo": {"braco_fluxo": 0.0, "atraso_fluxo": 0},
    "só braço + alinhamento do fluxo (sem observador)": {"w_pert": 0.0},
}

CHAVES = {
    "hover": ("xy_rms", "xy_med", "xy_p95", "xy_max", "xy_max_voo", "dz_rms", "dz_max", "incl_rms_graus", "incl_max_graus", "rumo_max_graus",
              "frac_saturado", "u_max", "du_rms", "p_media_w", "est_vel_rms", "est_atitude_rms_graus", "est_deriva_rms",
              "pert_rms", "pert_max", "i_vel_max", "frac_i_limite", "frac_sat_incl", "a_des_xy_max", "i_z_max",
              "coletivo_max", "w_medio", "w_dp", "w_max"),
    "degrau": ("pico", "t_recuperacao_s", "residuo", "dz_max", "incl_max_graus", "rumo_max_graus", "frac_saturado",
               "u_max", "du_rms", "est_vel_rms", "pert_max", "i_vel_max", "frac_sat_incl", "w_max"),
    "seguimento": ("v_rms", "xy_rms", "xy_max", "z_rms", "incl_max_graus", "rumo_max_graus", "frac_saturado", "u_max",
                   "du_rms", "est_vel_rms", "pert_max", "i_vel_max", "frac_sat_incl", "w_max"),
    "comando": ("sobressinal", "subida_10_90_s", "assenta_5pct_s", "erro_regime", "afundamento", "incl_max_graus",
                "du_rms", "est_vel_rms"),
}
# métricas em que «não aconteceu na janela» (inf) fica fora da média e é contada em `_n`
CHAVES_INFINITAS = ("t_recuperacao_s", "assenta_5pct_s")


# ------------------------------------------------------------------------------------------------ vento pareado
class VentoPareado:
    """Avança o vento DINÂMICO do env (o `_passo_vento` do próprio `HoverEnv`) com um gerador aleatório PRÓPRIO.

    O env chama `_passo_vento` no fim do `reset` (passo 1) e no início de cada `step`, com o `np_random` que também
    alimenta o ruído dos sensores. Para a série de vento não depender de QUANTOS números a planta já consumiu (o núcleo
    calibra 1 s no chão; a RL não), troca-se o gerador só durante essas chamadas: depois do `reset` re-sorteia-se o
    arranque (`_reinicia_dinamico` + passo 1) e antes de cada `step` avança-se um passo — o `step` do env vê
    `_din_passo` já em dia e não volta a sortear. O vento base (`definir_vento`) não tem acaso: não precisa disto.
    """

    def __init__(self, env, seed: int):
        self.env = env
        self.rng = np.random.default_rng([int(seed), SAL_VENTO])
        self.ativo = env.vento_dinamico is not None

    @contextlib.contextmanager
    def _gerador(self):
        env = self.env
        original = env.np_random
        env.np_random = self.rng
        try:
            yield
        finally:
            env.np_random = original

    def depois_do_reset(self) -> None:
        if not self.ativo:
            return
        with self._gerador():
            self.env._reinicia_dinamico()
            self.env._passo_vento()

    def antes_do_passo(self) -> None:
        env = self.env
        if self.ativo and env.vento_dinamico is not None and env._din_passo < env.passos + 1:
            with self._gerador():
                env._passo_vento()


# ------------------------------------------------------------------------------------------------ um episódio
def criar(variante: str, dados: dict, T: float, aleatorios: bool, ganhos_kw: dict | None = None, dr: bool = False):
    """(env, controlador) da variante — a planta é a MESMA; só muda quem estima e controla."""
    if variante == "rl":
        return ac.criar_env(dados, dr=dr, episodio_s=T, aleatorios=aleatorios), ac.ControladorRL(ac.rl_cache()[0])
    if variante == "python":
        env = ac.criar_env(dados, dr=dr, episodio_s=T, aleatorios=aleatorios)
        gn = an.ganhos_nominais(dados, an.u_yaw_identificado()).com(**(ganhos_kw or {}))
        return env, ac.ControladorCascata(ganhos=gn, estimador="melhorado")
    kw = dict({"cascata_fase1": GANHOS_FASE1, "cascata_vz_antiga": GANHOS_VERTICAL_ANTIGA}.get(variante, {}))
    kw.update(ganhos_kw or {})
    env = an.criar_env_nucleo(dados, dr=dr, episodio_s=T, aleatorios=aleatorios, cascata={"ganhos_kw": kw})
    return env, sitl.ControladorNucleo()


def correr(env, ctrl, seed: int, T: float, regime: dict) -> dict:
    """Um episódio com o vento do `regime`: devolve o registo por decisão (arrays) — como `avaliar_classico.correr`,
    mais o vento, a perturbação aerodinâmica verdadeira e o estado da cascata (só no núcleo)."""
    base, din, liga = regime.get("base"), regime.get("dinamico"), regime.get("liga")
    v_cmd = np.array(regime["comando"], dtype=float) if regime.get("comando") else None
    gerador = None
    if regime.get("natural"):                       # o vento dos 3 botões do cockpit, como o runner o aplica (passo a passo)
        gerador = vento_natural.VentoNatural(semente=int(seed))
        gerador.definir(True, float(regime["natural"][0]), True, float(regime["natural"][1]))
    if base:
        env.definir_vento(*base)
    if din:
        env.definir_vento_dinamico(din)
    ctrl.preparar(env)
    env.reset(seed=seed)
    vento = VentoPareado(env, seed)
    vento.depois_do_reset()
    ctrl.reiniciar(env, None)                       # (a calibração no chão do protótipo Python acontece aqui)
    sonda = ac.SondaFC(env.fc)
    nucleo = getattr(env, "nucleo", None)
    casc = getattr(ctrl, "casc", None)
    lim_i = float(nucleo.cfg.cascata.lim_i_vel) if nucleo is not None else float("nan")
    pl = env.planta
    cols = ("t", "x", "y", "z", "phi", "theta", "yaw", "vx", "vy", "vz", "xr", "yr", "zr", "vxr", "vyr", "vzr",
            "ex", "ey", "e_roll", "e_pitch", "e_vx", "e_vy", "p_w", "s_n", "s_sat", "u_max", "w", "px", "py",
            "ix", "iy", "iz", "adx", "ady", "col", "sat_incl")
    buf = {c: [] for c in cols}
    n_max = round(T / env.dt_decisao)
    k_liga = round(T_LIGA / env.dt_decisao) if liga else -1
    terminou = False
    u_pico = 0.0
    orig = env.fc.passo

    def passo_com_pico(*a, **k):                    # o motor mais carregado de cada passo de 2 ms
        nonlocal u_pico
        u = orig(*a, **k)
        u_pico = max(u_pico, float(u.max()))
        return u

    env.fc.passo = passo_com_pico
    for k in range(n_max):
        t = k * env.dt_decisao
        if k == k_liga:
            env.definir_vento(*liga)
        if v_cmd is not None:                       # degrau de comando (referencial do mundo, como a B0)
            env.definir_comando(v_cmd if t >= T_COMANDO else np.zeros(3))
        if gerador is not None:                     # (gerador próprio, com a semente do episódio: o mesmo vento para todos)
            env.definir_vento(*vento_natural.polar_do_vetor(gerador.passo(env.dt_decisao)))
        vento.antes_do_passo()
        a = ctrl.acao(env, t)
        _obs, _r, term, _trunc, info = env.step(a)
        d = env._derivados()
        est = env.estimador
        # perturbação aerodinâmica VERDADEIRA: a força específica no plano x,y do CORPO (o empuxo não tem componente aí),
        # rodada para o mundo — o que o controlo tem de anular
        f = pl.imu.verdade()[1]
        cf, sf, ct, st = math.cos(d["phi"]), math.sin(d["phi"]), math.cos(d["theta"]), math.sin(d["theta"])
        cp, sp = math.cos(d["yaw"]), math.sin(d["yaw"])
        pwx = cp * ct * f[0] + (cp * st * sf - sp * cf) * f[1]
        pwy = sp * ct * f[0] + (sp * st * sf + cp * cf) * f[1]
        if nucleo is not None:
            s = nucleo.saida
            diag = (s.i_vel[0], s.i_vel[1], s.i_z, s.a_des[0], s.a_des[1], s.coletivo,
                    1.0 if int(s.flags) & sitl.FLAG_SAT_INCLINACAO else 0.0)
        elif casc is not None and casc.dados:
            dd = casc.dados
            diag = (*dd["i_vel"], dd["i_z"], dd["a_des"][0], dd["a_des"][1], dd["coletivo"], 1.0 if dd["sat_incl"] else 0.0)
        else:
            diag = (float("nan"),) * 7
        fila = (t + env.dt_decisao, d["x"], d["y"], d["z"], d["phi"], d["theta"], d["yaw"], *d["v_vec"], *env.p_ref,
                *env.v_ref, est.x, est.y, est.roll, est.pitch, est.vx, est.vy, info["p_total"], sonda.n, sonda.sat,
                u_pico, float(np.linalg.norm(env.vento_atual)), pwx, pwy, *diag)
        for c, v in zip(cols, fila, strict=True):
            buf[c].append(float(v))
        if term:
            terminou = True
            break
    reg = {c: np.array(v) for c, v in buf.items()}
    reg.update({"terminou": terminou, "yaw0": float(env.yaw0), "n": len(reg["t"]), "T": T, "dt": env.dt_decisao,
                "lim_i": lim_i, "du_rms": sonda.resumo()["du_rms"]})
    return reg


def _rms(v) -> float:
    v = np.asarray(v, dtype=float)
    return float(np.sqrt(np.mean(v * v))) if v.size else float("nan")


def _maxabs(v) -> float:
    v = np.asarray(v, dtype=float)
    return float(np.abs(v).max()) if v.size else float("nan")


def _comuns(reg: dict, m) -> dict:
    """Métricas comuns às três tarefas, na janela `m`: atitude, rumo, motores, estimador, perturbação, cascata, vento."""
    incl = np.arccos(np.clip(np.cos(reg["phi"]) * np.cos(reg["theta"]), -1.0, 1.0))
    yaw_rel = np.unwrap(reg["yaw"]) - reg["yaw0"]
    idx = np.nonzero(m)[0]
    i0, i1 = max(idx[0] - 1, 0), idx[-1]
    n_fis = max(reg["s_n"][i1] - reg["s_n"][i0], 1.0)
    c, s = math.cos(reg["yaw0"]), math.sin(reg["yaw0"])
    deriva = np.hypot(reg["x"] - (reg["x"][0] + c * reg["ex"] - s * reg["ey"]),
                      reg["y"] - (reg["y"][0] + s * reg["ex"] + c * reg["ey"]))
    cf, sf, ct, st = np.cos(reg["phi"]), np.sin(reg["phi"]), np.cos(reg["theta"]), np.sin(reg["theta"])
    cp, sp = np.cos(reg["yaw"]), np.sin(reg["yaw"])
    vbx = cp * ct * reg["vx"] + sp * ct * reg["vy"] - st * reg["vz"]
    vby = (cp * st * sf - sp * cf) * reg["vx"] + (sp * st * sf + cp * cf) * reg["vy"] + ct * sf * reg["vz"]
    pert = np.hypot(reg["px"], reg["py"])
    i_norma = np.maximum(np.abs(reg["ix"]), np.abs(reg["iy"]))
    return {"incl_rms_graus": math.degrees(_rms(incl[m])), "incl_max_graus": math.degrees(float(incl[m].max())),
            "rumo_max_graus": math.degrees(_maxabs(yaw_rel[m])),
            "frac_saturado": float((reg["s_sat"][i1] - reg["s_sat"][i0]) / n_fis), "u_max": float(reg["u_max"][i1]),
            "p_media_w": float(np.mean(reg["p_w"][m])), "du_rms": float(reg["du_rms"]),
            "est_vel_rms": _rms(np.hypot(reg["e_vx"] - vbx, reg["e_vy"] - vby)[m]),
            "est_atitude_rms_graus": math.degrees(_rms(np.hypot(reg["e_roll"] - reg["phi"], reg["e_pitch"] - reg["theta"])[m])),
            "est_deriva_rms": _rms(deriva[m]),
            "pert_rms": _rms(pert[m]), "pert_max": float(pert[m].max()),
            "i_vel_max": float(np.hypot(reg["ix"], reg["iy"])[m].max()),
            "frac_i_limite": float(np.mean(i_norma[m] >= 0.999 * reg["lim_i"])) if math.isfinite(reg["lim_i"]) else float("nan"),
            "frac_sat_incl": float(np.mean(reg["sat_incl"][m])), "a_des_xy_max": float(np.hypot(reg["adx"], reg["ady"])[m].max()),
            "i_z_max": _maxabs(reg["iz"][m]), "coletivo_max": float(reg["col"][m].max()),
            "w_medio": float(np.mean(reg["w"][m])), "w_dp": float(np.std(reg["w"][m])), "w_max": float(reg["w"][m].max())}


def metricas(reg: dict, tarefa: str, regime: dict | None = None) -> dict:
    t = reg["t"]
    regime = regime or {}
    if reg["terminou"]:
        return {"terminou": True, "t_fim": float(t[-1]) if len(t) else 0.0}
    if tarefa == "hover":
        m = (t >= JANELA_HOVER[0]) & (t <= JANELA_HOVER[1])
        dxy = np.hypot(reg["x"], reg["y"])
        dz = reg["z"] - reg["zr"]
        return {"terminou": False, **_comuns(reg, m), "xy_rms": _rms(dxy[m]), "xy_max": float(dxy[m].max()),
                "xy_med": float(np.median(dxy[m])), "xy_p95": float(np.percentile(dxy[m], 95.0)),
                "xy_max_voo": float(dxy.max()), "dz_rms": _rms(dz[m]), "dz_max": _maxabs(dz[m])}
    if tarefa == "degrau":
        pre = (t >= T_LIGA - 2.0) & (t <= T_LIGA)
        m = t > T_LIGA
        x0, y0 = float(np.mean(reg["x"][pre])), float(np.mean(reg["y"][pre]))
        dev = np.hypot(reg["x"] - x0, reg["y"] - y0)[m]
        ts = t[m] - T_LIGA
        fora = np.nonzero(dev > BANDA_RECUPERACAO_M)[0]
        if fora.size == 0:
            t_rec = 0.0
        elif fora[-1] >= len(ts) - 1:
            t_rec = float("inf")                    # nunca voltou a ficar dentro da banda
        else:
            t_rec = float(ts[fora[-1] + 1])
        return {"terminou": False, **_comuns(reg, m), "pico": float(dev.max()), "t_recuperacao_s": t_rec,
                "residuo": float(np.mean(dev[ts >= ts[-1] - 3.0])), "dz_max": _maxabs((reg["z"] - reg["zr"])[m])}
    if tarefa == "seguimento":
        m = t >= T0_SEGUIMENTO
        exy = np.hypot(reg["x"] - reg["xr"], reg["y"] - reg["yr"])[m]
        ev = np.stack([reg["vx"] - reg["vxr"], reg["vy"] - reg["vyr"], reg["vz"] - reg["vzr"]])[:, m]
        return {"terminou": False, **_comuns(reg, m), "v_rms": _rms(np.linalg.norm(ev, axis=0)), "xy_rms": _rms(exy),
                "xy_max": float(exy.max()), "z_rms": _rms((reg["z"] - reg["zr"])[m])}
    if tarefa == "comando":                         # as métricas do degrau de velocidade da B0 (`ac.metricas_degrau`)
        janela = float(regime.get("janela", JANELA_COMANDO))
        m = (t >= T_COMANDO) & (t <= T_COMANDO + janela)
        d = ac.metricas_degrau(reg, T_COMANDO, np.array(regime.get("comando", V_COMANDO), dtype=float), janela)
        return {**{k: d[k] for k in ("terminou", "sobressinal", "subida_10_90_s", "assenta_5pct_s", "erro_regime", "afundamento")},
                **{k: v for k, v in _comuns(reg, m).items() if k in CHAVES["comando"]}}
    raise ValueError(f"tarefa desconhecida: {tarefa}")


def episodio(job: dict) -> dict:
    """Um episódio → métricas (função de topo: serializável para o `multiprocessing`)."""
    t0 = time.perf_counter()
    regime = job.get("spec") or REGIMES[job["regime"]]
    tarefa = regime["tarefa"]
    T = job.get("T") or {"hover": T_HOVER, "degrau": T_DEGRAU, "seguimento": T_SEGUIMENTO,
                         "comando": T_COMANDO + float(regime.get("janela", JANELA_COMANDO)) + 0.5}[tarefa]
    dados = ac.carregar_rl_dados()
    env, ctrl = criar(job["variante_base"], dados, T, tarefa == "seguimento", job.get("ganhos_kw"), job.get("dr", False))
    reg = correr(env, ctrl, job["seed"], T, regime)
    env.close()
    out = metricas(reg, tarefa, regime)
    if job.get("series"):
        out["series"] = {c: reg[c].tolist() for c in job["series"]}
    out.update({"regime": job["regime"], "variante": job["variante"], "seed": job["seed"],
                "parede_s": time.perf_counter() - t0})
    return out


# ------------------------------------------------------------------------------------------------ execução e agregação
def executar(jobs: list[dict], n_jobs: int) -> list[dict]:
    if n_jobs <= 1:
        return [episodio(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=n_jobs, initializer=ac._init_worker) as ex:
        return list(ex.map(episodio, jobs, chunksize=1))


def agregar(res: list[dict], chaves: tuple[str, ...]) -> dict:
    """Média, desvio-padrão, mediana e PIOR semente por métrica, sobre as sementes que SOBREVIVERAM; `quedas` à parte."""
    vivos = [r for r in res if not r.get("terminou")]
    out: dict = {"n": len(res), "quedas": len(res) - len(vivos),
                 "sementes_com_queda": sorted(r["seed"] for r in res if r.get("terminou"))}
    for c in chaves:
        v = np.array([r[c] for r in vivos if r.get(c) is not None and np.isfinite(r[c])], dtype=float)
        out[c] = float(np.mean(v)) if v.size else float("nan")
        out[c + "_dp"] = float(np.std(v)) if v.size else float("nan")
        out[c + "_med"] = float(np.median(v)) if v.size else float("nan")
        out[c + "_pior"] = float(np.max(v)) if v.size else float("nan")
        if c in CHAVES_INFINITAS:
            out[c + "_n"] = int(v.size)
    out["por_semente"] = [{"seed": r["seed"], "terminou": bool(r.get("terminou")), **{c: r.get(c) for c in chaves}}
                          for r in res]
    return out


def avaliar(regimes: list[str], variantes: dict[str, dict], sementes, n_jobs: int, verboso: bool = True) -> dict:
    """{regime: {variante: agregado}}. `variantes` = nome → {"base": variante de `criar`, "ganhos_kw": {...}}."""
    jobs = [{"regime": r, "variante": v, "variante_base": spec.get("base", v), "ganhos_kw": spec.get("ganhos_kw"),
             "dr": spec.get("dr", False), "seed": s}
            for r in regimes for v, spec in variantes.items() for s in sementes]
    t0 = time.perf_counter()
    res = executar(jobs, n_jobs)
    if verboso:
        print(f"  {len(jobs)} episódios em {time.perf_counter() - t0:.0f} s ({n_jobs} processos)", flush=True)
    out: dict = {}
    for r in regimes:
        out[r] = {}
        for v in variantes:
            sel = [x for x in res if x["regime"] == r and x["variante"] == v]
            out[r][v] = agregar(sel, CHAVES[REGIMES[r]["tarefa"]])
    return out


def aceitavel(g: dict) -> bool:
    """O regime é «voável» para esta variante? 100 % de sobrevivência e a pior semente dentro de `CRITERIO`."""
    return g["quedas"] == 0 and all(g.get(k + "_pior", float("inf")) <= lim for k, lim in CRITERIO.items())


def sobrevive(g: dict) -> bool:
    """Nenhuma semente terminou (queda, capotamento, teto, brownout)."""
    return g["quedas"] == 0


# famílias de regimes de PAIRAGEM com intensidade W (o envelope é a maior W em que a família inteira passa)
FAMILIAS = {
    "constante_horizontal": lambda n: n.startswith("const_") and n.endswith(("_frente", "_lado")),
    "aleatorio": lambda n: n.startswith("natural_"),                 # o gerador do cockpit (`vento_natural`)
    "constante_ascendente": lambda n: n.startswith("const_") and n.endswith("_subida"),
    "constante_descendente": lambda n: n.startswith("const_") and n.endswith("_descida"),
    "turbulencia_env": lambda n: n.startswith("dryden_"),
    "rajadas_env": lambda n: n.startswith(("rajadas_", "rajadas_curtas_")),
}


def envelope(resultados: dict, variante: str, familia, criterio=aceitavel) -> dict:
    """A maior intensidade W tal que TODOS os regimes da `familia` (predicado sobre o nome) até W, inclusive, cumprem o
    `criterio` (`aceitavel` ou `sobrevive`) para a variante. Só conta se a família foi medida a partir da menor W dela."""
    por_w: dict[float, bool] = {}
    for nome, por_var in resultados.items():
        if variante not in por_var or not familia(nome) or "w" not in REGIMES.get(nome, {}):
            continue
        w = REGIMES[nome]["w"]
        por_w[w] = por_w.get(w, True) and criterio(por_var[variante])
    w_ok = None
    for w in sorted(por_w):
        if not por_w[w]:
            break
        w_ok = w
    return {"w_max": w_ok, "w_min_medida": min(por_w) if por_w else None,
            "por_intensidade": {f"{w:g}": bool(ok) for w, ok in sorted(por_w.items())}}


def envelopes(resultados: dict, variantes) -> dict:
    return {v: {nome: {"aceitavel": envelope(resultados, v, f, aceitavel), "sobrevive": envelope(resultados, v, f, sobrevive)}
                for nome, f in FAMILIAS.items()} for v in variantes}


def recomendacao_site(resultados: dict, variante: str = "cascata") -> dict:
    """O TETO do slider de intensidade do cockpit, tirado das medições desta corrida para a `variante` (a cascata que voa
    por omissão): a maior W em que o vento CONSTANTE horizontal E o ALEATÓRIO do gerador do cockpit passam os dois —
    `teto_sem_quedas` (nenhuma semente cai) e `teto_aceitavel` (além disso, a pior semente dentro de `CRITERIO`)."""
    env_ = envelopes(resultados, [variante])[variante]

    def teto(criterio: str):
        ws = [env_[f][criterio]["w_max"] for f in ("constante_horizontal", "aleatorio") if env_[f][criterio]["w_min_medida"] is not None]
        return None if not ws or any(w is None for w in ws) else min(ws)
    com_w = [n for n in resultados if "w" in REGIMES.get(n, {}) and variante in resultados[n]]
    quedas = {n: resultados[n][variante]["quedas"] for n in com_w if resultados[n][variante]["quedas"]}
    return {"variante": variante, "teto_sem_quedas_m_s": teto("sobrevive"), "teto_aceitavel_m_s": teto("aceitavel"),
            "regimes_com_quedas": quedas, "envelope": env_,
            "gerador": {"modulo": "vento_natural.VentoNatural", "intensidade_max_atual": vento_natural.INTENSIDADE_MAX,
                        "teto_fator": vento_natural.TETO_FATOR, "sigma_h": vento_natural.SIGMA_H, "sigma_w": vento_natural.SIGMA_W,
                        "rajada_amp": list(vento_natural.RAJADA_AMP), "rajada_intervalo_s": vento_natural.RAJADA_INTERVALO_S}}


# ------------------------------------------------------------------------------------------------ relatório
def _f(g: dict, c: str, casas: int = 1, mult: float = 1.0, pior: bool = True) -> str:
    v = g.get(c)
    if v is None or not math.isfinite(v):
        return "—"
    txt = f"{mult * v:.{casas}f}±{mult * g[c + '_dp']:.{casas}f}"
    return txt + (f" (pior {mult * g[c + '_pior']:.{casas}f})" if pior else "")


def imprimir(resultados: dict, variantes: list[str]) -> None:
    grupos = {"hover": [("‖xy‖ mediana cm", "xy_med", 1, 100.0), ("‖xy‖ p95 cm", "xy_p95", 1, 100.0),
                        ("‖xy‖ máx. cm", "xy_max", 1, 100.0), ("‖xy‖ máx. do voo cm", "xy_max_voo", 0, 100.0),
                        ("|Δz| máx. cm", "dz_max", 1, 100.0), ("inclinação máx. °", "incl_max_graus", 1, 1.0),
                        ("sat. motores %", "frac_saturado", 2, 100.0)],
              "degrau": [("pico cm", "pico", 1, 100.0), ("recuperação s", "t_recuperacao_s", 1, 1.0),
                         ("resíduo cm", "residuo", 1, 100.0), ("|Δz| máx. cm", "dz_max", 1, 100.0)],
              "seguimento": [("‖v−v_ref‖ RMS m/s", "v_rms", 3, 1.0), ("‖xy−p_ref‖ RMS cm", "xy_rms", 1, 100.0),
                             ("‖xy−p_ref‖ máx. cm", "xy_max", 0, 100.0), ("|z−z_ref| RMS cm", "z_rms", 1, 100.0)],
              "comando": [("sobressinal %", "sobressinal", 1, 100.0), ("subida 10–90 % s", "subida_10_90_s", 2, 1.0),
                          ("assentamento 5 % s", "assenta_5pct_s", 2, 1.0), ("erro de regime m/s", "erro_regime", 3, 1.0),
                          ("afundamento %", "afundamento", 1, 100.0)]}
    for tarefa, linhas in grupos.items():
        nomes = [r for r in resultados if REGIMES[r]["tarefa"] == tarefa]
        if not nomes:
            continue
        print(f"\n#### {tarefa.upper()} — média±dp (pior semente) sobre as sementes que sobreviveram; quedas/n")
        print("| regime | variante | quedas | " + " | ".join(rot for rot, *_ in linhas) + " |")
        print("|---|---|---|" + "---|" * len(linhas))
        for r in nomes:
            for v in variantes:
                g = resultados[r].get(v)
                if g is None:
                    continue
                cel = []
                for _rot, c, casas, mult in linhas:
                    txt = _f(g, c, casas, mult)
                    if c in CHAVES_INFINITAS and g.get(c + "_n", g["n"]) < g["n"] - g["quedas"]:
                        txt += f" [{g[c + '_n']}/{g['n'] - g['quedas']} recuperam]"
                    cel.append(txt)
                print(f"| {r} | {v} | {g['quedas']}/{g['n']} | " + " | ".join(cel) + " |")


def imprimir_envelopes(env_: dict) -> None:
    def w(e):
        if e["w_min_medida"] is None:
            return "n/m"
        return f"<{e['w_min_medida']:g}" if e["w_max"] is None else f"{e['w_max']:g}"
    print("\nENVELOPE por família de regimes de pairagem — maior W (m/s) em que a família inteira passa: ACEITÁVEL = 100 % de "
          "sobrevivência e a pior semente dentro de " + ", ".join(f"{k} ≤ {v:g} m" for k, v in CRITERIO.items())
          + " · SOBREVIVE = nenhuma queda («<W» = já falha na menor W medida; n/m = família não medida nesta corrida)")
    print("| variante | " + " | ".join(FAMILIAS) + " |")
    print("|---|" + "---|" * len(FAMILIAS))
    for v, fam in env_.items():
        print(f"| {v} | " + " | ".join(f"{w(fam[f]['aceitavel'])} / {w(fam[f]['sobrevive'])}" for f in FAMILIAS) + " |")
    print("(cada célula: aceitável / sobrevive)")


def calibrar(args, dados: dict) -> int:
    """Varredura NAS SEMENTES DE CALIBRAÇÃO: é daqui que saem os números que justificam a banda do observador e cada peça
    do modelo (variantes do núcleo C++ por `ganhos_kw`; grava `calibracao.json` ao lado da avaliação)."""
    t0 = time.perf_counter()
    variantes = {nome: {"base": "cascata", "ganhos_kw": kw} for nome, kw in VARIANTES_CALIBRACAO.items()}
    print(f"CALIBRAÇÃO nas sementes {SEMENTES_CALIBRACAO[0]}..{SEMENTES_CALIBRACAO[-1]} (NÃO são as de avaliação) · "
          f"{len(variantes)} variantes × {len(REGIMES_CALIBRACAO)} regimes · {args.jobs} processos", flush=True)
    res = avaliar(list(REGIMES_CALIBRACAO), variantes, SEMENTES_CALIBRACAO, args.jobs)
    cols = [("pairar ‖xy‖ RMS cm", "calmo", "xy_rms", 100.0, 1), ("pairar inclin. RMS °", "calmo", "incl_rms_graus", 1.0, 2),
            ("comando sobressinal %", "cmd_frente", "sobressinal", 100.0, 1),
            ("comando assent. 5 % s", "cmd_frente", "assenta_5pct_s", 1.0, 2),
            ("seguimento ‖xy‖ cm", "seg_calmo", "xy_rms", 100.0, 1), ("degrau 3 m/s pico cm", "degrau_3_lado", "pico", 100.0, 1),
            ("recuperação s", "degrau_3_lado", "t_recuperacao_s", 1.0, 1),
            ("descolar a 5 m/s máx. cm", "const_5_lado", "xy_max_voo", 100.0, 0),
            ("turbulência 3 m/s RMS cm", "dryden_3", "xy_rms", 100.0, 1), ("turbulência 5 m/s RMS cm", "dryden_5", "xy_rms", 100.0, 1),
            ("seguimento com 3 m/s cm", "seg_const_3", "xy_rms", 100.0, 1)]
    print("\n| variante | quedas | " + " | ".join(c[0] for c in cols) + " |")
    print("|---|---|" + "---|" * len(cols))
    for v in variantes:
        q = sum(res[r][v]["quedas"] for r in REGIMES_CALIBRACAO)
        cel = [f"{m * res[r][v][c]:.{casas}f}" if math.isfinite(res[r][v][c]) else "—" for _rot, r, c, m, casas in cols]
        print(f"| {v} | {q} | " + " | ".join(cel) + " |")
    caminho = (args.json or SAIDA_JSON).with_name("calibracao.json")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(ac.limpar({
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "sementes_calibracao": list(SEMENTES_CALIBRACAO),
        "build": an.build_do_hardware(dados)[0], "variantes": VARIANTES_CALIBRACAO, "regimes": list(REGIMES_CALIBRACAO),
        "resultados": res, "duracao_s": time.perf_counter() - t0}), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {caminho} ({time.perf_counter() - t0:.0f} s)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--rapido", action="store_true", help="3 sementes e 7 regimes (fumo)")
    p.add_argument("--todos", action="store_true", help="TODOS os regimes (inclui os modos dinâmicos do env), não só os publicados")
    p.add_argument("--sementes", type=int, default=len(SEMENTES_AVALIACAO))
    p.add_argument("--calibracao", action="store_true", help="usa as sementes de CALIBRAÇÃO 9000… (não grava o JSON publicado)")
    p.add_argument("--calibrar", action="store_true",
                   help="varredura da banda do observador e das peças do modelo NAS SEMENTES DE CALIBRAÇÃO (grava calibracao.json) e sai")
    p.add_argument("--jobs", type=int, default=min(JOBS_MAX, (os.cpu_count() or 2) - 1))
    p.add_argument("--so", default=None, help="regex: só os regimes cujo nome casa (de TODOS, não só dos publicados)")
    p.add_argument("--variantes", default="cascata,cascata_fase1,rl")
    p.add_argument("--extra", action="append", default=[],
                   help="variante ad hoc: nome[:base]=JSON de ganhos_kw; base = cascata (omissão) | python "
                        "(ex.: lento='{\"razao_pert\": 2.5}' ou py:python='{}')")
    p.add_argument("--json", type=Path, default=None, help=f"omissão: {SAIDA_JSON.relative_to(_AQUI)} (só na corrida completa)")
    args = p.parse_args(argv)
    args.jobs = max(1, min(args.jobs, JOBS_MAX))      # a máquina é partilhada
    dados = ac.carregar_rl_dados()
    bib = sitl.biblioteca_padrao()                    # compila a .so UMA vez, antes de criar os processos
    if args.calibrar:
        return calibrar(args, dados)
    sementes = SEMENTES_CALIBRACAO if args.calibracao else SEMENTES_AVALIACAO
    sementes = sementes[:3] if args.rapido else sementes[: args.sementes]
    regimes = list(REGIMES_RAPIDOS) if args.rapido else list(REGIMES if args.todos else REGIMES_PUBLICADOS)
    if args.so:
        regimes = [r for r in REGIMES if re.search(args.so, r)]
    variantes: dict[str, dict] = {v: {"base": v} for v in args.variantes.split(",") if v}
    for e in args.extra:
        nome, _, txt = e.partition("=")
        nome, _, base = nome.partition(":")
        variantes[nome] = {"base": base or "cascata", "ganhos_kw": json.loads(txt)}
    completa = not (args.rapido or args.so or args.todos or args.calibracao or args.extra) \
        and args.sementes >= len(SEMENTES_AVALIACAO) and set(variantes) >= {"cascata", "cascata_fase1", "rl"}
    t0 = time.perf_counter()
    print(f"AVALIAÇÃO COM VENTO · build {an.build_do_hardware(dados)[0]!r} · sementes {sementes[0]}..{sementes[-1]} "
          f"({'CALIBRAÇÃO' if args.calibracao else 'avaliação'}) · {len(regimes)} regimes × {list(variantes)} · "
          f"{args.jobs} processos · núcleo interface v{sitl.versao_da_interface()} ({bib.caminho.name})", flush=True)
    resultados = avaliar(regimes, variantes, sementes, args.jobs)
    imprimir(resultados, list(variantes))
    cfg_c = an.criar_env_nucleo(dados, dr=False, episodio_s=1.0).nucleo.cfg.cascata
    saida = {"gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "build": an.build_do_hardware(dados)[0],
             "modelo_rl": str(ac.MODELO_RL.relative_to(_AQUI)), "sementes": list(sementes),
             "nucleo": {"versao_interface": sitl.versao_da_interface(), "estado_bytes": bib.tamanho_nucleo,
                        "observador": {k: getattr(cfg_c, k) for k in ("w_pert", "lim_pert", "tau_vel", "braco_fluxo", "atraso_fluxo")}},
             "protocolo": {"t_hover_s": T_HOVER, "janela_hover_s": list(JANELA_HOVER), "t_liga_s": T_LIGA,
                           "t_seguimento_s": T_SEGUIMENTO, "banda_recuperacao_m": BANDA_RECUPERACAO_M,
                           "t_comando_s": T_COMANDO, "janela_comando_s": JANELA_COMANDO,
                           "vento_pareado": f"default_rng([seed, {SAL_VENTO}])", "direcoes": DIRECOES},
             "criterio_aceitavel": CRITERIO, "ganhos_fase1": GANHOS_FASE1,
             "variantes": variantes, "regimes": {r: REGIMES[r] for r in regimes}, "resultados": resultados,
             "envelope": envelopes(resultados, variantes),
             "recomendacao_site": recomendacao_site(resultados) if "cascata" in variantes else None,
             "duracao_s": time.perf_counter() - t0}
    imprimir_envelopes(saida["envelope"])
    if saida["recomendacao_site"]:
        r = saida["recomendacao_site"]
        print(f"\nTETO DO SLIDER (vento constante horizontal E aleatório do `vento_natural`, cascata): sem quedas até "
              f"{r['teto_sem_quedas_m_s']} m/s · «aceitável» até {r['teto_aceitavel_m_s']} m/s"
              + (f" · regimes com quedas: {r['regimes_com_quedas']}" if r["regimes_com_quedas"] else " · nenhuma queda em nenhum regime medido"))
    caminho = args.json or (SAIDA_JSON if completa else None)
    if caminho is not None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(ac.limpar(saida), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n→ {caminho} ({saida['duracao_s']:.0f} s)")
    else:
        print(f"\n(corrida parcial: nada gravado; {saida['duracao_s']:.0f} s — use --json para gravar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
