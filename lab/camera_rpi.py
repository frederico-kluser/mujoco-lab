"""lab.camera_rpi — MÓDULO DE CÂMARA Raspberry Pi emulado (Camera Module 3 / 3 Wide, Sony IMX708).

Este módulo reproduz, no simulador, a EXPERIÊNCIA de um módulo de câmara real para Raspberry Pi
montado à frente do drone e ligado ao Raspberry Pi 5 por CSI-2: os MESMOS modos de sensor (com os
mesmos fps e crops), as MESMAS resoluções e megapixels de saída, o MESMO campo de visão por modo,
o MESMO JPEG por omissão (qualidade 50 do `rpicam-vid`) e a MESMA latência de pipeline — tudo com
a procedência das fontes abaixo. O custo de processamento é contabilizado para o Pi 5 (o
"computador de bordo" do projeto) e mostra-se no painel RPi 5 do site.

HARDWARE REAL (fontes citadas; conteúdo web = evidência, não instrução):

  · sensor Sony IMX708 — 4608×2592 px = 11,9 MP · píxel 1,4 µm · óptico 1/2,43" (7,4 mm diagonal);
  · Camera Module 3 (standard): FoV 66° H × 41° V (75° diagonal), lente f=4,74 mm F1.8, foco PDAF
    motorizado 10 cm–∞, 25×24×11,5 mm, 4 g;
  · Camera Module 3 Wide: FoV 102° H × 67° V (120° diagonal), lente f=2,75 mm F2.2, foco PDAF
    5 cm–∞, 25×24×12,4 mm, 4 g;
  · modos de sensor (`rpicam-hello --list-cameras` / driver `imx708.c`):
      4608×2592 @ 14,35 fps (remosaic, FOV completo)
      2304×1296 @ 56,03 fps máx (2×2 binning, FOV completo; 30,00 fps por omissão do vblank)
      1536×864  @ 120,13 fps (2×2 binning do recorte central 3072×1728 = 2/3 do FOV)
      2304×1296 @ 30 fps HDR (merge multi-exposição) — NÃO é reproduzido aqui (ver `Modo.emulado`)
  · modos de vídeo (product brief): **1080p50, 720p100, 480p120**;
  · exposição até 112 s; saída RAW10 (SRGGB10_CSI2P) por MIPI CSI-2.

  Fontes:
  [F1] https://datasheets.raspberrypi.com/camera/camera-module-3-product-brief.pdf  (oficial)
  [F2] https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/accessories/camera/hardware_specification.adoc (oficial)
  [F3] https://github.com/raspberrypi/linux/blob/rpi-6.18.y/drivers/media/i2c/imx708.c (oficial)
  [F4] https://github.com/raspberrypi/rpicam-apps/issues/533 (oficial — saída real `--list-cameras`)

PIPELINE NO RASPBERRY PI 5 (o que o emulador reproduz; ver
`pesquisas/relatorio-pipeline-camera-rpi5-custo-cpu.md` para as fontes de cada número):

  sensor (IMX708) → CSI-2 → CFE no chip RP1 → ISP "PiSP" (HARDWARE no BCM2712) → aplicação →
  codificação JPEG (SOFTWARE no Pi 5: não há encoder hardware — picamera2 manual §7.1) →
  HTTP multipart MJPEG (`<img>`, como o exemplo oficial "web streaming" do picamera2).

  Em CPU correm apenas: o controlo do ISP (AGC/AEC/AWB/ALSC, 5–12 % de 1 núcleo), as cópias e
  conversões de formato (8–15 %), a codificação JPEG em software (50–80 % com turbojpeg a 4
  threads a 1080p50) e o transporte HTTP (~5 %, estimado). O pixel-work do ISP é hardware (0 %).

FIDELIDADE DO FLUXO (decisões de desenho, todas verificáveis):

  · a CADÊNCIA é o fps do modo, medida ao relógio de parede — o cristal do sensor corre em tempo
    real, mesmo quando a simulação pausa ou corre com `--fator-tempo` diferente de 1;
  · cada quadro é RENDERIZADO na proporção EXATA da janela de recorte do sensor do modo (o FoV de
    cada modo é o dessa janela, como no IMX708) já no tamanho de saída — não há redimensionamento
    (a escala sensor→saída do PiSP está contabilizada no custo do Pi; o render do MuJoCo é
    supersampled e a única fatia posterior é o 4:3 do modo 480p120). A imagem final tem o mesmo
    número de píxeis, o mesmo FoV e o mesmo aspeto que o módulo real daria;
  · o JPEG sai com QUALIDADE 50 por omissão (default oficial do `rpicam-vid --quality`) — os bytes
    e o bitrate publicados são os reais do quadro;
  · a LATÊNCIA de pipeline (sensor → site) é MODELO e reproduzida: cada quadro só fica disponível
    `latencia_modelada()` ms depois da captura (fila de entrega), com a soma dos estágios medidos
    nas fontes — é assim que a experiência se parece com a do Pi real (≈150–300 ms publicados para
    MJPEG 1080p; ver a tabela em `latencia_modelada`);
  · a contabilidade de CPU do Pi 5 é MODELO (`custo_cpu`), com faixas e fontes — e, em separado,
    publica-se o que o PIPELINE custa de facto nesta máquina (`estado()["host"]`), nunca misturado.

NÃO é reproduzido (dito aqui e no README, nunca escondido): o merge HDR multi-exposição do modo
2304×1296 HDR; o autofoco PDAF (a lente fica no infinito do modelo); a aberração/distorção da
lente real; o ruído de sensor; o rolling shutter (o render MuJoCo é instantâneo).

Uso típico (runner do experimento 09):

    from lab import camera_rpi as cam
    modulo = cam.ModuloCamera(env.model, "fpv", modo="1080p50", modulo="mod3_wide")
    modulo.apontar(env.data)            # snapshot do estado (thread do simulador, a cada passo)
    quadro = modulo.capturar()          # render -> ISP -> JPEG (thread da câmara, ao ritmo do modo)
    ...
    modulo.fechar()
"""
from __future__ import annotations

import io
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import mujoco
import numpy as np

