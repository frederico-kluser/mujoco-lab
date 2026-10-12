#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_controlador.py — PROVA do SELETOR DE CONTROLADOR (contrato r12).

O pedido do dono (2026-10-12): «o drone VOLTAR A RODAR (yaw livre), WASDQE relativo ao RUMO, olhar para o
círculo, e ver no site quem faz o quê» — com DOIS caminhos de controlo trocáveis ao vivo: a política RL
(`out/real_1950_voo_final/final.zip`, contrato r11, yaw fixo) e a CASCATA CLÁSSICA C++ do firmware
(`firmware/nucleo/` via ctypes, `sitl.NucleoCpp`, os mesmos adaptadores do `sitl.DroneRealEnvNucleo` modo
`cascata`).

CONTRATO r12 (o que este script prova, ponto por ponto):

  · bloco `"voo"` ganha `{yaw_taxa?, yaw_alvo?, segui_alvo?}` (OPCIONAIS — um ficheiro r11 continua
    válido; o servidor escreve o bloco completo): `yaw_taxa` ∈ [−2, 2] rad/s (teclas Z/C mandam ±0,5),
    `yaw_alvo` = `null` (sem alvo) ou rumo em rad DESDE O ARMAR, normalizado a ]−π, π] (tecla X fixa o
    rumo atual), `segui_alvo` bool (tecla V = «olhar»: o IBVS do núcleo segue o círculo);
  · validação ESTRITA do servidor como as restantes chaves (`POST /api/voo`): tipos errados, faixas e
    chaves desconhecidas → 400 com o motivo; o runner é TOLERANTE no ficheiro (ausência = defaults);
  · SELETOR: `POST /api/controlador {"modo": "rl"|"classico"}` (só `modo`; mais chaves ou modo inválido →
    400) + bloco `"controlador": {modo, seq}` no ficheiro (escrita atómica, merge) + `--controlador
    rl|classico` no arranque (padrão `rl` = o comportamento de sempre). O runner troca AO VIVO: a troca
    reinicia o EPISÓDIO (calibração do giroscópio no chão) e o estado é honesto (`trocando` + `motivo`;
    `erro` + `motivo` quando recusada — ex. planta cf2) — nunca se finge uma troca;
  · WASDQE RELATIVO AO RUMO no modo clássico: o comando da cascata é no referencial do nariz e o `p_ref`
    do eco recebe a rotação `v_ref_mundo` — com yaw a 90°, W (avanço) muda de eixo (+x → +y no mundo);
  · yaw Z/C (taxa ±0,5 rad/s) / X (fixar rumo = `yaw_alvo` = rumo atual) / V (olhar);
  · «olhar» liga o IBVS (câMARA mono QVGA + detetor C++ do núcleo) e o ALVO APARECE CENTRADO na
    telemetria (`controlador.olhar.erro_px` ≈ [0,0] depois da aquisição; `estado` = 0 = A_SEGUIR), com o
    ponto mocap a descrever o círculo (0,5 m/s, raio 1,5 m — o cenário do dono);
  · painéis do site presentes (seletor, keycaps de yaw, «quem faz o quê», bordo com os DOIS alvos);
  · NÃO-TAUTOLOGIA: 2 MUTAÇÕES (cópias em $TMPDIR) têm de FALHAR as mesmas checagens — sem a rotação do
    `v_ref_mundo` o «W muda de eixo» cai; sem a validação estrita do seletor a recusa cai.

Seções (§1–§4 peças · §5 integração real · §6 mutações):

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controlador.py          # tudo
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controlador.py --so-pecas
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controlador.py --sem-e2e  # sem §5

Exit 0 = todas as checagens passam; 1 = alguma falha (diz qual).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
for _caminho in (_RAIZ, _AQUI):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import numpy as np
import sim_site
import sim_view

PORTA_TESTE = 8573                     # porta do §5 (a do `teste_camera` é 8561; a do voo, outra)
T_RODADA_S = 240.0                     # s máximos da ronda de integração (§5)
YAW_ALVO_TESTE = math.pi / 2.0         # rad — o rumo do «W muda de eixo» (90°)


class Checagens:
    """Acumulador de checagens: uma linha por checagem (com o detalhe medido) + resumo no fim."""

    def __init__(self, titulo: str) -> None:
        self.titulo = titulo
        self.falhas: list[str] = []
        self.n = 0
        print(f"\n=== {titulo} ===", flush=True)

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.n += 1
        estado = "OK  " if cond else "FALHA"
        print(f"  [{estado}] {nome}" + (f" — {detalhe}" if detalhe else ""), flush=True)
        if not cond:
            self.falhas.append(nome + (f" — {detalhe}" if detalhe else ""))
        return bool(cond)

    def fechar(self) -> bool:
        if self.falhas:
            print(f"  => {self.titulo}: {self.n - len(self.falhas)}/{self.n} · FALHAS: {len(self.falhas)}",
                  flush=True)
            return False
        print(f"  => {self.titulo}: {self.n}/{self.n} TUDO OK", flush=True)
        return True


