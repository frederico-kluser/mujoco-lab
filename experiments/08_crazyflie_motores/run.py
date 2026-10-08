#!/usr/bin/env python3
"""Crazyflie 2 (Bitcraze) — demo dos MOTORES e CONTROLES, sem código de estabilização.

Modelo pronto do mujoco_menagerie (`models/bitcraze_crazyflie_2/`) + a camada de funções
`lab/crazyflie.py` (modos, controles e leituras). NÃO há PID, atitude-lock, IK nem código do
firmware/ROS da Bitcraze — só os motores a seguir comandos abertos.

    uv run python experiments/08_crazyflie_motores/run.py                 # demo dos modos + validação + vídeo/GIF
    uv run python experiments/08_crazyflie_motores/run.py --sem-video     # só números

Roteiro de MODOS (funções de `lab.crazyflie`): hover → empuxo em cosseno → momentos em cosseno
(x, y, z) → varredura pelos 4 rotores (mixer) → hover. Tudo ABERTO: qualquer perturração deriva.

Validação (exit 0/1) contra fórmulas fechadas, medida em CONDIÇÕES ISOLADAS (modelo fresco por
teste, sem histórico) — a sequência da demo mistura efeitos (ver README: o modelo inclui arrasto
do ar e acima de ~1 m/s os torques aerodinâmicos acoplam os eixos):
  · canais: 4 atuadores (empuxo + 3 momentos) com gear físico · sensores prontos ·
  · keyframe hover: empuxo == peso (m·g = 0,26487 N) ·
  · mixer: wrench aplicado == analítico (identidade algébrica) ·
  · empuxo→altitude: amplitude de z == ΔF/(m·ω²) ·
  · momento→rotação: amplitude de ω == M/(I·ω) nos 3 eixos ·
  · demo: comandos dentro de ctrlrange · sem NaN.
"""
from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
from lab import mjkit  # noqa: E402  (define MUJOCO_GL=egl antes de importar mujoco)
from lab import crazyflie as cf  # noqa: E402

import argparse  # noqa: E402

import mujoco  # noqa: E402
import numpy as np  # noqa: E402

AQUI = Path(__file__).resolve().parent

FREQ = 0.25            # Hz dos cossenos dos modos
AMP_EMPUXO = 0.01      # N (≈ 4% do peso)
AMP_MOMENTO = 5e-7     # N·m por eixo (modesto: CF2 é nervoso e o arrasto do ar acopla acima de ~1 m/s)
TAXA_ROTOR = 0.02      # pulso de 2% do empuxo base num rotor de cada vez

FASES = [("hover", 2.0), ("empuxo", 8.0), ("momento_x", 4.0), ("momento_y", 4.0),
         ("momento_z", 4.0), ("rotores", 6.0), ("hover", 2.0)]


def fit_senoide(u: np.ndarray, y: np.ndarray) -> float:
    """Amplitude de y ≈ a·cos(u) + b·sin(u) por mínimos quadrados (janela de nº inteiro de períodos)."""
    G = np.column_stack([np.cos(u), np.sin(u)])
    (a, b), *_ = np.linalg.lstsq(G, y, rcond=None)
    return float(np.hypot(a, b))


def teste_empuxo_z() -> tuple[float, float]:
    """Modelo fresco, parado: 2 períodos de ΔF em cosseno → amplitude de z = ΔF/(m·ω²)."""
    model, data = cf.carregar()
    omega = 2 * np.pi * FREQ
    ts, zs = [], []
    for _ in range(int(8.0 / model.opt.timestep)):
        cf.modo_empuxo(model, data, data.time, amp=AMP_EMPUXO, freq=FREQ)
        mujoco.mj_step(model, data)
        ts.append(data.time), zs.append(data.qpos[2])
    ts = np.asarray(ts)
    u = omega * ts
    return fit_senoide(u, np.asarray(zs)), AMP_EMPUXO / (cf.MASSA * omega ** 2)


