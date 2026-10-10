"""lab.drone_rpi — o drone que o dono vai CONSTRUIR: quad 5″ que transporta um Raspberry Pi 5, com
sensor de giroscópio e 4 motores brushless (bateria desconsiderada por enquanto).

Esta camada modela o HARDWARE real — não há código de estabilização/controle/voo aqui (isso é do dono):

  · `carregar()`  → (model, data) a partir de `models/drone_rpi/drone_rpi.xml` (4 canais de empuxo
    POR ROTOR, sensores `giro`/`acc`/`quat`/`pos`, física 500 Hz);
  · `Motores`     → a dinâmica REAL dos 4 motores brushless + ESC: velocidade de rotor ω com
    atraso de 1.ª ordem ASSIMÉTRICO (subida τ_sub ≈ 11 ms, descida τ_desc ≈ 27 ms — a hélice só
    abranda por arrasto de pás), lei quadrática T = kf·ω², saturação por rotor [0, ω_max],
    quantização de comando DShot (11 bits) e atraso de comando (jitter do RPi 5). As FORÇAS entram
    sempre pelo `mj_step` (atores `motor` do modelo, 1 por rotor);
  · `Giroscopio`  → o modelo de erro do sensor real (pré-definições `mpu6050`/`bmi088`): bias
    residual pós-calibração + deriva (random walk) + ruído branco + amostragem/hold + atraso;
  · `Accel`       → o mesmo para o acelerómetro (só existe se o hardware do dono o tiver);
  · `ler_*`       → leituras; `MODOS` → roteiros abertos sem realimentação (só demonstração).

PREMISSA DE REALISMO (regra do dono, 2026-10-09): a política só pode ver o que o hardware mede
(giroscópio, e acelerómetro se existir). Posição/velocidade/atitude exatas são info privilegiada —
podem entrar na RECOMPENSA, nunca na observação nem na execução.

Parâmetros (troque quando escolher o hardware; fontes em `models/drone_rpi/README.md`):
  · propulsão: motor 2306 + hélice 5×4.3 a 4S → T_max ≈ 11,77 N/rotor a ω_max ≈ 27 000 RPM;
  · kf = T_max/ω_max² = 1,47e-6 N/(rad/s)² · kq = kf·0,016 m (razão momento/empuxo das pás);
  · motores: τ_sub 11 ms / τ_desc 27 ms (Faessler RAL17); alternativa Crazyflie: Tm ≈ 72 ms (SysID);
  · RPi 5: política a 50 Hz; atraso de comando 8 ms (pior caso medido do kernel normal; 28 µs com
    PREEMPT_RT — ponha `atraso_comando=0` para o caso RT).
"""
from __future__ import annotations

import mujoco
import numpy as np

# --------------------------------------------------------------------------------------- propulsão
MASSA = 0.328                 # kg — sem bateria (ver README.md do modelo; 0,503 kg com 4S 1500 mAh)
GRAVIDADE = 9.81              # m/s² (a do MuJoCo)
T_ROTOR_MAX = 11.77           # N por rotor (2306 + 5×4.3 a 4S ≈ 1,2 kgf — T-Motor/UAVMODEL)
OMEGA_MAX = 2827.0            # rad/s (27 000 RPM carregado a 4S)
KF = T_ROTOR_MAX / OMEGA_MAX ** 2      # N/(rad/s)² — T = kf·ω²  (≈1,4734e-6)
KM_RATIO = 0.016              # m — kq/kf: momento de reação/empuxo das pás (X2 usa 0,0201)
T_ROTORES = ("rotor1", "rotor2", "rotor3", "rotor4")

# dinâmica de motor/ESC (1.ª ordem assimétrica sobre ω)
TAU_SUBIDA = 0.011            # s — aceleração do rotor (Faessler RAL17)
TAU_DESCIDA = 0.027           # s — abrandamento (só o arrasto das pás freia; 2,5× mais lento)
TAU_ALTERNATIVO_CF = 0.072    # s — Tm do Crazyflie 2.1 (SysID arXiv 2404.07837) — para testar robustez

