#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/hardware.py — escolher e trocar as PEÇAS REAIS do drone (motores, hélices,
baterias, frame…) e ver o que muda, sem editar código.

As peças vivem em `models/drone_rpi/componentes.json` (dados do fabricante, com fontes) e as combinações em
`models/drone_rpi/builds.json` (com o build ATIVO). Tudo o resto — massa, inércia, kf/kq, constantes
elétricas, ω_max(V), pairagem, autonomia — é DERIVADO (`lab/drone_rpi/componentes.py`). O treino
(`train.py --planta real`), o site e a validação usam o build ativo; o `train.py` grava o `hardware.json`
(peças + derivados + DR) ao lado de cada política, porque uma política só vale para as peças com que treinou.

    uv run python experiments/09_drone_hover_rl/hardware.py listar              # peças e builds
    uv run python experiments/09_drone_hover_rl/hardware.py mostrar [build]     # números derivados
    uv run python experiments/09_drone_hover_rl/hardware.py comparar            # todos os builds lado a lado
    uv run python experiments/09_drone_hover_rl/hardware.py dimensionar --celula molicel_p45b --s 6   # ponto fixo
    uv run python experiments/09_drone_hover_rl/hardware.py usar <build>        # torna-o ATIVO (+ CoALA + XML)
    uv run python experiments/09_drone_hover_rl/hardware.py montar --nome meu --base <build> \\
        --motor <id> --helice <id> --celula <id> --s 4 --p 2 [--frame <id>] [--esc <id>] [--usar]
    uv run python experiments/09_drone_hover_rl/hardware.py coala              # catálogo → memória CoALA
    uv run python experiments/09_drone_hover_rl/hardware.py xml [build]        # MJCF gerado (inspecionar)

Depois de trocar de peças: `run.py` (validação física) e um treino novo (`train.py --planta real
--out-dir experiments/09_drone_hover_rl/out/real_<nome>`).
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import subprocess
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ)]
from lab import drone_rpi as dr
from lab.drone_rpi import componentes as comp

COALA = _RAIZ / ".agents" / "mujoco-lab-agent-skill" / "scripts" / "coala.py"
XML_ATIVO = comp.PASTA_MODELO / "drone_rpi.xml"
GRUPOS = ("motores", "helices", "celulas", "frames", "esc", "eletronica", "sensores")


def _nome(peca: dict) -> str:
    return f"{peca.get('fabricante', '')} {peca.get('modelo', '')}".strip()


def cmd_listar(_args) -> int:
    cat = comp.carregar_catalogo()
    builds = comp.carregar_builds()
    for g in GRUPOS:
        print(f"\n{g.upper()} ({len(cat.get(g, {}))})")
        for pid, p in cat.get(g, {}).items():
            extra = ""
            if g == "motores":
                extra = f"{p['kv_rpm_v']} KV · {p['massa_g']} g · R {p['r_int_mohm']} mΩ · {len(p.get('tabela', []))} pontos de ensaio"
            elif g == "helices":
                extra = f"{p['diametro_pol']}×{p['passo_pol']}″ · {p['massa_g']} g"
            elif g == "celulas":
                extra = (f"{p['quimica']} · {p['capacidade_mah']} mAh · {p['massa_g']} g · R {p['r_dc_mohm']} mΩ · "
                         f"{p['ciclos_80']} ciclos→80 %")
            elif g == "frames":
                extra = f"{p['wheelbase_mm']} mm · {p['massa_g']} g · hélice ≤ {p['helice_max_pol']}″"
            print(f"  {pid:28s} {_nome(p):40s} {extra}")
    print(f"\nBUILDS (ativo = {builds['ativo']})")
    for nome, b in builds["builds"].items():
        marca = "*" if nome == builds["ativo"] else " "
        print(f" {marca} {nome:28s} {b.get('descricao', '')}")
    return 0


def _linha_resumo(hw) -> dict:
    r = hw.resumo()
    ph = r["pairagem_v_nominal"]
    return {"build": hw.nome, "massa_g": r["massa_total_g"], "t_w": r["t_w_cheia"], "p_w": ph["p_total"],
            "g_w": ph["g_por_w"], "duty": ph["acelerador"], "rpm": ph["rpm"], "aut": r["autonomia_min"],
            "wh": r["bateria"]["wh"], "bat_g": r["bateria"]["massa_g"]}


