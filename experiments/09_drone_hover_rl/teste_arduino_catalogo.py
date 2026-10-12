#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_arduino_catalogo.py — PROVA das peças ARDUINO do catálogo e do build novo.

Contexto (dono, 2026-10-12): TUDO corre num Arduino (estimador + estabilização + movimento + olhar para um círculo).
A pesquisa (`pesquisas/2026-10-12-para-um-quadricoptero-grande-*.md`, Q5/Q6) concluiu que a Pi Camera Module 3 (CSI-2)
não existe em Arduino e recomendou o Portenta H7 + Vision Shield. O catálogo ganhou as peças REAIS (Portenta H7, Nicla
Vision, GIGA R1, Vision Shield HM0360/HM01B0) e o build `endurance_15pol_arduino` (o p50b com o computador trocado).

O que se prova (tudo por execução; temporários SÓ em `$TMPDIR`):

  §1 PEÇAS vs DATASHEETS — os números do catálogo batem com os das fichas oficiais da Arduino/Himax (guardados AQUI como
     oráculo, independentes do JSON): clocks (M7 480 / M4 240 MHz), FPU (M7 dupla, M4 simples), flash/RAM/SDRAM/QSPI, PWM,
     câmara paralela de 8 bit, corrente máxima, IMU do Nicla, sensores das shields (resolução, píxel, formato óptico), mono
     vs RGB, lente/FoV, fontes e razões de tudo o que é ESTIMADO (massa do Portenta, FoV das shields…);
  §2 CÂMARA × EMULADOR — o `lab/camera_rpi.py` aceita as câmaras novas: catálogo = módulos campo a campo, modos reais
     (fps ≤ máximo do sensor), FoV pela fórmula fechada, JPEG MONO de 8 bit com as dimensões da saída, recusa de modos
     do outro mundo, latência do caminho DCMI, sem custo de Pi 5, e a Pi Camera EXATAMENTE como era;
  §3 BUILD — `endurance_15pol_arduino` = p50b com SÓ o computador/câmara trocados; massa, potência e autonomia pelo modelo;
     a planta constrói e paira; `hardware.py usar` numa CÓPIA segura; o build ATIVO continua o p50b;
  §4 MUTAÇÕES (`--mutacao`) — o teste NÃO é tautológico: mutações em CÓPIAS das fontes (nunca nas reais) têm de FALHAR as
     checagens certas.

Uso:
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_arduino_catalogo.py            # §1–§3
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_arduino_catalogo.py --mutacao  # §4
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_arduino_catalogo.py --so-espec # §1 + §2 (espec.)
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_arduino_catalogo.py --so-pecas # §1–§3 sem CLI
    ... --fontes DIR   # o MESMO teste contra uma cópia das fontes (é o que o §4 usa)
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def _raiz_das_fontes(argv: list[str]) -> Path:
    """`--fontes DIR` escolhe a raiz de onde se importam `lab/` e os catálogos (antes de importar o que quer que seja)."""
    for i, a in enumerate(argv):
        if a == "--fontes" and i + 1 < len(argv):
            return Path(argv[i + 1]).resolve()
        if a.startswith("--fontes="):
            return Path(a.split("=", 1)[1]).resolve()
    return _REPO


RAIZ = _raiz_das_fontes(sys.argv)
_EXP = RAIZ / "experiments" / "09_drone_hover_rl"
sys.path[:0] = [str(RAIZ), str(_EXP)]
os.environ.setdefault("MUJOCO_GL", "egl")          # render sem janela (ANTES de importar o mujoco)

import mujoco
import numpy as np

from lab import camera_rpi as cam
from lab import drone_rpi as dr
from lab.drone_rpi import componentes as comp

CATALOGO = RAIZ / "models" / "drone_rpi" / "componentes.json"
BUILDS = RAIZ / "models" / "drone_rpi" / "builds.json"
BUILD_NOVO = "endurance_15pol_arduino"
BUILD_ATIVO = "endurance_15pol_p50b"
TOL_S = 1e-9

# ============================================================================================ ORÁCULO (as fichas)
# Números copiados das fichas oficiais (lidas em 2026-10-12) — INDEPENDENTES do JSON, para o teste não ser tautológico.
#   [H7]  Portenta H7 collective datasheet ABX00042/45/46 (05/11/2025): §1.1 MCU, §1.2 memórias, §1.4 HD, §1.7 MKR, §2.2
#   [VS]  Portenta Vision Shield Rev 2 collective datasheet ASX00021/26 (18/02/2026): §2.1
#   [NV]  Nicla Vision datasheet ABX00051 (07/10/2026): features, §2.2
#   [GG]  GIGA R1 WiFi datasheet ABX00063 (03/07/2026): features
#   [HX]  Himax HM0360/HM01B0 (páginas oficiais) + módulos de referência HM0360-MWA-00FW703 / HM01B0-MNA-00FT870 (lente)
H7 = {"m7_mhz": 480, "m4_mhz": 240, "flash_kb": 2048, "ram_kb": 1024, "sdram_mb": 8, "qspi_mb": 16, "pwm_hd": 10,
      "pwm_mkr": 7, "cam_bits": 8, "cam_mhz": 80, "pico_ma": 230, "pico_v": 5.0, "dims": (66.04, 25.4)}
SHIELD = {"massa_g": 8.0, "dims": (66.04, 25.4)}
HM0360 = {"res": (640, 480), "matriz": (656, 496), "pixel_um": 3.6, "diag_mm": 2.88, "fps": 60.0,
          "fov": {"diag": 85.0, "horizontal": 70.1, "vertical": 55.4}, "focal_mm": 1.56, "f_stop": 2.4}
HM01B0 = {"res": (320, 320), "pixel_um": 3.6, "diag_mm": 1.63, "fps_matriz": 51.0, "fps_qvga": 60.0, "fps_bin": 120.0,
          "fov": {"diag": 115.0, "horizontal": 87.0, "vertical": 87.0}, "focal_mm": 0.66, "f_stop": 2.4}
NICLA = {"m7_mhz": 480, "m4_mhz": 240, "imu": "LSM6DSOX", "gc2145_pixel_um": 1.75, "gc2145_focal_mm": 2.2,
         "gc2145_f": 2.2, "gc2145_angulo": 80, "captura_ma": 105, "dims": (22.86, 22.86)}
GIGA = {"sdram_mb": 8, "qspi_mb": 16, "pwm_datasheet": 13, "pwm_loja": 12, "conector": "20 pinos",
        "ov7675_fov_diag": 63.9, "ov7675_fps": 15, "ov7675_focal_mm": 1.75, "dims": (101.52, 53.34)}
MODOS_ESPERADOS = {
    "portenta_vision_shield_hm0360": {"VGA60": ((640, 480), 60.0), "QVGA60": ((320, 240), 60.0),
                                      "QVGA30": ((320, 240), 30.0)},
    "portenta_vision_shield_hm01b0": {"320x320p45": ((320, 320), 45.0), "QVGA60": ((320, 240), 60.0),
                                      "QVGA30": ((320, 240), 30.0), "QQVGA120": ((160, 120), 120.0)},
}
# os 7 modos da Pi Camera (IMX708) como eram antes das câmaras Arduino — a Pi não pode mudar
MODOS_PI = {"1080p50": ((1920, 1080), 50.0, (0, 0, 4608, 2592)), "720p100": ((1280, 720), 100.0, (768, 432, 3072, 1728)),
            "480p120": ((640, 480), 120.0, (768, 432, 3072, 1728)),
            "2304x1296p56": ((2304, 1296), 56.03, (0, 0, 4608, 2592)),
            "1536x864p120": ((1536, 864), 120.13, (768, 432, 3072, 1728)),
            "4608x2592p14": ((4608, 2592), 14.35, (0, 0, 4608, 2592)),
            "2304x1296p30hdr": ((2304, 1296), 30.0, (0, 0, 4608, 2592))}


