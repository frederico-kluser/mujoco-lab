#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_cockpit.py — PROVA do COCKPIT (contrato r13, 2026-10-12).

O pedido do dono: «não quero opções, quero o melhor», «o modo de controlar já vem ativado», o vento com
três botões («ligar, definir a intensidade e a aleatoriedade ativar ou não»), um modo em que «a bola se
movimenta aleatoriamente» e o drone a mantém centrada na câmara FPV, e uma interface «muito intuitiva e
performativa». Este script prova o lado do BACKEND desse contrato (o site tem os testes dele em
`site/testes/`):

  §1 GERADOR DO VENTO (`vento_natural.py`): com a aleatoriedade desligada o vento é EXATAMENTE a média
     pedida (e não consome o gerador de números); com ela ligada a média vetorial continua a ser W, a
     dispersão é a declarada (σ ≈ 0,25·W), o teto 2,5·W nunca é passado, há rajadas, a direção deambula;
     ligar/desligar entra em rampa (sem degraus) e desligado é zero EXATO; determinístico pela semente;
     validação estrita dos quatro campos.
  §2 SERVIDOR (`sim_site.py`): `POST /api/vento-simples` e `POST /api/bola` (subconjuntos, faixas, chaves
     desconhecidas → `ValueError` = 400), o `seq` do servidor, o ARRANQUE LIMPO (`controlo_de_arranque`:
     vento desligado mantendo as preferências, voo ATIVO com as teclas soltas, sem «seguir»), o
     `--controlador auto` (`resolver_controlador`: clássico na planta real em CTBR, RL no cf2), a
     convivência com o contrato antigo (um POST antigo devolve-lhe a autoridade; o PARAR desliga os dois) e
     o eco honesto (com os 3 botões no ficheiro, o `dinamico` velho não aparece como ativo).
  §3 RUNNER (`sim_view.py`): os blocos `vento_simples`/`bola` do ficheiro de controlo (`ler_registo`), a
     neutralização do vento antigo quando mandam os 3 botões, o vento do gerador a chegar ao env pela
     porta de sempre (`definir_vento`), a velocidade da bola e o canal do HUD (datagrama UDP do
     `EmissorHud` → `CanalHud` do servidor, ida e volta em menos de 1 s).
  §4 INTEGRAÇÃO REAL (um `sim_site.py` verdadeiro, ficheiros de controlo e bateria em $TMPDIR): arranca
     SEM flags e voa a cascata clássica com o voo ativo e o vento desligado; o HUD chega por Server-Sent
     Events a ≥ 30 Hz; W move o drone para a frente do NARIZ; ligar o vento põe na física a intensidade
     pedida (em rampa) e desligá-lo devolve o ar parado; «seguir a bola» põe a bola a andar e o detetor de
     bordo a vê-la com o erro de centragem limitado; o drone não cai em nenhum passo.
  §5 MUTAÇÕES (não-tautologia): cópias mutadas das fontes têm de FALHAR as checagens correspondentes.

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_cockpit.py            # tudo
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_cockpit.py --sem-e2e  # sem a §4

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
import threading
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

PORTA_TESTE = 8797
ESPERA_ARRANQUE_S = 150.0        # o runner importa torch/SB3 e compila a .so do núcleo na 1.ª vez
DT = 0.02                        # s — o passo de decisão (50 Hz)


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

    def recusa(self, nome: str, funcao, *args) -> bool:
        """`funcao(*args)` tem de levantar `ValueError` (é o que o servidor traduz num 400)."""
        try:
            funcao(*args)
        except ValueError as erro:
            return self.ok(nome, True, str(erro)[:90])
        return self.ok(nome, False, "não recusou")

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


# ---------------------------------------------------------------------------------------- §1 gerador do vento
def _serie(gerador, n: int) -> np.ndarray:
    return np.array([gerador.passo(DT) for _ in range(n)])


def secao_gerador() -> bool:
    import vento_natural as vn
    c = Checagens("§1 gerador do vento dos 3 botões (vento_natural.py)")

    # --- constante: exatamente a média pedida, sem consumir o gerador de números
    g = vn.VentoNatural(semente=3)
    estado_rng = g._rng.bit_generator.state["state"]["state"]
    g.definir(True, 3.0, False, 45.0)
    v = _serie(g, 600)
    alvo = 3.0 * np.array([math.cos(math.radians(45)), math.sin(math.radians(45)), 0.0])
    c.ok("constante: depois da rampa o vento é EXATAMENTE W na direção pedida",
         float(np.max(np.abs(v[-1] - alvo))) < 1e-6, f"|Δ| máx {np.max(np.abs(v[-1] - alvo)):.2e} m/s")
    c.ok("constante: não consome o gerador de números (zero aleatoriedade)",
         g._rng.bit_generator.state["state"]["state"] == estado_rng and g.n_rajadas == 0)
    normas = np.linalg.norm(v, axis=1)
    c.ok("ligar entra em RAMPA (monótona, sem degrau): 63 % ao fim de ~0,6 s",
         bool(np.all(np.diff(normas) >= -1e-12)) and 0.55 < normas[29] / 3.0 < 0.70
         and float(np.max(np.diff(normas))) < 0.12,
         f"|v|(0,6 s) = {normas[29]:.2f} m/s · maior salto {np.max(np.diff(normas)):.3f} m/s por passo")

    # --- desligar: rampa a descer e zero EXATO
    g.definir(False, 3.0, False, 45.0)
    v = _serie(g, 600)
    normas = np.linalg.norm(v, axis=1)
    primeiro_zero = int(np.argmax(normas == 0.0))
    c.ok("desligar desce em rampa e chega a zero EXATO (fica em zero)",
         bool(np.all(np.diff(normas) <= 1e-12)) and normas[-1] == 0.0 and 100 < primeiro_zero < 400
         and bool(np.all(normas[primeiro_zero:] == 0.0)),
         f"zero exato a partir de {primeiro_zero * DT:.1f} s")

    # --- aleatório: a média mantém-se, a dispersão é a declarada, o teto nunca é passado
    for w in (1.0, 3.0, 5.0):
        g = vn.VentoNatural(semente=11)
        g.definir(True, w, True, 90.0)
        v = _serie(g, int(900 / DT))[200:]
        normas = np.linalg.norm(v, axis=1)
        media_vec = float(np.linalg.norm(v.mean(axis=0)))
        azimute = math.degrees(math.atan2(v[:, 1].mean(), v[:, 0].mean()))
        c.ok(f"aleatório W={w:g}: a média VETORIAL continua a ser W (±6 %) na direção pedida (±5°)",
             abs(media_vec / w - 1.0) < 0.06 and abs(azimute - 90.0) < 5.0,
             f"média {media_vec:.2f} m/s @ {azimute:.1f}°")
        c.ok(f"aleatório W={w:g}: dispersão declarada (σ|v| ∈ [0,18; 0,32]·W) e p95 ≥ 1,3·W",
             0.18 < normas.std() / w < 0.32 and np.percentile(normas, 95) / w > 1.3,
             f"σ {normas.std() / w:.2f}·W · p95 {np.percentile(normas, 95) / w:.2f}·W")
        c.ok(f"aleatório W={w:g}: o teto {vn.TETO_FATOR:g}·W nunca é passado",
             float(normas.max()) <= vn.TETO_FATOR * w + 1e-9, f"máx {normas.max() / w:.2f}·W")
        if w == 3.0:
            c.ok("aleatório: há rajadas (1 a cada 4–14 s) e componente vertical (σ_z ≈ 0,1·W)",
                 4.0 < 900.0 / max(g.n_rajadas, 1) < 14.0 and 0.05 < v[:, 2].std() / w < 0.18,
                 f"{g.n_rajadas} rajadas em 900 s · σ_z {v[:, 2].std() / w:.2f}·W")
            az = np.degrees(np.unwrap(np.arctan2(v[:, 1], v[:, 0])))
            c.ok("aleatório: a direção deambula (σ do azimute entre 8° e 30°)", 8.0 < az.std() < 30.0,
                 f"σ azimute {az.std():.1f}°")

    # --- desligar a aleatoriedade esquece tudo: volta à média constante, sem nada pendente
    g = vn.VentoNatural(semente=5)
    g.definir(True, 4.0, True, 0.0)
    _serie(g, 2000)
    g.definir(True, 4.0, False, 0.0)
    v = _serie(g, 50)
    c.ok("desligar a aleatoriedade: o vento volta JÁ a ser a média constante (nada pendente)",
         float(np.max(np.abs(v - np.array([4.0, 0.0, 0.0])))) < 1e-6 and not g.em_rajada)

    # --- determinismo e validação
    a, b = vn.VentoNatural(semente=7), vn.VentoNatural(semente=7)
    outro = vn.VentoNatural(semente=8)
    for x in (a, b, outro):
        x.definir(True, 4.0, True, 10.0)
    sa, sb, so = _serie(a, 1500), _serie(b, 1500), _serie(outro, 1500)
    c.ok("determinístico pela semente (mesma semente = mesmo vento, bit a bit; outra semente = outro vento)",
         bool(np.array_equal(sa, sb)) and not np.array_equal(sa, so))
    nulo = vn.VentoNatural(semente=1)
    nulo.definir(True, 0.0, True, 0.0)
    c.ok("W = 0 com tudo ligado: zero EXATO (nada é proporcional a nada)",
         float(np.max(np.abs(_serie(nulo, 200)))) == 0.0)
    for nome, args in (("intensidade acima do teto", (True, vn.INTENSIDADE_MAX + 0.01, False, 0.0)),
                       ("intensidade negativa", (True, -0.1, False, 0.0)),
                       ("intensidade NaN", (True, float("nan"), False, 0.0)),
                       ("`ligado` que não é booleano", (1, 2.0, False, 0.0)),
                       ("`aleatorio` que não é booleano", (True, 2.0, "sim", 0.0)),
                       ("direção infinita", (True, 2.0, False, float("inf")))):
        c.recusa(f"validação: {nome} é recusada", vn.validar, *args)
    c.ok("validação: a direção é reduzida a [0, 360)°", vn.validar(True, 1.0, False, -90.0)["direcao"] == 270.0)
    vel, az, el = vn.polar_do_vetor([0.0, 2.0, 2.0])
    c.ok("polar_do_vetor: [0, 2, 2] → 2,83 m/s @ 90° de azimute e 45° de elevação",
         abs(vel - math.sqrt(8)) < 1e-9 and abs(az - 90.0) < 1e-9 and abs(el - 45.0) < 1e-9)
    return c.fechar()