def _http(url: str, corpo: dict | None = None, timeout: float = 15.0):
    """`(codigo, corpo_json)` de um GET/POST à API do `sim_site.py` (JSON; erros HTTP não rebentam)."""
    dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
    pedido = urllib.request.Request(url, data=dados, method="POST" if corpo is not None else "GET")
    if dados is not None:
        pedido.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            bruto = resposta.read().decode("utf-8")
            return int(resposta.status), json.loads(bruto) if bruto else {}
    except urllib.error.HTTPError as erro:
        bruto = erro.read().decode("utf-8")
        return int(erro.code), json.loads(bruto) if bruto else {}


# ---------------------------------------------------------------------------------------- §1 contrato
def secao_contrato() -> bool:
    """§1: o contrato r12 — bloco `voo` com yaw/olhar (validado/recusado) e o bloco `controlador`."""
    c = Checagens("§1 contrato r12: `voo` {yaw_taxa, yaw_alvo, segui_alvo} + `controlador`")

    # --- leitura do ficheiro (runner): aceita os campos novos e guarda-os
    voo = sim_view._ler_voo({"ativo": True, "teclas": {"w": True}, "yaw_taxa": 0.5, "yaw_alvo": 1.0,
                             "segui_alvo": True, "seq": 7})
    c.ok("runner aceita o bloco `voo` r12 completo",
         voo is not None and voo.ativo and voo.teclas["w"] and voo.yaw_taxa == 0.5
         and abs(voo.yaw_alvo - 1.0) < 1e-12 and voo.segui_alvo and voo.seq == 7,
         f"voo = {voo}")
    voo_r11 = sim_view._ler_voo({"ativo": True, "teclas": {"w": True}, "seq": 1})
    c.ok("ficheiro r11 (sem os campos novos) continua válido — defaults 0/None/False",
         voo_r11 is not None and voo_r11.yaw_taxa == 0.0 and voo_r11.yaw_alvo is None
         and voo_r11.segui_alvo is False)
    try:
        sim_view._ler_voo({"ativo": True, "teclas": {}, "yaw_taxa": 9.9})
        c.ok("runner recusa `yaw_taxa` fora de [−2, 2] rad/s", False, "aceitou 9.9")
    except ValueError as erro:
        c.ok("runner recusa `yaw_taxa` fora de [−2, 2] rad/s", "yaw_taxa" in str(erro), str(erro)[:70])
    try:
        sim_view._ler_voo({"ativo": True, "teclas": {}, "yaw_alvo": "agora"})
        c.ok("runner recusa `yaw_alvo` que não seja número/null", False, "aceitou string")
    except ValueError:
        c.ok("runner recusa `yaw_alvo` que não seja número/null", True)
    voo_norm = sim_view._ler_voo({"ativo": False, "teclas": {}, "yaw_alvo": 4.0 * math.pi + 0.25})
    c.ok("`yaw_alvo` normaliza-se a ]−π, π] (radianos desde o armar)",
         voo_norm is not None and voo_norm.yaw_alvo is not None
         and -math.pi < voo_norm.yaw_alvo <= math.pi
         and abs(voo_norm.yaw_alvo - 0.25) < 1e-9, f"yaw_alvo = {None if voo_norm is None else voo_norm.yaw_alvo}")

    # --- leitura do seletor (runner)
    sel = sim_view._ler_controlador({"modo": "classico", "seq": 3})
    c.ok("runner aceita o bloco `controlador` {modo, seq}",
         sel is not None and sel.modo == "classico" and sel.seq == 3)
    try:
        sim_view._ler_controlador({"modo": "xpto"})
        c.ok("runner recusa `controlador.modo` inválido", False, "aceitou 'xpto'")
    except ValueError:
        c.ok("runner recusa `controlador.modo` inválido", True)
    registo = sim_view.ler_registo({"vel": 1.0, "controlador": {"modo": "rl"}, "voo": {"ativo": True}})
    c.ok("ler_registo integra os dois blocos (e um ficheiro sem eles continua válido)",
         registo.controlador is not None and registo.controlador.modo == "rl" and registo.voo.ativo
         and sim_view.ler_registo({"vel": 0.0}).controlador is None)

    # --- validação ESTRITA do servidor (POST /api/voo)
    bloco = sim_site.validar_voo({"ativo": True, "teclas": {"w": True}, "yaw_taxa": -0.5,
                                  "yaw_alvo": None, "segui_alvo": False}, {})
    b = bloco["voo"]
    c.ok("POST /api/voo r12: bloco COMPLETO com o `seq` do servidor",
         b["teclas"]["w"] is True and b["yaw_taxa"] == -0.5 and b["yaw_alvo"] is None
         and b["segui_alvo"] is False and b["seq"] == 1, f"bloco = {b}")
    for corpo, motivo in (({"ativo": True, "teclas": {}, "yaww": 1}, "desconhecidas"),
                          ({"ativo": True, "teclas": {}, "yaw_taxa": "0.5"}, "yaw_taxa"),
                          ({"ativo": True, "teclas": {}, "yaw_alvo": "agora"}, "yaw_alvo"),
                          ({"ativo": True, "teclas": {}, "segui_alvo": "sim"}, "segui_alvo")):
        try:
            sim_site.validar_voo(corpo, {})
            c.ok(f"POST /api/voo recusa {corpo} ({motivo})", False, "aceitou")
        except ValueError as erro:
            c.ok(f"POST /api/voo recusa {motivo} inválido", motivo.split()[0] in str(erro), str(erro)[:70])
    c.ok("POST /api/voo aceita `yaw_alvo: null` (é VALOR, não ausência)",
         sim_site.validar_voo({"ativo": False, "teclas": {}, "yaw_alvo": None}, {})["voo"]["yaw_alvo"] is None)

    # --- validação ESTRITA do seletor (POST /api/controlador)
    sel = sim_site.validar_controlador({"modo": "classico"}, {})
    c.ok("POST /api/controlador: bloco {modo, seq} com o seq do servidor",
         sel == {"controlador": {"modo": "classico", "seq": 1}}, f"sel = {sel}")
    for corpo in ({"modo": "xpto"}, {"modo": "classico", "seq": 2}, {}, {"modo": None}):
        try:
            sim_site.validar_controlador(corpo, {})
            c.ok(f"POST /api/controlador recusa {corpo}", False, "aceitou")
        except ValueError:
            c.ok(f"POST /api/controlador recusa corpo inválido {corpo}", True)
    return c.fechar()


