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

from .. import camera_rpi as cam_rpi
from .componentes import Hardware

TIMESTEP = 0.002
ROTORES = ("rotor1", "rotor2", "rotor3", "rotor4")
REACOES = ("reacao1", "reacao2", "reacao3", "reacao4")
SITES_ROTOR = ("r1", "r2", "r3", "r4")
SITE_BOCA_CANO = "boca_cano"
N_SLOTS_TIRO = 8
ALCANCE_PROJETIL_M = 50.0
DURACAO_CAMINHO_TIRO_S = 1.0
DURACAO_FOGO_CANO_S = 0.060

_COR = {"frame": [0.13, 0.13, 0.15, 1], "motor": [0.72, 0.72, 0.76, 1], "esc": [0.18, 0.22, 0.55, 1],
        "bateria": [0.50, 0.12, 0.10, 1], "rpi": [0.06, 0.45, 0.22, 1], "fc": [0.10, 0.10, 0.10, 1],
        "sensor": [0.85, 0.65, 0.10, 1], "perna": [0.25, 0.25, 0.28, 1],
        "helice_cw": [0.10, 0.55, 0.85, 0.22], "helice_ccw": [0.90, 0.40, 0.10, 0.22],
        "helice_cf": [0.11, 0.12, 0.14, 0.96],
        "helice_ponta_cw": [0.15, 0.72, 0.98, 1.0],
        "helice_ponta_ccw": [0.98, 0.52, 0.12, 1.0],
        "motor_sino": [0.12, 0.13, 0.15, 1.0],
        "cobre_bobina": [0.85, 0.52, 0.18, 1.0],
        "aco_inox": [0.78, 0.80, 0.83, 1.0],
        "aluminio_vermelho": [0.78, 0.14, 0.16, 1.0],
        "aluminio_anodizado": [0.58, 0.60, 0.64, 1.0],
        "fio_vermelho": [0.86, 0.15, 0.15, 1.0],
        "fio_preto": [0.10, 0.10, 0.12, 1.0],
        "fio_azul": [0.14, 0.42, 0.88, 1.0],
        "conector_xt90": [0.95, 0.72, 0.08, 1.0],
        "usb_azul": [0.10, 0.48, 0.92, 1.0],
        "cabo_csi": [0.92, 0.86, 0.72, 1.0]}
_COR_ARMA = {
    "glock_od": [0.44, 0.41, 0.30, 1.0],
    "glock_aco": [0.18, 0.19, 0.21, 1.0],
    "glock_cano_aco": [0.30, 0.31, 0.34, 1.0],
    "glock_preto": [0.08, 0.08, 0.09, 1.0],
    "glock_mira": [0.95, 0.96, 0.98, 1.0],
}
_COR_EFEITOS_ARMA = {
    "fogo_nucleo": ([1.0, 0.97, 0.70, 1.0], 1.0),
    "fogo_labareda": ([1.0, 0.48, 0.08, 1.0], 0.95),
    "projetil_cobre": ([1.0, 0.82, 0.25, 1.0], 0.90),
    "rastro_tiro": ([1.0, 0.72, 0.16, 1.0], 0.85),
}


def _caixa_pack(hw: Hardware) -> tuple[float, float, float]:
    from .bateria import _dims_pack
    dims = [float(x) / 1000.0 for x in hw.bateria.dados.get("dims_mm", ())] or _dims_pack(hw)
    return tuple(sorted(dims, reverse=True))      # (comprido, largo, alto) — deitado ao longo de x


def _quat_pa(psi_rad: float, pitch_rad: float) -> list[float]:
    """Quaternião [w, x, y, z] de uma pá no azimute `psi_rad` (em torno de z) inclinada de `pitch_rad` (em torno do raio x)."""
    cz, sz = math.cos(0.5 * psi_rad), math.sin(0.5 * psi_rad)
    cx, sx = math.cos(0.5 * pitch_rad), math.sin(0.5 * pitch_rad)
    # Rz(psi) * Rx(pitch)
    return [cz * cx, cz * sx, sz * sx, sz * cx]