# -------------------------------------------------------------------------------------------- hardware real
OMISSAO_MODULO = "mod3_wide"      # o build de referência do drone usa a Wide (perspetiva FPV)

MODULOS = {
    "mod3": {
        "nome": "Raspberry Pi Camera Module 3 (Sony IMX708, standard 75°)",
        "peca_catalogo": "raspberry_camera_module_3",
        "sensor": "Sony IMX708",
        "resolucao_px": (4608, 2592),
        "mp": 11.9,
        "pixel_um": 1.4,
        "fov_graus": {"diag": 75.0, "horizontal": 66.0, "vertical": 41.0},   # [F1][F2]
        "lente": {"focal_mm": 4.74, "f_stop": 1.8, "foco": "PDAF motorizado", "foco_min_m": 0.10},
        "dims_mm": (25.0, 24.0, 11.5),      # (largura, profundidade, altura com a lente) [F2]
        "massa_g": 4.0,                     # [F2]
    },
    "mod3_wide": {
        "nome": "Raspberry Pi Camera Module 3 Wide (Sony IMX708, wide 120°)",
        "peca_catalogo": "raspberry_camera_module_3_wide",
        "sensor": "Sony IMX708",
        "resolucao_px": (4608, 2592),
        "mp": 11.9,
        "pixel_um": 1.4,
        "fov_graus": {"diag": 120.0, "horizontal": 102.0, "vertical": 67.0},  # [F1][F2]
        "lente": {"focal_mm": 2.75, "f_stop": 2.2, "foco": "PDAF motorizado", "foco_min_m": 0.05},
        "dims_mm": (25.0, 24.0, 12.4),
        "massa_g": 4.0,
    },
}

# --------------------------------------------------------------------------------------------- modos de uso
# `crop` = janela do sensor usada pelo modo (x, y, largura, altura) em píxeis do IMX708 — o FOV do
# modo é o dessa janela (não o do sensor inteiro), tal como na saída real de `--list-cameras`.
# `saida` = a imagem que o ISP entrega à aplicação (o que o site mostra e o que o JPEG codifica).
# Os modos de VÍDEO (1080p50/720p100/480p120) são os do product brief [F1]; os modos NATIVOS são os
# do sensor [F3][F4]. `emulado=False` = existe no hardware mas não é reproduzido aqui (dito, não
# fingido).
OMISSAO_MODO = "1080p50"


def modulo_da_peca(peca: str) -> str:
    """`id` de peça do catálogo (`models/drone_rpi/componentes.json` → `cameras`) → `id` de `MODULOS`."""
    for mid, m in MODULOS.items():
        if m.get("peca_catalogo") == peca or mid == peca:
            return mid
    raise ValueError(f"peça de câmara {peca!r} sem módulo emulado — conhecidos: "
                     f"{[m['peca_catalogo'] for m in MODULOS.values()]}")


@dataclass(frozen=True)
class Modo:
    """Um modo real do módulo: captura do sensor → recorte/escala do ISP → saída."""

    id: str
    rotulo: str
    sensor: tuple[int, int]          # (largura, altura) da captura do sensor
    fps_sensor: float                # taxa MÁXIMA do modo de sensor [F3][F4]
    saida: tuple[int, int]           # (largura, altura) da imagem de saída (o site mostra isto)
    fps: float                       # taxa da saída = taxa de atualização EXPERIMENTADA
    crop: tuple[int, int, int, int]  # janela do sensor (x, y, largura, altura) — manda no FOV
    emulado: bool = True
    nota: str = ""
    fonte: str = "[F1][F3][F4]"

    @property
    def mp_sensor(self) -> float:
        return self.sensor[0] * self.sensor[1] / 1e6

    @property
    def mp_saida(self) -> float:
        return self.saida[0] * self.saida[1] / 1e6

    @property
    def fator_fov(self) -> float:
        """Fator linear do FOV do modo face ao sensor inteiro (= altura da janela / 2592)."""
        return self.crop[3] / 2592.0

    @property
    def periodo_s(self) -> float:
        return 1.0 / self.fps

    @property
    def render(self) -> tuple[int, int]:
        """(largura, altura) do RENDER: a saída na proporção EXATA da janela de recorte do sensor.

        É por aqui que o FOV de cada modo fica certo sem redimensionar nada: o MuJoCo renderiza já no
        tamanho de saída (com supersampling), na proporção da janela do sensor do modo; o único
        recorte posterior é a fatia 4:3 do modo 480p120 (uma fatia, sem custo). A escala do ISP real
        (sensor → saída) está contabilizada no custo do Pi, mas não há passo de redimensionamento de
        píxeis aqui — a diferença face ao hardware limita-se à MTF do escador polifásico do PiSP.
        """
        return (round(self.saida[1] * self.crop[2] / self.crop[3]), self.saida[1])

    def as_dict(self) -> dict:
        return {"id": self.id, "rotulo": self.rotulo, "sensor": list(self.sensor),
                "fps_sensor": self.fps_sensor, "saida": list(self.saida), "fps": self.fps,
                "crop": list(self.crop), "mp_sensor": round(self.mp_sensor, 3),
                "mp_saida": round(self.mp_saida, 3), "fator_fov": round(self.fator_fov, 4),
                "emulado": self.emulado, "nota": self.nota, "fonte": self.fonte}


