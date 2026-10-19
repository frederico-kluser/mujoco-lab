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

  · braços articulados (`--build articulado_…`): +8 juntas no fim do ator e do crítico, também a zero — a política
           rígida que já voa passa a ver os encoders e o fine-tune ensina-a a usá-los.

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


def _mapa_entradas(planta: str, dim_antiga: int, dim_nova: int, n_ator_antigo: int = 0,
                   n_ator_novo: int = 0) -> list[tuple[int, int, int]]:
    """Segmentos [(antigo_ini, novo_ini, n), …] do alinhamento da entrada: cada um copia as colunas [a : a+n] → [b : b+n];
    o resto (os canais NOVOS) fica a zero.

      · cf2:  [0:16] → [0:16] (os 3 canais de `v_ref` em [16:19] a zero);
      · real: a obs é [ATOR | CRÍTICO] — o bloco do ator antigo vai para o INÍCIO do ator novo e o do crítico antigo para
        o INÍCIO do crítico novo; o que o ator/crítico novo tem a mais (o `v_ref` do modo comando, 3; as 8 juntas dos
        braços articulados) fica a zero. Ex.: rígido 42 → comando 48: (0,0,21), (21,24,21); rígido de comando 48 →
        articulado de comando 64: (0,0,24), (24,32,24).
    """
    if planta == "cf2":
        return [(0, 0, dim_antiga)]
    n_crit_antigo, n_crit_novo = dim_antiga - n_ator_antigo, dim_nova - n_ator_novo
    if n_ator_antigo > n_ator_novo or n_crit_antigo > n_crit_novo:
        raise SystemExit(f"[transferir] a observação nova ({n_ator_novo}+{n_crit_novo}) é menor do que a antiga "
                         f"({n_ator_antigo}+{n_crit_antigo}): só se acrescentam canais")
    return [(0, 0, n_ator_antigo), (n_ator_antigo, n_ator_novo, n_crit_antigo)]


def _copia_entrada(camada_antiga: torch.nn.Linear, camada_nova: torch.nn.Linear,
                   segmentos: list[tuple[int, int, int]]) -> None:
    """Copia o peso/bias de uma `Linear` alinhando as ENTRADAS pelos segmentos (saídas idênticas). Os segmentos têm o
    comprimento EXATO (antes desta versão, o 1.º segmento copiava a obs inteira e as colunas do crítico iam parar às
    entradas `v_ref` do ator — invisível na validação, que só usa `v_ref = 0`)."""
    with torch.no_grad():
        camada_nova.weight.zero_()
        camada_nova.bias.copy_(camada_antiga.bias)
        for a, b, n in segmentos:
            camada_nova.weight[:, b:b + n].copy_(camada_antiga.weight[:, a:a + n])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Transfere uma política PPO para a observação do modo comando (contrato r11), "
                    "com as entradas novas a zero e validação de igualdade de ações.")
    p.add_argument("--de", type=Path, required=True, metavar="ZIP", help="política de origem (PPO .zip)")
    p.add_argument("--para", type=Path, required=True, metavar="DIR", help="pasta de saída (final.zip)")
    p.add_argument("--planta", choices=("cf2", "real"), default="cf2",
                   help="planta da política de origem (define o mapa de entradas)")
    p.add_argument("--build", type=str, default=None,
                   help="planta real: build do env NOVO (por omissão o da política de origem). Um build com braços "
                        "articulados acrescenta as 8 juntas à observação (entradas novas a zero)")
    p.add_argument("--sem-comando", action="store_true",
                   help="planta real: o env novo SEM o modo comando (só acrescentar as juntas a uma política rígida)")
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
        if args.build is not None:
            build, motivo = args.build, f"build '{args.build}' pedido (--build)"
        print(f"[transferir] peças do env novo: {motivo}")
        ambiente = DroneRealEnv(build=build, modo_acao=dados.get("modo_acao", args.modo_acao),
                                aleatorizar=False, comando=not args.sem_comando)
        n_ator_antigo, n_ator_novo = int(antigo.policy._n_ator), int(ambiente.obs_ator_dim)
    else:
        from env import HoverEnv
        ambiente = HoverEnv(comando=True)
        n_ator_antigo = n_ator_novo = 0
    dim_nova = int(ambiente.observation_space.shape[0])
    if not planta_real and (dim_antiga, dim_nova) != (16, 19):
        raise SystemExit(f"[transferir] cf2: o mapa espera 16 → 19 dims (recebido {dim_antiga} → {dim_nova})")
    segmentos = _mapa_entradas(args.planta, dim_antiga, dim_nova, n_ator_antigo, n_ator_novo)
    print(f"[transferir] entradas {dim_antiga} → {dim_nova} · segmentos (antigo, novo, n) = {segmentos}")

    novos = {}
    if planta_real:
        from politica import PoliticaAssimetrica
        novos = {"n_ator": n_ator_novo}
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
                _copia_entrada(la, lb, segmentos)                  # entrada realinhada
            else:
                with torch.no_grad():
                    lb.weight.copy_(la.weight)
                    lb.bias.copy_(la.bias)
    with torch.no_grad():
        modelo.policy.action_net.weight.copy_(antigo.policy.action_net.weight)
        modelo.policy.action_net.bias.copy_(antigo.policy.action_net.bias)
        modelo.policy.log_std.copy_(antigo.policy.log_std)

    # ---- VALIDAÇÃO: em estados sem comando (v_ref = 0) as ações têm de ser IDÊNTICAS
    rng = np.random.default_rng(0)
    deltas = []
    for _ in range(int(args.n_estados)):
        obs_antiga = rng.normal(0.0, 0.5, size=(dim_antiga,)).astype(np.float32)
        obs_nova = np.zeros(dim_nova, dtype=np.float32)
        for a, b, n in segmentos:
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
