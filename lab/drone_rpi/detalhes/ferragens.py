"""lab/drone_rpi/detalhes/ferragens.py — FERRAGENS normalizadas do drone (2026-10-20): parafusos, porcas, anilhas,
pilares (espaçadores), anéis E e pernos roscados com a GEOMETRIA DAS NORMAS — para todos os módulos de detalhe.

Só aparência (massa 0, sem contacto, grupo 3, pelo `Contexto.geom`): a física fica igual bit a bit. Cada ferragem é
registada (`registo.ferragens`) com a norma, a rosca, o comprimento, o material, o corpo, o ponto e o eixo — é daí que
saem a LISTA DE FERRAGENS da página `/pecas` (contada, por passo de montagem) e a auditoria («cada parafuso passa por um
furo e a cabeça assenta numa superfície», `auditoria.py`).

    from .ferragens import M
    fer = ctx.ferragens                                   # o Coletor partilhado (`adicionar_detalhes` fecha-o)
    fer.parafuso("drone", ponto, eixo, "M3", aperto=4.5, porca="ISO 10511", peca="placa_motor", inst=k)
    fer.pilar("drone", base, (0, 0, 1), "M2.5", 16.0, tipo="sextavado", material="latao", peca="rpi5")

CONVENÇÕES (todas as medidas das tabelas em mm; a geometria sai em metros)
  · PARAFUSO: `ponto` = centro da face de APOIO da cabeça (onde a cabeça toca na peça), `eixo` = do lado da cabeça para
    a ponta (para DENTRO da peça). A cabeça fica em [−k, 0] e a haste em [0, L] ao longo do eixo.
  · PORCA/ANILHA: `ponto` = centro da face de apoio (a que toca na peça), `eixo` = para FORA da peça (o mesmo sentido
    do parafuso que a atravessa). Ocupa [0, m] ao longo do eixo.
  · O comprimento escolhe-se da SÉRIE NORMALIZADA (`COMPRIMENTOS`) — o mais curto que dá o aperto pedido mais a altura
    da anilha e da porca e 1–3 fios de rosca de fora (com porca) ou ≥ 1,5·d de rosca metida (furo roscado em alumínio).
  · A ROSCA desenha-se (filete helicoidal de 60°, perfil ISO 68-1: fundo P/4, crista P/8) só onde se VÊ: a ponta que sai
    da porca, a haste à vista entre peças (`haste_visivel`) e os pernos dos pilares; o resto da haste está dentro das
    peças. A página 3D mostra cada ferragem INTEIRA (`malha_completa`).
  · Malhas fundidas: uma por corpo × material (`fer_<corpo>_<material>`), com o intervalo de faces de cada peça no
    registo (`ctx.registar_faixas`) — dezenas de geoms para centenas de ferragens.

NORMAS (valores nominais das tabelas; fontes no fim): ISO 4762 (sextavado interior, cabeça cilíndrica), ISO 7380-1
(cabeça abaulada), ISO 4032 (porca sextavada), ISO 10511/DIN 985 (porca autoblocante baixa com anel de nylon),
ISO 7089 (anilha lisa), DIN 6799 (anel E), DIN 916 (perno de sextavado interior com ponta côncava), pilares de latão
M2,5 do Raspberry Pi (sextavado de 5 mm) e espaçadores de alumínio/nylon M3.

Fontes (dados de fichas; web = não confiável, só citado):
  https://www.roymech.co.uk/Useful_Tables/Screws/cap_screws.htm (ISO 4762) ·
  https://www.fastenerdata.co.uk/iso-7380-socket-button-head-screw (ISO 7380) ·
  https://www.engineeringtoolbox.com/metric-hex-nuts-d_2054.html (ISO 4032) ·
  https://www.fasteners.eu/standards/DIN/985/ (DIN 985 ≈ ISO 10511) ·
  https://www.fasteners.eu/standards/ISO/7089/ (ISO 7089) · https://www.fasteners.eu/standards/DIN/6799/ (DIN 6799) ·
  https://www.fasteners.eu/standards/DIN/916/ (DIN 916) · ISO 68-1 / ISO 261 (perfil e passo grosso).
"""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass

import mujoco
import numpy as np

MM = 1e-3
_TAU = 2.0 * math.pi

# ================================================================================================= tabelas (mm)
PASSO = {"M2": 0.4, "M2.5": 0.45, "M3": 0.5, "M4": 0.7, "M5": 0.8, "M6": 1.0, "M8": 1.25, "M10": 1.5}
DIAMETRO = {"M2": 2.0, "M2.5": 2.5, "M3": 3.0, "M4": 4.0, "M5": 5.0, "M6": 6.0, "M8": 8.0, "M10": 10.0}
# ISO 4762: dk (Ø cabeça), k (altura), s (sextavado interior), t (profundidade do sextavado)
ISO4762 = {"M2": (3.8, 2.0, 1.5, 1.0), "M2.5": (4.5, 2.5, 2.0, 1.1), "M3": (5.5, 3.0, 2.5, 1.3),
           "M4": (7.0, 4.0, 3.0, 2.0), "M5": (8.5, 5.0, 4.0, 2.5), "M6": (10.0, 6.0, 5.0, 3.0)}
# ISO 7380-1 (abaulada): dk, k, s, t   (M2/M2,5 dos catálogos — a norma começa em M3)
ISO7380 = {"M2": (3.5, 1.3, 1.3, 0.7), "M2.5": (4.7, 1.5, 1.5, 0.9), "M3": (5.7, 1.65, 2.0, 1.04),
           "M4": (7.6, 2.2, 2.5, 1.3), "M5": (9.5, 2.75, 3.0, 1.56), "M6": (10.5, 3.3, 4.0, 2.08)}
# ISO 4032: s (entre faces), m (altura)
ISO4032 = {"M2": (4.0, 1.6), "M2.5": (5.0, 2.0), "M3": (5.5, 2.4), "M4": (7.0, 3.2), "M5": (8.0, 4.7),
           "M6": (10.0, 5.2), "M8": (13.0, 6.8), "M10": (16.0, 8.4)}
# ISO 10511 / DIN 985 (autoblocante): s, h (altura total), m (parte metálica sextavada)
ISO10511 = {"M2.5": (5.0, 3.8, 2.0), "M3": (5.5, 4.0, 2.4), "M4": (7.0, 5.0, 2.9), "M5": (8.0, 5.0, 3.2),
            "M6": (10.0, 6.0, 4.0), "M8": (13.0, 8.0, 5.5), "M10": (17.0, 10.0, 6.5)}
# ISO 7089 (anilha lisa): d1 (furo), d2 (exterior), h
ISO7089 = {"M2": (2.2, 5.0, 0.3), "M2.5": (2.7, 6.0, 0.5), "M3": (3.2, 7.0, 0.5), "M4": (4.3, 9.0, 0.8),
           "M5": (5.3, 10.0, 1.0), "M6": (6.4, 12.0, 1.6), "M8": (8.4, 16.0, 1.6), "M10": (10.5, 20.0, 2.0)}
# DIN 6799 (anel E): Ø do veio → (Ø da ranhura d, Ø exterior aberto d3, espessura s)
DIN6799 = {3.0: (2.3, 6.0, 0.6), 4.0: (3.2, 7.3, 0.6), 5.0: (4.0, 9.3, 0.7), 6.0: (5.0, 11.3, 0.7),
           8.0: (6.0, 12.3, 0.7), 10.0: (8.0, 16.3, 1.0), 12.0: (9.0, 18.8, 1.1)}
