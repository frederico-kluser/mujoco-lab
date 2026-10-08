#!/usr/bin/env python3
"""docs_search.py — busca na documentação OFICIAL do MuJoCo espelhada localmente (docs/upstream/).

Sem dependências (stdlib). Modos:

  docs_search.py "contact solref timeconst"          busca full-text ranqueada (BM25) em todo o espelho
  docs_search.py --attr geom.friction                 atributo MJCF: tipo, padrão e descrição (XMLreference.rst)
  docs_search.py --elem actuator/position             elemento MJCF: descrição + lista de atributos com padrões
  docs_search.py --api mj_step                        função C: assinatura + comentário (mujoco.h) + doc (APIreference)
  docs_search.py --type mjtIntegrator                 enum/struct dos headers (mjmodel.h, mjdata.h, …)
  docs_search.py --changelog implicitfast             linhas do changelog agrupadas por versão
  docs_search.py --list                               arquivos espelhados (por repositório)

Opções: --repo mujoco|mujoco_warp|mujoco_playground|mujoco_mpc|mujoco_menagerie · --limit N · --context N · --json · --root DIR

O espelho é criado por `sync_docs.py` (tag do MuJoCo instalado). Sem espelho → `Erro … — Solução: …` e exit 3.
Contrato: exit 0 achou · 1 nada encontrado · 2 uso inválido · 3 espelho ausente.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

TEXT_EXT = {".rst", ".md", ".py", ".h", ".hpp", ".cc", ".cpp", ".xml", ".txt", ".json", ".toml", ".yaml", ".yml", ".cmake", ".sh", ".tex", ".bib"}
TOKEN = re.compile(r"[a-z0-9_]+")


def die(msg: str, fix: str, code: int = 1) -> None:
    print(f"Erro: {msg} — Solução: {fix}", file=sys.stderr)
    sys.exit(code)


def find_root(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
    else:
        p = None
        for base in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
            if (base / "docs" / "upstream").is_dir():
                p = base / "docs" / "upstream"
                break
        if p is None:
            p = Path.cwd() / "docs" / "upstream"
    if not p.is_dir() or not any(p.iterdir()):
        die(f"espelho da documentação não encontrado em {p}",
            "python3 .agents/mujoco-agent-skill/scripts/sync_docs.py  (clona a tag do MuJoCo instalado; ~20 s)", 3)
    return p


def iter_files(root: Path, repo: str | None):
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXT_EXT:
            rel = p.relative_to(root)
            if repo and rel.parts[0] != repo:
                continue
            yield p, rel


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


# ------------------------------------------------------------------------------------------ BM25 full-text
def blocks_of(text: str, suffix: str):
    """Divide em blocos (início_de_linha, texto): parágrafos p/ prosa, janelas de 24 linhas p/ código."""
    lines = text.splitlines()
    out: list[tuple[int, str]] = []
    if suffix in {".rst", ".md", ".txt", ".tex", ".bib"}:
        cur: list[str] = []
        start = 1
        for i, ln in enumerate(lines, 1):
            if ln.strip() == "":
                if cur:
                    out.append((start, "\n".join(cur)))
                    cur = []
                continue
            if not cur:
                start = i
            cur.append(ln)
            if sum(len(x) for x in cur) > 1400:
                out.append((start, "\n".join(cur)))
                cur = []
        if cur:
            out.append((start, "\n".join(cur)))
    else:
        step, win = 18, 24
        for s in range(0, max(1, len(lines)), step):
            chunk = lines[s: s + win]
            if chunk:
                out.append((s + 1, "\n".join(chunk)))
    return out


def fulltext(root: Path, query: str, repo: str | None, limit: int, ctx: int):
    q = [t for t in TOKEN.findall(query.lower()) if t]
    if not q:
        die("consulta vazia", "passe pelo menos um termo", 2)
    docs = []  # (rel, line, text, tokens)
    df: Counter = Counter()
    for p, rel in iter_files(root, repo):
        text = read(p)
        for line, blk in blocks_of(text, p.suffix.lower()):
            toks = TOKEN.findall(blk.lower())
            if not toks:
                continue
            docs.append((rel, line, blk, toks))
            for t in set(toks):
                df[t] += 1
    n = len(docs)
    avg = sum(len(d[3]) for d in docs) / max(1, n)
    phrase = query.lower().strip()
    scored = []
    for rel, line, blk, toks in docs:
        tf = Counter(toks)
        score = 0.0
        hit_terms = 0
        for t in q:
            if tf[t] == 0:
                continue
            hit_terms += 1
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * (tf[t] * 2.2) / (tf[t] + 1.2 * (0.25 + 0.75 * len(toks) / avg))
        if hit_terms == 0:
            continue
        score *= (0.5 + 0.5 * hit_terms / len(q)) * (1.6 if hit_terms == len(q) else 1.0)
        if len(q) > 1 and phrase in blk.lower():
            score *= 1.5
        top = rel.parts[0]
        if "doc/" in str(rel) and rel.suffix in {".rst", ".md"}:
            score *= 1.25
        if "XMLreference" in rel.name or "/skills/" in str(rel):
            score *= 1.1
        if rel.parts[:2] == (top, "python") and rel.name.endswith("_test.py"):
            score *= 0.85
        scored.append((score, rel, line, blk))
    scored.sort(key=lambda x: -x[0])
    return scored[:limit]


# ------------------------------------------------------------------------------------- XML reference lookups
ANCHOR = re.compile(r"^\.\. _([A-Za-z0-9_\-]+):\s*$")


def load_xmlref(root: Path):
    p = root / "mujoco" / "doc" / "XMLreference.rst"
    if not p.exists():
        die("XMLreference.rst ausente no espelho", "rode sync_docs.py --only mujoco", 3)
    return p, read(p).splitlines()


def anchor_blocks(lines: list[str]):
    """{âncora: (linha_inicial, texto)} — texto vai até a próxima âncora."""
    idx = [(i, m.group(1)) for i, ln in enumerate(lines) if (m := ANCHOR.match(ln))]
    out = {}
    for k, (i, name) in enumerate(idx):
        j = idx[k + 1][0] if k + 1 < len(idx) else len(lines)
        out[name] = (i + 1, "\n".join(lines[i + 2: j]).strip("\n"))
    return out, idx


def clean_rst(s: str) -> str:
    s = re.sub(r":at:`([^`]*)`", r"\1", s)
    s = re.sub(r":at-val:`([^`]*)`", r"[\1]", s)
    s = re.sub(r":el-prefix:`([^`]*)`", r"\1", s)
    s = re.sub(r":ref:`([^`<]*)<?[^`]*>?`", r"\1", s)
    s = re.sub(r"\|-\||\|\*\|", "", s)
    return s


def cmd_attr(root: Path, spec: str, limit: int):
    if "." not in spec:
        die("use --attr elemento.atributo (ex.: geom.friction, option.integrator)", "ex.: --attr option.timestep", 2)
    elem, attr = spec.rsplit(".", 1)
    elem = elem.replace("/", "-").lower()
    p, lines = load_xmlref(root)
    blocks, _ = anchor_blocks(lines)
    hits = [(n, b) for n, b in blocks.items() if n.lower().endswith(f"{elem}-{attr.lower()}") or n.lower() == f"{elem}-{attr.lower()}"]
    if not hits:
        cands = [n for n in blocks if attr.lower() in n.lower()][:12]
        die(f"atributo '{spec}' não encontrado", "tente `--elem " + elem + "` ou busca full-text. Parecidos: " + ", ".join(cands), 1)
    for n, (ln, body) in hits[:limit]:
        print(f"[{n}]  XMLreference.rst:{ln}")
        print("  " + clean_rst(body).replace("\n", "\n  "))
        print()
    return 0


def cmd_elem(root: Path, spec: str, limit: int):
    elem = spec.replace("/", "-").lower()
    p, lines = load_xmlref(root)
    blocks, idx = anchor_blocks(lines)
    hits = [n for n in blocks if n.lower() == elem or n.lower().endswith("-" + elem)]
    hits = [n for n in hits if re.search(r":el-prefix:|^\*\*", blocks[n][1][:300]) or n.count("-") <= 2]
    if not hits:
        die(f"elemento '{spec}' não encontrado", "ex.: --elem body/geom · actuator/motor · option · compiler", 1)
    for n in hits[:limit]:
        ln, body = blocks[n]
        # região do elemento: até a próxima âncora cujo bloco comece com :el-prefix:
        order = [a for _, a in idx]
        k = order.index(n)
        attrs = []
        for a in order[k + 1:]:
            b = blocks[a][1]
            if b.lstrip().startswith(":el-prefix:") or b.lstrip().startswith("**"):
                break
            m = re.match(r"\s*:at:`([^`]+)`:\s*:at-val:`([^`]*)`", b)
            if m:
                attrs.append((m.group(1), m.group(2)))
        print(f"[{n}]  XMLreference.rst:{ln}")
        intro = clean_rst(body).split("\n\n")
        print("  " + "\n  ".join(intro[0].splitlines()[:12]))
        if attrs:
            print("  atributos (nome: tipo, padrão):")
            for a, v in attrs:
                print(f"    - {a}: {v}")
        print()
    return 0


# ------------------------------------------------------------------------------------------- C API / tipos
def header_files(root: Path):
    return sorted((root / "mujoco" / "include" / "mujoco").glob("*.h"))


def cmd_api(root: Path, name: str):
    found = False
    for h in header_files(root):
        lines = read(h).splitlines()
        for i, ln in enumerate(lines):
            if re.search(rf"\b{re.escape(name)}\s*\(", ln) and ("MJAPI" in ln or ln.startswith(("MJAPI", "typedef", "extern"))):
                # comentário imediatamente acima
                j = i - 1
                com = []
                while j >= 0 and lines[j].lstrip().startswith("//"):
                    com.insert(0, lines[j].strip())
                    j -= 1
                decl = [ln]
                k = i
                while not decl[-1].rstrip().endswith(";") and k + 1 < len(lines):
                    k += 1
                    decl.append(lines[k])
                print(f"[{h.name}:{i+1}]")
                print("  " + "\n  ".join(com + decl))
                found = True
    p = root / "mujoco" / "doc" / "APIreference" / "functions.rst"
    if p.exists():
        blocks, _ = anchor_blocks(read(p).splitlines())
        if name in blocks:
            ln, body = blocks[name]
            body = re.sub(r"^.*\n[~\-=^]+\n", "", body, count=1)
            body = body.replace(".. mujoco-include:: " + name, "").strip()
            print(f"[doc/APIreference/functions.rst:{ln}]")
            print("  " + body.replace("\n", "\n  "))
            found = True
    if not found:
        die(f"função '{name}' não encontrada nos headers/APIreference", "confira o nome (ex.: mj_step, mj_contactForce, mju_mulQuat); use a busca full-text", 1)
    return 0


def cmd_type(root: Path, name: str):
    found = False
    for h in header_files(root):
        lines = read(h).splitlines()
        for i, ln in enumerate(lines):
            if re.match(rf"\s*typedef\s+(enum|struct)\s+{re.escape(name)}_?\b", ln):
                j = i
                while j < len(lines) and not re.match(rf"\s*\}}\s*{re.escape(name)}\s*;", lines[j]):
                    j += 1
                j = min(j, len(lines) - 1)
                k = i - 1
                com = []
                while k >= 0 and lines[k].lstrip().startswith("//"):
                    com.insert(0, lines[k].strip()); k -= 1
                print(f"[{h.name}:{i+1}-{j+1}]")
                print("  " + "\n  ".join(com + lines[i: j + 1]))
                found = True
                break
    if not found:
        die(f"tipo '{name}' não encontrado nos headers", "exemplos: mjtIntegrator, mjtSensor, mjModel, mjData, mjOption", 1)
    return 0


def cmd_changelog(root: Path, term: str, ctx: int):
    p = root / "mujoco" / "doc" / "changelog.rst"
    if not p.exists():
        die("changelog.rst ausente", "rode sync_docs.py --only mujoco", 3)
    lines = read(p).splitlines()
    version = "?"
    rows: dict[str, list[str]] = defaultdict(list)
    for i, ln in enumerate(lines):
        m = re.match(r"^(Version [0-9][^\n]*|Upcoming version[^\n]*)\s*$", ln)
        if m and i + 1 < len(lines) and re.fullmatch(r"[\-=~^]{3,}", lines[i + 1].strip() or "x"):
            version = m.group(1)
        if term.lower() in ln.lower():
            lo, hi = max(0, i - ctx), min(len(lines), i + ctx + 1)
            rows[version].append(f"  {i+1}: " + " ".join(x.strip() for x in lines[lo:hi] if x.strip()))
    if not rows:
        die(f"'{term}' não aparece no changelog", "tente outro termo ou a busca full-text", 1)
    for v, items in rows.items():
        print(v)
        for it in items[:8]:
            print(it[:500])
    return 0


def cmd_list(root: Path, repo: str | None):
    cnt: Counter = Counter()
    for p, rel in iter_files(root, repo):
        if len(rel.parts) > 1:
            cnt[rel.parts[0]] += 1
    for r, c in cnt.items():
        sj = root / r / "SOURCE.json"
        meta = json.loads(sj.read_text()) if sj.exists() else {}
        print(f"{r:20s} {c:5d} arquivos · ref {meta.get('ref','?')} · commit {str(meta.get('commit','?'))[:10]} · {meta.get('commit_date','?')}")
    print(f"\níndice completo: {root/'INDEX.md'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", help="termos da busca full-text")
    ap.add_argument("--attr"), ap.add_argument("--elem"), ap.add_argument("--api"), ap.add_argument("--type"), ap.add_argument("--changelog")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--repo", choices=["mujoco", "mujoco_warp", "mujoco_playground", "mujoco_mpc", "mujoco_menagerie"])
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--context", type=int, default=0, help="linhas de contexto extra (changelog) ou de snippet")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", help="pasta do espelho (padrão: docs/upstream do projeto)")
    a = ap.parse_args()
    root = find_root(a.root)

    if a.list:
        return cmd_list(root, a.repo)
    if a.attr:
        return cmd_attr(root, a.attr, a.limit)
    if a.elem:
        return cmd_elem(root, a.elem, a.limit)
    if a.api:
        return cmd_api(root, a.api)
    if a.type:
        return cmd_type(root, a.type)
    if a.changelog:
        return cmd_changelog(root, a.changelog, a.context or 1)
    if not a.query:
        ap.print_usage(sys.stderr)
        die("falta a consulta", "ex.: docs_search.py \"solref timeconst\"", 2)
    res = fulltext(root, a.query, a.repo, a.limit, a.context)
    if not res:
        die(f"nada encontrado para '{a.query}'", "tente menos termos, sinônimos em inglês ou --repo outro", 1)
    if a.json:
        print(json.dumps([{"score": round(s, 3), "file": str(r), "line": ln, "text": b} for s, r, ln, b in res], ensure_ascii=False, indent=1))
        return 0
    for i, (s, rel, ln, blk) in enumerate(res, 1):
        print(f"{i}. docs/upstream/{rel}:{ln}  [{s:.1f}]")
        show = blk.splitlines()[: 6 + a.context]
        print("   " + "\n   ".join(x[:160] for x in show))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
