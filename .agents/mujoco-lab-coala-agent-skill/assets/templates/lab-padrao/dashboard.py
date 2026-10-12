#!/usr/bin/env python3
"""dashboard.py — gestão de TREINO no terminal (sem janelas): rondas, progresso, artefactos e próximos passos.

Lê o que o `train.py` deixou em `out/runs/<ronda>/` (`treino.jsonl`, `resumo_treino.json`, `final.zip`,
`best_model.zip`, `checkpoints/`) e responde ao que se pergunta entre rondas: *que ronda está melhor, quanto
treinou, e o que corro agora?*

    uv run --group hover-rl python <exp>/dashboard.py                    # tabela de todas as rondas (1 leitura)
    uv run --group hover-rl python <exp>/dashboard.py --seguir           # atualiza a cada 2 s (Ctrl+C sai)
    uv run --group hover-rl python <exp>/dashboard.py --ronda base       # detalhe de uma ronda
    uv run --group hover-rl python <exp>/dashboard.py --json             # o mesmo em JSON (para scripts)

Nota do padrão: este painel é do TREINO. A simulação ao vivo (janela limpa + site) é o `sim_site.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
RUNS = _AQUI / "out" / "runs"


def ler_jsonl(caminho: Path) -> list[dict]:
    """Linhas JSON válidas de um ficheiro (ignora linhas a meio de escrita — não inventa valores)."""
    if not caminho.exists():
        return []
    linhas = []
    for bruta in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
        if not bruta.startswith("{"):
            continue
        try:
            linhas.append(json.loads(bruta))
        except ValueError:
            continue
    return linhas


def ler_ronda(pasta: Path) -> dict:
    """Resumo de uma ronda: passos, fase, retornos, erro médio, artefactos e idade do último relatório."""
    relatorios = ler_jsonl(pasta / "treino.jsonl")
    resumo = {}
    if (pasta / "resumo_treino.json").exists():
        try:
            resumo = json.loads((pasta / "resumo_treino.json").read_text(encoding="utf-8"))
        except ValueError:
            resumo = {}
    ultimo = relatorios[-1] if relatorios else {}
    com_aval = [r for r in relatorios if r.get("erro_medio_graus") is not None]
    checkpoints = sorted((pasta / "checkpoints").glob("*.zip")) if (pasta / "checkpoints").is_dir() else []
    mtime = max([p.stat().st_mtime for p in pasta.rglob("*") if p.is_file()] or [0.0])
    return {
        "ronda": pasta.name,
        "relatorios": len(relatorios),
        "passos": resumo.get("passos_totais") or ultimo.get("passos"),
        "fase": ultimo.get("fase"),
        "alvo_graus": ultimo.get("alvo_graus"),
        "vento_max": ultimo.get("vento_max"),
        "retorno_medio": ultimo.get("retorno_medio"),
        "melhor_retorno": ultimo.get("melhor_retorno") if ultimo.get("melhor_retorno") is not None
        else (resumo.get("melhor_retorno") or (com_aval[-1].get("retorno_medio") if com_aval else None)),
        "erro_medio_graus": (com_aval[-1].get("erro_medio_graus") if com_aval else resumo.get("erro_medio_graus_final")),
        "fps": ultimo.get("fps"),
        "minutos": round((time.time() - mtime) / 60.0, 1) if mtime else None,
        "final": (pasta / "final.zip").exists(),
        "melhor": (pasta / "best_model.zip").exists(),
        "checkpoints": len(checkpoints),
        "ultimo_checkpoint": checkpoints[-1].name if checkpoints else None,
        "parede_s": resumo.get("parede_s"),
    }


def rondas(filtro: str | None = None) -> list[dict]:
    """Todas as rondas em `out/runs/` (ordenadas pela mais recente), ou só a pedida."""
    if not RUNS.is_dir():
        return []
    pastas = [p for p in RUNS.iterdir() if p.is_dir() and (filtro is None or p.name == filtro)]
    dados = [ler_ronda(p) for p in pastas]
    return sorted(dados, key=lambda r: (r["passos"] or 0), reverse=True)


def fmt(v, casas=2) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{casas}f}"
    return str(v)


def imprimir_tabela(dados: list[dict]) -> None:
    if not dados:
        print(f"sem rondas em {RUNS} — Solução: uv run --group hover-rl python train.py --nome base")
        return
    cab = ("ronda", "passos", "fase", "alvo°", "vento", "ret. médio", "melhor", "erro°", "fps", "final", "best", "ckp", "há min")
    larguras = (14, 8, 5, 6, 6, 11, 11, 7, 8, 6, 5, 4, 7)
    print("  ".join(c.ljust(l) for c, l in zip(cab, larguras)))
    print("-" * (sum(larguras) + 2 * len(larguras)))
    for r in dados:
        linha = (r["ronda"][:14], fmt(r["passos"], 0), fmt(r["fase"], 0), fmt(r["alvo_graus"], 0), fmt(r["vento_max"], 1),
                 fmt(r["retorno_medio"], 1), fmt(r["melhor_retorno"], 1), fmt(r["erro_medio_graus"], 2), fmt(r["fps"], 0),
                 "sim" if r["final"] else "—", "sim" if r["melhor"] else "—", fmt(r["checkpoints"], 0), fmt(r["minutos"], 1))
        print("  ".join(str(c).ljust(l) for c, l in zip(linha, larguras)))


def imprimir_detalhe(r: dict) -> None:
    print(f"ronda {r['ronda']}:")
    for chave in ("passos", "fase", "alvo_graus", "vento_max", "retorno_medio", "melhor_retorno", "erro_medio_graus",
                  "fps", "relatorios", "checkpoints", "ultimo_checkpoint", "parede_s", "minutos"):
        print(f"  {chave:18s} {fmt(r[chave], 2)}")
    print(f"  final.zip          {'sim' if r['final'] else '—'}   best_model.zip  {'sim' if r['melhor'] else '—'}")
    pasta = RUNS / r["ronda"]
    print("\n  próximos passos:")
    if r["checkpoints"] or r["final"]:
        alvo = (pasta / "best_model.zip") if r["melhor"] else (pasta / "final.zip")
        print(f"    simular:  uv run --group hover-rl python {_AQUI.name}/sim_site.py --model {alvo.relative_to(_AQUI)}")
    print(f"    retomar:  uv run --group hover-rl python {_AQUI.name}/train.py --nome {r['ronda']}_r2 "
          f"--retomar {pasta.relative_to(_AQUI)}/final.zip")
    print(f"    deploy:   uv run --group hover-rl python {_AQUI.name}/deploy.py --skip-multi")


def seguinte(dados: list[dict]) -> None:
    """Diz qual é a melhor ronda (por erro médio, desempate pelo retorno) e o comando para a usar."""
    com_erro = [r for r in dados if r["erro_medio_graus"] is not None]
    if not com_erro:
        return
    melhor = min(com_erro, key=lambda r: (r["erro_medio_graus"], -(r["melhor_retorno"] or -1e9)))
    pasta = RUNS / melhor["ronda"] / ("best_model.zip" if melhor["melhor"] else "final.zip")
    print(f"\nmelhor ronda por erro médio: {melhor['ronda']} ({fmt(melhor['erro_medio_graus'], 3)}°)")
    print(f"  usar:  uv run --group hover-rl python {_AQUI.name}/sim_site.py --model {pasta.relative_to(_AQUI)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Painel de TREINO do template lab-padrao (só leitura, sem janelas).",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Este painel é SÓ LEITURA: nunca escreve em out/runs/. "
                                        "Para a simulação ao vivo usa o sim_site.py.")
    ap.add_argument("--ronda", default=None, help="detalhe de uma ronda (nome da pasta em out/runs/)")
    ap.add_argument("--json", action="store_true", help="imprime o relatório em JSON e sai")
    ap.add_argument("--seguir", action="store_true", help="atualiza a cada --intervalo s até Ctrl+C")
    ap.add_argument("--intervalo", type=float, default=2.0, help="período do --seguir (s)")
    a = ap.parse_args(argv)
    try:
        while True:
            dados = rondas(a.ronda)
            if a.json:
                print(json.dumps(dados, indent=2, ensure_ascii=False))
            elif a.ronda:
                if not dados:
                    print(f"ronda '{a.ronda}' não existe em {RUNS}")
                    return 1
                imprimir_detalhe(dados[0])
            else:
                imprimir_tabela(dados)
                seguinte(dados)
            if not a.seguir:
                return 0
            time.sleep(max(0.2, a.intervalo))
            print("\n" + "=" * 100 + "\n")
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
