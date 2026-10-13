#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/avaliar_bola.py — MODO «SEGUIR A BOLA»: a bola anda ao acaso e o drone tem de a manter CENTRADA
na imagem da câmara FPV (fixa ao corpo, sem gimbal). Aqui MEDE-SE — antes × depois × tracker PPO — no mesmo protocolo e sementes.

PROTOCOLO (um episódio = uma semente × uma velocidade × um caminho de câmara)
  · planta: `DroneRealEnvNucleo` em modo cascata (o C++ do firmware manda em tudo e vê SÓ sensores), SEM vento, sem DR;
  · 0 → 4 s: descola e segura (modo VELOCIDADE), bola PARADA 2 m à frente; aos 4 s liga-se o OLHAR e a bola começa a mexer:
    `env.definir_trajetoria_ponto("aleatorio", vel)` (velocidade de Ornstein–Uhlenbeck com teto `vel`, reprodutível pela semente
    do episódio — a bola não vê o drone, por isso a trajetória é A MESMA para todos os controladores);
  · 4 → 8 s: aquisição (fora das métricas); 8 → 38 s: JANELA DE MEDIDA (30 s);
  · câmara do detetor: mono QVGA 320×240 a 30 Hz, RENDERIZADA (EGL) + detetor C++ no laço, com a latência do caminho —
    `pi_116ms` (build ativo p50b, pipeline Pi) e `arduino_21ms` (build `endurance_15pol_arduino`, DCMI);
  · velocidades da bola 0,3 / 0,5 / 0,8 m/s (o TETO; a média medida é ≈ 0,76× o teto e a aceleração RMS 0,26 / 0,45 /
    0,73 m/s²); 12 sementes de AVALIAÇÃO (6200…6211) que NUNCA entram na afinação (`treinar_bola.py` usa 8100…);
  · o `u/r` de guinada é o identificado pela B0 no build p50b, nos DOIS builds — é o que o runner da interface faz (o do
    build Arduino, identificado à parte pelo `avaliar_nucleo.py`, é 0,4306: −1,7 %).
REPRODUTIBILIDADE (medida): a BOLA repete bit a bit (gerador próprio, semeado no `reset`); o VOO repete entre processos só até
ao arredondamento (o mesmo episódio em dois processos: 2,092478206334188° vs 2,0924782063341607°, com a câmara em modo
projeção) e, de vez em quando, essa diferença é amplificada por um evento discreto do filtro — com a câmara renderizada, 1
episódio em 4 mudou ≈ 0,1° no RMS (os outros repetiram os 16 algarismos). A origem do arredondamento não foi isolada.

MÉTRICA DO DONO — «bola centrada NA IMAGEM da câmara de bordo». A verdade vem da pose EXATA da câmara `fpv` (cópia privada do
estado + `mj_kinematics`/`mj_camlight`; a mesma matemática do `visao.projetar`), por isso inclui o roll/pitch do drone:
    e_h = atan(x_c / z_c)  (+ = bola à DIREITA do centro)     e_v = atan(y_c / z_c)  (+ = ACIMA do centro)
    e   = ângulo entre o eixo óptico e a bola = atan(√(x_c² + y_c²)/z_c)          px = f·tan(·), f da câmara QVGA do detetor
em graus e em px — mediana, RMS, p95 e máximo, horizontal e vertical separados e a norma. Fora do campo o erro em px SATURA na meia
imagem (160 / 120 / 200 px): perder a bola nunca melhora o número. Mais: fração do tempo com a bola no campo (centro dentro
da imagem), fração em A_SEGUIR, erro de distância |D − d*|, fração com a guinada saturada (no teto de taxa e em taxa OU slew),
quedas, inclinações e o caminho percorrido pelo drone.

VARIANTES
  · `depois`  — a lei POR OMISSÃO do firmware (`visao::config_padrao` + o que `sitl.config_de_hardware` põe): é a que o runner usa;
  · `antes`   — a lei de antes desta atividade (guinada + v_z + v_x, v_y = 0), reposta por `seguidor_antes()` (= o
                `visao::config_versao1` do C++);
  · `ppo`     — o tracker PPO existente (`out/real_1950_seguimento_final/final.zip` sobre a IA-voo congelada, `env_seguimento`),
                na latência com que treinou (116 ms) e na mínima do seu laço de 25 Hz (40 ms), no build p50b.

    .venv/bin/python experiments/09_drone_hover_rl/avaliar_bola.py                  # tudo → out/bola/avaliacao.json
    .venv/bin/python experiments/09_drone_hover_rl/avaliar_bola.py --rapido         # 2 sementes (fumo)
    .venv/bin/python experiments/09_drone_hover_rl/avaliar_bola.py --variantes depois --velocidades 1.0,1.2 --sem-teto
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]
from lab import mjkit  # noqa: F401, I001  (MUJOCO_GL=egl antes de `import mujoco`)

