"""lab/drone_rpi/detalhes/impressao.py — os MODELOS PARA IMPRIMIR (STL) das peças do drone impressas em ABS (2026-10-20).

    .venv/bin/python -m lab.drone_rpi.detalhes.impressao [--build B] [--zip saida.zip] [--material abs]

Pedido do dono: «a página que vejo as partes do drone tem de me apresentar os modelos para imprimir das peças 3D e os
seus custos». Cada peça × instância impressa sai como um STL binário em MILÍMETROS (a unidade que os fatiadores
assumem), tirado do MESMO modelo que o simulador compila:

  · as malhas de material ABS dessa peça (as faixas de faces das malhas fundidas — o registo dos detalhes — e as
    primitivas), no referencial do corpo principal da peça, na pose de referência (juntas a 0);
  · DEITADA na face de apoio: a de `notas["impressas"][peça#inst]["orientacao"]` (quaternion do corpo para a posição de
    impressão) quando o módulo a declarou; senão a maior face plana que toca no plano de apoio — o «colocar na face»
    dos fatiadores —, rodada em torno de z para a menor pegada e centrada na mesa;
  · VERIFICADA: malha fechada (cada aresta em exatamente 2 triângulos, com os sentidos opostos, depois de soldar os
    vértices coincidentes), volume positivo (normais para fora) e que cabe na mesa de uma impressora de mesa comum
    (`MESA_MM` = 220 × 220 × 250 mm, a da Ender-3).

As cópias iguais (os 4 ombros de um lado, …) saem num ficheiro só, com a quantidade a imprimir. O ZIP leva também um
LEIA-ME com as definições de impressão e a lista (peça, quantidade, massa, tempo, medidas).
"""
from __future__ import annotations

import argparse
import io
import math
import re
import struct
import sys
import zipfile
from pathlib import Path

import mujoco
import numpy as np

MESA_MM = (220.0, 220.0, 250.0)
ABS = re.compile(r"(?:^|_)abs(?:_|$)", re.IGNORECASE)
DEFINICOES = (
    "ABS · bico 0,4 mm · camada 0,2 mm · 3 perímetros (1,2 mm) · 5 camadas em cima e em baixo · enchimento 40 % "
    "(giroide) · bico 240–250 °C · mesa 100 °C · caixa FECHADA, sem correntes de ar (o ABS empena) · sem suportes "
    "salvo indicação · insertos de latão M3 cravados a quente (~220 °C) nos furos de Ø4,0")


# ------------------------------------------------------------------------------------------------- malhas
def _torno(perfil: list[tuple[float, float]], n: int = 48) -> tuple[np.ndarray, np.ndarray]:
    """Sólido de revolução fechado em torno de z: `perfil` = [(r, z)] do polo de baixo (r = 0) ao de cima (r = 0)."""
    anel = perfil[1:-1]
    phi = np.arange(n) * (2 * math.pi / n)
    c, s = np.cos(phi), np.sin(phi)
    V = [np.array([[0.0, 0.0, perfil[0][1]]])]
    for r, z in anel:
        V.append(np.stack([r * c, r * s, np.full(n, z)], axis=1))
    V.append(np.array([[0.0, 0.0, perfil[-1][1]]]))
    V = np.concatenate(V)
    topo = len(V) - 1
    F = []
    j = np.arange(n)
    j1 = (j + 1) % n
    F.append(np.stack([np.zeros(n, int), 1 + j1, 1 + j], axis=1))            # leque de baixo (normal para baixo)
    for i in range(len(anel) - 1):
        a, b = 1 + i * n + j, 1 + i * n + j1
        cc, dd = 1 + (i + 1) * n + j1, 1 + (i + 1) * n + j
        F.append(np.stack([a, b, cc], axis=1))
        F.append(np.stack([a, cc, dd], axis=1))
    k = 1 + (len(anel) - 1) * n
    F.append(np.stack([np.full(n, topo), k + j, k + j1], axis=1))            # leque de cima (normal para cima)
    return V, np.concatenate(F).astype(np.int64)


