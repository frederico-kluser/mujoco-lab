"""lab/drone_rpi/detalhes/fios.py — CABLAGEM realista do drone (só APARÊNCIA: massa 0, sem contacto, grupo 3).

Cada cabo é um TUBO varrido ao longo de uma curva suave (fichas e abraçadeiras são prismas e fitas fechadas) e tudo o que
tem o mesmo material no mesmo corpo junta-se numa MALHA — os cabos seguem a superfície real (sobem às abraçadeiras CNC
dos tubos, contornam a pilha, dobram nas juntas) com poucos geoms: um por corpo × material.

O que se desenha (bitolas, cores e fichas REAIS — fontes no fim; Ø = diâmetro exterior do fio de silicone):
  · FASES — 3 fios 16 AWG (Ø 3,0 mm) laranja-escuro por motor: o «motor cable» dos ESC T-Motor (16 AWG, 65 mm),
    emendado (termo-retráctil preto) com extensões da mesma bitola até às balas de 3,5 mm dos cabos do motor
    (`motor{k}_fase_{a,b,c}_conector`, módulo `motores`), com a fêmea em termo-retráctil enfiada na bala; presas ao
    tubo com abraçadeiras de nylon de 2,5 mm. No build articulado seguem numa manga entrançada de PET desde a emenda
    (protege-as onde dobram) e cruzam o COTOVELO pelo eixo.
  · ALIMENTAÇÃO dos ESC — par vermelho/preto 14 AWG (Ø 3,5 mm) da saída de entrada do ESC às ilhas da placa de energia
    no topo da pilha (`el_pdb_esc{k}_pos/neg`), a subir pela folga entre a Raspberry Pi e a janela da placa de cima;
    SINAL de cada ESC = par ENTRANÇADO branco/preto (o «twisted-pair throttle signal cable» do AIR 40A) até à ficha
    JST-GH do FC (`el_fc_con_esc`).
  · BATERIA — 10 AWG (Ø 5,5 mm) vermelho/preto dos copos do XT90 macho (`el_xt90_copo_pos/neg`), por trás e por cima
    da placa de cima, até às ilhas da bateria (`el_pdb_bat_pos/neg`); balanceador 6S (7 fios 22 AWG: 1 preto + 6
    vermelhos) até à ficha JST-XH (`el_bat_balanco`). Sem a eletrónica desenha-se o XT90 macho (AMASS) atrás do
    `conector_xt90`.
  · Raspberry Pi 5 — 5 V/5 A da saída do BEC (`el_pdb_saida_5v`) por cabo USB-C com ficha em ângulo (cabo para baixo)
    na `el_rpi5_usbc`; UART do FC (JST-GH em `el_fc_con_rc`) para os pinos 6 (GND), 8 (TXD) e 10 (RXD) do GPIO (ficha
    Dupont 1×3). FPC: 15 vias de 1 mm (16 mm) na Camera Module 3 → 22 vias de 0,5 mm (11,5 mm) no `el_rpi5_cam_disp0`:
    desce à frente da placa, passa por baixo dela, sobe por um rasgo, corre na placa por fora da borda −y da RPi, dobra
    a 45° para subir à borda, e dobra outra vez à frente da trava para entrar no conector ao longo de x.
  · FC — I2C (JST-GH) do `el_fc_con_i2c` para o INA226 da placa de energia (`el_pdb_con_i2c`); sensores de baixo
    (PMW3901 + VL53L1X, com um saltador de 4 fios entre as placas) por um JST-GH que sobe pelo lado +y do pack até ao
    `el_fc_con_gps` (UART livre: o build não tem GPS).
  · Build ARTICULADO — barramento DYNAMIXEL RS-485 («Robot Cable-X4P»: GND/VDD/D+/D−, 21 AWG, fichas JST EHR-04 de
    2,5 mm, cor natural): o regulador de 24 V (`el_fonte24_borne_saida`) alimenta em estrela os 4 servos do ombro e cada
    um passa ao servo do cotovelo; o regulador é alimentado em 18 AWG a partir das ilhas da bateria.

JUNTAS (articulado): um cabo que cruza uma junta é partido num troço POR CORPO (drone / braco{k} / mastro{k}) e os troços
encontram-se num ponto do EIXO da junta, por fora da dobradiça — esse ponto é fixo nos dois corpos, por isso o cabo fica
ligado em qualquer ângulo e DOBRA ali quando a junta roda (o «service loop» real). No ombro passa um FEIXE (manga com a
alimentação, o sinal e o DYNAMIXEL); no cotovelo a manga das fases. A folga ao longo do eixo mede-se com um raio sobre o
próprio eixo contra as peças visíveis que lá estão (as dos outros módulos incluídas); do lado do braço o feixe sai
primeiro para FORA (32 mm do eixo, mais do que o raio da caixa do redutor) antes de voltar ao tubo, para não a cortar
em nenhum ângulo de mira.

ADAPTAÇÃO: o módulo corre DEPOIS de eletronica/motores/estrutura e ancora nas peças deles pelo NOME (acima); quando não
existem (`DRONE_DETALHES=fios`) usa as peças COM MASSA (esc{k}/esc, motor{k}, el_rpi5, el_fc_h7, el_cablagem, camera,
bateria, sensores_baixo, servo_*, fonte_servos) com a MESMA disposição. A superfície dos braços mede-se com raios contra as
peças visíveis — primitivas (`mju_rayGeom`) e as MALHAS dos outros módulos (raio-triângulo vetorizado): o tubo redondo e as
abraçadeiras da estrutura ou a caixa da física. Tudo é opcional (builds sem FC, sem RPi, com ESC 4-em-1, sem câmara CSI,
sem braços…). Substitui os fios simplificados do `modelo.py` (fio_motor*, abracadeira_braco*, cabo_bateria_*).

Fontes (web = dado não confiável, só citado):
  silicone (Ø exterior): https://www.amazon.com/BNTECHGO-Silicone-Flexible-Strands-Stranded/dp/B017TGYW3S (10 AWG 5,5 mm)
    · https://bntechgo.com/bntechgo-14-gauge-silicone-wire-kit-ultra-flexible-200-ft-black-and-red-each-color-100-ft-high-temp-200-c-600v-14-awg-silicone-wire-400-strands-of-tinned-copper-wire-stranded-wire-stranded-wire-for-model-battery
      (14 AWG 3,5 mm) · https://vxb.com/products/16-gauge-silicone-wire-dual-color-spool-red-and-bl (16 AWG 3,0 mm)
    · https://bntechgo.com/bntechgo-20-gauge-silicone-wire-kit-ultra-flexible-6-colors-each-100-ft-high-temp-200-c-600v-20-awg-silicone-wire-100-strands-of-tinned-copper-wire-stranded-wire-for-model-battery
      (20 AWG 1,8 mm)
  ESC T-Motor: https://store.tmotor.com/product/air-40a-6s-esc.html (AIR 40A: cabo de sinal em par entrançado)
    · https://www.ligpower.com/product/alpha-40a-6s-esc.html (alimentação: silicone vermelho/preto 14 AWG 150 mm)
    · https://store.tmotor.com/product/v40a-bldc-foc-drone-esc-14s-60v.html (motor: silicone laranja-escuro 16 AWG 65 mm)
  XT90: https://maxamps.com/products/xt90-male-connector (31 × 21 × 10 mm) · https://www.tme.com/us/en-us/details/xt90s-f/dc-power-connectors/amass (10 AWG)
  Raspberry Pi 5: https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf (85 × 56, furos 3,5/49)
    · https://www.raspberrypi.com/documentation/accessories/camera.html (CAM/DISP na borda dos micro-HDMI, até à Ethernet)
    · https://www.pishop.us/product/raspberry-pi-camera-cable-standard-mini-200mm-v2 (22 vias 0,5 mm ↔ 15 vias 1 mm)
    · https://www.kadidisplay.com/blog-news/15-pin-vs-22-pin-raspberry-pi-dsi-connectors-cable-pinout-and-compatibility (11,5 mm)
    · https://raspberry.tips/en/raspberry-pi-gpio-pinout (pinos 2/4 5 V, 6 GND, 8 TXD, 10 RXD)
  JST-GH 1,25 mm (portas Pixhawk): https://docs.px4.io/main/en/flight_controller/amovlab_flycore
  DYNAMIXEL: https://docs.robotis.com/docs/dxl/model_reference/x_series/xh_series/xh430-w350 (RS-485: JST EHR-04, GND/VDD/D+/D−)
    · https://docs.robotis.com/docs/parts/interface/dxl_bridge (21 AWG) · https://robotis.us/products/dynamixel-xh430-v210-r
      (traz o «Robot Cable-X4P 180 mm») · https://uk.rs-online.com/web/p/wire-housings-plugs/3116221 (EHR-4: 12 × 3,8 mm)
"""
from __future__ import annotations

import itertools
import math
import re
import warnings
from dataclasses import dataclass

import mujoco
import numpy as np

_G = mujoco.mjtGeom
_PRIMITIVAS = {int(_G.mjGEOM_BOX), int(_G.mjGEOM_CAPSULE), int(_G.mjGEOM_CYLINDER), int(_G.mjGEOM_SPHERE),
               int(_G.mjGEOM_ELLIPSOID)}
MM = 0.001
EZ = np.array([0.0, 0.0, 1.0])

# ------------------------------------------------------------------ bitolas (Ø exterior, m) e medidas
D_BAT = 0.0055          # 10 AWG
D_ESC = 0.0035          # 14 AWG
D_FASE = 0.0030         # 16 AWG
D_18 = 0.0023           # 18 AWG (alimentação do regulador de 24 V)
D_5V = 0.0038           # cabo USB-C 5 A (bainha redonda)
D_SINAL = 0.0008        # cada fio do par entrançado do sinal do ESC
D_JST = 0.0009          # 28 AWG (JST-GH)
D_DUPONT = 0.0012       # 26 AWG (fios Dupont)
D_DXL = 0.0032          # cabo DYNAMIXEL X4P (4 × 21 AWG torcidos)
D_BAL = 0.0013          # 22 AWG do balanceador
D_MANGA = 0.0080        # manga entrançada das 3 fases (articulado)
D_FEIXE = 0.0090        # manga do feixe do ombro (articulado)
L_RABICHO = 0.065       # «motor cable» de fábrica dos ESC T-Motor (65 mm)
PASSO_PAR = 0.011       # passo do par entrançado do sinal
LARG_ABRAC, ESP_ABRAC = 0.0025, 0.0011      # abraçadeira de nylon de 2,5 mm
XT90_MACHO = (0.019, 0.020, 0.010)          # parte do macho fora da fêmea: comprimento × largura × altura
FPC_LARG_RPI, FPC_LARG_CAM, FPC_ESP = 0.0115, 0.016, 0.0003
FOLGA_PILHA = 0.0021    # cabos que sobem ao lado da RPi: centro a 2,1 mm da borda (a janela da placa de cima dá 4 mm)
# XH430 da estrutura (para achar as fichas dos servos que ela desenha): largura, altura, profundidade, horn ao topo
SERVO_W, SERVO_H, SERVO_D, HORN_TOPO = 0.0285, 0.0465, 0.034, 0.013

_MATERIAIS = {
    "fios_vermelho": {"rgba": [0.80, 0.06, 0.05, 1.0], "specular": 0.35, "shininess": 0.5},
    "fios_preto": {"rgba": [0.05, 0.05, 0.055, 1.0], "specular": 0.35, "shininess": 0.5},
    "fios_laranja": {"rgba": [0.95, 0.40, 0.05, 1.0], "specular": 0.35, "shininess": 0.5},     # «deep orange» T-Motor
    "fios_branco": {"rgba": [0.90, 0.90, 0.88, 1.0], "specular": 0.3, "shininess": 0.4},
    "fios_amarelo": {"rgba": [0.95, 0.80, 0.10, 1.0], "specular": 0.3, "shininess": 0.4},
    "fios_verde": {"rgba": [0.10, 0.62, 0.25, 1.0], "specular": 0.3, "shininess": 0.4},
    "fios_azul": {"rgba": [0.12, 0.35, 0.85, 1.0], "specular": 0.3, "shininess": 0.4},
    "fios_nylon": {"rgba": [0.07, 0.07, 0.075, 1.0], "specular": 0.55, "shininess": 0.7},      # abraçadeiras
    "fios_termo": {"rgba": [0.03, 0.03, 0.035, 1.0], "specular": 0.15, "shininess": 0.25},     # termo-retráctil
    "fios_manga": {"rgba": [0.17, 0.17, 0.19, 1.0], "specular": 0.6, "shininess": 0.8},        # manga entrançada PET
    "fios_xt90": {"rgba": [0.96, 0.74, 0.05, 1.0], "specular": 0.45, "shininess": 0.6},
    "fios_ouro": {"rgba": [0.86, 0.68, 0.25, 1.0], "specular": 0.8, "shininess": 0.8},
    "fios_fpc": {"rgba": [0.94, 0.92, 0.86, 1.0], "specular": 0.25, "shininess": 0.3},         # FPC branco
    "fios_jst": {"rgba": [0.93, 0.90, 0.81, 1.0], "specular": 0.3, "shininess": 0.4},          # nylon natural JST
    "fios_dupont": {"rgba": [0.06, 0.06, 0.065, 1.0], "specular": 0.4, "shininess": 0.5},
    "fios_dxl": {"rgba": [0.11, 0.11, 0.12, 1.0], "specular": 0.4, "shininess": 0.5},
    "fios_aco": {"rgba": [0.72, 0.73, 0.75, 1.0], "specular": 0.8, "shininess": 0.8},
}