def cmd_mostrar(args) -> int:
    hw = dr.hardware(args.build)
    r = hw.resumo()
    print(f"build '{hw.nome}' — {hw.descricao}")
    print(f"  motor   {_nome(hw.motor.dados)} · {hw.motor.kv:g} KV · R {1000 * hw.motor.r_int:.0f} mΩ (+ESC "
          f"{1000 * hw.esc.r_on:.0f} mΩ) · I₀ {hw.motor.i0:g} A @ {hw.motor.v_i0:g} V")
    print(f"  hélice  {_nome(hw.helice.dados)} · D {hw.helice.diametro / comp.POL:g}″ · kf {hw.kf:.4e} · "
          f"kq {hw.kq:.4e} (kq/kf {1000 * hw.kq / hw.kf:.1f} mm) · {hw.origem_kf_kq}")
    b = hw.bateria
    print(f"  bateria {b.s}S{b.p}P {_nome(b.celula.dados)} ({b.quimica}) · {b.capacidade_ah:g} Ah · "
          f"{b.energia_wh:.0f} Wh · {1000 * b.massa:.0f} g ({b.densidade_wh_kg:.0f} Wh/kg) · R₀ {1000 * b.r0:.1f} mΩ")
    print(f"  frame   {_nome(hw.frame.dados)} · wheelbase {1000 * hw.frame.wheelbase:.0f} mm · arquitetura "
          f"{hw.arquitetura} · J rotor {hw.j_rotor:.2e} kg·m²")
    print("  massa   " + " + ".join(f"{k} {v:.0f}" for k, v in r["massas_g"].items()) +
          f" = {r['massa_total_g']:.0f} g")
    ph = r["pairagem_v_nominal"]
    print(f"  pairagem a {b.v_nominal:.1f} V: {ph['rpm']:.0f} rpm · duty {100 * ph['duty']:.1f} % · "
          f"{ph['p_motores']:.1f} W motores + {ph['p_eletronica']:.1f} W eletrónica = {ph['p_total']:.1f} W · "
          f"{ph['i_total']:.2f} A · {ph['g_por_w']:.2f} g/W")
    print(f"  T/W com a bateria cheia {r['t_w_cheia']:.2f} · ω_max {r['omega_max_cheia_rpm']:.0f} rpm")
    print(f"  AUTONOMIA de pairagem estimada: {r['autonomia_min']:.1f} min (até {r['autonomia']['v_pouso']:.1f} V "
          f"sob carga; {r['autonomia']['energia_wh']:.1f} Wh)")
    print("  limite de rotação (sob a corrente de pairagem):")
    i_ref = ph["i_total"]
    for soc in (1.0, 0.8, 0.5, 0.2, 0.1):
        v = float(b.ocv(soc)) - i_ref * (b.r0 + hw.r_ligacoes)
        print(f"    SoC {100 * soc:5.0f} %: {v:6.2f} V → ω_max {hw.omega_max(v) / comp.RPM_PARA_RAD:7.0f} rpm · "
              f"T_max {4 * hw.empuxo_max(v) / 9.81:5.2f} kgf (T/W {4 * hw.empuxo_max(v) / hw.peso:.2f})")
    return 0


def cmd_comparar(_args) -> int:
    builds = comp.carregar_builds()
    print(f"{'build':28s} {'massa g':>8s} {'pack g':>7s} {'Wh':>6s} {'P pair W':>9s} {'g/W':>6s} {'acel.':>6s} "
          f"{'T/W':>5s} {'autonomia':>10s}")
    for nome in builds["builds"]:
        try:
            r = _linha_resumo(dr.hardware(nome))
        except (KeyError, ValueError) as e:
            print(f"{nome:28s} [inválido: {e}]")
            continue
        marca = " *" if nome == builds["ativo"] else ""
        print(f"{nome:28s} {r['massa_g']:8.0f} {r['bat_g']:7.0f} {r['wh']:6.0f} {r['p_w']:9.1f} {r['g_w']:6.2f} "
              f"{100 * r['duty']:5.1f}% {r['t_w']:5.2f} {r['aut']:8.1f} min{marca}")
    return 0


def cmd_usar(args) -> int:
    builds = comp.carregar_builds()
    if args.build not in builds["builds"]:
        print(f"erro: build '{args.build}' não existe — disponíveis: {sorted(builds['builds'])}")
        return 2
    dr.hardware(args.build)                       # valida (peças existem, hélice cabe no frame)
    builds["ativo"] = args.build
    comp.gravar_builds(builds)
    hw = dr.hardware(args.build)
    dr.exportar_xml(hw, XML_ATIVO)
    print(f"build ATIVO = '{args.build}' (builds.json) · MJCF regenerado em {XML_ATIVO.relative_to(_RAIZ)}")
    if not args.sem_coala:
        sincronizar_coala(apenas_ativo=True)
    print("próximo: `run.py` (validação) e um treino novo — as políticas antigas valem para as peças antigas")
    return 0


