"""lab/drone_rpi/detalhes/eletronica.py — a ELETRÓNICA e as BATERIAS do drone com aspeto de peça REAL (só visual: massa
0, sem contacto, grupo 3 — regras no `Contexto`; a física fica igual bit a bit, `python -m lab.drone_rpi.detalhes.ver`).

As caixas com massa do `modelo._montar` (`el_rpi5`, `el_fc_h7`, `el_cablagem`, `esc1..4`/`esc`, `bateria`, `camera`,
`sensores_baixo`, `fonte_servos`, `el_arduino_portenta_h7`) continuam lá, com a massa e a inércia de sempre — ficam
INVISÍVEIS (`ctx.esconder`) quando a peça desenhada aqui as representa por inteiro. Os nomes antigos `rpi5_*`,
`cinta_bateria_*` e `conector_xt90` passam para as peças novas que fazem o mesmo papel. Tudo o que não é âncora junta-se
numa malha por corpo × material (`bateria3d.Fundidor`, com as faixas de faces de cada peça no registo); as âncoras que
os outros módulos procuram pelo nome são primitivas com nome. Sem texturas (o MJCF continua exportável com `to_xml`).

O que se desenha (medidas do fabricante, em mm; «estimado» = sem número oficial, escolhido por coerência):
  · Raspberry Pi 5 — PCB 85 × 56 × 1,6 com os 4 furos Ø2,7 (padrão 58 × 49, a 3,5 mm das bordas) e as coroas
    douradas, os furos do Active Cooler, USB-C a x = 11,2 (recetáculo OCO: casca 8,94 × 3,26, cavidade 8,40 × 2,62 ×
    6,9 de fundo — cabe a ficha de um cabo real, casca 8,25 × 2,4 metida 6,65 mm; a âncora `rpi5_usbc` é a caixa
    INVISÍVEL do envelope, para os fios porem a ficha ao centro dela), micro-HDMI a 25,8 e 39,2, USB 2.0 (y = 47),
    USB 3.0 (y = 29,1, línguas azuis), RJ45 (y = 10,2) a sair ~3 mm da borda, 2 × MIPI 22 vias, GPIO 2 × 20 (passo
    2,54, dourado), PCIe FFC, botão, LED, RTC/UART (JST-SH), BCM2712, RP1, LPDDR4X, PMIC, ranhura microSD por baixo.
    FERRAGENS (`ctx.ferragens`): 4 pilares de latão M2,5 sextavados de 5 mm entre faces macho-fêmea de 6 mm (o macho
    atravessa a placa de baixo, porca M2,5 por baixo) e, por cima, 4 pilares M-F de 16 mm até à ponte do FC com 4
    parafusos ISO 7380 M2,5 × 6 (sem ponte: os parafusos apertam a PCB aos pilares de baixo).
  · Active Cooler oficial — 63,5 × 42,5 × 13,7 (acima da PCB), alumínio, ventoinha radial de 30 mm, 2 pinos de pressão
    brancos, cabo de 4 fios até ao conector FAN (contorno e aletas estimados: base em L livre dos MIPI e da Ethernet).
  · Ponte de carbono do FC (estimado) — 1,5 mm sobre os pilares de 16 mm (o padrão de 30,5 mm do FC não cai nos furos do
    Pi): 2 réguas nos furos do Pi e 2 travessas com os furos do FC.
  · PILHA M3 do FC e da placa de energia — 4 parafusos ISO 7380 M3 (aço preto) por baixo da ponte (as cabeças cabem
    nos 0,65 mm entre a ponte e o topo do Active Cooler), amortecedores de silicone no FC, espaçadores lisos de nylon
    (o parafuso atravessa: só a porca tem rosca) e porcas de nylon com anilha por cima da placa de energia. Sem Pi
    (Portenta): espaçadores de nylon desde a placa de baixo, parafusos por baixo dela.
  · FC H7 30×30 — PCB 36 × 36 × 1,6 preto, STM32H743 (LQFP-100), BMI088, barómetro sob espuma, USB-C, microSD, JST-GH
    (UART/sensores na borda +y, GPS/I2C à frente, ESC atrás), LEDs; frente para +x.
  · Placa de energia (`cablagem`: módulo de energia + BEC 5 V/5 A) — PCB 60 × 40 com os furos de 30,5, ilhas da
    bateria (atrás) e de cada ESC (cantos), shunt + INA226, BEC síncrono (bobina blindada, CI, condensadores de
    polímero) e as ILHAS DA SAÍDA 5 V `el_pm_5v_pos`/`el_pm_5v_neg` na borda −y (de onde sai o cabo 20 AWG da RPi 5) —
    disposição estimada, com os componentes longe das porcas da pilha.
  · 4× T-Motor AIR 40A — 55,6 × 25,2 × 11,3 em termorretrátil preto com rótulo, condensador, saídas de entrada e de
    fases, ao longo do braço sobre FITA DE ESPUMA de 1 mm e preso ao tubo por 2 ABRAÇADEIRAS de nylon 3,6 mm (laço justo
    ao ESC e ao tubo, cabeça de lado); nos braços articulados vivem no corpo `braco{k}`.
  · Camera Module 3 (Wide) — PCB 25 × 24, bloco do IMX708 + lente, FPC de 15 vias, 4 parafusos ISO 7380 M2 × 5 com
    porca atrás do suporte em L de PETG (estimado), que aperta à placa com 2 M3 + porcas baixas por baixo.
    Portenta Vision Shield no build Arduino.
  · Build Arduino: Portenta H7 (66,04 × 25,4) encaixado numa placa de suporte (estimada, 88 × 27) pelos conectores HD,
    em 4 espaçadores de nylon de 3 mm com M3; BMI088 numa placa à parte em fita de espuma (o Portenta não tem IMU).
  · Braços articulados: regulador buck-boost 24 V/5 A dos servos (PCB aberta, estimado) com 4 M3 de nylon e anilhas
    de 1 mm à placa de baixo.
  · BATERIAS, cintas, tapete, XT90 e sensores de baixo: `bateria3d.py` (docstring lá).

VERSÃO ACESSÍVEL (2.ª fase, 2026-10-20; os builds antigos ficam IGUAIS bit a bit — o código novo entra por
`hw.frame.id` `*_abs` e pelo tipo `motorredutor_dc` do servo do ombro):
  · frame `*_abs` → os SUPORTES IMPRESSOS em ABS (material `el_abs_cinza`; malhas FECHADAS: sólidos que só se tocam
    pelas faces, volume exato; `notas["impressas"]` com a orientação de impressão): ponte da pilha do FC (`ponte_fc`:
    3,4 mm — o que cabe entre o topo do Active Cooler e os amortecedores do FC —, rebaixos onde entram os pilares M2,5
    × 15 do Pi e CONTRAFUROS onde ficam as cabeças dos M3 da pilha, imprime-se de cabeça para baixo); suporte em L da
    câmara (`suporte_camera`: placa de 2,4 mm, pé de 3 mm, 2 nervuras a 45°); travessa dos sensores (`bateria3d`).
    A pilha M3 e os espaçadores de nylon ficam COMPRADOS (um espaçador de ABS com paredes de 2 mm teria Ø7,4 e tocaria
    nas fichas JST-GH do FC); os pilares de latão do Pi também (rosca M2,5).
  · mecanismo de motorredutores DC (`ombro_fuso_impresso_cotovelo_servo`) → sai o regulador de 24 V e entram
    (catálogo → `fonte_servos`): 4 × DRV8871 (Adafruit #3190, 24,4 × 20,4 × 9,7 mm, 2,2 g; ILIM 27 kΩ → 2,37 A; um
    dissipador colado de 7 × 7 mm no CI — no limite dissipa ~2,6 W) cada um no seu SUPORTE IMPRESSO (`suporte_driver`
    k) na placa de cima junto ao seu ombro (fora dos cantos, onde ficam os atuadores), colado com espuma de 2 mm (a
    placa não tem furos) e preso por 2 × M3 + porca autoblocante; o UBEC dos servos dos cotovelos (Hobbywing UBEC 10A
    V2, 2–6S, 45 × 20 × 16,2 mm, 34 g, saída a 6,0 V: o DS3218MG é dado até 6,8 V) no BERÇO impresso
    (`bandeja_fonte` #3) atrás da pilha, debaixo do carregador da carga útil — com 16,2 mm não cabe entre as placas
    (12,8 mm); e, com motorredutores de 12 V, 2 × buck XL4016 8 A (61 × 41 × 27 mm, ~50 g; um por PAR de ombros do
    mesmo lado: 2 × 2,37 A de pico) PENDURADOS por baixo da placa de baixo, um de cada lado do pack, nas BASES
    impressas (`bandeja_fonte` #1/#2) com 4 insertos de latão M3 × 5,7 (Ø4,6, furo Ø4,0) cravados a quente nas
    colunas. Disposição interior do XL4016 e aparência do UBEC ESTIMADAS (as fichas só dão as medidas exteriores).

ÂNCORAS para o módulo `fios` (nomes de geoms): `rpi5_usbc` (envelope do recetáculo, invisível), `rpi5_gpio_40p` +
`el_rpi5_gpio_pino01..20`, `el_rpi5_cam_disp0` (+ `_trava`; o CAM/DISP 1 é `el_rpi5_ffc_disp1`), `el_rpi5_fan_ficha`;
`el_fc_con_uart` / `el_fc_con_uart2` / `el_fc_con_sensores` (borda +y), `el_fc_con_gps`, `el_fc_con_i2c`,
`el_fc_con_esc`; `el_pdb_pcb`,
`el_pdb_bat_pos/neg`, `el_pdb_esc{k}_pos/neg`, `el_pm_con_i2c`, `el_pm_5v_pos/neg`; `el_esc{k}_saida_entrada` e
`el_esc{k}_saida_fases`; `el_cam_conector_fpc`; `conector_xt90` (fêmea do pack), `el_xt90_macho`,
`el_xt90_copo_pos/neg` (copos do macho, cilindros ao longo de x: o cabo do drone sai da ponta −x), `el_bat_balanco`
(ficha JST-XH do balanceador), `el_bat_terminal_pos/neg` (soldas dos cabos do pack, NOVAS); `el_fluxo_conector`,
`el_fluxo_pcb`, `el_tof_pcb`; `el_fonte24_borne_entrada/saida`. Versão acessível (também em `notas["ancoras"]` com o
ponto e a direção de saída do fio): `el_drv{k}_alimentacao` (borne VM/GND), `el_drv{k}_motor` (borne OUT1/OUT2) —
entradas dos fios na face de FORA (±y) —, `el_drv{k}_sinal` (barra de 6 pinos, ficha de cima); `el_ubec_entrada`
(+y) / `el_ubec_saida` (−y) nas pontas do UBEC; `el_buck12_{n}_borne_entrada/saida` (n = 1 do lado +y, 2 do lado −y;
ilhas IN/OUT viradas para baixo).

Fontes (web = dado, só citado):
  https://pip.raspberrypi.com/documents/RP-008347-DS-1-raspberry-pi-5-mechanical-drawing.pdf (cotas do Pi 5)
  https://www.raspberrypi.com/news/introducing-raspberry-pi-5 (Ethernet em baixo à direita, PoE)
  https://forums.raspberrypi.com/viewtopic.php?t=365947 (USB 3.0 azuis = as mais perto da Ethernet)
  https://www.raspberrypi.com/documentation/accessories/camera.html (CAM/DISP entre o micro-HDMI e a Ethernet)
  https://forums.raspberrypi.com/viewtopic.php?t=358253 (conector FAN entre o GPIO e as USB 2.0)
  https://blog.dddac.com/raspberry-pi-5-power-over-gpio (LED bicolor ao lado do botão de energia)
  https://pip.raspberrypi.com/documents/RP-008188-DS-active-cooler-product-brief.pdf (63,5 × 42,5 × 13,7, ventoinha 30)
  USB Type-C Cable and Connector Specification (USB-IF) — ficha 8,25 × 2,40, recetáculo 8,34 × 2,56 mín. (interface)
  https://www.iswfa.com/drone-propulsion-power/escs/t-motor-air-40a-6s-esc (AIR 40A: 55,6 × 25,2 × 11,3 mm, 26 g)
  https://www.corvon.tech/en/products/corvon-h743-flight-controller-30x30-fc-for-drones-with-dual-imu-compass-barometer-stm32h743-7-uart-10-pwm-supports-betaflight-inav-ardupilot-px4-usb-c-blackbox-logging-5v-9v-bec-outputs
    e https://docs.px4.io/main/en/flight_controller/zenfc_h743 (FC H743 36 × 36, furos 30,5, BMI088)
  https://www.raspberrypi.com/products/camera-module-3 (25 × 24 × 11,5 / 12,4 mm Wide, FPC 15 × 1 mm, furos M2)
  https://shop.pimoroni.com/products/pmw3901-optical-flow-sensor-breakout (PMW3901: 24 × 24 × 5 mm)
  https://www.pololu.com/product/3415 (VL53L1X: 13 × 18 × 2 mm)
  https://docs.arduino.cc/hardware/portenta-h7 (66,04 × 25,4 mm, conectores de alta densidade por baixo)
  Versão acessível: https://www.adafruit.com/product/3190 e
  https://shop.pimoroni.com/en-us/products/adafruit-drv8871-dc-motor-driver-breakout-board-3-6a-max (DRV8871: 24,4 ×
  20,4 × 9,7 mm, 2,2 g) · https://www.ti.com/lit/ds/symlink/drv8871.pdf (I = 64/R_ILIM) ·
  https://www.hobbywingdirect.com/products/ubec-10a e https://www.readymaderc.com/products/details/hobby-wing-ubec-10a-v2
  (UBEC 10A V2: 2–6S, 6,0/7,4/8,4 V, 45 × 20 × 16,2 mm, 34 g) ·
  https://www.rytronics.in/product/xl4016-8a-200w-dc-dc-step-down-buck-converter e
  https://www.handsontec.com/dataspecs/power%20supply/8A%20XL4016E1%20DC-DC.pdf (XL4016: 61 × 41 × 27 mm, 8 A) ·
  https://cnckitchenus.store/products/heat-set-insert-m3-x-5-7-100-pieces (inserto M3 × 5,7, Ø4,6, furo Ø4,0) —
  pesquisa `pesquisas/2026-10-20-materiais-acessiveis-precos.md`.
"""
from __future__ import annotations

import itertools
import math
import re
import warnings

import mujoco
import numpy as np

from . import bateria3d as b3
from .bateria3d import (
    MM,
    Fundidor,
    Quadro,
    arredondar,
    eixo_para,
    g_anel,
    g_caixa,
    g_caixa_arred,
    g_cil,
    g_fita,
    g_placa_furos,
    g_tubo,
    juntar,
    mover,
)
from .ferragens import _torno

_G = mujoco.mjtGeom

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
    "el_papel_peixe": ((0.55, 0.11, 0.09, 1.0), 0.15, 0.15, 0.0, 0.0),
    "el_rotulo_branco": ((0.88, 0.88, 0.86, 1.0), 0.25, 0.30, 0.0, 0.0),
    "el_rotulo_texto": ((0.10, 0.10, 0.12, 1.0), 0.10, 0.10, 0.0, 0.0),
    "el_xt90": ((0.93, 0.72, 0.10, 1.0), 0.35, 0.45, 0.0, 0.0),
    "el_fivela": ((0.10, 0.10, 0.11, 1.0), 0.60, 0.60, 0.03, 0.0),
    "el_borracha": ((0.10, 0.10, 0.11, 1.0), 0.05, 0.05, 0.0, 0.0),
    "el_petg": ((0.10, 0.10, 0.11, 1.0), 0.30, 0.35, 0.0, 0.0),
    "el_terminal_verde": ((0.10, 0.55, 0.25, 1.0), 0.30, 0.35, 0.0, 0.0),
    "el_trimmer_azul": ((0.15, 0.35, 0.85, 1.0), 0.35, 0.40, 0.0, 0.0),
    "el_espuma_fita": ((0.16, 0.16, 0.17, 1.0), 0.05, 0.05, 0.0, 0.0),   # fita de espuma dupla face (ESC, IMU)
    "el_abracadeira": ((0.06, 0.06, 0.065, 1.0), 0.35, 0.40, 0.0, 0.0),  # nylon 6.6 preto (UV)
    "el_invisivel": ((0.0, 0.0, 0.0, 0.0), 0.0, 0.0, 0.0, 0.0),
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


