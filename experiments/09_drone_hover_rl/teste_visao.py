#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_visao.py — PROVA da ATIVIDADE C: «olhar para o círculo» em CLÁSSICO e em C++ de firmware.

O dono decidiu (2026-10-12) que estabilização/rotação/movimento são algoritmos clássicos num Arduino e a IA só entra
onde a medição o exigir. Esta atividade é a parte VISUAL: um detetor de círculo sobre um frame monocromático
(`firmware/nucleo/visao.hpp`), o estimador do alvo com compensação do atraso da câmara (`alvo.hpp`: α-β / KF-CV /
KF-CA + histórico de atitude) e a lei de servo visual IBVS + máquina de estados de perda (`ibvs.hpp`), tudo C++17
`float` sem heap (as MESMAS regras do núcleo) a correr em SITL (`sitl_visao.py`, ctypes) e a compilar para
Cortex-M4/M7. O que se prova:

  §0 REGRAS DE FIRMWARE no código (sem `double`/`new`/`malloc`/`std::`/exceções/RTTI, só <stdint.h>/<math.h>,
     literais `float`) — e o auditor TEM DENTES;
  §1 COMPILAÇÃO no host: g++/clang++ -O0/-Os/-O2/-O3 e C++11…20 com -Wall -Wextra -Wdouble-promotion -Werror
     (+ -Wshadow -Wconversion), cabeçalhos auto-suficientes, flags com dentes; ESTRESSE com ASan+UBSan
     (`firmware/teste/estresse_visao.cpp`: frames de tamanho exato com ruído/píxeis quentes/tabuleiros/discos,
     janelas e parâmetros hostis, relógio com voltas/saltos, atitude NaN/inf, câmara com lixo);
  §2 COMPILAÇÃO CRUZADA `clang --target=thumbv7em-none-eabihf -ffreestanding -Os` (Cortex-M4 e M7): tamanho, RAM
     em .bss, símbolos só `sinf cosf atan2f sqrtf` + mem*, sem heap/double/divisão de biblioteca; e a ESTIMATIVA
     DE CICLOS Cortex-M7 por frame com `llvm-mca -mcpu=cortex-m7` sobre os laços do objeto cross-compilado;
  §3 LAYOUT (structs de ctypes geradas do `visao_tipos.hpp` ≡ sizeof do C++) e validação de Configs;
  §4 DETETOR sobre frames RENDERIZADOS (MuJoCo EGL, câmara à frente do corpo, esfera branca, luma BT.601 como a
     Portenta Vision Shield) a 160×120 e 320×240: erro de localização vs a projeção EXATA do simulador (sem ruído
     e com ruído gaussiano), desfoque, vinheta, saturação, píxeis quentes/mortos, distrator alongado rejeitado
     (sozinho e ao lado do alvo), janela de busca, alvo cortado pelo FOV, sem alvo, falsos positivos, tempo no
     host e ciclos M7;
  §5 ESTIMADOR sob atraso de 116 ms COM o drone a rodar (ψ roteirizado): erro de previsão de α-β / KF-CV / KF-CA em
     «círculo» e «oito» (as leis de `env_real.definir_trajetoria_ponto`, 0,3–0,8 m/s) vs «sem previsão» e «sem
     desrodar»; relógio perto da volta de 2³²;
  §6 LEI IBVS: margens de fase (≥ 45° com τ_yaw 0,3–0,6 s e atraso ±50 ms), laço fechado com planta cinemática
     (yaw 2.ª ordem + lag de velocidade, câmara com atraso): centra alvo estático, segue círculo/oito, FF reduz o
     erro, v_z desrodado de pitch/roll, perda → procura → reaquisição com histerese, limites/slew, determinismo,
     saneamento de NaN;
  §7 MUTAÇÕES: a FONTE C++ mutada (sinal do yaw, atraso ignorado, gate de circularidade, FF, desrotação…) é
     compilada de verdade e o teste TEM de a apanhar; o C++ intacto passa o mesmo critério (controlo).

NÃO fecha laço com o simulador completo (a cascata de voo ainda não existe em C++): a planta do §6 é cinemática e
declara-se como tal; o teste de laço fechado completo fica para a integração.

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_visao.py
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_visao.py --rapido   # sem §7 (mutações)

Exit 0 = tudo verde; 1 = alguma checagem falhou (ou falta uma ferramenta: falha ALTO, nunca salta).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import contextlib
import ctypes
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("MUJOCO_GL", "egl")

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

import numpy as np
import sitl_visao as sv

FIRMWARE_DIR = sv.FIRMWARE_DIR
NUCLEO_DIR = sv.NUCLEO_DIR
CROSS_DIR = FIRMWARE_DIR / "cross"
ESTRESSE_CPP = FIRMWARE_DIR / "teste" / "estresse_visao.cpp"
FICHEIROS_C = ("visao_tipos.hpp", "visao.hpp", "alvo.hpp", "ibvs.hpp", "capi_visao.cpp")
VERIFICA_CPP = CROSS_DIR / "verifica_visao.cpp"
PASSOS_ESTRESSE_DET, PASSOS_ESTRESSE_SEG = 20000, 400

# FoV vertical do HM0360 da Portenta Vision Shield (módulo de referência da Himax: 55,4° V) — vem do emulador
# `lab/camera_rpi.py` (fonte única); cai para o valor da ficha se o emulador não tiver o módulo Arduino.
FOVY_HM0360_FALLBACK = 55.4


