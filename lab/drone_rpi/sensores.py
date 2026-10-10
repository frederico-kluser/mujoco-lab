"""lab.drone_rpi.sensores — os sensores REAIS do drone com o modelo de erro na fonte das leituras.

Todos partilham a mesma mecânica (classe `SensorRuidoso`): o simulador regista a grandeza VERDADEIRA a
cada passo de física; o sensor amostra à SUA taxa (hold entre amostras), com ATRASO de transporte
(múltiplo do passo de física), e devolve

    medida = sat( quant( verdade(t − atraso)·(1 + e_escala) + bias(t) + ruído ) )

bias(t) = bias residual pós-calibração (sorteado por voo) + deriva em passeio aleatório; ruído branco por
amostra σ = densidade·√(largura de banda). Parâmetros dos datasheets no catálogo (`componentes.json` →
`sensores`). O que cada sensor mede:

  · IMU (`giro`, `acc` do MuJoCo no site `imu`): ω no frame do corpo (rad/s) e força específica (m/s²,
    +9,81 em z em repouso) + ruído de VIBRAÇÃO dos motores ∝ (ω_rotor/ω_pairagem)²;
  · Telémetro ToF (`tof`: `rangefinder` no site `baixo`, eixo z do site a apontar para BAIXO): distância
    ao chão ao longo do eixo (= h/cos(inclinação) em chão plano); inválido fora de [mín, máx];
  · Fluxo ótico (PMW3901-like, no mesmo site `baixo`): taxa angular da linha de vista em rad/s,
        Ω_x = v_y/d − ω_x,   Ω_y = −v_x/d − ω_y     (v, ω no frame do site; d = distância ao chão)
    — inclui a parte ROTACIONAL (como o sensor real; compensa-se com o giroscópio no RPi); inválido
    abaixo da distância mínima de foco ou sem chão; satura em ±7,4 rad/s;
  · Barómetro: altitude z + deriva + ruído (telemetria);
  · Monitor de bateria (INA226/ADC): V e I do barramento com ganho/offset/ruído.
"""
from __future__ import annotations

from collections import deque

import mujoco
import numpy as np


class SensorRuidoso:
    """Amostragem + atraso + bias/deriva + escala + ruído + saturação + quantização (vetor de `dim`)."""

    def __init__(self, dim: int, dt_fisica: float, cfg: dict):
        self.dim = dim
        self.dt = float(dt_fisica)
        self.taxa_hz = float(cfg.get("taxa_hz", 1.0 / self.dt))
        self.atraso_s = float(cfg.get("atraso_s", 0.0))
        self.bias_sigma = float(cfg.get("bias_sigma", 0.0))
        self.deriva_sigma = float(cfg.get("deriva_sigma", 0.0))       # por √s
        self.ruido_sigma = float(cfg.get("ruido_sigma", 0.0))         # por amostra
        self.escala_sigma = float(cfg.get("escala_sigma", 0.0))       # erro de fator de escala (fração)
        self.saturacao = float(cfg.get("saturacao", np.inf))
        self.lsb = float(cfg.get("lsb", 0.0))
        self.escala_ruido = 1.0                                       # DR: multiplica ruído/bias/deriva
        self.n_atraso = max(0, round(self.atraso_s / self.dt))
        self.periodo = 1.0 / self.taxa_hz
        self._hist: deque = deque(maxlen=self.n_atraso + 1)
        self.medicao = np.zeros(dim)
        self.bias = np.zeros(dim)
        self.escala = np.ones(dim)
        self._prox = 0.0
        self.n_amostras = 0

    def reiniciar(self, rng, t0: float = 0.0, verdade=None) -> None:
        """Novo voo: bias residual e erro de escala sorteados; histórico com a verdade atual."""
        s = self.escala_ruido
        self.bias = rng.normal(0.0, self.bias_sigma * s, self.dim) if self.bias_sigma > 0 else np.zeros(self.dim)
        self.escala = 1.0 + (rng.normal(0.0, self.escala_sigma, self.dim) if self.escala_sigma > 0
                             else np.zeros(self.dim))
        self._hist.clear()
        v = np.zeros(self.dim) if verdade is None else np.asarray(verdade, dtype=float).reshape(self.dim)
        for _ in range(self._hist.maxlen):
            self._hist.append(v.copy())
        self._prox = t0
        self.medicao = self._medir(v, rng, ruido=False)
        self.n_amostras = 0

    def _medir(self, verdade: np.ndarray, rng, ruido: bool = True, extra_sigma: float = 0.0) -> np.ndarray:
        m = verdade * self.escala + self.bias
        sigma = self.ruido_sigma * self.escala_ruido
        if ruido and (sigma > 0.0 or extra_sigma > 0.0):
            m = m + rng.normal(0.0, 1.0, self.dim) * np.sqrt(sigma * sigma + extra_sigma * extra_sigma)
        if self.lsb > 0.0:
            m = np.round(m / self.lsb) * self.lsb
        if self.saturacao < np.inf:
            m = np.minimum(np.maximum(m, -self.saturacao), self.saturacao)
        return m

    def registar(self, t: float, verdade, rng, extra_sigma: float = 0.0) -> bool:
        """Regista a verdade do passo; devolve True se saiu uma amostra NOVA neste passo."""
        self._hist.append(np.asarray(verdade, dtype=float).reshape(self.dim))
        if self.deriva_sigma > 0.0:
            self.bias = self.bias + rng.normal(0.0, self.deriva_sigma * self.escala_ruido * np.sqrt(self.dt),
                                               self.dim)
        if t + 1e-12 >= self._prox:
            self._prox += self.periodo
            if self._prox <= t:                         # recupera de saltos (reset de tempo)
                self._prox = t + self.periodo
            self.medicao = self._medir(self._hist[0], rng, extra_sigma=extra_sigma)
            self.n_amostras += 1
            return True
        return False

    def ler(self) -> np.ndarray:
        return self.medicao.copy()