# ------------------------------------------------------------------------------------------------ checagens
class Checagens:
    """Acumulador de checagens: uma linha por checagem (com o detalhe medido) e as falhas à parte."""

    def __init__(self) -> None:
        self.linhas: list[str] = []
        self.falhas: list[str] = []

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.linhas.append(nome)
        if not cond:
            self.falhas.append(nome)
        print(f"        [{'OK  ' if cond else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""), flush=True)
        return bool(cond)


def _titulo(texto: str) -> None:
    print(f"\n[teste] {texto}", flush=True)


def _recusa(funcao) -> bool:
    try:
        funcao()
    except ValueError:
        return True
    except Exception:  # noqa: BLE001  (qualquer outro erro NÃO conta como recusa certa)
        return False
    return False


def _cat() -> dict:
    return json.loads(CATALOGO.read_text(encoding="utf-8"))


def _builds() -> dict:
    return json.loads(BUILDS.read_text(encoding="utf-8"))


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _tem_fontes(peca: dict) -> bool:
    fontes = peca.get("fontes") or []
    return len(fontes) >= 1 and any(str(f).startswith("http") for f in fontes) and bool(peca.get("confianca"))


# ================================================================================================= §1 PEÇAS
def checa_pecas(c: Checagens) -> None:
    _titulo("§1 peças vs datasheets: Portenta H7, Nicla Vision, GIGA R1 e as câmaras da Vision Shield")
    cat = _cat()
    ele, cams = cat["eletronica"], cat["cameras"]
    h7, nicla, giga = ele["arduino_portenta_h7"], ele["arduino_nicla_vision"], ele["arduino_giga_r1"]
    mcu = h7["mcu"]
    m7, m4 = mcu["nucleo_m7"], mcu["nucleo_m4"]

    c.ok("[§1] Portenta H7: clocks M7 480 MHz e M4 240 MHz (ficha ABX00042 §1.1)",
         m7["clock_max_mhz"] == H7["m7_mhz"] and m4["clock_max_mhz"] == H7["m4_mhz"],
         f"M7 {m7['clock_max_mhz']} MHz · M4 {m4['clock_max_mhz']} MHz · (OpenMV: {m7['clock_openmv_mhz']}/"
         f"{m4['clock_openmv_mhz']} MHz)")
    c.ok("[§1] Portenta H7: FPU de DUPLA precisão no M7 e de SIMPLES no M4 (o M4 é FPv4-SP; a ficha só diz 'with FPU')",
         m7["fpu"] == "dupla precisão" and m4["fpu"] == "simples precisão" and m4["art_accelerator"] is True
         and m7["cache_l1_kb"] == {"dados": 16, "instrucoes": 16},
         f"M7 {m7['fpu']} · M4 {m4['fpu']} · cache L1 M7 {m7['cache_l1_kb']}")
    c.ok("[§1] Portenta H7: memórias 2 MB flash + 1 MB RAM + 8 MB SDRAM + 16 MB QSPI (ficha §1.1/§1.2)",
         (mcu["flash_kb"], mcu["ram_kb"], mcu["sdram_mb"], mcu["flash_qspi_mb"])
         == (H7["flash_kb"], H7["ram_kb"], H7["sdram_mb"], H7["qspi_mb"]),
         f"flash {mcu['flash_kb']} kB · RAM {mcu['ram_kb']} kB · SDRAM {mcu['sdram_mb']} MB · QSPI "
         f"{mcu['flash_qspi_mb']} MB")
    c.ok("[§1] Portenta H7: 10 PWM no conector HD + 7 no cabeçalho MKR; câmara paralela de 8 bit a 80 MHz; JPEG por "
         "hardware; SEM IMU (ficha §1.4/§1.7)",
         mcu["pwm"] == {"conector_hd": H7["pwm_hd"], "cabecalho_mkr": H7["pwm_mkr"]}
         and mcu["camera_interface"]["bits"] == H7["cam_bits"] and mcu["camera_interface"]["clock_max_mhz"] == H7["cam_mhz"]
         and mcu["jpeg_hardware"] is True and mcu["imu_integrada"] is False,
         f"PWM {mcu['pwm']} · câmara {mcu['camera_interface']} · IMU integrada {mcu['imu_integrada']}")
    pot = h7["potencia_w"]
    pico_ficha = H7["pico_ma"] / 1000.0 * H7["pico_v"]
    c.ok("[§1] Portenta H7: consumo repouso < voo ≤ pico e pico = 230 mA × 5 V = 1,15 W (ficha §2.2); repouso e voo "
         "são as leituras MEDIDAS pelo MDPI (0,134 A × 4,93 V; 0,206 A × 4,87 V)",
         abs(pot["pico"] - pico_ficha) < 1e-9 and pot["repouso"] < pot["voo"] <= pot["pico"]
         and abs(pot["repouso"] - 0.134 * 4.93) < 0.005 and abs(pot["voo"] - 0.206 * 4.87) < 0.005,
         f"repouso {pot['repouso']} W · voo {pot['voo']} W · pico {pot['pico']} W (ficha {pico_ficha:.2f} W)")
    c.ok("[§1] Portenta H7: orçamento de ciclos por passo de 500 Hz = clock ÷ 500 (M7 960 000 · M4 480 000)",
         h7["ciclos_por_passo_500hz"] == {"m7": m7["clock_max_mhz"] * 1_000_000 // 500,
                                          "m4": m4["clock_max_mhz"] * 1_000_000 // 500},
         f"{h7['ciclos_por_passo_500hz']}")
    est = h7["estimado"]
    c.ok("[§1] Portenta H7: massa e consumo em voo são ESTIMADOS e DITOS (razão + fonte), nunca o número de expedição "
         "(0,2 kg da loja, 158,8 g da Mouser)",
         5.0 <= h7["massa_g"] <= 15.0 and "massa_g" in est and "EXPEDIÇÃO" in est["massa_g"]
         and "potencia_w.voo" in est and "estimado" in h7["confianca"].lower(),
         f"massa {h7['massa_g']} g · estimado: {sorted(est)}")

    ni = nicla["mcu"]
    gc = nicla["camera_integrada"]
    c.ok("[§1] Nicla Vision: mesmo M7/M4 (480/240 MHz, FPU dupla/simples), 2 MB flash + 1 MB RAM; IMU LSM6DSOX "
         "(±2…16 g, ±125…2000 dps); captura = 105 mA (ficha §2.2)",
         ni["nucleo_m7"]["clock_max_mhz"] == NICLA["m7_mhz"] and ni["nucleo_m4"]["clock_max_mhz"] == NICLA["m4_mhz"]
         and ni["nucleo_m7"]["fpu"] == "dupla precisão" and (ni["flash_kb"], ni["ram_kb"]) == (2048, 1024)
         and nicla["imu"]["modelo"] == NICLA["imu"] and nicla["imu"]["acelerometro_g"] == [2, 4, 8, 16]
         and nicla["imu"]["giroscopio_dps"] == [125, 250, 500, 1000, 2000]
         and abs(nicla["potencia_w"]["voo"] - NICLA["captura_ma"] / 1000.0 * 3.7) < 0.01,
         f"M7 {ni['nucleo_m7']['clock_max_mhz']} MHz · IMU {nicla['imu']['modelo']} · voo {nicla['potencia_w']['voo']} W")
    c.ok("[§1] Nicla Vision: câmara GC2145 de 2 MP RGB (píxel 1,75 µm, f = 2,2 mm, f/2,2, 80°) — a única das placas com "
         "lente na ficha; massa 2 g e 22,86×22,86 mm",
         gc["mp"] == 2 and gc["rgb"] is True and gc["pixel_um"] == NICLA["gc2145_pixel_um"]
         and gc["lente"] == {"focal_mm": NICLA["gc2145_focal_mm"], "f_stop": NICLA["gc2145_f"]}
         and gc["angulo_de_visao_graus"] == NICLA["gc2145_angulo"] and nicla["massa_g"] == 2
         and tuple(nicla["dims_mm"][:2]) == NICLA["dims"],
         f"GC2145 {gc['mp']} MP · {gc['lente']} · {gc['angulo_de_visao_graus']}° · {nicla['massa_g']} g")
    gi = giga["mcu"]
    ov = giga["camera_suportada"]["modulo_loja_ov7675"]
    c.ok("[§1] GIGA R1: mesmo SoC + 8 MB SDRAM + 16 MB QSPI; PWM 13 na ficha vs 12 na loja (a discrepância fica "
         "registada); conector de câmara Arducam de 20 pinos; massa ESTIMADA pelo Mega (37 g)",
         (gi["sdram_mb"], gi["flash_qspi_mb"]) == (GIGA["sdram_mb"], GIGA["qspi_mb"])
         and gi["pwm"] == {"datasheet": GIGA["pwm_datasheet"], "loja_e_docs": GIGA["pwm_loja"]}
         and GIGA["conector"] in giga["camera_suportada"]["conector"] and giga["massa_g"] == 37
         and "massa_g" in giga["estimado"] and "Mega" in giga["estimado"]["massa_g"],
         f"SDRAM {gi['sdram_mb']} MB · PWM {gi['pwm']} · {giga['camera_suportada']['conector']} · {giga['massa_g']} g")
    c.ok("[§1] GIGA R1: câmara da loja OV7675 = RGB 640×480 a 15 fps, f = 1,75 mm, 63,9° na diagonal (lenta para 25–30 Hz)",
         ov["rgb"] is True and ov["fps"] == GIGA["ov7675_fps"] and ov["fov_diag_graus"] == GIGA["ov7675_fov_diag"]
         and ov["focal_mm"] == GIGA["ov7675_focal_mm"] and ov["pixel_px"] == [640, 480],
         f"{ov}")
    nucleos = [(p["mcu"]["nucleo_m7"]["clock_max_mhz"], p["mcu"]["nucleo_m4"]["clock_max_mhz"], p["mcu"]["flash_kb"],
                p["mcu"]["ram_kb"]) for p in (h7, nicla, giga)]
    c.ok("[§1] as 3 placas partilham o MESMO STM32H747: (480 MHz, 240 MHz, 2048 kB, 1024 kB) — consistência cruzada",
         len(set(nucleos)) == 1 and nucleos[0] == (480, 240, 2048, 1024), f"{nucleos}")

    s0, s1 = cams["portenta_vision_shield_hm0360"], cams["portenta_vision_shield_hm01b0"]
    c.ok("[§1] Vision Shield HM0360: 640×480 (matriz 656×496), píxel 3,6 µm, 1/6″ (2,88 mm), 0,3072 MP, 60 FPS máx.; "
         "8 g e 66,04×25,40 mm (ficha Rev 2 + Himax)",
         tuple(s0["resolucao_px"]) == HM0360["res"] and tuple(s0["matriz_ativa_px"]) == HM0360["matriz"]
         and s0["pixel_um"] == HM0360["pixel_um"] and "1/6" in s0["optico"] and "2,88" in s0["optico"]
         and abs(s0["mp"] - 640 * 480 / 1e6) < 1e-9 and s0["massa_g"] == SHIELD["massa_g"]
         and tuple(s0["dims_mm"][:2]) == SHIELD["dims"]
         and max(m["fps_sensor_max"] for m in s0["modos_sensor"]) == HM0360["fps"],
         f"{s0['resolucao_px']} · {s0['pixel_um']} µm · {s0['optico']} · {s0['massa_g']} g")
    c.ok("[§1] Vision Shield HM01B0: 320×320, píxel 3,6 µm, 1/11″ (1,63 mm), 0,1024 MP; matriz inteira ≤ 51 fps, "
         "janela QVGA 60 fps, binning 2×2 120 fps — a ficha da shield ('320×320 QVGA 60FPS') junta duas coisas",
         tuple(s1["resolucao_px"]) == HM01B0["res"] and s1["pixel_um"] == HM01B0["pixel_um"] and "1/11" in s1["optico"]
         and "1,63" in s1["optico"] and abs(s1["mp"] - 320 * 320 / 1e6) < 1e-9
         and {m["id"]: m["fps_sensor_max"] for m in s1["modos_sensor"]}
         == {"320x320p45": HM01B0["fps_matriz"], "QVGA60": HM01B0["fps_qvga"], "QVGA30": HM01B0["fps_qvga"],
             "QQVGA120": HM01B0["fps_bin"]},
         f"{ {m['id']: m['fps_sensor_max'] for m in s1['modos_sensor']} }")
    pi = [cams["raspberry_camera_module_3"], cams["raspberry_camera_module_3_wide"]]
    c.ok("[§1] MONO vs RGB: as duas câmaras da shield são monocromáticas de 8 bit (RAW8, sem ISP) e as Pi Camera "
         "continuam RGB/RAW10 (sem a chave `mono`)",
         all(s["mono"] is True and "RAW8" in s["formato_sensor"] and "sem Bayer" in s["formato_sensor"]
             for s in (s0, s1)) and all("mono" not in p and "RAW10" in p["formato_sensor"] for p in pi),
         f"shield: {s0['formato_sensor']} · Pi: {pi[0]['formato_sensor']}")
    c.ok("[§1] interface: as shields são DVP paralelo → DCMI (sem CSI-2) e a Himax dá '<2 ms' de arranque de quadro no "
         "HM0360; as Pi Camera são MIPI CSI-2",
         all("DVP paralelo" in s["interface"] and "DCMI" in s["interface"] and "sem CSI-2" in s["interface"]
             for s in (s0, s1)) and s0["latencia"]["inicio_quadro_ms_max"] == 2.0
         and s1["latencia"]["inicio_quadro_ms_max"] is None and all("CSI-2" in p["interface"] for p in pi),
         f"HM0360 {s0['latencia']['inicio_quadro_ms_max']} ms · HM01B0 {s1['latencia']['inicio_quadro_ms_max']}")
    c.ok("[§1] lente das shields: a Arduino NÃO a publica — FoV/focal vêm dos módulos de referência da Himax "
         "(HM0360-MWA: 70,1°×55,4° f 1,56 mm; HM01B0-MNA: 87°×87° f 0,66 mm, f/2,4) e estão marcados ESTIMADOS",
         s0["fov_graus"] == HM0360["fov"] and s0["lente"]["focal_mm"] == HM0360["focal_mm"]
         and s0["lente"]["f_stop"] == HM0360["f_stop"] and s1["fov_graus"] == HM01B0["fov"]
         and s1["lente"]["focal_mm"] == HM01B0["focal_mm"] and s1["lente"]["f_stop"] == HM01B0["f_stop"]
         and all("fov_graus" in s["estimado"] and "NÃO publica" in s["estimado"]["fov_graus"] for s in (s0, s1)),
         f"HM0360 {s0['fov_graus']} · HM01B0 {s1['fov_graus']}")
    novas = [ele[k] for k in ("arduino_portenta_h7", "arduino_nicla_vision", "arduino_giga_r1")] + [s0, s1]
    razoes = [r for p in novas for r in p.get("estimado", {}).values()]
    c.ok("[§1] TODAS as 5 peças novas têm fontes (URL) e confiança; todo campo ESTIMADO traz uma razão com mais de 40 "
         "caracteres (a fonte e o porquê)",
         all(_tem_fontes(p) for p in novas) and len(razoes) >= 9 and all(len(str(r)) > 40 for r in razoes),
         f"{len(novas)} peças · {len(razoes)} campos estimados com razão")


# ======================================================================================= §2 CÂMARA × EMULADOR
def _modelo_pequeno(com_marcador: bool = False):
    """(model, data) pequeno com a câmara `fpv` — para as provas de especificação/pipeline (como no teste_fpv)."""
    spec = mujoco.MjSpec()
    spec.compiler.degree = False
    spec.worldbody.add_geom(type=mujoco.mjtGeom.mjGEOM_PLANE, size=[20, 20, 0.1])
    corpo = spec.worldbody.add_body(name="drone", pos=[0, 0, 1.5])
    corpo.add_freejoint()
    corpo.add_geom(type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.1, 0.1, 0.03], mass=1.0)
    cam.add_camera_fpv(corpo, (0.15, 0.0, 0.03), 55.4, nome="fpv")
    if com_marcador:
        cam.adicionar_ponto(spec)
    model = spec.compile()
    data = mujoco.MjData(model)
    if com_marcador:
        cam.posicionar_ponto(model, data, [2.15, 0.0, 1.53])
    mujoco.mj_forward(model, data)
    return model, data


def checa_especificacao(c: Checagens) -> None:
    _titulo("§2a câmara × emulador (especificação, sem render): catálogo = módulos, modos reais, FoV, latência")
    cat = _cat()
    cams = cat["cameras"]
    novos = ("portenta_vision_shield_hm0360", "portenta_vision_shield_hm01b0")
    for pid in novos:
        peca = cams[pid]
        mid = cam.modulo_da_peca(pid)
        m = cam.MODULOS[mid]
        iguais = (
            abs(float(peca["massa_g"]) - float(m["massa_g"])) < TOL_S
            and [float(v) for v in peca["dims_mm"]] == [float(v) for v in m["dims_mm"]]
            and {k: float(v) for k, v in peca["fov_graus"].items()} == {k: float(v) for k, v in m["fov_graus"].items()}
            and peca["sensor"] == m["sensor"] and abs(float(peca["mp"]) - float(m["mp"])) < TOL_S
            and abs(float(peca["pixel_um"]) - float(m["pixel_um"])) < TOL_S
            and list(peca["resolucao_px"]) == list(m["resolucao_px"])
            and float(peca["lente"]["focal_mm"]) == float(m["lente"]["focal_mm"])
            and float(peca["lente"]["f_stop"]) == float(m["lente"]["f_stop"])
            and m["peca_catalogo"] == pid and m["plataforma"] == "arduino" and m["mono"] is True
            and peca["mono"] is True)
        c.ok(f"[§2] catálogo × MODULOS: '{pid}' ↔ '{mid}' dizem o MESMO campo a campo (massa, dims, FoV, sensor, MP, "
             f"píxel, resolução, lente)", iguais, f"{peca['sensor']} · {peca['fov_graus']} · {peca['massa_g']} g")
    for pid in novos:
        mid = cam.modulo_da_peca(pid)
        cat_modos = {m["id"]: m for m in cams[pid]["modos_sensor"]}
        emu_modos = cam.modos_do_modulo(mid)
        iguais = (set(cat_modos) == set(emu_modos) == set(MODOS_ESPERADOS[pid])
                  and all(tuple(cat_modos[i]["resolucao_px"]) == emu_modos[i].saida == emu_modos[i].sensor
                          and cat_modos[i]["fps"] == emu_modos[i].fps and tuple(cat_modos[i]["crop_px"]) == emu_modos[i].crop
                          and cat_modos[i]["mono"] is True and emu_modos[i].mono is True for i in emu_modos)
                  and all(emu_modos[i].saida == MODOS_ESPERADOS[pid][i][0] and emu_modos[i].fps == MODOS_ESPERADOS[pid][i][1]
                          for i in emu_modos) and cams[pid]["modos_video"] == list(emu_modos))
        c.ok(f"[§2] modos de '{pid}': catálogo = emulador = os da ficha/Himax (id, saída, fps, janela) — "
             f"{sorted(emu_modos)}", iguais,
             f"{ {i: (emu_modos[i].saida, emu_modos[i].fps) for i in emu_modos} }")

    # ---- cada modo: fps ≤ máximo do sensor, janela dentro do sensor, sem ampliação, proporção do render e FoV fechado
    pior_fov, violacoes, ids = 0.0, [], 0
    for pid in novos:
        mid = cam.modulo_da_peca(pid)
        res = cams[pid]["resolucao_px"]
        v_pub = cams[pid]["fov_graus"]["vertical"]
        for i, mo in cam.modos_do_modulo(mid).items():
            ids += 1
            x, y, w, h = mo.crop
            if not (mo.fps <= mo.fps_sensor + TOL_S and x >= 0 and y >= 0 and x + w <= res[0] and y + h <= res[1]
                    and mo.saida[0] <= w and mo.saida[1] <= h and mo.sensor_altura_px == res[1]
                    and abs(mo.render[0] / mo.render[1] - w / h) < 1e-3 and mo.render[1] == mo.saida[1]):
                violacoes.append(f"{mid}/{i}")
            fechado = math.degrees(2.0 * math.atan((h / res[1]) * math.tan(math.radians(v_pub) / 2.0)))
            pior_fov = max(pior_fov, abs(fechado - cam.fovy_graus(mid, i)))
    c.ok(f"[§2] {ids} modos Arduino: fps ≤ máximo do sensor, janela DENTRO do sensor, sem ampliação, proporção do "
         f"render = a da janela e a altura do sensor do emulador = a do catálogo", not violacoes,
         f"violações: {violacoes or 'nenhuma'}")
    c.ok("[§2] FoV: fovy = 2·atan(h_janela/h_sensor · tan(V/2)) em todos os modos (fórmula fechada, calculada AQUI "
         "com a altura do sensor do catálogo)", pior_fov < 1e-9, f"pior desvio {pior_fov:.2e}°")
    ancoras = {("vs_hm0360", "VGA60"): 55.4, ("vs_hm0360", "QVGA30"): 55.4, ("vs_hm01b0", "320x320p45"): 87.0,
               ("vs_hm01b0", "QVGA60"): 70.8807, ("vs_hm01b0", "QQVGA120"): 70.8807}
    c.ok("[§2] âncoras de FoV vertical: HM0360 55,4° em todos os modos (só o binning muda); HM01B0 87° na matriz "
         "inteira e 70,88° na janela QVGA (240/320 linhas)",
         all(abs(cam.fovy_graus(m, i) - v) < 5e-4 for (m, i), v in ancoras.items()),
         f"{ {f'{m}/{i}': round(cam.fovy_graus(m, i), 3) for (m, i) in ancoras} }")
    c.ok("[§2] modo por omissão = o da biblioteca Camera da Arduino (QVGA, 30 fps) nas shields e 1080p50 na Pi Camera; "
         "`modo_omissao` e `plataforma` por módulo",
         cam.modo_omissao("vs_hm0360") == cam.modo_omissao("vs_hm01b0") == "QVGA30"
         and cam.modos_do_modulo("vs_hm0360")["QVGA30"].fps == 30.0
         and cam.modo_omissao("mod3_wide") == cam.modo_omissao("mod3") == cam.OMISSAO_MODO == "1080p50"
         and {m: cam.plataforma(m) for m in cam.MODULOS}
         == {"mod3": "rpi5", "mod3_wide": "rpi5", "vs_hm0360": "arduino", "vs_hm01b0": "arduino"},
         f"{ {m: (cam.plataforma(m), cam.modo_omissao(m)) for m in cam.MODULOS} }")
    lat = cam.latencia_modelada("QVGA60", "vs_hm0360")
    soma = sum(lat["estagios_ms"].values())
    pi_lat = cam.latencia_modelada("1080p50")["total_ms"]
    c.ok("[§2] latência do caminho DCMI: soma dos estágios = total; QVGA60 = 1 período (16,7 ms) + 3 ms + 1 ms ≈ 20,7 ms "
         "— bem abaixo dos 116 ms do MJPEG da Pi; os 2 estágios ASSUMIDOS estão ditos",
         abs(soma - lat["total_ms"]) < 0.11 and abs(lat["total_ms"] - (1000.0 / 60.0 + 4.0)) < 0.1 and lat["total_ms"] < pi_lat / 4
         and "ASSUMIDOS" in lat["nota"] and "ISP" in lat["nota"] and lat["faixa_publicada_ms"] is None,
         f"{lat['estagios_ms']} = {lat['total_ms']} ms (Pi 1080p50: {pi_lat} ms)")
    l30, l60 = cam.latencia_modelada("QVGA30", "vs_hm0360")["total_ms"], lat["total_ms"]
    c.ok("[§2] a latência cai com o fps (o termo de leitura é 1 período): QVGA30 > QVGA60 e a 30 fps = 33,3 + 4 ms",
         l30 > l60 and abs(l30 - (1000.0 / 30.0 + 4.0)) < 0.1, f"QVGA30 {l30} ms · QVGA60 {l60} ms")
    ram = 1024 * 1024
    bytes_modo = {f"{m}/{i}": mo.saida[0] * mo.saida[1] for m in ("vs_hm0360", "vs_hm01b0")
                  for i, mo in cam.modos_do_modulo(m).items()}
    c.ok("[§2] memória: o quadro mono de 8 bit cabe na RAM de 1 MB do H747 em todos os modos (QVGA 76 800 B, VGA "
         "307 200 B = 29 % da RAM — acima de QVGA a biblioteca da Arduino aconselha a SDRAM)",
         max(bytes_modo.values()) < ram and bytes_modo["vs_hm0360/QVGA30"] == 76800
         and bytes_modo["vs_hm0360/VGA60"] == 307200,
         f"QVGA {bytes_modo['vs_hm0360/QVGA30']} B · VGA {bytes_modo['vs_hm0360/VGA60']} B "
         f"({100 * bytes_modo['vs_hm0360/VGA60'] / ram:.0f} % da RAM)")


def checa_captura(c: Checagens) -> None:
    _titulo("§2b câmara × emulador (render EGL): JPEG mono de 8 bit, recusas, Pi Camera intacta")
    from PIL import Image
    model, data = _modelo_pequeno()

    # ---- captura MONO: cada modo de cada shield dá um JPEG de 1 canal ('L') com as dimensões EXATAS da saída
    erros, n = [], 0
    for mid in ("vs_hm0360", "vs_hm01b0"):
        modulo = cam.ModuloCamera(model, "fpv", modulo=mid)
        for i, mo in cam.modos_do_modulo(mid).items():
            modulo.ligar(True, i)
            modulo.apontar(data)
            q = modulo.capturar()
            imagem = Image.open(io.BytesIO(q.jpeg))
            n += 1
            fovy = float(model.cam_fovy[modulo.camera_id])
            if not (imagem.mode == "L" and imagem.size == mo.saida and (q.largura, q.altura) == mo.saida
                    and abs(fovy - cam.fovy_graus(mid, i)) < TOL_S):
                erros.append(f"{mid}/{i}: {imagem.mode} {imagem.size} fovy {fovy:.3f}")
        modulo.fechar()
    c.ok(f"[§2] captura mono: {n} modos Arduino dão JPEG de 1 canal (PIL 'L') EXATAMENTE nas dimensões da saída e o "
         f"render usa o FoV do modo", not erros, f"erros: {erros or 'nenhum'}")

    # ---- conversão para cinzento (luma BT.601) e perda de cor
    magenta = np.array([[[255, 0, 255]]], dtype=np.uint8)
    branco = np.array([[[255, 255, 255]]], dtype=np.uint8)
    verde_igual = np.array([[[0, 180, 0]]], dtype=np.uint8)      # 0,587·180 = 105,7 → o mesmo cinzento do magenta
    cinza = cam.para_cinza(np.concatenate([magenta, branco, verde_igual], axis=1))
    c.ok("[§2] cinzento BT.601 (0,299/0,587/0,114): magenta (255,0,255) → 105 (luma 0,41), branco → 255 e um verde "
         "escolhido a dedo dá o MESMO cinzento — numa câmara mono a cor perde-se, só resta o brilho",
         cinza.shape == (1, 3) and cinza.dtype == np.uint8 and int(cinza[0, 0]) == 105 and int(cinza[0, 1]) == 255
         and abs(int(cinza[0, 2]) - int(cinza[0, 0])) <= 1 and cam.LUMA_BT601 == (0.299, 0.587, 0.114),
         f"magenta {int(cinza[0, 0])} · branco {int(cinza[0, 1])} · verde {int(cinza[0, 2])}")
    mmodel, mdata = _modelo_pequeno(com_marcador=True)
    modulo = cam.ModuloCamera(mmodel, "fpv", modulo="vs_hm0360", modo="VGA60")
    modulo.apontar(mdata)
    q = modulo.capturar()
    g = np.array(Image.open(io.BytesIO(q.jpeg)))
    centro = float(g[237:243, 317:323].mean())
    modulo.fechar()
    c.ok("[§2] o marcador magenta emissivo do simulador, visto pela câmara MONO a 2 m: um disco com luma ≈ 0,5 (131/255 "
         "medido) sobre fundo escuro — só contraste de brilho (um alvo branco/IR seria melhor)",
         g.shape == (480, 640) and 100.0 <= centro <= 150.0 and float(np.median(g)) < 10.0,
         f"luma no centro {centro:.0f}/255 ({centro / 255:.2f}) · mediana do quadro {float(np.median(g)):.0f}")

    # ---- recusas: cada módulo só aceita os modos do SEU mundo (construtor e ligar), nunca se finge
    shield = cam.ModuloCamera(model, "fpv", modulo="vs_hm0360")
    pi = cam.ModuloCamera(model, "fpv", modulo="mod3_wide", modo="480p120")
    c.ok("[§2] recusas (ValueError nos dois caminhos): a shield recusa 1080p50 e o HDR; a Pi Camera recusa QVGA30; "
         "módulo desconhecido recusa",
         _recusa(lambda: cam.ModuloCamera(model, "fpv", modulo="vs_hm0360", modo="1080p50"))
         and _recusa(lambda: shield.ligar(True, "1080p50"))
         and _recusa(lambda: cam.ModuloCamera(model, "fpv", modulo="mod3_wide", modo="QVGA30"))
         and _recusa(lambda: pi.ligar(True, "QVGA30"))
         and _recusa(lambda: cam.ModuloCamera(model, "fpv", modulo="nope")),
         "ValueError em 5/5")
    shield.fechar()

    # ---- estado/configuração do módulo Arduino: honestidade sobre a plataforma
    mod = cam.ModuloCamera(model, "fpv", modulo="vs_hm0360", modo="QVGA60")
    mod.apontar(data)
    quadro = mod.capturar()
    est, cfg = mod.estado(), mod.configuracao()
    lat = cam.latencia_modelada("QVGA60", "vs_hm0360")["total_ms"] / 1000.0
    c.ok("[§2] estado/configuração do módulo Arduino: plataforma 'arduino', mono, quadro cru 76 800 B, SEM custo de Pi 5 "
         "(`custo_pi5: None`), latência do caminho DCMI e a nota de plataforma",
         est["plataforma"] == cfg["plataforma"] == "arduino" and est["mono"] is True and cfg["mono"] is True
         and est["bytes_quadro_bruto"] == 76800 and est["custo_pi5"] is None and cfg["custo_pi5"] is None
         and est["latencia_modelada_ms"]["total_ms"] == cam.latencia_modelada("QVGA60", "vs_hm0360")["total_ms"]
         and "sem Raspberry Pi" in est["nota_plataforma"] and est["saida"] == [320, 240]
         and cfg["modo"]["mono"] is True and cfg["fov_modo_graus"]["vertical"] == 55.4,
         f"{ {k: est[k] for k in ('plataforma', 'mono', 'bytes_quadro_bruto', 'custo_pi5')} }")
    c.ok("[§2] a latência do modelo é CUMPRIDA na entrega: `disponiveis()` vazio antes de t+20,7 ms e entrega a partir dela",
         mod.disponiveis(agora=quadro.t_captura + lat - 1e-6) == []
         and [x.seq for x in mod.disponiveis(agora=quadro.t_captura + lat + 1e-6)] == [quadro.seq],
         f"t_disponivel − t_captura = {1000 * (quadro.t_disponivel - quadro.t_captura):.1f} ms")
    mod.fechar()

    # ---- a fonte `simulacao` (vista do simulador, não hardware) fica a CORES mesmo num módulo mono
    livre = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, livre)
    sim = cam.ModuloCamera(model, "simulacao", modulo="vs_hm0360", modo="QVGA30", camera_livre=lambda: livre)
    sim.apontar(data)
    qs = sim.capturar()
    imagem_sim = Image.open(io.BytesIO(qs.jpeg))
    c.ok("[§2] fonte `simulacao` num módulo mono: a vista do simulador NÃO é hardware — sai a cores (RGB), 320×240 e "
         "sem custo de Pi", imagem_sim.mode == "RGB" and imagem_sim.size == (320, 240)
         and sim.estado()["mono"] is False and sim.estado()["custo_pi5"] is None,
         f"{imagem_sim.mode} {imagem_sim.size}")
    sim.fechar()

    # ---- a Pi Camera EXATAMENTE como era (comportamento, valores e chaves)
    pm = cam.ModuloCamera(model, "fpv", modulo="mod3_wide", modo="480p120")
    pm.apontar(data)
    qp = pm.capturar()
    ip = Image.open(io.BytesIO(qp.jpeg))
    ep = pm.estado()
    novas = {"plataforma", "mono", "bytes_quadro_bruto", "nota_plataforma"}
    valores_pi = all(cam.MODOS[i].saida == s and cam.MODOS[i].fps == f and cam.MODOS[i].crop == cr
                     and cam.MODOS[i].sensor_altura_px == 2592 and not cam.MODOS[i].mono
                     for i, (s, f, cr) in MODOS_PI.items())
    c.ok("[§2] Pi Camera INTACTA: os 7 modos do IMX708 com os valores de antes (altura do sensor 2592, sem mono), "
         "captura RGB de 3 canais, FoV 67,0°/47,62°, latência 116 ms e 94 % de CPU do Pi 5 a 1080p50, `estado()` sem "
         "as chaves do Arduino e `as_dict` sem `mono`",
         set(cam.MODOS) == set(MODOS_PI) and valores_pi and ip.mode == "RGB" and ip.size == (640, 480)
         and abs(cam.fovy_graus("mod3_wide", "1080p50") - 67.0) < 1e-9
         and abs(cam.fovy_graus("mod3_wide", "720p100") - 47.620) < 5e-3
         and cam.latencia_modelada("1080p50")["total_ms"] == 116.0
         and cam.latencia_modelada("1080p50", "mod3_wide")["total_ms"] == 116.0
         and cam.custo_cpu("1080p50")["total_pct_nucleo"] == 94.0
         and not (novas & set(ep)) and isinstance(ep["custo_pi5"], dict)
         and "mono" not in cam.MODOS["1080p50"].as_dict() and cam.plataforma("mod3_wide") == "rpi5",
         f"{ip.mode} {ip.size} · lat {cam.latencia_modelada('1080p50')['total_ms']} ms")
    pm.fechar()


