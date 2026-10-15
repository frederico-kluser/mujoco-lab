#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/treinar_bola.py — o «TREINO» SEM INTERFACE do modo «seguir a bola»: afina os ganhos da lei IBVS do
firmware (`firmware/nucleo/ibvs.hpp`, versão 2) por otimização SEM GRADIENTE, em paralelo, no simulador completo.

O que a medição decidiu (`avaliar_bola.py` → `out/bola/avaliacao.json`): a lei clássica em C++ ganha ao tracker PPO por uma ordem de
grandeza; o que há para «treinar» são os GANHOS dela. Aqui cada candidato é um vetor de ganhos; voa-se o MESMO protocolo do `avaliar_bola.py` (planta MuJoCo +
núcleo C++ + bola aleatória) e minimiza-se o custo `avaliar_bola.custo` (centragem na imagem em graus + distância + perdas).

    ganhos (ibvs_ganhos.hpp) ──▶ sep-CMA-ES (λ candidatos/geração) ──▶ episódios em paralelo (câmara em modo PROJEÇÃO: sem GPU)
          ▲                                                                   │ custo médio por candidato
          └────────── --promover: reescreve o cabeçalho VERSIONADO ◀── validação nas 12 sementes de AFINAÇÃO ◀──┘

REGRAS DE HONESTIDADE
  · sementes de AFINAÇÃO 8100…8111 (`avaliar_bola.SEMENTES_AFINACAO`), DISJUNTAS das de avaliação 6200…6211 — o script recusa-se a
    correr se se cruzarem; a tabela antes × depois sai do `avaliar_bola.py`, noutras sementes e com a câmara RENDERIZADA;
  · em cada geração TODOS os candidatos voam as MESMAS sementes (comparação pareada); as sementes rodam de geração em geração
    para o ótimo não decorar duas bolas;
  · o resultado só é PROMOVIDO se, na validação com as 12 sementes de afinação × 3 velocidades × 2 latências, o custo médio
    baixar face ao ponto de partida (senão fica tudo como estava e diz-se);
  · os ganhos promovidos ficam em `firmware/nucleo/ibvs_ganhos.hpp` (versionado) — nunca só em `out/`.

Otimizador: sep-CMA-ES — a CMA-ES com covariância DIAGONAL (Ros & Hansen, «A Simple Modification in CMA-ES Achieving Linear Time
and Space Complexity», PPSN X, 2008; Hansen, «The CMA Evolution Strategy: A Tutorial», 2016) — reimplementada aqui (≈ 40 linhas);
espaço de busca normalizado a [0, 1] por parâmetro (os ruídos de processo em escala logarítmica), com corte aos limites.

    .venv/bin/python experiments/09_drone_hover_rl/treinar_bola.py --geracoes 12            # treina → out/bola/afinacao.json
    .venv/bin/python experiments/09_drone_hover_rl/treinar_bola.py --promover               # afinacao.json → ibvs_ganhos.hpp
    .venv/bin/python experiments/09_drone_hover_rl/treinar_bola.py --rapido                 # fumo: 2 gerações de 4 candidatos
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

import avaliar_bola as ab
import numpy as np

CABECALHO = _AQUI / "firmware" / "nucleo" / "ibvs_ganhos.hpp"
SAIDA_JSON = _AQUI / "out" / "bola" / "afinacao.json"
REGISTO = _AQUI / "out" / "bola" / "treino_log.jsonl"