def malha_primitiva(tipo: int, s) -> tuple[np.ndarray, np.ndarray]:
    """Triângulos (normais para fora) de uma primitiva do MuJoCo, no referencial do geom."""
    G = mujoco.mjtGeom
    if tipo == int(G.mjGEOM_BOX):
        a, b, c = (float(x) for x in s[:3])
        V = np.array([[-a, -b, -c], [a, -b, -c], [a, b, -c], [-a, b, -c],
                      [-a, -b, c], [a, -b, c], [a, b, c], [-a, b, c]])
        F = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                      [2, 3, 7], [2, 7, 6], [0, 4, 7], [0, 7, 3], [1, 2, 6], [1, 6, 5]])
        return V, F
    if tipo == int(G.mjGEOM_CYLINDER):
        r, h = float(s[0]), float(s[1])
        return _torno([(0.0, -h), (r, -h), (r, h), (0.0, h)])
    th = np.linspace(0.0, math.pi, 17)
    if tipo == int(G.mjGEOM_CAPSULE):
        r, h = float(s[0]), float(s[1])
        baixo = [(r * math.sin(t), -h - r * math.cos(t)) for t in th[:9]]
        cima = [(r * math.sin(t), h - r * math.cos(t)) for t in th[8:]]
        return _torno(baixo + cima)
    if tipo in (int(G.mjGEOM_SPHERE), int(G.mjGEOM_ELLIPSOID)):
        V, F = _torno([(math.sin(t), -math.cos(t)) for t in th])
        esc = np.array([s[0], s[0], s[0]] if tipo == int(G.mjGEOM_SPHERE) else s[:3], float)
        return V * esc, F
    return np.zeros((0, 3)), np.zeros((0, 3), np.int64)


def _soldar(V: np.ndarray, tol: float = 1e-6) -> np.ndarray:
    _, inv = np.unique(np.round(V / tol).astype(np.int64), axis=0, return_inverse=True)
    return inv.reshape(-1)


def manifold(V: np.ndarray, F: np.ndarray) -> bool:
    """A superfície é uma variedade fechada e orientada TOPOLOGICAMENTE? (soldados os vértices coincidentes, cada aresta
    orientada aparece uma vez e a oposta também). Uma malha geometricamente fechada com «junções em T» (furos e faces
    triangulados de lados diferentes) falha aqui e passa em `fechada`: os fatiadores reparam-nas sozinhos."""
    if len(F) == 0:
        return False
    w = _soldar(V)[F]
    w = w[(w[:, 0] != w[:, 1]) & (w[:, 1] != w[:, 2]) & (w[:, 0] != w[:, 2])]
    if len(w) == 0:
        return False
    e = np.concatenate([w[:, [0, 1]], w[:, [1, 2]], w[:, [2, 0]]])
    n = int(w.max()) + 1
    k = e[:, 0] * n + e[:, 1]
    u, cont = np.unique(k, return_counts=True)
    if (cont != 1).any():
        return False
    return bool(np.isin(e[:, 1] * n + e[:, 0], u).all())


def fechada(V: np.ndarray, F: np.ndarray) -> bool:
    """A superfície fecha GEOMETRICAMENTE e com as normais para fora? (a soma vetorial das áreas é ~0 — numa malha
    aberta sobra a área do buraco — e o volume com sinal é positivo): é o que dá o volume certo e o que o fatiador
    precisa para saber o que é «dentro»."""
    from .massas import volume_area
    vol, _area, deseq = volume_area(V, F)
    return bool(vol > 0.0 and deseq < 1e-4)


def _quat_mat(q) -> np.ndarray:
    R = np.zeros(9)
    mujoco.mju_quat2Mat(R, np.asarray(q, float) / max(np.linalg.norm(q), 1e-12))
    return R.reshape(3, 3)


