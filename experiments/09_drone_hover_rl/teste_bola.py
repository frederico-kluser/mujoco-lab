#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_bola.py — PROVA do modo «SEGUIR A BOLA»: a bola anda ao acaso e o drone mantém-na centrada na
imagem da câmara FPV (lei IBVS versão 2 do firmware C++: guinada + translação lateral + compensações).

O que se prova (tolerâncias derivadas das MEDIÇÕES do `avaliar_bola.py`, com folga; nada de «assert True»):

  §0 a BOLA ALEATÓRIA (`env_real.definir_trajetoria_ponto("aleatorio")`): reprodutível pela semente do episódio e pela `semente`
     explícita, sem gastar um número do gerador do env (os sensores ficam iguais), parte do repouso, contínua, teto de velocidade
     e de aceleração, dentro da arena e da banda de altura em 20 min de bola, velocidade média ≈ 0,8·teto; `parado`/`circulo`/`oito`
     intactos (fórmulas fechadas);
  §1 a INTERFACE: `ibvs_ganhos.hpp` (versionado) É a Config por omissão e a que o runner recebe de `sitl.config_de_hardware`;
     `kVersaoVisao = 2`; o gerador do cabeçalho faz ida e volta; Configs novas inválidas são recusadas; o treino recusa as
     sementes de avaliação;
  §2 a lei da VERSÃO 1 continua lá, BIT A BIT: `config_versao1` no C++ novo ≡ o C++ de antes desta atividade (as fontes do commit
     b153c3d, compiladas agora) em 5 cenários × 1400 decisões — e, se o git não tiver esse commit, contra os valores gravados;
  §3 a lei da VERSÃO 2 por mecanismo (roteiros geométricos, sem simulador): sinais de v_y/guinada, repartição do movimento
     tangencial, compensação da translação própria (alvo parado visto de um drone a andar ⇒ velocidade do alvo ≈ 0),
     compensação da inclinação (o canal vertical anula o erro NA IMAGEM), limites e slew de v_y, perda ⇒ v = 0;
  §4 as MEDIDAS: a verdade do `avaliar_bola.Verdade` ≡ `visao.projetar` e vê o pitch do corpo; a câmara em modo PROJEÇÃO
     (treino) ≡ a RENDERIZADA + detetor C++ (avaliação) em píxeis e na validade;
  §5 MALHA FECHADA no simulador completo (2 sementes de TESTE 7300–7301, que não são nem de afinação nem de avaliação): a
     versão 2 centra melhor que a versão 1 nas duas latências, sem quedas, sem perder a bola; a bola repete bit a bit entre
     processos e o voo até ao arredondamento;
  §6 MUTAÇÕES anti-tautologia: 5 na fonte C++ (recompilada de verdade) + 2 no Python — todas têm de ser APANHADAS.

    .venv/bin/python experiments/09_drone_hover_rl/teste_bola.py            # tudo (≈ 3–5 min)
    .venv/bin/python experiments/09_drone_hover_rl/teste_bola.py --rapido   # sem a malha fechada no simulador (§5)
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

import avaliar_bola as ab
import env_real
import numpy as np
import sitl_visao as sv
import treinar_bola as tb

NUCLEO_DIR = sv.NUCLEO_DIR
COMMIT_ANTES = "b153c3d"                 # o último commit com a lei da versão 1 por omissão (fontes de referência do §2)
FICHEIROS_ANTES = ("visao_tipos.hpp", "visao.hpp", "alvo.hpp", "ibvs.hpp", "capi_visao.cpp")
SEMENTES_TESTE = (7300, 7301)            # nem de afinação (8100…) nem de avaliação (6200…)
FOVY_PI = 67.0                           # FoV vertical da câmara do build ativo (a do protocolo `pi_116ms`)
# valores GRAVADOS da lei v1 com as fontes do commit b153c3d (planta cinemática, T = 14 s): (Σ|yaw_taxa|, Σ|v_x|, ψ final)
OURO_V1 = {"circulo": (479.08271808736026, 107.932241981689, 4.63767702657725),
           "oito": (429.53759749489836, 673.5794859705493, -0.1634258628364338),
           "oclusao": (488.442777691409, 105.66654932609526, 4.668068282689962),
           "alfa_beta": (376.5407741079107, 479.4416273003444, -2.397273095651653),
           "cv": (18.493861542257946, 90.60852591723142, -0.009030842297922932)}