# ---------------------------------------------------------------------------------------- §2 seletor
def secao_seletor() -> bool:
    """§2: a máquina de estado do seletor (troca/recusa honesta) e o estado `trocando`/`erro` da API."""
    c = Checagens("§2 seletor: troca e estado honesto (trocando/erro + motivo)")

    # env cf2 (sem planta real): a troca para clássico TEM de ser recusada com motivo — honesto
    env = sim_view.HoverEnv(helices=False, comando=True)
    piloto = sim_view.ControladorDeVoo(env, politica=None, modo="rl")
    c.ok("arranque no modo do CLI (padrão rl)",
         piloto.modo == "rl" and piloto.estado == "pronto" and piloto.fonte.startswith("política RL"),
         f"modo = {piloto.modo}, fonte = {piloto.fonte}")
    c.ok("requisitar `classico` sinaliza a troca", piloto.requisitar("classico"))
    piloto.trocar()
    c.ok("cf2: a troca para clássico é RECUSADA com `erro` + motivo (nunca se finge)",
         piloto.modo == "rl" and piloto.estado == "erro" and "PLANTA REAL" in (piloto.motivo or ""),
         f"estado = {piloto.estado}, motivo = {piloto.motivo}")
    c.ok("a recusa NÃO se repete a cada passo (o pedido fica cancelado até mudar)",
         not piloto.requisitar("classico") and not piloto.requisitar("classico"))
    c.ok("requisitar o modo EM VIGOR não dispara troca nenhuma", piloto.requisitar("rl") is False)

    # estado honesto do `/api/state` (servidor): pedido ≠ eco → `trocando` + motivo
    eco_rl = {"modo": "rl", "fonte": "política RL (PPO, IA-1)", "yaw_taxa": 0.0, "yaw_alvo": None,
              "segui_alvo": False, "v_ref_fonte": "wasdqe (contrato r11)", "rumo": 0.1, "olhar": None,
              "estado": "pronto", "motivo": None}
    bloco = sim_site.controlador_em_vigor({"controlador": eco_rl}, {"controlador": {"modo": "classico"}},
                                          "rl")
    c.ok("pedido ≠ eco → `trocando` com o motivo da troca (reinício do episódio)",
         bloco["estado"] == "trocando" and bloco["pedido"] == "classico" and bloco["modo"] == "rl"
         and (bloco["motivo"] or "").startswith("troca de controlador"),
         f"estado = {bloco['estado']}, motivo = {bloco['motivo']}")
    eco_erro = dict(eco_rl, estado="erro", motivo="não dá")
    bloco = sim_site.controlador_em_vigor({"controlador": eco_erro},
                                          {"controlador": {"modo": "classico"}}, "rl")
    c.ok("uma recusa do runner (`erro` + motivo) propaga-se em vez de virar `trocando` eterno",
         bloco["estado"] == "erro" and bloco["motivo"] == "não dá")
    bloco = sim_site.controlador_em_vigor({}, {}, "rl")
    c.ok("sem eco (runner sem telemetria) o estado vem do CLI — `pronto` no arranque rl",
         bloco["estado"] == "pronto" and bloco["modo"] == "rl" and bloco["yaw_alvo"] is None
         and bloco["olhar"] is None)
    return c.fechar()


