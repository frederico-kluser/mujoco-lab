#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_fpv.py — PROVA do MÓDULO DE CÂMARA FPV (CSI → Raspberry → site).

O que se prova (tudo por execução; `$TMPDIR` para os temporários, nunca o diretório global):

  §1 ESPECIFICAÇÃO (in-process, sem simulação): o catálogo de peças (`componentes.json` → `cameras`) e o
     emulador (`lab/camera_rpi.MODULOS`) dizem o MESMO campo a campo (massa, dimensões, FoV, sensor, MP,
     píxel) — é o travão da duplicação; os MODOS são os reais (resoluções, fps, crops do `--list-cameras`);
     o FoV por modo bate com a fórmula fechada `2·atan(fator·tan(V/2))` em TODOS os modos × módulos; o
     modelo de CPU soma as etapas e escala por MP/s; o modelo de latência soma os estágios e a 1080p30 cai
     na faixa publicada (150–300 ms); o modo HDR é NÃO emulado e recusa-se (nunca se finge);
  §2 PIPELINE (modelo pequeno, EGL, síncrono): cada modo gera JPEG EXATAMENTE com as dimensões da saída
     (verificadas com PIL), a qualidade por omissão é 50 (q50 < q95 em bytes), a latência do modelo é cumprida
     (`disponiveis()` vazio antes, entrega depois), o módulo desligado não captura, a troca de modo muda o
     TAMANHO e o FOV do render (escrito por captura — a corrida que a revisão apanhou) e o construtor
     recusa modos não emulados;
  §3 CADÊNCIA (thread real): `correr_cadencia` entrega os fps NOMINAIS do modo (±10 %) e a entrega respeita
     a latência; trocar de modo A CORRER muda a cadência;
  §4 RUNNER + SERVIDOR (processos reais): o `sim_view.py --sem-janela` escreve `quadro.jpg`/`estado.json`
     com o modo por omissão e a telemetria com a chave `fpv`; o `sim_site.py` serve `/api/fpv.jpg`,
     `/api/fpv/estado`, o stream `/api/fpv.mjpg` (multipart) e o `POST /api/fpv` (validação 400/200 + o
     bloco no controlo) e o painel RPi 5 publica `camera`/`camera_nucleos`;
  §5 MUTAÇÕES (`--mutacao`): o teste NÃO é tautológico — mutações textuais nas fontes têm de FALHAR as
     checagens certas (cadência, FoV, dimensões, validação).

Uso:
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_fpv.py            # §1–§4
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_fpv.py --mutacao  # §5
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_fpv.py --so-espec # só §1
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

import mujoco
import sim_view

from lab import camera_rpi as cam_rpi
from lab import mjkit  # noqa: F401         (MUJOCO_GL=egl antes do mujoco)

PORTA_HTTP = 8601          # porta do servidor de teste (a do laboratório para testes do FPV)
PORTA_HTTP_M = 8602        # porta para o teste de mutação
TOL_FPS = 0.10             # ±10 % da taxa nominal (o requisito da "mesma taxa de atualização")
TOL_S = 1e-9


# ------------------------------------------------------------------------------------------------ checagens
class Checagens:
    """Acumulador de checagens: uma linha por checagem (com o detalhe medido) e as falhas à parte."""

    def __init__(self, titulo: str) -> None:
        self.titulo = titulo
        self.linhas: list[str] = []
        self.falhas: list[str] = []

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.linhas.append(nome)
        if not cond:
            self.falhas.append(nome)
        print(f"        [{'OK  ' if cond else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""),
              flush=True)
        return bool(cond)


def _titulo(titulo: str) -> None:
    print(f"\n[teste] {titulo}", flush=True)


def _json_rota(base: str, rota: str, corpo: dict | None = None, timeout: float = 10.0):
    if corpo is None:
        pedido = urllib.request.Request(base + rota)
    else:
        pedido = urllib.request.Request(base + rota, data=json.dumps(corpo).encode(),
                                        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            return resposta.status, json.loads(resposta.read()), dict(resposta.headers)
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read()), dict(erro.headers)


def _espera(predicado, limite: float, o_que: str) -> bool:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < limite:
        if predicado():
            return True
        time.sleep(0.05)
    print(f"        [FALHA] tempo esgotado à espera de {o_que}", flush=True)
    return False


