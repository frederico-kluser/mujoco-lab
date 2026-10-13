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

DOIS CAMINHOS, A MESMA TRAJETÓRIA (2026-10-12). `passo` despacha para `_passo_escalar` — as contas acima em `float`
do Python, sem NumPy (medido: 86 % do `env.step` era despacho do NumPy em vetores de 3–4) — ou, se a aritmética
escalar não reproduzir bit a bit o NumPy/BLAS desta máquina (`escalar.OK`), para `_passo_vetorial`, o código
vetorial de origem. A prova de que os dois (e o código anterior a esta otimização) dão `qpos`/`qvel`/sensores/bateria
IDÊNTICOS bit a bit é `experiments/09_drone_hover_rl/bench_treino.py identidade`.
"""
from __future__ import annotations

import mujoco
import numpy as np

from . import escalar
from .aero import Aerodinamica, FlagsAero
from .bateria import EstadoDesgaste, ModeloBateria
from .componentes import Hardware
from .modelo import REACOES, ROTORES, SITES_ROTOR
from .propulsao import Propulsao
from .sensores import IMU, Barometro, FluxoOptico, MonitorBateria, Telemetro, _sortear

ALTURA_SEM_SOLO = 50.0      # m — altura usada quando o raio não encontra chão

_fma = escalar.fma
_mj_step1, _mj_step2, _mj_ray = mujoco.mj_step1, mujoco.mj_step2, mujoco.mj_ray
_F64 = np.dtype(np.float64)


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


def _lista4(acelerador) -> list:
    """Acelerador por motor → lista de 4 floats (ndarray de qualquer tipo real, lista, tuplo ou escalar)."""
    if type(acelerador) is np.ndarray and acelerador.dtype is _F64 and acelerador.shape == (4,):
        return acelerador.tolist()
    return np.broadcast_to(np.asarray(acelerador, dtype=float), (4,)).tolist()


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
        self._detalhe: dict | tuple = {}
        self._alt = [ALTURA_SEM_SOLO] * 4
        self._kappa_t = [1.0] * 4
        self.n_passos = 0
        self._fator_frame = 1.0 - hw.frame.perda_download if self.aero.flags.download else 1.0
        # caminho escalar: VISTAS fixas da memória do MuJoCo (o `MjData` não muda de sítio), lidas com um
        # `.tolist()` por passo, e os índices de `ctrl` como inteiros
        self._escalar = escalar.OK
        c = self.corpo
        self._v_xmat, self._v_xpos, self._v_xipos = data.xmat[c], data.xpos[c], data.xipos[c]
        self._v_qvel = data.qvel[0:6]
        self._v_vento = model.opt.wind
        self._v_sites = [data.site_xpos[int(i)] for i in self.sites]
        s0 = int(self.sites[0])                      # os 4 sites seguidos (o normal) leem-se de uma só vez
        self._v_sites4 = data.site_xpos[s0:s0 + 4] if [int(i) for i in self.sites] == list(range(s0, s0 + 4)) else None
        self._v_ctrl, self._v_xfrc, self._v_sd = data.ctrl, data.xfrc_applied[c], data.sensordata
        self._i_t = [int(i) for i in self.slot_t]
        self._i_q = [int(i) for i in self.slot_q]

    # ------------------------------------------------------------------ vistas ndarray (a API de sempre)
    @property
    def altura_rotores(self) -> np.ndarray:
        """Altura de cada rotor ao chão (m) no último passo."""
        return np.array(self._alt, dtype=float)

    @altura_rotores.setter
    def altura_rotores(self, valor) -> None:
        self._alt = np.broadcast_to(np.asarray(valor, dtype=float), (4,)).tolist()

    @property
    def kappa_t(self) -> np.ndarray:
        """κ_T de cada rotor (solo × inflow × VRS) no último passo."""
        return np.array(self._kappa_t, dtype=float)

    @kappa_t.setter
    def kappa_t(self, valor) -> None:
        self._kappa_t = np.broadcast_to(np.asarray(valor, dtype=float), (4,)).tolist()

    @property
    def detalhe_aero(self) -> dict:
        """{"solo", "inflow", "vrs"}: o fator de cada efeito por rotor no último passo ({} antes do 1.º)."""
        d = self._detalhe
        if isinstance(d, dict):
            return d
        return {"solo": np.array(d[0]), "inflow": np.array(d[1]), "vrs": np.array(d[2])}

    @detalhe_aero.setter
    def detalhe_aero(self, valor: dict) -> None:
        self._detalhe = valor

    # ------------------------------------------------------------------ estado
    # `False` só serve à prova de identidade contra o código de antes de 2026-10-13 (`bench_treino.py`), em que o
    # ruído do VRS atravessava os reinícios — é a ÚNICA diferença deliberada de trajetória em relação a ele.
    repor_aero_no_reinicio = True

    def reiniciar(self, soc0: float = 1.0, temperatura_c: float | None = None, armado: bool = False,
                  omega=None) -> None:
        """Novo voo: rotores parados (ou `omega`), pack descansado com `soc0`, sensores recalibrados.

        Chamar DEPOIS de pôr o estado do MuJoCo (qpos/qvel) e de um `mj_forward` (os sensores arrancam
        com a verdade atual)."""
        self.prop.reiniciar(omega)
        self.prop.armar(armado)
        if self.repor_aero_no_reinicio:
            self.aero.reiniciar()                # o ruído do VRS recomeça do zero ⇒ `reset(seed)` é reprodutível
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
    def _resolver_tensao(self, corrente_bus=None) -> float:
        """Newton em V: f(V) = V − (OCV − V_rc) + R₀·(I_m(V) + P_e/V) = 0 (2–4 iterações).

        `corrente_bus` = a função (I, dI/dV) dos 4 ESC à tensão V (por omissão a vetorial da propulsão)."""
        corrente_bus = corrente_bus or self.prop.corrente_bus
        e = self.bat.tensao_aberta()
        r0 = self.bat.r0()
        p_e = 0.0 if self.brownout else self.p_eletronica
        v = max(self.v_bus, 0.5 * e, 1e-3)
        for _ in range(8):
            i_m, di_m = corrente_bus(v)
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
        if self._escalar:
            self._passo_escalar(acelerador)
        else:
            self._passo_vetorial(acelerador)

    def _passo_escalar(self, acelerador=None) -> None:
        """O passo em escalares Python: as MESMAS contas de `_passo_vetorial`, pela mesma ordem de operações.

        Onde o vetorial usa o BLAS, a expressão escalar é a que o kernel desta máquina calcula — verificada no
        arranque em `escalar.verificar`: `A @ x` → 0 + fma(a2, x2, fma(a0, x0, a1·x1)) por linha; `np.dot` de
        colunas de 4 → (0 + (p0 + p2)) + (0 + (p1 + p3)); somas de 4 parcelas em sequência a partir de +0,0 (os
        `0.0 +` não são ruído: fixam o SINAL de um resultado nulo, como os acumuladores do NumPy/BLAS).
        """
        m, d = self.model, self.data
        prop, aero = self.prop, self.aero
        flags = aero.flags
        if acelerador is not None:
            prop._definir_acelerador_l(_lista4(acelerador))
        _mj_step1(m, d)

        # cinemática atual dos rotores (mundo): R (linha a linha), origem, v e ω (ω da junta livre vem LOCAL)
        r00, r01, r02, r10, r11, r12, r20, r21, r22 = self._v_xmat.tolist()
        ox, oy, oz = self._v_xpos.tolist()
        vx, vy, vz, wl0, wl1, wl2 = self._v_qvel.tolist()
        ux, uy, uz = self._v_vento.tolist()
        wx = 0.0 + _fma(r02, wl2, _fma(r00, wl0, r01 * wl1))       # ω_mundo = R·ω_local
        wy = 0.0 + _fma(r12, wl2, _fma(r10, wl0, r11 * wl1))
        wz = 0.0 + _fma(r22, wl2, _fma(r20, wl0, r21 * wl1))
        v4 = self._v_sites4
        pos_r = v4.tolist() if v4 is not None else [vista.tolist() for vista in self._v_sites]
        v_ar, v_axial = [], []
        for px, py, pz in pos_r:
            rx, ry, rz = px - ox, py - oy, pz - oz
            ax = vx + (wy * rz - wz * ry) - ux                # v do rotor (v + ω × r) − vento
            ay = vy + (wz * rx - wx * rz) - uy
            az = vz + (wx * ry - wy * rx) - uz
            v_ar.append((ax, ay, az))
            v_axial.append(0.0 + _fma(az, r22, _fma(ax, r02, ay * r12)))       # v_ar · ẑ_corpo

        # altura de cada rotor ao chão (raio para baixo, sem o próprio drone)
        alt = self._alt
        if flags.solo:
            raio, grupo, corpo, gid = self._raio, self._geomgroup, self.corpo, self._gid
            for i, vista in enumerate(self._v_sites):
                h = _mj_ray(m, d, vista, raio, grupo, 1, corpo, gid)
                alt[i] = h if h >= 0.0 else ALTURA_SEM_SOLO

        kt, kq, g_solo, k_inflow, k_vrs = aero._fatores_l(alt, v_axial, prop._omega, self.dt, self.rng)
        self._kappa_t = kt
        self._detalhe = (g_solo, k_inflow, k_vrs)

        # barramento e rotores
        v = self._resolver_tensao(prop._corrente_bus_l)
        if v < self.hw.v_brownout and not self.brownout:
            self.brownout = True                             # BEC/ESC desligam — o drone cai
            prop.armar(False)
            v = self._resolver_tensao(prop._corrente_bus_l)
        empuxo, reacao = prop._passo_l(self.dt, v, kq, kt)
        ctrl, ff = self._v_ctrl, self._fator_frame
        for i, t in zip(self._i_t, empuxo):
            ctrl[i] = t * ff                                  # o rasto que bate na estrutura (download)
        for i, q in zip(self._i_q, reacao):
            ctrl[i] = q

        # arrasto de rotor (força no plano do rotor, aplicada no rotor) → força e binário no CM
        omega = prop._omega
        if flags.arrasto_rotor:
            cd0, cd1 = aero._cd_l
            forca = []
            for (ax, ay, az), w in zip(v_ar, omega):
                fx = -cd0 * w * (0.0 + _fma(az, r20, _fma(ax, r00, ay * r10)))       # −c_d·ω·(v_ar · x̂_corpo)
                fy = -cd1 * w * (0.0 + _fma(az, r21, _fma(ax, r01, ay * r11)))       # −c_d·ω·(v_ar · ŷ_corpo)
                forca.append((fx * r00 + fy * r01, fx * r10 + fy * r11, fx * r20 + fy * r21))
        else:
            forca = [(0.0, 0.0, 0.0)] * 4
        cx, cy, cz = self._v_xipos.tolist()
        (bx0, by0, bz0), (bx1, by1, bz1), (bx2, by2, bz2), (bx3, by3, bz3) = (
            (p[0] - cx, p[1] - cy, p[2] - cz) for p in pos_r)                # braços CM → rotor
        (fx0, fy0, fz0), (fx1, fy1, fz1), (fx2, fy2, fz2), (fx3, fy3, fz3) = forca
        # Σ b_i × f_i — cada produto interno pela ordem do `ddot` de colunas: (0 + (p0 + p2)) + (0 + (p1 + p3))
        tx = (((0.0 + (by0 * fz0 + by2 * fz2)) + (0.0 + (by1 * fz1 + by3 * fz3)))
              - ((0.0 + (bz0 * fy0 + bz2 * fy2)) + (0.0 + (bz1 * fy1 + bz3 * fy3))))
        ty = (((0.0 + (bz0 * fx0 + bz2 * fx2)) + (0.0 + (bz1 * fx1 + bz3 * fx3)))
              - ((0.0 + (bx0 * fz0 + bx2 * fz2)) + (0.0 + (bx1 * fz1 + bx3 * fz3))))
        tz = (((0.0 + (bx0 * fy0 + bx2 * fy2)) + (0.0 + (bx1 * fy1 + bx3 * fy3)))
              - ((0.0 + (by0 * fx0 + by2 * fx2)) + (0.0 + (by1 * fx1 + by3 * fx3))))
        if flags.giroscopico:                                 # τ = −Ω × (Σ h_i)·ẑ_corpo
            hs = -prop._momento_angular_soma_l()
            tx = tx + hs * (wy * r22 - wz * r12)
            ty = ty + hs * (wz * r02 - wx * r22)
            tz = tz + hs * (wx * r12 - wy * r02)
        else:
            tx, ty, tz = tx + 0.0, ty + 0.0, tz + 0.0
        xfrc = self._v_xfrc
        xfrc[0] = (((0.0 + fx0) + fx1) + fx2) + fx3            # f_arrasto.sum(axis=0)
        xfrc[1] = (((0.0 + fy0) + fy1) + fy2) + fy3
        xfrc[2] = (((0.0 + fz0) + fz1) + fz2) + fz3
        xfrc[3] = tx
        xfrc[4] = ty
        xfrc[5] = tz

        _mj_step2(m, d)

        # bateria: corrente REAL deste passo (motores + eletrónica)
        p_e = 0.0 if self.brownout else self.p_eletronica
        b0, b1, b2, b3 = prop._i_bus
        self.i_total = i_total = ((((0.0 + b0) + b1) + b2) + b3) + p_e / v
        self.bat.passo(i_total, self.dt)
        self.v_bus = v_bus = self.bat.v

        # sensores (sensordata = estado no início deste passo, com as forças aplicadas): prepara todos, sorteia os
        # normais de todos numa só chamada ao gerador e conclui pela mesma ordem (a sequência é a de sempre)
        tt = float(d.time)
        w0, w1, w2, w3 = omega
        carga = (((((0.0 + w0) + w1) + w2) + w3) / 4) / self.omega_h        # np.mean(ω)/ω_pairagem
        sd = self._v_sd.tolist()
        imu, tof, fluxo, baro, monitor = self.imu, self.tof, self.fluxo, self.baro, self.monitor
        n = imu._preparar(tt, sd, carga)
        if tof is not None:
            n += tof._preparar(tt, sd)
        if fluxo is not None:
            n += fluxo._preparar(tt, sd)
        if baro is not None:
            n += baro._preparar(tt, float(self._v_xpos[2]))
        n += monitor._preparar(tt, v_bus, i_total)
        z = _sortear(self.rng, n)
        k = imu._concluir(z, 0)
        if tof is not None:
            k = tof._concluir(z, k)
        if fluxo is not None:
            k = fluxo._concluir(z, k)
        if baro is not None:
            k = baro._concluir(z, k)
        monitor._concluir(z, k)
        self.n_passos += 1

    def _passo_vetorial(self, acelerador=None) -> None:
        """O passo vetorial de ORIGEM (NumPy/BLAS) — a referência, e o caminho usado quando `escalar.OK` é False."""
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
        alt = np.array(self._alt)
        if self.aero.flags.solo:
            for i in range(4):
                h = mujoco.mj_ray(m, d, pos_r[i], self._raio, self._geomgroup, 1, self.corpo, self._gid)
                alt[i] = h if h >= 0.0 else ALTURA_SEM_SOLO
            self._alt = alt.tolist()

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

        omega = self.prop.omega
        f_arrasto = self.aero.forca_arrasto(v_ar, (ex, ey, ez), omega)
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
        carga = float(np.mean(omega)) / self.omega_h
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
