#!/usr/bin/env python3
"""Pêndulo físico — período analítico e COMPARAÇÃO DE INTEGRADORES (Euler, RK4, implicit, implicitfast).

    uv run python experiments/NN_pendulo/run.py                       # tabela dos 4 integradores + vídeo/gráfico com o escolhido
    uv run python experiments/NN_pendulo/run.py --theta0 60 --dt 0.005 --integrador rk4
    uv run python experiments/NN_pendulo/run.py --sem-video           # só números
    uv run python experiments/NN_pendulo/run.py --view                # janela (launch_passive) com o pêndulo balançando

Mede o período por cruzamentos de zero de θ(t) e compara com T = T0·(2/π)·K(sin²(θ0/2)) (solução exata do pêndulo físico; K = integral elíptica completa; T0 = 2π√(I/(m·g·d)));
mede a deriva de energia (sem amortecimento a energia deveria se conservar). Saídas em out/: pendulo.mp4, pendulo.gif, pendulo.png, resumo.json.
Exit 0 = o integrador escolhido acertou o período dentro de --tol (%) ; 1 = fora.
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
from scipy.special import ellipk  # noqa: E402

AQUI = Path(__file__).resolve().parent
INTEGRADORES = {"euler": mujoco.mjtIntegrator.mjINT_EULER, "rk4": mujoco.mjtIntegrator.mjINT_RK4,
                "implicit": mujoco.mjtIntegrator.mjINT_IMPLICIT, "implicitfast": mujoco.mjtIntegrator.mjINT_IMPLICITFAST}


def analitico(model, data, theta0: float) -> dict:
    """Período e energia de oscilação previstos, a partir do MODELO COMPILADO (massa, CM e inércia efetiva no pivô)."""
    mujoco.mj_forward(model, data)
    M = np.zeros((model.nv, model.nv))
    mujoco.mj_fullM(model, data, M)  # 3.10+: assinatura (m, d, dst); mjData.qM foi removido na 3.11 (agora data.M em CSR)
    b = model.body("haste").id
    m = float(model.body_mass[b])
    d = float(np.linalg.norm(data.xipos[b] - data.xanchor[model.joint("pivo").id]))  # distância pivô → centro de massa
    g = float(np.linalg.norm(model.opt.gravity))
    T0 = 2 * np.pi * np.sqrt(M[0, 0] / (m * g * d))
    # período EXATO para qualquer amplitude: T = T0 · (2/π) · K(k²), k = sin(θ0/2), K = integral elíptica completa de 1ª espécie
    T = T0 * (2 / np.pi) * ellipk(np.sin(theta0 / 2) ** 2)
    return {"I_pivo": float(M[0, 0]), "m": m, "d": d, "T0": float(T0), "T": float(T), "E_osc": float(m * g * d * (1 - np.cos(theta0)))}


def cruzamentos_ascendentes(t: np.ndarray, x: np.ndarray) -> np.ndarray:
    i = np.where((x[:-1] < 0) & (x[1:] >= 0))[0]
    return t[i] - x[i] * (t[i + 1] - t[i]) / (x[i + 1] - x[i])  # interpolação linear do instante do zero


def simular(model, data, integrador: str, theta0: float, duracao: float):
    model.opt.integrator = INTEGRADORES[integrador]
    mujoco.mj_resetData(model, data)
    data.qpos[0] = theta0
    mujoco.mj_forward(model, data)
    return mjkit.record(model, data, None, duration=duracao, probes={"theta": lambda m, d: d.qpos[0]})


def metricas(res: dict, ana: dict) -> dict:
    t, th = res["log"]["t"], res["log"]["theta"]
    zc = cruzamentos_ascendentes(t, th)
    per = float(np.mean(np.diff(zc))) if len(zc) > 2 else float("nan")
    e = res["log"]["pe"] + res["log"]["ke"]
    return {"periodo_s": per, "erro_periodo_pct": 100 * (per - ana["T"]) / ana["T"], "deriva_energia_pct": 100 * float(e[-1] - e[0]) / ana["E_osc"],
            "n_periodos": int(len(zc) - 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", default=str(AQUI / "model.xml"))
    ap.add_argument("--theta0", type=float, default=5.0, help="ângulo inicial em graus (padrão 5: oscilação pequena)")
    ap.add_argument("--dt", type=float, default=None, help="passo de tempo (s); padrão: o do XML (0.002)")
    ap.add_argument("--periodos", type=int, default=10, help="nº de períodos simulados para a tabela")
    ap.add_argument("--integrador", choices=list(INTEGRADORES), default="rk4", help="integrador do vídeo/gráfico e do exit code")
    ap.add_argument("--tol", type=float, default=0.5, help="tolerância do erro de período (%%) para o exit code")
    ap.add_argument("--saida", default=str(AQUI / "out"))
    ap.add_argument("--sem-video", action="store_true")
    ap.add_argument("--view", action="store_true", help="abre a janela interativa em vez de gravar")
    a = ap.parse_args()

    model, data = mjkit.load(a.modelo)
    if a.dt:
        model.opt.timestep = a.dt
    th0 = np.radians(a.theta0)
    ana = analitico(model, data, th0)
    dur = (a.periodos + 0.5) * ana["T"]
    print(f"MuJoCo {mujoco.__version__} · dt = {model.opt.timestep*1000:g} ms · θ0 = {a.theta0:g}° · m = {ana['m']:.3f} kg · d = {ana['d']*100:.1f} cm · I_pivô = {ana['I_pivo']:.4f} kg·m²")
    print(f"período analítico: T0 = {ana['T0']:.5f} s (pequenas oscilações) · T = {ana['T']:.5f} s (exato para θ0 = {a.theta0:g}°)\n")

    if a.view:
        data.qpos[0] = th0
        mujoco.mj_forward(model, data)
        model.opt.integrator = INTEGRADORES[a.integrador]
        mjkit.run_viewer(model, data)
        return 0

    print(f"{'integrador':14s} {'período (s)':>12s} {'erro período':>13s} {'deriva de energia em %d períodos' % a.periodos:>34s}")
    tab = {}
    for nome in INTEGRADORES:
        r = metricas(simular(model, data, nome, th0, dur), ana)
        tab[nome] = r
        print(f"{nome:14s} {r['periodo_s']:12.5f} {r['erro_periodo_pct']:+12.4f}% {r['deriva_energia_pct']:+33.4f}%")

    out = Path(a.saida)
    model.opt.integrator = INTEGRADORES[a.integrador]
    mujoco.mj_resetData(model, data)
    data.qpos[0] = th0
    mujoco.mj_forward(model, data)
    e0 = None

    def hud(m, d):
        nonlocal e0
        e = d.energy.sum()
        e0 = e if e0 is None else e0
        return [f"t = {d.time:5.2f} s   θ = {np.degrees(d.qpos[0]):+6.2f}°", f"integrador: {a.integrador}   ΔE = {100*(e-e0)/ana['E_osc']:+.3f}%"]

    res = mjkit.record(model, data, None, duration=min(dur, 8.0), mp4=None if a.sem_video else out / "pendulo.mp4", gif=None if a.sem_video else out / "pendulo.gif",
                       camera="frontal", hud=hud, probes={"theta_deg": lambda m, d: np.degrees(d.qpos[0]), "E_total": lambda m, d: d.energy.sum()})
    mjkit.plot(res["log"], ["theta_deg", "E_total"], out / "pendulo.png", f"pêndulo · {a.integrador} · dt {model.opt.timestep*1000:g} ms · θ0 {a.theta0:g}°")
    ok = abs(tab[a.integrador]["erro_periodo_pct"]) <= a.tol
    (out / "resumo.json").write_text(json.dumps({"mujoco": mujoco.__version__, "dt": model.opt.timestep, "theta0_deg": a.theta0, "analitico": ana, "integradores": tab,
                                                 "escolhido": a.integrador, "ok": bool(ok)}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[{'OK ' if ok else 'FALHA'}] {a.integrador}: erro de período {tab[a.integrador]['erro_periodo_pct']:+.4f}% (tolerância {a.tol}%) · saídas em {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
