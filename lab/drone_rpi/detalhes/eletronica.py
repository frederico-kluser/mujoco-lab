"""lab/drone_rpi/detalhes/eletronica.py — a ELETRÓNICA do drone com aspeto de peça REAL (só visual: massa 0, sem
contacto, grupo 3 — regras no `Contexto`; a física fica igual bit a bit, `python -m lab.drone_rpi.detalhes.ver`).

As caixas com massa do `modelo._montar` (`el_rpi5`, `el_fc_h7`, `el_cablagem`, `esc1..4`/`esc`, `bateria`, `camera`,
`sensores_baixo`, `fonte_servos`, `el_arduino_portenta_h7`) continuam lá, com a massa e a inércia de sempre — ficam
INVISÍVEIS (`ctx.esconder`) só quando a peça desenhada aqui as representa por inteiro. Os detalhes antigos `rpi5_*`,
`cinta_bateria_*` e `conector_xt90` são substituídos por peças melhores com o MESMO nome (as que fazem o mesmo papel:
`rpi5_dissipador` é a base do Active Cooler, `cinta_bateria_1` a volta da cinta ao pack, `conector_xt90` a fêmea do
pack…), por isso quem procura esses nomes continua a achá-los. Cada peça adapta-se ao build (`ctx.hw`): o que o build
não tem não se desenha. Sem texturas (o MJCF continua exportável com `to_xml`): só primitivas e materiais simples.

O que se desenha (medidas do fabricante, em mm; «estimado» = sem número oficial, escolhido por coerência):
  · Raspberry Pi 5 — PCB 85×56×1,6, furos Ø2,7 a 3,5 mm das bordas (padrão 58×49, pilares M2,5 de latão), USB-C a
    x = 11,2, micro-HDMI a 25,8 e 39,2, na borda direita USB 2.0 (y = 47, línguas pretas), USB 3.0 (y = 29,1,
    línguas AZUIS, as mais perto da Ethernet) e RJ45 Gigabit (y = 10,2, 13,3 de altura, LEDs verde/âmbar) a sair
    ~3 mm da borda; os 2 conectores MIPI de 22 vias (CAM/DISP 0/1) na borda dos micro-HDMI, até à Ethernet; GPIO 2×20
    (passo 2,54, pinos dourados); FFC PCIe na borda esquerda; botão de energia + LED bicolor na borda junto ao USB-C;
    UART e RTC (JST-SH); BCM2712 (tampa metálica) e RP1 debaixo do dissipador. Orientação = a da caixa `el_rpi5`:
    portas USB/RJ45 para a FRENTE (+x), GPIO à esquerda (+y), USB-C/HDMI/MIPI à direita (−y).
  · Active Cooler oficial — 63,5×42,5×13,7, alumínio anodizado, ventoinha radial de 30 mm, 2 pinos de mola brancos,
    cabo de 4 fios até ao conector FAN (entre o fim do GPIO e as USB 2.0); contorno e aletas estimados (base em L, livre
    dos conectores MIPI e da Ethernet).
  · Ponte de carbono do FC (estimado) — 4 réguas de 1,5 mm nos pilares M2,5 de 16 mm do Pi (o padrão de 30,5 mm do FC
    não cai nos furos do Pi): o FC fica por cima do Active Cooler sem lhe tapar as aletas.
  · FC H7 30×30 — PCB 36×36×1,6 preto, furos 30,5 mm com amortecedores de silicone, STM32H743 (LQFP-100 14×14), IMU
    BMI088 (LGA 3×4,5), barómetro sob espuma, USB-C, microSD por baixo, JST-GH (UART e sensores na borda +y, de
    entrada lateral; GPS/I2C à frente; ESC atrás), LEDs; montado com a frente para +x; pilha M3 de nylon até à placa
    de energia.
  · Placa de energia (`cablagem`: módulo de energia + BEC 5 V/5 A) — PCB 60×40, ilhas estanhadas da bateria (atrás) e
    de cada ESC (no canto do braço respetivo) para os cabos do módulo `fios`, shunt + INA226 (como o PM02D digital),
    BEC síncrono (bobina blindada, CI, 2 condensadores de polímero), JST-GH I2C e saída de 5 V.
  · 4× T-Motor AIR 40A — 55,6×25,2×11,3 mm em termorretrátil preto com rótulo, condensador eletrolítico na entrada,
    saídas de entrada (bateria/sinal) e de fases (motor), deitados AO LONGO do braço, assentes no topo do tubo; nos
    braços articulados vivem no corpo `braco{k}` (sobem/descem com o braço; a massa continua na caixa do corpo `drone`).
  · Camera Module 3 Wide — PCB 25×24 verde, lente de 12,4 mm (bloco do sensor IMX708 + barril + vidro), conector FPC de
    15 vias na borda de baixo, 4 parafusos M2 (furos Ø2,2), suporte em L de PETG com passagem para o FPC. Portenta Vision
    Shield no build Arduino (PCB 66×25,4, HM0360, 2 microfones, conectores HD).
  · Por baixo do pack: PMW3901 (placa 24×24×5, bloco ótico com lente) + VL53L1X (placa Pololu 13×18×2) numa bandeja de
    PETG presa pelas cintas, a olhar para o chão.
  · Pack 6S2P Molicel P50B — 12 células 21700 (Ø21,55 × 70,15 máx.) deitadas em 6×2 com separadores, em termorretrátil
    azul (os topos dobrados por cima do papel de peixe), rótulo, XT90 (fêmea do pack + macho do drone, contactos de
    4,5 mm), tapete anti-derrapante e 2 cintas de 15 mm com fivela que passam pelos rasgos da placa de baixo (±40, ±45
    mm, os do módulo `estrutura`). Packs pouch/LiPo (ou cujas medidas não acomodam as células) → bloco termorretraído
    com rótulo. (O balanceador é do módulo `fios`.)
  · Braços articulados: regulador buck-boost 24 V/5 A dos servos (PCB aberta: toroide de cobre, eletrolíticos,
    dissipador, trimmer multivoltas, bornes de entrada/saída) — estimado (o catálogo só dá «24 V / 5 A, 40 g»).
  · Build Arduino: Portenta H7 (66,04×25,4: STM32H747, SDRAM, Murata 1DX blindado, USB-C, ESLOV, bateria, bordas
    castelladas, conectores HD por baixo) e BMI088 numa placa à parte (o Portenta não tem IMU).

ÂNCORAS para o módulo `fios` (nomes de geoms deste módulo): `rpi5_gpio_40p` + `el_rpi5_gpio_pino01..20`,
`el_rpi5_cam_disp0` (+ `_trava`; o CAM/DISP 1 chama-se `el_rpi5_ffc_disp1` para o FPC ter um só alvo), `rpi5_usbc`,
`el_rpi5_fan_ficha`; `el_fc_con_uart` / `el_fc_con_sensores` (borda +y), `el_fc_con_gps`, `el_fc_con_i2c`,
`el_fc_con_esc`; só a PCB e as ilhas da placa de energia têm «pdb» no nome (`el_pdb_pcb`, `el_pdb_bat_pos/neg`,
`el_pdb_esc{k}_pos/neg`) — o resto é `el_pm_*` (`el_pm_saida_5v` na borda +y); `el_esc{k}_saida_entrada` e
`el_esc{k}_saida_fases`; `el_cam_conector_fpc`; `conector_xt90` (fêmea do pack), `el_xt90_macho` e
`el_xt90_copo_pos/neg` (copos de solda do lado do drone); `el_fluxo_pcb`, `el_tof_pcb`; `el_fonte24_borne_entrada/saida`.

Fontes (web = dado, só citado):
  https://pip.raspberrypi.com/documents/RP-008347-DS-1-raspberry-pi-5-mechanical-drawing.pdf (cotas do Pi 5)
  https://www.raspberrypi.com/news/introducing-raspberry-pi-5 (Ethernet em baixo à direita, PoE)
  https://forums.raspberrypi.com/viewtopic.php?t=365947 (USB 3.0 azuis = as mais perto da Ethernet)
  https://www.raspberrypi.com/documentation/accessories/camera.html (CAM/DISP entre o micro-HDMI e a Ethernet)
  https://forums.raspberrypi.com/viewtopic.php?t=358253 (conector FAN entre o GPIO e as USB 2.0)
  https://blog.dddac.com/raspberry-pi-5-power-over-gpio (LED bicolor ao lado do botão de energia)
  https://pip.raspberrypi.com/documents/RP-008188-DS-active-cooler-product-brief.pdf (63,5×42,5×13,7, ventoinha 30)
  https://www.iswfa.com/drone-propulsion-power/escs/t-motor-air-40a-6s-esc (AIR 40A: 55,6×25,2×11,3 mm, 26 g)
  https://www.corvon.tech/en/products/corvon-h743-flight-controller-30x30-fc-for-drones-with-dual-imu-compass-barometer-stm32h743-7-uart-10-pwm-supports-betaflight-inav-ardupilot-px4-usb-c-blackbox-logging-5v-9v-bec-outputs
    e https://docs.px4.io/main/en/flight_controller/zenfc_h743 (FC H743 36×36, furos 30,5, BMI088)
  https://www.raspberrypi.com/products/camera-module-3 (25×24×11,5 / 12,4 mm Wide, FPC 15×1 mm)
  https://shop.pimoroni.com/products/pmw3901-optical-flow-sensor-breakout (PMW3901: 24×24×5 mm)
  https://www.pololu.com/product/3415 (VL53L1X: 13×18×2 mm)
  https://www.bitcraze.io/products/flow-deck-v2 (PMW3901 + VL53L1x juntos, 21×28×4 mm — referência)
  https://www.18650batterystore.com/products/molicel-21700-p50b-5000mah-50a-battery (P50B: 21,55×70,15 mm máx.)
  https://uavgarage.com/shop/amass-xt90-female-connector-with-housing-1-pcs (XT90: contactos de 4,5 mm; caixa estimada)
"""
from __future__ import annotations