import numpy as np

SAIDA_JSON = _AQUI / "out" / "bola" / "avaliacao.json"
JSON_B0 = _AQUI / "out" / "classico" / "avaliacao.json"
PILOTO_RL = _AQUI / "out" / "real_1950_voo_final" / "final.zip"
TRACKER_PPO = _AQUI / "out" / "real_1950_seguimento_final" / "final.zip"
BUILD_ARDUINO = "endurance_15pol_arduino"

SEMENTES_AVALIACAO = tuple(range(6200, 6212))     # NUNCA usadas para afinar (o `treinar_bola.py` recusa-as)
SEMENTES_AFINACAO = tuple(range(8100, 8112))      # as do `treinar_bola.py`
VELOCIDADES = (0.3, 0.5, 0.8)                     # m/s — o teto de velocidade da bola (banda do desenho do dono)
CAMINHOS = {"pi_116ms": (None, 0.116), "arduino_21ms": (BUILD_ARDUINO, 0.021)}   # nome → (build | None = o da política, latência s)
LARGURA, ALTURA, FPS = 320, 240, 30.0             # a câmara mono do detetor (a do runner e do `avaliar_nucleo.py`)
VENTO_DIRECAO_GRAUS = 90.0                        # o vento do `--ventos` sopra de lado (para +y), como no `avaliar_vento.py`
T_OLHAR_S = 4.0                                   # descola e segura 4 s antes de ligar o OLHAR; a bola começa a mexer aqui
T_AQUISICAO_S = 4.0                               # as métricas ignoram os primeiros 4 s de OLHAR
T_MEDIDA_S = 30.0                                 # janela de medida
FLAG_SATUROU_YAW = 256                            # visao_tipos.hpp: kFlagSaturouYaw (teto de taxa OU slew)
FLAG_SATUROU_LATERAL = 512                        # kFlagSaturouLateral (v_y no teto ou em slew)

CHAVES = ("centro_mediana_graus", "h_mediana_graus", "v_mediana_graus", "centro_mediana_px", "h_mediana_px", "v_mediana_px",
          "centro_rms_graus", "centro_p95_graus", "centro_max_graus", "h_rms_graus", "h_p95_graus", "h_max_graus",
          "v_rms_graus", "v_p95_graus", "v_max_graus", "centro_rms_px", "centro_p95_px", "centro_max_px", "h_rms_px", "h_p95_px",
          "h_max_px", "v_rms_px", "v_p95_px", "v_max_px", "frac_fov", "frac_a_seguir", "frac_frames_validos", "dist_erro_rms",
          "dist_media", "dist_min", "dist_max", "frac_fora_banda", "frac_yaw_teto", "frac_yaw_saturada", "frac_lateral_saturada",
          "roll_rms_graus", "pitch_rms_graus", "caminho_drone_m", "vel_bola_media", "los_taxa_p95", "z_min", "custo")


# ------------------------------------------------------------------------------------------------ a verdade na imagem
class Verdade:
    """Erro de centragem EXATO na câmara `fpv`: cópia privada de (qpos, mocap) → cinemática → pose da câmara → bola no referencial
    da câmara. Não toca no `data` da simulação (um `mj_forward` no meio do laço mudaria o que os sensores leem)."""

    def __init__(self, model, largura: int = LARGURA, altura: int = ALTURA, camera: str = "fpv"):
        import mujoco
        self.mj, self.model = mujoco, model
        self.local = mujoco.MjData(model)
        self.cid = int(model.camera(camera).id)
        self.largura, self.altura = int(largura), int(altura)
        self.f_px = 0.5 * altura / math.tan(math.radians(float(model.cam_fovy[self.cid])) / 2.0)

    def medir(self, data, ponto) -> tuple:
        """`(e_h, e_v, e, u_px, v_px, no_campo, distância)` — ângulos em rad; (u, v) = offset em px face ao CENTRO, saturado na
        meia imagem fora do campo; `no_campo` = centro da bola dentro da imagem."""
        mj, loc = self.mj, self.local
        loc.qpos[:] = data.qpos
        loc.mocap_pos[:] = data.mocap_pos
        loc.mocap_quat[:] = data.mocap_quat
        mj.mj_kinematics(self.model, loc)
        mj.mj_camlight(self.model, loc)
        rot = loc.cam_xmat[self.cid].reshape(3, 3)            # colunas = eixos da câmara no mundo (x dir., y cima, −z visão)
        d = rot.T @ (np.asarray(ponto, dtype=float) - loc.cam_xpos[self.cid])
        xc, yc, zc = float(d[0]), float(d[1]), -float(d[2])
        dist = math.sqrt(xc * xc + yc * yc + zc * zc)
        e = math.atan2(math.hypot(xc, yc), zc)
        meio_u, meio_v = 0.5 * self.largura, 0.5 * self.altura
        if zc > 1e-6:
            e_h, e_v = math.atan(xc / zc), math.atan(yc / zc)
            u, v = self.f_px * xc / zc, -self.f_px * yc / zc
            no_campo = abs(u) < meio_u and abs(v) < meio_v
        else:                                                   # atrás da câmara: o erro por eixo satura a 90°
            e_h, e_v = math.copysign(0.5 * math.pi, xc), math.copysign(0.5 * math.pi, yc)
            u, v, no_campo = math.copysign(meio_u, xc), -math.copysign(meio_v, yc), False
        if not no_campo:
            u, v = max(-meio_u, min(meio_u, u)), max(-meio_v, min(meio_v, v))
        return e_h, e_v, e, u, v, no_campo, dist


