#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/ab_treino.py — A/B de HIPERPARÂMETROS do treino PPO, sem interface.

A pergunta: «o treino está otimizado?» tem duas metades. O DÉBITO (passos por segundo) é do `bench_treino.py`.
Esta é a outra: a mesma quantidade de passos de ambiente aprende MAIS com outros hiperparâmetros? Responde-se
como se responde a tudo neste laboratório — medindo: cada BRAÇO é um conjunto de flags do `train.py`, corre nas
MESMAS sementes e com o MESMO orçamento de passos, e comparam-se as curvas de avaliação (`evaluations.npz`: os
10 episódios determinísticos sem vento que o `EvalCallback` corre a cada 40 000 passos de ambiente).

    uv run --group hover-rl python experiments/09_drone_hover_rl/ab_treino.py \\
        --comuns "--retomar $PWD/experiments/09_drone_hover_rl/out/real_endurance15_rajadas/final.zip" \\
        --braco base= --braco lr3e4_kl="--lr 3e-4 --target-kl 0.02"            # 3 sementes × 1,5 M passos

O que se compara (por braço: média ± desvio-padrão entre sementes, e semente a semente):
  · retorno de avaliação a 25 / 50 / 75 / 100 % do orçamento (interpolado na grelha comum);
  · ÁREA sob a curva ÷ orçamento = o retorno médio ao longo do treino (quem aprende mais cedo ganha aqui);
  · o melhor retorno visto e a que passo foi;
  · do `train_diag.jsonl`: `approx_kl` e `clip_fraction` médios (o tamanho real do passo da política).
A comparação é POR PASSOS, não por relógio: pode correr com a máquina ocupada (o débito mede-se à parte).

QUE TAREFA: na planta real o treino DO ZERO cai no atrator «sentar no chão» com qualquer hiperparâmetro (retorno
≈ 331 com z ≈ 0,115 m ao fim de 240–560 k passos — reproduzido aqui em 2026-10-13 com `lr 1e-4` e com `lr 3e-4`),
por isso um A/B do zero não mede nada. A tarefa com curva que mexe é a RECEITA real do projeto: o ARRANQUE A
QUENTE (`--comuns "--retomar out/real_endurance15_rajadas/final.zip"`: a política do frame antigo afinada na
planta de 1950 mm, 517 → ~670 de retorno em 3 M passos).

O limiar de sucesso do `train.py` (que pára o treino cedo) fica desligado (`--sucesso` enorme): todos os runs
gastam o orçamento inteiro, senão as curvas não se comparam. Um braço «ganha» quando é melhor na área E no fim
em TODAS as sementes pareadas — com 3 sementes isto é evidência modesta, e o relatório di-lo.

Saída: `out/ab_treino/<braço>/seed<s>/` (os runs) e `out/ab_treino/resultado.json`. Exit 0 se todos os runs
acabaram; 1 se algum falhou.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
SAIDA = _AQUI / "out" / "ab_treino"
FRACOES = (0.25, 0.5, 0.75, 1.0)
SEM_LIMIAR = 1.0e9          # `--sucesso` impossível: o treino nunca pára cedo


def ler_bracos(pares: list[str]) -> dict[str, list[str]]:
    """`nome=flags do train.py` → {nome: [flags…]} (a ordem do CLI é a ordem do relatório)."""
    bracos: dict[str, list[str]] = {}
    for par in pares:
        nome, sep, flags = par.partition("=")
        nome = nome.strip()
        if not sep or not nome or not nome.replace("_", "").replace("-", "").isalnum():
            raise SystemExit(f"--braco {par!r}: use nome=\"flags do train.py\" (nome alfanumérico; flags podem ser vazias)")
        if nome in bracos:
            raise SystemExit(f"--braco {nome!r} repetido")
        bracos[nome] = shlex.split(flags)
    if len(bracos) < 2:
        raise SystemExit("um A/B precisa de pelo menos dois --braco")
    return bracos


def comando(braco: str, flags: list[str], semente: int, args: argparse.Namespace) -> tuple[list[str], Path]:
    pasta = args.saida / braco / f"seed{semente}"
    cmd = [sys.executable, str(_AQUI / "train.py"), "--planta", args.planta, "--timesteps", str(args.timesteps),
           "--n-envs", str(args.n_envs), "--seed", str(semente), "--sem-painel", "--out-dir", str(pasta),
           "--sucesso", f"{SEM_LIMIAR:g}", "--eval-envs", str(args.eval_envs), *args.comuns, *flags]
    return cmd, pasta


