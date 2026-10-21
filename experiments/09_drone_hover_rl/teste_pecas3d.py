"""experiments/09_drone_hover_rl/teste_pecas3d.py — PROVA do drone «100% realista» e da página das PEÇAS 3D (`/pecas`).

Pedido do dono (2026-10-20): modelagem e partes móveis realistas, baterias fiéis, o Raspberry Pi 5 ligado à bateria por
cabo, motores com a forma e o tamanho reais, dobradiças verídicas, abraçadeiras presas, parafusos e porcas modelados, e
uma página onde se veja cada peça em 3D com as instruções de montagem.

O que se prova (tudo por execução; temporários SÓ em `$TMPDIR`):
  §1 EXPORTAÇÃO — o JSON da página sai do MESMO modelo do simulador: todos os geoms visíveis numa peça do catálogo, as
     malhas fundidas cortadas por faixas de faces que cobrem a malha inteira sem sobreposição, os passos numerados de
     seguida e com peças que existem, as ferragens com uma malha completa por tipo e as quantidades certas, os 4
     rotores com o sentido real, as juntas com os limites do MuJoCo;
  §2 API — `GET /api/pecas3d` do `sim_site.py` (gzip, ETag e 304, `?build=` válido/400) e `GET /pecas` serve a SPA;
  §3 SIMULADOR — o sem-fim de cada ombro roda razão·q em torno do SEU eixo (medido no `geom_quat`), a troca ao vivo
     mostra o motor e o pack REAIS da variante (e esconde os outros), e a física fica idêntica bit a bit com e sem
     detalhes (`ver.conferir_fisica`);
  §4 AUDITORIA DE REALISMO — `auditoria.auditar` sem falhas nos 2 builds (parafusos normalizados, assentes e em furos,
     porcas com rosca de fora, cabos ligados às âncoras, cadeia de energia até ao USB-C do Pi 5, abraçadeiras presas,
     eixos = juntas, todos os geoms com peça);
  §1b A PÁGINA DO DRONE (pedido de 2026-10-20) — nada da carga útil (geoms, ligações, fichas, passos, textos), um
     «porque é necessária» em cada peça, custos que somam (R$ e US$), as peças IMPRESSAS em ABS com massa medida,
     malha fechada, a caber na mesa e as cópias iguais num só STL, e as BIELAS dos ombros de fuso;
  §2b STL — `GET /api/pecas3d/stl.zip` (todos + LEIA-ME) e `GET /api/pecas3d/stl?arquivo=` (STL binário em mm, com os
     triângulos e o volume do JSON, assente em z = 0); nome inválido → 404;
  §3b BIELA — a animação da planta põe o corpo do atuador e a porca alinhados com B→A e o fuso a girar sobre o seu
     eixo, com L(q) = a do catálogo (a mesma geometria da física);
  §5 MUTAÇÕES (`--mutacao`) — o teste NÃO é tautológico: cada mutação, numa CÓPIA das fontes, tem de FALHAR a checagem
     certa.

Uso:
    MUJOCO_GL=egl .venv/bin/python experiments/09_drone_hover_rl/teste_pecas3d.py              # §1–§4
    MUJOCO_GL=egl .venv/bin/python experiments/09_drone_hover_rl/teste_pecas3d.py --mutacao    # §5
    ... --rapido   # §1–§3 sem a física nem a auditoria (é o que as mutações usam)
    ... --fontes DIR   # o MESMO teste contra uma cópia das fontes
"""
from __future__ import annotations

import argparse
import gzip
import itertools
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

_REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def _raiz_das_fontes(argv: list[str]) -> Path:
    for i, a in enumerate(argv):
        if a == "--fontes" and i + 1 < len(argv):
            return Path(argv[i + 1]).resolve()
        if a.startswith("--fontes="):
            return Path(a.split("=", 1)[1]).resolve()
    return _REPO


RAIZ = _raiz_das_fontes(sys.argv)
_EXP = RAIZ / "experiments" / "09_drone_hover_rl"
sys.path[:0] = [str(RAIZ), str(_EXP)]
os.environ.setdefault("MUJOCO_GL", "egl")

import mujoco
import numpy as np

BUILDS = ("articulado_15pol_abs", "articulado_15pol_mn5006", "endurance_15pol_p50b")
BUILD_ACESSIVEL = "articulado_15pol_abs"
# palavras da carga útil que NÃO podem aparecer na página das peças (pedido do dono, 2026-10-20)
PROIBIDAS = r"\b(armas?|glock|carga útil|tiros?|gatilho|muniç\w*|proj[ée]te?is|proj[ée]til|recuo|mira[rs]?)\b"


