#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/avaliar_real.py — avalia uma política da PLANTA REAL em várias condições.

Episódios determinísticos (ação = média da política) no `DroneRealEnv` com as peças do `hardware.json` do
modelo, numa grelha de condições: estado da bateria (SoC inicial), vento base e domain randomization. Mede por
episódio: sobrevivência (sem terminar), |z − alvo| e ‖xy‖ médios na 2.ª metade (já depois de descolar), fração de
passos com xy E z dentro de 5/10 cm, rumo, potência média e a autonomia restante que o site mostraria.

    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_real.py --model out/real_<nome>/best_model.zip
    ... --episodios 5 --json out/real_<nome>/avaliacao.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]
from lab import mjkit  # noqa: F401, I001

import numpy as np

from env_real import DroneRealEnv, build_do_hardware

CONDICOES = [
    {"nome": "nominal · bateria cheia · ar parado", "soc0": 1.0, "vento": 0.0, "dr": False},
    {"nome": "nominal · SoC 50 %", "soc0": 0.5, "vento": 0.0, "dr": False},
    {"nome": "nominal · SoC 25 % (tensão baixa)", "soc0": 0.25, "vento": 0.0, "dr": False},
    {"nome": "vento 2 m/s", "soc0": 1.0, "vento": 2.0, "dr": False},
    {"nome": "vento 3 m/s", "soc0": 1.0, "vento": 3.0, "dr": False},
    {"nome": "vento 3 m/s + rajadas (até +3 m/s)", "soc0": 1.0, "vento": 3.0, "dr": False,
     "dinamico": {"modo": "rajadas", "p": 0.02, "duracao": 10, "u_max": 3.0}},
    {"nome": "frente de vento 3 m/s aos 5 s", "soc0": 1.0, "vento": 0.0, "dr": False,
     "dinamico": {"modo": "frente", "t_s": 5.0, "u_max": 3.0}},
    {"nome": "DR (peças/bateria/sensores sorteados)", "soc0": None, "vento": 0.0, "dr": True},
    {"nome": "DR + vento 2 m/s", "soc0": None, "vento": 2.0, "dr": True},
    # ---- OOD (FORA DO CURRÍCULO DE TREINO): a pesquisa de suficiência do treino
    # (pesquisas/relatorio-treino-rl-suficiencia.md) exige avaliação fora da distribuição — o currículo
    # vai a 3 m/s e as políticas só viram 0–3 m/s; 4–5 m/s, SoC residual e DR+vento forte são o teste de
    # generalização. A massa ±15 % cobre-se pelo DR (`aleatorizar=True` sorteia peças/massas); os
    # comandos extremos cobrem-se no `teste_controle_voo.py` (WASDQE aos limites).
    {"nome": "OOD · vento 4 m/s (fora do currículo)", "soc0": 1.0, "vento": 4.0, "dr": False, "ood": True},
    {"nome": "OOD · vento 5 m/s (teto do contrato)", "soc0": 1.0, "vento": 5.0, "dr": False, "ood": True},
    {"nome": "OOD · vento 5 m/s + rajadas (até +3 m/s)", "soc0": 1.0, "vento": 5.0, "dr": False, "ood": True,
     "dinamico": {"modo": "rajadas", "p": 0.02, "duracao": 10, "u_max": 3.0}},
    {"nome": "OOD · SoC 10 % (residual) + vento 3 m/s", "soc0": 0.10, "vento": 3.0, "dr": False, "ood": True},
    {"nome": "OOD · DR + vento 4 m/s (massa ±15 % via DR)", "soc0": None, "vento": 4.0, "dr": True, "ood": True},
]


def modo_comando(modelo) -> bool:
    """A política é de CONTROLE DE VOO (`--comandos`, obs 48)? Deteção pela observação, nunca por flag.

    Sem isto, avaliar uma política `--comandos` num env clássico (obs 21/24) rebenta no `predict` — e o
    retreino de 2026-10-11 é TODO em modo comando. Com `comando=True` o env treina/avalia com perfis de
    comando aleatórios (v_ref em movimento) e as métricas passam a ser de SEGUIMENTO da referência.
    """
    from env_real import OBS_ATOR_DIM, OBS_ATOR_DIM_COMANDO
    # detector PROVADO (o mesmo do `sim_view.ambiente_para`): `_n_ator` do ator é a observação que o
    # ATOR vê (21 clássico / 24 comando) — a obs do env leva ainda o crítico assimétrico (42/48)
    n_ator = getattr(getattr(modelo, "policy", None), "_n_ator", None)
    if n_ator is not None:
        return int(n_ator) == OBS_ATOR_DIM_COMANDO
    obs = int(modelo.observation_space.shape[0])
    return obs in (OBS_ATOR_DIM_COMANDO, 2 * OBS_ATOR_DIM_COMANDO) and obs != 2 * OBS_ATOR_DIM


