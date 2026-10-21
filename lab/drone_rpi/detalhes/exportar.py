"""lab/drone_rpi/detalhes/exportar.py — exporta o drone, PEÇA A PEÇA, para a página 3D do cockpit (`/pecas`).

    .venv/bin/python -m lab.drone_rpi.detalhes.exportar [--build B] [--saida f.json] [--resumo]

O JSON sai do MESMO modelo que o simulador compila (`modelo.construir_spec` com os detalhes) — a página mostra exatamente
as peças que voam: a árvore de corpos com as juntas (as dobradiças mexem-se na página como no MuJoCo), as malhas (as
fundidas por corpo × material cortadas pelas faixas de faces de cada peça, que o MuJoCo 3.15 preserva ao compilar), as
primitivas, os materiais, as FERRAGENS (uma malha completa por tipo — «ISO 4762 M3×8 aço preto» — e uma instância por
parafuso, com a haste inteira roscada que no simulador fica escondida dentro das peças), os cabos com as âncoras, os
eixos e as peças alternativas da troca ao vivo. Os textos (nome, especificações reais, «como funciona», passos de
montagem) vêm de `pecas.py`.

Formato (`versao` 1): números em metros; vetores binários em base64 (float32 / uint16|uint32, little-endian).
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import mujoco
import numpy as np

_RAIZ = Path(__file__).resolve().parents[3]

TIPOS = {int(mujoco.mjtGeom.mjGEOM_BOX): "box", int(mujoco.mjtGeom.mjGEOM_CYLINDER): "cylinder",
         int(mujoco.mjtGeom.mjGEOM_CAPSULE): "capsule", int(mujoco.mjtGeom.mjGEOM_SPHERE): "sphere",
         int(mujoco.mjtGeom.mjGEOM_ELLIPSOID): "ellipsoid", int(mujoco.mjtGeom.mjGEOM_MESH): "mesh"}

# fora da página: o chão, os efeitos do tiro, o disco translúcido das hélices (ajuda visual do cockpit) e a ARMA inteira
# (a página das peças é do drone; o dono não quer a arma nela — pedido de 2026-10-20)
_FORA = re.compile(r"^(chao$|caminho_tiro_|projetil_tiro_|arma_|helice\d+$)")
PECAS_FORA = {"carga_util"}

# peça de cada geom SEM registo (as peças com massa que se veem e os nomes antigos), pela ordem
_REGRAS_NOME = (
    (r"^ombro(\d)_carro$", "ombro_porca", 1),
    (r"^(el_rpi5|rpi5_)", "rpi5", None),
    (r"^el_ponte_fc", "fc", None),
    (r"^el_fc_", "fc", None),
    (r"^(el_pdb_|el_pm_|el_cablagem)", "pdb", None),
    (r"^el_esc(\d)_", "esc", 1),
    (r"^el_esc4_", "esc", None),
    (r"^el_cam_", "camera", None),
    (r"^(el_bat_|conector_xt90|el_xt90|cinta_bateria|el_cinta)", "bateria", None),
    (r"^el_fonte24", "fonte_servos", None),
    (r"^el_fluxo", "sensor_fluxo", None),
    (r"^el_tof", "sensor_tof", None),
    (r"^el_bandeja", "bandeja_sensores", None),
    (r"^el_portenta", "portenta", None),
    (r"^el_imu", "imu", None),
    (r"^motor(\d)", "motor", 1),
    (r"^helice(\d)_", "helice", 1),
    (r"^placa_superior", "placa_superior", None),
    (r"^placa$", "placa_inferior", None),
    (r"^espacador_placa_(\d)", "espacadores", None),
    (r"^suporte_motor_(\d)", "suporte_motor", 1),
    (r"^trelica_estab_(\d)", "trelica", 1),
    (r"^(est_|m_est_)", "estrutura", None),
    (r"^fios_", "cablagem", None),
    (r"^fer_", "ferragens", None),
    (r"^(esc(\d)?|bateria|camera|sensores_baixo|fonte_servos|el_rpi5|el_fc_h7|el_arduino_portenta_h7)$", "outros", None),
)


def _b64(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")


def _indices(f: np.ndarray, nv: int) -> dict:
    if nv < 65535:
        return {"i": _b64(f.astype("<u2").ravel()), "itipo": "u16"}
    return {"i": _b64(f.astype("<u4").ravel()), "itipo": "u32"}


def _peca_por_nome(nome: str) -> tuple[str, int] | None:
    for padrao, peca, grupo in _REGRAS_NOME:
        mt = re.match(padrao, nome)
        if mt:
            inst = int(mt.group(grupo)) if grupo and mt.lastindex and mt.group(grupo) else 0
            return peca, inst
    return None


def _material_info(m: mujoco.MjModel, mid: int) -> dict:
    tex = None
    tid = int(m.mat_texid[mid, int(mujoco.mjtTextureRole.mjTEXROLE_RGB)])
    if tid >= 0:
        nome_t = m.texture(tid).name
        tex = "carbono" if ("carbono" in nome_t or "tecido" in nome_t) else "espiras" if "espiras" in nome_t else nome_t
    return {"rgba": [round(float(x), 4) for x in m.mat_rgba[mid]], "specular": round(float(m.mat_specular[mid]), 3),
            "shininess": round(float(m.mat_shininess[mid]), 3), "reflectance": round(float(m.mat_reflectance[mid]), 3),
            "emission": round(float(m.mat_emission[mid]), 3), "textura": tex}


def _arred(v, n=6) -> list:
    return [round(float(x), n) for x in v]


def exportar(build: str | None = None, cockpit: bool = True, saida_stl: Path | None = None) -> dict:
    """O dicionário da página 3D para o `build` (omissão: o que o cockpit voa — `BUILD_COCKPIT_OMISSAO` do sim_site,
    o articulado — ou o build ativo do catálogo com `cockpit=False`). Com `saida_stl`, escreve também o ZIP com os
    STL das peças impressas (`impressao.pacote`) — o que a página descarrega."""
    from lab import drone_rpi as dr
    from lab.drone_rpi import modelo

    from . import ferragens as fer
    from . import pecas as cat
    from . import registo_do_spec
    if build is None:
        build = "articulado_15pol_abs" if cockpit else dr.nome_build_ativo()
    t0 = time.perf_counter()
    hw = dr.hardware(build)
    anterior = os.environ.get("DRONE_DETALHES")
    os.environ["DRONE_DETALHES"] = "todos"                 # a página mostra o drone COMPLETO (e repõe-se a seguir:
    try:                                                    # o servidor do cockpit corre isto no seu processo)
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
    mujoco.mj_forward(m, d)
    bid_drone = m.body("drone").id

    # ---------------------------------------------------------------- corpos e juntas (só a subárvore do drone)
    corpos, idx_corpo = [], {}
    for b in range(m.nbody):
        a = b
        while a not in (0, bid_drone):
            a = int(m.body_parentid[a])
        if a != bid_drone:
            continue
        pai = int(m.body_parentid[b])
        junta = None
        for j in range(m.njnt):
            if int(m.jnt_bodyid[j]) == b and int(m.jnt_type[j]) == int(mujoco.mjtJoint.mjJNT_HINGE):
                lim = m.jnt_range[j]
                junta = {"nome": m.joint(j).name, "eixo": _arred(m.jnt_axis[j]), "pos": _arred(m.jnt_pos[j]),
                         "limites_graus": [round(math.degrees(float(lim[0])), 3), round(math.degrees(float(lim[1])), 3)]
                         if m.jnt_limited[j] else None}
        idx_corpo[b] = len(corpos)
        corpos.append({"nome": m.body(b).name, "pai": idx_corpo.get(pai, -1) if b != bid_drone else -1,
                       "pos": _arred(m.body_pos[b]) if b != bid_drone else [0.0, 0.0, 0.0],
                       "quat": _arred(m.body_quat[b]) if b != bid_drone else [1.0, 0.0, 0.0, 0.0], "junta": junta})

    # ---------------------------------------------------------------- materiais
    materiais = {}

    def mat_nome(g: int) -> str | None:
        mid = int(m.geom_matid[g])
        if mid < 0:
            return None
        nome = m.material(mid).name
        if nome not in materiais:
            materiais[nome] = _material_info(m, mid)
        return nome

    # ---------------------------------------------------------------- malhas e geoms
    malhas, idx_malha = [], {}
    n_tri = 0

    def malha_de(mesh_id: int) -> int:
        nonlocal n_tri
        if mesh_id in idx_malha:
            return idx_malha[mesh_id]
        va, vn = int(m.mesh_vertadr[mesh_id]), int(m.mesh_vertnum[mesh_id])
        fa, fn = int(m.mesh_faceadr[mesh_id]), int(m.mesh_facenum[mesh_id])
        v = np.asarray(m.mesh_vert[va:va + vn], dtype="<f4")
        f = np.asarray(m.mesh_face[fa:fa + fn], dtype=np.int64)
        item = {"nv": vn, "nf": fn, "v": _b64(v.ravel()), **_indices(f, vn)}
        ta, tn = int(m.mesh_texcoordadr[mesh_id]), int(m.mesh_texcoordnum[mesh_id])
        if ta >= 0 and tn == vn and np.array_equal(np.asarray(m.mesh_facetexcoord[fa:fa + fn]), f):
            item["uv"] = _b64(np.asarray(m.mesh_texcoord[ta:ta + tn], dtype="<f4").ravel())
        idx_malha[mesh_id] = len(malhas)
        malhas.append(item)
        n_tri += fn
        return idx_malha[mesh_id]

    regs_geoms = reg.geoms if reg is not None else {}
    regs_faixas = reg.faixas if reg is not None else {}
    geoms, sem_peca = [], {}
    prefixos_anim = []
    for g in range(m.ngeom):
        b = int(m.geom_bodyid[g])
        if b not in idx_corpo:
            continue
        nome = m.geom(g).name or f"geom{g}"
        if _FORA.match(nome) or nome.startswith("fer_"):      # as ferragens vão como instâncias (abaixo)
            continue
        rgba = m.geom_rgba[g]
        mid = int(m.geom_matid[g])
        alfa = float(rgba[3]) if mid < 0 or list(rgba) != [0.5, 0.5, 0.5, 1.0] else float(m.mat_rgba[mid, 3])
        if float(rgba[3]) == 0.0:
            continue                                          # peça com massa escondida (o detalhe representa-a)
        tipo = TIPOS.get(int(m.geom_type[g]))
        if tipo is None:
            continue
        base = {"corpo": idx_corpo[b], "nome": nome, "tipo": tipo, "size": _arred(m.geom_size[g]),
                "pos": _arred(m.geom_pos[g]), "quat": _arred(m.geom_quat[g]), "material": mat_nome(g),
                "grupo": int(m.geom_group[g])}
        if mid < 0 or list(rgba) != [0.5, 0.5, 0.5, 1.0]:
            base["rgba"] = _arred(rgba, 4)
        _ = alfa
        mt = re.match(r"^(helice|motor)(\d)_", nome)
        if mt and (nome.startswith((f"helice{mt.group(2)}_", f"motor{mt.group(2)}_raio"))):
            base["anim"] = {"tipo": "rotor", "k": int(mt.group(2))}
        mt = re.match(r"^semfim(\d)_rotor", nome)
        if mt:
            base["anim"] = {"tipo": "semfim", "k": int(mt.group(1))}
        mt = re.match(r"^ombro(\d)_fuso_(base|veio|porca)", nome)
        if mt:
            base["anim"] = {"tipo": "biela", "k": int(mt.group(1)), "papel": mt.group(2)}
        if tipo == "mesh":
            base["malha"] = malha_de(int(m.geom_dataid[g]))
        if nome in regs_faixas and tipo == "mesh":
            for peca, inst, f0, f1 in regs_faixas[nome]:
                if peca in PECAS_FORA:
                    continue
                geoms.append({**base, "faces": [int(f0), int(f1)], "peca": peca, "inst": int(inst)})
            continue
        pi = regs_geoms.get(nome) or _peca_por_nome(nome)
        if pi is not None and pi[0] in PECAS_FORA:
            continue
        if pi is None:
            pi = ("outros", 0)
            sem_peca[nome] = True
        geoms.append({**base, "peca": pi[0], "inst": int(pi[1])})
    _ = prefixos_anim

    # ---------------------------------------------------------------- ferragens: tipos (malha completa) + instâncias
    tipos_fer, inst_fer = {}, []
    if reg is not None:
        for r in reg.ferragens:
            corpo = r.get("corpo", "drone")
            try:
                b = m.body(corpo).id
            except KeyError:
                continue
            if b not in idx_corpo:
                continue
            if r.get("peca") in PECAS_FORA:
                continue
            if r.get("tipo") == "abracadeira":            # geometria própria (nos fios): só a lista
                ch = f"abracadeira {r.get('largura_mm', 2.5):g}×{r.get('comp_mm', 100):g}"
                tipos_fer.setdefault(ch, {"descricao": r.get("descricao") or f"Abraçadeira de nylon {ch}",
                                          "tipo": "abracadeira", "malhas": [], "qtd": 0})
                tipos_fer[ch]["qtd"] += 1
                continue
            ch = fer.chave(r)
            if ch not in tipos_fer:
                partes = []
                for mat, v, f in fer.malha_completa(r):
                    if mat not in materiais and mat in fer.MATERIAIS:
                        rgba, sp, br, rf = fer.MATERIAIS[mat]
                        materiais[mat] = {"rgba": list(rgba), "specular": sp, "shininess": br, "reflectance": rf,
                                          "emission": 0.0, "textura": None}
                    partes.append({"material": mat, "nv": len(v), "nf": len(f),
                                   "v": _b64(np.asarray(v, dtype="<f4").ravel()), **_indices(f, len(v))})
                    n_tri += len(f)
                binario = fer.BINARIO_NM.get((r.get("rosca"), fer.MATERIAL_TIPO.get(r.get("material", ""), "aco")))
                tipos_fer[ch] = {"descricao": fer.descricao(r), "tipo": r["tipo"], "norma": r.get("norma"),
                                 "rosca": r.get("rosca"), "comp_mm": r.get("comp_mm"), "material": r.get("material"),
                                 "binario_nm": binario, "malhas": partes, "qtd": 0}
            tipos_fer[ch]["qtd"] += 1
            # `desenhada` = o Coletor desenhou-a (instância na página); False = a peça que a usa já a desenha (a cabeça
            # à vista, ou a ferragem que gira com o sem-fim/a hélice): conta na lista mas não se instancia por cima
            inst_fer.append({"tipo": ch, "corpo": idx_corpo[b], "pos": _arred(r["ponto"]),
                             "quat": _arred(r.get("quat", [1, 0, 0, 0])), "peca": r.get("peca", "ferragens"),
                             "inst": int(r.get("inst", 0)), "modulo": r.get("modulo", ""),
                             "desenhada": bool(r.get("desenhada", True))})

    # ---------------------------------------------------------------- metadados das peças e dos passos
    presentes: dict[str, set] = {}
    for gm in geoms:
        presentes.setdefault(gm["peca"], set()).add(gm["inst"])
    for it in inst_fer:
        presentes.setdefault(it["peca"], set()).add(it["inst"])
    meta = cat.catalogo(hw, sorted(presentes))
    passos = cat.passos(hw, sorted(presentes))
    for p_ in passos:                                          # ferragens de cada passo (contadas do modelo)
        conta: dict[str, int] = {}
        for it in inst_fer:
            if it["peca"] in p_["pecas"] or it.get("passo") == p_["id"]:
                conta[it["tipo"]] = conta.get(it["tipo"], 0) + 1
        p_["ferragens"] = [{"tipo": k, "qtd": v, "descricao": tipos_fer[k]["descricao"],
                            "binario_nm": tipos_fer[k].get("binario_nm")} for k, v in sorted(conta.items())]
    for pid, inst in presentes.items():
        if pid in meta:
            meta[pid]["instancias"] = sorted(inst)
            meta[pid]["quantidade"] = max(1, len(inst))
    # ---------------------------------------------------------------- massas medidas, impressão 3D e custos
    from . import massas as ms
    from . import precos as pr
    lista = ms.bom(hw=hw, m=m, reg=reg)
    notas_imp = (reg.notas.get("impressas", {}) if reg is not None else {}) or {}
    impressas = {}
    for ch, it in lista["pecas"].items():
        if it["peca"] in PECAS_FORA or it["impressa_g"] <= 0.0:
            continue
        info = notas_imp.get(ch, {})
        impressas[ch] = {"peca": it["peca"], "inst": it["inst"], "nome": info.get("nome", ""),
                         "orientacao": info.get("orientacao", [1.0, 0.0, 0.0, 0.0]), "nota": info.get("nota", ""),
                         "massa_g": round(it["impressa_g"], 1), "volume_cm3": round(it["volume_cm3"], 2),
                         "impresso_cm3": round(it["impresso_cm3"], 2), "tempo_h": round(it["tempo_h"], 2),
                         "aberta": bool(it["aberta"]),
                         "custo_usd": round(it["impressa_g"] / 1000.0 * pr.preco_filamento_usd_kg(), 2)}
    from . import impressao as im
    pac = im.pacote(m, d, reg, hw.nome, excluir=PECAS_FORA, nomes={k: v.get("nome", k) for k, v in meta.items()})
    for ch, r in pac["pecas"].items():
        if ch in impressas:
            impressas[ch].update({c: r[c] for c in ("arquivo", "dims_mm", "cabe_mesa", "fechada", "copias",
                                                    "instancias_iguais", "orientacao_auto", "triangulos")})
    if saida_stl is not None:
        tmp = Path(saida_stl).with_name(Path(saida_stl).name + f".{os.getpid()}.tmp")
        tmp.write_bytes(im.zip_bytes(pac["ficheiros"]))
        tmp.replace(saida_stl)
    custos = pr.custos(hw, meta, lista, inst_fer, tipos_fer, impressas)
    for pid, e in custos.get("extras", {}).items():           # compras sem peça desenhada neste build
        if pid not in meta:
            meta[pid] = {"nome": e["nome"], "categoria": e["categoria"], "resumo": "Compra sem modelo 3D neste build.",
                         "como_funciona": "", "porque": cat.PORQUE.get(pid, ""), "specs": [], "fontes": [],
                         "instancias": [], "quantidade": 0, "sem_modelo": True}
    for pid, f in meta.items():
        f["massa_medida_g"] = round(sum(it["massa_g"] for it in lista["pecas"].values() if it["peca"] == pid), 1)
        f["impressa"] = any(v["peca"] == pid for v in impressas.values())
        f["custo"] = custos["por_peca"].get(pid)
    # bielas dos ombros de fuso (a geometria do catálogo — a mesma da física e da animação da planta)
    bielas = []
    fz = getattr(getattr(getattr(hw, "bracos", None), "ombro", None), "fuso", None)
    if fz is not None:
        for k in range(1, 5):
            try:
                bb = m.body(f"braco{k}")
            except KeyError:
                continue
            h = np.array(bb.pos, dtype=float)
            a_v, b_v = fz.vetores(math.copysign(1.0, h[0]), math.copysign(1.0, h[1]))
            bielas.append({"k": k, "junta": f"ombro{k}", "corpo_base": idx_corpo.get(int(m.body_parentid[bb.id]), 0),
                           "corpo_braco": idx_corpo.get(int(bb.id), -1), "h": _arred(h), "a": _arred(a_v),
                           "b": _arred(b_v), "passo": float(fz.passo)})
    rotores = []
    giro = list(getattr(hw, "GIRO", (1, 1, 1, 1)))
    for k in range(1, 5):
        sid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SITE, f"r{k}")
        if sid < 0 or int(m.site_bodyid[sid]) not in idx_corpo:
            continue
        rotores.append({"k": k, "giro": int(giro[k - 1]) if k - 1 < len(giro) else 1,
                        "corpo": idx_corpo[int(m.site_bodyid[sid])], "centro": _arred(m.site_pos[sid])})
    ligacoes = [c for c in (reg.ligacoes if reg is not None else []) if c.get("peca") not in PECAS_FORA
                and not str(c.get("de", "")).startswith("arma_") and not str(c.get("para", "")).startswith("arma_")]
    eixos = list(reg.eixos) if reg is not None else []
    variantes = {k: (v if isinstance(v, dict) else {"geoms": list(v)}) for k, v in (reg.variantes if reg else {}).items()}
    dados = {
        "versao": 1,
        "build": hw.nome,
        "massa_total_g": round(1000.0 * float(hw.massa_total), 1),
        "gerado": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "materiais": materiais,
        "malhas": malhas,
        "corpos": corpos,
        "geoms": geoms,
        "pecas": meta,
        "categorias": cat.CATEGORIAS,
        "ferragens": {"tipos": tipos_fer, "instancias": inst_fer},
        "ligacoes": ligacoes,
        "eixos": eixos,
        "variantes": variantes,
        "rotores": rotores,
        "impressas": impressas,
        "impressao": {"mesa_mm": list(im.MESA_MM), "definicoes": im.DEFINICOES,
                      "zip": f"pecas_impressas_{hw.nome}.zip"},
        "bielas": bielas,
        "custos": custos,
        "massas_parametros": lista["parametros"],
        "passos": passos,
        "estatisticas": {"geoms": len(geoms), "malhas": len(malhas), "triangulos": int(n_tri),
                         "ferragens": len(inst_fer), "pecas": len(meta), "sem_peca": sorted(sem_peca)[:50],
                         "segundos": round(time.perf_counter() - t0, 2)},
    }
    return dados


def exportar_bytes(build: str | None = None, comprimir: bool = True) -> tuple[bytes, str]:
    """(corpo, etag) — o JSON em UTF-8 (gzip se `comprimir`)."""
    dados = exportar(build)
    bruto = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    etag = hashlib.sha1(bruto).hexdigest()[:16]
    return (gzip.compress(bruto, 6) if comprimir else bruto), etag


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", default=None)
    ap.add_argument("--saida", type=Path, default=None)
    ap.add_argument("--resumo", action="store_true", help="só as estatísticas e a lista de peças")
    ap.add_argument("--gzip", action="store_true", help="--saida em gzip (o que o sim_site.py serve)")
    ap.add_argument("--stl-zip", type=Path, default=None, help="escreve também o ZIP com os STL das peças impressas")
    a = ap.parse_args(argv)
    sys.path[:0] = [p for p in (str(_RAIZ),) if p not in sys.path]
    dados = exportar(a.build, saida_stl=a.stl_zip)
    if a.saida:
        bruto = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        tmp = a.saida.with_name(a.saida.name + f".{os.getpid()}.tmp")
        tmp.write_bytes(gzip.compress(bruto, 6) if a.gzip else bruto)
        tmp.replace(a.saida)                                 # escrita atómica: quem lê nunca vê meio ficheiro
        print(f"[exportar] {a.saida} ({a.saida.stat().st_size / 1e6:.2f} MB) etag={hashlib.sha1(bruto).hexdigest()[:16]}")
    est = dados["estatisticas"]
    print(f"[exportar] {dados['build']}: {est['geoms']} geoms, {est['malhas']} malhas, {est['triangulos']} triângulos, "
          f"{est['ferragens']} ferragens, {est['pecas']} peças em {est['segundos']} s")
    if a.resumo:
        for pid, p in dados["pecas"].items():
            print(f"  · {pid:22s} ×{p.get('quantidade', 1)}  {p.get('nome', '')}")
        if est["sem_peca"]:
            print("  sem peça:", ", ".join(est["sem_peca"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
