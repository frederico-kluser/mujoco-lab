"""lab.spot — MODOS, CONTROLES e LEITURAS do Spot (Boston Dynamics) para você criar algoritmos.

Modelo base: `models/boston_dynamics_spot/` (mujoco_menagerie, BSD-3) — INTACTO. Esta camada:

  1. acrescenta SENSORES via MjSpec (sem editar os XMLs upstream);
  2. expõe CONTROLES como funções (alvos dos 12 servos de posição);
  3. expõe MODOS como funções (posturas e varredura de motores, sem realimentação);
  4. expõe LEITURAS dos sensores como funções.

NÃO há marcha, equilíbrio, IK, PD cascata nem código do Spot SDK/BD — os algoritmos são seus.

    from lab import spot
    modelo, data = spot.carregar()
    spot.postura(modelo, data, "agachar")
    spot.definir_alvo(modelo, data, "fl_hy", 1.2)
    imu = spot.ler_imu(modelo, data)        # {'giro', 'acc', 'quat', 'vel'}
    pes = spot.ler_pes(modelo, data)        # {'FL': 12.3, ...} N de contato de cada pé
    enc = spot.ler_juntas(modelo, data)     # {'pos': {...}, 'vel': {...}}

Sensores IMPORTANTES num quadrúpede (os escolhidos e porquê):
  · IMU do tronco (`imu_gyro`, `imu_acc`, `imu_quat`, `imu_vel`) — atitude, taxa e aceleração própria;
    sem isto não há estabilização nem odometria.
  · Encoders das juntas (`junta_pos_*`, `junta_vel_*`) — retroação de cada motor (aqui: servo de posição).
  · Força de contacto dos 4 pés (`pe_*`, touch) — deteção de fase de apoio, impacto e carga;
    é o sensor que separa um quadrúpede de um braço.
  (Torque dos atuadores: `ler_torques` lê `qfrc_actuator` — não precisa de sensor dedicado.)
"""
from __future__ import annotations

from pathlib import Path

import mujoco
import numpy as np

from lab import mjkit  # noqa: F401  (garante MUJOCO_GL antes de import mujoco em quem consome o módulo)

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "models" / "boston_dynamics_spot" / "spot.xml"
CENA = RAIZ / "models" / "boston_dynamics_spot" / "scene.xml"

JUNTAS = ["fl_hx", "fl_hy", "fl_kn", "fr_hx", "fr_hy", "fr_kn",
          "hl_hx", "hl_hy", "hl_kn", "hr_hx", "hr_hy", "hr_kn"]
PES = {"FL": "fl_lleg", "FR": "fr_lleg", "HL": "hl_lleg", "HR": "hr_lleg"}
SENSORES_IMU = ("imu_gyro", "imu_acc", "imu_quat", "imu_vel")

GRAVIDADE = 9.81

# posturas absolutas por sufixo de junta (hx, hy, kn); "sentar" diferencia frente/costas
POSTURAS = {
    "agachar": {"tudo": {"hx": 0.0, "hy": 1.55, "kn": -2.30}},
    "sentar": {"frente": {"hx": 0.0, "hy": 0.65, "kn": -1.05}, "costas": {"hx": 0.0, "hy": 2.00, "kn": -2.50}},
    "esticar": {"tudo": {"hx": 0.0, "hy": 0.50, "kn": -0.85}},
}


# ----------------------------------------------------------------------------------------------- carga
def carregar(cena: bool = True, sensores: bool = True, keyframe: str = "home",
             energia: bool = True) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """Carrega o modelo (intocado) e, com `sensores=True`, acrescenta IMU/encoders/touch via MjSpec.

    Devolve (model, data) já no keyframe `home` (postura nominal de pé).

    `energia=True` (predefinição) liga `mjENBL_ENERGY` para que `data.energy` funcione — os experimentos
    contam com isso. Use `energia=False` para preparar o modelo para o MJX: `mjx.put_model` não implementa
    a flag de energia e falha com `NotImplementedError: mjtEnableBit.mjENBL_ENERGY` (MJX-JAX e MJX-Warp);
    o MuJoCo Warp nativo aceita-a.
    ⚠ Com `energia=False` o `data.energy` fica a ZEROS sem dar erro: `mjkit.record` grava `pe`/`ke` = 0 em
    silêncio — use esta opção só para treino/inferência em MJX, nunca para medir ou validar energia."""
    caminho = CENA if cena else MODELO
    if not sensores:
        model, data = mjkit.load(caminho, energy_flag=energia)
    else:
        spec = mujoco.MjSpec.from_file(str(caminho))
        _adiciona_sensores(spec)
        model = spec.compile()
        if energia:
            model.opt.enableflags |= mujoco.mjtEnableBit.mjENBL_ENERGY
        data = mujoco.MjData(model)
    if keyframe and model.nkey:
        mujoco.mj_resetDataKeyframe(model, data, model.key(keyframe).id)
    mujoco.mj_forward(model, data)
    return model, data


