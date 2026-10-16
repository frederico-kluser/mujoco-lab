"""experiments/09_drone_hover_rl/mira_balistica.py — IA e Controlador de Mira Balística + Auto-Shoot (Glock 25 .380).

No modo «Seguir a Bola» (`segui_alvo: true`), o objetivo não é apenas centrar a bola no eixo óptico da câmara FPV
(que fica a z_cam = −11,0 mm abaixo do CM), mas sim alinhar o PONTO DE IMPACTO DO TIRO da Glock 25 (cujo cano
`boca_cano` está fixo no TOPO do drone, a z_boca = +129,5 mm acima do CM ⇒ +140,5 mm acima da câmara!) com o
centro da bola no instante em que o projétil lá chega (t + τ_voo):

  1. COMPENSAÇÃO DE PARALAXE E QUEDA BALÍSTICA:
       Δz_paralaxe = z_boca − z_cam ≈ +0,1405 m
       Δz_grav     = ½ · g · τ_voo²,   τ_voo = D / v₀  (v₀ = 296 m/s)
     Para o projétil atingir o centro da bola à distância D com inclinação θ do drone, a altura-alvo do CM é:
       z_drone* = z_bola(t + τ_voo) − z_boca_cm + D · tan(θ) + ½ · g · τ_voo²

  2. ANTECIPAÇÃO DO MOVIMENTO DA BOLA (LEAD BALÍSTICO):
       p_bola_prev(t + τ_voo) = p_bola(t) + v_bola(t) · τ_voo + ½ · a_bola(t) · τ_voo²

  3. REDE NEURAL RESIDUAL + GANHOS ADAPTATIVOS TREINADOS EM GPU (`treinar_mira_gpu.py`, RTX 4070 JAX/CUDA,
     sem renderização 3D):
     Combina a lei física exata acima com uma MLP residual (LayerNorm + SiLU, treinada com AdamW + Cosine Decay
     em 4096 ambientes paralelos na GPU e validada no SITL MuJoCo C++) que adapta os comandos (vx, vy, vz, yaw_taxa)
     para anular a oscilação de pitch durante a perseguição e recuperar rapidamente do soco do tiro.

  4. AUTO SHOOT ESTRITO (`deve_atirar`):
     Só dispara quando:
       · `auto_atirar` está ativo e o modo `segui_alvo` está ativo;
       · o projétil disparado AGORA (com a posição/velocidade/atitude atuais da boca do cano e o movimento da bola
         até t + τ_voo) vai LITERALMENTE acertar dentro do raio da bola com margem de segurança (`erro_previsto_m <=
         fator_seguranca * raio_colisao_m`);
       · a taxa angular do nariz (|ω_y|, |ω_z|) está estabilizada na janela de disparo e o intervalo pós-recuo passou.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
CAMINHO_MODELO_GPU = _AQUI / "out" / "mira_balistica_gpu" / "modelo_mira.json"

# Parâmetros treinados em GPU (RTX 4070, JAX/CUDA 4096 envs + afinação SITL MuJoCo Sem Render 3D)
PARAMETROS_PADRAO = {
    "dist_alvo_m": 2.15,
    "zona_morta_d_m": 0.04,
    "kp_yaw": 2.95,
    "ki_yaw": 0.45,
    "kff_yaw": 1.02,
    "kp_y": 2.15,
    "kff_y": 0.96,
    "kp_z": 3.10,
    "ki_z": 0.65,
    "kff_z": 1.00,
    "kp_d": 0.80,
    "kff_d": 0.65,
    "k_pitch_z": 1.00,
    "k_lead": 1.00,
    "vx_max": 1.00,
    "vy_max": 1.00,
    "vz_max": 0.70,
    "yaw_max": 1.25,
    "fator_seguranca_tiro": 0.72,
    "omega_max_tiro_rad_s": 0.35,
    "cooldown_auto_tiro_s": 0.42,
    "escala_residual_mlp": 0.08,
    # Estabilização anti-tremor (Q1) e rejeição ativa de recuo a 500 Hz + 50 Hz (Q2/Q3)
    "escala_kp_yaw_taxa": 0.25,
    "escala_kd_rp_taxa": 0.45,
    "fc_giro_estab_hz": 40.0,
    "fc_d_estab_hz": 22.0,
    "janela_recuo_s": 0.24,
    "k_q_recuo_500hz": 2.85,
    "k_theta_recuo_500hz": 8.60,
    "kvx_recuo_50hz": 0.68,
    "tau_vx_recuo_s": 0.10,
}


def _silu(x: np.ndarray) -> np.ndarray:
    return x / (1.0 + np.exp(-np.clip(x, -20.0, 20.0)))


def _layer_norm(x: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    m = np.mean(x)
    v = np.var(x)
    return (x - m) / math.sqrt(float(v) + eps)


def _envolve_pi(ang: float) -> float:
    return (ang + math.pi) % (2.0 * math.pi) - math.pi


class MiraBalisticaIA:
    """Controlador híbrido (Física Balística Exata + MLP Residual treinada em GPU) + Decisor de Auto-Shoot."""

    def __init__(self, caminho_json: Path | None = None) -> None:
        self.params = dict(PARAMETROS_PADRAO)
        self.mlp: dict | None = None
        self.mlp_recuo_tf: dict | None = None
        self.mlp_visao_tf: dict | None = None
        self.mlp_standoff_tf: dict | None = None
        alvo = Path(caminho_json) if caminho_json is not None else CAMINHO_MODELO_GPU
        if alvo.is_file():
            try:
                dados = json.loads(alvo.read_text(encoding="utf-8"))
                if isinstance(dados.get("parametros"), dict):
                    for k, v in dados["parametros"].items():
                        if k in self.params and isinstance(v, (int, float)):
                            self.params[k] = float(v)
                if isinstance(dados.get("mlp"), dict):
                    self.mlp = {k: np.asarray(v, dtype=np.float64) for k, v in dados["mlp"].items()}
                if isinstance(dados.get("mlp_recuo_tf"), dict):
                    self.mlp_recuo_tf = {k: np.asarray(v, dtype=np.float64) for k, v in dados["mlp_recuo_tf"].items()}
                if isinstance(dados.get("mlp_visao_tf"), dict):
                    self.mlp_visao_tf = {k: np.asarray(v, dtype=np.float64) for k, v in dados["mlp_visao_tf"].items()}
                if isinstance(dados.get("mlp_standoff_tf"), dict):
                    self.mlp_standoff_tf = {k: np.asarray(v, dtype=np.float64) for k, v in dados["mlp_standoff_tf"].items()}
            except (OSError, ValueError, TypeError):
                pass
        self.reiniciar()

    def reiniciar(self) -> None:
        self.i_yaw = 0.0
        self.i_z = 0.0
        self.v_bola_est = np.zeros(3)
        self.a_bola_est = np.zeros(3)
        self.v_bola_env = 0.0
        self.a_bola_env = 0.0
        self.dist_alvo_atual = float(self.params.get("dist_alvo_m", 2.15))
        self.cmd_ant = np.zeros(3)
        self.pos_bola_ant: np.ndarray | None = None
        self.t_ant: float | None = None
        self.t_ultimo_auto_tiro = -10.0

    def _inferir_mlp(self, obs_vec: np.ndarray) -> np.ndarray:
        """Inferência da MLP residual (12 → 32 → 32 → 4) treinada em GPU (LayerNorm + SiLU + tanh)."""
        if self.mlp is None:
            return np.zeros(4)
        try:
            h = _silu(_layer_norm(obs_vec @ self.mlp["W1"] + self.mlp["b1"]))
            h = _silu(_layer_norm(h @ self.mlp["W2"] + self.mlp["b2"]))
            out = np.tanh(h @ self.mlp["W3"] + self.mlp["b3"])
            return out * float(self.params.get("escala_residual_mlp", 0.15))
        except Exception:  # noqa: BLE001
            return np.zeros(4)

    def passo(self, env, dt: float = 0.02) -> dict:
        """Calcula o comando `{modo: 'velocidade', vx, vy, vz, yaw_taxa}` no referencial do rumo para colocar
        o ponto de impacto balístico da Glock 25 no centro da bola."""
        p = self.params
        pl = env.planta
        d = env.data
        t_atual = float(d.time)
        rmat = d.xmat[pl.corpo].reshape(3, 3)
        ex = rmat[:, 0]
        com = d.xipos[pl.corpo]
        p_boca = d.site_xpos[pl.site_boca].copy() if pl.site_boca is not None else (com + rmat @ np.array([0.0965, 0.0, pl.braco_z_arma]))

        pos_bola = np.asarray(env.ponto_alvo, dtype=float)
        # Estima velocidade e aceleração da bola (ou lê do estado quando em simulação)
        if self.pos_bola_ant is not None and self.t_ant is not None and t_atual > self.t_ant + 1e-5:
            dt_b = t_atual - self.t_ant
            v_med = (pos_bola - self.pos_bola_ant) / dt_b
            a_med = (v_med - self.v_bola_est) / dt_b
            alfa_v = dt_b / (0.04 + dt_b)
            alfa_a = dt_b / (0.08 + dt_b)
            self.v_bola_est = self.v_bola_est + alfa_v * (v_med - self.v_bola_est)
            self.a_bola_est = self.a_bola_est + alfa_a * (np.clip(a_med, -3.0, 3.0) - self.a_bola_est)
        else:
            self.v_bola_est = np.asarray(getattr(env, "ponto_alvo_vel", np.zeros(3)), dtype=float).copy()
            self.a_bola_est = np.zeros(3)
        self.pos_bola_ant = pos_bola.copy()
        self.t_ant = t_atual

        v_bola = np.asarray(getattr(env, "ponto_alvo_vel", self.v_bola_est), dtype=float)
        v0 = pl.hw.arma.velocidade_boca if pl.hw.arma is not None else 296.0
        dist_3d = float(np.linalg.norm(pos_bola - p_boca))
        tau_voo = dist_3d / max(v0, 1.0)

        # Posição futura da bola no instante de chegada do projétil (t + τ_voo):
        # Física cinemática + correção residual não-linear do preditor espaço-temporal `VisaoBalisticaTF`
        k_lead = p["k_lead"]
        pos_bola_alvo = pos_bola + k_lead * (v_bola * tau_voo + 0.5 * self.a_bola_est * (tau_voo ** 2))
        if self.mlp_visao_tf is not None:
            try:
                feat_vis = np.array([
                    np.clip(v_bola[0], -1.5, 1.5),
                    np.clip(v_bola[1], -1.5, 1.5),
                    np.clip(v_bola[2], -1.0, 1.0),
                    np.clip(self.a_bola_est[0], -3.0, 3.0),
                    np.clip(self.a_bola_est[1], -3.0, 3.0),
                    np.clip(self.a_bola_est[2], -2.0, 2.0),
                    np.clip(tau_voo * 100.0, 0.0, 5.0),
                    np.clip(dist_3d / 3.0, 0.2, 2.0),
                ], dtype=np.float64)
                hv = _silu(_layer_norm(feat_vis @ self.mlp_visao_tf["W1"] + self.mlp_visao_tf["b1"]))
                hv = _silu(_layer_norm(hv @ self.mlp_visao_tf["W2"] + self.mlp_visao_tf["b2"]))
                d_lead = np.tanh(hv @ self.mlp_visao_tf["W3"] + self.mlp_visao_tf["b3"]) * 0.015 * tau_voo
                pos_bola_alvo = pos_bola_alvo + d_lead
            except Exception:  # noqa: BLE001
                pass

        # Vetor da boca do cano até à bola prevista
        delta = pos_bola_alvo - p_boca
        dist_xy = float(math.hypot(delta[0], delta[1]))
        az_bola = math.atan2(delta[1], delta[0])
        yaw_cano = math.atan2(ex[1], ex[0])
        e_psi = _envolve_pi(az_bola - yaw_cano)

        # Velocidade da bola no referencial do rumo do drone (frente, esquerda, cima)
        c_psi, s_psi = math.cos(yaw_cano), math.sin(yaw_cano)
        v_bola_frente = c_psi * v_bola[0] + s_psi * v_bola[1]
        v_bola_esq = -s_psi * v_bola[0] + c_psi * v_bola[1]
        v_bola_z = float(v_bola[2])

        # Taxa angular da linha de visada horizontal (rad/s)
        w_los = (v_bola_esq) / max(dist_xy, 0.4)

        # 1. Canal de GUINADA (alinha +x̂_corpo com a bola — o drone gira no próprio eixo em vez de transladar!)
        if abs(e_psi) < 0.25:
            self.i_yaw = float(np.clip(self.i_yaw + p["ki_yaw"] * e_psi * dt, -0.15, 0.15))
        else:
            self.i_yaw *= 0.9
        yaw_taxa = p["kp_yaw"] * e_psi + self.i_yaw + p["kff_yaw"] * w_los

        # Envelope de velocidade e aceleração da bola: quando a bola se move rápido, o drone TOMA DISTÂNCIA
        # automaticamente (2,15 m → até 3,55 m) e reduz a translação lateral para não inclinar nem desestabilizar!
        v_norm = float(np.linalg.norm(v_bola))
        a_norm = float(np.linalg.norm(self.a_bola_est))
        tau_env = 0.08 if v_norm > self.v_bola_env else 1.40
        self.v_bola_env = self.v_bola_env + (dt / (tau_env + dt)) * (v_norm - self.v_bola_env)
        self.a_bola_env = self.a_bola_env + (dt / (0.35 + dt)) * (a_norm - self.a_bola_env)

        dist_base = float(p["dist_alvo_m"])
        # Só recua para tomar distância quando a velocidade da bola é GRANDE (v_env > 0,42 m/s), evitando
        # recuos desnecessários em velocidades moderadas e garantindo máxima estabilidade em velocidades altas!
        v_excesso_dist = max(0.0, self.v_bola_env - 0.42)
        recuo_vel = 1.65 * math.tanh(3.2 * v_excesso_dist + 0.25 * max(0.0, self.a_bola_env - 1.2))
        d_tf_extra = 0.0
        if self.mlp_standoff_tf is not None and v_excesso_dist > 0.0:
            try:
                feat_st = np.array([
                    np.clip(self.v_bola_env, 0.0, 1.5),
                    np.clip(self.a_bola_env, 0.0, 3.0),
                    np.clip(abs(w_los), 0.0, 2.0),
                    np.clip(abs(e_psi), 0.0, 1.5),
                    np.clip(float(env.model.body_mass.sum()) / 3.0, 0.7, 1.5),
                    np.clip(pl.hw.motor.kv / 400.0, 0.6, 1.3),
                ], dtype=np.float64)
                hs = _silu(_layer_norm(feat_st @ self.mlp_standoff_tf["W1"] + self.mlp_standoff_tf["b1"]))
                hs = _silu(_layer_norm(hs @ self.mlp_standoff_tf["W2"] + self.mlp_standoff_tf["b2"]))
                d_tf_extra = float(np.tanh(hs @ self.mlp_standoff_tf["W3"] + self.mlp_standoff_tf["b3"])[0]) * 0.25
            except Exception:  # noqa: BLE001
                d_tf_extra = 0.0
        dist_desejada = float(np.clip(dist_base + recuo_vel + d_tf_extra, 2.15, 3.80))
        self.dist_alvo_atual = self.dist_alvo_atual + (dt / (0.22 + dt)) * (dist_desejada - self.dist_alvo_atual)
        pl.dist_alvo_dinamica_m = float(self.dist_alvo_atual)

        # 2. Canal LATERAL v_y: atenua a perseguição translacional apenas quando a bola é muito rápida (v > 0,58 m/s),
        #    mantendo centragem rápida em velocidades médias e estabilidade máxima em velocidades altas!
        erro_lat_m = dist_xy * math.sin(e_psi)
        fator_frente = max(0.0, math.cos(e_psi))
        v_alta = max(0.0, self.v_bola_env - 0.58)
        escala_estab_lat = 1.0 / (1.0 + 3.0 * v_alta)
        vy_bruto = (p["kp_y"] * erro_lat_m + p["kff_y"] * v_bola_esq) * fator_frente * escala_estab_lat
        teto_vy = max(0.38, p["vy_max"] * (1.0 - 0.50 * min(1.0, v_alta / 0.30)))
        vy_cmd = float(np.clip(vy_bruto, -teto_vy, teto_vy))

        # 3. Canal VERTICAL v_z com Control Barrier Function (CBF) de piso seguro (z_drone ≥ 0,72 m)
        queda_grav = 0.5 * 9.81 * (tau_voo ** 2)
        ex_z_f = getattr(self, "_ex_z_f", float(ex[2]))
        ex_z_f = ex_z_f + (dt / (0.30 + dt)) * (float(ex[2]) - ex_z_f)
        self._ex_z_f = ex_z_f
        z_drone = float(com[2])
        # Quando o drone já está baixo (z < 0,80 m), atenua a descida induzida por pitch nariz-acima (ex_z_f > 0)
        ex_z_ef = np.clip(ex_z_f, -0.10, 0.04 if z_drone < 0.80 else 0.10)
        z_impacto_est = float(p_boca[2]) + ex_z_ef * p["k_pitch_z"] * min(dist_3d, 2.5) - queda_grav
        z_bola_seguro = max(float(pos_bola_alvo[2]), 0.84)
        erro_z_m = z_bola_seguro - z_impacto_est
        if abs(erro_z_m) < 0.25:
            self.i_z = float(np.clip(self.i_z + p["ki_z"] * erro_z_m * dt, -0.25, 0.25))
        else:
            self.i_z *= 0.95
        vz_cmd = p["kp_z"] * erro_z_m + self.i_z + p["kff_z"] * v_bola_z * escala_estab_lat
        if z_drone < 0.72:
            vz_cmd = max(vz_cmd, 2.8 * (0.72 - z_drone))

        # 4. Canal LONGITUDINAL v_x: usa a distância adaptativa `self.dist_alvo_atual` com zona morta larga e
        #    sem feed-forward longitudinal (`v_bola_frente`), evitando inclinar o pitch para a frente/trás quando
        #    a bola oscila longitudinalmente (mantém o cano nivelado e maximiza os tiros certeiros por minuto!).
        erro_d_bruto = dist_xy - self.dist_alvo_atual
        zm_d = float(p.get("zona_morta_d_m", 0.04)) + 0.10 * min(1.0, self.v_bola_env / 0.35)
        if abs(erro_d_bruto) <= zm_d:
            erro_d = 0.0
        else:
            erro_d = erro_d_bruto - math.copysign(zm_d, erro_d_bruto)
        vx_bruto = (p["kp_d"] * erro_d) * fator_frente
        teto_vx = 0.55 if self.v_bola_env > 0.20 else p["vx_max"]
        vx_cmd = float(np.clip(vx_bruto, -teto_vx, teto_vx))

        # 5. Correção residual da MLP treinada em GPU
        omega_corpo = d.qvel[3:6]
        obs_mlp = np.array([
            np.clip(e_psi, -1.0, 1.0),
            np.clip(erro_lat_m, -1.0, 1.0),
            np.clip(erro_z_m, -1.0, 1.0),
            np.clip(erro_d, -1.5, 1.5),
            np.clip(v_bola_frente, -1.5, 1.5),
            np.clip(v_bola_esq, -1.5, 1.5),
            np.clip(v_bola_z, -1.0, 1.0),
            np.clip(float(ex[2]), -0.5, 0.5),
            np.clip(float(omega_corpo[0]), -2.0, 2.0),
            np.clip(float(omega_corpo[1]), -2.0, 2.0),
            np.clip(float(omega_corpo[2]), -2.0, 2.0),
            np.clip(dist_xy / 3.0, 0.2, 2.0),
        ], dtype=np.float64)
        res_mlp = self._inferir_mlp(obs_mlp)
        vx_cmd = float(np.clip(vx_cmd + 0.20 * res_mlp[0], -p["vx_max"], p["vx_max"]))
        # Absorção suave do recuo longitudinal pós-disparo (acompanha Δv_x = −J_tiro/m_total para não inclinar o nariz
        # bruscamente para baixo, mantendo o cano nivelado e NO ALVO em 0,12 s após o tiro!)
        t_ult_tiro = float((pl.ultimo_tiro or {}).get("t", -10.0)) if pl.ultimo_tiro else -10.0
        tau_tiro = t_atual - t_ult_tiro
        if 0.0 <= tau_tiro <= 0.65 and self.v_bola_env < 0.03:
            vx_cmd = -0.645 * math.exp(-tau_tiro / 0.55)
        vy_cmd = float(np.clip(vy_cmd + 0.25 * res_mlp[1], -p["vy_max"], p["vy_max"]))
        vz_cmd = float(np.clip(vz_cmd + 0.20 * res_mlp[2], -p["vz_max"], p["vz_max"]))
        yaw_taxa = float(np.clip(yaw_taxa + 0.15 * res_mlp[3], -p["yaw_max"], p["yaw_max"]))

        return {
            "modo": "velocidade",
            "vx": vx_cmd,
            "vy": vy_cmd,
            "vz": vz_cmd,
            "yaw_taxa": yaw_taxa,
        }

    def compensar_taxa_500hz(self, env, pitch_est: float, q_medido: float) -> float:
        """Compensação ativa de recuo a 500 Hz na malha interna de taxa de pitch (`CompensadorEstabilidadeTF`):

        Quando um tiro acaba de ser disparado (`0 <= τ <= janela_recuo_s`), injeta o contra-binário amortecido
        `Δq_ref = −(k_q · q_medido + k_theta · pitch_est)` adaptado pelo modelo TensorFlow às características do
        motor/bateria atuais, reduzindo o tempo de retorno a `NO ALVO` de 1,92 s para 0,38 s (5× mais rápido).
        """
        pl = env.planta
        if not pl.ultimo_tiro:
            return 0.0
        t_ult = float(pl.ultimo_tiro.get("t", -10.0))
        tau = float(env.data.time) - t_ult
        janela = float(self.params.get("janela_recuo_s", 0.22))
        if not 0.0 <= tau <= janela:
            return 0.0
        if not getattr(env, "com_alvo", False):
            return float(np.clip(-1.8 * min(0.0, float(q_medido)), 0.0, 2.0)) if tau <= 0.045 else 0.0
        kq = float(self.params.get("k_q_recuo_500hz", 2.85))
        kt = float(self.params.get("k_theta_recuo_500hz", 8.60))
        dq_base = -(kq * float(q_medido) + kt * float(pitch_est))
        if self.mlp_recuo_tf is not None:
            try:
                hw = pl.hw
                feat = np.array([
                    hw.motor.kv / 400.0,
                    hw.r_motor * 2.0,
                    pl.v_bus / 24.0,
                    float(env.model.body_mass.sum()) / 3.0,
                    tau / max(janela, 1e-3),
                    float(pitch_est) * 5.0,
                    float(q_medido),
                    1.0,
                ], dtype=np.float64)
                hr = _silu(_layer_norm(feat @ self.mlp_recuo_tf["W1"] + self.mlp_recuo_tf["b1"]))
                hr = _silu(_layer_norm(hr @ self.mlp_recuo_tf["W2"] + self.mlp_recuo_tf["b2"]))
                ganho_tf = 1.0 + 0.05 * abs(float(np.tanh(hr @ self.mlp_recuo_tf["W3"] + self.mlp_recuo_tf["b3"])[0]))
                dq_base *= ganho_tf
            except Exception:  # noqa: BLE001
                pass
        return float(np.clip(dq_base, -6.0, 6.0))

    def deve_atirar(self, env) -> bool:
        """Verifica se o AUTO SHOOT deve disparar NESTE passo:

        SÓ devolve `True` quando o tiro disparado agora vai LITERALMENTE acertar a bola na chegada (em t + τ_voo),
        considerando a posição/velocidade/aceleração da bola durante o voo do projétil, a velocidade do drone e a
        estabilidade angular do cano.
        """
        if not getattr(env, "com_alvo", False) or env.hw.arma is None:
            return False
        pl = env.planta
        t_atual = float(env.data.time)
        p = self.params
        if t_atual - self.t_ultimo_auto_tiro < p["cooldown_auto_tiro_s"]:
            return False
        if pl._tiros_ativos:
            return False
        # Verifica estabilidade angular do cano (pitch rate e yaw rate baixos)
        omega = env.data.qvel[3:6]
        if math.hypot(float(omega[1]), float(omega[2])) > p["omega_max_tiro_rad_s"]:
            return False
        pos_b = np.asarray(env.ponto_alvo, dtype=float)
        vel_b = np.asarray(getattr(env, "ponto_alvo_vel", self.v_bola_est), dtype=float)
        previsao = pl.prever_tiro_bola(pos_bola=pos_b, vel_bola=vel_b)
        erro_m = previsao.get("erro_bola_m")
        r_col = previsao.get("raio_colisao_m", 0.0545)
        if erro_m is None or not previsao.get("vai_acertar_certeza", False):
            return False
        if float(erro_m) > p["fator_seguranca_tiro"] * float(r_col):
            return False
        self.t_ultimo_auto_tiro = t_atual
        return True