# comando ESC
DSHOT_BITS = 11               # DShot11: 2048 níveis (0..2047)
ATRASO_COMANDO = 0.008        # s — sensor→inferência→ESC no RPi 5 (pior caso kernel normal: 8,45 ms)

# --------------------------------------------------------------------------------------- sensores
# modelo de erro do giroscópio (após calibração de arranque, como os firmwares fazem):
#   medida(t) = ω_verdadeiro(t − atraso) + bias(t) + ruído,  bias(t) = bias₀ + random walk
GIRO_PRESETS = {
    #                    bias₀ σ (rad/s)  ruído σ (rad/s)  deriva σ (rad/s/√s)  atraso (s)  taxa (Hz)
    "mpu6050": {"bias_sigma": 0.035, "ruido_sigma": 0.0020, "deriva_sigma": 0.0005,
                "atraso_s": 0.004, "taxa_hz": 1000.0},
    "bmi088": {"bias_sigma": 0.0035, "ruido_sigma": 0.0018, "deriva_sigma": 0.0002,
               "atraso_s": 0.002, "taxa_hz": 1000.0},
}
# acelerómetro (só no hardware "IMU"): medida = a_específica + bias + ruído
ACC_PRESETS = {
    "mpu6050": {"bias_sigma": 0.10, "ruido_sigma": 0.05, "atraso_s": 0.004, "taxa_hz": 1000.0},
    "bmi088": {"bias_sigma": 0.05, "ruido_sigma": 0.03, "atraso_s": 0.002, "taxa_hz": 1000.0},
}

MODELO_XML = "models/drone_rpi/drone_rpi.xml"


def carregar(keyframe: str | None = None) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """Carrega o drone do dono (`models/drone_rpi/drone_rpi.xml`) e devolve (model, data).

    `keyframe` opcional ("hover" | "pousado") repõe o estado nesse keyframe. Nada é alterado no XML.
    """
    import pathlib
    raiz = pathlib.Path(__file__).resolve().parents[1]
    model = mujoco.MjModel.from_xml_path(str(raiz / MODELO_XML))
    data = mujoco.MjData(model)
    if keyframe is not None:
        mujoco.mj_resetDataKeyframe(model, data, model.key(keyframe).id)
    mujoco.mj_forward(model, data)
    return model, data


