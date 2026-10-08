#!/usr/bin/env python3
"""Crazyflie 2 (Bitcraze) — janela interativa para mexer nos MOTORES e CONTROLES, sem estabilização.

Modelo pronto do mujoco_menagerie + camada de funções `lab/crazyflie.py`. Não há PID nem atitude-lock:
o drone segue os seus comandos abertos (e deriva — é assim mesmo).

SIMULADOR SEMPRE FÍSICO: tudo passa por `mj_step` (gravidade, arrasto, contactos, atuadores). O arranque
é com **motores desligados** — o drone assenta no chão pela física; nada paira por magia. Para descolar:
`T` (1,2× peso) e, à altura desejada, `H` (pairar) — ou `↑` para ir ajustando o empuxo.

    uv run python experiments/08_crazyflie_motores/view.py
    uv run python experiments/08_crazyflie_motores/view.py --modo hover   # arranque já a pairar

Teclado (foco na janela):
    1..7  modos (desligado/hover/empuxo/momento_x/momento_y/momento_z/rotores)
    ↑ / ↓  empuxo ±0,01 N          ← / →  momento_x ±0,5 µN·m       PGUP / PGDN  momento_y ±0,5 µN·m
    , / .  momento_z ±0,5 µN·m     T  descolar (1,2× peso)            H  hover (empuxo = peso)
    D  desligar (motores a zero)   S  ler sensores                    L  listar comandos
    P  pausa                       R  reiniciar (reset do simulador)

Terminal (REPL):
    modo <nome> · empuxo 0.30 · momento x 1e-6 · rotores 0.07 0.07 0.07 0.07 ·
    sensores · list · hover · desligar · quit
"""
from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
from lab import mjkit  # noqa: E402  (define MUJOCO_GL=egl antes de importar mujoco)
from lab import crazyflie as cf  # noqa: E402

import argparse  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

import mujoco  # noqa: E402
import mujoco.viewer  # noqa: E402  (import aqui, não dentro de main(): senão `mujoco` vira local)
import numpy as np  # noqa: E402

AQUI = Path(__file__).resolve().parent
TAB, ESQ, DIR, CIMA, BAIXO, PAG_CIMA, PAG_BAIXO = 258, 263, 262, 265, 264, 266, 267
DEMP = 0.01       # N por tecla ↑/↓
DMOM = 5e-7       # N·m por tecla de momento


class Painel:
    """Comandos abertos (empuxo + momentos) + modo ativo. Sem realimentação — quem controla é você."""

    def __init__(self, model, data):
        self.m, self.d = model, data
        self.modo = "desligado"
        self.t0 = data.time
        self.empuxo = 0.0
        self.momentos = [0.0, 0.0, 0.0]
        self.pausa = False
        self.sair = False

    def aplicar(self, model, data) -> None:
        if self.modo != "manual":
            cf.MODOS[self.modo](model, data, data.time - self.t0)
            m = cf.ler_motores(model, data)
            self.empuxo, self.momentos = m["empuxo"], list(m["momentos"])
        else:
            cf.definir_wrench(model, data, self.empuxo, tuple(self.momentos))

    def mudar_modo(self, nome: str) -> None:
        self.modo = nome
        self.t0 = self.d.time
        print(f"modo: {nome}")

    def ajustar(self, de: float, i: int | None = None) -> None:
        self.modo = "manual"
        if i is None:
            self.empuxo = float(np.clip(self.empuxo + de, 0.0, cf.EMPUXO_MAX))
        else:
            lo = -cf.MOMENTOS_MAX[i]
            hi = cf.MOMENTOS_MAX[i]
            self.momentos[i] = float(np.clip(self.momentos[i] + de, lo, hi))
        self.hud()

    def hud(self) -> None:
        m = cf.ler_motores(self.m, self.d)
        print(f"[{self.modo:>10}] empuxo = {m['empuxo']:.4f} N · momentos = "
              f"({m['momentos'][0]:+.2e}, {m['momentos'][1]:+.2e}, {m['momentos'][2]:+.2e}) N·m")

    def listar(self) -> None:
        self.hud()
        print(f"modos: {' · '.join(list(cf.MODOS) + ['manual'])}")

    def sensores(self) -> None:
        imu = cf.ler_imu(self.m, self.d)
        est = cf.ler_estado(self.m, self.d)
        print(f"imu:  giro = {np.round(imu['giro'], 3)} rad/s · acc = {np.round(imu['acc'], 2)} m/s² · quat = {np.round(imu['quat'], 3)}")
        print(f"est:  pos = {np.round(est['pos'], 3)} m · vel = {np.round(est['vel'], 3)} m/s · vel_ang = {np.round(est['vel_ang'], 3)} rad/s")


