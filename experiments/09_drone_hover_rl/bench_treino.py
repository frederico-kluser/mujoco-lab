#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/bench_treino.py — o treino PPO do drone está otimizado? Mede e PROVA.

Três perguntas, três subcomandos (`tudo` corre os três):

    identidade   a otimização do caminho quente (planta/FC/estimador em escalares — `lab/drone_rpi/escalar.py`) mudou
                 a FÍSICA? Corre o código ORIGINAL (extraído do git: `--ref`, por omissão o último commit antes da
                 otimização) e o ATUAL lado a lado, no mesmo processo, com as MESMAS sementes e as MESMAS ações
                 aleatórias fixas, e compara a cada passo de decisão `qpos`, `qvel`, `ctrl`, forças, sensores (verdade e
                 medidos), observação, recompensa, terminação e a telemetria da planta (bateria, motores, aerodinâmica,
                 FC, estimador) — igualdade EXATA, byte a byte (`tobytes`, mais estrita que `np.array_equal`: distingue
                 −0,0 de +0,0 e exige os mesmos NaN). Cenários: o do treino (DR + comandos + rajadas), nominal, vento
                 constante + turbulência, modo `motores`, bateria a descarregar até 0 %, brownout, aerodinâmica
                 desligada (toda e por partes), outros builds do catálogo, alvo mocap. Também corre o caminho VETORIAL
                 de reserva do código atual (`DRONE_RPI_ESCALAR=0`) contra o original.
    passo        quanto acelerou o `env.step`? A/B/A/B intercalado no mesmo processo, em blocos curtos de 100 passos
                 com as mesmas ações (a máquina pode estar carregada: só a RAZÃO conta; o mínimo dos blocos aproxima o
                 tempo sem contenção) + repartição do tempo do passo (planta, da qual MuJoCo; FC; estimador; resto do
                 ambiente) por cronómetro, sem `cProfile` (que distorce o código Python de chamadas curtas).
    escala       débito do `SubprocVecEnv` por nº de ambientes: rollouts do PPO de verdade (`collect_rollouts`: ambiente
                 + inferência da política, sem update) e, à parte, o custo de UM update — com os hiperparâmetros que o
                 `train.py` usaria para esse `n_envs`. Grava `out/bench_treino/escala.json`.

    python experiments/09_drone_hover_rl/bench_treino.py identidade                 # 13 cenários × 5 sementes × 2000
    python experiments/09_drone_hover_rl/bench_treino.py identidade --rapido        # fumo: 2 sementes × 300 passos
    python experiments/09_drone_hover_rl/bench_treino.py passo
    python experiments/09_drone_hover_rl/bench_treino.py escala --n-envs-lista 1,4,8,16,24,32   # com a máquina LIVRE

Saída: `out/bench_treino/{identidade,passo,escala}.json` (nunca toca noutros ficheiros de `out/`). Código de saída 0 se
tudo o que foi pedido passou (a identidade é o único critério de falha; os tempos são só medidos).
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import multiprocessing as mp
import os
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
PASTA_EXP = Path("experiments") / "09_drone_hover_rl"
PASTA_SAIDA = _AQUI / "out" / "bench_treino"

REF_ORIGINAL = "b153c3d"        # último commit ANTES da otimização do caminho quente (2026-10-12)
CAMINHOS_REF = ["lab", "models/drone_rpi", "pyproject.toml", ".agents/mujoco-lab-agent-skill",
                ".agents/mujoco-lab-coala-agent-skill/scripts/mjkit.py",
                *(f"{PASTA_EXP.as_posix()}/{f}" for f in ("env.py", "env_real.py", "fc.py", "estimador.py"))]
MODULOS_DA_ARVORE = ("env", "env_real", "fc", "estimador")      # + `lab` e `lab.*`
BUILD_TREINO = "endurance_15pol_p50b"


# =========================================================================================== árvores de código
def extrair_original(ref: str, destino: Path) -> Path:
    """Extrai do git (`git archive <ref>`) só o que o ambiente precisa para correr: `lab/`, `models/drone_rpi/` e os
    quatro módulos do experimento. Devolve a raiz da árvore extraída."""
    destino.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git", "-C", str(_RAIZ), "archive", "--format=tar", ref, "--", *CAMINHOS_REF],
                       capture_output=True, check=False)
    if r.returncode != 0:
        raise SystemExit(f"erro: `git archive {ref}` falhou — {r.stderr.decode(errors='replace').strip()}\n"
                         "      (use --ref <commit anterior à otimização> ou --original <pasta com o código antigo>)")
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
        tar.extractall(destino, filter="tar")
    return destino


def _da_arvore(nome: str) -> bool:
    return nome in MODULOS_DA_ARVORE or nome == "lab" or nome.startswith("lab.")


def _retirar_modulos() -> dict:
    """Tira do `sys.modules` (e devolve) os módulos que pertencem a uma árvore de código."""
    return {n: sys.modules.pop(n) for n in [n for n in sys.modules if _da_arvore(n)]}