def _montar(hw: Hardware, deslocamento: np.ndarray | None = None, z0: float = 0.3,
             com_alvo: bool = False) -> mujoco.MjSpec:
    """Constrói o spec; `deslocamento` é subtraído a todas as posições do corpo (põe a origem no CM)."""
    spec = mujoco.MjSpec()
    spec.modelname = f"drone_rpi_{hw.nome}"
    spec.compiler.degree = False
    spec.option.timestep = TIMESTEP
    spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    spec.option.density = 1.225
    spec.option.viscosity = 1.8e-5
    # framebuffer offscreen: comporta o MODO maior do módulo de câmara (4608×2592 = 11,9 MP) —
    # o MuJoCo nunca renderiza acima de `<visual><global offwidth/offheight>` (regra do lab)
    spec.visual.global_.offwidth = 4608
    spec.visual.global_.offheight = 2592
    spec.visual.map.zfar = 80.0
    spec.stat.extent = max(1.0, 2.0 * hw.frame.wheelbase)

    tex = spec.add_texture(name="chao", type=mujoco.mjtTexture.mjTEXTURE_2D,
                           builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER, rgb1=[0.25, 0.25, 0.25],
                           rgb2=[0.33, 0.33, 0.33], width=256, height=256)
    mat = spec.add_material(name="chao", texrepeat=[10, 10], reflectance=0.1)
    mat.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = tex.name
    for nome, rgba in _COR.items():
        spec.add_material(name=nome, rgba=rgba)
    if hw.arma is not None:
        for nome, rgba in _COR_ARMA.items():
            spec.add_material(name=nome, rgba=rgba)
        for nome, (rgba, emissao) in _COR_EFEITOS_ARMA.items():
            m_ef = spec.add_material(name=nome, rgba=rgba, emission=emissao, specular=0.0, shininess=0.0)
            _ = m_ef

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

    # ---- frame de alta estabilidade: dupla placa em sanduíche + 4 braços + treliças anti-torção
    # PLACA CENTRAL: `placa_mm` do catálogo quando existe (é o caso do frame 1950: a placa NÃO cresce
    # com o wheelbase — são os braços que esticam, e o orçamento de massa do catálogo trata as placas
    # como constantes); sem o campo, a fórmula histórica 0,16·wheelbase (os frames antigos, para os quais
    # ela foi calibrada).
    lado = (0.5 * float(hw.frame.dados["placa_mm"]) / 1000.0 if hw.frame.dados.get("placa_mm")
            else max(0.045, 0.16 * hw.frame.wheelbase))
    esp = 0.0015
    corpo.add_geom(name="placa", type=mujoco.mjtGeom.mjGEOM_BOX, size=[lado, lado, esp], pos=p(0, 0, 0),
                   mass=0.4 * massas["frame"] + massas["extra"], material="frame")
    # Placa superior do sanduíche estrutural + 4 espaçadores CNC vermelhos nos cantos (group=3, mass=0)
    z_deck_sup = esp + 0.014
    corpo.add_geom(name="placa_superior", type=mujoco.mjtGeom.mjGEOM_BOX,
                   size=[0.88 * lado, 0.88 * lado, 0.0012], pos=p(0, 0, z_deck_sup),
                   group=3, mass=0.0, material="frame", **sem_contacto)
    for idx_sp, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1)), start=1):
        corpo.add_geom(name=f"espacador_placa_{idx_sp}", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.003, 0.5 * z_deck_sup, 0],
                       pos=p(0.78 * sx * lado, 0.78 * sy * lado, 0.5 * z_deck_sup),
                       group=3, mass=0.0, material="aluminio_vermelho", **sem_contacto)

    for i, (x, y) in enumerate(rot):
        ang = math.atan2(y, x)
        corpo.add_geom(name=f"braco{i + 1}", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.5 * braco, 0.012, 0.005], pos=p(0.5 * x, 0.5 * y, 0.0),
                       quat=[math.cos(ang / 2), 0, 0, math.sin(ang / 2)], mass=0.15 * massas["frame"],
                       material="frame", **sem_contacto)
        # Suporte CNC do motor na ponta do braço + abraçadeiras estruturais
        corpo.add_geom(name=f"suporte_motor_{i + 1}", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.024, 0.0025, 0], pos=p(x, y, 0.0035),
                       group=3, mass=0.0, material="aluminio_vermelho", **sem_contacto)
        # Fios trifásicos de silicone (fases A/B/C: vermelho, preto, azul) do ESC central até ao motor
        ux, uy = math.cos(ang), math.sin(ang)
        nx, ny = -uy, ux
        r_ini = min(0.85 * lado, 0.22 * braco)
        r_fim = max(braco - 0.020, r_ini + 0.02)
        for offset_lat, cor_fio, sufixo in ((-0.0045, "fio_vermelho", "a"),
                                            (0.0, "fio_preto", "b"),
                                            (0.0045, "fio_azul", "c")):
            p_ini = p(r_ini * ux + offset_lat * nx, r_ini * uy + offset_lat * ny, 0.0062)
            p_fim = p(r_fim * ux + offset_lat * nx, r_fim * uy + offset_lat * ny, 0.0062)
            corpo.add_geom(name=f"fio_motor{i + 1}_{sufixo}", type=mujoco.mjtGeom.mjGEOM_CAPSULE,
                           size=[0.0016, 0, 0], fromto=p_ini + p_fim,
                           group=3, mass=0.0, material=cor_fio, **sem_contacto)
        # Abraçadeiras (zip-ties) que prendem os 3 fios ao tubo de carbono do braço
        for k_ab, frac_ab in enumerate((0.35, 0.68), start=1):
            corpo.add_geom(name=f"abracadeira_braco{i + 1}_{k_ab}", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.003, 0.0135, 0.0062],
                           pos=p(frac_ab * x, frac_ab * y, 0.001),
                           quat=[math.cos(ang / 2), 0, 0, math.sin(ang / 2)],
                           group=3, mass=0.0, material="fio_preto", **sem_contacto)

    # Treliças diagonais anti-torção em fibra de carbono entre braços adjacentes (aumentam a rigidez modal)
    pares_trelica = ((0, 2), (2, 1), (1, 3), (3, 0))
    for idx_t, (ia, ib) in enumerate(pares_trelica, start=1):
        xa, ya = 0.34 * rot[ia][0], 0.34 * rot[ia][1]
        xb, yb = 0.34 * rot[ib][0], 0.34 * rot[ib][1]
        corpo.add_geom(name=f"trelica_estab_{idx_t}", type=mujoco.mjtGeom.mjGEOM_CAPSULE,
                       size=[0.0035, 0, 0], fromto=p(xa, ya, 0.0) + p(xb, yb, 0.0),
                       group=3, mass=0.0, material="frame", **sem_contacto)

    # ---- motores (baseados no T-Motor Antigravity MN4004 KV300 real) e hélices 3D rotativas
    d_mot = float(hw.motor.dados.get("diametro_mm", 28.0)) / 1000.0
    h_mot = float(hw.motor.dados.get("altura_mm", 0.6 * d_mot * 1000.0)) / 1000.0
    z_mot = 0.005 + 0.5 * h_mot
    z_rotor = 0.005 + h_mot + 0.008
    m_rotor = hw.motor.massa + hw.helice.massa
    r_hel = hw.helice.raio
    c_med = hw.helice.corda_media
    taper = hw.helice.afunilamento
    theta_pa = hw.helice.angulo_passo_75_rad
    n_pas = max(int(hw.helice.pas), 2)
    q_nao_id = [math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5)]
    for i, (x, y) in enumerate(rot):
        # Cilindro de massa/colisão exata do motor+hélice (preserva a inércia bit a bit)
        corpo.add_geom(name=f"motor{i + 1}", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.5 * d_mot, 0.5 * h_mot, 0], pos=p(x, y, z_mot), mass=m_rotor, material="motor")
        # Anatomia real do T-Motor Antigravity MN4004: bobinas de cobre do estator + sino anodizado preto + raios ventilados + eixo
        corpo.add_geom(name=f"motor{i + 1}_estator_cobre", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.44 * d_mot, 0.36 * h_mot, 0], pos=p(x, y, z_mot + 0.001),
                       group=3, mass=0.0, material="cobre_bobina", **sem_contacto)
        corpo.add_geom(name=f"motor{i + 1}_sino_anel", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.51 * d_mot, 0.22 * h_mot, 0], pos=p(x, y, z_mot + 0.22 * h_mot),
                       group=3, mass=0.0, material="motor_sino", **sem_contacto)
        corpo.add_geom(name=f"motor{i + 1}_base_cnc", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.48 * d_mot, 0.14 * h_mot, 0], pos=p(x, y, z_mot - 0.38 * h_mot),
                       group=3, mass=0.0, material="motor_sino", **sem_contacto)
        for k_r in range(3):
            ang_r = k_r * math.pi / 3.0
            corpo.add_geom(name=f"motor{i + 1}_raio_{k_r + 1}", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.49 * d_mot, 0.065 * d_mot, 0.0012],
                           pos=p(x, y, z_mot + 0.48 * h_mot),
                           quat=[math.cos(0.5 * ang_r), 0.0, 0.0, math.sin(0.5 * ang_r)],
                           group=3, mass=0.0, material="motor_sino", **sem_contacto)
        corpo.add_geom(name=f"motor{i + 1}_eixo", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.11 * d_mot, 0.0055, 0], pos=p(x, y, z_mot + 0.5 * h_mot + 0.004),
                       group=3, mass=0.0, material="aco_inox", **sem_contacto)

        # Disco translúcido de motion-blur (group=2) + Hélice 3D com cubo e pás perfiladas rotativas (group=1)
        cor = "helice_cw" if hw.GIRO[i] < 0 else "helice_ccw"
        cor_ponta = "helice_ponta_cw" if hw.GIRO[i] < 0 else "helice_ponta_ccw"
        corpo.add_geom(name=f"helice{i + 1}", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[r_hel, 0.0012, 0], pos=p(x, y, z_rotor), mass=0.0, material=cor,
                       group=2, **sem_contacto)
        corpo.add_geom(name=f"helice{i + 1}_cubo", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[max(0.013, 0.075 * r_hel), 0.0038, 0], pos=p(x, y, z_rotor),
                       quat=q_nao_id, group=1, mass=0.0, material="motor_sino", **sem_contacto)
        s_giro = float(hw.GIRO[i])                 # rotores 1,2 giram CW (-1); rotores 3,4 giram CCW (+1)
        for b_idx in range(n_pas):
            psi_b = 2.0 * math.pi * b_idx / n_pas
            cb, sb = math.cos(psi_b), math.sin(psi_b)
            # Secção interior (raiz → meio da pá)
            r_in = 0.29 * r_hel
            corpo.add_geom(name=f"helice{i + 1}_pa{b_idx + 1}_raiz", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.23 * r_hel, 0.58 * c_med, 0.0016],
                           pos=p(x + r_in * cb, y + r_in * sb, z_rotor + 0.0005),
                           quat=_quat_pa(psi_b, s_giro * theta_pa),
                           group=1, mass=0.0, material="helice_cf", **sem_contacto)
            # Secção exterior afunilada (scimitar meio → ponta da pá)
            r_out = 0.73 * r_hel
            corpo.add_geom(name=f"helice{i + 1}_pa{b_idx + 1}_ponta", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.23 * r_hel, max(0.004, 0.58 * c_med * taper), 0.0011],
                           pos=p(x + r_out * cb, y + r_out * sb, z_rotor + 0.0005),
                           quat=_quat_pa(psi_b, 0.75 * s_giro * theta_pa),
                           group=1, mass=0.0, material="helice_cf", **sem_contacto)
            # Faixa colorida de ponta da pá (identifica sentido CW/CCW e torna a rotação nítida)
            r_tip = 0.93 * r_hel
            corpo.add_geom(name=f"helice{i + 1}_pa{b_idx + 1}_faixa", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.045 * r_hel, max(0.0038, 0.52 * c_med * taper), 0.0013],
                           pos=p(x + r_tip * cb, y + r_tip * sb, z_rotor + 0.0006),
                           quat=_quat_pa(psi_b, 0.65 * s_giro * theta_pa),
                           group=1, mass=0.0, material=cor_ponta, **sem_contacto)
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

    # ---- pilha de eletrónica: FC (se houver), RPi 5 fiel (PCB, SoC BCM2712, Active Cooler, portas USB/RJ45/GPIO/HDMI) e restantes
    z = z_pilha + 0.006
    for c in hw.consumidores:
        dims = [float(v) / 2000.0 for v in c.dados.get("dims_mm", (40, 40, 10))]
        cor = "rpi" if "rpi" in c.id else ("fc" if "fc" in c.id else "sensor")
        z_centro_c = z + dims[2]
        corpo.add_geom(name=f"el_{c.id}", type=mujoco.mjtGeom.mjGEOM_BOX, size=dims,
                       pos=p(0, 0, z_centro_c), mass=c.massa, material=cor, **sem_contacto)
        if "rpi" in c.id:
            # Representação anatómica fiel da Raspberry Pi 5 (85×56 mm):
            #   · PCB verde fina + 4 pilares de latão;
            #   · SoC Broadcom BCM2712 + Active Cooler (dissipador de alumínio aletado + ventoinha radial);
            #   · Southbridge RP1 + PMIC Dialog DA9091;
            #   · Borda frontal/direita (+x): 2× torres USB 3.0 (interior azul) + USB 2.0 + Gigabit Ethernet RJ45;
            #   · Borda lateral (-y): USB-C de alimentação + 2× micro-HDMI;
            #   · Borda lateral (+y): barramento GPIO de 40 pinos;
            #   · Conectores MIPI CSI/DSI + cabo flat CSI até à câmara frontal.
            sx_r, sy_r, sz_r = dims[0], dims[1], dims[2]
            z_pcb = z + 0.0012
            corpo.add_geom(name="rpi5_soc_bcm2712", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.0085, 0.0085, 0.0012], pos=p(-0.008, 0.002, z_pcb + 0.0022),
                           group=3, mass=0.0, material="aco_inox", **sem_contacto)
            corpo.add_geom(name="rpi5_dissipador", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.018, 0.018, 0.0035], pos=p(-0.005, 0.002, z_pcb + 0.0055),
                           group=3, mass=0.0, material="aluminio_anodizado", **sem_contacto)
            corpo.add_geom(name="rpi5_ventoinha", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                           size=[0.012, 0.0022, 0], pos=p(-0.002, 0.002, z_pcb + 0.0082),
                           group=3, mass=0.0, material="fio_preto", **sem_contacto)
            corpo.add_geom(name="rpi5_rp1", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.006, 0.006, 0.001], pos=p(0.012, -0.006, z_pcb + 0.002),
                           group=3, mass=0.0, material="fc", **sem_contacto)
            # Torres USB 3.0 (com interior azul), USB 2.0 e porta Gigabit Ethernet RJ45 na borda +x
            x_porta = sx_r - 0.006
            corpo.add_geom(name="rpi5_rj45", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.008, 0.0075, 0.0065], pos=p(x_porta, -0.017, z_pcb + 0.007),
                           group=3, mass=0.0, material="aco_inox", **sem_contacto)
            corpo.add_geom(name="rpi5_usb3_torre", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.0075, 0.0065, 0.0075], pos=p(x_porta, 0.001, z_pcb + 0.008),
                           group=3, mass=0.0, material="aco_inox", **sem_contacto)
            corpo.add_geom(name="rpi5_usb3_azul", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.0078, 0.0050, 0.0020], pos=p(x_porta + 0.0005, 0.001, z_pcb + 0.009),
                           group=3, mass=0.0, material="usb_azul", **sem_contacto)
            corpo.add_geom(name="rpi5_usb2_torre", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.0075, 0.0065, 0.0075], pos=p(x_porta, 0.018, z_pcb + 0.008),
                           group=3, mass=0.0, material="aco_inox", **sem_contacto)
            # Borda +y: barramento GPIO de 40 pinos
            corpo.add_geom(name="rpi5_gpio_40p", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.0255, 0.0025, 0.0042], pos=p(-0.006, sy_r - 0.0035, z_pcb + 0.005),
                           group=3, mass=0.0, material="fio_preto", **sem_contacto)
            # Borda -y: USB-C de energia + 2× micro-HDMI
            corpo.add_geom(name="rpi5_usbc", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.0045, 0.0038, 0.0018], pos=p(-0.028, -sy_r + 0.003, z_pcb + 0.0025),
                           group=3, mass=0.0, material="aco_inox", **sem_contacto)
            for idx_h, x_h in enumerate((-0.014, -0.001), start=1):
                corpo.add_geom(name=f"rpi5_micro_hdmi_{idx_h}", type=mujoco.mjtGeom.mjGEOM_BOX,
                               size=[0.0035, 0.0038, 0.0016], pos=p(x_h, -sy_r + 0.003, z_pcb + 0.0025),
                               group=3, mass=0.0, material="aco_inox", **sem_contacto)
            _ = sz_r
        z += 2 * dims[2] + 0.004
    corpo.add_site(name="imu", pos=p(0, 0, z_pilha + 0.012), size=[0.006, 0, 0])

    # ---- pack de bateria por baixo da placa (berço de baixo CG + cintas de velcro + cabos XT90)
    c_b, l_b, a_b = _caixa_pack(hw)
    z_bat = -esp - 0.004 - 0.5 * a_b
    corpo.add_geom(name="bateria", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.5 * c_b, 0.5 * l_b, 0.5 * a_b],
                   pos=p(0, 0, z_bat), mass=massas["bateria"], material="bateria")
    for idx_cb, x_cb in enumerate((-0.28 * c_b, 0.28 * c_b), start=1):
        corpo.add_geom(name=f"cinta_bateria_{idx_cb}", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.008, 0.5 * l_b + 0.002, 0.5 * a_b + 0.002],
                       pos=p(x_cb, 0, z_bat), group=3, mass=0.0, material="fio_preto", **sem_contacto)
    corpo.add_geom(name="conector_xt90", type=mujoco.mjtGeom.mjGEOM_BOX,
                   size=[0.011, 0.008, 0.005], pos=p(-0.5 * c_b - 0.010, 0.0, z_bat + 0.25 * a_b),
                   group=3, mass=0.0, material="conector_xt90", **sem_contacto)
    for s_cabo, cor_cabo, sufixo in ((0.004, "fio_vermelho", "pos"), (-0.004, "fio_preto", "neg")):
        corpo.add_geom(name=f"cabo_bateria_{sufixo}", type=mujoco.mjtGeom.mjGEOM_CAPSULE,
                       size=[0.0025, 0, 0],
                       fromto=p(-0.5 * c_b - 0.010, s_cabo, z_bat + 0.25 * a_b) + p(-0.020, s_cabo, esp + 0.004),
                       group=3, mass=0.0, material=cor_cabo, **sem_contacto)

    # ---- sensores de baixo (ToF + fluxo) por baixo do pack, a olhar para o chão
    z_baixo = z_bat - 0.5 * a_b - 0.004
    m_sens = sum(v for k, v in massas.items() if k.startswith("sensor_"))
    corpo.add_geom(name="sensores_baixo", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.012, 0.012, 0.002],
                   pos=p(0, 0, z_baixo + 0.002), mass=max(m_sens, 1e-4), material="sensor", **sem_contacto)
    corpo.add_site(name="baixo", pos=p(0, 0, z_baixo), quat=[0, 1, 0, 0], size=[0.004, 0, 0])

    # ---- módulo de câmara À FRENTE do drone (CSI na Pi Camera, DVP na Vision Shield do Arduino; peça REAL do
    # catálogo: massa, dimensões e FoV)
    # Placa na vertical no nariz (+x): a LENTE aponta para a frente, por isso a espessura no eixo ótico é a
    # ALTURA COM LENTE (dims[2] = 11,5/12,4 mm) e as outras duas dimensões ficam em y (largura) e z
    # (profundidade da placa, de pé). A `<camera fpv>` fica 1 mm à frente da face da lente (para o próprio
    # módulo não entrar na imagem) e olha para +x (ver `camera_rpi.add_camera_fpv`). A massa entra no
    # orçamento (`massas["camera"]`), como em qualquer peça real; sem contacto (o payload não colide, tal
    # como o ESC/pilha).
    if hw.camera is not None:
        d_largura, d_profundidade, d_altura = hw.camera.dims   # (placa y, placa z, espessura+lente em x)
        d_x, d_y, d_z = d_altura, d_largura, d_profundidade
        x_cam = lado + 0.5 * d_x - 0.002    # encostada à frente da placa central, lente para +x
        z_cam = esp + 0.5 * d_z + 0.001     # sobre a placa
        corpo.add_geom(name="camera", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.5 * d_x, 0.5 * d_y, 0.5 * d_z], pos=p(x_cam, 0, z_cam),
                       mass=hw.camera.massa, material="sensor", **sem_contacto)
        # FoV de arranque = o do modo POR OMISSÃO do módulo (1080p50 na Pi Camera; QVGA a 30 fps na Vision Shield
        # do Arduino) — o `ModuloCamera` reescreve-o a cada captura com o do modo em vigor
        modulo_cam = cam_rpi.modulo_da_peca(hw.camera.id)
        cam_rpi.add_camera_fpv(corpo, p(x_cam + 0.5 * d_x + 0.001, 0, z_cam),
                               cam_rpi.fovy_graus(modulo_cam, cam_rpi.modo_omissao(modulo_cam)), nome="fpv")

    # ---- ARMA FIXA NO TOPO DO DRONE (ex.: Glock 25 .380 Auto, peça REAL do catálogo `armas`)
    # Modelagem anatómica fiel à Glock 25 OD Green (.380 Auto, 187×32×128 mm, cano 102 mm, ferrolho 25,5 mm,
    # miras 153 mm, gatilho Safe Action® 28 N a 71,2 mm, punho inclinado a 22° com ranhuras Gen3 e base preta
    # do carregador, janela de ejeção prateada, serrilhas traseiras do ferrolho e berço rígido no topo).
    # A massa exata `hw.arma.massa` (785 g com 15 tiros) é distribuída entre `arma_quadro` (45 %) e
    # `arma_ferrolho` (55 %), ambos centrados em (x=0, y=0) para manter o CM horizontal sobre o centro dos
    # rotores e o tensor de inércia fiel; as restantes peças anatómicas e os geoms de fogo do cano têm mass=0.
    if hw.arma is not None:
        c_a, l_a, a_a = hw.arma.dims                # (187, 32, 128) mm em m
        l_fer = hw.arma.largura_ferrolho            # 25,5 mm em m
        c_cano = hw.arma.comprimento_cano           # 102 mm em m
        z_base_arma = z + 0.002                     # topo da pilha de eletrónica
        m_quadro = 0.45 * hw.arma.massa             # quadro de polímero + carregador cheio (45 % da massa)
        m_ferrolho = hw.arma.massa - m_quadro       # ferrolho + cano de aço no topo (55 %; soma exata = hw.arma.massa)
        z_quadro = z_base_arma + 0.68 * a_a         # trilho horizontal do quadro (dust cover / frame rail)
        z_cano = z_base_arma + 0.875 * a_a          # eixo do cano / ferrolho (no topo da pistola)

        # 1. Berço rígido de montagem no topo do drone + solenoide de acionamento do gatilho (28 N)
        corpo.add_geom(name="arma_suporte_base", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.055, 0.022, 0.003], pos=p(0.0, 0.0, z_base_arma + 0.001),
                       mass=0.0, material="glock_preto", **sem_contacto)
        corpo.add_geom(name="arma_suporte_frente", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.006, 0.018, 0.32 * a_a], pos=p(0.042, 0.0, z_base_arma + 0.33 * a_a),
                       mass=0.0, material="glock_preto", **sem_contacto)

        # 2. Quadro horizontal de polímero OD Green (com a massa do quadro+carregador centrada em x=0, y=0)
        corpo.add_geom(name="arma_quadro", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.5 * c_a, 0.5 * l_a, 0.009], pos=p(0.0, 0.0, z_quadro),
                       mass=m_quadro, material="glock_od", **sem_contacto)
        # Ranhuras do trilho de acessórios Glock na ponta dianteira do quadro
        for s_y, sufixo in ((1.0, "esq"), (-1.0, "dir")):
            corpo.add_geom(name=f"arma_trilho_{sufixo}", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.026, 0.0012, 0.0018],
                           pos=p(0.5 * c_a - 0.030, s_y * (0.5 * l_a + 0.0005), z_quadro + 0.002),
                           mass=0.0, material="glock_preto", **sem_contacto)

        # 3. Punho inclinado a 22° (ângulo clássico Glock) + ranhuras dos dedos + base preta do carregador
        ang_punho = math.radians(22.0)
        q_punho = [math.cos(0.5 * ang_punho), 0.0, math.sin(0.5 * ang_punho), 0.0]
        x_punho = -0.052
        z_punho = z_base_arma + 0.34 * a_a
        corpo.add_geom(name="arma_punho", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.024, 0.5 * l_a, 0.33 * a_a], pos=p(x_punho, 0.0, z_punho),
                       quat=q_punho, mass=0.0, material="glock_od", **sem_contacto)
        corpo.add_geom(name="arma_base_carregador", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.026, 0.5 * l_a + 0.001, 0.005],
                       pos=p(x_punho - 0.015, 0.0, z_base_arma + 0.005),
                       quat=q_punho, mass=0.0, material="glock_preto", **sem_contacto)
        for idx_d, frac_z in enumerate((0.20, 0.34, 0.48), start=1):
            corpo.add_geom(name=f"arma_dedo_{idx_d}", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                           size=[0.004, 0.5 * l_a - 0.001, 0.0],
                           pos=p(x_punho + 0.025 - (0.34 - frac_z) * 0.04, 0.0, z_base_arma + frac_z * a_a),
                           quat=[math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0],
                           mass=0.0, material="glock_od", **sem_contacto)
        corpo.add_geom(name="arma_retentor_carregador", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.005, 0.5 * l_a + 0.0015, 0.008],
                       pos=p(-0.028, 0.0, z_base_arma + 0.52 * a_a),
                       mass=0.0, material="glock_preto", **sem_contacto)

        # 4. Guarda-mato + gatilho Safe Action® (28 N, a 71,2 mm) + atuador solenoide de disparo
        corpo.add_geom(name="arma_guarda_mato_baixo", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.022, 0.007, 0.003], pos=p(0.002, 0.0, z_base_arma + 0.44 * a_a),
                       mass=0.0, material="glock_od", **sem_contacto)
        corpo.add_geom(name="arma_guarda_mato_frente", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.0035, 0.007, 0.11 * a_a], pos=p(0.022, 0.0, z_base_arma + 0.55 * a_a),
                       mass=0.0, material="glock_od", **sem_contacto)
        ang_gat = math.radians(-18.0)
        corpo.add_geom(name="arma_gatilho", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.003, 0.0035, 0.011], pos=p(0.002, 0.0, z_base_arma + 0.56 * a_a),
                       quat=[math.cos(0.5 * ang_gat), 0.0, math.sin(0.5 * ang_gat), 0.0],
                       mass=0.0, material="glock_preto", **sem_contacto)
        corpo.add_geom(name="arma_solenoide_gatilho", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.005, 0.012, 0.0], pos=p(-0.008, 0.0, z_base_arma + 0.56 * a_a),
                       quat=[math.sqrt(0.5), 0.0, math.sqrt(0.5), 0.0],
                       mass=0.0, material="glock_aco", **sem_contacto)

        # 5. Ferrolho de aço Tenifer/NDLC (55 % da massa) + janela de ejeção + serrilhas traseiras
        corpo.add_geom(name="arma_ferrolho", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.5 * c_a, 0.5 * l_fer, 0.125 * a_a], pos=p(0.0, 0.0, z_cano),
                       mass=m_ferrolho, material="glock_aco", **sem_contacto)
        corpo.add_geom(name="arma_janela_ejecao", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.014, 0.5 * l_fer + 0.0006, 0.007],
                       pos=p(0.006, -0.001, z_cano + 0.005),
                       mass=0.0, material="glock_cano_aco", **sem_contacto)
        for idx_s in range(6):
            x_s = -0.5 * c_a + 0.014 + idx_s * 0.0045
            corpo.add_geom(name=f"arma_serrilha_{idx_s + 1}", type=mujoco.mjtGeom.mjGEOM_BOX,
                           size=[0.001, 0.5 * l_fer + 0.0007, 0.011],
                           pos=p(x_s, 0.0, z_cano - 0.001),
                           mass=0.0, material="glock_preto", **sem_contacto)

        # 6. Cano de aço (102 mm), furo de 9 mm (.380 Auto) e miras (153 mm entre miras, com pontos brancos)
        q_eixo_x = [math.sqrt(0.5), 0.0, math.sqrt(0.5), 0.0]
        x_boca = 0.5 * c_a + 0.003
        corpo.add_geom(name="arma_cano", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.0068, 0.5 * c_cano, 0], pos=p(x_boca - 0.5 * c_cano, 0, z_cano),
                       quat=q_eixo_x, mass=0.0, material="glock_cano_aco", **sem_contacto)
        corpo.add_geom(name="arma_boca_furo", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                       size=[0.0045, 0.0015, 0], pos=p(x_boca + 0.0005, 0, z_cano),
                       quat=q_eixo_x, mass=0.0, material="glock_preto", **sem_contacto)
        z_mira = z_base_arma + a_a + 0.0025
        corpo.add_geom(name="arma_mira_frente", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.0035, 0.002, 0.0028], pos=p(0.5 * 0.153, 0, z_mira),
                       mass=0.0, material="glock_preto", **sem_contacto)
        corpo.add_geom(name="arma_ponto_mira_frente", type=mujoco.mjtGeom.mjGEOM_SPHERE,
                       size=[0.0013, 0, 0], pos=p(0.5 * 0.153 - 0.003, 0, z_mira + 0.0005),
                       mass=0.0, material="glock_mira", **sem_contacto)
        corpo.add_geom(name="arma_mira_tras", type=mujoco.mjtGeom.mjGEOM_BOX,
                       size=[0.0045, 0.0065, 0.0028], pos=p(-0.5 * 0.153, 0, z_mira),
                       mass=0.0, material="glock_preto", **sem_contacto)
        for s_y, sufixo in ((1.0, "esq"), (-1.0, "dir")):
            corpo.add_geom(name=f"arma_ponto_mira_tras_{sufixo}", type=mujoco.mjtGeom.mjGEOM_SPHERE,
                           size=[0.0011, 0, 0], pos=p(-0.5 * 0.153 - 0.004, s_y * 0.0028, z_mira + 0.0005),
                           mass=0.0, material="glock_mira", **sem_contacto)
        corpo.add_site(name=SITE_BOCA_CANO, pos=p(x_boca, 0, z_cano), quat=q_eixo_x, size=[0.005, 0, 0])

        # 7. EFEITO DE FOGO DO CANO (muzzle flash emissivo na boca do cano; alpha=0 em repouso, acende no disparo)
        corpo.add_geom(name="arma_fogo_nucleo", type=mujoco.mjtGeom.mjGEOM_ELLIPSOID,
                       size=[0.022, 0.012, 0.012], pos=p(x_boca + 0.020, 0, z_cano),
                       rgba=[1.0, 0.97, 0.70, 0.0], group=2, mass=0.0, material="fogo_nucleo", **sem_contacto)
        corpo.add_geom(name="arma_fogo_cone", type=mujoco.mjtGeom.mjGEOM_ELLIPSOID,
                       size=[0.065, 0.022, 0.022], pos=p(x_boca + 0.062, 0, z_cano),
                       rgba=[1.0, 0.48, 0.08, 0.0], group=2, mass=0.0, material="fogo_labareda", **sem_contacto)
        corpo.add_geom(name="arma_fogo_cruz_h", type=mujoco.mjtGeom.mjGEOM_ELLIPSOID,
                       size=[0.018, 0.048, 0.008], pos=p(x_boca + 0.028, 0, z_cano),
                       rgba=[1.0, 0.55, 0.12, 0.0], group=2, mass=0.0, material="fogo_labareda", **sem_contacto)
        corpo.add_geom(name="arma_fogo_cruz_v", type=mujoco.mjtGeom.mjGEOM_ELLIPSOID,
                       size=[0.018, 0.008, 0.048], pos=p(x_boca + 0.028, 0, z_cano),
                       rgba=[1.0, 0.55, 0.12, 0.0], group=2, mass=0.0, material="fogo_labareda", **sem_contacto)

        # 8. PROJÉTEIS (.380 ACP, visíveis até 50 m) e CAMINHOS/RASTROS (visíveis por 1,0 s) no mundo
        # ATENÇÃO: `quat=q_eixo_x` não-identidade obriga o compilador do MuJoCo a pôr `geom_sameframe=0`
        # (com a identidade punha `geom_sameframe=3` e ignorava `geom_quat`, desenhando uma linha vertical!).
        for k in range(N_SLOTS_TIRO):
            wb.add_geom(name=f"projetil_tiro_{k}", type=mujoco.mjtGeom.mjGEOM_SPHERE,
                        size=[0.018, 0, 0], pos=[0.0, 0.0, -10.0], quat=q_eixo_x,
                        rgba=[1.0, 0.82, 0.25, 0.0], group=2, mass=0.0, material="projetil_cobre", **sem_contacto)
            wb.add_geom(name=f"caminho_tiro_{k}", type=mujoco.mjtGeom.mjGEOM_CAPSULE,
                        size=[0.008, 0.01, 0], pos=[0.0, 0.0, -10.0], quat=q_eixo_x,
                        rgba=[1.0, 0.72, 0.16, 0.0], group=2, mass=0.0, material="rastro_tiro", **sem_contacto)

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

    # ---- PONTO-ALVO VISUAL opcional (IA de seguimento visual: «ver o ponto e seguir») — esfera brilhante no
    # mundo, SEM massa e SEM colisão: o que a câmara vê, nunca a física (regra do simulador físico)
    if com_alvo:
        cam_rpi.adicionar_ponto(spec)

    spec.add_key(name="pousado", qpos=[0, 0, z0, 1, 0, 0, 0])
    return spec


def construir_spec(hw: Hardware, com_alvo: bool = False) -> mujoco.MjSpec:
    """Spec final com a origem do corpo no CM (duas passagens)."""
    m1 = _montar(hw, com_alvo=com_alvo).compile()
    cm = np.array(m1.body_ipos[m1.body("drone").id])
    spec = _montar(hw, deslocamento=cm, com_alvo=com_alvo)
    return spec


def carregar(hw: Hardware, com_alvo: bool = False) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """(model, data) do build, com o drone no ar a 0,3 m (o `reset` do ambiente pousa-o pela física).

    `com_alvo=True` acrescenta o corpo mocap `ponto` (esfera brilhante emissiva) da IA de seguimento: sem massa, sem colisão,
    só para a câmara ver — a física do modelo não muda um átomo.
    """
    model = construir_spec(hw, com_alvo=com_alvo).compile()
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
