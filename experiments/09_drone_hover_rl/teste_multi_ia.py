#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_multi_ia.py — PROVA do mecanismo multi-IA de bordo.

O que se prova (a cascata só é confiável se a identidade, o fail-safe e a publicação forem testados):

  §1 CASCATA = IA-1 SOZINHA quando não há tracker (não-tautologia incluída):
     · com a IA-2 ausente, `cascata.passo(t, obs)` devolve EXATAMENTE a ação da IA-1 sozinha
       (max|Δ| = 0 sobre estados aleatórios — é isto que garante que o mecanismo não muda o voo
       quando só há uma IA);
     · com uma IA-2 A PRODUZIR v_ref ≠ 0 a ação MUDA (max|Δ| > 0) — sem isto a prova anterior seria
       uma tautologia (uma cascata que ignora o tracker passaria sempre);
     · a substituição do `v_ref` na obs toca SÓ nos canais do contrato (21:24 em obs 24/48);
  §2 WATCHDOG/FAIL-SAFE:
     · IA-2 ausente → `v_ref_fonte: "wasdqe"` (o comando do site continua — nunca sem controlo);
     · IA-2 a falhar (inferência rebenta) → volta ao WASDQE e aos 3 erros seguidos fica `erro`;
     · IA-1 a falhar → AÇÃO NEUTRA `ctbr = [0,0,0,0]` + aviso («o FC mantém o drone»);
     · contas por IA: inferências, latência p50/p99, última obs/ação, ritmo por IA (25 vs 50 Hz);
  §3 RUNNER: a telemetria publica a chave aditiva `"multi_ia"` (2 IAs: voo + seguimento; a IA-2
     `sem_politica` quando não há política — e nada rebenta com ela em falta);
  §4 SERVIDOR: `/api/state` publica `multi_ia` e `rpi5.multi_ia` (com semáforo) e as linhas do
     `/api/sim` levam `multi_ia` — a fronteira site↔API está ligada.

Uso: `uv run --group hover-rl python experiments/09_drone_hover_rl/teste_multi_ia.py`
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import ClassVar

import numpy as np

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

from multi_ia import (
    ACAO_NEUTRA_CTBR,
    CANAIS_V_REF,
    IA,
    TAXA_IA_SEGUIMENTO_HZ,
    TAXA_IA_VOO_HZ,
    CascataMultiIA,
    configurar_escalas_v_ref,
    observacao_seguimento,
)

MODELO_VOO = _AQUI / "out" / "real_1950_voo_final" / "final.zip"


class Checagens:
    def __init__(self, titulo: str) -> None:
        self.titulo, self.linhas, self.falhas = titulo, [], []

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.linhas.append(nome)
        if not cond:
            self.falhas.append(nome)
        print(f"        [{'OK  ' if cond else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""),
              flush=True)
        return bool(cond)


def _carregar_voo():
    """A IA-1 real (`out/real_1950_voo_final/final.zip`) — a política que voa a planta 1950."""
    from stable_baselines3 import PPO
    return PPO.load(str(MODELO_VOO), device="cpu")


def _obs_aleatorias(rng, n: int = 8) -> list:
    configurar_escalas_v_ref(1.0, 0.7)
    return [rng.normal(scale=0.3, size=48).astype(np.float32) for _ in range(n)]


def _json_rota(base: str, rota: str):
    try:
        with urllib.request.urlopen(base + rota, timeout=5) as resposta:
            return resposta.status, json.loads(resposta.read())
    except Exception as erro:                          # noqa: BLE001 — o teste quer o erro como dado
        return 0, {"erro": f"{type(erro).__name__}: {erro}"}


