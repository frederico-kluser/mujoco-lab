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
     Por cima do vento BASE há VENTO DINÂMICO (`definir_vento_dinamico`): `rajadas` (envelope senoidal que
     SOMA ao base), `frente` (degrau que o SUBSTITUI a partir de `t_s`) e `dryden` (turbulência OU de 1.ª
     ordem saturada em norma a `u_max`). Trocar de modo a meio do episódio NÃO reinicia nada — é o que o
     site usa nos controlos de vento ao vivo (`POST /api/vento-dinamico`). `u_max = 0` = modo inerte
     (ar parado, sem consumir o `rng`: os runs sem dinâmica ficam bit-idênticos).
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
VENTO_DINAMICO_CHAVES = frozenset({"modo", "u_max", "p", "duracao", "t_s", "sigma", "L", "v_min"})
VENTO_DINAMICO_U_MAX = 3.0        # m/s — teto do modo (amplitude da rajada/frente ou saturação da turbulência)
RAJADAS_P = 0.02                  # 1/passo de decisão
RAJADAS_DURACAO = 10              # passos
FRENTE_T_S = 2.0                  # s — instante da frente
FRENTE_U_MIN = 0.5                # m/s — piso da amostra da frente (U[0,5; u_max] quando o teto o permite)
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


def valida_vento_dinamico(config: dict | None) -> dict | None:
    """Valida e NORMALIZA a config do vento dinâmico (`None` = sem vento dinâmico).

    Devolve um dict NOVO só com as chaves do modo e os defaults preenchidos (o dict recebido nunca é
    tocado) — ou `None`. Levanta `ValueError` com mensagem clara para: config que não é dict, `modo` em
    falta/desconhecido, chave desconhecida (apanha gralhas como `durancao`, que passariam em silêncio),
    valores não finitos e faixas impossíveis. É usado pelo `__init__`, pelo `definir_vento_dinamico` (site
    e treino) e pelo `train.py`, que valida os `--vento-dinamico-params` ANTES de criar os envs.

    `u_max = 0` é válido e significa modo INERTE (ar parado, nada de dinâmica entra na física).
    """
    if config is None:
        return None
    if not isinstance(config, dict):
        raise ValueError(  # noqa: TRY004  (o contrato do laboratório pede ValueError também para o tipo)
            f"`vento_dinamico` tem de ser um dict (ou None) — ex.: {{'modo': 'rajadas', 'p': 0.02}} "
            f"(recebido {config!r})")
    if "modo" not in config:
        raise ValueError(f"`vento_dinamico` precisa da chave `modo`, uma de {VENTO_DINAMICO_MODOS} "
                         f"(recebido {config!r})")
    modo = config["modo"]
    if modo not in VENTO_DINAMICO_MODOS:
        raise ValueError(f"`vento_dinamico['modo']` tem de ser um de {VENTO_DINAMICO_MODOS} (recebido {modo!r})")
    desconhecidas = set(config) - VENTO_DINAMICO_CHAVES
    if desconhecidas:
        raise ValueError(f"`vento_dinamico` tem chaves desconhecidas {sorted(desconhecidas)} — aceita "
                         f"{sorted(VENTO_DINAMICO_CHAVES)} (gralhas como `durancao` são recusadas à entrada, "
                         "em vez de ignoradas em silêncio)")
    u_max = finito("vento_dinamico['u_max']", config.get("u_max", VENTO_DINAMICO_U_MAX))
    if u_max < 0.0:
        raise ValueError(f"`vento_dinamico['u_max']` tem de ser ≥ 0 m/s (recebido {u_max!r}): 0 = modo "
                         "inerte (ar parado, nenhuma dinâmica entra na física)")

    if modo == "rajadas":
        p = finito("vento_dinamico['p']", config.get("p", RAJADAS_P))
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"`vento_dinamico['p']` tem de estar em [0, 1] (recebido {p!r}): é a "
                             "probabilidade de começar uma rajada POR passo de decisão")
        duracao = config.get("duracao", RAJADAS_DURACAO)
        if isinstance(duracao, bool) or not isinstance(duracao, (int, np.integer)) or int(duracao) < 1:
            raise ValueError(f"`vento_dinamico['duracao']` tem de ser um inteiro ≥ 1 passos de decisão "
                             f"(recebido {duracao!r}): 0 não faria rajada nenhuma e um float não teria "
                             "envelope definido")
        return {"modo": modo, "u_max": u_max, "p": p, "duracao": int(duracao)}

    if modo == "frente":
        t_s = finito("vento_dinamico['t_s']", config.get("t_s", FRENTE_T_S))
        if t_s < 0.0:
            raise ValueError(f"`vento_dinamico['t_s']` tem de ser ≥ 0 s (recebido {t_s!r}): é o instante do "
                             "episódio em que a frente chega (0 = frente no 1.º passo de decisão)")
        return {"modo": modo, "u_max": u_max, "t_s": t_s}

    sigma = finito("vento_dinamico['sigma']", config.get("sigma", DRYDEN_SIGMA))
    if sigma <= 0.0:
        raise ValueError(f"`vento_dinamico['sigma']` tem de ser > 0 m/s (recebido {sigma!r}): é o "
                         "desvio-padrão estacionário da turbulência (σ = 0 seria um modo inerte)")
    comprimento = finito("vento_dinamico['L']", config.get("L", DRYDEN_L))
    if comprimento <= 0.0:
        raise ValueError(f"`vento_dinamico['L']` tem de ser > 0 m (recebido {comprimento!r}): é a escala de "
                         "comprimento do modelo de Dryden (α = exp(−Δt·V/L))")
    v_min = finito("vento_dinamico['v_min']", config.get("v_min", DRYDEN_V_MIN))
    if v_min <= 0.0:
        raise ValueError(f"`vento_dinamico['v_min']` tem de ser > 0 m/s (recebido {v_min!r}): com vento base "
                         "nulo a escala de tempo L/V seria infinita (α = 1) e a turbulência congelava em zero")
    return {"modo": modo, "u_max": u_max, "sigma": sigma, "L": comprimento, "v_min": v_min}


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
        self.vento_dinamico = valida_vento_dinamico(vento_dinamico)   # normalizado uma vez, aqui
        self.rng = np.random.default_rng(seed)
        self.passos = 0
        self.retorno = 0.0
        self.episodios = 0
        self.acao_anterior = 0.0
        self._base_vento = np.zeros(3)                          # vento BASE (o que o definir_vento escreveu)
        self.vento = np.zeros(3)                                # vento EM VIGOR = base + dinâmica (mundo)
        self.dt_decisao = float(self.model.opt.timestep) * self.decimacao   # Δt do passo de decisão (s)
        self._reinicia_dinamico()                               # estado da dinâmica (rajada/frente/turbulência)
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
    def definir_vento(self, vel: float, azimute: float, elevacao: float = 0.0) -> np.ndarray:
        """Vento BASE constante em POLAR (`vel` m/s, ângulos em GRAUS) — cortado ao teto, nunca NaN.

        É o vento que a UI/CLI manda (`POST /api/vento`; campos `vel`/`azimute`/`elevacao` do ficheiro de
        controlo) e a base sobre a qual a dinâmica atua: as `rajadas` SOMAM-se-lhe, a `frente`/`dryden`
        substituem-no enquanto o modo durar. Devolve o vector escrito (m/s, frame mundo).
        """
        v = min(max(finito("vel", vel), 0.0), VENTO_VEL_MAX)
        self._base_vento = vetor_vento(v, finito("azimute", azimute), finito("elevacao", elevacao))
        self.vento = np.array(self._base_vento, dtype=float)   # a dinâmica reescreve-o no passo seguinte
        return np.array(self.vento, dtype=float)

    @property
    def vento_vec(self) -> np.ndarray:
        """Cópia do vector de vento EM VIGOR (m/s, frame mundo) — o que a física leva agora (base + dinâmica)."""
        return np.array(self.vento, dtype=float)

    def vento_polar(self) -> tuple[float, float]:
        """(velocidade m/s, azimute graus) do vento em vigor — o que a telemetria publica."""
        return float(np.linalg.norm(self.vento)), azimute_graus(self.vento)

    @property
    def vento_modo(self) -> str:
        """Modo de vento dinâmico EM VIGOR (`"nenhum"` quando não há dinâmica ou o teto é 0)."""
        cfg = self.vento_dinamico
        return "nenhum" if cfg is None or float(cfg["u_max"]) == 0.0 else str(cfg["modo"])

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

    # ------------------------------------------------------------------ vento DINÂMICO (ao vivo)
    def _reinicia_dinamico(self) -> None:
        """Reinicia o estado da dinâmica no passo ACTUAL do episódio (não toca no vento base).

        O relógio da dinâmica arranca nos passos já decorridos, para o agendamento da frente continuar a usar
        o tempo do EPISÓDIO mesmo quando isto é chamado a meio (troca de modo a quente, `--vento-dinamico`).
        A frente é reamostrada aqui; a turbulência arranca em zero (cresce até σ na escala L/V — arranque
        calmo) e não há rajada em curso.
        """
        self._din_passo = int(self.passos)
        self._rajada_k = 0
        self._rajada_n = 0
        self._rajada_vec = np.zeros(3)
        self._turb = np.zeros(3)
        self._frente_passo = 1
        self._frente_vec = np.zeros(3)
        if self.vento_dinamico is not None and self.vento_dinamico["modo"] == "frente":
            self._frente_passo = self._passo_da_frente(self.vento_dinamico["t_s"])
            self._frente_vec = self._sorteia_frente()

    def _passo_da_frente(self, t_s: float) -> int:
        """Passo de decisão (1-based) em que a frente entra: o 1.º cujo intervalo `[t, t+Δt)` contém `t_s`.

        `k = floor(t_s/Δt + 1e-9) + 1` com Δt = `dt_decisao`: o vento é constante DENTRO do passo, logo o
        degrau entra no passo que contém `t_s` (se `t_s` cair numa fronteira, no passo que aí começa).
        """
        return int(np.floor(float(t_s) / self.dt_decisao + 1e-9)) + 1

    def _sorteia_frente(self) -> np.ndarray:
        """Amostra a frente: `u ~ U[min(0,5; u_max), u_max]`, azimute U[0, 360)°, elevação ±20°.

        O piso de 0,5 m/s (`FRENTE_U_MIN`) só se aplica quando o teto o permite; com `0 < u_max < 0,5` a
        frente vale `u_max`. Com `u_max = 0` o modo é INERTE: devolve o vector nulo e NÃO consome o `rng`.
        """
        u_max = float(self.vento_dinamico["u_max"])
        if u_max == 0.0:
            return np.zeros(3)
        u = float(self.rng.uniform(min(FRENTE_U_MIN, u_max), u_max))
        azimute = float(self.rng.uniform(0.0, 360.0))
        elevacao = float(np.degrees(self.rng.uniform(-VENTO_ELEV_MAX, VENTO_ELEV_MAX)))
        return vetor_vento(u, azimute, elevacao)

    def definir_vento_dinamico(self, config: dict | None) -> dict | None:
        """Liga/reconfigura/desliga o vento dinâmico em RUNTIME (mesma validação do `__init__`).

        Trocar de modo (ou ligar/desligar) re-planeia o RESTO do episódio: a frente é reamostrada e a
        rajada/turbulência recomeçam (o vento já escrito para este passo mantém-se até ao passo seguinte).
        Manter o mesmo modo só troca os parâmetros — é o que o treino faz quando o estágio do currículo sobe
        (`u_max` novo): a rajada em curso e a turbulência continuam, e uma frente ainda não chegada é
        reamostrada com o teto novo. Com `u_max = 0` o modo fica inerte (volta/fica o vento base, sem degrau
        nem turbulência e sem consumir o `rng`). Devolve a config NORMALIZADA (ou `None`).
        """
        novo = valida_vento_dinamico(config)
        antigo = self.vento_dinamico
        mudou_modo = ((novo is None) != (antigo is None)
                      or (novo is not None and antigo is not None and novo["modo"] != antigo["modo"]))
        self.vento_dinamico = novo
        if novo is None:
            if antigo is not None:
                self.vento = np.array(self._base_vento, dtype=float)   # volta ao vento base, sem dinâmica
            return None
        if mudou_modo:
            self._reinicia_dinamico()
            self._passo_vento()                    # o vento do próximo passo já é o dinâmico
        elif novo["modo"] == "frente" and self.passos + 1 < self._frente_passo:
            self._frente_vec = self._sorteia_frente()              # a frente ainda não chegou: teto novo
        return novo

    def _passo_vento(self) -> None:
        """Escreve em `self.vento` o vento do passo de decisão que agora começa (BASE + dinâmica).

        Chamado UMA vez por passo de decisão: no fim do `reset` (passo 1, logo o arranque já é contra o
        vento) e no início de cada `step` — a guarda em `step` evita repetir o passo já aplicado.

        `u_max = 0` é o único caso de INÉRCIA e é tratado AQUI, antes de qualquer modo: fica exactamente o
        vento base e NÃO se sorteia nada do `rng` (nem rajada, nem frente, nem ξ da turbulência) — é o que
        torna um run com dinâmica bit-idêntico a um run sem ela enquanto o teto for 0.
        """
        self._din_passo += 1
        cfg = self.vento_dinamico
        if cfg is None or float(cfg["u_max"]) == 0.0:
            self.vento = np.array(self._base_vento, dtype=float)
            return
        if cfg["modo"] == "rajadas":
            self._passo_rajada(cfg)
        elif cfg["modo"] == "frente":
            self.vento = np.array(self._frente_vec if self._din_passo >= self._frente_passo
                                  else self._base_vento, dtype=float)
        else:
            self._passo_dryden(cfg)

    def _passo_rajada(self, cfg: dict) -> None:
        """RAJADA: sorteia com prob. `p` e aplica o envelope `sin(π·k/(N+1))` SOBRE o vento base."""
        if self._rajada_k >= self._rajada_n:                    # nenhuma rajada activa → sorteia
            self._rajada_k = 0
            self._rajada_n = 0                                  # limpa a duração antiga (senão re-aplicava-a)
            if float(self.rng.random()) < cfg["p"]:
                u = float(self.rng.uniform(0.0, cfg["u_max"]))
                azimute = float(self.rng.uniform(0.0, 360.0))
                elevacao = float(np.degrees(self.rng.uniform(-VENTO_ELEV_MAX, VENTO_ELEV_MAX)))
                self._rajada_vec = vetor_vento(u, azimute, elevacao)
                self._rajada_n = int(cfg["duracao"])
        if self._rajada_k < self._rajada_n:                     # rajada activa: envelope 0→u→0
            self._rajada_k += 1
            env = float(np.sin(np.pi * self._rajada_k / (self._rajada_n + 1.0)))
            self.vento = np.asarray(self._base_vento + self._rajada_vec * env, dtype=float)
        else:                                                   # entre rajadas: fica o vento base
            self.vento = np.array(self._base_vento, dtype=float)

    def _passo_dryden(self, cfg: dict) -> None:
        """Turbulência OU por passo: `x ← α·x + σ·√(1−α²)·ξ`, `α = exp(−Δt·V/L)`, `V = max(‖base‖, v_min)`.

        O vento aplicado é `base + x`, saturado em NORMA a `u_max` quando há teto (o estado `x` do OU não é
        saturado, para o processo continuar a ser exactamente o da fórmula). Com `u_max = 0` este método NÃO
        é chamado (o `_passo_vento` trata a inércia antes de escolher o modo).
        """
        v_ref = max(float(np.linalg.norm(self._base_vento)), float(cfg["v_min"]))
        alpha = float(np.exp(-self.dt_decisao * v_ref / float(cfg["L"])))
        xi = self.rng.normal(0.0, 1.0, 3)
        self._turb = alpha * self._turb + float(cfg["sigma"]) * float(np.sqrt(1.0 - alpha * alpha)) * xi
        total = np.asarray(self._base_vento + self._turb, dtype=float)
        norma = float(np.linalg.norm(total))
        u_max = float(cfg["u_max"])
        if u_max > 0.0 and norma > u_max:
            total = total * (u_max / norma)
        self.vento = total

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
        self.vento = np.array(self._base_vento, dtype=float)   # o vento BASE mantém-se entre episódios
        self._reinicia_dinamico()               # rajada/turbulência a zero, frente reamostrada para o ep.
        self._passo_vento()                     # 1.º passo de decisão já leva o vento (base + dinâmica)
        self._verifica_sanidade("reset")
        return self.observacao(), {"theta": self.theta, "theta_alvo": self.theta_alvo, "trim": self.trim,
                                   "vento_modo": self.vento_modo}

    def step(self, acao):
        """Um passo de DECISÃO = `decimacao` passos de física (`mj_step`) com o comando e o vento em vigor."""
        self._passo_vento()                     # vento do passo que agora começa (base + dinâmica)
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
                "vento_modo": self.vento_modo, "no_alvo": bonus_no_alvo(erro), "retorno": self.retorno}
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
