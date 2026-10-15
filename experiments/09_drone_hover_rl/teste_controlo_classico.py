#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_controlo_classico.py — PROVA da cascata clássica (`controlo_classico.py`).

Checagens + exit code (0 = tudo OK, 1 = alguma falhou), no estilo dos outros `teste_*.py`:

  §1 FÓRMULAS FECHADAS (sem simulador): ganhos derivados da planta vs as equações (razões entre laços, K_i, limites
     de inclinação, folga de yaw), compensação 1/(cosφ·cosθ), controlador raiz quadrada, erro de atitude com
     PRIORIDADE DE INCLINAÇÃO (invariância ao yaw, sinais), velocidade no referencial do rumo, conversão para a ação do
     env, validação de comandos, desarmado = neutro, anti-windup;
  §2 MALHA FECHADA no `DroneRealEnv` (build ativo, SEM VENTO, semente de CALIBRAÇÃO): ganhos derivados do próprio env
     (margens de fase), hover sem deriva, degrau de velocidade amortecido, yaw de 90° sem perder altitude, a cascata
     manda no referencial do RUMO, tilt-prioridade com o yaw saturado, robustez com DR;
  §3 MUTAÇÕES que o teste TEM de apanhar: (a) o sinal do yaw trocado, (b) a compensação 1/(cosφ·cosθ) em falta, (c) a
     prioridade de inclinação perdida (o erro de yaw entra nas taxas p, q), (d) o anti-windup desligado.

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controlo_classico.py [--rapido]
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]
from lab import mjkit  # noqa: F401, I001

import numpy as np

import avaliar_classico as ac
import controlo_classico as cc

SEMENTE = ac.SEMENTES_CALIBRACAO[0]          # NUNCA as de avaliação
G = cc.G


