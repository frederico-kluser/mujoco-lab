"""lab/drone_rpi/detalhes/estrutura.py — ESTRUTURA realista (frame DIY de carbono de 1950 mm) e MECANISMO dos braços
articulados (ombro com servo + sem-fim autobloqueante, cotovelo de acionamento direto), só VISUAL: as regras estão no
`Contexto` do pacote (massa 0, sem contacto, grupo 3) e a física fica igual bit a bit (`python -m
lab.drone_rpi.detalhes.ver --so estrutura`).

O QUE SE DESENHA (dimensões reais; o que não tem cota publicada vem marcado «estimado»)

  frame (os dois builds)
    · placa de baixo 208 × 208 × 3 mm (catálogo `placa_mm`) em carbono 3K tafetá (textura EMBUTIDA do MuJoCo: xadrez de
      mechas de 2,5 mm — nada de texturas em memória, que o `to_xml` não exporta), com furo central de cablagem, rasgos
      das cintas da bateria e furos de alívio; no rígido os cantos são chanfrados, no articulado têm o ENTALHE por onde
      passa a caixa do redutor do ombro;
    · placa de cima (`placa_superior`, o mesmo geom reestilizado) com a janela da pilha de eletrónica e furos de alívio;
      no articulado é a MESA dos 4 servos do ombro (orelhas e furos por onde o horn aciona o sem-fim);
    · 4 espaçadores de alumínio Ø5 M3 (`espacador_placa_*`, reestilizados) com parafusos por cima e por baixo;
    · tubos de carbono 25 × 23 mm (catálogo `diy_tubo_carbono_1950`) — no rígido com o TOPO à altura onde assentam a
      placa do motor e os ESC (eixo a −10 mm do plano da placa), no articulado no plano das juntas (= o eixo físico);
    · rígido: abraçadeiras CNC dos tubos nos cantos da placa, suporte do motor que abraça a ponta do tubo com a placa do
      motor por cima (`suporte_motor_*`, reestilizados), abraçadeiras em cruz das treliças (`trelica_estab_*`, varões de
      8 mm ao eixo dos tubos);
    · trem de pouso: abraçadeira em T no tubo, perna de carbono Ø12 (a cápsula física) e pé de borracha com o fundo no
      ponto de contacto da cápsula.

  mecanismo dos braços articulados (só com `ctx.articulado`; cada peça no CORPO que roda como ela)
    OMBRO (eixo y na esquina da placa, a `raio_ombro` = 150 mm do centro)
      · corpo `drone` (FIXO): caixa do redutor em alumínio com janela de policarbonato à frente (+a: a coroa) e janela
        de inspeção do lado de dentro (−b: o sem-fim a engrenar), 2 rolamentos 6800 no veio de saída, sem-fim de aço de
        1 entrada m 0,8 (d₁ 12 mm → Ø13,6 mm, passo axial π·m = 2,51 mm) de eixo VERTICAL a 14 mm = (d₁ + d₂)/2 do veio,
        rolamentos 685 do sem-fim, o servo DYNAMIXEL XH430-V210-R (28,5 × 46,5 × 34 mm) deitado na placa de cima com o
        horn para baixo a acionar o sem-fim, encoder AS5048A (placa adaptadora 28 × 22 mm, entreferro ≤ 2 mm) na ponta
        do veio e a ESCALA −40…+40° (os batentes do catálogo) na face exterior da caixa;
      · corpo `braco{k}` (RODA com o ombro): coroa de bronze de 20 dentes (d₂ 16 mm, Ø17,6 mm), veio Ø10, íman
        diametral, cubo de alumínio LARANJA com o encaixe do tubo a 45° e o PONTEIRO vermelho sobre a escala, e o tubo;
    COTOVELO (eixo y na ponta do braço)
      · corpo `braco{k}`: o servo XH430 (horn e idler nos dois lados, eixo = eixo do cotovelo), berço de alumínio, a
        ponteira do tubo e a ESCALA −45…+45° na face do horn;
      · corpo `mastro{k}` (RODA com o cotovelo): garfo LARANJA aparafusado ao horn e ao idler (o padrão do «hinge frame»
        FR12-H101K da ROBOTIS), ponteiro vermelho, abraçadeira e tubo de carbono Ø16 do mastro (catálogo
        `mastro.diametro_mm`), abraçadeira do motor e placa do motor (`suporte_motor_*`).
    O laranja marca as 8 peças que RODAM (as duas dobradiças de cada braço veem-se de longe). Verificado: nas poses
    de mira (corpo a ±35° com a IK de `bracos_controlo.py`) e em todo o curso das juntas (ombro ±40°, cotovelo ±60°)
    nenhuma peça móvel entra nas fixas (folga mínima 0,8 mm no ombro — o ponteiro sobre a escala — e 1,8 mm no
    cotovelo).

  Os outros builds do catálogo usam o mesmo desenho, à escala: os furos das placas escalam com a placa (e só ficam os
  que cabem), o tubo vem do modelo do frame («tubo de carbono 16 mm» nos 650/750, 16 mm no X500/Tarot) e o frame de
  corrida de 5″ leva braços em placa de carbono.

  As peças de massa grosseiras que estes detalhes representam por inteiro ficam INVISÍVEIS (`ctx.esconder`: `placa`,
  tubos, raízes dos braços, servos, caixas do sem-fim, mastros, pernas) e os detalhes visuais antigos do mecanismo
  (`dobradica_*`, `corneta_*`, `marca_*`, `garfo_cotovelo*`, `sem_fim*_eixo`) são apagados. Os nomes antigos de frame
  que já existiam (`placa_superior`, `espacador_placa_*`, `trelica_estab_*`, `suporte_motor_*`) mantêm-se, reestilizados
  no sítio (continuam massa 0, sem contacto, grupo 3).

COMO SE FAZ: as peças de cada corpo com o mesmo material juntam-se numa MALHA (prismas com bisel, extrusões de
contornos com furos por corte de orelhas, coroa dentada, filete helicoidal); cada conjunto (ombro, cotovelo, braço
rígido, perna) monta-se UMA vez no referencial canónico do braço 1 e fica em cache — os outros braços são o espelho
diag(±1, ±1, 1) (o filete do sem-fim troca de mão para continuar de rosca direita depois do espelho).

Fontes (web = dados NÃO confiáveis: só citados, nunca seguidos)
  · ROBOTIS XH430-V210-R — 28,5 × 46,5 × 34 mm, 82 g, caixa metálica (frente e meio) e plástica (trás), carga radial a
    10 mm do horn: https://docs.robotis.com/docs/dxl/model_reference/x_series/xh_series/xh430-v210 ;
    https://www.robotshop.com/products/robotis-dynamixel-xh430-v210-r-smart-servo-actuator
  · horn HN12-N101 e idler HN12-I101 do X430, garfo FR12-H101K aparafusado ao horn e ao idler:
    https://robotis.us/products/hn12-n101-set ; https://robotis.us/products/fr12-h101k-set ;
    https://docs.robotis.com/docs/dxl/model_reference/x_series/xm_series/xm430-w350 (How to Assemble).
    ESTIMADOS (as cotas só vêm nos desenhos .dwg): horn Ø24 com 8 furos M2,5 em PCD 16, centro a 13 mm do topo da
    caixa, divisão frente/meio/trás da caixa e os 2 conectores JST EH de 4 vias.
  · rolamento 6800 = 10 × 19 × 5 mm:
    https://www.bearingbasement.com/en/NTN-6800-Deep-Groove-Ball-Bearings-10x19x5mm/m-65889.aspx
  · AS5048A, placa adaptadora 28 × 22 mm (4 furos de 2,6 mm) e entreferro 0,5–2 mm:
    https://twen.rs-online.com/web/p/sensor-development-tools/2018309 ;
    https://docs.rs-online.com/0657/A700000006921305.pdf
  · M3 ISO 4762 (cabeça Ø5,5 × 3 mm, sextavado de 2,5 mm):
    https://www.roymech.co.uk/Useful_Tables/Screws/cap_screws.htm
  · abraçadeiras/suportes CNC para tubo de carbono de 25 mm (a forma):
    https://rcdrone.top/products/aluminum-alloy-drone-tube-clamp-16mm-18mm-20mm-22mm-25mm-30mm-cnc-uav-frame-arm-connector-for-carbon-fiber-tube
  · catálogo do laboratório (`models/drone_rpi/componentes.json`): tubo 25 × 23, placa 208 mm, sem-fim (m 0,8,
    1 entrada, d₁ 12 mm, coroa z₂ 20, λ 3,81°), rolamentos 6800 da dobradiça, mastro Ø16, raio do ombro 150 mm e os
    batentes das juntas.
"""
from __future__ import annotations

import functools
import math
import re

import mujoco
import numpy as np

# ============================================================================ dimensões (m)
TUBO_R = 0.0125              # tubo do braço 25 × 23 mm (catálogo)
Z_TUBO_RIGIDO = -0.010       # eixo do tubo no rígido: topo a +2,5 mm (assentam aí a placa do motor e os ESC)
PERNA_R = 0.006              # a cápsula física da perna (Ø12)
SERVO_W, SERVO_H, SERVO_D = 0.0285, 0.0465, 0.034     # XH430: largura, altura, profundidade (= eixo do horn)
HORN_R, HORN_E = 0.012, 0.0025                        # horn HN12-N101 (estimado)
HORN_TOPO = 0.013            # centro do horn → topo da caixa (estimado)
ROL6800 = (0.005, 0.0095)                             # rolamento 6800: raio do furo, raio exterior (largura 5 mm)
SEMFIM_M, SEMFIM_D1, COROA_Z = 0.0008, 0.012, 20       # catálogo: módulo, diâmetro primitivo do sem-fim, dentes
ENTRE_EIXOS = 0.5 * (SEMFIM_D1 + SEMFIM_M * COROA_Z)  # 14 mm
PLACA_SUP_E = 0.0012         # meia espessura da placa de cima (a de sempre)
MASTRO_R = 0.008             # tubo do mastro Ø16 (catálogo `mastro.diametro_mm`)
LADRILHO_CARBONO = 0.005     # ladrilho da textura do carbono: 2 × 2 mechas de 2,5 mm (3K tafetá)
K_UV = 1.0 / LADRILHO_CARBONO
U45 = (math.sqrt(0.5), math.sqrt(0.5), 0.0)           # direção canónica do braço 1 (+x, +y)

