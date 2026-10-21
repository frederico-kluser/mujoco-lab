"""lab/drone_rpi/detalhes/bateria3d.py — os PACKS DE BATERIA desenhados com FIDELIDADE (2026-10-20) e a biblioteca de
malhas fundidas do módulo `eletronica` (só aparência: massa 0, sem contacto, grupo 3 — regras no `Contexto`).

Pedido do dono: «as baterias quero que representem com fidelidade». Nada de um bloco a esconder o pack: vê-se a
construção real. Medidas, cores e fontes na pesquisa `pesquisas/2026-10-20-baterias-modelacao-3d-fiel.md` (resumidas
abaixo; web = dado não confiável, só citado). «estimado» = sem número oficial, escolhido por coerência e dito porquê.

PACKS 21700 (Molicel P50B / P45B, LG M50LT, Samsung 50E) — o arranjo dos packs comerciais: S GRUPOS lado a lado ao
longo de x (cada grupo = uma coluna de P células paralelas empilhadas: 6S2P = 6 × 2, 6S1P = 6 × 1, 6S3P = 3 camadas,
4S3P = 4 × 3), eixos das células ao longo de y, polaridade alternada por grupo (grupos ímpares com o + na face A = +y,
pares na face B = −y). TODAS as células uma a uma com as medidas NOMINAIS da ficha (P50B 21,40 × 70,00; P45B só há o
máximo 21,55 × 70,15; M50LT 21,1 × 70,5; 50E 21,1 × 70,6 medido), a manga real (P50B cinzenta com 2 faixas
cinzento-escuras junto ao + — fórum; P45B cinzenta; M50LT cinzento-escuro — as fontes divergem, escolheu-se a do
M50T; 50E ciano), o código 2D impresso, o polo + (tampa Ø9, junta preta, ombro cravado) com o anel isolador de papel
de peixe Ø19,8/10,5 × 0,2 mm e o fundo de aço da lata. Fitas série/paralelo nas duas faces: níquel 0,15 × 8 mm sobre
cobre 0,10 × 10 mm (a sanduíche Cu/Ni que um pack de 50 A pede — o níquel sozinho não chega), uma tira por coluna e
uma ponte por camada, 4 pontos de soldadura por extremo de célula; na face A as ligações 1→2, 3→4, 5→6, na face B
2→3, 4→5 e os dois TERMINAIS (G1− e G6+, nas colunas das pontas). Kapton âmbar translúcido sobre cada ligação, feltro
nas arestas de baixo das faces, BALANCEADOR com S+1 fios 22 AWG (Ø1,6), cada um a sair da fita da sua junção (pino 1 =
P−, pino S+1 = P+), por baixo do termorretrátil até à traseira e daí à ficha JST-XH (S+1 vias, passo 2,5 mm; 7 vias =
19,8 × 5,7 × 7,5 mm) `el_bat_balanco`; CABOS PRINCIPAIS 10 AWG (Ø5,5) de silicone dos terminais (soldados no cobre,
`el_bat_terminal_pos/neg`) ao XT90 fêmea `conector_xt90` (o P+ corre por fora da face B, preso pelas cintas, como nos
packs DIY). Termorretrátil de PVC TRANSPARENTE (existe à venda: «clear») com uma tonalidade azulada leve (α 0,2) — a
ESCOLHA para se verem as células, as fitas e o balanceador — e um rótulo branco na face A.
PACKS POUCH comerciais (Gens Ace 6S 5000 45C, Tattu semi-sólido 6S1P 12 Ah, Tattu G-Tech 4S 10 Ah, LiPo 4S/3S 1500):
as células empilhadas com a espessura real (espessura do pack / S, menos o invólucro e a espuma), as abas soldadas na
placa de topo, espuma por cima e por baixo, o invólucro de PVC impresso OPACO (o real; cores não publicadas →
estimadas), cabos 10 AWG, balanceador e ficha. Amprius SA102 6S2P (DIY): 2 pilhas de 6 bolsas 56,5 × 49,5 × 5,5 com
PLACAS DE COMPRESSÃO de alumínio de 3 mm e 6 parafusos M3 (a célula exige 30 PSI ≈ 207 kPa: ≈ 540 N por pilha),
almofadas de silicone, barramento de abas em FR4 na face B e PVC transparente em cada pilha.

MONTAGEM no drone: cada pack pendurado debaixo da placa de baixo sobre o TAPETE anti-derrapante (EVA de 4 mm, em
almofadas entre as cintas e com furos onde há porcas por baixo da placa) e 2 CINTAS de 15 mm (nylon com fivela de
alumínio anodizado), JUSTAS ao pack, que sobem pelos RASGOS da placa em (±28, ±15) mm do centro do pack — DENTRO da
pegada do pack: a cinta corre por cima do pack, entre ele e a placa, e por cima da placa só atravessa |y| ≤ 17 mm
(longe dos pilares da Raspberry Pi 5 em y = ±24,5; a ±39,8 mm, onde estavam, a cinta esquerda batia nos pilares em
x = −39 mm). Os rasgos ficam em `registo.notas["rasgos_cintas"]` para o módulo `estrutura` os cortar.
SENSORES DE BAIXO (PMW3901 + VL53L1X): o ToF e o fluxo do simulador medem no site `baixo` (`sensores.py`: `rangefinder`
e `velocimeter` no site; `modelo.py`: 4 mm por baixo da caixa física do pack, no eixo). As placas ficam NESSE sítio (a
janela do VL53L1X à cota do site), numa travessa de PETG presa à PLACA por 2 pernas e 2 parafusos M3 — não às cintas,
para não mudarem de sítio na troca ao vivo. Um pack mais alto do que o espaço acima do site (o 6S3P em 3 camadas)
cobriria as placas: para esse a travessa desce com o pack (a variante traz a sua, `dz` no registo da variante = quanto
o site `baixo` teria de descer para a física acompanhar — o simulador hoje não o move). No frame IMPRESSO (`*_abs`, 2.ª
fase) a travessa é de ABS (`MATERIAL_ABS`) e imprimível: pernas e pés com a largura da travessa (24 mm), as pernas a
partir do topo da travessa (sólidos fechados que só se tocam: volume exato) — imprime-se deitada sobre a face −x
(`notas["impressas"]["bandeja_sensores#0"]`, orientação `Q_DE_LADO`).

TROCA AO VIVO: os 6 packs de `CATALOGO_BATERIAS_PAINEL` ficam no modelo (`ctx.registar_variante("bateria", id, …)`, alfa
0 nas inativas: custo de desenho 0); a ativa é a do build quando a célula, S e P coincidem; senão o pack do build fica
visível como variante com o id dele. Cada variante = pack + cabos + balanceador + ficha + cintas + tapete (+ travessa
dos sensores quando a sua é outra). O XT90 (fêmea + macho do drone com os copos `el_xt90_copo_pos/neg`) é fixo:
todos os packs terminam num XT90 (o Tattu semi-sólido traz de fábrica o XT90S-F anti-faísca; os outros re-terminados).

Fontes: Molicel P50B https://www.molicel.com/wp-content/uploads/Product-Data-Sheet-of-INR-21700-P50B-80122.pdf e
https://www.dnkpower.com/wp-content/uploads/2024/11/Molicel-INR21700P50B.pdf · P45B
https://www.molicel.com/wp-content/uploads/INR21700P45B_1.2_Product-Data-Sheet-of-INR-21700-P45B-80109.pdf · LG M50LT
https://f.hubspotusercontent10.net/hubfs/6584819/Cell%20Spec%20Sheets/LG/Lithium%20Ion%20LG%20INR%2021700%20M50LT%202021-LSD-MBD-b00002_21700_M50LT_PS_Promotion_V1.pdf
· Samsung 50E https://lygte-info.dk/review/batteries2012/Samsung%20INR21700-50E%205000mAh%20(Cyan)%20UK.html · cores
https://liionwholesale.com/products/molicel-npe-inr-21700-p50b-60a-5000mah-flat-top-21700-battery-authorized-distributor
· anel https://renewspark.com/products/21700-insulator-rings-fish-paper · fitas https://cellsaviors.com/blog/copper-nickel-sandwich
e https://blog.uavmodel.com/diy-li-ion-battery-pack-building-for-long-range-fpv-drones-cells-welding-and-safety ·
6S2P comerciais https://wrekd.com/products/6s2p-21-6v-molicel-p50b-10000mah-li-ion-battery-pack ·
https://www.au-line.com/products/21700-s70-ultra-10000mah-6s2p-22-2v-140a-xt60-xt90 · JST-XH
https://www.jst-mfg.com/product/pdf/eng/eXH.pdf · XT90 http://shop.smc-powers.com/XT90H-F.html (contactos Ø4,5),
https://maxamps.com/products/xt90-male-connector (31 × 21 × 10), https://mjbots.com/products/xt90s-f · Amprius SA102
https://amprius.com/documents/Amprius_Product_Catalog.pdf · Tattu 12 Ah
https://www.tattuworld.com/products/tattu-380wh-kg-12000mah-6s1p-22-2v-10c-semi-solid-state-uav-lipo-battery.html ·
Tattu G-Tech 4S https://www.grepow.com/uav-battery/tattu-4s-10000mah-14-8v-25c-lipo-drone-battery.html · Gens Ace
https://genstattu.com/gens-ace-5000mah-6s-45c-22-2v-g-tech-lipo-battery-pack-with-ec5-plug · LiPo 1500
https://www.racedayquads.com/products/lumenier-1500mah-4s-75c-lipo-battery · silicone 10 AWG
https://bntechgo.com/bntechgo-10-gauge-silicone-wire-spool-red-250-feet-ultra-flexible-high-temp-200-c-600v-10-awg-silicone-rubber-wire-with-1050-strands-of-tinned-copper-wire-stranded-wire-for-model-battery
· PVC transparente https://dee5shrink.com/pvc-heat-shrink-sleeves-for-battery · PMW3901
https://shop.pimoroni.com/products/pmw3901-optical-flow-sensor-breakout · VL53L1X https://www.pololu.com/product/3415.

A BIBLIOTECA (usada também pela `eletronica`): geradores de malhas em mm (`g_caixa`, `g_caixa_arred`, `g_cil`,
`g_anel`, `g_tubo`, `g_fita`, `g_prisma`, `g_placa_furos`, `g_extrusao_y`) e o `Fundidor` — junta tudo o que tem o
mesmo (corpo, material, variante) numa malha e regista as FAIXAS DE FACES de cada peça (`ctx.registar_faixas`).
"""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass, field

import mujoco
import numpy as np

from .ferragens import (
    ISO7380,
    _anilha_7089,
    _cabeca_7380,
    _porca_4032,
    _porca_10511,
    _torno,
    base_do_eixo,
)

MM = 1e-3
TAU = 2.0 * math.pi
_G = mujoco.mjtGeom


# =================================================================================================== geometria (mm)
def _arr(v, f):
    return np.asarray(v, float).reshape(-1, 3), np.asarray(f, np.int64).reshape(-1, 3)


def juntar(*partes):
    """Junta várias (v, f) numa só."""
    vs, fs, n = [], [], 0
    for v, f in partes:
        v, f = _arr(v, f)
        if len(f) == 0:
            continue
        vs.append(v)
        fs.append(f + n)
        n += len(v)
    if not vs:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    return np.concatenate(vs), np.concatenate(fs)


def mover(vf, R=None, p=None):
    """(v, f) rodado por R (det ±1: com det −1 as faces viram para fora outra vez) e deslocado de p."""
    v, f = _arr(*vf)
    if R is not None:
        R = np.asarray(R, float)
        v = v @ R.T
        if np.linalg.det(R) < 0:
            f = f[:, ::-1]
    if p is not None:
        v = v + np.asarray(p, float)
    return v, f


def sem_degeneradas(v, f, area_min: float = 1e-10):
    """Tira triângulos de área (quase) nula — o compilador do MuJoCo poderia tirá-los e baralhar as faixas."""
    v, f = _arr(v, f)
    if len(f) == 0:
        return v, f
    t = v[f]
    a = np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    return v, f[a > area_min]


def _quad(v: list, f: list, a, b, c, d, n) -> None:
    """Quadrilátero a-b-c-d (vértices próprios: aresta viva) com a normal do lado de `n`."""
    a, b, c, d = (np.asarray(x, float) for x in (a, b, c, d))
    if np.dot(np.cross(b - a, c - a), np.asarray(n, float)) < 0:
        b, d = d, b
    i = len(v)
    v.extend([a, b, c, d])
    f.extend([(i, i + 1, i + 2), (i, i + 2, i + 3)])


def _caixa_modelo():
    v, f = [], []
    _quad(v, f, (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, -1))
    _quad(v, f, (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1), (0, 0, 1))
    _quad(v, f, (0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1), (0, -1, 0))
    _quad(v, f, (0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1), (0, 1, 0))
    _quad(v, f, (0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1), (-1, 0, 0))
    _quad(v, f, (1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1), (1, 0, 0))
    return np.asarray(v, float), np.asarray(f, np.int64)


_CAIXA_V, _CAIXA_F = _caixa_modelo()


def g_caixa(x0, x1, y0, y1, z0, z1):
    """Caixa pelos limites (arestas vivas, 12 triângulos)."""
    lo = np.array([min(x0, x1), min(y0, y1), min(z0, z1)])
    hi = np.array([max(x0, x1), max(y0, y1), max(z0, z1)])
    return lo + _CAIXA_V * (hi - lo), _CAIXA_F.copy()


@functools.lru_cache(maxsize=512)
def _caixa_arred_c(hx, hy, hz, r, n):
    """Caixa centrada (meias medidas h) com TODAS as arestas e cantos arredondados de raio r (esfera-cubo: as faces
    planas são as tiras entre as costuras duplicadas da esfera UV)."""
    r = max(1e-4, min(r, hx - 1e-4, hy - 1e-4, hz - 1e-4))
    ix, iy, iz = hx - r, hy - r, hz - r
    sinais = ((1, 1), (-1, 1), (-1, -1), (1, -1))
    lon, sxy = [], []
    for q in range(4):
        for i in range(n + 1):
            lon.append(q * 0.5 * math.pi + 0.5 * math.pi * i / n)
            sxy.append(sinais[q])
    lat, sz = [], []
    for i in range(n + 1):
        lat.append(-0.5 * math.pi + 0.5 * math.pi * i / n)
        sz.append(-1)
    for i in range(n + 1):
        lat.append(0.5 * math.pi * i / n)
        sz.append(1)
    nl, nc = len(lat), len(lon)
    v = np.zeros((nl * nc, 3))
    for j, (la, s_z) in enumerate(zip(lat, sz)):
        cl, sl = math.cos(la), math.sin(la)
        for i, (lo, (s_x, s_y)) in enumerate(zip(lon, sxy)):
            v[j * nc + i] = (s_x * ix + r * cl * math.cos(lo), s_y * iy + r * cl * math.sin(lo), s_z * iz + r * sl)
    f = []
    for j in range(nl - 1):
        for i in range(nc):
            i2 = (i + 1) % nc
            a, b, c, d = j * nc + i, j * nc + i2, (j + 1) * nc + i2, (j + 1) * nc + i
            f += [(a, b, c), (a, c, d)]
    # tampas de cima e de baixo (o retângulo entre os 4 cantos dos polos)
    cima = [(nl - 1) * nc + q * (n + 1) for q in range(4)]
    baixo = [q * (n + 1) for q in range(4)]
    f += [(cima[0], cima[1], cima[2]), (cima[0], cima[2], cima[3])]
    f += [(baixo[0], baixo[2], baixo[1]), (baixo[0], baixo[3], baixo[2])]
    return sem_degeneradas(v, np.array(f, np.int64))


