#!/usr/bin/env python3
"""new_experiment.py — cria experiments/NN_nome/ a partir de um template testado da skill.

    python3 .agents/mujoco-agent-skill/scripts/new_experiment.py --list                      # templates disponíveis
    python3 .agents/mujoco-agent-skill/scripts/new_experiment.py drone_hover --template quadrotor
    python3 .agents/mujoco-agent-skill/scripts/new_experiment.py pendulo --template pendulum
    python3 .agents/mujoco-agent-skill/scripts/new_experiment.py meu_teste                    # template "blank"
    python3 .agents/mujoco-agent-skill/scripts/new_experiment.py x --dry-run

O que faz: acha a raiz do projeto (pyproject.toml), calcula o próximo número NN, copia model.xml/run.py/README.md do template para experiments/NN_nome/,
garante lab/mjkit.py (symlink para a skill quando ela mora no projeto, senão cópia) e .gitignore com experiments/*/out/.
Não sobrescreve nada existente. Exit 0 ok · 1 erro operacional · 2 uso inválido.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
TEMPLATES = SKILL / "assets" / "templates"


def die(msg: str, fix: str, code: int = 1) -> None:
    print(f"Erro: {msg} — Solução: {fix}", file=sys.stderr)
    sys.exit(code)


def project_root() -> Path:
    for base in [Path.cwd(), *Path.cwd().parents]:
        if (base / "pyproject.toml").exists():
            return base
    die("pyproject.toml não encontrado acima do diretório atual", "rode dentro do projeto do laboratório (ou crie o pyproject.toml com `uv init`)")


def describe(t: Path) -> str:
    r = t / "README.md"
    if r.exists():
        for ln in r.read_text(encoding="utf-8").splitlines():
            if ln.strip() and not ln.startswith("#"):
                return ln.strip()[:110]
        return r.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
    return ""


def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", s.lower().strip()).strip("_")
    if not s:
        die(f"nome inválido: {s!r}", "use letras/números, ex.: drone_hover", 2)
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nome", nargs="?")
    ap.add_argument("--template", default="blank")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--lib", choices=["auto", "symlink", "copy"], default="auto", help="como disponibilizar lab/mjkit.py")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    avail = sorted(p.name for p in TEMPLATES.iterdir() if p.is_dir()) if TEMPLATES.is_dir() else []
    if a.list:
        for n in avail:
            print(f"{n:12s} {describe(TEMPLATES / n)}")
        return 0
    if not a.nome:
        ap.print_usage(sys.stderr)
        die("falta o nome do experimento", "ex.: new_experiment.py drone_hover --template quadrotor", 2)
    if a.template not in avail:
        die(f"template '{a.template}' não existe", f"disponíveis: {', '.join(avail)}", 2)

    root = project_root()
    exp_dir = root / "experiments"
    nums = [int(m.group(1)) for p in exp_dir.glob("[0-9][0-9]_*") if (m := re.match(r"(\d+)_", p.name))] if exp_dir.is_dir() else []
    nn = (max(nums) + 1) if nums else 1
    dest = exp_dir / f"{nn:02d}_{slug(a.nome)}"
    if dest.exists():
        die(f"{dest} já existe", "escolha outro nome")
    src = TEMPLATES / a.template
    plan = [f"criar {dest.relative_to(root)}/ ← template '{a.template}': " + ", ".join(sorted(p.name for p in src.iterdir() if p.is_file()))]

    lab = root / "lab"
    lib_src = SKILL / "scripts" / "mjkit.py"
    lib_dst = lab / "mjkit.py"
    inside = str(SKILL).startswith(str(root))
    mode = a.lib if a.lib != "auto" else ("symlink" if inside else "copy")
    if not lib_dst.exists():
        plan.append(f"{mode} {lib_dst.relative_to(root)} ← skill/scripts/mjkit.py" + ("" if (lab / '__init__.py').exists() else " (+ lab/__init__.py)"))
    gi = root / ".gitignore"
    if not gi.exists() or "experiments/*/out/" not in gi.read_text(encoding="utf-8"):
        plan.append("acrescentar 'experiments/*/out/' ao .gitignore")
    print("\n".join(("PLANO (dry-run):" if a.dry_run else "FAZENDO:", *[f"  · {p}" for p in plan])))
    if a.dry_run:
        return 0

    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "out"))
    for f in dest.glob("*"):
        f.chmod(0o755 if f.suffix == ".py" else 0o644)
        if f.name == "README.md":
            txt = f.read_text(encoding="utf-8")
            f.write_text(f"<!-- criado de assets/templates/{a.template} por new_experiment.py -->\n" + txt, encoding="utf-8")
    lab.mkdir(exist_ok=True)
    (lab / "__init__.py").touch(exist_ok=True)
    if not lib_dst.exists():
        if mode == "symlink":
            lib_dst.symlink_to(Path(*([".."] * 1), SKILL.relative_to(root), "scripts", "mjkit.py"))
        else:
            shutil.copy2(lib_src, lib_dst)
    if not gi.exists() or "experiments/*/out/" not in gi.read_text(encoding="utf-8"):
        with gi.open("a", encoding="utf-8") as fh:
            fh.write("\n# saídas geradas pelos experimentos\nexperiments/*/out/\n")
    print(f"\nPronto: {dest.relative_to(root)}\n  rodar:  uv run python {dest.relative_to(root)}/run.py --sem-video\n  janela: uv run python {dest.relative_to(root)}/run.py --view")
    return 0


if __name__ == "__main__":
    sys.exit(main())