# ============================================================================================ §3 BUILD
def checa_build(c: Checagens) -> None:
    _titulo("§3 build endurance_15pol_arduino: o p50b com o computador trocado; massa, potência, autonomia, planta")
    cat, builds = _cat(), _builds()
    b_ard, b_p50 = builds["builds"][BUILD_NOVO], builds["builds"][BUILD_ATIVO]
    c.ok("[§3] o build ATIVO continua 'endurance_15pol_p50b' (builds.json no disco) e o p50b mantém RPi 5 + FC H7 + "
         "Pi Camera Module 3 Wide",
         builds["ativo"] == BUILD_ATIVO and comp.nome_build_ativo() == BUILD_ATIVO
         and b_p50["eletronica"] == ["rpi5", "fc_h7", "cablagem"] and b_p50["camera"] == "raspberry_camera_module_3_wide"
         and b_p50["arquitetura"] == "fc", f"ativo = {builds['ativo']}")
    trocados = {"descricao", "eletronica", "arquitetura", "camera"}
    iguais = {k for k in b_p50 if k not in trocados}
    c.ok("[§3] o build novo é o p50b com SÓ o computador de bordo trocado: frame 1950, motor, hélice, bateria 6S2P P50B, "
         "ESC, sensores (BMI088 + VL53L1X + PMW3901 + INA226) e todos os parâmetros iguais; muda só descrição, "
         "eletrónica, arquitetura e câmara",
         {k: b_ard[k] for k in iguais} == {k: b_p50[k] for k in iguais} and set(b_ard) == set(b_p50)
         and b_ard["eletronica"] == ["arduino_portenta_h7", "cablagem"] and b_ard["arquitetura"] == "arduino"
         and b_ard["camera"] == "portenta_vision_shield_hm0360" and b_ard["frame"] == "diy_tubo_carbono_1950"
         and b_ard["sensores"]["imu"] == "bmi088",
         f"iguais: {len(iguais)} chaves · eletrónica {b_ard['eletronica']} · câmara {b_ard['camera']}")
    hw_a, hw_p = dr.hardware(BUILD_NOVO), dr.hardware(BUILD_ATIVO)
    ele = cat["eletronica"]
    esperada = (hw_p.massa_total - (ele["rpi5"]["massa_g"] + ele["fc_h7"]["massa_g"]
                                    + cat["cameras"]["raspberry_camera_module_3_wide"]["massa_g"]) / 1000.0
                + (ele["arduino_portenta_h7"]["massa_g"] + cat["cameras"]["portenta_vision_shield_hm0360"]["massa_g"]) / 1000.0)
    m_a, m_p = hw_a.massas, hw_p.massas
    c.ok("[§3] massa: p50b − (RPi 5 52 g + FC 8 g + Pi Camera 4 g) + (Portenta 10 g + shield 8 g) = 2136,6 g; o orçamento "
         "do build novo não tem rpi5 nem fc_h7 e tem Portenta + câmara",
         abs(hw_a.massa_total - esperada) < 1e-9 and abs(hw_a.massa_total * 1000.0 - 2136.6) < 1e-6
         and "rpi5" not in m_a and "fc_h7" not in m_a and "arduino_portenta_h7" in m_a and "camera" in m_a
         and abs(m_p["frame"] - m_a["frame"]) < TOL_S and abs(m_p["bateria"] - m_a["bateria"]) < TOL_S,
         f"{hw_p.massa_total * 1000:.1f} g → {hw_a.massa_total * 1000:.1f} g ({1000 * (hw_a.massa_total - hw_p.massa_total):+.1f} g)")
    p_sens = sum(float(s.get("potencia_w", 0.0)) for s in hw_a.sensores.values())
    ph_a, ph_p = hw_a.ponto_pairagem(hw_a.bateria.v_nominal), hw_p.ponto_pairagem(hw_p.bateria.v_nominal)
    aut_a, aut_p = comp.autonomia_estimada(hw_a)["minutos"], comp.autonomia_estimada(hw_p)["minutos"]
    c.ok("[§3] potência: a eletrónica do build novo = (Portenta 1,0 W + sensores) ÷ 0,88 ≈ 1,3 W (a do p50b é 6,5 W) e a "
         "pairagem desce de ~198 W para ~187 W; T/W sobe",
         abs(hw_a.potencia_eletronica("voo") - (1.0 + p_sens) / 0.88) < 1e-9
         and 1.0 < hw_a.potencia_eletronica("voo") < 1.6 and 6.0 < hw_p.potencia_eletronica("voo") < 7.0
         and 5.0 < ph_p["p_total"] - ph_a["p_total"] < 20.0 and abs(ph_p["p_total"] - 198.1) < 0.5
         and ph_a["g_por_w"] > ph_p["g_por_w"],
         f"eletrónica {hw_p.potencia_eletronica('voo'):.2f} → {hw_a.potencia_eletronica('voo'):.2f} W · pairagem "
         f"{ph_p['p_total']:.1f} → {ph_a['p_total']:.1f} W · {ph_p['g_por_w']:.2f} → {ph_a['g_por_w']:.2f} g/W")
    r_a, r_p = hw_a.resumo(), hw_p.resumo()
    c.ok("[§3] autonomia pelo modelo: p50b 65,8 min (como antes) → Arduino ~70 min (+4 min); T/W com a bateria cheia ≥ 2,6; "
         "sem saturação; meta de 60 min cumprida",
         abs(aut_p - 65.8) < 0.3 and 2.0 < aut_a - aut_p < 8.0 and aut_a > hw_a.dados["meta_autonomia_min"]
         and r_a["t_w_cheia"] >= 2.6 and not ph_a["satura"] and r_a["autonomia_min"] == aut_a,
         f"{aut_p:.1f} → {aut_a:.1f} min ({aut_a - aut_p:+.1f}) · T/W {r_p['t_w_cheia']:.2f} → {r_a['t_w_cheia']:.2f}")

    # ---- a planta constrói (MuJoCo + ar + bateria) e paira: massa do modelo = orçamento, pairagem = catálogo
    model, data = dr.carregar(hw_a)
    corpo = model.body("drone").id
    pl = dr.Planta(hw_a, model, data, rng=np.random.default_rng(4))
    data.qpos[2] = 5.0
    mujoco.mj_forward(model, data)
    pl.reiniciar(0.7, armado=True)
    ph = hw_a.ponto_pairagem(pl.v_bus)
    pl.prop.reiniciar(np.full(4, ph["omega"]))
    pl.prop.armar(True)
    potencias = []
    for k in range(1000):
        if k % 25 == 0:
            ph = hw_a.ponto_pairagem(pl.v_bus)
        pl.passo([ph["acelerador"]] * 4)
        if k >= 500:
            potencias.append(pl.potencias()["total"])
    p_med = float(np.mean(potencias))
    p_cat = hw_a.ponto_pairagem(pl.v_bus)["p_total"]
    vz = float(data.qvel[2])
    gw = hw_a.massa_total * 1000.0 / p_med
    c.ok("[§3] a planta do build novo constrói e PAIRA: massa do modelo = orçamento (2136,6 g), origem no CM, câmara "
         "'fpv' a olhar para +x com o FoV do módulo (55,4°), potência medida = catálogo ±3 %, |v_z| < 0,3 m/s, "
         "g/W em 8–14",
         abs(float(model.body_mass.sum()) - hw_a.massa_total) < 1e-9 and float(np.abs(model.body_ipos[corpo]).max()) < 1e-9
         and abs(float(model.cam_fovy[model.camera("fpv").id]) - 55.4) < TOL_S
         and abs(p_med - p_cat) / p_cat < 0.03 and abs(vz) < 0.3 and 8.0 <= gw <= 14.0,
         f"P medida {p_med:.1f} W vs catálogo {p_cat:.1f} W · {gw:.2f} g/W · v_z {vz:+.3f} m/s · massa "
         f"{1000 * float(model.body_mass.sum()):.1f} g")


