"""lab.drone_rpi.bateria — o pack de bateria do drone: tensão com queda sob carga, SoC, calor e desgaste.

Modelo elétrico (Thevenin de 1 ramo RC, o padrão dos BMS/gauges — TI SLUAAR3: V_medida = OCV − I·R):

    V_terminal = OCV_pack(SoC) − V_rc − I·(R₀ + R_ligações)
    dV_rc/dt  = −V_rc/τ₁ + I/C₁            (polarização: a tensão "recupera" quando a corrente cai)
    dSoC/dt   = −I/(3600·Q_nom·SoH)        (contagem de Coulomb sobre a capacidade ATUAL)

com o pack N_s·S N_p·P: OCV_pack = N_s·OCV_célula, R₀ = R_célula·N_s/N_p, R₁ = r1_frac·R₀, C₁ = τ₁/R₁.

R₀ efetiva = R₀(25 °C, nova) · f_T(T) · f_SoC(SoC) · f_SoH:
  · f_T  = exp(E_a/R·(1/T − 1/298,15)), E_a = 22 kJ/mol (≈ ×2,2 a 0 °C — a queda de tensão no frio);
  · f_SoC = 1 + max(0, 0,2 − SoC)/0,2 (a resistência sobe no fim da descarga: ×2 a 0 %);
  · f_SoH = 1 + k_R·(1 − SoH)/0,2 com k_R = 0,5 (+50 % no fim de vida; a camada SEI cresce).

Térmica do pack (1 nó): m·c_p·dT/dt = I²·R₀ + V_rc·I − h·A·(T − T_amb), c_p = 900 J/(kg·K),
h = 20 W/(m²·K) (convecção forçada pelo downwash), A = superfície do invólucro.

DESGASTE (persistente entre voos — `EstadoDesgaste` em JSON): cada recarga fecha um ciclo parcial com
profundidade DoD (carga descarregada / capacidade), C-rate médio e temperatura média; a perda de capacidade é

    ΔSoH = (0,2/N₈₀) · DoD^1,2 · max(1, C/C_ref)^0,5 · f_T,desg

(N₈₀ = ciclos a 100 % DoD até 80 % do datasheet da célula, nas condições C_ref do ensaio; DoD^1,2 = lei de
Wöhler — descargas fundas desgastam mais por ciclo equivalente; f_T,desg = Arrhenius 30 kJ/mol acima de 25 °C).
SoH ≤ 0,8 ⇒ "reformar" (fim de vida, convenção da indústria). Ciclos equivalentes = Ah descarregados/Q_nom.
É um modelo semi-empírico calibrado nos ciclos do datasheet — o SoH real mede-se (capacidade e R_int).
"""
from __future__ import annotations

import json
import math
import os
import pathlib
from dataclasses import asdict, dataclass, field

import numpy as np

from .componentes import Hardware, v_pouso_celula

R_GAS = 8.314
EA_RESISTENCIA = 22_000.0     # J/mol — dependência térmica de R₀ (Arrhenius)
EA_DESGASTE = 30_000.0        # J/mol — aceleração do desgaste com a temperatura (acima de 25 °C)
K_R_SOH = 0.5                 # +50 % de R₀ no fim de vida (SoH = 0,8)
CP_PACK = 900.0               # J/(kg·K)
H_CONVECCAO = 20.0            # W/(m²·K)
SOH_FIM_DE_VIDA = 0.80
EXPOENTE_DOD = 1.2
EXPOENTE_C = 0.5
RESERVA_SOC = {"lipo": 0.20, "li-ion": 0.10}   # reserva de pouso para a "autonomia restante" mostrada


