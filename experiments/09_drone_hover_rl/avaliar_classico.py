#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/avaliar_classico.py — cascata CLÁSSICA vs política RL, MEDIDO no mesmo simulador.

Faz correr a `CascataClassica` (`controlo_classico.py`) e a política RL de referência
`out/real_1950_voo_final/final.zip` no `DroneRealEnv` (build do `hardware.json` da política = `endurance_15pol_p50b`,
SEM VENTO), com a MESMA planta, as MESMAS sementes (⇒ os mesmos planos WASDQE, o mesmo ruído dos sensores e,
com `aleatorizar=True`, o mesmo domain randomization) e as mesmas janelas de medida. Protocolo-modelo:
`avaliar_real.py` (ação determinística, `env.step` a 50 Hz com 10 passos de física de 2 ms por decisão).

TESTES
  (a) HOVER 30 s × N sementes: ‖xy‖ RMS/máx, |Δz| RMS, roll/pitch RMS, deriva de rumo, esforço dos motores (RMS
      de Δu por passo de 2 ms, potência média). Janela de medida: t ∈ [10 s, 30 s] (o descolar fica de fora).
  (b) DEGRAUS de velocidade: 0→1 m/s à frente, 0→0,7 m/s a subir, 0→−1 m/s lateral (direita): tempo de subida
      10–90 %, sobressinal, assentamento a 2 %/5 %, erro de regime.
  (c) SEGUIMENTO de planos aleatórios WASDQE (`comandos_aleatorios=True`, o plano do próprio env): ‖v − v_ref‖ e
      ‖xy − p_ref‖ (RMS, e a média da 2.ª metade do episódio = a métrica do `avaliar_real.py`).
  (d) YAW (só a cascata — a RL não roda): degrau de rumo de 90°, taxa de 0,5 rad/s, rodar enquanto avança a
      1 m/s (arco coerente, |Δz| máx.), fração de passos com a mistura saturada.
  (e) ROBUSTEZ com DR ligado (`aleatorizar=True`) em (a)–(c).

REGRAS DE HONESTIDADE
  · calibração ≠ avaliação: os ganhos/limites da cascata foram afinados em SEMENTES DE CALIBRAÇÃO (9000..) que
    NÃO entram na avaliação (5000..); a varredura vem em `--calibrar` e está no README;
  · a métrica de seguimento é a do env (referência `p_ref` integrada no referencial do MUNDO) e, à parte, a
    mesma métrica no referencial de ARRANQUE (o do estimador: o env sorteia um rumo inicial ±5° que nenhum dos
    dois controladores pode saber) — as duas são reportadas;
  · MEDIDO = números desta corrida; INFERIDO = leitura/explicação (marcado como tal no README).

    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_classico.py --rapido
    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_classico.py --json out/classico/avaliacao.json
    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_classico.py --calibrar
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
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]
from lab import mjkit  # noqa: F401, I001

import numpy as np

import controlo_classico as cc
from env import VOO_Z_MIN
from env_real import DroneRealEnv, build_do_hardware

MODELO_RL = _AQUI / "out" / "real_1950_voo_final" / "final.zip"
SAIDA_JSON = _AQUI / "out" / "classico" / "avaliacao.json"
SEMENTES_AVALIACAO = tuple(range(5000, 5012))       # as de `avaliar_real.py` começam em 5000
SEMENTES_CALIBRACAO = tuple(range(9000, 9008))      # NUNCA entram na avaliação
JANELA_HOVER = (10.0, 30.0)                         # s
JANELA_SEGUIMENTO_T0 = 4.0                          # s — descolar fora
T_CALIBRACAO_GIRO = 1.0                             # s no chão, antes de armar (só estimador melhorado)


# ------------------------------------------------------------------------------------------------ ambiente e sonda
def carregar_rl(caminho: Path = MODELO_RL):
    from stable_baselines3 import PPO
    modelo = PPO.load(str(caminho), device="cpu")
    hw = caminho.parent / "hardware.json"
    dados = json.loads(hw.read_text(encoding="utf-8")) if hw.is_file() else {}
    return modelo, dados


_CACHE: dict = {}


def rl_cache():
    if "rl" not in _CACHE:
        import torch
        torch.set_num_threads(1)
        _CACHE["rl"] = carregar_rl()
    return _CACHE["rl"]


def criar_env(dados_hw: dict, *, dr: bool, episodio_s: float, aleatorios: bool = False,
              alvo_z: float = 1.0) -> DroneRealEnv:
    build, _ = build_do_hardware(dados_hw)
    return DroneRealEnv(build=build, modo_acao=dados_hw.get("modo_acao", "ctbr"), aleatorizar=dr,
                        comando=True, comandos_aleatorios=aleatorios, episodio_s=episodio_s, alvo_z=alvo_z)


class SondaFC:
    """Envolve `env.fc.passo` (sem tocar no fc.py) e mede, a CADA passo de física de 2 ms: Δu dos motores e a
    saturação da mistura (algum motor no teto 1,0 ou no `idle`; o diferencial a ocupar a faixa toda)."""

    def __init__(self, fc):
        self.fc = fc
        self._orig = fc.passo
        self.n = 0
        self.soma_du2 = 0.0
        self.sat = 0
        self.dif_cheio = 0
        self.u_ant = None
        fc.passo = self

    def __call__(self, acelerador, taxas_sp, giro_medido):
        u = self._orig(acelerador, taxas_sp, giro_medido)
        if self.u_ant is not None:
            self.soma_du2 += float(np.mean((u - self.u_ant) ** 2))
            self.n += 1
        self.u_ant = u.copy()
        if u.max() >= 1.0 - 1e-9 or u.min() <= self.fc.idle + 1e-9:
            self.sat += 1
        if float(u.max() - u.min()) >= 0.999 * (1.0 - self.fc.idle):
            self.dif_cheio += 1
        return u

    def resumo(self) -> dict:
        n = max(self.n, 1)
        return {"du_rms": math.sqrt(self.soma_du2 / n), "frac_saturado": self.sat / n,
                "frac_dif_cheio": self.dif_cheio / n}


# ------------------------------------------------------------------------------------------------ controladores
class ControladorRL:
    """A política RL de referência (ação determinística = a média, como o `avaliar_real.py`)."""

    nome = "rl"

    def __init__(self, modelo):
        self.modelo = modelo

    def preparar(self, env) -> None:
        pass

    def reiniciar(self, env, obs) -> None:
        self._obs = obs

    def acao(self, env, t: float):
        a, _ = self.modelo.predict(env.observacao(), deterministic=True)
        return a


def deslocamento_sensor_cm(env) -> float:
    """Altura do CM acima do sensor de baixo (o ToF mede a altura do SENSOR; o env mede a do CM) — geometria
    do build, conhecida: 4,3 cm."""
    return -float(env.model.site_pos[env.model.site("baixo").id][2])