def checa_usar_em_copia(c: Checagens) -> None:
    """`hardware.py usar endurance_15pol_arduino` numa CÓPIA do builds.json (o real nunca muda)."""
    _titulo("§3b hardware.py usar <build novo> numa cópia segura: constrói a planta e o ativo REAL não se mexe")
    import hardware as cli  # experiments/09_drone_hover_rl/hardware.py (das fontes escolhidas)
    antes = _sha(BUILDS)
    tmp = Path(tempfile.mkdtemp(prefix="teste_arduino_", dir=os.environ.get("TMPDIR")))
    copia = tmp / "builds.json"
    shutil.copy2(BUILDS, copia)
    guardado = (comp.BUILDS_JSON, cli.XML_ATIVO, cli._RAIZ)
    try:
        comp.BUILDS_JSON, cli.XML_ATIVO, cli._RAIZ = copia, tmp / "drone_rpi.xml", tmp
        saida = io.StringIO()
        _stdout, sys.stdout = sys.stdout, saida
        try:
            codigo = cli.cmd_usar(argparse.Namespace(build=BUILD_NOVO, sem_coala=True))
        finally:
            sys.stdout = _stdout
        ativo_copia = comp.nome_build_ativo()
        hw = dr.hardware()                           # o ATIVO da cópia
        model, data = dr.carregar(hw)
        pl = dr.Planta(hw, model, data, rng=np.random.default_rng(0))
        mujoco.mj_forward(model, data)
        pl.reiniciar(1.0, armado=True)
        pl.passo([0.5] * 4)
        xml = (tmp / "drone_rpi.xml").read_text(encoding="utf-8")
        ok_xml = "drone_rpi_endurance_15pol_arduino" in xml and 'name="fpv"' in xml and "<camera" in xml
    finally:
        comp.BUILDS_JSON, cli.XML_ATIVO, cli._RAIZ = guardado
        shutil.rmtree(tmp, ignore_errors=True)
    c.ok("[§3] `usar` na CÓPIA: exit 0, o ativo da cópia passa a ser o build novo, o MJCF sai com a câmara `fpv`, a "
         "planta constrói e dá 1 passo; o builds.json REAL fica byte a byte igual e o ativo real continua o p50b",
         codigo == 0 and ativo_copia == BUILD_NOVO and hw.nome == BUILD_NOVO and ok_xml
         and abs(hw.massa_total * 1000.0 - 2136.6) < 1e-6 and _sha(BUILDS) == antes
         and comp.nome_build_ativo() == BUILD_ATIVO and _builds()["ativo"] == BUILD_ATIVO,
         f"ativo da cópia = {ativo_copia} · real = {comp.nome_build_ativo()} · sha igual {_sha(BUILDS) == antes}")


