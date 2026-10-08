#!/usr/bin/env python3
"""Experimento 03 — o exemplo do §4.2 do relatório (haste articulada + motor), corrigido, validado e com contraprova do bug original.

    uv run python experiments/03_haste_relatorio/run.py                   # corrigido + contraprova; grava vídeo/GIF/gráficos em out/
    uv run python experiments/03_haste_relatorio/run.py --sem-video       # só números (CI)
    uv run python experiments/03_haste_relatorio/run.py --view            # janela interativa (só a pedido)

O que se verifica (exit 0 = tudo OK):
  1. nome errado de atuador dá KeyError (no original, `mj_name2id` devolveria −1 e `ctrl[-1]` escreveria no último atuador sem erro);
  2. `ctrl` → torque na junta (gear = 1): qfrc_actuator = ctrl após `mj_forward`;
  3. modelo corrigido: nenhum contato haste×caixa e a haste oscila (|θ|máx > 0,5 rad);
  4. contraprova: no modelo ORIGINAL (pos y = 0,2) a haste penetra a caixa, há contato permanente e a junta fica travada (|θ|máx < 0,05 rad).
  5. variante «pêndulo forçado» (haste pendurada + amortecimento): θ(t) do MuJoCo × EDO não linear I·θ'' + c·θ' + m·g·d·sinθ = T·sin(ωt) integrada com scipy (RMS < 0,01 rad).
"""
from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
from lab import mjkit  # noqa: E402  (define MUJOCO_GL=egl antes de importar mujoco)

import argparse  # noqa: E402
import json  # noqa: E402

import mujoco  # noqa: E402
import numpy as np  # noqa: E402

AQUI = Path(__file__).resolve().parent
TORQUE, FREQ = 15.0, 1.0  # N·m e Hz do comando senoidal do relatório


def comando(model: mujoco.MjModel, data: mujoco.MjData, slot: int) -> None:
    data.ctrl[slot] = TORQUE * np.sin(2 * np.pi * FREQ * data.time)


def contatos_haste_caixa(model: mujoco.MjModel, data: mujoco.MjData) -> int:
    g_haste, g_caixa = model.geom("haste").id, model.geom("caixa").id
    return sum(1 for i in range(data.ncon) if {int(data.contact[i].geom1), int(data.contact[i].geom2)} == {g_haste, g_caixa})


def simular(xml: Path, duracao: float) -> dict:
    model, data = mjkit.load(xml)
    slot = int(model.actuator_ctrladr[model.actuator("atuador_principal").id])  # índice real em data.ctrl (nu ≠ nactuator com atuadores multi-entrada)
    theta, ncont, pen = [], [], []
    while data.time < duracao:
        comando(model, data, slot)
        mujoco.mj_step(model, data)
        theta.append(float(data.qpos[0]))
        ncont.append(contatos_haste_caixa(model, data))
        pen.append(min([float(data.contact[i].dist) for i in range(data.ncon)] or [0.0]))
    theta = np.array(theta)
    return {"theta_max": float(np.abs(theta).max()), "theta_final": float(theta[-1]), "passos_com_contato_haste_caixa": int(np.sum(np.array(ncont) > 0)),
            "penetracao_max_m": float(-min(pen)) if pen else 0.0, "passos": len(theta)}


