"""experiments/09_drone_hover_rl/visao.py — VISÃO do guia visual: marcador, projeção, detetor e o GATE.

A IA exterior («ver o ponto e seguir», servoing visual) precisa de VER o ponto na imagem da câmara FPV.
Este módulo tem as peças visuais — todas clássicas, como a pesquisa recomenda (`pesquisas/
relatorio-seguimento-visual-rl.md`, ponto 9: threshold de cor + centróide chega; DL só ganha sob
desfoque/occlusão):

  · `adicionar_ponto(spec)` / `posicionar_ponto(model, pos)` — uma **esfera brilhante** (magenta
    puro, raro na cena) no mundo, SEM massa e SEM colisão (nunca toca na física — regra do lab);
  · `projetar(model, data, pos_mundo, camera)` — a projeção EXATA do ponto 3D na câmara (intrínsecos do
    MuJoCo: fovy em GRAUS sempre, ponto principal ao centro);
  · `detetar_marcador(imagem)` — threshold de cor + centróide + raio/área (proxy de profundidade), tal
    como o detector clássico da pesquisa;
  · `prova_projecao_detector(...)` — o **GATE obrigatório antes de treinar** (injeção do agente-pai,
    ponto 6): reprojectar o ponto 3D conhecido e exigir **erro < 1 px** entre a projeção e o detector
    (literatura: <0,5 px excelente, <1 px bom, >2 px mau).

Convenção de imagem: `u` cresce para a direita, `v` para baixo (origem no canto superior esquerdo) — a
do OpenCV/detetor. A câmara MuJoCo olha para −z próprio, `x` próprio = direita, `y` próprio = cima.
"""
from __future__ import annotations

import math

import mujoco
import numpy as np

LIMIAR_GATE_PX = 1.0                    # px — o limiar "bom" da literatura para reprojeção

# As funções do MARCADOR vivem no `lab/camera_rpi.py` (o lab não importa do experimento) e reexportam-se
# aqui: `adicionar_ponto`/`posicionar_ponto`/`pos_ponto`/`COR_PONTO`/`RAIO_PONTO`.
from lab.camera_rpi import (
    COR_PONTO,
    RAIO_PONTO,
    adicionar_ponto,
    mocap_do_ponto,
    pos_ponto,
    posicionar_ponto,
)


# --------------------------------------------------------------------------------------------- projeção
def intrinsecos(model, camera: str = "fpv", altura_px: int = 1080) -> dict:
    """Intrínsecos pinhole da câmara do MuJoCo para uma imagem de `altura_px` (largura por aspeto do render).

    O MuJoCo não tem distorção: `f = (altura/2)/tan(fovy/2)` com o ponto principal ao centro. `cam_fovy`
    está em GRAUS sempre (verificado em 3.15 — não segue o `compiler angle`).
    """
    cid = model.camera(camera).id
    fovy = math.radians(float(model.cam_fovy[cid]))
    f = 0.5 / math.tan(fovy / 2.0) * altura_px   # EXATO do MuJoCo (f = 0.5/tan(fovy/2)·res_y)
    return {"cid": cid, "f": f, "fovy_graus": math.degrees(fovy),
            "sensores": tuple(float(x) for x in model.cam_sensorsize[cid]) if hasattr(model, "cam_sensorsize") else (0.0, 0.0),
            "intrinsecos": tuple(float(x) for x in model.cam_intrinsic[cid])}