def checa_cli(c: Checagens) -> None:
    _titulo("§3c CLI (subprocessos, só leitura): hardware.py listar/mostrar mostram as peças e o build novo")
    cli = _EXP / "hardware.py"
    r1 = subprocess.run([sys.executable, str(cli), "mostrar", BUILD_NOVO], capture_output=True, text=True, timeout=180,
                        check=False)
    r2 = subprocess.run([sys.executable, str(cli), "listar"], capture_output=True, text=True, timeout=180, check=False)
    c.ok("[§3] `hardware.py mostrar <build novo>`: arquitetura arduino, câmara MONO no modo por omissão QVGA30 (FoV "
         "70°×55°), 2137 g, 70,0 min; `listar` mostra as 5 peças novas",
         r1.returncode == 0 and "arquitetura arduino" in r1.stdout and "monocromática" in r1.stdout
         and "QVGA30" in r1.stdout and "2137 g" in r1.stdout and "70.0 min" in r1.stdout
         and r2.returncode == 0 and all(k in r2.stdout for k in (
             "arduino_portenta_h7", "arduino_nicla_vision", "arduino_giga_r1", "portenta_vision_shield_hm0360",
             "portenta_vision_shield_hm01b0", BUILD_NOVO)),
         f"mostrar exit {r1.returncode} · listar exit {r2.returncode}")


