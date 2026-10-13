#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_vento_classico.py — PROVA da fase 2: a cascata clássica (núcleo C++) CONTRA O VENTO.

Checagens + exit code (0 = tudo OK, 1 = alguma falhou), no estilo dos outros `teste_*.py`:

  §1 FÓRMULAS FECHADAS (sem simulador): os ganhos do observador de perturbação derivados da planta; o observador
     converge para uma perturbação constante com a resposta de polos duplos (1 − (1 + ωt)·e^{−ωt}); o modelo leva o
     empuxo (da atitude) e o arrasto — uma manobra SEM perturbação não é «vento»; a perturbação observada é anulada na
     aceleração pedida e cortada à autoridade da inclinação; sem observador a cascata é a da fase 1; a velocidade do
     fluxo do estimador sem os artefactos da rotação (braço ao CM e alinhamento com o giroscópio); a parametrização da
     «aleatoriedade» do site (`turbulencia_de`: Dryden de baixa altitude, medida no processo de vento do env) e o vento
     pareado (a mesma série de vento para todas as variantes);
  §2 MALHA FECHADA no núcleo C++ em SITL (planta completa do MuJoCo, sementes de CALIBRAÇÃO): degrau de vento, vento
     forte constante, turbulência, seguimento com vento — cada um contra a fase 1 no MESMO binário (contra-prova) —,
     SEM REGRESSÃO em ar parado (pairagem e degrau de comando) e C++ ≡ protótipo Python com vento;
  §3 MUTAÇÕES da fonte C++ (compiladas de verdade) que este teste TEM de apanhar.