import math
import re
import warnings

import mujoco
import numpy as np

_G = mujoco.mjtGeom
CAIXA, CIL, CAPS = _G.mjGEOM_BOX, _G.mjGEOM_CYLINDER, _G.mjGEOM_CAPSULE
MM = 1e-3

# rotações locais: levam o eixo z de um cilindro para +x / +y
R_EIXO_X = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
R_EIXO_Y = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])

# nome: (rgba, specular, shininess, reflectance, emission) — prefixo `el_` (os materiais são partilhados no spec)
_MATERIAIS = {
    "el_pcb_verde": ((0.05, 0.36, 0.16, 1.0), 0.35, 0.50, 0.0, 0.0),
    "el_pcb_preto": ((0.05, 0.05, 0.06, 1.0), 0.45, 0.55, 0.0, 0.0),
    "el_pcb_vermelho": ((0.36, 0.045, 0.045, 1.0), 0.40, 0.50, 0.0, 0.0),
    "el_pcb_azul": ((0.06, 0.20, 0.55, 1.0), 0.40, 0.50, 0.0, 0.0),
    "el_pcb_roxo": ((0.30, 0.11, 0.42, 1.0), 0.40, 0.50, 0.0, 0.0),
    "el_pcb_pololu": ((0.03, 0.22, 0.58, 1.0), 0.40, 0.50, 0.0, 0.0),
    "el_ouro": ((0.80, 0.62, 0.22, 1.0), 0.85, 0.75, 0.10, 0.0),
    "el_estanho": ((0.64, 0.64, 0.62, 1.0), 0.70, 0.60, 0.05, 0.0),
    "el_cobre": ((0.72, 0.38, 0.17, 1.0), 0.75, 0.60, 0.05, 0.0),
    "el_aco": ((0.56, 0.57, 0.60, 1.0), 0.60, 0.60, 0.08, 0.0),
    "el_aluminio": ((0.55, 0.57, 0.60, 1.0), 0.45, 0.40, 0.03, 0.0),
    "el_latao": ((0.70, 0.56, 0.26, 1.0), 0.75, 0.65, 0.05, 0.0),
    "el_plastico_preto": ((0.06, 0.06, 0.07, 1.0), 0.25, 0.30, 0.0, 0.0),
    "el_plastico_brilho": ((0.03, 0.03, 0.035, 1.0), 0.70, 0.80, 0.03, 0.0),
    "el_cinza_escuro": ((0.20, 0.20, 0.22, 1.0), 0.20, 0.20, 0.0, 0.0),
    "el_abertura": ((0.015, 0.015, 0.018, 1.0), 0.05, 0.05, 0.0, 0.0),
    "el_jst": ((0.84, 0.81, 0.71, 1.0), 0.15, 0.20, 0.0, 0.0),
    "el_nylon": ((0.85, 0.84, 0.79, 1.0), 0.20, 0.25, 0.0, 0.0),
    "el_usb_azul": ((0.08, 0.36, 0.86, 1.0), 0.40, 0.50, 0.0, 0.0),
    "el_chip": ((0.09, 0.09, 0.10, 1.0), 0.30, 0.40, 0.0, 0.0),
    "el_tampa_soc": ((0.62, 0.63, 0.65, 1.0), 0.80, 0.75, 0.10, 0.0),
    "el_trava_fpc": ((0.32, 0.21, 0.12, 1.0), 0.20, 0.25, 0.0, 0.0),
    "el_led_verde": ((0.15, 1.00, 0.25, 1.0), 0.50, 0.50, 0.0, 0.9),
    "el_led_azul": ((0.20, 0.45, 1.00, 1.0), 0.50, 0.50, 0.0, 0.9),
    "el_led_ambar": ((1.00, 0.62, 0.05, 1.0), 0.50, 0.50, 0.0, 0.9),
    "el_silicone": ((0.90, 0.40, 0.10, 1.0), 0.15, 0.20, 0.0, 0.0),
    "el_espuma": ((0.12, 0.12, 0.13, 1.0), 0.02, 0.02, 0.0, 0.0),
    "el_carbono": ((0.09, 0.09, 0.10, 1.0), 0.65, 0.70, 0.03, 0.0),
    "el_termo_preto": ((0.07, 0.07, 0.08, 1.0), 0.55, 0.65, 0.02, 0.0),
    "el_rotulo_esc": ((0.07, 0.17, 0.50, 1.0), 0.35, 0.40, 0.0, 0.0),
    "el_condensador": ((0.08, 0.10, 0.32, 1.0), 0.45, 0.55, 0.0, 0.0),
    "el_cap_polimero": ((0.60, 0.60, 0.62, 1.0), 0.70, 0.60, 0.05, 0.0),
    "el_ferrite": ((0.22, 0.22, 0.24, 1.0), 0.25, 0.30, 0.0, 0.0),
    "el_vidro": ((0.04, 0.05, 0.09, 1.0), 1.00, 1.00, 0.40, 0.0),
    "el_termo_bateria": ((0.08, 0.27, 0.62, 1.0), 0.55, 0.65, 0.03, 0.0),
    "el_termo_pouch": ((0.13, 0.13, 0.15, 1.0), 0.50, 0.60, 0.03, 0.0),
    "el_papel_peixe": ((0.55, 0.11, 0.09, 1.0), 0.15, 0.15, 0.0, 0.0),
    "el_rotulo_branco": ((0.88, 0.88, 0.86, 1.0), 0.25, 0.30, 0.0, 0.0),
    "el_rotulo_cor": ((0.95, 0.70, 0.08, 1.0), 0.25, 0.30, 0.0, 0.0),
    "el_rotulo_texto": ((0.10, 0.10, 0.12, 1.0), 0.10, 0.10, 0.0, 0.0),
    "el_xt90": ((0.93, 0.72, 0.10, 1.0), 0.35, 0.45, 0.0, 0.0),
    "el_cinta": ((0.07, 0.07, 0.075, 1.0), 0.05, 0.05, 0.0, 0.0),
    "el_fivela": ((0.22, 0.22, 0.24, 1.0), 0.60, 0.60, 0.03, 0.0),
    "el_borracha": ((0.10, 0.10, 0.11, 1.0), 0.05, 0.05, 0.0, 0.0),
    "el_petg": ((0.10, 0.10, 0.11, 1.0), 0.30, 0.35, 0.0, 0.0),
    "el_terminal_verde": ((0.10, 0.55, 0.25, 1.0), 0.30, 0.35, 0.0, 0.0),
    "el_trimmer_azul": ((0.15, 0.35, 0.85, 1.0), 0.35, 0.40, 0.0, 0.0),
}


def _materiais(ctx) -> None:
    """Os materiais `el_*` (nomes partilhados no spec: o primeiro módulo a criar um nome ganha)."""
    for nome, (rgba, spec, brilho, refl, emis) in _MATERIAIS.items():
        ctx.material(nome, rgba, specular=spec, shininess=brilho, reflectance=refl, emission=emis)