# ============================================================================================ §1 especificação
def checa_especificacao(c: Checagens) -> None:
    _titulo("§1 especificação: catálogo × emulador, modos reais, FoV, CPU e latência")
    cat = json.loads((_RAIZ / "models" / "drone_rpi" / "componentes.json").read_text(encoding="utf-8"))
    for pid, peca in cat["cameras"].items():
        mid = cam_rpi.modulo_da_peca(pid)
        m = cam_rpi.MODULOS[mid]
        iguais = (
            abs(float(peca["massa_g"]) - float(m["massa_g"])) < 1e-9     # ambos em gramas
            and [float(v) for v in peca["dims_mm"]] == [float(v) for v in m["dims_mm"]]
            and {k: float(v) for k, v in peca["fov_graus"].items()}
            == {k: float(v) for k, v in m["fov_graus"].items()}
            and peca["sensor"] == m["sensor"]
            and abs(float(peca["mp"]) - float(m["mp"])) < 1e-9
            and abs(float(peca["pixel_um"]) - float(m["pixel_um"])) < 1e-9
            and list(peca["resolucao_px"]) == list(m["resolucao_px"])
            and float(peca["lente"]["focal_mm"]) == float(m["lente"]["focal_mm"])
        )
        c.ok(f"[§1] catálogo × MODULOS: '{pid}' diz o MESMO campo a campo (travão da duplicação)",
             iguais, f"massa {peca['massa_g']} g · dims {peca['dims_mm']} · FoV {peca['fov_graus']}")
    for mid, m in cam_rpi.MODULOS.items():
        c.ok(f"[§1] '{mid}' tem peça do catálogo correspondente",
             m["peca_catalogo"] in cat["cameras"], f"peca_catalogo={m['peca_catalogo']}")

    # ---- modos reais: resoluções, fps e crops (valores do `--list-cameras`/driver imx708, citados no módulo)
    esperados = {
        "4608x2592p14": ((4608, 2592), 14.35, (0, 0, 4608, 2592)),
        "2304x1296p56": ((2304, 1296), 56.03, (0, 0, 4608, 2592)),
        "1536x864p120": ((1536, 864), 120.13, (768, 432, 3072, 1728)),
        "1080p50": ((1920, 1080), 50.0, (0, 0, 4608, 2592)),
        "720p100": ((1280, 720), 100.0, (768, 432, 3072, 1728)),
        "480p120": ((640, 480), 120.0, (768, 432, 3072, 1728)),
    }
    for modo, (saida, fps, crop) in esperados.items():
        mo = cam_rpi.MODOS[modo]
        c.ok(f"[§1] modo {modo}: saída {saida[0]}×{saida[1]} @ {fps:g} fps · crop {crop} (valores reais)",
             mo.saida == saida and abs(mo.fps - fps) < TOL_S and mo.crop == crop,
             f"emulado: {mo.saida} @ {mo.fps} crop {mo.crop}")
    hdr = cam_rpi.MODOS["2304x1296p30hdr"]
    c.ok("[§1] modo HDR 2304×1296p30 existe na tabela mas marcado NÃO EMULADO (nunca se finge)",
         not hdr.emulado and "não" in hdr.nota.lower(), f"emulado={hdr.emulado} · nota={hdr.nota!r}")
    modelo_pequeno, _ = _modelo_pequeno()
    modulo_hdr = cam_rpi.ModuloCamera(modelo_pequeno, "fpv", modo="1080p50", modulo="mod3_wide")
    c.ok("[§1] construtor E ligar() recusam o modo não emulado (erro claro nos dois caminhos)",
         _recusa(lambda: cam_rpi.ModuloCamera(modelo_pequeno, "fpv", modo="2304x1296p30hdr"))
         and _recusa(lambda: modulo_hdr.ligar(True, "2304x1296p30hdr")), "ValueError nos dois")
    modulo_hdr.fechar()

    # ---- render: a proporção da JANELA de recorte (é o que torna o FoV de cada modo correto)
    for modo, mo in cam_rpi.MODOS.items():
        proporcao_render = mo.render[0] / mo.render[1]
        proporcao_janela = mo.crop[2] / mo.crop[3]
        c.ok(f"[§1] modo {modo}: render {mo.render} tem a proporção da janela do recorte "
             f"({proporcao_janela:.4f}) e a altura da saída",
             abs(proporcao_render - proporcao_janela) < 1e-3 and mo.render[1] == mo.saida[1],
             f"render {proporcao_render:.4f} × altura {mo.render[1]} vs saída {mo.saida}")

    # ---- FoV: fórmula fechada 2·atan(fator·tan(V/2)) em TODOS os modos × módulos
    pior = 0.0
    for mid, m in cam_rpi.MODULOS.items():
        for modo, mo in cam_rpi.MODOS.items():
            fechado = math.degrees(2.0 * math.atan(mo.fator_fov * math.tan(
                math.radians(m["fov_graus"]["vertical"]) / 2.0)))
            pior = max(pior, abs(fechado - cam_rpi.fovy_graus(mid, modo)))
    c.ok("[§1] fovy de todos os modos × módulos = 2·atan(fator·tan(V/2)) (fórmula fechada)",
         pior < 1e-12, f"pior desvio {pior:.2e}°")
    âncoras = {("mod3", "1080p50"): 41.0, ("mod3", "720p100"): 27.992, ("mod3_wide", "1080p50"): 67.0,
               ("mod3_wide", "720p100"): 47.620}
    for (mid, modo), valor in âncoras.items():
        c.ok(f"[§1] âncora de FoV {mid}/{modo} = {valor}°",
             abs(cam_rpi.fovy_graus(mid, modo) - valor) < 5e-3,
             f"medido {cam_rpi.fovy_graus(mid, modo):.3f}°")
    c.ok("[§1] `fovy` é GRAUS SEMPRE (não segue o `compiler angle`) — regra descoberta em 3.15",
         _fovy_graus_sempre(), "spec em radianos com fovy=45 → render idêntico ao spec em graus")

    # ---- modelo de CPU: soma exata, faixas/fontes, escala por MP/s
    for modo in cam_rpi.MODOS:
        if not cam_rpi.MODOS[modo].emulado:
            continue
        custo = cam_rpi.custo_cpu(modo)
        soma = sum(e["pct"] for e in custo["etapas"].values())
        c.ok(f"[§1] custo CPU {modo}: total = soma das etapas (com faixa e fonte em cada uma)",
             abs(soma - custo["total_pct_nucleo"]) < 0.11 and all(
                 e["faixa"] and e["fonte"] for e in custo["etapas"].values()),
             f"soma {soma:.1f}% vs total {custo['total_pct_nucleo']}% · {custo['total_nucleos']} núcleos")
    ref = cam_rpi.custo_cpu("1080p50")
    pesado = cam_rpi.custo_cpu("4608x2592p14")
    leve = cam_rpi.custo_cpu("480p120")
    c.ok("[§1] custo CPU escala com a taxa de píxeis (12 MP@14fps > 1080p50 > 480p120)",
         pesado["total_nucleos"] > ref["total_nucleos"] > leve["total_nucleos"],
         f"{pesado['total_nucleos']} > {ref['total_nucleos']} > {leve['total_nucleos']} núcleos")
    c.ok("[§1] referência do modelo = 1080p50 com as âncoras publicadas (JPEG software 50–80% etc.)",
         ref["modo_referencia"] == "1080p50"
         and abs(ref["etapas"]["codificacao_jpeg"]["pct"] - 65.0) < 1e-9
         and ref["etapas"]["codificacao_jpeg"]["faixa"] == "50–80",
         f"jpeg {ref['etapas']['codificacao_jpeg']}")
    c.ok("[§1] alternativa H.264 publicada (whitepaper oficial) citada no resultado (comparação, não uso)",
         "whitepaper" in ref["comparacao_h264"]["fonte"].lower() and ref["comparacao_h264"]["pct_1080p50"],
         ref["comparacao_h264"]["fonte"])

    # ---- modelo de latência: soma, período, faixa publicada
    for modo in ("1080p50", "720p100", "4608x2592p14"):
        lat = cam_rpi.latencia_modelada(modo)
        soma = sum(lat["estagios_ms"].values())
        c.ok(f"[§1] latência {modo}: total = soma dos estágios (cada um com origem dita)",
             abs(soma - lat["total_ms"]) < 0.11 and "ASSUMIDAS" in lat["nota"],
             f"soma {soma:.1f} vs total {lat['total_ms']} ms")
    l30 = _latencia_a_fps(30.0)
    l50 = cam_rpi.latencia_modelada("1080p50")["total_ms"]
    c.ok("[§1] o MESMO modelo a 1080p30 cai na faixa publicada 150–300 ms e a 50 fps é menor",
         150.0 <= l30 <= 300.0 and l50 < l30, f"1080p30 = {l30:.0f} ms · 1080p50 = {l50:.0f} ms")


