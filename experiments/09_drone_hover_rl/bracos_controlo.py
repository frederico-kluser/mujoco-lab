"""experiments/09_drone_hover_rl/bracos_controlo.py — CONTROLADOR DOS BRAÇOS ARTICULADOS (algoritmo do drone 09).

O corpo do drone (com a arma, o IMU e a câmara) passa a poder ARFAR por cima dos motores: as 8 juntas (ombro + cotovelo
em cada braço, todos os eixos paralelos ao y do corpo) inclinam os motores de τ face ao corpo, e o núcleo de firmware
(interface 4) controla o referencial dos MOTORES — que fica de nível para segurar a posição — enquanto o corpo fica no
ângulo de MIRA. Este módulo decide os 8 alvos dos servos a cada ciclo do barramento (`barramento_hz` do catálogo).

LEI (fórmulas fechadas, sem afinação à mão):

  1. QUEM MEXE O QUÊ (medido: a primeira versão, «os servos seguram o pitch do corpo», divergiu em 2 s — o cotovelo
     roda os mastros, leves, 10× mais depressa do que o empuxo diferencial roda o drone inteiro, e a lei perseguia o
     ângulo que ela própria mudava). Cada atuador fica com a variável que mexe MAIS DEPRESSA:
       · modo `mira` (núcleo de firmware em mira por arfagem, interface 4): o empuxo diferencial segura o pitch do
         CORPO (a arma, θ*_corpo = −elevação) e os servos dão ao empuxo a inclinação longitudinal que a cascata pede:
             τ* = incl_ref = atan2(n̂·ĥ, n̂_z) − θ̂_corpo         (calculado no núcleo, `Saida::incl_ref`)
       · modo `lento` (sem núcleo: o FC Python do treino RL controla o referencial dos motores): os servos levam o
         corpo a θ*_corpo DEVAGAR, abaixo da banda da atitude — τ̇* = K_LENTO·(θ̂_corpo − θ*_corpo).
  2. CINEMÁTICA INVERSA (os 4 rotores no MESMO plano dos motores, como com τ = 0): no referencial dos motores o
     cotovelo do braço i fica à altura cos φ_i·[r_s·sen τ − l₁·sen(q₁ − τ)]; igualar a zero para os 4 dá
         q₁* = τ* + δ(τ*),   δ = asin((r_s/l₁)·sen τ*)        (igual nos 4 braços: eixos paralelos)
         q₂* = τ* − q₁*  = −δ
  3. MACRO-MINI (ombro lento com sem-fim, cotovelo rápido): o ombro persegue só a parte LENTA de q₁* (filtro de 1.ª
     ordem de TAU_OMBRO_S, com zona morta de 1°: parado, o sem-fim segura sem corrente) e o cotovelo corrige JÁ a diferença — q₂ = τ* − q̂₁,i (com o ombro MEDIDO de cada braço). O
     eixo dos motores é τ* em cada instante (à velocidade do cotovelo); quando o ombro chega, q₂ → −δ e o cotovelo
     recupera a amplitude para o transitório seguinte. (Medido: com o ombro a seguir as flutuações de τ, os 4 braços
     — ~0,27 kg·m² somados em torno dos ombros — davam ao corpo pancadas de binário e o pitch oscilava ±2° a 2,8 Hz;
     com o filtro fica dentro do ruído da pairagem com braços travados.)
  4. LIMITES: τ* cortado ao que as juntas alcançam e com taxa máxima (a do cotovelo sob carga); os alvos ficam nos
     batentes do catálogo.

Modos: `mira`, `lento`, `rigido` (todas as juntas a 0 — o drone de sempre, com mastros) e `manual` (τ* direto).
"""
from __future__ import annotations

import math

import numpy as np

