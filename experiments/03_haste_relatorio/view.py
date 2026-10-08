#!/usr/bin/env python3
"""Abre o experimento 03 numa janela interativa (viewer passivo). Só a pedido do usuário: a janela aparece na tela dele.

    uv run python experiments/03_haste_relatorio/view.py            # haste do relatório (corrigida)
Em sessão Wayland o GLFW usa o backend Wayland nativo (XWayland só com PYGLFW_LIBRARY_VARIANT=x11). No macOS use `mjpython`.
"""
import subprocess
import sys
from pathlib import Path

sys.exit(subprocess.call([sys.executable, str(Path(__file__).with_name("run.py")), "--view", *sys.argv[1:]]))