# ============================================================================ malhas (numpy puro, em cache)


def _det3(R) -> float:
    return float(R[0, 0] * (R[1, 1] * R[2, 2] - R[1, 2] * R[2, 1]) - R[0, 1] * (R[1, 0] * R[2, 2] - R[1, 2] * R[2, 0])
                 + R[0, 2] * (R[1, 0] * R[2, 1] - R[1, 1] * R[2, 0]))


class _Malha:
    """Triângulos de várias peças com o mesmo material (uma malha + um geom no fim)."""

    def __init__(self):
        self.v, self.f, self.t, self.n = [], [], [], 0

    def junta(self, parte, R=None, p=None):
        v, f, t = parte
        if R is not None:
            v = v @ np.asarray(R, float).T
            if _det3(np.asarray(R, float)) < 0.0:     # espelho: inverte o sentido dos triângulos (normais para fora)
                f = f[:, ::-1]
        if p is not None:
            v = v + np.asarray(p, float)
        self.v.append(v)
        self.f.append(f + self.n)
        self.t.append(t)
        self.n += len(v)

    def arrays(self):
        return np.concatenate(self.v), np.concatenate(self.f), np.concatenate(self.t)


class _Lotes:
    """Peças agrupadas por (etiqueta, material) — a etiqueta diz a que corpo vão (no canónico: «fixo», «movel»…)."""

    def __init__(self):
        self.malhas: dict[tuple[str, str], _Malha] = {}

    def junta(self, etiqueta, material, parte, R=None, p=None):
        self.malhas.setdefault((etiqueta, material), _Malha()).junta(parte, R, p)

    def congelar(self) -> tuple:
        return tuple((chave, *m.arrays()) for chave, m in self.malhas.items() if m.n)


def _ret_arred(hx: float, hy: float, r: float, n: int = 3):
    """Contorno (em função do recuo) de um retângulo de cantos arredondados, anti-horário."""
    r0 = min(r, hx, hy)

    def f(recuo: float = 0.0):
        ax, ay = hx - recuo, hy - recuo
        if r0 <= 1e-9:                        # cantos vivos: um vértice por canto
            return np.array([(ax, ay), (-ax, ay), (-ax, -ay), (ax, -ay)])
        rr = max(r0 - recuo, 0.25 * r0)       # o anel recuado do bisel mantém um raio mínimo (mesmo nº de vértices)
        pts = []
        for cx, cy, a0 in ((ax - rr, ay - rr, 0.0), (-ax + rr, ay - rr, 90.0), (-ax + rr, -ay + rr, 180.0),
                           (ax - rr, -ay + rr, 270.0)):
            for i in range(n + 1):
                a = math.radians(a0 + 90.0 * i / n)
                pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        return np.array(pts)
    return f


def _comprimentos(c):
    d = np.linalg.norm(np.diff(np.vstack([c, c[:1]]), axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(d)])[:len(c)]


@functools.cache
def _prisma(hx: float, hy: float, r: float, n: int, z0: float, z1: float, bisel: float = 0.0):
    """Prisma de retângulo arredondado com bisel nas arestas de cima e de baixo (aspeto de peça maquinada)."""
    fcont = _ret_arred(hx, hy, r, n)
    aneis = ([(fcont(bisel), z0), (fcont(0.0), z0 + bisel), (fcont(0.0), z1 - bisel), (fcont(bisel), z1)]
             if bisel > 0.0 else [(fcont(0.0), z0), (fcont(0.0), z1)])
    m = len(aneis[0][0])
    V, F, T = [], [], []
    for c, z in aneis:
        s = _comprimentos(c)
        for j in range(m):
            V.append((c[j, 0], c[j, 1], z))
            T.append((s[j] * K_UV, z * K_UV))
    for i in range(len(aneis) - 1):
        a0, b0 = i * m, (i + 1) * m
        for j in range(m):
            j1 = (j + 1) % m
            F += [(a0 + j, a0 + j1, b0 + j1), (a0 + j, b0 + j1, b0 + j)]
    for (c, z), sinal in ((aneis[0], -1), (aneis[-1], 1)):
        cen = c.mean(axis=0)
        i0 = len(V)
        V.append((cen[0], cen[1], z))
        T.append((cen[0] * K_UV, cen[1] * K_UV))
        for j in range(m):
            V.append((c[j, 0], c[j, 1], z))
            T.append((c[j, 0] * K_UV, c[j, 1] * K_UV))
        for j in range(m):
            a, b = i0 + 1 + j, i0 + 1 + (j + 1) % m
            F.append((i0, a, b) if sinal > 0 else (i0, b, a))
    return np.array(V), np.array(F, dtype=np.int64), np.array(T)


def _caixa(hx, hy, hz, r=0.0015, bisel=0.0006, n=3):
    """Caixa centrada com as arestas verticais arredondadas e bisel em cima/baixo."""
    return _prisma(round(hx, 7), round(hy, 7), round(r, 7), n, round(-hz, 7), round(hz, 7), round(bisel, 7))


@functools.cache
def _anel_polar(th: tuple, r_ext: tuple, r_int, z0: float, z1: float):
    """Sólido entre dois contornos polares (r(θ) estrelado à volta da origem) de z0 a z1; `r_int=None` = maciço."""
    th = np.asarray(th, float)
    n = len(th)
    re = np.asarray(r_ext, float)
    c, s = np.cos(th), np.sin(th)
    P = np.stack([re * c, re * s], 1)
    V, F, T = [], [], []

    def add(x, y, z, u, w):
        V.append((x, y, z))
        T.append((u * K_UV, w * K_UV))
        return len(V) - 1

    arc = _comprimentos(P)
    lo = [add(P[j, 0], P[j, 1], z0, arc[j], z0) for j in range(n)]
    hi = [add(P[j, 0], P[j, 1], z1, arc[j], z1) for j in range(n)]
    for j in range(n):
        j1 = (j + 1) % n
        F += [(lo[j], lo[j1], hi[j1]), (lo[j], hi[j1], hi[j])]
    if r_int is None:
        for z, sinal in ((z0, -1), (z1, 1)):
            ic = add(0.0, 0.0, z, 0.0, 0.0)
            ids = [add(P[j, 0], P[j, 1], z, P[j, 0], P[j, 1]) for j in range(n)]
            for j in range(n):
                a, b = ids[j], ids[(j + 1) % n]
                F.append((ic, a, b) if sinal > 0 else (ic, b, a))
    else:
        ri = np.asarray(r_int, float)
        Q = np.stack([ri * c, ri * s], 1)
        arcq = _comprimentos(Q)
        loq = [add(Q[j, 0], Q[j, 1], z0, arcq[j], z0) for j in range(n)]
        hiq = [add(Q[j, 0], Q[j, 1], z1, arcq[j], z1) for j in range(n)]
        for j in range(n):
            j1 = (j + 1) % n
            F += [(loq[j], hiq[j1], loq[j1]), (loq[j], hiq[j], hiq[j1])]
        for z, sinal in ((z0, -1), (z1, 1)):
            ip = [add(P[j, 0], P[j, 1], z, P[j, 0], P[j, 1]) for j in range(n)]
            iq = [add(Q[j, 0], Q[j, 1], z, Q[j, 0], Q[j, 1]) for j in range(n)]
            for j in range(n):
                j1 = (j + 1) % n
                if sinal > 0:
                    F += [(iq[j], ip[j], ip[j1]), (iq[j], ip[j1], iq[j1])]
                else:
                    F += [(iq[j], ip[j1], ip[j]), (iq[j], iq[j1], ip[j1])]
    return np.array(V), np.array(F, dtype=np.int64), np.array(T)


def _theta(n: int, fase: float = 0.0) -> tuple:
    return tuple(round(fase + 2.0 * math.pi * i / n, 9) for i in range(n))


@functools.cache
def _cilindro(r, z0, z1, n=20):
    return _anel_polar(_theta(n), (r,) * n, None, z0, z1)


@functools.cache
def _anel(r_ext, r_int, z0, z1, n=20):
    return _anel_polar(_theta(n), (r_ext,) * n, (r_int,) * n, z0, z1)


@functools.cache
def _hexagono(r_af, z0, z1):
    """Prisma sextavado (r_af = metade da medida entre faces)."""
    rc = r_af / math.cos(math.pi / 6.0)
    return _anel_polar(_theta(6, math.pi / 6.0), (rc,) * 6, None, z0, z1)


@functools.cache
def _engrenagem(z: int, m: float, z0: float, z1: float, r_furo: float):
    """Coroa de dentes retos trapezoidais (adendo m, dedendo 1,25 m) com furo."""
    tau, psi = 2.0 * math.pi / z, math.pi / (2.0 * z)
    rp, ra, rf = 0.5 * m * z, 0.5 * m * z + m, 0.5 * m * z - 1.25 * m
    pts = []
    for i in range(z):
        c0 = i * tau
        for d, rr in ((-tau / 2, rf), (-1.25 * psi, rf), (-0.55 * psi, ra), (0.55 * psi, ra), (1.25 * psi, rf)):
            pts.append(((c0 + d) % (2.0 * math.pi), rr))
    pts.sort()
    _ = rp
    return _anel_polar(tuple(p[0] for p in pts), tuple(p[1] for p in pts), (r_furo,) * len(pts), z0, z1)


