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

    @property
    def perfil(self) -> str:
        """Família aerodinâmica/geométrica da pá: `scimitar_cf` (T-Motor P/MF carbono), `mr_naca` (APC MR) ou `tri_pa_fpv`."""
        if self.dados.get("perfil"):
            return str(self.dados["perfil"])
        if self.pas >= 3:
            return "tri_pa_fpv"
        if "apc" in self.id.lower():
            return "mr_naca"
        return "scimitar_cf"

    @property
    def corda_media(self) -> float:
        """Corda média da pá c̄ (m): `corda_media_mm` do catálogo ou lei geométrica por perfil (≈ 0,078·D nas P-series CF)."""
        if self.dados.get("corda_media_mm"):
            return float(self.dados["corda_media_mm"]) / 1000.0
        fator = {"scimitar_cf": 0.078, "mr_naca": 0.084, "tri_pa_fpv": 0.115}.get(self.perfil, 0.080)
        return fator * self.diametro

    @property
    def afunilamento(self) -> float:
        """Razão de afunilamento ponta/raiz λ_taper = c_ponta / c_raiz (0,42 nominal nas pás scimitar de carbono)."""
        return float(self.dados.get("afunilamento", 0.42))

    @property
    def solidez(self) -> float:
        """Solidez do disco do rotor σ = N_pás · c̄ / (π · R)."""
        return float(self.pas) * self.corda_media / (math.pi * max(self.raio, 1e-6))

    @property
    def angulo_passo_75_rad(self) -> float:
        """Ângulo geométrico de passo a 75 % do raio: θ_75 = arctan(P / (0,75 · π · D))."""
        return math.atan2(self.passo, 0.75 * math.pi * max(self.diametro, 1e-6))

    @property
    def fator_inercia(self) -> float:
        """Fator adimensional de inércia rotacional κ_J = J_hélice / (m·R²) em função do afunilamento λ_taper.
        No afunilamento nominal λ_taper = 0,42 vale exatamente 0,20 (preservando a identidade bit a bit)."""
        lam = self.afunilamento
        nom = 1.0 + 2.0 * 0.42 + 3.0 * (0.42 ** 2)
        return 0.20 * (1.0 + 2.0 * lam + 3.0 * (lam ** 2)) / nom

    def ct_cp_bemt(self) -> tuple[float, float]:
        """Calcula (C_T, C_P) estáticos pela Teoria do Elemento de Pá + Momento (BEMT) a partir do tamanho e
        design da hélice (diâmetro D, passo P, N_pás, corda/solidez σ, afunilamento e perfil aerodinâmico)."""
        perf = {
            "scimitar_cf": (5.85, 0.014, 1.12),   # (a₀ rad⁻¹, C_d0 perfil fino CF, κ_ind)
            "mr_naca": (5.50, 0.018, 1.16),       # perfil NACA/APC mais espesso
            "tri_pa_fpv": (5.20, 0.024, 1.22),    # pá curta de baixo Reynolds
        }.get(self.perfil, (5.70, 0.016, 1.14))
        a0, cd0, k_ind = perf
        sigma = self.solidez
        # Correção de perdas de ponta de Prandtl (fator B ≈ 1 − √(2·C_T)/N_pás ≈ 0,92–0,95)
        b_prandtl = 1.0 - 0.11 / max(float(self.pas), 1.0)
        sa = sigma * a0 * b_prandtl
        theta75 = self.angulo_passo_75_rad
        lam0 = (sa / 16.0) * (math.sqrt(max(1.0 + (64.0 / (3.0 * max(sa, 1e-6))) * theta75, 0.0)) - 1.0)
        ct_bemt = max(2.0 * (lam0 ** 2), 1e-5)
        # Convenção UIUC: C_T_uiuc = π³ · ct_bemt / 4, C_P_uiuc = π⁴ · cp_bemt / 4
        cp_bemt = k_ind * lam0 * ct_bemt + 0.125 * sigma * cd0 * (1.0 + 0.15 * self.afunilamento)
        ct_uiuc = (math.pi ** 3 / 4.0) * ct_bemt
        cp_uiuc = (math.pi ** 4 / 4.0) * cp_bemt
        return ct_uiuc, cp_uiuc

    def com_design(self, *, diametro_pol: float | None = None, passo_pol: float | None = None,
                   pas: int | None = None, corda_media_mm: float | None = None,
                   afunilamento: float | None = None, perfil: str | None = None) -> Helice:
        """Cria uma variante da hélice com novo tamanho/design (diâmetro, passo, nº de pás, corda, afunilamento
        ou perfil), recalculando a massa por escala física e ajustando `ct`/`cp` pelo rácio BEMT do novo design."""
        d_novo = self.diametro if diametro_pol is None else float(diametro_pol) * POL
        p_novo = self.passo if passo_pol is None else float(passo_pol) * POL
        pas_novo = self.pas if pas is None else int(pas)
        dados_novos = dict(self.dados)
        dados_novos["id_base"] = self.dados.get("id_base", self.id)
        dados_novos.setdefault("perfil", self.perfil)
        if corda_media_mm is not None:
            dados_novos["corda_media_mm"] = float(corda_media_mm)
        if afunilamento is not None:
            dados_novos["afunilamento"] = float(afunilamento)
        if perfil is not None:
            dados_novos["perfil"] = str(perfil)
        dados_novos["design_customizado"] = True
        ct0, cp0 = self.ct_cp_bemt()
        # Massa escala com (N_pás / N_pás0) · (D / D0)^2,3 · (c̄ / c̄0)
        r_d = d_novo / max(self.diametro, 1e-6)
        r_pas = pas_novo / max(self.pas, 1)
        temp = Helice(id=f"{self.id}_custom", fabricante=self.fabricante, modelo=f"{self.modelo} (design)",
                      diametro=d_novo, passo=p_novo, massa=self.massa, ct=self.ct, cp=self.cp,
                      pas=pas_novo, dados=dados_novos)
        r_c = temp.corda_media / max(self.corda_media, 1e-6)
        m_nova = self.massa * r_pas * (r_d ** 2.0) * r_c
        ct1, cp1 = temp.ct_cp_bemt()
        dados_novos["escala_ct_design"] = ct1 / max(ct0, 1e-6)
        dados_novos["escala_cp_design"] = cp1 / max(cp0, 1e-6)
        return Helice(id=temp.id, fabricante=self.fabricante, modelo=temp.modelo,
                      diametro=d_novo, passo=p_novo, massa=m_nova,
                      ct=ct1 if self.ct is None else self.ct * (ct1 / max(ct0, 1e-6)),
                      cp=cp1 if self.cp is None else self.cp * (cp1 / max(cp0, 1e-6)),
                      pas=pas_novo, dados=dados_novos)


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