# (campo de ConfigSeguidor, constante C++, mínimo, máximo, escala, afinar?, comentário do cabeçalho)
PARAMETROS = (
    ("sigma_px", "kSigmaPx", 0.15, 1.5, "log", True, "px — σ da medida de u, v no filtro do alvo"),
    ("q_ang", "kQAng", 1e-3, 1e-1, "log", True, "rad²·s⁻⁵ — PSD do jerk dos ângulos (KF-CA)"),
    ("q_raio", "kQRaioCv", 2e-7, 2e-5, "log", False, "s⁻³ — PSD da aceleração do raio normalizado (canal do raio em CV)"),
    ("kp_z", "kKpZ", 0.5, 3.5, "lin", True, "1/s — P do desvio vertical"),
    ("kff_z", "kKffZ", 0.0, 1.2, "lin", True, "feedforward da velocidade vertical do alvo"),
    ("acel_z_max", "kAcelZMax", 0.5, 3.0, "lin", False, "m/s² — slew de v_z"),
    ("kp_d", "kKpD", 0.2, 1.5, "lin", True, "1/s — P da distância"),
    ("kff_d", "kKffD", 0.0, 1.0, "lin", True, "feedforward da velocidade radial do alvo"),
    ("acel_x_max", "kAcelXMax", 0.2, 2.0, "lin", True, "m/s² — slew de v_x"),
    ("zona_morta_d", "kZonaMortaD", 0.0, 0.3, "lin", False, "m — zona morta da distância"),
    ("kp_y", "kKpY", 0.3, 3.0, "lin", True, "1/s — P do desvio lateral"),
    ("kff_y", "kKffY", 0.0, 1.0, "lin", True,
     "fração da velocidade tangencial do alvo que a translação lateral leva (o resto: guinada)"),
    ("acel_y_max", "kAcelYMax", 0.5, 4.0, "lin", True, "m/s² — slew de v_y"),
    ("k_incl_z", "kInclZ", 0.0, 1.0, "lin", False, "[0,1] — canal vertical na IMAGEM (compensa a inclinação do corpo)"),
    ("tau_incl_s", "kTauIncl", 0.0, 0.5, "lin", False, "s — PT1 da parcela de inclinação"),
)
CAMPOS = tuple(p[0] for p in PARAMETROS)
AFINADOS = tuple(p[0] for p in PARAMETROS if p[5])
VELOCIDADES_TREINO = (0.5, 0.8)        # as difíceis; a validação final usa as três do protocolo
T_MEDIDA_TREINO_S = 20.0               # janela de medida de cada episódio de treino (a avaliação usa 30 s)


# ------------------------------------------------------------------------------------------------ o cabeçalho versionado
def ler_ganhos(caminho: Path = CABECALHO) -> dict[str, float]:
    """Os ganhos em vigor: as constantes `constexpr float k… = …f;` do `ibvs_ganhos.hpp`, por campo de `ConfigSeguidor`."""
    texto = Path(caminho).read_text(encoding="utf-8")
    achados = dict(re.findall(r"constexpr\s+float\s+(k\w+)\s*=\s*([-+0-9.eE]+)f\s*;", texto))
    falta = [const for _c, const, *_ in PARAMETROS if const not in achados]
    if falta:
        raise ValueError(f"{caminho}: faltam as constantes {falta}")
    return {campo: float(achados[const]) for campo, const, *_ in PARAMETROS}


def _lit(v: float) -> str:
    s = f"{float(np.float32(v)):.6g}"
    return (s if any(c in s for c in ".eE") else s + ".0") + "f"


def gerar_cabecalho(valores: dict[str, float], proveniencia: str) -> str:
    """O texto do `ibvs_ganhos.hpp` com `valores` (todos os campos de PARAMETROS) e a linha de proveniência."""
    linhas = []
    for campo, const, lo, hi, _esc, _af, coment in PARAMETROS:
        v = float(valores[campo])
        if not (math.isfinite(v) and lo - 1e-12 <= v <= hi + 1e-12):
            raise ValueError(f"{campo} = {v!r} fora de [{lo}, {hi}]")
        decl = f"constexpr float {const} = {_lit(v)};"
        linhas.append(f"{decl:<38} // {coment}")
    corpo = "\n".join(linhas)
    return (
        "// firmware/nucleo/ibvs_ganhos.hpp — os GANHOS AFINADOS da lei «seguir a bola» (ibvs.hpp, versão 2). C++ float32.\n"
        "//\n"
        "// GERADO por experiments/09_drone_hover_rl/treinar_bola.py --promover — NÃO EDITAR À MÃO (regenerar com o treino).\n"
        "// É a única fonte dos números que `visao::config_padrao` põe na lei por omissão (a que o runner da interface usa);\n"
        "// os limites de guinada/velocidade continuam a vir da planta (sitl.config_de_hardware) e não daqui.\n"
        "//\n"
        f"// proveniência: {proveniencia}\n"
        "#pragma once\n\nnamespace nucleo {\nnamespace visao {\nnamespace ganhos {\n\n"
        f"{corpo}\n\n"
        "}  // namespace ganhos\n}  // namespace visao\n}  // namespace nucleo\n")