class Arvore:
    """Uma árvore de código CARREGADA e isolada: o `env_real` dela e os módulos `lab.*` que ele usa.

    Duas árvores têm módulos com os MESMOS nomes (`lab.drone_rpi.planta`, `env_real`, `fc`…): cada `Arvore` guarda os
    seus e só os põe no `sys.modules` (e a sua raiz no `sys.path`) enquanto o código dela corre — `with arv.ativa():` —
    para os imports tardios (dentro de funções) acharem os módulos DESTA árvore e nunca os da outra.
    """

    def __init__(self, nome: str, raiz: Path, escalar: bool = True):
        self.nome, self.raiz = nome, Path(raiz)
        self.pasta = self.raiz / PASTA_EXP
        self._modulos: dict = {}
        antes = os.environ.get("DRONE_RPI_ESCALAR")
        if not escalar:
            os.environ["DRONE_RPI_ESCALAR"] = "0"
        else:
            os.environ.pop("DRONE_RPI_ESCALAR", None)
        try:
            with self.ativa():
                self.mod = importlib.import_module("env_real")
                self.dr = sys.modules["lab.drone_rpi"]
                self.planta_mod = sys.modules["lab.drone_rpi.planta"]
                self.escalar_mod = sys.modules.get("lab.drone_rpi.escalar")
        finally:
            if antes is None:
                os.environ.pop("DRONE_RPI_ESCALAR", None)
            else:
                os.environ["DRONE_RPI_ESCALAR"] = antes
        for m in self._modulos.values():
            ficheiro = getattr(m, "__file__", None)
            if ficheiro and self.raiz.resolve() not in Path(ficheiro).resolve().parents:
                raise RuntimeError(f"a árvore '{nome}' carregou {ficheiro}, fora de {self.raiz}")

    @contextlib.contextmanager
    def ativa(self):
        """Os módulos e os caminhos DESTA árvore à vista do sistema de imports enquanto durar o bloco."""
        de_fora = _retirar_modulos()
        sys.modules.update(self._modulos)
        caminho = list(sys.path)
        outras = [p for p in caminho if (Path(p) / "env_real.py").exists() or (Path(p) / "lab" / "drone_rpi").exists()]
        sys.path[:] = [str(self.pasta), str(self.raiz)] + [p for p in caminho if p not in outras]
        try:
            yield self
        finally:
            self._modulos = _retirar_modulos()       # inclui o que foi importado tardiamente dentro do bloco
            sys.modules.update(de_fora)
            sys.path[:] = caminho

    def caminho_ativo(self) -> str:
        if self.escalar_mod is None:
            return "vetorial (código original)"
        return self.escalar_mod.resumo()


# =========================================================================================== cenários
def cenarios() -> list[dict]:
    """Os cenários da prova de identidade (dicts simples: têm de atravessar o `multiprocessing`)."""
    rajadas = {"modo": "rajadas", "p": 0.02, "duracao": 10, "u_max": 3.0}
    return [
        {"nome": "treino", "descricao": "a configuração do train.py --comandos: DR + perfis de comando + vento U[0,3] "
                                        "+ rajadas",
         "kw": {"aleatorizar": True, "comando": True, "comandos_aleatorios": True, "vento_aleatorio": (0.0, 3.0),
                "vento_dinamico": rajadas}},
        {"nome": "nominal", "descricao": "sem DR, sem vento, recompensa de pairagem (v3-real)", "kw": {}},
        {"nome": "dr_hover", "descricao": "DR sem comandos, vento por episódio U[0,3]",
         "kw": {"aleatorizar": True, "vento_aleatorio": (0.0, 3.0)}},
        {"nome": "vento_dryden", "descricao": "vento constante (2; 1; 0,3) m/s + turbulência Dryden",
         "kw": {"vento": (2.0, 1.0, 0.3), "vento_dinamico": {"modo": "dryden", "sigma": 0.5, "L": 10.0, "u_max": 3.0}}},
        {"nome": "motores", "descricao": "modo de ação `motores` (sem FC) com DR e vento",
         "kw": {"modo_acao": "motores", "aleatorizar": True, "vento_aleatorio": (0.0, 3.0)}},
        {"nome": "bateria", "descricao": "pack de 0,4 % da capacidade: o SoC vai de 100 % a 0 % (toda a curva OCV, "
                                         "R₀(SoC), corte a 0); resets com `manter_bateria`",
         "kw": {"comando": True, "comandos_aleatorios": True}, "escala_cap": 0.004, "manter": 4},
        {"nome": "brownout", "descricao": "v_brownout subido para 21,2 V + pack pequeno: o barramento cai abaixo do "
                                          "corte em voo (ESC e eletrónica desligam, o drone cai)",
         "kw": {"aleatorizar": True, "vento_aleatorio": (0.0, 2.0)}, "v_brownout": 21.2, "escala_cap": 0.01,
         "manter": 3},
        {"nome": "aero_base", "descricao": "TODA a aerodinâmica extra desligada (T = kf·ω²)",
         "kw": {"aleatorizar": True}, "flags": {"solo": False, "inflow": False, "vrs": False, "arrasto_rotor": False,
                                              "giroscopico": False, "download": False}},
        {"nome": "aero_parcial_a", "descricao": "sem efeito de solo nem VRS (só inflow, arrasto, giroscópico)",
         "kw": {"vento_aleatorio": (0.0, 3.0)}, "flags": {"solo": False, "vrs": False}},
        {"nome": "aero_parcial_b", "descricao": "sem arrasto de rotor, giroscópico e inflow (só solo e VRS)",
         "kw": {"vento_aleatorio": (0.0, 3.0)}, "flags": {"arrasto_rotor": False, "giroscopico": False,
                                                        "inflow": False}},
        {"nome": "build_lipo_4s", "descricao": "outro build: LiPo 4S (curva OCV de 21 pontos, curva do ESC de 3)",
         "build": "lipo_15pol_mn4006_4s", "kw": {"aleatorizar": True, "comando": True, "comandos_aleatorios": True}},
        {"nome": "build_5pol", "descricao": "outro build: referência de 5″ (ESC sem tabela: curva identidade)",
         "build": "referencia_5pol", "kw": {"aleatorizar": True, "vento_aleatorio": (0.0, 2.0)}},
        {"nome": "com_alvo", "descricao": "modelo com o corpo mocap do alvo (IA de seguimento visual)",
         "build": "endurance_15pol_arduino", "kw": {"com_alvo": True, "comando": True, "comandos_aleatorios": True}},
    ]


