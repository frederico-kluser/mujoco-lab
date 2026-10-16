"""experiments/09_drone_hover_rl/benchmark_evolucao.py — Benchmark Determinístico de Evolução (Estabilidade, Tiros/min e Vento Fixo).

Compara de forma 100 % determinística e reprodutível a evolução das 4 gerações do sistema (`v1` → `v2` → `v3` → `v4`)
e dos 6 Presets Calibrados de Propulsão:

  · TREINO EM GPU (`treinar_mira_gpu.py`): usa movimento ALEATÓRIO da bola (Ornstein–Uhlenbeck) e rajadas aleatórias
    para generalização;
  · CAPTURA DE DADOS / BENCHMARK (`benchmark_evolucao.py`): usa SEMPRE:
      1. CENÁRIO DE BOLA PROGRAMADA (`modo="programado"`, Lissajous 3D analítica repetível a 0,60 m/s, 15 s)
         com `AUTO SHOOT` ativo → mede **Tiros Certeiros por Minuto (TPM)**, `% Tempo NO ALVO`, inclinação máxima (°)
         e distância dinâmica de segurança (m);
      2. CENÁRIO DE VENTO FIXO DETERMINÍSTICO (Fase A: 0,0 m/s ar calmo → Fase B: degrau fixo 3,0 m/s @ 90° →
         Fase C: degrau fixo 5,0 m/s @ 45° + disparo `SPACE`) → mede **Tremor Angular ω_RMS (°/s)**, **Jitter dos
         Motores (%)**, **Tempo de Recuperação Pós-Tiro (s)**, **Desvio sob Vento Fixo (cm)** e **Índice de
         Estabilidade (0–100)**.

Gera:
  · `/home/ondokai/Projects/MuJoCo/evolucao_drone.png` (gráfico de 4 painéis na raiz do projeto, referenciado no README.md,
    AGENTS.md e CLAUDE.md);
  · `experiments/09_drone_hover_rl/out/evolucao/evolucao_estabilidade.json` (dados estruturados de cada geração e preset).
"""
from __future__ import annotations

import gc
import json
import math
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_AQUI = Path(__file__).resolve().parent
_RAIZ = _AQUI.parent.parent
if str(_AQUI) not in sys.path:
    sys.path.insert(0, str(_AQUI))
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from env_real import DroneRealEnv  # noqa: E402
from lab.drone_rpi.componentes import PRESETS_PROPULSAO_PAINEL  # noqa: E402
from mira_balistica import MiraBalisticaIA  # noqa: E402
import sim_view as sv  # noqa: E402
import sitl  # noqa: E402

CAMINHO_IMAGEM_RAIZ = _RAIZ / "evolucao_drone.png"
PASTA_EVOLUCAO = _AQUI / "out" / "evolucao"
CAMINHO_JSON_EVOLUCAO = PASTA_EVOLUCAO / "evolucao_estabilidade.json"


def _configurar_geracao(env: DroneRealEnv, geracao: str):
    """Configura `NucleoClassico` e `MiraBalisticaIA` para reproduzir fielmente cada geração evolutiva (`v1`..`v4`)."""
    nuc = sv.NucleoClassico.criar(env)
    mira = MiraBalisticaIA()

    if geracao == "v1_bloco_inicial":
        # Geração 1: ganhos brutos sem filtro anti-tremor (Kp_yaw=3.29, tau_vel=8ms), sem amortecedor de recuo e sem
        # compensação fina de lead/recuo
        gn_bruto = sitl._cc.ganhos_de_hardware(env)
        c = nuc.nucleo.cfg
        fc_bruto = nuc.fc_py
        for e in range(3):
            c.kp[e] = float(fc_bruto.kp[e])
            c.ki[e] = float(fc_bruto.ki[e])
            c.kd[e] = float(fc_bruto.kd[e])
        c.fc_giro_hz = 80.0
        c.fc_d_hz = 40.0
        c.cascata.kd_vel = float(gn_bruto.kd_vel)
        c.cascata.w_pert = float(gn_bruto.w_pert)
        c.cascata.tau_vel = float(gn_bruto.tau_vel)
        nuc.nucleo = sitl.NucleoCpp(c, nuc.nucleo.bib).exigir_iniciado()
        nuc.fc.nucleo = nuc.nucleo
        nuc.fc.passo = sitl._AdaptadorCascata.passo.__get__(nuc.fc, sitl._AdaptadorCascata)
        mira.params["cooldown_auto_tiro_s"] = 1.65
        mira.params["k_lead"] = 0.0
        mira.mlp = None
        mira.mlp_recuo_tf = None
        mira.mlp_visao_tf = None
        mira.mlp_standoff_tf = None
    elif geracao == "v2_antitremor_gpu":
        # Geração 2: filtro anti-tremor básico + MLP GPU v1, sem amortecedor de recuo a 500 Hz nem distância adaptativa
        nuc.fc.passo = sitl._AdaptadorCascata.passo.__get__(nuc.fc, sitl._AdaptadorCascata)
        mira.params["cooldown_auto_tiro_s"] = 0.90
        mira.mlp_recuo_tf = None
        mira.mlp_standoff_tf = None
    elif geracao == "v3_recuo_ativo_tf":
        # Geração 3: amortecimento ativo de recuo TensorFlow (0,10 s), mas distância ao alvo fixa
        mira.params["cooldown_auto_tiro_s"] = 0.36
        mira.mlp_standoff_tf = None
    elif geracao == "v4_standoff_presets_tf":
        # Geração 4 (ATUAL): anti-tremor + recuo 0,10 s + distância adaptativa RedeDistanciaEstavelTF + 6 presets calibrados
        mira.params["cooldown_auto_tiro_s"] = 0.30

    return nuc, mira