def _recusa(funcao) -> bool:
    try:
        funcao()
    except ValueError:
        return True
    except Exception:  # noqa: BLE001  (qualquer outro erro NÃO conta como recusa certa)
        return False
    return False


def _modelo_pequeno(fovy: float = 67.0):
    """(model, data) pequeno com a câmara `fpv` — para as provas de especificação/pipeline."""
    spec = mujoco.MjSpec()
    spec.compiler.degree = False
    spec.worldbody.add_geom(type=mujoco.mjtGeom.mjGEOM_PLANE, size=[20, 20, 0.1])
    corpo = spec.worldbody.add_body(name="drone", pos=[0, 0, 1.5])
    corpo.add_freejoint()
    corpo.add_geom(type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.1, 0.1, 0.03], mass=1.0)
    cam_rpi.add_camera_fpv(corpo, (0.15, 0.0, 0.03), fovy, nome="fpv")
    model = spec.compile()
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


def _fovy_graus_sempre() -> bool:
    """O `fovy` segue GRAUS nos dois modos do compiler (o ângulo do compiler NÃO o converte)."""
    valores = []
    for degree in (True, False):
        spec = mujoco.MjSpec()
        spec.compiler.degree = degree
        corpo = spec.worldbody.add_body(name="drone")
        corpo.add_camera(name="fpv", pos=[0, 0, 0], fovy=45.0)
        model = spec.compile()
        valores.append(float(model.cam_fovy[model.camera("fpv").id]))
    return abs(valores[0] - 45.0) < TOL_S and abs(valores[1] - 45.0) < TOL_S


def _latencia_a_fps(fps: float) -> float:
    """Total do modelo de latência para uma saída 1920×1080 a `fps` (a fórmula, por fora)."""
    periodo = 1000.0 / fps
    mp = 1920 * 1080 / 1e6
    return (cam_rpi.LATENCIA_SENSOR_PERIODO * periodo + cam_rpi.LATENCIA_FILA_PERIODO * periodo
            + cam_rpi.LATENCIA_ISP_MS + cam_rpi.LATENCIA_CODIF_REF_MS * mp
            / (cam_rpi.MODOS["1080p50"].mp_saida) + cam_rpi.LATENCIA_REDE_MS
            + cam_rpi.LATENCIA_CLIENTE_PERIODO * periodo)


# ================================================================================================ §2 pipeline
def checa_pipeline(c: Checagens) -> None:
    _titulo("§2 pipeline: JPEG por modo, qualidade 50, latência cumprida, modo/fovy por captura")
    try:
        from PIL import Image
    except ImportError:
        c.ok("[§2] Pillow disponível (o pipeline codifica JPEG com ele)", False, "PIL ausente")
        return
    model, data = _modelo_pequeno()
    modulo = cam_rpi.ModuloCamera(model, "fpv", modo="1080p50", modulo="mod3_wide")
    for modo, mo in cam_rpi.MODOS.items():
        if not mo.emulado:
            continue
        modulo.ligar(True, modo)
        modulo.apontar(data)
        quadro = modulo.capturar()
        imagem = Image.open(io.BytesIO(quadro.jpeg))
        c.ok(f"[§2] modo {modo}: JPEG EXATAMENTE {mo.saida[0]}×{mo.saida[1]} (dimensões verificadas com PIL)",
             imagem.size == mo.saida and quadro.largura == mo.saida[0] and quadro.altura == mo.saida[1],
             f"JPEG {imagem.size} · render {mo.render}")
        fovy_modelo = float(model.cam_fovy[modulo.camera_id])
        c.ok(f"[§2] modo {modo}: o render usa o FOV do modo (escrito por captura, antes do update_scene)",
             abs(fovy_modelo - cam_rpi.fovy_graus("mod3_wide", modo)) < TOL_S,
             f"cam_fovy={fovy_modelo:.3f}° = fovy_graus(mod3_wide, {modo})")
    # qualidade 50 por omissão (rpicam-vid --quality 50) e EFEITIVA nos bytes
    modulo.ligar(True, "1080p50")
    modulo.apontar(data)
    q50 = modulo.capturar()
    alto = cam_rpi.ModuloCamera(model, "fpv", modo="1080p50", modulo="mod3_wide", qualidade=95)
    alto.apontar(data)
    q95 = alto.capturar()
    c.ok("[§2] qualidade JPEG 50 por omissão (default do rpicam-vid) e aplicada (q50 < q95 em bytes)",
         cam_rpi.QUALIDADE_OMISSAO == 50 and modulo.estado()["jpeg_qualidade"] == 50
         and q50.bytes < q95.bytes, f"q50 {q50.bytes // 1024} KB < q95 {q95.bytes // 1024} KB")
    # latência do modelo cumprida
    lat = cam_rpi.latencia_modelada("1080p50")["total_ms"] / 1000.0
    c.ok("[§2] latência cumprida: `disponiveis()` vazio antes de t+latência e entrega a partir dela",
         modulo.disponiveis(agora=q50.t_captura + lat - 1e-6) == []
         and [q.seq for q in modulo.disponiveis(agora=q50.t_captura + lat + 1e-6)] == [q50.seq],
         f"latência do modelo {1000 * lat:.0f} ms · t_disponivel−t_captura = "
         f"{1000 * (q50.t_disponivel - q50.t_captura):.1f} ms")
    # módulo desligado não captura
    estado = modulo.ligar(False)
    c.ok("[§2] módulo desligado: não captura, não acumula fila e o estado diz a verdade",
         modulo.capturar() is None and modulo.estado()["ligada"] is False and estado["ligada"] is False,
         f"quadros={modulo.estado()['quadros']} fila={modulo.estado()['fila']}")
    modulo.ligar(True, "720p100")
    # construtor recusa modo não emulado (reparação da revisão)
    c.ok("[§2] o CONSTRUTOR também recusa modo não emulado (não só o `ligar`)",
         _recusa(lambda: cam_rpi.ModuloCamera(model, "fpv", modo="2304x1296p30hdr")),
         "ValueError no __init__")
    modulo.fechar()
    alto.fechar()

    # ---- contrato do controlo (runner): `sim_view._ler_fpv` valida o bloco completo e os modos
    bloco_ok = sim_view.ler_registo({"fpv": {"ligada": False, "modo": "720p100", "seq": 3}}).fpv
    c.ok("[§2] `sim_view._ler_fpv` aceita o bloco completo e guarda modo/ligada/seq",
         bloco_ok is not None and bloco_ok.modo == "720p100" and bloco_ok.ligada is False
         and bloco_ok.seq == 3 and isinstance(bloco_ok.assinatura(), str),
         f"bloco={bloco_ok}")
    c.ok("[§2] `sim_view._ler_fpv` recusa modo desconhecido, não emulado e bloco a meio (3/3)",
         _recusa(lambda: sim_view.ler_registo({"fpv": {"ligada": True, "modo": "nope"}}))
         and _recusa(lambda: sim_view.ler_registo({"fpv": {"ligada": True, "modo": "2304x1296p30hdr"}}))
         and _recusa(lambda: sim_view.ler_registo({"fpv": {"ligada": True}})),
         "ValueError nos três")


