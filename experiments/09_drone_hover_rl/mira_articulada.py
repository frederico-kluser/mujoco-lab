"""experiments/09_drone_hover_rl/mira_articulada.py — MIRA POR ARFAGEM com os braços articulados + TIRO COM RISCO.

O drone NÃO se mexe para mirar: segura x, y, z (comando de velocidade nulo ao núcleo) e aponta a arma só com a GUINADA
(azimute) e o PITCH DO CORPO (elevação — os servos dos braços inclinam os motores para o corpo arfar por cima deles,
interface 4 do núcleo). Assim pode atirar de qualquer altura face ao alvo («o círculo»): à mesma altura, por baixo ou
por cima.

O QUE O DRONE SABE (nada de verdade privilegiada na decisão):
  · o ALVO vem de um rastreador de câmara (`RastreadorAlvo`): a posição com a LATÊNCIA e o ruído do módulo de câmara do
    build (Pi Camera 116 ms; Vision Shield 21 ms), filtrada por um Kalman de aceleração constante e extrapolada até agora;
  · a ARMA aponta para onde a atitude ESTIMADA pelo núcleo diz (viés e ruído do estimador incluídos) — o erro de
    pontaria que a câmara vê (alvo vs retícula, fixos ao corpo) fecha o integrador de elevação;
  · a bala só sai `latencia_disparo` depois da ordem (solenoide + percussor, 16 ms na Glock 25 do catálogo).

LEI DE MIRA (fórmulas fechadas):
  1. ponto de impacto: p* = p̂ + v̂·T + ½·â·T², T = L_disparo + τ_voo, τ_voo = |p* − p_boca|/v₀ (2 iterações);
  2. direção do cano: d ∝ (p* − p_boca)/τ_voo − v_boca + ½·g·τ_voo·ẑ  (a velocidade da boca soma-se à bala; a queda
     compensa-se para cima);
  3. azimute ψ* = atan2(d_y, d_x) → guinada: r = k_p·e_ψ + k_i·∫e_ψ + k_ff·ω_LOS;
  4. elevação ε* = atan2(d_z, |d_xy|) → pitch do corpo θ* = −(ε* + c + Δε_TF + ε̇*/k_att), com c a integrar o erro
     de elevação que a câmara mede (tira o viés de atitude) e Δε_TF a correção residual aprendida (TensorFlow).

DECISÃO DE TIRO (o dono: «a penalização para o erro é muito alta: só atira quando acha que vai acertar»): com um erro a
custar K acertos (`penalidade`), atirar vale a pena só se P(acerto) − K·(1 − P(acerto)) > 0 ⇔ P(acerto) > K/(1+K)
(≈ 0,952 com K = 20). P(acerto) vem da `RedeConfiancaTiroTF` (treinada em TensorFlow com tiros VIRTUAIS rotulados pela
balística exata do simulador) e só é consultada se o portão físico já passou: erro previsto ≤ f·raio de colisão, taxas
angulares baixas, sem tiro no ar nem recuo ativo, e o drone ESTÁVEL (sem subir/descer/deslizar nem rolar — medido: a
mirar para baixo cada recuo atira o drone para cima e, a disparar sem este portão, o empuxo chegou a varrer ±30°).
"""
from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
CAMINHO_MODELO = _AQUI / "out" / "mira_articulada" / "modelo_mira_articulada.json"

V0_PADRAO = 296.0
K_AR_PROJETIL = 0.00180          # 1/m — o MESMO coeficiente balístico da planta (`Planta._passo_visuais_tiro`)
LATENCIA_CAMERA_PI_S, LATENCIA_CAMERA_DCMI_S = 0.116, 0.021
FPS_CAMERA = 50.0                # Hz — 2304×1296p56 da Pi Camera 3 a 50 Hz (o detetor corre a cada frame)
SIGMA_ANGULO_CAMERA = math.radians(0.05)   # rad — centróide sub-píxel a 1080p (≈ 0,3 px)
SIGMA_DIST_CAMERA = 0.02         # fração da distância (raio aparente do círculo → distância)
N_CARACTERISTICAS = 30