@functools.cache
def _rosca(r_raiz: float, r_crista: float, passo: float, z0: float, z1: float, mao: int = 1, n_volta: int = 16):
    """Parafuso sem-fim (eixo z): núcleo + filete helicoidal trapezoidal; `mao` = +1 à direita, −1 à esquerda."""
    V, F = [], []
    wr, wc = 0.62 * passo, 0.24 * passo
    voltas = (z1 - z0 - wr) / passo
    K = max(int(voltas * n_volta), 2)
    sec = [(r_raiz - 1e-4, -wr / 2), (r_crista, -wc / 2), (r_crista, wc / 2), (r_raiz - 1e-4, wr / 2)]
    for e in range(3):                     # 3 faixas (flanco, crista, flanco) com vértices próprios: normais limpas
        base = len(V)
        for k in range(K + 1):
            t = 2.0 * math.pi * voltas * k / K
            a = mao * t
            zc = z0 + wr / 2 + passo * t / (2.0 * math.pi)
            for rr, dz in (sec[e], sec[e + 1]):
                V.append((rr * math.cos(a), rr * math.sin(a), zc + dz))
        for k in range(K):
            p0, p1 = base + 2 * k, base + 2 * (k + 1)
            tri = [(p0, p1, p1 + 1), (p0, p1 + 1, p0 + 1)]
            F += [x[::-1] for x in tri] if mao < 0 else tri
    Vn, Fn, Tn = _cilindro(r_raiz, z0, z1, n=n_volta)
    V = np.vstack([np.array(V), Vn])
    F = np.vstack([np.array(F, dtype=np.int64), Fn + len(V) - len(Vn)])
    T = np.vstack([np.zeros((len(V) - len(Vn), 2)), Tn])
    return V, F, T


@functools.cache
def _elipsoide(rx, ry, rz, n=10):
    """Elipsoide (malha UV) — pés de borracha."""
    V, F = [], []
    for i in range(n + 1):
        ph = math.pi * i / n - math.pi / 2
        for j in range(2 * n):
            th = math.pi * j / n
            V.append((rx * math.cos(ph) * math.cos(th), ry * math.cos(ph) * math.sin(th), rz * math.sin(ph)))
    for i in range(n):
        for j in range(2 * n):
            a, b = i * 2 * n + j, i * 2 * n + (j + 1) % (2 * n)
            F += [(a, b, b + 2 * n), (a, b + 2 * n, a + 2 * n)]
    return np.array(V), np.array(F, dtype=np.int64), np.zeros((len(V), 2))


# ------------------------------------------------------------------ extrusão de contornos com furos
def _cruz(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def _triangular(exterior, furos=()):
    """Corte de orelhas com pontes de Eberly para os furos (puro Python): devolve (pontos, triângulos anti-horários)."""
    P = [tuple(map(float, p)) for p in exterior]
    if _area2(P) < 0:
        P.reverse()
    anel = list(range(len(P)))
    hs = []
    for h in furos:
        h = [tuple(map(float, p)) for p in h]
        if _area2(h) > 0:
            h.reverse()
        hs.append(h)
    hs.sort(key=lambda h: -max(p[0] for p in h))
    for h in hs:
        i0 = len(P)
        P.extend(h)
        idx_h = list(range(i0, i0 + len(h)))
        k = max(range(len(h)), key=lambda j: (h[j][0], -h[j][1]))
        M = h[k]
        melhor, bi, ix = math.inf, -1, None
        n = len(anel)
        for j in range(n):                     # raio +x a partir do vértice mais à direita do furo
            a, b = P[anel[j]], P[anel[(j + 1) % n]]
            if (a[1] - M[1]) * (b[1] - M[1]) > 0 or a[1] == b[1]:
                continue
            t = (M[1] - a[1]) / (b[1] - a[1])
            if t < 0 or t > 1:
                continue
            x = a[0] + t * (b[0] - a[0])
            if x >= M[0] - 1e-12 and x - M[0] < melhor:
                melhor, bi, ix = x - M[0], j, (x, M[1])
        pa, pb = bi, (bi + 1) % n
        cand_pos = pa if P[anel[pa]][0] > P[anel[pb]][0] else pb
        cand = anel[cand_pos]
        Pc = P[cand]
        tri = (M, ix, Pc) if _cruz(M, ix, Pc) > 0 else (M, Pc, ix)
        melhor_ang, escolhido, esc_pos = math.inf, cand, cand_pos
        for j in range(n):                     # vértices reflexos dentro do triângulo de visibilidade
            q = anel[j]
            if j == cand_pos or P[q] == Pc:
                continue
            pq = P[q]
            if _cruz(P[anel[j - 1]], pq, P[anel[(j + 1) % n]]) >= 0:
                continue
            if _cruz(tri[0], tri[1], pq) >= -1e-15 and _cruz(tri[1], tri[2], pq) >= -1e-15 and \
                    _cruz(tri[2], tri[0], pq) >= -1e-15:
                ang = abs(math.atan2(pq[1] - M[1], pq[0] - M[0]))
                if ang < melhor_ang - 1e-12 or (abs(ang - melhor_ang) < 1e-12 and pq[0] < P[escolhido][0]):
                    melhor_ang, escolhido, esc_pos = ang, q, j
        alvo = P[escolhido]
        pos = esc_pos
        for j in range(n):                     # o vértice pode estar repetido (pontes anteriores): a cópia certa
            if P[anel[j]] != alvo:
                continue
            a, v, b = P[anel[j - 1]], alvo, P[anel[(j + 1) % n]]
            dentro = (_cruz(a, v, M) >= 0 and _cruz(v, b, M) >= 0) if _cruz(a, v, b) >= 0 else \
                (_cruz(a, v, M) >= 0 or _cruz(v, b, M) >= 0)
            if dentro:
                pos = j
                break
        hk = idx_h[k:] + idx_h[:k]
        anel = anel[:pos + 1] + hk + [hk[0], escolhido] + anel[pos + 1:]
    tris, v = [], anel[:]
    while len(v) > 3:
        n = len(v)
        reflexos = [v[j] for j in range(n) if _cruz(P[v[j - 1]], P[v[j]], P[v[(j + 1) % n]]) <= 0]
        cortou = False
        for j in range(n):
            ia, ib, ic = v[j - 1], v[j], v[(j + 1) % n]
            a, b, c = P[ia], P[ib], P[ic]
            if _cruz(a, b, c) <= 1e-18:
                continue
            ok = True
            for q in reflexos:
                if q in (ia, ib, ic):
                    continue
                pq = P[q]
                if pq == a or pq == b or pq == c:
                    continue
                if _cruz(a, b, pq) >= -1e-15 and _cruz(b, c, pq) >= -1e-15 and _cruz(c, a, pq) >= -1e-15:
                    ok = False
                    break
            if ok:
                tris.append((ia, ib, ic))
                del v[j]
                cortou = True
                break
        if not cortou:
            del v[0]
    if len(v) == 3:
        tris.append(tuple(v))
    return P, tris


@functools.cache
def _extrusao(exterior: tuple, furos: tuple, z0: float, z1: float):
    """Placa de contorno + furos (em xy) extrudida de z0 a z1, com as paredes de todos os contornos."""
    P, tris = _triangular(exterior, furos)
    V, F, T = [], [], []
    npt = len(P)
    for z in (z0, z1):
        for x, y in P:
            V.append((x, y, z))
            T.append((x * K_UV, y * K_UV))
    for a, b, c in tris:
        if abs(_cruz(P[a], P[b], P[c])) < 1e-14:
            continue
        F.append((a, c, b))                      # baixo (normal −z)
        F.append((npt + a, npt + b, npt + c))    # cima
    for cont, sentido in [(exterior, 1)] + [(h, -1) for h in furos]:
        c = [tuple(map(float, p)) for p in cont]
        if (_area2(c) > 0) != (sentido > 0):
            c.reverse()
        s = _comprimentos(np.array(c))
        base, m = len(V), len(c)
        for j, (x, y) in enumerate(c):
            V.append((x, y, z0))
            T.append((s[j] * K_UV, z0 * K_UV))
            V.append((x, y, z1))
            T.append((s[j] * K_UV, z1 * K_UV))
        for j in range(m):
            j1 = (j + 1) % m
            a0, a1, b0, b1 = base + 2 * j, base + 2 * j1, base + 2 * j + 1, base + 2 * j1 + 1
            F += [(a0, a1, b1), (a0, b1, b0)]
    return np.array(V), np.array(F, dtype=np.int64), np.array(T)


def _circulo(cx, cy, r, n=20, fase=0.0):
    return tuple((round(cx + r * math.cos(fase + 2 * math.pi * i / n), 7),
                  round(cy + r * math.sin(fase + 2 * math.pi * i / n), 7)) for i in range(n))


def _rasgo(cx, cy, meio, r, ang=0.0, n=6):
    """Rasgo oblongo centrado em (cx, cy): meio-comprimento `meio` entre centros, raio `r`, ângulo `ang`."""
    pts = []
    ca, sa = math.cos(ang), math.sin(ang)
    for sinal, a0 in ((1.0, -90.0), (-1.0, 90.0)):
        for i in range(n + 1):
            a = math.radians(a0 + 180.0 * i / n)
            x, y = sinal * meio + r * math.cos(a), r * math.sin(a)
            pts.append((round(cx + ca * x - sa * y, 7), round(cy + sa * x + ca * y, 7)))
    return tuple(pts)


def _poligono_arred(vertices, r, n=4):
    """Arredonda os cantos (côncavos e convexos) de um polígono anti-horário com raio r."""
    out = []
    m = len(vertices)
    for i in range(m):
        p0, p1, p2 = (np.array(vertices[j % m], float) for j in (i - 1, i, i + 1))
        d0, d1 = p0 - p1, p2 - p1
        l0, l1 = np.linalg.norm(d0), np.linalg.norm(d1)
        d0, d1 = d0 / l0, d1 / l1
        ang = math.acos(max(-1.0, min(1.0, float(d0 @ d1))))
        rr = min(r, 0.45 * min(l0, l1) * math.tan(0.5 * ang))
        if rr <= 1e-6 or abs(math.pi - ang) < 1e-6:
            out.append((round(float(p1[0]), 7), round(float(p1[1]), 7)))
            continue
        t = rr / math.tan(0.5 * ang)
        a, b = p1 + d0 * t, p1 + d1 * t
        bis = (d0 + d1) / np.linalg.norm(d0 + d1)
        c = p1 + bis * (rr / math.sin(0.5 * ang))
        a0 = math.atan2(a[1] - c[1], a[0] - c[0])
        da = (math.atan2(b[1] - c[1], b[0] - c[0]) - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(n + 1):
            aa = a0 + da * k / n
            out.append((round(float(c[0] + rr * math.cos(aa)), 7), round(float(c[1] + rr * math.sin(aa)), 7)))
    return tuple(out)


def _no_poligono(x, y, poly) -> bool:
    dentro, n = False, len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x0 + (y - y0) * (x1 - x0) / (y1 - y0) > x:
            dentro = not dentro
    return dentro


def _dist_segmento(x, y, a, b) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0.0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - ax - t * dx, y - ay - t * dy)


@functools.cache
def _furos_que_cabem(contorno: tuple, furos: tuple, margem: float = 0.002) -> tuple:
    """Só os furos que cabem no contorno (com `margem` às bordas e aos furos já aceites) — o mesmo desenho serve placas
    de outros tamanhos (os frames de 500 mm e de 5″ do catálogo) sem furos a sair da peça."""
    aceites, caixas = [], []
    n = len(contorno)
    for f in furos:
        if not all(_no_poligono(x, y, contorno) for x, y in f):
            continue
        if min(_dist_segmento(x, y, contorno[i], contorno[(i + 1) % n]) for x, y in f for i in range(n)) < margem:
            continue
        xs, ys = [p[0] for p in f], [p[1] for p in f]
        cx = (min(xs) - margem, max(xs) + margem, min(ys) - margem, max(ys) + margem)
        if any(cx[0] < c[1] and c[0] < cx[1] and cx[2] < c[3] and c[2] < cx[3] for c in caixas):
            continue
        aceites.append(f)
        caixas.append(cx)
    return tuple(aceites)


def _tubo_do_frame(hw):
    """Raio do tubo dos braços a partir do catálogo («tubo de carbono 25×23 mm», «… 16 mm»); `None` = braços em placa
    (frames de corrida de 5″); sem número, 16 mm (os X500/Tarot 650 usam tubo de 16 mm)."""
    texto = f"{getattr(hw.frame, 'modelo', '')} {hw.frame.dados.get('modelo', '')}"
    m = re.search(r"tubo de carbono (\d+(?:[.,]\d+)?)", texto)
    if m:
        return 0.5 * float(m.group(1).replace(",", ".")) / 1000.0
    if hw.frame.wheelbase < 0.30:
        return None
    return 0.008


# ------------------------------------------------------------------ transformações
def _rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


R_PERFIL_XZ = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]])   # perfil (x, y) → plano xz, extrusão → +y
R_PONTEIRO = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])   # perfil (x, y) → xz, espessura → −y