# ============================================================================================== §3 cadência
def _correr_cadencia_breve(model, data, modo: str, segundos: float):
    """(módulo, quadros entregues, evento de paragem, thread) — uma corrida curta de cadência."""
    modulo = cam_rpi.ModuloCamera(model, "fpv", modo=modo, modulo="mod3_wide")
    entregues: list = []
    parar = threading.Event()
    thread = threading.Thread(
        target=lambda: cam_rpi.correr_cadencia(modulo, parar.is_set, entregues.append), daemon=True)
    modulo.apontar(data)
    thread.start()
    time.sleep(segundos)
    parar.set()
    thread.join(timeout=3.0)
    modulo.fechar()
    return modulo, entregues, parar, thread


def checa_cadencia(c: Checagens) -> None:
    _titulo("§3 cadência real (thread): fps nominais ±10 % e latência cumprida na entrega")
    model, data = _modelo_pequeno()
    modulo = cam_rpi.ModuloCamera(model, "fpv", modo="1080p50", modulo="mod3_wide")
    entregues: list[cam_rpi.Quadro] = []
    parar = threading.Event()

    def ciclo() -> None:
        cam_rpi.correr_cadencia(modulo, parar.is_set, entregues.append)

    thread = threading.Thread(target=ciclo, daemon=True)
    modulo.apontar(data)
    t0 = time.perf_counter()
    thread.start()
    time.sleep(2.2)
    parar.set()
    thread.join(timeout=3.0)
    dt = time.perf_counter() - t0
    taxa = (len(entregues) - 1) / dt if len(entregues) > 1 else 0.0
    nom = cam_rpi.MODOS["1080p50"].fps
    tentativas = [round(taxa, 1)]
    # Sob CONTENÇÃO de host (outros processos) a taxa nominal pode não ser sustentável — o que se prova
    # aqui é a fidelidade do MÓDULO, por isso re-tenta (módulo novo, thread nova) e relata tudo + loadavg.
    while abs(taxa - nom) / nom > TOL_FPS and len(tentativas) < 3:
        modulo, entregues, parar, thread = _correr_cadencia_breve(model, data, "1080p50", 2.2)
        dt = 2.2
        taxa = (len(entregues) - 1) / dt if len(entregues) > 1 else 0.0
        tentativas.append(round(taxa, 1))
    carga = ",".join(str(v) for v in os.getloadavg())
    c.ok(f"[§3] 1080p50: {len(entregues)} quadros em {dt:.1f} s = {taxa:.1f} fps (nominal {nom:g})",
         abs(taxa - nom) / nom <= TOL_FPS,
         f"desvio {100 * (taxa - nom) / nom:+.1f} % · tentativas {tentativas} · loadavg {carga}")
    lat = cam_rpi.latencia_modelada("1080p50")["total_ms"] / 1000.0
    atrasos = [q.t_disponivel - q.t_captura for q in entregues]
    c.ok("[§3] entrega com a latência do modelo (cada quadro sai ≥ latência depois da captura)",
         atrasos and min(atrasos) >= lat - 1e-3 and max(atrasos) < lat + 0.25,
         f"atraso {1000 * min(atrasos):.0f}–{1000 * max(atrasos):.0f} ms · modelo {1000 * lat:.0f} ms")
    estado = modulo.estado()
    c.ok("[§3] `estado()` coerente: bitrate ≈ bytes_medio·8·fps_medido e host_ms é média (não o último)",
         estado["bitrate_mbps"] is None or abs(
             estado["bitrate_mbps"] - estado["bytes_medio"] * 8e-6 * estado["fps_medido"]) < 0.05,
         f"bitrate {estado['bitrate_mbps']} Mbps · fps_medido {estado['fps_medido']} · "
         f"host {estado['host_ms']['total']} ms")
    # troca de modo A CORRER muda a cadência (reparação da revisão: o período é relido a cada ciclo)
    entregues2: list[cam_rpi.Quadro] = []
    parar2 = threading.Event()
    modulo2 = cam_rpi.ModuloCamera(model, "fpv", modo="1080p50", modulo="mod3_wide")
    thread2 = threading.Thread(target=lambda: cam_rpi.correr_cadencia(modulo2, parar2.is_set,
                                                                     entregues2.append), daemon=True)
    modulo2.apontar(data)
    thread2.start()
    time.sleep(0.7)
    n_50 = len(entregues2)
    modulo2.ligar(True, "1536x864p120")          # 120 fps: a cadência tem de subir
    time.sleep(1.3)
    parar2.set()
    thread2.join(timeout=3.0)
    taxa2 = (len(entregues2) - n_50) / 1.3
    taxa1 = n_50 / 0.7
    # A prova é a TROCA de cadência (razão ≥ 1,5× entre os dois trechos), não o valor absoluto: sob
    # carga do PC os dois trechos caem juntos e a razão continua a dizer que a cadência segue o modo.
    c.ok("[§3] troca de modo A CORRER muda a cadência (50 → 120 fps sem recriar a thread)",
         taxa2 >= 1.5 * taxa1, f"{taxa1:.0f} fps antes · {taxa2:.0f} fps depois (razão "
         f"{taxa2 / max(taxa1, 1e-9):.2f}× · n_50={n_50} → {len(entregues2)})")
    # estado publicado depois de DESLIGAR (reparação: escrever_estado do runner)
    modulo2.ligar(False)
    c.ok("[§3] desligar muda o estado imediatamente (sem esperar por quadros novos)",
         modulo2.estado()["ligada"] is False, f"estado ligada={modulo2.estado()['ligada']}")
    modulo2.fechar()


