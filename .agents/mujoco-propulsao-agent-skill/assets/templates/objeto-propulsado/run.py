#!/usr/bin/env python3
"""run.py — validação do objeto propulsado por fórmulas FECHADAS (modelo fresco, condições isoladas).

Cada checagem compara TEORIA (fórmulas a partir dos parâmetros do modelo) com MEDIDO (a simulação).
Exit 0 = física são · exit 1 = reprovação. Serve de molde aos testes do teu objeto novo.

Layout dos DOFs do freejoint (3.15): `qvel[:3]` = linear no MUNDO, `qvel[3:]` = angular no CORPO.
Momentos: `mj_subtreeVel` (chamado aqui) preenche `subtree_linvel/subtree_angmom` — o `flg_subtreevel`
só regista que foi chamado, não calcula nada por si.

Checagens:
  sanidade        massas do XML = o que a teoria assume (2.4 kg no total)
  hover           empuxo_z = m·g ⇒ qacc_z = 0
  eixos           F num bocal durante T ⇒ Δp = F·T NA direção desse eixo (valida a orientação dos sites)
  motor           base apoiada: ω_hinge = τ·T/I_volante · voo livre: q̇ = τ·T/I_red e ΣL_z ≈ 0 (contra-roda)
  impulso_eixo    Δp = J (momento entregue pela carga = impulso)
  impulso_fora    ΔL_z = −y·J (torque do impulso aplicado fora do centro)
  separacao       ação-reação: +J na tampa, −J no objeto ⇒ momento total conservado e afastam-se
"""
from __future__ import annotations

import sys

import numpy as np

import mujoco

from objeto_propulsao import (Carga, carregar, definir_empuxo, definir_motor, dof_de,
                              massa_total, qpos_de)

TOL = 0.02          # tolerância relativa padrão (2 %)
FALHAS: list[str] = []


def conferir(nome: str, teoria: float, medido: float, tol: float = TOL, unidade: str = "") -> None:
    """Compara teoria × medido; regista a falha (não rebenta) para o resumo final."""
    escala = max(abs(teoria), 1e-12)
    ok = abs(medido - teoria) <= tol * escala if escala > 1e-9 else abs(medido - teoria) <= tol
    marca = "OK " if ok else "FALHA"
    print(f"  [{marca}] {nome:42s} teoria={teoria:+.6g}  medido={medido:+.6g}  "
          f"|Δ|={abs(medido - teoria):.3g} {unidade}")
    if not ok:
        FALHAS.append(nome)


def novo():
    """Modelo FRESCO por checagem (condições isoladas, sem histórico) e com kinemática coerente."""
    model, data, ctrl = carregar()
    carga = Carga(model)
    mujoco.mj_forward(model, data)                          # derivados (xpos/xipos) válidos a partir daqui
    return model, data, ctrl, carga


def passos(model, data, carga, n: int) -> None:
    for _ in range(n):
        carga.passo(data)
        mujoco.mj_step(model, data)


def raizes(model) -> list[int]:
    """Corpos-livres (filhos diretos do mundo): as raízes de cada sub-árvore."""
    return [b for b in range(1, model.nbody) if int(model.body_parentid[b]) == 0]


def momentos(model, data):
    """`(p, L)` do sistema, L sobre o CoM do sistema — requer `mj_forward` antes (usa `mj_subtreeVel`).

    p = Σ Mᵢ·vᵢ · L = Σ (Lᵢ sobre o CoM da sub-árvore) + Σ (rᵢ − R)×Mᵢ·vᵢ
    """
    mujoco.mj_subtreeVel(model, data)
    rs = raizes(model)
    ms = np.array([model.body_subtreemass[b] for b in rs])
    vs = np.array([data.subtree_linvel[b] for b in rs])
    cs = np.array([data.subtree_com[b] for b in rs])
    p = (ms[:, None] * vs).sum(axis=0)
    R = (ms[:, None] * cs).sum(axis=0) / ms.sum()
    L = np.zeros(3)
    for i, b in enumerate(rs):
        L += data.subtree_angmom[b] + np.cross(cs[i] - R, ms[i] * vs[i])
    return p, L


