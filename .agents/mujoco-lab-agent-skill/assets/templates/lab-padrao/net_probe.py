#!/usr/bin/env python3
"""net_probe.py — sonda a REDE da política: observação → h1 → h2 → ação → comando físico (sem auto-loop).

Para responder a "o que é que a rede está a ver e a decidir?" sem abrir janela nenhuma:

    uv run --group hover-rl python <exp>/net_probe.py                          # N passos com a melhor política
    uv run --group hover-rl python <exp>/net_probe.py --theta 45 --alvo 60     # UMA observação imposta (isolada)
    uv run --group hover-rl python <exp>/net_probe.py --passos 25 --tabela     # 25 passos, tabelas completas de h1/h2
    uv run --group hover-rl python <exp>/net_probe.py --model out/runs/base/best_model.zip --jsonl out/sonda.jsonl

Regra do padrão: **por omissão NÃO há ciclo automático** — corre exatamente `--passos` passos (ou uma única
observação imposta) e sai com 0. Sem política, a ação é nula (`ctrl = τ_trim`) e as ativações vão vazias («—»):
nada de zeros inventados.

ADAPTAR: os rótulos das entradas/saídas vivem no `env.py` (`N_OBS`/`N_ACT`) e no site (`ROTULOS_OBS/ACT`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

from lab import mjkit  # noqa: F401, I001  (fixa MUJOCO_GL=egl ANTES de `import mujoco`; é efeito de importação)

import numpy as np

import env as env_mod

RUNS = _AQUI / "out" / "runs"


def melhor_modelo() -> Path | None:
    """`best_model.zip` mais recente em `out/runs/*/`; na falta, o `final.zip` mais recente."""
    for nome in ("best_model.zip", "final.zip"):
        candidatos = [p / nome for p in RUNS.glob("*") if (p / nome).exists()]
        if candidatos:
            return max(candidatos, key=lambda p: p.stat().st_mtime)
    return None


def carregar(caminho: Path | None):
    """Carrega a política PPO (`None` = sem política: ação nula e sem ativações)."""
    if caminho is None:
        return None
    from stable_baselines3 import PPO

    return PPO.load(caminho, device="cpu")


def ativacoes(politica, obs) -> tuple[list[float], list[float]]:
    """(h1, h2) — as ativações das duas primeiras camadas `Linear` da MLP da política."""
    if politica is None:
        return [], []
    import torch

    rede = politica.policy.mlp_extractor.policy_net
    camadas = [c for c in rede if isinstance(c, torch.nn.Linear)]
    saidas: list[list[float]] = []

    def guarda(_modulo, _entradas, saida) -> None:
        saidas.append([float(v) for v in saida.detach().reshape(-1)])

    handles = [c.register_forward_hook(guarda) for c in camadas[:2]]
    try:
        with torch.no_grad():
            rede(torch.as_tensor(np.asarray(obs, dtype=np.float32)).reshape(1, -1))
    finally:
        for h in handles:
            h.remove()
    return (saidas[0] if saidas else []), (saidas[1] if len(saidas) > 1 else [])


def resumo_camada(valores: list[float], n: int = 5) -> str:
    """Resumo de uma camada: nº de nós, média, máximo |a| e os `n` nós mais ativos (índice:valor)."""
    if not valores:
        return "—"
    a = np.asarray(valores, dtype=float)
    ordem = np.argsort(-np.abs(a))[:n]
    picos = " ".join(f"{int(i)}:{a[i]:+.2f}" for i in ordena_seguro(ordem))
    return f"{len(valores)} nós · média {a.mean():+.3f} · max|a| {np.abs(a).max():.3f} · picos {picos}"


def ordena_seguro(ordem) -> list[int]:
    """Índices por ordem decrescente de |a| (passa pelo `int` para o `argsort` não vazar `np.int64`)."""
    return [int(i) for i in ordem]


def tabela(nome: str, valores: list[float], rotulos=None) -> str:
    """Tabela completa `índice rótulo valor barra` de um vetor (para `--tabela`)."""
    if not valores:
        return f"{nome}: —"
    linhas = [f"{nome} ({len(valores)}):"]
    for i, v in enumerate(valores):
        rotulo = rotulos(i) if rotulos else f"{nome}[{i}]"
        barra = "█" * min(20, round(20 * min(1.0, abs(v) / max(1e-9, max(abs(x) for x in valores)))))
        linhas.append(f"  {i:3d} {rotulo:16s} {v:+8.4f} {barra}")
    return "\n".join(linhas)


def registo(env, obs, politica, acao, h1, h2, ctrl) -> dict:
    """Uma linha de sonda (JSON serializável) com tudo o que a rede viu e decidiu."""
    vel, azim = env.vento_polar()
    return {"t": round(float(env.data.time), 6), "passo": int(env.passos),
            "theta_graus": round(float(np.degrees(env.theta)), 4),
            "alvo_graus": round(float(np.degrees(env.theta_alvo)), 4),
            "erro_graus": round(float(np.degrees(env.erro)), 4), "vento_vel": round(vel, 4),
            "vento_azim": round(azim, 2), "obs": [round(float(x), 6) for x in np.asarray(obs).reshape(-1)],
            "h1": [round(float(x), 6) for x in h1], "h2": [round(float(x), 6) for x in h2],
            "act": [round(float(x), 6) for x in np.asarray(acao).reshape(-1)],
            "ctrl_Nm": round(float(np.asarray(ctrl).reshape(-1)[0]), 6) if np.size(ctrl) else None}


def imprimir(l: dict, politica, completa: bool) -> None:
    """Imprime uma linha de sonda: sempre θ/erro/vento/obs/ação; h1/h2 em resumo (ou tabela completa)."""
    tem_pol = politica is not None
    print(f"t={l['t']:7.3f}s passo={l['passo']:4d} θ={l['theta_graus']:+7.2f}° erro={l['erro_graus']:+6.2f}° "
          f"vento={l['vento_vel']:.2f} m/s @ {l['vento_azim']:.0f}°")
    print(f"  obs  {' '.join(f'{v:+.3f}' for v in l['obs'])}")
    if completa:
        print(tabela("h1", l["h1"]))
        print(tabela("h2", l["h2"]))
    else:
        print(f"  h1   {resumo_camada(l['h1'])}")
        print(f"  h2   {resumo_camada(l['h2'])}")
    if not tem_pol:
        print("  (sem política: ação NULA → ctrl = τ_trim; ativações indisponíveis)")
    print(f"  act  {' '.join(f'{v:+.3f}' for v in l['act'])}   ctrl={l['ctrl_Nm']} N·m")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sonda a rede da política (observação → h1 → h2 → ação).",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Sem auto-loop: corre só o que pedires (--passos N ou --theta) e sai 0.")
    ap.add_argument("--model", type=Path, default=None, metavar="CAMINHO.zip",
                    help="política a sondar (padrão: o `best_model.zip` mais recente de out/runs/)")
    ap.add_argument("--passos", type=int, default=10, help="passos a correr com a política (padrão 10; 0 = só a observação imposta)")
    ap.add_argument("--theta", type=float, default=None, help="impõe o ângulo (graus) numa observação ISOLADA (não corre física)")
    ap.add_argument("--alvo", type=float, default=env_mod.ALVO_GRAUS, help="ângulo-alvo (graus)")
    ap.add_argument("--omega", type=float, default=0.0, help="velocidade angular imposta (rad/s), com --theta")
    ap.add_argument("--vento", type=float, default=0.0, help="vento em m/s durante a sonda")
    ap.add_argument("--vento-azimute", type=float, default=0.0, help="azimute do vento (graus)")
    ap.add_argument("--tabela", action="store_true", help="tabela completa de h1/h2 (senão só o resumo)")
    ap.add_argument("--jsonl", type=Path, default=None, metavar="CAMINHO", help="escreve as linhas da sonda em JSONL")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    caminho = a.model or melhor_modelo()
    politica = carregar(caminho)
    env = env_mod.novo_env(theta_alvo_graus=a.alvo, jitter=False, seed=a.seed)
    print(f"[sonda] política: {caminho if caminho else 'NENHUMA (ação nula; ativações indisponíveis)'}")
    print(f"[sonda] obs {env_mod.N_OBS} → ação {env_mod.N_ACT} · alvo {a.alvo:.1f}° · vento {a.vento:.2f} m/s")

    fich = a.jsonl.open("w", encoding="utf-8") if a.jsonl else None
    linhas: list[dict] = []
    try:
        if a.theta is not None:                       # observação ISOLADA (sem física: só a rede a responder)
            env.reset(seed=a.seed)
            env.data.qpos[env.qadr] = np.radians(a.theta)
            env.data.qvel[env.dof] = a.omega
            env.definir_vento(a.vento, a.vento_azimute, 0.0)
            import mujoco

            mujoco.mj_forward(env.model, env.data)
            obs = env.observacao()
            acao = np.zeros(env_mod.N_ACT, dtype=np.float32) if politica is None else np.asarray(
                politica.predict(obs, deterministic=True)[0], dtype=np.float32).reshape(-1)[: env_mod.N_ACT]
            h1, h2 = ativacoes(politica, obs)
            ctrl = [env.acao_para_ctrl(acao)]
            l = registo(env, obs, politica, acao, h1, h2, ctrl)
            linhas.append(l)
            imprimir(l, politica, a.tabela)
        for _ in range(max(0, a.passos)):             # N passos, sem auto-loop: acaba e sai
            obs = env.observacao()
            acao = np.zeros(env_mod.N_ACT, dtype=np.float32) if politica is None else np.asarray(
                politica.predict(obs, deterministic=True)[0], dtype=np.float32).reshape(-1)[: env_mod.N_ACT]
            h1, h2 = ativacoes(politica, obs)
            ctrl = [env.acao_para_ctrl(acao)]
            env.definir_vento(a.vento, a.vento_azimute, 0.0)
            _obs, recompensa, terminado, truncado, _info = env.step(acao)
            l = registo(env, obs, politica, acao, h1, h2, ctrl)
            l["recompensa"] = round(float(recompensa), 6)
            l["terminou"] = bool(terminado or truncado)
            linhas.append(l)
            imprimir(l, politica, a.tabela)
            if l["terminou"]:
                print("[sonda] episódio terminou — paro (sem auto-reset nesta sonda)")
                break
    finally:
        if fich is not None:
            for l in linhas:
                fich.write(json.dumps(l, ensure_ascii=False) + "\n")
            fich.close()
            print(f"[sonda] {len(linhas)} linhas em {a.jsonl}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