# ====================================================================================== §4 MUTAÇÕES
def _mut_clock_m7(t: str) -> str:
    i = t.index('"arduino_portenta_h7"')
    j = t.index('"clock_max_mhz": 480', i)
    return t[:j] + '"clock_max_mhz": 400' + t[j + len('"clock_max_mhz": 480'):]


def _mut_fov_hm0360(t: str) -> str:
    i = t.index('"portenta_vision_shield_hm0360"')
    j = t.index('"vertical": 55.4', i)
    return t[:j] + '"vertical": 50.0' + t[j + len('"vertical": 55.4'):]


def _mut_mono_desligado(t: str) -> str:
    antigo = "if mo.mono and self.camera_livre is None:"
    assert t.count(antigo) == 1
    return t.replace(antigo, "if False:")


def _mut_ativo(t: str) -> str:
    antigo = '"ativo": "endurance_15pol_p50b"'
    assert t.count(antigo) == 1
    return t.replace(antigo, '"ativo": "endurance_15pol_arduino"')


def _mut_rpi5_volta(t: str) -> str:
    d = json.loads(t)
    d["builds"][BUILD_NOVO]["eletronica"] = ["rpi5", "arduino_portenta_h7", "cablagem"]
    return json.dumps(d, ensure_ascii=False, indent=2) + "\n"