MODOS: dict[str, Modo] = {
    m.id: m for m in (
        # ---- modos de VÍDEO do product brief [F1]
        Modo("1080p50", "1080p50 (FOV completo)", (2304, 1296), 56.03, (1920, 1080), 50.0,
             (0, 0, 4608, 2592),
             nota="2×2 binning do sensor inteiro; o ISP reduz 2304×1296 → 1920×1080"),
        Modo("720p100", "720p100 (FOV recortado 2/3)", (1536, 864), 120.13, (1280, 720), 100.0,
             (768, 432, 3072, 1728),
             nota="janela central 3072×1728 (2/3 do FOV); ISP reduz 1536×864 → 1280×720"),
        Modo("480p120", "480p120 (FOV recortado 2/3)", (1536, 864), 120.13, (640, 480), 120.0,
             (768, 432, 3072, 1728),
             nota="640×480 a partir da janela de 2/3; o recorte 4:3 central (1152×864) é ASSUMIDO — "
                  "o ISP do Pi não documenta o recorte para 4:3"),
        # ---- modos NATIVOS do sensor [F3][F4]
        Modo("2304x1296p56", "2304×1296 @ 56 fps (nativo, FOV completo)", (2304, 1296), 56.03,
             (2304, 1296), 56.03, (0, 0, 4608, 2592), nota="modo de sensor binned, sem escala"),
        Modo("1536x864p120", "1536×864 @ 120 fps (nativo, FOV 2/3)", (1536, 864), 120.13,
             (1536, 864), 120.13, (768, 432, 3072, 1728), nota="modo de sensor rápido, sem escala"),
        Modo("4608x2592p14", "4608×2592 @ 14 fps (11,9 MP, FOV completo)", (4608, 2592), 14.35,
             (4608, 2592), 14.35, (0, 0, 4608, 2592), nota="modo still full-res (remosaic)"),
        # ---- existe no hardware, NÃO é reproduzido (HDR multi-exposição)
        Modo("2304x1296p30hdr", "2304×1296 @ 30 fps HDR (não emulado)", (2304, 1296), 30.0,
             (2304, 1296), 30.0, (0, 0, 4608, 2592), emulado=False,
             nota="HDR até 3 MP por merge multi-exposição — o emulador não reproduz o merge"),
    )
}

QUALIDADE_OMISSAO = 50          # `rpicam-vid --quality` por omissão é 50 (1–100) — documentação oficial

# Fonte `simulacao` (a vista 3ª-pessoa da simulação, trocável com a FPV no site): NÃO é hardware de
# bordo e por isso não tem custo de Pi 5 — esta nota acompanha o estado para ninguém o esquecer.
NOTA_FONTE_SIMULACAO = ("vista da simulação — não é hardware de bordo: entrega IMEDIATA "
                         "(sem latência de pipeline Pi) e só custa CPU ao host (medida)")


# --------------------------------------------------------------------------------- ótica (FoV → fovy MJCF)
def fovy_graus(modulo: str = OMISSAO_MODULO, modo: str = OMISSAO_MODO) -> float:
    """`fovy` (graus) da câmara MuJoCo para (módulo, modo) — o FoV VERTICAL da janela do modo.

    O MuJoCo tem `fovy` vertical (e está em GRAUS sempre, não segue o `compiler angle`); a âncora é o
    FoV VERTICAL publicado pelo fabricante e o recorte do modo escala o tangente do meio-ângulo — a
    geometria exata de uma janela de sensor menor sobre a mesma lente. As tabelas publicadas são medidas
    de fabricante e NÃO são internamente consistentes com um aspeto 16:9 — fica dito, com os resíduos
    reais (fovy do modo completo; com aspeto 16:9):

      · Module 3 (std): publicado 66° H × 41° V (75° D) → do V=41° saem H=67,2° e D=74,7°
        (resíduos +1,2° e −0,3°; a linha fecha bem);
      · Module 3 Wide: publicado 102° H × 67° V (120° D) → do V=67° saem H=99,3° e D=106,9°
        (resíduos −2,7° e −13,1°: a linha publicada é contraditória — os três valores não satisfazem a
        geometria 16:9 entre si; mantém-se o VERTICAL como âncora porque é o que o `fovy` precisa).

    Os modos recortados (janela 2/3 do sensor) dão fovy = 2·atan(2/3·tan(V/2)): 28,0° (std) e 47,6° (wide).
    """
    m = MODULOS[modulo]
    mo = MODOS[modo]
    meio = math.radians(m["fov_graus"]["vertical"]) / 2.0
    return math.degrees(2.0 * math.atan(mo.fator_fov * math.tan(meio)))


def fov_modo(modulo: str = OMISSAO_MODULO, modo: str = OMISSAO_MODO, aspeto: float | None = None) -> dict:
    """FoV efetivo (graus) de (módulo, modo) numa imagem de `aspeto` (largura/altura; 16:9 por omissão)."""
    m, mo = MODULOS[modulo], MODOS[modo]
    aspeto = (mo.saida[0] / mo.saida[1]) if aspeto is None else float(aspeto)
    v = fovy_graus(modulo, modo)
    meia_v = math.tan(math.radians(v) / 2.0)
    meia_h = math.atan(aspeto * meia_v)
    meia_d = math.atan(math.hypot(aspeto * meia_v, meia_v))
    return {"vertical": round(v, 2), "horizontal": round(math.degrees(2.0 * meia_h), 2),
            "diag": round(math.degrees(2.0 * meia_d), 2),
            "publicado": dict(m["fov_graus"]), "fator_fov": round(mo.fator_fov, 4)}


# ------------------------------------------------------------------------ modelo de CPU do Raspberry Pi 5
# % de UM núcleo Cortex-A76 @ 2,4 GHz do BCM2712 no modo de referência 1080p50. >100 % = mais que um
# núcleo. O pixel-work do ISP é hardware (0 %); em CPU correm o controlo, as cópias e a codificação.
# Âncoras e faixas: `pesquisas/relatorio-pipeline-camera-rpi5-custo-cpu.md` (medições publicadas);
# o `dominio` diz que taxa de píxeis escala cada etapa ("sensor" = captura, "saida" = imagem de saída).
REF_MODO = "1080p50"
CUSTO_PI5: dict[str, dict] = {
    "aquisicao_csi": {"pct": 2.0, "faixa": "0–3", "dominio": "sensor",
                      "fonte": "CFE/RP1 em hardware (oficial); âncora de software ≤4% medida com preview"},
    "controlo_isp": {"pct": 10.0, "faixa": "8–12", "dominio": "sensor",
                     "fonte": "AGC/AEC/AWB/ALSC por frame + requests (PiSP hardware faz o pixel-work)"},
    "copias_formato": {"pct": 12.0, "faixa": "8–15", "dominio": "saida",
                       "fonte": "RGB888 1080p = 6,2 MB/frame; âncora medida 37% @720p30 (com cópias)"},
    "codificacao_jpeg": {"pct": 65.0, "faixa": "50–80", "dominio": "saida",
                         "fonte": "JPEG SOFTWARE (turbojpeg, 4 threads) — o Pi 5 não tem encoder hardware"},
    "transporte_http": {"pct": 5.0, "faixa": "assumido", "dominio": "fixo",
                        "fonte": "estimativa local (HTTP multipart no mesmo SoC) — SEM fonte publicada"},
}
H264_ALTERNATIVA = {           # só para COMPARAÇÃO no painel: se o stream fosse H.264 (x264 software)
    "rotulo": "H.264 (x264 software, low-latency) — alternativa não usada",
    "pct_1080p30": "60–90", "pct_1080p50": "100–150",
    "fonte": "whitepaper oficial RP-010033-WP-1 (o Pi 5 não tem encoder H.264 hardware)",
}


