#!/usr/bin/env python3
"""view.py — janela de visualização com TECLAS de ação (molde para o teu objeto).

Teclas (foco na janela):
  W/S  empuxo +X/−X (pulso)   A/D  empuxo +Y/−Y (pulso)   Q/E  empuxo +Z/−Z (pulso)
  G    detonar a SEPARAÇÃO (carga explosiva: solta o parafuso e empurra tampa/objeto em sentidos opostos)
  R    reiniciar (reset EXPLÍCITO do simulador) · ESPAÇO pausar/retomar · ESC sair

NOTA: o `key_callback` do viewer só dispara na PREMÇÃO (não há keyup) — cada premção é um PULSO de
0,25 s. Para o controlo "segurar-tecla" (estado contínuo, o que o cockpit usa) o padrão é outro:
site keydown/keyup → `POST /api/*` → ficheiro de controlo → runner → `definir_*()` — ver
`references/controlos-teclado.md`.
"""
from __future__ import annotations

import time

import mujoco

from objeto_propulsao import Carga, carregar, definir_empuxo

PULSO_S = 0.25                 # duração de cada premção de tecla (s)
ESC, ESPACO = 256, 32          # códigos GLFW que o callback entrega (letras = ASCII maiúsculo)

# tecla (código) → (função, argumento) — empuxo em NEWTON, torque em N·m
ACOES = {
    ord("W"): ("empuxo", "x", +20.0), ord("S"): ("empuxo", "x", -20.0),
    ord("A"): ("empuxo", "y", +20.0), ord("D"): ("empuxo", "y", -20.0),
    ord("Q"): ("empuxo", "z", +30.0), ord("E"): ("empuxo", "z", -30.0),
}


def main() -> int:
    model, data, ctrl = carregar()
    carga = Carga(model)
    mujoco.mj_forward(model, data)
    pulsos: dict[str, tuple[float, int]] = {}     # canal -> (valor, passos_restantes)
    estado = {"pausado": False}

    def tecla(keycode: int) -> None:
        if keycode == ESC:
            return
        if keycode == ESPACO:
            estado["pausado"] = not estado["pausado"]
            return
        if keycode == ord("R"):
            mujoco.mj_resetData(model, data)      # reset EXPLÍCITO (única forma de voltar ao início)
            carga.limpar(data)
            mujoco.mj_forward(model, data)
            print("reiniciado")
            return
        if keycode == ord("G"):
            carga.detonar_separacao(data, (1.0, 0.0, 0.0))
            print("CARGA DETONADA — parafuso solto, tampa +J, objeto −J")
            return
        acao = ACOES.get(keycode)
        if acao is not None:
            _, eixo, valor = acao
            passos = int(round(PULSO_S / model.opt.timestep))
            pulsos[eixo] = (valor, passos)
            print(f"empuxo_{eixo}: {valor:+.1f} N por {PULSO_S:.2f} s")

    with mujoco.viewer.launch_passive(model, data, key_callback=tecla, show_left_ui=False,
                                      show_right_ui=False) as v:
        print(__doc__)
        while v.is_running():
            if not estado["pausado"]:
                # pulsos de empuxo (o ctrl PERSISTE entre passos: zera-se o que termina)
                for eixo in ("x", "y", "z"):
                    valor, restam = pulsos.get(eixo, (0.0, 0))
                    definir_empuxo(data, ctrl, eixo, valor if restam > 0 else 0.0)
                    if restam > 0:
                        pulsos[eixo] = (valor, restam - 1)
                carga.passo(data)                 # ANTES de cada mj_step (forças da carga)
                mujoco.mj_step(model, data)
            v.sync()
            time.sleep(model.opt.timestep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
