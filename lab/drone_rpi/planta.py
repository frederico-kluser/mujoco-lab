"""lab.drone_rpi.planta — o HARDWARE simulado a cada passo de física (motores+ESC, bateria, ar, sensores).

Um passo (dt = timestep do modelo, 2 ms):

    mj_step1                         cinemática/velocidades/sensores do estado ATUAL (sem atraso)
    cinemática dos rotores           posição, eixo, velocidade do ar (v − vento), altura ao solo (mj_ray)
    κ_T, κ_Q                         efeito de solo, inflow axial, VRS (aero.py)
    V_bus (Newton)                   V = OCV − V_rc − R₀·(I_motores(V) + P_eletrónica/V)   ← bateria ↔ ESC
    rotores                          J·ω̇ = K_t·I − Q₀ − κ_Q·kq·ω²  (propulsao.py)
    forças                           ctrl[rotor_i] = κ_T·kf·ω², ctrl[reacao_i] = −s_i·(Q_aero + J·ω̇),
                                     xfrc_applied = arrasto de rotor + giroscópico
    mj_step2                         dinâmica + contactos + integração (a física é TODA do MuJoCo)
    bateria.passo(I_total)           SoC (Coulomb), V_rc, temperatura, ciclo
    sensores.passo                   IMU, ToF, fluxo, barómetro, monitor de bateria (com erro)

Ledger de potência (o que a bateria fornece): P_total = Σ V_bus·I_bus,i (motores+ESC) + P_eletrónica
(RPi 5, FC, sensores ÷ η_BEC) — tudo a partir do que os motores REALMENTE puxam.
Brownout: V_bus < v_brownout ⇒ ESC e eletrónica desligam (o drone cai pela física).
"""
from __future__ import annotations

import mujoco
import numpy as np

from .aero import Aerodinamica, FlagsAero
from .bateria import EstadoDesgaste, ModeloBateria
from .componentes import Hardware
from .modelo import REACOES, ROTORES, SITES_ROTOR
from .propulsao import Propulsao
from .sensores import IMU, Barometro, FluxoOptico, MonitorBateria, Telemetro

ALTURA_SEM_SOLO = 50.0      # m — altura usada quando o raio não encontra chão


def _cruz_linhas(w: np.ndarray, r: np.ndarray) -> np.ndarray:
    """w × r para cada linha de `r` (4, 3) — explícito (o np.cross genérico é ~10× mais lento aqui)."""
    out = np.empty_like(r)
    out[:, 0] = w[1] * r[:, 2] - w[2] * r[:, 1]
    out[:, 1] = w[2] * r[:, 0] - w[0] * r[:, 2]
    out[:, 2] = w[0] * r[:, 1] - w[1] * r[:, 0]
    return out