# ------------------------------------------------------------------------------------------------ espaço de busca
def para_unitario(valores: dict[str, float]) -> np.ndarray:
    z = []
    for campo, _c, lo, hi, esc, afinar, _k in PARAMETROS:
        if afinar:
            v = float(valores[campo])
            z.append((math.log(v / lo) / math.log(hi / lo)) if esc == "log" else (v - lo) / (hi - lo))
    return np.clip(np.array(z), 0.0, 1.0)


def de_unitario(z: np.ndarray, base: dict[str, float]) -> dict[str, float]:
    """Vetor em [0,1]ⁿ (só os parâmetros AFINADOS) → dict completo de ganhos (os fixos vêm de `base`)."""
    out = dict(base)
    i = 0
    for campo, _c, lo, hi, esc, afinar, _k in PARAMETROS:
        if afinar:
            u = float(min(max(z[i], 0.0), 1.0))
            out[campo] = lo * (hi / lo) ** u if esc == "log" else lo + u * (hi - lo)
            i += 1
    return out


class SepCMAES:
    """sep-CMA-ES (covariância diagonal) a MINIMIZAR em [0,1]ⁿ — Ros & Hansen 2008; constantes de Hansen 2016, tabela 1, com as
    taxas de aprendizagem da covariância multiplicadas por (n + 2)/3 (a diagonal aprende-se mais depressa que a matriz cheia)."""

    def __init__(self, x0: np.ndarray, sigma0: float, lam: int, rng: np.random.Generator):
        n = len(x0)
        self.n, self.lam, self.rng = n, int(lam), rng
        self.mu = self.lam // 2
        w = math.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.w = w / w.sum()
        self.mu_ef = 1.0 / float(np.sum(self.w ** 2))
        self.c_sigma = (self.mu_ef + 2.0) / (n + self.mu_ef + 5.0)
        self.d_sigma = 1.0 + 2.0 * max(0.0, math.sqrt((self.mu_ef - 1.0) / (n + 1.0)) - 1.0) + self.c_sigma
        self.c_c = (4.0 + self.mu_ef / n) / (n + 4.0 + 2.0 * self.mu_ef / n)
        acel = (n + 2.0) / 3.0
        self.c_1 = min(1.0, acel * 2.0 / ((n + 1.3) ** 2 + self.mu_ef))
        self.c_mu = min(1.0 - self.c_1, acel * 2.0 * (self.mu_ef - 2.0 + 1.0 / self.mu_ef) / ((n + 2.0) ** 2 + self.mu_ef))
        self.chi_n = math.sqrt(n) * (1.0 - 1.0 / (4.0 * n) + 1.0 / (21.0 * n * n))
        self.m = np.array(x0, dtype=float)
        self.sigma = float(sigma0)
        self.c = np.ones(n)                      # diagonal da covariância
        self.p_sigma, self.p_c = np.zeros(n), np.zeros(n)
        self.geracao = 0

    def pedir(self) -> np.ndarray:
        """λ candidatos (cortados a [0,1]): x_i = m + σ·√C·N(0, I)."""
        self._y = self.rng.standard_normal((self.lam, self.n)) * np.sqrt(self.c)
        return np.clip(self.m + self.sigma * self._y, 0.0, 1.0)

    def dizer(self, x: np.ndarray, custos: np.ndarray) -> None:
        """Atualiza média, passo e covariância com os custos dos candidatos `x` (os de `pedir`, já cortados)."""
        ordem = np.argsort(custos)[: self.mu]
        y = (x[ordem] - self.m) / self.sigma     # passos EFETIVOS (depois do corte aos limites)
        y_w = self.w @ y
        self.m = self.m + self.sigma * y_w
        self.p_sigma = (1.0 - self.c_sigma) * self.p_sigma + math.sqrt(self.c_sigma * (2.0 - self.c_sigma) * self.mu_ef) * y_w / np.sqrt(self.c)
        self.geracao += 1
        norma = float(np.linalg.norm(self.p_sigma))
        h = norma / math.sqrt(1.0 - (1.0 - self.c_sigma) ** (2 * self.geracao)) < (1.4 + 2.0 / (self.n + 1.0)) * self.chi_n
        self.p_c = (1.0 - self.c_c) * self.p_c + (math.sqrt(self.c_c * (2.0 - self.c_c) * self.mu_ef) * y_w if h else 0.0)
        self.c = ((1.0 - self.c_1 - self.c_mu) * self.c + self.c_1 * (self.p_c ** 2 + (0.0 if h else self.c_c * (2.0 - self.c_c)) * self.c)
                  + self.c_mu * (self.w @ (y ** 2)))
        self.sigma = float(np.clip(self.sigma * math.exp((self.c_sigma / self.d_sigma) * (norma / self.chi_n - 1.0)), 1e-3, 0.5))