def teste_momentos_w() -> tuple[list[float], list[float]]:
    """Modelo fresco por eixo, parado: 1 período de M em cosseno → amplitude de ω = M/(I·ω)."""
    medidos, teorias = [], []
    for eixo in range(3):
        model, data = cf.carregar()
        I = float(model.body_inertia[model.body("cf2").id][eixo])
        omega = 2 * np.pi * FREQ
        ts, ws = [], []
        for _ in range(int(4.0 / model.opt.timestep)):
            cf.modo_momento(model, data, data.time, eixo=eixo, amp=AMP_MOMENTO, freq=FREQ)
            mujoco.mj_step(model, data)
            ts.append(data.time), ws.append(data.qvel[3 + eixo])
        ts = np.asarray(ts)
        medidos.append(fit_senoide(omega * ts, np.asarray(ws)))
        teorias.append(AMP_MOMENTO / (I * omega))
    return medidos, teorias


def aplica_fase(model, data, nome: str, tau: float) -> None:
    """Chama as funções de modo de `lab.crazyflie` com parâmetros de demonstração."""
    if nome == "hover":
        cf.modo_hover(model, data, tau)
    elif nome == "empuxo":
        cf.modo_empuxo(model, data, tau, amp=AMP_EMPUXO, freq=FREQ)
    elif nome.startswith("momento_"):
        cf.modo_momento(model, data, tau, eixo="xyz".index(nome[-1]), amp=AMP_MOMENTO, freq=FREQ)
    elif nome == "rotores":
        cf.modo_rotores(model, data, tau, taxa=TAXA_ROTOR, duracao=1.0)


def checa_canais(model: mujoco.MjModel) -> tuple[bool, str]:
    if model.nactuator != 4:
        return False, f"esperado 4 canais, há {model.nactuator}"
    for i, nome in enumerate(cf.MOTORES):
        if mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) != nome:
            return False, f"canal #{i} não é {nome}"
    gears = tuple(abs(float(model.actuator_gear[model.actuator(n).id, 3 + i])) for i, n in enumerate(cf.MOTORES[1:]))
    if not np.allclose(gears, cf.MOMENTOS_MAX, rtol=1e-9):
        return False, f"gear físico inesperado: {gears}"
    return True, "empuxo (0–0,35 N) + 3 momentos (±MOMENTOS_MAX) com gear físico"


