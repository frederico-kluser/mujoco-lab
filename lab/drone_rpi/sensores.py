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

IMPLEMENTAÇÃO (2026-10-12). A 500 Hz, com vetores de 1–3 elementos, o custo era o despacho do NumPy: o estado de cada
sensor (bias, escala, histórico, medição) vive em LISTAS de `float` e a conta faz-se em escalares, pela mesma ordem de
operações — resultado bit a bit igual ao vetorial (ver `escalar.py`). Por fora nada muda: `medicao`, `bias`, `escala`
e `fluxo` continuam a ser `ndarray`. Cada `registar` tem duas fases — `_preparar` (regista a verdade, avança o relógio
de amostragem e diz QUANTOS normais N(0, 1) o passo consome) e `_concluir` (aplica a deriva e mede, com os normais já
sorteados) — para a `Planta` sortear os de todos os sensores numa só chamada ao gerador: `standard_normal(n)` dá a
mesma sequência que as chamadas separadas de `normal` (verificado em `escalar.verificar`).
"""
from __future__ import annotations

import math
from collections import deque

import mujoco
import numpy as np

from .escalar import clip

_INF = math.inf
_copysign, _nan = math.copysign, math.isnan


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
        self._raiz_dt = math.sqrt(self.dt)
        self._hist: deque = deque(maxlen=self.n_atraso + 1)           # listas de `dim` floats (a mais antiga à frente)
        self._med = [0.0] * dim                                       # a medição atual …
        self._med_np = None                                           # … e o `ndarray` dela, feito só quando o pedem
        self._bias = [0.0] * dim
        self._escala = [1.0] * dim
        self._prox = 0.0
        self.n_amostras = 0
        self._n = 0                 # normais N(0, 1) que o passo preparado consome
        self._amostra = False       # o passo preparado tira uma amostra nova?
        self._s_ruido = None        # σ total do ruído dessa amostra (None = sem ruído)

    # ------------------------------------------------------------------ vistas ndarray (a API de sempre)
    @property
    def medicao(self) -> np.ndarray:
        if self._med_np is None:
            self._med_np = np.array(self._med, dtype=float)
        return self._med_np

    @medicao.setter
    def medicao(self, valor) -> None:
        self._med = np.asarray(valor, dtype=float).reshape(self.dim).tolist()
        self._med_np = None

    @property
    def bias(self) -> np.ndarray:
        return np.array(self._bias, dtype=float)

    @bias.setter
    def bias(self, valor) -> None:
        self._bias = np.broadcast_to(np.asarray(valor, dtype=float), (self.dim,)).tolist()

    @property
    def escala(self) -> np.ndarray:
        return np.array(self._escala, dtype=float)

    @escala.setter
    def escala(self, valor) -> None:
        self._escala = np.broadcast_to(np.asarray(valor, dtype=float), (self.dim,)).tolist()

    # ------------------------------------------------------------------ voo novo
    def reiniciar(self, rng, t0: float = 0.0, verdade=None) -> None:
        """Novo voo: bias residual e erro de escala sorteados; histórico com a verdade atual."""
        s = self.escala_ruido
        self.bias = rng.normal(0.0, self.bias_sigma * s, self.dim) if self.bias_sigma > 0 else np.zeros(self.dim)
        self.escala = 1.0 + (rng.normal(0.0, self.escala_sigma, self.dim) if self.escala_sigma > 0
                             else np.zeros(self.dim))
        self._hist.clear()
        v = ([0.0] * self.dim if verdade is None
             else np.asarray(verdade, dtype=float).reshape(self.dim).tolist())
        for _ in range(self._hist.maxlen):
            self._hist.append(list(v))
        self._prox = t0
        self._med = self._medir_l(v, None, 0, None)
        self._med_np = None
        self.n_amostras = 0

    # ------------------------------------------------------------------ medição
    def _medir_l(self, verdade: list, z, k: int, s_ruido) -> list:
        """medida = sat(quant(verdade·escala + bias + ruído)); o ruído são `dim` normais de `z`, a partir de `k`,
        vezes `s_ruido` (None = sem ruído)."""
        lsb, sat = self.lsb, self.saturacao
        if s_ruido is not None and self.dim == 3 and lsb > 0.0 and sat < _INF:
            # o caso da IMU (3 eixos com ruído, quantização e saturação, a 500 Hz): a mesma conta, sem laço
            try:
                v0, v1, v2 = verdade
                e0, e1, e2 = self._escala
                b0, b1, b2 = self._bias
                q0 = (v0 * e0 + b0 + z[k] * s_ruido) / lsb
                q1 = (v1 * e1 + b1 + z[k + 1] * s_ruido) / lsb
                q2 = (v2 * e2 + b2 + z[k + 2] * s_ruido) / lsb
                x0 = _copysign(round(abs(q0)), q0) * lsb
                x1 = _copysign(round(abs(q1)), q1) * lsb
                x2 = _copysign(round(abs(q2)), q2) * lsb
                return [min(sat, max(-sat, x0)), min(sat, max(-sat, x1)), min(sat, max(-sat, x2))]
            except (OverflowError, ValueError):       # NaN/inf (o `round` recusa-os): segue pelo caminho geral
                pass
        m = []
        for v, e, b in zip(verdade, self._escala, self._bias):
            x = v * e + b
            if s_ruido is not None:
                x = x + z[k] * s_ruido
                k += 1
            if lsb > 0.0:
                q = x / lsb
                # np.round(q): para o par, com o sinal do zero (`rint`, em linha; NaN/inf passam tal e qual)
                x = (_copysign(round(abs(q)), q) if q - q == 0.0 else q) * lsb
            if sat < _INF:
                x = x if (x > -sat or _nan(x)) else -sat           # np.maximum(x, −sat)
                x = x if (x < sat or _nan(x)) else sat             # np.minimum(x, sat)
            m.append(x)
        return m

    def _medir(self, verdade, rng, ruido: bool = True, extra_sigma: float = 0.0) -> np.ndarray:
        """Uma medição AVULSA (sorteia o seu próprio ruído) — a forma vetorial de sempre, para uso externo."""
        v = np.asarray(verdade, dtype=float).reshape(self.dim).tolist()
        sigma = self.ruido_sigma * self.escala_ruido
        if ruido and (sigma > 0.0 or extra_sigma > 0.0):
            s_ruido = math.sqrt(sigma * sigma + extra_sigma * extra_sigma)
            return np.array(self._medir_l(v, rng.standard_normal(self.dim).tolist(), 0, s_ruido))
        return np.array(self._medir_l(v, None, 0, None))

    def _preparar(self, t: float, verdade: list, extra_sigma: float = 0.0) -> int:
        """1.ª fase de `registar`: guarda a verdade do passo (lista de `dim` floats), decide se sai uma amostra
        nova e devolve quantos normais N(0, 1) o passo consome (deriva + ruído da amostra)."""
        self._hist.append(verdade)
        n = self.dim if self.deriva_sigma > 0.0 else 0
        if t + 1e-12 >= self._prox:
            self._prox += self.periodo
            if self._prox <= t:                         # recupera de saltos (reset de tempo)
                self._prox = t + self.periodo
            sigma = self.ruido_sigma * self.escala_ruido
            if sigma > 0.0 or extra_sigma > 0.0:
                self._s_ruido = math.sqrt(sigma * sigma + extra_sigma * extra_sigma)
                n += self.dim
            else:
                self._s_ruido = None
            self._amostra = True
        else:
            self._amostra = False
        self._n = n
        return n

    def _concluir(self, z, k: int) -> bool:
        """2.ª fase de `registar`: deriva do bias e, se houver amostra nova, a medição — com os normais `z[k:]` já
        sorteados (primeiro os da deriva, depois os do ruído). Devolve True se saiu uma amostra NOVA."""
        if self.deriva_sigma > 0.0:
            sd = self.deriva_sigma * self.escala_ruido * self._raiz_dt
            dim = self.dim
            if dim == 3:
                b0, b1, b2 = self._bias
                self._bias = [b0 + sd * z[k], b1 + sd * z[k + 1], b2 + sd * z[k + 2]]
            else:
                self._bias = [b + sd * zj for b, zj in zip(self._bias, z[k:k + dim])]
            k += dim
        if self._amostra:
            self._med = self._medir_l(self._hist[0], z, k, self._s_ruido)
            self._med_np = None
            self.n_amostras += 1
            return True
        return False

    def registar(self, t: float, verdade, rng, extra_sigma: float = 0.0) -> bool:
        """Regista a verdade do passo; devolve True se saiu uma amostra NOVA neste passo."""
        n = self._preparar(t, np.asarray(verdade, dtype=float).reshape(self.dim).tolist(), extra_sigma)
        return self._concluir(_sortear(rng, n), 0)

    def ler(self) -> np.ndarray:
        return self.medicao.copy()


def _sortear(rng, n: int):
    """`n` normais N(0, 1) numa só chamada ao gerador (lista de floats; nenhuma chamada se n = 0)."""
    return rng.standard_normal(n).tolist() if n else ()


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
        self._novo = False

    def verdade(self) -> tuple[np.ndarray, np.ndarray]:
        sd = self.data.sensordata
        return (np.array(sd[self._g[0]:self._g[0] + 3]), np.array(sd[self._a[0]:self._a[0] + 3]))

    def reiniciar(self, rng, t0: float = 0.0) -> None:
        g, a = self.verdade()
        self.giro.reiniciar(rng, t0, g)
        self.acc.reiniciar(rng, t0, a)

    def _preparar(self, t: float, sd: list, carga_rotores: float) -> int:
        """`sd` = `data.sensordata` como lista; devolve os normais que o giroscópio + o acelerómetro consomem."""
        g, a = self._g[0], self._a[0]
        k = carga_rotores * carga_rotores            # (ω/ω_h)² médio
        return (self.giro._preparar(t, sd[g:g + 3], self.vib_giro * k)
                + self.acc._preparar(t, sd[a:a + 3], self.vib_acc * k))

    def _concluir(self, z, k: int) -> int:
        """Conclui os dois sensores com os normais `z[k:]`; devolve o índice do 1.º normal ainda por usar."""
        self._novo = self.giro._concluir(z, k)
        k += self.giro._n
        self.acc._concluir(z, k)
        return k + self.acc._n

    def passo(self, t: float, rng, carga_rotores: float = 0.0) -> bool:
        self._concluir(_sortear(rng, self._preparar(t, self.data.sensordata.tolist(), carga_rotores)), 0)
        return self._novo


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
        self.distancia = clip(medida, 0.0, self.d_max) if self.valido else self.d_max

    def _preparar(self, t: float, sd: list) -> int:
        d = sd[self._r[0]]
        if d < 0.0:                                   # sem chão no raio (MuJoCo devolve −1)
            d = 10.0 * self.d_max
        return self.s._preparar(t, [d], self.ruido_rel * d)

    def _concluir(self, z, k: int) -> int:
        if self.s._concluir(z, k):
            self._atualiza(self.s._med[0])
        return k + self.s._n

    def passo(self, t: float, rng) -> None:
        self._concluir(_sortear(rng, self._preparar(t, self.data.sensordata.tolist())), 0)


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
        self._fluxo = [0.0, 0.0]
        self._fluxo_np = None
        self.valido = False
        self._ok = False

    @property
    def fluxo(self) -> np.ndarray:
        if self._fluxo_np is None:
            self._fluxo_np = np.array(self._fluxo, dtype=float)
        return self._fluxo_np

    @fluxo.setter
    def fluxo(self, valor) -> None:
        self._fluxo = np.asarray(valor, dtype=float).reshape(2).tolist()
        self._fluxo_np = None

    def _verdade_l(self, sd: list) -> tuple[list, float]:
        """(fluxo verdadeiro, distância) da lista `sd` = `data.sensordata`."""
        iv, ig = self._v[0], self._g[0]
        d = sd[self._r[0]]
        if d <= 1e-3:
            return [0.0, 0.0], d
        # ω no frame do site (rot. de 180° em x) = (ω_x, −ω_y, −ω_z) do corpo
        return [sd[iv + 1] / d - sd[ig], -sd[iv] / d - -sd[ig + 1]], d

    def verdade(self) -> tuple[np.ndarray, float]:
        f, d = self._verdade_l(self.data.sensordata.tolist())
        return np.array(f), d

    def reiniciar(self, rng, t0: float = 0.0) -> None:
        f, d = self.verdade()
        self.s.reiniciar(rng, t0, f)
        self.valido = bool(self.d_min <= d <= self.d_max)
        self.fluxo = self.s.ler() if self.valido else np.zeros(2)

    def _preparar(self, t: float, sd: list) -> int:
        f, d = self._verdade_l(sd)
        self._ok = self.d_min <= d <= self.d_max
        sat = self.sat
        return self.s._preparar(t, [clip(f[0], -sat, sat), clip(f[1], -sat, sat)])

    def _concluir(self, z, k: int) -> int:
        if self.s._concluir(z, k):
            self.valido = bool(self._ok)
            sat = self.sat
            m = self.s._med
            self._fluxo = [clip(m[0], -sat, sat), clip(m[1], -sat, sat)] if self.valido else [0.0, 0.0]
            self._fluxo_np = None
        return k + self.s._n

    def passo(self, t: float, rng) -> None:
        self._concluir(_sortear(rng, self._preparar(t, self.data.sensordata.tolist())), 0)


class Barometro:
    """Altitude barométrica (m): z + deriva + ruído."""

    def __init__(self, model, data, cfg: dict, corpo: int):
        self.data = data
        self.corpo = corpo
        self.s = SensorRuidoso(1, float(model.opt.timestep), cfg)
        self.altitude = 0.0

    def reiniciar(self, rng, t0: float = 0.0) -> None:
        self.s.reiniciar(rng, t0, [float(self.data.xpos[self.corpo, 2])])
        self.altitude = self.s._med[0]

    def _preparar(self, t: float, z_corpo: float) -> int:
        return self.s._preparar(t, [z_corpo])

    def _concluir(self, z, k: int) -> int:
        if self.s._concluir(z, k):
            self.altitude = self.s._med[0]
        return k + self.s._n

    def passo(self, t: float, rng) -> None:
        self._concluir(_sortear(rng, self._preparar(t, float(self.data.xpos[self.corpo, 2]))), 0)


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
        self.tensao, self.corrente = self.v._med[0], self.i._med[0]

    def _preparar(self, t: float, v: float, i: float) -> int:
        return self.v._preparar(t, [v]) + self.i._preparar(t, [i])

    def _concluir(self, z, k: int) -> int:
        if self.v._concluir(z, k):
            self.tensao = self.v._med[0]
        k += self.v._n
        if self.i._concluir(z, k):
            self.corrente = self.i._med[0]
        return k + self.i._n

    def passo(self, t: float, rng, v: float, i: float) -> None:
        self._concluir(_sortear(rng, self._preparar(t, float(v), float(i))), 0)