# --------------------------------------------------------------------------------------- motores
class Motores:
    """ESC + 4 motores brushless: velocidade de rotor com dinâmica real, empuxo T = kf·ω².

    Uso por passo de física (dt = timestep do modelo):

        motores.comandar(omega_cmd)     # 4 velocidades alvo (rad/s) — o que a política manda
        for _ in range(decimation):
            motores.passo(dt)           # integra ω e ESCREVE data.ctrl (N) dos 4 rotores
            mujoco.mj_step(model, data)

    Física da camada (tudo o resto passa pelo `mj_step`):
      · ω̇ = (ω_cmd − ω)/τ_sub se ω_cmd > ω, senão /τ_desc  (assimétrico; solução exata por passo);
      · quantização DShot: ω_cmd arredondado a DSHOT_BITS níveis em [0, ω_max];
      · atraso de comando: o comando só chega aos motores passados `atraso_comando` segundos
        (fila FIFO; o RPi 5 com Linux normal tem 8,45 ms de pior caso medido);
      · saturação por rotor: ω ∈ [0, ω_max] ⇒ T ∈ [0, T_max] — a "caixa" de comandos impossíveis
        (empuxo máximo E momento máximo) não existe aqui: cada rotor satura sozinho.
    """

    def __init__(self, model: mujoco.MjModel, data: mujoco.MjData, *,
                 tau_subida: float = TAU_SUBIDA, tau_descida: float = TAU_DESCIDA,
                 omega_max: float = OMEGA_MAX, kf: float = KF,
                 dshot_bits: int = DSHOT_BITS, atraso_comando: float = ATRASO_COMANDO):
        self.model, self.data = model, data
        self.tau_subida = float(tau_subida)
        self.tau_descida = float(tau_descida)
        self.omega_max = float(omega_max)
        self.kf = float(kf)
        self.dshot_bits = int(dshot_bits)
        self.atraso_comando = float(atraso_comando)
        self.slots = np.array([model.actuator_ctrladr[mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_ACTUATOR, n)] for n in T_ROTORES], dtype=int)
        self.omega = np.zeros(4)          # velocidade REAL dos rotores (rad/s)
        self._comando = np.zeros(4)       # último comando recebido pelos motores (após atraso/quantização)
        self._fila: list[tuple[float, np.ndarray]] = []   # (t_aplicar, omega_cmd quantizado)

    # -- comando (lado do computador de bordo) ------------------------------------------------
    def comandar(self, omega_cmd) -> np.ndarray:
        """Recebe as 4 velocidades-alvo (rad/s), quantiza (DShot) e agenda a chegada aos motores."""
        c = np.clip(np.asarray(omega_cmd, dtype=float).reshape(4), 0.0, self.omega_max)
        if self.dshot_bits > 0:
            niveis = 2 ** self.dshot_bits - 1
            c = np.round(c / self.omega_max * niveis) / niveis * self.omega_max
        self._fila.append((self.data.time + self.atraso_comando, c))
        return c

    def reiniciar(self, omega=None) -> None:
        """Repõe os rotores (arranque: parados) e limpa a fila de comandos."""
        self.omega = np.zeros(4) if omega is None else np.clip(
            np.asarray(omega, dtype=float).reshape(4), 0.0, self.omega_max)
        self._comando = self.omega.copy()
        self._fila.clear()
        self._escrever_ctrl()

    # -- física do motor/ESC (a cada passo de mj_step) ------------------------------------------
    def passo(self, dt: float) -> np.ndarray:
        """Integra ω durante `dt` (1.ª ordem assimétrica, solução exata) e escreve `data.ctrl` (N)."""
        while self._fila and self._fila[0][0] <= self.data.time + 1e-12:
            _, c = self._fila.pop(0)
            self._comando = c
        cmd = self._comando
        tau = np.where(cmd > self.omega, self.tau_subida, self.tau_descida)
        self.omega = cmd + (self.omega - cmd) * np.exp(-dt / tau)
        self.omega = np.clip(self.omega, 0.0, self.omega_max)
        self._escrever_ctrl()
        return self.forcas()

    def forcas(self) -> np.ndarray:
        """Empuxo atual de cada rotor (N), T = kf·ω² (é o que está em `data.ctrl`)."""
        return self.kf * self.omega ** 2

    def _escrever_ctrl(self) -> None:
        self.data.ctrl[self.slots] = self.forcas()