# série de comprimentos normalizados (ISO 4762 / ISO 7380) por rosca
COMPRIMENTOS = {"M2": (3, 4, 5, 6, 8, 10, 12, 16, 20), "M2.5": (3, 4, 5, 6, 8, 10, 12, 14, 16, 20, 25),
                "M3": (4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 30, 35, 40, 45, 50),
                "M4": (5, 6, 8, 10, 12, 14, 16, 20, 25, 30, 35, 40), "M5": (6, 8, 10, 12, 16, 20, 25, 30, 35, 40),
                "M6": (8, 10, 12, 16, 20, 25, 30, 35, 40, 50)}
# binários de aperto de referência (N·m) — classe 12.9 em aço / furo roscado em alumínio (valores de oficina, com
# freio de rosca médio); os de nylon são «à mão» (o nylon M3 parte a ~0,5 N·m)
BINARIO_NM = {("M2", "aco"): 0.35, ("M2.5", "aco"): 0.6, ("M3", "aco"): 1.0, ("M4", "aco"): 2.3,
              ("M5", "aco"): 4.5, ("M6", "aco"): 7.7, ("M2", "aluminio"): 0.25, ("M2.5", "aluminio"): 0.45,
              ("M3", "aluminio"): 0.8, ("M4", "aluminio"): 1.8, ("M2.5", "nylon"): 0.2, ("M3", "nylon"): 0.3}

NORMAS_CABECA = ("ISO 4762", "ISO 7380")
NORMAS_PORCA = ("ISO 4032", "ISO 10511")

# materiais das ferragens (nome no spec → rgba, especular, brilho, refletância)
MATERIAIS = {
    "fer_aco_preto": ((0.10, 0.10, 0.11, 1.0), 0.75, 0.80, 0.04),      # 12.9 óxido negro
    "fer_aco_inox": ((0.70, 0.71, 0.73, 1.0), 0.90, 0.85, 0.10),       # A2-70
    "fer_aco_zincado": ((0.78, 0.80, 0.84, 1.0), 0.90, 0.85, 0.12),    # 8.8 zincado brilhante
    "fer_latao": ((0.78, 0.62, 0.30, 1.0), 0.85, 0.80, 0.08),
    "fer_aluminio": ((0.72, 0.73, 0.76, 1.0), 0.80, 0.70, 0.05),
    "fer_aluminio_preto": ((0.09, 0.09, 0.10, 1.0), 0.55, 0.60, 0.02),
    "fer_aluminio_vermelho": ((0.72, 0.10, 0.10, 1.0), 0.70, 0.65, 0.03),
    "fer_nylon_branco": ((0.90, 0.89, 0.84, 1.0), 0.20, 0.25, 0.0),
    "fer_nylon_preto": ((0.08, 0.08, 0.085, 1.0), 0.25, 0.30, 0.0),
    "fer_nylon_azul": ((0.16, 0.36, 0.78, 1.0), 0.30, 0.35, 0.0),     # anel de nylon das autoblocantes
    "fer_titanio": ((0.55, 0.55, 0.58, 1.0), 0.70, 0.70, 0.05),
    "fer_mola": ((0.20, 0.20, 0.22, 1.0), 0.80, 0.85, 0.06),           # anel E (aço de mola fosfatado)
}
MATERIAL_TIPO = {"fer_aco_preto": "aco", "fer_aco_inox": "aco", "fer_aco_zincado": "aco", "fer_titanio": "aco",
                 "fer_latao": "aluminio", "fer_aluminio": "aluminio", "fer_aluminio_preto": "aluminio",
                 "fer_aluminio_vermelho": "aluminio", "fer_nylon_branco": "nylon", "fer_nylon_preto": "nylon",
                 "fer_nylon_azul": "nylon", "fer_mola": "aco"}


def material(nome: str) -> str:
    """Aceita «aco_preto» ou «fer_aco_preto» e devolve o nome do material no spec."""
    n = nome if nome.startswith("fer_") else f"fer_{nome}"
    if n not in MATERIAIS:
        raise KeyError(f"material de ferragem desconhecido {nome!r} (há {sorted(MATERIAIS)})")
    return n


def comprimento_normalizado(rosca: str, minimo_mm: float, maximo_mm: float | None = None) -> float:
    """O comprimento da série normalizada mais curto ≥ `minimo_mm` (e ≤ `maximo_mm`, se dado)."""
    serie = COMPRIMENTOS.get(rosca)
    if serie is None:
        raise KeyError(f"rosca sem série de comprimentos: {rosca}")
    for L in serie:
        if L + 1e-9 >= minimo_mm and (maximo_mm is None or L <= maximo_mm + 1e-9):
            return float(L)
    raise ValueError(f"{rosca}: nenhum comprimento normalizado entre {minimo_mm:.2f} e {maximo_mm} mm (série {serie})")


# ================================================================================================= malhas (mm)
class _Malha:
    """Triângulos (anti-horários vistos de fora) acumulados; arestas vivas = vértices próprios por face."""

    def __init__(self):
        self.v: list[np.ndarray] = []
        self.f: list[np.ndarray] = []
        self.n = 0

    def junta(self, v, f, R=None, p=None):
        v = np.asarray(v, float).reshape(-1, 3)
        f = np.asarray(f, np.int64).reshape(-1, 3)
        if R is not None:
            R = np.asarray(R, float)
            v = v @ R.T
            if np.linalg.det(R) < 0:
                f = f[:, ::-1]
        if p is not None:
            v = v + np.asarray(p, float)
        self.v.append(v)
        self.f.append(f + self.n)
        self.n += len(v)
        return self

    def arrays(self) -> tuple[np.ndarray, np.ndarray]:
        if not self.v:
            return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
        return np.concatenate(self.v), np.concatenate(self.f)


def _torno(segmentos, n: int = 24, fase: float = 0.0):
    """Sólido de revolução em torno de z: `segmentos` = polilinhas (r, z) que percorrem o perfil no sentido
    anti-horário (r → direita, z ↑); cada uma tem vértices próprios (aresta viva); r = 0 vira um só vértice."""
    v, f = [], []
    phi = fase + np.arange(n) * _TAU / n
    c, s = np.cos(phi), np.sin(phi)
    for seg in segmentos:
        aneis = []
        for r, z in seg:
            if r < 1e-12:
                aneis.append([len(v)] * n)
                v.append((0.0, 0.0, z))
            else:
                b = len(v)
                v.extend(zip((r * c).tolist(), (r * s).tolist(), [z] * n, strict=True))
                aneis.append(list(range(b, b + n)))
        for j in range(len(seg) - 1):
            a, b = aneis[j], aneis[j + 1]
            for i in range(n):
                i2 = (i + 1) % n
                if a[i] != a[i2]:
                    f.append((a[i], a[i2], b[i2]))
                if b[i2] != b[i]:
                    f.append((a[i], b[i2], b[i]))
    return np.array(v, float), np.array(f, np.int64)


