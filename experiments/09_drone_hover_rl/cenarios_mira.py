"""experiments/09_drone_hover_rl/cenarios_mira.py — os 3 CENÁRIOS DE ALTURA da mira e o episódio de tiro (treino e benchmark).

O dono quer a precisão medida em 3 cenários — o drone À MESMA ALTURA do alvo («o círculo»), MAIS BAIXO do que ele e
MAIS ALTO do que ele — com a qualidade = «quantos acertos faz num tempo curto», e com o erro MUITO penalizado:

    pontuação = acertos − K·erros            (K = `PENALIDADE`, 20: um erro apaga 20 acertos)

    cenário   drone (z)   alvo (centro)   elevação típica a ~2,5 m
    mesma       1,4 m        1,4 m              0°
    abaixo      1,0 m        2,0 m           +22° (mira para CIMA: corpo nariz-acima)
    acima       2,2 m        1,0 m           −26° (mira para BAIXO: corpo nariz-abaixo)

Cada episódio: descola até à altura do cenário (núcleo de firmware, cascata clássica), põe a bola à frente a `distancia`,
liga a trajetória (`programado` = Lissajous determinística do benchmark; `aleatorio` = Ornstein–Uhlenbeck do treino),
dá `aquisicao_s` para apontar e depois conta, numa JANELA CURTA de `janela_s`, os tiros, acertos e erros — e quanto o
drone se mexeu (x, y, z) enquanto mirava. Tudo pelo `mj_step` (regra do laboratório): a bala é a da planta, o recuo
também.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [p for p in (str(_RAIZ), str(_AQUI)) if p not in sys.path]

BUILD_ARTICULADO = "articulado_15pol_mn5006"
PENALIDADE = 20.0
CENARIOS = {
    "mesma": {"z_drone": 1.4, "z_alvo": 1.4, "rotulo": "Mesma altura do alvo"},
    "abaixo": {"z_drone": 1.0, "z_alvo": 2.0, "rotulo": "Drone ABAIXO do alvo (mira para cima)"},
    "acima": {"z_drone": 2.2, "z_alvo": 1.0, "rotulo": "Drone ACIMA do alvo (mira para baixo)"},
}
HOVER = {"modo": "velocidade", "vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0}


@dataclass
class OpcoesEpisodio:
    cenario: str = "mesma"
    semente: int = 0
    modo_bola: str = "programado"          # "programado" (benchmark) | "aleatorio" (treino) | "parado"
    vel_bola: float = 0.55
    raio_bola: float = 1.0                 # amplitude da Lissajous / irrelevante no aleatório
    distancia: float = 2.5                 # m — distância horizontal inicial da bola à frente do drone
    descolagem_s: float = 4.0
    aquisicao_s: float = 3.0
    janela_s: float = 10.0
    atirar: bool = True                    # auto-tiro com a decisão da mira (portão físico + rede TF se existir)
    usar_tf: bool = True
    articulado: bool = True                # False = o drone RÍGIDO de sempre com a `MiraBalisticaIA` (sobe/desce para mirar)
    dz_alvo: float | None = None           # treino: altura do alvo face ao drone sorteada (substitui a do cenário)
    z_drone: float | None = None
    gancho_decisao: object = None          # f(env, mira, k) chamado a cada decisão (gravação para o treino)
    extra: dict = field(default_factory=dict)


def criar_env(opc: OpcoesEpisodio, episodio_s: float):
    from env_real import DroneRealEnv
    cen = CENARIOS[opc.cenario]
    z_d = float(opc.z_drone if opc.z_drone is not None else cen["z_drone"])
    build = BUILD_ARTICULADO if opc.articulado else None
    return DroneRealEnv(build=build, modo_acao="ctbr", comando=True, com_alvo=True, episodio_s=episodio_s, alvo_z=z_d)


def correr_episodio(opc: OpcoesEpisodio, env=None, nuc=None) -> dict:
    """Um episódio do cenário — devolve as métricas da JANELA (tiros/acertos/erros/pontuação/deslocamento)."""
    import sim_view as sv
    from mira_articulada import LATENCIA_CAMERA_DCMI_S, LATENCIA_CAMERA_PI_S, MiraArticuladaIA

    cen = CENARIOS[opc.cenario]
    total_s = opc.descolagem_s + opc.aquisicao_s + opc.janela_s + 1.0
    if env is None:
        env = criar_env(opc, total_s + 2.0)
        nuc = sv.NucleoClassico.criar(env)
        nuc.instalar()
    env.reset(seed=int(opc.semente))
    nuc.pos_reset()
    lat = LATENCIA_CAMERA_DCMI_S if "arduino" in str(env.hw.nome) else LATENCIA_CAMERA_PI_S
    if opc.articulado:
        mira = MiraArticuladaIA(latencia_camera_s=lat, semente=int(opc.semente) + 101)
        mira.usar_tf = bool(opc.usar_tf)
    else:
        from mira_balistica import MiraBalisticaIA
        mira = MiraBalisticaIA()
        mira.params["cooldown_auto_tiro_s"] = 0.30         # = geração v4 do benchmark (`benchmark_evolucao.py`)
    dt = env.dt_decisao
    for _ in range(int(round(opc.descolagem_s / dt))):
        nuc.comando(HOVER)
        env.step(np.zeros(4, dtype=np.float32))
    # bola à frente do drone, à altura do cenário (ou à pedida no treino)
    p_d = np.array(env.data.qpos[:3], dtype=float)
    yaw = math.atan2(float(env.data.xmat[env.corpo][3]), float(env.data.xmat[env.corpo][0]))
    z_alvo = float(p_d[2] + opc.dz_alvo) if opc.dz_alvo is not None else float(cen["z_alvo"])
    env.ponto_alvo = np.array([p_d[0] + opc.distancia * math.cos(yaw), p_d[1] + opc.distancia * math.sin(yaw), z_alvo])
    env.ponto_banda_z = (max(0.3, z_alvo - 0.45), z_alvo + 0.45)
    env.definir_trajetoria_ponto(opc.modo_bola, vel=opc.vel_bola, raio=opc.raio_bola,
                                 semente=int(opc.semente) + 7 if opc.modo_bola == "aleatorio" else None)
    mira.reiniciar()
    n_aq = int(round(opc.aquisicao_s / dt))
    n_jan = int(round(opc.janela_s / dt))
    pl = env.planta
    estacao = np.array(env.data.qpos[:3], dtype=float)     # onde pairava antes de começar a mirar
    desloc_estacao = 0.0
    t0_tiros, t0_acertos, t0_erros = pl.n_tiros, pl.n_acertos_bola, pl.n_erros_bola
    pos_ini = None
    desloc = []
    pitch_corpo, elev_err = [], []
    k_total = 0
    for k in range(n_aq + n_jan):
        cmd = mira.passo(env, dt=dt)
        nuc.comando(cmd)
        na_janela = k >= n_aq
        if na_janela and pos_ini is None:
            pos_ini = np.array(env.data.qpos[:3], dtype=float)
            t0_tiros, t0_acertos, t0_erros = pl.n_tiros, pl.n_acertos_bola, pl.n_erros_bola
        if opc.gancho_decisao is not None:
            opc.gancho_decisao(env, mira, k_total)
        if na_janela and opc.atirar:
            if opc.articulado:
                if mira.deve_atirar(env):
                    mira.atirar(env)
            elif mira.deve_atirar(env):
                env.disparar(1)
        env.step(np.zeros(4, dtype=np.float32))
        k_total += 1
        desloc_estacao = max(desloc_estacao, float(np.linalg.norm(np.array(env.data.qpos[:3]) - estacao)))
        if na_janela:
            desloc.append(np.array(env.data.qpos[:3], dtype=float) - pos_ini)
            if opc.articulado and mira.ultimo:
                pitch_corpo.append(math.degrees(mira.ultimo["pitch_v"]))
                elev_err.append(math.degrees(mira.ultimo["eps_req"] - mira.ultimo["eps_cano_cam"]))
    # tiros ainda no ar no fim da janela contam (a janela fecha as ORDENS, não as balas)
    for _ in range(int(round(0.2 / dt))):
        nuc.comando(mira.passo(env, dt=dt) if opc.articulado else HOVER)
        if opc.gancho_decisao is not None:
            opc.gancho_decisao(env, mira, k_total)
        env.step(np.zeros(4, dtype=np.float32))
        k_total += 1
    tiros = pl.n_tiros - t0_tiros
    acertos = pl.n_acertos_bola - t0_acertos
    erros = pl.n_erros_bola - t0_erros
    d = np.array(desloc) if desloc else np.zeros((1, 3))
    return {
        "cenario": opc.cenario, "semente": opc.semente, "articulado": opc.articulado, "usar_tf": opc.usar_tf,
        "tiros": int(tiros), "acertos": int(acertos), "erros": int(erros),
        "pontuacao": float(acertos - PENALIDADE * erros),
        "acertos_por_min": float(60.0 * acertos / opc.janela_s),
        "precisao_pct": float(100.0 * acertos / max(tiros, 1)),
        "desloc_max_m": float(np.max(np.linalg.norm(d, axis=1))),
        "desloc_xy_max_m": float(np.max(np.linalg.norm(d[:, :2], axis=1))),
        "desloc_z_max_m": float(np.max(np.abs(d[:, 2]))),
        "desloc_estacao_max_m": float(desloc_estacao),      # quanto se afastou de onde pairava, desde que começou a mirar
        "pitch_corpo_medio_graus": float(np.mean(pitch_corpo)) if pitch_corpo else 0.0,
        "erro_elevacao_rms_graus": float(np.sqrt(np.mean(np.square(elev_err)))) if elev_err else 0.0,
        "janela_s": opc.janela_s,
    }


__all__ = ["BUILD_ARTICULADO", "CENARIOS", "HOVER", "OpcoesEpisodio", "PENALIDADE", "correr_episodio", "criar_env"]
