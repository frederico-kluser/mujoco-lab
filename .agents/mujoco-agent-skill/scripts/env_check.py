#!/usr/bin/env python3
"""env_check.py — diagnóstico do ambiente MuJoCo (Python, pacotes, renderização GL/EGL, GPU, sessão gráfica, docs).

    python3 .agents/mujoco-agent-skill/scripts/env_check.py            # checagem rápida (testa EGL em subprocesso isolado)
    python3 .agents/mujoco-agent-skill/scripts/env_check.py --gl all   # testa egl, osmesa e glfw (glfw cria uma janela oculta: precisa de display)
    python3 .agents/mujoco-agent-skill/scripts/env_check.py --gpu      # também verifica JAX/Warp (se instalados) em subprocesso
    python3 .agents/mujoco-agent-skill/scripts/env_check.py --json

Use o python da venv do projeto (`.venv/bin/python`) para ver os pacotes certos; com o python do sistema ele avisa que não achou o mujoco.
Cada linha: OK · INFO (opcional/ausente) · WARN (funciona, mas atenção) · FAIL (quebra) — seguido de `→ Solução`.
Exit 0 sem FAIL · 1 com FAIL.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from importlib import metadata
from pathlib import Path

ROWS: list[dict] = []


def add(level: str, name: str, detail: str = "", fix: str = "") -> None:
    ROWS.append({"level": level, "name": name, "detail": detail, "fix": fix})


def ver(pkg: str) -> str | None:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None


def run(cmd: list[str], timeout: int = 60, env: dict | None = None) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except FileNotFoundError:
        return 127, "não encontrado"


def find_root() -> Path:
    for base in [Path.cwd(), *Path.cwd().parents]:
        if (base / "pyproject.toml").exists() or (base / "docs" / "upstream").is_dir():
            return base
    return Path.cwd()


GL_PROBE = textwrap.dedent("""
    import os, sys, time
    import mujoco, numpy as np
    m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><light pos="0 0 3"/><geom type="sphere" size=".2" rgba="1 0 0 1"/></worldbody></mujoco>')
    d = mujoco.MjData(m); mujoco.mj_forward(m, d)
    with mujoco.Renderer(m, 240, 320) as r:
        r.update_scene(d); r.render()
        t = time.perf_counter()
        for _ in range(20):
            r.update_scene(d); img = r.render()
        ms = (time.perf_counter() - t) / 20 * 1000
    print(f"frame {img.shape} média {float(img.mean()):.1f} · {ms:.1f} ms/quadro (320x240)")