def g_caixa_arred(x0, x1, y0, y1, z0, z1, r, n: int = 3):
    """Caixa pelos limites com arestas arredondadas de raio r (n segmentos por quarto de volta)."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    v, f = _caixa_arred_c(round(0.5 * (x1 - x0), 6), round(0.5 * (y1 - y0), 6), round(0.5 * (z1 - z0), 6),
                          round(float(r), 6), int(n))
    return v + np.array([0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)]), f


@functools.lru_cache(maxsize=512)
def g_cil(r, z0, z1, n: int = 24, tampa0: bool = True, tampa1: bool = True):
    """Cilindro de eixo z (tampas planas com aresta viva)."""
    seg = []
    if tampa0:
        seg.append([(0.0, z0), (r, z0)])
    seg.append([(r, z0), (r, z1)])
    if tampa1:
        seg.append([(r, z1), (0.0, z1)])
    return _torno(seg, n=n)


@functools.lru_cache(maxsize=512)
def g_anel(r0, r1, z0, z1, n: int = 24):
    """Anel (coroa espessa) de eixo z entre os raios r0 < r1 e as cotas z0 < z1."""
    return _torno([[(r0, z0), (r1, z0)], [(r1, z0), (r1, z1)], [(r1, z1), (r0, z1)], [(r0, z1), (r0, z0)]], n=n)


def eixo_para(eixo) -> np.ndarray:
    """Rotação que leva o z local ao `eixo` (o x local no plano de `ref` por omissão)."""
    return base_do_eixo(eixo)


def arredondar(pts, raio: float, n: int = 4, fechada: bool = False, raios=None) -> np.ndarray:
    """Polilinha com os cantos arredondados (arco de Bézier quadrático de `n` pontos por canto; `raios` por vértice)."""
    p = [np.asarray(x, float) for x in pts]
    if len(p) < 3:
        return np.array(p)
    m = len(p)
    idx = range(m) if fechada else range(1, m - 1)
    out = [] if fechada else [p[0]]
    for i in idx:
        a, b, c = p[(i - 1) % m], p[i], p[(i + 1) % m]
        ra = raio if raios is None else raios[i]
        la, lc = np.linalg.norm(b - a), np.linalg.norm(c - b)
        if la < 1e-9 or lc < 1e-9 or ra <= 0:
            out.append(b)
            continue
        ua, uc = (b - a) / la, (c - b) / lc
        ang = math.acos(max(-1.0, min(1.0, float(np.dot(ua, uc)))))
        if ang < 1e-3:
            out.append(b)
            continue
        d = min(ra * math.tan(0.5 * ang), 0.45 * la, 0.45 * lc)
        p0, p2 = b - ua * d, b + uc * d
        for k in range(n + 1):
            t = k / n
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p2)
    if not fechada:
        out.append(p[-1])
    res = [out[0]]
    for q in out[1:]:
        if np.linalg.norm(q - res[-1]) > 1e-6:
            res.append(q)
    return np.array(res)


def _tangentes(p: np.ndarray, fechada: bool) -> np.ndarray:
    p = np.asarray(p, float)
    if fechada:
        d = np.roll(p, -1, axis=0) - np.roll(p, 1, axis=0)
    else:
        seg = np.diff(p, axis=0)
        un = seg / np.maximum(np.linalg.norm(seg, axis=1, keepdims=True), 1e-9)
        d = np.zeros_like(p)
        d[0], d[-1] = seg[0], seg[-1]
        if len(p) > 2:
            d[1:-1] = un[1:] + un[:-1]
    return d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)


def _quadros(p: np.ndarray, t: np.ndarray, n0) -> tuple[np.ndarray, np.ndarray]:
    """Normais transportadas em paralelo ao longo da polilinha (e as binormais t × n)."""
    m = len(p)
    if n0 is not None:
        n = np.asarray(n0, float)
    else:
        n = np.cross(t[0], (0.0, 0.0, 1.0) if abs(t[0][2]) < 0.9 else (1.0, 0.0, 0.0))
    N = np.zeros((m, 3))
    for i in range(m):
        n = n - (n @ t[i]) * t[i]
        nn = math.sqrt(float(n @ n))
        n = n / nn if nn > 1e-12 else N[i - 1]
        N[i] = n
    return N, np.cross(t, N)


def g_tubo(pts, raio: float, lados: int = 8, tampas: bool = True, n0=None):
    """Tubo (cabo) de raio `raio` ao longo da polilinha `pts`: quadros transportados em paralelo e, em cada vértice, a
    secção em MEIA-ESQUADRIA (elipse no plano bissetor: o tubo não emagrece nas curvas); tampas planas."""
    p = np.asarray(pts, float)
    if len(p) < 2:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    keep = np.concatenate([[True], np.linalg.norm(np.diff(p, axis=0), axis=1) > 1e-6])
    p = p[keep]
    m = len(p)
    if m < 2:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    t = _tangentes(p, False)
    N, B = _quadros(p, t, n0)
    K = np.zeros((m, 3))
    esc = np.ones(m)
    if m > 2:
        seg = np.diff(p, axis=0)
        u = seg / np.linalg.norm(seg, axis=1, keepdims=True)
        kk = u[1:] - u[:-1]
        nk = np.linalg.norm(kk, axis=1)
        ok = nk > 1e-9
        K[1:-1][ok] = kk[ok] / nk[ok, None]
        esc[1:-1] = np.where(ok, 1.0 / np.maximum(0.35, np.einsum("ij,ij->i", u[:-1], t[1:-1])), 1.0)
    th = np.arange(lados) * TAU / lados
    D = np.cos(th)[None, :, None] * N[:, None, :] + np.sin(th)[None, :, None] * B[:, None, :]
    proj = np.einsum("mlk,mk->ml", D, K)
    D = D + ((esc - 1.0)[:, None] * proj)[:, :, None] * K[:, None, :]
    V = (p[:, None, :] + raio * D).reshape(-1, 3)
    i = np.arange(m - 1)[:, None]
    j = np.arange(lados)[None, :]
    j2 = (j + 1) % lados
    a, b, c, d = i * lados + j, i * lados + j2, (i + 1) * lados + j2, (i + 1) * lados + j
    F = np.concatenate([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([a, c, d], -1).reshape(-1, 3)])
    if tampas:
        cen = len(V)
        V = np.vstack([V, p[0], p[-1]])
        jj = np.arange(lados)
        c0 = np.stack([np.full(lados, cen), (jj + 1) % lados, jj], -1)
        c1 = np.stack([np.full(lados, cen + 1), (m - 1) * lados + jj, (m - 1) * lados + (jj + 1) % lados], -1)
        F = np.concatenate([F, c0, c1])
    return V, F.astype(np.int64)


def g_fita(pts, largura: float, esp: float, ref_b=(1.0, 0.0, 0.0), fechada: bool = False):
    """Fita de secção retangular (largura ao longo de `ref_b` projetado, espessura na outra direção) ao longo da
    polilinha — cintas, abraçadeiras, fitas de níquel dobradas. Cada lado com vértices próprios (aresta viva)."""
    p = np.asarray(pts, float)
    if len(p) < 2:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    t = _tangentes(p, fechada)
    rb = np.asarray(ref_b, float)
    bs = rb[None, :] - (t @ rb)[:, None] * t
    nb = np.linalg.norm(bs, axis=1)
    for i in range(len(p)):                                 # direção da largura indefinida: a do ponto anterior
        if nb[i] < 1e-6:
            bs[i] = bs[i - 1] if i else np.cross(t[i], (0.0, 0.0, 1.0))
            nb[i] = np.linalg.norm(bs[i])
    bs = bs / nb[:, None]
    ns = np.cross(t, bs)
    hw, he = 0.5 * largura, 0.5 * esp
    cantos = [(-hw, -he), (hw, -he), (hw, he), (-hw, he)]
    m = len(p)
    nseg = m if fechada else m - 1
    Vs, Fs = [], []
    base = 0
    i = np.arange(nseg)
    i2 = (i + 1) % m
    for lado in range(4):
        (b0, n0), (b1, n1) = cantos[lado], cantos[(lado + 1) % 4]
        va = p + bs * b0 + ns * n0
        vb = p + bs * b1 + ns * n1
        V = np.empty((2 * m, 3))
        V[0::2], V[1::2] = va, vb
        a, b, c, d = base + 2 * i, base + 2 * i + 1, base + 2 * i2 + 1, base + 2 * i2
        Fs.append(np.concatenate([np.stack([a, b, c], -1), np.stack([a, c, d], -1)]))
        Vs.append(V)
        base += 2 * m
    if not fechada:                                         # pontas
        for k, sinal in ((0, -1.0), (m - 1, 1.0)):
            quad = [p[k] + bs[k] * cb + ns[k] * cn for cb, cn in cantos]
            vv, ff = [], []
            _quad(vv, ff, *quad, sinal * t[k])
            Vs.append(np.asarray(vv))
            Fs.append(np.asarray(ff) + base)
            base += 4
    return np.concatenate(Vs), np.concatenate(Fs).astype(np.int64)


def g_prisma(poligono, z0, z1):
    """Prisma de um polígono CONVEXO (x, y) anti-horário, de z0 a z1."""
    pol = [np.asarray(q, float) for q in poligono]
    m = len(pol)
    v, f = [], []
    for k in range(m):
        a, b = pol[k], pol[(k + 1) % m]
        nrm = np.array([b[1] - a[1], -(b[0] - a[0]), 0.0])
        _quad(v, f, (a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1), nrm)
    for z, s in ((z0, -1.0), (z1, 1.0)):
        b0 = len(v)
        v.extend((q[0], q[1], z) for q in pol)
        for k in range(1, m - 1):
            tri = (b0, b0 + k, b0 + k + 1)
            f.append(tri if s > 0 else tri[::-1])
    return _arr(v, f)


def _anel_quadrado(cx, cy, a, r, z, cima: bool, n: int):
    """Triangulação plana do quadrado [cx±a]×[cy±a] menos o círculo de raio r (normal ±z)."""
    th = np.arange(n) * TAU / n + math.pi / n
    v, f = [], []
    circ = [(cx + r * math.cos(t), cy + r * math.sin(t), z) for t in th]
    # o ponto do quadrado na mesma direção (projeção radial no quadrado)
    quad = []
    for t in th:
        c, s = math.cos(t), math.sin(t)
        k = a / max(abs(c), abs(s))
        quad.append((cx + k * c, cy + k * s, z))
    cantos = [(cx + a, cy + a, z), (cx - a, cy + a, z), (cx - a, cy - a, z), (cx + a, cy - a, z)]
    v.extend(circ)
    v.extend(quad)
    v.extend(cantos)
    for i in range(n):
        i2 = (i + 1) % n
        f += [(i, n + i, n + i2), (i, n + i2, i2)]
    # os 4 cantos: o triângulo entre os dois pontos do quadrado de cada lado do canto
    angc = [math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4]
    for j, ac in enumerate(angc):
        i = math.floor((ac - math.pi / n) / (TAU / n)) % n
        f.append((n + i, 2 * n + j, n + (i + 1) % n))
    v, f = _arr(v, f)
    nz = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])[:, 2]
    errados = (nz < 0) if cima else (nz > 0)
    f[errados] = f[errados][:, ::-1]
    return v, f


def g_placa_furos(x0, x1, y0, y1, z0, z1, furos=(), n: int = 16, margem: float = 0.6):
    """Placa retangular com FUROS redondos [(cx, cy, r)] que a atravessam (paredes incluídas). Grelha das caixas dos
    furos: a célula que é a caixa de um furo leva a coroa (quadrado − círculo); uma caixa partida por outro furo
    desalinhado vira furo quadrado (células vazias com paredes); o resto são retângulos cheios."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    furos = [(float(cx), float(cy), float(r)) for cx, cy, r in furos
             if x0 + r + 0.2 < cx < x1 - r - 0.2 and y0 + r + 0.2 < cy < y1 - r - 0.2]
    # meia-caixa de cada furo: furos alinhados (mesmo x ou mesmo y) com a MESMA caixa e furos desalinhados com caixas
    # que não se sobrepõem nesse eixo — as linhas da grelha nunca partem a caixa de um furo
    n_f = len(furos)
    a = [r + margem for _cx, _cy, r in furos]
    for _it in range(6):
        for i in range(n_f):
            cxi, cyi, ri = furos[i]
            a[i] = min(a[i], cxi - x0 - 0.1, x1 - cxi - 0.1, cyi - y0 - 0.1, y1 - cyi - 0.1)
            for j in range(n_f):
                if j == i:
                    continue
                cxj, cyj, rj = furos[j]
                for di in (abs(cxi - cxj), abs(cyi - cyj)):
                    if di < 1e-6:
                        a[i] = a[j] = min(a[i], a[j])           # alinhados: a mesma caixa
                    elif di < a[i] + a[j] + 0.02:
                        lim = 0.5 * (di - 0.02)
                        a[i] = max(min(a[i], lim), ri + 0.12)
                        a[j] = max(min(a[j], lim), rj + 0.12)
    caixas = [(cx - ai, cx + ai, cy - ai, cy + ai, cx, cy, r, ai) for (cx, cy, r), ai in zip(furos, a)]
    xs = sorted({round(x, 6) for x in (x0, x1, *[c[0] for c in caixas], *[c[1] for c in caixas])})
    ys = sorted({round(y, 6) for y in (y0, y1, *[c[2] for c in caixas], *[c[3] for c in caixas])})
    nx, ny = len(xs) - 1, len(ys) - 1
    estado = [["cheia"] * ny for _ in range(nx)]
    anel = {}
    for i in range(nx):
        for j in range(ny):
            xa, xb, ya, yb = xs[i], xs[i + 1], ys[j], ys[j + 1]
            for c in caixas:
                if xa < c[1] - 1e-6 and c[0] + 1e-6 < xb and ya < c[3] - 1e-6 and c[2] + 1e-6 < yb:
                    if abs(xa - c[0]) < 1e-5 and abs(xb - c[1]) < 1e-5 and abs(ya - c[2]) < 1e-5 and abs(yb - c[3]) < 1e-5:
                        estado[i][j] = "anel"
                        anel[(i, j)] = c
                    else:
                        estado[i][j] = "vazia"
                    break
    v, f, partes = [], [], []
    for i in range(nx):
        for j in range(ny):
            xa, xb, ya, yb = xs[i], xs[i + 1], ys[j], ys[j + 1]
            if estado[i][j] == "cheia":
                for z, sz in ((z1, 1.0), (z0, -1.0)):
                    _quad(v, f, (xa, ya, z), (xb, ya, z), (xb, yb, z), (xa, yb, z), (0, 0, sz))
            elif estado[i][j] == "anel":
                _c0, _c1, _c2, _c3, cx, cy, r, a = anel[(i, j)]
                partes.append(_anel_quadrado(cx, cy, a, r, z1, True, n))
                partes.append(_anel_quadrado(cx, cy, a, r, z0, False, n))
                pv, pf = _torno([[(r, z1), (r, z0)]], n=n, fase=math.pi / n)   # parede do furo (normal para o eixo)
                partes.append((pv + np.array([cx, cy, 0.0]), pf))
            else:                                               # furo quadrado: paredes para os vizinhos cheios
                for di, dj, a_, b_, nrm in ((-1, 0, (xa, ya), (xa, yb), (1, 0, 0)), (1, 0, (xb, ya), (xb, yb), (-1, 0, 0)),
                                            (0, -1, (xa, ya), (xb, ya), (0, 1, 0)), (0, 1, (xa, yb), (xb, yb), (0, -1, 0))):
                    ii, jj = i + di, j + dj
                    if 0 <= ii < nx and 0 <= jj < ny and estado[ii][jj] != "vazia":
                        _quad(v, f, (a_[0], a_[1], z0), (b_[0], b_[1], z0), (b_[0], b_[1], z1), (a_[0], a_[1], z1), nrm)
    for (xa, xb, ya, yb, nrm) in ((x0, x1, y0, y0, (0, -1, 0)), (x0, x1, y1, y1, (0, 1, 0)),
                                  (x0, x0, y0, y1, (-1, 0, 0)), (x1, x1, y0, y1, (1, 0, 0))):
        _quad(v, f, (xa, ya, z0), (xb, yb, z0), (xb, yb, z1), (xa, ya, z1), nrm)
    return juntar((np.array(v).reshape(-1, 3), np.array(f, np.int64).reshape(-1, 3)), *partes)