class Checagens:
    def __init__(self):
        self.linhas, self.falhas = [], []

    def ok(self, nome: str, passou: bool, detalhe: str = "") -> bool:
        self.linhas.append(nome)
        if not passou:
            self.falhas.append(nome)
        print(f"{'[ OK  ]' if passou else '[FALHA]'} {nome}" + (f" — {detalhe}" if detalhe else ""), flush=True)
        return passou


def _titulo(t: str) -> None:
    print(f"\n=== {t}", flush=True)


def _b64f(s: str) -> np.ndarray:
    import base64
    return np.frombuffer(base64.b64decode(s), dtype="<f4")


def _b64i(s: str, tipo: str) -> np.ndarray:
    import base64
    return np.frombuffer(base64.b64decode(s), dtype="<u2" if tipo == "u16" else "<u4")


# ============================================================================================ §1 exportação
def checa_exportacao(c: Checagens) -> dict:
    from lab import drone_rpi as dr
    from lab.drone_rpi.detalhes import exportar
    from lab.drone_rpi.detalhes.pecas import CATEGORIAS
    _titulo("§1 exportação: o JSON da página sai do modelo do simulador, peça a peça")
    saida = {}
    for b in BUILDS:
        d = exportar.exportar(b)
        saida[b] = d
        hw = dr.hardware(b)
        est = d["estatisticas"]
        c.ok(f"[§1] {b}: todos os geoms visíveis numa peça do catálogo (nada em «outros»)",
             not [g for g in d["geoms"] if g["peca"] in ("outros",)] and not est["sem_peca"],
             f"{len(d['geoms'])} geoms; sem peça: {est['sem_peca'][:5]}")
        cats = {x["id"] for x in CATEGORIAS}
        c.ok(f"[§1] {b}: cada peça tem ficha com nome e categoria conhecida",
             all(p.get("nome") and p.get("categoria") in cats for p in d["pecas"].values()),
             f"{len(d['pecas'])} fichas")
        # faixas: cobrem a malha inteira, sem sobreposição
        por_malha: dict[tuple, list] = {}
        for g in d["geoms"]:
            if g["tipo"] == "mesh" and g.get("faces"):
                por_malha.setdefault((g["nome"], g["malha"]), []).append(tuple(g["faces"]))
        mal = []
        for (nome, mi), fx in por_malha.items():
            fx.sort()
            nf = d["malhas"][mi]["nf"]
            cont = fx[0][0] == 0 and fx[-1][1] == nf and all(a[1] == b_[0] for a, b_ in itertools.pairwise(fx))
            if not cont:
                mal.append(nome)
        c.ok(f"[§1] {b}: as faixas de faces das malhas fundidas cobrem cada malha inteira, de seguida",
             bool(por_malha) and not mal, f"{len(por_malha)} malhas fundidas; mal cortadas: {mal[:4]}")
        # passos
        ns = [p["n"] for p in d["passos"]]
        c.ok(f"[§1] {b}: passos de montagem numerados 1..N sem buracos, todos com peças que existem",
             ns == list(range(1, len(ns) + 1)) and all(all(x in d["pecas"] for x in p["pecas"]) for p in d["passos"]),
             f"{len(ns)} passos")
        # ferragens
        tipos = d["ferragens"]["tipos"]
        inst = d["ferragens"]["instancias"]
        conta: dict[str, int] = {}
        for it in inst:
            conta[it["tipo"]] = conta.get(it["tipo"], 0) + 1
        sem_malha = [k for k, t in tipos.items() if t["tipo"] != "abracadeira" and not t["malhas"]]
        quant = [k for k, t in tipos.items() if t["tipo"] != "abracadeira" and t["qtd"] != conta.get(k, 0)]
        n_paraf = sum(1 for it in inst if tipos[it["tipo"]]["tipo"] == "parafuso")
        c.ok(f"[§1] {b}: ferragens com malha completa por tipo e quantidades = instâncias (há parafusos)",
             n_paraf > 0 and not sem_malha and not quant,
             f"{len(inst)} instâncias, {n_paraf} parafusos, {len(tipos)} tipos")
        # malhas válidas (índices dentro dos vértices)
        ruins = []
        for i, mm in enumerate(d["malhas"]):
            idx = _b64i(mm["i"], mm["itipo"])
            if idx.size != 3 * mm["nf"] or (idx.size and int(idx.max()) >= mm["nv"]) or _b64f(mm["v"]).size != 3 * mm["nv"]:
                ruins.append(i)
        c.ok(f"[§1] {b}: malhas decodificáveis (índices dentro dos vértices)", not ruins, f"{len(d['malhas'])} malhas")
        # rotores e juntas
        giro = list(hw.GIRO)
        rot = {r["k"]: r for r in d.get("rotores", [])}
        c.ok(f"[§1] {b}: 4 rotores com o sentido real do catálogo (GIRO)",
             len(rot) == 4 and all(rot[k]["giro"] == int(giro[k - 1]) for k in rot), f"{[rot[k]['giro'] for k in sorted(rot)]}")
        if hw.bracos is not None:
            juntas = [cp["junta"] for cp in d["corpos"] if cp["junta"]]
            lim_o = [math.degrees(x) for x in hw.bracos.ombro.limites] if max(abs(x) for x in hw.bracos.ombro.limites) < 3.2 \
                else list(hw.bracos.ombro.limites)
            c.ok(f"[§1] {b}: 8 juntas exportadas com os limites do MuJoCo",
                 len(juntas) == 8 and all(j["limites_graus"] for j in juntas),
                 f"ombro {juntas[0]['limites_graus'] if juntas else None} (catálogo {lim_o})")
        tam = len(json.dumps(d, separators=(",", ":")).encode())
        c.ok(f"[§1] {b}: o JSON cabe numa página (< 40 MB antes do gzip)", tam < 40e6, f"{tam / 1e6:.1f} MB")
        checa_pagina_drone(c, b, d, hw)
    return saida