def _quat(r: np.ndarray) -> list:
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.asarray(r, dtype=float).reshape(9))
    return [float(v) for v in q]


def _rz(ang: float) -> np.ndarray:
    c, s = math.cos(ang), math.sin(ang)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _mat_de_quat(q) -> np.ndarray:
    r = np.zeros(9)
    mujoco.mju_quat2Mat(r, np.asarray(q, dtype=float))
    return r.reshape(3, 3)


class _Kit:
    """Peças num referencial LOCAL (mm) de um corpo: `origem` (m, no corpo) e rotação `R` (local → corpo)."""

    def __init__(self, ctx, corpo: str, origem, r: np.ndarray | None = None):
        self.ctx, self.corpo = ctx, corpo
        self.o = np.asarray(origem, dtype=float)
        self.r = np.eye(3) if r is None else np.asarray(r, dtype=float)

    def p(self, x, y, z) -> list:
        return [float(v) for v in self.o + self.r @ (np.array([x, y, z], dtype=float) * MM)]

    def q(self, rl: np.ndarray | None = None) -> list:
        return _quat(self.r if rl is None else self.r @ rl)

    def caixa(self, nome, x0, x1, y0, y1, z0, z1, mat):
        """Caixa pelos limites (mm, referencial local)."""
        meia = [0.5 * abs(x1 - x0) * MM, 0.5 * abs(y1 - y0) * MM, 0.5 * abs(z1 - z0) * MM]
        if min(meia) <= 0.0:
            return None
        return self.ctx.geom(self.corpo, nome, type=CAIXA, size=meia,
                             pos=self.p(0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)), quat=self.q(),
                             material=mat)

    def cil(self, nome, centro, raio, meia, mat, eixo: str = "z"):
        if raio <= 0.0 or meia <= 0.0:
            return None
        rl = {"z": None, "x": R_EIXO_X, "y": R_EIXO_Y}[eixo]
        return self.ctx.geom(self.corpo, nome, type=CIL, size=[raio * MM, meia * MM, 0.0], pos=self.p(*centro),
                             quat=self.q(rl), material=mat)

    def cil_z(self, nome, x, y, z0, z1, raio, mat):
        return self.cil(nome, (x, y, 0.5 * (z0 + z1)), raio, 0.5 * (z1 - z0), mat, "z")

    def cil_x(self, nome, x0, x1, y, z, raio, mat):
        return self.cil(nome, (0.5 * (x0 + x1), y, z), raio, 0.5 * (x1 - x0), mat, "x")

    def cil_y(self, nome, x, y0, y1, z, raio, mat):
        return self.cil(nome, (x, 0.5 * (y0 + y1), z), raio, 0.5 * (y1 - y0), mat, "y")

    def capsula(self, nome, p0, p1, raio, mat):
        a, b = self.p(*p0), self.p(*p1)
        if np.linalg.norm(np.subtract(a, b)) < 1e-6:
            return None
        return self.ctx.geom(self.corpo, nome, type=CAPS, size=[raio * MM, 0.0, 0.0], fromto=a + b, material=mat)


def _info(ctx, nome: str):
    """(centro, meias-medidas) de uma caixa que já existe, ou None."""
    g = ctx.geom_existente(nome)
    if g is None:
        return None
    return np.array(g.pos, dtype=float), np.array(g.size, dtype=float)


def _esconder(ctx, nome: str) -> None:
    if ctx.geom_existente(nome) is not None:
        ctx.esconder(nome)


def _apagar(ctx, *nomes: str) -> None:
    """Apaga detalhes visuais antigos (só os que são mesmo só visuais) — ANTES de se reutilizar o nome."""
    for nome in nomes:
        g = ctx.geom_existente(nome)
        if g is not None and int(g.group) in (1, 2, 3) and float(g.mass) == 0.0 and not g.contype \
                and not g.conaffinity:
            ctx.apagar(nome)


# =================================================================================================== Raspberry Pi 5
_RPI5_FUROS = ((3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5))
_RPI5_ANTIGOS = ("rpi5_soc_bcm2712", "rpi5_dissipador", "rpi5_ventoinha", "rpi5_rp1", "rpi5_rj45", "rpi5_usb3_torre",
                 "rpi5_usb3_azul", "rpi5_usb2_torre", "rpi5_gpio_40p", "rpi5_usbc", "rpi5_micro_hdmi_1",
                 "rpi5_micro_hdmi_2")