class ControladorCascata:
    """`CascataClassica` ligada ao env: lê `env.estimador`/`env.planta.imu.giro` (SÓ sensores) e escreve a ação.

    `cmd_fn(t)` devolve o `cmd` do firmware (referencial do rumo); por omissão lê o `v_ref` do próprio env
    (plano aleatório/degraus do `definir_comando`), que o RL também recebe.
    """

    nome = "cascata"

    def __init__(self, ganhos=None, razao: float = 4.0, estimador: str = "bordo", cmd_fn=None,
                 opcoes_ganhos: dict | None = None, opcoes_est: dict | None = None,
                 razao_atitude: float = 2.5):
        self._ganhos = ganhos
        self.opcoes = dict(opcoes_ganhos or {})
        self.razao = self.opcoes.pop("razao", razao)
        self.razao_atitude = self.opcoes.pop("razao_atitude", razao_atitude)
        self.estimador = estimador
        self.cmd_fn = cmd_fn
        self.opcoes_est = opcoes_est or {}
        self.casc = None

    def preparar(self, env) -> None:
        if self.estimador == "melhorado":
            env.estimador = cc.EstimadorClassico(env.dt, **self.opcoes_est)

    def reiniciar(self, env, obs) -> None:
        opcoes = dict(self.opcoes)
        # piso de altitude = o do contrato r11 (VOO_Z_MIN, do CM) lido ao nível do SENSOR (o ToF mede a altura do sensor)
        opcoes.setdefault("altura_min", VOO_Z_MIN - deslocamento_sensor_cm(env))
        gn = self._ganhos or cc.ganhos_de_hardware(env, razao=self.razao, razao_atitude=self.razao_atitude,
                                                   **opcoes)
        self.ganhos = gn
        self.casc = cc.CascataClassica(gn)
        if self.estimador == "melhorado":
            calibrar_no_chao(env, T_CALIBRACAO_GIRO)
        self.casc.armar(True, env.estimador, z_alvo=env.alvo_z - deslocamento_sensor_cm(env))

    def acao(self, env, t: float):
        cmd = self.cmd_fn(t) if self.cmd_fn else {"vx": env.v_ref[0], "vy": env.v_ref[1], "vz": env.v_ref[2]}
        c, tx = self.casc.passo(env.estimador, env.planta.imu.giro.medicao, cmd, env.dt_decisao)
        return np.asarray(cc.cmd_para_acao(c, tx), dtype=np.float32)


def calibrar_no_chao(env, segundos: float) -> None:
    """Pré-voo: calibra o estimador MELHORADO com o drone PARADO no chão (motores em `idle`), SEM avançar o
    relógio do episódio (`env.passos`, plano e `p_ref` não andam) — o equivalente do «calibrar o giroscópio
    ao ligar» de qualquer FC. A física é a do `mj_step` (mesmo laço de 7 linhas do `DroneRealEnv.step`)."""
    pl, est, fc = env.planta, env.estimador, env.fc
    est.calibrar(True)
    for _ in range(round(segundos / env.dt)):
        u = fc.passo(0.0, np.zeros(3), pl.imu.giro.medicao)
        pl.passo(u)
        tof, fl = pl.tof, pl.fluxo
        est.passo(pl.imu.giro.medicao, pl.imu.acc.medicao, tof.distancia, tof.valido, tof.s.n_amostras,
                  fl.fluxo, fl.valido, fl.s.n_amostras)
    est.calibrar(False)


# ------------------------------------------------------------------------------------------------ um episódio
def correr(env, ctrl, seed: int, T: float, *, cmd_mundo=None, opcoes_reset: dict | None = None) -> dict:
    """Corre um episódio de `T` s e devolve o registo (arrays por decisão) + resumo da sonda do FC.

    `cmd_mundo(t)` (opcional) → `v_ref` do env (`definir_comando`, frame MUNDO do contrato r11) aplicado ANTES de cada
    decisão, igual para o RL e para a cascata. Terminação (queda/capotamento) fecha o episódio com `terminou=True`.
    """
    ctrl.preparar(env)
    env.reset(seed=seed, options=opcoes_reset or {})
    ctrl.reiniciar(env, None)               # (a calibração no chão acontece aqui — fora da sonda e do relógio)
    sonda = SondaFC(env.fc)
    n_max = round(T / env.dt_decisao)
    cols = ("t", "x", "y", "z", "phi", "theta", "yaw", "vx", "vy", "vz", "xr", "yr", "zr", "vxr", "vyr", "vzr",
            "ex", "ey", "eh", "epsi", "p_w", "wx", "wy", "wz", "s_n", "s_sat", "s_dif", "e_roll", "e_pitch",
            "e_vx", "e_vy", "fc_iz")
    buf = {c: [] for c in cols}
    terminou = False
    yaw0 = float(env.yaw0)
    for k in range(n_max):
        t = k * env.dt_decisao
        if cmd_mundo is not None:
            env.definir_comando(cmd_mundo(t))
        a = ctrl.acao(env, t)
        _obs, _r, term, _trunc, info = env.step(a)
        d = env._derivados()
        est = env.estimador
        fila = (t + env.dt_decisao, d["x"], d["y"], d["z"], d["phi"], d["theta"], d["yaw"], *d["v_vec"],
                *env.p_ref, *env.v_ref, est.x, est.y, est.h, est.psi, info["p_total"], *d["omega"],
                sonda.n, sonda.sat, sonda.dif_cheio, est.roll, est.pitch, est.vx, est.vy, env.fc.integral[2])
        for c, v in zip(cols, fila, strict=True):
            buf[c].append(float(v))
        if term:
            terminou = True
            break
    reg = {c: np.array(v) for c, v in buf.items()}
    reg.update({"terminou": terminou, "yaw0": yaw0, "n": len(reg["t"]), "T": T,
                "sonda": sonda.resumo(), "dt": env.dt_decisao})
    return reg


def rodar_arranque(reg: dict, x, y):
    """Vetor do plano no referencial de ARRANQUE (rumo inicial): R_z(−ψ₀)·(x, y)."""
    c, s = math.cos(reg["yaw0"]), math.sin(reg["yaw0"])
    return c * x + s * y, -s * x + c * y


def referencia_no_arranque(reg: dict):
    """A referência do env (`p_ref`, `v_ref`: referencial do MUNDO) lida NO referencial de arranque — o único que os
    controladores conhecem (o estimador começa em (0, 0) com o rumo inicial ψ₀ ± 5°, que o env sorteia e ninguém
    sabe): p = p₀ + R_z(ψ₀)·p_ref, v = R_z(ψ₀)·v_ref. Usada SÓ na métrica, nunca por um controlador."""
    c, s = math.cos(reg["yaw0"]), math.sin(reg["yaw0"])
    x0, y0 = reg["x"][0] - reg["xr"][0] * 0.0, reg["y"][0]
    xr = x0 + c * reg["xr"] - s * reg["yr"]
    yr = y0 + s * reg["xr"] + c * reg["yr"]
    vxr = c * reg["vxr"] - s * reg["vyr"]
    vyr = s * reg["vxr"] + c * reg["vyr"]
    return xr, yr, vxr, vyr


# ------------------------------------------------------------------------------------------------ métricas
def _rms(v) -> float:
    v = np.asarray(v, dtype=float)
    return float(np.sqrt(np.mean(v * v))) if v.size else float("nan")


def metricas_hover(reg: dict, janela=JANELA_HOVER) -> dict:
    t = reg["t"]
    m = (t >= janela[0]) & (t <= janela[1])
    if not m.any():
        return {"terminou": reg["terminou"]}
    dxy = np.hypot(reg["x"][m], reg["y"][m])
    yaw_rel = np.unwrap(reg["yaw"]) - reg["yaw0"]
    diag = diagnostico_estimador(reg, m)
    return {**diag, "terminou": bool(reg["terminou"]), "xy_rms": _rms(dxy), "xy_max": float(dxy.max()),
            "dz_rms": _rms(reg["z"][m] - reg["zr"][m]), "roll_rms_graus": math.degrees(_rms(reg["phi"][m])),
            "pitch_rms_graus": math.degrees(_rms(reg["theta"][m])),
            "deriva_rumo_graus": abs(math.degrees(float(yaw_rel[m][-1] - yaw_rel[m][0]))),
            "rumo_max_graus": math.degrees(float(np.abs(yaw_rel[m]).max())),
            "du_rms": reg["sonda"]["du_rms"], "p_media_w": float(np.mean(reg["p_w"][m])),
            "frac_saturado": reg["sonda"]["frac_saturado"]}