def retangulo_arred(w: float, h: float, r: float, n: int = 6):
    """Contorno (x, z) anti-horário de um retângulo w × h centrado com cantos de raio r (n pontos por canto)."""
    r = max(0.0, min(r, 0.5 * w - 1e-6, 0.5 * h - 1e-6))
    pts = []
    cs = ((0.5 * w - r, 0.5 * h - r, 0.0), (-0.5 * w + r, 0.5 * h - r, 0.5 * math.pi),
          (-0.5 * w + r, -0.5 * h + r, math.pi), (0.5 * w - r, -0.5 * h + r, 1.5 * math.pi))
    for cx, cz, a0 in cs:
        for k in range(n + 1):
            a = a0 + 0.5 * math.pi * k / n
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def g_extrusao_y(w: float, h: float, r: float, y0: float, y1: float, r_e: float, xc: float = 0.0,
                 zc: float = 0.0, n: int = 6, n_e: int = 3):
    """Sólido de secção x-z retangular arredondada (w × h, raio r, centro (xc, zc)) de y0 a y1, com as arestas das
    duas tampas arredondadas de raio r_e — o termorretrátil de um pack (r = o raio das células das pontas)."""
    seq = [(y0 + r_e * (1 - math.cos(0.5 * math.pi * k / n_e)), r_e * (1 - math.sin(0.5 * math.pi * k / n_e)))
           for k in range(n_e + 1)]
    seq += [(y1 - r_e * (1 - math.cos(0.5 * math.pi * k / n_e)), r_e * (1 - math.sin(0.5 * math.pi * k / n_e)))
            for k in range(n_e, -1, -1)]
    v, f = [], []
    nr = 0
    for y, dlt in seq:
        cont = retangulo_arred(w - 2 * dlt, h - 2 * dlt, max(r - dlt, 0.05), n)
        nr = len(cont)
        v.extend((xc + x, y, zc + z) for x, z in cont)
    for j in range(len(seq) - 1):
        for i in range(nr):
            i2 = (i + 1) % nr
            a, b, c, d = j * nr + i, j * nr + i2, (j + 1) * nr + i2, (j + 1) * nr + i
            f += [(a, b, c), (a, c, d)]
    for j in (0, len(seq) - 1):
        cen = len(v)
        v.append((xc, seq[j][0], zc))
        for i in range(nr):
            f.append((cen, j * nr + i, j * nr + (i + 1) % nr))
    return sem_degeneradas(*orientar_convexo((v, f), (xc, 0.5 * (y0 + y1), zc)))


def orientar_convexo(vf, centro=None):
    """Vira para fora as faces de um sólido CONVEXO (normal · (centro da face − centro) > 0)."""
    v, f = _arr(*vf)
    if len(f) == 0:
        return v, f
    c = v.mean(axis=0) if centro is None else np.asarray(centro, float)
    t = v[f]
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    errados = np.einsum("ij,ij->i", nrm, t.mean(axis=1) - c) < 0
    f = f.copy()
    f[errados] = f[errados][:, ::-1]
    return v, f


# =================================================================================================== fundidor
@dataclass
class _Parte:
    peca: str
    inst: int
    v: np.ndarray        # m, no referencial do corpo
    f: np.ndarray


class Fundidor:
    """Junta as peças por (corpo, material, chave) numa malha — dezenas de geoms para milhares de peças — e regista a
    faixa de faces de cada peça (o MuJoCo 3.15 preserva o número e a ordem das faces ao compilar). `chave` separa as
    variantes da troca ao vivo (um geom por variante × material, para se poderem ligar/desligar)."""

    def __init__(self, ctx, prefixo: str = "el"):
        self.ctx = ctx
        self.prefixo = prefixo
        self.grupos: dict[tuple[str, str, str], list[_Parte]] = {}
        self.geoms: dict[str, list[str]] = {}
        self._fechado = False

    def junta(self, corpo: str, material: str, vf_m, peca: str, inst: int = 0, chave: str = "") -> None:
        v, f = sem_degeneradas(*vf_m)
        if len(f) == 0:
            return
        self.grupos.setdefault((str(corpo), str(material), str(chave)), []).append(
            _Parte(str(peca), int(inst), np.asarray(v, float), np.asarray(f, np.int64)))

    def nome(self, corpo: str, material: str, chave: str) -> str:
        mat = material.removeprefix("el_")
        if chave:
            return f"{self.prefixo}_v_{chave}_{mat}" + ("" if corpo == "drone" else f"_{corpo}")
        return f"{self.prefixo}_m_{mat}_{corpo}"

    def fechar(self) -> dict[str, list[str]]:
        """Cria as malhas e os geoms; devolve {chave: [nomes dos geoms]}."""
        if self._fechado:
            return self.geoms
        self._fechado = True
        for (corpo, mat, chave), lista in self.grupos.items():
            lista.sort(key=lambda q: (q.peca, q.inst))
            vs, fs, faixas = [], [], []
            nv = nf = 0
            for q in lista:
                vs.append(q.v)
                fs.append(q.f + nv)
                faixas.append((q.peca, q.inst, nf, nf + len(q.f)))
                nv += len(q.v)
                nf += len(q.f)
            juntas = []
            for fx in faixas:
                if juntas and juntas[-1][0] == fx[0] and juntas[-1][1] == fx[1] and juntas[-1][3] == fx[2]:
                    juntas[-1] = (fx[0], fx[1], juntas[-1][2], fx[3])
                else:
                    juntas.append(fx)
            nome = self.nome(corpo, mat, chave)
            me = self.ctx.spec.add_mesh(name=f"m_{nome}")
            me.uservert = np.concatenate(vs).ravel().tolist()
            me.userface = np.concatenate(fs).ravel().tolist()
            me.inertia = mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL
            self.ctx.geom(corpo, nome, type=_G.mjGEOM_MESH, meshname=f"m_{nome}", material=mat,
                          peca=juntas[0][0], inst=juntas[0][1])
            self.ctx.registar_faixas(nome, juntas)
            self.geoms.setdefault(chave, []).append(nome)
        return self.geoms


class Quadro:
    """Um referencial LOCAL (mm) num corpo: `origem` (m, no corpo) e rotação `R` (local → corpo). Junta malhas locais
    no `Fundidor` (`m`) e cria primitivas com NOME (as âncoras dos outros módulos: `caixa`, `cil`)."""

    def __init__(self, ctx, fund: Fundidor, corpo: str, origem, R=None, chave: str = ""):
        self.ctx, self.fund, self.corpo = ctx, fund, corpo
        self.o = np.asarray(origem, float)
        self.R = np.eye(3) if R is None else np.asarray(R, float)
        self.chave = chave

    def ponto(self, x, y, z) -> np.ndarray:
        """Ponto local (mm) → corpo (m)."""
        return self.o + self.R @ (np.array([x, y, z], float) * MM)

    def dir(self, d) -> np.ndarray:
        return self.R @ np.asarray(d, float)

    def m(self, material: str, vf, peca: str, inst: int = 0, R=None, p=None, chave: str | None = None) -> None:
        """Junta a malha local `vf` (mm; opcionalmente rodada/deslocada no referencial local) ao fundidor."""
        v, f = mover(vf, R, p)
        if len(f) == 0:
            return
        vm = self.o + (v * MM) @ self.R.T
        if np.linalg.det(self.R) < 0:
            f = f[:, ::-1]
        self.fund.junta(self.corpo, material, (vm, f), peca, inst, self.chave if chave is None else chave)

    def q(self, Rl=None) -> list:
        R = self.R if Rl is None else self.R @ np.asarray(Rl, float)
        q = np.zeros(4)
        mujoco.mju_mat2Quat(q, np.asarray(R, float).reshape(9))
        return [float(x) for x in q]

    def malha(self, nome: str, material: str, vf, peca: str, inst: int = 0):
        """Uma malha com NOME próprio (fora do fundidor): âncoras que outros módulos procuram pelo nome."""
        v, f = sem_degeneradas(*vf)
        if len(f) == 0:
            return None
        vm = self.o + (v * MM) @ self.R.T
        if np.linalg.det(self.R) < 0:
            f = f[:, ::-1]
        me = self.ctx.spec.add_mesh(name=f"m_{nome}")
        me.uservert = vm.ravel().tolist()
        me.userface = np.asarray(f, np.int64).ravel().tolist()
        me.inertia = mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL
        return self.ctx.geom(self.corpo, nome, type=_G.mjGEOM_MESH, meshname=f"m_{nome}", material=material,
                             peca=peca, inst=inst)

    def caixa(self, nome: str, x0, x1, y0, y1, z0, z1, mat: str, peca: str | None = None, inst: int | None = None,
              rgba=None):
        """Caixa primitiva com NOME pelos limites (mm, local)."""
        meia = [0.5 * abs(x1 - x0) * MM, 0.5 * abs(y1 - y0) * MM, 0.5 * abs(z1 - z0) * MM]
        if min(meia) <= 0.0:
            return None
        kw = {} if rgba is None else {"rgba": list(rgba)}
        return self.ctx.geom(self.corpo, nome, type=_G.mjGEOM_BOX, size=meia,
                             pos=self.ponto(0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)).tolist(), quat=self.q(),
                             material=mat, peca=peca, inst=inst, **kw)

    def cil(self, nome: str, a, b, raio: float, mat: str, peca: str | None = None, inst: int | None = None):
        """Cilindro primitivo com NOME de `a` a `b` (mm, local) — `fromto`: as pontas leem-se no geom."""
        pa, pb = self.ponto(*a), self.ponto(*b)
        return self.ctx.geom(self.corpo, nome, type=_G.mjGEOM_CYLINDER, size=[raio * MM, 0.0, 0.0],
                             fromto=pa.tolist() + pb.tolist(), material=mat, peca=peca, inst=inst)



# =================================================================================================== materiais
# nome: (rgba, specular, shininess, reflectance) — prefixo `el_` (partilhados com a eletrónica); cores RGB das mangas
# ESTIMADAS a partir do nome da cor (a pesquisa só tem «Gray»/«Cyan»), os packs comerciais sem cor publicada também
MATERIAIS_BAT = {
    "el_bat_pvc": ((0.80, 0.90, 0.97, 0.20), 0.95, 0.95, 0.0),      # termorretrátil de PVC transparente (azulado leve)
    "el_cel_p50b": ((0.62, 0.64, 0.66, 1.0), 0.45, 0.55, 0.0),      # manga cinzenta (distribuidor oficial)
    "el_cel_faixa": ((0.26, 0.27, 0.29, 1.0), 0.45, 0.55, 0.0),     # faixas cinzento-escuras junto ao + (fórum)
    "el_cel_p45b": ((0.58, 0.60, 0.63, 1.0), 0.45, 0.55, 0.0),
    "el_cel_m50lt": ((0.42, 0.43, 0.45, 1.0), 0.45, 0.55, 0.0),     # conflito cinzento/transparente → o do M50T
    "el_cel_50e": ((0.22, 0.68, 0.80, 1.0), 0.45, 0.55, 0.0),       # ciano (HKJ)
    "el_cel_aco": ((0.74, 0.75, 0.77, 1.0), 0.90, 0.80, 0.08),      # lata, tampa e ombro de aço niquelado
    "el_bat_niquel": ((0.64, 0.63, 0.60, 1.0), 0.55, 0.50, 0.03),   # fita de níquel puro 0,15 mm
    "el_bat_cobre": ((0.80, 0.46, 0.23, 1.0), 0.80, 0.70, 0.05),    # fita de cobre 0,10 mm (sanduíche)
    "el_bat_kapton": ((0.86, 0.52, 0.10, 0.42), 0.85, 0.85, 0.0),   # fita de poliimida (âmbar translúcida)
    "el_bat_vermelho": ((0.78, 0.07, 0.05, 1.0), 0.55, 0.60, 0.0),  # silicone vermelho (10 / 22 AWG)
    "el_bat_preto": ((0.045, 0.045, 0.05, 1.0), 0.30, 0.35, 0.0),   # silicone preto, feltro, cintas, tapete EVA, fivela
    "el_bat_branco": ((0.90, 0.89, 0.85, 1.0), 0.20, 0.25, 0.0),    # JST-XH (PA6 natural) e rótulos
    "el_bat_bolsa": ((0.80, 0.81, 0.82, 1.0), 0.75, 0.65, 0.06),    # laminado de alumínio das células pouch
    "el_bat_espuma": ((0.30, 0.31, 0.33, 1.0), 0.05, 0.05, 0.0),    # espuma de PE / almofadas de silicone
    "el_bat_inv_gensace": ((0.06, 0.06, 0.065, 1.0), 0.60, 0.70, 0.03),   # PVC impresso (estimado: preto)
    "el_bat_inv_tattu": ((0.16, 0.17, 0.19, 1.0), 0.60, 0.70, 0.03),      # semi-sólido (estimado: cinzento-escuro)
    "el_bat_inv_gtech": ((0.05, 0.05, 0.055, 1.0), 0.60, 0.70, 0.03),     # G-Tech: PVC preto (revendedor)
    "el_bat_inv_lipo": ((0.07, 0.07, 0.08, 1.0), 0.60, 0.70, 0.03),       # LiPo genérica (estimado: preto)
    "el_bat_amarelo": ((0.95, 0.72, 0.08, 1.0), 0.35, 0.45, 0.0),   # faixa do logótipo Gens Ace (estimado)
    "el_bat_parafuso": ((0.10, 0.10, 0.11, 1.0), 0.75, 0.80, 0.04),  # parafusos 12.9 óxido negro (os do pack)
    "el_bat_zinco": ((0.78, 0.80, 0.84, 1.0), 0.90, 0.85, 0.12),     # porcas/anilhas zincadas
    "el_bat_nylon_azul": ((0.16, 0.36, 0.78, 1.0), 0.30, 0.35, 0.0), # anel de nylon das autoblocantes
    "el_bat_azul": ((0.08, 0.30, 0.78, 1.0), 0.35, 0.45, 0.0),      # faixa Tattu (estimado)
}


def materiais(ctx) -> None:
    for nome, (rgba, sp, br, rf) in MATERIAIS_BAT.items():
        ctx.material(nome, rgba, specular=sp, shininess=br, reflectance=rf)


# =================================================================================================== versão ACESSÍVEL
# (2.ª fase, 2026-10-20) frame `*_abs`: TODOS os suportes impressos em ABS — o material tem «abs» no nome (é assim que
# `massas.py` e a página os reconhecem), cada peça é uma malha FECHADA (sólidos fechados que só se tocam pelas faces:
# o volume soma-se exato) e fica registada em `notas["impressas"]` com a orientação de impressão.
MATERIAL_ABS = "el_abs_cinza"
COR_ABS = ((0.23, 0.24, 0.25, 1.0), 0.25, 0.30, 0.0)      # ABS cinzento-escuro fosco (a cor por omissão do contrato)
Q_IDENTIDADE = (1.0, 0.0, 0.0, 0.0)                      # a face de baixo já está na mesa
Q_VIRADA = (0.0, 1.0, 0.0, 0.0)                          # 180° em x: a face de cima vai para a mesa
Q_DE_LADO = (math.sqrt(0.5), 0.0, -math.sqrt(0.5), 0.0)  # −90° em y: a face −x vai para a mesa


def frame_abs(hw) -> bool:
    """O frame é a versão ACESSÍVEL impressa em ABS (`*_abs`, ou `material_impresso: ABS` no catálogo)."""
    f = getattr(hw, "frame", None)
    if f is None:
        return False
    return str(getattr(f, "id", "")).endswith("_abs") or \
        str((getattr(f, "dados", None) or {}).get("material_impresso", "")).upper() == "ABS"


def material_abs(ctx) -> str:
    rgba, sp, br, rf = COR_ABS
    ctx.material(MATERIAL_ABS, rgba, specular=sp, shininess=br, reflectance=rf)
    return MATERIAL_ABS


def regista_impressa(ctx, peca: str, inst: int, nome: str, orientacao, nota: str) -> None:
    """`notas["impressas"]["peca#inst"]` — a página mostra o modelo para imprimir, a massa e o custo."""
    ctx.registo.notas.setdefault("impressas", {})[f"{peca}#{int(inst)}"] = {
        "nome": nome, "orientacao": [float(x) for x in orientacao], "nota": nota}


