#!/usr/bin/env python3
"""sim_site.py — UM COMANDO arranca o padrão do laboratório: runner + servidor + site (`padrao-simulacao-clean-site`).

    uv run --group hover-rl python <exp>/sim_site.py                 # janela 3D LIMPA + site em http://127.0.0.1:8080
    uv run --group hover-rl python <exp>/sim_site.py --sem-janela    # só site + API (validação, sem janela nenhuma)
    uv run --group hover-rl python <exp>/sim_site.py --model out/melhor_modelo.zip --port 0

O que este ficheiro faz:
  1. arranca o RUNNER (`sim_view.py`) como SUBPROCESSO — é ele que abre a janela limpa e escreve a telemetria;
  2. serve o SITE (`site/dist/`) e a API JSON que o site consome (só stdlib: `http.server`);
  3. imprime o URL no terminal e abre o browser.

Janela MuJoCo 100% clean: a janela mostra SÓ a simulação 3D (o runner nunca chama `set_texts`/`set_figures`).
TODAS as métricas e TODOS os controlos ficam no site: vento em tempo real, VENTO DINÂMICO (rajadas/frente/
turbulência), REINICIAR (é o ÚNICO caminho de reinício), LOOP (desligado por omissão — sem ciclo automático) e
o painel do COMPUTADOR DE BORDO (Raspberry Pi 5).

API (6 rotas — é o CONTRATO, não mudar ao copiar o template):
  · `GET  /api/sim`          → `{"estado","ep","passo","retorno","vento":{vel,azimute,elevacao,ativo,vec,modo},
                               "vento_dinamico":{modo,params,ativo},"vento_atual":{vec,vel,azimute,elevacao,modo,
                               fonte},"rpi5":{…},"linhas":[…]}` com as ≤200 últimas amostras da telemetria;
  · `GET  /api/state`        → o mesmo resumo sem `linhas`, mais `modelo_nome`, `sim_vivo`, `contador_reiniciar`,
                               `loop`, `pid`, `porta`, `idade_telemetria_s` e o painel `rpi5` completo (specs
                               oficiais citadas + inferência medida + uso ao vivo);
  · `POST /api/vento`        → `{"vel","azimute","elevacao"}` (qualquer subconjunto; faixas 0–5 m/s, 0–360°,
                               −90–90°) → 200 · 400 se fora da faixa;
  · `POST /api/vento-dinamico` → `{"modo": "nenhum"|"rajadas"|"frente"|"dryden"|"rajada_agora", "params": {…},
                               "ativo": bool}`: liga/desliga a dinâmica SEM reiniciar o episódio (`rajadas`/
                               `dryden` e o `frente` do formato `{u_max,t_s}` são validados pelo PRÓPRIO `env.py`;
                               o `frente` aceita ainda `{vel,azimute,elevacao}` = degrau imediato do vento base;
                               `rajada_agora` é uma rajada dirigida one-shot);
  · `POST /api/reiniciar`    → incrementa `reiniciar` no controlo → `{"contador": n}` (reinício pelo site);
  · `POST /api/loop`         → `{"ativo": bool}` liga/desliga o auto-reset no fim do episódio.
Estados honestos: 400 (valor/faixa inválida) · 404 (rota/asset/path traversal) · 500. Sem websockets: o site
faz polling a `GET /api/sim` a ~2,9 Hz.

PAINEL DO RASPBERRY PI 5 (computador de bordo de TODOS os projetos): o `rpi5` do `/api/sim`//`/api/state` é
montado a partir do relatório do `deploy.py` (`out/deploy_report.json`; `--benchmark` aponta a outro ficheiro)
+ das decisões/s medidas na telemetria. Sem relatório o painel diz «sem benchmark» e não inventa tempos.

Pré-requisito do site (uma vez): `cd site && npm install && npm run build` (ver `site/LEIAME.md`). Se o
`dist/` não existir, o servidor serve uma página a dizer exatamente isso — e o resto (API) funciona na mesma.

PORTÁTIL (bundle `front-conexao`): o módulo do projeto só é importado quando alguém usa o vento
dinâmico (para validar os modos com as MESMAS regras do `env.py`); sem essa função a validação é
estrutural (modos do contrato + números finitos). `--env-modulo NOME` escolhe o módulo (padrão `env`).
ADAPTAR: nada aqui — o que é do teu robô está no `env.py` do projeto e em `site/src/lib/config.ts`.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_RAIZ), str(_AQUI)]     # para o `env.valida_vento_dinamico` (importado só quando usado)
SITE_DIST = _AQUI / "site" / "dist"
SITE_FONTES = _AQUI / "site"
CONTROLO_OMISSAO = _AQUI / "out" / "controle_vento.json"
TELEMETRIA_OMISSAO = _AQUI / "out" / "sim_telemetria.jsonl"
RUNNER = _AQUI / "sim_view.py"
INDEX = SITE_DIST / "index.html"
MAX_LINHAS = 200                       # teto de amostras devolvidas por `GET /api/sim`
MAX_CORPO = 64 * 1024                  # teto do corpo de um POST (64 kB chega e sobra)
MAX_LEITURA = 4 * 1024 * 1024          # bytes lidos do fim da telemetria por pedido
FAIXAS = {"vel": (0.0, 5.0), "azimute": (0.0, 360.0), "elevacao": (-90.0, 90.0)}
VEL_MAX, AZIM_MAX, ELEV_MAX = FAIXAS["vel"][1], FAIXAS["azimute"][1], FAIXAS["elevacao"][1]
TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css",
         ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
         ".webp": "image/webp", ".woff2": "font/woff2", ".woff": "font/woff", ".map": "application/json",
         ".txt": "text/plain; charset=utf-8"}
# vento DINÂMICO ao vivo: os 3 modos contínuos são do `env.py`, `rajada_agora` é um one-shot do runner e
# `nenhum` é inerte. As chaves dos params são as MESMAS do treino (`--vento-dinamico-params`).
MODOS_DINAMICOS = ("nenhum", "rajadas", "frente", "dryden", "rajada_agora")
MODOS_DINAMICOS_ENV = ("rajadas", "frente", "dryden")
FRENTE_BASE, FRENTE_ENV = ("vel", "azimute", "elevacao"), ("u_max", "t_s")   # os 2 formatos do `frente`
RAJADA_DURACAO_PADRAO = 25             # passos de decisão (0,5 s a 50 Hz) — duração da rajada one-shot
RAJADA_U_PADRAO = 3.0                  # m/s — amplitude da rajada one-shot sem `u` nos params
RAJADA_U_MAX = VEL_MAX                 # m/s — teto do contrato para a rajada one-shot
CONTROLO_INICIAL = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False, "reiniciar": 0,
                    "loop": False, "dinamico": {"modo": "nenhum", "params": {}, "ativo": False, "seq": 0}}
# painel RPi 5: o relatório do `deploy.py` é procurado por ordem (o `--benchmark` manda nisto)
BENCHMARKS = (_AQUI / "out" / "deploy_report.json", _AQUI / "out" / "deploy" / "deploy.json")
BUDGET_US = 20_000.0                   # 50 Hz = 20 ms por decisão (o `PERIODO_50HZ_US` do deploy.py)
NUCLEOS_SOC = 4                        # 4× Cortex-A76 no BCM2712
RPI5_SPECS = {
    "soc": "Broadcom BCM2712",
    "cpu": "4× Cortex-A76 @ 2,4 GHz (512 kB L2/núcleo + 2 MB L3)",
    "ram": "LPDDR4X-4267, 1–16 GB (variante)",
    "gpu": "VideoCore VII",
    "alimentacao": "5 V / 5 A (27 W); pico ~12 W",
    "throttle": "térmico 80 → 85 °C (corte de 2,4 → 1,5 GHz)",
    "alvo_hz": 50,
    "budget_ms": 20,
    "nucleos": NUCLEOS_SOC,
    "npu": None,                       # o BCM2712 não tem NPU: quem corre a rede é o CPU (ONNX Runtime)
    "jitter_so": {"standard_ms_pior_caso": 9.4, "preempt_rt_us_max": 225,
                  "nota": "o jitter do SO é o gargalo real a 50 Hz: 9,4 ms de pior caso num kernel standard "
                          "contra os 20 ms do período (um kernel PREEMPT_RT desce a ≤225 µs)"},
    "inferencia_publicada": {"modelo": "small CNN (ONNX Runtime, 1 core A76)",
                             "fp32_ms": 0.194, "int8_ms": 0.143, "fator_int8": 1.36, "fator_int8_sdot": 1.83,
                             "nucleos_ort_default": "intra_op = núcleos físicos; XNNPACK EP = 1"},
    "fonte": "Raspberry Pi 5 Product Brief (RP-008348-DS) + medições publicadas no A76",
    "nota": "specs do ALVO (Raspberry Pi 5); a imagem do painel é uma ILUSTRAÇÃO de referência (Model B+)",
}
MENSAGEM_SEM_DIST = (
    "site/dist/index.html não existe — corra `npm run build` em {pasta} (ou `npm install && npm run build`) "
    "e recarregue esta página."
)
_VALIDADOR_ENV = None
# Módulo do PROJETO (lista de 1, para o `--env-modulo` o poder trocar antes do 1.º uso)
_MODULO_ENV = ["env"]


# ------------------------------------------------------------------------------------ utilidades (só stdlib)
def _absoluto(caminho) -> Path:
    """Caminho absoluto (resolvido contra o cwd do SITE, não o do runner) — `--controlo`/`--telemetria`.

    O runner é lançado com `cwd=cwd do site` (para o MUJOCO_LOG.TXT ficar fora da raiz), por isso um caminho
    relativo tem de ser fixado aqui: senão o site lia/escrevia num sítio e o filho noutro, e a telemetria
    nunca aparecia na API.
    """
    alvo = Path(caminho).expanduser()
    return alvo if alvo.is_absolute() else (Path.cwd() / alvo).resolve()


def escrever_atomico(caminho: Path, dados: dict) -> None:
    """Escrita ATÓMICA (tmp no mesmo diretório + `os.replace`): quem lê nunca vê o ficheiro a meio."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(f".{caminho.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, caminho)


