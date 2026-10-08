#!/usr/bin/env python3
"""inspect_model.py — compila um modelo MuJoCo (MJCF/URDF/.mjb) e entrega um RELATÓRIO + checagens de risco + teste de fumaça.

    python3 .agents/mujoco-agent-skill/scripts/inspect_model.py models/triangulo_invertido.xml
    python3 .agents/mujoco-agent-skill/scripts/inspect_model.py robot.xml --tree --steps 2000
    python3 .agents/mujoco-agent-skill/scripts/inspect_model.py robot.xml --json > relatorio.json
    python3 .agents/mujoco-agent-skill/scripts/inspect_model.py robot.xml --no-smoke        # só compilar e listar

O que mostra: contagens (nq, nv, nu, nactuator, nbody, ngeom…), opções físicas, massa total, árvore de corpos/juntas (--tree), atuadores
(inclui entradas de controle e ranges), sensores, tipos de geom e parâmetros de contato; RISCOS (WARN) como timeconst < 2·timestep,
corpo móvel sem massa, razão de massas alta, atuador sem ctrlrange, ctrl multi-entrada; e um teste de fumaça de N passos com controle zero
(NaN, deriva de energia, avisos do mjData, penetração máxima, velocidades).
Exit: 0 compila e passou · 1 compila com WARN de risco alto/instável · 2 erro de compilação/uso.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

try:
    import mujoco
except ImportError:
    sys.exit("Erro: pacote mujoco ausente — Solução: rode com a venv do projeto (.venv/bin/python) ou `uv sync`.")

HINTS = {
    "moving bodies must be larger than mjMINVAL": "corpo móvel sem massa/inércia: dê <geom> com size/density/mass, ou <inertial pos mass diaginertia/> (geoms com mass=0 não contam)",
    "unrecognized attribute": "atributo inexistente ou REMOVIDO em 3.15 — confira com docs_search.py --attr elem.attr e --changelog <nome>",
    "unrecognized element": "elemento inexistente ou removido em 3.15 — confira com docs_search.py --elem <nome>",
    "Error opening file": "arquivo não encontrado: confira caminho relativo ao XML principal e <compiler meshdir/texturedir>",
    "XML parse error": "XML malformado (tag não fechada, aspas, & sem escape)",
    "mesh": "malha: verifique `file`/`meshdir`, ou ≥ 4 `vertex` não coplanares; use <compiler meshdir=…>",
    "repeated name": "nomes devem ser únicos por tipo de elemento (body, geom, joint…)",
    "Nan, Inf or huge value": "instabilidade numérica: reduza timestep, aumente solref timeconst, use integrator implicitfast",
    "actdim": "combinação de recursos do atuador incompatível em 3.15 (ex.: pid com ki>0 e slewmax>0 ao mesmo tempo)",
}


def nm(model, typ, i) -> str:
    n = mujoco.mj_id2name(model, typ, i)
    return n if n else f"#{i}"


def enum_name(enum, v) -> str:
    for k, e in enum.__members__.items():
        if int(e) == int(v):
            return k
    return str(v)


def build(path: Path):
    try:
        if path.suffix == ".mjb":
            return mujoco.MjModel.from_binary_path(str(path)), None
        return mujoco.MjModel.from_xml_path(str(path)), None
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        hint = next((h for k, h in HINTS.items() if k in msg), "leia a mensagem acima; docs_search.py \"<termo do erro>\" costuma achar a regra")
        return None, f"{msg.strip()}\n  → Solução: {hint}"


def summarize(model: mujoco.MjModel) -> dict:
    o = model.opt
    d = {
        "contagens": {k: int(getattr(model, k)) for k in ("nq", "nv", "nu", "nactuator", "na", "nbody", "njnt", "ngeom", "nsite", "ncam", "nlight", "nmesh",
                                                            "ntendon", "nsensor", "nsensordata", "neq", "nkey", "nmocap", "ntex", "nmat") if hasattr(model, k)},
        "opcoes": {
            "timestep": float(o.timestep), "integrator": enum_name(mujoco.mjtIntegrator, o.integrator), "solver": enum_name(mujoco.mjtSolver, o.solver),
            "cone": enum_name(mujoco.mjtCone, o.cone), "iterations": int(o.iterations), "ls_iterations": int(o.ls_iterations), "noslip_iterations": int(o.noslip_iterations),
            "tolerance": float(o.tolerance), "impratio": float(o.impratio), "gravity": [float(x) for x in o.gravity], "wind": [float(x) for x in o.wind],
            "density": float(o.density), "viscosity": float(o.viscosity), "disableflags": int(o.disableflags), "enableflags": int(o.enableflags),
        },
        "massa_total_kg": float(mujoco.mj_getTotalmass(model)),
    }
    return d


def tree(model) -> list[str]:
    out = []
    depth = {0: 0}
    for b in range(model.nbody):
        if b:
            depth[b] = depth[int(model.body_parentid[b])] + 1
        ind = "  " * depth[b]
        js = []
        for j in range(model.body_jntadr[b], model.body_jntadr[b] + model.body_jntnum[b]) if model.body_jntadr[b] >= 0 else []:
            t = enum_name(mujoco.mjtJoint, model.jnt_type[j]).replace("mjJNT_", "").lower()
            rng = f" [{model.jnt_range[j][0]:.3g},{model.jnt_range[j][1]:.3g}]" if model.jnt_limited[j] else ""
            js.append(f"{nm(model, mujoco.mjtObj.mjOBJ_JOINT, j)}:{t}{rng}")
        mocap = " (mocap)" if model.body_mocapid[b] >= 0 else ""
        out.append(f"{ind}{nm(model, mujoco.mjtObj.mjOBJ_BODY, b)}  m={model.body_mass[b]:.4g} kg{mocap}" + ("  · " + ", ".join(js) if js else ""))
    return out


def actuators(model) -> list[dict]:
    """Uma linha por atuador. Com atuadores MULTI-ENTRADA (pid/dcmotor/orientation) há três espaços de índice:
    atuador [i] (nactuator) · controle [actuator_ctrladr[i] : +ctrlnum] (nu) · saída [actuator_outadr[i] : +outnum] (nout)."""
    rows = []
    for i in range(model.nactuator):
        trn = enum_name(mujoco.mjtTrn, model.actuator_trntype[i]).replace("mjTRN_", "").lower()
        tid = int(model.actuator_trnid[i][0])
        tobj = {"joint": mujoco.mjtObj.mjOBJ_JOINT, "jointinparent": mujoco.mjtObj.mjOBJ_JOINT, "tendon": mujoco.mjtObj.mjOBJ_TENDON,
                "site": mujoco.mjtObj.mjOBJ_SITE, "body": mujoco.mjtObj.mjOBJ_BODY}.get(trn)
        ca, cn = int(model.actuator_ctrladr[i]), int(model.actuator_ctrlnum[i])
        oa = int(model.actuator_outadr[i]) if hasattr(model, "actuator_outadr") else i
        rows.append({
            "nome": nm(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i), "alvo": f"{trn}:{nm(model, tobj, tid) if tobj is not None else tid}",
            "gain": enum_name(mujoco.mjtGain, model.actuator_gaintype[i]).replace("mjGAIN_", "").lower(),
            "bias": enum_name(mujoco.mjtBias, model.actuator_biastype[i]).replace("mjBIAS_", "").lower(),
            "dyn": enum_name(mujoco.mjtDyn, model.actuator_dyntype[i]).replace("mjDYN_", "").lower(),
            "ctrladr": ca, "ctrlnum": cn, "outadr": oa,
            "ctrlrange": [float(x) for x in model.actuator_ctrlrange[ca]] if model.actuator_ctrllimited[ca] else None,  # índice de CONTROLE, não de atuador
            "forcerange": [float(x) for x in model.actuator_forcerange[i]] if model.actuator_forcelimited[i] else None,
            "gear": [round(float(x), 4) for x in model.actuator_gear[oa] if x != 0] or [0.0],                          # índice de SAÍDA
        })
    return rows


def sensors(model) -> list[dict]:
    return [{"nome": nm(model, mujoco.mjtObj.mjOBJ_SENSOR, i), "tipo": enum_name(mujoco.mjtSensor, model.sensor_type[i]).replace("mjSENS_", "").lower(),
             "dim": int(model.sensor_dim[i]), "adr": int(model.sensor_adr[i])} for i in range(model.nsensor)]


def risks(model, acts) -> list[tuple[str, str]]:
    r: list[tuple[str, str]] = []
    h = float(model.opt.timestep)
    # contatos macios: timeconst >= 2*timestep (regra oficial)
    bad = [(nm(model, mujoco.mjtObj.mjOBJ_GEOM, g), float(model.geom_solref[g][0])) for g in range(model.ngeom)
           if model.geom_solref[g][0] > 0 and model.geom_solref[g][0] < 2 * h and (model.geom_contype[g] or model.geom_conaffinity[g])]
    if bad:
        r.append(("ALTO", f"solref timeconst < 2·timestep ({2*h:g}) em {len(bad)} geom(s), ex.: {bad[0][0]}={bad[0][1]:g} → contato instável/explosivo; aumente timeconst ou reduza o timestep"))
    under = [nm(model, mujoco.mjtObj.mjOBJ_GEOM, g) for g in range(model.ngeom)
             if model.geom_solref[g][0] > 0 and model.geom_solref[g][1] < 0.5 and (model.geom_contype[g] or model.geom_conaffinity[g])]
    if under:
        r.append(("MÉDIO", f"dampratio < 0.5 em {len(under)} geom(s) (ex.: {under[0]}) → contato subamortecido: pode vibrar para sempre e nunca repousar"))
    if h > 0.01:
        r.append(("MÉDIO", f"timestep {h:g} s é grande (> 10 ms): contatos e atuadores rígidos tendem a ficar instáveis"))
    # corpos móveis sem massa
    for b in range(1, model.nbody):
        moves = model.body_dofnum[b] > 0 or any(model.body_dofnum[int(p)] > 0 for p in _ancestors(model, b))
        if moves and model.body_mass[b] < 1e-9:
            r.append(("ALTO", f"corpo móvel '{nm(model, mujoco.mjtObj.mjOBJ_BODY, b)}' sem massa → inércia nula/instável"))
    # razão de massas entre corpo e pai
    for b in range(2, model.nbody):
        p = int(model.body_parentid[b])
        if p > 0 and model.body_mass[b] > 0 and model.body_mass[p] > 0:
            ratio = max(model.body_mass[b], model.body_mass[p]) / min(model.body_mass[b], model.body_mass[p])
            if ratio > 100:
                r.append(("MÉDIO", f"razão de massa {ratio:.0f}:1 entre '{nm(model, mujoco.mjtObj.mjOBJ_BODY, p)}' e '{nm(model, mujoco.mjtObj.mjOBJ_BODY, b)}' → pode exigir `armature`/passo menor"))
                break
    for a in acts:
        if a["ctrlnum"] > 1:
            r.append(("INFO", f"atuador '{a['nome']}' tem {a['ctrlnum']} entradas de controle (ctrladr={a['ctrladr']}, outadr={a['outadr']}): os acessores nomeados (data.actuator(nome).ctrl/.force, model.actuator(nome).ctrlrange/.gear) usam o ID e dão valor/slot ERRADO — use data.ctrl[ctrladr:+ctrlnum] e os campos de saída por outadr (ou lab.mjkit.Ctrl)"))
        if a["gain"] != "fixed" or a["bias"] != "none":
            continue
        if a["ctrlrange"] is None and a["gain"] == "fixed" and a["dyn"] == "none":
            r.append(("INFO", f"atuador '{a['nome']}' sem ctrlrange: comando ilimitado (ok para teste; defina ctrlrange/forcerange em robôs reais)"))
    if model.nu != model.nactuator:
        r.append(("INFO", f"nu ({model.nu}) ≠ nactuator ({model.nactuator}): há atuadores multi-entrada — não assuma data.ctrl[i] = atuador i"))
    return r


def _ancestors(model, b):
    while b > 0:
        b = int(model.body_parentid[b])
        yield b


def smoke(model, steps: int) -> dict:
    data = mujoco.MjData(model)
    model.opt.enableflags |= mujoco.mjtEnableBit.mjENBL_ENERGY
    if model.nkey:
        mujoco.mj_resetDataKeyframe(model, data, 0)
    mujoco.mj_forward(model, data)
    e0 = float(data.energy.sum())
    emax = e0
    max_pen = 0.0
    max_v = 0.0
    ncon_max = 0
    ok = True
    for i in range(steps):
        mujoco.mj_step(model, data)
        if not (np.isfinite(data.qpos).all() and np.isfinite(data.qvel).all()):
            ok = False
            break
        emax = max(emax, float(data.energy.sum()))
        ncon_max = max(ncon_max, int(data.ncon))
        if data.ncon:
            max_pen = max(max_pen, -min(c.dist for c in data.contact[: data.ncon]))
        max_v = max(max_v, float(np.abs(data.qvel).max()) if model.nv else 0.0)
    warns = {k: int(data.warning[int(v)].number) for k, v in mujoco.mjtWarning.__members__.items() if k != "mjNWARNING" and int(v) < len(data.warning) and data.warning[int(v)].number}
    return {"passos": steps if ok else i, "finito": ok, "t_sim_s": float(data.time), "energia_inicial_J": e0, "energia_final_J": float(data.energy.sum()),
            "energia_max_acima_do_inicial_J": emax - e0, "penetracao_max_mm": max_pen * 1000, "contatos_max": ncon_max, "vel_max_gdl": max_v, "avisos_mjData": warns}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modelo")
    ap.add_argument("--tree", action="store_true", help="imprime a árvore de corpos e juntas")
    ap.add_argument("--steps", type=int, default=1000, help="passos do teste de fumaça (padrão 1000)")
    ap.add_argument("--no-smoke", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    path = Path(a.modelo)
    if not path.exists():
        print(f"Erro: arquivo não encontrado: {path} — Solução: passe o caminho de um .xml/.urdf/.mjb", file=sys.stderr)
        return 2
    model, err = build(path)
    if err:
        print(f"Erro de compilação em {path}:\n  {err}", file=sys.stderr)
        return 2
    rep = {"modelo": str(path), "mujoco": mujoco.__version__, **summarize(model)}
    acts = actuators(model)
    rep["atuadores"] = acts
    rep["sensores"] = sensors(model)
    types = {}
    for g in range(model.ngeom):
        types[enum_name(mujoco.mjtGeom, model.geom_type[g]).replace("mjGEOM_", "").lower()] = types.get(enum_name(mujoco.mjtGeom, model.geom_type[g]).replace("mjGEOM_", "").lower(), 0) + 1
    rep["geoms_por_tipo"] = types
    rep["riscos"] = [{"nivel": n, "msg": m} for n, m in risks(model, acts)]
    if not a.no_smoke:
        rep["fumaca"] = smoke(model, a.steps)
        s = rep["fumaca"]
        if not s["finito"]:
            rep["riscos"].append({"nivel": "ALTO", "msg": f"NaN/Inf após {s['passos']} passos: simulação instável"})
        if s["energia_max_acima_do_inicial_J"] > 0.02 * max(1.0, abs(s["energia_inicial_J"])) and not model.nu:
            rep["riscos"].append({"nivel": "MÉDIO", "msg": f"energia cresce sem atuadores (+{s['energia_max_acima_do_inicial_J']:.3g} J): integrador/passo inadequado"})
        if s["avisos_mjData"]:
            rep["riscos"].append({"nivel": "MÉDIO", "msg": f"avisos do mjData: {s['avisos_mjData']}"})
    if a.tree:
        rep["arvore"] = tree(model)
    if a.json:
        print(json.dumps(rep, indent=1, ensure_ascii=False))
    else:
        c = rep["contagens"]
        print(f"MuJoCo {mujoco.__version__} · {path}")
        print("contagens: " + " · ".join(f"{k}={v}" for k, v in c.items() if v))
        o = rep["opcoes"]
        print(f"opções: dt={o['timestep']:g} s · {o['integrator']} · {o['solver']} · cone {o['cone']} · iter {o['iterations']} · g={o['gravity']}"
              + (f" · densidade={o['density']:g} viscosidade={o['viscosity']:g}" if o['density'] or o['viscosity'] else ""))
        print(f"massa total: {rep['massa_total_kg']:.4f} kg · geoms: {rep['geoms_por_tipo']}")
        if a.tree:
            print("\nárvore:\n  " + "\n  ".join(rep["arvore"]))
        if acts:
            print("\natuadores (nome → alvo · gain/bias/dyn · ctrl[adr:+num] · ctrlrange · forcerange · gear):")
            for x in acts:
                print(f"  {x['nome']:18s} → {x['alvo']:22s} · {x['gain']}/{x['bias']}/{x['dyn']} · ctrl[{x['ctrladr']}:+{x['ctrlnum']}] · {x['ctrlrange']} · {x['forcerange']} · gear {x['gear']}")
        if rep["sensores"]:
            print("\nsensores: " + ", ".join(f"{s['nome']}({s['tipo']},{s['dim']})" for s in rep["sensores"]))
        if "fumaca" in rep:
            s = rep["fumaca"]
            print(f"\nteste de fumaça ({s['passos']} passos, t={s['t_sim_s']:.2f} s, ctrl=0): finito={s['finito']} · E {s['energia_inicial_J']:.3f}→{s['energia_final_J']:.3f} J "
                  f"· penetração máx {s['penetracao_max_mm']:.2f} mm · contatos máx {s['contatos_max']} · |qvel| máx {s['vel_max_gdl']:.3g}")
        print("\nriscos:" + ("" if rep["riscos"] else " nenhum"))
        for r in rep["riscos"]:
            print(f"  [{r['nivel']}] {r['msg']}")
    return 1 if any(r["nivel"] == "ALTO" for r in rep["riscos"]) else 0


if __name__ == "__main__":
    sys.exit(main())
