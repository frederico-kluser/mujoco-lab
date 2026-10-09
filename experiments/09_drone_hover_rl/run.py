#!/usr/bin/env python3
"""Validação do ambiente de RL do drone (`experiments/09_drone_hover_rl/env.py`, CONTRATO v2) por fórmulas fechadas.

Não treina nada: cada checagem usa um MODELO FRESCO (o `env.py` compila o seu próprio MjModel em cada
`HoverEnv(...)`) em CONDIÇÕES ISOLADAS — estados impostos à mão no `reset`/`qpos` e comparados com o que as
fórmulas dizem, sem histórico de simulação. Nenhuma janela/render é aberta.

    uv run --group hover-rl python experiments/09_drone_hover_rl/run.py     # exit 0 = tudo [OK]

Recompensa v2b (por passo de decisão; `yaw_err` envolvido em [−π, π], alvo 0) — yaw/ω_z/Δa baixados/levantados
após a campanha de 20 treinos (chatter de momentos no v2); o resto é idêntico ao v2:
    r = −1.0·‖xy‖ − 1.0·|z−alvo_z| − 0.2·|yaw_err| − 0.05·‖v‖ − 0.05·‖ω_xy‖ − 0.1·|ω_z|
        − 0.05·‖Δa‖ + 1.0·𝟙[bonus] − 100·𝟙[terminated]
    bonus = ‖xy‖ < 0.05 ∧ |z−alvo_z| < 0.05 ∧ |yaw_err| < 0.10  (ESTRITO)

Checagens (critérios no cabeçalho de cada secção):
  1. mapeamento da ação → `data.ctrl` (unidades físicas, 1:1 com os 4 canais), incluindo cortes e o caso
     `thrust_realista=False`;
  2. recompensa v2: cada termo isolado à mão (coeficientes literais), bónus nos limiares EXATOS (estrito),
     bónus por dentro/por fora, terminação → −100, e a recompensa do `step` contra a fórmula recalculada
     dos sensores com uma implementação independente;
  3. física: empuxo = peso paira (|Δz| < 2 mm em 1 s), a=+1 sobe, a=−1 desce, e o vento lateral não muda a
     altitude;
  4. vento: `definir_vento` escreve `model.opt.wind` e o drone DERIVA (física real do modelo de fluido),
     `definir_vento_aleatorio` amostra por reset (norma/azimute/elevação), `vento=None` → ar parado;
  5. observação: forma (16,), escalas fixas por bloco, bloco de yaw coerente (obs[5] ≈ yaw/π), transformação
     mundo→corpo e ruído σ=ruido_obs;
  6. Gymnasium: `reset(seed)` determinístico (inclusive o vento aleatório semeado por `np_random`), `info`
     com as 8 chaves, episódio completo (truncagem em `episodio_s`) e `check_env` do Stable-Baselines3;
  7. contagens/contrato do modelo: nu, sensores, dt, decimation, `ctrladr` 1:1 e `cf2.xml` upstream intacto;
  8. vento DINÂMICO (`vento_dinamico=dict|None`) por fórmulas fechadas: validação da config (ValueError para
     modo/chaves/faixas), `rajadas` com o envelope `u·sin(π·k/(N+1))` (medido passo a passo, e rajada nova
     quando a anterior acaba), `frente` com o degrau no passo `k = floor(t_s/0,02)+1` (base antes, frente
     constante depois; determinístico dada a seed), `dryden` com o OU `x ← α·x + σ·√(1−α²)·ξ` (α = e^(−Δt·V/L)
     verificado pelo desvio-padrão dos incrementos, com `V = max(‖base‖, v_min)`) e a saturação em `u_max`;
     com `u_max = 0` o modo é INERTE nos TRÊS modos (fica só o vento base e nem se consome o `np_random`);
     com `vento_dinamico=None` (predefinição) NADA muda — é o caminho do contrato v2b.
"""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
from lab import mjkit  # noqa: F401, I001  (MUJOCO_GL=egl antes de `import mujoco`: ordem de imports intencional)
from lab import crazyflie as cf  # (API do laboratório: sensores e constantes físicas)
from env import (  # (ambiente em validação)
    ALVO_TOL,
    BONUS_XY,
    BONUS_YAW,
    BONUS_Z,
    FRENTE_U_MIN,
    THRUST_MAX_REAL,
    VENTO_ELEV_MAX,
    YAW_ALVO,
    Z_TERMINA,
    HoverEnv,
    atitude,
    bonus_no_alvo,
    envolve_pi,
    quat_para_matriz,
    recompensa,
    termina,
    valida_vento_dinamico,
    vetor_vento,
)

import mujoco
import numpy as np

ALVO_TOLERANCIA = 1e-9    # tolerância das recompensas de referência (o estado de hover é preservado ao bit)
ALVO_TOLERANCIA_EXATA = 1e-9   # tolerância contra a fórmula recalculada a partir dos sensores
AQUI = Path(__file__).resolve().parent
CHAVES_INFO = {"z", "dist_xy", "v", "no_alvo", "yaw_err", "vento_vel", "vento_atual", "vento_azim"}