def avaliar(modelo, dados_hw: dict | None, cond: dict, episodios: int, seed: int) -> dict:
    build, _ = build_do_hardware(dados_hw)
    modo = (dados_hw or {}).get("modo_acao", "ctbr")
    vento = None if cond["vento"] <= 0 else (cond["vento"], 0.0, 0.0)
    comando = modo_comando(modelo)
    env = DroneRealEnv(build=build, modo_acao=modo, aleatorizar=cond["dr"], vento=vento,
                       vento_dinamico=cond.get("dinamico"),
                       comando=comando, comandos_aleatorios=comando)
    res = []
    for k in range(episodios):
        opts = {} if cond["soc0"] is None else {"soc0": cond["soc0"]}
        if vento is not None:
            ang = 360.0 * k / max(episodios, 1)                       # direções diferentes por episódio
            env.definir_vento(cond["vento"], ang)
        obs, info = env.reset(seed=seed + k, options=opts)
        zs, xys, yaws, pots, dentro5, dentro10 = [], [], [], [], 0, 0
        terminou, n = False, 0
        for n in range(1, env.max_passos + 1):
            acao, _ = modelo.predict(obs, deterministic=True)
            obs, _r, term, trunc, info = env.step(acao)
            if n > env.max_passos // 2:                               # 2.ª metade: já descolou
                dz = abs(info["z"] - env.alvo_z)
                zs.append(dz)
                xys.append(info["dist_xy"])
                yaws.append(abs(info["yaw_err"]))
                pots.append(info["p_total"])
                dentro5 += int(info["dist_xy"] < 0.05 and dz < 0.05)
                dentro10 += int(info["dist_xy"] < 0.10 and dz < 0.10)
            if term:
                terminou = True
                break
            if trunc:
                break
        m = max(len(zs), 1)
        res.append({"sobreviveu": not terminou, "passos": n, "dz_medio": float(np.mean(zs)) if zs else None,
                    "dxy_medio": float(np.mean(xys)) if xys else None, "yaw_medio": float(np.mean(yaws)) if yaws else None,
                    "frac_5cm": dentro5 / m, "frac_10cm": dentro10 / m,
                    "p_media_w": float(np.mean(pots)) if pots else None, "soc_final": float(info["soc"]),
                    "autonomia_min": env.planta.bat.autonomia_restante_min(float(np.mean(pots)) / max(env.planta.v_bus, 1e-3))
                    if pots else None})
    def media(chave):
        v = [r[chave] for r in res if r[chave] is not None]
        return float(np.mean(v)) if v else None
    return {"condicao": cond["nome"], "episodios": episodios,
            "sobrevivencia": float(np.mean([r["sobreviveu"] for r in res])),
            "dz_medio": media("dz_medio"), "dxy_medio": media("dxy_medio"), "yaw_medio": media("yaw_medio"),
            "frac_5cm": media("frac_5cm"), "frac_10cm": media("frac_10cm"), "p_media_w": media("p_media_w"),
            "autonomia_min": media("autonomia_min"), "episodios_detalhe": res}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Avalia uma política da planta real numa grelha de condições.")
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--episodios", type=int, default=5)
    p.add_argument("--seed", type=int, default=5000)
    p.add_argument("--json", type=Path, default=None, help="grava o resultado (por omissão ao lado do modelo)")
    p.add_argument("--apenas-ood", action="store_true",
                   help="avalia SÓ as condições OOD (fora do currículo de treino) — a exigência da "
                        "pesquisa de suficiência do treino")
    args = p.parse_args(argv)
    from stable_baselines3 import PPO
    modelo = PPO.load(str(args.model), device="cpu")
    hw_json = args.model.parent / "hardware.json"
    dados = json.loads(hw_json.read_text(encoding="utf-8")) if hw_json.is_file() else None
    print(f"política {args.model} · peças: {build_do_hardware(dados)[1]} · {args.episodios} episódios por condição"
          + (" · MODO COMANDO (seguimento de referência em movimento)" if modo_comando(modelo) else ""))
    print(f"{'condição':44s} {'vivo':>5s} {'|Δz| m':>7s} {'‖xy‖ m':>7s} {'≤5 cm':>6s} {'≤10 cm':>7s} {'|ψ| rad':>8s} {'P W':>6s}")
    t0 = time.perf_counter()
    tabela = []
    condicoes = [c for c in CONDICOES if (bool(c.get("ood")) == args.apenas_ood
                                         if args.apenas_ood else True)]
    for cond in condicoes:
        r = avaliar(modelo, dados, cond, args.episodios, args.seed)
        tabela.append(r)

        def f(v, casas=3):
            return "—" if v is None else f"{v:.{casas}f}"
        print(f"{r['condicao']:44s} {100 * r['sobrevivencia']:4.0f}% {f(r['dz_medio']):>7s} {f(r['dxy_medio']):>7s} "
              f"{f(100 * r['frac_5cm'] if r['frac_5cm'] is not None else None, 0):>5s}% "
              f"{f(100 * r['frac_10cm'] if r['frac_10cm'] is not None else None, 0):>6s}% {f(r['yaw_medio']):>8s} "
              f"{f(r['p_media_w'], 1):>6s}")
    # resumo por grupo (distribuição de treino vs OOD) — o veredito de generalização
    for etiqueta, filtro in (("NO DISTRIBUIÇÃO", lambda c: not c.get("ood")), ("OOD", lambda c: c.get("ood"))):
        grupo = [r for r, c in zip(tabela, condicoes) if filtro(c)]
        if grupo:
            vivo = 100.0 * sum(r["sobrevivencia"] for r in grupo) / len(grupo)
            dxy = [r["dxy_medio"] for r in grupo if r["dxy_medio"] is not None]
            print(f"resumo {etiqueta:16s}: sobrevivência {vivo:.0f}% · ‖xy‖ médio "
                  f"{(sum(dxy) / len(dxy) if dxy else float('nan')):.3f} m · {len(grupo)} condições")
    destino = args.json or (args.model.parent / "avaliacao_real.json")
    destino.write_text(json.dumps({"modelo": str(args.model), "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                   "tabela": tabela}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"({time.perf_counter() - t0:.0f} s) → {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