def _fer(ctx):
    return ctx.ferragens


# =================================================================================================== Raspberry Pi 5
_RPI5_FUROS = ((3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5))
_RPI5_COOLER = ((6.8, 11.5), (42.0, 44.0))           # furos dos pinos de pressão do Active Cooler (estimado)
_RPI5_ANTIGOS = ("rpi5_soc_bcm2712", "rpi5_dissipador", "rpi5_ventoinha", "rpi5_rp1", "rpi5_rj45", "rpi5_usb3_torre",
                 "rpi5_usb3_azul", "rpi5_usb2_torre", "rpi5_gpio_40p", "rpi5_usbc", "rpi5_micro_hdmi_1",
                 "rpi5_micro_hdmi_2")
COOLER_ALTURA = 13.7                                   # acima da PCB (product brief)


def _rpi5(ctx, fund: Fundidor, rpi, z_placa_topo: float | None, z_placa_fundo: float | None,
          z_ponte: float | None, esp_ponte: float = 1.5, comp_m25: float = 6.0, peca_ponte: str = "fc") -> None:
    """Raspberry Pi 5 + Active Cooler. Coordenadas da PLACA (mm, origem no canto de baixo-esquerdo do desenho
    mecânico: x de 0 (PCIe) a 85 (USB/RJ45), y de 0 (USB-C/HDMI) a 56 (GPIO), z a partir da face de baixo da PCB).
    `z_ponte` = topo dos pilares de cima (a face onde assenta a ponte do FC), `esp_ponte` = espessura da ponte nesse
    sítio (o parafuso M2,5 de `comp_m25` mm aperta-a ao pilar)."""
    _apagar(ctx, *_RPI5_ANTIGOS)
    c, h = rpi
    z0 = c[2] - h[2]
    k = Quadro(ctx, fund, "drone", (c[0] - 0.0425, c[1] - 0.028, z0))
    with ctx.peca("rpi5"):
        furos = [(fx, fy, 1.35) for fx, fy in _RPI5_FUROS] + [(fx, fy, 1.25) for fx, fy in _RPI5_COOLER]
        k.m("el_pcb_verde", g_placa_furos(0.0, 85.0, 0.0, 56.0, 0.0, 1.6, furos, n=16), "rpi5")
        for fx, fy in _RPI5_FUROS:                      # coroas douradas (cima e baixo)
            for za, zb in ((1.6, 1.63), (-0.03, 0.0)):
                k.m("el_ouro", mover(g_anel(1.35, 3.0, za, zb, 16), None, (fx, fy, 0.0)), "rpi5")
        # SoC, RP1, LPDDR4X, PMIC (o SoC e o RP1 mantêm os nomes antigos: debaixo das almofadas do dissipador)
        k.caixa("rpi5_soc_bcm2712", 16.0, 33.0, 20.0, 37.0, 1.6, 2.6, "el_tampa_soc")
        k.caixa("rpi5_rp1", 51.0, 61.0, 25.5, 35.5, 1.6, 2.5, "el_chip")
        k.m("el_chip", juntar(g_caixa(35.0, 47.0, 21.0, 36.0, 1.6, 2.5), g_caixa(12.0, 18.5, 8.0, 13.5, 1.6, 2.4)), "rpi5")
        k.m("el_aco", g_caixa(0.0, 14.5, 20.5, 34.5, -1.45, 0.0), "rpi5")      # ranhura microSD (por baixo)
        # Active Cooler (63,5 × 42,5 × 13,7 acima da PCB): base em L, aletas, trilhos, ventoinha radial de 30 mm
        z_top = 1.6 + COOLER_ALTURA
        k.caixa("rpi5_dissipador", 4.5, 44.0, 7.0, 49.5, 2.6, 5.0, "el_aluminio")
        alu = [g_caixa(44.0, 65.5, 19.0, 49.5, 2.6, 5.0)]
        for i in range(7):
            x_a = 45.4 + 3.25 * i
            alu.append(g_caixa(x_a, x_a + 1.0, 19.5, 47.0, 5.0, z_top))
        alu += [g_caixa(4.5, 44.0, 7.0, 9.0, 5.0, 12.5), g_caixa(4.5, 44.0, 47.5, 49.5, 5.0, 12.5)]
        k.m("el_aluminio", juntar(*alu), "rpi5")
        k.caixa("rpi5_ventoinha", 9.5, 39.5, 13.0, 43.0, 5.0, z_top - 0.4, "el_plastico_preto")
        k.m("el_cinza_escuro", mover(g_anel(6.6, 11.0, z_top - 0.4, z_top - 0.25, 24), None, (24.5, 28.0, 0.0)), "rpi5")
        pas = [mover(g_caixa(6.8, 10.8, -0.4, 0.4, z_top - 3.0, z_top - 0.45), _rz(math.tau * j / 9), (24.5, 28.0, 0.0))
               for j in range(9)]
        k.m("el_plastico_preto", juntar(*pas), "rpi5")
        k.m("el_plastico_brilho", mover(g_cil(6.5, z_top - 0.45, z_top - 0.05, 24), None, (24.5, 28.0, 0.0)), "rpi5")
        pinos = []
        for fx, fy in _RPI5_COOLER:                      # pinos de pressão (nylon branco): cabeça + haste com mola
            pinos += [mover(g_cil(2.1, 5.0, 6.6, 12), None, (fx, fy, 0.0)), mover(g_cil(1.2, -1.2, 5.0, 10), None,
                                                                                (fx, fy, 0.0)),
                      mover(g_cil(1.6, -2.0, -1.2, 10), None, (fx, fy, 0.0))]
        k.m("el_nylon", juntar(*pinos), "rpi5")
        # cabo da ventoinha (4 fios) até ao conector FAN (JST-SH 4 vias, entre o fim do GPIO e as USB 2.0)
        cabo = arredondar([(38.5, 42.0, z_top - 1.0), (41.5, 48.6, z_top - 1.6), (64.5, 48.6, z_top - 1.6),
                           (67.4, 50.5, 6.2)], 2.0, 4)
        k.m("el_plastico_preto", g_tubo(cabo, 0.7, 6), "rpi5")
        k.m("el_jst", g_caixa(64.4, 70.4, 48.5, 52.7, 1.6, 4.5), "rpi5")
        k.caixa("el_rpi5_fan_ficha", 64.9, 69.9, 48.9, 52.3, 4.5, 6.4, "el_jst")
        # GPIO 2 × 20 (passo 2,54): base preta + 20 colunas de pinos dourados (6 mm acima da base)
        k.caixa("rpi5_gpio_40p", 7.1, 57.9, 49.96, 55.04, 1.6, 4.1, "el_plastico_preto")
        for i in range(20):
            xc = 8.37 + 2.54 * i
            k.caixa(f"el_rpi5_gpio_pino{i + 1:02d}", xc - 0.32, xc + 0.32, 50.91, 54.09, 4.1, 10.1, "el_ouro")
        # borda direita: USB 2.0 (y = 47), USB 3.0 (y = 29,1, línguas azuis), RJ45 (y = 10,2) a sair ~3 mm da PCB
        aberturas, linguas_pretas, leds_v, leds_a = [], [], [], []
        for nome, yc, lingua in (("rpi5_usb2_torre", 47.0, None), ("rpi5_usb3_torre", 29.1, "el_usb_azul")):
            y0, y1 = yc - 6.6, yc + 6.6
            k.caixa(nome, 70.5, 88.0, y0, y1, 1.6, 17.2, "el_aco")
            for j, (zb, zt) in enumerate(((3.0, 8.0), (10.4, 15.4)), 1):
                aberturas.append(g_caixa(88.0, 88.15, y0 + 0.6, y1 - 0.6, zb, zt))
                if lingua is not None and j == 1:
                    k.caixa("rpi5_usb3_azul", 88.0, 88.3, y0 + 1.2, y1 - 1.2, zt - 2.6, zt - 0.9, lingua)
                elif lingua is not None:
                    k.m(lingua, g_caixa(88.0, 88.3, y0 + 1.2, y1 - 1.2, zt - 2.6, zt - 0.9), "rpi5")
                else:
                    linguas_pretas.append(g_caixa(88.0, 88.3, y0 + 1.2, y1 - 1.2, zt - 2.6, zt - 0.9))
        k.caixa("rpi5_rj45", 66.6, 88.0, 2.2, 18.2, 1.6, 14.9, "el_aco")
        aberturas.append(g_caixa(88.0, 88.15, 4.3, 16.1, 2.6, 11.0))
        leds_v.append(g_caixa(88.0, 88.25, 3.0, 5.4, 12.0, 13.8))
        leds_a.append(g_caixa(88.0, 88.25, 15.0, 17.4, 12.0, 13.8))
        # borda de baixo: USB-C OCO a x = 11,2 (casca 8,94 × 3,26; cavidade 8,40 × 2,62 × 6,9), 2 micro-HDMI, RTC, UART
        k.caixa("rpi5_usbc", 6.73, 15.67, -1.2, 6.3, 1.6, 4.86, "el_invisivel", rgba=(0.0, 0.0, 0.0, 0.0))
        xa, xb, za, zb = 6.73, 15.67, 1.6, 4.86
        cav_x0, cav_x1, cav_z0, cav_z1, cav_y1 = 7.0, 15.4, 1.92, 4.54, 5.7
        casca = [g_caixa(xa, xb, -1.2, 6.3, za, cav_z0), g_caixa(xa, xb, -1.2, 6.3, cav_z1, zb),
                 g_caixa(xa, cav_x0, -1.2, 6.3, cav_z0, cav_z1), g_caixa(cav_x1, xb, -1.2, 6.3, cav_z0, cav_z1),
                 g_caixa(cav_x0, cav_x1, cav_y1, 6.3, cav_z0, cav_z1),
                 g_caixa(xa - 0.6, xa, 3.6, 5.6, 0.0, 2.6), g_caixa(xb, xb + 0.6, 3.6, 5.6, 0.0, 2.6)]   # patas THT
        k.m("el_aco", juntar(*casca), "rpi5")
        k.m("el_ouro", g_caixa(cav_x0 + 0.9, cav_x1 - 0.9, cav_y1 - 0.08, cav_y1, cav_z0 + 0.9, cav_z1 - 0.9), "rpi5")
        for i, xc in enumerate((25.8, 39.2), 1):
            k.caixa(f"rpi5_micro_hdmi_{i}", xc - 3.75, xc + 3.75, -1.0, 5.8, 1.6, 5.0, "el_aco")
            aberturas.append(g_caixa(xc - 3.0, xc + 3.0, -1.15, -1.0, 2.3, 4.3))
        k.m("el_jst", juntar(g_caixa(17.5, 21.5, 0.8, 5.05, 1.6, 4.5), g_caixa(30.0, 35.0, 0.8, 5.05, 1.6, 4.5)), "rpi5")
        for nome, x_m in (("el_rpi5_cam_disp0", 46.0), ("el_rpi5_ffc_disp1", 53.5)):
            k.caixa(nome, x_m, x_m + 4.5, 2.0, 16.6, 1.6, 3.6, "el_plastico_preto")
            k.caixa(f"{nome}_trava", x_m + 4.5, x_m + 5.5, 2.3, 16.3, 1.6, 3.9, "el_trava_fpc")
        # borda esquerda: FFC PCIe (16 vias), botão de energia e LED bicolor
        linguas_pretas += [g_caixa(0.4, 4.4, 22.0, 34.0, 1.6, 3.4), g_caixa(-0.5, 3.8, 8.0, 11.6, 1.6, 3.4)]
        leds_v.append(g_caixa(0.2, 1.4, 13.0, 14.6, 1.6, 2.2))
        k.m("el_trava_fpc", g_caixa(4.4, 5.3, 22.3, 33.7, 1.6, 3.6), "rpi5")
        k.m("el_abertura", juntar(*aberturas), "rpi5")
        k.m("el_plastico_preto", juntar(*linguas_pretas), "rpi5")
        k.m("el_led_verde", juntar(*leds_v), "rpi5")
        k.m("el_led_ambar", juntar(*leds_a), "rpi5")
    _esconder(ctx, "el_rpi5")
    # ---- ferragens: pilares de latão M2,5 (macho para baixo pela placa + porca), pilares de cima / parafusos
    fer = _fer(ctx)
    if fer is None:
        return
    for fx, fy in _RPI5_FUROS:
        p_pcb = k.ponto(fx, fy, 0.0)
        if z_placa_topo is not None and z_placa_fundo is not None:
            comp = round((z0 - z_placa_topo) / MM, 3)
            fer.pilar("drone", p_pcb.tolist(), (0.0, 0.0, -1.0), "M2.5", comp, tipo="sextavado", af=5.0, macho=6.0,
                      material_="latao", peca="rpi5", ref=(1.0, 0.0, 0.0))
            fer.porca("drone", [float(p_pcb[0]), float(p_pcb[1]), float(z_placa_fundo)], (0.0, 0.0, -1.0), "M2.5",
                      norma="ISO 4032", material_="latao", peca="rpi5")
        if z_ponte is not None:
            p_ponte = [float(p_pcb[0]), float(p_pcb[1]), float(z_ponte)]
            fer.pilar("drone", p_ponte, (0.0, 0.0, -1.0), "M2.5", round((z_ponte - (z0 + 1.6 * MM)) / MM, 3),
                      tipo="sextavado", af=5.0, macho=6.0, material_="latao", peca="rpi5", ref=(1.0, 0.0, 0.0))
            fer.parafuso("drone", [p_ponte[0], p_ponte[1], float(z_ponte + esp_ponte * MM)], (0.0, 0.0, -1.0), "M2.5",
                         comp=comp_m25, cabeca="ISO 7380", porca=None, material_="aco_preto", peca=peca_ponte)
        else:
            fer.parafuso("drone", k.ponto(fx, fy, 1.6).tolist(), (0.0, 0.0, -1.0), "M2.5", comp=6.0,
                         cabeca="ISO 7380", porca=None, material_="aco_preto", peca="rpi5")


def _furos_pilha(ctx, centro, base) -> list:
    """Os 4 furos do padrão de 30,5 mm da pilha (FC/placa de energia) no referencial local de `base`."""
    out = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        p = np.array([centro[0] + sx * 0.01525, centro[1] + sy * 0.01525, 0.0])
        out.append(((p[0] - base[0]) / MM, (p[1] - base[1]) / MM))
    return out


def _ponte_fc(ctx, fund: Fundidor, rpi, centro_pilha, z_fundo: float) -> None:
    """Ponte de carbono (1,5 mm) nos 4 pilares do Pi: 2 réguas sobre os furos do Pi (x = 3,5 e 61,5) e 2 travessas nas
    linhas dos furos de 30,5 mm do FC/placa de energia, com os furos M2,5 e M3."""
    c, _h = rpi
    base = (c[0] - 0.0425, c[1] - 0.028)
    k = Quadro(ctx, fund, "drone", (base[0], base[1], z_fundo))
    fp = _furos_pilha(ctx, centro_pilha, base)
    xs_fc = sorted({round(x, 4) for x, _y in fp})
    ys_fc = sorted({round(y, 4) for _x, y in fp})
    x_fr0 = min(57.5, xs_fc[-1] - 3.4)
    with ctx.peca("fc"):
        pecas = [g_placa_furos(-0.5, 7.5, -0.5, 56.5, 0.0, 1.5, [(3.5, 3.5, 1.35), (3.5, 52.5, 1.35)], n=12),
                 g_placa_furos(x_fr0, 65.5, -0.5, 56.5, 0.0, 1.5,
                               [(61.5, 3.5, 1.35), (61.5, 52.5, 1.35)] + [(x, y, 1.65) for x, y in fp if x > x_fr0 + 2],
                               n=12)]
        for yc in ys_fc:
            pecas.append(g_placa_furos(7.5, x_fr0, yc - 4.0, yc + 4.0, 0.0, 1.5,
                                       [(x, y, 1.65) for x, y in fp if abs(y - yc) < 1e-3 and 7.5 < x < x_fr0], n=12))
        k.m("el_carbono", juntar(*pecas), "fc")