def diagnostico_estimador(reg: dict, m) -> dict:
    """O que o ESTIMADOR erra, na janela `m` (verdade só para medir): atitude (roll/pitch), velocidade horizontal no
    corpo (fluxo) e DERIVA da odometria — a posição verdadeira menos (início + odometria rodada de ψ₀)."""
    c, s = math.cos(reg["yaw0"]), math.sin(reg["yaw0"])
    px = reg["x"][0] + c * reg["ex"] - s * reg["ey"]
    py = reg["y"][0] + s * reg["ex"] + c * reg["ey"]
    deriva = np.hypot(reg["x"] - px, reg["y"] - py)
    # velocidade verdadeira no corpo: Rᵀ·v (ZYX)
    cf, sf = np.cos(reg["phi"]), np.sin(reg["phi"])
    ct, st = np.cos(reg["theta"]), np.sin(reg["theta"])
    cp, sp = np.cos(reg["yaw"]), np.sin(reg["yaw"])
    vx, vy, vz = reg["vx"], reg["vy"], reg["vz"]
    vbx = (cp * ct) * vx + (sp * ct) * vy - st * vz
    vby = (cp * st * sf - sp * cf) * vx + (sp * st * sf + cp * cf) * vy + (ct * sf) * vz
    e_v = np.hypot(reg["e_vx"] - vbx, reg["e_vy"] - vby)
    e_att = np.hypot(reg["e_roll"] - reg["phi"], reg["e_pitch"] - reg["theta"])
    return {"est_deriva_rms": _rms(deriva[m]), "est_atitude_rms_graus": math.degrees(_rms(e_att[m])),
            "est_vel_rms": _rms(e_v[m]), "est_xy_rms": _rms(np.hypot(reg["ex"], reg["ey"])[m])}


def metricas_seguimento(reg: dict, t0: float = JANELA_SEGUIMENTO_T0) -> dict:
    t = reg["t"]
    m = t >= t0
    if not m.any():
        return {"terminou": reg["terminou"]}
    ev = np.stack([reg["vx"] - reg["vxr"], reg["vy"] - reg["vyr"], reg["vz"] - reg["vzr"]])[:, m]
    exy = np.hypot(reg["x"] - reg["xr"], reg["y"] - reg["yr"])[m]
    ez = np.abs(reg["z"] - reg["zr"])[m]
    # referencial de ARRANQUE: a referência lida no frame dos controladores (ver `referencia_no_arranque`)
    xra, yra, vxra, vyra = referencia_no_arranque(reg)
    exya = np.hypot(reg["x"] - xra, reg["y"] - yra)[m]
    eva = np.stack([reg["vx"] - vxra, reg["vy"] - vyra, reg["vz"] - reg["vzr"]])[:, m]
    metade = m & (t >= 0.5 * reg["T"])
    exy_all = np.hypot(reg["x"] - reg["xr"], reg["y"] - reg["yr"])
    return {"terminou": bool(reg["terminou"]), "v_rms": _rms(np.linalg.norm(ev, axis=0)),
            "xy_rms": _rms(exy), "z_rms": _rms(ez), "xy_medio_2a_metade": float(np.mean(exy_all[metade])),
            "v_rms_arranque": _rms(np.linalg.norm(eva, axis=0)), "xy_rms_arranque": _rms(exya),
            "du_rms": reg["sonda"]["du_rms"], "p_media_w": float(np.mean(reg["p_w"][m])),
            "frac_saturado": reg["sonda"]["frac_saturado"]}


def metricas_degrau(reg: dict, t_degrau: float, v_final: np.ndarray, janela_s: float = 8.0) -> dict:
    """Resposta ao degrau de velocidade `v_final` (3 m/s, mundo/arranque) aplicado em `t_degrau`: projeta a velocidade
    verdadeira (referencial de ARRANQUE) na direção do comando e mede 10–90 %, sobressinal, assentamento, regime."""
    v_final = np.asarray(v_final, dtype=float)
    amp = float(np.linalg.norm(v_final))
    u = v_final / amp
    va_x, va_y = rodar_arranque(reg, reg["vx"], reg["vy"])
    s_all = u[0] * va_x + u[1] * va_y + u[2] * reg["vz"]
    t = reg["t"]
    m = (t >= t_degrau) & (t <= t_degrau + janela_s)
    if m.sum() < 10 or reg["terminou"]:
        return {"terminou": bool(reg["terminou"])}
    ts, s = t[m] - t_degrau, s_all[m]
    base = float(np.mean(s_all[(t >= t_degrau - 1.0) & (t < t_degrau)]))
    s = s - base
    def cruza(frac):
        i = np.nonzero(s >= frac * amp)[0]
        return float(ts[i[0]]) if i.size else float("nan")
    t10, t90 = cruza(0.1), cruza(0.9)
    sobre = float((s.max() - amp) / amp)
    def assenta(tol):
        fora = np.nonzero(np.abs(s - amp) > tol * amp)[0]
        if fora.size == 0:
            return 0.0
        if fora[-1] >= len(ts) - 1:
            return float("inf")
        return float(ts[fora[-1] + 1])
    regime = float(np.mean(s[ts >= janela_s - 2.0]) - amp)
    i_pico = int(np.argmax(s))
    afundamento = float((amp - s[i_pico:].min()) / amp) if i_pico < len(s) - 1 else 0.0   # queda abaixo do alvo após o pico
    return {"terminou": False, "subida_10_90_s": t90 - t10, "sobressinal": sobre, "assenta_2pct_s": assenta(0.02),
            "assenta_5pct_s": assenta(0.05), "erro_regime": regime, "afundamento": max(afundamento, 0.0),
            "amplitude": amp, "base": base}


def _janela_sat(reg: dict, m) -> tuple[float, float]:
    """Fração de passos de física com a mistura saturada / com o diferencial a ocupar a faixa toda, na janela `m`."""
    idx = np.nonzero(m)[0]
    if idx.size < 2:
        return float("nan"), float("nan")
    i0, i1 = max(idx[0] - 1, 0), idx[-1]
    n = max(reg["s_n"][i1] - reg["s_n"][i0], 1)
    return float((reg["s_sat"][i1] - reg["s_sat"][i0]) / n), float((reg["s_dif"][i1] - reg["s_dif"][i0]) / n)


