"""lab/drone_rpi/detalhes/auditoria.py — AUDITORIA DE REALISMO do detalhe visual (2026-10-20): mede, no modelo que o
simulador compila, o que «verídico» quer dizer para o dono — e diz o que falha.

    MUJOCO_GL=egl .venv/bin/python -m lab.drone_rpi.detalhes.auditoria [--build B] [--json saida.json] [--detalhe]

VERIFICAÇÕES (cada uma com tolerância explícita; os números saem do modelo compilado, não do código que o desenhou)
  F1 parafusos: comprimento da SÉRIE NORMALIZADA da rosca (ISO 4762/7380);
  F2 cabeça ASSENTE: raios paralelos ao eixo, a partir da coroa de apoio da cabeça (entre o furo e a orla), têm de
     bater numa superfície a ≤ 0,35 mm (a cabeça encosta mesmo à peça);
  F3 FURO REAL: um raio ao longo do eixo, da face de apoio até ao fim do aperto, não pode bater em material das peças
     apertadas (o parafuso passa num furo, não atravessa a placa);
  F4 porca ASSENTE e com ROSCA DE FORA: a anilha/porca encosta (raio para trás ≤ 0,35 mm) e o parafuso passa da porca
     ≥ ½ passo;
  C1 cada CABO declarado (`ctx.ligacao`) toca nas suas duas âncoras (≤ 0,5 mm da superfície ou dentro dela);
  C2 a CADEIA DE ENERGIA do computador de bordo existe: pack → XT90 → 10 AWG → placa de energia → BEC 5 V → cabo →
     entrada do computador (o USB-C `rpi5_usbc` do Raspberry Pi 5, ou a âncora que a eletrónica declarar em
     `notas["entrada_computador"]`, por exemplo a do Portenta H7);
  A1 ABRAÇADEIRAS presas: os pontos da face de dentro (`laco` do registo) estão a ≤ 0,25 mm do feixe (raio para o
     centro da fita) — nem folgadas nem a entrar;
  E1 EIXOS das dobradiças/rolamentos/sem-fim declarados (`ctx.eixo`) coincidem com a junta do MuJoCo: ≤ 0,1° e ≤ 0,1 mm
     (ou, sem junta, ficam no corpo que diz);
  P1 todos os geoms visíveis do drone pertencem a uma PEÇA do catálogo (a página 3D mostra-os a todos).
Exit 0 = tudo OK (as verificações sem dados — ex. um build sem cabos declarados — dizem «sem dados», não falham).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import mujoco
import numpy as np

_RAIZ = Path(__file__).resolve().parents[3]
TOL_ASSENTO = 0.35e-3
TOL_LIGACAO = 0.5e-3
TOL_ABRAC = 0.25e-3
GRUPO_FORA = 5


def _modelo(build: str):
    sys.path[:0] = [p for p in (str(_RAIZ),) if p not in sys.path]
    from lab import drone_rpi as dr
    from lab.drone_rpi import modelo

    from . import registo_do_spec
    anterior = os.environ.get("DRONE_DETALHES")
    os.environ["DRONE_DETALHES"] = "todos"
    try:
        hw = dr.hardware(build)
        spec = modelo.construir_spec(hw)
    finally:
        if anterior is None:
            os.environ.pop("DRONE_DETALHES", None)
        else:
            os.environ["DRONE_DETALHES"] = anterior
    reg = registo_do_spec(spec)
    m = spec.compile()
    d = mujoco.MjData(m)
    mujoco.mj_resetData(m, d)
    d.qpos[:3] = [0.0, 0.0, 2.0]
    mujoco.mj_forward(m, d)
    return hw, m, d, reg


def _mundo(m, d, corpo: str, p) -> np.ndarray:
    b = m.body(corpo).id
    return d.xpos[b] + d.xmat[b].reshape(3, 3) @ np.asarray(p, float)


def _dir_mundo(m, d, corpo: str, v) -> np.ndarray:
    b = m.body(corpo).id
    w = d.xmat[b].reshape(3, 3) @ np.asarray(v, float)
    return w / max(float(np.linalg.norm(w)), 1e-12)


class _Raios:
    """mj_ray contra as peças VISÍVEIS (grupos 0–3), sem as ferragens (postas no grupo 5) e sem os geoms dados."""

    def __init__(self, m, d):
        self.m, self.d = m, d
        self.grupo0 = m.geom_group.copy()
        for g in range(m.ngeom):
            nome = m.geom(g).name or ""
            if nome.startswith("fer_") or "abracadeira" in nome or (nome.startswith("fios_") and "nylon" in nome):
                m.geom_group[g] = GRUPO_FORA
            elif float(m.geom_rgba[g, 3]) == 0.0:
                # escondido (variante inativa da troca ao vivo, caixa física representada por um detalhe): não se vê
                # nem existe na peça real — e o `mj_ray` olharia para o alfa do MATERIAL, não para o do geom
                m.geom_group[g] = GRUPO_FORA
        self.mascara = np.array([1, 1, 1, 1, 0, 0], dtype=np.uint8)
        self.gid = np.array([-1], dtype=np.int32)

    def lancar(self, p, v) -> tuple[float, int]:
        v = np.asarray(v, float)
        v = v / max(float(np.linalg.norm(v)), 1e-12)
        dist = mujoco.mj_ray(self.m, self.d, np.asarray(p, float), v, self.mascara, 1, -1, self.gid)
        return float(dist), int(self.gid[0])

    def repor(self):
        self.m.geom_group[:] = self.grupo0


def _ferragens(m, d, reg, raios: _Raios, detalhe: bool) -> dict:
    from .ferragens import (
        COMPRIMENTOS,
        DIAMETRO,
        ISO4032,
        ISO4762,
        ISO7089,
        ISO7380,
        ISO10511,
        PASSO,
    )
    falhas = {"F1": [], "F2": [], "F3": [], "F4": []}
    n = 0
    for r in reg.ferragens:
        if r.get("tipo") != "parafuso":
            continue
        n += 1
        nome = f"{r.get('norma')} {r.get('rosca')}×{r.get('comp_mm'):g} ({r.get('peca')}#{r.get('inst')}, {r.get('modulo')})"
        rosca = r["rosca"]
        if float(r["comp_mm"]) not in [float(x) for x in COMPRIMENTOS.get(rosca, ())]:
            falhas["F1"].append(f"{nome}: {r['comp_mm']} mm não é da série")
        try:
            p0 = _mundo(m, d, r["corpo"], r["ponto"])
            z = _dir_mundo(m, d, r["corpo"], r["eixo"])
        except KeyError:
            continue
        dk = (ISO4762 if r["norma"] == "ISO 4762" else ISO7380)[rosca][0] * 1e-3
        dd = DIAMETRO[rosca] * 1e-3
        h_an = ISO7089[rosca][2] * 1e-3 if r.get("anilha_cabeca") else 0.0
        # base perpendicular ao eixo
        a = np.cross(z, [1.0, 0.0, 0.0] if abs(z[0]) < 0.9 else [0.0, 1.0, 0.0])
        a /= np.linalg.norm(a)
        b = np.cross(z, a)
        r_coroa = 0.5 * (0.5 * dd + 0.5 * dk) + 0.25e-3
        assentes = 0
        for ang in np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False):
            q = p0 + (math.cos(ang) * a + math.sin(ang) * b) * r_coroa - z * 0.3e-3
            dist, _g = raios.lancar(q, z)
            if 0.0 <= dist <= TOL_ASSENTO + 0.3e-3:
                assentes += 1
        if assentes < 4:
            falhas["F2"].append(f"{nome}: cabeça assente em {assentes}/8 raios")
        aperto = r.get("aperto_mm")
        if aperto:
            dist, g = raios.lancar(p0 + z * 0.15e-3, z)
            if 0.0 <= dist < float(aperto) * 1e-3 - 0.3e-3:
                falhas["F3"].append(f"{nome}: o eixo bate em {m.geom(g).name or g} a {dist * 1e3:.2f} mm (sem furo)")
            if r.get("porca"):
                h_p = (ISO10511[rosca][1] if r["porca"] == "ISO 10511" else ISO4032[rosca][1]) * 1e-3
                h_ap = ISO7089[rosca][2] * 1e-3 if r.get("anilha_porca") else 0.0
                sobra = float(r["comp_mm"]) * 1e-3 - (h_an + float(aperto) * 1e-3 + h_ap + h_p)
                if sobra < 0.5 * PASSO[rosca] * 1e-3:
                    falhas["F4"].append(f"{nome}: só {sobra * 1e3:.2f} mm de rosca a sair da porca")
                p_face = p0 + z * float(aperto) * 1e-3
                ok = 0
                for ang in np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False):
                    q = p_face + (math.cos(ang) * a + math.sin(ang) * b) * (0.5 * dd + 0.6e-3) + z * 0.3e-3
                    dist, _g = raios.lancar(q, -z)
                    if 0.0 <= dist <= TOL_ASSENTO + 0.3e-3:
                        ok += 1
                if ok < 4:
                    falhas["F4"].append(f"{nome}: porca/anilha assente em {ok}/8 raios")
    out = {}
    for k, v in falhas.items():
        out[k] = {"total": n, "falhas": len(v), "exemplos": v if detalhe else v[:8]}
    return out


def _dist_geom(m, d, g: int, p) -> float:
    """Distância (m) de um ponto do mundo à caixa do geom no referencial dele (0 se estiver dentro)."""
    R = d.geom_xmat[g].reshape(3, 3)
    q = R.T @ (np.asarray(p, float) - d.geom_xpos[g])
    t = int(m.geom_type[g])
    s = m.geom_size[g]
    if t == int(mujoco.mjtGeom.mjGEOM_MESH):
        mid = int(m.geom_dataid[g])
        va, vn = int(m.mesh_vertadr[mid]), int(m.mesh_vertnum[mid])
        v = m.mesh_vert[va:va + vn]
        lo, hi = v.min(axis=0), v.max(axis=0)
    elif t == int(mujoco.mjtGeom.mjGEOM_BOX):
        lo, hi = -s, s
    elif t in (int(mujoco.mjtGeom.mjGEOM_CYLINDER), int(mujoco.mjtGeom.mjGEOM_CAPSULE)):
        r, h = s[0], s[1] + (s[0] if t == int(mujoco.mjtGeom.mjGEOM_CAPSULE) else 0.0)
        radial = max(0.0, math.hypot(q[0], q[1]) - r)
        axial = max(0.0, abs(q[2]) - h)
        return math.hypot(radial, axial)
    elif t == int(mujoco.mjtGeom.mjGEOM_SPHERE):
        return max(0.0, float(np.linalg.norm(q)) - s[0])
    else:
        lo, hi = -s, s
    fora = np.maximum(lo - q, 0.0) + np.maximum(q - hi, 0.0)
    return float(np.linalg.norm(fora))


def _ligacoes(m, d, reg, detalhe: bool) -> dict:
    falhas = []
    for c in reg.ligacoes:
        for ponta, ancora, corpo, p in ((0, c["de"], c["corpos"][0], c["pontos"][0]), (1, c["para"], c["corpos"][1],
                                                                                        c["pontos"][1])):
            gid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, ancora)
            if gid < 0:
                falhas.append(f"{c['id']}: âncora {ancora!r} não existe")
                continue
            try:
                w = _mundo(m, d, corpo, p)
            except KeyError:
                falhas.append(f"{c['id']}: corpo {corpo!r} não existe")
                continue
            dist = _dist_geom(m, d, gid, w)
            if dist > TOL_LIGACAO:
                falhas.append(f"{c['id']} ponta {ponta}: a {dist * 1e3:.2f} mm de {ancora}")
    return {"total": len(reg.ligacoes), "falhas": len(falhas), "exemplos": falhas if detalhe else falhas[:10]}


# ligações internas (dentro de uma peça: pistas de cobre, contactos que encaixam) — para a cadeia de energia
_INTERNAS = (("conector_xt90", "el_xt90_macho"), ("el_xt90_macho", "el_xt90_copo_pos"),
             ("el_xt90_macho", "el_xt90_copo_neg"), ("el_pdb_bat_pos", "el_pm_5v_pos"),
             ("el_pdb_bat_neg", "el_pm_5v_neg"), ("el_pdb_bat_pos", "el_pm_saida_5v"))


def _cadeia(reg) -> dict:
    viz: dict[str, set] = {}

    def liga(a, b):
        viz.setdefault(a, set()).add(b)
        viz.setdefault(b, set()).add(a)
    for a, b in _INTERNAS:
        liga(a, b)
    origem = set()
    for c in reg.ligacoes:
        liga(c["de"], c["para"])
        if c.get("peca") == "bateria" or str(c["de"]).startswith("el_bat_") or c["id"].startswith("bateria"):
            origem.add(c["de"])
    if not reg.ligacoes:
        return {"estado": "sem dados", "caminho": []}
    alvo = str((getattr(reg, "notas", None) or {}).get("entrada_computador", "rpi5_usbc"))
    from collections import deque
    # começa nos TERMINAIS do pack (as células), se a bateria os declarar
    terminais = sorted(o for o in origem if o.startswith("el_bat_terminal"))
    for o in terminais or sorted(origem):
        pai = {o: None}
        fila = deque([o])
        while fila:
            x = fila.popleft()
            if x == alvo:
                cam = []
                while x is not None:
                    cam.append(x)
                    x = pai[x]
                return {"estado": "ok", "caminho": cam[::-1]}
            for y in viz.get(x, ()):
                if y not in pai:
                    pai[y] = x
                    fila.append(y)
    return {"estado": "falha", "caminho": [], "nota": f"sem caminho de {sorted(origem) or 'nenhuma origem da bateria'} até {alvo}"}


def _abracadeiras(m, d, reg, raios: _Raios, detalhe: bool) -> dict:
    falhas, n = [], 0
    for r in reg.ferragens:
        if r.get("tipo") != "abracadeira" or not r.get("laco"):
            continue
        n += 1
        pts = np.array([_mundo(m, d, r["corpo"], p) for p in r["laco"]])
        c = pts.mean(axis=0)
        piores = []
        for p in pts[:: max(1, len(pts) // 16)]:
            v = c - p
            dist, _g = raios.lancar(p - v / max(np.linalg.norm(v), 1e-12) * 0.1e-3, v)
            piores.append(dist - 0.1e-3 if dist >= 0 else 1.0)
        pior = max(piores)
        if pior > TOL_ABRAC:
            falhas.append(f"abraçadeira {r.get('inst')} ({r.get('corpo')}): folga máx. {pior * 1e3:.2f} mm")
    return {"total": n, "falhas": len(falhas), "exemplos": falhas if detalhe else falhas[:10]}


def _eixos(m, d, reg, detalhe: bool) -> dict:
    falhas, n = [], 0
    for e in reg.eixos:
        if not e.get("junta"):
            continue
        j = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, e["junta"])
        if j < 0:
            falhas.append(f"{e['nome']}: junta {e['junta']} não existe")
            continue
        n += 1
        if e.get("tipo") == "sem-fim":          # o sem-fim é perpendicular ao ombro: só confere que existe e o corpo
            continue
        try:
            p = _mundo(m, d, e["corpo"], e["ponto"])
            u = _dir_mundo(m, d, e["corpo"], e["direcao"])
        except KeyError:
            falhas.append(f"{e['nome']}: corpo {e['corpo']} não existe")
            continue
        uj = d.xaxis[j] / np.linalg.norm(d.xaxis[j])
        ang = math.degrees(math.acos(min(1.0, abs(float(u @ uj)))))
        w = p - d.xanchor[j]
        dist = float(np.linalg.norm(w - (w @ uj) * uj))
        if ang > 0.1 or dist > 0.1e-3:
            falhas.append(f"{e['nome']} vs {e['junta']}: {ang:.3f}°, {dist * 1e3:.3f} mm")
    return {"total": n, "falhas": len(falhas), "exemplos": falhas if detalhe else falhas[:10]}


def _sem_peca(m, reg) -> dict:
    from .exportar import _FORA, _peca_por_nome
    bid = m.body("drone").id
    nomes = []
    for g in range(m.ngeom):
        b = int(m.geom_bodyid[g])
        a = b
        while a not in (0, bid):
            a = int(m.body_parentid[a])
        if a != bid or float(m.geom_rgba[g, 3]) == 0.0:
            continue
        nome = m.geom(g).name or f"geom{g}"
        if _FORA.match(nome) or nome in reg.faixas or nome in reg.geoms:
            continue
        pp = _peca_por_nome(nome)
        if pp is None or pp[0] in ("outros", "estrutura", "cablagem", "ferragens"):
            nomes.append(nome)
    return {"total": m.ngeom, "falhas": len(nomes), "exemplos": nomes[:20]}


def auditar(build: str, detalhe: bool = False) -> dict:
    _hw, m, d, reg = _modelo(build)
    if reg is None:
        return {"build": build, "erro": "sem registo (detalhes desligados?)"}
    raios = _Raios(m, d)
    try:
        res = {"build": build,
               **_ferragens(m, d, reg, raios, detalhe),
               "C1": _ligacoes(m, d, reg, detalhe),
               "C2": _cadeia(reg),
               "A1": _abracadeiras(m, d, reg, raios, detalhe),
               "E1": _eixos(m, d, reg, detalhe),
               "P1": _sem_peca(m, reg)}
    finally:
        raios.repor()
    res["ok"] = all((v.get("falhas", 0) == 0) for k, v in res.items() if isinstance(v, dict) and k != "C2") and \
        res["C2"]["estado"] in ("ok", "sem dados")
    return res


NOMES = {"F1": "parafusos: comprimento normalizado", "F2": "parafusos: cabeça assente", "F3": "parafusos: passam num furo",
         "F4": "porcas assentes e rosca de fora", "C1": "cabos tocam nas âncoras", "C2": "cadeia de energia do computador",
         "A1": "abraçadeiras presas (folga ≤ 0,25 mm)", "E1": "eixos = juntas do MuJoCo", "P1": "geoms com peça"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", action="append", default=None)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--detalhe", action="store_true")
    a = ap.parse_args(argv)
    builds = a.build or ["articulado_15pol_mn5006", "endurance_15pol_p50b"]
    todos, ok = [], True
    for b in builds:
        r = auditar(b, a.detalhe)
        todos.append(r)
        print(f"[auditoria] {b}")
        for k in ("F1", "F2", "F3", "F4", "C1", "C2", "A1", "E1", "P1"):
            v = r.get(k)
            if v is None:
                continue
            if k == "C2":
                print(f"   {k} {NOMES[k]:40s} {v['estado']}  {' → '.join(v.get('caminho', []))}{v.get('nota', '')}")
                continue
            estado = "sem dados" if v["total"] == 0 else ("OK" if v["falhas"] == 0 else f"{v['falhas']} FALHA(S)")
            print(f"   {k} {NOMES[k]:40s} {v['total']:5d}  {estado}")
            for ex in v["exemplos"][: (50 if a.detalhe else 4)]:
                print(f"        · {ex}")
        ok = ok and bool(r.get("ok"))
    if a.json:
        a.json.write_text(json.dumps(todos, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[auditoria] " + ("TUDO OK" if ok else "HÁ FALHAS"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