def _polar(raio_fn, zs, n: int, fase: float = 0.0, r_furo: float | None = None):
    """Sólido «estrelado» em torno de z: parede exterior r = raio_fn(θ, z) nas cotas `zs` (crescentes), topos planos e,
    com `r_furo`, um furo cilíndrico (parede interior). Serve para sextavados com chanfro (r = min(hexágono, cone))."""
    th = fase + np.arange(n) * _TAU / n
    c, s = np.cos(th), np.sin(th)
    v, f = [], []
    aneis = []
    for z in zs:
        r = np.array([raio_fn(t, z) for t in th])
        b = len(v)
        v.extend(zip((r * c).tolist(), (r * s).tolist(), [z] * n, strict=True))
        aneis.append(b)
    for j in range(len(zs) - 1):
        a, b = aneis[j], aneis[j + 1]
        for i in range(n):
            i2 = (i + 1) % n
            f += [(a + i, a + i2, b + i2), (a + i, b + i2, b + i)]
    for z, ref, cima in ((zs[0], aneis[0], False), (zs[-1], aneis[-1], True)):
        # o topo/fundo com vértices próprios (aresta viva com a parede)
        r = np.array([raio_fn(t, z) for t in th])
        b = len(v)
        v.extend(zip((r * c).tolist(), (r * s).tolist(), [z] * n, strict=True))
        if r_furo is None:
            cen = len(v)
            v.append((0.0, 0.0, z))
            for i in range(n):
                t = (cen, b + i, b + (i + 1) % n)
                f.append(t if cima else t[::-1])
        else:
            bi = len(v)
            v.extend(zip((r_furo * c).tolist(), (r_furo * s).tolist(), [z] * n, strict=True))
            for i in range(n):
                i2 = (i + 1) % n
                q = [(bi + i, b + i, b + i2), (bi + i, b + i2, bi + i2)]
                f += q if cima else [t[::-1] for t in q]
    if r_furo is not None:                                 # parede do furo (normais para o eixo)
        b0 = len(v)
        for z in (zs[0], zs[-1]):
            v.extend(zip((r_furo * c).tolist(), (r_furo * s).tolist(), [z] * n, strict=True))
        b1 = b0 + n
        for i in range(n):
            i2 = (i + 1) % n
            f += [(b0 + i, b1 + i2, b0 + i2), (b0 + i, b1 + i, b1 + i2)]
    return np.array(v, float), np.array(f, np.int64)


def _hexagono_r(af: float, t: float) -> float:
    """Raio do hexágono (af entre faces) na direção t, com vértices em 0°, 60°, … (faces a 30° + 60°·k)."""
    u = (t % (math.pi / 3.0)) - math.pi / 6.0             # 0 no meio da face (30°), ±30° nos vértices
    return 0.5 * af / math.cos(u)


@functools.cache
def _sextavado(af: float, z0: float, z1: float, chanfro: bool, r_furo: float | None, n_lado: int = 4):
    """Prisma sextavado (af entre faces) com o CHANFRO de 30° das porcas (o cone corta os vértices e deixa o círculo
    de apoio ≈ 0,95·af) nas duas faces, com ou sem furo."""
    rc = 0.5 * af / math.cos(math.pi / 6.0)
    r_apoio = 0.5 * af * 0.95
    h_ch = (rc - r_apoio) * math.tan(math.radians(30.0)) if chanfro else 0.0

    def raio(t, z):
        rh = _hexagono_r(af, t)
        if not chanfro:
            return rh
        d = min(z - z0, z1 - z)                            # distância à face mais próxima
        return min(rh, r_apoio + d / math.tan(math.radians(30.0)))
    zs = [z0]
    if chanfro:
        zs += [z0 + 0.5 * h_ch, z0 + h_ch]
        zs += [z1 - h_ch, z1 - 0.5 * h_ch]
    zs.append(z1)
    zs = sorted({round(z, 9) for z in zs})
    return _polar(raio, zs, 6 * n_lado, fase=0.0, r_furo=r_furo)


@functools.cache
def _rosca_ext(d: float, P: float, z0: float, z1: float, ponta: bool = True, n: int = 12, tampa0: bool = True):
    """Haste ROSCADA (filete ISO 68-1 de 60°, passo P) de z0 a z1, com chanfro de 45° na ponta (z1) se `ponta`.
    A hélice começa uma volta antes de z0 e acaba uma depois de z1, com as cotas «presas» ao intervalo (topos planos)."""
    r_maj = 0.5 * d
    r_min = r_maj - 0.6134 * P
    u_r = (0.0, P / 8.0, 7.0 * P / 16.0, 9.0 * P / 16.0, 7.0 * P / 8.0)
    r_r = (r_min, r_min, r_maj, r_maj, r_min)
    voltas = (z1 - z0) / P + 2.0
    ncol = math.ceil(voltas * n) + 1
    nr = len(u_r)
    v = np.zeros((ncol * nr, 3))
    for i in range(ncol):
        th = i * _TAU / n
        z_base = z0 - P + P * i / n
        for j in range(nr):
            z = z_base + u_r[j]
            r = r_r[j]
            zc = min(max(z, z0), z1)
            if ponta:
                r = min(r, r_min + max(0.0, z1 - zc) * 1.0 + 0.15 * P)
            v[i * nr + j] = (r * math.cos(th), r * math.sin(th), zc)
    f = []
    for i in range(ncol - 1):
        for j in range(nr):
            a = i * nr + j
            b = (i + 1) * nr + j
            if j + 1 < nr:
                a2, b2 = a + 1, b + 1
            else:                                          # a última linha liga à 1.ª da volta seguinte
                if i + n + 1 >= ncol:
                    continue
                a2, b2 = (i + n) * nr, (i + n + 1) * nr
            f += [(a, b, b2), (a, b2, a2)]
    f = np.array(f, np.int64)
    # tira triângulos degenerados (presos aos topos)
    tri = v[f]
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    f = f[area > 1e-14]
    # topos (discos no raio do núcleo)
    m = _Malha().junta(v, f)
    if tampa0:
        m.junta(*_torno([[(0.0, z0), (r_min, z0)]], n=n))
    m.junta(*_torno([[(r_min if not ponta else r_min - 0.3 * P, z1), (0.0, z1)]], n=n))
    return m.arrays()


@functools.cache
def _haste_lisa(d: float, z0: float, z1: float, n: int = 12):
    r = 0.5 * d
    return _torno([[(r, z0), (r, z1)]], n=n)