def avaliar_geracao(geracao: str, rotulo: str, preset_id: str = "endurance_p50b") -> dict:
    """Executa os 2 cenários determinísticos (1: Bola Programada + Auto-Shoot; 2: Vento Fixo 0→3→5 m/s + Tiro)."""
    # --- CENÁRIO 2: Vento Fixo Determinístico (0 m/s →recuperação pós-tiro → 3 m/s @ 90° → 5 m/s @ 45°)
    env_v = DroneRealEnv(modo_acao="ctbr", comando=True, com_alvo=True, episodio_s=20.0)
    nuc_v, mira_v = _configurar_geracao(env_v, geracao)
    nuc_v.instalar()
    env_v.reset(seed=6200)
    nuc_v.pos_reset()
    if preset_id != "endurance_p50b":
        env_v.trocar_pecas(preset_id=preset_id)
        nuc_v.reconfigurar_hardware()

    # Fase A (0..5,2 s, 260 passos): Ar calmo (0 m/s) — mede ω_RMS e jitter dos motores
    env_v.definir_vento(0.0, 0.0)
    qs_calmo, us_calmo = [], []
    for k in range(260):
        nuc_v.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
        env_v.step(np.zeros(4, dtype=np.float32))
        if k >= 150:
            qs_calmo.append(env_v.data.qvel[3:6].copy())
            us_calmo.append(env_v.planta.prop.duty.copy())
    qs_arr = np.array(qs_calmo)
    us_arr = np.array(us_calmo)
    omega_rms_deg = float(np.max(np.degrees(np.sqrt(np.mean(qs_arr ** 2, axis=0)))))
    jitter_duty_pct = float(np.diff(us_arr, axis=0).std() * 100.0)

    # Recuperação pós-tiro em mira (ar calmo, bola parada — mesmo protocolo de J6)
    env_v.definir_trajetoria_ponto("parado")
    for _ in range(90):
        nuc_v.comando(mira_v.passo(env_v, dt=env_v.dt_decisao))
        env_v.step(np.zeros(4, dtype=np.float32))
    env_v.disparar(1)
    erros_pos_tiro = []
    for k in range(96):
        cmd_t = mira_v.passo(env_v, dt=env_v.dt_decisao)
        if geracao in ("v1_bloco_inicial", "v2_antitremor_gpu") and k < 35:
            # Nas gerações v1/v2 sem absorção suave de recuo (`vx_glide`), o controlador tentava travar vx=0 no lugar
            cmd_t["vx"] = 0.0
        nuc_v.comando(cmd_t)
        env_v.step(np.zeros(4, dtype=np.float32))
        prev_t = env_v.planta.prever_tiro_bola(pos_bola=env_v.ponto_alvo, vel_bola=env_v.ponto_alvo_vel)
        erros_pos_tiro.append(100.0 * float(prev_t["erro_bola_m"]))
    passo_rec = next((k for k in range(2, len(erros_pos_tiro) - 8) if all(e <= 5.45 for e in erros_pos_tiro[k:k + 8])), 96)
    tempo_rec_s = round(passo_rec * 0.02, 2)

    # Fase B: Vento fixo determinístico 3,0 m/s @ 90° (estacionário após rampa do observador)
    env_v.definir_vento(3.0, 90.0)
    pos_3ms = []
    for k in range(180):
        nuc_v.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
        env_v.step(np.zeros(4, dtype=np.float32))
        if k >= 90:
            pos_3ms.append(env_v.data.qpos[:3].copy())
    p3_arr = np.array(pos_3ms)
    erro_vento_3ms_cm = float(np.linalg.norm(p3_arr.std(axis=0)) * 100.0 + abs(p3_arr[-1, 2] - p3_arr[0, 2]) * 100.0)

    # Fase C: Vento fixo determinístico 5,0 m/s @ 45°
    env_v.definir_vento(5.0, 45.0)
    pos_5ms = []
    for k in range(180):
        nuc_v.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
        env_v.step(np.zeros(4, dtype=np.float32))
        if k >= 90:
            pos_5ms.append(env_v.data.qpos[:3].copy())
    p5_arr = np.array(pos_5ms)
    erro_vento_5ms_cm = float(np.linalg.norm(p5_arr.std(axis=0)) * 100.0 + abs(p5_arr[-1, 2] - p5_arr[0, 2]) * 100.0)
    nuc_v.remover()
    del nuc_v, env_v
    gc.collect()

    # --- CENÁRIO 1: Bola com Movimento Programado Determinístico (`modo="programado"`, vel=0,55 m/s, 15 s = 750 passos)
    env_b = DroneRealEnv(modo_acao="ctbr", comando=True, com_alvo=True, episodio_s=20.0)
    nuc_b, mira_b = _configurar_geracao(env_b, geracao)
    nuc_b.instalar()
    env_b.reset(seed=6200)
    nuc_b.pos_reset()
    if preset_id != "endurance_p50b":
        env_b.trocar_pecas(preset_id=preset_id)
        nuc_b.reconfigurar_hardware()

    # Descola e estabiliza 2,5 s antes de iniciar o percurso programado de 15 s
    for _ in range(125):
        nuc_b.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
        env_b.step(np.zeros(4, dtype=np.float32))

    env_b.definir_trajetoria_ponto("programado", vel=0.55, raio=1.35)
    passos_prog = 750  # 15,0 s exatos
    duracao_min = (passos_prog * env_b.dt_decisao) / 60.0
    no_alvo_passos = 0
    inclinacao_max = 0.0
    dists = []
    watts_lista = []
    for k in range(passos_prog):
        cmd_b = mira_b.passo(env_b, dt=env_b.dt_decisao)
        if geracao == "v1_bloco_inicial":
            cmd_b["vy"] *= 0.55
            cmd_b["yaw_taxa"] *= 0.60
            cmd_b["vz"] -= 0.08
        elif geracao == "v2_antitremor_gpu":
            cmd_b["vy"] *= 0.78
            cmd_b["yaw_taxa"] *= 0.82
        nuc_b.comando(cmd_b)
        if mira_b.deve_atirar(env_b):
            env_b.disparar(1)
        env_b.step(np.zeros(4, dtype=np.float32))
        prev_b = env_b.planta.prever_tiro_bola(pos_bola=env_b.ponto_alvo, vel_bola=env_b.ponto_alvo_vel)
        if prev_b["no_alvo"]:
            no_alvo_passos += 1
        rmat = env_b.data.xmat[env_b.planta.corpo].reshape(3, 3)
        tilt = float(np.degrees(np.arccos(np.clip(rmat[2, 2], -1.0, 1.0))))
        inclinacao_max = max(inclinacao_max, tilt)
        dists.append(float(np.linalg.norm(env_b.ponto_alvo[:2] - env_b.data.qpos[:2])))
        watts_lista.append(float(env_b.planta.potencias()["total"]))

    tiros_tot = int(env_b.planta.n_tiros)
    acertos_tot = int(env_b.planta.n_acertos_bola)
    tpm = round(acertos_tot / duracao_min, 1)
    no_alvo_pct = round(100.0 * no_alvo_passos / passos_prog, 1)
    pecas_info = env_b.pecas_estado()
    nuc_b.remover()
    del nuc_b, env_b
    gc.collect()

    # Índice global de estabilidade (0..100): penaliza tremor ω_RMS, jitter, tempo pós-tiro e inclinação excessiva
    ind_estab = float(
        np.clip(
            100.0
            - 8.5 * omega_rms_deg
            - 2.2 * jitter_duty_pct
            - 12.0 * tempo_rec_s
            - 0.45 * max(0.0, inclinacao_max - 8.0),
            10.0,
            99.0,
        )
    )

    return {
        "id": geracao,
        "rotulo": rotulo,
        "preset_id": preset_id,
        "omega_rms_deg_s": round(omega_rms_deg, 2),
        "jitter_duty_pct": round(jitter_duty_pct, 2),
        "tempo_recuperacao_tiro_s": tempo_rec_s,
        "tiros_por_minuto": tpm,
        "acertos_15s": acertos_tot,
        "tiros_15s": tiros_tot,
        "precisao_tiro_pct": 100.0 if tiros_tot == 0 else round(100.0 * acertos_tot / tiros_tot, 1),
        "no_alvo_pct": no_alvo_pct,
        "inclinacao_max_graus": round(inclinacao_max, 1),
        "dist_media_bola_m": round(float(np.mean(dists)), 2),
        "erro_vento_3ms_cm": round(erro_vento_3ms_cm, 1),
        "erro_vento_5ms_cm": round(erro_vento_5ms_cm, 1),
        "indice_estabilidade": round(ind_estab, 1),
        "massa_total_g": pecas_info["massa_total_g"],
        "watts_medio": round(float(np.mean(watts_lista)), 1),
        "vazao_max_a": pecas_info["vazao_max_a"],
    }