# ============================================================================================ §1
def secao_cascata(c: Checagens) -> None:
    politica = _carregar_voo()
    rng = np.random.default_rng(7)
    obs_list = _obs_aleatorias(rng)

    # (a) sem IA-2: a cascata devolve EXATAMENTE a ação da IA-1 (identidade — a prova principal)
    cascata = CascataMultiIA(
        ia_voo=IA(nome="voo", papel="v_ref → ação", taxa_hz=TAXA_IA_VOO_HZ, politica=politica))
    diferencas = []
    for i, obs in enumerate(obs_list):
        acao_cascata = cascata.passo(0.02 * i, obs)
        acao_direta, _ = politica.predict(obs, deterministic=True)
        diferencas.append(float(np.max(np.abs(acao_cascata - np.asarray(acao_direta, dtype=float)))))
    c.ok("[§1] sem IA-2: a cascata dá AÇÕES IDÊNTICAS à IA-1 sozinha (max|Δ| = 0)",
         max(diferencas) == 0.0, f"max|Δ| = {max(diferencas):.3e} sobre {len(obs_list)} estados")

    # (b) NÃO-TAUTOLOGIA: com uma IA-2 a produzir v_ref ≠ 0 a ação MUDA
    tracker = IA(nome="seguimento", papel="ponto → v_ref", taxa_hz=TAXA_IA_SEGUIMENTO_HZ,
                 politica=lambda obs: np.array([1.0, 0.0, 0.0]), obs_de=lambda: np.zeros(12, np.float32))
    cascata_t = CascataMultiIA(
        ia_voo=IA(nome="voo", papel="v_ref → ação", taxa_hz=TAXA_IA_VOO_HZ, politica=politica),
        ia_seguimento=tracker)
    diferencas_t = []
    for i, obs in enumerate(obs_list[:6]):       # ≥3 ciclos do tracker (25 Hz) até a histerese engatar
        acao_t = cascata_t.passo(0.02 * i, obs)
        acao_direta, _ = politica.predict(obs, deterministic=True)
        diferencas_t.append(float(np.max(np.abs(acao_t - np.asarray(acao_direta, dtype=float)))))
    c.ok("[§1] NÃO-TAUTOLOGIA: com o tracker a produzir v_ref ≠ 0 a ação MUDA (max|Δ| > 0)",
         max(diferencas_t) > 1e-6, f"max|Δ| = {max(diferencas_t):.4f}")
    est_t = cascata_t.estado()
    c.ok("[§1] com o tracker ativo a fonte do v_ref é o tracker (visível no estado)",
         est_t["v_ref_fonte"] == "seguimento", f"fonte={est_t['v_ref_fonte']}")

    # (c) a substituição toca SÓ nos canais do contrato
    obs = np.zeros(48, dtype=np.float32)
    obs[21:24] = [0.5, -0.5, 0.2]                        # v_ref do WASDQE (escalado) no ATOR
    obs[45:48] = [0.5, -0.5, 0.2]                        # e no CRÍTICO
    obs_sub = cascata_t._substituir_v_ref(obs, np.array([1.0, 0.0, -0.7]))
    fora = [i for i in range(48) if i not in (*range(21, 24), *range(45, 48))]
    # os canais guardam o v_ref ESCALADO (vx/VOO_VEL, vy/VOO_VEL, vz/VOO_SUBIDA = 0,7) — logo
    # [1.0, 0.0, -0.7] m/s vira [1.0, 0.0, -1.0] na obs (é a escala do contrato r11)
    c.ok("[§1] a substituição do v_ref toca SÓ nos canais 21:24 e 45:48 (contrato r11, escalado)",
         bool(np.allclose(obs_sub[21:24], [1.0, 0.0, -1.0]) and np.allclose(obs_sub[45:48], [1.0, 0.0, -1.0])
              and np.allclose(obs_sub[fora], obs[fora])),
         f"canais = {CANAIS_V_REF.get(48)} · canais = {obs_sub[21:24].tolist()}")
    c.ok("[§1] sem canais de v_ref (obs clássica 21) nada se substitui",
         np.allclose(cascata_t._substituir_v_ref(np.zeros(21, np.float32), np.ones(3)), 0.0))