def _pilha_m3(ctx, fund: Fundidor, centro, z_base_apoio: float, z_cabeca: float, z_fc: float | None,
              z_pdb: float | None, apoio: str) -> None:
    """Pilha M3: parafusos ISO 7380 por baixo do apoio (ponte ou placa), amortecedores de silicone no FC, espaçadores
    lisos de nylon e porcas de nylon com anilha no topo (placa de energia, ou o FC sem ela)."""
    fer = _fer(ctx)
    if fer is None:
        return
    k = Quadro(ctx, fund, "drone", (centro[0], centro[1], 0.0))
    furos = [(sx * 15.25, sy * 15.25) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    topo = (z_pdb + 1.6 * MM) if z_pdb is not None else (z_fc + 1.6 * MM + 0.9 * MM)
    aperto = (topo - z_cabeca) / MM
    for fx, fy in furos:
        p = k.ponto(fx, fy, 0.0)
        fer.parafuso("drone", [float(p[0]), float(p[1]), float(z_cabeca)], (0.0, 0.0, 1.0), "M3", aperto=aperto,
                     cabeca="ISO 7380", porca="ISO 4032", material_="aco_preto", material_porca="nylon_branco",
                     anilha_porca=True, peca="pdb" if z_pdb is not None else "fc",
                     nota=f"pilha M3 do FC/placa de energia: aperta {apoio}")
        if z_fc is not None:
            # amortecedor de silicone (carretel: abas Ø7,2 × 0,9, alma Ø4,6 no furo do FC, furo Ø3,2)
            zf = (z_fc / MM)
            perfil = [[(1.65, zf - 0.9), (3.6, zf - 0.9)], [(3.6, zf - 0.9), (3.6, zf)], [(3.6, zf), (2.3, zf)],
                      [(2.3, zf), (2.3, zf + 1.6)], [(2.3, zf + 1.6), (3.6, zf + 1.6)],
                      [(3.6, zf + 1.6), (3.6, zf + 2.5)], [(3.6, zf + 2.5), (1.65, zf + 2.5)],
                      [(1.65, zf + 2.5), (1.65, zf - 0.9)]]
            k.m("el_silicone", mover(_torno(perfil, n=20), None, (fx, fy, 0.0)), "fc")
            fer.registar(tipo="amortecedor", norma="amortecedor de silicone M3 (FC)", rosca="M3",
                         material="fer_nylon_preto", corpo="drone", ponto=[float(p[0]), float(p[1]), float(z_fc)],
                         eixo=(0.0, 0.0, 1.0), peca="fc", descricao="Amortecedor de silicone M3 do FC (30,5 mm)")
        if z_pdb is not None:                           # espaçador liso de nylon até à placa de energia
            z_ini = (z_fc / MM + 2.5) if z_fc is not None else (z_base_apoio / MM)
            comp = z_pdb / MM - z_ini
            if comp > 0.3:
                fer.pilar("drone", [float(p[0]), float(p[1]), z_ini * MM], (0.0, 0.0, 1.0), "M3", round(comp, 3),
                          tipo="redondo", af=6.0, material_="nylon_branco", peca="pdb",
                          ref=(1.0, 0.0, 0.0))


def _fc_h7(ctx, fund: Fundidor, fc, com_imu: bool, pwm: bool = False) -> None:
    """FC H743 30×30 (referencial: centro da caixa em xy, z a partir da face de baixo da PCB; frente para +x). Com
    `pwm` (servos PWM nos cotovelos) leva também a ficha JST-SH de 6 vias das saídas PWM na borda −y
    (`el_fc_con_pwm`, entrada lateral: a placa de energia está 4 mm por cima)."""
    c, h = fc
    z0 = c[2] - h[2]
    k = Quadro(ctx, fund, "drone", (c[0], c[1], z0))
    furos = [(sx * 15.25, sy * 15.25, 2.3) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    with ctx.peca("fc"):
        k.m("el_pcb_preto", g_placa_furos(-18.0, 18.0, -18.0, 18.0, 0.0, 1.6, furos, n=16), "fc")
        k.m("el_chip", g_caixa(-7.0, 7.0, -7.0, 7.0, 1.6, 3.0), "fc")
        k.m("el_estanho", g_caixa(-8.0, 8.0, -8.0, 8.0, 1.6, 1.85), "fc")
        if com_imu:
            k.m("el_chip", g_caixa(-12.0, -9.0, 3.0, 7.5, 1.6, 2.55), "fc")
        k.m("el_espuma", g_caixa(6.0, 12.0, -14.5, -8.5, 1.6, 4.1), "fc")
        k.m("el_aco", juntar(g_caixa(-12.47, -3.53, -18.6, -11.25, 1.6, 4.8), g_caixa(-4.0, 8.0, -9.0, 3.0, -1.85, 0.0)),
            "fc")
        k.m("el_abertura", g_caixa(-11.7, -4.3, -18.75, -18.6, 2.3, 4.1), "fc")
        k.caixa("el_fc_con_esc", -17.8, -13.55, -4.5, 4.5, 1.6, 4.5, "el_jst")
        k.caixa("el_fc_con_gps", 13.4, 17.6, -9.4, -0.6, 1.6, 5.85, "el_jst")
        k.caixa("el_fc_con_i2c", 13.4, 17.6, 2.4, 8.6, 1.6, 5.85, "el_jst")
        k.caixa("el_fc_con_uart", -11.5, -5.5, 13.75, 18.0, 1.6, 5.85, "el_jst")
        k.caixa("el_fc_con_sensores", 4.4, 11.6, 13.75, 18.0, 1.6, 5.85, "el_jst")
        # 2.ª UART livre (JST-SH 4 vias de entrada lateral: TX/RX/5V/GND) na borda +y, entre a UART e os sensores
        k.caixa("el_fc_con_uart2", -3.55, 2.45, 13.75, 18.0, 1.6, 4.55, "el_jst")
        ctx.registo.notas.setdefault("ancoras", {})["el_fc_con_uart2"] = {
            "corpo": "drone", "ponto": [float(x) for x in k.ponto(-0.55, 18.0, 3.075)], "direcao": [0.0, 1.0, 0.0],
            "vias": 4, "nota": "JST-SH 4 vias, entrada lateral (+y): TX, RX, 5 V, GND"}
        if pwm:
            k.caixa("el_fc_con_pwm", -3.35, 5.65, -18.0, -13.75, 1.6, 4.55, "el_jst")
            ctx.registo.notas.setdefault("ancoras", {})["el_fc_con_pwm"] = {
                "corpo": "drone", "ponto": [float(x) for x in k.ponto(1.15, -18.0, 3.0)],
                "direcao": [0.0, -1.0, 0.0], "nota": "JST-SH 6 vias, entrada lateral (−y): S1–S4, 5 V, GND"}
        k.m("el_led_verde", g_caixa(-10.8, -9.2, -12.4, -11.6, 1.6, 2.2), "fc")
        k.m("el_led_azul", g_caixa(-7.8, -6.2, -12.4, -11.6, 1.6, 2.2), "fc")
    _esconder(ctx, "el_fc_h7")


# =================================================================================================== placa de energia
def _sinais_rotores(ctx) -> list:
    try:
        return [(1.0 if x >= 0 else -1.0, 1.0 if y >= 0 else -1.0) for x, y in ctx.hw.pos_rotores]
    except Exception:  # noqa: BLE001
        return [(1.0, 1.0), (-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0)]


def _pdb(ctx, fund: Fundidor, pdb, com_ina: bool) -> None:
    """Módulo de energia + BEC 5 V/5 A (60 × 40, furos de 30,5): ilhas da bateria e de cada ESC, shunt + INA226,
    BEC e as ilhas da saída 5 V (`el_pm_5v_pos/neg`) — componentes fora do alcance das porcas da pilha (r 4,5 mm)."""
    c, h = pdb
    z0 = c[2] - h[2]
    k = Quadro(ctx, fund, "drone", (c[0], c[1], z0))
    furos = [(sx * 15.25, sy * 15.25, 1.65) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    with ctx.peca("pdb"):
        k.caixa("el_pdb_pcb", -30.0, 30.0, -20.0, 20.0, 0.0, 1.6, "el_invisivel", rgba=(0.0, 0.0, 0.0, 0.0))
        k.m("el_pcb_vermelho", g_placa_furos(-30.0, 30.0, -20.0, 20.0, 0.0, 1.6, furos, n=16), "pdb")
        for fx, fy, _r in furos:
            k.m("el_estanho", mover(g_anel(1.65, 3.2, 1.6, 1.63, 16), None, (fx, fy, 0.0)), "pdb")
        k.caixa("el_pdb_bat_pos", -29.5, -23.5, 2.0, 10.0, 1.6, 2.0, "el_estanho")
        k.caixa("el_pdb_bat_neg", -29.5, -23.5, -10.0, -2.0, 1.6, 2.0, "el_estanho")
        for i, (sx, sy) in enumerate(_sinais_rotores(ctx), 1):
            k.caixa(f"el_pdb_esc{i}_pos", sx * 27.5 - 2.0, sx * 27.5 + 2.0, sy * 14.5 - 3.0, sy * 14.5 + 3.0, 1.6,
                    1.95, "el_estanho")
            k.caixa(f"el_pdb_esc{i}_neg", sx * 22.75 - 1.75, sx * 22.75 + 1.75, sy * 14.5 - 3.0, sy * 14.5 + 3.0, 1.6,
                    1.95, "el_estanho")
        if com_ina:
            k.m("el_estanho", g_caixa(-19.0, -12.6, -1.6, 1.6, 1.6, 2.5), "pdb")             # shunt 2512
            k.m("el_chip", g_caixa(-11.0, -8.0, -6.5, -3.5, 1.6, 2.7), "pdb")                # INA226 (MSOP-10)
        k.m("el_ferrite", g_caixa_arred(1.0, 8.0, -10.0, -3.0, 1.6, 6.1, 0.6, 2), "pdb")     # bobina blindada
        k.m("el_chip", g_caixa(-7.0, -2.1, -8.5, -4.6, 1.6, 3.1), "pdb")                     # CI do BEC (SOIC-8)
        k.m("el_cap_polimero", juntar(mover(g_cil(3.15, 1.6, 7.0, 20), None, (-4.5, 4.0, 0.0)),
                                      mover(g_cil(3.15, 1.6, 7.0, 20), None, (4.5, 4.0, 0.0))), "pdb")
        k.caixa("el_pm_con_i2c", 25.4, 29.6, -5.0, 5.0, 1.6, 5.85, "el_jst")
        # saída 5 V do BEC: 2 ilhas para o cabo 20 AWG da RPi 5 (+ condensador de saída ao lado)
        k.caixa("el_pm_5v_pos", -7.0, -3.0, -19.6, -16.4, 1.6, 2.0, "el_estanho")
        k.caixa("el_pm_5v_neg", -1.0, 3.0, -19.6, -16.4, 1.6, 2.0, "el_estanho")
        k.m("el_cap_polimero", mover(g_cil(2.5, 1.6, 6.5, 16), None, (7.0, -15.0, 0.0)), "pdb")
        k.m("el_rotulo_branco", juntar(g_caixa(-7.5, -2.5, -15.6, -15.2, 1.6, 1.63), g_caixa(-5.3, -4.7, -16.2, -14.6, 1.6, 1.63),
                                       g_caixa(-1.5, 3.5, -15.6, -15.2, 1.6, 1.63)), "pdb")   # serigrafia «+ −»
    _esconder(ctx, "el_cablagem")


def _imu_avulsa(ctx, fund: Fundidor, base, x: float, y: float, z: float) -> None:
    """BMI088 numa placa de 18 × 14 (roxa) com barra de 6 pinos, colada com fita de espuma dupla face (amortece)."""
    k = Quadro(ctx, fund, "drone", base)
    with ctx.peca("imu"):
        k.m("el_espuma_fita", g_caixa(x - 8.0, x + 8.0, y - 6.0, y + 6.0, z, z + 1.0), "imu")
        z += 1.0
        k.m("el_pcb_roxo", g_caixa(x - 9.0, x + 9.0, y - 7.0, y + 7.0, z, z + 1.6), "imu")
        k.m("el_chip", g_caixa(x - 1.5, x + 1.5, y - 2.25, y + 2.25, z + 1.6, z + 2.55), "imu")
        k.m("el_plastico_preto", g_caixa(x + 5.5, x + 8.0, y - 6.5, y + 6.5, z + 1.6, z + 4.1), "imu")
        k.m("el_ouro", g_caixa(x + 6.4, x + 7.1, y - 6.0, y + 6.0, z + 4.1, z + 7.0), "imu")


# =================================================================================================== Portenta H7
def _portenta(ctx, fund: Fundidor, port, z_placa_topo: float | None, z_placa_fundo: float | None) -> None:
    """Arduino Portenta H7 (66,04 × 25,4) encaixado pelos conectores HD numa placa de suporte (estimada) em 4
    espaçadores de nylon de 3 mm com M3 à placa de baixo."""
    c, h = port
    z_pcb = c[2] - h[2] + 1.5 * MM
    k = Quadro(ctx, fund, "drone", (c[0], c[1], z_pcb))
    hx, hy = 33.02, 12.7
    with ctx.peca("portenta"):
        k.m("el_pcb_preto", g_caixa(-hx, hx, -hy, hy, 0.0, 1.0), "portenta")
        k.m("el_plastico_preto", juntar(*[g_caixa(-12.0, 12.0, yy - 1.8, yy + 1.8, -1.5, 0.0) for yy in (6.0, -6.0)]),
            "portenta")
        k.m("el_chip", juntar(g_caixa(-8.0, 6.0, -7.0, 7.0, 1.0, 2.2), g_caixa(9.0, 17.0, -6.0, 6.0, 1.0, 2.0)), "portenta")
        k.m("el_aco", juntar(g_caixa(19.5, 29.5, -1.0, 7.5, 1.0, 2.4), g_caixa(-36.4, -27.5, -4.47, 4.47, 1.0, 4.2)),
            "portenta")
        k.m("el_abertura", g_caixa(-36.55, -36.4, -3.7, 3.7, 1.7, 3.5), "portenta")
        k.m("el_jst", juntar(g_caixa(27.0, 31.0, -11.5, -5.5, 1.0, 4.0), g_caixa(-24.0, -18.0, -11.8, -8.0, 1.0, 4.0)),
            "portenta")
        k.m("el_ouro", juntar(*[g_caixa(-30.0, 30.0, yy - 0.4, yy + 0.4, 0.0, 1.05) for yy in (hy - 0.3, -hy + 0.3)]),
            "portenta")
        if z_placa_topo is not None:
            # placa de suporte (88 × 27, estreita: os espaçadores da pilha de 30,5 mm passam ao lado) com os recetáculos
            # HD (1,4 mm) por baixo das fichas do Portenta
            z_s1 = -1.5 - 1.4
            z_s0 = z_s1 - 1.6
            furos = [(sx * 40.0, sy * 9.0, 1.65) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
            k.m("el_pcb_verde", g_placa_furos(-44.0, 44.0, -13.5, 13.5, z_s0, z_s1, furos, n=12), "portenta")
            k.m("el_plastico_preto", juntar(*[g_caixa(-12.5, 12.5, yy - 2.1, yy + 2.1, z_s1, -1.5)
                                              for yy in (6.0, -6.0)]), "portenta")
            ancoras = ctx.registo.notas.setdefault("ancoras", {})
            k.caixa("el_portenta_5v", -3.8, 0.45, -13.5, -9.25, z_s1, z_s1 + 3.2, "el_jst", peca="portenta")
            ancoras["el_portenta_5v"] = {"corpo": "drone", "ponto": k.ponto(-1.675, -13.5, z_s1 + 1.6).tolist(),
                                         "direcao": [0.0, -1.0, 0.0]}
            ctx.registo.notas["entrada_computador"] = "el_portenta_5v"
            for i_pwm, (sx, sy) in enumerate(((1, 1), (-1, -1), (-1, 1), (1, -1)), 1):
                nm_pwm = f"el_portenta_pwm{i_pwm}"
                y0_p, y1_p = (-13.5, -9.25) if sy < 0 else (9.25, 13.5)
                k.caixa(nm_pwm, sx * 35.0 - 2.125, sx * 35.0 + 2.125, y0_p, y1_p, z_s1, z_s1 + 3.2, "el_jst",
                        peca="portenta")
                ancoras[nm_pwm] = {"corpo": "drone", "ponto": k.ponto(sx * 35.0, sy * 13.5, z_s1 + 1.6).tolist(),
                                   "direcao": [0.0, float(sy), 0.0]}
            fer = _fer(ctx)
            if fer is not None and z_placa_fundo is not None:
                z_sup = z_pcb + z_s0 * MM
                for fx, fy, _r in furos:
                    p = k.ponto(fx, fy, 0.0)
                    esp = (z_sup - z_placa_topo) / MM
                    if esp > 0.3:
                        fer.pilar("drone", [float(p[0]), float(p[1]), float(z_placa_topo)], (0.0, 0.0, 1.0), "M3",
                                  round(esp, 3), tipo="redondo", af=6.0, material_="nylon_branco", peca="portenta")
                    fer.parafuso("drone", [float(p[0]), float(p[1]), float(z_placa_fundo)], (0.0, 0.0, 1.0), "M3",
                                 aperto=(z_sup + 1.6 * MM - z_placa_fundo) / MM, cabeca="ISO 7380", porca="ISO 4032",
                                 material_="aco_preto", material_porca="nylon_branco", peca="portenta",
                                 nota="placa de suporte do Portenta: atravessa placa_inferior")
    _esconder(ctx, "el_arduino_portenta_h7")


# =================================================================================================== ESC
def _raio_tubo_mm(ctx, omissao: float) -> float:
    """Raio exterior do tubo dos braços (catálogo: «tubo(s) de carbono 25×23 mm» → 12,5; «… 16 mm» → 8)."""
    texto = f"{getattr(ctx.hw.frame, 'modelo', '')} {ctx.hw.frame.dados.get('modelo', '')}"
    m = re.search(r"tubos? de carbono (\d+(?:[.,]\d+)?)", texto)
    return 0.5 * float(m.group(1).replace(",", ".")) if m else omissao


def _assento_esc(ctx, k_braco: int, p_drone: np.ndarray, meia_z: float):
    """(corpo, posição no corpo, rotação do corpo, z da base do ESC no corpo, raio do tubo mm): no rígido a base da
    caixa `esc{k}` (o topo do tubo da `estrutura`); no articulado o topo do tubo redondo do braço, no corpo `braco{k}`."""
    tubo = ctx.geom_existente(f"braco{k_braco}_tubo")
    if tubo is not None and ctx.existe_corpo(f"braco{k_braco}"):
        b = ctx.corpo(f"braco{k_braco}")
        r_b = _mat_de_quat(b.quat)
        p_loc = r_b.T @ (p_drone - np.array(b.pos, dtype=float))
        r_tubo = _raio_tubo_mm(ctx, float(tubo.size[2]) / MM)
        return f"braco{k_braco}", p_loc, r_b, float(tubo.pos[2]) + r_tubo * MM, r_tubo
    return "drone", p_drone, np.eye(3), float(p_drone[2]) - meia_z, _raio_tubo_mm(ctx, 8.0)


def _contacto_abracadeira(meia_l: float, h_topo: float, r_tubo: float, n: int = 24) -> list:
    """Pontos (u, w) onde a face de dentro da abraçadeira TOCA: o topo do ESC e o arco de baixo do tubo."""
    pts = [(u, h_topo) for u in np.linspace(-meia_l + 1.8, meia_l - 1.8, 7)]
    for i in range(n + 1):
        a = math.pi + math.pi * i / n                    # metade de baixo do tubo
        if abs(math.cos(a)) * r_tubo <= meia_l:
            pts.append((r_tubo * math.cos(a), -r_tubo + r_tubo * math.sin(a)))
    return pts


def _laco_abracadeira(meia_l: float, h_topo: float, r_tubo: float, esp: float) -> np.ndarray:
    """Laço (u, w) de uma abraçadeira justa à secção do ESC ([−meia_l, meia_l] × [0, h_topo]) e do tubo (centro
    (0, −r_tubo)): o invólucro convexo dos dois, afastado de meia espessura."""
    pts = [(-meia_l, h_topo), (meia_l, h_topo), (meia_l, 0.0), (-meia_l, 0.0)]
    for i in range(36):
        a = math.tau * i / 36
        pts.append((r_tubo * math.cos(a), -r_tubo + r_tubo * math.sin(a)))
    p = sorted({(round(x, 6), round(y, 6)) for x, y in pts})

    def cruz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    baixo, cima = [], []
    for q in p:
        while len(baixo) >= 2 and cruz(baixo[-2], baixo[-1], q) <= 0:
            baixo.pop()
        baixo.append(q)
    for q in reversed(p):
        while len(cima) >= 2 and cruz(cima[-2], cima[-1], q) <= 0:
            cima.pop()
        cima.append(q)
    casco = np.array(baixo[:-1] + cima[:-1])
    # afastar cada vértice de meia espessura ao longo da normal média
    n = len(casco)
    out = []
    for i in range(n):
        a, b, c = casco[i - 1], casco[i], casco[(i + 1) % n]
        e1, e2 = b - a, c - b
        n1 = np.array([e1[1], -e1[0]]) / max(np.linalg.norm(e1), 1e-9)
        n2 = np.array([e2[1], -e2[0]]) / max(np.linalg.norm(e2), 1e-9)
        nn = n1 + n2
        nn = nn / max(np.linalg.norm(nn), 1e-9)
        out.append(b + nn * 0.5 * esp / max(0.5, float(np.dot(nn, n1))))
    return np.array(out)


def _esc_air40a(ctx, fund: Fundidor, k_esc: int) -> None:
    """T-Motor AIR 40A (55,6 × 25,2 × 11,3) ao longo do braço: termorretrátil, rótulo, condensador, saídas, fita de
    espuma de 1 mm por baixo e 2 abraçadeiras de nylon justas ao ESC e ao tubo. O condensador (Ø10 × 15,5) vai deitado
    POR CIMA do ESC quando este fica fora do disco da hélice (frame 1950: a ~0,5 m do motor); debaixo do disco (frames
    pequenos, com o ESC entre a perna e o motor) as pás passam a 2–10 mm do termorretrátil, por isso vai deitado AO LADO
    (−y, encostado ao termorretrátil, a meia altura, soldado às ilhas de entrada), fora das abraçadeiras."""
    hw = ctx.hw
    s_esc = hw.frame.esc_no_braco if hw.frame.esc_no_braco is not None else 0.45 * hw.braco
    cond_ao_lado = (hw.braco - s_esc) / MM - 31.5 < hw.helice.raio / MM + 2.0
    g = ctx.geom_existente(f"esc{k_esc}")
    p = np.array(g.pos, dtype=float)
    corpo, p_loc, r_b, z_base, r_t = _assento_esc(ctx, k_esc, p, float(g.size[2]))
    d = r_b.T @ np.array([p[0], p[1], 0.0])
    ang = math.atan2(d[1], d[0])
    R = _rz(ang)
    e_fita = 1.0
    k = Quadro(ctx, fund, corpo, (p_loc[0], p_loc[1], z_base), R)
    n = f"el_esc{k_esc}"
    with ctx.peca("esc", k_esc):
        k.m("el_espuma_fita", g_caixa(-26.0, 26.0, -5.0, 5.0, 0.0, e_fita), "esc", k_esc)
        zb = e_fita
        k.m("el_termo_preto", g_caixa_arred(-27.8, 27.8, -12.6, 12.6, zb, zb + 11.3, 1.6, 2), "esc", k_esc)
        k.m("el_rotulo_esc", g_caixa(-4.0, 22.0, -9.5, 9.5, zb + 11.3, zb + 11.45), "esc", k_esc)
        k.m("el_rotulo_branco", g_caixa(0.0, 18.0, -2.4, 2.4, zb + 11.45, zb + 11.5), "esc", k_esc)
        k.caixa(f"{n}_saida_fases", 27.8, 31.5, -9.0, 9.0, zb + 2.5, zb + 7.5, "el_termo_preto")
        k.caixa(f"{n}_saida_entrada", -31.5, -27.8, -7.0, 7.0, zb + 2.5, zb + 7.5, "el_termo_preto")
        x_c, y_c, z_c = (-26.8, -17.6, zb + 5.65) if cond_ao_lado else (-25.0, 0.0, zb + 16.3)
        k.m("el_condensador", mover(g_cil(5.0, 0.0, 15.5, 20), eixo_para((1, 0, 0)), (x_c, y_c, z_c)), "esc", k_esc)
        k.m("el_aluminio", mover(g_cil(4.3, 0.0, 0.4, 20), eixo_para((1, 0, 0)), (x_c + 15.5, y_c, z_c)), "esc", k_esc)
        # 2 abraçadeiras de nylon 3,6 mm (laço justo ao ESC e ao tubo, cabeça de lado), fora do condensador e do rótulo
        laco = _laco_abracadeira(12.6, zb + 11.3, r_t, 1.1)
        fer = _fer(ctx)
        for xa in (-6.0, 24.0):
            pts = [(xa, u, w) for u, w in laco]
            k.m("el_abracadeira", g_fita(arredondar(pts, 1.0, 3, fechada=True), 3.6, 1.1, (1.0, 0.0, 0.0), fechada=True),
                "esc", k_esc)
            k.m("el_abracadeira", g_caixa(xa - 2.6, xa + 2.6, 12.6 + 0.55, 12.6 + 4.6, zb + 2.0, zb + 7.5), "esc", k_esc)
            if fer is not None:
                laco_c = [k.ponto(xa, u, w).tolist() for u, w in _contacto_abracadeira(12.6, zb + 11.3, r_t)]
                fer.registar(tipo="abracadeira", norma="abraçadeira de nylon 3,6 × 150", largura_mm=3.6, comp_mm=150,
                             corpo=corpo, ponto=k.ponto(xa, 0.0, zb + 5.0).tolist(), eixo=k.dir((1.0, 0.0, 0.0)).tolist(),
                             peca="esc", inst=k_esc, material="fer_nylon_preto", laco=laco_c,
                             descricao="Abraçadeira de nylon 3,6 × 150 mm (ESC ao tubo do braço)")
    _esconder(ctx, f"esc{k_esc}")


def _esc_4em1(ctx, fund: Fundidor, z_placa_topo, z_placa_fundo) -> None:
    """ESC 4-em-1 (padrão 30,5 mm): PCB preta, 4 pares de MOSFET, MCU, condensador, ilhas dos motores, amortecedores,
    4 M3 por baixo da placa com porcas de nylon por cima. Num 5″ assenta por cima das raízes dos braços de carbono."""
    c, h = _info(ctx, "esc")
    g_mot = ctx.geom_existente("motor1")
    z_braco = float(g_mot.pos[2] - g_mot.size[1]) if (g_mot is not None and not ctx.hw.frame.dados.get("tubo_mm")) else c[2] - h[2]
    z0 = max(c[2] - h[2], z_braco)
    k = Quadro(ctx, fund, "drone", (c[0], c[1], z0))
    furos = [(sx * 15.25, sy * 15.25, 1.65) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    ancoras = ctx.registo.notas.setdefault("ancoras", {})
    with ctx.peca("esc"):
        k.m("el_pcb_preto", g_placa_furos(-19.0, 19.0, -19.0, 19.0, 0.5, 2.1, furos, n=12), "esc")
        for fx, fy, _r in furos:
            k.m("el_silicone", mover(g_anel(1.65, 3.4, 0.0, 0.5, 16), None, (fx, fy, 0.0)), "esc")
        for i, (sx, sy) in enumerate(((1, 1), (-1, -1), (-1, 1), (1, -1)), 1):
            k.m("el_chip", g_caixa(sx * 9.0 - 3.0, sx * 9.0 + 3.0, sy * 5.0 - 5.0, sy * 5.0 + 5.0, 2.1, 3.2), "esc")
            for f, yc in zip("abc", (3.2, 6.0, 8.8), strict=True):
                nm_pad = f"el_esc_motor{i}_{f}"
                k.caixa(nm_pad, sx * 17.0 - 1.5, sx * 17.0 + 1.5, sy * yc - 1.0, sy * yc + 1.0, 2.1, 2.4, "el_estanho")
                ancoras[nm_pad] = {"corpo": "drone", "ponto": k.ponto(sx * 17.0, sy * yc, 2.4).tolist(),
                                   "direcao": [float(sx), 0.0, 0.0]}
        k.m("el_chip", g_caixa(-2.5, 2.5, -2.5, 2.5, 2.1, 3.1), "esc")
        k.m("el_condensador", mover(g_cil(4.5, 0.0, 16.0, 20), eixo_para((1, 0, 0)), (-8.0, -14.0, 5.4)), "esc")
    fer = _fer(ctx)
    if fer is not None and z_placa_fundo is not None:
        for fx, fy, _r in furos:
            p = k.ponto(fx, fy, 0.0)
            fer.parafuso("drone", [float(p[0]), float(p[1]), float(z_placa_fundo)], (0.0, 0.0, 1.0), "M3",
                         aperto=(z0 + 2.1 * MM - z_placa_fundo) / MM, cabeca="ISO 7380", porca="ISO 4032",
                         material_="aco_preto", material_porca="nylon_branco", peca="esc",
                         nota="ESC 4-em-1: atravessa placa_inferior")
    _esconder(ctx, "esc")


# =================================================================================================== câmaras
def _pe_camera(ctx, k: Quadro, xb: float) -> tuple[float, float]:
    """(início do pé do suporte da câmara, x dos 2 furos M3) no referencial da câmara: o pé vai de xb − 13 a xb + 1,
    a não ser que a cinta da bateria passe por cima da placa nesse sítio (frames pequenos: no 5″ a cinta da frente
    corre a x 20,5–35,5 e o pé chegava a 29,6) — aí o pé começa 0,5 mm depois da cinta (≥ 6 mm de pé)."""
    x0, xf = xb - 13.0, xb - 7.5
    gb = ctx.geom_existente("bateria")
    if gb is None:
        return x0, xf
    borda = (float(gb.pos[0]) + (b3.RASGO_X + 0.5 * b3.L_CINTA) * MM - float(k.o[0])) / MM + 0.5
    if x0 < borda <= xb + 1.0 - 6.0:
        return borda, 0.5 * (borda + xb + 1.0)
    return x0, xf


def _pe_camera_curto(ctx, k: Quadro, x_f: float, z_placa_loc: float) -> tuple[float, float]:
    """(espessura do pé, |y| dos 2 M3) do suporte da câmara: (3, 8) — ou (2, 9,5) quando o topo do pack do build (a
    caixa física `bateria`, com a pegada por baixo dos 2 M3 + 3,5 mm) fica a menos de 4,5 mm da face de baixo da placa
    (o Tattu de 194 mm do semissólido: 4 mm). Com o pé de 3 mm o M3 × 10 passa 1,6 mm da porca baixa (2,4) e toca no
    pack; com o de 2 mm e a porca sem anilha o comprimento normalizado é M3 × 8 (passa 0,6 mm da porca: F4 ≥ ½ passo)
    e a ponta fica a 1 mm do pack; as porcas a ±9,5 deixam 13,5 mm entre as faces de dentro (|y| 6,75) para o FPC."""
    gb, gp = ctx.geom_existente("bateria"), ctx.geom_existente("placa")
    if gb is None or gp is None:
        return 3.0, 8.0
    pb, hb = np.asarray(gb.pos, float), np.asarray(gb.size, float)
    folga = ((float(gp.pos[2]) - float(gp.size[2])) - (float(pb[2]) + float(hb[2]))) / MM
    if folga >= 4.5:
        return 3.0, 8.0
    for yy in (8.0, -8.0):
        q = k.ponto(x_f, yy, z_placa_loc)
        if abs(float(q[0]) - pb[0]) <= hb[0] + 3.5 * MM and abs(float(q[1]) - pb[1]) <= hb[1] + 3.5 * MM:
            return 2.0, 9.5
    return 3.0, 8.0


def _suporte_camera(ctx, fund: Fundidor, k: Quadro, xb: float, hy: float, hz: float, z_placa_loc: float | None,
                    furos_m2: list) -> None:
    """Suporte em L de PETG atrás da placa da câmara (estimado): placa vertical de 2 mm com os 4 furos M2 e a
    passagem do FPC por baixo, pé de 12 mm na placa de baixo com 2 furos M3 (pé de 3 mm; de 2 mm, com os M3 mais
    afastados, quando o pack fica perto da placa — `_pe_camera_curto`)."""
    if z_placa_loc is None:
        return
    x_pe, x_f = _pe_camera(ctx, k, xb)
    e_pe, y_f = _pe_camera_curto(ctx, k, x_f, z_placa_loc)
    with ctx.peca("camera"):
        Rx = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])    # placa (y, z) → espessura em x
        vert = g_placa_furos(-hy - 2.0, hy + 2.0, z_placa_loc + e_pe, hz, -1.0, 1.0,
                             [(yy, zz, 1.1) for yy, zz in furos_m2], n=12)
        k.m("el_petg", mover(vert, Rx, (xb, 0.0, 0.0)), "camera")
        pe = g_placa_furos(x_pe, xb + 1.0, -hy - 2.0, hy + 2.0, z_placa_loc, z_placa_loc + e_pe,
                           [(x_f, y_f, 1.65), (x_f, -y_f, 1.65)], n=12)
        k.m("el_petg", pe, "camera")
    fer = _fer(ctx)
    if fer is not None:
        for yy in (y_f, -y_f):
            # porca baixa ISO 4032 (2,4 mm): por baixo da placa há só 4 mm até ao topo do pack (o Tattu de 194 mm chega cá)
            # (pé de 2 mm: sem anilha debaixo da porca, para o comprimento normalizado ser o M3 × 8)
            fer.parafuso("drone", k.ponto(x_f, yy, z_placa_loc + e_pe).tolist(), (0.0, 0.0, -1.0), "M3",
                         aperto=e_pe + 3.0, cabeca="ISO 7380", porca="ISO 4032", anilha_porca=e_pe >= 3.0,
                         material_="aco_preto", peca="camera", nota="suporte da câmara: atravessa placa_inferior")


def _camera_csi(ctx, fund: Fundidor, cam, z_placa_topo: float | None, abs_: bool = False) -> None:
    """Raspberry Pi Camera Module 3 (Wide) de pé no nariz, lente para +x (referencial: centro da caixa `camera`).
    Com `abs_` o suporte é o de ABS impresso (`_suporte_camera_abs`, placa vertical de 2,4 mm)."""
    c, h = cam
    k = Quadro(ctx, fund, "drone", c)
    hx, hy, hz = (float(v) / MM for v in h)
    xb = -hx
    xp0, xp1 = xb + 1.0, xb + 2.0                         # a PCB (1 mm) encostada ao suporte
    z_l = hz - 0.394 * 2.0 * hz                           # centro ótico a 9,46 mm do topo de uma placa de 24 mm
    furos = [(hy - 2.0, hz - 2.0), (-hy + 2.0, hz - 2.0), (-hy + 2.0, hz - 14.5), (hy - 2.0, hz - 14.5)]
    Rx = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])        # placa (y, z) → normal +x
    with ctx.peca("camera"):
        k.m("el_pcb_verde", mover(g_placa_furos(-hy, hy, -hz, hz, xp0, xp1, [(yy, zz, 1.1) for yy, zz in furos], n=12),
                                  Rx, None), "camera")
        k.m("el_plastico_preto", g_caixa(xp1, xp1 + 4.6, -4.25, 4.25, z_l - 4.25, z_l + 4.25), "camera")
        k.m("el_plastico_brilho", mover(g_cil(3.9, 0.0, hx - 0.25 - (xp1 + 4.6), 24), eixo_para((1, 0, 0)),
                                        (xp1 + 4.6, 0.0, z_l)), "camera")
        k.m("el_vidro", mover(g_cil(2.9, 0.0, 0.2, 24), eixo_para((1, 0, 0)), (hx - 0.25, 0.0, z_l)), "camera")
        k.caixa("el_cam_conector_fpc", xp1, xp1 + 2.5, -10.4, 10.4, -hz, -hz + 5.0, "el_plastico_preto")
        k.m("el_trava_fpc", g_caixa(xp1, xp1 + 3.0, -10.0, 10.0, -hz - 0.4, -hz + 0.8), "camera")
    fer = _fer(ctx)
    e_sup = ESP_SUPORTE_CAMERA_ABS if abs_ else 2.0
    if fer is not None and z_placa_topo is not None:
        for yy, zz in furos:
            fer.parafuso("drone", k.ponto(xp1, yy, zz).tolist(), (-1.0, 0.0, 0.0), "M2", aperto=1.0 + e_sup,
                         cabeca="ISO 7380", porca="ISO 4032", anilha_porca=False, material_="aco_preto", peca="camera")
    z_loc = None if z_placa_topo is None else (z_placa_topo - c[2]) / MM
    if abs_:
        _suporte_camera_abs(ctx, fund, k, xb, hy, hz, z_loc, furos)
    else:
        _suporte_camera(ctx, fund, k, xb, hy, hz, z_loc, furos)
    _esconder(ctx, "camera")


def _camera_dvp(ctx, fund: Fundidor, cam, z_placa_topo: float | None, abs_: bool = False) -> None:
    """Portenta Vision Shield (HM0360) de pé no nariz: conectores HD atrás, PCB, módulo da câmara e microfones."""
    c, h = cam
    k = Quadro(ctx, fund, "drone", c)
    hx, hy, hz = (float(v) / MM for v in h)
    xb = -hx
    xf = xb + 4.0
    with ctx.peca("camera"):
        k.m("el_pcb_preto", g_caixa(xb + 3.0, xf, -hy, hy, -hz, hz), "camera")
        k.m("el_plastico_preto", juntar(*[g_caixa(xb + 1.5, xb + 3.0, yy - 10.0, yy + 10.0, -1.8, 1.8)
                                          for yy in (-hy * 0.45, hy * 0.45)]), "camera")
        k.m("el_plastico_preto", g_caixa(xf, xf + 2.5, -3.0, 3.0, -3.0, 3.0), "camera")
        k.m("el_plastico_brilho", mover(g_cil(2.2, 0.0, hx - 0.25 - (xf + 2.5), 20), eixo_para((1, 0, 0)),
                                        (xf + 2.5, 0.0, 0.0)), "camera")
        k.m("el_vidro", mover(g_cil(1.4, 0.0, 0.2, 20), eixo_para((1, 0, 0)), (hx - 0.25, 0.0, 0.0)), "camera")
        k.m("el_aco", juntar(*[g_caixa(xf, xf + 1.0, yy - 1.75, yy + 1.75, 5.0, 7.65) for yy in (-14.0, 14.0)]), "camera")
        k.caixa("el_cam_conector_fpc", xb + 1.5, xb + 3.0, -10.0, 10.0, -hz, -hz + 4.0, "el_plastico_preto")
    z_loc = None if z_placa_topo is None else (z_placa_topo - c[2]) / MM
    if abs_:
        _suporte_camera_abs(ctx, fund, k, xb, hy, hz, z_loc, [])
    else:
        _suporte_camera(ctx, fund, k, xb, hy, hz, z_loc, [])
    _esconder(ctx, "camera")


# =================================================================================================== regulador 24 V
def _fonte_servos(ctx, fund: Fundidor, z_placa_topo, z_placa_fundo) -> None:
    """Conversor buck-boost 24 V / 5 A dos servos (PCB aberta; disposição estimada) com 4 M3 de nylon, anilhas de
    nylon de 1 mm entre a PCB e a placa de baixo e porcas de nylon por baixo dela."""
    c, h = _info(ctx, "fonte_servos")
    z0 = c[2] - h[2]
    k = Quadro(ctx, fund, "drone", (c[0], c[1], z0))
    hx, hy = float(h[0]) / MM, float(h[1]) / MM
    furos = [(sx * (hx - 3.5), sy * (hy - 3.5), 1.65) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    with ctx.peca("fonte_servos"):
        k.m("el_pcb_azul", g_placa_furos(-hx, hx, -hy, hy, 0.0, 1.6, furos, n=12), "fonte_servos")
        k.m("el_cobre", mover(g_anel(3.0, 7.0, 1.6, 8.6, 24), None, (-4.0, 3.0, 0.0)), "fonte_servos")
        k.m("el_cinza_escuro", mover(g_cil(3.0, 1.6, 8.5, 16), None, (-4.0, 3.0, 0.0)), "fonte_servos")
        caps = []
        for xx, yy in ((7.0, 6.0), (-1.5, -7.5)):
            caps.append(mover(g_cil(4.0, 1.6, 11.0, 20), None, (xx, yy, 0.0)))
        k.m("el_condensador", juntar(*caps), "fonte_servos")
        k.m("el_aluminio", juntar(*[mover(g_cil(3.6, 11.0, 11.2, 20), None, (xx, yy, 0.0)) for xx, yy in
                                    ((7.0, 6.0), (-1.5, -7.5))] + [g_caixa(5.0, 13.0, -10.5, -2.5, 1.6, 9.6)]),
            "fonte_servos")
        k.m("el_trimmer_azul", g_caixa(-13.5, -9.0, -10.5, -5.5, 1.6, 11.6), "fonte_servos")
        k.caixa("el_fonte24_borne_entrada", -hx, -hx + 7.0, -5.1, 5.1, 1.6, 11.0, "el_terminal_verde")
        k.caixa("el_fonte24_borne_saida", hx - 7.0, hx, -5.1, 5.1, 1.6, 11.0, "el_terminal_verde")
    fer = _fer(ctx)
    if fer is not None and z_placa_topo is not None and z_placa_fundo is not None:
        folga = (z0 - z_placa_topo) / MM
        for fx, fy, _r in furos:
            p = k.ponto(fx, fy, 1.6)
            if folga > 0.2:
                fer.pilar("drone", [float(p[0]), float(p[1]), float(z_placa_topo)], (0.0, 0.0, 1.0), "M3",
                          round(folga, 3), tipo="redondo", af=7.0, material_="nylon_branco", peca="fonte_servos")
            fer.parafuso("drone", p.tolist(), (0.0, 0.0, -1.0), "M3", aperto=(z0 + 1.6 * MM - z_placa_fundo) / MM,
                         cabeca="ISO 4762", porca="ISO 4032", anilha_porca=False, material_="nylon_branco",
                         peca="fonte_servos", nota="regulador 24 V: atravessa placa_inferior")
    _esconder(ctx, "fonte_servos")


# =================================================================================================== versão ACESSÍVEL
# 2.ª fase (2026-10-20): frame `*_abs` → os SUPORTES da eletrónica impressos em ABS (ponte do FC, suporte da câmara,
# travessa dos sensores em `bateria3d`, suportes dos drivers e do buck); mecanismo de motorredutores DC → sai o
# regulador de 24 V e entram os 4 drivers DRV8871, o UBEC dos servos e (só se os motores forem de 12 V) o buck.
ESP_PONTE_ABS = 3.4            # mm — o que cabe entre o topo do Active Cooler (13,7 mm acima do Pi) e os amortecedores
CONTRAFURO_M3 = (3.2, 1.65)    # raio e fundo do contrafuro da cabeça ISO 7380 M3 (Ø5,7 × 1,65) — por baixo da ponte
ALOJ_PILAR = 3.1               # raio do rebaixo onde entra o topo do pilar sextavado de 5 mm (Ø entre cantos 5,77)
PILARES_M25 = (25.0, 20.0, 18.0, 16.0, 15.0, 12.0, 11.0, 10.0)   # comprimentos de catálogo dos pilares M2,5 M-F
ESP_SUPORTE_CAMERA_ABS = 2.4   # mm — placa vertical do suporte da câmara em ABS (≥ 2 mm de parede)
# Adafruit DRV8871 #3190 (ficha: 24,4 × 20,4 × 9,7 mm com os bornes, 2,2 g): PCB, 2 bornes de 3,5 mm (VM/GND e
# OUT1/OUT2) numa borda e a barra de 6 pinos na outra (fotos do fabricante) — disposição interior estimada
DRV_A, DRV_B, DRV_ALTURA = 24.4, 20.4, 9.7
# UBEC dos servos dos cotovelos (aceita 6S): Hobbywing UBEC 10A V2 — 45 × 20 × 16,2 mm, 34 g, 2–6S, 6,0/7,4/8,4 V,
# 10 A (15 A de pico); a saída fica a 6,0 V (o DS3218MG é dado até 6,8 V) — pesquisa `fuso.md` §6
UBEC_DIMS = (45.0, 20.0, 16.2)
# buck XL4016 8 A (61 × 41 × 27 mm, ~50 g, 4–40 V → 1,25–36 V) — 2, um por par de ombros (motorredutores de 12 V)
BUCK_DIMS = (61.0, 41.0, 27.0)
INSERTO_M3 = (5.7, 2.0, 2.3)   # inserto de latão M3 × 5,7 de cravar a quente: comprimento, raio do FURO impresso (Ø4,0)
#                                e raio exterior do serrilhado (Ø4,6) — desenha-se com o Ø do furo (o ABS fecha à volta)
_MATERIAIS_ATUADORES = {
    "el_dissipador": ((0.05, 0.05, 0.055, 1.0), 0.50, 0.55, 0.03, 0.0),   # alumínio anodizado preto (dissipadores)
    "el_toroide": ((0.86, 0.82, 0.58, 1.0), 0.20, 0.25, 0.0, 0.0),        # núcleo de pó de ferro (amarelo/branco)
}


def _atuadores_dc(hw) -> bool:
    """O mecanismo dos braços usa motorredutores DC nos ombros (versão acessível): sai o regulador de 24 V dos servos
    DYNAMIXEL, entram os drivers DRV8871 (ponte H, 1 por motor) e o UBEC dos servos dos cotovelos."""
    b = getattr(hw, "bracos", None)
    if b is None:
        return False
    return str((getattr(b.ombro.servo, "dados", None) or {}).get("tipo", "")) == "motorredutor_dc"


def _tensao_ombro(hw) -> float:
    b = getattr(hw, "bracos", None)
    return float(getattr(getattr(b, "ombro", None).servo, "tensao", 0.0)) if b is not None else 0.0


def _placa_seg(x0, x1, y0, y1, z0, z1, furos, n: int = 12):
    """Placa com furos partida ao longo de y a meio de furos consecutivos — furos desalinhados nunca partilham uma
    linha da grelha de `g_placa_furos` (ficam redondos); os sólidos só se tocam pelas faces (volume exato)."""
    fs = sorted(furos, key=lambda f: f[1])
    cortes = [y0]
    for a, b in itertools.pairwise(fs):
        if b[1] - a[1] > 1e-6:
            cortes.append(0.5 * (a[1] + b[1]))
    cortes.append(y1)
    partes = []
    for ya, yb in itertools.pairwise(cortes):
        partes.append(g_placa_furos(x0, x1, ya, yb, z0, z1, [f for f in fs if ya < f[1] < yb], n=n))
    return juntar(*partes)


def _cotas_ponte_abs(rpi, fc):
    """(z do fundo da ponte ABS, z do topo dos pilares de cima, comprimento dos pilares mm, fundo do rebaixo mm) —
    a ponte vai do topo do Active Cooler + 0,3 mm até aos amortecedores do FC; None se não couber."""
    z_pi_topo = float(rpi[0][2] - rpi[1][2]) + 1.6 * MM
    z1 = float(fc[0][2] - fc[1][2]) - 0.9 * MM
    z0 = z1 - ESP_PONTE_ABS * MM
    if z0 < z_pi_topo + (COOLER_ALTURA + 0.3) * MM - 1e-9:
        return None
    for comp in PILARES_M25:
        reb = (z_pi_topo + comp * MM - z0) / MM
        if 0.3 - 1e-6 <= reb <= ESP_PONTE_ABS - 2.0 + 1e-6:
            return z0, z_pi_topo + comp * MM, comp, round(reb, 6)
    return None


def _ponte_fc_abs(ctx, fund: Fundidor, rpi, centro_pilha, z0: float, reb: float) -> None:
    """Ponte da pilha do FC IMPRESSA em ABS (versão acessível): 3,4 mm (o que cabe entre o Active Cooler e os
    amortecedores), 2 réguas nos pilares do Pi (rebaixos de `reb` mm onde entra o topo do pilar sextavado) e 2
    travessas com os 4 furos de 30,5 mm, cada um com o CONTRAFURO por baixo onde fica a cabeça do M3 (rente à face de
    baixo: não desce para o dissipador). Camadas empilhadas = sólidos fechados (volume exato)."""
    c, _h = rpi
    base = (c[0] - 0.0425, c[1] - 0.028)
    k = Quadro(ctx, fund, "drone", (base[0], base[1], z0))
    fp = _furos_pilha(ctx, centro_pilha, base)
    rc, hc = CONTRAFURO_M3
    e = ESP_PONTE_ABS
    xs = sorted({round(x, 4) for x, _y in fp})
    ys = sorted({round(y, 4) for _x, y in fp})
    x_fr0 = min(56.5, xs[-1] - rc - 2.0)
    pilares = list(_RPI5_FUROS)
    cortes = sorted({0.0, round(reb, 6), hc, e})
    pecas = []
    for za, zb in itertools.pairwise(cortes):
        r_pi = ALOJ_PILAR if zb <= reb + 1e-6 else 1.35
        r_fc = rc if zb <= hc + 1e-6 else 1.7
        f_pi = [(x, y, r_pi) for x, y in pilares]
        f_fc = [(x, y, r_fc) for x, y in fp]
        pecas.append(_placa_seg(-1.5, 8.5, -2.5, 58.5, za, zb, [f for f in f_pi if f[0] < 30.0]))
        pecas.append(_placa_seg(x_fr0, 66.5, -2.5, 58.5, za, zb,                # 1,9 mm à volta do rebaixo
                                [f for f in f_pi if f[0] > 30.0] + [f for f in f_fc if f[0] > x_fr0]))
        for yc in ys:
            pecas.append(_placa_seg(8.5, x_fr0, yc - 5.5, yc + 5.5, za, zb,
                                    [f for f in f_fc if f[0] < x_fr0 and abs(f[1] - yc) < 1e-3]))
    with ctx.peca("ponte_fc"):
        k.m(b3.MATERIAL_ABS, juntar(*pecas), "ponte_fc")
    b3.regista_impressa(
        ctx, "ponte_fc", 0, "Ponte da pilha do FC (sobre o Raspberry Pi 5)", b3.Q_VIRADA,
        "Imprime-se de CABEÇA PARA BAIXO (a face de cima, plana, na mesa): os contrafuros das cabeças M3 e os rebaixos "
        "dos pilares ficam virados para cima, sem suportes. 3,4 mm de espessura — o que cabe entre o topo do Active "
        "Cooler (13,7 mm acima do Pi) e os amortecedores do FC; assenta nos 4 pilares de latão M2,5 × 15 do Pi e leva o "
        "padrão de 30,5 mm do FC (as cabeças dos M3 ficam DENTRO da ponte, rentes à face de baixo).")


def _suporte_camera_abs(ctx, fund: Fundidor, k: Quadro, xb: float, hy: float, hz: float, z_placa_loc: float | None,
                        furos_m2: list) -> None:
    """Suporte em L da câmara IMPRESSO em ABS (versão acessível): placa vertical de 2,4 mm com os 4 furos M2 (porcas
    atrás), pé de 3 mm com os 2 furos M3 na placa de baixo e 2 nervuras a 45° nas bordas (longe das porcas M2)."""
    if z_placa_loc is None:
        return
    ev, ep, g = ESP_SUPORTE_CAMERA_ABS, 3.0, 7.0
    w = hy + 3.0
    xr = xb + 1.0 - ev                                     # face de trás da placa vertical
    zf = z_placa_loc + ep                                  # topo do pé
    Rx = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])    # placa (y, z) → espessura em x
    Rp = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]])    # prisma (x, z) extrudido em y
    with ctx.peca("suporte_camera"):
        vert = g_placa_furos(-w, w, zf, hz + 0.5, 1.0 - ev, 1.0, [(yy, zz, 1.1) for yy, zz in furos_m2], n=12)
        k.m(b3.MATERIAL_ABS, mover(vert, Rx, (xb, 0.0, 0.0)), "suporte_camera")
        x_pe, x_f = _pe_camera(ctx, k, xb)
        pe = g_placa_furos(x_pe, xb + 1.0, -w, w, z_placa_loc, zf, [(x_f, 8.0, 1.65), (x_f, -8.0, 1.65)], n=12)
        k.m(b3.MATERIAL_ABS, pe, "suporte_camera")
        g = min(g, xr - x_pe)
        tri = [(xr, zf), (xr, zf + g), (xr - g, zf)]
        for y0, y1 in ((w - ev, w), (-w, -w + ev)):
            k.m(b3.MATERIAL_ABS, mover(b3.g_prisma(tri, y0, y1), Rp, None), "suporte_camera")
    b3.regista_impressa(
        ctx, "suporte_camera", 0, "Suporte em L da câmara (nariz)", b3.Q_IDENTIDADE,
        "Imprime-se como está, o pé na mesa: a placa vertical sobe sem saliências e as 2 nervuras têm 45° (não precisam "
        "de suportes); os 4 furos M2 da câmara ficam horizontais (Ø2,2). Placa de 2,4 mm, pé de 3 mm com 2 furos M3 "
        "para a placa de baixo.")
    fer = _fer(ctx)
    if fer is not None:
        for yy in (8.0, -8.0):
            fer.parafuso("drone", k.ponto(x_f, yy, zf).tolist(), (0.0, 0.0, -1.0), "M3",
                         aperto=6.0, cabeca="ISO 7380", porca="ISO 4032", material_="aco_preto", peca="suporte_camera",
                         nota="suporte da câmara (ABS): atravessa placa_inferior")