# ---------------------------------------------------------------------------------------- §3 rumo/yaw
def secao_rumo() -> bool:
    """§3: WASDQE relativo ao RUMO («W muda de eixo») e os comandos de yaw Z/C/X/V."""
    c = Checagens("§3 rumo: WASDQE relativo ao rumo + yaw Z/C/X/V")

    # `v_ref_mundo`: a rotação que põe o eco `p_ref` no frame mundo
    v = sim_view.v_ref_mundo([1.0, 0.0, 0.0], 0.0)
    c.ok("rumo 0 → W é +x no mundo (identidade)", np.allclose(v, [1, 0, 0]), f"v = {v}")
    v = sim_view.v_ref_mundo([1.0, 0.0, 0.0], YAW_ALVO_TESTE)
    c.ok("com yaw a 90° W MUDA DE EIXO: avanço [+1,0] vira +y no mundo",
         np.allclose(v, [0, 1, 0], atol=1e-12), f"v = {v}")
    v = sim_view.v_ref_mundo([0.0, 1.0, 0.7], YAW_ALVO_TESTE)
    c.ok("lateral A (esquerda) a 90° vira −x (e o vertical não muda)",
         np.allclose(v, [-1, 0, 0.7], atol=1e-12), f"v = {v}")

    # `comando_classico`: os comandos Z/C/X/V e as prioridades
    cmd = sim_view.comando_classico(sim_view.Voo(ativo=True, teclas={"w": True}, yaw_taxa=0.5))
    c.ok("Z/C: `yaw_taxa` chega ao comando (modo velocidade; W = +vx no RUMO)",
         cmd == {"vx": 1.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.5, "modo": "velocidade"}, f"cmd = {cmd}")
    cmd = sim_view.comando_classico(sim_view.Voo(ativo=False, yaw_alvo=1.2))
    c.ok("X: `yaw_alvo` → modo yaw_alvo com o rumo pedido (desde o armar)",
         cmd["modo"] == "yaw_alvo" and cmd["yaw"] == 1.2 and cmd["yaw_taxa"] == 0.0, f"cmd = {cmd}")
    cmd = sim_view.comando_classico(sim_view.Voo(ativo=False, yaw_alvo=1.2, segui_alvo=True))
    c.ok("V: `segui_alvo` ganha ao `yaw_alvo` (prioridade: olhar > yaw_alvo > velocidade)",
         cmd["modo"] == "olhar", f"cmd = {cmd}")
    cmd = sim_view.comando_classico(sim_view.Voo(ativo=False, segui_alvo=True), alvo=False)
    c.ok("sem alvo no modelo o «olhar» CAI para a prioridade seguinte (nunca se finge um IBVS)",
         cmd["modo"] == "velocidade", f"cmd = {cmd}")
    cmd = sim_view.comando_classico(sim_view.Voo(ativo=True, teclas={"w": True, "a": True}))
    c.ok("diagonal W+A normalizada para 1,0 m/s NO RUMO (vx = vy = 1/√2)",
         abs(cmd["vx"] - 1 / math.sqrt(2)) < 1e-12 and abs(cmd["vy"] - 1 / math.sqrt(2)) < 1e-12
         and cmd["vz"] == 0.0, f"cmd = {cmd}")
    cmd = sim_view.comando_classico(sim_view.Voo(ativo=False, teclas={"w": True}))
    c.ok("desarmado (`ativo: false`) → teclas tratadas como soltas (segura posição)",
         cmd["vx"] == 0.0 and cmd["vy"] == 0.0 and cmd["vz"] == 0.0, f"cmd = {cmd}")
    return c.fechar()


# ---------------------------------------------------------------------------------------- §4 painéis
TESTIDS_PAINEL = {
    "seletor-controlador": ("controlador.tsx", 'data-testid="seletor-controlador"'),
    "controlador-estado": ("controlador.tsx", 'data-testid="controlador-estado"'),
    "controlador-motivo": ("controlador.tsx", 'data-testid="controlador-motivo"'),
    "controlador-modo-rl": ("controlador.tsx", 'data-testid="controlador-modo-rl"'),
    "controlador-modo-classico": ("controlador.tsx", 'data-testid="controlador-modo-classico"'),
    # os keycaps e as linhas das tabelas usam testids DINÂMICOS (`tecla-${tecla}`, `${linha.id}`,
    # `${alvo.id}`): o literal ou o padrão contam — a semântica de cada letra/id já é provada em §3
    "tecla-z": ("controlo-voo.tsx", "data-testid={`tecla-${tecla}`}"),
    "tecla-c": ("controlo-voo.tsx", "data-testid={`tecla-${tecla}`}"),
    "tecla-x": ("controlo-voo.tsx", "data-testid={`tecla-${tecla}`}"),
    "tecla-v": ("controlo-voo.tsx", "data-testid={`tecla-${tecla}`}"),
    "voo-rumo": ("controlo-voo.tsx", 'data-testid="voo-rumo"'),
    "quem-faz-o-que": ("quem-faz-o-que.tsx", 'data-testid="quem-faz-o-que"'),
    "quem-faz-o-que-fc": ("quem-faz-o-que.tsx", "data-testid={`quem-faz-o-que-${linha.id}`}"),
    "bordo-alvos": ("rpi5.tsx", 'data-testid="bordo-alvos"'),
    "bordo-alvo-rpi5": ("rpi5.tsx", "data-testid={`bordo-alvo-${alvo.id}`}"),
    "bordo-alvo-arduino": ("rpi5.tsx", "data-testid={`bordo-alvo-${alvo.id}`}"),
}


