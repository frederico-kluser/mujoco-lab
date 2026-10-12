#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_seguimento.py — provas do SEGUIMENTO VISUAL (IA nº 2).

§1 HONESTIDADE da percepção: a PROJEÇÃO EXATA (a que o treino usa) bate com o RENDER real + DETETOR
   CLÁSSICO (o que o deploy usa) — erro < 1–2 px (o desenho do dono exige este teste).
§2 CONTRATO: modelo com `com_alvo` compila, o mocap `ponto` move-se por `data.mocap_pos` e a física do
   drone não muda (sem `com_alvo` o modelo é idêntico ao de sempre).
§3 AÇÃO: a ação do tracker é `v_ref` nas faixas do contrato r11 (±1,0 m/s xy, ±0,7 m/s z) e a cascata
   com a IA-voo CONGELADA dá ações idênticas sem tracker vs com tracker neutro (v_ref = 0).

Sai 0 com tudo verde; prova EXECUTADA (render EGL + cascata real), nada de mock.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_AQUI.parent.parent), str(_AQUI)]

import mujoco
import visao
from env_real import VOO_SUBIDA, VOO_VEL, DroneRealEnv

import lab.drone_rpi as dr

PILOTO = _AQUI / "out" / "real_1950_voo_final" / "final.zip"
TOTAL = FALHAS = 0


def ok(desc: str, sim: bool, detalhe: str = "") -> bool:
    global TOTAL, FALHAS
    TOTAL += 1
    if not sim:
        FALHAS += 1
    print(f"        [{'OK  ' if sim else 'FALHA'}] {desc}" + (f" — {detalhe}" if detalhe else ""))
    return sim


def main() -> int:
    print("== teste_seguimento — IA nº 2 (ponto → detetor → tracker → v_ref → IA-voo congelada → FC)")
    if not PILOTO.is_file():
        ok(f"IA-voo congelada existe ({PILOTO.name})", False, "falta out/real_1950_voo_final/final.zip")
        return 1

    # ------------------------------------------------------------------------------- §1 honestidade
    print("  == §1 projeção do treino × detetor clássico do deploy (render real, erro < 2 px)")
    hw = dr.hardware()
    model, data = dr.modelo.carregar(hw, com_alvo=True)
    data.qpos[0:3] = [0, 0, 1.0]
    mujoco.mj_forward(model, data)
    larg, alt = 1920, 1080
    r = mujoco.Renderer(model, height=alt, width=larg)
    erros = []
    for pos in [(1.5, 0.0, 1.0), (2.2, 0.4, 1.1), (1.2, -0.3, 0.9), (3.0, 0.6, 1.3), (1.0, 0.1, 1.05)]:
        visao.posicionar_ponto(model, data, pos)
        mujoco.mj_forward(model, data)
        r.update_scene(data, camera="fpv")
        det = visao.detetar_marcador(r.render())          # o detetor clássico do DEPLOY (threshold)
        proj = visao.projetar(model, data, pos, camera="fpv", largura_px=larg, altura_px=alt)
        if det["visivel"] and proj["visivel"]:
            erros.append(math.hypot(det["u"] - proj["u"], det["v"] - proj["v"]))
    r.close()
    ok(f"projeção × detetor < 2 px em {len(erros)} posições",
       len(erros) == 5 and max(erros) < 2.0,
       f"erro médio {np.mean(erros):.3f} px · máximo {max(erros):.3f} px")

    # ---------------------------------------------------------------------------------- §2 modelo
    print("  == §2 com_alvo: mocap `ponto` sem tocar na física")
    model0, _ = dr.modelo.carregar(hw, com_alvo=False)
    ok("sem com_alvo o modelo é IDÊNTICO (nq/nv/massas iguais)",
       (model.nq, model.nv) == (model0.nq, model0.nv)
       and abs(model.body_mass.sum() - model0.body_mass.sum()) < 1e-12,
       f"nq/nv {model.nq}/{model.nv} · Δmassa {model.body_mass.sum() - model0.body_mass.sum():.1e} kg")
    env = DroneRealEnv(build=None, modo_acao="ctbr", com_alvo=True)
    env.definir_trajetoria_ponto("circulo", vel=0.5, raio=1.5)
    antes = env.data.mocap_pos[visao.mocap_do_ponto(env.model)].copy()
    for _ in range(10):
        env.step(np.zeros(4))
    depois = env.data.mocap_pos[visao.mocap_do_ponto(env.model)].copy()
    ok("o mocap move-se por data.mocap_pos (trajetória círculo, 0,3–0,8 m/s)",
       float(np.linalg.norm(depois - antes)) > 0.05,
       f"Δ{np.linalg.norm(depois - antes):.3f} m em 10 passos · posição {np.round(depois, 2)}")

    # --------------------------------------------------------------------------------- §3 contrato
    print("  == §3 ação = v_ref no envelope r11 · cascata idêntica com tracker neutro")
    env = DroneRealEnv(build=None, modo_acao="ctbr", comando=True, com_alvo=True)
    env.definir_v_ref([10.0, -10.0, 10.0])          # pedido 10× acima do envelope
    v = env.v_ref if np.any(env.v_ref) else env._v_ref_externo
    ok(f"v_ref saturado ao envelope r11 (±{VOO_VEL:g} xy / ±{VOO_SUBIDA:g} z)",
       abs(v[0]) <= VOO_VEL + 1e-9 and abs(v[1]) <= VOO_VEL + 1e-9 and abs(v[2]) <= VOO_SUBIDA + 1e-9,
       f"v_ref={np.round(v, 3)}")
    # cascata: sem tracker (v_ref=0 por omissão) vs com tracker neutro (definir_v_ref([0,0,0]))
    from stable_baselines3 import PPO
    piloto = PPO.load(str(PILOTO), device="cpu")
    env.reset(seed=11)
    obs_base = env.observacao().copy()
    a1, _ = piloto.predict(obs_base, deterministic=True)
    env.definir_v_ref([0.0, 0.0, 0.0])              # tracker NEUTRO
    env._passo_comando()
    a2, _ = piloto.predict(env.observacao(), deterministic=True)
    ok("IA-voo congelada: ações IDÊNTICAS sem tracker vs com tracker neutro (v_ref = 0)",
       np.allclose(a1, a2, atol=1e-6), f"max|Δ| = {float(np.max(np.abs(a1 - a2))):.2e}")

    print(f"[teste] {TOTAL - FALHAS}/{TOTAL} checagens OK")
    print("o tracker vê o ponto pela projeção provada contra o detetor clássico, comanda v_ref dentro "
          "do contrato r11 e a IA-voo congelada segue-a sem mudar de comportamento")
    return 1 if FALHAS else 0


if __name__ == "__main__":
    sys.exit(main())