def _adiciona_sensores(spec: mujoco.MjSpec) -> None:
    """IMU no tronco + encoders das 12 juntas + touch nos 4 pés. Só leituras — nada de controlo."""
    spec.body("body").add_site(name="imu", pos=[0.06, 0, 0.05], size=[0.01])
    spec.add_sensor(name="imu_gyro", type=mujoco.mjtSensor.mjSENS_GYRO,
                    objtype=mujoco.mjtObj.mjOBJ_SITE, objname="imu")
    spec.add_sensor(name="imu_acc", type=mujoco.mjtSensor.mjSENS_ACCELEROMETER,
                    objtype=mujoco.mjtObj.mjOBJ_SITE, objname="imu")
    spec.add_sensor(name="imu_quat", type=mujoco.mjtSensor.mjSENS_FRAMEQUAT,
                    objtype=mujoco.mjtObj.mjOBJ_SITE, objname="imu")
    spec.add_sensor(name="imu_vel", type=mujoco.mjtSensor.mjSENS_VELOCIMETER,
                    objtype=mujoco.mjtObj.mjOBJ_SITE, objname="imu")
    for rotulo, corpo in PES.items():
        # site = volume EXATO da esfera do pé (pos/size do geom foot): o ponto de contacto cai sempre
        # dentro do volume do site — semântica do sensor touch (senão só apanha contactos centrados)
        spec.body(corpo).add_site(name=f"pe_{rotulo}", pos=[0, 0, -0.3365], size=[0.036])
        spec.add_sensor(name=f"pe_{rotulo}", type=mujoco.mjtSensor.mjSENS_TOUCH,
                        objtype=mujoco.mjtObj.mjOBJ_SITE, objname=f"pe_{rotulo}")
    for jn in JUNTAS:
        spec.add_sensor(name=f"junta_pos_{jn}", type=mujoco.mjtSensor.mjSENS_JOINTPOS,
                        objtype=mujoco.mjtObj.mjOBJ_JOINT, objname=jn)
        spec.add_sensor(name=f"junta_vel_{jn}", type=mujoco.mjtSensor.mjSENS_JOINTVEL,
                        objtype=mujoco.mjtObj.mjOBJ_JOINT, objname=jn)


def peso(model: mujoco.MjModel) -> float:
    """Peso total do robô (N) = Σ massas × g."""
    return float(model.body_mass.sum() * GRAVIDADE)


# ----------------------------------------------------------------------------------------------- controles
def _slot(model: mujoco.MjModel, junta: str) -> tuple[int, float, float]:
    """(posição em data.ctrl, ctrlrange lo, hi) do servo da junta."""
    aid = model.actuator(junta).id
    adr = int(model.actuator_ctrladr[aid])
    lo, hi = model.actuator_ctrlrange[aid]
    return adr, float(lo), float(hi)


def definir_alvo(model: mujoco.MjModel, data: mujoco.MjData, junta: str, rad: float) -> float:
    """Alvo (rad) do servo de posição da junta; cortado para o ctrlrange (= limites da junta). Devolve o aplicado."""
    adr, lo, hi = _slot(model, junta)
    v = float(np.clip(rad, lo, hi))
    data.ctrl[adr] = v
    return v


def definir_alvos(model: mujoco.MjModel, data: mujoco.MjData, alvos: dict) -> dict:
    """Vários alvos de uma vez: {'fl_hy': 1.2, 'fl_kn': -1.6}. Devolve {junta: aplicado}."""
    return {jn: definir_alvo(model, data, jn, v) for jn, v in alvos.items()}


