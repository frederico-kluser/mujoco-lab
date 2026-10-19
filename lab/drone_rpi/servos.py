"""lab.drone_rpi.servos — os 8 SERVOS dos braços articulados, como HARDWARE (o que a peça faz sozinha).

Cada junta (`componentes.Junta`) é um DYNAMIXEL com o seu PID de posição interno, o perfil de velocidade e o encoder
absoluto — e, no OMBRO, um sem-fim autobloqueante entre o servo e o braço. A planta chama `passo` a cada passo de
física (500 Hz) com a posição/velocidade REAIS da junta (MuJoCo) e escreve o binário devolvido no atuador da junta;
quem decide os ALVOS (a cinemática dos braços, a mira) é o controlador do experimento, pelo barramento (`definir_alvo`).

SERVO DIRETO (cotovelo) — motor DC + caixa, reta binário-velocidade na saída (a da ficha):
    perfil:   s ← s + clip(alvo − s, ±v_perfil·dt)                    («Profile Velocity», fração de ω₀)
    PWM:      d = clip(kp·(s − q̂) − kd·q̇̂, −1, 1)                       (q̂, q̇̂ = encoder/velocidade QUANTIZADOS; no ombro
                                                                       o servo vê o SEU ângulo θ = N× o do braço)
    binário:  τ = τ_b·(d − q̇/ω₀)                                       (τ_b = bloqueio, ω₀ = vazio: a reta do motor DC)
    corrente: I = I_b·|τ|/τ_b + I_espera                              (τ = K_t·I; potência = V·I no regulador de 24 V)

SERVO + SEM-FIM (ombro) — o servo roda o sem-fim (ângulo θ, na saída do servo); o braço segue θ/N pelo engrenamento
(mola k com folga b e amortecimento c):
    τ_braço = −k·zm(q − θ/N, b/2) − c·(q̇ − θ̇/N)                       (zm = zona morta: a folga)
    a carga que chega ao servo depende do SENTIDO (autobloqueio, λ < φ — `componentes.Junta`):
        o braço opõe-se ao movimento:  τ_s = |τ_braço|/(N·η),  η = tan λ / tan(λ + φ)
        o braço ajuda o movimento:     τ_s = |τ_braço|·tan(φ − λ)/(N·tan λ)   (continua a ter de EMPURRAR)
    θ̇ = ω₀·(d − sinal(d)·τ_s/τ_b); se a carga vence o servo, θ̇ = 0 (o sem-fim SEGURA — sem corrente se d ≈ 0)
    o alvo do servo é N·(alvo + c_i), com c_i a corrigir devagar a folga/deformação pelo encoder EXTERNO do braço.

O que fica de fora (documentado, não escondido): a folga interna de 0,25° dos servos diretos (o encoder mede a SAÍDA,
por isso a cinemática usa o ângulo verdadeiro), o deslizamento do sem-fim por vibração (autobloqueio estático), a
temperatura dos servos e a regeneração de energia a travar.
"""
from __future__ import annotations

import math

import numpy as np

from .componentes import Junta, MecanismoBracos

V_QUANTUM_DXL = 0.229 * 2.0 * math.pi / 60.0     # rad/s — unidade da «Present Velocity» dos DYNAMIXEL X (0,229 rpm)
ACEL_PERFIL = 40.0                               # rad/s² — «Profile Acceleration» no BRAÇO, servo direto (o mastro é leve)
ACEL_PERFIL_SEM_FIM = 3.0                        # rad/s² — idem no ombro: o braço inteiro (~0,07 kg·m²) arranca devagar
KI_CORRECAO_SEM_FIM = 2.0                        # 1/s — correção lenta da folga pelo encoder externo (laço duplo)


def _quantiza(v: float, passo: float) -> float:
    return passo * round(v / passo) if passo > 0.0 else v


def _zona_morta(e: float, meia: float) -> float:
    if e > meia:
        return e - meia
    if e < -meia:
        return e + meia
    return 0.0


