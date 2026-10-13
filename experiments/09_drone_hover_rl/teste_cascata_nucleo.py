"""experiments/09_drone_hover_rl/teste_cascata_nucleo.py — PROVA da atividade B: a CASCATA CLÁSSICA + o ESTIMADOR CLÁSSICO + o OLHAR
no NÚCLEO DE FIRMWARE C++ (`firmware/nucleo/`), em SITL fechado com o MuJoCo, a correr no ALVO Cortex-M4/M7.

A B0 (`controlo_classico.py`) é a referência em Python float64; a atividade C deu o detetor/IBVS em C++; aqui o núcleo passou a ter
`estimador_classico.hpp` + `cascata.hpp` ligados em `resolver_modo()` (modos CTBR · VELOCIDADE · YAW_ALVO · OLHAR). O que se prova:

  §0 REGRAS DE FIRMWARE no código novo (sem double/new/malloc/std::, só <stdint.h>/<math.h>) e NENHUMA constante de projeto escrita à
     mão no `cascata.hpp`/`estimador_classico.hpp` (todas vêm da Config; o auditor TEM DENTES); paridade de nomes GanhosCascata ↔ ConfigCascata;
  §1 COMPILAÇÃO no host (g++/clang++, -O0…-O3, C++11…20, cabeçalhos auto-suficientes) e ESTRESSE ASan+UBSan da interface 2 (3 M de passos
     hostis: NaN/inf/1e30, relógio a voltar, câmara absurda, mudanças de modo) com invariantes;
  §2 COMPILAÇÃO CRUZADA do núcleo COMPLETO (+ detetor) para Cortex-M4 e M7: tamanhos, RAM da instância, símbolos (só sinf/cosf/atan2f/sqrtf +
     mem*), sem double/heap/__cxa;
  §3 LAYOUT + CONFIG: structs aninhadas de ctypes ≡ sizeof do C++; `config_de_hardware` ≡ `ganhos_de_hardware`; compensação de tensão ≡
     `DroneRealEnv.acelerador_pairagem`; export `constexpr` bit a bit; Configs inválidas recusadas; Config v1 ⇒ comportamento v1;
  §4 EQUIVALÊNCIA (golden vectors do Python → C++): ≥ 2000 decisões de um voo GRAVADO (incl. saturação de yaw) e 30 000 passos do
     estimador (calibração no chão + portão do acelerómetro ativo), |Δ| ≤ 1e-4; duas sementes + DR; `passo` ≡ `planear`+`atuar`;
  §5 MALHA FECHADA com o MuJoCo: C++ vs Python (≤ 5 %), modos VELOCIDADE/YAW_ALVO, saturação de yaw, OLHAR com frames mono RENDERIZADOS + detetor C++
     (116 ms e 21 ms), perda/reaquisição e a «parede» da autoridade de yaw a 0,8 m/s;
  §6 NO ALVO: o MESMO código em QEMU Cortex-M4/M7 bit a bit ≡ host (voo gravado + deteções), comparador com dentes, libm própria ≤ 2 ULP,
     instruções EXATAS por passo (traço do QEMU) e ciclos ESTIMADOS (llvm-mca M7; tabela M4F) → µs @480/@240 MHz e % do orçamento de 2 ms;
  §7 MUTAÇÕES da fonte C++ (≥ 5): cada uma compilada de verdade e APANHADA pelo detetor certo.

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_cascata_nucleo.py [--rapido] [--secoes 0,2,4]

Exit 0 = tudo verde; 1 = alguma checagem falhou (ou falta uma ferramenta: falha ALTO, nunca salta).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import ctypes
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

import avaliar_classico as ac
import avaliar_nucleo as an
import controlo_classico as cc
import numpy as np
import qemu_alvo as qa
import sitl
import teste_nucleo as tn
from env import VOO_Z_MIN

FIRMWARE_DIR, NUCLEO_DIR, CROSS_DIR = sitl.FIRMWARE_DIR, sitl.NUCLEO_DIR, tn.CROSS_DIR
QEMU_DIR = FIRMWARE_DIR / "cross" / "qemu"
ESTRESSE_CASCATA = FIRMWARE_DIR / "teste" / "estresse_cascata.cpp"
PASSOS_ESTRESSE = 3_000_000
# --- tolerâncias da equivalência (float32 vs float64; medido ~10× abaixo) ---------------------------------------------------------
TOL_CASCATA = 1e-4            # |Δ| do coletivo (T/(m·g)) e das taxas p, q, r (rad/s): o critério do enunciado (medido ≲ 5e-5)
TOL_DIAG = {"a_des": 2e-3, "n_des": 1e-4, "e_tilt": 1e-4, "gama": 1e-4, "v_h": 1e-5, "v_o": 1e-5, "v_sp_h": 1e-5, "p_sp": 1e-5,
            "z_sp": 1e-4, "psi_sp": 1e-4, "r_ref": 1e-4, "i_vel": 1e-5, "i_z": 2e-3, "pert": 2e-3}
# campos da ConfigCascata que NÃO são da cascata: a geometria/tempos do sensor de fluxo, consumidos pelo estimador clássico (interface 3)
CAMPOS_DO_ESTIMADOR = ("braco_fluxo", "atraso_fluxo")
TOL_EST = {"roll": 2e-5, "pitch": 2e-5, "psi": 5e-5, "h": 1e-4, "vz": 1e-4, "vx": 1e-5, "vy": 1e-5, "x": 2e-4, "y": 2e-4}
TOL_REL_MALHA = 0.05          # ≤ 5 % nas métricas da malha fechada C++ vs Python (o enunciado)
CAMPOS_EST = ("roll", "pitch", "psi", "h", "vz", "vx", "vy", "x", "y")
MODOS_PY = {"velocidade": sitl.MODO_VELOCIDADE, "yaw_alvo": sitl.MODO_YAW_ALVO}


# ============================================================================================ §0 regras
LITERAIS_PERMITIDOS = {"0.0f", "1.0f", "2.0f", "3.0f", "0.5f",                     # estrutura das fórmulas (raiz quadrada, polos triplos…)
                       "1e-3f", "1e-6f", "1e-9f", "1.0e6f",                         # guardas numéricas (nomeadas em cascata_detalhe)
                       "6.28318530717958647692f"}                                   # 2π
RE_LITERAL = re.compile(r"(?<![\w.])(?:\d+\.\d*|\.\d+|\d+(?:\.\d*)?[eE][-+]?\d+)[fF]?(?![\w.])")


def literais_de_projeto(texto: str) -> list[str]:
    """Literais de ponto flutuante FORA da lista de estruturais/guardas — ganhos, limites e constantes de tempo escritos à mão."""
    limpo = tn._sem_comentarios_e_strings(texto)
    return sorted({m.group(0) for m in RE_LITERAL.finditer(limpo)} - LITERAIS_PERMITIDOS)


def campos_struct(nome: str, ficheiro: Path) -> list[str]:
    est = sitl.estruturas_do_header(ficheiro)
    return [n for n, _ in est[nome]._fields_]


def secao_regras(c: tn.Checagens) -> None:
    ficheiros = sorted(NUCLEO_DIR.glob("*.[ch]pp")) + [CROSS_DIR / "verifica_nucleo.cpp", CROSS_DIR / "verifica_hal.cpp"]
    ruins = {}
    for f in ficheiros:
        v = tn.auditar_texto(f.read_text(encoding="utf-8"), permitir_virtual=f.name == "verifica_hal.cpp")
        if v:
            ruins[f.name] = v[:3]
    c.ok("[§0] TODO o núcleo (incl. cascata.hpp, estimador_classico.hpp, nucleo.cpp) + HAL + verifica_nucleo cumprem as regras de firmware "
         "(sem double/new/malloc/std::/exceções/RTTI, só <stdint.h>/<math.h>, literais float)", not ruins,
         f"{len(ficheiros)} ficheiros auditados" if not ruins else str(ruins))
    por_ficheiro = {f: literais_de_projeto((NUCLEO_DIR / f).read_text(encoding="utf-8")) for f in ("cascata.hpp", "estimador_classico.hpp")}
    c.ok("[§0] NENHUMA constante de projeto escrita à mão em cascata.hpp / estimador_classico.hpp: os únicos literais são estruturais "
         f"({', '.join(sorted(LITERAIS_PERMITIDOS - {'6.28318530717958647692f'}))}, 2π) — ganhos, limites e tempos vêm da Config",
         not any(por_ficheiro.values()), str(por_ficheiro) if any(por_ficheiro.values()) else "")
    mudo = [t for t in ("float f(float x) { return x * 0.8f; }", "const float k_att = 3.37f;", "float g = 9.81f;",
                        "float lim = 1.5f;") if not literais_de_projeto(t)]
    c.ok("[§0] o auditor de constantes TEM DENTES: apanha `0.8f`, `3.37f`, `9.81f` e `1.5f` injetados e não dá falsos positivos "
         "(0.0f, 1.0f, 0.5f, 1e-3f em comentários e código)", not mudo and not literais_de_projeto("// 3.37f\nfloat x = 0.5f + 1e-3f;"),
         f"não apanhou: {mudo}" if mudo else "")
    # paridade de nomes: todo o `gn.<campo>` que a CascataClassica.passo usa existe na ConfigCascata do C++
    texto = Path(cc.__file__).read_text(encoding="utf-8")
    corpo = texto[texto.index("class CascataClassica:"):texto.index("class EstimadorClassico")]
    usados = set(re.findall(r"\bgn\.(\w+)", corpo))
    cpp = set(campos_struct("ConfigCascata", NUCLEO_DIR / "config.hpp"))
    renomeados = {"ref_posicao": "ref_posicao_trava"}
    faltam = sorted(u for u in usados if renomeados.get(u, u) not in cpp)
    mortos = sorted(cpp - {renomeados.get(u, u) for u in usados} - {"decimacao", *sitl.LITERAIS_CASCATA, *CAMPOS_DO_ESTIMADOR})
    c.ok("[§0] paridade GanhosCascata ↔ ConfigCascata: todos os `gn.<campo>` do `CascataClassica.passo` existem na Config C++ "
         f"({len(usados)} campos) e não há campos da Config sem uso no protótipo (fora a decimação, os literais espelhados e os do sensor de fluxo)",
         not faltam and not mortos, f"faltam no C++: {faltam} · sem uso no Python: {mortos}" if (faltam or mortos) else f"{len(cpp)} campos na ConfigCascata")
    # os campos do sensor de fluxo (interface 3) não são da cascata: quem os usa é o estimador clássico — nos DOIS lados, e a cascata não
    est_cpp = tn._sem_comentarios_e_strings((NUCLEO_DIR / "estimador_classico.hpp").read_text(encoding="utf-8"))
    casc_cpp = tn._sem_comentarios_e_strings((NUCLEO_DIR / "cascata.hpp").read_text(encoding="utf-8"))
    est_py = texto[texto.index("class EstimadorClassico"):]
    usa = {k: (f"c.cascata.{k}" in est_cpp, k in est_py, re.search(rf"\b{k}\b", casc_cpp) is None, hasattr(cc.GanhosCascata(), k)) for k in CAMPOS_DO_ESTIMADOR}
    c.ok(f"[§0] os campos do SENSOR DE FLUXO da ConfigCascata ({', '.join(CAMPOS_DO_ESTIMADOR)}) são consumidos pelo estimador clássico (C++: `c.cascata.<campo>`; "
         "Python: `EstimadorClassico.configurar_fluxo`), existem em `GanhosCascata` e a cascata não lhes toca", all(all(v) for v in usa.values()), str(usa))


# ============================================================================================ §1 host
def secao_host(c: tn.Checagens, tmp: Path, cfg_bin: Path) -> None:
    gpp, clangpp = tn._ferramenta("g++"), tn._ferramenta("clang++")
    fontes = [NUCLEO_DIR / "nucleo.cpp", NUCLEO_DIR / "capi.cpp", CROSS_DIR / "verifica_nucleo.cpp"]
    jobs = [(cxx, f, opt) for cxx in (gpp, clangpp) for opt in ("-O0", "-Os", "-O2", "-O3") for f in fontes]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(lambda j: tn._compilar_host(j[0], j[1], tmp / f"h_{abs(hash(j))}.o", j[2],
                                                      tn.FLAGS_EXTRA if j[0] == gpp else ()), jobs))
    ruins = [(Path(j[0]).name, j[1].name, j[2], r.stderr.strip().splitlines()[:1]) for j, r in zip(jobs, res, strict=True) if r.returncode != 0]
    c.ok("[§1] o núcleo completo, o capi e o verifica_nucleo compilam no host com -Wall -Wextra -Wdouble-promotion -Werror (g++ e clang++, "
         "-O0/-Os/-O2/-O3; g++ também -Wshadow -Wconversion…)", not ruins, f"{len(jobs)} compilações" if not ruins else str(ruins))
    padroes = ("c++11", "c++14", "gnu++14", "c++17", "c++20")
    jobs = [(cxx, std, f) for cxx in (gpp, clangpp) for std in padroes for f in fontes]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(lambda j: tn._correr([j[0], f"-std={j[1]}", "-O2", "-fno-exceptions", "-fno-rtti", *tn.FLAGS_AVISOS, "-I", FIRMWARE_DIR,
                                                "-c", j[2], "-o", tmp / f"s_{abs(hash(j))}.o"]), jobs))
    ruins = [(Path(j[0]).name, j[1], j[2].name) for j, r in zip(jobs, res, strict=True) if r.returncode != 0]
    c.ok(f"[§1] o mesmo código compila em {', '.join(padroes)} (g++ e clang++; o core Arduino mbed usa gnu++14)", not ruins,
         f"{len(jobs)} compilações" if not ruins else str(ruins))
    mal = []
    for h in sorted(NUCLEO_DIR.glob("*.hpp")):
        tu = tmp / f"auto_{h.name}.cpp"
        tu.write_text(f'#include "{h.resolve()}"\n', encoding="utf-8")
        r = tn._correr([gpp, "-std=c++17", "-fsyntax-only", "-fno-exceptions", "-fno-rtti", *tn.FLAGS_AVISOS, "-I", FIRMWARE_DIR, tu])
        if r.returncode != 0:
            mal.append((h.name, r.stderr.strip().splitlines()[:1]))
    c.ok("[§1] cada cabeçalho do núcleo (incl. cascata.hpp e estimador_classico.hpp) é auto-suficiente", not mal, str(mal) if mal else "")
    for cxx in (gpp, clangpp):
        exe = tmp / f"estresse_c_{Path(cxx).name}"
        rc = tn._correr([cxx, *tn.FLAGS_SANITIZERS, "-I", FIRMWARE_DIR, ESTRESSE_CASCATA, NUCLEO_DIR / "nucleo.cpp", "-o", exe])
        if rc.returncode != 0:
            c.ok(f"[§1] estresse da interface 2 ({Path(cxx).name}) compila", False, rc.stderr[:300])
            continue
        r = tn._correr([exe, cfg_bin, str(PASSOS_ESTRESSE)])
        m = re.search(r"violações (\d+) · falhas numéricas sinalizadas (\d+) · passos armados (\d+) · passos com a cascata a mandar (\d+) · "
                      r"em OLHAR (\d+)", r.stdout)
        v, fa, arm, casc, olh = (int(x) for x in m.groups()) if m else (-1, 0, 0, 0, 0)
        c.ok(f"[§1] ESTRESSE ASan+UBSan da INTERFACE 2 ({Path(cxx).name}): {PASSOS_ESTRESSE:,} passos hostis (NaN/inf/±1e30, dt inválido, relógio "
             "a saltar e a VOLTAR, câmara absurda, mudanças de modo, armar/reiniciar/calibrar_chao/travar, passo partido) — sem UB/OOB e com os "
             "invariantes (motores ∈ [0,1], taxas dentro dos tetos, tudo finito)", r.returncode == 0 and v == 0 and casc > 0 and olh > 0 and fa > 0,
             f"violações {v} · falhas sinalizadas {fa} · armados {arm} · cascata a mandar {casc} · OLHAR {olh} {r.stderr.strip()[:120]}")


# ============================================================================================ §2 cruzada
def secao_cruzada(c: tn.Checagens, tmp: Path) -> dict:
    clang = tn._ferramenta("clang++", "clang")
    llvm_size, llvm_nm, llvm_objdump = (tn._ferramenta(n) for n in ("llvm-size", "llvm-nm", "llvm-objdump"))
    fontes = {"nucleo": NUCLEO_DIR / "nucleo.cpp", "capi": NUCLEO_DIR / "capi.cpp", "completo": CROSS_DIR / "verifica_nucleo.cpp",
              "hal": CROSS_DIR / "verifica_hal.cpp"}
    info: dict = {}
    for placa, cpu in tn.CPUS.items():
        objs, falhas = {}, []
        for nome, fonte in fontes.items():
            o = tmp / f"x_{nome}_{cpu[0]}.o"
            r = tn.compilar_cruzado(clang, cpu, fonte, o)
            if r.returncode != 0:
                falhas.append((nome, r.stderr.strip().splitlines()[:2]))
            objs[nome] = o
        c.ok(f"[§2] {placa}: núcleo completo + capi + cadeia detetor→núcleo + HAL compilam com clang --target=thumbv7em-none-eabihf -ffreestanding "
             f"-fno-exceptions -fno-rtti -Os -Wall -Wextra -Wdouble-promotion -Werror -mcpu={cpu[0]} -mfpu={cpu[1]}", not falhas, str(falhas) if falhas else "")
        if falhas:
            continue
        m = tn.medir_objeto(llvm_size, objs["nucleo"])
        o2 = tmp / f"x_nucleo_O2_{cpu[0]}.o"
        tn._correr([clang, *[f for f in tn.FLAGS_CROSS if f != "-Os"], "-O2", f"-mcpu={cpu[0]}", f"-mfpu={cpu[1]}", "-I", FIRMWARE_DIR,
                    "-isystem", CROSS_DIR, "-c", fontes["nucleo"], "-o", o2])
        m2 = tn.medir_objeto(llvm_size, o2)
        inst = tmp / f"inst_{cpu[0]}.cpp"
        inst.write_text('#include "nucleo/nucleo.hpp"\nnucleo::Nucleo g_nucleo;\n', encoding="utf-8")
        oi = tmp / f"inst_{cpu[0]}.o"
        tn.compilar_cruzado(clang, cpu, inst, oi)
        mi = tn.medir_objeto(llvm_size, oi)
        info[cpu[0]] = {"os": m, "o2": m2, "ram_nucleo": mi["bss"], "data_nucleo": mi["data"]}
        c.ok(f"[§2] {placa}: nucleo.o (estimador clássico + cascata + IBVS + taxa, -Os) = text {m['text']} B · data {m['data']} B · bss {m['bss']} B "
             f"(-O2: text {m2['text']} B); uma instância GLOBAL `nucleo::Nucleo` = {mi['bss']} B em .bss, .data {mi['data']} B (sem imagem em flash)",
             m["text"] > 0 and m["data"] == 0 and m["bss"] == 0 and mi["bss"] > 0 and mi["data"] == 0 and mi["text"] == 0,
             "sem variáveis globais: todo o estado vive na instância do chamador")
        # a cadeia completa (detetor → Camera → Nucleo) = verifica_nucleo.o + nucleo.o numa ligação relocável (os métodos do Nucleo vivem em nucleo.cpp)
        junto = tmp / f"completo_{cpu[0]}.o"
        rl = tn._correr([tn._ferramenta("ld.lld"), "-r", objs["completo"], objs["nucleo"], "-o", junto])
        if rl.returncode != 0:
            c.ok(f"[§2] {placa}: ligação relocável nucleo.o + verifica_nucleo.o", False, rl.stderr[:200])
            continue
        mc = tn.medir_objeto(llvm_size, junto)
        info[cpu[0]]["completo"] = mc
        v = tn.verificar_objeto(llvm_nm, llvm_objdump, objs["nucleo"], firmware=True)
        vc = tn.verificar_objeto(llvm_nm, llvm_objdump, junto, firmware=True)
        c.ok(f"[§2] {placa}: símbolos indefinidos do núcleo e da cadeia completa = só libm {sorted(tn.LIBM_PERMITIDA)} + mem* — sem "
             "malloc/new/__cxa_*/typeinfo/vtables/atexit/double (llvm-nm) e sem secções de construtores/exceções",
             not v["proibidos"] and not v["estranhos"] and not v["secoes_ruins"] and not vc["proibidos"] and not vc["estranhos"] and not vc["secoes_ruins"],
             f"indefinidos = {vc['indefinidos']} · cadeia completa (núcleo+detetor, ligados): text {mc['text']} B · data {mc['data']} B · bss {mc['bss']} B")
        c.ok(f"[§2] {placa}: nenhuma instrução de double (0 × `.f64` no disassembly) no núcleo nem na cadeia completa", v["f64"] == 0 and vc["f64"] == 0,
             f"{v['f64']} / {vc['f64']} ocorrências")
    return info


# ============================================================================================ gravação do protótipo Python
class GravadorEst:
    """Embrulha o `EstimadorClassico` e grava as entradas/saídas de cada passo de 500 Hz (+ eventos de calibração)."""

    def __init__(self, inner):
        self.i, self.log = inner, []

    def __getattr__(self, n):
        return getattr(self.i, n)

    def _est(self):
        i = self.i
        return (i.roll, i.pitch, i.psi, i.h, i.vz, i.vx, i.vy, i.x, i.y)

    def reiniciar(self, acc=(0, 0, 9.81), tof_d=0.0, tof_ok=False):
        self.i.reiniciar(acc, tof_d, tof_ok)
        self.log.append(("reiniciar", (tuple(map(float, acc)), float(tof_d), bool(tof_ok))))

    def calibrar(self, ativo):
        self.i.calibrar(ativo)
        self.log.append(("cal", bool(ativo), self._est()))

    def passo(self, giro, acc, tof_d, tof_ok, n_tof, fluxo, fluxo_ok, n_fluxo):
        self.i.passo(giro, acc, tof_d, tof_ok, n_tof, fluxo, fluxo_ok, n_fluxo)
        self.log.append(("passo", (tuple(map(float, giro)), tuple(map(float, acc)), float(tof_d), bool(tof_ok), int(n_tof),
                                   tuple(map(float, fluxo)), bool(fluxo_ok), int(n_fluxo)), self._est(), float(self.i._a_h)))


def cenario(t: float) -> dict:
    """Manobras em função do tempo (referencial do rumo): hover, W, A, Q/E, degrau de rumo de 90°, taxa de yaw ACIMA do teto (satura),
    arco, diagonal, rumo −160°, velocidade+taxa mistas — exercita o conformador de yaw, a prioridade de inclinação e o portão."""
    if t < 4:
        return {}
    if t < 7:
        return {"vx": 1.0}
    if t < 10:
        return {"vy": 1.0}
    if t < 12:
        return {"vz": 0.7}
    if t < 14:
        return {"vz": -0.7}
    if t < 15:
        return {}
    if t < 25:
        return {"modo": "yaw_alvo", "yaw": math.pi / 2}
    if t < 28:
        return {"yaw_taxa": 1.2}
    if t < 31:
        return {}
    if t < 38:
        return {"vx": 1.0, "yaw_taxa": 0.5}
    if t < 41:
        return {"vx": -0.7, "vy": -0.7}
    if t < 44:
        return {"modo": "yaw_alvo", "yaw": -2.8}
    if t < 50:
        return {"vx": 0.8, "vy": 0.5, "vz": 0.3, "yaw_taxa": -0.4}
    return {}


def gravar_python(dados: dict, u_yaw: float, seed: int, T: float = 60.0, dr: bool = False) -> dict:
    """O protótipo B0 a voar (estimador melhorado + cascata, como o `avaliar_classico`) com o `cenario`, gravando o que ele vê e decide."""
    env = ac.criar_env(dados, dr=dr, episodio_s=T)
    gest = GravadorEst(cc.EstimadorClassico(env.dt))
    env.estimador = gest
    env.reset(seed=seed)
    gn = cc.ganhos_de_hardware(env, u_yaw_por_taxa=u_yaw, altura_min=VOO_Z_MIN - ac.deslocamento_sensor_cm(env))
    casc = cc.CascataClassica(gn)
    gest.i.configurar_fluxo(gn.atraso_fluxo, gn.braco_fluxo)      # como o `ControladorCascata` (e a Config do C++: campos da cascata)
    ac.calibrar_no_chao(env, 1.0)
    z_alvo = env.alvo_z - ac.deslocamento_sensor_cm(env)
    arm_est = gest._est()
    casc.armar(True, env.estimador, z_alvo=z_alvo)
    rec = []
    for k in range(round(T / env.dt_decisao)):
        t = k * env.dt_decisao
        cmd = dict(cenario(t))
        est9 = gest._est()
        giro = tuple(map(float, env.planta.imu.giro.medicao))
        co, tx = casc.passo(env.estimador, giro, cmd, env.dt_decisao)
        rec.append((t, est9, giro, cmd, env.dt_decisao, float(co), tuple(map(float, tx)), dict(casc.dados)))
        _o, _r, term, _tr, _i = env.step(np.asarray(cc.cmd_para_acao(co, tx), dtype=np.float32))
        if term:
            break
    z = np.array([r_[1][3] for r_ in rec])
    return {"rec": rec, "log_est": gest.log, "gn": gn, "z_alvo": z_alvo, "arm_est": arm_est, "seed": seed, "dr": dr, "env_hw": (env.hw, env.model, env.dt),
            "z_min": float(z.min()), "decisoes": len(rec)}


def config_de(g: dict, bib, **kw):
    hw, model, dt = g["env_hw"]
    return bib.Config.from_buffer_copy(sitl.config_de_hardware(hw, model, dt, ganhos=g["gn"], estimador_classico=True, bib=bib, **kw))


def comparar_cascata(bib, cfg, g: dict, n: int | None = None) -> dict:
    """Repete no C++ as decisões gravadas e devolve os máx |Δ| do coletivo/taxas, do diagnóstico e as contagens de flags."""
    lib = bib.lib
    cid = lib.cascata_criar()
    cfgc = bib.ConfigCascata.from_buffer_copy(cfg.cascata)
    lib.cascata_iniciar(cid, ctypes.byref(cfgc))
    lib.cascata_armar(cid, 1)
    est, cmd, diag = bib.Saida(), bib.Comando(), bib.Saida()
    for k, v in zip(CAMPOS_EST, g["arm_est"], strict=True):
        setattr(est, k, v)
    lib.cascata_travar(cid, ctypes.byref(est), 1, g["z_alvo"])
    res, flags, giro = (ctypes.c_float * 4)(), ctypes.c_int32(), (ctypes.c_float * 3)()
    dmax, dd, fl = np.zeros(4), {k: 0.0 for k in TOL_DIAG}, {"sat_yaw": 0, "sat_incl": 0, "sat_rp": 0, "sat_col": 0}
    por_passo = []
    for r in g["rec"][:n]:
        _t, est9, giro3, cm, dt, c_py, tx_py, dpy = r
        for kk, vv in zip(CAMPOS_EST, est9, strict=True):
            setattr(est, kk, vv)
        for i in range(3):
            giro[i] = giro3[i]
        cmd.modo = MODOS_PY[cm.get("modo", "velocidade")]
        cmd.vx, cmd.vy, cmd.vz = cm.get("vx", 0.0), cm.get("vy", 0.0), cm.get("vz", 0.0)
        cmd.yaw_taxa, cmd.yaw, cmd.tem_z_alvo, cmd.z_alvo = cm.get("yaw_taxa", 0.0), cm.get("yaw", 0.0), 0, 0.0
        lib.cascata_passo(cid, ctypes.byref(cfgc), ctypes.byref(est), giro, ctypes.byref(cmd), dt, res, ctypes.byref(flags), ctypes.byref(diag))
        d = np.array([abs(res[0] - c_py)] + [abs(res[1 + i] - tx_py[i]) for i in range(3)])
        dmax = np.maximum(dmax, d)
        por_passo.append(float(d.max()))
        fl["sat_yaw"] += bool(flags.value & sitl.FLAG_SAT_YAW_TAXA)
        fl["sat_incl"] += bool(flags.value & sitl.FLAG_SAT_INCLINACAO)
        fl["sat_rp"] += bool(flags.value & sitl.FLAG_SAT_TAXA_RP)
        fl["sat_col"] += bool(flags.value & sitl.FLAG_SAT_COLETIVO)
        for cn in TOL_DIAG:
            a = np.atleast_1d(np.array(getattr(diag, cn), dtype=float))
            dd[cn] = max(dd[cn], float(np.max(np.abs(a - np.atleast_1d(np.array(dpy[cn], dtype=float))))))
    lib.cascata_liberar(cid)
    return {"max": dmax, "diag": dd, "flags": fl, "por_passo": np.array(por_passo), "n": len(por_passo)}


def comparar_cascata_sintetico(bib, cfg, gn, n: int = 4000, semente: int = 7, janela: int = 50) -> dict:
    """A mesma comparação com entradas SINTÉTICAS violentas (inclinações de ±45°, erros de velocidade de ±4 m/s, vz medida de ±4 m/s, taxas de yaw
    e comandos muito acima dos limites): obriga a cascata a saturar a inclinação, as taxas p/q, o coletivo e o yaw — ramos que o voo gravado (suave)
    não toca. As entradas são as mesmas nos dois lados; o Python é o protótipo float64. A altura fica longe do piso/teto: aí a referência fica
    «colada» ao limite e um ramo `<` decidido por 1e-9 diverge entre float32 e float64 sem ser um erro do port. Pelo mesmo motivo (o teste «coletivo ≥
    máx − 1e-9» do anti-windup vertical é inoperante abaixo de 1,2e-7 em float32) as duas cascatas REARMAM-SE a cada `janela` decisões: um ramo que vira
    num passo deixa um integrador com UM incremento de diferença, que sem rearmar ficaria para sempre."""
    rng = np.random.default_rng(semente)
    lib = bib.lib
    cid = lib.cascata_criar()
    cfgc = bib.ConfigCascata.from_buffer_copy(cfg.cascata)
    lib.cascata_iniciar(cid, ctypes.byref(cfgc))
    lib.cascata_armar(cid, 1)
    est, cmd, diag = bib.Saida(), bib.Comando(), bib.Saida()
    py = cc.CascataClassica(gn)
    e0 = dict(zip(CAMPOS_EST, (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0), strict=True))
    py.armar(True, e0, z_alvo=None)
    for k, v in e0.items():
        setattr(est, k, v)
    lib.cascata_travar(cid, ctypes.byref(est), 0, 0.0)
    res, flags, giro = (ctypes.c_float * 4)(), ctypes.c_int32(), (ctypes.c_float * 3)()
    dmax, fl, por_passo = np.zeros(4), {"sat_yaw": 0, "sat_incl": 0, "sat_rp": 0, "sat_col": 0}, []
    h, psi, e = 1.0, 0.0, dict(e0)
    for i in range(n):
        if i > 0 and i % janela == 0:                       # rearma as duas (ver o docstring)
            py.armar(False)
            lib.cascata_armar(cid, 0)
            py.armar(True, e, z_alvo=None)
            lib.cascata_armar(cid, 1)
            for kk, vv in e.items():
                setattr(est, kk, vv)
            lib.cascata_travar(cid, ctypes.byref(est), 0, 0.0)
        psi = (psi + rng.normal(0, 0.1) + math.pi) % (2 * math.pi) - math.pi
        h = float(np.clip(h + rng.normal(0, 0.1), 0.7, 1.7))      # longe dos pisos/tetos de altitude: ali a referência fica «colada» e o
        e = {"roll": float(rng.uniform(-0.8, 0.8)), "pitch": float(rng.uniform(-0.8, 0.8)), "psi": psi, "h": h, "vz": float(rng.normal(0, 2.0)),
             "vx": float(rng.normal(0, 2.0)), "vy": float(rng.normal(0, 2.0)), "x": float(rng.normal(0, 2.0)), "y": float(rng.normal(0, 2.0))}
        e = {k: float(np.float32(v)) for k, v in e.items()}
        gi = [float(np.float32(x)) for x in rng.normal(0, 0.6, 3)]
        yaw_aut = i % 5 == 0
        cm = {"vx": float(rng.uniform(-2, 2)), "vy": float(rng.uniform(-2, 2)), "vz": float(rng.uniform(-0.3, 0.3)),
              "yaw_taxa": float(rng.uniform(-2.5, 2.5)), "modo": "yaw_alvo" if yaw_aut else "velocidade", "yaw": float(rng.uniform(-6, 6))}
        cm = {k: (float(np.float32(v)) if isinstance(v, float) else v) for k, v in cm.items()}
        c_py, tx_py = py.passo(e, gi, cm, 0.02)
        for kk, vv in e.items():
            setattr(est, kk, vv)
        for j in range(3):
            giro[j] = gi[j]
        cmd.modo = MODOS_PY[cm["modo"]]
        cmd.vx, cmd.vy, cmd.vz, cmd.yaw_taxa, cmd.yaw, cmd.tem_z_alvo, cmd.z_alvo = cm["vx"], cm["vy"], cm["vz"], cm["yaw_taxa"], cm["yaw"], 0, 0.0
        lib.cascata_passo(cid, ctypes.byref(cfgc), ctypes.byref(est), giro, ctypes.byref(cmd), 0.02, res, ctypes.byref(flags), ctypes.byref(diag))
        d = np.array([abs(res[0] - c_py)] + [abs(res[1 + j] - tx_py[j]) for j in range(3)])
        dmax = np.maximum(dmax, d)
        por_passo.append(float(d.max()))
        fl["sat_yaw"] += bool(flags.value & sitl.FLAG_SAT_YAW_TAXA)
        fl["sat_incl"] += bool(flags.value & sitl.FLAG_SAT_INCLINACAO)
        fl["sat_rp"] += bool(flags.value & sitl.FLAG_SAT_TAXA_RP)
        fl["sat_col"] += bool(flags.value & sitl.FLAG_SAT_COLETIVO)
    lib.cascata_liberar(cid)
    return {"max": dmax, "flags": fl, "n": n, "p999": float(np.percentile(por_passo, 99.9)), "n_acima": int((np.array(por_passo) > 1e-3).sum())}


def comparar_estimador(bib, cfg, g: dict, n: int | None = None) -> dict:
    """Repete no C++ o fluxo de sensores gravado (calibração no chão incluída) e devolve os máx |Δ| das 9 estimativas + o uso do portão."""
    lib = bib.lib
    eid = lib.estcl_criar()
    s, out = bib.Sensores(), bib.Saida()
    maxd, passos, gate = np.zeros(9), 0, 0
    a_portao = cfg.est_cl.a_portao
    for ev in g["log_est"][:n]:
        if ev[0] == "reiniciar":
            acc, tof_d, tof_ok = ev[1]
            for i in range(3):
                s.acc[i] = acc[i]
            s.tof_d, s.tof_ok = tof_d, int(tof_ok)
            lib.estcl_iniciar_com(eid, ctypes.byref(s))
        elif ev[0] == "cal":
            lib.estcl_janela(eid, ctypes.byref(cfg), int(ev[1]))
        else:
            giro, acc, tof_d, tof_ok, n_tof, fluxo, fluxo_ok, n_fluxo = ev[1]
            for i in range(3):
                s.giro[i], s.acc[i] = giro[i], acc[i]
            s.tof_d, s.tof_ok, s.n_tof = tof_d, int(tof_ok), n_tof
            s.fluxo[0], s.fluxo[1], s.fluxo_ok, s.n_fluxo = fluxo[0], fluxo[1], int(fluxo_ok), n_fluxo
            lib.estcl_passo(eid, ctypes.byref(cfg), ctypes.byref(s), g["env_hw"][2], ctypes.byref(out))
            if not (out.flags & sitl.FLAG_CALIBRANDO):
                cpp, py = np.array([getattr(out, k) for k in CAMPOS_EST]), np.array(ev[2])
                d = np.abs(cpp - py)
                d[2] = abs((cpp[2] - py[2] + math.pi) % (2 * math.pi) - math.pi)
                maxd = np.maximum(maxd, d)
                passos += 1
                gate += ev[3] > a_portao
    lib.estcl_liberar(eid)
    return {"max": dict(zip(CAMPOS_EST, maxd, strict=True)), "passos": passos, "passos_com_portao": int(gate)}


def fora_de_tolerancia(max_est: dict, escala: float = 1.0) -> list[str]:
    return [f"{k} {v:.1e}>{TOL_EST[k] * escala:.0e}" for k, v in max_est.items() if v > TOL_EST[k] * escala]


# ============================================================================================ §3 layout / config
def secao_layout(c: tn.Checagens, tmp: Path, bib, ctx: dict) -> None:
    cfg, env = ctx["cfg"], ctx["env"]
    n = {nm: (ctypes.sizeof(getattr(bib, nm)), int(getattr(bib.lib, f"nucleo_tamanho_{nm.lower() if nm != 'ReferenciasTaxa' else 'referencias'}")()))
         for nm in ("Config", "Sensores", "Comando", "Saida", "ReferenciasTaxa")}
    c.ok("[§3] as structs de ctypes (geradas do config.hpp + visao_tipos.hpp, com structs ANINHADAS: Camera, ConfigSeguidor, SaidaSeguidor, "
         "ConfigCascata…) têm o MESMO sizeof que o C++", all(a == b for a, b in n.values()), " · ".join(f"{k} {a} B" for k, (a, _) in n.items()))
    mau = tmp / "mau.hpp"
    mau.write_text("struct Config { float a; double b; };\nstruct Sensores { float a; };\nstruct Comando { float a; };\nstruct Saida { float a; };\n", encoding="utf-8")
    mau2 = tmp / "mau2.hpp"
    mau2.write_text("struct Config { float a; Desconhecido b; };\nstruct Sensores { float a; };\nstruct Comando { float a; };\nstruct Saida { float a; };\n", encoding="utf-8")
    estrito = []
    for f in (mau, mau2):
        try:
            sitl.estruturas_do_header(f)
            estrito.append(False)
        except ValueError:
            estrito.append(True)
    c.ok("[§3] o parser de layout continua ESTRITO com structs aninhadas: um `double` e um tipo desconhecido levantam erro (nada diverge em silêncio)", all(estrito))
    g = ctx["gn"]
    d = sitl.config_para_dict(cfg)["cascata"]
    erros = {}
    for nome in cfg.cascata._fields_:
        nome = nome[0]
        if hasattr(g, nome) and nome != "decimacao":
            v = getattr(g, nome)
            erros[nome] = abs(d[nome] - float(np.float32(float(v)))) if not isinstance(v, str) else 0.0
    pior = max(erros.values())
    c.ok(f"[§3] `config_de_hardware` ≡ `ganhos_de_hardware`: os {len(erros)} campos da ConfigCascata com o mesmo nome em `GanhosCascata` são o "
         f"float32 exato do valor Python (|Δ| máx {pior:.1e}); decimação = {d['decimacao']} (50 Hz com 500 Hz); ref_posicao_trava = {d['ref_posicao_trava']}",
         pior == 0.0 and d["decimacao"] == env.decimation and d["ref_posicao_trava"] == 1, "")
    c.ok(f"[§3] limites DERIVADOS da planta e não escritos à mão: taxa_yaw_max {d['taxa_yaw_max']:.4f} rad/s · acel_yaw_max {d['acel_yaw_max']:.4f} rad/s² "
         f"(identificados no simulador) · tilt_max {math.degrees(d['tilt_max']):.1f}° · k_att {d['k_att']:.3f} · k_vel {d['k_vel']:.3f} · k_pos {d['k_pos']:.3f}",
         abs(d["taxa_yaw_max"] - 0.5076) < 5e-3 and abs(d["k_att"] - 3.3734) < 1e-3 and abs(d["tilt_max"] - math.radians(30)) < 1e-6)
    # compensação de tensão: o C++ (u_pair(V)·√c) ≡ DroneRealEnv.acelerador_pairagem para a mesma tensão
    nuc = sitl.NucleoCpp(cfg, bib).exigir_iniciado()
    omega = float(env.hw.ponto_pairagem(env.hw.bateria.v_nominal)["omega"])
    erro_u = 0.0
    for v in np.linspace(14.0, 26.0, 49):
        nuc.reiniciar()
        nuc.armar(True)
        sitl.preencher_sensores(nuc.sens, (0, 0, 0), (0, 0, 9.81), 1.0, True, 1, (0, 0), True, 1, v_bat=float(v))
        nuc.sens.t_us = 2000
        sitl.definir_comando_dict(nuc.cmd, {"modo": "velocidade"})
        nuc.calibrar()
        nuc.travar_referencias(False, 0.0)
        ref = nuc.planear(0.002)
        s = nuc.saida
        u_cpp = float(ref.acelerador) / math.sqrt(max(float(s.coletivo), 1e-9))
        u_py = sitl.u_pairagem_de_tensao(env.hw, omega, float(np.float32(v)), env.u_pairagem)
        erro_u = max(erro_u, abs(u_cpp - u_py))
    nuc.close()
    c.ok(f"[§3] compensação de TENSÃO da bateria no C++ (u = ESC⁻¹(K/V)·√c, curva do ESC de {cfg.n_esc} nós na Config) ≡ `DroneRealEnv.acelerador_pairagem` "
         f"para 49 tensões de 14 a 26 V: |Δu| máx {erro_u:.1e}", erro_u < 2e-6, "")
    hpp = sitl.exportar_config_hpp(cfg, tmp / "cfg_gerada.hpp")
    prog = tmp / "despeja.cpp"
    prog.write_text(f'#include <stdio.h>\n#include "{hpp}"\nint main() {{ fwrite(&kConfig, 1, sizeof(kConfig), stdout); return 0; }}\n', encoding="utf-8")
    exe = tmp / "despeja"
    r = tn._correr(["g++", "-std=c++17", "-I", FIRMWARE_DIR, prog, "-o", exe])
    ok_rt = r.returncode == 0 and subprocess.run([str(exe)], capture_output=True, check=False).stdout == bytes(cfg)
    tu = tmp / "kconfig_m4.cpp"
    tu.write_text(f'#include "{hpp}"\nstatic_assert(kConfig.versao == nucleo::kVersaoInterface, "versao");\nstatic_assert(kConfig.usa_cascata == 1, "cascata");\n', encoding="utf-8")
    rc = tn._correr([tn._ferramenta("clang++"), *tn.FLAGS_CROSS, "-mcpu=cortex-m4", "-mfpu=fpv4-sp-d16", "-I", FIRMWARE_DIR, "-isystem", CROSS_DIR,
                     "-fsyntax-only", tu])
    c.ok("[§3] `exportar_config_hpp` com structs aninhadas: o `constexpr nucleo::Config kConfig` gerado (cascata + seguidor + curva do ESC) compila para "
         f"Cortex-M4 e reproduz a Config BIT A BIT ({ctypes.sizeof(cfg)} B)", ok_rt and rc.returncode == 0, r.stderr[:200] or rc.stderr[:200])

    def recusada(mut) -> bool:
        k = bib.Config.from_buffer_copy(cfg)
        mut(k)
        return not sitl.NucleoCpp(k, bib).iniciado
    casos = {"versão 1": lambda k: setattr(k, "versao", 1),
             "k_att = NaN": lambda k: setattr(k.cascata, "k_att", float("nan")),
             "tilt_max ≥ 90°": lambda k: setattr(k.cascata, "tilt_max", 1.6),
             "decimação 0": lambda k: setattr(k.cascata, "decimacao", 0),
             "coletivo_max ≤ min": lambda k: setattr(k.cascata, "coletivo_max", 0.1),
             "altura_max ≤ min": lambda k: setattr(k.cascata, "altura_max", 0.0),
             "n_esc = 1": lambda k: setattr(k, "n_esc", 1),
             "curva do ESC não crescente": lambda k: k.esc_d.__setitem__(3, 0.0),
             "a_portao = 0": lambda k: setattr(k.est_cl, "a_portao", 0.0),
             "w_pert = NaN": lambda k: setattr(k.cascata, "w_pert", float("nan")),
             "lim_pert < 0": lambda k: setattr(k.cascata, "lim_pert", -1.0),
             "atraso_fluxo fora da fila": lambda k: setattr(k.cascata, "atraso_fluxo", 16),
             "seguidor com f_px = 0": lambda k: setattr(k.seguidor, "f_px", 0.0),
             "estimador_classico = 2": lambda k: setattr(k, "estimador_classico", 2)}
    aceites = [nm for nm, m in casos.items() if not recusada(m)]
    c.ok("[§3] iniciar() recusa Configs inválidas da interface 2 (versão, NaN, tilt ≥ 90°, decimação 0, limites trocados, curva do ESC, portão, seguidor, flag)",
         not aceites, f"aceites por engano: {aceites}" if aceites else f"{len(casos)}/{len(casos)} recusadas")
    v1 = sitl.config_de_hardware(env.hw, env.model, env.dt)
    n1 = sitl.NucleoCpp(v1, bib).exigir_iniciado()
    sitl.preencher_sensores(n1.sens, (0.1, -0.1, 0.05), (0.1, 0.2, 9.8), 1.0, True, 1, (0.01, 0.02), True, 1)
    n1.reiniciar()
    n1.armar(True)
    sitl.definir_comando_ctbr(n1.cmd, 0.6, (0.5, -0.5, 0.1))
    n1.passo(0.002)
    ctbr = [float(m) for m in n1.passo(0.002).motor]
    n1.reiniciar()
    n1.armar(True)
    sitl.definir_comando_ctbr(n1.cmd, 0.6, (0.5, -0.5, 0.1))
    n1.passo(0.002)
    n1.cmd.modo = sitl.MODO_VELOCIDADE
    s1 = n1.passo(0.002)
    ok_v1 = [float(m) for m in s1.motor] == ctbr and bool(s1.flags & sitl.FLAG_MODO_RESERVADO)
    n1.close()
    c.ok("[§3] COMPATIBILIDADE v1: uma Config sem cascata (usa_cascata = 0, estimador_classico = 0 — a que `config_de_hardware(hw, model, dt)` dá) comporta-se "
         "como a v1: VELOCIDADE cai em CTBR com kFlagModoReservado e os motores são IGUAIS (o caminho CTBR da atividade A não mudou)", ok_v1,
         f"flags={s1.flags}")


# ============================================================================================ §4 equivalência
def secao_equivalencia(c: tn.Checagens, bib, ctx: dict, gravacoes: dict) -> None:
    g = gravacoes["nominal"]
    cfg = ctx["cfg_golden"]
    r = comparar_cascata(bib, cfg, g)
    n_dec = r["n"]
    pior = float(r["max"].max())
    c.ok(f"[§4] GOLDEN VECTORS da cascata: {n_dec} decisões (50 Hz, {n_dec / 50:.0f} s de voo GRAVADO do protótipo Python com estimador melhorado: hover, W, A, "
         f"Q/E, degrau de rumo de 90°, taxa de yaw acima do teto, arco, diagonal) — |Δ| máx coletivo {r['max'][0]:.1e} · p {r['max'][1]:.1e} · q {r['max'][2]:.1e} · "
         f"r {r['max'][3]:.1e} ≤ {TOL_CASCATA:.0e}", n_dec >= 2000 and pior <= TOL_CASCATA, f"p99 {np.percentile(r['por_passo'], 99):.1e}")
    c.ok(f"[§4] a gravação EXERCITA a saturação de yaw ({r['flags']['sat_yaw']} decisões com o pedido acima do teto de 0,51 rad/s), a de inclinação "
         f"({r['flags']['sat_incl']}), a das taxas p/q ({r['flags']['sat_rp']}) e a do coletivo ({r['flags']['sat_col']}) — o C++ sai das mesmas decisões",
         r["flags"]["sat_yaw"] > 100, "")
    fora = {k: v for k, v in r["diag"].items() if v > TOL_DIAG[k]}
    c.ok("[§4] o diagnóstico INTERNO da cascata (a_des, n_des, e_tilt, γ, v no rumo/arranque, v_sp, p_sp, z_sp, ψ_sp, r_ref, integrais) também bate: "
         + ", ".join(f"{k} {v:.0e}" for k, v in r["diag"].items()), not fora, str(fora) if fora else "")
    sint = comparar_cascata_sintetico(bib, cfg, ctx["gn"])
    c.ok(f"[§4] golden vectors com entradas SINTÉTICAS violentas ({sint['n']} decisões: inclinações de ±45°, erros de velocidade de ±3 m/s, saltos de altura, yaw a ±2,5 rad/s, "
         f"modo de rumo absoluto): cobrem a saturação de inclinação ({sint['flags']['sat_incl']} decisões), das taxas p/q ({sint['flags']['sat_rp']}), do coletivo "
         f"({sint['flags']['sat_col']}) e do yaw ({sint['flags']['sat_yaw']}) — |Δ| máx {float(sint['max'].max()):.1e}, {sint['n_acima']} decisões acima de 1e-3 "
         f"(p99,9 {sint['p999']:.1e}; as duas cascatas rearmam-se a cada 50 decisões)", min(sint["flags"].values()) > 50 and sint["n_acima"] <= 0.005 * sint["n"] and float(sint["max"].max()) < 0.05, "")
    e = comparar_estimador(bib, cfg, g)
    fora = fora_de_tolerancia(e["max"])
    c.ok(f"[§4] GOLDEN VECTORS do estimador clássico: {e['passos']} passos de 500 Hz (calibração do giroscópio no chão incluída; portão do acelerómetro ATIVO em "
         f"{e['passos_com_portao']} passos, a_h > {cfg.est_cl.a_portao} m/s²): " + " ".join(f"{k} {v:.0e}" for k, v in e["max"].items()),
         e["passos"] >= 20000 and e["passos_com_portao"] > 1000 and not fora, str(fora) if fora else "")
    seg = {}
    for nome in ("outra_semente", "dr"):
        gg = gravacoes[nome]
        cg = ctx["cfg_de"](gg)
        rr, ee = comparar_cascata(bib, cg, gg), comparar_estimador(bib, cg, gg)
        seg[nome] = (float(rr["max"].max()), fora_de_tolerancia(ee["max"], 3.0), rr["n"])
    c.ok("[§4] outro voo (semente 5001) e um voo com DOMAIN RANDOMIZATION (ganhos DESSE sorteio): a mesma equivalência — cascata |Δ| "
         f"{seg['outra_semente'][0]:.1e} / {seg['dr'][0]:.1e} ≤ {TOL_CASCATA:.0e}; estimador dentro de 3× as tolerâncias",
         all(v[0] <= TOL_CASCATA and not v[1] and v[2] >= 2000 for v in seg.values()), str({k: v[1] for k, v in seg.items()}))
    # passo ≡ planear + atuar (sem atraso), bit a bit, com sensores sintéticos realistas (cascata em VELOCIDADE com yaw_taxa)
    nuc_a, nuc_b = sitl.NucleoCpp(ctx["cfg"], bib).exigir_iniciado(), sitl.NucleoCpp(ctx["cfg"], bib).exigir_iniciado()
    rng = np.random.default_rng(3)
    dif = 0
    for n_ in (nuc_a, nuc_b):
        n_.reiniciar()
        n_.armar(True)
        sitl.preencher_sensores(n_.sens, (0, 0, 0), (0, 0, 9.81), 1.0, True, 1, (0, 0), True, 1, v_bat=22.0)
        n_.calibrar()
        n_.travar_referencias(True, 1.0)
    for k in range(600):
        giro, acc, fluxo = rng.normal(0, 0.02, 3), np.array([0.1, 0.0, 9.81]) + rng.normal(0, 0.05, 3), rng.normal(0, 0.01, 2)
        for n_ in (nuc_a, nuc_b):
            sitl.preencher_sensores(n_.sens, giro, acc, 0.96, True, 1 + k // 17, fluxo, True, 1 + k // 5, v_bat=22.0)
            n_.sens.t_us = 2000 * (k + 1)
            sitl.definir_comando_dict(n_.cmd, {"vx": 0.5 if k > 100 else 0.0, "yaw_taxa": 0.3})
        a = bytes(nuc_a.passo(0.002))
        ref = nuc_b.planear(0.002)
        dif += a != bytes(nuc_b.atuar(ref, 0.002))
    nuc_a.close()
    nuc_b.close()
    c.ok("[§4] `passo()` ≡ `planear()` + `atuar()` (o passo partido que o SITL usa para pôr o atraso do comando entre os laços): 600 passos BIT A BIT iguais "
         "na Saida inteira", dif == 0, f"{dif} diferenças")
    d = decimacao(bib, cfg)
    c.ok(f"[§4] DECIMAÇÃO: o laço externo decide 1× por {d['decimacao']} passos do núcleo (50 Hz com 500 Hz) e segura (ZOH) as referências entre decisões — em "
         f"{d['ticks']} blocos de 10 passos as taxas pedidas só mudam nas decisões ({d['mudou_no_tick']} mudanças nos passos de decisão, {d['mudou_fora']} fora delas)",
         d["mudou_fora"] == 0 and d["mudou_no_tick"] >= d["ticks"] - 2, "")
    k_mau = bib.Config.from_buffer_copy(cfg)
    k_mau.cascata.k_att *= 1.2
    r_mau = comparar_cascata(bib, k_mau, g, 1500)
    c.ok("[§4] NÃO-TAUTOLOGIA: com o ganho de atitude k_att +20 % o C++ SAI da tolerância (|Δ| "
         f"{float(r_mau['max'].max()):.1e} > {TOL_CASCATA:.0e}) — o teste não passa por construção", float(r_mau["max"].max()) > 10 * TOL_CASCATA, "")


# ============================================================================================ §5 malha fechada
def _tarefas(jobs: list[dict], n_jobs: int = 8) -> list[dict]:
    with cf.ProcessPoolExecutor(max_workers=n_jobs, initializer=an._init_worker) as ex:
        return list(ex.map(an.tarefa, jobs, chunksize=1))


def _rel(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1e-9)


def secao_malha(c: tn.Checagens, u_yaw: float, rapido: bool) -> dict:
    sementes = (5000, 5001, 5002)
    base = {"seed": 0, "dr": False, "u_yaw": u_yaw}
    jobs = []
    for s in sementes:
        for var, kind in (("cpp", "nucleo"), ("py", "python_vivo")):
            jobs.append({**base, "kind": kind, "teste": "hover", "seed": s, "T": 30.0, "v": var})
            jobs.append({**base, "kind": kind, "teste": "seguimento", "seed": s, "T": 10.0, "v": var})
            jobs.append({**base, "kind": kind, "teste": "degrau", "seed": s, "v": [1.0, 0.0, 0.0], "var": var})
            jobs.append({**base, "kind": kind, "teste": "yaw_degrau", "seed": s, "dur": 14.0, "var": var})
            jobs.append({**base, "kind": kind, "teste": "yaw_taxa", "seed": s, "r": 1.2, "dur": 8.0, "var": var})
            jobs.append({**base, "kind": kind, "teste": "yaw_arco", "seed": s, "v": 1.0, "r": 0.5, "dur": 14.0, "var": var})
            jobs.append({**base, "kind": kind, "teste": "hover", "seed": s, "T": 20.0, "dr": True, "var": var})
    res = _tarefas(jobs)
    por = {}
    for j, r in zip(jobs, res, strict=True):
        por[(j["kind"], j["teste"], j["seed"], j["dr"], j.get("r"))] = r

    def media(kind, teste, chave, dr=False, r=None):
        return float(np.mean([por[(kind, teste, s, dr, r)][chave] for s in sementes]))
    quedas = sum(bool(x.get("terminou")) for x in res)
    out = {}
    for rot, teste, chaves, dr in (("hover 30 s", "hover", ("xy_rms", "dz_rms", "roll_rms_graus", "pitch_rms_graus"), False),
                                   ("seguimento WASDQE", "seguimento", ("v_rms", "xy_rms", "z_rms"), False),
                                   ("degrau frente", "degrau", ("sobressinal", "subida_10_90_s"), False),
                                   ("yaw 90°", "yaw_degrau", ("subida_10_90_s", "sobressinal", "dz_max"), False)):
        difs = {k: _rel(media("nucleo", teste, k, dr), media("python_vivo", teste, k, dr)) for k in chaves}
        out[rot] = {k: (media("nucleo", teste, k, dr), media("python_vivo", teste, k, dr)) for k in chaves}
        c.ok(f"[§5] MALHA FECHADA {rot} (sementes de avaliação {sementes[0]}…{sementes[-1]}, sem vento, o C++ manda nos motores e vê só sensores): C++ vs Python = "
             + " · ".join(f"{k} {out[rot][k][0]:.4g} vs {out[rot][k][1]:.4g} ({100 * v:.2f} %)" for k, v in difs.items()) + f" — todas ≤ {100 * TOL_REL_MALHA:.0f} %",
             all(v <= TOL_REL_MALHA for v in difs.values()), "")
    d_dr = {k: _rel(media("nucleo", "hover", k, True), media("python_vivo", "hover", k, True)) for k in ("xy_rms", "dz_rms")}
    c.ok("[§5] com DOMAIN RANDOMIZATION (peças/bateria/sensores sorteados; o C++ com os ganhos da planta NOMINAL, o Python com os ganhos re-derivados por sorteio): hover "
         f"‖xy‖ {media('nucleo', 'hover', 'xy_rms', True) * 100:.1f} vs {media('python_vivo', 'hover', 'xy_rms', True) * 100:.1f} cm — sem quedas e dentro de 10 %",
         quedas == 0 and all(v <= 0.10 for v in d_dr.values()), f"quedas={quedas}")
    # saturação de yaw: a taxa pedida (1,2 rad/s) é cortada ao teto da planta
    taxa = media("nucleo", "yaw_taxa", "taxa_media", False, 1.2)
    teto = 0.5076
    c.ok(f"[§5] YAW com taxa pedida ACIMA do teto (1,2 rad/s): o C++ segura a taxa medida em {taxa:.3f} rad/s ≤ teto {teto:.3f} + 3 % (autoridade de yaw do frame), sem saturar a "
         f"mistura (frac. saturada {media('nucleo', 'yaw_taxa', 'frac_saturado', False, 1.2) * 100:.2f} %) e |Δz| máx {media('nucleo', 'yaw_taxa', 'dz_max', False, 1.2) * 100:.1f} cm",
         taxa <= teto * 1.03 and media("nucleo", "yaw_taxa", "frac_saturado", False, 1.2) < 0.02, "")
    ya = media("nucleo", "yaw_degrau", "erro_regime_graus")
    c.ok(f"[§5] YAW_ALVO: o degrau de rumo de 90° converge (erro final {ya:+.2f}°, sobressinal {media('nucleo', 'yaw_degrau', 'sobressinal') * 100:.2f} %, assentamento a 5 % "
         f"{media('nucleo', 'yaw_degrau', 'assenta_5pct_s'):.2f} s)", abs(ya) < 1.5 and media("nucleo", "yaw_degrau", "sobressinal") < 0.03, "")
    hov = media("nucleo", "hover", "xy_rms")
    c.ok(f"[§5] VELOCIDADE com v = 0 SEGURA a posição (como o modo Position do PX4): hover de 30 s a ‖xy‖ RMS {hov * 100:.1f} cm (RL de referência: 13,0 cm), "
         f"deriva de rumo {media('nucleo', 'hover', 'deriva_rumo_graus'):.1f}°", hov < 0.08, "")
    return out


def olhar_perda(dados: dict, u_yaw: float) -> dict:
    """OLHAR com a perda do alvo: segue um alvo parado, o alvo some atrás do drone (cenário, como o `definir_trajetoria_ponto`) e volta — estados do IBVS."""
    env = an.criar_env_nucleo(dados, dr=False, episodio_s=22.0, u_yaw=u_yaw, com_alvo=True, cascata={"camera": {"latencia_s": 0.116}})
    env.ponto_modo, env.ponto_vel = "parado", 0.0
    env.reset(seed=11)
    p0 = np.array(env.ponto_alvo, dtype=float)
    estados, tempos = [], []
    for k in range(round(22.0 / env.dt_decisao)):
        t = k * env.dt_decisao
        env.fc.definir_comando({"modo": "olhar"} if t >= 4.0 else {})
        if 10.0 <= t < 12.5:
            env.ponto_alvo[:] = (-3.0, 0.0, p0[2])         # o cenário esconde o alvo ATRÁS do drone (fora do campo)
        elif t >= 12.5:
            env.ponto_alvo[:] = p0
        env.step(np.zeros(4, dtype=np.float32))
        estados.append(int(env.nucleo.saida.seguidor.estado))
        tempos.append(t)
    camera = env.camera_sitl.estatisticas()
    env.close()
    e, t = np.array(estados), np.array(tempos)
    seq = [int(x) for i, x in enumerate(e) if i == 0 or e[i - 1] != x]
    return {"sequencia": seq, "perdido_em": float(t[(e == 2) & (t > 10.0)][0]) if ((e == 2) & (t > 10.0)).any() else float("nan"),
            "a_seguir_de_novo_em": float(t[(e == 0) & (t > 12.5)][0]) if ((e == 0) & (t > 12.5)).any() else float("nan"),
            "frac_final_a_seguir": float(np.mean(e[t > 18.0] == 0)), "frames": camera}


def secao_olhar(c: tn.Checagens, u_yaw: float, dados: dict) -> dict:
    base = {"kind": "olhar", "teste": "olhar", "dr": False, "u_yaw": u_yaw, "T": 30.0}
    jobs = [{**base, "variante": "pi", "build": None, "latencia": 0.116, "modo": "parado", "vel": 0.0, "seed": 7000},
            {**base, "variante": "pi", "build": None, "latencia": 0.116, "modo": "circulo", "vel": 0.5, "seed": 7000},
            {**base, "variante": "ard", "build": "arduino", "latencia": 0.021, "modo": "circulo", "vel": 0.5, "seed": 7000},
            {**base, "variante": "pi", "build": None, "latencia": 0.116, "modo": "circulo", "vel": 0.8, "seed": 7000},
            {**base, "variante": "ard", "build": "arduino", "latencia": 0.021, "modo": "circulo", "vel": 0.8, "seed": 7000}]
    # a «parede» da guinada é da lei da VERSÃO 1 do IBVS (só guinada: `visao::config_versao1`); a lei por omissão (versão 2,
    # «seguir a bola») junta-lhe a translação lateral — os 4 círculos voam-se também com a v1 (`pi5v`…`ard8`) para a medir
    import avaliar_bola
    v1 = avaliar_bola.seguidor_antes()
    jobs += [{**j, "variante": j["variante"] + "_v1", "seguidor": v1} for j in jobs[1:]]
    est, pi5, ard5, pi8n, ard8n, pi5v, ard5v, pi8, ard8 = _tarefas(jobs, 8)
    c.ok(f"[§5] OLHAR com frames mono QVGA RENDERIZADOS (EGL, 30 Hz, latência 116 ms) + detetor C++ + IBVS + cascata, alvo PARADO: rumo RMS {est['rumo_rms_graus']:.2f}° · "
         f"|D−d*| RMS {est['dist_erro_rms'] * 100:.1f} cm · A_SEGUIR {est['frac_a_seguir'] * 100:.0f} % · frames válidos {est['frac_frames_validos'] * 100:.0f} % "
         f"(render {est['render_ms']:.2f} ms + detetor {est['detetor_ms']:.2f} ms no host)", est["rumo_rms_graus"] < 1.0 and est["frac_a_seguir"] > 0.9 and est["frac_frames_validos"] > 0.99
         and est["dist_erro_rms"] < 0.15, "")
    c.ok(f"[§5] OLHAR segue o CÍRCULO a 0,5 m/s sem perder o alvo (3D completo, planta MuJoCo): rumo RMS {pi5['rumo_rms_graus']:.2f}° (116 ms) / {ard5['rumo_rms_graus']:.2f}° (21 ms DCMI, "
         f"build Arduino), máx {pi5['rumo_max_graus']:.1f}° / {ard5['rumo_max_graus']:.1f}°, A_SEGUIR {pi5['frac_a_seguir'] * 100:.0f} % / {ard5['frac_a_seguir'] * 100:.0f} %",
         pi5["rumo_rms_graus"] < 3.0 and ard5["rumo_rms_graus"] < 2.0 and pi5["frac_a_seguir"] > 0.9 and ard5["frac_a_seguir"] > 0.9 and not pi5.get("terminou"), "")
    c.ok(f"[§5] a PAREDE da autoridade de yaw com a lei v1 do IBVS (só guinada): a 0,8 m/s o yaw fica no teto de {pi8['yaw_teto']:.2f} rad/s durante {pi8['frac_yaw_no_limite'] * 100:.0f} % "
         f"(116 ms) / {ard8['frac_yaw_no_limite'] * 100:.0f} % (21 ms) do tempo e o rumo RMS sobe para {pi8['rumo_rms_graus']:.1f}° / {ard8['rumo_rms_graus']:.1f}° "
         f"(×{pi8['rumo_rms_graus'] / pi5v['rumo_rms_graus']:.1f} / ×{ard8['rumo_rms_graus'] / ard5v['rumo_rms_graus']:.1f} face a 0,5 m/s; taxa LOS verdadeira p95 "
         f"{pi8['los_taxa_p95']:.2f} rad/s) — o alvo continua no campo ({pi8['frac_frames_validos'] * 100:.0f} % de frames válidos): é a autoridade de yaw, não a visão",
         # a razão face a 0,5 m/s é ×2,3 nominal nesta semente mas o render não é determinístico (medido ×1,9–×2,3): limiar 1,5
         pi8["frac_yaw_no_limite"] > 0.2 and ard8["frac_yaw_no_limite"] > 0.2 and pi8["rumo_rms_graus"] > 1.5 * pi5v["rumo_rms_graus"] and pi8["frac_frames_validos"] > 0.95, "")
    c.ok(f"[§5] …e a lei POR OMISSÃO (v2: guinada + translação lateral) contorna-a: o mesmo círculo a 0,8 m/s dá rumo RMS {pi8n['rumo_rms_graus']:.1f}° / {ard8n['rumo_rms_graus']:.1f}° "
         f"(medido ×0,5 / ×0,6 do da v1; exige-se < ×0,8 / ×0,9) com o yaw no teto só {pi8n['frac_yaw_no_limite'] * 100:.0f} % / {ard8n['frac_yaw_no_limite'] * 100:.0f} % do tempo (< 10 %), sem perder o alvo",
         pi8n["rumo_rms_graus"] < 0.8 * pi8["rumo_rms_graus"] and ard8n["rumo_rms_graus"] < 0.9 * ard8["rumo_rms_graus"] and pi8n["frac_yaw_no_limite"] < 0.1
         and ard8n["frac_yaw_no_limite"] < 0.1 and pi8n["frac_frames_validos"] > 0.95 and not pi8n.get("terminou") and not ard8n.get("terminou"), "")
    p = olhar_perda(dados, u_yaw)
    ok = 2 in p["sequencia"] and p["sequencia"][-1] == 0 and p["frac_final_a_seguir"] > 0.9 and np.isfinite(p["perdido_em"]) and p["perdido_em"] - 10.0 < 1.0
    c.ok(f"[§5] OLHAR com perda e reaquisição (o alvo some atrás do drone 2,5 s): estados A_SEGUIR=0/EM_FALTA=1/PERDIDO=2/REAQUISICAO=3 → sequência {p['sequencia']}; PERDIDO a "
         f"t = {p['perdido_em']:.2f} s (≤ 1 s depois de sumir), de novo em A_SEGUIR a t = {p['a_seguir_de_novo_em']:.2f} s, {p['frac_final_a_seguir'] * 100:.0f} % "
         "em A_SEGUIR no fim — o drone não cai", ok, "")
    return {"pi5": pi5, "ard5": ard5, "pi8": pi8, "ard8": ard8, "estatico": est, "perda": p,
            "pi5_v1": pi5v, "ard5_v1": ard5v, "pi8_v2": pi8n, "ard8_v2": ard8n}


# ============================================================================================ §6 alvo
def secao_alvo(c: tn.Checagens, tmp: Path, rapido: bool) -> dict:
    info: dict = {}
    t0 = time.perf_counter()
    voo = qa.gravar_voo(segundos=14.0, seed=0)
    R, est = voo["RegistoCls"], voo["est"]
    regs = voo["registos"] + qa.registos_detetar(R, 24)
    rel = qa.provar(regs, voo["cfg"], est, tmp / "voo_a", verboso=False)
    info["voo"] = rel
    ok_v = bool(rel.get("ok"))
    tam = {cpu: rel[cpu]["tamanho"] for cpu in ("m4", "m7")}
    c.ok(f"[§6] NO ALVO: o MESMO código em QEMU Cortex-M4 (mps2-an386) e M7 (mps2-an500) dá as MESMAS saídas BIT A BIT que o host (libm própria, -ffp-contract=off): "
         f"{rel['passos']} passos de 500 Hz de um voo SITL gravado (calibração no chão, VELOCIDADE, YAW_ALVO, taxa de yaw saturada) + {rel['deteccoes']} deteções sintéticas "
         f"do detetor, {rel['host_minima']['stdout'].split('bytes=')[1].split()[0]} B de saída; crc32 {rel['m4']['stdout'].split('crc32=')[-1]}; imagens M4 text "
         f"{tam['m4']['text']} B / M7 text {tam['m7']['text']} B (com driver, detetor e libm própria) · QEMU {rel['m4']['duracao_s']:.1f} s / {rel['m7']['duracao_s']:.1f} s",
         ok_v, str({k: rel[k].get("bit_exact") for k in ("m4", "m7")}))
    voo2 = qa.gravar_voo(segundos=10.0, seed=1, olhar=True)
    regs2 = voo2["registos"] + qa.registos_detetar(voo2["RegistoCls"], 6, semente=9)
    rel2 = qa.provar(regs2, voo2["cfg"], voo2["est"], tmp / "voo_b", verboso=False, com_glibc=False)
    info["olhar"] = rel2
    c.ok(f"[§6] idem num voo em OLHAR (câmara renderizada + IBVS + cascata a 116 ms): {rel2['passos']} passos, host ≡ M4 ≡ M7 BIT A BIT", bool(rel2.get("ok")),
         str({k: rel2[k].get("bit_exact") for k in ("m4", "m7")}))
    g = rel.get("glibc")
    if g:
        sa = g.get("saida", {})
        mot = sa.get("campos", {}).get("motor", {})
        info["glibc"] = sa.get("campos", {})
        c.ok("[§6] host com a glibc em vez da libm própria (só diferença de libm, ≤ 2 ULP por chamada): as Saídas do mesmo voo diferem pouco — motores máx |Δ| "
             f"{mot.get('max_abs', 0.0):.1e} ({mot.get('max_ulp', 0)} ULP), {sa.get('bit_exact', False) and 'bit-exact' or 'não bit-exact (esperado: as libm diferem)'}",
             mot.get("max_abs", 1.0) < 5e-3, "")
    # o comparador TEM DENTES: uma imagem M7 compilada com FMA (-ffp-contract=fast) diverge do host
    elf_fma = qa.compilar_imagem("m7", FIRMWARE_DIR, extra=("-ffp-contract=fast",))
    saida_fma = tmp / "voo_a" / "saida_fma.bin"
    rq = qa.correr_qemu(elf_fma, "m7", tmp / "voo_a" / "config.bin", tmp / "voo_a" / "entrada.bin", saida_fma)
    cmp_fma = qa._comparar_por_op(tmp / "voo_a" / "saida_host.bin", saida_fma, est, [r.op for r in regs])
    campos = cmp_fma.get("saida", {}).get("campos", {})
    mx = max((v.get("max_ulp", 0) for v in campos.values()), default=0)
    c.ok(f"[§6] o comparador TEM DENTES: a mesma imagem M7 compilada com `-ffp-contract=fast` (FMA) NÃO é bit-exact ({len(campos)} campos divergem, até {mx} ULP; 1.º bloco "
         f"divergente {cmp_fma['saida']['primeiro_divergente']}) — por isso o harness fixa -ffp-contract=off nos dois lados", rq["codigo"] == 0 and not cmp_fma["bit_exact"] and mx > 0, "")
    # libm própria vs glibc em ULP
    exe = tmp / "testa_libm"
    rl = tn._correr(["g++", "-O2", "-ffp-contract=off", "-fno-math-errno", "-Wall", "-Wextra", "-Werror", QEMU_DIR / "testa_libm.cpp", QEMU_DIR / "libm_minima.cpp", "-I", QEMU_DIR,
                     "-o", exe])
    out = subprocess.run([str(exe)], capture_output=True, text=True, check=False).stdout if rl.returncode == 0 else rl.stderr
    m = re.search(r"sin max ULP ([\d.]+).*cos ([\d.]+).*atan2 ([\d.]+)", out)
    ulp = [float(x) for x in m.groups()] if m else [99.0]
    info["libm_ulp"] = ulp
    c.ok(f"[§6] a libm PRÓPRIA (sem libm: Cody–Waite + polinómios de Chebyshev; `libm_minima.cpp`) tem erro máx vs glibc: sinf {ulp[0]:.0f} · cosf {ulp[1]:.0f} · atan2f "
         f"{ulp[2]:.0f} ULP em 4 M de pontos (|x| ≤ 100 rad) — ≤ 2 ULP", m is not None and max(ulp) <= 2.0, out.strip()[:120])
    # instruções e ciclos
    trab = tmp / "traco"
    ciclos = {}
    for cpu in ("m7", "m4"):
        r = qa.rastrear_instrucoes(cpu, voo["registos"], voo["cfg"], est, trab / cpu)
        ciclos[cpu] = r
    m7, m4 = ciclos["m7"], ciclos["m4"]
    nm, tk = int(np.median(m7["normal_instr"])), int(np.median(m7["tick_instr"]))
    nm4, tk4 = int(np.median(m4["normal_instr"])), int(np.median(m4["tick_instr"]))
    lt, ln = m7["chamadas_libm_tick"], m7["chamadas_libm_normal"]
    c.ok(f"[§6] INSTRUÇÕES EXATAS por passo (traço do QEMU, instruction-accurate, -O2; MEDIDO): passo normal de 500 Hz (estimador + laço de taxa + mistura) {nm} instr no M7 / "
         f"{nm4} no M4 · passo com DECISÃO da cascata (50 Hz) {tk} / {tk4}; chamadas à libm (sinf/cosf/atan2f): normal {ln['nucleo_sinf']}/{ln['nucleo_cosf']}/{ln['nucleo_atan2f']} · "
         f"decisão {lt['nucleo_sinf']}/{lt['nucleo_cosf']}/{lt['nucleo_atan2f']}", nm < 2000 and tk < 4000 and len(m7["normal_instr"]) > 20, "")
    est_ciclos = {}
    for cpu, r in (("m7", m7), ("m4", m4)):
        est_ciclos[cpu] = {k: {"mca": qa.ciclos_mca(r["tracos"][k], cpu, trab), "tabela": qa.ciclos_tabela_m4(r["tracos"][k])} for k in ("normal", "tick")}
    info["ciclos"] = est_ciclos
    info["instrucoes"] = {"m7": {"normal": nm, "tick": tk}, "m4": {"normal": nm4, "tick": tk4}, "libm_tick": lt, "libm_normal": ln}
    um = {"m7": 480.0, "m4": 240.0}
    linhas = []
    for cpu in ("m7", "m4"):
        for k in ("normal", "tick"):
            cy = est_ciclos[cpu][k]["mca"]["ciclos"]
            linhas.append(f"{cpu.upper()} {k}: {cy} ciclos = {cy / um[cpu]:.1f} µs @ {um[cpu]:.0f} MHz ({100 * cy / um[cpu] / 2000:.2f} % de 2 ms)")
    pior_us = max(est_ciclos[cpu][k]["mca"]["ciclos"] / um[cpu] for cpu in ("m7", "m4") for k in ("normal", "tick"))
    pior_tab = max(est_ciclos["m4"][k]["tabela"]["ciclos"] / um["m4"] for k in ("normal", "tick"))
    c.ok("[§6] CICLOS ESTIMADOS (llvm-mca sobre as sequências EXATAS executadas; caches/flash ideais — NÃO medido; o DWT->CYCCNT não existe no QEMU): " + " · ".join(linhas) +
         f" · M4 por tabela ARM (VMLA 3, VDIV/VSQRT 14, LDR 2, ramo 1+P): normal {est_ciclos['m4']['normal']['tabela']['ciclos']} / decisão {est_ciclos['m4']['tick']['tabela']['ciclos']} ciclos "
         f"({est_ciclos['m4']['normal']['tabela']['ciclos'] / um['m4']:.1f} / {est_ciclos['m4']['tick']['tabela']['ciclos'] / um['m4']:.1f} µs @ 240 MHz)",
         pior_us < 40.0 and pior_tab < 60.0, f"o pior passo ocupa {100 * max(pior_us, pior_tab) / 2000:.2f} % do orçamento de 2 ms")
    info["tempo_s"] = time.perf_counter() - t0
    return info


# ============================================================================================ §7 mutações
MUTACOES = (
    ("cascata.hpp", "r.taxas[2] = limita(r_ff + g.peso_yaw * g.k_yaw * gama, -g.taxa_yaw_max, g.taxa_yaw_max);",
     "r.taxas[2] = limita(r_ff - g.peso_yaw * g.k_yaw * gama, -g.taxa_yaw_max, g.taxa_yaw_max);", "sinal do erro de yaw (γ)", "golden"),
    ("cascata.hpp", "float coletivo = mod / g.g;", "float coletivo = fz / g.g;", "empuxo SEM a compensação ÷cosφcosθ (usa só a componente vertical)", "golden"),
    ("cascata.hpp", "i_vel_[0] = limita(i_vel_[0] + g.ki_vel * dt * (evx + k_aw * (ax_s - ax)), -g.lim_i_vel, g.lim_i_vel);",
     "i_vel_[0] = limita(i_vel_[0] + g.ki_vel * dt * (evx + 0.0f * k_aw * (ax_s - ax)), -g.lim_i_vel, g.lim_i_vel);",
     "anti-windup por retro-cálculo anulado (só se vê quando a inclinação satura)", "golden"),
    ("cascata.hpp", "const float e_x = -nby / meio_cos;", "const float e_x = -nby;", "erro de inclinação sem o 1/cos(α/2) (prioridade de inclinação)", "golden"),
    ("cascata.hpp", "r_ref_ += limita(r_des - r_ref_, -g.acel_yaw_max * dt, g.acel_yaw_max * dt);", "r_ref_ = r_des;",
     "limite de ACELERAÇÃO de yaw removido (a mistura saturaria)", "golden"),
    ("cascata.hpp", "v_mod_h_[0] += am * (v_sp_h_[0] - v_mod_h_[0]);", "v_mod_h_[0] += am * (v_sp_h_[1] - v_mod_h_[0]);",
     "modelo de seguimento da velocidade: canal trocado", "golden"),
    ("estimador_classico.hpp", "k = k / (1.0f + rel * rel);", "k = k * (1.0f + 0.0f * rel);", "portão do acelerómetro removido", "golden"),
    ("estimador_classico.hpp", "const float p = s.giro[0] - bias_giro_[0] - b_pi_[0];", "const float p = s.giro[0] - b_pi_[0];",
     "viés do giroscópio NÃO subtraído (calibração no chão inútil em p)", "golden"),
    ("estimador_classico.hpp", "bias_acc_ = limita(bias_acc_ - w * w * w * periodo * erro, -e.lim_bias_acc, e.lim_bias_acc);",
     "bias_acc_ = limita(bias_acc_ + w * w * w * periodo * erro, -e.lim_bias_acc, e.lim_bias_acc);", "sinal do viés do acelerómetro (altura de 3.ª ordem)", "golden"),
    # --- interface 3 (fase 2: vento): o observador de perturbação da cascata e a velocidade do fluxo sem os artefactos da rotação
    ("cascata.hpp", "d_obs_[i] = limita(d_obs_[i] + dt * g.w_pert * g.w_pert * e_o, -g.lim_pert, g.lim_pert);",
     "d_obs_[i] = limita(d_obs_[i] - dt * g.w_pert * g.w_pert * e_o, -g.lim_pert, g.lim_pert);",
     "observador de perturbação: ganho do estado estendido com o sinal trocado", "golden"),
    ("cascata.hpp", "const float ax = aff_x + g.k_vel * evx + i_vel_[0] - g.kd_vel * d_filt_[0] - d_obs_[0];",
     "const float ax = aff_x + g.k_vel * evx + i_vel_[0] - g.kd_vel * d_filt_[0] + d_obs_[0];",
     "a perturbação observada SOMA-SE à aceleração pedida em vez de ser anulada", "golden"),
    ("cascata.hpp", "const float fz_emp = (g.g + az_ref_) / den;", "const float fz_emp = 0.0f * (g.g + az_ref_) / den;",
     "observador de perturbação SEM o modelo do empuxo (cada inclinação passa a ser «vento»)", "golden"),
    ("estimador_classico.hpp", "const float vx_m = s.tof_d * (q_f - s.fluxo[1]) + braco * q_f;",
     "const float vx_m = s.tof_d * (q_f - s.fluxo[1]) - braco * q_f;", "braço do sensor de fluxo ao CM com o sinal trocado", "golden"),
    ("estimador_classico.hpp", "if (n_atraso > 0 && n_fila_ > n_atraso) {", "if (n_atraso > 0 && n_fila_ > n_atraso + 100) {",
     "alinhamento giroscópio/fluxo desligado (a rotação tirada ao fluxo é a de agora)", "golden"),
    ("nucleo.cpp", "float d = cfg_.upv_k / v_bat;", "float d = cfg_.upv_k / 22.0f;", "compensação de tensão desligada (tensão fixa)", "tensao"),
    ("nucleo.cpp", "if (cont_cascata_ == 0) {  // ---- uma decisão da cascata", "if (cont_cascata_ >= 0) {  // ---- uma decisão da cascata",
     "a cascata corre a 500 Hz em vez de 50 Hz (decimação ignorada)", "decimacao"),
)


def _compilar_mutante(i: int, ficheiro: str, antigo: str, novo: str, base: Path):
    raiz = base / f"mut_{i}"
    pasta = raiz / "nucleo"
    shutil.copytree(NUCLEO_DIR, pasta)
    f = pasta / ficheiro
    texto = f.read_text(encoding="utf-8")
    if texto.count(antigo) != 1:
        return f"âncora {antigo!r} encontrada {texto.count(antigo)}× em {ficheiro} (esperada 1×)"
    f.write_text(texto.replace(antigo, novo), encoding="utf-8")
    try:
        sitl.compilar_nucleo(pasta, raiz / "out", limpar=False)
    except RuntimeError as erro:
        return f"o mutante não compila: {erro}"
    return raiz


def decimacao(bib, cfg, n: int = 120) -> dict:
    """O laço externo decide 1× por `decimacao` passos (50 Hz com 500 Hz) e as referências SEGURAM (ZOH) entre decisões: com sensores e comando
    a mudar a cada passo, as taxas pedidas só mudam nos passos 0, 10, 20… depois de travar."""
    nuc = sitl.NucleoCpp(cfg, bib).exigir_iniciado()
    rng = np.random.default_rng(5)
    dec = int(cfg.cascata.decimacao)
    nuc.reiniciar()
    nuc.armar(True)
    sitl.preencher_sensores(nuc.sens, (0, 0, 0), (0, 0, 9.81), 1.0, True, 1, (0, 0), True, 1, v_bat=22.0)
    nuc.calibrar()
    nuc.travar_referencias(False, 0.0)
    ant, mudou_tick, mudou_fora = None, 0, 0
    for k in range(n):
        sitl.preencher_sensores(nuc.sens, rng.normal(0, 0.05, 3), (0.2, 0.1, 9.81) + rng.normal(0, 0.1, 3), 1.0, True, 1 + k // 17,
                                rng.normal(0, 0.01, 2), True, 1 + k // 5, v_bat=22.0)
        nuc.sens.t_us = 2000 * (k + 1)
        sitl.definir_comando_dict(nuc.cmd, {"vx": float(rng.uniform(-1, 1)), "vy": float(rng.uniform(-1, 1)), "yaw_taxa": float(rng.uniform(-0.4, 0.4))})
        s = nuc.passo(0.002)
        atual = (float(s.taxas_ref[0]), float(s.taxas_ref[1]), float(s.coletivo))
        if ant is not None and atual != ant:
            if k % dec == 0:
                mudou_tick += 1
            else:
                mudou_fora += 1
        ant = atual
    nuc.close()
    return {"decimacao": dec, "mudou_no_tick": mudou_tick, "mudou_fora": mudou_fora, "ticks": n // dec}


def _tensao_ok(bib, cfg, env) -> bool:
    """A compensação de tensão: u_pair(V) varia com V (a 16 V ≠ a 25 V) como no Python."""
    nuc = sitl.NucleoCpp(cfg, bib).exigir_iniciado()
    us = []
    for v in (16.0, 25.0):
        nuc.reiniciar()
        nuc.armar(True)
        sitl.preencher_sensores(nuc.sens, (0, 0, 0), (0, 0, 9.81), 1.0, True, 1, (0, 0), True, 1, v_bat=v)
        nuc.calibrar()
        nuc.travar_referencias(False, 0.0)
        sitl.definir_comando_dict(nuc.cmd, {})
        ref = nuc.planear(0.002)
        us.append(float(ref.acelerador))
    nuc.close()
    return us[0] - us[1] > 0.1


def secao_mutacoes(c: tn.Checagens, tmp: Path, bib, ctx: dict, gravacao: dict) -> None:
    cfg_g = ctx["cfg_golden"]
    base = comparar_cascata(bib, cfg_g, gravacao, 1200)
    base_e = comparar_estimador(bib, cfg_g, gravacao, 9000)
    base_s = comparar_cascata_sintetico(bib, cfg_g, ctx["gn"], 1500)
    base_d = decimacao(bib, cfg_g)
    c.ok("[§7] CONTROLO: o C++ intacto passa os critérios usados nas mutações (1200 decisões gravadas, 1500 de entradas violentas e 9000 passos do estimador; |Δ| cascata "
         f"{float(base['max'].max()):.1e} / {float(base_s['max'].max()):.1e}, estimador dentro das tolerâncias; decimação {base_d['decimacao']}: as referências só mudam nas decisões)",
         float(base["max"].max()) <= TOL_CASCATA and float(base_s["max"].max()) <= TOL_CASCATA and not fora_de_tolerancia(base_e["max"]) and base_d["mudou_fora"] == 0
         and base_d["mudou_no_tick"] > 3, "")
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(_compilar_mutante, i, f, a, n, tmp) for i, (f, a, n, _d, _t) in enumerate(MUTACOES)]
        raizes = [fu.result() for fu in futs]
    apanhadas = 0
    for (ficheiro, _a, _n, desc, detetor), raiz in zip(MUTACOES, raizes, strict=True):
        if isinstance(raiz, str):
            c.ok(f"[§7] mutação «{desc}» ({ficheiro}) aplicável e compilável", False, raiz)
            continue
        so = next((raiz / "out").glob("libnucleo-*.so"))
        mbib = sitl.BibliotecaNucleo(so, raiz / "nucleo" / "config.hpp")
        mcfg = mbib.Config.from_buffer_copy(cfg_g)
        if detetor == "tensao":
            apanhada = not _tensao_ok(mbib, mcfg, ctx["env"])
            motivo = "a tensão deixa de mexer no acelerador"
        elif detetor == "decimacao":
            d = decimacao(mbib, mcfg)
            apanhada = d["mudou_fora"] > 0
            motivo = f"as referências mudam em {d['mudou_fora']} passos que não são decisões (a cada {d['decimacao']} passos)"
        else:
            rc, re_ = comparar_cascata(mbib, mcfg, gravacao, 1200), comparar_estimador(mbib, mcfg, gravacao, 9000)
            rs = comparar_cascata_sintetico(mbib, mcfg, ctx["gn"], 1500)
            fora = fora_de_tolerancia(re_["max"])
            apanhada = float(rc["max"].max()) > TOL_CASCATA or float(rs["max"].max()) > TOL_CASCATA or bool(fora)
            motivo = (f"cascata |Δ| {float(rc['max'].max()):.1e}" if float(rc["max"].max()) > TOL_CASCATA else
                      f"cascata (entradas violentas) |Δ| {float(rs['max'].max()):.1e}" if float(rs["max"].max()) > TOL_CASCATA else
                      f"estimador {', '.join(fora[:2])}")
        apanhadas += apanhada
        quem = {"golden": "pelo teste de equivalência (golden vectors: voo gravado + entradas violentas)", "tensao": "pelo teste da compensação de tensão",
                "decimacao": "pelo teste da decimação (50 Hz com ZOH)"}[detetor]
        c.ok(f"[§7] mutação de FONTE «{desc}» ({ficheiro}) é APANHADA {quem}", apanhada, motivo if apanhada else "NÃO FOI APANHADA")
    c.ok(f"[§7] {apanhadas}/{len(MUTACOES)} mutantes da fonte C++ compilados e apanhados em {time.perf_counter() - t0:.0f} s (o enunciado pede ≥ 5)", apanhadas == len(MUTACOES), "")


# ============================================================================================ main
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--rapido", action="store_true", help="sem §7 (mutações) e com menos passos de estresse")
    p.add_argument("--secoes", default="0,1,2,3,4,5,6,7", help="secções a correr (ex.: 0,2,4)")
    args = p.parse_args(argv)
    quer = {int(x) for x in args.secoes.split(",")}
    global PASSOS_ESTRESSE
    if args.rapido:
        PASSOS_ESTRESSE = 600_000
    t0 = time.perf_counter()
    c = tn.Checagens("cascata")
    tmp = Path(tempfile.mkdtemp(prefix="teste_cascata_"))
    try:
        bib = sitl.biblioteca_padrao()
        dados = ac.carregar_rl_dados()
        u_yaw = an.u_yaw_identificado(dados)
        env = ac.criar_env(dados, dr=False, episodio_s=1.0)
        gn = cc.ganhos_de_hardware(env, u_yaw_por_taxa=u_yaw, altura_min=VOO_Z_MIN - ac.deslocamento_sensor_cm(env))
        camera = {"largura": 320, "altura": 240, "fovy_graus": float(env.model.cam_fovy[env.model.camera("fpv").id]), "atraso_s": 0.116}
        cfg = sitl.config_de_hardware(env.hw, env.model, env.dt, env=env, ganhos=gn, estimador_classico=True, camera=camera, bib=bib)
        cfg_bin = tmp / "cfg_cascata.bin"
        cfg_bin.write_bytes(bytes(cfg))
        ctx = {"env": env, "gn": gn, "cfg": cfg, "u_yaw": u_yaw}
        gravacoes: dict = {}
        if quer & {4, 7}:
            print("== gravação do protótipo Python (voos de 60 s com o cenário de manobras)", flush=True)
            for nome, kw in (("nominal", {"seed": 5000}), ("outra_semente", {"seed": 5001}), ("dr", {"seed": 5002, "dr": True, "T": 40.0})):
                gravacoes[nome] = gravar_python(dados, u_yaw, **kw)
                print(f"   {nome}: {gravacoes[nome]['decisoes']} decisões, {len(gravacoes[nome]['log_est'])} eventos do estimador", flush=True)
            ctx["cfg_de"] = lambda g: config_de(g, bib)
            ctx["cfg_golden"] = config_de(gravacoes["nominal"], bib)
        if 0 in quer:
            print("§0 — regras de firmware, constantes na Config, paridade de nomes", flush=True)
            secao_regras(c)
        if 1 in quer:
            print("§1 — compilação no host + estresse ASan/UBSan da interface 2", flush=True)
            secao_host(c, tmp, cfg_bin)
        info_cruz: dict = {}
        if 2 in quer:
            print("§2 — compilação cruzada Cortex-M4/M7 do núcleo completo", flush=True)
            info_cruz = secao_cruzada(c, tmp)
        if 3 in quer:
            print("§3 — layout, Config, compensação de tensão, compatibilidade v1", flush=True)
            secao_layout(c, tmp, bib, ctx)
        if 4 in quer:
            print("§4 — equivalência C++ ≡ Python (golden vectors)", flush=True)
            secao_equivalencia(c, bib, ctx, gravacoes)
        if 5 in quer:
            print("§5 — malha fechada com o MuJoCo (C++ vs Python; modos; OLHAR com frames renderizados)", flush=True)
            secao_malha(c, u_yaw, args.rapido)
            secao_olhar(c, u_yaw, dados)
        info_alvo: dict = {}
        if 6 in quer:
            print("§6 — no alvo: QEMU Cortex-M4/M7 bit a bit, instruções e ciclos", flush=True)
            info_alvo = secao_alvo(c, tmp, args.rapido)
        if 7 in quer and not args.rapido:
            print("§7 — mutações da fonte C++", flush=True)
            secao_mutacoes(c, tmp, bib, ctx, gravacoes["nominal"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, falhas = len(c.linhas), c.falhas
    print(f"\n[teste] {n - len(falhas)}/{n} checagens OK ({time.perf_counter() - t0:.0f} s)")
    if info_cruz:
        for cpu, m in info_cruz.items():
            print(f"        {cpu}: nucleo.o -Os text {m['os']['text']} B · -O2 {m['o2']['text']} B · RAM da instância {m['ram_nucleo']} B")
    if info_alvo and "instrucoes" in info_alvo:
        print("        instruções/passo:", json.dumps(info_alvo["instrucoes"]))
    for f in falhas:
        print(f"[teste] FALHOU: {f}")
    if not falhas:
        print("[teste] a cascata clássica + o estimador clássico + o olhar em C++ float32 sem heap equivalem ao protótipo Python (golden vectors e malha fechada), "
              "voam o MuJoCo, correm bit a bit iguais em Cortex-M4/M7 (QEMU) e o teste apanha as mutações")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
