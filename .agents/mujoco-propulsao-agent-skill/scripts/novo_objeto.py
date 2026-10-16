#!/usr/bin/env python3
"""novo_objeto.py — planta um objeto propulsado (motores · propulsão · carga explosiva) pronto a adaptar.

    python3 .agents/mujoco-propulsao-agent-skill/scripts/novo_objeto.py meu_objeto
    python3 .agents/mujoco-propulsao-agent-skill/scripts/novo_objeto.py meu_objeto --destino /caminho/livre
    python3 .agents/mujoco-propulsao-agent-skill/scripts/novo_objeto.py --list

Por omissão cria `experiments/NN_<nome>/` (NN = próximo número livre) a partir do template testado
`assets/templates/objeto-propulsado/`, renomeia o módulo `objeto_propulsao.py` → `<nome>.py` e
substitui os identificadores. Depois: `uv run python experiments/NN_<nome>/run.py` (exit 0 = física são).

O template é AUTÓNOMO (sem `lab/`): quando o objeto for usado por vários experimentos, sobe o
`<nome>.py` para `lab/<nome>.py` e o `modelo.xml` para `models/<nome>/` (padrão do laboratório).
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent
TEMPLATES = SKILL / "assets" / "templates"
TEMPLATE = TEMPLATES / "objeto-propulsado"
EXCLUIR = {"__pycache__", "out", "node_modules", ".git"}
IDENTIFICADORES = ("objeto_propulsao", "objeto_propulsado")   # módulo, modelo/experimento


def raiz_projeto() -> Path:
    for p in [Path.cwd(), *Path(__file__).resolve().parents]:
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def proximo_numero(raiz: Path) -> int:
    ns = [int(m.group(1)) for d in (raiz / "experiments").glob("[0-9][0-9]_*")
          if (m := re.match(r"(\d+)_", d.name))]
    return max(ns, default=9) + 1


def copiar(origem: Path, destino: Path, nome: str) -> list[Path]:
    criados: list[Path] = []
    for caminho in sorted(origem.rglob("*")):
        rel = caminho.relative_to(origem)
        if any(part in EXCLUIR for part in rel.parts):
            continue
        alvo = destino / rel
        if caminho.is_dir():
            alvo.mkdir(parents=True, exist_ok=True)
            continue
        if caminho.name == "objeto_propulsao.py":
            alvo = destino / f"{nome}.py"
        alvo.parent.mkdir(parents=True, exist_ok=True)
        texto = caminho.read_text(encoding="utf-8")
        for ident in IDENTIFICADORES:
            texto = texto.replace(ident, nome)
        alvo.write_text(texto, encoding="utf-8")
        criados.append(alvo)
    return criados


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nome", nargs="?", help="nome do objeto (minúsculas, [a-z0-9_])")
    ap.add_argument("--destino", metavar="DIR", help="pasta de destino (por omissão experiments/NN_<nome>)")
    ap.add_argument("--list", action="store_true", help="mostra o template de origem e sai")
    args = ap.parse_args()

    if args.list:
        print(f"template: {TEMPLATE}")
        for p in sorted(TEMPLATE.iterdir()):
            print(f"  {p.name}")
        return 0

    if not args.nome:
        ap.error("falta o <nome> do objeto (ou usa --list)")
    nome = args.nome.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", nome):
        ap.error(f"nome inválido: {args.nome!r} — usa minúsculas, dígitos e _ (ex.: foguete_pequeno)")

    raiz = raiz_projeto()
    destino = Path(args.destino).expanduser().resolve() if args.destino else \
        raiz / "experiments" / f"{proximo_numero(raiz):02d}_{nome}"
    if destino.exists() and any(destino.iterdir()):
        print(f"Erro: destino já existe e não está vazio: {destino} — Solução: escolhe outro nome/caminho",
              file=sys.stderr)
        return 1

    criados = copiar(TEMPLATE, destino, nome)
    rel = destino.relative_to(raiz) if str(destino).startswith(str(raiz)) else destino
    print(f"objeto '{nome}' criado em {rel} ({len(criados)} ficheiros):")
    for f in criados:
        print(f"  {f.relative_to(destino)}")
    print(f"""
PRÓXIMOS PASSOS:
  1. uv run python {rel}/run.py          # valida a física (exit 0) — SEMPRE antes de adaptar
  2. uv run python {rel}/view.py         # janela com as teclas de ação
  3. adapta o modelo às specs REAIS e regista as fontes no README
  4. controlos (tecla → ação, API, site): references/controlos-teclado.md desta skill
  5. hardware real (RPi 5/Arduino): references/rpi5-hardware.md desta skill
  6. no fim: python3 .agents/mujoco-lab-coala-agent-skill/scripts/coala.py add --type semantic \\
       --key "<assunto>" --content "…" --tags propulsao,objeto,{nome}""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