def main() -> int:
    # ------------------------------------------------------------------ sanidade
    print("== sanidade ==")
    model, data, ctrl, carga = novo()
    g = float(-model.opt.gravity[2])
    conferir("massa total do sistema (kg)", 2.4, massa_total(model), 0.001)
    conferir("gravidade do modelo (m/s²)", 9.81, g, 0.001)

    # ------------------------------------------------------------------ hover: empuxo_z = m·g ⇒ qacc_z = 0
    # Com o parafuso SOLTO o equilíbrio é exato; com o weld MOLE o MuJoCo começa em queda livre (a
    # mola do weld só monta força com deslocamento) — ver `references/explosivos-impulsao.md`.
    print("== hover ==")
    model, data, ctrl, carga = novo()
    dof = dof_de(model, "objeto_livre")                     # qvel[:3] linear MUNDO · [3:] angular CORPO
    dof_t = dof_de(model, "tampa_livre")
    bi_o = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "objeto")
    carga.separar(data)                                     # corpo rígido puro (objeto + volante)
    definir_empuxo(data, ctrl, "z", float(model.body_subtreemass[bi_o]) * g)
    mujoco.mj_forward(model, data)
    conferir("qacc_z com empuxo = peso (m/s²)", 0.0, float(data.qacc[dof + 2]), 1e-6)
    conferir("tampa livre em queda: qacc_z = −g (m/s²)", -g, float(data.qacc[dof_t + 2]), 1e-6)

    # ------------------------------------------------------------------ eixos: Δp = F·T na direção certa
    print("== eixos (orientação dos bocais) ==")
    F, T, n = 10.0, 0.05, 25
    for eixo, indice in (("x", 0), ("y", 1)):
        model, data, ctrl, carga = novo()
        definir_empuxo(data, ctrl, eixo, F)                 # sem hover: a gravidade só mexe em z
        passos(model, data, carga, n)
        mujoco.mj_forward(model, data)
        p, _ = momentos(model, data)
        conferir(f"Δp_{eixo} = F·T (kg·m/s)", F * T, float(p[indice]), TOL)
        conferir("Δp no outro eixo horizontal (kg·m/s)", 0.0, float(p[1 - indice]), TOL)
        conferir("Δp_z = −m·g·T (kg·m/s)", -massa_total(model) * g * T, float(p[2]), TOL)

    # ------------------------------------------------------------------ motor (volante de reação)
    print("== motor (volante de reação) ==")
    model, data, ctrl, carga = novo()
    dof = dof_de(model, "objeto_livre")
    bi_o = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "objeto")
    i_o = float(model.body_inertia[bi_o][2])                # Izz do objeto (sem o volante)
    i_w = float(model.body_inertia[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "volante")][2])
    i_red = 1.0 / (1.0 / i_w + 1.0 / i_o)                   # inércia REDUZIDA do hinge (dois corpos livres)

    # (a) base apoiada: o solo segura a reação ⇒ ω_hinge = τ·T/I_w exato
    qo, qt = qpos_de(model, "objeto_livre"), qpos_de(model, "tampa_livre")
    data.qpos[qo:qo + 3] = (0.0, 0.0, 0.05)                 # objeto assente no chão
    data.qpos[qt:qt + 3] = (0.0, 0.0, 0.12)                 # tampa soldada por cima
    for _ in range(50):                                     # assentar (sem comando)
        carga.passo(data)
        mujoco.mj_step(model, data)
    data.qvel[:] = 0.0
    tau, T, n = 0.05, 0.05, 25
    definir_motor(data, ctrl, tau)
    passos(model, data, carga, n)
    mujoco.mj_forward(model, data)
    omega_w = float(data.qvel[dof_de(model, "volante_hinge")])
    conferir("omega_hinge = τ·T/I_w (rad/s)", tau * T / i_w, omega_w, TOL)

    # (b) voo livre (tampa libertada, curto o suficiente para não tocar): q̇ = τ·T/I_red e ΣL_z ≈ 0
    model, data, ctrl, carga = novo()
    dof = dof_de(model, "objeto_livre")
    bi_o = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "objeto")
    bi_t = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "tampa")
    carga.separar(data)                                     # tampa livre (cai sozinha, sem contacto em T)
    definir_motor(data, ctrl, tau)
    passos(model, data, carga, 10)                          # T = 0.02 s
    mujoco.mj_forward(model, data)
    q_ponto = float(data.qvel[dof_de(model, "volante_hinge")])
    omega_b = float(data.qvel[dof + 5])                     # angular z (frame do corpo ≈ mundo aqui)
    _, L = momentos(model, data)
    conferir("q̇_hinge = τ·T/I_red (rad/s)", tau * 0.02 / i_red, q_ponto, TOL)
    conferir("ΣL_z conservado (kg·m²/s)", 0.0, float(L[2]), max(2e-3, 0.05 * abs(i_w * q_ponto)))
    if q_ponto * omega_b < 0:
        print(f"  [OK ] objeto contra-roda                        q̇={q_ponto:+.4f}  "
              f"omega_obj={omega_b:+.4f} rad/s")
    else:
        print(f"  [FALHA] objeto contra-roda                      q̇={q_ponto:+.4f}  "
              f"omega_obj={omega_b:+.4f} rad/s")
        FALHAS.append("objeto contra-roda")

    # ------------------------------------------------------------------ impulso: Δp = J
    print("== carga explosiva (impulso) ==")
    model, data, ctrl, carga = novo()
    bi_o = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "objeto")
    J = np.array([2.0, 0.0, 0.0])
    carga.detonar(data, J, data.xipos[bi_o].copy(), "objeto")   # parafuso MANTIDO (sistema único)
    passos(model, data, carga, carga.n)
    mujoco.mj_forward(model, data)
    p, _ = momentos(model, data)
    conferir("Δp_x = J (kg·m/s)", J[0], float(p[0]), TOL)
    conferir("Δv = J/m (m/s)", J[0] / massa_total(model), float(p[0] / massa_total(model)), TOL)

    # ------------------------------------------------------------------ impulso fora do centro: ΔL_z = −y·J
    model, data, ctrl, carga = novo()
    bi_o = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "objeto")
    y0, Jx = 0.05, 1.0
    carga.detonar(data, (Jx, 0.0, 0.0), data.xipos[bi_o] + np.array([0.0, y0, 0.0]), "objeto")
    passos(model, data, carga, carga.n)
    mujoco.mj_forward(model, data)
    _, L = momentos(model, data)
    conferir("ΔL_z = −y·J (kg·m²/s)", -y0 * Jx, float(L[2]), TOL, "(sinal: torque de −y·F)")

    # ------------------------------------------------------------------ separação: ação-reação
    model, data, ctrl, carga = novo()
    bi_o = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "objeto")
    bi_t = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "tampa")
    Jsep = np.array([1.0, 0.0, 0.0])
    carga.detonar_separacao(data, Jsep)                       # +J tampa, −J objeto (ponto comum)
    passos(model, data, carga, carga.n)
    mujoco.mj_forward(model, data)
    mujoco.mj_subtreeVel(model, data)
    p_o = float(model.body_subtreemass[bi_o] * data.subtree_linvel[bi_o][0])
    p_t = float(model.body_subtreemass[bi_t] * data.subtree_linvel[bi_t][0])
    conferir("p_x(tampa) = +J (kg·m/s)", Jsep[0], p_t, TOL)
    conferir("p_x(objeto) = −J (kg·m/s)", -Jsep[0], p_o, TOL)
    conferir("p_x(total) = 0 (kg·m/s)", 0.0, p_o + p_t, 1e-3)
    afastamento = float(data.xpos[bi_t][0] - data.xpos[bi_o][0])
    if afastamento > 0:
        print(f"  [OK ] tampa a afastar-se (+x)                     Δx={afastamento:.4f} m")
    else:
        print(f"  [FALHA] tampa a afastar-se (+x)                   Δx={afastamento:.4f} m")
        FALHAS.append("tampa a afastar-se")

    # ------------------------------------------------------------------ resumo
    print()
    if FALHAS:
        print(f"REPROVADO — {len(FALHAS)} checagem(ns): {', '.join(FALHAS)}")
        return 1
    print("APROVADO — todas as fórmulas fechadas conferem (física são).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
