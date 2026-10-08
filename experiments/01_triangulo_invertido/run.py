#!/usr/bin/env python3
"""Experimento 01 — objeto triangular de cabeça para baixo caindo (MuJoCo 3.15, sem janela).

Simula a queda de um prisma triangular (ou tetraedro) com a aresta/ponta para baixo, VALIDA a física contra
valores analíticos e grava vídeo (MP4), GIF, tira de quadros (filmstrip) e gráficos de telemetria.

    uv run python experiments/01_triangulo_invertido/run.py                      # prisma triangular (padrão)
    uv run python experiments/01_triangulo_invertido/run.py --modelo models/tetraedro_invertido.xml
    uv run python experiments/01_triangulo_invertido/run.py --sem-video          # só os números (rápido)
    uv run python experiments/01_triangulo_invertido/run.py --slowmo 1 --duracao 4 --contatos

Saídas em experiments/01_triangulo_invertido/out/: queda.mp4 · queda.gif · filmstrip.png · telemetria.png · resumo.json
Janela interativa (zoom, arrastar, reiniciar com Backspace): view.py, nesta mesma pasta.
"""
from __future__ import annotations

import os

# Render offscreen por GPU (EGL), sem abrir janela. TEM de vir ANTES de `import mujoco`.
os.environ.setdefault("MUJOCO_GL", "egl")

import argparse
import json
import sys
import time
from pathlib import Path

import imageio.v2 as imageio
import matplotlib
import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (depois de escolher o backend)

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
G = 9.81


# --------------------------------------------------------------------------------------------- modelo
def carregar(caminho: Path) -> tuple[mujoco.MjModel, mujoco.MjData]:
    if not caminho.exists():
        sys.exit(f"Erro: modelo não encontrado: {caminho} — Solução: passe --modelo com um XML existente (ex.: models/triangulo_invertido.xml).")
    model = mujoco.MjModel.from_xml_path(str(caminho))
    model.opt.enableflags |= mujoco.mjtEnableBit.mjENBL_ENERGY  # data.energy = [potencial, cinética]
    return model, mujoco.MjData(model)


def corpo_livre(model: mujoco.MjModel) -> int:
    """Id do primeiro corpo com junta livre (o objeto que cai)."""
    for j in range(model.njnt):
        if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE:
            return int(model.jnt_bodyid[j])
    sys.exit("Erro: o modelo não tem corpo com <freejoint> — Solução: adicione <freejoint/> ao corpo que deve cair.")


def numerico(model: mujoco.MjModel, nome: str) -> float | None:
    """Valor de um <custom><numeric name=...> do MJCF (None se não existir)."""
    return float(model.numeric(nome).data[0]) if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_NUMERIC, nome) >= 0 else None


def altura_vertice_mais_baixo(model: mujoco.MjModel, data: mujoco.MjData, body_id: int) -> float:
    """Altura (mundo) do vértice mais baixo das malhas do corpo, no estado atual (mj_forward já feito)."""
    zmin = np.inf
    for g in range(model.ngeom):
        if model.geom_bodyid[g] != body_id or model.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH:
            continue
        m = model.geom_dataid[g]
        v = model.mesh_vert[model.mesh_vertadr[m]: model.mesh_vertadr[m] + model.mesh_vertnum[m]]
        mundo = data.geom_xpos[g] + v @ data.geom_xmat[g].reshape(3, 3).T
        zmin = min(zmin, float(mundo[:, 2].min()))
    return zmin


# ------------------------------------------------------------------------------------------- desenho
def fonte(tam: int):
    """DejaVu Sans Mono (vem com o matplotlib): tem acentos e símbolos como ×, ao contrário da fonte padrão do Pillow."""
    try:
        return ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSansMono.ttf"), tam)
    except OSError:
        return ImageFont.load_default()