def postura(model: mujoco.MjModel, data: mujoco.MjData, nome: str) -> dict:
    """Postura nomeada: 'home' (keyframe), 'zero' (0 cortado p/ limites) ou uma de POSTURAS."""
    kid = model.key("home").id
    if nome == "home":
        alvos = {jn: float(model.key_ctrl[kid][i]) for i, jn in enumerate(JUNTAS)}
    elif nome == "zero":
        alvos = {jn: 0.0 for jn in JUNTAS}
    else:
        spec = POSTURAS[nome]
        alvos = {}
        for jn in JUNTAS:
            grupo = "frente" if jn[:2] in ("fl", "fr") else "costas"
            alvos[jn] = spec["tudo"][jn[3:]] if "tudo" in spec else spec[grupo][jn[3:]]
    return definir_alvos(model, data, alvos)


# ----------------------------------------------------------------------------------------------- modos (roteiros abertos)
def modo_postura(nome: str):
    """Devolve uma função modo(model, data, tau) que aplica a postura `nome` (ignora tau)."""

    def f(model, data, tau):
        postura(model, data, nome)
    f.__doc__ = f"postura '{nome}'"
    return f


def modo_varrer(model, data, tau: float, junta: str | None = None, amp: float = 0.2, freq: float = 0.25, base: dict | None = None) -> None:
    """Senoide aberta numa junta (`junta=None` = a `tau` escolhe a junta, uma janela de 1/freq cada).

    `base` = postura sobre a qual varrer (padrão: home)."""
    alvos = dict(base) if base else postura(model, data, "home")
    if junta is None:
        jn = JUNTAS[int(tau * freq) % len(JUNTAS)]
    else:
        jn = junta
    alvos[jn] = alvos[jn] + amp * np.cos(2 * np.pi * freq * tau)
    definir_alvos(model, data, alvos)


MODOS = {"home": modo_postura("home"), "zero": modo_postura("zero"),
         "agachar": modo_postura("agachar"), "sentar": modo_postura("sentar"),
         "esticar": modo_postura("esticar"), "varrer": modo_varrer}


# ----------------------------------------------------------------------------------------------- leituras
def _sens(data: mujoco.MjData, nome: str) -> np.ndarray:
    return data.sensor(nome).data.copy()


def ler_imu(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """IMU do tronco: giro (rad/s, corpo) · acc (m/s², aceleração própria — em repouso lê +g em z) ·
    quat [w x y z] · vel (m/s, corpo)."""
    return {"giro": _sens(data, "imu_gyro"), "acc": _sens(data, "imu_acc"),
            "quat": _sens(data, "imu_quat"), "vel": _sens(data, "imu_vel")}


def ler_juntas(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """Encoders: {'pos': {junta: rad}, 'vel': {junta: rad/s}}."""
    pos, vel = {}, {}
    for jn in JUNTAS:
        pos[jn] = float(_sens(data, f"junta_pos_{jn}")[0])
        vel[jn] = float(_sens(data, f"junta_vel_{jn}")[0])
    return {"pos": pos, "vel": vel}


def ler_pes(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """Força de contato de cada pé (sensor touch, N): {'FL': .., 'FR': .., 'HL': .., 'HR': ..}."""
    return {rot: float(_sens(data, f"pe_{rot}")[0]) for rot in PES}


def ler_torques(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """Torque dos atuadores por junta (N·m), lido de qfrc_actuator (sem sensor dedicado)."""
    out = {}
    for jn in JUNTAS:
        dof = int(model.jnt_dofadr[model.joint(jn).id])
        out[jn] = float(data.qfrc_actuator[dof])
    return out


def ler_tudo(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """Tudo de uma vez: imu · juntas · pés · torques · qpos."""
    d = ler_imu(model, data)
    j = ler_juntas(model, data)
    d["juntas_pos"], d["juntas_vel"] = j["pos"], j["vel"]
    d["pes"] = ler_pes(model, data)
    d["torques"] = ler_torques(model, data)
    d["qpos"] = data.qpos.copy()
    return d