class ServoJunta:
    """Um servo de junta (direto ou com sem-fim) — ver o docstring do módulo."""

    def __init__(self, junta: Junta, mecanismo: MecanismoBracos, nome: str, rng: np.random.Generator | None = None):
        self.junta, self.nome = junta, nome
        s = junta.servo
        self.n = float(junta.reducao)
        self.sem_fim = self.n > 1.0
        self.tau_b = s.binario_bloqueio                       # na saída do SERVO
        self.w0 = s.omega_vazio                               # idem
        self.i_b, self.i_espera, self.v = s.corrente_bloqueio, s.corrente_espera, s.tensao
        self.kp, self.kd = mecanismo.kp_duty, mecanismo.kd_duty
        self.eta = junta.eficiencia_subir
        self.f_desc = junta.fator_descer
        self.res_enc = junta.encoder_resolucao                # encoder que mede o BRAÇO (externo no ombro)
        self.res_servo = s.resolucao                          # encoder interno do servo
        self.lim = junta.limites
        self.v_perfil = junta.fracao_velocidade_perfil * self.w0 / self.n     # rad/s no braço
        self.a_perfil = ACEL_PERFIL_SEM_FIM if self.sem_fim else ACEL_PERFIL
        rng = rng if rng is not None else np.random.default_rng(0)
        # erro de linearidade do encoder do braço (fixo por unidade: a «precisão» da ficha), sorteado uma vez
        self.vies_enc = float(rng.uniform(-1.0, 1.0)) * 0.5 * junta.encoder_precisao
        self.ligado = True
        self.reiniciar(0.0)

    # ------------------------------------------------------------------ estado
    def reiniciar(self, q0: float = 0.0) -> None:
        self.alvo = float(q0)
        self.sp = float(q0)                  # setpoint do perfil (braço)
        self.vp = 0.0                        # velocidade do perfil
        self.theta = self.n * float(q0)      # ângulo da saída do servo (sem-fim) — braço = θ/N
        self.theta_d = 0.0
        self.corr = 0.0                      # correção da folga (laço duplo, rad no braço)
        self.duty = 0.0
        self.tau = 0.0                       # binário aplicado à junta (N·m)
        self.corrente = self.i_espera
        self.q_med = float(q0)
        self.qd_med = 0.0
        self.saturado = False
        self.energia_j = 0.0                 # J tirados do barramento de 24 V desde o reset (espera incluída)
        self.curso = 0.0                     # rad percorridos pela junta desde o reset (Σ|Δq| da posição REAL)
        self._q_ant = float(q0)

    def definir_alvo(self, q_alvo: float) -> None:
        """Posição-alvo da junta (rad) — a escrita síncrona do barramento; cortada aos batentes da junta."""
        self.alvo = float(min(max(q_alvo, self.lim[0]), self.lim[1]))

    # ------------------------------------------------------------------ um passo de física
    def passo(self, q: float, qd: float, dt: float) -> float:
        """O `ctrl` do atuador da junta com a posição `q` e a velocidade `qd` REAIS (atualiza encoder, binário e corrente):
        no servo DIRETO é o binário do PWM (N·m, atuador `motor`); no SEM-FIM é o alvo do engrenamento (rad, atuador de
        posição). O binário que a junta recebe fica em `self.tau`."""
        self.curso += abs(q - self._q_ant)                    # quanto a junta rodou (contador; não entra na física)
        self._q_ant = q
        # encoder do braço (quantizado + erro de linearidade) e velocidade lida no barramento
        self.q_med = _quantiza(q + self.vies_enc, self.res_enc)
        self.qd_med = _quantiza(qd, V_QUANTUM_DXL / self.n)
        if not self.ligado:                                   # sem alimentação (brownout): servo solto
            self.duty, self.corrente, self.saturado = 0.0, 0.0, False
            if self.sem_fim:                                  # o sem-fim segura (o servo não roda)
                self.theta_d = 0.0
                self.tau = -self.junta.rigidez * _zona_morta(q - self.theta / self.n, 0.5 * self.junta.folga) \
                    - self.junta.amortecimento * qd
                return self._alvo_engrenamento(q)
            self.tau = 0.0                                    # binário desligado: só o atrito da caixa e a c.e.m.
            return 0.0
        # perfil de velocidade/aceleração do servo (no referencial do braço)
        erro_p = self.alvo - self.sp
        v_des = math.copysign(min(abs(erro_p) / max(dt, 1e-9), self.v_perfil,
                                  math.sqrt(2.0 * self.a_perfil * abs(erro_p))), erro_p)
        dv = max(-self.a_perfil * dt, min(self.a_perfil * dt, v_des - self.vp))
        self.vp += dv
        self.sp += self.vp * dt
        if (self.alvo - self.sp) * erro_p < 0.0:              # não ultrapassa o alvo
            self.sp, self.vp = self.alvo, 0.0
        if self.sem_fim:
            return self._passo_sem_fim(q, qd, dt)
        return self._passo_direto(q, qd)

    def _passo_direto(self, q: float, qd: float) -> float:
        """Devolve o binário do PWM, τ_b·d (atuador `motor`); a parte −τ_b·q̇/ω₀ é o amortecimento da junta no modelo."""
        d = self.kp * (self.sp - self.q_med) - self.kd * self.qd_med
        self.saturado = abs(d) >= 1.0
        d = max(-1.0, min(1.0, d))
        self.duty = d
        tau = self.tau_b * (d - qd / self.w0)                  # o binário TOTAL na saída (telemetria e corrente)
        self.tau = tau
        self.corrente = self.i_b * abs(tau) / self.tau_b + self.i_espera
        return self.tau_b * d

    def _passo_sem_fim(self, q: float, qd: float, dt: float) -> float:
        j = self.junta
        n = self.n
        # laço duplo: o encoder EXTERNO corrige devagar a folga/deformação (o servo só vê o seu encoder interno)
        e_braco = self.sp - self.q_med
        self.corr = max(-0.02, min(0.02, self.corr + KI_CORRECAO_SEM_FIM * e_braco * dt))
        theta_alvo = n * (self.sp + self.corr)
        theta_med = _quantiza(self.theta, self.res_servo)
        d = self.kp * (theta_alvo - theta_med) - self.kd * self.theta_d     # o PID do servo vê o SEU ângulo (N× o do braço)
        self.saturado = abs(d) >= 1.0
        d = max(-1.0, min(1.0, d))
        self.duty = d
        # engrenamento: binário no braço (com folga) e a carga refletida no servo, conforme o sentido
        tau_braco = -j.rigidez * _zona_morta(q - self.theta / n, 0.5 * j.folga) - j.amortecimento * qd
        carga = -tau_braco                                     # o que o braço faz no sem-fim (sentido do braço)
        if abs(d) < 1e-9:
            self.theta_d = 0.0
            tau_s = 0.0
        else:
            sentido = 1.0 if d > 0.0 else -1.0
            if carga * sentido < 0.0:                          # o braço opõe-se ao movimento pedido
                tau_s = abs(carga) / (n * self.eta)
            else:                                              # o braço ajuda — autobloqueio: ainda é preciso empurrar
                tau_s = abs(carga) * self.f_desc / n
            w = self.w0 * (d - sentido * tau_s / self.tau_b)
            if w * sentido <= 0.0:                             # a carga vence o servo: o sem-fim segura
                w, tau_s = 0.0, self.tau_b * abs(d)
            self.theta_d = w
        self.theta += self.theta_d * dt
        self.tau = tau_braco
        self.corrente = self.i_b * min(1.0, tau_s / self.tau_b) + self.i_espera
        return self._alvo_engrenamento(q)

    def _alvo_engrenamento(self, q: float) -> float:
        """Alvo do atuador de POSIÇÃO que faz de engrenamento (kp = rigidez, kv = amortecimento): θ/N deslocado pela
        folga — dentro da folga o alvo é o próprio q (só fica o amortecimento), fora dela a mola vê θ/N ± b/2."""
        ref = self.theta / self.n
        meia = 0.5 * self.junta.folga
        e = q - ref
        if e > meia:
            return ref + meia
        if e < -meia:
            return ref - meia
        return q

    @property
    def potencia(self) -> float:
        """W no barramento de 24 V (antes do regulador)."""
        return self.v * self.corrente