def _drv8871(ctx, fund: Fundidor, k_drv: int, centro, z_face: float, R, esp_placa: float, placa: str) -> dict:
    """Driver DRV8871 (Adafruit #3190) de um motorredutor no SUPORTE IMPRESSO em ABS (`suporte_driver`, k) encostado à
    face `z_face` de uma placa; `R` = (a, b, z) do suporte → corpo (b = a borda dos bornes, z = para FORA da placa):
    almofada de espuma de 2 mm (as pontas dos pinos não tocam no suporte), 2 paredes que centram a placa (colada: não
    tem furos de fixação), 2 × M3 + porca autoblocante do outro lado da placa. Bornes (VM/GND e OUT1/OUT2) na borda b
    (o fio sai para o lado do ombro), barra de 6 pinos (IN1/IN2/GND) na borda oposta."""
    k = Quadro(ctx, fund, "drone", (centro[0], centro[1], z_face), R)
    ha, hb = 0.5 * DRV_A, 0.5 * DRV_B
    e_base, e_esp = 2.4, 2.0
    zp = e_base + e_esp                                     # face de baixo da PCB
    n = f"el_drv{k_drv}"
    out = {}
    a_par = 17.8                                            # cabeças (r 2,85) a 0,25 mm das paredes
    with ctx.peca("suporte_driver", k_drv):
        base = g_placa_furos(-21.5, 21.5, -hb - 1.0, hb + 1.0, 0.0, e_base, [(-a_par, 0.0, 1.7), (a_par, 0.0, 1.7)],
                             n=12)
        paredes = juntar(g_caixa(-ha - 2.3, -ha - 0.3, -hb, hb - 8.0, e_base, zp + 2.0),
                         g_caixa(ha + 0.3, ha + 2.3, -hb, hb - 8.0, e_base, zp + 2.0))
        k.m(b3.MATERIAL_ABS, juntar(base, paredes), "suporte_driver", k_drv)
    with ctx.peca("fonte_servos"):
        k.m("el_espuma_fita", g_caixa(-8.0, 8.0, -6.0, 2.0, e_base, zp), "fonte_servos")
        k.m("el_pcb_azul", g_caixa(-ha, ha, -hb, hb, zp, zp + 1.6), "fonte_servos")
        zt = zp + 1.6
        k.m("el_chip", juntar(g_caixa(-2.45, 2.45, -4.0, 2.0, zt, zt + 1.7),                 # DRV8871 (HSOP-8)
                              g_caixa(3.6, 5.6, -5.0, -3.8, zt, zt + 0.5),                    # R do ILIM (0805)
                              g_caixa(-6.2, -4.2, -5.0, -3.8, zt, zt + 0.5)), "fonte_servos")
        k.m("el_cap_polimero", juntar(g_caixa(-8.6, -6.2, -2.0, -0.4, zt, zt + 1.1),
                                      g_caixa(6.2, 8.6, -2.0, -0.4, zt, zt + 1.1)), "fonte_servos")
        # dissipador colado no DRV8871 (7 × 7 mm, alhetas): no limite de 2,37 A o CI dissipa ~2,6 W (pesquisa)
        zd = zt + 1.7
        k.m("el_dissipador", juntar(g_caixa(-3.5, 3.5, -4.5, 2.5, zd, zd + 1.2),
                                    *[g_caixa(-3.5 + 1.95 * j, -2.5 + 1.95 * j, -4.5, 2.5, zd + 1.2, zd + 5.0)
                                      for j in range(4)]), "fonte_servos")
        # bornes de 3,5 mm (2 vias cada): VM/GND do lado −a, OUT1/OUT2 do lado +a; entradas dos fios na face +b
        b0, b1, h_b = hb - 7.6, hb, DRV_ALTURA - 1.6
        for nome_b, a0 in (("alimentacao", -ha + 2.0), ("motor", ha - 9.0)):
            k.caixa(f"{n}_{nome_b}", a0, a0 + 7.0, b0, b1, zt, zt + h_b, "el_terminal_verde", peca="fonte_servos")
            ab, cab = [], []
            for j in range(2):
                ac = a0 + 1.75 + 3.5 * j
                ab.append(g_caixa(ac - 1.2, ac + 1.2, b1, b1 + 0.12, zt + 1.4, zt + 4.0))
                cab.append(mover(g_cil(1.25, zt + h_b, zt + h_b + 0.15, 12), None, (ac, b0 + 3.0, 0.0)))
            k.m("el_abertura", juntar(*ab), "fonte_servos")
            k.m("el_aco", juntar(*cab), "fonte_servos")
            ponta = k.ponto(a0 + 3.5, b1, zt + 2.7)
            out[f"{n}_{nome_b}"] = (ponta, k.dir((0.0, 1.0, 0.0)))
        # barra de 6 pinos (IN1, IN2, GND…): base preta e os pinos dourados (6 mm para cima)
        k.caixa(f"{n}_sinal", -7.62, 7.62, -hb + 0.2, -hb + 2.74, zt, zt + 2.5, "el_plastico_preto", peca="fonte_servos")
        pinos = [g_caixa(-6.35 + 2.54 * i - 0.32, -6.35 + 2.54 * i + 0.32, -hb + 1.15, -hb + 1.79, zt + 2.5, zt + 8.5)
                 for i in range(6)]
        k.m("el_ouro", juntar(*pinos), "fonte_servos")
        out[f"{n}_sinal"] = (k.ponto(0.0, -hb + 1.47, zt + 8.5), k.dir((0.0, 0.0, 1.0)))
        k.m("el_rotulo_branco", g_caixa(-3.0, 3.0, 4.0, 4.6, zt, zt + 0.03), "fonte_servos")
    fer = _fer(ctx)
    if fer is not None:
        for aa in (-a_par, a_par):
            fer.parafuso("drone", k.ponto(aa, 0.0, e_base).tolist(), k.dir((0.0, 0.0, -1.0)).tolist(), "M3",
                         aperto=e_base + esp_placa, cabeca="ISO 7380", porca="ISO 10511",
                         material_="aco_preto", peca="suporte_driver", inst=k_drv,
                         nota=f"suporte do driver (ABS): atravessa {placa}")
    return out


