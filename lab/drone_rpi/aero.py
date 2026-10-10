"""lab.drone_rpi.aero — a aerodinâmica que o MuJoCo NÃO modela, por rotor e por passo de física.

O MuJoCo dá o arrasto do CORPO (modelo de fluido por caixa de inércia, ligado por `density/viscosity`) e o
vento (`opt.wind`); o empuxo de um `motor` é idêntico a qualquer altura, densidade e velocidade (verificado
no Q8 #20). Aqui entram, todos DESLIGÁVEIS por flag (com tudo desligado o resultado é bit-idêntico à
"aerodinâmica base" `T = kf·ω²`):

1. EFEITO DE SOLO (multirrotor) — Sanchez-Cuevas, Heredia & Ollero, Int. J. Aerospace Eng. 2017
   (citado em par.nsf.gov/servlets/purl/10181219, eq. 7), extensão do modelo de imagem de
   Cheeseman & Bennett (1955) aos rotores vizinhos e à sustentação do corpo:
       T_IGE/T_OGE = [1 − (R/4z)² − R²·z/√(d²+4z²)³ − (R²/2)·z/√(2d²+4z²)³ − 2R²·z·K_b/√(b²+4z²)³]⁻¹
   z = altura do rotor ao solo (raio para baixo, `mj_ray`, por rotor), d = distância entre eixos
   VIZINHOS, b = distância entre eixos OPOSTOS (wheelbase), K_b = 2 (sustentação do corpo, empírico).
   Teto 1,6 (a expressão diverge quando o rotor encosta ao solo, fora do domínio validado).
2. EMPUXO vs INFLOW AXIAL (subida/descida) — teoria combinada elemento de pá + quantidade de movimento
   (BEMT, pá retangular, inflow uniforme): C_T = (σa/2)·(θ/3 − λ/2) e C_T = 2·(λ − λ_c)·λ ⇒ λ fechado;
   θ é calibrado para reproduzir o C_T estático (kf) em pairagem e σa = 0,45 é AJUSTADO à curva C_T(J)
   publicada da APC 15×5.5MR (κ_T = 0,707 vs 0,709 a J = 0,19; 0,503 vs 0,492 a J = 0,30; o empuxo cruza
   zero perto de J ≈ 0,5, como na APC). À MESMA rotação, SUBIR reduz o empuxo e DESCER aumenta-o (até ao
   VRS). C_Q = C_Q,perfil + λ·C_T (a potência induzida acompanha).
3. VORTEX RING STATE (descida no próprio rasto) — empírico: perda `k_vrs·exp(−((x−1)/0,35)²)` com
   x = v_descida/v_h, v_h = √(T/(2ρA)) (perda desprezável abaixo de ≈0,5·v_h, máxima a v_h) + flutuação
   aleatória do empuxo (AR(1), τ = 0,1 s) proporcional ao mesmo envelope. k_vrs = 0,25.
4. ARRASTO DE ROTOR (força-H + flapping) — força no PLANO do rotor, linear na velocidade do ar e na
   rotação (Forster 2015 / gym-pybullet-drones): F_i = −c_d·ω_i·v_⊥,i, aplicada NO ROTOR (gera também
   momento). c_d calibrado para dar, em pairagem, a desaceleração linear a = −d·v com d = 0,30 s⁻¹ (faixa
   identificada 0,26–0,43 s⁻¹, Faessler & Franchi arXiv 1712.02402). Anisotropia d_x ≠ d_y opcional.
5. DOWNLOAD (interferência rotor–estrutura): o rasto que bate nos braços/corpo puxa a estrutura para baixo
   — fração `frame.perda_download` do empuxo (NASA Ames, Russell et al. 2016: ~5 % com braços finos a ~15 %
   com braços largos). Entra na pairagem do catálogo e na força aplicada pela Planta.
6. GIROSCÓPICO + REAÇÃO À ACELERAÇÃO DO ROTOR — τ = −Ω × Σ h_i (h_i = s_i·J·ω_i·ẑ_corpo) e −s_i·J·ω̇_i
   (este último já sai em `Propulsao.binarios_reacao`).

Tudo é escrito pela `Planta` em `data.ctrl` (empuxo/reação por rotor) e `data.xfrc_applied` (arrasto de
rotor + giroscópico), sempre antes do `mj_step2` — a física continua toda no `mj_step`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .componentes import RHO_AR, Hardware

SIGMA_A = 0.45          # solidez × declive de sustentação — AJUSTADO à curva C_T(J) da APC 15×5.5MR
                        # (PER3, J ≤ 0,3: RMS 0,0065; σ ≈ 0,08 · a ≈ 5,7 /rad numa bipá de 15″)
KB_CORPO = 2.0          # Sanchez-Cuevas 2017 — coeficiente empírico de sustentação do corpo
GANHO_SOLO_MAX = 1.6
D_ARRASTO = 0.30        # s⁻¹ — arrasto de rotor em pairagem (Faessler & Franchi: 0,26–0,43)
K_VRS = 0.25
VRS_LARGURA = 0.35
VRS_TAU = 0.10          # s — correlação da flutuação de empuxo no VRS
VRS_SIGMA = 0.10        # desvio da flutuação no pico do envelope (fração do empuxo)
OMEGA_MIN_INFLOW = 0.05  # fração de ω_pairagem abaixo da qual a correção de inflow não se aplica


@dataclass
class FlagsAero:
    solo: bool = True
    inflow: bool = True
    vrs: bool = True
    arrasto_rotor: bool = True
    giroscopico: bool = True
    download: bool = True       # perda de empuxo do rasto na estrutura (frame.perda_download; NASA 5–15 %)

    @classmethod
    def base(cls) -> FlagsAero:
        """"Aerodinâmica base": T = kf·ω² puro (nada desta camada)."""
        return cls(False, False, False, False, False, False)


def ganho_solo(z, raio: float, d_vizinhos: float, b_opostos: float, kb: float = KB_CORPO) -> np.ndarray:
    """T_IGE/T_OGE de Sanchez-Cuevas 2017 (eq. no docstring) para alturas `z` (m) ao solo (≥ 0)."""
    z = np.maximum(np.asarray(z, dtype=float), 1e-6)
    r2 = raio * raio
    s = ((raio / (4.0 * z)) ** 2
         + r2 * z / np.sqrt((d_vizinhos ** 2 + 4.0 * z * z) ** 3)
         + 0.5 * r2 * z / np.sqrt((2.0 * d_vizinhos ** 2 + 4.0 * z * z) ** 3)
         + 2.0 * r2 * z * kb / np.sqrt((b_opostos ** 2 + 4.0 * z * z) ** 3))
    g = np.where(s < 1.0 - 1.0 / GANHO_SOLO_MAX, 1.0 / np.maximum(1.0 - s, 1e-9), GANHO_SOLO_MAX)
    return np.minimum(g, GANHO_SOLO_MAX)


class Aerodinamica:
    """Fatores κ_T/κ_Q por rotor e forças/binários extra (arrasto de rotor, giroscópico)."""

    def __init__(self, hw: Hardware, flags: FlagsAero | None = None, d_xy=(D_ARRASTO, D_ARRASTO)):
        self.hw = hw
        self.flags = flags if flags is not None else FlagsAero()
        h = hw.helice
        self.raio = h.raio
        self.area = h.area
        self.b_opostos = hw.frame.wheelbase
        self.d_vizinhos = hw.frame.wheelbase / math.sqrt(2.0)
        # BEMT: C_T estático (convenção de helicóptero, T = C_T·ρ·A·(ΩR)²) a partir de kf
        self.ct0 = hw.kf / (RHO_AR * math.pi * self.raio ** 4)
        self.cq0 = hw.kq / (RHO_AR * math.pi * self.raio ** 5)
        self.lam0 = math.sqrt(self.ct0 / 2.0)
        self.theta = 3.0 * (2.0 * self.ct0 / SIGMA_A + self.lam0 / 2.0)
        self.cq_perfil = max(self.cq0 - self.lam0 * self.ct0, 0.0)
        self.kb = KB_CORPO
        self.k_vrs = K_VRS
        self.escala_solo = 1.0               # DR: força do efeito de solo
        # arrasto de rotor: c_d tal que, em pairagem nominal, Σ F/m = −d·v
        p = hw.ponto_pairagem(hw.bateria.v_nominal)
        self.omega_h = p["omega"]
        self.definir_arrasto(*d_xy)
        self._vrs_ruido = np.zeros(4)

    def definir_arrasto(self, d_x: float, d_y: float) -> None:
        """Arrasto de rotor (s⁻¹) ao longo de x e y do CORPO, em pairagem (c_d por rotor)."""
        m = self.hw.massa_total
        self.d_xy = (float(d_x), float(d_y))
        self.cd = np.array([d_x, d_y]) * m / (4.0 * self.omega_h)   # N/((rad/s)·(m/s)) por rotor

    # ------------------------------------------------------------------ fatores de empuxo/binário
    def fator_inflow(self, v_axial, omega) -> tuple[np.ndarray, np.ndarray]:
        """(κ_T, κ_Q) do BEMT para a velocidade axial do ar `v_axial` (m/s, + = rotor a SUBIR)."""
        w = np.asarray(omega, dtype=float)
        v = np.asarray(v_axial, dtype=float)
        ok = w > OMEGA_MIN_INFLOW * self.omega_h
        lam_c = np.where(ok, v / np.maximum(w * self.raio, 1e-6), 0.0)
        a = SIGMA_A * self.theta / 6.0
        b = SIGMA_A / 4.0
        bb = b - 2.0 * lam_c
        lam = (-bb + np.sqrt(bb * bb + 8.0 * a)) / 4.0
        ct = a - b * lam
        kt = np.minimum(np.maximum(ct / self.ct0, 0.0), 1.3)
        cq = self.cq_perfil + lam * np.maximum(ct, 0.0)
        kq = np.minimum(np.maximum(cq / self.cq0, 0.1), 1.5)
        return np.where(ok, kt, 1.0), np.where(ok, kq, 1.0)

    def fator_vrs(self, v_axial, empuxo, dt: float, rng) -> np.ndarray:
        """Perda (e flutuação) de empuxo no vortex ring state, por rotor."""
        v_h = np.sqrt(np.maximum(empuxo, 0.0) / (2.0 * RHO_AR * self.area))
        x = np.where(v_h > 1e-6, -np.asarray(v_axial) / np.maximum(v_h, 1e-6), 0.0)
        env = np.where(x > 0.0, np.exp(-((x - 1.0) / VRS_LARGURA) ** 2), 0.0)
        if rng is not None:
            a = math.exp(-dt / VRS_TAU)
            self._vrs_ruido = a * self._vrs_ruido + math.sqrt(1.0 - a * a) * rng.normal(0.0, 1.0, 4)
        return np.minimum(np.maximum(1.0 - self.k_vrs * env + VRS_SIGMA * env * self._vrs_ruido, 0.3), 1.2)

    def fatores(self, altura, v_axial, omega, dt: float, rng=None) -> tuple[np.ndarray, np.ndarray, dict]:
        """κ_T (4,), κ_Q (4,) e o detalhe de cada efeito, para alturas/velocidades axiais/rotações dadas.

        Caminho QUENTE (500 Hz × 4 rotores): as mesmas fórmulas de `ganho_solo`/`fator_inflow`/`fator_vrs`
        em escalares Python (arrays de 4 em NumPy custam ~5× mais aqui); os testes comparam os dois caminhos.
        """
        f = self.flags
        if not (f.solo or f.inflow or f.vrs):
            um = np.ones(4)
            return um, um, {"solo": um, "inflow": um, "vrs": um}
        r, r2 = self.raio, self.raio * self.raio
        d2, b2, kb, esc = self.d_vizinhos ** 2, self.b_opostos ** 2, self.kb, self.escala_solo
        sa, th6, b4 = SIGMA_A, SIGMA_A * self.theta / 6.0, SIGMA_A / 4.0
        ct0, cq0, cqp = self.ct0, self.cq0, self.cq_perfil
        w_min = OMEGA_MIN_INFLOW * self.omega_h
        kf, area2 = self.hw.kf, 2.0 * RHO_AR * self.area
        if f.vrs and rng is not None:
            a = math.exp(-dt / VRS_TAU)
            self._vrs_ruido = a * self._vrs_ruido + math.sqrt(1.0 - a * a) * rng.normal(0.0, 1.0, 4)
        g_s, k_ti, k_qi, k_v = [1.0] * 4, [1.0] * 4, [1.0] * 4, [1.0] * 4
        for i in range(4):
            w = float(omega[i])
            va = float(v_axial[i])
            if f.solo:
                z = max(float(altura[i]), 1e-6)
                z2 = 4.0 * z * z
                s = ((r / (4.0 * z)) ** 2 + r2 * z / (d2 + z2) ** 1.5 + 0.5 * r2 * z / (2.0 * d2 + z2) ** 1.5
                     + 2.0 * r2 * z * kb / (b2 + z2) ** 1.5)
                g = min(1.0 / (1.0 - s), GANHO_SOLO_MAX) if s < 1.0 - 1.0 / GANHO_SOLO_MAX else GANHO_SOLO_MAX
                g_s[i] = 1.0 + (g - 1.0) * esc
            if f.inflow and w > w_min:
                lam_c = va / (w * r)
                bb = b4 - 2.0 * lam_c
                lam = (-bb + math.sqrt(bb * bb + 8.0 * th6)) / 4.0
                ct = th6 - b4 * lam
                k_ti[i] = min(max(ct / ct0, 0.0), 1.3)
                k_qi[i] = min(max((cqp + lam * max(ct, 0.0)) / cq0, 0.1), 1.5)
            if f.vrs:
                t_est = kf * w * w * g_s[i] * k_ti[i]
                v_h = math.sqrt(max(t_est, 0.0) / area2)
                x = -va / v_h if v_h > 1e-6 else 0.0
                env = math.exp(-((x - 1.0) / VRS_LARGURA) ** 2) if x > 0.0 else 0.0
                k_v[i] = min(max(1.0 - self.k_vrs * env + VRS_SIGMA * env * float(self._vrs_ruido[i]), 0.3), 1.2)
        g_solo, k_t_in, k_q_in, k_vrs = np.array(g_s), np.array(k_ti), np.array(k_qi), np.array(k_v)
        del sa
        return g_solo * k_t_in * k_vrs, k_q_in, {"solo": g_solo, "inflow": k_t_in, "vrs": k_vrs}

    # ------------------------------------------------------------------ forças extra (mundo)
    def forca_arrasto(self, v_ar_rotores: np.ndarray, eixos_corpo: np.ndarray, omega) -> np.ndarray:
        """(4, 3) forças de arrasto de rotor (mundo, N): −c_d·ω·v_⊥ projetada nos eixos x/y do CORPO."""
        if not self.flags.arrasto_rotor:
            return np.zeros((4, 3))
        ex, ey, _ez = eixos_corpo                                  # colunas da matriz do corpo
        vx = v_ar_rotores @ ex
        vy = v_ar_rotores @ ey
        w = np.asarray(omega)
        fx = -self.cd[0] * w * vx
        fy = -self.cd[1] * w * vy
        return np.outer(fx, ex) + np.outer(fy, ey)

    def binario_giroscopico(self, omega_corpo_mundo: np.ndarray, h_rotores, ez: np.ndarray) -> np.ndarray:
        """τ = −Ω × (Σ h_i)·ẑ_corpo (mundo, N·m)."""
        if not self.flags.giroscopico:
            return np.zeros(3)
        hs = float(np.sum(h_rotores))
        w = omega_corpo_mundo
        return -hs * np.array([w[1] * ez[2] - w[2] * ez[1], w[2] * ez[0] - w[0] * ez[2],
                               w[0] * ez[1] - w[1] * ez[0]])
