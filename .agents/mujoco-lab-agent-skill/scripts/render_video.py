#!/usr/bin/env python3
"""render_video.py — grava vídeo (MP4), GIF e/ou tira de quadros de QUALQUER modelo MuJoCo, sem janela (EGL).

    python3 .agents/mujoco-lab-agent-skill/scripts/render_video.py models/triangulo_invertido.xml --duration 3 --slowmo 0.5 --out out/queda
    python3 .agents/mujoco-lab-agent-skill/scripts/render_video.py robo.xml --keyframe home --ctrl "motor_a=0.3,motor_b=-0.2" --duration 5 --track torso
    python3 .agents/mujoco-lab-agent-skill/scripts/render_video.py cena.xml --qpos "0 0 1 1 0 0 0" --contacts --camera frontal --gif --sheet

Roda o modelo SEM controlador próprio (dinâmica passiva), com controles constantes opcionais (--ctrl nome=valor,… via Ctrl seguro p/ multi-entrada).
Para controle de verdade (PID, trajetórias), escreva um script com mjkit.record (ver assets/templates/*/run.py).
Saídas: <out>.mp4 (padrão) · <out>.gif (--gif) · <out>_sheet.png (--sheet) . Exit 0 ok · 2 uso/erro.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mjkit  # noqa: E402  (define MUJOCO_GL=egl antes de importar mujoco)

import mujoco  # noqa: E402
import numpy as np  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modelo")
    ap.add_argument("--duration", type=float, default=4.0, help="segundos SIMULADOS")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--slowmo", type=float, default=1.0, help="0.5 = câmera lenta")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--camera", help="nome de uma <camera> do modelo (padrão: câmera livre do modelo)")
    ap.add_argument("--track", help="nome de um corpo para a câmera livre seguir")
    ap.add_argument("--keyframe", help="nome (ou índice) de um <key> para iniciar")
    ap.add_argument("--qpos", help="qpos inicial: números separados por espaço (nq valores)")
    ap.add_argument("--ctrl", help="controles constantes: nome=valor,nome=valor")
    ap.add_argument("--contacts", action="store_true", help="desenha pontos e forças de contato")
    ap.add_argument("--no-mp4", action="store_true")
    ap.add_argument("--gif", action="store_true")
    ap.add_argument("--sheet", action="store_true", help="tira de 8 quadros")
    ap.add_argument("--out", default="out/video", help="prefixo de saída (sem extensão)")
    a = ap.parse_args()

    if not Path(a.modelo).exists():
        print(f"Erro: modelo não encontrado: {a.modelo} — Solução: passe o caminho de um .xml/.urdf/.mjb", file=sys.stderr)
        return 2
    try:
        model, data = mjkit.load(a.modelo)
    except Exception as e:  # noqa: BLE001
        print(f"Erro: não compilou: {e} — Solução: rode inspect_model.py {a.modelo} para a dica de correção", file=sys.stderr)
        return 2
    if a.keyframe is not None:
        key = int(a.keyframe) if a.keyframe.isdigit() else model.key(a.keyframe).id
        mujoco.mj_resetDataKeyframe(model, data, key)
    if a.qpos:
        q = np.array([float(x) for x in a.qpos.split()])
        if q.size != model.nq:
            print(f"Erro: --qpos tem {q.size} valores, o modelo tem nq={model.nq} — Solução: informe {model.nq} números", file=sys.stderr)
            return 2
        data.qpos[:] = q
    mujoco.mj_forward(model, data)

    ctrl = mjkit.Ctrl(model)
    fixed = {}
    if a.ctrl:
        for par in a.ctrl.split(","):
            k, v = par.split("=")
            if k.strip() not in ctrl.adr:
                print(f"Erro: atuador '{k}' não existe — Solução: use um de {sorted(ctrl.adr)}", file=sys.stderr)
                return 2
            fixed[k.strip()] = float(v)

    def controlador(m, d):
        for k, v in fixed.items():
            ctrl.set(d, k, v)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
      res = mjkit.record(model, data, controlador if fixed else None, duration=a.duration, fps=a.fps, slowmo=a.slowmo, camera=a.camera, width=a.width, height=a.height,
                       mp4=None if a.no_mp4 else out.with_suffix(".mp4"), gif=out.with_suffix(".gif") if a.gif else None,
                       sheet=out.parent / (out.name + "_sheet.png") if a.sheet else None, contacts=a.contacts, track=a.track)
    except Exception as e:  # noqa: BLE001  (câmera inexistente, resolução > <visual><global offwidth/offheight>, falha de GL…)
        print(f"Erro: o render falhou ({str(e).strip().splitlines()[0][:160]}) — Solução: confira --camera (nome existente), --width/--height ≤ <visual><global offwidth offheight> do XML e MUJOCO_GL=egl", file=sys.stderr)
        return 2
    saidas = [str(p) for p in (out.with_suffix(".mp4") if not a.no_mp4 else None, out.with_suffix(".gif") if a.gif else None,
                               out.parent / (out.name + "_sheet.png") if a.sheet else None) if p]
    print(f"{res['frames']} quadros · {res['wall_s']:.1f} s de relógio · ncon máx {int(res['log']['ncon'].max())} · saídas: {', '.join(saidas)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