# --------------------------------------------------------------------------------------- sensores
class _SensorComErro:
    """Base: amostragem por taxa + hold, atraso, bias residual + deriva (random walk) e ruído branco."""

    def __init__(self, model: mujoco.MjModel, data: mujoco.MjData, nome_sensor: str, cfg: dict,
                 dim: int = 3):
        self.model, self.data, self.dim = model, data, dim
        self.nome_sensor = nome_sensor
        self.bias_sigma = float(cfg["bias_sigma"])
        self.ruido_sigma = float(cfg["ruido_sigma"])
        self.atraso_s = float(cfg["atraso_s"])
        self.taxa_hz = float(cfg["taxa_hz"])
        self.deriva_sigma = float(cfg.get("deriva_sigma", 0.0))
        self._sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, nome_sensor)
        self._adr = model.sensor_adr[self._sid]
        self.medicao = np.zeros(dim)
        self.bias = np.zeros(dim)
        self._hist: list[tuple[float, np.ndarray]] = []   # (t, leitura_verdadeira)
        self._prox_amostra = 0.0

    def reiniciar(self, np_random) -> None:
        """Calibração de arranque: bias residual amostrado por episódio + deriva zerada."""
        self.bias = np_random.normal(0.0, self.bias_sigma, self.dim)
        self._hist.clear()
        self._prox_amostra = 0.0
        self.medicao = self._verdade_agora().copy()

    def _verdade_agora(self) -> np.ndarray:
        return np.array(self.data.sensordata[self._adr:self._adr + self.dim], dtype=float)

    def passo(self, dt: float, np_random) -> None:
        """Regista a verdade física e atualiza a medição à taxa do sensor (com hold entre amostras)."""
        t = self.data.time
        self._hist.append((t, self._verdade_agora()))
        while self._hist and self._hist[0][0] < t - max(self.atraso_s, 0.02) - dt:
            self._hist.pop(0)
        if t + 1e-12 >= self._prox_amostra:
            self._prox_amostra = t + 1.0 / self.taxa_hz
            if self.deriva_sigma > 0.0:                     # random walk do bias
                self.bias = self.bias + np_random.normal(0.0, self.deriva_sigma * np.sqrt(dt), self.dim)
            alvo = t - self.atraso_s
            verdade = self._hist[0][1]
            for tt, vv in self._hist:                        # sample-and-hold do instante atrasado
                if tt <= alvo:
                    verdade = vv
            ruido = np_random.normal(0.0, self.ruido_sigma, self.dim) if self.ruido_sigma > 0 else 0.0
            self.medicao = verdade + self.bias + ruido

    def ler(self) -> np.ndarray:
        return self.medicao.copy()


class Giroscopio(_SensorComErro):
    """Sensor de giroscópio do dono (rad/s, frame do corpo): medida = ω + bias + deriva + ruído."""

    def __init__(self, model: mujoco.MjModel, data: mujoco.MjData, preset: str = "mpu6050", **overrides):
        cfg = dict(GIRO_PRESETS[preset])
        cfg.update(overrides)
        super().__init__(model, data, "giro", cfg, dim=3)
        self.preset = preset


class Accel(_SensorComErro):
    """Acelerómetro (m/s², frame do corpo, força específica — lê +9,81 em z em repouso)."""

    def __init__(self, model: mujoco.MjModel, data: mujoco.MjData, preset: str = "mpu6050", **overrides):
        cfg = dict(ACC_PRESETS[preset])
        cfg.update(overrides)
        super().__init__(model, data, "acc", cfg, dim=3)
        self.preset = preset


# --------------------------------------------------------------------------------------- leituras
def ler_imu(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """Leituras VERDADEIRAS do simulador (para comparação/telemetria — não é o que a política vê)."""
    return {"giro": np.array(data.sensor("giro").data, dtype=float),
            "acc": np.array(data.sensor("acc").data, dtype=float),
            "quat": np.array(data.sensor("quat").data, dtype=float)}


def ler_estado(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """Estado privilegiado (só para recompensa/logs): posição/velocidade/atitude exatas."""
    return {"pos": np.array(data.sensor("pos").data, dtype=float),
            "vel": np.array(data.qvel[:3], dtype=float),
            "vel_ang": np.array(data.qvel[3:6], dtype=float)}


# --------------------------------------------------------------------------------------- modos (abertos)
def modo_desligado(model, data, motores: Motores, tau: float) -> None:
    """Motores parados (o drone assenta pela física)."""
    motores.comandar(np.zeros(4))


def modo_gaz_fixo(model, data, motores: Motores, tau: float, fracao: float = 0.45) -> None:
    """Gaz constante nos 4 rotores (fração de ω_max) — sem realimentação; serve para testar a planta."""
    motores.comandar(fracao * OMEGA_MAX * np.ones(4))


MODOS = {"desligado": modo_desligado, "gaz_fixo": modo_gaz_fixo}