# (nome, ficheiro, função de mutação, flag do teste, marca que a falha TEM de trazer)
MUTACOES = (
    ("clock-m7-do-portenta", "models/drone_rpi/componentes.json", _mut_clock_m7, "--so-espec", "Portenta H7: clocks"),
    ("fov-hm0360-no-catalogo", "models/drone_rpi/componentes.json", _mut_fov_hm0360, "--so-espec", "catálogo × MODULOS"),
    ("mono-desligado-no-emulador", "lab/camera_rpi.py", _mut_mono_desligado, "--so-pecas", "captura mono"),
    ("build-ativo-trocado", "models/drone_rpi/builds.json", _mut_ativo, "--so-pecas", "build ATIVO continua"),
    ("rpi5-volta-ao-build-novo", "models/drone_rpi/builds.json", _mut_rpi5_volta, "--so-pecas",
     "o build novo é o p50b com SÓ o computador"),
)


def _montar_copia(destino: Path) -> None:
    """Cópia MÍNIMA das fontes que o teste usa (nunca se muta nas reais): lab/, os 2 JSON, hardware.py, pyproject."""
    shutil.copy2(RAIZ / "pyproject.toml", destino / "pyproject.toml")
    shutil.copytree(RAIZ / "lab", destino / "lab", ignore=shutil.ignore_patterns("__pycache__", "mjkit.py"))
    (destino / "models" / "drone_rpi").mkdir(parents=True)
    for nome in ("componentes.json", "builds.json"):
        shutil.copy2(RAIZ / "models" / "drone_rpi" / nome, destino / "models" / "drone_rpi" / nome)
    (destino / "experiments" / "09_drone_hover_rl").mkdir(parents=True)
    shutil.copy2(_EXP / "hardware.py", destino / "experiments" / "09_drone_hover_rl" / "hardware.py")