def checa_sensores(model: mujoco.MjModel) -> tuple[bool, str]:
    nomes = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SENSOR, i) for i in range(model.nsensor)]
    if nomes != list(cf.SENSORES):
        return False, f"sensores {nomes}"
    return True, "body_gyro · body_linacc · body_quat (nativos) + posicao · vel (camada)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tol-amp", type=float, default=0.05, help="tolerância relativa das amplitudes vs teoria (padrão 5%)")
    ap.add_argument("--slowmo", type=float, default=1.0)
    ap.add_argument("--saida", default=str(AQUI / "out"))
    ap.add_argument("--sem-video", action="store_true")
    a = ap.parse_args()

    model, data = cf.carregar()
    dur_total = sum(d for _, d in FASES)
    bidx = model.body("cf2").id

    # ------------------------------------------------- validações analíticas (condições isoladas)
    amp_z, amp_z_teo = teste_empuxo_z()
    amps_w, amps_w_teo = teste_momentos_w()
    print(f"empuxo→z (isolado):   amplitude {amp_z:.4f} m · teoria ΔF/(m·ω²) = {amp_z_teo:.4f} m")
    print(f"momentos→ω (isolado): amplitude " + " / ".join(f"{x:.4f}" for x in amps_w)
          + " rad/s · teoria M/(I·ω) = " + " / ".join(f"{x:.4f}" for x in amps_w_teo))

    # mixer: identidade algébrica (round-trip contra a teoria da geometria dos rotores)
    t_rotores = np.array([0.10, 0.05, 0.07, 0.03])
    f_apl, m_apl = cf.comandar_rotores(model, data, t_rotores)
    f_teo = float(t_rotores.sum())
    m_teo = (sum(p[1] * ti for p, ti in zip(cf.POS_ROTORES, t_rotores)),
             -sum(p[0] * ti for p, ti in zip(cf.POS_ROTORES, t_rotores)),
             sum(g * cf.KM * ti for g, ti in zip(cf.GIRO, t_rotores)))
    err_mixer = max(abs(f_apl - f_teo), max(abs(x - y) for x, y in zip(m_apl, m_teo)))

    kid = model.key("hover").id
    hover_ok = abs(float(model.key_ctrl[kid][0]) - cf.PESO) < 1e-9

    # ------------------------------------------------- demo (sequência de modos, para o vídeo)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
    cam.trackbodyid = bidx
    cam.distance, cam.azimuth, cam.elevation = 1.0, 130.0, -12.0

    def controlador(m, d):
        acum = 0.0
        for nome, dur in FASES:
            if acum <= d.time < acum + dur:
                aplica_fase(m, d, nome, d.time - acum)
                return
            acum += dur

    print(f"\nCrazyflie · motor show: {[n for n, _ in FASES]} · {dur_total:.0f} s simulados")
    out = Path(a.saida)
    model.vis.global_.offwidth, model.vis.global_.offheight = 1280, 720
    res = mjkit.record(model, data, controlador, duration=dur_total, slowmo=a.slowmo, camera=cam,
                       mp4=None if a.sem_video else out / "crazyflie_motores.mp4",
                       gif=None if a.sem_video else out / "crazyflie_motores.gif",
                       sheet=None if a.sem_video else out / "folha.png",
                       hud=lambda m, d: [f"t = {d.time:5.2f} s · z = {d.qpos[2]:.2f} m · |v| = {np.linalg.norm(d.qvel[:3]):.2f} m/s"],
                       probes={"z": lambda m, d: d.qpos[2],
                               "empuxo": lambda m, d: cf.ler_motores(m, d)["empuxo"],
                               "w": lambda m, d: d.qvel[3:6].copy()})
    log = res["log"]
    z = np.asarray(log["z"])
    w = np.asarray(log["w"])
    empuxo = np.asarray(log["empuxo"])

    dentro = bool(np.all(empuxo >= -1e-12) and np.all(empuxo <= cf.EMPUXO_MAX + 1e-12))
    finito = bool(np.isfinite(z).all() and np.isfinite(w).all())

    checks = [
        ("canais de atuação (4) com gear físico", *checa_canais(model)),
        ("sensores prontos (3 nativos + 2)", *checa_sensores(model)),
        ("keyframe hover: empuxo == peso (m·g)", hover_ok,
         f"ctrl[0] = {float(model.key_ctrl[kid][0]):.5f} N · peso = {cf.PESO:.5f} N"),
        ("mixer de rotores: wrench == analítico", err_mixer < 1e-12, f"erro máx {err_mixer:.2e}"),
        (f"empuxo→altitude (isolado): |ΔA|/A < {a.tol_amp:.0%}",
         abs(amp_z - amp_z_teo) / amp_z_teo < a.tol_amp,
         f"medida {amp_z:.4f} m · teoria {amp_z_teo:.4f} m"),
        (f"momentos→rotação (isolado): |ΔA|/A < {a.tol_amp:.0%}",
         all(abs(x - y) / y < a.tol_amp for x, y in zip(amps_w, amps_w_teo)),
         "medida " + "/".join(f"{x:.4f}" for x in amps_w) + " vs teoria " + "/".join(f"{x:.4f}" for x in amps_w_teo) + " rad/s"),
        ("demo: comandos sempre dentro de ctrlrange", dentro, ""),
        ("demo: sem NaN/inf", finito, ""),
    ]

    ok_all = True
    for nome, ok, *det in checks:
        ok_all &= bool(ok)
        d = det[0] if det and det[0] else ""
        print(f"[{'OK ' if ok else 'FALHA'}] {nome}" + (f" — {d}" if d else ""))

    if not a.sem_video:
        mjkit.plot(log, ["z", "empuxo"], out / "altitude.png", "Crazyflie — altitude (m) · empuxo (N)")
        mjkit.plot(log, ["w"], out / "rotacao.png", "Crazyflie — velocidade angular de corpo (rad/s)")
        print(f"\nsaídas em {out} (crazyflie_motores.mp4/gif, folha.png, altitude.png, rotacao.png) · {res['frames']} quadros")
    print(f"simulação: {res.get('wall_s', 0):.1f} s de parede para {dur_total:.0f} s simulados")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
