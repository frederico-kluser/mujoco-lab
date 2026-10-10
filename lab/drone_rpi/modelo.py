"""lab.drone_rpi.modelo — gera o MJCF do drone a partir do build (MjSpec), com as massas REAIS das peças.

Nada é desenhado à mão: a geometria vem do frame (wheelbase), as dimensões do motor/pack/RPi do catálogo e
as massas do orçamento (`Hardware.massas`). A inércia é a que o MuJoCo calcula dos geoms com essas massas
(caixas/cilindros nos sítios certos). A origem do corpo `drone` é posta EXATAMENTE no centro de massa
(1.ª compilação mede o CM; a 2.ª desloca tudo), por isso `qpos[:3]` = posição do CM.

Corpo `drone` (junta livre `livre`):
  · placa central + 4 braços (frame), 4 motores (cilindros, com a massa da hélice), 4 discos de hélice
    VISUAIS (sem massa nem contacto), ESC, pack de bateria por baixo da placa, pilha RPi 5 (+ FC), sensores
    de baixo (ToF + fluxo) por baixo do pack, 4 pernas de trem de pouso (colisão);
  · sites: `r1..r4` (cubos dos rotores, no plano da hélice), `imu` (centro da pilha), `baixo` (sensor de
    baixo, eixo z a apontar para o CHÃO), `cm` (centro de massa);
  · atuadores (8, todos `motor` sem limites — a camada `Planta` escreve valores FÍSICOS):
    `rotor1..4` (força ao longo de z do site, N) e `reacao1..4` (binário em z do site, N·m);
  · sensores: `giro`/`acc` (IMU), `tof` (rangefinder ao chão), `vel_baixo` (velocimeter do sensor de
    baixo), `pos`/`quat`/`vel` (telemetria/recompensa — informação privilegiada, nunca na observação).
Física: 500 Hz (`timestep` 0,002), `implicitfast`, ar (ρ = 1,225, μ = 1,8e-5) para o vento e o arrasto
do corpo.
"""
from __future__ import annotations

import math
import pathlib

import mujoco
import numpy as np

from .componentes import Hardware

TIMESTEP = 0.002
ROTORES = ("rotor1", "rotor2", "rotor3", "rotor4")
REACOES = ("reacao1", "reacao2", "reacao3", "reacao4")
SITES_ROTOR = ("r1", "r2", "r3", "r4")

_COR = {"frame": [0.13, 0.13, 0.15, 1], "motor": [0.72, 0.72, 0.76, 1], "esc": [0.18, 0.22, 0.55, 1],
        "bateria": [0.50, 0.12, 0.10, 1], "rpi": [0.06, 0.45, 0.22, 1], "fc": [0.10, 0.10, 0.10, 1],
        "sensor": [0.85, 0.65, 0.10, 1], "perna": [0.25, 0.25, 0.28, 1],
        "helice_cw": [0.10, 0.55, 0.85, 0.35], "helice_ccw": [0.90, 0.40, 0.10, 0.35]}


def _caixa_pack(hw: Hardware) -> tuple[float, float, float]:
    from .bateria import _dims_pack
    dims = [float(x) / 1000.0 for x in hw.bateria.dados.get("dims_mm", ())] or _dims_pack(hw)
    return tuple(sorted(dims, reverse=True))      # (comprido, largo, alto) — deitado ao longo de x