def _rpi5(ctx, rpi, z_placa_topo: float | None, z_ponte: float | None) -> None:
    """Raspberry Pi 5 + Active Cooler. Coordenadas da PLACA (mm, origem no canto de baixo-esquerdo do desenho
    mecânico: x de 0 (PCIe) a 85 (USB/RJ45), y de 0 (USB-C/HDMI) a 56 (GPIO), z a partir da face de baixo da PCB)."""
    _apagar(ctx, *_RPI5_ANTIGOS)                     # os nomes antigos passam para as peças novas equivalentes
    c, h = rpi
    z0 = c[2] - h[2]
    k = _Kit(ctx, "drone", (c[0] - 0.0425, c[1] - 0.028, z0))
    k.caixa("el_rpi5_pcb", 0.0, 85.0, 0.0, 56.0, 0.0, 1.6, "el_pcb_verde")
    # pilares M2,5 de latão: 6 mm até à placa por baixo; por cima, 16 mm até à ponte do FC (ou parafusos de cabeça)
    for i, (fx, fy) in enumerate(_RPI5_FUROS, 1):
        if z_placa_topo is not None:
            k.cil_z(f"el_rpi5_pilar_inf{i}", fx, fy, (z_placa_topo - z0) / MM, 0.0, 2.6, "el_latao")
        if z_ponte is not None:
            k.cil_z(f"el_rpi5_pilar_sup{i}", fx, fy, 1.6, (z_ponte - z0) / MM, 2.6, "el_latao")
        else:
            k.cil_z(f"el_rpi5_parafuso{i}", fx, fy, 1.6, 3.2, 2.25, "el_aco")

    # SoC e RP1 (debaixo das almofadas térmicas do dissipador)
    k.caixa("rpi5_soc_bcm2712", 16.0, 33.0, 20.0, 37.0, 1.6, 2.6, "el_tampa_soc")
    k.caixa("rpi5_rp1", 51.0, 61.0, 25.5, 35.5, 1.6, 2.5, "el_chip")

    # Active Cooler (63,5 × 42,5 × 13,7): base em L (livre dos MIPI e da Ethernet), aletas, ventoinha radial de 30 mm
    k.caixa("rpi5_dissipador", 4.5, 44.0, 7.0, 49.5, 2.6, 5.0, "el_aluminio")
    k.caixa("el_rpi5_cooler_base_b", 44.0, 65.5, 19.0, 49.5, 2.6, 5.0, "el_aluminio")
    for i in range(7):
        x_a = 45.4 + 3.25 * i
        k.caixa(f"el_rpi5_aleta{i + 1}", x_a, x_a + 1.0, 19.5, 47.0, 5.0, 16.3, "el_aluminio")
    k.caixa("el_rpi5_cooler_trilho_a", 4.5, 44.0, 7.0, 9.0, 5.0, 12.5, "el_aluminio")
    k.caixa("el_rpi5_cooler_trilho_b", 4.5, 44.0, 47.5, 49.5, 5.0, 12.5, "el_aluminio")
    k.caixa("rpi5_ventoinha", 9.5, 39.5, 13.0, 43.0, 5.0, 14.6, "el_plastico_preto")
    k.cil_z("el_rpi5_ventoinha_entrada", 24.5, 28.0, 14.6, 14.9, 11.0, "el_cinza_escuro")
    k.cil_z("el_rpi5_ventoinha_cubo", 24.5, 28.0, 14.9, 15.5, 6.5, "el_plastico_brilho")
    k.cil_z("el_rpi5_pino_cooler1", 6.8, 11.5, 5.0, 7.0, 2.1, "el_nylon")
    k.cil_z("el_rpi5_pino_cooler2", 42.0, 44.0, 5.0, 7.0, 2.1, "el_nylon")
    # cabo da ventoinha (4 fios) até ao conector FAN (JST-SH 4 vias, entre o fim do GPIO e as USB 2.0)
    k.capsula("el_rpi5_fan_cabo1", (38.5, 42.0, 14.2), (41.5, 48.6, 13.3), 0.7, "el_plastico_preto")
    k.capsula("el_rpi5_fan_cabo2", (41.5, 48.6, 13.3), (64.5, 48.6, 13.3), 0.7, "el_plastico_preto")
    k.capsula("el_rpi5_fan_cabo3", (64.5, 48.6, 13.3), (67.4, 50.5, 6.2), 0.7, "el_plastico_preto")
    k.caixa("el_rpi5_fan_conector", 64.4, 70.4, 48.5, 52.7, 1.6, 4.5, "el_jst")
    k.caixa("el_rpi5_fan_ficha", 64.9, 69.9, 48.9, 52.3, 4.5, 6.4, "el_jst")

    # GPIO 2×20 (passo 2,54): base preta + 20 colunas de pinos dourados (6 mm acima da base)
    k.caixa("rpi5_gpio_40p", 7.1, 57.9, 49.96, 55.04, 1.6, 4.1, "el_plastico_preto")
    for i in range(20):
        xc = 8.37 + 2.54 * i
        k.caixa(f"el_rpi5_gpio_pino{i + 1:02d}", xc - 0.32, xc + 0.32, 50.91, 54.09, 4.1, 10.1, "el_ouro")

    # borda direita: USB 2.0 (y = 47), USB 3.0 (y = 29,1, línguas azuis) e RJ45 (y = 10,2) a sair ~3 mm da PCB
    for nome, yc, lingua in (("rpi5_usb2_torre", 47.0, None), ("rpi5_usb3_torre", 29.1, "el_usb_azul")):
        y0, y1 = yc - 6.6, yc + 6.6
        k.caixa(nome, 70.5, 88.0, y0, y1, 1.6, 17.2, "el_aco")
        for j, (zb, zt) in enumerate(((3.0, 8.0), (10.4, 15.4)), 1):
            k.caixa(f"el_{nome}_porta{j}", 88.0, 88.15, y0 + 0.6, y1 - 0.6, zb, zt, "el_abertura")
            if lingua is not None:
                nome_l = "rpi5_usb3_azul" if j == 1 else f"el_{nome}_lingua{j}"
                k.caixa(nome_l, 88.0, 88.3, y0 + 1.2, y1 - 1.2, zt - 2.6, zt - 0.9, lingua)
    k.caixa("rpi5_rj45", 66.6, 88.0, 2.2, 18.2, 1.6, 14.9, "el_aco")
    k.caixa("el_rpi5_rj45_porta", 88.0, 88.15, 4.3, 16.1, 2.6, 11.0, "el_abertura")
    k.caixa("el_rpi5_rj45_led_verde", 88.0, 88.25, 3.0, 5.4, 12.0, 13.8, "el_led_verde")
    k.caixa("el_rpi5_rj45_led_ambar", 88.0, 88.25, 15.0, 17.4, 12.0, 13.8, "el_led_ambar")

    # borda de baixo: USB-C (x = 11,2), 2× micro-HDMI (25,8 e 39,2), RTC e UART (JST-SH), 2× MIPI 22 vias
    k.caixa("rpi5_usbc", 6.73, 15.67, -1.2, 6.3, 1.6, 4.8, "el_aco")
    k.caixa("el_rpi5_usbc_porta", 7.5, 14.9, -1.35, -1.2, 2.3, 4.1, "el_abertura")
    for i, xc in enumerate((25.8, 39.2), 1):
        k.caixa(f"rpi5_micro_hdmi_{i}", xc - 3.75, xc + 3.75, -1.0, 5.8, 1.6, 5.0, "el_aco")
        k.caixa(f"el_rpi5_micro_hdmi_{i}_porta", xc - 3.0, xc + 3.0, -1.15, -1.0, 2.3, 4.3, "el_abertura")
    k.caixa("el_rpi5_rtc", 17.5, 21.5, 0.8, 5.05, 1.6, 4.5, "el_jst")
    k.caixa("el_rpi5_uart", 30.0, 35.0, 0.8, 5.05, 1.6, 4.5, "el_jst")
    for nome, x_m in (("el_rpi5_cam_disp0", 46.0), ("el_rpi5_ffc_disp1", 53.5)):
        k.caixa(nome, x_m, x_m + 4.5, 2.0, 16.6, 1.6, 3.6, "el_plastico_preto")
        k.caixa(f"{nome}_trava", x_m + 4.5, x_m + 5.5, 2.3, 16.3, 1.6, 3.9, "el_trava_fpc")

    # borda esquerda: FFC PCIe (16 vias), botão de energia e LED bicolor
    k.caixa("el_rpi5_pcie", 0.4, 4.4, 22.0, 34.0, 1.6, 3.4, "el_plastico_preto")
    k.caixa("el_rpi5_botao", -0.5, 3.8, 8.0, 11.6, 1.6, 3.4, "el_plastico_preto")
    k.caixa("el_rpi5_led", 0.2, 1.4, 13.0, 14.6, 1.6, 2.2, "el_led_verde")
    _esconder(ctx, "el_rpi5")


def _ponte_fc(ctx, rpi, centro_pilha, z_fundo: float) -> None:
    """Ponte de carbono (1,5 mm) nos 4 pilares do Pi: 2 réguas sobre os furos (x = 3,5 e 61,5) e 2 travessas nas
    linhas dos furos de 30,5 mm do FC/placa de energia (y = centro ± 15,25)."""
    c, _h = rpi
    k = _Kit(ctx, "drone", (c[0] - 0.0425, c[1] - 0.028, z_fundo))
    yc = 28.0 + (centro_pilha[1] - c[1]) / MM
    k.caixa("el_ponte_fc_tras", -0.5, 7.5, -0.5, 56.5, 0.0, 1.5, "el_carbono")
    k.caixa("el_ponte_fc_frente", 57.5, 65.5, -0.5, 56.5, 0.0, 1.5, "el_carbono")
    k.caixa("el_ponte_fc_esq", 7.5, 57.5, yc + 11.25, yc + 19.25, 0.0, 1.5, "el_carbono")
    k.caixa("el_ponte_fc_dir", 7.5, 57.5, yc - 19.25, yc - 11.25, 0.0, 1.5, "el_carbono")


# =================================================================================================== FC H7
_FUROS_30 = ((15.25, 15.25), (-15.25, 15.25), (-15.25, -15.25), (15.25, -15.25))


def _fc_h7(ctx, fc, z_pdb_fundo: float | None, com_imu: bool) -> None:
    """FC H743 30×30 (referencial: centro da caixa em xy, z a partir da face de baixo da PCB; frente para +x)."""
    c, h = fc
    z0 = c[2] - h[2]
    k = _Kit(ctx, "drone", (c[0], c[1], z0))
    k.caixa("el_fc_pcb", -18.0, 18.0, -18.0, 18.0, 0.0, 1.6, "el_pcb_preto")
    for i, (fx, fy) in enumerate(_FUROS_30, 1):
        k.cil_z(f"el_fc_amortecedor{i}", fx, fy, -1.0, 2.8, 3.6, "el_silicone")
        if z_pdb_fundo is not None:
            k.cil_z(f"el_fc_espacador{i}", fx, fy, 2.8, (z_pdb_fundo - z0) / MM, 2.6, "el_nylon")
        else:
            k.cil_z(f"el_fc_porca{i}", fx, fy, 2.8, 5.2, 2.8, "el_nylon")
    k.caixa("el_fc_mcu", -7.0, 7.0, -7.0, 7.0, 1.6, 3.0, "el_chip")
    k.caixa("el_fc_mcu_pernas", -8.0, 8.0, -8.0, 8.0, 1.6, 1.85, "el_estanho")
    if com_imu:
        k.caixa("el_fc_imu_bmi088", -12.0, -9.0, 3.0, 7.5, 1.6, 2.55, "el_chip")
    k.caixa("el_fc_baro_espuma", 6.0, 12.0, -14.5, -8.5, 1.6, 4.1, "el_espuma")
    k.caixa("el_fc_usbc", -12.47, -3.53, -18.6, -11.25, 1.6, 4.8, "el_aco")
    k.caixa("el_fc_usbc_porta", -11.7, -4.3, -18.75, -18.6, 2.3, 4.1, "el_abertura")
    k.caixa("el_fc_microsd", -4.0, 8.0, -9.0, 3.0, -1.85, 0.0, "el_aco")
    # JST-GH: ESC atrás (8 vias), GPS e I2C à frente, UART e sensores na borda +y (entrada lateral, rente à borda)
    k.caixa("el_fc_con_esc", -17.8, -13.55, -4.5, 4.5, 1.6, 4.5, "el_jst")
    k.caixa("el_fc_con_gps", 13.4, 17.6, -9.4, -0.6, 1.6, 5.85, "el_jst")
    k.caixa("el_fc_con_i2c", 13.4, 17.6, 2.4, 8.6, 1.6, 5.85, "el_jst")
    k.caixa("el_fc_con_uart", -11.5, -5.5, 13.75, 18.0, 1.6, 5.85, "el_jst")
    k.caixa("el_fc_con_sensores", 4.4, 11.6, 13.75, 18.0, 1.6, 5.85, "el_jst")
    k.caixa("el_fc_led_verde", -10.8, -9.2, -12.4, -11.6, 1.6, 2.2, "el_led_verde")
    k.caixa("el_fc_led_azul", -7.8, -6.2, -12.4, -11.6, 1.6, 2.2, "el_led_azul")
    _esconder(ctx, "el_fc_h7")