def checa_pagina_drone(c: Checagens, b: str, d: dict, hw) -> None:
    """§1b — o que o dono pediu para a página: sem carga útil, «porque» em tudo, custos, impressão 3D, bielas."""
    import re
    proib = re.compile(PROIBIDAS, re.IGNORECASE)
    nomes_fora = [g["nome"] for g in d["geoms"] if re.match(r"^(arma_|caminho_tiro_|projetil_tiro_)", g["nome"])]
    textos = []
    for pid, f in d["pecas"].items():
        for campo in ("nome", "resumo", "como_funciona", "porque"):
            textos.append((f"{pid}.{campo}", str(f.get(campo) or "")))
        for k_, v_ in f.get("specs", []):
            textos.append((f"{pid}.spec", f"{k_} {v_}"))
    for ps in d["passos"]:
        textos.append((f"passo {ps['n']}", ps["titulo"] + " " + ps["texto"]))
    achados = [(onde, proib.search(t).group(0)) for onde, t in textos if proib.search(t)]
    lig = [x["id"] for x in d["ligacoes"] if "arma" in str(x.get("de", "")) + str(x.get("para", ""))]
    c.ok(f"[§1b] {b}: a página NÃO mostra nem descreve a carga útil (geoms, peça, ligações, textos)",
         not nomes_fora and "carga_util" not in d["pecas"] and not lig and not achados,
         f"geoms {nomes_fora[:2]} · ligações {lig[:2]} · textos {achados[:3]}")
    sem = [pid for pid, f in d["pecas"].items() if pid not in ("outros", "ferragens") and len(str(f.get("porque") or "")) < 60]
    c.ok(f"[§1b] {b}: cada peça explica PORQUE é necessária ao projeto (≥ 60 caracteres)", not sem,
         f"{len(d['pecas'])} peças; sem «porque»: {sem[:6]}")
    cu = d.get("custos") or {}
    soma = sum(e["total_usd"] for e in cu.get("por_peca", {}).values())
    fora = [pid for pid in cu.get("por_peca", {}) if pid not in d["pecas"]]
    c.ok(f"[§1b] {b}: custos de referência que SOMAM (total = Σ peças, todas na lista, R$ = US$ × câmbio)",
         cu.get("total_usd", 0) > 100 and abs(soma - cu["total_usd"]) < 0.05 and not fora
         and abs(cu["total_brl"] - cu["total_usd"] * cu["cambio_usd_brl"]) < 0.06,
         f"{cu.get('total_usd')} US$ = {cu.get('total_brl')} R$ · fora da lista {fora[:3]}")
    imp = d.get("impressas") or {}
    if b == BUILD_ACESSIVEL:
        ruins = [ch for ch, v in imp.items() if not (v.get("arquivo") and v["massa_g"] > 0 and v.get("fechada")
                                                      and v.get("cabe_mesa"))]
        c.ok(f"[§1b] {b}: peças IMPRESSAS em ABS, cada uma com STL, massa medida, malha fechada e a caber na mesa",
             len(imp) >= 4 and not ruins, f"{len(imp)} peças × instância; com problemas: {ruins[:4]}")
        por_arq: dict[str, list] = {}
        for v in imp.values():
            por_arq.setdefault(v["arquivo"], []).append(v)
        coer = all(len(vs) == vs[0]["copias"] == len(vs[0]["instancias_iguais"]) for vs in por_arq.values())
        c.ok(f"[§1b] {b}: as cópias IGUAIS de uma peça saem num só STL (com a quantidade a imprimir)",
             coer and any(len(vs) > 1 for vs in por_arq.values()),
             f"{len(por_arq)} STL para {len(imp)} peças × instância")
        fz = hw.bracos.ombro.fuso if hw.bracos is not None else None
        bl = d.get("bielas") or []
        papeis: dict[int, set] = {}
        for g in d["geoms"]:
            if (g.get("anim") or {}).get("tipo") == "biela":
                papeis.setdefault(g["anim"]["k"], set()).add(g["anim"]["papel"])
        compl = not papeis or all(papeis.get(k) == {"base", "veio", "porca"} for k in range(1, 5))
        c.ok(f"[§1b] {b}: as 4 BIELAS dos ombros de fuso exportadas com a geometria do catálogo (e os 3 papéis animados)",
             fz is not None and len(bl) == 4 and compl
             and all(abs(np.linalg.norm(np.subtract(x["a"], x["b"])) - fz.comprimento_em(0.0)) < 1e-6 for x in bl),
             f"{len(bl)} bielas · papéis {dict(sorted((k, sorted(v)) for k, v in papeis.items()))}")
    else:
        c.ok(f"[§1b] {b}: sem peças impressas declaradas como tal fora do build acessível (ou todas válidas)",
             all(v.get("fechada", True) for v in imp.values()), f"{len(imp)} impressas")


