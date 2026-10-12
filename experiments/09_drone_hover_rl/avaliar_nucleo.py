"""experiments/09_drone_hover_rl/avaliar_nucleo.py — o NÚCLEO DE FIRMWARE C++ no laço FECHADO com o MuJoCo: C++ vs Python vs RL.

A B0 (`avaliar_classico.py`) mediu a cascata clássica em Python (float64) contra a política RL `out/real_1950_voo_final/final.zip`.
Esta atividade (B) portou-a para o núcleo C++ float32 (`firmware/nucleo/`: `estimador_classico.hpp` + `cascata.hpp` + `taxa.hpp`
+ IBVS) e fecha o laço com o MuJoCo em SITL (`sitl.py`, modo cascata): o C++ manda nos motores e vê SÓ os sensores medidos. Aqui
repete-se o PROTOCOLO da B0 com o C++ — mesma planta (build `endurance_15pol_p50b` do `hardware.json` da política), mesmas
sementes de avaliação (5000…5011 ⇒ os mesmos planos WASDQE, o mesmo ruído dos sensores e, com DR, as mesmas peças sorteadas),
mesmas janelas e métricas — SEM VENTO:

  (a) HOVER 30 s · (b) DEGRAUS de velocidade (frente, subida, lateral) · (c) SEGUIMENTO de planos WASDQE aleatórios ·
  (d) YAW (degrau de 90°, taxa de 0,5 rad/s, arcos a 1 m/s com 0,3 e 0,5 rad/s) · (e) tudo com DOMAIN RANDOMIZATION ·
  (f) OLHAR para o círculo (frames mono QVGA renderizados + detetor C++ + IBVS) com a latência do Pi (116 ms) e do DCMI (21 ms).

Variantes: `nucleo_cpp` (este código C++, ganhos DA PLANTA NOMINAL — o firmware não conhece o sorteio do DR) · `python_vivo` (o
protótipo `ControladorCascata` + `EstimadorClassico`, corrido AGORA, com os ganhos re-derivados por episódio como na B0) ·
`python_nominal` (o mesmo protótipo com os ganhos da planta nominal FIXOS — a comparação limpa com o C++ no DR) · `python_b0` e
`rl_b0` (os números PUBLICADOS da B0 em `out/classico/avaliacao.json`; a RL não se volta a correr: não é o assunto).

REGRAS DE HONESTIDADE
  · NENHUM ganho foi afinado aqui: a Config sai de `ganhos_de_hardware(env)` (planta) com o `u_yaw_por_taxa` IDENTIFICADO pela B0
    nas sementes de CALIBRAÇÃO (9000…); as de avaliação (5000…5011) não servem para afinar nada;
  · a métrica de seguimento é a do env (referência `p_ref` no referencial do MUNDO), como na B0;
  · MEDIDO = números desta corrida; INFERIDO = leitura/explicação (marcado como tal no README).

    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_nucleo.py --rapido
    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_nucleo.py --json out/nucleo/avaliacao.json
    uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_nucleo.py --so-olhar
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

import avaliar_classico as ac
import controlo_classico as cc
import sitl
from env import VOO_Z_MIN
from env_real import build_do_hardware

SAIDA_JSON = _AQUI / "out" / "nucleo" / "avaliacao.json"
JSON_B0 = _AQUI / "out" / "classico" / "avaliacao.json"
SEMENTES_AVALIACAO = ac.SEMENTES_AVALIACAO
BUILD_ARDUINO = "endurance_15pol_arduino"
LATENCIA_PI_S, LATENCIA_DCMI_S = 0.116, 0.021
T_OLHAR_S = 4.0                       # descola e segura 4 s (modo VELOCIDADE) antes de OLHAR; o alvo só começa a mexer aqui
JANELA_OLHAR_S = 4.0                  # as métricas do olhar ignoram os primeiros 4 s depois de ligar o IBVS (aquisição)
RAIO_TRAJETORIA_M = 1.5               # o do `env_real.definir_trajetoria_ponto`

VARIANTES_CPP = ("nucleo_cpp", "python_vivo", "python_nominal")


# ------------------------------------------------------------------------------------------------ ganhos e env
def u_yaw_identificado(dados: dict | None = None) -> float:
    """O `u/r` de yaw IDENTIFICADO pela B0 (sementes de calibração; `identificacao_yaw` do JSON publicado)."""
    if JSON_B0.is_file():
        return float(json.loads(JSON_B0.read_text(encoding="utf-8"))["identificacao_yaw"]["u_yaw_por_taxa"])
    return float(cc.GanhosCascata().u_yaw_por_taxa)


def criar_env_nucleo(dados: dict, *, dr: bool, episodio_s: float, aleatorios: bool = False, alvo_z: float = 1.0,
                     u_yaw: float | None = None, cascata: dict | None = None, build=None, com_alvo: bool = False):
    """`DroneRealEnvNucleo` em modo cascata com os MESMOS argumentos do `avaliar_classico.criar_env`."""
    b = build if build is not None else build_do_hardware(dados)[0]
    opcoes = {"u_yaw_por_taxa": u_yaw if u_yaw is not None else u_yaw_identificado(), **(cascata or {})}
    return sitl.DroneRealEnvNucleo(build=b, modo_acao=dados.get("modo_acao", "ctbr"), aleatorizar=dr, comando=True,
                                   comandos_aleatorios=aleatorios, episodio_s=episodio_s, alvo_z=alvo_z,
                                   com_alvo=com_alvo, modo_nucleo="cascata", cascata=opcoes)


def ganhos_nominais(dados: dict, u_yaw: float) -> cc.GanhosCascata:
    """Os ganhos da cascata Python da planta NOMINAL (sem DR) — os que o C++ tem na Config."""
    env = ac.criar_env(dados, dr=False, episodio_s=1.0)
    return cc.ganhos_de_hardware(env, u_yaw_por_taxa=u_yaw, altura_min=VOO_Z_MIN - ac.deslocamento_sensor_cm(env))


# ------------------------------------------------------------------------------------------------ um episódio
def _executar(teste: str, job: dict, criar_env, criar_ctrl) -> dict:
    """O despacho de `avaliar_classico.tarefa`, com fábricas de env e controlador (para o C++ e o Python de ganhos fixos)."""
    seed = job["seed"]
    if teste == "hover":
        T = job.get("T", 30.0)
        env = criar_env(T, False, 1.0)
        reg = ac.correr(env, criar_ctrl(None), seed, T)
        return ac.metricas_hover(reg)
    if teste == "seguimento":
        T = job.get("T", 10.0)
        env = criar_env(T, True, 1.0)
        reg = ac.correr(env, criar_ctrl(None), seed, T)
        return ac.metricas_seguimento(reg)
    if teste == "degrau":
        v = np.array(job["v"], dtype=float)
        t_deg, janela = job.get("t_degrau", 6.0), job.get("janela", 8.0)
        T = t_deg + janela + 0.5
        env = criar_env(T, False, job.get("alvo_z", 1.0))
        reg = ac.correr(env, criar_ctrl(None), seed, T, cmd_mundo=lambda t: v if t >= t_deg else np.zeros(3))
        return ac.metricas_degrau(reg, t_deg, v, janela)
    if teste in ("yaw_degrau", "yaw_taxa", "yaw_arco"):
        t0y = 6.0
        env = criar_env(t0y + job["dur"] + 0.5, False, 1.0)
        if teste == "yaw_degrau":
            alvo = job.get("alvo", math.pi / 2)
            cmd_fn = lambda t: ({"modo": "yaw_alvo", "yaw": alvo} if t >= t0y else {})
        elif teste == "yaw_taxa":
            cmd_fn = lambda t: ({"yaw_taxa": job["r"]} if t >= t0y else {})
        else:
            cmd_fn = lambda t: ({"vx": job["v"], "yaw_taxa": job["r"]} if t >= t0y else {})
        reg = ac.correr(env, criar_ctrl(cmd_fn), seed, t0y + job["dur"])
        if teste == "yaw_degrau":
            return ac.metricas_yaw_degrau(reg, t0y, alvo, job["dur"])
        if teste == "yaw_taxa":
            return ac.metricas_yaw_taxa(reg, t0y, job["r"], job["dur"])
        return ac.metricas_yaw_arco(reg, t0y, job["v"], job["r"], job["dur"])
    raise ValueError(f"teste desconhecido: {teste}")


def tarefa(job: dict) -> dict:
    """Um episódio → métricas (função de topo: serializável para o `multiprocessing`)."""
    kind, teste = job["kind"], job["teste"]
    t0 = time.perf_counter()
    dados = ac.carregar_rl_dados()
    if kind == "olhar":
        out = tarefa_olhar(job, dados)
    elif kind == "ident":                              # identificação do yaw NUM build (o `ac.tarefa` só vê o do hardware.json da RL)
        out = ac.identificar_yaw_um({**dados, "build": job["build"]}, job["seed"], job["r"], job["dur"])
    elif kind == "nucleo":
        u_yaw = job["u_yaw"]
        out = _executar(
            teste, job,
            lambda T, aleatorios, alvo_z: criar_env_nucleo(dados, dr=job["dr"], episodio_s=T, aleatorios=aleatorios,
                                                           alvo_z=alvo_z, u_yaw=u_yaw, cascata=job.get("cascata")),
            lambda cmd_fn: sitl.ControladorNucleo(cmd_fn))
    elif kind == "python_nominal":
        gn = ganhos_nominais(dados, job["u_yaw"])
        out = _executar(
            teste, job,
            lambda T, aleatorios, alvo_z: ac.criar_env(dados, dr=job["dr"], episodio_s=T, aleatorios=aleatorios,
                                                       alvo_z=alvo_z),
            lambda cmd_fn: ac.ControladorCascata(ganhos=gn, estimador="melhorado", cmd_fn=cmd_fn))
    elif kind == "python_vivo":                       # o protótipo da B0, tal e qual (ganhos re-derivados por episódio)
        out = ac.tarefa({"kind": "cascata", "teste": teste, "seed": job["seed"], "dr": job["dr"],
                         "estimador": "melhorado", "opcoes": {"u_yaw_por_taxa": job["u_yaw"]},
                         **{k: v for k, v in job.items() if k in ("T", "v", "t_degrau", "janela", "alvo_z", "dur", "r", "alvo")}})
    else:
        raise ValueError(f"kind desconhecido: {kind}")
    out.update({"kind": kind, "teste": teste, "seed": job["seed"], "dr": job["dr"], "parede_s": time.perf_counter() - t0})
    return out


# ------------------------------------------------------------------------------------------------ OLHAR (f)
def _los_rate(t: np.ndarray, az: np.ndarray) -> np.ndarray:
    """Taxa (rad/s) do azimute VERDADEIRO do alvo (no referencial do mundo), por diferenças centrais."""
    return np.gradient(np.unwrap(az), t)


def tarefa_olhar(job: dict, dados: dict) -> dict:
    """OLHAR para o alvo: descola e segura (VELOCIDADE), liga o IBVS a T_OLHAR_S e o alvo começa a mexer nesse instante.

    Câmara mono QVGA renderizada (EGL) a 30 Hz, com a latência `job["latencia"]`; o detetor e o IBVS são o C++ do núcleo.
    Métricas (verdade só para MEDIR): erro de rumo do alvo face ao eixo da câmara, erro de distância |D − d*|, elevação,
    fração do tempo em A_SEGUIR, fração de frames com deteção válida, fração do tempo com o yaw no limite e a taxa de
    linha de vista VERDADEIRA do alvo (o que o yaw teria de seguir) — tudo depois de JANELA_OLHAR_S de aquisição.
    """
    build = BUILD_ARDUINO if job.get("build") == "arduino" else build_do_hardware(dados)[0]
    T = job.get("T", 30.0)
    seed = job["seed"]
    camera = {"latencia_s": job["latencia"], "fps": 30.0}
    if job.get("seguidor"):
        camera["seguidor"] = job["seguidor"]
    env = criar_env_nucleo(dados, dr=job.get("dr", False), episodio_s=T, u_yaw=job["u_yaw"], com_alvo=True, build=build,
                           cascata={"camera": camera, "ganhos_kw": job.get("ganhos_kw") or {}})
    env.ponto_modo, env.ponto_vel, env.ponto_raio = "parado", job["vel"], RAIO_TRAJETORIA_M
    env.reset(seed=seed)
    n = round(T / env.dt_decisao)
    k_olhar = round(T_OLHAR_S / env.dt_decisao)
    cfg_c = env.nucleo.cfg.cascata
    dist_alvo = float(env.nucleo.cfg.seguidor.dist_alvo_m)       # d* do IBVS (visao::config_padrao: 1,5 m)
    tg = []
    for k in range(n):
        if k == k_olhar:
            env.definir_trajetoria_ponto(job["modo"], vel=job["vel"], raio=RAIO_TRAJETORIA_M)
        env.fc.definir_comando({"modo": "olhar"} if k >= k_olhar else {})
        _o, _r, term, _tr, _i = env.step(np.zeros(4, dtype=np.float32))
        d = env._derivados()
        s = env.nucleo.saida
        yaw = d["yaw"]
        cam = np.array([d["x"], d["y"], d["z"]]) + np.array([0.115 * math.cos(yaw), 0.115 * math.sin(yaw), 0.025])
        rel = np.array(env.ponto_alvo) - cam
        az = math.atan2(rel[1], rel[0])
        tg.append((k * env.dt_decisao, (az - yaw + math.pi) % (2 * math.pi) - math.pi, az,
                   math.atan2(rel[2], math.hypot(rel[0], rel[1])), float(np.linalg.norm(rel)), int(s.seguidor.estado),
                   float(s.yaw_taxa_ref), int(s.seguidor.flags), int(s.flags), d["z"], d["theta"], d["phi"]))
        if term:
            break
    r = np.array(tg)
    est = env.camera_sitl.estatisticas()
    env.close()
    caiu = len(r) < n
    m = r[:, 0] >= T_OLHAR_S + JANELA_OLHAR_S
    if caiu or not m.any():
        return {"terminou": True}
    los = _los_rate(r[:, 0], r[:, 2])
    # o que a opção «lateral assist» (v_y ∝ velocidade tangencial do alvo quando o yaw satura) teria de fornecer: o excesso da taxa de linha de
    # vista VERDADEIRA sobre o teto de yaw, vezes a distância — NÃO está implementado (só medido)
    excesso = np.maximum(np.abs(los[m]) - float(cfg_c.taxa_yaw_max), 0.0) * r[m, 4]
    seguir = r[m, 5] == 0
    sat_yaw = np.abs(r[m, 6]) >= 0.999 * cfg_c.taxa_yaw_max
    return {"terminou": False,
            "rumo_rms_graus": math.degrees(float(np.sqrt(np.mean(r[m, 1] ** 2)))),
            "rumo_max_graus": math.degrees(float(np.abs(r[m, 1]).max())),
            "dist_erro_rms": float(np.sqrt(np.mean((r[m, 4] - dist_alvo) ** 2))),
            "elev_rms_graus": math.degrees(float(np.sqrt(np.mean(r[m, 3] ** 2)))),
            "frac_a_seguir": float(np.mean(seguir)), "frac_frames_validos": est["frac_validos"],
            "frac_yaw_no_limite": float(np.mean(sat_yaw)),
            "los_taxa_max": float(np.abs(los[m]).max()), "los_taxa_p95": float(np.percentile(np.abs(los[m]), 95)),
            "frac_los_acima_do_teto": float(np.mean(excesso > 0.0)), "vy_assist_p95": float(np.percentile(excesso, 95)),
            "vy_assist_max": float(excesso.max()),
            "yaw_teto": float(cfg_c.taxa_yaw_max), "yaw_acel_teto": float(cfg_c.acel_yaw_max),
            "z_min": float(r[:, 9].min()), "roll_max_graus": math.degrees(float(np.abs(r[:, 11]).max())),
            "frames": est["frames"], "render_ms": est["render_ms_mediana"], "detetor_ms": est["detetor_ms_mediana"]}


# ------------------------------------------------------------------------------------------------ execução
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


def _jobs(teste: str, variante: str, sementes, dr: bool, u_yaw: float, extra: dict | None = None) -> list[dict]:
    kind = {"nucleo_cpp": "nucleo"}.get(variante, variante)
    return [{"kind": kind, "variante": variante, "teste": teste, "seed": s, "dr": dr, "u_yaw": u_yaw, **(extra or {})}
            for s in sementes]


def correr_secao(rotulo: str, jobs: list[dict], n_jobs: int, t_ini: float) -> list[dict]:
    t0 = time.perf_counter()
    res = executar(jobs, n_jobs)
    print(f"  [{time.perf_counter() - t_ini:6.1f} s] {rotulo}: {len(jobs)} episódios em {time.perf_counter() - t0:.1f} s",
          flush=True)
    return res


def _publicado(b0: dict, etq: str, secao: str, nome_b0: str, sub: str | None = None):
    """O grupo agregado PUBLICADO da B0 (`out/classico/avaliacao.json`) para a variante `nome_b0`."""
    try:
        g = b0["secoes"][etq][secao]
        if sub is not None:
            g = g[sub]
        return g.get(nome_b0)
    except KeyError:
        return None


def _excluidas_b0(b0: dict, etq: str, rotulo: str) -> list[int]:
    """As sementes que a B0 excluiu das médias da secção (onde alguma variante — a RL — caiu)."""
    for nome_b0 in ("rl", "cascata_melhorado"):
        for caminho in ((rotulo,), ("degraus", rotulo.split("_", 1)[-1]), ("yaw", rotulo.split("_", 1)[-1])):
            try:
                g = b0["secoes"][etq]
                for k in caminho:
                    g = g[k]
                if nome_b0 in g:
                    return list(g[nome_b0].get("sementes_excluidas") or [])
            except (KeyError, TypeError):
                continue
    return []


def diferenca_relativa(grupos: dict, chave: str, a: str = "nucleo_cpp", b: str = "python_vivo") -> dict:
    """Diferença C++ − Python por semente (comum, sem quedas) numa métrica: média e máximo de |Δ|/|Python| e Δ da média."""
    pa = {x["seed"]: x[chave] for x in grupos[a]["por_semente"] if x.get(chave) is not None and np.isfinite(x[chave])}
    pb = {x["seed"]: x[chave] for x in grupos[b]["por_semente"] if x.get(chave) is not None and np.isfinite(x[chave])}
    s = sorted(set(pa) & set(pb))
    if not s:
        return {"n": 0}
    va, vb = np.array([pa[k] for k in s]), np.array([pb[k] for k in s])
    rel = np.abs(va - vb) / np.maximum(np.abs(vb), 1e-9)
    return {"n": len(s), "media_cpp": float(va.mean()), "media_py": float(vb.mean()),
            "dif_media_pct": 100.0 * float((va.mean() - vb.mean()) / max(abs(vb.mean()), 1e-9)),
            "dif_rel_media_pct": 100.0 * float(rel.mean()), "dif_rel_max_pct": 100.0 * float(rel.max())}


SECOES_METRICAS = {
    "hover": ["xy_rms", "dz_rms", "roll_rms_graus", "pitch_rms_graus", "deriva_rumo_graus", "p_media_w"],
    "seguimento": ["v_rms", "xy_rms", "z_rms", "xy_medio_2a_metade"],
    "degrau_frente": ["sobressinal", "subida_10_90_s", "erro_regime"],
    "yaw_degrau_90": ["subida_10_90_s", "assenta_5pct_s", "dz_max"],
    "yaw_arco_0.5": ["raio_ajustado", "vel_media", "dz_max"],
}


def avaliar_protocolo(args, dados: dict, u_yaw: float, b0: dict) -> dict:
    sementes = SEMENTES_AVALIACAO[:3] if args.rapido else SEMENTES_AVALIACAO[: args.sementes]
    t_ini = time.perf_counter()
    resultado: dict = {}
    for dr in (False, True):
        etq = "dr" if dr else "nominal"
        print(f"== {'COM' if dr else 'SEM'} domain randomization", flush=True)
        s_: dict = {}
        variantes = ["nucleo_cpp", "python_vivo"] + (["python_nominal"] if dr else [])
        testes = [("hover", {"T": 30.0}, "hover"), ("seguimento", {"T": 10.0}, "seguimento")]
        for nome, (v_cmd, extra) in ac.DEGRAUS.items():
            testes.append(("degrau", {"v": v_cmd, **extra}, f"degrau_{nome}"))
        for nome, teste, extra in (("degrau_90", "yaw_degrau", {"dur": 14.0}), ("taxa_0.5", "yaw_taxa", {"r": 0.5, "dur": 10.0}),
                                   ("arco_0.3", "yaw_arco", {"v": 1.0, "r": 0.3, "dur": 14.0}),
                                   ("arco_0.5", "yaw_arco", {"v": 1.0, "r": 0.5, "dur": 14.0})):
            testes.append((teste, extra, f"yaw_{nome}"))
        for teste, extra, rotulo in testes:
            jobs = [j for v in variantes for j in _jobs(teste, v, sementes, dr, u_yaw, extra)]
            chaves = ac.CHAVES[{"degrau": "degrau"}.get(teste, teste)]
            res = correr_secao(f"{rotulo} ({etq})", jobs, args.jobs, t_ini)
            # a B0 agrega só sobre as sementes em que NENHUMA variante caiu — a RL incluída (no DR a RL cai na 5007): para as colunas
            # ficarem PAREADAS exclui-se também aqui o que a B0 excluiu (as séries por semente completas ficam no JSON)
            excl = set(_excluidas_b0(b0, etq, rotulo))
            pares = [(j, r) for j, r in zip(jobs, res, strict=True) if j["seed"] not in excl]
            s_[rotulo] = ac.agrupar([j for j, _ in pares], [r for _, r in pares], chaves)
            for v in s_[rotulo].values():
                v["sementes_excluidas_b0"] = sorted(excl)
            # os números PUBLICADOS da B0 (Python e RL), para mostrar lado a lado
            if rotulo in ("hover", "seguimento"):
                for k_b0, nome_b0 in (("python_b0", "cascata_melhorado"), ("rl_b0", "rl")):
                    g = _publicado(b0, etq, rotulo, nome_b0)
                    if g is not None:
                        s_[rotulo][k_b0] = g
            elif rotulo.startswith("degrau_"):
                for k_b0, nome_b0 in (("python_b0", "cascata_melhorado"), ("rl_b0", "rl")):
                    g = _publicado(b0, etq, "degraus", nome_b0, rotulo.split("_", 1)[1])
                    if g is not None:
                        s_[rotulo][k_b0] = g
            elif rotulo.startswith("yaw_"):
                g = b0.get("secoes", {}).get(etq, {}).get("yaw", {}).get(rotulo.split("_", 1)[1])
                if g is not None:
                    s_[rotulo]["python_b0"] = g
        s_["equivalencia"] = {}
        for rotulo, chaves in SECOES_METRICAS.items():
            if rotulo in s_:
                par = "python_nominal" if dr and "python_nominal" in s_[rotulo] else "python_vivo"
                s_["equivalencia"][rotulo] = {c: diferenca_relativa(s_[rotulo], c, "nucleo_cpp", par) for c in chaves}
        resultado[etq] = s_
    resultado["duracao_s"] = time.perf_counter() - t_ini
    return resultado


def identificar_yaw_build(dados: dict, build: str, n_jobs: int, seed: int = ac.SEMENTES_CALIBRACAO[0]) -> float:
    """O `u/r` de yaw IDENTIFICADO no simulador para `build` (a mesma receita do `avaliar_classico.identificar_yaw`: taxas de 0,1 a
    0,5 rad/s sem limites, o integral do PID de yaw do FC em regime é o acelerador diferencial que vence o arrasto; declive pela origem;
    semente de CALIBRAÇÃO)."""
    jobs = [{"kind": "ident", "variante": "ident", "teste": "ident_yaw", "seed": seed, "dr": False, "u_yaw": 0.0, "build": build,
             "r": r, "dur": 10.0} for r in (0.1, 0.2, 0.3, 0.4, 0.5)]
    res = executar(jobs, n_jobs)
    r_ss = np.array([x["r_ss"] for x in res])
    i_z = np.array([x["i_z"] for x in res])
    return float(np.sum(i_z * r_ss) / np.sum(r_ss * r_ss))


def avaliar_olhar(args, dados: dict, u_yaw: float) -> dict:
    """(f) OLHAR: círculo/oito a várias velocidades × {Pi 116 ms, DCMI 21 ms} (+ sensibilidade ao teto de yaw)."""
    t_ini = time.perf_counter()
    sementes = (7000, 7001, 7002) if not args.rapido else (7000,)
    u_ard = u_yaw
    if not args.rapido:
        # o build Arduino tem a SUA planta (massa, motores): o `u/r` de yaw identifica-se nele (sementes de calibração)
        u_ard = identificar_yaw_build(dados, BUILD_ARDUINO, min(args.jobs, 6))
        print(f"  identificação do yaw no build Arduino: u/r = {u_ard:.4f} (p50b: {u_yaw:.4f})", flush=True)
    casos = [("circulo", v) for v in (0.3, 0.5, 0.6, 0.7, 0.8)] + [("oito", v) for v in (0.3, 0.5, 0.8)]
    if args.rapido:
        casos = [("circulo", 0.5), ("circulo", 0.8)]
    configs = [("pi_116ms", None, LATENCIA_PI_S, u_yaw), ("arduino_21ms", "arduino", LATENCIA_DCMI_S, u_ard)]
    jobs = [{"kind": "olhar", "variante": f"{nome}:{modo}:{v}", "teste": "olhar", "seed": s, "dr": False, "u_yaw": u,
             "build": b, "latencia": lat, "modo": modo, "vel": v, "T": 30.0}
            for nome, b, lat, u in configs for modo, v in casos for s in sementes]
    sens = [] if args.rapido else [{"kind": "olhar", "variante": f"sens_yaw_0.8:{modo}:{v}", "teste": "olhar", "seed": s,
                                    "dr": False, "u_yaw": u_yaw, "build": None, "latencia": LATENCIA_PI_S, "modo": modo,
                                    "vel": v, "T": 30.0, "ganhos_kw": {"taxa_yaw_max": 0.8, "acel_yaw_max": 1.5}}
                                   for modo, v in (("circulo", 0.6), ("circulo", 0.8), ("oito", 0.5), ("oito", 0.8)) for s in sementes]
    res = correr_secao("OLHAR (círculo/oito)", jobs + sens, args.jobs, t_ini)
    return ac.agrupar(jobs + sens, res, ("rumo_rms_graus", "rumo_max_graus", "dist_erro_rms", "elev_rms_graus",
                                         "frac_a_seguir", "frac_frames_validos", "frac_yaw_no_limite", "los_taxa_max",
                                         "los_taxa_p95", "frac_los_acima_do_teto", "vy_assist_p95", "vy_assist_max", "z_min", "roll_max_graus",
                                         "render_ms", "detetor_ms"))


# ------------------------------------------------------------------------------------------------ relatório
def imprimir_protocolo(r: dict) -> None:
    cols_h = ["nucleo_cpp", "python_vivo", "python_nominal", "python_b0", "rl_b0"]
    for etq in ("nominal", "dr"):
        if etq not in r:
            continue
        s_ = r[etq]
        print(f"\n#### {etq.upper()}")
        for rotulo in ("hover", "seguimento"):
            g = s_[rotulo]
            cols = [c for c in cols_h if c in g]
            print(f"({rotulo}: quedas " + ", ".join(f"{k}={g[k].get('quedas', '—')}/{g[k].get('n_total', g[k].get('n', '—'))}"
                                                    for k in cols) + ")")
        print(ac.tabela_md("hover 30 s", s_["hover"], [
            ("‖xy‖ RMS (cm)", "xy_rms", 1, 100), ("‖xy‖ máx. (cm)", "xy_max", 1, 100), ("|Δz| RMS (cm)", "dz_rms", 1, 100),
            ("roll RMS (°)", "roll_rms_graus", 2, 1), ("pitch RMS (°)", "pitch_rms_graus", 2, 1),
            ("deriva de rumo (°)", "deriva_rumo_graus", 1, 1), ("RMS Δu / 2 ms", "du_rms", 4, 1),
            ("potência (W)", "p_media_w", 1, 1)], [c for c in cols_h if c in s_["hover"]]))
        print(ac.tabela_md("seguimento", s_["seguimento"], [
            ("‖v−v_ref‖ RMS (m/s)", "v_rms", 3, 1), ("‖xy−p_ref‖ RMS (m)", "xy_rms", 3, 1),
            ("|z−z_ref| RMS (m)", "z_rms", 3, 1), ("‖xy−p_ref‖ 2.ª metade (m)", "xy_medio_2a_metade", 3, 1)],
            [c for c in cols_h if c in s_["seguimento"]]))
        for nome in ("frente", "subida", "lateral"):
            g = s_[f"degrau_{nome}"]
            print(ac.tabela_md(f"degrau {nome}", g, [
                ("subida 10–90 % (s)", "subida_10_90_s", 2, 1), ("sobressinal (%)", "sobressinal", 1, 100),
                ("assentamento 2 % (s)", "assenta_2pct_s", 2, 1), ("assentamento 5 % (s)", "assenta_5pct_s", 2, 1),
                ("erro de regime (m/s)", "erro_regime", 3, 1)], [c for c in cols_h if c in g]))
        for nome in ("degrau_90", "taxa_0.5", "arco_0.3", "arco_0.5"):
            g = s_[f"yaw_{nome}"]
            chaves = ac.CHAVES[{"degrau_90": "yaw_degrau", "taxa_0.5": "yaw_taxa"}.get(nome, "yaw_arco")][:6]
            for c in [c for c in ("nucleo_cpp", "python_vivo", "python_nominal", "python_b0") if c in g]:
                print(f"yaw {nome} [{c}]: " + ", ".join(f"{k}={ac.fmt(g[c], k)}" for k in chaves))
        print("EQUIVALÊNCIA C++ vs Python (por semente; Δ% = (média C++ − média Python)/média Python; |Δ|rel = diferença relativa por semente):")
        for rotulo, d in s_["equivalencia"].items():
            print(f"  {rotulo}: " + " · ".join(
                f"{k} {v['dif_media_pct']:+.1f} % (|Δ|rel média {v['dif_rel_media_pct']:.1f} %, máx {v['dif_rel_max_pct']:.1f} %)"
                for k, v in d.items() if v.get("n")))


def imprimir_olhar(g: dict) -> None:
    print("\n#### OLHAR — círculo/oito (3 sementes; câmara mono QVGA 30 Hz renderizada; verdade só para medir)")
    print("| caminho · trajetória | rumo RMS (°) | rumo máx (°) | \\|D−d*\\| RMS (m) | elevação RMS (°) | A_SEGUIR (%) | frames válidos (%) | yaw no limite (%) | taxa LOS máx / p95 (rad/s) | v_y de «lateral assist» p95 / máx (m/s) | quedas |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for nome, a in g.items():
        def f(c, casas=2, m=1.0, a=a):
            return f"{m * a[c]:.{casas}f}" if np.isfinite(a.get(c, float("nan"))) else "—"
        print(f"| {nome} | {f('rumo_rms_graus')} | {f('rumo_max_graus')} | {f('dist_erro_rms', 3)} | {f('elev_rms_graus')} | "
              f"{f('frac_a_seguir', 1, 100)} | {f('frac_frames_validos', 1, 100)} | {f('frac_yaw_no_limite', 1, 100)} | "
              f"{f('los_taxa_max', 2)} / {f('los_taxa_p95', 2)} | {f('vy_assist_p95', 3)} / {f('vy_assist_max', 3)} | {a.get('quedas', 0)}/{a.get('n_total', '—')} |")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--rapido", action="store_true", help="3 sementes (fumo)")
    p.add_argument("--sementes", type=int, default=len(SEMENTES_AVALIACAO))
    p.add_argument("--jobs", type=int, default=min(10, (os.cpu_count() or 2) - 1))
    p.add_argument("--json", type=Path, default=SAIDA_JSON)
    p.add_argument("--so-olhar", action="store_true", help="só a secção (f) OLHAR")
    p.add_argument("--sem-olhar", action="store_true", help="salta a secção (f) OLHAR")
    p.add_argument("--u-yaw", type=float, default=None, help="u/r de yaw (omissão: o identificado pela B0)")
    args = p.parse_args(argv)
    dados = ac.carregar_rl_dados()
    u_yaw = args.u_yaw if args.u_yaw is not None else u_yaw_identificado(dados)
    b0 = json.loads(JSON_B0.read_text(encoding="utf-8")) if JSON_B0.is_file() else {}
    sitl.biblioteca_padrao()                      # compila a .so UMA vez, antes de criar os processos
    t0 = time.perf_counter()
    print(f"AVALIAÇÃO do NÚCLEO C++ (cascata clássica + estimador clássico) no MuJoCo · build {build_do_hardware(dados)[0]!r} · "
          f"sementes de avaliação {SEMENTES_AVALIACAO[0]}..{SEMENTES_AVALIACAO[-1]} · u/r de yaw = {u_yaw:.4f} (identificado pela B0) · "
          f"{args.jobs} processos · SEM VENTO", flush=True)
    saida: dict = {"gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "u_yaw_por_taxa": u_yaw, "build": build_do_hardware(dados)[0],
                   "sementes_avaliacao": list(SEMENTES_AVALIACAO[:3] if args.rapido else SEMENTES_AVALIACAO[: args.sementes]),
                   "nucleo": {"versao_interface": sitl.versao_da_interface(), "estado_bytes": sitl.biblioteca_padrao().tamanho_nucleo}}
    if not args.so_olhar:
        saida["protocolo"] = avaliar_protocolo(args, dados, u_yaw, b0)
        imprimir_protocolo(saida["protocolo"])
    if not args.sem_olhar:
        print("== (f) OLHAR", flush=True)
        saida["olhar"] = avaliar_olhar(args, dados, u_yaw)
        imprimir_olhar(saida["olhar"])
    saida["duracao_s"] = time.perf_counter() - t0
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(ac.limpar(saida), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {args.json} ({saida['duracao_s']:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
