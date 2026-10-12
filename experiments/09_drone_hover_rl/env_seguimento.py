"""experiments/09_drone_hover_rl/env_seguimento.py — IA nº 2: SEGUIMENTO VISUAL («ver o ponto e seguir»).

CASCATA (desenho do dono, 2026-10-12): ponto-alvo → detetor → **IA-seguimento (esta)** → `v_ref`
(±1,0 m/s xy, ±0,7 m/s z — MESMA semântica do WASDQE/contrato r11) → **IA-voo interior**
(`out/real_1950_voo_final/final.zip`, CONGELADA) → FC (malha de taxa) → física.

DESENHO (decisões vinculativas do dono — cumpridas à letra; as alíneas [n] são as dele):

1. PONTO-ALVO visível: corpo mocap `ponto` (esfera emissiva) criado por `com_alvo=True` no modelo
   (`lab/drone_rpi/modelo.py`), movido em trajetória pelo `DroneRealEnv` (0,3–0,8 m/s, começando à
   frente do drone). A física do drone não muda (mocap = cenário).
2. OBS do tracker (ator, pequena e REALISTA): posição do ponto na imagem (u,v normalizados ao centro) +
   escala aparente (raio em píxeis normalizado) + o `v_ref` atual + erro de posição em píxeis (aqui as
   duas componentes u,v em píxeis normalizadas à largura/altura). No TREINO (u,v) vêm da **PROJEÇÃO
   EXATA** (`visao.projetar` — a matemática do `_cam_projection` do MuJoCo, provada contra a
   renderização); no DEPLOY real seria o detetor clássico (threshold da esfera brilhante) — a validação
   da honestidade é `teste_seguimento.py` (render real → detetor → erro < 1–2 px vs projeção).
   PROPRIOCEÇÃO obrigatória (injeção da pesquisa, arXiv 2609.09234: sem ela a sobrevivência cai de
   97,1 % para 4,4 %): v̂ do estimador de bordo, ω medido, roll/pitch (gravidade).
   LATÊNCIA INJETADA na obs: 116 ms (a latência de modelo da nossa câmara @1080p50) — treinar com
   latência zero e voar com atraso é instabilidade garantida (armadilha 3 da pesquisa).
3. AÇÃO: `v_ref` (3) em [-1,1]³ → escalada ao envelope r11 (±1,0/±0,7 m/s) — exatamente o que a IA-voo
   interior sabe seguir. O env usa a API EXISTENTE `DroneRealEnv.definir_v_ref` (clamps no envelope).
4. RECOMPENSA: ponto centrado (−‖(u,v)‖), distância-alvo ao ponto (manter 1–2 m; d* = 1,5 m explícito),
   sobrevivência, suavidade (−‖Δv_ref‖) e penalidade FORTE por deixar o ponto sair do FOV (−5/ passo).
   Episódios de 10 s.
5. TREINO: `train_seguimento.py` — PPO SB3, MLP 64-64, 2 seeds × 1–2 M passos, currículo
   (ponto parado → móvel lento → 0,8 m/s).
6. AVALIAÇÃO: rollouts com trajetórias NUNCA vistas (círculo, oito, aleatório) — ver
   `avaliar_seguimento` (erro de seguimento em m, centragem em px, % FOV, estabilidade ‖Δv_ref‖).
"""
from __future__ import annotations

import math
import sys
from collections import deque
from pathlib import Path
from typing import ClassVar

import numpy as np