def seguidor_antes() -> dict:
    """A LEI DE ANTES desta atividade (versão 1: guinada PI+FF, v_z, v_x de distância, v_y = 0, sem compensações) como campos
    de `ConfigSeguidor` a sobrepor à Config por omissão — lidos do C++ (`visao::config_versao1`, uma só fonte da verdade). É
    assim que o «antes» continua mensurável depois de os defaults mudarem (o `teste_bola.py` prova-o contra os números do C++
    original)."""
    import ctypes

    import sitl
    bib = sitl.biblioteca_padrao()
    padrao = bib.config_seguidor_padrao(LARGURA, ALTURA, 60.0)
    v1 = bib.ConfigSeguidor.from_buffer_copy(padrao)
    fn = bib.lib.seguidor_config_versao1
    fn.argtypes, fn.restype = [ctypes.POINTER(bib.ConfigSeguidor)], None
    fn(ctypes.byref(v1))
    return {n: getattr(v1, n) for n, _t in v1._fields_ if getattr(v1, n) != getattr(padrao, n)}


def u_yaw_identificado() -> float | None:
    """O `u/r` de guinada IDENTIFICADO pela B0 no simulador (o MESMO que o runner usa, para qualquer build)."""
    if JSON_B0.is_file():
        return float(json.loads(JSON_B0.read_text(encoding="utf-8"))["identificacao_yaw"]["u_yaw_por_taxa"])
    return None


def dados_hardware() -> dict:
    hw = PILOTO_RL.parent / "hardware.json"
    return json.loads(hw.read_text(encoding="utf-8")) if hw.is_file() else {}


def _rms(x) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else float("nan")


def metricas(reg: np.ndarray, f_px: float, d_alvo: float, yaw_teto: float, caiu: bool, t_ini: float | None = None,
             t_fim: float | None = None) -> dict:
    """Métricas da janela de medida. Colunas de `reg`: t, e_h, e_v, e, u, v, no_campo, dist, estado, yaw_ref, flags_seguidor,
    roll, pitch, x, y, z, bx, by, bz, az_mundo (linha de vista verdadeira)."""
    t_ini = T_OLHAR_S + T_AQUISICAO_S if t_ini is None else t_ini
    t_fim = t_ini + T_MEDIDA_S if t_fim is None else t_fim
    m = (reg[:, 0] >= t_ini - 1e-9) & (reg[:, 0] < t_fim - 1e-9) if len(reg) else np.zeros(0, dtype=bool)
    if caiu or not m.any():
        return {"terminou": True, "t_fim": float(reg[-1, 0]) if len(reg) else 0.0, "custo": CUSTO_QUEDA}
    r = reg[m]
    g = np.degrees
    meio_d = math.hypot(0.5 * LARGURA, 0.5 * ALTURA)
    px = np.minimum(np.hypot(r[:, 4], r[:, 5]), meio_d)
    out = {"terminou": False}
    for nome, ang, pix in (("centro", r[:, 3], px), ("h", r[:, 1], r[:, 4]), ("v", r[:, 2], r[:, 5])):
        a = np.abs(g(ang))
        out[f"{nome}_rms_graus"], out[f"{nome}_p95_graus"], out[f"{nome}_max_graus"] = _rms(a), float(np.percentile(a, 95)), float(a.max())
        out[f"{nome}_mediana_graus"] = float(np.median(a))
        p = np.abs(pix)
        out[f"{nome}_mediana_px"] = float(np.median(p))
        out[f"{nome}_rms_px"], out[f"{nome}_p95_px"], out[f"{nome}_max_px"] = _rms(p), float(np.percentile(p, 95)), float(p.max())
    out["h_medio_graus"], out["v_medio_graus"] = float(g(r[:, 1]).mean()), float(g(r[:, 2]).mean())
    out["frac_fov"] = float(np.mean(r[:, 6]))
    out["frac_a_seguir"] = float(np.mean(r[:, 8] == 0))
    out["dist_erro_rms"] = _rms(r[:, 7] - d_alvo)
    out["dist_media"], out["dist_min"], out["dist_max"] = float(r[:, 7].mean()), float(r[:, 7].min()), float(r[:, 7].max())
    out["frac_fora_banda"] = float(np.mean((r[:, 7] < BANDA_DIST[0] * d_alvo) | (r[:, 7] > BANDA_DIST[1] * d_alvo)))
    out["frac_yaw_teto"] = float(np.mean(np.abs(r[:, 9]) >= 0.999 * yaw_teto)) if yaw_teto > 0 else float("nan")
    out["frac_yaw_saturada"] = float(np.mean((r[:, 10].astype(np.int64) & FLAG_SATUROU_YAW) != 0))
    out["frac_lateral_saturada"] = float(np.mean((r[:, 10].astype(np.int64) & FLAG_SATUROU_LATERAL) != 0))
    out["roll_rms_graus"], out["pitch_rms_graus"] = _rms(g(r[:, 11])), _rms(g(r[:, 12]))
    out["roll_max_graus"], out["pitch_max_graus"] = float(np.abs(g(r[:, 11])).max()), float(np.abs(g(r[:, 12])).max())
    out["caminho_drone_m"] = float(np.sum(np.hypot(np.diff(r[:, 13]), np.diff(r[:, 14]))))
    dt = float(np.median(np.diff(r[:, 0])))
    vb = np.linalg.norm(np.diff(r[:, 16:19], axis=0), axis=1) / dt
    out["vel_bola_media"], out["vel_bola_max"] = float(vb.mean()), float(vb.max())
    los = np.abs(np.gradient(np.unwrap(r[:, 19]), r[:, 0]))
    out["los_taxa_p95"], out["los_taxa_max"] = float(np.percentile(los, 95)), float(los.max())
    out["z_min"], out["z_max"] = float(r[:, 15].min()), float(r[:, 15].max())
    out["custo"] = custo(out)
    return out