def projetar(model, data, pos_mundo, camera: str = "fpv", largura_px: int = 1920,
             altura_px: int = 1080) -> dict:
    """Projeção EXATA de um ponto 3D na imagem: `(u, v, profundidade)`.

    `profundidade` = distância ao longo da visão (−z da câmara; negativa/None quando atrás da câmara).
    """
    cid = model.camera(camera).id
    cam_pos = np.asarray(data.cam_xpos[cid], dtype=float)
    rot = np.asarray(data.cam_xmat[cid], dtype=float).reshape(3, 3)   # colunas = eixos da câmara no mundo
    delta = np.asarray(pos_mundo, dtype=float) - cam_pos
    v0, v1, v2 = rot.T @ delta                    # referencial da câmara do MuJoCo (−z = a visão)
    if float(v2) >= 0:
        return {"u": None, "v": None, "profundidade": -float(v2), "visivel": False}
    # FÓRMULA EXATA do MuJoCo (fonte: docs/upstream/mujoco_warp/.../sensor.py `_cam_projection`):
    #   sensorsize≠0 → fx = intrinsic[0]/sensorsize[0]*res[0]; senão f = 0.5/tan(fovy/2 em rad)*res[1]
    #   pixel = (−fx·v0, fy·v1)/v2 + 0.5·res  — com v2 NEGATIVO à frente. As linhas resultantes já são
    #   da convenção do detetor (linha 0 em cima) — medido: coincide com o centróide emissivo (<1 px).
    k = intrinsecos(model, camera, altura_px)
    fx = fy = k["f"]
    sx, sy = k.get("sensores", (0.0, 0.0))
    if not math.isclose(sx, 0.0) and not math.isclose(sy, 0.0):
        i0, i1 = k.get("intrinsecos", (0.0, 0.0))[:2]
        fx = i0 / sx * largura_px
        fy = i1 / sy * altura_px
    u = -fx * float(v0) / float(v2) + 0.5 * largura_px
    v = fy * float(v1) / float(v2) + 0.5 * altura_px
    profundidade = -float(v2)
    visivel = 0.0 <= u < largura_px and 0.0 <= v < altura_px
    return {"u": u, "v": v, "profundidade": profundidade, "visivel": bool(visivel)}


# --------------------------------------------------------------------------------------------- detetor
def detetar_marcador(imagem) -> dict:
    """Detector CLÁSSICO da pesquisa: threshold de cor + centróide + área/raio (proxy de profundidade).

    `imagem` = array (H, W, 3) uint8 (o render do MuJoCo). Devolve `{visivel, u, v, area_px, raio_px}`
    com `u,v` em píxeis da imagem (origem em cima à esquerda) e `raio_px = sqrt(area/π)` — é este raio
    que a IA usa como proxy de profundidade (quanto maior, mais perto).
    """
    rgb = np.asarray(imagem)
    if rgb.ndim != 3:
        raise ValueError(f"esperava uma imagem (H, W, 3), recebi {getattr(rgb, 'shape', None)}")
    mascara = (rgb[:, :, 0] > 180) & (rgb[:, :, 2] > 180) & (rgb[:, :, 1] < 90)
    n = int(mascara.sum())
    if n == 0:
        return {"visivel": False, "u": None, "v": None, "area_px": 0, "raio_px": 0.0}
    ys, xs = np.nonzero(mascara)
    return {"visivel": True, "u": float(xs.mean()), "v": float(ys.mean()),
            "area_px": n, "raio_px": math.sqrt(n / math.pi)}


# ----------------------------------------------------------------------------------------------- GATE
def prova_projecao_detector(model, data, posicoes, camera: str = "fpv", largura_px: int = 1920,
                            altura_px: int = 1080, render=None) -> dict:
    """GATE obrigatório antes de treinar: projeção exata × detetor real, erro médio e máximo < 1 px.

    Para cada posição do marcador: posiciona, renderiza, deteta e reprojecta; o erro é a distância em
    píxeis entre o centróide DETETADO e a projeção do centro 3D. Devolve `{ok, erros_px, erro_medio,
    erro_max}` — `ok` exige `erro_max < LIMIAR_GATE_PX`.
    """
    erros = []
    for pos in posicoes:
        posicionar_ponto(model, data, pos)
        mujoco.mj_forward(model, data)      # o mocap entra em `geom_xpos` no forward (é ele que a cena
        imagem = render(largura_px, altura_px)   # renderiza)
        det = detetar_marcador(imagem)
        proj = projetar(model, data, pos, camera=camera, largura_px=largura_px, altura_px=altura_px)
        if not det["visivel"] or not proj["visivel"]:
            erros.append(float("inf"))
            continue
        erros.append(float(math.hypot(det["u"] - proj["u"], det["v"] - proj["v"])))
    finitos = [e for e in erros if math.isfinite(e)]
    erro_medio = float(np.mean(finitos)) if finitos else float("inf")
    erro_max = float(np.max(erros)) if erros else float("inf")
    return {"ok": bool(finitos) and len(finitos) == len(posicoes) and erro_max < LIMIAR_GATE_PX,
            "erros_px": erros, "erro_medio": erro_medio, "erro_max": erro_max,
            "limiar_px": LIMIAR_GATE_PX}


__all__ = [
    "COR_PONTO",
    "LIMIAR_GATE_PX",
    "RAIO_PONTO",
    "adicionar_ponto",
    "detetar_marcador",
    "intrinsecos",
    "mocap_do_ponto",
    "pos_ponto",
    "posicionar_ponto",
    "projetar",
    "prova_projecao_detector",
]
