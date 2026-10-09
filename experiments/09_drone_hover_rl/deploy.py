#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/deploy.py — deploy da política PPO do hover: ONNX → validação → benchmark → multi-IA.

Pipeline (tudo em CPU, sem GPU e sem render):

  1. EXPORT — carrega o `best_model.zip` (`PPO.load`) e exporta o GRAFO da política para ONNX com o *exporter
     legacy* (`torch.onnx.export(..., dynamo=False)`; o `dynamo=True` exigiria `onnxscript`, que não está
     instalado — daí o `DeprecationWarning` esperado). Entrada ESTÁTICA `(1, 16)` float32, opset 17,
     `do_constant_folding=True`, sem `dynamic_axes` (lote = 1, formas fixas). Confere com `onnx.checker` e
     corre com `onnxruntime.InferenceSession` (CPU EP).
  2. VALIDAÇÃO NUMÉRICA — compara o output do grafo com o PyTorch sobre ≥1000 observações REAIS (geradas pelo
     `HoverEnv` com `reset()` + passos de ação aleatória). O que se compara: a AÇÃO DETERMINÍSTICA, isto é a
     **média** da gaussiana da política (`ActorCriticPolicy.get_distribution(obs).mode()` ==
     `policy._predict(obs, deterministic=True)`, que a `DiagGaussianDistribution` define como
     `self.distribution.mean`) — NÃO uma amostra (`sample()`/`rsample()`), que seria estocástica e não teria
     nada que comparar. Como a média é o que o grafo devolve, o `Clip` para a caixa [-1, 1] fica FORA do
     grafo: quem corta é o `HoverEnv.acao_para_ctrl` (`np.clip`) e o `model.predict` (que também corta) — o
     relatório diz quantas observações precisariam desse corte. Portanto os ops do grafo são
     `Gemm`/`Tanh` (+ eventuais `MatMul`/`Add`/`Sub`), sem `Clip`.
     Observações ou saídas NÃO FINITAS (NaN/Inf) REPROVAM a validação explicitamente (`_finitas`): o ONNX
     Runtime devolve `NaN` em silêncio — não levanta exceção — e `max|Δ|` também seria `NaN`, pelo que uma
     comparação ingénua passaria por boa. Reprovada a validação, o veredicto di-lo e o exit code é 1.
  3. BENCHMARK PROXY RPi 5 — sessão ORT com `intra_op_num_threads=1` (proxy do core do A76) e
     `graph_optimization_level=ORT_ENABLE_ALL`; ≥10 000 `session.run` com observações reais e buffer
     pré-alocado `(1, 16)`. Reporta p50/p99/max µs por chamada e responde "cabe a 50 Hz?" (período 20 000 µs)
     e "cabe a 100 Hz?" (10 000 µs). Contraste com `--threads-contraste` (default 4 = todo o SoC do PC).
     `--threads`/`--threads-contraste` exigem inteiro ≥ 1: no ORT o `0` (e negativo) significa "default" =
     TODOS os cores, o que destruiria o proxy de 1 core sem avisar. O `/proc/loadavg` antes/depois entra
     sempre no relatório (mesmo com `--skip-multi`), porque os µs só são comparáveis com a máquina ociosa.
     ATENÇÃO: isto é um PROXY no PC — o alvo de RUN é um Raspberry Pi 5 (4×A76); os números aqui não são os
     de lá (o ganho int8 ~1,83× no RPi vem de outra pesquisa, não deste benchmark).
  4. INT8 (`--int8`) — `onnxruntime.quantization.quantize_dynamic` (QInt8) → re-validação (max|Δ| contra o
     fp32) + re-benchmark (Δ de latência). O relatório dá a RAZÃO medida (p50 fp32 / p50 int8) sem adjetivo
     fixo: neste proxy x86 o int8 tanto pode sair mais rápido como mais lento.
  5. MULTI-IA (`--nproc N`, default 4) — N PROCESSOS (`multiprocessing`, contexto `spawn`), cada um com a SUA
     `InferenceSession` e (com `--pinned`) afinidade ao seu core `(i+1) % N` — proxy do isolamento de cores no
     RPi. O MAPA índice→core é calculado no processo PAI (`mapear_nucleos`) e PASSADO ao filho, que só o
     aplica e o confirma: com `multiprocessing.Pool` o worker é reutilizado e um cálculo local no filho
     herdaria a afinidade da tarefa anterior (índices "colados" no mesmo core). A tabela imprime o core
     OBTIDO e o esperado e avisa se coincidirem mal. Cada processo corre um loop a 50 Hz (`sleep` até ao
     período) durante `--duracao` s e mede o seu p50/p99/max REAL por iteração (só `session.run` + overhead
     Python, SEM o sleep). O pai agrega: tabela por processo, throughput total (inferências/s), CPU por
     `/proc/loadavg` antes/depois (stdlib, sem psutil) e as iterações que estouraram o período de 20 ms.
  6. RELATÓRIO — tabela final + `out/deploy_report.json` (ou `--out CAMINHO`; default: pasta do modelo, ou
     `$TMPDIR` quando o modelo está no temporário = smoke) com versões (torch/onnx/onnxruntime), tempos,
     validação e o veredicto "cabe/no cabe a 50 Hz no proxy".

Correr:

    uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py                  # modelo default
    uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --model m.zip --int8
    uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --skip-multi     # smoke rápido
    uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --nproc 4 --duracao 3 --pinned
    uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --nproc 16 --duracao 0.25 --pinned

Exit codes: 0 = tudo OK · 1 = validação numérica falhou (max|Δ| ≥ 1e-5 ou obs/saída com NaN/Inf) ·
2 = modelo/argumentos inválidos (ficheiro inexistente, zip corrompido ou que não é do Stable-Baselines3,
`--threads`/`--threads-contraste` < 1, nenhum `best_model.zip` em `out/runs/`). O carregamento do modelo está
embrulhado em try/except: uma falha sai como `[ERRO]` legível, nunca como traceback, e NUNCA como o exit 1
(reservado para a validação).

Só este ficheiro: nada aqui toca em `env.py`, `run.py`, `train.py`, `view.py`, `dashboard.py` ou `net_probe.py`
(o ambiente é importado como está, com a configuração default de `HoverEnv`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import platform
import sys
import tempfile
import time
import warnings
from collections import Counter
from pathlib import Path

import numpy as np

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
for _caminho_sys in (str(_AQUI), str(_RAIZ)):     # `env` (irmão) e `lab` (raiz) importáveis
    if _caminho_sys not in sys.path:
        sys.path.insert(0, _caminho_sys)

OBS_DIM = 16                     # contrato do env: observação normalizada, sem VecNormalize ⇒ grafo puro
ACAO_DIM = 4                     # [empuxo, momento x, momento y, momento z]
FREQ_HZ = 50.0                   # decisão do env: decimation=10 × dt=0,002 s
PERIODO_US = 1e6 / FREQ_HZ       # 20 000 µs — período do deadline a 50 Hz
PERIODO_100HZ_US = 10_000.0      # 10 000 µs — período do deadline a 100 Hz
LIMIAR_VALIDACAO = 1e-5          # max|Δ| máximo aceite entre grafo e PyTorch
OP_SET = 17
ENTRADA = "obs"
SAIDA = "acao"
SAIDAS = [SAIDA]
AQUECIMENTO = 200                # runs de aquecimento antes de medir


# ------------------------------------------------------------------------------------- utilidades (stdlib)
def _erro(mensagem: str, codigo: int = 2) -> None:
    """Erro de configuração: imprime `[ERRO] …` e sai com o código (2 = modelo/argumentos inválidos)."""
    print(f"[ERRO] {mensagem}")
    raise SystemExit(codigo)


def _sha256(caminho: Path) -> str:
    """SHA-256 do ficheiro (identifica o grafo no relatório)."""
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _finitas(*arrays) -> bool:
    """Todos os arrays são finitos (sem NaN/Inf)? — o ORT devolve NaN em silêncio, não levanta."""
    return all(bool(np.isfinite(np.asarray(a, dtype=float)).all()) for a in arrays)


def _json_sanitiza(obj):
    """Troca NaN/Inf por `null` (o JSON estrito não tem esses literais; `jq` recusa-os)."""
    if isinstance(obj, dict):
        return {k: _json_sanitiza(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_sanitiza(v) for v in obj]
    if isinstance(obj, (float, np.floating)) and not np.isfinite(obj):
        return None
    if isinstance(obj, (np.integer, np.bool_)):
        return obj.item()
    return obj


def _nucleos_disponiveis() -> list[int]:
    """Cores a que este processo pode ir (lista ordenada); vazia se o SO não suportar afinidade."""
    if not hasattr(os, "sched_getaffinity"):
        return []
    try:
        return sorted(os.sched_getaffinity(0))
    except OSError:
        return []


def mapear_nucleos(n_proc: int) -> list[int] | None:
    """Mapa do PAI: índice i → core `(i + 1) % N` (a lista de cores sai do processo PAI).

    O mapa é calculado AQUI e passado ao filho como argumento. Calculá-lo DENTRO do filho é um bug: com
    `multiprocessing.Pool` o mesmo worker é reutilizado por outra tarefa e `sched_getaffinity` já devolveria
    só o core da tarefa anterior — o índice seguinte herdava o core do anterior em vez do seu.
    """
    disponiveis = _nucleos_disponiveis()
    if not disponiveis:
        return None
    return [disponiveis[((i + 1) % n_proc) % len(disponiveis)] for i in range(n_proc)]


def _loadavg() -> dict:
    """`/proc/loadavg` (médias de 1/5/15 min e processos em execução/total) — stdlib, sem `psutil`."""
    try:
        campos = Path("/proc/loadavg").read_text().split()
        em_execucao, total = campos[3].split("/")
        return {"1min": float(campos[0]), "5min": float(campos[1]), "15min": float(campos[2]),
                "em_execucao": int(em_execucao), "total_processos": int(total)}
    except (OSError, ValueError, IndexError):
        return {}


def _cpu_nome() -> str:
    """Nome do CPU (primeiro `model name` de `/proc/cpuinfo`)."""
    try:
        for linha in Path("/proc/cpuinfo").read_text().splitlines():
            if linha.startswith("model name"):
                return linha.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def _versoes() -> dict:
    """Versões que importam para reproduzir o deploy (o torch é o do treino; o ORT, o do runtime)."""
    import gymnasium
    import onnx
    import onnxruntime as ort
    import stable_baselines3 as sb3
    import torch
    return {"python": platform.python_version(), "torch": torch.__version__, "onnx": onnx.__version__,
            "onnxruntime": ort.__version__, "stable_baselines3": sb3.__version__,
            "gymnasium": gymnasium.__version__, "numpy": np.__version__}


def _dentro(caminho: Path, raiz: Path) -> bool:
    """`caminho` está sob `raiz`? (usado para detetar o modo smoke, com o modelo em `$TMPDIR`)."""
    try:
        caminho.resolve().relative_to(raiz.resolve())
        return True
    except (ValueError, OSError):
        return False


def _tmpdir() -> Path:
    """Diretório temporário da sessão (`$TMPDIR`; nunca o `/tmp` literal)."""
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def _percentis(tempos_us) -> dict:
    """p50/p99/max/média/desvio (µs) de uma série de tempos de chamada."""
    a = np.asarray(tempos_us, dtype=float)
    if a.size == 0:
        return {"n": 0, "p50_us": float("nan"), "p99_us": float("nan"), "max_us": float("nan"),
                "media_us": float("nan"), "desvio_us": float("nan")}
    return {"n": int(a.size), "p50_us": float(np.percentile(a, 50)), "p99_us": float(np.percentile(a, 99)),
            "max_us": float(a.max()), "media_us": float(a.mean()), "desvio_us": float(a.std())}


def _fmt_linha_tempos(p: dict) -> str:
    """Uma linha de tempos (µs) para as tabelas."""
    return (f"p50 {p['p50_us']:8.1f} µs · p99 {p['p99_us']:8.1f} µs · max {p['max_us']:9.1f} µs "
            f"(média {p['media_us']:7.1f} ± {p['desvio_us']:5.1f}, n = {p['n']})")


def _cabe(p: dict) -> str:
    """Veredicto textual de deadline a partir do p99 e do max."""
    ok50 = "SIM" if p["p99_us"] < PERIODO_US else "NÃO"
    ok100 = "SIM" if p["p99_us"] < PERIODO_100HZ_US else "NÃO"
    return (f"cabe a 50 Hz (20 000 µs)? {ok50} (p99 {p['p99_us']:.1f} µs, folga "
            f"{100.0 * (1.0 - p['p99_us'] / PERIODO_US):.1f} % do período) · "
            f"cabe a 100 Hz (10 000 µs)? {ok100} · pior caso {p['max_us']:.1f} µs")


# ------------------------------------------------------------------------------------- env / modelo / obs
def _novo_env():
    """`HoverEnv` com a configuração default (a mesma do treino: alvo 1 m, decimation 10, ruído 0)."""
    from env import HoverEnv
    return HoverEnv()


def gerar_observacoes(env, n: int, seed: int = 0) -> tuple[np.ndarray, int]:
    """`n` observações (16,) REAIS do env: `reset(seed)` + passos de AÇÃO ALEATÓRIA em [-1, 1]⁴.

    Devolve `(obs (n, 16) float32, nº de resets)` — os resets acontecem quando o episódio termina/trunca
    (ação aleatória derruba o drone depressa e isso é esperado). Determinístico dada a seed.
    """
    obs, _ = env.reset(seed=seed)
    amostras = [np.asarray(obs, dtype=np.float32)]
    resets = 0
    while len(amostras) < n:
        acao = env.np_random.uniform(-1.0, 1.0, size=ACAO_DIM).astype(np.float32)
        obs, _, terminado, truncado, _ = env.step(acao)
        amostras.append(np.asarray(obs, dtype=np.float32))
        if terminado or truncado:
            obs, _ = env.reset()
            resets += 1
    return np.stack(amostras[:n]), resets


def modelo_mais_recente() -> Path:
    """`best_model.zip` mais recente de `out/runs/*/` (procura recursiva, escolhe por mtime)."""
    candidatos = [p for p in (_AQUI / "out" / "runs").glob("**/best_model.zip") if p.is_file()]
    if not candidatos:
        _erro(f"nenhum `best_model.zip` em {_AQUI / 'out' / 'runs'} — treina primeiro (train.py) ou passa "
              f"--model CAMINHO")
    return max(candidatos, key=lambda p: p.stat().st_mtime)


def caminho_relatorio_default(modelo: Path) -> Path:
    """Relatório ao lado do modelo; se o modelo está em `$TMPDIR` (smoke) grava no próprio `$TMPDIR`."""
    if _dentro(modelo, _tmpdir()):
        return _tmpdir() / "deploy_report.json"
    return modelo.parent / "deploy_report.json"


def carregar_politica(caminho: Path):
    """`PPO.load` (CPU) e confere que os espaços batem com o contrato do env (16,) → (4,).

    Qualquer falha de carregamento (zip vazio/corrompido, zip que não é SB3, torch desalinhado, obs com outra
    forma) sai como `[ERRO]` limpo com exit 2 — NUNCA um traceback cru, e nunca confundida com o exit 1 da
    validação numérica.
    """
    from stable_baselines3 import PPO
    try:
        modelo = PPO.load(str(caminho), device="cpu")
    except Exception as e:                  # noqa: BLE001 — fronteira de I/O: qualquer falha é "modelo inválido"
        _erro(f"falha ao carregar o modelo {caminho} ({type(e).__name__}: {e}) — ficheiro corrompido/vazio, "
              f"não é um zip do Stable-Baselines3 ou foi gravado com outra versão")
    politica = modelo.policy
    forma_obs = tuple(modelo.observation_space.shape)
    forma_acao = tuple(modelo.action_space.shape)
    if forma_obs != (OBS_DIM,) or forma_acao != (ACAO_DIM,):
        _erro(f"o modelo espera obs {forma_obs} / ação {forma_acao}; o HoverEnv dá "
              f"({OBS_DIM},) / ({ACAO_DIM},)")
    politica.set_training_mode(False)        # sem dropout/batchnorm: caminho determinístico puro
    return modelo, politica


# ------------------------------------------------------------------------------------- ONNX: export/check
def exportar_onnx(politica, caminho_onnx: Path) -> dict:
    """Exporta a AÇÃO DETERMINÍSTICA (média da gaussiana) para ONNX com o exporter legacy (`dynamo=False`).

    O wrapper compõe os submódulos REAIS da política (`features_extractor` → `mlp_extractor.forward_actor` →
    `action_net`), que é exatamente a média devolvida por
    `_get_action_dist_from_latent(...)` → `DiagGaussianDistribution.mode()`. Isto evita arrastar para o grafo
    o `log_std.exp()`/`Normal` (log-probabilidade, que não serve para inferir) e garante um grafo puro.
    """
    import onnx
    import torch
    from torch import nn

    class PoliticaDeterministica(nn.Module):
        """Wrapper de exportação: só o ramo determinístico (média) dos submódulos reais da política."""

        def __init__(self, politica):
            super().__init__()
            self.politica = politica

        def forward(self, obs):
            features = self.politica.extract_features(obs, self.politica.pi_features_extractor)
            return self.politica.action_net(self.politica.mlp_extractor.forward_actor(features))

    embru = PoliticaDeterministica(politica).eval()
    exemplo = torch.zeros((1, OBS_DIM), dtype=torch.float32)          # lote 1, 16 features, estático
    caminho_onnx.parent.mkdir(parents=True, exist_ok=True)

    with warnings.catch_warnings(record=True) as capturados:
        warnings.simplefilter("always")
        torch.onnx.export(embru, (exemplo,), str(caminho_onnx), export_params=True, opset_version=OP_SET,
                          do_constant_folding=True, input_names=[ENTRADA], output_names=[SAIDA],
                          dynamic_axes=None, dynamo=False)
    avisos = [f"{w.category.__name__}: {w.message}" for w in capturados]

    modelo_onnx = onnx.load(str(caminho_onnx))
    onnx.checker.check_model(modelo_onnx)                              # levanta se o grafo for inválido
    ops = Counter(no.op_type for no in modelo_onnx.graph.node)
    entradas = {i.name: [d.dim_value for d in i.type.tensor_type.shape.dim]
                for i in modelo_onnx.graph.input}
    saidas = {s.name: [d.dim_value for d in s.type.tensor_type.shape.dim]
              for s in modelo_onnx.graph.output}
    if entradas.get(ENTRADA) != [1, OBS_DIM] or saidas.get(SAIDA) != [1, ACAO_DIM]:
        _erro(f"formas ONNX inesperadas: entradas={entradas} saídas={saidas} "
              f"(esperado {ENTRADA} [1, {OBS_DIM}] e {SAIDA} [1, {ACAO_DIM}])")
    return {"caminho": str(caminho_onnx), "bytes": caminho_onnx.stat().st_size, "sha256": _sha256(caminho_onnx),
            "opset": {o.domain or "ai.onnx": o.version for o in modelo_onnx.opset_import},
            "ir_version": int(modelo_onnx.ir_version), "ops": dict(sorted(ops.items())),
            "entradas": entradas, "saidas": saidas, "checker": "OK",
            "avisos_export": avisos,
            "dynamo": False, "do_constant_folding": True, "dynamic_axes": None}


def criar_sessao(caminho: Path | str, threads: int = 1):
    """`InferenceSession` ORT: CPU EP, `intra_op_num_threads=threads`, `ORT_ENABLE_ALL`, execução sequencial."""
    import onnxruntime as ort
    opcoes = ort.SessionOptions()
    opcoes.intra_op_num_threads = int(threads)
    opcoes.inter_op_num_threads = 1
    opcoes.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    opcoes.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    opcoes.log_severity_level = 3
    return ort.InferenceSession(str(caminho), sess_options=opcoes, providers=["CPUExecutionProvider"])


def correr_grafo(sessao, obs: np.ndarray) -> np.ndarray:
    """Corre o grafo (lote ESTÁTICO = 1) observação a observação e devolve `(n, 4)`."""
    buf = np.zeros((1, OBS_DIM), dtype=np.float32)
    saida = np.empty((len(obs), ACAO_DIM), dtype=np.float32)
    for i, amostra in enumerate(obs):
        buf[0] = amostra
        saida[i] = sessao.run(SAIDAS, {ENTRADA: buf})[0][0]
    return saida


# ------------------------------------------------------------------------------------- validação numérica
def validar(sessao, politica, modelo, obs: np.ndarray) -> dict:
    """max|Δ| grafo vs PyTorch sobre `obs` REAIS — o que se compara é a MÉDIA (ação determinística).

    Referências: `politica.get_distribution(t).mode()` (= média da gaussiana; é o que o grafo devolve) e
    `politica._predict(t, deterministic=True)` (o mesmo caminho pela API privada do SB3, usado como
    contraprova de que `deterministic=True` ⇒ média, não amostra). `modelo.predict(obs, deterministic=True)`
    é também comparado, mas ele corta a ação à caixa [-1, 1] (`np.clip`, porque `squash_output=False`),
    corte que NÃO está no grafo — o número de observações afetadas fica registado.

    Observações ou saídas NÃO FINITAS (NaN/Inf) REPROVAM a validação, e nada aqui pode estoirar por causa
    disso: o ONNX Runtime devolve `NaN` em silêncio, enquanto o PyTorch faz o contrário — o
    `torch.distributions.Normal` do SB3 valida os argumentos e LEVANTA `ValueError` com a média NaN. Por isso
    o caminho de referência está dentro de um `try/except`: se falhar, fica registado como motivo e a
    validação reprova (com `max|Δ| = NaN` → `null` no JSON), em vez de sair um traceback ou um "OK" falso.
    """
    import torch

    saida = correr_grafo(sessao, obs)
    obs_finitas = _finitas(obs)
    saida_finita = _finitas(saida)
    motivos = []
    if not obs_finitas:
        motivos.append("observações com NaN/Inf")
    if not saida_finita:
        motivos.append("saída do grafo ONNX com NaN/Inf")

    referencia_ok = True
    erro_referencia = None
    try:
        t = torch.as_tensor(np.asarray(obs, dtype=np.float32))
        with torch.no_grad():
            media = politica.get_distribution(t).mode().cpu().numpy()
            privada = politica._predict(t, deterministic=True).cpu().numpy()
            previsao = np.stack([modelo.predict(o, deterministic=True)[0] for o in obs])
    except Exception as e:                    # noqa: BLE001 — referência opcional: falha vira motivo, não crash
        referencia_ok = False
        erro_referencia = f"{type(e).__name__}: {str(e).splitlines()[0]}"
        media = privada = previsao = np.full((len(obs), ACAO_DIM), np.nan, dtype=np.float32)
        motivos.append(f"referência PyTorch indisponível ({erro_referencia})")

    d_media = float(np.abs(saida - media).max())
    d_privada_da_media = float(np.abs(privada - media).max())          # contraprova: _predict devolve a média
    d_predict = float(np.abs(saida - previsao).max())
    fora_da_caixa = int(np.count_nonzero(np.abs(media) > 1.0))

    media_finita = _finitas(media)
    if referencia_ok and not media_finita:
        motivos.append("média do PyTorch com NaN/Inf")
    if not motivos and not d_media < LIMIAR_VALIDACAO:
        motivos.append(f"max|Δ| {d_media:.3e} ≥ limiar {LIMIAR_VALIDACAO:.0e}")
    return {"n": len(obs), "max_delta_media": d_media, "max_delta_predict": d_predict,
            "max_delta_predict_vs_media": float(np.abs(previsao - media).max()),
            "max_delta_privada_vs_media": d_privada_da_media, "limiar": LIMIAR_VALIDACAO,
            "n_fora_da_caixa": fora_da_caixa,
            "obs_finitas": obs_finitas, "saida_finita": saida_finita, "media_finita": media_finita,
            "referencia_ok": referencia_ok, "erro_referencia": erro_referencia,
            "motivo": "; ".join(motivos) or None,
            "referencia": "media_da_gaussiana (get_distribution().mode() == _predict(deterministic=True))",
            "clamp_no_grafo": False, "ok": not motivos}, saida


# ------------------------------------------------------------------------------------- benchmark single
def benchmark(sessao, obs_pool: np.ndarray, n: int, threads: int) -> dict:
    """≥`n` `session.run` com obs reais (buffer pré-alocado) → p50/p99/max µs + veredicto de deadline.

    Observações/saídas não finitas são SINALIZADAS (`obs_finitas`/`saida_finita`), não escondidas: os tempos
    continuam válidos (o ORT corre à mesma), mas o resultado do grafo não é utilizável.
    """
    buf = np.zeros((1, OBS_DIM), dtype=np.float32)
    n_pool = len(obs_pool)
    obs_finitas = _finitas(obs_pool)
    if not obs_finitas:
        print("      [AVISO] observações do benchmark com NaN/Inf: os tempos medidos continuam válidos, mas a "
              "saída do grafo não é utilizável")
    for k in range(min(AQUECIMENTO, n)):
        buf[0] = obs_pool[k % n_pool]
        sessao.run(SAIDAS, {ENTRADA: buf})
    saida_finita = True                       # olha para VÁRIAS amostras: uma só podia ser a saudável
    for k in range(min(n_pool, 32)):
        buf[0] = obs_pool[k]
        if not _finitas(sessao.run(SAIDAS, {ENTRADA: buf})[0]):
            saida_finita = False
            break
    if not saida_finita:
        print("      [AVISO] a saída do grafo tem NaN/Inf: o modelo não é utilizável (ver a validação)")
    tempos = np.empty(n, dtype=float)
    for k in range(n):
        buf[0] = obs_pool[k % n_pool]
        t0 = time.perf_counter_ns()
        sessao.run(SAIDAS, {ENTRADA: buf})
        tempos[k] = (time.perf_counter_ns() - t0) / 1e3
    r = _percentis(tempos)
    r.update({"threads": int(threads), "cabe_50hz": bool(r["p99_us"] < PERIODO_US),
              "cabe_100hz": bool(r["p99_us"] < PERIODO_100HZ_US),
              "inferencias_s": float(1e6 / r["media_us"]) if r["media_us"] > 0 else 0.0,
              "aquecimento": min(AQUECIMENTO, n), "obs_finitas": obs_finitas,
              "saida_finita": saida_finita})
    return r


# ------------------------------------------------------------------------------------- multi-IA (spawn)
def _processo_multi(indice: int, caminho_onnx: str, threads: int, duracao: float, obs_pool: np.ndarray,
                    nucleo_esperado: int | None) -> dict:
    """(FILHO, spawn) loop de inferência a 50 Hz com a SUA sessão ORT e o SEU core, por `duracao` s.

    O core NÃO é calculado aqui: vem do PAI em `nucleo_esperado` (ver `mapear_nucleos`) e este processo só o
    APLICA com `sched_setaffinity`, lendo-o de volta para confirmar (`sched_getaffinity`). Com
    `multiprocessing.Pool` o worker é reutilizado por outra tarefa e a afinidade herdada da tarefa anterior
    tornaria qualquer cálculo local errado — daí a separação.

    Mede apenas `session.run` + o overhead Python da iteração (o `sleep` até ao período fica FORA da
    medição); uma iteração conta como PERDA DE DEADLINE quando esse tempo passa o período de 20 ms.
    Antes do loop faz uma rajada "quente" (200 runs seguidos, SEM sleep) para separar a inferência pura do
    custo de acordar do `sleep` — esse custo cai DENTRO da medição do loop (é a realidade de um loop de
    controlo a 50 Hz) e é a razão pela qual o p50 do loop é maior do que o do benchmark de um só processo.
    """
    nucleo = nucleo_esperado
    afinidade_ok: bool | None = None
    erro_afinidade: str | None = None
    if nucleo_esperado is not None:
        try:
            os.sched_setaffinity(0, {int(nucleo_esperado)})
        except (AttributeError, OSError) as e:
            afinidade_ok, erro_afinidade, nucleo = False, f"{type(e).__name__}: {e}", None
        else:
            obtidos = sorted(os.sched_getaffinity(0))
            afinidade_ok = obtidos == [int(nucleo_esperado)]
            nucleo = obtidos[0] if len(obtidos) == 1 else None

    sessao = criar_sessao(caminho_onnx, threads)
    buf = np.zeros((1, OBS_DIM), dtype=np.float32)
    n_pool = len(obs_pool)
    periodo = 1.0 / FREQ_HZ

    tempos_quentes: list[float] = []
    for k in range(AQUECIMENTO):
        buf[0] = obs_pool[k % n_pool]
        t0 = time.perf_counter_ns()
        sessao.run(SAIDAS, {ENTRADA: buf})
        tempos_quentes.append((time.perf_counter_ns() - t0) / 1e3)
    quente = _percentis(tempos_quentes)

    tempos: list[float] = []
    perdas = 0
    i = 0
    t_inicio = time.perf_counter()
    proximo = t_inicio + periodo
    while time.perf_counter() - t_inicio < duracao:
        buf[0] = obs_pool[i % n_pool]
        t0 = time.perf_counter_ns()
        sessao.run(SAIDAS, {ENTRADA: buf})
        dt_us = (time.perf_counter_ns() - t0) / 1e3
        tempos.append(dt_us)
        if dt_us > PERIODO_US:
            perdas += 1
        i += 1
        proximo += periodo
        espera = proximo - time.perf_counter()
        if espera > 0:
            time.sleep(espera)
    p = _percentis(tempos)
    return {"indice": int(indice), "pid": int(os.getpid()), "nucleo": nucleo,
            "nucleo_esperado": nucleo_esperado, "afinidade_ok": afinidade_ok,
            "erro_afinidade": erro_afinidade, "iteracoes": len(tempos),
            "perdas": int(perdas), "tempos_us": tempos, "rajada_quente": quente, **p}


def correr_multi(caminho_onnx: Path, n_proc: int, duracao: float, threads: int, obs_pool: np.ndarray,
                 afinidade: bool) -> dict:
    """Arranca N processos (spawn) e agrega tempos, throughput total, loadavg e perdas de deadline.

    O mapa índice → core é calculado no PAI (`mapear_nucleos`) e cada filho limita-se a aplicá-lo.
    """
    disponiveis = _nucleos_disponiveis()
    mapa = mapear_nucleos(n_proc) if afinidade else None
    avisos = []
    if afinidade and mapa is None:
        avisos.append("sched_setaffinity indisponível neste SO: --pinned ignorado")
    if mapa is not None and n_proc > len(disponiveis):
        avisos.append(f"{n_proc} processos para {len(disponiveis)} cores: há cores partilhados por construção")
    load_antes = _loadavg()
    contexto = mp.get_context("spawn")
    tarefas = [(i, str(caminho_onnx), threads, duracao, obs_pool, (mapa[i] if mapa else None))
               for i in range(n_proc)]
    t0 = time.perf_counter()
    with contexto.Pool(processes=n_proc) as pool:              # o __exit__ termina/aguarda os filhos
        resultados = pool.starmap(_processo_multi, tarefas)
    parede = time.perf_counter() - t0
    load_depois = _loadavg()

    resultados.sort(key=lambda r: r["indice"])
    iteracoes = sum(r["iteracoes"] for r in resultados)
    perdas = sum(r["perdas"] for r in resultados)
    agregado = _percentis(np.concatenate([np.asarray(r["tempos_us"], dtype=float) for r in resultados]))
    delta_load = (load_depois.get("1min", float("nan")) - load_antes.get("1min", float("nan"))
                  if load_antes and load_depois else float("nan"))

    # pinning: o que CONTa é o core efetivamente obtido no filho vs o esperado pelo mapa do pai
    nucleos = [r["nucleo"] for r in resultados if r["nucleo"] is not None]
    distintos = len(set(nucleos))
    com_afinidade = [r for r in resultados if r["nucleo_esperado"] is not None]
    pinning_ok = all(r["afinidade_ok"] for r in com_afinidade) if com_afinidade else None
    for r in resultados:
        if r["erro_afinidade"]:
            avisos.append(f"processo {r['indice']}: falha ao fixar o core {r['nucleo_esperado']} "
                          f"({r['erro_afinidade']})")
        elif r["afinidade_ok"] is False:
            avisos.append(f"processo {r['indice']}: afinidade obtida {r['nucleo']} ≠ esperada "
                          f"{r['nucleo_esperado']}")
    if mapa is not None and distintos != len(set(mapa)):
        avisos.append(f"só {distintos} cores distintos para {len(set(mapa))} cores no mapa")
    return {"nproc": int(n_proc), "duracao_s": float(duracao), "threads": int(threads),
            "afinidade": bool(afinidade), "nucleos_disponiveis": len(disponiveis),
            "mapa_nucleos": mapa, "nucleos_distintos": int(distintos), "pinning_ok": pinning_ok,
            "avisos": avisos,
            "parede_s": float(parede), "iteracoes_total": int(iteracoes), "perdas_total": int(perdas),
            "throughput_inf_s": float(iteracoes / parede) if parede > 0 else 0.0,
            "processos": resultados, "agregado": agregado,
            "loadavg_antes": load_antes, "loadavg_depois": load_depois,
            "loadavg_delta_1min": float(delta_load)}


# ------------------------------------------------------------------------------------- int8
def quantizar_int8(caminho_fp32: Path, caminho_int8: Path) -> dict:
    """`quantize_dynamic` (QInt8) do grafo fp32 → ficheiro int8 (+ tamanhos)."""
    from onnxruntime.quantization import QuantType, quantize_dynamic
    quantize_dynamic(str(caminho_fp32), str(caminho_int8), weight_type=QuantType.QInt8)
    b_fp32, b_int8 = caminho_fp32.stat().st_size, caminho_int8.stat().st_size
    return {"caminho": str(caminho_int8), "bytes": int(b_int8), "bytes_fp32": int(b_fp32),
            "reducao_tamanho": float(b_int8 / b_fp32) if b_fp32 else float("nan"),
            "sha256": _sha256(caminho_int8), "weight_type": "QInt8", "metodo": "quantize_dynamic"}


# ------------------------------------------------------------------------------------- main
def _cli(argv=None) -> argparse.Namespace:
    """Argumentos da linha de comandos (todos com default utilizável em smoke)."""
    p = argparse.ArgumentParser(
        prog="deploy.py",
        description="Deploy da política PPO do hover: export ONNX + validação + benchmark proxy RPi 5 + N IAs "
                    "em paralelo (só CPU, sem render).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--model", type=Path, default=None,
                   help="caminho do .zip do SB3 (default: best_model.zip mais recente de out/runs/*/)")
    p.add_argument("--onnx", type=Path, default=None,
                   help="ONNX de saída (default: <pasta do modelo>/policy.onnx)")
    p.add_argument("--timesteps-bench", type=int, default=10_000,
                   help="nº de session.run medidos no benchmark de um só processo")
    p.add_argument("--threads", type=int, default=1,
                   help="intra_op_num_threads do benchmark (inteiro ≥ 1; 1 = proxy do core do RPi 5)")
    p.add_argument("--threads-contraste", type=int, default=4,
                   help="intra_op_num_threads da variante de contraste (inteiro ≥ 1; todo o SoC do PC)")
    p.add_argument("--int8", action="store_true", help="quantiza dinamicamente para int8 e re-benchmarka")
    p.add_argument("--nproc", type=int, default=4, help="nº de PROCESSOS no teste multi-IA")
    p.add_argument("--duracao", type=float, default=10.0, help="duração do loop de cada processo (s)")
    p.add_argument("--pinned", action="store_true",
                   help="fixa cada processo ao seu core ((i+1) %% N) via sched_setaffinity — proxy do RPi")
    p.add_argument("--n-validacao", type=int, default=1024,
                   help="nº de observações reais na validação numérica (≥ 1000)")
    p.add_argument("--seed", type=int, default=0, help="seed da geração de observações")
    p.add_argument("--out", type=Path, default=None,
                   help="relatório JSON (default: pasta do modelo, ou $TMPDIR se o modelo estiver no temporário)")
    p.add_argument("--skip-multi", action="store_true", help="salta o teste multi-IA (smoke rápido)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    """Corre o pipeline completo e devolve o exit code (0 OK · 1 validação falhou · 2 config inválida)."""
    args = _cli(argv)
    if args.timesteps_bench < 1 or args.nproc < 1 or args.duracao <= 0 or args.n_validacao < 1:
        print("[ERRO] --timesteps-bench, --nproc, --n-validacao ≥ 1 e --duracao > 0")
        return 2
    # --threads 0/negativo não é "1 thread": o ORT interpreta 0 (e valores < 0) como "default" = todos os
    # cores do SoC, o que arruinaria o proxy de 1 core do RPi e mentiria no relatório.
    if args.threads < 1 or args.threads_contraste < 1:
        print(f"[ERRO] --threads/--threads-contraste têm de ser inteiros ≥ 1 (recebido "
              f"--threads {args.threads}, --threads-contraste {args.threads_contraste}); no ONNX Runtime "
              f"0/negativo significa 'default' = todos os cores, não 1 core")
        return 2
    if args.n_validacao < 1000:
        print(f"[AVISO] --n-validacao {args.n_validacao} < 1000: o critério pede ≥ 1000 observações")
    if args.timesteps_bench < 1000:
        print(f"[AVISO] --timesteps-bench {args.timesteps_bench} < 1000: com tão poucas amostras o p99 fica "
              f"praticamente igual ao max (a estatística de cauda é fraca) — usa ≥ 10 000 para um p99 útil")

    modelo_caminho = args.model or modelo_mais_recente()
    if not modelo_caminho.is_file():
        print(f"[ERRO] modelo não encontrado: {modelo_caminho}")
        return 2
    onnx_caminho = args.onnx or (modelo_caminho.parent / "policy.onnx")
    relatorio_caminho = args.out or caminho_relatorio_default(modelo_caminho)
    smoke = _dentro(modelo_caminho, _tmpdir())
    t_inicio = time.perf_counter()
    load_inicio = _loadavg()          # o loadavg entra SEMPRE no relatório (mesmo com --skip-multi)

    versoes = _versoes()
    print("=" * 110)
    print("deploy.py — política PPO do hover → ONNX → validação → benchmark proxy RPi 5 → multi-IA")
    print(f"CPU: {_cpu_nome()} · núcleos disponíveis: "
          f"{len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count()}")
    print(f"versões: torch {versoes['torch']} · onnx {versoes['onnx']} · onnxruntime {versoes['onnxruntime']} "
          f"· sb3 {versoes['stable_baselines3']} · numpy {versoes['numpy']} · python {versoes['python']}")
    print(f"modelo: {modelo_caminho}" + ("  [SMOKE: modelo em $TMPDIR]" if smoke else ""))
    print(f"ONNX: {onnx_caminho}")
    print(f"relatório: {relatorio_caminho}")
    print("=" * 110)

    # 1) modelo + observações reais
    modelo, politica = carregar_politica(modelo_caminho)
    env = _novo_env()
    t_obs = time.perf_counter()
    obs, resets = gerar_observacoes(env, args.n_validacao, seed=args.seed)
    t_obs = time.perf_counter() - t_obs
    print(f"\n[1/6] observações REAIS do HoverEnv: {obs.shape} float32 · {resets} resets · "
          f"{t_obs:.1f} s · norma média {float(np.linalg.norm(obs, axis=1).mean()):.3f} "
          f"(passos de ação aleatória em [-1,1]⁴)")

    # 2) export ONNX + checker + sessão ORT
    info_onnx = exportar_onnx(politica, onnx_caminho)
    print(f"[2/6] ONNX exportado ({info_onnx['bytes']} B, sha256 {info_onnx['sha256'][:12]}…) · "
          f"opset {info_onnx['opset']} · ir_version {info_onnx['ir_version']} · "
          f"entradas {info_onnx['entradas']} → saídas {info_onnx['saidas']}")
    print(f"      ops do grafo: {info_onnx['ops']}  (exporter legacy dynamo=False, "
          f"do_constant_folding=True, dynamic_axes=None)")
    for aviso in info_onnx["avisos_export"][:3]:
        print(f"      aviso do export: {aviso}")
    if len(info_onnx["avisos_export"]) > 3:
        print(f"      … +{len(info_onnx['avisos_export']) - 3} avisos")
    print(f"      onnx.checker: {info_onnx['checker']} · onnxruntime: "
          f"{criar_sessao(onnx_caminho, args.threads).get_providers()}")

    # 3) validação numérica
    sessao_fp32 = criar_sessao(onnx_caminho, args.threads)
    validacao, saidas_fp32 = validar(sessao_fp32, politica, modelo, obs)
    print(f"[3/6] validação numérica sobre {validacao['n']} obs reais — referência: "
          f"{validacao['referencia']}")
    print(f"      max|Δ| ONNX vs média (gaussiana)      = {validacao['max_delta_media']:.3e}  "
          f"(limiar {validacao['limiar']:.0e}) → {'[OK]' if validacao['ok'] else '[FALHA]'}")
    print(f"      contraprova: |_predict(det.) − média| = {validacao['max_delta_privada_vs_media']:.3e} "
          f"(é a MESMA coisa: a SB3 devolve a média, não uma amostra)")
    print(f"      max|Δ| ONNX vs model.predict (com clip) = {validacao['max_delta_predict']:.3e} · "
          f"{validacao['n_fora_da_caixa']}/{validacao['n']} médias fora de [-1,1] (o clip fica no env)")
    print(f"      finitude: obs {'OK' if validacao['obs_finitas'] else 'NaN/Inf'} · grafo "
          f"{'OK' if validacao['saida_finita'] else 'NaN/Inf'} · PyTorch "
          f"{'OK' if validacao['media_finita'] else 'NaN/Inf'}")
    if not validacao["ok"]:
        print(f"      [FALHA] {validacao['motivo']} — o grafo não reproduz a política "
              f"(o ORT devolve NaN/Inf em silêncio; ver o relatório)")

    # 4) benchmark fp32 (proxy RPi 5) + contraste
    print(f"[4/6] benchmark proxy RPi 5: {args.timesteps_bench} session.run, "
          f"intra_op={args.threads} (proxy do core do A76), ORT_ENABLE_ALL, buffer (1,{OBS_DIM}) pré-alocado")
    bench = benchmark(sessao_fp32, obs, args.timesteps_bench, args.threads)
    print(f"      --threads {bench['threads']}: {_fmt_linha_tempos(bench)}")
    print(f"      → {_cabe(bench)} · {bench['inferencias_s']:.0f} inferências/s num core")
    bench_contraste = None
    if args.threads_contraste != args.threads:
        sessao_contraste = criar_sessao(onnx_caminho, args.threads_contraste)
        bench_contraste = benchmark(sessao_contraste, obs, args.timesteps_bench, args.threads_contraste)
        print(f"      contraste --threads {bench_contraste['threads']} (todo o SoC do PC): "
              f"{_fmt_linha_tempos(bench_contraste)}")
        print(f"      → ganho p50 = {bench['p50_us'] / bench_contraste['p50_us']:.2f}× · "
              f"{_cabe(bench_contraste)}")
    load_bench = _loadavg()
    if load_inicio and load_bench:
        print(f"      contexto de carga: /proc/loadavg 1 min {load_inicio['1min']:.2f} → "
              f"{load_bench['1min']:.2f} durante o benchmark · em execução "
              f"{load_inicio['em_execucao']} → {load_bench['em_execucao']} (os µs só são comparáveis com a "
              f"máquina ociosa)")

    # 5) int8 opcional
    int8 = None
    if args.int8:
        caminho_int8 = onnx_caminho.with_name(onnx_caminho.stem + "_int8.onnx")
        print(f"[5/6] int8: quantize_dynamic(QInt8) → {caminho_int8}")
        info_int8 = quantizar_int8(onnx_caminho, caminho_int8)
        sessao_int8 = criar_sessao(caminho_int8, args.threads)
        saidas_int8 = correr_grafo(sessao_int8, obs)
        d_int8 = float(np.abs(saidas_int8 - saidas_fp32).max())
        bench_int8 = benchmark(sessao_int8, obs, args.timesteps_bench, args.threads)
        fator = float(bench["p50_us"] / bench_int8["p50_us"]) if bench_int8["p50_us"] else 0.0
        int8 = {"info": info_int8, "max_delta_vs_fp32": d_int8,
                "benchmark": bench_int8,
                "delta_p50_us": float(bench_int8["p50_us"] - bench["p50_us"]),
                "fator_p50": fator, "int8_mais_rapido": bool(fator > 1.0),
                "delta_p99_us": float(bench_int8["p99_us"] - bench["p99_us"])}
        print(f"      tamanho {info_int8['bytes']} B vs {info_int8['bytes_fp32']} B fp32 "
              f"({info_int8['reducao_tamanho']:.2f}×) · max|Δ| int8 vs fp32 = {d_int8:.3e} (degradação)")
        print(f"      --threads {bench_int8['threads']}: {_fmt_linha_tempos(bench_int8)}")
        print(f"      → medido nesta máquina: Δ p50 = {int8['delta_p50_us']:+.1f} µs e razão "
              f"p50_fp32/p50_int8 = {fator:.2f}× ({'int8 mais rápido' if fator > 1.0 else 'int8 mais lento'} "
              f"nesta medição — não é um resultado universal) · {_cabe(bench_int8)}")

    # 6) multi-IA
    multi = None
    if not args.skip_multi:
        print(f"[6/6] multi-IA: {args.nproc} PROCESSOS (spawn), cada um com a sua sessão ORT "
              f"(intra_op={args.threads})" + (f", afinidade ao core (i+1) % {args.nproc}"
                                              if args.pinned else ", sem afinidade") +
              f", loop a 50 Hz durante {args.duracao} s")
        multi = correr_multi(onnx_caminho, args.nproc, args.duracao, args.threads, obs, args.pinned)
        print(f"      {'proc':>4} {'pid':>7} {'core':>5} {'esp.':>5} {'iterações':>10} {'p50 µs':>9} "
              f"{'p99 µs':>9} {'max µs':>9} {'perdas':>7}")
        for r in multi["processos"]:
            nucleo = "-" if r["nucleo"] is None else str(r["nucleo"])
            esperado = "-" if r["nucleo_esperado"] is None else str(r["nucleo_esperado"])
            print(f"      {r['indice']:>4} {r['pid']:>7} {nucleo:>5} {esperado:>5} {r['iteracoes']:>10} "
                  f"{r['p50_us']:>9.1f} {r['p99_us']:>9.1f} {r['max_us']:>9.1f} {r['perdas']:>7}")
        la_a, la_d = multi["loadavg_antes"], multi["loadavg_depois"]
        quentes = {r["indice"]: r["rajada_quente"]["p50_us"] for r in multi["processos"]}
        print(f"      total: {multi['iteracoes_total']} iterações · "
              f"throughput {multi['throughput_inf_s']:.1f} inferências/s "
              f"(parede {multi['parede_s']:.2f} s, inclui arranque dos processos) · "
              f"{multi['perdas_total']} perdas de deadline em {multi['iteracoes_total']} iterações")
        if multi["mapa_nucleos"] is not None:
            estado = ("todos os índices no core esperado" if multi["pinning_ok"] else
                      "há índice(s) FORA do core esperado")
            print(f"      pinning: {multi['nucleos_distintos']}/{len(set(multi['mapa_nucleos']))} cores "
                  f"distintos · {estado} · mapa índice→core {multi['mapa_nucleos']}")
        for aviso in multi["avisos"]:
            print(f"      [AVISO] {aviso}")
        print(f"      p50 do loop ≈ {multi['agregado']['p50_us']:.1f} µs vs p50 em rajada quente (sem sleep) "
              f"{np.mean(list(quentes.values())):.1f} µs: a diferença é o custo de ACORDAR do sleep, que cai "
              f"dentro da iteração — é a realidade de um loop a 50 Hz, não overhead do modelo")
        if la_a and la_d:
            print(f"      /proc/loadavg 1 min: {la_a['1min']:.2f} → {la_d['1min']:.2f} "
                  f"(Δ {multi['loadavg_delta_1min']:+.2f}; a média de 1 min reage devagar a "
                  f"{args.duracao:g} s de teste) · em execução: {la_a['em_execucao']}/{la_a['total_processos']} "
                  f"→ {la_d['em_execucao']}/{la_d['total_processos']}")
    else:
        print("[6/6] multi-IA: saltado (--skip-multi)")

    # relatório + veredicto
    parede = time.perf_counter() - t_inicio
    load_fim = _loadavg()
    if multi is not None:
        veredicto_tempos = (f"cabe a 50 Hz no proxy ({multi['nproc']} IAs em paralelo, p99 agregado "
                            f"{multi['agregado']['p99_us']:.1f} µs < {PERIODO_US:.0f} µs, "
                            f"{multi['perdas_total']} perdas em {multi['iteracoes_total']} iterações)"
                            if multi["perdas_total"] == 0 else
                            f"NÃO cabe a 50 Hz no proxy com {multi['nproc']} IAs: {multi['perdas_total']} "
                            f"perdas de deadline em {multi['iteracoes_total']} iterações")
    else:
        veredicto_tempos = (f"cabe a 50 Hz no proxy (p99 {bench['p99_us']:.1f} µs < {PERIODO_US:.0f} µs)"
                            if bench["cabe_50hz"] else
                            f"NÃO cabe a 50 Hz no proxy (p99 {bench['p99_us']:.1f} µs ≥ {PERIODO_US:.0f} µs)")
    # uma validação reprovada MANDA no veredicto: um grafo que devolve NaN/Inf ou não reproduz a política
    # não é "utilizável a 50 Hz", por muito bom que seja o tempo.
    veredicto = (f"validação numérica FALHOU ({validacao['motivo']}) — deploy NÃO fiável; tempos: "
                 f"{veredicto_tempos}" if not validacao["ok"] else veredicto_tempos)
    relatorio = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "parede_s": float(parede), "smoke": bool(smoke),
        "host": platform.node(), "cpu": _cpu_nome(),
        "nucleos": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count(),
        "versoes": versoes,
        "loadavg": {"inicio": load_inicio, "apos_benchmark": load_bench, "fim": load_fim,
                    "delta_1min_total": float(load_fim.get("1min", float("nan"))
                                              - load_inicio.get("1min", float("nan")))
                    if load_inicio and load_fim else None,
                    "nota": "médias de 1/5/15 min e processos em execução/total de /proc/loadavg (stdlib); "
                            "a média de 1 min reage devagar a testes de poucos segundos"},
        "modelo": {"caminho": str(modelo_caminho), "bytes": int(modelo_caminho.stat().st_size),
                   "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(modelo_caminho.stat().st_mtime))},
        "estatico": {"obs_dim": OBS_DIM, "acao_dim": ACAO_DIM, "freq_hz": FREQ_HZ,
                     "periodo_us": PERIODO_US, "periodo_100hz_us": PERIODO_100HZ_US},
        "cli": {"threads": args.threads, "threads_contraste": args.threads_contraste,
                "timesteps_bench": args.timesteps_bench, "n_validacao": args.n_validacao,
                "nproc": args.nproc, "duracao_s": args.duracao, "pinned": bool(args.pinned),
                "int8": bool(args.int8), "skip_multi": bool(args.skip_multi), "seed": args.seed},
        "onnx": info_onnx, "validacao": validacao,
        "observacoes": {"n": len(obs), "resets": int(resets), "seed": int(args.seed),
                        "geracao_s": float(t_obs), "politica": "aleatória em [-1,1]^4 sobre o HoverEnv"},
        "benchmark": bench, "benchmark_contraste": bench_contraste, "int8": int8, "multi_ia": multi,
        "proxy": "PC desta máquina — PROXY, não o Raspberry Pi 5 (4×A76) alvo; o int8 ~1,83× no RPi vem "
                 "de outra pesquisa, não deste benchmark",
        "veredicto": veredicto,
    }
    relatorio_caminho.parent.mkdir(parents=True, exist_ok=True)
    relatorio_caminho.write_text(json.dumps(_json_sanitiza(relatorio), indent=2, ensure_ascii=False) + "\n")

    print("-" * 110)
    print(f"[relatório] {relatorio_caminho} ({relatorio_caminho.stat().st_size} B)")
    print(f"tempos: fp32 {_fmt_linha_tempos(bench)}")
    if int8 is not None:
        print(f"tempos: int8 {_fmt_linha_tempos(int8['benchmark'])}")
    print(f"VEREDICTO: {veredicto}")
    print(f"validação: max|Δ| {validacao['max_delta_media']:.3e} < {LIMIAR_VALIDACAO:.0e} → "
          f"{'[OK]' if validacao['ok'] else '[FALHA]'}"
          + (f" · motivo: {validacao['motivo']}" if validacao["motivo"] else "")
          + f" · pipeline completo em {parede:.1f} s")
    print("=" * 110)
    return 0 if validacao["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