def _taxa_mp_s(largura: int, altura: int, fps: float) -> float:
    """Megapíxeis por segundo (a moeda do custo de pixel-work)."""
    return largura * altura * fps / 1e6


def custo_cpu(modo: str = OMISSAO_MODO) -> dict:
    """Custo MODELO da câmara no Pi 5 (% de 1 núcleo A76 por etapa + total em núcleos).

    Escala por taxa de píxeis face ao modo de referência 1080p50 (sensor 2304×1296@50 = 149,3 MP/s;
    saída 1920×1080@50 = 103,7 MP/s). As faixas e as fontes de cada etapa vão no resultado — o painel
    mostra-as tal e qual; nada é arredondado para "ficar bonito".
    """
    mo = MODOS[modo]
    ref = MODOS[REF_MODO]
    taxa = {"sensor": _taxa_mp_s(*mo.sensor, mo.fps) / _taxa_mp_s(*ref.sensor, ref.fps),
            "saida": _taxa_mp_s(*mo.saida, mo.fps) / _taxa_mp_s(*ref.saida, ref.fps),
            "fixo": 1.0}
    etapas, total = {}, 0.0
    for nome, base in CUSTO_PI5.items():
        pct = base["pct"] * taxa[base["dominio"]]
        total += pct
        etapas[nome] = {"pct": round(pct, 1), "faixa": base["faixa"], "dominio": base["dominio"],
                        "fonte": base["fonte"]}
    return {"etapas": etapas, "total_pct_nucleo": round(total, 1),
            "total_nucleos": round(total / 100.0, 3), "modo_referencia": REF_MODO,
            "taxa_mp_s": {"sensor": round(_taxa_mp_s(*mo.sensor, mo.fps), 1),
                          "saida": round(_taxa_mp_s(*mo.saida, mo.fps), 1)},
            "comparacao_h264": dict(H264_ALTERNATIVA)}


# --------------------------------------------------------------------------------------- modelo de latência
# Soma de estágios, cada um com a sua origem (medições publicadas para Pi + câmara CSI). Os termos de
# "período de frame" caem quando o modo é mais rápido — por isso o total a 1080p50 (118 ms) sai abaixo da
# faixa publicada para MJPEG 1080p30 (150–300 ms) e o total do MESMO modelo a 1080p30 dá ~163 ms, dentro
# da faixa (verificado; fica dito em `latencia_modelada`).
LATENCIA_ISP_MS = 18.0        # medido: ISP ≈ 18 ms (Pi 4 + CSI, tese Aalto)
LATENCIA_CODIF_REF_MS = 23.0  # medido: codificação 1080p ≈ 23 ms (idem); JPEG software no Pi 5 da mesma ordem
LATENCIA_REDE_MS = 5.0        # assumido: LAN local (SEM fonte publicada — dito no resultado)
LATENCIA_FILA_PERIODO = 2.0   # ASSUMIDO: 2,0 períodos de frame em fila (o `buffer_count=6` do picamera2 é o
#                               nº de BUFFERS alocados, não a latência publicada; 2,0 é escolha de projeto e
#                               põe o total do modelo na faixa publicada a 1080p30 — ver nota do resultado)
LATENCIA_SENSOR_PERIODO = 0.5  # exposição+leitura CSI ≈ meio período
LATENCIA_CLIENTE_PERIODO = 1.0  # o <img> pinta no ciclo seguinte do browser
FAIXA_PUBLICADA_MS = (150.0, 300.0)   # MJPEG 1080p em Pi (comunidade/docs, baixa confiança)


def latencia_modelada(modo: str = OMISSAO_MODO) -> dict:
    """Latência MODELO captura→site (ms) por estágio — e é esta soma que a entrega reproduz."""
    mo = MODOS[modo]
    periodo = 1000.0 * mo.periodo_s
    estagios = {
        "sensor_leitura": round(LATENCIA_SENSOR_PERIODO * periodo, 1),
        "fila_buffers": round(LATENCIA_FILA_PERIODO * periodo, 1),
        "isp": LATENCIA_ISP_MS,
        "codificacao": round(LATENCIA_CODIF_REF_MS * mo.mp_saida / MODOS[REF_MODO].mp_saida, 1),
        "transporte": LATENCIA_REDE_MS,
        "apresentacao": round(LATENCIA_CLIENTE_PERIODO * periodo, 1),
    }
    return {"estagios_ms": estagios, "total_ms": round(sum(estagios.values()), 1),
            "faixa_publicada_ms": list(FAIXA_PUBLICADA_MS),
            "nota": "soma de estágios com origem declarada (ISP e codificação medidos; fila de buffers e "
                    "rede ASSUMIDAS); a faixa publicada para MJPEG 1080p é 150–300 ms — a 1080p30 este "
                    "mesmo modelo dá ~163 ms (dentro da faixa) e a 1080p50 menos, porque os termos de "
                    "período de frame caem com o fps"}


# ------------------------------------------------------------------------------------------------ marcador
# Esfera VISUAL brilhante no mundo — o ponto que a IA guia visual («ver o ponto e seguir») tem de VER na
# imagem. Sem massa e SEM colisão: só a câmara a vê (o simulador é SEMPRE físico — nada de fantasmas na
# dinâmica). O detetor/projeção estão em `experiments/09_drone_hover_rl/visao.py`.
COR_PONTO = (1.0, 0.0, 1.0, 1.0)     # magenta puro — não existe noutra cena
RAIO_PONTO = 0.05                    # m (≈ 27 px de raio a 1,5 m com a lente Wide)