def _cruz_soma(r: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Σ_i r_i × f_i para (4, 3) × (4, 3)."""
    return np.array([np.dot(r[:, 1], f[:, 2]) - np.dot(r[:, 2], f[:, 1]),
                     np.dot(r[:, 2], f[:, 0]) - np.dot(r[:, 0], f[:, 2]),
                     np.dot(r[:, 0], f[:, 1]) - np.dot(r[:, 1], f[:, 0])])


class Planta:
    """Motores/ESC + bateria + aerodinâmica + sensores de um drone `Hardware` sobre (model, data)."""

    def __init__(self, hw: Hardware, model: mujoco.MjModel, data: mujoco.MjData, *,
                 flags_aero: FlagsAero | None = None, desgaste: EstadoDesgaste | None = None,
                 rng: np.random.Generator | None = None, perfil_eletronica: str = "voo"):
        self.hw, self.model, self.data = hw, model, data
        self.dt = float(model.opt.timestep)
        self.rng = rng if rng is not None else np.random.default_rng()
        self.corpo = model.body("drone").id
        self.slot_t = np.array([model.actuator_ctrladr[model.actuator(n).id] for n in ROTORES])
        self.slot_q = np.array([model.actuator_ctrladr[model.actuator(n).id] for n in REACOES])
        self.sites = np.array([model.site(n).id for n in SITES_ROTOR])
        self.prop = Propulsao(hw)
        self.bat = ModeloBateria(hw, desgaste)
        self.aero = Aerodinamica(hw, flags_aero)
        s = hw.sensores
        self.imu = IMU(model, data, s["imu"])
        self.tof = Telemetro(model, data, s["tof"]) if "tof" in s else None
        self.fluxo = FluxoOptico(model, data, s["fluxo"]) if "fluxo" in s else None
        self.baro = Barometro(model, data, s["baro"], self.corpo) if "baro" in s else None
        self.monitor = MonitorBateria(self.dt, s.get("monitor", {}))
        self.perfil = perfil_eletronica
        self.p_eletronica = hw.potencia_eletronica(perfil_eletronica)
        self.omega_h = self.aero.omega_h
        self._geomgroup = None
        self._raio = np.array([0.0, 0.0, -1.0])
        self._gid = np.zeros(1, dtype=np.int32)
        self.v_bus = self.bat.v
        self.i_total = 0.0
        self.brownout = False
        self.detalhe_aero: dict = {}
        self.altura_rotores = np.full(4, ALTURA_SEM_SOLO)
        self.kappa_t = np.ones(4)
        self.n_passos = 0
        self._fator_frame = 1.0 - hw.frame.perda_download if self.aero.flags.download else 1.0

    # ------------------------------------------------------------------ estado
    def reiniciar(self, soc0: float = 1.0, temperatura_c: float | None = None, armado: bool = False,
                  omega=None) -> None:
        """Novo voo: rotores parados (ou `omega`), pack descansado com `soc0`, sensores recalibrados.

        Chamar DEPOIS de pôr o estado do MuJoCo (qpos/qvel) e de um `mj_forward` (os sensores arrancam
        com a verdade atual)."""
        self.prop.reiniciar(omega)
        self.prop.armar(armado)
        self.bat.reiniciar(soc0, temperatura_c)
        self.v_bus = self.bat.v
        self.i_total = self.p_eletronica / max(self.v_bus, 1e-3)
        self.brownout = False
        self.data.ctrl[self.slot_t] = self.prop.empuxos()
        self.data.ctrl[self.slot_q] = 0.0
        self.data.xfrc_applied[self.corpo] = 0.0
        t0 = float(self.data.time)
        self.imu.reiniciar(self.rng, t0)
        for s in (self.tof, self.fluxo, self.baro):
            if s is not None:
                s.reiniciar(self.rng, t0)
        self.monitor.reiniciar(self.rng, self.v_bus, self.i_total, t0)
        self.n_passos = 0

    def reiniciar_sensores(self) -> None:
        """Recalibra os sensores no instante atual (bias novos, histórico = verdade atual, relógio de
        amostragem realinhado) — usado quando o ambiente põe o tempo do episódio a 0 depois de assentar."""
        t0 = float(self.data.time)
        self.imu.reiniciar(self.rng, t0)
        for s in (self.tof, self.fluxo, self.baro):
            if s is not None:
                s.reiniciar(self.rng, t0)
        self.monitor.reiniciar(self.rng, self.v_bus, self.i_total, t0)

    def armar(self, armado: bool = True) -> None:
        if not self.brownout:
            self.prop.armar(armado)

    # ------------------------------------------------------------------ bateria ↔ ESC
    def _resolver_tensao(self) -> float:
        """Newton em V: f(V) = V − (OCV − V_rc) + R₀·(I_m(V) + P_e/V) = 0 (2–4 iterações)."""
        e = self.bat.tensao_aberta()
        r0 = self.bat.r0()
        p_e = 0.0 if self.brownout else self.p_eletronica
        v = max(self.v_bus, 0.5 * e, 1e-3)
        for _ in range(8):
            i_m, di_m = self.prop.corrente_bus(v)
            f = v - e + r0 * (i_m + p_e / v)
            df = 1.0 + r0 * (di_m - p_e / (v * v))
            dv = -f / df if df > 1e-9 else -f
            v_novo = max(v + dv, 1e-3)
            if abs(v_novo - v) < 1e-9:
                v = v_novo
                break
            v = v_novo
        return v

    # ------------------------------------------------------------------ passo de física
    def passo(self, acelerador=None) -> None:
        """Um passo de física com o acelerador por motor [0, 1] (None = mantém o último)."""
        m, d = self.model, self.data
        if acelerador is not None:
            self.prop.definir_acelerador(acelerador)
        mujoco.mj_step1(m, d)

        # cinemática atual dos rotores (mundo)
        rmat = d.xmat[self.corpo].reshape(3, 3)
        ex, ey, ez = rmat[:, 0], rmat[:, 1], rmat[:, 2]
        origem = d.xpos[self.corpo]
        w_mundo = rmat @ d.qvel[3:6]                         # ω da junta livre vem no frame LOCAL
        pos_r = d.site_xpos[self.sites]
        v_r = d.qvel[0:3] + _cruz_linhas(w_mundo, pos_r - origem)
        v_ar = v_r - m.opt.wind
        v_axial = v_ar @ ez

        # altura de cada rotor ao chão (raio para baixo, sem o próprio drone)
        alt = self.altura_rotores
        if self.aero.flags.solo:
            for i in range(4):
                h = mujoco.mj_ray(m, d, pos_r[i], self._raio, self._geomgroup, 1, self.corpo, self._gid)
                alt[i] = h if h >= 0.0 else ALTURA_SEM_SOLO

        kt, kq, self.detalhe_aero = self.aero.fatores(alt, v_axial, self.prop.omega, self.dt, self.rng)
        self.kappa_t = kt

        # barramento e rotores
        v = self._resolver_tensao()
        if v < self.hw.v_brownout and not self.brownout:
            self.brownout = True                             # BEC/ESC desligam — o drone cai
            self.prop.armar(False)
            v = self._resolver_tensao()
        self.prop.passo(self.dt, v, kq)
        t = self.prop.empuxos(kt)
        d.ctrl[self.slot_t] = t * self._fator_frame        # o rasto que bate na estrutura (download)
        d.ctrl[self.slot_q] = self.prop.binarios_reacao()

        f_arrasto = self.aero.forca_arrasto(v_ar, (ex, ey, ez), self.prop.omega)
        com = d.xipos[self.corpo]
        tau = _cruz_soma(pos_r - com, f_arrasto)
        tau += self.aero.binario_giroscopico(w_mundo, self.prop.momento_angular(), ez)
        d.xfrc_applied[self.corpo, :3] = f_arrasto.sum(axis=0)
        d.xfrc_applied[self.corpo, 3:] = tau

        mujoco.mj_step2(m, d)

        # bateria: corrente REAL deste passo (motores + eletrónica)
        p_e = 0.0 if self.brownout else self.p_eletronica
        self.i_total = float(self.prop.i_bus.sum()) + p_e / v
        self.bat.passo(self.i_total, self.dt)
        self.v_bus = self.bat.v

        # sensores (sensordata = estado no início deste passo, com as forças aplicadas)
        tt = float(d.time)
        carga = float(np.mean(self.prop.omega)) / self.omega_h
        self.imu.passo(tt, self.rng, carga)
        if self.tof is not None:
            self.tof.passo(tt, self.rng)
        if self.fluxo is not None:
            self.fluxo.passo(tt, self.rng)
        if self.baro is not None:
            self.baro.passo(tt, self.rng)
        self.monitor.passo(tt, self.rng, self.v_bus, self.i_total)
        self.n_passos += 1

    # ------------------------------------------------------------------ leituras
    def potencias(self) -> dict:
        """Ledger de potência (W) do passo atual."""
        p_mot = float(self.v_bus * self.prop.i_bus.sum())
        p_e = 0.0 if self.brownout else self.p_eletronica
        consumidores = {c.id: c.p(self.perfil) for c in self.hw.consumidores}
        for papel, s in self.hw.sensores.items():
            consumidores[f"sensor_{papel}"] = float(s.get("potencia_w", 0.0))
        p5 = sum(consumidores.values())
        return {"motores": p_mot, "eletronica": p_e, "bec_perdas": p_e - p5 if p_e > 0 else 0.0,
                "consumidores_5v": consumidores, "total": p_mot + p_e}

    def omega_max_atual(self) -> float:
        """Teto de rotação com a tensão ATUAL do barramento (rad/s) — decai com a descarga."""
        return self.hw.omega_max(self.v_bus)

    def telemetria(self) -> dict:
        b = self.bat.telemetria()
        pw = self.potencias()
        return {"bateria": b, "potencia": pw, "motores": self.prop.telemetria(),
                "v_bus": self.v_bus, "i_total": self.i_total, "brownout": self.brownout,
                "omega_max": self.omega_max_atual(), "t_max_rotor": self.hw.kf * self.omega_max_atual() ** 2,
                "kappa_t": self.kappa_t.copy(), "altura_rotores": self.altura_rotores.copy()}


def potencia_pairagem_bancada(hw: Hardware, v_bus: float) -> float:
    """Potência elétrica TOTAL em pairagem pelo regime estacionário (W) — o mesmo que `ponto_pairagem`."""
    return hw.ponto_pairagem(v_bus)["p_total"]


def ligar_rng(planta: Planta, rng: np.random.Generator) -> None:
    """Troca o gerador aleatório da planta (o ambiente usa o `np_random` do Gymnasium)."""
    planta.rng = rng


__all__ = ["Planta", "ligar_rng", "potencia_pairagem_bancada"]
