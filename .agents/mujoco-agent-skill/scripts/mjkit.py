"""mjkit.py — utilitários pequenos para experimentos MuJoCo (headless primeiro). Só depende de mujoco, numpy, imageio, Pillow, matplotlib.

IMPORTE ESTE MÓDULO ANTES de `import mujoco`: ele define MUJOCO_GL=egl (render offscreen por GPU, sem janela) se a variável ainda não existir.

    from lab import mjkit            # cópia no projeto (new_experiment.py faz a cópia) — ou: sys.path.insert(0, ".agents/mujoco-agent-skill/scripts"); import mjkit
    model, data = mjkit.load("models/robo.xml")
    ctrl = mjkit.Ctrl(model)                       # escrita SEGURA de controles por nome (ver abaixo)
    def controlador(m, d): ctrl.set(d, "motor_a", 0.5)
    res = mjkit.record(model, data, controlador, duration=4, mp4="out/v.mp4", gif="out/v.gif", sheet="out/f.png",
                       probes={"z": lambda m, d: d.qpos[2]}, hud=lambda m, d: [f"z={d.qpos[2]:.2f}"])
    mjkit.plot(res["log"], ["z"], "out/z.png")
    mjkit.run_viewer(model, data, controlador, slowmo=1.0)     # janela com o MESMO controlador (launch_passive)

Armadilha tratada: em 3.15 `data.actuator('x').ctrl` usa o ID do atuador como índice de `data.ctrl`; com atuadores MULTI-ENTRADA (pid, dcmotor,
orientation) `nu ≠ nactuator` e isso grava no slot errado. `Ctrl.set` usa `actuator_ctrladr` e `actuator_ctrlnum` (sempre correto).
"""
from __future__ import annotations

import os

os.environ.setdefault("MUJOCO_GL", "egl")  # offscreen sem janela; o viewer (GLFW) não depende disso
if os.environ["MUJOCO_GL"] == "egl":
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")  # evita o PyOpenGL prender o GLX e quebrar o EGL em sessões X11

import time
from pathlib import Path
from typing import Callable, Sequence

import mujoco
import numpy as np

__all__ = ["load", "Ctrl", "energy", "record", "plot", "contact_sheet", "run_viewer", "free_fall_time", "named_sites"]


# ----------------------------------------------------------------------------------------------- carga
def load(source: str | Path, *, energy_flag: bool = True) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """Carrega MJCF/URDF/.mjb de um caminho, ou MJCF de uma string XML. Liga o cálculo de energia (data.energy = [potencial, cinética])."""
    s = str(source)
    if s.lstrip().startswith("<"):
        model = mujoco.MjModel.from_xml_string(s)
    elif s.endswith(".mjb"):
        model = mujoco.MjModel.from_binary_path(s)
    else:
        model = mujoco.MjModel.from_xml_path(s)
    if energy_flag:
        model.opt.enableflags |= mujoco.mjtEnableBit.mjENBL_ENERGY
    return model, mujoco.MjData(model)


# --------------------------------------------------------------------------------------- controle seguro
class Ctrl:
    """Escreve em data.ctrl pelo NOME do atuador usando actuator_ctrladr/ctrlnum (correto também para atuadores multi-entrada)."""

    def __init__(self, model: mujoco.MjModel):
        self.m = model
        self.adr = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i): (int(model.actuator_ctrladr[i]), int(model.actuator_ctrlnum[i]))
                    for i in range(model.nactuator)}

    def set(self, data: mujoco.MjData, name: str, value) -> None:
        a, n = self.adr[name]
        v = np.atleast_1d(np.asarray(value, dtype=float))
        if v.size != n:  # escalar em atuador multi-entrada seria ambíguo (replicaria em todas as entradas): exija vetor do tamanho certo
            raise ValueError(f"atuador '{name}' tem {n} controle(s) (ctrladr={a}); recebeu {v.size} valor(es) — passe um vetor de tamanho {n}")
        data.ctrl[a: a + n] = v

    def get(self, data: mujoco.MjData, name: str) -> np.ndarray:
        a, n = self.adr[name]
        return data.ctrl[a: a + n].copy()


def energy(data: mujoco.MjData) -> tuple[float, float]:
    """(potencial, cinética) — exige mjENBL_ENERGY (load() liga)."""
    return float(data.energy[0]), float(data.energy[1])


def named_sites(model: mujoco.MjModel) -> list[str]:
    return [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SITE, i) or f"#{i}" for i in range(model.nsite)]


def free_fall_time(height: float, g: float = 9.81) -> float:
    return float(np.sqrt(2.0 * height / g))