# =================================================================================================== células
# desenho das células 21700 (medidas: `componentes.json` → `celulas.<id>.dims_mm` NOMINAL e `dims_max_mm`)
ESTILO_21700 = {
    "molicel_p50b": {"manga": "el_cel_p50b", "faixas": ((1.6, 3.6), (5.2, 6.7)), "tampa_d": 9.0},
    "molicel_p45b": {"manga": "el_cel_p45b", "faixas": (), "tampa_d": 9.0},
    "lg_m50lt": {"manga": "el_cel_m50lt", "faixas": (), "tampa_d": 9.0},
    "samsung_50e": {"manga": "el_cel_50e", "faixas": (), "tampa_d": 9.0},    # Ø do + ≈ 9 mm (30T/40T: fórum)
}


@functools.lru_cache(maxsize=1)
def _celulas_catalogo() -> dict:
    from .. import componentes as comp
    return comp.carregar_catalogo()["celulas"]


def dims_celula(cel_id: str) -> tuple[tuple, tuple]:
    """(nominal, máxima) da ficha: (Ø, comprimento) nas cilíndricas, (c, l, e) nas pouch."""
    d = _celulas_catalogo().get(cel_id, {})
    nom = tuple(float(x) for x in d.get("dims_mm", ()))
    mx = tuple(float(x) for x in d.get("dims_max_mm", nom))
    return nom, mx


@functools.lru_cache(maxsize=16)
def _celula_canonica(d: float, L: float, manga: str, faixas: tuple, tampa_d: float, n: int = 24) -> dict:
    """Uma célula 21700 de eixo z (o + em z = +L/2), por material, em mm: manga (com as dobras sobre o ombro e o
    fundo), faixas, código 2D impresso, fundo e tampa de aço, junta preta, anel de papel de peixe Ø19,8/10,5 × 0,2."""
    r = 0.5 * d
    h = 0.5 * L
    out: dict[str, list] = {}

    def j(mat, vf):
        out.setdefault(mat, []).append(vf)
    j(manga, _torno([[(r - 0.9, -h), (r - 0.3, -h), (r, -h + 0.3), (r, h - 0.7), (r - 0.3, h - 0.4),
                      (r - 1.25, h - 0.4)]], n=n))
    for a, b in faixas:                                     # faixas escuras (medidas a partir do topo +)
        j("el_cel_faixa", _torno([[(r + 0.04, h - b), (r + 0.04, h - a)]], n=n))
    # impressão: código 2D (5 × 5) e a linha do modelo, na face −x (a que fica virada para baixo no pack)
    j("el_bat_preto", g_caixa(-r - 0.03, -r + 0.35, -2.5, 2.5, -h + 6.0, -h + 11.0))
    j("el_bat_preto", g_caixa(-r - 0.03, -r + 0.12, -0.7, 0.7, -h + 13.0, -h + 38.0))
    # fundo (−): lata de aço; topo (+): ombro cravado, junta, tampa
    j("el_cel_aco", _torno([[(0.0, -h + 0.05), (r - 0.9, -h + 0.05)]], n=n))
    j("el_cel_aco", _torno([[(r - 1.25, h - 0.45), (5.6, h - 0.45)], [(5.6, h - 0.45), (5.6, h - 0.55)]], n=n))
    j("el_bat_preto", _torno([[(5.6, h - 0.55), (0.5 * tampa_d + 0.25, h - 0.55)]], n=n))
    j("el_cel_aco", _torno([[(0.5 * tampa_d, h - 0.6), (0.5 * tampa_d, h)], [(0.5 * tampa_d, h), (0.0, h)]], n=n))
    j("el_papel_peixe", g_anel(5.25, 9.9 if r > 10.3 else r - 0.5, h - 0.35, h - 0.15, 16))
    return {k: juntar(*v) for k, v in out.items()}


def _rot_celula(mais_em_y_pos: bool) -> np.ndarray:
    """Eixo canónico z → ±y do pack; o −x canónico (a impressão) → −z do pack (fica virada para baixo)."""
    if mais_em_y_pos:
        return np.column_stack([(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)])
    return np.column_stack([(0.0, 0.0, 1.0), (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)])


@dataclass
class PackGeo:
    """Geometria de um pack no SEU referencial (mm): x ao longo do pack, y transversal (faces A +y / B −y), z para cima
    com o topo do pack em z = 0 (o pack fica em z < 0)."""

    tipo: str
    pecas: list = field(default_factory=list)      # [(material, peça, (v, f))]
    x0: float = 0.0
    x1: float = 0.0
    y0: float = 0.0
    y1: float = 0.0
    z0: float = 0.0                                  # fundo (o mais baixo; o topo é 0)
    cabo_face_b: tuple | None = None                 # (x_a, x_b, z, raio): o P+ por fora da face B (bossa da cinta)
    term_pos: tuple = ()                             # (ponto, direção) onde o cabo P+ sai do terminal
    term_neg: tuple = ()
    caminho_pos: list = field(default_factory=list)  # pontos do P+ (do terminal até sair do pack)
    caminho_neg: list = field(default_factory=list)
    balanco: list = field(default_factory=list)      # [[pontos]] fio a fio (pino 1 = P−), até saírem do pack
    cabecas_topo: list = field(default_factory=list)  # [(x, y, r)] cabeças de parafuso no topo (furos no tapete)
    ferragens: list = field(default_factory=list)    # [dict] parafusos/porcas próprios (registados sem desenhar)
    term_caixas: dict = field(default_factory=dict)  # «pos»/«neg» → (x0, x1, y0, y1, z0, z1) da solda do terminal
    obst_baixo: list = field(default_factory=list)   # [(x, y, r, z)] saliências abaixo do fundo (pontas de parafuso)
    z_base: float | None = None                      # fundo plano (sem as saliências); None = z0
    rotulo_x: tuple = ()
    tomadas_pts: list = field(default_factory=list)  # ponto da tomada de cada fio do balanceador (na fita / ilha)
    s: int = 6
    xt90s: bool = False                              # o pack traz de fábrica um XT90S-F (anti-faísca)
    descricao: str = ""

    def junta(self, material: str, peca: str, vf) -> None:
        v, f = sem_degeneradas(*vf)
        if len(f):
            self.pecas.append((material, peca, (v, f)))

    @property
    def dims(self) -> tuple:
        """(comprimento, largura, altura) do corpo do pack (mm), como no `CATALOGO_BATERIAS_PAINEL`."""
        return (round(self.x1 - self.x0, 1), round(self.y1 - self.y0, 1), round(-self.z0, 1))


# --------------------------------------------------------------------------------------------------- 21700
E_CU, E_NI, E_KAP, E_FELTRO, E_PVC = 0.10, 0.15, 0.06, 1.0, 0.25
R_BAL, R_10AWG = 0.8, 2.75
FOLGA_CEL = 0.2                                  # entre células (sem suporte: encostadas como nos packs comerciais)


@functools.lru_cache(maxsize=32)
def pack_21700(cel_id: str, S: int, P: int) -> PackGeo:
    """S grupos lado a lado (x) × P células empilhadas (z), eixos em y; o grupo k tem o + na face A (+y) se k é ímpar."""
    (d, L), _mx = dims_celula(cel_id)
    est = ESTILO_21700.get(cel_id, ESTILO_21700["molicel_p50b"])
    can = _celula_canonica(round(d, 4), round(L, 4), est["manga"], tuple(est["faixas"]), est["tampa_d"])
    pg = PackGeo("21700", s=S)
    passo = d + FOLGA_CEL
    X = S * passo - FOLGA_CEL
    H = P * passo - FOLGA_CEL
    xs = [-0.5 * X + 0.5 * d + i * passo for i in range(S)]
    zs = [-E_PVC - 0.5 * d - j * passo for j in range(P)]
    h = 0.5 * L
    Rp, Rn = _rot_celula(True), _rot_celula(False)
    for i, x in enumerate(xs):
        mais_a = (i % 2 == 0)                         # grupo 1 (i = 0) com o + na face A
        for z in zs:
            for mat, vf in can.items():
                pg.junta(mat, "bateria", mover(vf, Rp if mais_a else Rn, (x, 0.0, z)))
    # ---- fitas (Cu 10 mm por baixo, Ni 8 mm por cima) e pontos de soldadura, nas duas faces
    z_t, z_b = zs[0], zs[-1]
    ligacoes = {"A": [(k, k + 1) for k in range(0, S - 1, 2)], "B": [(k, k + 1) for k in range(1, S - 1, 2)]}
    terminais_b = [0] + ([S - 1] if S % 2 == 0 else [])
    terminais_a = [] if S % 2 == 0 else [S - 1]

    def face_y(face, camada):                       # y da camada: 0 = cobre (de dentro para fora)
        e = (0.0, E_CU, E_CU + E_NI, E_CU + E_NI + E_KAP)[camada]
        return (h + e) if face == "A" else -(h + e)

    def tira(face, x_a, x_b, z_a, z_b2, camada, mat):
        ya, yb = sorted((face_y(face, camada), face_y(face, camada + 1)))
        pg.junta(mat, "bateria", g_caixa(x_a, x_b, ya, yb, z_a, z_b2))

    def conjunto(face, cols, terminal=False):
        for camada, mat, larg in ((0, "el_bat_cobre", 10.0), (1, "el_bat_niquel", 8.0)):
            for c in cols:                                   # tira vertical (paralelo) em cada coluna
                tira(face, xs[c] - 0.5 * larg, xs[c] + 0.5 * larg, z_b - 0.5 * larg - 0.5, z_t + 0.5 * larg + 0.5,
                     camada, mat)
            if len(cols) == 2:                               # pontes (série), uma por camada de células
                for z in zs:
                    tira(face, xs[cols[0]], xs[cols[1]], z - 0.5 * larg, z + 0.5 * larg, camada, mat)
        # 4 pontos de soldadura por extremo de célula
        y_s = face_y(face, 2) + (0.03 if face == "A" else -0.03)
        for c in cols:
            for z in zs:
                for dx in (-2.0, 2.0):
                    for dz in (-2.6, 2.6):
                        pv, pf = _torno([[(0.45, 0.0), (0.0, 0.0)]], n=6)     # disco (só a face de fora)
                        pg.junta("el_bat_preto", "bateria",
                                 mover((pv, pf), eixo_para((0, 1, 0) if face == "A" else (0, -1, 0)),
                                       (xs[c] + dx, y_s, z + dz)))
        if not terminal and len(cols) == 2:                   # Kapton sobre a ligação
            ya, yb = sorted((face_y(face, 2), face_y(face, 3)))
            pg.junta("el_bat_kapton", "bateria", g_caixa(xs[cols[0]] - 6.0, xs[cols[1]] + 6.0, ya, yb,
                                                         z_b - 6.0, z_t + 6.0))
    for face, lig in ligacoes.items():
        for a, b in lig:
            conjunto(face, (a, b))
    for c in terminais_b:
        conjunto("B", (c,), terminal=True)
    for c in terminais_a:
        conjunto("A", (c,), terminal=True)
    # ---- feltro nas arestas de baixo das faces (protege o termorretrátil dos cantos das fitas)
    y_ext = h + E_CU + E_NI + E_KAP + 2 * R_BAL               # o balanceador corre por baixo do PVC, sobre o Kapton
    for face, sgn in (("A", 1.0), ("B", -1.0)):
        ya, yb = sorted((sgn * (h + E_CU + E_NI + E_KAP), sgn * (h + E_CU + E_NI + E_KAP + E_FELTRO)))
        pg.junta("el_bat_preto", "bateria", g_caixa(-0.5 * X + 1.0, 0.5 * X - 1.0, ya, yb, -H - E_PVC + 0.4,
                                                     -H - E_PVC + 5.5))
    # ---- termorretrátil transparente (secção x-z: retângulo de cantos com o raio das células)
    W_pvc = X + 2 * E_PVC + 2 * R_BAL + 0.2                 # + a passagem dos fios do balanceador pela traseira
    H_pvc = H + 2 * E_PVC
    y_pvc = y_ext + E_PVC
    x_c_pvc = -(R_BAL + 0.1)
    pg.junta("el_bat_pvc", "bateria", g_extrusao_y(W_pvc, H_pvc, 0.5 * d + E_PVC, -y_pvc, y_pvc, 2.0, xc=x_c_pvc,
                                                    zc=-0.5 * H_pvc, n=6, n_e=2))
    # rótulo (branco) na face A, com as linhas de texto (pretas): «6S2P 21,6 V 10 Ah · Molicel P50B»
    rx, rz = min(0.20 * X, 24.0), min(0.20 * H_pvc, 7.5)
    zc = -0.5 * H_pvc
    pg.junta("el_bat_branco", "bateria", g_caixa(-rx, rx, y_pvc, y_pvc + 0.12, zc - rz, zc + rz))
    pg.rotulo_x = (-rx, rx)
    for k, (fr, dz) in enumerate(((0.85, 0.45), (0.60, 0.0), (0.72, -0.45))):
        pg.junta("el_bat_preto", "bateria", g_caixa(-fr * rx, fr * rx - 0.3 * rx * (k == 1), y_pvc + 0.12, y_pvc + 0.17,
                                                     zc + dz * rz - 1.1, zc + dz * rz + 1.1))
    # ---- TERMINAIS (P− no grupo 1, P+ no grupo S) e os cabos 10 AWG: soldados no cobre a meia altura e para fora
    z_mid = -0.5 * H_pvc
    z_neg = z_mid + (0.22 * H if P > 1 else 0.0)
    z_pos = z_mid - (0.22 * H if P > 1 else 0.0)
    y_b = -(h + E_CU)
    face_term_pos = "B" if S % 2 == 0 else "A"
    sgn_pos = -1.0 if face_term_pos == "B" else 1.0
    pg.term_neg = ((xs[0], y_b, z_neg), (0.0, -1.0, 0.0))
    pg.term_pos = ((xs[-1], sgn_pos * (h + E_CU), z_pos), (0.0, sgn_pos, 0.0))
    y_cabo_b = -(y_pvc + R_10AWG + 0.05)
    x_tras = x_c_pvc - 0.5 * W_pvc
    # P−: sai logo do PVC e vai para trás
    pg.caminho_neg = [(xs[0], y_b - 1.5, z_neg), (xs[0], y_cabo_b, z_neg), (xs[0] - 6.0, y_cabo_b - 1.0, z_neg),
                      (x_tras - 4.0, y_cabo_b - 2.0, z_neg)]
    if face_term_pos == "B":
        # P+: sai do PVC na coluna S e corre por FORA da face B, a meia altura (z_pos), até à traseira
        pg.caminho_pos = [(xs[-1], -(h + E_CU) - 1.5, z_pos), (xs[-1], y_cabo_b, z_pos), (xs[-1] - 6.0, y_cabo_b, z_pos),
                          (x_tras + 2.0, y_cabo_b, z_pos), (x_tras - 4.0, y_cabo_b - 0.5, z_pos)]
        pg.cabo_face_b = (x_tras - 4.0, xs[-1] + 3.0, z_pos, R_10AWG)
    else:
        y_a = y_pvc + R_10AWG + 0.05
        pg.caminho_pos = [(xs[-1], h + E_CU + 1.5, z_pos), (xs[-1], y_a, z_pos), (xs[-1] - 6.0, y_a, z_pos),
                          (x_tras - 4.0, y_a, z_pos)]
    for nome, (pt, _dr) in (("neg", pg.term_neg), ("pos", pg.term_pos)):
        x, y, z = pt
        sy = -1.0 if y < 0 else 1.0
        # a ponta descarnada achatada sobre o cobre + a solda (âncora `el_bat_terminal_<polo>` no pack ativo)
        ya, yb = sorted((y + sy * E_CU, y + sy * (E_CU + 1.4)))
        pg.term_caixas[nome] = (x - 4.0, x + 4.0, ya, yb, z - 3.5, z + 3.5)
    # ---- BALANCEADOR: S+1 fios 22 AWG; pino 1 = P− (coluna 1, face B), pino k+1 = junção Gk+/Gk+1−, pino S+1 = P+
    tomadas = [("B", 0, None)]
    for k in range(1, S):
        face = "A" if (k % 2 == 1) else "B"                 # junção k (Gk/Gk+1): ímpar na face A, par na B
        tomadas.append((face, k - 1, k))
    tomadas.append((face_term_pos, S - 1, None))
    y_fio = {"A": h + E_CU + E_NI + E_KAP + R_BAL, "B": -(h + E_CU + E_NI + E_KAP + R_BAL)}
    x_tom = [xs[c0] if c1 is None else 0.5 * (xs[c0] + xs[c1]) for _f, c0, c1 in tomadas]
    # em cada face, o fio que nasce mais longe da traseira corre mais acima (passa por cima das tomadas mais perto)
    ordem = {}
    n_a = sum(1 for t in tomadas if t[0] == "A")
    for face in ("A", "B"):
        idx = sorted((i for i, t in enumerate(tomadas) if t[0] == face), key=lambda i: -x_tom[i])
        for k, i in enumerate(idx):
            ordem[i] = k
    for pino, (face, c0, c1) in enumerate(tomadas, 1):
        x_t = x_tom[pino - 1]
        z_tom = z_t + 2.0
        k = ordem[pino - 1] + (0 if face == "A" else n_a)
        z_corre = -2.2 - 1.75 * k                            # cada fio na sua cota, por baixo do PVC, ao longo da face
        y = y_fio[face]
        x_sai = x_tras + 4.0
        # a traseira das células à cota do fio (o fio corre por cima delas, por baixo do PVC alargado atrás)
        dz_c = min(abs(z_corre - z_t), 0.5 * d - 0.05)
        x_cel = xs[0] - math.sqrt(max((0.5 * d) ** 2 - dz_c ** 2, 0.0))
        x_volta = min(x_cel - R_BAL - 0.05, x_tras + 3.0)
        pts = [(x_t, y, z_tom), (x_t, y, z_corre), (x_t - 3.0, y, z_corre)]
        if face == "B":                                      # pela traseira até à face A
            pts += [(xs[0], y, z_corre), (x_volta, y, z_corre), (x_volta, y_fio["A"], z_corre)]
        pts += [(x_sai, y_fio["A"], z_corre), (x_sai - 2.0, y_fio["A"] + 3.0, z_corre),
                (x_tras - 3.0, y_fio["A"] + 3.4, z_corre)]
        pg.balanco.append(pts)
        pg.tomadas_pts.append((x_t, (h + E_CU + E_NI) * (1.0 if face == "A" else -1.0), z_tom))
        pg.junta("el_estanho", "bateria", g_caixa_arred(x_t - 1.4, x_t + 1.4,
                                                       *sorted((y - sy * R_BAL, y + sy * 0.2)), z_tom - 1.4,
                                                       z_tom + 1.4, 0.4, 1))
    pg.x0, pg.x1 = x_tras, x_c_pvc + 0.5 * W_pvc
    pg.y0 = -(y_pvc + (2 * R_10AWG + 0.1 if face_term_pos == "B" else 0.0))
    pg.y1 = y_pvc + 0.17
    pg.z0 = -H_pvc
    tipo = {"molicel_p50b": "Molicel P50B", "molicel_p45b": "Molicel P45B", "lg_m50lt": "LG M50LT",
            "samsung_50e": "Samsung 50E"}.get(cel_id, cel_id)
    pg.descricao = f"{S}S{P}P {tipo} 21700 (DIY: Ni/Cu, PVC transparente)"
    return pg