@dataclass(frozen=True)
class Camera:
    """Módulo de câmara CSI (o que "transmite para o Raspberry") montado à frente do drone.

    Só o HARDWARE físico vive aqui (massa, dimensões, sensor, FoV, modos — tudo com fonte no
    catálogo). O comportamento (pipeline, fps, JPEG, latência, CPU do Pi 5) é do emulador
    `lab/camera_rpi.py`, que usa ESTES valores — o catálogo é a fonte de verdade das peças.
    """

    id: str
    nome: str
    massa: float              # kg
    dados: dict = field(default_factory=dict, compare=False)

    @property
    def dims(self) -> tuple[float, float, float]:
        """(largura, profundidade, altura COM a lente) em m — a ordem é a do catálogo e do datasheet.

        Na montagem do nariz (`modelo.py`) a placa fica de pé a olhar para +x: a ALTURA com lente (o 3.º
        valor, 11,5/12,4 mm) é a espessura no eixo ótico (x), a largura vai para y e a profundidade da
        placa para z.
        """
        return tuple(float(v) / 1000.0 for v in self.dados.get("dims_mm", (25.0, 24.0, 11.5)))

    @property
    def fov_graus(self) -> dict:
        """FoV publicado (graus): {diag, horizontal, vertical}."""
        return dict(self.dados.get("fov_graus", {}))


