"""lab.drone_rpi.componentes — catálogo de componentes REAIS do drone do dono e derivação física.

FONTE DE VERDADE (versionada, com as fontes de cada número):
  · `models/drone_rpi/componentes.json` — peças reais (motores com as tabelas de ensaio do fabricante,
    hélices, células e packs, frames, ESC, eletrónica de bordo, sensores);
  · `models/drone_rpi/builds.json`      — combinações nomeadas e qual está ATIVA (`"ativo"`).
A memória CoALA guarda uma cópia pesquisável (`experiments/09_drone_hover_rl/hardware.py coala`).

Trocar motor/bateria/hélice = escolher outro build (ou montar um com `hardware.py montar`). Tudo o resto
é DERIVADO aqui por fórmulas a partir dos dados do fabricante — nada é afinado à mão:

  · massa total = soma do orçamento (frame + 4 motores + 4 hélices + ESC + pack + eletrónica + sensores);
  · geometria em X a partir do wheelbase (distância diagonal motor-motor);
  · hélice: `kf = C_T·ρ·D⁴/(4π²)`, `kq = C_P·ρ·D⁵/(8π³)` (convenção UIUC, n em rot/s) — ou, quando o
    catálogo traz a TABELA DE ENSAIO do fabricante para este motor+hélice, mínimos quadrados sobre ela
    (`T = kf·ω²` e `Q = K_t·(I_motor − I₀(ω)) = kq·ω²`): dado medido vence coeficiente genérico;
  · motor BLDC (modelo DC equivalente): `K_e = K_t = 60/(2π·KV)`, `I = (d·V − K_e·ω)/R`, perdas em
    vazio `Q₀(ω) = K_t·I₀·(½ + ½·ω/ω₀)` (½ fricção/histerese + ½ correntes de Foucault, ω₀ = KV·V_ensaio);
  · regime estacionário: `K_t·(d·V − K_e·ω)/R − Q₀(ω) − kq·ω² = 0` (quadrática fechada em ω) ⇒
    `ω_max(V)` e `T_max(V) = kf·ω_max²` DECAEM com a tensão da bateria (o "limite de rotação" do plano);
  · inércia do rotor `J = J_hélice + J_sino`, `J_hélice ≈ 0,2·m·R²` (pás afiladas) e `J_sino = m_sino·r²`
    (anel; `m_sino ≈ 0,35·m_motor`) — ESTIMATIVA documentada (a confirmar por SysID).
"""
from __future__ import annotations

import copy
import json
import math
import pathlib
from dataclasses import dataclass, field

import numpy as np

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PASTA_MODELO = RAIZ / "models" / "drone_rpi"
CATALOGO_JSON = PASTA_MODELO / "componentes.json"
BUILDS_JSON = PASTA_MODELO / "builds.json"

RHO_AR = 1.225            # kg/m³ — ar ao nível do mar a 15 °C (o MuJoCo usa o `density` do modelo: o mesmo)
GRAVIDADE = 9.81          # m/s² — a do MuJoCo (opt.gravity = [0, 0, −9.81])
POL = 0.0254              # m por polegada
RPM_PARA_RAD = 2.0 * math.pi / 60.0

# Curvas OCV (tensão de circuito aberto POR CÉLULA, em repouso) × SoC, por química — o OCV da célula
# usada pode substituir estas (`curva_ocv` explícita na célula do catálogo).
CURVAS_OCV = {
    # LiPo (LiCoO₂/NMC de pacote "soft"): tabela de repouso amplamente publicada (ver componentes.json →
    # fontes da química); 0 % = 3,27 V, plateau 3,75–3,85 V.
    "lipo": ([0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
              0.75, 0.80, 0.85, 0.90, 0.95, 1.00],
             [3.27, 3.61, 3.69, 3.71, 3.73, 3.75, 3.77, 3.79, 3.80, 3.82, 3.84, 3.85, 3.87, 3.91, 3.95,
              3.98, 4.02, 4.08, 4.11, 4.15, 4.20]),
    # Li-ion NMC/NCA de alta energia (21700/18650): tabela do plano (§2.2, UDPOWER) com a cauda baixa das
    # células cilíndricas (que descem até 2,5 V sob carga) — 0 % = 3,00 V em repouso.
    "li-ion": ([0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00],
               [3.00, 3.30, 3.45, 3.55, 3.65, 3.70, 3.75, 3.80, 3.85, 3.95, 4.05, 4.20]),
}
# tensão de POUSO por célula, sob carga (a autonomia "útil" acaba aqui; abaixo estraga o pack)
V_POUSO_CELULA = {"lipo": 3.50, "li-ion": 3.00}
# As tabelas de bancada da T-Motor são OTIMISTAS: os cruzamentos independentes (Tyto Robotics ym47 e #3496)
# dão 6–9 % MENOS eficiência (pesquisa verificada 3-0, 2026-10-10). O modelo aplica a meio (+7,5 %) ao binário
# das hélices calibradas por tabela do fabricante (mais potência para o mesmo empuxo) — `kq_tabela_bruto`
# guarda o valor sem correção.
CORRECAO_KQ_TABELA = 1.075