As tolerâncias de §2 saem das medições nas sementes de calibração (`avaliar_vento.py --calibrar`, com folga); as de
avaliação (5000…5011) não entram aqui.

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_vento_classico.py [--rapido]
"""
from __future__ import annotations

import argparse
import math
import shutil
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]
from lab import mjkit  # noqa: F401, I001

import numpy as np

import avaliar_classico as ac
import avaliar_nucleo as an
import avaliar_vento as av
import controlo_classico as cc
import sitl
from env import valida_vento_dinamico
from env_real import build_do_hardware
from teste_controlo_classico import Checagens, est_nivel, perto

G = cc.G
SEMENTES = ac.SEMENTES_CALIBRACAO[:4]          # NUNCA as de avaliação
DT = 0.02

# --- tolerâncias da malha fechada (núcleo C++, sementes de calibração 9000…9003; medido → limite, com folga) -------------------
TOL = {
    "degrau_pico": 0.32,            # m — pico do desvio a um degrau de vento de 3 m/s, pior semente (medido 0,21; fase 1: 1,50)
    "degrau_recuperacao": 10.0,     # s — volta a ficar a < 10 cm, pior semente (medido 4,2, pior 7,4; fase 1: 14,4, melhor 13)
    "forte_xy_max": 0.50,           # m — vento constante de 5 m/s: desvio máx. na janela (= CRITERIO; medido 0,25; fase 1: 3,4)
    "forte_xy_voo": 1.00,           # m — idem no voo todo, com a descolagem (= CRITERIO; medido 0,61; fase 1: 3,5)
    "aleatorio_p95": 0.35,          # m — vento ALEATÓRIO do cockpit a 3 m/s, p95 de ‖xy‖ (medido 0,22; fase 1: 1,21)
    "seguimento_rms": 0.45,         # m — plano WASDQE com 3 m/s de lado, ‖xy − p_ref‖ RMS (medido 0,28; fase 1: 2,78)
    "hover_margem": 0.005,          # m — a pairagem em ar parado não piora mais do que isto face à fase 1 (medido −1,8 cm)
    "hover_incl_rms": 0.70,         # ° — agitação da inclinação em ar parado (medido 0,37; fase 1: 0,12)
    "comando_sobressinal": 0.08,    # — degrau de comando 0 → 1 m/s (medido 0,029; fase 1: 0,100)
    "comando_assenta": 2.5,         # s — assentamento a 5 % (medido 0,69; fase 1: 2,8)
    "cpp_python": 0.05,             # — diferença relativa C++ vs Python em malha fechada com vento
}
JOBS = av.JOBS_MAX                  # processos em paralelo (a máquina é partilhada)


def planta_sintetica() -> cc.PlantaLinear:
    """Planta SINTÉTICA com números redondos (as fórmulas fechadas conferem-se à mão), com o sensor de fluxo."""
    return cc.PlantaLinear(omega_taxa=8.0, tau_motor=0.05, alfa_yaw=2.0, inercia_zz=0.5, c_yaw=0.6, u_pairagem=0.6,
                           idle=0.05, dt_decisao=DT, atraso_vel=0.03, braco_fluxo=0.04, atraso_fluxo=4)


def observar(gn: cc.GanhosCascata, v_de_t, segundos: float, pitch: float = 0.0, amostras=()) -> tuple[cc.CascataClassica, dict]:
    """Corre a cascata com as estimativas PRESCRITAS (velocidade do mundo em x = `v_de_t(t)`, inclinação fixa): estuda o
    observador sozinho. Devolve a cascata e d̂_x nos instantes `amostras`."""
    casc = cc.CascataClassica(gn)
    est = est_nivel(pitch=pitch)
    casc.armar(True, est)
    lido = {}
    for i in range(round(segundos / DT)):
        t = i * DT
        est["vx"] = v_de_t(t) * math.cos(pitch)          # corpo: v_bx = v·cosθ (a velocidade vertical do mundo é nula)
        casc.passo(est, (0.0, 0.0, 0.0), {}, DT)
        for a in amostras:
            if abs(t - a) < 0.5 * DT:
                lido[a] = casc.d_obs[0]
    return casc, lido


# ------------------------------------------------------------------------------------------ §1 fórmulas fechadas
def secao_formulas() -> bool:
    c = Checagens("§1 formulas fechadas (sem simulador)")
    p = planta_sintetica()
    gn = cc.GanhosCascata.de_planta(p)

    # ---- ganhos derivados da planta
    c.ok("observador: ω = ω_c/razão_pert (razão 1), limite = g·tan(tilt_max), τ_vel/braço/alinhamento = os do sensor de fluxo",
         perto(gn.w_pert, 8.0) and perto(gn.lim_pert, G * math.tan(gn.tilt_max)) and perto(gn.tau_vel, 0.03)
         and perto(gn.braco_fluxo, 0.04) and gn.atraso_fluxo == 4
         and perto(cc.GanhosCascata.de_planta(p, razao_pert=2.0).w_pert, 4.0),
         f"ω={gn.w_pert:g} rad/s lim={gn.lim_pert:.3f} m/s² τ_vel={gn.tau_vel:g} s")
    try:
        cc.GanhosCascata.de_planta(p, razao_pert=0.0)
        recusa = False
    except ValueError:
        recusa = True
    c.ok("razao_pert ≤ 0 é recusada (ValueError)", recusa)

    # ---- o observador converge para uma perturbação constante, com a resposta de polos duplos
    d, k, w = 1.5, gn.k_arrasto, gn.w_pert
    tempos = [m / w for m in (1, 3, 5)]
    casc, lido = observar(gn, lambda t: d / k * (1.0 - math.exp(-k * t)), 8.0, amostras=tempos)
    teoria = {m: 1.0 - (1.0 + m) * math.exp(-m) for m in (1, 3, 5)}
    medido = {m: lido[m / w] / d for m in (1, 3, 5)}
    c.ok("perturbação constante d (planta v̇ = −d_arr·v + d): d̂ → d (erro < 0,5 %) e a subida é a de polos duplos em −ω, "
         "d̂/d = 1 − (1 + ωt)·e^{−ωt} em t = 1/ω, 3/ω, 5/ω (± 0,06: Euler a 50 Hz)",
         abs(casc.d_obs[0] - d) < 0.005 * d and abs(casc.d_obs[1]) < 1e-12 and all(abs(medido[m] - teoria[m]) < 0.06 for m in teoria),
         " · ".join(f"t={m}/ω: {medido[m]:.3f} (teoria {teoria[m]:.3f})" for m in teoria) + f" · final {casc.d_obs[0]:.4f} vs {d}")

    # ---- o modelo leva o empuxo (da atitude) e o arrasto: uma manobra SEM perturbação não é «vento»
    th = math.radians(10.0)
    a_emp = G * math.tan(th)
    casc_m, _ = observar(gn, lambda t: a_emp / k * (1.0 - math.exp(-k * t)), 8.0, pitch=th)
    pico = 0.0
    casc_t = cc.CascataClassica(gn)
    est = est_nivel(pitch=th)
    casc_t.armar(True, est)
    for i in range(400):
        est["vx"] = a_emp / k * (1.0 - math.exp(-k * i * DT)) * math.cos(th)
        casc_t.passo(est, (0.0, 0.0, 0.0), {}, DT)
        pico = max(pico, abs(casc_t.d_obs[0]))
    c.ok("modelo do observador = empuxo lido da ATITUDE (g·tanθ) − arrasto: a acelerar com 10° de inclinação e SEM perturbação "
         "(v̇ = g·tanθ − d_arr·v), d̂ fica em zero (|d̂| < 0,02 m/s² durante 8 s) — uma manobra não é vento",
         pico < 0.02 and abs(casc_m.d_obs[0]) < 0.02, f"|d̂| máx {pico:.4f} m/s² com a_empuxo = {a_emp:.2f} m/s²")

    # ---- a perturbação observada é ANULADA na aceleração pedida (e só isso muda face à fase 1)
    sem = gn.com(w_pert=0.0)
    ca, cb = cc.CascataClassica(gn), cc.CascataClassica(sem)
    ea = est_nivel()
    ca.armar(True, ea)
    cb.armar(True, ea)
    pior, pior_resto, d_p = 0.0, 0.0, 0.3            # perturbação pequena: a inclinação não satura (o anti-windup não entra)
    for i in range(200):
        ea["vx"] = d_p / k * (1.0 - math.exp(-k * i * DT))
        ea["vy"] = -0.5 * ea["vx"]
        ca.passo(ea, (0.0, 0.0, 0.0), {}, DT)
        cb.passo(ea, (0.0, 0.0, 0.0), {}, DT)
        for j in range(2):
            pior = max(pior, abs((ca.dados["a_des"][j] - cb.dados["a_des"][j]) + ca.d_obs[j]))
        pior_resto = max(pior_resto, abs(ca.dados["a_des"][2] - cb.dados["a_des"][2]), abs(ca.i_vel[0] - cb.i_vel[0]),
                         abs(ca.i_vel[1] - cb.i_vel[1]), abs(ca.i_z - cb.i_z))
    c.ok("a_pedida(com observador) − a_pedida(fase 1) = −d̂ (x e y), e a aceleração vertical e os integrais não mudam",
         pior < 1e-12 and pior_resto < 1e-12 and ca.d_obs[0] > 0.8 * d_p and ca.d_obs[1] < -0.4 * d_p,
         f"|Δa + d̂| máx {pior:.1e} · d̂ = ({ca.d_obs[0]:+.3f}, {ca.d_obs[1]:+.3f}) m/s² para d = ({d_p:+.2f}, {-0.5 * d_p:+.2f})")
    c.ok("SEM observador (w_pert = 0) a cascata é a da fase 1: d̂ ≡ 0 e `dados['pert']` = (0, 0)",
         cb.d_obs == [0.0, 0.0] and cb.dados["pert"] == (0.0, 0.0) and cb.v_obs is None)

    # ---- limite: a autoridade da inclinação
    casc_l, _ = observar(gn, lambda t: 40.0 * t, 6.0)
    c.ok("limite: uma «perturbação» absurda (velocidade a crescer 40 m/s²) fica cortada a ±lim_pert = g·tan(tilt_max)",
         perto(casc_l.d_obs[0], gn.lim_pert, 1e-12), f"d̂ = {casc_l.d_obs[0]:.4f} (limite {gn.lim_pert:.4f})")
    casc_l.armar(False)
    c.ok("desarmar zera o observador (d̂ = 0, modelo por arrancar)", casc_l.d_obs == [0.0, 0.0] and casc_l.v_obs is None)

    # ---- estimador: velocidade do fluxo sem os artefactos da rotação
    def rodar_no_lugar(braco: float, atraso: int) -> float:
        """Rotação PURA em torno do CM (v_cm = 0), sensor de fluxo 4 cm abaixo, amostras de fluxo a 100 Hz com 4 passos
        de atraso face ao giroscópio: devolve max |v̂_x| (devia ser 0)."""
        est = cc.EstimadorClassico(0.002, braco_fluxo=braco, atraso_fluxo=atraso)
        est.reiniciar((0.0, 0.0, G), 1.0, True)
        b_real, n_real, dist = 0.04, 4, 1.0
        q = [0.8 * math.sin(6.0 * 0.002 * j) for j in range(-n_real, 1500)]

        def q_em(j):
            return q[j + n_real]
        fy, pior_v, n_fl = 0.0, 0.0, 0
        for j in range(1500):
            if j % 5 == 0:                                   # amostra nova: o fluxo do instante j − 4 (v_bx = −q·b)
                fy = q_em(j - n_real) * b_real / dist + q_em(j - n_real)
                n_fl += 1
            est.passo((0.0, q_em(j), 0.0), (0.0, 0.0, G), dist, True, 1, (0.0, fy), True, n_fl)
            if j > 400:                                      # (a 1.ª amostra, com a fila ainda vazia, já decaiu)
                pior_v = max(pior_v, abs(est.vx))
        return pior_v
    v_ok, v_sem_braco, v_sem_alinh = rodar_no_lugar(0.04, 4), rodar_no_lugar(0.0, 4), rodar_no_lugar(0.04, 0)
    c.ok("estimador: a rodar NO LUGAR (v_cm = 0) a velocidade do fluxo dá 0 com o braço ao CM e o alinhamento giroscópio/fluxo "
         "certos; sem o braço lê −q·b e sem o alinhamento lê d·(q(t) − q(t − 8 ms))",
         v_ok < 1e-9 and v_sem_braco > 0.02 and v_sem_alinh > 0.02,
         f"|v̂_x| máx: {v_ok:.1e} m/s · sem braço {v_sem_braco:.3f} · sem alinhamento {v_sem_alinh:.3f}")
    try:
        cc.EstimadorClassico(0.002, atraso_fluxo=cc.ATRASO_FLUXO_MAX)
        recusa = False
    except ValueError:
        recusa = True
    c.ok("o alinhamento não cabe na fila do firmware (≥ 16 passos) ⇒ ValueError", recusa)

    # ---- a «aleatoriedade» do site
    razao, l_u = av.dryden_baixa_altitude(1.0)
    c.ok("Dryden de baixa altitude (MIL-F-8785C) a 1 m: σ_u/σ_w = 1/(0,177 + 0,000823·h)^0,4 = 1,99 e L_u = h/(…)^1,2 = 7,84 m "
         "⇒ σ = 0,2·W e L = 8 m", abs(razao - 1.987) < 0.005 and abs(l_u - 7.84) < 0.02 and av.SIGMA_REL_TURBULENCIA == 0.2
         and av.L_TURBULENCIA_M == 8.0, f"σ_u/σ_w = {razao:.3f} · L_u = {l_u:.2f} m")
    t3 = av.turbulencia_de(3.0)
    aceites = all(valida_vento_dinamico(av.turbulencia_de(w)) == av.turbulencia_de(w) for w in av.INTENSIDADES)
    c.ok("turbulencia_de(W) = {modo: dryden, sigma: 0,2·W, L: 8, u_max: W + 3σ = 1,6·W, v_min: 1} e o env aceita-o de 1 a 5 m/s",
         t3 == {"modo": "dryden", "sigma": 0.6000000000000001, "L": 8.0, "u_max": 3.0 + 3 * 0.6000000000000001, "v_min": 1.0}
         and aceites, str(t3))
    g_bom = {"quedas": 0, "xy_max_pior": 0.4, "xy_max_voo_pior": 0.9, "dz_max_pior": 0.1}
    c.ok("critério de «aceitável»: 100 % de sobrevivência E a pior semente dentro dos três limites (uma queda, ou um só limite "
         "passado, chumba)", av.aceitavel(g_bom) and not av.aceitavel({**g_bom, "quedas": 1})
         and not av.aceitavel({**g_bom, "dz_max_pior": 0.31}) and not av.aceitavel({**g_bom, "xy_max_voo_pior": 1.01}))
    return c.fechar()


def secao_vento_do_env() -> bool:
    """O processo de vento do env com a parametrização recomendada (sem física: só `_passo_vento`), e o vento pareado."""
    c = Checagens("§1b a «aleatoriedade» medida no processo de vento do env + vento pareado")
    dados = ac.carregar_rl_dados()

    def serie(seed: int, w: float, consumir: int, n: int = 15000):
        env = ac.criar_env(dados, dr=False, episodio_s=1.0)
        env.definir_vento(w, 90.0, 0.0)
        env.definir_vento_dinamico(av.turbulencia_de(w))
        env.reset(seed=seed)
        vp = av.VentoPareado(env, seed)
        vp.depois_do_reset()
        env.np_random.normal(size=consumir)                 # a planta de uma variante consome mais números do que a de outra
        out = []
        for _ in range(n):
            vp.antes_do_passo()
            out.append(env.vento_atual)
            env.passos += 1                                 # (o relógio do episódio, sem física)
        return np.array(out)
    w = 3.0
    a, b, outra = serie(9000, w, 0), serie(9000, w, 5000), serie(9001, w, 0, 2000)
    c.ok("VENTO PAREADO: a série de vento de uma semente é a MESMA quer a planta tenha consumido 0 ou 5000 números do gerador "
         "(o núcleo calibra 1 s no chão; a RL não) e muda com a semente", np.array_equal(a, b) and not np.array_equal(a[:2000], outra),
         f"{len(a)} passos · max|Δ| {np.abs(a - b).max():.1e}")
    turb = a - np.array([0.0, w, 0.0])
    sigma, tau = av.SIGMA_REL_TURBULENCIA * w, av.L_TURBULENCIA_M / w
    dp = turb[500:].std(axis=0)
    alfa = [float(np.corrcoef(turb[500:-1, j], turb[501:, j])[0, 1]) for j in range(3)]
    alfa_teo = math.exp(-DT * w / av.L_TURBULENCIA_M)
    norma = np.linalg.norm(a, axis=1)
    c.ok(f"turbulencia_de({w:g}) MEDIDA no env (300 s): desvio-padrão por componente = σ = {sigma:.2f} m/s (± 25 %), correlação entre "
         f"passos = exp(−Δt·W/L) = {alfa_teo:.5f} (constante de tempo L/W = {tau:.1f} s) e a norma nunca passa u_max = 1,6·W",
         all(abs(v - sigma) < 0.25 * sigma for v in dp) and all(abs(v - alfa_teo) < 0.003 for v in alfa) and norma.max() <= 1.6 * w + 1e-9,
         f"dp = ({dp[0]:.2f}, {dp[1]:.2f}, {dp[2]:.2f}) m/s · α = ({alfa[0]:.5f}, {alfa[1]:.5f}, {alfa[2]:.5f}) · ‖vento‖ médio {norma.mean():.2f}, "
         f"máx {norma.max():.2f} m/s")

    # ---- ganhos_de_hardware(env) e a Config do núcleo
    env0 = ac.criar_env(dados, dr=False, episodio_s=1.0)
    gn = cc.ganhos_de_hardware(env0)
    fl, gi = env0.hw.sensores["fluxo"], env0.hw.sensores["imu"]["giro"]
    periodo = 1.0 / fl["taxa_hz"]
    tau_vel = fl["atraso_s"] + periodo * (1.0 / cc.ALFA_FLUXO - 1.0) + 0.5 * periodo
    ok = (perto(gn.w_pert, gn.omega_taxa) and perto(gn.tau_vel, tau_vel) and perto(gn.lim_pert, G * math.tan(gn.tilt_max))
          and gn.atraso_fluxo == round((fl["atraso_s"] - gi["atraso_s"]) / env0.dt)
          and perto(gn.braco_fluxo, -float(env0.model.site_pos[env0.model.site("baixo").id][2])))
    c.ok("ganhos_de_hardware(env): ω = ω_c da malha de taxa, τ_vel = atraso + T·(1/α − 1) + T/2 do sensor de fluxo, alinhamento = "
         "(atraso do fluxo − atraso do giroscópio)/dt e braço = altura do CM sobre o site do fluxo", ok,
         f"ω={gn.w_pert:.2f} rad/s τ_vel={1e3 * gn.tau_vel:.1f} ms alinhamento={gn.atraso_fluxo} passos braço={100 * gn.braco_fluxo:.1f} cm")
    envn = an.criar_env_nucleo(dados, dr=False, episodio_s=1.0)
    cfg = envn.nucleo.cfg.cascata
    ok = (sitl.versao_da_interface() >= 3 and abs(cfg.w_pert - gn.w_pert) < 1e-5 and abs(cfg.tau_vel - gn.tau_vel) < 1e-7
          and abs(cfg.lim_pert - gn.lim_pert) < 1e-5 and cfg.atraso_fluxo == gn.atraso_fluxo and abs(cfg.braco_fluxo - gn.braco_fluxo) < 1e-7)
    c.ok("o PADRÃO de `sitl` (o que o site voa: `DroneRealEnvNucleo(modo_nucleo=\"cascata\")`) já traz o observador ligado com os "
         f"mesmos números (interface {sitl.versao_da_interface()})", ok,
         f"Config: w_pert={cfg.w_pert:.3f} lim_pert={cfg.lim_pert:.3f} tau_vel={cfg.tau_vel:.4f} braco_fluxo={cfg.braco_fluxo:.4f} "
         f"atraso_fluxo={cfg.atraso_fluxo}")
    envn.close()
    return c.fechar()


# ------------------------------------------------------------------------------------------ §2 malha fechada
REGIMES_MALHA = ("calmo", "cmd_frente", "degrau_3_lado", "const_5_lado", "natural_3", "seg_const_3")


def media(res: dict, regime: str, variante: str, chave: str) -> float:
    return float(res[regime][variante][chave])


def pior(res: dict, regime: str, variante: str, chave: str) -> float:
    return float(res[regime][variante][chave + "_pior"])


def checagens_malha(res: dict, var: str = "cascata") -> dict[str, tuple[bool, str]]:
    """As checagens de malha fechada da variante `var` (as que as mutações têm de fazer falhar). {nome: (passou, detalhe)}."""
    q = sum(res[r][var]["quedas"] for r in res if var in res[r])
    dg, fo, tu, sg, cm, ca = (res[r][var] for r in ("degrau_3_lado", "const_5_lado", "natural_3", "seg_const_3", "cmd_frente", "calmo"))
    rec = dg["t_recuperacao_s_pior"] if dg["t_recuperacao_s_n"] == dg["n"] - dg["quedas"] else float("inf")
    return {
        "sem_quedas": (q == 0, f"{q} quedas"),
        "degrau_de_vento": (q == 0 and dg["pico_pior"] <= TOL["degrau_pico"] and rec <= TOL["degrau_recuperacao"],
                            f"pico {100 * dg['pico']:.0f} cm (pior {100 * dg['pico_pior']:.0f}) · recuperação {dg['t_recuperacao_s']:.1f} s (pior {rec:.1f})"),
        "vento_forte": (q == 0 and fo["xy_max_pior"] <= TOL["forte_xy_max"] and fo["xy_max_voo_pior"] <= TOL["forte_xy_voo"],
                        f"‖xy‖ máx. {100 * fo['xy_max']:.0f} cm (pior {100 * fo['xy_max_pior']:.0f}) · no voo todo {100 * fo['xy_max_voo_pior']:.0f} cm"),
        "vento_aleatorio": (q == 0 and tu["xy_p95"] <= TOL["aleatorio_p95"],
                            f"‖xy‖ mediana {100 * tu['xy_med']:.1f} cm · p95 {100 * tu['xy_p95']:.1f} cm"),
        "seguimento_com_vento": (q == 0 and sg["xy_rms"] <= TOL["seguimento_rms"], f"‖xy − p_ref‖ RMS {100 * sg['xy_rms']:.1f} cm"),
        "comando": (q == 0 and cm["sobressinal"] <= TOL["comando_sobressinal"] and cm["assenta_5pct_s"] <= TOL["comando_assenta"]
                    and cm["assenta_5pct_s_n"] == cm["n"],
                    f"sobressinal {100 * cm['sobressinal']:.1f} % · assentamento a 5 % {cm['assenta_5pct_s']:.2f} s"),
        "agitacao_em_ar_parado": (q == 0 and ca["incl_rms_graus"] <= TOL["hover_incl_rms"], f"inclinação RMS {ca['incl_rms_graus']:.2f}°"),
    }


def secao_malha(rapido: bool) -> dict:
    c = Checagens("§2 malha fechada: núcleo C++ em SITL, planta completa, sementes de calibração")
    sementes = SEMENTES[:2] if rapido else SEMENTES
    variantes = {"cascata": {"base": "cascata"}, "cascata_fase1": {"base": "cascata_fase1"}}
    t0 = time.perf_counter()
    res = av.avaliar(list(REGIMES_MALHA), variantes, sementes, JOBS, verboso=False)
    py = av.avaliar(["degrau_3_lado"], {"python": {"base": "python"}}, sementes[:2], 2, verboso=False)
    print(f"        ({len(REGIMES_MALHA) * 2 * len(sementes) + 2} episódios em {time.perf_counter() - t0:.0f} s)", flush=True)
    chk = checagens_malha(res)
    f1 = {r: res[r]["cascata_fase1"] for r in REGIMES_MALHA}
    c.ok("o drone não cai em nenhum dos regimes (ar parado, comando, degrau de 3 m/s, 5 m/s constante, turbulência, seguimento)",
         chk["sem_quedas"][0] and sum(f1[r]["quedas"] for r in f1) == 0, chk["sem_quedas"][1])
    c.ok(f"DEGRAU DE VENTO (3 m/s de lado, ligado a meio da pairagem): pico ≤ {100 * TOL['degrau_pico']:.0f} cm e de volta a < 10 cm em "
         f"≤ {TOL['degrau_recuperacao']:g} s em TODAS as sementes", chk["degrau_de_vento"][0], chk["degrau_de_vento"][1])
    c.ok("contra-prova: a fase 1 (mesmo binário, sem observador) faz ≥ 4× esse pico — é o observador que o segura",
         f1["degrau_3_lado"]["pico"] >= 4.0 * TOL["degrau_pico"], f"fase 1: pico {100 * f1['degrau_3_lado']['pico']:.0f} cm")
    c.ok(f"VENTO FORTE (5 m/s constante, desde a descolagem): ‖xy‖ máx. ≤ {100 * TOL['forte_xy_max']:.0f} cm na janela e ≤ "
         f"{100 * TOL['forte_xy_voo']:.0f} cm no voo todo (o critério de «aceitável» do envelope)", chk["vento_forte"][0], chk["vento_forte"][1])
    c.ok("contra-prova: a fase 1 fica a metros (o integral, limitado a 2 m/s², não chega para os 2,1 m/s² do vento)",
         f1["const_5_lado"]["xy_rms"] > 2.0 and f1["const_5_lado"]["i_vel_max"] > 1.99,
         f"fase 1: ‖xy‖ RMS {f1['const_5_lado']['xy_rms']:.2f} m · integral {f1['const_5_lado']['i_vel_max']:.2f} m/s² · "
         f"perturbação {f1['const_5_lado']['pert_max']:.2f} m/s²")
    c.ok(f"VENTO ALEATÓRIO do cockpit (`vento_natural`: 3 m/s + turbulência + rajadas + direção a deambular): p95 de ‖xy‖ ≤ "
         f"{100 * TOL['aleatorio_p95']:.0f} cm (a fase 1 faz ≥ 2× mais)",
         chk["vento_aleatorio"][0] and f1["natural_3"]["xy_p95"] >= 2.0 * res["natural_3"]["cascata"]["xy_p95"],
         chk["vento_aleatorio"][1] + f" · fase 1: p95 {100 * f1['natural_3']['xy_p95']:.1f} cm")
    c.ok(f"SEGUIMENTO de um plano WASDQE com 3 m/s de lado: ‖xy − p_ref‖ RMS ≤ {100 * TOL['seguimento_rms']:.0f} cm (a fase 1 perde > 1,5 m)",
         chk["seguimento_com_vento"][0] and f1["seg_const_3"]["xy_rms"] > 1.5,
         chk["seguimento_com_vento"][1] + f" · fase 1 {f1['seg_const_3']['xy_rms']:.2f} m")
    dh = res["calmo"]["cascata"]["xy_rms"] - f1["calmo"]["xy_rms"]
    c.ok(f"SEM REGRESSÃO em ar parado — pairagem: ‖xy‖ RMS não piora mais de {1000 * TOL['hover_margem']:.0f} mm face à fase 1 e a "
         f"inclinação RMS fica ≤ {TOL['hover_incl_rms']:g}°", dh <= TOL["hover_margem"] and chk["agitacao_em_ar_parado"][0],
         f"{100 * res['calmo']['cascata']['xy_rms']:.1f} cm vs fase 1 {100 * f1['calmo']['xy_rms']:.1f} cm · " + chk["agitacao_em_ar_parado"][1]
         + f" (fase 1 {f1['calmo']['incl_rms_graus']:.2f}°)")
    c.ok(f"SEM REGRESSÃO em ar parado — degrau de COMANDO 0 → 1 m/s: sobressinal ≤ {100 * TOL['comando_sobressinal']:.0f} % e assentamento a "
         f"5 % ≤ {TOL['comando_assenta']:g} s, e não pior do que a fase 1 (+ 2 pontos)",
         chk["comando"][0] and res["cmd_frente"]["cascata"]["sobressinal"] <= f1["cmd_frente"]["sobressinal"] + 0.02,
         chk["comando"][1] + f" · fase 1: {100 * f1['cmd_frente']['sobressinal']:.1f} % / {f1['cmd_frente']['assenta_5pct_s']:.2f} s")
    # C++ ≡ Python com vento (as duas primeiras sementes, semente a semente)
    pc = {x["seed"]: x for x in res["degrau_3_lado"]["cascata"]["por_semente"]}
    pp = {x["seed"]: x for x in py["degrau_3_lado"]["python"]["por_semente"]}
    dif = max(abs(pc[s]["pico"] - pp[s]["pico"]) / pp[s]["pico"] for s in pp)
    c.ok(f"C++ ≡ protótipo Python em malha fechada COM vento (degrau de 3 m/s, semente a semente): pico dentro de {100 * TOL['cpp_python']:.0f} %",
         dif <= TOL["cpp_python"], " · ".join(f"{s}: C++ {100 * pc[s]['pico']:.1f} cm vs Python {100 * pp[s]['pico']:.1f} cm" for s in pp))
    return {"ok": c.fechar(), "res": res}


# ------------------------------------------------------------------------------------------ §3 mutações
MUTACOES = (
    ("cascata.hpp", "const float ax = aff_x + g.k_vel * evx + i_vel_[0] - g.kd_vel * d_filt_[0] - d_obs_[0];",
     "const float ax = aff_x + g.k_vel * evx + i_vel_[0] - g.kd_vel * d_filt_[0] + d_obs_[0];",
     "a perturbação observada SOMA-SE em x em vez de ser anulada", ("comando", "vento_aleatorio", "sem_quedas")),
    ("cascata.hpp", "d_obs_[i] = limita(d_obs_[i] + dt * g.w_pert * g.w_pert * e_o, -g.lim_pert, g.lim_pert);",
     "d_obs_[i] = limita(d_obs_[i] + 0.0f * dt * g.w_pert * g.w_pert * e_o, -g.lim_pert, g.lim_pert);",
     "o estado estendido não integra (o observador nunca vê a perturbação)", ("degrau_de_vento", "vento_forte")),
    ("cascata.hpp", "const float fz_emp = (g.g + az_ref_) / den;", "const float fz_emp = 0.0f * (g.g + az_ref_) / den;",
     "observador SEM o modelo do empuxo (cada inclinação passa a ser «vento»)", ("comando", "degrau_de_vento", "vento_forte", "sem_quedas")),
    ("cascata.hpp", "const float am = dt / (g.tau_vel + dt);", "const float am = 1.0f + 0.0f * g.tau_vel;",
     "modelo do observador SEM o atraso da velocidade medida", ("comando",)),
    ("estimador_classico.hpp", "const float vx_m = s.tof_d * (q_f - s.fluxo[1]) + braco * q_f;",
     "const float vx_m = s.tof_d * (q_f - s.fluxo[1]) - 9.0f * braco * q_f;",
     "braço do sensor de fluxo com o sinal trocado e 9× maior (a rotação entra na velocidade)", ("comando", "agitacao_em_ar_parado", "sem_quedas")),
)


def episodio_mutante(job: dict) -> dict:
    """Um episódio com uma .so MUTANTE do núcleo (função de topo: corre num processo à parte)."""
    bib = sitl.BibliotecaNucleo(Path(job["so"]), Path(job["cabecalho"]))
    dados = ac.carregar_rl_dados()
    regime = av.REGIMES[job["regime"]]
    tarefa = regime["tarefa"]
    T = {"hover": av.T_HOVER, "degrau": av.T_DEGRAU, "seguimento": av.T_SEGUIMENTO, "comando": av.T_COMANDO + av.JANELA_COMANDO + 0.5}[tarefa]
    env = sitl.DroneRealEnvNucleo(build=build_do_hardware(dados)[0], modo_acao="ctbr", comando=True,
                                  comandos_aleatorios=tarefa == "seguimento", episodio_s=T, alvo_z=1.0, modo_nucleo="cascata",
                                  biblioteca=bib, cascata={"u_yaw_por_taxa": an.u_yaw_identificado()})
    reg = av.correr(env, sitl.ControladorNucleo(), job["seed"], T, regime)
    env.close()
    return {**av.metricas(reg, tarefa), "regime": job["regime"], "variante": "cascata", "seed": job["seed"]}


def secao_mutacoes(res_base: dict) -> bool:
    import teste_cascata_nucleo as tcn
    c = Checagens("§3 mutacoes da fonte C++: o teste tem de as APANHAR")
    base = checagens_malha(res_base)
    c.ok("linha de base: o C++ intacto passa TODAS as checagens de malha fechada usadas nas mutações", all(v[0] for v in base.values()),
         " · ".join(f"{k}={v[0]}" for k, v in base.items()))
    tmp = Path(tempfile.mkdtemp(prefix="teste_vento_"))
    try:
        raizes = [tcn._compilar_mutante(i, f, a, n, tmp) for i, (f, a, n, _d, _c) in enumerate(MUTACOES)]
        jobs = []
        for i, raiz in enumerate(raizes):
            if isinstance(raiz, str):
                continue
            so = next((raiz / "out").glob("libnucleo-*.so"))
            jobs += [{"mut": i, "so": str(so), "cabecalho": str(raiz / "nucleo" / "config.hpp"), "regime": r, "seed": s}
                     for r in REGIMES_MALHA for s in SEMENTES[:1]]
        with ProcessPoolExecutor(max_workers=JOBS, initializer=ac._init_worker) as ex:
            saidas = list(ex.map(episodio_mutante, jobs, chunksize=1))
        apanhadas = 0
        for i, ((ficheiro, _a, _n, desc, esperadas), raiz) in enumerate(zip(MUTACOES, raizes, strict=True)):
            if isinstance(raiz, str):
                c.ok(f"mutação «{desc}» ({ficheiro}) aplicável e compilável", False, raiz)
                continue
            res = {r: {"cascata": av.agregar([x for j, x in zip(jobs, saidas, strict=True) if j["mut"] == i and j["regime"] == r],
                                             av.CHAVES[av.REGIMES[r]["tarefa"]])} for r in REGIMES_MALHA}
            for r in res.values():                        # um regime em que o mutante caiu não tem métricas: conta como falha
                for k, v in list(r["cascata"].items()):
                    if isinstance(v, float) and math.isnan(v):
                        r["cascata"][k] = float("inf")
            chk = checagens_malha(res)
            falharam = [k for k, v in chk.items() if not v[0]]
            ok = any(k in falharam for k in esperadas)
            apanhadas += ok
            c.ok(f"MUTAÇÃO «{desc}» ({ficheiro}) é apanhada ({' ou '.join(esperadas)})", ok,
                 "falham: " + (", ".join(f"{k} [{chk[k][1]}]" for k in falharam) if falharam else "NADA — não foi apanhada"))
        c.ok(f"{apanhadas}/{len(MUTACOES)} mutantes da fonte C++ compilados e apanhados (pedidos ≥ 3)", apanhadas == len(MUTACOES))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return c.fechar()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rapido", action="store_true", help="2 sementes na malha fechada e sem as mutações")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    sitl.biblioteca_padrao()                       # compila a .so UMA vez, antes de criar os processos
    ok1 = secao_formulas()
    ok1b = secao_vento_do_env()
    r2 = secao_malha(args.rapido)
    ok3 = True if args.rapido else secao_mutacoes(r2["res"])
    ok = ok1 and ok1b and r2["ok"] and ok3
    print(f"\n{'TUDO OK' if ok else 'HÁ FALHAS'} ({time.perf_counter() - t0:.0f} s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