@dataclass(frozen=True)
class Arma:
    """Arma montada FIXA no topo do drone (`models/drone_rpi/componentes.json` → `armas`).

    Física e balística fechadas a partir dos dados da ficha técnica:
      · dimensões `(comprimento, largura, altura)` em m (187 × 32 × 128 mm na Glock 25);
      · massas em kg: `massa` (com carregador cheio, 785 g), `massa_vazia` (645 g), `massa_sem_carregador` (575 g);
      · energia na boca do cano: `E₀ = ½ · m_p · v₀²` (269,68 J ≈ 270 J para 95 gr @ 296 m/s);
      · impulso do tiro ("o soco"): `J_tiro = m_p · v₀ + m_polvora · v_gases` (N·s), entregue em `-x̂_corpo`
        ao longo de `duracao_impulso` s (`F_media = J_tiro / duracao_impulso`, N) no eixo do cano (site `boca_cano`).
    """

    id: str
    fabricante: str
    modelo: str
    calibre: str
    massa: float                    # kg — com carregador cheio (padrão em voo)
    massa_vazia: float              # kg — com carregador vazio
    massa_sem_carregador: float     # kg — sem carregador
    capacidade: int                 # tiros no carregador padrão (15 na G25)
    comprimento_cano: float         # m (0,102 m na G25)
    largura_ferrolho: float         # m (0,0255 m na G25)
    peso_gatilho_n: float           # N (28 N na G25)
    massa_projetil: float           # kg (6,156e-3 kg = 95 gr)
    velocidade_boca: float          # m/s (296 m/s = 971 fps)
    massa_polvora: float            # kg (0,20e-3 kg ≈ 3,1 gr)
    velocidade_gases: float         # m/s (470 m/s)
    duracao_impulso: float = 0.020  # s — janela física do pulso de recuo (10 passos de 2 ms = 20 ms)
    dados: dict = field(default_factory=dict, compare=False)

    @property
    def dims(self) -> tuple[float, float, float]:
        """(comprimento x, largura y, altura z) em m."""
        if "dims_mm" in self.dados:
            return tuple(float(v) / 1000.0 for v in self.dados["dims_mm"])
        return (
            float(self.dados.get("comprimento_mm", 187.0)) / 1000.0,
            float(self.dados.get("largura_mm", 32.0)) / 1000.0,
            float(self.dados.get("altura_mm", 128.0)) / 1000.0,
        )

    @property
    def massa_municao_unitaria(self) -> float:
        """Massa de um cartucho completo (kg) = (massa_cheia − massa_vazia) / capacidade."""
        return (self.massa - self.massa_vazia) / max(self.capacidade, 1)

    @property
    def energia_boca_j(self) -> float:
        """Energia cinética na boca do cano E₀ = ½·m_p·v₀² (J)."""
        return 0.5 * self.massa_projetil * (self.velocidade_boca ** 2)

    @property
    def impulso_projetil(self) -> float:
        """Quantidade de movimento linear do projétil p_p = m_p·v₀ (N·s)."""
        return self.massa_projetil * self.velocidade_boca

    @property
    def impulso_gases(self) -> float:
        """Impulso adicional do jato de gases propelentes na boca do cano J_g = m_c·v_g (N·s)."""
        return self.massa_polvora * self.velocidade_gases

    @property
    def impulso_tiro(self) -> float:
        """Impulso total de recuo por disparo ("o soco") J_tiro = m_p·v₀ + m_c·v_g (N·s)."""
        return self.impulso_projetil + self.impulso_gases

    @property
    def forca_media_tiro(self) -> float:
        """Força média durante a janela `duracao_impulso`: F = J_tiro / Δt_soco (N)."""
        return self.impulso_tiro / max(self.duracao_impulso, 1e-6)

    @property
    def energia_recuo_livre_arma_j(self) -> float:
        """Energia de recuo livre da pistola isolada E_rec = J_tiro² / (2·m_arma) (J)."""
        return (self.impulso_tiro ** 2) / (2.0 * max(self.massa, 1e-6))

    @property
    def area_frontal(self) -> float:
        """Área frontal efetiva (m², perpendicular a +x)."""
        _c, l, a = self.dims
        aero = self.dados.get("aerodinamica") or {}
        fator = float(aero.get("fator_area_frontal", 0.75))
        return fator * l * a

    @property
    def area_lateral(self) -> float:
        """Área lateral efetiva (m², perpendicular a +y: silhueta ferrolho + punho)."""
        c, _l, a = self.dims
        aero = self.dados.get("aerodinamica") or {}
        fator = float(aero.get("fator_area_lateral", 0.65))
        return fator * c * a


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
    arquitetura: str          # "fc" (FC dedicado faz a malha de taxa) | "rpi" (RPi 5 sozinho, PREEMPT_RT) | "arduino"
    #                           (Portenta H7: laço de taxa no M4 e visão no M7 — só informativo, nada deriva dele)
    bec_eficiencia: float
    r_ligacoes: float         # Ω — cabos da bateria + conector + PDB (no pack)
    atraso_comando: float     # s — RPi→FC/ESC (sensor→inferência→comando)
    v_brownout: float         # V — abaixo disto o BEC/ESC desligam (queda)
    temperatura_ambiente: float  # °C
    camera: Camera | None = None  # módulo de câmara CSI (opcional; entra no orçamento de massa)
    arma: Arma | None = None      # arma montada fixa no topo do drone (opcional; entra no orçamento, inércia e aero)
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
        if self.camera is not None:
            m["camera"] = self.camera.massa
        if self.arma is not None:
            m["arma"] = self.arma.massa
        return m

    def arrasto_arma_xy(self, v_ref: float | None = None) -> tuple[float, float]:
        """Acréscimo de coeficiente linear de arrasto (Δd_x, Δd_y) em s⁻¹ devido ao perfil da arma no topo.

        Fórmula fechada: ΔF_{d,i} = ½·ρ·C_{d,i}·A_i·v_ref·v_i ⇒ Δd_i = ½·ρ·C_{d,i}·A_i·v_ref / m_total.
        Sem arma devolve `(0.0, 0.0)`.
        """
        if self.arma is None:
            return (0.0, 0.0)
        aero = self.arma.dados.get("aerodinamica") or {}
        cd_x = float(aero.get("cd_frontal", 1.15))
        cd_y = float(aero.get("cd_lateral", 1.20))
        v = float(aero.get("v_ref_linearizacao_m_s", 3.0) if v_ref is None else v_ref)
        m = max(self.massa_total, 1e-6)
        dx = 0.5 * RHO_AR * cd_x * self.arma.area_frontal * v / m
        dy = 0.5 * RHO_AR * cd_y * self.arma.area_lateral * v / m
        return (dx, dy)

    def resumo_arma(self) -> dict | None:
        """Dados físicos, balísticos e de recuo da arma montada no drone (ou `None` sem arma)."""
        if self.arma is None:
            return None
        a = self.arma
        dx, dy = self.arrasto_arma_xy()
        return {
            "id": a.id,
            "fabricante": a.fabricante,
            "modelo": a.modelo,
            "calibre": a.calibre,
            "massa_g": a.massa * 1000.0,
            "massa_vazia_g": a.massa_vazia * 1000.0,
            "massa_sem_carregador_g": a.massa_sem_carregador * 1000.0,
            "capacidade": a.capacidade,
            "comprimento_cano_mm": a.comprimento_cano * 1000.0,
            "dims_mm": [round(v * 1000.0, 1) for v in a.dims],
            "peso_gatilho_n": a.peso_gatilho_n,
            "massa_projetil_g": a.massa_projetil * 1000.0,
            "velocidade_boca_m_s": a.velocidade_boca,
            "energia_boca_j": a.energia_boca_j,
            "impulso_projetil_ns": a.impulso_projetil,
            "impulso_gases_ns": a.impulso_gases,
            "impulso_tiro_ns": a.impulso_tiro,
            "duracao_impulso_s": a.duracao_impulso,
            "forca_media_tiro_n": a.forca_media_tiro,
            "delta_v_drone_m_s": a.impulso_tiro / max(self.massa_total, 1e-6),
            "direcao_tiro_corpo": [1.0, 0.0, 0.0],
            "direcao_soco_corpo": [-1.0, 0.0, 0.0],
            "delta_d_xy_s1": [dx, dy],
        }

    @property
    def massa_total(self) -> float:
        return float(sum(self.massas.values()))

    @property
    def massa_estrutura_sem_carga(self) -> float:
        """Massa do drone base (kg) sem carga útil/arma (`arma` excluída)."""
        return float(sum(v for k, v in self.massas.items() if k != "arma"))

    @property
    def massa_carga_total(self) -> float:
        """Massa total de carga útil acoplada no build (kg): arma + carga extra."""
        return float(self.massas.get("arma", 0.0))

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
        if type(omega) is float:                     # escalar (chamado a cada passo de decisão): sem NumPy
            return self.motor.ke * self.motor.i0 * (0.5 + 0.5 * omega / self.omega0) if omega > 0.0 else 0.0
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
        inversa = self.__dict__.get("_curva_esc_inversa")
        if inversa is None or inversa[0] is not d:   # tabela escalar do `np.interp(duty, d, u)`, feita uma vez
            from .escalar import Tabela
            inversa = self._curva_esc_inversa = (d, Tabela(d, u))
        return inversa[1](float(duty))

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

    def areas_equivalentes_corpo(self) -> tuple[float, float]:
        """Áreas equivalentes de arrasto de corpo rombo (C_d·A_x, C_d·A_y) em m² (frame + bateria + pilha + arma)."""
        lado = (0.5 * float(self.frame.dados["placa_mm"]) / 1000.0 if self.frame.dados.get("placa_mm")
                else max(0.045, 0.16 * self.frame.wheelbase))
        # Braços (4 tubos a 45°) + placa central + pack de bateria + pilha de eletrónica
        a_bracos = 4.0 * (0.5 * self.frame.wheelbase) * 0.012 * 0.7071
        dims_bat = [float(x) / 1000.0 for x in self.bateria.dados.get("dims_mm", (142, 70, 44))]
        c_b, l_b, a_b = sorted(dims_bat, reverse=True)
        cda_x = 1.10 * (a_bracos + l_b * a_b + (2.0 * lado) * 0.035)
        cda_y = 1.10 * (a_bracos + c_b * a_b + (2.0 * lado) * 0.035)
        if self.arma is not None:
            aero_a = self.arma.dados.get("aerodinamica") or {}
            cda_x += float(aero_a.get("cd_frontal", 1.15)) * self.arma.area_frontal
            cda_y += float(aero_a.get("cd_lateral", 1.20)) * self.arma.area_lateral
        return (cda_x, cda_y)

    def ponto_maximo(self, soc: float = 1.0, temperatura_c: float | None = None, soh: float = 1.0) -> dict:
        """Ponto de operação a 100 % de acelerador (`duty_max`) resolvendo a queda de tensão REAL na bateria:
        V_bus = OCV(SoC) − I_total(V_bus, duty_max) · R_ef(SoC, T, SoH).

        Devolve tensões, correntes, potências, empuxo bruto e EFETIVO (descontando `perda_download` e incluindo
        o ganho de efeito de solo no arranque) e a verificação dos limites elétricos/térmicos de cada peça.
        """
        b = self.bateria
        soc_c = float(np.clip(soc, 0.0, 1.0))
        ocv = float(b.ocv(soc_c))
        t_c = self.temperatura_ambiente if temperatura_c is None else float(temperatura_c)
        f_t = math.exp(22_000.0 / 8.314 * (1.0 / (t_c + 273.15) - 1.0 / 298.15))
        f_soc = 1.0 + max(0.0, 0.2 - soc_c) / 0.2
        f_soh = 1.0 + 0.5 * (1.0 - float(soh)) / 0.2
        r_tot = b.r0 * f_t * f_soc * f_soh + self.r_ligacoes
        d_max = self.duty_max
        p_ele = self.potencia_eletronica("voo")
        v = ocv
        for _ in range(30):
            w = self.omega_max(v)
            i_fase = max(0.0, float(self.corrente_motor(d_max, v, w)))
            i_bus = d_max * i_fase / self.esc.eficiencia
            i_tot = 4.0 * i_bus + p_ele / max(v, 1e-3)
            v_novo = max(self.v_brownout, ocv - i_tot * r_tot)
            if abs(v_novo - v) < 1e-7:
                v = v_novo
                break
            v = v_novo
        w_max = self.omega_max(v)
        i_fase = max(0.0, float(self.corrente_motor(d_max, v, w_max)))
        i_bus = d_max * i_fase / self.esc.eficiencia
        i_tot = 4.0 * i_bus + p_ele / max(v, 1e-3)
        p_mot_unit = v * i_bus
        p_mot = 4.0 * p_mot_unit
        p_tot = p_mot + p_ele
        t_bruto = 4.0 * self.kf * (w_max ** 2)
        f_dl = 1.0 - self.frame.perda_download
        t_efetivo_oge = f_dl * t_bruto
        # Ganho de efeito de solo EXATO com as pernas apoiadas no chão (Sanchez-Cuevas 2017, igual a `aero.ganho_solo`)
        dims_bat = [float(x) / 1000.0 for x in self.bateria.dados.get("dims_mm", (142, 70, 44))]
        a_b = min(dims_bat)
        z_baixo = -0.0015 - 0.004 - a_b - 0.004
        h_pernas = max(self.frame.altura_pernas, -z_baixo + 0.03)
        h_motor = float(self.motor.dados.get("altura_mm", 20.0)) / 1000.0
        z_chao = h_pernas + 0.006 + 0.0015 + h_motor + 0.014
        r_h = self.helice.raio
        r2 = r_h * r_h
        b_op = self.frame.wheelbase
        d_viz = b_op / math.sqrt(2.0)
        s_ige = (
            (r_h / (4.0 * z_chao)) ** 2
            + r2 * z_chao / math.sqrt((d_viz ** 2 + 4.0 * z_chao * z_chao) ** 3)
            + 0.5 * r2 * z_chao / math.sqrt((2.0 * d_viz ** 2 + 4.0 * z_chao * z_chao) ** 3)
            + 2.0 * r2 * z_chao * 2.0 / math.sqrt((b_op ** 2 + 4.0 * z_chao * z_chao) ** 3)
        )
        g_ige = min(1.0 / max(1.0 - s_ige, 1e-9), 1.6)
        t_efetivo_ige = t_efetivo_oge * g_ige
        return {
            "soc": soc_c,
            "v_ocv": ocv,
            "v_bus_carga": v,
            "queda_tensao_v": ocv - v,
            "r_total_mohm": r_tot * 1000.0,
            "omega_max": w_max,
            "rpm_max": w_max / RPM_PARA_RAD,
            "i_fase_motor": i_fase,
            "i_bus_motor": i_bus,
            "i_total": i_tot,
            "p_motor_unit_w": p_mot_unit,
            "p_motores_w": p_mot,
            "p_total_w": p_tot,
            "empuxo_bruto_n": t_bruto,
            "empuxo_efetivo_oge_n": t_efetivo_oge,
            "empuxo_efetivo_ige_n": t_efetivo_ige,
            "ganho_solo_descolagem": g_ige,
            "limites_pecas": {
                "motor_i_max_a": self.motor.i_max,
                "motor_i_ok": i_fase <= self.motor.i_max,
                "motor_p_max_w": self.motor.p_max,
                "motor_p_ok": p_mot_unit <= self.motor.p_max,
                "esc_i_max_a": self.esc.i_max,
                "esc_i_ok": i_bus <= self.esc.i_max,
                "bateria_i_max_a": b.i_max,
                "bateria_i_ok": i_tot <= b.i_max,
            },
        }

    def impacto_vento(self, vento_m_s: float, azimute_graus: float = 90.0, massa: float | None = None,
                      soc: float = 1.0, tilt_max_graus: float = 30.0) -> dict:
        """Cálculo físico fechado do impacto do vento `vento_m_s` (m/s) acoplado ao peso `massa` (kg) e `soc`:

          1. Força horizontal de arrasto = arrasto H-force dos 4 rotores + arrasto parasita de corpo rombo
             (frame + bateria + eletrónica + arma no topo);
          2. Inclinação de equilíbrio θ_eq = arctan(F_vento / (m·g)) necessária para segurar posição;
          3. Inflow axial v_axial = W·sin(θ_eq) através do disco inclinado (BEMT: reduz κ_T e altera κ_Q);
          4. Empuxo total necessário T_nec = √((m·g)² + F_vento²) / (1 − perda_download) e rotação ω_vento;
          5. Tensão real do barramento por ponto fixo V_bus = OCV(SoC) − I_total(V_bus)·R₀, corrente, potência
             e verificação de saturação de empuxo (duty > duty_max) e de inclinação (θ_eq > tilt_max).
        """
        m = self.massa_total if massa is None else max(float(massa), 1e-3)
        w_vel = max(0.0, float(vento_m_s))
        az = math.radians(float(azimute_graus))
        wx = abs(w_vel * math.cos(az))
        wy = abs(w_vel * math.sin(az))
        b = self.bateria
        soc_c = float(np.clip(soc, 0.0, 1.0))
        ocv = float(b.ocv(soc_c))
        f_soc = 1.0 + max(0.0, 0.2 - soc_c) / 0.2
        r_tot = b.r0 * f_soc + self.r_ligacoes
        f_dl = 1.0 - self.frame.perda_download
        p_ele = self.potencia_eletronica("voo")

        # Coeficientes de arrasto linear (rotor + arma) e quadrático (corpo rombo)
        dx_a, dy_a = self.arrasto_arma_xy()
        d_x, d_y = 0.30 + dx_a, 0.30 + dy_a
        cda_x, cda_y = self.areas_equivalentes_corpo()
        f_wx = d_x * m * wx + 0.5 * RHO_AR * cda_x * w_vel * wx
        f_wy = d_y * m * wy + 0.5 * RHO_AR * cda_y * w_vel * wy
        f_vento = math.hypot(f_wx, f_wy)
        peso_n = m * GRAVIDADE
        theta_eq = math.atan2(f_vento, peso_n)
        theta_graus = math.degrees(theta_eq)
        satura_incl = theta_graus > float(tilt_max_graus)

        # Inflow axial BEMT no disco inclinado (v_axial = W·sin(θ_eq) > 0: ar entra por cima do disco)
        v_axial = w_vel * math.sin(theta_eq)
        raio = self.helice.raio
        ct0 = self.kf / (RHO_AR * math.pi * (raio ** 4))
        cq0 = self.kq / (RHO_AR * math.pi * (raio ** 5))
        lam0 = math.sqrt(ct0 / 2.0)
        sigma_a = 0.45
        theta_pa = 3.0 * (2.0 * ct0 / sigma_a + lam0 / 2.0)
        cq_perf = max(cq0 - lam0 * ct0, 0.0)
        t_rotor_nec = math.hypot(peso_n, f_vento) / (4.0 * f_dl)
        w_est = math.sqrt(max(t_rotor_nec / self.kf, 1e-6))
        for _ in range(6):
            lam_c = v_axial / max(w_est * raio, 1e-6)
            a_b = sigma_a * theta_pa / 6.0
            b_b = sigma_a / 4.0
            bb = b_b - 2.0 * lam_c
            lam = (-bb + math.sqrt(bb * bb + 8.0 * a_b)) / 4.0
            ct = a_b - b_b * lam
            kt_inflow = min(max(ct / ct0, 0.25), 1.3)
            cq = cq_perf + lam * max(ct, 0.0)
            kq_inflow = min(max(cq / cq0, 0.1), 1.5)
            w_est = math.sqrt(max(t_rotor_nec / (kt_inflow * self.kf), 1e-6))

        # Equilíbrio elétrico com a bateria sob carga
        v = ocv
        satura_empuxo = False
        for _ in range(30):
            d_nec = self.duty_para_omega(w_est, v, kappa_q=kq_inflow)
            satura_empuxo = d_nec > self.duty_max
            d_ef = min(d_nec, self.duty_max)
            w_real = w_est if not satura_empuxo else float(self.omega_regime(d_ef, v, kappa_q=kq_inflow))
            i_fase = max(0.0, float(self.corrente_motor(d_ef, v, w_real)))
            i_bus = d_ef * i_fase / self.esc.eficiencia
            i_tot = 4.0 * i_bus + p_ele / max(v, 1e-3)
            v_novo = max(self.v_brownout, ocv - i_tot * r_tot)
            if abs(v_novo - v) < 1e-7:
                v = v_novo
                break
            v = v_novo

        d_nec = self.duty_para_omega(w_est, v, kappa_q=kq_inflow)
        satura_empuxo = d_nec > self.duty_max
        d_ef = min(d_nec, self.duty_max)
        w_real = w_est if not satura_empuxo else float(self.omega_regime(d_ef, v, kappa_q=kq_inflow))
        i_fase = max(0.0, float(self.corrente_motor(d_ef, v, w_real)))
        i_bus = d_ef * i_fase / self.esc.eficiencia
        i_tot = 4.0 * i_bus + p_ele / max(v, 1e-3)
        p_mot = 4.0 * v * i_bus
        p_tot = p_mot + p_ele
        t_disp_total = 4.0 * f_dl * kt_inflow * self.kf * (w_real ** 2)
        t_vert_disp = t_disp_total * math.cos(min(theta_eq, math.radians(tilt_max_graus)))
        v_pouso = v_pouso_celula(b.celula) * b.s
        sustenta = (not satura_empuxo) and (not satura_incl) and (v >= v_pouso) and (t_vert_disp >= peso_n * 0.999)
        return {
            "vento_m_s": w_vel,
            "azimute_graus": float(azimute_graus),
            "massa_g": m * 1000.0,
            "forca_vento_n": f_vento,
            "acel_vento_m_s2": f_vento / m,
            "inclinacao_eq_graus": theta_graus,
            "kappa_t_inflow": kt_inflow,
            "kappa_q_inflow": kq_inflow,
            "empuxo_necessario_n": 4.0 * t_rotor_nec * f_dl,
            "empuxo_disponivel_n": t_disp_total,
            "omega": w_real,
            "rpm": w_real / RPM_PARA_RAD,
            "duty_necessario": d_nec,
            "duty": d_ef,
            "acelerador": self.duty_para_acelerador(d_ef),
            "v_bus": v,
            "i_fase": i_fase,
            "i_bus_motor": i_bus,
            "i_total": i_tot,
            "p_motores": p_mot,
            "p_eletronica": p_ele,
            "p_total": p_tot,
            "satura_empuxo": bool(satura_empuxo),
            "satura_inclinacao": bool(satura_incl),
            "satura": bool(satura_empuxo or satura_incl or v < v_pouso),
            "sustenta_voo": bool(sustenta),
        }

    def vento_maximo_sustentavel(self, massa: float | None = None, soc: float = 1.0,
                                 azimute_graus: float = 90.0, tilt_max_graus: float = 30.0) -> float:
        """Velocidade máxima de vento constante (m/s) que o drone sustenta sem saturar motores nem inclinação."""
        if not self.impacto_vento(0.0, azimute_graus, massa=massa, soc=soc, tilt_max_graus=tilt_max_graus)["sustenta_voo"]:
            return 0.0
        lo, hi = 0.0, 25.0
        for _ in range(28):
            mid = 0.5 * (lo + hi)
            if self.impacto_vento(mid, azimute_graus, massa=massa, soc=soc, tilt_max_graus=tilt_max_graus)["sustenta_voo"]:
                lo = mid
            else:
                hi = mid
        return round(lo, 3)

    def limites_carga(self, massa_total: float | None = None, soc: float = 1.0, vento_m_s: float = 0.0) -> dict:
        """Calcula o envelope de carga útil, impacto na bateria e viabilidade de descolagem/voo do build."""
        m = self.massa_total if massa_total is None else max(float(massa_total), 1e-3)
        m_base = self.massa_estrutura_sem_carga
        carga_atual = max(0.0, m - m_base)
        pm = self.ponto_maximo(soc=soc)
        t_max_oge = pm["empuxo_efetivo_oge_n"]
        t_max_ige = pm["empuxo_efetivo_ige_n"]
        m_max_oge = t_max_oge / GRAVIDADE
        m_max_ige = t_max_ige / GRAVIDADE
        m_max_seguro = t_max_oge / (1.35 * GRAVIDADE)
        peso_n = m * GRAVIDADE
        tw_oge = t_max_oge / max(peso_n, 1e-6)
        tw_ige = t_max_ige / max(peso_n, 1e-6)
        iv = self.impacto_vento(vento_m_s, massa=m, soc=soc)
        w_max = self.vento_maximo_sustentavel(massa=m, soc=soc)
        pode_alcar = bool(tw_ige > 1.005 and pm["v_bus_carga"] > self.v_brownout)
        pode_oge = bool(tw_oge > 1.01 and iv["sustenta_voo"])
        pode_seguro = bool(tw_oge >= 1.35 and iv["sustenta_voo"])
        if not pode_alcar:
            estado = "impossivel_alcar_voo"
        elif tw_oge <= 1.01:
            estado = "preso_efeito_solo"
        elif not iv["sustenta_voo"]:
            estado = "insustentavel_no_vento"
        elif tw_oge < 1.35:
            estado = "marginal_sem_reserva"
        else:
            estado = "voo_seguro"
        return {
            "massa_sem_carga_g": round(m_base * 1000.0, 1),
            "massa_total_g": round(m * 1000.0, 1),
            "carga_atual_g": round(carga_atual * 1000.0, 1),
            "massa_max_descolagem_oge_g": round(m_max_oge * 1000.0, 1),
            "carga_max_descolagem_oge_g": round(max(0.0, m_max_oge - m_base) * 1000.0, 1),
            "massa_max_descolagem_ige_g": round(m_max_ige * 1000.0, 1),
            "carga_max_descolagem_ige_g": round(max(0.0, m_max_ige - m_base) * 1000.0, 1),
            "massa_max_voo_seguro_g": round(m_max_seguro * 1000.0, 1),
            "carga_max_voo_seguro_g": round(max(0.0, m_max_seguro - m_base) * 1000.0, 1),
            "t_w_efetivo_oge": round(tw_oge, 3),
            "t_w_efetivo_ige": round(tw_ige, 3),
            "pode_alcar_voo": pode_alcar,
            "pode_pairar_oge": pode_oge,
            "pode_voar_seguro": pode_seguro,
            "estado_voo": estado,
            "vento_max_m_s": w_max,
            "operacao_atual": iv,
            "ponto_maximo": pm,
        }

    def resumo(self) -> dict:
        """Números-chave do build (orçamento, T/W, pairagem, ω_max e autonomia estimada)."""
        b = self.bateria
        v_nom = b.v_nominal
        ph = self.ponto_pairagem(v_nom)
        t_max = 4.0 * self.empuxo_max(b.v_cheia)
        aut = autonomia_estimada(self)
        return {
            "build": self.nome, "massa_total_g": self.massa_total * 1000.0,
            "massa_sem_carga_g": self.massa_estrutura_sem_carga * 1000.0,
            "carga_total_g": self.massa_carga_total * 1000.0,
            "massas_g": {k: v * 1000.0 for k, v in self.massas.items()},
            "kf": self.kf, "kq": self.kq, "kq_kf_m": self.kq / self.kf, "origem_kf_kq": self.origem_kf_kq,
            "j_rotor": self.j_rotor, "r_motor_ohm": self.r_motor,
            "bateria": {"id": b.id, "quimica": b.quimica, "s": b.s, "p": b.p, "ah": b.capacidade_ah,
                        "wh": b.energia_wh, "massa_g": b.massa * 1000.0, "wh_kg": b.densidade_wh_kg,
                        "r0_mohm": b.r0 * 1000.0},
            "arma": self.resumo_arma(),
            "limites_carga": self.limites_carga(),
            "t_w_cheia": t_max / self.peso,
            "omega_max_cheia_rpm": self.omega_max(b.v_cheia) / RPM_PARA_RAD,
            "pairagem_v_nominal": ph,
            "autonomia_min": aut["minutos"], "autonomia": aut,
        }