# custo escalar de UM episódio (o que o `treinar_bola.py` minimiza; aqui só se reporta). O objetivo do dono é a CENTRAGEM (RMS +
# cauda, em graus); a distância entra como restrição branda (a bola tem de ficar na banda em que o detetor a vê e longe das
# hélices) e perder a bola ou cair custa muito. Unidade ≈ graus de erro de centragem.
CUSTO_QUEDA = 500.0
PESO_P95, PESO_DIST, PESO_BANDA, PESO_FOV, PESO_SEGUIR = 0.25, 2.0, 20.0, 100.0, 5.0
BANDA_DIST = (0.6, 1.6)             # × d*: fora de [0,9; 2,4] m (d* = 1,5 m) conta como «fora da banda»


def custo(m: dict) -> float:
    """J = e_RMS + 0,25·e_p95 [°] + 2·|D − d*|_RMS [m] + 20·(fração fora da banda de distância) + 100·(1 − fração no campo)
    + 5·(1 − fração em A_SEGUIR); queda = 500."""
    if m.get("terminou"):
        return CUSTO_QUEDA
    return float(m["centro_rms_graus"] + PESO_P95 * m["centro_p95_graus"] + PESO_DIST * m["dist_erro_rms"]
                 + PESO_BANDA * m.get("frac_fora_banda", 0.0) + PESO_FOV * (1.0 - m["frac_fov"])
                 + PESO_SEGUIR * (1.0 - m["frac_a_seguir"]))


# ------------------------------------------------------------------------------------------------ um episódio
def _linha(t, med, estado, yaw_ref, flags, d, bola, cam_az) -> tuple:
    return (t, med[0], med[1], med[2], med[3], med[4], 1.0 if med[5] else 0.0, med[6], estado, yaw_ref, flags, d["phi"], d["theta"],
            d["x"], d["y"], d["z"], bola[0], bola[1], bola[2], cam_az)