def _correr_copia(copia: Path, flag: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(Path(__file__).resolve()), flag, "--fontes", str(copia)],
                          capture_output=True, text=True, timeout=600, check=False)


def checa_mutacoes(c: Checagens) -> None:
    _titulo("§4 mutações: o teste NÃO é tautológico (cada mutação, numa CÓPIA, tem de FALHAR a checagem certa)")
    base = Path(tempfile.mkdtemp(prefix="teste_arduino_mut_", dir=os.environ.get("TMPDIR")))
    try:
        controlo = base / "controlo"
        controlo.mkdir()
        _montar_copia(controlo)
        r0 = _correr_copia(controlo, "--so-pecas")
        c.ok("[§4] controlo: a cópia SEM mutação passa o teste (as falhas abaixo vêm só da mutação)",
             r0.returncode == 0, f"exit {r0.returncode}")
        for nome, rel, mutar, flag, marca in MUTACOES:
            copia = base / nome
            copia.mkdir()
            _montar_copia(copia)
            alvo = copia / rel
            alvo.write_text(mutar(alvo.read_text(encoding="utf-8")), encoding="utf-8")
            r = _correr_copia(copia, flag)
            linhas_falha = [ln.strip() for ln in r.stdout.splitlines() if "[FALHA]" in ln and marca in ln]
            c.ok(f"[§4] mutação {nome} ({rel}): {flag} FALHA na checagem certa ('{marca}')",
                 r.returncode != 0 and bool(linhas_falha), f"exit {r.returncode} · {len(linhas_falha)} falha(s) com a marca")
    finally:
        shutil.rmtree(base, ignore_errors=True)


# ------------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Prova das peças Arduino do catálogo e do build endurance_15pol_arduino.")
    p.add_argument("--mutacao", action="store_true", help="corre SÓ as mutações (§4)")
    p.add_argument("--so-espec", action="store_true", help="corre §1 + §2a (sem render, sem planta)")
    p.add_argument("--so-pecas", action="store_true", help="corre §1–§3 sem subprocessos (usado pelo §4)")
    p.add_argument("--fontes", type=Path, default=_REPO, help="raiz das fontes (por omissão o repositório)")
    args = p.parse_args(argv)

    total = Checagens()
    if args.mutacao:
        checa_mutacoes(total)
    else:
        usadas = Path(cam.__file__).resolve().parents[1]
        total.ok("[§0] o teste corre contra as fontes pedidas (`lab/` importado da raiz escolhida)",
                 usadas == RAIZ, f"lab em {usadas}")
        checa_pecas(total)
        checa_especificacao(total)
        if not args.so_espec:
            checa_captura(total)
            checa_build(total)
            checa_usar_em_copia(total)
            if not args.so_pecas:
                checa_cli(total)
    print(f"\n[teste] {len(total.linhas) - len(total.falhas)}/{len(total.linhas)} checagens OK", flush=True)
    if total.falhas:
        for nome in total.falhas:
            print(f"[teste] FALHOU: {nome}", flush=True)
        return 1
    print("[teste] as peças Arduino batem com as fichas, o emulador aceita a câmara mono sem mudar a Pi Camera, o build "
          "novo é o p50b com o computador trocado e o build ativo continua o p50b", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