def cmd_montar(args) -> int:
    builds = comp.carregar_builds()
    base = copy.deepcopy(builds["builds"][args.base or builds["ativo"]])
    for chave in ("motor", "helice", "frame", "esc"):
        valor = getattr(args, chave)
        if valor:
            base[chave] = valor
    if args.celula:
        base["bateria"]["celula"] = args.celula
    if args.s:
        base["bateria"]["s"] = int(args.s)
    if args.p:
        base["bateria"]["p"] = int(args.p)
    base["descricao"] = args.descricao or f"montado a partir de {args.base or builds['ativo']}"
    hw = dr.hardware(base)                        # valida e deriva antes de gravar
    builds["builds"][args.nome] = base
    if args.usar:
        builds["ativo"] = args.nome
    comp.gravar_builds(builds)
    print(f"build '{args.nome}' gravado em builds.json" + (" e ATIVO" if args.usar else ""))
    args.build = args.nome
    cmd_mostrar(args)
    if args.usar:
        dr.exportar_xml(hw, XML_ATIVO)
    if not args.sem_coala:
        sincronizar_coala(apenas_ativo=not args.usar)
    return 0


def cmd_dimensionar(args) -> int:
    """O "ponto fixo" do §3 do plano com peças reais: varre N_p (células em paralelo) para uma célula/série e
    mostra massa, T/W, pairagem e autonomia — mais bateria nem sempre é mais voo (cada grama pede empuxo)."""
    builds = comp.carregar_builds()
    nome_base = args.base or builds["ativo"]
    base = copy.deepcopy(builds["builds"][nome_base])
    if args.celula:
        base["bateria"]["celula"] = args.celula
    if args.s:
        base["bateria"]["s"] = int(args.s)
    cel = base["bateria"]["celula"]
    s_ = base["bateria"]["s"]
    extra_por_celula = float(base["bateria"].get("massa_extra_g", 0.0)) / max(1, s_ * base["bateria"]["p"])
    print(f"dimensionar a bateria do build '{nome_base}' com {cel} em {s_}S (ligações ≈ {extra_por_celula:.1f} g/célula):")
    print(f"{'pack':>6s} {'massa g':>8s} {'pack g':>7s} {'Wh':>6s} {'P pair W':>9s} {'g/W':>6s} {'T/W':>5s} {'autonomia':>10s}")
    melhor = None
    for n_p in range(1, int(args.pmax) + 1):
        cfg = copy.deepcopy(base)
        cfg["bateria"]["p"] = n_p
        cfg["bateria"]["massa_extra_g"] = extra_por_celula * s_ * n_p
        cfg["bateria"].pop("dims_mm", None)
        cfg["nome"] = f"{nome_base}_{s_}s{n_p}p"
        try:
            r = _linha_resumo(dr.hardware(cfg))
        except (KeyError, ValueError) as e:
            print(f"{s_}S{n_p}P  [inválido: {e}]")
            continue
        marca = ""
        if r["t_w"] < 2.0:
            marca = "  ⚠ T/W < 2"
        print(f"{s_}S{n_p}P {r['massa_g']:8.0f} {r['bat_g']:7.0f} {r['wh']:6.0f} {r['p_w']:9.1f} {r['g_w']:6.2f} "
              f"{r['t_w']:5.2f} {r['aut']:8.1f} min{marca}")
        if r["t_w"] >= 2.0 and (melhor is None or r["aut"] > melhor[1]):
            melhor = (n_p, r["aut"])
    if melhor:
        print(f"→ maior autonomia com T/W ≥ 2: {s_}S{melhor[0]}P ({melhor[1]:.1f} min). Para o usar: hardware.py montar "
              f"--nome <nome> --base {nome_base} --celula {cel} --s {s_} --p {melhor[0]} --usar")
    return 0


def _coala_add(chave: str, conteudo: str, tags: str, fonte: str) -> bool:
    if not COALA.is_file():
        return False
    r = subprocess.run([sys.executable, str(COALA), "add", "--type", "semantic", "--key", chave, "--content",
                        conteudo, "--origin", "agent", "--source", fonte, "--tags", tags],
                       capture_output=True, text=True, cwd=str(_RAIZ), check=False)
    return r.returncode == 0