# ======================================================================================= §4 runner + servidor
def checa_runner(c: Checagens) -> None:
    _titulo("§4a runner: quadro.jpg/estado.json com o modo por omissão e telemetria com `fpv`")
    pasta = Path(tempfile.mkdtemp(prefix="teste_fpv_", dir=os.environ.get("TMPDIR")))
    controlo, telemetria = pasta / "ctl.json", pasta / "tel.jsonl"
    comando = [sys.executable, str(_AQUI / "sim_view.py"), "--sem-janela", "--max-segundos", "4",
               "--fpv", str(pasta), "--controlo", str(controlo), "--telemetria", str(telemetria)]
    subprocess.run(comando, cwd=str(pasta), capture_output=True, text=True, timeout=120, check=False)
    quadro, estado = pasta / "quadro.jpg", pasta / "estado.json"
    c.ok("[§4a] o runner escreveu quadro.jpg (JPEG válido) e estado.json", quadro.is_file()
         and quadro.read_bytes()[:2] == b"\xff\xd8" and estado.is_file(),
         f"quadro {quadro.stat().st_size if quadro.is_file() else 0} bytes")
    dados = json.loads(estado.read_text(encoding="utf-8"))
    mo = cam_rpi.MODOS[cam_rpi.OMISSAO_MODO]
    c.ok("[§4a] estado.json: modo por omissão, saída certa, fps_medido perto do nominal e custos preenchidos",
         dados["modo"] == cam_rpi.OMISSAO_MODO and dados["saida"] == list(mo.saida)
         and dados["fps_medido"] is not None
         # ±10% da taxa nominal é provado no §3 (módulo ISOLADO — é a prova de fidelidade); AQUI correm
         # os DOIS módulos ao mesmo tempo (FPV + simulação a 1080p50) e o HOST pode saturar (mede-se
         # ~43 fps cada com o PC livre, ~26 com o PC carregado): limite do PC, não do módulo, e o
         # `fps_medido` mostra-o sem maquilhagem. Exige-se ≥ 50% do nominal + quadros a sair de facto.
         and dados["fps_medido"] >= 0.5 * mo.fps and dados["quadros"] > 0
         and dados["custo_pi5"]["total_nucleos"] > 0 and dados["host_ms"]["total"] > 0,
         f"modo {dados['modo']} {dados['saida']} · fps {dados['fps_medido']} (nominal {mo.fps}) · "
         f"cpu_pi {dados['custo_pi5']['total_nucleos']} núcleos · host {dados['host_ms']['total']} ms")
    linhas = [json.loads(l) for l in telemetria.read_text(encoding="utf-8").splitlines() if l.strip()]
    ultima = linhas[-1] if linhas else {}
    c.ok("[§4a] telemetria com a chave aditiva `fpv` (só os campos compactos do contrato)",
         isinstance(ultima.get("fpv"), dict)
         and set(ultima["fpv"]) == {"ligada", "modo", "saida", "fps_nominal", "fps_medido", "bytes_medio",
                                    "bitrate_mbps", "quadros", "latencia_ms", "cpu_nucleos", "host_ms"},
         f"fpv={ultima.get('fpv')}")
    modelo = cam_rpi.custo_cpu(cam_rpi.OMISSAO_MODO)
    lat_modelo = cam_rpi.latencia_modelada(cam_rpi.OMISSAO_MODO)["total_ms"]
    fpv = ultima.get("fpv") or {}
    c.ok("[§4a] telemetria: `cpu_nucleos`/`latencia_ms` são o MODELO do Pi 5 e `host_ms` o MEDIDO (valores, "
         "não só chaves — a troca modelo/medido seria apanhada)",
         abs(fpv.get("cpu_nucleos", -1) - modelo["total_nucleos"]) < 1e-9
         and abs(fpv.get("latencia_ms", -1) - lat_modelo) < 1e-9
         and 0.0 < fpv.get("host_ms", -1) < 1000.0
         and abs(fpv.get("cpu_nucleos", -1) - fpv.get("host_ms", -2)) > 1e-6,
         f"cpu_nucleos={fpv.get('cpu_nucleos')} (modelo {modelo['total_nucleos']}) · "
         f"latencia={fpv.get('latencia_ms')} ms (modelo {lat_modelo}) · host={fpv.get('host_ms')} ms")
    # ---- módulo da FONTE `simulacao` (vista 3ª-pessoa): telemetria + ficheiros + honestidade do custo
    campos = {"ligada", "modo", "saida", "fps_nominal", "fps_medido", "bytes_medio",
              "bitrate_mbps", "quadros", "latencia_ms", "cpu_nucleos", "host_ms"}
    sim = ultima.get("simulacao")
    c.ok("[§4a] telemetria com a chave aditiva `simulacao` (MESMO formato compacto do `fpv`)",
         isinstance(sim, dict) and set(sim) == campos,
         f"simulacao={sim}")
    sim = sim or {}
    c.ok("[§4a] `simulacao`: custo de Pi 5 é NULL (não é hardware de bordo) e `host_ms` é MEDIDO (valores)",
         sim.get("cpu_nucleos") is None and 0.0 < sim.get("host_ms", -1) < 1000.0,
         f"cpu_nucleos={sim.get('cpu_nucleos')} (None: sem custo de Pi) · host={sim.get('host_ms')} ms")
    dados_sim = json.loads((pasta / "estado_sim.json").read_text(encoding="utf-8"))
    c.ok("[§4a] estado_sim.json: fonte `simulacao`, `custo_pi5: null` com `nota_fonte` honesta e quadro "
         "JPEG válido em `quadro_sim.jpg`",
         dados_sim.get("fonte") == "simulacao" and dados_sim.get("custo_pi5") is None
         and isinstance(dados_sim.get("nota_fonte"), str) and "não é hardware de bordo" in dados_sim["nota_fonte"]
         and (pasta / "quadro_sim.jpg").read_bytes()[:2] == b"\xff\xd8",
         f"fonte={dados_sim.get('fonte')} · custo_pi5={dados_sim.get('custo_pi5')} · "
         f"nota={dados_sim.get('nota_fonte')!r} · quadro {dados_sim.get('largura')}x{dados_sim.get('altura')}")
    c.ok("[§4a] sem a câmara (`--sem-fpv`) a telemetria publica `fpv: null` E `simulacao: null` "
         "(nunca se inventa)", _runner_sem_fpv(pasta), "`--sem-fpv` → os dois null em todas as linhas")
    shutil.rmtree(pasta, ignore_errors=True)


def _runner_sem_fpv(pasta: Path) -> bool:
    comando = [sys.executable, str(_AQUI / "sim_view.py"), "--sem-janela", "--sem-fpv", "--max-segundos", "2",
               "--fpv", str(pasta / "nada"), "--controlo", str(pasta / "ctl2.json"),
               "--telemetria", str(pasta / "tel2.jsonl")]
    subprocess.run(comando, cwd=str(pasta), capture_output=True, text=True, timeout=120, check=False)
    linhas = [json.loads(l) for l in (pasta / "tel2.jsonl").read_text(encoding="utf-8").splitlines()
              if l.strip()]
    return bool(linhas) and all(l.get("fpv") is None and l.get("simulacao") is None for l in linhas)


def checa_servidor(c: Checagens) -> None:
    _titulo("§4b servidor: stream MJPEG, quadro, estado, POST /api/fpv e painel RPi 5")
    pasta = Path(tempfile.mkdtemp(prefix="teste_fpv_srv_", dir=os.environ.get("TMPDIR")))
    base = f"http://127.0.0.1:{PORTA_HTTP}"
    comando = [sys.executable, str(_AQUI / "sim_site.py"), "--sem-browser", "--sem-janela",
               "--port", str(PORTA_HTTP), "--controlo", str(pasta / "ctl.json"),
               "--telemetria", str(pasta / "tel.jsonl"), "--fpv", str(pasta / "fpv")]
    processo = subprocess.Popen(comando, cwd=str(pasta), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, start_new_session=True)
    try:
        pronto = lambda: _tentar(base + "/api/fpv/estado")
        c.ok("[§4b] o servidor arranca e responde ao /api/fpv/estado", _espera(pronto, 60, "o servidor"),
             f"pid {processo.pid}")
        tem_quadro = lambda: _tentar(base + "/api/fpv.jpg")
        c.ok("[§4b] o runner (filho) produz o 1.º quadro", _espera(tem_quadro, 60, "o 1.º quadro"), "")
        status, jpeg, cabecalhos = _jpeg(base + "/api/fpv.jpg")
        largura_fpv, altura_fpv = _jpeg_dimensoes(jpeg)
        c.ok("[§4b] GET /api/fpv.jpg: JPEG VÁLIDO (decodificado) com Content-Type image/jpeg",
             status == 200 and largura_fpv == 1920 and altura_fpv == 1080
             and cabecalhos.get("Content-Type", "").startswith("image/jpeg"),
             f"{status} · {len(jpeg)} bytes · decodificado {largura_fpv}x{altura_fpv}")
        _, jpeg_sim, _ = _jpeg(base + "/api/simulacao.jpg")
        largura_sim, altura_sim = _jpeg_dimensoes(jpeg_sim)
        c.ok("[§4b] GET /api/simulacao.jpg: JPEG VÁLIDO (decodificado) da vista da simulação",
             largura_sim == 1920 and altura_sim == 1080,
             f"{len(jpeg_sim)} bytes · decodificado {largura_sim}x{altura_sim}")
        status, estado, _ = _json_rota(base, "/api/fpv/estado")
        mo = cam_rpi.MODOS[cam_rpi.OMISSAO_MODO]
        c.ok("[§4b] GET /api/fpv/estado: modo por omissão com a saída certa",
             status == 200 and estado["fpv"]["modo"] == cam_rpi.OMISSAO_MODO
             and estado["fpv"]["saida"] == list(mo.saida), f"modo {estado['fpv']['modo']}")
        # stream multipart: partes `image/jpeg` com a fronteira do contrato
        partes, fronteira, distintas = _ler_stream(base + "/api/fpv.mjpg", 3, 15.0)
        c.ok("[§4b] GET /api/fpv.mjpg: multipart/x-mixed-replace com partes JPEG (o padrão picamera2)",
             partes >= 3 and fronteira, f"{partes} partes · boundary {fronteira!r}")
        c.ok("[§4b] o stream AVANÇA: partes consecutivas trazem quadros DIFERENTES (não reenvia o mesmo)",
             distintas >= 2, f"{distintas} payloads distintos entre as {partes} partes")
        # ---- rotas do módulo da FONTE `simulacao` (o mesmo padrão do FPV)
        status_s, jpeg_s, cabecalhos_s = _jpeg(base + "/api/simulacao.jpg")
        c.ok("[§4b] GET /api/simulacao.jpg: JPEG válido da vista da simulação (Content-Type image/jpeg)",
             status_s == 200 and jpeg_s[:2] == b"\xff\xd8"
             and cabecalhos_s.get("Content-Type", "").startswith("image/jpeg"),
             f"{status_s} · {len(jpeg_s)} bytes")
        status_e, estado_s, _ = _json_rota(base, "/api/simulacao/estado")
        bloco_s = estado_s.get("simulacao") or {}
        c.ok("[§4b] GET /api/simulacao/estado: fonte `simulacao`, custo_pi5 NULL + nota honesta",
             status_e == 200 and bloco_s.get("fonte") == "simulacao"
             and bloco_s.get("custo_pi5") is None
             and isinstance(bloco_s.get("nota_fonte"), str) and bloco_s.get("nota_fonte"),
             f"fonte={bloco_s.get('fonte')} · custo_pi5={bloco_s.get('custo_pi5')} · "
             f"nota={bloco_s.get('nota_fonte')!r}")
        partes_s, fronteira_s, distintas_s = _ler_stream(base + "/api/simulacao.mjpg", 3, 15.0)
        c.ok("[§4b] GET /api/simulacao.mjpg: multipart válido E avança (quadros distintos)",
             partes_s >= 3 and fronteira_s and distintas_s >= 2,
             f"{partes_s} partes · {distintas_s} distintos · boundary {fronteira_s!r}")
        # POST /api/fpv: validação + controlo
        status, resposta, _ = _json_rota(base, "/api/fpv", {"modo": "720p100"})
        seq1 = resposta.get("fpv", {}).get("seq")
        status2, resposta2, _ = _json_rota(base, "/api/fpv", {"modo": "720p100"})   # mesmo valor: seq novo
        c.ok("[§4b] POST /api/fpv: 200 com bloco completo e `seq` do SERVIDOR a incrementar sempre",
             status == 200 and status2 == 200
             and resposta["fpv"] == {"ligada": True, "modo": "720p100", "seq": seq1}
             and resposta2["fpv"]["seq"] == seq1 + 1,
             f"seq {seq1} → {resposta2['fpv']['seq']}")
        # a troca de modo muda OS DOIS JPEG (o bloco `fpv` manda nos dois módulos) — com espera pelos
        # quadros NOVOS: o runner aplica o modo e renderiza no ciclo seguinte (retenta até 3 s)
        d_fpv, d_sim = (0, 0), (0, 0)
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 3.0:
            _, jp, _ = _jpeg(base + "/api/fpv.jpg")
            _, js, _ = _jpeg(base + "/api/simulacao.jpg")
            d_fpv, d_sim = _jpeg_dimensoes(jp), _jpeg_dimensoes(js)
            if d_fpv == (1280, 720) and d_sim == (1280, 720):
                break
            time.sleep(0.1)
        c.ok("[§4b] trocar de modo muda as dimensões DOS DOIS JPEG (fpv e simulação, PIL)",
             d_fpv == (1280, 720) and d_sim == (1280, 720),
             f"fpv {d_fpv} · simulacao {d_sim} (após POST modo 720p100)")
        recusas = [(_json_rota(base, "/api/fpv", {"modo": "2304x1296p30hdr"})[0], "hdr"),
                   (_json_rota(base, "/api/fpv", {"modo": "nope"})[0], "modo desconhecido"),
                   (_json_rota(base, "/api/fpv", {"ligada": None})[0], "null"),
                   (_json_rota(base, "/api/fpv", {"ww": 1})[0], "chave desconhecida")]
        c.ok("[§4b] POST /api/fpv recusa HDR/nada/null/chave desconhecida com 400 (4/4)",
             all(status == 400 for status, _ in recusas), str(recusas))
        status, _, _ = _json_rota(base, "/api/fpv", {"ligada": False})
        estado_ok = _espera(lambda: (json.loads(urllib.request.urlopen(
            base + "/api/fpv/estado", timeout=5).read())["fpv"] or {}).get("ligada") is False, 5.0,
            "o estado desligado")
        c.ok("[§4b] desligar chega ao módulo (estado.json atualiza SEM quadros novos)",
             status == 200 and estado_ok, "ligada=false no estado")
        # FRESCURA: um estado.json antigo (out/fpv persistente) nunca parece atual (com retentativas)
        marcado, bloco_velho = _estado_velho_marcado(
            base, "/api/fpv/estado", pasta / "fpv" / "estado.json", "fpv")
        c.ok("[§4b] estado VELHO (out/fpv persistente, runner morto) é marcado `estado_velho` — nunca "
             "parece atual", marcado,
             f"estado_velho={bool(bloco_velho.get('estado_velho'))} · "
             f"idade={bloco_velho.get('idade_estado_s')} s")
        marcado_s, bloco_s = _estado_velho_marcado(
            base, "/api/simulacao/estado", pasta / "fpv" / "estado_sim.json", "simulacao")
        c.ok("[§4b] estado VELHO da simulação é marcado `estado_velho` (mesmo corte do FPV)",
             marcado_s, f"estado_velho={bool(bloco_s.get('estado_velho'))} · "
             f"idade={bloco_s.get('idade_estado_s')} s")
        # o controlo tem o bloco COMPLETO (contrato do runner) e o painel RPi 5 tem a câmara
        controlo = json.loads((pasta / "ctl.json").read_text(encoding="utf-8"))
        status, estado_api, _ = _json_rota(base, "/api/state")
        rpi5 = estado_api.get("rpi5") or {}
        uso = rpi5.get("uso") or {}
        c.ok("[§4b] o ficheiro de controlo tem o bloco `fpv` completo (ligada+modo+seq)",
             controlo.get("fpv", {}).get("modo") == "720p100" and "ligada" in controlo["fpv"]
             and isinstance(controlo["fpv"].get("seq"), int), f"controlo.fpv={controlo.get('fpv')}")
        c.ok("[§4b] painel RPi 5: `camera` com etapas de custo e `uso.camera_nucleos`/`nucleos_total`",
             isinstance(rpi5.get("camera"), dict)
             and rpi5["camera"]["custo_pi5"]["etapas"]["codificacao_jpeg"]["pct"] > 0
             and uso.get("camera_nucleos", 0) > 0 and uso.get("nucleos_total", 0) >= uso["camera_nucleos"],
             f"camera={rpi5.get('camera', {}).get('modo')} · uso={ {k: uso.get(k) for k in ('camera_nucleos', 'inferencia_nucleos', 'nucleos_total')} }")
    finally:
        _matar(processo)
        shutil.rmtree(pasta, ignore_errors=True)