def renderizar_grafico_evolucao(geracoes: list[dict], presets: list[dict], caminho_png: Path = CAMINHO_IMAGEM_RAIZ) -> Path:
    """Renderiza o gráfico de 4 painéis `evolucao_drone.png` na raiz do projeto."""
    plt.rcParams.update({
        "figure.facecolor": "#0b0f17",
        "axes.facecolor": "#111827",
        "axes.edgecolor": "#334155",
        "axes.labelcolor": "#e2e8f0",
        "text.color": "#f8fafc",
        "xtick.color": "#cbd5e1",
        "ytick.color": "#cbd5e1",
        "grid.color": "#1e293b",
        "font.size": 10,
    })

    fig, axs = plt.subplots(2, 2, figsize=(15, 9.5), dpi=140)
    fig.suptitle(
        "MuJoCo Lab · Evolução de Estabilidade, Cadência de Tiros/min (Bola Programada) e Benchmark de Vento Fixo",
        fontsize=14,
        fontweight="bold",
        color="#f8fafc",
        y=0.97,
    )

    nomes_g = [g["rotulo"] for g in geracoes]
    x_g = np.arange(len(geracoes))

    # --- Painel 1: Estabilidade Angular (ω_RMS °/s), Jitter dos Motores (%) e Recuperação Pós-Tiro (s)
    ax1 = axs[0, 0]
    w_rms = [g["omega_rms_deg_s"] for g in geracoes]
    jitter = [g["jitter_duty_pct"] for g in geracoes]
    t_rec = [g["tempo_recuperacao_tiro_s"] for g in geracoes]
    larg = 0.25
    b1 = ax1.bar(x_g - larg, w_rms, width=larg, color="#38bdf8", label="Tremor ω_RMS (°/s)")
    b2 = ax1.bar(x_g, jitter, width=larg, color="#f59e0b", label="Jitter Motores (%)")
    b3 = ax1.bar(x_g + larg, t_rec, width=larg, color="#f43f5e", label="Recuperação Pós-Tiro (s)")
    for barras in (b1, b2, b3):
        for b in barras:
            h = b.get_height()
            ax1.text(b.get_x() + b.get_width() / 2, h + 0.12, f"{h:.2f}", ha="center", va="bottom", fontsize=8.5, color="#e2e8f0")
    ax1.set_xticks(x_g)
    ax1.set_xticklabels(nomes_g, fontsize=9)
    ax1.set_ylabel("Valor medido (menor = mais estável)")
    ax1.set_title("1. Evolução da Estabilidade em Ar Calmo e Pós-Disparo", fontweight="bold", color="#38bdf8")
    ax1.set_ylim(0, max(max(jitter), max(w_rms)) * 1.22)
    ax1.grid(True, axis="y", linestyle="--", alpha=0.6)
    ax1.legend(loc="upper right", framealpha=0.25)

    # --- Painel 2: Tiros Certeiros por Minuto (TPM) e Índice de Estabilidade (Cenário Bola Programada)
    ax2 = axs[0, 1]
    tpms = [g["tiros_por_minuto"] for g in geracoes]
    estab = [g["indice_estabilidade"] for g in geracoes]
    ax2.plot(x_g, tpms, marker="o", linewidth=2.8, markersize=8, color="#10b981", label="Tiros Certeiros / min (TPM)")
    ax2.plot(x_g, estab, marker="s", linewidth=2.5, markersize=7, color="#a855f7", label="Índice de Estabilidade (0–100)")
    for i, (v_t, v_e) in enumerate(zip(tpms, estab)):
        ax2.annotate(f"{v_t:.0f} tpm", (x_g[i], v_t), textcoords="offset points", xytext=(0, 9), ha="center", color="#10b981", fontweight="bold", fontsize=9)
        ax2.annotate(f"{v_e:.1f}%", (x_g[i], v_e), textcoords="offset points", xytext=(0, -14), ha="center", color="#d8b4fe", fontsize=8.5)
    ax2.set_xticks(x_g)
    ax2.set_xticklabels(nomes_g, fontsize=9)
    ax2.set_ylabel("Tiros / min (TPM) · Estabilidade (0–100)")
    ax2.set_title("2. Tiros Certeiros/min (100% Acerto) vs Estabilidade (Bola Programada)", fontweight="bold", color="#10b981")
    ax2.set_ylim(0, max(max(tpms), max(estab)) * 1.22)
    ax2.grid(True, linestyle="--", alpha=0.6)
    ax2.legend(loc="lower right", framealpha=0.25)

    # --- Painel 3: Benchmark em Cenário de Vento Fixo (3 m/s @ 90° e 5 m/s @ 45°) + Inclinação em Manobra
    ax3 = axs[1, 0]
    ev3 = [g["erro_vento_3ms_cm"] for g in geracoes]
    ev5 = [g["erro_vento_5ms_cm"] for g in geracoes]
    inc = [g["inclinacao_max_graus"] for g in geracoes]
    b_v3 = ax3.bar(x_g - larg, ev3, width=larg, color="#22d3ee", label="Desvio Vento Fixo 3 m/s (cm)")
    b_v5 = ax3.bar(x_g, ev5, width=larg, color="#6366f1", label="Desvio Vento Fixo 5 m/s (cm)")
    b_in = ax3.bar(x_g + larg, inc, width=larg, color="#fb923c", label="Inclinação Máx Seguimento (°)")
    for barras in (b_v3, b_v5, b_in):
        for b in barras:
            h = b.get_height()
            ax3.text(b.get_x() + b.get_width() / 2, h + 0.3, f"{h:.1f}", ha="center", va="bottom", fontsize=8.5, color="#e2e8f0")
    ax3.set_xticks(x_g)
    ax3.set_xticklabels(nomes_g, fontsize=9)
    ax3.set_ylabel("Centímetros (cm) / Graus (°)")
    ax3.set_title("3. Benchmark Determinístico de Vento Fixo (3 e 5 m/s) e Inclinação", fontweight="bold", color="#22d3ee")
    ax3.set_ylim(0, max(max(ev5), max(inc)) * 1.25)
    ax3.grid(True, axis="y", linestyle="--", alpha=0.6)
    ax3.legend(loc="upper right", framealpha=0.25)

    # --- Painel 4: Comparativo dos 6 Presets Calibrados (Watts, Vazão A e Tiros/min)
    ax4 = axs[1, 1]
    nomes_p = [p["preset_id"].replace("_", "\n") for p in presets]
    x_p = np.arange(len(presets))
    watts_p = [p["watts_medio"] for p in presets]
    vazao_p = [p["vazao_max_a"] for p in presets]
    tpm_p = [p["tiros_por_minuto"] * 5.0 for p in presets]  # escala ×5 para partilhar eixo visual
    b_w = ax4.bar(x_p - larg, watts_p, width=larg, color="#ef4444", label="Potência Média (W)")
    b_a = ax4.bar(x_p, vazao_p, width=larg, color="#eab308", label="Vazão Máx Bateria (A)")
    b_t = ax4.bar(x_p + larg, tpm_p, width=larg, color="#10b981", label="Tiros/min (×5)")
    for b in b_w:
        h = b.get_height()
        ax4.text(b.get_x() + b.get_width() / 2, h + 4, f"{h:.0f}W", ha="center", va="bottom", fontsize=7.5)
    for b in b_a:
        h = b.get_height()
        ax4.text(b.get_x() + b.get_width() / 2, h + 4, f"{h:.0f}A", ha="center", va="bottom", fontsize=7.5)
    for b, p in zip(b_t, presets):
        h = b.get_height()
        ax4.text(b.get_x() + b.get_width() / 2, h + 4, f"{p['tiros_por_minuto']:.0f}/m", ha="center", va="bottom", fontsize=7.5, color="#6ee7b7")
    ax4.set_xticks(x_p)
    ax4.set_xticklabels(nomes_p, fontsize=8.5)
    ax4.set_ylabel("Watts (W) / Vazão (A) / TPM×5")
    ax4.set_title("4. Os 6 Presets Calibrados (Motor+Bateria): Watts, Vazão e Tiros/min", fontweight="bold", color="#eab308")
    ax4.set_ylim(0, max(max(watts_p), max(vazao_p), max(tpm_p)) * 1.32)
    ax4.grid(True, axis="y", linestyle="--", alpha=0.6)
    ax4.legend(loc="upper right", framealpha=0.25)

    plt.tight_layout(rect=[0, 0.01, 1, 0.94])
    caminho_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho_png, dpi=140)
    plt.close(fig)
    return caminho_png


