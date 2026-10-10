"""lab.drone_rpi.propulsao — ESC + 4 motores brushless + hélices: a dinâmica REAL dos rotores.

Por rotor i (modelo DC equivalente do BLDC com comutação de 120°, corrente quase-estática porque
L/R ≈ 0,1–0,5 ms ≪ τ mecânico ≈ 20–60 ms):

    V_m  = d·V_bus                                (ESC: ciclo útil d ∈ [0, 1] sobre o barramento)
    I    = (V_m − K_e·ω)/R                        (R = R_motor + R_ESC/cabos; I < 0 = travagem)
    J·ω̇ = K_t·I − Q₀(ω) − κ_Q·kq·ω²              (Q₀ = perdas em vazio; κ_Q = correção aerodinâmica)
    T    = κ_T·kf·ω²                              (empuxo; κ_T = solo/inflow/VRS — ver aero.py)
    I_bus = d·I/η_ESC   (motorizando)   ·   d·I·η_ESC   (regenerando)

O ESC armado com PWM complementar ("damped light" — BLHeli_S/Bluejay/AM32 por omissão) deixa I < 0:
o motor TRAVA o rotor quando o comando desce (é o que torna a descida rápida). Desarmado, a ponte
abre e o rotor só abranda pelo arrasto das pás e pelas perdas em vazio (roda livre).

Daqui saem, sem parâmetros extra, o atraso de subida/descida (τ ≈ J/(K_t²/R + 2·kq·ω)), o teto de
rotação ω_max(V) que DECAI com a bateria e a corrente que a bateria realmente fornece.

Integração: Euler semi-implícito em ω (linearização de f(ω) no passo) — estável para qualquer dt
de física (τ/dt ≈ 10–30 a 500 Hz) e exato no regime estacionário.
"""
from __future__ import annotations

import numpy as np

from .componentes import Hardware


def quantiza_dshot(acelerador, bits: int = 11) -> np.ndarray:
    """Acelerador [0, 1] → valor DShot. DShot reserva 0..47 para comandos: o acelerador usa 48..2047
    (2000 níveis com bits=11). 0 continua 0 (motor parado). Devolve o acelerador QUANTIZADO em [0, 1]."""
    u = np.minimum(np.maximum(np.asarray(acelerador, dtype=float), 0.0), 1.0)
    if bits <= 0:
        return u
    niveis = 2 ** bits - 48                       # 2000 para DShot11
    q = np.round(u * (niveis - 1)) / (niveis - 1)
    return np.where(u > 0.0, q, 0.0)