PARAMETROS_PADRAO = {
    "kp_yaw": 2.4,
    "ki_yaw": 0.8,
    "kff_yaw": 1.0,
    "yaw_max": 0.9,
    "ki_el": 2.0,
    "kff_el": 1.0,
    "lim_c_el": math.radians(3.0),
    "fator_seguranca": 0.60,
    "omega_max_tiro": 0.25,
    "cooldown_s": 0.25,
    "penalidade": 20.0,
    "q_jerk": 30.0,
    "vz_max_tiro": 0.25,       # m/s — portão de ESTABILIDADE: não dispara com o drone a subir/descer (pós-recuo)
    "vxy_max_tiro": 0.35,      # m/s — nem a deslizar
    "roll_max_tiro": math.radians(4.0),
}

NOMES_CARACTERISTICAS = (
    [f"q_ombro{i}" for i in range(1, 5)] + [f"q_cotovelo{i}" for i in range(1, 5)]
    + ["tau_d", "roll_est", "pitch_est", "giro_x", "giro_y", "giro_z", "e_el", "e_az", "erro_prev_r", "tau_voo",
       "dist", "elev_req", "vb_frente", "vb_esq", "vb_z", "ab_norma", "desde_tiro", "dh", "e_pitch_fc", "incerteza",
       "vz_drone", "vxy_drone"])
assert len(NOMES_CARACTERISTICAS) == N_CARACTERISTICAS