# ---------------------------------------------------------------------------------------- §2 servidor
def secao_servidor() -> bool:
    import sim_site as s
    c = Checagens("§2 servidor: vento dos 3 botões, bola, arranque limpo, `auto` (sim_site.py)")

    novo = s.validar_vento_simples({"ligado": True, "intensidade": 3.5, "aleatorio": True, "direcao": 370.0}, {})
    bloco = novo["vento_simples"]
    c.ok("vento-simples: bloco COMPLETO com o `seq` do servidor",
         bloco == {"ligado": True, "intensidade": 3.5, "aleatorio": True, "direcao": 10.0, "seq": 1}, str(bloco))
    seguinte = s.validar_vento_simples({"intensidade": 1.0}, novo)["vento_simples"]
    c.ok("vento-simples: um SUBCONJUNTO mantém o resto (só a intensidade mudou; seq +1)",
         seguinte == {"ligado": True, "intensidade": 1.0, "aleatorio": True, "direcao": 10.0, "seq": 2},
         str(seguinte))
    primeiro = s.validar_vento_simples({"ligado": True}, {})["vento_simples"]
    c.ok("vento-simples: sem estado anterior, LIGAR usa o padrão (2 m/s, constante)",
         primeiro["intensidade"] == s.VENTO_SIMPLES_PADRAO["intensidade"] and primeiro["aleatorio"] is False)
    for nome, corpo in (("corpo vazio", {}), ("chave desconhecida (gralha)", {"intencidade": 3}),
                        ("intensidade fora da faixa", {"intensidade": 9}),
                        ("`ligado` como número", {"ligado": 1}), ("corpo que não é objeto", [1, 2])):
        c.recusa(f"vento-simples: {nome} → 400", s.validar_vento_simples, corpo, {})

    b = s.validar_bola({"velocidade": 0.6}, {})["bola"]
    c.ok("bola: velocidade aceite com `seq` do servidor", b == {"velocidade": 0.6, "seq": 1}, str(b))
    b_zero = s.validar_bola({"velocidade": 0.0, "auto_atirar": True}, {})["bola"]
    c.ok("bola: velocidade 0,0 m/s (parada) e `auto_atirar: true` aceites",
         b_zero == {"velocidade": 0.0, "auto_atirar": True, "seq": 1}, str(b_zero))
    for nome, corpo in (("acima do máximo", {"velocidade": s.BOLA_VEL_MAX + 0.01}),
                        ("abaixo do mínimo", {"velocidade": -0.01}), ("sem velocidade", {}),
                        ("chave desconhecida", {"velocidade": 0.5, "modo": "x"})):
        c.recusa(f"bola: {nome} → 400", s.validar_bola, corpo, {})
    c.ok("bola: sem bloco (ou com lixo) o eco é o padrão, com a faixa para o slider",
         s.bola_do_controlo({}) == {"velocidade": s.BOLA_VEL_PADRAO, "min": s.BOLA_VEL_MIN,
                                   "max": s.BOLA_VEL_MAX}
         and s.bola_do_controlo({"bola": {"velocidade": "depressa"}})["velocidade"] == s.BOLA_VEL_PADRAO)

    # --- tiro (SPACE, Glock 25 no topo do drone)
    t1 = s.validar_tiro({"gatilho": True}, {})
    c.ok("tiro: premir SPACE (`gatilho: true`) incrementa `disparos` (+1) e `seq` (+1)",
         t1["tiro"] == {"gatilho": True, "disparos": 1, "seq": 1}, str(t1["tiro"]))
    t2 = s.validar_tiro({"gatilho": False}, t1)
    c.ok("tiro: largar SPACE (`gatilho: false`) solta o gatilho sem disparar outro tiro (`seq` +1)",
         t2["tiro"] == {"gatilho": False, "disparos": 1, "seq": 2}, str(t2["tiro"]))
    t3 = s.validar_tiro({}, t2)
    c.ok("tiro: corpo vazio `{}` equivale a um disparo (`gatilho: true`, `disparos` +1)",
         t3["tiro"] == {"gatilho": True, "disparos": 2, "seq": 3}, str(t3["tiro"]))
    for nome, corpo in (("chave desconhecida", {"gatilho": True, "arma": "x"}),
                        ("`gatilho` que não é booleano", {"gatilho": 1}),
                        ("corpo que não é objeto", [1])):
        c.recusa(f"tiro: {nome} → 400", s.validar_tiro, corpo, {})

    # --- carga útil extra (POST /api/carga)
    cg1 = s.validar_carga({"carga_extra_g": 1200.0}, {})
    c.ok("carga: `carga_extra_g` aceite com `seq` do servidor (+1)",
         cg1["carga"] == {"carga_extra_g": 1200.0, "seq": 1}, str(cg1["carga"]))
    for nome, corpo in (("negativa", {"carga_extra_g": -10}),
                        ("acima de 5000 g", {"carga_extra_g": 5001}),
                        ("sem campo", {}),
                        ("chave desconhecida", {"carga_extra_g": 100, "extra": 1})):
        c.recusa(f"carga: {nome} → 400", s.validar_carga, corpo, {})

    # --- otimização gráfica do MuJoCo (POST /api/graficos)
    gr1 = s.validar_graficos({"sombras": False, "reflexos": False, "escala_resolucao": 0.5, "qualidade_jpeg": 65}, {})
    c.ok("graficos: opções de otimização MuJoCo aceites com `seq` (+1)",
         gr1["graficos"]["sombras"] is False and gr1["graficos"]["reflexos"] is False
         and gr1["graficos"]["escala_resolucao"] == 0.5 and gr1["graficos"]["qualidade_jpeg"] == 65
         and gr1["graficos"]["seq"] == 1, str(gr1["graficos"]))
    for nome, corpo in (("vazio", {}),
                        ("chave desconhecida", {"sombras": False, "aa": 4}),
                        ("sombras não booleano", {"sombras": 1}),
                        ("escala fora de [0.25, 1.0]", {"escala_resolucao": 1.5}),
                        ("jpeg fora de [30, 95]", {"qualidade_jpeg": 10})):
        c.recusa(f"graficos: {nome} → 400", s.validar_graficos, corpo, {})

    # --- troca de preset calibrado de motores e bateria (POST /api/pecas)
    pc1 = s.validar_pecas({"preset_id": "interceptor_lipo"}, {})
    c.ok("pecas: `preset_id` calibrado aceite com `motor_id`, `bateria_id` e `seq` (+1)",
         pc1["pecas"] == {"preset_id": "interceptor_lipo", "motor_id": "tmotor_mn4006_kv380",
                          "bateria_id": "lipo_6s1p_4500_alta_vazao", "seq": 1},
         str(pc1["pecas"]))
    for nome, corpo in (("vazio", {}),
                        ("preset desconhecido", {"preset_id": "preset_falso"}),
                        ("combinação livre não calibrada", {"motor_id": "tmotor_mn5006_kv450", "bateria_id": "molicel_p45b_6s1p"}),
                        ("motor desconhecido", {"motor_id": "motor_falso"}),
                        ("bateria desconhecida", {"bateria_id": "pilha_aa"}),
                        ("chave desconhecida", {"preset_id": "endurance_p50b", "helice_id": "x"})):
        c.recusa(f"pecas: {nome} → 400", s.validar_pecas, corpo, {})

    # --- arranque limpo: estado fixo, preferências preservadas
    velho = {"vento_simples": {"ligado": True, "intensidade": 4.0, "aleatorio": True, "direcao": 120.0, "seq": 7},
             "voo": {"ativo": False, "teclas": {"w": True}, "segui_alvo": True, "yaw_taxa": 0.5, "seq": 3},
             "bola": {"velocidade": 0.7, "seq": 2}, "loop": True, "reiniciar": 5}
    arr = s.controlo_de_arranque(velho)
    c.ok("arranque: o vento nasce DESLIGADO mas as preferências ficam (4 m/s, aleatório, 120°)",
         arr["vento_simples"] == {"ligado": False, "intensidade": 4.0, "aleatorio": True, "direcao": 120.0,
                                  "seq": 8}, str(arr["vento_simples"]))
    c.ok("arranque: o voo nasce ATIVO, com as 6 teclas soltas, sem yaw e sem «seguir a bola»",
         arr["voo"]["ativo"] is True and not any(arr["voo"]["teclas"].values())
         and set(arr["voo"]["teclas"]) == set("wasdqe") and arr["voo"]["segui_alvo"] is False
         and arr["voo"]["yaw_taxa"] == 0.0 and arr["voo"]["yaw_alvo"] is None and arr["voo"]["seq"] == 4)
    c.ok("arranque: a velocidade da bola guardada fica; `loop`/`reiniciar` não são tocados",
         arr["bola"] == {"velocidade": 0.7, "seq": 3} and "loop" not in arr and "reiniciar" not in arr)
    lixo = s.controlo_de_arranque({"vento_simples": {"intensidade": "forte"}, "bola": 3})
    c.ok("arranque: preferências inválidas (ficheiro escrito à mão) voltam ao padrão em vez de impedir",
         lixo["vento_simples"]["intensidade"] == s.VENTO_SIMPLES_PADRAO["intensidade"]
         and lixo["bola"]["velocidade"] == s.BOLA_VEL_PADRAO)

    # --- `auto`: o que ganhou na medição para a planta que vai voar
    c.ok("`auto` → clássico na planta REAL em CTBR", s.resolver_controlador("auto", {"modo_acao": "ctbr"}) == "classico")
    c.ok("`auto` → RL no cf2 (sem hardware.json) e na planta real em modo `motores`",
         s.resolver_controlador("auto", None) == "rl"
         and s.resolver_controlador("auto", {"modo_acao": "motores"}) == "rl")
    c.ok("`rl`/`classico` explícitos passam tal e qual",
         s.resolver_controlador("rl", {"modo_acao": "ctbr"}) == "rl"
         and s.resolver_controlador("classico", None) == "classico")
    padrao = s.analisar_argumentos([])
    c.ok("o PADRÃO do site é `auto`, sem janela nativa (o cockpit é o site) e com o stream em memória",
         padrao.controlador == "auto" and padrao.com_janela is False and padrao.fpv is None
         and s.pasta_fpv_omissao(8080, {"XDG_RUNTIME_DIR": str(_AQUI)}).parts[-2:]
         == ("mujoco-lab-drone", "fpv-8080")
         and s.pasta_fpv_omissao(8080, {}) == s.FPV_OMISSAO)

    # --- convivência com o contrato antigo
    com_simples = {"vel": 3.0, "ativo": True, "azimute": 10.0, "elevacao": 0.0,
                   "dinamico": {"modo": "aleatoria", "params": {}, "ativo": True, "seq": 4},
                   "vento_simples": {"ligado": True, "intensidade": 2.0, "aleatorio": False, "direcao": 0.0,
                                     "seq": 1}}
    c.ok("eco honesto: com os 3 botões no ficheiro, o `dinamico` velho NÃO aparece como ativo",
         s.vento_do_controlo(com_simples) == {"modo": "nenhum", "params": {}, "ativo": False}
         and s.vento_base_do_controlo(com_simples)["vel"] == 0.0)
    sem = {k: v for k, v in com_simples.items() if k != "vento_simples"}
    c.ok("eco: sem o bloco dos 3 botões o contrato antigo aparece como sempre",
         s.vento_do_controlo(sem)["ativo"] is True and s.vento_base_do_controlo(sem)["vel"] == 3.0)
    c.ok("um POST do contrato antigo (`/api/vento`) devolve-lhe a autoridade (o bloco sai)",
         s.validar_vento({"vel": 1.0}, com_simples)["vento_simples"] is None)
    c.ok("um POST `/api/vento-dinamico` também (o bloco sai)",
         s.validar_vento_dinamico({"modo": "nenhum"}, com_simples)["vento_simples"] is None)
    parado = s.validar_parar(com_simples)
    c.ok("PARAR desliga os DOIS: vento antigo a 0 + dinâmica `nenhum` + 3 botões desligados (preferências ficam)",
         parado["vel"] == 0.0 and parado["dinamico"]["modo"] == "nenhum"
         and parado["vento_simples"]["ligado"] is False and parado["vento_simples"]["intensidade"] == 2.0
         and parado["vento_simples"]["seq"] == 2)
    return c.fechar()