def _rot_para(n: np.ndarray, alvo=(0.0, 0.0, -1.0)) -> np.ndarray:
    """Rotação que leva a direção `n` para `alvo` (Rodrigues)."""
    a = n / np.linalg.norm(n)
    b = np.asarray(alvo, float)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-12:
        if c > 0:
            return np.eye(3)
        eixo = np.array([1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        eixo = eixo - a * np.dot(eixo, a)
        eixo /= np.linalg.norm(eixo)
        return 2 * np.outer(eixo, eixo) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * (1.0 / (1.0 + c))


def face_de_apoio(V: np.ndarray, F: np.ndarray) -> tuple[np.ndarray, float]:
    """(normal, área m²) da maior face plana que toca no plano de apoio — a candidata a ficar na mesa."""
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    cr = np.cross(b - a, c - a)
    ar = 0.5 * np.linalg.norm(cr, axis=1)
    ok = ar > 1e-12
    nrm = np.zeros_like(cr)
    nrm[ok] = cr[ok] / (2 * ar[ok, None])
    chave = np.round(nrm[ok] * 2000).astype(np.int64)
    _u, inv = np.unique(chave, axis=0, return_inverse=True)
    soma = np.bincount(inv.reshape(-1), weights=ar[ok])
    melhor, n_melhor = -1.0, np.array([0.0, 0.0, -1.0])
    idx_ok = np.nonzero(ok)[0]
    for i in np.argsort(-soma)[:40]:
        sel = idx_ok[inv.reshape(-1) == i]
        n = nrm[sel].mean(axis=0)
        n /= np.linalg.norm(n)
        h = float((V @ n).max())
        toca = np.all(np.stack([a[sel] @ n, b[sel] @ n, c[sel] @ n], axis=1) > h - 5e-5, axis=1)
        area = float(ar[sel][toca].sum())
        if area > melhor * 1.0001:
            melhor, n_melhor = area, n
    return n_melhor, melhor


def _pegada(P: np.ndarray, mesa=MESA_MM) -> tuple[float, tuple[float, float]]:
    """(ângulo em torno de z, (x, y) mm) — a menor pegada; entre as que cabem na mesa, a menor."""
    xy = P[:, :2]
    melhor = None
    for g in range(180):
        t = math.radians(g)
        c, s = math.cos(t), math.sin(t)
        x = xy[:, 0] * c - xy[:, 1] * s
        y = xy[:, 0] * s + xy[:, 1] * c
        dx, dy = float(x.max() - x.min()), float(y.max() - y.min())
        cabe = max(dx, dy) <= max(mesa[:2]) and min(dx, dy) <= min(mesa[:2])
        cand = (not cabe, dx * dy, g, (dx, dy))
        if melhor is None or cand[:2] < melhor[:2]:
            melhor = cand
    return math.radians(melhor[2]), melhor[3]


# ------------------------------------------------------------------------------------------------- peças
def indice(m: mujoco.MjModel, reg, material=ABS) -> dict[str, list[tuple[int, tuple[int, int] | None]]]:
    """{«peça#inst»: [(geom, faixa de faces | None)]} das partes de material `material` (as visíveis)."""
    out: dict[str, list] = {}
    faixas = getattr(reg, "faixas", {}) or {}
    geoms = getattr(reg, "geoms", {}) or {}
    for g in range(m.ngeom):
        if float(m.geom_rgba[g, 3]) == 0.0:
            continue
        mid = int(m.geom_matid[g])
        if mid < 0 or not material.search(m.material(mid).name or ""):
            continue
        nome = m.geom(g).name or ""
        if nome in faixas and int(m.geom_type[g]) == int(mujoco.mjtGeom.mjGEOM_MESH):
            for peca, inst, f0, f1 in faixas[nome]:
                out.setdefault(f"{peca}#{int(inst)}", []).append((g, (int(f0), int(f1))))
        elif nome in geoms:
            peca, inst = geoms[nome]
            out.setdefault(f"{peca}#{int(inst)}", []).append((g, None))
    return out


def triangulos(m: mujoco.MjModel, d: mujoco.MjData, partes) -> tuple[np.ndarray, np.ndarray, int]:
    """(V m, F, corpo principal): os triângulos das `partes` no referencial do corpo com mais faces (pose de `d`)."""
    blocos, nf_corpo = [], {}
    for g, faixa in partes:
        if int(m.geom_type[g]) == int(mujoco.mjtGeom.mjGEOM_MESH):
            mid = int(m.geom_dataid[g])
            va, vn = int(m.mesh_vertadr[mid]), int(m.mesh_vertnum[mid])
            fa, fn = int(m.mesh_faceadr[mid]), int(m.mesh_facenum[mid])
            V = np.asarray(m.mesh_vert[va:va + vn], float)
            F = np.asarray(m.mesh_face[fa:fa + fn], np.int64)
            if faixa is not None:
                F = F[faixa[0]:faixa[1]]
            usados = np.unique(F)
            mapa = np.full(vn, -1, np.int64)
            mapa[usados] = np.arange(len(usados))
            V, F = V[usados], mapa[F]
        else:
            V, F = malha_primitiva(int(m.geom_type[g]), m.geom_size[g])
        R = np.asarray(d.geom_xmat[g], float).reshape(3, 3)
        blocos.append((g, V @ R.T + d.geom_xpos[g], F))
        b = int(m.geom_bodyid[g])
        nf_corpo[b] = nf_corpo.get(b, 0) + len(F)
    corpo = max(nf_corpo, key=nf_corpo.get) if nf_corpo else 0
    Rb = np.asarray(d.xmat[corpo], float).reshape(3, 3)
    pb = np.asarray(d.xpos[corpo], float)
    Vs, Fs, base = [], [], 0
    for _g, Vw, F in blocos:
        Vs.append((Vw - pb) @ Rb)
        Fs.append(F + base)
        base += len(Vw)
    if not Vs:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64), corpo
    return np.concatenate(Vs), np.concatenate(Fs), corpo


def stl_binario(V_mm: np.ndarray, F: np.ndarray, titulo: str) -> bytes:
    tri = V_mm[F].astype(np.float64)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1)
    n[ln > 0] /= ln[ln > 0, None]
    rec = np.zeros(len(F), dtype=[("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"] = n
    rec["v"] = tri
    cab = ("drone " + titulo).encode("ascii", "replace")[:80].ljust(80, b" ")
    return cab + struct.pack("<I", len(F)) + rec.tobytes()


def preparar(V: np.ndarray, F: np.ndarray, orientacao=None, mesa=MESA_MM) -> dict:
    """Orienta (face de apoio para −z), roda para a menor pegada e centra; devolve V em mm e o diagnóstico."""
    from .massas import massa_impressa_g, volume_area
    vol, area, _ = volume_area(V, F)
    if orientacao is not None:
        R = _quat_mat(orientacao)
        auto = False
    else:
        n, _area = face_de_apoio(V, F)
        R = _rot_para(n)
        auto = True
    P = V @ R.T
    t, _dims = _pegada(P, mesa)
    c, s = math.cos(t), math.sin(t)
    Rz = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    P = P @ Rz.T * 1000.0
    lo, hi = P.min(axis=0), P.max(axis=0)
    P = P - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    dims = (P.max(axis=0) - P.min(axis=0)).tolist()
    mg, impresso = massa_impressa_g(vol, area)
    cabe = (max(dims[0], dims[1]) <= max(mesa[:2]) + 1e-6 and min(dims[0], dims[1]) <= min(mesa[:2]) + 1e-6
            and dims[2] <= mesa[2] + 1e-6)
    return {"V_mm": P, "dims_mm": [round(x, 1) for x in dims], "cabe_mesa": bool(cabe), "fechada": fechada(V, F),
            "manifold": manifold(V, F),
            "volume_cm3": round(vol * 1e6, 3), "massa_g": round(mg, 2), "impresso_cm3": round(impresso, 3),
            "orientacao_auto": auto, "triangulos": len(F)}


def mesma_peca(V1: np.ndarray, F1: np.ndarray, V2: np.ndarray, F2: np.ndarray, tol: float = 2e-5) -> bool:
    """As duas cópias são a MESMA peça (a 2.ª = a 1.ª rodada e deslocada, sem espelho)? Os módulos geram as cópias com
    o mesmo código, por isso os vértices vêm pela mesma ordem: Kabsch nos vértices correspondentes, resíduo < `tol` e
    det(R) = +1 (uma peça espelhada NÃO é a mesma: imprime-se à parte)."""
    if V1.shape != V2.shape or F1.shape != F2.shape or not np.array_equal(F1, F2):
        return False
    c1, c2 = V1.mean(axis=0), V2.mean(axis=0)
    h = (V1 - c1).T @ (V2 - c2)
    u, _s, vt = np.linalg.svd(h)
    r = vt.T @ u.T
    if np.linalg.det(r) < 0.0:
        return False
    return bool(np.abs((V1 - c1) @ r.T - (V2 - c2)).max() < tol)


def pacote(m: mujoco.MjModel, d: mujoco.MjData, reg, build: str, material=ABS, mesa=MESA_MM,
           excluir: set[str] | frozenset = frozenset(), nomes: dict | None = None) -> dict:
    """As peças impressas do modelo: {"pecas": {«peça#inst»: diagnóstico + ficheiro}, "ficheiros": {nome: bytes}}."""
    notas = (getattr(reg, "notas", {}) or {}).get("impressas", {}) or {}
    grupos: dict[str, list[list[str]]] = {}                 # peça → [[chaves iguais], …]
    info: dict[str, dict] = {}
    malhas: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    locais: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for ch, partes in sorted(indice(m, reg, material).items(), key=lambda t: (t[0].split("#")[0], int(t[0].split("#")[1]))):
        peca, _, inst = ch.partition("#")
        if peca in excluir:
            continue
        V, F, corpo = triangulos(m, d, partes)
        if len(F) == 0:
            continue
        ori = (notas.get(ch) or {}).get("orientacao")
        r = preparar(V, F, ori, mesa)
        r.update(peca=peca, inst=int(inst), corpo=m.body(corpo).name)
        malhas[ch] = (r.pop("V_mm"), F)
        locais[ch] = (V, F)
        info[ch] = r
        lista = grupos.setdefault(peca, [])
        for chs in lista:
            if mesma_peca(*locais[chs[0]], V, F):
                chs.append(ch)
                break
        else:
            lista.append([ch])
    ficheiros: dict[str, bytes] = {}
    for peca, lista in grupos.items():
        for chs in lista:
            primeira = chs[0]
            nome = f"{peca}.stl" if len(lista) == 1 else f"{peca}_n{info[primeira]['inst']}.stl"
            P, F = malhas[primeira]
            ficheiros[nome] = stl_binario(P, F, f"{build} {primeira} ABS mm")
            for ch in chs:
                info[ch].update(arquivo=nome, igual_a=primeira, copias=len(chs),
                                instancias_iguais=[info[x]["inst"] for x in chs])
    ficheiros["LEIA-ME.txt"] = leia_me(build, info, nomes or {}, mesa).encode("utf-8")
    return {"pecas": info, "ficheiros": ficheiros}


def leia_me(build: str, info: dict, nomes: dict, mesa=MESA_MM) -> str:
    linhas = [f"Peças impressas em ABS do drone — build {build}", "",
              "Definições de impressão (todas as peças):", "  " + DEFINICOES, "",
              (f"Cada STL está em milímetros, já deitado na face de apoio e centrado. Mesa de referência "
               f"{mesa[0]:.0f} × {mesa[1]:.0f} × {mesa[2]:.0f} mm."), "",
              "ficheiro                         qtd   g/un   h/un*   medidas (mm)            notas"]
    vistos = set()
    for _ch, r in sorted(info.items(), key=lambda t: t[1]["arquivo"]):
        if r["arquivo"] in vistos:
            continue
        vistos.add(r["arquivo"])
        nota = []
        if not r["fechada"]:
            nota.append("MALHA ABERTA (verificar no fatiador)")
        if not r["cabe_mesa"]:
            nota.append("NÃO CABE na mesa de referência")
        dims = " × ".join(f"{x:.0f}" for x in r["dims_mm"])
        linhas.append(f"{r['arquivo']:32s} {r['copias']:3d}  {r['massa_g']:6.1f}  {r['impresso_cm3'] / 12.0:5.1f}   "
                      f"{dims:22s}  {'; '.join(nota)}")
        if nomes.get(r["peca"]):
            linhas.append(f"    {nomes[r['peca']]}")
    linhas += ["", "* tempo estimado a ~12 cm³/h de plástico depositado (bico 0,4 mm); o fatiador dá o valor exato."]
    return "\n".join(linhas) + "\n"


def zip_bytes(ficheiros: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for nome in sorted(ficheiros):
            zi = zipfile.ZipInfo(nome, date_time=(2026, 10, 20, 0, 0, 0))   # data fixa: o mesmo modelo → o mesmo ZIP
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, ficheiros[nome])
    return buf.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", default="articulado_15pol_abs")
    ap.add_argument("--zip", type=Path, default=None)
    ap.add_argument("--material", default=None, help="regex do nome do material (omissão: as peças de ABS)")
    a = ap.parse_args(argv)
    from .massas import _modelo
    hw, m, reg = _modelo(a.build)
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    mat = re.compile(a.material, re.IGNORECASE) if a.material else ABS
    r = pacote(m, d, reg, hw.nome, mat)
    print(f"[impressao] {hw.nome}: {len(r['pecas'])} peças × instância impressas, "
          f"{len(r['ficheiros']) - 1} STL diferentes")
    for ch, x in sorted(r["pecas"].items()):
        print(f"   {ch:24s} {x['arquivo']:28s} {x['massa_g']:7.1f} g  {' × '.join(f'{v:.0f}' for v in x['dims_mm']):>18s} mm"
              f"  {'fechada' if x['fechada'] else 'ABERTA'}  {'cabe' if x['cabe_mesa'] else 'NÃO CABE'}"
              f"  {'auto' if x['orientacao_auto'] else 'declarada'}")
    if a.zip:
        a.zip.write_bytes(zip_bytes(r["ficheiros"]))
        print(f"[impressao] {a.zip} ({a.zip.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