def gerar_acoes(semente: int, n: int) -> np.ndarray:
    """Ações aleatórias FIXAS (float32, como as do PPO): blocos de pairagem ruidosa, manobra suave, comandos violentos,
    cortes de motor e capotagens — para o voo passar por solo, subida, descida (VRS), saturação, queda e terminação
    por inclinação > 90°."""
    g = np.random.default_rng(100_003 * (semente + 1))
    a = np.empty((n, 4), dtype=np.float32)
    k = 0
    while k < n:
        dur = int(g.integers(20, 140))
        modo = int(g.choice(5, p=[0.38, 0.27, 0.13, 0.12, 0.10]))
        if modo == 0:                                   # pairagem ruidosa a subir devagar
            bloco = g.normal(0.0, 0.04, (dur, 4))
            bloco[:, 0] += g.uniform(0.02, 0.25)
        elif modo == 1:                                 # manobra suave
            bloco = g.normal(0.0, 0.15, (dur, 4)) + g.uniform(-0.15, 0.15, 4)
            bloco[:, 0] += g.uniform(0.0, 0.3)
        elif modo == 2:                                 # violento, com valores fora de [−1, 1] (o ambiente corta)
            bloco = g.uniform(-1.3, 1.3, (dur, 4))
        elif modo == 3:                                 # corte/redução de motores: descida no próprio rasto
            bloco = g.normal(0.0, 0.05, (dur, 4))
            bloco[:, 0] += g.uniform(-1.2, -0.1)
        else:                                           # capotagem: taxa máxima sustentada em roll ou pitch
            bloco = g.normal(0.0, 0.03, (dur, 4))       # (em `motores`: um motor no máximo/mínimo) → termina
            bloco[:, 0] += 0.1
            bloco[:, int(g.integers(1, 3))] += float(g.choice([-1.0, 1.0]))
        a[k:k + dur] = bloco[:n - k]
        k += dur
    return a


def criar_env(arv: Arvore, cen: dict):
    """O `DroneRealEnv` do cenário, construído com as classes DESTA árvore."""
    kw = dict(cen.get("kw", {}))
    nome_build = cen.get("build", BUILD_TREINO)
    cfg_build = {**arv.dr.carregar_builds()["builds"][nome_build], "nome": nome_build}
    cfg_build.pop("arma", None)               # `REF_ORIGINAL` (b153c3d) é anterior à Glock 25 no catálogo
    build = arv.dr.hardware(cfg_build)
    if "v_brownout" in cen:
        build.v_brownout = float(cen["v_brownout"])
    if "flags" in cen:
        kw["flags_aero"] = arv.dr.FlagsAero(**cen["flags"])
    env = arv.mod.DroneRealEnv(build=build, **kw)
    if "escala_cap" in cen:
        env.planta.bat.escala_cap = float(cen["escala_cap"])
    return env


# =========================================================================================== assinatura do estado
def _vec(*partes) -> np.ndarray:
    return np.concatenate([np.atleast_1d(np.asarray(p, dtype=float)).ravel() for p in partes])


def assinatura(env) -> list[tuple[str, np.ndarray]]:
    """Tudo o que define o estado do simulador e da planta, por campos nomeados (float64) — o que se compara."""
    pl, d = env.planta, env.data
    b, pr, fc, est = pl.bat, pl.prop, env.fc, env.estimador
    giro, acc, tof, fl, mon = pl.imu.giro, pl.imu.acc, pl.tof, pl.fluxo, pl.monitor
    det = pl.detalhe_aero
    pot = pl.potencias()
    return [
        ("qpos", _vec(d.qpos)), ("qvel", _vec(d.qvel)), ("tempo", _vec(d.time)), ("ctrl", _vec(d.ctrl)),
        ("xfrc_applied", _vec(d.xfrc_applied[pl.corpo])), ("sensordata", _vec(d.sensordata)),
        ("vento", _vec(env.model.opt.wind)),
        ("bateria", _vec(b.soc, b.v, b.v_rc, b.temp, b.i, b.p, b.ah_ciclo, b.wh_ciclo, b.t_ciclo, b.soma_c_dt,
                         b.soma_t_dt, b.i_pico, b.v_min, b.desgaste.soh, b.r0())),
        ("planta", _vec(pl.v_bus, pl.i_total, pl.brownout, pl.n_passos, pot["motores"], pot["total"])),
        ("kappa_t", _vec(pl.kappa_t)), ("altura_rotores", _vec(pl.altura_rotores)),
        ("detalhe_aero", _vec(*(det[k] for k in ("solo", "inflow", "vrs"))) if det else np.zeros(0)),
        ("vrs_ruido", _vec(pl.aero._vrs_ruido)),
        ("motores", _vec(pr.omega, pr.omega_dot, pr.duty, pr.acelerador, pr.i_fase, pr.i_bus, pr.empuxo, pr.q_aero,
                         pr.armado)),
        ("imu", _vec(giro.medicao, giro.bias, giro.escala, giro.n_amostras, giro._prox,
                     acc.medicao, acc.bias, acc.escala, acc.n_amostras, acc._prox)),
        ("tof", _vec(tof.distancia, tof.valido, tof.s.n_amostras, tof.s.medicao, tof.s.bias, tof.s.escala)),
        ("fluxo", _vec(fl.fluxo, fl.valido, fl.s.n_amostras, fl.s.medicao, fl.s.bias, fl.s.escala)),
        ("monitor", _vec(mon.tensao, mon.corrente, mon.v.medicao, mon.i.medicao, mon.v.escala, mon.i.escala,
                         mon.i.bias)),
        ("fc", _vec(fc.integral, fc.giro_f, fc.d_f, fc.giro_ant, fc.saida, fc.armado)),
        ("estimador", _vec(est.roll, est.pitch, est.psi, est.h, est.vz, est.vx, est.vy, est.x, est.y)),
    ]