# ---------------------------------------------------------------------------------------- §3 runner
class _EnvFalso:
    """O mínimo que o `Controlo` usa do env para o VENTO (regista o que lhe chega)."""

    dt_decisao = DT
    comando = False

    def __init__(self) -> None:
        self.ventos: list[tuple[float, float, float]] = []
        self.dinamicos: list = []

    def definir_vento(self, vel, azimute, elevacao=0.0):
        self.ventos.append((float(vel), float(azimute), float(elevacao)))

    def definir_vento_dinamico(self, config):
        self.dinamicos.append(config)

    def definir_gatilho_tiro(self, gatilho: bool):
        self.gatilho = bool(gatilho)

    def disparar(self, n: int = 1):
        self.disparos = getattr(self, "disparos", 0) + int(n)
        return {"tiros_acumulados": self.disparos, "impulso_ns": 1.9162 * n, "forca_n": 95.81 * n,
                "duracao_s": 0.02, "direcao_soco": [-1.0, 0.0, 0.0], "azimute_soco_graus": 180.0,
                "delta_v_m_s": 0.6457 * n, "delta_omega_pitch_rad_s": -1.025 * n}


def secao_runner(pasta: Path) -> bool:
    import sim_site
    import sim_view as m
    c = Checagens("§3 runner: blocos do controlo, vento a chegar ao env, HUD por UDP (sim_view.py)")

    r = m.ler_registo({"vel": 3.0, "azimute": 0.0, "ativo": True,
                       "vento_simples": {"ligado": True, "intensidade": 2.5, "aleatorio": True, "direcao": 30.0,
                                         "seq": 4},
                       "bola": {"velocidade": 0.3, "seq": 1}})
    c.ok("ler_registo: bloco `vento_simples` validado",
         r.vento_simples is not None and r.vento_simples.ligado and r.vento_simples.intensidade == 2.5
         and r.vento_simples.aleatorio and r.vento_simples.direcao == 30.0 and r.vento_simples.seq == 4)
    c.ok("ler_registo: bloco `bola` validado", r.bola is not None and r.bola.velocidade == 0.3)
    antigo = m.ler_registo({"vel": 1.0})
    c.ok("ler_registo: sem os blocos novos fica `None` (um ficheiro r12 continua válido)",
         antigo.vento_simples is None and antigo.bola is None)
    c.recusa("ler_registo: intensidade fora da faixa é recusada (o registo é ignorado com aviso)",
             m.ler_registo, {"vento_simples": {"ligado": True, "intensidade": 99}})
    c.recusa("ler_registo: velocidade da bola fora da faixa é recusada",
             m.ler_registo, {"bola": {"velocidade": 5.0}})
    rt = m.ler_registo({"tiro": {"gatilho": True, "disparos": 3, "seq": 5}})
    c.ok("ler_registo: bloco `tiro` validado",
         rt.tiro is not None and rt.tiro.gatilho is True and rt.tiro.disparos == 3 and rt.tiro.seq == 5)
    c.recusa("ler_registo: `tiro.disparos` negativo é recusado",
             m.ler_registo, {"tiro": {"gatilho": True, "disparos": -1}})
    rcg = m.ler_registo({"carga": {"carga_extra_g": 850.0, "seq": 2}})
    c.ok("ler_registo: bloco `carga` validado",
         rcg.carga is not None and rcg.carga.carga_extra_g == 850.0 and rcg.carga.seq == 2)
    c.recusa("ler_registo: `carga.carga_extra_g` fora da faixa é recusada",
             m.ler_registo, {"carga": {"carga_extra_g": -5.0}})
    rgr = m.ler_registo({"graficos": {"sombras": False, "mostrar_fios_detalhes": False, "escala_resolucao": 0.5, "seq": 3}})
    c.ok("ler_registo: bloco `graficos` validado",
         rgr.graficos is not None and rgr.graficos.sombras is False
         and rgr.graficos.mostrar_fios_detalhes is False and rgr.graficos.escala_resolucao == 0.5)
    c.recusa("ler_registo: `graficos.escala_resolucao` fora da faixa é recusada",
             m.ler_registo, {"graficos": {"escala_resolucao": 0.1}})

    # --- o Controlo aplica o registo: o vento antigo é neutralizado e o do gerador chega ao env
    pasta.mkdir(parents=True, exist_ok=True)
    ficheiro = pasta / "controlo_pecas.json"
    ficheiro.write_text(json.dumps({
        "vel": 3.0, "azimute": 200.0, "elevacao": 0.0, "ativo": True,
        "dinamico": {"modo": "dryden", "params": {"sigma": 0.5, "L": 10.0, "u_max": 3.0}, "ativo": True, "seq": 9},
        "vento_simples": {"ligado": True, "intensidade": 2.0, "aleatorio": False, "direcao": 90.0, "seq": 1},
        "bola": {"velocidade": 0.7, "seq": 1}}), encoding="utf-8")
    controlo, env = m.Controlo(ficheiro), _EnvFalso()
    aplicado = controlo.verifica(env)
    c.ok("3 botões no ficheiro: o vento ANTIGO fica neutro (base 0 e nenhum modo dinâmico do env ligado)",
         aplicado is not None and env.ventos and env.ventos[-1][0] == 0.0
         and all(cfg is None for cfg in env.dinamicos) and controlo.ultimo.vel == 0.0
         and controlo.ultimo.dinamico is None,
         f"definir_vento → {env.ventos[-1] if env.ventos else None} · dinâmicos {env.dinamicos}")
    c.ok("a velocidade da bola do ficheiro chega ao runner", controlo.bola_vel == 0.7)
    for _ in range(400):
        mandou = controlo.passo_vento_simples(env)
    vel, az, el = env.ventos[-1]
    c.ok("o vento dos 3 botões chega ao env pela porta de sempre (`definir_vento`): 2 m/s @ 90°",
         mandou and abs(vel - 2.0) < 1e-3 and abs(az - 90.0) < 1e-6 and abs(el) < 1e-9,
         f"{vel:.3f} m/s @ {az:.1f}° (elev {el:+.1f})")
    modo_constante = controlo.modo_efetivo()
    controlo._aplica_vento_simples(m.VentoSimples(True, 2.0, True, 90.0, 2))
    c.ok("o modo publicado na telemetria é `nenhum` (vento constante) e `natural` com a aleatoriedade",
         modo_constante == "nenhum" and controlo.modo_efetivo() == "natural")
    ficheiro.write_text(json.dumps({"vel": 1.5, "azimute": 0.0, "ativo": True, "vento_simples": None}),
                        encoding="utf-8")
    os.utime(ficheiro, ns=(time.time_ns(), time.time_ns() + 5_000_000))     # assinatura nova garantida
    env.ventos.clear()
    controlo.verifica(env)
    c.ok("sem o bloco (POST do contrato antigo): volta a mandar o vento antigo e o gerador cala-se",
         env.ventos and env.ventos[-1][0] == 1.5 and controlo.passo_vento_simples(env) is False
         and controlo.modo_efetivo() == "nenhum", f"definir_vento → {env.ventos[-1] if env.ventos else None}")
    # o bloco volta DEPOIS de ter saído com o vento a soprar: a rampa não pode recomeçar do nível velho
    # («vento fantasma» de 2 m/s a aparecer do nada — achado da revisão das suítes antigas, 2026-10-12)
    ficheiro.write_text(json.dumps({"vel": 0.0, "azimute": 0.0, "ativo": False, "vento_simples": {
        "ligado": False, "intensidade": 2.0, "aleatorio": False, "direcao": 90.0, "seq": 3}}), encoding="utf-8")
    os.utime(ficheiro, ns=(time.time_ns(), time.time_ns() + 9_000_000))
    env.ventos.clear()
    controlo.verifica(env)
    controlo.passo_vento_simples(env)
    c.ok("o bloco volta DESLIGADO depois de ter saído a soprar: vento 0 no 1.º passo (sem rampa fantasma)",
         env.ventos and env.ventos[-1][0] == 0.0, f"definir_vento → {env.ventos[-1] if env.ventos else None}")
    controlo._aplica_vento_simples(m.VentoSimples(True, 1.0, False, 0.0, 4))
    controlo.passo_vento_simples(env)
    c.ok("e ligado a 1 m/s parte de ZERO em rampa (1.º passo muito abaixo de 1 m/s, nunca acima)",
         0.0 < env.ventos[-1][0] < 0.2, f"1.º passo {env.ventos[-1][0]:.3f} m/s")

    # --- HUD: datagrama UDP do runner → canal do servidor
    canal = sim_site.CanalHud()
    emissor = m.EmissorHud(canal.porta)
    try:
        visto, _ = canal.esperar(0, 0.05)
        emissor.enviar({"t": 1.5, "fase": "a_voar", "vento": [1.0, 0.0, 0.0]})
        seq, dados = canal.esperar(visto, 1.0)
        c.ok("HUD: um datagrama do `EmissorHud` chega ao `CanalHud` em < 1 s (JSON intacto)",
             seq == visto + 1 and dados is not None
             and json.loads(dados.decode()) == {"t": 1.5, "fase": "a_voar", "vento": [1.0, 0.0, 0.0]})
        for k in range(20):
            emissor.enviar({"k": k})
        time.sleep(0.2)
        ultimo, idade = canal.ultimo()
        c.ok("HUD: só o ÚLTIMO conta (cliente lento perde amostras em vez de acumular atraso)",
             ultimo is not None and json.loads(ultimo.decode()) == {"k": 19} and idade is not None and idade < 1.0)
        sem_porta = m.EmissorHud(0)
        sem_porta.enviar({"x": 1})
        c.ok("HUD: sem porta (runner lançado à mão) não se envia nada e nada rebenta", sem_porta.n == 0)
    finally:
        emissor.fechar()
        canal.fechar()
    c.ok("as constantes do handshake são as MESMAS nos dois lados (porta do HUD e faixa da bola)",
         m.ENV_HUD_PORTA == sim_site.ENV_HUD_PORTA
         and (m.BOLA_VEL_MIN, m.BOLA_VEL_MAX, m.BOLA_VEL_PADRAO)
         == (sim_site.BOLA_VEL_MIN, sim_site.BOLA_VEL_MAX, sim_site.BOLA_VEL_PADRAO))
    return c.fechar()


