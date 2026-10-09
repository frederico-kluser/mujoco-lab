"""Testes da skill mujoco-agent-skill — rodam offline (EGL offscreen, sem janela), da raiz do projeto:

    uv run pytest .agents/mujoco-lab-agent-skill/tests -q            # tudo (~1-2 min)
    uv run pytest .agents/mujoco-lab-agent-skill/tests -q -k "not templates"   # só scripts/biblioteca

Cada template e o experimento 09 têm `run.py` que valida a física/contrato e sai com 0/1: aqui exigimos exit 0.
(Os testes dos experimentos 01 e 03 caíram com a remoção dos experimentos 01–08 em 2026-10-08 — histórico no git.)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
ROOT = next(p for p in SKILL.parents if (p / "pyproject.toml").exists())
SCRIPTS = SKILL / "scripts"
TEMPLATES = SKILL / "assets" / "templates"
# `PYTHONDONTWRITEBYTECODE=1`: os `run.py` dos templates importam módulos irmãos (`env.py`, `lab/…`) e o Python
# gravaria `__pycache__` DENTRO dos templates (poluía `assets/templates/**` a cada corrida da suíte).
ENV = dict(os.environ, MUJOCO_GL="egl", PYTHONDONTWRITEBYTECODE="1")


def run(args: list[str], timeout: int = 300, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=cwd or ROOT, env=ENV, timeout=timeout)


# ------------------------------------------------------------------------------------------ biblioteca
def test_mjkit_ctrl_multi_input_slots():
    """Armadilha 3.15: com atuador multi-entrada (pid = 2 controles) o acessor por nome grava no slot errado; mjkit.Ctrl não."""
    sys.path.insert(0, str(ROOT))
    from lab import mjkit  # noqa: PLC0415

    import mujoco  # noqa: PLC0415

    xml = """<mujoco><worldbody>
      <body><joint name="j1" axis="0 1 0"/><geom size=".05"/></body>
      <body pos="1 0 0"><joint name="j2" axis="0 1 0"/><geom size=".05"/></body>
      <body pos="2 0 0"><joint name="j3" axis="0 1 0"/><geom size=".05"/></body></worldbody>
      <actuator><motor name="m" joint="j1"/><pid name="p" joint="j2" kp="5" kv="1"/><position name="pos" joint="j3" kp="10"/></actuator></mujoco>"""
    model, data = mjkit.load(xml)
    assert model.nu == 4 and model.nactuator == 3
    ctrl = mjkit.Ctrl(model)
    ctrl.set(data, "pos", 99.0)
    assert data.ctrl[model.actuator_ctrladr[model.actuator("pos").id]] == 99.0
    assert data.ctrl[2] == 0.0  # o slot 2 pertence ao 2º controle do pid e NÃO foi tocado
    ctrl.set(data, "p", [1.0, 2.0])
    assert list(data.ctrl[1:3]) == [1.0, 2.0]
    with pytest.raises(ValueError):
        ctrl.set(data, "p", [1.0, 2.0, 3.0])
    with pytest.raises(ValueError):  # escalar em atuador multi-entrada é ambíguo: exige vetor
        ctrl.set(data, "p", 0.5)
    mujoco.mj_step(model, data)


def test_mjkit_record_returns_log(tmp_path):
    sys.path.insert(0, str(ROOT))
    from lab import mjkit  # noqa: PLC0415

    model, data = mjkit.load(ROOT / "models" / "triangulo_invertido.xml")
    res = mjkit.record(model, data, None, duration=0.2, probes={"z": lambda m, d: d.xipos[1, 2]})
    # após mj_step, campos derivados (xipos…) refletem o estado ANTERIOR à integração → 1º ponto = 1.0; o último já caiu ~0,2 m
    assert len(res["log"]["t"]) == 100 and res["log"]["z"][0] <= 1.0 and 0.78 < res["log"]["z"][-1] < 0.85


# ---------------------------------------------------------------------------------------------- scripts
def test_inspect_model_demo_json():
    r = run([str(SCRIPTS / "inspect_model.py"), "models/triangulo_invertido.xml", "--json", "--steps", "300"])
    assert r.returncode == 0, r.stderr
    rep = json.loads(r.stdout)
    assert abs(rep["massa_total_kg"] - 20.7846) < 1e-3 and rep["fumaca"]["finito"]


def test_inspect_model_multi_input_indexing():
    """ctrlrange/gear devem ser lidos por actuator_ctrladr/outadr (bug: indexar por ID mostrava None/1 com pid antes)."""
    import tempfile  # noqa: PLC0415

    xml = """<mujoco><worldbody><body><joint name="a"/><geom size=".1"/></body><body pos="1 0 0"><joint name="b"/><geom size=".1"/></body></worldbody>
      <actuator><pid name="p" joint="a" kp="1" kv="1"/><motor name="m" joint="b" gear="7" ctrlrange="-2 2"/></actuator></mujoco>"""
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
        f.write(xml)
    r = run([str(SCRIPTS / "inspect_model.py"), f.name, "--json", "--no-smoke"])
    assert r.returncode == 0, r.stderr
    m = [a for a in json.loads(r.stdout)["atuadores"] if a["nome"] == "m"][0]
    assert m["ctrlrange"] == [-2.0, 2.0] and m["gear"] == [7.0] and m["ctrladr"] == 2


def test_inspect_model_compile_error_exit2(tmp_path):
    bad = tmp_path / "ruim.xml"
    bad.write_text("<mujoco><worldbody><body><joint/></body></worldbody></mujoco>")  # corpo móvel sem massa
    r = run([str(SCRIPTS / "inspect_model.py"), str(bad)])
    assert r.returncode == 2 and "Solução" in r.stderr and "mjMINVAL" in r.stderr and "corpo móvel sem massa" in r.stderr  # a dica específica casa com a mensagem da 3.15


@pytest.mark.skipif(not (ROOT / "docs" / "upstream" / "mujoco" / "doc" / "XMLreference.rst").exists(), reason="espelho de docs ausente (rode sync_docs.py)")
def test_docs_search_modes():
    ds = str(SCRIPTS / "docs_search.py")
    assert "Euler" in run([ds, "--attr", "option.integrator"]).stdout
    assert "mj_step" in run([ds, "--api", "mj_step"]).stdout
    assert "mjINT_IMPLICITFAST" in run([ds, "--type", "mjtIntegrator"]).stdout
    assert "Version 3." in run([ds, "--changelog", "implicitfast"]).stdout
    assert run([ds, "solref timeconst", "--limit", "2"]).returncode == 0
    assert run([ds, "--attr", "geom.naoexiste"]).returncode == 1


def _egl_ok() -> bool:
    """EGL offscreen disponível? (máquinas sem GPU/EGL pulam os testes de render em vez de falhar)"""
    r = run([str(SCRIPTS / "env_check.py"), "--json", "--gl", "egl"])
    try:
        rows = json.loads(r.stdout)
    except ValueError:
        return False
    return any("MUJOCO_GL=egl" in x["name"] and x["level"] == "OK" for x in rows)


def test_render_video_smoke(tmp_path):
    if not _egl_ok():
        pytest.skip("EGL offscreen indisponível nesta máquina")
    out = tmp_path / "v"
    r = run([str(SCRIPTS / "render_video.py"), "models/tetraedro_invertido.xml", "--duration", "0.3", "--width", "160", "--height", "90",
             "--camera", "frontal", "--sheet", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    assert out.with_suffix(".mp4").stat().st_size > 1000 and (tmp_path / "v_sheet.png").exists()


def test_new_experiment_dry_run():
    r = run([str(SCRIPTS / "new_experiment.py"), "teste_x", "--template", "pendulum", "--dry-run"])
    assert r.returncode == 0 and "PLANO" in r.stdout
    assert run([str(SCRIPTS / "new_experiment.py"), "x", "--template", "inexistente"]).returncode == 2


def test_env_check_json():
    r = run([str(SCRIPTS / "env_check.py"), "--json", "--gl", "egl"])
    rows = json.loads(r.stdout)
    assert any(x["name"].startswith("mujoco 3.15") and x["level"] == "OK" for x in rows)
    if not any("MUJOCO_GL=egl" in x["name"] and x["level"] == "OK" for x in rows):
        pytest.skip("EGL offscreen indisponível nesta máquina")


# --------------------------------------------------------------------------- experimentos e templates
def test_experiment_09_run_py():
    """O único experimento atual (09_drone_hover_rl): `run.py` valida o contrato do env por fórmulas fechadas e sai 0.

    Substitui os antigos `test_experiment_01_physics_checks` e `test_experiment_03_report_example`
    (experimentos 01–08 removidos em 2026-10-08 por decisão do dono; histórico no git). Precisa do grupo
    `hover-rl` (gymnasium + stable-baselines3): sem ele o teste é pulado em vez de falhar.
    """
    pytest.importorskip("gymnasium", reason="grupo hover-rl não instalado")
    pytest.importorskip("stable_baselines3", reason="grupo hover-rl não instalado")
    r = run(["experiments/09_drone_hover_rl/run.py"], timeout=300)
    assert r.returncode == 0, r.stdout[-800:]
    assert "checagens [OK]" in r.stdout and "0 [FALHA]" in r.stdout


@pytest.mark.parametrize("modelo,massa", [("models/triangulo_invertido.xml", 20.7846), ("models/tetraedro_invertido.xml", 7.5425)])
def test_demo_models_mass_matches_analytic(modelo, massa):
    import mujoco  # noqa: PLC0415

    m = mujoco.MjModel.from_xml_path(str(ROOT / modelo))
    assert abs(float(mujoco.mj_getTotalmass(m)) - massa) < 2e-3


@pytest.mark.parametrize("template", ["blank", "pendulum", "arm", "quadrotor", "car", "lab-padrao"])
def test_templates_run_ok(template, tmp_path):
    """Cada template compila, simula e passa nas próprias checagens (exit 0)."""
    r = run([str(TEMPLATES / template / "run.py"), "--sem-video", "--saida", str(tmp_path)], timeout=400)
    assert r.returncode == 0, (r.stdout + r.stderr)[-1200:]


@pytest.mark.parametrize("template", ["blank", "pendulum", "arm", "quadrotor", "car", "lab-padrao"])
def test_templates_models_inspect_clean(template):
    r = run([str(SCRIPTS / "inspect_model.py"), str(TEMPLATES / template / "model.xml"), "--json", "--steps", "300"])
    assert r.returncode == 0, r.stderr
    assert not [x for x in json.loads(r.stdout)["riscos"] if x["nivel"] == "ALTO"]