_AQUI = Path(__file__).resolve().parent
_RAIZ = _AQUI.parent.parent
for _p in (str(_RAIZ), str(_AQUI)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gymnasium
import visao
from env_real import VOO_SUBIDA, VOO_VEL, DroneRealEnv
from gymnasium import spaces

# ------------------------------------------------------------------------------- constantes do desenho
D_ESTRELA = 1.5            # m — a distância-alvo ao ponto (a banda do dono é 1–2 m)
PASSOS_POR_ACAO = 2        # 2 passos interiores (50 Hz) por ação do tracker = 25 Hz (banda 25–30 Hz)
LATENCIA_S = 0.116         # s — latência de MODELO da câmara emulada @1080p50 (injetada na obs)
PENALIDADE_FUFO = 5.0      # por passo com o ponto FORA do FOV (a regra «NUNCA sair do FOV»)
OMEGA_ESCALA = 2.0         # rad/s
V_ESCALA = 2.0             # m/s
RAIO_ESCALA = 0.25         # normalização do raio em píxeis (raio/(altura/4) clamped a 1)

OBS_DIM = 17               # u,v norm · escala · visível · v_ref(3) · erro_px(2) · v̂(3) · ω(3) · roll, pitch



class _PilotoOnnx:
    """IA-voo CONGELADA via ONNX (o `deploy.py` exporta e valida: max|Δ| ~1e-6 vs torch).

    O `predict` do SB3 em torch custava ~2 ms por chamada e dominava o passo do tracker (medido: 67
    passos/s agregados com 4 envs); o ONNX custa ~65 µs — a cascata passa a correr à velocidade da
    física. Fallback: se não houver `policy.onnx` ao lado do `.zip`, usa-se o PPO em torch (lento).
    """

    def __init__(self, piloto_zip: str | Path):
        caminho = Path(piloto_zip)
        onnx = caminho.parent / "policy.onnx"
        import onnxruntime as ort
        from stable_baselines3 import PPO
        modelo = PPO.load(str(caminho), device="cpu")
        self.n_ator = int(getattr(modelo.policy, "_n_ator", 0)) or None
        self.sessao = ort.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])
        self.entrada = self.sessao.get_inputs()[0].name
        self.dim = int(self.sessao.get_inputs()[0].shape[1])
        del modelo                                   # só precisávamos do _n_ator/dimensão

    def predict(self, obs, deterministic: bool = True):
        a = np.asarray(obs, dtype=np.float32).reshape(-1)
        if self.n_ator:
            a = a[: self.n_ator]
        saida = self.sessao.run(None, {self.entrada: a.reshape(1, -1).astype(np.float32)})[0]
        return np.asarray(saida[0], dtype=np.float32), None