def metricas_yaw_degrau(reg: dict, t0: float, alvo: float, janela_s: float) -> dict:
    """Degrau de rumo `alvo` [rad] em `t0`: subida 10–90 %, sobressinal, assentamento, erro de regime, |Δz|, deriva xy."""
    if reg["terminou"]:
        return {"terminou": True}
    t = reg["t"]
    m = (t >= t0) & (t <= t0 + janela_s)
    pre = (t >= t0 - 1.0) & (t < t0)
    yaw = np.unwrap(reg["yaw"])
    y = yaw[m] - float(np.mean(yaw[pre]))
    ts = t[m] - t0
    def cruza(frac):
        i = np.nonzero(y >= frac * alvo)[0]
        return float(ts[i[0]]) if i.size else float("nan")
    def assenta(tol):
        fora = np.nonzero(np.abs(y - alvo) > tol * alvo)[0]
        if fora.size == 0:
            return 0.0
        return float("inf") if fora[-1] >= len(ts) - 1 else float(ts[fora[-1] + 1])
    z0 = float(np.mean(reg["z"][pre]))
    xy0 = (float(np.mean(reg["x"][pre])), float(np.mean(reg["y"][pre])))
    sat, dif = _janela_sat(reg, m)
    return {"terminou": False, "subida_10_90_s": cruza(0.9) - cruza(0.1), "sobressinal": float((y.max() - alvo) / alvo),
            "assenta_2pct_s": assenta(0.02), "assenta_5pct_s": assenta(0.05),
            "erro_regime_graus": math.degrees(float(np.mean(y[ts >= janela_s - 2.0]) - alvo)),
            "dz_max": float(np.abs(reg["z"][m] - z0).max()),
            "xy_deriva_max": float(np.hypot(reg["x"][m] - xy0[0], reg["y"][m] - xy0[1]).max()),
            "roll_pico_graus": math.degrees(float(np.abs(reg["phi"][m]).max())),
            "pitch_pico_graus": math.degrees(float(np.abs(reg["theta"][m]).max())),
            "taxa_pico": float(np.abs(reg["wz"][m]).max()), "frac_saturado": sat, "frac_dif_cheio": dif}


def metricas_yaw_taxa(reg: dict, t0: float, r_cmd: float, dur: float) -> dict:
    """Taxa de yaw `r_cmd` [rad/s] mantida de `t0` a `t0+dur`: taxa média/erro na janela estacionária, |Δz|, saturação."""
    if reg["terminou"]:
        return {"terminou": True}
    t = reg["t"]
    m = (t >= t0) & (t <= t0 + dur)
    est = (t >= t0 + 0.4 * dur) & (t <= t0 + dur)
    pre = (t >= t0 - 1.0) & (t < t0)
    z0 = float(np.mean(reg["z"][pre]))
    sat, dif = _janela_sat(reg, m)
    return {"terminou": False, "taxa_media": float(np.mean(reg["wz"][est])), "taxa_cmd": r_cmd,
            "erro_taxa_rms": _rms(reg["wz"][est] - r_cmd), "dz_max": float(np.abs(reg["z"][m] - z0).max()),
            "roll_pico_graus": math.degrees(float(np.abs(reg["phi"][m]).max())),
            "pitch_pico_graus": math.degrees(float(np.abs(reg["theta"][m]).max())),
            "frac_saturado": sat, "frac_dif_cheio": dif}


def metricas_yaw_arco(reg: dict, t0: float, v: float, r_cmd: float, dur: float) -> dict:
    """Avançar a `v` m/s (no rumo) a rodar `r_cmd` rad/s: o caminho deve ser um ARCO de raio v/r. Ajuste de círculo
    (mínimos quadrados) ao caminho em [t0+3 s, t0+dur]: raio ajustado vs v/r, desvio RMS ao círculo, |Δz| máx."""
    if reg["terminou"]:
        return {"terminou": True}
    t = reg["t"]
    m = (t >= t0 + 3.0) & (t <= t0 + dur)
    mm = (t >= t0) & (t <= t0 + dur)
    pre = (t >= t0 - 1.0) & (t < t0)
    x, y = reg["x"][m], reg["y"][m]
    a = np.stack([2 * x, 2 * y, np.ones_like(x)], axis=1)
    b = x * x + y * y
    cx, cy, c0 = np.linalg.lstsq(a, b, rcond=None)[0]
    raio = math.sqrt(max(c0 + cx * cx + cy * cy, 0.0))
    dist = np.hypot(x - cx, y - cy)
    vel = np.hypot(reg["vx"][m], reg["vy"][m])
    z0 = float(np.mean(reg["z"][pre]))
    sat, dif = _janela_sat(reg, mm)
    return {"terminou": False, "raio_ajustado": float(raio), "raio_esperado": v / r_cmd,
            "desvio_circulo_rms": _rms(dist - raio), "vel_media": float(np.mean(vel)),
            "dz_max": float(np.abs(reg["z"][mm] - z0).max()),
            "roll_pico_graus": math.degrees(float(np.abs(reg["phi"][mm]).max())),
            "frac_saturado": sat, "frac_dif_cheio": dif}


# ------------------------------------------------------------------------------------------------ tarefas (jobs)
def tarefa(job: dict) -> dict:
    """Corre UM episódio descrito por `job` e devolve as métricas (função de topo → serializável p/ multiprocessing)."""
    kind, teste, seed, dr = job["kind"], job["teste"], job["seed"], job["dr"]
    modelo, dados = rl_cache() if kind == "rl" else (None, _CACHE.setdefault("dados", carregar_rl_dados()))
    if kind == "rl":
        ctrl = ControladorRL(modelo)
    else:
        ctrl = ControladorCascata(razao=job.get("razao", 4.0), estimador=job.get("estimador", "bordo"),
                                  opcoes_ganhos=job.get("opcoes"), opcoes_est=job.get("est_kw"),
                                  razao_atitude=job.get("razao_atitude", 2.5))
    t0 = time.perf_counter()
    if teste == "hover":
        T = job.get("T", 30.0)
        env = criar_env(dados, dr=dr, episodio_s=T)
        reg = correr(env, ctrl, seed, T)
        out = metricas_hover(reg)
    elif teste == "seguimento":
        T = job.get("T", 10.0)
        env = criar_env(dados, dr=dr, episodio_s=T, aleatorios=True)
        reg = correr(env, ctrl, seed, T)
        out = metricas_seguimento(reg)
    elif teste == "degrau":
        v = np.array(job["v"], dtype=float)
        t_deg = job.get("t_degrau", 6.0)
        janela = job.get("janela", 8.0)
        T = t_deg + janela + 0.5
        env = criar_env(dados, dr=dr, episodio_s=T, alvo_z=job.get("alvo_z", 1.0))
        reg = correr(env, ctrl, seed, T, cmd_mundo=lambda t: v if t >= t_deg else np.zeros(3))
        out = metricas_degrau(reg, t_deg, v, janela)
    elif teste == "ident_yaw":
        out = identificar_yaw_um(dados, seed, job["r"], job["dur"])
    elif teste in ("yaw_degrau", "yaw_taxa", "yaw_arco"):
        t0y = 6.0
        env = criar_env(dados, dr=dr, episodio_s=t0y + job["dur"] + 0.5)
        if teste == "yaw_degrau":
            alvo = job.get("alvo", math.pi / 2)
            cmd_fn = lambda t: ({"modo": "yaw_alvo", "yaw": alvo} if t >= t0y else {})
        elif teste == "yaw_taxa":
            cmd_fn = lambda t: ({"yaw_taxa": job["r"]} if t >= t0y else {})
        else:
            cmd_fn = lambda t: ({"vx": job["v"], "yaw_taxa": job["r"]} if t >= t0y else {})
        ctrl = ControladorCascata(razao=job.get("razao", 4.0), estimador=job.get("estimador", "melhorado"),
                                  opcoes_ganhos=job.get("opcoes"), opcoes_est=job.get("est_kw"), cmd_fn=cmd_fn)
        reg = correr(env, ctrl, seed, t0y + job["dur"])
        if teste == "yaw_degrau":
            out = metricas_yaw_degrau(reg, t0y, alvo, job["dur"])
        elif teste == "yaw_taxa":
            out = metricas_yaw_taxa(reg, t0y, job["r"], job["dur"])
        else:
            out = metricas_yaw_arco(reg, t0y, job["v"], job["r"], job["dur"])
    else:
        raise ValueError(f"teste desconhecido: {teste}")
    out.update({"kind": kind, "teste": teste, "seed": seed, "dr": dr, "parede_s": time.perf_counter() - t0})
    return out


