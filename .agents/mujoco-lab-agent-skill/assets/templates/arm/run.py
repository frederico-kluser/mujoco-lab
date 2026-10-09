#!/usr/bin/env python3
"""Braço robótico de 3 GDL — IK diferencial (Jacobiano) seguindo um alvo em círculo, com servos <position> (PD).

    uv run python experiments/NN_braco/run.py                     # simula 8 s, valida o rastreamento e grava vídeo/GIF/gráficos
    uv run python experiments/NN_braco/run.py --raio 0.2 --periodo 3 --sem-video
    uv run python experiments/NN_braco/run.py --view              # janela interativa (R reinicia, P pausa)

Controle: a cada passo, v = v_alvo + Kp·(p_alvo − p_ponta); dq = Jᵀ(JJᵀ + λ²I)⁻¹·v·dt (mínimos quadrados amortecidos); q_cmd += dq → ctrl dos servos.
O alvo é um corpo MOCAP (data.mocap_pos). Validação: erro RMS de rastreamento da ponta (após 1 s) < --tol (m); limites das juntas respeitados; sem NaN.
Exit 0 = passou · 1 = falhou.
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
CENTRO = np.array([0.55, 0.0, 0.55])


class SeguidorIK:
    """Cartesiano → juntas: IK diferencial por mínimos quadrados amortecidos + feedforward de velocidade."""

    def __init__(self, model, site: str = "ponta", kp: float = 10.0, lam: float = 0.05):
        self.m, self.kp, self.lam = model, kp, lam
        self.site = model.site(site).id
        self.jacp = np.zeros((3, model.nv))
        self.ctrl = mjkit.Ctrl(model)
        self.nomes = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nactuator)]
        self.lo, self.hi = model.actuator_ctrlrange[:, 0].copy(), model.actuator_ctrlrange[:, 1].copy()
        self.q_cmd = None

    def reset(self, data):
        self.q_cmd = data.qpos[: self.m.nu].copy()

    def passo(self, data, p_alvo: np.ndarray, v_alvo: np.ndarray) -> float:
        if self.q_cmd is None:
            self.reset(data)
        mujoco.mj_jacSite(self.m, data, self.jacp, None, self.site)
        J = self.jacp[:, : self.m.nu]
        erro = p_alvo - data.site_xpos[self.site]
        v = v_alvo + self.kp * erro
        dq = J.T @ np.linalg.solve(J @ J.T + self.lam**2 * np.eye(3), v) * self.m.opt.timestep
        self.q_cmd = np.clip(self.q_cmd + dq, self.lo, self.hi)
        for nome, q in zip(self.nomes, self.q_cmd):
            self.ctrl.set(data, nome, q)
        return float(np.linalg.norm(erro))


def trajetoria(t: float, raio: float, periodo: float):
    """Círculo no plano YZ que começa no centro: p(t) e v(t) analíticos."""
    w = 2 * np.pi / periodo
    p = CENTRO + raio * np.array([0.0, np.sin(w * t), 1 - np.cos(w * t)])
    v = raio * w * np.array([0.0, np.cos(w * t), np.sin(w * t)])
    return p, v


def pose_inicial(model, data, p0: np.ndarray) -> None:
    """Resolve a cinemática inversa offline (iterando no espaço das juntas) para começar com a ponta já em p0."""
    jacp = np.zeros((3, model.nv))
    site = model.site("ponta").id
    data.qpos[:3] = [0.0, -1.0, 1.6]
    for _ in range(300):
        mujoco.mj_kinematics(model, data)  # posições dos corpos/sites para o qpos atual
        mujoco.mj_comPos(model, data)      # mj_jacSite também precisa de cdof/subtree_com (mj_kinematics → mj_comPos, nessa ordem); ou chame mj_forward
        mujoco.mj_jacSite(model, data, jacp, None, site)
        e = p0 - data.site_xpos[site]
        data.qpos[:3] += jacp[:, :3].T @ np.linalg.solve(jacp[:, :3] @ jacp[:, :3].T + 0.01 * np.eye(3), e) * 0.5
    data.ctrl[:3] = data.qpos[:3]
    mujoco.mj_forward(model, data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", default=str(AQUI / "model.xml"))
    ap.add_argument("--duracao", type=float, default=8.0)
    ap.add_argument("--raio", type=float, default=0.15, help="raio do círculo (m)")
    ap.add_argument("--periodo", type=float, default=4.0, help="período do círculo (s)")
    ap.add_argument("--tol", type=float, default=0.01, help="tolerância do erro RMS de rastreamento (m)")
    ap.add_argument("--slowmo", type=float, default=1.0)
    ap.add_argument("--saida", default=str(AQUI / "out"))
    ap.add_argument("--sem-video", action="store_true")
    ap.add_argument("--view", action="store_true")
    a = ap.parse_args()

    model, data = mjkit.load(a.modelo)
    seg = SeguidorIK(model)
    p0, _ = trajetoria(0.0, a.raio, a.periodo)
    pose_inicial(model, data, p0)
    seg.reset(data)
    erros: list[float] = []

    def controlador(m, d):
        p, v = trajetoria(d.time, a.raio, a.periodo)
        d.mocap_pos[0] = p
        erros.append(seg.passo(d, p, v))

    if a.view:
        mjkit.run_viewer(model, data, controlador, slowmo=a.slowmo)
        return 0

    out = Path(a.saida)
    res = mjkit.record(model, data, controlador, duration=a.duracao, slowmo=a.slowmo, camera="frontal",
                       mp4=None if a.sem_video else out / "braco.mp4", gif=None if a.sem_video else out / "braco.gif",
                       sheet=None if a.sem_video else out / "braco_sheet.png",
                       hud=lambda m, d: [f"t = {d.time:5.2f} s   erro da ponta = {erros[-1]*1000:5.1f} mm", "alvo (verde) · IK por Jacobiano + servos PD"],
                       probes={"erro_mm": lambda m, d: erros[-1] * 1000, "q_ombro": lambda m, d: d.qpos[1], "q_cotovelo": lambda m, d: d.qpos[2],
                               "forca_max": lambda m, d: np.abs(d.actuator_force).max()})
    log = res["log"]
    sel = log["t"] > 1.0
    rms = float(np.sqrt(np.mean((log["erro_mm"][sel] / 1000) ** 2)))
    q_ok = bool(np.all(data.qpos[: model.nu] >= model.jnt_range[: model.nu, 0] - 1e-3) and np.all(data.qpos[: model.nu] <= model.jnt_range[: model.nu, 1] + 1e-3))
    fmax = float(log["forca_max"].max())
    checks = [("erro RMS da ponta após 1 s", rms < a.tol, f"{rms*1000:.2f} mm (tolerância {a.tol*1000:.0f} mm)"),
              ("juntas dentro dos limites", q_ok, f"q = {np.round(data.qpos[:3], 3)}"),
              ("torque dentro do forcerange", fmax <= float(model.actuator_forcerange[0, 1]) + 1e-6, f"|τ| máx = {fmax:.1f} N·m (limite {float(model.actuator_forcerange[0,1]):g})"),
              ("sem NaN", bool(np.isfinite(log["erro_mm"]).all()), "")]
    mjkit.plot(log, ["erro_mm", "q_ombro", "q_cotovelo", "forca_max"], out / "telemetria.png", f"braço 3 GDL · círculo r={a.raio} m, T={a.periodo} s")
    print(f"MuJoCo {mujoco.__version__} · dt {model.opt.timestep*1000:g} ms · {mujoco.mjtIntegrator(model.opt.integrator).name} · {a.duracao:g} s")
    for n, ok, d in checks:
        print(f"[{'OK ' if ok else 'FALHA'}] {n:34s} {d}")
    (out / "resumo.json").write_text(json.dumps({"rms_m": rms, "forca_max": fmax, "ok": all(c[1] for c in checks)}, indent=2), encoding="utf-8")
    return 0 if all(ok for _, ok, _ in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
