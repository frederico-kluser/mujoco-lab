#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/sim_site.py — UM COMANDO: janela MuJoCo limpa + site com métricas e controlos.

Arranca tudo o que o dono precisa numa só linha:

  1. `sim_view.py` como SUBPROCESSO (o seu próprio grupo de processos; SIGTERM/SIGKILL limpos no fim) — é ele
     que abre a janela 100% limpa (só o 3D) e escreve a telemetria;
  2. um servidor HTTP local (só stdlib, `ThreadingHTTPServer`) que serve o SITE (`site/dist/`, com os assets
     em `/assets/...`) e a API que o site consome;
  3. o URL no terminal e o browser aberto (`xdg-open`; `--sem-browser` desliga).

    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py                 # 1 comando
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py --sem-janela     # só site + API
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py --port 0         # porta livre

API (JSON; todas as escritas são ATÓMICAS: tmp + `os.replace` no ficheiro de controlo):
  · `GET  /`                      → `site/dist/index.html` (ou a mensagem "corra npm run build em site/");
                                    qualquer caminho que não seja ficheiro cai no index (rotas do site);
  · `GET  /assets/...`            → ficheiros de `site/dist/` (sem sair da pasta: path traversal é 404);
  · `GET  /api/sim`               → `{"estado","ep","passo","retorno","vento":{...},"linhas":[…]}` com as
                                    ≤200 últimas amostras da telemetria (objetos JSON, já parseados), mais
                                    `modelo`/`modelo_nome`, `vento_dinamico` (o que foi pedido) e
                                    `vento_atual` (vetor vx,vy,vz + polar + modo, lido da telemetria);
  · `GET  /api/state`             → resumo (acima + `modelo`/`modelo_nome`/`modelo_motivo`, `sim_vivo`,
                                    `pid`, `porta`, caminhos, nº de amostras, idade da última amostra) e o
                                    painel `rpi5` (specs oficiais citadas + inferência medida no proxy +
                                    uso ao vivo: decisoes/s da telemetria × p50 ÷ 20 ms);
  · `POST /api/vento-dinamico`    → `{"modo": "nenhum"|"rajadas"|"frente"|"dryden"|"rajada_agora",
                                    "params": {...}, "ativo": bool}` — vento DINÂMICO ao vivo, SEM reiniciar
                                    o episódio. `rajadas`/`dryden` (e o `frente` do formato (b)) são
                                    validados pelo próprio `env.py` (`ValueError` → 400); o `frente` aceita
                                    ainda o formato (a) `params = {vel, azimute, elevacao}` = degrau
                                    IMEDIATO do vento base (validado aqui com as faixas do `POST /api/vento`
                                    e escrito também no topo do controlo); `rajada_agora` é uma rajada
                                    dirigida one-shot (`u`, `azimute`, `elevacao`, `duracao`);
                                    `nenhum`/`ativo:false` desliga;
  · `POST /api/vento`             → `{"vel","azimute","elevacao"}` (qualquer subconjunto; faixas 0-5 m/s,
                                    0-360°, −90..90°; NaN/inf → 400) e escreve o controlo;
  · `POST /api/reiniciar`         → incrementa `reiniciar` no controlo → `{"contador": n}` (é o ÚNICO
                                    caminho para recomeçar o episódio: o runner não tem auto-loop);
  · `POST /api/loop`              → `{"ativo": bool}` liga/desliga o auto-reset no fim do episódio.

O ficheiro de controlo (o site escreve, o runner lê a cada passo de decisão) e a telemetria (o runner
escreve, o site lê) estão descritos no cabeçalho do `sim_view.py` — este processo só os toca para os criar
(se faltarem) e para responder aos POSTs.
"""
from __future__ import annotations

import argparse
import json
import math
import mimetypes
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_RAIZ), str(_AQUI)]      # para o `env.valida_vento_dinamico` (importado só quando usado)
SIM_VIEW = _AQUI / "sim_view.py"
DIST = _AQUI / "site" / "dist"
INDEX = DIST / "index.html"
CONTROLO_OMISSAO = _AQUI / "out" / "controle_vento.json"
TELEMETRIA_OMISSAO = _AQUI / "out" / "sim_telemetria.jsonl"

VEL_MAX, AZIM_MAX, ELEV_MAX = 5.0, 360.0, 90.0     # faixas do contrato (as mesmas do sim_view.py)
MODOS_DINAMICOS = ("nenhum", "rajadas", "frente", "dryden", "rajada_agora")   # modos do vento ao vivo
MODOS_DINAMICOS_ENV = ("rajadas", "frente", "dryden")   # os que o `env.definir_vento_dinamico` conhece
FRENTE_BASE, FRENTE_ENV = ("vel", "azimute", "elevacao"), ("u_max", "t_s")   # os 2 formatos do `frente`
RAJADA_DURACAO_PADRAO = 25        # passos de decisão — duração da rajada one-shot
RAJADA_U_PADRAO = 3.0             # m/s — amplitude da rajada one-shot sem `u` nos params
RAJADA_U_MAX = 5.0                # m/s — teto do contrato para a rajada one-shot
# painel RPi 5: o relatório do `deploy.py` (proxy x86 de 1 core do A76) fica AQUI e é lido a cada pedido
BENCHMARK_OMISSAO = _AQUI / "out" / "deploy_r10" / "deploy.json"
BUDGET_US = 20_000.0              # 50 Hz = 20 ms (o `periodo_us` do deploy.py)
NUCLEOS_SOC = 4                   # 4x Cortex-A76 no BCM2712
RPI5_SPECS = {
    "soc": "Broadcom BCM2712",
    "cpu": "4x Cortex-A76 @ 2,4 GHz (512 kB L2/nucleo + 2 MB L3)",
    "ram": "LPDDR4X-4267, 1-16 GB (variante)",
    "gpu": "VideoCore VII",
    "alimentacao": "5 V / 5 A (27 W); pico ~12 W",
    "throttle": "termico 80 -> 85 graus C (corte de 2,4 -> 1,5 GHz)",
    "alvo_hz": 50,
    "budget_ms": 20,
    "nucleos": NUCLEOS_SOC,
    "jitter_so": {"standard_ms_pior_caso": 9.4, "preempt_rt_us_max": 225,
                  "nota": "o jitter do SO e o gargalo real a 50 Hz: 9,4 ms de pior caso no kernel "
                          "standard vs 20 ms de periodo (PREEMPT_RT desce a <=225 us)"},
    "inferencia_publicada": {"modelo": "small CNN (ONNX Runtime, 1 core A76)",
                             "fp32_ms": 0.194, "int8_ms": 0.143, "fator_int8": 1.36,
                             "fator_int8_sdot": 1.83,
                             "nucleos_ort_default": "intra_op = nucleos fisicos; XNNPACK EP = 1"},
    "fonte": "Raspberry Pi 5 Product Brief (RP-008348-DS) + medicoes publicadas no A76",
    "nota": "specs do ALVO (Raspberry Pi 5); a imagem que o dono tem num B+ de 2014 nao tem estes numeros",
}
CONTROLO_INICIAL = {"vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False, "reiniciar": 0,
                    "loop": False}
MAX_LINHAS = 200                                   # teto de amostras devolvidas por `GET /api/sim`
MAX_CORPO = 64 * 1024                              # teto do corpo de um POST (64 kB chega e sobra)
MAX_LEITURA = 4 * 1024 * 1024                      # bytes lidos do fim da telemetria por pedido
MENSAGEM_SEM_DIST = (
    "site/dist/index.html nao existe — corra `npm run build` em {pasta} (ou `npm install && npm run build`) "
    "e recarregue esta pagina."
)


# ---------------------------------------------------------------------------------------------- ficheiros
def _absoluto(caminho) -> Path:
    """Caminho absoluto (resolvido contra o cwd do SITE, não o do runner) — `--controlo`/`--telemetria`.

    O runner é lançado com `cwd=experiments/09_drone_hover_rl` (para o MUJOCO_LOG.TXT ficar na pasta do
    experimento), por isso um caminho relativo tem de ser fixado aqui: senão o site lia/escrevia num sítio e
    o filho noutro, e a telemetria nunca aparecia na API.
    """
    alvo = Path(caminho).expanduser()
    return alvo if alvo.is_absolute() else (Path.cwd() / alvo).resolve()


def ler_controlo(caminho: Path) -> dict:
    """Controlo em vigor (tolerante: ficheiro ausente/ilegível → valores iniciais do contrato)."""
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            return {**CONTROLO_INICIAL, **dados}
    except (OSError, ValueError):
        pass
    return dict(CONTROLO_INICIAL)


def escrever_controlo(caminho: Path, dados: dict) -> dict:
    """Escreve o controlo de forma ATÓMICA (tmp no mesmo diretório + `os.replace`) e carimba `t`."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    registo = {**CONTROLO_INICIAL, **dados, "t": time.time()}
    tmp = caminho.with_name(f".{caminho.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(registo, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, caminho)                       # troca atómica: o runner nunca lê meio ficheiro
    return registo


def ultimas_linhas(caminho: Path, n: int = MAX_LINHAS) -> list[dict]:
    """Últimas `n` amostras VÁLIDAS da telemetria (lê só o fim do ficheiro; ignora linhas truncadas)."""
    try:
        with Path(caminho).open("rb") as ficheiro:
            ficheiro.seek(0, os.SEEK_END)
            tamanho = ficheiro.tell()
            ficheiro.seek(max(0, tamanho - MAX_LEITURA))
            bruto = ficheiro.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    linhas = []
    for linha in bruto.splitlines():
        linha = linha.strip()
        if not linha.startswith("{"):
            continue                                # 1.ª linha pode estar cortada a meio: ignora-se
        try:
            amostra = json.loads(linha)
        except ValueError:
            continue
        if isinstance(amostra, dict):
            linhas.append(amostra)
    return linhas[-n:]


def resumo_telemetria(caminho: Path) -> dict:
    """Resumo do fim da telemetria: estado/ep/passo/retorno + o VENTO EM VIGOR da última amostra."""
    linhas = ultimas_linhas(caminho, MAX_LINHAS)
    if not linhas:
        return {"estado": "desconhecido", "ep": 0, "passo": 0, "retorno": 0.0, "linhas": 0, "t": None,
                "vento_vec": None, "vento_vel": None, "vento_azim": None, "vento_modo": None}
    ultima = linhas[-1]
    vec = ultima.get("vento_vec")
    return {"estado": str(ultima.get("estado", "desconhecido")), "ep": int(ultima.get("ep", 0) or 0),
            "passo": int(ultima.get("passo", 0) or 0), "retorno": float(ultima.get("retorno", 0.0) or 0.0),
            "linhas": len(linhas), "t": ultima.get("t"),
            "vento_vec": [float(v) for v in vec] if isinstance(vec, list) and len(vec) == 3 else None,
            "vento_vel": float(ultima.get("vento_vel", 0.0) or 0.0),
            "vento_azim": float(ultima.get("vento_azim", 0.0) or 0.0),
            "vento_modo": str(ultima.get("vento_modo", "nenhum") or "nenhum")}


def vento_do_controlo(controlo: dict) -> dict:
    """Bloco `vento_dinamico` do controlo em vigor (o que o site pediu): `{modo, params, ativo}`."""
    din = controlo.get("dinamico")
    if not isinstance(din, dict):
        return {"modo": "nenhum", "params": {}, "ativo": False}
    return {"modo": str(din.get("modo", "nenhum")), "params": din.get("params") or {},
            "ativo": bool(din.get("ativo", False))}


def vento_em_vigor(resumo: dict, controlo: dict) -> dict:
    """Vento que a FÍSICA leva agora: vector (vx,vy,vz) + polar + modo dinâmico em vigor.

    Vem da ÚLTIMA amostra da telemetria (é o `model.opt.wind` do runner, incluindo rajadas/turbulência); sem
    telemetria cai no vento BASE pedido no controlo, para a API nunca ficar sem resposta.
    """
    vec = resumo.get("vento_vec")
    if vec is None:
        din = vento_do_controlo(controlo)
        base = [float(controlo.get("vel", 0.0) or 0.0), float(controlo.get("azimute", 0.0) or 0.0),
                float(controlo.get("elevacao", 0.0) or 0.0)]
        if din["ativo"] and din["modo"] == "frente" and "vel" in din["params"]:
            # `frente` (a): degrau imediato do vento base — sem telemetria é ele que manda (o topo do
            # controlo só o tem se a escrita veio do site; um ficheiro à mão pode trazer só o bloco).
            base = [float(din["params"]["vel"]), float(din["params"]["azimute"]),
                    float(din["params"]["elevacao"])]
        vel, azim, elev = base
        if not controlo.get("ativo", True) and not (din["ativo"] and din["modo"] == "frente"):
            vel = 0.0
        cos_e, az = math.cos(math.radians(elev)), math.radians(azim)
        vec = [vel * cos_e * math.cos(az), vel * cos_e * math.sin(az), vel * math.sin(math.radians(elev))]
        return {"vec": [round(v, 6) for v in vec], "vel": round(vel, 6), "azimute": round(azim % 360.0, 6),
                "elevacao": round(elev, 6), "modo": din["modo"] if din["ativo"] else "nenhum",
                "fonte": "controlo (sem telemetria)"}
    norma = math.sqrt(sum(v * v for v in vec))
    elev = 0.0 if norma == 0.0 else math.degrees(math.asin(max(-1.0, min(1.0, vec[2] / norma))))
    return {"vec": [round(v, 6) for v in vec], "vel": round(norma, 6),
            "azimute": round(math.degrees(math.atan2(vec[1], vec[0])) % 360.0, 6) if norma else 0.0,
            "elevacao": round(elev, 6), "modo": str(resumo.get("vento_modo") or "nenhum"),
            "fonte": "telemetria (runner)"}


def ler_benchmark(caminho: Path | None = None) -> dict | None:
    """Relatório do `deploy.py` (JSON) — `None` se não existir/for ilegível (a API continua a funcionar)."""
    alvo = Path(caminho) if caminho is not None else BENCHMARK_OMISSAO
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def mesma_coisa(a, b) -> bool:
    """Os dois caminhos apontam para o MESMO ficheiro? Relativos são resolvidos contra a pasta do experimento.

    O relatório do `deploy.py` grava o caminho do modelo RELATIVO à pasta onde correu (`out/.../best_model.zip`),
    não ao cwd de quem lê a API: sem isto, `modelo_coincide` dizia sempre `false`.
    """
    pa, pb = Path(str(a)), Path(str(b))
    pa = pa if pa.is_absolute() else _AQUI / pa
    pb = pb if pb.is_absolute() else _AQUI / pb
    return pa.resolve() == pb.resolve()


def bloco_rpi5(bench: dict | None, decisoes_s: float, modelo_em_uso=None) -> dict:
    """Painel RPi 5: specs fixas + inferência medida (benchmark) + uso calculado AO VIVO.

    `uso.fracao_budget = p50_us · decisoes_s / 20000` (a fórmula do contrato: decisões/s reais × latência ÷
    período de 20 ms a 50 Hz) e `pct_budget` é a mesma coisa em %; `pct_cpu_equivalente` reparte-a pelos 4
    núcleos do BCM2712 (a inferência do proxy é single-thread: `nucleos_multi_ia = 1`). Sem benchmark,
    `fonte = "sem benchmark"` e os campos de inferência vêm a `None` — o painel mostra "sem dados".
    `inferencia.modelo_coincide` diz se o modelo MEDIDO é o mesmo que o runner está a carregar (o painel
    estima o custo do que corre, não de outro `.zip`).
    """
    jitter, publicada = RPI5_SPECS["jitter_so"], RPI5_SPECS["inferencia_publicada"]
    uso = {"decisoes_s": round(float(decisoes_s), 3), "latencia_estimada_us": None, "fracao_budget": None,
           "pct_budget": None, "pct_cpu_equivalente": None, "nucleos_multi_ia": 1,
           "pct_periodo": None,          # p50 do NOSSO MLP por decisão, em % do período de 20 ms
           "pct_periodo_publicado_cnn": round(100.0 * publicada["fp32_ms"] * 1000.0 / BUDGET_US, 3),
           "jitter_ms_standard": jitter["standard_ms_pior_caso"],
           "jitter_us_preempt_rt": jitter["preempt_rt_us_max"],
           "gargalo": "jitter do SO a 50 Hz (9,4 ms de pior caso no kernel standard) — a inferência do "
                      "nosso MLP usa <1% do período de 20 ms",
           "nota": "p50 (proxy x86 de 1 core A76) x decisoes/s medidas na telemetria / 20 ms (50 Hz)"}
    if not bench:
        return {"specs": dict(RPI5_SPECS), "inferencia": None, "uso": uso, "fonte": "sem benchmark",
                "benchmark": str(BENCHMARK_OMISSAO)}
    b = bench.get("benchmark") or {}
    p50 = float(b.get("p50_us") or 0.0)
    onnx = bench.get("onnx") or {}
    int8 = bench.get("int8") or {}
    fracao = p50 * float(decisoes_s) / BUDGET_US
    uso.update({"latencia_estimada_us": round(p50, 3), "fracao_budget": round(fracao, 6),
                "pct_budget": round(100.0 * fracao, 3),
                "pct_cpu_equivalente": round(100.0 * fracao / NUCLEOS_SOC, 3),
                "pct_periodo": round(100.0 * p50 / BUDGET_US, 4)})
    inferencia = {
        "p50_us": round(p50, 3), "p99_us": round(float(b.get("p99_us") or 0.0), 3),
        "max_us": round(float(b.get("max_us") or 0.0), 3),
        "modelo_kb": round(float(onnx.get("bytes") or 0) / 1024.0, 2),   # ONNX fp32 (o que corre no RPi)
        "int8_fator": round(float(int8.get("fator_p50") or 0.0), 4),     # p50 fp32 / p50 int8 (medido)
        "int8_kb": round(float((int8.get("info") or {}).get("bytes") or 0) / 1024.0, 2),
        "int8_reducao_tamanho": round(float((int8.get("info") or {}).get("reducao_tamanho") or 0.0), 4),
        "inferencias_s": round(float(b.get("inferencias_s") or 0.0), 1),
        "threads": b.get("threads"), "n": b.get("n"), "cabe_50hz": b.get("cabe_50hz"),
        "modelo": (bench.get("modelo") or {}).get("caminho"),
        "modelo_coincide": None,        # preenchido por `bloco_rpi5` com o modelo que o runner carregou
        "json": bench.get("_caminho", str(BENCHMARK_OMISSAO)),
        "gerado_em": bench.get("gerado_em"), "cpu_benchmark": bench.get("cpu"),
        "veredicto": bench.get("veredicto"),
    }
    modelo_bench = inferencia["modelo"]
    if modelo_em_uso is not None and modelo_bench:
        inferencia["modelo_coincide"] = mesma_coisa(modelo_bench, modelo_em_uso)
    return {"specs": dict(RPI5_SPECS), "inferencia": inferencia, "uso": uso,
            "fonte": "proxy x86 calibrado (1 core do A76; nao e o RPi)", "benchmark": inferencia["json"]}


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
    opcional (por omissão liga-se quando `vel > 0` e desliga-se com `vel == 0`) — é o que faz
    `{"vel": 0}` ser "parar o vento" sem precisar de um campo extra.
    """
    if not isinstance(dados, dict):
        raise ValueError("o corpo tem de ser um objeto JSON")  # noqa: TRY004
    novos = {}
    for campo, teto in (("vel", VEL_MAX), ("azimute", AZIM_MAX), ("elevacao", ELEV_MAX)):
        valor = _numero_finito(dados, campo)
        if valor is None:
            continue
        if campo == "vel" and not 0.0 <= valor <= VEL_MAX:
            raise ValueError(f"`vel` tem de estar em [0, {VEL_MAX}] m/s (recebido {valor!r})")
        if campo == "azimute" and not 0.0 <= valor <= AZIM_MAX:
            raise ValueError(f"`azimute` tem de estar em [0, {AZIM_MAX}] graus (recebido {valor!r})")
        if campo == "elevacao" and not -ELEV_MAX <= valor <= ELEV_MAX:
            raise ValueError(f"`elevacao` tem de estar em [-{ELEV_MAX}, {ELEV_MAX}] graus (recebido {valor!r})")
        novos[campo] = valor
    if not novos:
        raise ValueError("indique pelo menos um de `vel`, `azimute` ou `elevacao`")
    vel = float(novos.get("vel", atual.get("vel", 0.0)))
    ativo = dados.get("ativo")
    if ativo is not None and not isinstance(ativo, bool):
        raise ValueError(f"`ativo` tem de ser booleano (recebido {ativo!r})")
    return {**atual, **novos, "ativo": (vel > 0.0) if ativo is None else ativo}


# ---------------------------------------------------------------------------------------------- servidor
class Servidor:
    """Estado partilhado entre os pedidos: caminhos, processo do runner, modelo e a porta em uso."""

    def __init__(self, controlo: Path, telemetria: Path, host: str, porta: int, verboso: bool = False,
                 filho: subprocess.Popen | None = None, modelo: Path | None = None,
                 motivo: str = ""):
        self.controlo = Path(controlo)
        self.telemetria = Path(telemetria)
        self.host = host
        self.porta = porta
        self.verboso = verboso
        self.filho = filho
        self.modelo = Path(modelo) if modelo is not None else None    # o .zip que o runner carregou
        self.modelo_motivo = motivo or ""                             # porquê este modelo (auditoria)
        self._ritmo = {"t": None, "passo": None, "valor": 0.0}       # decisoes/s medidos entre pedidos
        self._bench = {"t": 0.0, "dados": None}                      # cache do relatório do deploy.py

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
            self._bench = {"t": agora, "dados": ler_benchmark()}
        return self._bench["dados"]

    @property
    def modelo_nome(self) -> str | None:
        """`pasta/ficheiro.zip` do modelo (o que o cabeçalho do site mostra), ou `None` sem modelo."""
        if self.modelo is None:
            return None
        pasta = self.modelo.parent.name
        return f"{pasta}/{self.modelo.name}" if pasta else self.modelo.name

    @property
    def sim_vivo(self) -> bool:
        return self.filho is not None and self.filho.poll() is None


class Handler(BaseHTTPRequestHandler):
    """Rotas da API + ficheiros de `site/dist/` (sem dependências externas)."""

    servidor: Servidor            # injetado por `criar_handler` (atributo de classe)
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ utilidades de resposta
    def _enviar(self, codigo: int, corpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")     # um `npm run build` novo aparece logo
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def _json(self, codigo: int, dados) -> None:
        self._enviar(codigo, json.dumps(dados, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def _erro(self, codigo: int, mensagem: str) -> None:
        self._json(codigo, {"erro": mensagem, "codigo": codigo})

    def log_message(self, formato: str, *args) -> None:   # assinatura do BaseHTTPRequestHandler
        if self.servidor.verboso:
            print(f"[site] {self.address_string()} {formato % args}", flush=True)

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:                             # assinatura do BaseHTTPRequestHandler
        rota = self.path.split("?", 1)[0]
        try:
            if rota == "/api/sim":
                self._api_sim()
            elif rota == "/api/state":
                self._api_state()
            elif rota.startswith("/api/"):
                self._erro(404, f"rota desconhecida: {rota}")
            else:
                self._estatico(rota)
        except Exception as erro:  # noqa: BLE001  (nenhum pedido pode matar o servidor)
            self._erro(500, f"erro interno: {erro}")

    def _api_sim(self) -> None:
        """`GET /api/sim`: estado do episódio + vento em vigor + as últimas amostras da telemetria.

        `modelo`/`modelo_nome` são ADITIVOS ao contrato original: o site aceita qualquer um deles (no topo ou
        dentro de `probe`) e mostra-o no cabeçalho sem precisar de outro pedido.
        """
        resumo = resumo_telemetria(self.servidor.telemetria)
        controlo = ler_controlo(self.servidor.controlo)
        self._json(200, {
            "estado": resumo["estado"],
            "ep": resumo["ep"],
            "passo": resumo["passo"],
            "retorno": resumo["retorno"],
            "vento": {campo: controlo.get(campo) for campo in ("vel", "azimute", "elevacao", "ativo")},
            "vento_dinamico": vento_do_controlo(controlo),
            "vento_atual": vento_em_vigor(resumo, controlo),
            "modelo": None if self.servidor.modelo is None else str(self.servidor.modelo),
            "modelo_nome": self.servidor.modelo_nome,
            "linhas": ultimas_linhas(self.servidor.telemetria),
        })

    def _api_state(self) -> None:
        """`GET /api/state`: resumo curto (sem as amostras) para o cabeçalho do site, com o MODELO em uso."""
        resumo = resumo_telemetria(self.servidor.telemetria)
        controlo = ler_controlo(self.servidor.controlo)
        filho = self.servidor.filho
        idade = None if resumo["t"] is None else round(time.time() - _mtime(self.servidor.telemetria), 3)
        self._json(200, {
            "estado": resumo["estado"],
            "ep": resumo["ep"],
            "passo": resumo["passo"],
            "retorno": resumo["retorno"],
            "vento": {campo: controlo.get(campo) for campo in ("vel", "azimute", "elevacao", "ativo")},
            "vento_dinamico": vento_do_controlo(controlo),
            "vento_atual": vento_em_vigor(resumo, controlo),
            "rpi5": bloco_rpi5(self.servidor.benchmark(),
                               self.servidor.medir_ritmo(resumo["passo"]), self.servidor.modelo),
            "modelo": None if self.servidor.modelo is None else str(self.servidor.modelo),
            "modelo_nome": self.servidor.modelo_nome,
            "modelo_motivo": self.servidor.modelo_motivo,
            "loop": bool(controlo.get("loop", False)),
            "reiniciar": int(controlo.get("reiniciar", 0) or 0),
            "sim_vivo": self.servidor.sim_vivo,
            "pid": None if filho is None else filho.pid,
            "porta": self.servidor.porta,
            "controlo": str(self.servidor.controlo),
            "telemetria": str(self.servidor.telemetria),
            "amostras": resumo["linhas"],
            "idade_telemetria_s": idade,
            "site_pronto": INDEX.is_file(),
        })

    def _estatico(self, rota: str) -> None:
        """Serve `site/dist/`; sem `index.html` devolve a mensagem de `npm run build` (200, texto simples)."""
        if not INDEX.is_file():
            corpo = MENSAGEM_SEM_DIST.format(pasta=DIST.parent).encode("utf-8")
            self._enviar(200, corpo, "text/plain; charset=utf-8")
            return
        caminho = urllib.parse.unquote(rota)
        if ".." in caminho.split("/"):
            self._erro(404, f"caminho inválido: {rota}")     # traversal: 404 explícito, nunca sai da pasta
            return
        alvo = _ficheiro_do_site(caminho)
        if alvo is None:
            if caminho.startswith("/assets/") or "." in Path(caminho).name:
                self._erro(404, f"não existe: {caminho}")    # asset em falta: 404 (o site tem de o saber)
                return
            alvo = INDEX                                     # rotas do site (SPA): cai no index
        try:
            corpo = alvo.read_bytes()
        except OSError as erro:
            self._erro(404, f"não consegui ler {alvo.name}: {erro}")
            return
        tipo = mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/json"):
            tipo += "; charset=utf-8"
        self._enviar(200, corpo, tipo)

    # ------------------------------------------------------------------ POST
    def do_POST(self) -> None:                            # assinatura do BaseHTTPRequestHandler
        rota = self.path.split("?", 1)[0]
        try:
            dados = self._ler_corpo()
            if rota == "/api/vento":
                self._post_vento(dados)
            elif rota == "/api/reiniciar":
                self._post_reiniciar()
            elif rota == "/api/vento-dinamico":
                self._post_vento_dinamico(dados)
            elif rota == "/api/loop":
                self._post_loop(dados)
            else:
                self._erro(404, f"rota desconhecida: {rota}")
        except _PedidoInvalido as erro:
            self._erro(400, str(erro))
        except Exception as erro:  # noqa: BLE001  (nenhum pedido pode matar o servidor)
            self._erro(500, f"erro interno: {erro}")

    def _ler_corpo(self):
        """Corpo do pedido já em JSON (objeto vazio se vier vazio; `_PedidoInvalido` se não for JSON)."""
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise _PedidoInvalido("Content-Length inválido") from None
        if tamanho < 0 or tamanho > MAX_CORPO:
            raise _PedidoInvalido(f"corpo com {tamanho} bytes (máximo {MAX_CORPO})")
        if tamanho == 0:
            return {}
        bruto = self.rfile.read(tamanho)
        try:
            return json.loads(bruto.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as erro:
            raise _PedidoInvalido(f"corpo não é JSON válido: {erro}") from None

    def _post_vento(self, dados) -> None:
        """Valida as faixas, escreve o controlo (atómico) e devolve o vento que ficou em vigor."""
        atual = ler_controlo(self.servidor.controlo)
        try:
            novo = validar_vento(dados, atual)
        except ValueError as erro:
            self._erro(400, str(erro))
            return
        registo = escrever_controlo(self.servidor.controlo, novo)
        print(f"[site] vento: {registo['vel']:.2f} m/s @ {registo['azimute']:.1f} deg"
              f" (elev {registo['elevacao']:+.1f}, {'ativo' if registo['ativo'] else 'desligado'})", flush=True)
        self._json(200, {"ok": True, "vento": {campo: registo[campo] for campo in
                                               ("vel", "azimute", "elevacao", "ativo")}})

    def _post_vento_dinamico(self, dados) -> None:
        """Liga/reconfigura/desliga o vento DINÂMICO ao vivo (sem reiniciar o episódio): 200/400.

        A validação é a do `env.py` para os modos que ele conhece (mesmas regras do treino), a do contrato
        para o `rajada_agora` e a do `/api/vento` para o `frente` do formato (a) (`{vel,azimute,elevacao}` =
        degrau imediato do vento base, que passa também a ser o vento base do controlo); as faixas más saem
        em 400 com a mensagem do validador.
        """
        atual = ler_controlo(self.servidor.controlo)
        try:
            novo = validar_vento_dinamico(dados, atual)
        except ValueError as erro:
            self._erro(400, str(erro))
            return
        except ImportError as erro:                      # env.py indisponível: não é culpa do pedido
            self._erro(500, f"não consegui validar os modos dinâmicos (env.py): {erro}")
            return
        registo = escrever_controlo(self.servidor.controlo, novo)
        din = registo["dinamico"]
        print(f"[site] vento dinamico: {din['modo']} {din['params']} ativo={din['ativo']} "
              f"(seq {din['seq']})", flush=True)
        if din["modo"] == "frente" and "vel" in din["params"]:
            print(f"[site] frente = degrau imediato do vento base: {registo['vel']:.2f} m/s @ "
                  f"{registo['azimute']:.1f} deg (elev {registo['elevacao']:+.1f}, "
                  f"{'ativo' if registo['ativo'] else 'desligado'})", flush=True)
        self._json(200, {"ok": True, "vento_dinamico": din, "vento_base": {"vel": registo["vel"],
                      "azimute": registo["azimute"], "elevacao": registo["elevacao"],
                      "ativo": registo["ativo"]}})

    def _post_reiniciar(self) -> None:
        """Incrementa o contador `reiniciar`: é o ÚNICO caminho para recomeçar o episódio (sem auto-loop)."""
        atual = ler_controlo(self.servidor.controlo)
        contador = int(atual.get("reiniciar", 0) or 0) + 1
        escrever_controlo(self.servidor.controlo, {**atual, "reiniciar": contador})
        print(f"[site] REINICIAR pedido (contador {contador})", flush=True)
        self._json(200, {"contador": contador})

    def _post_loop(self, dados) -> None:
        """Liga/desliga o auto-reset no fim do episódio (`{"ativo": bool}`)."""
        if not isinstance(dados, dict):
            self._erro(400, "o corpo tem de ser um objeto JSON")
            return
        ativo = dados.get("ativo", dados.get("loop"))
        if not isinstance(ativo, bool):
            self._erro(400, f"`ativo` tem de ser booleano (recebido {ativo!r})")
            return
        atual = ler_controlo(self.servidor.controlo)
        escrever_controlo(self.servidor.controlo, {**atual, "loop": ativo})
        print(f"[site] loop {'ligado' if ativo else 'desligado'}", flush=True)
        self._json(200, {"ok": True, "loop": ativo})


_VALIDADOR_ENV = None


def _validador_env():
    """`env.valida_vento_dinamico` importado à primeira utilização (o site é stdlib até aqui).

    Importar o `env.py` puxa o MuJoCo para o processo do SITE: é o preço de validar os modos dinâmicos com
    as MESMAS regras do treino/runner, em vez de duplicar faixas aqui (uma divergência daria 200 na API e um
    aviso no runner). Só acontece quando alguém usa o vento dinâmico; sem ele o site nunca importa MuJoCo.
    """
    global _VALIDADOR_ENV
    if _VALIDADOR_ENV is None:
        from env import valida_vento_dinamico  # import tardio (pesado): ver o docstring
        _VALIDADOR_ENV = valida_vento_dinamico
    return _VALIDADOR_ENV


def _params_rajada_agora(params: dict) -> dict:
    """Params da rajada one-shot: `u` [0, 5] m/s, `azimute` [0, 360)°, `elevacao` ±90°, `duracao` ≥ 1.

    Gémea da do `sim_view.py` (o runner valida outra vez ao aplicar; aqui serve para o 400 da API).
    """
    desconhecidas = set(params) - {"u", "azimute", "elevacao", "duracao"}
    if desconhecidas:
        raise ValueError(f"`params` (rajada_agora) tem chaves desconhecidas {sorted(desconhecidas)} — aceita "
                         "['azimute', 'duracao', 'elevacao', 'u']")
    u = params.get("u", RAJADA_U_PADRAO)
    if isinstance(u, bool) or not isinstance(u, (int, float)) or not math.isfinite(float(u)):
        raise ValueError(f"`params.u` tem de ser um número finito (recebido {u!r})")
    if not 0.0 <= float(u) <= RAJADA_U_MAX:
        raise ValueError(f"`params.u` tem de estar em [0, {RAJADA_U_MAX}] m/s (recebido {u!r})")
    saida = {"u": float(u)}
    for campo, minimo, maximo in (("azimute", 0.0, AZIM_MAX), ("elevacao", -ELEV_MAX, ELEV_MAX)):
        valor = params.get(campo, 0.0)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(float(valor)):
            raise ValueError(f"`params.{campo}` tem de ser um número finito (recebido {valor!r})")
        if not minimo <= float(valor) <= maximo:
            raise ValueError(f"`params.{campo}` tem de estar em [{minimo}, {maximo}] (recebido {valor!r})")
        saida[campo] = float(valor) % AZIM_MAX if campo == "azimute" else float(valor)
    duracao = params.get("duracao", RAJADA_DURACAO_PADRAO)
    if isinstance(duracao, bool) or not isinstance(duracao, int) or int(duracao) < 1:
        raise ValueError(f"`params.duracao` tem de ser um inteiro ≥ 1 passos de decisão (recebido {duracao!r})")
    saida["duracao"] = int(duracao)
    return saida


def _params_frente(params: dict, atual: dict) -> tuple[dict, dict | None]:
    """Params do modo `frente` → `(params, vento_base_novo|None)`: aceita os DOIS formatos do contrato.

    · formato (a) `{"vel", "azimute", "elevacao"}` → degrau IMEDIATO do vento base: validado com as MESMAS
      faixas do `POST /api/vento` (`vel` [0, 5] m/s, `azimute` [0, 360]°, `elevacao` ±90°) e devolvido
      também como vento BASE do controlo (`vel`/`azimute`/`elevacao`/`ativo`) — assim o estado do site, o
      ficheiro e a física dizem o mesmo, e o degrau é o vento base que fica depois de um `nenhum`. Campo
      ausente mantém o valor em vigor (como no `/api/vento`), para `{"azimute": 270}` ser só uma viragem;
      NÃO passa pelo validador do env (que espera `u_max`/`t_s` e recusaria estas chaves);
    · formato (b) `{"u_max", "t_s"}` (ou sem params) → modo em curso do env: quem valida é o `env.py`.
    Chaves desconhecidas ou mistura dos dois formatos → `ValueError` (o POST responde 400). O `"modo"` lá
    dentro é tolerado quando diz "frente": é o que o `env.valida_vento_dinamico` devolve e o site guarda, e
    o site/frontend pode reenviar os params lidos do `/api/sim` tal e qual (ida-e-volta).
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
    for campo, minimo, maximo in (("vel", 0.0, VEL_MAX), ("azimute", 0.0, AZIM_MAX),
                                  ("elevacao", -ELEV_MAX, ELEV_MAX)):
        valor = _numero_finito(params, campo)
        if valor is None:
            valor = float(atual.get(campo, 0.0) or 0.0)  # ausente = mantém o vento base em vigor
        if not minimo <= valor <= maximo:
            raise ValueError(f"`params.{campo}` tem de estar em [{minimo}, {maximo}] (recebido {valor!r})")
        novos[campo] = valor
    return novos, {**novos, "ativo": novos["vel"] > 0.0}


def validar_vento_dinamico(dados, atual: dict) -> dict:
    """`POST /api/vento-dinamico` → controlo novo, com o bloco `dinamico` validado (ValueError → 400).

    Os modos do env (`rajadas`/`dryden`, e o `frente` do formato (b)) passam pelo `valida_vento_dinamico`
    do PRÓPRIO `env.py` (params normalizados com os defaults do treino); o `frente` do formato (a)
    (`vel`/`azimute`/`elevacao`) é um degrau imediato do vento base e é validado aqui (as faixas do
    `/api/vento`), escrevendo também o vento BASE do controlo; o `rajada_agora` (one-shot dirigido, que o
    env não tem) é validado aqui; `nenhum` não leva params. O `seq` é incrementado a CADA pedido: é o que
    permite disparar duas rajadas iguais seguidas (o runner só (re)age quando a assinatura do bloco muda).
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
        raise ValueError(f"`ativo` tem de ser booleano (recebido {ativo!r})")  # noqa: TRY004
    base_novo = None
    if modo == "frente":                                 # 2 formatos: degrau imediato OU modo do env
        params, base_novo = _params_frente(params, atual)
        if base_novo is None:                            # formato (b): quem valida é o `env.py`
            params = _validador_env()({"modo": modo, **params}) or {}
    elif modo in MODOS_DINAMICOS_ENV:
        params = _validador_env()({"modo": modo, **params}) or {}
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


class _PedidoInvalido(Exception):
    """Corpo/parâmetros maus → HTTP 400."""


def _ficheiro_do_site(rota: str) -> Path | None:
    """Ficheiro de `site/dist/` correspondente à rota, ou `None` (404/SPA). Nunca sai da pasta do site."""
    relativo = rota.lstrip("/") or "index.html"
    if relativo.endswith("/"):
        relativo += "index.html"
    alvo = (DIST / relativo).resolve()
    if not alvo.is_relative_to(DIST.resolve()) or not alvo.is_file():
        return None
    return alvo


def _mtime(caminho: Path) -> float:
    try:
        return Path(caminho).stat().st_mtime
    except OSError:
        return time.time()


def criar_handler(servidor: Servidor):
    """Classe de handler já com o estado do servidor ligado (o `BaseHTTPRequestHandler` não tem __init__ extra)."""
    return type("HandlerLigado", (Handler,), {"servidor": servidor})


def abrir_servidor(host: str, porta: int, servidor: Servidor) -> ThreadingHTTPServer:
    """`ThreadingHTTPServer` na porta pedida (0 = livre), tentando as 10 seguintes se estiver ocupada."""
    tentativas = [porta] if porta == 0 else [porta + i for i in range(11)]
    for tentativa in tentativas:
        try:
            httpd = ThreadingHTTPServer((host, tentativa), criar_handler(servidor))
        except OSError as erro:
            if porta == 0 or tentativa == tentativas[-1]:
                raise SystemExit(f"[site] não consegui abrir {host}:{tentativa} ({erro}) — escolha outra "
                                 f"--port") from erro
            continue
        if tentativa != porta:
            print(f"[site] porta {porta} ocupada: fico na {tentativa}", flush=True)
        servidor.porta = int(httpd.server_address[1])
        httpd.daemon_threads = True
        return httpd
    raise SystemExit("[site] não consegui abrir nenhuma porta")      # inalcançável (o ciclo já saiu)


# ---------------------------------------------------------------------------------------------- runner
def _mais_recente(caminhos) -> Path | None:
    """Ficheiro mais recente de `caminhos` (empate desfeito pelo nome, para ser determinístico)."""
    ficheiros = [p for p in caminhos if p.is_file()]
    return max(ficheiros, key=lambda p: (p.stat().st_mtime_ns, str(p))) if ficheiros else None


def _modelo_validado(out: Path) -> tuple[Path, str] | None:
    """Modelo da ÚLTIMA validação COM SUCESSO em `out/avaliacao_vento/*.json` que ainda exista em disco.

    Os relatórios do `avaliar_vento.py`/`avaliar_denso.py` gravam
    `{"modelo": ..., "n_pass": ..., "n_total": ..., "satisfatorio": bool}` (o `modelo` é relativo à raiz do
    laboratório). Só contam os `satisfatorio: true` (ou `n_pass == n_total`): uma validação que correu MAL
    não promove ninguém. É a melhor pista que existe em disco sobre qual política voa bem — foi o que o dono
    validou (ex.: `vento_r9_polir_vento3/final.zip`, 16/16).
    """
    registos = sorted((out / "avaliacao_vento").glob("*.json"),
                      key=lambda p: p.stat().st_mtime_ns, reverse=True)
    for registo in registos:
        try:
            dados = json.loads(registo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(dados, dict) or not isinstance(dados.get("modelo"), str) or not dados["modelo"]:
            continue
        n_pass, n_total, ok = dados.get("n_pass"), dados.get("n_total"), dados.get("satisfatorio")
        if ok is None:
            ok = (isinstance(n_pass, int) and isinstance(n_total, int) and n_total > 0
                  and n_pass == n_total)
        if not ok:
            continue
        caminho = Path(dados["modelo"])
        if not caminho.is_absolute():
            caminho = _RAIZ / caminho       # os relatórios gravam caminhos relativos à raiz do laboratório
        if caminho.is_file():
            resumo = f"{n_pass}/{n_total}" if isinstance(n_pass, int) and isinstance(n_total, int) else "ok"
            return caminho, f"validacao mais recente ({registo.name}: {resumo})"
    return None


def modelo_por_omissao() -> tuple[Path, str]:
    """`(caminho, motivo)` do modelo por omissão — a ordem de preferência é a MESMA do `sim_view.py`.

    1. o modelo da ÚLTIMA validação com sucesso em `out/avaliacao_vento/*.json` que exista em disco
       (é a política validada pelo dono — ex.: `vento_r9_polir_vento3/final.zip`, 16/16);
    2. `out/vento_*/final.zip` mais recente SEM `_seed` no nome (os "polir/curr" treinados com vento);
    3. `out/vento_*_seed*/final.zip` mais recente (as séries com sementes);
    4. `out/runs/*/final.zip` mais recente;
    5. um `best_model.zip` qualquer (`out/vento_*/` ou `out/runs/*/`) — último recurso;
    6. `SystemExit` com mensagem clara se não houver nada.

    Nunca se escolhe um `best_model.zip` de `out/runs/*/` enquanto existir um `final.zip` de `out/vento_*/`
    (era isso que punha a política fraca antiga a voar e o drone a "sumir" logo no arranque).
    """
    out = _AQUI / "out"
    validado = _modelo_validado(out)
    if validado is not None:
        return validado
    vento = sorted(out.glob("vento_*/final.zip"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    candidato = _mais_recente(p for p in vento if "_seed" not in p.parent.name)
    if candidato is not None:
        return candidato, "vento_*/final.zip mais recente (sem _seed)"
    candidato = _mais_recente(vento)
    if candidato is not None:
        return candidato, "vento_*_seed*/final.zip mais recente"
    candidato = _mais_recente((out / "runs").glob("*/final.zip"))
    if candidato is not None:
        return candidato, "runs/*/final.zip mais recente"
    candidato = _mais_recente(list((out / "runs").glob("*/best_model.zip"))
                              + list(out.glob("vento_*/best_model.zip")))
    if candidato is not None:
        return candidato, "best_model.zip mais recente (ultimo recurso)"
    raise SystemExit(f"[site] nenhum modelo em {out} (avaliacao_vento/*.json, vento_*/final.zip, "
                     "runs/*/final.zip, best_model.zip) — treine primeiro (train.py) ou indique --model "
                     "CAMINHO")


def escolher_modelo(args) -> tuple[Path, str]:
    """`(caminho absoluto, motivo)` do modelo a usar: `--model` explícito manda; senão o por omissão."""
    if args.model is not None:
        return _absoluto(args.model), "explicito (--model)"
    return modelo_por_omissao()


def comando_do_runner(args, modelo: Path | None = None) -> list[str]:
    """Linha de comandos do `sim_view.py` (o `--sem-janela` do site é repassado ao filho).

    O `--model` vai SEMPRE explícito: é o caminho que o site já resolveu (e anuncia na API), para o runner
    carregar exactamente o mesmo ficheiro que o site diz estar a correr.
    """
    comando = [sys.executable, str(SIM_VIEW), "--controlo", str(args.controlo),
               "--telemetria", str(args.telemetria)]
    alvo = modelo if modelo is not None else args.model
    if alvo is not None:
        comando += ["--model", str(alvo)]
    if args.sem_janela:
        comando.append("--sem-janela")
    if args.fator_tempo is not None:
        comando += ["--fator-tempo", f"{args.fator_tempo:g}"]
    if args.loop:
        comando.append("--loop")
    return comando


def lancar_runner(args, modelo: Path | None = None) -> subprocess.Popen:
    """Arranca o `sim_view.py` no seu PRÓPRIO grupo de processos (para o SIGTERM apanhar tudo)."""
    comando = comando_do_runner(args, modelo)
    print(f"[site] runner: {' '.join(comando)}", flush=True)
    return subprocess.Popen(comando, cwd=str(_AQUI), start_new_session=True)   # herda stdout/stderr


def terminar_runner(filho: subprocess.Popen | None, limite: float = 5.0) -> None:
    """SIGTERM ao grupo do runner (SIGKILL se ele não sair em `limite` s) — sempre sem deixar órfãos."""
    if filho is None or filho.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(filho.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        filho.terminate()
    try:
        filho.wait(timeout=limite)
        print(f"[site] runner terminou (exit {filho.returncode})", flush=True)
        return
    except subprocess.TimeoutExpired:
        print("[site] runner não saiu com SIGTERM: SIGKILL", flush=True)
    try:
        os.killpg(os.getpgid(filho.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        filho.kill()
    try:
        filho.wait(timeout=limite)
    except subprocess.TimeoutExpired:
        print("[site] aviso: runner resistiu ao SIGKILL", file=sys.stderr, flush=True)


def abrir_browser(url: str) -> None:
    """`xdg-open URL` (sem bloquear); aviso claro se não houver abridor."""
    abridor = shutil.which("xdg-open")
    if abridor is None:
        print(f"[site] xdg-open não existe: abra {url} à mão", file=sys.stderr, flush=True)
        return
    try:
        subprocess.Popen([abridor, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        print(f"[site] browser aberto em {url}", flush=True)
    except OSError as erro:
        print(f"[site] não consegui abrir o browser ({erro}): abra {url} à mão", file=sys.stderr, flush=True)


def analisar_argumentos(argv=None) -> argparse.Namespace:
    """Argumentos do comando único (os do runner são repassados tal e qual)."""
    p = argparse.ArgumentParser(
        description="UM COMANDO: janela MuJoCo limpa (sim_view.py) + site com métricas e controlos "
                    "(site/dist/) + API local. O vento e o REINICIAR vão pelo ficheiro de controlo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("API: GET /api/sim · GET /api/state · POST /api/vento {vel,azimute,elevacao} · "
                "POST /api/vento-dinamico {modo,params?,ativo?} — `frente` aceita {vel,azimute,elevacao} "
                "(degrau IMEDIATO do vento base) OU {u_max,t_s} (degrau em curso do env); "
                "POST /api/reiniciar · POST /api/loop {\"ativo\": bool}\n"
                "SIGINT/SIGTERM: fecha o servidor e mata o runner (exit 0)."),
    )
    p.add_argument("--model", type=Path, default=None,
                   help="modelo do Stable-Baselines3 (.zip) para o runner; por omissão o site escolhe por "
                        "esta ordem: o modelo da última validação com sucesso (out/avaliacao_vento/*.json) "
                        "-> vento_*/final.zip mais recente (sem _seed) -> vento_*_seed*/final.zip -> "
                        "runs/*/final.zip -> best_model.zip; passa-o explícito ao runner e anuncia-o "
                        "(com o motivo) em /api/state e /api/sim")
    p.add_argument("--sem-janela", action="store_true",
                   help="só site + API (o runner corre sem viewer: nada de GLFW/GL) — é o modo dos testes")
    p.add_argument("--port", type=int, default=8080, metavar="PORTA",
                   help="porta do site; 0 = uma porta livre escolhida pelo sistema (padrão: 8080; se estiver "
                        "ocupada tenta as 10 seguintes)")
    p.add_argument("--host", default="127.0.0.1",
                   help="interface onde servir o site (padrão: 127.0.0.1, só a máquina local)")
    p.add_argument("--controlo", type=Path, default=CONTROLO_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro de controlo (vento/reiniciar/loop); padrão: {CONTROLO_OMISSAO}")
    p.add_argument("--telemetria", type=Path, default=TELEMETRIA_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro JSONL de telemetria do runner; padrão: {TELEMETRIA_OMISSAO}")
    p.add_argument("--fator-tempo", type=float, default=None, metavar="F",
                   help="ritmo do runner (1 = tempo real; 0 = sem travão); por omissão usa o do sim_view.py")
    p.add_argument("--loop", action="store_true", help="arranca o runner com auto-reset no fim do episódio")
    p.add_argument("--sem-browser", action="store_true", help="não abre o browser (o URL sai na mesma)")
    p.add_argument("--verboso", action="store_true", help="mostra cada pedido HTTP no terminal")
    return p.parse_args(argv)


def main(argv=None) -> int:
    """Arranca o runner + o servidor e fica à espera de SIGINT/SIGTERM (exit 0)."""
    args = analisar_argumentos(argv)
    if not SIM_VIEW.is_file():
        raise SystemExit(f"[site] falta o runner: {SIM_VIEW}")
    # O runner corre com cwd=experiments/09_drone_hover_rl: um caminho RELATIVO dado ao site (--controlo,
    # --telemetria, --model) tem de ser resolvido AQUI, senão o site lia/escrevia num sítio e o filho noutro.
    args.controlo = _absoluto(args.controlo)
    args.telemetria = _absoluto(args.telemetria)
    if not INDEX.is_file():
        print(f"[site] aviso: {MENSAGEM_SEM_DIST.format(pasta=DIST.parent)}", flush=True)
    if not args.controlo.exists():
        # o `loop` inicial segue o CLI: se o ficheiro nascesse com `loop: false`, desligava logo o `--loop`
        escrever_controlo(args.controlo, {**CONTROLO_INICIAL, "loop": bool(args.loop)})
        print(f"[site] controlo criado: {args.controlo} (loop={bool(args.loop)})", flush=True)

    # o runner corre com cwd=experiments/09_drone_hover_rl: `--model` relativo resolve-se contra o cwd do SITE
    modelo, motivo = escolher_modelo(args)
    if not modelo.is_file():
        raise SystemExit(f"[site] modelo inexistente: {modelo}")
    print(f"[site] modelo: {modelo} ({motivo})", flush=True)   # diz SEMPRE qual escolheu e porquê
    filho = lancar_runner(args, modelo)
    servidor = Servidor(args.controlo, args.telemetria, args.host, args.port, args.verboso, filho, modelo,
                        motivo)
    httpd = abrir_servidor(args.host, args.port, servidor)
    url = f"http://{args.host}:{servidor.porta}/"
    print(f"[site] runner pid {filho.pid} | controlo {args.controlo} | telemetria {args.telemetria}",
          flush=True)
    print(f"[site] site em {url} (Ctrl+C fecha)", flush=True)

    parar = threading.Event()

    def ao_sinal(_sinal, _frame):
        parar.set()

    for sinal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sinal, ao_sinal)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    thread.start()
    if not args.sem_browser:
        abrir_browser(url)

    avisado = False
    try:
        while not parar.wait(0.2):
            if not avisado and filho.poll() is not None:
                print(f"[site] aviso: o runner terminou (exit {filho.returncode}) — o site continua a servir "
                      f"o que já está na telemetria", flush=True)
                avisado = True
    finally:
        print("[site] a fechar (servidor + runner)...", flush=True)
        httpd.shutdown()
        httpd.server_close()
        terminar_runner(filho)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # `stdout` fechou do outro lado (ex.: `| head`): sair sem traceback e sem o aviso de flush
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