# =================================================================================================== placa de energia
def _sinais_rotores(ctx) -> list:
    try:
        return [(1.0 if x >= 0 else -1.0, 1.0 if y >= 0 else -1.0) for x, y in ctx.hw.pos_rotores]
    except Exception:  # noqa: BLE001
        return [(1.0, 1.0), (-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0)]


def _pdb(ctx, pdb, apoio: str, z_apoio: float | None, com_ina: bool) -> None:
    """Módulo de energia + BEC 5 V/5 A (60×40): ilhas estanhadas da bateria e de cada ESC, shunt + INA226, BEC.
    `apoio`: «pilha» (na pilha M3 do FC), «ponte» (espaçadores na ponte) ou «placa» (pilares desde a placa)."""
    c, h = pdb
    z0 = c[2] - h[2]
    k = _Kit(ctx, "drone", (c[0], c[1], z0))
    k.caixa("el_pdb_pcb", -30.0, 30.0, -20.0, 20.0, 0.0, 1.6, "el_pcb_vermelho")
    if apoio in ("ponte", "placa") and z_apoio is not None:
        for i, (fx, fy) in enumerate(_FUROS_30, 1):
            k.cil_z(f"el_pm_espacador{i}", fx, fy, (z_apoio - z0) / MM, 0.0, 2.4, "el_nylon")
    # ilhas: bateria atrás (−x), um par +/− por ESC no canto do braço respetivo
    k.caixa("el_pdb_bat_pos", -29.5, -23.5, 2.0, 10.0, 1.6, 2.0, "el_estanho")
    k.caixa("el_pdb_bat_neg", -29.5, -23.5, -10.0, -2.0, 1.6, 2.0, "el_estanho")
    for i, (sx, sy) in enumerate(_sinais_rotores(ctx), 1):
        k.caixa(f"el_pdb_esc{i}_pos", sx * 24.75 - 2.25, sx * 24.75 + 2.25, sy * 14.5 - 3.0, sy * 14.5 + 3.0, 1.6,
                1.95, "el_estanho")
        k.caixa(f"el_pdb_esc{i}_neg", sx * 19.25 - 2.0, sx * 19.25 + 2.0, sy * 14.5 - 3.0, sy * 14.5 + 3.0, 1.6,
                1.95, "el_estanho")
    if com_ina:
        k.caixa("el_pm_shunt", -19.0, -12.6, -1.6, 1.6, 1.6, 2.5, "el_estanho")
        k.caixa("el_pm_ina226", -11.0, -8.0, -6.5, -3.5, 1.6, 2.7, "el_chip")
    k.caixa("el_pm_bec_indutor", 2.0, 10.0, -15.0, -7.0, 1.6, 6.1, "el_ferrite")
    k.caixa("el_pm_bec_ci", -4.5, 0.5, -13.0, -9.0, 1.6, 3.1, "el_chip")
    k.cil_z("el_pm_bec_cap1", 14.5, -11.0, 1.6, 7.1, 3.15, "el_cap_polimero")
    k.cil_z("el_pm_bec_cap2", 14.5, -3.5, 1.6, 7.1, 3.15, "el_cap_polimero")
    k.caixa("el_pm_con_i2c", 25.4, 29.6, -5.0, 5.0, 1.6, 5.85, "el_jst")
    k.caixa("el_pm_saida_5v", -6.0, 6.0, 12.0, 16.5, 1.6, 6.5, "el_jst")
    _esconder(ctx, "el_cablagem")


def _imu_avulsa(ctx, kit: _Kit, x: float, y: float, z: float) -> None:
    """BMI088 numa placa de 18×14 (roxa) com barra de 6 pinos — para os builds sem FC (o Portenta não tem IMU)."""
    kit.caixa("el_imu_pcb", x - 9.0, x + 9.0, y - 7.0, y + 7.0, z, z + 1.6, "el_pcb_roxo")
    kit.caixa("el_imu_bmi088", x - 1.5, x + 1.5, y - 2.25, y + 2.25, z + 1.6, z + 2.55, "el_chip")
    kit.caixa("el_imu_barra", x + 5.5, x + 8.0, y - 6.5, y + 6.5, z + 1.6, z + 4.1, "el_plastico_preto")
    kit.caixa("el_imu_pinos", x + 6.4, x + 7.1, y - 6.0, y + 6.0, z + 4.1, z + 7.0, "el_ouro")


# =================================================================================================== Portenta H7
def _portenta(ctx, port, z_placa_topo: float | None) -> None:
    """Arduino Portenta H7 (66,04×25,4): conectores de alta densidade por baixo, STM32H747, SDRAM, Wi-Fi blindado."""
    c, h = port
    z_pcb = c[2] - h[2] + 1.5 * MM       # os conectores HD (1,5 mm) por baixo da PCB
    k = _Kit(ctx, "drone", (c[0], c[1], z_pcb))
    hx, hy = 33.02, 12.7
    k.caixa("el_portenta_pcb", -hx, hx, -hy, hy, 0.0, 1.0, "el_pcb_preto")
    if z_placa_topo is not None:
        for i, (fx, fy) in enumerate(((hx - 2.5, hy - 2.5), (-hx + 2.5, hy - 2.5), (-hx + 2.5, -hy + 2.5),
                                      (hx - 2.5, -hy + 2.5)), 1):
            k.cil_z(f"el_portenta_pilar{i}", fx, fy, (z_placa_topo - z_pcb) / MM, 0.0, 1.8, "el_latao")
    for i, yy in enumerate((6.0, -6.0), 1):
        k.caixa(f"el_portenta_hd{i}", -12.0, 12.0, yy - 1.8, yy + 1.8, -1.5, 0.0, "el_plastico_preto")
    k.caixa("el_portenta_mcu", -8.0, 6.0, -7.0, 7.0, 1.0, 2.2, "el_chip")
    k.caixa("el_portenta_sdram", 9.0, 17.0, -6.0, 6.0, 1.0, 2.0, "el_chip")
    k.caixa("el_portenta_wifi", 19.5, 29.5, -1.0, 7.5, 1.0, 2.4, "el_aco")
    k.caixa("el_portenta_usbc", -36.4, -27.5, -4.47, 4.47, 1.0, 4.2, "el_aco")
    k.caixa("el_portenta_usbc_porta", -36.55, -36.4, -3.7, 3.7, 1.7, 3.5, "el_abertura")
    k.caixa("el_portenta_eslov", 27.0, 31.0, -11.5, -5.5, 1.0, 4.0, "el_jst")
    k.caixa("el_portenta_bateria", -24.0, -18.0, -11.8, -8.0, 1.0, 4.0, "el_jst")
    for i, yy in enumerate((hy - 0.3, -hy + 0.3), 1):
        k.caixa(f"el_portenta_castelado{i}", -30.0, 30.0, yy - 0.4, yy + 0.4, 0.0, 1.05, "el_ouro")
    _esconder(ctx, "el_arduino_portenta_h7")


# =================================================================================================== ESC
def _raio_tubo_mm(ctx, omissao: float) -> float:
    """Raio exterior do tubo dos braços (catálogo: «tubo de carbono 25×23 mm» → 12,5 mm) — o módulo `estrutura`
    desenha-o assim; sem o número no catálogo, a meia-altura da caixa física."""
    texto = str(ctx.hw.frame.dados.get("modelo", ""))
    m = re.search(r"tubo[^0-9]*?(\d+(?:[.,]\d+)?)\s*[×x]\s*\d+(?:[.,]\d+)?\s*mm", texto)
    return 0.5 * float(m.group(1).replace(",", ".")) if m else omissao