def _montar(hw: Hardware, deslocamento: np.ndarray | None = None, z0: float = 0.3) -> mujoco.MjSpec:
    """Constrói o spec; `deslocamento` é subtraído a todas as posições do corpo (põe a origem no CM)."""
    spec = mujoco.MjSpec()
    spec.modelname = f"drone_rpi_{hw.nome}"
    spec.compiler.degree = False
    spec.option.timestep = TIMESTEP
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    spec.option.density = 1.225
    spec.option.viscosity = 1.8e-5
    spec.visual.global_.offwidth = 1280
    spec.visual.global_.offheight = 720
    spec.stat.extent = max(1.0, 2.0 * hw.frame.wheelbase)

    tex = spec.add_texture(name="chao", type=mujoco.mjtTexture.mjTEXTURE_2D,
                           builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER, rgb1=[0.25, 0.25, 0.25],
                           rgb2=[0.33, 0.33, 0.33], width=256, height=256)
    mat = spec.add_material(name="chao", texrepeat=[10, 10], reflectance=0.1)
    mat.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = tex.name
    for nome, rgba in _COR.items():
        spec.add_material(name=nome, rgba=rgba)

    wb = spec.worldbody
    wb.add_geom(name="chao", type=mujoco.mjtGeom.mjGEOM_PLANE, size=[50, 50, 0.1], material="chao",
                friction=[0.9, 0.005, 0.0001])
    wb.add_light(name="sol", pos=[0, 0, 6], dir=[0, 0, -1], type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
                 diffuse=[0.7, 0.7, 0.7])

    corpo = wb.add_body(name="drone", pos=[0, 0, z0])
    corpo.add_freejoint(name="livre")
    off = np.zeros(3) if deslocamento is None else np.asarray(deslocamento, dtype=float)

    def p(x, y, z):
        return list(np.array([x, y, z], dtype=float) - off)

    sem_contacto = {"contype": 0, "conaffinity": 0}
    massas = hw.massas
    braco = hw.braco
    rot = hw.pos_rotores

    # ---- frame: placa central + 4 braços
    lado = max(0.045, 0.16 * hw.frame.wheelbase)
    esp = 0.0015
    corpo.add_geom(name="placa", type=mujoco.mjtGeom.mjGEOM_BOX, size=[lado, lado, esp], pos=p(0, 0, 0),
                   mass=0.4 * massas["frame"] + massas["extra"], material="frame")
    for i, (x, y) in enumerate(rot):
        ang = math.atan2(y, x)
        corpo.add_geom(name=f"braco{i + 1}", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.5 * braco, 0.012, 0.005], pos=p(0.5 * x, 0.5 * y, 0.0),
                       quat=[math.cos(ang / 2), 0, 0, math.sin(ang / 2)], mass=0.15 * massas["frame"],
                       material="frame", **sem_contacto)

    # ---- motores (+ massa das hélices) e discos de hélice visuais
    d_mot = float(hw.motor.dados.get("diametro_mm", 28.0)) / 1000.0
    h_mot = float(hw.motor.dados.get("altura_mm", 0.6 * d_mot * 1000.0)) / 1000.0
    z_mot = 0.005 + 0.5 * h_mot
    z_rotor = 0.005 + h_mot + 0.008
    m_rotor = hw.motor.massa + hw.helice.massa
    for i, (x, y) in enumerate(rot):
        corpo.add_geom(name=f"motor{i + 1}", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.5 * d_mot, 0.5 * h_mot, 0], pos=p(x, y, z_mot), mass=m_rotor, material="motor")
        cor = "helice_cw" if hw.GIRO[i] < 0 else "helice_ccw"
        corpo.add_geom(name=f"helice{i + 1}", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[hw.helice.raio, 0.0015, 0], pos=p(x, y, z_rotor), mass=0.0, material=cor,
                       group=2, **sem_contacto)
        corpo.add_site(name=SITES_ROTOR[i], pos=p(x, y, z_rotor), size=[0.01, 0, 0])

    # ---- ESC (4-em-1 no centro, ou 1 por braço)
    if hw.esc.dados.get("formato", "4em1") == "4em1":
        corpo.add_geom(name="esc", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.021, 0.021, 0.004],
                       pos=p(0, 0, esp + 0.004), mass=massas["esc"], material="esc", **sem_contacto)
        z_pilha = esp + 0.008
    else:
        for i, (x, y) in enumerate(rot):
            corpo.add_geom(name=f"esc{i + 1}", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.016, 0.011, 0.003],
                           pos=p(0.45 * x, 0.45 * y, esp + 0.004), mass=0.25 * massas["esc"],
                           material="esc", **sem_contacto)
        z_pilha = esp

    # ---- pilha de eletrónica: FC (se houver), RPi 5 e restantes consumidores
    z = z_pilha + 0.006
    for c in hw.consumidores:
        dims = [float(v) / 2000.0 for v in c.dados.get("dims_mm", (40, 40, 10))]
        cor = "rpi" if "rpi" in c.id else ("fc" if "fc" in c.id else "sensor")
        corpo.add_geom(name=f"el_{c.id}", type=mujoco.mjtGeom.mjGEOM_BOX, size=dims,
                       pos=p(0, 0, z + dims[2]), mass=c.massa, material=cor, **sem_contacto)
        z += 2 * dims[2] + 0.004
    corpo.add_site(name="imu", pos=p(0, 0, z_pilha + 0.012), size=[0.006, 0, 0])

    # ---- pack de bateria por baixo da placa (correia), ao longo de x
    c_b, l_b, a_b = _caixa_pack(hw)
    z_bat = -esp - 0.004 - 0.5 * a_b
    corpo.add_geom(name="bateria", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.5 * c_b, 0.5 * l_b, 0.5 * a_b],
                   pos=p(0, 0, z_bat), mass=massas["bateria"], material="bateria")

    # ---- sensores de baixo (ToF + fluxo) por baixo do pack, a olhar para o chão
    z_baixo = z_bat - 0.5 * a_b - 0.004
    m_sens = sum(v for k, v in massas.items() if k.startswith("sensor_"))
    corpo.add_geom(name="sensores_baixo", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.012, 0.012, 0.002],
                   pos=p(0, 0, z_baixo + 0.002), mass=max(m_sens, 1e-4), material="sensor", **sem_contacto)
    corpo.add_site(name="baixo", pos=p(0, 0, z_baixo), quat=[0, 1, 0, 0], size=[0.004, 0, 0])

    # ---- trem de pouso (colisão): 4 pernas sob os braços, mais baixas do que o pack
    h_pernas = max(hw.frame.altura_pernas, -z_baixo + 0.03)
    for i, (x, y) in enumerate(rot):
        xp, yp = 0.55 * x, 0.55 * y
        corpo.add_geom(name=f"perna{i + 1}", type=mujoco.mjtGeom.mjGEOM_CAPSULE, size=[0.006, 0, 0],
                       fromto=p(xp, yp, -0.004) + p(xp, yp, -h_pernas), mass=0.25 * massas["pernas"],
                       material="perna", friction=[0.9, 0.005, 0.0001])
    corpo.add_site(name="cm", pos=[0, 0, 0], size=[0.004, 0, 0])

    # ---- atuadores: empuxo e reação por rotor (valores físicos escritos pela Planta)
    for i in range(4):
        a = spec.add_actuator(name=ROTORES[i], trntype=mujoco.mjtTrn.mjTRN_SITE, target=SITES_ROTOR[i],
                              gear=[0, 0, 1, 0, 0, 0],
                              ctrllimited=mujoco.mjtLimited.mjLIMITED_FALSE)
        a.set_to_motor()
        a.gear = [0, 0, 1, 0, 0, 0]
    for i in range(4):
        a = spec.add_actuator(name=REACOES[i], trntype=mujoco.mjtTrn.mjTRN_SITE, target=SITES_ROTOR[i],
                              gear=[0, 0, 0, 0, 0, 1],
                              ctrllimited=mujoco.mjtLimited.mjLIMITED_FALSE)
        a.set_to_motor()
        a.gear = [0, 0, 0, 0, 0, 1]

    # ---- sensores
    S, O = mujoco.mjtSensor, mujoco.mjtObj
    spec.add_sensor(name="giro", type=S.mjSENS_GYRO, objtype=O.mjOBJ_SITE, objname="imu")
    spec.add_sensor(name="acc", type=S.mjSENS_ACCELEROMETER, objtype=O.mjOBJ_SITE, objname="imu")
    tof = spec.add_sensor(name="tof", type=S.mjSENS_RANGEFINDER, objtype=O.mjOBJ_SITE, objname="baixo")
    tof.intprm[0] = 1 << int(mujoco.mjtRayDataField.mjRAYDATA_DIST)   # data="dist" (obrigatório no 3.15)
    spec.add_sensor(name="vel_baixo", type=S.mjSENS_VELOCIMETER, objtype=O.mjOBJ_SITE, objname="baixo")
    spec.add_sensor(name="pos", type=S.mjSENS_FRAMEPOS, objtype=O.mjOBJ_SITE, objname="cm")
    spec.add_sensor(name="quat", type=S.mjSENS_FRAMEQUAT, objtype=O.mjOBJ_BODY, objname="drone")
    spec.add_sensor(name="vel", type=S.mjSENS_FRAMELINVEL, objtype=O.mjOBJ_SITE, objname="cm")

    spec.add_key(name="pousado", qpos=[0, 0, z0, 1, 0, 0, 0])
    return spec


def construir_spec(hw: Hardware) -> mujoco.MjSpec:
    """Spec final com a origem do corpo no CM (duas passagens)."""
    m1 = _montar(hw).compile()
    cm = np.array(m1.body_ipos[m1.body("drone").id])
    spec = _montar(hw, deslocamento=cm)
    return spec


def carregar(hw: Hardware) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """(model, data) do build, com o drone no ar a 0,3 m (o `reset` do ambiente pousa-o pela física)."""
    model = construir_spec(hw).compile()
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


def exportar_xml(hw: Hardware, caminho: pathlib.Path | str) -> str:
    """Escreve o MJCF gerado (para inspecionar com `inspect_model.py`/viewer) e devolve o texto."""
    xml = construir_spec(hw).to_xml()
    cabeca = (f"<!-- GERADO por lab/drone_rpi/modelo.py a partir do build '{hw.nome}' "
              f"(models/drone_rpi/builds.json) — NÃO editar à mão: troque peças no catálogo e regenere com "
              f"`experiments/09_drone_hover_rl/hardware.py xml`. -->\n")
    pathlib.Path(caminho).write_text(cabeca + xml, encoding="utf-8")
    return xml