def episodio_classico(job: dict) -> dict:
    """OLHAR do núcleo C++ com a bola `aleatorio` (ou `job["modo"]`): câmara renderizada + detetor C++ + IBVS + cascata."""
    import avaliar_nucleo as an
    import sitl_camera
    from env_real import build_do_hardware
    sitl_camera.MODO_OMISSAO = job.get("camera_modo", "render")     # "projecao" = sem GPU (só o treino; a avaliação renderiza)
    dados = dados_hardware()
    build = job.get("build") or build_do_hardware(dados)[0]
    seed, vel = int(job["seed"]), float(job["vel"])
    t_medida = float(job.get("t_medida", T_MEDIDA_S))
    T = T_OLHAR_S + T_AQUISICAO_S + t_medida
    camera = {"largura": LARGURA, "altura": ALTURA, "fps": FPS, "latencia_s": float(job["latencia"])}
    if job.get("seguidor"):
        camera["seguidor"] = dict(job["seguidor"])
    env = an.criar_env_nucleo(dados, dr=bool(job.get("dr", False)), episodio_s=T + 1.0, u_yaw=job.get("u_yaw"), com_alvo=True,
                              build=build, cascata={"camera": camera, "ganhos_kw": job.get("ganhos_kw") or {}})
    try:
        env.ponto_modo, env.ponto_vel = "parado", vel
        env.camera_sitl.semente = seed                           # o ruído do modo projeção muda com o episódio
        env.reset(seed=seed)
        # VENTO (opcional): o gerador do cockpit (`vento_natural.VentoNatural`), a soprar desde a descolagem, pareado
        # pela semente — o mesmo vento para todas as variantes. `vento` = intensidade média W (m/s); 0 = ar parado.
        gerador = None
        if float(job.get("vento") or 0.0) > 0.0:
            import vento_natural
            gerador = vento_natural.VentoNatural(semente=seed)
            gerador.definir(True, float(job["vento"]), bool(job.get("vento_aleatorio", True)),
                            float(job.get("vento_direcao", VENTO_DIRECAO_GRAUS)))
        verdade = Verdade(env.model)
        cfg = env.nucleo.cfg
        d_alvo, yaw_teto = float(cfg.seguidor.dist_alvo_m), float(cfg.cascata.taxa_yaw_max)
        n, k_olhar = round(T / env.dt_decisao), round(T_OLHAR_S / env.dt_decisao)
        acao = np.zeros(4, dtype=np.float32)
        linhas, caiu = [], False
        diag = [] if job.get("series") else None
        for k in range(n):
            if k == k_olhar:
                env.definir_trajetoria_ponto(job.get("modo", "aleatorio"), vel=vel)
                if job.get("sem_teto"):                      # estudo do limite físico: velocidades acima da banda do desenho
                    env.ponto_vel = vel
            env.fc.definir_comando({"modo": "olhar"} if k >= k_olhar else {})
            if gerador is not None:
                env.definir_vento(*vento_natural.polar_do_vetor(gerador.passo(env.dt_decisao)))
            _o, _r, term, _tr, _i = env.step(acao)
            d = env._derivados()
            s = env.nucleo.saida
            med = verdade.medir(env.data, env.ponto_alvo)
            cam = verdade.local.cam_xpos[verdade.cid]
            az = math.atan2(env.ponto_alvo[1] - cam[1], env.ponto_alvo[0] - cam[0])
            linhas.append(_linha((k + 1) * env.dt_decisao, med, int(s.seguidor.estado), float(s.yaw_taxa_ref),
                                 int(s.seguidor.flags), d, env.ponto_alvo, az))
            if diag is not None:                             # sinais internos do núcleo (só para diagnóstico)
                g = s.seguidor
                diag.append((g.vx, g.vy, g.vz, g.yaw_taxa, g.e_psi, g.e_elev, g.dist, g.taxa_bearing, g.acel_bearing, s.vx, s.vy,
                             s.vz, s.roll, s.pitch, s.psi, s.h, float(d["v_vec"][0]), float(d["v_vec"][1]), float(d["v_vec"][2]),
                             d["yaw"], float(s.flags), g.t_sem_det_s, float(g.n_aceites), float(g.n_rejeitadas),
                             g.v_alvo_rad, g.v_alvo_tan, g.v_alvo_vert, g.e_h_cam, g.e_v_cam))
            if term:
                caiu = True
                break
        reg = np.array(linhas)
        out = metricas(reg, verdade.f_px, d_alvo, yaw_teto, caiu)
        cam_reg = np.array(env.camera_sitl.registo) if env.camera_sitl.registo else np.zeros((0, 5))
        mj = cam_reg[:, 0] >= T_OLHAR_S + T_AQUISICAO_S if len(cam_reg) else np.zeros(0, dtype=bool)
        out["frac_frames_validos"] = float(np.mean(cam_reg[mj, 1])) if mj.any() else float("nan")
        out["yaw_teto"], out["yaw_acel_teto"] = yaw_teto, float(cfg.cascata.acel_yaw_max)
        out["f_px"], out["fovy_graus"] = verdade.f_px, float(env.model.cam_fovy[verdade.cid])
        if job.get("series"):
            out["series"], out["diag"] = reg, np.array(diag)
        return out
    finally:
        env.close()


