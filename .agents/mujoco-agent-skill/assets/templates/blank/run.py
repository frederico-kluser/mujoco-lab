#!/usr/bin/env python3
"""Experimento em branco — edite `model.xml` e a função `controlador`.

    uv run python experiments/NN_nome/run.py                 # simula, imprime métricas e grava out/video.mp4, out/video.gif, out/telemetria.png
    uv run python experiments/NN_nome/run.py --sem-video     # só números
    uv run python experiments/NN_nome/run.py --view          # janela interativa com o MESMO controlador

Padrão do laboratório: (1) validar o modelo contra física analítica; (2) gravar vídeo/gráficos; (3) devolver exit code 0/1 conforme as checagens.
"""
from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
from lab import mjkit  # noqa: E402  (define MUJOCO_GL=egl antes de importar mujoco)

import argparse  # noqa: E402

import mujoco  # noqa: E402
import numpy as np  # noqa: E402

AQUI = Path(__file__).resolve().parent


def controlador(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    """Chamado ANTES de cada mj_step. Controles: ctrl.set(data, "nome_do_atuador", valor). Forças externas: data.xfrc_applied[corpo, :6]."""
    return


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", default=str(AQUI / "model.xml"))
    ap.add_argument("--duracao", type=float, default=3.0)
    ap.add_argument("--slowmo", type=float, default=1.0)
    ap.add_argument("--saida", default=str(AQUI / "out"))
    ap.add_argument("--sem-video", action="store_true")
    ap.add_argument("--view", action="store_true")
    a = ap.parse_args()

    model, data = mjkit.load(a.modelo)
    mujoco.mj_forward(model, data)
    if a.view:
        mjkit.run_viewer(model, data, controlador, slowmo=a.slowmo)
        return 0

    out = Path(a.saida)
    corpo = model.body("alvo").id
    res = mjkit.record(model, data, controlador, duration=a.duracao, slowmo=a.slowmo, camera="frontal",
                       mp4=None if a.sem_video else out / "video.mp4", gif=None if a.sem_video else out / "video.gif",
                       hud=lambda m, d: [f"t = {d.time:5.2f} s   z = {d.xipos[corpo, 2]:.3f} m"],
                       probes={"z": lambda m, d: d.xipos[corpo, 2], "v": lambda m, d: np.linalg.norm(d.qvel[:3])})
    mjkit.plot(res["log"], ["z", "v"], out / "telemetria.png", "experimento em branco")
    z_fim, v_fim = float(res["log"]["z"][-1]), float(res["log"]["v"][-1])
    checks = [("sem NaN", bool(np.isfinite(res["log"]["z"]).all())), ("repouso (|v| < 1e-3)", v_fim < 1e-3)]  # ← troque por validações analíticas do SEU experimento
    for nome, ok in checks:
        print(f"[{'OK ' if ok else 'FALHA'}] {nome}")
    print(f"z_final = {z_fim:.4f} m · |v| = {v_fim:.1e} m/s · saídas em {out}")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