def correr(tarefa: tuple[str, list[str], int, argparse.Namespace]) -> dict:
    braco, flags, semente, args = tarefa
    cmd, pasta = comando(braco, flags, semente, args)
    pasta.mkdir(parents=True, exist_ok=True)
    feito = pasta / "evaluations.npz"
    if feito.is_file() and (pasta / "final.zip").is_file() and not args.refazer:
        return {"braco": braco, "seed": semente, "pasta": str(pasta), "rc": 0, "s": 0.0, "reaproveitado": True}
    t0 = time.perf_counter()
    env = dict(os.environ, MUJOCO_GL=os.environ.get("MUJOCO_GL", "egl"), OMP_NUM_THREADS="1")
    with (pasta / "treino.log").open("w", encoding="utf-8") as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(pasta), env=env, check=False).returncode
    dt = time.perf_counter() - t0
    print(f"  [{braco} · seed {semente}] rc={rc} em {dt / 60:.1f} min", flush=True)
    return {"braco": braco, "seed": semente, "pasta": str(pasta), "rc": rc, "s": dt, "reaproveitado": False}


def curva(pasta: Path) -> tuple[np.ndarray, np.ndarray]:
    """(passos DESTE run, retorno médio dos episódios de avaliação) do `evaluations.npz`.

    Com `--retomar` o contador do SB3 continua o do checkpoint (a 1.ª avaliação vem a 2,5 M + 40 k…): os passos
    passam a contar-se desde o início deste run — a 1.ª avaliação fica a UM intervalo de avaliação do zero.
    """
    dados = np.load(pasta / "evaluations.npz")
    passos = np.asarray(dados["timesteps"], dtype=float)
    intervalo = float(np.median(np.diff(passos))) if passos.size > 1 else float(passos[0])
    return passos - (passos[0] - intervalo), np.asarray(dados["results"], dtype=float).mean(axis=1)


def diagnostico(pasta: Path) -> dict:
    """Médias do `train_diag.jsonl` (KL aproximada e fração cortada) — `{}` se o ficheiro não existir."""
    ficheiro = pasta / "train_diag.jsonl"
    if not ficheiro.is_file():
        return {}
    kl, clip = [], []
    for linha in ficheiro.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        if isinstance(d.get("approx_kl"), (int, float)):
            kl.append(float(d["approx_kl"]))
        if isinstance(d.get("clip_fraction"), (int, float)):
            clip.append(float(d["clip_fraction"]))
    return {"approx_kl": float(np.mean(kl)) if kl else None, "clip_fraction": float(np.mean(clip)) if clip else None,
            "atualizacoes": len(kl)}


def metricas(pasta: Path, orcamento: int) -> dict:
    passos, retorno = curva(pasta)
    grelha = np.linspace(passos[0], orcamento, 200)
    interp = np.interp(grelha, passos, retorno)                       # para lá da última avaliação: o último valor
    i = int(np.argmax(retorno))
    return {**{f"r_{int(100 * f)}": float(np.interp(f * orcamento, passos, retorno)) for f in FRACOES},
            "area": float(interp.mean()), "melhor": float(retorno[i]), "passo_do_melhor": int(passos[i]),
            "avaliacoes": int(passos.size), "ultimo_passo": int(passos[-1]), **diagnostico(pasta)}