def adicionar_ponto(spec, raio: float = RAIO_PONTO) -> str:
    """Acrescenta a esfera-marcador como CORPO MOCAP (sem junta) de um MjSpec; devolve o nome do geom.

    DECISÃO MEDIDA (2026-10-12): um geom do MUNDO NÃO acompanha `model.geom_pos` — o `mj_forward`
    repõe `data.geom_xpos` em [0,0,0] (verificado em 3.15, modelo mínimo). O caminho certo é um corpo
    **mocap** sem free joint: `nmocap=1`, **nq/nv intactos**, massa 0, e a posição vem de
    `data.mocap_pos` (cinemática de CENÁRIO — o marcador não é um robot, nada de fantasmas na física;
    a regra do simulador físico aplica-se aos corpos dinâmicos).
    """
    corpo = spec.worldbody.add_body(name="ponto", mocap=True)
    mat = spec.add_material(name="ponto_mat")
    mat.rgba = list(COR_PONTO)
    mat.emission = 1.0    # esfera BRILHANTE (emissiva): disco uniforme, centróide sem viés de sombreado
    corpo.add_geom(name="ponto_esfera", type=mujoco.mjtGeom.mjGEOM_SPHERE, size=[float(raio)],
                   material="ponto_mat", contype=0, conaffinity=0, mass=0.0)
    return "marcador"


def mocap_do_ponto(model) -> int:
    """Índice do mocap do marcador (pelo nome, nunca cru)."""
    return int(model.body_mocapid[model.body("ponto").id])


def posicionar_ponto(model, data, pos) -> None:
    """Move o marcador (mocap + `mj_forward` fica na responsabilidade de quem chama, antes de ler/render)."""
    data.mocap_pos[mocap_do_ponto(model)] = [float(v) for v in pos]


def pos_ponto(model, data) -> list:
    return [float(v) for v in data.mocap_pos[mocap_do_ponto(model)]]


# --------------------------------------------------------------------------------------------- montagem
# O drone olha para +x (W = +x). Uma câmara MuJoCo olha ao longo do −z dela própria, por isso a
# pose abaixo põe z_câmara = −x_corpo (a olhar para a frente), y_câmara = +z_corpo (o topo da imagem
# é o topo do drone) e x_câmara = −y_corpo (a direita da imagem é a direita do drone).
XYAXES_FRENTE = (0.0, -1.0, 0.0, 0.0, 0.0, 1.0)


def add_camera_fpv(corpo, pos, fovy: float, nome: str = "fpv") -> None:
    """Acrescenta a câmara FPV (`<camera>`) a um corpo MjSpec, OLHANDO PARA A FRENTE (+x do corpo).

    `pos` é a posição da LENTE no referencial do corpo; `fovy` em GRAUS. ⚠ Verificado no MuJoCo 3.15:
    o `fovy` NÃO segue o `compiler angle` — é SEMPRE graus, tanto no MJCF como em `MjModel.cam_fovy`
    (ao contrário de `range`, que também não converte; um spec em radianos com `fovy=0.785` vira um
    campo de visão de 0,785°, não de 45°). Sem massa nem contacto: uma `<camera>` nunca mexe na física
    (quem tem massa é o geom do módulo, adicionado por quem monta o hardware).
    """
    cam = corpo.add_camera(name=nome, pos=[float(v) for v in pos], fovy=float(fovy))
    cam.quat = quat_para_frente(XYAXES_FRENTE)


def quat_para_frente(xyaxes: tuple[float, float, float, float, float, float] = XYAXES_FRENTE) -> list:
    """Quaternion `[w x y z]` (convenção MuJoCo) da orientação de uma câmara dada pelos `xyaxes` MJCF.

    Os `xyaxes` são (x_câmara, y_câmara) no referencial do corpo; o z é o produto vetorial. O resultado
    é o mesmo que escrever `xyaxes="0 -1 0 0 0 1"` no MJCF — a API `MjsCamera` só expõe `quat`, por isso
    a conversão faz-se aqui (provada contra a pose real da câmara nos testes do experimento).
    """
    eixo_x = np.asarray(xyaxes[:3], dtype=float)
    eixo_y = np.asarray(xyaxes[3:], dtype=float)
    eixo_z = np.cross(eixo_x, eixo_y)
    matriz = np.column_stack([eixo_x, eixo_y, eixo_z])
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, matriz.flatten())
    return [float(v) for v in quat]


def preparar_framebuffer(model) -> None:
    """Garante que o framebuffer offscreen comporta o modo maior (4608×2592) — regra do MuJoCo: a
    resolução de render nunca pode passar `<visual><global offwidth/offheight>`. Aceita o `MjModel`
    (campos `vis`) ou o `MjSpec` (campos `visual`) — nos dois casos o efeito é o mesmo."""
    alvo = model.vis if hasattr(model, "vis") else model.visual
    alvo.global_.offwidth = max(int(alvo.global_.offwidth), 4608)
    alvo.global_.offheight = max(int(alvo.global_.offheight), 2592)


# ---------------------------------------------------------------------------------------------- pipeline
@dataclass
class Quadro:
    """Um quadro do módulo: o JPEG real + toda a cronometragem honesta."""

    seq: int
    jpeg: bytes
    largura: int
    altura: int
    t_captura: float            # instante da captura (relógio de parede, perf_counter)
    t_disponivel: float         # t_captura + latência do modelo (é quando o "site" o pode ver)
    t_codificado: float         # fim do render+ISP+JPEG (custo real deste host)
    bytes: int = 0
    ms_render: float = 0.0
    ms_isp: float = 0.0
    ms_jpeg: float = 0.0

    @property
    def latencia_modelada_ms(self) -> float:
        return 1000.0 * (self.t_disponivel - self.t_captura)

    @property
    def custo_host_ms(self) -> float:
        return self.ms_render + self.ms_isp + self.ms_jpeg