def repl(painel: Painel) -> None:
    ajuda = ("comandos: modo <nome> · empuxo <N> · momento <x|y|z> <N·m> · rotores t1 t2 t3 t4 · "
             "sensores · list · hover · desligar · quit")
    print(f"REPL pronto — {ajuda}")
    while not painel.sair:
        try:
            linha = input()
        except EOFError:
            print("REPL: stdin fechado — controlo só pelo teclado da janela")
            break
        except KeyboardInterrupt:
            painel.sair = True
            break
        partes = linha.split()
        if not partes:
            continue
        cmd, args = partes[0].lower(), partes[1:]
        try:
            if cmd in ("quit", "exit", "q"):
                painel.sair = True
            elif cmd in ("help", "?"):
                print(ajuda)
            elif cmd == "modo" and len(args) == 1:
                if args[0] in cf.MODOS:
                    painel.mudar_modo(args[0])
                else:
                    print(f"modo desconhecido: {args[0]} — {list(cf.MODOS)}")
            elif cmd == "empuxo" and len(args) == 1:
                painel.modo = "manual"
                painel.empuxo = float(np.clip(float(args[0]), 0.0, cf.EMPUXO_MAX))
                painel.hud()
            elif cmd == "momento" and len(args) == 2 and args[0] in "xyz":
                painel.modo = "manual"
                i = "xyz".index(args[0])
                painel.momentos[i] = float(np.clip(float(args[1]), -cf.MOMENTOS_MAX[i], cf.MOMENTOS_MAX[i]))
                painel.hud()
            elif cmd == "rotores" and len(args) == 4:
                painel.modo = "manual"
                f, mm = cf.comandar_rotores(painel.m, painel.d, [float(x) for x in args])
                painel.empuxo, painel.momentos = f, list(mm)
                painel.hud()
            elif cmd == "sensores":
                painel.sensores()
            elif cmd == "list":
                painel.listar()
            elif cmd == "hover":
                painel.modo = "manual"
                painel.empuxo, painel.momentos = cf.PESO, [0.0, 0.0, 0.0]
                painel.hud()
            elif cmd == "descolar":
                painel.modo = "manual"
                painel.empuxo, painel.momentos = 1.2 * cf.PESO, [0.0, 0.0, 0.0]
                painel.hud()
            elif cmd == "desligar":
                painel.modo = "manual"
                painel.empuxo, painel.momentos = 0.0, [0.0, 0.0, 0.0]
                painel.hud()
            else:
                print(f"não entendi: {linha!r} — {ajuda}")
        except ValueError as e:
            print(f"erro: {e} — {ajuda}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modo", default="desligado", choices=list(cf.MODOS) + ["manual"],
                    help='modo inicial (predefinição "desligado": o drone assenta no chão pela física)')
    ap.add_argument("--slowmo", type=float, default=1.0)
    ap.add_argument("--fecha-apos", type=float, default=None, help="fecha a janela sozinha após N s (teste automático)")
    a = ap.parse_args()

    model, data = cf.carregar()
    painel = Painel(model, data)
    painel.modo = a.modo

    def on_key(code: int) -> None:
        c = chr(code) if 32 <= code < 127 else ""
        if c in "1234567":
            painel.mudar_modo((list(cf.MODOS) + ["manual"])[int(c) - 1])
        elif code == CIMA:
            painel.ajustar(+DEMP)
        elif code == BAIXO:
            painel.ajustar(-DEMP)
        elif code == ESQ:
            painel.ajustar(-DMOM, i=0)
        elif code == DIR:
            painel.ajustar(+DMOM, i=0)
        elif code == PAG_CIMA:
            painel.ajustar(+DMOM, i=1)
        elif code == PAG_BAIXO:
            painel.ajustar(-DMOM, i=1)
        elif c == ",":
            painel.ajustar(-DMOM, i=2)
        elif c == ".":
            painel.ajustar(+DMOM, i=2)
        elif c in ("T", "t"):
            painel.modo = "manual"
            painel.empuxo, painel.momentos = 1.2 * cf.PESO, [0.0, 0.0, 0.0]
            print(f"descolar: empuxo = {painel.empuxo:.4f} N (1,2× peso) — à altura desejada, clique H para pairar")
            painel.hud()
        elif c in ("H", "h"):
            painel.modo = "manual"
            painel.empuxo, painel.momentos = cf.PESO, [0.0, 0.0, 0.0]
            painel.hud()
        elif c in ("D", "d"):
            painel.modo = "manual"
            painel.empuxo, painel.momentos = 0.0, [0.0, 0.0, 0.0]
            painel.hud()
        elif c in ("S", "s"):
            painel.sensores()
        elif c in ("L", "l"):
            painel.listar()
        elif c in ("P", "p"):
            painel.pausa = not painel.pausa
            print("pausa" if painel.pausa else "a correr")
        elif c in ("R", "r"):
            mujoco.mj_resetDataKeyframe(model, data, model.key("hover").id)
            mujoco.mj_forward(model, data)
            painel.mudar_modo("manual")
            painel.empuxo, painel.momentos = cf.PESO, [0.0, 0.0, 0.0]
            print("reiniciado no keyframe hover")

    threading.Thread(target=repl, args=(painel,), daemon=True).start()
    print("Crazyflie · simulador físico — arranca com motores desligados (assenta no chão) · "
          "T descolar · H pairar · 1..7 modos · ↑/↓ empuxo · ←/→ momento_x · S sensores")

    with mujoco.viewer.launch_passive(model, data, key_callback=on_key) as v:
        t_ini = time.perf_counter()
        while v.is_running() and not painel.sair:
            if a.fecha_apos is not None and time.perf_counter() - t_ini > a.fecha_apos:
                break
            t0 = time.perf_counter()
            if not painel.pausa:
                with v.lock():
                    painel.aplicar(model, data)
                    mujoco.mj_step(model, data)
            v.sync()
            rest = model.opt.timestep / a.slowmo - (time.perf_counter() - t0)
            if rest > 0:
                time.sleep(rest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