def episodio_ppo(job: dict) -> dict:
    """O tracker PPO existente (IA-2 → v_ref → IA-voo congelada → FC) na MESMA bola e na mesma janela: 2 s de aquecimento do
    próprio env + 2 s com o tracker e a bola parada; aos 4 s a bola começa a mexer; medida de 8 a 38 s. A câmara é a `fpv` do
    build ativo; a verdade mede-se em px da câmara QVGA do detetor (mesmo FoV: os graus são os mesmos)."""
    import env_seguimento as es
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1)
    seed, vel = int(job["seed"]), float(job["vel"])
    t_medida = float(job.get("t_medida", T_MEDIDA_S))
    T = T_OLHAR_S + T_AQUISICAO_S + t_medida
    env = es.EnvSeguimento(PILOTO_RL, episodio_s=T + 10.0, latencia_s=float(job["latencia"]), trajetoria="parado", vel_ponto=vel)
    guia = PPO.load(str(job.get("tracker") or TRACKER_PPO), device="cpu")
    obs, _info = env.reset(seed=seed)
    interior = env.env
    verdade = Verdade(interior.model)
    t = 100 * interior.dt_decisao                               # o aquecimento do `EnvSeguimento.reset`
    linhas, caiu, movendo = [], False, False
    while t < T - 1e-9:
        if not movendo and t >= T_OLHAR_S - 1e-9:
            env.definir_trajetoria_ponto(job.get("modo", "aleatorio"), vel=vel)
            if job.get("sem_teto"):
                interior.ponto_vel = vel
            movendo = True
        a, _ = guia.predict(obs, deterministic=True)
        obs, _r, term, _trunc, _i = env.step(a)
        t += env.dt_guia
        d = interior._derivados()
        med = verdade.medir(interior.data, interior.ponto_alvo)
        cam = verdade.local.cam_xpos[verdade.cid]
        az = math.atan2(interior.ponto_alvo[1] - cam[1], interior.ponto_alvo[0] - cam[0])
        linhas.append(_linha(t, med, 0, 0.0, 0, d, interior.ponto_alvo, az))
        if term:
            caiu = True
            break
    reg = np.array(linhas)
    out = metricas(reg, verdade.f_px, es.D_ESTRELA, 0.0, caiu)
    out["frac_frames_validos"] = float("nan")
    out["f_px"], out["fovy_graus"] = verdade.f_px, float(interior.model.cam_fovy[verdade.cid])
    if job.get("series"):
        out["series"] = reg
    env.fechar()
    return out


def tarefa(job: dict) -> dict:
    """Um episódio → métricas (função de topo: serializável para o `multiprocessing`)."""
    t0 = time.perf_counter()
    out = episodio_ppo(job) if job.get("kind") == "ppo" else episodio_classico(job)
    out.update({"seed": job["seed"], "vel": job["vel"], "variante": job.get("variante"), "caminho": job.get("caminho"),
                "parede_s": time.perf_counter() - t0})
    return out


# ------------------------------------------------------------------------------------------------ execução e agregação
T_LIMITE_EPISODIO_S = 900.0        # s de parede: um episódio que não responde nisto é um ERRO (não se espera para sempre)


def _init_worker() -> None:
    os.environ.setdefault("OMP_NUM_THREADS", "1")


def _init_worker_ppo() -> None:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MUJOCO_GL", "egl")
    with contextlib.suppress(ImportError):
        import torch
        torch.set_num_threads(1)


def _correr_pool(jobs: list[dict], n_jobs: int, contexto, inicializador) -> list[dict]:
    """Os episódios num pool de processos, com limite de tempo por episódio: um que não responda mata o pool e levanta
    `RuntimeError` a dizer qual foi (medido 1×: 3 episódios do tracker PPO presos a 98 % de CPU num pool `fork`)."""
    ex = ProcessPoolExecutor(max_workers=min(n_jobs, len(jobs)), mp_context=contexto, initializer=inicializador)
    futs = [ex.submit(tarefa, j) for j in jobs]
    try:
        return [f.result(timeout=T_LIMITE_EPISODIO_S) for f in futs]
    except FutureTimeout as erro:
        presos = [{k: j.get(k) for k in ("variante", "caminho", "vel", "seed")} for j, f in zip(jobs, futs, strict=True) if not f.done()]
        for p in list(getattr(ex, "_processes", {}).values()):
            with contextlib.suppress(Exception):
                p.kill()
        raise RuntimeError(f"episódio(s) sem resposta em {T_LIMITE_EPISODIO_S:g} s: {presos[:6]}") from erro
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def executar(jobs: list[dict], n_jobs: int) -> list[dict]:
    """Corre os episódios em paralelo e devolve as métricas na ordem dos `jobs`. Os da lei C++ vão num pool `fork` (herdam a
    .so já carregada); os do tracker PPO num pool `spawn` à parte (interpretadores limpos: torch/onnxruntime não se dão com
    processos bifurcados que já têm contexto EGL e a .so do núcleo)."""
    if n_jobs <= 1 or len(jobs) <= 1:
        return [tarefa(j) for j in jobs]
    import multiprocessing
    res: list = [None] * len(jobs)
    for ppo, contexto, inic in ((False, None, _init_worker), (True, multiprocessing.get_context("spawn"), _init_worker_ppo)):
        idx = [i for i, j in enumerate(jobs) if (j.get("kind") == "ppo") == ppo]
        if idx:
            for i, r in zip(idx, _correr_pool([jobs[i] for i in idx], n_jobs, contexto, inic), strict=True):
                res[i] = r
    return res