# ------------------------------------------------------------------------------------------------ custo de um conjunto de ganhos
def episodios(ganhos: dict[str, float], sementes, velocidades, rotulo: str, t_medida: float, camera_modo: str) -> list[dict]:
    """Os episódios (jobs do `avaliar_bola`) de UM candidato: 2 caminhos × velocidades × sementes, com os ganhos sobrepostos."""
    proibidas = set(sementes) & set(ab.SEMENTES_AVALIACAO)
    if proibidas:
        raise ValueError(f"sementes de AVALIAÇÃO não entram na afinação: {sorted(proibidas)}")
    return ab.jobs_variante(rotulo, sementes, velocidades, seguidor={k: float(ganhos[k]) for k in CAMPOS},
                            t_medida=t_medida, camera_modo=camera_modo)


def custos_por_rotulo(jobs: list[dict], res: list[dict]) -> dict[str, float]:
    soma: dict[str, list[float]] = {}
    for j, r in zip(jobs, res, strict=True):
        soma.setdefault(j["variante"], []).append(float(r["custo"]))
    return {k: float(np.mean(v)) for k, v in soma.items()}


def resumo(jobs: list[dict], res: list[dict], rotulo: str) -> dict:
    """Médias de um rótulo (todas as condições juntas) nas métricas que interessam + nº de quedas."""
    rs = [r for j, r in zip(jobs, res, strict=True) if j["variante"] == rotulo]
    vivos = [r for r in rs if not r.get("terminou")]
    out = {"custo": float(np.mean([r["custo"] for r in rs])), "quedas": len(rs) - len(vivos), "n": len(rs)}
    for c in ("centro_rms_graus", "centro_p95_graus", "h_rms_graus", "v_rms_graus", "dist_erro_rms", "frac_fov", "frac_a_seguir",
              "roll_rms_graus", "pitch_rms_graus"):
        out[c] = float(np.mean([r[c] for r in vivos])) if vivos else float("nan")
    return out


def validar(pool, partida: dict, final: dict, camera_modo: str, sementes=ab.SEMENTES_AFINACAO,
            t_medida: float = ab.T_MEDIDA_S) -> dict:
    """Ponto de partida × resultado nas sementes de AFINAÇÃO todas, 3 velocidades, 2 latências (pareado por episódio)."""
    jobs = (episodios(partida, sementes, ab.VELOCIDADES, "partida", t_medida, camera_modo)
            + episodios(final, sementes, ab.VELOCIDADES, "final", t_medida, camera_modo))
    res = list(pool.map(ab.tarefa, jobs, chunksize=1))
    a = np.array([r["custo"] for j, r in zip(jobs, res, strict=True) if j["variante"] == "partida"])
    b = np.array([r["custo"] for j, r in zip(jobs, res, strict=True) if j["variante"] == "final"])
    d = b - a
    return {"partida": resumo(jobs, res, "partida"), "final": resumo(jobs, res, "final"), "n_pares": len(d),
            "delta_custo_medio": float(d.mean()), "delta_custo_erro_padrao": float(d.std(ddof=1) / math.sqrt(len(d))),
            "frac_episodios_melhores": float(np.mean(d < 0.0)), "sementes": list(sementes), "camera": camera_modo}


