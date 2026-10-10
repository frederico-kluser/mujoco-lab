"""lab.drone_rpi — o drone que o dono vai CONSTRUIR, com peças REAIS trocáveis: RPi 5 a bordo, 4 motores
brushless com dinâmica elétrica real, bateria com queda de tensão/SoC/desgaste, aerodinâmica que o MuJoCo
não tem (solo, inflow, VRS, arrasto de rotor, giroscópico) e sensores com modelo de erro.

Esta camada modela o HARDWARE — não há código de estabilização/controlo/voo aqui (isso é do dono; a malha
interna do FC e o estimador de bordo do experimento vivem em `experiments/09_drone_hover_rl/`).

    from lab import drone_rpi as dr
    hw = dr.hardware()                    # build ATIVO de models/drone_rpi/builds.json (ou dr.hardware("nome"))
    model, data = dr.carregar(hw)         # MJCF gerado das peças (MjSpec), origem do corpo no CM
    planta = dr.Planta(hw, model, data)   # motores+ESC, bateria, aerodinâmica, sensores
    planta.reiniciar(soc0=1.0, armado=True)
    planta.passo([0.5, 0.5, 0.5, 0.5])    # 1 passo de física com 50 % de acelerador em cada motor
    dr.ler_bateria(planta), dr.ler_motores(planta), dr.ler_imu(planta), dr.ler_estado(model, data)

Peças, fontes e builds: `models/drone_rpi/componentes.json` + `builds.json` (ver o README ao lado).
Trocar motor/bateria = `experiments/09_drone_hover_rl/hardware.py usar <build>` (ou `montar`).
PREMISSA DE REALISMO (regra do dono): a política só vê o que os sensores medem; posição/velocidade/atitude
exatas (`ler_estado`) são informação privilegiada — recompensa e crítico, nunca a observação do ator.
"""
from __future__ import annotations

import mujoco
import numpy as np

from . import aero, bateria, componentes, modelo, propulsao, sensores
from .aero import Aerodinamica, FlagsAero, ganho_solo
from .bateria import EstadoDesgaste, ModeloBateria, perda_por_ciclo
from .componentes import (
    GRAVIDADE,
    RHO_AR,
    Hardware,
    autonomia_estimada,
    carregar_builds,
    carregar_catalogo,
    nome_build_ativo,
    resolver,
)
from .modelo import REACOES, ROTORES, SITES_ROTOR, construir_spec, exportar_xml
from .planta import Planta
from .propulsao import Propulsao, quantiza_dshot


def hardware(build: str | dict | None = None) -> Hardware:
    """O build resolvido (None = o ATIVO em `builds.json`)."""
    return resolver(build)


def carregar(hw: Hardware | str | None = None) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """(model, data) gerados das peças do build (o drone nasce a 0,3 m; pouse-o pela física)."""
    if not isinstance(hw, Hardware):
        hw = resolver(hw)
    return modelo.carregar(hw)


# --------------------------------------------------------------------------------------- definir_*
def definir_aceleradores(planta: Planta, acelerador) -> np.ndarray:
    """Acelerador por motor em [0, 1] (cortado) → ciclo útil DShot quantizado. Devolve o aplicado."""
    return planta.prop.definir_acelerador(np.clip(np.asarray(acelerador, dtype=float).reshape(4), 0.0, 1.0))


def definir_armado(planta: Planta, armado: bool) -> None:
    """Arma/desarma os ESC (desarmado = roda livre, sem travagem)."""
    planta.armar(armado)


def definir_vento(model: mujoco.MjModel, vx: float, vy: float, vz: float = 0.0) -> None:
    """Vento uniforme (m/s, mundo) no modelo de fluido do MuJoCo."""
    model.opt.wind[:] = (vx, vy, vz)


# --------------------------------------------------------------------------------------- ler_*
def ler_bateria(planta: Planta) -> dict:
    return planta.bat.telemetria()


def ler_motores(planta: Planta) -> dict:
    return planta.prop.telemetria()


def ler_imu(planta: Planta) -> dict:
    """Leituras MEDIDAS (com erro) — o que o hardware entrega ao RPi."""
    return {"giro": planta.imu.giro.ler(), "acc": planta.imu.acc.ler(),
            "tof": (planta.tof.distancia, planta.tof.valido) if planta.tof else None,
            "fluxo": (planta.fluxo.fluxo.copy(), planta.fluxo.valido) if planta.fluxo else None,
            "baro": planta.baro.altitude if planta.baro else None,
            "v_bat": planta.monitor.tensao, "i_bat": planta.monitor.corrente}


def ler_estado(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """Estado PRIVILEGIADO (só recompensa/crítico/telemetria): posição do CM, velocidade, atitude, ω."""
    return {"pos": np.array(data.sensor("pos").data), "quat": np.array(data.sensor("quat").data),
            "vel": np.array(data.sensor("vel").data), "omega_corpo": np.array(data.qvel[3:6])}


# --------------------------------------------------------------------------------------- modos (abertos)
def modo_desligado(planta: Planta, tau: float) -> None:
    """Desarmado: o drone assenta pela física."""
    planta.armar(False)


def modo_gaz_fixo(planta: Planta, tau: float, fracao: float = 0.5) -> None:
    """Acelerador constante nos 4 motores, SEM realimentação (para ver a planta sozinha)."""
    planta.armar(True)
    definir_aceleradores(planta, [fracao] * 4)


def modo_rampa(planta: Planta, tau: float, duracao: float = 5.0) -> None:
    """Rampa de acelerador 0→100 % em `duracao` s (curva de empuxo/corrente da bancada)."""
    planta.armar(True)
    definir_aceleradores(planta, [min(1.0, tau / duracao)] * 4)


MODOS = {"desligado": modo_desligado, "gaz_fixo": modo_gaz_fixo, "rampa": modo_rampa}

__all__ = [
    "GRAVIDADE", "MODOS", "REACOES", "RHO_AR", "ROTORES", "SITES_ROTOR", "Aerodinamica", "EstadoDesgaste",
    "FlagsAero", "Hardware", "ModeloBateria", "Planta", "Propulsao", "aero", "autonomia_estimada", "bateria",
    "carregar", "carregar_builds", "carregar_catalogo", "componentes", "construir_spec", "definir_aceleradores",
    "definir_armado", "definir_vento", "exportar_xml", "ganho_solo", "hardware", "ler_bateria", "ler_estado",
    "ler_imu", "ler_motores", "modelo", "nome_build_ativo", "perda_por_ciclo", "propulsao", "quantiza_dshot",
    "resolver", "sensores",
]