class ModuloCamera:
    """Módulo de câmara emulado: captura (render do MuJoCo) → ISP (recorte/escala) → JPEG → fila.

    · `apontar(data)` copia o estado do simulador (chamar da thread do simulador, a cada passo);
    · `capturar()` faz UM quadro síncrono (pode correr noutra thread; cria o seu contexto GL);
    · `disponiveis()` devolve os quadros cuja latência de modelo já passou — é isto que reproduz a
      latência real: um quadro capturado em `t` só é "visto" em `t + latencia_modelada()`;
    · `estado()` publica o que o painel RPi 5 e a telemetria mostram (fps medido, bytes, CPU modelo,
      custo REAL neste host — sempre separados).

    A cadência (fps) é do MODO e corre ao relógio de parede: quem decide quando capturar é o dono da
    thread (`correr_cadencia` faz o ciclo completo). O módulo pode estar DESLIGADO (`ligar(False)`,
    como um módulo sem alimentação): não captura nem gasta CPU nenhuma.

    FONTE DE IMAGEM (duas, a escolher no construtor):
    · **`camera`** (por omissão): renderiza com a `<camera>` do MODELO (`camera="fpv"` montada à frente
      do drone pelo `add_camera_fpv`) — é o módulo de câmara de bordo, com FoV do modo e custo de CPU
      do Pi 5;
    · **`simulacao`** (`camera_livre=callable`): renderiza com uma `mujoco.MjvCamera` reconfigurada a
      CADA captura por `camera_livre()`, que devolve a câmara livre já com `lookat`/`azimuth`/
      `elevation`/`distance` (ex.: terceira-pessoa a seguir o drone com os ângulos do site). É a vista
      da SIMULAÇÃO, não hardware de bordo: **não tem custo de Pi 5** (`estado()["custo_pi5"]` é `None`
      e leva `nota_fonte` a dizer isso) e o seu **FoV é o GLOBAL do MuJoCo** (`model.vis.global_.fovy`,
      45° por omissão) — o `MjvCamera` livre não tem `fovy` próprio e por isso o FoV do MODO não se
      aplica aqui (o resto do pipeline — modo, tamanho, JPEG, latência, cadência — é exatamente o
      mesmo: é o mesmo módulo emulado).
    """

    def __init__(self, model, camera: str = "fpv", modo: str = OMISSAO_MODO,
                 modulo: str = OMISSAO_MODULO, qualidade: int = QUALIDADE_OMISSAO,
                 com_latencia: bool = True,
                 camera_livre: Callable[[], mujoco.MjvCamera] | None = None) -> None:
        if modo not in MODOS:
            raise ValueError(f"modo {modo!r} não existe — disponíveis: {sorted(MODOS)}")
        if not MODOS[modo].emulado:
            raise ValueError(f"o modo {modo!r} existe no hardware mas NÃO é emulado ({MODOS[modo].nota})")
        if modulo not in MODULOS:
            raise ValueError(f"módulo {modulo!r} não existe — disponíveis: {sorted(MODULOS)}")
        self.camera_livre = camera_livre          # fonte `simulacao`: a pose vem toda do MjvCamera
        if camera_livre is None:
            try:
                self.camera_id = model.camera(camera).id
            except KeyError as erro:
                raise ValueError(f"o modelo não tem a câmara {camera!r} (monte-a com "
                                 f"`camera_rpi.add_camera_fpv`)") from erro
        else:
            # fonte LIVRE: não há `<camera>` do modelo (a pose é do `MjvCamera` a cada captura) e por
            # isso também não há `cam_fovy` nenhum para escrever (o FoV livre é o global do MuJoCo)
            self.camera_id = None
        self.model = model
        self.camera_nome = camera
        self.modulo = modulo
        self.qualidade = int(qualidade)
        self.com_latencia = bool(com_latencia)
        self._modo = MODOS[modo]
        self._renderer = None
        self._render_tamanho = None
        self._pronto = mujoco.MjData(model)      # snapshot publicado pelo simulador
        self._local = mujoco.MjData(model)        # cópia privada de quem renderiza
        self._t_pronto = 0.0
        self._trava = threading.Lock()             # só os snapshots (apontar/_snapshot)
        self._trava_estado = threading.Lock()      # fila + contadores (capturar × disponiveis × estado)
        self._seq = 0
        self._fila: list[Quadro] = []              # quadros ainda por "entregar"
        self._ligada = True
        self._fps = {"t": None, "n": 0, "valor": 0.0}
        self._bytes = {"n": 0, "soma": 0}
        self._host = {"render": 0.0, "isp": 0.0, "jpeg": 0.0}
        self._ultima_entrega = None
        if camera_livre is None:
            self._aplicar_fovy()      # o `fovy` do modelo segue o modo em vigor (o FoV muda com o recorte)

    # -------------------------------------------------------------------------------- controlo do módulo
    def ligar(self, ligada: bool = True, modo: str | None = None) -> dict:
        """Alimentação/streaming do módulo e troca de modo (como no hardware real).

        A troca de modo NÃO escreve no modelo: o FoV aplica-se por CAPTURA (`capturar` escreve
        `model.cam_fovy` na thread que renderiza, imediatamente antes do render) — é a única escrita em
        execução e por isso um render nunca apanha o FoV de outro modo ou de outro `ModuloCamera`.
        """
        if modo is not None:
            if modo not in MODOS:
                raise ValueError(f"modo {modo!r} não existe — disponíveis: {sorted(MODOS)}")
            if not MODOS[modo].emulado:
                raise ValueError(f"o modo {modo!r} existe no hardware mas NÃO é emulado ({MODOS[modo].nota})")
            self._modo = MODOS[modo]
            self._descartar_fila()
        self._ligada = bool(ligada)
        if not self._ligada:
            self._descartar_fila()
        return self.estado()

    @property
    def modo(self) -> str:
        return self._modo.id

    @property
    def ligada(self) -> bool:
        return self._ligada

    def fovy(self) -> float:
        """`fovy` (graus) do modo em vigor (o FoV vertical da janela de captura)."""
        return fovy_graus(self.modulo, self._modo.id)

    def _aplicar_fovy(self) -> None:
        """Põe o `fovy` do modo em vigor no modelo SÓ no arranque (default para quem ler o modelo).

        Em execução quem escreve o FoV é `capturar` (na thread do render, imediatamente antes de cada
        `update_scene`) — uma única escritora, sem corridas entre a troca de modo e o render. ⚠
        `MjModel.cam_fovy` está em GRAUS SEMPRE (não segue o `compiler angle` — verificado em 3.15; ver
        `add_camera_fpv`).

        NÃO se aplica à fonte `simulacao` (`camera_livre`): a `MjvCamera` livre não tem `fovy` próprio
        — usa o GLOBAL do MuJoCo (`model.vis.global_.fovy`) e o FoV do modo não existe aí.
        """
        if self.camera_id is None:                 # fonte livre: sem `<camera>` no modelo
            return
        self.model.cam_fovy[self.camera_id] = self.fovy()

    def configuracao(self) -> dict:
        """Descrição completa do (módulo, modo) em vigor — o site mostra-a como "o que a câmara é"."""
        m = MODULOS[self.modulo]
        livre = self.camera_livre is not None
        return {"fonte": "simulacao" if livre else "camera",
                "nota_fonte": (NOTA_FONTE_SIMULACAO if livre else None),
                "modulo": m["nome"], "modulo_id": self.modulo, "sensor": m["sensor"],
                "sensor_mp": m["mp"], "sensor_px": list(m["resolucao_px"]), "pixel_um": m["pixel_um"],
                "fov_publicado_graus": dict(m["fov_graus"]), "fov_modo_graus": fov_modo(self.modulo,
                                                                                        self._modo.id),
                "lente": dict(m["lente"]), "modo": self._modo.as_dict(),
                "jpeg_qualidade": self.qualidade,
                "latencia_modelada": (latencia_modelada(self._modo.id)
                                      if self.com_latencia else None),
                "custo_pi5": None if livre else custo_cpu(self._modo.id)}

    # -------------------------------------------------------------------------------- captura e codificação
    def apontar(self, data, t: float | None = None) -> None:
        """Publica o estado atual do simulador (thread do simulador — cópia de ~5 µs, não bloqueia).

        ⚠ `t` (opcional) tem de ser do domínio de `time.perf_counter()` — é o relógio da latência do
        modelo; com outro relógio o `t_disponivel` deixa de fazer sentido (a entrega sairia imediata ou
        nunca). A omissão usa o `perf_counter` do momento.
        """
        with self._trava:
            mujoco.mj_copyData(self._pronto, self.model, data)
            self._t_pronto = time.perf_counter() if t is None else float(t)

    def _snapshot(self) -> float:
        with self._trava:
            mujoco.mj_copyData(self._local, self.model, self._pronto)
            return self._t_pronto

    def capturar(self) -> Quadro | None:
        """UM quadro completo (render → recorte do ISP → JPEG) já na proporção da janela do sensor.

        Devolve `None` se o módulo estiver desligado. O quadro sai COM a latência do modelo marcada em
        `t_disponivel` (a entrega faz-se com `disponiveis()`), tal como o pipeline real.
        """
        if not self._ligada:
            return None
        mo = self._modo
        t0 = time.perf_counter()
        t_estado = self._snapshot()
        tamanho = mo.render
        if self._renderer is None or self._render_tamanho != tamanho:   # contexto GL NA thread do render
            preparar_framebuffer(self.model)
            if self._renderer is not None:
                self._renderer.close()
            self._renderer = mujoco.Renderer(self.model, height=tamanho[1], width=tamanho[0])
            self._render_tamanho = tamanho
        # FONTE DE IMAGEM: a `<camera>` do modelo (com o FoV do modo, escrito aqui — única escritora em
        # `model.cam_fovy`, na thread do render) OU a `MjvCamera` livre de `camera_livre()` (fonte
        # `simulacao`; o seu FoV é o GLOBAL do MuJoCo, `model.vis.global_.fovy` — não há FoV de modo).
        if self.camera_livre is not None:
            self._renderer.update_scene(self._local, camera=self.camera_livre())
        else:
            self.model.cam_fovy[self.camera_id] = fovy_graus(self.modulo, mo.id)
            self._renderer.update_scene(self._local, camera=self.camera_nome)
        rgb = self._renderer.render()
        t1 = time.perf_counter()
        img = self._isp(rgb, mo)
        t2 = time.perf_counter()
        jpeg = self._jpeg(img)
        t3 = time.perf_counter()
        self._seq += 1
        latencia = latencia_modelada(mo.id)["total_ms"] / 1000.0 if self.com_latencia else 0.0
        quadro = Quadro(seq=self._seq, jpeg=jpeg, largura=int(img.shape[1]), altura=int(img.shape[0]),
                        t_captura=t_estado or t0, t_disponivel=(t_estado or t0) + latencia,
                        t_codificado=t3, bytes=len(jpeg),
                        ms_render=1000.0 * (t1 - t0), ms_isp=1000.0 * (t2 - t1),
                        ms_jpeg=1000.0 * (t3 - t2))
        with self._trava_estado:                    # fila + contadores (lidos por `disponiveis`/`estado`)
            self._fila.append(quadro)
            self._contabilizar(quadro)
        return quadro

    def _isp(self, rgb: np.ndarray, mo: Modo) -> np.ndarray:
        """Recorte do ISP → a imagem de SAÍDA (uma fatia, quando o modo é mais estreito que a janela).

        O render já sai na proporção EXATA da janela de recorte do sensor (`Modo.render`), por isso o
        ISP aqui só faz o que falta: a fatia central quando a saída é mais estreita que a janela (o
        4:3 do modo 480p120 — recorte ASSUMIDO, dito no modo). Não há redimensionamento: a escala
        sensor→saída do PiSP está contabilizada no custo do Pi, mas o MuJoCo renderiza já na saída.
        """
        largura = rgb.shape[1]
        alvo = mo.saida[0]
        if largura == alvo:
            return rgb
        x0 = (largura - alvo) // 2
        return rgb[:, x0:x0 + alvo]

    def _jpeg(self, img: np.ndarray) -> bytes:
        from PIL import Image
        buffer = io.BytesIO()
        Image.fromarray(img).save(buffer, format="JPEG", quality=self.qualidade)
        return buffer.getvalue()

    def _contabilizar(self, quadro: Quadro) -> None:
        agora = quadro.t_codificado
        f = self._fps
        if f["t"] is None:
            f["t"], f["n"] = agora, 1
        else:
            f["n"] += 1
            if agora - f["t"] >= 1.0:
                f["valor"] = (f["valor"] * 0.4 + 0.6 * (f["n"] - 1) / (agora - f["t"])
                              if f["valor"] else (f["n"] - 1) / (agora - f["t"]))
                f["t"], f["n"] = agora, 1
        self._bytes["n"] += 1
        self._bytes["soma"] += quadro.bytes
        # média móvel (EMA 0,2) do custo REAL por etapa: `estado()` publica a MÉDIA, não o último quadro
        for chave, valor in (("render", quadro.ms_render), ("isp", quadro.ms_isp), ("jpeg", quadro.ms_jpeg)):
            atual = self._host[chave]
            self._host[chave] = valor if atual == 0.0 else 0.8 * atual + 0.2 * valor

    def disponiveis(self, agora: float | None = None) -> list[Quadro]:
        """Quadros cuja latência de modelo já passou, por ordem de captura (e retira-os da fila)."""
        agora = time.perf_counter() if agora is None else float(agora)
        with self._trava_estado:
            prontos = [q for q in self._fila if q.t_disponivel <= agora]
            if prontos:
                self._fila = [q for q in self._fila if q.t_disponivel > agora]
                self._ultima_entrega = agora
        return prontos

    def _descartar_fila(self) -> None:
        with self._trava_estado:
            self._fila.clear()

    def estado(self) -> dict:
        """Estado público do módulo (telemetria + painel RPi 5): honesto, sem números inventados.

        `fonte` diz de onde vem a imagem: `"camera"` (o módulo de bordo, com custo de Pi 5) ou
        `"simulacao"` (a vista da simulação — **não é hardware de bordo**: `custo_pi5` vem `None`, com
        `nota_fonte` a dizer isso; só o `host_ms` medido se aplica).
        """
        mo = self._modo
        livre = self.camera_livre is not None
        with self._trava_estado:                    # instantâneo dos contadores partilhados
            bytes_medio = (self._bytes["soma"] / self._bytes["n"]) if self._bytes["n"] else 0
            fps_medido = self._fps["valor"] if self._fps["valor"] else None
            quadros, fila = self._seq, len(self._fila)
            host = dict(self._host)                 # média móvel do custo REAL por etapa (não o último)
        return {
            "fonte": "simulacao" if livre else "camera",
            "nota_fonte": (NOTA_FONTE_SIMULACAO if livre else None),
            "ligada": self._ligada, "modo": mo.id, "modo_rotulo": mo.rotulo,
            "modulo": MODULOS[self.modulo]["nome"],
            "sensor": list(mo.sensor), "saida": list(mo.saida), "crop": list(mo.crop),
            "mp_sensor": round(mo.mp_sensor, 3), "mp_saida": round(mo.mp_saida, 3),
            "fps_nominal": mo.fps, "fps_medido": None if fps_medido is None else round(fps_medido, 2),
            "jpeg_qualidade": self.qualidade, "bytes_medio": int(bytes_medio),
            "bitrate_mbps": round((bytes_medio * 8.0 / 1e6) * (fps_medido or 0.0), 2) if fps_medido else None,
            "quadros": quadros, "fila": fila,
            # NEM latência de modelo para a vista da simulação (não é hardware de bordo: um
            # atraso de pipeline Pi numa vista do simulador seria uma mentira — entrega imediata)
            "latencia_modelada_ms": (latencia_modelada(mo.id) if self.com_latencia else None),
            # NUNCA custo de Pi para a vista da simulação (honestidade: não é hardware de bordo)
            "custo_pi5": None if livre else custo_cpu(mo.id),
            "host_ms": {"render": round(host["render"], 2), "isp": round(host["isp"], 2),
                        "jpeg": round(host["jpeg"], 2),
                        "total": round(sum(host.values()), 2),
                        "nota": "média móvel do custo REAL deste pipeline nesta máquina (nunca o modelo do Pi)"},
        }

    def fechar(self) -> None:
        """Liberta o renderer (chamar da thread que o criou — o contexto GL é dela)."""
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None