MODOS_BRACOS = ("mira", "lento", "rigido", "manual")
K_LENTO = 1.5                   # 1/s — banda do modo `lento` (≪ a da atitude, ~6 Hz): o corpo chega ao pitch em ~2 s
TAU_OMBRO_S = 0.6               # s — o ombro só segue a parte lenta de τ (o cotovelo faz o resto)
ZONA_MORTA_OMBRO = math.radians(1.0)   # o ombro só se mexe para mudanças sustentadas > 1° (o cotovelo absorve as
#                                        pequenas): parado, o sem-fim segura o braço SEM corrente (medido: sem a zona
#                                        morta os ombros traseiros puxavam 0,18 A em pairagem a perseguir flutuações)
FRACAO_TAXA_TAU = 0.32          # da velocidade em vazio do cotovelo: ~100°/s — medido: a 218°/s os servos seguiam os saltos
#                                 de ±20–30° da direção de empuxo pedida quando o coletivo bate no mínimo (pós-recuo a
#                                 mirar para baixo) e o empuxo varria; a ~100°/s seguem a mira e a posição sem esse varrer


def geometria(hw) -> dict:
    """r_s (raio do ombro), l1 (ombro→cotovelo), l_m (mastro: eixo do cotovelo → plano da hélice) — os do modelo."""
    from lab.drone_rpi.modelo import geometria_bracos
    return geometria_bracos(hw)


def delta_ombro(tau: float, r_s: float, l1: float) -> float:
    """δ(τ) = asin((r_s/l₁)·sen τ): o ombro faz τ + δ e o cotovelo −δ (rotores no plano dos motores)."""
    return math.asin(max(-1.0, min(1.0, (r_s / l1) * math.sin(tau))))


def cinematica_inversa(tau: float, r_s: float, l1: float) -> tuple[float, float]:
    """(q₁*, q₂*) de regime para a inclinação τ dos motores face ao corpo."""
    d = delta_ombro(tau, r_s, l1)
    return tau + d, -d


def cinematica_direta(hw, q: np.ndarray) -> dict:
    """Posição dos 4 rotores (centro da hélice) e eixo de cada motor no referencial do CORPO, para as 8 juntas `q`
    (ordem ombro1..4, cotovelo1..4) — a mesma geometria do MJCF (testada contra o MuJoCo em `teste_bracos.py`).

    p_i = S_i + R_y(q₁)·(l₁·u_i) + R_y(q₁ + q₂)·(0, 0, l_m),   eixo_i = R_y(q₁ + q₂)·ẑ
    """
    g = geometria(hw)
    out_p, out_e = [], []
    for i, (x, y) in enumerate(hw.pos_rotores):
        ang = math.atan2(y, x)
        u = np.array([math.cos(ang), math.sin(ang), 0.0])
        s = g["r_s"] * u
        q1, q2 = float(q[i]), float(q[4 + i])
        out_p.append(s + _ry(q1) @ (g["l1"] * u) + _ry(q1 + q2) @ np.array([0.0, 0.0, g["l_m"]]))
        out_e.append(_ry(q1 + q2) @ np.array([0.0, 0.0, 1.0]))
    return {"rotores": np.array(out_p), "eixos": np.array(out_e)}