@functools.cache
def _cabeca_4762(rosca: str, n: int = 24):
    """Cabeça ISO 4762 com a face de apoio em z = 0 e o topo em z = −k (a haste vai para +z): chanfro do topo, rebaixo
    sextavado VERDADEIRO (paredes e fundo cónico de 118°)."""
    dk, k, s, t = ISO4762[rosca]
    r = 0.5 * dk
    ch = 0.08 * dk
    rh = 0.5 * s / math.cos(math.pi / 6.0)                 # raio dos vértices do sextavado
    # perfil (para z positivo «para cima» = para fora da cabeça); depois espelha-se z → −z
    v1, f1 = _torno([[(r * 0.97, 0.0), (r, 0.12 * k)], [(r, 0.12 * k), (r, k - ch)], [(r, k - ch), (r - ch, k)]], n=n)
    # topo com o furo sextavado: coroa entre o círculo r − ch e o hexágono, amostrados nos mesmos ângulos
    nh = 36
    th = np.arange(nh) * _TAU / nh
    ext = np.column_stack([(r - ch) * np.cos(th), (r - ch) * np.sin(th)])
    rr = np.array([_hexagono_r(s, t_) for t_ in th])
    hx = np.column_stack([rr * np.cos(th), rr * np.sin(th)])
    v, f = [], []
    for i in range(nh):
        v.append((ext[i, 0], ext[i, 1], k))
    for i in range(nh):
        v.append((hx[i, 0], hx[i, 1], k))
    for i in range(nh):
        i2 = (i + 1) % nh
        f += [(nh + i, i, i2), (nh + i, i2, nh + i2)]
    # paredes do rebaixo (vértices próprios por face do sextavado)
    passo = nh // 6
    for kf in range(6):
        idx = [(passo * kf + j) % nh for j in range(passo + 1)]
        b = len(v)
        v.extend((hx[i, 0], hx[i, 1], k) for i in idx)
        v.extend((hx[i, 0], hx[i, 1], k - t) for i in idx)
        for j in range(passo):
            f += [(b + j, b + j + 1, b + passo + 2 + j), (b + j, b + passo + 2 + j, b + passo + 1 + j)]
    # fundo cónico (118°) do rebaixo
    b = len(v)
    v.extend((hx[i, 0], hx[i, 1], k - t) for i in range(nh))
    v.append((0.0, 0.0, k - t - rh / math.tan(math.radians(59.0))))
    for i in range(nh):
        f.append((b + nh, b + i, b + (i + 1) % nh))
    m = _Malha().junta(v1, f1).junta(np.array(v), np.array(f, np.int64))
    # fundo da cabeça (face de apoio): coroa entre a haste e a orla
    m.junta(*_torno([[(0.0, 0.0), (r * 0.97, 0.0)]], n=n))
    vv, ff = m.arrays()
    vv[:, 2] *= -1.0                                       # topo para −z (a haste vai para +z)
    return vv, ff[:, ::-1]


@functools.cache
def _cabeca_7380(rosca: str, n: int = 24):
    """Cabeça abaulada ISO 7380 (face de apoio em z = 0, cúpula para −z) com o sextavado interior."""
    dk, k, s, t = ISO7380[rosca]
    r = 0.5 * dk
    rh = 0.5 * s / math.cos(math.pi / 6.0)
    r_topo = rh + 0.25 * (r - rh)
    pts = [(r, 0.0), (r, 0.08 * k)]
    for i in range(1, 9):                                   # arco da cúpula até à orla do sextavado
        a = 0.5 * math.pi * i / 8
        pts.append((r_topo + (r - r_topo) * math.cos(a), 0.08 * k + (k - 0.08 * k) * math.sin(a)))
    v1, f1 = _torno([pts], n=n)
    nh = 36
    th = np.arange(nh) * _TAU / nh
    ext = np.column_stack([r_topo * np.cos(th), r_topo * np.sin(th)])
    rr = np.array([_hexagono_r(s, t_) for t_ in th])
    hx = np.column_stack([rr * np.cos(th), rr * np.sin(th)])
    v, f = [], []
    v.extend((ext[i, 0], ext[i, 1], k) for i in range(nh))
    v.extend((hx[i, 0], hx[i, 1], k) for i in range(nh))
    for i in range(nh):
        i2 = (i + 1) % nh
        f += [(nh + i, i, i2), (nh + i, i2, nh + i2)]
    passo = nh // 6
    for kf in range(6):
        idx = [(passo * kf + j) % nh for j in range(passo + 1)]
        b = len(v)
        v.extend((hx[i, 0], hx[i, 1], k) for i in idx)
        v.extend((hx[i, 0], hx[i, 1], k - t) for i in idx)
        for j in range(passo):
            f += [(b + j, b + j + 1, b + passo + 2 + j), (b + j, b + passo + 2 + j, b + passo + 1 + j)]
    b = len(v)
    v.extend((hx[i, 0], hx[i, 1], k - t) for i in range(nh))
    v.append((0.0, 0.0, k - t - 0.3 * s))
    for i in range(nh):
        f.append((b + nh, b + i, b + (i + 1) % nh))
    m = _Malha().junta(v1, f1).junta(np.array(v), np.array(f, np.int64))
    m.junta(*_torno([[(0.0, 0.0), (r, 0.0)]], n=n))
    vv, ff = m.arrays()
    vv[:, 2] *= -1.0
    return vv, ff[:, ::-1]


@functools.cache
def _porca_4032(rosca: str):
    s, m = ISO4032[rosca]
    d = DIAMETRO[rosca]
    return _sextavado(s, 0.0, m, True, 0.5 * d * 0.86)


@functools.cache
def _porca_10511(rosca: str):
    """Autoblocante: a parte metálica sextavada (chanfro só na face de apoio) + a gola onde vive o anel de nylon,
    cravada por cima (a borda dobrada) — devolve (metal, nylon)."""
    s, h, mm = ISO10511[rosca]
    d = DIAMETRO[rosca]
    metal = _Malha()
    metal.junta(*_sextavado(s, 0.0, mm, True, 0.5 * d * 0.86))
    r_gola = 0.5 * s * 0.90
    metal.junta(*_torno([[(r_gola, mm), (r_gola, h - 0.35)], [(r_gola, h - 0.35), (r_gola - 0.45, h)],
                         [(r_gola - 0.45, h), (0.5 * d + 0.55, h)]], n=36))
    nylon = _torno([[(0.5 * d + 0.55, h - 0.001), (0.5 * d * 0.92, h - 0.001)],
                    [(0.5 * d * 0.92, h - 0.001), (0.5 * d * 0.92, mm)]], n=24)
    return metal.arrays(), nylon


@functools.cache
def _anilha_7089(rosca: str):
    d1, d2, h = ISO7089[rosca]
    r1, r2 = 0.5 * d1, 0.5 * d2
    return _torno([[(r1, 0.0), (r2, 0.0)], [(r2, 0.0), (r2, h)], [(r2, h), (r1, h)], [(r1, h), (r1, 0.0)]], n=32)


@functools.cache
def _anel_e(d_veio: float):
    """Anel E (DIN 6799) assente na ranhura: 3 dedos para dentro e a abertura (forma em C), espessura s."""
    dg, d3, s = DIN6799[min(DIN6799, key=lambda k: abs(k - d_veio))]
    r_in, r_out = 0.5 * dg, 0.5 * d3
    n = 40
    abertura = math.radians(70.0)
    v, f = [], []
    th = np.linspace(0.5 * abertura, _TAU - 0.5 * abertura, n)

    def r_int(t):                                          # 3 dedos a 0°, 120°, 240° tocam na ranhura
        dd = min(abs(((t - a + math.pi) % _TAU) - math.pi) for a in (math.pi, math.pi / 3.0, -math.pi / 3.0))
        return r_in if dd < math.radians(18.0) else r_in + 0.35 * (r_out - r_in)
    for z in (0.0, s):
        for t in th:
            v.append((r_out * math.cos(t), r_out * math.sin(t), z))
        for t in th:
            ri = r_int(t)
            v.append((ri * math.cos(t), ri * math.sin(t), z))
    o0, i0, o1, i1 = 0, n, 2 * n, 3 * n
    for j in range(n - 1):
        f += [(o1 + j, o1 + j + 1, i1 + j + 1), (o1 + j, i1 + j + 1, i1 + j)]        # topo (+z)
        f += [(o0 + j, i0 + j + 1, o0 + j + 1), (o0 + j, i0 + j, i0 + j + 1)]        # fundo (−z)
        f += [(o0 + j, o0 + j + 1, o1 + j + 1), (o0 + j, o1 + j + 1, o1 + j)]        # exterior (+r)
        f += [(i0 + j, i1 + j + 1, i0 + j + 1), (i0 + j, i1 + j, i1 + j + 1)]        # interior (−r)
    for j, sinal in ((0, 1), (n - 1, -1)):                 # as duas pontas da abertura
        q = [(o0 + j, i0 + j, i1 + j), (o0 + j, i1 + j, o1 + j)]
        f += q if sinal < 0 else [t[::-1] for t in q]
    return np.array(v, float), np.array(f, np.int64)