# ------------------------------------------------------------------------------------------------ treino
def treinar(args) -> int:
    import sitl
    sitl.biblioteca_padrao()                               # compila a .so UMA vez, antes de criar os processos
    partida = ler_ganhos()
    rng = np.random.default_rng(args.semente)
    es = SepCMAES(para_unitario(partida), args.sigma, args.candidatos, rng)
    sementes_treino = [s for s in ab.SEMENTES_AFINACAO if s not in ab.SEMENTES_AVALIACAO]
    REGISTO.parent.mkdir(parents=True, exist_ok=True)
    REGISTO.write_text("", encoding="utf-8")
    t0 = time.perf_counter()
    print(f"TREINO «seguir a bola»: sep-CMA-ES · {len(AFINADOS)} ganhos {AFINADOS} · λ = {args.candidatos} · até {args.geracoes} "
          f"gerações / {args.orcamento_min:g} min · {args.sementes_por_geracao} sementes × {len(VELOCIDADES_TREINO)} velocidades × "
          f"{len(ab.CAMINHOS)} latências por candidato · câmara «{args.camera}» · {args.jobs} processos", flush=True)
    historia = []
    with ProcessPoolExecutor(max_workers=args.jobs, initializer=ab._init_worker) as pool:
        for g in range(args.geracoes):
            if (time.perf_counter() - t0) / 60.0 > args.orcamento_min:
                print(f"  orçamento de {args.orcamento_min:g} min esgotado na geração {g}", flush=True)
                break
            k = args.sementes_por_geracao
            sementes = [sementes_treino[(g * k + i) % len(sementes_treino)] for i in range(k)]
            x = es.pedir()
            cands = [de_unitario(xi, partida) for xi in x] + [de_unitario(es.m, partida)]      # o último = a MÉDIA atual
            jobs = [j for i, c in enumerate(cands)
                    for j in episodios(c, sementes, VELOCIDADES_TREINO, f"c{i}", args.t_medida, args.camera)]
            res = list(pool.map(ab.tarefa, jobs, chunksize=1))
            por = custos_por_rotulo(jobs, res)
            custos = np.array([por[f"c{i}"] for i in range(len(x))])
            custo_media = por[f"c{len(x)}"]
            es.dizer(x, custos)
            linha = {"geracao": g, "sementes": sementes, "custo_media": custo_media, "custo_melhor": float(custos.min()),
                     "custo_mediana": float(np.median(custos)), "sigma": es.sigma, "t_min": (time.perf_counter() - t0) / 60.0,
                     "media": de_unitario(es.m, partida)}
            historia.append(linha)
            with REGISTO.open("a", encoding="utf-8") as f:
                f.write(json.dumps(linha, ensure_ascii=False) + "\n")
            print(f"  [{linha['t_min']:5.1f} min] geração {g:2d} · sementes {sementes} · custo da média {custo_media:6.3f} · melhor "
                  f"{custos.min():6.3f} · mediana {np.median(custos):6.3f} · σ {es.sigma:.3f}", flush=True)
        final = de_unitario(es.m, partida)
        sem_val = sementes_treino[: args.sementes_validacao]
        print(f"  validação: ponto de partida × resultado em {len(sem_val)} sementes de afinação, 3 velocidades, 2 latências…", flush=True)
        val = validar(pool, partida, final, args.camera, sem_val, ab.T_MEDIDA_S if not args.rapido else args.t_medida)
    # só conta como melhoria uma descida do custo médio MAIOR que o seu erro-padrão (pareado), sem quedas
    melhorou = val["delta_custo_medio"] + val["delta_custo_erro_padrao"] < 0.0 and val["final"]["quedas"] == 0
    saida = {"gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "otimizador": "sep-CMA-ES (Ros & Hansen 2008)",
             "afinados": list(AFINADOS), "candidatos": args.candidatos, "geracoes_feitas": len(historia),
             "sementes_afinacao": list(sementes_treino), "velocidades_treino": list(VELOCIDADES_TREINO),
             "t_medida_treino_s": args.t_medida, "camera": args.camera, "custo": ab.custo.__doc__, "partida": partida,
             "final": final, "validacao": val, "melhorou": bool(melhorou), "historia": historia,
             "duracao_min": (time.perf_counter() - t0) / 60.0}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(ab.limpar(saida), ensure_ascii=False, indent=1), encoding="utf-8")
    p, f = val["partida"], val["final"]
    print(f"\nVALIDAÇÃO (sementes de afinação {sem_val[0]}..{sem_val[-1]}, {val['n_pares']} episódios pareados):\n"
          f"  partida: custo {p['custo']:.3f} · centragem RMS {p['centro_rms_graus']:.2f}° (H {p['h_rms_graus']:.2f} / V {p['v_rms_graus']:.2f}) · "
          f"|D−d*| {p['dist_erro_rms']:.3f} m · quedas {p['quedas']}\n"
          f"  final:   custo {f['custo']:.3f} · centragem RMS {f['centro_rms_graus']:.2f}° (H {f['h_rms_graus']:.2f} / V {f['v_rms_graus']:.2f}) · "
          f"|D−d*| {f['dist_erro_rms']:.3f} m · quedas {f['quedas']}\n"
          f"  Δcusto = {val['delta_custo_medio']:+.3f} ± {val['delta_custo_erro_padrao']:.3f} (erro-padrão) · melhor em "
          f"{100 * val['frac_episodios_melhores']:.0f} % dos episódios → {'MELHOROU: promover com --promover' if melhorou else 'NÃO melhorou: fica o ponto de partida'}")
    print(f"→ {args.json} ({saida['duracao_min']:.1f} min)")
    return 0


