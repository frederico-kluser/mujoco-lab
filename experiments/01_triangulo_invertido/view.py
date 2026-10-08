#!/usr/bin/env python3
"""Abre o Experimento 01 numa JANELA interativa (viewer do MuJoCo).

    uv run python experiments/01_triangulo_invertido/view.py                       # UI completa (física na thread do viewer)
    uv run python experiments/01_triangulo_invertido/view.py --modelo models/tetraedro_invertido.xml
    uv run python experiments/01_triangulo_invertido/view.py --passivo --slowmo 0.3   # SEU loop controla a física (launch_passive)
    uv run python experiments/01_triangulo_invertido/view.py --passivo --fechar-apos 3  # teste automático: abre, roda 3 s e fecha

Modo padrão = mujoco.viewer.launch (bloqueante): ESPAÇO pausa/continua · BACKSPACE reinicia (solta o objeto de novo) ·
setas ←/→ avançam/voltam passo a passo (pausado) · duplo-clique seleciona um corpo · Ctrl+botão direito empurra o corpo ·
botão esquerdo gira a câmera · botão direito move · roda do mouse dá zoom · painel esquerdo: opções de renderização
(F1 = ajuda com todas as teclas).

Modo --passivo = mujoco.viewer.launch_passive (não bloqueante): o loop abaixo chama mj_step e viewer.sync().
Teclas extras: R reinicia · P pausa. (No macOS, launch_passive só funciona com `mjpython view.py --passivo`.)
Em sessão Wayland o GLFW usa o backend Wayland nativo (XWayland só com PYGLFW_LIBRARY_VARIANT=x11).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import mujoco
import mujoco.viewer

RAIZ = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", default=str(RAIZ / "models" / "triangulo_invertido.xml"))
    ap.add_argument("--passivo", action="store_true", help="usa launch_passive com loop próprio (em vez de launch)")
    ap.add_argument("--slowmo", type=float, default=1.0, help="só no modo --passivo: 0.5 = metade da velocidade real")
    ap.add_argument("--fechar-apos", type=float, default=None, metavar="S", help="só no modo --passivo: fecha sozinho após S segundos")
    a = ap.parse_args()

    caminho = Path(a.modelo)
    if not caminho.exists():
        sys.exit(f"Erro: modelo não encontrado: {caminho} — Solução: passe --modelo com um XML existente.")
    model = mujoco.MjModel.from_xml_path(str(caminho))
    data = mujoco.MjData(model)

    if not a.passivo:
        print(f"viewer (launch) · {caminho.name} · feche a janela para sair")
        mujoco.viewer.launch(model, data)
        return 0

    estado = {"pausado": False}

    def tecla(keycode: int) -> None:  # chamado pelo viewer para teclas que ele não trata; códigos GLFW = ASCII maiúsculo
        if chr(keycode) == "R":
            mujoco.mj_resetData(model, data)
            mujoco.mj_forward(model, data)
        elif chr(keycode) == "P":
            estado["pausado"] = not estado["pausado"]

    print(f"viewer (launch_passive) · {caminho.name} · slowmo {a.slowmo:g}× · R reinicia · P pausa · feche a janela para sair")
    with mujoco.viewer.launch_passive(model, data, key_callback=tecla) as viewer:
        inicio = time.perf_counter()
        while viewer.is_running():
            if a.fechar_apos is not None and time.perf_counter() - inicio > a.fechar_apos:
                break
            t0 = time.perf_counter()
            if not estado["pausado"]:
                with viewer.lock():  # a thread da UI lê `data`; o lock evita ler um passo pela metade
                    mujoco.mj_step(model, data)
            viewer.sync()  # copia o estado para a janela
            folga = model.opt.timestep / a.slowmo - (time.perf_counter() - t0)
            if folga > 0:
                time.sleep(folga)  # mantém o relógio da simulação ≈ relógio real
    print(f"fim: t_sim = {data.time:.2f} s · z_cm = {data.xipos[1, 2]:.4f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