# ============================================================================================ §2 API
def _porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def checa_api(c: Checagens) -> None:
    import sim_site as ss
    _titulo("§2 API: GET /api/pecas3d (gzip, ETag/304, ?build=) e GET /pecas (a SPA)")
    tmp = Path(tempfile.mkdtemp(prefix="teste_pecas3d_api_", dir=os.environ.get("TMPDIR")))
    porta = _porta_livre()
    srv = ss.Servidor(tmp / "c.json", tmp / "t.jsonl", "127.0.0.1", porta, False, None, None)
    httpd = ss.ServidorHTTP(("127.0.0.1", porta), ss.criar_handler(srv))
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{porta}"
    try:
        req = urllib.request.Request(f"{base}/api/pecas3d", headers={"Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=120) as r:
            corpo, enc, etag = r.read(), r.headers.get("Content-Encoding"), r.headers.get("ETag")
            build_h = r.headers.get("X-Pecas3d-Build")
        try:                                     # um servidor que não comprime tem de FALHAR a checagem, não rebentar
            dados = json.loads(gzip.decompress(corpo) if enc == "gzip" else corpo)
        except (OSError, ValueError):
            dados = {}
        c.ok("[§2] GET /api/pecas3d: 200, gzip, ETag e o build do cockpit (o articulado)",
             enc == "gzip" and bool(etag) and dados.get("build") == ss.BUILD_COCKPIT_OMISSAO == build_h,
             f"{len(corpo) / 1e6:.2f} MB gzip, build {dados.get('build')}")
        req2 = urllib.request.Request(f"{base}/api/pecas3d", headers={"If-None-Match": etag or ""})
        try:
            urllib.request.urlopen(req2, timeout=60)
            cod = 200
        except urllib.error.HTTPError as e:
            cod = e.code
        c.ok("[§2] o mesmo pedido com If-None-Match → 304 (não volta a gerar nem a enviar)", cod == 304, f"HTTP {cod}")
        try:
            urllib.request.urlopen(f"{base}/api/pecas3d?build=nao_existe", timeout=60)
            cod = 200
        except urllib.error.HTTPError as e:
            cod = e.code
        c.ok("[§2] ?build= desconhecido → 400 com o motivo", cod == 400, f"HTTP {cod}")
        with urllib.request.urlopen(f"{base}/api/pecas3d?build=endurance_15pol_p50b", timeout=120) as r:
            d2 = json.loads(r.read())
        c.ok("[§2] ?build=endurance_15pol_p50b → as peças desse build (sem gzip quando o cliente não o pede)",
             d2.get("build") == "endurance_15pol_p50b", f"{len(d2.get('geoms', []))} geoms")
        with urllib.request.urlopen(f"{base}/pecas", timeout=30) as r:
            html = r.read().decode("utf-8", errors="replace")
        c.ok("[§2] GET /pecas serve a SPA (o index.html do site, com o script da página)",
             "<div id=\"root\">" in html or "npm run build" in html, f"{len(html)} bytes")
        checa_stl(c, base)
    finally:
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(tmp, ignore_errors=True)


def checa_stl(c: Checagens, base: str) -> None:
    """§2b — os modelos para imprimir: o ZIP e cada STL (binário, mm) batem com o JSON."""
    import io
    import struct
    import zipfile
    with urllib.request.urlopen(f"{base}/api/pecas3d?build={BUILD_ACESSIVEL}", timeout=180) as r:
        d = json.loads(r.read())
    imp = d.get("impressas") or {}
    arqs = {v["arquivo"]: v for v in imp.values()}
    with urllib.request.urlopen(f"{base}/api/pecas3d/stl.zip?build={BUILD_ACESSIVEL}", timeout=180) as r:
        tipo, zb = r.headers.get("Content-Type"), r.read()
    with zipfile.ZipFile(io.BytesIO(zb)) as z:
        nomes = set(z.namelist())
    c.ok("[§2b] GET /api/pecas3d/stl.zip: ZIP com TODOS os STL do JSON e o LEIA-ME das definições",
         tipo == "application/zip" and set(arqs) <= nomes and "LEIA-ME.txt" in nomes,
         f"{len(nomes)} ficheiros · {len(arqs)} STL no JSON")
    erros = []
    for arq, v in list(arqs.items())[:6]:
        with urllib.request.urlopen(f"{base}/api/pecas3d/stl?build={BUILD_ACESSIVEL}&arquivo={arq}", timeout=60) as r:
            corpo = r.read()
        n = struct.unpack("<I", corpo[80:84])[0]
        rec = np.frombuffer(corpo[84:], dtype=[("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("a", "<u2")])
        tri = rec["v"].astype(float)
        vol = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0) / 1000.0
        if not (len(corpo) == 84 + 50 * n == 84 + 50 * len(rec) and n == v["triangulos"]
                and abs(float(tri[..., 2].min())) < 1e-3 and abs(vol - v["volume_cm3"]) <= 0.02 * v["volume_cm3"] + 1e-3):
            erros.append(f"{arq}: n {n}/{v['triangulos']} · zmin {tri[..., 2].min():.3f} · vol {vol:.2f}/{v['volume_cm3']}")
    c.ok("[§2b] cada STL é binário em mm, com os triângulos e o VOLUME do JSON (±2 %) e assente em z = 0",
         bool(arqs) and not erros, "; ".join(erros[:3]) or f"{min(len(arqs), 6)} STL conferidos")
    try:
        urllib.request.urlopen(f"{base}/api/pecas3d/stl?build={BUILD_ACESSIVEL}&arquivo=..%2Fsim_site.py", timeout=60)
        cod = 200
    except urllib.error.HTTPError as e:
        cod = e.code
    c.ok("[§2b] pedido de um ficheiro que não é um STL das peças → 404", cod == 404, f"HTTP {cod}")


# ============================================================================================ §3 simulador
def checa_simulador(c: Checagens, com_fisica: bool) -> None:
    from env_real import DroneRealEnv

    from lab.drone_rpi import componentes as comp
    from lab.drone_rpi.detalhes import RGBA_OMISSAO
    _titulo("§3 simulador: o sem-fim roda razão·q, a troca ao vivo mostra as peças reais, a física não muda")
    env = DroneRealEnv(build="articulado_15pol_mn5006", modo_acao="ctbr", comando=True, episodio_s=5.0)
    env.reset(seed=3)
    pl, m = env.planta, env.model
    c.ok("[§3] o articulado tem os 4 sem-fins animados (eixo, razão e sentido no modelo)",
         len(pl._eixos_anim) == 4, f"{len(pl._eixos_anim)} eixos")
    if pl._eixos_anim:
        erros = []
        for q_teste in (0.31, -0.27):
            for qadr, fator, ponto, u, gids, rel, q0 in pl._eixos_anim:
                env.data.qpos[qadr] = q_teste
                pl._aplicar_animacao_eixos()
                th = fator * q_teste
                # ângulo medido: rotação relativa q_atual ⊗ q0⁻¹ em torno de u
                for g, q0g in zip(gids, q0, strict=True):
                    qa = m.geom_quat[g]
                    qi = np.array([q0g[0], -q0g[1], -q0g[2], -q0g[3]])
                    w = np.zeros(4)
                    mujoco.mju_mulQuat(w, qa, qi)
                    ang = 2.0 * math.atan2(float(np.dot(w[1:], u)), float(w[0]))
                    d_ = (ang - th + math.pi) % (2 * math.pi) - math.pi
                    if abs(d_) > 1e-6:
                        erros.append(abs(d_))
                env.data.qpos[qadr] = 0.0
        pl._aplicar_animacao_eixos()
        fatores = sorted({round(abs(e[1]), 6) for e in pl._eixos_anim})
        c.ok("[§3] cada sem-fim roda EXATAMENTE razão·sentido·q em torno do seu eixo (|razão| = 20)",
             not erros and fatores == [20.0], f"fatores {fatores}; desvio máx {max(erros) if erros else 0:.2e} rad")
    # troca ao vivo — variantes reais
    tipos = {v["tipo"] for v in pl._variantes}
    c.ok("[§3] o modelo traz as variantes reais dos motores e das baterias do painel", {"motor", "bateria"} <= tipos,
         f"{len(pl._variantes)} variantes ({sorted(tipos)})")
    erros = []
    for pid, spec in comp.PRESETS_PROPULSAO_PAINEL.items():
        env.trocar_pecas(preset_id=pid)
        for tipo, ident in (("motor", spec["motor_id"]), ("bateria", spec["bateria_id"])):
            # um geom PARTILHADO por várias variantes (cintas, travessa…) fica visível se for da escolhida
            da_escolhida = {g for v in pl._variantes if v["tipo"] == tipo and v["id"] == ident for g in v["gids"]}
            for v in pl._variantes:
                if v["tipo"] != tipo:
                    continue
                for g in v["gids"]:
                    visivel = list(m.geom_rgba[g]) == list(RGBA_OMISSAO)
                    escondido = float(m.geom_rgba[g, 3]) == 0.0
                    if (g in da_escolhida and not visivel) or (g not in da_escolhida and not escondido):
                        erros.append(f"{pid}:{tipo}:{v['id']}")
                        break
    c.ok("[§3] cada preset do painel mostra o SEU motor e o SEU pack reais e esconde os outros",
         bool(pl._variantes) and not erros, f"{len(comp.PRESETS_PROPULSAO_PAINEL)} presets; erradas: {sorted(set(erros))[:4]}")
    env.close() if hasattr(env, "close") else None
    checa_biela(c)
    if com_fisica:
        from lab.drone_rpi.detalhes import ver
        for b in BUILDS:
            e = ver.conferir_fisica(b, "todos")
            c.ok(f"[§3] {b}: voo de 600 passos IDÊNTICO bit a bit com e sem detalhes", not e, "; ".join(e))


def checa_biela(c: Checagens) -> None:
    """§3b — a animação da biela na planta, com 3 geoms de prova no braço 1 (independente do desenho da estrutura)."""
    from lab import drone_rpi as dr
    from lab.drone_rpi import modelo
    hw = dr.hardware(BUILD_ACESSIVEL)
    fz = hw.bracos.ombro.fuso
    ant = os.environ.get("DRONE_DETALHES")
    os.environ["DRONE_DETALHES"] = "nenhum"
    try:
        spec = modelo.construir_spec(hw)
    finally:
        if ant is None:
            os.environ.pop("DRONE_DETALHES", None)
        else:
            os.environ["DRONE_DETALHES"] = ant
    corpo, braco = spec.body("drone"), spec.body("braco1")
    h = np.array(braco.pos)
    sx, sy = math.copysign(1.0, h[0]), math.copysign(1.0, h[1])
    a, b = (np.array(v) for v in fz.vetores(sx, sy))
    d0 = (a - b) / np.linalg.norm(a - b)
    lat = np.cross(d0, [0.0, 1.0, 0.0])
    lat /= np.linalg.norm(lat)
    qz = np.zeros(4)
    mujoco.mju_quatZ2Vec(qz, d0)
    vis = {"group": 3, "mass": 0, "contype": 0, "conaffinity": 0}
    corpo.add_geom(name="ombro1_fuso_base_prova", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.003, 0.003, 0.01],
                   pos=list(h + b + 0.012 * d0 + 0.006 * lat), quat=list(qz), **vis)
    corpo.add_geom(name="ombro1_fuso_veio_prova", type=mujoco.mjtGeom.mjGEOM_SPHERE, size=[0.002, 0, 0],
                   pos=list(h + b + 0.03 * d0 + 0.004 * lat), **vis)
    braco.add_geom(name="ombro1_fuso_porca_prova", type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.004, 0.004, 0.008],
                   pos=list(a - 0.01 * d0), quat=list(qz), **vis)
    m = spec.compile()
    d = mujoco.MjData(m)
    pl = dr.Planta(hw, m, d, rng=np.random.default_rng(0))
    jq = m.jnt_qposadr[m.joint("ombro1").id]
    gb, gv, gp = (m.geom(n).id for n in ("ombro1_fuso_base_prova", "ombro1_fuso_veio_prova", "ombro1_fuso_porca_prova"))
    erros = []
    for q in (0.0, 0.35, -0.5):
        d.qpos[jq] = q
        pl._aplicar_animacao_eixos()
        mujoco.mj_forward(m, d)
        bd = m.body("drone").id
        rb, pb = d.xmat[bd].reshape(3, 3), d.xpos[bd]
        B = pb + rb @ (h + b)
        ry = np.array([[math.cos(q), 0, math.sin(q)], [0, 1, 0], [-math.sin(q), 0, math.cos(q)]])
        A = pb + rb @ (h + ry @ a)
        u = (A - B) / np.linalg.norm(A - B)
        L = float(np.linalg.norm(A - B))
        ex_b, ex_p = d.geom_xmat[gb].reshape(3, 3)[:, 2], d.geom_xmat[gp].reshape(3, 3)[:, 2]
        pv = d.geom_xpos[gv] - B
        dist_eixo = float(np.linalg.norm(pv - (pv @ u) * u))
        pp = d.geom_xpos[gp] - A
        if not (abs(L - fz.comprimento_em(q, sx, sy)) < 1e-9 and abs(abs(ex_b @ u) - 1) < 1e-9 and abs(abs(ex_p @ u) - 1) < 1e-9
                and abs(dist_eixo - 0.004) < 1e-9 and np.linalg.norm(pp + 0.01 * u) < 1e-9):
            erros.append(f"q={q}: L {L * 1000:.2f}/{fz.comprimento_em(q, sx, sy) * 1000:.2f} mm · ∥ {ex_b @ u:.4f}/{ex_p @ u:.4f}"
                         f" · eixo {dist_eixo * 1000:.3f} mm")
    c.ok("[§3b] biela na planta: corpo do atuador e porca alinhados com B→A, fuso a girar sobre o seu eixo, L(q) do catálogo",
         len(pl._bielas_anim) == 1 and not erros, "; ".join(erros[:2]) or "3 poses do ombro")


# ============================================================================================ §4 auditoria
def checa_auditoria(c: Checagens) -> None:
    from lab.drone_rpi.detalhes import auditoria
    _titulo("§4 auditoria de realismo (parafusos, porcas, cabos, cadeia de energia, abraçadeiras, eixos, peças)")
    from lab import drone_rpi as dr
    for b in BUILDS:
        r = auditoria.auditar(b)
        rigido = dr.hardware(b).bracos is None
        for k in ("F1", "F2", "F3", "F4", "C1", "A1", "E1", "P1"):
            v = r[k]
            vazio_ok = k == "E1" and rigido               # num drone rígido não há dobradiças a conferir
            c.ok(f"[§4] {b}: {k} {auditoria.NOMES[k]}", (v["total"] > 0 or vazio_ok) and v["falhas"] == 0,
                 f"{v['total']} verificados, {v['falhas']} falhas {v['exemplos'][:2]}")
        c.ok(f"[§4] {b}: C2 {auditoria.NOMES['C2']}", r["C2"]["estado"] == "ok", " → ".join(r["C2"]["caminho"]))


# ============================================================================================ §5 mutações
def _mut_faixas(t: str) -> str:
    antigo = "        if nome in regs_faixas and tipo == \"mesh\":"
    assert t.count(antigo) == 1
    return t.replace(antigo, "        if False:")


def _mut_semfim(t: str) -> str:
    antigo = "            th = fator * float(q[qadr])"
    assert t.count(antigo) == 1
    return t.replace(antigo, "            th = float(q[qadr])")


def _mut_variante(t: str) -> str:
    antigo = "                if g not in visiveis:\n                    m.geom_rgba[g] = [0.0, 0.0, 0.0, 0.0]"
    assert t.count(antigo) == 1
    return t.replace(antigo, "                if g not in visiveis:\n                    pass")


def _mut_gzip(t: str) -> str:
    antigo = '        aceita_gzip = "gzip" in (self.headers.get("Accept-Encoding") or "")'
    assert t.count(antigo) == 1
    return t.replace(antigo, "        aceita_gzip = False")


def _mut_passos(t: str) -> str:
    antigo = "    for i, p_ in enumerate(lista, 1):           # numerados DEPOIS de tirar os passos sem peças neste build\n        p_[\"n\"] = i"
    assert t.count(antigo) == 1
    return t.replace(antigo, "    for i, p_ in enumerate(lista, 1):\n        p_[\"n\"] = 2 * i")


def _mut_arma(t: str) -> str:
    antigo = '_FORA = re.compile(r"^(chao$|caminho_tiro_|projetil_tiro_|arma_|helice\\d+$)")'
    assert t.count(antigo) == 1, "padrão _FORA"
    return t.replace(antigo, '_FORA = re.compile(r"^(chao$|caminho_tiro_|projetil_tiro_|helice\\d+$)")')


def _mut_porque(t: str) -> str:
    antigo = '        f.setdefault("porque", PORQUE.get(pid, ""))'
    assert t.count(antigo) == 1
    return t.replace(antigo, '        f.setdefault("porque", "")')


def _mut_copias(t: str) -> str:
    antigo = "            if mesma_peca(*locais[chs[0]], V, F):"
    assert t.count(antigo) == 1
    return t.replace(antigo, "            if False:")


def _mut_biela(t: str) -> str:
    antigo = "            rb = self._rot_min(d0, d)"
    assert t.count(antigo) == 1
    return t.replace(antigo, "            rb = np.eye(3)")


MUTACOES = (
    ("arma-na-pagina", "lab/drone_rpi/detalhes/exportar.py", _mut_arma, "carga útil"),
    ("porque-vazio", "lab/drone_rpi/detalhes/pecas.py", _mut_porque, "PORQUE"),
    ("stl-sem-copias", "lab/drone_rpi/detalhes/impressao.py", _mut_copias, "cópias IGUAIS"),
    ("biela-parada", "lab/drone_rpi/planta.py", _mut_biela, "biela na planta"),
    ("exportar-sem-faixas", "lab/drone_rpi/detalhes/exportar.py", _mut_faixas, "faixas de faces"),
    ("semfim-sem-razao", "lab/drone_rpi/planta.py", _mut_semfim, "razão·sentido·q"),
    ("variante-nao-esconde", "lab/drone_rpi/planta.py", _mut_variante, "esconde os outros"),
    ("api-sem-gzip", "experiments/09_drone_hover_rl/sim_site.py", _mut_gzip, "gzip"),
    ("passos-com-buracos", "lab/drone_rpi/detalhes/pecas.py", _mut_passos, "sem buracos"),
)


def _montar_copia(destino: Path) -> None:
    shutil.copy2(RAIZ / "pyproject.toml", destino / "pyproject.toml")
    shutil.copytree(RAIZ / "lab", destino / "lab", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(RAIZ / "models" / "drone_rpi", destino / "models" / "drone_rpi")
    exp = destino / "experiments" / "09_drone_hover_rl"
    exp.mkdir(parents=True)
    for f in _EXP.glob("*.py"):
        shutil.copy2(f, exp / f.name)
    (exp / "site").mkdir()
    if (_EXP / "site" / "dist").is_dir():
        shutil.copytree(_EXP / "site" / "dist", exp / "site" / "dist")


def checa_mutacoes(c: Checagens) -> None:
    _titulo("§5 mutações: cada mutação, numa CÓPIA das fontes, tem de FALHAR a checagem certa")
    base = Path(tempfile.mkdtemp(prefix="teste_pecas3d_mut_", dir=os.environ.get("TMPDIR")))
    try:
        ctl = base / "controlo"
        ctl.mkdir()
        _montar_copia(ctl)
        r0 = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--rapido", "--fontes", str(ctl)],
                            capture_output=True, text=True, timeout=900, check=False)
        c.ok("[§5] controlo: a cópia SEM mutação passa", r0.returncode == 0, f"exit {r0.returncode}")
        for nome, rel, mutar, marca in MUTACOES:
            copia = base / nome
            copia.mkdir()
            _montar_copia(copia)
            alvo = copia / rel
            alvo.write_text(mutar(alvo.read_text(encoding="utf-8")), encoding="utf-8")
            r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--rapido", "--fontes", str(copia)],
                               capture_output=True, text=True, timeout=900, check=False)
            linhas = [ln for ln in r.stdout.splitlines() if "[FALHA]" in ln and marca in ln]
            c.ok(f"[§5] mutação {nome} ({rel}) FALHA na checagem certa ('{marca}')", r.returncode != 0 and bool(linhas),
                 f"exit {r.returncode} · {len(linhas)} falha(s) com a marca")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Prova do drone realista e da página das peças 3D.")
    p.add_argument("--mutacao", action="store_true")
    p.add_argument("--rapido", action="store_true", help="§1–§3 sem a física nem a auditoria")
    p.add_argument("--fontes", type=Path, default=_REPO)
    a = p.parse_args(argv)
    c = Checagens()
    if a.mutacao:
        checa_mutacoes(c)
    else:
        import lab
        c.ok("[§0] o teste corre contra as fontes pedidas", Path(lab.__file__).resolve().parents[1] == RAIZ,
             str(Path(lab.__file__).resolve().parents[1]))
        checa_exportacao(c)
        checa_api(c)
        checa_simulador(c, com_fisica=not a.rapido)
        if not a.rapido:
            checa_auditoria(c)
    print(f"\n[teste] {len(c.linhas) - len(c.falhas)}/{len(c.linhas)} checagens OK", flush=True)
    if c.falhas:
        for n in c.falhas:
            print(f"[teste] FALHOU: {n}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