@functools.cache
def _r_eixo_t(u: tuple):
    u = np.asarray(u, float) / np.linalg.norm(u)
    v = np.array([-u[1], u[0], 0.0])           # z × u
    s, c = float(np.linalg.norm(v)), float(u[2])
    if s < 1e-12:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * K + (1 - c) * (K @ K)


def _r_eixo(u):
    """Rotação que leva o z local à direção `u`."""
    return _r_eixo_t(tuple(round(float(x), 9) for x in u))


# ============================================================================ materiais


def _obter_material(ctx, nome: str):
    """O OBJETO do material, procurado na LISTA `spec.materials` (no 3.15 `spec.material(nome)` devolve None para
    materiais acrescentados depois de um `spec.delete` — o `apagar` de qualquer módulo)."""
    obter = getattr(ctx, "obter_material", None)
    if obter is not None:
        return obter(nome)
    return next((m for m in ctx.spec.materials if m.name == nome), None)


def _textura_carbono(ctx) -> str:
    """Carbono 3K tafetá: textura EMBUTIDA (xadrez 2 × 2 com a aresta de cada mecha marcada) — o `to_xml` exporta-a."""
    nome = "est_carbono_3k"
    if not any(t.name == nome for t in ctx.spec.textures):
        ctx.spec.add_texture(name=nome, type=mujoco.mjtTexture.mjTEXTURE_2D,
                             builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
                             width=64, height=64, rgb1=[0.095, 0.095, 0.105], rgb2=[0.15, 0.15, 0.162],
                             mark=mujoco.mjtMark.mjMARK_EDGE, markrgb=[0.065, 0.065, 0.07])
    return nome


_MATERIAIS = {
    "carbono": ([1.0, 1.0, 1.0, 1.0], {"specular": 0.55, "shininess": 0.75, "texrepeat": [1.0, 1.0]}, True),
    "carbono_liso": ([0.10, 0.10, 0.11, 1.0], {"specular": 0.6, "shininess": 0.8}, False),
    "alu_preto": ([0.10, 0.10, 0.11, 1.0], {"specular": 0.45, "shininess": 0.55}, False),
    "alu_natural": ([0.66, 0.68, 0.71, 1.0], {"specular": 0.75, "shininess": 0.7}, False),
    "alu_laranja": ([0.96, 0.42, 0.04, 1.0], {"specular": 0.6, "shininess": 0.6}, False),
    "alu_vermelho": ([0.78, 0.12, 0.13, 1.0], {"specular": 0.6, "shininess": 0.6}, False),
    "aco": ([0.62, 0.64, 0.67, 1.0], {"specular": 0.9, "shininess": 0.9}, False),
    "aco_preto": ([0.16, 0.16, 0.17, 1.0], {"specular": 0.7, "shininess": 0.8}, False),
    "sextavado": ([0.02, 0.02, 0.02, 1.0], {"specular": 0.1, "shininess": 0.1}, False),
    "bronze": ([0.74, 0.52, 0.24, 1.0], {"specular": 0.75, "shininess": 0.7}, False),
    "servo_metal": ([0.075, 0.075, 0.085, 1.0], {"specular": 0.35, "shininess": 0.45}, False),
    "servo_plastico": ([0.12, 0.12, 0.13, 1.0], {"specular": 0.12, "shininess": 0.2}, False),
    "branco": ([0.93, 0.93, 0.91, 1.0], {"specular": 0.2, "shininess": 0.3}, False),
    "etiqueta": ([0.52, 0.54, 0.57, 1.0], {"specular": 0.45, "shininess": 0.5}, False),
    "vermelho": ([0.92, 0.06, 0.05, 1.0], {"specular": 0.4, "shininess": 0.5, "emission": 0.25}, False),
    "borracha": ([0.05, 0.05, 0.055, 1.0], {"specular": 0.05, "shininess": 0.1}, False),
    "pcb": ([0.06, 0.36, 0.17, 1.0], {"specular": 0.35, "shininess": 0.5}, False),
    "iman": ([0.45, 0.46, 0.50, 1.0], {"specular": 0.8, "shininess": 0.8}, False),
    "acrilico": ([0.78, 0.88, 0.96, 0.22], {"specular": 0.9, "shininess": 0.95}, False),
    "conector": ([0.94, 0.91, 0.80, 1.0], {"specular": 0.2, "shininess": 0.3}, False),
    "chip": ([0.03, 0.03, 0.03, 1.0], {"specular": 0.3, "shininess": 0.4}, False),
}


def _materiais(ctx) -> dict:
    tex = _textura_carbono(ctx)
    nomes = {}
    for chave, (rgba, kw, com_textura) in _MATERIAIS.items():
        nome = f"est_{chave}"
        existia = _obter_material(ctx, nome) is not None
        ctx.material(nome, rgba, **kw)
        if com_textura and not existia:
            _obter_material(ctx, nome).textures[int(mujoco.mjtTextureRole.mjTEXROLE_RGB)] = tex
        nomes[chave] = nome
    return nomes


class _Montador(_Lotes):
    """Os lotes FINAIS (etiqueta = nome do corpo) + a criação das malhas e geoms."""

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.mat = _materiais(ctx)
        self.pos_corpo: dict[str, list] = {}

    def origem(self, corpo: str) -> np.ndarray:
        """Posição dos geoms de malha do corpo (no `drone` = p(0, 0, 0): as peças desenham-se nominais)."""
        return np.asarray(self.pos_corpo.get(corpo, [0.0, 0.0, 0.0]), float)

    def colocar(self, conjunto: tuple, corpos: dict, R, origens: dict):
        """Põe um conjunto canónico congelado: etiqueta → corpo, com a rotação/espelho R e a origem de cada etiqueta."""
        for (etq, material), V, F, T in conjunto:
            self.junta(corpos[etq], material, (V, F, T), R, origens.get(etq))

    def criar(self):
        for (corpo, material), m in self.malhas.items():
            if not m.n:
                continue
            v, f, t = m.arrays()
            nome = f"est_{corpo}_{material}"
            _malha_no_spec(self.ctx, f"m_{nome}", v, f, t)
            self.ctx.geom(corpo, nome, type=mujoco.mjtGeom.mjGEOM_MESH, meshname=f"m_{nome}",
                          material=self.mat[material], pos=list(self.origem(corpo)))


def _malha_no_spec(ctx, nome: str, v, f, t):
    me = ctx.spec.add_mesh(name=nome)
    me.uservert = v.ravel().tolist()
    me.userface = f.ravel().tolist()
    me.usertexcoord = t.ravel().tolist()
    me.inertia = mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL     # massa 0: a inércia nunca conta, assim não falha
    return me


def _reestilizar_malha(ctx, g, nome_malha: str, parte, material: str):
    """Um geom VISUAL que já existia (o nome fica) passa a ser uma malha nossa (massa 0, sem contacto, grupo 3)."""
    _malha_no_spec(ctx, nome_malha, *parte)
    g.type = mujoco.mjtGeom.mjGEOM_MESH
    g.meshname = nome_malha
    g.material = material


# ============================================================================ peças reutilizáveis