def identificar_yaw_um(dados: dict, seed: int, r_cmd: float, dur: float) -> dict:
    """UM ensaio de identificação do yaw: a cascata paira e, em t = 6 s, manda `yaw_taxa = r_cmd` SEM limites de
    taxa/aceleração (é a MISTURA do fc.py que limita). Mede a taxa de yaw verdadeira e o integral do PID de yaw do FC
    (= o acelerador diferencial de EQUILÍBRIO) e a aceleração inicial."""
    t0y = 6.0
    env = criar_env(dados, dr=False, episodio_s=t0y + dur)
    opcoes = {"taxa_yaw_max": 2.0, "acel_yaw_max": 1000.0, "avanco_yaw_max": 1000.0, "comp_yaw_empuxo": False}
    ctrl = ControladorCascata(razao=4.0, estimador="melhorado", opcoes_ganhos=opcoes,
                              cmd_fn=lambda t: ({"yaw_taxa": r_cmd} if t >= t0y else {}))
    reg = correr(env, ctrl, seed, t0y + dur)
    t = reg["t"]
    est = (t >= t0y + 0.55 * dur) & (t <= t0y + dur)
    ini = (t >= t0y + 0.05) & (t <= t0y + 0.5)
    acc = float(np.polyfit(t[ini], reg["wz"][ini], 1)[0]) if ini.sum() > 3 else float("nan")
    return {"terminou": bool(reg["terminou"]), "r_cmd": r_cmd, "r_ss": float(np.mean(reg["wz"][est])),
            "i_z": float(np.mean(reg["fc_iz"][est])), "acel_inicial": acc,
            "frac_saturado": reg["sonda"]["frac_saturado"], "z_max": float(reg["z"].max())}


def identificar_yaw(dados: dict, n_jobs: int = 4, seed: int = SEMENTES_CALIBRACAO[0]) -> dict:
    """IDENTIFICA os limites de yaw do frame no simulador (planta nominal, semente de CALIBRAÇÃO):
      · EQUILÍBRIO — taxas fixas 0,1…0,5 rad/s: o integral do PID de yaw do FC é o acelerador diferencial que vence o
        arrasto, I_z = (u/r)·r ⇒ `u_yaw_por_taxa` = declive; com α_z e J_zz do FC: c_yaw = (u/r)·α_z·J_zz;
      · SATURAÇÃO — 1,0 rad/s sem limites: a mistura limita; mede a aceleração inicial e a taxa terminal máxima.
    """
    jobs = [{"kind": "cascata", "teste": "ident_yaw", "seed": seed, "dr": False, "r": r, "dur": 10.0}
            for r in (0.1, 0.2, 0.3, 0.4, 0.5)]
    jobs.append({"kind": "cascata", "teste": "ident_yaw", "seed": seed, "dr": False, "r": 1.0, "dur": 5.0})
    res = executar(jobs, n_jobs)
    eq = [r for r in res if r["r_cmd"] <= 0.5]
    r_ss = np.array([r["r_ss"] for r in eq])
    i_z = np.array([r["i_z"] for r in eq])
    u_por_taxa = float(np.sum(i_z * r_ss) / np.sum(r_ss * r_ss))          # declive pela origem
    env = criar_env(dados, dr=False, episodio_s=1.0)
    alfa_z, j_zz = float(env.fc.alfa[2]), float(env.fc.inercia[2])
    sat = next(r for r in res if r["r_cmd"] == 1.0)
    return {"u_yaw_por_taxa": u_por_taxa, "c_yaw_medido": u_por_taxa * alfa_z * j_zz,
            "c_yaw_formula_rotor": 0.30 * float(env.massa) * (0.5 * float(env.hw.frame.wheelbase)) ** 2,
            "alfa_z_fc": alfa_z, "j_zz": j_zz, "taxa_terminal_saturada": sat["r_ss"],
            "acel_inicial_saturada": sat["acel_inicial"], "frac_saturado_saturada": sat["frac_saturado"],
            "equilibrio": [{"r_ss": float(a), "i_z": float(b)} for a, b in zip(r_ss, i_z, strict=True)]}


def carregar_rl_dados() -> dict:
    hw = MODELO_RL.parent / "hardware.json"
    return json.loads(hw.read_text(encoding="utf-8")) if hw.is_file() else {}


def _init_worker() -> None:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    with contextlib.suppress(ImportError):
        import torch
        torch.set_num_threads(1)


