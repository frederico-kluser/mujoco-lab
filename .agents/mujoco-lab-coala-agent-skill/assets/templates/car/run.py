#!/usr/bin/env python3
"""Carro de 4 rodas — aceleração, curvas com direção Ackermann e frenagem, validados contra o MODELO CINEMÁTICO DE BICICLETA.

    uv run python experiments/NN_carro/run.py                     # simula, valida e grava vídeo/GIF/gráficos
    uv run python experiments/NN_carro/run.py --vel 1.0 --delta 25 --sem-video
    uv run python experiments/NN_carro/run.py --atrito 0.5        # piso escorregadio (veja o subesterço/derrapagem nos números)
    uv run python experiments/NN_carro/run.py --view              # janela interativa (R reinicia, P pausa)

Controle: PI de velocidade do veículo → torque igual nas duas rodas traseiras; esterçamento Ackermann (δ de bicicleta → ângulos esquerdo/direito) com limite de taxa.
Previsão cinemática: raio R = L/tan δ e taxa de guinada ψ̇ = v·tan δ / L (vale a baixa velocidade, sem derrapagem). Exit 0 = todas as checagens passaram · 1 = alguma falhou.
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
L, T = 0.30, 0.22  # entre-eixos e bitola (m) — iguais ao model.xml


def ackermann(delta: float) -> tuple[float, float]:
    """δ de bicicleta (rad, + = esquerda) → (esquerda, direita). A roda interna esterça mais."""
    t = np.tan(abs(delta))
    interna = np.arctan2(L * t, L - 0.5 * T * t)
    externa = np.arctan2(L * t, L + 0.5 * T * t)
    return (interna, externa) if delta >= 0 else (-externa, -interna)


class Carro:
    def __init__(self, model, kp=2.0, ki=3.0, taxa_dir_deg=90.0):
        self.m, self.kp, self.ki, self.taxa = model, kp, ki, np.radians(taxa_dir_deg)
        self.bid = model.body("carro").id
        self.ctrl = mjkit.Ctrl(model)
        self.reset()

    def reset(self):
        self.i, self.delta, self.t_ant = 0.0, 0.0, -1.0

    def __call__(self, data, v_ref: float, delta_ref: float) -> None:
        if data.time < self.t_ant:
            self.reset()
        self.t_ant = data.time
        dt = self.m.opt.timestep
        vx = float((data.xmat[self.bid].reshape(3, 3).T @ data.qvel[:3])[0])
        e = v_ref - vx
        tau = self.kp * e + self.ki * self.i
        if abs(tau) < 1.5:  # anti-windup: só integra fora da saturação
            self.i += e * dt
        tau = float(np.clip(tau, -1.5, 1.5))
        self.ctrl.set(data, "tr_e", tau)
        self.ctrl.set(data, "tr_d", tau)
        self.delta += float(np.clip(delta_ref - self.delta, -self.taxa * dt, self.taxa * dt))
        de, dd = ackermann(self.delta)
        self.ctrl.set(data, "est_e", de)
        self.ctrl.set(data, "est_d", dd)


def plano(t: float, v: float, delta_deg: float) -> tuple[float, float]:
    """(v_ref, δ_ref em rad) no instante t: acelera, reta, curva à esquerda, reta, curva à direita, reta, freia."""
    d = np.radians(delta_deg)
    vref = min(v, v * t / 2.0)  # rampa de aceleração em 2 s
    if t > 12.0:
        vref = max(0.0, v * (14.0 - t) / 2.0)  # frenagem
    delta = 0.0
    if 3.0 <= t < 6.5:
        delta = d
    elif 7.5 <= t < 11.0:
        delta = -d
    return vref, delta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", default=str(AQUI / "model.xml"))
    ap.add_argument("--vel", type=float, default=1.5, help="velocidade de cruzeiro (m/s)")
    ap.add_argument("--delta", type=float, default=20.0, help="ângulo de direção de bicicleta nas curvas (graus)")
    ap.add_argument("--atrito", type=float, default=None, help="coeficiente de atrito de deslizamento do pneu/piso (padrão do XML: 1.0)")
    ap.add_argument("--camera", default="seguir", choices=["fixa", "seguir"], help="seguir = câmera que acompanha o carro (padrão); fixa = vista geral da pista")
    ap.add_argument("--slowmo", type=float, default=1.0)
    ap.add_argument("--saida", default=str(AQUI / "out"))
    ap.add_argument("--sem-video", action="store_true")
    ap.add_argument("--view", action="store_true")
    a = ap.parse_args()

    model, data = mjkit.load(a.modelo)
    if a.atrito is not None:
        for g in range(model.ngeom):
            if model.geom_contype[g] == 1:
                model.geom_friction[g, 0] = a.atrito
    mujoco.mj_forward(model, data)
    carro = Carro(model)
    bid = carro.bid

    def controlador(m, d):
        v, dl = plano(d.time, a.vel, a.delta)
        carro(d, v, dl)

    if a.view:
        mjkit.run_viewer(model, data, controlador, slowmo=a.slowmo)
        return 0

    out = Path(a.saida)
    dur = 14.5

    def corpo(d):
        return d.xmat[bid].reshape(3, 3).T @ d.qvel[:3]

    res = mjkit.record(model, data, controlador, duration=dur, slowmo=a.slowmo, camera=a.camera,
                       mp4=None if a.sem_video else out / "carro.mp4", gif=None if a.sem_video else out / "carro.gif",
                       sheet=None if a.sem_video else out / "carro_sheet.png",
                       hud=lambda m, d: [f"t = {d.time:5.2f} s   v = {corpo(d)[0]:4.2f} m/s   ψ̇ = {d.qvel[5]:+5.2f} rad/s", f"direção δ = {np.degrees(carro.delta):+5.1f}°   (Ackermann)"],
                       probes={"x": lambda m, d: d.xipos[bid, 0], "y": lambda m, d: d.xipos[bid, 1], "vx": lambda m, d: corpo(d)[0], "vy": lambda m, d: corpo(d)[1],
                               "psi_dot": lambda m, d: d.qvel[5], "delta": lambda m, d: carro.delta,
                               "psi_dot_prev": lambda m, d: corpo(d)[0] * np.tan(carro.delta) / L,
                               "inclinacao_deg": lambda m, d: np.degrees(np.arccos(np.clip(d.xmat[bid][8], -1, 1)))})
    lg = res["log"]
    t = lg["t"]

    def janela(t0, t1):
        return (t >= t0) & (t < t1)

    w = janela(1.8, 3.0)
    v_med = float(lg["vx"][w].mean())
    wc = janela(4.5, 6.4)  # curva à esquerda em regime
    psi_sim, psi_prev = float(lg["psi_dot"][wc].mean()), float(lg["psi_dot_prev"][wc].mean())
    wd = janela(8.8, 10.9)
    psi_sim_d, psi_prev_d = float(lg["psi_dot"][wd].mean()), float(lg["psi_dot_prev"][wd].mean())
    beta = np.degrees(np.arctan2(lg["vy"], np.maximum(np.abs(lg["vx"]), 0.2)))
    beta_sim = float(beta[wc].mean())  # deriva do centro de gravidade em regime (curva à esquerda)
    beta_cin = float(np.degrees(np.arctan(0.5 * np.tan(np.radians(a.delta)))))  # CG no meio do entre-eixos: β = atan(l_r·tanδ/L), l_r = L/2
    checks = [("velocidade de cruzeiro (1,8–3 s)", abs(v_med - a.vel) / a.vel < 0.05, f"{v_med:.3f} m/s (alvo {a.vel:g})"),
              ("taxa de guinada, curva à esquerda", abs(psi_sim - psi_prev) / abs(psi_prev) < 0.12, f"sim {psi_sim:+.3f} · bicicleta {psi_prev:+.3f} rad/s (Δ {100*abs(psi_sim-psi_prev)/abs(psi_prev):.1f}%)"),
              ("taxa de guinada, curva à direita", abs(psi_sim_d - psi_prev_d) / abs(psi_prev_d) < 0.12, f"sim {psi_sim_d:+.3f} · bicicleta {psi_prev_d:+.3f} rad/s"),
              ("deriva do CG em curva (β) vs cinemática", abs(beta_sim - beta_cin) < 2.5, f"sim {beta_sim:+.1f}° · cinemática atan(½·tanδ) = {beta_cin:+.1f}°"),
              ("inclinação (capotamento)", float(lg["inclinacao_deg"].max()) < 15, f"máx = {float(lg['inclinacao_deg'].max()):.1f}°"),
              ("parou ao final", float(np.hypot(lg["vx"][-1], lg["vy"][-1])) < 0.05, f"|v| final = {float(np.hypot(lg['vx'][-1], lg['vy'][-1])):.3f} m/s"),
              ("sem NaN", bool(np.isfinite(lg["x"]).all()), "")]
    mjkit.plot(lg, ["vx", "psi_dot", "psi_dot_prev", "delta"], out / "telemetria.png", f"carro · atrito {a.atrito if a.atrito is not None else 1.0:g} · δ = {a.delta:g}°")
    try:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 6), dpi=100, facecolor="#0e1420")
        ax.set_facecolor("#0e1420"); ax.plot(lg["x"], lg["y"], color="#ffa24a", lw=2); ax.set_aspect("equal"); ax.grid(True, alpha=.3)
        ax.set_title("trajetória (x, y) em m", color="#e6ebf5"); ax.tick_params(colors="#aab4c8")
        fig.savefig(out / "trajetoria.png"); plt.close(fig)
    except Exception:  # noqa: BLE001
        pass
    print(f"MuJoCo {mujoco.__version__} · dt {model.opt.timestep*1000:g} ms · {mujoco.mjtIntegrator(model.opt.integrator).name} · m = {float(mujoco.mj_getTotalmass(model)):.2f} kg · "
          f"R = L/tanδ = {L/np.tan(np.radians(a.delta)):.2f} m")
    for n, ok, d in checks:
        print(f"[{'OK ' if ok else 'FALHA'}] {n:36s} {d}")
    (out / "resumo.json").write_text(json.dumps({"v_med": v_med, "psi_sim": psi_sim, "psi_prev": psi_prev, "ok": all(c[1] for c in checks)}, indent=2), encoding="utf-8")
    return 0 if all(ok for _, ok, _ in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
