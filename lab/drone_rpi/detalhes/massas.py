"""lab/drone_rpi/detalhes/massas.py — MASSAS e CUSTOS realistas do drone, peça a peça, medidos na GEOMETRIA (2026-10-20).

    .venv/bin/python -m lab.drone_rpi.detalhes.massas [--build B] [--json saida.json] [--atualizar-catalogo]

Pedido do dono: «mude os nossos cálculos de peso para ficarem realistas» e «a página tem de apresentar os modelos para
imprimir das peças 3D e os seus custos». Cada peça do registo (`detalhes.registo_do_spec`) recebe a massa pela regra que
corresponde ao que ela É:

  · IMPRESSA em ABS (material com «abs» no nome; malha FECHADA): como um slicer — paredes de `PAREDE_MM` + enchimento
    `ENCHIMENTO` do interior: m = ρ_ABS · (min(V, A·t) + f·(V − min(V, A·t))), ρ_ABS = 1,04 g/cm³; tempo de impressão =
    volume impresso / `TAXA_CM3_H`; custo = m · preço do filamento;
  · TUBO de carbono/alumínio (`notas["tubos"]`, ou o tubo pelo nome): comprimento × secção anelar × densidade;
  · FERRAGEM (parafuso, porca, anilha, pilar, anel, perno, amortecedor): volume da malha COMPLETA das normas × densidade
    do material (aço 7,85 · latão 8,5 · nylon 1,14 · alumínio 2,70 · silicone 1,10);
  · CABO (fios_*): volume do tubo varrido × 2,2 g/cm³ (cobre + silicone; 10 AWG = 45 g/m, 16 AWG = 15 g/m, 22 AWG ≈ 4 g/m);
    abraçadeiras de nylon pelo volume × 1,14;
  · COMPRADA com ficha (motor, hélice, ESC, Pi, FC, câmara, sensores, bateria, servos/motorredutores, encoders,
    reguladores — `COMPRADAS_FICHA`): a massa do CATÁLOGO (a da ficha do fabricante — a geometria visual não é maciça
    como a peça real);
  · o resto das peças mecânicas (tubos de carbono, veios, rolamentos, porca, fuso, acoplamento, colares): volume da
    geometria × densidade do material (carbono 1,55 · aço 7,85 · latão 8,5 · alumínio 2,70 …).

`--atualizar-catalogo` escreve as massas medidas do build `articulado_15pol_abs` no catálogo (frame, pernas, ombro,
fuso, cotovelo, mastro, reguladores, extra), marcadas como «medido na geometria» — o simulador usa-as (a física passa a
ter o peso real das peças). Só depois de o desenho estar fechado (o teste `teste_ombro_fuso.py` confere o orçamento).
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

RHO = {"abs": 1.04, "pla": 1.24, "petg": 1.27, "carbono": 1.55, "aluminio": 2.70, "aco": 7.85, "latao": 8.50,
       "bronze": 8.80, "cobre": 8.96, "nylon": 1.14, "silicone": 1.10, "borracha": 1.20, "fr4": 1.85, "cabo": 2.20,
       "pvc": 1.38, "titanio": 4.43}
PAREDE_MM = 1.2          # 3 perímetros de 0,4 mm (e 5 camadas de 0,2 mm em cima/baixo)
ENCHIMENTO = 0.40        # peças estruturais
TAXA_CM3_H = 12.0        # volume impresso por hora (bico 0,4 mm, ABS ~50 mm/s) — afinado pela pesquisa
PRECO_ABS_USD_KG = 20.0  # filamento ABS 1 kg (substituído pela pesquisa se `PRECOS` trouxer outro)
CAMBIO_USD_BRL = 5.5     # substituído pela pesquisa

# peças compradas cuja massa vem da FICHA do catálogo (não da geometria visual, que não é maciça)
COMPRADAS_FICHA = {"motor", "helice", "esc", "rpi5", "fc", "pdb", "camera", "sensor_fluxo", "sensor_tof", "bateria",
                   "ombro_motor", "ombro_servo", "cotovelo_servo", "ombro_encoder", "cotovelo_encoder", "portenta", "imu",
                   "fonte_servos", "cablagem"}

# peças compradas mecânicas sem ficha no catálogo (g, por unidade)
MASSAS_COMPRADAS_G = {"608zz": 12.0, "688zz": 3.0, "6800zz": 6.0, "685zz": 1.6, "684zz": 1.0, "686zz": 2.6,
                      "colar_8mm": 6.0, "iman_6x2_5": 0.5, "inserto_m3": 0.25}


def _material_de(nome_mat: str) -> str:
    n = (nome_mat or "").lower()
    if "abs" in n:
        return "abs"
    for chave, mat in (("carbono", "carbono"), ("latao", "latao"), ("bronze", "bronze"), ("cobre", "cobre"),
                       ("nylon", "nylon"), ("silicone", "silicone"), ("borracha", "borracha"), ("aluminio", "aluminio"),
                       ("alu_", "aluminio"), ("alu", "aluminio"), ("inox", "aco"), ("aco", "aco"), ("mola", "aco"),
                       ("titanio", "titanio"), ("pcb", "fr4"), ("petg", "petg")):
        if chave in n:
            return mat
    return ""


def volume_area(v: np.ndarray, f: np.ndarray) -> tuple[float, float, float]:
    """(volume m³ com sinal, área m², desequilíbrio |Σ n·A| / Σ A) — o desequilíbrio ≈ 0 numa malha fechada."""
    if len(f) == 0:
        return 0.0, 0.0, 1.0
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    cr = np.cross(b - a, c - a)
    area = 0.5 * float(np.linalg.norm(cr, axis=1).sum())
    vol = float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)
    deseq = float(np.linalg.norm(0.5 * cr.sum(axis=0))) / max(area, 1e-15)
    return vol, area, deseq


def massa_impressa_g(vol_m3: float, area_m2: float) -> tuple[float, float]:
    """(massa g, volume impresso cm³) de uma peça impressa: paredes + enchimento (modelo de slicer)."""
    V = abs(vol_m3) * 1e6                     # cm³
    A = area_m2 * 1e4                         # cm²
    casca = min(V, A * PAREDE_MM / 10.0)
    impresso = casca + ENCHIMENTO * (V - casca)
    return RHO["abs"] * impresso, impresso


def _primitiva_volume_area(tipo: int, s) -> tuple[float, float]:
    G = mujoco.mjtGeom
    if tipo == int(G.mjGEOM_BOX):
        a, b, c = 2 * s[0], 2 * s[1], 2 * s[2]
        return a * b * c, 2 * (a * b + b * c + a * c)
    if tipo == int(G.mjGEOM_CYLINDER):
        r, h = s[0], 2 * s[1]
        return math.pi * r * r * h, 2 * math.pi * r * (r + h)
    if tipo == int(G.mjGEOM_CAPSULE):
        r, h = s[0], 2 * s[1]
        return math.pi * r * r * h + 4.0 / 3.0 * math.pi * r ** 3, 2 * math.pi * r * h + 4 * math.pi * r * r
    if tipo == int(G.mjGEOM_SPHERE):
        return 4.0 / 3.0 * math.pi * s[0] ** 3, 4 * math.pi * s[0] ** 2
    if tipo == int(G.mjGEOM_ELLIPSOID):
        a, b, c = s
        p = 1.6075
        return 4.0 / 3.0 * math.pi * a * b * c, 4 * math.pi * (((a * b) ** p + (a * c) ** p + (b * c) ** p) / 3) ** (1 / p)
    return 0.0, 0.0


def _tri_geom(m, g: int, faces=None):
    mid = int(m.geom_dataid[g])
    va, vn = int(m.mesh_vertadr[mid]), int(m.mesh_vertnum[mid])
    fa, fn = int(m.mesh_faceadr[mid]), int(m.mesh_facenum[mid])
    v = np.asarray(m.mesh_vert[va:va + vn], float)
    f = np.asarray(m.mesh_face[fa:fa + fn], np.int64)
    if faces is not None:
        f = f[faces[0]:faces[1]]
    return v, f


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
    return hw, spec.compile(), reg


def bom(build: str | None = None, hw=None, m=None, reg=None) -> dict:
    """A lista de materiais com MASSA (e volume/tempo das impressas) por peça × instância."""
    from . import ferragens as fer
    if hw is None:
        hw, m, reg = _modelo(build)
    pecas: dict[str, dict] = {}

    def item(peca: str, inst: int) -> dict:
        ch = f"{peca}#{inst}"
        if ch not in pecas:
            pecas[ch] = {"peca": peca, "inst": int(inst), "massa_g": 0.0, "impressa_g": 0.0, "ferragens_g": 0.0,
                         "volume_cm3": 0.0,
                         "impresso_cm3": 0.0, "area_cm2": 0.0, "aberta": False, "origem": set(), "materiais": set()}
        return pecas[ch]

    # ---------------------------------------------------------------- geometria (impressas, cabos, metal à vista)
    reg_g = reg.geoms if reg else {}
    reg_f = reg.faixas if reg else {}
    tubos = (reg.notas.get("tubos", {}) if reg else {}) or {}
    for g in range(m.ngeom):
        nome = m.geom(g).name or ""
        if float(m.geom_rgba[g, 3]) == 0.0 or nome.startswith(("fer_", "arma_", "chao", "caminho_tiro", "projetil")):
            continue
        mid = int(m.geom_matid[g])
        nome_mat = m.material(mid).name if mid >= 0 else ""
        mat = _material_de(nome_mat)
        partes = []
        if nome in reg_f and int(m.geom_type[g]) == int(mujoco.mjtGeom.mjGEOM_MESH):
            for peca, inst, f0, f1 in reg_f[nome]:
                partes.append((peca, inst, (f0, f1)))
        elif nome in reg_g:
            peca, inst = reg_g[nome]
            partes.append((peca, inst, None))
        else:
            continue
        for peca, inst, faixa in partes:
            it = item(peca, inst)
            if int(m.geom_type[g]) == int(mujoco.mjtGeom.mjGEOM_MESH):
                v, f = _tri_geom(m, g, faixa)
                vol, area, deseq = volume_area(v, f)
            else:
                vol, area = _primitiva_volume_area(int(m.geom_type[g]), m.geom_size[g])
                deseq = 0.0
            if mat == "abs":
                mg, imp = massa_impressa_g(vol, area)
                it["impressa_g"] += mg
                it["impresso_cm3"] += imp
                it["volume_cm3"] += abs(vol) * 1e6
                it["area_cm2"] += area * 1e4
                it["aberta"] |= deseq > 2e-3
                it["origem"].add("geometria ABS")
            elif nome.startswith("fios_") or "_fios_" in nome:   # (os troços que rodam com o atuador: `…_fuso_base_fios_*`)
                # a manga entrançada desenha-se como um tubo cheio que LEVA as 3 fases: 3 × 16 AWG (7 mm² de cobre +
                # silicone) dentro de Ø8–9 mm ⇒ ~0,8 g/cm³ efetivos; os outros cabos são cobre + silicone (2,2 g/cm³)
                rho = RHO["nylon"] if "nylon" in nome_mat else (0.8 if "manga" in nome_mat else RHO["cabo"])
                it["massa_g"] += abs(vol) * 1e6 * rho
                it["origem"].add("cabo (volume × densidade)")
            elif mat and peca not in COMPRADAS_FICHA and f"{peca}#{int(inst)}" not in tubos:
                it["massa_g"] += abs(vol) * 1e6 * RHO[mat]
                it["origem"].add(f"geometria × {mat} {RHO[mat]:g} g/cm³")
            it["materiais"].add(nome_mat)
    # ---------------------------------------------------------------- tubos declarados
    for ch, t in tubos.items():
        peca, _, inst = ch.partition("#")
        it = item(peca, int(inst or 0))
        L = float(t.get("comprimento_mm", 0.0)) / 10.0
        R, r = 0.05 * float(t.get("d_ext_mm", 0.0)), 0.05 * float(t.get("d_int_mm", 0.0))
        it["massa_g"] += math.pi * (R * R - r * r) * L * RHO.get(t.get("material", "carbono"), RHO["carbono"])
        it["origem"].add("tubo (comprimento × secção)")
    # ---------------------------------------------------------------- ferragens
    cache: dict[str, float] = {}
    rho_fer = {"fer_aco_preto": "aco", "fer_aco_inox": "aco", "fer_aco_zincado": "aco", "fer_latao": "latao",
               "fer_aluminio": "aluminio", "fer_aluminio_preto": "aluminio", "fer_aluminio_vermelho": "aluminio",
               "fer_nylon_branco": "nylon", "fer_nylon_preto": "nylon", "fer_nylon_azul": "nylon", "fer_mola": "aco",
               "fer_titanio": "titanio"}
    for r in (reg.ferragens if reg else []):
        if r.get("peca") == "carga_util":
            continue
        it = item(r.get("peca", "ferragens"), int(r.get("inst", 0)))
        if r.get("tipo") == "abracadeira":
            L = float(r.get("comp_mm", 100.0))
            m_ab = 0.0022 * L * float(r.get("largura_mm", 2.5)) / 2.5   # 2,5 × 100 mm ≈ 0,22 g
            it["massa_g"] += m_ab
            it["ferragens_g"] += m_ab
            it["origem"].add("abraçadeira")
            continue
        ch = fer.chave(r)
        if ch not in cache:
            tot = 0.0
            for mat, v, f in fer.malha_completa(r):
                vol, _a, _d = volume_area(v, f)
                tot += abs(vol) * 1e6 * RHO.get(rho_fer.get(mat, "aco"), RHO["aco"])
            cache[ch] = tot
        it["massa_g"] += cache[ch]
        it["ferragens_g"] += cache[ch]
        it["origem"].add("ferragens (norma × densidade)")
    # ---------------------------------------------------------------- arrumar
    for it in pecas.values():
        it["massa_g"] += it["impressa_g"]
        it["tempo_h"] = it["impresso_cm3"] / TAXA_CM3_H
        it["origem"] = sorted(it["origem"])
        it["materiais"] = sorted(x for x in it["materiais"] if x)
        for k in ("massa_g", "impressa_g", "ferragens_g", "volume_cm3", "impresso_cm3", "area_cm2", "tempo_h"):
            it[k] = round(float(it[k]), 3)
    return {"build": getattr(hw, "nome", build), "pecas": pecas,
            "parametros": {"rho_abs_g_cm3": RHO["abs"], "parede_mm": PAREDE_MM, "enchimento": ENCHIMENTO,
                           "taxa_cm3_h": TAXA_CM3_H}}


# peça do registo → grupo do orçamento físico do simulador (`Hardware.massas`); o que não estiver aqui vai para «extra»
GRUPO_FISICO = {
    "placa_inferior": "frame", "placa_superior": "frame", "espacadores": "frame", "tubo_braco": "frame",
    "abracadeira_tubo": "frame", "trelica": "frame", "estrutura": "frame",
    "perna": "pernas",
    "ombro_caixa": "redutor_ombro", "ombro_semfim": "redutor_ombro", "ombro_veio": "redutor_ombro",
    "ombro_encoder": "redutor_ombro", "ombro_servo": "redutor_ombro", "ombro_motor": "redutor_ombro",
    "cotovelo_servo": "redutor_cotovelo", "cotovelo_berco": "redutor_cotovelo", "cotovelo_encoder": "redutor_cotovelo",
    "ombro_cubo": "dobradica", "cotovelo_garfo": "dobradica",
    "mastro": "mastro", "suporte_motor": "mastro", "motor": "mastro", "helice": "mastro",
}


def orcamento_fisico(r: dict) -> dict:
    """Soma as massas medidas por grupo do orçamento físico (g): frame, pernas, por braço o redutor do ombro/cotovelo,
    as dobradiças e o mastro, e o «extra» (cabos, abraçadeiras, ferragens e suportes da eletrónica, cintas)."""
    g = {"frame": 0.0, "pernas": 0.0, "redutor_ombro": 0.0, "redutor_cotovelo": 0.0, "dobradica": 0.0, "mastro": 0.0,
         "extra": 0.0}
    for p in r["pecas"].values():
        g[GRUPO_FISICO.get(p["peca"], "extra")] += p["massa_g"]
    return {k: round(v, 1) for k, v in g.items()}


# grupos do catálogo que o `--atualizar-catalogo` escreve (build acessível): peça → (grupo, divisor por unidade)
GRUPOS_CATALOGO = {
    "frame": ("placa_inferior", "placa_superior", "espacadores", "tubo_braco", "abracadeira_tubo", "trelica", "estrutura",
              "insertos"),
    "pernas": ("perna",),
    "ombro_redutor": ("ombro_forquilha", "ombro_veio", "ombro_cubo", "ombro_suporte"),
    "fuso_atuador": ("ombro_bloco", "ombro_fuso"),
    "fuso_carro": ("ombro_porca",),
    "cotovelo_redutor": ("cotovelo_berco", "cotovelo_garfo"),
    "mastro": ("mastro", "suporte_motor"),
    "fonte_servos": ("bandeja_fonte", "suporte_driver"),
}


def massas_catalogo(r: dict) -> dict:
    """As massas (g) a escrever no catálogo, por grupo: as do frame/pernas totais, as do braço POR UNIDADE (÷ 4), e o
    «extra» = tudo o que não é peça com ficha nem está noutro grupo (cabos, abraçadeiras, suportes, ferragens soltas)."""
    soma: dict[str, float] = {k: 0.0 for k in GRUPOS_CATALOGO}
    grupo_de = {pid: g for g, pids in GRUPOS_CATALOGO.items() for pid in pids}
    extra = 0.0
    for p in r["pecas"].values():
        g = grupo_de.get(p["peca"])
        if g is not None:
            soma[g] += p["massa_g"]
        elif p["peca"] not in COMPRADAS_FICHA:
            extra += p["massa_g"]
        else:                                     # peça com ficha: a massa dela é a da ficha, mas os PARAFUSOS que a
            extra += p["ferragens_g"]             # prendem (e as abraçadeiras) não estão na ficha
    por_braco = ("ombro_redutor", "fuso_atuador", "fuso_carro", "cotovelo_redutor", "mastro")
    out = {k: round(v / (4.0 if k in por_braco else 1.0), 1) for k, v in soma.items()}
    out["extra"] = round(extra, 1)
    return out


def atualizar_catalogo(build: str, valores: dict, raiz: Path = _RAIZ) -> dict:
    """Escreve `valores` (de `massas_catalogo`) no catálogo e no build (o simulador passa a usá-los). Devolve as
    alterações {campo: (antes, depois)}."""
    fc, fb = raiz / "models" / "drone_rpi" / "componentes.json", raiz / "models" / "drone_rpi" / "builds.json"
    cat = json.loads(fc.read_text(encoding="utf-8"))
    bds = json.loads(fb.read_text(encoding="utf-8"))
    b = bds["builds"][build]
    fr = cat["frames"][b["frame"]]
    mec = cat["mecanismos_braco"][b["bracos"]]
    nota = "medido na geometria (lab/drone_rpi/detalhes/massas.py, 2026-10-20)"
    mud = {}

    def por(obj, chave, valor, rotulo):
        mud[rotulo] = (obj.get(chave), valor)
        obj[chave] = valor
    por(fr, "massa_g", valores["frame"], "frame.massa_g")
    por(fr, "massa_pernas_g", valores["pernas"], "frame.massa_pernas_g")
    fr["confianca"] = nota
    por(mec["ombro"], "massa_redutor_g", valores["ombro_redutor"], "ombro.massa_redutor_g")
    if mec["ombro"].get("fuso"):
        por(mec["ombro"]["fuso"], "massa_atuador_g", valores["fuso_atuador"], "fuso.massa_atuador_g")
        por(mec["ombro"]["fuso"], "massa_carro_g", valores["fuso_carro"], "fuso.massa_carro_g")
    por(mec["cotovelo"], "massa_redutor_g", valores["cotovelo_redutor"], "cotovelo.massa_redutor_g")
    por(mec["mastro"], "massa_g", valores["mastro"], "mastro.massa_g")
    por(mec, "massa_dobradica_g", 0.0, "massa_dobradica_g")
    fs = mec.setdefault("fonte_servos", {})
    eletr = float(fs.get("massa_eletronica_g", fs.get("massa_g", 0.0) if "massa_eletronica_g" not in fs else 0.0))
    fs.setdefault("massa_eletronica_g", eletr)
    por(fs, "massa_g", round(fs["massa_eletronica_g"] + valores["fonte_servos"], 1), "fonte_servos.massa_g")
    por(b, "massa_extra_g", valores["extra"], "build.massa_extra_g")
    mec.setdefault("estimado", {})["massas"] = nota + " — ver `python -m lab.drone_rpi.detalhes.massas`"
    fc.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fb.write_text(json.dumps(bds, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return mud


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", default="articulado_15pol_abs")
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--atualizar-catalogo", action="store_true",
                    help="escreve as massas medidas no catálogo e no build (só o build acessível)")
    a = ap.parse_args(argv)
    r = bom(a.build)
    tot = sum(p["massa_g"] for p in r["pecas"].values())
    imp = sum(p["impressa_g"] for p in r["pecas"].values())
    print(f"[massas] {r['build']}: {len(r['pecas'])} peças×instância com massa medida — {tot:.0f} g "
          f"(dos quais {imp:.0f} g impressos em ABS)")
    por: dict[str, float] = {}
    for p in r["pecas"].values():
        por[p["peca"]] = por.get(p["peca"], 0.0) + p["massa_g"]
    for k, v in sorted(por.items(), key=lambda t: -t[1])[:40]:
        print(f"   {k:24s} {v:8.1f} g")
    print("   orçamento físico (g):", orcamento_fisico(r))
    abertas = [k for k, p in r["pecas"].items() if p["aberta"]]
    if abertas:
        print("   ⚠ malhas impressas ABERTAS (volume aproximado):", ", ".join(abertas[:12]))
    valores = massas_catalogo(r)
    print("   para o catálogo (g; braço = por unidade):", valores)
    if a.atualizar_catalogo:
        if a.build != "articulado_15pol_abs":
            print("[massas] --atualizar-catalogo só para o build acessível (articulado_15pol_abs)")
            return 2
        for campo, (antes, depois) in atualizar_catalogo(a.build, valores).items():
            print(f"   {campo:28s} {antes!s:>8s} → {depois}")
    if a.json:
        a.json.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