# --------------------------------------------------------------------------------------------------- pouch comerciais
# (célula, S, P) → medidas do PACK do fabricante (mm), invólucro (estimado quando a cor não é publicada), XT90S-F
POUCH_PACKS = {
    ("gensace_5ah_45c", 6, 1): {"L": 157.0, "W": 46.0, "T": 44.0, "inv": "el_bat_inv_gensace", "faixa": "el_bat_amarelo",
                                "nome": "Gens Ace 5000 mAh 6S 45C"},
    ("gensace_5ah_45c", 4, 1): {"L": 158.0, "W": 46.0, "T": 31.0, "inv": "el_bat_inv_gensace", "faixa": "el_bat_amarelo",
                                "nome": "Gens Ace 5000 mAh 4S 45C"},
    ("tattu_semisolido_12ah", 6, 1): {"L": 194.0, "W": 71.0, "T": 32.0, "inv": "el_bat_inv_tattu", "faixa": "el_bat_azul",
                                      "nome": "Tattu semi-sólido 12000 mAh 6S1P", "xt90s": True},
    ("tattu_gtech_10ah", 4, 1): {"L": 169.0, "W": 65.0, "T": 39.0, "inv": "el_bat_inv_gtech", "faixa": "el_bat_branco",
                                 "nome": "Tattu G-Tech 10000 mAh 4S 25C"},
    ("lipo_1500_4s_cell", 4, 1): {"L": 75.0, "W": 34.0, "T": 34.0, "inv": "el_bat_inv_lipo", "faixa": "el_bat_branco",
                                  "nome": "LiPo 1500 mAh 4S 75C"},
    ("lipo_1500_4s_cell", 3, 1): {"L": 75.0, "W": 35.0, "T": 26.5, "inv": "el_bat_inv_lipo", "faixa": "el_bat_branco",
                                  "nome": "LiPo 1500 mAh 3S"},
}
E_INV, E_ESPUMA = 0.30, 1.0


@functools.lru_cache(maxsize=16)
def pack_pouch(cel_id: str, S: int, P: int) -> PackGeo:
    """Pack LiPo/semi-sólido COMERCIAL: S·P bolsas empilhadas (z) com a espessura real, abas soldadas na placa da ponta
    (−x), espuma em cima e em baixo, invólucro de PVC impresso OPACO com a faixa do logótipo e o rótulo; os cabos e o
    balanceador saem da ponta −x."""
    nom, _mx = dims_celula(cel_id)
    esp = POUCH_PACKS.get((cel_id, S, P))
    if esp is None:                                        # outra combinação: pela célula
        c_l, c_w, c_t = (nom + (140.0, 45.0, 7.0))[:3] if len(nom) == 3 else (140.0, 45.0, 7.0)
        esp = {"L": c_l + 10.0, "W": c_w + 1.5, "T": S * P * c_t + 2.6, "inv": "el_bat_inv_lipo",
               "faixa": "el_bat_branco", "nome": f"LiPo {S}S{P}P"}
    L, W, T = esp["L"], esp["W"], esp["T"]
    pg = PackGeo("pouch", s=S, xt90s=bool(esp.get("xt90s")))
    n_cel = S * P
    t_c = (T - 2 * E_INV - 2 * E_ESPUMA) / n_cel
    zona = 9.0                                              # abas + placa da ponta (−x)
    lc, wc = L - 2 * E_INV - zona - 1.0, W - 2 * E_INV - 1.0
    xc = 0.5 * L - E_INV - 0.5 - 0.5 * lc                   # o corpo encostado à ponta +x
    z_top = -E_INV - E_ESPUMA
    pg.junta("el_bat_espuma", "bateria", g_caixa(-0.5 * L + E_INV + zona, 0.5 * L - E_INV, -0.5 * wc, 0.5 * wc,
                                                 z_top, -E_INV))
    pg.junta("el_bat_espuma", "bateria", g_caixa(-0.5 * L + E_INV + zona, 0.5 * L - E_INV, -0.5 * wc, 0.5 * wc,
                                                 -T + E_INV, -T + E_INV + E_ESPUMA))
    x_placa = -0.5 * L + E_INV + 1.0
    for k in range(n_cel):
        z1 = z_top - k * t_c
        z0 = z1 - t_c + 0.15
        pg.junta("el_bat_bolsa", "bateria", g_caixa_arred(xc - 0.5 * lc, xc + 0.5 * lc, -0.5 * wc, 0.5 * wc, z0, z1,
                                                         min(1.2, 0.45 * t_c), 2))
        zm = 0.5 * (z0 + z1)
        pg.junta("el_bat_bolsa", "bateria", g_caixa(xc - 0.5 * lc - 4.0, xc - 0.5 * lc + 0.2, -0.5 * wc + 1.0,
                                                    0.5 * wc - 1.0, zm - 0.2, zm + 0.2))        # selagem
        for sy, mat in ((1.0, "el_bat_niquel"), (-1.0, "el_cel_aco")):                        # abas (Al / Ni-Cu)
            yy = sy * 0.25 * wc
            pg.junta(mat, "bateria", g_caixa(x_placa + 1.6, xc - 0.5 * lc - 4.0, yy - 5.0, yy + 5.0, zm - 0.1, zm + 0.1))
    pg.junta("el_pcb_verde", "bateria", g_caixa(x_placa, x_placa + 1.6, -0.5 * wc, 0.5 * wc, -T + E_INV + 0.5,
                                                -E_INV - 0.5))
    # invólucro opaco (o real) + faixa do logótipo e linhas de texto nos lados, rótulo branco por baixo
    pg.junta(esp["inv"], "bateria", g_caixa_arred(-0.5 * L, 0.5 * L, -0.5 * W, 0.5 * W, -T, 0.0, 3.0, 3))
    for sy in (1.0, -1.0):
        ya, yb = sorted((sy * 0.5 * W, sy * (0.5 * W + 0.12)))
        pg.junta(esp["faixa"], "bateria", g_caixa(-0.40 * L, 0.40 * L, ya, yb, -0.62 * T, -0.38 * T))
        ya2, yb2 = sorted((sy * (0.5 * W + 0.12), sy * (0.5 * W + 0.17)))
        for k, fr in enumerate((0.30, 0.18)):
            pg.junta("el_bat_branco", "bateria", g_caixa(-fr * L, fr * L - 0.1 * L * k, ya2, yb2,
                                                         -0.72 * T - 1.1 * k - 1.0, -0.72 * T - 1.1 * k + 0.2))
    pg.junta("el_bat_branco", "bateria", g_caixa(-0.30 * L, 0.30 * L, -0.33 * W, 0.33 * W, -T - 0.12, -T))
    for k, fr in enumerate((0.85, 0.6, 0.72)):
        pg.junta("el_bat_preto", "bateria", g_caixa(-0.25 * L * fr, 0.25 * L * fr, -0.33 * W * fr + 0.5 * k,
                                                    -0.33 * W * fr + 0.5 * k + 2.0, -T - 0.17, -T - 0.12))
    # cabos 10 AWG pela ponta −x (P+ do lado +y, como o copo + do XT90), balanceador ao lado
    z_c = -min(0.5 * T, 10.0)
    for nome, yy in (("pos", 6.0), ("neg", -6.0)):
        pts = [(x_placa + 1.6, yy, z_c), (-0.5 * L + 2.0, yy, z_c), (-0.5 * L - 1.5, yy, z_c)]
        setattr(pg, f"caminho_{nome}", pts)
        setattr(pg, f"term_{nome}", ((x_placa + 1.6, yy, z_c), (-1.0, 0.0, 0.0)))
        pg.term_caixas[nome] = (x_placa + 1.6, x_placa + 3.0, yy - 4.0, yy + 4.0, z_c - 3.5, z_c + 3.5)
    # manga de saída dos cabos (termorretrátil preto sobre as pontas, rente ao invólucro)
    for yy in (6.0, -6.0):
        pv, pf = g_cil(R_10AWG + 0.6, 0.0, 6.0, 12)
        pg.junta("el_bat_preto", "bateria", mover((pv, pf), eixo_para((-1, 0, 0)), (-0.5 * L + 1.0, yy, z_c)))
    y_b0 = min(0.5 * W - 5.0, 18.0)
    z_b = -min(0.5 * T, 10.0) + 5.0
    y_ex = 0.5 * W + 3.0
    for k in range(S + 1):                                # fita plana (y) → pilha vertical (z) em (x_ex, y_ex)
        yy = y_b0 - (S - k) * 1.7
        zk = -2.0 - 1.75 * k
        pg.tomadas_pts.append((x_placa, yy, z_b))
        pg.balanco.append([(x_placa + 1.6, yy, z_b), (-0.5 * L - 3.0, yy, z_b), (-0.5 * L - 4.5, yy, zk),
                           (-0.5 * L - 6.0, y_ex, zk)])
    pg.x0, pg.x1, pg.y0, pg.y1, pg.z0 = -0.5 * L, 0.5 * L, -0.5 * W - 0.17, 0.5 * W + 0.17, -T - 0.17
    pg.descricao = esp["nome"]
    return pg


# --------------------------------------------------------------------------------------------------- Amprius DIY
PLACA_AMP, PAD_AMP = 2.5, 1.0