def pendulo_forcado(xml: Path, duracao: float) -> dict:
    """Simula a variante pendurada e compara θ(t) com a EDO não linear (parâmetros lidos do PRÓPRIO modelo compilado)."""
    from scipy.integrate import solve_ivp

    model, data = mjkit.load(xml)
    slot = int(model.actuator_ctrladr[model.actuator("atuador_principal").id])
    mujoco.mj_forward(model, data)
    M = np.zeros((1, 1)); mujoco.mj_fullM(model, data, M)
    inercia = float(M[0, 0])                                   # I em torno do pivô (θ = 0, haste pendurada)
    massa = float(model.body_mass[model.body("haste_articulada").id])
    d = abs(float(data.xipos[model.body("haste_articulada").id][2] - data.xanchor[0][2]))   # distância pivô→CM
    c = float(model.dof_damping[0])
    mgd, w = massa * 9.81 * d, 2 * np.pi * FREQ
    t_eval = np.arange(0, duracao, model.opt.timestep)
    ref = solve_ivp(lambda t, y: [y[1], (TORQUE * np.sin(w * t) - c * y[1] - mgd * np.sin(y[0])) / inercia], (0, duracao), [0.0, 0.0], t_eval=t_eval, rtol=1e-10, atol=1e-12)
    theta = []
    for _ in range(len(t_eval)):
        theta.append(float(data.qpos[0]))        # estado ANTES do passo ↔ instante data.time (mesma convenção de t_eval)
        comando(model, data, slot)
        mujoco.mj_step(model, data)
    theta = np.array(theta)
    rms = float(np.sqrt(np.mean((theta - ref.y[0]) ** 2)))
    return {"I_kg_m2": inercia, "m_g_d_N_m": mgd, "c": c, "theta_max_sim": float(np.abs(theta).max()), "theta_max_edo": float(np.abs(ref.y[0]).max()), "rms_rad": rms,
            "omega_n_rad_s": float(np.sqrt(mgd / inercia))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duracao", type=float, default=6.0, help="segundos simulados")
    ap.add_argument("--saida", default=str(AQUI / "out"))
    ap.add_argument("--sem-video", action="store_true")
    ap.add_argument("--slowmo", type=float, default=1.0)
    ap.add_argument("--view", action="store_true", help="abre o viewer (só a pedido do usuário)")
    a = ap.parse_args()
    model_xml, original_xml = AQUI / "model.xml", AQUI / "model_original.xml"

    if a.view:
        model, data = mjkit.load(model_xml)
        slot = int(model.actuator_ctrladr[model.actuator("atuador_principal").id])
        mjkit.run_viewer(model, data, lambda m, d: comando(m, d, slot), slowmo=a.slowmo)
        return 0

    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    checks: list[tuple[str, bool, str]] = []

    # 1) nome errado: erro explícito (mj_name2id devolveria -1)
    model, data = mjkit.load(model_xml)
    try:
        model.actuator("atuador_pricipal")
        checks.append(("nome errado de atuador levanta KeyError", False, "não levantou"))
    except KeyError:
        checks.append(("nome errado de atuador levanta KeyError", mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "atuador_pricipal") == -1, "mj_name2id → -1 (ctrl[-1] escreveria no ÚLTIMO atuador)"))

    # 2) ctrl → torque (gear = 1)
    slot = int(model.actuator_ctrladr[model.actuator("atuador_principal").id])
    data.ctrl[slot] = 2.5
    mujoco.mj_forward(model, data)
    checks.append(("ctrl → torque na junta (gear = 1)", abs(float(data.qfrc_actuator[0]) - 2.5) < 1e-9, f"qfrc_actuator = {float(data.qfrc_actuator[0]):.3f} N·m para ctrl = 2.5"))

    # 3) modelo corrigido e 4) contraprova do original
    ok = simular(model_xml, a.duracao)
    bug = simular(original_xml, a.duracao)
    checks.append(("corrigido: sem contato haste×caixa", ok["passos_com_contato_haste_caixa"] == 0, f"{ok['passos_com_contato_haste_caixa']} passos com contato"))
    checks.append(("corrigido: a haste oscila", ok["theta_max"] > 0.5, f"|θ|máx = {ok['theta_max']:.3f} rad ({np.degrees(ok['theta_max']):.0f}°)"))
    checks.append(("original: contato permanente haste×caixa", bug["passos_com_contato_haste_caixa"] > 0.9 * bug["passos"], f"{bug['passos_com_contato_haste_caixa']}/{bug['passos']} passos · penetração {1000*bug['penetracao_max_m']:.0f} mm"))
    checks.append(("original: junta travada pelo contato", bug["theta_max"] < 0.05, f"|θ|máx = {bug['theta_max']:.4f} rad com o mesmo torque de {TORQUE:g} N·m"))

    pen = pendulo_forcado(AQUI / "model_pendulo.xml", max(a.duracao, 10.0))
    checks.append(("pêndulo forçado: θ(t) MuJoCo × EDO não linear", pen["rms_rad"] < 0.01, f"RMS = {1000*pen['rms_rad']:.2f} mrad · |θ|máx {pen['theta_max_sim']:.3f} × {pen['theta_max_edo']:.3f} rad "
                   f"(I = {pen['I_kg_m2']:.4f} kg·m², m·g·d = {pen['m_g_d_N_m']:.2f} N·m, ω_n = {pen['omega_n_rad_s']:.2f} rad/s)"))

    if not a.sem_video:
        mjkit.record(*mjkit.load(AQUI / "model_pendulo.xml"), lambda m, d: comando(m, d, 0), duration=max(a.duracao, 10.0), slowmo=a.slowmo, camera="lateral",
                     mp4=out / "pendulo.mp4", gif=out / "pendulo.gif", sheet=out / "pendulo_sheet.png",
                     hud=lambda m, d: [f"t = {d.time:5.2f} s   torque = {d.ctrl[0]:+6.2f} N·m", f"θ = {np.degrees(d.qpos[0]):+7.1f}°   (pêndulo forçado, c = 0,5)"])
        model, data = mjkit.load(model_xml)
        res = mjkit.record(model, data, lambda m, d: comando(m, d, slot), duration=a.duracao, slowmo=a.slowmo, camera="lateral",
                           mp4=out / "haste.mp4", gif=out / "haste.gif", sheet=out / "haste_sheet.png",
                           hud=lambda m, d: [f"t = {d.time:4.2f} s   torque = {d.ctrl[0]:+6.2f} N·m", f"θ = {np.degrees(d.qpos[0]):+7.1f}°   (|θ|máx {np.degrees(ok['theta_max']):.0f}°)"],
                           probes={"theta": lambda m, d: d.qpos[0], "torque": lambda m, d: d.ctrl[0]})
        mjkit.plot(res["log"], ["theta", "torque"], out / "telemetria.png", "haste articulada (modelo corrigido)")
    (out / "resumo.json").write_text(json.dumps({"corrigido": ok, "original": bug, "pendulo_forcado": pen, "checks": [{"nome": n, "ok": o, "detalhe": d} for n, o, d in checks]}, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"MuJoCo {mujoco.__version__} · torque {TORQUE:g} N·m · {FREQ:g} Hz · {a.duracao:g} s")
    for n, o, d in checks:
        print(f"[{'OK ' if o else 'FALHA'}] {n:46s} {d}")
    return 0 if all(o for _, o, _ in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