def escrever_controlo(caminho: Path, dados: dict) -> dict:
    """Escreve o controlo de forma atómica e carimba `t` (o runner ignora-o; serve de rasto para o site)."""
    registo = {**CONTROLO_INICIAL, **dados, "t": round(time.time(), 3)}
    escrever_atomico(caminho, registo)
    return registo


def ler_controlo(caminho: Path) -> dict:
    """Conteúdo do ficheiro de controlo (ou os valores de arranque, se ainda não existir/estiver inválido)."""
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            return {**CONTROLO_INICIAL, **dados}
    except (OSError, ValueError):
        pass
    return dict(CONTROLO_INICIAL)


def ultimas_linhas(caminho: Path, n: int = MAX_LINHAS) -> list[dict]:
    """As ≤n últimas linhas JSON VÁLIDAS da telemetria (lê só o FIM do ficheiro; ignora linhas truncadas)."""
    try:
        with Path(caminho).open("rb") as ficheiro:
            ficheiro.seek(0, os.SEEK_END)
            tamanho = ficheiro.tell()
            ficheiro.seek(max(0, tamanho - MAX_LEITURA))
            bruto = ficheiro.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    linhas: list[dict] = []
    for linha in bruto.splitlines():
        linha = linha.strip()
        if not linha.startswith("{"):
            continue                                # 1.ª linha pode estar cortada a meio: ignora-se
        try:
            amostra = json.loads(linha)
        except ValueError:
            continue                                # linha a meio de escrita: ignora, não inventa
        if isinstance(amostra, dict):
            linhas.append(amostra)
    return linhas[-n:]


def _mtime(caminho: Path) -> float:
    """`mtime` do ficheiro (ou agora, se não existir) — usado para a idade da telemetria."""
    try:
        return Path(caminho).stat().st_mtime
    except OSError:
        return time.time()


def resumo_telemetria(caminho: Path) -> dict:
    """Resumo do fim da telemetria: estado/ep/passo/retorno + o VENTO EM VIGOR da última amostra."""
    linhas = ultimas_linhas(caminho, MAX_LINHAS)
    if not linhas:
        return {"estado": "sem_dados", "ep": 0, "passo": 0, "retorno": 0.0, "linhas": 0, "t": None,
                "vento_vec": None, "vento_vel": None, "vento_azim": None, "vento_modo": None}
    ultima = linhas[-1]
    vec = ultima.get("vento_vec")
    return {"estado": str(ultima.get("estado", "sem_dados")), "ep": int(ultima.get("ep", 0) or 0),
            "passo": int(ultima.get("passo", 0) or 0), "retorno": float(ultima.get("retorno", 0.0) or 0.0),
            "linhas": len(linhas), "t": ultima.get("t"),
            "vento_vec": [float(v) for v in vec] if isinstance(vec, list) and len(vec) == 3 else None,
            "vento_vel": float(ultima.get("vento_vel", 0.0) or 0.0),
            "vento_azim": float(ultima.get("vento_azim", 0.0) or 0.0),
            "vento_modo": str(ultima.get("vento_modo", "nenhum") or "nenhum")}


def vento_do_controlo(controlo: dict) -> dict:
    """Bloco `vento_dinamico` do controlo em vigor (o que o site PEDIU): `{modo, params, ativo}`."""
    din = controlo.get("dinamico")
    if not isinstance(din, dict):
        return {"modo": "nenhum", "params": {}, "ativo": False}
    return {"modo": str(din.get("modo", "nenhum")), "params": din.get("params") or {},
            "ativo": bool(din.get("ativo", False))}


def vento_em_vigor(resumo: dict, controlo: dict) -> dict:
    """Vento que a FÍSICA leva agora: vector (vx,vy,vz) + polar + modo dinâmico em vigor.

    Vem da ÚLTIMA amostra da telemetria (é o `env.vento_vec`, incluindo rajadas/turbulência/frente); sem
    telemetria cai no vento BASE pedido no controlo, para a API nunca ficar sem resposta (e aí diz-se que a
    fonte é o controlo, não a física).
    """
    vec = resumo.get("vento_vec")
    din = vento_do_controlo(controlo)
    if vec is None:
        base = [float(controlo.get("vel", 0.0) or 0.0), float(controlo.get("azimute", 0.0) or 0.0),
                float(controlo.get("elevacao", 0.0) or 0.0)]
        if din["ativo"] and din["modo"] == "frente" and "vel" in din["params"]:
            # `frente` (a): degrau imediato do vento base — sem telemetria é ele que manda (um ficheiro
            # escrito à mão pode trazer só o bloco `dinamico`, sem subir o vento base ao topo).
            base = [float(din["params"]["vel"]), float(din["params"]["azimute"]), float(din["params"]["elevacao"])]
        vel, azimute, elevacao = base
        if not controlo.get("ativo", True) and not (din["ativo"] and din["modo"] == "frente"):
            vel = 0.0
        cos_e, az = math.cos(math.radians(elevacao)), math.radians(azimute)
        vec = [vel * cos_e * math.cos(az), vel * cos_e * math.sin(az), vel * math.sin(math.radians(elevacao))]
        return {"vec": [round(v, 6) for v in vec], "vel": round(vel, 6), "azimute": round(azimute % AZIM_MAX, 6),
                "elevacao": round(elevacao, 6), "modo": din["modo"] if din["ativo"] else "nenhum",
                "fonte": "controlo (sem telemetria)"}
    norma = math.sqrt(sum(v * v for v in vec))
    elevacao = 0.0 if norma == 0.0 else math.degrees(math.asin(max(-1.0, min(1.0, vec[2] / norma))))
    return {"vec": [round(v, 6) for v in vec], "vel": round(norma, 6),
            "azimute": round(math.degrees(math.atan2(vec[1], vec[0])) % AZIM_MAX, 6) if norma else 0.0,
            "elevacao": round(elevacao, 6), "modo": str(resumo.get("vento_modo") or "nenhum"),
            "fonte": "telemetria (runner)"}


# ------------------------------------------------------------------------------------ painel RPi 5
def _primeiro(*valores, predefinido=None):
    """Primeiro valor NÃO nulo de `valores` (tolerância a dois formatos de relatório do `deploy.py`)."""
    for valor in valores:
        if valor is not None:
            return valor
    return predefinido


def _numero_ou_nada(valor):
    """Número finito (int/float) ou `None` — o painel nunca mostra `NaN`."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor) if math.isfinite(float(valor)) else None


def ler_benchmark(caminho: Path | None = None) -> dict | None:
    """Relatório do `deploy.py` (JSON) — `None` se não existir/for ilegível.

    Aceita os DOIS formatos que o laboratório já produziu: o do template (`benchmark.p50/p99/max` em µs,
    `export.bytes`, `int8.benchmark`) e o do experimento 09 (`benchmark.p50_us`, `onnx.bytes`,
    `int8.fator_p50`). O `_caminho` fica no dict devolvido, para o painel poder dizer de onde veio.
    """
    candidatos = [Path(caminho)] if caminho is not None else list(BENCHMARKS)
    for alvo in candidatos:
        try:
            dados = json.loads(Path(alvo).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(dados, dict):
            return {**dados, "_caminho": str(alvo)}
    return None


def mesma_coisa(a, b) -> bool:
    """Os dois caminhos apontam para o MESMO ficheiro? Relativos são resolvidos contra a pasta do experimento
    E contra a raiz do repositório (a primeira base em que o ficheiro existe).

    O relatório do `deploy.py` grava o caminho do modelo relativo à pasta onde correu (`out/runs/...zip` no
    experimento, `experiments/<nome>/out/...` na raiz), não ao cwd de quem lê a API: sem isto,
    `modelo_coincide` dizia `false` para o mesmo modelo.
    """
    def resolver(caminho) -> Path:
        c = Path(str(caminho))
        if c.is_absolute():
            return c.resolve()
        candidatos = [_AQUI / c, _RAIZ / c]
        return next((x for x in candidatos if x.exists()), candidatos[0]).resolve()
    return resolver(a) == resolver(b)


def bloco_rpi5(bench: dict | None, decisoes_s: float, modelo_em_uso=None) -> dict:
    """Painel do computador de bordo: specs fixas do alvo + inferência medida + uso calculado AO VIVO.

    `uso.fracao_budget = p50_us · decisoes_s / 20 000` (decisões/s reais × latência ÷ período de 20 ms a
    50 Hz) e `pct_budget` é o mesmo em %; `pct_periodo` é o custo de UMA decisão (p50 ÷ 20 ms), que não vai a
    zero quando o episódio pára — é a barra honesta do painel. Sem relatório, `fonte = "sem benchmark"` e os
    campos de inferência vêm a `None`: o painel mostra "—" em vez de inventar tempos.
    `inferencia.modelo_coincide` diz se o modelo MEDIDO é o mesmo que o runner carregou (o painel estima o
    custo do que corre, não de outro `.zip`).
    """
    jitter, publicada = RPI5_SPECS["jitter_so"], RPI5_SPECS["inferencia_publicada"]
    uso = {"decisoes_s": round(float(decisoes_s), 3), "latencia_estimada_us": None, "fracao_budget": None,
           "pct_budget": None, "pct_cpu_equivalente": None, "nucleos_multi_ia": 1, "pct_periodo": None,
           "pct_periodo_publicado_cnn": round(100.0 * publicada["fp32_ms"] * 1000.0 / BUDGET_US, 3),
           "jitter_ms_standard": jitter["standard_ms_pior_caso"],
           "jitter_us_preempt_rt": jitter["preempt_rt_us_max"],
           "gargalo": "jitter do SO a 50 Hz (9,4 ms de pior caso num kernel standard) — a inferência da "
                      "nossa MLP usa uma fracção pequena do período de 20 ms",
           "nota": "p50 do benchmark × decisões/s medidas na telemetria ÷ 20 ms (50 Hz)"}
    if not bench:
        return {"specs": dict(RPI5_SPECS), "inferencia": None, "uso": uso, "hardware": None,
                "fonte": "sem benchmark", "benchmark": None}
    b = bench.get("benchmark") or {}
    export = bench.get("export") or {}
    onnx = bench.get("onnx") or {}
    int8 = bench.get("int8") or {}
    int8_bench = int8.get("benchmark") or {}
    multi = bench.get("multi") or {}
    p50 = _numero_ou_nada(_primeiro(b.get("p50_us"), b.get("p50")))
    p99 = _numero_ou_nada(_primeiro(b.get("p99_us"), b.get("p99")))
    pior = _numero_ou_nada(_primeiro(b.get("max_us"), b.get("max")))
    modelo = bench.get("modelo")
    modelo_medido = modelo.get("caminho") if isinstance(modelo, dict) else modelo
    # O fator int8 é SEMPRE medido (fp32/int8): o formato do 09 traz-no pronto, o do template calcula-se.
    fator_int8 = _numero_ou_nada(int8.get("fator_p50"))
    if fator_int8 is None and p50 and int8_bench.get("p50"):
        fator_int8 = p50 / float(int8_bench["p50"])
    # Inferências/s: medida no multi-IA, no benchmark, ou derivada de 1/p50 (diz-se qual, em `nota`).
    inferencias_s = _numero_ou_nada(_primeiro(b.get("inferencias_s"), multi.get("inferencias_por_s")))
    derivada = inferencias_s is None and p50
    if derivada:
        inferencias_s = 1e6 / p50
    cabe = _primeiro(b.get("cabe_50hz"), (p99 <= BUDGET_US) if p99 is not None else None)
    if p50 is not None:
        fracao = p50 * float(decisoes_s) / BUDGET_US
        uso.update({"latencia_estimada_us": round(p50, 3), "fracao_budget": round(fracao, 6),
                    "pct_budget": round(100.0 * fracao, 3),
                    "pct_cpu_equivalente": round(100.0 * fracao / NUCLEOS_SOC, 3),
                    "pct_periodo": round(100.0 * p50 / BUDGET_US, 4)})
    inferencia = {"p50_us": p50, "p99_us": p99, "max_us": pior,
                  "modelo_kb": round(_numero_ou_nada(_primeiro(onnx.get("bytes"), export.get("bytes"))) / 1024.0, 2)
                  if _primeiro(onnx.get("bytes"), export.get("bytes")) else None,
                  "int8_fator": round(fator_int8, 4) if fator_int8 else None,
                  "int8_kb": round(_numero_ou_nada(int8.get("bytes")) / 1024.0, 2) if int8.get("bytes") else None,
                  "int8_reducao_tamanho": _numero_ou_nada(_primeiro(int8.get("reducao_tamanho"),
                                                                    int8.get("razao_tamanho"))),
                  "inferencias_s": round(inferencias_s, 1) if inferencias_s else None,
                  "inferencias_s_derivada": bool(derivada),
                  "threads": b.get("threads"), "n": b.get("n"), "cabe_50hz": cabe,
                  "modelo": modelo_medido, "modelo_coincide": None,
                  "json": bench.get("_caminho"), "gerado_em": bench.get("gerado_em"),
                  "cpu_benchmark": bench.get("cpu"), "veredicto": b.get("veredicto"),
                  "ops": (bench.get("export") or {}).get("ops"), "n_proc_multi": multi.get("n_proc"),
                  "estouros_20ms": multi.get("estouros_20ms_totais")}
    if modelo_em_uso is not None and modelo_medido:
        inferencia["modelo_coincide"] = mesma_coisa(modelo_medido, modelo_em_uso)
    fonte = bench.get("fonte") or ("benchmark do deploy.py nesta máquina (proxy x86 de 1 core A76; não é o RPi)"
                                   + ("" if not derivada else " · inferências/s derivadas de 1/p50"))
    return {"specs": dict(RPI5_SPECS), "inferencia": inferencia, "uso": uso, "hardware": None,
            "fonte": fonte, "benchmark": bench.get("_caminho")}


# ---------------------------------------------------------------------------------------------- validação
def _numero_finito(dados: dict, campo: str) -> float | None:
    """Campo numérico finito do POST; `None` se ausente. `ValueError` se não for número finito (NaN/inf)."""
    if campo not in dados or dados[campo] is None:
        return None
    valor = dados[campo]
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(float(valor)):
        raise ValueError(f"`{campo}` tem de ser um número finito (recebido {valor!r})")
    return float(valor)


def validar_vento(dados, atual: dict) -> dict:
    """`POST /api/vento` → controlo novo (vel/azimute/elevacao validados; o resto do ficheiro fica igual).

    Qualquer subconjunto dos três pode vir no corpo; o que não vem mantém o valor em vigor. `ativo` é
    opcional (por omissão liga-se quando `vel > 0` e desliga-se com `vel == 0`) — é o que faz `{"vel": 0}`
    ser "parar o vento" sem precisar de um campo extra.
    """
    if not isinstance(dados, dict):
        raise ValueError("o corpo tem de ser um objeto JSON")  # noqa: TRY004
    novos = {}
    for campo in ("vel", "azimute", "elevacao"):
        valor = _numero_finito(dados, campo)
        if valor is None:
            continue
        lo, hi = FAIXAS[campo]
        if not lo <= valor <= hi:
            raise ValueError(f"`{campo}` tem de estar em [{lo}, {hi}] (recebido {valor!r})")
        novos[campo] = valor
    if not novos:
        raise ValueError("indique pelo menos um de `vel`, `azimute` ou `elevacao`")
    vel = float(novos.get("vel", atual.get("vel", 0.0)))
    ativo = dados.get("ativo")
    if ativo is not None and not isinstance(ativo, bool):
        raise ValueError(f"`ativo` tem de ser booleano (recebido {ativo!r})")
    return {**atual, **novos, "ativo": (vel > 0.0) if ativo is None else ativo}


def _validador_env(nome: str | None = None):
    """`valida_vento_dinamico` do módulo do PROJETO, importado à primeira utilização (`None` se não existir).

    Importar o módulo do projeto puxa o MuJoCo para o processo do SITE: é o preço de validar os modos dinâmicos
    com as MESMAS regras do treino/runner, em vez de duplicar faixas aqui (uma divergência daria 200 na API e um
    aviso no runner). Só acontece quando alguém usa o vento dinâmico; sem ele o site nunca importa MuJoCo.
    Um projeto SEM essa função continua a funcionar: a validação é então ESTRUTURAL (ver `_valida_estrutural`).
    """
    global _VALIDADOR_ENV
    if _VALIDADOR_ENV is None:
        try:
            modulo = importlib.import_module(nome or _MODULO_ENV[0])
            _VALIDADOR_ENV = getattr(modulo, "valida_vento_dinamico", False)
        except ImportError:
            _VALIDADOR_ENV = False
    return _VALIDADOR_ENV or None


def _valida_estrutural(config: dict | None) -> dict | None:
    """Validação de RECURSO quando o projeto não tem `valida_vento_dinamico` (modos do CONTRATO + números).

    Aceita os modos `rajadas`/`frente`/`dryden` com os params numéricos finitos conhecidos e recusa chaves
    desconhecidas — a mesma mensagem clara do validador do `env.py`, sem depender dele. Quem aplica e volta a
    validar é o RUNNER (`env.definir_vento_dinamico`), portanto isto é só a porta de entrada da API.
    """
    if config is None:
        return None
    if not isinstance(config, dict) or "modo" not in config:
        raise ValueError(f"`vento_dinamico` precisa de `modo`, um de {list(MODOS_DINAMICOS_ENV)} (recebido {config!r})")
    modo = config["modo"]
    if modo not in MODOS_DINAMICOS_ENV:
        raise ValueError(f"`modo` tem de ser um de {list(MODOS_DINAMICOS_ENV)} (recebido {modo!r})")
    chaves = {"modo", "u_max", "p", "duracao", "t_s", "sigma", "L", "v_min"}
    desconhecidas = set(config) - chaves
    if desconhecidas:
        raise ValueError(f"`params` tem chaves desconhecidas {sorted(desconhecidas)} — aceita {sorted(chaves)}")
    limpos: dict = {"modo": modo}
    for campo, valor in config.items():
        if campo == "modo":
            continue
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(float(valor)):
            raise ValueError(f"`params.{campo}` tem de ser um número finito (recebido {valor!r})")
        limpos[campo] = float(valor)
    limpos.setdefault("u_max", 3.0)
    if float(limpos["u_max"]) < 0.0:
        raise ValueError(f"`params.u_max` tem de ser ≥ 0 m/s (recebido {limpos['u_max']!r}): 0 = modo inerte")
    return limpos


def _params_rajada_agora(params: dict) -> dict:
    """Params da rajada one-shot: `u` [0, 5] m/s, `azimute` [0, 360)°, `elevacao` ±90°, `duracao` ≥ 1.

    Gémea da do `sim_view.py` (o runner valida outra vez ao aplicar; aqui serve para o 400 da API).
    """
    desconhecidas = set(params) - {"u", "azimute", "elevacao", "duracao"}
    if desconhecidas:
        raise ValueError(f"`params` (rajada_agora) tem chaves desconhecidas {sorted(desconhecidas)} — aceita "
                         "['azimute', 'duracao', 'elevacao', 'u']")
    u = _numero_finito(params, "u")
    u = RAJADA_U_PADRAO if u is None else u
    if not 0.0 <= u <= RAJADA_U_MAX:
        raise ValueError(f"`params.u` tem de estar em [0, {RAJADA_U_MAX}] m/s (recebido {u!r})")
    saida = {"u": u}
    for campo in ("azimute", "elevacao"):
        valor = _numero_finito(params, campo)
        valor = 0.0 if valor is None else valor
        lo, hi = FAIXAS[campo]
        if not lo <= valor <= hi:
            raise ValueError(f"`params.{campo}` tem de estar em [{lo}, {hi}] (recebido {valor!r})")
        saida[campo] = valor % AZIM_MAX if campo == "azimute" else valor
    duracao = params.get("duracao", RAJADA_DURACAO_PADRAO)
    if isinstance(duracao, bool) or not isinstance(duracao, int) or int(duracao) < 1:
        raise ValueError(f"`params.duracao` tem de ser um inteiro ≥ 1 passos de decisão (recebido {duracao!r})")
    saida["duracao"] = int(duracao)
    return saida


def _params_frente(params: dict, atual: dict) -> tuple[dict, dict | None]:
    """Params do modo `frente` → `(params, vento_base_novo|None)`: aceita os DOIS formatos do contrato.

    · formato (a) `{"vel", "azimute", "elevacao"}` → degrau IMEDIATO do vento base: validado com as MESMAS
      faixas do `POST /api/vento` e devolvido também como vento BASE do controlo (`vel`/`azimute`/`elevacao`/
      `ativo`) — assim o site, o ficheiro e a física dizem o mesmo, e o degrau é o vento que fica depois de um
      `nenhum`. Campo ausente mantém o valor em vigor (como no `/api/vento`), para `{"azimute": 270}` ser só
      uma viragem; NÃO passa pelo validador do env (que espera `u_max`/`t_s` e recusaria estas chaves);
    · formato (b) `{"u_max", "t_s"}` (ou sem params) → modo em curso do env: quem valida é o `env.py`.
    Chaves desconhecidas ou mistura dos dois formatos → `ValueError` (o POST responde 400). O `"modo"` lá
    dentro é tolerado quando diz "frente": é o que o `env.valida_vento_dinamico` devolve e o site guarda, e o
    frontend pode reenviar os params lidos do `/api/sim` tal e qual (ida-e-volta).
    """
    limpos = dict(params)
    if limpos.get("modo") == "frente":
        limpos.pop("modo")
    desconhecidas = set(limpos) - set(FRENTE_BASE) - set(FRENTE_ENV)
    if desconhecidas:
        raise ValueError(f"`params` (frente) tem chaves desconhecidas {sorted(desconhecidas)} — aceita "
                         f"{list(FRENTE_BASE)} (degrau imediato do vento base) ou {list(FRENTE_ENV)} "
                         "(modo em curso do env)")
    da_base = [campo for campo in FRENTE_BASE if campo in limpos]
    do_env = [campo for campo in FRENTE_ENV if campo in limpos]
    if da_base and do_env:
        raise ValueError(f"`params` (frente) não pode misturar os dois formatos: {da_base} são um degrau "
                         f"imediato do vento base e {do_env} o modo em curso do env")
    if not da_base:
        return dict(params), None                        # (b): sem params = defaults do env
    novos = {}
    for campo in FRENTE_BASE:
        valor = _numero_finito(limpos, campo)
        if valor is None:
            valor = float(atual.get(campo, 0.0) or 0.0)  # ausente = mantém o vento base em vigor
        lo, hi = FAIXAS[campo]
        if not lo <= valor <= hi:
            raise ValueError(f"`params.{campo}` tem de estar em [{lo}, {hi}] (recebido {valor!r})")
        novos[campo] = valor
    return novos, {**novos, "ativo": novos["vel"] > 0.0}


def validar_vento_dinamico(dados, atual: dict) -> dict:
    """`POST /api/vento-dinamico` → controlo novo, com o bloco `dinamico` validado (`ValueError` → 400).

    Os modos do env (`rajadas`/`dryden`, e o `frente` do formato (b)) passam pelo `valida_vento_dinamico` do
    PRÓPRIO `env.py` (params normalizados com os defaults do treino); o `frente` do formato (a) é um degrau
    imediato do vento base e é validado aqui (as faixas do `/api/vento`), escrevendo também o vento BASE do
    controlo; o `rajada_agora` (one-shot dirigido, que o env não tem) é validado aqui; `nenhum` não leva
    params. O `seq` é incrementado a CADA pedido: é o que permite disparar duas rajadas iguais seguidas (o
    runner só (re)age quando a ASSINATURA do bloco muda).
    """
    if not isinstance(dados, dict):
        raise ValueError("o corpo tem de ser um objeto JSON")  # noqa: TRY004
    modo = dados.get("modo")
    if modo is None:
        raise ValueError(f"indique `modo`, um de {list(MODOS_DINAMICOS)}")
    if modo not in MODOS_DINAMICOS:
        raise ValueError(f"`modo` tem de ser um de {list(MODOS_DINAMICOS)} (recebido {modo!r})")
    params = dados.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("`params` tem de ser um objeto JSON")  # noqa: TRY004
    ativo = dados.get("ativo", modo != "nenhum")
    if not isinstance(ativo, bool):
        raise ValueError(f"`ativo` tem de ser booleano (recebido {ativo!r})")  # noqa: TRY004 (→ 400)
    validador = _validador_env() or _valida_estrutural     # o do projeto, ou o estrutural de recurso
    base_novo = None
    if modo == "frente":                                 # 2 formatos: degrau imediato OU modo do env
        params, base_novo = _params_frente(params, atual)
        if base_novo is None:                            # formato (b): quem valida é o `env.py`
            params = validador({"modo": modo, **params}) or {}
    elif modo in MODOS_DINAMICOS_ENV:
        params = validador({"modo": modo, **params}) or {}
    elif modo == "rajada_agora":
        params = _params_rajada_agora(params)
    else:
        params = {}
    anterior = atual.get("dinamico")
    seq = int(anterior.get("seq", 0) or 0) + 1 if isinstance(anterior, dict) else 1
    novo = {**atual, "dinamico": {"modo": modo, "params": params, "ativo": bool(ativo), "seq": seq}}
    if base_novo is not None:
        novo.update(base_novo)                           # o degrau do `frente` passa a ser o vento base
    return novo


def porta_livre(host: str, porta: int, tentativas: int = 20) -> int:
    """Primeira porta livre a partir de `porta` (0 = o sistema escolhe) — evita o "porta ocupada" no arranque."""
    if porta == 0:
        with socket.socket() as s:
            s.bind((host, 0))
            return int(s.getsockname()[1])
    for p in range(porta, porta + tentativas):
        with socket.socket() as s:
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    raise SystemExit(f"Erro: nenhuma porta livre em {host}:{porta}–{porta + tentativas} — Solução: use --port 0")


# ---------------------------------------------------------------------------------------------- servidor
class Servidor:
    """Estado do servidor: caminhos, processo do runner, modelo em uso e métricas de sessão."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.controlo = _absoluto(args.controlo)
        self.telemetria = _absoluto(args.telemetria)
        self.dist = SITE_DIST
        self.modelo = Path(args.model) if args.model else None
        self.modelo_nome = self.modelo.name if self.modelo else "trim (sem política)"
        self.modelo_motivo = "política indicada em --model" if self.modelo else "sem --model: ação nula (ctrl = τ_trim)"
        self.runner: subprocess.Popen | None = None
        self.t_inicio = time.time()
        self.verboso = bool(args.verboso)
        self.porta = 0
        self._lock = threading.Lock()
        self._ritmo = {"t": None, "passo": None, "valor": 0.0}      # decisões/s medidas entre pedidos
        self._bench = {"t": 0.0, "dados": None}                     # cache do relatório do deploy.py

    # ------------------------------------------------------------------ runner
    def arrancar_runner(self) -> None:
        """Arranca o `sim_view.py` como subprocesso (mesmo interpretador) e devolve já o controlo."""
        cmd = [sys.executable, str(RUNNER), "--controlo", str(self.controlo), "--telemetria", str(self.telemetria),
               "--fator-tempo", str(self.args.fator_tempo), "--seed", str(self.args.seed)]
        if self.args.sem_janela:
            cmd.append("--sem-janela")
        if self.args.model:
            cmd += ["--model", str(self.args.model)]
        if self.args.loop:
            cmd.append("--loop")
        if not self.controlo.exists():
            escrever_controlo(self.controlo, {"loop": bool(self.args.loop)})
        print(f"[site] runner: {' '.join(cmd[1:])}", flush=True)
        self.runner = subprocess.Popen(cmd, cwd=str(_AQUI))

    def runner_vivo(self) -> bool:
        return self.runner is not None and self.runner.poll() is None

    def parar_runner(self) -> None:
        """Termina o runner (SIGTERM → espera 5 s → SIGKILL): sem processos órfãos ao fechar o servidor."""
        if self.runner is None or self.runner.poll() is not None:
            return
        self.runner.terminate()
        try:
            self.runner.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self.runner.kill()
        print("[site] runner terminado", flush=True)

    # ------------------------------------------------------------------ painel RPi 5
    def medir_ritmo(self, passo: int) -> float:
        """Decisões/s REAIS medidas na telemetria: Δpasso / Δtempo-de-parede entre pedidos (EMA 0,3).

        O painel faz polling ao `/api/state`, logo cada pedido dá uma amostra; com o episódio parado o Δpasso
        é 0 e a taxa cai para 0 (é a verdade: não há decisões). Sem duas amostras ainda → 0.
        """
        agora, amostra = time.time(), self._ritmo
        valor = amostra["valor"]
        if amostra["t"] is not None and agora - amostra["t"] >= 0.2:
            delta_t = agora - amostra["t"]
            taxa = (int(passo) - int(amostra["passo"])) / delta_t if delta_t > 0 else 0.0
            valor = taxa if amostra["valor"] == 0.0 else 0.7 * amostra["valor"] + 0.3 * max(0.0, taxa)
        amostra.update({"t": agora, "passo": int(passo), "valor": valor})
        return valor

    def benchmark(self, max_idade: float = 5.0) -> dict | None:
        """Relatório do `deploy.py` (cache de `max_idade` s: o painel não relê o JSON a cada pedido)."""
        agora = time.time()
        if self._bench["dados"] is None or agora - self._bench["t"] >= max_idade:
            self._bench = {"t": agora, "dados": ler_benchmark(self.args.benchmark)}
        return self._bench["dados"]

    # ------------------------------------------------------------------ leituras/escritas do contrato
    def estado_atual(self) -> dict:
        """Resumo do estado (sem `linhas`): contrato do site + vento dinâmico + painel do RPi 5."""
        resumo = resumo_telemetria(self.telemetria)
        controlo = ler_controlo(self.controlo)
        em_vigor = vento_em_vigor(resumo, controlo)
        return {
            "estado": resumo["estado"],
            "ep": resumo["ep"],
            "passo": resumo["passo"],
            "retorno": resumo["retorno"],
            # `vento` = o que o site PEDIU (o topo do ficheiro de controlo) + o vector/modo em vigor, para o
            # site só precisar de uma chave para desenhar a rosa dos ventos e os selos.
            "vento": {"vel": controlo["vel"], "azimute": controlo["azimute"], "elevacao": controlo["elevacao"],
                      "ativo": bool(controlo["ativo"]), "vec": em_vigor["vec"], "modo": em_vigor["modo"]},
            "vento_dinamico": vento_do_controlo(controlo),
            "vento_atual": em_vigor,
            "vento_em_vigor": {"vel": em_vigor["vel"], "azimute": em_vigor["azimute"]},
            "rpi5": bloco_rpi5(self.benchmark(), self.medir_ritmo(resumo["passo"]), self.modelo),
            "contador_reiniciar": int(controlo["reiniciar"]),
            "loop": bool(controlo["loop"]),
            "modelo": str(self.modelo) if self.modelo else None,
            "modelo_nome": self.modelo_nome,
            "modelo_motivo": self.modelo_motivo,
            "sim_vivo": self.runner_vivo(),
            "pid": None if self.runner is None else self.runner.pid,
            "porta": self.porta,
            "controlo": str(self.controlo),
            "telemetria": str(self.telemetria),
            "n_linhas": resumo["linhas"],
            "amostras": resumo["linhas"],
            "idade_telemetria_s": round(time.time() - _mtime(self.telemetria), 3),
            "site_pronto": INDEX.is_file(),
            "ups": round((time.time() - self.t_inicio), 1),
        }

    def definir_vento(self, corpo: dict) -> dict:
        """`POST /api/vento`: valida as faixas, MESCLA com o controlo atual e escreve-o de forma atómica."""
        atual = ler_controlo(self.controlo)
        atual = validar_vento(corpo, atual)
        escrever_controlo(self.controlo, atual)
        return {"vento": {"vel": atual["vel"], "azimute": atual["azimute"], "elevacao": atual["elevacao"],
                          "ativo": atual["ativo"]}}

    def definir_vento_dinamico(self, corpo: dict) -> dict:
        """`POST /api/vento-dinamico`: valida o bloco `dinamico` e escreve-o (SEM reiniciar o episódio)."""
        atual = ler_controlo(self.controlo)
        atual = validar_vento_dinamico(corpo, atual)
        escrever_controlo(self.controlo, atual)
        bloco = atual["dinamico"]
        print(f"[site] vento dinâmico → {bloco['modo']} (seq {bloco['seq']}, ativo {bloco['ativo']})", flush=True)
        return {"vento_dinamico": vento_do_controlo(atual)}

    def reiniciar(self) -> dict:
        """`POST /api/reiniciar`: o CONTADOR é o mecanismo (o runner vê o valor novo e faz `env.reset()`)."""
        atual = ler_controlo(self.controlo)
        atual["reiniciar"] = int(atual["reiniciar"]) + 1
        escrever_controlo(self.controlo, atual)
        print(f"[site] REINICIAR → contador {atual['reiniciar']}", flush=True)
        return {"contador": atual["reiniciar"]}

    def definir_loop(self, corpo: dict) -> dict:
        """`POST /api/loop`: liga/desliga o auto-reset no fim do episódio (por omissão está OFF)."""
        if not isinstance(corpo, dict) or "ativo" not in corpo:
            raise ValueError('esperava {"ativo": bool}')
        if not isinstance(corpo["ativo"], bool):
            raise TypeError(f"`ativo` tem de ser booleano (recebido {corpo['ativo']!r})")
        atual = ler_controlo(self.controlo)
        atual["loop"] = corpo["ativo"]
        escrever_controlo(self.controlo, atual)
        print(f"[site] LOOP {'ligado' if corpo['ativo'] else 'desligado'}", flush=True)
        return {"loop": atual["loop"]}


# ---------------------------------------------------------------------------------------------- HTTP
def _pagina_sem_site(motivo: str) -> bytes:
    """Página honesta quando o `dist/` não existe: diz o comando exato que falta (não finge um site)."""
    return f"""<!doctype html><html lang="pt"><head><meta charset="utf-8"><title>site por construir</title>
<style>body{{background:#0e1420;color:#e6ebf5;font:16px/1.6 ui-monospace,monospace;margin:8vh auto;max-width:60rem;padding:0 2rem}}
code{{background:#1b2536;padding:.2rem .4rem;border-radius:.3rem}}h1{{color:#ffa24a}}</style></head><body>
<h1>O site ainda não está construído</h1>
<p>{motivo}</p>
<p>A API (6 rotas) está a funcionar: <code>GET /api/sim</code>, <code>GET /api/state</code>,
<code>POST /api/vento</code>, <code>POST /api/vento-dinamico</code>, <code>POST /api/reiniciar</code>,
<code>POST /api/loop</code>.</p>
<pre>cd site
source ~/.secrets      # MOTION_TOKEN do registry @motionplus (ver .npmrc)
node ensure-setup.mjs  # instala o que falta
npm run build          # gera dist/ que este servidor serve</pre>
<p>Passo a passo completo: <code>site/LEIAME.md</code>.</p></body></html>""".encode()


class Handler(BaseHTTPRequestHandler):
    """Handler HTTP: 6 rotas de API + ficheiros do `site/dist/` (SPA). Estado no `Servidor` injetado."""

    server_version = "lab-padrao-sim-site/1.0"
    servidor: Servidor            # injetado por `criar_handler` (o BaseHTTPRequestHandler não aceita __init__ extra)

    # ------------------------------------------------------------------ respostas
    def _responde(self, corpo: bytes, tipo: str = "application/json", codigo: int = 200) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def _json(self, obj: Any, codigo: int = 200) -> None:
        self._responde(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode(), "application/json", codigo)

    def _erro(self, codigo: int, mensagem: str) -> None:
        self._json({"erro": mensagem, "codigo": codigo}, codigo)

    def log_message(self, formato: str, *args) -> None:      # ruído do BaseHTTPRequestHandler
        if self.servidor.verboso:
            print(f"[site] {self.address_string()} {formato % args}", flush=True)

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:                                 # assinatura do BaseHTTPRequestHandler
        rota = self.path.split("?", 1)[0]
        try:
            if rota == "/api/sim":
                estado = self.servidor.estado_atual()
                estado["linhas"] = ultimas_linhas(self.servidor.telemetria)
                self._json(estado)
            elif rota == "/api/state":
                self._json(self.servidor.estado_atual())
            elif rota.startswith("/api/"):
                self._erro(404, f"rota desconhecida: {rota}")
            else:
                self._estatico(rota)
        except Exception as erro:                             # noqa: BLE001 — a API nunca derruba o servidor
            self._erro(500, f"erro interno: {erro!r}")

    def do_HEAD(self) -> None:
        self.do_GET()

    def _estatico(self, rota: str) -> None:
        """Serve `site/dist/<rota>`; sem `dist/` devolve a página de instruções; rotas do SPA caem no index."""
        caminho = urllib.parse.unquote(rota)
        relativo = Path(caminho.lstrip("/") or "index.html")
        if ".." in relativo.parts:
            self._erro(404, f"caminho inválido: {rota}")      # traversal: 404 explícito, nunca sai da pasta
            return
        if not self.servidor.dist.is_dir():
            self._responde(_pagina_sem_site(f"pasta esperada: {self.servidor.dist}"), "text/html; charset=utf-8", 200)
            return
        alvo = self.servidor.dist / relativo
        if not alvo.is_file():
            if relativo.suffix and relativo.suffix not in (".html",):
                self._erro(404, f"asset não encontrado: {rota}")
                return
            alvo = self.servidor.dist / "index.html"          # rotas do site (SPA)
        try:
            corpo = alvo.read_bytes()
        except OSError as erro:
            self._erro(404, f"não consegui ler {alvo.name}: {erro}")
            return
        self._responde(corpo, TIPOS.get(alvo.suffix, "application/octet-stream"))

    # ------------------------------------------------------------------ POST
    def do_POST(self) -> None:                                # assinatura do BaseHTTPRequestHandler
        rota = self.path.split("?", 1)[0]
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho > MAX_CORPO:
                self._erro(400, f"corpo demasiado grande (limite {MAX_CORPO} bytes)")
                return
            bruto = self.rfile.read(tamanho) if tamanho else b"{}"
            try:
                corpo = json.loads(bruto.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError) as erro:
                self._erro(400, f"JSON inválido: {erro}")
                return
            if rota == "/api/vento":
                self._json(self.servidor.definir_vento(corpo))
            elif rota == "/api/vento-dinamico":
                self._json(self.servidor.definir_vento_dinamico(corpo))
            elif rota == "/api/reiniciar":
                self._json(self.servidor.reiniciar())
            elif rota == "/api/loop":
                self._json(self.servidor.definir_loop(corpo))
            else:
                self._erro(404, f"rota desconhecida: {rota}")
        except (ValueError, TypeError) as erro:               # valor/faixa/tipo inválido → 400 (estado honesto)
            self._erro(400, str(erro))
        except Exception as erro:                             # noqa: BLE001
            self._erro(500, f"erro interno: {erro!r}")


def criar_handler(servidor: Servidor):
    """Classe de handler já com o estado do servidor ligado (o `BaseHTTPRequestHandler` não tem `__init__` extra)."""
    return type("HandlerLigado", (Handler,), {"servidor": servidor})


# ---------------------------------------------------------------------------------------------- CLI
def analisar_argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="UM comando: arranca o runner (`sim_view.py`), o servidor do site e a API JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("API: GET /api/sim · GET /api/state · POST /api/vento {vel,azimute,elevacao} ·\n"
                "     POST /api/vento-dinamico {modo,params,ativo} · POST /api/reiniciar · POST /api/loop {\"ativo\": bool}\n"
                "Painel do computador de bordo (Raspberry Pi 5): alimentado pelo relatório do deploy.py.\n"
                "Pré-requisito do site: cd site && npm install && npm run build (ver site/LEIAME.md)."))
    p.add_argument("--model", type=Path, default=None, metavar="CAMINHO.zip",
                   help="política PPO (Stable-Baselines3) a pilotar; sem isto a ação é nula (ctrl = τ_trim)")
    p.add_argument("--sem-janela", action="store_true",
                   help="NÃO abre a janela 3D: só site + API + telemetria (validação sem janelas)")
    p.add_argument("--port", type=int, default=8080, metavar="PORTA",
                   help="porta do site (padrão 8080; se estiver ocupada tenta a seguinte; 0 = livre)")
    p.add_argument("--host", default="127.0.0.1", help="interface de escuta (padrão 127.0.0.1: só a tua máquina)")
    p.add_argument("--controlo", type=Path, default=CONTROLO_OMISSAO, metavar="CAMINHO",
                   help="ficheiro de controlo JSON (vento/vento dinâmico/REINICIAR/LOOP)")
    p.add_argument("--telemetria", type=Path, default=TELEMETRIA_OMISSAO, metavar="CAMINHO",
                   help="ficheiro JSONL da telemetria que o site lê por polling")
    p.add_argument("--benchmark", type=Path, default=None, metavar="CAMINHO.json",
                   help="relatório do deploy.py para o painel RPi 5 (padrão: out/deploy_report.json, "
                        "senão out/deploy/deploy.json)")
    p.add_argument("--env-modulo", default="env", metavar="NOME",
                   help="módulo do PROJETO para validar o vento dinâmico (padrão: env) — ver CONTRATOS.md")
    p.add_argument("--fator-tempo", type=float, default=1.0, metavar="F",
                   help="ritmo do runner: 1 = tempo real (padrão), 0,5 = metade, 2 = dobro, 0 = sem travão")
    p.add_argument("--seed", type=int, default=0, help="semente do reset (o episódio N usa seed+N)")
    p.add_argument("--loop", action="store_true", help="arranca o runner com auto-reset no fim do episódio")
    p.add_argument("--sem-browser", action="store_true", help="não abre o browser (o URL sai na mesma)")
    p.add_argument("--verboso", action="store_true", help="mostra cada pedido HTTP no terminal")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = analisar_argumentos(argv)
    _MODULO_ENV[0] = str(args.env_modulo)
    if not RUNNER.exists():
        print(f"Erro: runner não encontrado: {RUNNER} — Solução: corre a partir do experimento (pasta com sim_view.py)",
              file=sys.stderr)
        return 1
    porta = porta_livre(args.host, args.port)
    servidor = Servidor(args)
    servidor.porta = porta
    httpd = ThreadingHTTPServer((args.host, porta), criar_handler(servidor))
    httpd.daemon_threads = True
    url = f"http://{args.host}:{porta}/"
    print(f"[site] site em {url}", flush=True)
    if not SITE_DIST.is_dir():
        print(f"[site] aviso: {SITE_DIST} não existe — o site mostra as instruções de build "
              f"(cd site && npm install && npm run build; ver site/LEIAME.md)", flush=True)
    if servidor.benchmark() is None:
        print("[site] painel RPi 5 sem benchmark: corre o deploy.py (gera out/deploy_report.json) ou passa "
              "--benchmark CAMINHO.json", flush=True)
    servidor.arrancar_runner()

    def fechar(*_args) -> None:
        print("\n[site] a fechar: servidor + runner", flush=True)
        servidor.parar_runner()
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, fechar)
    signal.signal(signal.SIGTERM, fechar)
    if not args.sem_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        servidor.parar_runner()
    return 0


if __name__ == "__main__":
    sys.exit(main())
