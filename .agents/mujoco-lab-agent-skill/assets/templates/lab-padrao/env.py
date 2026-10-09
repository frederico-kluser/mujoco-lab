#!/usr/bin/env python3
"""env.py — ambiente Gymnasium PADRÃO do laboratório (template `lab-padrao`): haste com ALVO de ângulo.

Este ficheiro é a peça que o `train.py` (PPO), o `deploy.py` (ONNX) e o `sim_view.py` (rollout ao vivo)
partilham. Ao copiar o template para outro robô muda-se o MODELO e a FÍSICA daqui; o CONTRATO não muda.

O que o ambiente faz (o padrão que se repete em todos os experimentos de RL do laboratório):
  1. OBSERVAÇÃO NORMALIZADA — `obs` ≈ [-1, 1], sem unidades cruas: [cos θ, sin θ, θ̇/ESCALA_OMEGA, erro/π].
  2. AÇÃO CENTRADA NO ALVO — a política não aprende o esforço absoluto: a ação `a ∈ [-1, 1]` é o DESVIO em
     torno do torque de equilíbrio no alvo (`trim = m·g·d·sin(θ_alvo)`, lido do MODELO compilado).
     `ctrl = trim + a·TORQUE_DELTA_MAX`. Sem isto a política gasta capacidade a redescobrir a gravidade.
  3. RECOMPENSA com bónus e terminação — penaliza erro/velocidade/esforço/taxa de ação, dá `BONUS_ALVO` por
     estar dentro da tolerância e TERMINA se o erro passar do envelope (`ERRO_TERMINA`) com penalidade.
  4. PERTURBAÇÃO ("VENTO") em tempo real — `definir_vento(vel, azimute, elevacao)` aplica uma força de
     arrasto quadrático NO SITE `ponta` que entra na física como torque generalizado (`qfrc_applied`), lida
     a cada passo de decisão. É o análogo do modelo de fluido do MuJoCo usado no drone.
  5. GUARDAS NaN — nenhum estado não finito passa em silêncio: `_verifica_sanidade` levanta `RuntimeError`
     com o motivo (o MuJoCo só avisa e devolve "huge values", que envenenariam o treino em silêncio).

Roda sem janela nenhuma (nenhum import de `mujoco.viewer`: `lab.mjkit` fixa MUJOCO_GL=egl antes do mujoco).

    uv run --group hover-rl python -c "import env; e = env.novo_env(); print(e.reset()[0])"

ADAPTAR ao teu robô (por ordem): (a) `model.xml` → o teu modelo/`models/<robo>/`; (b) os NOMES lidos do
modelo (secção «nomes lidos do modelo»); (c) a observação e a recompensa (`recompensa()` e `observacao()`);
(d) a perturbação (`_forca_vento()`), se o teu robô não tiver uma "vela". O resto (contrato de step/reset,
trim, guardas) fica.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import ClassVar

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
from lab import mjkit  # noqa: I001  (MJKP: MUJOCO_GL=egl fixado antes de `import mujoco`: ordem intencional)

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces

AQUI = Path(__file__).resolve().parent
MODELO_OMISSAO = AQUI / "model.xml"

# --------------------------------------------------------------------------- nomes lidos do modelo (ADAPTAR)
JUNTA = "pivo"          # junta hinge accionada (1 DOF)
ATUADOR = "torque"      # atuador de torque dessa junta (ctrl em N·m)
SITE_PONTA = "ponta"    # site onde a perturbação é aplicada (e de onde sai o braço de alavanca)

# --------------------------------------------------------------------------- escalas da observação (normalizada)
ESCALA_OMEGA = 10.0     # rad/s → [2]  θ̇/10
ESCALA_ERRO = np.pi     # rad   → [3]  (θ − θ_alvo)/π
N_OBS = 4               # ADAPTAR: nº de entradas da rede (o site desenha o que vier na telemetria)
N_ACT = 1               # ADAPTAR: nº de saídas

# --------------------------------------------------------------------------- física do EPISÓDIO (o exemplo)
ALVO_GRAUS = 60.0         # ângulo-alvo por omissão (graus); o `run.py` valida a fórmula do trim neste alvo
DECIMACAO = 10            # passos de física por passo de decisão (2 ms × 10 = 20 ms = 50 Hz)
PASSOS_MAX = 500          # teto do episódio (10 s a 50 Hz)
TORQUE_DELTA_MAX = 15.0   # N·m — meia-amplitude da ação em torno do trim (ctrlrange do modelo é ±30)
JITTER_ALVO = np.radians(5.0)   # rad — jitter do ângulo no reset (evita decorar um único estado inicial)

# --------------------------------------------------------------------------- terminação / bónus
ERRO_TERMINA = np.radians(80.0)   # rad — envelope: erro maior que isto = "saiu do alvo" (episódio termina)
PENALIDADE_TERMINAL = 50.0
BONUS_ALVO = 1.0                  # por passo dentro da tolerância
BONUS_TOL = np.radians(3.0)       # rad — tolerância do bónus (ESTRITA: 3°)
ALVO_TOL = BONUS_TOL              # compatibilidade com a UI (o site mostra a mesma tolerância)

# --------------------------------------------------------------------------- pesos da recompensa
# Tudo em unidades NORMALIZADAS (o erro em tolerâncias, a velocidade na escala da obs, a ação em [-1, 1]):
# assim os pesos não dependem do robô e comparam-se entre rondas — foi o que se aprendeu no experimento 09,
# onde a penalidade da taxa de ação estava na unidade errada e criava um ATRATOR de chatter (políticas que
# saturavam e capotavam). O ESFORÇO ABSOLUTO (o trim da gravidade) NÃO é penalizado; só o desvio à ação nula.
PESO_ERRO = 1.0        # 1/tol²  — erro² em tolerâncias (o bónus +1 cancela exactamente na borda da tolerância)
TETO_ERRO = 5.0        # tol     — saturação do termo do erro (longe do alvo o quadrado domina tudo)
PESO_OMEGA = 0.05      # 1/1     — velocidade angular na escala da observação
PESO_ACAO = 0.001      # 1/1     — esforço (desvio ao trim)
PESO_DELTA_ACAO = 0.05  # 1/1    — taxa de ação (contra o chatter)

# --------------------------------------------------------------------------- perturbação ("vento")
VENTO_VEL_MAX = 5.0               # m/s — teto da UI/CLI (o `run.py --vento` valida a faixa)
VENTO_ELEV_MAX = np.radians(20.0)  # rad — elevação máxima do vento aleatório
AREA_VELA = 0.5                   # m²  — área de referência exposta ao vento (ADAPTAR: A do teu robô)
CD_VELA = 1.2                     # —   coeficiente de arrasto
RHO_AR = 1.225                    # kg/m³
VENTO_DINAMICO_MODOS = ("rajadas", "frente", "dryden")
RAJADAS_P = 0.02                  # 1/passo de decisão
RAJADAS_DURACAO = 10              # passos
FRENTE_T_S = 2.0                  # s — instante da frente
DRYDEN_SIGMA = 0.5                # m/s
DRYDEN_L = 10.0                   # m
DRYDEN_V_MIN = 1.0                # m/s

# --------------------------------------------------------------------------- tetos de sanidade
SANIDADE_THETA_MAX = 1.0e3        # rad   — um estado legítimo fica em |θ| ≤ π
SANIDADE_OMEGA_MAX = 1.0e5        # rad/s — e |θ̇| ≲ 100 rad/s (o torque máximo dá ~16 rad/s²)


# --------------------------------------------------------------------------- puros (funções fechadas, testáveis)
def finito(nome: str, valor) -> float:
    """Converte para `float` e EXIGE um valor finito — `ValueError` claro em vez de NaN/inf silencioso."""
    try:
        v = float(valor)
    except (TypeError, ValueError) as erro:
        raise ValueError(f"{nome}: esperava um número, recebi {valor!r} ({erro})") from erro
    if not np.isfinite(v):
        raise ValueError(f"{nome}: valor não finito ({v}) — NaN/inf não entra na física")
    return v


def envolve_pi(angulo: float) -> float:
    """Traz um ângulo para (−π, π] — o erro do alvo tem de ser sempre o caminho curto."""
    return float((angulo + np.pi) % (2 * np.pi) - np.pi)


def vetor_vento(vel: float, azimute_graus: float, elevacao_graus: float = 0.0) -> np.ndarray:
    """Velocidade do vento (m/s) em coordenadas do MUNDO: azimute em graus a partir de +X, elevação em graus."""
    v = finito("vel", vel)
    a = np.radians(finito("azimute", azimute_graus))
    e = np.radians(finito("elevacao", elevacao_graus))
    return np.array([v * np.cos(e) * np.cos(a), v * np.cos(e) * np.sin(a), v * np.sin(e)])


def azimute_graus(vento) -> float:
    """Azimute (graus, 0–360) de um vetor de vento — o inverso de `vetor_vento` (para a telemetria/UI)."""
    v = np.asarray(vento, dtype=float).reshape(-1)
    if v.size < 2 or not np.all(np.isfinite(v[:2])) or np.hypot(v[0], v[1]) < 1e-12:
        return 0.0
    return float(np.degrees(np.arctan2(v[1], v[0])) % 360.0)


def bonus_no_alvo(erro: float, tol: float = BONUS_TOL) -> bool:
    """`True` quando o erro está dentro da tolerância do bónus."""
    return abs(envolve_pi(erro)) < tol


def termina(erro: float, envelope: float = ERRO_TERMINA) -> bool:
    """`True` quando o erro saiu do envelope do episódio (o robô "caiu"/perdeu o alvo)."""
    return abs(envolve_pi(erro)) > envelope


def recompensa(erro: float, omega: float, acao: float, acao_anterior: float) -> float:
    """Recompensa do passo: erro + velocidade + esforço + taxa de ação, mais o bónus de estar no alvo.

    Unidades NORMALIZADAS (ver os pesos acima). Com |erro| = BONUS_TOL o bónus (+1,0) e o termo do erro
    (−1,0) cancelam-se: a borda da tolerância vale 0 e o interior vale cada vez mais — é o desenho que faz a
    política encostar ao alvo em vez de o rondar.

    ADAPTAR: é AQUI que se muda o que a política aprende. Mantém a FORMA (parcelas explícitas + bónus +
    terminação com penalidade) porque é isso que torna o treino comparável entre rondas.
    """
    en = min(abs(envolve_pi(erro)) / BONUS_TOL, TETO_ERRO)
    r = -(PESO_ERRO * en**2 + PESO_OMEGA * (omega / ESCALA_OMEGA) ** 2
          + PESO_ACAO * acao**2 + PESO_DELTA_ACAO * (acao - acao_anterior) ** 2)
    return float(r + BONUS_ALVO * bonus_no_alvo(erro))


class EnvPadrao(gym.Env):
    """Haste com junta hinge e atuador de torque: manter `theta_alvo` contra gravidade e perturbação."""

    metadata: ClassVar[dict] = {"render_modes": []}   # sem render: a janela é do `view.py`/`sim_view.py`

    def __init__(self, modelo: str | Path = MODELO_OMISSAO, theta_alvo_graus: float = ALVO_GRAUS,
                 decimacao: int = DECIMACAO, passos_max: int = PASSOS_MAX, jitter: bool = True,
                 vento_dinamico: dict | None = None, seed: int | None = None) -> None:
        super().__init__()
        self.modelo_caminho = Path(modelo)
        self.model = mujoco.MjModel.from_xml_path(str(self.modelo_caminho))
        self.data = mujoco.MjData(self.model)
        self.ctrl = mjkit.Ctrl(self.model)                     # escrita por NOME (correta em atuadores multi-entrada)
        self.theta_alvo = finito("theta_alvo_graus", theta_alvo_graus) * np.pi / 180.0
        self.decimacao = int(decimacao)
        self.passos_max = int(passos_max)
        self.jitter = bool(jitter)
        self.vento_dinamico = dict(vento_dinamico) if vento_dinamico else None
        self.rng = np.random.default_rng(seed)
        self.passos = 0
        self.retorno = 0.0
        self.episodios = 0
        self.acao_anterior = 0.0
        self.vento = np.zeros(3)                                # velocidade do vento em vigor (mundo)
        self._vento_dinamico_estado = np.zeros(2)               # estado interno do modo "dryden"
        self._vento_dinamico_pedido: tuple[float, float] | None = None
        self.nan_detetados = 0

        # ---- constantes FÍSICAS lidas do MODELO COMPILADO (nada de números mágicos no código) ----
        self.junta = self.model.joint(JUNTA).id
        self.dof = int(self.model.jnt_dofadr[self.junta])
        self.qadr = int(self.model.jnt_qposadr[self.junta])
        b = self.model.body("haste").id
        mujoco.mj_forward(self.model, self.data)
        self.massa = float(mujoco.mj_getTotalmass(self.model))
        self.braco_com = float(np.linalg.norm(self.data.xipos[b] - self.data.xanchor[self.junta]))
        self.braco_ponta = float(np.linalg.norm(self.data.site(SITE_PONTA).xpos - self.data.xanchor[self.junta]))
        self.gravidade = float(np.linalg.norm(self.model.opt.gravity))
        self.eixo = np.asarray(self.data.xaxis[self.junta], dtype=float).copy()
        self.trim = self.massa * self.gravidade * self.braco_com * np.sin(self.theta_alvo)
        self.inercia = self._inercia_pivo()

        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(N_OBS,), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(N_ACT,), dtype=np.float32)
        self.reset(seed=seed)

    # ------------------------------------------------------------------ leituras do estado
    def _inercia_pivo(self) -> float:
        """Inércia efetiva no pivô (M[0,0]) a partir do modelo compilado — o `run.py` compara-a com a analítica."""
        M = np.zeros((self.model.nv, self.model.nv))
        mujoco.mj_fullM(self.model, self.data, M)   # 3.10+: (m, d, dst); o mjData.qM foi removido na 3.11
        return float(M[self.dof, self.dof])

    @property
    def theta(self) -> float:
        return float(self.data.qpos[self.qadr])

    @property
    def omega(self) -> float:
        return float(self.data.qvel[self.dof])

    @property
    def erro(self) -> float:
        return envolve_pi(self.theta - self.theta_alvo)

    def observacao(self) -> np.ndarray:
        """Observação NORMALIZADA (≈ [-1, 1]): [cos θ, sin θ, θ̇/ESCALA_OMEGA, erro/ESCALA_ERRO]."""
        obs = np.array([np.cos(self.theta), np.sin(self.theta), self.omega / ESCALA_OMEGA,
                        self.erro / ESCALA_ERRO], dtype=np.float32)
        if not np.all(np.isfinite(obs)):
            raise RuntimeError(f"observação não finita {obs} (θ={self.theta}, ω={self.omega}) — estado corrompido")
        return obs

    def definir_alvo(self, theta_alvo_graus: float) -> float:
        """Muda o alvo do episódio e RECALCULA o trim (currículo: o alvo cresce ao longo do treino).

        Sem isto o `ctrl` continuaria centrado no trim do alvo antigo e a política teria de compensar o degrau.
        """
        self.theta_alvo = finito("theta_alvo_graus", theta_alvo_graus) * np.pi / 180.0
        self.trim = self.massa * self.gravidade * self.braco_com * np.sin(self.theta_alvo)
        return float(self.trim)

    # ------------------------------------------------------------------ ação ↔ comando físico
    def acao_para_ctrl(self, acao) -> float:
        """Ação `a ∈ [-1, 1]` → torque FÍSICO (N·m), CENTRADO no trim do alvo. Corta (clip), não rejeita."""
        a = np.asarray(acao, dtype=float).reshape(-1)
        if a.size != N_ACT:
            raise ValueError(f"ação com {a.size} valor(es); esperava {N_ACT}")
        if not np.all(np.isfinite(a)):
            raise ValueError(f"ação não finita: {a}")
        return float(self.trim + np.clip(a[0], -1.0, 1.0) * TORQUE_DELTA_MAX)

    def aplicar_acao(self, acao) -> float:
        """Escreve o comando no atuador (`data.ctrl`) e devolve o torque aplicado. Ação nula = trim (eq. no alvo)."""
        torque = self.acao_para_ctrl(acao)
        self.ctrl.set(self.data, ATUADOR, [torque])
        return torque

    # ------------------------------------------------------------------ perturbação ("vento")
    def definir_vento(self, vel: float, azimute: float, elevacao: float = 0.0) -> None:
        """Põe o vento em vigor (m/s, graus, graus). Aplicado à física no passo de decisão seguinte."""
        v = min(max(finito("vel", vel), 0.0), VENTO_VEL_MAX)
        self.vento = vetor_vento(v, finito("azimute", azimute), finito("elevacao", elevacao))

    def vento_polar(self) -> tuple[float, float]:
        """(velocidade m/s, azimute graus) do vento em vigor — o que a telemetria publica."""
        return float(np.linalg.norm(self.vento)), azimute_graus(self.vento)

    def _forca_vento(self) -> np.ndarray:
        """Força de arrasto quadrático (N) no site da ponta. ADAPTAR: A/Cd do teu robô (ou o fluido do MuJoCo)."""
        v = float(np.linalg.norm(self.vento))
        if v < 1e-9:
            return np.zeros(3)
        return 0.5 * RHO_AR * CD_VELA * AREA_VELA * v * self.vento   # ½ρCdA·|v|·v

    def _aplica_vento(self) -> float:
        """Torque generalizado (N·m) da perturbação: τ = (r × F)·eixo, com r = ponta − pivô."""
        F = self._forca_vento()
        r = np.asarray(self.data.site(SITE_PONTA).xpos, dtype=float) - np.asarray(self.data.xanchor[self.junta], dtype=float)
        tau = float(np.dot(np.cross(r, F), self.eixo))
        self.data.qfrc_applied[self.dof] = tau   # força externa REAL: entra no mj_step (nada de teleporte)
        return tau

    def vento_dinamico_passo(self) -> None:
        """Avança um modo de vento DINÂMICO (domain randomization): rajadas, frente ou turbulência Dryden."""
        cfg = self.vento_dinamico or {}
        modo = str(cfg.get("modo", "rajadas"))
        u_max = float(cfg.get("u_max", 3.0))
        if modo not in VENTO_DINAMICO_MODOS:
            raise ValueError(f"modo de vento dinâmico desconhecido: {modo!r} (use {VENTO_DINAMICO_MODOS})")
        vel, azim = self.vento_polar()
        if modo == "rajadas":
            if self._vento_dinamico_pedido is None and self.rng.random() < float(cfg.get("p", RAJADAS_P)):
                dur = int(cfg.get("duracao", RAJADAS_DURACAO))
                self._vento_dinamico_pedido = (float(self.rng.uniform(0.0, u_max)), float(self.rng.uniform(0.0, 360.0)))
                self._vento_dinamico_estado = np.array([dur], dtype=float)
            if self._vento_dinamico_pedido is not None:
                self._vento_dinamico_estado[0] -= 1
                if self._vento_dinamico_estado[0] <= 0:
                    self._vento_dinamico_pedido = None
                else:
                    vel, azim = self._vento_dinamico_pedido
        elif modo == "frente":
            t = self.passos * self.model.opt.timestep * self.decimacao
            if t >= float(cfg.get("t_s", FRENTE_T_S)):
                vel = min(u_max, max(0.5, float(self.rng.uniform(0.5, u_max))))
                azim = float(cfg.get("azimute", 0.0))
        else:  # dryden: AR(1) com correlação α = exp(−Δt·V/L) sobre a componente transversal
            dt = self.model.opt.timestep * self.decimacao
            sigma = float(cfg.get("sigma", DRYDEN_SIGMA))
            L = float(cfg.get("L", DRYDEN_L))
            V = max(vel, float(cfg.get("v_min", DRYDEN_V_MIN)))
            alpha = float(np.exp(-dt * V / L))
            ruido = self.rng.normal(0.0, sigma * np.sqrt(max(1e-12, 1 - alpha**2)))
            self._vento_dinamico_estado[1] = alpha * self._vento_dinamico_estado[1] + ruido
            vel = float(np.clip(np.hypot(vel, self._vento_dinamico_estado[1]), 0.0, u_max))
            azim = azimute_graus(vetor_vento(1.0, azim)) + float(np.degrees(np.arctan2(self._vento_dinamico_estado[1], max(vel, 1e-6))))
        self.definir_vento(min(vel, u_max), azim, 0.0)

    # ------------------------------------------------------------------ guardas de sanidade
    def _verifica_sanidade(self, onde: str) -> None:
        """Levanta `RuntimeError` se o estado saiu do envelope físico (NaN/inf ou valores absurdos)."""
        valores = {"theta": self.theta, "omega": self.omega, "t": float(self.data.time)}
        for nome, v in valores.items():
            if not np.isfinite(v):
                self.nan_detetados += 1
                raise RuntimeError(f"[{onde}] estado não finito: {nome}={v} — NaN/inf na física "
                                   f"(passo {self.passos}, vento {self.vento_polar()}). Verifica o modelo/atuador.")
        if abs(self.theta) > SANIDADE_THETA_MAX or abs(self.omega) > SANIDADE_OMEGA_MAX:
            self.nan_detetados += 1
            raise RuntimeError(f"[{onde}] estado fora do envelope: θ={self.theta:.3e} rad, θ̇={self.omega:.3e} rad/s "
                               f"(limites {SANIDADE_THETA_MAX:.0e}/{SANIDADE_OMEGA_MAX:.0e}) — vento absurdo ou modelo instável")

    # ------------------------------------------------------------------ API Gymnasium
    def reset(self, *, seed: int | None = None, options: dict | None = None):
        """Episódio novo: estado inicial perto do alvo (jitter ±5°), velocidade nula, ação anterior zerada."""
        super().reset(seed=seed)
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        mujoco.mj_resetData(self.model, self.data)
        jitter = float(self.rng.uniform(-JITTER_ALVO, JITTER_ALVO)) if self.jitter else 0.0
        self.data.qpos[self.qadr] = self.theta_alvo + jitter
        self.data.qvel[self.dof] = 0.0
        self.data.qfrc_applied[:] = 0.0     # nenhuma força externa aplicada ainda (o vento entra no 1.º passo)
        mujoco.mj_forward(self.model, self.data)
        self.passos = 0
        self.retorno = 0.0
        self.episodios += 1
        self.acao_anterior = 0.0
        self._verifica_sanidade("reset")
        return self.observacao(), {"theta": self.theta, "theta_alvo": self.theta_alvo, "trim": self.trim}

    def step(self, acao):
        """Um passo de DECISÃO = `decimacao` passos de física (`mj_step`) com o comando e o vento em vigor."""
        if self.vento_dinamico:
            self.vento_dinamico_passo()
        ctrl = self.aplicar_acao(acao)
        tau_vento = self._aplica_vento()
        for _ in range(self.decimacao):
            mujoco.mj_step(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)   # campos derivados após o mj_step são do estado ANTERIOR
        self.passos += 1
        self._verifica_sanidade("step")

        erro, omega = self.erro, self.omega
        a = float(np.clip(np.asarray(acao, dtype=float).reshape(-1)[0], -1.0, 1.0))
        r = recompensa(erro, omega, a, self.acao_anterior)
        terminado = termina(erro)
        if terminado:
            r -= PENALIDADE_TERMINAL
        truncado = self.passos >= self.passos_max
        self.acao_anterior = a
        self.retorno += r
        vel_vento, azim_vento = self.vento_polar()
        info = {"theta": self.theta, "theta_alvo": self.theta_alvo, "erro": erro, "omega": omega, "ctrl": ctrl,
                "tau_vento": tau_vento, "vento_vel": vel_vento, "vento_azim": azim_vento, "trim": self.trim,
                "no_alvo": bonus_no_alvo(erro), "retorno": self.retorno}
        return self.observacao(), float(r), bool(terminado), bool(truncado), info


def novo_env(**kwargs) -> EnvPadrao:
    """Fábrica usada pelo `train.py`/`deploy.py`/`sim_view.py` (um só sítio para mudar a configuração)."""
    return EnvPadrao(**kwargs)


if __name__ == "__main__":   # smoke: `python env.py` mostra as constantes derivadas do MODELO
    e = novo_env()
    obs, info = e.reset(seed=0)
    print(f"env: massa={e.massa:.4f} kg · braço CM={e.braco_com:.4f} m · ponta={e.braco_ponta:.4f} m")
    print(f"     inércia no pivô M00={e.inercia:.6f} kg·m² · trim(θ*={np.degrees(e.theta_alvo):.1f}°)={e.trim:.4f} N·m")
    print(f"     envelope: termina com |erro| > {np.degrees(ERRO_TERMINA):.0f}° · bónus com |erro| < {np.degrees(BONUS_TOL):.1f}°")
    print(f"     obs={np.round(obs, 4)} (N_OBS={N_OBS}) · ação (N_ACT={N_ACT}) → ctrl ∈ "
          f"[{e.acao_para_ctrl([-1]):.3f}, {e.acao_para_ctrl([1]):.3f}] N·m")
    for a in ([0.0], [0.5], [-0.5]):
        obs, r, term, trunc, info = e.step(a)
        print(f"     a={a[0]:+.2f} → ctrl={info['ctrl']:+.3f} N·m θ={np.degrees(info['theta']):+7.2f}° erro={np.degrees(info['erro']):+6.2f}° r={r:+.5f}")