def _ubec(ctx, fund: Fundidor, centro, z_topo_placa: float, z_placa_fundo_sup: float) -> dict:
    """UBEC dos 4 servos dos cotovelos — Hobbywing UBEC 10A V2 (2–6S, saída posta a 6,0 V: o DS3218MG é dado até
    6,8 V; 45 × 20 × 16,2 mm, 34 g) — no BERÇO IMPRESSO em ABS (`bandeja_fonte` #3) em cima da placa de cima, atrás
    da pilha e debaixo do carregador da carga útil, deitado ao longo de x: base de 2,4 mm que passa por cima do rasgo
    de alívio, 2 paredes que o centram, fita de espuma dupla face (o UBEC não tem furos) e 4 × M3 + porca autoblocante
    por baixo da placa. Corpo em termorretrátil preto com rótulo (aparência estimada); entrada (pack) na ponta −x e
    saída (servos) na ponta +x, de frente para a pilha."""
    L, W, H = UBEC_DIMS                                     # 45 ao longo de y local (= −x do drone), 20 ao longo de x
    e_b, e_f = 2.4, 1.0
    k = Quadro(ctx, fund, "drone", (centro[0], centro[1], z_topo_placa), _rz(0.5 * math.pi))
    parafusos = [(sx * 14.0, sy * 16.5) for sx in (1, -1) for sy in (1, -1)]
    out = {}
    with ctx.peca("bandeja_fonte", 3):
        base = g_placa_furos(-17.5, 17.5, -20.0, 20.0, 0.0, e_b, [(x, y, 1.7) for x, y in parafusos], n=12)
        paredes = juntar(g_caixa(-0.5 * W - 2.3, -0.5 * W - 0.3, -12.0, 12.0, e_b, e_b + 6.0),
                         g_caixa(0.5 * W + 0.3, 0.5 * W + 2.3, -12.0, 12.0, e_b, e_b + 6.0))
        k.m(b3.MATERIAL_ABS, juntar(base, paredes), "bandeja_fonte", 3)
    with ctx.peca("fonte_servos"):
        k.m("el_espuma_fita", g_caixa(-0.5 * W + 1.5, 0.5 * W - 1.5, -0.5 * L + 4.0, 0.5 * L - 4.0, e_b, e_b + e_f),
            "fonte_servos")
        z0 = e_b + e_f
        k.m("el_termo_preto", g_caixa_arred(-0.5 * W, 0.5 * W, -0.5 * L, 0.5 * L, z0, z0 + H, 1.8, 2), "fonte_servos")
        k.m("el_rotulo_esc", g_caixa(-0.5 * W + 2.0, 0.5 * W - 2.0, -13.0, 13.0, z0 + H, z0 + H + 0.12), "fonte_servos")
        k.m("el_rotulo_branco", g_caixa(-3.5, 3.5, -10.0, 10.0, z0 + H + 0.12, z0 + H + 0.15), "fonte_servos")
        for nome, s in (("el_ubec_entrada", 1.0), ("el_ubec_saida", -1.0)):
            y0, y1 = sorted((s * 0.5 * L, s * (0.5 * L + 1.5)))
            k.caixa(nome, -5.0, 5.0, y0, y1, z0 + 3.0, z0 + H - 4.0, "el_termo_preto", peca="fonte_servos")
            out[nome] = (k.ponto(0.0, s * (0.5 * L + 1.5), z0 + 0.5 * (H - 1.0)), k.dir((0.0, s, 0.0)))
    fer = _fer(ctx)
    if fer is not None:
        for x, y in parafusos:
            fer.parafuso("drone", k.ponto(x, y, e_b).tolist(), (0.0, 0.0, -1.0), "M3",
                         aperto=e_b + (z_topo_placa - z_placa_fundo_sup) / MM, cabeca="ISO 7380", porca="ISO 10511",
                         material_="aco_preto", peca="bandeja_fonte", inst=3,
                         nota="berço do UBEC (ABS): atravessa placa_superior")
    b3.regista_impressa(
        ctx, "bandeja_fonte", 3, "Berço do UBEC dos servos dos cotovelos", b3.Q_IDENTIDADE,
        "Imprime-se como está (a base na mesa, as 2 paredes para cima). Base de 2,4 mm (passa por cima do rasgo de "
        "alívio da placa de cima) com 4 furos M3; o UBEC cola-se com fita de espuma dupla face entre as paredes.")
    return out


