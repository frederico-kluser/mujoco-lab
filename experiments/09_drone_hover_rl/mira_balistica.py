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
    "cooldown_auto_tiro_s": 0.45,
    "escala_residual_mlp": 0.08,
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
            except (OSError, ValueError, TypeError):
                pass
        self.reiniciar()

    def reiniciar(self) -> None:
        self.i_yaw = 0.0
        self.i_z = 0.0
        self.v_bola_est = np.zeros(3)
        self.a_bola_est = np.zeros(3)
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

        # Posição futura da bola no instante de chegada do projétil (t + τ_voo)
        k_lead = p["k_lead"]
        pos_bola_alvo = pos_bola + k_lead * (v_bola * tau_voo + 0.5 * self.a_bola_est * (tau_voo ** 2))

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

        # 1. Canal de GUINADA (alinha +x̂_corpo com a bola)
        if abs(e_psi) < 0.25:
            self.i_yaw = float(np.clip(self.i_yaw + p["ki_yaw"] * e_psi * dt, -0.15, 0.15))
        else:
            self.i_yaw *= 0.9
        yaw_taxa = p["kp_yaw"] * e_psi + self.i_yaw + p["kff_yaw"] * w_los

        # 2. Canal LATERAL v_y (anula o erro lateral da linha de tiro imediatamente sem inclinar o pitch!)
        erro_lat_m = dist_xy * math.sin(e_psi)
        fator_frente = max(0.0, math.cos(e_psi))
        vy_cmd = (p["kp_y"] * erro_lat_m + p["kff_y"] * v_bola_esq) * fator_frente

        # 3. Canal VERTICAL v_z (alinha a altura do impacto balístico de `boca_cano` com o centro da bola)
        # Queda gravitacional na distância D e inclinação vertical filtrada do cano (evita que o pitch de alta
        # frequência sacuda a altura; o erro estacionário é anulado por completo pelo integral i_z).
        queda_grav = 0.5 * 9.81 * (tau_voo ** 2)
        ex_z_f = getattr(self, "_ex_z_f", float(ex[2]))
        ex_z_f = ex_z_f + (dt / (0.25 + dt)) * (float(ex[2]) - ex_z_f)
        self._ex_z_f = ex_z_f
        z_impacto_est = float(p_boca[2]) + ex_z_f * p["k_pitch_z"] * dist_3d - queda_grav
        erro_z_m = float(pos_bola_alvo[2]) - z_impacto_est
        if abs(erro_z_m) < 0.25:
            self.i_z = float(np.clip(self.i_z + p["ki_z"] * erro_z_m * dt, -0.25, 0.25))
        else:
            self.i_z *= 0.95
        vz_cmd = p["kp_z"] * erro_z_m + self.i_z + p["kff_z"] * v_bola_z

        # 4. Canal LONGITUDINAL v_x (mantém dist_alvo_m = 2,15 m, onde a paralaxe vertical cano-câmara é 3,7° < 5°)
        erro_d_bruto = dist_xy - p["dist_alvo_m"]
        zm_d = float(p.get("zona_morta_d_m", 0.04))
        if abs(erro_d_bruto) <= zm_d:
            erro_d = 0.0
        else:
            erro_d = erro_d_bruto - math.copysign(zm_d, erro_d_bruto)
        vx_cmd = (p["kp_d"] * erro_d + p["kff_d"] * v_bola_frente) * fator_frente

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