class EnvSeguimento(gymnasium.Env):
    """Tracker visual: obs (projeção + propriocepção) → `v_ref` → IA-voo CONGELADA → FC → física.

    O ponto-alvo é o corpo mocap `ponto` (cenário) movido pelo `DroneRealEnv` (0,3–0,8 m/s). A ação é a
    MESMA do WASDQE: velocidades no envelope r11. A IA-voo interior (`--comandos`) está CONGELADA —
    «freeze inner, train outer» (a evidência A da pesquisa: treinar só o nível de cima é mais eficiente).
    """

    metadata: ClassVar[dict] = {"render_modes": []}

    def __init__(self, piloto_zip: str | Path, episodio_s: float = 10.0, latencia_s: float = LATENCIA_S,
                 trajetoria: str = "aleatorio", vel_ponto: float = 0.5, resolucao: tuple[int, int] = (1920, 1080),
                 vento: float = 0.0):
        super().__init__()
        # CONGELADA (nunca treina): ONNX quando existe `policy.onnx` ao lado (65 µs), torch senão
        if (Path(piloto_zip).parent / "policy.onnx").is_file():
            self.piloto = _PilotoOnnx(piloto_zip)
        else:
            from stable_baselines3 import PPO
            self.piloto = PPO.load(str(piloto_zip), device="cpu")
        self.env = DroneRealEnv(build=None, modo_acao="ctbr", comando=True, comandos_aleatorios=False,
                                com_alvo=True, episodio_s=episodio_s)
        self.trajetoria = trajetoria
        self.vel_ponto = float(vel_ponto)
        self.resolucao = (int(resolucao[0]), int(resolucao[1]))
        self.vento = float(vento)
        self.dt_guia = self.env.dt_decisao * PASSOS_POR_ACAO
        self.max_passos = max(1, round(episodio_s / self.dt_guia))
        self._latencia_passos = max(1, round(latencia_s / self.dt_guia))
        self._fila_obs: deque = deque(maxlen=self._latencia_passos + 1)
        self._v_ref = np.zeros(3)
        self._passos = 0
        self.observation_space = spaces.Box(low=-10.0, high=10.0, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(3,), dtype=np.float32)

    # ------------------------------------------------------------------------------ percepção
    def _ver_projecao(self) -> dict:
        """(u, v, raio_px, profundidade) pela PROJEÇÃO EXATA do ponto no modelo da câmara (treino).

        O `teste_seguimento.py` prova que esta projeção bate com o render real + detetor clássico
        (erro < 1–2 px) — é por isso que o treino pode usar a projeção sem mentir sobre o deploy.
        """
        import mujoco
        mujoco.mj_forward(self.env.model, self.env.data)
        pos = np.asarray(self.env.ponto_alvo, dtype=float)
        larg, alt = self.resolucao
        proj = visao.projetar(self.env.model, self.env.data, pos, camera="fpv",
                              largura_px=larg, altura_px=alt)
        if not proj["visivel"]:
            return {"visivel": False, "u": None, "v": None, "raio_px": 0.0, "profundidade": None}
        k = visao.intrinsecos(self.env.model, "fpv", alt)
        raio_px = k["f"] * visao.RAIO_PONTO / proj["profundidade"] if proj["profundidade"] > 0 else 0.0
        return {"visivel": True, "u": proj["u"], "v": proj["v"], "raio_px": float(raio_px),
                "profundidade": float(proj["profundidade"])}

    def _observacao(self, vis: dict) -> np.ndarray:
        """obs 17D — REFERÊNCIA para o mecanismo multi-IA (frente B copia esta grelha):

        | canal | conteúdo | normalização |
        |---|---|---|
        | [0] | u do ponto na imagem | (u−cx)/cx |
        | [1] | v do ponto na imagem | (v−cy)/cy |
        | [2] | escala aparente (proxy de profundidade) | raio_px/(altura/4), máx 1 |
        | [3] | ponto visível | 0/1 |
        | [4:7] | `v_ref` em vigor | /1,0 xy · /0,7 z (envelope r11) |
        | [7:9] | erro de posição em píxeis | (u−cx)/largura, (v−cy)/altura |
        | [9:12] | v̂ do estimador de bordo | /2,0 m/s |
        | [12:15] | ω medido (IMU) | /2,0 rad/s |
        | [15:17] | roll, pitch (gravidade do estimador) | /π |

        Propriocepção [9:17] OBRIGATÓRIA (literatura: sem ela a sobrevivência cai de 97,1 % para 4,4 %).
        """
        larg, alt = self.resolucao
        cx, cy = larg / 2.0, alt / 2.0
        est, imu = self.env.estimador, self.env.planta.imu
        if vis["visivel"]:
            u_n = (vis["u"] - cx) / cx
            v_n = (vis["v"] - cy) / cy
            escala = min(vis["raio_px"] / (alt / 4.0), 1.0)
            flag = 1.0
            erro_px = np.array([(vis["u"] - cx) / larg, (vis["v"] - cy) / alt])   # erro em píxeis/normalizado
        else:
            u_n = v_n = escala = flag = 0.0
            erro_px = np.zeros(2)
        v_ref = np.array([self._v_ref[0] / VOO_VEL, self._v_ref[1] / VOO_VEL, self._v_ref[2] / VOO_SUBIDA])
        v_est = np.array([est.vx, est.vy, est.vz]) / V_ESCALA
        omega = np.asarray(imu.giro.medicao, dtype=float) / OMEGA_ESCALA
        obs = np.concatenate(([u_n, v_n, escala, flag], v_ref, erro_px, v_est, omega,
                              [est.roll / math.pi, est.pitch / math.pi]))
        return np.clip(obs, -10.0, 10.0).astype(np.float32)

    # ------------------------------------------------------------------------------ ciclo
    def definir_trajetoria_ponto(self, modo: str, vel: float = 0.5, raio: float = 1.5) -> None:
        """Encaminha a troca de trajetória do ponto para o env físico (`env_method` do SB3).

        SEM este encaminhamento o wrapper não tem o método, os workers do `SubprocVecEnv` morrem na
        troca de estágio do currículo e o `train_seguimento.py` rebenta em `EOFError` (medido em
        2026-10-12: o gate abriu, o currículo avançou… e o processo morreu). Mantém `trajetoria`/
        `vel_ponto` do wrapper em sincronia (o `reset` usa-os).
        """
        self.trajetoria = modo
        self.vel_ponto = float(vel)
        self.env.definir_trajetoria_ponto(modo, vel=vel, raio=raio)

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        traj = (options or {}).get("trajetoria", self.trajetoria)
        vel = float((options or {}).get("vel_ponto", self.vel_ponto))
        _obs_env, _info = self.env.reset(seed=seed)
        self.env.definir_trajetoria_ponto(traj, vel=vel, raio=1.5)
        if self.vento > 0:
            self.env.definir_vento(self.vento, float(np.random.default_rng(seed).uniform(0, 360)))
        else:
            self.env.definir_vento(0.0, 0.0)
        # aquecimento: a IA-voo leva o drone a pairar (~2 s) — o tracker começa a voar, como no uso real
        self.env.definir_v_ref([0.0, 0.0, 0.0])
        for _ in range(100):
            acao, _ = self.piloto.predict(self.env.observacao(), deterministic=True)
            self.env.step(acao)
        self._v_ref = np.zeros(3)
        vis = self._ver_projecao()
        primeiro = self._observacao(vis)
        self._fila_obs.clear()
        for _ in range(self._latencia_passos + 1):
            self._fila_obs.append(primeiro)         # latência começa preenchida
        self._passos = 0
        return self._fila_obs[0].copy(), {"vis": vis, "trajetoria": traj}

    def step(self, acao):
        a = np.clip(np.asarray(acao, dtype=float).reshape(3), -1.0, 1.0)
        self._v_ref = np.array([a[0] * VOO_VEL, a[1] * VOO_VEL, a[2] * VOO_SUBIDA])   # envelope r11
        self.env.definir_v_ref(self._v_ref)          # API EXISTENTE do env_real (com clamp)
        terminado = truncado = False
        for _ in range(PASSOS_POR_ACAO):
            acao_piloto, _ = self.piloto.predict(self.env.observacao(), deterministic=True)
            _obs, _r, terminado, truncado, _info = self.env.step(acao_piloto)   # IA-voo CONGELADA
            if terminado or truncado:
                break
        vis = self._ver_projecao()
        obs_fresca = self._observacao(vis)
        self._fila_obs.append(obs_fresca)
        obs = self._fila_obs[0].copy()               # obs ATRASADA (latência de modelo da câmara)

        # ------------------------------------------------------------- recompensa (desenho do dono)
        larg, alt = self.resolucao
        cx, cy = larg / 2.0, alt / 2.0
        if vis["visivel"]:
            e_centro = math.hypot((vis["u"] - cx) / cx, (vis["v"] - cy) / cy)
            d = vis["profundidade"]
            r_dist = abs(d - D_ESTRELA) if d is not None else 0.0
            r_fufo = 0.0
        else:
            e_centro, r_dist, r_fufo = 0.0, 0.0, PENALIDADE_FUFO
        sobrevivencia = 0.0 if terminado else 0.5
        dv_ref = float(np.linalg.norm(self._v_ref - getattr(self, "_v_ref_anterior", self._v_ref)))
        recompensa = (sobrevivencia - 1.0 * e_centro - 1.0 * r_dist - 0.05 * dv_ref - r_fufo)
        self._v_ref_anterior = self._v_ref.copy()
        self._passos += 1
        if self._passos >= self.max_passos:
            truncado = True
        info = {"vis": vis, "e_centro_px": (math.hypot(vis["u"] - cx, vis["v"] - cy)
                                            if vis["visivel"] else None),
                "d": vis["profundidade"], "erro_distancia": r_dist if vis["visivel"] else None,
                "visivel": bool(vis["visivel"]), "dv_ref": dv_ref, "v_ref": self._v_ref.tolist(),
                "sobreviveu": not terminado}
        return obs, float(recompensa), bool(terminado), bool(truncado), info

    def fechar(self):
        if hasattr(self.env, "fechar"):
            self.env.fechar()


