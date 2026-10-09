#!/usr/bin/env python3
"""new_experiment.py — cria experiments/NN_nome/ a partir de um template testado da skill.

    python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py --list                      # templates disponíveis
    python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py meu_robo --template lab-padrao
    python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py drone_hover --template quadrotor
    python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py pendulo --template pendulum
    python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py meu_teste                    # template "blank"
    python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py x --dry-run

O que faz: acha a raiz do projeto (pyproject.toml), calcula o próximo número NN, copia o template para experiments/NN_nome/, garante lab/mjkit.py
(symlink para a skill quando ela mora no projeto, senão cópia) e .gitignore com experiments/*/out/. Não sobrescreve nada existente.

Templates: `blank|pendulum|arm|quadrotor|car` são UM `model.xml` + `run.py` + `README.md` (física + validação).
`lab-padrao` é o TEMPLATE BASE completo do laboratório (env Gymnasium + run + train PPO + view + sim_view/sim_site
do padrão `padrao-simulacao-clean-site` + site React + deploy ONNX + LEIAME/INTERFACE). Com ele o nome do
experimento é substituído nos sítios certos (ver `SUBSTITUICOES`) e o `lab-padrao/LEIAME.md` passou a `LEIAME.md`.

Exit 0 ok · 1 erro operacional · 2 uso inválido.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
TEMPLATES = SKILL / "assets" / "templates"

# Templates que NÃO são um único par model.xml+run.py: têm árvore própria (site/, LEIAME.md, vários módulos) e
# precisam de substituições de nome. `lab-padrao` é o template base do laboratório (padrão janela limpa + site).
TEMPLATES_ARVORE = {"lab-padrao"}
# (ficheiro relativo ao template, texto a substituir, substituição) — aplicadas depois da cópia, só em ficheiros existentes.
SUBSTITUICOES = [
    ("README.md", "{{NOME_EXPERIMENTO}}", "{nome}"),
    ("LEIAME.md", "{{NOME_EXPERIMENTO}}", "{nome}"),
    ("INTERFACE.md", "{{NOME_EXPERIMENTO}}", "{nome}"),
    ("site/index.html", "{{NOME_EXPERIMENTO}}", "{nome}"),
    ("site/package.json", "{{NOME_PACOTE}}", "{pacote}"),
    ("site/src/lib/sim.ts", "{{NOME_EXPERIMENTO}}", "{nome}"),
]
# Ficheiros/diretórios que o experimento NUNCA deve herdar do template (saídas e caches; o `dist/` é construído).
IGNORAR = ("__pycache__", "out", "node_modules", "dist", ".vite", "MUJOCO_LOG.TXT", ".pytest_cache", ".ruff_cache")


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
    conteudo = sorted(p.name for p in src.iterdir() if p.is_file() or p.is_dir() and p.name not in IGNORAR)
    plan = [f"criar {dest.relative_to(root)}/ ← template '{a.template}': " + ", ".join(conteudo)]
    if a.template in TEMPLATES_ARVORE:
        plan.append(f"substituir os marcadores de nome em {len(SUBSTITUICOES)} ficheiro(s) "
                    f"({{{{NOME_EXPERIMENTO}}}} → {slug(a.nome)}); os passos de validação saem no fim")

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

    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*IGNORAR))
    nome = slug(a.nome)
    # Permissões em TODA a árvore: os .py executáveis (têm shebang) e os DIRETÓRIOS 755 — sem o bit de
    # execução num diretório não se entra nele (bug real apanhado ao criar o 1.º experimento de árvore).
    for f in dest.rglob("*"):
        f.chmod(0o755 if (f.is_dir() or f.suffix == ".py") else 0o644)
    for f in dest.glob("*"):
        if f.name == "README.md":
            txt = f.read_text(encoding="utf-8")
            f.write_text(f"<!-- criado de assets/templates/{a.template} por new_experiment.py -->\n" + txt, encoding="utf-8")
    # marca de proveniência + substituição dos marcadores (só no template de árvore)
    if a.template in TEMPLATES_ARVORE:
        marcador = f"<!-- criado de assets/templates/{a.template} por new_experiment.py -->\n"
        (dest / "LEIAME.md").write_text(marcador + (dest / "LEIAME.md").read_text(encoding="utf-8"), encoding="utf-8")
        trocas = 0
        for relativo, de, para in SUBSTITUICOES:
            alvo = dest / relativo
            if not alvo.exists():
                continue
            txt = alvo.read_text(encoding="utf-8")
            novo = txt.replace(de, para.format(nome=nome, pacote=f"{nome}-site"))
            if novo != txt:
                alvo.write_text(novo, encoding="utf-8")
                trocas += 1
        print(f"  · marcadores de nome substituídos em {trocas} ficheiro(s)")
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
    rel = dest.relative_to(root)
    if a.template in TEMPLATES_ARVORE:
        print(f"\nPronto: {rel}  (TEMPLATE BASE: lê {rel}/LEIAME.md — o que adaptar e o que NUNCA mudar)")
        print(f"  1) validar:  uv run --group hover-rl python {rel}/run.py            # exit 0 = física sã")
        print(f"  2) treinar:  uv run --group hover-rl python {rel}/train.py --timesteps 200000 --nome base")
        print(f"  3) padrão:   uv run --group hover-rl python {rel}/sim_site.py        # janela 3D limpa + site")
        print(f"     site:      (cd {rel}/site && node ensure-setup.mjs && npm run build)  # uma vez")
    else:
        print(f"\nPronto: {rel}\n  rodar:  uv run python {rel}/run.py --sem-video\n  janela: uv run python {rel}/run.py --view")
    return 0


if __name__ == "__main__":
    sys.exit(main())