def _assento_esc(ctx, k_braco: int, p_drone: np.ndarray, meia_z: float):
    """(corpo, posição no corpo, rotação do corpo, z da base do ESC no corpo): no rígido a base da caixa `esc{k}` (o
    topo do tubo da `estrutura`); no articulado o topo do tubo redondo do braço, no corpo `braco{k}`."""
    tubo = ctx.geom_existente(f"braco{k_braco}_tubo")
    if tubo is not None and ctx.existe_corpo(f"braco{k_braco}"):
        b = ctx.corpo(f"braco{k_braco}")
        r_b = _mat_de_quat(b.quat)
        p_loc = r_b.T @ (p_drone - np.array(b.pos, dtype=float))
        r_tubo = _raio_tubo_mm(ctx, float(tubo.size[2]) / MM) * MM
        return f"braco{k_braco}", p_loc, r_b, float(tubo.pos[2]) + r_tubo
    return "drone", p_drone, np.eye(3), float(p_drone[2]) - meia_z


def _esc_air40a(ctx, k_esc: int) -> None:
    """T-Motor AIR 40A (55,6×25,2×11,3) ao longo do braço: termorretrátil, rótulo, condensador, saídas."""
    g = ctx.geom_existente(f"esc{k_esc}")
    p = np.array(g.pos, dtype=float)
    corpo, p_loc, r_b, z_base = _assento_esc(ctx, k_esc, p, float(g.size[2]))
    d = r_b.T @ np.array([p[0], p[1], 0.0])          # direção do braço (do centro para fora) no corpo do ESC
    ang = math.atan2(d[1], d[0])
    k = _Kit(ctx, corpo, (p_loc[0], p_loc[1], z_base), _rz(ang))
    n = f"el_esc{k_esc}"
    k.caixa(f"{n}_corpo", -27.8, 27.8, -12.6, 12.6, 0.0, 11.3, "el_termo_preto")
    k.caixa(f"{n}_rotulo", -4.0, 22.0, -9.5, 9.5, 11.3, 11.45, "el_rotulo_esc")
    k.caixa(f"{n}_rotulo_texto", 0.0, 18.0, -2.4, 2.4, 11.45, 11.5, "el_rotulo_branco")   # «AIR 40A» impresso
    k.caixa(f"{n}_saida_fases", 27.8, 31.5, -9.0, 9.0, 2.5, 7.5, "el_termo_preto")
    k.caixa(f"{n}_saida_entrada", -31.5, -27.8, -7.0, 7.0, 2.5, 7.5, "el_termo_preto")
    k.cil_x(f"{n}_condensador", -25.0, -9.5, 0.0, 16.3, 5.0, "el_condensador")
    k.cil_x(f"{n}_condensador_topo", -9.5, -9.1, 0.0, 16.3, 4.3, "el_aluminio")
    _esconder(ctx, f"esc{k_esc}")


def _esc_4em1(ctx) -> None:
    """ESC 4-em-1 (padrão 30,5 mm): PCB preta, 4 pares de MOSFET, MCU, condensador, ilhas dos motores, amortecedores."""
    c, h = _info(ctx, "esc")
    z0 = c[2] - h[2]
    k = _Kit(ctx, "drone", (c[0], c[1], z0))
    k.caixa("el_esc4_pcb", -19.0, 19.0, -19.0, 19.0, 0.0, 1.6, "el_pcb_preto")
    for i, (fx, fy) in enumerate(_FUROS_30, 1):
        k.cil_z(f"el_esc4_amortecedor{i}", fx, fy, -0.5, 3.0, 3.4, "el_silicone")
    for i, (sx, sy) in enumerate(((1, 1), (-1, -1), (-1, 1), (1, -1)), 1):
        k.caixa(f"el_esc4_mosfets{i}", sx * 9.0 - 3.0, sx * 9.0 + 3.0, sy * 5.0 - 5.0, sy * 5.0 + 5.0, 1.6, 2.7,
                "el_chip")
        k.caixa(f"el_esc4_ilhas{i}", sx * 17.0 - 1.5, sx * 17.0 + 1.5, sy * 6.0 - 4.5, sy * 6.0 + 4.5, 1.6, 1.9,
                "el_estanho")
    k.caixa("el_esc4_mcu", -2.5, 2.5, -2.5, 2.5, 1.6, 2.6, "el_chip")
    k.cil_x("el_esc4_condensador", -8.0, 8.0, -14.0, 6.6, 5.0, "el_condensador")
    _esconder(ctx, "esc")


# =================================================================================================== câmaras
def _suporte_camera(ctx, k: _Kit, xb: float, hy: float, hz: float, z_placa_loc: float | None) -> None:
    """Suporte em L de PETG atrás da placa da câmara, aparafusado à placa central, com passagem por baixo para o FPC
    (16 mm) — estimado."""
    if z_placa_loc is None:
        return
    k.caixa("el_cam_suporte", xb - 2.0, xb, -hy - 2.0, hy + 2.0, z_placa_loc + 3.5, hz - 1.0, "el_petg")
    for i, s in enumerate((1.0, -1.0), 1):
        y0, y1 = sorted((s * (hy - 3.5), s * (hy + 2.0)))
        k.caixa(f"el_cam_suporte_pe{i}", xb - 12.0, xb, y0, y1, z_placa_loc, z_placa_loc + 4.0, "el_petg")


def _camera_csi(ctx, cam, z_placa_topo: float | None) -> None:
    """Raspberry Pi Camera Module 3 (Wide) de pé no nariz, lente para +x (referencial: centro da caixa `camera`)."""
    c, h = cam
    k = _Kit(ctx, "drone", c)
    hx, hy, hz = (float(v) / MM for v in h)
    xb, xf = -hx, -hx + 2.0                          # face de trás da caixa / face da frente da PCB (1 mm de PCB)
    z_l = hz - 0.394 * 2.0 * hz                      # centro ótico a 9,46 mm do topo de uma placa de 24 mm
    k.caixa("el_cam_pcb", xb + 1.0, xf, -hy, hy, -hz, hz, "el_pcb_verde")
    k.caixa("el_cam_sensor", xf, xf + 4.6, -4.25, 4.25, z_l - 4.25, z_l + 4.25, "el_plastico_preto")
    k.cil_x("el_cam_lente", xf + 4.6, hx - 0.25, 0.0, z_l, 3.9, "el_plastico_brilho")
    k.cil_x("el_cam_vidro", hx - 0.25, hx - 0.05, 0.0, z_l, 2.9, "el_vidro")
    k.caixa("el_cam_conector_fpc", xf, xf + 2.5, -10.4, 10.4, -hz, -hz + 5.0, "el_plastico_preto")
    k.caixa("el_cam_conector_trava", xf, xf + 3.0, -10.0, 10.0, -hz - 0.4, -hz + 0.8, "el_trava_fpc")
    for i, (yy, zz) in enumerate(((hy - 2.0, hz - 2.0), (-hy + 2.0, hz - 2.0), (-hy + 2.0, hz - 14.5),
                                  (hy - 2.0, hz - 14.5)), 1):
        k.cil_x(f"el_cam_parafuso{i}", xf, xf + 1.2, yy, zz, 1.9, "el_aco")
    _suporte_camera(ctx, k, xb, hy, hz, None if z_placa_topo is None else (z_placa_topo - c[2]) / MM)
    _esconder(ctx, "camera")


def _camera_dvp(ctx, cam, z_placa_topo: float | None) -> None:
    """Portenta Vision Shield (HM0360) de pé no nariz: conectores HD atrás, PCB, módulo da câmara e microfones."""
    c, h = cam
    k = _Kit(ctx, "drone", c)
    hx, hy, hz = (float(v) / MM for v in h)
    xb = -hx
    xf = xb + 4.0
    k.caixa("el_cam_pcb", xb + 3.0, xf, -hy, hy, -hz, hz, "el_pcb_preto")
    for i, yy in enumerate((-hy * 0.45, hy * 0.45), 1):
        k.caixa(f"el_cam_hd{i}", xb + 1.5, xb + 3.0, yy - 10.0, yy + 10.0, -1.8, 1.8, "el_plastico_preto")
    k.caixa("el_cam_sensor", xf, xf + 2.5, -3.0, 3.0, -3.0, 3.0, "el_plastico_preto")
    k.cil_x("el_cam_lente", xf + 2.5, hx - 0.25, 0.0, 0.0, 2.2, "el_plastico_brilho")
    k.cil_x("el_cam_vidro", hx - 0.25, hx - 0.05, 0.0, 0.0, 1.4, "el_vidro")
    for i, yy in enumerate((-14.0, 14.0), 1):
        k.caixa(f"el_cam_microfone{i}", xf, xf + 1.0, yy - 1.75, yy + 1.75, 5.0, 7.65, "el_aco")
    _suporte_camera(ctx, k, xb, hy, hz, None if z_placa_topo is None else (z_placa_topo - c[2]) / MM)
    _esconder(ctx, "camera")