""")


def check_python_pkgs() -> None:
    v = sys.version.split()[0]
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    add("OK" if sys.version_info >= (3, 10) else "FAIL", f"Python {v}", f"{sys.executable} · {'venv' if in_venv else 'SEM venv (python do sistema)'}",
        "" if sys.version_info >= (3, 10) else "MuJoCo 3.15 exige Python ≥ 3.10")
    mj = ver("mujoco")
    if not mj:
        add("FAIL", "pacote mujoco", "não instalado neste python", "uv sync  (ou: uv pip install 'mujoco>=3.15,<3.16')  e rode com .venv/bin/python")
        return
    try:
        import mujoco  # noqa: PLC0415

        add("OK", f"mujoco {mujoco.__version__}", f"{Path(mujoco.__file__).parent}")
    except Exception as e:  # noqa: BLE001
        add("FAIL", "import mujoco", str(e)[:160], "reinstale: uv pip install --reinstall mujoco")
        return
    for pkg, need in [("numpy", True), ("scipy", False), ("matplotlib", False), ("imageio", False), ("imageio-ffmpeg", False), ("pillow", False),
                      ("glfw", True), ("pyopengl", False), ("absl-py", True)]:
        v2 = ver(pkg)
        add("OK" if v2 else ("FAIL" if need else "INFO"), f"{pkg} {v2 or 'ausente'}", "", "" if v2 else f"uv add {pkg}")
    extras = {"rerun-sdk": "viz", "mujoco-mjx": "gpu", "jax": "gpu", "jaxlib": "gpu", "mujoco-warp": "gpu", "warp-lang": "gpu", "gymnasium": "rl",
              "dm_control": "dmc", "playground": "rl", "urdf2mjcf": "urdf", "robot_descriptions": "urdf", "trimesh": "urdf"}
    inst = {k: ver(k) for k in extras}
    have = [f"{k} {v}" for k, v in inst.items() if v]
    miss = sorted({g for k, g in extras.items() if not inst[k]})
    add("INFO", "opcionais instalados", ", ".join(have) if have else "nenhum", "")
    if miss:
        add("INFO", "grupos opcionais ausentes", ", ".join(miss), "uv sync --group <grupo>   (viz, urdf, rl, gpu)")


def check_session() -> None:
    sess = os.environ.get("XDG_SESSION_TYPE", "?")
    disp, way = os.environ.get("DISPLAY"), os.environ.get("WAYLAND_DISPLAY")
    add("OK" if (disp or way) else "WARN", f"sessão gráfica: {sess}", f"DISPLAY={disp} WAYLAND_DISPLAY={way} XAUTHORITY={'definido' if os.environ.get('XAUTHORITY') else 'vazio'}",
        "" if (disp or way) else "sem display: use render offscreen (MUJOCO_GL=egl) e não abra viewer")
    mg = os.environ.get("MUJOCO_GL")
    add("INFO", f"MUJOCO_GL={mg or '(não definido → glfw)'}", "o backend de render de mujoco.Renderer; o viewer usa GLFW sempre", "")


def check_gl(which: list[str]) -> None:
    for be in which:
        env = dict(os.environ, MUJOCO_GL=be)
        if be == "egl":
            env.setdefault("PYOPENGL_PLATFORM", "egl")
        t = time.perf_counter()
        code, out = run([sys.executable, "-c", GL_PROBE], timeout=90, env=env)
        dt = time.perf_counter() - t
        if code == 0:
            linha = next((ln for ln in reversed(out.splitlines()) if ln.startswith("frame")), out.splitlines()[-1])
            avisos = [ln for ln in out.splitlines() if "WARNING" in ln or "Failed to load plugin" in ln]
            add("OK", f"render offscreen MUJOCO_GL={be}", linha + f" · init+teste {dt:.1f}s" + (f" · avisos benignos: {len(avisos)}" if avisos else ""))
        else:
            tail = out.splitlines()[-1][:200] if out else ""
            lvl = "FAIL" if be == "egl" else "INFO"
            fix = {"egl": "precisa de libEGL + driver (NVIDIA/Mesa); teste: eglinfo -B ; erro de dispositivo → MUJOCO_EGL_DEVICE_ID=0",
                   "osmesa": "indisponível aqui (o pacote mesa do Arch não traz libOSMesa; `pacman -Ss osmesa` vazio) — use EGL; com MUJOCO_GL=osmesa o próprio `import mujoco` quebra",
                   "glfw": "precisa de DISPLAY/WAYLAND_DISPLAY e GLFW; em SSH sem display use egl"}[be]
            add(lvl, f"render offscreen MUJOCO_GL={be}", f"falhou: {tail}", fix)


def check_gpu(deep: bool) -> None:
    if shutil.which("nvidia-smi"):
        code, out = run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"])
        add("OK" if code == 0 else "WARN", "GPU NVIDIA (nvidia-smi)", out.splitlines()[0] if out else "", "" if code == 0 else "driver NVIDIA não responde")
    else:
        add("INFO", "nvidia-smi ausente", "sem GPU NVIDIA visível: MJX roda em CPU; MuJoCo Warp exige NVIDIA", "")
    if not deep:
        return
    if ver("jax"):
        code, out = run([sys.executable, "-c", "import jax; print(jax.__version__, jax.devices())"], timeout=120)
        add("OK" if code == 0 else "WARN", "JAX", out.splitlines()[-1][:200], "" if code == 0 else "jax[cuda13] + driver compatível; JAX_PLATFORMS=cpu força CPU")
    if ver("warp-lang"):
        code, out = run([sys.executable, "-c", "import warp as wp; wp.init(); print(wp.__version__, 'cuda devices:', wp.get_cuda_device_count())"], timeout=120)
        add("OK" if code == 0 else "WARN", "NVIDIA Warp", out.splitlines()[-1][:200], "" if code == 0 else "precisa de driver CUDA; wp.config.log_level = wp.LOG_WARNING silencia o log (wp.config.quiet é obsoleto em Warp 1.17+)")


def check_tools(root: Path) -> None:
    ff = shutil.which("ffmpeg")
    add("OK" if ff else "INFO", "ffmpeg do sistema", ff or "ausente (imageio-ffmpeg traz um binário próprio)", "" if ff else "pacman -S ffmpeg (opcional)")
    up = root / "docs" / "upstream"
    sj = up / "mujoco" / "SOURCE.json"
    if sj.exists():
        meta = json.loads(sj.read_text())
        mj = ver("mujoco")
        same = mj and meta.get("ref", "").lstrip("v") == mj
        add("OK" if same else "WARN", f"espelho de docs {meta.get('ref')} ({meta.get('commit','')[:9]})",
            f"{up}", "" if same else f"mujoco instalado = {mj}; re-sincronize: python3 .agents/mujoco-agent-skill/scripts/sync_docs.py")
    else:
        add("WARN", "espelho da documentação ausente", str(up), "python3 .agents/mujoco-agent-skill/scripts/sync_docs.py")
    skills = sorted(p.name for p in (root / ".agents").glob("*-agent-skill")) if (root / ".agents").is_dir() else []
    add("OK" if skills else "INFO", "skills do projeto", ", ".join(skills) or "nenhuma", "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gl", choices=["egl", "osmesa", "glfw", "all", "none"], default="egl", help="backends de render a testar (padrão egl)")
    ap.add_argument("--gpu", action="store_true", help="também testa JAX/Warp, se instalados")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = find_root()
    check_python_pkgs()
    check_session()
    if ver("mujoco") and a.gl != "none":
        check_gl(["egl", "osmesa", "glfw"] if a.gl == "all" else [a.gl])
    check_gpu(a.gpu)
    check_tools(root)
    if a.json:
        print(json.dumps(ROWS, ensure_ascii=False, indent=1))
    else:
        for r in ROWS:
            print(f"{r['level']:5s} {r['name']}" + (f"  — {r['detail']}" if r["detail"] else ""))
            if r["fix"] and r["level"] in {"FAIL", "WARN", "INFO"}:
                print(f"      → Solução: {r['fix']}")
        n = {k: sum(1 for r in ROWS if r["level"] == k) for k in ("OK", "INFO", "WARN", "FAIL")}
        print(f"\n{n['OK']} OK · {n['INFO']} info · {n['WARN']} avisos · {n['FAIL']} falhas")
    return 1 if any(r["level"] == "FAIL" for r in ROWS) else 0


if __name__ == "__main__":
    sys.exit(main())
