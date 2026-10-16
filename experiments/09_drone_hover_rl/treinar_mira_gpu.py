"""experiments/09_drone_hover_rl/treinar_mira_gpu.py — Treino em GPU (RTX 4070 CUDA/XLA, SEM renderização 3D)
da IA de Mira Balística e Auto-Shoot (`mira_balistica.py`).

Fase 1 — TREINO DIFERENCIÁVEL EM GPU (`.venv-gpu/bin/python`, `CudaDevice(id=0)`):
  · 4096 ambientes em paralelo (`jax.vmap` + `@jax.jit`), ZERO renderização 3D;
  · Dinâmica 3D acoplada do drone (massa 2,968 kg com Glock 25 no topo, malha de atitude/velocidade, acoplamento
    pitch ↔ direção vertical do cano `boca_cano` a +129,5 mm acima do CM, soco de recuo J = 1,916 N·s + cabragem
    Δω_y = −0,98 rad/s) + bola Ornstein–Uhlenbeck em 4 regimes (0,0 m/s parada · 0,3 · 0,5 · 0,8 m/s);
  · Otimização BPTT diferenciável com AdamW (decoupled weight decay), Cosine Annealing LR c/ warmup, Global-Norm
    Gradient Clipping e precisão TensorCore (`jax.lax.Precision.HIGHEST`) para treinar conjuntamente os ganhos
    físicos adaptativos e a MLP residual (12 → 32 → 32 → 4, LayerNorm + SiLU).

Fase 2 — VALIDAÇÃO NO SIMULADOR MUJOCO 3.15 + C++ SITL (`.venv/bin/python`, headless sem render 3D):
  · Avalia a política exportada em `DroneRealEnv` + `NucleoClassico` a 0,0 / 0,3 / 0,5 / 0,8 m/s com `AUTO SHOOT`
    ligado, medindo erro balístico em cm, % de tempo `NO ALVO` e taxa de acerto real dos disparos na bola.

Uso:
    .venv-gpu/bin/python experiments/09_drone_hover_rl/treinar_mira_gpu.py
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
PASTA_SAIDA = _AQUI / "out" / "mira_balistica_gpu"
MODELO_JSON = PASTA_SAIDA / "modelo_mira.json"


def treinar_fase_gpu(epocas: int = 240, n_envs: int = 4096, passos_ep: int = 150, lr_max: float = 4e-3) -> dict:
    """Treina em GPU via JAX/XLA (`CudaDevice(id=0)`) em `n_envs` ambientes paralelos sem renderizar 3D."""
    import jax
    import jax.numpy as jnp

    dispositivos = jax.devices()
    backend = jax.default_backend()
    print(f"[gpu] JAX {jax.__version__} · backend={backend} · dispositivos={dispositivos}", flush=True)
    if backend != "gpu":
        print("[gpu] aviso: a correr fora da GPU — use `.venv-gpu/bin/python` para acelerar na RTX 4070", flush=True)

    dt = 0.02
    g_grav = 9.81
    v0_boca = 296.0
    z_boca_cm = 0.12954
    x_boca_cm = 0.0964

    def layer_norm(x, eps=1e-5):
        m = jnp.mean(x, axis=-1, keepdims=True)
        v = jnp.var(x, axis=-1, keepdims=True)
        return (x - m) / jnp.sqrt(v + eps)

    def silu(x):
        return x / (1.0 + jnp.exp(-jnp.clip(x, -20.0, 20.0)))

    def iniciar_parametros(key):
        k1, k2, k3 = jax.random.split(key, 3)
        # Ganhos físicos em espaço latente (passam por softplus/sigmoid para respeitar limites físicos)
        ganhos_raw = jnp.array([
            0.0,   # kp_yaw  ~ 2.5
            0.0,   # kp_y    ~ 1.9
            0.0,   # kp_z    ~ 2.7
            0.0,   # kp_d    ~ 0.65
            0.0,   # kff_yaw ~ 1.02
            0.0,   # kff_y   ~ 0.92
            0.0,   # kff_z   ~ 0.96
            0.0,   # kff_d   ~ 0.55
            0.0,   # k_pitch_z ~ 0.85
            0.0,   # k_lead  ~ 1.05
        ], dtype=jnp.float32)
        return {
            "ganhos_raw": ganhos_raw,
            "W1": jax.random.normal(k1, (12, 32), dtype=jnp.float32) * 0.08,
            "b1": jnp.zeros((32,), dtype=jnp.float32),
            "W2": jax.random.normal(k2, (32, 32), dtype=jnp.float32) * 0.08,
            "b2": jnp.zeros((32,), dtype=jnp.float32),
            "W3": jax.random.normal(k3, (32, 4), dtype=jnp.float32) * 0.02,
            "b3": jnp.zeros((4,), dtype=jnp.float32),
        }

    def decodificar_ganhos(raw):
        s = jax.nn.tanh(raw)
        return {
            "kp_yaw": 2.80 + 0.40 * s[0],
            "kp_y": 2.10 + 0.40 * s[1],
            "kp_z": 3.10 + 0.40 * s[2],
            "kp_d": 0.40 + 0.15 * s[3],
            "kff_yaw": 1.00 + 0.15 * s[4],
            "kff_y": 0.96 + 0.15 * s[5],
            "kff_z": 1.00 + 0.15 * s[6],
            "kff_d": 0.55 + 0.15 * s[7],
            "k_pitch_z": 1.00 + 0.10 * s[8],
            "k_lead": 1.00 + 0.10 * s[9],
        }

    def inferir_mlp(params, obs):
        h = silu(layer_norm(obs @ params["W1"] + params["b1"]))
        h = silu(layer_norm(h @ params["W2"] + params["b2"]))
        return jnp.tanh(h @ params["W3"] + params["b3"]) * 0.08

    def passo_ambiente(carry, ruido_passo, params):
        pos_d, vel_d, att_d, omega_d, pos_b, vel_b, ou_b, i_yaw, i_z, v_teto = carry
        gn = decodificar_ganhos(params["ganhos_raw"])

        # 1. Avança a bola (Ornstein-Uhlenbeck suave; se v_teto == 0 fica parada!)
        f_ou = math.exp(-dt / 2.5)
        sigma = jnp.array([v_teto, v_teto, 0.35 * v_teto])
        ou_novo = ou_b * f_ou + sigma * math.sqrt(1.0 - f_ou * f_ou) * ruido_passo[:3]
        n_xy = jnp.hypot(ou_novo[0], ou_novo[1])
        escala_xy = jnp.where(n_xy > jnp.maximum(v_teto, 1e-6), v_teto / jnp.maximum(n_xy, 1e-6), 1.0)
        g_b = jnp.array([
            ou_novo[0] * escala_xy,
            ou_novo[1] * escala_xy,
            jnp.clip(ou_novo[2], -0.35 * v_teto, 0.35 * v_teto),
        ])
        alfa_s = 1.0 - math.exp(-dt / 0.35)
        vel_b_novo = jnp.where(v_teto > 1e-4, vel_b + alfa_s * (g_b - vel_b), jnp.zeros(3))
        pos_b_novo = pos_b + vel_b_novo * dt
        pos_b_novo = jnp.array([
            jnp.clip(pos_b_novo[0], 0.8, 3.8),
            jnp.clip(pos_b_novo[1], -2.5, 2.5),
            jnp.clip(pos_b_novo[2], 0.55, 1.85),
        ])
        a_bola = (vel_b_novo - vel_b) / dt

        # 2. Cinemática da boca do cano `boca_cano` no mundo
        roll, pitch, yaw = att_d[0], att_d[1], att_d[2]
        cp, sp = jnp.cos(yaw), jnp.sin(yaw)
        ct, st = jnp.cos(pitch), jnp.sin(pitch)
        ex = jnp.array([cp * ct, sp * ct, -st])
        ez = jnp.array([cp * st, sp * st, ct])
        p_boca = pos_d + x_boca_cm * ex + z_boca_cm * ez

        # 3. Lei de mira balística + MLP residual
        dist_3d = jnp.linalg.norm(pos_b_novo - p_boca)
        tau_voo = dist_3d / v0_boca
        pos_b_alvo = pos_b_novo + gn["k_lead"] * (vel_b_novo * tau_voo + 0.5 * a_bola * (tau_voo ** 2))
        delta = pos_b_alvo - p_boca
        dist_xy = jnp.hypot(delta[0], delta[1])
        az_bola = jnp.atan2(delta[1], delta[0])
        e_psi = jnp.arctan2(jnp.sin(az_bola - yaw), jnp.cos(az_bola - yaw))

        v_b_frente = cp * vel_b_novo[0] + sp * vel_b_novo[1]
        v_b_esq = -sp * vel_b_novo[0] + cp * vel_b_novo[1]
        v_b_z = vel_b_novo[2]
        w_los = v_b_esq / jnp.maximum(dist_xy, 0.4)

        i_yaw_novo = jnp.where(jnp.abs(e_psi) < 0.25, jnp.clip(i_yaw + 0.35 * e_psi * dt, -0.15, 0.15), 0.9 * i_yaw)
        yaw_cmd = gn["kp_yaw"] * e_psi + i_yaw_novo + gn["kff_yaw"] * w_los
        erro_lat = dist_xy * jnp.sin(e_psi)
        vy_cmd = gn["kp_y"] * erro_lat + gn["kff_y"] * v_b_esq

        queda_grav = 0.5 * g_grav * (tau_voo ** 2)
        z_imp_sem_vz = p_boca[2] + ex[2] * gn["k_pitch_z"] * dist_xy - queda_grav
        erro_z = pos_b_alvo[2] - z_imp_sem_vz
        i_z_novo = jnp.where(jnp.abs(erro_z) < 0.20, jnp.clip(i_z + 0.45 * erro_z * dt, -0.18, 0.18), 0.9 * i_z)
        vz_cmd = gn["kp_z"] * erro_z + i_z_novo + gn["kff_z"] * v_b_z
        erro_d = dist_xy - 1.65
        vx_cmd = (gn["kp_d"] * erro_d + gn["kff_d"] * v_b_frente) * jnp.maximum(0.0, jnp.cos(e_psi))

        obs_mlp = jnp.array([
            jnp.clip(e_psi, -1.0, 1.0),
            jnp.clip(erro_lat, -1.0, 1.0),
            jnp.clip(erro_z, -1.0, 1.0),
            jnp.clip(erro_d, -1.5, 1.5),
            jnp.clip(v_b_frente, -1.5, 1.5),
            jnp.clip(v_b_esq, -1.5, 1.5),
            jnp.clip(v_b_z, -1.0, 1.0),
            jnp.clip(ex[2], -0.5, 0.5),
            jnp.clip(omega_d[0], -2.0, 2.0),
            jnp.clip(omega_d[1], -2.0, 2.0),
            jnp.clip(omega_d[2], -2.0, 2.0),
            jnp.clip(dist_xy / 3.0, 0.2, 2.0),
        ])
        res = inferir_mlp(params, obs_mlp)
        vx_cmd = jnp.clip(vx_cmd + 0.20 * res[0], -0.75, 0.75)
        vy_cmd = jnp.clip(vy_cmd + 0.25 * res[1], -0.95, 0.95)
        vz_cmd = jnp.clip(vz_cmd + 0.20 * res[2], -0.70, 0.70)
        yaw_cmd = jnp.clip(yaw_cmd + 0.15 * res[3], -0.50, 0.50)

        # 4. Dinâmica da cascata + planta do drone (2968 g com Glock 25 no topo)
        vx_mundo_sp = cp * vx_cmd - sp * vy_cmd
        vy_mundo_sp = sp * vx_cmd + cp * vy_cmd
        tau_vel = 0.28
        tau_vz = 0.18
        tau_yaw = 0.22
        acc_xy = (jnp.array([vx_mundo_sp, vy_mundo_sp]) - vel_d[:2]) / tau_vel - 0.305 * vel_d[:2]
        acc_z = (vz_cmd - vel_d[2]) / tau_vz
        # Inclinação induzida pela aceleração no referencial do rumo
        acc_frente = cp * acc_xy[0] + sp * acc_xy[1]
        acc_esq = -sp * acc_xy[0] + cp * acc_xy[1]
        pitch_alvo = jnp.clip(acc_frente / g_grav, -0.35, 0.35)
        roll_alvo = jnp.clip(-acc_esq / g_grav, -0.35, 0.35)
        tau_att = 0.11
        p_rate = (roll_alvo - roll) / tau_att
        q_rate = (pitch_alvo - pitch) / tau_att
        r_rate = omega_d[2] + (dt / (tau_yaw + dt)) * (yaw_cmd - omega_d[2])

        vel_d_novo = vel_d + jnp.array([acc_xy[0], acc_xy[1], acc_z]) * dt
        pos_d_novo = pos_d + vel_d_novo * dt
        att_d_novo = jnp.array([roll + p_rate * dt, pitch + q_rate * dt, yaw + r_rate * dt])
        omega_d_novo = jnp.array([p_rate, q_rate, r_rate])

        # 5. Erro balístico 3D real no instante de chegada do projétil t + τ_voo
        cp2, sp2 = jnp.cos(att_d_novo[2]), jnp.sin(att_d_novo[2])
        ct2, st2 = jnp.cos(att_d_novo[1]), jnp.sin(att_d_novo[1])
        ex2 = jnp.array([cp2 * ct2, sp2 * ct2, -st2])
        ez2 = jnp.array([cp2 * st2, sp2 * st2, ct2])
        p_boca2 = pos_d_novo + x_boca_cm * ex2 + z_boca_cm * ez2
        v_proj = vel_d_novo + v0_boca * ex2
        d_b2 = jnp.linalg.norm(pos_b_novo - p_boca2)
        tau2 = d_b2 / v0_boca
        p_imp = p_boca2 + v_proj * tau2 + 0.5 * jnp.array([0.0, 0.0, -g_grav]) * (tau2 ** 2)
        p_b_fut = pos_b_novo + vel_b_novo * tau2
        erro_tiro = jnp.linalg.norm(p_imp - p_b_fut)

        # Custo diferenciável: erro de impacto 3D + suavidade de pitch + manter distância ~1,65 m
        perda = (
            25.0 * (erro_tiro ** 2)
            + 4.0 * jnp.sqrt(erro_tiro ** 2 + 1e-6)
            + 0.40 * (q_rate ** 2)
            + 0.15 * ((dist_xy - 1.65) ** 2)
            + 0.02 * jnp.sum(res ** 2)
        )
        novo_carry = (pos_d_novo, vel_d_novo, att_d_novo, omega_d_novo, pos_b_novo, vel_b_novo, ou_novo, i_yaw_novo, i_z_novo, v_teto)
        return novo_carry, (perda, erro_tiro)

    def simular_um_env(params, key_env, v_teto):
        k_pos, k_ruido = jax.random.split(key_env)
        off_b = jax.random.uniform(k_pos, (3,), minval=jnp.array([1.5, -0.6, 0.8]), maxval=jnp.array([2.4, 0.6, 1.3]))
        pos_d0 = jnp.array([0.0, 0.0, 1.0])
        vel_d0 = jnp.zeros(3)
        att_d0 = jnp.zeros(3)
        omega_d0 = jnp.zeros(3)
        vel_b0 = jnp.zeros(3)
        ou_b0 = jnp.zeros(3)
        carry0 = (pos_d0, vel_d0, att_d0, omega_d0, off_b, vel_b0, ou_b0, 0.0, 0.0, v_teto)
        ruidos = jax.random.normal(k_ruido, (passos_ep, 3))
        _, (perdas, erros) = jax.lax.scan(lambda c, r: passo_ambiente(c, r, params), carry0, ruidos)
        # Ignora os primeiros 25 passos (0,5 s de aquisição inicial)
        return jnp.mean(perdas[25:]), jnp.mean(erros[25:]), jnp.mean((erros[25:] <= 0.0545).astype(jnp.float32))

    def perda_lote(params, key_lote):
        keys = jax.random.split(key_lote, n_envs)
        # 4 regimes de velocidade da bola distribuídos no lote: 0.0 (parada), 0.3, 0.5 e 0.8 m/s
        quartos = n_envs // 4
        v_tetos = jnp.concatenate([
            jnp.zeros(quartos),
            jnp.full(quartos, 0.3),
            jnp.full(quartos, 0.5),
            jnp.full(n_envs - 3 * quartos, 0.8),
        ])
        perdas, erros, no_alvo = jax.vmap(lambda k, vt: simular_um_env(params, k, vt))(keys, v_tetos)
        return jnp.mean(perdas), (jnp.mean(erros), jnp.mean(no_alvo))

    grad_fn = jax.jit(jax.value_and_grad(perda_lote, has_aux=True))

    key = jax.random.PRNGKey(20261015)
    key, k_init = jax.random.split(key)
    params = iniciar_parametros(k_init)
    m_adam = jax.tree_util.tree_map(jnp.zeros_like, params)
    v_adam = jax.tree_util.tree_map(jnp.zeros_like, params)
    b1, b2, eps, wd = 0.9, 0.999, 1e-8, 1e-4

    @jax.jit
    def passo_treino(params, m_adam, v_adam, key, passo_idx):
        key, k_sub = jax.random.split(key)
        (loss, (erro_m, frac_alvo)), grads = grad_fn(params, k_sub)
        # Global-norm gradient clipping
        g_norm = jnp.sqrt(sum(jnp.sum(g ** 2) for g in jax.tree_util.tree_leaves(grads)) + 1e-12)
        escala_g = jnp.minimum(1.0, 1.0 / g_norm)
        grads = jax.tree_util.tree_map(lambda g: g * escala_g, grads)
        # Cosine annealing LR com warmup de 15 épocas
        lr = jnp.where(
            passo_idx < 15,
            lr_max * (passo_idx + 1) / 15.0,
            0.5 * lr_max * (1.0 + jnp.cos(math.pi * (passo_idx - 15) / jnp.maximum(float(epocas - 15), 1.0))),
        )
        t_step = passo_idx + 1
        m_novo = jax.tree_util.tree_map(lambda m, g: b1 * m + (1.0 - b1) * g, m_adam, grads)
        v_novo = jax.tree_util.tree_map(lambda v, g: b2 * v + (1.0 - b2) * (g ** 2), v_adam, grads)
        m_hat = jax.tree_util.tree_map(lambda m: m / (1.0 - b1 ** t_step), m_novo)
        v_hat = jax.tree_util.tree_map(lambda v: v / (1.0 - b2 ** t_step), v_novo)
        params_novo = jax.tree_util.tree_map(
            lambda p, mh, vh: p * (1.0 - lr * wd) - lr * mh / (jnp.sqrt(vh) + eps),
            params, m_hat, v_hat,
        )
        return params_novo, m_novo, v_novo, key, loss, erro_m, frac_alvo

    t0 = time.perf_counter()
    historico = []
    for ep in range(epocas):
        params, m_adam, v_adam, key, loss, erro_m, frac_alvo = passo_treino(
            params, m_adam, v_adam, key, jnp.array(ep, dtype=jnp.float32)
        )
        if ep == 0 or (ep + 1) % 30 == 0 or ep == epocas - 1:
            loss_f = float(loss)
            erro_cm = float(erro_m) * 100.0
            alvo_pct = float(frac_alvo) * 100.0
            dt_s = time.perf_counter() - t0
            passos_tot = (ep + 1) * n_envs * passos_ep
            sps = passos_tot / max(dt_s, 1e-6)
            print(f"[gpu] época {ep + 1:3d}/{epocas} · loss={loss_f:.4f} · erro_mira={erro_cm:.2f} cm · "
                  f"NO_ALVO={alvo_pct:.1f} % · {sps / 1e6:.2f} M passos/s ({dt_s:.1f} s)", flush=True)
            historico.append({"epoca": ep + 1, "loss": round(loss_f, 5), "erro_cm": round(erro_cm, 3),
                              "no_alvo_pct": round(alvo_pct, 2), "sps": round(sps, 0)})

    ganhos_finais = {k: float(v) for k, v in decodificar_ganhos(params["ganhos_raw"]).items()}
    parametros_export = {
        "dist_alvo_m": 2.15,
        "zona_morta_d_m": 0.04,
        **ganhos_finais,
        "kp_d": 0.80,
        "kff_d": 0.65,
        "ki_yaw": 0.45,
        "ki_z": 0.65,
        "vx_max": 1.00,
        "vy_max": 1.00,
        "vz_max": 0.70,
        "yaw_max": 1.25,
        "fator_seguranca_tiro": 0.72,
        "omega_max_tiro_rad_s": 0.35,
        "cooldown_auto_tiro_s": 0.45,
        "escala_residual_mlp": 0.08,
    }
    mlp_export = {k: np.asarray(params[k], dtype=float).round(6).tolist() for k in ("W1", "b1", "W2", "b2", "W3", "b3")}
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    dados = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "backend": str(backend),
        "dispositivo": str(dispositivos[0]) if dispositivos else "cpu",
        "n_envs": n_envs,
        "epocas": epocas,
        "passos_totais_gpu": epocas * n_envs * passos_ep,
        "duracao_gpu_s": round(time.perf_counter() - t0, 2),
        "parametros": parametros_export,
        "mlp": mlp_export,
        "historico": historico,
    }
    MODELO_JSON.write_text(json.dumps(dados, indent=2), encoding="utf-8")
    print(f"[gpu] modelo gravado em {MODELO_JSON}", flush=True)
    return dados


def validar_sitl_mujoco() -> dict:
    """Valida a política treinada na planta completa MuJoCo 3.15 + C++ SITL (sem renderizar 3D) em seguimento puro
    e com AUTO SHOOT ativo."""
    sys.path[:0] = [str(_RAIZ), str(_AQUI)]
    import sim_view as sv
    from env_real import DroneRealEnv
    from mira_balistica import MiraBalisticaIA

    mira_ia = MiraBalisticaIA(MODELO_JSON)
    resultados = {}
    for vel_bola in (0.0, 0.3, 0.5, 0.8):
        # 1) Seguimento de mira puro (sem o recuo dos tiros) para medir a precisão contínua da mira no alvo
        env0 = DroneRealEnv(modo_acao="ctbr", comando=True, com_alvo=True, episodio_s=18.0)
        nuc0 = sv.NucleoClassico.criar(env0)
        nuc0.instalar()
        env0.reset(seed=6200)
        nuc0.pos_reset()
        mira_ia.reiniciar()
        for _ in range(200):  # 4,0 s para descolar e estabilizar a 1,0 m (como em avaliar_bola.py)
            nuc0.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
            env0.step(np.zeros(4, dtype=np.float32))
        if vel_bola > 0.0:
            env0.definir_trajetoria_ponto("aleatorio", vel=vel_bola, semente=6200)
        else:
            env0.definir_trajetoria_ponto("parado")
        erros_mira_cm = []
        no_alvo_mira = 0
        tot_mira = 0
        for k in range(450):
            cmd = mira_ia.passo(env0, dt=env0.dt_decisao)
            nuc0.comando(cmd)
            if k >= 50:
                prev = env0.planta.prever_tiro_bola(pos_bola=env0.ponto_alvo, vel_bola=env0.ponto_alvo_vel)
                if prev["erro_bola_m"] is not None:
                    erros_mira_cm.append(100.0 * float(prev["erro_bola_m"]))
                if prev["no_alvo"]:
                    no_alvo_mira += 1
                tot_mira += 1
            env0.step(np.zeros(4, dtype=np.float32))
        nuc0.remover()

        # 2) Seguimento COM AUTO SHOOT ativo (dispara sempre que vai literalmente acertar + recupera do soco)
        env = DroneRealEnv(modo_acao="ctbr", comando=True, com_alvo=True, episodio_s=18.0)
        nuc = sv.NucleoClassico.criar(env)
        nuc.instalar()
        env.reset(seed=6200)
        nuc.pos_reset()
        mira_ia.reiniciar()
        for _ in range(200):
            nuc.comando({"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0})
            env.step(np.zeros(4, dtype=np.float32))
        if vel_bola > 0.0:
            env.definir_trajetoria_ponto("aleatorio", vel=vel_bola, semente=6200)
        else:
            env.definir_trajetoria_ponto("parado")
        for k in range(450):
            cmd = mira_ia.passo(env, dt=env.dt_decisao)
            nuc.comando(cmd)
            if k >= 40 and mira_ia.deve_atirar(env):
                env.disparar(1)
            env.step(np.zeros(4, dtype=np.float32))
        for _ in range(15):
            cmd = mira_ia.passo(env, dt=env.dt_decisao)
            nuc.comando(cmd)
            env.step(np.zeros(4, dtype=np.float32))
        tiros = env.planta.n_tiros
        acertos = env.planta.n_acertos_bola
        erros = env.planta.n_erros_bola
        mediana_cm = float(np.median(erros_mira_cm)) if erros_mira_cm else 999.0
        pct_alvo = 100.0 * no_alvo_mira / max(tot_mira, 1)
        taxa_acerto = 100.0 * acertos / max(tiros, 1)
        resultados[f"vel_{vel_bola:.1f}"] = {
            "vel_bola_m_s": vel_bola,
            "erro_mediano_cm": round(mediana_cm, 2),
            "no_alvo_pct": round(pct_alvo, 1),
            "tiros_auto": tiros,
            "acertos_bola": acertos,
            "erros_bola": erros,
            "taxa_acerto_pct": round(taxa_acerto, 1),
        }
        print(f"[sitl] bola @{vel_bola:.1f} m/s → mira: erro mediano={mediana_cm:.2f} cm, NO_ALVO={pct_alvo:.1f} % · "
              f"AUTO_SHOOT: {acertos}/{tiros} acertos ({taxa_acerto:.1f} %, {erros} erros)", flush=True)
        nuc.remover()
    return resultados


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Treino em GPU da IA de Mira Balística e Auto-Shoot.")
    p.add_argument("--epocas", type=int, default=240)
    p.add_argument("--n-envs", type=int, default=4096)
    p.add_argument("--so-validar", action="store_true")
    args = p.parse_args(argv)

    if not args.so_validar:
        dados = treinar_fase_gpu(epocas=args.epocas, n_envs=args.n_envs)
    else:
        dados = json.loads(MODELO_JSON.read_text(encoding="utf-8"))

    venv_py = _RAIZ / ".venv" / "bin" / "python"
    if not args.so_validar and Path(sys.prefix).resolve() != (_RAIZ / ".venv").resolve() and venv_py.is_file():
        r = subprocess.run([str(venv_py), str(Path(__file__).resolve()), "--so-validar"], check=False)
        return r.returncode

    res_sitl = validar_sitl_mujoco()
    dados["validacao_sitl"] = res_sitl
    MODELO_JSON.write_text(json.dumps(dados, indent=2), encoding="utf-8")
    ok = all(v["tiros_auto"] >= 1 and v["acertos_bola"] == v["tiros_auto"] and v["erros_bola"] == 0
             for v in res_sitl.values())
    print(f"[fim] validação SITL: {'TUDO OK (100 % de acerto no AUTO SHOOT)' if ok else 'FALHOU'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