def correr_cadencia(modulo: ModuloCamera, parar, ao_disponivel, passo_estado=None) -> int:
    """Ciclo completo do módulo: captura ao ritmo do modo (relógio de parede) e entrega com latência.

    `parar` é um callable que a thread vigia (`threading.Event` serve); `ao_disponivel(quadro)` recebe
    cada quadro QUANDO a latência de modelo o libera (é aí que se escreve o ficheiro/servidor);
    `passo_estado()` (opcional) é chamado a cada ciclo (ex.: publicar estado). Devolve os quadros feitos.

    É para correr numa thread própria: o contexto GL do render nasce aqui e é libertado aqui. O ESTADO
    do simulador chega por `modulo.apontar(data)` chamado pela THREAD DO SIMULADOR (uma cópia de 5 µs
    por passo de decisão) — esta thread nunca toca no `MjData` a correr. Se o host não der conta do
    modo (ex. 4608×2592 a 14 fps numa máquina lenta), o ciclo NÃO tenta compensar com rajadas: a taxa
    medida desce e o estado mostra-a — como no hardware real.
    """
    feitos = 0
    try:
        proximo = time.perf_counter()
        while not parar():
            periodo = modulo._modo.periodo_s     # relido a cada ciclo: uma troca de modo muda a cadência
            if modulo.ligada:
                modulo.capturar()
                feitos += 1
                for quadro in modulo.disponiveis():
                    ao_disponivel(quadro)
            if passo_estado is not None:
                passo_estado()
            proximo += periodo
            resto = proximo - time.perf_counter()
            if resto > 0:
                time.sleep(resto)
            else:
                proximo = time.perf_counter()      # caímos atrás do ritmo: não acumulamos atraso
    finally:
        modulo.fechar()
    return feitos


__all__ = [
    "MODOS",
    "MODULOS",
    "OMISSAO_MODO",
    "OMISSAO_MODULO",
    "QUALIDADE_OMISSAO",
    "Modo",
    "ModuloCamera",
    "Quadro",
    "add_camera_fpv",
    "correr_cadencia",
    "custo_cpu",
    "fov_modo",
    "fovy_graus",
    "latencia_modelada",
    "modulo_da_peca",
    "preparar_framebuffer",
    "quat_para_frente",
]
