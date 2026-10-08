#!/usr/bin/env python3
"""Spot (Boston Dynamics) — janela interativa para mexer nas JUNTAS e MOTORES, sem lógica de locomoção.

Modelo pronto do mujoco_menagerie (`models/boston_dynamics_spot/scene.xml`): 12 servos `<position>` (PD)
a seguir os alvos que você mandar. Não há marcha nem equilíbrio — se empurrar forte, o robô cai.

    uv run python experiments/07_spot_motores/view.py
    uv run python experiments/07_spot_motores/view.py --alvo "fl_hy=1.2,fl_kn=-1.6"

Teclado (com foco na janela):
    TAB / N  próxima junta        B  junta anterior       ↑ / ↓  alvo ±0,05 rad
    PGUP / PGDN  alvo ±0,2 rad    H  postura home          Z  zeros (dentro dos limites)
    1..4  posturas prontas (home/agachar/sentar/esticar)   S  varrer a junta selecionada
    L  listar estado              P  pausa                 R  reiniciar (volta ao home)

Terminal (REPL, ao lado da janela):
    set fl_hy 1.2 · pose agachar · sweep fl_kn 0.3 · sweep off · list · home · help · quit
"""
from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
from lab import mjkit  # noqa: E402  (define MUJOCO_GL=egl antes de importar mujoco)
from lab import spot  # noqa: E402  (API de funções: modos, controles e leituras de sensores)

import argparse  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

import mujoco  # noqa: E402
import mujoco.viewer  # noqa: E402  (import aqui, não dentro de main(): senão `mujoco` vira local e dá UnboundLocalError)
import numpy as np  # noqa: E402

AQUI = Path(__file__).resolve().parent
JUNTAS = spot.JUNTAS
FREQUENCIA_SWEEP = 0.25  # Hz

# códigos GLFW das teclas especiais (o key_callback do viewer recebe o keycode)
TAB, ESQ, DIR, CIMA, BAIXO, PAG_CIMA, PAG_BAIXO = 258, 263, 262, 265, 264, 266, 267


class Painel:
    """Estado compartilhado entre o viewer, o teclado e o REPL. Alvo em radianos, sempre dentro de ctrlrange."""

    def __init__(self, model: mujoco.MjModel, data: mujoco.MjData):
        self.m, self.d = model, data
        self.ctrl = mjkit.Ctrl(model)
        kid = model.key("home").id
        self.home = model.key_ctrl[kid].copy()
        self.lo, self.hi = model.actuator_ctrlrange[:, 0].copy(), model.actuator_ctrlrange[:, 1].copy()
        self.qadr = [int(model.jnt_qposadr[model.joint(n).id]) for n in JUNTAS]  # acessores nomeados devolvem arrays: use os arrays crus
        self.pos = np.zeros(len(JUNTAS))  # posição medida por junta, atualizada em aplicar()
        self.alvo = self.home.copy()
        self.sel = 0
        self.pausa = False
        self.sair = False
        self.sweep_j: int | None = None
        self.sweep_amp = 0.25

    # ------------------------------------------------------------------ utilidades
    def nome_sel(self) -> str:
        return JUNTAS[self.sel]

    def mover(self, delta: float) -> None:
        j = self.sel
        self.alvo[j] = float(np.clip(self.alvo[j] + delta, self.lo[j], self.hi[j]))
        self.hud()

    def set_alvo(self, nome: str, valor: float) -> None:
        aplicado = spot.definir_alvo(self.m, self.d, nome, valor)  # a API corta para os limites
        j = JUNTAS.index(nome)
        self.alvo[j] = aplicado
        self.sel = j
        self.hud()

    def pose(self, nome: str) -> None:
        aplicados = spot.postura(self.m, self.d, nome)  # home/zero/agachar/sentar/esticar via lab/spot.py
        for jn, v in aplicados.items():
            self.alvo[JUNTAS.index(jn)] = v
        self.hud(f"postura: {nome}")

    def sensores(self) -> None:
        imu = spot.ler_imu(self.m, self.d)
        pes = spot.ler_pes(self.m, self.d)
        print(f"imu: giro = {np.round(imu['giro'], 3)} rad/s · acc = {np.round(imu['acc'], 2)} m/s² · "
              f"quat = {np.round(imu['quat'], 3)} · vel = {np.round(imu['vel'], 3)} m/s")
        print("pés (N): " + " · ".join(f"{k} = {v:.1f}" for k, v in pes.items())
              + f" · Σ = {sum(pes.values()):.1f} · peso = {spot.peso(self.m):.1f}")

    def hud(self, extra: str = "") -> None:
        j = self.sel
        pos = self.pos_sel()
        linha = (f"[{JUNTAS[j]:>5}] alvo = {self.alvo[j]:+.3f} rad · posição = {pos:+.3f} rad · "
                 f"faixa = [{self.lo[j]:+.3f}, {self.hi[j]:+.3f}]")
        if extra:
            linha += f"   ({extra})"
        print(linha)

    def pos_sel(self) -> float:
        return float(self.pos[self.sel])  # atualizado em aplicar() a cada passo

    def listar(self) -> None:
        print(f"{'junta':>6} {'alvo':>9} {'posição':>9} {'faixa':>18}")
        for i, nome in enumerate(JUNTAS):
            print(f"{nome:>6} {self.alvo[i]:+9.3f} {self.pos[i]:+9.3f} [{self.lo[i]:+.3f}, {self.hi[i]:+.3f}]")

    # ------------------------------------------------------------------ passo de simulação
    def aplicar(self, model: mujoco.MjModel, data: mujoco.MjData) -> None:
        alvo = self.alvo.copy()
        if self.sweep_j is not None:
            j = self.sweep_j
            alvo[j] = self.alvo[j] + self.sweep_amp * np.sin(2 * np.pi * FREQUENCIA_SWEEP * data.time)
        alvo = np.clip(alvo, self.lo, self.hi)
        for i, nome in enumerate(JUNTAS):
            self.ctrl.set(data, nome, alvo[i])
        self.pos = np.array([data.qpos[k] for k in self.qadr])


