#!/usr/bin/env python3
"""Script oficial da skill `drone-evolucao-benchmark-agent-skill`.

Executa e verifica o pipeline completo de evolução do drone:
  1. `--pesquisar "<consulta>"`: pesquisa na web via `tavily-agent-skill`;
  2. `--treinar`: corre o treino GPU (JAX CUDA + TensorFlow 2.21 OpenXLA) com bola aleatória;
  3. `--benchmark`: corre `benchmark_evolucao.py` (bola programada + vento fixo) e gera `evolucao_drone.png` na raiz;
  4. `--check`: verifica a existência e integridade de `evolucao_drone.png` e `evolucao_estabilidade.json` e imprime
     o resumo explicativo e as tabelas Markdown para `README.md`, `AGENTS.md` e `CLAUDE.md`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
EXP09 = RAIZ / "experiments" / "09_drone_hover_rl"
PNG_RAIZ = RAIZ / "evolucao_drone.png"
JSON_EVOLUCAO = EXP09 / "out" / "evolucao" / "evolucao_estabilidade.json"
TAVILY_SCRIPT = Path("/home/ondokai/.agents/skills/tavily-agent-skill/scripts/tavily.py")


def pesquisar(consulta: str) -> int:
    print(f"[skill:pesquisa] A pesquisar com tavily-agent-skill: {consulta!r}", flush=True)
    cmd = ["python3", str(TAVILY_SCRIPT), "search", consulta, "--depth", "advanced", "--max-wait", "90"]
    return subprocess.call(cmd, cwd=str(RAIZ))


def treinar_gpu() -> int:
    py_gpu = RAIZ / ".venv-gpu" / "bin" / "python"
    py = py_gpu if py_gpu.is_file() else Path(sys.executable)
    print(f"[skill:treino-gpu] A treinar em GPU + TensorFlow OpenXLA ({py})...", flush=True)
    return subprocess.call([str(py), str(EXP09 / "treinar_mira_gpu.py")], cwd=str(RAIZ))


def rodar_benchmark() -> int:
    py_venv = RAIZ / ".venv" / "bin" / "python"
    py = py_venv if py_venv.is_file() else Path(sys.executable)
    print("[skill:benchmark] A correr benchmark determinístico (Bola Programada + Vento Fixo)...", flush=True)
    return subprocess.call([str(py), str(EXP09 / "benchmark_evolucao.py")], cwd=str(RAIZ))


def verificar_e_imprimir() -> int:
    if not PNG_RAIZ.is_file() or PNG_RAIZ.stat().st_size < 10_000:
        print(f"Erro: gráfico {PNG_RAIZ} ausente ou inválido — Solução: corra com --benchmark", file=sys.stderr)
        return 1
    if not JSON_EVOLUCAO.is_file():
        print(f"Erro: JSON {JSON_EVOLUCAO} ausente — Solução: corra com --benchmark", file=sys.stderr)
        return 1
    dados = json.loads(JSON_EVOLUCAO.read_text(encoding="utf-8"))
    geracoes = dados.get("geracoes", [])
    presets = dados.get("presets", [])
    if len(geracoes) < 4 or len(presets) < 6:
        print("Erro: JSON de evolução incompleto", file=sys.stderr)
        return 1

    print(f"[OK] Gráfico na raiz: {PNG_RAIZ} ({PNG_RAIZ.stat().st_size} bytes)")
    print(f"[OK] Dados de evolução: {JSON_EVOLUCAO} ({len(geracoes)} gerações, {len(presets)} presets)\n")
    print("| Geração | Tremor ω_RMS (°/s) | Jitter Motores (%) | Rec. Pós-Tiro (s) | Tiros/min (TPM) | Vento Fixo 3/5 m/s (cm) | Estabilidade (0–100) |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for g in geracoes:
        rot = g["rotulo"].replace("\n", " ")
        print(
            f"| **{rot}** | {g['omega_rms_deg_s']:.2f} | {g['jitter_duty_pct']:.2f} % | "
            f"{g['tempo_recuperacao_tiro_s']:.2f} s | **{g['tiros_por_minuto']:.1f}** ({g['precisao_tiro_pct']:.0f}%) | "
            f"{g['erro_vento_3ms_cm']:.1f} / {g['erro_vento_5ms_cm']:.1f} | **{g['indice_estabilidade']:.1f}** |"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Ciclo de evolução e benchmark determinístico do drone")
    ap.add_argument("--pesquisar", type=str, default=None, help="Consulta web técnica via tavily-agent-skill")
    ap.add_argument("--treinar", action="store_true", help="Executa o treino em GPU + TensorFlow OpenXLA (cenário aleatório)")
    ap.add_argument("--benchmark", action="store_true", help="Executa o benchmark determinístico (bola programada + vento fixo)")
    ap.add_argument("--ciclo-completo", action="store_true", help="Corre treino GPU + benchmark determinístico + verificação")
    ap.add_argument("--check", action="store_true", help="Valida evolucao_drone.png e evolucao_estabilidade.json e imprime tabela")
    args = ap.parse_args()

    if args.pesquisar:
        rc = pesquisar(args.pesquisar)
        if rc != 0:
            return rc
    if args.treinar or args.ciclo_completo:
        rc = treinar_gpu()
        if rc != 0:
            return rc
    if args.benchmark or args.ciclo_completo:
        rc = rodar_benchmark()
        if rc != 0:
            return rc
    if args.check or args.ciclo_completo or not (args.pesquisar or args.treinar or args.benchmark):
        return verificar_e_imprimir()
    return 0


if __name__ == "__main__":
    sys.exit(main())