# =================================================================================================== sensores de baixo
def _sensores_baixo(ctx, z_bat_fundo: float, meia_x_bandeja: float, com_fluxo: bool, com_tof: bool) -> None:
    """PMW3901 (24×24×5, bloco ótico com lente) e VL53L1X (13×18×2) numa bandeja de PETG debaixo do pack."""
    sb = _info(ctx, "sensores_baixo")
    if sb is None or not (com_fluxo or com_tof):
        return
    c, _h = sb
    k = _Kit(ctx, "drone", (c[0], c[1], z_bat_fundo))
    k.caixa("el_bandeja_sensores", -meia_x_bandeja, meia_x_bandeja, -20.0, 20.0, -1.5, 0.0, "el_petg")
    if com_fluxo:
        k.caixa("el_fluxo_pcb", -12.0, 12.0, -12.0, 12.0, -3.1, -1.5, "el_pcb_preto")
        k.caixa("el_fluxo_otica", -3.25, 3.25, -3.25, 3.25, -5.6, -3.1, "el_plastico_preto")
        k.cil_z("el_fluxo_lente", 0.0, 0.0, -5.8, -5.6, 1.6, "el_vidro")
        k.caixa("el_fluxo_conector", -11.5, -7.0, -6.0, 6.0, -5.6, -3.1, "el_jst")
    if com_tof:
        x_t = 22.5 if com_fluxo else 0.0
        k.caixa("el_tof_pcb", x_t - 9.0, x_t + 9.0, -6.5, 6.5, -3.1, -1.5, "el_pcb_pololu")
        k.caixa("el_tof_vl53l1x", x_t - 2.45, x_t + 2.45, -1.25, 1.25, -4.66, -3.1, "el_chip")
        k.caixa("el_tof_janelas", x_t - 1.9, x_t + 1.9, -0.55, 0.55, -4.72, -4.66, "el_vidro")
    _esconder(ctx, "sensores_baixo")


# =================================================================================================== bateria
def _arranjo_celulas(meias_mm: np.ndarray, diam: float, comp: float, n: int):
    """Células cilíndricas deitadas ao longo de y numa grelha n1 (x) × n2 (z) que caiba na caixa do pack (tolerância de
    4 % na secção e 8 % no comprimento); None se as medidas do catálogo não as acomodarem."""
    c, l_, a = (2.0 * float(v) for v in meias_mm)
    if comp > 1.08 * l_:
        return None
    melhor = None
    for n1 in range(1, n + 1):
        if n % n1:
            continue
        n2 = n // n1
        if n1 * diam <= 1.04 * c and n2 * diam <= 1.04 * a:
            folga = (c - n1 * diam) + (a - n2 * diam)
            if melhor is None or folga < melhor[0]:
                melhor = (folga, n1, n2)
    return None if melhor is None else (melhor[1], melhor[2])


def _bateria(ctx, z_placa: tuple | None, com_bandeja: bool, meia_x_bandeja: float) -> None:
    """Pack da bateria + XT90 + tapete + cintas (referencial: centro da caixa `bateria`)."""
    _apagar(ctx, "conector_xt90", "cinta_bateria_1", "cinta_bateria_2")   # os nomes passam para as peças novas
    pb, sb = _info(ctx, "bateria")
    hw = ctx.hw
    k = _Kit(ctx, "drone", pb)
    mx, my, mz = (float(v) / MM for v in sb)          # meias-medidas do pack (mm)
    cel = hw.bateria.celula
    dims = tuple(float(v) for v in (cel.dims_mm or ()))
    arr = _arranjo_celulas(sb / MM, dims[0], dims[1], hw.bateria.s * hw.bateria.p) if len(dims) == 2 else None
    if arr is not None:
        # termorretrátil por cima das células: as colunas das pontas dão os lados arredondados, o meio é plano
        n1, n2 = arr
        d = dims[0]
        px, pz = max(d, 2.0 * mx / n1), max(d, 2.0 * mz / n2)
        r = 0.5 * min(d, px, pz)
        meia_comp = min(0.5 * dims[1], my) - 1.0
        x_ext = (n1 - 1) * 0.5 * px
        zs = [-(n2 - 1) * 0.5 * pz + j * pz for j in range(n2)]
        topo = zs[-1] + r
        for i, xi in enumerate(sorted({-x_ext, x_ext}), 1):
            for j, zj in enumerate(zs, 1):
                k.cil_y(f"el_bat_celula{i}{j}", xi, -meia_comp, meia_comp, zj, r, "el_termo_bateria")
        if n1 > 1:
            k.caixa("el_bat_nucleo", -x_ext, x_ext, -meia_comp, meia_comp, -topo, topo, "el_termo_bateria")
        x_topo, z_topo = x_ext + r - 0.6, topo - 0.6
        janela_x, janela_z = max(x_topo - 9.0, 0.5 * x_topo), max(z_topo - 7.0, 0.5 * z_topo)
        for s, nome in ((1.0, "pos"), (-1.0, "neg")):
            y0, y1 = sorted((s * meia_comp, s * (meia_comp + 0.6)))
            k.caixa(f"el_bat_topo_{nome}", -x_topo, x_topo, y0, y1, -z_topo, z_topo, "el_termo_bateria")
        k.caixa("el_bat_papel_peixe", -janela_x, janela_x, meia_comp + 0.6, meia_comp + 0.8, -janela_z, janela_z,
                "el_papel_peixe")
        y_face, hz_face = meia_comp + 0.6, z_topo
    else:
        k.caixa("el_bat_bloco", -mx, mx, -my, my, -mz, mz, "el_termo_pouch")
        y_face, hz_face = my, mz
    # rótulo na face −y (a que se vê de frente-direita): fundo branco, faixa de cor e 3 linhas de «texto»
    rx, rz = min(30.0, 0.42 * mx), max(4.0, hz_face - 5.0)
    yr = -y_face
    k.caixa("el_bat_rotulo", -rx, rx, yr - 0.15, yr, -rz, rz, "el_rotulo_branco")
    k.caixa("el_bat_rotulo_faixa", -rx, rx, yr - 0.2, yr - 0.15, rz - min(7.0, 0.35 * rz), rz, "el_rotulo_cor")
    for i, (frac, z_l) in enumerate(((0.80, 0.30), (0.62, 0.0), (0.70, -0.32)), 1):
        k.caixa(f"el_bat_rotulo_linha{i}", -frac * rx, frac * rx - 0.25 * rx, yr - 0.2, yr - 0.15,
                z_l * rz - 1.1, z_l * rz + 1.1, "el_rotulo_texto")

    # XT90: a fêmea do pack (o `conector_xt90`, no sítio do de antes) + o macho do drone com os copos de solda
    cx, cz = -mx - 10.0, 0.25 * 2.0 * mz
    x_f1 = cx + 10.0
    k.caixa("conector_xt90", x_f1 - 20.0, x_f1, -10.5, 10.5, cz - 5.3, cz + 5.3, "el_xt90")
    k.caixa("el_xt90_macho", x_f1 - 39.0, x_f1 - 20.0, -10.0, 10.0, cz - 5.0, cz + 5.0, "el_xt90")
    k.cil_x("el_xt90_copo_pos", x_f1 - 44.0, x_f1 - 39.0, 5.25, cz, 2.6, "el_ouro")
    k.cil_x("el_xt90_copo_neg", x_f1 - 44.0, x_f1 - 39.0, -5.25, cz, 2.6, "el_ouro")

    # tapete anti-derrapante entre o pack e a placa; 2 cintas de 15 mm com fivela pelos rasgos da placa de baixo
    if z_placa is not None:
        z_pl_fundo, z_pl_topo = ((z - pb[2]) / MM for z in z_placa)
        folga = z_pl_fundo - mz
        if folga > 0.5:
            k.caixa("el_bat_tapete", -(mx - 6.0), mx - 6.0, -(my - 4.0), my - 4.0, mz, mz + folga - 0.3,
                    "el_borracha")
        t, w = 1.2, 7.5
        z_inf = -mz - (1.5 if com_bandeja else 0.0)
        y_r = max(45.0, my + t + 2.0)                 # rasgos da placa de baixo (módulo `estrutura`: ±40, ±45 mm)
        x_c = min(40.0, 0.3 * 2.0 * mx)
        for i, xc in enumerate((-x_c, x_c), 1):
            x0, x1 = xc - w, xc + w
            # a volta ao pack (por baixo e pelos lados, até à placa) — o nome antigo, para quem o procura
            k.caixa(f"cinta_bateria_{i}", x0, x1, -my - t, my + t, z_inf - t, z_pl_fundo - t, "el_cinta")
            for s, lado in ((1.0, "esq"), (-1.0, "dir")):
                ya, yb = sorted((s * my, s * (y_r + 0.75)))
                k.caixa(f"el_cinta{i}_{lado}_placa", x0, x1, ya, yb, z_pl_fundo - t, z_pl_fundo, "el_cinta")
                ya, yb = sorted((s * (y_r - 0.75), s * (y_r + 0.75)))
                k.caixa(f"el_cinta{i}_{lado}_rasgo", x0, x1, ya, yb, z_pl_fundo, z_pl_topo + t, "el_cinta")
            k.caixa(f"el_cinta{i}_cima", x0, x1, -y_r - 0.75, y_r + 0.75, z_pl_topo, z_pl_topo + t, "el_cinta")
            k.caixa(f"el_cinta{i}_fivela", xc - w - 1.5, xc + w + 1.5, -my - t - 2.2, -my - t, -7.0, 7.0,
                    "el_fivela")
    _esconder(ctx, "bateria")