def _parafuso(lt, etq, p, eixo, d=0.0055, k=0.003, s=0.0025, material="aco_preto"):
    """Cabeça de parafuso de sextavado interior (ISO 4762) com o sextavado escuro; `eixo` = para fora da peça."""
    R = _r_eixo(eixo)
    lt.junta(etq, material, _cilindro(round(0.5 * d, 7), 0.0, round(k, 7), n=12), R, p)
    lt.junta(etq, "sextavado", _hexagono(round(0.5 * s, 7), round(k - 0.0006, 7), round(k + 0.00015, 7)), R, p)


def _servo_xh430(lt, etq, R, p, rotulos=(True, True)):
    """DYNAMIXEL XH430 no referencial do servo: x = altura (horn perto de +x), y = largura, z = profundidade (horn na
    face −z, idler na +z); origem no EIXO do horn, na face do horn. `R`, `p` levam-no ao referencial do conjunto."""
    W, H, D = SERVO_W, SERVO_H, SERVO_D
    x0, x1 = HORN_TOPO - H, HORN_TOPO
    xc = 0.5 * (x0 + x1)
    pc = p + R @ np.array([xc, 0.0, 0.0])
    for (za, zb), mat in (((0.0, 0.0068), "servo_metal"), ((0.0072, 0.0268), "servo_metal"),
                          ((0.0272, D), "servo_plastico")):       # frente e meio metálicos, trás em plástico (sulcos)
        lt.junta(etq, mat, _prisma(round(0.5 * H, 7), round(0.5 * W, 7), 0.0022, 3, za, zb, 0.0005), R, pc)
    lt.junta(etq, "servo_metal", _prisma(round(0.5 * H - 0.0006, 7), round(0.5 * W - 0.0006, 7), 0.0018, 3, 0.0066,
                                         0.0274, 0.0), R, pc)
    lt.junta(etq, "alu_natural", _cilindro(HORN_R, -HORN_E, 0.0, n=28), R, p)          # horn
    for i in range(8):                                                                # 8 furos M2,5 em PCD 16
        a = 2 * math.pi * i / 8 + math.pi / 8
        lt.junta(etq, "sextavado", _cilindro(0.00115, -0.00025, 0.0, n=6), R,
                 p + R @ np.array([0.008 * math.cos(a), 0.008 * math.sin(a), -HORN_E - 0.0001]))
    lt.junta(etq, "aco", _cilindro(0.0021, -0.0004, 0.0, n=12), R, p + R @ np.array([0.0, 0.0, -HORN_E]))
    lt.junta(etq, "alu_natural", _cilindro(0.0085, D, D + 0.0018, n=24), R, p)          # idler
    lt.junta(etq, "servo_plastico", _anel(0.0105, 0.0085, D, D + 0.0008, n=24), R, p)
    for sx_ in (-1, 1):                                                               # parafusos M2 da tampa de trás
        for sy_ in (-1, 1):
            q = np.array([xc + sx_ * (0.5 * H - 0.0028), sy_ * (0.5 * W - 0.0028), D])
            lt.junta(etq, "aco_preto", _cilindro(0.0016, 0.0, 0.0006, n=8), R, p + R @ q)
    for lado, ativo in zip((1.0, -1.0), rotulos, strict=True):                        # etiquetas laterais
        if ativo:
            q = np.array([xc - 0.003, lado * (0.5 * W + 0.0001), 0.5 * D + 0.001])
            lt.junta(etq, "etiqueta", _caixa(0.0095, 0.00012, 0.0065, r=0.0008, bisel=0.0), R, p + R @ q)
    for lado in (-1.0, 1.0):                         # 2 conectores JST EH de 4 vias (RS-485) no topo longe do horn
        lt.junta(etq, "conector", _caixa(0.0028, 0.0060, 0.0029, r=0.0005, bisel=0.0002), R,
                 p + R @ np.array([x0 - 0.0028, lado * 0.0068, 0.0262]))


def _escala(lt, etq, R, p, angulos, r0, r_menor, r_maior, maiores, largura=0.0008, n_arco=8):
    """Escala de traços brancos no plano xz do referencial R (normal ±y); o ângulo mede-se a partir de −x, positivo
    para +z (o sentido em que a junta roda o ponteiro com q > 0)."""
    for ang in angulos:
        a = math.radians(ang)
        r1 = r_maior if ang in maiores else r_menor
        d = np.array([-math.cos(a), 0.0, math.sin(a)])
        Rt = R @ np.column_stack([d, [0.0, 1.0, 0.0], np.cross(d, [0.0, 1.0, 0.0])])
        lt.junta(etq, "branco", _caixa(0.5 * (r1 - r0), 0.00015, 0.5 * largura, r=0.0, bisel=0.0), Rt,
                 p + R @ (d * 0.5 * (r0 + r1)))
    a0, a1 = math.radians(min(angulos)), math.radians(max(angulos))
    for i in range(n_arco):                         # o arco da escala
        aa, bb = a0 + (a1 - a0) * i / n_arco, a0 + (a1 - a0) * (i + 1) / n_arco
        pa = np.array([-math.cos(aa), 0.0, math.sin(aa)]) * r0
        pb = np.array([-math.cos(bb), 0.0, math.sin(bb)]) * r0
        d = pb - pa
        comp = float(np.linalg.norm(d))
        d /= comp
        Rt = R @ np.column_stack([d, [0.0, 1.0, 0.0], np.cross(d, [0.0, 1.0, 0.0])])
        lt.junta(etq, "branco", _caixa(0.5 * comp + 0.0002, 0.00015, 0.00035, r=0.0, bisel=0.0), Rt,
                 p + R @ (0.5 * (pa + pb)))


def _ponteiro(lt, etq, R, p, r0, r1, espessura=0.0008):
    """Ponteiro vermelho em cunha a apontar para −x (no plano xz do referencial R), com a espessura para −y."""
    pts = ((-r1, 0.0), (-r0, 0.0016), (-r0 + 0.002, 0.0011), (-r0 + 0.002, -0.0011), (-r0, -0.0016))
    perfil = _extrusao(tuple((round(x, 7), round(y, 7)) for x, y in pts), (), 0.0, espessura)
    lt.junta(etq, "vermelho", perfil, R @ R_PONTEIRO, p)


def _tubo(lt, etq, u, r0, r1, z=0.0, raio=TUBO_R, n=24):
    """Tubo de carbono ao longo de `u` (no plano xy) de r0 a r1 a partir da origem, eixo à altura z."""
    lt.junta(etq, "carbono", _cilindro(raio, round(r0, 7), round(r1, 7), n=n), _r_eixo((u[0], u[1], 0.0)),
             np.array([0.0, 0.0, z]))


def _bloco_ao_longo(lt, etq, material, centro, u, comp, larg, z0, z1, r=0.002, bisel=0.0008):
    """Bloco maquinado (abraçadeira) orientado segundo `u` (xy), de z0 a z1."""
    lt.junta(etq, material, _caixa(0.5 * comp, 0.5 * larg, 0.5 * (z1 - z0), r=r, bisel=bisel),
             _rot_z(math.atan2(u[1], u[0])), np.asarray(centro, float) + np.array([0.0, 0.0, 0.5 * (z0 + z1)]))


def _face_garfo(r_olho, z_topo, rc=0.003, n_arco=14, n_canto=4):
    """Contorno da face do garfo no plano (c, z), anti-horário: meia-lua de raio `r_olho` à volta do eixo (por baixo)
    e os dois lados até ao topo, com os cantos de cima arredondados."""
    pts = [(r_olho, 0.0), (r_olho, z_topo - rc)]
    for i in range(1, n_canto + 1):
        a = 0.5 * math.pi * i / n_canto
        pts.append((r_olho - rc + rc * math.cos(a), z_topo - rc + rc * math.sin(a)))
    pts.append((-r_olho + rc, z_topo))
    for i in range(1, n_canto + 1):
        a = 0.5 * math.pi + 0.5 * math.pi * i / n_canto
        pts.append((-r_olho + rc + rc * math.cos(a), z_topo - rc + rc * math.sin(a)))
    pts.append((-r_olho, 0.0))
    for i in range(1, n_arco):
        a = math.pi + math.pi * i / n_arco
        pts.append((r_olho * math.cos(a), r_olho * math.sin(a)))
    return tuple((round(x, 7), round(y, 7)) for x, y in pts)


# ============================================================================ conjuntos canónicos (em cache)


@functools.cache
def _perna_canonica(r_perna: float, z_tubo: float, z_fundo: float, r_t: float = TUBO_R) -> tuple:
    """Trem de pouso no referencial do braço (+x ao longo do braço): abraçadeira em T no tubo (raio `r_t`), perna de
    carbono Ø12 e pé de borracha com o fundo no ponto de contacto da cápsula física (`z_fundo`)."""
    lt = _Lotes()
    c = np.array([r_perna, 0.0, 0.0])
    z_b0, z_b1 = z_tubo - r_t - 0.006, z_tubo + r_t + 0.0025
    _bloco_ao_longo(lt, "p", "alu_preto", c, (1.0, 0.0), 0.030, 2 * r_t + 0.009, z_b0, z_b1, r=0.003)
    for s in (-1, 1):
        _parafuso(lt, "p", c + np.array([s * 0.009, 0.0, z_b1]), (0, 0, 1))
    z_pe = z_fundo + 0.0085
    lt.junta("p", "carbono_liso", _cilindro(PERNA_R, round(z_pe, 7), round(z_b0 + 0.0005, 7), n=16), None, c)
    lt.junta("p", "alu_preto", _cilindro(0.0082, round(z_pe + 0.004, 7), round(z_pe + 0.012, 7), n=16), None, c)
    lt.junta("p", "borracha", _elipsoide(0.0115, 0.0115, 0.0085), None, c + np.array([0.0, 0.0, z_pe]))
    return lt.congelar()


