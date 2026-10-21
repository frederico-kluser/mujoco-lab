"""teste_ombro_fuso.py — prova do OMBRO ACESSÍVEL: atuador linear de fuso Tr8×2 numa alavanca (build `articulado_15pol_abs`).

Pedido do dono (2026-10-20): «a junta do começo do drone não parece realista, veja se estamos REALMENTE simulando um
mecanismo real e fácil de fazer». O sem-fim de módulo 1 não aguentava o momento do empuxo (~500 N no dente); o ombro
passou a ser uma dobradiça (veio Ø8 em 2 × 608ZZ) movida por uma BIELA: um motorredutor JGB37-520 roda um fuso Tr8×2
cuja porca de latão empurra a alavanca do cubo do braço — as peças do eixo Z de uma impressora 3D. Este teste prova,
contra ORÁCULOS escritos aqui (independentes de `componentes.Fuso`):

  §1 fórmulas fechadas — λ = atan(p/(π·d₂)) < φ' = atan(μ/cos β) (autobloqueio), η = tan λ/tan(λ+φ'); L(q) = |R_y(q)·a − b|
     e o braço de alavanca |dL/dq| por diferenças finitas; o inverso q(θ) exato nos 4 quadrantes; L monótono no curso;
     braço de alavanca mínimo ≥ 30 mm; o curso da porca cabe no fuso; binário/velocidade «de ficha» = servo × N(0) × η;
  §2 modelo — Σ massas = orçamento; o corpo do atuador no CM declarado (B + cm·û) e o carro da porca em A, no braço;
  §3 bancada — um ombro vai a −8°: a junta fica onde a porca a põe (q do MuJoCo = q(θ) do oráculo, ± folga) e a
     velocidade média ≤ ω₀/|N(q)| (a reta do motor através da biela); os outros 3 parados;
  §4 pairagem — o fuso segura o momento do empuxo com a corrente de ESPERA; servos dos ombros DESLIGADOS 2 s em voo:
     o braço não se mexe mais do que a folga;
  §5 voo — o corpo arfa a ±20° com os motores de nível e o drone parado (núcleo de firmware, interface 4);
  §6 mutações (`--mutacao`) — cada bug plantado tem de FALHAR na checagem certa.

    .venv/bin/python experiments/09_drone_hover_rl/teste_ombro_fuso.py [--so-estatico] [--mutacao]
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def _raiz_das_fontes(argv: list[str]) -> Path:
    for i, a in enumerate(argv):
        if a == "--fontes" and i + 1 < len(argv):
            return Path(argv[i + 1]).resolve()
    return _REPO


RAIZ = _raiz_das_fontes(sys.argv)
_EXP = RAIZ / "experiments" / "09_drone_hover_rl"
sys.path[:0] = [str(RAIZ), str(_EXP)]
os.environ.setdefault("MUJOCO_GL", "egl")

import mujoco
import numpy as np

from lab import drone_rpi as dr

BUILD = "articulado_15pol_abs"


class Checagens:
    def __init__(self) -> None:
        self.linhas: list[str] = []
        self.falhas: list[str] = []

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.linhas.append(nome)
        if not cond:
            self.falhas.append(nome)
        print(f"        [{'OK  ' if cond else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""), flush=True)
        return bool(cond)


def _titulo(texto: str) -> None:
    print(f"\n[teste] {texto}", flush=True)


# ------------------------------------------------------------------------------------------------ oráculo da biela
def _ry(q: float) -> np.ndarray:
    c, s = math.cos(q), math.sin(q)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _vetores(dados: dict, sx: float, sy: float) -> tuple[np.ndarray, np.ndarray]:
    """(a, b) em metros a partir do JSON do catálogo (espelho por quadrante) — sem passar por `componentes.Fuso`."""
    tras = sx < 0.0 and dados.get("alavanca_tras_mm") is not None
    a = np.array(dados["alavanca_tras_mm"] if tras else dados["alavanca_mm"], float) / 1000.0
    b = np.array((dados.get("base_tras_mm") or dados["base_mm"]) if tras else dados["base_mm"], float) / 1000.0
    esp = np.array([1.0 if tras else sx, sy, 1.0])
    return a * esp, b * esp


def _comp(a: np.ndarray, b: np.ndarray, q: float) -> float:
    return float(np.linalg.norm(_ry(q) @ a - b))


def _q_de_comp(a: np.ndarray, b: np.ndarray, alvo: float, lim=(-0.9, 0.9)) -> float:
    """Inverso por bisseção (oráculo lento e independente)."""
    lo, hi = lim
    flo = _comp(a, b, lo) - alvo
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        fm = _comp(a, b, mid) - alvo
        if (fm < 0.0) == (flo < 0.0):
            lo, flo = mid, fm
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _dados_fuso() -> dict:
    cat = dr.carregar_catalogo()
    b = dr.carregar_builds()["builds"][BUILD]
    return cat["mecanismos_braco"][b["bracos"]]


# ============================================================================================ §1 fórmulas
def checa_formulas(c: Checagens) -> None:
    _titulo("§1 fuso trapezoidal e biela pelas fórmulas fechadas (oráculo independente)")
    try:
        hw = dr.hardware(BUILD)
    except Exception as erro:  # noqa: BLE001
        c.ok("[§1] build acessível resolve", False, f"{type(erro).__name__}: {erro}")
        return
    mec = _dados_fuso()
    d = mec["ombro"]["fuso"]
    o = hw.bracos.ombro
    p, d2 = d["passo_mm"] / 1000.0, d["d_medio_mm"] / 1000.0
    beta, mu = math.radians(d["meio_angulo_flanco_graus"]), float(d["coef_atrito"])
    lam = math.atan(p / (math.pi * d2))
    phi = math.atan(mu / math.cos(beta))
    eta = math.tan(lam) / math.tan(lam + phi)
    c.ok("[§1] Tr8×2 AUTOBLOQUEANTE: λ = atan(p/(π·d₂)) < φ' = atan(μ/cos β) — o empuxo não roda o fuso",
         lam < phi and o.e_autobloqueante and abs(o.angulo_avanco - lam) < 1e-12,
         f"λ {math.degrees(lam):.2f}° < φ' {math.degrees(phi):.2f}°")
    c.ok("[§1] rendimento η = tan λ / tan(λ+φ') (o mesmo da junta)", abs(o.eficiencia_subir - eta) < 1e-12, f"η {eta:.3f}")
    erro_l, erro_inv, mono, braco_min = 0.0, 0.0, True, 1.0
    lim = o.limites
    for sx in (1.0, -1.0):
        for sy in (1.0, -1.0):
            a, b = _vetores(d, sx, sy)
            qs = np.linspace(lim[0], lim[1], 81)
            dl = []
            for q in qs:
                erro_l = max(erro_l, abs(o.fuso.comprimento_em(float(q), sx, sy) - _comp(a, b, float(q))))
                h = 1e-6
                dnum = (_comp(a, b, q + h) - _comp(a, b, q - h)) / (2 * h)
                dl.append(dnum)
                erro_l = max(erro_l, abs(o.fuso.derivada(float(q), sx, sy) - dnum) * 1e-3)
                th = o.fuso.theta_de_q(float(q), sx, sy)
                alvo = _comp(a, b, 0.0) + th * p / (2.0 * math.pi)
                erro_inv = max(erro_inv, abs(o.fuso.q_de_theta(th, sx, sy) - _q_de_comp(a, b, alvo)))
            dl = np.array(dl)
            mono &= bool(np.all(dl < 0) or np.all(dl > 0))
            braco_min = min(braco_min, float(np.abs(dl).min()))
    c.ok("[§1] L(q) = |R_y(q)·a − b| e dL/dq iguais ao oráculo nos 4 quadrantes", erro_l < 1e-9, f"erro {erro_l:.1e} m")
    c.ok("[§1] o inverso q(θ) (forma fechada) = bisseção do oráculo em todo o curso", erro_inv < 1e-7,
         f"erro {math.degrees(erro_inv):.1e}°")
    c.ok("[§1] L(q) MONÓTONO em todo o curso (o fuso comanda a junta de ponta a ponta)", mono)
    c.ok("[§1] braço de alavanca mínimo ≥ 30 mm no curso (o binário que o fuso dá cai com ele)", braco_min >= 0.030,
         f"mín {braco_min * 1000:.1f} mm")
    a, b = _vetores(d, 1.0, 1.0)
    ls = [_comp(a, b, float(q)) for q in np.linspace(lim[0], lim[1], 81)]
    curso = max(ls) - min(ls)
    folga_fuso = d["comprimento_fuso_mm"] / 1000.0 - curso
    c.ok("[§1] o curso da porca cabe no fuso com ≥ 35 mm para a porca e o bloco dos rolamentos", folga_fuso >= 0.035,
         f"curso {curso * 1000:.1f} mm · fuso {d['comprimento_fuso_mm']:.0f} mm")
    n0 = 2.0 * math.pi * abs((_comp(a, b, 1e-6) - _comp(a, b, -1e-6)) / 2e-6) / p
    sv = o.servo
    c.ok("[§1] «de ficha» com a junta a 0: N(0) = 2π·|L'(0)|/p, τ_b = τ_servo·N·η, ω₀ = ω_servo/N",
         abs(o.reducao - n0) < 1e-3 and abs(o.binario_bloqueio_saida - sv.binario_bloqueio * n0 * eta) < 1e-3
         and abs(o.omega_vazio_saida - sv.omega_vazio / n0) < 1e-6,
         f"N {n0:.1f} · τ_b {o.binario_bloqueio_saida:.1f} N·m · ω₀ {math.degrees(o.omega_vazio_saida):.1f}°/s")
    tw = hw.empuxo_max_total / (hw.massa_total * 9.81) if hasattr(hw, "empuxo_max_total") else None
    c.ok("[§1] o build acessível resolve e voa com margem (T/W ≥ 1,8)", tw is None or tw >= 1.8,
         f"{hw.massa_total * 1000:.0f} g" + (f" · T/W {tw:.2f}" if tw is not None else ""))


# ============================================================================================ §2 modelo
def checa_modelo(c: Checagens) -> None:
    _titulo("§2 modelo: massas = orçamento, atuador no CM declarado, carro da porca no braço")
    hw = dr.hardware(BUILD)
    m, _d = dr.carregar(hw)
    soma = float(m.body_mass[1:].sum())
    c.ok("[§2] Σ massas do modelo = orçamento do build", abs(soma - hw.massa_total) < 1e-6,
         f"{soma * 1000:.2f} g · orçamento {hw.massa_total * 1000:.2f} g")
    dd = _dados_fuso()["ombro"]["fuso"]
    erro = 0.0
    for k in range(1, 5):
        h = np.array(m.body(f"braco{k}").pos)
        sx, sy = math.copysign(1.0, h[0]), math.copysign(1.0, h[1])
        a, b = _vetores(dd, sx, sy)
        u = (a - b) / np.linalg.norm(a - b)
        cm = h + b + dd["cm_atuador_mm"] / 1000.0 * u
        erro = max(erro, float(np.linalg.norm(np.array(m.geom(f"servo_ombro{k}").pos) - cm)))
        erro = max(erro, float(np.linalg.norm(np.array(m.geom(f"ombro{k}_carro").pos) - a)))
        c_m = m.geom(f"ombro{k}_carro").bodyid
        erro = max(erro, 0.0 if m.body(int(c_m[0]) if hasattr(c_m, "__len__") else int(c_m)).name == f"braco{k}" else 1.0)
    c.ok("[§2] corpo do atuador em B + cm·(B→A) no corpo do drone; carro da porca em A no corpo do braço", erro < 1e-9,
         f"erro {erro:.1e} m")


# ============================================================================================ §3 bancada
def checa_bancada(c: Checagens) -> None:
    _titulo("§3 bancada (drone pousado): a junta segue a porca; velocidade ≤ ω₀/|N(q)| (motor através da biela)")
    hw = dr.hardware(BUILD)
    m, d = dr.carregar(hw)
    pl = dr.Planta(hw, m, d, rng=np.random.default_rng(3))
    mujoco.mj_resetData(m, d)
    d.qpos[2] = 0.3
    mujoco.mj_forward(m, d)
    pl.reiniciar(1.0, armado=False)
    for _ in range(1000):
        pl.passo()
    sv = pl.servos
    o = hw.bracos.ombro
    dd = _dados_fuso()["ombro"]["fuso"]
    alvos = np.zeros(8)
    alvos[4:] = math.radians(40.0)
    alvos[0] = math.radians(-8.0)
    sv.definir_alvos(alvos)
    serie, desvio = [], 0.0
    h = np.array(m.body("braco1").pos)
    sx, sy = math.copysign(1.0, h[0]), math.copysign(1.0, h[1])
    a, b = _vetores(dd, sx, sy)
    l0 = _comp(a, b, 0.0)
    s0 = sv.servos[0]
    sinal = 1.0 if o.fuso.n_em(0.0, sx, sy) > 0 else -1.0
    v_lim = []
    k_rig = float(_dados_fuso()["ombro"]["rigidez_nm_rad"])
    for k in range(3000):                        # 6 s
        pl.passo()
        q = float(d.qpos[pl.j_qadr[0]])
        serie.append((k * pl.dt, q))
        q_porca = _q_de_comp(a, b, l0 + sinal * s0.theta * dd["passo_mm"] / 1000.0 / (2.0 * math.pi))
        # o braço pode estar afastado da porca pela FOLGA e pela deformação elástica |τ|/k — não mais
        desvio = max(desvio, abs(q - q_porca) - abs(s0.tau) / k_rig)
        n_q = 2.0 * math.pi * abs((_comp(a, b, q + 1e-6) - _comp(a, b, q - 1e-6)) / 2e-6) / (dd["passo_mm"] / 1000.0)
        v_lim.append(o.servo.omega_vazio / n_q)
    so1 = np.array(serie)
    curso = math.radians(-8.0)
    t10 = so1[np.argmax(so1[:, 1] <= 0.1 * curso), 0]
    t90 = so1[np.argmax(so1[:, 1] <= 0.9 * curso), 0]
    v_media = 0.8 * abs(curso) / max(t90 - t10, 1e-6)
    q_fim = np.degrees(d.qpos[pl.j_qadr])
    c.ok("[§3] a junta do MuJoCo fica onde a PORCA a põe (oráculo da biela a partir do ângulo do fuso) ± folga ± |τ|/k",
         desvio <= 0.5 * o.folga + math.radians(0.05), f"desvio máx {math.degrees(desvio):.3f}° (folga ±{math.degrees(o.folga) / 2:.2f}°)")
    c.ok("[§3] ombro 1 chega aos −8° com a velocidade média ≤ ω₀/|N(q)| (a reta do motor através da biela); os outros 3 "
         "parados", v_media <= max(v_lim) * 1.02 and abs(q_fim[0] + 8.0) < 1.0 and np.all(np.abs(q_fim[1:4]) < 1.0),
         f"média {math.degrees(v_media):.1f}°/s (limite {math.degrees(max(v_lim)):.1f}°/s) · fim {np.round(q_fim[:4], 2)}°")


def checa_bloqueio(c: Checagens) -> None:
    """§3b — a proteção de BLOQUEIO do firmware, num servo isolado com o braço PRESO (q = 0 fixo, alvo a +10°)."""
    _titulo("§3b proteção de bloqueio: a empurrar sem andar, o FC corta o driver e o fuso segura")
    from lab.drone_rpi.servos import ServoJunta
    hw = dr.hardware(BUILD)
    mec = hw.bracos
    s = ServoJunta(mec.ombro, mec, "ombro1", np.random.default_rng(0), (1.0, 1.0))
    s.reiniciar(0.0)
    s.definir_alvo(math.radians(10.0))
    dt = 0.002
    serie = []
    for k in range(2500):                         # 5 s com o braço preso
        s.passo(0.0, 0.0, dt)
        serie.append((k * dt, s.corrente, s.duty))
    arr = np.array(serie)
    i_esp, i_b = mec.ombro.servo.corrente_espera, mec.ombro.servo.corrente_bloqueio
    corte = mec.ombro.corte_bloqueio
    pausa = arr[arr[:, 2] == 0.0]
    t_pausa = float(len(pausa)) * dt
    c.ok("[§3b] braço preso: o motor empurra (corrente de bloqueio) e ao fim do corte o FC DESLIGA o driver (só a espera) "
         "durante a pausa, e volta a tentar", s.cortes_bloqueio >= 1 and float(arr[: int(corte / dt), 1].max()) > 0.5 * i_b
         and t_pausa >= 0.9 * mec.ombro.pausa_bloqueio and abs(float(pausa[:, 1].mean()) - i_esp) < 1e-9,
         f"{s.cortes_bloqueio} corte(s) em 5 s · pico {arr[:, 1].max():.2f} A · {t_pausa:.1f} s desligado a {i_esp} A")


def checa_trava_tiro(c: Checagens) -> None:
    """§3d — ao ordenar um tiro o FC TRAVA os motores dos ombros até a bala sair (o fuso segura): nenhum impulso do motor
    mexe o corpo enquanto o cano aponta (servos isolados, a meio de um movimento)."""
    _titulo("§3d trava de tiro: com um tiro a sair os ombros param (o fuso segura) e depois retomam")
    from lab.drone_rpi.servos import ServosBracos
    hw = dr.hardware(BUILD)
    sv = ServosBracos(hw.bracos, np.random.default_rng(0), [(1.0, 1.0), (-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0)])
    sv.reiniciar(np.zeros(8))
    alvos = np.zeros(8)
    alvos[:4] = math.radians(10.0)
    sv.definir_alvos(alvos)
    dt = 0.002
    q = np.zeros(8)

    def passo():
        sv.passo(q, np.zeros(8), dt)
        for i, s in enumerate(sv.servos[:4]):
            q[i] = s._q_de_theta(s.theta)
    for _ in range(100):                          # 0,2 s a andar
        passo()
    th0 = np.array([s.theta for s in sv.servos[:4]])
    sv.travar_ombros(0.05)
    duties = []
    for _ in range(int(0.05 / dt)):
        passo()
        duties.append([s.duty for s in sv.servos[:4]])
    th1 = np.array([s.theta for s in sv.servos[:4]])
    for _ in range(50):
        passo()
    th2 = np.array([s.theta for s in sv.servos[:4]])
    c.ok("[§3d] travados 50 ms a meio do movimento: PWM 0 e o fuso parado; depois retomam", np.allclose(duties, 0.0)
         and np.allclose(th1, th0) and np.all(np.abs(th2 - th1) > 0.01),
         f"Δθ travado {np.abs(th1 - th0).max():.1e} rad · depois {np.abs(th2 - th1).min():.2f} rad")


def checa_perfil(c: Checagens) -> None:
    """§3c — sem carga, o braço vai ao FIM do curso à velocidade do perfil através da biela: q̇ = f·ω₀/|N(q)| — mais
    depressa onde o braço de alavanca encurta (servo isolado; o braço segue a porca, sem MuJoCo)."""
    _titulo("§3c sem carga: a velocidade do braço muda com o braço de alavanca, q̇ = f·ω₀/|N(q)|")
    from lab.drone_rpi.servos import ServoJunta
    hw = dr.hardware(BUILD)
    mec = hw.bracos
    o = mec.ombro
    s = ServoJunta(o, mec, "ombro1", np.random.default_rng(0), (1.0, 1.0))
    s.reiniciar(0.0)
    alvo = 0.9 * o.limites[1]
    s.definir_alvo(alvo)
    dt, q, desvios = 0.002, 0.0, []
    for _ in range(4000):
        q_ant = q
        s.passo(q, 0.0, dt)
        q = s._q_de_theta(s.theta)                 # braço rígido e sem carga: está onde a porca o põe
        v = (q - q_ant) / dt
        if 0.3 * alvo < q < 0.85 * alvo:            # em cruzeiro (fora da aceleração, do apanhar do atraso e da travagem)
            # o braço segue o PERFIL (sp): a velocidade é a do perfil no sítio do perfil
            v_teo = o.fracao_velocidade_perfil * o.servo.omega_vazio / abs(o.fuso.n_em(s.sp, 1.0, 1.0))
            desvios.append(abs(v / v_teo - 1.0))
    n0, n_fim = abs(o.fuso.n_em(0.0)), abs(o.fuso.n_em(0.85 * alvo))
    c.ok("[§3c] sem carga, em cruzeiro, o braço anda a f·ω₀/|N(q)| (±3 %) — mais depressa no fim do curso, onde a "
         "alavanca efetiva encurta", bool(desvios) and max(desvios) < 0.03,
         f"desvio máx {100 * max(desvios or [1.0]):.1f} % · N(0) {n0:.0f} → N(fim) {n_fim:.0f}")


# ============================================================================================ §4 pairagem
def checa_pairagem(c: Checagens) -> None:
    _titulo("§4 pairagem: o fuso segura o momento do empuxo com 0 A e, desligado, não deixa o braço mexer")
    import sim_view as sv_mod
    from env_real import DroneRealEnv
    env = DroneRealEnv(build=BUILD, modo_acao="ctbr", comando=True, com_alvo=False, episodio_s=40.0)
    nuc = sv_mod.NucleoClassico.criar(env)
    nuc.instalar()
    env.reset(seed=4)
    nuc.pos_reset()
    hover = {"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0}
    for _ in range(300):
        nuc.comando(hover)
        env.step(np.zeros(4, dtype=np.float32))
    pl = env.planta
    tau = float(np.abs(pl.servos.binarios[:4]).mean())
    i_o = pl.servos.correntes[:4]
    i_esp = env.hw.bracos.ombro.servo.corrente_espera
    c.ok("[§4] pairagem: o ombro aguenta o momento do empuxo (> 3 N·m) com a corrente de ESPERA (o fuso é que segura)",
         tau > 3.0 and float(np.max(i_o)) < i_esp + 0.05, f"momento {tau:.2f} N·m · corrente {np.round(i_o, 3)} A")
    q0 = pl.juntas_verdade()[:4].copy()
    env.definir_modo_bracos("rigido")
    for s in pl.servos.servos[:4]:
        s.ligado = False
    for _ in range(100):
        nuc.comando(hover)
        env.step(np.zeros(4, dtype=np.float32))
    dq = float(np.degrees(np.abs(pl.juntas_verdade()[:4] - q0)).max())
    folga = math.degrees(env.hw.bracos.ombro.folga)
    c.ok("[§4] servos dos ombros DESLIGADOS 2 s em voo: o braço não se mexe mais do que a folga (autobloqueio)",
         dq <= folga, f"max |Δq| {dq:.3f}° (folga {folga:.2f}°)")


# ============================================================================================ §5 voo
def checa_voo(c: Checagens) -> None:
    _titulo("§5 voo: o corpo arfa ±20° para mirar, os motores ficam de nível, xyz parado")
    import sim_view as sv_mod
    from env import atitude
    from env_real import DroneRealEnv
    env = DroneRealEnv(build=BUILD, modo_acao="ctbr", comando=True, com_alvo=False, episodio_s=60.0)
    nuc = sv_mod.NucleoClassico.criar(env)
    nuc.instalar()
    env.reset(seed=2)
    nuc.pos_reset()
    hover = {"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0}
    for _ in range(300):
        nuc.comando(hover)
        env.step(np.zeros(4, dtype=np.float32))
    p0 = env.data.qpos[:3].copy()
    for alvo in (-20.0, 20.0):
        env.definir_pitch_corpo(math.radians(alvo))
        pit, mot, des, trans = [], [], [], []
        for k in range(500):
            nuc.comando(hover)
            env.step(np.zeros(4, dtype=np.float32))
            trans.append(float(np.linalg.norm(env.data.qpos[:3] - p0)))
            if k >= 400:
                pit.append(math.degrees(atitude(env.data.qpos[3:7])[1]))
                mot.append(math.degrees(float(nuc.nucleo.saida.pitch_motor)))
                des.append(trans[-1])
        c.ok(f"[§5] corpo a {alvo:+.0f}°: pitch médio a ±1°, motores de nível (±2°), x/y/z a < 8 cm em regime e < 0,4 m no "
             "transitório", abs(np.mean(pit) - alvo) < 1.0 and np.max(np.abs(mot)) < 2.0 and max(des) < 0.08
             and max(trans) < 0.4,
             f"pitch {np.mean(pit):+.2f}±{np.std(pit):.2f}° · motores máx {np.max(np.abs(mot)):.2f}° · desvio "
             f"{max(des) * 100:.1f} cm (transitório {max(trans) * 100:.1f} cm)")


# ============================================================================================ §6 mutações
MUTACOES = [
    # (nome, ficheiro relativo, texto original, texto mutado, marca da checagem que tem de falhar, argumentos)
    ("fuso-sem-autobloqueio", "models/drone_rpi/componentes.json", '"coef_atrito": 0.15,', '"coef_atrito": 0.05,',
     "autobloqueante", ["--so-estatico"]),
    ("reducao-constante", "lab/drone_rpi/servos.py",
     "return self.n if self.fuso is None else abs(self.fuso.n_em(q, self.sx, self.sy))", "return self.n",
     "alavanca efetiva encurta", []),
    ("porca-ignorada", "lab/drone_rpi/servos.py",
     "return theta / self.n if self.fuso is None else self.fuso.q_de_theta(self._s * theta, self.sx, self.sy)",
     "return theta / self.n", "onde a PORCA", []),
    ("carro-no-corpo", "lab/drone_rpi/modelo.py", 'b.add_geom(name=f"ombro{k}_carro"', 'corpo.add_geom(name=f"ombro{k}_carro"',
     "carro da porca", ["--so-estatico"]),
    ("sem-trava-de-tiro", "lab/drone_rpi/servos.py", "                s._travado = max(s._travado, float(duracao_s))",
     "                pass", "travados 50 ms", []),
    ("sem-protecao-bloqueio", "lab/drone_rpi/servos.py",
     "                    self._pausa, self._t_bloqueio = j.pausa_bloqueio, 0.0",
     "                    self._t_bloqueio = 0.0", "DESLIGA o driver", []),
]


def checa_mutacoes(c: Checagens) -> None:
    _titulo("§6 mutações: cada bug plantado FALHA na checagem certa")
    base = Path(tempfile.mkdtemp(prefix="mut_fuso_", dir=os.environ.get("TMPDIR")))
    try:
        for nome, rel, orig, mut, marca, extra in MUTACOES:
            copia = base / nome
            shutil.copytree(RAIZ, copia, ignore=shutil.ignore_patterns(".git", ".venv", "node_modules", "out", "docs",
                                                                         "memory", "pesquisas", "__pycache__"))
            f = copia / rel
            texto = f.read_text(encoding="utf-8")
            if orig not in texto:
                c.ok(f"[§6] mutação {nome}: o texto original existe em {rel}", False)
                continue
            f.write_text(texto.replace(orig, mut, 1), encoding="utf-8")
            r = subprocess.run([sys.executable, str(copia / "experiments/09_drone_hover_rl/teste_ombro_fuso.py"),
                                "--fontes", str(copia), *extra], capture_output=True, text=True, timeout=900, check=False,
                               env={**os.environ, "PYTHONPATH": str(copia), "DRONE_DETALHES": "nenhum"})   # a física não
            #                                                                         depende dos detalhes (provado no ver.py)
            falhas = [ln for ln in r.stdout.splitlines() if "FALHA" in ln and marca.lower() in ln.lower()]
            c.ok(f"[§6] mutação {nome} ({rel}) FALHA na checagem certa ('{marca}')", r.returncode != 0 and bool(falhas),
                 f"exit {r.returncode} · {len(falhas)} falha(s) com a marca")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Prova do ombro de fuso (biela) do build acessível.")
    ap.add_argument("--so-estatico", action="store_true", help="só §1–§2 (sem simular; usado pelas mutações)")
    ap.add_argument("--mutacao", action="store_true", help="corre SÓ as mutações (§6)")
    ap.add_argument("--fontes", type=Path, default=_REPO)
    a = ap.parse_args(argv)
    total = Checagens()
    if a.mutacao:
        checa_mutacoes(total)
    else:
        usadas = Path(dr.__file__).resolve().parents[2]
        total.ok("[§0] o teste corre contra as fontes pedidas", usadas == RAIZ, f"lab em {usadas}")
        checa_formulas(total)
        if not any("resolve" in f for f in total.falhas):
            checa_modelo(total)
            if not a.so_estatico:
                checa_bancada(total)
                checa_bloqueio(total)
                checa_perfil(total)
                checa_trava_tiro(total)
                checa_pairagem(total)
                checa_voo(total)
    print(f"\n[teste] {len(total.linhas) - len(total.falhas)}/{len(total.linhas)} checagens OK", flush=True)
    if total.falhas:
        for nome in total.falhas:
            print(f"[teste] FALHOU: {nome}", flush=True)
        return 1
    print("[teste] ombro de fuso: autobloqueante pelas fórmulas, a junta segue a porca, a velocidade é a do motor através "
          "da biela, segura o empuxo com 0 A e o corpo arfa para mirar com o drone parado", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
