#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_bracos.py — PROVA dos BRAÇOS ARTICULADOS (8 juntas) e da MIRA POR ARFAGEM.

Pedido do dono (2026-10-19): cada braço sobe/desce na base e tem uma 2.ª dobradiça a uma distância segura um pouco maior
do que a hélice; as pontas apontam sempre para o mesmo lado (lateralmente); motores de precisão com a velocidade de
ajuste dentro do limite do motor; 8 dados novos (as juntas) nos treinos; atirar de qualquer altura face ao alvo sem
mudar x, y, z — só a guinada e a arfagem do corpo. O que se prova (por execução; temporários só em `$TMPDIR`):

  §1 PEÇAS × FICHAS — servo DYNAMIXEL XH430-V210-R e encoder AS5048A contra os números das fichas (oráculo AQUI, não
     lido do JSON); sem-fim pelas fórmulas fechadas (λ < φ ⇒ autobloqueante; η = tan λ / tan(λ + φ)); orçamento de
     massa = soma das peças; T/W do build ≥ 2,2; mastro = raio da hélice + folga > raio da hélice;
  §2 MODELO — 8 juntas de dobradiça com o eixo y do CORPO; batentes = os do catálogo; Σ massas = orçamento; CM do
     conjunto na origem; rotores no sítio do drone rígido (x, y) com juntas a 0; builds rígidos sem juntas novas; a
     malha de taxa do FC do articulado com margem de fase ≥ 45° (o rígido com os ganhos de sempre);
  §3 CINEMÁTICA — `bracos_controlo.cinematica_direta` = MuJoCo (50 poses ao acaso); as pontas NUNCA mudam de y
     (lateral); a cinemática inversa põe os 4 eixos paralelos a R_y(τ)·ẑ e os 4 rotores no MESMO plano dos motores;
  §4 HÉLICE × BRAÇO — em toda a grelha de juntas dentro dos batentes, a hélice (disco) passa longe do tubo do braço
     e do servo do cotovelo; a condição fechada para o braço a 45°: mastro > raio·max|sen q|/√(1 + cos²q) = raio;
  §5 SERVOS (bancada no MuJoCo, drone pousado) — o cotovelo não passa da velocidade em vazio da ficha; o ombro (sem-fim
     20:1) não passa de ω₀/20; encoders quantizados; em pairagem o ombro SEGURA o momento do empuxo só com a corrente de
     espera e, desligado, o sem-fim não deixa o braço mexer (autobloqueio);
  §6 VOO (núcleo de firmware, interface 4) — corpo a −25°/+25° com os motores de nível: pitch ±1°, motores ±2°, x/y/z
     a menos de 6 cm em regime (6–8 s depois da ordem; < 0,3 m no transitório da troca de 50°); a observação dos treinos
     ganha as 8 juntas (encoders no ator, verdade no crítico);
  §7 MIRA (`--mira`) — os 3 cenários de altura: sem erros, ≥ 8 acertos em 10 s e afastamento da estação menor do que o
     deslize de um recuo (1,25·Δv/K_vel ≈ 0,40 m: a mira não translada, é o recuo que empurra);
  §8 MUTAÇÕES (`--mutacao`) — mutações em CÓPIAS das fontes têm de FALHAR as checagens certas;
  §9 COCKPIT (`--cockpit`) — o runner do cockpit com `--build articulado_15pol_mn5006`: RL recusado com motivo, seguir
     a bola + AUTO SHOOT com a mira por arfagem (0 erros), Q/E do dono a mudar o pitch do corpo, HUD com os 8 servos
     (curso, energia, potência) e o ledger motores + eletrónica + servos = total; o `sim_site.py --build` passa-o.

Uso:
    .venv/bin/python experiments/09_drone_hover_rl/teste_bracos.py              # §1–§6
    .venv/bin/python experiments/09_drone_hover_rl/teste_bracos.py --mira       # + §7
    .venv/bin/python experiments/09_drone_hover_rl/teste_bracos.py --cockpit    # + §9 (runner do cockpit)
    .venv/bin/python experiments/09_drone_hover_rl/teste_bracos.py --mutacao    # §8
    ... --so-estatico                                                            # §1–§4 (sem simular; o §8 usa-o)
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
from lab.drone_rpi import modelo as mo

BUILD = "articulado_15pol_mn5006"
# ORÁCULO das fichas (lidas em 2026-10-19; independentes do JSON):
#   [XH] ROBOTIS XH430-V210-R — docs.robotis.com: 2,6 N·m a 24 V / 0,7 A; 52 rpm a 24 V; 28,5×46,5×34 mm; 82 g;
#        encoder de 4096 pulsos/volta; contínuo estimado = 20 % do bloqueio (robotis.us)
#   [AS] ams AS5048A — datasheet v1-11: 14 bits = 0,0219°/LSB; precisão de sistema 0,05°
FICHA_XH430_V210 = {"binario_bloqueio": 2.6, "corrente_bloqueio": 0.7, "rpm_vazio": 52.0, "massa_g": 82.0,
                    "tensao": 24.0, "pulsos": 4096}
FICHA_AS5048A = {"bits": 14, "resolucao_graus": 0.0219}


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


