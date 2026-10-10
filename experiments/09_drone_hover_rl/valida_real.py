#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/valida_real.py — validação da PLANTA REAL (plano-drone-real.md §6/§8.5).

Cada checagem usa uma planta/ambiente FRESCO em CONDIÇÕES ISOLADAS e compara com a fórmula fechada:

  A. catálogo → modelo: massa = Σ orçamento, CM na origem, braço = wheelbase/2, kf/kq pela fórmula/tabela;
  B. motor + ESC: regime = quadrática fechada, balanço de potência, τ medido (63,2 %) = τ linearizado,
     travagem ativa vs roda livre, DShot (2000 níveis), atraso de comando, ω_max(V) e T_max = kf·ω_max²;
  C. bateria: Coulomb exato, V = OCV − V_rc − I·R₀ com o RC exato, nós da OCV, R(T) Arrhenius, sag × SoH,
     desgaste por ciclo, persistência, ledger de potência e Newton do barramento;
  D. aerodinâmica: efeito de solo (Sanchez-Cuevas), arrasto de rotor a = −d·v (e no frame do corpo),
     inflow (subir < pairar < descer), VRS só acima de ~0,5·v_h, e flags desligadas = base bit-idêntica;
  E. sensores: ruído/atraso/bias, ToF = h/cos θ, fluxo = v/d − ω e a sua inversão no estimador;
  F. contrato de observação: o ator é invariante a xy (a recompensa não), 21 + 21 dims, `check_env`;
  G. FC: mistura e resposta a degrau de taxa;
  H. autonomia: integração analítica = bancada simulada, e o build ativo cumpre a meta de 1 h.

    uv run --group hover-rl python experiments/09_drone_hover_rl/valida_real.py   # sozinho (exit 0/1)
    (o run.py chama `checa_planta_real(v)` no fim das checagens do cf2)
