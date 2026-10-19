"""lab/drone_rpi/detalhes/motores.py — MOTORES T-Motor «Antigravity» e HÉLICES de carbono com a forma REAL (só aparência).

Por rotor k = 1..4, no corpo do motor (`drone` nos builds rígidos, `mastro{k}` no articulado), com as medidas do catálogo
(`hw.motor.dados`, `hw.helice`) e das fichas do fabricante; malhas próprias (`spec.add_mesh`, vértices gerados aqui) e
primitivas, TUDO pelo `Contexto.geom` (massa 0, sem contacto; grupo 3 = motor, grupo 1 = hélice, como as pás de sempre).

MOTOR — outrunner T-Motor Antigravity (MN4004 KV300 no build ativo: Φ44,35 × 19 mm, estator Φ40 × 4 mm, 18N24P, veio Φ4,
cabos de 50 mm; MN5006 KV450 no articulado: Φ55,6 × 30 mm, estator Φ50 × 6 mm, 24N28P, veio Φ6, cabos de 60 mm):
  motor{k}                 o cilindro com MASSA e colisão fica, INVISÍVEL (`esconder`): as peças abaixo representam-no todo
  motor{k}_base_cnc        base CNC vazada (suporte do estator), alumínio anodizado preto: anéis de baixo e de cima unidos
                           por 4 colunas (4 janelas laterais de ventilação; a dos cabos virada para o centro do drone),
                           4 braços em X com os furos M3 e o cubo do rolamento — por baixo vêem-se as bobinas
  motor{k}_estator_nucleo  pacote de chapas do estator (coroa interior + sapatas dos dentes)
  motor{k}_estator_cobre   as N bobinas de cobre esmaltado (uma por dente, em cunha, espiras na textura)
  motor{k}_sino_anel       sino (rotor): parede com os ímanes e aba do topo
  motor{k}_sino_aresta     chanfro diamantado (alumínio polido) no rebordo do sino
  motor{k}_raio_1          topo do sino: 6 raios curvos (a ventoinha centrífuga da série) + ressalto de montagem — GIRA
  motor{k}_eixo            veio de aço, e motor{k}_rolamento: face do rolamento de baixo (684 / 686, blindagem ZZ)
  motor{k}_parafusos       4 parafusos M3 de cabeça cilíndrica (sextavado interior) por baixo do suporte, no círculo dos furos
  motor{k}_adaptador       adaptador de hélice (alumínio maquinado) entre o ressalto e o cubo da hélice
  motor{k}_manga           manga termorretrátil na saída dos cabos de fase (na base, virada para o centro do drone)
  motor{k}_fase_{a,b,c}    os 3 cabos de fase (silicone vermelho/preto/azul — as fases a/b/c dos `fio_motor{k}_*`)
  motor{k}_fase_{x}_conector  conector bala de 3,5 mm dourado na ponta de cada cabo — o módulo `fios` liga-se AQUI:
                           ponto = `fromto[3:6]` do geom (no corpo do motor), raio do cabo = `size[0]` de `motor{k}_fase_{x}`

HÉLICE — T-Motor P15×5 CF «polish» no build ativo (381 × 127 mm, 21 g, 2 pás, furo central Φ6 + 2 furos M3 a 12 mm):
  helice{k}                o disco translúcido de sempre (grupo 2) — NÃO é tocado
  helice{k}_cubo           cubo de carbono chanfrado (tecido na textura)
  helice{k}_pa{b}_raiz     pá b, do cubo a 50 % do raio  ┐ forma REAL: pescoço estreito no cubo, corda máxima a ~27 % do
  helice{k}_pa{b}_ponta    pá b, de 50 % do raio à ponta ┘ raio, afunilada (`afunilamento`) até à ponta arredondada, bordo de
                           ataque direito e de fuga curvo, corda média = `corda_media`; torção do passo geométrico
                           θ(r) = atan(P / 2πr) (θ₇₅ = `angulo_passo_75_rad`, limitada a ~23° junto ao cubo); perfil fino
                           arqueado (NACA 4 dígitos, ~4,4 mm de espessura no pescoço → ~0,9 mm na ponta, bordo de fuga rombo);
                           CW e CCW espelhadas; tecido de carbono 3K (xadrez fino) e verniz brilhante («polish»)
  helice{k}_pa{b}_faixa    faixa colorida junto à ponta (CW azul / CCW laranja: identifica o sentido e mostra a rotação)
  helice{k}_tampa          tampa de aperto (alumínio anodizado preto) sobre o cubo
  helice{k}_centro         pino de centragem Φ6 visto no furo da tampa
  helice{k}_parafusos      os 2 parafusos M3 de cabeça cilíndrica no círculo de 12 mm (hélices de aparafusar); nas de furo
                           central (APC, 5″ FPV) é `helice{k}_porca` (porca autoblocante)

O site `r{k}` (a esfera de 1 cm no plano da hélice que o cockpit desenhava por cima da tampa) fica transparente (só
`rgba`). ANIMAÇÃO: `Planta._aplicar_geoms_helices` roda RÍGIDAS em torno do eixo de cada rotor todas as peças `helice{k}_*` e
`motor{k}_raio_*` do corpo do site `r{k}` (menos as de revolução centradas no eixo) — daí estes nomes. Os nomes antigos
pedidos por `valida_real.py` (A6/B10) continuam a existir, agora com a forma real.

Medidas (fichas citadas = dados `untrusted`, só evidência):
  · MN4004 KV300: Φ44,35 × 19 mm, 53 g, 18N24P, veio Φ4 mm, cabo 50 mm — https://store.tmotor.com/product/mn4004-kv300-motor-antigravity-type.html
    e a ficha https://cdn.robotshop.com/media/T/Tmo/RB-Tmo-245/pdf/ligpower_mn4004_kv300_antigravity_ultralight_effic_datasheet.pdf ;
    estator Φ40 × 4 mm e «compatível com todas as hélices de carbono T-Motor ou de furo M6» —
    https://www.getfpv.com/tiger-motor-mn4004-300kv-antigravity-2-black-motors.html ; série com «ventilação e arrefecimento
    próprios» (topo de ventoinha) — https://uav-en.tmotor.com/2018/Antigravity_0402/23.html
  · MN5006 KV450: Φ55,6 × 30 mm, 24N28P, «centrifugal cooling design» — https://store.tmotor.com/product/mn5006-kv450-motor-antigravity-type.html ;
    veio Φ6 mm, cabo 60 mm — https://www.getfpv.com/t-motor-antigravity-mn5006-motor.html ; hélice presa por 2 parafusos
    M3 — https://rcdrone.top/products/src-mn5006-mn5006-antigravity-type-4-6s-uav-motor-kv300
  · P15×5 CF polish: 381 × 127 mm, 21 ± 1,5 g, CF + epóxi — https://store.tmotor.com/product/polish-carbon-fiber-15x5-prop.html ;
    furo central Φ6 + 2 furos M3 a 12 mm — https://www.uavmodel.com/products/tmotor-sanded-matte-p-series-propellers-for-multirotors
    e https://drones.altigator.com/tmotor-carbon-propellers-15x5-v2-p-41445.html ; a pá real (scan laser da T-Motor 15×5 da
    NASA) tem perfil, corda e torção contínuos e bordo de fuga rombo — https://ntrs.nasa.gov/api/citations/20170011320/downloads/20170011320.pdf
  · ESTIMADO (sem número oficial encontrado): círculo dos 4 furos M3 da base (0,56·Φ: 25 mm no MN40xx, ~31 mm no MN50xx),
    alturas internas (base, sino, topo), espessura e Φ do cubo da hélice (0,021·D e 0,06·D), forma da corda (pico a 27 % do
    raio) e o nº de raios do topo (6) — proporções tiradas de fotografias da série, não de desenhos cotados.
"""
from __future__ import annotations

import functools
import math
import re
from dataclasses import dataclass