class ServosBracos:
    """Os 8 servos (4 ombros + 4 cotovelos), na ordem `ombro1..4, cotovelo1..4` (a dos nomes do modelo)."""

    def __init__(self, mecanismo: MecanismoBracos, rng: np.random.Generator | None = None):
        self.mec = mecanismo
        rng = rng if rng is not None else np.random.default_rng(0x5E40)
        self.servos = ([ServoJunta(mecanismo.ombro, mecanismo, f"ombro{i + 1}", rng) for i in range(4)]
                       + [ServoJunta(mecanismo.cotovelo, mecanismo, f"cotovelo{i + 1}", rng) for i in range(4)])

    def reiniciar(self, q0=None) -> None:
        q0 = np.zeros(8) if q0 is None else np.asarray(q0, dtype=float)
        for s, q in zip(self.servos, q0, strict=True):
            s.reiniciar(float(q))

    def ligar(self, ligado: bool) -> None:
        for s in self.servos:
            s.ligado = bool(ligado)

    def definir_alvos(self, alvos) -> None:
        for s, a in zip(self.servos, np.asarray(alvos, dtype=float).reshape(8), strict=True):
            s.definir_alvo(float(a))

    def passo(self, q, qd, dt: float) -> list:
        """Os 8 `ctrl` dos atuadores das juntas (ver `ServoJunta.passo`); soma a energia de cada servo (V·I·dt)."""
        ctrl = []
        for s, a, b in zip(self.servos, q, qd, strict=True):
            ctrl.append(s.passo(float(a), float(b), dt))
            s.energia_j += s.v * s.corrente * dt
        return ctrl

    @property
    def medidas(self) -> np.ndarray:
        """As 8 posições MEDIDAS (rad) — encoder externo nos ombros, interno nos cotovelos."""
        return np.array([s.q_med for s in self.servos])

    @property
    def velocidades(self) -> np.ndarray:
        return np.array([s.qd_med for s in self.servos])

    @property
    def alvos(self) -> np.ndarray:
        return np.array([s.alvo for s in self.servos])

    @property
    def binarios(self) -> np.ndarray:
        return np.array([s.tau for s in self.servos])

    @property
    def correntes(self) -> np.ndarray:
        return np.array([s.corrente for s in self.servos])

    def potencia_24v(self) -> float:
        return float(sum(s.potencia for s in self.servos))

    @property
    def energias_wh(self) -> np.ndarray:
        """Wh que cada servo já tirou da BATERIA desde o reset (24 V ÷ rendimento do regulador)."""
        return np.array([s.energia_j for s in self.servos]) / (3600.0 * self.mec.fonte_eficiencia)

    @property
    def cursos(self) -> np.ndarray:
        """rad que cada junta já percorreu desde o reset (Σ|Δq|)."""
        return np.array([s.curso for s in self.servos])

    def potencia_carga_bateria(self) -> float:
        """W na BATERIA acima da espera (a espera já está na potência da eletrónica do build)."""
        p = sum(s.v * max(0.0, s.corrente - s.i_espera) for s in self.servos)
        return p / self.mec.fonte_eficiencia


__all__ = ["ACEL_PERFIL", "ACEL_PERFIL_SEM_FIM", "ServoJunta", "ServosBracos", "V_QUANTUM_DXL"]