# =================================================================================================== regulador 24 V
def _fonte_servos(ctx) -> None:
    """Conversor buck-boost 24 V / 5 A dos servos (PCB aberta; disposição estimada)."""
    c, h = _info(ctx, "fonte_servos")
    k = _Kit(ctx, "drone", (c[0], c[1], c[2] - h[2]))
    hx, hy = float(h[0]) / MM, float(h[1]) / MM
    k.caixa("el_fonte24_pcb", -hx, hx, -hy, hy, 0.0, 1.6, "el_pcb_azul")
    k.cil_z("el_fonte24_toroide", -5.5, 5.5, 1.6, 8.6, 7.5, "el_cobre")
    k.cil_z("el_fonte24_toroide_furo", -5.5, 5.5, 1.6, 8.7, 3.0, "el_cinza_escuro")
    for i, (xx, yy) in enumerate(((6.5, 9.5), (-2.0, -10.5)), 1):
        k.cil_z(f"el_fonte24_cap{i}", xx, yy, 1.6, 11.0, 4.0, "el_condensador")
        k.cil_z(f"el_fonte24_cap{i}_topo", xx, yy, 11.0, 11.2, 3.6, "el_aluminio")
    k.caixa("el_fonte24_dissipador", 2.5, 13.5, -14.5, -2.5, 1.6, 9.6, "el_aluminio")
    k.caixa("el_fonte24_trimmer", -13.5, -8.7, -15.0, -5.5, 1.6, 11.6, "el_trimmer_azul")
    k.caixa("el_fonte24_borne_entrada", -hx, -hx + 7.0, -5.1, 5.1, 1.6, 11.0, "el_terminal_verde")
    k.caixa("el_fonte24_borne_saida", hx - 7.0, hx, -5.1, 5.1, 1.6, 11.0, "el_terminal_verde")
    _esconder(ctx, "fonte_servos")


# =================================================================================================== montagem
def _fazer(nome: str, fn, *args) -> None:
    """Cada peça é independente: um erro numa não impede as outras nem o modelo de compilar (avisa)."""
    try:
        fn(*args)
    except Exception as e:  # noqa: BLE001 — detalhe visual nunca pode derrubar o simulador
        warnings.warn(f"detalhes/eletronica: {nome} não desenhado ({type(e).__name__}: {e})", stacklevel=2)


def adicionar(ctx) -> None:
    """Desenha a eletrónica do build `ctx.hw` (o que o build não tem não se desenha)."""
    _materiais(ctx)
    hw = ctx.hw
    placa = _info(ctx, "placa")
    z_placa_topo = None if placa is None else float(placa[0][2] + placa[1][2])
    z_placa = None if placa is None else (float(placa[0][2] - placa[1][2]), z_placa_topo)
    ids = {c.id for c in hw.consumidores}
    rpi = _info(ctx, "el_rpi5") if "rpi5" in ids else None
    fc = _info(ctx, "el_fc_h7") if "fc_h7" in ids else None
    pdb = _info(ctx, "el_cablagem") if "cablagem" in ids else None
    port = _info(ctx, "el_arduino_portenta_h7") if "arduino_portenta_h7" in ids else None
    sens = hw.sensores or {}
    com_imu = "imu" in sens

    def fundo(info):
        return float(info[0][2] - info[1][2])

    # ponte do FC sobre o Pi (se houver placas por cima dele e espaço acima do Active Cooler)
    z_ponte, centro_pilha = None, None
    if rpi is not None and (fc is not None or pdb is not None):
        alvo = fc if fc is not None else pdb
        z_alvo = fundo(alvo) - (1.0 if fc is not None else 2.0) * MM
        if z_alvo - 1.5 * MM >= fundo(rpi) + 16.4 * MM:
            z_ponte, centro_pilha = z_alvo - 1.5 * MM, alvo[0]
    if rpi is not None:
        _fazer("Raspberry Pi 5", _rpi5, ctx, rpi, z_placa_topo, z_ponte)
        if z_ponte is not None:
            _fazer("ponte do FC", _ponte_fc, ctx, rpi, centro_pilha, z_ponte)
    if port is not None:
        _fazer("Portenta H7", _portenta, ctx, port, z_placa_topo)
    if fc is not None:
        _fazer("FC H7", _fc_h7, ctx, fc, fundo(pdb) if pdb is not None else None, com_imu)
    if pdb is not None:
        if fc is not None:
            apoio, z_apoio = "pilha", None
        elif z_ponte is not None:
            apoio, z_apoio = "ponte", z_ponte + 1.5 * MM
        else:
            apoio, z_apoio = "placa", z_placa_topo
        _fazer("placa de energia", _pdb, ctx, pdb, apoio, z_apoio, "monitor" in sens)
        if fc is None and com_imu:
            c, h = pdb
            _fazer("IMU avulsa", _imu_avulsa, ctx, _Kit(ctx, "drone", (c[0], c[1], c[2] - h[2])), 5.0, 10.0, 1.6)

    # ESC (individuais ao longo dos braços ou 4-em-1 no centro)
    if hw.esc.dados.get("formato", "4em1") == "4em1":
        if ctx.geom_existente("esc") is not None:
            _fazer("ESC 4-em-1", _esc_4em1, ctx)
    else:
        for i in range(1, 5):
            if ctx.geom_existente(f"esc{i}") is not None:
                _fazer(f"ESC {i}", _esc_air40a, ctx, i)

    # câmara do nariz
    cam = _info(ctx, "camera") if hw.camera is not None else None
    if cam is not None:
        tipo = str(hw.camera.dados.get("tipo", ""))
        if tipo == "modulo_camera_csi":
            _fazer("câmara CSI", _camera_csi, ctx, cam, z_placa_topo)
        elif tipo == "modulo_camera_dvp":
            _fazer("câmara DVP", _camera_dvp, ctx, cam, z_placa_topo)

    # pack, sensores de baixo (na bandeja presa pelas cintas) e regulador dos servos
    bat = _info(ctx, "bateria")
    if bat is not None:
        x_cinta = min(40.0, 0.3 * 2.0 * float(bat[1][0]) / MM)
        meia_x_bandeja = x_cinta + 9.5
        com_bandeja = ("fluxo" in sens or "tof" in sens) and ctx.geom_existente("sensores_baixo") is not None
        _fazer("sensores de baixo", _sensores_baixo, ctx, fundo(bat), meia_x_bandeja, "fluxo" in sens, "tof" in sens)
        _fazer("bateria", _bateria, ctx, z_placa, com_bandeja, meia_x_bandeja)
    if ctx.geom_existente("fonte_servos") is not None:
        _fazer("regulador 24 V", _fonte_servos, ctx)
