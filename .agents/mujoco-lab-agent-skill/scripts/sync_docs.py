#!/usr/bin/env python3
"""sync_docs.py — espelha a documentação OFICIAL do MuJoCo como texto local pesquisável.

Faz um clone esparso e raso (git) de cada repositório da DeepMind, copia só TEXTO
(rst/md/py/h/cc/xml/json/...; imagens, vídeos e malhas ficam de fora), converte notebooks
.ipynb em Markdown (só células de texto e código, sem outputs) e regista a proveniência
(ref, commit, data, licença) em SOURCE.json + INDEX.md.

Uso (a partir da raiz do projeto, com a venv do projeto ou qualquer python3 ≥ 3.9):

    python3 .agents/mujoco-lab-agent-skill/scripts/sync_docs.py                    # tudo, versão = mujoco instalado
    python3 .agents/mujoco-lab-agent-skill/scripts/sync_docs.py --only mujoco      # só o repositório principal
    python3 .agents/mujoco-lab-agent-skill/scripts/sync_docs.py --version 3.15.0 --dest docs/upstream
    python3 .agents/mujoco-lab-agent-skill/scripts/sync_docs.py --dry-run

Saída: <dest>/<repo>/... (caminhos estáveis, sem versão no nome) + <dest>/INDEX.md.
Licenças: mujoco/mujoco_warp/playground/mpc = Apache-2.0; menagerie = licença por modelo (ver LICENSE
de cada pasta). Os ficheiros espelhados mantêm os cabeçalhos de copyright originais.

Contrato de erros: `Erro: <o quê> — Solução: <o que fazer>` em stderr; exit 0 ok, 1 operacional, 2 uso.
Não escreve fora de --dest; os clones temporários vão para $TMPDIR (tempfile.mkdtemp).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEXT_EXT = {
    ".rst", ".md", ".txt", ".py", ".h", ".hpp", ".cc", ".cpp", ".xml", ".json", ".toml",
    ".yaml", ".yml", ".cmake", ".sh", ".bib", ".tex", ".ipynb", ".cfg", ".mjcf", ".urdf",
}
SKIP_DIRS = {
    ".git", ".github", "images", "_static", "node_modules", "__pycache__", "assets", "css", "js",
    "templates", "dist", "build", ".venv", "third_party", "html",
}
MAX_BYTES = 1_500_000  # ignora ficheiros de texto gigantes (dados, mapas)

GH = "https://github.com/google-deepmind"
REPOS: dict[str, dict] = {
    "mujoco": {
        "url": f"{GH}/mujoco.git",
        "ref": "{ver}",
        "cone": ["doc", "include", "python", "mjx", "model", "sample", "plugin", "wasm"],
        "license": "Apache-2.0",
    },
    "mujoco_warp": {
        "url": f"{GH}/mujoco_warp.git",
        "ref": "v{ver}",
        "cone": [".agent", "benchmarks", "contrib", "mujoco_warp", "notebooks"],
        "license": "Apache-2.0",
    },
    "mujoco_playground": {
        "url": f"{GH}/mujoco_playground.git",
        "ref": "main",
        "cone": ["mujoco_playground", "learning"],
        "license": "Apache-2.0",
    },
    "mujoco_mpc": {
        "url": f"{GH}/mujoco_mpc.git",
        "ref": "main",
        "cone": ["docs", "python"],
        "license": "Apache-2.0",
    },
    "mujoco_menagerie": {
        "url": f"{GH}/mujoco_menagerie.git",
        "ref": "main",
        # modo não-cone: só READMEs/XMLs/licenças de cada modelo (sem malhas/texturas)
        "nocone": ["/*.md", "/*.py", "/*/*.md", "/*/*.xml", "/*/LICENSE*", "/*/*/*.xml"],
        "license": "por modelo (ver LICENSE de cada pasta)",
    },
}


def die(msg: str, fix: str, code: int = 1) -> None:
    print(f"Erro: {msg} — Solução: {fix}", file=sys.stderr)
    sys.exit(code)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and r.returncode != 0:
        die(f"`{' '.join(cmd[:3])}…` falhou: {r.stderr.strip()[:300]}", "verifique a rede/URL e tente de novo")
    return r


def installed_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("mujoco")
    except Exception:
        return None


def find_project_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists() or (p / ".agents").is_dir():
            return p
    return start


def ref_exists(url: str, ref: str) -> bool:
    out = run(["git", "ls-remote", "--tags", "--heads", url, ref], check=False).stdout
    return bool(out.strip())


def ipynb_to_md(path: Path) -> str:
    nb = json.loads(path.read_text(encoding="utf-8"))
    parts: list[str] = [f"<!-- convertido de {path.name} (outputs removidos) -->"]
    for cell in nb.get("cells", []):
        src = "".join(cell.get("source", []))
        if not src.strip():
            continue
        if cell.get("cell_type") == "markdown":
            parts.append(src)
        elif cell.get("cell_type") == "code":
            parts.append("```python\n" + src.rstrip() + "\n```")
    return "\n\n".join(parts) + "\n"


def copy_filtered(src_root: Path, dst_root: Path, dry: bool) -> tuple[int, int]:
    n_files = n_bytes = 0
    for p in sorted(src_root.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(src_root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        ext = p.suffix.lower()
        name = p.name
        is_license = name.upper().startswith(("LICENSE", "NOTICE", "AUTHORS"))
        if ext not in TEXT_EXT and not is_license:
            continue
        if p.stat().st_size > MAX_BYTES:
            continue
        if ext == ".ipynb":
            dst = dst_root / rel.with_suffix(".ipynb.md")
            data = ipynb_to_md(p).encode("utf-8")
        else:
            dst = dst_root / rel
            data = p.read_bytes()
        n_files += 1
        n_bytes += len(data)
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
    return n_files, n_bytes


def first_heading(p: Path) -> str:
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    for i, ln in enumerate(lines[:60]):
        if p.suffix == ".md" and ln.startswith("#"):
            return ln.lstrip("# ").strip()[:90]
        if p.suffix == ".rst" and i + 1 < len(lines) and re.fullmatch(r"([=\-~^#*])\1{2,}", lines[i + 1].strip() or "x") and ln.strip():
            return ln.strip()[:90]
    return ""


def sync_repo(name: str, spec: dict, ver: str, dest: Path, tmp: Path, dry: bool) -> dict:
    ref = spec["ref"].format(ver=ver)
    if not ref_exists(spec["url"], ref):
        print(f"  aviso: ref '{ref}' não existe em {name}; a usar a ramo principal", file=sys.stderr)
        ref = "main"
    work = tmp / name
    print(f"→ {name} @ {ref}")
    run(["git", "clone", "--quiet", "--depth", "1", "--branch", ref, "--filter=blob:none", "--sparse", spec["url"], str(work)])
    if "nocone" in spec:
        run(["git", "sparse-checkout", "set", "--no-cone", *spec["nocone"]], cwd=work)
    else:
        run(["git", "sparse-checkout", "set", *spec["cone"]], cwd=work)
    commit = run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
    date = run(["git", "log", "-1", "--format=%cs"], cwd=work).stdout.strip()
    out = dest / name
    if out.exists() and not dry:
        shutil.rmtree(out)
    n_files, n_bytes = copy_filtered(work, out, dry)
    meta = {
        "repo": f"{GH}/{name}", "ref": ref, "commit": commit, "commit_date": date,
        "license": spec["license"], "files": n_files, "bytes": n_bytes,
        "synced_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Espelho só de texto (sem imagens/malhas). Fonte da verdade: o repositório acima.",
    }
    if not dry:
        (out / "SOURCE.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"   {n_files} ficheiros · {n_bytes/1e6:.1f} MB · {commit[:10]} ({date})")
    return meta


def write_index(dest: Path, metas: dict[str, dict]) -> None:
    lines = ["# Espelho local da documentação oficial do MuJoCo", "",
             "Gerado por `.agents/mujoco-lab-agent-skill/scripts/sync_docs.py` — **não editar à mão**.",
             "Pesquisar: `python3 .agents/mujoco-lab-agent-skill/scripts/docs_search.py \"termo\"` ou `rg -i termo docs/upstream`.", ""]
    lines += ["| Repo | Ref | Commit | Data | Ficheiros | Licença |", "|---|---|---|---|---|---|"]
    for n, m in metas.items():
        lines.append(f"| `{n}` | `{m['ref']}` | `{m['commit'][:10]}` | {m['commit_date']} | {m['files']} | {m['license']} |")
    lines.append("")
    for n in metas:
        root = dest / n
        docs = [p for p in sorted(root.rglob("*")) if p.suffix in {".rst", ".md"} and p.is_file()]
        # no repo principal, só doc/ e READMEs; nos outros, todos os .md/.rst
        if n == "mujoco":
            docs = [p for p in docs if "doc" in p.relative_to(root).parts[:1] or p.parent == root]
        lines += [f"## {n}", "", "| Ficheiro | Título | KB |", "|---|---|---|"]
        for p in docs[:400]:
            rel = p.relative_to(dest)
            lines.append(f"| `{rel}` | {first_heading(p)} | {p.stat().st_size/1024:.0f} |")
        lines.append("")
    (dest / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", help="versão do MuJoCo (padrão: a instalada, ou a última tag)")
    ap.add_argument("--dest", default=None, help="destino (padrão: <raiz-do-projeto>/docs/upstream)")
    ap.add_argument("--only", help="lista CSV de repos: " + ",".join(REPOS))
    ap.add_argument("--dry-run", action="store_true", help="clona e conta, mas não escreve em --dest")
    a = ap.parse_args()

    ver = a.version or installed_version()
    if not ver:
        tags = run(["git", "ls-remote", "--tags", "--refs", REPOS["mujoco"]["url"]]).stdout.split()
        vs = sorted((t.rsplit("/", 1)[-1] for t in tags if "refs/tags/" in t), key=lambda s: [int(x) if x.isdigit() else 0 for x in re.split(r"[.]", s)])
        ver = vs[-1]
    root = find_project_root(Path.cwd())
    dest = Path(a.dest) if a.dest else root / "docs" / "upstream"
    names = [n.strip() for n in a.only.split(",")] if a.only else list(REPOS)
    bad = [n for n in names if n not in REPOS]
    if bad:
        die(f"repo desconhecido: {bad}", f"use um de: {', '.join(REPOS)}", 2)
    if shutil.which("git") is None:
        die("git não encontrado", "instale o git (pacman -S git)", 3)

    print(f"MuJoCo {ver} → {dest}{' (dry-run)' if a.dry_run else ''}")
    metas: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="mjdocs-") as td:
        for n in names:
            metas[n] = sync_repo(n, REPOS[n], ver, dest, Path(td), a.dry_run)
    if not a.dry_run:
        # mantém no INDEX também os repos já espelhados anteriormente e não pedidos agora
        for n in REPOS:
            sj = dest / n / "SOURCE.json"
            if n not in metas and sj.exists():
                metas[n] = json.loads(sj.read_text(encoding="utf-8"))
        write_index(dest, {n: metas[n] for n in REPOS if n in metas})
        print(f"OK — índice em {dest/'INDEX.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