@functools.cache
def _braco_rigido_canonico(braco: float, z: float, esp: float, r_t, r_canto: float) -> tuple:
    """Braço do build rígido no referencial do braço (+x para fora, origem no centro da placa): tubo de raio `r_t` (ou
    braço em placa de carbono, `r_t=None`), abraçadeira do canto da placa (o chanfro a `r_canto`), suporte do motor que
    abraça a ponta do tubo e abraçadeira em cruz das treliças."""
    lt = _Lotes()
    if r_t is None:                           # frame de corrida: braço em placa 22 × 5 mm, motor por cima
        lt.junta("d", "carbono", _caixa(0.5 * (braco + 0.018), 0.011, 0.0025, r=0.004, bisel=0.0005), None,
                 np.array([0.5 * (braco + 0.018), 0.0, 0.0]))
        for s_r in (0.6 * r_canto, 0.85 * r_canto):
            _parafuso(lt, "d", np.array([s_r, 0.0, 0.0025]), (0, 0, 1), d=0.0045, k=0.0015, s=0.002)
        return lt.congelar()
    d_t = 2.0 * r_t
    _tubo(lt, "d", (1.0, 0.0), r_canto - 0.012, braco + 0.022, z, raio=r_t)
    comp = 2.4 * d_t
    c0 = r_canto + 0.005
    _bloco_ao_longo(lt, "d", "alu_preto", (c0, 0.0, 0.0), (1.0, 0.0), comp, d_t + 0.015, z - r_t - 0.004, esp + 0.004,
                    r=0.004)
    for s_l in (-1, 1):
        for s_r in (c0 - 0.33 * comp, c0 + 0.33 * comp):
            _parafuso(lt, "d", np.array([s_r, s_l * (0.5 * d_t + 0.001), esp + 0.004]), (0, 0, 1))
    _bloco_ao_longo(lt, "d", "alu_preto", (braco, 0.0, 0.0), (1.0, 0.0), d_t + 0.027, d_t + 0.009, z - r_t - 0.002,
                    z + r_t, r=0.004)
    for s_l in (-1, 1):
        _parafuso(lt, "d", np.array([braco, s_l * (0.5 * d_t + 0.0045), z - 0.004]), (0, s_l, 0))
    c = 0.34 * braco
    if c - 0.5 * (d_t + 0.001) > c0 + 0.5 * comp:
        _bloco_ao_longo(lt, "d", "alu_preto", (c, 0.0, 0.0), (1.0, 0.0), d_t + 0.001, d_t + 0.011, z - r_t - 0.004,
                        z + r_t + 0.004, r=0.004)
        _parafuso(lt, "d", np.array([c, 0.0, z + r_t + 0.004]), (0, 0, 1))
    return lt.congelar()


@functools.cache
def _ombro_canonico(l1: float, z_sup: float, esp: float, mao: int) -> tuple:
    """OMBRO do braço 1 no referencial canónico (a, b, z) com origem no eixo: etiqueta «fixo» (corpo `drone`) e
    «movel» (corpo `braco{k}`). Ver o docstring do módulo."""
    lt = _Lotes()
    F, Mv = "fixo", "movel"
    zb0, zb1 = -0.014, z_sup - PLACA_SUP_E
    a0, a1 = -0.024, 0.012
    b_c = -0.028                              # plano médio da coroa, do sem-fim e do servo (para dentro, em −b)
    a_w = -ENTRE_EIXOS                        # eixo vertical do sem-fim
    paredes_b = ((-0.041, -0.037), (-0.019, -0.015))
    # ---------------- caixa do redutor (alumínio): paredes dos rolamentos 6800, fundo, tampa, costas e janelas
    janela_b = _poligono_arred(((-0.0127, -0.0105), (-0.0127, 0.0105), (-0.0215, 0.0105), (-0.0215, -0.0105)), 0.0015)
    ext_parede = _poligono_arred(((a1, zb0), (a1, zb1), (a0, zb1), (a0, zb0)), 0.002)
    alojamento = _circulo(0.0, 0.0, ROL6800[1] - 0.0002, n=24)
    for i_p, (bb0, bb1) in enumerate(paredes_b):
        furos = (alojamento, janela_b) if i_p == 0 else (alojamento,)
        lt.junta(F, "alu_natural", _extrusao(ext_parede, furos, bb0, bb1), R_PERFIL_XZ)
        lt.junta(F, "aco", _anel(ROL6800[1], ROL6800[1] - 0.0016, bb0 - 0.0002, bb1 + 0.0002, n=24), R_PERFIL_XZ)
        lt.junta(F, "aco_preto", _anel(ROL6800[1] - 0.0016, ROL6800[0] + 0.0016, bb0 + 0.0003, bb1 - 0.0003, n=24),
                 R_PERFIL_XZ)
    lt.junta(F, "acrilico", _extrusao(janela_b, (), paredes_b[0][0] + 0.0012, paredes_b[0][0] + 0.0027), R_PERFIL_XZ)
    lt.junta(F, "alu_natural", _caixa(0.5 * (a1 - a0), 0.009, 0.0015, r=0.001, bisel=0.0003),
             None, np.array([0.5 * (a0 + a1), b_c, zb0 + 0.0015]))
    tampa = _extrusao(_poligono_arred(((a1, -0.037), (a1, -0.019), (a0, -0.019), (a0, -0.037)), 0.001),
                      (_circulo(a_w, b_c, 0.0055, n=16),), round(zb1 - 0.003, 7), round(zb1, 7))
    lt.junta(F, "alu_natural", tampa)
    lt.junta(F, "alu_natural", _caixa(0.0015, 0.009, 0.5 * (zb1 - zb0) - 0.003, r=0.0, bisel=0.0003),
             None, np.array([a0 + 0.0015, b_c, 0.5 * (zb0 + zb1)]))
    lt.junta(F, "acrilico", _caixa(0.00075, 0.009, 0.5 * (zb1 - zb0) - 0.003, r=0.0, bisel=0.0),
             None, np.array([a1 - 0.0009, b_c, 0.5 * (zb0 + zb1)]))
    for bb in (-0.0355, -0.0205):            # parafusos M2,5 da janela da frente
        for zz in (zb0 + 0.0045, zb1 - 0.0045):
            _parafuso(lt, F, np.array([a1, bb, zz]), (1, 0, 0), d=0.0045, k=0.0012, s=0.002)
    lt.junta(F, "alu_natural", _caixa(0.006, 0.011, 0.0015, r=0.002, bisel=0.0004), None,
             np.array([a0 - 0.005, b_c, esp + 0.0015]))                   # aba de fixação na placa de baixo
    for bb in (-0.0345, -0.0215):
        _parafuso(lt, F, np.array([a0 - 0.0065, bb, esp + 0.003]), (0, 0, 1), k=0.0025)
    # ---------------- sem-fim (fixo: no simulador o rotor do servo não roda), veio, rolamentos 685, acoplamento
    lt.junta(F, "aco", _rosca(0.005, 0.0068, round(math.pi * SEMFIM_M, 7), -0.0085, 0.0085, mao), None,
             np.array([a_w, b_c, 0.0]))
    lt.junta(F, "aco", _cilindro(0.0025, round(zb0 + 0.0005, 7), round(zb1 + 0.0035, 7), n=12), None,
             np.array([a_w, b_c, 0.0]))
    for zz in (zb0 + 0.0015, zb1 - 0.0015):
        lt.junta(F, "aco_preto", _anel(0.0055, 0.0026, round(zz - 0.0013, 7), round(zz + 0.0013, 7), n=16), None,
                 np.array([a_w, b_c, 0.0]))
    lt.junta(F, "alu_natural", _cilindro(0.005, round(zb1, 7), round(zb1 + 0.0029, 7), n=16), None,
             np.array([a_w, b_c, 0.0]))
    # ---------------- servo do ombro deitado na placa de cima, horn para baixo no eixo do sem-fim, em 4 pilares
    z_frente = z_sup + PLACA_SUP_E + 0.003
    _servo_xh430(lt, F, np.eye(3), np.array([a_w, b_c, z_frente]))
    for aa, bb in ((-0.0445, -0.0385), (-0.0445, -0.0175), (-0.004, -0.040), (-0.004, -0.016)):
        lt.junta(F, "alu_natural", _cilindro(0.002, round(z_sup + PLACA_SUP_E, 7), round(z_frente, 7), n=12), None,
                 np.array([aa, bb, 0.0]))
    # ---------------- encoder AS5048A na ponta de dentro do veio: placa 28 × 22 mm de pé em 4 pilares
    b_pcb0, b_pcb1 = -0.0505, -0.0489
    lt.junta(F, "pcb", _caixa(0.011, 0.0008, 0.0138, r=0.0012, bisel=0.0), None,
             np.array([0.0015, 0.5 * (b_pcb0 + b_pcb1), 0.0]))
    lt.junta(F, "chip", _caixa(0.0025, 0.0006, 0.0022, r=0.0, bisel=0.0), None, np.array([0.0, b_pcb1 + 0.0006, 0.0]))
    lt.junta(F, "conector", _caixa(0.0028, 0.0025, 0.005, r=0.0004, bisel=0.0002), None,
             np.array([0.0098, b_pcb0 - 0.0025, 0.0075]))
    for aa in (-0.0070, 0.0100):
        for zz in (-0.0112, 0.0112):
            lt.junta(F, "alu_natural", _cilindro(0.002, 0.0, round(-0.041 - b_pcb1, 7), n=10), _r_eixo((0, -1, 0)),
                     np.array([aa, -0.041, zz]))
            _parafuso(lt, F, np.array([aa, b_pcb0, zz]), (0, -1, 0), d=0.0045, k=0.0015, s=0.002)
    # ---------------- escala −40…+40° na face exterior da caixa (do lado do cubo)
    _escala(lt, F, np.diag([1.0, -1.0, 1.0]), np.array([0.0, paredes_b[1][1] + 0.00016, 0.0]),
            (-40, -30, -20, -10, 0, 10, 20, 30, 40), 0.0165, 0.0195, 0.0210, (-40, -20, 0, 20, 40))
    # ======== peças que RODAM com o ombro
    Ry = _r_eixo((0, 1, 0))
    lt.junta(Mv, "aco", _cilindro(0.005, -0.042, 0.0105, n=20), Ry)                     # veio Ø10
    lt.junta(Mv, "aco", _cilindro(0.004, -0.0438, -0.042, n=16), Ry)                    # suporte do íman
    lt.junta(Mv, "iman", _cilindro(0.003, -0.0463, -0.0438, n=16), Ry)                  # íman diametral Ø6
    lt.junta(Mv, "bronze", _engrenagem(COROA_Z, SEMFIM_M, round(b_c - 0.0032, 7), round(b_c + 0.0032, 7), 0.005), Ry)
    for z0_, z1_ in ((b_c - 0.0052, b_c - 0.0032), (b_c + 0.0032, b_c + 0.0052)):
        lt.junta(Mv, "bronze", _anel(0.0065, 0.005, round(z0_, 7), round(z1_, 7), n=20), Ry)
    r_cubo = round(min(0.0145, zb1 - 0.0005), 7)      # o topo do cubo fica abaixo da placa de cima em qualquer ângulo
    lt.junta(Mv, "alu_laranja", _prisma(r_cubo, r_cubo, r_cubo, 7, -0.014, 0.011, 0.0008), Ry)
    u = np.array(U45)
    lt.junta(Mv, "alu_laranja", _prisma(0.0155, 0.0155, 0.0155, 7, 0.006, 0.042, 0.0008), _r_eixo(U45))
    for s in (0.020, 0.034):
        _parafuso(lt, Mv, s * u + np.array([0, 0, 0.0155]), (0, 0, 1))
    _parafuso(lt, Mv, np.array([0.0, 0.011, 0.0]), (0, 1, 0), d=0.007, k=0.004, s=0.004)
    _ponteiro(lt, Mv, np.diag([1.0, -1.0, 1.0]), np.array([0.0, -0.0142, 0.0]), 0.0135, 0.0215, espessura=0.0009)
    _tubo(lt, Mv, U45, 0.030, l1 - 0.058)
    return lt.congelar()