def _info_vec(info: dict) -> np.ndarray:
    chaves = ("z", "dist_xy", "v", "no_alvo", "yaw_err", "vento_vel", "vento_azim", "soc", "v_bat", "i_bat", "p_total",
              "soh", "brownout")
    v = [float(info[k]) for k in chaves]
    voo = info.get("voo")
    if voo:
        v += [*voo["v_ref"], *voo["p_ref"], voo["erro_xy"], voo["erro_z"], voo["erro_v"], float(voo["seguindo"])]
    return np.asarray(v, dtype=float)


def _diferenca(nome: str, a: np.ndarray, b: np.ndarray) -> dict | None:
    """None se `a` e `b` são IDÊNTICOS byte a byte; senão o relatório da diferença."""
    if a.shape == b.shape and a.tobytes() == b.tobytes():
        return None
    if a.shape != b.shape:
        return {"campo": nome, "motivo": f"formas diferentes {a.shape} vs {b.shape}"}
    with np.errstate(invalid="ignore"):
        delta = np.abs(a - b)
    i = int(np.nanargmax(np.where(np.isnan(delta), np.inf, delta))) if delta.size else 0
    return {"campo": nome, "indice": i, "original": repr(float(a.flat[i])), "outro": repr(float(b.flat[i])),
            "erro_max": float(np.nanmax(delta)) if np.isfinite(delta).any() else float("nan"),
            "array_equal": bool(np.array_equal(a, b)), "n_elementos_diferentes": int(np.sum(a != b))}


def comparar(ref_campos, campos) -> dict | None:
    for (nome, a), (_n, b) in zip(ref_campos, campos, strict=True):
        dif = _diferenca(nome, a, b)
        if dif is not None:
            return dif
    return None


# =========================================================================================== prova de identidade
def _passo_seguro(env, acao):
    """`env.step` ou a exceção de divergência (que também tem de ser igual nas duas árvores)."""
    try:
        obs, r, te, tr, info = env.step(acao)
    except RuntimeError as erro:
        return None, repr(erro)
    return (obs, r, te, tr, info), None


def correr_cenario(tarefa: dict) -> dict:
    """Um cenário × uma semente: original vs atual (e vs o caminho vetorial de reserva do atual, se pedido)."""
    cen, semente, n_passos = tarefa["cenario"], tarefa["semente"], tarefa["passos"]
    t0 = time.perf_counter()
    arvores = [Arvore("original", tarefa["original"]), Arvore("atual", tarefa["atual"])]
    if tarefa.get("vetorial"):
        arvores.append(Arvore("atual-vetorial", tarefa["atual"], escalar=False))
    envs = []
    for a in arvores:
        with a.ativa():
            envs.append(criar_env(a, cen))
    # ÚNICO estado que NÃO depende da semente (achado desta prova, igual no código original): o ruído AR(1) do VRS
    # (`aero._vrs_ruido`) avança no `__init__` do ambiente (o `_medir_repouso` corre a planta com um gerador SEM
    # semente) e nenhum `reset` o repõe. Para comparar as duas árvores iguala-se esse estado ao do original; tudo o
    # resto (bias dos sensores, bateria, FC, estimador) é sorteado/reposto no `reset(seed=…)`.
    # Desde 2026-10-13 o código ATUAL repõe esse ruído em cada reinício (`Planta.repor_aero_no_reinicio`, a correção
    # da reprodutibilidade); o original não. Para a prova de identidade a reposição desliga-se nas árvores atuais — é
    # a única diferença deliberada de trajetória e está provada à parte (`valida_real.py`: reset(seed) reprodutível).
    vrs0 = [float(x) for x in envs[0].planta.aero._vrs_ruido]
    for e in envs[1:]:
        e.planta.repor_aero_no_reinicio = False
        e.planta.aero._vrs_ruido = list(vrs0)
    acoes = gerar_acoes(semente, n_passos)
    manter = int(cen.get("manter", 0))
    res = {"cenario": cen["nome"], "semente": semente, "passos_pedidos": n_passos, "passos": 0, "resets": 0,
           "terminados": 0, "divergencias": 0, "comparacoes": 0, "caminhos": {a.nome: a.caminho_ativo() for a in arvores},
           "diferenca": None}
    z, soc, brown, no_ar, dz_max, incl_max, ncon = [], [], 0, 0, 0.0, 0.0, 0

    def confere(etapa: str, extra) -> bool:
        ref = assinatura(envs[0]) + extra[0]
        for arv, env, ex in zip(arvores[1:], envs[1:], extra[1:], strict=True):
            dif = comparar(ref, assinatura(env) + ex)
            res["comparacoes"] += 1
            if dif is not None:
                res["diferenca"] = {"contra": arv.nome, "etapa": etapa, "passo": res["passos"], **dif}
                return False
        return True

    def reinicia(n_reset: int) -> bool:
        opcoes = {"manter_bateria": True} if (manter and n_reset > 0 and n_reset % manter != 0) else None
        saidas = []
        for a, e in zip(arvores, envs, strict=True):
            with a.ativa():
                saidas.append(e.reset(seed=semente if n_reset == 0 else None, options=opcoes))
        return confere(f"reset {n_reset}", [[("obs", _vec(o)), ("info", _info_vec(i))] for o, i in saidas])

    ok = reinicia(0)
    k = 0
    while ok and k < n_passos:
        saidas = []
        for a, e in zip(arvores, envs, strict=True):
            with a.ativa():
                saidas.append(_passo_seguro(e, acoes[k]))
        k += 1
        res["passos"] = k
        erros = [s[1] for s in saidas]
        if any(e is not None for e in erros):
            if len(set(erros)) != 1:
                res["diferenca"] = {"etapa": "step", "passo": k, "campo": "exceção", "valores": erros}
                break
            res["divergencias"] += 1
            res["resets"] += 1
            ok = reinicia(res["resets"])
            continue
        extra = [[("obs", _vec(s[0][0])), ("recompensa", _vec(s[0][1])), ("fim", _vec(s[0][2], s[0][3])),
                  ("info", _info_vec(s[0][4]))] for s in saidas]
        ok = confere("step", extra)
        _obs, _r, te, tr, info = saidas[0][0]
        e0 = envs[0]
        z.append(info["z"])
        soc.append(info["soc"])
        brown += int(bool(info["brownout"]))
        no_ar += int(e0.data.ncon == 0)
        ncon = max(ncon, int(e0.data.ncon))
        dz_max = max(dz_max, abs(float(e0.data.qvel[2])))
        incl_max = max(incl_max, float(np.max(np.abs(e0.data.qvel[3:6]))))
        if ok and (te or tr):
            res["terminados"] += int(te)
            res["resets"] += 1
            ok = reinicia(res["resets"])
    for e in envs:
        e.close()
    res.update(ok=bool(ok and res["diferenca"] is None), duracao_s=round(time.perf_counter() - t0, 1),
               cobertura={"z_max": round(max(z, default=0.0), 3), "soc_min": round(min(soc, default=1.0), 4),
                          "soc_max": round(max(soc, default=1.0), 4), "passos_em_brownout": brown,
                          "fracao_sem_contacto": round(no_ar / max(len(z), 1), 3), "contactos_max": ncon,
                          "v_z_max": round(dz_max, 2), "taxa_max": round(incl_max, 2)})
    return res