import mujoco
import numpy as np

_MM = 1e-3
_TAU = 2.0 * math.pi
_GRUPO_HELICE = 1          # pás 3D: o «mostrar_helices» do cockpit (como as de sempre)
_GRUPO_MOTOR = 3           # detalhes: o «fios e detalhes» do cockpit
# texturas: SÓ procedimentais (`builtin` do MuJoCo — o `to_xml` não exporta imagens em memória). O tecido de carbono é um
# xadrez fino de dois pretos (cada casa = um cabo de fibra 3K de ~2 mm; um período = 2 cabos) e as espiras das bobinas o
# mesmo xadrez lido numa só coluna (riscas alternadas de dois tons de cobre, uma por espira).
_CABO_FIBRA = 0.002        # m: largura de um cabo (tow) de fibra 3K
_PERIODO_TECIDO = 2.0 * _CABO_FIBRA
_TEX_CARBONO = np.eye(2)   # casas alinhadas com a envergadura da pá (tecido liso 3K); uma rotação de 45° daria o «bias»
_PASSO_ESPIRA = 0.0007     # m entre espiras visíveis nas bobinas
_CHEIA = 2.5               # expoente da queda da corda depois do pico (pá «cheia» a meio, como as P-series)


# =========================================================================================== medidas
@dataclass(frozen=True)
class _Motor:
    d: float          # Φ exterior do sino (m)
    h: float          # altura total (m)
    ds: float         # Φ do estator
    ts: float         # espessura do pacote de chapas
    n: int            # nº de dentes (bobinas)
    eixo: float       # Φ do veio
    r_furos: float    # raio do círculo dos 4 furos M3 da base (ESTIMADO)
    cabo: float       # comprimento dos cabos de fase


@dataclass(frozen=True)
class _Helice:
    r: float          # raio (m)
    corda: float      # corda média (m)
    afun: float       # afunilamento c_ponta / c_máx
    passo: float      # passo geométrico (m)
    pas: int
    perfil: str       # scimitar_cf | mr_naca | tri_pa_fpv
    r_cubo: float
    h_cubo: float
    fixacao: str      # "parafusos" (2 × M3 a 12 mm) | "porca"


def _dims_motor(motor) -> _Motor:
    dd = motor.dados
    d = float(dd.get("diametro_mm", 28.0)) * _MM
    h = float(dd.get("altura_mm", 0.6 * d / _MM)) * _MM
    m = re.search(r"(\d{2})(\d{2})", f"{motor.modelo} {motor.id}")       # MN4004 → estator Φ40 × 04 mm; 2306 → 23 × 06
    ds, ts = (int(m.group(1)) * _MM, int(m.group(2)) * _MM) if m else (0.9 * d, 0.3 * h)
    ds = min(ds, 0.92 * d)
    ts = min(max(ts, 0.12 * h), 0.30 * h)
    cfg = re.search(r"(\d+)\s*N\s*(\d+)\s*P", f"{dd.get('configuracao', '')} {dd.get('nota', '')}")
    n = int(cfg.group(1)) if cfg else 12
    eixo = float(dd.get("eixo_mm", 4.0 if d < 0.050 else 6.0)) * _MM
    r_furos = 0.5 * min(max(0.56 * d, 0.012), 0.80 * ds)
    cabo = float(dd.get("cabo_mm", 50.0 if d < 0.050 else 60.0)) * _MM
    return _Motor(d, h, ds, ts, max(6, min(n, 36)), eixo, r_furos, cabo)


def _dims_helice(helice) -> _Helice:
    dia = 2.0 * helice.raio
    perfil = str(helice.perfil)
    fixacao = "porca" if perfil != "scimitar_cf" else "parafusos"
    return _Helice(r=float(helice.raio), corda=float(helice.corda_media), afun=float(helice.afunilamento),
                   passo=float(helice.passo), pas=max(int(helice.pas), 2), perfil=perfil,
                   r_cubo=min(max(0.030 * dia, 0.0065), 0.015), h_cubo=min(max(0.021 * dia, 0.005), 0.010),
                   fixacao=fixacao)


# =========================================================================================== malhas
class _Malha:
    """Acumula pedaços FECHADOS de malha: vértices, triângulos (anti-horários vistos de fora) e, se pedido, coordenadas
    de textura. Arestas vivas = vértices próprios de cada face (o MuJoCo não os funde: normais nítidas)."""

    def __init__(self) -> None:
        self._v: list[np.ndarray] = []
        self._f: list[np.ndarray] = []
        self._t: list[np.ndarray] = []
        self._n = 0

    def juntar(self, v, f, t=None, rot_z: float = 0.0, desloc=(0.0, 0.0, 0.0), espelho_y: bool = False,
               espelho_z: bool = False) -> None:
        v = np.array(v, dtype=float).reshape(-1, 3)
        f = np.asarray(f, dtype=np.int64).reshape(-1, 3)
        if espelho_y:
            v[:, 1] *= -1.0
        if espelho_z:
            v[:, 2] *= -1.0
        if espelho_y != espelho_z:                       # um espelho inverte a orientação das faces
            f = f[:, ::-1]
        if rot_z:
            c, s = math.cos(rot_z), math.sin(rot_z)
            v[:, :2] = v[:, :2] @ np.array([[c, s], [-s, c]])
        v += np.asarray(desloc, dtype=float)
        self._v.append(v)
        self._f.append(f + self._n)
        self._t.append(np.zeros((len(v), 2)) if t is None else np.asarray(t, dtype=float).reshape(-1, 2))
        self._n += len(v)

    def saida(self, textura: bool = False, mtex=None) -> tuple:
        v = np.concatenate(self._v)
        f = np.concatenate(self._f)
        t = np.concatenate(self._t) if textura else None
        if t is not None and mtex is not None:
            t = t @ np.asarray(mtex, dtype=float).T
        return (tuple(v.ravel().tolist()), tuple(f.ravel().tolist()),
                None if t is None else tuple(t.ravel().tolist()))


def _revolucao(segmentos, n: int = 48, tex=None):
    """Sólido de revolução em torno de z. `segmentos` = polilinhas (r, z) que, encadeadas, percorrem o perfil no sentido
    ANTI-HORÁRIO (r → direita, z ↑); cada uma tem vértices próprios (aresta viva entre elas); r = 0 vira um só vértice.
    `tex`: None, ou um código por segmento — "p" (projeção plana xy: topos) ou "c" (cilíndrica: paredes; com costura)."""
    v, f, t = [], [], []
    for k_seg, seg in enumerate(segmentos):
        cil = tex is not None and tex[k_seg] == "c"
        m = n + 1 if cil else n                              # a costura da textura cilíndrica duplica a 1.ª coluna
        phi = np.arange(m) * _TAU / n
        cphi, sphi = np.cos(phi), np.sin(phi)
        anel = []
        for r, z in seg:
            if r < 1e-12:
                anel.append([len(v)] * m)
                v.append((0.0, 0.0, z))
                t.append((0.0, 0.0))
            else:
                b = len(v)
                v.extend(zip((r * cphi).tolist(), (r * sphi).tolist(), [z] * m, strict=True))
                if cil:
                    t.extend(zip((phi * r / _PERIODO_TECIDO).tolist(), [z / _PERIODO_TECIDO] * m, strict=True))
                else:
                    t.extend(zip((r * cphi / _PERIODO_TECIDO).tolist(), (r * sphi / _PERIODO_TECIDO).tolist(), strict=True))
                anel.append(list(range(b, b + m)))
        for j in range(len(seg) - 1):
            a, c = anel[j], anel[j + 1]
            for i in range(n):
                i2 = i + 1 if cil else (i + 1) % n
                if a[i] != a[i2]:
                    f.append((a[i], a[i2], c[i2]))
                if c[i2] != c[i]:
                    f.append((a[i], c[i2], c[i]))
    return np.array(v), np.array(f), (np.array(t) if tex is not None else None)