class Checagens:
    """Acumulador de checagens: uma linha por checagem (com o detalhe medido) + resumo no fim."""

    def __init__(self, titulo: str) -> None:
        self.titulo = titulo
        self.falhas: list[str] = []
        self.n = 0
        print(f"\n=== {titulo} ===", flush=True)

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.n += 1
        if not cond:
            self.falhas.append(nome)
        print(f"        [{'OK  ' if cond else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""), flush=True)
        return bool(cond)

    def fechar(self) -> bool:
        estado = "TUDO OK" if not self.falhas else f"{len(self.falhas)}/{self.n} FALHARAM"
        print(f"--- {self.titulo}: {estado}", flush=True)
        return not self.falhas


def perto(a: float, b: float, rel: float = 1e-9, abs_: float = 1e-12) -> bool:
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


# ------------------------------------------------------------------------------------------ utilitários §1
def est_nivel(psi: float = 0.0, h: float = 1.0, vx: float = 0.0, vy: float = 0.0, vz: float = 0.0,
              x: float = 0.0, y: float = 0.0, roll: float = 0.0, pitch: float = 0.0) -> dict:
    return {"roll": roll, "pitch": pitch, "psi": psi, "h": h, "vz": vz, "vx": vx, "vy": vy, "x": x, "y": y}


def voar_sem_planta(gn: cc.GanhosCascata, est: dict, cmd: dict, segundos: float, dt: float = 0.02,
                    casc: cc.CascataClassica | None = None) -> cc.CascataClassica:
    """Corre a cascata com um `est` CONGELADO (sem planta): estuda o laço de controlo sozinho."""
    casc = casc or cc.CascataClassica(gn)
    if not casc.armado:
        casc.armar(True, est)
    for _ in range(round(segundos / dt)):
        casc.passo(est, (0.0, 0.0, 0.0), cmd, dt)
    return casc


def planta_sintetica() -> cc.PlantaLinear:
    """Planta SINTÉTICA com números redondos: as fórmulas fechadas conferem-se à mão."""
    return cc.PlantaLinear(omega_taxa=8.0, tau_motor=0.05, alfa_yaw=2.0, inercia_zz=0.5, c_yaw=0.6,
                           u_pairagem=0.6, idle=0.05, dt_decisao=0.02, u_yaw_por_taxa=None)


# ------------------------------------------------------------------------------------------ §1 fórmulas fechadas
def secao_formulas() -> bool:
    c = Checagens("§1 formulas fechadas (sem simulador)")
    p = planta_sintetica()

    # ---- ganhos derivados da planta
    gn = cc.GanhosCascata.de_planta(p, razao=4.0, razao_atitude=2.5, razao_posicao=2.5, razao_integral=2.0)
    ok = (perto(gn.k_att, 8.0 / 2.5) and perto(gn.k_vel, gn.k_att / 4.0) and perto(gn.k_pos, gn.k_vel / 2.5)
          and perto(gn.ki_vel, gn.k_vel ** 2 / 2.0))
    c.ok("ganhos: K_att = ωc/razão_atitude, K_vel = K_att/razão, K_pos = K_vel/razão_posicao, K_i = K_vel²/razão_integral",
         ok, f"K_att={gn.k_att:.4f} K_vel={gn.k_vel:.4f} K_pos={gn.k_pos:.4f} K_i={gn.ki_vel:.4f}")
    ok = (perto(gn.k_vz, 1.0 / (0.05 * 2.0)) and perto(gn.k_pz, 1.0 / (0.05 * 4.0 * 4.0)) and perto(gn.ki_vz, gn.k_vz ** 2 / 10.0)
          and perto(gn.tau_modelo_z, 0.05 + 0.5 * p.dt_decisao) and perto(gn.coletivo_max, 2.0))
    c.ok("vertical (2026-10-13): K_vz = 1/(τ_m·razão_vz) com razão_vz = 2, K_pz = 1/(τ_m·razão²) (onde estava), K_iz = K_vz²/10, "
         "modelo de seguimento τ_m + dt/2, teto do coletivo 2,0", ok,
         f"K_vz={gn.k_vz:.3f} K_pz={gn.k_pz:.3f} K_iz={gn.ki_vz:.3f} τ_z={gn.tau_modelo_z:.4f} c_max={gn.coletivo_max:g}")
    ga = cc.GanhosCascata.de_planta(p, razao_vz=4.0, razao_integral_z=4.0, tau_modelo_z=0.0, coletivo_teto=1.8)
    c.ok("vertical: a lei de ANTES continua a um argumento de distância (razão_vz = 4, K_iz = K_vz²/4, sem modelo, teto 1,8)",
         perto(ga.k_vz, 1.0 / (0.05 * 4.0)) and perto(ga.k_pz, ga.k_vz / 4.0) and perto(ga.ki_vz, ga.k_vz ** 2 / 4.0)
         and ga.tau_modelo_z == 0.0 and perto(ga.coletivo_max, 1.8) and perto(ga.k_pz, gn.k_pz),
         f"K_vz={ga.k_vz:.3f} K_pz={ga.k_pz:.3f} K_iz={ga.ki_vz:.3f}")
    g4 = cc.GanhosCascata.de_planta(p, razao=4.0, razao_atitude=4.0, razao_posicao=4.0, razao_integral=4.0)
    c.ok("razão entre laços ≈ 4 (a da pesquisa): K_att/K_vel = K_vel/K_pos = 4 e ωc/K_att = 4",
         perto(g4.k_att / g4.k_vel, 4.0) and perto(g4.k_vel / g4.k_pos, 4.0) and perto(p.omega_taxa / g4.k_att, 4.0))
    try:
        cc.GanhosCascata.de_planta(p, razao=1.0)
        rejeita = False
    except ValueError:
        rejeita = True
    c.ok("razões ≤ 1 são recusadas (ValueError)", rejeita)

    # ---- limites de inclinação
    tmax = min(math.radians(30.0), math.acos(1.3 / 1.8))
    c.ok("limite de inclinação = min(30°, acos(reserva/c_max)) e a_xy,max = g·tan(tilt)",
         perto(gn.tilt_max, tmax) and perto(G * math.tan(gn.tilt_max), G * math.tan(tmax)),
         f"tilt_max={math.degrees(gn.tilt_max):.2f}°")
    for ax, ay, az in ((9.0, 0.0, 0.0), (-4.0, 7.0, 1.0), (0.0, -20.0, 2.0)):
        nx, ny, nz, _col, sat = cc.direcao_empuxo(ax, ay, az, G, gn.tilt_max, gn.coletivo_min, gn.coletivo_max)
        incl = math.acos(nz)
        if not (sat and perto(incl, gn.tilt_max, 1e-9)):
            break
    else:
        incl = gn.tilt_max
    c.ok("direcao_empuxo corta a inclinação EXATAMENTE em tilt_max (e sinaliza a saturação)",
         bool(sat) and perto(incl, gn.tilt_max, 1e-9), f"inclinação {math.degrees(incl):.3f}° (limite {math.degrees(gn.tilt_max):.3f}°)")

    # ---- compensação 1/(cosφ·cosθ)
    rng = np.random.default_rng(1)
    pior = 0.0
    for _ in range(200):
        ax, ay = (float(v) for v in rng.uniform(-3.0, 3.0, 2))
        az = float(rng.uniform(-2.0, 2.0))
        nx, ny, nz, col, sat = cc.direcao_empuxo(ax, ay, az, G, math.radians(60.0), 0.0, 5.0)
        fx, fy, fz = col * G * nx, col * G * ny, col * G * nz        # força específica produzida
        pior = max(pior, abs(fz - (G + az)), abs(fx - ax), abs(fy - ay), abs(col - (G + az) / (G * nz)))
    c.ok("empuxo coletivo = (g + a_z)/(g·cosφ·cosθ): a componente vertical é m(g + a_z) e a horizontal m·a_xy",
         pior < 1e-9, f"pior desvio {pior:.2e} m/s²")
    nz45 = cc.direcao_empuxo(G, 0.0, 0.0, G, math.radians(60.0), 0.0, 5.0)
    c.ok("a 45° de inclinação o coletivo é 1/cos45° = √2 (pairar inclinado custa 41 % de empuxo)",
         perto(nz45[3], math.sqrt(2.0), 1e-9), f"coletivo {nz45[3]:.6f}")

    # ---- controlador raiz quadrada
    k, lim = 1.5, 0.8
    e1 = lim / (k * k)
    v_lin, v_sq = cc.raiz_quadrada(e1 * 0.999999, k, lim), cc.raiz_quadrada(e1 * 1.000001, k, lim)
    d = 1e-6
    d_lin = (cc.raiz_quadrada(e1 - d, k, lim) - cc.raiz_quadrada(e1 - 2 * d, k, lim)) / d
    d_sq = (cc.raiz_quadrada(e1 + 2 * d, k, lim) - cc.raiz_quadrada(e1 + d, k, lim)) / d
    far = 3.0
    c.ok("raiz quadrada: contínua e com derivada contínua na junção; longe v² = 2·lim·(e − lim/2k²)",
         abs(v_lin - v_sq) < 1e-5 and abs(d_lin - d_sq) < 1e-3
         and perto(cc.raiz_quadrada(far, k, lim) ** 2, 2 * lim * (far - 0.5 * lim / (k * k)), 1e-12)
         and cc.raiz_quadrada(-far, k, lim) < 0.0,
         f"salto {abs(v_lin - v_sq):.1e}, Δderivada {abs(d_lin - d_sq):.1e}")

    # ---- erro de atitude: prioridade de inclinação
    e0 = cc.erro_atitude(0.0, 0.0, 0.0, (0.0, 0.0, 1.0), 0.0)
    c.ok("erro de atitude é NULO quando a atitude é a desejada", all(abs(v) < 1e-12 for v in e0), f"{e0}")
    t = math.radians(20.0)
    ex_a = cc.erro_atitude(0.0, 0.0, 0.3, (math.sin(t), 0.0, math.cos(t)), 0.3)
    ex_b = cc.erro_atitude(0.0, 0.0, 0.3, (math.sin(t), 0.0, math.cos(t)), 0.3 + 2.0)
    c.ok("PRIORIDADE DE INCLINAÇÃO: o erro (e_x, e_y) não depende do rumo desejado (um erro de yaw de 2 rad não o muda)",
         abs(ex_a[0] - ex_b[0]) < 1e-12 and abs(ex_a[1] - ex_b[1]) < 1e-12 and abs(ex_b[2] - ex_a[2]) > 1.0,
         f"Δ(e_x,e_y)=({abs(ex_a[0] - ex_b[0]):.1e}, {abs(ex_a[1] - ex_b[1]):.1e}), γ {ex_a[2]:+.3f} → {ex_b[2]:+.3f}")
    ex = cc.erro_atitude(0.0, 0.0, 0.0, (math.sin(t), 0.0, math.cos(t)), 0.0)       # empuxo para +x ⇒ pitch +
    ey = cc.erro_atitude(0.0, 0.0, 0.0, (0.0, math.sin(t), math.cos(t)), 0.0)       # empuxo para +y ⇒ roll −
    yw = cc.erro_atitude(0.0, 0.0, 0.1, (0.0, 0.0, 1.0), 0.4)
    c.ok("sinais: empuxo para +x → q>0 (pitch↑); para +y → p<0 (roll↓); rumo desejado > rumo → γ = Δψ > 0 (anti-horário)",
         ex[1] > 0.0 and abs(ex[0]) < 1e-12 and ey[0] < 0.0 and abs(ey[1]) < 1e-12 and perto(yw[2], 0.3, 1e-9),
         f"e_y(+x)={ex[1]:+.4f} e_x(+y)={ey[0]:+.4f} γ={yw[2]:+.4f}")
    # sinal-seno: 2·sin(α/2) (inclinação de 20° → 0,3473)
    c.ok("o erro de inclinação é a parte vetorial do quaternião ×2: 2·sin(α/2)", perto(ex[1], 2.0 * math.sin(t / 2.0), 1e-9),
         f"{ex[1]:.6f} vs {2.0 * math.sin(t / 2.0):.6f}")

    # ---- velocidade no referencial do rumo
    phi, th, vbx, vby, vz = 0.05, -0.08, 0.7, -0.3, 0.4
    vhx, vhy = cc.velocidade_no_rumo(phi, th, vbx, vby, vz)
    cf, sf, ct, st = math.cos(phi), math.sin(phi), math.cos(th), math.sin(th)
    den = ct * cf
    vbz = (vz + st * vbx - ct * sf * vby) / den
    rx = np.array([[1, 0, 0], [0, cf, -sf], [0, sf, cf]])
    ry = np.array([[ct, 0, st], [0, 1, 0], [-st, 0, ct]])
    v_h = ry @ rx @ np.array([vbx, vby, vbz])
    c.ok("v no rumo = R_y(θ)·R_x(φ)·v_corpo, com v_z do observador (e v_H,z = v_z)",
         abs(vhx - v_h[0]) < 1e-12 and abs(vhy - v_h[1]) < 1e-12 and abs(v_h[2] - vz) < 1e-12,
         f"(vx,vy)=({vhx:.4f},{vhy:.4f})")

    # ---- conversão para o acelerador / a ação do env
    a = cc.cmd_para_acao(1.3, (0.4, -0.8, 2.0))
    c.ok("cmd_para_acao: a₀ = c − 1; a₁₂₃ = taxas/[2,2,1] cortadas a [-1, 1]",
         perto(a[0], 0.3) and perto(a[1], 0.2) and perto(a[2], -0.4) and a[3] == 1.0, f"{[round(v, 3) for v in a]}")
    c.ok("acelerador_de_coletivo = u_pair·√c (T ∝ u²) e é u_pair em pairagem (c = 1)",
         perto(cc.acelerador_de_coletivo(1.0, 0.63), 0.63) and perto(cc.acelerador_de_coletivo(2.0, 0.63), 0.63 * math.sqrt(2.0)))

    # ---- validação de comandos / estimativas
    erros = 0
    for cmd in ({"modo": "voo-livre"}, {"vx": float("nan")}, {"modo": "yaw_alvo"}, {"yaw_taxa": float("inf")}):
        try:
            cc.CascataClassica(gn).passo(est_nivel(), (0, 0, 0), cmd, 0.02)
        except ValueError:
            erros += 1
    c.ok("comandos inválidos (modo desconhecido, NaN, yaw_alvo sem `yaw`, inf) levantam ValueError", erros == 4, f"{erros}/4")

    # ---- desarmado = neutro
    casc = cc.CascataClassica(gn)
    n0 = casc.passo(est_nivel(), (0, 0, 0), {"vx": 1.0}, 0.02)
    casc.armar(True, est_nivel())
    casc.passo(est_nivel(), (0, 0, 0), {"vx": 1.0}, 0.02)
    casc.armar(False)
    n1 = casc.passo(est_nivel(), (0, 0, 0), {"vx": 1.0}, 0.02)
    casc.armar(True, est_nivel())
    c.ok("DESARMADO = NEUTRO: sem armar ou depois de desarmar → (coletivo 0, taxas 0) e os integradores zeram",
         n0 == (0.0, (0.0, 0.0, 0.0)) and n1 == (0.0, (0.0, 0.0, 0.0)) and casc.i_vel == [0.0, 0.0] and casc.i_z == 0.0,
         f"{n0} · {n1}")

    # ---- referencial do RUMO: cmd.vx = «frente» aponta para onde o drone aponta
    est = est_nivel(psi=math.pi / 2)
    cs = voar_sem_planta(gn.com(ref_posicao="trava"), est, {"vx": 1.0}, 1.0)
    ax, ay, _az = cs.dados["a_des"]
    c.ok("referencial do rumo: com o drone a apontar para +y (ψ = 90°), W (vx>0) acelera para +y e não para +x",
         ay > 1.0 and abs(ax) < 0.05 * abs(ay), f"a = ({ax:+.3f}, {ay:+.3f}) m/s²")
    cs = voar_sem_planta(gn, est_nivel(), {"vy": 1.0}, 1.0)
    c.ok("A (vy>0, esquerda) acelera para +y com o drone a apontar para +x", cs.dados["a_des"][1] > 1.0
         and abs(cs.dados["a_des"][0]) < 0.05, f"a = {tuple(round(v, 3) for v in cs.dados['a_des'][:2])}")
    cs = voar_sem_planta(gn, est_nivel(), {"vz": 0.7}, 1.0)
    c.ok("Q (vz>0, cima) aumenta o coletivo acima de 1 (e E diminui-o)",
         cs.dados["coletivo"] > 1.05 and voar_sem_planta(gn, est_nivel(), {"vz": -0.7}, 1.0).dados["coletivo"] < 0.95,
         f"coletivo Q={cs.dados['coletivo']:.3f}")

    # ---- yaw: sinal e limites
    cs = voar_sem_planta(gn, est_nivel(), {"yaw_taxa": 0.2}, 0.5)
    _c1, tx = cs.passo(est_nivel(), (0, 0, 0), {"yaw_taxa": 0.2}, 0.02)
    cn = voar_sem_planta(gn, est_nivel(), {"yaw_taxa": -0.2}, 0.5)
    _c2, tn = cn.passo(est_nivel(), (0, 0, 0), {"yaw_taxa": -0.2}, 0.02)
    ca = voar_sem_planta(gn, est_nivel(), {"modo": "yaw_alvo", "yaw": 1.0}, 0.5)
    _c3, ta = ca.passo(est_nivel(), (0, 0, 0), {"modo": "yaw_alvo", "yaw": 1.0}, 0.02)
    c.ok("yaw: yaw_taxa > 0 e yaw_alvo > ψ̂ dão r_sp > 0 (anti-horário); yaw_taxa < 0 dá r_sp < 0",
         tx[2] > 0.0 and tn[2] < 0.0 and ta[2] > 0.0, f"r_sp = {tx[2]:+.3f} / {tn[2]:+.3f} / {ta[2]:+.3f}")
    cs = voar_sem_planta(gn, est_nivel(), {"yaw_taxa": 9.0}, 3.0)
    c.ok("limite da taxa de yaw: yaw_taxa = 9 rad/s é cortada a taxa_yaw_max; e a aceleração a acel_yaw_max",
         perto(cs.r_ref, gn.taxa_yaw_max, 1e-9)
         and perto(abs(voar_sem_planta(gn, est_nivel(), {"yaw_taxa": 9.0}, 0.2).r_ref), gn.acel_yaw_max * 0.2, 1e-6),
         f"r_ref = {cs.r_ref:.4f} (limite {gn.taxa_yaw_max:.4f})")
    lim_ok = True
    cs = cc.CascataClassica(gn)
    cs.armar(True, est_nivel())
    for _ in range(60):
        cs_c, (p_, q_, r_) = cs.passo(est_nivel(roll=0.4, pitch=-0.4), (0, 0, 0),
                                      {"vx": 1e3, "vy": -1e3, "vz": 1e3, "yaw_taxa": 1e3}, 0.02)
        lim_ok = lim_ok and abs(p_) <= gn.taxa_rp_max + 1e-12 and abs(q_) <= gn.taxa_rp_max + 1e-12 \
            and abs(r_) <= gn.taxa_yaw_max + 1e-12 and gn.coletivo_min - 1e-12 <= cs_c <= gn.coletivo_max + 1e-12
    c.ok("limites de saída com comandos absurdos (v = 10³ m/s): taxas e coletivo dentro dos tetos", lim_ok)

    # ---- anti-windup
    saturado = gn.com(tilt_max=math.radians(3.0))
    cs = voar_sem_planta(saturado, est_nivel(), {"vx": 1.0}, 12.0)
    i_cheio = abs(cs.i_vel[0])
    cs_sem = voar_sem_planta(saturado.com(aw_ganho=0.0), est_nivel(), {"vx": 1.0}, 12.0)
    solta = voar_sem_planta(saturado, est_nivel(), {"vx": 0.0}, 1.0, casc=cs)
    a_solta = abs(solta.dados["a_des"][0])
    c.ok("anti-windup: com a inclinação SATURADA 12 s, o integral fica limitado (retro-cálculo) e, ao largar o comando, a"
         " aceleração pedida volta a ≈ 0 em 1 s",
         i_cheio < 0.6 * abs(cs_sem.i_vel[0]) and i_cheio < 1.0 and a_solta < 0.3,
         f"|I| com AW = {i_cheio:.3f} vs sem AW = {abs(cs_sem.i_vel[0]):.3f} m/s²; |a| 1 s depois de largar = {a_solta:.3f}")
    return c.fechar()


# ------------------------------------------------------------------------------------------ §2 malha fechada
def correr_cascata(T: float, cmd_fn=None, dr: bool = False, opcoes=None, seed: int = SEMENTE, cmd_mundo=None) -> dict:
    dados = ac.carregar_rl_dados()
    env = ac.criar_env(dados, dr=dr, episodio_s=T)
    ctrl = ac.ControladorCascata(estimador="melhorado", opcoes_ganhos=dict(opcoes or {}), cmd_fn=cmd_fn)
    return ac.correr(env, ctrl, seed, T, cmd_mundo=cmd_mundo)


def secao_malha_fechada(rapido: bool) -> dict:
    c = Checagens("§2 malha fechada no DroneRealEnv (build ativo, SEM VENTO, semente de calibração)")
    dados = ac.carregar_rl_dados()
    env0 = ac.criar_env(dados, dr=False, episodio_s=1.0)
    gn = cc.ganhos_de_hardware(env0)
    m = cc.margens_cascata(env0, gn)
    resultados: dict = {}

    # ---- ganhos derivados do PRÓPRIO env
    _w, _t, _l, wc = cc._malha_taxa_do_env(env0)
    ok = (perto(gn.omega_taxa, wc) and perto(gn.k_att, wc / gn.razao_atitude) and perto(gn.k_vel, gn.k_att / gn.razao_lacos)
          and perto(gn.k_pos, gn.k_vel / gn.razao_posicao) and perto(gn.k_vz, 1.0 / (env0.fc.tau_motor * 2.0))
          and perto(gn.k_arrasto, float(np.mean(env0.planta.aero.d_xy))))
    c.ok("ganhos_de_hardware(env): ωc, K_att, K_vel, K_pos, K_vz e o arrasto vêm das fórmulas aplicadas ao fc.py do env", ok,
         f"ωc={wc:.2f} rad/s K_att={gn.k_att:.2f} K_vel={gn.k_vel:.2f} K_pos={gn.k_pos:.2f} K_vz={gn.k_vz:.2f}")
    c.ok("margens de fase em cascata (resposta REAL da malha de taxa): atitude ≥ 60°, posição ≥ 60°, velocidade ≥ 45°, "
         "vertical ≥ 50°, ganho ≥ 6 dB",
         m["atitude"]["pm_graus"] >= 60.0 and m["posicao"]["pm_graus"] >= 60.0 and m["velocidade"]["pm_graus"] >= 45.0
         and m["velocidade_vertical"]["pm_graus"] >= 50.0 and min(v["gm_db"] for k, v in m.items() if k != "taxa") >= 6.0,
         " · ".join(f"{k} {v['pm_graus']:.0f}°" for k, v in m.items()))

    # ---- hover sem deriva
    T = 18.0 if rapido else 30.0
    reg = correr_cascata(T)
    h = ac.metricas_hover(reg, janela=(10.0, T))
    resultados["hover"] = h
    c.ok("hover sem deriva: ‖xy‖ RMS < 12 cm, |Δz| RMS < 5 cm, roll/pitch RMS < 0,3°, deriva de rumo < 3° e sem terminar",
         not h["terminou"] and h["xy_rms"] < 0.12 and h["dz_rms"] < 0.05 and h["roll_rms_graus"] < 0.3
         and h["pitch_rms_graus"] < 0.3 and h["deriva_rumo_graus"] < 3.0,
         f"‖xy‖ {100 * h['xy_rms']:.1f} cm · Δz {100 * h['dz_rms']:.1f} cm · roll/pitch {h['roll_rms_graus']:.2f}/"
         f"{h['pitch_rms_graus']:.2f}° · rumo {h['deriva_rumo_graus']:.2f}°")

    # ---- degrau de velocidade amortecido
    t_deg = 6.0
    regd = correr_cascata(t_deg + 9.0, cmd_mundo=lambda t: np.array([1.0, 0.0, 0.0]) if t >= t_deg else np.zeros(3))
    d = ac.metricas_degrau(regd, t_deg, np.array([1.0, 0.0, 0.0]), 8.0)
    t = regd["t"]
    s = regd["vx"][(t >= t_deg + 5.0)]
    c.ok("degrau 0 → 1 m/s: sobressinal < 1,2× (< 20 %), 10–90 % em < 1 s, sem oscilação sustentada (σ(v) < 0,06 m/s depois de "
         "5 s) e erro de regime < 8 %",
         d["sobressinal"] < 0.20 and d["subida_10_90_s"] < 1.0 and float(np.std(s)) < 0.06 and abs(d["erro_regime"]) < 0.08,
         f"sobressinal {100 * d['sobressinal']:.1f} % · subida {d['subida_10_90_s']:.2f} s · σ {np.std(s):.3f} · regime "
         f"{d['erro_regime']:+.3f} m/s")
    resultados["degrau"] = d

    # ---- yaw 90° sem perder altitude
    t_y = 6.0
    alvo = math.pi / 2
    regy = correr_cascata(t_y + 12.0, cmd_fn=lambda t: ({"modo": "yaw_alvo", "yaw": alvo} if t >= t_y else {}))
    yy = ac.metricas_yaw_degrau(regy, t_y, alvo, 12.0)
    resultados["yaw"] = yy
    c.ok("yaw 90° (modo yaw_alvo): chega a 90° ± 1° (assenta em < 9 s), sobressinal < 5 %, |Δz| < 0,2 m, sem saturar a mistura",
         not yy["terminou"] and abs(yy["erro_regime_graus"]) < 1.0 and yy["assenta_5pct_s"] < 9.0 and yy["sobressinal"] < 0.05
         and yy["dz_max"] < 0.2 and yy["frac_saturado"] < 0.01,
         f"subida {yy['subida_10_90_s']:.2f} s · assenta 5 % {yy['assenta_5pct_s']:.2f} s · sobressinal {100 * yy['sobressinal']:.2f} % · "
         f"|Δz| {100 * yy['dz_max']:.1f} cm · saturação {100 * yy['frac_saturado']:.2f} %")

    # ---- tilt-prioridade com o yaw «saturado» (comando de yaw muito acima do possível)
    def cmd_yaw_e_frente(t):
        return {"yaw_taxa": 5.0, "vx": 1.0} if t >= 6.0 else {}
    regp = correr_cascata(15.0, cmd_fn=cmd_yaw_e_frente)
    tt = regp["t"]
    janela = tt >= 11.0
    # velocidade no REFERENCIAL DO RUMO (o drone roda: a «frente» roda com ele): módulo ≈ 1 m/s
    vel = np.hypot(regp["vx"], regp["vy"])[janela]
    sat = ac._janela_sat(regp, tt >= 6.0)[0]
    c.ok("tilt-prioridade: com o yaw comandado muito além do possível (5 rad/s) o roll/pitch continua a seguir — o avanço "
         "chega a 1 m/s (± 0,2) sem perder a altitude (|Δz| < 0,2 m) nem saturar a mistura (< 1 %)",
         not regp["terminou"] and abs(float(np.mean(vel)) - 1.0) < 0.2 and float(np.abs(regp["z"][tt >= 6.0] - 1.0).max()) < 0.2
         and sat < 0.01,
         f"⟨‖v‖⟩ {np.mean(vel):.3f} m/s · |Δz| {100 * np.abs(regp['z'][tt >= 6.0] - 1.0).max():.1f} cm · saturação {100 * sat:.2f} %")
    # contra-prova (não-tautologia): SEM os limites de yaw a mistura satura e a altitude perde-se
    sem_limites = {"taxa_yaw_max": 1.0, "acel_yaw_max": 100.0, "avanco_yaw_max": 100.0, "comp_yaw_empuxo": False}
    regq = correr_cascata(15.0, cmd_fn=cmd_yaw_e_frente, opcoes=sem_limites)
    satq = ac._janela_sat(regq, regq["t"] >= 6.0)[0]
    dzq = float(np.abs(regq["z"][regq["t"] >= 6.0] - 1.0).max())
    c.ok("contra-prova: SEM os limites de yaw a mesma manobra satura a mistura (> 5 %) ou perde > 0,5 m de altitude "
         "(os limites derivados do frame é que protegem o roll/pitch)",
         satq > 0.05 or dzq > 0.5 or regq["terminou"], f"saturação {100 * satq:.1f} % · |Δz| {100 * dzq:.0f} cm")

    # ---- robustez com DR ligado (massa, inércia, kf, motores, bateria, sensores e arrasto sorteados)
    regr = correr_cascata(18.0, dr=True, seed=ac.SEMENTES_CALIBRACAO[1])
    hr = ac.metricas_hover(regr, janela=(10.0, 18.0))
    t_v = 6.0
    regv = correr_cascata(t_v + 8.0, dr=True, seed=ac.SEMENTES_CALIBRACAO[2],
                          cmd_mundo=lambda t: np.array([0.7, 0.0, 0.0]) if t >= t_v else np.zeros(3))
    dv = ac.metricas_degrau(regv, t_v, np.array([0.7, 0.0, 0.0]), 7.0)
    c.ok("robustez com DR: paira 18 s sem cair (‖xy‖ RMS < 25 cm) e segue 0,7 m/s com sobressinal < 30 % e regime < 15 %",
         not regr["terminou"] and hr["xy_rms"] < 0.25 and not regv["terminou"] and dv["sobressinal"] < 0.30
         and abs(dv["erro_regime"]) < 0.15 * 0.7,
         f"‖xy‖ {100 * hr['xy_rms']:.1f} cm · degrau: sobressinal {100 * dv['sobressinal']:.1f} % regime {dv['erro_regime']:+.3f} m/s")
    return {"ok": c.fechar(), "resultados": resultados, "ganhos": gn}


# ------------------------------------------------------------------------------------------ §3 mutações
@contextmanager
def mutacao(nome: str):
    """Aplica a mutação `nome` ao módulo da cascata (por `mock.patch`, sem tocar no ficheiro)."""
    orig_erro, orig_dir = cc.erro_atitude, cc.direcao_empuxo
    if nome == "sinal_do_yaw":
        def erro_trocado(*a, **k):
            ex, ey, gama = orig_erro(*a, **k)
            return ex, ey, -gama
        with mock.patch.object(cc, "erro_atitude", erro_trocado):
            yield
    elif nome == "sem_1_sobre_cos":
        def dir_sem_cos(ax, ay, az, g, tilt_max, c_min, c_max):
            nx, ny, nz, _col, sat = orig_dir(ax, ay, az, g, tilt_max, c_min, c_max)
            return nx, ny, nz, max(min((g + az) / g, c_max), c_min), sat        # esquece o ÷ cosφ·cosθ
        with mock.patch.object(cc, "direcao_empuxo", dir_sem_cos):
            yield
    elif nome == "sem_prioridade_inclinacao":
        def erro_acoplado(*a, **k):
            ex, ey, gama = orig_erro(*a, **k)
            return ex + 0.5 * gama, ey, gama                                    # o erro de yaw «vaza» para as taxas p, q
        with mock.patch.object(cc, "erro_atitude", erro_acoplado):
            yield
    elif nome == "sem_anti_windup":
        orig_init = cc.CascataClassica.__init__
        def init_sem_aw(self, ganhos):
            orig_init(self, ganhos.com(aw_ganho=0.0))
        with mock.patch.object(cc.CascataClassica, "__init__", init_sem_aw):
            yield
    else:
        raise ValueError(nome)


def checagens_mutaveis(rapido: bool) -> dict[str, bool]:
    """As checagens que as mutações têm de fazer falhar. Devolve {nome: passou}."""
    p = planta_sintetica()
    gn = cc.GanhosCascata.de_planta(p)
    out: dict[str, bool] = {}
    # (1) compensação 1/(cosφ·cosθ)
    pior = 0.0
    rng = np.random.default_rng(2)
    for _ in range(50):
        ax, ay, az = (float(v) for v in rng.uniform(-3.0, 3.0, 3))
        _nx, _ny, nz, col, _ = cc.direcao_empuxo(ax, ay, az, G, math.radians(60.0), 0.0, 5.0)
        pior = max(pior, abs(col * G * nz - (G + az)))
    out["compensacao_1_sobre_cos"] = pior < 1e-9
    # (2) prioridade de inclinação: p, q não dependem do erro de yaw
    def taxas_com_yaw(alvo_yaw: float):
        cs = cc.CascataClassica(gn)
        cs.armar(True, est_nivel())
        _c, tx = cs.passo(est_nivel(), (0, 0, 0), {"modo": "yaw_alvo", "yaw": alvo_yaw}, 0.02)
        for _ in range(30):
            _c, tx = cs.passo(est_nivel(), (0, 0, 0), {"modo": "yaw_alvo", "yaw": alvo_yaw}, 0.02)
        return tx
    a, b = taxas_com_yaw(0.0), taxas_com_yaw(2.5)
    out["prioridade_inclinacao"] = abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9
    # (3) anti-windup
    cs = voar_sem_planta(gn.com(tilt_max=math.radians(3.0)), est_nivel(), {"vx": 1.0}, 12.0)
    out["anti_windup"] = abs(cs.i_vel[0]) < 1.0
    # (4) sinal do yaw em malha fechada (sim): yaw_alvo = +60° ⇒ o rumo CHEGA a +60° (e não foge)
    if not rapido:
        alvo = math.radians(60.0)
        reg = correr_cascata(16.0, cmd_fn=lambda t: ({"modo": "yaw_alvo", "yaw": alvo} if t >= 6.0 else {}))
        yaw = np.unwrap(reg["yaw"])
        fim = float(np.mean(yaw[reg["t"] >= 14.0]) - np.mean(yaw[(reg["t"] >= 5.0) & (reg["t"] < 6.0)]))
        out["yaw_em_malha_fechada"] = (not reg["terminou"]) and abs(fim - alvo) < math.radians(3.0)
    return out


def secao_mutacoes(rapido: bool) -> bool:
    c = Checagens("§3 mutacoes: o teste tem de as APANHAR")
    base = checagens_mutaveis(rapido)
    c.ok("linha de base: as checagens sensíveis passam sem mutação", all(base.values()),
         " · ".join(f"{k}={v}" for k, v in base.items()))
    esperado = {"sinal_do_yaw": ("yaw_em_malha_fechada",), "sem_1_sobre_cos": ("compensacao_1_sobre_cos",),
                "sem_prioridade_inclinacao": ("prioridade_inclinacao",), "sem_anti_windup": ("anti_windup",)}
    for nome, chaves in esperado.items():
        if rapido and "yaw_em_malha_fechada" in chaves:
            continue
        with mutacao(nome):
            mut = checagens_mutaveis(rapido)
        apanhou = [k for k in chaves if not mut.get(k, True)]
        c.ok(f"MUTAÇÃO «{nome}» é apanhada ({', '.join(chaves)} falha)", bool(apanhou),
             " · ".join(f"{k}={v}" for k, v in mut.items()))
    return c.fechar()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rapido", action="store_true", help="episódios mais curtos e sem a mutação em malha fechada")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    ok1 = secao_formulas()
    r2 = secao_malha_fechada(args.rapido)
    ok3 = secao_mutacoes(args.rapido)
    ok = ok1 and r2["ok"] and ok3
    print(f"\n{'TUDO OK' if ok else 'HÁ FALHAS'} ({time.perf_counter() - t0:.0f} s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