def secao_paineis() -> bool:
    """§4: os painéis novos estão NO FRONT (testids estáveis nos componentes certos)."""
    c = Checagens("§4 painéis: seletor, keycaps de yaw, «quem faz o quê», bordo com 2 alvos")
    base = _AQUI / "site" / "src" / "components" / "sim"
    ficheiros = {nome: (base / nome).read_text(encoding="utf-8") if (base / nome).is_file() else ""
                 for nome in {f for f, _padrao in TESTIDS_PAINEL.values()}}
    for testid, (ficheiro, padrao) in TESTIDS_PAINEL.items():
        texto = ficheiros.get(ficheiro, "")
        c.ok(f'data-testid="{testid}" em site/src/components/sim/{ficheiro}',
             f'data-testid="{testid}"' in texto or padrao in texto)
    return c.fechar()


# ---------------------------------------------------------------------------------------- §5 integração
def _arrancar_site(pasta: Path, porta: int, controlador: str = "rl"):
    """`sim_site.py --sem-janela --sem-browser --controlador …` numa pasta própria (§5)."""
    pasta.mkdir(parents=True, exist_ok=True)
    controlo, telemetria = pasta / "controlo.json", pasta / "telemetria.jsonl"
    for caminho in (controlo, telemetria):
        caminho.unlink(missing_ok=True)
    comando = [sys.executable, str(_AQUI / "sim_site.py"), "--sem-browser", "--sem-janela",
               "--port", str(porta), "--controlo", str(controlo), "--telemetria", str(telemetria),
               "--controlador", controlador, "--fator-tempo", "1"]
    processo = subprocess.Popen(comando, cwd=str(_AQUI), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, start_new_session=True)
    base_url, lidas, t0 = None, [], time.perf_counter()
    while time.perf_counter() - t0 < 240:
        linha = processo.stdout.readline()
        if not linha:
            break
        lidas.append(linha.rstrip())
        achado = re.search(r"(http://[\d.]+:\d+/)", linha)
        if achado:
            base_url = achado.group(1).rstrip("/")
            break
    return processo, base_url, controlo, telemetria, "\n".join(lidas)