def repl(painel: Painel) -> None:
    """REPL no terminal: comandos de uma linha para mover juntas e mudar posturas."""
    ajuda = ("comandos: set <junta> <rad> · pose <home|agachar|sentar|esticar|zero> · sweep <junta> [amp] · "
             "sweep off · sensores · list · home · help · quit")
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
            elif cmd == "list":
                painel.listar()
            elif cmd == "sensores":
                painel.sensores()
            elif cmd == "home":
                painel.pose("home")
            elif cmd == "set" and len(args) == 2:
                painel.set_alvo(args[0], float(args[1]))
            elif cmd == "pose" and len(args) == 1:
                painel.pose(args[0])
            elif cmd == "sweep" and args and args[0] == "off":
                painel.sweep_j = None
                print("sweep OFF")
            elif cmd == "sweep" and args:
                painel.sweep_j = JUNTAS.index(args[0])
                painel.sweep_amp = float(args[1]) if len(args) > 1 else 0.25
                print(f"sweep ON em {args[0]} (±{painel.sweep_amp:.2f} rad, {FREQUENCIA_SWEEP} Hz)")
            else:
                print(f"não entendi: {linha!r} — {ajuda}")
        except ValueError as e:
            print(f"erro: {e} — {ajuda}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alvo", default="", help='postura inicial, ex.: "fl_hy=1.2,fl_kn=-1.6"')
    ap.add_argument("--slowmo", type=float, default=1.0)
    ap.add_argument("--fecha-apos", type=float, default=None, help="fecha a janela sozinha após N s (teste automático)")
    a = ap.parse_args()

    model, data = spot.carregar()  # modelo do menagerie + sensores (lab/spot.py), já no keyframe home
    painel = Painel(model, data)
    painel.pos = np.array([data.qpos[k] for k in painel.qadr])

    if a.alvo:
        for par in a.alvo.split(","):
            nome, valor = par.split("=")
            painel.set_alvo(nome.strip(), float(valor))

    def on_key(code: int) -> None:
        c = chr(code) if 32 <= code < 127 else ""
        if code == TAB or c in ("N", "n"):
            painel.sel = (painel.sel + 1) % len(JUNTAS)
            painel.hud("próxima junta")
        elif c in ("B", "b"):
            painel.sel = (painel.sel - 1) % len(JUNTAS)
            painel.hud("junta anterior")
        elif code == CIMA:
            painel.mover(+0.05)
        elif code == BAIXO:
            painel.mover(-0.05)
        elif code == PAG_CIMA:
            painel.mover(+0.2)
        elif code == PAG_BAIXO:
            painel.mover(-0.2)
        elif c in ("H", "h"):
            painel.pose("home")
        elif c in ("Z", "z"):
            painel.pose("zero")
        elif c in "1234":
            painel.pose(["home", "agachar", "sentar", "esticar"][int(c) - 1])
        elif c in ("S", "s"):
            if painel.sweep_j == painel.sel:
                painel.sweep_j = None
                print(f"sweep OFF em {painel.nome_sel()}")
            else:
                painel.sweep_j = painel.sel
                print(f"sweep ON em {painel.nome_sel()} (±{painel.sweep_amp:.2f} rad, {FREQUENCIA_SWEEP} Hz)")
        elif c in ("I", "i"):
            painel.sensores()
        elif c in ("L", "l"):
            painel.listar()
        elif c in ("P", "p"):
            painel.pausa = not painel.pausa
            print("pausa" if painel.pausa else "a correr")
        elif c in ("R", "r"):
            mujoco.mj_resetDataKeyframe(model, data, model.key("home").id)
            painel.pose("home")
            print("reiniciado na postura home")

    threading.Thread(target=repl, args=(painel,), daemon=True).start()
    print("Spot · juntas e motores — TAB/N próxima junta · ↑/↓ alvo · H home · 1..4 posturas · S sweep · L listar")

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
