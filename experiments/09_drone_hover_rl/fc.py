"""experiments/09_drone_hover_rl/fc.py — o FLIGHT CONTROLLER dedicado (firmware estilo Betaflight) simulado.

Arquitetura do plano §6 P1.7 / §7 C1 (o Linux do RPi 5 não serve de FC primário — arXiv 2604.19275): a
POLÍTICA corre no RPi 5 a 50 Hz e manda SETPOINTS ao FC (acelerador coletivo + taxas angulares do
corpo, como um rádio em modo "acro"); o FC fecha a malha de TAXA à frequência da física (500 Hz) com o
SEU giroscópio e faz a mistura para os 4 motores (DShot → ESC). Isto é o modelo do hardware/firmware que
o dono compra — a política (o algoritmo do dono) continua a ser a única decisão de voo.

Por eixo (p, q, r): PID de taxa com D sobre a MEDIDA, filtros PT1 no giroscópio (90 Hz) e no termo D
(60 Hz), anti-windup por limite do integral. Ganhos calculados da PLANTA (não afinados à mão):

    ω̇ ≈ α·u_mix (u_mix = diferencial de acelerador no eixo), motor ≈ 1.ª ordem τ_m
    α_eixo = 4·braço_eixo·(dT/du)/I_eixo   (yaw: 4·(kq/kf)·(dT/du)/I_zz)
    K_p = 1/(α·4ζ²·τ_m) com ζ = 0,7   (polo duplo amortecido da malha P + lag do motor)
    K_i = K_p·ω_c/4,  K_d = 0,15·K_p·τ_m,  ω_c = 1/(2·τ_m)

Mistura em X com "airmode" (como o Betaflight): se a soma sai de [idle, 1], desloca-se o coletivo para
preservar a autoridade de atitude; só se o diferencial pedido não couber é que ele é escalado.
Desarmado: tudo a 0 (motores parados).
"""
from __future__ import annotations

import math

import numpy as np

FILTRO_GIRO_HZ = 90.0
FILTRO_D_HZ = 60.0
ZETA = 0.7
LIMITE_I = 0.25          # fração de acelerador


def _alfa_pt1(fc_hz: float, dt: float) -> float:
    rc = 1.0 / (2.0 * math.pi * fc_hz)
    return dt / (rc + dt)


class ControladorFC:
    """Malha de taxa + mistura + airmode, a correr a cada passo de física."""

    def __init__(self, hw, model, dt: float):
        self.hw = hw
        self.dt = float(dt)
        corpo = model.body("drone").id
        # inércia no frame do CORPO (o MuJoCo guarda-a nos eixos principais): I = R·diag·Rᵀ
        q = model.body_iquat[corpo]
        r = np.zeros(9)
        import mujoco
        mujoco.mju_quat2Mat(r, q)
        r = r.reshape(3, 3)
        i_corpo = r @ np.diag(model.body_inertia[corpo]) @ r.T
        self.inercia = np.diag(i_corpo).copy()
        # planta linearizada em pairagem nominal
        v = hw.bateria.v_nominal
        ph = hw.ponto_pairagem(v)
        w_h = ph["omega"]
        kt = ke = hw.motor.ke
        b = kt * ke / hw.r_motor + 0.5 * kt * hw.motor.i0 / hw.omega0 + 2.0 * hw.kq * w_h
        # rad/s por unidade de ACELERADOR em regime: dω/d(duty) × d(duty)/d(acelerador) (curva do ESC)
        dw_du = (kt * v / hw.r_motor) / b * hw.inclinacao_esc(ph["acelerador"])
        self.tau_motor = hw.j_rotor / b                    # s — constante de tempo do rotor em pairagem
        dT_du = 2.0 * hw.kf * w_h * dw_du                  # N por unidade de acelerador, por rotor
        a = hw.braco / math.sqrt(2.0)                      # braço em x e em y (X simétrico)
        alfa = np.array([4.0 * a * dT_du / self.inercia[0],
                         4.0 * a * dT_du / self.inercia[1],
                         4.0 * (hw.kq / hw.kf) * dT_du / self.inercia[2]])
        self.alfa = alfa
        tm = self.tau_motor
        self.kp = 1.0 / (alfa * 4.0 * ZETA * ZETA * tm)
        wc = 1.0 / (2.0 * tm)
        self.ki = self.kp * wc / 4.0
        self.kd = 0.15 * self.kp * tm
        self.u_pairagem = ph["acelerador"]
        # mistura (r1 frente-esq CW, r2 trás-dir CW, r3 trás-esq CCW, r4 frente-dir CCW):
        # roll: +sign(y) · pitch: −sign(x) (q > 0 baixa o nariz: os rotores de TRÁS sobem) · yaw: −s_i
        pos = hw.pos_rotores
        self.mix = np.stack([np.sign(pos[:, 1]), -np.sign(pos[:, 0]), -hw.GIRO], axis=1)   # (4, 3)
        self.idle = hw.esc.idle
        self.a_giro = _alfa_pt1(FILTRO_GIRO_HZ, self.dt)
        self.a_d = _alfa_pt1(FILTRO_D_HZ, self.dt)
        self.reiniciar()

    def reiniciar(self) -> None:
        self.integral = np.zeros(3)
        self.giro_f = np.zeros(3)
        self.d_f = np.zeros(3)
        self.giro_ant = np.zeros(3)
        self.saida = np.zeros(4)
        self.armado = False

    def armar(self, armado: bool) -> None:
        if armado and not self.armado:
            self.integral[:] = 0.0
        self.armado = bool(armado)

    def passo(self, acelerador: float, taxas_sp, giro_medido) -> np.ndarray:
        """Um ciclo do FC: setpoints (coletivo [0,1], taxas rad/s) + giroscópio → acelerador por motor."""
        if not self.armado:
            self.saida = np.zeros(4)
            return self.saida
        g = np.asarray(giro_medido, dtype=float)
        self.giro_f += self.a_giro * (g - self.giro_f)
        erro = np.asarray(taxas_sp, dtype=float) - self.giro_f
        deriv = (self.giro_f - self.giro_ant) / self.dt
        self.giro_ant = self.giro_f.copy()
        self.d_f += self.a_d * (deriv - self.d_f)
        self.integral = np.minimum(np.maximum(self.integral + self.ki * erro * self.dt, -LIMITE_I), LIMITE_I)
        u_eixos = self.kp * erro + self.integral - self.kd * self.d_f
        dif = self.mix @ u_eixos                              # (4,) diferencial por motor
        col = min(max(float(acelerador), 0.0), 1.0)
        span = float(dif.max() - dif.min())
        faixa = 1.0 - self.idle
        if span > faixa:                                      # o diferencial não cabe: escala-o
            dif *= faixa / span
            span = faixa
        u = col + dif
        if u.max() > 1.0:                                     # airmode: desloca o coletivo para baixo
            u -= u.max() - 1.0
        if u.min() < self.idle:                               # ... ou para cima (nunca abaixo do idle)
            u += self.idle - u.min()
        self.saida = np.minimum(np.maximum(u, self.idle), 1.0)
        return self.saida