@functools.cache
def _cotovelo_canonico(z_suporte: float) -> tuple:
    """COTOVELO do braço 1, canónico (c, d, z) com origem no eixo: etiqueta «braco» (servo, berço, ponteira, escala —
    no corpo `braco{k}`, deslocados para a ponta) e «mastro» (garfo, ponteiro, abraçadeiras, tubo — `mastro{k}`)."""
    lt = _Lotes()
    B, Ms = "braco", "mastro"
    hd = 0.5 * SERVO_D
    # servo: x do servo = +c (horn perto do topo +c), y = −z, z = +d (horn na face −d, idler na +d)
    R_s = np.column_stack([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])
    _servo_xh430(lt, B, R_s, np.array([0.0, -hd, 0.0]))
    # berço (alumínio preto) por baixo do servo, ligado à ponteira do tubo
    zb1 = -0.5 * SERVO_W
    berco = ((0.010, -0.0165), (0.010, 0.0165), (-0.0365, 0.0165), (-0.0365, -0.0165), (-0.0335, -0.0165),
             (-0.0615, -0.0445), (-0.0445, -0.0615), (0.0005, -0.0165))
    lt.junta(B, "alu_preto", _extrusao(_poligono_arred(berco, 0.002), (), round(zb1 - 0.003, 7), round(zb1, 7)))
    u = np.array(U45)
    lt.junta(B, "alu_preto", _caixa(0.020, 0.016, 0.017, r=0.004, bisel=0.0008), _rot_z(math.pi / 4),
             -0.072 * u + np.array([0.0, 0.0, -0.0005]))
    for s in (-0.080, -0.064):
        _parafuso(lt, B, s * u + np.array([0, 0, 0.0165]), (0, 0, 1))
    # escala −45…+45° na face do horn, fora do raio do garfo
    _escala(lt, B, np.eye(3), np.array([0.0, -hd - 0.00016, 0.0]), (-45, -30, -15, 0, 15, 30, 45), 0.0152, 0.0178,
            0.0190, (-45, 0, 45))
    # ======== garfo que RODA com o cotovelo, aparafusado ao horn (−d) e ao idler (+d)
    z_ponte, r_olho = 0.048, 0.0135
    face = _face_garfo(r_olho, z_ponte + 0.004)
    furo = _rasgo(0.0, 0.029, 0.008, 0.0045, ang=math.pi / 2)
    for d0, d1 in ((-hd - HORN_E - 0.003, -hd - HORN_E), (hd + 0.0018, hd + 0.0048)):
        lt.junta(Ms, "alu_laranja", _extrusao(face, (furo,), round(d0, 7), round(d1, 7)), R_PERFIL_XZ)
        d_ext, sinal = (d0, -1.0) if d0 < 0 else (d1, 1.0)
        for i in range(4):
            a = math.pi / 4 + i * math.pi / 2
            _parafuso(lt, Ms, np.array([0.008 * math.cos(a), d_ext, 0.008 * math.sin(a)]), (0, sinal, 0),
                      d=0.0045, k=0.0015, s=0.002)
    lt.junta(Ms, "alu_laranja", _caixa(r_olho, hd + 0.0053, 0.004, r=0.002, bisel=0.0006), None,
             np.array([0.0, -0.00035, z_ponte]))
    _ponteiro(lt, Ms, np.eye(3), np.array([0.0, -hd - HORN_E - 0.0032, 0.0]), 0.012, 0.0185)
    z_c0, z_top = z_ponte + 0.004, z_suporte - 0.0025
    lt.junta(Ms, "alu_preto", _cilindro(0.0125, round(z_c0, 7), round(z_c0 + 0.016, 7), n=24))
    _parafuso(lt, Ms, np.array([0.0125, 0.0, z_c0 + 0.008]), (1, 0, 0))
    lt.junta(Ms, "carbono", _cilindro(MASTRO_R, round(z_c0 + 0.004, 7), round(z_top - 0.004, 7), n=20))
    lt.junta(Ms, "alu_preto", _cilindro(0.0125, round(z_top - 0.016, 7), round(z_top, 7), n=24))
    _parafuso(lt, Ms, np.array([0.0125, 0.0, z_top - 0.008]), (1, 0, 0))
    return lt.congelar()


# ============================================================================ frame


@functools.cache
def _desenho_placas(art: bool, L: float, pin1: tuple, bateria: tuple | None, Ls_rigido: float) -> tuple:
    """(contorno, furos) da placa de baixo e da de cima — desenhados para a placa de 208 mm, à escala da placa do build
    e só com os furos que cabem (puro: fica em cache)."""
    if art:
        x_n, y_n = abs(pin1[0]) - 0.025, abs(pin1[1]) - 0.052        # entalhe da caixa do redutor + encoder
        v = [(L, -y_n), (L, y_n), (x_n, y_n), (x_n, L), (-x_n, L), (-x_n, y_n), (-L, y_n), (-L, -y_n),
             (-x_n, -y_n), (-x_n, -L), (x_n, -L), (x_n, -y_n)]
    else:
        c = 0.23 * L
        v = [(L, -L + c), (L, L - c), (L - c, L), (-L + c, L), (-L, L - c), (-L, -L + c), (-L + c, -L), (L - c, -L)]
    ext_b = _poligono_arred(tuple(v), 0.003)
    furos = [_poligono_arred(((0.22 * L, -0.125 * L), (0.22 * L, 0.125 * L), (-0.22 * L, 0.125 * L),
                              (-0.22 * L, -0.125 * L)), 0.048 * L)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            if bateria is not None:                                  # rasgos das cintas da bateria (as do modelo)
                cb, lb = bateria
                furos.append(_rasgo(sx * 0.28 * cb, sy * (0.5 * lb + 0.0065), 0.008, 0.002))
            furos += [_circulo(sx * 0.29 * L, sy * 0.77 * L, 0.067 * L),
                      _circulo(sx * 0.77 * L, sy * 0.29 * L, 0.067 * L)]
    furos_b = _furos_que_cabem(ext_b, tuple(furos))
    janela = _poligono_arred(((0.047, -0.032), (0.047, 0.032), (-0.047, 0.032), (-0.047, -0.032)), 0.006)
    furos = [janela]
    if art:
        Ls = L
        xh, yh = abs(pin1[0]) - 0.020, abs(pin1[1]) - 0.0115       # entalhe do cubo do ombro
        xo = abs(pin1[0]) + 0.0025                                  # orelha que segura o horn do servo
        v = [(xo, -yh), (xo, -0.060), (Ls, -0.060), (Ls, 0.060), (xo, 0.060), (xo, yh), (xh, yh), (xh, Ls),
             (-xh, Ls), (-xh, yh), (-xo, yh), (-xo, 0.060), (-Ls, 0.060), (-Ls, -0.060), (-xo, -0.060), (-xo, -yh),
             (-xh, -yh), (-xh, -Ls), (xh, -Ls), (xh, -yh)]
        for sx in (-1, 1):
            for sy in (-1, 1):                                      # passagem do acoplamento horn → sem-fim
                furos.append(_circulo(sx * (abs(pin1[0]) - ENTRE_EIXOS), sy * (abs(pin1[1]) - 0.028), 0.0128, n=24))
        furos += [_rasgo(sx * 0.072, 0.0, 0.016, 0.007, ang=math.pi / 2) for sx in (-1, 1)]
        furos += [_rasgo(0.0, sy * 0.064, 0.024, 0.007) for sy in (-1, 1)]
        ext_s = _poligono_arred(tuple(v), 0.0025)
    else:
        Ls = Ls_rigido
        c = 0.197 * Ls
        v = [(Ls, -Ls + c), (Ls, Ls - c), (Ls - c, Ls), (-Ls + c, Ls), (-Ls, Ls - c), (-Ls, -Ls + c), (-Ls + c, -Ls),
             (Ls - c, -Ls)]
        furos += [_rasgo(sx * 0.765 * Ls, 0.0, 0.197 * Ls, 0.087 * Ls, ang=math.pi / 2) for sx in (-1, 1)]
        furos += [_rasgo(0.0, sy * 0.678 * Ls, 0.273 * Ls, 0.087 * Ls) for sy in (-1, 1)]
        ext_s = _poligono_arred(tuple(v), 0.003)
    return ext_b, furos_b, ext_s, _furos_que_cabem(ext_s, tuple(furos), 0.003)


def _placas(mt: _Montador, art: bool, L: float, esp: float, pin1):
    """Placa de baixo (malha nova; a de massa fica invisível) e placa de cima (`placa_superior` reestilizada)."""
    ctx = mt.ctx
    gb, g = ctx.geom_existente("bateria"), ctx.geom_existente("placa_superior")
    bateria = (round(2.0 * float(gb.size[0]), 7), round(2.0 * float(gb.size[1]), 7)) if gb is not None else None
    Ls = round(float(g.size[0]), 7) if g is not None else round(0.88 * L, 7)
    ext_b, furos_b, ext_s, furos_s = _desenho_placas(art, round(L, 7), (round(pin1[0], 7), round(pin1[1], 7)),
                                                     bateria, Ls)
    mt.junta("drone", "carbono", _extrusao(ext_b, furos_b, -esp, esp))
    ctx.esconder("placa")
    if g is not None:
        _reestilizar_malha(ctx, g, "m_est_placa_superior", _extrusao(ext_s, furos_s, -PLACA_SUP_E, PLACA_SUP_E),
                           mt.mat["carbono"])


def _espacadores(mt: _Montador, z_sup: float, esp: float, L: float):
    """Os 4 espaçadores `espacador_placa_*` (Ø5 M3) entre as placas, com os parafusos por cima e por baixo (na placa
    grande a 60 mm do centro, longe das abraçadeiras e das caixas do ombro; nas pequenas onde estavam)."""
    ctx = mt.ctx
    z0, z1 = esp, z_sup - PLACA_SUP_E
    a = 0.577 * L if L >= 0.09 else 0.78 * L
    for i, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1)), start=1):
        g = ctx.geom_existente(f"espacador_placa_{i}")
        if g is None:
            continue
        x, y = sx * a, sy * a
        g.size = [0.0025, 0.5 * (z1 - z0), 0.0]
        g.pos = ctx.p(x, y, 0.5 * (z0 + z1))
        _parafuso(mt, "drone", np.array([x, y, z_sup + PLACA_SUP_E]), (0, 0, 1), d=0.0057, k=0.00165)
        _parafuso(mt, "drone", np.array([x, y, -esp]), (0, 0, -1), d=0.0057, k=0.00165)