def avaliar_seguimento(guia_zip: Path, piloto_zip: Path, episodios: int = 5,
                       resolucao: tuple[int, int] = (1920, 1080)) -> dict:
    """Avaliação OBRIGATÓRIA com trajetórias NUNCA vistas: círculo, oito, aleatório (0,3–0,8 m/s)."""
    from stable_baselines3 import PPO
    guia = PPO.load(str(guia_zip), device="cpu")
    saida: dict = {}
    for traj in ("circulo", "oito", "aleatorio"):
        env = EnvSeguimento(piloto_zip, trajetoria=traj, vel_ponto=0.6, resolucao=resolucao)
        centros, dds, dvs, fofo, passos, vivos = [], [], [], 0, 0, 0
        for k in range(episodios):
            obs, info = env.reset(seed=9000 + k)
            while True:
                acao, _ = guia.predict(obs, deterministic=True)
                obs, _r, term, trunc, info = env.step(acao)
                passos += 1
                vivos += int(info["sobreviveu"])
                fofo += int(info["visivel"])
                if info["e_centro_px"] is not None:
                    centros.append(info["e_centro_px"])
                if info["erro_distancia"] is not None:
                    dds.append(info["erro_distancia"])
                dvs.append(info["dv_ref"])
                if term or trunc:
                    break
        env.fechar()
        saida[traj] = {"erro_seguimento_m": float(np.mean(dds)) if dds else None,
                       "erro_centragem_px": float(np.mean(centros)) if centros else None,
                       "frac_tempo_fov": fofo / max(passos, 1),
                       "sobrevivencia": vivos / max(passos, 1),
                       "dv_ref_medio": float(np.mean(dvs)) if dvs else None,
                       "dv_ref_max": float(np.max(dvs)) if dvs else None,
                       "episodios": episodios}
    return saida
