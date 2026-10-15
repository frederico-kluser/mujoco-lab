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

IMPLEMENTAÇÃO (2026-10-12): o `passo` corre a 500 Hz com vetores de 3–4 elementos, onde o custo do NumPy é só
despacho — a conta faz-se em `float` do Python, pela MESMA ordem de operações (resultado bit a bit igual ao vetorial;
prova em `bench_treino.py identidade`). O estado e os ganhos vivem em listas; por fora continuam a ser `ndarray`
(`integral`, `giro_f`, `d_f`, `giro_ant`, `kp`, `ki`, `kd`, `mix`: ler devolve uma cópia só de leitura, atribuir um
vetor novo funciona). A mistura `mix @ u` é um `dgemv` do BLAS: com a matriz de sinais (±1/0) a linha
`0 + ((m0·u0 + m1·u1) + m2·u2)` é exata (o `0 +` fixa o sinal de um resultado nulo, como o acumulador do BLAS), e isso
é VERIFICADO contra o NumPy desta máquina sempre que a `mix` é definida (amostras fixas, com zeros de ambos os sinais)
— se não bater, o `passo` usa o `mix @ u` de origem.
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


_F64 = np.dtype(np.float64)
_nan = math.isnan


def _tres(v) -> list:
    """Vetor de 3 (ndarray de qualquer tipo real, lista ou tuplo) → lista de floats (`np.asarray(v, dtype=float)`)."""
    if type(v) is np.ndarray and v.dtype is _F64:
        return v.tolist()
    return np.asarray(v, dtype=float).tolist()


class _Vetor:
    """Atributo vetorial guardado como LISTA de floats em `_<nome>` (o laço de 500 Hz lê a lista, sem NumPy).

    Por fora é um `ndarray`: LER devolve uma cópia só de leitura (alterá-la no sítio dá erro, em vez de se perder em
    silêncio); ATRIBUIR um vetor novo substitui a lista.
    """

    def __init__(self, forma: tuple = (3,)):
        self.forma = forma

    def __set_name__(self, dono, nome: str) -> None:
        self.privado = "_" + nome

    def __get__(self, obj, tipo=None):
        if obj is None:
            return self
        a = np.array(getattr(obj, self.privado), dtype=float)
        a.flags.writeable = False
        return a

    def __set__(self, obj, valor) -> None:
        setattr(obj, self.privado, np.broadcast_to(np.asarray(valor, dtype=float), self.forma).tolist())


class ControladorFC:
    """Malha de taxa + mistura + airmode, a correr a cada passo de física."""

    integral = _Vetor()
    giro_f = _Vetor()
    d_f = _Vetor()
    giro_ant = _Vetor()
    kp = _Vetor()
    ki = _Vetor()
    kd = _Vetor()

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

    @property
    def mix(self) -> np.ndarray:
        """Matriz de mistura (4, 3): acelerador diferencial por motor = mix @ (u_roll, u_pitch, u_yaw)."""
        return self._mix

    @mix.setter
    def mix(self, valor) -> None:
        self._mix = np.array(valor, dtype=float).reshape(4, 3)
        self._mix.flags.writeable = False
        self._mix_l = self._mix.tolist()
        # a linha escalar 0 + ((m0·u0 + m1·u1) + m2·u2) reproduz o `mix @ u` (dgemv) desta máquina? (amostras fixas)
        g = np.random.default_rng(20261012)
        self._mix_escalar = True
        for _ in range(64):
            u = g.normal(size=3) * 10.0 ** g.uniform(-3.0, 1.0)
            nulos = g.random(3) < 0.33
            u[nulos] = g.choice([0.0, -0.0], size=int(nulos.sum()))
            u0, u1, u2 = u.tolist()
            meu = np.array([0.0 + ((m0 * u0 + m1 * u1) + m2 * u2) for m0, m1, m2 in self._mix_l])
            if meu.tobytes() != (self._mix @ u).tobytes():
                self._mix_escalar = False
                break

    def reiniciar(self) -> None:
        self.integral = np.zeros(3)
        self.giro_f = np.zeros(3)
        self.d_f = np.zeros(3)
        self.giro_ant = np.zeros(3)
        self.saida = np.zeros(4)
        self.armado = False

    def armar(self, armado: bool) -> None:
        if armado and not self.armado:
            self._integral = [0.0, 0.0, 0.0]
        self.armado = bool(armado)

    def passo(self, acelerador: float, taxas_sp, giro_medido) -> np.ndarray:
        """Um ciclo do FC: setpoints (coletivo [0,1], taxas rad/s) + giroscópio → acelerador por motor."""
        if not self.armado:
            self.saida = np.zeros(4)
            return self.saida
        a_giro, a_d, dt = self.a_giro, self.a_d, self.dt
        u_eixos, giro_f, d_f, integral = [], [], [], []
        for g, sp, gf, ga, df, itg, kp, ki, kd in zip(_tres(giro_medido), _tres(taxas_sp), self._giro_f,
                                                      self._giro_ant, self._d_f, self._integral, self._kp,
                                                      self._ki, self._kd, strict=True):
            gf = gf + a_giro * (g - gf)                           # PT1 do giroscópio
            erro = sp - gf
            df = df + a_d * ((gf - ga) / dt - df)                 # derivada da MEDIDA, com PT1
            itg = itg + ki * erro * dt
            itg = itg if (itg > -LIMITE_I or _nan(itg)) else -LIMITE_I       # anti-windup (np.maximum/minimum)
            itg = itg if (itg < LIMITE_I or _nan(itg)) else LIMITE_I
            giro_f.append(gf)
            d_f.append(df)
            integral.append(itg)
            u_eixos.append(kp * erro + itg - kd * df)
        self._giro_f, self._giro_ant, self._d_f, self._integral = giro_f, giro_f, d_f, integral
        if self._mix_escalar:
            u0, u1, u2 = u_eixos
            d0, d1, d2, d3 = [0.0 + ((m0 * u0 + m1 * u1) + m2 * u2) for m0, m1, m2 in self._mix_l]
        else:
            d0, d1, d2, d3 = (self._mix @ np.array(u_eixos)).tolist()        # (4,) diferencial por motor
        col = min(max(float(acelerador), 0.0), 1.0)
        span = max(d0, d1, d2, d3) - min(d0, d1, d2, d3)
        idle = self.idle
        faixa = 1.0 - idle
        if span > faixa:                                      # o diferencial não cabe: escala-o
            k = faixa / span
            d0, d1, d2, d3 = d0 * k, d1 * k, d2 * k, d3 * k
        u0, u1, u2, u3 = col + d0, col + d1, col + d2, col + d3
        teto = max(u0, u1, u2, u3)
        if teto > 1.0:                                        # airmode: desloca o coletivo para baixo
            k = teto - 1.0
            u0, u1, u2, u3 = u0 - k, u1 - k, u2 - k, u3 - k
        piso = min(u0, u1, u2, u3)
        if piso < idle:                                       # ... ou para cima (nunca abaixo do idle)
            k = idle - piso
            u0, u1, u2, u3 = u0 + k, u1 + k, u2 + k, u3 + k
        saida = []
        for u in (u0, u1, u2, u3):
            u = u if (u > idle or _nan(u)) else idle           # np.maximum(u, idle)
            saida.append(u if (u < 1.0 or _nan(u)) else 1.0)   # np.minimum(u, 1.0)
        self.saida = np.array(saida)
        return self.saida