def v_pouso_celula(celula) -> float:
    """Tensão de pouso POR CÉLULA sob carga: a da célula (se o fabricante a dá) ou a da química."""
    return float(celula.v_pouso) if celula.v_pouso is not None else V_POUSO_CELULA[celula.quimica]


# =========================================================================================== catálogo
def _ler_json(caminho: pathlib.Path) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def carregar_catalogo(caminho: pathlib.Path | str | None = None) -> dict:
    """O catálogo de peças (`componentes.json`) como dict (cópia nova a cada chamada)."""
    return _ler_json(pathlib.Path(caminho) if caminho else CATALOGO_JSON)


def carregar_builds(caminho: pathlib.Path | str | None = None) -> dict:
    """`builds.json` → `{"ativo": nome, "builds": {nome: {...}}}`."""
    return _ler_json(pathlib.Path(caminho) if caminho else BUILDS_JSON)


def nome_build_ativo(caminho: pathlib.Path | str | None = None) -> str:
    """Nome do build ATIVO (o que o treino, o site e a validação usam por omissão)."""
    return str(carregar_builds(caminho)["ativo"])


def gravar_builds(dados: dict, caminho: pathlib.Path | str | None = None) -> None:
    """Escrita ATÓMICA do `builds.json` (tmp + os.replace)."""
    import os
    destino = pathlib.Path(caminho) if caminho else BUILDS_JSON
    tmp = destino.with_suffix(f".tmp{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, destino)


# =========================================================================================== peças
@dataclass(frozen=True)
class Motor:
    id: str
    fabricante: str
    modelo: str
    kv: float                 # rpm/V
    massa: float              # kg (com cabos, sem hélice)
    r_int: float              # Ω — resistência interna (linha-linha) do fabricante
    i0: float                 # A — corrente em vazio ...
    v_i0: float               # V — ... medida a esta tensão
    i_max: float              # A — corrente máxima (pico/10 s do fabricante)
    p_max: float              # W
    tabela: tuple = ()        # linhas do ensaio do fabricante (dicts)
    dados: dict = field(default_factory=dict, compare=False)

    @property
    def kv_rad(self) -> float:
        """KV em (rad/s)/V."""
        return self.kv * RPM_PARA_RAD

    @property
    def ke(self) -> float:
        """Constante de força contra-eletromotriz = constante de binário K_t (SI), V·s/rad = N·m/A."""
        return 1.0 / self.kv_rad


@dataclass(frozen=True)
class Helice:
    id: str
    fabricante: str
    modelo: str
    diametro: float           # m
    passo: float              # m
    massa: float              # kg
    ct: float | None          # C_T estático (UIUC: T = C_T·ρ·n²·D⁴) — None se só houver tabela
    cp: float | None          # C_P estático (P = C_P·ρ·n³·D⁵)
    pas: int = 2
    dados: dict = field(default_factory=dict, compare=False)

    @property
    def raio(self) -> float:
        return 0.5 * self.diametro

    @property
    def area(self) -> float:
        return math.pi * self.raio ** 2


@dataclass(frozen=True)
class Celula:
    id: str
    fabricante: str
    modelo: str
    quimica: str              # "lipo" | "li-ion"
    capacidade_ah: float
    massa: float              # kg
    r_dc: float               # Ω — resistência DC (pulso ~10 s) a 25 °C, 50 % SoC, nova
    v_max: float
    v_nom: float
    v_corte: float            # V — corte absoluto do fabricante
    i_max: float              # A — descarga contínua máxima
    ciclos_80: float          # ciclos (100 % DoD, condições do datasheet) até 80 % da capacidade
    c_ref_ciclos: float       # C-rate de descarga do ensaio de ciclos
    curva: tuple              # (soc[], ocv[]) por célula
    v_pouso: float | None = None  # V/célula sob carga em que se pousa (None = o da química)
    r1_frac: float = 0.6      # R₁/R₀ do ramo RC (polarização) — típico 0,4–0,8 (ver bateria.py)
    tau1: float = 30.0        # s — constante de tempo do ramo RC
    dims_mm: tuple = ()       # (diâmetro, comprimento) cilíndrica ou (c, l, a) pouch
    dados: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class Bateria:
    """Pack N_s·S N_p·P de uma célula do catálogo (+ massa de ligações/BMS/invólucro)."""

    id: str
    celula: Celula
    s: int
    p: int
    massa_extra: float = 0.0  # kg — níquel, cabos, conector, termorretrátil, BMS
    dados: dict = field(default_factory=dict, compare=False)

    @property
    def quimica(self) -> str:
        return self.celula.quimica

    @property
    def massa(self) -> float:
        return self.s * self.p * self.celula.massa + self.massa_extra

    @property
    def capacidade_ah(self) -> float:
        return self.p * self.celula.capacidade_ah

    @property
    def v_nominal(self) -> float:
        return self.s * self.celula.v_nom

    @property
    def v_cheia(self) -> float:
        return self.s * self.celula.v_max

    @property
    def energia_wh(self) -> float:
        """Energia nominal (Ah × V nominal) — a do rótulo do pack."""
        return self.capacidade_ah * self.v_nominal

    @property
    def densidade_wh_kg(self) -> float:
        return self.energia_wh / self.massa

    @property
    def r0(self) -> float:
        """Resistência DC do pack (nova, 25 °C): R_célula·S/P (+ ligações, contadas na massa_extra? não:
        as ligações entram em `r_ligacoes` do build)."""
        return self.celula.r_dc * self.s / self.p

    @property
    def i_max(self) -> float:
        return self.p * self.celula.i_max

    def ocv(self, soc) -> np.ndarray | float:
        """OCV do PACK (V) para um SoC em [0, 1] (interpolação linear da curva da célula)."""
        s, v = self.celula.curva
        return self.s * np.interp(np.clip(soc, 0.0, 1.0), s, v)


@dataclass(frozen=True)
class Frame:
    id: str
    fabricante: str
    modelo: str
    wheelbase: float          # m — diagonal motor-motor
    massa: float              # kg — placas + braços + parafusos (sem trem de pouso se `massa_pernas` > 0)
    helice_max: float         # m — maior hélice que cabe
    massa_pernas: float = 0.0  # kg — trem de pouso
    altura_pernas: float = 0.06  # m — folga do pack ao chão + pernas
    perda_download: float = 0.05  # fração do empuxo perdida no rasto que bate na estrutura (NASA: 5–15 %)
    dados: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class ESC:
    id: str
    fabricante: str
    modelo: str
    massa_total: float        # kg — os 4 canais (4-em-1) ou 4 × individual
    eficiencia: float         # P_saída/P_entrada (perdas de comutação + condução)
    r_on: float               # Ω — resistência de condução no caminho (2 MOSFET) + cabos do motor
    i_max: float              # A por canal
    dshot_bits: int = 11      # DShot: 2048 valores (48..2047 = 2000 níveis de acelerador)
    idle: float = 0.055       # fração de acelerador com o FC armado (Betaflight motor_idle 5,5 %)
    travagem_ativa: bool = True   # "damped light"/PWM complementar (BLHeli_S/Bluejay/AM32): trava o rotor
    dados: dict = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class Consumidor:
    """Eletrónica alimentada pelo BEC 5 V (RPi 5, FC, sensores...)."""

    id: str
    nome: str
    massa: float              # kg
    potencia: dict            # {perfil: W} — perfis "repouso", "voo", "pico"
    dados: dict = field(default_factory=dict, compare=False)

    def p(self, perfil: str = "voo") -> float:
        return float(self.potencia.get(perfil, self.potencia.get("voo", 0.0)))


# =========================================================================================== build resolvido
@dataclass
class Hardware:
    """Um build RESOLVIDO: as peças + tudo o que se deriva delas (ver o docstring do módulo)."""

    nome: str
    descricao: str
    frame: Frame
    motor: Motor
    helice: Helice
    bateria: Bateria
    esc: ESC
    consumidores: list
    sensores: dict            # {papel: preset dict} — imu, tof, fluxo, baro, monitor
    arquitetura: str          # "fc" (FC dedicado faz a malha de taxa) | "rpi" (RPi 5 sozinho, PREEMPT_RT)
    bec_eficiencia: float
    r_ligacoes: float         # Ω — cabos da bateria + conector + PDB (no pack)
    atraso_comando: float     # s — RPi→FC/ESC (sensor→inferência→comando)
    v_brownout: float         # V — abaixo disto o BEC/ESC desligam (queda)
    temperatura_ambiente: float  # °C
    massa_extra: float = 0.0  # kg — parafusos, abraçadeiras, fita (lastro do orçamento)
    dados: dict = field(default_factory=dict)
    # derivados (preenchidos em __post_init__)
    kf: float = 0.0
    kq: float = 0.0
    origem_kf_kq: str = ""
    j_rotor: float = 0.0
    r_motor: float = 0.0      # Ω — R efetiva no modelo DC (motor + ESC/cabos)

    def __post_init__(self) -> None:
        if self.helice.diametro > self.frame.helice_max + 1e-9:
            raise ValueError(f"hélice {self.helice.id} ({self.helice.diametro / POL:.1f}″) não cabe no frame "
                             f"{self.frame.id} (máx. {self.frame.helice_max / POL:.1f}″)")
        self.kf, self.kq, self.origem_kf_kq = _kf_kq(self.motor, self.helice)
        self.j_rotor = inercia_rotor(self.motor, self.helice)
        self.r_motor = self.motor.r_int + self.esc.r_on
        self.curva_esc = _curva_esc(self)

    # ---------------------------------------------------------------- massa e geometria
    @property
    def massas(self) -> dict:
        """Orçamento de massa (kg) por grupo — a soma é `massa_total`."""
        m = {
            "frame": self.frame.massa,
            "pernas": self.frame.massa_pernas,
            "motores": 4 * self.motor.massa,
            "helices": 4 * self.helice.massa,
            "esc": self.esc.massa_total,
            "bateria": self.bateria.massa,
            "extra": self.massa_extra,
        }
        for c in self.consumidores:
            m[c.id] = c.massa
        for papel, s in self.sensores.items():
            m[f"sensor_{papel}"] = float(s.get("massa_g", 0.0)) / 1000.0
        return m

    @property
    def massa_total(self) -> float:
        return float(sum(self.massas.values()))

    @property
    def peso(self) -> float:
        return self.massa_total * GRAVIDADE

    @property
    def braco(self) -> float:
        """Distância centro→eixo do rotor (m) = wheelbase/2."""
        return 0.5 * self.frame.wheelbase

    @property
    def pos_rotores(self) -> np.ndarray:
        """(4, 2) posições xy dos rotores no corpo (X, frente = +x, esquerda = +y)."""
        a = self.braco / math.sqrt(2.0)
        return np.array([[a, a], [-a, -a], [-a, a], [a, -a]])

    # sentido de rotação de cada rotor visto de cima: +1 = CCW (ω ao longo de +z do corpo), −1 = CW.
    # Diagonais com o mesmo sentido: r1 (frente-esq) e r2 (trás-dir) CW; r3 (trás-esq) e r4 (frente-dir) CCW.
    GIRO = np.array([-1.0, -1.0, 1.0, 1.0])

    # ---------------------------------------------------------------- motor (regime estacionário)
    @property
    def omega0(self) -> float:
        """Velocidade em vazio de referência das perdas Q₀ (rad/s) = KV·V_ensaio(I₀)."""
        return self.motor.kv_rad * self.motor.v_i0

    def q0(self, omega) -> np.ndarray | float:
        """Binário de perdas em vazio Q₀(ω) = K_t·I₀·(½ + ½·ω/ω₀) para ω > 0 (0 parado)."""
        w = np.asarray(omega, dtype=float)
        q = self.motor.ke * self.motor.i0 * (0.5 + 0.5 * w / self.omega0)
        return np.where(w > 0.0, q, 0.0) if q.ndim else (float(q) if w > 0.0 else 0.0)

    def omega_regime(self, duty, v_bus, kappa_q: float = 1.0) -> np.ndarray | float:
        """ω de regime (rad/s) para um ciclo útil `duty` ∈ [0, 1] e a tensão do barramento `v_bus`.

        Equilíbrio de binários com corrente quase-estática (L/R ≪ τ mecânico):
            K_t·(d·V − K_e·ω)/R − K_t·I₀·(½ + ½·ω/ω₀) − κ_Q·kq·ω² = 0
        ⇒ kq'·ω² + b·ω − c = 0, b = K_t·K_e/R + ½·K_t·I₀/ω₀, c = K_t·(d·V/R − ½·I₀) (c ≤ 0 → ω = 0).
        """
        kt = ke = self.motor.ke
        r = self.r_motor
        kq = self.kq * kappa_q
        b = kt * ke / r + 0.5 * kt * self.motor.i0 / self.omega0
        c = kt * (np.asarray(duty, dtype=float) * np.asarray(v_bus, dtype=float) / r - 0.5 * self.motor.i0)
        w = (-b + np.sqrt(b * b + 4.0 * kq * np.maximum(c, 0.0))) / (2.0 * kq)
        return np.where(c > 0.0, w, 0.0) if np.ndim(w) else (float(w) if c > 0.0 else 0.0)

    def corrente_motor(self, duty, v_bus, omega) -> np.ndarray | float:
        """Corrente de fase equivalente I = (d·V − K_e·ω)/R (A; negativa = travagem regenerativa)."""
        return (np.asarray(duty) * np.asarray(v_bus) - self.motor.ke * np.asarray(omega)) / self.r_motor

    # ---------------------------------------------------------------- ESC: acelerador → ciclo útil
    def acelerador_para_duty(self, acelerador) -> np.ndarray | float:
        """Curva do ESC calibrada na tabela do fabricante (ver `_curva_esc`): 0 → 0, monótona, 1 → d_max."""
        u, d = self.curva_esc
        a = np.asarray(acelerador, dtype=float)
        r = np.where(a > 0.0, np.interp(a, u, d), 0.0)
        return r if r.ndim else float(r)

    def duty_para_acelerador(self, duty) -> float:
        """Inverso da curva do ESC (o acelerador que dá este ciclo útil)."""
        u, d = self.curva_esc
        return float(np.interp(float(duty), d, u))

    @property
    def duty_max(self) -> float:
        return float(self.curva_esc[1][-1])

    def inclinacao_esc(self, acelerador: float) -> float:
        """d(duty)/d(acelerador) no ponto (para os ganhos do FC)."""
        h = 1e-3
        return (self.acelerador_para_duty(min(acelerador + h, 1.0))
                - self.acelerador_para_duty(max(acelerador - h, 1e-6))) / (min(acelerador + h, 1.0)
                                                                         - max(acelerador - h, 1e-6))

    def omega_max(self, v_bus) -> float:
        """Teto de rotação (rad/s) com acelerador a 100 % — decai com a tensão (o limite do plano §5)."""
        return float(self.omega_regime(self.duty_max, v_bus))

    def empuxo_max(self, v_bus) -> float:
        """Empuxo máximo POR ROTOR (N) = kf·ω_max(V)²."""
        return self.kf * self.omega_max(v_bus) ** 2

    def duty_para_omega(self, omega, v_bus, kappa_q: float = 1.0) -> float:
        """Ciclo útil que sustenta `omega` em regime (inverso de `omega_regime`)."""
        w = float(omega)
        i = (float(self.q0(w)) + kappa_q * self.kq * w * w) / self.motor.ke
        return (self.motor.ke * w + self.r_motor * i) / float(v_bus)

    # ---------------------------------------------------------------- eletrónica e pairagem
    def potencia_eletronica(self, perfil: str = "voo") -> float:
        """W consumidos NA BATERIA pela eletrónica de 5 V (consumidores ÷ eficiência do BEC) + sensores."""
        p5 = sum(c.p(perfil) for c in self.consumidores)
        p5 += sum(float(s.get("potencia_w", 0.0)) for s in self.sensores.values())
        return p5 / self.bec_eficiencia

    def ponto_pairagem(self, v_bus: float, massa: float | None = None) -> dict:
        """Regime de pairagem em ar parado (fora do efeito de solo) com o barramento a `v_bus`.

        Devolve ω, duty, corrente de fase e do barramento por motor, potências (mecânica, elétrica dos
        motores, eletrónica, total na bateria) e a eficiência g/W do sistema.
        """
        m = self.massa_total if massa is None else float(massa)
        t = m * GRAVIDADE / (4.0 * (1.0 - self.frame.perda_download))   # o rasto perde parte na estrutura
        w = math.sqrt(t / self.kf)
        d = self.duty_para_omega(w, v_bus)
        i_fase = float(self.corrente_motor(d, v_bus, w))
        i_bus = d * i_fase / self.esc.eficiencia
        p_mec = 4.0 * self.kq * w ** 3
        p_mot = 4.0 * v_bus * i_bus
        p_ele = self.potencia_eletronica("voo")
        return {"omega": w, "rpm": w / RPM_PARA_RAD, "duty": d, "acelerador": self.duty_para_acelerador(d),
                "empuxo_rotor": t,
                "i_fase": i_fase, "i_bus_motor": i_bus, "p_mecanica": p_mec, "p_motores": p_mot,
                "p_eletronica": p_ele, "p_total": p_mot + p_ele, "i_total": (p_mot + p_ele) / v_bus,
                "g_por_w": m * 1000.0 / (p_mot + p_ele), "g_por_w_motores": m * 1000.0 / p_mot,
                "satura": d > self.duty_max}

    def resumo(self) -> dict:
        """Números-chave do build (orçamento, T/W, pairagem, ω_max e autonomia estimada)."""
        b = self.bateria
        v_nom = b.v_nominal
        ph = self.ponto_pairagem(v_nom)
        t_max = 4.0 * self.empuxo_max(b.v_cheia)
        aut = autonomia_estimada(self)
        return {
            "build": self.nome, "massa_total_g": self.massa_total * 1000.0,
            "massas_g": {k: v * 1000.0 for k, v in self.massas.items()},
            "kf": self.kf, "kq": self.kq, "kq_kf_m": self.kq / self.kf, "origem_kf_kq": self.origem_kf_kq,
            "j_rotor": self.j_rotor, "r_motor_ohm": self.r_motor,
            "bateria": {"id": b.id, "quimica": b.quimica, "s": b.s, "p": b.p, "ah": b.capacidade_ah,
                        "wh": b.energia_wh, "massa_g": b.massa * 1000.0, "wh_kg": b.densidade_wh_kg,
                        "r0_mohm": b.r0 * 1000.0},
            "t_w_cheia": t_max / self.peso,
            "omega_max_cheia_rpm": self.omega_max(b.v_cheia) / RPM_PARA_RAD,
            "pairagem_v_nominal": ph,
            "autonomia_min": aut["minutos"], "autonomia": aut,
        }


# =========================================================================================== derivações
def _kf_kq(motor: Motor, helice: Helice) -> tuple[float, float, str]:
    """kf, kq e a origem: TABELA do fabricante (este motor + esta hélice) > C_T/C_P da hélice."""
    linhas = [r for r in motor.tabela if r.get("helice") == helice.id and r.get("rpm")]
    if len(linhas) >= 1:
        w = np.array([r["rpm"] for r in linhas], dtype=float) * RPM_PARA_RAD
        t = np.array([r["empuxo_g"] for r in linhas], dtype=float) * 1e-3 * GRAVIDADE
        kf = float(np.sum(t * w ** 2) / np.sum(w ** 4))
        q = []
        for r, wi in zip(linhas, w, strict=True):
            if r.get("torque_nm"):
                q.append(float(r["torque_nm"]))
            else:   # binário do eixo pela corrente: Q = K_t·(I_fase − I₀(ω)), I_fase = I_bus/d
                d = float(r["acelerador_pct"]) / 100.0
                i_fase = float(r["corrente_a"]) / max(d, 1e-6)
                i0 = motor.i0 * (0.5 + 0.5 * wi / (motor.kv_rad * motor.v_i0))
                q.append(motor.ke * (i_fase - i0))
        q = np.array(q)
        kq = float(np.sum(q * w ** 2) / np.sum(w ** 4))
        fonte = "torque medido" if all(r.get("torque_nm") for r in linhas) else "corrente medida"
        independente = all(r.get("independente") for r in linhas)
        if not independente:
            kq *= CORRECAO_KQ_TABELA
        corr = "medição independente" if independente else f"+{100 * (CORRECAO_KQ_TABELA - 1):.1f} % de realismo"
        return kf, kq, f"tabela do fabricante ({len(linhas)} pontos; kq por {fonte}; {corr})"
    if helice.ct is None or helice.cp is None:
        raise ValueError(f"sem tabela de ensaio para {motor.id}+{helice.id} e a hélice não traz C_T/C_P")
    d = helice.diametro
    kf = helice.ct * RHO_AR * d ** 4 / (4.0 * math.pi ** 2)
    kq = helice.cp * RHO_AR * d ** 5 / (8.0 * math.pi ** 3)
    return kf, kq, "C_T/C_P estáticos da hélice (convenção UIUC)"


def _curva_esc(hw) -> tuple[np.ndarray, np.ndarray]:
    """Curva acelerador → ciclo útil EFETIVO do ESC, calibrada nas linhas da tabela do fabricante.

    Em cada linha (acelerador u, tensão V, rpm, corrente I_bus) o ciclo útil que explica o ponto com o KV e
    a R FÍSICOS do motor sai do equilíbrio elétrico com o ESC de eficiência η:
        d·V = K_e·ω + R·I_fase,  I_fase = η·I_bus/d   ⇒   d = [K_e·ω + √((K_e·ω)² + 4·V·R·η·I_bus)]/(2V)
    Nos ensaios T-Motor isto dá d ≈ 0,46 a 50 % e ≈ 0,83 a 100 % (perdas de comutação/limite do ESC): é o
    que faz o empuxo máximo do modelo bater com o da tabela (e o T/W real). Pontos: (0, 0), as linhas
    (monótonas) e, se a tabela não chega a 100 %, extrapolação linear até 1 (cortada a d ≤ 1). Sem tabela
    para este motor+hélice: identidade (d = u).
    """
    linhas = sorted((r for r in hw.motor.tabela if r.get("helice") == hw.helice.id and r.get("rpm")
                     and r.get("corrente_a") and r.get("acelerador_pct")), key=lambda r: r["acelerador_pct"])
    if not linhas:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0])
    ke, r, eta = hw.motor.ke, hw.r_motor, hw.esc.eficiencia
    us, ds = [0.0], [0.0]
    for lin in linhas:
        v = float(lin["tensao_v"])
        e = ke * float(lin["rpm"]) * RPM_PARA_RAD
        d = (e + math.sqrt(e * e + 4.0 * v * r * eta * float(lin["corrente_a"]))) / (2.0 * v)
        us.append(float(lin["acelerador_pct"]) / 100.0)
        ds.append(min(d, 1.0))
    us_a, ds_a = np.array(us), np.maximum.accumulate(np.array(ds))
    if us_a[-1] < 1.0:
        k = (ds_a[-1] - ds_a[-2]) / max(us_a[-1] - us_a[-2], 1e-9)
        us_a = np.append(us_a, 1.0)
        ds_a = np.append(ds_a, min(1.0, ds_a[-1] + k * (1.0 - us_a[-2])))
    return us_a, ds_a