# ============================================================================================ §2
def secao_watchdog(c: Checagens) -> None:
    configurar_escalas_v_ref(1.0, 0.7)
    rng = np.random.default_rng(11)

    # (a) IA-2 ausente: a fonte é o WASDQE — nunca se fica sem controlo
    cascata = CascataMultiIA(ia_voo=IA(nome="voo", papel="p", taxa_hz=50.0,
                                       politica=lambda obs: np.zeros(4)))
    acao = cascata.passo(0.02, rng.normal(size=48).astype(np.float32))
    c.ok("[§2] IA-2 ausente: v_ref vem do WASDQE e a ação sai na mesma (nunca sem controlo)",
         cascata.estado()["v_ref_fonte"] == "wasdqe" and acao.shape == (4,),
         f"fonte={cascata.estado()['v_ref_fonte']} · acao={acao.tolist()}")
    c.ok("[§2] sem tracker o estado diz `sem_politica` (honesto — nada se inventa)",
         cascata.estado()["ias"][1]["estado"] == "sem_politica")

    # (b) IA-2 a FALHAR (a inferência rebenta): volta ao WASDQE e aos 3 erros seguidos fica `erro`
    def rebenta(obs):
        raise RuntimeError("tracker em chamas")

    tracker = IA(nome="seguimento", papel="ponto → v_ref", taxa_hz=25.0, politica=rebenta,
                 obs_de=lambda: np.zeros(12, np.float32))
    cascata_f = CascataMultiIA(ia_voo=IA(nome="voo", papel="p", taxa_hz=50.0,
                                         politica=lambda obs: np.zeros(4)), ia_seguimento=tracker)
    for k in range(8):                      # 8 passos × 20 ms = 160 ms → ≥3 execuções a 25 Hz
        cascata_f.passo(0.02 * k, rng.normal(size=48).astype(np.float32))
    est_f = cascata_f.estado()
    c.ok("[§2] IA-2 a rebentar 3× seguidas: estado `erro` e o v_ref continua a ser o do WASDQE",
         est_f["ias"][1]["estado"] == "erro" and est_f["v_ref_fonte"] == "wasdqe",
         f"estado={est_f['ias'][1]['estado']} · fonte={est_f['v_ref_fonte']} · "
         f"falhas={est_f['ias'][1]['falhas']}")

    # (c) IA-1 a FALHAR: AÇÃO NEUTRA + aviso (o FC mantém o drone)
    def voo_rebenta(obs):
        raise ValueError("rede de voo em baixo")

    cascata_n = CascataMultiIA(ia_voo=IA(nome="voo", papel="p", taxa_hz=50.0, politica=voo_rebenta))
    acoes = [cascata_n.passo(0.02 * k, rng.normal(size=48).astype(np.float32)) for k in range(3)]
    est_n = cascata_n.estado()
    c.ok("[§2] IA-1 a rebentar: ação NEUTRA ctbr = [0,0,0,0] (pairagem + taxas zero)",
         all(np.allclose(a, ACAO_NEUTRA_CTBR) for a in acoes), f"acoes={acoes[-1].tolist()}")
    c.ok("[§2] o aviso diz que o FC MANTÉM o drone (e o estado da IA fica degradado)",
         (est_n["aviso"] or "").find("FC mantém") >= 0
         and est_n["ias"][0]["estado"] in ("fallback", "erro"),
         f"estado={est_n['ias'][0]['estado']}")

    # (d) contas por IA: inferências, latências p50/p99, última obs/ação, ritmo (25 vs 50 Hz)
    tracker_bom = IA(nome="seguimento", papel="ponto → v_ref", taxa_hz=25.0,
                     politica=lambda obs: np.array([0.2, 0.0, 0.1]),
                     obs_de=lambda: np.zeros(12, np.float32))
    cascata_c = CascataMultiIA(ia_voo=IA(nome="voo", papel="p", taxa_hz=50.0,
                                         politica=lambda obs: np.zeros(4)), ia_seguimento=tracker_bom)
    t0 = time.perf_counter()
    for k in range(20):
        cascata_c.passo(t0 + 0.02 * k, rng.normal(size=48).astype(np.float32))
    est_c = cascata_c.estado()
    voo_c, seg_c = est_c["ias"]
    c.ok("[§2] contas por IA: inferências > 0 e latência p50/p99 preenchida (estilo deploy.py)",
         voo_c["n_inferencias"] == 20 and voo_c["latencia"]["p50_us"] is not None
         and voo_c["latencia"]["p99_us"] is not None, f"voo n={voo_c['n_inferencias']}")
    c.ok("[§2] a IA-2 corre no SEU ritmo (25 Hz): ~metade das inferências da IA-1 (50 Hz)",
         5 <= seg_c["n_inferencias"] <= 12,
         f"seguimento n={seg_c['n_inferencias']} vs voo n={voo_c['n_inferencias']}")
    c.ok("[§2] última observação e última ação guardadas por IA",
         voo_c["ultima_obs"] is not None and voo_c["ultima_acao"] is not None
         and seg_c["ultima_acao"] is not None)
    c.ok("[§2] o orçamento soma as latências das IAs contra o período de 20 ms (50 Hz)",
         est_c["latencia_total_us"]["p50_us"] is not None and est_c["periodo_us"] == 20000.0
         and est_c["fc"]["ia"] is False,
         f"total p50={est_c['latencia_total_us']['p50_us']} µs · período={est_c['periodo_us']} µs")

    # (e) observação do tracker: placeholder documentado, sem inventar ponto
    class Vazio:
        pass

    obs_seg = observacao_seguimento(Vazio())
    c.ok("[§2] observacao_seguimento sem ponto em env: 13 canais com visivel = 0 (nunca se inventa ponto)",
         obs_seg.shape == (13,) and obs_seg[3] == 0.0, f"obs={obs_seg.tolist()[:4]}…")

    class ComPonto:
        ponto_uv_raio: ClassVar[dict] = {"visivel": True, "centro": [0.5, -0.2], "raio": 0.1}

    obs_seg2 = observacao_seguimento(ComPonto())
    c.ok("[§2] observacao_seguimento lê o ponto quando existe em env (u,v,raio,visivel=1)",
         obs_seg2[3] == 1.0 and abs(obs_seg2[0] - 0.5) < 1e-6 and abs(obs_seg2[1] + 0.2) < 1e-6,
         f"obs={obs_seg2.tolist()[:4]}…")


