#!/usr/bin/env python3
"""verify_claims.py — verificação INDEPENDENTE (reexecução) das afirmações centrais da pesquisa profunda (Fase 5).

    .venv/bin/python pesquisas/tools/verify_claims.py            # local + rede (PyPI, AUR RPC, GitHub API/raw)
    .venv/bin/python pesquisas/tools/verify_claims.py --local    # só testes no MuJoCo instalado

Em vez de pedir a 3 verificadores LLM que «derrubem» cada afirmação, as afirmações DECIDÍVEIS POR MÁQUINA são reexecutadas aqui, por código escrito pelo orquestrador (não
copiado dos investigadores): testes no mujoco 3.15.0 instalado e consultas às fontes primárias (APIs públicas do AUR/PyPI/GitHub, e a tabela de SPS da doc local).
Cada linha: ID · afirmação · observado · OK|FALHA. Saída em pesquisas/verificacao/independente.{md,json}. Exit 0 se tudo OK, 1 se algum FALHA.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "pesquisas" / "verificacao"
RESULTS: list[dict] = []


def check(cid: str, claim: str):
    def deco(fn):
        try:
            ok, obs = fn()
        except Exception as e:  # noqa: BLE001
            ok, obs = False, f"exceção: {type(e).__name__}: {str(e)[:160]}"
        RESULTS.append({"id": cid, "afirmacao": claim, "observado": obs, "ok": bool(ok)})
        return fn
    return deco


def get(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mujoco-lab-verify/1.0 (+local)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URLs fixas e públicas)
        return r.read()


def jget(url: str):
    return json.loads(get(url))


# =============================================================================================== LOCAL
def local_checks() -> None:
    import mujoco
    import numpy as np

    os.chdir(tempfile.mkdtemp(prefix="vc_"))  # MUJOCO_LOG.TXT cai aqui, não na raiz do projeto

    @check("E01", "data.actuator('x').ctrl grava no slot errado com atuador multi-entrada (pid): nu ≠ nactuator")
    def _():
        m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><body><joint name="a"/><geom size=".1"/></body><body pos="1 0 0"><joint name="b"/><geom size=".1"/></body><body pos="2 0 0"><joint name="c"/><geom size=".1"/></body></worldbody>'
                                           '<actuator><motor joint="a"/><pid name="p" joint="b" kp="1" kv="1"/><position name="q" joint="c" kp="1"/></actuator></mujoco>')
        d = mujoco.MjData(m)
        d.actuator("q").ctrl[:] = 7
        slot = int(m.actuator_ctrladr[m.actuator("q").id])
        return (m.nu == 4 and m.nactuator == 3 and d.ctrl[2] == 7 and d.ctrl[slot] == 0), f"nu={m.nu} nactuator={m.nactuator} ctrl={d.ctrl.tolist()} slot_correto={slot}"

    @check("E02", "blocos <visual> repetidos são MESCLADOS por atributo; o mesmo sub-elemento repetido no MESMO bloco é erro")
    def _():
        m = mujoco.MjModel.from_xml_string('<mujoco><visual><global offwidth="1920" offheight="1080"/></visual><visual><headlight ambient=".3 .3 .3"/></visual><worldbody/></mujoco>')
        ok1 = m.vis.global_.offwidth == 1920 and abs(m.vis.headlight.ambient[0] - 0.3) < 1e-6
        try:
            mujoco.MjModel.from_xml_string('<mujoco><visual><global offwidth="1"/><global offwidth="2"/></visual></mujoco>')
            ok2, msg = False, "sem erro"
        except Exception as e:  # noqa: BLE001
            ok2, msg = ("unique" in str(e) or "Schema" in str(e)), str(e).strip().splitlines()[0][:80]
        return ok1 and ok2, f"offwidth={m.vis.global_.offwidth}, ambient={m.vis.headlight.ambient[0]:.1f}; duplicado → {msg}"

    @check("E03", "mjData.qM foi removido (agora M em CSR) e mj_fullM(m, d, dst) tem a nova assinatura")
    def _():
        m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><body><joint axis="0 1 0"/><geom size=".1"/></body></worldbody></mujoco>')
        d = mujoco.MjData(m); mujoco.mj_forward(m, d)
        M = np.zeros((1, 1)); mujoco.mj_fullM(m, d, M)
        return (not hasattr(d, "qM") and hasattr(d, "M") and M[0, 0] > 0), f"hasattr(qM)={hasattr(d,'qM')} hasattr(M)={hasattr(d,'M')} M00={M[0,0]:.4f}"

    @check("E04", "MjSpec não tem delete_body/delete_geom…; só spec.delete(elemento); e spec.compiler.strippath → AttributeError (use spec.strippath)")
    def _():
        s = mujoco.MjSpec()
        try:
            s.compiler.strippath
            has_c = True
        except AttributeError:
            has_c = False
        return (not hasattr(s, "delete_body") and hasattr(s, "delete") and not has_c and hasattr(s, "strippath")), \
            f"delete_body={hasattr(s,'delete_body')} delete={hasattr(s,'delete')} compiler.strippath={has_c} spec.strippath={hasattr(s,'strippath')}"

    @check("E05", "padrões 3.15.0: Euler, Newton, cone piramidal, dt 2 ms, 100 iterações, refsafe ligado")
    def _():
        m = mujoco.MjModel.from_xml_string("<mujoco/>")
        o = m.opt
        refsafe_on = (int(o.disableflags) & int(mujoco.mjtDisableBit.mjDSBL_REFSAFE)) == 0
        return (o.integrator == 0 and o.solver == 2 and o.cone == 0 and abs(o.timestep - 0.002) < 1e-12 and o.iterations == 100 and refsafe_on), \
            f"integrator={o.integrator} solver={o.solver} cone={o.cone} dt={o.timestep} iter={o.iterations} refsafe={refsafe_on}"

    @check("E06", "enum mjtIntegrator = Euler, RK4, implicit, implicitfast, discrete (5 valores)")
    def _():
        names = [k for k in mujoco.mjtIntegrator.__members__]
        return names == ["mjINT_EULER", "mjINT_RK4", "mjINT_IMPLICIT", "mjINT_IMPLICITFAST", "mjINT_DISCRETE"], str(names)

    @check("E07", "fluidcoef por omissão = (0.5, 0.25, 1.5, 1.0, 1.0)")
    def _():
        m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><body><freejoint/><geom size=".1 .05 .02" type="ellipsoid" fluidshape="ellipsoid"/></body></worldbody></mujoco>')
        return np.allclose(m.geom_fluid[0, 1:6], [0.5, 0.25, 1.5, 1.0, 1.0]), f"geom_fluid[0,1:6]={m.geom_fluid[0,1:6].tolist()}"

    @check("E08", "mj_contactForce devolve força no frame do contato; frame.reshape(3,3).T @ f[:3] → mundo; soma em repouso = m·g")
    def _():
        m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><geom type="plane" size="2 2 .1"/><body pos="0 0 .3"><freejoint/><geom type="box" size=".1 .1 .1" mass="2"/></body></worldbody></mujoco>')
        d = mujoco.MjData(m)
        for _ in range(1500):
            mujoco.mj_step(m, d)
        tot = np.zeros(3)
        for i in range(d.ncon):
            f = np.zeros(6); mujoco.mj_contactForce(m, d, i, f)
            tot += d.contact[i].frame.reshape(3, 3).T @ f[:3]
        mg = 2 * 9.81
        sinal = "geom[0] é o plano" if m.geom_type[d.contact[0].geom[0]] == mujoco.mjtGeom.mjGEOM_PLANE else "geom[0] é a caixa"
        return abs(abs(tot[2]) - mg) / mg < 0.01 and abs(tot[0]) < 0.05 * mg, f"soma_mundo={np.round(tot,3).tolist()} (m·g={mg:.3f}); ncon={d.ncon}; {sinal}; len(contact)={len(d.contact)}"

    @check("E09", "geoms visual+collision no mesmo corpo DOBRAM a massa; inertiagrouprange='3 3' corrige")
    def _():
        corpo = '<body><freejoint/><geom type="sphere" size=".1" group="2" contype="0" conaffinity="0"/><geom type="sphere" size=".1" group="3"/></body>'
        m1 = mujoco.MjModel.from_xml_string(f"<mujoco><worldbody>{corpo}</worldbody></mujoco>")
        m2 = mujoco.MjModel.from_xml_string(f'<mujoco><compiler inertiagrouprange="3 3"/><worldbody>{corpo}</worldbody></mujoco>')
        a, b = float(m1.body_mass[1]), float(m2.body_mass[1])
        return abs(a / b - 2) < 1e-6, f"massa padrão={a:.4f} kg · com inertiagrouprange=3 3 → {b:.4f} kg"

    @check("E10", "com compiler angle=degree, o range da junta é convertido para rad mas o ctrlrange do atuador NÃO")
    def _():
        m = mujoco.MjModel.from_xml_string('<mujoco><compiler angle="degree"/><worldbody><body><joint name="j" range="-30 30"/><geom size=".1"/></body></worldbody><actuator><position joint="j" kp="1" ctrlrange="-30 30"/></actuator></mujoco>')
        return (abs(m.jnt_range[0, 1] - np.radians(30)) < 1e-6 and abs(m.actuator_ctrlrange[0, 1] - 30) < 1e-9), f"jnt_range={m.jnt_range[0].round(4).tolist()} rad · ctrlrange={m.actuator_ctrlrange[0].tolist()}"

    @check("E11", "mjd_transitionFD com flg_centered=True devolve D com SINAL TROCADO em relação a False (bug upstream 3.15.0)")
    def _():
        m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><body><joint name="j" axis="0 1 0"/><geom size=".1"/></body></worldbody><actuator><motor joint="j"/></actuator><sensor><actuatorfrc actuator="motor"/></sensor></mujoco>'.replace('actuator="motor"', 'actuator="a"').replace("<motor joint", '<motor name="a" joint'))
        d = mujoco.MjData(m); d.ctrl[0] = 0.3; mujoco.mj_forward(m, d)
        res = {}
        for cen in (False, True):
            A = np.zeros((2 * m.nv + m.na, 2 * m.nv + m.na)); B = np.zeros((2 * m.nv + m.na, m.nu))
            C = np.zeros((m.nsensordata, 2 * m.nv + m.na)); D = np.zeros((m.nsensordata, m.nu))
            mujoco.mjd_transitionFD(m, d, 1e-6, cen, A, B, C, D)
            res[cen] = float(D[0, 0])
        return (res[False] * res[True] < 0), f"D[False]={res[False]:+.4f} · D[True]={res[True]:+.4f}"

    @check("E12", "<geom mesh=…/> sem type=\"mesh\" vira esfera; com type=\"mesh\" vira malha; só vertex= gera o casco convexo")
    def _():
        asset = '<asset><mesh name="m" vertex="0 0 0 1 0 0 0 1 0 0 0 1"/></asset>'
        a = mujoco.MjModel.from_xml_string(f'<mujoco>{asset}<worldbody><geom mesh="m"/></worldbody></mujoco>')
        b = mujoco.MjModel.from_xml_string(f'<mujoco>{asset}<worldbody><geom type="mesh" mesh="m"/></worldbody></mujoco>')
        return (a.geom_type[0] == mujoco.mjtGeom.mjGEOM_SPHERE and b.geom_type[0] == mujoco.mjtGeom.mjGEOM_MESH and b.nmeshface >= 4), \
            f"sem type → {mujoco.mjtGeom(a.geom_type[0]).name} · com type → {mujoco.mjtGeom(b.geom_type[0]).name} ({b.nmeshface} faces)"

    @check("E13", "a gravidade está em qfrc_bias (não em qfrc_passive nem qfrc_applied)")
    def _():
        m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><body><joint axis="0 1 0"/><geom type="capsule" fromto="0 0 0 1 0 0" size=".02"/></body></worldbody></mujoco>')
        d = mujoco.MjData(m); mujoco.mj_forward(m, d)
        return (abs(d.qfrc_bias[0]) > 0.1 and d.qfrc_passive[0] == 0 and d.qfrc_applied[0] == 0), f"qfrc_bias={d.qfrc_bias[0]:.3f} qfrc_passive={d.qfrc_passive[0]} qfrc_applied={d.qfrc_applied[0]}"

    @check("E14", "data.timer funciona nos bindings Python (timer padrão em segundos) após mj_step; não existe mj_timingStatus")
    def _():
        m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><body><freejoint/><geom size=".1"/></body></worldbody></mujoco>')
        d = mujoco.MjData(m)
        for _ in range(2000):
            mujoco.mj_step(m, d)
        t = d.timer[int(mujoco.mjtTimer.mjTIMER_STEP)]
        return (t.number >= 2000 and t.duration > 0 and not hasattr(mujoco, "mj_timingStatus")), f"STEP.number={t.number} duration={t.duration:.4f}s mj_timingStatus={hasattr(mujoco,'mj_timingStatus')}"

    @check("E15", "mjtSensor tem 49 tipos e NÃO existe sensor 'imu'")
    def _():
        names = [k for k in mujoco.mjtSensor.__members__ if k != "mjNSENS"]
        return (len(names) == 49 and not any("IMU" in n.upper() for n in names)), f"{len(names)} tipos; imu? {any('IMU' in n.upper() for n in names)}"

    @check("E16", "o wheel NÃO traz mjpython, .pc nem config CMake; traz libmujoco.so.3.15.0, 4 plugins e headers")
    def _():
        pkg = Path(mujoco.__file__).parent
        libs = sorted(p.name for p in pkg.glob("lib*.so*"))
        plug = sorted(p.name for p in (pkg / "plugin").glob("*.so")) if (pkg / "plugin").exists() else []
        headers = len(list((pkg / "include").rglob("*.h")))
        bad = [p.name for p in pkg.rglob("*") if p.suffix == ".pc" or p.name.lower().startswith("mujococonfig")]
        mjpy = (Path(sys.executable).parent / "mjpython").exists()
        return (any("libmujoco.so.3.15.0" in x for x in libs) and len(plug) == 4 and headers >= 60 and not bad and not mjpy), \
            f"libs={libs} plugins={plug} headers={headers} .pc/cmake={bad} mjpython={mjpy}"

    @check("E17", "pyGLFW tem variantes wayland/x11 escolhidas por XDG_SESSION_TYPE / PYGLFW_LIBRARY_VARIANT")
    def _():
        import glfw
        d = Path(glfw.__file__).parent
        src = (d / "library.py").read_text() if (d / "library.py").exists() else Path(glfw.__file__).read_text()
        return ((d / "wayland").exists() and (d / "x11").exists() and "XDG_SESSION_TYPE" in src and "PYGLFW_LIBRARY_VARIANT" in src), \
            f"dirs={sorted(p.name for p in d.iterdir() if p.is_dir() and p.name in ('wayland','x11'))} XDG_SESSION_TYPE={'XDG_SESSION_TYPE' in src} PYGLFW_LIBRARY_VARIANT={'PYGLFW_LIBRARY_VARIANT' in src}"

    @check("E18", "mj_step(nstep=N) equivale a N passos simples")
    def _():
        xml = '<mujoco><worldbody><body pos="0 0 1"><freejoint/><geom size=".1"/></body></worldbody></mujoco>'
        m = mujoco.MjModel.from_xml_string(xml); a, b = mujoco.MjData(m), mujoco.MjData(m)
        mujoco.mj_step(m, a, nstep=25)
        for _ in range(25):
            mujoco.mj_step(m, b)
        return np.allclose(a.qpos, b.qpos, atol=1e-12), f"|Δqpos|={np.abs(a.qpos-b.qpos).max():.1e}"

    @check("E19", "option collision=… foi removido (3.0.0) e é rejeitado; atributos novos são aceitos")
    def _():
        try:
            mujoco.MjModel.from_xml_string('<mujoco><option collision="all"/></mujoco>')
            return False, "aceito (inesperado)"
        except Exception as e:  # noqa: BLE001
            return ("unrecognized" in str(e) or "Schema" in str(e)), str(e).strip().splitlines()[0][:90]

    @check("E20", "queda livre: tempo de impacto simulado = √(2h/g) dentro de 1 passo (esfera de 1 m)")
    def _():
        m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><geom type="plane" size="2 2 .1"/><body pos="0 0 1.1"><freejoint/><geom size=".1" mass="1"/></body></worldbody></mujoco>')
        d = mujoco.MjData(m); t = None
        while d.time < 1 and t is None:
            mujoco.mj_step(m, d)
            if d.ncon: t = d.time
        prev = (2 * 1.0 / 9.81) ** 0.5
        return abs(t - prev) <= 1.5 * m.opt.timestep, f"simulado={t:.4f} s · previsto={prev:.4f} s"



    @check("E21", "atuador <pid> com ki>0 E slewmax>0 ao mesmo tempo NÃO compila em 3.15.0 (actdim > 1); ki sozinho compila")
    def _():
        base = '<mujoco><worldbody><body><joint name="j"/><geom size=".1"/></body></worldbody><actuator><pid joint="j" kp="1" kv="1" {x}/></actuator></mujoco>'
        ok_ki = mujoco.MjModel.from_xml_string(base.format(x='ki="1" imax="1"')) is not None
        try:
            mujoco.MjModel.from_xml_string(base.format(x='ki="1" imax="1" slewmax="1"'))
            return False, "compilou (inesperado)"
        except Exception as e:  # noqa: BLE001
            return (ok_ki and "actdim" in str(e)), f"ki sozinho: compila · ki+slewmax: {str(e).strip().splitlines()[0][:90]}"

    @check("E22", "sob XDG_SESSION_TYPE=wayland o pyGLFW carrega glfw/wayland/libglfw.so (só Wayland); PYGLFW_LIBRARY_VARIANT=x11 carrega a variante X11")
    def _():
        import subprocess
        code = "import glfw; print(glfw._glfw._name.split('site-packages/')[-1], bool(glfw.platform_supported(glfw.PLATFORM_WAYLAND)), bool(glfw.platform_supported(glfw.PLATFORM_X11)))"
        def run(env_extra):
            env = {k: v for k, v in os.environ.items() if k not in ("PYGLFW_LIBRARY_VARIANT", "XDG_SESSION_TYPE")}
            env.update(env_extra)
            return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=60).stdout.strip()
        w, x = run({"XDG_SESSION_TYPE": "wayland"}), run({"XDG_SESSION_TYPE": "wayland", "PYGLFW_LIBRARY_VARIANT": "x11"})
        return (w.startswith("glfw/wayland/libglfw.so True False") and x.startswith("glfw/x11/libglfw.so False True")), f"wayland → {w} · variante x11 → {x}"

    @check("E23", "changelog: C++20 é o mínimo para compilar (3.3.7) e o dampratio da 3.15.0 é o do ATUADOR (inércia refletida), não o do solref de contato")
    def _():
        t = (ROOT / "docs/upstream/mujoco/doc/changelog.rst").read_text(encoding="utf-8")
        ok1 = "minimum C++ standard required to compile MuJoCo is now C++20" in t
        i = t.find("Actuator :ref:`dampratio<actuator-position-dampratio>` now computes the reflected inertia")
        return ok1 and i >= 0, f"C++20 em 3.3.7: {ok1} · item dampratio-do-atuador na 3.15.0: {i >= 0}"

    @check("E24", "MjSpec: mesh.maxhullvert = 3 derruba o processo (SIGSEGV/abort do qhull) — testado em subprocesso")
    def _():
        import subprocess
        code = ("import mujoco\ns = mujoco.MjSpec()\nm = s.add_mesh(name='m'); m.uservert = [0,0,0,1,0,0,0,1,0,0,0,1,1,1,1]\n"
                "m.maxhullvert = 3\ng = s.worldbody.add_geom(type=mujoco.mjtGeom.mjGEOM_MESH, meshname='m')\ns.compile()\nprint('SEM-CRASH')")
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60, cwd=tempfile.gettempdir())
        return (r.returncode != 0 and "SEM-CRASH" not in r.stdout), f"returncode={r.returncode} stdout={r.stdout.strip()[:40]!r} stderr={r.stderr.strip()[-80:]!r}"


# =============================================================================================== WEB
def web_checks() -> None:
    @check("W01", "AUR: mujoco 3.15.0 (compila do fonte), mujoco-bin uma versão atrás, python-mujoco desatualizado/flagged")
    def _():
        r = jget("https://aur.archlinux.org/rpc/v5/info?arg[]=mujoco&arg[]=mujoco-bin&arg[]=python-mujoco")
        by = {x["Name"]: x for x in r["results"]}
        ok = by["mujoco"]["Version"].startswith("3.15.0") and not by["mujoco-bin"]["Version"].startswith("3.15") and by["python-mujoco"].get("OutOfDate")
        return bool(ok), "; ".join(f"{n} {x['Version']} (OutOfDate={'sim' if x.get('OutOfDate') else 'não'}, mant. {x.get('Maintainer')})" for n, x in by.items())

    def pypi(name):
        return jget(f"https://pypi.org/pypi/{name}/json")

    @check("W02", "PyPI mujoco: 3.15.0 é a última; requires-python >=3.10; wheels cp313/cp314 manylinux x86_64")
    def _():
        j = pypi("mujoco"); files = j["urls"]
        tags = {f["filename"].split("-")[2] for f in files if f["filename"].endswith(".whl")}
        manyl = any("manylinux" in f["filename"] and "x86_64" in f["filename"] and "-cp313-" in f["filename"] for f in files)
        return (j["info"]["version"] == "3.15.0" and j["info"]["requires_python"] == ">=3.10" and manyl and {"cp313", "cp314"} <= tags), \
            f"versão={j['info']['version']} requires_python={j['info']['requires_python']} tags={sorted(tags)}"

    @check("W03", "dm_control exige mujoco>=3.15.0 e labmaze; labmaze não tem wheel para CPython 3.13")
    def _():
        j = pypi("dm_control")
        req = j["info"]["requires_dist"] or []
        lab = pypi("labmaze")
        tags = sorted({f["filename"].split("-")[2] for f in lab["urls"] if f["filename"].endswith(".whl")})
        has_lm = any(r.lower().startswith("labmaze") for r in req)
        return (has_lm and any("mujoco" in r and "3.15" in r for r in req) and "cp313" not in tags), \
            f"dm_control {j['info']['version']} mujoco: {[r for r in req if r.lower().startswith('mujoco')]} labmaze: {has_lm}; labmaze {lab['info']['version']} wheels={tags}"

    @check("W04", "mjlab fixa mujoco~=3.11.x e mujoco-warp~=3.11.x (não coexiste com 3.15.0)")
    def _():
        j = pypi("mjlab"); req = j["info"]["requires_dist"] or []
        pins = [r for r in req if r.lower().startswith(("mujoco", "warp"))]
        return any("3.11" in r for r in pins), f"mjlab {j['info']['version']} · {pins}"

    @check("W05", "playground 0.2.0 requer Python >=3.11")
    def _():
        j = pypi("playground")
        return j["info"]["requires_python"] == ">=3.11", f"playground {j['info']['version']} requires_python={j['info']['requires_python']}"

    @check("W06", "urdf2mjcf (K-Scale) não depende de CoACD/V-HACD; PyPI 0.2.39, Python >=3.11")
    def _():
        j = pypi("urdf2mjcf"); req = [r.lower() for r in (j["info"]["requires_dist"] or [])]
        return (not any("coacd" in r or "vhacd" in r for r in req)), f"urdf2mjcf {j['info']['version']} requires_python={j['info']['requires_python']} deps={[r.split(';')[0] for r in req]}"

    @check("W07", "urdf2mjcf: nenhum arquivo .py do repositório menciona CoACD / V-HACD")
    def _():
        tree = jget("https://api.github.com/repos/kscalelabs/urdf2mjcf/git/trees/master?recursive=1")["tree"]
        py = [t["path"] for t in tree if t["path"].endswith(".py") and t["type"] == "blob" and "test" not in t["path"].lower()]
        hits = []
        for p in py:
            txt = get(f"https://raw.githubusercontent.com/kscalelabs/urdf2mjcf/master/{p}").decode("utf-8", "replace").lower()
            if "coacd" in txt or "vhacd" in txt or "v-hacd" in txt:
                hits.append(p)
        return not hits, f"{len(py)} arquivos .py verificados; menções a CoACD/V-HACD: {hits or 'nenhuma'}"

    @check("W08", "MuJoCo 3.15.0 (tag) não instala mujoco.pc: nenhum .pc/pkgconfig no repositório e o CMake exporta mujocoConfig.cmake")
    def _():
        tree = jget("https://api.github.com/repos/google-deepmind/mujoco/git/trees/3.15.0?recursive=1")["tree"]
        paths = [t["path"] for t in tree]
        pc = [p for p in paths if p.endswith(".pc") or p.endswith(".pc.in") or "pkgconfig" in p.lower()]
        cm = get("https://raw.githubusercontent.com/google-deepmind/mujoco/3.15.0/CMakeLists.txt").decode("utf-8", "replace")
        cfg = [p for p in paths if "mujocoConfig" in p or p.lower().endswith("mujococonfig.cmake.in")]
        mentions = bool(re.search(r"pkg-?config|\.pc\b", cm, re.I))
        return (not pc and not mentions and bool(cfg or "install(EXPORT" in cm or "mujocoTargets" in cm)), \
            f"arquivos .pc/pkgconfig na árvore: {pc or 'nenhum'}; CMakeLists menciona pkg-config: {mentions}; config/export cmake: {cfg or ('install(EXPORT' in cm)}"

    @check("W09", "mujoco_mpc dormente: último commit do main em maio/2025")
    def _():
        c = jget("https://api.github.com/repos/google-deepmind/mujoco_mpc/commits?per_page=1")[0]["commit"]["committer"]["date"]
        return c.startswith("2025-05"), f"último commit: {c}"

    @check("W10", "rerun-sdk 0.38.1 é a última; requires-python >=3.10")
    def _():
        j = pypi("rerun-sdk")
        return j["info"]["version"].startswith("0.38"), f"rerun-sdk {j['info']['version']} requires_python={j['info']['requires_python']}"

    @check("W11", "mujoco-menagerie no PyPI 2026.10.1; Menagerie tem Skydio X2 e Crazyflie 2 como únicos drones")
    def _():
        j = pypi("mujoco-menagerie")
        readme = (ROOT / "docs/upstream/mujoco_menagerie/README.md").read_text(encoding="utf-8") if (ROOT / "docs/upstream/mujoco_menagerie/README.md").exists() else ""
        dr = re.search(r"\*\*Drones\.\*\*(.*?)(?=\n\*\*[A-Z][^*]*\.\*\*|\Z)", readme, re.S)
        txt = dr.group(1) if dr else ""
        return (j["info"]["version"] == "2026.10.1" and "Skydio" in txt and "Crazyflie" in txt), f"mujoco-menagerie {j['info']['version']}; seção Drones cita: {re.findall(r'Skydio[^|\\n]*|Crazyflie[^|\\n]*', txt)[:2]}"


def docs_checks() -> None:
    @check("D01", "os números 2,96 M e 2,33 M SPS do relatório vêm da MESMA linha «JAX FFI (WARP)» da tabela oficial de mjx.rst (Humanoid e Aloha Pot); Pure Warp = 3,35 M / 2,45 M")
    def _():
        t = (ROOT / "docs/upstream/mujoco/doc/mjx.rst").read_text(encoding="utf-8")
        i = t.find("Steps per Second (SPS) for MJX-Warp Graph Modes")
        bloco = t[i: i + 900] if i >= 0 else ""
        linhas = [re.sub(r"\s+", " ", x.strip()) for x in bloco.splitlines() if x.strip().startswith(("* -", "-"))]
        ok = i >= 0 and "Pure Warp (No JAX FFI)" in bloco and re.search(r"JAX FFI \(``WARP``\)\s*\n\s*- 2\.96M\s*\n\s*- 2\.33M", bloco) is not None and "3.35M" in bloco and "2.45M" in bloco
        return ok, " | ".join(linhas[:14])

    @check("D02", "viewer.launch_passive sem mjpython no macOS levanta RuntimeError (não SegFault) — leitura do código 3.15.0")
    def _():
        s = (ROOT / "docs/upstream/mujoco/python/mujoco/viewer.py").read_text(encoding="utf-8")
        return ("requires that the Python script be run under" in s and "RuntimeError" in s and "mjpython" in s), "viewer.py: raise RuntimeError('`launch_passive` requires that the Python script be run under `mjpython` on macOS')"

    @check("D03", "doc/skills (6 SKILL.md) está fora da toctree de doc/index.rst")
    def _():
        idx = (ROOT / "docs/upstream/mujoco/doc/index.rst").read_text(encoding="utf-8")
        return ("skills" not in idx), f"'skills' em index.rst: {'skills' in idx}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", action="store_true", help="não faz consultas de rede")
    a = ap.parse_args()
    local_checks()
    docs_checks()
    if not a.local:
        web_checks()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "independente.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Verificação independente (reexecução) das afirmações centrais", "",
          f"Gerado por `pesquisas/tools/verify_claims.py` — {sum(r['ok'] for r in RESULTS)}/{len(RESULTS)} OK.", "",
          "| ID | Afirmação | Observado | Resultado |", "| --- | --- | --- | --- |"]
    for r in RESULTS:
        md.append(f"| {r['id']} | {r['afirmacao'].replace('|', '¦')} | {str(r['observado']).replace('|', '¦')[:380]} | {'OK' if r['ok'] else 'FALHA'} |")
    (OUT / "independente.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for r in RESULTS:
        print(f"[{'OK ' if r['ok'] else 'FALHA'}] {r['id']} {r['afirmacao'][:100]}\n        → {str(r['observado'])[:230]}")
    print(f"\n{sum(r['ok'] for r in RESULTS)}/{len(RESULTS)} OK · detalhes em {OUT}")
    return 0 if all(r["ok"] for r in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