@functools.lru_cache(maxsize=4)
def pack_amprius(S: int, P: int) -> PackGeo:
    """Amprius SA102 S×P (DIY): P pilhas de S bolsas (56,5 × 49,5 × 5,5 mm, abas na face B) lado a lado em x, entre
    2 PLACAS DE COMPRESSÃO de alumínio de 2,5 mm (os 30 PSI que a célula exige) com almofadas de silicone de 1 mm e
    6 parafusos M3 × 45 (ISO 7380 em cima, porca autoblocante em baixo), barramento de abas em FR4 na face B, PVC
    transparente em cada pilha."""
    (L1, W1, T1), _mx = dims_celula("amprius_sa102") if len(dims_celula("amprius_sa102")[0]) == 3 else \
        ((56.5, 49.5, 5.5), None)
    L2 = 53.0
    pg = PackGeo("amprius", s=S)
    folga = 7.0                                            # entre pilhas (passam os parafusos do meio)
    xs = [(-0.5 * (P - 1) + j) * (W1 + folga) for j in range(P)]
    z_c1 = -PLACA_AMP - PAD_AMP
    for x in xs:
        for k in range(S):
            z1 = z_c1 - k * T1
            z0 = z1 - T1 + 0.1
            zm = 0.5 * (z0 + z1)
            pg.junta("el_bat_bolsa", "bateria", g_caixa_arred(x - 0.5 * W1, x + 0.5 * W1, -0.5 * L2, 0.5 * L2, z0, z1,
                                                             1.0, 2))
            pg.junta("el_bat_bolsa", "bateria", g_caixa(x - 0.5 * W1 + 1.0, x + 0.5 * W1 - 1.0, -0.5 * L2 - 2.5,
                                                        -0.5 * L2 + 0.2, zm - 0.2, zm + 0.2))         # selagem
            for sx, mat in ((1.0, "el_bat_niquel"), (-1.0, "el_cel_aco")):
                xx = x + sx * (0.25 * W1) * (1.0 if k % 2 == 0 else -1.0)          # camadas alternadas (série)
                pg.junta(mat, "bateria", g_caixa(xx - 6.0, xx + 6.0, -0.5 * L1 - 2.2, -0.5 * L2 - 2.5, zm - 0.1,
                                                 zm + 0.1))
        z_cel0 = z_c1 - S * T1
        for za, zb in ((z_c1, -PLACA_AMP), (-PLACA_AMP - PAD_AMP - S * T1 - PAD_AMP, z_cel0)):
            pg.junta("el_bat_espuma", "bateria", g_caixa(x - 0.5 * W1, x + 0.5 * W1, -0.5 * L2, 0.5 * L2, za, zb))
        pg.junta("el_bat_pvc", "bateria", g_caixa_arred(x - 0.5 * W1 - 0.3, x + 0.5 * W1 + 0.3, -0.5 * L2 - 0.3,
                                                        0.5 * L2 + 0.3, z_cel0 - 0.3, z_c1 + 0.3, 1.2, 2))
    H = 2 * PLACA_AMP + 2 * PAD_AMP + S * T1
    x_ext = xs[-1] + 0.5 * W1 + 7.0
    for z0, z1 in ((-PLACA_AMP, 0.0), (-H, -H + PLACA_AMP)):
        pg.junta("el_aluminio", "bateria", g_placa_furos(-x_ext, x_ext, -0.5 * L2 - 0.5, 0.5 * L2 + 0.5, z0, z1,
                                                         [(bx, by, 1.7) for bx in [-x_ext + 3.5, *[0.5 * (xs[j] + xs[j + 1]) for j in range(P - 1)], x_ext - 3.5] for by in (-22.0, 22.0)]))
    # barramento das abas (FR4 verde) na face B, com as ilhas de cobre e a solda
    y_bus0, y_bus1 = -0.5 * L1 - 2.2 - 1.6, -0.5 * L1 - 2.2
    pg.junta("el_pcb_verde", "bateria", g_caixa(xs[0] - 0.5 * W1, xs[-1] + 0.5 * W1, y_bus0, y_bus1, -H + PLACA_AMP + 1.0,
                                                -PLACA_AMP - 1.0))
    for x in xs:
        for k in range(S):
            zm = z_c1 - (k + 0.5) * T1
            for sx in (1.0, -1.0):
                xx = x + sx * (0.25 * W1)
                pg.junta("el_bat_cobre", "bateria", g_caixa(xx - 7.0, xx + 7.0, y_bus0 - 0.05, y_bus0, zm - 2.3, zm + 2.3))
                pg.junta("el_estanho", "bateria", g_caixa_arred(xx - 5.0, xx + 5.0, y_bus0 - 0.6, y_bus0 - 0.05,
                                                               zm - 1.2, zm + 1.2, 0.25, 1))
    # parafusos M3 × 45: cabeça ISO 7380 em cima (no furo do tapete), anilha + porca ISO 10511 em baixo
    parafusos = [(bx, by) for bx in [-x_ext + 3.5, *[0.5 * (xs[j] + xs[j + 1]) for j in range(P - 1)], x_ext - 3.5]
                 for by in (-22.0, 22.0)]
    cab = _cabeca_7380("M3")
    an = _anilha_7089("M3")
    (pm_v, pm_f), (pn_v, pn_f) = _porca_10511("M3")
    Rb = np.diag([1.0, -1.0, -1.0])                         # eixo do parafuso para baixo (−z)
    for bx, by in parafusos:
        pg.junta("el_bat_parafuso", "bateria", mover(cab, Rb, (bx, by, 0.0)))
        pg.junta("el_bat_parafuso", "bateria", mover(g_cil(1.3, H + 0.5 + 4.0 - 0.3, 45.0, 10), Rb, (bx, by, 0.0)))
        pg.junta("el_bat_zinco", "bateria", mover(an, Rb, (bx, by, -H)))
        pg.junta("el_bat_zinco", "bateria", mover((pm_v, pm_f), Rb, (bx, by, -H - 0.5)))
        pg.junta("el_bat_nylon_azul", "bateria", mover((pn_v, pn_f), Rb, (bx, by, -H - 0.5)))
        pg.cabecas_topo.append((bx, by, 0.5 * ISO7380["M3"][0] + 0.6))
        pg.ferragens.append({"tipo": "parafuso", "ponto": (bx, by, 0.0), "eixo": (0.0, 0.0, -1.0), "rosca": "M3",
                             "comp": 45.0, "aperto": H, "cabeca": "ISO 7380", "porca": "ISO 10511"})
    # terminais: P− (camada de cima) e P+ (camada de baixo) na ponta de trás do barramento; balanceador ao lado
    x_tras = xs[0] - 0.5 * W1
    z_neg, z_pos = z_c1 - 0.5 * T1, z_c1 - (S - 0.5) * T1
    y_t = y_bus0 - 0.6
    pg.term_neg = ((x_tras + 4.0, y_t, z_neg), (0.0, -1.0, 0.0))
    pg.term_pos = ((x_tras + 4.0, y_t, z_pos), (0.0, -1.0, 0.0))
    for nome, z in (("neg", z_neg), ("pos", z_pos)):
        setattr(pg, f"caminho_{nome}", [(x_tras + 4.0, y_t - 1.0, z), (x_tras + 4.0, y_t - R_10AWG - 0.5, z),
                                        (x_tras - 3.0, y_t - R_10AWG - 1.0, z), (x_tras - 9.0, y_t - R_10AWG - 1.0, z)])
        pg.term_caixas[nome] = (x_tras + 0.5, x_tras + 7.5, y_t - 1.0, y_t + 0.1, z - 2.6, z + 2.6)
    # balanceador: das ilhas de cada camada, ao longo do barramento entre os cabos (cotas −13…−24), à volta da
    # traseira da pilha (entre ela e os parafusos de trás) e para fora pelo canto +y
    y_f = y_bus0 - R_BAL - 0.4
    x_volta = xs[0] - 0.5 * W1 - 0.3 - R_BAL - 0.05
    for k in range(S + 1):
        z_tap = z_c1 - min(k, S) * T1 + (-0.8 if k == 0 else (0.8 if k == S else 0.0))
        xk = x_tras + 12.0 + 2.6 * k
        zc = -13.0 - 1.8 * k
        pg.tomadas_pts.append((xk, y_bus0, z_tap))
        pg.balanco.append([(xk, y_bus0 - 0.6, z_tap), (xk, y_f, z_tap), (xk, y_f, zc), (x_volta, y_f, zc),
                           (x_volta, 17.0, zc), (-x_ext - 3.0, 17.0, zc), (-x_ext - 4.5, 0.5 * L2 + 3.0, zc)])
        pg.junta("el_estanho", "bateria", g_caixa_arred(xk - 1.3, xk + 1.3, y_bus0 - 0.9, y_bus0 - 0.05, z_tap - 1.3,
                                                       z_tap + 1.3, 0.3, 1))
    pg.x0, pg.x1 = -x_ext, x_ext
    pg.y0, pg.y1 = y_bus0 - 1.2, 0.5 * L2 + 0.5
    pg.z0 = -H - 0.5 - 4.0 - 0.5
    pg.z_base = -H
    pg.obst_baixo = [(bx, by, 4.0, -H - 5.0) for bx, by in parafusos]
    pg.descricao = f"Amprius SiCore SA102 {S}S{P}P (DIY, placas de compressão 30 PSI)"
    return pg


def pack_geo(cel_id: str, S: int, P: int) -> PackGeo:
    """O pack desenhado para (célula, S, P)."""
    if cel_id in ESTILO_21700:
        return pack_21700(cel_id, S, P)
    if cel_id == "amprius_sa102":
        return pack_amprius(S, P)
    return pack_pouch(cel_id, S, P)


# =================================================================================================== montagem no drone
L_CINTA, E_CINTA = 15.0, 1.3                     # cinta de 15 mm de nylon (1,3 mm)
RASGO_X, RASGO_Y = 28.0, 15.0                    # rasgos da placa (centro do pack, mm): dentro da pegada do pack
RASGO_COMP, RASGO_LARG = 20.0, 4.0
E_TAPETE_MIN = 1.0
JST_XH_PASSO, JST_XH_FUNDO, JST_XH_ALTURA = 2.5, 5.7, 7.5
XT90_L, XT90_H, XT90_CHANFRO, XT90_PASSO, XT90_COPO_R = 21.0, 10.5, 2.5, 11.0, 2.75
XT90_SALIENCIA_MAX = 45.0    # mm para lá da borda da placa de baixo: mais do que isto, o XT90 fica DE PÉ


def _secao_xt90():
    """Secção em «D» do XT90 (y, z): 21 × 10,5 mm com os 2 cantos de cima chanfrados (a chave de polaridade)."""
    hw, hh, c = 0.5 * XT90_L, 0.5 * XT90_H, XT90_CHANFRO
    return [(-hw, -hh), (hw, -hh), (hw, hh - c), (hw - c, hh), (-(hw - c), hh), (-hw, hh - c)]


def _corpo_xt90(x0: float, x1: float, z_c: float):
    """Prisma do XT90 entre x0 < x1 (eixo ao longo de x), centrado em y = 0, z = z_c."""
    pr = g_prisma(_secao_xt90(), x0, x1)                  # extrusão em z: (y, z, x) → rodar
    R = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    return mover(pr, R, (0.0, 0.0, z_c))


def _jst_xh(n: int, x_tras: float, y_c: float, z_c: float):
    """Ficha JST-XH de n vias (caixa XHP-n: (n−1)·2,5 + 4,9 × 5,7 × 7,5) com a traseira em x_tras (os fios entram por
    +x), a frente em x_tras − 5,7 (encaixe): caixa, rampa da trava, entradas dos contactos. Devolve {material: vf}."""
    b = (n - 1) * JST_XH_PASSO + 4.9
    x0, x1 = x_tras - JST_XH_FUNDO, x_tras
    caixa = g_caixa(x0, x1, y_c - 0.5 * b, y_c + 0.5 * b, z_c - 0.5 * JST_XH_ALTURA, z_c + 0.5 * JST_XH_ALTURA)
    trava = g_caixa(x0 + 0.6, x0 + 3.6, y_c - 1.6, y_c + 1.6, z_c + 0.5 * JST_XH_ALTURA, z_c + 0.5 * JST_XH_ALTURA + 0.9)
    furos = [g_caixa(x0 - 0.05, x0, y_c + (k - 0.5 * (n - 1)) * JST_XH_PASSO - 0.6,
                     y_c + (k - 0.5 * (n - 1)) * JST_XH_PASSO + 0.6, z_c - 0.6, z_c + 1.6) for k in range(n)]
    return {"el_bat_branco": juntar(caixa, trava), "el_bat_preto": juntar(*furos)}, b


def _caminho_cinta(y0, y1, z0, zpb, zpt, y_s, r_c, bossa=None):
    """Laço fechado (y, z) da cinta à volta da secção do pack [y0, y1] × [z0, 0] (topo em 0), a subir pelos rasgos
    (±y_s) e a passar por cima da placa ([zpb, zpt]); `bossa` = (z, r) do cabo P+ por fora da face B."""
    t = 0.5 * E_CINTA
    pts = [(-y_s, zpt + t), (y_s, zpt + t), (y_s, zpb - 0.2), (y_s + 1.2, t), (y1 + t, t), (y1 + t, z0 - t),
           (y0 - t, z0 - t)]
    if bossa is not None:
        zb, rb = bossa
        yb = y0 + 2 * rb + 0.1
        pts += [(yb - t, max(z0 + 2.0, zb - rb - 4.0)), (yb - t, zb - rb - 2.5), (y0 - t, zb - rb + 0.6),
                (y0 - t, zb + rb - 0.6), (yb - t, zb + rb + 2.5), (yb - t, -2.0)]
        y_top0 = yb
    else:
        y_top0 = y0
    pts += [(y_top0 - t, t), (-y_s - 1.2, t), (-y_s, zpb - 0.2)]
    raios = [1.0, 1.0, 1.5, 1.5, r_c + t, r_c + t, r_c + t] + ([1.5] * 6 if bossa is not None else []) + \
        [r_c + t, 1.5, 1.0]
    return pts, raios


