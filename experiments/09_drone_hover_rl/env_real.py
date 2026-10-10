"""experiments/09_drone_hover_rl/env_real.py — ambiente Gymnasium do drone REAL do dono (plano-drone-real.md).

O mesmo objetivo do v09 ("trava-se em (0, 0, alvo_z) e aguenta o vento"), agora com o HARDWARE que o dono
vai construir — peças reais do catálogo `models/drone_rpi/` (build ativo por omissão; `build="..."` para
outro) — e SÓ com informação que existe no drone real:

PLANTA (`lab/drone_rpi`, tudo pelo `mj_step` a 500 Hz): 4 motores BLDC com modelo elétrico (corrente,
travagem, ω_max(V)), ESC DShot, bateria com queda de tensão/SoC/temperatura/desgaste, efeito de solo,
inflow, VRS, arrasto de rotor, giroscópico, sensores com erro (IMU, ToF, fluxo ótico, monitor de bateria).

AÇÃO `Box(-1, 1, (4,))` (sempre com o atraso de comando do RPi, 8 ms nominais, FIFO por passo de física):
  · `modo_acao="ctbr"` (padrão; arquitetura FC dedicado, plano §7 C1): a₀ → acelerador coletivo LINEAR EM
    EMPUXO à volta da pairagem nominal (u = u_pairagem·√(1 + a₀): −1 → 0, 0 → pairagem, +1 → 2× o peso) e
    a₁..₃ → taxas do corpo (p, q, r) até ±[2; 2; 1] rad/s; o FC simulado (`fc.py`) fecha a malha de taxa a
    500 Hz e mistura;
  · `modo_acao="motores"` (RPi 5 sozinho, PREEMPT_RT): cada aᵢ → acelerador do motor i (mesma
    centragem), sem FC.

OBSERVAÇÃO `Box(-inf, inf, (42,))` = [ATOR (21) | CRÍTICO privilegiado (21)]:
  · ATOR [0:21] — SÓ sensores + estimação de bordo (`estimador.py`) + ação anterior:
      [0:3] giro medido/2 rad/s · [3:6] acelerómetro medido/9,81 · [6:8] roll̂, pitcĥ (rad) ·
      [8] Δψ̂/π (rumo desde o armar) · [9] ĥ − alvo_z (m, ToF+acc) · [10] v̂_z (m/s) ·
      [11:13] v̂_x, v̂_y no corpo (m/s, fluxo) · [13:15] odometria x̂, ŷ (m) · [15] ToF válido ·
      [16] fluxo válido · [17:21] ação anterior;
  · CRÍTICO [21:42] — informação privilegiada, SÓ para o crítico (asymmetric actor-critic, plano §7 D1):
      p − p_alvo (3) · v mundo (3) · (roll, pitch, yaw_err)/π (3) · ω corpo/2 (3) · ω_rotor/ω_max (4) ·
      SoC · V_bus/V_nominal · vento/5 (3).
  A política exportada (deploy) só recebe `obs[:OBS_ATOR_DIM]`.

RECOMPENSA v3-real (por passo de decisão; xyz privilegiado é PERMITIDO na recompensa — §1 do plano):

    r = 1 − 0,35·tanh(‖xy‖/1 m) − 0,35·tanh(|z − alvo|/0,5 m) − 0,10·tanh(|yaw_err|/0,5 rad)
          − 0,10·tanh(‖v‖/1 m/s) − 0,05·tanh(‖ω‖/2 rad/s) − 0,05·min(‖Δa‖, 1)
          + 0,5·𝟙[bónus v2b: ‖xy‖ < 0,05 ∧ |z − alvo| < 0,05 ∧ |yaw_err| < 0,10] − 50·𝟙[terminated]

com `yaw_err = ψ − ψ₀` (rumo relativo ao do arranque: sem magnetómetro o yaw absoluto não é observável — §7 A).
PORQUÊ não a v2b do cf2: as penalidades da v2b são ILIMITADAS por passo (−1·‖xy‖…) e o fim custa −100; com
sensores reais o drone pode derivar metros e cada passo passava a custar −5 — terminar cedo ficava MELHOR do
que voar (medido no 1.º treino: z médio a cair para 0,56 m aos 0,8 M passos). Na v3-real cada passo vivo vale
r ∈ [0, 1,5] (os pesos somam 1): cair nunca compensa. Pairagem perfeita ≈ 1,5 × 500 = 750 por episódio.
TERMINAÇÃO: CM abaixo de metade da altura de repouso (impacto), |roll| ou |pitch| > 90°, z > 3 m ou
brownout da bateria. TRUNCAGEM: `episodio_s`.

RESET: drone pousado pela física (motores parados), FC/ESC armados no fim (os motores arrancam no 1.º
passo), estimador calibrado com as leituras em repouso. `options={"manter_bateria": True}` mantém o pack
(SoC/temperatura/ciclo) — é o REINICIAR do site (pousar e voltar a descolar não carrega a bateria);
`options={"soc0": x}` fixa o SoC inicial. Com `aleatorizar=True` (treino) cada episódio sorteia
massa/inércia/CM, kf/kq/J/R/KV/I₀ por motor, bateria (SoC₀, SoH, R, temperatura), atraso de comando,
ruído dos sensores e arrasto de rotor/solo/VRS (plano §6 P1.5).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]
from lab import mjkit  # noqa: F401, I001  (MUJOCO_GL=egl antes de `import mujoco`)
from lab import drone_rpi as dr

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces

from env import (
    TILT_MAX,
    Z_TETO,
    HoverEnv,
    atitude,
    azimute_graus,
    bonus_no_alvo,
    envolve_pi,
    finito,
    quat_yaw,
    valida_vento_dinamico,
)
from estimador import EstimadorBordo
from fc import ControladorFC

OBS_ATOR_DIM = 21
OBS_CRITICO_DIM = 21
OBS_DIM = OBS_ATOR_DIM + OBS_CRITICO_DIM
TAXA_MAX = np.array([2.0, 2.0, 1.0])      # rad/s — setpoints de taxa máximos (p, q, r): pairar não pede mais
ESCALA_GIRO = 2.0
MODOS_ACAO = ("ctbr", "motores")
JITTER_XY = 0.02
JITTER_YAW = math.radians(5.0)
ASSENTAR_MAX_S = 1.5
ASSENTAR_V = 1e-3
ASSENTAR_QUIETOS = 10

# domain randomization (faixas por episódio; plano §6 P1.5 + SimpleFlight arXiv 2412.11764)
DR = {
    "massa": (0.95, 1.05), "inercia": (0.90, 1.10), "cm_xy": 0.004,
    "kf": (0.92, 1.08), "kf_motor": (0.98, 1.02), "kq": (0.90, 1.10), "j": (0.80, 1.25),
    "r": (0.90, 1.15), "kv": (0.97, 1.03), "i0": (0.8, 1.2), "eta": (0.97, 1.0),
    "soc0": (0.30, 1.0), "soh": (0.80, 1.0), "r_bat": (0.8, 1.3), "t_amb": (5.0, 35.0),
    "atraso": (0.0, 0.012), "ruido": (0.5, 2.0), "d_xy": (0.20, 0.45), "solo": (0.7, 1.3), "vrs": (0.5, 1.5),
}


# recompensa v3-real (docstring do módulo): pesos que somam 1 ⇒ estar vivo vale sempre r ≥ 0
R_VIVO = 1.0
PESOS_REAL = {"xy": 0.35, "z": 0.35, "yaw": 0.10, "v": 0.10, "omega": 0.05, "delta_a": 0.05}
ESCALAS_REAL = {"xy": 1.0, "z": 0.5, "yaw": 0.5, "v": 1.0, "omega": 2.0}
BONUS_REAL = 0.5
PENALIDADE_REAL = 50.0


def recompensa_real(dist_xy: float, dz: float, yaw_err: float, v: float, omega, delta_a,
                    terminado: bool) -> float:
    """Recompensa v3-real (fórmula no docstring do módulo) — pura, sem estado."""
    w, e = PESOS_REAL, ESCALAS_REAL
    r = (R_VIVO - w["xy"] * math.tanh(dist_xy / e["xy"]) - w["z"] * math.tanh(dz / e["z"])
         - w["yaw"] * math.tanh(abs(yaw_err) / e["yaw"]) - w["v"] * math.tanh(abs(v) / e["v"])
         - w["omega"] * math.tanh(float(np.linalg.norm(omega)) / e["omega"])
         - w["delta_a"] * min(float(np.linalg.norm(delta_a)), 1.0))
    if bonus_no_alvo(dist_xy, dz, yaw_err):
        r += BONUS_REAL
    if terminado:
        r -= PENALIDADE_REAL
    return float(r)


def build_do_hardware(dados: dict | None) -> tuple[str | dict | None, str]:
    """O build com que uma política treinou, a partir do seu `hardware.json`: o NOME (se ainda existir em
    `builds.json`) → a configuração GRAVADA no `hardware.json` (se as peças ainda existirem no catálogo) → o build
    ATIVO (com aviso: a política foi treinada para outras peças). Devolve `(build, motivo)`."""
    if not dados:
        return None, "build ativo (sem hardware.json)"
    nome = dados.get("build")
    if nome in dr.carregar_builds()["builds"]:
        return nome, f"build '{nome}' do catálogo"
    cfg = dados.get("config_build")
    if isinstance(cfg, dict):
        try:
            dr.hardware({**cfg, "nome": nome})
            return {**cfg, "nome": nome}, f"build '{nome}' reconstruído do hardware.json (já não está no builds.json)"
        except (KeyError, ValueError) as erro:
            return None, (f"AVISO: build '{nome}' irreconstruível ({erro}) — a usar o build ATIVO; a política foi "
                          "treinada para outras peças")
    return None, f"AVISO: build '{nome}' desconhecido — a usar o build ATIVO"


class DroneRealEnv(HoverEnv):
    """O drone real do dono — ver o docstring do módulo (herda o vento base/dinâmico do `HoverEnv`)."""

    metadata = {"render_modes": []}  # noqa: RUF012

    def __init__(self, build: str | dict | None = None, alvo_z: float = 1.0, decimation: int = 10,
                 episodio_s: float = 10.0, modo_acao: str = "ctbr", aleatorizar: bool = False,
                 flags_aero: dr.FlagsAero | None = None,
                 vento: tuple[float, float, float] | None = None,
                 vento_aleatorio: tuple[float, float] | None = None,
                 vento_dinamico: dict | None = None,
                 soc0: float = 1.0, desgaste: dr.EstadoDesgaste | None = None,
                 render_mode: str | None = None):
        gym.Env.__init__(self)
        if isinstance(decimation, bool) or not isinstance(decimation, (int, np.integer)) or int(decimation) < 1:
            raise ValueError(f"decimation tem de ser um inteiro ≥ 1 (recebido {decimation!r})")
        if float(episodio_s) <= 0.0:
            raise ValueError(f"episodio_s tem de ser > 0 s (recebido {episodio_s!r})")
        if modo_acao not in MODOS_ACAO:
            raise ValueError(f"modo_acao tem de ser um de {MODOS_ACAO} (recebido {modo_acao!r})")
        if vento is not None and vento_aleatorio is not None:
            raise ValueError("`vento` (constante) e `vento_aleatorio` (currículo) são exclusivos: escolha um")
        self.hw = build if isinstance(build, dr.Hardware) else dr.hardware(build)
        self.modo_acao = modo_acao
        self.aleatorizar = bool(aleatorizar)
        self.decimation = int(decimation)
        self.episodio_s = float(episodio_s)
        self.render_mode = render_mode
        self.ruido_obs = 0.0
        self.tau_escala = 1.0
        self.helices = False
        self.soc0 = float(soc0)

        self.model, self.data = dr.carregar(self.hw)
        self.corpo = self.model.body("drone").id
        self.dt = float(self.model.opt.timestep)
        self.dt_decisao = self.dt * self.decimation
        self.max_passos = max(1, round(self.episodio_s / self.dt_decisao))
        self.massa = float(self.model.body_mass.sum())
        self.gravidade = abs(float(self.model.opt.gravity[2]))
        self.mg = self.massa * self.gravidade
        self._massa_nom = self.model.body_mass.copy()
        self._inercia_nom = self.model.body_inertia.copy()
        self._ipos_nom = self.model.body_ipos.copy()

        self.planta = dr.Planta(self.hw, self.model, self.data, flags_aero=flags_aero, desgaste=desgaste)
        self.fc = ControladorFC(self.hw, self.model, self.dt)
        self.estimador = EstimadorBordo(self.dt)
        _ph = self.hw.ponto_pairagem(self.hw.bateria.v_nominal)
        self.u_pairagem = float(_ph["acelerador"])
        self._omega_pairagem = float(_ph["omega"])
        self.omega_ref = self.hw.omega_max(self.hw.bateria.v_cheia)
        self.atraso_comando = self.hw.atraso_comando

        # altura de repouso (define o "caiu" e o alvo mínimo honesto)
        self.z_repouso = self._medir_repouso()
        self.z_termina = 0.5 * self.z_repouso
        alvo_min = self.z_repouso + 0.15
        alvo_z = finito("alvo_z", alvo_z)
        if not alvo_min <= alvo_z <= Z_TETO - 0.1:
            raise ValueError(f"alvo_z tem de estar em [{alvo_min:.2f}, {Z_TETO - 0.1:.2f}] m (recebido {alvo_z!r}): "
                             f"o CM em repouso fica a {self.z_repouso:.3f} m e o bónus pede |z − alvo| < 0,05 m")
        self.alvo_z = alvo_z
        self.alvo = np.array([0.0, 0.0, alvo_z])

        # vento (mesmo maquinário e contrato do HoverEnv)
        self.vento_dinamico = valida_vento_dinamico(vento_dinamico)
        self.vento = None
        self.vento_aleatorio = None
        self._base_vento = np.zeros(3)
        self._din_passo = 0
        self._rajada_k = self._rajada_n = 0
        self._rajada_vec = np.zeros(3)
        self._turb = np.zeros(3)
        self._frente_passo = 1
        self._frente_vec = np.zeros(3)
        self.passos = 0
        if (self.vento_dinamico is not None and self.vento_dinamico["modo"] == "frente"
                and self._passo_da_frente(self.vento_dinamico["t_s"]) > self.max_passos):
            raise ValueError("`vento_dinamico['t_s']` cai fora do episódio (a frente nunca chegaria)")
        if vento is not None:
            self.definir_vento(*self._vento_em_polar(vento))
        elif vento_aleatorio is not None:
            self.definir_vento_aleatorio(*vento_aleatorio)
        else:
            self.model.opt.wind[:] = 0.0
        if self.vento_dinamico is not None:
            self._reinicia_dinamico()

        self.acao_anterior = np.zeros(4, dtype=np.float32)
        self._cmd_ativo = np.zeros(4)
        self._cmd_pendente = np.zeros(4)
        self._contagem_atraso = 0
        self.yaw0 = 0.0
        self.parametros_dr: dict = {}
        self.action_space = spaces.Box(-1.0, 1.0, (4,), dtype=np.float32)
        self.observation_space = spaces.Box(-np.inf, np.inf, (OBS_DIM,), dtype=np.float32)

    # ------------------------------------------------------------------ arranque físico
    def _medir_repouso(self) -> float:
        """Larga o drone a 0,3 m (motores desligados) e mede a altura do CM em repouso."""
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[2] = 0.3
        mujoco.mj_forward(self.model, self.data)
        self.planta.reiniciar(1.0, armado=False)
        self._assentar(max_s=2.0)
        return float(self.data.qpos[2])

    def _assentar(self, max_s: float = ASSENTAR_MAX_S) -> None:
        """Passos de física com os motores desligados até o drone estar quieto no chão."""
        quietos = 0
        for _ in range(int(max_s / self.dt)):
            self.planta.passo()
            if np.linalg.norm(self.data.qvel) < ASSENTAR_V and self.data.ncon > 0:
                quietos += 1
                if quietos >= ASSENTAR_QUIETOS:
                    return
            else:
                quietos = 0

    # ------------------------------------------------------------------ domain randomization
    def _sortear_dr(self) -> dict:
        u = self.np_random.uniform
        p = {k: float(u(*DR[k])) for k in ("massa", "inercia", "kf", "kq", "j", "r", "kv", "i0", "eta",
                                            "soc0", "soh", "r_bat", "t_amb", "atraso", "ruido", "solo", "vrs")}
        p["kf_motor"] = u(*DR["kf_motor"], 4)
        p["cm"] = u(-DR["cm_xy"], DR["cm_xy"], 2)
        p["d_x"], p["d_y"] = (float(x) for x in u(*DR["d_xy"], 2))
        return p

    def _aplicar_parametros(self, p: dict | None) -> None:
        """Aplica (ou repõe, com `p=None`) os parâmetros físicos do episódio."""
        m, pl = self.model, self.planta
        if p is None:
            m.body_mass[:] = self._massa_nom
            m.body_inertia[:] = self._inercia_nom
            m.body_ipos[:] = self._ipos_nom
            pl.prop.aplicar_escalas()
            pl.bat.escala_r = 1.0
            pl.aero.definir_arrasto(dr.aero.D_ARRASTO, dr.aero.D_ARRASTO)
            pl.aero.escala_solo = 1.0
            pl.aero.k_vrs = dr.aero.K_VRS
            for s in self._sensores():
                s.escala_ruido = 1.0
            self.atraso_comando = self.hw.atraso_comando
        else:
            c = self.corpo
            m.body_mass[c] = self._massa_nom[c] * p["massa"]
            m.body_inertia[c] = self._inercia_nom[c] * p["massa"] * p["inercia"]
            m.body_ipos[c] = self._ipos_nom[c] + np.array([p["cm"][0], p["cm"][1], 0.0])
            pl.prop.aplicar_escalas(kf=p["kf"] * p["kf_motor"], kq=p["kq"], j=p["j"], r=p["r"], kv=p["kv"],
                                    i0=p["i0"], eta=p["eta"])
            pl.bat.escala_r = p["r_bat"]
            pl.aero.definir_arrasto(p["d_x"], p["d_y"])
            pl.aero.escala_solo = p["solo"]
            pl.aero.k_vrs = dr.aero.K_VRS * p["vrs"]
            for s in self._sensores():
                s.escala_ruido = p["ruido"]
            self.atraso_comando = p["atraso"]
        mujoco.mj_setConst(m, self.data)

    def _sensores(self):
        pl = self.planta
        out = [pl.imu.giro, pl.imu.acc]
        for s in (pl.tof, pl.fluxo, pl.baro):
            if s is not None:
                out.append(s.s)
        return out

    # ------------------------------------------------------------------ API Gymnasium
    def reset(self, *, seed: int | None = None, options: dict | None = None):
        gym.Env.reset(self, seed=seed)
        opts = options or {}
        self.planta.rng = self.np_random
        manter = bool(opts.get("manter_bateria", False))
        if self.aleatorizar and not manter:
            self.parametros_dr = self._sortear_dr()
            self._aplicar_parametros(self.parametros_dr)
            soc0 = self.parametros_dr["soc0"]
            self.planta.bat.desgaste = dr.EstadoDesgaste(pack_id=self.hw.bateria.id, soh=self.parametros_dr["soh"])
            self.planta.bat.t_amb = self.parametros_dr["t_amb"]
        else:
            if not manter:
                self.parametros_dr = {}
                self._aplicar_parametros(None)
            soc0 = float(opts.get("soc0", self.soc0))
        estado_bat = self._guardar_bateria() if manter else None

        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[0] = float(self.np_random.uniform(-JITTER_XY, JITTER_XY))
        self.data.qpos[1] = float(self.np_random.uniform(-JITTER_XY, JITTER_XY))
        self.data.qpos[2] = self.z_repouso + 0.003
        self.data.qpos[3:7] = quat_yaw(float(self.np_random.uniform(-JITTER_YAW, JITTER_YAW)))
        self.model.opt.wind[:] = 0.0
        mujoco.mj_forward(self.model, self.data)
        self.planta.reiniciar(soc0, armado=False)
        self._assentar()
        if estado_bat is not None:
            self._repor_bateria(estado_bat)
        self.data.time = 0.0
        mujoco.mj_forward(self.model, self.data)
        self.planta.reiniciar_sensores()
        self.planta.armar(True)
        self.fc.reiniciar()
        self.fc.armar(True)
        tof = self.planta.tof
        self.estimador.reiniciar(self.planta.imu.acc.ler(), tof.distancia, tof.valido)
        self.yaw0 = float(atitude(self.data.qpos[3:7])[2])

        if self.vento_aleatorio is not None:
            self._amostra_vento()
        elif self.vento is not None:
            self.model.opt.wind[:] = self.vento
            self._base_vento = np.array(self.vento, dtype=float)
        else:
            self.model.opt.wind[:] = 0.0
            self._base_vento[:] = 0.0
        self.passos = 0
        self.acao_anterior = np.zeros(4, dtype=np.float32)
        self._cmd_ativo = np.zeros(4)
        self._cmd_pendente = np.zeros(4)
        self._contagem_atraso = 0
        if self.vento_dinamico is not None:
            self._reinicia_dinamico()
            self._passo_vento()
        return self.observacao(), self._info()

    def _guardar_bateria(self) -> dict:
        b = self.planta.bat
        return {k: getattr(b, k) for k in ("soc", "v_rc", "temp", "soc_inicio", "ah_ciclo", "wh_ciclo",
                                           "t_ciclo", "soma_c_dt", "soma_t_dt", "i_pico", "v_min")}

    def _repor_bateria(self, estado: dict) -> None:
        b = self.planta.bat
        for k, v in estado.items():
            setattr(b, k, v)
        b.v = b.ocv() - b.v_rc
        self.planta.v_bus = b.v

    # ------------------------------------------------------------------ ação
    def _comando(self, a: np.ndarray) -> np.ndarray:
        """Ação [-1,1]⁴ → comando físico: ctbr = [coletivo, p, q, r]; motores = 4 aceleradores.

        O acelerador é LINEAR EM EMPUXO à volta da pairagem: u = u_pair(V)·√(1 + a) ⇒ T/T_pairagem ≈ 1 + a
        (T ∝ ω² ∝ u²), ou seja a = −1 → 0, a = 0 → pairagem, a = +1 → 2× o peso — a MESMA escala de ação para
        qualquer conjunto de peças. COMPENSAÇÃO DE TENSÃO (como o `vbat_sag_compensation` do Betaflight): o
        u_pair é o acelerador de pairagem à tensão MEDIDA da bateria (monitor INA226, dado real de bordo) —
        a política NÃO vê a bateria, mas o seu "0" continua a ser "pairar" de 100 % a 10 % de SoC. Cortado a [0, 1].
        """
        uh = self.acelerador_pairagem()

        def acelerador(x):
            return np.minimum(uh * np.sqrt(np.maximum(1.0 + x, 0.0)), 1.0)

        if self.modo_acao == "ctbr":
            return np.concatenate(([float(acelerador(a[0]))], a[1:] * TAXA_MAX))
        return acelerador(a)

    def acelerador_pairagem(self) -> float:
        """Acelerador de pairagem NOMINAL (massa do catálogo) à tensão medida da bateria (ver `_comando`)."""
        v = self.planta.monitor.tensao
        if not v > 0.5 * self.hw.bateria.v_nominal:
            return self.u_pairagem
        d = self.hw.duty_para_omega(self._omega_pairagem, v)
        return float(min(self.hw.duty_para_acelerador(min(d, self.hw.duty_max)), 1.0))

    def acao_para_ctrl(self, acao):
        """Compatibilidade com as peças do v09: devolve (coletivo/aceleradores, taxas ou None)."""
        c = self._comando(self._acao_valida(acao))
        if self.modo_acao == "ctbr":
            return float(c[0]), c[1:]
        return c, None

    def aplicar_acao(self, acao):
        return self.acao_para_ctrl(acao)

    def step(self, acao):
        a = self._acao_valida(acao)
        delta_a = a - self.acao_anterior.astype(float)
        self._cmd_pendente = self._comando(a)
        self._contagem_atraso = round(self.atraso_comando / self.dt)
        if self.vento_dinamico is not None and self._din_passo < self.passos + 1:
            self._passo_vento()
        pl, est, fc = self.planta, self.estimador, self.fc
        for _ in range(self.decimation):
            if self._contagem_atraso <= 0:
                self._cmd_ativo = self._cmd_pendente
            else:
                self._contagem_atraso -= 1
            c = self._cmd_ativo
            if self.modo_acao == "ctbr":
                u = fc.passo(c[0], c[1:], pl.imu.giro.medicao)
            else:
                u = c if pl.prop.armado else np.zeros(4)
            pl.passo(u)
            tof, fl = pl.tof, pl.fluxo
            est.passo(pl.imu.giro.medicao, pl.imu.acc.medicao, tof.distancia, tof.valido, tof.s.n_amostras,
                      fl.fluxo, fl.valido, fl.s.n_amostras)
        self.passos += 1
        self.acao_anterior = a.astype(np.float32)

        d = self._derivados()
        if not np.isfinite([d["x"], d["y"], d["z"], d["v"]]).all() or abs(d["z"]) > 1e3:
            raise RuntimeError("simulação DIVERGIU (estado fora da sanidade) — chame reset()")
        terminado = bool(d["z"] < self.z_termina or d["z"] > Z_TETO
                         or max(abs(d["phi"]), abs(d["theta"])) > TILT_MAX or pl.brownout)
        r = recompensa_real(d["dist_xy"], d["dz"], d["yaw_err"], d["v"], d["omega"], delta_a, terminado)
        truncado = bool(self.passos >= self.max_passos)
        return self.observacao(d), float(r), terminado, truncado, self._info(d)

    # ------------------------------------------------------------------ estado → observação
    def _derivados(self) -> dict:
        """Estado PRIVILEGIADO exato (qpos/qvel — sem desfasamento de 1 passo): só recompensa/crítico/info."""
        q = self.data.qpos
        rmat = np.zeros(9)
        mujoco.mju_quat2Mat(rmat, q[3:7])
        rmat = rmat.reshape(3, 3)
        cm = q[0:3] + rmat @ (self.model.body_ipos[self.corpo] - self._ipos_nom[self.corpo])
        phi, theta, yaw = (float(v) for v in atitude(q[3:7]))
        x, y, z = (float(v) for v in cm)
        v = np.array(self.data.qvel[0:3])
        return {"x": x, "y": y, "z": z, "phi": phi, "theta": theta, "yaw": yaw,
                "yaw_err": envolve_pi(yaw - self.yaw0), "dist_xy": float(math.hypot(x, y)),
                "dz": abs(z - self.alvo_z), "v": float(np.linalg.norm(v)), "v_vec": v,
                "omega": np.array(self.data.qvel[3:6], dtype=float)}

    def observacao(self, d: dict | None = None) -> np.ndarray:
        pl, est = self.planta, self.estimador
        d = self._derivados() if d is None else d
        ator = np.concatenate((
            pl.imu.giro.medicao / ESCALA_GIRO, pl.imu.acc.medicao / self.gravidade,
            [est.roll, est.pitch, est.psi / math.pi, est.h - self.alvo_z, est.vz, est.vx, est.vy, est.x, est.y,
             1.0 if pl.tof.valido else 0.0, 1.0 if pl.fluxo.valido else 0.0],
            self.acao_anterior))
        critico = np.concatenate((
            [d["x"] - self.alvo[0], d["y"] - self.alvo[1], d["z"] - self.alvo[2]], d["v_vec"],
            [d["phi"] / math.pi, d["theta"] / math.pi, d["yaw_err"] / math.pi], d["omega"] / ESCALA_GIRO,
            pl.prop.omega / self.omega_ref, [pl.bat.soc, pl.v_bus / self.hw.bateria.v_nominal],
            np.asarray(self.model.opt.wind) / 5.0))
        return np.concatenate((ator, critico)).astype(np.float32)

    def _info(self, d: dict | None = None) -> dict:
        d = self._derivados() if d is None else d
        vento = self.vento_atual
        norma = float(np.linalg.norm(vento))
        b = self.planta.bat
        return {"z": d["z"], "dist_xy": d["dist_xy"], "v": d["v"],
                "no_alvo": bonus_no_alvo(d["dist_xy"], d["dz"], d["yaw_err"]), "yaw_err": d["yaw_err"],
                "vento_vel": norma, "vento_atual": norma, "vento_azim": azimute_graus(vento),
                "soc": b.soc, "v_bat": self.planta.v_bus, "i_bat": self.planta.i_total, "p_total": b.p,
                "soh": b.desgaste.soh, "brownout": self.planta.brownout}

    def close(self) -> None:
        return


__all__ = ["DR", "MODOS_ACAO", "OBS_ATOR_DIM", "OBS_CRITICO_DIM", "OBS_DIM", "TAXA_MAX", "DroneRealEnv",
           "build_do_hardware", "recompensa_real"]