def _setor(r0: float, r1: float, z0: float, z1: float, phi0: float, phi1: float, n: int = 10):
    """Setor de coroa circular (r0..r1, z0..z1, phi0..phi1) fechado: paredes curvas lisas, topos e faces radiais vivas."""
    phi = np.linspace(phi0, phi1, n + 1)
    c, s = np.cos(phi), np.sin(phi)
    v, f = [], []

    def anel(r, z):
        b = len(v)
        v.extend(zip((r * c).tolist(), (r * s).tolist(), [z] * (n + 1), strict=True))
        return b
    for r, sinal in ((r1, 1), (r0, -1)):                     # paredes exterior (+r) e interior (−r)
        b0, b1 = anel(r, z0), anel(r, z1)
        for i in range(n):
            q = (b0 + i, b0 + i + 1, b1 + i + 1, b1 + i)
            tri = [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
            f.extend(tri if sinal > 0 else [x[::-1] for x in tri])
    for z, sinal in ((z1, 1), (z0, -1)):                     # topo (+z) e fundo (−z)
        bi, be = anel(r0, z), anel(r1, z)
        for i in range(n):
            q = (bi + i, be + i, be + i + 1, bi + i + 1)
            tri = [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
            f.extend(tri if sinal > 0 else [x[::-1] for x in tri])
    for i, sinal in ((0, -1), (n, 1)):                       # faces radiais (−φ no início, +φ no fim)
        b = len(v)
        v.extend([(r0 * c[i], r0 * s[i], z0), (r1 * c[i], r1 * s[i], z0), (r1 * c[i], r1 * s[i], z1),
                  (r0 * c[i], r0 * s[i], z1)])
        tri = [(b, b + 1, b + 2), (b, b + 2, b + 3)]
        f.extend(tri if sinal < 0 else [x[::-1] for x in tri])
    return np.array(v), np.array(f)


def _faixa(esq, dir_, z0: float, z1: float):
    """Faixa extrudida entre z0 e z1, limitada pelas polilinhas `esq` e `dir_` (m × 2, mesmo nº de pontos; esquerda/
    direita de quem anda ao longo da faixa): topo, fundo, paredes (suaves ao longo da curva) e topos de início e fim."""
    esq, dir_ = np.asarray(esq, float), np.asarray(dir_, float)
    m = len(esq)
    v, f = [], []

    def pts(lst, z):
        b = len(v)
        v.extend((float(x), float(y), z) for x, y in lst)
        return list(range(b, b + len(lst)))

    for z, cima in ((z1, True), (z0, False)):
        e, d = pts(esq, z), pts(dir_, z)
        for i in range(m - 1):
            tri = [(e[i], d[i], d[i + 1]), (e[i], d[i + 1], e[i + 1])]
            f.extend(tri if cima else [t[::-1] for t in tri])
    for lst, lado in ((dir_, 1), (esq, -1)):
        b0, b1 = pts(lst, z0), pts(lst, z1)
        for i in range(m - 1):
            q = (b0[i], b0[i + 1], b1[i + 1], b1[i]) if lado > 0 else (b0[i + 1], b0[i], b1[i], b1[i + 1])
            f.extend([(q[0], q[1], q[2]), (q[0], q[2], q[3])])
    for i, sinal in ((0, 1), (m - 1, -1)):
        a0, a1 = pts([esq[i], dir_[i]], z0), pts([esq[i], dir_[i]], z1)
        q = (a0[0], a0[1], a1[1], a1[0]) if sinal > 0 else (a0[1], a0[0], a1[0], a1[1])
        f.extend([(q[0], q[1], q[2]), (q[0], q[2], q[3])])
    return np.array(v), np.array(f)


def _caixa(x0: float, x1: float, meia_l: float, z0: float, z1: float):
    """Paralelepípedo ao longo de +x (de x0 a x1, largura 2·meia_l)."""
    return _faixa([(x0, meia_l), (x1, meia_l)], [(x0, -meia_l), (x1, -meia_l)], z0, z1)


def _prisma(poligono, z0: float, z1: float):
    """Prisma reto de um polígono CONVEXO anti-horário (xy): topos em leque, faces laterais com vértices próprios."""
    p = np.asarray(poligono, float)
    k = len(p)
    v, f = [], []
    for z, cima in ((z1, True), (z0, False)):
        b = len(v)
        v.append((float(p[:, 0].mean()), float(p[:, 1].mean()), z))
        v.extend((float(x), float(y), z) for x, y in p)
        for i in range(k):
            t = (b, b + 1 + i, b + 1 + (i + 1) % k)
            f.append(t if cima else t[::-1])
    for i in range(k):
        a, c = p[i], p[(i + 1) % k]
        b = len(v)
        v.extend([(a[0], a[1], z0), (c[0], c[1], z0), (c[0], c[1], z1), (a[0], a[1], z1)])
        f.extend([(b, b + 1, b + 2), (b, b + 2, b + 3)])
    return np.array(v), np.array(f)


def _superelipsoide(a: float, b: float, c: float, e: float = 0.32, nu: int = 16, nv: int = 8):
    """Superelipsoide |x/a|^(2/e) + |y/b|^(2/e) + |z/c|^(2/e) ≈ 1 (e pequeno = caixa de cantos redondos): vértices
    (com polos únicos), faces e o parâmetro u ∈ [0, 1) de cada vértice."""
    def pw(w, ex):
        return np.sign(w) * np.abs(w) ** ex
    us = np.arange(nu) * _TAU / nu
    vs = np.linspace(-0.5 * math.pi, 0.5 * math.pi, nv + 1)[1:-1]
    v = [(0.0, 0.0, -c)]
    par = [0.0]
    for lat in vs:
        cv, sv = pw(math.cos(lat), e), pw(math.sin(lat), e)
        for u in us:
            v.append((a * cv * pw(math.cos(u), e), b * cv * pw(math.sin(u), e), c * sv))
            par.append(u / _TAU)
    v.append((0.0, 0.0, c))
    par.append(0.0)
    f = []
    topo = len(v) - 1
    for i in range(nu):                                   # leque de baixo (normal −z)
        f.append((0, 1 + (i + 1) % nu, 1 + i))
    for j in range(len(vs) - 1):
        r0, r1 = 1 + j * nu, 1 + (j + 1) * nu
        for i in range(nu):
            i2 = (i + 1) % nu
            f.extend([(r0 + i, r0 + i2, r1 + i2), (r0 + i, r1 + i2, r1 + i)])
    rl = 1 + (len(vs) - 1) * nu
    for i in range(nu):                                   # leque de cima (normal +z)
        f.append((rl + i, rl + (i + 1) % nu, topo))
    return np.array(v), np.array(f), np.array(par)


def _cabeca_cilindrica(d: float = 0.0055, h: float = 0.0030, s: float = 0.0025, prof: float = 0.0016, n: int = 24):
    """Cabeça de parafuso ISO 4762 (cilíndrica, sextavado interior de `s` entre faces) com o fundo em z = 0 e o topo em
    z = h; o sextavado é um rebaixo de verdade (paredes e fundo)."""
    r = 0.5 * d
    ch = 0.12 * h                                          # chanfro do topo
    v, f, _ = _revolucao([[(0.0, 0.0), (r, 0.0)], [(r, 0.0), (r, h - ch)], [(r, h - ch), (r - ch, h)]], n=n)
    v, f = list(map(tuple, v)), [tuple(t) for t in f]
    phi = np.arange(n) * _TAU / n
    a_hex = 0.5 * s
    # topo: coroa entre a circunferência (r − ch) e o contorno do sextavado amostrado nos mesmos ângulos
    rh = a_hex / np.cos(((phi + math.pi / 6) % (math.pi / 3)) - math.pi / 6)
    b = len(v)
    v.extend(zip(((r - ch) * np.cos(phi)).tolist(), ((r - ch) * np.sin(phi)).tolist(), [h] * n, strict=True))
    v.extend(zip((rh * np.cos(phi)).tolist(), (rh * np.sin(phi)).tolist(), [h] * n, strict=True))
    for i in range(n):
        i2 = (i + 1) % n
        f.extend([(b + n + i, b + i, b + i2), (b + n + i, b + i2, b + n + i2)])
    # paredes do rebaixo (normais para DENTRO do furo = para fora do sólido), com os MESMOS pontos do contorno do topo
    # (malha fechada, sem juntas em T) e vértices próprios em cada face do sextavado; depois o fundo
    hx, hy = rh * np.cos(phi), rh * np.sin(phi)
    passo = n // 6
    for k in range(6):
        idx = [(2 + passo * k + j) % n for j in range(passo + 1)]       # canto k → canto k+1 (cantos a 30° + 60°·k)
        b = len(v)
        v.extend((hx[i], hy[i], h) for i in idx)
        v.extend((hx[i], hy[i], h - prof) for i in idx)
        for j in range(passo):
            f.extend([(b + j, b + j + 1, b + passo + 2 + j), (b + j, b + passo + 2 + j, b + passo + 1 + j)])
    b = len(v)
    v.append((0.0, 0.0, h - prof))
    v.extend(zip(hx.tolist(), hy.tolist(), [h - prof] * n, strict=True))
    for i in range(n):
        f.append((b, b + 1 + i, b + 1 + (i + 1) % n))
    return np.array(v), np.array(f)


def _arco(r0: float, r1: float, z0: float, z1: float, n: int = 48):
    """Coroa circular (tubo curto) r0..r1 × z0..z1, arestas vivas."""
    return _revolucao([[(r0, z0), (r1, z0)], [(r1, z0), (r1, z1)], [(r1, z1), (r0, z1)], [(r0, z1), (r0, z0)]], n=n)


# =========================================================================================== motor (malhas)
def _alturas(dm: _Motor) -> dict:
    """Cotas internas do motor (m, a partir do fundo da base) — proporções da série Antigravity (ESTIMADAS)."""
    d, h = dm.d, dm.h
    r = 0.5 * d
    z_tc1 = h - max(0.11 * h, 0.0016)                       # topo do sino (o ressalto da hélice vai até h)
    z_tc0 = z_tc1 - max(0.07 * h, 0.0012)
    o = min(max(0.3 * dm.ts + 0.0006, 0.0010), 0.0030)       # cabeças das bobinas acima/abaixo do pacote de chapas
    z_sm = z_tc0 - 0.00045 - (0.5 * dm.ts + o)
    # o sino só cobre o estator e as bobinas (desce 0,8 mm abaixo delas): o resto da altura é a base, alta e vazada
    h_b = min(max(0.15 * h, z_sm - (0.5 * dm.ts + o) - 0.0014), 0.45 * h)
    r_mag = min(0.5 * dm.ds + 0.00045, r - 0.0010)
    return {"h_b": h_b, "r_b": 0.465 * d, "r_ri": 0.415 * d, "r_hb": max(0.155 * d, 0.5 * dm.eixo + 0.002),
            "w_a": 0.15 * d, "z_b0": h_b + 0.0006, "z_tc0": z_tc0, "z_tc1": z_tc1, "r_mag": r_mag,
            "r_rim": min(0.43 * d, r_mag - 0.0006), "ch": 0.016 * d, "r_bo": 0.21 * d, "o": o, "z_sm": z_sm,
            "z_s0": z_sm - 0.5 * dm.ts, "z_s1": z_sm + 0.5 * dm.ts,
            "r_y": max(0.28 * dm.ds, max(0.155 * d, 0.5 * dm.eixo + 0.002) + 0.0015),
            "r_sap": 0.5 * dm.ds - 0.0011, "r": r}


@functools.lru_cache(maxsize=16)
def _malhas_motor(dm: _Motor) -> dict:
    """As malhas do motor no referencial «fundo da base, eixo z, braços da base a 45°» (iguais nos 4 motores)."""
    a = _alturas(dm)
    r, h = a["r"], dm.h
    out = {}

    # base CNC vazada: cubo do rolamento + anel de baixo + 4 colunas (nos braços) + anel de cima — 4 janelas laterais
    # de ventilação (a dos cabos fica virada para o centro do drone) — e 4 braços em X com os furos M3
    hb, rb, ri = a["h_b"], a["r_b"], a["r_ri"]
    h_inf, h_sup = max(0.22 * hb, 0.0010), max(0.15 * hb, 0.0008)
    c_b = min(0.35 * h_sup, 0.0004)
    base = _Malha()
    base.juntar(*_revolucao([[(0.0, 0.0), (a["r_hb"], 0.0)], [(a["r_hb"], 0.0), (a["r_hb"], a["z_s0"])],
                             [(a["r_hb"], a["z_s0"]), (0.0, a["z_s0"])]])[:2])
    base.juntar(*_arco(ri, rb, 0.0, h_inf, n=64)[:2])
    base.juntar(*_revolucao([[(ri, hb - h_sup), (rb, hb - h_sup)], [(rb, hb - h_sup), (rb, hb - c_b)],
                             [(rb, hb - c_b), (rb - c_b, hb)], [(rb - c_b, hb), (ri, hb)],
                             [(ri, hb), (ri, hb - h_sup)]], n=64)[:2])
    a_col = math.radians(16.0)
    h_braco = h_inf + 0.35 * (hb - h_inf)
    for k in range(4):
        phi = math.pi / 4 + k * math.pi / 2
        base.juntar(*_setor(ri, rb, h_inf - 0.0001, hb - h_sup + 0.0001, phi - a_col, phi + a_col))
        base.juntar(*_caixa(0.5 * a["r_hb"], ri + 0.0006, 0.5 * a["w_a"], 0.0, h_braco), rot_z=phi)
    out["base"] = base.saida()

    nucleo = _Malha()                                      # coroa (yoke) + anel das sapatas dos dentes
    nucleo.juntar(*_arco(a["r_hb"] - 0.0002, a["r_y"], a["z_s0"], a["z_s1"]))
    nucleo.juntar(*_arco(a["r_sap"], 0.5 * dm.ds, a["z_s0"], a["z_s1"], n=72))
    out["nucleo"] = nucleo.saida()

    cobre = _Malha()                                       # N bobinas em cunha (ângulo constante: mais largas por fora)
    rho0, rho1 = a["r_y"] + 0.00015, a["r_sap"] - 0.00015
    rho_c, a_r = 0.5 * (rho0 + rho1), 0.5 * (rho1 - rho0)
    psi_h = 0.43 * _TAU / dm.n
    meia_z = 0.5 * dm.ts + a["o"]
    sv, sf, su = _superelipsoide(a_r, psi_h * rho_c, meia_z, e=0.30, nu=12, nv=6)
    for j in range(dm.n):
        phi0 = j * _TAU / dm.n
        rho = rho_c + sv[:, 0]
        ang = phi0 + sv[:, 1] / rho_c
        vv = np.column_stack([rho * np.cos(ang), rho * np.sin(ang), a["z_sm"] + sv[:, 2]])
        tt = np.column_stack([np.full_like(su, 0.25), rho / (2.0 * _PASSO_ESPIRA)])   # coluna fixa → riscas
        cobre.juntar(vv, sf, tt)
    out["cobre"] = cobre.saida(textura=True)

    ch = a["ch"]                                           # sino: parede dos ímanes + aba do topo (perfil anti-horário)
    anel = _Malha()
    ch2 = 0.5 * ch
    anel.juntar(*_revolucao([[(a["r_mag"], a["z_b0"]), (r - ch2, a["z_b0"])], [(r - ch2, a["z_b0"]), (r, a["z_b0"] + ch2)],
                             [(r, a["z_b0"] + ch2), (r, a["z_tc1"] - ch)],
                             [(r, a["z_tc1"] - ch), (r - ch, a["z_tc1"])],
                             [(r - ch, a["z_tc1"]), (a["r_rim"], a["z_tc1"])],
                             [(a["r_rim"], a["z_tc1"]), (a["r_rim"], a["z_tc0"])],
                             [(a["r_rim"], a["z_tc0"]), (a["r_mag"], a["z_tc0"])],
                             [(a["r_mag"], a["z_tc0"]), (a["r_mag"], a["z_b0"])]], n=96)[:2])
    out["anel"] = anel.saida()

    dlt = 0.00006                                          # chanfro diamantado: banda fina por fora do chanfro do sino
    p1, p2 = np.array([r, a["z_tc1"] - ch]), np.array([r - ch, a["z_tc1"]])
    nrm = np.array([1.0, 1.0]) / math.sqrt(2.0)
    q1, q2 = p1 + dlt * nrm, p2 + dlt * nrm
    aresta = _Malha()
    aresta.juntar(*_revolucao([[tuple(p1 - 0.2 * dlt * nrm), tuple(q1)], [tuple(q1), tuple(q2)],
                               [tuple(q2), tuple(p2 - 0.2 * dlt * nrm)], [tuple(p2 - 0.2 * dlt * nrm),
                                                                           tuple(p1 - 0.2 * dlt * nrm)]], n=96)[:2])
    out["aresta"] = aresta.saida()

    topo = _Malha()                                        # 6 raios curvos (ventoinha) + ressalto de montagem da hélice
    cb = 0.0005
    topo.juntar(*_revolucao([[(0.0, a["z_tc0"]), (a["r_bo"], a["z_tc0"])],
                             [(a["r_bo"], a["z_tc0"]), (a["r_bo"], h - cb)], [(a["r_bo"], h - cb), (a["r_bo"] - cb, h)],
                             [(a["r_bo"] - cb, h), (0.0, h)]], n=48)[:2])
    ra, rb = a["r_bo"] - 0.0008, a["r_rim"] + 0.0008
    t = np.linspace(0.0, 1.0, 11)
    for k in range(6):
        phi = k * _TAU / 6 + 0.60 * t ** 0.9
        rr = ra + (rb - ra) * t
        w = (0.115 + (0.070 - 0.115) * t) * dm.d
        cx, cy = rr * np.cos(phi), rr * np.sin(phi)
        tx, ty = np.gradient(cx), np.gradient(cy)
        nt = np.hypot(tx, ty)
        nx, ny = -ty / nt, tx / nt                          # normal à esquerda de quem anda para fora
        esq = np.column_stack([cx + 0.5 * w * nx, cy + 0.5 * w * ny])
        dir_ = np.column_stack([cx - 0.5 * w * nx, cy - 0.5 * w * ny])
        topo.juntar(*_faixa(esq, dir_, a["z_tc0"], a["z_tc1"]))
    out["topo"] = topo.saida()

    # rolamento de baixo (face vista por baixo da base, à volta do veio): pistas interior e exterior salientes e a
    # blindagem metálica (ZZ) rebaixada — 684 (4 × 9 × 4 mm) no veio Φ4, 686 (6 × 13 × 5 mm) no Φ6
    ri_r, ro_r = 0.5 * dm.eixo, 1.125 * dm.eixo
    rol = _Malha()
    rol.juntar(*_revolucao([[(ri_r, 0.0004), (ri_r, -0.00005)], [(ri_r, -0.00005), (ri_r + 0.0007, -0.00005)],
                            [(ri_r + 0.0007, -0.00005), (ri_r + 0.0007, 0.00012)],
                            [(ri_r + 0.0007, 0.00012), (ro_r - 0.0007, 0.00012)],
                            [(ro_r - 0.0007, 0.00012), (ro_r - 0.0007, -0.00005)],
                            [(ro_r - 0.0007, -0.00005), (ro_r, -0.00005)], [(ro_r, -0.00005), (ro_r, 0.0004)],
                            [(ro_r, 0.0004), (ri_r, 0.0004)]], n=32)[:2])
    out["rolamento"] = rol.saida()

    paraf = _Malha()                                       # 4 × M3 por baixo: sextavado virado para baixo
    cv, cf = _cabeca_cilindrica()
    for k in range(4):
        ang = math.pi / 4 + k * math.pi / 2
        paraf.juntar(cv, cf, espelho_z=True, desloc=(dm.r_furos * math.cos(ang), dm.r_furos * math.sin(ang), 0.0))
    out["parafusos"] = paraf.saida()
    return out


# =========================================================================================== hélice (pá paramétrica)
def _forma_pa(dh: _Helice) -> dict:
    """Parâmetros da planta da pá (x = r/R): pescoço no cubo, corda máxima em x_p, afunilamento até x_t, ponta elítica.
    A corda máxima sai da corda MÉDIA do catálogo (média de x_h a 1 = `corda_media`)."""
    fam = {"scimitar_cf": (0.27, 0.93, 0.035, 0.040), "mr_naca": (0.30, 0.90, 0.020, 0.045),
           "tri_pa_fpv": (0.38, 0.88, 0.015, 0.035)}.get(dh.perfil, (0.30, 0.91, 0.025, 0.040))
    x_p, x_t, varr, arq = fam
    x_h = dh.r_cubo / dh.r
    c_h = min(1.15 * dh.h_cubo, 1.6 * dh.r_cubo)
    lam = min(max(dh.afun, 0.15), 1.0)
    xs = np.linspace(x_h, 1.0, 4001)
    alfa, beta = np.zeros_like(xs), np.zeros_like(xs)
    sub = xs <= x_p
    s = np.sin(0.5 * math.pi * (xs[sub] - x_h) / max(x_p - x_h, 1e-9))
    alfa[sub], beta[sub] = 1.0 - s, s
    mid = (xs > x_p) & (xs <= x_t)
    beta[mid] = 1.0 - (1.0 - lam) * ((xs[mid] - x_p) / (x_t - x_p)) ** _CHEIA
    tip = xs > x_t
    beta[tip] = lam * np.sqrt(np.clip(1.0 - ((xs[tip] - x_t) / (1.0 - x_t)) ** 2, 0.0, 1.0))
    i_a, i_b = float(np.mean(alfa)), float(np.mean(beta))
    c_pico = max((dh.corda - c_h * i_a) / max(i_b, 1e-9), 1.3 * c_h)
    return {"x_h": x_h, "x_p": x_p, "x_t": x_t, "c_h": c_h, "c_pico": c_pico, "lam": lam,
            "varr": varr * dh.r, "arq": arq, "d_off": 0.10 * c_pico}


def _seccao_pa(dh: _Helice, fp: dict, x: float, nc: int = 12, inflar: float = 0.0) -> np.ndarray:
    """Laço da secção à estação x (pá ao longo de +x, a avançar para +y = sentido CCW visto de cima): extradorso do bordo
    de fuga ao de ataque e intradorso de volta — (2·nc − 1) × 3, em metros."""
    x_h, x_p, x_t, c_h, c_pk = fp["x_h"], fp["x_p"], fp["x_t"], fp["c_h"], fp["c_pico"]
    if x <= x_h:
        c, u_s = c_h, 0.0
    elif x <= x_p:
        u_s = math.sin(0.5 * math.pi * (x - x_h) / max(x_p - x_h, 1e-9))
        c = c_h + (c_pk - c_h) * u_s
    elif x <= x_t:
        u_s = 1.0
        c = c_pk * (1.0 - (1.0 - fp["lam"]) * ((x - x_p) / (x_t - x_p)) ** _CHEIA)
    else:
        u_s = 1.0
        c = None
    varr = fp["varr"] * max(0.0, (x - 0.55) / 0.45) ** 2
    y_le_reto = 0.5 * c_pk - fp["d_off"]
    if x <= x_t:
        y_mid = (-fp["d_off"] * u_s) if x <= x_p else (y_le_reto - 0.5 * c)
        y_mid -= varr
    else:                                                   # ponta elítica, simétrica em torno da linha média em x_t
        c_t = c_pk * fp["lam"]
        w = (x - x_t) / (1.0 - x_t)
        c = c_t * math.sqrt(max(1.0 - w * w, 0.0))
        y_mid = (y_le_reto - 0.5 * c_t) - varr
    # espessura (pescoço gordo → ponta fina), arqueamento e passo
    t_ponta = max(0.00055, 0.0048 * dh.r)
    t_raiz = 0.55 * dh.h_cubo
    t = t_raiz if x <= x_h else t_ponta + (t_raiz - t_ponta) * ((1.0 - x) / (1.0 - x_h)) ** 1.4
    th_g = math.atan2(dh.passo, _TAU * max(x * dh.r, 1e-6))
    th_max = math.radians(23.0)                              # junto ao cubo o passo real fica-se pelos ~21–23°
    theta = th_g * (1.0 + (th_g / th_max) ** 10) ** -0.1
    m_c, p_c = fp["arq"] * u_s, 0.40
    s = 0.5 * (1.0 - np.cos(np.linspace(0.0, math.pi, nc)))          # LE (0) → TE (1), cosseno
    tau = t / max(c, 1e-6)
    yt = 5.0 * tau * c * (0.2969 * np.sqrt(s) - 0.1260 * s - 0.3516 * s ** 2 + 0.2843 * s ** 3 - 0.1015 * s ** 4)
    yt += max(0.00008, 0.06 * t) * s + inflar
    yc = np.where(s < p_c, m_c / p_c ** 2 * (2 * p_c * s - s ** 2),
                  m_c / (1 - p_c) ** 2 * (1 - 2 * p_c + 2 * p_c * s - s ** 2)) * c
    y_le = y_mid + 0.5 * c + inflar
    eta = y_le - s * (c + 2.0 * inflar)
    y_rot = y_mid + 0.10 * c
    sup = np.column_stack([eta, yc + yt])[::-1]                         # TE → LE
    inf = np.column_stack([eta, yc - yt])[1:]                           # LE → TE
    laco = np.vstack([sup, inf])
    ct, st = math.cos(theta), math.sin(theta)
    de = laco[:, 0] - y_rot
    yy = y_rot + de * ct - laco[:, 1] * st
    zz = de * st + laco[:, 1] * ct
    return np.column_stack([np.full(len(laco), x * dh.r), yy, zz])


def _loft(lacos: list[np.ndarray], tex: bool = True):
    """Superfície fechada por estações: pele lisa (bordo de ataque redondo), faixa do bordo de fuga com vértices próprios
    (aresta viva) e tampas planas nas duas pontas. Orientação para fora (pá CCW)."""
    ns, npt = len(lacos), len(lacos[0])
    P = np.stack(lacos)                                                  # ns × npt × 3
    arc = np.concatenate([np.zeros((ns, 1)), np.cumsum(np.linalg.norm(np.diff(P, axis=1), axis=2), axis=1)], axis=1)
    v = [P.reshape(-1, 3)]
    t = [np.column_stack([P[:, :, 0].ravel(), arc.ravel()]) / _PERIODO_TECIDO]
    idx = np.arange(ns * npt).reshape(ns, npt)
    f = []
    for j in range(ns - 1):
        for i in range(npt - 1):
            a, b, c, d = idx[j, i], idx[j + 1, i], idx[j + 1, i + 1], idx[j, i + 1]
            f.extend([(a, b, c), (a, c, d)])
    base = ns * npt                                                      # bordo de fuga (último → primeiro ponto do laço)
    te = np.stack([P[:, -1], P[:, 0]], axis=1).reshape(-1, 3)
    v.append(te)
    t.append(np.column_stack([te[:, 0], te[:, 1]]) / _PERIODO_TECIDO)
    for j in range(ns - 1):
        a, b, c, d = base + 2 * j, base + 2 * (j + 1), base + 2 * (j + 1) + 1, base + 2 * j + 1
        f.extend([(a, b, c), (a, c, d)])
    n0 = base + 2 * ns
    for j, sinal in ((0, 1), (ns - 1, -1)):                              # tampas: raiz (−x) e ponta (+x)
        lac = P[j]
        cen = lac.mean(axis=0)
        v.append(np.vstack([cen, lac]))
        t.append(np.column_stack([np.r_[cen[0], lac[:, 0]], np.r_[cen[1], lac[:, 1]]]) / _PERIODO_TECIDO)
        for i in range(npt):
            i2 = (i + 1) % npt
            tri = (n0, n0 + 1 + i, n0 + 1 + i2)
            f.append(tri if sinal > 0 else tri[::-1])
        n0 += npt + 1
    return np.concatenate(v), np.array(f), (np.concatenate(t) if tex else None)


def _estacoes(fp: dict) -> tuple[np.ndarray, np.ndarray, tuple[float, float]]:
    """Estações da raiz (até 50 % do raio) e da ponta (com as bordas da faixa colorida como estações próprias)."""
    x_h, x_p, x_t = fp["x_h"], fp["x_p"], fp["x_t"]
    x0 = 0.55 * x_h
    raiz = np.unique(np.concatenate([np.linspace(x0, x_h, 3), np.linspace(x_h, x_p, 7), np.linspace(x_p, 0.5, 5)]))
    f0, f1 = x_t - 0.055, x_t + 0.012
    w = np.sin(np.linspace(0.0, 0.5 * math.pi, 7))[1:] * 0.985
    ponta = np.unique(np.concatenate([np.linspace(0.5, f0, 7), np.linspace(f0, f1, 4),
                                      [x_t], x_t + (1.0 - x_t) * w]))
    return raiz, ponta, (f0, f1)


@functools.lru_cache(maxsize=16)
def _malhas_helice(dh: _Helice) -> dict:
    """Malhas da hélice no referencial do rotor (plano da hélice em z = 0, pá 1 ao longo de +x): raiz, ponta e faixa
    nas variantes CCW e CW (espelho), cubo, parafusos de aperto ou porca."""
    fp = _forma_pa(dh)
    raiz_x, ponta_x, (f0, f1) = _estacoes(fp)
    out = {}
    pecas = {"raiz": [_seccao_pa(dh, fp, x) for x in raiz_x],
             "ponta": [_seccao_pa(dh, fp, x) for x in ponta_x],
             "faixa": [_seccao_pa(dh, fp, x, inflar=0.00012) for x in ponta_x if f0 - 1e-9 <= x <= f1 + 1e-9]}
    for nome, lacos in pecas.items():
        v, f, t = _loft(lacos, tex=(nome != "faixa"))
        for sent, esp in (("ccw", False), ("cw", True)):
            m = _Malha()
            m.juntar(v, f, t, espelho_y=esp)
            out[f"{nome}_{sent}"] = m.saida(textura=(nome != "faixa"), mtex=_TEX_CARBONO)
    r, h = dh.r_cubo, dh.h_cubo
    ch = 0.1 * h
    cubo = _Malha()
    cubo.juntar(*_revolucao([[(0.0, -0.5 * h), (r - ch, -0.5 * h)], [(r - ch, -0.5 * h), (r, -0.5 * h + ch)],
                             [(r, -0.5 * h + ch), (r, 0.5 * h - ch)], [(r, 0.5 * h - ch), (r - ch, 0.5 * h)],
                             [(r - ch, 0.5 * h), (0.0, 0.5 * h)]], n=48, tex=("p", "p", "c", "p", "p")))
    out["cubo"] = cubo.saida(textura=True, mtex=_TEX_CARBONO)
    if dh.fixacao == "parafusos":
        par = _Malha()
        cv, cf = _cabeca_cilindrica()
        for sx in (1.0, -1.0):
            par.juntar(cv, cf, desloc=(sx * 0.006, 0.0, 0.0))            # círculo de 12 mm (T-Motor P/MF)
        out["parafusos"] = par.saida()
    else:
        s_af = 0.008 if dh.r < 0.1 else 0.010                           # M5 (5″) / M6
        hexa = [(s_af / math.sqrt(3.0) * math.cos(k * math.pi / 3), s_af / math.sqrt(3.0) * math.sin(k * math.pi / 3))
                for k in range(6)]
        porca = _Malha()
        porca.juntar(*_prisma(hexa, 0.0, 0.62 * s_af))
        porca.juntar(*_arco(0.30 * s_af, 0.46 * s_af, 0.6 * s_af, 0.80 * s_af, n=24))   # anel de nylon/cúpula
        out["porca"] = porca.saida()
    return out


# =========================================================================================== materiais e texturas
def _por_nome(lista, nome: str):
    """O elemento do spec com esse nome, procurado na LISTA (texturas e malhas; o mesmo cuidado de `ctx.obter_material`:
    no MuJoCo 3.15 a procura por nome falha para elementos acrescentados depois de um `spec.delete`)."""
    return next((e for e in lista if e.name == nome), None)


def _textura(ctx, nome: str, rgb1, rgb2, lado: int = 64, **kw) -> None:
    """Xadrez 2 × 2 procedimental (`builtin` checker) — exporta-se no MJCF (`to_xml`), ao contrário de imagens em memória."""
    if _por_nome(ctx.spec.textures, nome) is None:
        ctx.spec.add_texture(name=nome, type=mujoco.mjtTexture.mjTEXTURE_2D, builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
                             rgb1=list(rgb1), rgb2=list(rgb2), width=lado, height=lado, **kw)



def _materiais(ctx, dh: _Helice) -> dict:
    """Materiais deste módulo (prefixo `det_mot_`/`det_hel_`) e os já existentes reutilizados (faixas e fios)."""
    _textura(ctx, "det_hel_tecido", (0.130, 0.135, 0.150), (0.080, 0.084, 0.095))
    _textura(ctx, "det_mot_espiras", (0.88, 0.50, 0.22), (0.58, 0.28, 0.09), lado=32)
    mat = {
        "anod": ctx.material("det_mot_anodizado", [0.055, 0.058, 0.066, 1.0], specular=0.45, shininess=0.55),
        "aresta": ctx.material("det_mot_aresta", [0.86, 0.87, 0.89, 1.0], specular=1.0, shininess=0.95),
        "alu": ctx.material("det_mot_aluminio", [0.70, 0.71, 0.74, 1.0], specular=0.85, shininess=0.75),
        "nucleo": ctx.material("det_mot_nucleo", [0.20, 0.215, 0.235, 1.0], specular=0.55, shininess=0.5),
        "cobre": ctx.material("det_mot_cobre", [1.0, 1.0, 1.0, 1.0], specular=0.85, shininess=0.8),
        "aco": ctx.material("det_mot_aco", [0.66, 0.67, 0.70, 1.0], specular=0.9, shininess=0.8),
        "termo": ctx.material("det_mot_termo", [0.035, 0.035, 0.04, 1.0], specular=0.15, shininess=0.25),
        "ouro": ctx.material("det_mot_ouro", [0.93, 0.73, 0.30, 1.0], specular=1.0, shininess=0.9),
    }
    if dh.perfil == "scimitar_cf":
        mat["pa"] = ctx.material("det_hel_carbono", [1.0, 1.0, 1.0, 1.0], specular=0.85, shininess=0.92)
        tex = "det_hel_tecido"
    else:                                                   # APC / FPV: plástico injetado
        cinza = [0.55, 0.52, 0.46, 1.0] if "apc" in str(dh.perfil) or dh.perfil == "mr_naca" else [0.10, 0.10, 0.11, 1.0]
        mat["pa"] = ctx.material("det_hel_plastico", cinza, specular=0.35, shininess=0.4)
        tex = None
    for chave, nome_tex in (("cobre", "det_mot_espiras"), ("pa", tex)):
        if nome_tex:
            ctx.obter_material(mat[chave]).textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = nome_tex
    for nome in ("fio_vermelho", "fio_preto", "fio_azul", "helice_ponta_cw", "helice_ponta_ccw"):
        mat[nome] = nome
    return mat


def _malha(ctx, nome: str, dados: tuple) -> str:
    """Regista a malha (uma vez por spec) e devolve o nome."""
    if _por_nome(ctx.spec.meshes, nome) is None:
        v, f, t = dados
        kw = {"usertexcoord": list(t)} if t is not None else {}
        ctx.spec.add_mesh(name=nome, uservert=list(v), userface=list(f), **kw)
    return nome


# =========================================================================================== montagem
_ANTIGOS_MOTOR = ("estator_cobre", "sino_anel", "base_cnc", "raio_1", "raio_2", "raio_3", "eixo")
_ANTIGOS_PA = ("raiz", "ponta", "faixa")


def _qz(ang: float) -> list[float]:
    return [math.cos(0.5 * ang), 0.0, 0.0, math.sin(0.5 * ang)]


def adicionar(ctx) -> None:
    """Motores T-Motor e hélices de carbono reais nos 4 rotores (ver o docstring do módulo)."""
    hw = ctx.hw
    dm, dh = _dims_motor(hw.motor), _dims_helice(hw.helice)
    mat = _materiais(ctx, dh)
    mm = {k: _malha(ctx, f"det_mot_{k}", v) for k, v in _malhas_motor(dm).items()}
    mh = {k: _malha(ctx, f"det_hel_{k}", v) for k, v in _malhas_helice(dh).items()}
    a = _alturas(dm)
    rot = np.asarray(hw.pos_rotores, dtype=float)
    giro = np.asarray(hw.GIRO, dtype=float)
    malha = mujoco.mjtGeom.mjGEOM_MESH
    cil, cap = mujoco.mjtGeom.mjGEOM_CYLINDER, mujoco.mjtGeom.mjGEOM_CAPSULE
    for i in range(4):
        k = i + 1
        g_mot, g_hel = ctx.geom_existente(f"motor{k}"), ctx.geom_existente(f"helice{k}")
        if g_mot is None or g_hel is None:
            continue
        corpo = g_mot.parent.name
        c = np.array(g_mot.pos, dtype=float)
        z0 = c[2] - float(g_mot.size[1])                     # fundo do motor (no corpo)
        zp = float(np.asarray(g_hel.pos, dtype=float)[2])   # plano da hélice (= site r{k})
        ux, uy = rot[i] / max(float(np.linalg.norm(rot[i])), 1e-9)
        ang = math.atan2(uy, ux)
        nx, ny = -uy, ux
        # ---- fora o detalhe antigo; o cilindro com massa fica, invisível (as peças abaixo representam-no todo)
        for suf in _ANTIGOS_MOTOR:
            if ctx.geom_existente(f"motor{k}_{suf}") is not None:
                ctx.apagar(f"motor{k}_{suf}")
        nomes_pa = [f"helice{k}_cubo"] + [f"helice{k}_pa{b}_{s}" for b in range(1, 9) for s in _ANTIGOS_PA]
        for nome in nomes_pa:
            if ctx.geom_existente(nome) is not None:
                ctx.apagar(nome)
        ctx.esconder(f"motor{k}")
        # o site do rotor (esfera cinzenta de 1 cm que o cockpit desenha — sites do grupo 0) saía por cima da tampa como
        # um falso «spinner»: fica transparente (só a cor; o site, a posição e a física não mudam)
        site = _por_nome(ctx.spec.sites, f"r{k}")
        if site is not None:
            site.rgba = [0.0, 0.0, 0.0, 0.0]

        # ---- motor (referencial: fundo da base no eixo; braços da base a 45° do braço do drone)
        pm, qm = [c[0], c[1], z0], _qz(ang)
        for nome, chave, material, q in ((f"motor{k}_base_cnc", "base", mat["anod"], qm),
                                         (f"motor{k}_estator_nucleo", "nucleo", mat["nucleo"], qm),
                                         (f"motor{k}_estator_cobre", "cobre", mat["cobre"], qm),
                                         (f"motor{k}_sino_anel", "anel", mat["anod"], qm),
                                         (f"motor{k}_sino_aresta", "aresta", mat["aresta"], qm),
                                         (f"motor{k}_raio_1", "topo", mat["anod"], _qz(ang + 0.3))):
            ctx.geom(corpo, nome, _GRUPO_MOTOR, type=malha, meshname=mm[chave], material=material, pos=pm, quat=q)
        ctx.geom(corpo, f"motor{k}_rolamento", _GRUPO_MOTOR, type=malha, meshname=mm["rolamento"], material=mat["aco"],
                 pos=pm, quat=qm)
        z_eixo0, z_eixo1 = z0 - 0.0012, z0 + a["z_tc0"]
        ctx.geom(corpo, f"motor{k}_eixo", _GRUPO_MOTOR, type=cil, size=[0.5 * dm.eixo, 0.5 * (z_eixo1 - z_eixo0), 0],
                 pos=[c[0], c[1], 0.5 * (z_eixo0 + z_eixo1)], material=mat["aco"])
        g_sup = ctx.geom_existente(f"suporte_motor_{k}")
        z_sup = (float(g_sup.pos[2]) - float(g_sup.size[1])) if g_sup is not None else z0 - 0.005
        ctx.geom(corpo, f"motor{k}_parafusos", _GRUPO_MOTOR, type=malha, meshname=mm["parafusos"], material=mat["aco"],
                 pos=[c[0], c[1], min(z_sup, z0)], quat=qm)
        z_cubo0 = zp - 0.5 * dh.h_cubo
        z_top = z0 + dm.h
        if z_cubo0 - z_top > 0.0003:
            r_ad = min(max(0.17 * dm.d, 0.004), 0.010, 0.95 * dh.r_cubo)
            ctx.geom(corpo, f"motor{k}_adaptador", _GRUPO_MOTOR, type=cil,
                     size=[r_ad, 0.5 * (z_cubo0 - z_top) + 0.00005, 0], pos=[c[0], c[1], 0.5 * (z_cubo0 + z_top)],
                     material=mat["alu"])

        # ---- cabos de fase: manga na base (virada para o centro do drone) → 3 cabos → conectores bala de 3,5 mm
        r_m = min(max(0.045 * dm.d, 0.0016), 0.0030)
        r_f = min(max(0.022 * dm.d, 0.0008), 0.0013)
        r_c = 0.0019
        sai = np.array([c[0] - ux * (a["r_b"] - 0.001), c[1] - uy * (a["r_b"] - 0.001), z0 + 0.55 * a["h_b"]])
        g_br = ctx.geom_existente(f"braco{k}")
        articulado = corpo != "drone"
        l_fio = max(0.020, dm.cabo - 0.018)
        if not articulado:
            z_fio = (float(g_br.pos[2]) + float(g_br.size[2]) if g_br is not None else z0) + r_c
            m1 = np.array([c[0] - ux * (a["r"] + 0.006), c[1] - uy * (a["r"] + 0.006), z_fio])
        else:
            m1 = np.array([c[0] - ux * (a["r"] + 0.004), c[1] - uy * (a["r"] + 0.004), z0 - 0.003])
        ctx.geom(corpo, f"motor{k}_manga", _GRUPO_MOTOR, type=cap, size=[r_m, 0, 0],
                 fromto=sai.tolist() + m1.tolist(), material=mat["termo"])
        g_mast = ctx.geom_existente(f"mastro{k}_tubo")
        r_mast = float(g_mast.size[0]) if g_mast is not None else 0.008
        for f_idx, (lat, cor) in enumerate(((-0.0045, "fio_vermelho"), (0.0, "fio_preto"), (0.0045, "fio_azul"))):
            fase = "abc"[f_idx]
            p1 = m1 + np.array([nx, ny, 0.0]) * (0.3 * lat)
            if not articulado:
                p2 = np.array([c[0] - ux * (a["r"] + 0.006 + l_fio) + nx * lat,
                               c[1] - uy * (a["r"] + 0.006 + l_fio) + ny * lat, z_fio])
                p3 = p2 + np.array([-ux, -uy, 0.0]) * 0.0045
            else:
                rr = r_mast + r_c + 0.0025
                dr_ = (a["r"] + 0.004) - rr
                dz = math.sqrt(max(l_fio ** 2 - dr_ ** 2, (0.5 * l_fio) ** 2))
                p2 = np.array([c[0] - ux * rr + nx * lat, c[1] - uy * rr + ny * lat, m1[2] - dz])
                p3 = p2 + np.array([0.0, 0.0, -0.0045])
            ctx.geom(corpo, f"motor{k}_fase_{fase}", _GRUPO_MOTOR, type=cap, size=[r_f, 0, 0],
                     fromto=p1.tolist() + p2.tolist(), material=mat[cor])
            ctx.geom(corpo, f"motor{k}_fase_{fase}_conector", _GRUPO_MOTOR, type=cil, size=[r_c, 0, 0],
                     fromto=p2.tolist() + p3.tolist(), material=mat["ouro"])

        # ---- hélice (referencial do rotor: plano da hélice; pás perpendiculares ao braço com o rotor parado)
        sent = "cw" if giro[i] < 0 else "ccw"
        ph = [c[0], c[1], zp]
        psi0 = ang + 0.5 * math.pi
        ctx.geom(corpo, f"helice{k}_cubo", _GRUPO_HELICE, type=malha, meshname=mh["cubo"], material=mat["pa"],
                 pos=ph, quat=_qz(psi0))
        cor_faixa = mat["helice_ponta_cw" if giro[i] < 0 else "helice_ponta_ccw"]
        for b in range(dh.pas):
            q = _qz(psi0 + _TAU * b / dh.pas)
            for parte, material in (("raiz", mat["pa"]), ("ponta", mat["pa"]), ("faixa", cor_faixa)):
                ctx.geom(corpo, f"helice{k}_pa{b + 1}_{parte}", _GRUPO_HELICE, type=malha,
                         meshname=mh[f"{parte}_{sent}"], material=material, pos=ph, quat=q)
        z_tampa = zp + 0.5 * dh.h_cubo
        if dh.fixacao == "parafusos":
            e_t = 0.0016
            ctx.geom(corpo, f"helice{k}_tampa", _GRUPO_HELICE, type=cil, size=[dh.r_cubo - 0.0006, 0.5 * e_t, 0],
                     pos=[c[0], c[1], z_tampa + 0.5 * e_t], material=mat["anod"])
            ctx.geom(corpo, f"helice{k}_centro", _GRUPO_HELICE, type=cil, size=[0.003, 0.0003, 0],
                     pos=[c[0], c[1], z_tampa + e_t + 0.0001], material=mat["alu"])
            ctx.geom(corpo, f"helice{k}_parafusos", _GRUPO_HELICE, type=malha, meshname=mh["parafusos"],
                     material=mat["aco"], pos=[c[0], c[1], z_tampa + e_t], quat=_qz(psi0))
        else:
            e_t = 0.0010
            ctx.geom(corpo, f"helice{k}_tampa", _GRUPO_HELICE, type=cil, size=[0.8 * dh.r_cubo, 0.5 * e_t, 0],
                     pos=[c[0], c[1], z_tampa + 0.5 * e_t], material=mat["aco"])
            ctx.geom(corpo, f"helice{k}_porca", _GRUPO_HELICE, type=malha, meshname=mh["porca"],
                     material=mat["aco"], pos=[c[0], c[1], z_tampa + e_t], quat=_qz(psi0))