def promover(args) -> int:
    """`afinacao.json` → `ibvs_ganhos.hpp` (só se a validação melhorou, ou com `--forcar`)."""
    dados = json.loads(args.json.read_text(encoding="utf-8"))
    if not dados.get("melhorou") and not args.forcar:
        print(f"{args.json}: a validação NÃO melhorou face ao ponto de partida — nada promovido (use --forcar para o contrariar)")
        return 1
    v = dados["validacao"]
    prov = (f"treinar_bola.py {dados['gerado_em']} · {dados['otimizador']}, {dados['geracoes_feitas']} gerações × {dados['candidatos']} "
            f"candidatos · sementes de afinação {dados['sementes_afinacao'][0]}–{dados['sementes_afinacao'][-1]} · validação: custo "
            f"{v['partida']['custo']:.3f} → {v['final']['custo']:.3f}, centragem RMS {v['partida']['centro_rms_graus']:.2f}° → "
            f"{v['final']['centro_rms_graus']:.2f}°")
    CABECALHO.write_text(gerar_cabecalho(dados["final"], prov), encoding="utf-8")
    print(f"promovido: {CABECALHO}\n  {prov}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--geracoes", type=int, default=12)
    p.add_argument("--candidatos", type=int, default=12, help="λ: candidatos por geração")
    p.add_argument("--sementes-por-geracao", type=int, default=2)
    p.add_argument("--sementes-validacao", type=int, default=len(ab.SEMENTES_AFINACAO), help="quantas sementes de afinação na validação final")
    p.add_argument("--sigma", type=float, default=0.15, help="passo inicial no espaço normalizado [0,1]")
    p.add_argument("--orcamento-min", type=float, default=30.0, help="não começa gerações novas depois disto")
    p.add_argument("--t-medida", type=float, default=T_MEDIDA_TREINO_S)
    p.add_argument("--camera", choices=("projecao", "render"), default="projecao")
    p.add_argument("--semente", type=int, default=0, help="semente do OTIMIZADOR (não das bolas)")
    p.add_argument("--jobs", type=int, default=min(12, max(1, (os.cpu_count() or 2) - 2)))
    p.add_argument("--json", type=Path, default=SAIDA_JSON)
    p.add_argument("--rapido", action="store_true", help="fumo: 2 gerações × 4 candidatos, 1 semente, janela de 8 s")
    p.add_argument("--promover", action="store_true", help="grava os ganhos do --json no ibvs_ganhos.hpp (versionado)")
    p.add_argument("--forcar", action="store_true", help="promove mesmo que a validação não tenha melhorado")
    args = p.parse_args(argv)
    if args.promover:
        return promover(args)
    if args.rapido:
        args.geracoes, args.candidatos, args.sementes_por_geracao, args.t_medida, args.sementes_validacao = 2, 4, 1, 8.0, 1
    return treinar(args)


if __name__ == "__main__":
    sys.exit(main())