class Checagens:
    def __init__(self) -> None:
        self.linhas, self.falhas = [], []

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.linhas.append(nome)
        if not cond:
            self.falhas.append(nome)
        print(f"        [{'OK  ' if cond else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""), flush=True)
        return bool(cond)


# ============================================================================================ §0 a bola aleatória
def _env_bola():
    return env_real.DroneRealEnv(build=None, modo_acao="ctbr", com_alvo=True)


def caminho_da_bola(env, n: int, vel: float, seed: int | None = None, semente: int | None = None) -> np.ndarray:
    """A bola SOZINHA (sem física do drone): `reset(seed)` + `definir_trajetoria_ponto("aleatorio")` + n passos de 20 ms."""
    if seed is not None:
        env.reset(seed=seed)
    env.definir_trajetoria_ponto("aleatorio", vel=vel, semente=semente)
    p = np.empty((n, 3))
    for k in range(n):
        env._ponto_passo()
        p[k] = env.ponto_alvo
    return p


def bola_reprodutivel(env) -> dict[str, bool]:
    """As propriedades de reprodutibilidade (a mini-suite com que se mede a mutação Python do gerador)."""
    a = caminho_da_bola(env, 600, 0.5, seed=31)
    b = caminho_da_bola(env, 600, 0.5, seed=31)
    c = caminho_da_bola(env, 600, 0.5, seed=32)
    d = caminho_da_bola(env, 600, 0.5, seed=31, semente=7)
    e = caminho_da_bola(env, 600, 0.5, seed=99, semente=7)
    return {"mesma semente do episódio ⇒ MESMA bola (bit a bit)": bool(np.array_equal(a, b)),
            "sementes diferentes ⇒ bolas diferentes": float(np.abs(a - c).max()) > 0.05,
            "`semente` explícita manda (igual com episódios de sementes diferentes)": bool(np.array_equal(d, e)),
            "`semente` explícita ≠ a do episódio": float(np.abs(a - d).max()) > 0.05}


def secao_bola(c: Checagens) -> None:
    env = _env_bola()
    r = bola_reprodutivel(env)
    c.ok("[§0] bola `aleatorio` REPRODUTÍVEL: " + "; ".join(r), all(r.values()), str([k for k, v in r.items() if not v]))
    # o gerador da bola não gasta números do env: os sensores medidos saem iguais com a bola parada e a andar
    obs = []
    for modo in ("parado", "aleatorio"):
        env.ponto_modo, env.ponto_vel = modo, 0.8
        env.reset(seed=5)
        o = [env.step(np.zeros(4, dtype=np.float32))[0] for _ in range(25)]
        obs.append(np.array(o))
    c.ok("[§0] a bola não gasta um número do gerador do env: 25 decisões com a bola parada e com a bola a andar dão as MESMAS "
         "observações (sensores, estimador)", bool(np.array_equal(obs[0], obs[1])),
         f"max|Δobs| = {float(np.abs(obs[0] - obs[1]).max()):.1e}")
    dt = env.dt_decisao
    for vel in (0.3, 0.5, 0.8):
        p = caminho_da_bola(env, 60000, vel, seed=40 + round(10 * vel))          # 20 min de bola
        v = np.diff(p, axis=0) / dt
        a = np.diff(v, axis=0) / dt
        vh, ah = np.hypot(v[:, 0], v[:, 1]), np.hypot(a[:, 0], a[:, 1])
        a_teto = 2.0 * vel / env_real.PONTO_TAU_SUAVE_S
        dentro = (np.abs(p[:, :2]).max() <= env_real.PONTO_ARENA_XY and p[:, 2].min() >= env_real.PONTO_Z_MIN
                  and p[:, 2].max() <= env_real.PONTO_Z_MAX)
        c.ok(f"[§0] bola a {vel:g} m/s, 20 min: parte do repouso, |v_xy| ≤ {vel:g} m/s, |v_z| ≤ {env_real.PONTO_FRAC_Z * vel:.2f} m/s, "
             f"|a_xy| ≤ 2·vel/τ = {a_teto:.1f} m/s², |xy| ≤ {env_real.PONTO_ARENA_XY:g} m, z ∈ [{env_real.PONTO_Z_MIN}; {env_real.PONTO_Z_MAX}] m, "
             "e não é uma bola parada (anda ≥ 70 % do teto em média, percorre > 5 m de lado a lado)",
             float(np.linalg.norm(v[0])) < 0.05 * vel and vh.max() <= vel * (1 + 1e-9)
             and np.abs(v[:, 2]).max() <= env_real.PONTO_FRAC_Z * vel * (1 + 1e-9) and ah.max() <= a_teto * 1.001 and dentro
             and 0.70 * vel <= vh.mean() <= 0.95 * vel and np.ptp(p[:, 0]) > 5.0 and np.ptp(p[:, 1]) > 5.0,
             f"|v_xy| média {vh.mean():.3f} (máx {vh.max():.3f}) · |v_z| máx {np.abs(v[:, 2]).max():.3f} · |a_xy| RMS {math.sqrt(np.mean(ah ** 2)):.2f} "
             f"(máx {ah.max():.2f}) m/s² · x ∈ [{p[:, 0].min():.1f}; {p[:, 0].max():.1f}] · y ∈ [{p[:, 1].min():.1f}; {p[:, 1].max():.1f}] · "
             f"z ∈ [{p[:, 2].min():.2f}; {p[:, 2].max():.2f}] m")
    # paredes: uma bola largada junto ao limite não o atravessa e volta para dentro
    env.reset(seed=3)
    env.ponto_alvo = np.array([env_real.PONTO_ARENA_XY - 0.05, -env_real.PONTO_ARENA_XY + 0.05, env_real.PONTO_Z_MAX - 0.01])
    p = caminho_da_bola(env, 3000, 0.8)
    c.ok("[§0] paredes suaves: largada a 5 cm do canto da arena e a 1 cm do teto da banda, a bola nunca sai e ao fim de 60 s já "
         "andou para dentro (sem teleportes: passo máximo ≤ vel·dt)",
         np.abs(p[:, :2]).max() <= env_real.PONTO_ARENA_XY and p[:, 2].max() <= env_real.PONTO_Z_MAX
         and np.abs(p[-1, :2]).max() < env_real.PONTO_ARENA_XY - 0.3
         and float(np.linalg.norm(np.diff(p, axis=0), axis=1).max()) <= 0.8 * math.hypot(1.0, env_real.PONTO_FRAC_Z) * dt * 1.001,
         f"|xy| máx {np.abs(p[:, :2]).max():.3f} m · fim ({p[-1, 0]:.2f}, {p[-1, 1]:.2f}, {p[-1, 2]:.2f})")
    env.reset(seed=1)
    env.definir_trajetoria_ponto("aleatorio", vel=5.0)
    teto = env.ponto_vel
    env.definir_trajetoria_ponto("circulo", vel=0.5, raio=1.5)
    p0 = env.ponto_alvo.copy()
    pc = []
    for _ in range(200):
        env._ponto_passo()
        pc.append(env.ponto_alvo.copy())
    pc = np.array(pc)
    t = dt * np.arange(1, 201)
    w = 0.5 / 1.5
    esperado = (p0 - [1.5, 0, 0]) + 1.5 * np.stack([np.cos(w * t), np.sin(w * t), 0 * t], axis=1)
    env.definir_trajetoria_ponto("oito", vel=0.5, raio=1.5)
    p0 = env.ponto_alvo.copy()
    po = []
    for _ in range(200):
        env._ponto_passo()
        po.append(env.ponto_alvo.copy())
    esp8 = p0 + np.stack([1.5 * np.sin(w * t), 1.5 * np.sin(w * t) * np.cos(w * t), 0 * t], axis=1)
    env.definir_trajetoria_ponto("parado")
    pp = env.ponto_alvo.copy()
    env._ponto_passo()
    c.ok(f"[§0] `vel` acima da banda é cortado a {env_real.PONTO_VEL_MAX} m/s e `circulo`/`oito`/`parado` continuam as fórmulas "
         "fechadas de sempre (partem da posição atual, sem teleportes)",
         teto == env_real.PONTO_VEL_MAX and float(np.abs(pc - esperado).max()) < 1e-12
         and float(np.abs(np.array(po) - esp8).max()) < 1e-12 and bool(np.array_equal(pp, env.ponto_alvo)),
         f"teto {teto} · círculo max|Δ| {float(np.abs(pc - esperado).max()):.1e} · oito {float(np.abs(np.array(po) - esp8).max()):.1e}")


# ============================================================================================ §1 interface
def secao_interface(c: Checagens, bib) -> None:
    ganhos = tb.ler_ganhos()
    cfg = sv.SeguidorCpp(320, 240, FOVY_PI, 2, None, bib, lei="v2").cfg
    dif = {k: (float(getattr(cfg, k)), v) for k, v in ganhos.items() if abs(float(getattr(cfg, k)) - float(np.float32(v))) > 0.0}
    c.ok(f"[§1] `ibvs_ganhos.hpp` (versionado) É a Config por omissão: os {len(ganhos)} ganhos do cabeçalho ≡ `visao::config_padrao` "
         "(float32 exato), com comp_translacao = 1 e o raio em CV — e kVersaoVisao = 2",
         not dif and cfg.comp_translacao == 1 and cfg.raio_cv == 1 and bib.const["kVersaoVisao"] == 2 and cfg.versao == 2, str(dif))
    texto = tb.gerar_cabecalho(ganhos, "ida e volta")
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "g.hpp"
        f.write_text(texto, encoding="utf-8")
        volta = tb.ler_ganhos(f)
    pior = max(abs(volta[k] - float(np.float32(ganhos[k]))) / max(abs(ganhos[k]), 1e-12) for k in ganhos)
    recusa = False
    try:
        tb.gerar_cabecalho({**ganhos, "kp_y": 99.0}, "x")
    except ValueError:
        recusa = True
    c.ok("[§1] o gerador do cabeçalho faz ida e volta (gerar → ler: erro relativo ≤ 1e-6, a precisão de 6 algarismos) e RECUSA "
         "um ganho fora dos limites do treino", pior <= 1e-6 and recusa, f"pior erro relativo {pior:.1e}")
    # o que o runner recebe: sitl.config_de_hardware(camera=…) — os MESMOS ganhos, com os limites da planta
    import sitl
    env = _env_bola()
    nb = sitl.biblioteca_padrao()
    kw = {"altura_min": sitl.VOO_Z_MIN_CONTRATO - sitl.deslocamento_sensor_cm(env.model)}
    camera = {"largura": 320, "altura": 240, "fps": 30.0, "latencia_s": 0.116, "atraso_s": 0.116,
              "fovy_graus": float(env.model.cam_fovy[env.model.camera("fpv").id])}
    cfgn = sitl.config_de_hardware(env.hw, env.model, env.dt, env=env, ganhos_kw=kw, estimador_classico=True, camera=camera, bib=nb)
    s = cfgn.seguidor
    dif = {k: float(getattr(s, k)) for k, v in ganhos.items() if float(getattr(s, k)) != float(np.float32(v))}
    nuc = sitl.NucleoCpp(cfgn, nb)
    antes = ab.seguidor_antes()
    c.ok("[§1] o RUNNER (`sitl.config_de_hardware(camera=…)`, o que o `sim_view` chama) recebe a lei da versão 2 com estes ganhos, "
         "o núcleo aceita a Config (o parser de ctypes do `sitl.py` lê as structs novas) e a lei v1 só difere nos campos de "
         "`seguidor_antes()`",
         not dif and s.comp_translacao == 1 and nuc.iniciado and cfgn.usa_visao == 1 and float(s.vy_max) > 0.0
         and antes.get("comp_translacao") == 0 and antes.get("kp_y") == 0.0 and antes.get("kff_y") == 0.0
         and antes.get("k_incl_z") == 0.0, f"diferem: {dif} · antes = {sorted(antes)}")
    nuc.close()
    maus = {"k_incl_z 1,5": {"k_incl_z": 1.5}, "vy_max 0": {"vy_max": 0.0}, "comp_translacao 2": {"comp_translacao": 2},
            "kp_y negativo": {"kp_y": -0.1}, "acel_y_max NaN": {"acel_y_max": float("nan")}, "raio_cv 3": {"raio_cv": 3},
            "tau_incl_s negativo": {"tau_incl_s": -1.0}}
    aceites = [n for n, m in maus.items() if sv.SeguidorCpp(320, 240, FOVY_PI, 2, m, bib, lei="v2").iniciado]
    c.ok(f"[§1] `config_valida` recusa as Configs novas inválidas ({', '.join(maus)})", not aceites, f"aceites: {aceites}")
    recusou = False
    try:
        tb.episodios(ganhos, [ab.SEMENTES_AVALIACAO[0]], (0.5,), "x", 5.0, "projecao")
    except ValueError:
        recusou = True
    c.ok("[§1] HONESTIDADE: as sementes de afinação e de avaliação são disjuntas e o treino RECUSA uma semente de avaliação",
         recusou and not set(ab.SEMENTES_AFINACAO) & set(ab.SEMENTES_AVALIACAO) and not set(SEMENTES_TESTE) & (
             set(ab.SEMENTES_AFINACAO) | set(ab.SEMENTES_AVALIACAO)))


# ============================================================================================ §2 a versão 1, bit a bit
CENARIOS_V1 = {"circulo": (("circulo", 0.5), {}), "oito": (("oito", 0.8), {"seed": 3}),
               "oclusao": (("circulo", 0.5), {"ocultar": ((4.0, 4.6), (8.0, 9.5)), "p_outlier": 0.05}),
               "alfa_beta": (("oito", 0.5), {"modelo": 0}), "cv": (("vertical", 0.3), {"modelo": 1})}


def _laco_v1(bib, traj, kw, lei):
    antiga = sv.LEI_OMISSAO
    sv.LEI_OMISSAO = lei
    try:
        return sv.simular_laco(sv.trajetoria_alvo(*traj), T=14.0, bib=bib, **kw)["series"]
    finally:
        sv.LEI_OMISSAO = antiga


def biblioteca_de_antes(tmp: Path):
    """As fontes do núcleo de visão do commit de ANTES desta atividade, compiladas agora (None se o git não o tiver)."""
    pasta = tmp / "antes" / "nucleo"
    pasta.mkdir(parents=True, exist_ok=True)
    for f in FICHEIROS_ANTES:
        r = subprocess.run(["git", "-C", str(_RAIZ), "show", f"{COMMIT_ANTES}:experiments/09_drone_hover_rl/firmware/nucleo/{f}"],
                           capture_output=True, text=True, check=False)
        if r.returncode != 0:
            return None
        (pasta / f).write_text(r.stdout, encoding="utf-8")
    return sv.BibliotecaVisao(sv.compilar_visao(pasta, tmp / "antes" / "so", limpar=False), pasta / "visao_tipos.hpp")


def secao_versao1(c: Checagens, tmp: Path, bib) -> None:
    velha = biblioteca_de_antes(tmp)
    novas = {n: _laco_v1(bib, traj, kw, "v1") for n, (traj, kw) in CENARIOS_V1.items()}
    if velha is not None:
        pior, estados, n = 0.0, True, 0
        for nome, (traj, kw) in CENARIOS_V1.items():
            a, b = _laco_v1(velha, traj, kw, "v2"), novas[nome]            # na .so de antes, a lei por omissão É a v1
            pior = max(pior, *(max(abs(x - y) for x, y in zip(a[k], b[k], strict=True))
                               for k in ("yaw", "vx", "vz", "e_psi_est", "taxa_est", "u_pred", "v_pred")))
            estados = estados and a["estado"] == b["estado"]
            n += len(a["yaw"])
        c.ok(f"[§2] a lei da VERSÃO 1 (`visao::config_versao1`) no C++ novo ≡ o C++ de antes (fontes do commit {COMMIT_ANTES}, "
             f"compiladas agora) BIT A BIT: comandos, erros estimados, previsão e estados em {len(CENARIOS_V1)} cenários "
             f"(círculo, oito, oclusão + 5 % de deteções falsas, α-β, KF-CV) × 1400 decisões", pior == 0.0 and estados,
             f"max|Δ| = {pior!r} em {n} decisões")
    else:
        print(f"        [aviso] o git não tem o commit {COMMIT_ANTES}: a comparação viva não corre — fica a dos valores gravados")
    pior = 0.0
    for nome, (sy, sx, psi) in OURO_V1.items():
        b = novas[nome]
        pior = max(pior, abs(sum(abs(x) for x in b["yaw"]) - sy) / sy, abs(sum(abs(x) for x in b["vx"]) - sx) / sx,
                   abs(b["psi"][-1] - psi) / max(abs(psi), 1.0))
    c.ok("[§2] idem contra os valores GRAVADOS com as fontes de antes (Σ|yaw_taxa|, Σ|v_x|, ψ final por cenário; a prova que "
         "sobrevive ao histórico do git)", pior < 1e-9, f"pior erro relativo {pior:.1e}")
    v2 = sv.SeguidorCpp(320, 240, FOVY_PI, 2, None, bib, lei="v2").cfg
    v1 = sv.SeguidorCpp(320, 240, FOVY_PI, 2, None, bib, lei="v1").cfg
    c.ok("[§2] …e a versão 1 tem mesmo v_y desligado e nenhuma compensação (kp_y = kff_y = 0, comp_translacao = 0, k_incl_z = 0, "
         "raio em CA), ao contrário da versão 2",
         v1.kp_y == 0.0 and v1.kff_y == 0.0 and v1.comp_translacao == 0 and v1.k_incl_z == 0.0 and v1.raio_cv == 0
         and v2.kp_y > 0.0 and v2.comp_translacao == 1)


# ============================================================================================ §3 a lei v2 por mecanismo
G_KW = {"largura": 320, "altura": 240, "fovy": FOVY_PI}


def roteiro(bib, alvo, drone, T: float = 6.0, lei: str = "v2", cfg: dict | None = None, visivel=lambda t: True,
            atraso: float = 0.05, fps: float = 30.0) -> list:
    """Geometria ESCRITA À MÃO a alimentar o Seguidor (sem simulador, sem ruído): `alvo(t) → (x, y, z)` no mundo; `drone(t) →
    (x, y, z, roll, pitch, psi, vx, vy, vz)` com as velocidades no referencial do rumo. Câmara pinhole no centro do drone, a `fps`,
    entregue com `atraso`. Devolve as `SaidaSeguidor` (cópias) a 100 Hz, com o instante."""
    seg = sv.SeguidorCpp(G_KW["largura"], G_KW["altura"], G_KW["fovy"], 2, cfg, bib, lei=lei)
    assert seg.iniciado
    f, cx, cy = float(seg.cfg.f_px), float(seg.cfg.cx), float(seg.cfg.cy)
    fila, cam, n, prox, saidas = [], None, 0, 0.0, []
    for k in range(round(T / 0.01)):
        t = k * 0.01
        x, y, z, roll, pitch, psi, vx, vy, vz = drone(t)
        if t + 1e-9 >= prox:
            prox += 1.0 / fps
            n += 1
            p = alvo(t)
            rot = sv._rot_zyx(roll, pitch, psi)
            d = (p[0] - x, p[1] - y, p[2] - z)
            pb = tuple(rot[0][i] * d[0] + rot[1][i] * d[1] + rot[2][i] * d[2] for i in range(3))
            dist = math.sqrt(sum(q * q for q in pb))
            ok = visivel(t) and pb[0] > 0.05
            u = cx + f * (-pb[1] / pb[0]) if ok else 0.0
            v = cy + f * (-pb[2] / pb[0]) if ok else 0.0
            r = f * 0.05 / math.sqrt(max(dist * dist - 0.0025, 1e-9)) if ok else 0.0
            fila.append((t + atraso, (1 if ok else 0, u, v, r, n, round(t * 1e6))))
        while fila and fila[0][0] <= t + 1e-9:
            cam = fila.pop(0)[1]
        o = seg.passo(round(t * 1e6), roll, pitch, psi, cam, vx, vy, vz)
        saidas.append((t, sv.SaidaSeguidor_copia(seg.bib, o)))
    seg.close()
    return saidas


def _parado(x=0.0, y=0.0, z=1.0, roll=0.0, pitch=0.0, psi=0.0):
    return lambda t: (x, y, z, roll, pitch, psi, 0.0, 0.0, 0.0)


def _media(saidas, campo: str, t0: float) -> float:
    return float(np.mean([getattr(o, campo) for t, o in saidas if t >= t0]))


def mecanismos(bib) -> dict[str, bool]:
    """A mini-suite da lei v2 (≈ 1 s): uma checagem por mecanismo — é com ela que se medem os mutantes da fonte C++."""
    r: dict[str, bool] = {}
    # (a) alvo PARADO à esquerda (y = +0,3 m a 1,5 m): o drone vai para a esquerda E roda para a esquerda; na imagem o alvo está à
    #     esquerda do centro; a v1, no mesmo roteiro, não translada
    s = roteiro(bib, lambda t: (1.5, 0.3, 1.0), _parado(), T=1.2)
    o = s[-1][1]
    s1 = roteiro(bib, lambda t: (1.5, 0.3, 1.0), _parado(), T=1.2, lei="v1")
    r["sinais: alvo à esquerda ⇒ v_y > 0 (esquerda), guinada > 0, erro na imagem < 0 (esquerda do centro); a v1 dá v_y = 0"] = (
        o.estado == 0 and o.vy > 0.05 and o.yaw_taxa > 0.02 and o.e_h_cam < -math.radians(5.0) and o.e_psi > math.radians(5.0)
        and all(x.vy == 0.0 for _t, x in s1) and s1[-1][1].yaw_taxa > 0.02)
    # (b) alvo PARADO visto de um drone que ANDA (para a esquerda a 0,4 m/s e para a frente a 0,2 m/s): com a translação
    #     própria descontada, a velocidade estimada do ALVO é ≈ 0 e a guinada não antecipa nada (taxa ≈ 0); a v1 vê a linha de
    #     vista a rodar a −0,4/1,5 rad/s
    anda = lambda t: (0.2 * t, 0.4 * t, 1.0, 0.0, 0.0, 0.0, 0.2, 0.4, 0.0)
    s = roteiro(bib, lambda t: (2.6, 1.2, 1.0), anda, T=3.0)
    s1 = roteiro(bib, lambda t: (2.6, 1.2, 1.0), anda, T=3.0, lei="v1")
    vt, vr, w, w1 = _media(s, "v_alvo_tan", 1.5), _media(s, "v_alvo_rad", 1.5), _media(s, "taxa_bearing", 1.5), _media(s1, "taxa_bearing", 1.5)
    r["translação própria descontada: alvo parado visto a andar ⇒ |v_tan| < 0,05, |v_rad| < 0,08 m/s e taxa ≈ 0 (a v1 vê −0,2 rad/s)"] = (
        abs(vt) < 0.05 and abs(vr) < 0.08 and abs(w) < 0.03 and w1 < -0.12)
    # (c) alvo a andar para a ESQUERDA a 0,5 m/s, drone parado: v_tan ≈ +0,5; a translação leva a fração kff_y e a guinada o resto
    esq = lambda t: (1.6, -0.6 + 0.5 * t, 1.0)
    kappa = 0.5                                                                   # fixada aqui: não depende do ganho promovido
    s = roteiro(bib, esq, _parado(), T=1.6, cfg={"kff_y": kappa})
    jan = [(t, o) for t, o in s if 1.0 <= t <= 1.4]
    vt = float(np.mean([o.v_alvo_tan for _t, o in jan]))
    w = float(np.mean([o.taxa_bearing * o.dist * math.cos(o.e_elev) for _t, o in jan]))
    r["repartição: alvo a 0,5 m/s para a esquerda ⇒ v_tan ≈ +0,5 m/s e, com kff_y = 0,5, a guinada antecipa só a outra metade"] = (
        abs(vt - 0.5) < 0.06 and abs(w - (1.0 - kappa) * vt) < 0.03 and s[-1][1].vy > 0.1)
    # (d) compensação da INCLINAÇÃO: drone parado com 6° de nariz para baixo; alvo à mesma altura (elevação inercial 0) aparece 6°
    #     ACIMA do centro ⇒ a v2 sobe, a v1 fica; alvo no CENTRO da imagem (0,158 m abaixo) ⇒ a v2 fica, a v1 desce
    th = math.radians(6.0)
    vert = {"k_incl_z": 1.0, "kp_z": 1.5}                                         # idem: o mecanismo, não o ganho promovido
    s = roteiro(bib, lambda t: (1.5, 0.0, 1.0), _parado(pitch=th), T=2.0, cfg=vert)
    s1 = roteiro(bib, lambda t: (1.5, 0.0, 1.0), _parado(pitch=th), T=2.0, lei="v1")
    sc = roteiro(bib, lambda t: (1.5, 0.0, 1.0 - 1.5 * math.tan(th)), _parado(pitch=th), T=2.0, cfg=vert)
    sc1 = roteiro(bib, lambda t: (1.5, 0.0, 1.0 - 1.5 * math.tan(th)), _parado(pitch=th), T=2.0, lei="v1")
    r["inclinação: com 6° de pitch a v2 anula o erro vertical NA IMAGEM (sobe com o alvo acima do centro; fica com ele centrado) e a v1 a elevação inercial"] = (
        abs(math.degrees(s[-1][1].e_v_cam) - 6.0) < 0.3 and s[-1][1].vz > 0.08 and abs(s1[-1][1].vz) < 0.01
        and abs(math.degrees(sc[-1][1].e_v_cam)) < 0.3 and abs(sc[-1][1].vz) < 0.01 and sc1[-1][1].vz < -0.05)
    # (e) limites: |v_y| ≤ vy_max e o slew ≤ acel_y_max (alvo MUITO à esquerda, ganho alto)
    cfg = {"kp_y": 3.0, "vy_max": 0.6, "acel_y_max": 1.5}
    s = roteiro(bib, lambda t: (1.5, 0.8, 1.0), _parado(), T=2.5, cfg=cfg)
    vy = [o.vy for _t, o in s]
    r["limites: v_y satura em vy_max, sobe no máximo a acel_y_max e levanta kFlagSaturouLateral"] = (
        abs(max(vy) - 0.6) < 1e-6 and max(abs(vy[i + 1] - vy[i]) for i in range(len(vy) - 1)) <= 1.5 * 0.01 * 1.001
        and any(o.flags & ab.FLAG_SATUROU_LATERAL for _t, o in s))
    # (f) perda: o alvo some aos 2 s ⇒ PERDIDO e v_y de volta a 0 (com o slew)
    s = roteiro(bib, lambda t: (1.5, 0.3, 1.0), _parado(), T=4.5, visivel=lambda t: t < 2.0)
    r["perda: sem alvo ⇒ PERDIDO, procura só em guinada e v_y, v_x, v_z de volta a 0"] = (
        s[-1][1].estado == 2 and s[-1][1].vy == 0.0 and s[-1][1].vx == 0.0 and s[-1][1].vz == 0.0 and s[-1][1].procura == 1
        and any(o.vy > 0.05 for t, o in s if t < 2.0))
    return r


def secao_lei(c: Checagens, bib) -> None:
    for nome, ok in mecanismos(bib).items():
        c.ok(f"[§3] {nome}", ok)


# ============================================================================================ §4 as medidas
def secao_medidas(c: Checagens) -> None:
    import mujoco
    import visao
    from sitl_camera import CameraSITL
    env = _env_bola()
    env.reset(seed=2)
    m, d = env.model, env.data
    ver = ab.Verdade(m)
    pior, sinais = 0.0, True
    for pos, quat in (((1.5, 0.0, 1.0), (1, 0, 0, 0)), ((2.0, 0.4, 1.3), (1, 0, 0, 0)), ((1.2, -0.3, 0.8), (0.99, 0.02, 0.05, 0.12)),
                      ((3.0, 0.6, 0.7), (0.98, -0.05, -0.08, -0.15))):
        d.qpos[0:3] = (0.0, 0.0, 1.0)
        d.qpos[3:7] = np.array(quat, dtype=float) / np.linalg.norm(quat)
        visao.posicionar_ponto(m, d, pos)
        mujoco.mj_forward(m, d)
        pr = visao.projetar(m, d, pos, camera="fpv", largura_px=320, altura_px=240)
        e_h, e_v, e, u, v, campo, _dist = ver.medir(d, pos)
        pior = max(pior, abs(u - (pr["u"] - 160.0)), abs(v - (pr["v"] - 120.0)))
        sinais = sinais and campo == pr["visivel"] and abs(math.tan(e) * ver.f_px - math.hypot(u, v)) < 1e-9
        sinais = sinais and (e_h > 0) == (u > 0) and (e_v > 0) == (v < 0)
    d.qpos[0:3] = (0.0, 0.0, 1.0)
    cam_z = None
    res = {}
    for nome, th in (("nivelado", 0.0), ("nariz para baixo 8°", math.radians(8.0))):
        d.qpos[3:7] = (math.cos(th / 2), 0.0, math.sin(th / 2), 0.0)
        mujoco.mj_forward(m, d)
        if cam_z is None:
            cam_z = float(d.cam_xpos[m.camera("fpv").id][2])
        alvo = (3.0, 0.0, cam_z)
        visao.posicionar_ponto(m, d, alvo)
        res[nome] = ver.medir(d, alvo)
    dv = math.degrees(res["nariz para baixo 8°"][1] - res["nivelado"][1])
    esq = ver.medir(d, (3.0, 1.0, cam_z))
    tras = ver.medir(d, (-3.0, 0.2, cam_z))
    c.ok("[§4] a VERDADE do protocolo (`avaliar_bola.Verdade`: pose exata da câmara) ≡ `visao.projetar` em 4 poses com roll/pitch/yaw "
         "(< 1e-6 px), com os sinais do enunciado (+ direita, + acima), e VÊ a inclinação do corpo: 8° de nariz para baixo põem a "
         "bola ≈ 8° acima do centro; atrás da câmara conta como fora do campo com o erro em px saturado",
         pior < 1e-6 and sinais and 7.0 < dv < 9.0 and esq[0] < 0.0 and not tras[5] and abs(tras[3]) == 160.0 and tras[2] > math.pi / 2,
         f"max|Δ| {pior:.1e} px · Δe_v com 8° de pitch = {dv:.2f}° · bola à esquerda: e_h = {math.degrees(esq[0]):.1f}°")
    # câmara em modo projeção (treino) vs renderizada + detetor C++ (avaliação)
    ren = CameraSITL(env, modo="render")
    pro = CameraSITL(env, modo="projecao", ruido_px=0.0)
    d.qpos[3:7] = (1.0, 0.0, 0.0, 0.0)
    casos = [((1.5, 0.0, 1.0), True), ((2.0, 0.5, 1.2), True), ((1.0, -0.3, 0.8), True), ((3.0, 0.9, 1.4), True), ((2.5, -1.0, 0.7), True),
             ((1.5, 1.4, 1.0), False), ((-2.0, 0.0, 1.0), False), ((1.2, 0.0, 2.1), False)]
    du = dr_ = 0.0
    val_ok = True
    for pos, visivel in casos:
        visao.posicionar_ponto(m, d, pos)
        a, b = ren.capturar(d), pro.capturar(d)
        val_ok = val_ok and a[0] == b[0] == int(visivel)
        if visivel:
            du, dr_ = max(du, abs(a[1] - b[1]), abs(a[2] - b[2])), max(dr_, abs(a[3] - b[3]))
    ren.fechar()
    pro.fechar()
    c.ok("[§4] a câmara em modo PROJEÇÃO (o treino sem GPU) ≡ a RENDERIZADA + detetor C++ (a avaliação): mesma validade em 8 "
         "posições (5 no campo; 3 fora: de lado, atrás, por cima) e |Δu|, |Δv| < 0,3 px, |Δraio| < 0,5 px",
         val_ok and du < 0.3 and dr_ < 0.5, f"max|Δcentróide| {du:.3f} px · max|Δraio| {dr_:.3f} px")


# ============================================================================================ §5 malha fechada
def secao_malha(c: Checagens, n_jobs: int) -> None:
    import sitl
    sitl.biblioteca_padrao()
    extra = {"t_medida": 20.0}
    jobs = [j for var in ("antes", "depois") for j in ab.jobs_variante(var, SEMENTES_TESTE, (0.5,), **extra)]
    rep = [{**j, "camera_modo": "projecao", "t_medida": 6.0, "variante": f"rep{i}"}
           for i in (0, 1) for j in ab.jobs_variante("depois", SEMENTES_TESTE[:1], (0.5,), caminhos={"pi_116ms": ab.CAMINHOS["pi_116ms"]})]
    res = ab.executar(jobs + rep, n_jobs)
    por = {}
    for j, r in zip(jobs, res[: len(jobs)], strict=True):
        por.setdefault((j["variante"], j["caminho"]), []).append(r)

    def med(var, cam, chave):
        return float(np.mean([r[chave] for r in por[(var, cam)]]))
    quedas = [(j["variante"], j["caminho"], j["seed"]) for j, r in zip(jobs, res, strict=False) if r.get("terminou")]
    c.ok(f"[§5] malha fechada no simulador completo (sementes de teste {SEMENTES_TESTE}, bola a 0,5 m/s, câmara renderizada): "
         "nenhuma queda em 8 episódios (versão 1 e versão 2, 116 ms e 21 ms)", not quedas, str(quedas))
    if quedas:
        return
    for cam in ab.CAMINHOS:
        a, dps = med("antes", cam, "centro_rms_graus"), med("depois", cam, "centro_rms_graus")
        av, dv = med("antes", cam, "v_rms_graus"), med("depois", cam, "v_rms_graus")
        ah, dh = med("antes", cam, "h_rms_graus"), med("depois", cam, "h_rms_graus")
        c.ok(f"[§5] {cam}: a versão 2 CENTRA MELHOR que a versão 1 — erro de centragem RMS {a:.2f}° → {dps:.2f}° (≤ 65 % do de antes; "
             f"medido 46–49 %), vertical {av:.2f}° → {dv:.2f}° (≤ 60 %), horizontal {ah:.2f}° → {dh:.2f}° (não piora), e fica abaixo de "
             "3,5° RMS; bola 100 % do tempo no campo, ≥ 97 % em A_SEGUIR, |D − d*| RMS < 0,45 m",
             dps <= 0.65 * a and dv <= 0.60 * av and dh <= 1.05 * ah and dps < 3.5 and med("depois", cam, "frac_fov") == 1.0
             and med("depois", cam, "frac_a_seguir") >= 0.97 and med("depois", cam, "dist_erro_rms") < 0.45,
             f"no campo {100 * med('depois', cam, 'frac_fov'):.0f} % · A_SEGUIR {100 * med('depois', cam, 'frac_a_seguir'):.1f} % · "
             f"|D−d*| {med('depois', cam, 'dist_erro_rms'):.3f} m · pitch RMS {med('antes', cam, 'pitch_rms_graus'):.2f}° → "
             f"{med('depois', cam, 'pitch_rms_graus'):.2f}°")
    c.ok("[§5] a versão 2 USA a translação lateral: o rolamento RMS sobe (a v1 só rola por acoplamento) e o drone percorre "
         f"{med('depois', 'pi_116ms', 'caminho_drone_m'):.1f} m em 20 s atrás da bola (v1: {med('antes', 'pi_116ms', 'caminho_drone_m'):.1f} m)",
         med("depois", "pi_116ms", "roll_rms_graus") > max(0.8, 1.3 * med("antes", "pi_116ms", "roll_rms_graus"))
         and med("depois", "pi_116ms", "caminho_drone_m") > 2.0,
         f"roll RMS {med('antes', 'pi_116ms', 'roll_rms_graus'):.2f}° → {med('depois', 'pi_116ms', 'roll_rms_graus'):.2f}°")
    r0, r1 = res[len(jobs)], res[len(jobs) + 1]
    c.ok("[§5] REPRODUTÍVEL: o mesmo episódio (semente, velocidade, latência; câmara em modo projeção) corrido 2× em processos "
         "diferentes tem a MESMA bola, bit a bit (velocidade média e LOS iguais), e o mesmo voo até ao arredondamento da planta "
         "(|Δ centragem RMS| < 0,2°, |Δ distância| < 0,02 m; medido ≈ 3e-14°)",
         r0["vel_bola_media"] == r1["vel_bola_media"] and r0["vel_bola_max"] == r1["vel_bola_max"]
         and abs(r0["centro_rms_graus"] - r1["centro_rms_graus"]) < 0.2 and abs(r0["dist_erro_rms"] - r1["dist_erro_rms"]) < 0.02,
         f"centragem {r0['centro_rms_graus']!r} vs {r1['centro_rms_graus']!r} · bola {r0['vel_bola_media']!r} vs {r1['vel_bola_media']!r}")


# ============================================================================================ §6 mutações
MUTACOES_CPP = (
    ("sinal do v_y", "ibvs.hpp", "vy_alvo = fator * (c_.kp_y *", "vy_alvo = -fator * (c_.kp_y *"),
    ("translação própria com o sinal trocado (eixo y)", "alvo.hpp", "const float ry = dist * ce * sinf(*az) - d[1];",
     "const float ry = dist * ce * sinf(*az) + d[1];"),
    ("a captura não é referida à posição própria", "ibvs.hpp", "cam.raio / c_.f_px, comp ? pcap : nullptr);",
     "cam.raio / c_.f_px, nullptr);"),
    ("sinal da compensação da inclinação", "ibvs.hpp", "e_z = e_el + c_.k_incl_z * incl_f_;", "e_z = e_el - c_.k_incl_z * incl_f_;"),
    ("repartição desligada (a guinada antecipa TUDO)", "ibvs.hpp", "w_los = (v_tan - vy_ff) / alcance;",
     "w_los = (v_tan - 0.0f * vy_ff) / alcance;"),
)


def secao_mutacoes(c: Checagens, tmp: Path, bib) -> None:
    base = mecanismos(bib)
    c.ok(f"[§6] CONTROLO: o C++ INTACTO passa as {len(base)} checagens da mini-suite de mecanismos (o critério dos mutantes)",
         all(base.values()), str([k for k, v in base.items() if not v]))
    apanhadas = 0
    for i, (nome, ficheiro, antigo, novo) in enumerate(MUTACOES_CPP):
        pasta = tmp / f"mut{i}" / "nucleo"
        shutil.copytree(NUCLEO_DIR, pasta, ignore=shutil.ignore_patterns("__pycache__"))
        alvo = pasta / ficheiro
        texto = alvo.read_text(encoding="utf-8")
        if texto.count(antigo) != 1:
            c.ok(f"[§6] MUTAÇÃO «{nome}» ({ficheiro}) aplica-se", False, f"o texto original aparece {texto.count(antigo)}× (tem de ser 1)")
            continue
        alvo.write_text(texto.replace(antigo, novo), encoding="utf-8")
        mut = sv.BibliotecaVisao(sv.compilar_visao(pasta, tmp / "so_mut", limpar=False), pasta / "visao_tipos.hpp")
        falhou = [k for k, v in mecanismos(mut).items() if not v]
        apanhadas += int(bool(falhou))
        c.ok(f"[§6] MUTAÇÃO «{nome}» ({ficheiro}) é APANHADA", bool(falhou),
             ("falha: " + falhou[0][:110]) if falhou else "NÃO FOI APANHADA — o teste não a vê")
    # mutações do Python: o gerador da bola sem semente; e a bola sem teto de velocidade
    env = _env_bola()
    original = env_real.DroneRealEnv._semear_ponto
    try:
        env_real.DroneRealEnv._semear_ponto = lambda self, semente=None: setattr(self, "_ponto_rng", np.random.default_rng())
        mut = bola_reprodutivel(env)
    finally:
        env_real.DroneRealEnv._semear_ponto = original
    falhou = [k for k, v in mut.items() if not v]
    apanhadas += int(bool(falhou))
    c.ok("[§6] MUTAÇÃO «gerador da bola sem semente (o RNG de antes)» (env_real.py) é APANHADA", bool(falhou),
         ("falha: " + falhou[0]) if falhou else "NÃO FOI APANHADA")
    tau = env_real.PONTO_TAU_SUAVE_S
    try:
        env_real.PONTO_TAU_SUAVE_S = 1e-6                    # sem o PT1: a velocidade salta (aceleração «infinita»)
        p = caminho_da_bola(env, 3000, 0.5, seed=41)
    finally:
        env_real.PONTO_TAU_SUAVE_S = tau
    a = np.diff(np.diff(p, axis=0) / env.dt_decisao, axis=0) / env.dt_decisao
    apanhou = float(np.hypot(a[:, 0], a[:, 1]).max()) > 2.0 * 0.5 / tau * 1.001
    apanhadas += int(apanhou)
    c.ok("[§6] MUTAÇÃO «bola sem suavização (OU puro: aceleração de ruído branco)» (env_real.py) é APANHADA pelo teto de aceleração do §0",
         apanhou, f"|a_xy| máx {float(np.hypot(a[:, 0], a[:, 1]).max()):.1f} m/s² > {2.0 * 0.5 / tau:.1f}")
    total = len(MUTACOES_CPP) + 2
    c.ok(f"[§6] {apanhadas}/{total} mutações apanhadas (o enunciado pede ≥ 3)", apanhadas == total)


# ============================================================================================ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="prova do modo «seguir a bola»")
    ap.add_argument("--rapido", action="store_true", help="sem o §5 (malha fechada no simulador completo)")
    ap.add_argument("--secoes", default="0,1,2,3,4,5,6")
    ap.add_argument("--jobs", type=int, default=min(10, max(1, (os.cpu_count() or 2) - 2)))
    args = ap.parse_args(argv)
    secs = set(args.secoes.split(","))
    if args.rapido:
        secs.discard("5")
    print("== teste_bola — modo «seguir a bola»: bola aleatória + lei IBVS versão 2 (guinada + translação lateral) em C++ de firmware")
    c = Checagens()
    t0 = time.time()
    bib = sv.carregar_biblioteca()
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as d:
        tmp = Path(d)
        if "5" in secs:                       # primeiro: cria processos (fork) antes de qualquer contexto EGL neste processo
            print("== §5 malha fechada no simulador completo (versão 1 × versão 2)")
            secao_malha(c, args.jobs)
        if "0" in secs:
            print("== §0 a bola aleatória")
            secao_bola(c)
        if "1" in secs:
            print("== §1 interface: ganhos versionados, Config por omissão, runner")
            secao_interface(c, bib)
        if "2" in secs:
            print("== §2 a lei da versão 1 continua lá, bit a bit")
            secao_versao1(c, tmp, bib)
        if "3" in secs:
            print("== §3 a lei da versão 2, mecanismo a mecanismo")
            secao_lei(c, bib)
        if "4" in secs:
            print("== §4 as medidas: verdade na imagem e câmara em modo projeção")
            secao_medidas(c)
        if "6" in secs:
            print("== §6 mutações (C++ recompilado de verdade + Python)")
            secao_mutacoes(c, tmp, bib)
    n, f = len(c.linhas), len(c.falhas)
    print(f"[teste] {n - f}/{n} checagens OK em {time.time() - t0:.0f} s")
    if f:
        print("FALHARAM:")
        for x in c.falhas:
            print("  -", x[:170])
    else:
        print("a bola aleatória é reprodutível e plausível, a lei v2 (guinada + translação lateral + compensações) centra-a melhor "
              "que a v1 no simulador completo, a v1 continua bit a bit no firmware e os ganhos por omissão são os versionados")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