def _silu(x: np.ndarray) -> np.ndarray:
    return x / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def _ln(x: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    m = np.mean(x, axis=-1, keepdims=True)
    v = np.var(x, axis=-1, keepdims=True)
    return (x - m) / np.sqrt(v + eps)


def mlp_inferir(pesos: dict, x: np.ndarray) -> np.ndarray:
    """MLP de inferência (NumPy) das redes treinadas em TensorFlow: [normalização] → (Dense → LayerNorm → SiLU)×n → Dense."""
    h = (np.asarray(x, dtype=np.float64) - pesos["mu"]) / pesos["sigma"]
    n = int(pesos["n_camadas"])
    for k in range(1, n):
        h = _silu(_ln(h @ pesos[f"W{k}"] + pesos[f"b{k}"]))
    return h @ pesos[f"W{n}"] + pesos[f"b{n}"]


def _k_att(env) -> float:
    """O ganho de atitude da cascata do núcleo (1/s) — para o avanço da taxa de elevação; 3,5 sem núcleo."""
    nucleo = getattr(env.fc, "nucleo", None)
    try:
        return float(nucleo.cfg.cascata.k_att)
    except AttributeError:
        return 3.5


def _envolve(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def atitude_zyx(rmat: np.ndarray) -> tuple[float, float, float]:
    """(roll, pitch, yaw) ZYX de uma matriz corpo→mundo."""
    pitch = -math.asin(max(-1.0, min(1.0, float(rmat[2, 0]))))
    return math.atan2(float(rmat[2, 1]), float(rmat[2, 2])), pitch, math.atan2(float(rmat[1, 0]), float(rmat[0, 0]))


def direcao_cano(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """x̂ do corpo (o cano) no mundo, para a atitude ZYX dada."""
    return np.array([math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), -math.sin(pitch)])


def estado_boca(env) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(p_boca, x̂_cano, v_boca) VERDADEIROS no instante atual — os que `Planta.disparar` usa para lançar a bala."""
    import mujoco
    m, d, pl = env.model, env.data, env.planta
    mujoco.mj_kinematics(m, d)
    mujoco.mj_comPos(m, d)
    rmat = d.xmat[pl.corpo].reshape(3, 3)
    ex = rmat[:, 0].copy()
    com = d.xipos[pl.corpo]
    p_boca = d.site_xpos[pl.site_boca].copy()
    w_mundo = rmat @ d.qvel[3:6]
    v_boca = d.qvel[0:3] + np.cross(w_mundo, p_boca - com)
    return p_boca, ex, v_boca


def simular_bala(p0: np.ndarray, v0: np.ndarray, posicoes_bola, raio_colisao: float, dt: float,
                 gravidade: np.ndarray, vento: np.ndarray, alcance: float = 50.0) -> tuple[bool, float]:
    """A balística EXATA da planta (`Planta._passo_visuais_tiro`): integrador de 2.ª ordem com gravidade + arrasto
    quadrático, colisão com a bola por segmento a cada passo — contra a posição da bola em CADA passo de física
    (`posicoes_bola[i]` = a bola no passo i após o disparo). Devolve (acertou, distância mínima à bola em m)."""
    p, v = np.asarray(p0, dtype=float).copy(), np.asarray(v0, dtype=float).copy()
    origem = p.copy()
    d_min = 1e9
    for pb in posicoes_bola:
        v_rel = v - vento
        acc = gravidade - K_AR_PROJETIL * float(np.linalg.norm(v_rel)) * v_rel
        p_novo = p + v * dt + 0.5 * acc * (dt * dt)
        v = v + acc * dt
        seg = p_novo - p
        s2 = float(seg @ seg)
        s_min = float(np.clip((pb - p) @ seg / max(s2, 1e-12), 0.0, 1.0))
        d_seg = float(np.linalg.norm(p + s_min * seg - pb))
        d_min = min(d_min, d_seg)
        if d_seg <= raio_colisao:
            return True, d_seg
        p = p_novo
        if p[2] <= 0.005 or float(np.linalg.norm(p - origem)) >= alcance:
            break
    return False, d_min


class RastreadorAlvo:
    """Câmara + detetor + Kalman: a posição do alvo medida a `fps` Hz com `latencia_s` de atraso e ruído angular/distância
    (no referencial da câmara, à volta da linha de vista), filtrada por um Kalman de ACELERAÇÃO CONSTANTE (3 eixos, ruído
    de jerk branco q) e extrapolada da hora da imagem até AGORA. Determinístico com a semente."""

    def __init__(self, latencia_s: float, fps: float = FPS_CAMERA, q_jerk: float = 30.0, semente: int = 0):
        self.lat, self.periodo, self.q = float(latencia_s), 1.0 / float(fps), float(q_jerk)
        self.rng = np.random.default_rng(semente)
        self.reiniciar(None)

    def reiniciar(self, p0) -> None:
        self.hist: deque = deque(maxlen=400)              # (t, posição verdadeira) — para a imagem com atraso
        self.x = None                                     # [3 eixos × (p, v, a)]
        self.P = None
        self.t_kf = 0.0
        self.t_prox_cap: float | None = None              # próxima captura ainda por processar
        self.inovacao = 0.0
        if p0 is not None:
            self._iniciar(p0)

    def _iniciar(self, p0) -> None:
        self.x = np.zeros((3, 3))
        self.x[:, 0] = p0
        self.P = np.tile(np.diag([0.01, 0.5, 4.0]), (3, 1, 1))

    def _prever(self, x: np.ndarray, P: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
        f = np.array([[1.0, dt, 0.5 * dt * dt], [0.0, 1.0, dt], [0.0, 0.0, 1.0]])
        q = self.q * np.array([[dt ** 5 / 20, dt ** 4 / 8, dt ** 3 / 6],
                               [dt ** 4 / 8, dt ** 3 / 3, dt ** 2 / 2],
                               [dt ** 3 / 6, dt ** 2 / 2, dt]])
        return x @ f.T, f @ P @ f.T + q

    def passo(self, t: float, p_verdade: np.ndarray, p_camera: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Avança até `t`. A câmara captura a cada 1/fps; cada imagem fica pronta `latencia` depois e mostra o alvo no
        instante da CAPTURA (a posição verdadeira de agora só entra no histórico). Devolve (p̂, v̂, â) extrapolados a `t`."""
        t = float(t)
        self.hist.append((t, np.asarray(p_verdade, dtype=float).copy()))
        if self.x is None:                               # adquirido antes do início do registo
            self._iniciar(p_verdade)
            self.t_kf = t
            self.t_prox_cap = t
        while self.t_prox_cap + self.lat <= t + 1e-9:
            t_cap = self.t_prox_cap
            pv = self._posicao_em(t_cap)
            z = self._medir(pv, np.asarray(p_camera, dtype=float))
            if t_cap > self.t_kf:
                self.x, self.P = self._prever(self.x, self.P, t_cap - self.t_kf)
                self.t_kf = t_cap
            r = self._r_medida(pv, p_camera)
            for e in range(3):                           # atualização eixo a eixo (H = [1, 0, 0])
                s_inov = self.P[e, 0, 0] + r
                k = self.P[e, :, 0] / s_inov
                inov = z[e] - self.x[e, 0]
                self.x[e] += k * inov
                self.P[e] -= np.outer(k, self.P[e, 0, :])
                self.inovacao = 0.9 * self.inovacao + 0.1 * abs(inov)
            self.t_prox_cap = t_cap + self.periodo
        x, _ = self._prever(self.x, self.P, max(t - self.t_kf, 0.0))
        return x[:, 0].copy(), x[:, 1].copy(), x[:, 2].copy()

    def incerteza(self) -> float:
        return float(math.sqrt(sum(self.P[e, 0, 0] for e in range(3)))) if self.P is not None else 1.0

    def _posicao_em(self, t: float):
        if not self.hist:
            return None
        if t <= self.hist[0][0]:
            return self.hist[0][1]
        for (t0, p0), (t1, p1) in zip(list(self.hist)[:-1], list(self.hist)[1:]):
            if t0 <= t <= t1:
                f = (t - t0) / max(t1 - t0, 1e-9)
                return p0 + f * (p1 - p0)
        return self.hist[-1][1]

    def _medir(self, p: np.ndarray, p_cam: np.ndarray) -> np.ndarray:
        rel = p - p_cam
        dist = float(np.linalg.norm(rel))
        u = rel / max(dist, 1e-6)
        a = np.cross(u, [0.0, 0.0, 1.0])
        if float(np.linalg.norm(a)) < 1e-6:
            a = np.array([1.0, 0.0, 0.0])
        a /= np.linalg.norm(a)
        b = np.cross(u, a)
        ruido = (self.rng.normal(0.0, SIGMA_DIST_CAMERA * dist) * u
                 + self.rng.normal(0.0, SIGMA_ANGULO_CAMERA * dist) * a
                 + self.rng.normal(0.0, SIGMA_ANGULO_CAMERA * dist) * b)
        return p + ruido

    @staticmethod
    def _r_medida(p: np.ndarray, p_cam: np.ndarray) -> float:
        dist = float(np.linalg.norm(p - p_cam))
        return ((SIGMA_DIST_CAMERA * dist) ** 2 + 2.0 * (SIGMA_ANGULO_CAMERA * dist) ** 2) / 3.0


class MiraArticuladaIA:
    """Mira por arfagem (braços articulados) + decisão de tiro com risco — ver o docstring do módulo."""

    def __init__(self, caminho_json: Path | None = None, latencia_camera_s: float = LATENCIA_CAMERA_PI_S,
                 semente: int = 0):
        self.params = dict(PARAMETROS_PADRAO)
        self.rede_confianca: dict | None = None
        self.rede_correcao: dict | None = None
        self.limiar_confianca: float | None = None
        self._portao_sem_tf: dict = {}
        alvo = Path(caminho_json) if caminho_json is not None else CAMINHO_MODELO
        if alvo.is_file():
            try:
                dados = json.loads(alvo.read_text(encoding="utf-8"))
                for k, v in (dados.get("parametros") or {}).items():
                    if k in self.params and isinstance(v, (int, float)):
                        self.params[k] = float(v)
                sem = ((dados.get("portao_gpu") or {}).get("sem_tf") or {})
                self._portao_sem_tf = {k: float(sem[k]) for k in ("fator_seguranca", "omega_max_tiro", "cooldown_s")
                                       if isinstance(sem.get(k), (int, float))}
                self.rede_confianca = self._pesos(dados.get("rede_confianca"))
                self.rede_correcao = self._pesos(dados.get("rede_correcao"))
                if isinstance(dados.get("limiar_confianca"), (int, float)):
                    self.limiar_confianca = float(dados["limiar_confianca"])
            except (OSError, ValueError, TypeError, KeyError):
                self.rede_confianca = self.rede_correcao = None
        self._params_tf = dict(self.params)
        self._usar_tf = True
        self.lat_cam = float(latencia_camera_s)
        self.semente = int(semente)
        self.rastreador = RastreadorAlvo(self.lat_cam, q_jerk=self.params["q_jerk"], semente=semente)
        self.reiniciar()

    @property
    def usar_tf(self) -> bool:
        return self._usar_tf

    @usar_tf.setter
    def usar_tf(self, valor: bool) -> None:
        """Sem as redes TF o portão passa a ser o MELHOR portão só-físico que a fase GPU encontrou (comparação justa)."""
        self._usar_tf = bool(valor)
        self.params = dict(self._params_tf)
        if not self._usar_tf:
            self.params.update(self._portao_sem_tf)

    @staticmethod
    def _pesos(d) -> dict | None:
        """Pesos de uma rede exportada — None se não existir ou se foi treinada com OUTRO vetor de características
        (o tamanho tem de ser `N_CARACTERISTICAS`: uma rede velha nunca é usada com características novas)."""
        if not isinstance(d, dict):
            return None
        pesos = {k: (np.asarray(v, dtype=np.float64) if isinstance(v, list) else v) for k, v in d.items()}
        if np.asarray(pesos.get("mu", ())).shape != (N_CARACTERISTICAS,):
            return None
        return pesos

    @property
    def limiar(self) -> float:
        """P(acerto) mínima para atirar: K/(1+K) — ou o limiar calibrado no treino (nunca abaixo de K/(1+K))."""
        k = float(self.params["penalidade"])
        base = k / (1.0 + k)
        return max(base, self.limiar_confianca) if self.limiar_confianca is not None else base

    def reiniciar(self) -> None:
        self.i_yaw = 0.0
        self.c_el = 0.0
        self.eps_ant: float | None = None
        self.eps_dot = 0.0
        self.t_ultimo_tiro = -10.0
        self.rastreador.reiniciar(None)
        self.ultimo: dict = {}
        self.desligar_correcao = False

    # ------------------------------------------------------------------ solução balística (o que o drone calcula)
    def _solucao(self, env) -> dict:
        pl = env.planta
        lat_tiro = float(pl.hw.arma.dados.get("latencia_disparo_ms", 16.0)) / 1000.0 if pl.hw.arma else 0.016
        v0 = pl.hw.arma.velocidade_boca if pl.hw.arma else V0_PADRAO
        t = float(env.data.time)
        p_boca, ex_verd, v_boca = estado_boca(env)
        p_cam = env.data.cam_xpos[pl._cid_fpv].copy() if pl._cid_fpv is not None else p_boca
        p_hat, v_hat, a_hat = self.rastreador.passo(t, np.asarray(env.ponto_alvo, dtype=float), p_cam)
        p_saida = p_boca + v_boca * lat_tiro            # onde a boca estará quando a bala sair
        tau = float(np.linalg.norm(p_hat - p_saida)) / v0
        for _ in range(2):
            tt = lat_tiro + tau
            p_imp = p_hat + v_hat * tt + 0.5 * a_hat * tt * tt
            tau = float(np.linalg.norm(p_imp - p_saida)) / v0
        g = abs(float(env.model.opt.gravity[2]))
        d = (p_imp - p_saida) / max(tau, 1e-4) - v_boca + np.array([0.0, 0.0, 0.5 * g * tau])
        d /= max(float(np.linalg.norm(d)), 1e-9)
        eps_req = math.atan2(float(d[2]), math.hypot(float(d[0]), float(d[1])))
        psi_req = math.atan2(float(d[1]), float(d[0]))
        # o cano: azimute pelo que a câmara vê (alvo vs retícula, fixos ao corpo) — o rumo verdadeiro; elevação pela
        # atitude ESTIMADA do núcleo (o que o controlador segura) e pela câmara (o que o integrador corrige)
        rmat = env.data.xmat[pl.corpo].reshape(3, 3)
        roll_v, pitch_v, yaw_v = atitude_zyx(rmat)
        roll_e, pitch_e = float(env.estimador.roll), float(env.estimador.pitch)
        d_cano_est = direcao_cano(roll_e, pitch_e, yaw_v)
        eps_cano_est = math.atan2(float(d_cano_est[2]), math.hypot(float(d_cano_est[0]), float(d_cano_est[1])))
        eps_cano_cam = math.atan2(float(ex_verd[2]), math.hypot(float(ex_verd[0]), float(ex_verd[1])))
        rel = p_imp - p_saida
        dist = float(np.linalg.norm(rel))
        dist_xy = max(math.hypot(float(rel[0]), float(rel[1])), 0.3)
        w_los = (float(rel[0]) * float(v_hat[1]) - float(rel[1]) * float(v_hat[0])) / (dist_xy * dist_xy)
        return {"t": t, "lat_tiro": lat_tiro, "v0": v0, "tau": tau, "p_boca": p_boca, "v_boca": v_boca,
                "p_hat": p_hat, "v_hat": v_hat, "a_hat": a_hat, "p_imp": p_imp, "d_req": d, "eps_req": eps_req,
                "psi_req": psi_req, "eps_cano_est": eps_cano_est, "eps_cano_cam": eps_cano_cam, "yaw": yaw_v,
                "roll_e": roll_e, "pitch_e": pitch_e, "dist": dist, "w_los": w_los, "d_cano_est": d_cano_est,
                "p_saida": p_saida, "pitch_v": pitch_v, "roll_v": roll_v}

    # ------------------------------------------------------------------ comando de voo (50 Hz)
    def passo(self, env, dt: float = 0.02) -> dict:
        """Comando para o núcleo: segura xyz (v = 0), guinada para o azimute e pitch do corpo para a elevação."""
        p = self.params
        s = self._solucao(env)
        e_az = _envolve(s["psi_req"] - s["yaw"]) + SIGMA_ANGULO_CAMERA * float(self.rastreador.rng.normal())
        if abs(e_az) < 0.2:
            self.i_yaw = float(np.clip(self.i_yaw + p["ki_yaw"] * e_az * dt, -0.15, 0.15))
        else:
            self.i_yaw *= 0.9
        yaw_taxa = float(np.clip(p["kp_yaw"] * e_az + self.i_yaw + p["kff_yaw"] * s["w_los"], -p["yaw_max"], p["yaw_max"]))
        # elevação: integrador do erro que a CÂMARA vê (com ruído) — tira o viés do estimador de atitude
        e_el_cam = s["eps_req"] - s["eps_cano_cam"] + SIGMA_ANGULO_CAMERA * float(self.rastreador.rng.normal())
        if abs(e_el_cam) < math.radians(4.0):
            self.c_el = float(np.clip(self.c_el + p["ki_el"] * e_el_cam * dt, -p["lim_c_el"], p["lim_c_el"]))
        if self.eps_ant is not None:
            self.eps_dot += (dt / (0.10 + dt)) * ((s["eps_req"] - self.eps_ant) / max(dt, 1e-4) - self.eps_dot)
        self.eps_ant = s["eps_req"]
        k_att = _k_att(env)
        d_el_tf, d_az_tf = self._correcao(env, s, e_az, e_el_cam)
        eps_cmd = s["eps_req"] + self.c_el + d_el_tf + p["kff_el"] * self.eps_dot / max(k_att, 0.5)
        yaw_taxa = float(np.clip(yaw_taxa + p["kp_yaw"] * d_az_tf, -p["yaw_max"], p["yaw_max"]))
        self.ultimo = {**s, "e_az": e_az, "e_el": e_el_cam, "eps_cmd": eps_cmd, "yaw_taxa": yaw_taxa}
        return {"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": yaw_taxa, "pitch_corpo": -eps_cmd}

    def _correcao(self, env, s: dict, e_az: float, e_el: float) -> tuple[float, float]:
        """Correção residual (Δε, Δψ) da `RedeCorrecaoMiraTF` — ±0,5° no máximo (só o resíduo sistemático)."""
        if self.rede_correcao is None or not self.usar_tf or self.desligar_correcao:
            return 0.0, 0.0
        x = self.caracteristicas(env, s=s, e_az=e_az, e_el=e_el)
        y = np.tanh(mlp_inferir(self.rede_correcao, x[None, :])[0]) * math.radians(0.5)
        return float(y[0]), float(y[1])

    # ------------------------------------------------------------------ características (as MESMAS no treino)
    def caracteristicas(self, env, s: dict | None = None, e_az: float | None = None, e_el: float | None = None) -> np.ndarray:
        s = self.ultimo if s is None else s
        pl = env.planta
        q = pl.juntas_medidas()
        _tau, tau_d = pl.inclinacao_motores_medida()
        giro = pl.imu.giro.medicao
        r_col = pl.raio_bola + 0.0045
        erro_prev = self.erro_previsto(env, s)
        c, sn = math.cos(s["yaw"]), math.sin(s["yaw"])
        vb = s["v_hat"]
        t_desde = min(1.0, float(env.data.time) - self.t_ultimo_tiro)
        pitch_cmd = -float(s.get("eps_cmd", s["eps_req"]))
        x = np.array([
            *(q / (math.pi / 4.0)), tau_d, s["roll_e"], s["pitch_e"], *giro,
            50.0 * float(e_el if e_el is not None else s.get("e_el", 0.0)),
            50.0 * float(e_az if e_az is not None else s.get("e_az", 0.0)),
            erro_prev / r_col, s["tau"] * 100.0, s["dist"] / 3.0, s["eps_req"],
            c * vb[0] + sn * vb[1], -sn * vb[0] + c * vb[1], vb[2], float(np.linalg.norm(s["a_hat"])) / 2.0,
            t_desde, (float(s["p_hat"][2]) - float(s["p_boca"][2])) / 1.5,
            50.0 * (pitch_cmd - s["pitch_e"]), self.rastreador.incerteza() * 20.0,
            float(env.estimador.vz), math.hypot(float(env.estimador.vx), float(env.estimador.vy)),
        ], dtype=np.float64)
        return x

    def erro_previsto(self, env, s: dict | None = None) -> float:
        """Distância (m) a que a bala passará do ponto de impacto previsto, com o cano ESTIMADO rodado pelo giroscópio
        durante a latência de disparo — o «vou acertar?» analítico do próprio drone."""
        s = self.ultimo if s is None else s
        giro = np.asarray(env.planta.imu.giro.medicao, dtype=float)
        rmat = env.data.xmat[env.planta.corpo].reshape(3, 3)
        w_mundo = rmat @ giro
        d0 = s["d_cano_est"]
        d1 = d0 + np.cross(w_mundo, d0) * s["lat_tiro"]
        d1 /= max(float(np.linalg.norm(d1)), 1e-9)
        v_bala = s["v_boca"] + s["v0"] * d1
        rel = s["p_imp"] - s["p_saida"]
        t_min = max(0.0, float(rel @ v_bala) / max(float(v_bala @ v_bala), 1e-9))
        g = np.array([0.0, 0.0, float(env.model.opt.gravity[2])])
        p_bala = s["p_saida"] + v_bala * t_min + 0.5 * g * t_min * t_min
        return float(np.linalg.norm(p_bala - s["p_imp"]))

    def probabilidade_acerto(self, env) -> float | None:
        if self.rede_confianca is None or not self.usar_tf:
            return None
        x = self.caracteristicas(env)
        z = float(mlp_inferir(self.rede_confianca, x[None, :])[0, 0])
        return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, z))))

    # ------------------------------------------------------------------ decisão de tiro
    def portao_fisico(self, env) -> bool:
        p = self.params
        if not getattr(env, "com_alvo", False) or env.hw.arma is None or not self.ultimo:
            return False
        if float(env.data.time) - self.t_ultimo_tiro < p["cooldown_s"]:
            return False
        if env.planta._tiros_ativos or getattr(env, "tiros_pendentes", 0):
            return False
        giro = env.planta.imu.giro.medicao
        if math.hypot(float(giro[1]), float(giro[2])) > p["omega_max_tiro"]:
            return False
        est = env.estimador                              # estabilidade do PRÓPRIO drone (o recuo empurra-o)
        if abs(float(est.vz)) > p["vz_max_tiro"] or math.hypot(float(est.vx), float(est.vy)) > p["vxy_max_tiro"]:
            return False
        if abs(float(est.roll)) > p["roll_max_tiro"]:
            return False
        r_col = env.planta.raio_bola + 0.0045
        return self.erro_previsto(env) <= p["fator_seguranca"] * r_col

    def deve_atirar(self, env) -> bool:
        """Atira só se o portão físico passa E P(acerto) ≥ K/(1+K) (com a rede TF; sem ela, só o portão físico)."""
        if not self.portao_fisico(env):
            return False
        prob = self.probabilidade_acerto(env)
        if prob is not None and prob < self.limiar:
            return False
        self.t_ultimo_tiro = float(env.data.time)
        return True

    def atirar(self, env) -> None:
        """Ordem de disparo com a latência real do gatilho (a bala sai `latencia_disparo` depois)."""
        lat = float(env.hw.arma.dados.get("latencia_disparo_ms", 16.0)) / 1000.0
        env.disparar(1, atraso_s=lat)


__all__ = ["CAMINHO_MODELO", "LATENCIA_CAMERA_DCMI_S", "LATENCIA_CAMERA_PI_S", "MiraArticuladaIA", "N_CARACTERISTICAS",
           "NOMES_CARACTERISTICAS", "PARAMETROS_PADRAO", "RastreadorAlvo", "atitude_zyx", "direcao_cano", "estado_boca",
           "mlp_inferir", "simular_bala"]
