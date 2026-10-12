#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/train_seguimento.py — treino da IA nº 2 (seguimento visual).

PPO (SB3), MLP 64-64 (ator e crítico), 2 seeds × 1–2 M passos (o desenho do dono), currículo simples:
**ponto parado → ponto móvel lento (0,3 m/s) → 0,8 m/s** (o gate avança de estágio quando o tracker
domina o atual: ponto ≥95 % do tempo no FOV e centragem média < 30 px numa avaliação).

Estilo do `train.py` (o dono mandou usá-lo como referência): logs por avaliação em JSONL, `--sem-painel`,
`out/real_1950_seguimento_s<seed>/` com `final.zip` + `hardware.json` + `treino_log.jsonl`.

USO:  python train_seguimento.py --piloto out/real_1950_voo_final/final.zip --semente 0 --passos 1500000
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
_RAIZ = _AQUI.parent.parent
for _p in (str(_RAIZ), str(_AQUI)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from env_seguimento import EnvSeguimento

ESTAGIOS = [("parado", 0.0), ("aleatorio", 0.3), ("aleatorio", 0.8)]   # currículo do dono
GATE_FOV = 0.95           # ≥95 % do tempo com o ponto no FOV
GATE_CENTRO_PX = (60.0, 80.0, 550.0)   # centragem máxima em px para AVANÇAR de cada estágio
                           # (parado → 0,3 → 0,8 m/s). PISOS MEDIDOS (2026-10-12) — a cascata não
                           # faz melhor que a interior permite (erro composto):
                           #   parado (hover puro, tracker nenhum)        = 37–40 px
                           #   alvo 0,3 m/s, feedforward PERFEITO         = 47,5 px (p90 73)
                           #   alvo 0,8 m/s, feedforward PERFEITO         = 452 px (p90 848)
                           # Os gates são piso + margem: 60 (parado), 80 (0,3) e 550 (0,8 — o
                           # último estágio não avança, o valor é só documental). Aos 0,8 m/s a
                           # tarefa real é NÃO PERDER o alvo de vista (gate de FOV 0,95), não
                           # centrá-lo: nenhum tracker, nem omnisciente, centra um alvo que muda
                           # de direção a essa velocidade.

AVALIACAO_CADA = 25_000   # passos entre avaliações do currículo

def avaliar_rapido(modelo, piloto_zip: Path, traj: str, vel: float, episodios: int = 4) -> dict:
    env = EnvSeguimento(piloto_zip, episodio_s=6.0, trajetoria=traj, vel_ponto=vel)
    centros, fofo, passos = [], 0, 0
    for k in range(episodios):
        obs, _info = env.reset(seed=1234 + k)
        while True:
            acao, _ = modelo.predict(obs, deterministic=True)
            obs, _r, term, trunc, info = env.step(acao)
            passos += 1
            fofo += int(info["visivel"])
            if info["e_centro_px"] is not None:
                centros.append(info["e_centro_px"])
            if term or trunc:
                break
    env.fechar()
    return {"fov": fofo / max(passos, 1),
            "centro_px": float(np.mean(centros)) if centros else 999.0}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Treino do tracker visual (IA nº 2) sobre a IA-voo congelada.")
    p.add_argument("--piloto", type=Path, required=True, help="IA-voo CONGELADA (final.zip)")
    p.add_argument("--semente", type=int, default=0)
    p.add_argument("--passos", type=int, default=1_500_000)
    p.add_argument("--out-dir", type=Path, default=None)
    p.add_argument("--n-envs", type=int, default=4)
    p.add_argument("--aprendizagem", type=float, default=3e-4)
    args = p.parse_args(argv)

    from stable_baselines3 import PPO
    from stable_baselines3.common.utils import set_random_seed
    from stable_baselines3.common.vec_env import SubprocVecEnv
    set_random_seed(args.semente)
    out_dir = args.out_dir or (_AQUI / "out" / f"real_1950_seguimento_s{args.semente}")
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "treino_log.jsonl"
    log.write_text("", encoding="utf-8")

    estagio = 0
    traj, vel = ESTAGIOS[0]

    def fabrica(rango: int):
        def _faz():
            return EnvSeguimento(args.piloto, trajetoria=traj, vel_ponto=vel)
        return _faz

    envs = SubprocVecEnv([fabrica(args.semente + i) for i in range(args.n_envs)], start_method="spawn")
    modelo = PPO("MlpPolicy", envs, policy_kwargs={"net_arch": {"pi": [64, 64], "vf": [64, 64]}},
                 learning_rate=args.aprendizagem, n_steps=256, batch_size=256, n_epochs=10,
                 gamma=0.99, gae_lambda=0.95, verbose=0, seed=args.semente)
    t0 = time.perf_counter()
    feitos = 0
    print(f"[seguimento] semente {args.semente} · {args.passos:,} passos · piloto {args.piloto.name} "
          f"· currículo {[f'{n}@{v}' for n, v in ESTAGIOS]}", flush=True)
    while feitos < args.passos:
        bloco = min(AVALIACAO_CADA, args.passos - feitos)
        modelo.learn(total_timesteps=bloco, reset_num_timesteps=False, progress_bar=False)
        feitos += bloco
        res = avaliar_rapido(modelo, args.piloto, traj, vel)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": feitos, "estagio": estagio, "trajetoria": traj, "vel": vel,
                                "fov": round(res["fov"], 4), "centro_px": round(res["centro_px"], 2),
                                "fps": round(feitos / max(time.perf_counter() - t0, 1), 1),
                                "semente": args.semente}) + "\n")
        print(f"[eval] t={feitos:,} estágio {estagio + 1}/{len(ESTAGIOS)} ({traj} @{vel:g} m/s) "
              f"· FOV {res['fov'] * 100:.0f} % · centragem {res['centro_px']:.1f} px", flush=True)
        # gate do currículo (o desenho: ponto parado → lento → 0,8 m/s)
        if (estagio + 1 < len(ESTAGIOS) and res["fov"] >= GATE_FOV
                and res["centro_px"] <= GATE_CENTRO_PX[estagio]):
            estagio += 1
            traj, vel = ESTAGIOS[estagio]
            envs.env_method("definir_trajetoria_ponto", traj, vel=vel, raio=1.5)
            print(f"[currículo] AVANÇA para {traj} @{vel:g} m/s "
                  f"(FOV {res['fov'] * 100:.0f} % ≥ {GATE_FOV * 100:.0f} % · centragem "
                  f"{res['centro_px']:.1f} px ≤ {GATE_CENTRO_PX[estagio]:g})", flush=True)
    modelo.save(str(out_dir / "final.zip"))
    hw = args.piloto.parent / "hardware.json"
    if hw.is_file():
        shutil.copy(hw, out_dir / "hardware.json")
    envs.close()
    print(f"[fim] {feitos:,} passos em {time.perf_counter() - t0:.0f} s · {out_dir / 'final.zip'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