def _buck_xl4016(ctx, fund: Fundidor, n_buck: int, centro, z_placa_fundo: float, z_placa_topo: float) -> dict:
    """Buck XL4016 8 A (61 × 41 × 27 mm, ~50 g; disposição interior ESTIMADA: 2 dissipadores pretos com o XL4016E1 e
    o díodo Schottky em TO-220, bobina toroidal, condensadores de entrada/saída, potenciómetro multivoltas, ilhas
    IN/OUT) PENDURADO por baixo da placa de baixo, ao lado do pack, na BASE IMPRESSA em ABS (`bandeja_fonte` #n): a
    base encosta à placa (2 × M3 com a porca autoblocante por cima da placa, apertados antes do buck), 4 colunas com
    insertos de latão M3 × 5,7 (furo Ø4,0) onde aperta a PCB, com os componentes virados para baixo (ar do rotor)."""
    for nome, (rgba, spec, brilho, refl, emis) in _MATERIAIS_ATUADORES.items():
        ctx.material(nome, rgba, specular=spec, shininess=brilho, reflectance=refl, emission=emis)
    L, W, _H = BUCK_DIMS                                    # 61 ao longo de x, 41 ao longo de y
    R = np.diag([1.0, -1.0, -1.0])                          # z local para BAIXO (pendurado)
    e_b, h_col = 2.4, INSERTO_M3[0] + 0.5
    k = Quadro(ctx, fund, "drone", (centro[0], centro[1], z_placa_fundo), R)
    furos = [(sx * (0.5 * L - 3.0), sy * (0.5 * W - 3.0)) for sx in (1, -1) for sy in (1, -1)]
    parafusos_base = [(0.0, 0.5 * W - 3.0), (0.0, -0.5 * W + 3.0)]
    out = {}
    nb = f"el_buck12_{n_buck}"
    with ctx.peca("bandeja_fonte", n_buck):
        base = g_placa_furos(-0.5 * L - 1.0, 0.5 * L + 1.0, -0.5 * W - 1.0, 0.5 * W + 1.0, 0.0, e_b,
                             [(fx, fy, 1.7) for fx, fy in parafusos_base], n=12)
        cols = []
        for fx, fy in furos:
            # coluna Ø8: anel à volta do furo do inserto (Ø4,0 × 5,7) + o resto cheio — 2 sólidos que só se tocam
            cols.append(mover(g_anel(INSERTO_M3[1], 4.0, e_b + h_col - INSERTO_M3[0], e_b + h_col, 20), None,
                              (fx, fy, 0.0)))
            cols.append(mover(g_cil(4.0, e_b, e_b + h_col - INSERTO_M3[0], 20), None, (fx, fy, 0.0)))
        k.m(b3.MATERIAL_ABS, juntar(base, *cols), "bandeja_fonte", n_buck)
        ins = [mover(g_anel(1.25, INSERTO_M3[1] - 0.03, e_b + h_col - INSERTO_M3[0], e_b + h_col, 16), None,
                     (fx, fy, 0.0)) for fx, fy in furos]
        k.m("el_latao", juntar(*ins), "bandeja_fonte", n_buck)
    zp = e_b + h_col
    zt = zp + 1.6
    with ctx.peca("fonte_servos"):
        k.m("el_pcb_azul", g_placa_furos(-0.5 * L, 0.5 * L, -0.5 * W, 0.5 * W, zp, zt,
                                         [(fx, fy, 1.6) for fx, fy in furos], n=16), "fonte_servos")
        # ilhas IN (−x local) e OUT (+x local), estanhadas, com a serigrafia «+»
        for nome, xc in ((f"{nb}_borne_entrada", -0.5 * L + 3.5), (f"{nb}_borne_saida", 0.5 * L - 3.5)):
            k.caixa(nome, xc - 2.0, xc + 2.0, -7.0, 7.0, zt, zt + 0.4, "el_estanho", peca="fonte_servos")
            out[nome] = (k.ponto(xc, 0.0, zt + 0.4), k.dir((0.0, 0.0, 1.0)))
        k.m("el_rotulo_branco", juntar(g_caixa(-0.5 * L + 2.5, -0.5 * L + 4.5, 8.0, 8.4, zt, zt + 0.03),
                                       g_caixa(-0.5 * L + 3.3, -0.5 * L + 3.7, 7.2, 9.2, zt, zt + 0.03),
                                       g_caixa(0.5 * L - 4.5, 0.5 * L - 2.5, 8.0, 8.4, zt, zt + 0.03),
                                       g_caixa(0.5 * L - 3.7, 0.5 * L - 3.3, 7.2, 9.2, zt, zt + 0.03)), "fonte_servos")
        # bobina toroidal (núcleo + espiras de cobre) e condensadores eletrolíticos
        xt_, yt_, r0, r1, ht = -8.0, 4.0, 5.5, 11.0, 11.0
        k.m("el_toroide", mover(g_anel(r0, r1, zt + 0.5, zt + 0.5 + ht, 28), None, (xt_, yt_, 0.0)), "fonte_servos")
        espiras = []
        for j in range(16):
            a = math.tau * (j + 0.5) / 16
            ca, sa = math.cos(a), math.sin(a)
            seccao = [(r0 - 0.45, zt + 0.05), (r1 + 0.45, zt + 0.05), (r1 + 0.45, zt + 0.95 + ht),
                      (r0 - 0.45, zt + 0.95 + ht)]
            pts = [(xt_ + rr * ca, yt_ + rr * sa, zz) for rr, zz in seccao]
            espiras.append(g_fita(arredondar(pts, 0.6, 2, fechada=True), 1.1, 0.8, (-sa, ca, 0.0), fechada=True))
        k.m("el_cobre", juntar(*espiras), "fonte_servos")
        caps = [mover(g_cil(4.0, zt, zt + 14.0, 20), None, (-23.0, 11.0, 0.0)),
                mover(g_cil(5.0, zt, zt + 20.0, 20), None, (24.5, -13.5, 0.0))]
        k.m("el_condensador", juntar(*caps), "fonte_servos")
        k.m("el_aluminio", juntar(mover(g_cil(3.6, zt + 14.0, zt + 14.2, 20), None, (-23.0, 11.0, 0.0)),
                                  mover(g_cil(4.6, zt + 20.0, zt + 20.2, 20), None, (24.5, -13.5, 0.0))), "fonte_servos")
        # 2 dissipadores pretos (alhetas) com o XL4016E1 (TO-220-5) e o Schottky (TO-220) encostados
        dis, epx = [], []
        for y0, y1 in ((-19.0, -5.0), (-3.0, 11.0)):
            dis.append(g_caixa(7.0, 19.0, y0, y0 + 2.5, zt, zt + 25.4))
            for j in range(4):
                xa = 7.0 + 3.6 * j
                dis.append(g_caixa(xa, xa + 1.2, y0 + 2.5, y1, zt + 1.5, zt + 25.4))
            epx.append(g_caixa(8.0, 18.0, y0 - 4.5, y0, zt + 3.0, zt + 18.0))
        k.m("el_dissipador", juntar(*dis), "fonte_servos")
        k.m("el_chip", juntar(*epx, g_caixa(-4.0, -1.0, -17.0, -15.0, zt, zt + 0.6),
                              g_caixa(1.5, 4.5, -17.0, -15.0, zt, zt + 0.6)), "fonte_servos")
        k.m("el_trimmer_azul", g_caixa(-18.75, -9.25, -17.4, -12.6, zt, zt + 10.0), "fonte_servos")
        k.m("el_ouro", mover(g_cil(1.0, zt + 10.0, zt + 10.6, 10), None, (-17.5, -15.0, 0.0)), "fonte_servos")
        k.m("el_led_ambar", g_caixa(-1.0, 1.0, -19.0, -18.0, zt, zt + 0.6), "fonte_servos")
    fer = _fer(ctx)
    if fer is not None:
        for fx, fy in furos:
            fer.parafuso("drone", k.ponto(fx, fy, zt).tolist(), k.dir((0.0, 0.0, -1.0)).tolist(), "M3", aperto=1.6,
                         rosca_metida=INSERTO_M3[0], cabeca="ISO 7380", porca=None, material_="aco_preto",
                         peca="fonte_servos", nota="buck XL4016: rosca no inserto de latão da base impressa")
            fer.registar(tipo="inserto", norma="inserto de latão M3", rosca="M3", comp_mm=INSERTO_M3[0],
                         d_ext_mm=2.0 * INSERTO_M3[2], material="fer_latao", corpo="drone",
                         ponto=k.ponto(fx, fy, zp).tolist(), eixo=k.dir((0.0, 0.0, -1.0)).tolist(),
                         peca="bandeja_fonte", inst=n_buck,
                         descricao=f"Inserto de latão M3 × {INSERTO_M3[0]:g} mm (cravar a quente no ABS)")
        for fx, fy in parafusos_base:
            fer.parafuso("drone", k.ponto(fx, fy, e_b).tolist(), k.dir((0.0, 0.0, -1.0)).tolist(), "M3",
                         aperto=e_b + (z_placa_topo - z_placa_fundo) / MM, cabeca="ISO 7380", porca="ISO 10511",
                         material_="aco_preto", peca="bandeja_fonte", inst=n_buck,
                         nota="base do buck (ABS): atravessa placa_inferior")
    b3.regista_impressa(
        ctx, "bandeja_fonte", n_buck, f"Base do buck XL4016 n.º {n_buck} (12 V dos motorredutores)", b3.Q_VIRADA,
        "Imprime-se com a face que encosta à placa na mesa (as colunas para cima, sem suportes). 4 colunas Ø8 com o "
        "furo Ø4,0 onde se crava a quente o inserto de latão M3 × 5,7; base de 2,4 mm com os 2 furos M3 que a prendem "
        "à placa de baixo.")
    return out