class Montagem:
    """Os packs (do build e do painel), o XT90, cintas, tapete e sensores de baixo no corpo `drone`."""

    def __init__(self, ctx, fund: Fundidor):
        self.ctx, self.fund = ctx, fund
        g = ctx.geom_existente("bateria")
        pb, sb = np.array(g.pos, float), np.array(g.size, float)
        self.pb, self.sb = pb, sb
        self.z_topo = float(pb[2] + sb[2])
        self.Q = Quadro(ctx, fund, "drone", (pb[0], pb[1], self.z_topo))
        pl = ctx.geom_existente("placa")
        if pl is not None:
            self.zpb = (float(pl.pos[2] - pl.size[2]) - self.z_topo) / MM
            self.zpt = (float(pl.pos[2] + pl.size[2]) - self.z_topo) / MM
        else:
            self.zpb, self.zpt = 4.0, 7.0
        st = next((x for x in ctx.spec.sites if x.name == "baixo"), None)
        self.z_site = ((float(st.pos[2]) - self.z_topo) / MM) if st is not None else -(2 * sb[2] / MM + 4.0)
        self.xy_site = (((float(st.pos[0]) - pb[0]) / MM, (float(st.pos[1]) - pb[1]) / MM) if st is not None
                        else (0.0, 0.0))

    # ------------------------------------------------------------------ peças fixas
    def xt90(self, x_fr: float, z_xt: float, xt90s: bool, QX: Quadro | None = None) -> dict:
        """XT90 fêmea do pack (`conector_xt90`, os copos em termorretrátil) encaixado no macho do drone
        (`el_xt90_macho` + os copos `el_xt90_copo_pos/neg`, nus: o cabo do drone é dos `fios`). `QX` = outro
        referencial (o XT90 DE PÉ, `xt90_posto`); sem ele, o do pack."""
        Q, ctx = (self.Q if QX is None else QX), self.ctx
        for nome in ("conector_xt90",):
            g = ctx.geom_existente(nome)
            if g is not None and int(g.group) in (1, 2, 3) and float(g.mass) == 0.0:
                ctx.apagar(nome)
        l_f = 15.0 if xt90s else 10.0                       # parte visível da fêmea (o resto entra no macho)
        x_enc = x_fr - l_f
        copos_f = [mover(g_cil(XT90_COPO_R, 0.0, 5.0, 16), eixo_para((1, 0, 0)), (x_fr, yy, z_xt))
                   for yy in (0.5 * XT90_PASSO, -0.5 * XT90_PASSO)]
        Q.malha("conector_xt90", "el_xt90", juntar(_corpo_xt90(x_enc, x_fr, z_xt), *copos_f), "bateria")
        Q.malha("el_xt90_macho", "el_xt90", _corpo_xt90(x_enc - 21.0, x_enc - 0.02, z_xt), "cabo_bateria")
        hh = 0.5 * XT90_H
        # marcas «+»/«−» em relevo no topo de cada corpo e as nervuras de agarrar
        for x_m in (x_fr - 0.5 * l_f, x_enc - 10.5):
            for yy, mais in ((0.5 * XT90_PASSO, True), (-0.5 * XT90_PASSO, False)):
                pecas = [g_caixa(x_m - 1.6, x_m + 1.6, yy - 0.35, yy + 0.35, z_xt + hh, z_xt + hh + 0.25)]
                if mais:
                    pecas.append(g_caixa(x_m - 0.35, x_m + 0.35, yy - 1.6, yy + 1.6, z_xt + hh, z_xt + hh + 0.25))
                Q.m("el_xt90", juntar(*pecas), "bateria" if x_m > x_enc else "cabo_bateria")
        for k in range(4):
            xr = x_enc - 4.0 - 4.0 * k
            for sy in (1.0, -1.0):
                ya, yb = sorted((sy * 0.5 * XT90_L, sy * (0.5 * XT90_L + 0.35)))
                Q.m("el_xt90", g_caixa(xr - 0.6, xr + 0.6, ya, yb, z_xt - hh + 1.2, z_xt + hh - XT90_CHANFRO - 0.5),
                    "cabo_bateria")
        copos = {}
        for polo, yy in (("pos", 0.5 * XT90_PASSO), ("neg", -0.5 * XT90_PASSO)):
            Q.cil(f"el_xt90_copo_{polo}", (x_enc - 21.0, yy, z_xt), (x_enc - 26.0, yy, z_xt), XT90_COPO_R, "el_ouro",
                  peca="cabo_bateria")
            # termorretrátil vermelho/preto sobre os copos da fêmea (lado do pack) até à saída do cabo
            v, f = mover(g_cil(XT90_COPO_R + 0.85, 0.0, 13.0, 16, tampa0=False, tampa1=False), eixo_para((1, 0, 0)),
                         (x_fr - 1.0, yy, z_xt))
            Q.m("el_bat_vermelho" if polo == "pos" else "el_bat_preto", (v, f), "bateria")
            Q.m("el_bat_vermelho" if polo == "pos" else "el_bat_preto",
                mover(g_anel(R_10AWG, XT90_COPO_R + 0.85, 12.6, 13.0, 16), eixo_para((1, 0, 0)), (x_fr - 1.0, yy, z_xt)),
                "bateria")
            copos[polo] = (x_fr + 5.0, yy, z_xt)
        return copos

    def xt90_posto(self, x_fr: float, z_xt: float, xt90s: bool):
        """O XT90 deitado (o de sempre: ao longo de −x atrás do pack) ou DE PÉ quando deitado sairia mais de
        `XT90_SALIENCIA_MAX` mm para lá da borda da placa de baixo (packs compridos / frames pequenos): de pé atrás do
        pack e da borda da placa, os copos do MACHO para CIMA (o 10 AWG do drone sobe livre, sem ter de virar junto
        às treliças) e os da fêmea para baixo (o cabo do pack chega por baixo). Devolve (copos no referencial do pack,
        direção por onde o cabo do pack chega aos copos — None = deitado, de +x —, (p0, p1) do encaixe)."""
        l_f = 15.0 if xt90s else 10.0
        pl = self.ctx.geom_existente("placa")
        borda = (float(pl.pos[0] - pl.size[0]) - float(self.Q.o[0])) / MM if pl is not None else -1e9
        ponta = x_fr - l_f - 26.0
        if borda - ponta <= XT90_SALIENCIA_MAX:
            copos = self.xt90(x_fr, z_xt, xt90s)
            cp = copos["pos"]
            return copos, None, ((cp[0] - 5.0, 0.0, cp[2]), (cp[0] - 5.0 - 10.0, 0.0, cp[2]))
        # de pé: o corpo 1 mm para trás da fêmea deitada e da borda da placa; a ponta dos copos do macho 20 mm acima
        # da face de cima da placa de baixo
        hh = 0.5 * XT90_H
        x_c = min(x_fr, borda) - hh - 1.0
        z_c = self.zpt + 20.0 - (l_f + 26.0)
        Rv = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])    # −x local (o macho) → +z
        QX = Quadro(self.ctx, self.fund, "drone", self.Q.ponto(x_c, 0.0, z_c), Rv)
        loc = self.xt90(0.0, 0.0, xt90s, QX)
        o = np.asarray(self.Q.o, float)
        copos = {polo: tuple(((QX.ponto(*q) - o) / MM).tolist()) for polo, q in loc.items()}
        e0 = tuple(((QX.ponto(-5.0, 0.0, 0.0) - o) / MM).tolist())
        e1 = tuple(((QX.ponto(-15.0, 0.0, 0.0) - o) / MM).tolist())
        notas = self.ctx.registo.notas.setdefault("ancoras", {})
        for polo, yy in (("pos", 0.5 * XT90_PASSO), ("neg", -0.5 * XT90_PASSO)):     # ponta livre dos copos do macho
            notas[f"el_xt90_copo_{polo}"] = {"corpo": "drone", "ponto": [float(v) for v in QX.ponto(-l_f - 26.0, yy, 0.0)],
                                             "direcao": [0.0, 0.0, 1.0], "nota": "XT90 de pé: o cabo do drone sai para cima"}
        return copos, (0.0, 0.0, -1.0), (e0, e1)

    # ------------------------------------------------------------------ por pack
    def pack(self, pg: PackGeo, chave: str, nomes: bool, copos: dict, ficha: dict) -> dict:
        """Pack + cabos + balanceador + ficha num `chave` do fundidor; com `nomes` as âncoras (terminais, ficha, cintas)."""
        Q = Quadro(self.ctx, self.fund, "drone", self.Q.o, chave=chave)
        for mat, peca, vf in pg.pecas:
            Q.m(mat, vf, peca)
        out = {"geoms": []}
        for polo in ("pos", "neg"):
            cx = pg.term_caixas.get(polo)
            if cx is None:
                continue
            if nomes:
                g = Q.caixa(f"el_bat_terminal_{polo}", *cx, "el_estanho", peca="bateria")
                out["geoms"].append(g.name)
            else:
                Q.m("el_estanho", g_caixa_arred(*cx, 0.5, 1), "bateria")
        # cabos 10 AWG: do terminal ao copo da fêmea (o P+ por baixo do P− quando cruza)
        z_xt = copos["pos"][2]
        pontas = {}
        for polo, mat in (("pos", "el_bat_vermelho"), ("neg", "el_bat_preto")):
            cam = [np.asarray(q, float) for q in getattr(pg, f"caminho_{polo}")]
            if not cam:
                continue
            fim = np.asarray(copos[polo], float)
            ult = cam[-1]
            if getattr(self, "_xt90_dir", None) is not None:
                # XT90 de pé: o cabo segue para trás à altura em que sai do pack, desce por baixo do copo e sobe
                # para dentro dele (o P+ passa por baixo do P− quando os lados trocam)
                cruza = (ult[1] < 0) != (fim[1] < 0)
                z_f = fim[2] - 14.0 - (2 * R_10AWG + 1.5 if (cruza and polo == "pos") else 0.0)
                cam += [np.array([fim[0] + 12.0, 0.5 * (ult[1] + fim[1]), min(float(ult[2]), z_f + 6.0)]),
                        np.array([fim[0] + 4.0, fim[1], z_f]), np.array([fim[0], fim[1], fim[2] - 7.0]), fim]
                pts = arredondar(cam, 5.0, 4)
                Q.m(mat, g_tubo(pts, R_10AWG, 10), "bateria")
                pontas[polo] = (pts[0], pts[-1])
                continue
            cruza = (ult[1] < 0) != (fim[1] < 0) and abs(ult[1]) > 8.0
            meio_x = 0.5 * (ult[0] + fim[0] + 13.0)
            if cruza:                                         # passa por baixo do outro cabo
                z_baixo = min(ult[2], z_xt) - 2 * R_10AWG - 1.5
                extra = [np.array([meio_x, ult[1] * 0.35, z_baixo]), np.array([fim[0] + 18.0, fim[1], z_baixo + 3.0])]
            else:
                extra = [np.array([meio_x, 0.5 * (ult[1] + fim[1]), 0.5 * (ult[2] + z_xt)])]
            extra += [np.array([fim[0] + 14.0, fim[1], z_xt]), np.array([fim[0] + 7.0, fim[1], z_xt])]
            # só os pontos que ficam entre a saída do pack e o copo (o cabo nunca volta para trás)
            x_ant = float(ult[0])
            for q in extra:
                if fim[0] + 3.0 < q[0] < x_ant - 1.5:
                    cam.append(q)
                    x_ant = float(q[0])
            cam.append(fim)
            pts = arredondar(cam, 5.0, 4)
            Q.m(mat, g_tubo(pts, R_10AWG, 10), "bateria")
            pontas[polo] = (pts[0], pts[-1])
        out["pontas_cabos"] = pontas
        # balanceador: da pilha vertical à saída do pack → ficha JST-XH (pinos ao longo de y)
        n = len(pg.balanco)
        if n:
            ultimos = [np.asarray(c[-1], float) for c in pg.balanco]
            x_s = min(float(q[0]) for q in ultimos)
            y_s = float(np.mean([q[1] for q in ultimos]))
            sy = 1.0 if y_s >= 0 else -1.0
            y_p = sy * max(abs(y_s) - 12.0, 21.5)
            x_r = x_s - 6.0
            z_p = -8.0
            pinos = []
            for k, c in enumerate(pg.balanco):
                cam = [np.asarray(q, float) for q in c]
                zk = float(cam[-1][2])
                y_pin = y_p + sy * (k - 0.5 * (n - 1)) * JST_XH_PASSO * (1.0 if sy > 0 else -1.0)
                y_pin = y_p + (k - 0.5 * (n - 1)) * JST_XH_PASSO
                cam += [np.array([x_s - 3.0, y_pin, zk]), np.array([x_s - 4.0, y_pin, z_p]),
                        np.array([x_r + 0.3, y_pin, z_p])]
                pts = arredondar(cam, 1.6, 3)
                Q.m("el_bat_preto" if k == 0 else "el_bat_vermelho", g_tubo(pts, R_BAL, 6), "bateria")
                pinos.append((pts[0], pts[-1]))
            mats, b = _jst_xh(n, x_r, y_p, z_p)
            if nomes:
                g = Q.caixa("el_bat_balanco", x_r - JST_XH_FUNDO, x_r, y_p - 0.5 * b, y_p + 0.5 * b, z_p - 0.5 * JST_XH_ALTURA,
                            z_p + 0.5 * JST_XH_ALTURA, "el_bat_branco", peca="bateria")
                out["geoms"].append(g.name)
                det = {k: v for k, v in mats.items() if k != "el_bat_branco"}
                trava = g_caixa(x_r - JST_XH_FUNDO + 0.6, x_r - JST_XH_FUNDO + 3.6, y_p - 1.6, y_p + 1.6,
                                z_p + 0.5 * JST_XH_ALTURA, z_p + 0.5 * JST_XH_ALTURA + 0.9)
                det["el_bat_branco"] = trava
            else:
                det = mats
            for mat, vf in det.items():
                Q.m(mat, vf, "bateria")
            out["pinos"] = pinos
        return out

    def cintas_tapete(self, pg: PackGeo, chave: str, nomes: bool, obst: list) -> list:
        """As 2 cintas (justas ao pack, pelos rasgos) + o tapete EVA em almofadas (com furos nas porcas de baixo)."""
        Q = Quadro(self.ctx, self.fund, "drone", self.Q.o, chave=chave)
        geoms = []
        r_c = 2.0 if pg.tipo == "21700" else 2.5
        for k, xc in enumerate((-RASGO_X, RASGO_X), 1):
            bossa = None
            if pg.cabo_face_b is not None and pg.cabo_face_b[0] < xc < pg.cabo_face_b[1]:
                bossa = (pg.cabo_face_b[2], pg.cabo_face_b[3])
            y0 = pg.y0
            pts, raios = _caminho_cinta(y0, pg.y1, pg.z_base if pg.z_base is not None else pg.z0, self.zpb, self.zpt,
                                        RASGO_Y, r_c, bossa)
            pts3 = [(xc, y, z) for y, z in pts]
            laco = arredondar(pts3, 1.5, 3, fechada=True, raios=raios)
            vf = g_fita(laco, L_CINTA, E_CINTA, (1.0, 0.0, 0.0), fechada=True)
            # fivela (alumínio anodizado preto) e a ponta dobrada por baixo
            zb = (pg.z_base if pg.z_base is not None else pg.z0) - E_CINTA
            yf = 0.5 * (pg.y0 + pg.y1) + 0.18 * (pg.y1 - pg.y0)
            fiv = juntar(g_caixa(xc - 9.5, xc + 9.5, yf - 10.0, yf - 7.0, zb - 3.4, zb),
                         g_caixa(xc - 9.5, xc + 9.5, yf + 7.0, yf + 10.0, zb - 3.4, zb),
                         g_caixa(xc - 9.5, xc - 7.8, yf - 7.0, yf + 7.0, zb - 3.4, zb),
                         g_caixa(xc + 7.8, xc + 9.5, yf - 7.0, yf + 7.0, zb - 3.4, zb),
                         g_caixa(xc - 7.8, xc + 7.8, yf - 1.0, yf + 1.0, zb - 3.0, zb - 0.6))
            ponta = g_fita([(xc, yf + 10.0, zb - 3.4 - 0.65), (xc, yf - 22.0, zb - 3.4 - 0.65)], L_CINTA, E_CINTA,
                           (1.0, 0.0, 0.0))
            if nomes:
                g = Q.malha(f"cinta_bateria_{k}", "el_bat_preto", juntar(vf, ponta), "cintas_bateria")
                geoms.append(g.name)
                Q.m("el_fivela", fiv, "cintas_bateria")
            else:
                Q.m("el_bat_preto", juntar(vf, ponta), "cintas_bateria")
                Q.m("el_fivela", fiv, "cintas_bateria")
        # tapete EVA de 4 mm: 3 almofadas entre as cintas, com furos nas porcas/cabeças que ficam por baixo da placa
        e_t = self.zpb
        if e_t >= E_TAPETE_MIN:
            if pg.tipo == "21700":
                ya, yb = pg.y0 + (2 * R_10AWG + 0.1 if pg.cabo_face_b is not None else 0.0) + 2.0, pg.y1 - 2.2
            else:
                ya, yb = pg.y0 + 2.0, pg.y1 - 2.0
            furos = [(x, y, r) for x, y, r in obst] + list(pg.cabecas_topo)
            limites = [(pg.x0 + 2.0, -RASGO_X - 0.5 * L_CINTA - 1.0), (-RASGO_X + 0.5 * L_CINTA + 1.0,
                                                                          RASGO_X - 0.5 * L_CINTA - 1.0),
                       (RASGO_X + 0.5 * L_CINTA + 1.0, pg.x1 - 2.0)]
            for xa, xb in limites:
                # obstáculo junto à ponta de uma almofada: encurta-a (um furo não caberia no recorte)
                for x, y, r in furos:
                    if ya - r < y < yb + r:
                        if xb - r - 1.2 < x < xb + r:
                            xb = min(xb, x - r - 0.6)
                        elif xa - r < x < xa + r + 1.2:
                            xa = max(xa, x + r + 0.6)
                if xb - xa < 6.0:
                    continue
                Q.m("el_bat_preto", g_placa_furos(xa, xb, ya, yb, 0.0, e_t - 0.05,
                                                  [(x, y, r) for x, y, r in furos if xa < x < xb], n=12), "cintas_bateria")
        return geoms

    def sensores(self, chave: str, z_s: float, yA: float, yB: float, nomes: bool, abs_: bool = False) -> list:
        """PMW3901 + VL53L1X na travessa de PETG presa à placa (2 pernas, 2 M3): a janela do VL53L1X à cota `z_s`.
        Com `abs_` (frame impresso) a travessa é de ABS e IMPRIMÍVEL: pernas e pés com a largura da travessa (o perfil
        em U é constante ao longo de x — imprime-se deitada sobre a face −x, sem suportes) e as pernas a partir do
        TOPO da travessa (os sólidos só se tocam: o volume é exato)."""
        Q = Quadro(self.ctx, self.fund, "drone", self.Q.o, chave=chave)
        geoms = []
        sx, sy = self.xy_site
        zt = z_s + 1.56                                        # topo da travessa (= base da placa do ToF)
        zb = z_s - 0.44
        # travessa (furos: janela do ToF e os 4 parafusos M2) + 2 pernas + 2 pés com o furo M3
        furos = [(sx, sy + 10.0, 3.2), (sx - 7.0, sy + 5.8, 1.1), (sx + 7.0, sy + 5.8, 1.1),
                 (sx - 9.0, sy - 1.0, 1.1), (sx + 9.0, sy - 1.0, 1.1)]
        trav = g_placa_furos(sx - 12.0, sx + 12.0, yB - 3.0, yA + 3.0, zb, zt, furos, n=12)
        if abs_:
            mx, z_p0 = 12.0, zt
        else:
            mx, z_p0 = 6.0, zb
        pernas = juntar(g_caixa(sx - mx, sx + mx, yA, yA + 3.0, z_p0, self.zpb - 3.0),
                        g_caixa(sx - mx, sx + mx, yB - 3.0, yB, z_p0, self.zpb - 3.0))
        pes = juntar(g_placa_furos(sx - mx, sx + mx, yA, yA + 13.0, self.zpb - 3.0, self.zpb - 0.02,
                                   [(sx, yA + 8.0, 1.7)], n=12),
                     g_placa_furos(sx - mx, sx + mx, yB - 13.0, yB, self.zpb - 3.0, self.zpb - 0.02,
                                   [(sx, yB - 8.0, 1.7)], n=12))
        Q.m(MATERIAL_ABS if abs_ else "el_petg", juntar(trav, pernas, pes), "bandeja_sensores")
        # VL53L1X (Pololu 3415: 18 × 13 × 2,2 com o sensor) por cima da travessa, a olhar para baixo pela janela
        t0, t1 = zt, zt + 0.64
        if nomes:
            geoms.append(Q.caixa("el_tof_pcb", sx - 9.0, sx + 9.0, sy + 3.5, sy + 16.5, t0, t1, "el_invisivel",
                                 peca="sensor_tof", rgba=(0.0, 0.0, 0.0, 0.0)).name)
        Q.m("el_pcb_pololu", g_placa_furos(sx - 9.0, sx + 9.0, sy + 3.5, sy + 16.5, t0, t1,
                                           [(sx - 7.0, sy + 5.8, 1.1), (sx + 7.0, sy + 5.8, 1.1)], n=10), "sensor_tof")
        Q.m("el_chip", g_caixa(sx - 2.45, sx + 2.45, sy + 10.0 - 1.25, sy + 10.0 + 1.25, z_s, t0), "sensor_tof")
        Q.m("el_vidro", juntar(g_caixa(sx - 1.9, sx - 0.4, sy + 9.45, sy + 10.55, z_s - 0.02, z_s),
                               g_caixa(sx + 0.4, sx + 1.9, sy + 9.45, sy + 10.55, z_s - 0.02, z_s)), "sensor_tof")
        Q.m("el_ouro", juntar(*[mover(g_anel(0.5, 0.85, t1, t1 + 0.03, 8), None, (sx + (j - 3) * 2.54, sy + 15.2, 0.0))
                                for j in range(7)]), "sensor_tof")
        # PMW3901 (Pimoroni: 24 × 24 × 5 com a lente) por baixo da travessa
        p1, p0 = zb, zb - 1.6
        if nomes:
            geoms.append(Q.caixa("el_fluxo_pcb", sx - 12.0, sx + 12.0, sy - 22.0, sy + 2.0, p0, p1, "el_invisivel",
                                 peca="sensor_fluxo", rgba=(0.0, 0.0, 0.0, 0.0)).name)
        Q.m("el_pcb_preto", g_placa_furos(sx - 12.0, sx + 12.0, sy - 22.0, sy + 2.0, p0, p1,
                                          [(sx - 9.0, sy - 1.0, 1.1), (sx + 9.0, sy - 1.0, 1.1)], n=10), "sensor_fluxo")
        Q.m("el_chip", g_caixa(sx - 3.0, sx + 3.0, sy - 13.0, sy - 7.0, p0 - 2.3, p0), "sensor_fluxo")
        Q.m("el_plastico_preto", mover(g_cil(3.6, -3.4, 0.0, 16), None, (sx, sy - 10.0, p0)), "sensor_fluxo")
        Q.m("el_vidro", mover(g_cil(1.3, -3.45, -3.4, 12), None, (sx, sy - 10.0, p0)), "sensor_fluxo")
        jst = (sx - 12.0, sx - 8.5, sy - 13.0, sy - 7.0, p0 - 2.9, p0)
        if nomes:
            geoms.append(Q.caixa("el_fluxo_conector", *jst, "el_jst", peca="sensor_fluxo").name)
        else:
            Q.m("el_jst", g_caixa(*jst), "sensor_fluxo")
        # parafusos M2 (ISO 7380, cabeça em cima) + porcas ISO 4032 por baixo — desenhados aqui (seguem a variante)
        cab = _cabeca_7380("M2")
        porca = _porca_4032("M2")
        Rb = np.diag([1.0, -1.0, -1.0])
        regs = []
        for (px, py), z_cab, aperto in (((sx - 7.0, sy + 5.8), t1, 0.64 + 2.0), ((sx + 7.0, sy + 5.8), t1, 0.64 + 2.0),
                                        ((sx - 9.0, sy - 1.0), zt, 2.0 + 1.6), ((sx + 9.0, sy - 1.0), zt, 2.0 + 1.6)):
            comp = 5.0 if aperto < 3.0 else 6.0
            peca = "sensor_tof" if py > sy + 5.0 else "sensor_fluxo"
            Q.m("el_bat_parafuso", mover(cab, Rb, (px, py, z_cab)), peca)
            Q.m("el_bat_parafuso", mover(g_cil(0.85, aperto + 1.6 - 0.2, comp, 8), Rb, (px, py, z_cab)), peca)
            Q.m("el_bat_zinco", mover(porca, Rb, (px, py, z_cab - aperto)), peca)
            regs.append({"ponto": (px, py, z_cab), "eixo": (0.0, 0.0, -1.0), "rosca": "M2", "comp": comp,
                         "aperto": aperto, "cabeca": "ISO 7380", "porca": "ISO 4032", "peca": peca})
        self._regs_sensores = regs
        return geoms

    def pes_sensores(self, yA: float, yB: float) -> None:
        """Os 2 parafusos M3 dos pés da travessa (fixos: todas as travessas usam os mesmos furos da placa)."""
        sx, _sy = self.xy_site
        fer = self.ctx.ferragens
        if fer is None:
            return
        for yy in (yA + 8.0, yB - 8.0):
            p = self.Q.ponto(sx, yy, self.zpb - 3.0)
            fer.parafuso("drone", p.tolist(), (0.0, 0.0, 1.0), "M3", aperto=(self.zpt - self.zpb) + 3.0,
                         cabeca="ISO 7380", porca="ISO 10511", material_="aco_preto", peca="bandeja_sensores",
                         nota="pé da travessa dos sensores de baixo: atravessa placa_inferior")