# ============================================================================================ §3/§4
def secao_runner_servidor(c: Checagens) -> None:
    """Runner + servidor reais: a telemetria publica `"multi_ia"` e as rotas levam-no ao site."""
    pasta = Path(tempfile.mkdtemp(prefix="multi_ia_", dir=os.environ.get("TMPDIR")))
    telemetria, controlo = pasta / "telemetria.jsonl", pasta / "controlo.json"
    comando = [sys.executable, str(_AQUI / "sim_view.py"), "--sem-janela", "--max-segundos", "4",
               "--controlo", str(controlo), "--telemetria", str(telemetria), "--fpv", str(pasta),
               "--model", str(MODELO_VOO),
               # cenário SEM tracker SEMPRE determinístico: a auto-descoberta encontraria a política
               # promovida em out/real_1950_seguimento_final/ (e o estado deixaria de ser `sem_politica`)
               "--sem-seguimento"]
    feito = subprocess.run(comando, cwd=str(_AQUI), capture_output=True, text=True, timeout=240,
                           check=False)
    c.ok("[§3] o runner corre com a cascata e SEM política de seguimento sem rebentar (exit 0)",
         feito.returncode == 0, f"exit={feito.returncode}")
    linhas = [json.loads(l) for l in telemetria.read_text(encoding="utf-8").splitlines() if l.strip()]
    com_multi = [l for l in linhas if isinstance(l.get("multi_ia"), dict)]
    c.ok("[§3] a telemetria publica a chave aditiva \"multi_ia\" (não inventa quando não há)",
         bool(com_multi) and len(com_multi) >= 5, f"{len(com_multi)}/{len(linhas)} linhas com multi_ia")
    estado = com_multi[-1]["multi_ia"] if com_multi else {}
    ias = estado.get("ias") or []
    c.ok("[§3] o estado tem as IAs por nome/papel/taxa (voo 50 Hz + seguimento 25 Hz)",
         {ia.get("nome") for ia in ias} >= {"voo", "seguimento"}
         and all(ia.get("papel") and ia.get("taxa_hz") for ia in ias),
         str([(ia.get("nome"), ia.get("taxa_hz"), ia.get("estado")) for ia in ias]))
    c.ok("[§3] sem tracker: a IA-2 vem `sem_politica` e a fonte do v_ref é o WASDQE (honesto)",
         any(ia.get("nome") == "seguimento" and ia.get("estado") == "sem_politica" for ia in ias)
         and estado.get("v_ref_fonte") == "wasdqe", f"fonte={estado.get('v_ref_fonte')}")
    c.ok("[§3] a IA-1 está a correr com latências medidas (p50/p99) e inferências contadas",
         any(ia.get("nome") == "voo" and ia.get("n_inferencias", 0) > 0
             and (ia.get("latencia") or {}).get("p50_us") is not None for ia in ias))

    # servidor: /api/state + /api/sim levam multi_ia
    porta = 8692
    servidor = subprocess.Popen(
        [sys.executable, str(_AQUI / "sim_site.py"), "--sem-browser", "--sem-janela", "--port", str(porta),
         "--controlo", str(controlo), "--telemetria", str(telemetria), "--model", str(MODELO_VOO)],
        cwd=str(_AQUI), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    base = None
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 120:
        linha = servidor.stdout.readline()
        if not linha:
            break
        if "site em http" in linha:
            base = f"http://127.0.0.1:{porta}"
            break
    if base is None:
        c.ok("[§4] o servidor arranca", False, "sem URL do sim_site em 120 s")
        return
    try:
        _, estado_rota = _json_rota(base, "/api/state")
        multi = estado_rota.get("multi_ia")
        c.ok("[§4] /api/state publica `multi_ia` (estado do orquestrador)",
             isinstance(multi, dict)
             and {ia.get("nome") for ia in (multi.get("ias") or [])} >= {"voo", "seguimento"},
             f"fonte={(multi or {}).get('v_ref_fonte')}")
        rpi5 = estado_rota.get("rpi5") or {}
        custo = rpi5.get("multi_ia")
        c.ok("[§4] /api/state publica o custo multi-IA no painel RPi 5 (com semáforo)",
             isinstance(custo, dict)
             and custo.get("semaforo") in ("OK", "ATENCAO", "ERRO", "sem dados")
             and custo.get("periodo_us") == 20000.0,
             f"semaforo={(custo or {}).get('semaforo')} · p99={(custo or {}).get('p99_us')} µs")
        c.ok("[§4] o FC vem marcado como NÃO-IA no painel (a estabilidade não é das redes)",
             ((custo or {}).get("fc") or {}).get("ia") is False)
        _, sim = _json_rota(base, "/api/sim")
        linhas_sim = sim.get("linhas") or []
        c.ok("[§4] as linhas do /api/sim levam `multi_ia` (a fronteira site↔API)",
             any(isinstance(linha.get("multi_ia"), dict) for linha in linhas_sim),
             f"{sum(1 for linha in linhas_sim if isinstance(linha.get('multi_ia'), dict))}"
             f"/{len(linhas_sim)} linhas")
    finally:
        os.killpg(os.getpgid(servidor.pid), 15)
        servidor.communicate(timeout=15)


# ============================================================ §5 FIXES da revisão crítica (2026-10-12)
def secao_fixes_revisao(c: Checagens) -> None:
    from env_seguimento import OBS_DIM, VOO_SUBIDA, VOO_VEL, EnvSeguimento
    from multi_ia import ESCALA_ACAO_R11, SUCESSOS_REENGATE, ObservacaoSeguimento

    # FIX 1 — a obs da IA-2 é a do BUILDER DO TREINO (max|Δ| = 0 para o MESMO estado)
    seg_env = EnvSeguimento(piloto_zip=str(MODELO_VOO), episodio_s=4.0)
    _obs_env, _info = seg_env.reset(seed=3)
    seg_env._v_ref = np.array([0.3, -0.2, 0.1])              # um estado NÃO trivial
    mecanismo = ObservacaoSeguimento(seg_env.env)
    mecanismo._v_ref = seg_env._v_ref.copy()                 # o MESMO estado
    vis = EnvSeguimento._ver_projecao(seg_env)
    obs_treino = EnvSeguimento._observacao(seg_env, vis)
    obs_mec = mecanismo()
    c.ok("[§5] FIX 1: a obs da IA-2 é a do BUILDER DO TREINO (max|Δ| = 0, 17 canais)",
         obs_mec.shape == (OBS_DIM,) == obs_treino.shape
         and float(np.max(np.abs(obs_mec - obs_treino))) == 0.0,
         f"max|Δ| = {float(np.max(np.abs(obs_mec - obs_treino))):.3e} · dim={obs_mec.shape}")
    c.ok("[§5] FIX 1: o canal v_ref(3) da obs é a AÇÃO CRUA (dividida pela escala = ação)",
         bool(np.allclose(obs_mec[4:7], seg_env._v_ref / [VOO_VEL, VOO_VEL, VOO_SUBIDA])),
         f"canal = {obs_mec[4:7].tolist()}")

    # FIX 2 — escala da ação: ação [0.4, −0.4, 0.2] → v_ref = (0.4, −0.4, 0.14) m/s
    v_ref = mecanismo.definir_acao(np.array([0.4, -0.4, 0.2]))
    c.ok("[§5] FIX 2: ação→v_ref com a escala do TREINO — z = 0,2·0,7 = 0,14 m/s",
         bool(np.allclose(v_ref, [0.4, -0.4, 0.14], atol=1e-9)),
         f"v_ref = {v_ref.tolist()} (esperado [0.4, -0.4, 0.14])")

    # FIX 4 — envelope r11: ação fora de [-1,1] limita a ±1,0 xy / ±0,7 z (o clip ±2 era violável)
    v_max = mecanismo.definir_acao(np.array([2.0, -2.0, 2.0]))
    c.ok("[§5] FIX 4: ação [2,−2,2] → v_ref (1,−1,0,7) — envelope CONTRATO ±1,0/±0,7",
         bool(np.allclose(v_max, [1.0, -1.0, 0.7])), f"v_ref = {v_max.tolist()}")
    c.ok("[§5] FIX 4: a escala do treino é (1, 1, 0,7) (o z do envelope r11)",
         tuple(ESCALA_ACAO_R11) == (1.0, 1.0, 0.7))

    # FIX 3 — NaN nunca se propaga: conta falha e o v_ref fica limpo (fallback WASDQE)
    def tracker_nan(obs):
        return np.array([np.nan, 0.1, -0.1])

    cascata_nan = CascataMultiIA(
        ia_voo=IA(nome="voo", papel="p", taxa_hz=50.0, politica=lambda obs: np.zeros(4)),
        ia_seguimento=IA(nome="seguimento", papel="p", taxa_hz=25.0, politica=tracker_nan,
                         obs_de=lambda: np.zeros(17, np.float32),
                         escala_acao=ESCALA_ACAO_R11))
    for k in range(10):
        cascata_nan.passo(0.02 * k, np.zeros(48, dtype=np.float32))
    est_nan = cascata_nan.estado()
    v_ref_nan = cascata_nan._v_ref_tracker
    c.ok("[§5] FIX 3: ação NaN → o v_ref NUNCA contém NaN (a cascata descarta-o)",
         v_ref_nan is None or bool(np.all(np.isfinite(v_ref_nan))),
         f"v_ref_tracker = {None if v_ref_nan is None else v_ref_nan.tolist()}")
    c.ok("[§5] FIX 3: a não-finitude CONTA como falha da IA (e a fonte fica no WASDQE)",
         est_nan["ias"][1]["n_falhas_total"] >= 1 and est_nan["v_ref_fonte"] == "wasdqe",
         f"falhas_total={est_nan['ias'][1]['n_falhas_total']} · fonte={est_nan['v_ref_fonte']}")

    # FIX 5 — falhas CONSECUTIVAS: intercaladas nunca escalam para `erro`; 3 seguidas sim
    chamadas = {"n": 0}
    def tracker_intercalado(obs):
        chamadas["n"] += 1
        if chamadas["n"] % 2 == 1:
            raise RuntimeError("falha intercalada")
        return np.array([0.1, 0.0, 0.0])

    ia_i = IA(nome="seguimento", papel="p", taxa_hz=25.0, politica=tracker_intercalado,
              obs_de=lambda: np.zeros(17, np.float32), escala_acao=ESCALA_ACAO_R11)
    cascata_i = CascataMultiIA(ia_voo=IA(nome="voo", papel="p", taxa_hz=50.0,
                                         politica=lambda obs: np.zeros(4)), ia_seguimento=ia_i)
    for k in range(8):
        cascata_i.passo(0.04 * k, np.zeros(48, dtype=np.float32))   # 8 execuções do tracker
    c.ok("[§5] FIX 5: 4 falhas INTERCALADAS nunca chegam a `erro` (a contagem é de consecutivas)",
         ia_i.estado != "erro" and ia_i.falhas <= 1,
         f"estado={ia_i.estado} · consecutivas={ia_i.falhas} · total={ia_i.n_falhas_total}")
    for _ in range(3):
        ia_i.falha("seguida")
    c.ok("[§5] FIX 5: 3 falhas CONSECUTIVAS → `erro` (o fail-safe da literatura)",
         ia_i.estado == "erro", f"estado={ia_i.estado}")

    # FIX 6 — histerese: o tracker só REENGATA depois de SUCESSOS_REENGATE sucessos seguidos
    chamadas = {"n": 0}
    def tracker_reengate(obs):
        chamadas["n"] += 1
        return np.array([0.5, 0.0, 0.0])

    ia_h = IA(nome="seguimento", papel="p", taxa_hz=25.0, politica=tracker_reengate,
              obs_de=lambda: np.zeros(17, np.float32),
              conversor_acao=lambda a: np.asarray(a, float) * np.array([1.0, 1.0, 0.7]))
    cascata_h = CascataMultiIA(ia_voo=IA(nome="voo", papel="p", taxa_hz=50.0,
                                         politica=lambda obs: np.zeros(4)), ia_seguimento=ia_h)
    fontes = []
    for k in range(8):                        # 8 execuções do tracker (uma por passo a 25 Hz/40 ms)
        cascata_h.passo(0.04 * k, np.zeros(48, dtype=np.float32))
        fontes.append(cascata_h.estado()["v_ref_fonte"])
    c.ok("[§5] FIX 6: histerese — o tracker só reengata após SUCESSOS_REENGATE sucessos seguidos",
         fontes[:SUCESSOS_REENGATE - 1] == ["wasdqe"] * (SUCESSOS_REENGATE - 1)
         and all(f == "seguimento" for f in fontes[SUCESSOS_REENGATE - 1:]),
         f"fontes = {fontes} (SUCESSOS_REENGATE = {SUCESSOS_REENGATE})")


def main() -> int:
    if not MODELO_VOO.is_file():
        print(f"[teste] falta a política da IA-1: {MODELO_VOO}", flush=True)
        return 1
    c = Checagens("multi_ia")
    secao_cascata(c)
    secao_watchdog(c)
    secao_fixes_revisao(c)
    secao_runner_servidor(c)
    print(f"\n[teste] {len(c.linhas) - len(c.falhas)}/{len(c.linhas)} checagens OK", flush=True)
    if c.falhas:
        for nome in c.falhas:
            print(f"[teste] FALHOU: {nome}", flush=True)
        return 1
    print("[teste] o mecanismo multi-IA de bordo cumpre o contrato: cascata = IA-1 sozinha sem "
          "tracker (e MUDA com ele), watchdog (WASDQE nunca falta; ação neutra + FC mantém quando a "
          "IA-1 cai), contas p50/p99 por IA e a telemetria/rotas publicam `multi_ia`", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())