# Raspberry Pi Pico 2 (ficha: 51 × 21 × 1 mm, furos Ø2,1 a 47 × 11,4 mm, 40 castelações de 2,54 mm a 17,78 mm entre
# filas, micro-USB numa ponta, BOOTSEL, RP2350 QFN-60 7 × 7) — https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf
PICO = (51.0, 21.0, 1.0)
# placa de ligação (estimada): 62 × 32 mm, o Pico soldado pelas castelações e as fichas JST-GH de entrada por CIMA
# (largura 1,25·(n − 1) + 3,0 mm, 4,25 de fundo e de altura), 4 furos M2,5
LIGACAO = (62.0, 32.0, 1.6)


def _gh(n: int) -> float:
    return 1.25 * (n - 1) + 3.0


def _pico2(ctx, fund: Fundidor, n_pico: int, centro, z_topo_placa: float, esp_placa: float, ks: tuple) -> dict:
    """Controlador dos 2 braços de um lado (Raspberry Pi Pico 2) na sua PLACA DE LIGAÇÃO com as fichas JST-GH de
    entrada por cima (uma por sinal e braço: driver, servo, Hall, SPI do AS5048A, I²C do AS5600; UART ao FC e 5 V),
    sobre o SUPORTE IMPRESSO em ABS (`suporte_controlador` n: base de 2,4 mm, 4 colunas com insertos M2,5 × 4) na
    placa de cima, por cima dos drivers do seu lado. `ks` = (braço da frente, braço de trás) desse lado."""
    R = np.eye(3) if n_pico == 1 else _rz(math.pi)          # a fila «de fora» das fichas para o lado do braço
    k = Quadro(ctx, fund, "drone", (centro[0], centro[1], z_topo_placa), R)
    Lc, Wc, ec = LIGACAO
    Lp, Wp, ep = PICO
    e_b, h_col = 2.4, 4.0
    z_c = e_b + h_col                                         # face de baixo da placa de ligação
    z_p = z_c + ec                                            # face de baixo do Pico (soldado por cima)
    furos_c = [(sx * (0.5 * Lc - 2.5), sy * (0.5 * Wc - 2.5)) for sx in (1, -1) for sy in (1, -1)]
    parafusos_b = [(0.0, 8.0), (0.0, -8.0)]
    out = {}
    with ctx.peca("suporte_controlador", n_pico):
        base = g_placa_furos(-0.5 * Lc + 1.0, 0.5 * Lc - 1.0, -0.5 * Wc + 1.0, 0.5 * Wc - 1.0, 0.0, e_b,
                             [(x, y, 1.7) for x, y in parafusos_b], n=12)
        cols = []
        for fx, fy in furos_c:                                # colunas Ø6 com o furo Ø3,2 do inserto M2,5 × 4
            cols.append(mover(g_anel(1.6, 3.0, e_b, z_c, 16), None, (fx, fy, 0.0)))
        k.m(b3.MATERIAL_ABS, juntar(base, *cols), "suporte_controlador", n_pico)
        k.m("el_latao", juntar(*[mover(g_anel(1.0, 1.57, z_c - 4.0, z_c, 12), None, (fx, fy, 0.0)) for fx, fy in furos_c]),
            "suporte_controlador", n_pico)
    with ctx.peca("controlador_bracos", n_pico):
        k.m("el_pcb_preto", g_placa_furos(-0.5 * Lc, 0.5 * Lc, -0.5 * Wc, 0.5 * Wc, z_c, z_c + ec,
                                          [(fx, fy, 1.35) for fx, fy in furos_c], n=12), "controlador_bracos", n_pico)
        # Pico 2: placa verde com os 4 furos, castelações douradas, RP2350, flash, cristal, BOOTSEL, LED, micro-USB
        x0p = -0.5 * Lc                                       # a ponta do USB rente à borda −x da placa de ligação
        xc = x0p + 0.5 * Lp
        k.m("el_pcb_verde", g_placa_furos(x0p, x0p + Lp, -0.5 * Wp, 0.5 * Wp, z_p, z_p + ep,
                                          [(xc + sx * 23.5, sy * 5.7, 1.05) for sx in (1, -1) for sy in (1, -1)], n=10),
            "controlador_bracos", n_pico)
        cast = [g_caixa(xc + (i - 9.5) * 2.54 - 0.45, xc + (i - 9.5) * 2.54 + 0.45, sy * 0.5 * Wp - 0.6,
                        sy * 0.5 * Wp + 0.6, z_p - 0.03, z_p + ep + 0.03) for i in range(20) for sy in (1, -1)]
        swd = [g_caixa(x0p + Lp - 1.6, x0p + Lp - 0.4, yy - 0.5, yy + 0.5, z_p + ep, z_p + ep + 0.03)
               for yy in (-2.54, 0.0, 2.54)]
        k.m("el_ouro", juntar(*cast, *swd), "controlador_bracos", n_pico)
        zt = z_p + ep
        k.m("el_chip", juntar(g_caixa(xc + 1.5 - 3.5, xc + 1.5 + 3.5, -3.5, 3.5, zt, zt + 0.9),          # RP2350
                              g_caixa(xc + 8.0, xc + 11.0, -4.5, -1.5, zt, zt + 0.6),                  # flash
                              g_caixa(xc - 9.5, xc - 7.0, 3.0, 5.0, zt, zt + 0.9)), "controlador_bracos", n_pico)
        k.m("el_aco", juntar(g_caixa(xc - 6.0, xc - 3.4, -6.2, -4.0, zt, zt + 0.8),                      # cristal
                             g_caixa(x0p - 1.3, x0p + 5.4, -3.8, 3.8, zt, zt + 2.6)), "controlador_bracos", n_pico)
        k.m("el_abertura", g_caixa(x0p - 1.45, x0p - 1.3, -3.4, 3.4, zt + 0.5, zt + 2.0), "controlador_bracos", n_pico)
        k.m("el_rotulo_branco", juntar(g_caixa(x0p + 8.0, x0p + 11.5, 5.0, 8.0, zt, zt + 1.4),            # BOOTSEL
                                       g_caixa(xc + 14.0, xc + 21.0, -2.0, 2.0, zt, zt + 0.02)), "controlador_bracos",
            n_pico)
        k.m("el_led_verde", g_caixa(x0p + 6.5, x0p + 7.6, -7.2, -6.2, zt, zt + 0.5), "controlador_bracos", n_pico)
        k.m("el_ferrite", g_caixa(xc + 13.0, xc + 15.5, 4.0, 6.5, zt, zt + 1.2), "controlador_bracos", n_pico)
        # fichas JST-GH de entrada por cima: fila de fora (braços) e fila de dentro (encoders, UART, 5 V)
        ka, kb = ks
        fora = [(f"drv{ka}", 3), (f"servo{ka}", 3), (f"hall{ka}", 4), (f"hall{kb}", 4), (f"servo{kb}", 3),
                (f"drv{kb}", 3)]
        dentro = [(f"spi{ka}", 6), (f"i2c{ka}", 4), ("uart", 4), ("alimentacao", 2), (f"i2c{kb}", 4), (f"spi{kb}", 6)]
        zc_t = z_c + ec
        for fila, sy in ((fora, 1.0), (dentro, -1.0)):
            larg = sum(_gh(nv) for _nome, nv in fila) + 1.5 * (len(fila) - 1)
            xa = -0.5 * larg
            y0, y1 = sorted((sy * (0.5 * Wp + 0.9), sy * (0.5 * Wp + 0.9 + 4.25)))
            pinos = []
            for nome, nv in fila:
                w = _gh(nv)
                g = k.caixa(f"el_pico{n_pico}_{nome}", xa, xa + w, y0, y1, zc_t, zc_t + 4.25, "el_jst",
                            peca="controlador_bracos", inst=n_pico)
                if g is not None:
                    out[f"el_pico{n_pico}_{nome}"] = (k.ponto(xa + 0.5 * w, 0.5 * (y0 + y1), zc_t + 4.25),
                                                      k.dir((0.0, 0.0, 1.0)))
                for j in range(nv):
                    xj = xa + 1.5 + 1.25 * j
                    pinos.append(g_caixa(xj - 0.25, xj + 0.25, 0.5 * (y0 + y1) - 0.25, 0.5 * (y0 + y1) + 0.25,
                                         zc_t + 4.25, zc_t + 4.3))
                xa += w + 1.5
            k.m("el_ouro", juntar(*pinos), "controlador_bracos", n_pico)
    fer = _fer(ctx)
    if fer is not None:
        for fx, fy in furos_c:
            fer.parafuso("drone", k.ponto(fx, fy, z_c + ec).tolist(), k.dir((0.0, 0.0, -1.0)).tolist(), "M2.5",
                         aperto=ec, rosca_metida=4.0, cabeca="ISO 7380", porca=None, material_="aco_preto",
                         peca="controlador_bracos", inst=n_pico,
                         nota="placa de ligação do Pico 2: rosca no inserto de latão do suporte impresso")
            fer.registar(tipo="inserto", norma="inserto de latão M2.5", rosca="M2.5", comp_mm=4.0, d_ext_mm=3.2,
                         material="fer_latao", corpo="drone", ponto=k.ponto(fx, fy, z_c).tolist(),
                         eixo=k.dir((0.0, 0.0, -1.0)).tolist(), peca="suporte_controlador", inst=n_pico,
                         descricao="Inserto de latão M2,5 × 4 mm (cravar a quente no ABS)")
        for fx, fy in parafusos_b:
            fer.parafuso("drone", k.ponto(fx, fy, e_b).tolist(), k.dir((0.0, 0.0, -1.0)).tolist(), "M3",
                         aperto=e_b + esp_placa, cabeca="ISO 7380", porca="ISO 10511", material_="aco_preto",
                         peca="suporte_controlador", inst=n_pico,
                         nota="suporte do controlador dos braços (ABS): atravessa placa_superior")
    b3.regista_impressa(
        ctx, "suporte_controlador", n_pico, f"Suporte do controlador dos braços n.º {n_pico} (Pico 2)", b3.Q_IDENTIDADE,
        "Imprime-se como está (a base na mesa, as 4 colunas para cima). Base de 2,4 mm com 2 furos M3 para a placa de "
        "cima e 4 colunas Ø6 com o furo Ø3,2 dos insertos de latão M2,5 × 4 onde aperta a placa de ligação.")
    return out