# =========================================================================================== derivações
def _kf_kq(motor: Motor, helice: Helice) -> tuple[float, float, str]:
    """kf, kq e a origem: TABELA do fabricante (este motor + esta hélice) > C_T/C_P da hélice."""
    ids_hel = {helice.id, helice.dados.get("id_base")} - {None}
    linhas = [r for r in motor.tabela if r.get("helice") in ids_hel and r.get("rpm")]
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
        if helice.dados.get("design_customizado"):
            kf *= float(helice.dados.get("escala_ct_design", 1.0)) * (helice.diametro / (float(helice.dados.get("diametro_pol", 15.0)) * POL)) ** 4
            kq *= float(helice.dados.get("escala_cp_design", 1.0)) * (helice.diametro / (float(helice.dados.get("diametro_pol", 15.0)) * POL)) ** 5
        corr = "medição independente" if independente else f"+{100 * (CORRECAO_KQ_TABELA - 1):.1f} % de realismo"
        return kf, kq, f"tabela do fabricante ({len(linhas)} pontos; kq por {fonte}; {corr})"
    ct_use, cp_use = (helice.ct, helice.cp) if (helice.ct is not None and helice.cp is not None) else helice.ct_cp_bemt()
    d = helice.diametro
    kf = ct_use * RHO_AR * d ** 4 / (4.0 * math.pi ** 2)
    kq = cp_use * RHO_AR * d ** 5 / (8.0 * math.pi ** 3)
    origem = "C_T/C_P estáticos da hélice (convenção UIUC)" if (helice.ct is not None and helice.cp is not None) else "BEMT geométrico do design da hélice"
    return kf, kq, origem