def inercia_rotor(motor: Motor, helice: Helice) -> float:
    """J do conjunto que gira (kg·m²): hélice ≈ 0,2·m·R² + sino ≈ (0,35·m_motor)·r_sino².

    `r_sino` = raio externo do motor (catálogo `diametro_mm`/2; na falta, 14 mm). ESTIMATIVA documentada
    — a domain randomization cobre ±25 % e o SysID do hardware real fixa o valor.
    """
    r_sino = float(motor.dados.get("diametro_mm", 28.0)) / 2000.0
    j_sino = 0.35 * motor.massa * r_sino ** 2
    j_helice = 0.2 * helice.massa * helice.raio ** 2
    return j_helice + j_sino


def autonomia_estimada(hw: Hardware, soc0: float = 1.0, dt: float = 2.0, perfil: str = "voo") -> dict:
    """Autonomia de PAIRAGEM (min) integrando a bateria (OCV(SoC) − I·R₀) com o regime de pairagem.

    Bancada sem MuJoCo (ar parado, fora do efeito de solo, SoH = 1, 25 °C): a cada `dt` resolve-se a
    tensão do barramento por ponto fixo (V = OCV − I(V)·R) e desconta-se a carga por contagem de Coulomb.
    Para quando a tensão POR CÉLULA sob carga cai abaixo da tensão de pouso da química (LiPo 3,5 V,
    Li-ion 3,0 V) ou o SoC chega a 0. Usada no resumo/`hardware.py`; a autonomia MEDIDA na planta MuJoCo
    é a do `run.py` (§ autonomia) e tem de concordar com esta.
    """
    b = hw.bateria
    cap_as = b.capacidade_ah * 3600.0
    r = b.r0 + hw.r_ligacoes
    v_pouso = v_pouso_celula(b.celula) * b.s
    soc, t, e_wh, v = float(soc0), 0.0, 0.0, float(b.ocv(soc0))
    serie = []
    while soc > 0.0 and t < 6.0 * 3600.0:
        ocv = float(b.ocv(soc))
        for _ in range(30):        # ponto fixo V = OCV − I(V)·R
            p = hw.ponto_pairagem(v)
            v_novo = ocv - p["i_total"] * r
            if abs(v_novo - v) < 1e-7:
                break
            v = v_novo
        if v < v_pouso or p["satura"]:
            break
        i = p["i_total"]
        if len(serie) == 0 or t - serie[-1][0] >= 60.0:
            serie.append((t, soc, v, i, p["p_total"]))
        soc -= i * dt / cap_as
        e_wh += p["p_total"] * dt / 3600.0
        t += dt
    return {"minutos": t / 60.0, "soc_final": max(soc, 0.0), "v_final": v, "energia_wh": e_wh,
            "v_pouso": v_pouso, "serie": serie}