@functools.cache
def _pilar(rosca: str, comp: float, tipo: str, af: float, macho: float):
    """Pilar (espaçador) fêmea-fêmea ou macho-fêmea (`macho` = comprimento do perno roscado em +z, 0 = sem): sextavado
    (`af` entre faces) ou redondo (Ø `af`), de z = 0 a z = comp, com os furos roscados à vista nas pontas."""
    d = DIAMETRO[rosca]
    P = PASSO[rosca]
    m = _Malha()
    r_furo = 0.5 * d * 0.86
    if tipo == "sextavado":
        m.junta(*_sextavado(af, 0.0, comp, False, r_furo))
    else:
        m.junta(*_polar(lambda t, z: 0.5 * af, [0.0, comp], 32, r_furo=r_furo))
    if macho > 0.0:
        m.junta(*_rosca_ext(d, P, comp, comp + macho, True, n=12))
    return m.arrays()


@functools.cache
def _perno_916(rosca: str, comp: float):
    """Perno de sextavado interior DIN 916 (ponta côncava): rosca inteira, sextavado na face de cima (z = 0)."""
    d = DIAMETRO[rosca]
    P = PASSO[rosca]
    s = {"M2": 0.9, "M2.5": 1.3, "M3": 1.5, "M4": 2.0, "M5": 2.5, "M6": 3.0}[rosca]
    m = _Malha().junta(*_rosca_ext(d, P, 0.0, comp, True, n=12, tampa0=False))
    nh = 18
    th = np.arange(nh) * _TAU / nh
    rr = np.array([_hexagono_r(s, t_) for t_ in th])
    r_min = 0.5 * d - 0.6134 * P
    v = [(r_min * math.cos(t_) * 0.98, r_min * math.sin(t_) * 0.98, -0.001) for t_ in th]
    v += [(rr[i] * math.cos(th[i]), rr[i] * math.sin(th[i]), -0.001) for i in range(nh)]
    f = []
    for i in range(nh):
        i2 = (i + 1) % nh
        f += [(nh + i, i2, i), (nh + i, nh + i2, i2)]
    v.append((0.0, 0.0, 0.6 * comp))
    for i in range(nh):
        f.append((nh + i, len(v) - 1, nh + (i + 1) % nh))
    m.junta(np.array(v), np.array(f, np.int64))
    return m.arrays()


# ================================================================================================= orientação
def base_do_eixo(eixo, ref=None) -> np.ndarray:
    """Rotação PRÓPRIA (det +1) que leva o z local ao `eixo` (o x local ao longo de `ref` projetado, se dado)."""
    z = np.asarray(eixo, float)
    z = z / max(np.linalg.norm(z), 1e-12)
    if ref is None:
        ref = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
    x = np.asarray(ref, float) - np.dot(ref, z) * z
    if np.linalg.norm(x) < 1e-9:
        x = np.array([0.0, 1.0, 0.0]) - z[1] * z
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    return np.column_stack([x, y, z])


# ================================================================================================= coletor
@dataclass
class _Peca3d:
    corpo: str
    material: str
    v: np.ndarray            # m, no referencial do corpo
    f: np.ndarray
    peca: str
    inst: int