def _controladores_bracos(ctx, fund: Fundidor) -> None:
    """Os 2 Raspberry Pi Pico 2 (catálogo `pico2_bracos`, peça `controlador_bracos` 1 = lado +y, 2 = lado −y) na placa
    de cima, por cima dos drivers do seu lado (|y| 61–91 mm, fora dos cantos e dos feixes dos ombros); a caixa física
    `el_pico2_bracos` (no topo da pilha) fica escondida."""
    g_sup = ctx.geom_existente("placa_superior")
    if g_sup is None:
        return
    zs_topo = float(g_sup.pos[2] + g_sup.size[2])
    esp = 2.0 * float(g_sup.size[2]) / MM
    cx = float(g_sup.pos[0])
    sinais = _sinais_rotores(ctx)
    ancoras = {}
    for n_pico, sy in ((1, 1.0), (2, -1.0)):
        do_lado = [k for k, (sx_, sy_) in enumerate(sinais, 1) if sy_ == sy]
        # o braço «a» (fichas do lado −x local) primeiro: −x do drone no Pico 1, +x no Pico 2 (rodado 180°)
        ks = tuple(sorted(do_lado, key=lambda k: sinais[k - 1][0] * (1.0 if n_pico == 1 else -1.0)))
        centro = (cx + (-2.5 if n_pico == 1 else 2.5) * MM, sy * 75.0 * MM)
        ancoras.update(_pico2(ctx, fund, n_pico, centro, zs_topo, esp, ks))
    notas = ctx.registo.notas.setdefault("ancoras", {})
    for nome, (p, d) in ancoras.items():
        notas[nome] = {"corpo": "drone", "ponto": [float(x) for x in p], "direcao": [float(x) for x in d]}
    _esconder(ctx, "el_pico2_bracos")


def _fonte_atuadores(ctx, fund: Fundidor, z_placa_topo: float | None, z_placa_fundo: float | None) -> None:
    """Energia dos atuadores do mecanismo de motorredutores (catálogo → `fonte_servos`), fora dos cantos (atuadores) e
    dos percursos dos feixes dos ombros na placa de cima (`fios`): por baixo da placa de baixo, de cada lado do pack,
    um buck XL4016 (motorredutores de 12 V: um por PAR de ombros do mesmo lado, 2 × 2,37 A de pico num buck de 8 A)
    com os 2 drivers DRV8871 desse lado, um de cada lado do buck (bornes virados para o ombro); o UBEC dos 4 servos
    dos cotovelos em cima da placa de cima, atrás da pilha, deitado ao longo de x (entrada −x, saída +x)."""
    g_sup = ctx.geom_existente("placa_superior")
    if g_sup is None or z_placa_topo is None or z_placa_fundo is None:
        return
    zs_topo = float(g_sup.pos[2] + g_sup.size[2])
    zs_fundo = float(g_sup.pos[2] - g_sup.size[2])
    cx_s = float(g_sup.pos[0])
    esp_inf = (z_placa_topo - z_placa_fundo) / MM
    b3.material_abs(ctx)
    ancoras = {}
    y_b = 0.5 * BUCK_DIMS[1] + 1.0 + 58.5                    # a base começa a 58,5 mm do eixo: passa os pés da
    #                                                          travessa dos sensores (até 57,4 mm do lado do P+ do pack)
    x_d = 0.5 * BUCK_DIMS[0] + 1.0 + 0.5 + 0.5 * DRV_B + 1.0  # o suporte do driver a 0,5 mm da base do buck
    for k_drv, (sx, sy) in enumerate(_sinais_rotores(ctx), 1):
        # (a, b, z) → (sx·y, sx·x, −z): b (bornes) para o lado do ombro, z para baixo (pendurado)
        R = np.array([[0.0, sx, 0.0], [sx, 0.0, 0.0], [0.0, 0.0, -1.0]])
        centro = (cx_s + sx * x_d * MM, sy * y_b * MM)
        ancoras.update(_drv8871(ctx, fund, k_drv, centro, z_placa_fundo, R, esp_inf, "placa_inferior"))
        b3.regista_impressa(
            ctx, "suporte_driver", k_drv, f"Suporte do driver DRV8871 do ombro {k_drv}", b3.Q_VIRADA,
            "Imprime-se com a face que encosta à placa na mesa (as 2 paredes para cima): base de 2,4 mm com 2 orelhas M3 "
            "e 2 paredes de 2 mm que centram a placa do driver, colada com espuma de 2 mm (a placa não tem furos de "
            "fixação). Pendura-se por baixo da placa de baixo, ao lado do buck.")
    ancoras.update(_ubec(ctx, fund, (cx_s - 69.5 * MM, 0.0), zs_topo, zs_fundo))
    if _tensao_ombro(ctx.hw) <= 15.0:
        for n_b, sy in ((1, 1.0), (2, -1.0)):
            ancoras.update(_buck_xl4016(ctx, fund, n_b, (cx_s, sy * y_b * MM), z_placa_fundo, z_placa_topo))
    notas = ctx.registo.notas.setdefault("ancoras", {})
    for nome, (p, d) in ancoras.items():
        notas[nome] = {"corpo": "drone", "ponto": [float(x) for x in p], "direcao": [float(x) for x in d]}
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
    b3.materiais(ctx)
    fund = Fundidor(ctx, "el")
    hw = ctx.hw
    placa = _info(ctx, "placa")
    z_placa_topo = None if placa is None else float(placa[0][2] + placa[1][2])
    z_placa_fundo = None if placa is None else float(placa[0][2] - placa[1][2])
    ids = {c.id for c in hw.consumidores}
    rpi = _info(ctx, "el_rpi5") if "rpi5" in ids else None
    fc = _info(ctx, "el_fc_h7") if "fc_h7" in ids else None
    pdb = _info(ctx, "el_cablagem") if "cablagem" in ids else None
    port = _info(ctx, "el_arduino_portenta_h7") if "arduino_portenta_h7" in ids else None
    sens = hw.sensores or {}
    com_imu = "imu" in sens

    def fundo(info):
        return float(info[0][2] - info[1][2])

    abs_ = b3.frame_abs(hw)
    if abs_:
        b3.material_abs(ctx)
    # ponte do FC sobre o Pi: em pilares M-F de 16 mm (se couber entre o Pi e a placa de cima dele); no frame ABS a
    # ponte é IMPRESSA (3,4 mm, pilares de 15 mm, cabeças dos M3 em contrafuros)
    z_ponte, centro_pilha, cotas_abs = None, None, None
    if rpi is not None and (fc is not None or pdb is not None):
        alvo = fc if fc is not None else pdb
        if abs_ and fc is not None:
            cotas_abs = _cotas_ponte_abs(rpi, fc)
        if cotas_abs is not None:
            z_ponte, centro_pilha = cotas_abs[1], alvo[0]
        else:
            z_pi_topo = fundo(rpi) + 1.6 * MM
            z_cand = z_pi_topo + 16.0 * MM
            if z_cand + 1.5 * MM <= fundo(alvo) - (0.9 if fc is not None else 0.5) * MM + 1e-9:
                z_ponte, centro_pilha = z_cand, alvo[0]
    if rpi is not None:
        if cotas_abs is not None:
            _fazer("Raspberry Pi 5", _rpi5, ctx, fund, rpi, z_placa_topo, z_placa_fundo, z_ponte,
                   ESP_PONTE_ABS - cotas_abs[3], 8.0, "ponte_fc")
            _fazer("ponte do FC (ABS)", _ponte_fc_abs, ctx, fund, rpi, centro_pilha, cotas_abs[0], cotas_abs[3])
        else:
            _fazer("Raspberry Pi 5", _rpi5, ctx, fund, rpi, z_placa_topo, z_placa_fundo, z_ponte)
            if z_ponte is not None:
                _fazer("ponte do FC", _ponte_fc, ctx, fund, rpi, centro_pilha, z_ponte)
    if port is not None:
        _fazer("Portenta H7", _portenta, ctx, fund, port, z_placa_topo, z_placa_fundo)
    if fc is not None:
        _fazer("FC H7", _fc_h7, ctx, fund, fc, com_imu, _atuadores_dc(hw))
    if pdb is not None:
        _fazer("placa de energia", _pdb, ctx, fund, pdb, "monitor" in sens)
        if fc is None and com_imu:
            c, h = pdb
            _fazer("IMU avulsa", _imu_avulsa, ctx, fund, (c[0], c[1], c[2] - h[2]), 5.0, 9.0, 1.6)
    # pilha M3 (ponte → FC → placa de energia), ou da placa de baixo (sem ponte)
    if fc is not None or pdb is not None:
        c_p = (fc if fc is not None else pdb)[0]
        z_fc = fundo(fc) if fc is not None else None
        z_pdb = fundo(pdb) if pdb is not None else None
        if cotas_abs is not None:
            _fazer("pilha M3", _pilha_m3, ctx, fund, c_p, cotas_abs[0] + ESP_PONTE_ABS * MM,
                   cotas_abs[0] + CONTRAFURO_M3[1] * MM, z_fc, z_pdb, "a ponte do FC (ABS: a cabeça no contrafuro)")
        elif z_ponte is not None:
            _fazer("pilha M3", _pilha_m3, ctx, fund, c_p, z_ponte + 1.5 * MM, z_ponte, z_fc, z_pdb, "a ponte do FC")
        elif z_placa_fundo is not None and rpi is None:
            _fazer("pilha M3", _pilha_m3, ctx, fund, c_p, z_placa_topo, z_placa_fundo, z_fc, z_pdb,
                   "a placa_inferior")

    # ESC (individuais ao longo dos braços ou 4-em-1 no centro)
    if hw.esc.dados.get("formato", "4em1") == "4em1":
        if ctx.geom_existente("esc") is not None:
            _fazer("ESC 4-em-1", _esc_4em1, ctx, fund, z_placa_topo, z_placa_fundo)
    else:
        for i in range(1, 5):
            if ctx.geom_existente(f"esc{i}") is not None:
                _fazer(f"ESC {i}", _esc_air40a, ctx, fund, i)

    # câmara do nariz
    cam = _info(ctx, "camera") if hw.camera is not None else None
    if cam is not None:
        tipo = str(hw.camera.dados.get("tipo", ""))
        if tipo == "modulo_camera_csi":
            _fazer("câmara CSI", _camera_csi, ctx, fund, cam, z_placa_topo, abs_)
        elif tipo == "modulo_camera_dvp":
            _fazer("câmara DVP", _camera_dvp, ctx, fund, cam, z_placa_topo, abs_)
    if ctx.geom_existente("fonte_servos") is not None:
        if _atuadores_dc(hw):
            _fazer("energia dos atuadores", _fonte_atuadores, ctx, fund, z_placa_topo, z_placa_fundo)
        else:
            _fazer("regulador 24 V", _fonte_servos, ctx, fund, z_placa_topo, z_placa_fundo)
    if ctx.geom_existente("el_pico2_bracos") is not None:
        _fazer("controladores dos braços (Pico 2)", _controladores_bracos, ctx, fund)

    # baterias (pack do build + variantes do painel), XT90, cintas, tapete, sensores de baixo — DEPOIS das outras
    # peças: o tapete leva furos onde ficam as porcas/cabeças que elas registaram por baixo da placa
    res = {}
    try:
        res = b3.montar(ctx, fund)
    except Exception as e:  # noqa: BLE001
        warnings.warn(f"detalhes/eletronica: bateria não desenhada ({type(e).__name__}: {e})", stacklevel=2)
    fund.fechar()
    try:
        b3.registar(ctx, fund, res)
    except Exception as e:  # noqa: BLE001
        warnings.warn(f"detalhes/eletronica: registo da bateria falhou ({type(e).__name__}: {e})", stacklevel=2)
    # o PCB invisível da placa de energia (âncora) e o envelope do USB-C: sem material visível
    for nome in ("el_pdb_pcb", "rpi5_usbc"):
        g = ctx.geom_existente(nome)
        if g is not None:
            g.material = ""
            g.rgba = [0.0, 0.0, 0.0, 0.0]