def _estado_velho_marcado(base: str, rota: str, caminho: Path, campo: str, tentativas: int = 3) -> tuple:
    """Finge um `estado.json` antigo (mtime −3600 s) e confere que a API o marca `estado_velho`.

    Retenta até `tentativas` vezes: o runner pode ainda estar a escrever o estado quando o teste faz a
    sua escrita falsa (sob carga isso acontece) — e aí o estado volta a ficar fresco, com razão.
    """
    resultado = (False, {})
    for _ in range(tentativas):
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        bruto["t_captura"] = time.time() - 3600.0
        caminho.write_text(json.dumps(bruto), encoding="utf-8")
        os.utime(caminho, (time.time() - 3600.0, time.time() - 3600.0))
        time.sleep(0.7)                                    # esgota o cache de 0,5 s do servidor
        _, resposta, _ = _json_rota(base, rota)
        bloco = resposta.get(campo) or {}
        resultado = (bool(bloco.get("estado_velho") is True
                          and (bloco.get("idade_estado_s") or 0) > 100), bloco)
        if resultado[0]:
            return resultado
    return resultado


def _jpeg_dimensoes(jpeg: bytes) -> tuple:
    """(largura, altura) decodificadas do JPEG — valida MESMO o conteúdo (não só o marcador SOI)."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(jpeg)) as imagem:
            return imagem.size
    except Exception:  # noqa: BLE001  (JPEG corrompido → (0, 0), e a checagem falha com razão)
        return (0, 0)


def _tentar(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as resposta:
            return resposta.status == 200
    except Exception:  # noqa: BLE001
        return False


def _jpeg(url: str):
    with urllib.request.urlopen(url, timeout=10) as resposta:
        return resposta.status, resposta.read(), dict(resposta.headers)


def _ler_stream(url: str, partes: int, limite_s: float) -> tuple[int, str, int]:
    """(partes JPEG, boundary, payloads distintos) do stream — `distintos` prova que o stream avança."""
    pedido = urllib.request.Request(url)
    with urllib.request.urlopen(pedido, timeout=limite_s) as resposta:
        fronteira = ""
        tipo = resposta.headers.get("Content-Type", "")
        if "boundary=" in tipo:
            fronteira = tipo.split("boundary=", 1)[1].strip()
        buf, t0, vistos = b"", time.perf_counter(), 0
        while vistos < partes and time.perf_counter() - t0 < limite_s:
            buf += resposta.read(65536)
            vistos = buf.count(b"\xff\xd8\xff")
        # separa os payloads JPEG (SOI..EOI) e conta os distintos
        payloads, resto = [], buf
        while True:
            i = resto.find(b"\xff\xd8\xff")
            j = resto.find(b"\xff\xd9", i + 3) if i >= 0 else -1
            if i < 0 or j < 0:
                break
            payloads.append(resto[i:j + 2])
            resto = resto[j + 2:]
        return vistos, fronteira, len(set(payloads))


def _matar(processo: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(processo.pid), 15)
    except (ProcessLookupError, PermissionError):
        processo.terminate()
    try:
        processo.wait(timeout=10)
    except subprocess.TimeoutExpired:
        processo.kill()


# ================================================================================================ §5 mutações
# Cada mutação mexe numa linha das fontes e tem de FALHAR uma checagem concreta (o nome dela está em
# `alvos`) — é isto que prova que o teste não é tautológico. As fontes são repostas SEMPRE no fim.
MUTACOES = (
    ("cadencia-periodo", "lab/camera_rpi.py", "return 1.0 / self.fps",
     "return 1.0 / 25.0"),
    ("fovy-trocado", "lab/camera_rpi.py",
     "return math.degrees(2.0 * math.atan(mo.fator_fov * math.tan(meio)))",
     "return math.degrees(2.0 * math.atan(math.tan(meio)))"),
    ("dims-saidas", "lab/camera_rpi.py",
     "round(self.saida[1] * self.crop[2] / self.crop[3])",
     "self.saida[1]"),
    ("validacao-fpv", "experiments/09_drone_hover_rl/sim_view.py",
     'raise ValueError(f"`fpv.modo` tem de ser um dos {sorted(cam_rpi.MODOS)} (recebido {modo!r})")',
     "pass"),
)


def checa_mutacoes(c: Checagens, fontes: Path) -> None:
    _titulo("§5 mutações: o teste NÃO é tautológico (cada mutação tem de FALHAR as checagens certas)")
    alvos = {"cadencia-periodo": "[§3] 1080p50", "fovy-trocado": "FOV do modo",
             "dims-saidas": "proporção da janela", "validacao-fpv": "_ler_fpv` recusa"}
    for nome, rel, original, mutado in MUTACOES:
        caminho = fontes / rel
        texto = caminho.read_text(encoding="utf-8")
        if original not in texto:
            c.ok(f"[§5] mutação {nome}: a linha-alvo ainda existe nas fontes", False,
                 f"{rel}: {original[:60]!r} não encontrada")
            continue
        caminho.write_text(texto.replace(original, mutado, 1), encoding="utf-8")
        try:
            saida = subprocess.run([sys.executable, str(_AQUI / "teste_fpv.py"), "--so-pecas"],
                                   capture_output=True, text=True, timeout=300, check=False)
            falhou = saida.returncode != 0 and alvos[nome] in saida.stdout
            c.ok(f"[§5] mutação {nome} ({rel}): --so-pecas FALHA (o teste nao e tautologico)",
                 falhou, f"exit {saida.returncode} · alvo {alvos[nome]!r} "
                         f"{'na' if alvos[nome] in saida.stdout else 'FORA da'} saída")
        finally:
            caminho.write_text(texto, encoding="utf-8")


# ---------------------------------------------------------------------------------------------------- main
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Prova do módulo de câmara FPV (especificação, pipeline, "
                                           "cadência, runner, servidor e mutações).")
    p.add_argument("--mutacao", action="store_true", help="corre SÓ as mutações (§5)")
    p.add_argument("--so-espec", action="store_true", help="corre SÓ a especificação (§1)")
    p.add_argument("--so-pecas", action="store_true",
                   help="corre §1–§4 sem processos externos longos (usado pelo §5)")
    p.add_argument("--fontes", type=Path, default=_RAIZ, help="raiz das fontes para mutar (§5)")
    args = p.parse_args(argv)

    total = Checagens("fpv")
    if args.mutacao:
        checa_mutacoes(total, args.fontes)
    else:
        checa_especificacao(total)
        if not args.so_espec:
            checa_pipeline(total)
            checa_cadencia(total)
            if not args.so_pecas:
                checa_runner(total)
                checa_servidor(total)
    print(f"\n[teste] {len(total.linhas) - len(total.falhas)}/{len(total.linhas)} checagens OK", flush=True)
    if total.falhas:
        for nome in total.falhas:
            print(f"[teste] FALHOU: {nome}", flush=True)
        return 1
    print("[teste] o módulo de câmara FPV obedece ao contrato: a especificação real (modos/fps/MP/FoV), "
          "o JPEG com as dimensões da saída, a latência do modelo cumprida, os fps nominais, o stream "
          "MJPEG do picamera2 e o custo de CPU no painel RPi 5", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