def comando_identidade(args, original: Path) -> bool:
    todos = cenarios()
    escolhidos = [c for c in todos if not args.cenarios or c["nome"] in args.cenarios]
    if args.cenarios and len(escolhidos) != len(set(args.cenarios)):
        raise SystemExit(f"erro: cenários desconhecidos em {args.cenarios} — existem: {[c['nome'] for c in todos]}")
    sementes = list(range(args.sementes))
    tarefas = [{"cenario": c, "semente": s, "passos": args.passos, "original": str(original), "atual": str(_RAIZ),
                "vetorial": s < args.sementes_vetorial}
               for c in escolhidos for s in sementes]
    print(f"\n== IDENTIDADE bit a bit: original ({args.ref if not args.original else args.original}) vs atual ==")
    print(f"   {len(escolhidos)} cenários × {len(sementes)} sementes × {args.passos} passos de decisão "
          f"(= {10 * args.passos} passos de física cada) · {args.processos} processos · o caminho vetorial de reserva "
          f"corre nas {min(args.sementes_vetorial, len(sementes))} primeiras sementes de cada cenário")
    t0 = time.perf_counter()
    resultados = []
    with mp.get_context("spawn").Pool(args.processos, maxtasksperchild=1) as pool:
        for r in pool.imap_unordered(correr_cenario, tarefas):
            resultados.append(r)
            c = r["cobertura"]
            estado = "IDÊNTICO" if r["ok"] else "DIFERENTE"
            print(f"   [{len(resultados):3d}/{len(tarefas)}] {r['cenario']:15s} semente {r['semente']} · {r['passos']:5d} "
                  f"passos · {r['resets']:3d} resets · {r['comparacoes']:5d} comparações · z_max {c['z_max']:.2f} m · "
                  f"SoC {c['soc_max']:.2f}→{c['soc_min']:.2f} · {estado} ({r['duracao_s']:.0f} s)", flush=True)
            if not r["ok"]:
                print(f"        ↳ {json.dumps(r['diferenca'], ensure_ascii=False)}", flush=True)
    resultados.sort(key=lambda r: (r["cenario"], r["semente"]))
    ok = all(r["ok"] for r in resultados)
    resumo = {}
    for c in escolhidos:
        rs = [r for r in resultados if r["cenario"] == c["nome"]]
        resumo[c["nome"]] = {
            "descricao": c["descricao"], "sementes": len(rs), "passos": sum(r["passos"] for r in rs),
            "resets": sum(r["resets"] for r in rs), "comparacoes": sum(r["comparacoes"] for r in rs),
            "identico": all(r["ok"] for r in rs),
            "soc_min": min(r["cobertura"]["soc_min"] for r in rs), "z_max": max(r["cobertura"]["z_max"] for r in rs),
            "passos_em_brownout": sum(r["cobertura"]["passos_em_brownout"] for r in rs),
            "fracao_sem_contacto": round(statistics.mean(r["cobertura"]["fracao_sem_contacto"] for r in rs), 3)}
    total_passos = sum(r["passos"] for r in resultados)
    caminhos = sorted({v for r in resultados for v in r["caminhos"].values()})
    print(f"\n   {'IDÊNTICO' if ok else 'HÁ DIFERENÇAS'}: {total_passos} passos de decisão ({10 * total_passos} de física), "
          f"{sum(r['comparacoes'] for r in resultados)} comparações byte a byte de 24 campos, "
          f"{sum(r['resets'] for r in resultados)} resets, em {time.perf_counter() - t0:.0f} s")
    for cam in caminhos:
        print(f"   caminho: {cam}")
    for nome, r in resumo.items():
        print(f"   {nome:15s} {'ok ' if r['identico'] else 'FALHOU'} · {r['passos']:6d} passos · {r['resets']:4d} resets · "
              f"z_max {r['z_max']:5.2f} m · SoC mín {r['soc_min']:.3f} · brownout {r['passos_em_brownout']:5d} passos · "
              f"{100 * r['fracao_sem_contacto']:3.0f} % no ar")
    gravar("identidade.json", {"ok": ok, "ref_original": args.original or args.ref, "sementes": args.sementes,
                               "passos_por_semente": args.passos, "passos_total": total_passos,
                               "campos_comparados": [n for n, _ in _nomes_campos()], "caminhos": caminhos,
                               "cenarios": resumo, "corridas": resultados})
    return ok