def _placa_motor(mt: _Montador, nome: str, d_mot: float, pos=None):
    """`suporte_motor_k` (o mesmo nome) passa a placa de motor CNC vermelha com furos de alívio e dos parafusos."""
    ctx = mt.ctx
    g = ctx.geom_existente(nome)
    if g is None:
        return
    r, e = 0.5 * d_mot + 0.0015, float(g.size[1])
    furos = [_circulo(0.0, 0.0, 0.19 * r, n=16)]
    for i in range(4):
        a, b = math.pi / 4 + i * math.pi / 2, i * math.pi / 2
        furos.append(_circulo(0.53 * r * math.cos(a), 0.53 * r * math.sin(a), 0.0017, n=8))
        furos.append(_rasgo(0.78 * r * math.cos(b), 0.78 * r * math.sin(b), 0.15 * r, 0.11 * r, ang=b + math.pi / 2))
    _reestilizar_malha(ctx, g, f"m_est_{nome}", _extrusao(_circulo(0.0, 0.0, r, n=40), tuple(furos), -e, e),
                       mt.mat["alu_vermelho"])
    if pos is not None:
        g.pos = pos


def _dados_perna(mt: _Montador, corpo: str, nome: str):
    """(raio ao longo do braço, z do fundo da cápsula) da perna física, no referencial nominal do corpo."""
    g = mt.ctx.geom_existente(nome)
    if g is None:
        return None
    ft = np.array(g.fromto, float)
    o = mt.origem(corpo)
    a, b = ft[:3] - o, ft[3:] - o
    return round(math.hypot(a[0], a[1]), 7), round(min(a[2], b[2]) - PERNA_R, 7)


def _frame_rigido(mt: _Montador, hw, esp: float, L: float):
    ctx = mt.ctx
    r_t = _tubo_do_frame(hw)
    z = round(0.0025 - r_t, 7) if r_t is not None else 0.0      # topo do tubo a +2,5 mm: a placa do motor assenta aí
    r_canto = (2.0 * L - 0.23 * L) / math.sqrt(2.0)              # o chanfro do canto da placa, ao longo da diagonal
    d_mot = float(hw.motor.dados.get("diametro_mm", 28.0)) / 1000.0
    conj = _braco_rigido_canonico(round(hw.braco, 7), z, round(esp, 7), r_t, round(r_canto, 7))
    topo = z + (r_t if r_t is not None else 0.0025)
    for i, (x, y) in enumerate(hw.pos_rotores):
        k = i + 1
        R = _rot_z(math.atan2(y, x))
        mt.colocar(conj, {"d": "drone"}, R, {})
        perna = _dados_perna(mt, "drone", f"perna{k}")
        if perna is not None:
            mt.colocar(_perna_canonica(perna[0], z, perna[1], r_t if r_t is not None else 0.004), {"p": "drone"}, R, {})
            ctx.esconder(f"perna{k}")
        g = ctx.geom_existente(f"suporte_motor_{k}")
        if g is not None:                      # a placa do motor assenta no topo do tubo (base do motor a +5 mm)
            _placa_motor(mt, f"suporte_motor_{k}", d_mot, pos=ctx.p(x, y, topo + float(g.size[1])))
        if ctx.geom_existente(f"braco{k}") is not None:
            ctx.esconder(f"braco{k}")
    # treliças anti-torção (`trelica_estab_*`, mesmos nomes): varões de carbono de 8 mm ao eixo dos tubos
    o = mt.origem("drone")
    for idx in range(1, 5):
        g = ctx.geom_existente(f"trelica_estab_{idx}")
        if g is None:
            continue
        ft = np.array(g.fromto, float)
        a, b = ft[:3] - o, ft[3:] - o
        a[2] = b[2] = z
        g.fromto = list(ctx.p(*a)) + list(ctx.p(*b))
        g.size = [min(0.004, 0.45 * (r_t if r_t is not None else 0.0055)), 0.0, 0.0]
        g.material = mt.mat["carbono_liso"]


def _mecanismo(mt: _Montador, hw, esp: float, z_sup: float):
    ctx = mt.ctx
    from ..modelo import geometria_bracos
    geo = geometria_bracos(hw)
    r_s, l1 = geo["r_s"], geo["l1"]
    d_mot = float(hw.motor.dados.get("diametro_mm", 28.0)) / 1000.0
    for i, (x, y) in enumerate(hw.pos_rotores):
        k = i + 1
        ang = math.atan2(y, x)
        ux, uy = math.cos(ang), math.sin(ang)
        sx, sy = math.copysign(1.0, ux), math.copysign(1.0, uy)
        M = np.diag([sx, sy, 1.0])
        mao = 1 if sx * sy > 0 else -1      # o espelho troca a mão do filete: assim o sem-fim fica sempre à direita
        P = np.array([r_s * ux, r_s * uy, 0.0])
        mt.colocar(_ombro_canonico(round(l1, 7), round(z_sup, 7), round(esp, 7), mao),
                   {"fixo": "drone", "movel": f"braco{k}"}, M, {"fixo": P})
        gs = ctx.geom_existente(f"suporte_motor_{k}")
        z_suporte = round(float(gs.pos[2]), 7) if gs is not None else round(geo["l_m"] - 0.04, 7)
        mt.colocar(_cotovelo_canonico(z_suporte), {"braco": f"braco{k}", "mastro": f"mastro{k}"}, M,
                   {"braco": l1 * np.array([ux, uy, 0.0])})
        _placa_motor(mt, f"suporte_motor_{k}", d_mot)
        perna = _dados_perna(mt, f"braco{k}", f"perna{k}")
        if perna is not None:
            mt.colocar(_perna_canonica(perna[0], 0.0, perna[1]), {"p": f"braco{k}"}, _rot_z(ang), {})
            ctx.esconder(f"perna{k}")
        for nome in (f"braco{k}_raiz", f"braco{k}_tubo", f"servo_ombro{k}", f"sem_fim{k}", f"servo_cotovelo{k}",
                     f"mastro{k}_tubo"):
            if ctx.geom_existente(nome) is not None:
                ctx.esconder(nome)
        antigos = [f"dobradica_ombro{k}", f"dobradica_cotovelo{k}", f"garfo_cotovelo{k}", f"sem_fim{k}_eixo"]
        antigos += [f"{t}_{j}{k}_{s}" for t in ("corneta", "marca") for j in ("ombro", "cotovelo") for s in ("a", "b")]
        for nome in antigos:
            if ctx.geom_existente(nome) is not None:
                ctx.apagar(nome)


# ============================================================================ entrada


def adicionar(ctx) -> None:
    """Estrutura realista (os dois builds) e, no articulado, o mecanismo dos braços — ver o docstring do módulo."""
    mt = _Montador(ctx)
    mt.pos_corpo["drone"] = ctx.p(0.0, 0.0, 0.0)
    L, _, esp = (float(v) for v in ctx.tamanho_geom("placa"))
    gsup = ctx.geom_existente("placa_superior")
    z_sup = float(np.array(gsup.pos)[2] - mt.origem("drone")[2]) if gsup is not None else esp + 0.014
    pin1 = (0.0, 0.0)
    if ctx.articulado:
        from ..modelo import geometria_bracos
        r_s = geometria_bracos(ctx.hw)["r_s"]
        x, y = ctx.hw.pos_rotores[0]
        a = math.atan2(y, x)
        pin1 = (r_s * math.cos(a), r_s * math.sin(a))
    _placas(mt, ctx.articulado, L, esp, pin1)
    _espacadores(mt, z_sup, esp, L)
    if ctx.articulado:
        _mecanismo(mt, ctx.hw, esp, z_sup)
    else:
        _frame_rigido(mt, ctx.hw, esp, L)
    mt.criar()