# --------------------------------------------------------------------------------------- utilitários
class Validador:
    """Acumula checagens `[OK]/[FALHA]` e imprime cada uma com o valor medido."""

    def __init__(self) -> None:
        self.linhas: list[tuple[str, bool]] = []

    def check(self, nome: str, ok: bool, detalhe: str = "") -> bool:
        ok = bool(ok)
        self.linhas.append((nome, ok))
        print(f"[{'OK ' if ok else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""))
        return ok

    @property
    def tudo_ok(self) -> bool:
        return all(ok for _, ok in self.linhas) and len(self.linhas) > 0

    @property
    def falhas(self) -> int:
        return sum(1 for _, ok in self.linhas if not ok)


def quat_de_euler(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Quaternion `[w x y z]` de uma atitude ZYX (mesma convenção de `atitude`)."""
    cr, sr = np.cos(roll / 2), np.sin(roll / 2)
    cp, sp = np.cos(pitch / 2), np.sin(pitch / 2)
    cy, sy = np.cos(yaw / 2), np.sin(yaw / 2)
    return np.array([cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy,
                     cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy])


def poe_estado(e: HoverEnv, pos, roll: float = 0.0, pitch: float = 0.0, yaw: float = 0.0,
               v_mundo=(0.0, 0.0, 0.0), omega=(0.0, 0.0, 0.0)) -> None:
    """Condição isolada: impõe posição/atitude/velocidades no `data` do env (modelo fresco) e sincroniza os derivados."""
    e.data.qpos[:3] = pos
    e.data.qpos[3:7] = quat_de_euler(roll, pitch, yaw)
    e.data.qvel[:3] = v_mundo
    e.data.qvel[3:] = omega
    e.data.ctrl[:] = 0.0
    mujoco.mj_forward(e.model, e.data)


def estado_dos_sensores(e: HoverEnv) -> dict:
    """Estado lido DIRETAMENTE dos sensores do lab (implementação independente do env)."""
    est = cf.ler_estado(e.model, e.data)
    imu = cf.ler_imu(e.model, e.data)
    x, y, z = (float(v) for v in est["pos"])
    rpy = atitude(imu["quat"])
    omega = np.asarray(imu["giro"], dtype=float)
    return {"x": x, "y": y, "z": z, "v": float(np.linalg.norm(est["vel"])),
            "yaw_err": envolve_pi(float(rpy[2]) - YAW_ALVO), "omega_xy": omega[:2], "omega_z": omega[2]}


def recompensa_fechada(x: float, y: float, z: float, v: float, yaw_err: float, omega_xy, omega_z: float,
                       delta_a, alvo_z: float) -> float:
    """Fórmula v2b escrita À MÃO (coeficientes literais), SEM o termo de terminação — não usa o `recompensa` do env."""
    d = float(np.hypot(x, y))
    r = (-1.0 * d - 1.0 * abs(z - alvo_z) - 0.2 * abs(yaw_err) - 0.05 * v
         - 0.05 * float(np.linalg.norm(omega_xy)) - 0.1 * abs(omega_z)
         - 0.05 * float(np.linalg.norm(delta_a)))
    if d < 0.05 and abs(z - alvo_z) < 0.05 and abs(yaw_err) < 0.10:
        r += 1.0
    return float(r)


def recompensa_base(e: HoverEnv, delta_a) -> float:
    """Fórmula v2 recalculada dos sensores no estado ATUAL (sem a penalidade de terminação)."""
    return recompensa_fechada(delta_a=delta_a, alvo_z=e.alvo_z, **estado_dos_sensores(e))


def recompensa_esperada(e: HoverEnv, terminado: bool, delta_a) -> float:
    """Recompensa esperada do último `step`: fórmula dos sensores + 100 se o passo terminou o episódio."""
    return recompensa_base(e, delta_a) - (100.0 if terminado else 0.0)


def deriva_com_vento(e: HoverEnv, vento, segundos: float = 1.0) -> np.ndarray:
    """Condição isolada: hover a 1 m em ar parado → liga `vento` → mede o deslocamento em `segundos` (a=0)."""
    e.reset(seed=0)
    poe_estado(e, (0.0, 0.0, 1.0))
    e.definir_vento(*vento)
    p0 = np.array(e.data.sensor("posicao").data, dtype=float)
    passos = round(segundos / e.dt_decisao)
    term = False
    for _ in range(passos):
        _, _, term, _, _ = e.step([0.0, 0.0, 0.0, 0.0])
    return np.array(e.data.sensor("posicao").data, dtype=float) - p0, term


# --------------------------------------------------------------------------------------- 1 · ação → ctrl
def checa_acao(v: Validador) -> None:
    print("\n1 · MAPEAMENTO DA AÇÃO (a=[empuxo, mx, my, mz] → data.ctrl em unidades físicas)")
    e = HoverEnv()
    mg, tmax, mmax = e.mg, e.thrust_max, e.momento_max

    e.aplicar_acao([0.0, 0.0, 0.0, 0.0])
    c = e.data.ctrl.copy()
    v.check("a=[0,0,0,0] → ctrl[0] == mg (hover)", abs(c[0] - mg) < ALVO_TOLERANCIA,
            f"ctrl[0] = {c[0]:.9f} N · mg = Σm·|g| = {mg:.9f} N (m = {e.massa:.4f} kg, g = {e.gravidade:.2f} m/s²)")
    e.aplicar_acao([1.0, 0.0, 0.0, 0.0])
    c_mais = e.data.ctrl.copy()
    v.check("a=[+1,0,0,0] → ctrl[0] == thrust_max", abs(c_mais[0] - tmax) < ALVO_TOLERANCIA,
            f"ctrl[0] = {c_mais[0]:.9f} N · thrust_max = {tmax:.9f} N (datasheet CF2.1)")
    e.aplicar_acao([-1.0, 0.0, 0.0, 0.0])
    c_menos = e.data.ctrl.copy()
    v.check("a=[-1,0,0,0] → ctrl[0] == 0 N", abs(c_menos[0]) < ALVO_TOLERANCIA, f"ctrl[0] = {c_menos[0]:.9e} N")

    e.aplicar_acao([0.5, 0.0, 0.0, 0.0])
    esperado = mg + (tmax - mg) * 0.5
    v.check("ramo a₀>0: a=[0,5,0,0,0] → mg + (thrust_max−mg)·0,5", abs(e.data.ctrl[0] - esperado) < ALVO_TOLERANCIA,
            f"ctrl[0] = {e.data.ctrl[0]:.9f} N · esperado {esperado:.9f} N")

    e.aplicar_acao([0.0, 1.0, 0.0, 0.0])
    c = e.data.ctrl.copy()
    esp = e.tau_escala * mmax[0]
    v.check("a=[0,1,0,0] → ctrl[1] == tau_escala·momento_max[0]",
            abs(c[1] - esp) < 1e-15 and abs(c[2]) == 0.0 and abs(c[3]) == 0.0,
            f"ctrl[1] = {c[1]:.9e} N·m · esperado {esp:.9e} N·m (tau_escala={e.tau_escala}, "
            f"momento_max={np.round(mmax, 7)} N·m) · ctrl[2:4] = {np.round(c[2:4], 9)}")
    v.check("momentos dentro da faixa física do canal (|ctrl| ≤ momento_max_i)",
            bool(np.all(np.abs(c[1:]) <= mmax + 1e-15)), f"máx |ctrl[1:4]| = {np.abs(c[1:]).max():.3e} N·m")

    e2 = HoverEnv(tau_escala=2.0)                     # 2× a faixa → tem de cortar
    e2.aplicar_acao([0.0, 1.0, -1.0, 1.0])
    v.check("clip: tau_escala=2,0 → |ctrl[1:4]| == momento_max", bool(np.allclose(np.abs(e2.data.ctrl[1:]),
            e2.momento_max, atol=1e-15)), f"ctrl[1:4] = {np.round(e2.data.ctrl[1:], 7)} · limite {np.round(mmax, 7)} N·m")

    e3 = HoverEnv(thrust_realista=False)
    e3.aplicar_acao([1.0, 0.0, 0.0, 0.0])
    v.check("thrust_realista=False → thrust_max = 0,35 N (ctrlrange upstream)",
            abs(e3.thrust_max - cf.EMPUXO_MAX) < 1e-12 and abs(e3.data.ctrl[0] - cf.EMPUXO_MAX) < ALVO_TOLERANCIA,
            f"ctrl[0] = {e3.data.ctrl[0]:.9f} N · cf.EMPUXO_MAX = {cf.EMPUXO_MAX} N")
    v.check("thrust_realista=True → 0,589 N (≈4×15 gf, T/W ≈ 2,2)",
            abs(THRUST_MAX_REAL - 0.589) < 1e-12 and abs(tmax - THRUST_MAX_REAL) < 1e-12,
            f"thrust_max = {tmax:.9f} N · T/W = {tmax / mg:.2f}")
    v.check("gear/ctrlrange do lab intactos numa carga nova (cf.carregar)",
            abs(cf.EMPUXO_MAX - 0.35) < 1e-12 and abs(cf.MOMENTOS_MAX[0] - 0.0056875) < 1e-15,
            f"cf.EMPUXO_MAX = {cf.EMPUXO_MAX} N · cf.MOMENTOS_MAX = {np.round(cf.MOMENTOS_MAX, 7)} N·m")


# --------------------------------------------------------------------------------------- 2 · recompensa v2
def checa_recompensa(v: Validador) -> None:
    print("\n2 · RECOMPENSA v2b POR FÓRMULA FECHADA (por passo de decisão; yaw 0,2 · ω_z 0,1 · Δa 0,05)")
    print("      r = −1,0·‖xy‖ − 1,0·|z−alvo_z| − 0,2·|yaw_err| − 0,05·‖v‖ − 0,05·‖ω_xy‖ − 0,1·|ω_z|"
          " − 0,05·‖Δa‖ + 1,0·𝟙[bónus] − 100·𝟙[terminado]")
    print("      bónus = ‖xy‖ < 0,05 ∧ |z−alvo_z| < 0,05 ∧ |yaw_err| < 0,10 (ESTRITO) · yaw_err alvo = 0 rad")

    print("  (a) função pura `recompensa()` — cada termo isolado, com os restantes em hover perfeito:")
    hover = {"x": 0.0, "y": 0.0, "z": 1.0, "v": 0.0, "yaw_err": 0.0, "omega_xy": (0.0, 0.0),
             "omega_z": 0.0, "delta_a": (0.0, 0.0, 0.0, 0.0), "terminado": False, "alvo_z": 1.0}
    r_hover = recompensa(**hover)
    v.check("hover perfeito (xy=0, z=1, yaw=0, v=ω=0, Δa=0) → r == +1,0", abs(r_hover - 1.0) < ALVO_TOLERANCIA,
            f"r = {r_hover:+.9f} · esperado +1,000000000 (só o bónus)")

    r_yaw = recompensa(**{**hover, "yaw_err": 0.5})
    v.check("yaw_err = 0,5 rad → r == −0,10 (bónus fora: 0,5 > 0,10)", abs(r_yaw + 0.10) < ALVO_TOLERANCIA,
            f"r = {r_yaw:+.9f} · esperado −0,100000000 = −0,2·0,5")
    v.check("yaw_err = −0,5 rad → r == −0,10 (o |yaw_err| não depende do sinal)",
            abs(recompensa(**{**hover, "yaw_err": -0.5}) + 0.10) < ALVO_TOLERANCIA,
            f"r = {recompensa(**{**hover, 'yaw_err': -0.5}):+.9f}")

    r_wz0 = recompensa(**{**hover, "omega_z": 0.0})
    r_wz1 = recompensa(**{**hover, "omega_z": 1.0})
    v.check("ω_z = 1 rad/s → contribuição Δr == −0,1 (|ω_z|)", abs((r_wz1 - r_wz0) + 0.1) < ALVO_TOLERANCIA,
            f"Δr = {r_wz1 - r_wz0:+.9f} · esperado −0,100000000 · r absoluto = {r_wz1:+.6f} "
            f"(= +0,9: o bónus continua ativo porque xy/z/yaw estão no alvo)")

    r_wxy0 = recompensa(**{**hover, "omega_xy": (0.0, 0.0)})
    r_wxy1 = recompensa(**{**hover, "omega_xy": (0.6, -0.8)})
    v.check("ω_xy = (0,6, −0,8) (‖ω_xy‖ = 1) → Δr == −0,05", abs((r_wxy1 - r_wxy0) + 0.05) < ALVO_TOLERANCIA,
            f"Δr = {r_wxy1 - r_wxy0:+.9f} · esperado −0,050000000 (‖ω_xy‖ = {np.linalg.norm([0.6, -0.8]):.6f})")

    r_xy = recompensa(**{**hover, "x": 0.3})
    v.check("‖xy‖ = 0,3 m → r == −0,3 (bónus fora)", abs(r_xy + 0.3) < ALVO_TOLERANCIA,
            f"r = {r_xy:+.9f} · esperado −0,300000000 = −1,0·0,3")

    r_z = recompensa(**{**hover, "z": 0.5})
    v.check("|z−alvo_z| = 0,5 m → r == −0,5 (bónus fora)", abs(r_z + 0.5) < ALVO_TOLERANCIA,
            f"r = {r_z:+.9f} · esperado −0,500000000 = −1,0·0,5")

    r_v0 = recompensa(**{**hover, "v": 0.0})
    r_v2 = recompensa(**{**hover, "v": 2.0})
    v.check("‖v‖ = 2 m/s → Δr == −0,1 (‖v‖)", abs((r_v2 - r_v0) + 0.1) < ALVO_TOLERANCIA,
            f"Δr = {r_v2 - r_v0:+.9f} · esperado −0,100000000")

    r_da0 = recompensa(**{**hover, "delta_a": (0.0, 0.0, 0.0, 0.0)})
    r_da1 = recompensa(**{**hover, "delta_a": (1.0, -1.0, 1.0, -1.0)})
    v.check("Δa = (+1,−1,+1,−1) (‖Δa‖ = 2) → Δr == −0,10 (taxa de ação: remédio do chatter)",
            abs((r_da1 - r_da0) + 0.10) < ALVO_TOLERANCIA,
            f"Δr = {r_da1 - r_da0:+.9f} · esperado −0,100000000 (‖Δa‖ = {np.linalg.norm([1, -1, 1, -1]):.6f})")

    lim = [(f"‖xy‖ = {BONUS_XY} m (limiar) → SEM bónus", {"x": BONUS_XY}, -BONUS_XY),
           (f"|z−alvo_z| = {BONUS_Z} m (limiar) → SEM bónus", {"z": 1.0 + BONUS_Z}, -BONUS_Z),
           (f"|yaw_err| = {BONUS_YAW} rad (limiar) → SEM bónus", {"yaw_err": BONUS_YAW}, -0.2 * BONUS_YAW)]
    for nome, mudanca, exp in lim:
        r = recompensa(**{**hover, **mudanca})
        v.check(nome, abs(r - exp) < ALVO_TOLERANCIA and not bonus_no_alvo(
            np.hypot(mudanca.get("x", 0.0), 0.0), abs(mudanca.get("z", 1.0) - 1.0), mudanca.get("yaw_err", 0.0)),
            f"r = {r:+.9f} · esperado {exp:+.9f} (desigualdade ESTRITA: no limiar não há bónus)")

    dentro = {"x": 0.049, "z": 1.049, "yaw_err": 0.099}
    r_dentro = recompensa(**{**hover, **dentro})
    exp_dentro = 1.0 - 0.049 - 0.049 - 0.2 * 0.099
    v.check("bónus logo DENTRO dos limiares (0,049 / 0,049 / 0,099) → r == +0,8822",
            abs(r_dentro - exp_dentro) < ALVO_TOLERANCIA and bonus_no_alvo(0.049, 0.049, 0.099),
            f"r = {r_dentro:+.9f} · esperado {exp_dentro:+.9f} (= 1 − 0,049 − 0,049 − 0,0198)")

    composicao = {"x": 0.3, "y": 0.4, "z": 0.7, "v": 1.0, "yaw_err": -0.2, "omega_xy": (0.3, 0.4),
                  "omega_z": -0.5, "delta_a": (0.5, 0.0, 0.0, 0.0)}
    r_comp = recompensa(**{**hover, **composicao})
    exp_comp = -(0.5 + 0.3 + 0.04 + 0.05 + 0.025 + 0.05 + 0.025)
    v.check("composição de TODOS os termos → r == −0,99 (‖xy‖=0,5 · dz=0,3 · yaw=0,2 · v=1 · ‖ω_xy‖=0,5 · "
            "ω_z=0,5 · ‖Δa‖=0,5)", abs(r_comp - exp_comp) < ALVO_TOLERANCIA,
            f"r = {r_comp:+.9f} · esperado {exp_comp:+.9f}")

    r_term = recompensa(**{**hover, "terminado": True})
    v.check("𝟙[terminated] → r == r_sem_terminação − 100", abs((r_term - r_hover) + 100.0) < ALVO_TOLERANCIA,
            f"r = {r_term:+.9f} · r sem terminação = {r_hover:+.9f} · penalidade = {r_hover - r_term:.6f}")

    wraps = [(np.pi + 0.1, -np.pi + 0.1), (1.5 * np.pi, -0.5 * np.pi), (2 * np.pi, 0.0), (-np.pi - 0.1, np.pi - 0.1)]
    v.check("envolve_pi: yaw envolvido em [−π, π] (π+0,1 → −π+0,1 · 3π/2 → −π/2 · 2π → 0)",
            all(abs(envolve_pi(a) - e_) < 1e-12 for a, e_ in wraps),
            " · ".join(f"envolve_pi({a:+.4f}) = {envolve_pi(a):+.6f}" for a, _ in wraps))

    print("  (b) recompensa do `step` (estados estacionários: a=0 → empuxo = peso, nada se move):")
    e = HoverEnv()
    e.reset(seed=0)
    poe_estado(e, (0.0, 0.0, 1.0))                    # hover exato no alvo: φ=θ=yaw=0, v=ω=0
    _, r, term, _, info = e.step([0.0, 0.0, 0.0, 0.0])
    esperado = recompensa_esperada(e, term, (0.0, 0.0, 0.0, 0.0))
    v.check("step: hover a z=1,0 m → r == +1,0 (bónus do alvo)", abs(r - 1.0) < ALVO_TOLERANCIA and not term,
            f"r = {r:.9f} · esperado +1,0 · z pós-passo = {info['z']:.9f} m (deriva {abs(info['z'] - 1.0):.1e} m)")
    v.check("step: r == fórmula v2b recalculada dos sensores (|Δ| < 1e-9)",
            abs(r - esperado) < ALVO_TOLERANCIA_EXATA, f"Δ = {abs(r - esperado):.1e}")

    e.reset(seed=0)
    poe_estado(e, (0.0, 0.0, 1.0), yaw=0.5)
    _, r, _, _, info = e.step([0.0, 0.0, 0.0, 0.0])
    v.check("step: yaw = 0,5 rad → r == −0,10", abs(r + 0.10) < ALVO_TOLERANCIA,
            f"r = {r:+.9f} · esperado −0,10 · yaw_err medido = {info['yaw_err']:+.9f} rad · no_alvo = {info['no_alvo']}")

    e.reset(seed=0)
    poe_estado(e, (0.3, 0.0, 1.0))
    _, r, _, _, info = e.step([0.0, 0.0, 0.0, 0.0])
    v.check("step: xy = 0,3 m → r == −0,3", abs(r + 0.3) < ALVO_TOLERANCIA,
            f"r = {r:+.9f} · esperado −0,3 · dist_xy = {info['dist_xy']:.9f} m")

    e.reset(seed=0)
    poe_estado(e, (0.0, 0.0, 0.5))
    _, r, _, _, info = e.step([0.0, 0.0, 0.0, 0.0])
    v.check("step: z = 0,5 m → r == −0,5", abs(r + 0.5) < ALVO_TOLERANCIA,
            f"r = {r:+.9f} · esperado −0,5 · |z−alvo| = {abs(info['z'] - 1.0):.6f} m")

    for nome, pos, yaw, exp in (("dentro (0,049 / 0,049 / 0,099)", (0.049, 0.0, 1.049), 0.099, 0.8822),
                                ("fora em xy (0,051)", (0.051, 0.0, 1.0), 0.0, -0.051),
                                ("fora em z (1,051)", (0.0, 0.0, 1.051), 0.0, -0.051),
                                ("fora em yaw (0,101)", (0.0, 0.0, 1.0), 0.101, -0.0202)):
        e.reset(seed=0)
        poe_estado(e, pos, yaw=yaw)
        _, r, _, _, info = e.step([0.0, 0.0, 0.0, 0.0])
        v.check(f"step: limiares do bónus {nome} → r == {exp:+.4f}", abs(r - exp) < ALVO_TOLERANCIA,
                f"r = {r:+.9f} · esperado {exp:+.9f} · no_alvo = {info['no_alvo']}")

    e.reset(seed=0)
    poe_estado(e, (0.0, 0.0, 1.0))
    e.acao_anterior = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    _, r, _, _, _ = e.step([0.0, 0.0, 0.0, 0.0])     # Δa = (−1, 0, 0, 0) → ‖Δa‖ = 1
    v.check("step: Δa (ação anterior = +1 → atual 0) → r == +1,0 − 0,05 (taxa de ação)",
            abs(r - 0.95) < ALVO_TOLERANCIA, f"r = {r:+.9f} · esperado +0,950000000 · ‖Δa‖ = 1")

    lim_t = [("z = 0,005 m (limiar) → False", termina(0.005, 0.0, 0.0), False),
             ("z = 0,0049 m → True", termina(0.0049, 0.0, 0.0), True),
             ("z = 3,0 m (teto) → False", termina(3.0, 0.0, 0.0), False),
             ("z = 3,001 m → True", termina(3.001, 0.0, 0.0), True),
             ("roll = π/2 (limiar) → False", termina(1.0, np.pi / 2, 0.0), False),
             ("roll = π/2 + 1e-6 → True", termina(1.0, np.pi / 2 + 1e-6, 0.0), True)]
    v.check("limiares de `termina()` (mantidos do contrato v1)", all(obtido == exp for _, obtido, exp in lim_t),
            " · ".join(f"{nome}: {obtido}" for nome, obtido, _ in lim_t))

    print("  (c) terminação (o −100 entra no passo em que `terminated=True`):")
    e_sub = HoverEnv()
    e_sub.reset(seed=0)
    poe_estado(e_sub, (0.0, 0.0, 1.0))
    for k in range(e_sub.max_passos):
        _, r, term, _, info = e_sub.step([1.0, 0.0, 0.0, 0.0])
        if term:
            break
    base = recompensa_base(e_sub, (0.0, 0.0, 0.0, 0.0))   # Δa = 0 (ação constante)
    v.check("subida a=+1 → terminated por z > 3,0 m, r = fórmula − 100",
            term and info["z"] > 3.0 and abs(r - (base - 100.0)) < ALVO_TOLERANCIA_EXATA and abs((base - r) - 100.0) < 1e-9,
            f"terminou no passo {k} (t={e_sub.data.time:.2f} s) com z = {info['z']:.4f} m · r = {r:.6f} · "
            f"fórmula = {base:.6f} · penalidade = {base - r:.6f}")

    e_cap = HoverEnv()
    e_cap.reset(seed=0)
    poe_estado(e_cap, (0.0, 0.0, 1.0), roll=np.radians(100.0))
    _, r, term, _, info = e_cap.step([0.0, 0.0, 0.0, 0.0])
    base = recompensa_base(e_cap, (0.0, 0.0, 0.0, 0.0))
    v.check("capotamento (roll=100° > π/2) → terminated no 1º passo, r = fórmula − 100",
            term and abs(r - (base - 100.0)) < ALVO_TOLERANCIA_EXATA and abs((base - r) - 100.0) < 1e-9,
            f"r = {r:.6f} · fórmula sem penalidade = {base:.6f} · z = {info['z']:.4f} m")

    e_q = HoverEnv()                                   # queda de 3 m: o CM penetra o piso e dispara z < 0,005
    e_q.reset(seed=0)
    poe_estado(e_q, (0.0, 0.0, 3.0))
    zmin, terminou_em = 9.0, None
    for k in range(e_q.max_passos):
        _, r, term, _, info = e_q.step([-1.0, 0.0, 0.0, 0.0])
        zmin = min(zmin, info["z"])
        if term:
            terminou_em = k
            break
    base = recompensa_base(e_q, (0.0, 0.0, 0.0, 0.0))
    v.check("queda de 3 m com motores desligados → terminated por z < 0,005 m (impacto), r = fórmula − 100",
            term and terminou_em is not None and info["z"] < 0.005 and abs(r - (base - 100.0)) < ALVO_TOLERANCIA_EXATA
            and abs((base - r) - 100.0) < 1e-9,
            f"terminou no passo {terminou_em} (t={e_q.data.time:.2f} s) com z = {info['z']:.5f} m "
            f"(mínimo no impacto {zmin:.5f} m) · r = {r:.4f} · penalidade = {base - r:.4f}")


# --------------------------------------------------------------------------------------- 3 · física
def checa_fisica(v: Validador) -> None:
    print("\n3 · FÍSICA (modelo fresco por teste; z lido do sensor `posicao`, que é o CM do corpo)")
    e = HoverEnv()

    e.reset(seed=0)
    poe_estado(e, (0.0, 0.0, 1.0))
    z0 = float(e.data.sensor("posicao").data[2])
    for _ in range(50):                               # 50 × 0,02 s = 1 s (500 passos de física)
        _, _, term_h, _, _ = e.step([0.0, 0.0, 0.0, 0.0])
    dz = float(e.data.sensor("posicao").data[2]) - z0
    v.check("empuxo = peso em hover a 1 m, SEM vento: |Δz| < 2 mm em 1 s", abs(dz) < 2e-3 and not term_h,
            f"Δz = {dz:+.3e} m (critério 2,0e-03) · z = {z0 + dz:.9f} m · term = {term_h}")

    e.reset(seed=0)
    poe_estado(e, (0.0, 0.0, 1.0))
    for _ in range(25):                               # 0,5 s a empuxo máximo
        _, _, term_s, _, info_s = e.step([1.0, 0.0, 0.0, 0.0])
    v.check("a=[+1,0,0,0] → sobe (Δz > 0 em 0,5 s) e não termina antes do teto",
            info_s["z"] > 1.0 and not term_s,
            f"Δz = {info_s['z'] - 1.0:+.4f} m em 0,5 s · z = {info_s['z']:.4f} m (teto 3,0 m) · "
            f"a = (thrust_max−mg)/m − g = {(e.thrust_max - e.mg) / e.massa - e.gravidade:+.2f} m/s²")

    e.reset(seed=0)
    poe_estado(e, (0.0, 0.0, 1.0))
    for _ in range(15):                               # 0,3 s com motores desligados
        _, _, term_d, _, info_d = e.step([-1.0, 0.0, 0.0, 0.0])
    v.check("a=[−1,0,0,0] → desce (Δz < 0 em 0,3 s)", info_d["z"] < 1.0 and not term_d,
            f"Δz = {info_d['z'] - 1.0:+.4f} m em 0,3 s (queda livre: −½·g·t² = {-0.5 * e.gravidade * 0.09:+.4f} m)")

    e.reset(seed=0)
    poe_estado(e, (0.0, 0.0, 1.0))
    e.definir_vento(5.0, 0.0, 0.0)
    for _ in range(50):                               # 1 s de vento lateral com empuxo = peso
        _, _, term_v, _, info_v = e.step([0.0, 0.0, 0.0, 0.0])
    v.check("vento lateral (+5 m/s em x) não muda a altitude: |Δz| < 5 mm em 1 s",
            abs(info_v["z"] - 1.0) < 5e-3 and not term_v,
            f"Δz = {info_v['z'] - 1.0:+.3e} m · Δx = {info_v['dist_xy']:+.4f} m (o arrasto é aplicado no CM, "
            "sem binário)")


# --------------------------------------------------------------------------------------- 4 · vento
def checa_vento(v: Validador) -> None:
    print("\n4 · VENTO (física real via `model.opt.wind`; o chão é estático → imune)")
    e = HoverEnv()
    v.check("vento=None (predefinição) → model.opt.wind fica [0, 0, 0]",
            bool(np.array_equal(e.vento_atual, np.zeros(3))) and e.vento is None and e.vento_aleatorio is None,
            f"opt.wind = {e.vento_atual} · vento = {e.vento} · vento_aleatorio = {e.vento_aleatorio}")

    d, term = deriva_com_vento(e, (5.0, 0.0, 0.0))
    v.check("definir_vento(5, 0, 0) → model.opt.wind == [5, 0, 0]", bool(np.array_equal(e.vento_atual, [5.0, 0.0, 0.0])),
            f"opt.wind = {e.vento_atual} m/s")
    v.check("vento +5 m/s em x → o drone DERIVA em +x (Δx > 0 em 1 s com a=0)",
            d[0] > 0.05 and abs(d[1]) < 1e-6 and not term,
            f"Δ = ({d[0]:+.4f}, {d[1]:+.4f}, {d[2]:+.4f}) m em 1 s · Δx > 0 · term = {term}")

    d2, term2 = deriva_com_vento(e, (3.0, 90.0, 0.0))
    v.check("definir_vento(3, 90, 0) → model.opt.wind ≈ [0, 3, 0] (azimute 90° → +y)",
            bool(np.allclose(e.vento_atual, [0.0, 3.0, 0.0], atol=1e-15)), f"opt.wind = {e.vento_atual} m/s")
    v.check("vento +3 m/s em y → o drone DERIVA em +y (Δy > 0 em 1 s com a=0)",
            d2[1] > 0.05 and abs(d2[0]) < 1e-6 and not term2,
            f"Δ = ({d2[0]:+.4f}, {d2[1]:+.4f}, {d2[2]:+.4f}) m em 1 s · Δy > 0 · term = {term2}")

    e.definir_vento(2.0, 0.0, 90.0)
    v.check("definir_vento(2, 0, 90) → elevação honrada: opt.wind == [0, 0, 2] (vertical, para cima)",
            bool(np.allclose(e.vento_atual, [0.0, 0.0, 2.0], atol=1e-15)),
            f"opt.wind = {e.vento_atual} m/s · vetor_vento(2,0,90) = {np.round(vetor_vento(2, 0, 90), 12)}")

    e.definir_vento(0.0, 123.0)
    v.check("definir_vento(0, …) → vento nulo (opt.wind == [0, 0, 0])", bool(np.array_equal(e.vento_atual, np.zeros(3))),
            f"opt.wind = {e.vento_atual} m/s")

    e_a = HoverEnv(vento_aleatorio=(0.0, 2.0))
    amostras, direcoes = [], []
    for s in range(8):
        e_a.reset(seed=s)
        w = e_a.vento_atual
        amostras.append(w)
        direcoes.append(w / max(float(np.linalg.norm(w)), 1e-12))
    normas = [float(np.linalg.norm(w)) for w in amostras]
    distintas = len({tuple(np.round(d, 6)) for d in direcoes})
    v.check("definir_vento_aleatorio(0, 2) → 8 resets amostram ventos com norma ≤ 2 m/s",
            all(u <= 2.0 + 1e-9 for u in normas) and max(normas) > 0.0,
            f"normas = {np.round(normas, 4)} m/s (máx {max(normas):.4f} ≤ 2,000000)")
    v.check("vento aleatório: ≥ 2 amostras e DIREÇÕES distintas entre resets", distintas >= 2,
            f"direções distintas = {distintas}/8 · 1ªs = {np.round(direcoes[0], 4)} e {np.round(direcoes[1], 4)}")

    elevacoes = [float(np.degrees(np.arcsin(np.clip(w[2] / max(float(np.linalg.norm(w)), 1e-12), -1, 1))))
                 for w in amostras]
    azimutes = [float(np.degrees(np.arctan2(w[1], w[0])) % 360.0) for w in amostras]
    v.check(f"vento aleatório: elevação dentro de ±{np.degrees(VENTO_ELEV_MAX):.0f}° e azimute em [0, 360)",
            all(abs(el) <= np.degrees(VENTO_ELEV_MAX) + 1e-9 for el in elevacoes)
            and all(0.0 <= az <= 360.0 for az in azimutes),
            f"elevações = {np.round(elevacoes, 3)}° · azimutes = {np.round(azimutes, 2)}°")

    e_c = HoverEnv(vento=(5.0, 0.0, 0.0))
    _, info_c = e_c.reset(seed=0)
    v.check("HoverEnv(vento=(5,0,0)) → o vento constante sobrevive ao reset (e o info reporta-o)",
            bool(np.array_equal(e_c.vento_atual, [5.0, 0.0, 0.0])) and abs(info_c["vento_vel"] - 5.0) < 1e-12
            and abs(info_c["vento_azim"] - 0.0) < 1e-12,
            f"opt.wind = {e_c.vento_atual} m/s · info = {{'vento_vel': {info_c['vento_vel']:.6f}, "
            f"'vento_azim': {info_c['vento_azim']:.6f}}}")

    e_c2 = HoverEnv(vento=(0.0, -3.0, 0.0))
    e_c2.reset(seed=1)
    v.check("HoverEnv(vento=(0,−3,0)) → vector preservado e azimute = 270°",
            bool(np.allclose(e_c2.vento_atual, [0.0, -3.0, 0.0], atol=1e-12))
            and abs(e_c2._info()["vento_azim"] - 270.0) < 1e-9,
            f"opt.wind = {e_c2.vento_atual} m/s · azimute = {e_c2._info()['vento_azim']:.6f}°")

    e_u = HoverEnv(vento_aleatorio=(2.0, 2.0))
    e_u.reset(seed=5)
    v.check("definir_vento_aleatorio(2, 2) → U_min == U_max: a norma é sempre 2 m/s",
            abs(float(np.linalg.norm(e_u.vento_atual)) - 2.0) < 1e-12,
            f"‖opt.wind‖ = {float(np.linalg.norm(e_u.vento_atual)):.12f} m/s · opt.wind = {e_u.vento_atual}")

    e.definir_vento_aleatorio(0.0, 1.0)
    estado_1 = (e.vento, e.vento_aleatorio)
    e.definir_vento(4.0, 45.0)
    v.check("`definir_vento` LIMPA o currículo (e `definir_vento_aleatorio` limpa o constante)",
            estado_1 == (None, (0.0, 1.0)) and e.vento_aleatorio is None and e.vento is not None,
            f"após definir_vento_aleatorio(0,1): vento={estado_1[0]}, aleatorio={estado_1[1]} · "
            f"após definir_vento(4,45): vento={e.vento}, aleatorio={e.vento_aleatorio}")

    erros = []
    for nome, chamada in (("vel < 0", lambda: HoverEnv().definir_vento(-1.0, 0.0)),
                          ("u_min > u_max", lambda: HoverEnv().definir_vento_aleatorio(2.0, 1.0)),
                          ("u_min < 0", lambda: HoverEnv().definir_vento_aleatorio(-1.0, 1.0)),
                          ("vento + vento_aleatorio", lambda: HoverEnv(vento=(1, 0, 0), vento_aleatorio=(0, 1)))):
        try:
            chamada()
            erros.append(f"{nome}: NÃO levantou")
        except ValueError:
            pass
    v.check("faixas inválidas de vento levantam ValueError (vel<0, u_min>u_max, u_min<0, ambos os modos)",
            not erros, " · ".join(erros) if erros else "4/4 casos levantaram ValueError")


# --------------------------------------------------------------------------------------- 5 · observação
def checa_observacao(v: Validador) -> None:
    print("\n5 · OBSERVAÇÃO (16,) — escalas fixas: Δp/1 m · rpy/π · v_corpo/1 m·s⁻¹ · ω/10 rad·s⁻¹ · ação anterior")
    e = HoverEnv()
    e.reset(seed=0)
    poe_estado(e, (0.0, 0.0, 1.0))
    obs = e.observacao()
    v.check("shape (16,) · float32 · dentro do observation_space",
            obs.shape == (16,) and obs.dtype == np.float32 and e.observation_space.contains(obs),
            f"shape {obs.shape} · dtype {obs.dtype} · espaço {e.observation_space}")
    v.check("hover a 1 m: Δp ≈ 0, rpy ≈ 0, v ≈ 0, ω ≈ 0, ação anterior = 0",
            bool(np.all(np.abs(obs) < 1e-6)),
            f"máx |obs| = {np.abs(obs).max():.2e} · obs[0:3] = {np.round(obs[0:3], 8)} · obs[9:12] = {np.round(obs[9:12], 8)}")

    # estado completo e conhecido: compara bloco a bloco com uma implementação independente (sensores do lab/)
    roll, pitch, yaw = np.radians([15.0, -8.0, 35.0])
    v_mundo = np.array([0.3, -0.2, 0.1])
    omega = np.array([0.1, -0.2, 0.3])
    e.reset(seed=0)
    poe_estado(e, (0.25, -0.1, 1.25), roll=roll, pitch=pitch, yaw=yaw, v_mundo=v_mundo, omega=omega)
    e.acao_anterior = np.array([0.3, -0.2, 0.1, -0.7], dtype=np.float32)
    obs = e.observacao()
    est, imu = cf.ler_estado(e.model, e.data), cf.ler_imu(e.model, e.data)
    esperado = np.concatenate([(est["pos"] - e.alvo) / 1.0, atitude(imu["quat"]) / np.pi,
                              est["vel"] / 1.0, imu["giro"] / 10.0, e.acao_anterior])
    v.check("blocos batem com a fórmula (sensores do lab/): Δp, rpy, v_corpo, ω, ação anterior",
            bool(np.allclose(obs, esperado, atol=1e-6)),
            f"Δmáx = {np.abs(obs - esperado).max():.2e} · Δp = {np.round(obs[0:3], 5)} · rpy/π = {np.round(obs[3:6], 5)} · "
            f"v_corpo = {np.round(obs[6:9], 5)} · ω/10 = {np.round(obs[9:12], 5)}")
    v.check("bloco de yaw coerente: obs[5] == yaw/π (o alvo de yaw é 0 → obs[5] é o erro de guinada/π)",
            abs(float(obs[5]) - yaw / np.pi) < 1e-6 and abs(float(obs[5]) - 35.0 / 180.0) < 1e-6,
            f"obs[5] = {obs[5]:+.9f} · yaw/π = {yaw / np.pi:+.9f} (yaw = {np.degrees(yaw):.1f}°) · "
            f"obs[3:6] = {np.round(obs[3:6], 6)}")

    R = quat_para_matriz(imu["quat"])
    v.check("transformação mundo→corpo: sensor `vel` == R(quat)ᵀ · qvel[:3]",
            bool(np.allclose(np.asarray(est["vel"]), R.T @ e.data.qvel[:3], atol=1e-12)),
            f"Δmáx = {np.abs(np.asarray(est['vel']) - R.T @ e.data.qvel[:3]).max():.2e} m/s "
            f"(v_mundo = {np.round(v_mundo, 3)} → v_corpo = {np.round(est['vel'], 5)})")
    v.check("atitude(quat) recupera os ângulos impostos (roll, pitch, yaw)",
            bool(np.allclose(atitude(imu["quat"]), [roll, pitch, yaw], atol=1e-9)),
            f"rpy = {np.round(np.degrees(atitude(imu['quat'])), 8)}° · imposto {np.round(np.degrees([roll, pitch, yaw]), 8)}°")

    e_ruido = HoverEnv(ruido_obs=0.1)
    e_ruido.reset(seed=0)
    poe_estado(e_ruido, (0.0, 0.0, 1.0))
    e_limpo = HoverEnv()                              # mesma condição isolada, mas sem ruído → referência exacta
    e_limpo.reset(seed=0)
    poe_estado(e_limpo, (0.0, 0.0, 1.0))
    limpa = e_limpo.observacao()
    amostras = np.array([e_ruido.observacao() for _ in range(300)])
    sigma = float((amostras - limpa).std())
    v.check("ruido_obs=0,1 → ruído gaussiano σ ≈ 0,1 na observação", abs(sigma - 0.1) < 0.01,
            f"σ medido = {sigma:.4f} em {amostras.size} amostras (esperado 0,1000 ± 0,001)")
    obs_a = e_limpo.observacao()
    v.check("ruido_obs=0 (predefinição) → observação determinística", bool(np.array_equal(obs_a, e_limpo.observacao())),
            f"máx |Δ| entre duas leituras = {np.abs(obs_a - e_limpo.observacao()).max():.1e}")


# --------------------------------------------------------------------------------------- 6 · Gymnasium
def checa_gymnasium(v: Validador) -> None:
    print("\n6 · GYMNASIUM (reset determinístico incl. vento, info com 8 chaves, episódio completo, check_env do SB3)")
    e = HoverEnv()
    obs, info = e.reset(seed=0)
    v.check("reset(seed=0) → (obs, info) com as 8 chaves do contrato",
            obs.shape == (16,) and set(info) == CHAVES_INFO and e.observation_space.contains(obs),
            f"info = {{{', '.join(f'{k}: {info[k]:.6f}' if isinstance(info[k], float) else f'{k}: {info[k]}' for k in sorted(info))}}}")
    obs_b, info_b = e.reset(seed=0)
    obs_c, _ = e.reset(seed=7)
    v.check("reset é determinístico dada a seed (mesma obs e mesmo info) e muda com outra seed",
            bool(np.array_equal(obs, obs_b)) and bool(np.array_equal(info["yaw_err"], info_b["yaw_err"]))
            and not bool(np.array_equal(obs, obs_c)),
            f"seed 0 == seed 0: {np.array_equal(obs, obs_b)} · seed 0 == seed 7: {np.array_equal(obs, obs_c)} · "
            f"yaw_err(seed 0) = {info['yaw_err']:+.6f} rad")

    e_v = HoverEnv(vento_aleatorio=(0.0, 2.0))
    e_v.reset(seed=11)
    w_a, obs_a = e_v.vento_atual.copy(), e_v.observacao()
    e_v.reset(seed=11)
    w_b, obs_b2 = e_v.vento_atual.copy(), e_v.observacao()
    e_v.reset(seed=12)
    w_c = e_v.vento_atual.copy()
    v.check("vento ALEATÓRIO semeado por `np_random`: mesma seed → mesmo vento; seed diferente → vento diferente",
            bool(np.array_equal(w_a, w_b)) and bool(np.array_equal(obs_a, obs_b2)) and not bool(np.array_equal(w_a, w_c)),
            f"seed 11 = {np.round(w_a, 6)} · seed 11 = {np.round(w_b, 6)} · seed 12 = {np.round(w_c, 6)} m/s")

    e.reset(seed=0)
    z_repouso = float(e.data.sensor("posicao").data[2])
    for k in range(e.max_passos):                     # motores desligados: o drone fica pousado o episódio todo
        obs, r, term, trunc, info = e.step([-1.0, 0.0, 0.0, 0.0])
        if term or trunc:
            break
    v.check(f"episódio com motores desligados: truncado exactamente em {e.max_passos} passos "
            f"({e.episodio_s:.0f} s), sem terminação espúria em repouso",
            trunc and not term and k == e.max_passos - 1 and abs(info["z"] - z_repouso) < 1e-3,
            f"passos = {k + 1} · t = {e.data.time:.2f} s · z = {info['z']:.6f} m (repouso {z_repouso:.6f} m, "
            f"limiar de queda {Z_TERMINA} m) · r final = {r:.4f}")

    e_aberto = HoverEnv()                             # evidência: empuxo = peso em MALHA ABERTA não se mantém
    e_aberto.reset(seed=0)
    for k in range(e_aberto.max_passos):
        _, _, term_ab, trunc_ab, info_ab = e_aberto.step([0.0, 0.0, 0.0, 0.0])
        if term_ab or trunc_ab:
            break
    print(f"      nota: a=0 (empuxo = peso) é equilíbrio INSTÁVEL em malha aberta — derivou para "
          f"d_xy = {info_ab['dist_xy']:.2f} m, z = {info_ab['z']:.3f} m, ‖v‖ = {info_ab['v']:.2f} m/s, "
          f"yaw_err = {np.degrees(info_ab['yaw_err']):+.1f}° e {'terminou' if term_ab else 'truncou'} no passo "
          f"{k + 1} (é isto que o treino tem de resolver)")
    v.check("info do step tem EXACTAMENTE as 8 chaves do contrato, com os tipos certos",
            set(info_ab) == CHAVES_INFO and isinstance(info_ab["no_alvo"], bool)
            and all(isinstance(info_ab[k], float)
                    for k in ("z", "dist_xy", "v", "yaw_err", "vento_vel", "vento_atual", "vento_azim")),
            f"chaves = {sorted(info_ab)} · no_alvo = {info_ab['no_alvo']} ({type(info_ab['no_alvo']).__name__}) · "
            f"vento_vel = {info_ab['vento_vel']:.4f} m/s · vento_azim = {info_ab['vento_azim']:.2f}°")
    v.check("`no_alvo` é a condição do bónus (xy < 0,05 ∧ |dz| < 0,05 ∧ |yaw_err| < 0,10)",
            info_ab["no_alvo"] == bonus_no_alvo(info_ab["dist_xy"], abs(info_ab["z"] - e_aberto.alvo_z),
                                                info_ab["yaw_err"])
            and bool(ALVO_TOL == BONUS_XY),
            f"no_alvo = {info_ab['no_alvo']} · ALVO_TOL = {ALVO_TOL} == BONUS_XY = {BONUS_XY} (compatibilidade)")

    try:
        from stable_baselines3.common.env_checker import check_env
    except ImportError as exc:                        # sem o grupo hover-rl instalado
        v.check("check_env do Stable-Baselines3", False,
                f"stable_baselines3 indisponível ({exc}) — correr com `uv run --group hover-rl`")
        return
    e_check = HoverEnv()
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        try:
            check_env(e_check, warn=True)
            erro = None
        except Exception as exc:                      # noqa: BLE001  (queremos reportar qualquer falha)
            erro = f"{type(exc).__name__}: {exc}"
    v.check("check_env do Stable-Baselines3 passa sem exceção", erro is None,
            erro if erro else f"avisos: {[str(w.message) for w in avisos] or 'nenhum'}")

    # o check_env faz rollouts com ações aleatórias: aqui fica o registo do que ele exercitou
    e_rand = HoverEnv()
    e_rand.reset(seed=1)
    ok_rand = True
    for _ in range(50):
        obs, r, term, trunc, info = e_rand.step(e_rand.action_space.sample())
        ok_rand &= bool(np.isfinite(obs).all() and np.isfinite(r))
        if term or trunc:
            e_rand.reset(seed=1)
    v.check("50 passos com ações aleatórias: obs/recompensa finitos, sem NaN/inf", ok_rand, "")


# --------------------------------------------------------------------------------------- 7 · robustez
def erro_de(fn) -> tuple[str | None, str]:
    """(nome da exceção, mensagem) levantada por `fn`, ou `(None, 'sem erro')` — classifica as guardas."""
    try:
        fn()
    except Exception as exc:                          # noqa: BLE001  (queremos classificar qualquer exceção)
        return type(exc).__name__, str(exc)
    return None, "sem erro"


def checa_robustez(v: Validador) -> None:
    print("\n7 · ROBUSTEZ (D1 não-finitos/sanidade · D2 faixa do alvo · D3 cartesiano vs polar)")
    print("      nenhum NaN/inf entra em silêncio em opt.wind/data.ctrl e nenhum alvo dá bónus de graça")

    casos = [("definir_vento(nan, 0)", lambda: HoverEnv().definir_vento(float("nan"), 0.0)),
             ("definir_vento(inf, 0)", lambda: HoverEnv().definir_vento(float("inf"), 0.0)),
             ("definir_vento(1, nan)", lambda: HoverEnv().definir_vento(1.0, float("nan"))),
             ("definir_vento(1, 0, inf)", lambda: HoverEnv().definir_vento(1.0, 0.0, float("inf"))),
             ("definir_vento_aleatorio(0, nan)", lambda: HoverEnv().definir_vento_aleatorio(0.0, float("nan"))),
             ("definir_vento_aleatorio(nan, 1)", lambda: HoverEnv().definir_vento_aleatorio(float("nan"), 1.0)),
             ("definir_vento_aleatorio(0, inf)", lambda: HoverEnv().definir_vento_aleatorio(0.0, float("inf")))]
    res = [(nome, *erro_de(fn)) for nome, fn in casos]
    v.check("D1 vento não-finito → ValueError (era opt.wind=[nan,nan,nan] silencioso / OverflowError cru)",
            all(t == "ValueError" and m for _, t, m in res),
            " · ".join(f"{nome} → {t}" for nome, t, _ in res))
    v.check("D1 mensagem das guardas de vento diz qual o argumento e o valor recebido",
            all(("FINITO" in m and "recebido" in m) for _, t, m in res if t == "ValueError"),
            res[0][2][:110] + " …")

    e_nan = HoverEnv()
    e_nan.reset(seed=0)
    ctrl0, wind0 = e_nan.data.ctrl.copy(), e_nan.vento_atual.copy()
    tipos = [(nome, *erro_de(lambda a=a, e=e_nan: e.step(a))) for nome, a in
             (("[nan,0,0,0]", [float("nan"), 0.0, 0.0, 0.0]), ("[inf,0,0,0]", [float("inf"), 0.0, 0.0, 0.0]),
              ("[1,2]", [1.0, 2.0]), ("['x',0,0,0]", ["x", 0.0, 0.0, 0.0]))]
    v.check("D1 ação não-finita/mal formada no `step` → ValueError (era ctrl NaN + WARNING do MuJoCo)",
            all(t == "ValueError" and m for _, t, m in tipos),
            " · ".join(f"{nome} → {t}" for nome, t, _ in tipos))
    v.check("D1 ação recusada NÃO estraga o estado: ctrl e vento intactos e obs continua finita",
            bool(np.array_equal(ctrl0, e_nan.data.ctrl)) and bool(np.array_equal(wind0, e_nan.vento_atual))
            and bool(np.isfinite(e_nan.observacao()).all()),
            f"ctrl igual = {np.array_equal(ctrl0, e_nan.data.ctrl)} · vento igual = "
            f"{np.array_equal(wind0, e_nan.vento_atual)} · obs finita = {bool(np.isfinite(e_nan.observacao()).all())}")
    v.check("D1 `acao_para_ctrl([nan]*4)` → ValueError (a guarda vive no mapeamento, não só no step)",
            erro_de(lambda: HoverEnv().acao_para_ctrl([float("nan")] * 4))[0] == "ValueError",
            f"{erro_de(lambda: HoverEnv().acao_para_ctrl([float('nan')] * 4))[1][:100]} …")
    v.check("D1 `HoverEnv(alvo_z=nan)` → ValueError", erro_de(lambda: HoverEnv(alvo_z=float("nan")))[0] == "ValueError",
            erro_de(lambda: HoverEnv(alvo_z=float("nan")))[1][:100])

    e_div = HoverEnv(vento=(1.0e4, 0.0, 0.0))
    e_div.reset(seed=0)
    tipo_div, msg_div = None, ""
    for k in range(60):
        tipo_div, msg_div = erro_de(lambda: e_div.step([0.0, 0.0, 0.0, 0.0]))
        if tipo_div is not None:
            break
    e_ok = HoverEnv(vento=(5.0, 0.0, 0.0))
    e_ok.reset(seed=0)
    poe_estado(e_ok, (0.0, 0.0, 1.0))
    for _ in range(50):
        _, r_ok, term_ok, _, info_ok = e_ok.step([0.0, 0.0, 0.0, 0.0])
    v.check("D1 vento absurdo mas FINITO (1e4 m/s) → RuntimeError com o estado medido (era v=1e4… garbage "
            "silencioso, com o MuJoCo só a avisar no stderr)",
            tipo_div == "RuntimeError" and "DIVERGIU" in msg_div and "‖v‖" in msg_div,
            f"passo {k} → {tipo_div}: {msg_div[:120]} …")
    v.check("D1 sanidade NÃO incomoda o vento legítimo: +5 m/s continua a voar 1 s sem erro nem NaN",
            tipo_div is not None and not term_ok and np.isfinite(r_ok) and abs(info_ok["z"] - 1.0) < 5e-3
            and bool(np.isfinite(e_ok.observacao()).all()),
            f"vento 5 m/s → z = {info_ok['z']:.6f} m · r = {r_ok:+.6f} · term = {term_ok}")

    fora = [0.004, 0.0625, 0.099, 2.91, 3.5, -1.0, 0.0]
    res_alvo = [(a, *erro_de(lambda a=a: HoverEnv(alvo_z=a))) for a in fora]
    v.check("D2 alvo_z fora de [0,10, 2,90] m → ValueError (abaixo o bónus sairia de graça com o drone pousado)",
            all(t == "ValueError" and "0.1" in m and "2.9" in m for _, t, m in res_alvo),
            " · ".join(f"{a} → {t}" for a, t, _ in res_alvo))
    limites_ok = [erro_de(lambda a=a: HoverEnv(alvo_z=a))[0] is None for a in (0.10, 1.0, 2.90)]
    e_alvo = HoverEnv()
    e_alvo.reset(seed=0)
    rs = []
    for _ in range(50):
        _, r_a, term_a, trunc_a, _ = e_alvo.step([-1.0, 0.0, 0.0, 0.0])   # motores DESLIGADOS
        rs.append(r_a)
        if term_a or trunc_a:
            break
    v.check("D2 limites aceites (0,10 · 1,0 · 2,90) e alvo_z=1,0 com motores desligados NÃO dá bónus "
            "(r médio < 0, era +0,94/passo com alvo_z=0,004)",
            all(limites_ok) and max(rs) < 0.0,
            f"limites válidos = {limites_ok} · r médio = {np.mean(rs):+.4f} (máx {max(rs):+.4f}) em {len(rs)} passos")

    e_cart = HoverEnv(vento=(3.0, 45.0, 0.0))
    e_pol = HoverEnv()
    v_pol = e_pol.definir_vento(3.0, 45.0)
    v.check("D3 `vento=(3, 45, 0)` é CARTESIANO (‖w‖ = 45,1 m/s) e `definir_vento(3, 45)` é POLAR "
            "(3 m/s a 45° → ≈2,12 m/s em +x e +y) — convenções diferentes, comportamento antigo preservado",
            bool(np.allclose(e_cart.vento_atual, [3.0, 45.0, 0.0], atol=1e-12))
            and abs(float(np.linalg.norm(e_cart.vento_atual)) - 45.1) < 0.01
            and bool(np.allclose(v_pol, [3.0 * np.cos(np.radians(45)), 3.0 * np.sin(np.radians(45)), 0.0], atol=1e-15))
            and abs(float(np.linalg.norm(v_pol)) - 3.0) < 1e-15,
            f"cartesiano: opt.wind = {np.round(e_cart.vento_atual, 9)} (‖w‖ = {np.linalg.norm(e_cart.vento_atual):.4f} m/s) · "
            f"polar: opt.wind = {np.round(v_pol, 6)} (‖w‖ = {np.linalg.norm(v_pol):.6f} m/s)")
    doc_init = HoverEnv.__init__.__doc__ or ""
    doc_polar = HoverEnv.definir_vento.__doc__ or ""
    doc_modulo = sys.modules["env"].__doc__ or ""
    v.check("D3 as duas convenções estão EXPLÍCITAS nos docstrings (CARTESIANO no __init__/módulo, POLAR em "
            "definir_vento) e `vento` errado dá erro claro (não o reshape opaco do NumPy)",
            "CARTESIANO" in doc_init and "POLAR" in doc_polar and "CARTESIANO" in doc_modulo
            and "3 componentes" in erro_de(lambda: HoverEnv(vento=(1.0, 2.0)))[1]
            and erro_de(lambda: HoverEnv(vento=(float("nan"), 0.0, 0.0)))[0] == "ValueError",
            f"docstrings: CARTESIANO no __init__ = {'CARTESIANO' in doc_init} · POLAR em definir_vento = "
            f"{'POLAR' in doc_polar} · CARTESIANO no módulo = {'CARTESIANO' in doc_modulo} · "
            f"vento=(1,2) → {erro_de(lambda: HoverEnv(vento=(1.0, 2.0)))[1][:60]} …")


# --------------------------------------------------------------------------------------- 8 · contrato
def checa_contrato(v: Validador) -> None:
    print("\n8 · CONTRATO DO MODELO E DO AMBIENTE (contagens, dt, decimation, upstream intacto)")
    e = HoverEnv()
    m = e.model
    nomes = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_SENSOR, i) for i in range(m.nsensor)]
    v.check("nu = 4 e nactuator = 4 (escrita 1:1 em data.ctrl)", m.nu == 4 and m.nactuator == 4,
            f"nu = {m.nu} · nactuator = {m.nactuator} · ctrladr = {list(m.actuator_ctrladr)}")
    v.check("os 4 canais são `body_thrust` + x/y/z_moment, com ctrladr = [0,1,2,3]",
            [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(4)] == list(cf.MOTORES)
            and list(m.actuator_ctrladr) == [0, 1, 2, 3],
            f"atuadores = {list(cf.MOTORES)}")
    v.check("nsensor = 5 (gyro, linacc, quat + posicao/vel da camada lab/)", m.nsensor == 5,
            f"sensores = {nomes}")
    v.check("dt = 0,002 s (500 Hz, RK4)", abs(e.dt - 0.002) < 1e-15 and m.opt.integrator == mujoco.mjtIntegrator.mjINT_RK4,
            f"dt = {e.dt} s · integrador = {m.opt.integrator} (RK4) · dt de decisão = {e.dt_decisao} s "
            f"({1 / e.dt_decisao:.0f} Hz)")

    e.reset(seed=0)
    t0 = float(e.data.time)
    e.step([0.0, 0.0, 0.0, 0.0])
    t1 = float(e.data.time)
    v.check("decimation respeitada: data.time avança 0,02 s por step()", abs((t1 - t0) - 0.02) < 1e-12,
            f"Δt = {t1 - t0:.12f} s ({e.decimation} × {e.dt} s) · t após reset = {t0:.1f} s")

    texto = (AQUI.parents[1] / "models" / "bitcraze_crazyflie_2" / "cf2.xml").read_text()
    m_lab, _ = cf.carregar()
    v.check("cf2.xml upstream intacto (ctrlrange 0,35 N e gear ±1e-5 em disco e numa carga nova)",
            'ctrlrange="0 0.35"' in texto and "-0.00001" in texto
            and float(m_lab.actuator_ctrlrange[m_lab.actuator("body_thrust").id, 1]) == 0.35,
            f"thrust ctrlrange numa carga nova = {m_lab.actuator_ctrlrange[m_lab.actuator('body_thrust').id]} N · "
            f"O env usa {e.thrust_max} N só em memória")
    v.check("o env não altera o `opt.wind` do XML (só o escreve em memória): cf2.xml sem atributo wind",
            "wind=" not in texto and float(m_lab.opt.wind[0]) == 0.0 and bool(np.array_equal(e.vento_atual, np.zeros(3))),
            f"wind no XML: {'wind=' in texto} · opt.wind do env (vento=None) = {e.vento_atual} m/s")


# --------------------------------------------------------------------------------------- 9 · vento dinâmico
def vento_dinamico_em_passos(e: HoverEnv, passos: int) -> np.ndarray:
    """Norma do vento ATIVO em cada um dos `passos` primeiros passos de decisão (vetor (passos,)).

    A ação é `a = 0` (empuxo = peso) em todos os passos, para a leitura ser do VENTO (o drone pode derivar ou
    até terminar — o que interessa é o `opt.wind` de cada passo, que o `step` escreve antes da física).
    """
    return np.linalg.norm(vento_dinamico_vetores(e, passos), axis=1)


def vento_dinamico_vetores(e: HoverEnv, passos: int) -> np.ndarray:
    """Vento ATIVO em cada um dos `passos` primeiros passos de decisão (passos, 3), na ordem 1..passos.

    O `reset` deixa JÁ aplicado o vento do 1.º passo de decisão e cada `step` escreve o do passo que começa
    antes de correr a física (e não o muda depois), logo o valor lido DEPOIS do `step` i é o que atuou nesse
    passo — a série sai diretamente dos `step`, sem ler o estado do `reset` (que repetiria o 1.º passo).
    """
    serie = []
    for _ in range(passos):
        e.step([0.0, 0.0, 0.0, 0.0])
        serie.append(e.vento_atual.copy())
    return np.asarray(serie, dtype=float)


def gerador_dinamico_vetores(e: HoverEnv, passos: int) -> np.ndarray:
    """Vector do vento aplicado após `passos` chamadas a `_passo_vento` SEM física (passos, 3).

    Usado nas estatísticas do Dryden: 5 000 passos de física derivariam o drone (e poderiam até terminar o
    episódio), quando o que se está a medir é a recorrência do OU, não a resposta do veículo.
    """
    serie = []
    for _ in range(passos):
        e._passo_vento()               # objeto em validação: o gerador de vento é o alvo da medição
        serie.append(e.vento_atual.copy())
    return np.asarray(serie, dtype=float)


def gerador_dinamico(e: HoverEnv, passos: int) -> np.ndarray:
    """Norma do vento após `passos` chamadas a `_passo_vento` SEM física (atalho de `gerador_dinamico_vetores`)."""
    return np.linalg.norm(gerador_dinamico_vetores(e, passos), axis=1)


def checa_vento_dinamico(v: Validador) -> None:
    print("\n9 · VENTO DINÂMICO (por cima do vento base; fórmulas fechadas, modelo fresco por teste)")
    print("      rajadas: ‖w(k)‖ = u·sin(π·k/(N+1)) · frente: degrau no passo k = floor(t_s/0,02)+1 · "
          "dryden: x ← α·x + σ·√(1−α²)·ξ, α = exp(−0,02·V/L), V = max(‖base‖, v_min)")
    print("      `vento_dinamico=None` (predefinição) → nada disto é chamado: o caminho é o contrato v2b")

    e_padrao = HoverEnv()
    v.check("vento_dinamico=None (predefinição) → nenhum vento dinâmico e info com as 8 chaves "
            "(vento_atual == vento_vel == ‖opt.wind‖)",
            e_padrao.vento_dinamico is None and e_padrao._info()["vento_atual"] == e_padrao._info()["vento_vel"]
            and e_padrao._info()["vento_atual"] == 0.0 and set(e_padrao._info()) == CHAVES_INFO,
            f"vento_dinamico = {e_padrao.vento_dinamico} · opt.wind = {e_padrao.vento_atual} m/s · "
            f"info = {{{', '.join(f'{k}={e_padrao._info()[k]:.6f}' if isinstance(e_padrao._info()[k], float) else f'{k}={e_padrao._info()[k]}' for k in sorted(e_padrao._info()))}}}")

    print("  (a) validação da config (`valida_vento_dinamico`): defaults preenchidos e ValueError claro")
    defaults = [({"modo": "rajadas"}, {"modo": "rajadas", "u_max": 3.0, "p": 0.02, "duracao": 10}),
                ({"modo": "frente"}, {"modo": "frente", "u_max": 3.0, "t_s": 2.0}),
                ({"modo": "dryden"}, {"modo": "dryden", "u_max": 3.0, "sigma": 0.5, "L": 10.0, "v_min": 1.0})]
    ok_defaults = all(valida_vento_dinamico(entrada) == esperado for entrada, esperado in defaults)
    entrada_nao_mexida = {"modo": "rajadas"}
    valida_vento_dinamico(entrada_nao_mexida)
    v.check("defaults de cada modo preenchidos (u_max 3,0 · p 0,02 · duracao 10 · t_s 2,0 · σ 0,5 · L 10 · "
            "v_min 1) e o dict recebido NÃO é alterado",
            ok_defaults and entrada_nao_mexida == {"modo": "rajadas"} and valida_vento_dinamico(None) is None,
            " · ".join(f"{modo}: {valida_vento_dinamico(entrada)}" for entrada, modo in
                       zip((d[0] for d in defaults), ("rajadas", "frente", "dryden"), strict=True)))

    invalidos = [
        ("sem modo", {"p": 0.02}), ("modo desconhecido", {"modo": "vendaval"}), ("chave gralha", {"modo": "rajadas", "durancao": 5}),
        ("p > 1", {"modo": "rajadas", "p": 1.5}), ("p < 0", {"modo": "rajadas", "p": -0.1}),
        ("duracao = 0", {"modo": "rajadas", "duracao": 0}), ("duracao float", {"modo": "rajadas", "duracao": 2.5}),
        ("t_s < 0", {"modo": "frente", "t_s": -1.0}), ("u_max < 0", {"modo": "frente", "u_max": -1.0}),
        ("σ = 0", {"modo": "dryden", "sigma": 0.0}), ("L = 0", {"modo": "dryden", "L": 0.0}),
        ("v_min = 0", {"modo": "dryden", "v_min": 0.0}), ("modo NaN", {"modo": "dryden", "sigma": float("nan")}),
        ("não é dict", "rajadas"),
    ]
    res_inv = [(nome, *erro_de(lambda c=c: valida_vento_dinamico(c))) for nome, c in invalidos]
    v.check(f"config inválidas → ValueError nas {len(invalidos)} formas (modo/chave/faixa/tipo)",
            all(t == "ValueError" and m for _, t, m in res_inv),
            " · ".join(f"{nome} → {t}" for nome, t, _ in res_inv))
    v.check("a mensagem das guardas diz qual a chave e o valor recebido (não um KeyError/TypeError opaco)",
            "modo" in dict(zip((n for n, _, _ in res_inv), (m for _, _, m in res_inv)))["sem modo"]
            and "durancao" in dict(zip((n for n, _, _ in res_inv), (m for _, _, m in res_inv)))["chave gralha"],
            f"sem modo: {res_inv[0][2][:80]} … · chave gralha: {res_inv[2][2][:80]} …")

    print("  (b) rajadas: envelope sin(π·k/(N+1)) somado ao vento base, e rajada nova quando a anterior acaba")
    e_r0 = HoverEnv(vento=(1.0, 0.0, 0.0), vento_dinamico={"modo": "rajadas", "p": 0.0, "duracao": 5, "u_max": 3.0})
    e_r0.reset(seed=0)
    normas_r0 = vento_dinamico_em_passos(e_r0, 20)
    v.check("p = 0 → nenhuma rajada em 20 passos: o vento base (1, 0, 0) mantém-se passo a passo",
            bool(np.allclose(normas_r0, 1.0, atol=1e-15)) and bool(np.allclose(e_r0.vento_atual, [1.0, 0.0, 0.0], atol=1e-15)),
            f"‖w‖ = {np.round(normas_r0, 6)} m/s (base 1 m/s, u_max 3)")

    e_r1 = HoverEnv(vento_dinamico={"modo": "rajadas", "p": 1.0, "duracao": 5, "u_max": 3.0})
    e_r1.reset(seed=0)
    medido_r1 = vento_dinamico_em_passos(e_r1, 5)                 # k = 1..5 (uma rajada inteira)
    amp = float(medido_r1[0]) / np.sin(np.pi / 6.0)               # k=1 → env = sin(π/6) = 0,5 → u = ‖w₁‖/0,5
    previsto_r1 = amp * np.sin(np.pi * np.arange(1, 6) / 6.0)
    v.check("p = 1, duracao = 5, u_max = 3 → perfil medido ‖w(k)‖ = u·sin(π·k/6) (k = 1..5) em todos os passos",
            bool(np.allclose(medido_r1, previsto_r1, atol=1e-12)) and 0.0 <= amp <= 3.0,
            f"u = {amp:.9f} m/s (≤ u_max 3) · medido {np.round(medido_r1, 9)} · "
            f"previsto {np.round(previsto_r1, 9)} m/s")
    e_r1v = HoverEnv(vento_dinamico={"modo": "rajadas", "p": 1.0, "duracao": 5, "u_max": 3.0})
    e_r1v.reset(seed=0)
    w1 = e_r1v.vento_atual.copy()                                 # k = 1 da 1.ª rajada (aplicado no reset)
    norma1 = float(np.linalg.norm(w1))
    elevacao_r1 = float(np.degrees(np.arcsin(np.clip(w1[2] / max(norma1, 1e-15), -1.0, 1.0))))
    azimute_r1 = float(np.degrees(np.arctan2(w1[1], w1[0])) % 360.0)
    v.check("rajada: direção amostrada dentro das bandas do env (elevação ±20°, azimute [0, 360)) e "
            "amplitude u ∈ [0, u_max]",
            abs(elevacao_r1) <= np.degrees(VENTO_ELEV_MAX) + 1e-9 and 0.0 <= azimute_r1 < 360.0
            and 0.0 <= amp <= 3.0,
            f"vetor em k=1 = {np.round(w1, 9)} m/s · elevação = {elevacao_r1:.4f}° (limite "
            f"±{np.degrees(VENTO_ELEV_MAX):.0f}°) · azimute = {azimute_r1:.3f}° · u = {amp:.6f} m/s ∈ [0, 3]")
    e_r1.step([0.0, 0.0, 0.0, 0.0])               # passo 6: a rajada acabou (N=5) e p=1 começa OUTRA
    w6 = e_r1.vento_atual.copy()
    amp2 = float(np.linalg.norm(w6)) / np.sin(np.pi / 6.0)
    v.check("acabada a rajada de 5 passos, p = 1 começa logo outra (passo 6): envelope no k = 1 e amplitude "
            "nova sorteada (≤ u_max)",
            abs(float(np.linalg.norm(w6)) - amp2 * np.sin(np.pi / 6.0)) < 1e-12 and 0.0 <= amp2 <= 3.0
            and e_r1._rajada_n == int(e_r1.vento_dinamico["duracao"]) and e_r1._rajada_k == 1,
            f"passo 6: ‖w‖ = {float(np.linalg.norm(w6)):.9f} m/s → u₂ = {amp2:.6f} m/s · rajada k=1/N=5")

    e_rs = HoverEnv(vento=(1.0, 0.0, 0.0), vento_dinamico={"modo": "rajadas", "p": 1.0, "duracao": 5, "u_max": 3.0})
    e_rs.reset(seed=3)
    w_sup = vento_dinamico_vetores(e_rs, 5)   # a rajada inteira (k = 1..5)
    u_sup = (w_sup - np.array([1.0, 0.0, 0.0])) / np.sin(np.pi * np.arange(1, 6) / 6.0)[:, None]
    v.check("rajada SOMADA ao vento base: (opt.wind − base)/env(k) é o mesmo vector em todos os passos da rajada",
            bool(np.allclose(u_sup, u_sup[0], atol=1e-12)) and 0.0 <= float(np.linalg.norm(u_sup[0])) <= 3.0,
            f"base = (1, 0, 0) · vector da rajada = {np.round(u_sup[0], 9)} m/s · desvio máx = "
            f"{np.abs(u_sup - u_sup[0]).max():.2e}")

    e_r0u = HoverEnv(vento=(1.0, 0.0, 0.0), vento_dinamico={"modo": "rajadas", "p": 1.0, "duracao": 5, "u_max": 0.0})
    e_r0u.reset(seed=0)
    normas_r0u = vento_dinamico_em_passos(e_r0u, 12)
    v.check("u_max = 0 é aceite e significa modo INERTE: p = 1 com u_max = 0 não muda o vento base",
            bool(np.allclose(normas_r0u, 1.0, atol=1e-15)),
            f"‖w‖ = {np.round(normas_r0u, 12)} m/s (base 1 m/s)")

    print("  (c) frente: degrau no passo k = floor(t_s/0,02)+1, substitui o vento base até ao fim")
    e_f = HoverEnv(vento=(1.0, 0.0, 0.0), vento_dinamico={"modo": "frente", "u_max": 3.0, "t_s": 0.2})
    e_f.reset(seed=1)
    k_frente = e_f._passo_da_frente(0.2)
    na_frente = vento_dinamico_vetores(e_f, 13)   # passos 1..13 (o reset já deixa o passo 1 aplicado)
    antes_ok = bool(np.allclose(na_frente[:k_frente - 1], [1.0, 0.0, 0.0], atol=1e-15))   # passos 1..10
    depois_ok = bool(np.allclose(na_frente[k_frente - 1:], na_frente[k_frente - 1], atol=1e-15))  # 11..13
    norma_frente = float(np.linalg.norm(na_frente[k_frente - 1]))
    v.check("t_s = 0,2 s → passo da frente k = floor(0,2/0,02)+1 = 11: base nos 10 primeiros passos, degrau no "
            "11.º e constante até ao fim",
            k_frente == 11 and na_frente.shape[0] == 13 and antes_ok and depois_ok
            and FRENTE_U_MIN - 1e-12 <= norma_frente <= 3.0,
            f"k = {k_frente} · ‖w‖ por passo (1..13) = {np.round(np.linalg.norm(na_frente, axis=1), 6)} "
            f"(base 1 m/s → frente {norma_frente:.6f} m/s ∈ [0,5; 3])")
    e_f2 = HoverEnv(vento=(1.0, 0.0, 0.0), vento_dinamico={"modo": "frente", "u_max": 3.0, "t_s": 0.0})
    _, info_f2 = e_f2.reset(seed=1)
    v.check("t_s = 0 → a frente já atua no 1.º passo de decisão (k = 1) e substitui o base desde o `reset`",
            e_f2._passo_da_frente(0.0) == 1 and not bool(np.allclose(e_f2.vento_atual, [1.0, 0.0, 0.0], atol=1e-15))
            and abs(info_f2["vento_atual"] - float(np.linalg.norm(e_f2.vento_atual))) < 1e-15,
            f"k = {e_f2._passo_da_frente(0.0)} · opt.wind no reset = {np.round(e_f2.vento_atual, 6)} m/s "
            f"(base era (1, 0, 0)) · info['vento_atual'] = {info_f2['vento_atual']:.6f} m/s")

    e_fa = HoverEnv(vento_dinamico={"modo": "frente", "u_max": 3.0, "t_s": 1.0})
    amplitudes = []
    for s in range(60):
        e_fa.reset(seed=s)
        amplitudes.append(float(np.linalg.norm(e_fa._frente_vec)))
    v.check(f"frente amostrada ~ U[{FRENTE_U_MIN}; 3] m/s em 60 seeds (mín ≥ 0,5 · máx ≤ 3 · varia)",
            min(amplitudes) >= FRENTE_U_MIN - 1e-12 and max(amplitudes) <= 3.0 + 1e-12
            and max(amplitudes) - min(amplitudes) > 0.5,
            f"min = {min(amplitudes):.4f} · max = {max(amplitudes):.4f} · média = {np.mean(amplitudes):.4f} m/s")
    e_fb = HoverEnv(vento_dinamico={"modo": "frente", "u_max": 3.0, "t_s": 1.0})
    e_fb.reset(seed=7)
    w_a7, w_b7 = e_fb._frente_vec.copy(), e_fb._frente_vec.copy()
    e_fb.reset(seed=7)
    w_a7b = e_fb._frente_vec.copy()
    e_fb.reset(seed=8)
    w_c8 = e_fb._frente_vec.copy()
    v.check("frente determinística dada a seed (seed 7 duas vezes → o mesmo vector; seed 8 → outro)",
            bool(np.array_equal(w_a7, w_a7b)) and not bool(np.array_equal(w_a7, w_c8)) and bool(np.array_equal(w_a7, w_b7)),
            f"seed 7 = {np.round(w_a7, 6)} · seed 7 = {np.round(w_a7b, 6)} · seed 8 = {np.round(w_c8, 6)} m/s")

    fora_ep = [("t_s = episodio_s", {"modo": "frente", "u_max": 3.0, "t_s": 10.0}, {}),
               ("t_s > episodio_s (curto)", {"modo": "frente", "u_max": 3.0, "t_s": 0.5}, {"episodio_s": 0.4})]
    res_fora = [(nome, *erro_de(lambda c=c, k=k: HoverEnv(vento_dinamico=c, **k))) for nome, c, k in fora_ep]
    v.check("frente fora do episódio (t_s ≥ fim) → ValueError (o passo da frente passaria de `max_passos`)",
            all(t == "ValueError" and "passo" in m for _, t, m in res_fora),
            " · ".join(f"{nome} → {t}: {m[:60]}…" for nome, t, m in res_fora))

    print("  (d) dryden: OU x ← α·x + σ·√(1−α²)·ξ com α = exp(−0,02·V/L) e V = max(‖base‖, v_min)")
    n_ou = 5000
    resultados_ou = {}
    for v_base, v_min, etiqueta in (((0.0, 0.0, 0.0), 1.0, "base nulo → V = v_min = 1"),
                                    ((4.0, 0.0, 0.0), 1.0, "base 4 m/s → V = ‖base‖ = 4")):
        e_d = HoverEnv(vento=v_base, vento_dinamico={"modo": "dryden", "sigma": 0.5, "L": 10.0,
                                                     "u_max": 10.0, "v_min": v_min})
        e_d.reset(seed=0)
        base = np.asarray(v_base, dtype=float)
        xs = gerador_dinamico_vetores(e_d, n_ou) - base     # x do OU = vento aplicado − vento base
        v_ref = max(float(np.linalg.norm(base)), v_min)
        alpha = float(np.exp(-e_d.dt_decisao * v_ref / 10.0))
        d = xs[1:] - alpha * xs[:-1]
        resultados_ou[etiqueta] = (alpha, 0.5 * float(np.sqrt(1 - alpha ** 2)), float(d.std()), float(d.mean()),
                                   float(xs.std()), v_ref)
    completa = all(abs(desvio - previsto) / previsto < 0.03 for _, previsto, desvio, *_ in resultados_ou.values())
    v.check(f"dryden: desvio-padrão dos incrementos d = x(k+1) − α·x(k) == σ·√(1−α²) (N = {n_ou} passos, "
            "erro < 3 %) nos DOIS regimes de V",
            completa and all(abs(media) < 5e-3 for _, _, _, media, _, _ in resultados_ou.values()),
            " · ".join(f"{etq}: α = {a:.9f} · σ√(1−α²) = {p:.9f} vs medido {d_:.9f} (média {m:+.2e})"
                       for etq, (a, p, d_, m, _, _) in resultados_ou.items()))
    v.check("dryden: V = max(‖base‖, v_min) — o α do regime com base 4 m/s é o de V = 4 (não o de v_min) e "
            "σ(x) ≈ σ = 0,5 m/s (processo estacionário)",
            abs(resultados_ou["base 4 m/s → V = ‖base‖ = 4"][0] - float(np.exp(-0.02 * 4.0 / 10.0))) < 1e-15
            and all(abs(sx - 0.5) < 0.12 for *_, sx, _ in resultados_ou.values()),
            " · ".join(f"{etq}: α = {a:.9f} (V = {vv:g} m/s) · σ(x) medido = {sx:.4f} m/s (σ = 0,5)"
                       for etq, (a, _, _, _, sx, vv) in resultados_ou.items()))

    e_ds = HoverEnv(vento_dinamico={"modo": "dryden", "sigma": 5.0, "L": 10.0, "u_max": 0.2})
    e_ds.reset(seed=0)
    normas_sat = gerador_dinamico(e_ds, 300)
    v.check("dryden saturado: com σ = 5 e u_max = 0,2 a norma do vento aplicado nunca passa u_max",
            bool(np.all(normas_sat <= 0.2 + 1e-12)) and float(normas_sat.max()) > 0.19,
            f"‖w‖ ∈ [{normas_sat.min():.6f}, {normas_sat.max():.6f}] m/s (teto 0,2)")

    print("  (e) reconfiguração em runtime (é o que o treino faz quando o estágio do currículo sobe)")
    e_rt = HoverEnv(vento=(1.0, 0.0, 0.0), vento_dinamico={"modo": "rajadas", "p": 0.0, "duracao": 5, "u_max": 3.0})
    e_rt.reset(seed=0)
    cfg_nova = e_rt.definir_vento_dinamico({"modo": "rajadas", "p": 1.0, "duracao": 5, "u_max": 0.5})
    # o vento do passo 1 foi planeado no `reset` (fica o base); a config nova governa os passos SEGUINTES
    w_rt = vento_dinamico_vetores(e_rt, 3)
    u_rt = (w_rt[1:] - np.array([1.0, 0.0, 0.0])) / np.sin(np.pi * np.arange(1, 3) / 6.0)[:, None]
    v.check("definir_vento_dinamico troca p/u_max em runtime: passa a haver rajada (p = 0 → 1) no passo "
            "seguinte, com o envelope do modo e a amplitude limitada pelo u_max novo (0,5)",
            cfg_nova == {"modo": "rajadas", "u_max": 0.5, "p": 1.0, "duracao": 5}
            and bool(np.allclose(w_rt[0], [1.0, 0.0, 0.0], atol=1e-15))
            and bool(np.allclose(u_rt, u_rt[0], atol=1e-12)) and 0.05 < float(np.linalg.norm(u_rt[0])) <= 0.5 + 1e-12,
            f"‖w‖ por passo = {np.round(np.linalg.norm(w_rt, axis=1), 6)} m/s · vector da rajada = "
            f"{np.round(u_rt[0], 6)} m/s (‖{np.linalg.norm(u_rt[0]):.6f}‖ ≤ u_max 0,5) · "
            f"config devolvida = {cfg_nova}")
    e_rt.definir_vento_dinamico(None)
    v.check("definir_vento_dinamico(None) desliga o modo e devolve o vento BASE a `opt.wind`",
            e_rt.vento_dinamico is None and bool(np.allclose(e_rt.vento_atual, [1.0, 0.0, 0.0], atol=1e-15)),
            f"opt.wind = {np.round(e_rt.vento_atual, 9)} m/s · vento_dinamico = {e_rt.vento_dinamico}")
    erro_rt = erro_de(lambda: e_rt.definir_vento_dinamico({"modo": "vendaval"}))
    v.check("definir_vento_dinamico valida como o __init__ (modo inválido → ValueError, sem escrita em opt.wind)",
            erro_rt[0] == "ValueError" and e_rt.vento_dinamico is None,
            f"{erro_rt[0]}: {erro_rt[1][:80]} …")

    print("  (f) arranque: o drone começa POUSADO e o vento dinâmico já atua no 1.º passo de decisão")
    e_arr = HoverEnv(vento_dinamico={"modo": "rajadas", "p": 1.0, "duracao": 10, "u_max": 3.0})
    _, info_arr = e_arr.reset(seed=0)
    z_arr = float(e_arr.data.sensor("posicao").data[2])
    v.check("com rajadas p = 1 o reset devolve o drone POUSADO (z ≈ 0,0125 m < 0,05) e o vento da 1.ª rajada "
            "JÁ aplicado em opt.wind (o 1.º passo de decisão é contra ele)",
            z_arr < 0.05 and info_arr["vento_atual"] > 0.0
            and abs(info_arr["vento_atual"] - float(np.linalg.norm(e_arr.vento_atual))) < 1e-15
            and abs(float(e_arr.data.time)) < 1e-15,
            f"z no reset = {z_arr:.6f} m · t = {e_arr.data.time:.2f} s · vento no reset = "
            f"{info_arr['vento_atual']:.6f} m/s (norma da 1.ª rajada no k = 1)")
    e_arr.reset(seed=0)
    _, _, term_arr, _, info_arr2 = e_arr.step([-1.0, 0.0, 0.0, 0.0])   # motores desligados: cai e termina
    v.check("a física do 1.º passo corre com o vento dinâmico aplicado (a norma lida pós-passo é a do vento "
            "que atuou) e o drone pousado só termina por impacto, não por 'mágica'",
            abs(info_arr2["vento_atual"] - float(np.linalg.norm(e_arr.vento_atual))) < 1e-15
            and info_arr2["vento_atual"] > 0.0,
            f"pós-passo: info['vento_atual'] = {info_arr2['vento_atual']:.6f} m/s == ‖opt.wind‖ = "
            f"{float(np.linalg.norm(e_arr.vento_atual)):.6f} m/s · terminou = {term_arr} · z = {info_arr2['z']:.5f} m")

    print("  (g) u_max = 0 = modo INERTE em TODOS os modos (ar parado a sério: só o vento base, sem sortear nada)")
    inerte = {}
    for modo, extra in (("rajadas", {"p": 1.0, "duracao": 5}), ("frente", {"t_s": 0.0}),
                        ("dryden", {"sigma": 5.0, "L": 10.0})):
        e_i = HoverEnv(vento=(1.0, 0.0, 0.0), vento_dinamico={"modo": modo, "u_max": 0.0, **extra})
        e_i.reset(seed=0)
        vetores_i = vento_dinamico_vetores(e_i, 50)
        inerte[modo] = float(np.abs(vetores_i - np.array([1.0, 0.0, 0.0])).max())
    v.check("u_max = 0 → INERTE nos TRÊS modos: 50 passos de `step` mantêm exatamente o vento base "
            "(rajadas com p = 1, frente com t_s = 0 e dryden com σ = 5 não entram na física)",
            all(d == 0.0 for d in inerte.values()),
            " · ".join(f"{m}: |w − base|∞ = {d:.1e} m/s" for m, d in inerte.items()))

    e_di = HoverEnv(vento=(1.0, 0.0, 0.0), vento_dinamico={"modo": "dryden", "u_max": 0.0, "sigma": 5.0, "L": 10.0})
    e_di.reset(seed=0)
    desvio_ou = gerador_dinamico_vetores(e_di, 200) - np.array([1.0, 0.0, 0.0])
    v.check("u_max = 0 no dryden não deixa entrar turbulência NENHUMA (era o defeito D1: sem saturação o OU "
            "escrevia vento ≠ base em `opt.wind` — medido antes: ‖w‖ até 1,94 com base 1 m/s)",
            float(np.abs(desvio_ou).max()) == 0.0 and bool(np.allclose(e_di.vento_atual, [1.0, 0.0, 0.0], atol=1e-15)),
            f"|w − base|∞ = {float(np.abs(desvio_ou).max()):.1e} m/s em 200 passos do gerador · opt.wind = "
            f"{np.round(e_di.vento_atual, 12)} m/s")

    e_fi = HoverEnv(vento=(1.0, 0.0, 0.0), vento_dinamico={"modo": "frente", "u_max": 0.0, "t_s": 0.0})
    e_ref = HoverEnv(vento=(1.0, 0.0, 0.0))                    # mesmo estado inicial, SEM vento dinâmico
    obs_fi, info_fi = e_fi.reset(seed=0)
    obs_ref, _ = e_ref.reset(seed=0)
    for _ in range(30):
        e_fi.step([0.0, 0.0, 0.0, 0.0])
        e_ref.step([0.0, 0.0, 0.0, 0.0])
    v.check("u_max = 0 na frente não faz degrau nenhum (era o defeito D2: com t_s = 0 o degrau valia 0 e "
            "SUBSTITUÍA o base, ‖w‖ 1,0 → 0,0 no 1.º passo) e nem consome o np_random: obs do reset e após "
            "30 passos idênticas às de um env SEM vento dinâmico",
            abs(info_fi["vento_atual"] - 1.0) < 1e-15
            and bool(np.allclose(e_fi.vento_atual, [1.0, 0.0, 0.0], atol=1e-15))
            and bool(np.array_equal(obs_fi, obs_ref)) and bool(np.array_equal(e_fi.observacao(), e_ref.observacao()))
            and e_fi._frente_vec.tolist() == [0.0, 0.0, 0.0],
            f"‖w‖ no reset = {info_fi['vento_atual']:.12f} m/s (base 1) · obs do reset == env sem dinâmico: "
            f"{bool(np.array_equal(obs_fi, obs_ref))} · obs após 30 passos == : {bool(np.array_equal(e_fi.observacao(), e_ref.observacao()))} · frente amostrada = {e_fi._frente_vec}")

    e_ra = HoverEnv(vento_aleatorio=(2.0, 2.0), vento_dinamico={"modo": "rajadas", "p": 1.0, "duracao": 5, "u_max": 1.0})
    e_ra.reset(seed=4)
    base_ra = e_ra._base_vento.copy()
    w_ra = vento_dinamico_vetores(e_ra, 5)    # a rajada inteira (k = 1..5)
    residual = (w_ra - base_ra) / np.sin(np.pi * np.arange(1, 6) / 6.0)[:, None]
    v.check("currículo + dinâmico convivem: o vento base é o amostrado no reset (‖2 m/s‖) e a rajada entra "
            "por cima com o envelope (resíduo constante)",
            abs(float(np.linalg.norm(base_ra)) - 2.0) < 1e-12 and bool(np.allclose(residual, residual[0], atol=1e-12))
            and 0.0 <= float(np.linalg.norm(residual[0])) <= 1.0,
            f"base amostrado = {np.round(base_ra, 6)} m/s (‖{np.linalg.norm(base_ra):.6f}‖) · vector da rajada = "
            f"{np.round(residual[0], 6)} m/s · desvio máx = {np.abs(residual - residual[0]).max():.2e}")

# --------------------------------------------------------------------------------------- main
def main() -> int:
    print("Validação do HoverEnv v2 (experiments/09_drone_hover_rl/env.py) — fórmulas fechadas, modelo fresco por teste")
    e0 = HoverEnv()
    print(f"modelo: Crazyflie 2 do menagerie · m = {e0.massa:.4f} kg · mg = {e0.mg:.6f} N · "
          f"thrust_max = {e0.thrust_max:.3f} N (T/W = {e0.thrust_max / e0.mg:.2f}) · "
          f"momento_max = {np.round(e0.momento_max, 7)} N·m · dt = {e0.dt} s · decimation = {e0.decimation}")
    print(f"alvos: (x, y, z) = (0, 0, {e0.alvo_z:.2f}) m · yaw = {YAW_ALVO:.2f} rad · vento = "
          f"{'nenhum' if e0.vento is None else e0.vento} · ρ = {e0.model.opt.density} kg/m³ "
          f"(arrasto do fluido ativo)")

    v = Validador()
    t0 = time.perf_counter()
    checa_acao(v)
    checa_recompensa(v)
    checa_fisica(v)
    checa_vento(v)
    checa_observacao(v)
    checa_gymnasium(v)
    checa_robustez(v)
    checa_contrato(v)
    checa_vento_dinamico(v)
    parede = time.perf_counter() - t0

    e = HoverEnv()
    e.reset(seed=0)
    print(f"\nz em repouso no início do episódio: {e.data.sensor('posicao').data[2]:.6f} m "
          f"(keyframe do lab = 0,1 m; o env assenta o drone no chão antes do episódio)")
    t1 = time.perf_counter()
    for _ in range(500):
        e.step([0.0, 0.0, 0.0, 0.0])
    pps = 500 / (time.perf_counter() - t1)
    print(f"desempenho: {pps:.0f} passos de decisão/s (10 s de simulação em {500 / pps:.3f} s de parede) · "
          f"validação completa em {parede:.1f} s")

    print(f"\n{len(v.linhas) - v.falhas}/{len(v.linhas)} checagens [OK] · {v.falhas} [FALHA]")
    return 0 if v.tudo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