class Coletor:
    """Junta as ferragens de TODOS os módulos (uma malha por corpo × material no fim) e regista cada uma.

    Cada chamada devolve o(s) registo(s) da ferragem ({"tipo", "norma", "rosca", "comp_mm", "material", "corpo",
    "ponto", "eixo", "peca", "inst", …}) — com `desenhar=False` não desenha nada (o chamador já a desenhou numa peça
    própria, ex. os parafusos da hélice que giram com ela) e só regista."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.pecas: list[_Peca3d] = []
        self._fechado = False

    # ---------------------------------------------------------------- internos
    def _por(self, corpo, material_, v_mm, f, R, ponto, peca, inst):
        v = (np.asarray(v_mm, float) * MM) @ np.asarray(R, float).T + np.asarray(ponto, float)
        self.pecas.append(_Peca3d(str(corpo), material(material_), v, np.asarray(f, np.int64), peca, int(inst)))

    def _registo(self, **kw) -> dict:
        kw["ponto"] = [float(x) for x in kw["ponto"]]
        kw["eixo"] = [float(x) for x in kw["eixo"]]
        atual = self.ctx.peca_atual
        if kw.get("peca") is None and atual is not None:
            kw["peca"], kw["inst"] = atual
        if kw.get("peca") is None:
            kw["peca"] = "ferragens"
        kw["inst"] = int(kw.get("inst") or 0)
        kw["modulo"] = kw.get("modulo") or self.ctx.registo.modulo_atual
        self.ctx.registo.ferragens.append(kw)
        return kw

    @staticmethod
    def _peca_inst(ctx, peca, inst):
        if peca is None:
            atual = ctx.peca_atual
            if atual is not None:
                return atual
            return "ferragens", int(inst or 0)
        return peca, int(inst or 0)

    # ---------------------------------------------------------------- ferragens
    def parafuso(self, corpo: str, ponto, eixo, rosca: str, comp: float | None = None, aperto: float | None = None,
                 cabeca: str = "ISO 4762", porca: str | None = None, anilha_cabeca: bool = False,
                 anilha_porca: bool = True, material_: str = "aco_preto", material_porca: str | None = None,
                 rosca_metida: float | None = None, haste_visivel: tuple | None = None, ref=None,
                 peca: str | None = None, inst: int | None = None, desenhar: bool = True, modulo: str = "",
                 nota: str = "") -> dict:
        """Um PARAFUSO (e a porca/anilhas dele). `aperto` = espessura apertada entre a cabeça e a porca (mm), ou até ao
        fundo do furo roscado; sem `comp` escolhe-se o comprimento normalizado (com porca: aperto + anilhas + porca +
        ≥ 1 fio de fora; sem porca: aperto + `rosca_metida` (omissão 1,5·d em alumínio))."""
        peca, inst = self._peca_inst(self.ctx, peca, inst)
        d, P = DIAMETRO[rosca], PASSO[rosca]
        R = base_do_eixo(eixo, ref)
        z = R[:, 2]
        h_an_c = ISO7089[rosca][2] if anilha_cabeca else 0.0
        h_an_p = ISO7089[rosca][2] if (anilha_porca and porca) else 0.0
        h_porca = (ISO10511[rosca][1] if porca == "ISO 10511" else ISO4032[rosca][1] if porca == "ISO 4032" else 0.0)
        if comp is None:
            if aperto is None:
                raise ValueError("parafuso: dê `comp` ou `aperto`")
            if porca:
                minimo = aperto + h_an_c + h_an_p + h_porca + 1.0 * P
                comp = comprimento_normalizado(rosca, minimo, minimo + 6.0 * P + 2.0)
            else:
                metida = rosca_metida if rosca_metida is not None else 1.5 * d
                comp = comprimento_normalizado(rosca, aperto + h_an_c + metida - 0.5)
        if cabeca not in NORMAS_CABECA:
            raise ValueError(f"cabeça {cabeca!r}: use {NORMAS_CABECA}")
        if porca is not None and porca not in NORMAS_PORCA:
            raise ValueError(f"porca {porca!r}: use {NORMAS_PORCA}")
        p0 = np.asarray(ponto, float)
        reg = self._registo(desenhada=bool(desenhar), tipo="parafuso", norma=cabeca, rosca=rosca, comp_mm=float(comp), material=material(material_),
                            corpo=str(corpo), ponto=p0, eixo=z, peca=peca, inst=inst, aperto_mm=aperto,
                            porca=porca, anilha_cabeca=anilha_cabeca, anilha_porca=bool(anilha_porca and porca),
                            quat=_quat_de(R), modulo=modulo, nota=nota)
        p_cab = p0 - z * (h_an_c * MM)                    # face de apoio da CABEÇA (com anilha fica atrás dela)
        if desenhar:
            cab = _cabeca_4762(rosca) if cabeca == "ISO 4762" else _cabeca_7380(rosca)
            self._por(corpo, material_, *cab, R, p_cab, peca, inst)
            # rosca à vista (cotas a partir da face da cabeça): a ponta que sai da porca e o troço pedido entre peças
            if porca and aperto is not None:
                z_sai = h_an_c + aperto + h_an_p + h_porca
                if comp - z_sai > 0.05:
                    v, f = _rosca_ext(d, P, round(z_sai - 0.6, 6), round(float(comp), 6), True)
                    self._por(corpo, material_, v, f, R, p_cab, peca, inst)
            if haste_visivel is not None:
                za, zb = haste_visivel
                if zb - za > 0.05:
                    v, f = _rosca_ext(d, P, round(za, 6), round(zb, 6), zb >= comp - 1e-6)
                    self._por(corpo, material_, v, f, R, p_cab, peca, inst)
        if anilha_cabeca:
            self.anilha(corpo, p_cab, z, rosca, material_=material_, peca=peca, inst=inst, desenhar=desenhar,
                        modulo=modulo)
        if porca:
            mm_ = material(material_)
            if material_porca is not None:
                mat_p = material_porca
            elif mm_ in ("fer_nylon_branco", "fer_nylon_preto"):
                mat_p = material_
            elif mm_ == "fer_aco_inox":
                mat_p = "aco_inox"
            else:
                mat_p = "aco_zincado"
            p_an = p0 + z * ((aperto or 0.0) * MM)          # a face de trás da última peça apertada
            if anilha_porca:
                self.anilha(corpo, p_an, z, rosca, material_=mat_p, peca=peca, inst=inst, desenhar=desenhar,
                            modulo=modulo)
            self.porca(corpo, p_an + z * (h_an_p * MM), z, rosca, norma=porca, material_=mat_p, peca=peca, inst=inst,
                       desenhar=desenhar, modulo=modulo)
        return reg

    def porca(self, corpo, ponto, eixo, rosca: str, norma: str = "ISO 4032", material_: str = "aco_zincado",
              peca=None, inst=None, desenhar: bool = True, modulo: str = "", ref=None) -> dict:
        peca, inst = self._peca_inst(self.ctx, peca, inst)
        R = base_do_eixo(eixo, ref)
        reg = self._registo(desenhada=bool(desenhar), tipo="porca", norma=norma, rosca=rosca, comp_mm=None, material=material(material_),
                            corpo=str(corpo), ponto=ponto, eixo=R[:, 2], peca=peca, inst=inst, quat=_quat_de(R),
                            modulo=modulo)
        if desenhar:
            if norma == "ISO 10511":
                (vm, fm), (vn, fn) = _porca_10511(rosca)
                self._por(corpo, material_, vm, fm, R, ponto, peca, inst)
                self._por(corpo, "nylon_azul", vn, fn, R, ponto, peca, inst)
            else:
                self._por(corpo, material_, *_porca_4032(rosca), R, ponto, peca, inst)
        return reg

    def anilha(self, corpo, ponto, eixo, rosca: str, material_: str = "aco_inox", peca=None, inst=None,
               desenhar: bool = True, modulo: str = "") -> dict:
        """Anilha ISO 7089: `ponto` = a face de baixo, espessura para +`eixo`."""
        peca, inst = self._peca_inst(self.ctx, peca, inst)
        R = base_do_eixo(eixo)
        p = np.asarray(ponto, float)
        reg = self._registo(desenhada=bool(desenhar), tipo="anilha", norma="ISO 7089", rosca=rosca, comp_mm=None, material=material(material_),
                            corpo=str(corpo), ponto=p, eixo=R[:, 2], peca=peca, inst=inst, quat=_quat_de(R),
                            modulo=modulo)
        if desenhar:
            self._por(corpo, material_, *_anilha_7089(rosca), R, p, peca, inst)
        return reg

    def pilar(self, corpo, ponto, eixo, rosca: str, comp: float, tipo: str = "sextavado", af: float | None = None,
              macho: float = 0.0, material_: str = "latao", peca=None, inst=None, desenhar: bool = True,
              modulo: str = "", ref=None, macho_visivel: bool = False) -> dict:
        """Pilar/espaçador de `comp` mm de `ponto` ao longo de `eixo` (sextavado de `af` entre faces ou redondo de Ø
        `af`); `macho` > 0 = macho-fêmea (perno roscado a sair da ponta — no simulador só se desenha com
        `macho_visivel`, porque fica metido na peça seguinte; a página 3D mostra-o sempre)."""
        peca, inst = self._peca_inst(self.ctx, peca, inst)
        if af is None:
            af = {"M2": 4.0, "M2.5": 5.0, "M3": 5.5, "M4": 7.0}.get(rosca, 1.8 * DIAMETRO[rosca]) if tipo == "sextavado" \
                else 2.0 * DIAMETRO[rosca] - 1.0
        R = base_do_eixo(eixo, ref)
        reg = self._registo(desenhada=bool(desenhar), tipo="pilar", norma=f"pilar {tipo} {'M-F' if macho else 'F-F'}", rosca=rosca,
                            comp_mm=float(comp), material=material(material_), corpo=str(corpo), ponto=ponto,
                            eixo=R[:, 2], peca=peca, inst=inst, af_mm=float(af), macho_mm=float(macho),
                            quat=_quat_de(R), modulo=modulo)
        if desenhar:
            self._por(corpo, material_, *_pilar(rosca, round(float(comp), 6), tipo, round(float(af), 6),
                                                round(float(macho) if macho_visivel else 0.0, 6)), R, ponto, peca, inst)
        return reg

    def anel_e(self, corpo, ponto, eixo, d_veio: float, peca=None, inst=None, desenhar: bool = True,
               modulo: str = "", ref=None) -> dict:
        """Anel E (DIN 6799) na ranhura de um veio de Ø `d_veio` mm: `ponto` = face de apoio, `eixo` = para fora."""
        peca, inst = self._peca_inst(self.ctx, peca, inst)
        R = base_do_eixo(eixo, ref)
        reg = self._registo(desenhada=bool(desenhar), tipo="anel_e", norma="DIN 6799", rosca=f"Ø{d_veio:g}", comp_mm=None,
                            material=material("mola"), corpo=str(corpo), ponto=ponto, eixo=R[:, 2], peca=peca,
                            inst=inst, d_veio_mm=float(d_veio), quat=_quat_de(R), modulo=modulo)
        if desenhar:
            self._por(corpo, "mola", *_anel_e(float(d_veio)), R, ponto, peca, inst)
        return reg

    def perno(self, corpo, ponto, eixo, rosca: str, comp: float, material_: str = "aco_preto", peca=None, inst=None,
              desenhar: bool = True, modulo: str = "", ref=None) -> dict:
        """Perno de aperto DIN 916 (sem cabeça): `ponto` = a face do sextavado (à superfície do cubo), `eixo` = para
        dentro (para o veio)."""
        peca, inst = self._peca_inst(self.ctx, peca, inst)
        R = base_do_eixo(eixo, ref)
        reg = self._registo(desenhada=bool(desenhar), tipo="perno", norma="DIN 916", rosca=rosca, comp_mm=float(comp),
                            material=material(material_), corpo=str(corpo), ponto=ponto, eixo=R[:, 2], peca=peca,
                            inst=inst, quat=_quat_de(R), modulo=modulo)
        if desenhar:
            self._por(corpo, material_, *_perno_916(rosca, round(float(comp), 6)), R, ponto, peca, inst)
        return reg

    def registar(self, **kw) -> dict:
        """Só regista (a geometria já existe numa peça própria) — ex. a abraçadeira de nylon dos fios."""
        kw.setdefault("ponto", (0.0, 0.0, 0.0))
        kw.setdefault("eixo", (0.0, 0.0, 1.0))
        kw.setdefault("desenhada", False)
        kw.setdefault("modulo", "")
        return self._registo(**kw)

    # ---------------------------------------------------------------- fim
    def fechar(self) -> None:
        """Uma malha por corpo × material, com as faixas de faces de cada peça no registo."""
        if self._fechado:
            return
        self._fechado = True
        if not self.pecas:
            return
        for nome, (rgba, spec, brilho, refl) in MATERIAIS.items():
            if any(p.material == nome for p in self.pecas):
                self.ctx.material(nome, rgba, specular=spec, shininess=brilho, reflectance=refl)
        grupos: dict[tuple[str, str], list[_Peca3d]] = {}
        for p in self.pecas:
            grupos.setdefault((p.corpo, p.material), []).append(p)
        for (corpo, mat), lista in grupos.items():
            lista.sort(key=lambda q: (q.peca, q.inst))
            vs, fs, faixas = [], [], []
            nv = nf = 0
            for q in lista:
                vs.append(q.v)
                fs.append(q.f + nv)
                faixas.append((q.peca, q.inst, nf, nf + len(q.f)))
                nv += len(q.v)
                nf += len(q.f)
            # junta as faixas contíguas da mesma peça
            juntas = []
            for fx in faixas:
                if juntas and juntas[-1][0] == fx[0] and juntas[-1][1] == fx[1] and juntas[-1][3] == fx[2]:
                    juntas[-1] = (fx[0], fx[1], juntas[-1][2], fx[3])
                else:
                    juntas.append(fx)
            v = np.concatenate(vs)
            f = np.concatenate(fs)
            nome_geom = f"{mat}_{corpo}"
            nome_malha = f"m_{nome_geom}"
            me = self.ctx.spec.add_mesh(name=nome_malha)
            me.uservert = v.ravel().tolist()
            me.userface = f.ravel().tolist()
            me.inertia = mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL
            self.ctx.geom(corpo, nome_geom, type=mujoco.mjtGeom.mjGEOM_MESH, meshname=nome_malha, material=mat)
            self.ctx.registar_faixas(nome_geom, juntas)


def _quat_de(R) -> list[float]:
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.asarray(R, float).reshape(9))
    return [float(x) for x in q]


# ================================================================================================= página 3D
def chave(reg: dict) -> str:
    """Chave do TIPO da ferragem (uma malha por tipo na página): «ISO 4762 M3×8 fer_aco_preto»…"""
    t = reg["tipo"]
    if t == "parafuso":
        return f"{reg['norma']} {reg['rosca']}×{reg['comp_mm']:g} {reg['material']}"
    if t == "pilar":
        return f"{reg['norma']} {reg['rosca']}×{reg['comp_mm']:g} af{reg.get('af_mm', 0):g} m{reg.get('macho_mm', 0):g} " \
               f"{reg['material']}"
    if t == "perno":
        return f"{reg['norma']} {reg['rosca']}×{reg['comp_mm']:g} {reg['material']}"
    if t == "anel_e":
        return f"{reg['norma']} Ø{reg.get('d_veio_mm', 0):g} {reg['material']}"
    return f"{reg['norma']} {reg['rosca']} {reg['material']}"


def descricao(reg: dict) -> str:
    """Texto curto para a lista de ferragens (pt-PT)."""
    t = reg["tipo"]
    mat = {"fer_aco_preto": "aço 12.9 óxido negro", "fer_aco_inox": "inox A2", "fer_aco_zincado": "aço zincado",
           "fer_latao": "latão", "fer_aluminio": "alumínio", "fer_aluminio_preto": "alumínio anodizado preto",
           "fer_aluminio_vermelho": "alumínio anodizado vermelho", "fer_nylon_branco": "nylon PA66",
           "fer_nylon_preto": "nylon PA66 preto", "fer_titanio": "titânio Gr5", "fer_mola": "aço de mola"}.get(
        reg.get("material", ""), reg.get("material", ""))
    if t == "parafuso":
        cab = "cabeça cilíndrica sextavado interior" if reg["norma"] == "ISO 4762" else "cabeça abaulada"
        return f"Parafuso {reg['norma']} {reg['rosca']}×{reg['comp_mm']:g} mm ({cab}, {mat})"
    if t == "porca":
        nome = "Porca autoblocante (anel de nylon)" if reg["norma"] == "ISO 10511" else "Porca sextavada"
        return f"{nome} {reg['norma']} {reg['rosca']} ({mat})"
    if t == "anilha":
        return f"Anilha lisa ISO 7089 {reg['rosca']} ({mat})"
    if t == "pilar":
        return f"Pilar {reg['norma'].replace('pilar ', '')} {reg['rosca']}×{reg['comp_mm']:g} mm ({mat})"
    if t == "perno":
        return f"Perno de aperto DIN 916 {reg['rosca']}×{reg['comp_mm']:g} mm ({mat})"
    if t == "anel_e":
        return f"Anel E DIN 6799 para veio Ø{reg.get('d_veio_mm', 0):g} mm ({mat})"
    return reg.get("descricao") or f"{reg.get('norma', '')} {reg.get('rosca', '')}"


def malha_completa(reg: dict) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """A ferragem INTEIRA (para a página 3D), no referencial dela (m): [(material, v, f)] — o parafuso com a haste toda
    roscada (ou lisa+rosca, ISO 4762 com L > 2·b), a porca, a anilha…"""
    t = reg["tipo"]
    rosca = reg.get("rosca", "M3")
    mat = reg.get("material", "fer_aco_preto")
    out = []
    if t == "parafuso":
        d, P = DIAMETRO[rosca], PASSO[rosca]
        L = float(reg["comp_mm"])
        cab = _cabeca_4762(rosca) if reg["norma"] == "ISO 4762" else _cabeca_7380(rosca)
        out.append((mat, *cab))
        b = 2.0 * d + 6.0 if reg["norma"] == "ISO 4762" else L          # comprimento roscado (ISO 4762: b ≈ 2d + 6)
        z_rosca = max(0.0, L - b)
        if z_rosca > 0.2:
            out.append((mat, *_haste_lisa(d, 0.0, round(z_rosca, 6))))
        out.append((mat, *_rosca_ext(d, P, round(z_rosca, 6), round(L, 6), True)))
    elif t == "porca":
        if reg["norma"] == "ISO 10511":
            (vm, fm), (vn, fn) = _porca_10511(rosca)
            out += [(mat, vm, fm), ("fer_nylon_azul", vn, fn)]
        else:
            out.append((mat, *_porca_4032(rosca)))
    elif t == "anilha":
        out.append((mat, *_anilha_7089(rosca)))
    elif t == "pilar":
        out.append((mat, *_pilar(rosca, float(reg["comp_mm"]), "sextavado" if "sextavado" in reg["norma"] else "redondo",
                                 float(reg.get("af_mm", 5.0)), float(reg.get("macho_mm", 0.0)))))
    elif t == "perno":
        out.append((mat, *_perno_916(rosca, float(reg["comp_mm"]))))
    elif t == "anel_e":
        out.append((mat, *_anel_e(float(reg.get("d_veio_mm", 5.0)))))
    elif t == "amortecedor":
        out.append((mat, *_amortecedor()))
    elif t == "inserto":
        out.append((reg.get("material", "fer_latao"),
                     *_inserto(rosca, float(reg.get("comp_mm", 5.7)), float(reg.get("d_ext_mm", 4.6)))))
    elif t == "parafuso_ombro":
        for parte in _parafuso_ombro_7379(rosca, float(reg.get("comp_mm", 6.0))):
            out.append((mat, *parte))
    elif t == "parafuso_iso4017":
        for parte in _parafuso_4017(rosca, float(reg.get("comp_mm", 25.0))):
            out.append((mat, *parte))
    return [(m_, np.asarray(v, float) * MM, np.asarray(f, np.int64)) for m_, v, f in out]


# ISO 7379 (parafuso de ombro) por rosca: (Ø do ombro, Ø da cabeça, altura da cabeça, sextavado interior, rosca útil)
ISO7379 = {"M3": (4.0, 7.0, 3.0, 2.0, 4.5), "M4": (5.0, 8.0, 4.0, 2.5, 6.5), "M5": (6.0, 10.0, 4.5, 3.0, 7.5),
           "M6": (8.0, 13.0, 5.5, 4.0, 9.5)}
# ISO 4017 (sextavado, rosca até à cabeça) por rosca: (entre faces, altura da cabeça)
ISO4017 = {"M3": (5.5, 2.0), "M4": (7.0, 2.8), "M5": (8.0, 3.5), "M6": (10.0, 4.0), "M8": (13.0, 5.3)}


@functools.cache
def _parafuso_ombro_7379(rosca: str, comp: float):
    """Parafuso de OMBRO ISO 7379 (pivôs dos atuadores de fuso): cabeça cilíndrica com sextavado interior de z = −k a 0,
    o OMBRO retificado (Ø maior do que a rosca) de 0 a `comp` e a rosca útil depois. Medidas em mm."""
    d_o, dk, k, s_hex, b = ISO7379.get(rosca, ISO7379["M4"])
    d, P = DIAMETRO[rosca], PASSO[rosca]
    cab = _polar(lambda t, z: 0.5 * dk - (0.3 if z in (-k, 0.0) else 0.0), [-k, -k + 0.3, -0.3, 0.0], 32,
                 r_furo=0.5 * s_hex / math.cos(math.pi / 6) * 0.98)
    return [cab, _haste_lisa(d_o, 0.0, comp, n=24), _rosca_ext(d, P, comp, comp + b, True, n=12)]


@functools.cache
def _parafuso_4017(rosca: str, comp: float):
    """Parafuso SEXTAVADO ISO 4017 (rosca até à cabeça): cabeça de z = −k a 0 e a rosca de 0 a `comp`. Medidas em mm."""
    s_f, k = ISO4017.get(rosca, ISO4017["M8"])
    d, P = DIAMETRO[rosca], PASSO[rosca]
    return [_sextavado(s_f, -k, 0.0, True, None), _rosca_ext(d, P, 0.0, comp, True, n=12)]


@functools.cache
def _inserto(rosca: str, comp: float = 5.7, d_ext: float = 4.6):
    """Inserto de latão de cravar a quente (M3 × 5,7: Ø4,6 recartilhado, para um furo de Ø4,0 na peça impressa — pesquisa
    2026-10-20 §5): corpo de z = 0 (a face da peça) a z = comp, recartilhado em 2 bandas (o plástico derretido entra
    nas estrias e não o deixa rodar nem sair) com o furo roscado à vista. As medidas em mm."""
    d = DIAMETRO[rosca]
    r_furo = 0.5 * d * 0.86
    r0 = 0.5 * d_ext

    def raio(th, z):
        banda = (0.12 * comp < z < 0.45 * comp) or (0.55 * comp < z < 0.88 * comp)
        return r0 - (0.12 * (0.5 + 0.5 * math.cos(16.0 * th)) if banda else 0.18)

    zs = [0.0, 0.12 * comp, 0.12 * comp + 1e-3, 0.45 * comp - 1e-3, 0.45 * comp, 0.55 * comp, 0.55 * comp + 1e-3,
          0.88 * comp - 1e-3, 0.88 * comp, comp]
    return _polar(raio, zs, 48, r_furo=r_furo)


@functools.cache
def _amortecedor():
    """Amortecedor de silicone M3 do FC (carretel: abas Ø7,2 × 0,9 mm, alma Ø4,6 no furo da placa de 1,6 mm, furo
    Ø3,3) — origem na face de baixo da placa que ele isola; o mesmo perfil que a `eletronica` desenha."""
    return _torno([[(1.65, -0.9), (3.6, -0.9)], [(3.6, -0.9), (3.6, 0.0)], [(3.6, 0.0), (2.3, 0.0)],
                   [(2.3, 0.0), (2.3, 1.6)], [(2.3, 1.6), (3.6, 1.6)], [(3.6, 1.6), (3.6, 2.5)],
                   [(3.6, 2.5), (1.65, 2.5)], [(1.65, 2.5), (1.65, -0.9)]], n=24)


__all__ = [
    "BINARIO_NM",
    "COMPRIMENTOS",
    "DIAMETRO",
    "DIN6799",
    "ISO4032",
    "ISO4762",
    "ISO7089",
    "ISO7380",
    "ISO10511",
    "MATERIAIS",
    "PASSO",
    "Coletor",
    "base_do_eixo",
    "chave",
    "comprimento_normalizado",
    "descricao",
    "malha_completa",
    "material",
]