# ------------------------------------------------------------------------------------------------ vídeo
def _font(size: int):
    from PIL import ImageFont

    try:
        import matplotlib

        return ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSansMono.ttf"), size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _hud(frame: np.ndarray, lines: Sequence[str]):
    from PIL import Image, ImageDraw

    img = Image.fromarray(frame)
    if not lines:
        return img
    d = ImageDraw.Draw(img, "RGBA")
    tam = max(14, frame.shape[0] // 32)
    f = _font(tam)
    w = max(len(s) for s in lines) * (tam * 0.62) + 28
    d.rounded_rectangle((10, 10, 10 + w, 10 + len(lines) * (tam + 7) + 14), 10, fill=(8, 12, 20, 175))
    for i, s in enumerate(lines):
        d.text((22, 17 + i * (tam + 7)), s, font=f, fill=(235, 240, 248, 255))
    return img


def contact_sheet(frames: Sequence[tuple[str, object]], path: str | Path, cols: int = 4, width: int = 480) -> None:
    """Monta uma tira de quadros [(rótulo, PIL.Image)] em grade."""
    from PIL import Image, ImageDraw

    ims = []
    for label, im in frames:
        h = int(im.height * width / im.width)
        t = im.resize((width, h), Image.LANCZOS)
        ImageDraw.Draw(t, "RGBA").rectangle((0, h - 30, width, h), fill=(8, 12, 20, 190))
        ImageDraw.Draw(t).text((10, h - 26), label, font=_font(20), fill=(235, 240, 248))
        ims.append(t)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * width, rows * ims[0].height), (8, 12, 20))
    for i, t in enumerate(ims):
        sheet.paste(t, ((i % cols) * width, (i // cols) * ims[0].height))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def record(model: mujoco.MjModel, data: mujoco.MjData, controller: Callable | None = None, *, duration: float = 4.0, fps: int = 60, slowmo: float = 1.0,
           camera: str | int | None = None, width: int = 1280, height: int = 720, mp4: str | Path | None = None, gif: str | Path | None = None,
           gif_width: int = 480, gif_fps: int = 15, sheet: str | Path | None = None, sheet_times: Sequence[float] | None = None, contacts: bool = False,
           hud: Callable | None = None, probes: dict[str, Callable] | None = None, on_step: Callable | None = None, track: str | None = None,
           consistent: bool = False) -> dict:
    """Simula `duration` s (tempo SIMULADO) chamando `controller(model, data)` ANTES de cada mj_step, e (opcional) grava vídeo/GIF/filmstrip.

    `slowmo` 0.5 = câmera lenta (a gravação captura a cada slowmo/fps s de tempo simulado). `probes` = {nome: f(model, data)} amostrados a cada passo → res["log"].
    `track` = nome de corpo para a câmera livre seguir (usa MjvCamera tracking). Devolve {"log": {...}, "frames": n, "wall_s": segundos}.
    ⚠ Após `mj_step`, grandezas DERIVADAS (xpos/xipos/xmat, sensordata, contatos, energia) refletem o estado ANTERIOR à integração (1 passo, `timestep` s de atraso).
    `consistent=True` chama `mj_forward` antes de probes/hud/render (custa ~1 mj_forward por passo) para que tudo corresponda a `data.time`.
    """
    from PIL import Image

    log: dict[str, list] = {"t": [], "ncon": [], "pe": [], "ke": []}
    for k in (probes or {}):
        log[k] = []
    n_steps = int(round(duration / model.opt.timestep))
    render = bool(mp4 or gif or sheet)
    renderer = writer = None
    gif_frames: list = []
    sheet_frames: list = []
    pend = sorted(sheet_times) if sheet_times else ([duration * i / 7 for i in range(8)] if sheet else [])
    if render:
        renderer = mujoco.Renderer(model, height=height, width=width)
        opt = mujoco.MjvOption()
        if contacts:
            opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True
            opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTFORCE] = True
        cam: object = camera if camera is not None else -1
        if track:
            tcam = mujoco.MjvCamera()
            tcam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
            tcam.trackbodyid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, track)
            tcam.distance, tcam.azimuth, tcam.elevation = 2.5, 120, -20
            cam = tcam
        if mp4:
            import imageio.v2 as imageio

            Path(mp4).parent.mkdir(parents=True, exist_ok=True)
            writer = imageio.get_writer(str(mp4), fps=fps, codec="libx264", quality=6, pixelformat="yuv420p", macro_block_size=2,
                                        ffmpeg_params=["-movflags", "+faststart"])
        dt_frame, next_t, k = slowmo / fps, 0.0, 0
    t0 = time.perf_counter()
    try:
        for i in range(n_steps):
            if controller:
                controller(model, data)
            mujoco.mj_step(model, data)
            if consistent:
                mujoco.mj_forward(model, data)  # atualiza xpos/sensores/contatos/energia para o estado ATUAL
            log["t"].append(data.time)
            log["ncon"].append(int(data.ncon))
            pe, ke = energy(data)
            log["pe"].append(pe), log["ke"].append(ke)
            for kname, fn in (probes or {}).items():
                v = fn(model, data)
                log[kname].append(np.array(v, copy=True) if isinstance(v, np.ndarray) else v)  # views do MjData aliasariam (todas as linhas = a última)
            if on_step:
                on_step(model, data)
            if render and data.time + 1e-9 >= next_t:
                next_t += dt_frame
                renderer.update_scene(data, camera=cam, scene_option=opt)
                frame = renderer.render()
                img = _hud(frame, hud(model, data) if hud else [f"t = {data.time:5.2f} s"])
                if writer:
                    writer.append_data(np.asarray(img))
                if gif and k % max(1, round(fps / gif_fps)) == 0:
                    gif_frames.append(img.resize((gif_width, int(gif_width * height / width)), Image.LANCZOS).quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
                while pend and data.time + 1e-9 >= pend[0]:
                    sheet_frames.append((f"t = {data.time:5.2f} s", img.copy())); pend.pop(0)
                k += 1
    finally:
        if writer:
            writer.close()
        if renderer:
            renderer.close()
    wall = time.perf_counter() - t0
    if gif and gif_frames:
        Path(gif).parent.mkdir(parents=True, exist_ok=True)
        gif_frames[0].save(str(gif), save_all=True, append_images=gif_frames[1:], duration=int(1000 / gif_fps), loop=0, optimize=True)
    if sheet and sheet_frames:
        contact_sheet(sheet_frames, sheet)
    return {"log": {k2: np.asarray(v) for k2, v in log.items()}, "frames": (k if render else 0), "wall_s": wall}


# ---------------------------------------------------------------------------------------------- gráficos
def plot(log: dict, keys: Sequence[str], path: str | Path, title: str = "", *, refs: dict[str, object] | None = None) -> None:
    """Gráfico simples (tema escuro) de log[k] × log['t'] para as chaves dadas.
    `refs` desenha linhas horizontais: {rótulo: (chave_do_painel, valor)} só no painel indicado; {rótulo: valor} desenha em TODOS os painéis."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"axes.facecolor": "#0e1420", "figure.facecolor": "#0e1420", "text.color": "#e6ebf5", "axes.labelcolor": "#e6ebf5",
                         "xtick.color": "#aab4c8", "ytick.color": "#aab4c8", "axes.edgecolor": "#3a4660", "grid.color": "#243049"})
    fig, axes = plt.subplots(len(keys), 1, figsize=(11, 2.8 * len(keys)), sharex=True, squeeze=False)
    for ax, k in zip(axes[:, 0], keys):
        v = np.asarray(log[k])
        if v.ndim == 1:
            ax.plot(log["t"], v, lw=1.8, color="#ffa24a", label=k)
        else:
            for j in range(v.shape[1]):
                ax.plot(log["t"], v[:, j], lw=1.4, label=f"{k}[{j}]")
        for lab, val in (refs or {}).items():
            alvo, y = val if isinstance(val, tuple) else (None, val)
            if alvo is None or alvo == k:
                ax.axhline(y, ls="--", lw=1, color="#7dd3fc", label=lab)
        ax.set_ylabel(k); ax.grid(True, alpha=.5); ax.legend(loc="upper right", fontsize=8)
    axes[-1, 0].set_xlabel("t (s)")
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=100)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------ viewer
def run_viewer(model: mujoco.MjModel, data: mujoco.MjData, controller: Callable | None = None, *, slowmo: float = 1.0,
               close_after: float | None = None) -> None:
    """Abre a janela (mujoco.viewer.launch_passive) e roda SEU controlador em tempo real. R reinicia · P pausa · fecha a janela para sair.
    No macOS rode com `mjpython`. Em sessão Wayland o GLFW usa o backend Wayland nativo. `close_after` (s) fecha sozinho (teste automático)."""
    import mujoco.viewer

    st = {"pause": False}

    def key(code: int) -> None:
        c = chr(code)
        if c == "R":
            mujoco.mj_resetData(model, data); mujoco.mj_forward(model, data)
        elif c == "P":
            st["pause"] = not st["pause"]

    with mujoco.viewer.launch_passive(model, data, key_callback=key) as v:
        t_ini = time.perf_counter()
        while v.is_running():
            if close_after is not None and time.perf_counter() - t_ini > close_after:
                break
            t0 = time.perf_counter()
            if not st["pause"]:
                with v.lock():
                    if controller:
                        controller(model, data)
                    mujoco.mj_step(model, data)
            v.sync()
            rest = model.opt.timestep / slowmo - (time.perf_counter() - t0)
            if rest > 0:
                time.sleep(rest)