# =========================================================================================== resolução
def _peca(catalogo: dict, grupo: str, chave: str) -> dict:
    try:
        d = copy.deepcopy(catalogo[grupo][chave])
    except KeyError:
        disponiveis = sorted(catalogo.get(grupo, {}))
        raise KeyError(f"'{chave}' não existe em {grupo} do catálogo — disponíveis: {disponiveis}") from None
    d["id"] = chave
    return d


def _motor(d: dict) -> Motor:
    return Motor(id=d["id"], fabricante=d["fabricante"], modelo=d["modelo"], kv=float(d["kv_rpm_v"]),
                 massa=float(d["massa_g"]) / 1000.0, r_int=float(d["r_int_mohm"]) / 1000.0,
                 i0=float(d["i0_a"]), v_i0=float(d["i0_v"]), i_max=float(d["i_max_a"]),
                 p_max=float(d["p_max_w"]), tabela=tuple(d.get("tabela", ())), dados=d)


def _helice(d: dict) -> Helice:
    return Helice(id=d["id"], fabricante=d["fabricante"], modelo=d["modelo"],
                  diametro=float(d["diametro_pol"]) * POL, passo=float(d["passo_pol"]) * POL,
                  massa=float(d["massa_g"]) / 1000.0, ct=d.get("ct"), cp=d.get("cp"),
                  pas=int(d.get("pas", 2)), dados=d)


