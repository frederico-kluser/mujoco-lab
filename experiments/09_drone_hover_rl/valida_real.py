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
        # O "centro" é o do QUADRADO DOS ROTORES (a geometria do frame), não o CM: um payload
        # assimétrico (ex. a câmara no nariz) desloca o CM uns décimos de mm e o raio medido do CM
        # já não é igual nos 4 rotores — aqui valida-se a geometria e o desvio do CM aparece no
        # detalhe (é física real do payload, não erro de montagem).
        centro = sites[:, :2].mean(axis=0)
        dist = np.hypot(sites[:, 0] - centro[0], sites[:, 1] - centro[1])
        desvio_cm = float(np.hypot(data.xpos[corpo, 0] - centro[0], data.xpos[corpo, 1] - centro[1]))
        v.check(f"A3[{nome}] centro→rotor = wheelbase/2", float(np.abs(dist - hw.braco).max()) < 1e-9,
                f"{dist.round(4)} m vs {hw.braco:.4f} m")
        # GUARDA do CM (a que o A3 antigo fazia sem querer, medindo do CM): o payload assimétrico
        # (câmara no nariz) desloca o CM uns décimos de mm — e um erro de massa num payload longe do
        # centro desloca-o MILÍMETROS. 1 mm de teto é generoso para o payload atual e apanha isso.
        v.check(f"A3a[{nome}] CM centrado (payload ≤ 1 mm do centro dos rotores)", desvio_cm < 1e-3,
                f"desvio do CM = {1000 * desvio_cm:.3f} mm em +x (câmara/pack fora do centro)")
        if hw.camera is not None:
            from lab import camera_rpi as cam_rpi
            cid = model.camera("fpv").id
            pos = data.cam_xpos[cid] - data.xpos[corpo]
            m3 = np.asarray(data.cam_xmat[cid]).reshape(3, 3)
            frente = -m3[:, 2]
            # Geometria COMPILED (sem repetir fórmulas do modelo.py): o geom do módulo tem de passar a
            # face dianteira da placa central, ficar na linha central (y≈0) e a lente 1 mm à frente da
            # face do próprio módulo — e a massa do geom tem de ser a da PEÇA do catálogo.
            gid = model.geom("camera").id
            pgid = model.geom("placa").id
            x_geom = float(model.geom_pos[gid, 0])
            meia_esp = float(model.geom_size[gid, 0])          # meia-espessura do módulo no eixo ótico
            face_placa = float(model.geom_pos[pgid, 0] + model.geom_size[pgid, 0])
            x_lente = float(pos[0])
            modulo_cam = cam_rpi.modulo_da_peca(hw.camera.id)
            modo_cam = cam_rpi.modo_omissao(modulo_cam)    # 1080p50 (Pi Camera) · QVGA30 (Vision Shield, Arduino)
            fovy_esperado = cam_rpi.fovy_graus(modulo_cam, modo_cam)
            v.check(f"A3b[{nome}] câmara fpv no NARIZ (módulo além da placa, lente à frente, y=0) e a "
                    f"olhar para +x",
                    x_geom > face_placa and abs(float(model.geom_pos[gid, 1])) < 1e-9
                    and 0.0 < x_lente - (x_geom + meia_esp) <= 0.005
                    and float(frente[0]) > 0.999 and float(np.abs(frente[1:]).max()) < 1e-6,
                    f"geom x={x_geom:.4f} (face da placa {face_placa:.4f}) · lente x={x_lente:.4f} "
                    f"({1000 * (x_lente - x_geom - meia_esp):.1f} mm à frente do módulo) · "
                    f"y={model.geom_pos[gid, 1]:.1e} · visão={frente.round(3)}")
            v.check(f"A3c[{nome}] fovy da câmara = FoV do módulo (modo {modo_cam})",
                    abs(float(model.cam_fovy[cid]) - fovy_esperado) < 1e-9,
                    f"fovy={model.cam_fovy[cid]:.6f}° vs {fovy_esperado:.6f}° (GRAUS sempre, 3.15)")
            # a massa da câmara entra no modelo SÓ ela: o mesmo build sem a peça difere exactamente nela
            from dataclasses import replace as _sem_peca
            sem_camera = dr.modelo.carregar(_sem_peca(hw, camera=None))[0]
            so_camera = m_mod - float(sem_camera.body_mass.sum())
            v.check(f"A3d[{nome}] a câmara entra no modelo com a massa da peça (e só ela)",
                    abs(so_camera - hw.camera.massa) < 1e-9,
                    f"{1000 * so_camera:.3f} g vs {1000 * hw.camera.massa:.3f} g (diferença de modelos)")
        if hw.arma is not None:
            from dataclasses import replace as _sem_peca_arma
            sid_boca = model.site("boca_cano").id
            pos_boca = data.site_xpos[sid_boca] - data.xpos[corpo]
            gid_fer = model.geom("arma_ferrolho").id
            gid_qua = model.geom("arma_quadro").id
            v.check(f"A3e[{nome}] arma ({hw.arma.id}) montada no TOPO do drone (z_cano > 0 acima do CM, "
                    f"boca_cano à frente em +x, centrada em y=0)",
                    float(pos_boca[2]) > 0.08 and float(pos_boca[0]) > 0.08 and abs(float(pos_boca[1])) < 1e-9
                    and float(model.geom_pos[gid_fer, 2]) > float(model.geom_pos[gid_qua, 2]) > 0.0,
                    f"boca_cano = ({pos_boca[0]:+.4f}, {pos_boca[1]:+.4f}, {pos_boca[2]:+.4f}) m rel. ao CM")
            sem_arma = dr.modelo.carregar(_sem_peca_arma(hw, arma=None))[0]
            so_arma = m_mod - float(sem_arma.body_mass.sum())
            v.check(f"A3f[{nome}] a arma entra no modelo com a massa exata da peça ({1000 * hw.arma.massa:.0f} g)",
                    abs(so_arma - hw.arma.massa) < 1e-9,
                    f"{1000 * so_arma:.3f} g vs {1000 * hw.arma.massa:.3f} g (diferença de modelos)")
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
    # A6: verificação da modelagem 3D detalhada do build ativo (frame de estabilidade, fios trifásicos, motor MN4004, RPi 5 e hélices 3D)
    hw_at = dr.hardware()
    m_at, _ = dr.carregar(hw_at)
    geoms_drone_3d = (
        "placa", "placa_superior", "espacador_placa_1", "espacador_placa_4",
        "trelica_estab_1", "trelica_estab_4", "suporte_motor_1", "suporte_motor_4",
        "fio_motor1_a", "fio_motor1_b", "fio_motor1_c", "fio_motor4_a", "fio_motor4_b", "fio_motor4_c",
        "abracadeira_braco1_1", "abracadeira_braco4_2",
        "motor1_estator_cobre", "motor1_sino_anel", "motor1_base_cnc", "motor1_raio_1", "motor1_eixo",
        "helice1_cubo", "helice1_pa1_raiz", "helice1_pa1_ponta", "helice1_pa1_faixa", "helice1_pa2_ponta",
        "el_rpi5", "rpi5_soc_bcm2712", "rpi5_dissipador", "rpi5_ventoinha", "rpi5_rp1",
        "rpi5_rj45", "rpi5_usb3_torre", "rpi5_usb3_azul", "rpi5_usb2_torre", "rpi5_gpio_40p", "rpi5_usbc", "rpi5_micro_hdmi_1",
        "cinta_bateria_1", "conector_xt90", "cabo_bateria_pos", "cabo_bateria_neg",
    )
    v.check("A6 modelagem 3D detalhada: treliças de estabilidade, fios trifásicos A/B/C até aos motores, motor MN4004 com bobinas e sino ventilado, Raspberry Pi 5 fiel e hélices 3D",
            all(m_at.geom(g).id >= 0 for g in geoms_drone_3d),
            f"{len(geoms_drone_3d)}/{len(geoms_drone_3d)} geoms estruturais, fios, motor, RPi 5 e hélices presentes")


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

    # B9: impacto físico do tamanho e design da hélice (diâmetro, passo, nº de pás, corda/solidez, afunilamento e perfil)
    h_base = hw.helice
    h_maior_d = h_base.com_design(diametro_pol=16.5)
    h_maior_passo = h_base.com_design(passo_pol=6.2)
    h_tripa = h_base.com_design(pas=3)
    h_ponta_larga = h_base.com_design(afunilamento=0.65)
    kf0, kq0, _ = dr.componentes.kf_kq(hw.motor, h_base)
    kf_d, kq_d, _ = dr.componentes.kf_kq(hw.motor, h_maior_d)
    kf_p, kq_p, _ = dr.componentes.kf_kq(hw.motor, h_maior_passo)
    kf_3, kq_3, _ = dr.componentes.kf_kq(hw.motor, h_tripa)
    j0 = dr.componentes.inercia_rotor(hw.motor, h_base)
    j_d = dr.componentes.inercia_rotor(hw.motor, h_maior_d)
    j_taper = dr.componentes.inercia_rotor(hw.motor, h_ponta_larga)
    v.check("B9 design e tamanho da hélice impactam a física: maior D, passo ou nº de pás aumentam kf/kq e inércia J_rotor (e afunilamento altera κ_J)",
            kf_d > kf0 and kq_d > kq0 and kf_p > kf0 and kq_p > kq0 and kf_3 > kf0 and j_d > j0 and j_taper > j0,
            f"kf: 15x5={kf0:.2e} → 16.5x5={kf_d:.2e}, 15x6.2={kf_p:.2e}, 3-pás={kf_3:.2e} · J_rotor: {j0:.2e} → D16.5={j_d:.2e}, taper0.65={j_taper:.2e}")

    # B10: rotação 3D das hélices no sentido físico correto (CW nos rotores 1,2; CCW nos rotores 3,4) proporcional a % de ω_max
    m_rot, d_rot, pl_rot = _planta(hw, flags=dra.FlagsAero.base(), seed=0)
    pl_rot.reiniciar(1.0, armado=True)
    for _ in range(100):
        pl_rot.passo([0.9, 0.45, 0.9, 0.45])
    pct = pl_rot.pct_rotacao_helices
    gid_ponta1 = m_rot.geom("helice1_pa1_ponta").id
    pos_pa_antes = m_rot.geom_pos[gid_ponta1].copy()
    ang_antes = list(pl_rot.angulos_helices)
    pl_rot.passo([0.9, 0.45, 0.9, 0.45])
    pl_rot.passo([0.9, 0.45, 0.9, 0.45])
    pos_pa_depois = m_rot.geom_pos[gid_ponta1].copy()
    dang = [((pl_rot.angulos_helices[i] - ang_antes[i] + math.pi) % (2.0 * math.pi)) - math.pi for i in range(4)]
    v.check("B10 hélices 3D rodam no sentido físico correto (CW: Δθ₁,₂ < 0; CCW: Δθ₃,₄ > 0) com velocidade proporcional à % de ω_max de cada motor",
            dang[0] < 0.0 and dang[1] < 0.0 and dang[2] > 0.0 and dang[3] > 0.0
            and abs(dang[0]) > 1.5 * abs(dang[1]) and abs(dang[2]) > 1.5 * abs(dang[3])
            and float(np.linalg.norm(pos_pa_depois - pos_pa_antes)) > 1e-3,
            f"%ω_max={[round(100*x, 1) for x in pct]} % · Δθ={[round(x, 4) for x in dang]} rad")
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
    # O piso físico do ganho a 0,5·D é o do ROTOR ISOLADO (o termo solo da fórmula); os termos de
    # interferência mútua (vizinhos/opostos) só ADICIONAM — e desaparecem com o espaçamento. O teto
    # antigo (≥1,15) era o do frame 650 (rotores a 1,21 D de separação, interferência forte); com o
    # wheelbase ×3 (rotores a ~3,6 D) a interferência cai e o ganho aproxima-se do rotor isolado — o que
    # a pesquisa prevê ("ground effect mais fraco e quadrático a >3 D"). Por isso o que se valida aqui é
    # a FÓRMULA exata + o piso do rotor isolado + a monotonia do decaimento, em QUALQUER geometria.
    k_isolado = 1.0 / (1.0 - (raio / (4 * 0.5 * d_hel)) ** 2)
    v.check("D1 efeito de solo (Sanchez-Cuevas 2017): fórmula exata, ≥ rotor isolado a 0,5·D, ≈1 a 5 m",
            g05 >= k_isolado - 1e-12 and g05 >= g175 >= g5 and abs(g5 - 1.0) < 2e-3
            and _rel(g05, 1 / (1 - s)) < 1e-12,
            f"0,5 D: ×{g05:.3f} (rotor isolado ×{k_isolado:.3f}, interferência "
            f"{100 * (g05 / k_isolado - 1):.1f} %) · 1,75 D: ×{g175:.3f} · 5 m: ×{g5:.4f} · "
            f"D = {d_hel:.3f} m · separação vizinhos = {dvz / d_hel:.1f} D")
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
    # D9 efeito giroscópico dos rotores: τ = −Ω × H = −(Σ h_i)·(Ω × ẑ)  (h_i = s_i·J·ω_i)
    ag = dra.Aerodinamica(hw)
    hs = 2.37e-4          # kg·m²/s — soma dos momentos angulares dos rotores (2 CW + 2 CCW a ω diferentes)
    casos = [((0.8, 0.0, 0.0), (0.0, 0.0, 1.0)), ((0.0, -0.5, 0.0), (0.0, 0.0, 1.0)),
             ((0.3, -0.2, 0.1), (0.0, 0.0, 1.0)), ((0.9, 0.1, 0.4), (0.0, 0.0, 1.0)),
             ((0.7, -0.7, 0.7), (0.7071067811865476, 0.0, 0.7071067811865476))]
    erros = [float(np.abs(ag.binario_giroscopico(np.array(w), np.full(4, hs / 4), np.array(e))
                          - (-hs * np.cross(np.array(w), np.array(e)))).max()) for w, e in casos]
    expl = ag.binario_giroscopico(np.array((0.8, 0.0, 0.0)), np.full(4, hs / 4), np.array((0.0, 0.0, 1.0)))
    paralelo = ag.binario_giroscopico(np.array((0.0, 0.0, 1.2)), np.full(4, hs / 4), np.array((0.0, 0.0, 1.0)))
    desligado = dra.Aerodinamica(hw, dra.FlagsAero(giroscopico=False)).binario_giroscopico(
        np.array((0.8, 0.0, 0.0)), np.full(4, hs / 4), np.array((0.0, 0.0, 1.0)))
    _m9, _d9, pl9 = _planta(hw, dra.FlagsAero(), seed=13)
    pl9.prop.omega = np.array([100.0, 200.0, 150.0, 120.0])
    ok_h = bool(np.allclose(pl9.prop.momento_angular(),
                            pl9.prop.giro * pl9.prop.j * pl9.prop.omega, rtol=0, atol=1e-15))
    v.check("D9 giroscópico: τ = −Ω × H = −(Σh_i)·(Ω × ẑ) com h_i = s_i·J·ω_i; Ω ∥ ẑ ⇒ 0; flag off ⇒ 0",
            max(erros) < 1e-15 and abs(expl[1] - 0.8 * hs) < 1e-15
            and float(np.abs(paralelo).max()) == 0.0 and float(np.abs(desligado).max()) == 0.0 and ok_h,
            f"τ(Ω=0,8·x̂) = {expl.round(9)} (esperado [0, {0.8 * hs:.3e}, 0]) · "
            f"‖τ(Ω∥ẑ)‖ = {float(np.abs(paralelo).max()):.1e} · h_i = s_i·J·ω_i ✔")


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

    # F6 — `reset(seed)` é REPRODUTÍVEL entre instâncias, seja qual for o passado de cada uma. Até 2026-10-13 não
    # era: a flutuação do VRS (o único estado da planta que nenhum reset repunha) atravessava os episódios, e a mesma
    # semente com as mesmas ações divergia na 1.ª descida na própria esteira. O perfil abaixo sobe e DESCE de propósito.
    def _voo(env: DroneRealEnv, semente: int, passos: int = 450) -> tuple[bytes, float]:
        g = np.random.default_rng(31_000 + semente)
        env.reset(seed=semente)
        z_max, estado = 0.0, b""
        for i in range(passos):
            acao = g.uniform(-0.1, 0.1, size=4).astype(np.float32)
            acao[0] = 0.9 if (i // 150) % 2 == 0 else -0.9
            _, _, term, trunc, _ = env.step(acao)
            z_max = max(z_max, float(env.data.qpos[2]))
            estado += env.data.qpos.tobytes() + env.data.qvel.tobytes()
            if term or trunc:
                break
        return estado, z_max

    fresco, usado = DroneRealEnv(), DroneRealEnv()
    _voo(usado, 999, 300)                              # esta instância já voou outro episódio antes
    (b1, z1), (b2, _) = _voo(fresco, 4242), _voo(usado, 4242)
    v.check("F6 reset(seed) reprodutível entre instâncias: a mesma semente e as mesmas ações dão `qpos`/`qvel` IGUAIS "
            "byte a byte numa instância nova e numa que já voou outro episódio (subida + descida na própria esteira)",
            b1 == b2 and z1 > 1.5, f"{len(b1)} bytes comparados · z máx. {z1:.2f} m")


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


# ============================================================================================ I. arma e tiro
def checa_arma_tiro(v: Validador, hw) -> None:
    """I1–I5: balística da Glock 25 (.380 Auto), impulso linear/angular do tiro no topo do drone e recuperação."""
    if hw.arma is None:
        return
    print("\n— I. arma fixa no topo (Glock 25 .380 Auto: balística, soco, direção, torque e recuperação) —")
    a = hw.arma
    e0_teoria = 0.5 * a.massa_projetil * (a.velocidade_boca ** 2)
    j_teoria = a.massa_projetil * a.velocidade_boca + a.massa_polvora * a.velocidade_gases
    f_teoria = j_teoria / a.duracao_impulso
    v.check("I1 balística .380 ACP (95 gr @ 296 m/s): E₀ = ½·m_p·v₀² ≈ 270 J e J_tiro = m_p·v₀ + m_c·v_g",
            abs(a.energia_boca_j - e0_teoria) < 1e-12 and 268.0 <= a.energia_boca_j <= 272.0
            and abs(a.impulso_tiro - j_teoria) < 1e-12 and abs(a.forca_media_tiro - f_teoria) < 1e-12,
            f"E₀ = {a.energia_boca_j:.2f} J · J_tiro = {a.impulso_tiro:.4f} N·s "
            f"(projétil {a.impulso_projetil:.4f} + gases {a.impulso_gases:.4f}) · "
            f"F_soco = {a.forca_media_tiro:.2f} N durante {1000 * a.duracao_impulso:.0f} ms")

    # I2 e I4: condições isoladas (gravidade = 0, densidade = 0, rotores parados) → Δv e Δω exatos pela fórmula fechada
    model, data, pl = _planta(hw, flags=dra.FlagsAero.base(), seed=0)
    model.opt.gravity[:] = 0.0
    model.opt.density = 0.0
    model.opt.viscosity = 0.0
    data.qpos[2] = 5.0
    data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    pl.reiniciar(1.0, armado=False)
    res = pl.disparar(1)
    n_passos = round(a.duracao_impulso / pl.dt)
    for _ in range(n_passos):
        pl.passo([0.0] * 4)
    dv_med = np.array(data.qvel[0:3], dtype=float)
    dw_med = np.array(data.qvel[3:6], dtype=float)
    dv_esp = -a.impulso_tiro / hw.massa_total
    z_cano = pl.braco_z_arma
    iyy = float(pl.inercia_corpo[1])
    dw_y_esp = -z_cano * a.impulso_tiro / iyy
    # Como o cano sobe com a cabragem durante os 20 ms (θ̄ ≈ ½·Δω_y·Δt_soco ≈ −0,01 rad), −x̂_corpo ganha uma
    # pequena componente −z de ~−0,0022 m/s e ‖Δv‖ conserva J_tiro/m_total a 1e-5.
    v.check("I2 impulso linear do tiro (isolado): Δp = −J_tiro·x̂_corpo ⇒ Δv_x = −J_tiro/m_total (±0,2 %)",
            _rel(dv_med[0], dv_esp) < 2e-3 and _rel(float(np.linalg.norm(dv_med)), abs(dv_esp)) < 1e-4
            and abs(dv_med[1]) < 1e-6 and abs(dv_med[2]) < 5e-3
            and isinstance(res, dict) and res["tiros_acumulados"] == 1,
            f"Δv = ({dv_med[0]:+.5f}, {dv_med[1]:+.5f}, {dv_med[2]:+.5f}) m/s vs teoria {dv_esp:+.5f} m/s")
    v.check("I4 impulso angular (arma no TOPO, z_cano > 0 acima do CM): ΔL_y = −z_cano·J_tiro ⇒ Δω_y = −z_cano·J/I_yy < 0 (nariz sobe)",
            _rel(dw_med[1], dw_y_esp) < 5e-3 and dw_med[1] < -0.5 and abs(dw_med[0]) < 1e-6 and abs(dw_med[2]) < 1e-6,
            f"Δω_y = {dw_med[1]:+.5f} rad/s vs teoria {dw_y_esp:+.5f} rad/s (z_cano = {1000 * z_cano:.1f} mm, I_yy = {iyy:.4f} kg·m²)")

    # I3: direção do soco roda com o rumo (yaw = +90° → nariz aponta para +y, soco empurra para −y)
    model2, data2, pl2 = _planta(hw, flags=dra.FlagsAero.base(), seed=0)
    model2.opt.gravity[:] = 0.0
    model2.opt.density = 0.0
    model2.opt.viscosity = 0.0
    data2.qpos[2] = 5.0
    ang = math.pi / 2.0
    data2.qpos[3:7] = [math.cos(ang / 2.0), 0.0, 0.0, math.sin(ang / 2.0)]
    data2.qvel[:] = 0.0
    mujoco.mj_forward(model2, data2)
    pl2.reiniciar(1.0, armado=False)
    res2 = pl2.disparar(1)
    for _ in range(n_passos):
        pl2.passo([0.0] * 4)
    dv2 = np.array(data2.qvel[0:3], dtype=float)
    v.check("I3 direção do soco acompanha o rumo: com yaw = 90° (+y), o soco empurra para −y (azimute 270°)",
            _rel(dv2[1], dv_esp) < 2e-3 and abs(dv2[0]) < 1e-3 and abs(res2["azimute_soco_graus"] - 270.0) < 1e-2,
            f"Δv = ({dv2[0]:+.4f}, {dv2[1]:+.4f}, {dv2[2]:+.4f}) m/s · azimute do soco = {res2['azimute_soco_graus']:.1f}°")

    # I5: disparo em pairagem com o controlador (DroneRealEnv + FC): o drone sente o soco, recua e recupera sem cair
    import sim_view as sv
    env = DroneRealEnv(modo_acao="ctbr", comando=True, episodio_s=15.0)
    nuc = sv.NucleoClassico.criar(env)
    nuc.instalar()
    env.reset(seed=0)
    nuc.pos_reset()
    for _ in range(200):
        nuc.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
        env.step(np.zeros(4, dtype=np.float32))
    x_antes = float(env.data.qpos[0])
    vx_antes = float(env.data.qvel[0])
    wy_antes = float(env.data.qvel[4])
    env.disparar(1)
    nuc.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
    env.step(np.zeros(4, dtype=np.float32))
    dvx_voo = float(env.data.qvel[0]) - vx_antes
    dwy_voo = float(env.data.qvel[4]) - wy_antes
    terminou = False
    for _ in range(200):
        nuc.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
        _, _, term, _, info = env.step(np.zeros(4, dtype=np.float32))
        terminou = terminou or bool(term)
    x_depois = float(env.data.qpos[0])
    z_depois = float(info["z"])
    nuc.remover()
    v.check("I5 disparo em pairagem (SPACE): produz o soco (−0,64 m/s e cabragem −1,08 rad/s) e a cascata recupera a posição sem cair",
            not terminou and abs(dvx_voo - dv_esp) < 0.03 and dwy_voo < -0.8
            and abs(x_depois - x_antes) < 0.12 and abs(z_depois - 1.0) < 0.08,
            f"soco imediato: Δv_x={dvx_voo:+.3f} m/s, Δω_y={dwy_voo:+.3f} rad/s → após 4 s: Δx={x_depois - x_antes:+.3f} m, z={z_depois:.3f} m")

    # I6 e I7: modelagem detalhada da Glock 25, efeito de fogo do cano, projétil visível SÓ até 50 m e caminho por 1,0 s
    m_vis, d_vis, pl_vis = _planta(hw, flags=dra.FlagsAero.base(), seed=0)
    d_vis.qpos[2] = 5.0
    d_vis.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
    d_vis.qvel[:] = 0.0
    mujoco.mj_forward(m_vis, d_vis)
    pl_vis.reiniciar(1.0, armado=False)
    geoms_anatomia = (
        "arma_suporte_base", "arma_quadro", "arma_punho", "arma_base_carregador", "arma_dedo_1", "arma_dedo_2",
        "arma_dedo_3", "arma_guarda_mato_baixo", "arma_guarda_mato_frente", "arma_gatilho", "arma_solenoide_gatilho",
        "arma_ferrolho", "arma_janela_ejecao", "arma_serrilha_1", "arma_serrilha_6", "arma_cano", "arma_boca_furo",
        "arma_mira_frente", "arma_ponto_mira_frente", "arma_mira_tras", "arma_fogo_nucleo", "arma_fogo_cone",
        "projetil_tiro_0", "caminho_tiro_0",
    )
    todos_existem = all(m_vis.geom(g).id >= 0 for g in geoms_anatomia)
    gid_fogo = m_vis.geom("arma_fogo_nucleo").id
    gid_proj = m_vis.geom("projetil_tiro_0").id
    gid_cam = m_vis.geom("caminho_tiro_0").id
    gid_fer = m_vis.geom("arma_ferrolho").id
    x_fer0 = float(m_vis.geom_pos[gid_fer, 0])
    alpha_fogo_antes = float(m_vis.geom_rgba[gid_fogo, 3])
    pl_vis.disparar(1)
    alpha_fogo_t0 = float(m_vis.geom_rgba[gid_fogo, 3])
    # avança 10 ms (5 passos de 2 ms): fogo do cano ativo, ferrolho recuado (blowback), projétil a ~3 m (< 50 m)
    for _ in range(5):
        pl_vis.passo([0.0] * 4)
    dx_fer_10ms = float(m_vis.geom_pos[gid_fer, 0]) - x_fer0
    tel_10ms = pl_vis.telemetria_arma()
    proj_vis_10ms = bool(tel_10ms["projetil_visivel"]) and float(m_vis.geom_rgba[gid_proj, 3]) > 0.9
    cam_vis_10ms = bool(tel_10ms["caminho_visivel"]) and float(m_vis.geom_rgba[gid_cam, 3]) > 0.8
    dist_10ms = float(tel_10ms["distancia_projetil_m"])
    # avança até t = 70 ms (mais 30 passos): fogo do cano e blowback já terminaram; projétil a ~20 m (< 50 m) ainda visível
    for _ in range(30):
        pl_vis.passo([0.0] * 4)
    alpha_fogo_70ms = float(m_vis.geom_rgba[gid_fogo, 3])
    v.check("I6 modelagem anatómica da Glock 25 (24 geoms: punho 22°, guarda-mato, gatilho, ferrolho, janela de ejeção, "
            "serrilhas, miras) + efeito de fogo do cano e blowback no disparo",
            todos_existem and alpha_fogo_antes == 0.0 and alpha_fogo_t0 > 0.9 and dx_fer_10ms < -0.020
            and alpha_fogo_70ms == 0.0,
            f"fogo α: antes={alpha_fogo_antes:.2f} → disparo={alpha_fogo_t0:.2f} → 70 ms={alpha_fogo_70ms:.2f} · "
            f"recuo blowback ferrolho={1000 * dx_fer_10ms:.1f} mm")
    # avança até t = 200 ms (mais 65 passos, total 100 passos = 0,200 s): a 296 m/s já passou dos 50 m (~169 ms)
    for _ in range(65):
        pl_vis.passo([0.0] * 4)
    tel_200ms = pl_vis.telemetria_arma()
    proj_vis_200ms = bool(tel_200ms["projetil_visivel"]) or float(m_vis.geom_rgba[gid_proj, 3]) > 0.0
    cam_vis_200ms = bool(tel_200ms["caminho_visivel"]) and float(m_vis.geom_rgba[gid_cam, 3]) > 0.8
    dist_200ms = float(tel_200ms["distancia_projetil_m"])
    comp_capsula_200ms = 2.0 * float(m_vis.geom_size[gid_cam, 1])
    # avança até t = 980 ms (mais 390 passos, total 490 passos = 0,980 s <= 1,0 s): caminho AINDA visível
    for _ in range(390):
        pl_vis.passo([0.0] * 4)
    tel_980ms = pl_vis.telemetria_arma()
    cam_vis_980ms = bool(tel_980ms["caminho_visivel"]) and float(m_vis.geom_rgba[gid_cam, 3]) > 0.05
    # avança até t = 1004 ms (mais 12 passos, total 502 passos = 1,004 s > 1,0 s): caminho apaga-se
    for _ in range(12):
        pl_vis.passo([0.0] * 4)
    tel_1004ms = pl_vis.telemetria_arma()
    cam_vis_1004ms = bool(tel_1004ms["caminho_visivel"]) or float(m_vis.geom_rgba[gid_cam, 3]) > 0.0
    v.check("I7 projétil renderizado APENAS até 50,0 m (~169 ms a 296 m/s) e caminho da trajetória visível por exatamente 1,0 s",
            proj_vis_10ms and 2.5 < dist_10ms < 3.5 and cam_vis_10ms
            and (not proj_vis_200ms) and abs(dist_200ms - 50.0) < 1e-6 and abs(comp_capsula_200ms - 50.0) < 1e-4
            and cam_vis_200ms and cam_vis_980ms and (not cam_vis_1004ms),
            f"10 ms: proj={proj_vis_10ms} ({dist_10ms:.2f} m) · 200 ms: proj={proj_vis_200ms} ({dist_200ms:.1f} m, "
            f"cápsula {comp_capsula_200ms:.1f} m), caminho={cam_vis_200ms} · 980 ms: caminho={cam_vis_980ms} · "
            f"1004 ms: caminho={cam_vis_1004ms}")

    # I8: orientação 3D do rastro (horizontal ao longo do cano, NUNCA vertical do céu ao chão) e colisão exata com a BOLA
    m_bola, d_bola = dr.carregar(hw, com_alvo=True)
    pl_bola = dr.Planta(hw, m_bola, d_bola, flags_aero=dra.FlagsAero.base())
    d_bola.qpos[2] = 1.0
    d_bola.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
    d_bola.qvel[:] = 0.0
    mujoco.mj_forward(m_bola, d_bola)
    pl_bola.reiniciar(1.0, armado=False)
    z_boca_mundo = float(d_bola.site_xpos[pl_bola.site_boca, 2])
    # Coloca a bola a 2,0 m à frente na linha de tiro do cano
    d_bola.mocap_pos[pl_bola._mocap_bola] = [2.0, 0.0, z_boca_mundo - 0.002]
    mujoco.mj_kinematics(m_bola, d_bola)
    mira_antes = pl_bola.prever_tiro_bola()
    pl_bola.disparar(1)
    for _ in range(10):
        pl_bola.passo([0.0] * 4)
    gid_c_bola = m_bola.geom("caminho_tiro_0").id
    eixo_z_capsula = d_bola.geom_xmat[gid_c_bola].reshape(3, 3)[:, 2]
    comp_ate_bola = 2.0 * float(m_bola.geom_size[gid_c_bola, 1])
    tel_bola = pl_bola.telemetria_arma()
    v.check("I8 rastro 3D alinhado do cano até ao impacto (eixo da cápsula horizontal +x̂, nunca vertical) e colisão com a BOLA detetada",
            mira_antes["no_alvo"] is True and mira_antes["mensagem"] == "NO ALVO"
            and abs(float(eixo_z_capsula[0]) - 1.0) < 1e-3 and abs(float(eixo_z_capsula[2])) < 1e-2
            and tel_bola["acertos_bola"] == 1 and tel_bola["ultimo_tiro"]["acertou_bola"] is True
            and 1.80 < comp_ate_bola < 1.98,
            f"eixo_capsula=({eixo_z_capsula[0]:+.4f}, {eixo_z_capsula[1]:+.4f}, {eixo_z_capsula[2]:+.4f}) · "
            f"comp={comp_ate_bola:.3f} m (cano→bola) · acertou_bola={tel_bola['ultimo_tiro']['acertou_bola']}")

    # I9: IA de Mira Balística (treinada em GPU) + AUTO SHOOT em bola parada (0 m/s) e móvel (0,4 m/s) — 100 % de acerto
    from mira_balistica import MiraBalisticaIA
    mira_ia = MiraBalisticaIA()
    acertos_tot, tiros_tot, erros_tot = 0, 0, 0
    for vel_teste in (0.0, 0.4):
        env_m = DroneRealEnv(modo_acao="ctbr", comando=True, com_alvo=True, episodio_s=12.0)
        nuc_m = sv.NucleoClassico.criar(env_m)
        nuc_m.instalar()
        env_m.reset(seed=6200)
        nuc_m.pos_reset()
        mira_ia.reiniciar()
        for _ in range(180):
            nuc_m.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
            env_m.step(np.zeros(4, dtype=np.float32))
        env_m.definir_trajetoria_ponto("aleatorio" if vel_teste > 0.0 else "parado", vel=vel_teste, semente=6200)
        for k in range(220):
            cmd_m = mira_ia.passo(env_m, dt=env_m.dt_decisao)
            nuc_m.comando(cmd_m)
            if k >= 30 and mira_ia.deve_atirar(env_m):
                env_m.disparar(1)
            env_m.step(np.zeros(4, dtype=np.float32))
        for _ in range(10):
            nuc_m.comando(mira_ia.passo(env_m, dt=env_m.dt_decisao))
            env_m.step(np.zeros(4, dtype=np.float32))
        tiros_tot += env_m.planta.n_tiros
        acertos_tot += env_m.planta.n_acertos_bola
        erros_tot += env_m.planta.n_erros_bola
        nuc_m.remover()
    v.check("I9 modo SEGUIR A BOLA + AUTO SHOOT (0,0 m/s parada e 0,4 m/s móvel): alinha a mira balística na bola e dispara SÓ quando vai acertar (100 % acerto)",
            tiros_tot >= 4 and acertos_tot == tiros_tot and erros_tot == 0,
            f"AUTO SHOOT: {acertos_tot}/{tiros_tot} acertos na bola (100,0 %, {erros_tot} erros)")


# ============================================================================================ J. carga e vento
def checa_carga_e_vento(v: Validador, hw) -> None:
    """J1–J4: limite de carga, impacto na bateria/autonomia, impossibilidade de alçar voo com excesso de peso e impacto do vento."""
    print("\n— J. limite de carga, impacto na bateria/voo e impacto do vento —")
    pm = hw.ponto_maximo(soc=1.0)
    lc = hw.limites_carga(soc=1.0, vento_m_s=0.0)
    f_dl = 1.0 - hw.frame.perda_download
    t_oge_esp = 4.0 * f_dl * hw.kf * (pm["omega_max"] ** 2)
    v.check("J1 ponto máximo sob carga: V_bus = OCV − I_tot·R_tot, T_efetivo_OGE = 4·(1−δ_dl)·kf·ω_max(V)² e limites das peças",
            abs(pm["v_bus_carga"] - (pm["v_ocv"] - pm["i_total"] * pm["r_total_mohm"] / 1000.0)) < 1e-6
            and _rel(pm["empuxo_efetivo_oge_n"], t_oge_esp) < 1e-12
            and lc["massa_max_descolagem_oge_g"] > lc["massa_max_voo_seguro_g"] > hw.massa_total * 1000.0
            and lc["pode_alcar_voo"] is True and lc["estado_voo"] == "voo_seguro",
            f"V_carga={pm['v_bus_carga']:.2f} V (queda {pm['queda_tensao_v']:.2f} V a {pm['i_total']:.1f} A) · "
            f"carga máx segura={lc['carga_max_voo_seguro_g']:.0f} g · OGE={lc['carga_max_descolagem_oge_g']:.0f} g · "
            f"IGE={lc['carga_max_descolagem_ige_g']:.0f} g")

    # J2: impacto progressivo da carga na corrente da bateria, queda de tensão e autonomia
    aut0 = dr.autonomia_estimada(hw, massa=hw.massa_total)["minutos"]
    aut1 = dr.autonomia_estimada(hw, massa=hw.massa_total + 0.600)["minutos"]
    aut2 = dr.autonomia_estimada(hw, massa=hw.massa_total + 1.200)["minutos"]
    aut_excesso = dr.autonomia_estimada(hw, massa=lc["massa_max_descolagem_oge_g"] / 1000.0 + 0.500)
    v.check("J2 impacto da carga na bateria: +0,6 kg e +1,2 kg aumentam a corrente e reduzem a autonomia; acima de T_max a autonomia é 0 min",
            aut0 > aut1 > aut2 > 10.0 and aut_excesso["minutos"] == 0.0 and not aut_excesso["pode_voar"],
            f"autonomia: base={aut0:.1f} min → +600 g={aut1:.1f} min → +1200 g={aut2:.1f} min → excesso={aut_excesso['minutos']:.1f} min ({aut_excesso['motivo_fim']})")

    # J3: excesso de peso impede fisicamente de alçar voo no simulador MuJoCo (mesmo a 100 % de acelerador)
    env_pesado = DroneRealEnv(modo_acao="motores", episodio_s=4.0)
    env_pesado.reset(seed=0)
    z_chao_p = float(env_pesado.data.qpos[2])
    soc_ini_p = float(env_pesado.planta.bat.soc)
    # Adiciona +3,0 kg (massa total ~5,97 kg > massa_max_descolagem_ige ~5,38 kg)
    est_carga = env_pesado.definir_carga(3.0)
    z_max_p = z_chao_p
    for _ in range(50):                           # 1,0 s a 100 % de comando nos 4 motores
        env_pesado.step(np.ones(4, dtype=np.float32))
        z_max_p = max(z_max_p, float(env_pesado.data.qpos[2]))
    soc_fim_p = float(env_pesado.planta.bat.soc)
    i_pesado = float(env_pesado.planta.i_total)
    v.check("J3 carga acima do limite (5968 g > 5381 g IGE): `pode_alcar_voo=False` e o drone NÃO sai do chão no MuJoCo mesmo a 100 % de acelerador (drenando a bateria no pico)",
            est_carga["pode_alcar_voo"] is False and est_carga["estado_voo"] == "impossivel_alcar_voo"
            and (z_max_p - z_chao_p) < 0.003 and env_pesado.data.ncon > 0
            and i_pesado > 25.0 and soc_fim_p < soc_ini_p,
            f"estado={est_carga['estado_voo']} · Δz_máx={1000 * (z_max_p - z_chao_p):.2f} mm (ncon={env_pesado.data.ncon}) · "
            f"I_bat={i_pesado:.1f} A · ΔSoC={100 * (soc_fim_p - soc_ini_p):.3f} %")

    # J4: cálculo acoplado do impacto do vento (força, inclinação, potência, autonomia e vento máximo vs peso)
    iv0 = hw.impacto_vento(0.0, soc=0.8)
    iv3 = hw.impacto_vento(3.0, soc=0.8)
    iv5 = hw.impacto_vento(5.0, soc=0.8)
    aut_v0 = dr.autonomia_estimada(hw, vento_m_s=0.0)["minutos"]
    aut_v3 = dr.autonomia_estimada(hw, vento_m_s=3.0)["minutos"]
    aut_v5 = dr.autonomia_estimada(hw, vento_m_s=5.0)["minutos"]
    w_max_leve = hw.vento_maximo_sustentavel(massa=hw.massa_estrutura_sem_carga, soc=0.8)
    w_max_arma = hw.vento_maximo_sustentavel(massa=hw.massa_total, soc=0.8)
    w_max_pesado = hw.vento_maximo_sustentavel(massa=hw.massa_total + 1.200, soc=0.8)
    w_max_impossivel = hw.vento_maximo_sustentavel(massa=lc["massa_max_descolagem_oge_g"] / 1000.0 + 0.5, soc=0.8)
    v.check("J4 impacto do vento acoplado ao peso: vento maior exige maior inclinação e potência (reduzindo a autonomia), e carga maior reduz o vento máximo sustentável até 0 m/s",
            0.0 == iv0["forca_vento_n"] < iv3["forca_vento_n"] < iv5["forca_vento_n"]
            and 0.0 == iv0["inclinacao_eq_graus"] < iv3["inclinacao_eq_graus"] < iv5["inclinacao_eq_graus"]
            and iv0["p_total"] < iv3["p_total"] < iv5["p_total"]
            and aut_v0 > aut_v3 > aut_v5
            and w_max_leve > w_max_arma > w_max_pesado > 0.0 and w_max_impossivel == 0.0,
            f"P(0/3/5 m/s)={iv0['p_total']:.1f}/{iv3['p_total']:.1f}/{iv5['p_total']:.1f} W · "
            f"aut(0/3/5 m/s)={aut_v0:.1f}/{aut_v3:.1f}/{aut_v5:.1f} min · "
            f"W_máx(sem arma / com G25 / +1,2 kg / excesso)={w_max_leve:.1f} / {w_max_arma:.1f} / {w_max_pesado:.1f} / {w_max_impossivel:.1f} m/s")

    # J5: troca ao vivo de motores e bateria (cores/tamanhos 3D distintos, vazão A, Watts gastos e viabilidade de voo)
    env_p = DroneRealEnv(modo_acao="ctbr", comando=True, episodio_s=6.0)
    env_p.reset(seed=0)
    gid_m1 = env_p.model.geom("motor1").id
    gid_bat = env_p.model.geom("bateria").id
    r_m1_antes = float(env_p.model.geom_size[gid_m1, 0])
    cor_m1_antes = env_p.model.geom_rgba[gid_m1].copy()
    tam_bat_antes = env_p.model.geom_size[gid_bat].copy()
    p_5006 = env_p.trocar_pecas(motor_id="tmotor_mn5006_kv450", bateria_id="lipo_6s1p_4500_alta_vazao")
    r_m1_5006 = float(env_p.model.geom_size[gid_m1, 0])
    cor_m1_5006 = env_p.model.geom_rgba[gid_m1].copy()
    tam_bat_lipo = env_p.model.geom_size[gid_bat].copy()
    p_4s_fraco = env_p.trocar_pecas(motor_id="tmotor_mn4004_kv300", bateria_id="lipo_4s1p_4500_baixa_tensao")
    v.check("J5 troca dinâmica de motores e bateria (`trocar_pecas`): atualiza tamanho/cor 3D no MuJoCo, KV, massa, vazão (A), Watts e deteta bateria 4S insuficiente",
            r_m1_5006 > r_m1_antes and not np.allclose(cor_m1_5006, cor_m1_antes)
            and not np.allclose(tam_bat_lipo, tam_bat_antes)
            and p_5006["motor_kv"] == 450.0 and p_5006["vazao_max_a"] == 225.0 and p_5006["pode_alcar_voo"] is True
            and p_4s_fraco["bateria_s"] == 3 and p_4s_fraco["pode_alcar_voo"] is False,
            f"MN5006+LiPo6S: D={2000*r_m1_5006:.1f} mm ({p_5006['motor_cor_nome']}), vazão={p_5006['vazao_max_a']} A, voa={p_5006['pode_alcar_voo']} · "
            f"MN4004+3S: T/W={p_4s_fraco['t_w_oge']:.2f}, voa={p_4s_fraco['pode_alcar_voo']}")

    # J6: estabilização anti-tremor em ar calmo (ω_RMS < 0,85°/s, jitter < 0,9 %) e recuperação pós-tiro em ≤ 0,48 s
    import sim_view as sv
    from mira_balistica import MiraBalisticaIA
    env_est = DroneRealEnv(modo_acao="ctbr", comando=True, com_alvo=True, episodio_s=12.0)
    nuc_est = sv.NucleoClassico.criar(env_est)
    nuc_est.instalar()
    env_est.reset(seed=6200)
    nuc_est.pos_reset()
    mira_est = MiraBalisticaIA()
    qs_calmo, us_calmo = [], []
    for k in range(260):
        nuc_est.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
        env_est.step(np.zeros(4, dtype=np.float32))
        if k >= 150:
            qs_calmo.append(env_est.data.qvel[3:6].copy())
            us_calmo.append(env_est.planta.prop.duty.copy())
    qs_arr = np.array(qs_calmo)
    us_arr = np.array(us_calmo)
    omega_rms_deg = float(np.max(np.degrees(np.sqrt(np.mean(qs_arr ** 2, axis=0)))))
    jitter_duty_pct = float(np.diff(us_arr, axis=0).std() * 100.0)
    env_est.definir_trajetoria_ponto("parado")
    for _ in range(90):
        nuc_est.comando(mira_est.passo(env_est, dt=env_est.dt_decisao))
        env_est.step(np.zeros(4, dtype=np.float32))
    env_est.disparar(1)
    erros_pos_tiro = []
    for _ in range(60):
        nuc_est.comando(mira_est.passo(env_est, dt=env_est.dt_decisao))
        env_est.step(np.zeros(4, dtype=np.float32))
        prev_t = env_est.planta.prever_tiro_bola(pos_bola=env_est.ponto_alvo, vel_bola=env_est.ponto_alvo_vel)
        erros_pos_tiro.append(100.0 * float(prev_t["erro_bola_m"]))
    passo_rec = next((k for k in range(2, len(erros_pos_tiro) - 8) if all(e <= 5.45 for e in erros_pos_tiro[k:k + 8])), 60)
    t_rec_s = passo_rec * 0.02
    nuc_est.remover()
    v.check("J6 estabilização anti-tremor (ω_RMS < 0,85°/s, jitter de duty < 0,9 %) e recuperação pós-tiro < 0,50 s",
            omega_rms_deg < 0.85 and jitter_duty_pct < 0.90 and t_rec_s <= 0.50,
            f"ar calmo: ω_RMS_máx={omega_rms_deg:.2f}°/s (antes 3,11°/s), jitter_duty={jitter_duty_pct:.2f} % (antes 6,63 %) · "
            f"retorno a NO ALVO pós-tiro={t_rec_s:.2f} s (antes 1,92 s)")


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
    checa_arma_tiro(v, hw)
    checa_carga_e_vento(v, hw)
    print(f"(planta real validada em {time.perf_counter() - t0:.1f} s)")


def main() -> int:
    v = Validador()
    checa_planta_real(v)
    print(f"\n{len(v.linhas) - v.falhas}/{len(v.linhas)} checagens [OK] · {v.falhas} [FALHA]")
    return 0 if v.falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