def _obstaculos_placa(ctx, Q: Quadro, zpb: float) -> list:
    """(x, y, r) no referencial do pack (mm) das ferragens já registadas que ficam por baixo da placa (porcas e cabeças
    de parafuso): o tapete leva furos nesses sítios."""
    out = []
    reg = getattr(ctx, "registo", None)
    if reg is None:
        return out
    raio = {"M2": 2.6, "M2.5": 3.4, "M3": 4.1, "M4": 5.2}
    Rt = Q.R.T
    for r in reg.ferragens:
        if r.get("corpo") != "drone" or r.get("tipo") not in ("porca", "parafuso", "anilha", "pilar"):
            continue
        pl = Rt @ ((np.asarray(r["ponto"], float) - Q.o) / MM)
        ez = float(np.asarray(r["eixo"], float)[2])
        # porca/anilha pendurada (eixo −z) ou cabeça de parafuso por baixo (eixo +z, apoio na face de baixo)
        if abs(pl[2] - zpb) < 0.6 and ((r["tipo"] in ("porca", "anilha") and ez < -0.5)
                                        or (r["tipo"] == "parafuso" and ez > 0.5)):
            out.append((float(pl[0]), float(pl[1]), raio.get(r.get("rosca"), 4.0)))
    return out


def montar(ctx, fund: Fundidor) -> dict:
    """Desenha os packs do build e do painel (variantes), o XT90, cintas, tapetes e sensores de baixo. Devolve as notas
    (rasgos das cintas, dimensões reais dos packs)."""
    from .. import componentes as comp
    hw = ctx.hw
    if ctx.geom_existente("bateria") is None:
        return {}
    materiais(ctx)
    for nome in ("cinta_bateria_1", "cinta_bateria_2"):     # os nomes antigos passam para as cintas novas
        g = ctx.geom_existente(nome)
        if g is not None and int(g.group) in (1, 2, 3) and float(g.mass) == 0.0 and not g.contype:
            ctx.apagar(nome)
    mt = Montagem(ctx, fund)
    bat = hw.bateria
    cel_id, S, P = bat.celula.id, int(bat.s), int(bat.p)
    variantes = []
    ativo = None
    if float(hw.frame.wheelbase) >= 0.40:                  # o painel só faz sentido nos frames grandes
        for vid, meta in comp.CATALOGO_BATERIAS_PAINEL.items():
            igual = meta["celula"] == cel_id and int(meta["s"]) == S and int(meta["p"]) == P
            variantes.append((vid, meta["celula"], int(meta["s"]), int(meta["p"])))
            if igual:
                ativo = vid
    if ativo is None:
        ativo = str(bat.id)
        variantes.append((ativo, cel_id, S, P))
    geos = {vid: pack_geo(c, s_, p_) for vid, c, s_, p_ in variantes}
    pg_at = geos[ativo]
    max_meio = max(max(-g.x0, g.x1) for g in geos.values())
    x_fr = -(max_meio + 14.0)
    z_xt = -11.0
    with ctx.peca("bateria"):
        copos, mt._xt90_dir, mt._encaixe = mt.xt90_posto(x_fr, z_xt, pg_at.xt90s)
    obst = _obstaculos_placa(ctx, mt.Q, mt.zpb)
    # sensores de baixo: a cota de cada variante (no site, ou abaixo do pack quando este é mais alto)
    z_s = mt.z_site
    sx, _sy = mt.xy_site
    folga_tof = 3.5 + 0.3                                 # cabeças dos M2 do ToF + 0,3 mm

    def cota_sensores(g: PackGeo) -> float:
        base = g.z_base if g.z_base is not None else g.z0
        ok = base >= z_s + folga_tof and all(z >= z_s + 1.56 + 0.4 for x, y, r, z in g.obst_baixo
                                             if abs(x - sx) < 12.0 + r)
        if ok:
            return z_s
        baixo = min([base] + [z for x, y, r, z in g.obst_baixo if abs(x - sx) < 12.0 + r])
        return baixo - folga_tof
    cotas = {vid: round(cota_sensores(g), 3) for vid, g in geos.items()}
    grupos: dict[float, list] = {}
    for vid, zz in cotas.items():
        grupos.setdefault(zz, []).append(vid)
    tem_sens = ctx.geom_existente("sensores_baixo") is not None and bool(
        {"fluxo", "tof"} & set((hw.sensores or {}).keys()))
    geoms_var = {vid: [] for vid in geos}
    abs_ = frame_abs(hw)
    if abs_:
        material_abs(ctx)
    if tem_sens:
        for idx, (zz, vids) in enumerate(sorted(grupos.items(), key=lambda t: -t[0])):
            yA = max(geos[v].y1 for v in vids) + 1.5
            yB = min(geos[v].y0 for v in vids) - 1.5
            chave = f"sens{idx}"
            nomes = ativo in vids
            nomeados = mt.sensores(chave, zz, yA, yB, nomes, abs_=abs_)
            if abs_ and nomes:
                regista_impressa(ctx, "bandeja_sensores", 0, "Travessa dos sensores de baixo (PMW3901 + VL53L1X)",
                                 Q_DE_LADO, "Perfil em U constante ao longo de x: imprime-se DEITADA sobre a face −x "
                                 "(sem suportes; os furos ficam horizontais, todos < 7 mm). Travessa de 2 mm com a janela "
                                 "do laser e os 4 furos M2, pernas de 3 mm e pés de 3 mm com o furo M3 dos parafusos que "
                                 "a prendem à placa de baixo (porca autoblocante por cima). As pernas descem ao lado do "
                                 "pack: na troca da bateria a travessa não sai.")
            regs = mt._regs_sensores
            for v in vids:
                geoms_var[v] += nomeados
                geoms_var[v].append(("chave", chave))
            if ctx.ferragens is not None and nomes:
                for r in regs:
                    p = mt.Q.ponto(*r["ponto"])
                    ctx.ferragens.parafuso("drone", p.tolist(), r["eixo"], r["rosca"], comp=r["comp"],
                                           aperto=r["aperto"], cabeca=r["cabeca"], porca=r["porca"], anilha_porca=False,
                                           peca=r["peca"], desenhar=False,
                                           nota=f"sensores de baixo (variantes {', '.join(vids)})")
            if nomes:
                mt.pes_sensores(yA, yB)
        ctx.esconder("sensores_baixo")
    # packs (inativos primeiro: os geoms partilhados ficam com a cor da ativa, que se regista por último)
    info = {}
    for vid in sorted(geos, key=lambda v: v == ativo):
        g = geos[vid]
        chave = "bat_" + vid
        nomes = vid == ativo
        r1 = mt.pack(g, chave, nomes, copos, {})
        r2 = mt.cintas_tapete(g, chave, nomes, obst)
        geoms_var[vid] += r1["geoms"] + r2
        geoms_var[vid].append(("chave", chave))
        info[vid] = r1
        if ctx.ferragens is not None and nomes:
            for fz in g.ferragens:
                p = mt.Q.ponto(*fz["ponto"])
                ctx.ferragens.parafuso("drone", p.tolist(), fz["eixo"], fz["rosca"], comp=fz["comp"], aperto=fz["aperto"],
                                       cabeca=fz["cabeca"], porca=fz["porca"], peca="bateria", desenhar=False,
                                       nota=f"placas de compressão do pack {vid}")
    ctx.esconder("bateria")
    mt._info = info
    mt._geoms_var = geoms_var
    mt._ativo = ativo
    mt._cotas = cotas
    mt._geos = geos
    mt._copos = copos
    return {"montagem": mt}


def registar(ctx, fund: Fundidor, res: dict) -> None:
    """Depois de `fund.fechar()`: regista as variantes (geoms com nome + os fundidos de cada chave), as ligações
    (cabos do pack ativo e balanceador) e as notas."""
    mt = res.get("montagem")
    if mt is None:
        return
    geoms = fund.geoms
    ordem = sorted(mt._geoms_var, key=lambda v: v == mt._ativo)
    for vid in ordem:
        lista = []
        for item in mt._geoms_var[vid]:
            if isinstance(item, tuple) and item[0] == "chave":
                lista += geoms.get(item[1], [])
            else:
                lista.append(item)
        lista = list(dict.fromkeys(lista))
        dz = (mt._cotas[vid] - mt.z_site) * MM
        ctx.registar_variante("bateria", vid, lista, ativa=(vid == mt._ativo), dz=dz,
                              dims_mm=list(mt._geos[vid].dims), descricao=mt._geos[vid].descricao)
    # ligações (pack ativo): terminais → XT90 fêmea; balanceador: fitas → ficha; encaixe; BEC na placa de energia
    ativo = mt._ativo
    inf = mt._info.get(ativo, {})
    Q = mt.Q
    for polo in ("pos", "neg"):
        pt = inf.get("pontas_cabos", {}).get(polo)
        if pt is not None:
            ctx.ligacao(f"cabo_pack_{polo}", de=f"el_bat_terminal_{polo}", para="conector_xt90",
                        corpos=("drone", "drone"), pontos=(Q.ponto(*pt[0]).tolist(), Q.ponto(*pt[1]).tolist()),
                        bitola="10 AWG", peca="bateria")
    nomes_chave = geoms.get("bat_" + ativo, [])
    # de onde saem os fios do balanceador: nas 21700 as FITAS de níquel das junções; nas bolsas (pouch, Amprius) a
    # placa da ponta / o barramento de abas em FR4 (os fios estão soldados nela, não nas abas)
    ordem = ("bat_niquel", "pcb_verde") if mt._geos[ativo].tipo == "21700" else ("pcb_verde", "bat_niquel")
    fita = next((n for n in nomes_chave if n.endswith(ordem[0])), None) or \
        next((n for n in nomes_chave if n.endswith(ordem[1])), None) or "el_bat_terminal_neg"
    tomadas = list(mt._geos[ativo].tomadas_pts)
    for k, (a, b) in enumerate(inf.get("pinos", []), 1):
        a = tomadas[k - 1] if k - 1 < len(tomadas) else a
        ctx.ligacao(f"balanceador_{k}", de=fita, para="el_bat_balanco", corpos=("drone", "drone"),
                    pontos=(Q.ponto(*a).tolist(), Q.ponto(*b).tolist()), bitola="22 AWG", peca="bateria", pino=k)
    e0, e1 = mt._encaixe
    ctx.ligacao("xt90_encaixe", de="conector_xt90", para="el_xt90_macho", corpos=("drone", "drone"),
                pontos=(Q.ponto(*e0).tolist(), Q.ponto(*e1).tolist()), bitola="XT90 (contactos Ø4,5)", peca="bateria")
    notas = ctx.registo.notas
    o = Q.o
    z_pl = float(o[2]) + 0.5 * (mt.zpb + mt.zpt) * MM
    notas["rasgos_cintas"] = [{"corpo": "drone", "centro": [float(o[0] + sxx * RASGO_X * MM), float(o[1] + syy * RASGO_Y * MM), z_pl],
                               "comprimento_mm": RASGO_COMP, "largura_mm": RASGO_LARG, "eixo_comprido": [1.0, 0.0, 0.0],
                               "peca": "placa_inferior"} for sxx in (-1, 1) for syy in (-1, 1)]
    notas["packs"] = {vid: {"dims_mm": list(g.dims), "descricao": g.descricao, "sensores_dz_mm": round(mt._cotas[vid] - mt.z_site, 2)}
                      for vid, g in mt._geos.items()}

__all__ = [
    "MM",
    "Fundidor",
    "Montagem",
    "PackGeo",
    "Quadro",
    "arredondar",
    "eixo_para",
    "g_anel",
    "g_caixa",
    "g_caixa_arred",
    "g_cil",
    "g_extrusao_y",
    "g_fita",
    "g_placa_furos",
    "g_prisma",
    "g_tubo",
    "juntar",
    "montar",
    "mover",
    "orientar_convexo",
    "pack_geo",
    "registar",
    "retangulo_arred",
    "sem_degeneradas",
]
