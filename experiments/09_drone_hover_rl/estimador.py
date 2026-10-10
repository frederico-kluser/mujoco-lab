"""experiments/09_drone_hover_rl/estimador.py — o que o RPi 5 sabe do voo, calculado SÓ com os sensores.

Nada aqui lê posição/velocidade/atitude do simulador: as entradas são as leituras MEDIDAS (com erro) do
giroscópio, acelerómetro, telémetro ToF e fluxo ótico (`lab/drone_rpi/sensores.py`). É o mesmo código que
correria no drone real, à taxa da física (o RPi lê a IMU a ≥ 500 Hz):

  · ATITUDE (roll φ, pitch θ): filtro complementar — integra as taxas medidas (cinemática de Euler ZYX) e
    puxa devagar (k = 0,5 /s) para a inclinação do acelerómetro φ_a = atan2(a_y, a_z),
    θ_a = atan2(−a_x, √(a_y²+a_z²)). ⚠ Num multirrotor em voo o acelerómetro mede empuxo+arrasto (não a
    gravidade) — com vento persistente a estimativa enviesa, COMO no real; o fluxo ótico corrige a posição.
  · RUMO Δψ desde o armar: integração da taxa de guinada (sem magnetómetro → deriva com o bias do giro).
  · ALTURA ĥ e VELOCIDADE VERTICAL v̂_z: predição com a aceleração vertical (R̂·a − g) e correção a cada
    amostra NOVA do ToF (ĥ_ToF = d·cosφ̂·cosθ̂) com ganhos de observador de 2.ª ordem (ω₀ = 4 rad/s, ζ = 0,7).
  · VELOCIDADE HORIZONTAL (corpo) pelo fluxo: o sensor (site `baixo`, rodado 180° em x) dá
    Ω_x = −v_y/d − ω_x e Ω_y = −v_x/d + ω_y ⇒ v_x = d·(ω_y − Ω_y), v_y = −d·(Ω_x + ω_x), filtrada (PT1);
  · ODOMETRIA (x̂, ŷ) no frame de arranque: integra R_z(Δψ)·v̂_xy. Deriva — como a de qualquer drone sem GPS.
"""
from __future__ import annotations

import math

G = 9.81
K_ATITUDE = 0.5          # 1/s — peso do acelerómetro no filtro complementar
W_ALTURA = 4.0           # rad/s — banda do observador de altura
ZETA_ALTURA = 0.7
ALFA_FLUXO = 0.35        # PT1 da velocidade do fluxo, por amostra nova
DECAI_FLUXO = 0.995      # sem fluxo válido, a velocidade estimada decai devagar (por passo de física)


class EstimadorBordo:
    """Estimação de bordo a partir das leituras medidas (escalares Python: barato a 500 Hz)."""

    def __init__(self, dt: float):
        self.dt = float(dt)
        self.reiniciar()

    def reiniciar(self, acc=(0.0, 0.0, G), tof_d: float = 0.0, tof_ok: bool = False) -> None:
        ax, ay, az = (float(v) for v in acc)
        self.roll = math.atan2(ay, az)
        self.pitch = math.atan2(-ax, math.hypot(ay, az))
        self.psi = 0.0
        self.h = tof_d * math.cos(self.roll) * math.cos(self.pitch) if tof_ok else 0.0
        self.vz = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.x = 0.0
        self.y = 0.0
        self._n_tof = -1
        self._n_fluxo = -1

    def passo(self, giro, acc, tof_d: float, tof_ok: bool, n_tof: int,
              fluxo, fluxo_ok: bool, n_fluxo: int) -> None:
        """Um passo de física com as leituras atuais (`n_*` = contador de amostras, p/ detetar novas)."""
        dt = self.dt
        p, q, r = (float(v) for v in giro)
        ax, ay, az = (float(v) for v in acc)
        sf, cf = math.sin(self.roll), math.cos(self.roll)
        ct = math.cos(self.pitch)
        tt = math.tan(self.pitch) if abs(ct) > 1e-3 else 0.0
        # atitude: cinemática ZYX + correção do acelerómetro
        droll = p + (q * sf + r * cf) * tt
        dpitch = q * cf - r * sf
        dpsi = (q * sf + r * cf) / ct if abs(ct) > 1e-3 else 0.0
        roll_a = math.atan2(ay, az)
        pitch_a = math.atan2(-ax, math.hypot(ay, az))
        self.roll += dt * (droll + K_ATITUDE * _envolve(roll_a - self.roll))
        self.pitch += dt * (dpitch + K_ATITUDE * (pitch_a - self.pitch))
        self.psi = _envolve(self.psi + dt * dpsi)
        # altura e velocidade vertical
        sf, cf = math.sin(self.roll), math.cos(self.roll)
        st, ct = math.sin(self.pitch), math.cos(self.pitch)
        a_z = -st * ax + sf * ct * ay + cf * ct * az - G
        self.vz += a_z * dt
        self.h += self.vz * dt
        if n_tof != self._n_tof:
            self._n_tof = n_tof
            if tof_ok:
                periodo = max(dt, 1.0 / 30.0)
                k_h = min(1.0, 2.0 * ZETA_ALTURA * W_ALTURA * periodo)
                k_v = W_ALTURA * W_ALTURA * periodo
                e = tof_d * cf * ct - self.h
                self.h += k_h * e
                self.vz += k_v * e
        # velocidade horizontal pelo fluxo (com a distância medida pelo ToF, mesmo site)
        if n_fluxo != self._n_fluxo:
            self._n_fluxo = n_fluxo
            if fluxo_ok and tof_ok:
                fx, fy = (float(v) for v in fluxo)
                vx_m = tof_d * (q - fy)
                vy_m = -tof_d * (fx + p)
                self.vx += ALFA_FLUXO * (vx_m - self.vx)
                self.vy += ALFA_FLUXO * (vy_m - self.vy)
        if not (fluxo_ok and tof_ok):
            self.vx *= DECAI_FLUXO
            self.vy *= DECAI_FLUXO
        cpsi, spsi = math.cos(self.psi), math.sin(self.psi)
        self.x += dt * (cpsi * self.vx - spsi * self.vy)
        self.y += dt * (spsi * self.vx + cpsi * self.vy)


def _envolve(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi
