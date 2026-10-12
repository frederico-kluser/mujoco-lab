#!/usr/bin/env python3
"""deploy.py — deploy da política: ONNX → validação numérica → benchmark proxy RPi → multi-IA.

Pipeline (tudo em CPU, sem janela nenhuma):

  1. EXPORT — carrega o `.zip` (PPO) e exporta o GRAFO da política para ONNX com o exporter legacy
     (`torch.onnx.export(..., dynamo=False)`), entrada ESTÁTICA `(1, N_OBS)` float32, opset 17, sem
     `dynamic_axes` (lote 1). Confere com `onnx.checker` e corre com `onnxruntime` (CPU EP).
  2. VALIDAÇÃO NUMÉRICA — compara o grafo com o PyTorch sobre observações REAIS do `env.py` (≥`--n-val`).
     Compara-se a AÇÃO DETERMINÍSTICA (a média da gaussiana, que é o que o grafo devolve), não uma amostra.
     Saídas NÃO FINITAS reprovam explicitamente (o ONNX Runtime devolve `NaN` em silêncio e um `max|Δ|`
     ingénuo passaria por bom). Reprovada a validação ⇒ veredicto negativo e exit code 1.
  3. BENCHMARK PROXY RPi — sessão ORT com `intra_op_num_threads=1` (proxy do core do A76) e buffer
     pré-alocado: p50/p99/max µs por chamada e resposta a "cabe a 50 Hz?" (20 000 µs) e "100 Hz?" (10 000 µs).
     ATENÇÃO: é um PROXY neste PC — os números NÃO são os do Raspberry Pi.
  4. INT8 (`--int8`) — `quantize_dynamic` (QInt8) → re-validação e re-benchmark (a razão medida, sem adjetivo).
  5. MULTI-IA (`--nproc N`) — N PROCESSOS (`spawn`), cada um com a SUA sessão e (com `--pinned`) afinidade ao
     seu core; cada um corre a 50 Hz durante `--duracao` s e mede o p50/p99 REAL por iteração (sem o sleep).
     O pai agrega: tabela por processo, inferências/s e iterações que estouraram os 20 ms.
  6. RELATÓRIO — tabela final + `out/deploy_report.json` (versões, tempos, veredicto, sha256 do modelo).

    uv run --group hover-rl python <exp>/deploy.py --skip-multi          # smoke rápido (export + validação + bench)
    uv run --group hover-rl python <exp>/deploy.py --nproc 4 --duracao 5 # multi-IA a sério
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import statistics
import sys
import time
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

from lab import mjkit  # noqa: F401, I001  (fixa MUJOCO_GL=egl ANTES de `import mujoco`; é efeito de importação)

import numpy as np

import env as env_mod
import train as train_mod

RUNS = _AQUI / "out" / "runs"
PERIODO_50HZ_US = 20_000.0


def _finitas(*arrays) -> bool:
    return all(np.all(np.isfinite(np.asarray(a, dtype=float))) for a in arrays)


def percentis(amostras_us: list[float]) -> dict:
    """p50/p99/max (µs) de uma amostra de tempos (sem numpy: listas pequenas e legíveis)."""
    if not amostras_us:
        return {"p50": None, "p99": None, "max": None, "n": 0}
    ordenados = sorted(amostras_us)
    return {"p50": round(statistics.median(ordenados), 1),
            "p99": round(ordenados[min(len(ordenados) - 1, int(0.99 * len(ordenados)))], 1),
            "max": round(ordenados[-1], 1), "n": len(ordenados)}


def cabe(p: dict) -> str:
    """Veredicto honesto do benchmark: cabe a 50 Hz / 100 Hz com o p99 (não com a média)."""
    if p["p99"] is None:
        return "sem dados"
    if p["p99"] <= PERIODO_50HZ_US / 2:
        return f"cabe a 100 Hz (p99 {p['p99']:.0f} µs ≤ 10 000 µs)"
    if p["p99"] <= PERIODO_50HZ_US:
        return f"cabe a 50 Hz (p99 {p['p99']:.0f} µs ≤ 20 000 µs)"
    return f"NÃO cabe a 50 Hz (p99 {p['p99']:.0f} µs > 20 000 µs)"


def observacoes_reais(n: int, seed: int = 0) -> np.ndarray:
    """`n` observações REAIS do ambiente (reset + passos com ações pseudo-aleatórias) — nada de ruído inventado."""
    env = env_mod.novo_env(seed=seed)
    rng = np.random.default_rng(seed)
    obs, _ = env.reset(seed=seed)
    saida = []
    while len(saida) < n:
        saida.append(np.asarray(obs, dtype=np.float32).reshape(-1))
        obs, _r, terminado, truncado, _info = env.step(rng.uniform(-1.0, 1.0, size=env_mod.N_ACT))
        if terminado or truncado:
            obs, _ = env.reset(seed=seed + len(saida))
    return np.stack(saida[:n])


def carregar_politica(caminho: Path):
    from stable_baselines3 import PPO

    return PPO.load(caminho, device="cpu")


def acao_torch(politica, obs: np.ndarray) -> np.ndarray:
    """Ação DETERMINÍSTICA do PyTorch (a média da gaussiana) — é o que o grafo ONNX devolve."""
    import torch

    tensor = torch.as_tensor(np.asarray(obs, dtype=np.float32))
    with torch.no_grad():
        return np.asarray(politica.policy._predict(tensor, deterministic=True), dtype=np.float32)


def exportar_onnx(politica, caminho: Path) -> dict:
    """Exporta o grafo da política (entrada estática (1, N_OBS), opset 17) e confere-o com `onnx.checker`."""
    import onnx
    import torch

    exemplo = torch.zeros((1, env_mod.N_OBS), dtype=torch.float32)

    class Envolvido(torch.nn.Module):
        """Caminho LIMPO e traçável até à média da gaussiana: `extract_features → mlp_extractor → action_net`.

        Não se chama `policy._predict(...)` no `forward`: ele passa por `get_distribution(...).get_actions(...)`,
        que o tracer do TorchScript não consegue exportar (o `export` rebenta com um dump de tensores). O
        resultado é IDÊNTICO — verificado nesta máquina: `action_net(forward_actor(extract_features(x)))` ==
        `_predict(x, deterministic=True)` (Δ = 0). A validação numérica compara os DOIS caminhos, por isso uma
        divergência futura é apanhada e não passa em silêncio. Sem `Clip`: quem corta é o env (`acao_para_ctrl`).
        """

        def __init__(self, politica) -> None:
            super().__init__()
            # ⚠ A política TEM de ser um SUBMÓDULO (`self.politica = politica`, com `politica` um `nn.Module`):
            # se os parâmetros ficarem "de fora" do módulo traçado, o exporter legacy tenta-os inserir como
            # CONSTANTES e rebenta com "Cannot insert a Tensor that requires grad as a constant".
            self.politica = politica

        def forward(self, x):
            caracteristicas = self.politica.extract_features(x)
            latente = self.politica.mlp_extractor.forward_actor(caracteristicas)
            return self.politica.action_net(latente)

    caminho.parent.mkdir(parents=True, exist_ok=True)
    # Armadilha do exporter legacy: com o módulo em modo de treino os parâmetros `requires_grad` são tentados
    # inserir como CONSTANTES no grafo → "Cannot insert a Tensor that requires grad as a constant". A cura é
    # pôr a política em modo de avaliação e exportar dentro de `torch.no_grad()`.
    politica.policy.set_training_mode(False)
    with torch.no_grad():
        torch.onnx.export(Envolvido(politica.policy).eval(), exemplo, str(caminho), opset_version=17,
                          do_constant_folding=True,
                          input_names=["obs"], output_names=["acao"], dynamo=False)
    modelo = onnx.load(str(caminho))
    onnx.checker.check_model(modelo)
    return {"caminho": str(caminho), "bytes": caminho.stat().st_size,
            "sha256": hashlib.sha256(caminho.read_bytes()).hexdigest()[:16],
            "ops": sorted({n.op_type for n in modelo.graph.node}),
            "entrada": [d.dim_value for d in modelo.graph.input[0].type.tensor_type.shape.dim]}


def sessao(caminho: Path, threads: int = 1):
    import onnxruntime as ort

    opcoes = ort.SessionOptions()
    opcoes.intra_op_num_threads = int(threads)
    opcoes.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(str(caminho), sess_options=opcoes, providers=["CPUExecutionProvider"])


def validar(sess, politica, obs: np.ndarray) -> dict:
    """Compara ONNX × PyTorch sobre observações reais; reprova se houver NaN/inf de qualquer lado."""
    entrada = sess.get_inputs()[0].name
    deltas, fora_da_caixa, nan = [], 0, 0
    for o in obs:
        y_onnx = np.asarray(sess.run(None, {entrada: o.reshape(1, -1)})[0], dtype=float).reshape(-1)
        y_torch = acao_torch(politica, o.reshape(1, -1)).reshape(-1)
        if not _finitas(y_onnx, y_torch):
            nan += 1
            continue
        deltas.append(float(np.abs(y_onnx - y_torch).max()))
        fora_da_caixa += int(np.any(np.abs(y_onnx) > 1.0))
    max_delta = max(deltas) if deltas else float("nan")
    return {"n": len(obs), "max_delta": max_delta, "nan": nan, "fora_da_caixa_1": fora_da_caixa,
            "ok": bool(nan == 0 and deltas and max_delta < 1e-4),
            "nota": "o grafo devolve a média da gaussiana SEM Clip: quem corta é o env (`acao_para_ctrl`)"}


def benchmark(sess, obs_pool: np.ndarray, n: int, threads: int) -> dict:
    """≥`n` inferências com buffer pré-alocado (o sleep fica FORA): p50/p99/max µs por chamada."""
    entrada = sess.get_inputs()[0].name
    buffer = np.zeros((1, env_mod.N_OBS), dtype=np.float32)
    for i in range(50):                                        # aquecimento
        buffer[0] = obs_pool[i % len(obs_pool)]
        sess.run(None, {entrada: buffer})
    tempos = []
    for i in range(n):
        buffer[0] = obs_pool[i % len(obs_pool)]
        t0 = time.perf_counter()
        sess.run(None, {entrada: buffer})
        tempos.append((time.perf_counter() - t0) * 1e6)
    return percentis(tempos) | {"threads": int(threads)}


def _processo_multi(indice: int, caminho: str, threads: int, duracao: float, obs_pool: np.ndarray, core: int | None):
    """Um processo-IA: sessão PRÓPRIA, afinidade opcional, loop a 50 Hz a medir o custo por iteração (sem sleep)."""
    if core is not None:
        try:
            os.sched_setaffinity(0, {core})
        except (AttributeError, OSError):
            core = None
    sess = sessao(Path(caminho), threads)
    entrada = sess.get_inputs()[0].name
    buffer = np.zeros((1, env_mod.N_OBS), dtype=np.float32)
    tempos, estouros = [], 0
    t_fim = time.perf_counter() + duracao
    i = 0
    while time.perf_counter() < t_fim:
        t_inicio = time.perf_counter()
        buffer[0] = obs_pool[i % len(obs_pool)]
        sess.run(None, {entrada: buffer})
        dt = time.perf_counter() - t_inicio
        tempos.append(dt * 1e6)
        if dt > 0.020:
            estouros += 1
        i += 1
        restante = 0.020 - dt
        if restante > 0:
            time.sleep(restante)
    return {"processo": indice, "core_pedido": core, "iteracoes": i, "estouros_20ms": estouros,
            **percentis(tempos)}


def correr_multi(caminho: Path, n_proc: int, duracao: float, threads: int, obs_pool: np.ndarray) -> dict:
    """N processos (contexto `spawn`) com afinidade mapeada no PAI e passada ao filho."""
    nucleos = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    mapa = [nucleos[(i + 1) % len(nucleos)] for i in range(n_proc)] if len(nucleos) >= n_proc else [None] * n_proc
    ctx = mp.get_context("spawn")
    tarefas = [(i, str(caminho), threads, duracao, obs_pool, mapa[i]) for i in range(n_proc)]
    with ctx.Pool(n_proc) as pool:
        resultados = pool.starmap(_processo_multi, tarefas)
    total_iter = sum(r["iteracoes"] for r in resultados)
    return {"n_proc": n_proc, "duracao_s": duracao, "processos": resultados,
            "iteracoes_totais": total_iter, "inferencias_por_s": round(total_iter / duracao, 1),
            "estouros_20ms_totais": sum(r["estouros_20ms"] for r in resultados),
            "nucleos_do_sistema": nucleos[:n_proc], "mapa_pedido": mapa}


def quantizar_int8(fp32: Path, destino: Path) -> dict:
    """Quantização dinâmica QInt8 (só pesos) — o ganho real mede-se no benchmark seguinte, sem promessas."""
    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(str(fp32), str(destino), weight_type=QuantType.QInt8)
    return {"caminho": str(destino), "bytes": destino.stat().st_size,
            "razao_tamanho": round(fp32.stat().st_size / max(1, destino.stat().st_size), 3)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Deploy da política: ONNX + validação + benchmark proxy RPi + multi-IA.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Exit 0 = validação numérica passou; 1 = reprovou (o relatório diz porquê).")
    ap.add_argument("--model", type=Path, default=None, metavar="CAMINHO.zip", help="política PPO (padrão: a melhor de out/runs/)")
    ap.add_argument("--onnx", type=Path, default=None, metavar="CAMINHO", help="onde escrever o .onnx (padrão: junto do modelo)")
    ap.add_argument("--out", type=Path, default=None, metavar="CAMINHO", help="relatório JSON (padrão: out/deploy_report.json)")
    ap.add_argument("--n-val", type=int, default=200, help="observações reais da validação numérica (padrão 200)")
    ap.add_argument("--n-bench", type=int, default=3_000, help="inferências do benchmark (padrão 3 000)")
    ap.add_argument("--threads", type=int, default=1, help="threads do ORT no benchmark (>1 desfaz o proxy de 1 core)")
    ap.add_argument("--nproc", type=int, default=4, help="processos do multi-IA (padrão 4)")
    ap.add_argument("--duracao", type=float, default=3.0, help="segundos de cada processo do multi-IA")
    ap.add_argument("--pinned", action="store_true", help="afinidade de cada processo ao seu core (proxy do isolamento)")
    ap.add_argument("--int8", action="store_true", help="quantiza para QInt8, re-valida e re-mede")
    ap.add_argument("--skip-multi", action="store_true", help="salta o multi-IA (smoke rápido)")
    a = ap.parse_args(argv)

    modelo = a.model or train_mod.encontrar_modelo_mais_recente(RUNS)
    if modelo is None or not Path(modelo).exists():
        print("Erro: nenhuma política encontrada — Solução: treina primeiro (train.py) ou passa --model CAMINHO.zip",
              file=sys.stderr)
        return 2
    modelo = Path(modelo)
    onnx_path = a.onnx or modelo.with_suffix(".onnx")
    relatorio: dict = {"modelo": str(modelo), "modelo_sha256": hashlib.sha256(modelo.read_bytes()).hexdigest()[:16]}
    print(f"[deploy] política {modelo.name} ({modelo.stat().st_size} B) → {onnx_path}")

    politica = carregar_politica(modelo)
    relatorio["export"] = exportar_onnx(politica, onnx_path)
    print(f"[deploy] ONNX: {relatorio['export']['bytes']} B · ops {relatorio['export']['ops']} · "
          f"entrada {relatorio['export']['entrada']}")

    obs = observacoes_reais(a.n_val)
    sess = sessao(onnx_path, a.threads)
    relatorio["validacao"] = validar(sess, politica, obs)
    v = relatorio["validacao"]
    print(f"[deploy] validação: max|Δ| = {v['max_delta']:.3e} em {v['n']} obs reais · não finitas {v['nan']} · "
          f"fora de [-1,1] {v['fora_da_caixa_1']} · {'OK' if v['ok'] else 'REPROVOU'}")

    relatorio["benchmark"] = benchmark(sess, obs, a.n_bench, a.threads) | {"veredicto": ""}
    relatorio["benchmark"]["veredicto"] = cabe(relatorio["benchmark"])
    b = relatorio["benchmark"]
    print(f"[deploy] benchmark (proxy RPi, {b['threads']} thread): p50 {b['p50']} µs · p99 {b['p99']} µs · "
          f"max {b['max']} µs · {b['veredicto']}")

    if a.int8:
        int8_path = onnx_path.with_name(onnx_path.stem + "_int8.onnx")
        relatorio["int8"] = quantizar_int8(onnx_path, int8_path)
        sess8 = sessao(int8_path, a.threads)
        relatorio["int8"]["validacao"] = validar(sess8, politica, obs[: max(20, a.n_val // 4)])
        relatorio["int8"]["benchmark"] = benchmark(sess8, obs, a.n_bench, a.threads)
        q = relatorio["int8"]
        razao = (b["p50"] or 0) / max(1e-9, q["benchmark"]["p50"] or 1e-9)
        print(f"[deploy] INT8: {q['bytes']} B ({q['razao_tamanho']}× menor) · max|Δ| {q['validacao']['max_delta']:.3e} · "
              f"p50 {q['benchmark']['p50']} µs (razão medida fp32/int8 {razao:.2f}×)")

    if not a.skip_multi:
        relatorio["multi"] = correr_multi(onnx_path, a.nproc, a.duracao, a.threads, obs)
        m = relatorio["multi"]
        print(f"[deploy] multi-IA ({m['n_proc']} processos, {m['duracao_s']} s): "
              f"{m['inferencias_por_s']} inferências/s · estouros de 20 ms {m['estouros_20ms_totais']}")
        for p in m["processos"]:
            print(f"    proc {p['processo']}: core {p['core_pedido']} · {p['iteracoes']} iterações · "
                  f"p50 {p['p50']} µs · p99 {p['p99']} µs")

    try:
        import onnx
        import onnxruntime
        import torch

        relatorio["versoes"] = {"torch": torch.__version__, "onnx": onnx.__version__,
                                "onnxruntime": onnxruntime.__version__, "numpy": np.__version__}
    except ImportError:            # as versões são informativas: a falta delas não invalida o relatório
        relatorio["versoes"] = {"nota": "não consegui ler todas as versões"}
    relatorio["ok"] = bool(relatorio["validacao"]["ok"])
    destino = a.out or (_AQUI / "out" / "deploy_report.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[deploy] relatório: {destino}")
    print(f"[deploy] veredicto: {'PASSOU' if relatorio['ok'] else 'REPROVOU'} "
          f"(validação numérica do grafo contra o PyTorch)")
    return 0 if relatorio["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