def _celula(d: dict) -> Celula:
    quimica = d["quimica"]
    if "curva_ocv" in d:
        curva = (tuple(d["curva_ocv"]["soc"]), tuple(d["curva_ocv"]["ocv"]))
    else:
        s, v = CURVAS_OCV[quimica]
        curva = (tuple(s), tuple(v))
    return Celula(id=d["id"], fabricante=d["fabricante"], modelo=d["modelo"], quimica=quimica,
                  capacidade_ah=float(d["capacidade_mah"]) / 1000.0, massa=float(d["massa_g"]) / 1000.0,
                  r_dc=float(d["r_dc_mohm"]) / 1000.0, v_max=float(d["v_max"]), v_nom=float(d["v_nom"]),
                  v_corte=float(d["v_corte"]), i_max=float(d["i_max_a"]), ciclos_80=float(d["ciclos_80"]),
                  c_ref_ciclos=float(d.get("c_ref_ciclos", 1.0)), curva=curva,
                  v_pouso=(float(d["v_pouso"]) if d.get("v_pouso") is not None else None),
                  r1_frac=float(d.get("r1_frac", 0.6)), tau1=float(d.get("tau1_s", 30.0)),
                  dims_mm=tuple(d.get("dims_mm", ())), dados=d)


def resolver(build: str | dict | None = None, catalogo: dict | None = None,
             builds: dict | None = None) -> Hardware:
    """Resolve um build (nome, dict de build ou None = o ATIVO) num `Hardware` com tudo derivado."""
    cat = carregar_catalogo() if catalogo is None else catalogo
    if build is None or isinstance(build, str):
        tabela = carregar_builds() if builds is None else builds
        nome = tabela["ativo"] if build is None else build
        try:
            cfg = copy.deepcopy(tabela["builds"][nome])
        except KeyError:
            raise KeyError(f"build '{nome}' não existe — disponíveis: {sorted(tabela['builds'])}") from None
    else:
        cfg = copy.deepcopy(build)
        nome = cfg.get("nome", "personalizado")

    bat = cfg["bateria"]
    cel = _celula(_peca(cat, "celulas", bat["celula"]))
    bateria = Bateria(id=bat.get("id", f"{bat['celula']}_{bat['s']}s{bat['p']}p"), celula=cel,
                      s=int(bat["s"]), p=int(bat["p"]), massa_extra=float(bat.get("massa_extra_g", 0.0)) / 1000.0,
                      dados=bat)
    f = _peca(cat, "frames", cfg["frame"])
    frame = Frame(id=f["id"], fabricante=f["fabricante"], modelo=f["modelo"],
                  wheelbase=float(f["wheelbase_mm"]) / 1000.0, massa=float(f["massa_g"]) / 1000.0,
                  helice_max=float(f["helice_max_pol"]) * POL, massa_pernas=float(f.get("massa_pernas_g", 0.0)) / 1000.0,
                  altura_pernas=float(f.get("altura_pernas_mm", 60.0)) / 1000.0,
                  perda_download=float(f.get("perda_download", 0.05)), dados=f)
    e = _peca(cat, "esc", cfg["esc"])
    esc = ESC(id=e["id"], fabricante=e["fabricante"], modelo=e["modelo"],
              massa_total=float(e["massa_total_g"]) / 1000.0, eficiencia=float(e["eficiencia"]),
              r_on=float(e["r_on_mohm"]) / 1000.0, i_max=float(e["i_max_a"]),
              dshot_bits=int(e.get("dshot_bits", 11)), idle=float(e.get("idle", 0.055)),
              travagem_ativa=bool(e.get("travagem_ativa", True)), dados=e)
    consumidores = []
    for cid in cfg.get("eletronica", []):
        c = _peca(cat, "eletronica", cid)
        consumidores.append(Consumidor(id=c["id"], nome=c["nome"], massa=float(c["massa_g"]) / 1000.0,
                                       potencia={k: float(v) for k, v in c["potencia_w"].items()}, dados=c))
    sensores = {}
    for papel, sid in cfg.get("sensores", {}).items():
        s = _peca(cat, "sensores", sid)
        sensores[papel] = s
    return Hardware(
        nome=nome, descricao=cfg.get("descricao", ""), frame=frame,
        motor=_motor(_peca(cat, "motores", cfg["motor"])), helice=_helice(_peca(cat, "helices", cfg["helice"])),
        bateria=bateria, esc=esc, consumidores=consumidores, sensores=sensores,
        arquitetura=cfg.get("arquitetura", "fc"), bec_eficiencia=float(cfg.get("bec_eficiencia", 0.88)),
        r_ligacoes=float(cfg.get("r_ligacoes_mohm", 3.0)) / 1000.0,
        atraso_comando=float(cfg.get("atraso_comando_ms", 8.0)) / 1000.0,
        v_brownout=float(cfg.get("v_brownout", 6.0)),
        temperatura_ambiente=float(cfg.get("temperatura_ambiente_c", 25.0)),
        massa_extra=float(cfg.get("massa_extra_g", 0.0)) / 1000.0, dados=cfg)
