"""Verificar e VER um módulo de detalhe visual (`lab/drone_rpi/detalhes/`):

    .venv/bin/python -m lab.drone_rpi.detalhes.ver --so eletronica [--build B] [--saida DIR] [--sem-traco]

1. REGRAS — compila o build SEM detalhes e COM os módulos pedidos e confere: as peças novas têm contype = conaffinity =
   0 e grupo 1–3 (nunca 0); massa, inércia e CM de TODOS os corpos iguais; nº de corpos/juntas/sites/sensores/atuadores
   igual; e o MJCF continua exportável (`to_xml`: nada de texturas em memória);
2. FÍSICA — o mesmo voo (núcleo de firmware, pairar, arfar o corpo +20° no articulado, um tiro) com e sem os módulos:
   qpos, qvel, duty dos motores, tensão e sensores têm de ser IDÊNTICOS bit a bit;
3. IMAGENS — vistas offscreen (grupos 0–3 como no cockpit) em `--saida` (omissão: $TMPDIR/detalhes/<módulos>/):
   geral, centro, motor, braço, baixo e, no articulado, cotovelo e mira (corpo a +25°, motores de nível).
Exit 0 = regras e física OK.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

import numpy as np

_RAIZ = Path(__file__).resolve().parents[3]
_EXP = _RAIZ / "experiments" / "09_drone_hover_rl"
sys.path[:0] = [p for p in (str(_RAIZ), str(_EXP)) if p not in sys.path]


def _compilar(build: str, modulos: str):
    os.environ["DRONE_DETALHES"] = modulos
    from lab import drone_rpi as dr
    hw = dr.hardware(build)
    return dr.carregar(hw)


def conferir_regras(build: str, modulos: str) -> list[str]:
    import mujoco
    m0, _ = _compilar(build, "nenhum")
    m1, _ = _compilar(build, modulos)
    erros = []
    for campo in ("nbody", "njnt", "nq", "nv", "nu", "nsensor", "nsite", "ncam", "nlight"):
        if getattr(m0, campo) != getattr(m1, campo):
            erros.append(f"{campo}: {getattr(m0, campo)} → {getattr(m1, campo)} (detalhe não pode mudar a árvore)")
    for campo in ("body_mass", "body_inertia", "body_ipos", "body_iquat", "body_pos", "body_quat"):
        a, b = getattr(m0, campo), getattr(m1, campo)
        if a.shape != b.shape or a.tobytes() != b.tobytes():
            erros.append(f"{campo} mudou (máx |Δ| {float(np.max(np.abs(a - b))) if a.shape == b.shape else 'forma'})")
    nomes0 = {m0.geom(i).name for i in range(m0.ngeom)}
    novos = [i for i in range(m1.ngeom) if m1.geom(i).name not in nomes0]
    for i in novos:
        g = m1.geom(i)
        if m1.geom_contype[i] or m1.geom_conaffinity[i]:
            erros.append(f"{g.name}: tem contacto")
        if int(m1.geom_group[i]) not in (1, 2, 3):
            erros.append(f"{g.name}: grupo {int(m1.geom_group[i])}")
    # o MJCF tem de continuar exportável (`modelo.exportar_xml` → `hardware.py xml`): texturas em memória (buffer) não
    # se exportam no 3.15 — só as builtin (checker/gradient/flat) ou materiais simples
    os.environ["DRONE_DETALHES"] = modulos
    from lab import drone_rpi as dr
    from lab.drone_rpi import modelo as modelo_mod
    try:
        modelo_mod.construir_spec(dr.hardware(build)).to_xml()
    except Exception as erro:  # noqa: BLE001
        erros.append(f"to_xml falhou (MJCF não exportável — textura em buffer?): {str(erro)[:120]}")
    tipos = {}
    for i in novos:
        t = str(mujoco.mjtGeom(int(m1.geom_type[i]))).split(".")[-1].replace("mjGEOM_", "")
        tipos[t] = tipos.get(t, 0) + 1
    print(f"[regras] {build} · {modulos}: {len(novos)} peças novas {tipos} · ngeom {m0.ngeom} → {m1.ngeom} · "
          f"{'OK' if not erros else f'{len(erros)} ERRO(S)'}", flush=True)
    return erros


def conferir_todos_builds(modulos: str) -> list[str]:
    """Todos os builds do catálogo compilam com os módulos (o `valida_real.py` compila-os todos): partes opcionais
    (FC, câmara, sensores, arma, braços…) têm de ser opcionais nos módulos."""
    from lab import drone_rpi as dr
    erros = []
    os.environ["DRONE_DETALHES"] = modulos
    nomes = list(dr.carregar_builds()["builds"])
    for b in nomes:
        try:
            dr.carregar(dr.hardware(b))
        except Exception as erro:  # noqa: BLE001
            erros.append(f"build {b} não compila com {modulos}: {type(erro).__name__}: {str(erro)[:120]}")
    print(f"[builds] {len(nomes) - len(erros)}/{len(nomes)} builds do catálogo compilam com {modulos}", flush=True)
    return erros


def _traco(build: str, modulos: str, passos: int = 600) -> np.ndarray:
    os.environ["DRONE_DETALHES"] = modulos
    from env_real import DroneRealEnv
    import sim_view as sv
    env = DroneRealEnv(build=build, modo_acao="ctbr", comando=True, com_alvo=True, episodio_s=60.0)
    nuc = sv.NucleoClassico.criar(env)
    nuc.instalar()
    env.reset(seed=11)
    nuc.pos_reset()
    h = {"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0}
    linhas = []
    for k in range(passos):
        if k == 250 and getattr(env, "bracos", None) is not None:
            env.definir_pitch_corpo(math.radians(20.0))
        if k == 420:
            env.disparar(1)
        nuc.comando(h)
        env.step(np.zeros(4, dtype=np.float32))
        pl = env.planta
        linhas.append(np.concatenate([env.data.qpos, env.data.qvel, pl.prop.duty, [pl.v_bus],
                                      np.asarray(env.data.sensordata, dtype=float)]))
    nuc.remover()
    return np.array(linhas)


def conferir_fisica(build: str, modulos: str) -> list[str]:
    a = _traco(build, "nenhum")
    b = _traco(build, modulos)
    igual = a.shape == b.shape and a.tobytes() == b.tobytes()
    print(f"[física] {build} · {modulos}: 600 passos (pairar, arfar, tiro) com e sem detalhes → "
          f"{'IDÊNTICO bit a bit' if igual else 'DIFERENTE'}", flush=True)
    return [] if igual else [f"física diferente (máx |Δ| {float(np.max(np.abs(a - b))) if a.shape == b.shape else 'forma'})"]


def imagens(build: str, modulos: str, saida: Path) -> list[Path]:
    import imageio.v2 as iio
    import mujoco
    m, d = _compilar(build, modulos)
    from lab import drone_rpi as dr
    hw = dr.hardware(build)
    d.qpos[:3] = [0.0, 0.0, 1.0]
    d.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
    mujoco.mj_forward(m, d)
    saida.mkdir(parents=True, exist_ok=True)
    w, h = min(1600, m.vis.global_.offwidth), min(1000, m.vis.global_.offheight)
    r = mujoco.Renderer(m, h, w)
    opt = mujoco.MjvOption()
    for g in range(4):
        opt.geomgroup[g] = 1
    feitos = []

    def foto(nome, lookat, dist, az, el):
        cam = mujoco.MjvCamera()
        cam.lookat[:] = lookat
        cam.distance, cam.azimuth, cam.elevation = dist, az, el
        r.update_scene(d, camera=cam, scene_option=opt)
        caminho = saida / f"{build}_{nome}.png"
        iio.imwrite(caminho, r.render())
        feitos.append(caminho)

    c = d.xpos[m.body("drone").id].copy()
    foto("geral", c, 2.4, 135, -22)
    foto("centro", c + np.array([0, 0, 0.02]), 0.42, 150, -30)
    foto("centro_topo", c, 0.38, 90, -89)
    foto("baixo", c, 0.7, 120, 25)
    try:
        mid = m.geom("motor1").id
        pm = d.geom_xpos[mid].copy()
    except KeyError:
        pm = c + np.array([0.69, 0.69, 0.0])
    foto("motor", pm, 0.28, 150, -25)
    bid = m.body("braco1").id if hw.bracos is not None else None
    pb = d.xpos[bid].copy() if bid is not None else c + np.array([0.12, 0.12, 0.0])
    foto("braco", pb, 0.32, 160, -20)
    if hw.bracos is not None:
        pmas = d.xpos[m.body("mastro1").id].copy()
        foto("cotovelo", pmas + np.array([0, 0, 0.05]), 0.35, 150, -15)
        # pose de MIRA: corpo +25° (nariz para baixo), motores de nível (IK dos braços)
        from bracos_controlo import cinematica_inversa, geometria
        g = geometria(hw)
        q1, q2 = cinematica_inversa(math.radians(-25.0), g["r_s"], g["l1"])
        th = math.radians(25.0)
        d.qpos[3:7] = [math.cos(th / 2), 0.0, math.sin(th / 2), 0.0]
        for k in range(1, 5):
            d.qpos[m.jnt_qposadr[m.joint(f"ombro{k}").id]] = q1
            d.qpos[m.jnt_qposadr[m.joint(f"cotovelo{k}").id]] = q2
        mujoco.mj_forward(m, d)
        foto("mira", d.xpos[m.body("drone").id], 2.2, 100, -12)
        foto("mira_ombro", d.xpos[m.body("braco1").id], 0.35, 100, -10)
    r.close()
    return feitos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--so", default="todos", help="módulos (ex.: eletronica,fios) ou «todos»")
    ap.add_argument("--build", default=None, help="um build; omissão: o ativo E o articulado")
    ap.add_argument("--saida", type=Path, default=None)
    ap.add_argument("--sem-traco", action="store_true", help="não corre o voo de identidade (só regras + imagens)")
    ap.add_argument("--sem-imagens", action="store_true")
    a = ap.parse_args(argv)
    os.environ.setdefault("MUJOCO_GL", "egl")
    builds = [a.build] if a.build else ["endurance_15pol_p50b", "articulado_15pol_mn5006"]
    saida = a.saida or Path(os.environ.get("TMPDIR", "/var/tmp")) / "detalhes" / a.so.replace(",", "+")
    erros = conferir_todos_builds(a.so)
    for b in builds:
        erros += conferir_regras(b, a.so)
        if not a.sem_traco:
            erros += conferir_fisica(b, a.so)
        if not a.sem_imagens:
            for f in imagens(b, a.so, saida):
                print(f"[imagem] {f}", flush=True)
    for e in erros:
        print(f"[ERRO] {e}", flush=True)
    print("[ver] " + ("TUDO OK" if not erros else f"{len(erros)} erro(s)"), flush=True)
    return 0 if not erros else 1


if __name__ == "__main__":
    sys.exit(main())
