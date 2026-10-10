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
]


def avaliar(modelo, dados_hw: dict | None, cond: dict, episodios: int, seed: int) -> dict:
    build, _ = build_do_hardware(dados_hw)
    modo = (dados_hw or {}).get("modo_acao", "ctbr")
    vento = None if cond["vento"] <= 0 else (cond["vento"], 0.0, 0.0)
    env = DroneRealEnv(build=build, modo_acao=modo, aleatorizar=cond["dr"], vento=vento,
                       vento_dinamico=cond.get("dinamico"))
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
    args = p.parse_args(argv)
    from stable_baselines3 import PPO
    modelo = PPO.load(str(args.model), device="cpu")
    hw_json = args.model.parent / "hardware.json"
    dados = json.loads(hw_json.read_text(encoding="utf-8")) if hw_json.is_file() else None
    print(f"política {args.model} · peças: {build_do_hardware(dados)[1]} · {args.episodios} episódios por condição")
    print(f"{'condição':44s} {'vivo':>5s} {'|Δz| m':>7s} {'‖xy‖ m':>7s} {'≤5 cm':>6s} {'≤10 cm':>7s} {'|ψ| rad':>8s} {'P W':>6s}")
    t0 = time.perf_counter()
    tabela = []
    for cond in CONDICOES:
        r = avaliar(modelo, dados, cond, args.episodios, args.seed)
        tabela.append(r)

        def f(v, casas=3):
            return "—" if v is None else f"{v:.{casas}f}"
        print(f"{r['condicao']:44s} {100 * r['sobrevivencia']:4.0f}% {f(r['dz_medio']):>7s} {f(r['dxy_medio']):>7s} "
              f"{f(100 * r['frac_5cm'] if r['frac_5cm'] is not None else None, 0):>5s}% "
              f"{f(100 * r['frac_10cm'] if r['frac_10cm'] is not None else None, 0):>6s}% {f(r['yaw_medio']):>8s} "
              f"{f(r['p_media_w'], 1):>6s}")
    destino = args.json or (args.model.parent / "avaliacao_real.json")
    destino.write_text(json.dumps({"modelo": str(args.model), "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                   "tabela": tabela}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"({time.perf_counter() - t0:.0f} s) → {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