def _id_sensor(model: mujoco.MjModel, nome: str) -> tuple[int, int]:
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, nome)
    if sid < 0:
        raise KeyError(f"o modelo não tem o sensor '{nome}'")
    return int(model.sensor_adr[sid]), int(model.sensor_dim[sid])


class IMU:
    """Giroscópio + acelerómetro (o mesmo chip) com vibração dos motores."""

    def __init__(self, model, data, cfg: dict):
        self.data = data
        dt = float(model.opt.timestep)
        self.cfg = cfg
        self.giro = SensorRuidoso(3, dt, cfg["giro"])
        self.acc = SensorRuidoso(3, dt, cfg["acc"])
        self.vib_acc = float(cfg.get("vibracao_acc_rms", 0.0))       # m/s² RMS em pairagem
        self.vib_giro = float(cfg.get("vibracao_giro_rms", 0.0))     # rad/s RMS em pairagem
        self._g = _id_sensor(model, "giro")
        self._a = _id_sensor(model, "acc")

    def verdade(self) -> tuple[np.ndarray, np.ndarray]:
        sd = self.data.sensordata
        return (np.array(sd[self._g[0]:self._g[0] + 3]), np.array(sd[self._a[0]:self._a[0] + 3]))

    def reiniciar(self, rng, t0: float = 0.0) -> None:
        g, a = self.verdade()
        self.giro.reiniciar(rng, t0, g)
        self.acc.reiniciar(rng, t0, a)

    def passo(self, t: float, rng, carga_rotores: float = 0.0) -> bool:
        g, a = self.verdade()
        k = carga_rotores * carga_rotores            # (ω/ω_h)² médio
        novo = self.giro.registar(t, g, rng, extra_sigma=self.vib_giro * k)
        self.acc.registar(t, a, rng, extra_sigma=self.vib_acc * k)
        return novo


class Telemetro:
    """Telémetro ToF ao chão (VL53L1X-like): (distância, válido)."""

    def __init__(self, model, data, cfg: dict):
        self.data = data
        self.s = SensorRuidoso(1, float(model.opt.timestep), cfg)
        self.d_min = float(cfg.get("alcance_min", 0.04))
        self.d_max = float(cfg.get("alcance_max", 3.6))
        self.ruido_rel = float(cfg.get("ruido_rel", 0.0))
        self._r = _id_sensor(model, "tof")
        self.distancia = 0.0
        self.valido = False

    def verdade(self) -> float:
        return float(self.data.sensordata[self._r[0]])

    def reiniciar(self, rng, t0: float = 0.0) -> None:
        self.s.reiniciar(rng, t0, [self.verdade()])
        self._atualiza(self.verdade())

    def _atualiza(self, medida: float) -> None:
        self.valido = bool(self.d_min <= medida <= self.d_max)
        self.distancia = float(np.clip(medida, 0.0, self.d_max)) if self.valido else self.d_max

    def passo(self, t: float, rng) -> None:
        d = self.verdade()
        if d < 0.0:                                   # sem chão no raio (MuJoCo devolve −1)
            d = 10.0 * self.d_max
        if self.s.registar(t, [d], rng, extra_sigma=self.ruido_rel * d):
            self._atualiza(float(self.s.medicao[0]))