kf_kq = _kf_kq


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
    """J do conjunto que gira (kg·m²): hélice = κ_J(afunilamento)·m·R² + sino ≈ (0,35·m_motor)·r_sino².

    `r_sino` = raio externo do motor (catálogo `diametro_mm`/2; na falta, 14 mm); `κ_J` vem da distribuição
    radial de corda da pá (`helice.fator_inercia`, igual a 0,20 no afunilamento nominal 0,42).
    """
    r_sino = float(motor.dados.get("diametro_mm", 28.0)) / 2000.0
    j_sino = 0.35 * motor.massa * r_sino ** 2
    j_helice = helice.fator_inercia * helice.massa * helice.raio ** 2
    return j_helice + j_sino


def autonomia_estimada(hw: Hardware, soc0: float = 1.0, dt: float = 2.0, perfil: str = "voo",
                       massa: float | None = None, vento_m_s: float = 0.0) -> dict:
    """Autonomia de PAIRAGEM (min) integrando a bateria (OCV(SoC) − I·R₀) com o regime de pairagem
    (em ar parado ou sob vento constante `vento_m_s` m/s, para a massa total `massa` kg).

    Bancada sem MuJoCo (fora do efeito de solo, SoH = 1, 25 °C): a cada `dt` resolve-se a
    tensão do barramento por ponto fixo (V = OCV − I(V)·R) e desconta-se a carga por contagem de Coulomb.
    Para quando a tensão POR CÉLULA sob carga cai abaixo da tensão de pouso da química (LiPo 3,5 V,
    Li-ion 3,0 V), o SoC chega a 0 ou o empuxo/inclinação saturam (`p["satura"]`).
    """
    b = hw.bateria
    cap_as = b.capacidade_ah * 3600.0
    r = b.r0 + hw.r_ligacoes
    v_pouso = v_pouso_celula(b.celula) * b.s
    soc, t, e_wh, v = float(soc0), 0.0, 0.0, float(b.ocv(soc0))
    serie = []
    motivo = "soc_zero"
    while soc > 0.0 and t < 6.0 * 3600.0:
        if vento_m_s > 0.0:
            p = hw.impacto_vento(vento_m_s, massa=massa, soc=soc)
            v = p["v_bus"]
        else:
            ocv = float(b.ocv(soc))
            for _ in range(30):        # ponto fixo V = OCV − I(V)·R
                p = hw.ponto_pairagem(v, massa=massa)
                v_novo = ocv - p["i_total"] * r
                if abs(v_novo - v) < 1e-7:
                    break
                v = v_novo
        if v < v_pouso:
            motivo = "tensao_pouso"
            break
        if p["satura"]:
            motivo = "saturacao_carga_ou_vento"
            break
        i = p["i_total"]
        if len(serie) == 0 or t - serie[-1][0] >= 60.0:
            serie.append((t, soc, v, i, p["p_total"]))
        soc -= i * dt / cap_as
        e_wh += p["p_total"] * dt / 3600.0
        t += dt
    return {"minutos": t / 60.0, "soc_final": max(soc, 0.0), "v_final": v, "energia_wh": e_wh,
            "v_pouso": v_pouso, "motivo_fim": motivo, "pode_voar": t > 0.0, "serie": serie}


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
    camera = None
    if cfg.get("camera"):
        c = _peca(cat, "cameras", cfg["camera"])
        camera = Camera(id=c["id"], nome=c.get("modelo", c["id"]),
                        massa=float(c["massa_g"]) / 1000.0, dados=c)
    arma = None
    if cfg.get("arma"):
        a = _peca(cat, "armas", cfg["arma"])
        bal = a.get("balistica") or {}
        arma = Arma(
            id=a["id"],
            fabricante=a.get("fabricante", ""),
            modelo=a.get("modelo", a["id"]),
            calibre=a.get("calibre", ""),
            massa=float(a.get("massa_g", a.get("massa_carregador_cheio_g", 785.0))) / 1000.0,
            massa_vazia=float(a.get("massa_carregador_vazio_g", 645.0)) / 1000.0,
            massa_sem_carregador=float(a.get("massa_sem_carregador_g", 575.0)) / 1000.0,
            capacidade=int(a.get("capacidade_padrao", 15)),
            comprimento_cano=float(a.get("comprimento_cano_mm", 102.0)) / 1000.0,
            largura_ferrolho=float(a.get("largura_ferrolho_mm", 25.5)) / 1000.0,
            peso_gatilho_n=float(a.get("peso_gatilho_n", 28.0)),
            massa_projetil=float(bal.get("massa_projetil_g", 6.156)) / 1000.0,
            velocidade_boca=float(bal.get("velocidade_boca_m_s", 296.0)),
            massa_polvora=float(bal.get("massa_polvora_g", 0.20)) / 1000.0,
            velocidade_gases=float(bal.get("velocidade_gases_m_s", 470.0)),
            duracao_impulso=float(a.get("duracao_impulso_s", 0.020)),
            dados=a,
        )
    return Hardware(
        nome=nome, descricao=cfg.get("descricao", ""), frame=frame,
        motor=_motor(_peca(cat, "motores", cfg["motor"])), helice=_helice(_peca(cat, "helices", cfg["helice"])),
        bateria=bateria, esc=esc, consumidores=consumidores, sensores=sensores, camera=camera, arma=arma,
        arquitetura=cfg.get("arquitetura", "fc"), bec_eficiencia=float(cfg.get("bec_eficiencia", 0.88)),
        r_ligacoes=float(cfg.get("r_ligacoes_mohm", 3.0)) / 1000.0,
        atraso_comando=float(cfg.get("atraso_comando_ms", 8.0)) / 1000.0,
        v_brownout=float(cfg.get("v_brownout", 6.0)),
        temperatura_ambiente=float(cfg.get("temperatura_ambiente_c", 25.0)),
        massa_extra=float(cfg.get("massa_extra_g", 0.0)) / 1000.0, dados=cfg)