def jobs_variante(variante: str, sementes, velocidades=VELOCIDADES, caminhos=CAMINHOS, seguidor: dict | None = None,
                  ventos=(0.0,), **extra) -> list[dict]:
    """Os episódios de uma variante: `antes` | `depois` | `ppo` | (qualquer nome + `seguidor` = campos a sobrepor).

    `ventos` = intensidades médias (m/s) do vento ALEATÓRIO do cockpit a soprar de lado durante todo o episódio; cada
    W > 0 acrescenta um caminho `<caminho>_vento<W>` (só nas variantes clássicas — o tracker PPO já perde em ar parado).
    """
    u_yaw = u_yaw_identificado()
    jobs = []
    if variante == "ppo":
        for nome, lat in (("ppo_116ms", 0.116), ("ppo_40ms", 0.021)):
            jobs += [{"kind": "ppo", "variante": variante, "caminho": nome, "latencia": lat, "vel": v, "seed": s, **extra}
                     for v in velocidades for s in sementes]
        return jobs
    seg = seguidor_antes() if variante == "antes" else dict(seguidor or {})
    for nome, (build, lat) in caminhos.items():
        for w in ventos:
            rotulo = nome if not w else f"{nome}_vento{w:g}"
            jobs += [{"kind": "classico", "variante": variante, "caminho": rotulo, "build": build, "latencia": lat,
                      "u_yaw": u_yaw, "vel": v, "seed": s, "seguidor": seg, "vento": float(w), **extra}
                     for v in velocidades for s in sementes]
    return jobs


def agregar(jobs: list[dict], res: list[dict]) -> dict:
    """Por (variante, caminho, velocidade): média, desvio-padrão (entre sementes), pior semente, n e quedas — as médias são sobre
    as sementes que NÃO caíram; as quedas contam-se à parte (critério de aceitação: 0)."""
    grupos: dict = {}
    for j, r in zip(jobs, res, strict=True):
        grupos.setdefault((j["variante"], j["caminho"], float(j["vel"])), []).append(r)
    out: dict = {}
    for (var, cam, vel), rs in grupos.items():
        vivos = [r for r in rs if not r.get("terminou")]
        g = {"n": len(rs), "quedas": len(rs) - len(vivos), "sementes_com_queda": sorted(r["seed"] for r in rs if r.get("terminou")),
             "sementes": sorted(r["seed"] for r in rs)}
        for c in CHAVES:
            x = np.array([r[c] for r in vivos if r.get(c) is not None and np.isfinite(r[c])], dtype=float)
            if not len(x):
                continue
            pior_alto = c not in ("frac_fov", "frac_a_seguir", "frac_frames_validos", "dist_min", "z_min")
            i = int(np.argmax(x) if pior_alto else np.argmin(x))
            g[c] = {"media": float(x.mean()), "dp": float(x.std(ddof=1)) if len(x) > 1 else 0.0, "pior": float(x[i]),
                    "mediana": float(np.median(x))}
        g["por_semente"] = [{"seed": r["seed"], "terminou": bool(r.get("terminou")),
                             **{c: r.get(c) for c in CHAVES}} for r in sorted(rs, key=lambda r: r["seed"])]
        out.setdefault(var, {}).setdefault(cam, {})[f"{vel:g}"] = g
    return out