def _nomes_campos() -> list[tuple[str, str]]:
    return [(n, "") for n in ("qpos", "qvel", "tempo", "ctrl", "xfrc_applied", "sensordata", "vento", "bateria",
                              "planta", "kappa_t", "altura_rotores", "detalhe_aero", "vrs_ruido", "motores", "imu",
                              "tof", "fluxo", "monitor", "fc", "estimador", "obs", "recompensa", "fim", "info")]


# =========================================================================================== tempo do env.step
def _env_treino(arv: Arvore):
    with arv.ativa():
        return criar_env(arv, cenarios()[0])


def _corre(env, acoes: np.ndarray) -> float:
    """Corre `len(acoes)` passos (com os resets que calharem, como no treino) e devolve os segundos."""
    t0 = time.perf_counter()
    for a in acoes:
        _o, _r, te, tr, _i = env.step(a)
        if te or tr:
            env.reset()
    return time.perf_counter() - t0


class _Cronometro:
    """Embrulha uma função e acumula o tempo que ela leva (para repartir o `env.step` sem `cProfile`)."""

    def __init__(self, f):
        self.f, self.t, self.n = f, 0.0, 0

    def __call__(self, *a, **k):
        t0 = time.perf_counter()
        try:
            return self.f(*a, **k)
        finally:
            self.t += time.perf_counter() - t0
            self.n += 1


def _reparticao(arv: Arvore, n_passos: int, semente: int = 0) -> dict:
    """Onde vai o tempo de um `env.step` desta árvore: planta (e, dentro dela, o MuJoCo), FC, estimador, resto."""
    import mujoco
    env = _env_treino(arv)
    acoes = gerar_acoes(semente, n_passos)
    with arv.ativa():
        env.reset(seed=semente)
        _corre(env, acoes[:200])                                    # aquece
    nomes = ("mj_step1", "mj_step2", "mj_ray")
    pm = arv.planta_mod
    crono_mj = {n: _Cronometro(getattr(mujoco, n)) for n in nomes}
    originais = {n: getattr(mujoco, n) for n in nomes}
    privados = {n: getattr(pm, "_" + n, None) for n in nomes}
    for n in nomes:                                                 # a planta atual liga `_mj_*` no import
        setattr(mujoco, n, crono_mj[n])
        if privados[n] is not None:
            setattr(pm, "_" + n, crono_mj[n])
    pl, fc, est = env.planta, env.fc, env.estimador
    c_pl, c_fc, c_est = _Cronometro(pl.passo), _Cronometro(fc.passo), _Cronometro(est.passo)
    pl.passo, fc.passo, est.passo = c_pl, c_fc, c_est
    try:
        with arv.ativa():
            total = _corre(env, acoes)
    finally:
        for n in nomes:
            setattr(mujoco, n, originais[n])
            if privados[n] is not None:
                setattr(pm, "_" + n, privados[n])
    env.close()
    mj = sum(c.t for c in crono_mj.values())
    ms = 1e3 / n_passos
    return {"passos": n_passos, "ms_passo_instrumentado": total * ms, "planta_ms": c_pl.t * ms,
            "mujoco_ms": mj * ms, "mujoco_detalhe_ms": {n: c.t * ms for n, c in crono_mj.items()},
            "planta_python_ms": (c_pl.t - mj) * ms, "fc_ms": c_fc.t * ms, "estimador_ms": c_est.t * ms,
            "ambiente_ms": (total - c_pl.t - c_fc.t - c_est.t) * ms,
            "fracoes": {"mujoco": mj / total, "planta_python": (c_pl.t - mj) / total, "fc": c_fc.t / total,
                        "estimador": c_est.t / total, "ambiente": (total - c_pl.t - c_fc.t - c_est.t) / total},
            "chamadas_planta_por_passo": c_pl.n / n_passos}


