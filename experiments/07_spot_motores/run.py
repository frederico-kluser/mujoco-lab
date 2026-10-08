#!/usr/bin/env python3
"""Spot (Boston Dynamics) — demo dos MOTORES e JUNTAS, sem lógica de locomoção.

Modelo pronto do mujoco_menagerie (`models/boston_dynamics_spot/scene.xml`): quadrúpede com 12 juntas
(3 por perna: hx, hy, kn) e 12 servos `<position>` (PD kp=500, kv=40). NÃO há marcha, equilíbrio, IK
nem política de RL — apenas os motores a seguir alvos de posição.

    uv run python experiments/07_spot_motores/run.py                 # demo "motor show" + validação + vídeo/GIF/gráficos
    uv run python experiments/07_spot_motores/run.py --sem-video     # só números
    uv run python experiments/07_spot_motores/run.py --amplitude 0.15 --janela 2.5

Roteiro: --repouso s na postura `home`, depois cada junta faz UMA senoide completa (±--amplitude rad,
--janela s) mantendo as outras na postura home, e --repouso s finais de repouso.

Validação (exit 0/1):
  1. estrutura junta↔servo 1:1 · 2. keyframe home = equilíbrio nominal (ctrl == qpos) ·
  3. servo puro vs teoria PD — em queda livre (sem chão), resposta sinusoidal das 4 juntas hx
     comparada com H(ω)=kp/(I(jω)²+kv·jω+kp), I = M[dof,dof] (|Δganho| < 5%, |Δfase| < 5°) ·
  4. rastreio em pé: ganho de amplitude ≥ 0.5 em todas as juntas (o acoplamento pelos pés no chão
     degrada o servo puro: medido ≈ 0.6 de ganho e ≈ 48° de atraso a 0,5 Hz) ·
  5. limites de junta respeitados · 6. base de pé no fim · 7. sem NaN.
"""
from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
from lab import mjkit  # noqa: E402  (define MUJOCO_GL=egl antes de importar mujoco)
from lab import spot  # noqa: E402  (API de funções: modos, controles e leituras de sensores)

import argparse  # noqa: E402

import mujoco  # noqa: E402
import numpy as np  # noqa: E402

AQUI = Path(__file__).resolve().parent
JUNTAS = spot.JUNTAS  # as 12 juntas do Spot (lab/spot.py)