def hud(frame: np.ndarray, linhas: list[str]) -> Image.Image:
    img = Image.fromarray(frame)
    d = ImageDraw.Draw(img, "RGBA")
    tam = max(16, frame.shape[0] // 30)
    f = fonte(tam)
    h = len(linhas) * (tam + 8) + 16
    d.rounded_rectangle((12, 12, 12 + int(frame.shape[1] * 0.62), 12 + h), 10, fill=(8, 12, 20, 175))
    for i, ln in enumerate(linhas):
        d.text((24, 20 + i * (tam + 8)), ln, font=f, fill=(235, 240, 248, 255))
    return img


def filmstrip(quadros: list[tuple[str, Image.Image]], caminho: Path, colunas: int = 4, largura: int = 480) -> None:
    ims = []
    for rotulo, im in quadros:
        h = int(im.height * largura / im.width)
        t = im.resize((largura, h), Image.LANCZOS)
        ImageDraw.Draw(t, "RGBA").rectangle((0, h - 30, largura, h), fill=(8, 12, 20, 190))
        ImageDraw.Draw(t).text((10, h - 26), rotulo, font=fonte(20), fill=(235, 240, 248))
        ims.append(t)
    linhas = (len(ims) + colunas - 1) // colunas
    h = ims[0].height
    folha = Image.new("RGB", (colunas * largura, linhas * h), (8, 12, 20))
    for i, t in enumerate(ims):
        folha.paste(t, ((i % colunas) * largura, (i // colunas) * h))
    folha.save(caminho)


def grafico(r: dict, tp: float, z_rep: float | None, caminho: Path, titulo: str) -> None:
    t = r["t"]
    plt.rcParams.update({"axes.facecolor": "#0e1420", "figure.facecolor": "#0e1420", "text.color": "#e6ebf5",
                         "axes.labelcolor": "#e6ebf5", "xtick.color": "#aab4c8", "ytick.color": "#aab4c8",
                         "axes.edgecolor": "#3a4660", "grid.color": "#243049", "font.size": 10})
    fig, ax = plt.subplots(2, 2, figsize=(14, 8.4), dpi=100)
    a = ax[0, 0]
    a.plot(t, r["z"], color="#ffa24a", lw=2, label="altura do centro de massa")
    a.axvline(tp, color="#7dd3fc", ls="--", lw=1.3, label=f"impacto previsto √(2h/g) = {tp:.3f} s")
    if z_rep:
        a.axhline(z_rep, color="#86efac", ls=":", lw=1.3, label=f"altura de repouso esperada = {z_rep:.4f} m")
    a.set(title="Altura × tempo", xlabel="t (s)", ylabel="z (m)"); a.legend(loc="upper right", fontsize=8); a.grid(True, alpha=.5)
    a = ax[0, 1]
    a.plot(t, r["pe"], color="#7dd3fc", label="potencial"); a.plot(t, r["ke"], color="#fca5a5", label="cinética")
    a.plot(t, r["pe"] + r["ke"], color="#f8fafc", lw=2, label="mecânica total")
    a.set(title="Energia (dissipada no impacto e no atrito)", xlabel="t (s)", ylabel="J"); a.legend(fontsize=8); a.grid(True, alpha=.5)
    a = ax[1, 0]
    a.semilogy(t, np.maximum(r["v"], 1e-12), color="#fbbf24", label="|v| linear (m/s)")
    a.semilogy(t, np.maximum(r["w"], 1e-12), color="#a78bfa", label="|ω| angular (rad/s)")
    a.axhline(1e-3, color="#475569", ls=":", lw=1)
    a.set(title="Velocidades (escala log) — repouso = abaixo de 1e-3", xlabel="t (s)", ylim=(1e-12, 1e2)); a.legend(fontsize=8); a.grid(True, alpha=.5)
    a = ax[1, 1]
    a.step(t, r["ncon"], color="#4ade80", where="post", label="contatos")
    b = a.twinx(); b.plot(t, -r["pen"] * 1000, color="#f87171", lw=1.2, label="penetração máx. (mm)")
    b.tick_params(colors="#aab4c8"); b.set_ylabel("mm", color="#f87171")
    a.set(title="Contatos e penetração", xlabel="t (s)", ylabel="nº de contatos"); a.grid(True, alpha=.5)
    fig.suptitle(titulo, fontsize=13, y=0.995)
    fig.tight_layout(); fig.savefig(caminho); plt.close(fig)


# ----------------------------------------------------------------------------------------- simulação
def simular(model, data, duracao, bid, renderizar=None):
    """Passo a passo, registando telemetria. `renderizar(t)` é chamado a cada passo (decide se captura um quadro)."""
    n = int(round(duracao / model.opt.timestep))
    r = {k: np.zeros(n) for k in ("t", "z", "v", "w", "pe", "ke", "pen")}
    r["ncon"] = np.zeros(n, dtype=int)
    t_contato = None
    for i in range(n):
        mujoco.mj_step(model, data)
        r["t"][i] = data.time
        r["z"][i] = data.xipos[bid, 2]
        r["v"][i] = np.linalg.norm(data.qvel[:3])
        r["w"][i] = np.linalg.norm(data.qvel[3:6])
        r["pe"][i], r["ke"][i] = data.energy[0], data.energy[1]
        r["ncon"][i] = data.ncon
        r["pen"][i] = min((c.dist for c in data.contact[: data.ncon]), default=0.0)
        if t_contato is None and data.ncon > 0:
            t_contato = data.time
        if renderizar:
            renderizar(data.time, i)
    return r, t_contato


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", default=str(RAIZ / "models" / "triangulo_invertido.xml"), help="MJCF do experimento")
    ap.add_argument("--duracao", type=float, default=3.0, help="segundos SIMULADOS (padrão 3.0)")
    ap.add_argument("--slowmo", type=float, default=0.5, help="câmera lenta: 0.5 = metade da velocidade real (padrão 0.5)")
    ap.add_argument("--fps", type=int, default=60, help="quadros por segundo do vídeo (padrão 60)")
    ap.add_argument("--largura", type=int, default=1280)
    ap.add_argument("--altura", type=int, default=720)
    ap.add_argument("--saida", default=str(AQUI / "out"), help="pasta de saída")
    ap.add_argument("--sem-video", action="store_true", help="não renderiza (só telemetria e validação)")
    ap.add_argument("--contatos", action="store_true", help="desenha pontos e forças de contato no vídeo (mjVIS_CONTACTPOINT/FORCE)")
    a = ap.parse_args()

    caminho = Path(a.modelo)
    out = Path(a.saida); out.mkdir(parents=True, exist_ok=True)
    model, data = carregar(caminho)
    bid = corpo_livre(model)
    mujoco.mj_forward(model, data)

    z0 = float(data.xipos[bid, 2])
    zv = altura_vertice_mais_baixo(model, data, bid)
    tp = float(np.sqrt(2 * zv / G)) if np.isfinite(zv) else float("nan")
    massa = float(model.body_mass[bid])
    integr = mujoco.mjtIntegrator(model.opt.integrator).name.replace("mjINT_", "")
    print(f"MuJoCo {mujoco.__version__} · modelo {caminho.relative_to(RAIZ) if caminho.is_relative_to(RAIZ) else caminho}"
          f" · integrador {integr} · dt = {model.opt.timestep*1000:.1f} ms · MUJOCO_GL={os.environ.get('MUJOCO_GL')}")
    print(f"corpo '{model.body(bid).name}': massa {massa:.4f} kg · CM a {z0:.3f} m · vértice mais baixo a {zv:.4f} m "
          f"→ impacto previsto (queda livre) em {tp:.4f} s")

    # ------------------------------------------------------------- render + simulação
    mp4 = gif = None
    renderer = quadros_gif = writer = None
    estado = {"prox": 0.0, "k": 0}
    quadros_fs: list[tuple[str, Image.Image]] = []
    tempos_fs = [0.0, tp - 0.10, tp + 0.03, tp + 0.15, tp + 0.30, tp + 0.55, tp + 1.0, a.duracao - 0.02] if np.isfinite(tp) else []
    t_gif = 20
    if not a.sem_video:
        try:
            renderer = mujoco.Renderer(model, height=a.altura, width=a.largura)
        except Exception as e:  # noqa: BLE001
            sys.exit(f"Erro: não foi possível criar o Renderer ({e}) — Solução: confira MUJOCO_GL=egl (ou osmesa) e <visual><global offwidth/offheight> do XML.")
        opt = mujoco.MjvOption()
        if a.contatos:
            opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True
            opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTFORCE] = True
        mp4 = out / "queda.mp4"; gif = out / "queda.gif"
        writer = imageio.get_writer(mp4, fps=a.fps, codec="libx264", quality=8, pixelformat="yuv420p", macro_block_size=16,
                                    ffmpeg_params=["-movflags", "+faststart"])
        quadros_gif = []
        dt_quadro = a.slowmo / a.fps  # tempo SIMULADO entre quadros (câmera lenta)
        pend = list(tempos_fs)

        def renderizar(t: float, i: int) -> None:
            if t + 1e-9 < estado["prox"]:
                return
            estado["prox"] += dt_quadro
            renderer.update_scene(data, camera="frontal" if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, "frontal") >= 0 else -1, scene_option=opt)
            quadro = renderer.render()
            v = float(np.linalg.norm(data.qvel[:3]))
            img = hud(quadro, [f"t = {t:5.3f} s    z_cm = {data.xipos[bid,2]:.3f} m    |v| = {v:4.2f} m/s",
                               f"contatos: {data.ncon}      câmera lenta {a.slowmo:g}×"])
            writer.append_data(np.asarray(img))
            if estado["k"] % max(1, round(a.fps / t_gif)) == 0:
                quadros_gif.append(img.resize((540, int(540 * a.altura / a.largura)), Image.LANCZOS).quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
            while pend and t >= pend[0]:
                quadros_fs.append((f"t = {t:5.3f} s", img.copy())); pend.pop(0)
            estado["k"] += 1
    else:
        renderizar = None

    t0 = time.perf_counter()
    r, t_contato = simular(model, data, a.duracao, bid, renderizar)
    dt_sim = time.perf_counter() - t0
    if writer:
        writer.close(); renderer.close()
        quadros_gif[0].save(gif, save_all=True, append_images=quadros_gif[1:], duration=int(1000 / t_gif), loop=0, optimize=True)
        if quadros_fs:
            filmstrip(quadros_fs, out / "filmstrip.png")
    print(f"simulados {a.duracao:g} s ({len(r['t'])} passos) em {dt_sim:.2f} s de relógio (inclui render se ligado)")

    # ------------------------------------------------------------------ validação física
    esp_massa = numerico(model, "esperado_massa_kg")
    esp_zrep = numerico(model, "esperado_altura_repouso")
    v_fim, w_fim, z_fim = float(r["v"][-1]), float(r["w"][-1]), float(r["z"][-1])
    e_tot = r["pe"] + r["ke"]
    checks: list[tuple[str, bool, str]] = []
    if esp_massa:
        checks.append(("massa = densidade × volume", abs(massa - esp_massa) < 1e-3 * esp_massa, f"{massa:.4f} kg (analítico {esp_massa:.4f})"))
    if t_contato is not None and np.isfinite(tp):
        checks.append(("instante do 1º contato = queda livre", abs(t_contato - tp) < 3 * model.opt.timestep,
                       f"simulado {t_contato:.4f} s · previsto {tp:.4f} s · Δ = {abs(t_contato-tp)*1000:.1f} ms"))
    else:
        checks.append(("houve contato com o chão", False, "nenhum contato registado — aumente --duracao"))
    checks.append(("energia mecânica nunca excede a inicial", float(e_tot.max() - e_tot[0]) < 0.01 * abs(e_tot[0]) + 0.5,
                   f"E0 = {e_tot[0]:.2f} J → E_final = {e_tot[-1]:.3f} J (máx. acima de E0: {max(0.0, float(e_tot.max()-e_tot[0])):.2e} J)"))
    checks.append(("termina em repouso", v_fim < 1e-3 and w_fim < 1e-2, f"|v| = {v_fim:.1e} m/s · |ω| = {w_fim:.1e} rad/s"))
    if esp_zrep:
        checks.append(("altura de repouso = raio inscrito", abs(z_fim - esp_zrep) < 0.003, f"{z_fim:.4f} m (analítico {esp_zrep:.4f} m)"))
    checks.append(("sem NaN/explosão", bool(np.isfinite(r["z"]).all() and np.abs(r["z"]).max() < 10), f"z máx. = {np.nanmax(np.abs(r['z'])):.2f} m"))

    print("\nVALIDAÇÃO FÍSICA")
    for nome, ok, det in checks:
        print(f"  [{'OK ' if ok else 'FALHA'}] {nome:40s} {det}")
    print(f"  penetração máxima no contato: {-r['pen'].min()*1000:.2f} mm · contatos simultâneos (máx.): {int(r['ncon'].max())}")

    titulo = f"{model.opt.timestep*1000:.0f} ms · {integr} · {caminho.stem} — impacto em {t_contato if t_contato else float('nan'):.3f} s"
    grafico(r, tp, esp_zrep, out / "telemetria.png", titulo)
    resumo = {
        "mujoco": mujoco.__version__, "modelo": str(caminho), "integrador": integr, "timestep_s": model.opt.timestep,
        "massa_kg": massa, "t_impacto_previsto_s": tp, "t_impacto_simulado_s": t_contato, "altura_final_m": z_fim,
        "v_final": v_fim, "w_final": w_fim, "energia_inicial_J": float(e_tot[0]), "energia_final_J": float(e_tot[-1]),
        "penetracao_max_mm": float(-r["pen"].min() * 1000), "checks": [{"nome": n, "ok": bool(o), "detalhe": d} for n, o, d in checks],
        "arquivos": {k: str(p) for k, p in {"mp4": mp4, "gif": gif, "filmstrip": (out / "filmstrip.png") if quadros_fs else None,
                                             "telemetria": out / "telemetria.png"}.items() if p},
    }
    (out / "resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsaídas em {out}: " + ", ".join(sorted(p.name for p in out.iterdir())))
    return 0 if all(ok for _, ok, _ in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