def _ry(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


class ControladorBracos:
    """Os 8 alvos dos servos a partir do pitch pretendido para o corpo — ver o docstring do módulo."""

    def __init__(self, hw, dt_fisica: float):
        mec = hw.bracos
        if mec is None:
            raise ValueError(f"o build '{hw.nome}' não tem braços articulados")
        self.hw = hw
        g = geometria(hw)
        self.r_s, self.l1 = g["r_s"], g["l1"]
        self.lim_o = mec.ombro.limites
        self.lim_c = mec.cotovelo.limites
        self.decimacao = max(1, round(1.0 / (mec.barramento_hz * dt_fisica)))
        self.dt_ciclo = self.decimacao * dt_fisica
        self.taxa_tau = FRACAO_TAXA_TAU * mec.cotovelo.omega_vazio_saida
        # τ alcançável: o cotovelo sozinho (o ombro pode estar parado) dá ±lim_c; com o ombro, até lim_o + lim_c
        self.tau_max = min(abs(self.lim_c[0]), abs(self.lim_c[1])) + min(abs(self.lim_o[0]), abs(self.lim_o[1]))
        self.modo = "mira"
        self.reiniciar()

    def reiniciar(self) -> None:
        self.pitch_corpo_alvo = 0.0
        self.tau_manual = 0.0
        self.tau_cmd = 0.0
        self.tau_lento = 0.0
        self.q1_alvo = 0.0
        self.contador = 0
        self.alvos = np.zeros(8)

    # `fonte_tau`: função sem argumentos que devolve o τ pedido pelo núcleo de firmware (`Saida::incl_ref`) — ligada pelo
    # `NucleoClassico` quando instala o núcleo; sem ela o modo `mira` faz o mesmo que o `lento`
    fonte_tau = None

    def definir_modo(self, modo: str) -> None:
        if modo not in MODOS_BRACOS:
            raise ValueError(f"modo dos braços desconhecido: {modo!r} — aceites: {MODOS_BRACOS}")
        self.modo = modo

    def definir_pitch_corpo(self, pitch_rad: float) -> None:
        """θ*_corpo (rad, ZYX: + = nariz para BAIXO). Mirar para cima e de ε rad = `definir_pitch_corpo(−ε)`."""
        lim = self.tau_max - 0.05
        self.pitch_corpo_alvo = float(max(-lim, min(lim, pitch_rad)))

    def passo(self, servos, pitch_corpo_est: float) -> bool:
        """Um passo de FÍSICA: a cada `decimacao` passos (o ciclo do barramento) escreve os 8 alvos em `servos`
        (`ServosBracos`). Devolve True quando escreveu. `pitch_corpo_est` = θ̂_corpo do estimador de bordo."""
        self.contador += 1
        if self.contador < self.decimacao:
            return False
        self.contador = 0
        q_med = servos.medidas
        if self.modo == "rigido":
            self.tau_cmd = 0.0
            self.alvos = np.zeros(8)
            servos.definir_alvos(self.alvos)
            return True
        if self.modo == "manual":
            tau_des = self.tau_manual
        elif self.modo == "mira" and self.fonte_tau is not None:
            tau_des = float(self.fonte_tau())
        else:                                                # `lento` (ou `mira` sem núcleo)
            tau_des = self.tau_cmd + K_LENTO * (float(pitch_corpo_est) - self.pitch_corpo_alvo) * self.dt_ciclo
        tau_des = max(-self.tau_max, min(self.tau_max, tau_des))
        passo_max = self.taxa_tau * self.dt_ciclo
        self.tau_cmd += max(-passo_max, min(passo_max, tau_des - self.tau_cmd))
        self.tau_lento += (self.dt_ciclo / (TAU_OMBRO_S + self.dt_ciclo)) * (self.tau_cmd - self.tau_lento)
        q1_ideal, _ = cinematica_inversa(self.tau_lento, self.r_s, self.l1)
        if abs(q1_ideal - self.q1_alvo) > ZONA_MORTA_OMBRO:
            self.q1_alvo = q1_ideal
        q1_alvo = max(self.lim_o[0], min(self.lim_o[1], self.q1_alvo))
        alvos = np.empty(8)
        alvos[:4] = q1_alvo
        for i in range(4):                                   # o cotovelo fecha JÁ o que o ombro (medido) ainda não fez
            alvos[4 + i] = max(self.lim_c[0], min(self.lim_c[1], self.tau_cmd - float(q_med[i])))
        self.alvos = alvos
        servos.definir_alvos(alvos)
        return True

    def estado(self) -> dict:
        return {"modo": self.modo, "pitch_corpo_alvo_graus": round(math.degrees(self.pitch_corpo_alvo), 3),
                "tau_cmd_graus": round(math.degrees(self.tau_cmd), 3),
                "alvos_graus": [round(math.degrees(float(v)), 3) for v in self.alvos]}


__all__ = ["MODOS_BRACOS", "ControladorBracos", "cinematica_direta", "cinematica_inversa", "delta_ombro", "geometria"]