# ---------------------------------------------------------------------------------------- §4 integração real
class _Sse(threading.Thread):
    """Lê `GET /api/hud` (Server-Sent Events) numa thread e guarda as amostras com o instante de chegada."""

    def __init__(self, url: str) -> None:
        super().__init__(daemon=True)
        self.url = url
        self.amostras: list[tuple[float, dict]] = []
        self.parar = threading.Event()
        self.erro: str | None = None

    def run(self) -> None:
        try:
            with urllib.request.urlopen(self.url, timeout=10) as resposta:
                for bruto in resposta:
                    if self.parar.is_set():
                        return
                    linha = bruto.decode("utf-8").strip()
                    if linha.startswith("data: "):
                        self.amostras.append((time.perf_counter(), json.loads(linha[6:])))
        except Exception as erro:  # noqa: BLE001  (a thread só regista; quem avalia é a checagem)
            self.erro = f"{type(erro).__name__}: {erro}"

    def ultima(self) -> dict:
        return self.amostras[-1][1] if self.amostras else {}

    def desde(self, t0: float) -> list[dict]:
        return [amostra for t, amostra in self.amostras if t >= t0]


def _esperar(condicao, limite: float, passo: float = 0.1) -> bool:
    fim = time.perf_counter() + limite
    while time.perf_counter() < fim:
        if condicao():
            return True
        time.sleep(passo)
    return bool(condicao())