def executar(jobs: list[dict], n_jobs: int) -> list[dict]:
    if n_jobs <= 1:
        return [tarefa(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=n_jobs, initializer=_init_worker) as ex:
        return list(ex.map(tarefa, jobs, chunksize=1))


def agregar(res: list[dict], chaves: tuple[str, ...]) -> dict:
    """Média (`k`), desvio (`k_dp`) e nº de valores finitos (`k_n`) por chave, sobre as sementes em que o episódio NÃO
    terminou (queda/capotamento); `terminaram` conta as terminações. Valores não finitos (ex. assentamento que nunca
    acontece na janela) ficam de fora da média e vêm em `k_n < n`."""
    ok = [r for r in res if not r.get("terminou", False)]
    out = {"n": len(res), "terminaram": len(res) - len(ok)}
    for c in chaves:
        v = np.array([r[c] for r in ok if c in r and np.isfinite(r[c])], dtype=float)
        out[c] = float(np.mean(v)) if v.size else float("nan")
        out[c + "_dp"] = float(np.std(v)) if v.size else float("nan")
        out[c + "_med"] = float(np.median(v)) if v.size else float("nan")
        out[c + "_n"] = int(v.size)
    return out


CHAVES = {
    "hover": ("xy_rms", "xy_max", "dz_rms", "roll_rms_graus", "pitch_rms_graus", "deriva_rumo_graus",
              "du_rms", "p_media_w", "frac_saturado", "est_deriva_rms", "est_atitude_rms_graus", "est_vel_rms",
              "est_xy_rms"),
    "seguimento": ("v_rms", "xy_rms", "z_rms", "xy_medio_2a_metade", "v_rms_arranque", "xy_rms_arranque",
                   "du_rms", "p_media_w"),
    "degrau": ("subida_10_90_s", "sobressinal", "assenta_2pct_s", "assenta_5pct_s", "erro_regime", "afundamento"),
    "yaw_degrau": ("subida_10_90_s", "sobressinal", "assenta_2pct_s", "assenta_5pct_s", "erro_regime_graus",
                   "dz_max", "xy_deriva_max", "roll_pico_graus", "pitch_pico_graus", "taxa_pico", "frac_saturado",
                   "frac_dif_cheio"),
    "yaw_taxa": ("taxa_media", "erro_taxa_rms", "dz_max", "roll_pico_graus", "pitch_pico_graus", "frac_saturado",
                 "frac_dif_cheio"),
    "yaw_arco": ("raio_ajustado", "raio_esperado", "desvio_circulo_rms", "vel_media", "dz_max", "roll_pico_graus",
                 "frac_saturado", "frac_dif_cheio"),
}

# variantes avaliadas: nome → (kind, estimador, opções de ganhos)
VARIANTES = {
    "rl": ("rl", None, {}),
    "cascata_bordo": ("cascata", "bordo", {}),
    "cascata_melhorado": ("cascata", "melhorado", {}),
    "cascata_melhorado_ref": ("cascata", "melhorado", {"ref_posicao": "integrada"}),
}
DEGRAUS = {"frente": ([1.0, 0.0, 0.0], {}), "subida": ([0.0, 0.0, 0.7], {"alvo_z": 0.5, "janela": 3.6, "t_degrau": 5.0}),
           "lateral": ([0.0, -1.0, 0.0], {})}


# ---------------------------------------------------------------------------------------------- calibração
# Varredura NAS SEMENTES DE CALIBRAÇÃO (9000..): é daqui que saem os números do README que justificam cada
# escolha de ganho/estimador — (nome, opções de ganhos, opções do estimador, estimador)
CONFIGS_CALIBRACAO = [
    ("base (ganhos derivados + estimador melhorado)", {}, {}, "melhorado"),
    ("estimador de bordo (sem calibração do giroscópio)", {}, {}, "bordo"),
    ("estimador melhorado SEM portão do acelerómetro", {}, {"portao_acc": False}, "melhorado"),
    ("estimador melhorado SEM calibração do giroscópio", {}, {"cal_giro": False}, "melhorado"),
    ("estimador melhorado com altura de 2.ª ordem (sem viés do acelerómetro)", {}, {"bias_acc_z": False}, "melhorado"),
    ("estimador melhorado + parte I do Mahony (k_i = 0,02 /s²)", {}, {"ki_mahony": 0.02}, "melhorado"),
    ("estimador melhorado + parte I do Mahony (k_i = 0,1 /s²)", {}, {"ki_mahony": 0.1}, "melhorado"),
    ("estimador melhorado + parte I do Mahony (k_i = 0,5 /s²)", {}, {"ki_mahony": 0.5}, "melhorado"),
    ("razão da atitude 2,0 (K_att = ωc/2)", {"razao_atitude": 2.0}, {}, "melhorado"),
    ("razão da atitude 3,0", {"razao_atitude": 3.0}, {}, "melhorado"),
    ("razão da atitude 4,0 (pesquisa)", {"razao_atitude": 4.0}, {}, "melhorado"),
    ("razões 4/4/4/4 (ponto de partida da pesquisa)",
     {"razao_atitude": 4.0, "razao_posicao": 4.0, "razao_integral": 4.0}, {}, "melhorado"),
    ("razão do integral 4 (K_i = K_v²/4)", {"razao_integral": 4.0}, {}, "melhorado"),
    ("razão da posição 4 (K_pos = K_v/4)", {"razao_posicao": 4.0}, {}, "melhorado"),
    ("referência de posição integrada (p_ref)", {"ref_posicao": "integrada"}, {}, "melhorado"),
    ("sem feed-forward de aceleração", {"k_ff_acc": 0.0}, {}, "melhorado"),
    ("sem feed-forward de atitude (n̂ × dn̂/dt)", {"ff_atitude": False}, {}, "melhorado"),
    ("sem modelo de seguimento (τ_modelo = 0)", {"tau_modelo": 0.0}, {}, "melhorado"),
    ("sem feed-forward de arrasto", {"k_arrasto": 0.0}, {}, "melhorado"),
]


def avaliar_config(nome: str, opcoes: dict, est_kw: dict, estimador: str, dr: bool, u_yaw: float,
                   n_jobs: int, sementes=SEMENTES_CALIBRACAO) -> dict:
    base = {"kind": "cascata", "dr": dr, "estimador": estimador, "opcoes": {**opcoes, "u_yaw_por_taxa": u_yaw},
            "est_kw": est_kw}
    jobs = []
    for s_ in sementes[:6]:
        jobs.append({**base, "teste": "degrau", "seed": s_, "v": [1.0, 0.0, 0.0], "tag": "frente"})
        jobs.append({**base, "teste": "degrau", "seed": s_, "v": [0.0, 0.0, 0.7], "alvo_z": 0.5, "janela": 3.6,
                     "t_degrau": 5.0, "tag": "subida"})
    for s_ in sementes:
        jobs.append({**base, "teste": "seguimento", "seed": s_, "T": 10.0})
        jobs.append({**base, "teste": "hover", "seed": s_, "T": 30.0})
    res = executar(jobs, n_jobs)
    pick = lambda teste, tag=None: [r for r, j in zip(res, jobs, strict=True)
                                    if j["teste"] == teste and (tag is None or j.get("tag") == tag)]
    fr, su = agregar(pick("degrau", "frente"), CHAVES["degrau"]), agregar(pick("degrau", "subida"), CHAVES["degrau"])
    sg, hv = agregar(pick("seguimento"), CHAVES["seguimento"]), agregar(pick("hover"), CHAVES["hover"])
    return {"nome": nome, "dr": dr, "terminaram": sum(bool(r.get("terminou")) for r in res),
            "degrau_frente": {k: fr[k] for k in ("sobressinal", "subida_10_90_s", "assenta_5pct_s", "erro_regime",
                                                   "afundamento")},
            "degrau_subida": {k: su[k] for k in ("sobressinal", "subida_10_90_s", "assenta_5pct_s")},
            "seguimento": {k: sg[k] for k in ("v_rms", "xy_rms", "z_rms")},
            "hover": {k: hv[k] for k in ("xy_rms", "dz_rms", "roll_rms_graus", "deriva_rumo_graus")}}


def calibrar(args, dados: dict, ident: dict) -> int:
    t_ini = time.perf_counter()
    n_jobs = max(args.jobs, 1)
    u_yaw = ident["u_yaw_por_taxa"]
    out = {"gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "sementes_calibracao": list(SEMENTES_CALIBRACAO),
           "configuracoes": []}
    print(f"CALIBRAÇÃO nas sementes {SEMENTES_CALIBRACAO[0]}..{SEMENTES_CALIBRACAO[-1]} (NÃO são as de avaliação)")
    for nome, opc, ekw, est in CONFIGS_CALIBRACAO:
        for dr in (False, True):
            r = avaliar_config(nome, opc, ekw, est, dr, u_yaw, n_jobs)
            out["configuracoes"].append(r)
            print(f"  [{time.perf_counter() - t_ini:6.0f} s] {'DR ' if dr else 'nom'} {nome:58s} "
                  f"hover {100 * r['hover']['xy_rms']:5.1f} cm · seg ‖xy‖ {r['seguimento']['xy_rms']:.3f} m "
                  f"‖v‖ {r['seguimento']['v_rms']:.3f} z {r['seguimento']['z_rms']:.3f} · degrau {100 * r['degrau_frente']['sobressinal']:4.1f} % "
                  f"ass5 {r['degrau_frente']['assenta_5pct_s']:.2f} s · term {r['terminaram']}", flush=True)
    caminho = args.json.with_name("calibracao.json")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(limpar(out), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {caminho}")
    return 0


# varredura do YAW (sementes de calibração): quota da folga de acelerador, peso de yaw e a pré-compensação do empuxo
CONFIGS_YAW = [
    ("base (f_yaw 0,6 · peso 0,7 · compensação de equilíbrio)", {}),
    ("f_yaw 0,8", {"f_yaw": 0.8}),
    ("f_yaw 1,0 (toda a folga)", {"f_yaw": 1.0}),
    ("peso de yaw 0,4 (PX4)", {"peso_yaw": 0.4}),
    ("peso de yaw 1,0", {"peso_yaw": 1.0}),
    ("sem pré-compensação do empuxo de yaw", {"comp_yaw_empuxo": False}),
    ("pré-compensação com o termo de aceleração", {"comp_yaw_acel": 1.0}),
    ("u/r da fórmula (arrasto de rotor, 0,56) em vez do identificado", {"u_yaw_por_taxa": 0.5594}),
]


def calibrar_yaw(args, ident: dict) -> int:
    t_ini = time.perf_counter()
    n_jobs = max(args.jobs, 1)
    sem = SEMENTES_CALIBRACAO[:4]
    out = {"gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "sementes_calibracao": list(sem), "configuracoes": []}
    print(f"CALIBRAÇÃO DO YAW nas sementes {sem[0]}..{sem[-1]} (NÃO são as de avaliação)")
    for nome, opc in CONFIGS_YAW:
        opcoes = {"u_yaw_por_taxa": ident["u_yaw_por_taxa"], **opc}
        linha = {"nome": nome}
        for rotulo, teste, extra in (("degrau_90", "yaw_degrau", {"dur": 14.0}), ("arco_0.5", "yaw_arco", {"v": 1.0, "r": 0.5, "dur": 14.0})):
            jobs = jobs_de(teste, "cascata_melhorado", sem, False, ident["u_yaw_por_taxa"], extra)
            for j in jobs:
                j["opcoes"] = dict(opcoes)
            ag = agregar(executar(jobs, n_jobs), CHAVES[teste])
            linha[rotulo] = {k: ag[k] for k in CHAVES[teste]}
            linha[rotulo]["terminaram"] = ag["terminaram"]
        out["configuracoes"].append(linha)
        d, a = linha["degrau_90"], linha["arco_0.5"]
        print(f"  [{time.perf_counter() - t_ini:5.0f} s] {nome:62s} degrau: subida {d['subida_10_90_s']:.2f} s assenta5% {d['assenta_5pct_s']:.2f} s "
              f"|Δz| {100 * d['dz_max']:5.1f} cm roll {d['roll_pico_graus']:.2f}° sat {100 * d['frac_saturado']:.1f} % · arco 0,5: |Δz| {100 * a['dz_max']:.1f} cm "
              f"v {a['vel_media']:.3f} sat {100 * a['frac_saturado']:.1f} % · quedas {d['terminaram'] + a['terminaram']}", flush=True)
    caminho = args.json.with_name("calibracao_yaw.json")
    caminho.write_text(json.dumps(limpar(out), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {caminho}")
    return 0


def limpar(o):
    """Serializável: numpy → python, NaN/inf → None."""
    if isinstance(o, dict):
        return {str(k): limpar(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [limpar(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def jobs_de(teste: str, variante: str, sementes, dr: bool, u_yaw: float, extra: dict | None = None) -> list[dict]:
    kind, est, opc = VARIANTES[variante]
    base = {"kind": kind, "teste": teste, "dr": dr, "variante": variante, **(extra or {})}
    if kind == "cascata":
        base.update({"estimador": est, "opcoes": {**opc, "u_yaw_por_taxa": u_yaw}})
    return [{**base, "seed": s} for s in sementes]


def correr_secao(rotulo: str, jobs: list[dict], n_jobs: int, t_ini: float) -> list[dict]:
    t0 = time.perf_counter()
    res = executar(jobs, n_jobs)
    print(f"  [{time.perf_counter() - t_ini:6.1f} s] {rotulo}: {len(jobs)} episódios em {time.perf_counter() - t0:.1f} s",
          flush=True)
    return res


def agrupar(jobs: list[dict], res: list[dict], chaves: tuple[str, ...], por: str = "variante") -> dict:
    """Agrega por variante sobre as sementes em que NENHUMA variante caiu (mesmas sementes ⇒ comparação pareada e sem
    o viés de excluir só as quedas de uma delas); `quedas` conta as quedas de cada variante em TODAS as sementes."""
    nomes = list(dict.fromkeys(j[por] for j in jobs))
    quedas = {n: sorted({j["seed"] for j, r in zip(jobs, res, strict=True) if j[por] == n and r.get("terminou")})
              for n in nomes}
    excluidas = sorted(set().union(*quedas.values()))
    out: dict = {}
    for n in nomes:
        rs = [r for j, r in zip(jobs, res, strict=True) if j[por] == n and j["seed"] not in excluidas]
        out[n] = agregar(rs, chaves)
        out[n].update({"quedas": len(quedas[n]), "sementes_com_queda": quedas[n], "sementes_excluidas": excluidas,
                       "n_total": sum(1 for j in jobs if j[por] == n)})
        out[n]["por_semente"] = [{"seed": j["seed"], **{c: r.get(c) for c in chaves}, "terminou": r.get("terminou")}
                                 for j, r in zip(jobs, res, strict=True) if j[por] == n]
    return out


def fmt(ag: dict, c: str, casas: int = 3, mult: float = 1.0) -> str:
    v = ag.get(c)
    if v is None or not math.isfinite(v):
        return "—"
    n, tot = ag.get(c + "_n", ag["n"]), ag["n"] - ag["terminaram"]
    txt = f"{mult * v:.{casas}f}±{mult * ag.get(c + '_dp', 0.0):.{casas}f}"
    return txt + (f" ({n}/{tot})" if n < tot else "")


def tabela_md(titulo: str, grupos: dict, linhas: list[tuple[str, str, int, float]], colunas: list[str]) -> str:
    cab = "| " + titulo + " | " + " | ".join(colunas) + " |\n|---|" + "---|" * len(colunas) + "\n"
    corpo = ""
    for rotulo, chave, casas, mult in linhas:
        corpo += f"| {rotulo} | " + " | ".join(fmt(grupos[c], chave, casas, mult) if c in grupos else "—"
                                                 for c in colunas) + " |\n"
    return cab + corpo


def vitorias(grupos: dict, chave: str, a: str, b: str) -> str:
    """Nº de sementes (comuns, sem quedas) em que `a` tem menor `chave` que `b` (mesmas sementes ⇒ mesmos planos)."""
    excl = set(grupos[a].get("sementes_excluidas", []))
    pa = {x["seed"]: x[chave] for x in grupos[a]["por_semente"] if x.get(chave) is not None and x["seed"] not in excl}
    pb = {x["seed"]: x[chave] for x in grupos[b]["por_semente"] if x.get(chave) is not None and x["seed"] not in excl}
    comuns = [k for k in pa if k in pb and math.isfinite(pa[k]) and math.isfinite(pb[k])]
    return f"{sum(pa[k] < pb[k] for k in comuns)}/{len(comuns)}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--rapido", action="store_true", help="3 sementes (fumo)")
    p.add_argument("--sementes", type=int, default=len(SEMENTES_AVALIACAO))
    p.add_argument("--jobs", type=int, default=min(8, (os.cpu_count() or 2) - 1))
    p.add_argument("--json", type=Path, default=SAIDA_JSON)
    p.add_argument("--sem-rl", action="store_true", help="não avalia a RL (só a cascata)")
    p.add_argument("--calibrar", action="store_true",
                   help="varredura de ganhos/estimador NAS SEMENTES DE CALIBRAÇÃO (grava calibracao.json) e sai")
    p.add_argument("--calibrar-yaw", action="store_true",
                   help="varredura do yaw (quota da folga, peso, pré-compensação) nas sementes de calibração")
    args = p.parse_args(argv)
    sementes = SEMENTES_AVALIACAO[:3] if args.rapido else SEMENTES_AVALIACAO[: args.sementes]
    n_jobs = max(args.jobs, 1)
    dados = carregar_rl_dados()
    build, motivo = build_do_hardware(dados)
    t_ini = time.perf_counter()
    print(f"AVALIAÇÃO cascata clássica vs RL · build {build!r} ({motivo}) · {len(sementes)} sementes de avaliação "
          f"{sementes[0]}..{sementes[-1]} (calibração {SEMENTES_CALIBRACAO[0]}..{SEMENTES_CALIBRACAO[-1]} NÃO entram) · "
          f"{n_jobs} processos · SEM VENTO", flush=True)
    variantes = [v for v in VARIANTES if not (args.sem_rl and v == "rl")]
    # 0. planta → ganhos → margens; identificação do yaw no simulador
    print("0. identificação do yaw + ganhos derivados da planta", flush=True)
    ident = identificar_yaw(dados, n_jobs)
    if args.calibrar:
        return calibrar(args, dados, ident)
    if args.calibrar_yaw:
        return calibrar_yaw(args, ident)
    env0 = criar_env(dados, dr=False, episodio_s=1.0)
    gn = cc.ganhos_de_hardware(env0, u_yaw_por_taxa=ident["u_yaw_por_taxa"],
                               altura_min=VOO_Z_MIN - deslocamento_sensor_cm(env0))
    margens = cc.margens_cascata(env0, gn)
    u_yaw = ident["u_yaw_por_taxa"]
    resultado: dict = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "build": build, "modelo_rl": str(MODELO_RL.relative_to(_AQUI)),
        "protocolo": {"sementes_avaliacao": list(sementes), "sementes_calibracao": list(SEMENTES_CALIBRACAO),
                      "janela_hover_s": list(JANELA_HOVER), "janela_seguimento_t0_s": JANELA_SEGUIMENTO_T0,
                      "calibracao_giro_s": T_CALIBRACAO_GIRO, "vento": "nenhum (fase 1)",
                      "decimacao": 10, "dt_fisica_s": 0.002, "dt_decisao_s": 0.02},
        "ganhos": {k: getattr(gn, k) for k in cc.GanhosCascata.__dataclass_fields__ if k != "notas"},
        "ganhos_notas": gn.notas, "margens": margens, "identificacao_yaw": ident, "secoes": {}}
    sec = resultado["secoes"]
    for dr in (False, True):
        etiqueta = "dr" if dr else "nominal"
        s_ = sec.setdefault(etiqueta, {})
        print(f"== {'COM' if dr else 'SEM'} domain randomization", flush=True)
        # (a) hover 30 s
        jobs = [j for v in variantes if v != "cascata_melhorado_ref"
                for j in jobs_de("hover", v, sementes, dr, u_yaw, {"T": 30.0})]
        s_["hover"] = agrupar(jobs, correr_secao(f"hover 30 s ({etiqueta})", jobs, n_jobs, t_ini), CHAVES["hover"])
        s_["vitorias"] = {}
        # (c) seguimento de planos
        jobs = [j for v in variantes for j in jobs_de("seguimento", v, sementes, dr, u_yaw, {"T": 10.0})]
        s_["seguimento"] = agrupar(jobs, correr_secao(f"seguimento ({etiqueta})", jobs, n_jobs, t_ini),
                                   CHAVES["seguimento"])
        if "rl" in s_["hover"]:
            for alvo in ("cascata_bordo", "cascata_melhorado"):
                s_["vitorias"][f"hover_xy_rms:{alvo}<rl"] = vitorias(s_["hover"], "xy_rms", alvo, "rl")
            for alvo in ("cascata_melhorado", "cascata_melhorado_ref"):
                for ch in ("v_rms", "xy_rms", "z_rms"):
                    s_["vitorias"][f"seguimento_{ch}:{alvo}<rl"] = vitorias(s_["seguimento"], ch, alvo, "rl")
        # (b) degraus
        s_["degraus"] = {}
        for nome, (v_cmd, extra) in DEGRAUS.items():
            jobs = [j for v in variantes for j in jobs_de("degrau", v, sementes, dr, u_yaw, {"v": v_cmd, **extra})]
            s_["degraus"][nome] = agrupar(jobs, correr_secao(f"degrau {nome} ({etiqueta})", jobs, n_jobs, t_ini),
                                          CHAVES["degrau"])
        # (d) yaw (só a cascata)
        s_["yaw"] = {}
        for nome, teste, extra in (("degrau_90", "yaw_degrau", {"dur": 14.0}),
                                   ("taxa_0.5", "yaw_taxa", {"r": 0.5, "dur": 10.0}),
                                   ("arco_0.3", "yaw_arco", {"v": 1.0, "r": 0.3, "dur": 14.0}),
                                   ("arco_0.5", "yaw_arco", {"v": 1.0, "r": 0.5, "dur": 14.0})):
            jobs = jobs_de(teste, "cascata_melhorado", sementes, dr, u_yaw, extra)
            s_["yaw"][nome] = agrupar(jobs, correr_secao(f"yaw {nome} ({etiqueta})", jobs, n_jobs, t_ini),
                                      CHAVES[teste])["cascata_melhorado"]
    resultado["duracao_s"] = time.perf_counter() - t_ini
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(limpar(resultado), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {args.json} ({resultado['duracao_s']:.0f} s)")
    imprimir_resumo(resultado, variantes)
    return 0


def imprimir_resumo(r: dict, variantes: list[str]) -> None:
    cols = [v for v in variantes]
    for etiqueta, s_ in r["secoes"].items():
        print(f"\n#### {etiqueta.upper()}")
        for secao in ("hover", "seguimento"):
            g = s_[secao]
            print(f"({secao}: quedas " + ", ".join(f"{k}={v['quedas']}/{v['n_total']}" for k, v in g.items())
                  + f" · médias sobre as sementes sem queda em NENHUMA variante, excluídas {next(iter(g.values()))['sementes_excluidas']})")
        print("vitórias (menor erro, sementes comuns): " + ", ".join(f"{k}={v}" for k, v in s_["vitorias"].items()))
        print(tabela_md("hover 30 s", s_["hover"], [
            ("‖xy‖ RMS (cm)", "xy_rms", 1, 100), ("‖xy‖ máx (cm)", "xy_max", 1, 100), ("|Δz| RMS (cm)", "dz_rms", 1, 100),
            ("roll RMS (°)", "roll_rms_graus", 2, 1), ("pitch RMS (°)", "pitch_rms_graus", 2, 1),
            ("deriva de rumo (°)", "deriva_rumo_graus", 1, 1), ("RMS Δu / 2 ms", "du_rms", 4, 1),
            ("potência (W)", "p_media_w", 1, 1)], [c for c in cols if c in s_["hover"]]))
        print(tabela_md("seguimento", s_["seguimento"], [
            ("‖v−v_ref‖ RMS (m/s)", "v_rms", 3, 1), ("‖xy−p_ref‖ RMS (m)", "xy_rms", 3, 1),
            ("|z−z_ref| RMS (m)", "z_rms", 3, 1)], cols))
        for nome, g in s_["degraus"].items():
            print(tabela_md(f"degrau {nome}", g, [
                ("subida 10–90 % (s)", "subida_10_90_s", 2, 1), ("sobressinal (%)", "sobressinal", 1, 100),
                ("assentamento 2 % (s)", "assenta_2pct_s", 2, 1), ("assentamento 5 % (s)", "assenta_5pct_s", 2, 1),
                ("erro de regime (m/s)", "erro_regime", 3, 1)], cols))
        for nome, ag in s_["yaw"].items():
            print(f"yaw {nome}: " + ", ".join(f"{c}={fmt(ag, c)}" for c in CHAVES[
                {"degrau_90": "yaw_degrau", "taxa_0.5": "yaw_taxa"}.get(nome, "yaw_arco")][:6]))


if __name__ == "__main__":
    sys.exit(main())
