#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/transferir_politica.py — transfere uma política treinada para a
observação do modo comando (contrato r11) sem a treinar de novo do zero.

PROBLEMA que resolve (medido em 2026-10-10): o cf2 não aprende a VOAR de raiz nem no modo clássico (a
campanha v2b precisou de 20 treinos/25 M passos) e, com a observação de comando, o arranque a partir do
zero cai num atrator: os motores desligados e o drone sentado no chão a colher r≈0,7/ passo. As boas
políticas hover já treinadas (r10, v2b) têm a observação antiga (16 dims no cf2; 21/42 na planta real) e o
`PPO.load` recusa-se a carregá-las no env novo (19/48).

O QUE FAZ: cria um PPO NOVO sobre o env de comando e COPIA os pesos do antigo, alinhando as entradas:

  · cf2:   entrada 16 → 19 — as linhas/colunas dos 3 canais novos (`v_ref` em [16:19]) ficam a ZERO
           (os canais novos não influenciam a saída no arranque; o fine-tune depois ensina-os);
  · real:  ator 21 → 24 (novos em [21:24]) e crítico 42 → 48 — a entrada do crítico é a obs COMPLETA
           [ator | crítico]: o mapa antigo→novo é [0:21]→[0:21] e [21:42]→[24:45] (o `v_ref` do crítico
           entra em [45:48], a zero).

VALIDAÇÃO (obrigatória, sai no fim): para estados SEM comando (`v_ref = 0`) a política nova tem de dar
EXATAMENTE as mesmas ações que a antiga (as linhas novas são zero, logo a função é a mesma) — o teste
compara N estados e falha se max|Δ| > 0. O resultado é um `final.zip` de PPO pronto para
`train.py --retomar` (fine-tune com perfis de comando) ou para o runner (`sim_view.py --model`).

    uv run --group hover-rl python experiments/09_drone_hover_rl/transferir_politica.py \\
        --de out/vento_r10_ft_dryden_600k/best_model.zip --para out/voo_cf2_transferida
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
for _caminho in (_RAIZ, _AQUI):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import torch  # noqa: E402
from stable_baselines3 import PPO  # noqa: E402


def _mapa_entradas(planta: str) -> tuple[int, int, list[tuple[int, int]]]:
    """(dim_antiga, dim_nova, segmentos) do alinhamento da entrada — segmentos [(antigo_ini, novo_ini), …].

    Cada segmento (a, b) copia as linhas [a : a+n] → [b : b+n] onde n = tamanho do segmento; o resto fica 0.
    """
    if planta == "cf2":
        return 16, 19, [(0, 0)]                      # [0:16] → [0:16]; [16:19] a zero
    return 42, 48, [(0, 0), (21, 24)]                # ator [0:21] → [0:21]; crítico [21:42] → [24:45]


