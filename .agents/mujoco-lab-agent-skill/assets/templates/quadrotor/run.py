#!/usr/bin/env python3
"""Quadricóptero — decolagem, quadrado de waypoints e pouso suave, com controlador GEOMÉTRICO em SO(3) (Lee et al.) e alocação de empuxo calculada do modelo.

    uv run python experiments/NN_drone/run.py                     # simula, valida o voo e grava vídeo/GIF/gráficos
    uv run python experiments/NN_drone/run.py --ar --vento 3      # liga o modelo de fluido (ar) e vento de 3 m/s em +X
    uv run python experiments/NN_drone/run.py --camera seguir --sem-video
    uv run python experiments/NN_drone/run.py --view              # janela interativa (R reinicia, P pausa)

Cadeia: trajetória min-jerk → aceleração desejada a = −Kp·e_p − Kv·e_v − Ki·∫e_p + g·ẑ + a_ff → força F = m·a → empuxo T = F·b3 e atitude desejada R_d (b3_d = F/|F|, guinada = yaw)
→ torque τ = J(−ωn²·e_R − 2ζωn·e_ω) + ω×Jω → [T, τx, τy, τz] = A·u → u = A⁻¹·[T, τ] (empuxo por rotor, saturado em ctrlrange).
A matriz A é montada a partir do modelo (posição dos sites e 'gear' de cada motor): não há sinais escritos à mão.
Exit 0 = todas as checagens passaram · 1 = alguma falhou.
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


def vee(M: np.ndarray) -> np.ndarray:
    return np.array([M[2, 1], M[0, 2], M[1, 0]])


def montar_trajetoria(inicio: np.ndarray, waypoints: list[np.ndarray], v_med: float, parada: float):
    """Segmentos (t0, t1, p0, p1) com perfil min-jerk (velocidade e aceleração nulas nas pontas) e paradas nos waypoints."""
    segs, t, p = [], 0.0, inicio
    for wp in waypoints:
        dur = max(np.linalg.norm(wp - p) / v_med, 0.6)
        segs.append((t, t + dur, p, wp)); t += dur
        segs.append((t, t + parada, wp, wp)); t += parada
        p = wp
    return segs, t


def referencia(segs, t: float):
    for t0, t1, p0, p1 in segs:
        if t < t1:
            s = (t - t0) / (t1 - t0)
            d = p1 - p0
            return (p0 + d * (10 * s**3 - 15 * s**4 + 6 * s**5), d * (30 * s**2 - 60 * s**3 + 30 * s**4) / (t1 - t0),
                    d * (60 * s - 180 * s**2 + 120 * s**3) / (t1 - t0) ** 2)
    return segs[-1][3], np.zeros(3), np.zeros(3)


class Quadricoptero:
    """Controlador geométrico + alocação. Estados internos (integral) são reiniciados quando o tempo volta atrás (R no viewer)."""

    def __init__(self, model, corpo="drone", wn_pos=3.0, zeta_pos=0.9, ki=1.2, wn_att=22.0, zeta_att=0.8, tilt_max_deg=35.0):
        self.model, self.bid = model, model.body(corpo).id
        self.mass = float(model.body_mass[self.bid])
        Ri = np.zeros(9); mujoco.mju_quat2Mat(Ri, model.body_iquat[self.bid]); Ri = Ri.reshape(3, 3)
        self.J = Ri @ np.diag(model.body_inertia[self.bid]) @ Ri.T  # inércia no referencial do corpo
        self.g = float(abs(model.opt.gravity[2]))
        # alocação: [T, τx, τy, τz] = A·u  (força ao longo de +z do site em p_i; torque reativo = 3º componente de torque do gear)
        A = np.zeros((4, model.nu))
        for i in range(model.nu):
            p = model.site_pos[model.actuator_trnid[i, 0]] - model.body_ipos[self.bid]
            tz = float(model.actuator_gear[i, 5])
            A[:, i] = [1.0, p[1], -p[0], tz]
        self.Ainv = np.linalg.inv(A)
        self.umax = float(model.actuator_ctrlrange[0, 1])
        self.kp, self.kv, self.ki = wn_pos**2, 2 * zeta_pos * wn_pos, ki
        self.wn, self.zeta, self.tilt = wn_att, zeta_att, np.radians(tilt_max_deg)
        self.reset()

    def reset(self):
        self.int_e = np.zeros(3)
        self.t_ant = -1.0
        self.sat = 0
        self.n = 0

    def __call__(self, data, p_ref, v_ref, a_ref, yaw=0.0) -> np.ndarray:
        if data.time < self.t_ant:
            self.reset()
        dt = self.model.opt.timestep
        self.t_ant = data.time
        p, v = data.xipos[self.bid].copy(), data.qvel[:3].copy()
        R, w = data.xmat[self.bid].reshape(3, 3).copy(), data.qvel[3:6].copy()
        ep, ev = p - p_ref, v - v_ref
        self.int_e = np.clip(self.int_e + ep * dt, -1.5, 1.5)
        a = -self.kp * ep - self.kv * ev - self.ki * self.int_e + a_ref + np.array([0, 0, self.g])
        F = self.mass * a
        # limita a inclinação pedida (evita capotar quando o erro é grande)
        Fh = np.linalg.norm(F[:2]); Fz = max(F[2], 0.3 * self.mass * self.g)
        if Fh > np.tan(self.tilt) * Fz:
            F[:2] *= np.tan(self.tilt) * Fz / Fh
        F[2] = Fz
        b3d = F / np.linalg.norm(F)
        b1c = np.array([np.cos(yaw), np.sin(yaw), 0.0])
        b2d = np.cross(b3d, b1c); b2d /= np.linalg.norm(b2d)
        Rd = np.column_stack([np.cross(b2d, b3d), b2d, b3d])
        eR = 0.5 * vee(Rd.T @ R - R.T @ Rd)
        T = float(F @ R[:, 2])
        tau = self.J @ (-self.wn**2 * eR - 2 * self.zeta * self.wn * w) + np.cross(w, self.J @ w)
        u = self.Ainv @ np.array([T, *tau])
        uc = np.clip(u, 0.0, self.umax)
        self.sat += int(np.any(uc != u)); self.n += 1
        return uc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", default=str(AQUI / "model.xml"))
    ap.add_argument("--altura", type=float, default=1.0, help="altura de cruzeiro (m)")
    ap.add_argument("--lado", type=float, default=1.0, help="lado do quadrado (m)")
    ap.add_argument("--vel", type=float, default=0.7, help="velocidade média entre waypoints (m/s)")
    ap.add_argument("--ar", action="store_true", help="liga o modelo de fluido: density=1.225 kg/m³, viscosity=1.81e-5 Pa·s")
    ap.add_argument("--vento", type=float, default=0.0, help="vento constante em +X (m/s); implica --ar")
    ap.add_argument("--camera", default="fixa", choices=["fixa", "seguir"])
    ap.add_argument("--slowmo", type=float, default=1.0)
    ap.add_argument("--saida", default=str(AQUI / "out"))
    ap.add_argument("--sem-video", action="store_true")
    ap.add_argument("--view", action="store_true")
    a = ap.parse_args()

    model, data = mjkit.load(a.modelo)
    if a.ar or a.vento:
        model.opt.density, model.opt.viscosity = 1.225, 1.81e-5
        model.opt.wind[:] = [a.vento, 0.0, 0.0]
    mujoco.mj_forward(model, data)
    quad = Quadricoptero(model)
    H, L = a.altura, a.lado
    wps = [np.array(x, float) for x in ([0, 0, H], [L, 0, H], [L, L, H], [0, L, H], [0, 0, H], [0, 0, 0.0])]
    segs, t_fim = montar_trajetoria(data.xipos[quad.bid].copy(), wps, a.vel, 1.2)
    ctrl = mjkit.Ctrl(model)
    nomes = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nactuator)]

    def controlador(m, d):
        p_ref, v_ref, a_ref = referencia(segs, d.time)
        u = quad(d, p_ref, v_ref, a_ref)
        for n, ui in zip(nomes, u):
            ctrl.set(d, n, ui)

    if a.view:
        mjkit.run_viewer(model, data, controlador, slowmo=a.slowmo)
        return 0

    out = Path(a.saida)
    dur = t_fim + 0.8
    res = mjkit.record(model, data, controlador, duration=dur, slowmo=a.slowmo, camera=a.camera,
                       mp4=None if a.sem_video else out / "drone.mp4", gif=None if a.sem_video else out / "drone.gif",
                       sheet=None if a.sem_video else out / "drone_sheet.png",
                       hud=lambda m, d: [f"t = {d.time:5.2f} s   z = {d.xipos[quad.bid, 2]:.2f} m   v = {np.linalg.norm(d.qvel[:3]):.2f} m/s",
                                         f"empuxo total = {float(np.sum(d.ctrl)):.1f} N   vento = {a.vento:g} m/s"],
                       probes={"x": lambda m, d: d.xipos[quad.bid, 0], "y": lambda m, d: d.xipos[quad.bid, 1], "z": lambda m, d: d.xipos[quad.bid, 2],
                               "inclinacao_deg": lambda m, d: np.degrees(np.arccos(np.clip(d.xmat[quad.bid][8], -1, 1))),
                               "empuxo": lambda m, d: float(np.sum(d.ctrl)),
                               "ref_x": lambda m, d: referencia(segs, d.time)[0][0], "ref_y": lambda m, d: referencia(segs, d.time)[0][1],
                               "ref_z": lambda m, d: referencia(segs, d.time)[0][2]})
    log = res["log"]
    t = log["t"]
    P = np.column_stack([log["x"], log["y"], log["z"]])
    Pref = np.column_stack([log["ref_x"], log["ref_y"], log["ref_z"]])
    err = np.linalg.norm(P - Pref, axis=1)
    # checagens ---------------------------------------------------------------------------------
    t_dec = t[np.argmax(log["z"] > 0.95 * H)] if np.any(log["z"] > 0.95 * H) else float("nan")
    # erro ao FIM de cada parada (waypoint alcançado)
    fins = []
    for t0, t1, p0, p1 in segs:
        if np.allclose(p0, p1):
            i = int(np.searchsorted(t, t1 - 0.05))
            fins.append(float(np.linalg.norm(P[min(i, len(t) - 1)] - p1)))
    rms = float(np.sqrt(np.mean(err[t > 1.5] ** 2)))
    checks = [("decolou (z > 95% da altura)", bool(np.isfinite(t_dec) and t_dec < 3.0), f"t = {t_dec:.2f} s"),
              ("erro nos waypoints (fim de cada parada)", max(fins[:-1]) < 0.05, f"máx = {max(fins[:-1])*100:.1f} cm (limite 5 cm) · pouso: {fins[-1]*100:.1f} cm do ponto"),
              ("erro RMS de rastreamento (após 1,5 s)", rms < (0.12 if a.vento else 0.08), f"{rms*100:.1f} cm"),
              ("inclinação máxima", float(log["inclinacao_deg"].max()) < 40, f"{float(log['inclinacao_deg'].max()):.1f}° (limite 40°)"),
              ("saturação de empuxo", quad.sat / max(quad.n, 1) < 0.05, f"{100*quad.sat/max(quad.n,1):.1f}% dos passos"),
              ("terminou pousado", float(P[-1, 2]) < 0.09 and float(np.linalg.norm(data.qvel[:3])) < 0.15, f"z = {P[-1,2]:.3f} m · |v| = {np.linalg.norm(data.qvel[:3]):.2f} m/s"),
              ("sem NaN", bool(np.isfinite(P).all()), "")]
    mjkit.plot({"t": t, "pos (m)": P, "ref (m)": Pref, "erro (m)": err, "inclinacao_deg": log["inclinacao_deg"], "empuxo": log["empuxo"]},
               ["pos (m)", "erro (m)", "inclinacao_deg", "empuxo"], out / "telemetria.png", f"quadricóptero · vento {a.vento:g} m/s · m = {quad.mass:.3f} kg")
    print(f"MuJoCo {mujoco.__version__} · dt {model.opt.timestep*1000:g} ms · {mujoco.mjtIntegrator(model.opt.integrator).name} · m = {quad.mass:.3f} kg · empuxo de pairar/rotor = {quad.mass*quad.g/4:.2f} N · duração {dur:.1f} s")
    for n, ok, d in checks:
        print(f"[{'OK ' if ok else 'FALHA'}] {n:42s} {d}")
    (out / "resumo.json").write_text(json.dumps({"rms_m": rms, "ok": all(c[1] for c in checks), "vento": a.vento}, indent=2), encoding="utf-8")
    return 0 if all(ok for _, ok, _ in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