def secao_integracao(pasta: Path, porta: int) -> bool:
    c = Checagens("§4 integração real: `sim_site.py` sem flags → cockpit a voar (planta real)")
    pasta.mkdir(parents=True, exist_ok=True)
    controlo, telemetria = pasta / "controlo.json", pasta / "telemetria.jsonl"
    for caminho in (controlo, telemetria):
        caminho.unlink(missing_ok=True)
    # estado VELHO de propósito: o arranque tem de o limpar (vento ligado + voo em espera + a seguir)
    controlo.write_text(json.dumps({
        "vel": 0.0, "azimute": 0.0, "elevacao": 0.0, "ativo": False, "reiniciar": 0, "loop": False,
        "vento_simples": {"ligado": True, "intensidade": 3.0, "aleatorio": True, "direcao": 0.0, "seq": 5},
        "voo": {"ativo": False, "teclas": {}, "segui_alvo": True, "seq": 2}}), encoding="utf-8")
    ambiente = {**os.environ, "DRONE_PASTA_BATERIA": str(pasta / "bateria"), "MUJOCO_GL": "egl"}
    comando = [sys.executable, str(_AQUI / "sim_site.py"), "--sem-browser", "--port", str(porta),
               "--controlo", str(controlo), "--telemetria", str(telemetria), "--fpv", str(pasta / "fpv")]
    registo = (pasta / "site.log").open("w", encoding="utf-8")
    processo = subprocess.Popen(comando, cwd=str(_AQUI), stdout=registo, stderr=subprocess.STDOUT,
                                start_new_session=True, env=ambiente)
    url = f"http://127.0.0.1:{porta}"
    sse = None
    try:
        def tem_hud() -> bool:
            try:
                return _http(f"{url}/api/hud.json", timeout=2.0)[1].get("hud") is not None
            except (OSError, ValueError):
                return False
        if not c.ok("o site arranca e o runner começa a mandar HUD", _esperar(tem_hud, ESPERA_ARRANQUE_S, 0.5),
                    f"ver {pasta / 'site.log'}"):
            return c.fechar()
        _, estado = _http(f"{url}/api/state")
        c.ok("arranque SEM flags: quem voa é a cascata clássica (`auto` → o que ganhou na medição)",
             (estado.get("controlador") or {}).get("pedido") == "classico", str(estado.get("controlador"))[:120])
        c.ok("arranque limpo: o vento nasce DESLIGADO (a preferência 3 m/s aleatório ficou guardada)",
             estado.get("vento_simples") == {"ligado": False, "intensidade": 3.0, "aleatorio": True,
                                             "direcao": 0.0}, str(estado.get("vento_simples")))
        pedido = (estado.get("voo") or {}).get("pedido") or {}
        c.ok("arranque limpo: voo ATIVO, teclas soltas, sem «seguir a bola»",
             pedido.get("ativo") is True and not any((pedido.get("teclas") or {}).values())
             and pedido.get("segui_alvo") is False, str(pedido)[:120])
        c.ok("a bola tem velocidade e faixa publicadas", (estado.get("bola") or {}).get("max") == 0.8)

        sse = _Sse(f"{url}/api/hud")
        sse.start()
        c.ok("o drone descola e fica A VOAR (fase do HUD em linguagem de voo)",
             _esperar(lambda: sse.ultima().get("fase") == "a_voar"
                      and abs(((sse.ultima().get("real") or {}).get("z") or 0.0) - 1.0) < 0.15, 40.0),
             f"fase {sse.ultima().get('fase')} · z {((sse.ultima().get('real') or {}).get('z'))}")
        c.ok("quem está a voar segundo o HUD: clássico, pronto",
             (sse.ultima().get("controlador") or {}).get("modo") == "classico"
             and (sse.ultima().get("controlador") or {}).get("estado") == "pronto")
        t0 = time.perf_counter()
        time.sleep(4.0)
        janela = sse.desde(t0)
        taxa = len(janela) / 4.0
        dt_sim = (janela[-1]["t"] - janela[0]["t"]) if len(janela) > 1 else 0.0
        c.ok("HUD por Server-Sent Events a ≥ 30 Hz (o runner manda 50)", taxa >= 30.0,
             f"{taxa:.1f} eventos/s durante 4 s")
        c.ok("a simulação corre em TEMPO REAL (≥ 0,9× em 4 s de relógio)", dt_sim >= 3.6,
             f"{dt_sim:.2f} s de simulação em 4,00 s de relógio")
        chaves = {"t", "fase", "vento", "est", "real", "bateria", "voo", "bola", "controlador", "motores",
                  "fovy"}
        c.ok("a amostra do HUD traz os blocos do contrato", chaves <= set(sse.ultima()),
             f"faltam {sorted(chaves - set(sse.ultima()))}")
        fovy = sse.ultima().get("fovy")
        c.ok("o FoV da câmara de bordo vem em TODAS as amostras, antes de o modo bola ligar",
             isinstance(fovy, float) and 20.0 < fovy < 160.0 and sse.ultima().get("bola") is None,
             f"fovy {fovy}° · bola {sse.ultima().get('bola')}")
        # --- otimização gráfica do MuJoCo + FPS ao vivo no HUD
        cod_gr, resp_gr = _http(f"{url}/api/graficos", {"sombras": False, "reflexos": False, "mostrar_fios_detalhes": False})
        time.sleep(0.25)
        gr_hud = sse.ultima().get("graficos") or {}
        c.ok("POST /api/graficos desliga sombras/reflexos/fios em tempo real e o HUD publica o FPS atual (> 0 fps)",
             cod_gr == 200 and resp_gr.get("ok") is True and gr_hud.get("sombras") is False
             and gr_hud.get("reflexos") is False and gr_hud.get("mostrar_fios_detalhes") is False
             and float(gr_hud.get("fps_atual") or 0.0) > 10.0,
             f"fps_atual={gr_hud.get('fps_atual')} · sombras={gr_hud.get('sombras')}")
        _http(f"{url}/api/graficos", {"sombras": True, "reflexos": True, "mostrar_fios_detalhes": True})
        # --- troca ao vivo de preset calibrado de motores e bateria (POST /api/pecas) + leitura de vazão (A) e Watts
        cod_pc, resp_pc = _http(f"{url}/api/pecas", {"preset_id": "interceptor_lipo"})
        time.sleep(0.30)
        pc_hud = sse.ultima().get("pecas") or {}
        c.ok("POST /api/pecas aplica preset calibrado ao vivo e o HUD publica cor/tamanho 3D, vazão (225 A) e Watts gastos",
             cod_pc == 200 and resp_pc.get("ok") is True and pc_hud.get("preset_id") == "interceptor_lipo"
             and pc_hud.get("motor_id") == "tmotor_mn4006_kv380"
             and pc_hud.get("bateria_id") == "lipo_6s1p_4500_alta_vazao"
             and float(pc_hud.get("vazao_max_a") or 0.0) == 225.0
             and float(pc_hud.get("watts_total") or 0.0) > 100.0,
             f"preset={pc_hud.get('preset_id')} · motor={pc_hud.get('motor_id')} ({pc_hud.get('motor_cor_nome')}) · "
             f"watts={pc_hud.get('watts_total')} W · vazão={pc_hud.get('vazao_atual_a')}/{pc_hud.get('vazao_max_a')} A")
        _http(f"{url}/api/pecas", {"preset_id": "endurance_p50b"})
        time.sleep(0.25)

        # --- W: para a frente do NARIZ
        x0 = sse.ultima()["real"]["x"]
        teclas = dict.fromkeys("wasdqe", False)
        _http(f"{url}/api/voo", {"ativo": True, "teclas": {**teclas, "w": True}})
        time.sleep(3.0)
        eco = sse.ultima().get("voo") or {}
        avanco = sse.ultima()["real"]["x"] - x0
        _http(f"{url}/api/voo", {"ativo": True, "teclas": teclas})
        c.ok("W (sem armar nada): o eco acende a tecla e o drone AVANÇA no sentido do nariz",
             (eco.get("teclas") or {}).get("w") is True and avanco > 0.8, f"Δx = {avanco:+.2f} m em 3 s")
        time.sleep(2.5)

        # --- TIRO (SPACE, Glock 25 fixa no topo do drone)
        vx_antes_tiro = float(sse.ultima()["real"]["vx"])
        pitch_antes_tiro = float(sse.ultima()["real"]["pitch"])
        cod_tiro, resp_tiro = _http(f"{url}/api/tiro", {"gatilho": True})
        c.ok("POST /api/tiro (SPACE) → 200 com o disparo registado",
             cod_tiro == 200 and (resp_tiro.get("tiro") or {}).get("disparos") == 1)
        t_tiro0 = time.perf_counter()
        time.sleep(0.25)
        _http(f"{url}/api/tiro", {"gatilho": False})
        amostras_tiro = sse.desde(t_tiro0)
        min_vx_tiro = min((float(a["real"]["vx"]) for a in amostras_tiro if a.get("real")), default=vx_antes_tiro)
        min_pitch_tiro = min((float(a["real"]["pitch"]) for a in amostras_tiro if a.get("real")), default=pitch_antes_tiro)
        tiro_hud = sse.ultima().get("tiro") or {}
        c.ok("SPACE dispara a Glock 25: o HUD regista o tiro (J ≈ 1,92 N·s) e o drone sofre o soco para trás (Δvx < −0,3 m/s) e cabra o nariz",
             tiro_hud.get("tiros") == 1 and abs(float(tiro_hud.get("impulso_ns") or 0.0) - 1.9162) < 0.01
             and min_vx_tiro - vx_antes_tiro < -0.30 and min_pitch_tiro < pitch_antes_tiro - 0.02,
             f"tiros={tiro_hud.get('tiros')} · J={tiro_hud.get('impulso_ns')} N·s · Δvx={min_vx_tiro - vx_antes_tiro:+.2f} m/s · Δpitch={min_pitch_tiro - pitch_antes_tiro:+.3f} rad")
        viu_fogo_ou_proj = any(
            bool((a.get("tiro") or {}).get("fogo_cano_ativo")) or bool((a.get("tiro") or {}).get("projetil_visivel"))
            for a in amostras_tiro
        )
        c.ok("no disparo: fogo do cano / projétil (< 50 m) e caminho de 1,0 s aparecem no HUD e o projétil apaga aos 50 m mantendo o caminho",
             viu_fogo_ou_proj and tiro_hud.get("projetil_visivel") is False
             and abs(float(tiro_hud.get("distancia_projetil_m") or 0.0) - 50.0) < 1e-3
             and tiro_hud.get("caminho_visivel") is True,
             f"proj_250ms={tiro_hud.get('projetil_visivel')} ({tiro_hud.get('distancia_projetil_m')} m) · caminho_250ms={tiro_hud.get('caminho_visivel')}")
        time.sleep(1.0)
        tiro_hud_depois = sse.ultima().get("tiro") or {}
        c.ok("após 1,0 s do disparo o caminho do projétil desaparece (`caminho_visivel = false`)",
             tiro_hud_depois.get("caminho_visivel") is False,
             f"caminho_1,25s={tiro_hud_depois.get('caminho_visivel')}")
        time.sleep(1.5)
        c.ok("após o soco do tiro a cascata recupera a pairagem (continua A VOAR)",
             sse.ultima()["fase"] == "a_voar", f"z {sse.ultima()['real']['z']:.2f} m")

        # --- vento: liga em rampa, a física leva a intensidade pedida, desliga a zero
        codigo, resposta = _http(f"{url}/api/vento-simples", {"ligado": True, "intensidade": 3.0,
                                                               "aleatorio": False, "direcao": 90.0})
        c.ok("POST /api/vento-simples → 200 com o bloco confirmado",
             codigo == 200 and resposta.get("vento_simples", {}).get("ligado") is True)
        time.sleep(0.4)
        a_meio = float(np.linalg.norm(sse.ultima()["vento"]))
        time.sleep(4.0)
        vento = sse.ultima()["vento"]
        c.ok("vento ligado: entra em rampa (a meio ainda não chegou) e a FÍSICA leva 3 m/s para +y",
             0.3 < a_meio < 2.6 and abs(vento[1] - 3.0) < 0.05 and abs(vento[0]) < 0.05,
             f"|v|(0,4 s) = {a_meio:.2f} m/s · depois {vento}")
        c.ok("com 3 m/s de vento lateral o drone continua A VOAR e perto do sítio",
             sse.ultima()["fase"] == "a_voar", f"z {sse.ultima()['real']['z']:.2f} m")

        def _sente_o_vento() -> bool:
            vb = sse.ultima().get("vento_bordo")
            return bool(vb) and 2.0 <= vb["vel"] <= 4.0 and abs((vb["direcao"] - 90.0 + 180.0) % 360.0 - 180.0) <= 25.0

        c.ok("o drone SENTE o vento a bordo: a estimativa do observador chega a 3 ± 1 m/s para 90 ± 25° (sem anemómetro)",
             _esperar(_sente_o_vento, 10.0), f"vento_bordo {sse.ultima().get('vento_bordo')} · real {sse.ultima()['vento']}")
        codigo, _ = _http(f"{url}/api/vento-simples", {"intensidade": 9})
        c.ok("intensidade fora da faixa → 400 (e o vento em vigor não muda)", codigo == 400)
        _http(f"{url}/api/vento-simples", {"aleatorio": True})
        time.sleep(6.0)
        serie = np.array([a["vento"] for a in sse.desde(time.perf_counter() - 5.0)])
        c.ok("aleatoriedade ligada: o vento passa a VARIAR (σ > 0,15 m/s) e o modo é `natural`",
             serie.shape[0] > 50 and float(np.linalg.norm(serie, axis=1).std()) > 0.15
             and sse.ultima()["vento_modo"] == "natural",
             f"σ|v| = {np.linalg.norm(serie, axis=1).std():.2f} m/s em {serie.shape[0]} amostras")
        _http(f"{url}/api/vento-simples", {"ligado": False})
        c.ok("vento desligado: volta a zero EXATO em poucos segundos",
             _esperar(lambda: float(np.linalg.norm(sse.ultima()["vento"])) == 0.0, 8.0),
             f"{sse.ultima()['vento']}")

        # --- seguir a bola: a bola anda e o detetor de bordo vê-a
        _http(f"{url}/api/bola", {"velocidade": 0.4})
        _http(f"{url}/api/voo", {"ativo": True, "teclas": teclas, "segui_alvo": True})
        c.ok("SEGUIR A BOLA: o HUD passa a trazer o bloco `bola` com deteção válida",
             _esperar(lambda: bool((sse.ultima().get("bola") or {}).get("valido")), 20.0),
             str(sse.ultima().get("bola"))[:140])
        p0 = list((sse.ultima().get("bola") or {}).get("alvo_mundo") or [0, 0, 0])
        t0 = time.perf_counter()
        time.sleep(12.0)
        bolas = [a["bola"] for a in sse.desde(t0) if a.get("bola")]
        p1 = (bolas[-1].get("alvo_mundo") if bolas else None) or p0
        c.ok("a bola MOVE-SE (aleatória, à velocidade pedida)",
             math.dist(p0, p1) > 0.3 and abs((bolas[-1] or {}).get("vel", 0.0) - 0.4) < 1e-6,
             f"deslocou-se {math.dist(p0, p1):.2f} m em 12 s")
        validos = [b for b in bolas if b.get("valido") and b.get("erro_tan")]
        frac = len(validos) / max(len(bolas), 1)
        erros = np.array([math.degrees(math.atan(math.hypot(*b["erro_tan"]))) for b in validos]) \
            if validos else np.array([90.0])
        # limiar de 5°: a lei de mira balística mantém a bola no centro da mira (< 5°); a lei antiga media 8,0°
        c.ok("o detetor de bordo VÊ a bola ≥ 90 % do tempo e o erro de centragem mediano é < 5°",
             frac >= 0.9 and float(np.median(erros)) < 5.0,
             f"vista {100 * frac:.0f} % · erro mediano {np.median(erros):.1f}° · p95 {np.percentile(erros, 95):.1f}°")
        # Liga o AUTO SHOOT com bola a 0,0 m/s (parada) e verifica que o drone coloca a bola NO ALVO e dispara acertando 100 %
        tiros_antes_auto = int((sse.ultima().get("tiro") or {}).get("tiros") or 0)
        acertos_antes_auto = int((sse.ultima().get("tiro") or {}).get("acertos_bola") or 0)
        erros_antes_auto = int((sse.ultima().get("tiro") or {}).get("erros_bola") or 0)
        _http(f"{url}/api/bola", {"velocidade": 0.0, "auto_atirar": True})
        time.sleep(2.5)
        _http(f"{url}/api/bola", {"auto_atirar": False})
        time.sleep(0.25)
        tiro_apos_auto = sse.ultima().get("tiro") or {}
        novos_tiros_auto = int(tiro_apos_auto.get("tiros") or 0) - tiros_antes_auto
        novos_acertos_auto = int(tiro_apos_auto.get("acertos_bola") or 0) - acertos_antes_auto
        novos_erros_auto = int(tiro_apos_auto.get("erros_bola") or 0) - erros_antes_auto
        c.ok("AUTO SHOOT + bola a 0,0 m/s: coloca a mira NO ALVO e dispara automaticamente APENAS quando acerta (100 % de acerto)",
             novos_tiros_auto >= 1 and novos_acertos_auto == novos_tiros_auto and novos_erros_auto == 0
             and isinstance(tiro_apos_auto.get("mira"), dict),
             f"auto_shoot: {novos_acertos_auto}/{novos_tiros_auto} acertos (erros={novos_erros_auto}) · mira={tiro_apos_auto.get('mira', {}).get('mensagem')}")
        c.ok("o drone não caiu a seguir a bola", sse.ultima()["fase"] == "a_voar")
        _http(f"{url}/api/voo", {"ativo": True, "teclas": teclas, "segui_alvo": False})
        time.sleep(1.5)
        parada_a = list((sse.ultima().get("bola") or {}).get("alvo_mundo") or [])
        time.sleep(1.5)
        parada_b = list((sse.ultima().get("bola") or {}).get("alvo_mundo") or [])
        c.ok("desligar o modo: a bola PÁRA onde está", bool(parada_a) and parada_a == parada_b, str(parada_b))

        # --- reiniciar
        _http(f"{url}/api/reiniciar", {})
        c.ok("REINICIAR: episódio novo (o HUD volta ao princípio) e o drone descola outra vez",
             _esperar(lambda: sse.ultima().get("ep", 1) >= 2 and sse.ultima().get("fase") == "a_voar", 40.0),
             f"ep {sse.ultima().get('ep')} · fase {sse.ultima().get('fase')}")
        c.ok("o stream do HUD nunca caiu", sse.erro is None and sse.is_alive(), str(sse.erro))
    finally:
        if sse is not None:
            sse.parar.set()
        try:
            os.killpg(os.getpgid(processo.pid), signal.SIGTERM)
            processo.wait(timeout=25)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(processo.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        registo.close()
    return c.fechar()


# ---------------------------------------------------------------------------------------- §5 mutações
_PREAMBULO = "import sys; sys.path[:0] = ['@FONTES@', '@AQUI@', '@RAIZ@']\n"
MUTACOES = (
    {"nome": "turbulência sem escala pela intensidade (σ fixo em vez de σ·W)",
     "ficheiro": "vento_natural.py",
     "antes": "        self.vetor = w * total\n        return self.vetor.copy()\n",
     "depois": "        self.vetor = total + (w - 1.0) * np.array([c, s, 0.0])\n        return self.vetor.copy()\n",
     "checagem": (_PREAMBULO + "import numpy as np, vento_natural as vn\n"
                  "g = vn.VentoNatural(semente=11); g.definir(True, 5.0, True, 90.0)\n"
                  "v = np.array([g.passo(0.02) for _ in range(20000)])[200:]\n"
                  "assert 0.18 < np.linalg.norm(v, axis=1).std() / 5.0 < 0.32, 'dispersao nao escala com W'\n")},
    {"nome": "ligar o vento em degrau (sem rampa)",
     "ficheiro": "vento_natural.py",
     "antes": "        self._w += (self.alvo - self._w) * (1.0 - math.exp(-dt / TAU_RAMPA_S))     # rampa de 1.ª ordem\n",
     "depois": "        self._w = self.alvo\n",
     "checagem": (_PREAMBULO + "import numpy as np, vento_natural as vn\n"
                  "g = vn.VentoNatural(semente=1); g.definir(True, 3.0, False, 0.0)\n"
                  "n = [float(np.linalg.norm(g.passo(0.02))) for _ in range(40)]\n"
                  "assert max(np.diff([0.0] + n)) < 0.12, 'degrau de vento'\n")},
    {"nome": "gerador que sai sem ser reposto (vento fantasma quando o bloco volta)",
     "ficheiro": "vento_natural.py",
     "antes": "        self.intensidade = 0.0\n        self._w = 0.0\n        self._turb[:] = 0.0\n",
     "depois": "        self.intensidade = 0.0\n        self._turb[:] = 0.0\n",
     "checagem": (_PREAMBULO + "import numpy as np, vento_natural as vn\n"
                  "g = vn.VentoNatural(semente=1); g.definir(True, 3.0, False, 0.0)\n"
                  "[g.passo(0.02) for _ in range(300)]\n"
                  "g.repor(); g.definir(False, 3.0, False, 0.0)\n"
                  "assert float(np.linalg.norm(g.passo(0.02))) == 0.0, 'vento fantasma depois de repor'\n")},
    {"nome": "arranque que deixa o vento ligado",
     "ficheiro": "sim_site.py",
     "antes": '        "vento_simples": {**base, "ligado": False, "seq": int(simples.get("seq", 0) or 0) + 1},\n',
     "depois": '        "vento_simples": {**base, "ligado": bool(simples.get("ligado", False)), '
               '"seq": int(simples.get("seq", 0) or 0) + 1},\n',
     "checagem": (_PREAMBULO + "import sim_site as s\n"
                  "a = s.controlo_de_arranque({'vento_simples': {'ligado': True, 'intensidade': 4.0, "
                  "'aleatorio': True, 'direcao': 0.0, 'seq': 1}})\n"
                  "assert a['vento_simples']['ligado'] is False, 'o vento de uma sessao anterior arrancou ligado'\n")},
    {"nome": "arranque com o controle de voo por armar",
     "ficheiro": "sim_site.py",
     "antes": '        "voo": {"ativo": True, "teclas": dict.fromkeys(("w", "a", "s", "d", "q", "e"), False),\n',
     "depois": '        "voo": {"ativo": False, "teclas": dict.fromkeys(("w", "a", "s", "d", "q", "e"), False),\n',
     "checagem": (_PREAMBULO + "import sim_site as s\n"
                  "assert s.controlo_de_arranque({})['voo']['ativo'] is True, 'o voo nao arrancou ativo'\n")},
    {"nome": "3 botões sem neutralizar o vento antigo (dois ventos somados)",
     "ficheiro": "sim_view.py",
     "antes": "            registo = replace(registo, vel=0.0, ativo=False, dinamico=None)\n",
     "depois": "            registo = replace(registo)\n",
     "checagem": (_PREAMBULO + "import json, os, tempfile, pathlib, sim_view as m\n"
                  "class E:\n"
                  "    dt_decisao = 0.02; comando = False\n"
                  "    def __init__(s): s.v = []\n"
                  "    def definir_vento(s, a, b, c=0.0): s.v.append(a)\n"
                  "    def definir_vento_dinamico(s, cfg): pass\n"
                  "f = pathlib.Path(tempfile.mkdtemp(dir=os.environ.get('TMPDIR'))) / 'c.json'\n"
                  "f.write_text(json.dumps({'vel': 3.0, 'ativo': True, 'vento_simples': {'ligado': False, "
                  "'intensidade': 2.0, 'aleatorio': False, 'direcao': 0.0, 'seq': 1}}))\n"
                  "c, e = m.Controlo(f), E(); c.verifica(e)\n"
                  "assert e.v and e.v[-1] == 0.0, 'o vento antigo ficou a soprar por baixo dos 3 botoes'\n")},
    {"nome": "`auto` a escolher a política na planta real",
     "ficheiro": "sim_site.py",
     "antes": '    if hardware and str(hardware.get("modo_acao", "ctbr")) == "ctbr":\n        return "classico"\n',
     "depois": '    if hardware and str(hardware.get("modo_acao", "ctbr")) == "ctbr":\n        return "rl"\n',
     "checagem": (_PREAMBULO + "import sim_site as s\n"
                  "assert s.resolver_controlador('auto', {'modo_acao': 'ctbr'}) == 'classico'\n")},
    {"nome": "tiro (SPACE) sem incrementar o contador de disparos",
     "ficheiro": "sim_site.py",
     "antes": '    disparos = anterior["disparos"] + (1 if gatilho else 0)\n',
     "depois": '    disparos = anterior["disparos"]\n',
     "checagem": (_PREAMBULO + "import sim_site as s\n"
                  "assert s.validar_tiro({'gatilho': True}, {})['tiro']['disparos'] == 1\n")},
)


def secao_mutacoes(pasta: Path) -> bool:
    """§5: NÃO-TAUTOLOGIA — cada mutação tem de fazer FALHAR a checagem correspondente."""
    c = Checagens(f"§5 mutações: as cópias mutadas têm de FALHAR ({len(MUTACOES)})")
    for mutacao in MUTACOES:
        texto = (_AQUI / mutacao["ficheiro"]).read_text(encoding="utf-8")
        if texto.count(mutacao["antes"]) != 1:
            c.ok(f"mutação «{mutacao['nome']}»: o texto-alvo existe UMA vez em {mutacao['ficheiro']}", False,
                 "o código mudou — atualize a mutação")
            continue
        # cópias em $TMPDIR com um `pyproject.toml` stub (os módulos procuram-no acima de si para o `_RAIZ`)
        destino = pasta / ("mut_" + re.sub(r"\W+", "_", mutacao["nome"])[:40])
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "pyproject.toml").write_text("[project]\nname = 'mutacao'\n", encoding="utf-8")
        (destino / mutacao["ficheiro"]).write_text(texto.replace(mutacao["antes"], mutacao["depois"], 1),
                                                   encoding="utf-8")
        codigo = (mutacao["checagem"].replace("@FONTES@", str(destino))
                  .replace("@AQUI@", str(_AQUI)).replace("@RAIZ@", str(_RAIZ)))
        real = subprocess.run([sys.executable, "-c", codigo.replace(str(destino), str(_AQUI), 1)],
                              capture_output=True, text=True, timeout=240, check=False)
        mutado = subprocess.run([sys.executable, "-c", codigo],
                                capture_output=True, text=True, timeout=240, check=False)
        c.ok(f"mutação «{mutacao['nome']}» FALHA a checagem (e a original passa)",
             real.returncode == 0 and mutado.returncode != 0,
             f"original exit {real.returncode} · mutado exit {mutado.returncode}"
             + (f" · {(real.stderr or '')[-160:]}" if real.returncode != 0 else ""))
    return c.fechar()


# ---------------------------------------------------------------------------------------- orquestração
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Prova do cockpit (contrato r13).")
    p.add_argument("--sem-e2e", action="store_true", help="salta a §4 (integração real com o runner)")
    p.add_argument("--porta", type=int, default=PORTA_TESTE)
    args = p.parse_args(argv)
    pasta = Path(os.environ.get("TMPDIR") or tempfile.gettempdir()) / "teste_cockpit"
    resultados = [secao_gerador(), secao_servidor(), secao_runner(pasta)]
    if not args.sem_e2e:
        resultados.append(secao_integracao(pasta, args.porta))
    resultados.append(secao_mutacoes(pasta))
    n_ok = sum(1 for r in resultados if r)
    print(f"\nRESUMO: {n_ok}/{len(resultados)} secoes TUDO OK", flush=True)
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