def _copia_entrada(camada_antiga: torch.nn.Linear, camada_nova: torch.nn.Linear,
                   segmentos: list[tuple[int, int]], n_antigo: int) -> None:
    """Copia o peso/bias de uma `Linear` alinhando as ENTRADAS pelos segmentos (saídas idênticas)."""
    with torch.no_grad():
        camada_nova.weight.zero_()
        camada_nova.bias.copy_(camada_antiga.bias)
        for a, b in segmentos:
            n = min(n_antigo - a, camada_antiga.weight.shape[1] - a, camada_nova.weight.shape[1] - b)
            camada_nova.weight[:, b:b + n].copy_(camada_antiga.weight[:, a:a + n])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Transfere uma política PPO para a observação do modo comando (contrato r11), "
                    "com as entradas novas a zero e validação de igualdade de ações.")
    p.add_argument("--de", type=Path, required=True, metavar="ZIP", help="política de origem (PPO .zip)")
    p.add_argument("--para", type=Path, required=True, metavar="DIR", help="pasta de saída (final.zip)")
    p.add_argument("--planta", choices=("cf2", "real"), default="cf2",
                   help="planta da política de origem (define o mapa de entradas)")
    p.add_argument("--build", type=str, default=None, help="planta real: build do catálogo (default: ativo)")
    p.add_argument("--modo-acao", choices=("ctbr", "motores"), default="ctbr",
                   help="planta real: modo de ação do env de saída")
    p.add_argument("--n-estados", type=int, default=64, help="estados da validação de igualdade")
    args = p.parse_args(argv)

    if not args.de.is_file():
        raise SystemExit(f"[transferir] origem não existe: {args.de}")
    antigo = PPO.load(str(args.de), device="cpu")
    dim_antiga = int(antigo.observation_space.shape[0])
    planta_real = hasattr(antigo.policy, "_n_ator")
    if (args.planta == "real") != planta_real:
        raise SystemExit(f"[transferir] --planta {args.planta} não casa com a política "
                         f"({'assimétrica (real)' if planta_real else 'MlpPolicy (cf2)'})")

    # env NOVO (modo comando) — só para definir os espaços e validar; sem física corrida
    if planta_real:
        from env_real import DroneRealEnv
        hw = args.de.parent / "hardware.json"
        dados = json.loads(hw.read_text(encoding="utf-8")) if hw.is_file() else {}
        from env_real import build_do_hardware
        build, motivo = build_do_hardware(dados)
        print(f"[transferir] peças da política: {motivo}")
        ambiente = DroneRealEnv(build=build, modo_acao=dados.get("modo_acao", args.modo_acao),
                                aleatorizar=False, comando=True)
    else:
        from env import HoverEnv
        ambiente = HoverEnv(comando=True)
    obs_dim = int(ambiente.observation_space.shape[0])
    dim_esperada, dim_nova, segmentos = _mapa_entradas(args.planta)
    if dim_antiga != dim_esperada:
        raise SystemExit(f"[transferir] a origem tem {dim_antiga} dims; o mapa espera {dim_esperada} "
                         f"(--planta {args.planta})")
    if obs_dim != dim_nova:
        raise SystemExit(f"[transferir] o env de comando dá {obs_dim} dims; o mapa espera {dim_nova}")

    novos = {}
    if planta_real:
        from politica import PoliticaAssimetrica
        novos = {"n_ator": int(antigo.policy._n_ator) + 3}
        politica_cls = PoliticaAssimetrica
    else:
        politica_cls = "MlpPolicy"
    modelo = PPO(politica_cls, ambiente, policy_kwargs={
        **novos,
        "net_arch": {"pi": [64, 64] if not planta_real else [128, 128],
                     "vf": [64, 64] if not planta_real else [128, 128]},
        "activation_fn": torch.nn.Tanh,
        "log_std_init": float(antigo.policy.log_std.detach().mean().item()),
    }, device="cpu", seed=0)

    # ---- cópia dos pesos: extratores (Linear de entrada com REALINHAMENTO) + cabeças + log_std
    pares = [(antigo.policy.mlp_extractor.policy_net, modelo.policy.mlp_extractor.policy_net),
             (antigo.policy.mlp_extractor.value_net, modelo.policy.mlp_extractor.value_net)]
    for origem, destino in pares:
        lineares_a = [m for m in origem.modules() if isinstance(m, torch.nn.Linear)]
        lineares_b = [m for m in destino.modules() if isinstance(m, torch.nn.Linear)]
        assert len(lineares_a) == len(lineares_b), "arquitetura de camadas diferente do esperado"
        for i, (la, lb) in enumerate(zip(lineares_a, lineares_b)):
            if i == 0:
                _copia_entrada(la, lb, segmentos, dim_antiga)      # entrada realinhada
            else:
                with torch.no_grad():
                    lb.weight.copy_(la.weight)
                    lb.bias.copy_(la.bias)
    with torch.no_grad():
        modelo.policy.action_net.weight.copy_(antigo.policy.action_net.weight)
        modelo.policy.action_net.bias.copy_(antigo.policy.action_net.bias)
        modelo.policy.log_std.copy_(antigo.policy.log_std)
    if planta_real:                                    # o extrator do ATOR tem a MÁSCARA nova (n_ator + 3)
        pass

    # ---- VALIDAÇÃO: em estados sem comando (v_ref = 0) as ações têm de ser IDÊNTICAS
    rng = np.random.default_rng(0)
    deltas = []
    for _ in range(int(args.n_estados)):
        obs_antiga = rng.normal(0.0, 0.5, size=(dim_antiga,)).astype(np.float32)
        obs_nova = np.zeros(dim_nova, dtype=np.float32)
        for a, b in segmentos:
            n = min(dim_antiga - a, dim_nova - b)
            obs_nova[b:b + n] = obs_antiga[a:a + n]
        with torch.no_grad():
            a_antiga, _ = antigo.policy.predict(obs_antiga, deterministic=True)
            a_nova, _ = modelo.policy.predict(obs_nova, deterministic=True)
        deltas.append(float(np.max(np.abs(np.asarray(a_antiga) - np.asarray(a_nova)))))
    max_delta = max(deltas) if deltas else 0.0
    if max_delta > 1e-6:
        raise SystemExit(f"[transferir] FALHA na validação: max|Δação| = {max_delta:.3e} (esperado 0)")
    print(f"[transferir] validação OK: {args.n_estados} estados sem comando dão AÇÕES IDÊNTICAS "
          f"(max|Δ| = {max_delta:.3e})")

    args.para.mkdir(parents=True, exist_ok=True)
    destino = args.para / "final.zip"
    modelo.save(str(destino))
    if planta_real and (args.de.parent / "hardware.json").is_file():
        (args.para / "hardware.json").write_bytes((args.de.parent / "hardware.json").read_bytes())
        print(f"[transferir] hardware.json copiado da origem (as peças são as mesmas)")
    print(f"[transferir] política transferida: {destino} (obs {dim_antiga} → {dim_nova})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