def limpar(o):
    """Serializável: numpy → python, NaN/inf → None."""
    if isinstance(o, dict):
        return {str(k): limpar(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [limpar(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return limpar(o.tolist())
    return o


def imprimir(ag: dict) -> None:
    def c(g, chave, casas=2, m=1.0):
        x = g.get(chave)
        return "—" if x is None else f"{m * x['media']:.{casas}f} ± {m * x['dp']:.{casas}f}"

    def pior(g, chave, casas=1, m=1.0):
        x = g.get(chave)
        return "—" if x is None else f"{m * x['pior']:.{casas}f}"

    print("\n| variante · caminho · bola | centragem mediana (°) | RMS (°) | p95 (°) | pior sem. RMS (°) | H RMS (°) | V RMS (°) | RMS (px) | p95 (px) | "
          "no campo (%) | A_SEGUIR (%) | \\|D−d*\\| RMS (m) | guinada no teto / saturada (%) | quedas |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for var, por_cam in ag.items():
        for cam, por_vel in por_cam.items():
            for vel, g in por_vel.items():
                print(f"| {var} · {cam} · {vel} m/s | {c(g, 'centro_mediana_graus')} | {c(g, 'centro_rms_graus')} | {c(g, 'centro_p95_graus')} | "
                      f"{pior(g, 'centro_rms_graus', 2)} | {c(g, 'h_rms_graus')} | {c(g, 'v_rms_graus')} | {c(g, 'centro_rms_px', 1)} | "
                      f"{c(g, 'centro_p95_px', 1)} | {c(g, 'frac_fov', 1, 100)} | {c(g, 'frac_a_seguir', 1, 100)} | "
                      f"{c(g, 'dist_erro_rms', 3)} | {c(g, 'frac_yaw_teto', 1, 100)} / {c(g, 'frac_yaw_saturada', 1, 100)} | "
                      f"{g['quedas']}/{g['n']} |")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--rapido", action="store_true", help="2 sementes (fumo)")
    p.add_argument("--sementes", type=int, default=len(SEMENTES_AVALIACAO), help="quantas sementes de AVALIAÇÃO (≤ 12)")
    p.add_argument("--variantes", default="antes,depois,ppo")
    p.add_argument("--velocidades", default=",".join(f"{v:g}" for v in VELOCIDADES))
    p.add_argument("--sem-teto", action="store_true", help="aceita velocidades da bola acima da banda do desenho (estudo do limite)")
    p.add_argument("--ventos", default="0",
                   help="intensidades (m/s) do vento ALEATÓRIO do cockpit a soprar de lado, separadas por vírgula; 0 = ar "
                        "parado (a avaliação publicada). Ex.: `--variantes depois --ventos 0,2,3 --json out/bola/"
                        "avaliacao_vento.json` (dê um --json próprio: o de omissão é o da avaliação sem vento)")
    p.add_argument("--jobs", type=int, default=min(12, max(1, (os.cpu_count() or 2) - 2)))
    p.add_argument("--json", type=Path, default=SAIDA_JSON)
    args = p.parse_args(argv)
    import sitl
    sitl.biblioteca_padrao()                        # compila a .so UMA vez, antes de criar os processos
    sementes = SEMENTES_AVALIACAO[:2] if args.rapido else SEMENTES_AVALIACAO[: args.sementes]
    velocidades = tuple(float(v) for v in args.velocidades.split(","))
    extra = {"sem_teto": True} if args.sem_teto else {}
    ventos = tuple(float(w) for w in args.ventos.split(","))
    if any(w > 0 for w in ventos) and args.json == SAIDA_JSON:
        p.error("--ventos com vento: dê um --json próprio (ex.: out/bola/avaliacao_vento.json) — o de omissão é o publicado sem vento")
    jobs = [j for var in args.variantes.split(",")
            for j in jobs_variante(var.strip(), sementes, velocidades, ventos=ventos, **extra)]
    t0 = time.perf_counter()
    print(f"SEGUIR A BOLA (aleatória, OU com teto) · {len(jobs)} episódios de {T_OLHAR_S + T_AQUISICAO_S + T_MEDIDA_S:g} s "
          f"(medida {T_MEDIDA_S:g} s) · sementes de avaliação {sementes[0]}..{sementes[-1]} · {args.jobs} processos · "
          + ("SEM VENTO" if not any(ventos) else f"vento aleatório de lado: {list(ventos)} m/s"), flush=True)
    res = executar(jobs, args.jobs)
    ag = agregar(jobs, res)
    imprimir(ag)
    saida = {"gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "protocolo": {
        "sementes_avaliacao": list(sementes), "velocidades": list(velocidades), "t_olhar_s": T_OLHAR_S,
        "t_aquisicao_s": T_AQUISICAO_S, "t_medida_s": T_MEDIDA_S, "camera": {"largura": LARGURA, "altura": ALTURA, "fps": FPS},
        "caminhos": {k: {"build": v[0] or "o da política (p50b)", "latencia_s": v[1]} for k, v in CAMINHOS.items()},
        "u_yaw_por_taxa": u_yaw_identificado(), "seguidor_antes": seguidor_antes(), "sem_teto": bool(args.sem_teto),
        "custo": "e_RMS + 0,25·e_p95 [°] + 2·|D−d*|_RMS [m] + 20·(fora da banda [0,6; 1,6]·d*) + 100·(1−campo) + 5·(1−A_SEGUIR); "
                 "queda = 500"},
        "resultados": ag, "duracao_s": time.perf_counter() - t0}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(limpar(saida), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {args.json} ({saida['duracao_s']:.0f} s)")
    return 1 if any(r.get("terminou") for j, r in zip(jobs, res, strict=True) if j["variante"] == "depois") else 0


if __name__ == "__main__":
    sys.exit(main())