def _ry(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


# ============================================================================================ §1 peças
def checa_pecas(c: Checagens) -> None:
    _titulo("§1 peças × fichas, sem-fim pelas fórmulas fechadas, orçamento e T/W")
    try:
        hw = dr.hardware(BUILD)
    except (KeyError, ValueError) as erro:
        c.ok("[§1] o build articulado resolve", False, repr(erro))
        return
    mec = hw.bracos
    sv = mec.cotovelo.servo
    f = FICHA_XH430_V210
    c.ok("[§1] servo XH430-V210-R = ficha (2,6 N·m · 0,7 A · 52 rpm · 82 g · 24 V · 4096 pulsos)",
         abs(sv.binario_bloqueio - f["binario_bloqueio"]) < 1e-9 and abs(sv.corrente_bloqueio - f["corrente_bloqueio"]) < 1e-9
         and abs(sv.omega_vazio - f["rpm_vazio"] * 2 * math.pi / 60) < 1e-9 and abs(sv.massa * 1000 - f["massa_g"]) < 1e-9
         and abs(sv.tensao - f["tensao"]) < 1e-9 and abs(sv.resolucao - 2 * math.pi / f["pulsos"]) < 1e-12,
         f"{sv.binario_bloqueio} N·m · {sv.corrente_bloqueio} A · {sv.omega_vazio * 60 / 2 / math.pi:.1f} rpm · {sv.massa * 1000:.0f} g")
    o = mec.ombro
    c.ok("[§1] encoder do braço no ombro = AS5048A (14 bits, 0,0219°/LSB)",
         abs(math.degrees(o.encoder_resolucao) - FICHA_AS5048A["resolucao_graus"]) < 1e-6,
         f"{math.degrees(o.encoder_resolucao):.4f}°/LSB")
    lam, phi = o.angulo_avanco, math.atan(o.coef_atrito)
    eta = math.tan(lam) / math.tan(lam + phi)
    c.ok("[§1] sem-fim AUTOBLOQUEANTE pela fórmula: λ = atan(m·z₁/d₁) < φ = atan μ",
         lam < phi and abs(math.degrees(lam) - math.degrees(math.atan(0.8 / 12.0))) < 0.01 and o.e_autobloqueante,
         f"λ {math.degrees(lam):.2f}° < φ {math.degrees(phi):.2f}°")
    c.ok("[§1] rendimento do sem-fim η = tan λ / tan(λ+φ) e binário/velocidade de saída = servo × N × η e ω₀/N",
         abs(o.eficiencia_subir - eta) < 1e-12 and abs(o.binario_bloqueio_saida - sv.binario_bloqueio * 20 * eta) < 1e-9
         and abs(o.omega_vazio_saida - sv.omega_vazio / 20) < 1e-12,
         f"η {eta:.3f} · τ_b {o.binario_bloqueio_saida:.2f} N·m · ω₀ {math.degrees(o.omega_vazio_saida):.1f}°/s")
    soma = sum(hw.massas.values())
    pecas = (hw.frame.massa + hw.frame.massa_pernas + 4 * hw.motor.massa + 4 * hw.helice.massa + hw.esc.massa_total
             + hw.bateria.massa + hw.massa_extra + sum(cc.massa for cc in hw.consumidores)
             + sum(float(s.get("massa_g", 0)) / 1000 for s in hw.sensores.values()) + hw.camera.massa + hw.arma.massa
             + 4 * (o.servo.massa + o.massa_redutor + o.encoder_massa + mec.cotovelo.servo.massa) + 4 * mec.massa_mastro
             + 8 * mec.massa_dobradica + mec.massa_fonte)
    c.ok("[§1] orçamento de massa = soma das peças (servos, sem-fins, encoders, mastros, dobradiças, regulador incluídos)",
         abs(soma - pecas) < 1e-9 and abs(hw.massa_total - soma) < 1e-12, f"{soma * 1000:.1f} g")
    tw = 4 * hw.empuxo_max(hw.bateria.v_nominal) / (hw.massa_total * 9.81)
    c.ok("[§1] o build articulado voa com margem: T/W ≥ 2,2 (com o MN5006; com o MN4004 seria ≈ 1,0)", tw >= 2.2,
         f"T/W {tw:.2f}")
    g = mo.geometria_bracos(hw)
    c.ok("[§1] mastro (eixo do cotovelo → plano da hélice) = raio da hélice + folga, e MAIOR do que o raio",
         abs(g["l_m"] - (hw.helice.raio + mec.folga_helice)) < 1e-12 and g["l_m"] > hw.helice.raio + 0.02,
         f"mastro {g['l_m'] * 1000:.1f} mm · raio {hw.helice.raio * 1000:.1f} mm")


# ============================================================================================ §2 modelo
def checa_modelo(c: Checagens) -> None:
    _titulo("§2 modelo: 8 juntas em y, batentes, massas, CM, rotores no sítio do rígido")
    hw = dr.hardware(BUILD)
    m, d = dr.carregar(hw)
    mujoco.mj_forward(m, d)
    juntas = mo.JUNTAS_OMBRO + mo.JUNTAS_COTOVELO
    eixos_ok, batentes_ok = True, True
    bid = m.body("drone").id
    r_corpo = d.xmat[bid].reshape(3, 3)
    for nome in juntas:
        j = m.joint(nome)
        eixo_mundo = d.xaxis[j.id]
        eixo_corpo = r_corpo.T @ eixo_mundo
        eixos_ok &= int(m.jnt_type[j.id]) == int(mujoco.mjtJoint.mjJNT_HINGE) and np.allclose(eixo_corpo, [0, 1, 0], atol=1e-12)
        lim = hw.bracos.ombro.limites if nome.startswith("ombro") else hw.bracos.cotovelo.limites
        batentes_ok &= bool(m.jnt_limited[j.id]) and np.allclose(m.jnt_range[j.id], lim, atol=1e-12)
    c.ok("[§2] 8 juntas de DOBRADIÇA com o eixo = y do corpo (as pontas só sobem/descem e inclinam à frente/trás)", eixos_ok,
         f"njnt {m.njnt} (1 livre + 8)")
    c.ok("[§2] batentes das juntas = os do catálogo (ombro ±40°, cotovelo ±60°)", batentes_ok)
    c.ok("[§2] Σ massas do modelo = orçamento do build", abs(float(m.body_mass.sum()) - hw.massa_total) < 1e-9,
         f"{float(m.body_mass.sum()) * 1000:.2f} g")
    c.ok("[§2] CM do conjunto (corpo + braços + mastros) na origem do corpo, juntas a 0",
         float(np.linalg.norm(d.subtree_com[bid] - d.xpos[bid])) < 1e-9)
    p_rot = np.array([r_corpo.T @ (d.site_xpos[m.site(n).id] - d.xpos[bid]) for n in mo.SITES_ROTOR])
    centro = p_rot[:, :2].mean(axis=0)                 # a origem está no CM (a arma/câmara à frente desviam-no um pouco)
    c.ok("[§2] com as juntas a 0 os rotores formam a MESMA cruz em X do drone rígido (o mastro só os põe mais acima)",
         np.allclose(p_rot[:, :2] - centro, hw.pos_rotores, atol=1e-9) and float(np.ptp(p_rot[:, 2])) < 1e-12,
         f"CM a ({-centro[0] * 1000:+.1f}, {-centro[1] * 1000:+.1f}) mm do centro · z dos rotores {np.round(p_rot[:, 2], 3)} m")
    hw0 = dr.hardware("endurance_15pol_p50b")
    m0, _ = dr.carregar(hw0)
    c.ok("[§2] o build RÍGIDO ativo não ganhou juntas nem atuadores (1 junta livre, 8 atuadores de rotor)",
         m0.njnt == 1 and m0.nu == 8 and not mo.tem_bracos(m0), f"njnt {m0.njnt} · nu {m0.nu}")
    # malha de taxa do FC (modelo de projeto do `fc.py`: motor τ_m + atraso + filtros): o MN5006 a 4,5 kg é rápido e as
    # fórmulas punham-na a 30° de margem (ressonância a ~3 Hz, 3,9 °/s de tremor) — o build exige ≥ 45° e o rígido
    # ativo fica com os ganhos de sempre (τ de projeto = τ_motor)
    import fc as fc_mod
    from controlo_classico import _margens, resposta_malha_taxa
    w = np.logspace(-2.0, 2.5, 6000)

    def margem_fase(h, modelo) -> tuple[float, object]:
        f = fc_mod.ControladorFC(h, modelo, 0.002)
        _t, ll = resposta_malha_taxa(float(f.kp[0]), float(f.ki[0]), float(f.kd[0]), float(f.alfa[0]), f.tau_motor,
                                     fc_mod.atraso_malha_taxa(h), fc_mod.FILTRO_GIRO_HZ, fc_mod.FILTRO_D_HZ, w)
        return _margens(w, ll), f
    mg, f_art = margem_fase(hw, m)
    mg0, f_rig = margem_fase(hw0, m0)
    c.ok("[§2] malha de taxa do FC: margem de fase ≥ 45° no articulado (motor rápido: τ de projeto > τ_motor) e o rígido "
         "ativo com τ de projeto = τ_motor",
         mg["pm_graus"] >= 44.9 and f_art.tau_projeto > f_art.tau_motor and f_rig.tau_projeto == f_rig.tau_motor,
         f"articulado PM {mg['pm_graus']:.1f}° a {mg['wc_rad_s']:.1f} rad/s (τ_m {f_art.tau_motor * 1e3:.1f} → τ de projeto "
         f"{f_art.tau_projeto * 1e3:.1f} ms) · rígido PM {mg0['pm_graus']:.1f}°")


# ============================================================================================ §3 cinemática
def checa_cinematica(c: Checagens) -> None:
    _titulo("§3 cinemática: direta = MuJoCo, pontas sem movimento lateral, inversa com os 4 rotores coplanares")
    from bracos_controlo import cinematica_direta, cinematica_inversa
    hw = dr.hardware(BUILD)
    m, d = dr.carregar(hw)
    g = mo.geometria_bracos(hw)
    rng = np.random.default_rng(7)
    qadr = [m.jnt_qposadr[m.joint(n).id] for n in mo.JUNTAS_OMBRO + mo.JUNTAS_COTOVELO]
    bid = m.body("drone").id
    mujoco.mj_forward(m, d)
    erro_p = erro_e = lateral = 0.0
    lim_o, lim_c = hw.bracos.ombro.limites, hw.bracos.cotovelo.limites
    for _ in range(50):
        q = np.concatenate([rng.uniform(*lim_o, 4), rng.uniform(*lim_c, 4)])
        d.qpos[qadr] = q
        mujoco.mj_forward(m, d)
        r = d.xmat[bid].reshape(3, 3)
        cd = cinematica_direta(hw, q)
        for i, nome in enumerate(mo.SITES_ROTOR):
            sid = m.site(nome).id
            p_mj = r.T @ (d.site_xpos[sid] - d.xpos[bid])
            e_mj = r.T @ d.site_xmat[sid].reshape(3, 3)[:, 2]
            erro_e = max(erro_e, float(np.linalg.norm(e_mj - cd["eixos"][i])))
        # a cinemática fechada mede-se a partir da origem ANTES do deslocamento para o CM: compara-se a diferença à pose 0
        p_mj = np.array([r.T @ (d.site_xpos[m.site(n).id] - d.xpos[bid]) for n in mo.SITES_ROTOR])
        d.qpos[qadr] = 0.0
        mujoco.mj_forward(m, d)
        r0 = d.xmat[bid].reshape(3, 3)
        p0 = np.array([r0.T @ (d.site_xpos[m.site(n).id] - d.xpos[bid]) for n in mo.SITES_ROTOR])
        cd0 = cinematica_direta(hw, np.zeros(8))
        erro_p = max(erro_p, float(np.abs((p_mj - p0) - (cd["rotores"] - cd0["rotores"])).max()))
        lateral = max(lateral, float(np.abs(p_mj[:, 1] - p0[:, 1]).max()))
    c.ok("[§3] cinemática direta fechada = MuJoCo em 50 poses ao acaso (posição dos rotores e eixo dos motores)",
         erro_p < 1e-9 and erro_e < 1e-9, f"erro pos {erro_p:.1e} m · eixo {erro_e:.1e}")
    c.ok("[§3] as pontas NUNCA mudam de y (lateralmente apontam sempre para o mesmo sítio)", lateral < 1e-12,
         f"max |Δy| {lateral:.1e} m")
    pior_alt = pior_eixo = 0.0
    for tau in np.radians(np.linspace(-40, 40, 17)):
        q1, q2 = cinematica_inversa(float(tau), g["r_s"], g["l1"])
        cd = cinematica_direta(hw, np.array([q1] * 4 + [q2] * 4))
        p_m = (_ry(float(tau)).T @ cd["rotores"].T).T              # no referencial dos MOTORES
        pior_alt = max(pior_alt, float(np.ptp(p_m[:, 2])))
        pior_eixo = max(pior_eixo, float(np.abs(cd["eixos"] - _ry(float(tau)) @ np.array([0, 0, 1.0])).max()))
    c.ok("[§3] cinemática inversa (q₁ = τ + asin(r_s·sen τ/l₁), q₂ = −asin(…)): eixos ∥ R_y(τ)·ẑ e os 4 rotores no mesmo "
         "plano dos motores, τ ∈ [−40°, 40°]", pior_alt < 1e-9 and pior_eixo < 1e-12,
         f"desnível {pior_alt:.1e} m · eixo {pior_eixo:.1e}")


# ============================================================================================ §4 folga da hélice
def _dist_ponto_segmento(p, a, b) -> float:
    ab = b - a
    t = float(np.clip((p - a) @ ab / max(float(ab @ ab), 1e-12), 0.0, 1.0))
    return float(np.linalg.norm(p - (a + t * ab)))


def checa_folga(c: Checagens) -> None:
    _titulo("§4 a hélice nunca chega ao braço (grelha de juntas dentro dos batentes)")
    hw = dr.hardware(BUILD)
    g = mo.geometria_bracos(hw)
    r_hel = hw.helice.raio
    meia_tubo = 0.012
    sv = hw.bracos.cotovelo.servo
    raio_servo = 0.5 * math.hypot(sv.dims[1], sv.dims[2])
    lim_o, lim_c = hw.bracos.ombro.limites, hw.bracos.cotovelo.limites
    ang = np.linspace(0, 2 * math.pi, 48, endpoint=False)
    rr = np.linspace(0.25, 1.0, 4) * r_hel
    pior = 1e9
    for q1 in np.linspace(*lim_o, 9):
        for q2 in np.linspace(*lim_c, 13):
            phi = math.radians(45.0)
            u = np.array([math.cos(phi), math.sin(phi), 0.0])
            ombro = g["r_s"] * u
            cotovelo = ombro + _ry(q1) @ (g["l1"] * u)
            r_m = _ry(q1 + q2)
            centro = cotovelo + r_m @ np.array([0.0, 0.0, g["l_m"]])
            ex, ey = r_m @ np.array([1.0, 0, 0]), r_m @ np.array([0, 1.0, 0])
            for a in ang:
                for r in rr:
                    p = centro + r * (math.cos(a) * ex + math.sin(a) * ey)
                    d_tubo = _dist_ponto_segmento(p, ombro, cotovelo - 0.03 * (cotovelo - ombro) / g["l1"]) - meia_tubo
                    d_servo = float(np.linalg.norm(p - cotovelo)) - raio_servo
                    pior = min(pior, d_tubo, d_servo)
    c.ok("[§4] folga mínima hélice ↔ tubo do braço e servo do cotovelo > 2 cm em TODA a grelha (9 × 13 poses)",
         pior > 0.02, f"pior folga {pior * 100:.1f} cm")
    q = np.radians(np.linspace(1, 90, 90))
    maximo = float(np.max(np.abs(np.sin(q)) / np.sqrt(1 + np.cos(q) ** 2)))
    c.ok("[§4] condição fechada (braço a 45°, eixos em y): sem colisão para QUALQUER q₂ se mastro > raio·max|sen q|/√(1+cos²q) "
         "= raio — o «um pouco maior do que a hélice» do dono", g["l_m"] > r_hel * maximo,
         f"max {maximo:.3f} · mastro {g['l_m'] * 1000:.0f} mm > {r_hel * maximo * 1000:.0f} mm")


# ============================================================================================ §5 servos
def checa_servos(c: Checagens) -> None:
    _titulo("§5 servos na bancada (drone pousado): limites de velocidade da ficha, encoders, autobloqueio")
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
    alvos = np.zeros(8)
    alvos[4:] = math.radians(40.0)               # cotovelos +40° (os mastros inclinam no ar: a hélice não chega ao chão)
    alvos[0] = math.radians(-8.0)                # SÓ o ombro 1 (frente-esq.): levanta a sua perna — um q₁ comum baixava
    #                                              as pontas da frente e subia as de trás (eixo único em y) e o drone balançava
    sv.definir_alvos(alvos)
    qd_max = np.zeros(8)
    serie_o1 = []
    for k in range(2500):                        # 5 s
        pl.passo()
        qd_max = np.maximum(qd_max, np.abs(d.qvel[pl.j_dadr]))
        serie_o1.append((k * pl.dt, float(d.qpos[pl.j_qadr[0]])))
    so1 = np.array(serie_o1)
    curso = math.radians(-8.0)
    t10 = so1[np.argmax(so1[:, 1] <= 0.1 * curso), 0]
    t90 = so1[np.argmax(so1[:, 1] <= 0.9 * curso), 0]
    v_media_o1 = 0.8 * abs(curso) / max(t90 - t10, 1e-6)
    w0_c = hw.bracos.cotovelo.omega_vazio_saida
    w0_o = hw.bracos.ombro.omega_vazio_saida
    q_fim = np.degrees(d.qpos[pl.j_qadr])
    c.ok("[§5] cotovelo: chega aos 40° e nunca passa da velocidade em VAZIO da ficha (52 rpm = 312°/s)",
         float(qd_max[4:].max()) <= w0_c * 1.02 and np.all(np.abs(q_fim[4:] - 40.0) < 1.0),
         f"máx {math.degrees(float(qd_max[4:].max())):.0f}°/s · fim {np.round(q_fim[4:], 2)}°")
    c.ok("[§5] ombro (sem-fim 20:1): chega aos −8° com a velocidade média do curso (10→90 %) ≤ ω₀/20 = 15,6°/s; os outros 3 "
         "ficam parados", v_media_o1 <= w0_o * 1.02 and abs(q_fim[0] + 8.0) < 1.0 and np.all(np.abs(q_fim[1:4]) < 1.0),
         f"média {math.degrees(v_media_o1):.1f}°/s (pico do braço {math.degrees(float(qd_max[0])):.1f}°/s, com o ressalto "
         f"elástico da folga) · fim {np.round(q_fim[:4], 2)}°")
    med = sv.medidas
    res_o, res_c = hw.bracos.ombro.encoder_resolucao, hw.bracos.cotovelo.encoder_resolucao
    quant = np.all(np.abs(med[:4] / res_o - np.round(med[:4] / res_o)) < 1e-6) and \
        np.all(np.abs(med[4:] / res_c - np.round(med[4:] / res_c)) < 1e-6)
    c.ok("[§5] as 8 leituras são QUANTIZADAS pelos encoders (14 bits no braço do ombro, 4096/volta no cotovelo)", bool(quant))


def checa_autobloqueio(c: Checagens) -> None:
    _titulo("§5b em pairagem o sem-fim segura o momento do empuxo sem corrente e, desligado, não deixa o braço mexer")
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
    tau_ombro = float(np.abs(pl.servos.binarios[:4]).mean())
    i_ombro = pl.servos.correntes[:4]
    i_esp = env.hw.bracos.ombro.servo.corrente_espera
    c.ok("[§5b] pairagem: o ombro aguenta o momento do empuxo (> 3 N·m) com a corrente de ESPERA (o sem-fim é que segura)",
         tau_ombro > 3.0 and float(np.max(i_ombro)) < i_esp + 0.05,
         f"momento {tau_ombro:.2f} N·m · corrente {np.round(i_ombro, 3)} A (espera {i_esp} A)")
    q0 = pl.juntas_verdade()[:4].copy()
    env.definir_modo_bracos("rigido")
    for s in pl.servos.servos[:4]:
        s.ligado = False
    for _ in range(100):
        nuc.comando(hover)
        env.step(np.zeros(4, dtype=np.float32))
    dq = float(np.degrees(np.abs(pl.juntas_verdade()[:4] - q0)).max())
    c.ok("[§5b] servos dos ombros DESLIGADOS 2 s em voo: o braço não se mexe mais do que a folga do sem-fim (0,5°)",
         dq < 0.5, f"max |Δq| {dq:.3f}°")


# ============================================================================================ §6 voo
def checa_voo(c: Checagens) -> None:
    _titulo("§6 voo com o núcleo de firmware (interface 4): o corpo arfa para mirar, os motores ficam de nível, xyz parado")
    import sim_view as sv_mod
    from env import atitude
    from env_real import ESCALA_JUNTA, DroneRealEnv
    env = DroneRealEnv(build=BUILD, modo_acao="ctbr", comando=True, com_alvo=False, episodio_s=60.0)
    nuc = sv_mod.NucleoClassico.criar(env)
    nuc.instalar()
    obs, _ = env.reset(seed=2)
    nuc.pos_reset()
    hover = {"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0}
    for _ in range(300):
        nuc.comando(hover)
        env.step(np.zeros(4, dtype=np.float32))
    p0 = env.data.qpos[:3].copy()
    for alvo in (-25.0, 25.0):
        env.definir_pitch_corpo(math.radians(alvo))
        pit, mot, des, trans = [], [], [], []
        for k in range(400):
            nuc.comando(hover)
            obs, *_ = env.step(np.zeros(4, dtype=np.float32))
            trans.append(float(np.linalg.norm(env.data.qpos[:3] - p0)))
            if k >= 300:                                     # regime: 6–8 s depois da ordem (o +25° vem de −25°: 50°)
                pit.append(math.degrees(atitude(env.data.qpos[3:7])[1]))
                mot.append(math.degrees(float(nuc.nucleo.saida.pitch_motor)))
                des.append(trans[-1])
        c.ok(f"[§6] corpo a {alvo:+.0f}°: pitch médio a ±1°, motores de nível (±2°), x/y/z a menos de 6 cm em regime "
             "e < 0,3 m no transitório",
             abs(np.mean(pit) - alvo) < 1.0 and np.max(np.abs(mot)) < 2.0 and max(des) < 0.06 and max(trans) < 0.3,
             f"pitch {np.mean(pit):+.2f}±{np.std(pit):.2f}° · motores máx {np.max(np.abs(mot)):.2f}° · desvio máx "
             f"{max(des) * 100:.1f} cm (transitório {max(trans) * 100:.1f} cm)")
    n_rig = DroneRealEnv(modo_acao="ctbr", comando=True, episodio_s=5.0).observation_space.shape[0]
    q_obs = obs[env.obs_ator_dim - 8: env.obs_ator_dim]
    c.ok("[§6] observação dos treinos: +8 juntas no ator (encoders/ESCALA) e +8 no crítico; a do rígido não muda (48)",
         obs.shape[0] == n_rig + 16 and np.allclose(q_obs, env.planta.juntas_medidas() / ESCALA_JUNTA, atol=1e-6),
         f"articulado {obs.shape[0]} · rígido {n_rig} · juntas no ator {np.round(np.degrees(q_obs * ESCALA_JUNTA), 1)}°")


# ============================================================================================ §7 mira
def checa_mira(c: Checagens) -> None:
    _titulo("§7 mira nos 3 cenários de altura (bola programada, janela de 10 s)")
    import sim_view as sv_mod
    from cenarios_mira import OpcoesEpisodio, correr_episodio, criar_env
    # o drone NÃO translada para mirar (a mira só pede guinada + pitch, v = 0); o que o afasta é o RECUO: cada tiro dá
    # Δv = J_tiro/m e o laço de velocidade devolve-o em ~1/K_vel — o drone desliza ≈ Δv/K_vel e volta. Limite = esse
    # deslize + 25 % (o rígido v4 afasta-se 0,8–1,6 m nos mesmos cenários para mirar: `benchmark_evolucao.py`)
    env0 = criar_env(OpcoesEpisodio(), 5.0)
    k_vel = float(sv_mod.NucleoClassico.criar(env0).nucleo.cfg.cascata.k_vel)
    dv = env0.hw.arma.impulso_tiro / env0.massa
    lim = 1.25 * dv / k_vel
    for cen in ("mesma", "abaixo", "acima"):
        r = correr_episodio(OpcoesEpisodio(cenario=cen, semente=90001, usar_tf=True))
        c.ok(f"[§7] {cen}: 0 erros, ≥ 8 acertos em 10 s e afastamento da estação < 1,25·Δv_recuo/K_vel = {lim:.2f} m "
             "(só guinada + arfagem; o recuo empurra)",
             r["erros"] == 0 and r["acertos"] >= 8 and r["desloc_estacao_max_m"] < lim,
             f"{r['acertos']} acertos / {r['erros']} erros · afastamento {r['desloc_estacao_max_m'] * 100:.0f} cm "
             f"(Δv {dv:.2f} m/s/tiro, K_vel {k_vel:.2f}/s) · corpo {r['pitch_corpo_medio_graus']:+.1f}°")


# ============================================================================================ §9 cockpit
def checa_cockpit(c: Checagens) -> None:
    """O runner do cockpit (`sim_view.py`) com `--build articulado_15pol_mn5006`, sem browser e em tempo simulado:
    RL recusado com motivo, «seguir a bola» + AUTO SHOOT com a mira por ARFAGEM, a altura do dono (Q/E) a mudar o pitch
    do corpo, e o HUD com os 8 servos (ângulos, curso, potência, energia) e o ledger de potência que fecha."""
    _titulo("§9 cockpit: seguir a bola + AUTO SHOOT com os braços, a altura do dono e os servos no HUD")
    import sim_view as sv_mod
    import sim_site
    modelo = _EXP / "out" / "real_1950_voo_final" / "final.zip"
    if not modelo.is_file():
        c.ok("[§9] política da planta real disponível (out/real_1950_voo_final/final.zip)", False, "sem o ficheiro")
        return
    pol = sv_mod.carregar_politica(modelo)
    env, _gestor = sv_mod.ambiente_para(pol, modelo, com_alvo=True, build=BUILD)
    piloto = sv_mod.ControladorDeVoo(env, pol, "classico")
    piloto.trocar()
    piloto.pedido = "rl"
    modo = piloto.trocar()
    c.ok("[§9] a política RL (observação 48) não voa o build com braços (64): o pedido RL é recusado com motivo e fica "
         "a cascata clássica", modo == "classico" and piloto.estado == "erro" and "observação" in str(piloto.motivo),
         f"modo {modo} · estado {piloto.estado} · {str(piloto.motivo)[:70]}…")
    env.reset(seed=3)
    piloto.pos_reset()
    piloto.bola_auto_atirar, piloto.bola_vel = True, 0.3
    dt = env.dt_decisao

    def voar(segundos, segui, teclas=None):
        energias = []
        n0, a0, e0 = env.planta.n_tiros, env.planta.n_acertos_bola, env.planta.n_erros_bola
        for _ in range(int(round(segundos / dt))):
            piloto.comando_do_passo(sv_mod.Voo(ativo=True, teclas=teclas or {}, segui_alvo=segui), sv_mod._rumo_de(env))
            env.step(np.zeros(4, dtype=np.float32))
            energias.append(env.planta.servos.energias_wh.sum())
        h = sv_mod.hud_bracos(env, piloto, env._derivados())
        return h, (env.planta.n_tiros - n0, env.planta.n_acertos_bola - a0, env.planta.n_erros_bola - e0), energias

    voar(5.0, False)                                             # descola (a cascata sobe sozinha a ~1 m)
    h1, t1, _e1 = voar(8.0, True)
    c.ok("[§9] a 1 m: AUTO SHOOT com a mira por arfagem acerta e não erra (≥ 5 acertos, 0 erros em 8 s)",
         t1[1] >= 5 and t1[2] == 0 and h1["mira_ativa"], f"{t1[1]} acertos / {t1[2]} erros · corpo {h1['pitch_corpo']:+.1f}°")
    voar(2.5, True, {"q": True})
    h2, t2, _e2 = voar(4.0, True)
    z2 = float(env.data.qpos[2])
    c.ok("[§9] Q (o dono sobe): o drone fica mais alto do que a bola e o CORPO arfa nariz-abaixo para a mira (> +15°, "
         "com a elevação negativa)", z2 > 2.0 and h2["pitch_corpo"] > 15.0 and h2["mira"]["elevacao"] < -10.0,
         f"z {z2:.2f} m · corpo {h2['pitch_corpo']:+.1f}° · elevação {h2['mira']['elevacao']:+.1f}°")
    voar(3.0, True, {"e": True})
    h3, t3, _e3 = voar(5.0, True)
    z3 = float(env.data.qpos[2])
    c.ok("[§9] E (o dono desce abaixo da bola): o CORPO arfa nariz-acima (< −5°) e continua a acertar sem erros",
         z3 < 1.0 and h3["pitch_corpo"] < -5.0 and t3[2] == 0, f"z {z3:.2f} m · corpo {h3['pitch_corpo']:+.1f}° · "
         f"{t3[1]} acertos / {t3[2]} erros")
    _h4, _t4, e4 = voar(1.5, True)
    pot = dict(env.planta.potencias())
    pot["eletronica"] -= env.hw.bracos.potencia_espera()
    soma = pot["motores"] + pot["eletronica"] + pot["servos"]
    c.ok("[§9] HUD dos braços: 8 juntas, curso e energia a crescer (a corrente sai da bateria), servos > 0 W e o ledger "
         "motores + eletrónica + servos = total",
         len(h3["juntas"]) == 8 and min(h3["curso"]) > 1.0 and all(b >= a for a, b in zip(e4, e4[1:])) and e4[-1] > 0.0
         and h3["potencia_w"] > 0.0 and abs(soma - pot["total"]) < 1e-6,
         f"curso mín {min(h3['curso']):.0f}° · energia {e4[-1]:.4f} Wh · servos {h3['potencia_w']:.1f} W · "
         f"soma {soma:.2f} = total {pot['total']:.2f} W")
    pecas = env.planta.telemetria_pecas()
    c.ok("[§9] painel de peças: os watts dos servos à parte e a soma bate com o total",
         "watts_servos" in pecas and abs(pecas["watts_motores"] + pecas["watts_eletronica"] + pecas["watts_servos"]
                                         - pecas["watts_total"]) < 0.3, f"{pecas.get('watts_servos')} W de servos")
    voar(1.0, False)
    c.ok("[§9] largar o «seguir»: o pitch pedido ao corpo volta a 0 (nivelado)",
         abs(env.bracos.pitch_corpo_alvo) < 1e-9 and not piloto.mira_art_ativa, f"alvo {env.bracos.pitch_corpo_alvo}")

    class _Args:                                                 # o site manda o `--build` ao runner
        controlo, telemetria, fpv, controlador, sem_janela = "c.json", "t.jsonl", "fpv", "classico", True
        fator_tempo, com_loop, model, build = None, False, None, BUILD
    cmd = sim_site.comando_do_runner(_Args(), modelo)
    hw_site = sim_site.resumo_hardware(sim_site.hardware_do_modelo(modelo, BUILD))
    c.ok("[§9] sim_site.py --build: o runner recebe o build e a ficha do site mostra-o (com braços, e de que build é a "
         "política)", cmd[cmd.index("--build") + 1] == BUILD and hw_site["build"] == BUILD and hw_site["bracos_articulados"]
         and hw_site["build_da_politica"] == "endurance_15pol_p50b", f"{' '.join(cmd[-6:])} · {hw_site['build']}")
    hw_pol = sim_site.hardware_do_modelo(modelo)
    c.ok("[§9] o cockpit voa POR OMISSÃO o drone com braços (pedido do dono): sem --build → articulado; `--build politica` "
         "→ o build da política (rígido); com uma política do cf2 (sem hardware.json) não há build",
         sim_site.resolver_build(None, hw_pol) == sim_site.BUILD_COCKPIT_OMISSAO
         and dr.hardware(sim_site.BUILD_COCKPIT_OMISSAO).bracos is not None
         and sim_site.resolver_build("politica", hw_pol) is None
         and sim_site.resolver_build("endurance_15pol_p50b", hw_pol) == "endurance_15pol_p50b"
         and sim_site.resolver_build(None, None) is None,
         f"omissão → {sim_site.resolver_build(None, hw_pol)} · politica → {sim_site.resolver_build('politica', hw_pol)}")


# ============================================================================================ §8 mutações
def _mut_eixo_x(t: str) -> str:
    antigo = 'j = b.add_joint(name=f"ombro{k}", type=hinge, axis=[0.0, 1.0, 0.0])'
    assert t.count(antigo) == 1
    return t.replace(antigo, 'j = b.add_joint(name=f"ombro{k}", type=hinge, axis=[1.0, 0.0, 0.0])')


def _mut_folga_negativa(t: str) -> str:
    antigo = '"folga_helice_mm": 40.0'
    assert t.count(antigo) == 1
    return t.replace(antigo, '"folga_helice_mm": -60.0')


def _mut_sem_delta(t: str) -> str:
    antigo = "    d = delta_ombro(tau, r_s, l1)\n    return tau + d, -d"
    assert t.count(antigo) == 1
    return t.replace(antigo, "    return tau, 0.0")


def _mut_atrito_baixo(t: str) -> str:
    antigo = '"coef_atrito": 0.1'
    assert t.count(antigo) == 1
    return t.replace(antigo, '"coef_atrito": 0.05')


def _mut_sem_margem_fase(t: str) -> str:
    antigo = '"fc_margem_fase_min_graus": 45,'
    assert t.count(antigo) == 1
    return t.replace(antigo, '')


def _mut_massa_esquecida(t: str) -> str:
    antigo = '"mastros": 4.0 * self.massa_mastro, '
    assert t.count(antigo) == 1
    return t.replace(antigo, '')


MUTACOES = (
    ("eixo-do-ombro-em-x", "lab/drone_rpi/modelo.py", _mut_eixo_x, "eixo = y do corpo"),
    ("folga-da-helice-negativa", "models/drone_rpi/componentes.json", _mut_folga_negativa, "MAIOR do que o raio"),
    ("cinematica-inversa-sem-delta", "experiments/09_drone_hover_rl/bracos_controlo.py", _mut_sem_delta, "mesmo plano"),
    ("sem-fim-reversivel", "models/drone_rpi/componentes.json", _mut_atrito_baixo, "build articulado resolve"),
    ("massa-dos-mastros-esquecida", "lab/drone_rpi/componentes.py", _mut_massa_esquecida, "orçamento de massa"),
    ("fc-sem-margem-de-fase", "models/drone_rpi/builds.json", _mut_sem_margem_fase, "margem de fase ≥ 45°"),
)


def _montar_copia(destino: Path) -> None:
    shutil.copy2(RAIZ / "pyproject.toml", destino / "pyproject.toml")
    shutil.copytree(RAIZ / "lab", destino / "lab", ignore=shutil.ignore_patterns("__pycache__"))
    (destino / "models" / "drone_rpi").mkdir(parents=True)
    for nome in ("componentes.json", "builds.json"):
        shutil.copy2(RAIZ / "models" / "drone_rpi" / nome, destino / "models" / "drone_rpi" / nome)
    exp = destino / "experiments" / "09_drone_hover_rl"
    exp.mkdir(parents=True)
    for nome in ("bracos_controlo.py", "teste_bracos.py", "fc.py", "controlo_classico.py"):
        shutil.copy2(_EXP / nome, exp / nome)


def checa_mutacoes(c: Checagens) -> None:
    _titulo("§8 mutações: o teste NÃO é tautológico (cada mutação, numa CÓPIA, tem de FALHAR a checagem certa)")
    base = Path(tempfile.mkdtemp(prefix="teste_bracos_mut_", dir=os.environ.get("TMPDIR")))
    try:
        def correr(copia: Path) -> subprocess.CompletedProcess:
            return subprocess.run([sys.executable, str(copia / "experiments" / "09_drone_hover_rl" / "teste_bracos.py"),
                                   "--so-estatico", "--fontes", str(copia)],
                                  capture_output=True, text=True, timeout=900, check=False)
        controlo = base / "controlo"
        controlo.mkdir()
        _montar_copia(controlo)
        r0 = correr(controlo)
        c.ok("[§8] controlo: a cópia SEM mutação passa o teste estático", r0.returncode == 0, f"exit {r0.returncode}")
        for nome, rel, mutar, marca in MUTACOES:
            copia = base / nome
            copia.mkdir()
            _montar_copia(copia)
            alvo = copia / rel
            alvo.write_text(mutar(alvo.read_text(encoding="utf-8")), encoding="utf-8")
            r = correr(copia)
            falhas = [ln for ln in r.stdout.splitlines() if "[FALHA]" in ln and marca in ln]
            c.ok(f"[§8] mutação {nome} ({rel}) FALHA na checagem certa ('{marca}')", r.returncode != 0 and bool(falhas),
                 f"exit {r.returncode} · {len(falhas)} falha(s) com a marca")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Prova dos braços articulados e da mira por arfagem.")
    p.add_argument("--mira", action="store_true", help="também o §7 (3 cenários de mira)")
    p.add_argument("--cockpit", action="store_true", help="também o §9 (runner do cockpit com os braços)")
    p.add_argument("--mutacao", action="store_true", help="corre SÓ as mutações (§8)")
    p.add_argument("--so-estatico", action="store_true", help="só §1–§4 (sem simulação; usado pelo §8)")
    p.add_argument("--fontes", type=Path, default=_REPO)
    a = p.parse_args(argv)
    total = Checagens()
    if a.mutacao:
        checa_mutacoes(total)
    else:
        usadas = Path(dr.__file__).resolve().parents[2]
        total.ok("[§0] o teste corre contra as fontes pedidas", usadas == RAIZ, f"lab em {usadas}")
        checa_pecas(total)
        if not any("build articulado resolve" in f for f in total.falhas):
            checa_modelo(total)
            checa_cinematica(total)
            checa_folga(total)
            if not a.so_estatico:
                checa_servos(total)
                checa_autobloqueio(total)
                checa_voo(total)
                if a.mira:
                    checa_mira(total)
                if a.cockpit:
                    checa_cockpit(total)
    print(f"\n[teste] {len(total.linhas) - len(total.falhas)}/{len(total.linhas)} checagens OK", flush=True)
    if total.falhas:
        for nome in total.falhas:
            print(f"[teste] FALHOU: {nome}", flush=True)
        return 1
    print("[teste] braços articulados: peças batem com as fichas, a cinemática fecha, a hélice nunca toca no braço, os servos "
          "respeitam os limites da ficha, o sem-fim segura sem corrente e o corpo arfa para mirar com o drone parado", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