def resumir(por_semente: dict[int, dict]) -> dict:
    chaves = ("r_25", "r_50", "r_75", "r_100", "area", "melhor", "approx_kl", "clip_fraction")
    out: dict = {}
    for c in chaves:
        v = np.array([m[c] for m in por_semente.values() if m.get(c) is not None], dtype=float)
        if v.size:
            out[c] = {"media": float(v.mean()), "dp": float(v.std(ddof=1)) if v.size > 1 else 0.0}
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--braco", action="append", default=[], metavar='NOME="FLAGS"',
                   help="um braço: nome=flags do train.py (repetir; o 1.º é a referência das diferenças)")
    p.add_argument("--timesteps", type=int, default=1_500_000, help="orçamento de passos de ambiente por run")
    p.add_argument("--sementes", default="0,1,2")
    p.add_argument("--planta", default="real", choices=("real", "cf2"))
    p.add_argument("--n-envs", type=int, default=16)
    p.add_argument("--eval-envs", type=int, default=4)
    p.add_argument("--paralelo", type=int, default=2, help="runs em simultâneo (cada um usa n_envs + eval_envs processos)")
    p.add_argument("--comuns", type=shlex.split, default=[],
                   help="flags do train.py comuns a TODOS os braços (caminhos ABSOLUTOS: cada run corre na sua pasta)")
    p.add_argument("--saida", type=Path, default=SAIDA)
    p.add_argument("--refazer", action="store_true", help="volta a treinar mesmo os runs que já acabaram")
    args = p.parse_args(argv)
    bracos = ler_bracos(args.braco)
    sementes = [int(s) for s in args.sementes.split(",") if s.strip()]
    tarefas = [(b, flags, s, args) for s in sementes for b, flags in bracos.items()]     # intercalado por semente
    print(f"A/B DO TREINO · planta {args.planta} · {args.timesteps:,} passos × sementes {sementes} × braços "
          f"{list(bracos)} = {len(tarefas)} runs · {args.paralelo} em simultâneo · {args.n_envs} envs", flush=True)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, args.paralelo)) as pool:
        feitos = list(pool.map(correr, tarefas))
    falhas = [f for f in feitos if f["rc"] != 0]
    resultado: dict = {"gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "planta": args.planta, "timesteps": args.timesteps,
                       "sementes": sementes, "n_envs": args.n_envs, "comuns": args.comuns,
                       "bracos": {b: {"flags": flags} for b, flags in bracos.items()},
                       "falhas": [{k: f[k] for k in ("braco", "seed", "rc")} for f in falhas],
                       "duracao_s": time.perf_counter() - t0}
    for b in bracos:
        por_semente = {}
        for f in feitos:
            if f["braco"] == b and f["rc"] == 0:
                try:
                    por_semente[f["seed"]] = metricas(Path(f["pasta"]), args.timesteps)
                except (OSError, KeyError, ValueError, IndexError) as erro:
                    falhas.append(f)
                    print(f"  [{b} · seed {f['seed']}] sem curva de avaliação: {erro}", flush=True)
        resultado["bracos"][b]["por_semente"] = por_semente
        resultado["bracos"][b]["resumo"] = resumir(por_semente)

    ref = next(iter(bracos))
    print(f"\n{'braço':14s} {'25 %':>14s} {'50 %':>14s} {'75 %':>14s} {'100 %':>14s} {'área':>14s} {'KL':>8s} {'clip':>6s}")
    for b in bracos:
        r = resultado["bracos"][b]["resumo"]
        celulas = [f"{r[c]['media']:7.1f} ± {r[c]['dp']:4.1f}" if c in r else f"{'—':>14s}"
                   for c in ("r_25", "r_50", "r_75", "r_100", "area")]
        kl = f"{r['approx_kl']['media']:.4f}" if "approx_kl" in r else "—"
        cf = f"{100 * r['clip_fraction']['media']:.1f}%" if "clip_fraction" in r else "—"
        print(f"{b:14s} " + " ".join(f"{c:>14s}" for c in celulas) + f" {kl:>8s} {cf:>6s}")
    comparacoes = {}
    for b in list(bracos)[1:]:
        a_ref, a_b = resultado["bracos"][ref]["por_semente"], resultado["bracos"][b]["por_semente"]
        comuns = sorted(set(a_ref) & set(a_b))
        d_area = [a_b[s]["area"] - a_ref[s]["area"] for s in comuns]
        d_fim = [a_b[s]["r_100"] - a_ref[s]["r_100"] for s in comuns]
        ganha = bool(comuns) and all(x > 0 for x in d_area) and all(x > 0 for x in d_fim)
        perde = bool(comuns) and all(x < 0 for x in d_area) and all(x < 0 for x in d_fim)
        comparacoes[b] = {"sementes": comuns, "delta_area": d_area, "delta_fim": d_fim,
                          "veredicto": "melhor em todas as sementes" if ganha else
                          "pior em todas as sementes" if perde else "sem diferença consistente"}
        print(f"\n{b} − {ref} (pareado por semente {comuns}): Δárea {[round(x, 1) for x in d_area]} · "
              f"Δfim {[round(x, 1) for x in d_fim]} → {comparacoes[b]['veredicto']}")
    resultado["comparacoes"] = comparacoes
    args.saida.mkdir(parents=True, exist_ok=True)
    (args.saida / "resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {args.saida / 'resultado.json'} ({resultado['duracao_s'] / 60:.0f} min)"
          + (f" · {len(falhas)} run(s) FALHARAM" if falhas else ""))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