# peças que NÃO são a superfície de um braço/mastro (os cabos não sobem para cima delas)
_NAO_SUPERFICIE = re.compile(r"^(fios_|esc|el_|motor|perna|helice|servo|sem_fim|rpi5|camera|bateria|cinta|sensores|"
                             r"arma|conector|dobradica|corneta|marca_|garfo|projetil|caminho_tiro)", re.IGNORECASE)


# ====================================================================================== geometria
def _u(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _rot_z(z) -> np.ndarray:
    z = _u(z)
    a = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x = _u(np.cross(a, z))
    return np.column_stack([x, np.cross(z, x), z])


def _base(ex, ez) -> np.ndarray:
    """Matriz (colunas = eixos) com x = ex e z o mais perto possível de ez."""
    ex = _u(ex)
    ez = np.asarray(ez, dtype=float) - float(np.dot(ez, ex)) * ex
    if float(np.linalg.norm(ez)) < 1e-9:
        ez = np.cross(ex, EZ) if abs(ex[2]) < 0.9 else np.cross(ex, [1.0, 0.0, 0.0])
    ez = _u(ez)
    return np.column_stack([ex, np.cross(ez, ex), ez])


def _mat_quat(q) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    q = q / max(float(np.linalg.norm(q)), 1e-12)
    r = np.zeros(9)
    mujoco.mju_quat2Mat(r, q)
    return r.reshape(3, 3)


def _pose(g):
    """(tipo, pos, R 3×3, size) de um geom do spec no referencial do corpo dele — resolve o `fromto`."""
    t = int(g.type)
    size = np.array(g.size, dtype=float)
    ft = np.array(g.fromto, dtype=float)
    if (not np.isnan(ft[0]) and float(np.linalg.norm(ft[3:] - ft[:3])) > 1e-9
            and t in (int(_G.mjGEOM_CAPSULE), int(_G.mjGEOM_CYLINDER), int(_G.mjGEOM_BOX), int(_G.mjGEOM_ELLIPSOID))):
        a, b = ft[:3], ft[3:]
        meio = 0.5 * float(np.linalg.norm(b - a))
        size = (np.array([size[0], meio, 0.0]) if t in (int(_G.mjGEOM_CAPSULE), int(_G.mjGEOM_CYLINDER))
                else np.array([size[0], size[1], meio]))
        return t, 0.5 * (a + b), _rot_z(b - a), size
    return t, np.array(g.pos, dtype=float), _mat_quat(g.quat), size


def _aabb(g):
    """Caixa alinhada (lo, hi) de um geom primitivo no referencial do corpo dele (None para malhas/planos)."""
    t, pos, r, s = _pose(g)
    if t in (int(_G.mjGEOM_BOX), int(_G.mjGEOM_ELLIPSOID)):
        h = s
    elif t == int(_G.mjGEOM_SPHERE):
        h = np.array([s[0]] * 3)
    elif t == int(_G.mjGEOM_CAPSULE):
        h = np.array([s[0], s[0], s[1] + s[0]])
    elif t == int(_G.mjGEOM_CYLINDER):
        h = np.array([s[0], s[0], s[1]])
    else:
        return None
    ext = np.abs(r) @ h
    return pos - ext, pos + ext


def _visivel(g) -> bool:
    if int(g.group) not in (0, 3):          # 1/2 = hélices e efeitos (rodam/piscam), 4/5 = escondidos
        return False
    return not (g.material == "" and float(g.rgba[3]) == 0.0)


def _sem_repetidos(pts, tol: float = 1e-6) -> list:
    out = []
    for p in pts:
        p = np.asarray(p, dtype=float)
        if not out or float(np.linalg.norm(p - out[-1])) > tol:
            out.append(p)
    return out


def _curva(pts, raio: float = 0.006, n: int = 6, ang_min: float = 0.05) -> list:
    """Polilinha com os cantos arredondados (Bézier quadrática com `n` pontos em cada vértice de viragem > ang_min rad)."""
    pts = _sem_repetidos(pts)
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, p, b = out[-1], pts[i], pts[i + 1]
        la, lb = float(np.linalg.norm(p - a)), float(np.linalg.norm(b - p))
        if la < 1e-7 or lb < 1e-7:
            continue
        ua, ub = (p - a) / la, (b - p) / lb
        if math.acos(max(-1.0, min(1.0, float(np.dot(ua, ub))))) < ang_min:
            out.append(p)
            continue
        d = min(raio, 0.45 * la, 0.45 * lb)
        pa, pb = p - d * ua, p + d * ub
        out.append(pa)
        for j in range(1, n + 1):
            t = j / (n + 1)
            out.append((1 - t) ** 2 * pa + 2 * (1 - t) * t * p + t ** 2 * pb)
        out.append(pb)
    out.append(pts[-1])
    return out


def _simplificar(pts, tol: float = 0.0004) -> list:
    """Douglas–Peucker: tira os pontos que se afastam < tol da corda (um tubo liso dá um só troço)."""
    pts = _sem_repetidos(pts)
    if len(pts) < 3:
        return pts
    p = np.asarray(pts, dtype=float)
    manter = np.zeros(len(p), dtype=bool)
    manter[0] = manter[-1] = True
    pilha = [(0, len(p) - 1)]
    while pilha:
        i0, i1 = pilha.pop()
        if i1 - i0 < 2:
            continue
        a, ab = p[i0], p[i1] - p[i0]
        lab = float(np.linalg.norm(ab))
        q = p[i0 + 1:i1] - a
        dist = (np.linalg.norm(np.cross(q, ab), axis=1) / lab) if lab > 1e-12 else np.linalg.norm(q, axis=1)
        j = int(np.argmax(dist))
        if dist[j] > tol:
            manter[i0 + 1 + j] = True
            pilha += [(i0, i0 + 1 + j), (i0 + 1 + j, i1)]
    return [p[i] for i in np.flatnonzero(manter)]


def _reamostrar(pts, passo: float) -> list:
    pts = _sem_repetidos(pts)
    if len(pts) < 2:
        return pts
    out = [pts[0]]
    for a, b in itertools.pairwise(pts):
        m = max(1, math.ceil(float(np.linalg.norm(b - a)) / passo))
        out += [a + (b - a) * j / m for j in range(1, m + 1)]
    return out


def _quadros(pts):
    """Tangentes e normais por transporte paralelo (sem torção) ao longo da polilinha."""
    p = np.asarray(pts, dtype=float)
    n = len(p)
    seg = np.diff(p, axis=0)
    seg = seg / np.maximum(np.linalg.norm(seg, axis=1, keepdims=True), 1e-12)
    t = np.zeros((n, 3))
    t[0], t[-1] = seg[0], seg[-1]
    if n > 2:
        t[1:-1] = seg[:-1] + seg[1:]
        fraco = np.linalg.norm(t[1:-1], axis=1) < 1e-9
        t[1:-1][fraco] = seg[1:][fraco]
    t = t / np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    a = EZ if abs(t[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    nn = np.zeros((n, 3))
    v = a - float(a @ t[0]) * t[0]
    nn[0] = v / np.linalg.norm(v)
    for i in range(1, n):
        v = nn[i - 1] - float(nn[i - 1] @ t[i]) * t[i]
        nv = float(np.sqrt(v @ v))
        nn[i] = v / nv if nv > 1e-9 else nn[i - 1]
    return t, nn, np.cross(t, nn)


def _casca(pontos2d) -> np.ndarray:
    """Invólucro convexo (cadeia monótona de Andrew), no sentido anti-horário."""
    pts = sorted({(round(float(x), 7), round(float(y), 7)) for x, y in pontos2d})
    if len(pts) < 3:
        return np.array(pts)

    def cruz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    baixo, cima = [], []
    for p in pts:
        while len(baixo) >= 2 and cruz(baixo[-2], baixo[-1], p) <= 0:
            baixo.pop()
        baixo.append(p)
    for p in reversed(pts):
        while len(cima) >= 2 and cruz(cima[-2], cima[-1], p) <= 0:
            cima.pop()
        cima.append(p)
    return np.array(baixo[:-1] + cima[:-1])


def _laco(casca: np.ndarray, folga: float) -> list:
    """Contorno 2D deslocado para fora `folga` (pela bissetriz de cada vértice)."""
    n = len(casca)
    out = []
    for i in range(n):
        a, p, c = casca[i - 1], casca[i], casca[(i + 1) % n]
        e1, e2 = _u(p - a), _u(c - p)
        n1, n2 = np.array([e1[1], -e1[0]]), np.array([e2[1], -e2[0]])
        nm = _u(n1 + n2)
        out.append(p + nm * folga / max(0.3, float(np.dot(nm, n1))))
    return out


# ====================================================================================== malhas por corpo × material
class _Malhas:
    """Tubos, fitas e prismas acumulados por (corpo, material) e emitidos no fim como UMA malha (geom) por lote."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.lotes: dict[tuple[str, str], list] = {}

    def _juntar(self, corpo: str, mat: str, v, f) -> None:
        lote = self.lotes.setdefault((corpo, mat), [[], [], 0])
        lote[0].append(np.asarray(v, dtype=float))
        lote[1].append(np.asarray(f, dtype=np.int64) + lote[2])
        lote[2] += len(v)

    def _varrer(self, corpo, mat, aneis, tampas=True, fechada=False, apices=None):
        """Faces entre anéis (cada anel com m pontos à volta da tangente) + tampas; normais para fora."""
        nr, m = len(aneis), len(aneis[0])
        f = []
        for i in range(nr - (0 if fechada else 1)):
            i2 = (i + 1) % nr
            for j in range(m):
                j2 = (j + 1) % m
                a, b, c, d = i * m + j, i * m + j2, i2 * m + j, i2 * m + j2
                f += [(a, b, c), (b, d, c)]
        verts = np.vstack([np.asarray(a, dtype=float) for a in aneis])
        if tampas and not fechada:
            ini, fim = apices if apices is not None else (np.mean(aneis[0], axis=0), np.mean(aneis[-1], axis=0))
            k0 = len(verts)
            verts = np.vstack([verts, ini, fim])
            for j in range(m):
                j2 = (j + 1) % m
                f.append((k0, j2, j))
                f.append((k0 + 1, (nr - 1) * m + j, (nr - 1) * m + j2))
        self._juntar(corpo, mat, verts, f)

    def tubo(self, corpo: str, mat: str, pts, d: float, lados: int | None = None) -> None:
        """Cabo redondo de Ø d ao longo dos pontos (já suaves), com as pontas abauladas."""
        pts = _sem_repetidos(pts)
        if len(pts) < 2:
            return
        r = 0.5 * d
        m = lados or (8 if d < 0.0016 else 10 if d < 0.0040 else 14)
        t, nn, bb = _quadros(pts)
        ang = np.linspace(0.0, 2.0 * math.pi, m, endpoint=False)
        cs, sn = np.cos(ang)[:, None], np.sin(ang)[:, None]
        p = np.asarray(pts, dtype=float)
        aneis = [p[0] - 0.62 * r * t[0] + 0.78 * r * (cs * nn[0] + sn * bb[0])]
        aneis += [p[i] + r * (cs * nn[i] + sn * bb[i]) for i in range(len(p))]
        aneis += [p[-1] + 0.62 * r * t[-1] + 0.78 * r * (cs * nn[-1] + sn * bb[-1])]
        self._varrer(corpo, mat, aneis, apices=(p[0] - r * t[0], p[-1] + r * t[-1]))

    def par(self, corpo: str, mat_a: str, mat_b: str, pts, d: float, passo: float = PASSO_PAR) -> None:
        """Par ENTRANÇADO (dois fios de Ø d em hélice um à volta do outro) ao longo dos pontos."""
        pts = _reamostrar(pts, passo / 12.0)
        if len(pts) < 2:
            return
        _t, nn, bb = _quadros(pts)
        s = np.concatenate([[0.0], np.cumsum([np.linalg.norm(b - a) for a, b in itertools.pairwise(pts)])])
        fi = 2.0 * math.pi * s / passo
        p = np.asarray(pts, dtype=float)
        h = (np.cos(fi)[:, None] * nn + np.sin(fi)[:, None] * bb) * (0.5 * d)
        self.tubo(corpo, mat_a, p + h, d, lados=6)
        self.tubo(corpo, mat_b, p - h, d, lados=6)

    def fita(self, corpo: str, mat: str, pts, larg, w_dir, esp: float, fechada: bool = False) -> None:
        """Perfil retangular (FPC, abraçadeira): `larg`/`w_dir` = largura e direção da largura (escalares ou por ponto;
        a direção é ortogonalizada à tangente)."""
        p0 = np.asarray(pts, dtype=float)
        n0 = len(p0)
        larg = np.broadcast_to(np.asarray(larg, dtype=float), (n0,))
        w_dir = np.asarray(w_dir, dtype=float)
        w_dir = np.broadcast_to(w_dir, (n0, 3)) if w_dir.ndim == 1 else w_dir
        manter = [0] + [i for i in range(1, n0) if float(np.linalg.norm(p0[i] - p0[i - 1])) > 1e-6]
        if fechada and len(manter) > 2 and float(np.linalg.norm(p0[manter[0]] - p0[manter[-1]])) < 1e-7:
            manter = manter[:-1]
        if len(manter) < 2:
            return
        p, larg, w_dir = p0[manter], larg[manter], w_dir[manter]
        n = len(p)
        aneis = []
        for i in range(n):
            a, b = (p[(i - 1) % n], p[(i + 1) % n]) if fechada else (p[max(i - 1, 0)], p[min(i + 1, n - 1)])
            t = _u(b - a)
            w = _u(w_dir[i] - float(np.dot(w_dir[i], t)) * t)
            nz = np.cross(t, w)
            hw, he = 0.5 * larg[i], 0.5 * esp
            aneis.append(np.array([p[i] + hw * w + he * nz, p[i] - hw * w + he * nz, p[i] - hw * w - he * nz,
                                   p[i] + hw * w - he * nz]))
        self._varrer(corpo, mat, aneis, tampas=not fechada, fechada=fechada)

    def caixa(self, corpo: str, mat: str, c, r, h) -> None:
        """Prisma retangular de centro c, eixos = colunas de r e meias-medidas h."""
        c, r, h = np.asarray(c, dtype=float), np.asarray(r, dtype=float), np.asarray(h, dtype=float)
        v = [c + r @ (np.array([(i & 1) * 2 - 1, ((i >> 1) & 1) * 2 - 1, ((i >> 2) & 1) * 2 - 1]) * h) for i in range(8)]
        f = [(0, 4, 6), (0, 6, 2), (1, 3, 7), (1, 7, 5), (0, 1, 5), (0, 5, 4), (2, 6, 7), (2, 7, 3), (0, 2, 3),
             (0, 3, 1), (4, 5, 7), (4, 7, 6)]
        self._juntar(corpo, mat, v, f)

    def criar(self) -> int:
        n = 0
        for (corpo, mat), (vs, fs, _k) in self.lotes.items():
            if not vs:
                continue
            nome = f"fios_{corpo}_{mat.removeprefix('fios_')}"
            me = self.ctx.spec.add_mesh(name=f"m_{nome}")
            me.uservert = np.vstack(vs).ravel().tolist()
            me.userface = np.vstack(fs).ravel().tolist()
            me.inertia = mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL
            self.ctx.geom(corpo, nome, type=_G.mjGEOM_MESH, meshname=me.name, material=mat)
            n += 1
        return n


# ====================================================================================== sonda (raios)
@dataclass
class _Caixa:
    corpo: str
    lo: np.ndarray
    hi: np.ndarray

    @property
    def c(self) -> np.ndarray:
        return 0.5 * (self.lo + self.hi)

    @property
    def h(self) -> np.ndarray:
        return 0.5 * (self.hi - self.lo)

    def extensao(self, d) -> float:
        return float(np.abs(np.asarray(d, dtype=float)) @ self.h)

    def topo(self) -> np.ndarray:
        return np.array([self.c[0], self.c[1], self.hi[2]])


class _Triangulos:
    """Triângulos das malhas visíveis de cada corpo (no referencial do corpo), calculados uma vez por montagem."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.por_corpo: dict[str, list] = {}
        self._malhas = None

    def de(self, corpo: str) -> list:
        if corpo not in self.por_corpo:
            if self._malhas is None:
                self._malhas = {m.name: m for m in self.ctx.spec.meshes}
            out = []
            for g in self.ctx.spec.geoms:
                if (g.parent is None or g.parent.name != corpo or int(g.type) != int(_G.mjGEOM_MESH)
                        or (g.name or "").startswith("fios_") or not _visivel(g)):
                    continue
                me = self._malhas.get(g.meshname)
                if me is None:
                    continue
                v = np.asarray(me.uservert, dtype=float).reshape(-1, 3)
                f = np.asarray(me.userface, dtype=np.int64).reshape(-1, 3)
                if len(v) == 0 or len(f) == 0:
                    continue
                esc = np.asarray(me.scale, dtype=float) if hasattr(me, "scale") else np.ones(3)
                v = v * esc
                vb = v @ _mat_quat(g.quat).T + np.array(g.pos, dtype=float)
                out.append((g.name or "", vb[f]))
            self.por_corpo[corpo] = out
        return self.por_corpo[corpo]


class _Sonda:
    """Raios contra as peças VISÍVEIS de um ou mais corpos num referencial comum (juntas a 0: os corpos filhos só estão
    TRANSLADADOS — `corpos` = {nome: origem do corpo}). Primitivas por `mju_rayGeom`; malhas por raio-triângulo
    (Möller–Trumbore vetorizado) — `zona` = (lo, hi) corta o que está longe, `teto` ignora os toques de malha acima."""

    def __init__(self, cena, corpos: dict, excluir=None, zona=None, teto: float | None = None):
        ctx = cena.ctx
        self.teto = teto
        self.perfis: dict = {}
        self.r_tubo: float | None = None
        self.itens = []
        tri = []
        for corpo, nome, t, pos, r, s, bb in cena.geoms_primitivas():
            if corpo not in corpos:
                continue
            if excluir is not None and excluir.search(nome):
                continue
            off = np.asarray(corpos[corpo], dtype=float)
            lo, hi = bb[0] + off, bb[1] + off
            if zona is not None and (np.any(hi < zona[0]) or np.any(lo > zona[1])):
                continue
            self.itens.append((t, np.ascontiguousarray(pos + off), np.ascontiguousarray(r.flatten()),
                               np.ascontiguousarray(s), nome, lo, hi))
        for corpo, off in corpos.items():
            for nome, tt in cena.tri.de(corpo):
                if excluir is not None and excluir.search(nome):
                    continue
                tt = tt + np.asarray(off, dtype=float)
                if zona is not None:
                    lo, hi = tt.min(axis=1), tt.max(axis=1)
                    ok = np.all(hi >= zona[0], axis=1) & np.all(lo <= zona[1], axis=1)
                    tt = tt[ok]
                if len(tt):
                    tri.append(tt)
        if tri:
            tt = np.concatenate(tri)
            self.A, self.E1, self.E2 = tt[:, 0], tt[:, 1] - tt[:, 0], tt[:, 2] - tt[:, 0]
            self.xy_lo, self.xy_hi = tt[:, :, :2].min(axis=1), tt[:, :, :2].max(axis=1)
        else:
            self.A = None

    def _malhas(self, p, v, dmax):
        if self.A is None:
            return None
        if abs(v[2]) > 0.999:          # raio vertical: só os triângulos cuja projeção contém o ponto
            sel = np.flatnonzero((self.xy_lo[:, 0] <= p[0]) & (self.xy_hi[:, 0] >= p[0])
                                 & (self.xy_lo[:, 1] <= p[1]) & (self.xy_hi[:, 1] >= p[1]))
            if len(sel) == 0:
                return None
            a, e1, e2 = self.A[sel], self.E1[sel], self.E2[sel]
        else:
            a, e1, e2 = self.A, self.E1, self.E2
        pv = np.column_stack([v[1] * e2[:, 2] - v[2] * e2[:, 1], v[2] * e2[:, 0] - v[0] * e2[:, 2],
                              v[0] * e2[:, 1] - v[1] * e2[:, 0]])
        det = np.einsum("ij,ij->i", e1, pv)
        ok = np.abs(det) > 1e-14
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = p - a
        uu = np.einsum("ij,ij->i", tv, pv) * inv
        qv = np.column_stack([tv[:, 1] * e1[:, 2] - tv[:, 2] * e1[:, 1], tv[:, 2] * e1[:, 0] - tv[:, 0] * e1[:, 2],
                              tv[:, 0] * e1[:, 1] - tv[:, 1] * e1[:, 0]])
        vv = (qv @ v) * inv
        tt = np.einsum("ij,ij->i", e2, qv) * inv
        m = ok & (uu >= 0.0) & (uu <= 1.0) & (vv >= 0.0) & (uu + vv <= 1.0) & (tt > 1e-7) & (tt <= dmax)
        if self.teto is not None:
            m &= (p[2] + tt * v[2]) <= self.teto
        return float(tt[m].min()) if np.any(m) else None

    def raio(self, p, v, dmax: float, z_passa: float | None = None):
        """Distância da primeira peça ao longo de p + λ·v (λ ≤ dmax), ou None. `z_passa`: das PRIMITIVAS só as que
        passam por essa cota (± 2 mm) — o tubo de um braço, não a placa de cima."""
        p = np.ascontiguousarray(p, dtype=float)
        v = np.ascontiguousarray(_u(v))
        melhor = self._malhas(p, v, dmax)
        for t, pos, mat, s, _nome, lo, hi in self.itens:
            if z_passa is not None and not (lo[2] <= z_passa + 0.002 and hi[2] >= z_passa - 0.002):
                continue
            d = mujoco.mju_rayGeom(pos, mat, s, p, v, t, None)
            if 0.0 <= d <= dmax and (melhor is None or d < melhor):
                melhor = d
        return melhor


@dataclass
class _Braco:
    """p(s, δ, dz) = o + s·u + δ·n + dz·ẑ no referencial do `corpo` (o = eixo do tubo)."""

    k: int
    corpo: str
    o: np.ndarray
    u: np.ndarray
    n: np.ndarray
    h0: float = 0.05        # altura (sobre o eixo) de onde partem os raios de cima

    def p(self, s: float, d: float = 0.0, dz: float = 0.0) -> np.ndarray:
        return self.o + s * self.u + d * self.n + np.array([0.0, 0.0, dz])

    def s(self, q) -> float:
        return float(np.dot(np.asarray(q, dtype=float) - self.o, self.u))

    def d(self, q) -> float:
        return float(np.dot(np.asarray(q, dtype=float) - self.o, self.n))

    def dz(self, q) -> float:
        return float(np.asarray(q, dtype=float)[2] - self.o[2])


def _topo(sonda: _Sonda, b: _Braco, s: float, d: float, omissao: float, lim=(0.0015, 0.03)) -> float:
    """dz do TOPO da superfície do braço em (s, δ): raio de cima (malhas abaixo do teto; primitivas pelo eixo)."""
    h0 = b.h0
    dist = sonda.raio(b.p(s, d, h0), -EZ, h0 + 0.03, z_passa=float(b.o[2]))
    if dist is None:
        return omissao
    dz = h0 - dist
    return dz if lim[0] - 0.012 <= dz <= lim[1] else omissao


def _fundo(sonda: _Sonda, b: _Braco, s: float, d: float, omissao: float) -> float:
    h0 = 0.045
    dist = sonda.raio(b.p(s, d, -h0), EZ, h0 + 0.03, z_passa=float(b.o[2]))
    if dist is None:
        return omissao
    dz = dist - h0
    return dz if -0.04 <= dz <= 0.0 else omissao


def _meia_largura(sonda: _Sonda, b: _Braco, s: float, dz: float, omissao: float) -> float:
    w = []
    for lado in (1.0, -1.0):
        dist = sonda.raio(b.p(s, lado * 0.03, dz), -lado * b.n, 0.03, z_passa=float(b.o[2]))
        w.append(0.03 - dist if dist is not None else omissao)
    v = max(w)
    return v if 0.003 <= v <= 0.03 else omissao


def _perfil(sonda: _Sonda, b: _Braco, s0: float, s1: float, d: float, r: float, omissao: float,
            passo: float = 0.004) -> list:
    """Pontos de um cabo de raio r deitado no topo do braço de s0 a s1 (sobe às abraçadeiras; simplificado). O perfil
    do topo mede-se UMA vez por troço, no eixo do braço (partilhado pelos cabos lado a lado); num tubo redondo o cabo
    afastado δ do topo desce R − √(R² − δ²)."""
    n = max(2, int(abs(s1 - s0) / passo) + 1)
    ss = np.linspace(s0, s1, n)
    chave = (round(s0, 5), round(s1, 5), n)
    cache = sonda.perfis
    if chave not in cache:
        zs = [_topo(sonda, b, s, 0.0, omissao) for s in ss]
        # o cabo não desce a buracos estreitos (< 6 mm) entre peças: máximo deslizante de 3 amostras
        cache[chave] = [max(zs[max(0, i - 1): i + 2]) for i in range(n)]
    if sonda.r_tubo is None:
        s_m = 0.5 * (s0 + s1)
        dz_t, dz_b = _topo(sonda, b, s_m, 0.0, 0.005), _fundo(sonda, b, s_m, 0.0, -0.005)
        w = _meia_largura(sonda, b, s_m, 0.5 * (dz_t + dz_b), 0.012)
        sonda.r_tubo = w if abs(w - 0.5 * (dz_t - dz_b)) < 0.0035 else 0.0
    rt = sonda.r_tubo
    queda = (rt - math.sqrt(max(rt * rt - d * d, 0.0))) if rt > 0.0 and abs(d) < rt else 0.0
    pts = [b.p(s, d, z + r - queda) for s, z in zip(ss, cache[chave], strict=True)]
    return _simplificar(pts, 0.0004)


# ====================================================================================== cena (âncoras)
class _Cena:
    def __init__(self, ctx, malhas: _Malhas):
        self._geoms_prim = None
        self.ctx, self.m = ctx, malhas
        self.hw = ctx.hw
        self.tri = _Triangulos(ctx)
        self.art = bool(ctx.articulado)
        self.placa = self.caixa("placa")
        self.rpi = self.caixa("el_rpi5")
        self.portenta = self.caixa("el_arduino_portenta_h7")
        self.computador = self.rpi if self.rpi is not None else self.portenta
        self.fc = self.caixa("el_fc_h7")
        self.pdb_massa = self.caixa("el_cablagem")
        self.bat = self.caixa("bateria")
        self.cam = self.caixa("camera")
        self.baixo = self.caixa("sensores_baixo")
        self.fonte = self.caixa("fonte_servos")
        self.esc4 = self.caixa("esc")
        self.z_topo = float(self.placa.hi[2]) if self.placa is not None else 0.0
        g = ctx.geom_existente("placa_superior")
        self.z_sup = float(g.pos[2]) if g is not None else None
        try:
            self.sinais = [(1.0 if x >= 0 else -1.0, 1.0 if y >= 0 else -1.0) for x, y in self.hw.pos_rotores]
        except Exception:  # noqa: BLE001
            self.sinais = [(1.0, 1.0), (-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0)]
        cam = getattr(self.hw, "camera", None)
        self.cam_csi = cam is not None and str(cam.dados.get("tipo", "")) == "modulo_camera_csi"

    # ---------------------------------------------------------------- consultas
    def caixa(self, *nomes) -> _Caixa | None:
        lo = hi = corpo = None
        for nome in nomes:
            g = self.ctx.geom_existente(nome)
            if g is None:
                continue
            bb = _aabb(g)
            if bb is None:
                continue
            cg = g.parent.name
            if corpo is None:
                corpo = cg
            elif cg != corpo:
                continue
            lo = bb[0] if lo is None else np.minimum(lo, bb[0])
            hi = bb[1] if hi is None else np.maximum(hi, bb[1])
        return None if lo is None else _Caixa(corpo, lo, hi)

    @staticmethod
    def local(caixa: _Caixa, x0, x1, y0, y1, z0, z1) -> _Caixa:
        """Caixa (mm) no referencial de uma placa: origem no canto (−x, −y) de baixo da caixa com massa."""
        o = np.array([caixa.lo[0], caixa.lo[1], caixa.lo[2]])
        return _Caixa(caixa.corpo, o + np.array([x0, y0, z0]) * MM, o + np.array([x1, y1, z1]) * MM)

    @staticmethod
    def centrada(caixa: _Caixa, x0, x1, y0, y1, z0, z1) -> _Caixa:
        """Caixa (mm) no referencial centrado em xy da caixa com massa, z a partir do fundo dela."""
        o = np.array([caixa.c[0], caixa.c[1], caixa.lo[2]])
        return _Caixa(caixa.corpo, o + np.array([x0, y0, z0]) * MM, o + np.array([x1, y1, z1]) * MM)

    def ancora(self, nome: str, reserva) -> _Caixa | None:
        """A peça `nome` da eletrónica, se existe; senão a caixa de reserva com a mesma disposição (ou None)."""
        cx = self.caixa(nome)
        if cx is not None:
            return cx
        try:
            return reserva()
        except Exception:  # noqa: BLE001 — peça opcional: sem âncora, o cabo não se desenha
            return None

    def geoms_primitivas(self) -> list:
        """As primitivas VISÍVEIS do spec (menos as dos fios), com pose e caixa — calculadas UMA vez por cena: as sondas
        (≈20 por build) liam e convertiam as ~600 peças de cada vez. Os fios só acrescentam `fios_*`, que as sondas
        ignoram, por isso a lista não muda enquanto o módulo corre."""
        if self._geoms_prim is None:
            lista = []
            for g in self.ctx.spec.geoms:
                nome = g.name or ""
                if nome.startswith("fios_") or not _visivel(g):
                    continue
                t = int(g.type)
                if t not in _PRIMITIVAS:
                    continue
                _t, pos, r, s = _pose(g)
                lista.append((g.parent.name if g.parent is not None else "", nome, t, pos, r, s, _aabb(g)))
            self._geoms_prim = lista
        return self._geoms_prim

    def sonda(self, corpos: dict, zona, teto=None, excluir=_NAO_SUPERFICIE) -> _Sonda:
        return _Sonda(self, corpos, excluir, zona=zona, teto=teto)

    # ---------------------------------------------------------------- âncoras da eletrónica (ou a mesma disposição)
    def pdb_pad(self, nome: str) -> _Caixa | None:
        """Ilhas/fichas da placa de energia (`el_pdb_*`), ou as mesmas na caixa `el_cablagem` (a placa fica lá)."""
        def reserva():
            pm = self.pdb_massa
            if pm is None:
                return None
            if nome in ("el_pdb_bat_pos", "el_pdb_bat_neg"):
                y0, y1 = (2.0, 10.0) if nome.endswith("pos") else (-10.0, -2.0)
                return self.centrada(pm, -29.5, -23.5, y0, y1, 1.6, 2.0)
            if nome == "el_pdb_saida_5v":
                return self.centrada(pm, -6.0, 0.0, -20.0, -15.75, 1.6, 4.5)
            if nome == "el_pdb_con_i2c":
                return self.centrada(pm, 25.4, 29.6, -5.0, 5.0, 1.6, 5.85)
            mt = re.match(r"el_pdb_esc(\d)_(pos|neg)", nome)
            if mt:
                sx, sy = self.sinais[int(mt.group(1)) - 1]
                xc = 24.75 if mt.group(2) == "pos" else 19.25
                hx = 2.25 if mt.group(2) == "pos" else 2.0
                return self.centrada(pm, sx * xc - hx, sx * xc + hx, sy * 14.5 - 3.0, sy * 14.5 + 3.0, 1.6, 1.95)
            return None
        return self.ancora(nome, reserva)

    def fc_con(self, nome: str) -> _Caixa | None:
        tabela = {"el_fc_con_esc": (-17.8, -13.55, -4.5, 4.5, 1.6, 4.5),
                  "el_fc_con_gps": (13.4, 17.6, -9.4, -0.6, 1.6, 5.85),
                  "el_fc_con_i2c": (13.4, 17.6, 2.4, 8.6, 1.6, 5.85),
                  "el_fc_con_rc": (-6.1, 0.1, 13.4, 17.6, 1.6, 5.85)}
        return self.ancora(nome, lambda: self.centrada(self.fc, *tabela[nome]) if self.fc is not None else None)

    def rpi_peca(self, nome: str) -> _Caixa | None:
        tabela = {"el_rpi5_usbc": (6.73, 15.67, -1.2, 6.3, 1.6, 4.8),
                  "el_rpi5_cam_disp0": (46.0, 50.5, 2.0, 16.6, 1.6, 3.6),
                  "el_rpi5_cam_disp0_trava": (50.5, 51.5, 2.3, 16.3, 1.6, 3.9),
                  "el_rpi5_gpio_base": (7.1, 57.9, 49.96, 55.04, 1.6, 4.1)}
        return self.ancora(nome, lambda: self.local(self.rpi, *tabela[nome]) if self.rpi is not None else None)

    # ---------------------------------------------------------------- ESC e motores
    def esc_saidas(self, k: int, u: np.ndarray, corpo_braco: str):
        """(corpo, ponto da entrada, ponto das fases, eixo do ESC para fora, eixo lateral): as faces das saídas do AIR 40A
        da eletrónica, ou as pontas da caixa `esc{k}` ao longo do braço. ESC 4-em-1: só as fases (do centro)."""
        ge, gf = self.ctx.geom_existente(f"el_esc{k}_saida_entrada"), self.ctx.geom_existente(f"el_esc{k}_saida_fases")
        if ge is not None and gf is not None:
            _t, pe, re_, se = _pose(ge)
            _t, pf, rf, sf = _pose(gf)
            return ge.parent.name, pe - re_[:, 0] * se[0], pf + rf[:, 0] * sf[0], rf[:, 0], rf[:, 1]
        n = np.array([-u[1], u[0], 0.0])
        esc = self.caixa(f"esc{k}")
        if esc is not None:
            c = esc.c.copy()
            corpo = esc.corpo
            if self.art and esc.corpo == "drone" and self.ctx.existe_corpo(corpo_braco):
                c = c - np.array(self.ctx.corpo(corpo_braco).pos, dtype=float)
                corpo = corpo_braco
            e = esc.extensao(u)
            return corpo, c - e * u, c + e * u, u, n
        if self.esc4 is not None and not self.art:
            e = 0.8 * self.esc4.extensao(u)
            return self.esc4.corpo, None, self.esc4.c + e * u, u, n
        return None

    def balas(self, k: int):
        """As 3 balas de 3,5 mm dos cabos do motor (módulo `motores`): [(corpo, ponta livre, direção, raio da bala)]."""
        out = []
        for f in "abc":
            g = self.ctx.geom_existente(f"motor{k}_fase_{f}_conector")
            if g is None:
                return None
            ft = np.array(g.fromto, dtype=float)
            if np.isnan(ft[0]):
                return None
            out.append((g.parent.name, ft[3:6], _u(ft[3:6] - ft[:3]), float(g.size[0])))
        return out


# ====================================================================================== peças repetidas
def _abracadeira(cena: _Cena, b: _Braco, sonda: _Sonda, s: float, circulos, lado_cabeca: float) -> None:
    """Abraçadeira de nylon de 2,5 mm: fita fechada à volta do invólucro convexo da secção do braço (tubo redondo ou caixa,
    medido com raios) e dos cabos (`circulos` = [(δ, dz, r)]), com a cabeça (fecho) de lado, em cima."""
    dz_t = _topo(sonda, b, s, 0.0, 0.005)
    dz_b = _fundo(sonda, b, s, 0.0, -0.005)
    zc = 0.5 * (dz_t + dz_b)
    w = _meia_largura(sonda, b, s, zc, 0.012)
    pts2 = []
    if abs(w - 0.5 * (dz_t - dz_b)) < 0.0035:          # tubo redondo
        rr = 0.5 * (dz_t - dz_b)
        pts2 += [(rr * math.cos(a), zc + rr * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)]
    else:                                                # caixa
        pts2 += [(x, z) for x in (-w, w) for z in (dz_b, dz_t)]
    for d, dz, r in circulos:
        pts2 += [(d + r * math.cos(a), dz + r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
    casca = _casca(pts2)
    if len(casca) < 3:
        return
    laco = [b.p(s, float(q[0]), float(q[1])) for q in _laco(casca, 0.5 * ESP_ABRAC + 0.0001)]
    cena.m.fita(b.corpo, "fios_nylon", laco, LARG_ABRAC, b.u, ESP_ABRAC, fechada=True)
    alvo = np.array([lado_cabeca, 1.0])
    q = casca[int(np.argmax([float(np.dot(c, alvo)) for c in casca]))]
    nm = _u(q - np.array([0.0, zc]))
    eixo = _u(nm[0] * b.n + nm[1] * EZ)
    c = b.p(s, float(q[0] + nm[0] * 0.0024), float(q[1] + nm[1] * 0.0024))
    cena.m.caixa(b.corpo, "fios_nylon", c, np.column_stack([b.u, eixo, np.cross(b.u, eixo)]), [0.0021, 0.0022, 0.0024])


def _bala_femea(cena: _Cena, corpo: str, p3, dvec, r_c: float) -> np.ndarray:
    """Fêmea de 3,5 mm em termo-retráctil enfiada na bala do motor; devolve o ponto onde o cabo da extensão entra."""
    p3 = np.asarray(p3, dtype=float)
    cena.m.tubo(corpo, "fios_termo", [p3 - 0.0035 * dvec, p3 + 0.011 * dvec], 2.0 * (r_c + 0.0007), lados=12)
    return p3 + 0.008 * dvec


def _ficha_eh(cena: _Cena, corpo: str, q, dq) -> None:
    """Ficha JST EHR-04 (12 × 3,8 × 8,1 mm, nylon natural) encaixada no conector do servo, a sair na direção dq."""
    dq = _u(dq)
    cena.m.caixa(corpo, "fios_jst", np.asarray(q, dtype=float) + 0.0038 * dq, _base(dq, EZ), [0.0040, 0.0058, 0.0030])


def _cantos(cx: _Caixa) -> list:
    return [np.array([x, y, z]) for x in (cx.lo[0], cx.hi[0]) for y in (cx.lo[1], cx.hi[1])
            for z in (cx.lo[2], cx.hi[2])]


def _canto(caixa: _Caixa, b: _Braco) -> float:
    """s (ao longo do braço) a partir do qual o eixo do braço sai da projeção horizontal da caixa."""
    s_lim = math.inf
    for eixo in (0, 1):
        if abs(b.u[eixo]) > 1e-6:
            alvo = caixa.hi[eixo] if b.u[eixo] > 0 else caixa.lo[eixo]
            s_lim = min(s_lim, float((alvo - b.o[eixo]) / b.u[eixo]))
    return max(0.0, s_lim) if math.isfinite(s_lim) else 0.0


def _posicoes_abracadeiras(s0: float, s1: float, pedidas) -> list:
    """As posições pedidas que caem no troço [s0, s1] (a ≥ 3 cm umas das outras); troço curto → uma só, a meio."""
    if s1 - s0 < 0.01:
        return []
    out = []
    for s in sorted(pedidas):
        if s0 <= s <= s1 and all(abs(s - q) > 0.03 for q in out):
            out.append(s)
    return out or [0.5 * (s0 + s1)]


def _subida(cena: _Cena, k: int, i: int, d: float = D_ESC) -> np.ndarray | None:
    """Ponto (xy) por onde o cabo i do braço k sobe ao lado da pilha (RPi/Portenta): na folga entre a placa e a janela da
    placa de cima, longe dos cantos arredondados da janela e das portas que saem das bordas."""
    comp = cena.computador if cena.computador is not None else cena.pdb_massa
    if comp is None:
        return None
    sx, sy = cena.sinais[k - 1]
    folga = FOLGA_PILHA + max(0.0, 0.5 * d - 0.00175)
    passo = 0.0038
    if sx > 0:      # braços da frente: sobem pela borda ±y perto do canto da frente (as portas USB/RJ45 saem em +x)
        return np.array([comp.c[0] + comp.h[0] - 0.0105 - i * passo, comp.c[1] + sy * (comp.h[1] + folga)])
    # braços de trás: sobem pela borda de trás (−x), fora do cartão microSD e do botão
    return np.array([comp.c[0] - comp.h[0] - folga, comp.c[1] + sy * (comp.h[1] - 0.0065 - i * passo)])


# ====================================================================================== energia e sinal dos ESC
def _alimentacao_e_sinal(cena: _Cena, k: int, b: _Braco, sonda: _Sonda, p_ent, ux, uy, lado: float,
                         feixe=None) -> None:
    """Par 14 AWG da entrada do ESC às ilhas da placa de energia e o par entrançado do sinal até à ficha do FC.
    Rígido: correm no topo do tubo e sobem ao lado da pilha. Articulado (`feixe`): do ESC à ponta do feixe no braço e,
    no drone, da outra ponta do feixe (na placa de cima) direitos às ilhas/ficha."""
    m = cena.m
    r_e = 0.5 * D_ESC
    s_e = b.s(p_ent)
    comp = cena.computador if cena.computador is not None else cena.pdb_massa
    s_lim = max(0.035, _canto(comp, b) + 0.006) if comp is not None else 0.05
    fios = (("pos", "fios_vermelho", -0.75 * D_ESC), ("neg", "fios_preto", 0.45 * D_ESC))
    topo_e = []
    for i, (polo, mat, lat) in enumerate(fios):
        p0 = p_ent + lat * uy + 0.003 * ux
        d_i = b.d(p0)
        pad = cena.pdb_pad(f"el_pdb_esc{k}_{polo}")
        alvo = None if pad is None else pad.topo() + np.array([0.0, 0.0, r_e - 0.0002])
        if feixe is not None:
            pts_b, pts_d = feixe(i, d_i, p0)
            m.tubo(b.corpo, mat, _curva(pts_b, 0.008), D_ESC)
            if alvo is not None:
                fim = pts_d[-1]
                z_v = max(float(alvo[2]) + 0.004, float(fim[2]))
                pts = [*pts_d, np.array([alvo[0] + 0.012 * cena.sinais[k - 1][0], alvo[1] + 0.012 *
                                         cena.sinais[k - 1][1], z_v]), alvo + np.array([0, 0, 0.0015]), alvo]
                m.tubo("drone", mat, _curva(pts, 0.008), D_ESC)
            continue
        sub = _subida(cena, k, i)
        corpo_pts = _perfil(sonda, b, s_e - 0.012, s_lim + 0.012, d_i, r_e, 0.005)
        pts = [p0, p0 - 0.006 * ux, *corpo_pts]
        topo_e.append(max(b.dz(q) for q in corpo_pts))
        if alvo is not None and sub is not None:
            z_base = float(corpo_pts[-1][2])
            pts += [np.array([sub[0], sub[1], z_base]), np.array([sub[0], sub[1], float(alvo[2]) + 0.002]),
                    0.5 * (np.array([sub[0], sub[1], alvo[2]]) + alvo) + np.array([0, 0, 0.0012]), alvo]
        m.tubo("drone", mat, _curva(pts, 0.007), D_ESC)
    # sinal: par entrançado branco/preto ao lado do vermelho, até à ficha JST-GH do FC
    con = cena.fc_con("el_fc_con_esc")
    lat_s = -0.75 * D_ESC - r_e - D_SINAL - 0.0004
    p0 = p_ent + lat_s * uy + 0.003 * ux
    d_s = b.d(p0)
    if feixe is not None:
        pts_b, pts_d = feixe(2, d_s, p0)
        m.par(b.corpo, "fios_branco", "fios_preto", _curva(pts_b, 0.008), D_SINAL)
        pts = list(pts_d)
    else:
        corpo_pts = _perfil(sonda, b, s_e - 0.012, s_lim + 0.012, d_s, D_SINAL, 0.005)
        pts = [p0, p0 - 0.006 * ux, *corpo_pts]
        sub = _subida(cena, k, 2, d=2 * D_SINAL)
        if sub is not None:
            pts.append(np.array([sub[0], sub[1], float(pts[-1][2])]))
    if con is not None and cena.fc is not None:
        _sx, sy = cena.sinais[k - 1]
        z_c = float(con.c[2])
        z_cima = float(cena.fc.hi[2]) + 0.0035
        y_lado = float(cena.fc.c[1]) + sy * (float(cena.fc.h[1]) + 0.0028)
        x_tras = float(con.lo[0]) - 0.0075
        dy = {1: 0.0034, 4: -0.0034, 3: 0.0011, 2: -0.0011}.get(k, 0.0)
        x_0 = float(pts[-1][0])
        pts += [np.array([x_0, float(pts[-1][1]), z_cima]), np.array([x_0, y_lado, z_cima]),
                np.array([x_tras, y_lado, z_cima]), np.array([x_tras - 0.002, float(con.c[1]) + dy, z_c]),
                np.array([float(con.lo[0]) - 0.003, float(con.c[1]) + dy, z_c])]
    m.par("drone", "fios_branco", "fios_preto", _curva(pts, 0.006), D_SINAL)
    if feixe is None and topo_e:
        circ = [(b.d(p_ent + lat * uy), max(topo_e), r_e) for _p, _mm, lat in fios]
        circ.append((d_s, max(topo_e) - r_e + D_SINAL, D_SINAL))
        for s_ab in _posicoes_abracadeiras(s_lim + 0.015, s_e - 0.015, (s_e - 0.05, 0.5 * (s_e + s_lim) + 0.01)):
            _abracadeira(cena, b, sonda, s_ab, circ, -lado)


# ====================================================================================== braços — RÍGIDO
def _braco_rigido(cena: _Cena, k: int) -> None:
    ctx, m = cena.ctx, cena.m
    mot = cena.caixa(f"motor{k}")
    if mot is None or cena.placa is None:
        return
    gb = ctx.geom_existente(f"braco{k}")
    z_eixo = float(gb.pos[2]) if gb is not None else float(cena.placa.c[2])
    o = np.array([cena.placa.c[0], cena.placa.c[1], z_eixo])
    u = _u([mot.c[0] - o[0], mot.c[1] - o[1], 0.0])
    n = np.array([-u[1], u[0], 0.0])
    h0 = 0.05 if cena.z_sup is None else min(0.05, cena.z_sup - 0.0025 - z_eixo)
    b = _Braco(k, "drone", o, u, n, h0=h0)
    s_mot = b.s(mot.c)
    a0, a1 = b.p(0.03), b.p(s_mot + 0.05)
    teto = None if cena.z_sup is None else cena.z_sup - 0.002
    sonda = cena.sonda({"drone": np.zeros(3)}, (np.minimum(a0, a1) - 0.06, np.maximum(a0, a1) + 0.06), teto=teto)
    saidas = cena.esc_saidas(k, u, "drone")
    if saidas is None:
        return
    _corpo_esc, p_ent, p_fas, ux, uy = saidas
    lado = 1.0 if k % 2 == 1 else -1.0
    r_f = 0.5 * D_FASE
    balas = cena.balas(k)
    # ---------------- FASES: rabicho laranja do ESC → emenda (termo) → extensão → fêmea na bala do motor
    s_f = b.s(p_fas)
    s_fim = (min(b.s(q[1]) for q in balas) - 0.035) if balas is not None else s_mot - float(mot.h[0]) - 0.012
    ds = []
    for i, lat in enumerate((-1.07 * D_FASE, 0.0, 1.07 * D_FASE)):
        p0 = p_fas + lat * uy - 0.003 * ux
        d_i = b.d(p0)
        ds.append(d_i)
        corpo_pts = _perfil(sonda, b, s_f + 0.012, s_fim, d_i, r_f, 0.005)
        pts = [p0, p0 + 0.006 * ux, *corpo_pts]
        if balas is not None:
            _c, p3, dv, r_c = balas[i]
            ent = _bala_femea(cena, "drone", p3, dv, r_c)
            pts += [ent + 0.016 * dv, ent]
        else:
            z_b = float(mot.lo[2]) - z_eixo + 0.0025
            pts += [b.p(s_mot - float(mot.h[0]) + 0.003, 0.7 * d_i, max(z_b, b.dz(corpo_pts[-1])))]
        m.tubo("drone", "fios_laranja", _curva(pts, 0.008), D_FASE)
        s_j = s_f + L_RABICHO
        if s_j < s_fim - 0.012:                 # emenda do rabicho de fábrica (só se o troço chega lá)
            dz_j = _topo(sonda, b, s_j, d_i, 0.005) + r_f
            m.tubo("drone", "fios_termo", [b.p(s_j - 0.008, d_i, dz_j), b.p(s_j + 0.008, d_i, dz_j)], D_FASE + 0.0009)
    for s_ab in _posicoes_abracadeiras(s_f + 0.02, s_fim - 0.01, (s_f + 0.115, 0.5 * (s_f + s_fim) + 0.03,
                                                                 s_fim - 0.025)):
        dz_w = _topo(sonda, b, s_ab, 0.0, 0.005) + r_f
        _abracadeira(cena, b, sonda, s_ab, [(d, dz_w, r_f) for d in ds], lado)
    # ---------------- ALIMENTAÇÃO 14 AWG + SINAL (par entrançado)
    if p_ent is not None:
        _alimentacao_e_sinal(cena, k, b, sonda, p_ent, ux, uy, lado)


# ====================================================================================== braços — ARTICULADO
def _folga_eixo(cena: _Cena, corpo_pai: str, corpo_filho: str, origem_filho, sinal: float, t_max: float = 0.10) -> float:
    """|t| a partir do qual o EIXO da junta (y do corpo, pela origem do filho) está livre do lado `sinal`: um raio sobre o
    próprio eixo, de fora para dentro, contra as peças visíveis dos dois corpos (primitivas e malhas)."""
    o = np.asarray(origem_filho, dtype=float)
    sonda = cena.sonda({corpo_pai: np.zeros(3), corpo_filho: o}, (o - 0.12, o + 0.12),
                       excluir=re.compile(r"^fios_|^perna|^helice", re.IGNORECASE))
    dist = sonda.raio(o + np.array([0.0, sinal * t_max, 0.0]), [0.0, -sinal, 0.0], t_max)
    return t_max - dist if dist is not None else 0.0


def _estrutura_ativa(cena: _Cena, k: int, junta: str) -> bool:
    g = cena.ctx.geom_existente(f"servo_{junta}{k}")
    return g is not None and not _visivel(g)


def _servo_conectores(cena: _Cena, k: int, junta: str):
    """[(corpo, ponto na face da ficha JST EH, direção para fora)] dos 2 conectores do servo: os do XH430 desenhado pela
    estrutura (deitado na placa de cima no ombro; no cotovelo com o eixo no da junta) ou na face da caixa com massa."""
    ctx = cena.ctx
    sx, sy = cena.sinais[k - 1]
    M = np.diag([sx, sy, 1.0])
    x0 = HORN_TOPO - SERVO_H
    nome = f"servo_{junta}{k}"
    if junta == "ombro":
        if _estrutura_ativa(cena, k, junta) and cena.z_sup is not None:
            P = np.array(ctx.corpo(f"braco{k}").pos, dtype=float)
            o = P + M @ np.array([-0.014, -0.028, 0.0])
            o[2] = cena.z_sup + 0.0012 + 0.003
            return [("drone", o + M @ np.array([x0 - 0.0056, lado * 0.0068, 0.0262]), M @ np.array([-1.0, 0.0, 0.0]))
                    for lado in (-1.0, 1.0)]
        cx = cena.caixa(nome)
        if cx is None:
            return None
        x = cx.lo[0] if sx > 0 else cx.hi[0]
        return [("drone", np.array([x, cx.c[1] + lado * 0.0068, cx.lo[2] + 0.010]), np.array([-sx, 0.0, 0.0]))
                for lado in (-1.0, 1.0)]
    L = np.array(ctx.corpo(f"mastro{k}").pos, dtype=float)
    if _estrutura_ativa(cena, k, junta):
        return [(f"braco{k}", L + M @ np.array([x0 - 0.0056, -0.5 * SERVO_D + 0.0262, lado * 0.0068]),
                 M @ np.array([-1.0, 0.0, 0.0])) for lado in (-1.0, 1.0)]
    cx = cena.caixa(nome)
    if cx is None:
        return None
    x = cx.lo[0] if sx > 0 else cx.hi[0]
    return [(f"braco{k}", np.array([x, cx.c[1], cx.c[2] + lado * 0.0068]), np.array([-sx, 0.0, 0.0]))
            for lado in (-1.0, 1.0)]


def _caixa_servo_cotovelo(cena: _Cena, k: int) -> _Caixa | None:
    """Extensão do servo do cotovelo no braço: o XH430 da estrutura (centrado no eixo, + garfo) ou a caixa com massa."""
    sx, sy = cena.sinais[k - 1]
    if _estrutura_ativa(cena, k, "cotovelo"):
        L = np.array(cena.ctx.corpo(f"mastro{k}").pos, dtype=float)
        x0 = HORN_TOPO - SERVO_H
        a = L + np.diag([sx, sy, 1.0]) @ np.array([x0, -0.0225, -0.5 * SERVO_W - 0.003])
        b = L + np.diag([sx, sy, 1.0]) @ np.array([HORN_TOPO, 0.0225, 0.5 * SERVO_W])
        return _Caixa(f"braco{k}", np.minimum(a, b), np.maximum(a, b))
    return cena.caixa(f"servo_cotovelo{k}")


def _raio_mastro(cena: _Cena, nm: str, z: float) -> float:
    """Raio da superfície do mastro à altura z (raios de fora para dentro): o tubo Ø16 da estrutura ou o da física."""
    sonda = cena.sonda({nm: np.zeros(3)}, (np.array([-0.05, -0.05, z - 0.01]), np.array([0.05, 0.05, z + 0.01])),
                       excluir=re.compile(r"^fios_|^motor|^helice|^suporte", re.IGNORECASE))
    out = []
    for v in ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)):
        dist = sonda.raio([0.05 * v[0], 0.05 * v[1], z], [-v[0], -v[1], 0.0], 0.05)
        if dist is not None:
            out.append(0.05 - dist)
    r = min(out) if out else 0.008
    return r if 0.004 <= r <= 0.02 else 0.008


def _abracadeira_mastro(cena: _Cena, corpo: str, dirn, r_tubo: float, r_m: float, z: float) -> None:
    """Abraçadeira à volta do mastro e da manga encostada à face `dirn`."""
    dirn = _u([dirn[0], dirn[1], 0.0])
    perp = np.array([-dirn[1], dirn[0], 0.0])
    pts2 = [(r_tubo * math.cos(a), r_tubo * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 36, endpoint=False)]
    pts2 += [(r_tubo + r_m + r_m * math.cos(a), r_m * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 16,
                                                                                         endpoint=False)]
    laco = [float(q[0]) * dirn + float(q[1]) * perp + np.array([0.0, 0.0, z])
            for q in _laco(_casca(pts2), 0.5 * ESP_ABRAC + 0.0001)]
    cena.m.fita(corpo, "fios_nylon", laco, LARG_ABRAC, EZ, ESP_ABRAC, fechada=True)


def _braco_articulado(cena: _Cena, k: int) -> None:
    ctx, m = cena.ctx, cena.m
    nb, nm = f"braco{k}", f"mastro{k}"
    if not (ctx.existe_corpo(nb) and ctx.existe_corpo(nm)) or cena.placa is None:
        return
    S = np.array(ctx.corpo(nb).pos, dtype=float)          # eixo do ombro (no drone)
    E = np.array(ctx.corpo(nm).pos, dtype=float)          # eixo do cotovelo (no braço)
    u = _u([E[0], E[1], 0.0])
    n = np.array([-u[1], u[0], 0.0])
    l1 = float(np.linalg.norm(E[:2]))
    bb = _Braco(k, nb, np.zeros(3), u, n, h0=0.05)
    _Braco(k, "drone", np.array([cena.placa.c[0], cena.placa.c[1], S[2]]), u, n)
    a0, a1 = bb.p(-0.02), bb.p(l1 + 0.02)
    sonda_b = cena.sonda({nb: np.zeros(3)}, (np.minimum(a0, a1) - 0.06, np.maximum(a0, a1) + 0.06))
    sx, sy = cena.sinais[k - 1]
    M = np.diag([sx, sy, 1.0])
    lado = 1.0 if k % 2 == 1 else -1.0
    saidas = cena.esc_saidas(k, u, nb)
    if saidas is None:
        return
    corpo_esc, p_ent, p_fas, ux, uy = saidas
    if corpo_esc == "drone":                 # ESC sem corpo do braço — passa para o referencial do braço
        p_ent = None if p_ent is None else p_ent - S
        p_fas = p_fas - S
    servo_c = _caixa_servo_cotovelo(cena, k)
    s_servo = min(bb.s(c) for c in _cantos(servo_c)) if servo_c is not None else l1 - 0.05

    # ---------------- COTOVELO: a manga das fases cruza do lado do eixo com menos peças
    t_mais, t_menos = _folga_eixo(cena, nb, nm, E, 1.0), _folga_eixo(cena, nb, nm, E, -1.0)
    lado_c = -sy if abs(t_mais - t_menos) < 0.004 else (1.0 if t_mais < t_menos else -1.0)
    r_m = 0.5 * D_MANGA
    t_cot = max(t_mais if lado_c > 0 else t_menos, 0.022) + r_m + 0.002
    X_cb = E + np.array([0.0, lado_c * t_cot, 0.0])
    X_cm = np.array([0.0, lado_c * t_cot, 0.0])
    lado_d = math.copysign(1.0, bb.d(X_cb))

    # ---------------- FASES: rabichos → manga entrançada → cotovelo pelo eixo → mastro → balas do motor
    s_f = bb.s(p_fas)
    s_m0 = s_f + L_RABICHO
    dz_m0 = _topo(sonda_b, bb, s_m0, 0.0, 0.005) + r_m
    for lat in (-1.07 * D_FASE, 0.0, 1.07 * D_FASE):
        p0 = p_fas + lat * uy - 0.003 * ux
        d0 = bb.d(p0)
        pts = [p0, p0 + 0.008 * ux, bb.p(s_f + 0.03, d0, _topo(sonda_b, bb, s_f + 0.03, d0, 0.005) + 0.5 * D_FASE),
               bb.p(s_m0 + 0.004, 0.3 * lat, dz_m0)]
        m.tubo(nb, "fios_laranja", _curva(pts, 0.008), D_FASE)
    s_m1 = s_servo - 0.045
    manga = _perfil(sonda_b, bb, s_m0, s_m1, 0.0, r_m, 0.005)
    d_contorno = 0.026
    if servo_c is not None:
        d_contorno = max([abs(bb.d(c)) for c in _cantos(servo_c) if bb.d(c) * lado_d > 0] + [d_contorno])
    d_contorno = max(d_contorno, abs(bb.d(X_cb))) + r_m + 0.003
    contorno = bb.p(s_servo - 0.008, lado_d * d_contorno, 0.002)
    junto = bb.p(bb.s(X_cb) - 0.010, lado_d * d_contorno, 0.0)
    m.tubo(nb, "fios_manga", _curva([*manga, contorno, junto, X_cb], 0.012), D_MANGA)
    m.tubo(nb, "fios_termo", [bb.p(s_m0 - 0.006, 0.0, dz_m0), bb.p(s_m0 + 0.010, 0.0, dz_m0)], D_MANGA + 0.0012)
    balas = cena.balas(k)
    mot = cena.caixa(f"motor{k}")
    if mot is None:
        return
    # mastro: sobe por fora do garfo, passa à face de dentro (−u) acima da abraçadeira e sobe até às balas
    z_alto = 0.078
    r_face = _raio_mastro(cena, nm, 0.11) + r_m
    p_cima = np.array([0.0, lado_c * t_cot, 0.062])
    p_face = -u * r_face + np.array([0.0, 0.0, z_alto])
    z_fim = (min(float(q[1][2]) for q in balas) - 0.026) if balas is not None else float(mot.lo[2]) - 0.035
    p_fim = -u * r_face + np.array([0.0, 0.0, z_fim])
    m.tubo(nm, "fios_manga", _curva([X_cm, p_cima, p_face, p_fim], 0.012), D_MANGA)
    m.tubo(nm, "fios_termo", [p_fim - np.array([0, 0, 0.012]), p_fim + np.array([0, 0, 0.004])], D_MANGA + 0.0012)
    for i, lat in enumerate((-1.07 * D_FASE, 0.0, 1.07 * D_FASE)):
        a = p_fim + np.array([0.0, 0.0, 0.002]) + 0.33 * lat * n
        if balas is not None:
            _c, p3, dv, r_c = balas[i]
            ent = _bala_femea(cena, nm, p3, dv, r_c)
            pts = [a, a + np.array([0.0, 0.0, 0.006]), ent + 0.012 * dv, ent]
        else:
            r_mot = float(mot.h[0])
            pts = [a, a + np.array([0.0, 0.0, 0.006]),
                   -u * (r_mot - 0.004) + lat * n + np.array([0.0, 0.0, float(mot.lo[2]) + 0.004])]
        m.tubo(nm, "fios_laranja", _curva(pts, 0.006), D_FASE)
    _abracadeira_mastro(cena, nm, -u, r_face - r_m, r_m, 0.5 * (z_alto + z_fim) + 0.01)

    # ---------------- OMBRO: feixe (alimentação + sinal + DYNAMIXEL) pelo eixo, do lado de fora do redutor (−b)
    r_h = 0.5 * D_FEIXE
    lado_p = -sy
    t_omb = max(_folga_eixo(cena, "drone", nb, S, lado_p), 0.02) + r_h + 0.0015
    X_d = S + np.array([0.0, lado_p * t_omb, 0.0])
    X_b = np.array([0.0, lado_p * t_omb, 0.0])
    w_tubo = _meia_largura(sonda_b, bb, 0.10, 0.0, 0.012)
    lado_h = math.copysign(1.0, bb.d(X_b)) if abs(bb.d(X_b)) > 1e-6 else -lado_d
    A = bb.p(0.090, lado_h * (w_tubo + r_h + 0.0005), 0.0)
    saida_b = np.array([sx * 0.032, X_b[1], 0.004])
    m.tubo(nb, "fios_manga", _curva([X_b, saida_b, A], 0.014), D_FEIXE)
    # lado do drone: sobe à placa de cima pelo lado do eixo e entra para dentro (por baixo do servo deitado)
    z_mesa = (cena.z_sup + 0.0012 if cena.z_sup is not None else cena.z_topo + 0.004) + r_h
    W1 = np.array([X_d[0], X_d[1], z_mesa])
    W2 = W1 + M @ np.array([-0.045, 0.0, 0.0])
    m.tubo("drone", "fios_manga", _curva([X_d, X_d + np.array([0, 0, 0.6 * (z_mesa - X_d[2])]), W1, W2], 0.012),
           D_FEIXE)
    dir_b = _u(A - saida_b)
    dir_d = _u(W2 - W1)
    for corpo, c, dv in ((nb, A, dir_b), ("drone", W2, dir_d)):      # termo-retráctil nas pontas do feixe
        m.tubo(corpo, "fios_termo", [c - 0.014 * dv, c + 0.001 * dv], D_FEIXE + 0.0012)

    def feixe(i, d_i, p0):
        """Pontos do fio i no braço (da ponta do feixe ao ESC) e no drone (da ponta do feixe na placa de cima)."""
        off = (i - 1) * 0.0022
        lat_b = _u(np.cross(dir_b, EZ))
        ini = A - 0.006 * dir_b + off * lat_b
        top = bb.p(0.13, d_i, _topo(sonda_b, bb, 0.13, d_i, 0.005) + 0.5 * D_ESC)
        borda = bb.p(0.112, lado_h * (w_tubo + 0.0015), _topo(sonda_b, bb, 0.112, 0.0, 0.005) - 0.001)
        pts_b = [ini, ini + 0.010 * dir_b, borda, top, p0 - 0.006 * ux, p0]
        lat_d = _u(np.cross(dir_d, EZ))
        fim = W2 - 0.006 * dir_d + off * lat_d
        return pts_b, [fim, fim + 0.012 * dir_d]

    if p_ent is not None:
        _alimentacao_e_sinal(cena, k, bb, sonda_b, p_ent, ux, uy, lado, feixe=feixe)
    # DYNAMIXEL: servo do ombro → feixe → braço (pelo lado do tubo) → servo do cotovelo
    so = _servo_conectores(cena, k, "ombro")
    sc = _servo_conectores(cena, k, "cotovelo")
    r_x = 0.5 * D_DXL
    d_l = lado_h * (w_tubo + r_x + 0.0004)
    if so is not None:
        _c, q, dq = so[0]
        _ficha_eh(cena, "drone", q, dq)
        fim = W2 - 0.006 * dir_d - 0.0025 * EZ
        m.tubo("drone", "fios_dxl", _curva([q + 0.004 * dq, q + 0.014 * dq, fim + 0.016 * dir_d, fim], 0.008), D_DXL)
    if sc is not None:
        # a ficha do servo do cotovelo fica do lado do tubo OPOSTO ao feixe: o cabo passa por baixo do tubo logo a seguir
        # à ponta do feixe, segue pelo outro lado e afasta-se da ponteira do tubo antes de entrar na ficha
        _c, q, dq = min(sc, key=lambda c: float(c[1][2]))
        _ficha_eh(cena, nb, q, dq)
        lado_f = math.copysign(1.0, bb.d(q)) if abs(bb.d(q)) > 1e-6 else -lado_h
        ini = A - 0.006 * dir_b - 0.0025 * EZ
        d_f = lado_f * (w_tubo + r_x + 0.0004)
        z_baixo = _fundo(sonda_b, bb, 0.14, 0.0, -0.0125) - r_x - 0.0004
        s_pont = l1 - 0.10
        pts = [ini, ini + 0.010 * dir_b]
        if lado_f != lado_h:
            pts += [bb.p(0.122, lado_h * (w_tubo + r_x), -0.004), bb.p(0.140, 0.0, z_baixo),
                    bb.p(0.158, d_f, -0.003)]
        pts += [bb.p(max(0.17, s_pont - 0.03), d_f, -0.002), bb.p(s_pont, lado_f * (0.0185 + r_x), -0.001),
                q + 0.022 * dq, q + 0.0045 * dq]
        m.tubo(nb, "fios_dxl", _curva(pts, 0.010), D_DXL)
        d_l = d_f
    # abraçadeiras: troço da alimentação (com o DYNAMIXEL ao lado) e troço das fases
    s_ab1 = 0.5 * (0.13 + bb.s(p_ent)) if p_ent is not None else 0.2
    dz_i = _topo(sonda_b, bb, s_ab1, 0.0, 0.005)
    circ = [(d_l, -0.002, r_x)] + [(lat, dz_i + 0.5 * D_ESC, 0.5 * D_ESC) for lat in (-0.75 * D_ESC, 0.45 * D_ESC)]
    _abracadeira(cena, bb, sonda_b, s_ab1, circ, -lado_d)
    s_ab2 = 0.5 * (s_m0 + s_m1)
    dz_o = _topo(sonda_b, bb, s_ab2, 0.0, 0.005)
    _abracadeira(cena, bb, sonda_b, s_ab2, [(0.0, dz_o + r_m, r_m), (d_l, -0.002, r_x)], lado_d)


# ====================================================================================== centro
def _bateria(cena: _Cena) -> None:
    """Copos do XT90 macho → (10 AWG) por trás e por cima da placa de cima → ilhas da bateria da placa de energia;
    balanceador até à ficha JST-XH."""
    ctx, m, bat = cena.ctx, cena.m, cena.bat
    if bat is None or cena.placa is None:
        return
    r = 0.5 * D_BAT
    copos = []
    for polo in ("pos", "neg"):
        g = ctx.geom_existente(f"el_xt90_copo_{polo}")
        if g is not None:
            _t, pos, rr, s = _pose(g)
            a, b = pos - rr[:, 2] * s[1], pos + rr[:, 2] * s[1]
            copos.append(a if a[0] < b[0] else b)
    if len(copos) != 2:
        copos = _xt90_proprio(cena)
    if copos is not None:
        x_borda = float(cena.placa.lo[0])
        z_cima = (cena.z_sup + 0.0012 if cena.z_sup is not None else cena.z_topo + 0.016) + r + 0.0012
        comp = cena.computador
        for polo, mat, c in (("pos", "fios_vermelho", copos[0]), ("neg", "fios_preto", copos[1])):
            pad = cena.pdb_pad(f"el_pdb_bat_{polo}")
            pts = [c + np.array([0.0015, 0.0, 0.0]), c - np.array([0.008, 0.0, 0.0]),
                   np.array([min(float(c[0]) - 0.012, x_borda - 0.012), c[1], 0.5 * (c[2] + z_cima)]),
                   np.array([x_borda - 0.006, c[1], z_cima + 0.002])]
            if pad is not None:
                alvo = pad.topo() + np.array([0.0, 0.0, r - 0.0003])
                x_p = float(comp.lo[0]) if comp is not None else float(alvo[0]) - 0.015
                z_ponte = max(z_cima, float(alvo[2]) - 0.009) + 0.002
                pts += [np.array([x_p - 0.016, alvo[1], z_cima + 0.002]), np.array([x_p - 0.004, alvo[1], z_ponte + 0.003]),
                        alvo - np.array([0.006, 0.0, -0.001]), alvo + np.array([0.0015, 0.0, 0.0])]
            else:
                pts += [np.array([x_borda + 0.03, c[1], z_cima])]
            m.tubo("drone", mat, _curva(pts, 0.010), D_BAT)
    _balanceador(cena)


def _xt90_proprio(cena: _Cena):
    """Sem a eletrónica: o XT90 macho + os 2 copos de solda atrás do `conector_xt90` (a mesma disposição dela)."""
    g = cena.ctx.geom_existente("conector_xt90")
    if g is None or cena.bat is None:
        return None
    pos = np.array(g.pos, dtype=float)
    x_f1 = pos[0] + 0.010
    c_m = np.array([x_f1 - 0.0295, pos[1], pos[2]])
    cena.m.caixa("drone", "fios_xt90", c_m, np.eye(3), [0.5 * v for v in XT90_MACHO])
    copos = []
    for dy in (0.00525, -0.00525):
        a, b = np.array([x_f1 - 0.044, pos[1] + dy, pos[2]]), np.array([x_f1 - 0.039, pos[1] + dy, pos[2]])
        cena.m.tubo("drone", "fios_ouro", [a, b], 0.0052, lados=12)
        copos.append(a)
    return copos


def _balanceador(cena: _Cena) -> None:
    """7 fios 22 AWG (1 preto + 6 vermelhos) do topo de trás do pack até à ficha JST-XH (a da eletrónica ou a nossa)."""
    bat = cena.bat
    s = int(getattr(getattr(cena.hw, "bateria", None), "s", 6) or 6)
    larg = (2.5 * (s + 1) + 2.4) * MM
    ficha = cena.caixa("el_bat_balanco")
    zc = float(bat.c[2]) + 0.25 * float(bat.hi[2] - bat.lo[2])
    if ficha is None:
        ficha = _Caixa("drone", np.array([bat.lo[0] - 0.00575, bat.c[1] + 0.013, zc - 0.0035]),
                       np.array([bat.lo[0], bat.c[1] + 0.013 + larg, zc + 0.0035]))
        cena.m.caixa("drone", "fios_jst", ficha.c, np.eye(3), ficha.h)
    x_t = float(bat.lo[0])
    y_c = float(ficha.c[1])
    z_t = float(bat.hi[2]) - 0.004
    p_fim = np.array([float(ficha.lo[0]), y_c, float(ficha.c[2])])
    for j in range(s + 1):
        dy = (j - 0.5 * s) * 2.5 * MM
        mat = "fios_preto" if j == 0 else "fios_vermelho"
        pts = [np.array([x_t + 0.002, y_c + dy, z_t]), np.array([x_t - 0.004, y_c + dy, z_t + 0.0015]),
               np.array([float(ficha.lo[0]) - 0.009, y_c + dy, float(ficha.c[2]) + 0.003]),
               p_fim + np.array([-0.004, dy, 0.0]), p_fim + np.array([0.002, dy, 0.0])]
        cena.m.tubo("drone", mat, _curva(pts, 0.004), D_BAL, lados=6)


def _rpi_fc(cena: _Cena) -> None:
    """USB-C 5 V do BEC à RPi; UART RPi ↔ FC; I2C FC ↔ INA226; ficha dos sinais dos ESC no FC."""
    m, rpi, fc = cena.m, cena.rpi, cena.fc
    # ---- 5 V: ficha USB-C em ângulo (cabo para baixo) na RPi; o cabo corre junto à borda −y e sobe pela folga entre os
    # dois micro-HDMI até à saída 5 V do BEC (placa de energia)
    usbc = cena.rpi_peca("el_rpi5_usbc")
    s5 = cena.pdb_pad("el_pdb_saida_5v")
    if usbc is not None and s5 is not None and rpi is not None:
        y_face = float(usbc.lo[1])
        zc, xc = float(usbc.c[2]), float(usbc.c[0])
        m.caixa("drone", "fios_aco", np.array([xc, y_face + 0.0022, zc]), np.eye(3), [0.0042, 0.0028, 0.00125])
        corpo_c = np.array([xc, y_face - 0.0021, zc - 0.0035])
        m.caixa("drone", "fios_preto", corpo_c, np.eye(3), [0.0060, 0.0021, 0.0062])
        ficha5 = np.array([float(s5.c[0]), float(s5.lo[1]) - 0.0022, float(s5.c[2])])
        m.caixa("drone", "fios_jst", ficha5, np.eye(3), [0.0028, 0.0022, 0.0018])
        x_sobe = float(rpi.lo[0]) + 0.0325
        y_sobe = float(rpi.lo[1]) - FOLGA_PILHA
        z_baixo = cena.z_topo + 0.5 * D_5V + 0.0005
        base = corpo_c - np.array([0.0, 0.0, 0.0062])
        pts = [base + np.array([0, 0, 0.003]), base - np.array([0, 0, 0.002]),
               np.array([xc + 0.006, y_sobe, z_baixo]), np.array([x_sobe - 0.006, y_sobe, z_baixo]),
               np.array([x_sobe, y_sobe, z_baixo + 0.006]), np.array([x_sobe, y_sobe, float(ficha5[2]) - 0.006]),
               np.array([0.5 * (x_sobe + ficha5[0]), float(ficha5[1]) - 0.004, float(ficha5[2])]),
               ficha5 - np.array([0.0, 0.0018, 0.0]), ficha5 + np.array([0.0, 0.001, 0.0])]
        m.tubo("drone", "fios_preto", _curva(pts, 0.006), D_5V)
    # ---- UART: Dupont 1×3 nos pinos 6/8/10 → JST-GH no `el_fc_con_rc`
    rc = cena.fc_con("el_fc_con_rc")
    gpio = cena.rpi_peca("el_rpi5_gpio_base")
    if rpi is not None and rc is not None and gpio is not None:
        x_p = [float(rpi.lo[0]) + (8.37 + 2.54 * j) * MM for j in (2, 3, 4)]
        y_p = float(rpi.lo[1]) + 53.77 * MM
        z_b = float(gpio.hi[2])
        z_c = z_b + 0.014
        m.caixa("drone", "fios_dupont", np.array([x_p[1], y_p, 0.5 * (z_b + z_c)]), np.eye(3), [0.0038, 0.00127, 0.007])
        f_rc = np.array([float(rc.c[0]), float(rc.hi[1]) + 0.0021, float(rc.c[2])])
        m.caixa("drone", "fios_jst", f_rc, np.eye(3), [0.0030, 0.0021, 0.0015])
        for x, mat, dx in ((x_p[0], "fios_preto", -0.0013), (x_p[1], "fios_amarelo", 0.0),
                           (x_p[2], "fios_verde", 0.0013)):
            pts = [np.array([x, y_p, z_c - 0.002]), np.array([x, y_p, z_c + 0.004]),
                   np.array([f_rc[0] + dx, f_rc[1] + 0.007, f_rc[2] + 0.002]),
                   np.array([f_rc[0] + dx, f_rc[1] + 0.0012, f_rc[2]])]
            m.tubo("drone", mat, _curva(pts, 0.004), D_DUPONT)
    # ---- I2C: FC → INA226 da placa de energia
    i2c, i2c_p = cena.fc_con("el_fc_con_i2c"), cena.pdb_pad("el_pdb_con_i2c")
    if i2c is not None and i2c_p is not None:
        a = np.array([float(i2c.hi[0]) + 0.0021, float(i2c.c[1]), float(i2c.c[2])])
        b = np.array([float(i2c_p.hi[0]) + 0.0021, float(i2c_p.c[1]), float(i2c_p.c[2])])
        for c in (a, b):
            m.caixa("drone", "fios_jst", c, np.eye(3), [0.0021, 0.0030, 0.0015])
        for j, mat in enumerate(("fios_preto", "fios_vermelho", "fios_amarelo", "fios_azul")):
            dy = (j - 1.5) * 1.25 * MM
            pts = [a + np.array([0.0012, dy, 0.0]), a + np.array([0.008, dy, 0.002]),
                   b + np.array([0.008, dy, -0.002]), b + np.array([0.0012, dy, 0.0])]
            m.tubo("drone", mat, _curva(pts, 0.004), D_JST, lados=6)
    # ---- ficha JST-GH dos sinais dos 4 ESC no `el_fc_con_esc`
    con = cena.fc_con("el_fc_con_esc")
    if con is not None and fc is not None:
        m.caixa("drone", "fios_jst", np.array([float(con.lo[0]) - 0.0021, float(con.c[1]), float(con.c[2])]),
                np.eye(3), [0.0021, 0.0044, 0.0015])
    _sensores(cena)


def _sensores(cena: _Cena) -> None:
    """PMW3901 + VL53L1X: saltador de 4 fios entre as placas e cabo JST-GH que sobe pelo lado +y até ao `el_fc_con_gps`."""
    m, bat, fc = cena.m, cena.bat, cena.fc
    gps = cena.fc_con("el_fc_con_gps")
    fluxo = cena.caixa("el_fluxo_pcb")
    tof = cena.caixa("el_tof_pcb")
    if fluxo is None:
        fluxo = cena.baixo
    if fluxo is None or bat is None or gps is None:
        return
    r = 0.5 * D_JST * 2.3
    con = cena.caixa("el_fluxo_conector")
    ini = (np.array([float(con.lo[0]) - 0.001, float(con.c[1]), float(con.c[2])]) if con is not None
           else np.array([float(fluxo.lo[0]) + 0.003, float(fluxo.c[1]), float(fluxo.lo[2]) - 0.001]))
    comp = cena.computador
    y_sobe = float(bat.hi[1]) + r + 0.0018
    if comp is not None:
        y_sobe = max(y_sobe, float(comp.hi[1]) + FOLGA_PILHA)
    x_sobe = float(comp.c[0]) + 0.012 if comp is not None else float(fluxo.c[0])
    z_c = float(gps.c[2])
    f_g = np.array([float(gps.hi[0]) + 0.0021, float(gps.c[1]), z_c])
    m.caixa("drone", "fios_jst", f_g, np.eye(3), [0.0021, 0.0042, 0.0015])
    z_fundo = min(float(fluxo.lo[2]), float(ini[2])) - 0.003
    z_cima = (float(fc.hi[2]) + 0.0030) if fc is not None else z_c + 0.004
    pts = [ini, ini - np.array([0.005, 0.0, 0.0]), np.array([ini[0] - 0.008, ini[1], z_fundo]),
           np.array([ini[0] - 0.008, float(bat.hi[1]) - 0.004, z_fundo]),
           np.array([x_sobe, y_sobe, float(bat.lo[2]) + 0.004]), np.array([x_sobe, y_sobe, z_cima]),
           np.array([f_g[0] + 0.006, float(f_g[1]) + 0.012, z_cima]), np.array([f_g[0] + 0.006, f_g[1], z_c]),
           f_g + np.array([0.0015, 0.0, 0.0])]
    m.tubo("drone", "fios_preto", _curva(pts, 0.008), 2.0 * r)
    if tof is not None and fluxo is not cena.baixo:
        a = np.array([float(tof.lo[0]) + 0.002, float(tof.c[1]), float(tof.lo[2]) - 0.0007])
        b = np.array([float(fluxo.hi[0]) - 0.002, float(fluxo.c[1]), float(fluxo.lo[2]) - 0.0007])
        for j, mat in enumerate(("fios_preto", "fios_vermelho", "fios_azul", "fios_amarelo")):
            dy = (j - 1.5) * 1.1 * MM
            pts = [a + np.array([0.0, dy, 0.0]), 0.5 * (a + b) + np.array([0.0, dy, -0.0025]),
                   b + np.array([0.0, dy, 0.0])]
            m.tubo("drone", mat, _curva(pts, 0.004), D_JST, lados=6)


def _fpc_camera(cena: _Cena) -> None:
    """FPC da Camera Module 3 (15 vias, 16 mm) ao `el_rpi5_cam_disp0` (22 vias, 11,5 mm) — ver o docstring do módulo."""
    if not cena.cam_csi or cena.cam is None or cena.rpi is None or cena.placa is None:
        return
    m, cam, rpi, placa = cena.m, cena.cam, cena.rpi, cena.placa
    con_cam = cena.ancora("el_cam_conector_fpc",
                          lambda: _Caixa("drone", np.array([cam.lo[0] + 0.002, cam.c[1] - 0.0104, cam.lo[2]]),
                                         np.array([cam.lo[0] + 0.0045, cam.c[1] + 0.0104, cam.lo[2] + 0.005])))
    con = cena.rpi_peca("el_rpi5_cam_disp0")
    trava = cena.rpi_peca("el_rpi5_cam_disp0_trava")
    if con_cam is None or con is None:
        return
    e = FPC_ESP
    z_top, z_bot = float(placa.hi[2]), float(placa.lo[2])
    x_c, y_c = float(con_cam.c[0]), float(con_cam.c[1])
    w = FPC_LARG_RPI
    x_tr = float(trava.hi[0]) if trava is not None else float(con.hi[0]) + 0.001
    z_con = float(con.c[2])
    z_lay = float(rpi.lo[2]) + 0.0042 + 0.5 * e          # por cima dos 2 conectores MIPI e das travas
    y_con = float(con.c[1])
    x_d = x_tr + 0.5 * w + 0.0015                         # centro da dobra à frente da trava
    y_borda = float(rpi.lo[1])
    y_fora = y_borda - 0.0125
    x_rasgo = float(cam.lo[0]) - 0.022
    zb = z_bot - 0.0006 - 0.5 * e
    zt = z_top + 0.0004 + 0.5 * e
    # (1) do conector da câmara para baixo (à frente da borda da placa) e por baixo da placa até ao rasgo
    pts1 = [np.array([x_c, y_c, float(con_cam.lo[2]) + 0.0025]), np.array([x_c, y_c, zb - 0.002]),
            np.array([x_c - 0.008, y_c, zb]), np.array([x_rasgo + 0.012, y_c, zb]),
            np.array([x_rasgo + 0.004, 0.5 * (y_c + y_fora), zb]), np.array([x_rasgo, y_fora, zb])]
    m.fita("drone", "fios_fpc", _curva(pts1, 0.004, n=4), FPC_LARG_CAM, [0.0, 1.0, 0.0], e)
    # (2) sobe pelo rasgo e corre na placa (largura em y; estreita para 11,5 mm) até à 1.ª dobra
    pts2 = _curva([np.array([x_rasgo, y_fora, zb]), np.array([x_rasgo, y_fora, zt]),
                   np.array([x_rasgo - 0.008, y_fora, zt]), np.array([x_d + 0.5 * w, y_fora, zt])], 0.003, n=4)
    comp = np.concatenate([[0.0], np.cumsum([np.linalg.norm(b - a) for a, b in itertools.pairwise(pts2)])])
    larg = [FPC_LARG_CAM + (w - FPC_LARG_CAM) * min(1.0, max(0.0, (c - 0.5 * comp[-1]) / (0.35 * comp[-1])))
            for c in comp]
    m.fita("drone", "fios_fpc", pts2, larg, [0.0, 1.0, 0.0], e)
    # (3) 1.ª dobra (45°): corre em +y (largura em x), sobe à borda −y da RPi e assenta por cima dos conectores
    pts3 = [np.array([x_d, y_fora - 0.5 * w, zt + e]), np.array([x_d, y_borda - 0.006, zt + e]),
            np.array([x_d, y_borda - 0.0008, z_lay]), np.array([x_d, y_con + 0.5 * w, z_lay])]
    m.fita("drone", "fios_fpc", _curva(pts3, 0.003, n=4), w, [1.0, 0.0, 0.0], e)
    # (4) 2.ª dobra (45°) à frente da trava: entra no conector ao longo de −x (largura em y) até ao centro dele
    pts4 = [np.array([x_d + 0.5 * w, y_con, z_lay + e]), np.array([x_tr + 0.0005, y_con, z_lay + e]),
            np.array([float(con.c[0]), y_con, z_con])]
    m.fita("drone", "fios_fpc", pts4, w, [0.0, 1.0, 0.0], e)


def _fonte_e_barramento(cena: _Cena) -> None:
    """Articulado: 18 AWG das ilhas da bateria à entrada do regulador de 24 V; cabos X4P da saída do regulador a cada
    servo do ombro (em estrela: sobem pela folga de trás da RPi e seguem deitados na placa de cima)."""
    m, fonte = cena.m, cena.fonte
    if fonte is None or not cena.art:
        return
    ent = cena.ancora("el_fonte24_borne_entrada", lambda: _Caixa(
        "drone", np.array([fonte.lo[0], fonte.c[1] - 0.005, fonte.lo[2]]),
        np.array([fonte.lo[0] + 0.007, fonte.c[1] + 0.005, fonte.hi[2]])))
    sai = cena.ancora("el_fonte24_borne_saida", lambda: _Caixa(
        "drone", np.array([fonte.hi[0] - 0.007, fonte.c[1] - 0.005, fonte.lo[2]]),
        np.array([fonte.hi[0], fonte.c[1] + 0.005, fonte.hi[2]])))
    z_mesa = (cena.z_sup + 0.0012) if cena.z_sup is not None else cena.z_topo + 0.016
    x_borda = float(cena.placa.lo[0]) if cena.placa is not None else float(fonte.lo[0]) - 0.02
    if ent is not None:
        for j, (polo, mat) in enumerate((("pos", "fios_vermelho"), ("neg", "fios_preto"))):
            alvo = cena.pdb_pad(f"el_pdb_bat_{polo}")
            if alvo is None:
                continue
            dy = (0.5 - j) * 0.0026
            p0 = np.array([float(ent.lo[0]) + 0.0015, float(ent.c[1]) + dy, float(ent.c[2])])
            q = alvo.topo() + np.array([0.0015, (1 - 2 * j) * 0.003, 0.5 * D_18])
            z_c = z_mesa + 0.5 * D_18 + 0.0045
            pts = [p0, p0 - np.array([0.006, 0.0, 0.0]), np.array([x_borda - 0.010, p0[1] + 0.012 * (1 - 2 * j), z_c - 0.01]),
                   np.array([x_borda - 0.004, p0[1] + 0.012 * (1 - 2 * j), z_c]),
                   np.array([float(q[0]) - 0.03, q[1], z_c]), np.array([float(q[0]) - 0.012, q[1], float(q[2]) + 0.004]), q]
            m.tubo("drone", mat, _curva(pts, 0.008), D_18)
    if sai is None or cena.computador is None:
        return
    comp = cena.computador
    r = 0.5 * D_DXL
    x_sobe = float(comp.lo[0]) - FOLGA_PILHA - 0.0002
    ys = {3: 0.0108, 1: 0.0075, 4: -0.0075, 2: -0.0108}
    for k in range(1, 5):
        so = _servo_conectores(cena, k, "ombro")
        if so is None:
            continue
        _c, q, dq = so[1]
        _ficha_eh(cena, "drone", q, dq)
        sx, sy = cena.sinais[k - 1]
        y_s = float(comp.c[1]) + ys.get(k, 0.0)
        p0 = np.array([float(sai.hi[0]) + 0.0035, float(sai.c[1]) + 0.0032 * (1 if y_s > comp.c[1] else -1),
                       float(sai.c[2])])
        m.caixa("drone", "fios_jst", p0 - np.array([0.0017, 0.0, 0.0]), np.eye(3), [0.0017, 0.0029, 0.0040])
        z_t = z_mesa + r
        alvo = q + 0.0045 * dq
        fora = alvo + 0.024 * dq
        pts = [p0, p0 + np.array([0.006, 0.0, 0.0]), np.array([x_sobe, y_s, float(p0[2]) + 0.004]),
               np.array([x_sobe, y_s, z_t + 0.004]), np.array([x_sobe - 0.012, y_s, z_t])]
        y_lado = float(alvo[1]) if abs(sx * (float(alvo[0]) - float(comp.c[0]))) < 0.08 else (
            float(comp.c[1]) + sy * (float(comp.h[1]) + 0.022))
        if sx > 0:      # servos da frente: corre pelo lado da janela, por cima da placa de cima
            pts += [np.array([x_sobe - 0.016, y_lado, z_t]), np.array([float(fora[0]) - 0.006, y_lado, z_t])]
        pts += [np.array([fora[0], fora[1], z_t]), fora + np.array([0, 0, 0.002]), alvo]
        m.tubo("drone", "fios_dxl", _curva(pts, 0.010), D_DXL)


# ====================================================================================== entrada
_ANTIGOS = ("fio_motor{k}_a", "fio_motor{k}_b", "fio_motor{k}_c", "abracadeira_braco{k}_1", "abracadeira_braco{k}_2")


def adicionar(ctx) -> None:
    """Cablagem completa do build (ver o docstring do módulo); cada parte é opcional e independente."""
    for k in range(1, 5):
        for modelo_nome in _ANTIGOS:
            nome = modelo_nome.format(k=k)
            if ctx.geom_existente(nome) is not None:
                ctx.apagar(nome)
    for nome in ("cabo_bateria_pos", "cabo_bateria_neg"):      # NUNCA o `conector_xt90` (a eletrónica recria-o)
        if ctx.geom_existente(nome) is not None:
            ctx.apagar(nome)
    for nome, kw in _MATERIAIS.items():
        ctx.material(nome, **kw)
    malhas = _Malhas(ctx)
    cena = _Cena(ctx, malhas)
    partes = [(f"braço {k}", (_braco_articulado if cena.art else _braco_rigido), (cena, k)) for k in range(1, 5)]
    partes += [("bateria", _bateria, (cena,)), ("RPi/FC", _rpi_fc, (cena,)), ("FPC", _fpc_camera, (cena,)),
               ("barramento", _fonte_e_barramento, (cena,))]
    for nome, fn, args in partes:
        try:
            fn(*args)
        except Exception as e:  # noqa: BLE001 — um detalhe visual nunca pode derrubar o simulador
            warnings.warn(f"detalhes/fios: {nome} não desenhado ({type(e).__name__}: {e})", stacklevel=2)
    malhas.criar()