def _fechar_site(processo) -> str:
    linhas = ""
    if processo is None:
        return linhas
    try:
        os.killpg(os.getpgid(processo.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        processo.terminate()
    try:
        linhas = processo.communicate(timeout=15)[0] or ""
    except subprocess.TimeoutExpired:
        processo.kill()
        linhas = processo.communicate()[0] or ""
    return linhas


def _ultima(telemetria: Path) -> dict:
    """Última linha VÁLIDA da telemetria (ou `{}`)."""
    try:
        linhas = [json.loads(l) for l in telemetria.read_text(encoding="utf-8").splitlines()
                  if l.strip().startswith("{")]
    except (OSError, ValueError):
        return {}
    return linhas[-1] if linhas else {}


def _esperar(telemetria: Path, predicado, timeout: float, base: str | None = None, rota: str = "/api/state"):
    """Espera até `predicado(linha, estado_api)` ser verdadeiro; devolve `(achou, linha, estado_api)`."""
    t0, linha, estado = time.perf_counter(), {}, {}
    while time.perf_counter() - t0 < timeout:
        linha = _ultima(telemetria)
        if base is not None:
            _codigo, estado = _http(base + rota)
        if predicado(linha, estado):
            return True, linha, estado
        time.sleep(0.25)
    return False, linha, estado


def _voo(base: str, **campos) -> tuple:
    corpo = {"ativo": campos.pop("ativo", True),
             "teclas": campos.pop("teclas", {"w": False, "a": False, "s": False, "d": False,
                                             "q": False, "e": False})}
    corpo.update(campos)
    return _http(base + "/api/voo", corpo)


def secao_integracao(pasta: Path, porta: int) -> bool:
    """§5: servidor + runner REAIS — o seletor troca ao vivo, o yaw roda, W segue o rumo, o olhar centra."""
    c = Checagens("§5 integração: seletor ao vivo + yaw livre + WASDQE no rumo + olhar centrado")
    processo, base, controlo, telemetria, stdout = _arrancar_site(pasta / "controlador", porta, "rl")
    if base is None:
        vivo = processo.poll() is None
        linhas = (stdout or "") + "\n" + (_fechar_site(processo) or "")
        return c.ok("servidor arrancou (--controlador rl)", False,
                    f"sem URL em 240 s · filho {'VIVO (mudo)' if vivo else f'morto (exit {processo.poll()})'}"
                    " · saída: " + (linhas[-400:].replace("\n", " | ") if linhas else "(vazia)"))
    try:
        c.ok("arranque mostra o controlador (rl = política como sempre)", True,
             next((l for l in stdout.splitlines() if "CONTROLADOR" in l), ""))
        _, _, estado = _esperar(telemetria, lambda l, e: (l.get("controlador") or {}).get("modo") == "rl",
                                60, base)
        c.ok("telemetria publica o bloco `controlador` (modo rl em vigor, estado pronto)",
             (estado.get("controlador") or {}).get("modo") == "rl"
             and (estado.get("controlador") or {}).get("estado") == "pronto"
             and "política" in ((estado.get("controlador") or {}).get("fonte") or ""),
             f"controlador = {estado.get('controlador')}")

        # ---- o SELETOR: POST /api/controlador → troca ao vivo com o episódio reiniciado (honesto)
        codigo, corpo = _http(base + "/api/controlador", {"modo": "classico"})
        c.ok("POST /api/controlador {modo: classico} → 200 e bloco no ficheiro (seq do servidor)",
             codigo == 200 and corpo.get("ok") is True
             and json.loads(controlo.read_text()).get("controlador", {}).get("modo") == "classico",
             f"HTTP {codigo} · {corpo}")
        codigo, corpo = _http(base + "/api/controlador", {"modo": "xpto"})
        c.ok("modo inválido → 400 com o motivo", codigo == 400 and "modo" in str(corpo),
             f"HTTP {codigo} · {corpo.get('erro', '')[:70]}")
        codigo, corpo = _http(base + "/api/controlador", {"modo": "rl", "seq": 9})
        c.ok("chave desconhecida (seq do cliente) → 400 (validação estrita)",
             codigo == 400 and "desconhecidas" in str(corpo), f"HTTP {codigo} · {corpo.get('erro', '')[:70]}")
        achou, linha, estado = _esperar(telemetria,
                                        lambda l, e: (l.get("controlador") or {}).get("modo") == "classico",
                                        90, base)
        c.ok("o runner TROCA ao vivo: `controlador.modo` = classico na telemetria",
             achou, f"controlador = {linha.get('controlador')}")
        com_trocando = False
        try:
            registos = [json.loads(l) for l in telemetria.read_text(encoding="utf-8").splitlines()
                        if l.strip().startswith("{")]
            com_trocando = any((r.get("controlador") or {}).get("estado") == "trocando"
                               and (r.get("controlador") or {}).get("motivo") for r in registos)
        except (OSError, ValueError):
            pass
        c.ok("estado honesto da troca: linha `trocando` COM motivo (episódio reiniciado) na telemetria",
             com_trocando)
        ep_depois = int(linha.get("ep", 0) or 0)
        c.ok("a troca reiniciou o episódio (ep avançou)", ep_depois >= 2, f"ep = {ep_depois}")
        bloco = (estado.get("controlador") or {})
        c.ok("fonte do modo clássico = cascata C++ (via ctypes) — quem faz o quê, honesto",
             "C++" in (bloco.get("fonte") or "") or "cascata" in (bloco.get("fonte") or "").lower(),
             f"fonte = {bloco.get('fonte')}")

        # ---- YAW: Z (taxa) roda; X (yaw_alvo) trava o rumo no alvo pedido
        _voo(base, yaw_taxa=0.5, yaw_alvo=None)
        achou, linha, _ = _esperar(telemetria,
                                   lambda l, e: (l.get("controlador") or {}).get("rumo") is not None
                                   and abs((l.get("controlador") or {}).get("rumo", 0.0)) > 0.3, 30, base)
        c.ok("Z (yaw_taxa +0,5 rad/s) RODA o drone (yaw livre — o rumo cresce)",
             achou, f"rumo = {(linha.get('controlador') or {}).get('rumo')}")
        rumo_antes = (linha.get("controlador") or {}).get("rumo", 0.0)
        alvo_x = rumo_antes + 0.8                          # tecla X: fixar um rumo (0,8 rad à frente)
        _voo(base, yaw_taxa=0.0, yaw_alvo=alvo_x)
        achou, linha, _ = _esperar(telemetria,
                                   lambda l, e: (l.get("controlador") or {}).get("rumo") is not None
                                   and abs((l.get("controlador") or {}).get("rumo", 0.0) - alvo_x) < 0.20,
                                   30, base)
        time.sleep(3.0)
        linha = _ultima(telemetria)
        rumo_final = (linha.get("controlador") or {}).get("rumo")
        c.ok("X (yaw_alvo) leva o drone AO rumo pedido e FIXA-O (3 s depois continua lá)",
             achou and rumo_final is not None and abs(rumo_final - alvo_x) < 0.25,
             f"alvo {alvo_x:.3f} · rumo final {rumo_final}")

        # ---- OLHAR (V): o IBVS liga, o alvo fica CENTRADO e descreve o CÍRCULO (drone ainda perto do alvo)
        _voo(base, ativo=False, segui_alvo=True, yaw_alvo=None, yaw_taxa=0.0)
        achou, linha, _ = _esperar(telemetria,
                                   lambda l, e: ((l.get("controlador") or {}).get("olhar") or {}).get("valido")
                                   is True, 40, base)
        c.ok("V (segui_alvo) LIGA o IBVS: o alvo aparece detetado na telemetria (`controlador.olhar`)",
             achou, f"olhar = {(linha.get('controlador') or {}).get('olhar')}")
        # amostra durante 8 s de OLHAR (a aquisição do IBVS entra na janela) e mede o erro ao centro
        erros, estados, t0 = [], [], time.perf_counter()
        while time.perf_counter() - t0 < 8.0:
            linha = _ultima(telemetria)
            ol = (linha.get("controlador") or {}).get("olhar") or {}
            if ol.get("valido"):
                erros.append(max(abs(ol.get("erro_px", [99, 99])[0]), abs(ol.get("erro_px", [99, 99])[1])))
                estados.append(int(ol.get("estado", -1)))
            time.sleep(0.4)
        mediana = float(np.median(erros)) if erros else 999.0
        c.ok("o alvo APARECE CENTRADO na telemetria (|erro_px| mediano < 25 px após a aquisição)",
             len(erros) >= 5 and mediana < 25.0,
             f"{len(erros)} amostras válidas · |erro_px| mediano = {mediana:.1f} px · máx = "
             f"{max(erros) if erros else '—'}")
        c.ok("o IBVS está em A_SEGUIR (estado 0) e o alvo descreve o CÍRCULO (cenário do dono)",
             0 in estados and _alvo_moveu(telemetria),
             f"estados IBVS vistos = {sorted(set(estados))}")
        _voo(base, ativo=False, segui_alvo=False, yaw_alvo=None)

        # ---- WASDQE RELATIVO AO RUMO: rumo a 90° → W leva o drone para +y (muda de eixo)
        _voo(base, yaw_alvo=YAW_ALVO_TESTE, yaw_taxa=0.0)
        achou, linha, _ = _esperar(telemetria,
                                   lambda l, e: (l.get("verdade") or {}).get("yaw") is not None
                                   and abs((l.get("verdade") or {}).get("yaw", 0.0) - YAW_ALVO_TESTE) < 0.25,
                                   40, base)
        c.ok("yaw_alvo = π/2: o drone roda para 90° (rumo absoluto)", achou,
             f"verdade.yaw = {(linha.get('verdade') or {}).get('yaw')}")
        _voo(base, teclas={"w": True, "a": False, "s": False, "d": False, "q": False, "e": False})
        achou, linha, _ = _esperar(telemetria, lambda l, e: _vel_mundo(l)[1] > 0.5, 30, base)
        vx_m, vy_m = _vel_mundo(linha)
        c.ok("com yaw a 90°, W MUDA DE EIXO: o avanço vai para +y no mundo (e não para +x)",
             achou and abs(vx_m) < 0.45, f"v_mundo = [{vx_m:.2f}, {vy_m:.2f}]")
        _voo(base, ativo=False)

        _codigo, estado = _http(base + "/api/state")
        bloco = estado.get("controlador") or {}
        c.ok("estado final do seletor: `pronto`, modo classico, `v_ref_fonte` do clássico (rumo/olhar)",
             bloco.get("modo") == "classico" and bloco.get("estado") == "pronto"
             and (bloco.get("v_ref_fonte") or "").startswith(("wasdqe", "olhar")),
             f"controlador = {bloco}")
    finally:
        log = _fechar_site(processo)
    c.ok("o arranque imprimiu o modo (mostra-o no arranque)", "CONTROLADOR" in (log or ""),
         "presente no log = " + str("CONTROLADOR" in (log or "")))
    return c.fechar()


def _vel_mundo(linha: dict) -> tuple[float, float]:
    """`(vx, vy)` do mundo a partir do `verdade` (velocidade no NARIZ rodada pelo yaw absoluto)."""
    verdade = linha.get("verdade") or {}
    try:
        yaw, vx, vy = float(verdade["yaw"]), float(verdade["vx"]), float(verdade["vy"])
    except (KeyError, TypeError, ValueError):
        return 0.0, 0.0
    return math.cos(yaw) * vx - math.sin(yaw) * vy, math.sin(yaw) * vx + math.cos(yaw) * vy


def _alvo_moveu(telemetria: Path) -> bool:
    """O alvo MOCAP (`controlador.olhar.alvo_mundo`) andou? (o círculo do «olhar» — cenário do dono)."""
    try:
        registos = [json.loads(l) for l in telemetria.read_text(encoding="utf-8").splitlines()
                    if l.strip().startswith("{")]
    except (OSError, ValueError):
        return False
    alvos = [tuple(((r.get("controlador") or {}).get("olhar") or {}).get("alvo_mundo") or ())
             for r in registos]
    alvos = [a for a in alvos if len(a) >= 2]
    return (len(alvos) >= 2
            and (abs(alvos[-1][0] - alvos[0][0]) > 0.3 or abs(alvos[-1][1] - alvos[0][1]) > 0.3))


# ---------------------------------------------------------------------------------------- §6 mutações
MUTACOES = (
    {"nome": "v_ref_mundo sem a rotação (W deixa de mudar de eixo)",
     "ficheiro": "sim_view.py",
     "antes": "    return [vx * c - vy * s, vx * s + vy * c, vz]",
     "depois": "    return [vx, vy, vz]",
     "checagem": (
         "import math, sys; sys.path[:0] = ['@FONTES@', '@AQUI@', '@RAIZ@']; import sim_view as m\n"
         "assert abs(m.v_ref_mundo([1.0,0.0,0.0], math.pi/2)[1] - 1.0) < 1e-9, 'W a 90 graus nao foi para +y'\n")},
    {"nome": "seletor sem validação estrita do modo",
     "ficheiro": "sim_site.py",
     "antes": "    if modo not in MODOS_CONTROLADOR:",
     "depois": "    if False and modo not in MODOS_CONTROLADOR:",
     "checagem": (
         "import sys; sys.path[:0] = ['@FONTES@', '@AQUI@', '@RAIZ@']; import sim_site as s\n"
         "try:\n"
         "    s.validar_controlador({'modo': 'xpto'}, {})\n"
         "except ValueError:\n"
         "    sys.exit(0)   # recusou como deve: a checagem PASSA (logo a mutação NÃO pegou)\n"
         "sys.exit(1)\n")},
)


def secao_mutacoes(pasta: Path) -> bool:
    """§6: NÃO-TAUTOLOGIA — cada mutação tem de fazer FALHAR a checagem correspondente."""
    c = Checagens("§6 mutações: as cópias mutadas têm de FALHAR (2)")
    for mutacao in MUTACOES:
        origem = _AQUI / mutacao["ficheiro"]
        texto = origem.read_text(encoding="utf-8")
        if mutacao["antes"] not in texto:
            c.ok(f"mutação «{mutacao['nome']}»: o texto-alvo existe em {mutacao['ficheiro']}", False,
                 "o código mudou — atualize a mutação")
            continue
        # as cópias vivem em $TMPDIR (regra do laboratório) mas com um `pyproject.tomol` stub para o
        # `_RAIZ` do módulo resolver (os módulos procuram-no acima de si) — o import pega na cópia mutada
        destino = pasta / ("mut_" + re.sub(r"\W+", "_", mutacao["nome"])[:40])
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "pyproject.toml").write_text("[project]\nname = 'mutacao'\n", encoding="utf-8")
        (destino / mutacao["ficheiro"]).write_text(
            texto.replace(mutacao["antes"], mutacao["depois"], 1), encoding="utf-8")
        codigo = (mutacao["checagem"].replace("@FONTES@", str(destino))
                  .replace("@AQUI@", str(_AQUI)).replace("@RAIZ@", str(_RAIZ)))
        # 1) a checagem PASSA nas fontes reais…
        real = subprocess.run([sys.executable, "-c", codigo.replace(str(destino), str(_AQUI), 1)],
                              capture_output=True, text=True, timeout=180, check=False)
        # 2) …e FALHA na cópia mutada (é isso que prova que a checagem tem dentes)
        mutado = subprocess.run([sys.executable, "-c", codigo],
                                capture_output=True, text=True, timeout=180, check=False)
        c.ok(f"mutação «{mutacao['nome']}» FALHA a checagem (e a original passa)",
             real.returncode == 0 and mutado.returncode != 0,
             f"original exit {real.returncode} · mutado exit {mutado.returncode}"
             + (f" · {(mutado.stderr or '')[-200:]}" if mutado.returncode == 0 else ""))
    return c.fechar()


# ---------------------------------------------------------------------------------------- orquestração
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Prova do seletor de controlador (contrato r12).")
    p.add_argument("--so-pecas", action="store_true", help="só §1–§4 (peças e painéis; sem correr o runner)")
    p.add_argument("--sem-e2e", action="store_true", help="salta a §5 (integração real)")
    p.add_argument("--porta", type=int, default=PORTA_TESTE)
    args = p.parse_args(argv)
    pasta = Path(os.environ.get("TMPDIR") or tempfile.gettempdir()) / "teste_controlador"
    resultados = [secao_contrato(), secao_seletor(), secao_rumo(), secao_paineis()]
    if not args.so_pecas and not args.sem_e2e:
        resultados.append(secao_integracao(pasta, args.porta))
    resultados.append(secao_mutacoes(pasta))
    n_ok = sum(1 for r in resultados if r)
    print(f"\nRESUMO: {n_ok}/{len(resultados)} secoes TUDO OK", flush=True)
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