# --------------------------------------------------------------------------------------- ajuste sinusoidal
def fit_senoide(u: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Ajusta y ≈ a·cos(u) + b·sin(u) por mínimos quadrados; devolve (amplitude, fase em rad)."""
    G = np.column_stack([np.cos(u), np.sin(u)])
    (a, b), *_ = np.linalg.lstsq(G, y, rcond=None)
    return float(np.hypot(a, b)), float(np.arctan2(b, a))


def teoria_pd(kp: float, kv: float, I: float, omega: float) -> tuple[float, float]:
    """Servo ideal kp·(alvo−q)−kv·q̇ sobre inércia I: H(ω)=kp/(I(jω)²+kv·jω+kp). Devolve (ganho, atraso em graus)."""
    H = kp / ((kp - I * omega ** 2) + 1j * kv * omega)
    return float(abs(H)), float(np.degrees(-np.angle(H)))


def valida_servo_puro(juntas: tuple[str, ...] = ("fl_hx", "fr_hx", "hl_hx", "hr_hx"),
                      amp: float = 0.2, periodo: float = 2.0, t0: float = 0.5) -> list[tuple]:
    """Senoida em queda livre (sem chão): sem contato, cada junta deve seguir a transferência analítica do PD."""
    model, data = spot.carregar(cena=False, sensores=False)  # spot.xml sem scene = sem piso → queda livre
    kid = model.key("home").id
    ctrl = mjkit.Ctrl(model)
    home = model.key_ctrl[kid].copy()
    lo, hi = model.actuator_ctrlrange[:, 0].copy(), model.actuator_ctrlrange[:, 1].copy()
    M = np.zeros((model.nv, model.nv))
    mujoco.mj_fullM(model, data, M)  # ordem 3.15: (m, d, dst)
    resultados = []
    for nome in juntas:
        aid = model.actuator(nome).id
        kp = float(model.actuator_gainprm[aid, 0])
        kv = float(-model.actuator_biasprm[aid, 2])
        j = JUNTAS.index(nome)
        qadr = int(model.jnt_qposadr[model.joint(nome).id])
        dofadr = int(model.jnt_dofadr[model.joint(nome).id])
        mujoco.mj_resetDataKeyframe(model, data, kid)
        mujoco.mj_forward(model, data)
        ts, alvos, qs = [], [], []
        for _ in range(int((t0 + 2 * periodo) / model.opt.timestep)):
            t = data.time
            alvo = home.copy()
            if t0 <= t < t0 + periodo:
                alvo[j] += amp * np.sin(2 * np.pi * (t - t0) / periodo)
            alvo = np.clip(alvo, lo, hi)
            for i in range(model.nactuator):
                ctrl.set(data, mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i), alvo[i])
            mujoco.mj_step(model, data)
            ts.append(data.time), alvos.append(alvo[j]), qs.append(data.qpos[qadr])
        ts = np.asarray(ts)
        w = (ts >= t0 + 0.5 * periodo) & (ts <= t0 + periodo)  # meia janela final = regime
        u = 2 * np.pi * (ts[w] - t0) / periodo
        amp_med, fase_med = fit_senoide(u, np.asarray(qs)[w])
        amp_cmd, fase_cmd = fit_senoide(u, np.asarray(alvos)[w])
        ganho_med = amp_med / amp_cmd
        atraso_med = np.degrees(fase_med - fase_cmd)  # > 0 = atraso (q atrás do alvo)
        I = float(M[dofadr, dofadr])
        ganho_teo, atraso_teo = teoria_pd(kp, kv, I, 2 * np.pi / periodo)
        resultados.append((nome, ganho_med, atraso_med, ganho_teo, atraso_teo, I, kp, kv))
    return resultados


class MotorShow:
    """Roteiro de motores: segura a postura home e faz UMA senoide por vez em cada junta (as outras seguram)."""

    def __init__(self, model: mujoco.MjModel, amplitude: float = 0.2, janela: float = 2.0, repouso: float = 2.0):
        self.m = model
        self.ctrl = mjkit.Ctrl(model)
        self.A, self.janela, self.repouso = float(amplitude), float(janela), float(repouso)
        kid = model.key("home").id
        self.home = model.key_ctrl[kid].copy()          # alvo nominal (ctrl do keyframe home)
        self.home_qpos = model.key_qpos[kid].copy()
        self.lo, self.hi = model.actuator_ctrlrange[:, 0].copy(), model.actuator_ctrlrange[:, 1].copy()
        self.qadr = [int(model.jnt_qposadr[model.joint(n).id]) for n in JUNTAS]   # acessores nomeados devolvem arrays: use os arrays crus
        self.dofadr = [int(model.jnt_dofadr[model.joint(n).id]) for n in JUNTAS]
        self.alvo = self.home.copy()                     # alvo do passo atual (lido pelas probes)
        self.ativa = "home"                              # junta sob senoide agora

    @property
    def t_fim_sweep(self) -> float:
        return self.repouso + len(JUNTAS) * self.janela

    @property
    def duracao(self) -> float:
        return self.t_fim_sweep + self.repouso

    def __call__(self, model: mujoco.MjModel, data: mujoco.MjData) -> None:
        alvo = self.home.copy()
        self.ativa = "home"
        if self.repouso <= data.time < self.t_fim_sweep:
            u = (data.time - self.repouso) / self.janela
            j = min(int(u), len(JUNTAS) - 1)
            fase = 2 * np.pi * (u - j)                   # uma senoide completa por janela (volta ao home)
            alvo[j] += self.A * np.sin(fase)
            self.ativa = JUNTAS[j]
        self.alvo = np.clip(alvo, self.lo, self.hi)
        for i, nome in enumerate(JUNTAS):
            self.ctrl.set(data, nome, self.alvo[i])


def checa_estrutura(model: mujoco.MjModel) -> tuple[bool, str]:
    """12 juntas ↔ 12 servos `position` 1:1, com transmissão direta para a junta de mesmo nome."""
    if model.nactuator != 12 or model.njnt != 13:
        return False, f"esperado 12 atuadores/13 juntas, há {model.nactuator}/{model.njnt}"
    for i, nome in enumerate(JUNTAS):
        anome = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
        if anome != nome:
            return False, f"atuador #{i} chama-se '{anome}', esperado '{nome}'"
        if model.actuator_trntype[i] != mujoco.mjtTrn.mjTRN_JOINT:
            return False, f"atuador '{nome}' não transmite para junta"
        jid = int(model.actuator_trnid[i, 0])
        if mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, jid) != nome:
            return False, f"atuador '{nome}' ligado à junta errada"
        if model.actuator_dyntype[i] != mujoco.mjtDyn.mjDYN_NONE:  # servo ideal: sem dinâmica interna
            return False, f"atuador '{nome}' não é servo position simples"
    return True, "12 servos position, 1:1 com as 12 juntas"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--amplitude", type=float, default=0.2, help="amplitude da senoide por junta, em rad (padrão 0.2)")
    ap.add_argument("--janela", type=float, default=2.0, help="duração da senoide de cada junta, em s (padrão 2.0)")
    ap.add_argument("--repouso", type=float, default=2.0, help="repouso inicial/final na postura home, em s (padrão 2.0)")
    ap.add_argument("--tol-ganho", type=float, default=0.5, help="ganho mínimo de amplitude aceite em pé (acoplamento pelos pés degrada o servo)")
    ap.add_argument("--slowmo", type=float, default=1.0)
    ap.add_argument("--saida", default=str(AQUI / "out"))
    ap.add_argument("--sem-video", action="store_true")
    a = ap.parse_args()

    # ---------------------------------------------------------------- 1/2 + 3 · modelo (com sensores) e servo puro (queda livre)
    model, data = spot.carregar()  # modelo do menagerie + camada de sensores (lab/spot.py), keyframe home
    show = MotorShow(model, a.amplitude, a.janela, a.repouso)

    servo = valida_servo_puro()
    print("servo puro (queda livre, sem chão) vs teoria PD  H(ω)=kp/(I(jω)²+kv·jω+kp):")
    for nome, gm, am, gt, at, I, kp, kv in servo:
        print(f"  {nome}: I={I:.4f} kg·m² · kp={kp:.0f}, kv={kv:.0f} · "
              f"ganho {gm:.3f} (teoria {gt:.3f}) · atraso {am:+.1f}° (teoria {at:+.1f}°)")

    out = Path(a.saida)
    dur = show.duracao

    # framebuffer offscreen: scene.xml não declara offwidth/offheight (640×480 por omissão); 720p em runtime
    # (não se edita o modelo do menagerie — isto não afeta a simulação, só o render)
    model.vis.global_.offwidth, model.vis.global_.offheight = 1280, 720

    # câmera livre fixa, enquadrando o robô de pé (scene.xml do menagerie não declara câmeras)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat, cam.distance, cam.azimuth, cam.elevation = [0.0, 0.0, 0.45], 2.2, 135.0, -15.0

    print(f"\nSpot · motor show em pé: {len(JUNTAS)} juntas × senoide de {a.janela:.1f} s (±{a.amplitude:.2f} rad) · {dur:.1f} s simulados")
    res = mjkit.record(model, data, show, duration=dur, slowmo=a.slowmo, camera=cam,
                       mp4=None if a.sem_video else out / "spot_motores.mp4",
                       gif=None if a.sem_video else out / "spot_motores.gif",
                       sheet=None if a.sem_video else out / "folha.png",
                       hud=lambda m, d: [f"t = {d.time:5.2f} s · motor: {show.ativa}"],
                       probes={"alvo": lambda m, d: show.alvo.copy(),
                               "q": lambda m, d: np.array([d.qpos[k] for k in show.qadr]),
                               "tau": lambda m, d: np.array([d.qfrc_actuator[k] for k in show.dofadr]),
                               "z_corpo": lambda m, d: d.body("body").xpos[2]})
    log = res["log"]
    t = np.asarray(log["t"])
    alvo, q, tau = np.asarray(log["alvo"]), np.asarray(log["q"]), np.asarray(log["tau"])

    # ------------------------------------------------------------------ métricas por junta
    rms = np.zeros(12)
    emax = np.zeros(12)
    ganhos = np.zeros(12)
    atrasos = np.zeros(12)
    tau_max = np.abs(tau).max(axis=0)
    omega = 2 * np.pi / a.janela
    for j in range(12):
        w = (t >= show.repouso + j * a.janela) & (t < show.repouso + (j + 1) * a.janela)
        err = alvo[w, j] - q[w, j]
        rms[j] = float(np.sqrt(np.mean(err ** 2)))
        emax[j] = float(np.abs(err).max())
        u = omega * (t[w] - show.repouso - j * a.janela)
        amp_q, fase_q = fit_senoide(u, q[w, j])
        amp_a, fase_a = fit_senoide(u, alvo[w, j])
        ganhos[j] = amp_q / amp_a
        atrasos[j] = np.degrees(fase_q - fase_a)

    qmin, qmax = q.min(axis=0), q.max(axis=0)
    margem = 2e-3  # 2 mm de folga numérica para os limites das juntas
    lo_j = np.array([model.jnt_range[model.joint(n).id, 0] for n in JUNTAS])
    hi_j = np.array([model.jnt_range[model.joint(n).id, 1] for n in JUNTAS])
    dentro = (qmin >= lo_j - margem) & (qmax <= hi_j + margem)
    fora = [JUNTAS[i] for i in range(12) if not bool(dentro[i])]

    kid = model.key("home").id
    home_qj = np.array([show.home_qpos[k] for k in show.qadr])
    home_ok = bool(np.allclose(show.home, home_qj, atol=1e-9) and np.all(show.home >= show.lo) and np.all(show.home <= show.hi))

    err_ganho = max(abs(g - t_) for _, g, _, t_, *_ in servo)
    err_fase = max(abs(f - t_) for _, _, f, _, t_, *_ in servo)

    mujoco.mj_forward(model, data)  # derivados consistentes para a leitura final
    R = data.body("body").xmat.reshape(3, 3)
    incl = float(np.arccos(np.clip(R[2, 2], -1.0, 1.0)))
    z_fim = float(data.body("body").xpos[2])
    finito = bool(np.isfinite(q).all() and np.isfinite(tau).all() and np.isfinite(alvo).all())

    # sensores da camada lab/spot.py (IMU do tronco + forças dos pés) no repouso final
    imu = spot.ler_imu(model, data)
    acc = imu["acc"]
    ok_imu = bool(abs(acc[2] - spot.GRAVIDADE) < 0.3 and np.linalg.norm(acc[:2]) < 0.3)
    soma_pes = float(sum(spot.ler_pes(model, data).values()))
    ok_pes = bool(abs(soma_pes - spot.peso(model)) / spot.peso(model) < 0.05)

    checks = [
        ("estrutura junta↔servo 1:1", *checa_estrutura(model)),
        ("keyframe home consistente (ctrl == qpos, dentro dos limites)", home_ok,
         f"desvio máx {np.abs(show.home - home_qj).max():.2e} rad"),
        ("servo puro = teoria PD (|Δganho| < 0.05, |Δfase| < 5°)", err_ganho < 0.05 and err_fase < 5.0,
         f"Δganho máx {err_ganho:.3f} · Δfase máx {err_fase:.1f}°"),
        (f"rastreio em pé: ganho de amplitude ≥ {a.tol_ganho:.2f} (todas as juntas)", bool((ganhos >= a.tol_ganho).all()),
         f"pior junta {JUNTAS[int(ganhos.argmin())]} = {ganhos.min():.3f}"),
        ("limites de junta respeitados", not fora, f"fora: {fora}" if fora else ""),
        ("base de pé no fim (z > 0.35 m, inclinação < 0.3 rad)", bool(z_fim > 0.35 and incl < 0.3),
         f"z = {z_fim:.3f} m · incl = {incl:.3f} rad"),
        ("sensor IMU: acc ≈ +g em repouso (aceleração própria)", ok_imu, f"acc = {np.round(acc, 2)} m/s²"),
        ("sensores dos pés: Σ forças ≈ peso", ok_pes,
         f"Σ = {soma_pes:.1f} N · peso = {spot.peso(model):.1f} N"),
        ("sem NaN/inf", finito, ""),
    ]

    print(f"\n{'junta':>6} {'RMS (rad)':>10} {'máx (rad)':>10} {'ganho':>7} {'atraso':>8} {'τ máx (N·m)':>12} {'q min..máx (rad)':>22}")
    for j, nome in enumerate(JUNTAS):
        print(f"{nome:>6} {rms[j]:10.4f} {emax[j]:10.4f} {ganhos[j]:7.3f} {atrasos[j]:+7.1f}° {tau_max[j]:12.1f} {qmin[j]:10.3f}..{qmax[j]:8.3f}")
    print("em pé, os pés no chão acoplam toda a estrutura: o servo perde ganho e atrasa (0,5 Hz · servo puro teria ganho ≈ 0.97, atraso ≈ 14°)")
    print("torques de referência do Spot real (BD docs): HX/HY ≈ 45 N·m · KN 37–97 N·m (o modelo usa actuatorfrcrange ±1000, não afinado)")
    ok_all = True
    for nome, ok, *det in checks:
        ok_all &= bool(ok)
        d = det[0] if det and det[0] else ""
        print(f"[{'OK ' if ok else 'FALHA'}] {nome}" + (f" — {d}" if d else ""))

    if not a.sem_video:
        mjkit.plot(log, ["alvo", "q"], out / "rastreio.png", "Spot — alvo dos servos × posição das 12 juntas (rad)")
        mjkit.plot(log, ["tau", "z_corpo"], out / "motores.png", "Spot — torque dos motores (N·m) · altura da base (m)")
        print(f"\nsaídas em {out} (spot_motores.mp4/gif, folha.png, rastreio.png, motores.png) · {res['frames']} quadros")
    print(f"simulação: {res.get('wall_s', 0):.1f} s de parede para {dur:.1f} s simulados")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