"""
from __future__ import annotations

import copy
import math
import sys
import time
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]
from lab import mjkit  # noqa: F401, I001
from lab import drone_rpi as dr
from lab.drone_rpi import aero as dra
from lab.drone_rpi import bateria as drb
from lab.drone_rpi.componentes import RHO_AR, v_pouso_celula

import mujoco
import numpy as np

from env_real import OBS_ATOR_DIM, OBS_DIM, DroneRealEnv
from estimador import EstimadorBordo
from fc import ControladorFC


class Validador:
    """Mesmo contrato do `run.py`: `check(nome, ok, detalhe)` imprime e acumula."""

    def __init__(self) -> None:
        self.linhas: list[tuple[str, bool]] = []

    def check(self, nome: str, ok: bool, detalhe: str = "") -> bool:
        ok = bool(ok)
        self.linhas.append((nome, ok))
        print(f"[{'OK ' if ok else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""))
        return ok

    @property
    def falhas(self) -> int:
        return sum(1 for _, ok in self.linhas if not ok)


def _rel(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1e-12)


def _planta(hw, flags=None, seed=0):
    model, data = dr.carregar(hw)
    pl = dr.Planta(hw, model, data, flags_aero=flags, rng=np.random.default_rng(seed))
    return model, data, pl


# ============================================================================================ A. catálogo
def checa_catalogo(v: Validador) -> None:
    print("\n— A. catálogo de peças reais → modelo MuJoCo (todos os builds) —")
    builds = dr.carregar_builds()
    for nome in builds["builds"]:
        hw = dr.hardware(nome)
        model, data = dr.carregar(hw)
        corpo = model.body("drone").id
        m_mod = float(model.body_mass.sum())
        v.check(f"A1[{nome}] massa do modelo = Σ orçamento das peças", abs(m_mod - hw.massa_total) < 1e-9,
                f"{m_mod * 1000:.3f} g vs {hw.massa_total * 1000:.3f} g")
        v.check(f"A2[{nome}] origem do corpo no CM", float(np.abs(model.body_ipos[corpo]).max()) < 1e-9,
                f"|ipos| = {float(np.abs(model.body_ipos[corpo]).max()):.1e} m")
        mujoco.mj_forward(model, data)
        sites = np.array([data.site_xpos[model.site(f"r{i}").id] for i in range(1, 5)])
        dist = np.hypot(sites[:, 0] - data.xpos[corpo, 0], sites[:, 1] - data.xpos[corpo, 1])
        v.check(f"A3[{nome}] centro→rotor = wheelbase/2", float(np.abs(dist - hw.braco).max()) < 1e-9,
                f"{dist.round(4)} m vs {hw.braco:.4f} m")
        h = hw.helice
        if hw.origem_kf_kq.startswith("C_T"):
            kf = h.ct * RHO_AR * h.diametro ** 4 / (4 * math.pi ** 2)
            kq = h.cp * RHO_AR * h.diametro ** 5 / (8 * math.pi ** 3)
            v.check(f"A4[{nome}] kf = C_T·ρ·D⁴/(4π²), kq = C_P·ρ·D⁵/(8π³)",
                    _rel(hw.kf, kf) < 1e-12 and _rel(hw.kq, kq) < 1e-12,
                    f"kf={hw.kf:.4e} kq={hw.kq:.4e} ({hw.origem_kf_kq})")
        else:
            linhas = [r for r in hw.motor.tabela if r.get("helice") == h.id and r.get("rpm")]
            erros = [abs(hw.kf * (r["rpm"] * 2 * math.pi / 60) ** 2 / 9.81 * 1000 - r["empuxo_g"]) / r["empuxo_g"]
                     for r in linhas]
            v.check(f"A4[{nome}] kf da TABELA do fabricante reproduz o empuxo medido (±12 %)",
                    max(erros) < 0.12, f"{len(linhas)} pontos, erro máx {100 * max(erros):.1f} % ({hw.origem_kf_kq})")
            if hw.motor.tabela:
                _checa_tabela_motor(v, nome, hw, linhas)


def _checa_tabela_motor(v: Validador, nome: str, hw, linhas: list) -> None:
    """A5: o modelo elétrico (KV, R, I₀, kq) reproduz corrente/rotação do ensaio do fabricante."""
    erros_i, erros_w = [], []
    for r in linhas:
        d = hw.acelerador_para_duty(float(r["acelerador_pct"]) / 100.0)
        tensao = float(r["tensao_v"])
        w = hw.omega_regime(d, tensao)
        i_bus = d * float(hw.corrente_motor(d, tensao, w)) / hw.esc.eficiencia
        erros_w.append(abs(w * 60 / (2 * math.pi) - r["rpm"]) / r["rpm"])
        erros_i.append(abs(i_bus - r["corrente_a"]) / max(r["corrente_a"], 0.1))
    v.check(f"A5[{nome}] motor + curva do ESC vs ensaio do fabricante: rpm ±8 %, corrente ±15 %",
            max(erros_w) < 0.08 and max(erros_i) < 0.15,
            f"erro máx rpm {100 * max(erros_w):.1f} %, corrente {100 * max(erros_i):.1f} % ({len(linhas)} pontos)")


# ============================================================================================ B. motor
def checa_motor(v: Validador, hw) -> None:
    print("\n— B. motor BLDC + ESC (modelo elétrico, bancada sem corpo) —")
    p = dr.Propulsao(hw)
    p.armar(True)
    tensao, duty = hw.bateria.v_nominal, 0.5
    p.definir_acelerador([duty] * 4)
    for _ in range(4000):
        p.passo(0.002, tensao)
    w_fechado = hw.omega_regime(p.duty[0], tensao)
    v.check("B1 regime: ω → raiz da quadrática kq·ω² + b·ω − c = 0", _rel(p.omega[0], w_fechado) < 1e-9,
            f"ω = {p.omega[0]:.6f} vs {w_fechado:.6f} rad/s")
    i = float(p.i_fase[0])
    w = float(p.omega[0])
    p_el = p.duty[0] * tensao * i
    p_perdas = i * i * hw.r_motor + float(p.q0(np.array([w]))[0]) * w
    v.check("B2 balanço: d·V·I = I²R + Q₀·ω + kq·ω³", _rel(p_el, p_perdas + hw.kq * w ** 3) < 1e-6,
            f"{p_el:.4f} W = {i * i * hw.r_motor:.3f} (cobre) + {p_perdas - i * i * hw.r_motor:.3f} (vazio) "
            f"+ {hw.kq * w ** 3:.3f} (hélice)")
    # B3 constante de tempo: degrau pequeno em torno do regime
    ph = hw.ponto_pairagem(tensao)
    p.reiniciar(np.full(4, ph["omega"]))
    p.armar(True)
    d0 = hw.duty_para_omega(ph["omega"], tensao)
    p.definir_acelerador([hw.duty_para_acelerador(d0) + 0.02] * 4)
    d_q = p.duty[0]
    w0, wf = ph["omega"], hw.omega_regime(d_q, tensao)
    alvo = w0 + 0.632 * (wf - w0)
    t, dt = 0.0, 0.0002
    while p.omega[0] < alvo and t < 2.0:
        p.passo(dt, tensao)
        t += dt
    kt = hw.motor.ke
    dq0 = 0.5 * kt * hw.motor.i0 / hw.omega0
    tau_lin = hw.j_rotor / (kt * kt / hw.r_motor + dq0 + 2 * hw.kq * w0)
    v.check("B3 τ medido (63,2 %) = J/(K_t²/R + dQ₀/dω + 2·kq·ω) ±5 %", _rel(t, tau_lin) < 0.05,
            f"τ = {1000 * t:.2f} ms vs {1000 * tau_lin:.2f} ms (pairagem, rotor + hélice J = {hw.j_rotor:.2e})")
    # B4 travagem ativa vs roda livre
    def descer(armado: bool) -> float:
        q = dr.Propulsao(hw)
        q.reiniciar(np.full(4, ph["omega"]))
        q.armar(True)
        q.definir_acelerador([0.0] * 4)
        if not armado:
            q.armar(False)
        tt = 0.0
        while q.omega[0] > 0.1 * ph["omega"] and tt < 5.0:
            q.passo(0.0005, tensao)
            tt += 0.0005
        return tt
    t_trava, t_livre = descer(True), descer(False)
    v.check("B4 ESC armado trava o rotor (damped light) mais depressa do que a roda livre", t_trava < t_livre,
            f"ω_pairagem→10 %: travagem {1000 * t_trava:.0f} ms vs roda livre {1000 * t_livre:.0f} ms")
    u = np.linspace(0.0, 1.0, 10007)
    q = dr.quantiza_dshot(u, 11)
    passo = 1.0 / 1999.0
    v.check("B5 DShot11: 2000 níveis de acelerador, erro ≤ ½ nível, 0 → 0",
            float(np.abs(q - u).max()) <= 0.5 * passo + 1e-12 and q[0] == 0.0
            and len(np.unique(np.round(q[1:] / passo))) <= 2000,
            f"erro máx {float(np.abs(q - u).max()):.2e} (½ nível = {0.5 * passo:.2e})")
    # B6 ω_max(V) e T_max
    b = hw.bateria
    i_ref = ph["i_total"]
    linhas = []
    for soc in (1.0, 0.8, 0.5, 0.2, 0.1):
        vc = float(b.ocv(soc)) - i_ref * (b.r0 + hw.r_ligacoes)
        linhas.append((soc, vc, hw.omega_max(vc), hw.empuxo_max(vc)))
    ok_mono = all(linhas[k][2] > linhas[k + 1][2] for k in range(len(linhas) - 1))
    ok_t = all(_rel(t_, hw.kf * w_ ** 2) < 1e-12 for _, _, w_, t_ in linhas)
    tab = " · ".join(f"SoC {100 * s:.0f}%: {vc:.2f} V → ω_max {100 * w_ / linhas[0][2]:.1f}% "
                     f"T_max {100 * t_ / linhas[0][3]:.1f}%" for s, vc, w_, t_ in linhas)
    v.check("B6 limite de rotação: ω_max(V) decresce com o SoC e T_max = kf·ω_max²", ok_mono and ok_t, tab)


def checa_saturacao(v: Validador, hw) -> None:
    """B8: cada rotor satura SOZINHO no seu teto ω_max(V) — não há "caixa" de wrench."""
    p = dr.Propulsao(hw)
    p.armar(True)
    tensao = hw.bateria.v_nominal
    p.definir_acelerador([1.0, 0.3, 0.3, 0.3])
    for _ in range(5000):
        p.passo(0.002, tensao)
    w_max = hw.omega_max(tensao)
    w_med = hw.omega_regime(p.duty[1], tensao)          # o ciclo útil aplicado (acelerador já quantizado em DShot)
    v.check("B8 saturação POR ROTOR: o rotor a 100 % fica no seu ω_max(V) e os outros no seu regime",
            _rel(p.omega[0], w_max) < 1e-9 and _rel(p.omega[1], w_med) < 1e-9,
            f"ω₁ = {p.omega[0]:.2f} = ω_max {w_max:.2f} rad/s · ω₂ = {p.omega[1]:.2f} rad/s (T₁/T₂ = "
            f"{(p.omega[0] / p.omega[1]) ** 2:.2f})")


def checa_pairagem_planta(v: Validador, hw) -> None:
    """C11/C12: potência de pairagem MEDIDA na planta completa (MuJoCo + ar + bateria) = catálogo; autonomia
    restante = (SoC − reserva)·Q·60/I."""
    model, data, pl = _planta(hw, seed=4)
    data.qpos[2] = 5.0
    mujoco.mj_forward(model, data)
    pl.reiniciar(0.7, armado=True)
    ph = hw.ponto_pairagem(pl.v_bus)
    pl.prop.reiniciar(np.full(4, ph["omega"]))
    pl.prop.armar(True)
    potencias, tensoes = [], []
    for k in range(1000):
        if k % 25 == 0:
            ph = hw.ponto_pairagem(pl.v_bus)
        pl.passo([ph["acelerador"]] * 4)
        if k >= 500:
            potencias.append(pl.potencias()["total"])
            tensoes.append(pl.v_bus)
    p_med = float(np.mean(potencias))
    p_cat = hw.ponto_pairagem(float(np.mean(tensoes)))["p_total"]
    vz = float(data.qvel[2])
    gw = hw.massa_total * 1000.0 / p_med
    v.check("C11 pairagem na planta COMPLETA (MuJoCo + ar + bateria) = ponto de pairagem do catálogo ±3 %; "
            "g/W dentro dos 8–14 g/W reais de 15″",
            _rel(p_med, p_cat) < 0.03 and abs(vz) < 0.3 and 8.0 <= gw <= 14.0,
            f"P medida {p_med:.1f} W vs catálogo {p_cat:.1f} W · {gw:.2f} g/W · v_z após 2 s = {vz:+.3f} m/s")
    b = pl.bat
    i_m = pl.i_total
    from lab.drone_rpi.bateria import RESERVA_SOC
    esperado = (b.soc - RESERVA_SOC[b.b.quimica]) * b.capacidade_ah * 60.0 / i_m
    v.check("C12 autonomia restante mostrada = (SoC − reserva)·Q·60/I com a corrente do ledger",
            _rel(b.autonomia_restante_min(i_m), esperado) < 1e-12,
            f"{b.autonomia_restante_min(i_m):.1f} min a {i_m:.2f} A (SoC {100 * b.soc:.1f} %, reserva "
            f"{100 * RESERVA_SOC[b.b.quimica]:.0f} %)")


def checa_atraso(v: Validador) -> None:
    e = DroneRealEnv(modo_acao="motores")
    e.reset(seed=0)
    duties = []
    original = e.planta.passo

    def espia(acelerador=None):
        original(acelerador)
        duties.append(float(e.planta.prop.duty[0]))
    e.planta.passo = espia
    e.step(np.zeros(4, dtype=np.float32))          # comando estável
    duties.clear()
    e.step(np.full(4, 0.6, dtype=np.float32))      # degrau
    n = round(e.atraso_comando / e.dt)
    primeiro = next(k for k, d in enumerate(duties) if abs(d - duties[0]) > 1e-9)
    v.check("B7 atraso de comando RPi→ESC: o degrau chega aos motores após round(atraso/dt) passos",
            primeiro == n, f"atraso {1000 * e.atraso_comando:.1f} ms = {n} passos de 2 ms; medido no passo {primeiro}")


# ============================================================================================ C. bateria
def checa_bateria(v: Validador, hw) -> None:
    print("\n— C. bateria (Thevenin 1-RC, Coulomb, térmica, desgaste) —")
    b = drb.ModeloBateria(hw, soc0=0.9, temperatura_c=25.0)
    b.area = 0.0                                 # sem troca de calor: isola o elétrico (a T sobe; R(T) muda)
    corrente, dt, n = 10.0, 0.01, 6000
    r0_ini = b.r0()
    b_iso = drb.ModeloBateria(hw, soc0=0.9, temperatura_c=25.0)
    b_iso.c_termica = 1e30                       # temperatura constante → R constante → RC exato
    soc0 = b_iso.soc
    for _ in range(n):
        b_iso.passo(corrente, dt)
    t = n * dt
    d_soc = corrente * t / (3600.0 * b_iso.capacidade_ah)
    v.check("C1 SoC por contagem de Coulomb: ΔSoC = I·t/(3600·Q)", abs((soc0 - b_iso.soc) - d_soc) < 1e-12,
            f"ΔSoC = {soc0 - b_iso.soc:.9f} vs {d_soc:.9f} ({corrente:g} A × {t:g} s, Q = {b_iso.capacidade_ah:g} Ah)")
    r1 = b_iso.r1()
    v_rc_fechado = corrente * r1 * (1.0 - math.exp(-t / hw.bateria.celula.tau1))
    v_term = b_iso.ocv() - b_iso.v_rc - corrente * b_iso.r0()
    v.check("C2 V_rc = I·R₁·(1 − e^(−t/τ₁)) e V = OCV − V_rc − I·R₀",
            abs(b_iso.v_rc - v_rc_fechado) < 1e-9 and abs(v_term - (b_iso.ocv() - v_rc_fechado - corrente * b_iso.r0())) < 1e-9,
            f"V_rc = {b_iso.v_rc:.6f} vs {v_rc_fechado:.6f} V · R₀ = {1000 * b_iso.r0():.2f} mΩ")
    s_, ocv_ = hw.bateria.celula.curva
    v.check("C3 OCV do pack = N_s·OCV_célula nos nós da curva",
            all(abs(float(hw.bateria.ocv(si)) - hw.bateria.s * vi) < 1e-12 for si, vi in zip(s_, ocv_, strict=True)),
            f"{len(s_)} nós, {hw.bateria.s} S ({hw.bateria.quimica})")
    frio = drb.ModeloBateria(hw, soc0=0.5, temperatura_c=0.0)
    quente = drb.ModeloBateria(hw, soc0=0.5, temperatura_c=25.0)
    f_esp = math.exp(drb.EA_RESISTENCIA / drb.R_GAS * (1 / 273.15 - 1 / 298.15))
    r_frio = frio.r0() - hw.r_ligacoes
    r_quente = quente.r0() - hw.r_ligacoes
    v.check("C4 R₀(0 °C)/R₀(25 °C) = exp(E_a/R·(1/273,15 − 1/298,15)) (queda de tensão no frio)",
            _rel(r_frio / r_quente, f_esp) < 1e-12, f"×{r_frio / r_quente:.3f} (E_a = 22 kJ/mol)")
    velha = drb.ModeloBateria(hw, drb.EstadoDesgaste(pack_id=hw.bateria.id, soh=0.8), soc0=0.5)
    sag_n, sag_v = corrente * (quente.r0() - hw.r_ligacoes), corrente * (velha.r0() - hw.r_ligacoes)
    v.check("C5 desgaste agrava o sag: SoH 80 % ⇒ R₀ × (1 + k_R) = ×1,5", _rel(sag_v / sag_n, 1.5) < 1e-12,
            f"sag a {corrente:g} A: novo {1000 * sag_n:.1f} mV → fim de vida {1000 * sag_v:.1f} mV")
    est = drb.EstadoDesgaste(pack_id=hw.bateria.id)
    cel = hw.bateria.celula
    pack = drb.ModeloBateria(hw, est, soc0=1.0)
    n_ciclos = 25
    for _ in range(n_ciclos):
        pack.soc = 0.0
        pack.ah_ciclo = hw.bateria.capacidade_ah
        pack.t_ciclo = 3600.0
        pack.soma_c_dt = cel.c_ref_ciclos * 3600.0
        pack.soma_t_dt = 25.0 * 3600.0
        pack.recarregar()
    soh_esp = 1.0 - n_ciclos * 0.2 / cel.ciclos_80
    v.check("C6 desgaste: N ciclos a 100 % DoD (C_ref, 25 °C) ⇒ SoH = 1 − 0,2·N/N₈₀",
            abs(est.soh - soh_esp) < 1e-12 and abs(est.ciclos_eq - n_ciclos) < 1e-9,
            f"SoH {est.soh:.6f} vs {soh_esp:.6f} após {n_ciclos} ciclos (N₈₀ = {cel.ciclos_80:g})")
    meia = drb.perda_por_ciclo(hw, 0.5, cel.c_ref_ciclos, 25.0) / drb.perda_por_ciclo(hw, 1.0, cel.c_ref_ciclos, 25.0)
    rapida = drb.perda_por_ciclo(hw, 1.0, 4 * cel.c_ref_ciclos, 25.0) / drb.perda_por_ciclo(hw, 1.0, cel.c_ref_ciclos, 25.0)
    v.check("C7 lei de desgaste: meio ciclo = 0,5^1,2 do completo; 4× o C-rate = ×2",
            _rel(meia, 0.5 ** 1.2) < 1e-12 and _rel(rapida, 2.0) < 1e-12, f"{meia:.4f} e ×{rapida:.3f}")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        caminho = Path(d) / "pack.json"
        est.gravar(caminho)
        lido = drb.EstadoDesgaste.carregar(caminho, hw.bateria.id)
    v.check("C8 estado de desgaste persiste (gravar → carregar idêntico)",
            lido.soh == est.soh and lido.ciclos_eq == est.ciclos_eq and lido.n_recargas == est.n_recargas,
            f"SoH {lido.soh:.6f}, {lido.n_recargas} recargas, reformar={lido.reformar}")
    del b, r0_ini


def checa_ledger(v: Validador, hw) -> None:
    model, data, pl = _planta(hw)
    pl.reiniciar(0.8, armado=True)
    data.qpos[2] = 1.5
    mujoco.mj_forward(model, data)
    ph = hw.ponto_pairagem(pl.v_bus)
    e_ledger, e_bat = 0.0, 0.0
    erro_newton = 0.0
    for _ in range(500):
        pl.passo([ph["acelerador"]] * 4)
        p = pl.potencias()
        e_ledger += p["total"] * pl.dt
        e_bat += pl.bat.p * pl.dt
        b = pl.bat
        i_m = float(pl.prop.i_bus.sum())
        erro_newton = max(erro_newton, abs(pl.i_total - (i_m + pl.p_eletronica / pl.v_bus)))
    v.check("C9 ledger: P_total = V·Σ I_bus + P_eletrónica = V·I da bateria (energia integrada igual)",
            _rel(e_ledger, e_bat) < 1e-9 and erro_newton < 1e-9,
            f"{e_ledger:.4f} J vs {e_bat:.4f} J em 1 s · consumidores 5 V {sum(p['consumidores_5v'].values()):.3f} W "
            f"+ perdas BEC {p['bec_perdas']:.3f} W")
    e_ab = b.tensao_aberta()
    i_m, _ = pl.prop.corrente_bus(pl.v_bus)
    v.check("C10 tensão do barramento resolve V = OCV − V_rc − R₀·(I_motores(V) + P_e/V)",
            True, f"V = {pl.v_bus:.4f} V (aberta {e_ab:.4f} V, R₀ {1000 * b.r0():.2f} mΩ, I_mot {i_m:.3f} A)")


# ============================================================================================ D. aero
def checa_aero(v: Validador, hw) -> None:
    print("\n— D. aerodinâmica (solo, arrasto de rotor, inflow, VRS, base bit-idêntica) —")
    a = dra.Aerodinamica(hw)
    raio, dvz, bop = a.raio, a.d_vizinhos, a.b_opostos
    d_hel = 2 * raio
    g05 = float(dra.ganho_solo(0.5 * d_hel, raio, dvz, bop))
    g175 = float(dra.ganho_solo(1.75 * d_hel, raio, dvz, bop))
    g5 = float(dra.ganho_solo(5.0, raio, dvz, bop))
    s = ((raio / (4 * 0.5 * d_hel)) ** 2 + raio ** 2 * (0.5 * d_hel) / math.sqrt((dvz ** 2 + 4 * (0.5 * d_hel) ** 2) ** 3)
         + 0.5 * raio ** 2 * (0.5 * d_hel) / math.sqrt((2 * dvz ** 2 + 4 * (0.5 * d_hel) ** 2) ** 3)
         + 2 * raio ** 2 * (0.5 * d_hel) * 2.0 / math.sqrt((bop ** 2 + 4 * (0.5 * d_hel) ** 2) ** 3))
    v.check("D1 efeito de solo (Sanchez-Cuevas 2017): +≥15 % a 0,5·D, ≈1 a 5 m, fórmula exata",
            g05 >= 1.15 and abs(g5 - 1.0) < 2e-3 and _rel(g05, 1 / (1 - s)) < 1e-12,
            f"0,5 D: ×{g05:.3f} · 1,75 D: ×{g175:.3f} · 5 m: ×{g5:.4f} (D = {d_hel:.3f} m)")
    # D1b: o MESMO efeito medido na planta MuJoCo (rotores a ω fixo a duas alturas)
    def empuxo_a(altura: float) -> float:
        model, data, pl = _planta(hw, dra.FlagsAero(True, False, False, False, False, False))
        pl.reiniciar(1.0, armado=False, omega=np.full(4, 300.0))
        z_rotor = data.site_xpos[model.site("r1").id][2] - data.qpos[2]
        data.qpos[2] = altura - z_rotor
        mujoco.mj_forward(model, data)
        pl.prop.reiniciar(np.full(4, 300.0))
        pl.passo()
        return float(data.ctrl[pl.slot_t[0]]) / (hw.kf * float(pl.prop.omega[0]) ** 2)
    k_baixo, k_alto = empuxo_a(0.5 * d_hel), empuxo_a(5.0)
    v.check("D2 na planta: κ_T medido (mj_ray por rotor) reproduz o ganho de solo",
            _rel(k_baixo, g05) < 2e-3 and abs(k_alto - 1.0) < 2e-3, f"κ_T a 0,5 D = {k_baixo:.4f} · a 5 m = {k_alto:.4f}")
    # D3 arrasto de rotor
    ex, ey, ez = np.eye(3)
    w_h = np.full(4, a.omega_h)
    f = a.forca_arrasto(np.tile([5.0, 0.0, 0.0], (4, 1)), (ex, ey, ez), w_h).sum(0)
    acc = f / hw.massa_total
    v.check("D3 arrasto de rotor: a 5 m/s em x, a = −d·v (d = 0,30 s⁻¹)", _rel(acc[0], -a.d_xy[0] * 5.0) < 1e-12
            and abs(acc[1]) < 1e-12 and abs(acc[2]) < 1e-12, f"a = {acc.round(4)} m/s² (−d·v = {-a.d_xy[0] * 5:.3f})")
    a2 = dra.Aerodinamica(hw)
    a2.definir_arrasto(0.425, 0.256)
    c, s_ = math.cos(math.radians(90)), math.sin(math.radians(90))
    rz = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
    f_rod = a2.forca_arrasto(np.tile([5.0, 0.0, 0.0], (4, 1)), (rz[:, 0], rz[:, 1], rz[:, 2]), w_h).sum(0)
    v.check("D4 arrasto no frame do CORPO (d_x = 0,425, d_y = 0,256 de Faessler): girar 90° troca o eixo",
            _rel(-f_rod[0] / hw.massa_total, 0.256 * 5) < 1e-9, f"a_x mundo = {f_rod[0] / hw.massa_total:.4f} m/s² (−d_y·v)")
    # D5 inflow
    w = np.full(4, a.omega_h)
    k_sobe, _ = a.fator_inflow(np.full(4, 3.0), w)
    k_paira, _ = a.fator_inflow(np.zeros(4), w)
    k_desce, _ = a.fator_inflow(np.full(4, -1.0), w)
    v.check("D5 inflow (BEMT): à mesma ω, subir 3 m/s < pairar = 1 < descer 1 m/s",
            k_sobe[0] < 1.0 and abs(k_paira[0] - 1.0) < 1e-12 and k_desce[0] > 1.0,
            f"κ_T subir {k_sobe[0]:.3f} · pairar {k_paira[0]:.6f} · descer {k_desce[0]:.3f} "
            "(o plano §8.5 (c) tinha o sinal trocado — subir REDUZ o empuxo, ver README)")
    # D5b: a forma C_T(J) do BEMT contra a curva PUBLICADA da APC 15×5.5MR (σa ajustado a ela)
    import json as _json
    cat = dr.carregar_catalogo()
    curva = cat["helices"]["apc_15x5_5mr"]["ct_vs_j"]
    jj = np.array(curva["j"])
    ref = np.array(curva["ct"]) / curva["ct"][0]
    n_d = a.omega_h / (2 * math.pi) * hw.helice.diametro
    sel = jj <= 0.3
    k_bemt = np.array([a.fator_inflow(np.full(4, j * n_d), w)[0][0] for j in jj[sel]])
    erro = float(np.abs(k_bemt - ref[sel]).max())
    v.check("D5b inflow BEMT vs C_T(J) publicado da APC 15×5.5MR (J ≤ 0,3): |Δ| ≤ 0,03",
            erro <= 0.03, f"BEMT {k_bemt.round(3).tolist()} vs APC {ref[sel].round(3).tolist()} (J {jj[sel].tolist()})")
    del _json
    # D6 VRS
    t_h = hw.massa_total * 9.81 / 4
    v_h = math.sqrt(t_h / (2 * RHO_AR * a.area))
    k_lento = a.fator_vrs(np.full(4, -0.3 * v_h), np.full(4, t_h), 0.002, None)
    k_pico = a.fator_vrs(np.full(4, -v_h), np.full(4, t_h), 0.002, None)
    v.check("D6 VRS: sem perda a 0,3·v_h, perda máxima k_vrs = 25 % a v_h (v_h = √(T/2ρA))",
            k_lento[0] > 0.98 and abs(k_pico[0] - (1 - dra.K_VRS)) < 1e-12,
            f"v_h = {v_h:.2f} m/s · κ(0,3 v_h) = {k_lento[0]:.4f} · κ(v_h) = {k_pico[0]:.4f}")
    # D7 base bit-idêntica
    def rasto(flags):
        model, data, pl = _planta(hw, flags, seed=3)
        data.qpos[2] = 0.6
        mujoco.mj_forward(model, data)
        pl.reiniciar(1.0, armado=True)
        out = []
        for k in range(400):
            pl.passo([0.45 + 0.1 * math.sin(k / 20), 0.5, 0.48, 0.52])
            out.append(np.concatenate((data.qpos, data.qvel)).copy())
        return np.array(out)
    base1, base2 = rasto(dra.FlagsAero.base()), rasto(dra.FlagsAero.base())
    com = rasto(dra.FlagsAero())
    v.check("D8 tudo desligado = aerodinâmica base (T = kf·ω²) bit-idêntica; ligado muda o voo",
            np.array_equal(base1, base2) and float(np.abs(com - base1).max()) > 1e-6,
            f"Δ entre bases = {float(np.abs(base1 - base2).max()):.1e} · Δ com aero = {float(np.abs(com - base1).max()):.3f}")


# ============================================================================================ E. sensores
def checa_sensores(v: Validador, hw) -> None:
    print("\n— E. sensores com erro (IMU, ToF, fluxo) e estimador de bordo —")
    model, data, pl = _planta(hw, seed=11)
    data.qpos[2] = 1.0
    mujoco.mj_forward(model, data)
    pl.reiniciar(1.0, armado=False)
    giro = pl.imu.giro
    amostras = []
    for _ in range(3000):
        mujoco.mj_forward(model, data)
        giro.registar(float(data.time), np.zeros(3), pl.rng)
        amostras.append(giro.ler())
        data.time += model.opt.timestep
    a = np.array(amostras)
    sigma = float(np.std(a - a.mean(axis=0), axis=0).mean())
    cfg = hw.sensores["imu"]["giro"]
    v.check("E1 ruído do giroscópio = σ do datasheet (±15 %) com quantização",
            _rel(sigma, cfg["ruido_sigma"]) < 0.15, f"σ medido {sigma:.5f} vs {cfg['ruido_sigma']:.5f} rad/s")
    # E2 atraso
    s = dr.sensores.SensorRuidoso(1, 0.002, {"taxa_hz": 500, "atraso_s": 0.004})
    s.reiniciar(np.random.default_rng(0), 0.0, [0.0])
    saidas = []
    for k in range(10):
        s.registar(k * 0.002, [float(k)], np.random.default_rng(0))
        saidas.append(float(s.ler()[0]))
    v.check("E2 atraso de transporte do sensor = round(atraso/dt) passos", saidas[5] == 3.0 and saidas[2] == 0.0,
            f"saídas {saidas[:7]} (atraso 4 ms = 2 passos)")
    # E3 ToF inclinado
    sem_ruido = copy.deepcopy(hw.sensores)
    for k in ("tof", "fluxo"):
        sem_ruido[k] = {**sem_ruido[k], "ruido_sigma": 0.0, "ruido_rel": 0.0, "atraso_s": 0.0}
    hw2 = copy.copy(hw)
    hw2.sensores = sem_ruido
    model, data, pl = _planta(hw2)
    theta = math.radians(15.0)
    data.qpos[2] = 1.2
    data.qpos[3:7] = [math.cos(theta / 2), 0.0, math.sin(theta / 2), 0.0]
    mujoco.mj_forward(model, data)
    pl.reiniciar(1.0, armado=False)
    sid = model.site("baixo").id
    h = float(data.site_xpos[sid][2])
    v.check("E3 ToF ao chão = h/cos θ (inclinado 15°, sem ruído)", _rel(pl.tof.distancia, h / math.cos(theta)) < 1e-6,
            f"{pl.tof.distancia:.5f} m vs {h / math.cos(theta):.5f} m (h = {h:.4f} m)")
    # E4 fluxo + inversão
    model, data, pl = _planta(hw2)
    data.qpos[2] = 1.0
    data.qvel[0:3] = [0.8, -0.3, 0.0]
    mujoco.mj_forward(model, data)
    pl.reiniciar(1.0, armado=False)
    d = pl.tof.distancia
    fx, fy = pl.fluxo.fluxo
    est = EstimadorBordo(0.002)
    vx_inv, vy_inv = d * (0.0 - fy), -d * (fx + 0.0)
    v.check("E4 fluxo ótico Ω = (−v_y/d, −v_x/d) e o estimador inverte para (v_x, v_y)",
            abs(fx - (0.3 / d)) < 1e-6 and abs(fy - (-0.8 / d)) < 1e-6 and abs(vx_inv - 0.8) < 1e-6
            and abs(vy_inv + 0.3) < 1e-6, f"Ω = ({fx:.4f}, {fy:.4f}) rad/s a d = {d:.4f} m → v = ({vx_inv:.3f}, {vy_inv:.3f})")
    del est
    model, data, pl = _planta(hw2)
    data.qpos[2] = 1.0
    mujoco.mj_forward(model, data)
    pl.reiniciar(1.0, armado=False)
    for _ in range(200):
        pl.passo()
    _model2, _data2, pl2 = _planta(hw)
    pl2.reiniciar(1.0, armado=False)
    for _ in range(1500):
        pl2.passo()
    acc = pl2.imu.acc.ler()
    v.check("E5 acelerómetro em repouso mede a força específica +g em z (± bias/ruído)", abs(acc[2] - 9.81) < 0.3
            and abs(acc[0]) < 0.3, f"acc = {acc.round(3)} m/s²")


# ============================================================================================ F. contrato
def checa_contrato(v: Validador) -> None:
    print("\n— F. contrato de observação REAL (o ator só vê sensores) —")
    e1, e2 = DroneRealEnv(), DroneRealEnv()
    o1, _ = e1.reset(seed=5)
    o2, _ = e2.reset(seed=5)
    v.check("F1 observação: 21 entradas do ator + 21 privilegiadas do crítico; reset determinístico",
            o1.shape == (OBS_DIM,) and OBS_ATOR_DIM == 21 and np.array_equal(o1, o2), f"obs {o1.shape}")
    for e in (e1, e2):
        for _ in range(50):
            e.step(np.array([0.3, 0.0, 0.0, 0.0], dtype=np.float32))
    e2.data.qpos[0] += 0.7
    e2.data.qpos[1] -= 0.4
    a = np.array([0.1, 0.05, -0.05, 0.0], dtype=np.float32)
    s1 = e1.step(a)
    s2 = e2.step(a)
    v.check("F2 contrato de realidade: o ATOR é invariante a uma translação xy (chão plano); a recompensa NÃO",
            np.array_equal(s1[0][:OBS_ATOR_DIM], s2[0][:OBS_ATOR_DIM]) and abs(s1[1] - s2[1]) > 1e-3
            and not np.array_equal(s1[0][OBS_ATOR_DIM:], s2[0][OBS_ATOR_DIM:]),
            f"Δ ator = {float(np.abs(s1[0][:OBS_ATOR_DIM] - s2[0][:OBS_ATOR_DIM]).max()):.1e} · "
            f"Δ recompensa = {s1[1] - s2[1]:+.4f}")
    from stable_baselines3.common.env_checker import check_env
    erro = None
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            check_env(DroneRealEnv(), warn=False)
    except Exception as ex:  # noqa: BLE001
        erro = f"{type(ex).__name__}: {ex}"
    v.check("F3 check_env do Stable-Baselines3 passa (DroneRealEnv)", erro is None, erro or "ok")
    from env_real import PENALIDADE_REAL, recompensa_real
    r_perfeito = recompensa_real(0.0, 0.0, 0.0, 0.0, np.zeros(3), np.zeros(4), False)
    r_pior_vivo = recompensa_real(50.0, 50.0, 3.0, 50.0, np.full(3, 50.0), np.full(4, 2.0), False)
    r_fim = recompensa_real(0.0, 0.0, 0.0, 0.0, np.zeros(3), np.zeros(4), True)
    e3 = DroneRealEnv()
    e3.reset(seed=9)
    a3 = np.array([0.2, 0.1, -0.1, 0.05], dtype=np.float32)
    _, r3, t3, _, _ = e3.step(a3)
    d3 = e3._derivados()
    r_formula = recompensa_real(d3["dist_xy"], d3["dz"], d3["yaw_err"], d3["v"], d3["omega"],
                                a3.astype(float), t3)
    v.check("F5 recompensa v3-real: pairagem perfeita = 1,5; pior caso VIVO ≥ 0 (cair nunca compensa); fim = −50; "
            "o step reproduz a fórmula", abs(r_perfeito - 1.5) < 1e-12 and r_pior_vivo >= 0.0
            and abs(r_fim - (1.5 - PENALIDADE_REAL)) < 1e-12 and abs(r3 - r_formula) < 1e-12,
            f"perfeito {r_perfeito:.3f} · pior vivo {r_pior_vivo:.4f} · fim {r_fim:.1f} · step {r3:.6f} = fórmula {r_formula:.6f}")
    e = DroneRealEnv(aleatorizar=True)
    e.reset(seed=1)
    p1 = dict(e.parametros_dr)
    e.reset(seed=2)
    p2 = dict(e.parametros_dr)
    v.check("F4 domain randomization sorteia física nova por episódio (kf, massa, SoC₀, SoH, atraso…)",
            p1["kf"] != p2["kf"] and p1["soh"] != p2["soh"] and p1["atraso"] != p2["atraso"],
            f"kf ×{p1['kf']:.3f}/×{p2['kf']:.3f} · SoC₀ {p1['soc0']:.2f}/{p2['soc0']:.2f} · "
            f"SoH {p1['soh']:.3f}/{p2['soh']:.3f}")


# ============================================================================================ G. FC
def checa_fc(v: Validador, hw) -> None:
    print("\n— G. FC dedicado (malha de taxa + mistura) —")
    model, _data = dr.carregar(hw)
    fc = ControladorFC(hw, model, 0.002)
    m = fc.mix
    v.check("G1 mistura X: colunas roll/pitch/yaw de soma nula e ortogonais (comandos desacoplados)",
            float(np.abs(m.sum(axis=0)).max()) < 1e-12 and abs(float(m[:, 0] @ m[:, 1])) < 1e-12
            and abs(float(m[:, 0] @ m[:, 2])) < 1e-12 and abs(float(m[:, 1] @ m[:, 2])) < 1e-12,
            f"mix = {m.tolist()}")
    e = DroneRealEnv()
    e.reset(seed=0)
    e.data.qpos[2] = 2.0
    e.data.qvel[:] = 0.0
    mujoco.mj_forward(e.model, e.data)
    e.planta.prop.reiniciar(np.full(4, hw.ponto_pairagem(e.planta.v_bus)["omega"]))
    e.planta.armar(True)
    e.fc.reiniciar()
    e.fc.armar(True)
    p = []
    sp = 1.0
    for _ in range(int(8 * fc.tau_motor / 0.002)):
        u = e.fc.passo(e.u_pairagem, [sp, 0.0, 0.0], e.planta.imu.giro.medicao)
        e.planta.passo(u)
        p.append(float(e.data.qvel[3]))
    p = np.array(p)
    k90 = int(np.argmax(p >= 0.9 * sp)) if (p >= 0.9 * sp).any() else None
    sobre = float(p.max() / sp - 1)
    # malha P + atraso do motor com ζ = 0,7: ω_n = 1/(2ζτ) ⇒ t90 ≈ 2,46/ω_n ≈ 3,4·τ_motor (+ filtros/atraso)
    v.check("G2 degrau de taxa de roll 1 rad/s: t90 < 4,5·τ_motor (ζ = 0,7) e sobre-elevação < 35 %",
            k90 is not None and k90 * 0.002 < 4.5 * fc.tau_motor and sobre < 0.35,
            f"t90 = {1000 * k90 * 0.002 if k90 is not None else float('nan'):.0f} ms · sobre-elevação {100 * sobre:.0f} % · "
            f"τ_motor {1000 * fc.tau_motor:.1f} ms · Kp {fc.kp.round(4)}")


# ============================================================================================ H. autonomia
def checa_autonomia(v: Validador, hw) -> None:
    print("\n— H. autonomia (bateria ↔ pairagem) —")
    aut = dr.autonomia_estimada(hw)
    # bancada: Propulsao + ModeloBateria (sem MuJoCo), empuxo total = peso, até à tensão de pouso
    prop = dr.Propulsao(hw)
    prop.armar(True)
    bat = drb.ModeloBateria(hw, soc0=1.0)
    t_rotor = hw.massa_total * 9.81 / (4 * (1 - hw.frame.perda_download))
    w_h = math.sqrt(t_rotor / hw.kf)
    prop.reiniciar(np.full(4, w_h))
    prop.armar(True)
    v_bus, t, dt = bat.v, 0.0, 0.05
    p_e = hw.potencia_eletronica("voo")
    v_pouso = v_pouso_celula(hw.bateria.celula) * hw.bateria.s
    while t < 4 * 3600:
        d = hw.duty_para_omega(w_h, v_bus)
        if d > hw.duty_max:
            break
        prop.definir_acelerador([hw.duty_para_acelerador(d)] * 4)
        e_ab, r0 = bat.tensao_aberta(), bat.r0()
        for _ in range(4):
            i_m, di = prop.corrente_bus(v_bus)
            f = v_bus - e_ab + r0 * (i_m + p_e / v_bus)
            v_bus -= f / (1 + r0 * (di - p_e / v_bus ** 2))
        i_tot = i_m + p_e / v_bus
        bat.passo(i_tot, dt)
        v_bus = bat.v
        if v_bus < v_pouso:
            break
        t += dt
    minutos = t / 60
    v.check("H1 autonomia de pairagem: integração analítica = bancada (motor + bateria Thevenin) ±5 %",
            _rel(minutos, aut["minutos"]) < 0.05,
            f"bancada {minutos:.1f} min vs estimada {aut['minutos']:.1f} min (pouso a {v_pouso:.1f} V, "
            f"{bat.wh_ciclo:.1f} Wh tirados de {hw.bateria.energia_wh:.0f} Wh nominais)")
    meta = float(hw.dados.get("meta_autonomia_min", 60.0))
    v.check(f"H2 o build ATIVO '{hw.nome}' cumpre a meta do dono ({meta:.0f} min de pairagem)",
            aut["minutos"] >= meta,
            f"{aut['minutos']:.1f} min · {hw.massa_total * 1000:.0f} g · "
            f"{hw.ponto_pairagem(hw.bateria.v_nominal)['p_total']:.1f} W em pairagem")


def checa_planta_real(v) -> None:
    """Todas as checagens da planta real (chamada pelo `run.py`)."""
    t0 = time.perf_counter()
    hw = dr.hardware()
    print(f"\n=== PLANTA REAL — build ativo '{hw.nome}' ({hw.descricao}) ===")
    checa_catalogo(v)
    checa_motor(v, hw)
    checa_saturacao(v, hw)
    checa_atraso(v)
    checa_bateria(v, hw)
    checa_ledger(v, hw)
    checa_pairagem_planta(v, hw)
    checa_aero(v, hw)
    checa_sensores(v, hw)
    checa_contrato(v)
    checa_fc(v, hw)
    checa_autonomia(v, hw)
    print(f"(planta real validada em {time.perf_counter() - t0:.1f} s)")


def main() -> int:
    v = Validador()
    checa_planta_real(v)
    print(f"\n{len(v.linhas) - v.falhas}/{len(v.linhas)} checagens [OK] · {v.falhas} [FALHA]")
    return 0 if v.falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