class FluxoOptico:
    """Fluxo ótico (PMW3901-like) no site `baixo`: (Ω_x, Ω_y) rad/s + válido."""

    def __init__(self, model, data, cfg: dict):
        self.data = data
        self.s = SensorRuidoso(2, float(model.opt.timestep), cfg)
        self.d_min = float(cfg.get("alcance_min", 0.08))
        self.d_max = float(cfg.get("alcance_max", 4.0))
        self.sat = float(cfg.get("saturacao", 7.4))
        self._v = _id_sensor(model, "vel_baixo")      # velocimeter: v no frame do site
        self._r = _id_sensor(model, "tof")
        self._g = _id_sensor(model, "giro")
        self.fluxo = np.zeros(2)
        self.valido = False

    def verdade(self) -> tuple[np.ndarray, float]:
        sd = self.data.sensordata
        v = np.array(sd[self._v[0]:self._v[0] + 3])
        d = float(sd[self._r[0]])
        w_corpo = np.array(sd[self._g[0]:self._g[0] + 3])
        w = np.array([w_corpo[0], -w_corpo[1], -w_corpo[2]])     # frame do site (rot. 180° em x)
        if d <= 1e-3:
            return np.zeros(2), d
        return np.array([v[1] / d - w[0], -v[0] / d - w[1]]), d

    def reiniciar(self, rng, t0: float = 0.0) -> None:
        f, d = self.verdade()
        self.s.reiniciar(rng, t0, f)
        self.valido = bool(self.d_min <= d <= self.d_max)
        self.fluxo = self.s.ler() if self.valido else np.zeros(2)

    def passo(self, t: float, rng) -> None:
        f, d = self.verdade()
        ok = self.d_min <= d <= self.d_max
        if self.s.registar(t, np.clip(f, -self.sat, self.sat), rng):
            self.valido = bool(ok)
            self.fluxo = np.clip(self.s.medicao, -self.sat, self.sat) if self.valido else np.zeros(2)


class Barometro:
    """Altitude barométrica (m): z + deriva + ruído."""

    def __init__(self, model, data, cfg: dict, corpo: int):
        self.data = data
        self.corpo = corpo
        self.s = SensorRuidoso(1, float(model.opt.timestep), cfg)
        self.altitude = 0.0

    def reiniciar(self, rng, t0: float = 0.0) -> None:
        self.s.reiniciar(rng, t0, [float(self.data.xpos[self.corpo, 2])])
        self.altitude = float(self.s.medicao[0])

    def passo(self, t: float, rng) -> None:
        if self.s.registar(t, [float(self.data.xpos[self.corpo, 2])], rng):
            self.altitude = float(self.s.medicao[0])


class MonitorBateria:
    """Medidor de tensão/corrente do barramento (INA226/ADC do FC) — o que o RPi sabe da bateria."""

    def __init__(self, dt_fisica: float, cfg: dict):
        self.v = SensorRuidoso(1, dt_fisica, cfg.get("tensao", {}))
        self.i = SensorRuidoso(1, dt_fisica, cfg.get("corrente", {}))
        self.tensao = 0.0
        self.corrente = 0.0

    def reiniciar(self, rng, v: float, i: float, t0: float = 0.0) -> None:
        self.v.reiniciar(rng, t0, [v])
        self.i.reiniciar(rng, t0, [i])
        self.tensao, self.corrente = float(self.v.medicao[0]), float(self.i.medicao[0])

    def passo(self, t: float, rng, v: float, i: float) -> None:
        if self.v.registar(t, [v], rng):
            self.tensao = float(self.v.medicao[0])
        if self.i.registar(t, [i], rng):
            self.corrente = float(self.i.medicao[0])
