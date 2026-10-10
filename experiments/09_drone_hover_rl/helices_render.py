#!/usr/bin/env python
"""Prova VISUAL da animação das hélices: dois renders offscreen (EGL) da janela 3D com o drone a voar.

Não é um experimento nem um controlador: é só a câmara. Corre o MESMO modelo/camada que o `sim_view.py`
mostra (`cf.carregar(helices=True)`, 4 geoms visuais `helice_1..4`) com um wrench de voo constante, anima as
hélices com `cf.Helices` (a mesma chamada por frame do runner) e grava duas imagens em dois momentos — as
hélices aparecem em poses diferentes porque cada rotor gira à sua velocidade (|ω| ∝ √t_i) e o ângulo
acumulado muda de um momento para o outro. Imprime os ângulos para a diferença ser verificável por número,
não só a olho.

    MUJOCO_GL=egl uv run --group hover-rl python experiments/09_drone_hover_rl/helices_render.py
    → out/helices_1.png, out/helices_2.png  (out/ é ignorado pelo git)

`--passos 30 37` escolhe os dois momentos (passos de decisão de 0,02 s = 10 passos de física);
`--sem-helices` grava as mesmas imagens SEM a adaptação (modelo upstream: as 4 hélices ficam fundidas numa
malha só e não giram) — é o par de controlo da prova visual.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

# Ordem intencional (I001 desligado): o `mjkit` fixa MUJOCO_GL=egl ANTES de `import mujoco`.
from lab import mjkit  # noqa: F401, I001
from lab import crazyflie as cf

import mujoco
import numpy as np
import PIL.Image

OUT = _AQUI / "out"
RESOLUCAO = (640, 480)                 # (largura, altura) — teto do framebuffer offscreen de `scene.xml`
EMPUXOS = (0.070, 0.062435, 0.062435, 0.070)   # N por rotor: Σ = 0,26487 N = peso e roll/pitch = 0 (guinada
                                               # pura) — o drone paira nivelado e pirueta devagar, com as
                                               # diagonais (hélices 1-4 e 2-3) a rodar em sentidos opostos
DECIMACAO = 10                         # passos de física (0,002 s) por passo de animação (0,02 s) — como no env
ALTURA = 0.45                          # m: altura inicial do CM (o keyframe do lab é 0,1 m — muito perto do chão)


def _camara(model: mujoco.MjModel) -> mujoco.MjvCamera:
    camara = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, camara)
    camara.lookat[:] = [0.0, 0.0, ALTURA - 0.02]
    camara.distance = 0.30
    camara.azimuth = 130.0
    camara.elevation = -42.0
    return camara


def corre(passos: list[int], com_helices: bool, destino: Path) -> list[Path]:
    """Corre a física até cada momento pedido e grava um PNG por momento. Devolve os caminhos gravados."""
    model, data = cf.carregar(helices=com_helices)
    helices = cf.Helices(model)
    estado = [0.0, 0.0, ALTURA, 1.0, 0.0, 0.0, 0.0]
    data.qpos[:] = estado                                # arranque explícito no ar (nada de teleporte a meio)
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    camara = _camara(model)
    renderer = mujoco.Renderer(model, RESOLUCAO[1], RESOLUCAO[0])   # (altura, largura)
    destino.mkdir(parents=True, exist_ok=True)
    imagens = []
    for alvo in sorted(passos):
        while round(data.time / (model.opt.timestep * DECIMACAO)) < alvo:
            cf.comandar_rotores(model, data, EMPUXOS)     # o MESMO wrench em cada passo (roteiro aberto)
            for _ in range(DECIMACAO):
                mujoco.mj_step(model, data)
            helices.atualizar(model, data, model.opt.timestep * DECIMACAO)
        renderer.update_scene(data, camara)
        caminho = destino / f"helices_{len(imagens) + 1}{'' if com_helices else '_sem'}.png"
        PIL.Image.fromarray(renderer.render()).save(caminho)
        imagens.append(caminho)
        print(f"  passo {alvo:3d} (t = {data.time:.2f} s): z = {data.sensor('posicao').data[2]:.4f} m · "
              f"ângulos das hélices = {np.round(helices.angulos, 3)} rad · ω = {np.round(helices.velocidades, 3)} "
              f"rad/s · {caminho}")
    del renderer
    return imagens


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--passos", type=int, nargs=2, default=(30, 37), metavar=("P1", "P2"),
                   help="os dois momentos (passos de decisão de 0,02 s; padrão: 30 e 37)")
    p.add_argument("--sem-helices", action="store_true",
                   help="grava o par de controlo SEM a adaptação (modelo upstream, hélices fundidas e paradas)")
    args = p.parse_args(argv)
    if args.passos[0] == args.passos[1] or min(args.passos) < 1:
        raise SystemExit("--passos: dois momentos distintos e ≥ 1")
    print(f"wrench de voo: empuxos por rotor = {EMPUXOS} N (Σ = {sum(EMPUXOS):.5f} N · peso = {cf.PESO:.5f} N) · "
          f"escala VISUAL = {cf.ESCALA_VISUAL:.2f} rad/s/√N ({cf.REVOLUCOES_VISUAIS:g} rev/s no máximo por rotor)")
    corre(list(args.passos), not args.sem_helices, OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
