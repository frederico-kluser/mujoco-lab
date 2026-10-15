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

DOIS CAMINHOS, O MESMO RESULTADO (2026-10-12). O estado (ω, ciclo útil, correntes…) e os parâmetros por rotor vivem
em LISTAS de `float`; por fora continuam a ser `ndarray` de 4 (atributos `omega`, `duty`, `kf`…: ler devolve uma
cópia só de leitura, atribuir um vetor novo funciona). Os métodos vetoriais de sempre (`passo`, `corrente_bus`,
`definir_acelerador`…) são a REFERÊNCIA e a API pública; os gémeos `_*_l` fazem a mesma conta em escalares, pela
mesma ordem de operações, e são os que a `Planta` chama a 500 Hz (ver `escalar.py`: a igualdade bit a bit é
verificada no arranque e provada em `experiments/09_drone_hover_rl/bench_treino.py`).
"""
from __future__ import annotations

import math

import numpy as np

from .componentes import Hardware
from .escalar import Tabela

_nan = math.isnan


def quantiza_dshot(acelerador, bits: int = 11) -> np.ndarray:
    """Acelerador [0, 1] → valor DShot. DShot reserva 0..47 para comandos: o acelerador usa 48..2047
    (2000 níveis com bits=11). 0 continua 0 (motor parado). Devolve o acelerador QUANTIZADO em [0, 1]."""
    u = np.minimum(np.maximum(np.asarray(acelerador, dtype=float), 0.0), 1.0)
    if bits <= 0:
        return u
    niveis = 2 ** bits - 48                       # 2000 para DShot11
    q = np.round(u * (niveis - 1)) / (niveis - 1)
    return np.where(u > 0.0, q, 0.0)


class _Vetor4:
    """Atributo (4,) guardado como LISTA de floats em `_<nome>` (o caminho quente lê a lista, sem NumPy).

    Por fora é um `ndarray`: LER devolve uma cópia só de leitura (alterá-la no sítio dá erro em vez de se perder em
    silêncio); ATRIBUIR um vetor (ou um escalar, que se repete pelos 4 rotores) substitui a lista. `parametro=True`
    marca os derivados da propulsão como desatualizados (recalculados na próxima utilização).
    """

    def __init__(self, parametro: bool = False):
        self.parametro = parametro

    def __set_name__(self, dono, nome: str) -> None:
        self.privado = "_" + nome

    def __get__(self, obj, tipo=None):
        if obj is None:
            return self
        a = np.array(getattr(obj, self.privado), dtype=float)
        a.flags.writeable = False
        return a

    def __set__(self, obj, valor) -> None:
        setattr(obj, self.privado, np.broadcast_to(np.asarray(valor, dtype=float), (4,)).tolist())
        if self.parametro:
            obj._const = None


class Propulsao:
    """Os 4 rotores. Parâmetros por rotor permitem DR (dispersão de fabrico motor a motor)."""

    # estado (listas de 4 floats por baixo; ndarray por fora)
    omega = _Vetor4()
    omega_dot = _Vetor4()
    duty = _Vetor4()
    acelerador = _Vetor4()
    i_fase = _Vetor4()
    i_bus = _Vetor4()
    empuxo = _Vetor4()
    q_aero = _Vetor4()
    # parâmetros físicos por rotor (com DR)
    kf = _Vetor4(parametro=True)
    kq = _Vetor4(parametro=True)
    j = _Vetor4(parametro=True)
    r = _Vetor4(parametro=True)
    ke = _Vetor4(parametro=True)
    kt = _Vetor4(parametro=True)
    i0 = _Vetor4(parametro=True)
    omega0 = _Vetor4(parametro=True)
    eta = _Vetor4(parametro=True)

    def __init__(self, hw: Hardware):
        self.hw = hw
        self.n = 4
        self.giro = hw.GIRO.copy()
        self._giro = [float(s) for s in self.giro]
        self.dshot_bits = hw.esc.dshot_bits
        self.travagem = hw.esc.travagem_ativa
        self._const = None
        self._curva = Tabela(*hw.curva_esc)          # acelerador → ciclo útil (curva calibrada do ESC)
        self._duty_dshot = None                      # ciclo útil de cada nível DShot (feita na 1.ª utilização)
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

    def _constantes(self) -> tuple:
        """Constantes por rotor do caminho escalar, derivadas dos parâmetros (mesmas expressões do caminho vetorial,
        calculadas uma vez por `aplicar_escalas` em vez de a cada passo): um tuplo por rotor com
        (K_e, R, η, 1/η, K_t, K_t·I₀, ω₀, K_t·K_e/R, ½·K_t·I₀/ω₀, kq, kf, J, s, s·J)."""
        c = self._const
        if c is None:
            c = self._const = tuple(
                (ke, r, eta, 1.0 / eta, kt, kt * i0, w0, kt * ke / r, 0.5 * kt * i0 / w0, kq, kf, j, s, s * j)
                for ke, r, eta, kt, i0, w0, kq, kf, j, s in zip(self._ke, self._r, self._eta, self._kt, self._i0,
                                                               self._omega0, self._kq, self._kf, self._j,
                                                               self._giro, strict=True))
        return c

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
            self._duty = [0.0, 0.0, 0.0, 0.0]

    def definir_acelerador(self, acelerador) -> np.ndarray:
        """Acelerador por motor [0, 1] (o que o FC manda por DShot) → quantizado → ciclo útil EFETIVO do ESC
        (curva calibrada na tabela do fabricante, `Hardware.acelerador_para_duty`)."""
        if not self.armado:
            self.duty = np.zeros(self.n)
            return self.duty
        self.acelerador = quantiza_dshot(acelerador, self.dshot_bits)
        u, d = self.hw.curva_esc
        acel = self.acelerador
        self.duty = np.where(acel > 0.0, np.interp(acel, u, d), 0.0)
        return self.duty

    def _tabela_dshot(self) -> list:
        """Ciclo útil de CADA nível DShot (k = 0 … níveis − 1 ↔ acelerador k/(níveis − 1)), pela curva do ESC.

        O acelerador quantizado só toma 2000 valores (DShot11): em vez de interpolar a curva 4× por passo de
        física, interpola-se uma vez por nível — a mesma conta, feita à cabeça (nível 0 = motor parado = 0)."""
        n1 = 2 ** self.dshot_bits - 49                # níveis − 1 (1999 no DShot11)
        curva = self._curva
        self._duty_dshot = [0.0] + [curva(k / n1) for k in range(1, n1 + 1)]
        return self._duty_dshot

    def _definir_acelerador_l(self, acelerador: list) -> None:
        """`definir_acelerador` em escalares: corte a [0, 1] → níveis DShot → curva do ESC, motor a motor."""
        if not self.armado:
            self._duty = [0.0, 0.0, 0.0, 0.0]
            return
        acel, duty = [], []
        if self.dshot_bits > 0:
            tab = self._duty_dshot or self._tabela_dshot()
            n1 = len(tab) - 1
            for a in acelerador:
                if a > 0.0:                           # (≤ 0 e NaN → parado, como o np.where(u > 0, q, 0))
                    k = round(min(1.0, a) * n1)                   # nível DShot (np.round: para o par)
                    acel.append(k / n1)
                    duty.append(tab[k])
                else:
                    acel.append(0.0)
                    duty.append(0.0)
        else:                                         # sem quantização: só o corte e a curva
            curva = self._curva
            for a in acelerador:
                u = a if (a > 0.0 or _nan(a)) else 0.0             # np.maximum(a, 0.0)
                u = u if (u < 1.0 or _nan(u)) else 1.0             # np.minimum(u, 1.0)
                acel.append(u)
                duty.append(curva(u) if u > 0.0 else 0.0)
        self._acelerador = acel
        self._duty = duty

    # ------------------------------------------------------------------ elétrico
    def _corrente_fase(self, v_bus: float, omega: np.ndarray) -> np.ndarray:
        if not self.armado:
            return np.zeros(self.n)
        i = (self.duty * v_bus - self.ke * omega) / self.r
        return i if self.travagem else np.maximum(i, 0.0)

    def corrente_bus(self, v_bus: float) -> tuple[float, float]:
        """Corrente total que os 4 ESC puxam do barramento à tensão `v_bus` e a derivada dI/dV
        (para o Newton da tensão do barramento — ver `Planta`)."""
        duty, eta = self.duty, self.eta
        i = self._corrente_fase(v_bus, self.omega)
        motorizando = duty * i >= 0.0
        fator = np.where(motorizando, 1.0 / eta, eta)
        i_bus = duty * i * fator
        if not self.armado:
            return 0.0, 0.0
        ativo = i > 0.0 if not self.travagem else np.ones(self.n, dtype=bool)
        di = np.where(ativo, duty * duty * fator / self.r, 0.0)
        return float(i_bus.sum()), float(di.sum())

    def _corrente_bus_l(self, v: float) -> tuple[float, float]:
        """`corrente_bus` em escalares (o Newton do barramento chama-a 2–4× por passo de física)."""
        if not self.armado:
            return 0.0, 0.0
        c0, c1, c2, c3 = self._const or self._constantes()
        d0, d1, d2, d3 = self._duty
        w0, w1, w2, w3 = self._omega
        r0, r1, r2, r3 = c0[1], c1[1], c2[1], c3[1]
        i0 = (d0 * v - c0[0] * w0) / r0
        i1 = (d1 * v - c1[0] * w1) / r1
        i2 = (d2 * v - c2[0] * w2) / r2
        i3 = (d3 * v - c3[0] * w3) / r3
        trava = self.travagem
        if not trava:                                 # ponte sem travagem: I ≥ 0 (np.maximum(i, 0.0))
            i0 = i0 if (i0 > 0.0 or _nan(i0)) else 0.0
            i1 = i1 if (i1 > 0.0 or _nan(i1)) else 0.0
            i2 = i2 if (i2 > 0.0 or _nan(i2)) else 0.0
            i3 = i3 if (i3 > 0.0 or _nan(i3)) else 0.0
        p0, p1, p2, p3 = d0 * i0, d1 * i1, d2 * i2, d3 * i3
        f0 = c0[3] if p0 >= 0.0 else c0[2]            # motorizando ÷ η · regenerando × η
        f1 = c1[3] if p1 >= 0.0 else c1[2]
        f2 = c2[3] if p2 >= 0.0 else c2[2]
        f3 = c3[3] if p3 >= 0.0 else c3[2]
        g0 = d0 * d0 * f0 / r0 if (trava or i0 > 0.0) else 0.0
        g1 = d1 * d1 * f1 / r1 if (trava or i1 > 0.0) else 0.0
        g2 = d2 * d2 * f2 / r2 if (trava or i2 > 0.0) else 0.0
        g3 = d3 * d3 * f3 / r3 if (trava or i3 > 0.0) else 0.0
        # i_bus.sum() e di.sum(): somas em sequência a partir de +0,0 (como o NumPy)
        return (((0.0 + p0 * f0) + p1 * f1) + p2 * f2) + p3 * f3, (((0.0 + g0) + g1) + g2) + g3

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
        duty, eta = self.duty, self.eta
        motorizando = duty * i >= 0.0
        self.i_bus = duty * i * np.where(motorizando, 1.0 / eta, eta)
        self.q_aero = kq * w_novo * w_novo

    def _passo_l(self, dt: float, v: float, kappa_q, kappa_t) -> tuple[list, list]:
        """`passo` + `empuxos(kappa_t)` + `binarios_reacao()` em escalares (um rotor de cada vez, mesma ordem de
        operações do caminho vetorial). Devolve (empuxo por rotor, binário de reação por rotor)."""
        armado, trava = self.armado, self.travagem
        duty, omega = self._duty, self._omega
        w_n, w_p, i_f, i_b, q_a, emp, reac = [], [], [], [], [], [], []
        for k, (ke, r, eta, inv_eta, kt, kt_i0, om0, ktke_r, dq0, kq, kf, j, s, _sj) in enumerate(
                self._const or self._constantes()):
            d, w = duty[k], omega[k]
            if kappa_q is not None:
                kq = kq * kappa_q[k]
            if armado:
                i = (d * v - ke * w) / r
                if not trava:
                    i = i if (i > 0.0 or _nan(i)) else 0.0
            else:
                i = 0.0
            q0 = kt_i0 * (0.5 + 0.5 * w / om0) if w > 0.0 else 0.0
            f = (kt * i - q0 - kq * w * w) / j
            conduz = armado if trava else i != 0.0
            df = (-(ktke_r if conduz else 0.0) - (dq0 if w > 0.0 else 0.0) - 2.0 * kq * w) / j
            wn = w + dt * f / (1.0 - dt * df)
            wn = wn if (wn > 0.0 or _nan(wn)) else 0.0          # np.maximum(·, 0.0)
            wp = (wn - w) / dt
            p = d * i
            qa = kq * wn * wn
            t = kf * wn * wn
            if kappa_t is not None:
                t = t * kappa_t[k]
            w_n.append(wn)
            w_p.append(wp)
            i_f.append(i)
            i_b.append(p * (inv_eta if p >= 0.0 else eta))
            q_a.append(qa)
            emp.append(t)
            reac.append(-s * (qa + j * wp))
        self._omega, self._omega_dot, self._i_fase, self._i_bus = w_n, w_p, i_f, i_b
        self._q_aero, self._empuxo = q_a, emp
        return emp, reac

    def empuxos(self, kappa_t=None) -> np.ndarray:
        """Empuxo de cada rotor (N) = κ_T·kf·ω²."""
        w = self.omega
        t = self.kf * w * w
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

    def _momento_angular_soma_l(self) -> float:
        """Σ h_i em escalares (`np.sum(momento_angular())`: soma em sequência a partir de +0,0)."""
        c0, c1, c2, c3 = self._const or self._constantes()
        w0, w1, w2, w3 = self._omega
        return (((0.0 + c0[13] * w0) + c1[13] * w1) + c2[13] * w2) + c3[13] * w3

    def telemetria(self) -> dict:
        w = self.omega
        return {"omega": w.copy(), "rpm": w * 60.0 / (2.0 * np.pi),
                "acelerador": self.acelerador.copy(), "duty": self.duty.copy(), "i_fase": self.i_fase.copy(),
                "i_bus": self.i_bus.copy(), "empuxo": self.empuxo.copy(), "armado": self.armado}
