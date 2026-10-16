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

import math

import mujoco
import numpy as np

from . import escalar
from .aero import Aerodinamica, FlagsAero
from .bateria import EstadoDesgaste, ModeloBateria
from .componentes import Hardware
from .modelo import (
    ALCANCE_PROJETIL_M,
    DURACAO_CAMINHO_TIRO_S,
    DURACAO_FOGO_CANO_S,
    N_SLOTS_TIRO,
    REACOES,
    ROTORES,
    SITE_BOCA_CANO,
    SITES_ROTOR,
)
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
        # arma fixa no topo (Glock 25 .380 Auto): site `boca_cano`, geoms de fogo/ferrolho/projéteis e estado de tiro
        try:
            self.site_boca: int | None = int(model.site(SITE_BOCA_CANO).id)
        except KeyError:
            self.site_boca = None
        self._v_boca = data.site_xpos[self.site_boca] if self.site_boca is not None else None
        self._gid_ferrolho = self._geom_id("arma_ferrolho")
        self._pos_ferrolho0 = (
            model.geom_pos[self._gid_ferrolho].copy() if self._gid_ferrolho is not None else None
        )
        self._gids_fogo = [
            g for g in (
                self._geom_id("arma_fogo_nucleo"),
                self._geom_id("arma_fogo_cone"),
                self._geom_id("arma_fogo_cruz_h"),
                self._geom_id("arma_fogo_cruz_v"),
            ) if g is not None
        ]
        self._gids_projetil = [
            g for g in (self._geom_id(f"projetil_tiro_{k}") for k in range(N_SLOTS_TIRO)) if g is not None
        ]
        self._gids_caminho = [
            g for g in (self._geom_id(f"caminho_tiro_{k}") for k in range(N_SLOTS_TIRO)) if g is not None
        ]
        for gid in (*self._gids_fogo, *self._gids_projetil, *self._gids_caminho):
            model.geom_sameframe[gid] = 0
        if self._gid_ferrolho is not None:
            model.geom_sameframe[self._gid_ferrolho] = 0
        # bola alvo (`ponto` mocap + `ponto_esfera` geom) e câmara `fpv` para interseção balística e mira FPS
        self._gid_bola = self._geom_id("ponto_esfera")
        try:
            bid_bola = int(model.body("ponto").id)
            self._mocap_bola: int | None = int(model.body_mocapid[bid_bola])
        except KeyError:
            self._mocap_bola = None
        self.raio_bola = float(model.geom_size[self._gid_bola, 0]) if self._gid_bola is not None else 0.05
        try:
            self._cid_fpv: int | None = int(model.camera("fpv").id)
        except KeyError:
            self._cid_fpv = None
        self._tiros_ativos: list[list[float]] = []    # [[forca_n, passos_restantes], ...]
        self._disparos_visuais: list[dict] = []       # projéteis em voo (≤ 50 m) e caminhos visíveis (≤ 1,0 s)
        self._fogo_restante_s = 0.0                   # contador decrescente do efeito de fogo do cano (s)
        self._ferrolho_restante_s = 0.0               # ciclo de blowback do ferrolho (s)
        self.n_tiros = 0
        self.n_acertos_bola = 0
        self.n_erros_bola = 0
        self.gatilho_tiro = False
        self.forca_tiro_atual = 0.0
        self.ultimo_tiro: dict | None = None
        # carga útil dinâmica extra (kg) e massa/inércia de base do corpo `drone`
        self._massa_corpo_base = float(model.body_mass[c])
        self._inercia_corpo_base = model.body_inertia[c].copy()
        self.carga_extra_kg = 0.0
        # altura do eixo do cano acima do CM (m) e inércia de pitch I_yy (kg·m²) no corpo
        self.braco_z_arma = (
            float(model.site_pos[self.site_boca, 2]) if self.site_boca is not None else 0.0
        )
        q_inercia = np.zeros(9)
        mujoco.mju_quat2Mat(q_inercia, model.body_iquat[c])
        r_inercia = q_inercia.reshape(3, 3)
        i_corpo = r_inercia @ np.diag(model.body_inertia[c]) @ r_inercia.T
        self.inercia_corpo = np.diag(i_corpo).copy()

    def _geom_id(self, nome: str) -> int | None:
        try:
            return int(self.model.geom(nome).id)
        except KeyError:
            return None

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
        self._tiros_ativos.clear()
        self._limpar_visuais_tiro()
        self.n_tiros = 0
        self.n_acertos_bola = 0
        self.n_erros_bola = 0
        self.gatilho_tiro = False
        self.forca_tiro_atual = 0.0
        self.ultimo_tiro = None
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

    # ------------------------------------------------------------------ arma e recuo do tiro ("o soco")
    def disparar(self, n: int = 1) -> dict | None:
        """Dispara `n` tiro(s) da arma montada no topo do drone (`hw.arma`), entregando o impulso J_tiro
        no site `boca_cano` em `-x̂_corpo` ao longo de N = round(duracao / dt) passos de física.

        Física 100 % real (via `xfrc_applied` antes de `mj_step2`):
          · impulso linear: Δp = −n · J_tiro · x̂_corpo  ⇒  Δv = −n · J_tiro / m_total · x̂_corpo;
          · impulso angular no CM: ΔL = (p_boca − r_CM) × Δp  ⇒  no corpo, ΔL_y = −z_cano · n · J_tiro < 0
            (nariz sobe / cabra ao disparar porque a arma está fixa EM CIMA do drone, acima do CM).
        Devolve o registo do disparo (ou `None` se `n <= 0` ou o build não tiver arma).
        """
        n = int(n)
        arma = self.hw.arma
        if n <= 0 or arma is None:
            return None
        mujoco.mj_kinematics(self.model, self.data)
        mujoco.mj_comPos(self.model, self.data)
        n_passos = max(1, round(arma.duracao_impulso / self.dt))
        j_total = float(n) * arma.impulso_tiro
        f_passo = j_total / (n_passos * self.dt)
        self._tiros_ativos.append([f_passo, n_passos])
        self.n_tiros += n
        rmat = self._v_xmat.reshape(3, 3)
        ex = rmat[:, 0].copy()                   # +x̂_corpo no mundo (direção do projétil)
        soco_dir = (-ex).copy()                  # −x̂_corpo no mundo (direção do soco no drone)
        j_vec = soco_dir * j_total
        com = self._v_xipos.copy()
        p_boca = self._v_boca.copy() if self._v_boca is not None else (com + rmat @ np.array([0.0965, 0.0, self.braco_z_arma]))
        braco_mundo = p_boca - com
        l_vec = np.cross(braco_mundo, j_vec)
        massa_atual = float(self.model.body_mass.sum())
        azim_soco = float(math.degrees(math.atan2(soco_dir[1], soco_dir[0])) % 360.0)
        # velocidade inicial do projétil no mundo = velocidade da boca do cano + v₀·x̂_corpo (296 m/s)
        w_mundo = rmat @ self.data.qvel[3:6]
        v_boca = self.data.qvel[0:3] + np.cross(w_mundo, braco_mundo)
        v_proj0 = v_boca + arma.velocidade_boca * ex
        slot = (self.n_tiros - 1) % max(len(self._gids_projetil), 1)
        # Se o slot já estava ocupado por um tiro anterior (< 1 s), apaga o anterior e assume o slot
        self._disparos_visuais = [d for d in self._disparos_visuais if d["slot"] != slot]
        disp_visual = {
            "id": int(self.n_tiros),
            "slot": int(slot),
            "t0": float(self.data.time),
            "origem": p_boca.copy(),
            "direcao": ex.copy(),
            "pos": p_boca.copy(),
            "vel": v_proj0.copy(),
            "distancia_m": 0.0,
            "alcance_max_render_m": ALCANCE_PROJETIL_M,
            "duracao_caminho_s": DURACAO_CAMINHO_TIRO_S,
            "alcancou_50m": False,
            "acertou_bola": False,
            "bateu_chao": False,
            "parou": False,
            "resultado": "em_voo",
            "projetil_visivel": True,
            "caminho_visivel": True,
            "tempo_vida_s": 0.0,
        }
        self._disparos_visuais.append(disp_visual)
        self._fogo_restante_s = DURACAO_FOGO_CANO_S
        self._ferrolho_restante_s = 0.045
        self._aplicar_geoms_disparo(disp_visual)
        self._aplicar_fogo_e_ferrolho()
        self.ultimo_tiro = {
            "t": round(float(self.data.time), 4),
            "n": n,
            "tiros_acumulados": self.n_tiros,
            "acertos_bola": self.n_acertos_bola,
            "erros_bola": self.n_erros_bola,
            "acertou_bola": None,
            "resultado": "em_voo",
            "ponto_impacto": None,
            "distancia_impacto_m": None,
            "impulso_ns": round(j_total, 5),
            "forca_n": round(f_passo, 3),
            "duracao_s": round(n_passos * self.dt, 4),
            "passos_fisica": n_passos,
            "direcao_tiro": [round(float(v), 5) for v in ex],
            "direcao_soco": [round(float(v), 5) for v in soco_dir],
            "azimute_soco_graus": round(azim_soco, 2),
            "impulso_vec": [round(float(v), 5) for v in j_vec],
            "torque_impulso_vec": [round(float(v), 5) for v in l_vec],
            "delta_v_m_s": round(j_total / max(massa_atual, 1e-6), 5),
            "braco_z_m": round(self.braco_z_arma, 5),
            "delta_omega_pitch_rad_s": round(-self.braco_z_arma * j_total / max(float(self.inercia_corpo[1]), 1e-6), 5),
            "origem_boca": [round(float(v), 4) for v in p_boca],
            "velocidade_projetil_m_s": round(float(np.linalg.norm(v_proj0)), 2),
            "alcance_render_m": ALCANCE_PROJETIL_M,
            "duracao_caminho_s": DURACAO_CAMINHO_TIRO_S,
        }
        return self.ultimo_tiro

    def _limpar_visuais_tiro(self) -> None:
        """Esconde todos os geoms visuais de fogo do cano, projéteis e caminhos de tiro e repõe o ferrolho."""
        self._disparos_visuais.clear()
        self._fogo_restante_s = 0.0
        self._ferrolho_restante_s = 0.0
        m = self.model
        for gid in self._gids_fogo:
            m.geom_rgba[gid, 3] = 0.0
        for gid in self._gids_projetil:
            m.geom_rgba[gid, 3] = 0.0
            m.geom_pos[gid] = [0.0, 0.0, -10.0]
        for gid in self._gids_caminho:
            m.geom_rgba[gid, 3] = 0.0
            m.geom_pos[gid] = [0.0, 0.0, -10.0]
        if self._gid_ferrolho is not None and self._pos_ferrolho0 is not None:
            m.geom_pos[self._gid_ferrolho] = self._pos_ferrolho0

    def _aplicar_fogo_e_ferrolho(self) -> None:
        """Atualiza o efeito de fogo do cano (muzzle flash) e o recuo blowback do ferrolho da Glock 25."""
        m = self.model
        if self._fogo_restante_s > 0.0 and self._gids_fogo:
            frac = min(1.0, max(0.0, self._fogo_restante_s / DURACAO_FOGO_CANO_S))
            escala = 0.65 + 0.55 * math.sin(math.pi * frac)
            # nucleo branco-amarelado + cone laranja + labaredas cruzadas
            alphas = (0.96 * frac, 0.88 * frac, 0.78 * frac, 0.78 * frac)
            for gid, a in zip(self._gids_fogo, alphas, strict=False):
                m.geom_rgba[gid, 3] = a
            if len(self._gids_fogo) >= 2:
                m.geom_size[self._gids_fogo[0]] = [0.022 * escala, 0.012 * escala, 0.012 * escala]
                m.geom_size[self._gids_fogo[1]] = [0.065 * escala, 0.022 * escala, 0.022 * escala]
        elif self._gids_fogo:
            for gid in self._gids_fogo:
                m.geom_rgba[gid, 3] = 0.0
        if self._gid_ferrolho is not None and self._pos_ferrolho0 is not None:
            if self._ferrolho_restante_s > 0.0:
                # Blowback: recua 32 mm nos primeiros 12 ms e regressa à bateria até aos 45 ms
                tau = 0.045 - self._ferrolho_restante_s
                recuo = (tau / 0.012) if tau <= 0.012 else max(0.0, (0.045 - tau) / 0.033)
                m.geom_pos[self._gid_ferrolho, 0] = self._pos_ferrolho0[0] - 0.032 * recuo
            else:
                m.geom_pos[self._gid_ferrolho, 0] = self._pos_ferrolho0[0]

    def _aplicar_geoms_disparo(self, disp: dict) -> None:
        """Posiciona o geom do projétil (se d <= 50 m e não bateu) e a cápsula do caminho (se τ <= 1,0 s) no mundo.

        Escreve tanto em `model.geom_pos/quat/size` como diretamente em `data.geom_xpos/xmat` (e com
        `geom_sameframe=0`) para que a cápsula vá SEMPRE da boca do cano até ao ponto de impacto/50 m e
        NUNCA fique vertical do céu ao chão.
        """
        slot = disp["slot"]
        m, d = self.model, self.data
        if slot < len(self._gids_projetil):
            gid_p = self._gids_projetil[slot]
            if disp["projetil_visivel"]:
                m.geom_pos[gid_p] = disp["pos"]
                d.geom_xpos[gid_p] = disp["pos"]
                m.geom_rgba[gid_p] = [1.0, 0.84, 0.28, 1.0]
            else:
                m.geom_rgba[gid_p, 3] = 0.0
                m.geom_pos[gid_p] = [0.0, 0.0, -10.0]
                d.geom_xpos[gid_p] = [0.0, 0.0, -10.0]
        if slot < len(self._gids_caminho):
            gid_c = self._gids_caminho[slot]
            if disp["caminho_visivel"]:
                p0 = disp["origem"]
                p1 = disp["pos"]
                delta = p1 - p0
                comp = float(np.linalg.norm(delta))
                if comp > 1e-4:
                    u = delta / comp
                    meio = 0.5 * (p0 + p1)
                else:
                    u = disp["direcao"]
                    comp = 0.02
                    meio = p0 + 0.01 * u
                quat = np.zeros(4)
                mujoco.mju_quatZ2Vec(quat, u)
                tau = disp["tempo_vida_s"]
                alpha = 0.90 if tau <= 0.80 else max(0.10, 0.90 * (1.0 - (tau - 0.80) / 0.20))
                cor = [0.18, 1.0, 0.55, alpha] if disp.get("acertou_bola") else [1.0, 0.72, 0.16, alpha]
                m.geom_pos[gid_c] = meio
                m.geom_quat[gid_c] = quat
                m.geom_size[gid_c] = [0.008, 0.5 * comp, 0.0]
                m.geom_rgba[gid_c] = cor
                d.geom_xpos[gid_c] = meio
                mujoco.mju_quat2Mat(d.geom_xmat[gid_c], quat)
            else:
                m.geom_rgba[gid_c, 3] = 0.0
                m.geom_pos[gid_c] = [0.0, 0.0, -10.0]
                d.geom_xpos[gid_c] = [0.0, 0.0, -10.0]

    def _passo_visuais_tiro(self) -> None:
        """Avança o fogo do cano, o(s) projétil(eis) até ao impacto (bola/chão) ou 50 m e o(s) caminho(s) durante 1,0 s."""
        if not self._disparos_visuais and self._fogo_restante_s <= 0.0 and self._ferrolho_restante_s <= 0.0:
            return
        dt = self.dt
        if self._fogo_restante_s > 0.0:
            self._fogo_restante_s = max(0.0, self._fogo_restante_s - dt)
        if self._ferrolho_restante_s > 0.0:
            self._ferrolho_restante_s = max(0.0, self._ferrolho_restante_s - dt)
        self._aplicar_fogo_e_ferrolho()
        if not self._disparos_visuais:
            return
        grav = self.model.opt.gravity.copy()
        vento = self.model.opt.wind.copy()
        pos_bola = (
            self.data.mocap_pos[self._mocap_bola].copy()
            if self._mocap_bola is not None and self._mocap_bola >= 0
            else None
        )
        r_col_bola = self.raio_bola + 0.0045     # raio da bola (50 mm) + raio do projétil 9 mm (4,5 mm)
        # Coeficiente balístico do projétil .380 ACP (9 mm, 6,156 g, C_d ≈ 0,295): k_ar = ρ·C_d·A/(2·m_p) ≈ 0,0018 m⁻¹
        k_ar = 0.00180
        vivos: list[dict] = []
        for disp in self._disparos_visuais:
            disp["tempo_vida_s"] = round(disp["tempo_vida_s"] + dt, 6)
            tau = disp["tempo_vida_s"]
            if not disp["parou"]:
                p_ant = disp["pos"].copy()
                v_rel = disp["vel"] - vento
                v_norm = float(np.linalg.norm(v_rel))
                acc = grav - k_ar * v_norm * v_rel
                p_novo = p_ant + disp["vel"] * dt + 0.5 * acc * (dt * dt)
                v_novo = disp["vel"] + acc * dt

                # 1. Verifica impacto com a BOLA (`ponto_esfera`) ao longo do segmento [p_ant, p_novo]
                bateu_bola = False
                if pos_bola is not None:
                    seg = p_novo - p_ant
                    seg2 = float(np.dot(seg, seg))
                    s_min = float(np.clip(np.dot(pos_bola - p_ant, seg) / max(seg2, 1e-12), 0.0, 1.0))
                    p_prox = p_ant + s_min * seg
                    d_bola = float(np.linalg.norm(p_prox - pos_bola))
                    if d_bola <= r_col_bola:
                        bateu_bola = True
                        disp["pos"] = p_prox
                        disp["vel"] = v_novo
                        disp["distancia_m"] = min(float(np.linalg.norm(p_prox - disp["origem"])), ALCANCE_PROJETIL_M)
                        disp["acertou_bola"] = True
                        disp["parou"] = True
                        disp["resultado"] = "acertou_bola"
                        disp["projetil_visivel"] = False
                        self.n_acertos_bola += 1
                        if self.ultimo_tiro is not None and self.ultimo_tiro.get("tiros_acumulados") == disp["id"]:
                            self.ultimo_tiro["acertou_bola"] = True
                            self.ultimo_tiro["resultado"] = "acertou_bola"
                            self.ultimo_tiro["acertos_bola"] = self.n_acertos_bola
                            self.ultimo_tiro["erros_bola"] = self.n_erros_bola
                            self.ultimo_tiro["ponto_impacto"] = [round(float(v), 4) for v in p_prox]
                            self.ultimo_tiro["distancia_impacto_m"] = round(disp["distancia_m"], 4)

                # 2. Verifica impacto com o CHÃO (z <= 0,005 m) antes dos 50 m
                if not bateu_bola and p_novo[2] <= 0.005 and p_ant[2] > 0.005:
                    s_chao = float(np.clip((p_ant[2] - 0.005) / max(p_ant[2] - p_novo[2], 1e-9), 0.0, 1.0))
                    p_chao = p_ant + s_chao * (p_novo - p_ant)
                    dist_chao = float(np.linalg.norm(p_chao - disp["origem"]))
                    if dist_chao <= ALCANCE_PROJETIL_M:
                        disp["pos"] = p_chao
                        disp["vel"] = v_novo
                        disp["distancia_m"] = dist_chao
                        disp["bateu_chao"] = True
                        disp["parou"] = True
                        disp["resultado"] = "errou_chao"
                        disp["projetil_visivel"] = False
                        self.n_erros_bola += 1
                        if self.ultimo_tiro is not None and self.ultimo_tiro.get("tiros_acumulados") == disp["id"]:
                            self.ultimo_tiro["acertou_bola"] = False
                            self.ultimo_tiro["resultado"] = "errou_chao"
                            self.ultimo_tiro["acertos_bola"] = self.n_acertos_bola
                            self.ultimo_tiro["erros_bola"] = self.n_erros_bola
                            self.ultimo_tiro["ponto_impacto"] = [round(float(v), 4) for v in p_chao]
                            self.ultimo_tiro["distancia_impacto_m"] = round(dist_chao, 4)

                # 3. Verifica limite de 50 metros de alcance de renderização do projétil
                if not disp["parou"]:
                    delta = p_novo - disp["origem"]
                    dist = float(np.linalg.norm(delta))
                    if dist >= ALCANCE_PROJETIL_M:
                        p_50m = disp["origem"] + (ALCANCE_PROJETIL_M / max(dist, 1e-9)) * delta
                        disp["pos"] = p_50m
                        disp["vel"] = v_novo
                        disp["distancia_m"] = ALCANCE_PROJETIL_M
                        disp["alcancou_50m"] = True
                        disp["parou"] = True
                        disp["resultado"] = "errou_50m"
                        disp["projetil_visivel"] = False
                        self.n_erros_bola += 1
                        if self.ultimo_tiro is not None and self.ultimo_tiro.get("tiros_acumulados") == disp["id"]:
                            self.ultimo_tiro["acertou_bola"] = False
                            self.ultimo_tiro["resultado"] = "errou_50m"
                            self.ultimo_tiro["acertos_bola"] = self.n_acertos_bola
                            self.ultimo_tiro["erros_bola"] = self.n_erros_bola
                            self.ultimo_tiro["ponto_impacto"] = [round(float(v), 4) for v in p_50m]
                            self.ultimo_tiro["distancia_impacto_m"] = ALCANCE_PROJETIL_M
                    else:
                        disp["pos"] = p_novo
                        disp["vel"] = v_novo
                        disp["distancia_m"] = dist
                        disp["projetil_visivel"] = True
            if tau <= DURACAO_CAMINHO_TIRO_S + 1e-9:
                disp["caminho_visivel"] = True
                self._aplicar_geoms_disparo(disp)
                vivos.append(disp)
            else:
                disp["caminho_visivel"] = False
                disp["projetil_visivel"] = False
                self._aplicar_geoms_disparo(disp)
        self._disparos_visuais = vivos

    def prever_tiro_bola(self, pos_bola: np.ndarray | None = None, vel_bola: np.ndarray | None = None) -> dict:
        """Calcula em tempo real ONDE O TIRO VAI PEGAR e se ACERTA A BOLA (considerando o movimento da bola
        até o projétil chegar):

          · Simula o voo balístico do projétil desde `boca_cano` com v₀ = v_boca + 296·x̂_corpo, gravidade e vento;
          · Compara a trajetória do projétil p_proj(τ) com a trajetória futura da bola p_bola(τ) = p_bola(0) + v_bola·τ;
          · Projeta o ponto de impacto na câmara FPV (`ponto_impacto_tan = [tx, ty]`, mesma convenção de `erro_tan`)
            para o visor FPS mostrar exatamente onde o tiro vai pegar e «NO ALVO» vs «FORA DO ALVO».
        """
        arma = self.hw.arma
        v0_boca = arma.velocidade_boca if arma is not None else 296.0
        rmat = self._v_xmat.reshape(3, 3)
        ex = rmat[:, 0]
        com = self._v_xipos
        p_boca = self._v_boca.copy() if self._v_boca is not None else (com + rmat @ np.array([0.0965, 0.0, self.braco_z_arma]))
        w_mundo = rmat @ self.data.qvel[3:6]
        v_boca = self.data.qvel[0:3] + np.cross(w_mundo, p_boca - com)
        v_proj0 = v_boca + v0_boca * ex
        grav = self.model.opt.gravity
        vento = self.model.opt.wind
        k_ar = 0.00180
        r_col = self.raio_bola + 0.0045

        if pos_bola is None and self._mocap_bola is not None and self._mocap_bola >= 0:
            pos_bola = self.data.mocap_pos[self._mocap_bola].copy()
        v_b = np.zeros(3) if vel_bola is None else np.asarray(vel_bola, dtype=float)

        if pos_bola is not None:
            pos_b0 = np.asarray(pos_bola, dtype=float)
            dist_b0 = float(np.linalg.norm(pos_b0 - p_boca))
            # Tempo de voo estimado até o plano da bola: τ_voo ≈ D / v₀ (≈ 5–15 ms a 1,5–4 m)
            v_rel0 = v_proj0 - vento
            a_proj0 = grav - k_ar * float(np.linalg.norm(v_rel0)) * v_rel0
            # Posição relativa inicial r₀ = p_boca − p_bola(0) e velocidade relativa u_rel = v_proj0 − v_bola
            r0 = p_boca - pos_b0
            u_rel = v_proj0 - v_b
            u2 = float(np.dot(u_rel, u_rel))
            tau_min = float(np.clip(-np.dot(r0, u_rel) / max(u2, 1e-6), 0.0, ALCANCE_PROJETIL_M / max(v0_boca, 1.0)))
            # Refina com a aceleração gravitacional/arrasto em τ_min
            p_proj_t = p_boca + v_proj0 * tau_min + 0.5 * a_proj0 * (tau_min * tau_min)
            p_bola_t = pos_b0 + v_b * tau_min
            erro_m = float(np.linalg.norm(p_proj_t - p_bola_t))
            p_imp = p_proj_t
            no_alvo = bool(erro_m <= r_col and tau_min > 0.0)
            # Para o AUTO SHOOT: exige margem estrita (≤ 76 % do raio de colisão) considerando o deslocamento da bola até τ_min
            vai_acertar = bool(erro_m <= 0.76 * r_col and tau_min > 0.0 and dist_b0 <= ALCANCE_PROJETIL_M)
        else:
            dist_b0 = 2.0
            tau_min = dist_b0 / max(v0_boca, 1.0)
            v_rel0 = v_proj0 - vento
            a_proj0 = grav - k_ar * float(np.linalg.norm(v_rel0)) * v_rel0
            p_imp = p_boca + v_proj0 * tau_min + 0.5 * a_proj0 * (tau_min * tau_min)
            erro_m = None
            no_alvo = False
            vai_acertar = False

        # Projeção de `p_imp` na câmara FPV (`ponto_impacto_tan = [tx, ty]`, x direita, y baixo)
        imp_tan = None
        if self._cid_fpv is not None:
            cam_pos = self.data.cam_xpos[self._cid_fpv]
            cam_mat = self.data.cam_xmat[self._cid_fpv].reshape(3, 3)
            dc = cam_mat.T @ (p_imp - cam_pos)
            xc, yc, zc = float(dc[0]), float(dc[1]), -float(dc[2])
            if zc > 0.05:
                imp_tan = [round(xc / zc, 5), round(-yc / zc, 5)]

        return {
            "no_alvo": no_alvo,
            "vai_acertar_certeza": vai_acertar,
            "mensagem": "NO ALVO" if no_alvo else "FORA DO ALVO",
            "erro_bola_m": None if erro_m is None else round(erro_m, 4),
            "raio_colisao_m": round(r_col, 4),
            "tempo_voo_ms": round(tau_min * 1000.0, 2),
            "distancia_bola_m": round(dist_b0, 3),
            "ponto_impacto_mundo": [round(float(v), 4) for v in p_imp],
            "ponto_impacto_tan": imp_tan,
        }

    def definir_carga_extra(self, carga_kg: float) -> dict:
        """Define uma carga útil extra `carga_kg` (≥ 0 kg) acoplada ao drone, atualizando a massa/inércia
        no MuJoCo (`mj_setConst` preservando o estado dinâmico atual) e recalibrando a aerodinâmica."""
        carga = max(0.0, float(carga_kg))
        self.carga_extra_kg = carga
        c = self.corpo
        m_nova = self._massa_corpo_base + carga
        fator_m = m_nova / max(self._massa_corpo_base, 1e-6)
        qpos_atual = self.data.qpos.copy()
        qvel_atual = self.data.qvel.copy()
        ctrl_atual = self.data.ctrl.copy()
        t_atual = float(self.data.time)
        self.model.body_mass[c] = m_nova
        self.model.body_inertia[c] = self._inercia_corpo_base * fator_m
        mujoco.mj_setConst(self.model, self.data)
        self.data.qpos[:] = qpos_atual
        self.data.qvel[:] = qvel_atual
        self.data.ctrl[:] = ctrl_atual
        self.data.time = t_atual
        mujoco.mj_forward(self.model, self.data)
        ph = self.hw.ponto_pairagem(self.hw.bateria.v_nominal, massa=m_nova)
        self.aero.omega_h = ph["omega"]
        self.omega_h = ph["omega"]
        self.aero.definir_arrasto(*self.aero.d_xy, massa=m_nova)
        return self.hw.limites_carga(massa_total=m_nova, soc=self.bat.soc)

    def _forca_tiro_passo(self) -> float:
        """Força escalar de recuo (N) a aplicar NESTE passo de física (avança os contadores ativos)."""
        if not self._tiros_ativos:
            self.forca_tiro_atual = 0.0
            return 0.0
        f_tot = 0.0
        restantes: list[list[float]] = []
        for item in self._tiros_ativos:
            f_tot += item[0]
            item[1] -= 1
            if item[1] > 0:
                restantes.append(item)
        self._tiros_ativos = restantes
        self.forca_tiro_atual = f_tot
        return f_tot

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
        if self._tiros_ativos:
            f_tiro = self._forca_tiro_passo()
            frx, fry, frz = -f_tiro * r00, -f_tiro * r10, -f_tiro * r20
            if self._v_boca is not None:
                px_b, py_b, pz_b = self._v_boca.tolist()
                bx_a, by_a, bz_a = px_b - cx, py_b - cy, pz_b - cz
            else:
                bx_a = 0.0965 * r00 + self.braco_z_arma * r02
                by_a = 0.0965 * r10 + self.braco_z_arma * r12
                bz_a = 0.0965 * r20 + self.braco_z_arma * r22
            xfrc[0] += frx
            xfrc[1] += fry
            xfrc[2] += frz
            xfrc[3] += by_a * frz - bz_a * fry
            xfrc[4] += bz_a * frx - bx_a * frz
            xfrc[5] += bx_a * fry - by_a * frx
        else:
            self.forca_tiro_atual = 0.0

        _mj_step2(m, d)
        self._passo_visuais_tiro()

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
        if self._tiros_ativos:
            f_tiro = self._forca_tiro_passo()
            f_recuo = -f_tiro * ex
            if self._v_boca is not None:
                braco_arma = self._v_boca - com
            else:
                braco_arma = 0.0965 * ex + self.braco_z_arma * ez
            tau_recuo = np.cross(braco_arma, f_recuo)
            d.xfrc_applied[self.corpo, :3] += f_recuo
            d.xfrc_applied[self.corpo, 3:] += tau_recuo
        else:
            self.forca_tiro_atual = 0.0

        mujoco.mj_step2(m, d)
        self._passo_visuais_tiro()

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

    def telemetria_arma(self, pos_bola: np.ndarray | None = None, vel_bola: np.ndarray | None = None) -> dict | None:
        """Estado e balística da arma montada no topo do drone (`None` sem arma no build)."""
        arma = self.hw.arma
        if arma is None:
            return None
        rmat = self._v_xmat.reshape(3, 3)
        ex = rmat[:, 0]
        soco = -ex
        azim_soco = float(math.degrees(math.atan2(soco[1], soco[0])) % 360.0)
        massa_atual = float(self.model.body_mass.sum())
        j_tiro = arma.impulso_tiro
        iyy = max(float(self.inercia_corpo[1]), 1e-6)
        cap = max(arma.capacidade, 1)
        municao = cap if self.n_tiros == 0 else (cap - (self.n_tiros % cap))
        ultimo_vis = self._disparos_visuais[-1] if self._disparos_visuais else None
        mira = self.prever_tiro_bola(pos_bola=pos_bola, vel_bola=vel_bola)
        return {
            "id": arma.id,
            "modelo": f"{arma.fabricante} {arma.modelo}".strip(),
            "calibre": arma.calibre,
            "massa_g": round(arma.massa * 1000.0, 1),
            "capacidade": cap,
            "municao": int(municao),
            "tiros": int(self.n_tiros),
            "acertos_bola": int(self.n_acertos_bola),
            "erros_bola": int(self.n_erros_bola),
            "gatilho": bool(self.gatilho_tiro),
            "em_recuo": bool(self._tiros_ativos),
            "fogo_cano_ativo": bool(self._fogo_restante_s > 0.0),
            "fogo_restante_ms": round(self._fogo_restante_s * 1000.0, 1),
            "projetil_visivel": any(d["projetil_visivel"] for d in self._disparos_visuais),
            "caminho_visivel": any(d["caminho_visivel"] for d in self._disparos_visuais),
            "distancia_projetil_m": round(float(ultimo_vis["distancia_m"]), 3) if ultimo_vis else 0.0,
            "tempo_caminho_s": round(float(ultimo_vis["tempo_vida_s"]), 4) if ultimo_vis else 0.0,
            "alcance_render_m": ALCANCE_PROJETIL_M,
            "duracao_caminho_s": DURACAO_CAMINHO_TIRO_S,
            "mira": mira,
            "disparos_visuais": [
                {
                    "id": d["id"],
                    "distancia_m": round(float(d["distancia_m"]), 3),
                    "tempo_vida_s": round(float(d["tempo_vida_s"]), 4),
                    "projetil_visivel": bool(d["projetil_visivel"]),
                    "caminho_visivel": bool(d["caminho_visivel"]),
                    "alcancou_50m": bool(d["alcancou_50m"]),
                    "acertou_bola": bool(d.get("acertou_bola", False)),
                    "bateu_chao": bool(d.get("bateu_chao", False)),
                    "resultado": str(d.get("resultado", "em_voo")),
                    "origem": [round(float(v), 3) for v in d["origem"]],
                    "pos": [round(float(v), 3) for v in d["pos"]],
                }
                for d in self._disparos_visuais
            ],
            "impulso_ns": round(j_tiro, 5),
            "forca_pico_n": round(arma.forca_media_tiro, 2),
            "forca_atual_n": round(float(self.forca_tiro_atual), 2),
            "duracao_ms": round(arma.duracao_impulso * 1000.0, 1),
            "energia_boca_j": round(arma.energia_boca_j, 2),
            "velocidade_boca_m_s": round(arma.velocidade_boca, 1),
            "delta_v_teorico_m_s": round(j_tiro / max(massa_atual, 1e-6), 5),
            "braco_z_m": round(self.braco_z_arma, 5),
            "impulso_angular_nms": round(self.braco_z_arma * j_tiro, 5),
            "delta_omega_pitch_rad_s": round(-self.braco_z_arma * j_tiro / iyy, 5),
            "direcao_tiro": [round(float(v), 5) for v in ex],
            "direcao_soco": [round(float(v), 5) for v in soco],
            "azimute_soco_graus": round(azim_soco, 2),
            "ultimo_tiro": self.ultimo_tiro,
        }

    def telemetria(self) -> dict:
        b = self.bat.telemetria()
        pw = self.potencias()
        return {"bateria": b, "potencia": pw, "motores": self.prop.telemetria(),
                "v_bus": self.v_bus, "i_total": self.i_total, "brownout": self.brownout,
                "omega_max": self.omega_max_atual(), "t_max_rotor": self.hw.kf * self.omega_max_atual() ** 2,
                "kappa_t": self.kappa_t.copy(), "altura_rotores": self.altura_rotores.copy(),
                "arma": self.telemetria_arma()}


def potencia_pairagem_bancada(hw: Hardware, v_bus: float) -> float:
    """Potência elétrica TOTAL em pairagem pelo regime estacionário (W) — o mesmo que `ponto_pairagem`."""
    return hw.ponto_pairagem(v_bus)["p_total"]


def ligar_rng(planta: Planta, rng: np.random.Generator) -> None:
    """Troca o gerador aleatório da planta (o ambiente usa o `np_random` do Gymnasium)."""
    planta.rng = rng


__all__ = ["Planta", "ligar_rng", "potencia_pairagem_bancada"]
