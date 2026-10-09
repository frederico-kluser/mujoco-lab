#!/usr/bin/env python3
"""view_model.py — abre QUALQUER modelo MuJoCo numa janela interativa (viewer oficial).

    python3 .agents/mujoco-lab-agent-skill/scripts/view_model.py models/triangulo_invertido.xml
    python3 .agents/mujoco-lab-agent-skill/scripts/view_model.py robo.xml --keyframe home
    python3 .agents/mujoco-lab-agent-skill/scripts/view_model.py robo.xml --passivo --slowmo 0.3 --fechar-apos 5      # launch_passive (teste automático)

Padrão: mujoco.viewer.launch (UI completa; física na thread do viewer): ESPAÇO pausa · BACKSPACE reinicia · setas passo a passo · Ctrl+botão direito empurra ·
duplo-clique seleciona · F1 ajuda · painéis: opções de visualização, controles dos atuadores (sliders!), juntas e sensores.
Equivalente sem script: `python -m mujoco.viewer --mjcf=modelo.xml`. No macOS use `mjpython` só com --passivo. Em sessão Wayland o GLFW usa o backend Wayland nativo
(XWayland só com PYGLFW_LIBRARY_VARIANT=x11).
Avisos benignos no KDE Wayland: `libdecor-gtk.so` e `OpenGL error 0x502 in or before mjr_makeContext`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mjkit  # noqa: E402

import mujoco  # noqa: E402
import mujoco.viewer  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modelo")
    ap.add_argument("--keyframe", help="nome/índice de <key> inicial")
    ap.add_argument("--passivo", action="store_true", help="launch_passive com loop do mjkit (sem UI de física)")
    ap.add_argument("--slowmo", type=float, default=1.0)
    ap.add_argument("--fechar-apos", type=float, default=None, metavar="S", help="só com --passivo")
    a = ap.parse_args()
    if not Path(a.modelo).exists():
        print(f"Erro: modelo não encontrado: {a.modelo} — Solução: passe o caminho de um .xml/.urdf/.mjb", file=sys.stderr)
        return 2
    model, data = mjkit.load(a.modelo, energy_flag=False)
    if a.keyframe is not None:
        mujoco.mj_resetDataKeyframe(model, data, int(a.keyframe) if a.keyframe.isdigit() else model.key(a.keyframe).id)
    if a.passivo:
        mjkit.run_viewer(model, data, None, slowmo=a.slowmo, close_after=a.fechar_apos)
    else:
        mujoco.viewer.launch(model, data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