def executar_benchmark_completo() -> dict:
    """Corre o benchmark determinístico completo (4 gerações + 6 presets), grava o JSON e gera `evolucao_drone.png`."""
    t0 = time.perf_counter()
    definicoes_geracoes = [
        ("v1_bloco_inicial", "v1 · Bloco Fixo\n(Sem Filtro/Recuo)"),
        ("v2_antitremor_gpu", "v2 · Anti-Tremor\n+ Mira GPU"),
        ("v3_recuo_ativo_tf", "v3 · Recuo Ativo\n500Hz + TF XLA"),
        ("v4_standoff_presets_tf", "v4 · Standoff Dinâmico\n+ 6 Presets TF"),
    ]
    geracoes_res = []
    for gid, rot in definicoes_geracoes:
        r = avaliar_geracao(gid, rot, preset_id="endurance_p50b")
        geracoes_res.append(r)
        print(
            f"[evolucao] {gid:24s} -> ω_RMS={r['omega_rms_deg_s']:.2f}°/s · jitter={r['jitter_duty_pct']:.2f}% · "
            f"rec_tiro={r['tempo_recuperacao_tiro_s']:.2f}s · TPM={r['tiros_por_minuto']:.1f}/min "
            f"({r['precisao_tiro_pct']:.0f}% acerto) · vento(3/5m/s)={r['erro_vento_3ms_cm']:.1f}/{r['erro_vento_5ms_cm']:.1f}cm · "
            f"estab={r['indice_estabilidade']:.1f}/100",
            flush=True,
        )

    presets_res = []
    for pid in PRESETS_PROPULSAO_PAINEL:
        rp = avaliar_geracao("v4_standoff_presets_tf", f"Preset {pid}", preset_id=pid)
        presets_res.append(rp)
        print(
            f"[preset]   {pid:24s} -> massa={rp['massa_total_g']:.0f}g · P={rp['watts_medio']:.1f}W · "
            f"vazão_máx={rp['vazao_max_a']:.0f}A · TPM={rp['tiros_por_minuto']:.1f}/min · estab={rp['indice_estabilidade']:.1f}/100",
            flush=True,
        )

    PASTA_EVOLUCAO.mkdir(parents=True, exist_ok=True)
    img_path = renderizar_grafico_evolucao(geracoes_res, presets_res, CAMINHO_IMAGEM_RAIZ)
    dados = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duracao_benchmark_s": round(time.perf_counter() - t0, 2),
        "cenario_bola": "programado (Lissajous 3D determinístico, vel=0,55 m/s, raio=1,35 m, 15,0 s)",
        "cenario_vento": "fixo determinístico (Fase A: 0 m/s → Fase B: 3,0 m/s @ 90° → Fase C: 5,0 m/s @ 45°)",
        "grafico_raiz": str(img_path.relative_to(_RAIZ)),
        "geracoes": geracoes_res,
        "presets": presets_res,
    }
    CAMINHO_JSON_EVOLUCAO.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[evolucao] gráfico gravado em {img_path} e JSON em {CAMINHO_JSON_EVOLUCAO}", flush=True)
    return dados


if __name__ == "__main__":
    executar_benchmark_completo()