@dataclass
class EstadoDesgaste:
    """Estado de saúde PERSISTENTE de um pack físico (sobrevive entre voos/sessões)."""

    pack_id: str
    soh: float = 1.0                  # capacidade atual / nominal
    ciclos_eq: float = 0.0            # ciclos equivalentes completos (Ah descarregados / Q_nom)
    ah_total: float = 0.0             # Ah descarregados ao longo da vida
    n_recargas: int = 0
    historico: list = field(default_factory=list)   # últimos ciclos: {dod, c_medio, t_medio_c, soh}

    @property
    def r_fator(self) -> float:
        return 1.0 + K_R_SOH * (1.0 - self.soh) / (1.0 - SOH_FIM_DE_VIDA)

    @property
    def reformar(self) -> bool:
        return self.soh <= SOH_FIM_DE_VIDA

    def para_dict(self) -> dict:
        d = asdict(self)
        d["r_fator"] = self.r_fator
        d["reformar"] = self.reformar
        return d

    @classmethod
    def de_dict(cls, d: dict) -> EstadoDesgaste:
        return cls(pack_id=str(d["pack_id"]), soh=float(d.get("soh", 1.0)),
                   ciclos_eq=float(d.get("ciclos_eq", 0.0)), ah_total=float(d.get("ah_total", 0.0)),
                   n_recargas=int(d.get("n_recargas", 0)), historico=list(d.get("historico", []))[-50:])

    def gravar(self, caminho: pathlib.Path | str) -> None:
        """Escrita ATÓMICA (tmp + os.replace) — o estado de um pack nunca fica meio escrito."""
        caminho = pathlib.Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = caminho.with_name(f".{caminho.name}.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.para_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, caminho)

    @classmethod
    def carregar(cls, caminho: pathlib.Path | str, pack_id: str) -> EstadoDesgaste:
        """Lê o estado do pack (ou devolve um pack NOVO se o ficheiro não existir ou for de outro pack)."""
        try:
            with open(caminho, encoding="utf-8") as f:
                d = json.load(f)
            if d.get("pack_id") == pack_id:
                return cls.de_dict(d)
        except (OSError, ValueError, KeyError):
            pass
        return cls(pack_id=pack_id)


def perda_por_ciclo(hw: Hardware, dod: float, c_medio: float, t_medio_c: float) -> float:
    """ΔSoH de UM ciclo parcial (fórmula no docstring do módulo)."""
    cel = hw.bateria.celula
    delta_ref = (1.0 - SOH_FIM_DE_VIDA) / cel.ciclos_80
    f_c = max(1.0, c_medio / cel.c_ref_ciclos) ** EXPOENTE_C
    t_k = t_medio_c + 273.15
    f_t = math.exp(EA_DESGASTE / R_GAS * (1.0 / 298.15 - 1.0 / t_k)) if t_medio_c > 25.0 else 1.0
    return delta_ref * max(0.0, min(1.0, dod)) ** EXPOENTE_DOD * f_c * f_t


class ModeloBateria:
    """O pack em voo: integra SoC/V_rc/temperatura a cada passo de física e guarda o ciclo em curso."""

    def __init__(self, hw: Hardware, desgaste: EstadoDesgaste | None = None, soc0: float = 1.0,
                 temperatura_c: float | None = None, escala_r: float = 1.0, escala_cap: float = 1.0):
        self.hw = hw
        self.b = hw.bateria
        self.desgaste = desgaste if desgaste is not None else EstadoDesgaste(pack_id=self.b.id)
        self.escala_r = float(escala_r)          # domain randomization da resistência (±)
        self.escala_cap = float(escala_cap)      # domain randomization da capacidade (±)
        self.t_amb = hw.temperatura_ambiente if temperatura_c is None else float(temperatura_c)
        dims = [float(x) / 1000.0 for x in hw.bateria.dados.get("dims_mm", ())] or _dims_pack(hw)
        c, l_, a = dims
        self.area = 2.0 * (c * l_ + c * a + l_ * a)
        self.c_termica = CP_PACK * self.b.massa
        self.reiniciar(soc0, temperatura_c)

    # ------------------------------------------------------------------ estado
    def reiniciar(self, soc0: float = 1.0, temperatura_c: float | None = None) -> None:
        """Pack descansado com SoC `soc0` (V_rc = 0) à temperatura dada (por omissão a ambiente)."""
        self.soc = float(np.clip(soc0, 0.0, 1.0))
        self.v_rc = 0.0
        self.temp = self.t_amb if temperatura_c is None else float(temperatura_c)
        self.i = 0.0
        self.v = float(self.ocv())
        self.p = 0.0
        # ciclo em curso (desde a última recarga)
        self.soc_inicio = self.soc
        self.ah_ciclo = 0.0
        self.wh_ciclo = 0.0
        self.t_ciclo = 0.0
        self.soma_c_dt = 0.0
        self.soma_t_dt = 0.0
        self.i_pico = 0.0
        self.v_min = self.v

    @property
    def capacidade_ah(self) -> float:
        """Capacidade ATUAL (Ah) = nominal × SoH × escala (DR)."""
        return self.b.capacidade_ah * self.desgaste.soh * self.escala_cap

    def ocv(self) -> float:
        return float(self.b.ocv(self.soc))

    def r0(self) -> float:
        """R₀ efetiva do pack + ligações (Ω) no estado atual (temperatura, SoC, desgaste)."""
        t_k = self.temp + 273.15
        f_t = math.exp(EA_RESISTENCIA / R_GAS * (1.0 / t_k - 1.0 / 298.15))
        f_soc = 1.0 + max(0.0, 0.2 - self.soc) / 0.2
        return self.b.r0 * f_t * f_soc * self.desgaste.r_fator * self.escala_r + self.hw.r_ligacoes

    def r1(self) -> float:
        t_k = self.temp + 273.15
        f_t = math.exp(EA_RESISTENCIA / R_GAS * (1.0 / t_k - 1.0 / 298.15))
        return self.b.celula.r1_frac * self.b.r0 * f_t * self.desgaste.r_fator * self.escala_r

    def tensao_aberta(self) -> float:
        """OCV − V_rc: a "fonte" vista pelos consumidores neste instante (falta só a queda I·R₀)."""
        return self.ocv() - self.v_rc

    # ------------------------------------------------------------------ passo
    def passo(self, corrente: float, dt: float) -> None:
        """Integra `dt` com a corrente `corrente` (A, + = descarga) e atualiza V/P/temperatura/ciclo."""
        i = float(corrente)
        r0 = self.r0()
        r1 = self.r1()
        tau = self.b.celula.tau1
        a = math.exp(-dt / tau)
        self.v = self.ocv() - self.v_rc - i * r0          # tensão no instante (com o V_rc antes do passo)
        self.v_rc = self.v_rc * a + i * r1 * (1.0 - a)    # solução exata do ramo RC com I constante
        self.soc = max(0.0, self.soc - i * dt / (3600.0 * self.capacidade_ah))
        calor = i * i * r0 + self.v_rc * i
        self.temp += dt * (calor - H_CONVECCAO * self.area * (self.temp - self.t_amb)) / self.c_termica
        self.i = i
        self.p = self.v * i
        if i > 0.0:
            self.ah_ciclo += i * dt / 3600.0
            self.wh_ciclo += self.p * dt / 3600.0
        self.t_ciclo += dt
        self.soma_c_dt += abs(i) / self.b.capacidade_ah * dt
        self.soma_t_dt += self.temp * dt
        self.i_pico = max(self.i_pico, i)
        self.v_min = min(self.v_min, self.v)

    # ------------------------------------------------------------------ leitura
    @property
    def v_celula(self) -> float:
        return self.v / self.b.s

    @property
    def alerta(self) -> str:
        """"" | "tensao_baixa" (abaixo da tensão de pouso da química) | "critica" (abaixo do corte)."""
        if self.v_celula <= self.b.celula.v_corte:
            return "critica"
        if self.v_celula <= v_pouso_celula(self.b.celula):
            return "tensao_baixa"
        return ""

    def autonomia_restante_min(self, i_media: float) -> float:
        """Minutos até à reserva de pouso com a corrente média dada (estimativa por Coulomb)."""
        reserva = RESERVA_SOC[self.b.quimica]
        if i_media <= 1e-6:
            return float("inf")
        return max(0.0, (self.soc - reserva) * self.capacidade_ah * 60.0 / i_media)

    # ------------------------------------------------------------------ desgaste
    def resumo_ciclo(self) -> dict:
        dod = self.ah_ciclo / max(self.b.capacidade_ah, 1e-9)
        t = max(self.t_ciclo, 1e-9)
        return {"dod": dod, "ah": self.ah_ciclo, "wh": self.wh_ciclo, "c_medio": self.soma_c_dt / t,
                "t_medio_c": self.soma_t_dt / t, "i_pico": self.i_pico, "v_min": self.v_min,
                "duracao_s": self.t_ciclo}

    def recarregar(self, soc_final: float = 1.0) -> dict:
        """FECHA o ciclo em curso (aplica o desgaste) e põe o pack carregado e descansado.

        Devolve o resumo do ciclo fechado (com o SoH depois do desgaste). Um ciclo vazio (nada
        descarregado) não conta recarga nem desgaste.
        """
        r = self.resumo_ciclo()
        if r["ah"] > 0.0:
            d = self.desgaste
            d.soh = max(0.0, d.soh - perda_por_ciclo(self.hw, r["dod"], r["c_medio"], r["t_medio_c"]))
            d.ciclos_eq += r["dod"]
            d.ah_total += r["ah"]
            d.n_recargas += 1
            d.historico = (d.historico + [{"dod": round(r["dod"], 4), "c_medio": round(r["c_medio"], 3),
                                           "t_medio_c": round(r["t_medio_c"], 2), "soh": round(d.soh, 5)}])[-50:]
        r["soh"] = self.desgaste.soh
        self.reiniciar(soc_final, None)
        return r

    def telemetria(self, i_media: float | None = None) -> dict:
        i_m = self.i if i_media is None else i_media
        return {"soc": self.soc, "v": self.v, "v_celula": self.v_celula, "i": self.i, "p": self.p,
                "temp_c": self.temp, "soh": self.desgaste.soh, "ciclos_eq": self.desgaste.ciclos_eq,
                "n_recargas": self.desgaste.n_recargas, "r0_mohm": self.r0() * 1000.0,
                "ah_voo": self.ah_ciclo, "wh_voo": self.wh_ciclo, "alerta": self.alerta,
                "reformar": self.desgaste.reformar,
                "autonomia_min": self.autonomia_restante_min(i_m)}


def _dims_pack(hw: Hardware) -> list[float]:
    """Dimensões (m) do pack a partir da célula e do arranjo S×P (cilíndricas deitadas lado a lado)."""
    cel = hw.bateria.celula
    n = hw.bateria.s * hw.bateria.p
    if len(cel.dims_mm) == 2:                       # cilíndrica (diâmetro, comprimento)
        d, comp = (x / 1000.0 for x in cel.dims_mm)
        colunas = math.ceil(n / 2) if n > 2 else n
        linhas = 2 if n > 2 else 1
        return [comp, colunas * d, linhas * d]
    if len(cel.dims_mm) == 3:                       # pouch (c, l, a por célula) empilhada
        c, l_, a = (x / 1000.0 for x in cel.dims_mm)
        return [c, l_, a * n]
    vol = hw.bateria.massa / 2200.0                 # densidade típica de pack ≈ 2,2 kg/L
    lado = vol ** (1.0 / 3.0)
    return [1.6 * lado, 1.0 * lado, 0.62 * lado]