class Propulsao:
    """Os 4 rotores (vetorizado). Parâmetros por rotor permitem DR (dispersão de fabrico motor a motor)."""

    def __init__(self, hw: Hardware):
        self.hw = hw
        self.n = 4
        self.giro = hw.GIRO.copy()
        self.dshot_bits = hw.esc.dshot_bits
        self.travagem = hw.esc.travagem_ativa
        self.aplicar_escalas()
        self.reiniciar()

    # ------------------------------------------------------------------ parâmetros (com DR)
    def aplicar_escalas(self, kf=1.0, kq=1.0, j=1.0, r=1.0, kv=1.0, i0=1.0, eta=1.0) -> None:
        """(Re)define os parâmetros físicos multiplicados por escalas (escalar ou (4,)) — domain randomization."""
        hw = self.hw
        um = np.ones(self.n)
        self.kf = hw.kf * um * kf
        self.kq = hw.kq * um * kq
        self.j = hw.j_rotor * um * j
        self.r = hw.r_motor * um * r
        self.ke = hw.motor.ke / (um * kv)            # KV maior ⇒ K_e menor
        self.kt = self.ke.copy()
        self.i0 = hw.motor.i0 * um * i0
        self.omega0 = hw.omega0 * um
        self.eta = np.clip(hw.esc.eficiencia * um * eta, 0.5, 1.0)

    # ------------------------------------------------------------------ estado
    def reiniciar(self, omega=None) -> None:
        """Rotores parados (ou em `omega`), ESC desarmado, ciclo útil 0."""
        self.omega = np.zeros(self.n) if omega is None else np.asarray(omega, dtype=float).reshape(self.n).copy()
        self.omega_dot = np.zeros(self.n)
        self.duty = np.zeros(self.n)
        self.acelerador = np.zeros(self.n)
        self.armado = False
        self.i_fase = np.zeros(self.n)
        self.i_bus = np.zeros(self.n)
        self.empuxo = np.zeros(self.n)
        self.q_aero = np.zeros(self.n)

    def armar(self, armado: bool = True) -> None:
        self.armado = bool(armado)
        if not self.armado:
            self.duty[:] = 0.0

    def definir_acelerador(self, acelerador) -> np.ndarray:
        """Acelerador por motor [0, 1] (o que o FC manda por DShot) → quantizado → ciclo útil EFETIVO do ESC
        (curva calibrada na tabela do fabricante, `Hardware.acelerador_para_duty`)."""
        if not self.armado:
            self.duty = np.zeros(self.n)
            return self.duty
        self.acelerador = quantiza_dshot(acelerador, self.dshot_bits)
        u, d = self.hw.curva_esc
        self.duty = np.where(self.acelerador > 0.0, np.interp(self.acelerador, u, d), 0.0)
        return self.duty

    # ------------------------------------------------------------------ elétrico
    def _corrente_fase(self, v_bus: float, omega: np.ndarray) -> np.ndarray:
        if not self.armado:
            return np.zeros(self.n)
        i = (self.duty * v_bus - self.ke * omega) / self.r
        return i if self.travagem else np.maximum(i, 0.0)

    def corrente_bus(self, v_bus: float) -> tuple[float, float]:
        """Corrente total que os 4 ESC puxam do barramento à tensão `v_bus` e a derivada dI/dV
        (para o Newton da tensão do barramento — ver `Planta`)."""
        i = self._corrente_fase(v_bus, self.omega)
        motorizando = self.duty * i >= 0.0
        fator = np.where(motorizando, 1.0 / self.eta, self.eta)
        i_bus = self.duty * i * fator
        if not self.armado:
            return 0.0, 0.0
        ativo = i > 0.0 if not self.travagem else np.ones(self.n, dtype=bool)
        di = np.where(ativo, self.duty * self.duty * fator / self.r, 0.0)
        return float(i_bus.sum()), float(di.sum())

    # ------------------------------------------------------------------ mecânico
    def q0(self, omega: np.ndarray) -> np.ndarray:
        return np.where(omega > 0.0, self.kt * self.i0 * (0.5 + 0.5 * omega / self.omega0), 0.0)

    def passo(self, dt: float, v_bus: float, kappa_q=None) -> None:
        """Integra ω durante `dt` com o barramento a `v_bus` (corrente quase-estática)."""
        kq = self.kq if kappa_q is None else self.kq * kappa_q
        w = self.omega
        i = self._corrente_fase(v_bus, w)
        q_em = self.kt * i
        q0 = self.q0(w)
        f = (q_em - q0 - kq * w * w) / self.j
        # derivada de f em ω (Euler semi-implícito): −K_t·K_e/R (se a ponte conduz) − dQ₀/dω − 2·kq·ω
        conduz = (i != 0.0) if not self.travagem else np.full(self.n, self.armado)
        df = (-np.where(conduz, self.kt * self.ke / self.r, 0.0)
              - np.where(w > 0.0, 0.5 * self.kt * self.i0 / self.omega0, 0.0)
              - 2.0 * kq * w) / self.j
        w_novo = np.maximum(w + dt * f / (1.0 - dt * df), 0.0)
        self.omega_dot = (w_novo - w) / dt
        self.omega = w_novo
        # a corrente do passo é a que ACELEROU o rotor (a mesma do Newton do barramento): energia coerente
        self.i_fase = i
        motorizando = self.duty * self.i_fase >= 0.0
        self.i_bus = self.duty * self.i_fase * np.where(motorizando, 1.0 / self.eta, self.eta)
        self.q_aero = kq * w_novo * w_novo

    def empuxos(self, kappa_t=None) -> np.ndarray:
        """Empuxo de cada rotor (N) = κ_T·kf·ω²."""
        t = self.kf * self.omega * self.omega
        self.empuxo = t if kappa_t is None else t * kappa_t
        return self.empuxo

    def binarios_reacao(self) -> np.ndarray:
        """Binário de reação sobre o CORPO, eixo z do rotor (N·m): −s_i·(Q_aero + J·ω̇).

        (O motor faz K_t·I − Q₀ = J·ω̇ + Q_aero no rotor; a reação no estator — preso ao corpo — é o
        simétrico; as perdas Q₀ são internas ao motor e cancelam.)"""
        return -self.giro * (self.q_aero + self.j * self.omega_dot)

    def momento_angular(self) -> np.ndarray:
        """h_i = s_i·J·ω_i (kg·m²/s) ao longo do eixo do rotor — para o efeito giroscópico."""
        return self.giro * self.j * self.omega

    def telemetria(self) -> dict:
        return {"omega": self.omega.copy(), "rpm": self.omega * 60.0 / (2.0 * np.pi),
                "acelerador": self.acelerador.copy(), "duty": self.duty.copy(), "i_fase": self.i_fase.copy(), "i_bus": self.i_bus.copy(),
                "empuxo": self.empuxo.copy(), "armado": self.armado}