def sincronizar_coala(apenas_ativo: bool = False) -> int:
    """Escreve na memória CoALA (chaves estáveis → supersessão) as peças, os builds e o build ativo."""
    if not COALA.is_file():
        print("memória CoALA local ausente (clone sem a skill privada) — nada a sincronizar")
        return 0
    cat = comp.carregar_catalogo()
    builds = comp.carregar_builds()
    n = 0
    fonte_cat = "models/drone_rpi/componentes.json"
    if not apenas_ativo:
        for g in GRUPOS:
            for pid, p in cat.get(g, {}).items():
                dados = {k: v for k, v in p.items() if k != "tabela"}
                if p.get("tabela"):
                    dados["tabela_pontos"] = len(p["tabela"])
                txt = (f"Peça REAL do drone do dono ({g}) '{pid}' — {_nome(p)}: "
                       f"{json.dumps(dados, ensure_ascii=False)}. Usar com experiments/09_drone_hover_rl/"
                       f"hardware.py (montar/usar); fonte de verdade: {fonte_cat}.")
                n += _coala_add(f"drone/peca/{g}/{pid}", txt, f"drone,peca,{g},hardware", fonte_cat)
        for nome, b in builds["builds"].items():
            try:
                r = _linha_resumo(dr.hardware(nome))
                deriv = (f" Derivado: {r['massa_g']:.0f} g, pairagem {r['p_w']:.1f} W ({r['g_w']:.2f} g/W), "
                         f"T/W {r['t_w']:.2f}, autonomia estimada {r['aut']:.1f} min.")
            except (KeyError, ValueError) as e:
                deriv = f" (inválido: {e})"
            txt = f"Build do drone '{nome}': {json.dumps(b, ensure_ascii=False)}.{deriv}"
            n += _coala_add(f"drone/build/{nome}", txt, "drone,build,hardware", "models/drone_rpi/builds.json")
    ativo = builds["ativo"]
    r = _linha_resumo(dr.hardware(ativo))
    txt = (f"Build ATIVO do drone do dono = '{ativo}' ({builds['builds'][ativo].get('descricao', '')}). "
           f"{r['massa_g']:.0f} g, pairagem {r['p_w']:.1f} W ({r['g_w']:.2f} g/W), T/W {r['t_w']:.2f}, autonomia "
           f"estimada {r['aut']:.1f} min. Trocar: hardware.py usar <build>; o treino grava hardware.json ao lado "
           "de cada política (os dados das peças com que treinou).")
    n += _coala_add("drone/build-ativo", txt, "drone,build,hardware,ativo", "models/drone_rpi/builds.json")
    print(f"CoALA: {n} registos escritos/supersedidos (chaves drone/peca/*, drone/build/*, drone/build-ativo)")
    return 0


def cmd_coala(_args) -> int:
    return sincronizar_coala(apenas_ativo=False)


def cmd_xml(args) -> int:
    hw = dr.hardware(args.build)
    destino = Path(args.saida) if args.saida else XML_ATIVO
    dr.exportar_xml(hw, destino)
    print(f"MJCF do build '{hw.nome}' em {destino} — inspecione com "
          f"`.venv/bin/python .agents/mujoco-lab-agent-skill/scripts/inspect_model.py {destino}`")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Peças reais do drone: listar, comparar, trocar (builds) e sincronizar "
                                            "com a memória CoALA.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("listar").set_defaults(f=cmd_listar)
    m = sub.add_parser("mostrar")
    m.add_argument("build", nargs="?", default=None)
    m.set_defaults(f=cmd_mostrar)
    sub.add_parser("comparar").set_defaults(f=cmd_comparar)
    u = sub.add_parser("usar")
    u.add_argument("build")
    u.add_argument("--sem-coala", action="store_true")
    u.set_defaults(f=cmd_usar)
    mo = sub.add_parser("montar")
    mo.add_argument("--nome", required=True)
    mo.add_argument("--base", default=None, help="build de partida (por omissão o ativo)")
    for chave in ("motor", "helice", "frame", "esc", "celula", "descricao"):
        mo.add_argument(f"--{chave}", default=None)
    mo.add_argument("--s", type=int, default=None, help="células em série")
    mo.add_argument("--p", type=int, default=None, help="células em paralelo")
    mo.add_argument("--usar", action="store_true", help="torna o build novo o ATIVO")
    mo.add_argument("--sem-coala", action="store_true")
    mo.set_defaults(f=cmd_montar)
    di = sub.add_parser("dimensionar", help="varre células em paralelo (o ponto fixo bateria ↔ autonomia)")
    di.add_argument("--base", default=None)
    di.add_argument("--celula", default=None)
    di.add_argument("--s", type=int, default=None)
    di.add_argument("--pmax", type=int, default=5)
    di.set_defaults(f=cmd_dimensionar)
    sub.add_parser("coala").set_defaults(f=cmd_coala)
    x = sub.add_parser("xml")
    x.add_argument("build", nargs="?", default=None)
    x.add_argument("--saida", default=None)
    x.set_defaults(f=cmd_xml)
    args = p.parse_args(argv)
    try:
        return int(args.f(args) or 0)
    except (KeyError, ValueError) as e:
        print(f"erro: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main", "math", "sincronizar_coala"]