def comando_passo(args, original: Path) -> bool:
    print("\n== TEMPO do env.step: original vs atual, A/B intercalado no mesmo processo ==")
    arv_o, arv_n = Arvore("original", original), Arvore("atual", _RAIZ)
    print(f"   atual: {arv_n.caminho_ativo()}")
    env_o, env_n = _env_treino(arv_o), _env_treino(arv_n)
    vrs0 = [float(x) for x in env_o.planta.aero._vrs_ruido]         # mesmo estado inicial ⇒ mesma trajetória e
    env_n.planta.repor_aero_no_reinicio = False                     # (o original não repõe o ruído do VRS no reinício)
    env_n.planta.aero._vrs_ruido = list(vrs0)                       # mesmo trabalho nas duas (ver `correr_cenario`)
    bloco, n_blocos = 100, max(4, args.passos * args.rondas // 100)
    acoes = gerar_acoes(7, bloco * n_blocos + 150)
    pares = ((arv_o, env_o), (arv_n, env_n))
    for arv, env in pares:
        with arv.ativa():
            env.reset(seed=7)
            _corre(env, acoes[:150])                                # aquece (caches, ramos)
    ms: dict[str, list] = {"original": [], "atual": []}
    for b in range(n_blocos):                                       # A/B, B/A, A/B… com as MESMAS ações
        acs = acoes[150 + b * bloco: 150 + (b + 1) * bloco]
        for arv, env in (pares if b % 2 == 0 else pares[::-1]):
            with arv.ativa():
                ms[arv.nome].append(1e3 * _corre(env, acs) / bloco)
        if (b + 1) % max(1, n_blocos // 6) == 0:
            print(f"   bloco {b + 1:3d}/{n_blocos}: original {statistics.median(ms['original']):6.3f} ms/passo · atual "
                  f"{statistics.median(ms['atual']):6.3f} ms/passo (medianas até aqui)", flush=True)
    iguais = bool(np.array_equal(env_o.data.qpos, env_n.data.qpos))
    env_o.close()
    env_n.close()
    razoes = sorted(o / n for o, n in zip(ms["original"], ms["atual"], strict=True))
    res = {"passos_por_bloco": bloco, "blocos": n_blocos, "passos_por_arvore": bloco * n_blocos,
           "ms_original_mediana": statistics.median(ms["original"]), "ms_atual_mediana": statistics.median(ms["atual"]),
           "ms_original_min": min(ms["original"]), "ms_atual_min": min(ms["atual"]),
           "razao_total": sum(ms["original"]) / sum(ms["atual"]), "razao_mediana": statistics.median(razoes),
           "razao_quartis": [razoes[len(razoes) // 4], razoes[(3 * len(razoes)) // 4]],
           "razao_dos_minimos": min(ms["original"]) / min(ms["atual"]), "mesma_trajetoria": iguais,
           "carga_maquina": os.getloadavg()}
    print(f"   → mediana {res['ms_original_mediana']:.3f} → {res['ms_atual_mediana']:.3f} ms/passo de decisão · razão "
          f"{res['razao_mediana']:.2f}× (quartis {res['razao_quartis'][0]:.2f}–{res['razao_quartis'][1]:.2f}×; tempo "
          f"total {res['razao_total']:.2f}×)")
    print(f"   → melhor bloco (≈ sem contenção) {res['ms_original_min']:.3f} → {res['ms_atual_min']:.3f} ms/passo · razão "
          f"{res['razao_dos_minimos']:.2f}× · {n_blocos} blocos de {bloco} passos por árvore · mesma trajetória: "
          f"{'sim' if iguais else 'NÃO'} · carga da máquina {res['carga_maquina'][0]:.1f}")
    for nome, arv in (("original", arv_o), ("atual", arv_n)):
        rep = _reparticao(arv, args.passos)
        res[f"reparticao_{nome}"] = rep
        f = rep["fracoes"]
        print(f"   repartição {nome:8s}: {rep['ms_passo_instrumentado']:.3f} ms = planta-Python {100 * f['planta_python']:4.1f} % "
              f"· MuJoCo {100 * f['mujoco']:4.1f} % (step1+step2+4 raios, {rep['mujoco_ms'] * 100:.1f} µs/passo de física) "
              f"· FC {100 * f['fc']:4.1f} % · estimador {100 * f['estimador']:4.1f} % · resto do ambiente "
              f"{100 * f['ambiente']:4.1f} %")
    gravar("passo.json", res)
    return True


# =========================================================================================== escala com n_envs
def _mede_vec(n_envs: int, raiz: Path, rollouts: int, semente: int = 0) -> dict:
    """Débito do PPO de verdade com `n_envs` ambientes desta árvore: rollouts (`collect_rollouts`) e UM update."""
    import torch
    import train
    torch.set_num_threads(1)
    args = train.ler_args(["--comandos", "--vento-dinamico", "rajadas", "--vento-dinamico-params",
                           '{"p": 0.02, "duracao": 10}', "--curriculo-vento", "3", "--sem-painel", "--n-envs",
                           str(n_envs), "--seed", str(semente), "--build", BUILD_TREINO])
    din = train.config_dinamica(args.vento_dinamico_cfg, 3.0)
    fabricas = [train._fabrica_env(semente + i, str(raiz / PASTA_EXP), str(raiz), 3.0, din, planta="real",
                                   build=args.build, modo_acao=args.modo_acao, aleatorizar=True, comando=True,
                                   perfis=True) for i in range(n_envs)]
    t0 = time.perf_counter()
    venv = train.SubprocVecEnv(fabricas)
    try:
        modelo, _ = train.criar_modelo(args, venv, train.PainelNulo())
        t_arranque = time.perf_counter() - t0
        _total, cb = modelo._setup_learn(10 ** 9, None, True, "bench", False)
        n_steps = modelo.n_steps
        modelo.collect_rollouts(venv, cb, modelo.rollout_buffer, n_rollout_steps=max(16, n_steps // 8))   # aquece
        tempos = []
        for _ in range(rollouts):
            t0 = time.perf_counter()
            modelo.collect_rollouts(venv, cb, modelo.rollout_buffer, n_rollout_steps=n_steps)
            tempos.append(time.perf_counter() - t0)
        t0 = time.perf_counter()
        modelo.train()
        t_update = time.perf_counter() - t0
        por_threads = {1: t_update}
        for n_threads in (2, 4):                     # o update com mais threads do torch (os ambientes estão parados)
            torch.set_num_threads(n_threads)
            t0 = time.perf_counter()
            modelo.train()
            por_threads[n_threads] = time.perf_counter() - t0
        torch.set_num_threads(1)
    finally:
        venv.close()
    passos = n_steps * n_envs
    t_roll = statistics.median(tempos)
    return {"n_envs": n_envs, "n_steps": n_steps, "passos_por_rollout": passos, "batch_size": modelo.batch_size,
            "n_epochs": modelo.n_epochs, "passos_gradiente_por_update": modelo.n_epochs * (passos // modelo.batch_size),
            "s_rollout": tempos, "passos_s_rollout": passos / t_roll, "s_update": t_update,
            "passos_s_treino": passos / (t_roll + t_update), "fracao_update": t_update / (t_roll + t_update),
            "s_update_por_threads_torch": por_threads, "s_arranque": t_arranque}


def comando_escala(args, original: Path | None) -> bool:
    lista = [int(x) for x in str(args.n_envs_lista).split(",") if x.strip()]
    logicos = os.cpu_count() or 1
    print(f"\n== ESCALA com o nº de ambientes (SubprocVecEnv, {logicos} threads) — rollouts do PPO + 1 update ==")
    print(f"   carga da máquina agora: {os.getloadavg()[0]:.1f} (com a máquina carregada os números absolutos são ruído; "
          "as razões entre linhas da mesma corrida valem mais)")
    linhas = []
    for n in lista:
        if n > logicos:
            print(f"   n_envs={n}: ignorado (mais do que os {logicos} núcleos lógicos)")
            continue
        linha = {"n_envs": n}
        arvores = [("atual", _RAIZ)] + ([("original", original)] if original is not None else [])
        for rep in range(args.repeticoes):
            for nome, raiz in (arvores if rep % 2 == 0 else arvores[::-1]):
                m = _mede_vec(n, Path(raiz), args.rollouts)
                linha.setdefault(nome, []).append(m)
        at = max(linha["atual"], key=lambda m: m["passos_s_rollout"])
        th = at["s_update_por_threads_torch"]
        texto = (f"   n_envs={n:2d} · n_steps={at['n_steps']:4d} · rollout {at['passos_por_rollout']} · "
                 f"{at['passos_s_rollout']:7.0f} passos/s só rollout · update {at['s_update']:.2f} s "
                 f"({100 * at['fracao_update']:.0f} % do ciclo; 2 threads {th[2]:.2f} s, 4 threads {th[4]:.2f} s) · "
                 f"{at['passos_s_treino']:7.0f} passos/s de treino")
        if "original" in linha:
            og = max(linha["original"], key=lambda m: m["passos_s_rollout"])
            linha["razao_rollout"] = at["passos_s_rollout"] / og["passos_s_rollout"]
            texto += f" · original {og['passos_s_rollout']:6.0f} passos/s → {linha['razao_rollout']:.2f}×"
        linha["melhor_atual"] = at
        linhas.append(linha)
        print(texto, flush=True)
    base = next((ln["melhor_atual"]["passos_s_rollout"] for ln in linhas if ln["n_envs"] == 1), None)
    if base:
        print("   escala relativa a 1 ambiente: " + " · ".join(
            f"{ln['n_envs']}→{ln['melhor_atual']['passos_s_rollout'] / base:.2f}×" for ln in linhas))
    gravar("escala.json", {"cpu_logicos": logicos, "carga_maquina": os.getloadavg(), "rollouts": args.rollouts,
                           "repeticoes": args.repeticoes, "linhas": linhas})
    return True


# =========================================================================================== utilitários
def gravar(nome: str, dados: dict) -> None:
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SAIDA / nome
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1, default=float)
    print(f"   gravado: {destino}")


def ler_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("comando", choices=("identidade", "passo", "escala", "tudo"))
    p.add_argument("--ref", default=REF_ORIGINAL, help="commit do código ORIGINAL (antes da otimização)")
    p.add_argument("--original", default=None, help="pasta com o código original já extraído (em vez de --ref)")
    p.add_argument("--sementes", type=int, default=5, help="identidade: sementes por cenário")
    p.add_argument("--passos", type=int, default=None,
                   help="passos de decisão por semente (identidade: 2000) ou por ronda (passo: 1500)")
    p.add_argument("--sementes-vetorial", type=int, default=2,
                   help="identidade: em quantas sementes de cada cenário também corre o caminho vetorial de reserva")
    p.add_argument("--cenarios", nargs="*", default=None, help="identidade: só estes cenários")
    p.add_argument("--processos", type=int, default=min(8, os.cpu_count() or 1), help="identidade: processos")
    p.add_argument("--rapido", action="store_true", help="identidade de fumo: 2 sementes × 300 passos")
    p.add_argument("--rondas", type=int, default=4,
                   help="passo: o A/B corre passos × rondas passos de decisão por árvore, em blocos alternados de 100")
    p.add_argument("--n-envs-lista", default="1,2,4,8", help="escala: nº de ambientes a medir")
    p.add_argument("--rollouts", type=int, default=3, help="escala: rollouts cronometrados por medição")
    p.add_argument("--repeticoes", type=int, default=1, help="escala: repetições (alternando original/atual)")
    p.add_argument("--com-original", action="store_true", help="escala: mede também o código original (A/B)")
    args = p.parse_args(argv)
    if args.rapido:
        args.sementes, args.sementes_vetorial = 2, 1
        args.passos = args.passos or 300
    return args


def main(argv=None) -> int:
    args = ler_args(argv)
    temporaria = None
    original = Path(args.original).resolve() if args.original else None
    precisa = args.comando in ("identidade", "passo", "tudo") or args.com_original
    if precisa and original is None:
        temporaria = Path(tempfile.mkdtemp(prefix="bench_treino_"))
        original = extrair_original(args.ref, temporaria / "original")
    ok = True
    try:
        if args.comando in ("identidade", "tudo"):
            passos = args.passos
            args.passos = passos or 2000
            ok = comando_identidade(args, original) and ok
            args.passos = passos
        if args.comando in ("passo", "tudo"):
            passos = args.passos
            args.passos = passos or 1500
            ok = comando_passo(args, original) and ok
            args.passos = passos
        if args.comando in ("escala", "tudo"):
            ok = comando_escala(args, original if args.com_original else None) and ok
    finally:
        if temporaria is not None:
            shutil.rmtree(temporaria, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