class Checagens:
    def __init__(self, titulo: str) -> None:
        self.titulo, self.linhas, self.falhas = titulo, [], []

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.linhas.append(nome)
        if not cond:
            self.falhas.append(nome)
        print(f"        [{'OK  ' if cond else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""), flush=True)
        return bool(cond)


# ============================================================================================ ferramentas
def _ferramenta(nome: str, *alternativas: str) -> str:
    for n in (nome, *alternativas):
        caminho = shutil.which(n)
        if caminho:
            return caminho
    raise FileNotFoundError(f"ferramenta em falta: {nome} (o teste exige-a; não salta)")


def _correr(cmd: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, check=False, **kw)


# ============================================================================================ §0 auditoria
def _sem_comentarios_e_strings(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", " ", texto, flags=re.DOTALL)
    texto = re.sub(r"//[^\n]*", " ", texto)
    return re.sub(r'"(?:\\.|[^"\\])*"', '""', texto)


# regra → regex (aplicada ao código sem comentários/strings) — as MESMAS do teste_nucleo.py
REGRAS_PROIBIDAS = {
    "double (só float)": r"\bdouble\b",
    "long double": r"\blong\s+double\b",
    "alocação dinâmica (new/delete)": r"\b(new|delete)\b",
    "malloc/calloc/realloc/free/alloca": r"\b(malloc|calloc|realloc|free|alloca)\s*\(",
    "biblioteca padrão C++ (std::)": r"\bstd\s*::",
    "exceções": r"\b(throw|try|catch|noexcept)\b",
    "RTTI": r"\b(typeid|dynamic_cast)\b",
    "virtual (sem vtables)": r"\bvirtual\b",
    "literal de ponto flutuante sem sufixo f (double)":
        r"(?<![\w.])(?:\d+\.\d*|\.\d+|\d+(?:\.\d*)?[eE][-+]?\d+)(?![\dfFeE.\w])",
    "include além de <stdint.h>/<math.h>/próprios": r'#\s*include\s*<(?!stdint\.h>|math\.h>)',
}


def auditar_texto(texto: str) -> list[str]:
    limpo = _sem_comentarios_e_strings(texto)
    achados = []
    for regra, rx in REGRAS_PROIBIDAS.items():
        for m in re.finditer(rx, limpo):
            achados.append(f"{regra}: «{limpo[max(0, m.start() - 20):m.end() + 20].strip()}»")
    return achados


def secao_regras(c: Checagens) -> None:
    ficheiros = [NUCLEO_DIR / n for n in FICHEIROS_C] + [VERIFICA_CPP]
    ausentes = [f.name for f in ficheiros if not f.is_file()]
    violacoes = {f.name: auditar_texto(f.read_text(encoding="utf-8")) for f in ficheiros if f.is_file()}
    violacoes = {k: v for k, v in violacoes.items() if v}
    c.ok("[§0] os ficheiros da atividade C cumprem as regras de firmware (sem double/new/malloc/std::/exceções/RTTI/"
         "virtual, só <stdint.h>/<math.h>, literais float)", not violacoes and not ausentes,
         f"{len(ficheiros)} ficheiros auditados" if not (violacoes or ausentes) else str(violacoes or ausentes))
    injetados = {
        "double": "float f(float x) { double y = x; return (float)y; }",
        "literal sem f": "float f(float x) { return x * 0.5; }",
        "expoente sem f": "const float k = 1e-3;",
        "new": "int* f() { return new int[4]; }",
        "malloc": "void* f() { return malloc(8); }",
        "std::": "#include <stdint.h>\nstd::size_t n;",
        "include <vector>": "#include <vector>\n",
        "throw": "void f() { throw 1; }",
        "virtual": "struct A { virtual void f() = 0; };",
    }
    mudos = [k for k, v in injetados.items() if not auditar_texto(v)]
    c.ok("[§0] o auditor TEM DENTES: apanha double, literal sem `f`, new, malloc, std::, include extra, throw e "
         "virtual injetados", not mudos, f"não apanhou: {mudos}" if mudos else f"{len(injetados)}/{len(injetados)}")
    limpos = ["float f(float x) { return x * 0.5f + 1e-3f; }  // double new malloc em comentário",
              'const char* s = "double new malloc";', "constexpr float k = 3.14159265358979323846f;"]
    falsos = [t for t in limpos if auditar_texto(t)]
    c.ok("[§0] o auditor não dá falsos positivos (literais com `f`, comentários e strings)", not falsos, str(falsos))


# ============================================================================================ §1 host
FLAGS_AVISOS = ["-Wall", "-Wextra", "-Wdouble-promotion", "-Werror"]
FLAGS_EXTRA = ["-Wshadow", "-Wfloat-conversion", "-Wconversion", "-Wundef", "-Wcast-qual"]
FLAGS_SANITIZERS = ["-std=c++17", "-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    "-fno-omit-frame-pointer", *FLAGS_AVISOS]


def _compilar_host(cxx: str, fonte: Path, saida: Path, opt: str, extra=(), std: str = "c++17") -> subprocess.CompletedProcess:
    return _correr([cxx, f"-std={std}", opt, "-fno-exceptions", "-fno-rtti", *FLAGS_AVISOS, *extra,
                    "-I", FIRMWARE_DIR, "-c", fonte, "-o", saida])


def compilar_estresse(cxx: str, raiz_firmware: Path, exe: Path) -> subprocess.CompletedProcess:
    """Compila o driver de estresse (a fonte do núcleo de visão é só cabeçalhos) com ASan+UBSan."""
    return _correr([cxx, *FLAGS_SANITIZERS, "-I", raiz_firmware, ESTRESSE_CPP, "-o", exe])


def correr_estresse(exe: Path, n_det: int = PASSOS_ESTRESSE_DET, n_seg: int = PASSOS_ESTRESSE_SEG) -> dict:
    r = _correr([exe, str(n_det), str(n_seg)])
    m = re.search(r"violações (\d+) · frames (\d+) · deteções válidas (\d+) · passos do seguidor (\d+) · estados "
                  r"(\d+)/(\d+)/(\d+)/(\d+) · falhas numéricas sinalizadas (\d+) · configs recusadas (\d+)", r.stdout)
    if m is None:
        return {"ok": False, "erro": (r.stderr.strip().splitlines() or [r.stdout[:80]])[0][:200]}
    v = [int(x) for x in m.groups()]
    return {"ok": r.returncode == 0 and v[0] == 0, "violacoes": v[0], "frames": v[1], "validas": v[2],
            "passos": v[3], "estados": v[4:8], "falhas": v[8], "recusadas": v[9], "erro": ""}


def secao_host(c: Checagens, tmp: Path) -> None:
    gpp, clangpp = _ferramenta("g++"), _ferramenta("clang++")
    cpps = [NUCLEO_DIR / "capi_visao.cpp", VERIFICA_CPP]
    trabalhos = [(cxx, f, opt, FLAGS_EXTRA if cxx == gpp else []) for cxx in (gpp, clangpp)
                 for opt in ("-O0", "-Os", "-O2", "-O3") for f in cpps]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        resultados = list(ex.map(lambda a: _compilar_host(a[0], a[1], tmp / f"h_{id(a)}.o", a[2], a[3]),
                                 [t for t in trabalhos]))
    falhas = [(Path(t[0]).name, t[1].name, t[2], r.stderr.strip().splitlines()[:2])
              for t, r in zip(trabalhos, resultados, strict=True) if r.returncode != 0]
    c.ok("[§1] o detetor, o estimador e o seguidor compilam no host com -Wall -Wextra -Wdouble-promotion -Werror "
         "(g++ e clang++, -O0/-Os/-O2/-O3; g++ também com " + " ".join(FLAGS_EXTRA) + ")", not falhas,
         f"{len(trabalhos)} compilações" if not falhas else str(falhas))
    padroes = ("c++11", "c++14", "gnu++14", "c++17", "c++20")
    jobs = [(cxx, f, std) for cxx in (gpp, clangpp) for std in padroes for f in cpps]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        res_std = list(ex.map(lambda a: _compilar_host(a[0], a[1], tmp / f"s_{id(a)}.o", "-O2", (), a[2]), jobs))
    ruins = [(Path(j[0]).name, j[2], j[1].name) for j, r in zip(jobs, res_std, strict=True) if r.returncode != 0]
    c.ok(f"[§1] compilam em {', '.join(padroes)} (g++ e clang++) — o core Arduino mbed usa gnu++14", not ruins,
         f"{len(jobs)} compilações" if not ruins else str(ruins))
    mal = []
    for nome in FICHEIROS_C:
        if not nome.endswith(".hpp"):
            continue
        tu = tmp / f"auto_{nome}.cpp"
        tu.write_text(f'#include "{(NUCLEO_DIR / nome).resolve()}"\n', encoding="utf-8")
        r = _correr([gpp, "-std=c++17", "-fsyntax-only", "-fno-exceptions", "-fno-rtti", *FLAGS_AVISOS,
                     "-I", FIRMWARE_DIR, tu])
        if r.returncode != 0:
            mal.append((nome, r.stderr.strip().splitlines()[:1]))
    c.ok("[§1] cada cabeçalho (visao_tipos, visao, alvo, ibvs) é auto-suficiente (compila sozinho)", not mal, str(mal))
    sujo = tmp / "dentes.cpp"
    sujo.write_text("float f(float x) { return x * 0.5; }\n", encoding="utf-8")
    r = _correr([gpp, "-std=c++17", "-O2", "-Wdouble-promotion", "-Werror", "-c", sujo, "-o", tmp / "dentes.o"])
    r2 = _correr([clangpp, "-std=c++17", "-O2", "-Wdouble-promotion", "-Werror", "-c", sujo, "-o", tmp / "d2.o"])
    c.ok("[§1] -Wdouble-promotion -Werror TEM DENTES: `x * 0.5` faz o g++ e o clang++ falhar",
         r.returncode != 0 and "double-promotion" in r.stderr and r2.returncode != 0)
    # ESTRESSE com sanitizers
    for cxx in (gpp, clangpp):
        exe = tmp / f"estresse_{Path(cxx).name}"
        rc = compilar_estresse(cxx, FIRMWARE_DIR, exe)
        if rc.returncode != 0:
            c.ok(f"[§1] estresse com ASan+UBSan ({Path(cxx).name}): compila", False, rc.stderr[:300])
            continue
        e = correr_estresse(exe)
        c.ok(f"[§1] ESTRESSE com ASan+UBSan ({Path(cxx).name}): {PASSOS_ESTRESSE_DET} frames hostis + "
             f"{PASSOS_ESTRESSE_SEG}×2500 passos do seguidor — sem UB/OOB, saídas finitas, comando dentro dos limites, "
             "Deteccao coerente (gates cumpridos) e os 4 estados alcançados",
             e["ok"] and e.get("validas", 0) > 0 and e.get("falhas", 0) > 0 and e.get("recusadas", 0) > 0
             and all(x > 0 for x in e.get("estados", [0])),
             (f"violações {e['violacoes']} · deteções válidas {e['validas']} · estados {e['estados']} · falhas "
              f"numéricas sinalizadas {e['falhas']} · configs recusadas {e['recusadas']}") if e["ok"] or "violacoes" in e
             else e["erro"])


# ============================================================================================ §2 cruzada
CPUS = {
    "Cortex-M4 (Nano 33 BLE, nRF52840)": ("cortex-m4", "fpv4-sp-d16"),
    "Cortex-M7 (H747/Portenta/Nicla/GIGA)": ("cortex-m7", "fpv5-d16"),
}
FLAGS_CROSS = ["--target=thumbv7em-none-eabihf", "-ffreestanding", "-fno-exceptions", "-fno-rtti", "-Os",
               "-Wall", "-Wextra", "-Wdouble-promotion", "-Werror", "-std=c++17"]
LIBM_PERMITIDA = {"sinf", "cosf", "atan2f", "sqrtf"}
RUNTIME_PERMITIDO = re.compile(r"^(__aeabi_mem(cpy|move|set|clr)[48]?|mem(cpy|set|move))$")
SIMBOLOS_PROIBIDOS = re.compile(
    r"(malloc|calloc|realloc|^free$|_Znw|_Zna|_Zdl|_Zda|__cxa|__gxx|_Unwind|__aeabi_unwind|_ZTI|_ZTV|_ZTS"
    r"|__dso_handle|atexit|__aeabi_(d|f2d|i2d|ui2d|l2d|ul2d)|__fixd|__floatd|cxa_guard"
    r"|__aeabi_l|__aeabi_u?idiv|__aeabi_u?ldiv)")
SECOES_PROIBIDAS = re.compile(r"^\.(init_array|ctors|fini_array|dtors|eh_frame|gcc_except_table|ARM\.extab)")


def compilar_cruzado(clang: str, cpu: tuple, fonte: Path, saida: Path, extra=(), opt: str | None = None,
                     asm: bool = False) -> subprocess.CompletedProcess:
    mcpu, mfpu = cpu
    flags = [f for f in FLAGS_CROSS if not (opt and f == "-Os")] + ([opt] if opt else [])
    return _correr([clang, *flags, f"-mcpu={mcpu}", f"-mfpu={mfpu}", *extra, "-I", FIRMWARE_DIR, "-isystem", CROSS_DIR,
                    "-S" if asm else "-c", fonte, "-o", saida])


def medir_objeto(llvm_size: str, obj: Path) -> dict:
    linha = _correr([llvm_size, "-B", obj]).stdout.strip().splitlines()[-1].split()
    return {"text": int(linha[0]), "data": int(linha[1]), "bss": int(linha[2])}


def verificar_objeto(llvm_nm: str, llvm_objdump: str, obj: Path, firmware: bool) -> dict:
    indef = [ln.split()[-1] for ln in _correr([llvm_nm, "-u", obj]).stdout.splitlines() if ln.strip()]
    todos = [ln.split()[-1] for ln in _correr([llvm_nm, obj]).stdout.splitlines() if ln.strip()]
    proibidos = sorted({s for s in indef + todos if SIMBOLOS_PROIBIDOS.search(s)})
    estranhos = sorted(s for s in indef if s not in LIBM_PERMITIDA and not RUNTIME_PERMITIDO.match(s)) if firmware else []
    dis = _correr([llvm_objdump, "-dr", obj]).stdout
    f64 = len(re.findall(r"\.f64\b", dis))
    secoes = [ln.split()[1] for ln in _correr([llvm_objdump, "-h", obj]).stdout.splitlines()
              if re.match(r"^\s*\d+\s+\S", ln)]
    return {"indefinidos": sorted(set(indef)), "proibidos": proibidos, "estranhos": estranhos, "f64": f64,
            "secoes_ruins": sorted({s for s in secoes if SECOES_PROIBIDAS.match(s)})}


# ----------------------------------------------------------------------------- ciclos M7 (llvm-mca)
# Kernels do detetor, por ordem de custo por píxel. O TU de análise compila com -DNUCLEO_VISAO_NOINLINE para que
# cada um fique numa função própria; extrai-se o laço interno do assembly e o llvm-mca (modelo do Cortex-M7:
# dual-issue, latências de carga) dá os ciclos por iteração em regime.
TU_MCA = """\
#include "nucleo/ibvs.hpp"
#include "nucleo/visao.hpp"
using namespace nucleo::visao;
extern "C" {
int32_t w_max(const uint8_t* p, int32_t n) { return detalhe::k_max_robusto(p, n); }
int32_t w_grelha(const uint8_t* p, int32_t n, int32_t* d) { return detalhe::k_soma_grelha(p, n, d); }
int32_t w_saltar(const uint8_t* p, int32_t x, int32_t x1, int32_t t) { return detalhe::k_saltar(p, x, x1, t); }
int32_t w_run(const uint8_t* p, int32_t x, int32_t x1, int32_t t, int32_t* a, int32_t* b) {
    return detalhe::k_run(p, x, x1, t, a, b);
}
Deteccao w_detetar(Detetor* d, const uint8_t* f, int32_t w, int32_t h, const ParamsDetetor* p) {
    return d->detetar(f, w, h, 0, *p);
}
SaidaSeguidor w_passo(Seguidor* s, uint32_t t, const Atitude* a, const Camera* c) { return s->passo(t, *a, *c); }
}
"""
KERNELS_LACO = {"max_robusto": r"k_max_robusto", "grelha": r"k_soma_grelha", "saltar": r"k_saltar", "run": r"k_run"}
KERNELS_FUNCAO = {"novo_run": r"novo_run", "fim_de_linha": r"fim_de_linha", "avaliar": r"avaliar"}
# ASSUMIDO (newlib-nano float em Cortex-M4/M7, ordem de grandeza publicada; sem medição aqui): ciclos por chamada de libm
CICLOS_LIBM = {"sinf": 110.0, "cosf": 110.0, "atan2f": 220.0, "sqrtf": 30.0}
# funções chamadas dentro de um ciclo `for` sobre os 3 canais do filtro (o nº de chamadas estáticas conta 1)
MULTIPLICIDADE = {"propagar": 3, "atualizar_canal": 3, "copiar": 3}
CICLOS_SQRTF = 30.0          # ASSUMIDO: `bl sqrtf` (libm do newlib sobre vsqrt.f32: 14–16 ciclos + chamada) ≈ 30


def _funcao_asm(asm: str, padrao: str) -> list[str]:
    """Linhas do corpo da função cujo símbolo C++ contém `padrao` (do rótulo até `.Lfunc_end`)."""
    linhas = asm.splitlines()
    ini = next((i for i, ln in enumerate(linhas) if re.match(rf"^_ZN[\w]*{padrao}[\w]*:", ln)), None)
    if ini is None:
        return []
    fim = next((i for i in range(ini + 1, len(linhas)) if linhas[i].startswith(".Lfunc_end")), len(linhas))
    return linhas[ini + 1:fim]


def _so_instrucoes(corpo: list[str]) -> list[str]:
    out = []
    for ln in corpo:
        t = ln.split("@")[0].rstrip()
        if not t.strip() or t.strip().startswith(".") and not t.strip().startswith(".LBB") or t.strip().endswith(":"):
            continue
        out.append(t)
    return out


def _lacos_internos(corpo: list[str]) -> list[list[str]]:
    """Corpos dos laços internos (rótulo com o comentário «Inner Loop Header» até ao ramo de volta)."""
    lacos = []
    for i, ln in enumerate(corpo):
        m = re.match(r"^(\.LBB\d+_\d+):.*Inner Loop Header", ln)
        if not m:
            continue
        rotulo = m.group(1)
        j = next((k for k in range(i + 1, len(corpo)) if re.search(rf"\bb\w*\s+{rotulo}\b", corpo[k])), None)
        if j is not None:
            lacos.append(_so_instrucoes(corpo[i + 1:j + 1]))
    return lacos


def _mca(llvm_mca: str, instrucoes: list[str], iteracoes: int, tmp: Path, nome: str) -> dict:
    ficheiro = tmp / f"mca_{nome}.s"
    ficheiro.write_text("\n".join(instrucoes) + "\n", encoding="utf-8")
    r = _correr([llvm_mca, "-mtriple=thumbv7em-none-eabihf", "-mcpu=cortex-m7", f"-iterations={iteracoes}",
                 "-skip-unsupported-instructions=lack-sched", ficheiro])
    m = re.search(r"Total Cycles:\s+(\d+)", r.stdout)
    n = re.search(r"Instructions:\s+(\d+)", r.stdout)
    if m is None or n is None:
        raise RuntimeError(f"llvm-mca falhou em {nome}: {r.stderr[:300]}")
    return {"ciclos_total": int(m.group(1)), "instrucoes": int(n.group(1)) // iteracoes,
            "ciclos_iter": int(m.group(1)) / iteracoes}


def ciclos_m7(clang: str, llvm_mca: str, tmp: Path, opt: str) -> dict:
    """Ciclos por unidade de trabalho do detetor no Cortex-M7 (estimativa estática do llvm-mca, caches ideais).

    Devolve `{kernel: ciclos}` — por píxel para os 4 laços, por chamada para novo_run/fim_de_linha/avaliar (limite
    SUPERIOR: o corpo inteiro como código reto) — mais o `.s` com que se mediu.
    """
    tu = tmp / f"mca_tu_{opt}.cpp"
    tu.write_text(TU_MCA, encoding="utf-8")
    asm = tmp / f"mca_tu_{opt}.s"
    cpu = CPUS["Cortex-M7 (H747/Portenta/Nicla/GIGA)"]
    r = compilar_cruzado(clang, cpu, tu, asm, extra=("-DNUCLEO_VISAO_NOINLINE",), opt=opt, asm=True)
    if r.returncode != 0:
        raise RuntimeError(f"compilar TU de análise: {r.stderr[:300]}")
    texto = asm.read_text(encoding="utf-8")
    saida: dict = {"opt": opt}
    for nome, pad in KERNELS_LACO.items():
        corpo = _funcao_asm(texto, pad)
        lacos = _lacos_internos(corpo)
        if not corpo or not lacos:
            raise RuntimeError(f"não encontrei o laço de {nome} no assembly")
        cands = []
        for i, lc in enumerate(lacos):
            m = _mca(llvm_mca, lc, 400, tmp, f"{nome}_{opt}_{i}")
            m["px_iter"] = max(1, sum(1 for ln in lc if re.search(r"\bldrb", ln)))   # píxeis lidos por iteração
            m["ciclos_px"] = m["ciclos_iter"] / m["px_iter"]
            cands.append(m)
        melhor = max(cands, key=lambda d: d["ciclos_px"])
        saida[nome] = melhor["ciclos_px"]
        saida[f"{nome}_instr"] = melhor["instrucoes"]
        saida[f"{nome}_px_iter"] = melhor["px_iter"]
    for nome, pad in KERNELS_FUNCAO.items():
        corpo = _so_instrucoes(_funcao_asm(texto, pad))
        if not corpo:
            raise RuntimeError(f"não encontrei a função {nome} no assembly")
        n_sqrt = sum(1 for ln in corpo if re.search(r"\bbl\s+sqrtf\b", ln))
        m = _mca(llvm_mca, corpo, 1, tmp, f"{nome}_{opt}")
        saida[nome] = m["ciclos_total"] + CICLOS_SQRTF * n_sqrt
        saida[f"{nome}_instr"] = m["instrucoes"]
    saida["seguidor"] = custo_seguidor_m7(texto, llvm_mca, tmp, opt)
    return saida


def custo_seguidor_m7(texto_asm: str, llvm_mca: str, tmp: Path, opt: str) -> dict:
    """Custo do `Seguidor::passo` no Cortex-M7 pelo GRAFO DE CHAMADAS do objeto de análise: cada função emitida vale o
    llvm-mca do seu corpo como código reto (limite SUPERIOR: conta os dois lados de cada `if`), mais as chamadas
    (estáticas, × MULTIPLICIDADE nos ciclos sobre os 3 canais) e a libm assumida (CICLOS_LIBM). É o pior caso — o passo em
    que chega um frame novo (desrota, filtra, prevê, controla)."""
    corpos: dict[str, list[str]] = {}
    nome = None
    for ln in texto_asm.splitlines():
        m = re.match(r"^(_Z\w+|w_\w+):", ln)
        if m:
            nome, corpos[m.group(1)] = m.group(1), []
        elif ln.startswith(".Lfunc_end"):
            nome = None
        elif nome is not None:
            corpos[nome].append(ln)
    custo_base: dict[str, float] = {}
    chamadas: dict[str, dict[str, int]] = {}
    for nm, corpo in corpos.items():
        ins = _so_instrucoes(corpo)
        if not ins:
            continue
        custo_base[nm] = _mca(llvm_mca, ins, 1, tmp, f"cg_{abs(hash(nm)) % 10**8}_{opt}")["ciclos_total"]
        chamadas[nm] = {}
        for alvo in re.findall(r"\b(?:bl|b\.w)\s+(\w+)", "\n".join(ins)):
            chamadas[nm][alvo] = chamadas[nm].get(alvo, 0) + 1
    raiz = next(nm for nm in corpos if "Seguidor5passo" in nm)
    libm_total: dict[str, int] = {}

    def custo(nm: str, mult: int, visitados: tuple) -> float:
        total = custo_base.get(nm, 0.0) * mult
        for alvo, n in chamadas.get(nm, {}).items():
            if alvo in CICLOS_LIBM:
                total += CICLOS_LIBM[alvo] * n * mult
                libm_total[alvo] = libm_total.get(alvo, 0) + n * mult
            elif alvo in custo_base and alvo not in visitados:
                m_ = next((v for k, v in MULTIPLICIDADE.items() if k in alvo), 1)
                total += custo(alvo, mult * n * m_, (*visitados, nm))
        return total
    ciclos = custo(raiz, 1, ())
    return {"ciclos": ciclos, "libm": libm_total, "funcoes": len(custo_base), "opt": opt}


def estimar_frame(k: dict, largura: int, altura: int, n_acima: int, n_runs: int, n_blobs: int = 1,
                  paso: int = 1) -> dict:
    """Ciclos M7 de um frame: 1.ª passagem (máx + grelha) + varrimento + runs + blobs. `n_acima` = píxeis ≥ limiar,
    `n_runs` = runs; cada chamada de salto/run paga ~12 ciclos de entrada/saída do laço (ASSUMIDO)."""
    n_px = largura * altura
    chamadas = n_runs + altura
    ciclos = {
        "1ª passagem (máx robusto)": (altura // paso) * (largura * k["max_robusto"] + 12),
        "1ª passagem (fundo, grelha 8×8)": ((altura + 7) // 8) * (((largura + 7) // 8) * k["grelha"] + 12),
        "2ª passagem (saltar fundo)": (n_px - n_acima) * k["saltar"] + chamadas * 12,
        "2ª passagem (runs)": n_acima * k["run"] + n_runs * 12,
        "novo_run": n_runs * k["novo_run"],
        "fim_de_linha": altura * k["fim_de_linha"],
        "avaliar": n_blobs * k["avaliar"],
    }
    ciclos["total"] = sum(ciclos.values())
    return ciclos


def secao_cruzada(c: Checagens, tmp: Path) -> dict:
    clang = _ferramenta("clang++", "clang")
    llvm_size, llvm_nm, llvm_objdump, llvm_mca = (_ferramenta(n) for n in ("llvm-size", "llvm-nm", "llvm-objdump",
                                                                          "llvm-mca"))
    info: dict = {"tamanhos": {}, "mca": {}}
    for placa, cpu in CPUS.items():
        o = tmp / f"vv_{cpu[0]}.o"
        r = compilar_cruzado(clang, cpu, VERIFICA_CPP, o)
        c.ok(f"[§2] {placa}: a cadeia de visão (detetor → Camera → seguidor → janela) compila com clang "
             f"--target=thumbv7em-none-eabihf -ffreestanding -fno-exceptions -fno-rtti -Os -Wall -Wextra "
             f"-Wdouble-promotion -Werror -mcpu={cpu[0]} -mfpu={cpu[1]}", r.returncode == 0, r.stderr.strip()[:300])
        if r.returncode != 0:
            continue
        r14 = _correr([clang, *[f for f in FLAGS_CROSS if f != "-std=c++17"], "-std=gnu++14", f"-mcpu={cpu[0]}",
                       f"-mfpu={cpu[1]}", "-I", FIRMWARE_DIR, "-isystem", CROSS_DIR, "-c", VERIFICA_CPP,
                       "-o", tmp / f"vv14_{cpu[0]}.o"])
        c.ok(f"[§2] {placa}: o mesmo código compila com -std=gnu++14 (o dialeto por omissão do core Arduino mbed)",
             r14.returncode == 0, r14.stderr.strip()[:200])
        m = medir_objeto(llvm_size, o)
        info["tamanhos"][cpu[0]] = m
        c.ok(f"[§2] {placa}: tamanho = text {m['text']} B · data {m['data']} B · bss {m['bss']} B (as instâncias "
             "globais Detetor+Seguidor caem em .bss, sem imagem em flash)",
             m["text"] > 0 and m["data"] == 0 and 2000 < m["bss"] < 40000,
             f"RAM do estado {m['bss']} B (+ o frame: 76 800 B em QVGA, 19 200 B em QQVGA)")
        v = verificar_objeto(llvm_nm, llvm_objdump, o, firmware=True)
        c.ok(f"[§2] {placa}: SEM malloc/new/__cxa_*/typeinfo/vtables/atexit/double/divisão de biblioteca (llvm-nm) e "
             "sem secções de construtores/exceções", not v["proibidos"] and not v["secoes_ruins"],
             f"proibidos={v['proibidos']} secções={v['secoes_ruins']}")
        c.ok(f"[§2] {placa}: símbolos indefinidos = só libm {sorted(LIBM_PERMITIDA)} + mem* do runtime",
             not v["estranhos"], f"indefinidos = {v['indefinidos']}")
        c.ok(f"[§2] {placa}: nenhuma instrução de double no disassembly (0 × `.f64`)", v["f64"] == 0,
             f"{v['f64']} ocorrências")
    sujo = tmp / "sujo.cpp"
    sujo.write_text(
        'extern "C" void* malloc(unsigned);\nvoid* operator new(unsigned n) { return malloc(n); }\n'
        "struct B { virtual int f() = 0; };\nstruct D : B { int f() override { return 1; } };\n"
        "long long g(long long a, long long b) { D* d = new D; double x = a * 1.5; return a / b + d->f() + (int)x; }\n",
        encoding="utf-8")
    cpu = next(iter(CPUS.values()))
    o = tmp / "sujo.o"
    r = compilar_cruzado(clang, cpu, sujo, o)
    if r.returncode == 0:
        vs = verificar_objeto(llvm_nm, llvm_objdump, o, firmware=True)
        c.ok("[§2] o verificador TEM DENTES: new/malloc, double (soft-float no M4) e divisão de 64 bit são apanhados",
             "_Znwj" in vs["proibidos"] and any(x.startswith("__aeabi_d") for x in vs["proibidos"])
             and "__aeabi_ldivmod" in vs["proibidos"], f"proibidos={vs['proibidos'][:6]} f64={vs['f64']}")
    else:
        c.ok("[§2] o verificador TEM DENTES (objeto sujo compila)", False, r.stderr[:200])
    # ciclos M7: llvm-mca nos laços do objeto cross-compilado
    for opt in ("-Os", "-O2"):
        k = ciclos_m7(clang, llvm_mca, tmp, opt)
        info["mca"][opt] = k
    k_os = info["mca"]["-Os"]
    c.ok("[§2] llvm-mca (-mcpu=cortex-m7) deu ciclos por píxel dos 4 laços do detetor: "
         + " · ".join(f"{n} {k_os[n]:.1f}" for n in KERNELS_LACO) + " ciclos/píxel (-Os); "
         + " · ".join(f"{n} {k_os[n]:.0f}" for n in KERNELS_FUNCAO) + " ciclos/chamada (limite superior)",
         all(0.5 < k_os[n] < 30 for n in KERNELS_LACO) and all(0 < k_os[n] < 5000 for n in KERNELS_FUNCAO),
         "ESTIMATIVA estática (dual-issue, caches e SRAM ideais), não medição")
    sg = info["mca"]["-Os"]["seguidor"]
    passo_us = sg["ciclos"] / 480.0
    c.ok("[§2] CUSTO do SEGUIDOR no Cortex-M7 (ESTIMATIVA do PIOR caso — o passo em que chega um frame —: llvm-mca de cada "
         f"função do grafo de chamadas como código reto, {sg['funcoes']} funções, + libm assumida sinf/cosf 110 · atan2f 220 · "
         f"sqrtf 30 ciclos): {passo_us:.0f} µs por passo = {100 * passo_us / 10000:.2f} % do período a 100 Hz "
         f"({100 * passo_us / 20000:.2f} % a 50 Hz) — chamadas de libm no pior caso: {sg['libm']}",
         0 < passo_us < 0.1 * 10000, "limite superior; sem medição em hardware (DWT->CYCCNT na placa fecha)")
    return info


# ============================================================================================ §3 layout/config
def secao_layout(c: Checagens, tmp: Path, bib) -> None:
    tams = {n: (ctypes.sizeof(getattr(bib, n)), int(getattr(bib.lib, f"visao_tamanho_{k}")()))
            for n, k in (("Camera", "camera"), ("ParamsDetetor", "params_detetor"), ("Deteccao", "deteccao"),
                         ("Atitude", "atitude"), ("ConfigSeguidor", "config_seguidor"),
                         ("SaidaSeguidor", "saida_seguidor"))}
    c.ok("[§3] as structs de ctypes (geradas do visao_tipos.hpp) têm o MESMO sizeof que o C++",
         all(a == b for a, b in tams.values()), " · ".join(f"{k} {a} B" for k, (a, _) in tams.items()))
    mau = tmp / "mau.hpp"
    mau.write_text("struct Camera { float a; double b; };\n", encoding="utf-8")
    try:
        sv.estruturas_do_header(mau)
        estrito = False
    except ValueError:
        estrito = True
    c.ok("[§3] o parser de layout é ESTRITO: um `double` no struct levanta erro (nada diverge em silêncio)", estrito)
    campos = [n for n, _t in bib.Camera._fields_]
    c.ok("[§3] a struct Camera tem exatamente {valido, u, v, raio, n, t} (o contrato com o núcleo de voo)",
         campos == ["valido", "u", "v", "raio", "n", "t"], str(campos))
    campos_cmd = [n for n, _t in bib.ComandoVoo._fields_]
    c.ok("[§3] o comando de saída é {vx, vy, vz, yaw_taxa} (referencial do rumo, yaw em rad/s)",
         campos_cmd == ["vx", "vy", "vz", "yaw_taxa"], str(campos_cmd))

    def recusada(mut) -> bool:
        s = sv.SeguidorCpp(bib=bib, cfg={})
        cfg = bib.ConfigSeguidor.from_buffer_copy(s.cfg)
        mut(cfg)
        nova = sv.SeguidorCpp(bib=bib)
        return int(bib.lib.seguidor_iniciar(nova.id, ctypes.byref(cfg))) == 0
    casos = {"versão errada": lambda k: setattr(k, "versao", k.versao + 1),
             "f_px = NaN": lambda k: setattr(k, "f_px", float("nan")),
             "kp_yaw = inf": lambda k: setattr(k, "kp_yaw", float("inf")),
             "yaw_max = 0": lambda k: setattr(k, "yaw_max", 0.0),
             "t_falta ≤ t_gap": lambda k: setattr(k, "t_falta_s", k.t_gap_s),
             "modelo = 7": lambda k: setattr(k, "modelo", 7),
             "n_reaq = 0": lambda k: setattr(k, "n_reaq", 0),
             "raio_alvo = −1": lambda k: setattr(k, "raio_alvo_m", -1.0),
             "q_ang = 0": lambda k: setattr(k, "q_ang", 0.0)}
    aceites = [n for n, mut in casos.items() if not recusada(mut)]
    c.ok("[§3] iniciar() recusa Configs inválidas (versão, NaN, inf, limite 0, tempos incoerentes, modelo/n_reaq "
         "inválidos, raio ≤ 0, q = 0)", not aceites,
         f"aceites por engano: {aceites}" if aceites else f"{len(casos)}/{len(casos)} recusadas")
    nao_iniciado = sv.SeguidorCpp(bib=bib, cfg={"yaw_max": 0.0})
    o = nao_iniciado.passo(1000, 0.0, 0.0, 0.0, (1, 160.0, 120.0, 8.0, 1, 900))
    c.ok("[§3] um Seguidor com Config recusada devolve comando NULO + kFlagNaoIniciado (nunca manda lixo)",
         not nao_iniciado.iniciado and o.vx == 0 and o.vz == 0 and o.yaw_taxa == 0
         and (o.flags & bib.const["kFlagNaoIniciado"]) != 0, f"flags={o.flags}")


# ============================================================================================ §4 detetor
LARGURAS = {"QVGA 320×240": (320, 240), "QQVGA 160×120": (160, 120)}
RAIO_ALVO = 0.05          # m — RAIO_PONTO do lab/camera_rpi.py


def para_cinza(rgb: np.ndarray) -> np.ndarray:
    """RGB uint8 → cinzento uint8 por luma ITU-R BT.601 (a de `lab.camera_rpi.para_cinza` e da PIL/OpenCV): o que
    um HM0360/HM01B0 de 8 bit entregaria — só brilho, sem cor."""
    return np.rint(rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114).astype(np.uint8)


class Cena:
    """O drone do dono com a câmara `fpv` à frente e a esfera-marcador (mocap) — a cena REAL do lab, só renderizada.

    Estático: o corpo fica em (0,0,1) com rumo 0 (como no `teste_seguimento.py`); o que se mede é a PERCEÇÃO (frame →
    detetor), por isso a física não entra. A esfera passa a BRANCA emissiva (câmara mono: o alvo distingue-se por
    brilho; o magenta do marcador dá luma 0,51 — medido abaixo).
    """

    def __init__(self) -> None:
        import mujoco
        import visao

        import lab.drone_rpi as dr
        self.mujoco, self.visao = mujoco, visao
        hw = dr.hardware()
        self.model, self.data = dr.modelo.carregar(hw, com_alvo=True)
        self.cid = self.model.camera("fpv").id
        try:
            from lab import camera_rpi as cam
            self.fovy = float(cam.fovy_graus("vs_hm0360", "QVGA30"))
            self.fonte_fov = "lab/camera_rpi.py (vs_hm0360 · QVGA30)"
        except (KeyError, ValueError, TypeError, ImportError):
            self.fovy, self.fonte_fov = FOVY_HM0360_FALLBACK, "ficha Himax HM0360-MWA (literal)"
        self.model.cam_fovy[self.cid] = self.fovy
        self.mid = self.model.material("ponto_mat").id
        self.gid = self.model.geom("ponto_esfera").id
        self.cor_original = (self.model.mat_rgba[self.mid].copy(), self.model.geom_rgba[self.gid].copy())
        self.data.qpos[0:3] = [0.0, 0.0, 1.0]
        mujoco.mj_forward(self.model, self.data)
        self._renderers: dict = {}
        self.cam_pos = np.array(self.data.cam_xpos[self.cid], dtype=float)

    def cor(self, branca: bool) -> None:
        rgba = (1.0, 1.0, 1.0, 1.0) if branca else tuple(self.cor_original[0])
        self.model.mat_rgba[self.mid] = rgba
        self.model.geom_rgba[self.gid] = rgba if branca else self.cor_original[1]

    def renderer(self, w: int, h: int):
        if (w, h) not in self._renderers:
            self._renderers[(w, h)] = self.mujoco.Renderer(self.model, height=h, width=w)
        return self._renderers[(w, h)]

    def focal_px(self, h: int) -> float:
        return 0.5 * h / math.tan(math.radians(self.fovy) / 2.0)

    def renderizar(self, w: int, h: int, pos) -> np.ndarray:
        self.visao.posicionar_ponto(self.model, self.data, pos)
        self.mujoco.mj_forward(self.model, self.data)
        r = self.renderer(w, h)
        r.update_scene(self.data, camera="fpv")
        return para_cinza(r.render())

    def projecao(self, w: int, h: int, pos) -> dict:
        """Projeção EXATA do centro (convenção da BORDA do MuJoCo) e da silhueta da esfera (centróide e raio da área)."""
        p = self.visao.projetar(self.model, self.data, pos, camera="fpv", largura_px=w, altura_px=h)
        rot = np.asarray(self.data.cam_xmat[self.cid], dtype=float).reshape(3, 3)
        eye = np.asarray(self.data.cam_xpos[self.cid], dtype=float)
        c = np.asarray(pos, dtype=float)
        f = self.focal_px(h)
        d = float(np.linalg.norm(c - eye))
        n = (c - eye) / d
        q = eye + n * (d * d - RAIO_ALVO ** 2) / d                       # centro da circunferência de contacto
        rho = RAIO_ALVO * math.sqrt(d * d - RAIO_ALVO ** 2) / d
        a = np.cross(n, [0.0, 0.0, 1.0])
        a /= np.linalg.norm(a)
        b = np.cross(n, a)
        t = np.linspace(0.0, 2.0 * math.pi, 361)[:-1]
        pts = q[None, :] + rho * (np.cos(t)[:, None] * a[None, :] + np.sin(t)[:, None] * b[None, :])
        loc = (pts - eye) @ rot                                            # Rᵀ·(p − eye) por linha
        u = -f * loc[:, 0] / loc[:, 2] + 0.5 * w
        v = f * loc[:, 1] / loc[:, 2] + 0.5 * h
        u1, v1 = np.roll(u, -1), np.roll(v, -1)
        cruz = u * v1 - u1 * v
        area = 0.5 * abs(float(cruz.sum()))
        cu = float(((u + u1) * cruz).sum() / (6.0 * 0.5 * cruz.sum()))
        cv = float(((v + v1) * cruz).sum() / (6.0 * 0.5 * cruz.sum()))
        return {"u": p["u"], "v": p["v"], "visivel": p["visivel"], "profundidade": p["profundidade"],
                "u_sil": cu, "v_sil": cv, "r_eq": math.sqrt(area / math.pi), "dist": d}

    def fechar(self) -> None:
        for r in self._renderers.values():
            with contextlib.suppress(Exception):
                r.close()
        self._renderers.clear()


def gerar_poses(cena: Cena, w: int, h: int, n: int, rng, dist=(1.0, 3.0), frac: float = 0.75) -> list:
    """`n` posições do alvo dentro do campo (frac do semi-campo) a `dist` metros de profundidade."""
    tv = math.tan(math.radians(cena.fovy) / 2.0)
    th = (w / h) * tv
    poses = []
    for _ in range(n):
        x = rng.uniform(*dist)
        y = -rng.uniform(-frac * th, frac * th) * x        # esquerda do corpo = +y (a direita da imagem é −y)
        z = max(rng.uniform(-frac * tv, frac * tv) * x, 0.15 - cena.cam_pos[2])   # acima do chão (z = 0)
        poses.append(tuple(cena.cam_pos + np.array([x, y, z])))
    return poses


def efeito(frame: np.ndarray, nome: str, rng) -> np.ndarray:
    """O mesmo frame com um defeito de sensor/ótica: ruído gaussiano, desfoque, vinheta, saturação, píxeis mortos."""
    f = frame.astype(np.float64)
    h, w = f.shape
    if nome == "limpo":
        return frame
    if nome.startswith("ruido"):
        f = f + rng.normal(0.0, float(nome[5:]), f.shape)
    elif nome.startswith("desfoque"):
        from scipy.ndimage import gaussian_filter
        f = gaussian_filter(f, float(nome[8:]))
    elif nome == "vinheta":
        yy, xx = np.mgrid[0:h, 0:w]
        r2 = ((xx - (w - 1) / 2) ** 2 + (yy - (h - 1) / 2) ** 2) / (((w - 1) / 2) ** 2 + ((h - 1) / 2) ** 2)
        f = f * (1.0 - 0.6 * r2)
    elif nome.startswith("ganho"):
        f = f * float(nome[5:])
    elif nome == "pixeis_mortos":
        n = max(8, w * h // 1000)
        f[rng.integers(0, h, n), rng.integers(0, w, n)] = 255.0       # quentes
        f[rng.integers(0, h, n), rng.integers(0, w, n)] = 0.0         # mortos
    else:
        raise ValueError(nome)
    return np.clip(np.rint(f), 0, 255).astype(np.uint8)


def avaliar_deteccoes(det, quadros: list, nome: str, w: int, h: int, rng, **params) -> dict:
    """Corre o detetor C++ sobre `quadros` (dicts com `frame` e `proj`) sob o efeito `nome`; erros em px (INDICE)."""
    det.params_padrao(w, h, **params)
    e_cen, e_sil, e_raio, validos = [], [], [], 0
    for q in quadros:
        f = efeito(q["frame"], nome, rng)
        d = det.detetar(f)
        if d.valido:
            validos += 1
            u_ref, v_ref = q["proj"]["u"] - 0.5, q["proj"]["v"] - 0.5           # borda → índice
            e_cen.append(math.hypot(d.u - u_ref, d.v - v_ref))
            e_sil.append(math.hypot(d.u - (q["proj"]["u_sil"] - 0.5), d.v - (q["proj"]["v_sil"] - 0.5)))
            e_raio.append(d.raio_px - q["proj"]["r_eq"])
    n = len(quadros)
    a = np.array(e_cen) if e_cen else np.array([float("nan")])
    return {"n": n, "validos": validos, "taxa": validos / n, "media": float(np.mean(a)),
            "p95": float(np.percentile(a, 95)), "max": float(np.max(a)),
            "media_sil": float(np.mean(e_sil)) if e_sil else float("nan"),
            "raio_vies": float(np.mean(e_raio)) if e_raio else float("nan"),
            "raio_std": float(np.std(e_raio)) if e_raio else float("nan")}


def disco_sintetico(w: int, h: int, cx: float, cy: float, r: float, fundo: int = 30, pico: int = 255, ss: int = 4):
    """Disco anti-aliased (cobertura exata por supersampling), convenção do índice."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    cob = np.zeros((h, w))
    for dy in (np.arange(ss) + 0.5) / ss - 0.5:
        for dx in (np.arange(ss) + 0.5) / ss - 0.5:
            cob += ((xs + dx - cx) ** 2 + (ys + dy - cy) ** 2 <= r * r)
    return np.clip(fundo + (pico - fundo) * cob / (ss * ss), 0, 255).round().astype(np.uint8)


def contagens_do_frame(frame: np.ndarray, limiar: int) -> tuple[int, int]:
    """(nº de píxeis ≥ limiar, nº de runs) — o que o llvm-mca precisa para dimensionar um frame."""
    m = frame >= limiar
    runs = int(np.count_nonzero(np.diff(m.astype(np.int8), axis=1) == 1) + m[:, 0].sum())
    return int(m.sum()), runs


def tempo_host_us(det, frame: np.ndarray, reps: int = 200, **params) -> float:
    t = []
    for _ in range(reps):
        t0 = time.perf_counter_ns()
        det.detetar(frame, **params)
        t.append(time.perf_counter_ns() - t0)
    return float(np.median(t)) / 1e3


def secao_detetor(c: Checagens, bib, cena: Cena, mca: dict) -> dict:
    rng = np.random.default_rng(12345)
    saida: dict = {"tabela": {}}
    det = sv.DetetorCpp(bib)
    print(f"        (cena: fovy {cena.fovy:.1f}° — {cena.fonte_fov}; f = {cena.focal_px(240):.1f} px a 320×240 e "
          f"{cena.focal_px(120):.1f} px a 160×120; raio do alvo {RAIO_ALVO * 100:.0f} cm)")
    quadros_por = {}
    for nome, (w, h) in LARGURAS.items():
        cena.cor(True)
        dist = (1.0, 3.0) if w == 320 else (1.0, 2.2)
        poses = gerar_poses(cena, w, h, 80, rng, dist=dist)
        quadros_por[nome] = [{"pos": p, "frame": cena.renderizar(w, h, p), "proj": cena.projecao(w, h, p)}
                             for p in poses]
    # ---- convenção de píxeis: o «0,708 px» do gate do visao.py é meio píxel de convenção, não erro do detetor
    q320 = quadros_por["QVGA 320×240"]
    det.params_padrao(320, 240)
    sem_corr, com_corr = [], []
    for q in q320:
        d = det.detetar(q["frame"])
        if d.valido:
            sem_corr.append(math.hypot(d.u - q["proj"]["u"], d.v - q["proj"]["v"]))
            com_corr.append(math.hypot(d.u - (q["proj"]["u"] - 0.5), d.v - (q["proj"]["v"] - 0.5)))
    c.ok("[§4] CONVENÇÃO: o erro «detetor vs projeção» SEM corrigir é ≈ 0,707 px (= √(0,5²+0,5²): a projeção do MuJoCo "
         "usa a convenção da BORDA, o detetor o ÍNDICE) e COM a correção de meio píxel cai para o erro real — é a "
         "origem dos 0,708 px do gate do visao.py", 0.65 < np.mean(sem_corr) < 0.78 and np.mean(com_corr) < 0.15,
         f"sem correção {np.mean(sem_corr):.3f} px · com correção {np.mean(com_corr):.3f} px")
    # ---- precisão por resolução e condição
    tabela = {}
    for nome, (w, h) in LARGURAS.items():
        quadros = quadros_por[nome]
        for cond in ("limpo", "ruido3", "ruido6", "ruido10", "desfoque1", "desfoque2", "vinheta", "ganho2",
                     "pixeis_mortos"):
            tabela[(nome, cond)] = avaliar_deteccoes(det, quadros, cond, w, h, np.random.default_rng(7))
    saida["tabela"] = tabela
    print("        erro de localização (px, convenção do índice) vs projeção EXATA do centro — 80 poses por linha:")
    print(f"        {'resolução':14s} {'condição':14s} {'válidos':>8s} {'média':>7s} {'p95':>7s} {'máx':>7s} {'vs silh.':>8s} "
          f"{'Δraio':>7s}")
    for (nome, cond), t in tabela.items():
        print(f"        {nome:14s} {cond:14s} {t['validos']:3d}/{t['n']:<4d} {t['media']:7.3f} {t['p95']:7.3f} {t['max']:7.3f} "
              f"{t['media_sil']:8.3f} {t['raio_vies']:+7.3f}")
    l320, l160 = tabela[("QVGA 320×240", "limpo")], tabela[("QQVGA 160×120", "limpo")]
    c.ok("[§4] sem ruído, a 320×240: 100 % válidos, erro de localização médio < 0,15 px e máximo < 0,5 px vs a projeção "
         "exata", l320["taxa"] == 1.0 and l320["media"] < 0.15 and l320["max"] < 0.5,
         f"média {l320['media']:.3f} · p95 {l320['p95']:.3f} · máx {l320['max']:.3f} px")
    c.ok("[§4] sem ruído, a 160×120: 100 % válidos, erro médio < 0,25 px e máximo < 0,6 px",
         l160["taxa"] == 1.0 and l160["media"] < 0.25 and l160["max"] < 0.6,
         f"média {l160['media']:.3f} · p95 {l160['p95']:.3f} · máx {l160['max']:.3f} px")
    c.ok("[§4] o viés de PERSPETIVA do centróide face à projeção do centro é real e pequeno: o erro contra o centróide da "
         "silhueta exata (o que um detetor de blob consegue ver) é menor que contra a projeção do centro",
         l320["media_sil"] <= l320["media"] + 1e-3, f"vs centro {l320['media']:.3f} px · vs silhueta {l320['media_sil']:.3f} px")
    r6, r6b = tabela[("QVGA 320×240", "ruido6")], tabela[("QQVGA 160×120", "ruido6")]
    c.ok("[§4] com ruído gaussiano σ = 6 níveis (≈ 2,4 % do fundo de escala): ≥ 98 % válidos e erro médio < 0,3 px "
         "(320×240) / < 0,5 px (160×120)", r6["taxa"] >= 0.98 and r6["media"] < 0.3 and r6b["taxa"] >= 0.98
         and r6b["media"] < 0.5, f"320×240 {r6['media']:.3f} px ({r6['validos']}/80) · 160×120 {r6b['media']:.3f} px "
         f"({r6b['validos']}/80)")
    r10 = tabela[("QVGA 320×240", "ruido10")]
    c.ok("[§4] com σ = 10 níveis o erro médio continua < 0,5 px (320×240) e o detetor não inventa blobs",
         r10["taxa"] >= 0.95 and r10["media"] < 0.5, f"{r10['media']:.3f} px, {r10['validos']}/80 válidos")
    d1, d2 = tabela[("QVGA 320×240", "desfoque1")], tabela[("QVGA 320×240", "desfoque2")]
    c.ok("[§4] tolera DESFOQUE (σ = 1 e 2 px): o centróide não se desloca (< 0,2 px) — só o raio enviesa",
         d1["taxa"] >= 0.98 and d2["taxa"] >= 0.95 and d1["media"] < 0.2 and d2["media"] < 0.2,
         f"σ1 {d1['media']:.3f} px (Δraio {d1['raio_vies']:+.2f}) · σ2 {d2['media']:.3f} px (Δraio {d2['raio_vies']:+.2f})")
    vg = tabela[("QVGA 320×240", "vinheta")]
    c.ok("[§4] tolera VINHETA (−60 % nos cantos): limiar adaptativo, erro médio < 0,3 px, ≥ 95 % válidos",
         vg["taxa"] >= 0.95 and vg["media"] < 0.3, f"{vg['media']:.3f} px, {vg['validos']}/80 válidos")
    gn = tabela[("QVGA 320×240", "ganho2")]
    c.ok("[§4] BRILHO SATURADO (ganho ×2: alvo e chão saturam): o limiar relativo ao máximo ainda acerta — centróide "
         "< 0,3 px; o raio engorda (halo)", gn["taxa"] >= 0.95 and gn["media"] < 0.3,
         f"{gn['media']:.3f} px, {gn['validos']}/80 válidos, Δraio {gn['raio_vies']:+.2f} px")
    pm = tabela[("QVGA 320×240", "pixeis_mortos")]
    c.ok("[§4] PÍXEIS QUENTES/MORTOS (0,1 % de cada): o máximo robusto (mín. de vizinhos) ignora o quente isolado e o "
         "alvo continua a ser achado (erro médio < 0,3 px, ≥ 95 % válidos)", pm["taxa"] >= 0.95 and pm["media"] < 0.3,
         f"{pm['media']:.3f} px, {pm['validos']}/80 válidos")
    # ---- píxeis quentes em força e os LIMITES declarados (reportados, não corrigidos)
    quadros = quadros_por["QVGA 320×240"]
    det.params_padrao(320, 240)
    rng_q = np.random.default_rng(3)
    ok_quentes = 0
    for q in quadros:
        f = q["frame"].copy()
        f[rng_q.integers(0, 240, 1000), rng_q.integers(0, 320, 1000)] = 255      # 1,3 % de píxeis quentes
        ok_quentes += int(det.detetar(f).valido)
    c.ok("[§4] com 1000 píxeis QUENTES espalhados (1,3 % do frame) o alvo continua a ser achado (≥ 95 %)",
         ok_quentes >= 76, f"{ok_quentes}/80 válidos")
    t3 = avaliar_deteccoes(det, quadros, "ganho3", 320, 240, np.random.default_rng(1))
    ok_col = ok_barra = 0
    for q in quadros:
        uc, vc = round(q["proj"]["u"] - 0.5), round(q["proj"]["v"] - 0.5)
        f1 = q["frame"].copy()
        f1[:, uc] = 30                                                      # coluna MORTA pelo centro do alvo
        ok_col += int(det.detetar(f1).valido)
        f2 = q["frame"].copy()
        f2[max(vc - 1, 0):vc + 2, :] = 30                                   # linha escura de 3 px pelo alvo
        ok_barra += int(det.detetar(f2).valido)
    saida["limites"] = {"ganho3": t3["taxa"], "coluna_morta": ok_col / 80, "barra_escura": ok_barra / 80}
    c.ok("[§4] LIMITES DECLARADOS (o detetor por momentos FALHA aqui — reportado, não corrigido; propostas no README): "
         f"chão saturado (ganho ×3: o chão passa o limiar e funde-se com o alvo que está sobre ele) só {100 * t3['taxa']:.0f} % "
         f"válidos; uma coluna morta ou uma linha escura que PARTE o alvo ao meio → {ok_col}/80 e {ok_barra}/80 (duas metades "
         "alongadas); propostas: AEC com janela no alvo, mapa de píxeis defeituosos/ponte de 1–2 px nos runs",
         t3["taxa"] < 0.7 and ok_col <= 8 and ok_barra <= 8)
    # ---- o limiar adaptativo vs fixo, e o marcador magenta (luma)
    quadros = quadros_por["QVGA 320×240"]
    det.params_padrao(320, 240)
    adapt_fixo = {}
    for nome, lim, cond in (("fixo 128 com ganho ×0,3", 128, "ganho0.3"), ("adaptativo com ganho ×0,3", 0, "ganho0.3"),
                            ("fixo 128 sem defeito", 128, "limpo")):
        ok_n = 0
        for q in quadros:
            d = det.detetar(efeito(q["frame"], cond, np.random.default_rng(1)), limiar=lim)
            ok_n += int(d.valido)
        adapt_fixo[nome] = ok_n
    c.ok("[§4] limiar ADAPTATIVO vs FIXO: com o brilho do alvo a 30 % (exposição curta) o fixo (128) perde o alvo e o "
         "adaptativo (fração do máximo) não; o fixo funciona onde o brilho é o esperado",
         adapt_fixo["fixo 128 com ganho ×0,3"] == 0 and adapt_fixo["adaptativo com ganho ×0,3"] >= 76
         and adapt_fixo["fixo 128 sem defeito"] >= 76, str(adapt_fixo))
    cena.cor(False)
    mag = [{"pos": q["pos"], "frame": cena.renderizar(320, 240, q["pos"]), "proj": q["proj"]} for q in quadros]
    cena.cor(True)
    tm = avaliar_deteccoes(det, mag, "limpo", 320, 240, np.random.default_rng(7))
    luma_mag = int(max(int(m["frame"].max()) for m in mag))
    c.ok("[§4] o marcador MAGENTA do simulador em câmara MONO tem luma ≈ 131/255 (metade de um branco) mas contra este "
         "fundo escuro ainda é detetável — só por brilho; num fundo claro (≥ 130) deixaria de ser: o alvo real tem de ser "
         "branco/IR", tm["taxa"] >= 0.95 and tm["media"] < 0.3 and 100 <= luma_mag <= 160,
         f"{tm['validos']}/80 válidos, erro {tm['media']:.3f} px, luma máx {luma_mag}")
    # ---- limite de tamanho: raio mínimo detetável (discos sintéticos anti-aliased)
    lim_tab = {}
    for (w, h) in ((320, 240), (160, 120)):
        det.params_padrao(w, h)
        for r in (1.5, 2.0, 2.5, 3.0, 4.0, 6.0):
            ok_n, errs = 0, []
            for _ in range(60):
                cx_, cy_ = rng.uniform(10, w - 10), rng.uniform(10, h - 10)
                d = det.detetar(disco_sintetico(w, h, cx_, cy_, r))
                if d.valido:
                    ok_n += 1
                    errs.append(math.hypot(d.u - cx_, d.v - cy_))
            lim_tab[(w, r)] = (ok_n / 60, float(np.mean(errs)) if errs else float("nan"))
    print("        disco sintético (anti-aliased) — taxa de deteção / erro médio (px) por raio:")
    for w in (320, 160):
        print("          " + f"{w}×{w * 3 // 4}: " + " · ".join(f"r={r}: {lim_tab[(w, r)][0] * 100:3.0f} % / {lim_tab[(w, r)][1]:.3f}"
                                                          for r in (1.5, 2.0, 2.5, 3.0, 4.0, 6.0)))
    r_min = {w: min((r for r in (1.5, 2.0, 2.5, 3.0, 4.0, 6.0) if lim_tab[(w, r)][0] >= 0.95), default=None)
             for w in (320, 160)}
    saida["r_min"] = r_min
    c.ok("[§4] raio mínimo detetável (≥ 95 %): " + " · ".join(f"{w}×{w * 3 // 4}: {r_min[w]} px" for w in (320, 160))
         + f" → alcance máximo de uma esfera de {RAIO_ALVO * 100:.0f} cm = f·R/r_min ≈ "
         + " · ".join(f"{cena.focal_px(h_) * RAIO_ALVO / r_min[w]:.1f} m" for w, h_ in ((320, 240), (160, 120))
                      if r_min[w]),
         all(r_min[w] is not None and r_min[w] <= 3.0 for w in (320, 160)),
         "d* = 1,5 m dá r = " + " / ".join(f"{cena.focal_px(h_) * RAIO_ALVO / 1.5:.1f}" for h_ in (240, 120))
         + " px (320×240 / 160×120, FoV 55,4°); no HM01B0 QQVGA120 (FoV 70,9°, f = "
         f"{0.5 * 120 / math.tan(math.radians(70.9) / 2):.0f} px) o alvo a 1,5 m tem só r = "
         f"{0.5 * 120 / math.tan(math.radians(70.9) / 2) * RAIO_ALVO / 1.5:.1f} px: no limite")
    saida["lim_tab"] = lim_tab
    # ---- distratores
    w, h = 320, 240
    det.params_padrao(w, h)
    q0 = quadros[0]
    bar_h = q0["frame"].copy()
    yb = 40 if q0["proj"]["v"] > 120 else 200
    bar_h[yb:yb + 3, 100:200] = 255                                          # barra horizontal 100×3 (lâmpada/tubo)
    d_barra = det.detetar(bar_h)
    solo = np.full((h, w), 30, np.uint8)
    solo[100:103, 60:200] = 255
    d_solo = det.detetar(solo)
    barra_v = np.full((h, w), 30, np.uint8)
    barra_v[:, 150:154] = 255                                                # poste vertical que atravessa o frame
    d_poste = det.detetar(barra_v)
    c.ok("[§4] DISTRATOR ALONGADO rejeitado: uma barra 140×3 sozinha (M_CIRCULARIDADE) e um poste de 240×4 que atravessa "
         "o frame inteiro (não esgota a memória: componentes em streaming) dão inválido",
         not d_solo.valido and d_solo.motivo == bib.const["M_CIRCULARIDADE"] and not d_poste.valido
         and d_poste.motivo in (bib.const["M_CIRCULARIDADE"], bib.const["M_BORDA"]),
         f"barra: motivo {d_solo.motivo} circ {d_solo.circularidade:.2f} · poste: motivo {d_poste.motivo}")
    u_ref, v_ref = q0["proj"]["u"] - 0.5, q0["proj"]["v"] - 0.5
    c.ok("[§4] o alvo ao lado de uma barra (blobs separados) continua a ser achado com o erro de sempre — etiquetagem "
         "de componentes, não um único momento do frame todo", d_barra.valido and math.hypot(d_barra.u - u_ref, d_barra.v - v_ref) < 0.3,
         f"válido={d_barra.valido} erro {math.hypot(d_barra.u - u_ref, d_barra.v - v_ref):.3f} px · blobs avaliados {d_barra.n_blobs}")
    gate_off = det.detetar(solo, circ_min=0.0, cheio_min=0.0, cheio_max=1e9)
    c.ok("[§4] o GATE DE CIRCULARIDADE tem dentes: sem ele (circ_min = 0 e sem «cheio») a mesma barra seria aceite como "
         "alvo", bool(gate_off.valido), f"sem gate: válido={gate_off.valido} (circ {gate_off.circularidade:.2f}, cheio {gate_off.cheio:.2f})")
    # barra encostada ao alvo (fundida): limite do método
    junta = q0["frame"].copy()
    ui, vi = round(u_ref), round(v_ref)
    junta[max(vi - 1, 0):vi + 2, max(ui - 5, 0):min(ui + 60, w)] = 255
    d_junta = det.detetar(junta)
    saida["junta_valido"] = bool(d_junta.valido)
    c.ok("[§4] LIMITE conhecido: uma barra FUNDIDA com o alvo (mesmo blob) faz o blob alongado e o detetor recusa (em vez "
         "de dar um centróide errado); a resposta é o seguimento com janela (abaixo) ou o filtro com previsão",
         not d_junta.valido and d_junta.motivo in (bib.const["M_CIRCULARIDADE"], bib.const["M_CHEIO"]),
         f"motivo {d_junta.motivo} circ {d_junta.circularidade:.2f}")
    # dois discos: o de mais massa ganha; a janela de busca escolhe o alvo
    dois = q0["frame"].copy()
    gr = disco_sintetico(w, h, 240.0 if u_ref < 160 else 80.0, 60.0 if v_ref > 120 else 180.0, 16.0)
    dois = np.maximum(dois, gr)
    d_dois = det.detetar(dois)
    roi = {"roi_x0": max(int(u_ref) - 30, 0), "roi_y0": max(int(v_ref) - 30, 0), "roi_x1": min(int(u_ref) + 31, w),
               "roi_y1": min(int(v_ref) + 31, h)}
    d_roi = det.detetar(dois, **roi)
    err_roi = math.hypot(d_roi.u - u_ref, d_roi.v - v_ref)
    c.ok("[§4] DOIS DISCOS (alvo r≈8 px + «lâmpada» r = 16 px): sem janela vence o de mais massa (a lâmpada — limite "
         "declarado); com a JANELA DE BUSCA à volta da posição prevista o alvo é o escolhido e o erro é o de sempre",
         d_dois.valido and math.hypot(d_dois.u - u_ref, d_dois.v - v_ref) > 20.0 and d_roi.valido and err_roi < 0.3,
         f"sem janela: ({d_dois.u:.0f},{d_dois.v:.0f}) r={d_dois.raio_px:.1f} · com janela: erro {err_roi:.3f} px")
    # ---- alvo cortado pelo FOV
    cena.cor(True)
    cortado = []
    for folga in (5.0, 2.0, 0.0, -3.0):             # centro a `folga` px do bordo direito: 1 a 60 % do disco cortado
        for r_ in (7.0, 9.0):
            f_ = disco_sintetico(w, h, w - 1 - folga, 100.0, r_)
            dg = det.detetar(f_)
            dsb = det.detetar(f_, margem_borda=0)
            cortado.append((dg, dsb, w - 1 - folga))
    todos_recusados = all((not dg.valido) and dg.motivo == bib.const["M_BORDA"] for dg, _, _ in cortado)
    vies = [abs(dsb.u - cxc) for _, dsb, cxc in cortado if dsb.valido]
    c.ok("[§4] ALVO PARCIALMENTE FORA DO FOV: o detetor recusa o blob cortado pelo bordo (M_BORDA) em vez de dar um "
         "centróide enviesado — medido: sem o gate o centróide do disco cortado erra até "
         f"{max(vies):.1f} px (p/ o interior) e os mais cortados falham também a circularidade", todos_recusados and max(vies) > 0.5,
         f"{len(cortado)} casos recusados; viés máx sem gate {max(vies):.2f} px")
    # ---- sem alvo / falsos positivos
    vazios = []
    for k in range(80):
        p_ = (-3.0 - 0.1 * k, 0.0, 1.0)         # a esfera ATRÁS da câmara
        vazios.append(cena.renderizar(320, 240, p_))
    fp_cena = sum(int(det.detetar(f).valido) for f in vazios)
    fp_ruido = 0
    n_ruido = 0
    for sigma in (4, 10, 20):
        for _ in range(60):
            f = np.clip(rng.normal(30.0, sigma, (240, 320)), 0, 255).astype(np.uint8)
            fp_ruido += int(det.detetar(f).valido)
            n_ruido += 1
    uni = det.detetar(np.full((240, 320), 200, np.uint8))
    c.ok("[§4] SEM ALVO → inválido: 80 frames da cena real sem esfera (atrás da câmara), 180 frames de ruído puro "
         "(σ = 4, 10, 20) e um frame uniforme saturado dão 0 falsos positivos",
         fp_cena == 0 and fp_ruido == 0 and not uni.valido,
         f"cena {fp_cena}/80 · ruído {fp_ruido}/{n_ruido} · uniforme motivo {uni.motivo}")
    # ---- frame degenerado
    c.ok("[§4] entradas inválidas (frame nulo/tamanho 0/ROI vazia) dão M_PARAMETROS sem ler memória",
         det.detetar(np.zeros((1, 1), np.uint8)).motivo == bib.const["M_PARAMETROS"]
         and det.detetar(np.zeros((8, 8), np.uint8), roi_x0=5, roi_y0=5, roi_x1=6, roi_y1=6).motivo
         == bib.const["M_PARAMETROS"])
    # ---- tempo no host e ciclos M7
    host = {}
    cena.cor(True)
    for nome, (w_, h_) in LARGURAS.items():
        q = quadros_por[nome][0]
        det.params_padrao(w_, h_)
        t_alvo = tempo_host_us(det, q["frame"])
        t_vazio = tempo_host_us(det, vazios[0][: h_ * 1, : w_] if (w_, h_) == (320, 240) else q["frame"] * 0)
        host[nome] = (t_alvo, t_vazio)
    det.params_padrao(320, 240)
    f_roi = quadros_por["QVGA 320×240"][0]["frame"]
    pq = quadros_por["QVGA 320×240"][0]["proj"]
    roi = {"roi_x0": max(int(pq["u"]) - 40, 0), "roi_y0": max(int(pq["v"]) - 40, 0),
               "roi_x1": min(int(pq["u"]) + 41, 320), "roi_y1": min(int(pq["v"]) + 41, 240)}
    t_roi = tempo_host_us(det, f_roi, **roi)
    ciclos = {}
    for opt, k in mca.items():
        for nome, (w_, h_) in LARGURAS.items():
            q = quadros_por[nome][0]
            det.params_padrao(w_, h_)
            d = det.detetar(q["frame"])
            n_acima, n_runs = contagens_do_frame(q["frame"], d.limiar)
            est = estimar_frame(k, w_, h_, n_acima, n_runs, n_blobs=max(d.n_blobs, 1))
            ciclos[(opt, nome)] = est
        wr, hr = roi["roi_x1"] - roi["roi_x0"], roi["roi_y1"] - roi["roi_y0"]
        sub = f_roi[roi["roi_y0"]:roi["roi_y1"], roi["roi_x0"]:roi["roi_x1"]]
        det.params_padrao(320, 240)
        d = det.detetar(f_roi, **roi)
        n_acima, n_runs = contagens_do_frame(sub, d.limiar)
        ciclos[(opt, "janela 81×81")] = estimar_frame(k, wr, hr, n_acima, n_runs, n_blobs=max(d.n_blobs, 1))
    saida["ciclos"], saida["host"], saida["t_roi_host"] = ciclos, host, t_roi
    print("        custo por frame (frame com alvo r≈9 px a 1,5 m):")
    print(f"        {'':22s} {'host (µs)':>10s} " + " ".join(f"{'M7 '+opt+' (µs)':>16s}" for opt in mca)
          + f" {'% de 33,3 ms':>13s} {'% de 40 ms':>11s}")
    for nome in list(LARGURAS) + ["janela 81×81"]:
        th = host[nome][0] if nome in host else t_roi
        linha = f"        {nome:22s} {th:10.1f} "
        for opt in mca:
            linha += f"{ciclos[(opt, nome)]['total'] / 480.0:16.0f} "
        tot = ciclos[("-Os", nome)]["total"] / 480.0
        linha += f"{100 * tot / 33333.0:12.1f}% {100 * tot / 40000.0:10.1f}%"
        print(linha)
    m7_qvga = ciclos[("-Os", "QVGA 320×240")]["total"] / 480.0
    m7_qqvga = ciclos[("-Os", "QQVGA 160×120")]["total"] / 480.0
    m7_roi = ciclos[("-Os", "janela 81×81")]["total"] / 480.0
    c.ok("[§4] TEMPO no host (medido, i.e. NÃO é o do M7): mediana de 200 chamadas — "
         + " · ".join(f"{n}: {host[n][0]:.0f} µs" for n in LARGURAS) + f" · janela 81×81: {t_roi:.0f} µs",
         all(host[n][0] < 2000 for n in LARGURAS), "x86-64 a vários GHz com caches grandes; só serve de ordem de grandeza")
    c.ok("[§4] CICLOS Cortex-M7 (ESTIMADOS por llvm-mca + contagem de píxeis/runs, 480 MHz, -Os): "
         f"QVGA {ciclos[('-Os', 'QVGA 320×240')]['total'] / 1e3:.0f} kcic = {m7_qvga / 1e3:.2f} ms "
         f"({100 * m7_qvga / 33333:.1f} % do período a 30 Hz, {100 * m7_qvga / 40000:.1f} % a 25 Hz) · QQVGA "
         f"{m7_qqvga / 1e3:.2f} ms ({100 * m7_qqvga / 33333:.1f} %) · janela 81×81 {m7_roi / 1e3:.2f} ms — sem "
         "medição em hardware (nenhuma fonte prova o fps no Portenta/Nicla)",
         m7_qvga < 0.15 * 33333 and m7_qqvga < 0.05 * 33333 and m7_roi < m7_qvga / 3,
         "margem ×2 recomendada pela pesquisa [S107]: QVGA " + f"{2 * m7_qvga / 1e3:.2f} ms")
    c.ok("[§4] RAM: o frame QVGA ocupa 76 800 B (QQVGA 19 200 B) e o detetor só acrescenta "
         f"{int(bib.lib.visao_tamanho_detetor())} B de trabalho (instância estática) — o H747 tem 1 MB de SRAM",
         int(bib.lib.visao_tamanho_detetor()) < 8192, f"sizeof(Detetor) = {int(bib.lib.visao_tamanho_detetor())} B")
    saida["quadros"] = quadros_por
    return saida


# ============================================================================================ §5 estimador
TRAJS = (("circulo", 0.3), ("circulo", 0.5), ("circulo", 0.8), ("oito", 0.3), ("oito", 0.5), ("oito", 0.8))
MODELOS = (("α-β", 0), ("KF-CV", 1), ("KF-CA", 2))


def cenario_estimador(modo: str, vel: float, amp: float = 0.25, f_yaw: float = 0.4):
    """Drone PARADO a rodar (ψ roteirizado: segue a linha de vista ± 0,25 rad a 0,4 Hz ⇒ taxa própria até
    ±0,63 rad/s) e alvo em círculo/oito — para avaliar só o estimador (atraso + rotação própria)."""
    alvo = sv.trajetoria_alvo(modo, vel)
    p0 = (0.5, 0.0, 1.0) if modo == "circulo" else (-1.0, 0.0, 1.0)

    def yaw(t):
        pt = alvo(t)
        return math.atan2(pt[1] - p0[1], pt[0] - p0[0]) + amp * math.sin(2.0 * math.pi * f_yaw * t)
    return alvo, p0, yaw


def prever_sob_atraso(bib, modo: str, vel: float, modelo: int, cfg: dict | None = None, atraso: float = 0.116,
                      seed: int = 0, T: float = 22.0, sigma_px: float = 0.3, sigma_att: float = 0.0026,
                      t0_us: int = 0, p_outlier: float = 0.0, yaw_bias: float = 0.0, series: bool = False) -> dict:
    alvo, p0, yaw = cenario_estimador(modo, vel)
    res = sv.simular_laco(alvo, T=T, modelo=modelo, cfg=cfg, atraso=atraso, seed=seed, sigma_px=sigma_px,
                          drone0=(p0[0], p0[1], p0[2], 0.0), yaw_script=yaw, bib=bib, sigma_att=sigma_att,
                          t0_us=t0_us, p_outlier=p_outlier, yaw_bias=yaw_bias)
    e = sv.erro_previsao(res)
    e["comb"] = math.hypot(e["rms_epsi_graus"], e["rms_el_graus"])
    if series:
        e["series"] = res["series"]
    return e


def media_comb(bib, modelo: int, trajs=TRAJS, seeds=(0, 1), **kw) -> float:
    v = [prever_sob_atraso(bib, m, vel, modelo, seed=sd, **kw)["comb"] for m, vel in trajs for sd in seeds]
    return float(np.mean(v))


def secao_estimador(c: Checagens, bib) -> dict:
    saida: dict = {}
    # ---- tabela: erro de previsão do RUMO (o que o controlador de yaw vê) e da elevação, sob 116 ms
    tab = {}
    for m, vel in TRAJS:
        for nome, mod in MODELOS:
            r = [prever_sob_atraso(bib, m, vel, mod, seed=sd) for sd in (0, 1)]
            tab[(m, vel, nome)] = {k: float(np.mean([x[k] for x in r])) for k in
                                   ("rms_epsi_graus", "rms_el_graus", "rms_az_velho_graus", "rms_az_cam_velho_graus",
                                    "max_epsi_graus")}
    saida["tab"] = tab
    print("        erro de previsão com 116 ms de atraso e o drone a rodar (RMS, graus; atitude com erro lento de 0,15°,"
          " medidas com σ = 0,3 px):")
    print(f"        {'alvo':14s} {'':6s} {'rumo α-β':>9s} {'rumo CV':>8s} {'rumo CA':>8s} {'elev CA':>8s}"
          f" | {'sem previsão':>12s} {'sem desrodar':>12s}")
    for m, vel in TRAJS:
        a, cv, ca = (tab[(m, vel, n)] for n, _ in MODELOS)
        print(f"        {m:8s} {vel:4.1f} m/s {a['rms_epsi_graus']:9.3f} {cv['rms_epsi_graus']:8.3f} {ca['rms_epsi_graus']:8.3f}"
              f" {ca['rms_el_graus']:8.3f} | {ca['rms_az_velho_graus']:12.2f} {ca['rms_az_cam_velho_graus']:12.2f}")
    melhores_rel = []
    for (m, vel, nome), t in tab.items():
        melhores_rel.append((t["rms_epsi_graus"] / t["rms_az_velho_graus"], t["rms_epsi_graus"], m, vel, nome))
    pior_rel = max(melhores_rel)
    c.ok("[§5] o PREVISOR sob atraso (α-β, KF-CV e KF-CA) bate a referência «sem previsão» (a última medida desrodada, "
         "como chegou) em TODOS os alvos: erro de rumo ≤ 0,5× o do «velho» e < 0,6°",
         pior_rel[0] <= 0.5 and max(t["rms_epsi_graus"] for t in tab.values()) < 0.6,
         f"pior razão {pior_rel[0]:.2f} ({pior_rel[2]} {pior_rel[3]} m/s, {pior_rel[4]}); erro máx RMS "
         f"{max(t['rms_epsi_graus'] for t in tab.values()):.2f}°")
    sem_rot = min(t["rms_az_cam_velho_graus"] / max(t["rms_epsi_graus"], 1e-9) for t in tab.values())
    c.ok("[§5] DESRODAR é necessário: o bearing da câmara sem compensar a rotação própria (116 ms × ±0,63 rad/s de "
         "yaw) erra ≈ 3,4° e o estimador com histórico de atitude fica ≥ 7× abaixo", sem_rot >= 7.0,
         f"pior razão (sem desrodar)/(estimador) = {sem_rot:.1f}")
    ca_circ08 = tab[("circulo", 0.8, "KF-CA")]
    c.ok("[§5] círculo a 0,8 m/s (taxa de bearing 0,53 rad/s): o «velho» erra "
         f"{ca_circ08['rms_az_velho_graus']:.2f}° (= taxa × atraso) e o KF-CA {ca_circ08['rms_epsi_graus']:.2f}° "
         f"(≥ 15× melhor)", ca_circ08["rms_az_velho_graus"] / ca_circ08["rms_epsi_graus"] >= 15.0)
    # ---- α-β vs KF-CV vs KF-CA: com atitude PERFEITA o KF-CA ganha; com a atitude real o piso é a atitude
    perf = {nome: media_comb(bib, mod, sigma_att=0.0) for nome, mod in MODELOS}
    real = {nome: media_comb(bib, mod, sigma_att=0.0026) for nome, mod in MODELOS}
    saida["perf"], saida["real"] = perf, real
    c.ok("[§5] com a atitude EXATA o KF-CA tem o menor erro de previsão (rumo+elevação, média dos 6 alvos): "
         f"KF-CA {perf['KF-CA']:.3f}° vs α-β {perf['α-β']:.3f}° ({100 * (1 - perf['KF-CA'] / perf['α-β']):.0f} % melhor) "
         f"e KF-CV {perf['KF-CV']:.3f}°", perf["KF-CA"] <= 0.9 * perf["α-β"] and perf["KF-CA"] <= perf["KF-CV"],
         "afinados em q_ang/α-β na grelha círculo/oito 0,3–0,8 m/s, 116 ms")
    spread = max(real.values()) / min(real.values())
    c.ok("[§5] com a atitude REAL (erro lento de 0,15°) os três filtros empatam (máx/mín < 1,25): o piso do erro é a "
         f"atitude estimada, não o modelo do alvo — α-β {real['α-β']:.3f}° · KF-CV {real['KF-CV']:.3f}° · KF-CA "
         f"{real['KF-CA']:.3f}°", spread < 1.25, f"máx/mín = {spread:.3f}")
    # ---- varrimento do atraso
    err_atraso = {}
    for atr in (0.021, 0.066, 0.116, 0.166):
        r = [prever_sob_atraso(bib, m, vel, 2, atraso=atr, seed=0) for m, vel in (("circulo", 0.8), ("oito", 0.5))]
        err_atraso[atr] = (float(np.mean([x["rms_epsi_graus"] for x in r])),
                           float(np.mean([x["rms_az_velho_graus"] for x in r])))
    saida["err_atraso"] = err_atraso
    print("        atraso (ms)  :" + "".join(f"{1000 * a:9.0f}" for a in err_atraso))
    print("        KF-CA (°)    :" + "".join(f"{v[0]:9.3f}" for v in err_atraso.values()))
    print("        sem previsão :" + "".join(f"{v[1]:9.2f}" for v in err_atraso.values()))
    e21, e166 = err_atraso[0.021][0], err_atraso[0.166][0]
    v21, v166 = err_atraso[0.021][1], err_atraso[0.166][1]
    e66, e116 = err_atraso[0.066][0], err_atraso[0.116][0]
    c.ok("[§5] o previsor MANTÉM o erro de rumo < 0,3° do pipeline do Arduino (21 ms) ao do Pi + 50 ms (166 ms), sempre "
         f"≥ 7× abaixo do «sem previsão»: previsor {e21:.2f}° → {e66:.2f}° → {e116:.2f}° → {e166:.2f}° · sem previsão "
         f"{v21:.2f}° → {v166:.2f}°", e21 < e66 < e116 < e166 < 0.3 and all(v / e >= 7.0 for e, v in err_atraso.values()),
         "cresce com o atraso porque o horizonte de extrapolação do alvo é maior (jerk não modelado); aqui o drone só roda, a translação própria durante o atraso não está em jogo (e não é compensada — ver alvo.hpp)")
    # ---- volta do relógio de 2^32
    a = prever_sob_atraso(bib, "circulo", 0.5, 2, series=True, T=8.0, t0_us=0)["series"]
    b = prever_sob_atraso(bib, "circulo", 0.5, 2, series=True, T=8.0, t0_us=0xFFFFF000)["series"]
    iguais = all(np.array_equal(np.asarray(a[k]), np.asarray(b[k]), equal_nan=True) for k in ("az_pred", "e_psi_est", "taxa_est"))
    c.ok("[§5] o relógio de µs que dá a volta de 2³² a meio do voo (t₀ = 0xFFFFF000) dá EXATAMENTE as mesmas saídas "
         "(diferenças com subtração sem sinal: histórico, filtro e máquina de estados)", iguais)
    # ---- outliers e gate de inovação
    com_gate = [prever_sob_atraso(bib, "circulo", 0.5, 2, p_outlier=0.05, seed=sd) for sd in (0, 1)]
    sem_gate = [prever_sob_atraso(bib, "circulo", 0.5, 2, p_outlier=0.05, seed=sd, cfg={"gate_sigma": 1.0e6})
                for sd in (0, 1)]
    e_cg = float(np.mean([x["rms_epsi_graus"] for x in com_gate]))
    e_sg = float(np.mean([x["rms_epsi_graus"] for x in sem_gate]))
    c.ok("[§5] GATE DE INOVAÇÃO: com 5 % de deteções FALSAS (píxel aleatório) o erro de rumo fica < 1° e sem o gate "
         f"(gate_sigma = 10⁶) é ≥ 3× pior: {e_cg:.2f}° vs {e_sg:.2f}°", e_cg < 1.0 and e_sg >= 3.0 * e_cg)
    # ---- o viés do giroscópio (rumo sem magnetómetro) cancela no erro de rumo
    base = prever_sob_atraso(bib, "circulo", 0.5, 2, seed=0)["rms_epsi_graus"]
    com_vies = prever_sob_atraso(bib, "circulo", 0.5, 2, seed=0, yaw_bias=0.02)["rms_epsi_graus"]
    c.ok("[§5] a DERIVA do rumo (viés do giroscópio 0,02 rad/s = 1,1°/s, sem magnetómetro) cancela no erro de rumo "
         "(azimute inercial e rumo derivam juntos): RMS inalterado (≤ 1,3×)", com_vies <= 1.3 * base + 0.02,
         f"sem viés {base:.3f}° · com viés {com_vies:.3f}°")
    return saida


# ============================================================================================ §6 lei IBVS
def margem_fase(kp: float, ki: float, tau: float, atraso: float, ts: float = 0.04) -> dict:
    """PM/GM/ωc de L(s) = (Kp + Ki/s)·e^{−s(T + Ts/2)}/(s·(τ·s + 1)) — yaw_taxa → rumo com lag τ de 1.ª ordem, atraso
    de câmara T e o ZOH do frame (Ts/2). ESTRUTURA PESSIMISTA: o atraso inteiro dentro do laço, como se o seguidor
    não desrodasse nem previsse (o previsor/desrotação só melhoram isto)."""
    w = np.logspace(-3, 2, 120000)
    s = 1j * w
    L = (kp + ki / s) * np.exp(-s * (atraso + ts / 2.0)) / (s * (tau * s + 1.0))
    mag = np.abs(L)
    fase = np.unwrap(np.angle(L))
    idx = np.where((mag[:-1] >= 1.0) & (mag[1:] < 1.0))[0]
    i = idx[-1]
    j = np.where((fase[:-1] > -np.pi) & (fase[1:] <= -np.pi))[0]
    gm = -20.0 * math.log10(float(mag[j[0]])) if len(j) else float("inf")
    return {"pm": 180.0 + math.degrees(float(fase[i])), "gm_db": gm, "wc": float(w[i])}


ATRASOS = (0.021, 0.066, 0.116, 0.166)          # Arduino DCMI (21 ms) · 116−50 · Pi (116 ms) · 116+50


def roteiro(bib, visivel, T: float, az_graus: float = 0.0, cfg: dict | None = None, passo: float = 0.01,
            fps: float = 25.0, atraso: float = 0.116, dist: float = 1.5, elev_graus: float = 0.0) -> list:
    """Drone estático a olhar para +x, alvo estático a `az_graus` (+ = esquerda) e `elev_graus` (+ = cima), a `dist` m,
    câmara ideal a 25 Hz com atraso; `visivel(t)` diz se o frame capturado em t vê o alvo. A planta NÃO responde (é um
    roteiro, não um laço): serve para olhar a máquina de estados e os comandos. Registo por passo:
    (t, estado, vx, vz, yaw, flags, e_psi, n_aceites)."""
    seg = sv.SeguidorCpp(320, 240, 55.4, 2, cfg, bib)
    f, cx, cy = float(seg.cfg.f_px), float(seg.cfg.cx), float(seg.cfg.cy)
    az, el = math.radians(az_graus), math.radians(elev_graus)
    u0 = cx - f * math.tan(az)
    v0 = cy - f * math.tan(el) / math.cos(az)
    r0 = f * 0.05 / dist
    fila, cam, n, prox, log, k = [], (0, 0.0, 0.0, 0.0, 0, 0), 0, 0.0, [], 0
    while k * passo < T:
        t = k * passo
        if t + 1e-9 >= prox:
            prox += 1.0 / fps
            n += 1
            v = visivel(t)
            fila.append((t + atraso, (1 if v else 0, u0 if v else 0.0, v0 if v else 0.0, r0 if v else 0.0, n,
                                      round(t * 1e6))))
        while fila and fila[0][0] <= t + 1e-9:
            cam = fila.pop(0)[1]
        o = seg.passo(round(t * 1e6), 0.0, 0.0, 0.0, cam)
        log.append((t, o.estado, o.vx, o.vz, o.yaw_taxa, o.flags, o.e_psi, o.n_aceites))
        k += 1
    seg.close()
    return log


def primeira(log: list, estado: int, depois: float = 0.0):
    return next((r[0] for r in log if r[1] == estado and r[0] >= depois), None)


def desrodar_pitch_roll(bib, com_atitude: bool, T: float = 16.0, seed: int = 0) -> dict:
    """Alvo estático fora do eixo (az +10°, el +5°, 1,5 m) com o drone parado a balançar ±10° em pitch e ±8° em roll
    (0,5 e 0,37 Hz): as coordenadas MUNDO do alvo são constantes, os píxeis não. Com a atitude o seguidor deve ver
    sempre o mesmo e_ψ/e_ε (e v_z ≈ 0); sem ela (atitude zero) vê o alvo a abanar."""
    rng = np.random.default_rng(seed)
    seg = sv.SeguidorCpp(320, 240, 55.4, 2, None, bib)
    f, cx, cy = float(seg.cfg.f_px), float(seg.cfg.cx), float(seg.cfg.cy)
    d, az, el = 1.5, math.radians(10.0), math.radians(5.0)
    p_w = np.array([d * math.cos(el) * math.cos(az), d * math.cos(el) * math.sin(az), d * math.sin(el)])
    fila, cam, n, prox, k, passo = [], (0, 0, 0, 0, 0, 0), 0, 0.0, 0, 0.01
    ep, ee, vz = [], [], []
    while k * passo < T:
        t = k * passo
        pitch, roll = math.radians(10.0) * math.sin(2 * math.pi * 0.5 * t), math.radians(8.0) * math.sin(2 * math.pi * 0.37 * t)
        if t + 1e-9 >= prox:
            prox += 0.04
            n += 1
            R = np.array(sv._rot_zyx(roll, pitch, 0.0))
            pb = R.T @ p_w
            u = cx + f * (-pb[1] / pb[0]) + rng.normal(0, 0.2)
            v = cy + f * (-pb[2] / pb[0]) + rng.normal(0, 0.2)
            fila.append((t + 0.116, (1, u, v, f * 0.05 / d, n, round(t * 1e6))))
        while fila and fila[0][0] <= t + 1e-9:
            cam = fila.pop(0)[1]
        a = (roll, pitch) if com_atitude else (0.0, 0.0)
        o = seg.passo(round(t * 1e6), a[0], a[1], 0.0, cam)
        if t > 5.0 and o.estado == 0:
            ep.append(math.degrees(o.e_psi))
            ee.append(math.degrees(o.e_elev))
            vz.append(o.vz)
        k += 1
    seg.close()
    return {"std_epsi": float(np.std(ep)), "std_eel": float(np.std(ee)), "std_vz": float(np.std(vz)),
            "rms_vz": float(np.sqrt(np.mean(np.square(vz)))),
            "media_epsi": float(np.mean(ep)), "media_eel": float(np.mean(ee)), "n": len(ep)}


def lixo_no_laco(bib) -> dict:
    """Alvo estático à frente e câmara ideal com «episódios de lixo»: atitude NaN/inf, píxel NaN/enorme, raio ≤ 0,
    relógio a recuar e a saltar. Todas as saídas têm de ser finitas e dentro dos limites; depois do lixo volta a seguir."""
    seg = sv.SeguidorCpp(320, 240, 55.4, 2, None, bib)
    f, cx, cy = float(seg.cfg.f_px), float(seg.cfg.cx), float(seg.cfg.cy)
    lim = (float(seg.cfg.vx_max), float(seg.cfg.vz_max), float(seg.cfg.yaw_max))
    n, prox, k, passo, fila = 0, 0.0, 0, 0.01, []
    cam = (0, 0.0, 0.0, 0.0, 0, 0)
    ruins, flags_falha, estados = 0, 0, []
    nan, inf = float("nan"), float("inf")
    for k in range(3000):
        t = k * passo
        if t + 1e-9 >= prox:
            prox += 0.04
            n += 1
            fila.append((t + 0.116, (1, cx, cy, f * 0.05 / 1.5, n, round(t * 1e6))))
        while fila and fila[0][0] <= t + 1e-9:
            cam = fila.pop(0)[1]
        roll = pitch = psi = 0.0
        c_ = cam
        t_us = round(t * 1e6)
        if 5.0 <= t < 5.3:
            roll = nan
        elif 7.0 <= t < 7.2:
            psi = inf
        elif 9.0 <= t < 9.4:
            c_ = (1, nan, cy, 7.6, n + 1000, t_us)
        elif 11.0 <= t < 11.3:
            c_ = (1, 1e30, cy, 7.6, n + 2000, t_us)
        elif 13.0 <= t < 13.3:
            c_ = (1, cx, cy, -5.0, n + 3000, t_us)
        elif 15.0 <= t < 15.2:
            t_us = max(t_us - 700000, 0)                 # o relógio recua
        elif 17.0 <= t < 17.1:
            t_us = (t_us + 4_000_000_000) & 0xFFFFFFFF   # e salta
        o = seg.passo(t_us, roll, pitch, psi, c_)
        vals = [o.vx, o.vy, o.vz, o.yaw_taxa, o.e_psi, o.e_elev, o.dist, o.taxa_bearing, o.az_pred, o.el_pred]
        if not all(math.isfinite(x) for x in vals):
            ruins += 1
        if abs(o.vx) > lim[0] + 1e-4 or abs(o.vz) > lim[1] + 1e-4 or abs(o.yaw_taxa) > lim[2] + 1e-4:
            ruins += 1
        flags_falha += int((o.flags & bib.const["kFlagFalhaNumerica"]) != 0)
        estados.append(o.estado)
        ult = o
    seg.close()
    return {"ruins": ruins, "falhas": flags_falha, "estado_final": estados[-1], "e_psi_final": math.degrees(ult.e_psi),
            "frac_seguir_fim": float(np.mean([e == 0 for e in estados[2500:]]))}


def secao_ibvs(c: Checagens, bib) -> dict:
    saida: dict = {}
    cfg = sv.SeguidorCpp(bib=bib).cfg
    kp, ki, kpz, kpd = float(cfg.kp_yaw), float(cfg.ki_yaw), float(cfg.kp_z), float(cfg.kp_d)
    # ------------------------------------------------------------------ margens de fase (frequência)
    pm = {(tau, a): margem_fase(kp, ki, tau, a) for tau in (0.3, 0.45, 0.6) for a in ATRASOS}
    saida["pm_yaw"] = pm
    print(f"        margem de fase do laço de YAW (Kp = {kp:g} /s, Ki = {ki:g} /s²; atraso inteiro DENTRO do laço + ZOH 20 ms):")
    print(f"        {'τ_yaw':8s} " + " ".join(f"{'T = ' + str(round(1000 * a)) + ' ms':>14s}" for a in ATRASOS))
    for tau in (0.3, 0.45, 0.6):
        print(f"        {tau:5.2f} s  " + " ".join(f"{pm[(tau, a)]['pm']:8.1f}° /{pm[(tau, a)]['gm_db']:4.1f}dB" for a in ATRASOS))
    pior = min(pm.values(), key=lambda d: d["pm"])
    c.ok("[§6] MARGEM DE FASE do laço de yaw ≥ 45° em TODA a grelha τ_yaw ∈ {0,3; 0,45; 0,6} s × atraso ∈ {21; 66; 116; 166} ms "
         f"(estrutura pessimista: sem previsor): mínimo {pior['pm']:.1f}° (τ 0,6 s, 166 ms); nominal (0,45 s; 116 ms) "
         f"{pm[(0.45, 0.116)]['pm']:.1f}°, margem de ganho {pm[(0.45, 0.116)]['gm_db']:.1f} dB",
         pior["pm"] >= 45.0 and all(d["gm_db"] >= 12.0 for d in pm.values()),
         "τ_yaw é HIPÓTESE (0,3–0,6 s) a confirmar quando a B0 publicar a identificação")
    d50 = pm[(0.45, 0.066)]["pm"] - pm[(0.45, 0.166)]["pm"]
    c.ok("[§6] o atraso ±50 ms muda a margem de fase pouco: 66 ms → 166 ms perde "
         f"{d50:.1f}° (≈ ωc·ΔT = {pm[(0.45, 0.116)]['wc']:.2f} rad/s × 100 ms) — o atraso de câmara não é o limite, o lag do yaw é",
         0.0 < d50 < 10.0, f"PM(66 ms) {pm[(0.45, 0.066)]['pm']:.1f}° · PM(116 ms) {pm[(0.45, 0.116)]['pm']:.1f}° · PM(166 ms) "
         f"{pm[(0.45, 0.166)]['pm']:.1f}°")
    pm_v = {(tv_, a): margem_fase(kpz, 0.0, tv_, a) for tv_ in (0.3, 0.5, 0.7) for a in ATRASOS}
    pm_d = {(tv_, a): margem_fase(kpd, 0.0, tv_, a) for tv_ in (0.3, 0.5, 0.7) for a in ATRASOS}
    c.ok("[§6] margens de fase ≥ 45° também nos laços de v_z (Kz = " f"{kpz:g}) e de v_x (Kd = {kpd:g}) com lag de velocidade "
         "τ_v ∈ {0,3; 0,5; 0,7} s e os mesmos atrasos", min(d["pm"] for d in pm_v.values()) >= 45.0
         and min(d["pm"] for d in pm_d.values()) >= 45.0,
         f"mínimos: v_z {min(d['pm'] for d in pm_v.values()):.1f}° · v_x {min(d['pm'] for d in pm_d.values()):.1f}°")
    # ------------------------------------------------------------------ laço fechado: alvo estático
    def estatico(pos, T=20.0, **kw):
        res = sv.simular_laco(sv.trajetoria_alvo("parado", 0.0, inicio=pos), T=T, bib=bib, **kw)
        S = res["series"]
        n = len(S["t"])
        fim = [i for i in range(n) if S["t"][i] > T - 3.0]
        ep0 = abs(S["e_psi_real"][0]) if abs(S["e_psi_real"][0]) > 0.05 else None
        t_c = 0.0
        for i in range(n - 1, -1, -1):
            if abs(math.degrees(S["e_psi_real"][i])) > 2.0:
                t_c = S["t"][min(i + 1, n - 1)]
                break
        sobre = 0.0
        if ep0:                                       # sobre-elevação: erro de sinal contrário / erro inicial
            sinal = 1.0 if S["e_psi_real"][0] > 0 else -1.0
            sobre = max(0.0, max(-sinal * e for e in S["e_psi_real"]) / ep0)
        return {"ep_fim": max(abs(math.degrees(S["e_psi_real"][i])) for i in fim),
                "dz_fim": max(abs(S["dist"][i] * math.sin(S["el_real"][i])) for i in fim),
                "dd_fim": max(abs(S["d_err"][i]) for i in fim), "t_cent": t_c, "sobre": sobre,
                "seguir_fim": float(np.mean([S["estado"][i] == 0 for i in fim]))}
    casos = ((2.0, 0.0, 1.0), (2.0, 1.0, 1.0), (2.0, -1.0, 1.8), (3.5, 0.5, 0.4), (2.5, 1.2, 1.5), (1.2, -0.4, 0.8))
    est = {p_: estatico(p_) for p_ in casos}
    saida["estatico"] = est
    print("        alvo ESTÁTICO (posição inicial → |e_ψ| fim · desvio vertical fim · |D−d*| fim · t(|e_ψ|<2°) · sobre-elevação):")
    for p_, e in est.items():
        print(f"          {p_!s:18s} {e['ep_fim']:5.2f}° · {100 * e['dz_fim']:4.1f} cm · {100 * e['dd_fim']:4.1f} cm · "
              f"{e['t_cent']:4.1f} s · {100 * e['sobre']:4.1f} %")
    c.ok("[§6] CENTRA um alvo estático (6 posições iniciais, até ±27° de rumo, 0,6 m de altura, 1,2–3,5 m): em ≤ 5 s "
         "o rumo fica < 2° e no fim < 1°, o desvio vertical < 5 cm, a distância a d* = 1,5 m ±8 cm, sem perder o alvo",
         all(e["t_cent"] <= 5.0 and e["ep_fim"] < 1.0 and e["dz_fim"] < 0.05 and e["dd_fim"] < 0.08 and e["seguir_fim"] == 1.0
             for e in est.values()),
         f"pior t {max(e['t_cent'] for e in est.values()):.1f} s · pior |e_ψ| fim {max(e['ep_fim'] for e in est.values()):.2f}° · "
         f"pior |D−d*| {100 * max(e['dd_fim'] for e in est.values()):.1f} cm")
    c.ok("[§6] a resposta ao degrau de rumo (27°) quase não sobre-eleva (< 15 %): coerente com PM ≈ 54° (nominal)",
         max(e["sobre"] for e in est.values()) < 0.15, f"pior {100 * max(e['sobre'] for e in est.values()):.1f} %")
    # ------------------------------------------------------------------ círculo, oito
    laco = {}
    for m, v in TRAJS:
        laco[(m, v)] = sv.metricas_laco(sv.simular_laco(sv.trajetoria_alvo(m, v), T=30.0, bib=bib))
    saida["laco"] = laco
    print("        SEGUIMENTO com 116 ms (planta cinemática: yaw 2.ª ordem τ 0,45 s, v com lag 0,5 s; KF-CA + FF + avanço):")
    print(f"        {'alvo':14s} {'rumo RMS/máx (°)':>17s} {'|D−d*| méd/máx (m)':>19s} {'no campo':>9s} {'A_SEGUIR':>9s}"
          f" {'yaw máx':>8s} {'v_x máx':>8s}")
    for (m, v), r in laco.items():
        print(f"        {m:8s} {v:4.1f} m/s {r['rms_rumo_graus']:8.2f} /{r['max_rumo_graus']:5.1f} "
              f"{r['erro_dist_medio_m']:11.3f} /{r['erro_dist_max_m']:5.2f} {100 * r['frac_campo']:8.1f}% "
              f"{100 * r['frac_seguir']:8.1f}% {r['yaw_max_rad_s']:8.2f} {r['vx_max']:8.2f}")
    circ = [laco[("circulo", v)] for v in (0.3, 0.5, 0.8)]
    c.ok("[§6] SEGUE o CÍRCULO a 0,3 / 0,5 / 0,8 m/s (raio 1,5 m, drone dentro dele): erro de rumo RMS < 1°, máx < 2,5°, alvo "
         "sempre no campo, distância média a d* < 6 cm, 100 % em A_SEGUIR",
         all(r["rms_rumo_graus"] < 1.0 and r["max_rumo_graus"] < 2.5 and r["frac_campo"] == 1.0
             and r["erro_dist_medio_m"] < 0.06 and r["frac_seguir"] == 1.0 for r in circ),
         " · ".join(f"{v}: {r['rms_rumo_graus']:.2f}°/{r['max_rumo_graus']:.1f}°" for v, r in zip((0.3, 0.5, 0.8), circ, strict=True)))
    oito = [laco[("oito", v)] for v in (0.3, 0.5)]
    c.ok("[§6] SEGUE o «OITO» a 0,3 / 0,5 m/s: rumo RMS < 2,5°, alvo sempre no campo, |D−d*| médio < 0,25 m",
         all(r["rms_rumo_graus"] < 2.5 and r["frac_campo"] == 1.0 and r["erro_dist_medio_m"] < 0.25 for r in oito),
         " · ".join(f"{v}: {r['rms_rumo_graus']:.2f}°, D {r['erro_dist_medio_m']:.2f} m" for v, r in zip((0.3, 0.5), oito, strict=True)))
    o08 = laco[("oito", 0.8)]
    c.ok("[§6] o «oito» a 0,8 m/s é o limite: o yaw SATURA (a autoridade de 0,8 rad/s é o gargalo — o alvo passa a 0,5 m "
         "com taxa de linha de vista ≈ 1,6 rad/s), o erro sobe (RMS ≈ 9°) mas o alvo continua no campo ≥ 95 % do tempo e "
         "o laço não instabiliza", o08["yaw_max_rad_s"] >= 0.79 and o08["frac_campo"] >= 0.95 and o08["rms_rumo_graus"] < 20.0,
         f"RMS {o08['rms_rumo_graus']:.1f}° · máx {o08['max_rumo_graus']:.0f}° · no campo {100 * o08['frac_campo']:.1f} % · "
         f"|D−d*| {o08['erro_dist_medio_m']:.2f} m (a PPO de referência: 0,94 m)")
    # ------------------------------------------------------------------ o FF (o ponto da pesquisa) e o avanço de fase
    sem_ff = {k: sv.metricas_laco(sv.simular_laco(sv.trajetoria_alvo(*k), T=30.0, bib=bib, cfg={"kff_yaw": 0.0, "tau_avanco_yaw": 0.0}))
              for k in (("circulo", 0.5), ("circulo", 0.8), ("oito", 0.5))}
    razoes = {k: sem_ff[k]["rms_rumo_graus"] / laco[k]["rms_rumo_graus"] for k in sem_ff}
    c.ok("[§6] o FEEDFORWARD DA TAXA DE BEARING do alvo é o que faz a diferença (o ponto da pesquisa): com o PI de margem "
         f"≥ 45° (Ki = {ki:g}) e sem FF o erro de rumo do círculo a 0,8 m/s é "
         f"{sem_ff[('circulo', 0.8)]['rms_rumo_graus']:.1f}° (o integral não chega: a/Ka finito) e com FF "
         f"{laco[('circulo', 0.8)]['rms_rumo_graus']:.2f}° — redução ≥ 6× no círculo e ≥ 2× no oito",
         razoes[("circulo", 0.5)] >= 6.0 and razoes[("circulo", 0.8)] >= 6.0 and razoes[("oito", 0.5)] >= 2.0,
         "razões " + " · ".join(f"{k[0]} {k[1]}: {r:.0f}×" for k, r in razoes.items()))
    # o baseline JUSTO: um PI forte (Ki 0,5, integra sempre, clamp 1 rad/s) sem FF — o integral segue uma taxa ≈ constante
    forte = {"kff_yaw": 0.0, "tau_avanco_yaw": 0.0, "ki_yaw": 0.5, "i_max_yaw": 1.0, "integra_ate": 100.0}
    pi_forte = {k: sv.metricas_laco(sv.simular_laco(sv.trajetoria_alvo(*k), T=30.0, bib=bib, cfg=forte))
                for k in (("circulo", 0.5), ("circulo", 0.8), ("oito", 0.5))}
    pm_forte = margem_fase(kp, 0.5, 0.45, 0.116)["pm"]
    saida["pi_forte"] = pi_forte
    c.ok("[§6] HONESTIDADE sobre o integral (a pesquisa diz que o PI anula o erro com taxa constante): um PI FORTE (Ki 0,5, "
         "integra sempre, clamp 1 rad/s) sem FF segue o CÍRCULO quase tão bem "
         f"({pi_forte[('circulo', 0.5)]['rms_rumo_graus']:.2f}° / {pi_forte[('circulo', 0.8)]['rms_rumo_graus']:.2f}° vs "
         f"{laco[('circulo', 0.5)]['rms_rumo_graus']:.2f}° / {laco[('circulo', 0.8)]['rms_rumo_graus']:.2f}° com FF) mas com margem de "
         f"fase de {pm_forte:.0f}° (< 45°), e no «OITO» (taxa que varia) o FF + avanço é "
         f"{pi_forte[('oito', 0.5)]['rms_rumo_graus'] / laco[('oito', 0.5)]['rms_rumo_graus']:.0f}× melhor "
         f"({pi_forte[('oito', 0.5)]['rms_rumo_graus']:.1f}° → {laco[('oito', 0.5)]['rms_rumo_graus']:.2f}°)",
         pm_forte < 45.0 and pi_forte[("circulo", 0.5)]["rms_rumo_graus"] < 2.0 * laco[("circulo", 0.5)]["rms_rumo_graus"] + 0.2
         and pi_forte[("oito", 0.5)]["rms_rumo_graus"] >= 4.0 * laco[("oito", 0.5)]["rms_rumo_graus"])
    ab = {k: sv.metricas_laco(sv.simular_laco(sv.trajetoria_alvo(*k), T=30.0, bib=bib, modelo=0))
          for k in (("oito", 0.3), ("oito", 0.5))}
    ganho_ca = {k: ab[k]["rms_rumo_graus"] / laco[k]["rms_rumo_graus"] for k in ab}
    c.ok("[§6] em laço fechado o KF-CA ganha ao α-β no «oito» (≥ 1,5×): só ele estima a ACELERAÇÃO do bearing e "
         "usa-a no avanço de fase (FF + τ_av·α) que cancela o lag do yaw — " + " · ".join(
             f"{k[1]} m/s: α-β {ab[k]['rms_rumo_graus']:.2f}° vs KF-CA {laco[k]['rms_rumo_graus']:.2f}°" for k in ab),
         all(g >= 1.5 for g in ganho_ca.values()))
    # vertical: o FF vertical
    def vert(kff):
        res = sv.simular_laco(sv.trajetoria_alvo("vertical", 0.3, raio=1.5), T=30.0, bib=bib, cfg={"kff_z": kff})
        S = res["series"]
        dz = [abs(S["dist"][i] * math.sin(S["el_real"][i])) for i in range(len(S["t"])) if S["t"][i] > 4.0]
        return float(np.mean(dz)), float(np.max(dz))
    (z0, z0m), (z5, z5m) = vert(0.0), vert(0.5)
    c.ok("[§6] v_z segue um alvo que sobe e desce ±0,5 m (pico 0,3 m/s): desvio vertical médio "
         f"{100 * z5:.0f} cm com o FF vertical vs {100 * z0:.0f} cm só com P (−{100 * (1 - z5 / z0):.0f} %)",
         z5 <= 0.7 * z0 and z5 < 0.2, f"máx {100 * z5m:.0f} cm vs {100 * z0m:.0f} cm")
    # ------------------------------------------------------------------ robustez: τ_yaw × atraso (incl. o do Arduino)
    rob = {}
    for tau in (0.3, 0.6):
        for atr in (0.021, 0.166):
            for k in (("circulo", 0.8), ("oito", 0.5)):
                rob[(tau, atr, k)] = sv.metricas_laco(sv.simular_laco(sv.trajetoria_alvo(*k), T=30.0, bib=bib, tau_yaw=tau, atraso=atr))
    pior_rob = max(rob.values(), key=lambda r: r["rms_rumo_graus"])
    c.ok("[§6] ROBUSTEZ do laço fechado: τ_yaw ∈ {0,3; 0,6} s × atraso ∈ {21 ms (Arduino DCMI); 166 ms (116+50)} em círculo "
         "0,8 e oito 0,5: sempre no campo, rumo RMS < 4°, sem oscilar (yaw ≤ yaw_max)",
         all(r["frac_campo"] == 1.0 and r["rms_rumo_graus"] < 4.0 for r in rob.values()),
         f"pior caso: rumo RMS {pior_rob['rms_rumo_graus']:.2f}° · menor erro (Arduino 21 ms) "
         f"{min(r['rms_rumo_graus'] for r in rob.values()):.2f}°")
    # ---- SENSIBILIDADE à autoridade de yaw (a B0 ainda a está a identificar: o `controlo_classico.py` em curso tem hoje
    #      taxa_yaw_max = 0,35 rad/s e acel_yaw_max = 0,45 rad/s²; a pesquisa dá 0,5–1 rad/s)
    sens = {}
    for ym, ya in ((0.35, 0.45), (0.5, 0.8), (0.8, 1.5)):
        for k in (("circulo", 0.3), ("circulo", 0.5), ("circulo", 0.8), ("oito", 0.5)):
            sens[(ym, k)] = sv.metricas_laco(sv.simular_laco(sv.trajetoria_alvo(*k), T=30.0, bib=bib,
                                                              cfg={"yaw_max": ym, "yaw_acel_max": ya}))
    saida["sens_yaw"] = sens
    print("        SENSIBILIDADE à autoridade de yaw (rumo RMS em ° / % do tempo com o alvo no campo):")
    print(f"        {'yaw_max':>9s}  " + "  ".join(f"{k[0][:3]} {k[1]} m/s".rjust(15) for k in (("circulo", 0.3), ("circulo", 0.5), ("circulo", 0.8), ("oito", 0.5))))
    for ym in (0.35, 0.5, 0.8):
        print(f"        {ym:6.2f} rad/s  " + "  ".join(
            f"{sens[(ym, k)]['rms_rumo_graus']:7.1f}° {100 * sens[(ym, k)]['frac_campo']:4.0f}%"
            for k in (("circulo", 0.3), ("circulo", 0.5), ("circulo", 0.8), ("oito", 0.5))))
    c.ok("[§6] SENSIBILIDADE à AUTORIDADE DE YAW (o gargalo, a identificar pela B0): com 0,35 rad/s (o teto atual do "
         "`controlo_classico.py` em curso) segue o círculo a 0,3 m/s (RMS < 1°) mas já erra ≥ 3° a 0,5 m/s e PERDE o alvo a 0,8 m/s "
         f"(no campo {100 * sens[(0.35, ('circulo', 0.8))]['frac_campo']:.0f} %); com 0,5 rad/s segue até 0,5 m/s e com 0,8 rad/s "
         "tudo até 0,8 m/s — a velocidade de seguimento sustentável vem da autoridade de yaw, não do algoritmo",
         sens[(0.35, ("circulo", 0.3))]["rms_rumo_graus"] < 1.0 and sens[(0.35, ("circulo", 0.5))]["rms_rumo_graus"] >= 3.0
         and sens[(0.35, ("circulo", 0.8))]["frac_campo"] < 0.5 and sens[(0.5, ("circulo", 0.5))]["rms_rumo_graus"] < 1.0
         and sens[(0.8, ("circulo", 0.8))]["rms_rumo_graus"] < 1.0)
    inv = sv.metricas_laco(sv.simular_laco(sv.trajetoria_alvo("circulo", 0.5), T=30.0, bib=bib, comando_yaw_inverte=True))
    c.ok("[§6] o harness TEM DENTES: com o comando de yaw INVERTIDO (erro de sinal) o alvo foge do campo "
         f"(no campo {100 * inv['frac_campo']:.0f} %) — um erro de sinal não passaria despercebido", inv["frac_campo"] < 0.5)
    # ------------------------------------------------------------------ desrodar pitch/roll
    com, sem = desrodar_pitch_roll(bib, True), desrodar_pitch_roll(bib, False)
    c.ok("[§6] DESRODAR roll/pitch: com o drone a balançar ±10° (pitch) e ±8° (roll) e o alvo parado, com a atitude o erro de "
         f"rumo e de elevação previstos ficam constantes (σ {com['std_epsi']:.2f}° / {com['std_eel']:.2f}°, v_z σ "
         f"{com['std_vz'] * 100:.1f} cm/s de oscilação) e sem ela (atitude 0) abanam (σ {sem['std_epsi']:.1f}° / "
         f"{sem['std_eel']:.1f}°, v_z oscila {sem['std_vz'] * 100:.0f} cm/s)",
         com["std_epsi"] < 0.3 and com["std_eel"] < 0.3 and com["std_vz"] < 0.02 and sem["std_eel"] > 2.0 and sem["std_vz"] > 0.08,
         f"valores médios com atitude: e_ψ {com['media_epsi']:.1f}° (alvo a 10°) e e_ε {com['media_eel']:.1f}° (alvo a 5°)")
    # ------------------------------------------------------------------ máquina de estados
    S_, E_, P_, R_ = 0, 1, 2, 3
    lg = roteiro(bib, lambda t: not (3.0 <= t < 3.6), T=6.0)
    t_perd0 = primeira(lg, P_)
    t_ini = primeira(lg, S_)
    t_falta = primeira(lg, E_, 3.0)
    t_perd = primeira(lg, P_, 3.0)
    t_reaq = primeira(lg, R_, 3.5)
    t_seg2 = primeira(lg, S_, 3.5)
    esp_falta, esp_perd = 3.0 - 0.04 + 0.116 + 0.1, 3.0 - 0.04 + 0.116 + 0.3
    c.ok("[§6] MÁQUINA DE ESTADOS — arranque: começa PERDIDO (procura) e só chega a A_SEGUIR depois de n_reaq = 3 deteções "
         f"aceites (REAQUISICAO) ≈ {t_ini:.2f} s", lg[0][1] == P_ and t_perd0 == 0.0 and 0.15 <= t_ini <= 0.3,
         f"1.º A_SEGUIR em {t_ini:.2f} s")
    c.ok("[§6] MÁQUINA DE ESTADOS — perda: A_SEGUIR → EM_FALTA ao fim de t_gap = 100 ms sem deteção e → PERDIDO a t_falta = "
         f"300 ms (esperado {esp_falta:.2f} s e {esp_perd:.2f} s; medido {t_falta:.2f} s e {t_perd:.2f} s, ±30 ms)",
         abs(t_falta - esp_falta) <= 0.03 and abs(t_perd - esp_perd) <= 0.03)
    seq_reaq = [r[1] for r in lg if r[0] >= 3.5]
    dur_reaq = sum(1 for r in lg if r[1] == R_ and r[0] >= 3.5) * 0.01
    c.ok("[§6] MÁQUINA DE ESTADOS — reaquisição COM HISTERESE: PERDIDO → REAQUISICAO → A_SEGUIR (não salta direto) e a "
         f"confirmação de 3 deteções dura {dur_reaq * 1000:.0f} ms (2 períodos de frame = 80 ms)",
         t_reaq is not None and t_seg2 is not None and t_reaq < t_seg2 and 0.06 <= dur_reaq <= 0.12
         and seq_reaq.index(R_) < seq_reaq.index(S_), f"REAQ em {t_reaq:.2f} s, A_SEGUIR em {t_seg2:.2f} s")
    lg2 = roteiro(bib, lambda t: not (5.0 <= t < 5.15), T=8.0)
    est2 = {r[1] for r in lg2 if r[0] >= 5.0}
    c.ok("[§6] MÁQUINA DE ESTADOS — falha CURTA (150 ms): passa por EM_FALTA mas nunca por PERDIDO/REAQUISICAO e volta direto a "
         "A_SEGUIR (a previsão cobre o buraco)", E_ in est2 and P_ not in est2 and R_ not in est2 and lg2[-1][1] == S_,
         f"estados visitados {sorted(est2)}")
    lg3 = roteiro(bib, lambda t: (t < 2.0) or (8.0 <= t < 8.04), T=11.0)
    est3 = [r[1] for r in lg3 if r[0] >= 8.0]
    c.ok("[§6] MÁQUINA DE ESTADOS — HISTERESE: UM único frame válido no meio da procura leva a REAQUISICAO mas a falha "
         "seguinte volta a PERDIDO — nunca a A_SEGUIR", R_ in est3 and S_ not in est3 and lg3[-1][1] == P_,
         f"estados depois de 8 s: {sorted(set(est3))}")
    esq = roteiro(bib, lambda t: t < 3.0, T=9.0, az_graus=20.0)
    dire = roteiro(bib, lambda t: t < 3.0, T=9.0, az_graus=-20.0)
    pe = [r for r in esq if r[0] >= 5.0 and r[1] == P_]
    pd = [r for r in dire if r[0] >= 5.0 and r[1] == P_]
    w_proc = float(cfg.w_procura)
    c.ok("[§6] PERDIDO: v = 0 e procura LENTA de yaw para o ÚLTIMO LADO — alvo visto à esquerda → yaw +"
         f"{w_proc:g} rad/s; à direita → −{w_proc:g} rad/s",
         all(abs(r[2]) < 1e-6 and abs(r[3]) < 1e-6 for r in pe + pd) and all(abs(r[4] - w_proc) < 1e-3 for r in pe)
         and all(abs(r[4] + w_proc) < 1e-3 for r in pd) and len(pe) > 100 and len(pd) > 100,
         f"yaw esq {pe[-1][4]:+.3f} · dir {pd[-1][4]:+.3f} rad/s")
    lg4 = roteiro(bib, lambda t: t < 3.0, T=9.0, az_graus=5.0, dist=2.5, elev_graus=8.0)
    em = [r for r in lg4 if r[1] == E_]
    v_decai = [abs(r[2]) + abs(r[3]) for r in em]
    c.ok("[§6] EM_FALTA segue a previsão sem se soltar: o yaw continua o rumo previsto e a translação DECAI para 0 até ao "
         "fim da janela, monotonamente e contínua (limitada pelo slew: sem degrau ao entrar em PERDIDO)", len(em) > 10 and v_decai[0] > 0.5 and v_decai[-1] <= 0.8 * v_decai[0]
         and all(v_decai[i + 1] <= v_decai[i] + 1e-6 for i in range(len(v_decai) - 1)),
         f"{len(em)} passos, |v_x|+|v_z| {v_decai[0]:.3f} → {v_decai[-1]:.3f} m/s")
    lg5 = roteiro(bib, lambda t: t < 1.0, T=8.0, cfg={"t_procura_max_s": 3.0})
    flag_esg = bib.const["kFlagProcuraEsgotada"]
    esg = [r for r in lg5 if (r[5] & flag_esg) != 0]
    c.ok("[§6] a procura de yaw tem um LIMITE (t_procura_max_s): depois de 3 s em PERDIDO sinaliza kFlagProcuraEsgotada e "
         "pára de rodar (o supervisor decide — nada de girar para sempre)", len(esg) > 100 and all(abs(r[4]) < 0.3 for r in esg[-50:])
         and abs(esg[-1][4]) < 1e-3, f"{len(esg)} passos com a flag; yaw final {esg[-1][4]:+.4f} rad/s" if esg else "sem flag")
    # ------------------------------------------------------------------ limites, slew, zona morta
    lg6 = roteiro(bib, lambda t: True, T=8.0, az_graus=25.0, dist=3.0, elev_graus=20.0)
    cfgl = {k: float(getattr(cfg, k)) for k in ("yaw_max", "yaw_acel_max", "vx_max", "vz_max", "acel_x_max", "acel_z_max")}
    dy = max(abs(lg6[i + 1][4] - lg6[i][4]) / 0.01 for i in range(len(lg6) - 1))
    dvx = max(abs(lg6[i + 1][2] - lg6[i][2]) / 0.01 for i in range(len(lg6) - 1))
    dvz = max(abs(lg6[i + 1][3] - lg6[i][3]) / 0.01 for i in range(len(lg6) - 1))
    lim_ok = (max(abs(r[4]) for r in lg6) <= cfgl["yaw_max"] + 1e-5 and max(abs(r[2]) for r in lg6) <= cfgl["vx_max"] + 1e-5
              and max(abs(r[3]) for r in lg6) <= cfgl["vz_max"] + 1e-5)
    c.ok("[§6] LIMITES e SLEW cumpridos com um degrau grande (alvo a 25° de rumo, 20° de elevação e 3 m, parado): |yaw| ≤ yaw_max "
         f"({cfgl['yaw_max']:g} rad/s), |v_x| ≤ {cfgl['vx_max']:g} m/s, |v_z| ≤ {cfgl['vz_max']:g} m/s e as acelerações "
         f"≤ yaw_acel_max ({cfgl['yaw_acel_max']:g} rad/s², medido {dy:.2f}) / acel_x ({cfgl['acel_x_max']:g}, medido "
         f"{dvx:.2f}) / acel_z ({cfgl['acel_z_max']:g}, medido {dvz:.2f})",
         lim_ok and dy <= cfgl["yaw_acel_max"] * 1.001 and dvx <= cfgl["acel_x_max"] * 1.001
         and dvz <= cfgl["acel_z_max"] * 1.001)
    zm = float(cfg.zona_morta_yaw)
    pequeno = roteiro(bib, lambda t: True, T=10.0, az_graus=math.degrees(0.6 * zm), cfg={"ki_yaw": 0.0})
    grande = roteiro(bib, lambda t: True, T=10.0, az_graus=math.degrees(8.0 * zm), cfg={"ki_yaw": 0.0})
    y_peq = max(abs(r[4]) for r in pequeno if r[0] >= 6.0)
    y_gra = max(abs(r[4]) for r in grande if r[0] >= 6.0)
    c.ok(f"[§6] ZONA MORTA suave do yaw: um erro de 0,6× a zona morta ({math.degrees(zm):.2f}°) não comanda yaw (|yaw| < 1e-6) e um de 8× "
         "comanda Kp·(e − zona morta) (contínua, sem degrau)",
         y_peq < 1e-6 and 0.5 * kp * 7.0 * zm < y_gra < 1.6 * kp * 7.0 * zm,
         f"yaw {y_peq:.2e} rad/s vs {y_gra:.4f} rad/s (esperado ≈ {kp * 7 * zm:.4f})")
    # ------------------------------------------------------------------ saneamento, determinismo, relógio
    lx = lixo_no_laco(bib)
    c.ok("[§6] SANEAMENTO: com NaN/inf na atitude, píxel NaN/1e30, raio negativo e o relógio a recuar/saltar 3000 passos "
         f"seguidos têm saídas SEMPRE finitas e dentro dos limites ({lx['ruins']} violações), e depois do lixo volta a "
         f"seguir (A_SEGUIR {100 * lx['frac_seguir_fim']:.0f} % no fim, e_ψ {lx['e_psi_final']:.2f}°)",
         lx["ruins"] == 0 and lx["frac_seguir_fim"] > 0.95 and abs(lx["e_psi_final"]) < 1.0,
         f"falhas numéricas sinalizadas: {lx['falhas']}")
    r1 = sv.simular_laco(sv.trajetoria_alvo("circulo", 0.5), T=12.0, bib=bib, seed=3)["series"]
    r2 = sv.simular_laco(sv.trajetoria_alvo("circulo", 0.5), T=12.0, bib=bib, seed=3)["series"]
    r3 = sv.simular_laco(sv.trajetoria_alvo("circulo", 0.5), T=12.0, bib=bib, seed=4)["series"]
    r4 = sv.simular_laco(sv.trajetoria_alvo("circulo", 0.5), T=12.0, bib=bib, seed=3, t0_us=0xFFFFF000)["series"]
    chaves = ("yaw", "vx", "vz", "e_psi_est", "estado")
    c.ok("[§6] DETERMINISMO: duas corridas com a mesma semente dão saídas idênticas bit a bit (yaw, v, e_ψ, estado) e uma "
         "semente diferente dá outras", all(np.array_equal(r1[k], r2[k]) for k in chaves)
         and not np.array_equal(r1["yaw"], r3["yaw"]))
    c.ok("[§6] o laço fechado com o relógio a dar a volta de 2³² a meio (t₀ = 0xFFFFF000) é IDÊNTICO ao de t₀ = 0",
         all(np.array_equal(r1[k], r4[k]) for k in chaves))
    # ------------------------------------------------------------------ taxa de chamada: 500 Hz não esgota o histórico
    r500 = sv.simular_laco(sv.trajetoria_alvo("circulo", 0.8), T=16.0, bib=bib, passo=0.002, passo_ctrl=0.002)
    m500 = sv.metricas_laco(r500)
    curto = sum(1 for fl in r500["series"]["flags"] if fl & bib.const["kFlagHistoricoCurto"])
    c.ok("[§6] o seguidor chamado a 500 Hz (a cadência do núcleo de voo) dá o mesmo resultado que a 100 Hz: o histórico de atitude "
         f"decima (≥ 4 ms entre amostras) e nunca fica curto (círculo 0,8 m/s: rumo RMS {m500['rms_rumo_graus']:.2f}°, "
         f"{curto} passos com kFlagHistoricoCurto)", m500["rms_rumo_graus"] < 1.0 and m500["frac_campo"] == 1.0 and curto == 0)
    # ------------------------------------------------------------------ janela de busca prevista
    res = sv.simular_laco(sv.trajetoria_alvo("circulo", 0.5), T=20.0, bib=bib, guardar_saidas=True)
    S = res["series"]
    dentro, total, larg = 0, 0, []
    pdet = bib.ParamsDetetor()
    for i, o in enumerate(S["saidas"]):
        if S["t"][i] < 4.0 or o.estado not in (0, 1) or not (o.raio_pred > 0):
            continue
        bib.lib.visao_janela_de_previsao(ctypes.byref(o), ctypes.byref(pdet))
        total += 1
        larg.append(pdet.roi_x1 - pdet.roi_x0)
        if pdet.roi_x0 <= S["u_real"][i] < pdet.roi_x1 and pdet.roi_y0 <= S["v_real"][i] < pdet.roi_y1:
            dentro += 1
    c.ok("[§6] JANELA DE BUSCA a partir da previsão (u_prev, v_prev, raio_prev ± 3·raio + 12 px): o alvo REAL cai dentro dela "
         f"em ≥ 99,5 % dos passos do círculo (A_SEGUIR) com meia-largura média de {np.mean(larg) / 2:.0f} px — o detetor passa a "
         "custar a janela, não o frame", total > 1000 and dentro / total >= 0.995 and np.mean(larg) < 120,
         f"{dentro}/{total} dentro; largura média {np.mean(larg):.0f} px")
    return saida


# ============================================================================================ §7 mutações
# (nome, ficheiro, texto original, texto mutado) — a fonte C++ é MUTADA, recompilada de verdade e o mini-teste tem de
# falhar. O texto original tem de aparecer EXATAMENTE uma vez (senão a mutação nem se aplica: falha ALTO).
MUTACOES = (
    ("sinal do yaw", "ibvs.hpp", "yaw_alvo = bruto;", "yaw_alvo = -bruto;"),
    ("atraso ignorado (a captura conta como «agora»: sem desrodar nem extrapolar o atraso)", "ibvs.hpp",
     "uint32_t t_cap = cam.t;", "uint32_t t_cap = t_us;"),
    ("gate de circularidade removido", "visao.hpp", "} else if (circ < p_.circ_min) {", "} else if (false) {"),
    ("gate «cheio» (anel/dispersão) removido", "visao.hpp",
     "} else if (cheio < p_.cheio_min || cheio > p_.cheio_max) {", "} else if (false) {"),
    ("feedforward do yaw desligado", "ibvs.hpp",
     "const float ff = c_.kff_yaw * (w_los + c_.tau_avanco_yaw * a_los) * peso_ff;", "const float ff = 0.0f;"),
    ("desrotação de roll/pitch ignorada", "ibvs.hpp", "geo::rot_zyx(rc, pc, yc), cam.u", "geo::rot_zyx(0.0f, 0.0f, yc), cam.u"),
    ("sinal do v_z", "ibvs.hpp", "vz_alvo = fator * (c_.kp_z *", "vz_alvo = -fator * (c_.kp_z *"),
    ("sinal do erro de distância", "ibvs.hpp", "const float ed = dist - c_.dist_alvo_m;", "const float ed = c_.dist_alvo_m - dist;"),
    ("gate de inovação do KF desligado", "alvo.hpp", "if (modelo_ != ALFA_BETA && y * y > gate_ * gate_ * s) aceita = false;",
     "if (modelo_ != ALFA_BETA && y * y > gate_ * gate_ * s) aceita = true;"),
    ("perda nunca declarada (t_falta infinito)", "ibvs.hpp", "} else if (t_sem > c_.t_falta_s) {\n                estado_ = PERDIDO;",
     "} else if (t_sem > 1.0e9f) {\n                estado_ = PERDIDO;"),
    ("sem histerese na reaquisição", "ibvs.hpp", "if (estado_ == REAQUISICAO && cont_reaq_ >= c_.n_reaq) estado_ = A_SEGUIR;",
     "if (estado_ == REAQUISICAO) estado_ = A_SEGUIR;"),
    ("sem slew no yaw", "ibvs.hpp", "cmd_yaw_ = ibvs_detalhe::desliza(cmd_yaw_, yaw_alvo, c_.yaw_acel_max * dt);", "cmd_yaw_ = yaw_alvo;"),
    ("azimute inercial com os eixos trocados", "alvo.hpp", "*az = atan2f(dw.y, dw.x);", "*az = atan2f(dw.x, dw.y);"),
)


def _frame_sintetico(w: int, h: int, forma: str) -> np.ndarray:
    f = np.full((h, w), 30, np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    if forma == "elipse":       # 2:1 — só a circularidade a distingue de um disco (o «cheio» dá ≈ 1,12)
        f[((xx - 150.0) / 12.0) ** 2 + ((yy - 100.0) / 6.0) ** 2 <= 1.0] = 255
    elif forma == "anel":       # oco — só o «cheio» o distingue (circularidade ≈ 1)
        r2 = (xx - 150.0) ** 2 + (yy - 100.0) ** 2
        f[(r2 <= 14.0 ** 2) & (r2 >= 9.0 ** 2)] = 255
    elif forma == "disco_e_barra":
        f = np.maximum(disco_sintetico(w, h, 100.3, 80.6, 8.0), f)
        f[200:203, 150:280] = 255
    return f


def mini_suite(bib) -> dict[str, bool]:
    """As checagens RÁPIDAS (≈ 2 s) com que se mede cada mutante: uma por mecanismo que a mutação toca."""
    r: dict[str, bool] = {}
    det = sv.DetetorCpp(bib)
    det.params_padrao(320, 240)
    r["detetor: elipse 2:1 recusada (gate de circularidade)"] = not det.detetar(_frame_sintetico(320, 240, "elipse")).valido
    r["detetor: anel oco recusado (gate «cheio»)"] = not det.detetar(_frame_sintetico(320, 240, "anel")).valido
    d = det.detetar(_frame_sintetico(320, 240, "disco_e_barra"))
    r["detetor: disco achado ao lado de uma barra (componentes)"] = bool(d.valido) and math.hypot(d.u - 100.3, d.v - 80.6) < 0.3
    rng = np.random.default_rng(5)
    r["detetor: ruído puro σ = 10 não dá deteções (gate de ruído)"] = not any(
        det.detetar(np.clip(rng.normal(30, 10, (240, 320)), 0, 255).astype(np.uint8)).valido for _ in range(20))
    e = prever_sob_atraso(bib, "circulo", 0.8, 2, T=14.0)
    r["estimador: erro de rumo do círculo a 0,8 m/s < 0,5° (atraso desrodado e previsto)"] = e["rms_epsi_graus"] < 0.5
    eo = prever_sob_atraso(bib, "circulo", 0.5, 2, T=14.0, p_outlier=0.05)
    r["estimador: 5 % de deteções falsas não estragam o rumo (< 1°)"] = eo["rms_epsi_graus"] < 1.0
    m = sv.metricas_laco(sv.simular_laco(sv.trajetoria_alvo("circulo", 0.8), T=18.0, bib=bib))
    r["laço: segue o círculo a 0,8 m/s (rumo RMS < 1,5°, sempre no campo)"] = m["rms_rumo_graus"] < 1.5 and m["frac_campo"] == 1.0
    res = sv.simular_laco(sv.trajetoria_alvo("parado", 0.0, inicio=(2.0, 1.0, 1.8)), T=14.0, bib=bib)
    S = res["series"]
    fim = [i for i in range(len(S["t"])) if S["t"][i] > 11.0]
    r["laço: centra um alvo estático (rumo < 1°, vertical < 5 cm, |D−d*| < 8 cm)"] = (
        max(abs(math.degrees(S["e_psi_real"][i])) for i in fim) < 1.0
        and max(abs(S["dist"][i] * math.sin(S["el_real"][i])) for i in fim) < 0.05 and max(abs(S["d_err"][i]) for i in fim) < 0.08)
    pr = desrodar_pitch_roll(bib, True, T=12.0)
    r["laço: v_z não vê o balanço de pitch/roll (desrotação)"] = pr["std_eel"] < 0.3 and pr["std_vz"] < 0.02
    lg = roteiro(bib, lambda t: not (3.0 <= t < 3.6), T=5.0)
    r["estados: a perda a 300 ms leva a PERDIDO"] = primeira(lg, 2, 3.0) is not None and abs(primeira(lg, 2, 3.0) - 3.39) < 0.05
    lg3 = roteiro(bib, lambda t: (t < 2.0) or (8.0 <= t < 8.04), T=10.0)
    r["estados: UM frame válido em PERDIDO nunca chega a A_SEGUIR (histerese)"] = 0 not in [x[1] for x in lg3 if x[0] >= 8.0]
    lg6 = roteiro(bib, lambda t: True, T=4.0, az_graus=25.0)
    dy = max(abs(lg6[i + 1][4] - lg6[i][4]) / 0.01 for i in range(len(lg6) - 1))
    r["comando: o yaw respeita o slew (≤ yaw_acel_max)"] = dy <= 1.5 * 1.001
    return r


def aplicar_mutacao(raiz_nucleo: Path, ficheiro: str, antigo: str, novo: str) -> None:
    alvo = raiz_nucleo / ficheiro
    texto = alvo.read_text(encoding="utf-8")
    n = texto.count(antigo)
    if n != 1:
        raise AssertionError(f"mutação mal definida: «{antigo[:50]}…» aparece {n}× em {ficheiro} (tem de ser 1)")
    alvo.write_text(texto.replace(antigo, novo), encoding="utf-8")


def secao_mutacoes(c: Checagens, tmp: Path, bib_controlo) -> None:
    base = mini_suite(bib_controlo)
    c.ok("[§7] CONTROLO: o C++ INTACTO passa as " + str(len(base)) + " checagens rápidas da mini-suite (o critério com que se "
         "medem os mutantes)", all(base.values()), "falham: " + str([k for k, v in base.items() if not v]))
    pastas = []
    for i, (nome, ficheiro, antigo, novo) in enumerate(MUTACOES):
        pasta = tmp / f"mut{i}" / "nucleo"
        shutil.copytree(NUCLEO_DIR, pasta, ignore=shutil.ignore_patterns("__pycache__"))
        aplicar_mutacao(pasta, ficheiro, antigo, novo)
        pastas.append(pasta)

    def compilar(p: Path):
        return sv.compilar_visao(p, tmp / "so_mut", limpar=False)
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        sos = list(ex.map(compilar, pastas))
    apanhadas = 0
    for (nome, ficheiro, antigo, novo), so, pasta in zip(MUTACOES, sos, pastas, strict=True):
        bib_m = sv.BibliotecaVisao(so, pasta / "visao_tipos.hpp")
        res = mini_suite(bib_m)
        falhou = [k for k, v in res.items() if not v]
        apanhadas += int(bool(falhou))
        c.ok(f"[§7] MUTAÇÃO «{nome}» ({ficheiro}) é APANHADA", bool(falhou),
             ("falha: " + " | ".join(falhou[:2])) if falhou else "NÃO FOI APANHADA — o teste não a vê")
    c.ok(f"[§7] {apanhadas}/{len(MUTACOES)} mutações da fonte C++ apanhadas (o enunciado pede ≥ 4: sinal do yaw, atraso "
         "ignorado, gate de circularidade, FF)", apanhadas >= 4 and apanhadas == len(MUTACOES))


# ============================================================================================ main
def main() -> int:
    ap = argparse.ArgumentParser(description="prova da atividade C (visão + alvo + IBVS)")
    ap.add_argument("--rapido", action="store_true", help="sem §7 (mutações)")
    ap.add_argument("--secoes", default="0,1,2,3,4,5,6,7", help="lista de secções (ex.: 4,6)")
    args = ap.parse_args()
    secs = set(args.secoes.split(","))
    if args.rapido:
        secs.discard("7")
    print("== teste_visao — atividade C: detetor + estimador do alvo + IBVS em C++ de firmware (SITL + cross M4/M7)")
    c = Checagens("visao")
    t0 = time.time()
    bib = sv.carregar_biblioteca()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        if "0" in secs:
            print("== §0 regras de firmware")
            secao_regras(c)
        if "1" in secs:
            print("== §1 compilação no host + estresse com sanitizers")
            secao_host(c, tmp)
        info: dict = {}
        if "2" in secs:
            print("== §2 compilação cruzada M4/M7 + ciclos (llvm-mca)")
            info = secao_cruzada(c, tmp)
        elif "4" in secs:
            clang, mca = _ferramenta("clang++", "clang"), _ferramenta("llvm-mca")
            info = {"mca": {opt: ciclos_m7(clang, mca, tmp, opt) for opt in ("-Os", "-O2")}}
        if "3" in secs:
            print("== §3 layout das structs e validação de Configs")
            secao_layout(c, tmp, bib)
        if "4" in secs:
            print("== §4 detetor sobre frames renderizados (MuJoCo EGL, luma BT.601)")
            cena = Cena()
            try:
                secao_detetor(c, bib, cena, info["mca"])
            finally:
                cena.fechar()
        if "5" in secs:
            print("== §5 estimador do alvo sob 116 ms de atraso com o drone a rodar")
            secao_estimador(c, bib)
        if "6" in secs:
            print("== §6 lei IBVS: margens, laço fechado cinemático, máquina de estados, saneamento")
            secao_ibvs(c, bib)
        if "7" in secs:
            print("== §7 mutações da fonte C++ (compiladas de verdade)")
            secao_mutacoes(c, tmp, bib)
    n, f = len(c.linhas), len(c.falhas)
    print(f"[teste] {n - f}/{n} checagens OK em {time.time() - t0:.0f} s")
    if f:
        print("FALHARAM:")
        for x in c.falhas:
            print("  -", x[:160])
    else:
        print("o detetor acha o círculo com ≈ 0,1 px, o estimador previne o atraso de câmara, o IBVS segue círculo/oito e a "
              "máquina de estados trata a perda — tudo em C++ float32 sem heap que compila para Cortex-M4/M7")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
