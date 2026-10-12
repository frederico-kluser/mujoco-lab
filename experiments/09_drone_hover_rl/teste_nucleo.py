#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_nucleo.py — PROVA do núcleo de FIRMWARE C++ (`firmware/nucleo/`).

O dono decidiu que estimador + estabilização (+ movimentação e olhar, depois) correm num ARDUINO. Esta é a
base: o que já existe em Python (`fc.py` laço de taxa + mistura + airmode, `estimador.py`) portado para C++17
`float` sem heap, com uma HAL abstrata e um SITL contra o MuJoCo (`sitl.py`). O que se prova:

  §0 REGRAS DE FIRMWARE no código: sem `double`/`new`/`malloc`/`std::`/exceções/RTTI, só <stdint.h>/<math.h>,
     literais em `float` — e o auditor TEM DENTES (apanha violações injetadas);
  §1 (f) COMPILAÇÃO no host: g++ (-O0/-Os/-O2/-O3) e clang++ com -Wall -Wextra -Wdouble-promotion -Werror
     (+ avisos extra), cada cabeçalho auto-suficiente; os flags TÊM DENTES (um `double` injetado falha);
     ESTRESSE com ASan+UBSan (`firmware/teste/estresse.cpp`, g++ e clang++): 400 000 passos de entradas hostis
     (extremos, NaN/inf, dt inválido, modos inexistentes, reinícios/armar/calibrar aleatórios) sem UB/OOB e com
     os invariantes do firmware (motores finitos em [0,1], ≥ idle se armados, 0 se desarmados);
  §2 (d) COMPILAÇÃO CRUZADA com `clang --target=thumbv7em-none-eabihf -ffreestanding -fno-exceptions
     -fno-rtti -Os -Wall -Wextra -Wdouble-promotion -Werror` para Cortex-M4 (Nano 33 BLE) e Cortex-M7
     (H747/Portenta/Nicla/GIGA): `llvm-size` (text/data/bss), `llvm-nm`/`llvm-objdump` sem malloc/new/__cxa_*/
     typeinfo/double; o verificador de símbolos TEM DENTES;
  §3 LAYOUT + CONFIG: structs de ctypes (geradas do config.hpp) ≡ sizeof do C++; `config_de_hardware` ≡
     `ControladorFC` (mesmas fórmulas); `exportar_config_hpp` faz round-trip exato (float32); Configs inválidas
     recusadas; saneamento (NaN → motores a 0), modo reservado, dt inválido;
  §4 (a) EQUIVALÊNCIA UNITÁRIA C++ ≡ Python: laço de taxa+mistura (aleatório realista, SATURAÇÃO do
     diferencial, AIRMODE para cima e para baixo, coletivo fora de faixa, DESARMADO/rearmar, windup do
     integral) com |Δu| ≤ TOL_U, e ESTIMADOR (fluxos de sensores GRAVADOS de um voo de 20 s + fluxos
     sintéticos com ToF/fluxo inválidos, volta do rumo e inclinação perto de 90°) dentro de tolerância float32;
  §5 (b) SHADOW: voo de 20 s com a política `out/real_1950_voo_final/final.zip` (modo comando, sem vento, perfil
     WASDQE): o Python voa, o núcleo C++ corre em paralelo sobre os MESMOS sensores e compara motores e
     estimativas passo a passo (10 000 passos de 500 Hz) — e a sombra não perturba o voo;
  §6 (c) MALHA FECHADA: o mesmo voo com o C++ a mandar nos motores (a política vê as estimativas do C++) em
     várias sementes e em dois cenários (perfil WASDQE e pairagem pura): sobrevive e as métricas (‖xy‖ RMS,
     |Δz|) ficam da MESMA ordem que com o Python; um C++ corrompido NÃO passa;
  §7 (e) MUTAÇÕES: Config corrompida (sinal da mistura, kd = 0, idle, limite do integral…) e FONTE C++
     mutada (sinal do D, sinal da mistura, anti-windup, airmode, PT1, sinal do fluxo, ganho do ToF, decaimento
     sem fluxo, volta do rumo, guarda de Euler…) compilada de verdade — o teste TEM de apanhar cada uma, pelo
     detetor certo: a equivalência C++ ≡ Python, ou o ESTRESSE com sanitizers para o saneamento (que não muda
     nada com entradas normais). O C++ intacto passa o mesmo critério (controlo).

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_nucleo.py
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_nucleo.py --rapido   # sem §6 nem mutações de fonte

Exit 0 = tudo verde; 1 = alguma checagem falhou (ou falta uma ferramenta/política: falha ALTO, nunca salta).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import ctypes
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

import numpy as np
import sitl
from estimador import EstimadorBordo
from fc import ControladorFC
from sitl import FIRMWARE_DIR, NUCLEO_DIR, NucleoCpp

CROSS_DIR = FIRMWARE_DIR / "cross"
ESTRESSE_CPP = FIRMWARE_DIR / "teste" / "estresse.cpp"
PASSOS_ESTRESSE = 400000
MODELO_VOO = sitl.MODELO_VOO
DT = 0.002

# ------------------------------------------------------------------------------------------ tolerâncias
# float32 tem unidade de arredondamento u = 2⁻²⁴ ≈ 6e-8 (relativa); o estimador corre a 500 Hz (N = 10⁴ passos
# em 20 s) e o erro de arredondamento por passo é ≈ u·|estado|. O que o filtro faz com ele fixa a tolerância:
#   · filtros CONTRACTIVOS com ganho k por passo têm um PISO de quantização ≈ u·|estado|/k (o incremento só conta
#     quando o erro passa de meio ulp/k): complementar (roll/pitch) k = K·dt = 1e-3 ⇒ 6e-8·0,3/1e-3 ≈ 2e-5 rad;
#     h/vz (ToF a 30 Hz, k = 0,19) ≈ 6e-8·25/0,19 ≈ 8e-6; vx/vy (α = 0,35) ≈ 2e-7;
#   · integradores puros (ψ, x, y) acumulam ≈ u·|estado|·√N: ψ ≈ 6e-8·π·10² ≈ 2e-5 rad; x, y ≈ 6e-8·8·10² ≈ 5e-5 m;
#   · o laço de taxa não acumula: PT1 contractivo, I limitado a ±0,25; o D tem o cancelamento (giro_f − giro_ant)/dt.
# O MEDIDO fica 10–200× abaixo destes tetos (ver os valores impressos) e 3–6 ordens abaixo do efeito de qualquer
# erro de fórmula (as mutações dão |Δ| ≳ 1e-2).
TOL_U = 1e-5          # |Δu| por motor (medido ≲ 1,3e-6, pior no D com ruído branco: cancelamento (giro_f − giro_ant)/dt);
                      # ≪ 1 LSB do DShot (1/2000 = 5e-4)
TOL_EIXOS = 2e-6      # |Δ u_eixos|/(1+|u|) e |Δ giro_f| (rad/s)
TOL_EST = {           # |Δ| máximo estimativas C++ − Python (voo gravado e fluxos sintéticos)
    "roll": 2e-5, "pitch": 2e-5,    # rad — piso de quantização do complementar (K = 0,5/s)
    "psi": 5e-5,                    # rad — integrador puro
    "h": 1e-4, "vz": 1e-4,          # m, m/s — corrigidos pelo ToF (a_z = soma de termos de ±9,8: cancelamento)
    "vx": 1e-5, "vy": 1e-5,         # m/s — PT1 do fluxo
    "x": 2e-4, "y": 2e-4,           # m — odometria: integrador puro
}
TOL_SOMBRA_U = 1e-5
# Malha fechada: relação C++/Python nas métricas (a física é a mesma; só muda quem estima/controla)
TOL_REL_METRICA = 0.15        # |Δ‖xy‖RMS| ≤ 15 % (medido ≲ 1 %) ...
TOL_ABS_XY = 0.01             # ... + 1 cm
TOL_ABS_DZ = 0.01             # |Δ |Δz| médio| ≤ 1 cm (medido ≲ 1 mm)
SEMENTES = (0, 1, 2)
HOLD = ((0.0, (0.0, 0.0, 0.0)),)
# condições EXTRA (além do voo pedido, sem vento): vento forte com rajadas e domain randomization (peças/bateria/
# sensores sorteados) — onde o acelerómetro mede empuxo+arrasto e os sensores têm mais erro
CONDICOES_EXTRA = (
    ("vento 3 m/s + rajadas", {"vento": (3.0, 0.0, 0.0),
                               "vento_dinamico": {"modo": "rajadas", "p": 0.02, "duracao": 10, "u_max": 3.0}}),
    ("DR (peças/bateria/sensores sorteados) + vento 2 m/s", {"aleatorizar": True, "vento": (2.0, 0.0, 0.0)}),
)


class Checagens:
    def __init__(self, titulo: str) -> None:
        self.titulo, self.linhas, self.falhas = titulo, [], []

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.linhas.append(nome)
        if not cond:
            self.falhas.append(nome)
        print(f"        [{'OK  ' if cond else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""),
              flush=True)
        return bool(cond)


def _f32(a):
    """Arredonda para float32 e devolve float64 — Python e C++ vêem exatamente os mesmos números."""
    return np.asarray(a, dtype=np.float32).astype(np.float64)


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


# regra → regex (aplicada ao código sem comentários/strings)
REGRAS_PROIBIDAS = {
    "double (só float)": r"\bdouble\b",
    "long double": r"\blong\s+double\b",
    "alocação dinâmica (new/delete)": r"\b(new|delete)\b",
    "malloc/calloc/realloc/free/alloca": r"\b(malloc|calloc|realloc|free|alloca)\s*\(",
    "biblioteca padrão C++ (std::)": r"\bstd\s*::",
    "exceções": r"\b(throw|try|catch|noexcept)\b",
    "RTTI": r"\b(typeid|dynamic_cast)\b",
    "literal de ponto flutuante sem sufixo f (double)":
        r"(?<![\w.])(?:\d+\.\d*|\.\d+|\d+(?:\.\d*)?[eE][-+]?\d+)(?![\dfFeE.\w])",
    "include além de <stdint.h>/<math.h>/próprios": r'#\s*include\s*<(?!stdint\.h>|math\.h>)',
}


def auditar_texto(texto: str, permitir_virtual: bool = False) -> list[str]:
    """Violações das regras de firmware num texto C++ (lista de `regra: trecho`)."""
    limpo = _sem_comentarios_e_strings(texto)
    achados = []
    regras = dict(REGRAS_PROIBIDAS)
    if not permitir_virtual:
        regras["virtual (sem vtables no núcleo)"] = r"\bvirtual\b"
    for regra, rx in regras.items():
        for m in re.finditer(rx, limpo):
            achados.append(f"{regra}: «{limpo[max(0, m.start() - 20):m.end() + 20].strip()}»")
    return achados


def secao_regras(c: Checagens) -> None:
    ficheiros = sorted(NUCLEO_DIR.glob("*.[ch]pp"))
    hal = [FIRMWARE_DIR / "hal.hpp", CROSS_DIR / "verifica_hal.cpp"]
    violacoes = {}
    for f in ficheiros:
        v = auditar_texto(f.read_text(encoding="utf-8"))
        if v:
            violacoes[f.name] = v
    for f in hal:
        v = auditar_texto(f.read_text(encoding="utf-8"), permitir_virtual=True)
        if v:
            violacoes[f.name] = v
    c.ok("[§0] núcleo + HAL cumprem as regras de firmware (sem double/new/malloc/std::/exceções/RTTI, "
         "só <stdint.h>/<math.h>, literais float)", not violacoes,
         f"{len(ficheiros) + len(hal)} ficheiros auditados" if not violacoes else str(violacoes))
    # o auditor TEM DENTES: cada violação injetada é apanhada
    injetados = {
        "double": "float f(float x) { double y = x; return (float)y; }",
        "literal sem f": "float f(float x) { return x * 0.5; }",
        "expoente sem f": "const float k = 1e-3;",
        "new": "int* f() { return new int[4]; }",
        "malloc": "void* f() { return malloc(8); }",
        "std::": "#include <stdint.h>\nstd::size_t n;",
        "include <vector>": "#include <vector>\n",
        "throw": "void f() { throw 1; }",
        "typeid": "int f() { return typeid(int).hash_code(); }",
        "virtual no núcleo": "struct A { virtual void f() = 0; };",
    }
    mudos = [k for k, v in injetados.items() if not auditar_texto(v)]
    c.ok("[§0] o auditor TEM DENTES: apanha `double`, literal sem `f`, new, malloc, std::, include extra, "
         "throw, typeid e virtual injetados", not mudos, f"não apanhou: {mudos}" if mudos
         else f"{len(injetados)}/{len(injetados)} violações injetadas apanhadas")
    limpos = ["float f(float x) { return x * 0.5f + 1e-3f; }  // double new malloc em comentário",
              'const char* s = "double new malloc";', "constexpr float k = 3.14159265358979323846f;"]
    falsos = [t for t in limpos if auditar_texto(t)]
    c.ok("[§0] o auditor não dá falsos positivos (literais com `f`, comentários e strings)", not falsos,
         f"falsos positivos: {falsos}" if falsos else "")


# ============================================================================================ §1 host
FLAGS_AVISOS = ["-Wall", "-Wextra", "-Wdouble-promotion", "-Werror"]
FLAGS_EXTRA = ["-Wshadow", "-Wfloat-conversion", "-Wconversion", "-Wundef", "-Wcast-qual"]


def _compilar_host(cxx: str, fonte: Path, saida: Path, opt: str, extra=()) -> subprocess.CompletedProcess:
    return _correr([cxx, "-std=c++17", opt, "-fno-exceptions", "-fno-rtti", *FLAGS_AVISOS, *extra,
                    "-I", FIRMWARE_DIR, "-c", fonte, "-o", saida])


FLAGS_SANITIZERS = ["-std=c++17", "-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    "-fno-omit-frame-pointer", *FLAGS_AVISOS]


def compilar_estresse(cxx: str, raiz_firmware: Path, exe: Path) -> subprocess.CompletedProcess:
    """Compila o driver de estresse + a fonte do núcleo de `raiz_firmware/nucleo` com ASan+UBSan."""
    return _correr([cxx, *FLAGS_SANITIZERS, "-I", raiz_firmware, ESTRESSE_CPP, raiz_firmware / "nucleo" / "nucleo.cpp",
                    "-o", exe])


def correr_estresse(exe: Path, config_bin: Path, passos: int = PASSOS_ESTRESSE) -> dict:
    """Corre o driver (exit 0 = invariantes cumpridos, sem erro de ASan/UBSan) e lê o resumo."""
    r = _correr([exe, config_bin, str(passos)])
    m = re.search(r"violações (\d+) · falhas numéricas sinalizadas (\d+) · passos armados (\d+) · desarmados (\d+)",
                  r.stdout)
    return {"ok": r.returncode == 0 and m is not None and int(m.group(1)) == 0, "codigo": r.returncode,
            "violacoes": int(m.group(1)) if m else -1, "falhas": int(m.group(2)) if m else 0,
            "armados": int(m.group(3)) if m else 0, "desarmados": int(m.group(4)) if m else 0,
            "erro": (r.stderr.strip().splitlines() or [""])[0][:160]}


def secao_host(c: Checagens, tmp: Path, config_bin: Path) -> None:
    gpp = _ferramenta("g++")
    clangpp = _ferramenta("clang++")
    cpps = [NUCLEO_DIR / "nucleo.cpp", NUCLEO_DIR / "capi.cpp", CROSS_DIR / "verifica_hal.cpp"]
    trabalhos = []
    for cxx in (gpp, clangpp):
        for opt in ("-O0", "-Os", "-O2", "-O3"):
            for f in cpps:
                trabalhos.append((cxx, f, opt, FLAGS_EXTRA if cxx == gpp else []))
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_compilar_host, cxx, f, tmp / f"h_{i}.o", opt, extra)
                for i, (cxx, f, opt, extra) in enumerate(trabalhos)]
        resultados = [fu.result() for fu in futs]
    falhas = [(Path(t[0]).name, t[1].name, t[2], r.stderr.strip().splitlines()[:2])
              for t, r in zip(trabalhos, resultados, strict=True) if r.returncode != 0]
    c.ok("[§1] (f) o núcleo, o capi e a HAL compilam no host com -Wall -Wextra -Wdouble-promotion -Werror "
         "(g++ e clang++, -O0/-Os/-O2/-O3; g++ também com " + " ".join(FLAGS_EXTRA) + ")", not falhas,
         f"{len(trabalhos)} compilações" if not falhas else str(falhas))
    # portabilidade de dialeto: o core Arduino mbed compila com gnu++14 (e há cores em C++11/17/20)
    padroes = ("c++11", "c++14", "gnu++14", "c++17", "c++20")
    jobs = [(cxx, f, std) for cxx in (gpp, clangpp) for std in padroes for f in cpps]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_correr, [cxx, f"-std={std}", "-O2", "-fno-exceptions", "-fno-rtti", *FLAGS_AVISOS,
                                    "-I", FIRMWARE_DIR, "-c", f, "-o", tmp / f"std_{i}.o"])
                for i, (cxx, f, std) in enumerate(jobs)]
        res_std = [fu.result() for fu in futs]
    ruins = [(Path(j[0]).name, j[2], j[1].name) for j, r in zip(jobs, res_std, strict=True) if r.returncode != 0]
    c.ok(f"[§1] o núcleo, o capi e a HAL compilam em {', '.join(padroes)} (g++ e clang++) — o core Arduino mbed usa gnu++14",
         not ruins, f"{len(jobs)} compilações" if not ruins else str(ruins))
    # cada cabeçalho é auto-suficiente (compila sozinho)
    cabecalhos = sorted(NUCLEO_DIR.glob("*.hpp")) + [FIRMWARE_DIR / "hal.hpp"]
    mal = []
    for h in cabecalhos:
        tu = tmp / f"auto_{h.name}.cpp"
        tu.write_text(f'#include "{h.resolve()}"\n', encoding="utf-8")
        r = _correr([gpp, "-std=c++17", "-fsyntax-only", "-fno-exceptions", "-fno-rtti", *FLAGS_AVISOS,
                     "-I", FIRMWARE_DIR, tu])
        if r.returncode != 0:
            mal.append((h.name, r.stderr.strip().splitlines()[:1]))
    c.ok("[§1] cada cabeçalho é auto-suficiente (compila sozinho)", not mal,
         f"{len(cabecalhos)} cabeçalhos" if not mal else str(mal))
    # os flags TÊM DENTES: um `double` injetado tem de falhar com -Wdouble-promotion -Werror
    sujo = tmp / "dentes.cpp"
    sujo.write_text("float f(float x) { return x * 0.5; }\n", encoding="utf-8")
    r = _correr([gpp, "-std=c++17", "-O2", "-Wdouble-promotion", "-Werror", "-c", sujo, "-o", tmp / "dentes.o"])
    r2 = _correr([clangpp, "-std=c++17", "-O2", "-Wdouble-promotion", "-Werror", "-c", sujo, "-o", tmp / "d2.o"])
    c.ok("[§1] -Wdouble-promotion -Werror TEM DENTES: `x * 0.5` (promoção a double) faz o g++ e o clang++ falhar",
         r.returncode != 0 and "double-promotion" in r.stderr and r2.returncode != 0,
         (r.stderr.strip().splitlines() or ["?"])[0][-80:])
    # ESTRESSE com sanitizers: entradas hostis (aleatórias, extremas, NaN/inf, dt inválido, modos inexistentes,
    # reinícios/armar/calibrar aleatórios) — sem UB/OOB e com os invariantes do firmware
    for cxx in (gpp, clangpp):
        exe = tmp / f"estresse_{Path(cxx).name}"
        rc = compilar_estresse(cxx, FIRMWARE_DIR, exe)
        if rc.returncode != 0:
            c.ok(f"[§1] estresse com ASan+UBSan ({Path(cxx).name}): compila", False, rc.stderr[:300])
            continue
        e = correr_estresse(exe, config_bin)
        c.ok(f"[§1] ESTRESSE com ASan+UBSan ({Path(cxx).name}): {PASSOS_ESTRESSE} passos de entradas hostis — sem UB/OOB "
             "e invariantes (motores finitos em [0,1] e ≥ idle se armados sem falha; desarmado ⇒ 0; estimativas finitas)",
             e["ok"] and e["falhas"] > 0 and e["armados"] > 0 and e["desarmados"] > 0,
             f"violações {e['violacoes']} · falhas numéricas sinalizadas {e['falhas']} · armados {e['armados']} · "
             f"desarmados {e['desarmados']} {e['erro']}")


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
    r"|__dso_handle|atexit|__aeabi_(d|f2d|i2d|ui2d|l2d|ul2d)|__fixd|__floatd|cxa_guard)")
SECOES_PROIBIDAS = re.compile(r"^\.(init_array|ctors|fini_array|dtors|eh_frame|gcc_except_table|ARM\.extab)")


def compilar_cruzado(clang: str, cpu: tuple, fonte: Path, saida: Path) -> subprocess.CompletedProcess:
    mcpu, mfpu = cpu
    return _correr([clang, *FLAGS_CROSS, f"-mcpu={mcpu}", f"-mfpu={mfpu}", "-I", FIRMWARE_DIR,
                    "-isystem", CROSS_DIR, "-c", fonte, "-o", saida])


def medir_objeto(llvm_size: str, obj: Path) -> dict:
    """text/data/bss do `llvm-size -B` e o detalhe por secção (.text, .ARM.exidx, .rodata)."""
    linha = _correr([llvm_size, "-B", obj]).stdout.strip().splitlines()[-1].split()
    det = {}
    for ln in _correr([llvm_size, "-A", obj]).stdout.splitlines():
        p = ln.split()
        if len(p) >= 2 and p[0].startswith(".") and p[1].isdigit():
            chave = ".ARM.exidx" if p[0].startswith(".ARM.exidx") else (
                ".text" if p[0].startswith(".text") else p[0].split(".")[1] and "." + p[0].split(".")[1])
            det[chave] = det.get(chave, 0) + int(p[1])
    return {"text": int(linha[0]), "data": int(linha[1]), "bss": int(linha[2]), "secoes": det}


def verificar_objeto(llvm_nm: str, llvm_objdump: str, obj: Path, firmware: bool, vtable_ok: bool = False) -> dict:
    """Símbolos indefinidos, instruções de double e secções proibidas de um objeto ARM."""
    indef = [ln.split()[-1] for ln in _correr([llvm_nm, "-u", obj]).stdout.splitlines() if ln.strip()]
    todos = [ln.split()[-1] for ln in _correr([llvm_nm, obj]).stdout.splitlines() if ln.strip()]
    proibidos = sorted({s for s in indef + todos if SIMBOLOS_PROIBIDOS.search(s)
                        and not (vtable_ok and s.startswith("_ZTV"))})
    estranhos = []
    if firmware:                       # o objeto do firmware só pode depender da libm do núcleo + mem*
        estranhos = sorted(s for s in indef if s not in LIBM_PERMITIDA and not RUNTIME_PERMITIDO.match(s))
    dis = _correr([llvm_objdump, "-dr", obj]).stdout
    f64 = len(re.findall(r"\.f64\b", dis))
    secoes = [ln.split()[1] for ln in _correr([llvm_objdump, "-h", obj]).stdout.splitlines()
              if re.match(r"^\s*\d+\s+\S", ln)]
    secoes_ruins = sorted({s for s in secoes if SECOES_PROIBIDAS.match(s)})
    return {"indefinidos": sorted(set(indef)), "proibidos": proibidos, "estranhos": estranhos,
            "f64": f64, "secoes_ruins": secoes_ruins}


def secao_cruzada(c: Checagens, tmp: Path) -> dict:
    clang = _ferramenta("clang++", "clang")
    llvm_size, llvm_nm, llvm_objdump = (_ferramenta(n) for n in ("llvm-size", "llvm-nm", "llvm-objdump"))
    tamanhos = {}
    fontes = {"nucleo": NUCLEO_DIR / "nucleo.cpp", "capi": NUCLEO_DIR / "capi.cpp",
              "hal": CROSS_DIR / "verifica_hal.cpp"}
    for placa, cpu in CPUS.items():
        objs, falhas = {}, []
        for nome, fonte in fontes.items():
            o = tmp / f"{nome}_{cpu[0]}.o"
            r = compilar_cruzado(clang, cpu, fonte, o)
            if r.returncode != 0:
                falhas.append((nome, r.stderr.strip().splitlines()[:2]))
            objs[nome] = o
        c.ok(f"[§2] (d) {placa}: núcleo+capi+HAL compilam com clang --target=thumbv7em-none-eabihf "
             f"-ffreestanding -fno-exceptions -fno-rtti -Os -Wall -Wextra -Wdouble-promotion -Werror "
             f"-mcpu={cpu[0]} -mfpu={cpu[1]}", not falhas, str(falhas) if falhas else "")
        if falhas:
            continue
        r14 = _correr([clang, *[f for f in FLAGS_CROSS if f != "-std=c++17"], "-std=gnu++14", f"-mcpu={cpu[0]}",
                       f"-mfpu={cpu[1]}", "-I", FIRMWARE_DIR, "-isystem", CROSS_DIR, "-c", fontes["nucleo"],
                       "-o", tmp / f"n14_{cpu[0]}.o"])
        c.ok(f"[§2] {placa}: o mesmo núcleo compila com -std=gnu++14 (o dialeto por omissão do core Arduino mbed)",
             r14.returncode == 0, r14.stderr.strip()[:200])
        m = medir_objeto(llvm_size, objs["nucleo"])
        tamanhos[cpu[0]] = m
        exidx = m["secoes"].get(".ARM.exidx", 0)
        c.ok(f"[§2] {placa}: tamanho do núcleo (nucleo.o) = text {m['text']} B (dos quais {exidx} B de "
             f".ARM.exidx) · data {m['data']} B · bss {m['bss']} B", m["text"] > 0 and m["data"] == 0 and m["bss"] == 0,
             "sem variáveis globais: todo o estado vive na instância do chamador")
        # RAM do estado: uma instância GLOBAL compilada para o alvo — tem de cair em .bss (sem imagem em flash) e
        # sem construtor estático (.init_array) nem atexit
        inst = tmp / f"instancia_{cpu[0]}.cpp"
        inst.write_text('#include "nucleo/nucleo.hpp"\nnucleo::Nucleo g_nucleo;\n', encoding="utf-8")
        o_inst = tmp / f"instancia_{cpu[0]}.o"
        r_inst = compilar_cruzado(clang, cpu, inst, o_inst)
        mi = medir_objeto(llvm_size, o_inst) if r_inst.returncode == 0 else {"text": 0, "data": 1, "bss": 0}
        vi = verificar_objeto(llvm_nm, llvm_objdump, o_inst, firmware=False) if r_inst.returncode == 0 else {
            "proibidos": ["?"], "secoes_ruins": ["?"]}
        m["ram_estado"] = mi["bss"]
        c.ok(f"[§2] {placa}: uma instância GLOBAL `nucleo::Nucleo` ocupa {mi['bss']} B de RAM em .bss "
             f"(.data = {mi['data']} B, sem imagem em flash), sem construtor estático (.init_array) nem atexit",
             mi["bss"] > 0 and mi["data"] == 0 and mi["text"] == 0 and not vi["secoes_ruins"] and not vi["proibidos"],
             f"secções proibidas={vi['secoes_ruins']} símbolos={vi['proibidos']}")
        v = verificar_objeto(llvm_nm, llvm_objdump, objs["nucleo"], firmware=True)
        c.ok(f"[§2] {placa}: SEM referências a malloc/new/delete/__cxa_*/typeinfo/vtables/atexit/double "
             f"(llvm-nm) e sem secções de construtores/exceções", not v["proibidos"] and not v["secoes_ruins"],
             f"proibidos={v['proibidos']} secções={v['secoes_ruins']}")
        c.ok(f"[§2] {placa}: símbolos indefinidos do núcleo = só libm {sorted(LIBM_PERMITIDA)} + mem* do "
             f"runtime do compilador", not v["estranhos"],
             f"indefinidos = {v['indefinidos']}" if not v["estranhos"] else f"estranhos = {v['estranhos']}")
        c.ok(f"[§2] {placa}: nenhuma instrução de double no disassembly (llvm-objdump: 0 × `.f64`) nem "
             f"chamadas `__aeabi_d*`", v["f64"] == 0, f"{v['f64']} ocorrências de .f64")
        for nome in ("capi", "hal"):
            vv = verificar_objeto(llvm_nm, llvm_objdump, objs[nome], firmware=False, vtable_ok=(nome == "hal"))
            c.ok(f"[§2] {placa}: {nome}.o (" + ("capi.cpp: só SITL" if nome == "capi" else "HAL de teste: a vtable "
                 "da classe concreta é esperada, sem typeinfo nem __cxa_*") + ") sem símbolos proibidos",
                 not vv["proibidos"] and vv["f64"] == 0, str(vv["proibidos"]))
    # o verificador de símbolos TEM DENTES: um objeto com malloc, new, virtual e double é apanhado
    sujo = tmp / "sujo.cpp"
    sujo.write_text(
        'extern "C" void* malloc(unsigned);\nvoid* operator new(unsigned n) { return malloc(n); }\n'
        "struct B { virtual int f() = 0; };\nstruct D : B { int f() override { return 1; } };\n"
        "int g(int a) { D* d = new D; double x = a * 1.5; return d->f() + (int)x; }\n", encoding="utf-8")
    cpu = next(iter(CPUS.values()))
    o = tmp / "sujo.o"
    r = compilar_cruzado(clang, cpu, sujo, o)
    if r.returncode == 0:
        vs = verificar_objeto(llvm_nm, llvm_objdump, o, firmware=True)
        c.ok("[§2] o verificador TEM DENTES: um objeto com malloc/new/vtable/double é apanhado "
             "(símbolos proibidos e double)", bool(vs["proibidos"]) and (vs["f64"] > 0 or vs["proibidos"]),
             f"proibidos={vs['proibidos'][:4]} f64={vs['f64']}")
    else:
        c.ok("[§2] o verificador TEM DENTES (objeto sujo compila)", False, r.stderr[:200])
    return tamanhos


# ============================================================================================ §3 layout/config
def _env_de_referencia():
    pol, build, _dados = sitl.carregar_politica(MODELO_VOO)
    env = sitl.DroneRealEnv(build=build, comando=True, modo_acao="ctbr", episodio_s=20.0)
    return pol, build, env


def secao_layout_config(c: Checagens, tmp: Path, bib, env) -> None:
    n = {nm: (ctypes.sizeof(getattr(bib, nm)), int(getattr(bib.lib, f"nucleo_tamanho_{nm.lower()}")()))
         for nm in ("Config", "Sensores", "Comando", "Saida")}
    c.ok("[§3] as structs de ctypes (geradas do config.hpp) têm o MESMO sizeof que o C++ "
         "(Config/Sensores/Comando/Saida)", all(a == b for a, b in n.values()),
         " · ".join(f"{k} {a} B" for k, (a, _) in n.items()))
    # o parser de layout é estrito: um campo que não saiba mapear levanta erro em vez de divergir calado
    mau = tmp / "mau.hpp"
    mau.write_text("struct Config { float a; double b; };\nstruct Sensores { float a; };\n"
                   "struct Comando { float a; };\nstruct Saida { float a; };\n", encoding="utf-8")
    try:
        sitl.estruturas_do_header(mau)
        parser_estrito = False
    except ValueError:
        parser_estrito = True
    c.ok("[§3] o parser de layout é ESTRITO: um `double` no struct levanta erro (nada diverge em silêncio)",
         parser_estrito)

    cfg = sitl.config_de_hardware(env.hw, env.model, env.dt)
    ref = ControladorFC(env.hw, env.model, env.dt)
    d = sitl.config_para_dict(cfg)
    rel = lambda a, b: float(np.max(np.abs((np.asarray(a) - np.asarray(b)) / np.asarray(b))))
    err = {"kp": rel(d["kp"], ref.kp), "ki": rel(d["ki"], ref.ki), "kd": rel(d["kd"], ref.kd),
           "mix": float(np.max(np.abs(np.asarray(d["mix"]) - ref.mix))),
           "idle": abs(d["idle"] - ref.idle), "u_pairagem": rel(d["u_pairagem"], ref.u_pairagem),
           "a_giro": rel(_alfa(d["fc_giro_hz"], d["dt_nominal"]), ref.a_giro),
           "a_d": rel(_alfa(d["fc_d_hz"], d["dt_nominal"]), ref.a_d)}
    pior = max(err.values())
    c.ok("[§3] `config_de_hardware` ≡ `ControladorFC` (mesmas fórmulas: planta → kp/ki/kd, mistura, idle, PT1): "
         f"erro relativo máximo {pior:.1e} (arredondamento float32 ≈ 6e-8)", pior < 5e-7,
         " · ".join(f"{k} {v:.0e}" for k, v in err.items()))
    c.ok("[§3] ganhos da planta 1950 mm: kp=" + str(np.round(ref.kp, 4).tolist()) + " ki=" + str(np.round(ref.ki, 4).tolist())
         + " kd=" + str(np.round(ref.kd, 5).tolist()), bool(np.all(ref.kp > 0)))

    # exportar_config_hpp: round-trip EXATO (float32) compilando e a correr um programa que despeja a kConfig
    hpp = sitl.exportar_config_hpp(cfg, tmp / "config_gerada.hpp")
    prog = tmp / "despeja.cpp"
    prog.write_text(f'#include <stdio.h>\n#include "{hpp}"\nint main() {{ fwrite(&kConfig, 1, sizeof(kConfig), stdout); '
                    "return 0; }\n", encoding="utf-8")
    exe = tmp / "despeja"
    r = _correr(["g++", "-std=c++17", "-I", FIRMWARE_DIR, prog, "-o", exe])
    if r.returncode == 0:
        out = subprocess.run([str(exe)], capture_output=True, check=False).stdout
        c.ok("[§3] `exportar_config_hpp` → `constexpr nucleo::Config kConfig` compila e reproduz a Config "
             "BIT A BIT (round-trip float32 com 9 dígitos)", out == bytes(cfg), f"{len(out)} B")
    else:
        c.ok("[§3] `exportar_config_hpp` compila", False, r.stderr[:300])
    tu_cross = tmp / "kconfig_cross.cpp"
    tu_cross.write_text(f'#include "{hpp}"\nstatic_assert(kConfig.versao == nucleo::kVersaoInterface, "versao");\n'
                        "static_assert(kConfig.idle > 0.0f && kConfig.idle < 1.0f, \"idle\");\n", encoding="utf-8")
    r = _correr([_ferramenta("clang++"), *FLAGS_CROSS, "-mcpu=cortex-m4", "-mfpu=fpv4-sp-d16", "-I", FIRMWARE_DIR,
                 "-isystem", CROSS_DIR, "-fsyntax-only", tu_cross])
    c.ok("[§3] a kConfig gerada também compila para Cortex-M4 (constexpr, sem heap)", r.returncode == 0,
         r.stderr.strip()[:200])

    # Configs inválidas são recusadas; o núcleo não iniciado não manda nada
    def recusada(mut) -> bool:
        k = bib.Config.from_buffer_copy(cfg)
        mut(k)
        nuc = NucleoCpp(k, bib)
        return not nuc.iniciado
    casos = {"versão errada": lambda k: setattr(k, "versao", k.versao + 1),
             "kp = NaN": lambda k: k.kp.__setitem__(0, float("nan")),
             "mix = inf": lambda k: k.mix[1].__setitem__(2, float("inf")),
             "fc_giro_hz = 0": lambda k: setattr(k, "fc_giro_hz", 0.0),
             "idle = 1": lambda k: setattr(k, "idle", 1.0),
             "dt_nominal < 0": lambda k: setattr(k, "dt_nominal", -1.0)}
    aceites = [nome for nome, mut in casos.items() if not recusada(mut)]
    c.ok("[§3] iniciar() recusa Configs inválidas (versão, NaN, inf, fc ≤ 0, idle ≥ 1, dt ≤ 0)", not aceites,
         f"aceites por engano: {aceites}" if aceites else f"{len(casos)}/{len(casos)} recusadas")
    nuc = NucleoCpp(bib.Config.from_buffer_copy(cfg), bib)
    k_mau = bib.Config.from_buffer_copy(cfg)
    k_mau.fc_d_hz = 0.0
    morto = NucleoCpp(k_mau, bib)
    sitl.preencher_sensores(morto.sens, (0, 0, 0), (0, 0, 9.81), 1.0, True, 1, (0, 0), True, 1)
    sitl.definir_comando_ctbr(morto.cmd, 0.6, (0, 0, 0))
    s = morto.passo(DT)
    c.ok("[§3] sem iniciar() válido, passo() devolve motores a 0 e kFlagNaoIniciado",
         all(m == 0.0 for m in s.motor) and bool(s.flags & sitl.FLAG_NAO_INICIADO), f"flags={s.flags}")

    # saneamento: NaN no giroscópio → motores a 0 + falha numérica + desarmado; NaN no acelerómetro →
    # o estimador recalibra-se mas o laço de taxa continua; modo reservado = CTBR + flag; dt inválido → nominal
    nuc.reiniciar(); nuc.armar(True)
    sitl.preencher_sensores(nuc.sens, (0.1, -0.1, 0.05), (0.1, 0.2, 9.8), 1.0, True, 1, (0.01, 0.02), True, 1)
    sitl.definir_comando_ctbr(nuc.cmd, 0.6, (0.5, -0.5, 0.1))
    boa = nuc.passo(DT)
    boa_motores = [float(m) for m in boa.motor]
    nuc.sens.giro[0] = float("nan")
    s = nuc.passo(DT)
    c.ok("[§3] saneamento: NaN no giroscópio ⇒ motores a 0, kFlagFalhaNumerica e núcleo desarmado",
         all(m == 0.0 for m in s.motor) and bool(s.flags & sitl.FLAG_FALHA_NUMERICA)
         and not (s.flags & sitl.FLAG_ARMADO), f"flags={s.flags}")
    nuc.reiniciar(); nuc.armar(True)
    sitl.preencher_sensores(nuc.sens, (0.1, -0.1, 0.05), (0.1, 0.2, 9.8), 1.0, True, 1, (0.01, 0.02), True, 1)
    nuc.passo(DT)
    nuc.sens.acc[2] = float("nan")
    s = nuc.passo(DT)
    flags_nan, motores_nan = int(s.flags), [float(m) for m in s.motor]    # `saida` é reutilizada: copiar já
    nuc.sens.acc[2] = 9.8
    nuc.sens.n_tof += 1
    s2 = nuc.passo(DT)
    c.ok("[§3] saneamento: NaN no acelerómetro ⇒ flag de falha, motores finitos (o laço de taxa não depende "
         "dele) e o estimador recalibra-se logo a seguir (estimativas finitas)",
         bool(flags_nan & sitl.FLAG_FALHA_NUMERICA) and all(math.isfinite(m) for m in motores_nan)
         and all(math.isfinite(getattr(s2, k)) for k in sitl.CAMPOS_ESTIMATIVA),
         f"flags={flags_nan}/{s2.flags}")
    nuc.reiniciar(); nuc.armar(True)
    sitl.preencher_sensores(nuc.sens, (0.1, -0.1, 0.05), (0.1, 0.2, 9.8), 1.0, True, 1, (0.01, 0.02), True, 1)
    nuc.passo(DT)
    sitl.definir_comando_ctbr(nuc.cmd, 0.6, (0.5, -0.5, 0.1))
    ctbr = nuc.passo(DT)
    ctbr_u = [float(m) for m in ctbr.motor]
    # (mesmo estado ⇒ repete a sequência com modo = VELOCIDADE e com dt inválido)
    resultados = {}
    for rotulo, mexer in (("reservado", lambda: setattr(nuc.cmd, "modo", sitl.MODO_VELOCIDADE)),
                          ("dt inválido", lambda: None)):
        nuc.reiniciar(); nuc.armar(True)
        sitl.preencher_sensores(nuc.sens, (0.1, -0.1, 0.05), (0.1, 0.2, 9.8), 1.0, True, 1, (0.01, 0.02), True, 1)
        sitl.definir_comando_ctbr(nuc.cmd, 0.6, (0.5, -0.5, 0.1))
        nuc.passo(DT)
        mexer()
        resultados[rotulo] = nuc.passo(DT if rotulo == "reservado" else float("nan"))
        resultados[rotulo] = ([float(m) for m in resultados[rotulo].motor], int(resultados[rotulo].flags))
    c.ok("[§3] modo VELOCIDADE/OLHAR (reservado): trata como CTBR com os campos coletivo/taxas e levanta "
         "kFlagModoReservado", resultados["reservado"][0] == ctbr_u
         and bool(resultados["reservado"][1] & sitl.FLAG_MODO_RESERVADO), f"flags={resultados['reservado'][1]}")
    c.ok("[§3] dt inválido (NaN) ⇒ usa o dt_nominal da Config (mesma saída que com dt = 2 ms)",
         resultados["dt inválido"][0] == ctbr_u, "")
    del boa_motores


def _alfa(fc_hz: float, dt: float) -> float:
    rc = 1.0 / (2.0 * math.pi * fc_hz)
    return dt / (rc + dt)


# ============================================================================================ §4 (a) taxa
def gerar_cenario(nome: str, n: int, rng: np.random.Generator) -> dict:
    """Entradas por passo do laço de taxa: armado, coletivo, setpoints (p,q,r) e giroscópio (rad/s)."""
    escala = np.array([2.0, 2.0, 1.0])
    ar = np.zeros((n, 3))
    for k in range(1, n):
        ar[k] = 0.97 * ar[k - 1] + 0.25 * rng.normal(size=3) * np.array([1.0, 1.0, 0.5])
    def por_blocos(passo_bloco: int, gerador):
        out = np.zeros((n,) + np.shape(gerador()))
        for k in range(0, n, passo_bloco):
            out[k:k + passo_bloco] = gerador()
        return out
    armado = np.ones(n, dtype=bool)
    giro, col = ar.copy(), por_blocos(50, lambda: 0.35 + 0.5 * rng.random())
    sp = por_blocos(25, lambda: rng.uniform(-1, 1, 3) * escala)
    if nome == "saturacao":                     # o diferencial não cabe em [idle,1] → escala
        sp = por_blocos(40, lambda: np.sign(rng.normal(size=3)) * np.array([40.0, 40.0, 20.0]))
        giro, col = 0.1 * ar, por_blocos(40, lambda: 0.4 + 0.4 * rng.random())
    elif nome == "airmode_baixo_motor":         # coletivo alto + diferencial → um motor passaria de 1
        col = por_blocos(30, lambda: 0.93 + 0.07 * rng.random())
        sp = por_blocos(25, lambda: rng.uniform(-1, 1, 3) * np.array([2.0, 2.0, 0.1]))
    elif nome == "airmode_alto_motor":          # coletivo ~0 + diferencial → um motor ficaria abaixo do idle
        col = por_blocos(30, lambda: 0.06 * rng.random())
        sp = por_blocos(25, lambda: rng.uniform(-1, 1, 3) * np.array([2.0, 2.0, 0.1]))
    elif nome == "coletivo_fora":               # coletivo fora de [0,1]
        col = por_blocos(20, lambda: rng.choice([-0.5, 1.7, 0.5, -1e3, 1e3, 0.0, 1.0]))
    elif nome == "desarmar_rearmar":
        armado[300:500] = False
        armado[800:900] = False
    elif nome == "windup":                      # erro persistente: o integral tem de parar no limite
        giro = np.zeros((n, 3))
        sp = np.tile(np.array([2.0, -2.0, 1.0]), (n, 1))
        col = np.full(n, 0.5)
    elif nome != "realista":
        raise KeyError(nome)
    return {"armado": armado, "col": _f32(col), "sp": _f32(sp), "giro": _f32(giro)}


CENARIOS_TAXA = (("realista", 4000), ("saturacao", 1500), ("airmode_baixo_motor", 1500),
                 ("airmode_alto_motor", 1500), ("coletivo_fora", 1000), ("desarmar_rearmar", 1200),
                 ("windup", 1500))


def rodar_taxa(bib, cfg, env, nome: str, n: int, semente: int = 0) -> dict:
    """Um cenário do laço de taxa+mistura: C++ vs `ControladorFC` com as MESMAS entradas (float32)."""
    cen = gerar_cenario(nome, n, np.random.default_rng(semente))
    ref = ControladorFC(env.hw, env.model, DT)
    nuc = NucleoCpp(cfg, bib).exigir_iniciado()
    nuc.reiniciar()
    ref.reiniciar()
    du_max = ge_max = ue_max = 0.0
    flags = 0
    zeros_ok = True
    for k in range(n):
        arm = bool(cen["armado"][k])
        ref.armar(arm)
        nuc.armar(arm)
        sitl.preencher_sensores(nuc.sens, cen["giro"][k], (0.0, 0.0, 9.81), 1.0, True, 1, (0.0, 0.0), True, 1)
        sitl.definir_comando_ctbr(nuc.cmd, cen["col"][k], cen["sp"][k])
        u_ref = ref.passo(float(cen["col"][k]), cen["sp"][k], cen["giro"][k])
        out = nuc.passo(DT)
        u_cpp = np.array(out.motor, dtype=float)
        du_max = max(du_max, float(np.max(np.abs(u_cpp - u_ref))))
        flags |= int(out.flags)
        if not arm:
            zeros_ok = zeros_ok and bool(np.all(u_cpp == 0.0)) and bool(np.all(u_ref == 0.0))
        else:
            ge_max = max(ge_max, float(np.max(np.abs(np.array(out.giro_f) - ref.giro_f))))
            u_eix = ref.kp * (cen["sp"][k] - ref.giro_f) + ref.integral - ref.kd * ref.d_f
            ue_max = max(ue_max, float(np.max(np.abs(np.array(out.u_eixos) - u_eix) / (1.0 + np.abs(u_eix)))))
    nuc.close()
    return {"du_max": du_max, "giro_f_max": ge_max, "u_eixos_rel_max": ue_max, "flags": flags,
            "desarmado_zero": zeros_ok}


def secao_taxa(c: Checagens, bib, cfg, env) -> None:
    pior_u = pior_e = 0.0
    flags = 0
    detalhes = []
    for nome, n in CENARIOS_TAXA:
        r = rodar_taxa(bib, cfg, env, nome, n)
        pior_u = max(pior_u, r["du_max"])
        pior_e = max(pior_e, r["giro_f_max"], r["u_eixos_rel_max"])
        flags |= r["flags"]
        detalhes.append(f"{nome} {r['du_max']:.1e}")
        c.ok(f"[§4] (a) laço de taxa+mistura, cenário «{nome}» ({n} passos): |Δu| = {r['du_max']:.2e} ≤ "
             f"{TOL_U:.0e}; giro_f/u_eixos {max(r['giro_f_max'], r['u_eixos_rel_max']):.1e} ≤ {TOL_EIXOS:.0e}",
             r["du_max"] <= TOL_U and max(r["giro_f_max"], r["u_eixos_rel_max"]) <= TOL_EIXOS
             and r["desarmado_zero"], "desarmado ⇒ u = 0 exato" if nome == "desarmar_rearmar" else "")
    c.ok("[§4] os cenários exercem TODOS os ramos da mistura: armado, diferencial escalado (saturação), "
         "airmode para baixo e para cima", all(flags & b for b in (sitl.FLAG_ARMADO, sitl.FLAG_DIF_ESCALADO,
         sitl.FLAG_AIRMODE_BAIXO, sitl.FLAG_AIRMODE_ALTO)), f"flags vistas = {flags:#06b}")
    c.ok(f"[§4] (a) pior |Δu| do laço de taxa+mistura em {len(CENARIOS_TAXA)} cenários = {pior_u:.2e} "
         f"(critério ≤ ~1e-5; usado {TOL_U:.0e})", pior_u <= TOL_U, " · ".join(detalhes))


# ============================================================================================ §4 (a) estimador
class _GravadorEstimador:
    """Envolve o `EstimadorBordo` do env: grava as entradas de cada `passo` e o estado depois dele."""

    def __init__(self, est):
        self._est = est
        self.entradas, self.saidas, self.reset, self.est0 = [], [], None, None

    @staticmethod
    def _estado(e) -> list:
        return [e.roll, e.pitch, e.psi, e.h, e.vz, e.vx, e.vy, e.x, e.y]

    def reiniciar(self, acc, tof_d, tof_ok):
        self._est.reiniciar(acc, tof_d, tof_ok)
        self.reset = (tuple(float(v) for v in acc), float(tof_d), bool(tof_ok))
        self.est0 = self._estado(self._est)
        self.entradas.clear()
        self.saidas.clear()

    def passo(self, giro, acc, tof_d, tof_ok, n_tof, fluxo, fluxo_ok, n_fluxo):
        self.entradas.append((*(float(v) for v in giro), *(float(v) for v in acc), float(tof_d), bool(tof_ok),
                              int(n_tof), *(float(v) for v in fluxo), bool(fluxo_ok), int(n_fluxo)))
        self._est.passo(giro, acc, tof_d, tof_ok, n_tof, fluxo, fluxo_ok, n_fluxo)
        self.saidas.append(self._estado(self._est))

    def __getattr__(self, nome):                 # roll, pitch, … para o env.observacao()
        return getattr(self._est, nome)


def gravar_voo_python(build, politica, seed: int = 0, segundos: float = 20.0) -> dict:
    """Voo de referência (Python) com os sensores e o estado do estimador GRAVADOS em cada passo de física."""
    env = sitl.criar_env(build, segundos, "python")
    grav = _GravadorEstimador(env.estimador)
    env.estimador = grav
    r = sitl.voar(env, politica, segundos, seed=seed)
    return {"voo": r, "reset": grav.reset, "est0": np.array(grav.est0), "entradas": grav.entradas,
            "saidas": np.array(grav.saidas)}


def _preencher_de_tuplo(s, e) -> None:
    sitl.preencher_sensores(s, e[0:3], e[3:6], e[6], e[7], e[8], e[9:11], e[11], e[12])


def comparar_estimador(bib, cfg, reset, est0, entradas, saidas, n: int | None = None) -> dict:
    """Reproduz um fluxo de sensores no núcleo C++ e compara as 9 estimativas com as do Python, passo a passo."""
    nuc = NucleoCpp(cfg, bib).exigir_iniciado()
    nuc.reiniciar()
    acc, tof_d, tof_ok = reset
    sitl.preencher_sensores(nuc.sens, (0, 0, 0), acc, tof_d, tof_ok, 0, (0, 0), False, 0)
    nuc.calibrar()
    e0 = np.array([getattr(nuc.saida, k) for k in sitl.CAMPOS_ESTIMATIVA])
    calibracao = float(np.max(np.abs(e0 - est0)))
    n = len(entradas) if n is None else min(n, len(entradas))
    dif = np.zeros((n, 9))
    psi_max = 0.0
    for k in range(n):
        _preencher_de_tuplo(nuc.sens, entradas[k])
        sitl.definir_comando_ctbr(nuc.cmd, 0.0, (0, 0, 0))
        out = nuc.passo(DT)
        dif[k] = np.array([getattr(out, nm) for nm in sitl.CAMPOS_ESTIMATIVA]) - saidas[k]
        psi_max = max(psi_max, abs(float(out.psi)))
    nuc.close()
    # (sem tolerância a voltas de 2π: um rumo que não envolve tem de FALHAR; a comparação é direta e o ψ do
    #  C++ tem de ficar em [−π, π])
    maximo = {nm: float(np.max(np.abs(dif[:, i]))) for i, nm in enumerate(sitl.CAMPOS_ESTIMATIVA)}
    return {"max": maximo, "calibracao": calibracao, "n": n, "finito": bool(np.isfinite(dif).all()),
            "psi_max": psi_max}


def fluxo_sintetico(semente: int, n: int, dt: float = DT, tumble: bool = False) -> dict:
    """Fluxo de sensores SINTÉTICO que exerce o que o voo real não exerce: ToF/fluxo INVÁLIDOS em blocos,
    contadores de amostra a 30/100 Hz, a volta do rumo (ψ passa ±π), picos no acelerómetro; com `tumble`
    a inclinação sobe a ≈ 90° (o ramo |cosθ| ≤ 1e-3 do estimador)."""
    rng = np.random.default_rng(semente)
    t = np.arange(n) * dt
    if tumble:                                        # pitch estático a 89,97° (cos = 5,2e-4 < 1e-3): ramo do guarda
        th = np.full(n, math.radians(89.97))
        ph = np.zeros(n)
        r = np.full(n, 0.05)                          # guinada constante: sem o guarda dpsi = r/cosθ ≈ 96 rad/s
    else:
        ph = 0.25 * np.sin(2 * math.pi * t / 7.0)
        th = 0.2 * np.sin(2 * math.pi * t / 5.0 + 1.0)
        r = 0.6 * np.sin(2 * math.pi * t / 9.0) + np.where((t > 6.0) & (t < 14.0), 1.0, 0.0)   # ψ passa ±π
    p = np.gradient(ph, dt) if not tumble else np.zeros(n)
    q = np.gradient(th, dt) if not tumble else np.zeros(n)
    # No ramo do guarda o ruído tem de ser ≈ 0: o ruído do giroscópio faria o θ andar ao acaso para fora de
    # |cosθ| ≤ 1e-3 e aí tan θ ≈ 10³ amplifica qualquer diferença float32/float64 (singularidade de Euler,
    # não um erro do porte); o do acelerómetro tem de ser ≪ g·cosθ = 5 mm/s².
    giro = np.stack([p, q, r], axis=1) + rng.normal(0, 0.0 if tumble else 0.01, (n, 3))
    g = 9.81
    acc = np.stack([-g * np.sin(th), g * np.sin(ph) * np.cos(th), g * np.cos(ph) * np.cos(th)], axis=1)
    acc = acc + rng.normal(0, 1e-5 if tumble else 0.05, (n, 3))
    picos = (rng.random(n) < 0.002) & (not tumble)
    acc[picos] += rng.normal(0, 3.0, (int(picos.sum()), 3))
    h = 1.0 + 0.3 * np.sin(2 * math.pi * t / 4.0)
    tof = np.where(tumble, 0.8, h / np.maximum(np.cos(ph) * np.cos(th), 0.05)) + rng.normal(0, 0.004, n)
    fluxo = rng.normal(0, 0.4, (n, 2))
    n_tof = (t / (1 / 30.0)).astype(int)
    n_fluxo = (t / 0.01).astype(int)
    def blocos(frac: float, bloco: int):
        ok = np.ones(n, dtype=bool)
        for k in range(0, n, bloco):
            if rng.random() < frac:
                ok[k:k + bloco] = False
        return ok
    tof_ok, fluxo_ok = blocos(0.2, 250), blocos(0.2, 150)
    entradas = [(*giro[k], *acc[k], float(tof[k]), bool(tof_ok[k]), int(n_tof[k]), *fluxo[k],
                 bool(fluxo_ok[k]), int(n_fluxo[k])) for k in range(n)]
    return {"entradas": entradas, "reset": (tuple(acc[0]), float(tof[0]), True)}


def python_do_fluxo(fl: dict) -> dict:
    est = EstimadorBordo(DT)
    acc, tof_d, tof_ok = fl["reset"]
    est.reiniciar(acc, tof_d, tof_ok)
    est0 = np.array(_GravadorEstimador._estado(est))
    saidas = []
    for e in fl["entradas"]:
        est.passo(e[0:3], e[3:6], e[6], e[7], e[8], e[9:11], e[11], e[12])
        saidas.append(_GravadorEstimador._estado(est))
    return {"est0": est0, "saidas": np.array(saidas)}


def _tolerado(max_dict: dict, escala: float = 1.0) -> list[str]:
    return [f"{k} {v:.1e}>{TOL_EST[k] * escala:.0e}" for k, v in max_dict.items() if v > TOL_EST[k] * escala]


def secao_estimador(c: Checagens, bib, cfg, gravacao: dict) -> None:
    r = comparar_estimador(bib, cfg, gravacao["reset"], gravacao["est0"], gravacao["entradas"],
                           gravacao["saidas"])
    fora = _tolerado(r["max"])
    c.ok(f"[§4] (a) ESTIMADOR: fluxo de sensores GRAVADO de um voo de 20 s ({r['n']} passos de 500 Hz, ToF+fluxo "
         f"+IMU medidos): C++ float32 ≡ Python float64 — max|Δ| " + " ".join(
             f"{k} {v:.1e}" for k, v in r["max"].items()), not fora and r["finito"], str(fora) if fora else
         "dentro das tolerâncias float32 (pisos de quantização no topo do ficheiro; medido 10–200× abaixo)")
    c.ok(f"[§4] a calibração do estimador (roll/pitch do acelerómetro, altura do ToF) coincide com o "
         f"`EstimadorBordo.reiniciar`: max|Δ| = {r['calibracao']:.1e}", r["calibracao"] < 1e-6)
    for nome, kw, n in (("sintético: ToF/fluxo inválidos em blocos, volta do rumo, picos no acelerómetro",
                         {"tumble": False}, 10000),
                        ("sintético: inclinação ≈ 90° (ramo |cosθ| ≤ 1e-3 do estimador)", {"tumble": True}, 12000)):
        fl = fluxo_sintetico(7, n, **kw)
        py = python_do_fluxo(fl)
        rs = comparar_estimador(bib, cfg, fl["reset"], py["est0"], fl["entradas"], py["saidas"])
        # perto de 90° o piso de quantização float32 do filtro complementar sobe: o incremento por passo
        # (dt·K·erro ≈ 1e-3·erro) só passa a contar quando erro > ulp(θ)/2/(K·dt) = u·|θ|/(K·dt) ≈ 6e-5·|θ|
        # (≈ 9e-5 rad com |θ| ≈ π/2, medido 5e-5) — daí a escala ×8 só neste fluxo
        fora = _tolerado(rs["max"], 8.0 if kw["tumble"] else 1.0)
        if rs["psi_max"] > math.pi + 1e-5:
            fora = [*fora, f"ψ saiu de [−π, π] ({rs['psi_max']:.3f})"]
        extra = f"ψ do C++ sempre em [−π, π] (máx |ψ| = {rs['psi_max']:.3f})"
        if kw["tumble"]:                              # o ramo do guarda foi MESMO exercido (no Python e no C++)
            em_guarda = float(np.mean(np.abs(np.cos(py["saidas"][:, 1])) <= 1e-3))
            fora = fora or ([] if em_guarda > 0.95 else [f"guarda só em {em_guarda:.0%} dos passos"])
            extra += f" · |cosθ| ≤ 1e-3 em {em_guarda:.0%} dos passos"
        c.ok(f"[§4] (a) ESTIMADOR {nome} ({rs['n']} passos): max|Δ| " + " ".join(
            f"{k} {v:.1e}" for k, v in rs["max"].items()), not fora and rs["finito"], str(fora) if fora else extra)
    fl = fluxo_sintetico(7, 6000)
    # os ramos de decaimento sem fluxo e de ToF inválido foram exercidos de facto
    n_inv = sum(1 for e in fl["entradas"] if not e[7] or not e[11])
    c.ok("[§4] os fluxos sintéticos exercem os ramos de ToF/fluxo INVÁLIDOS (decaimento) e a volta do rumo",
         n_inv > 200, f"{n_inv} passos com ToF ou fluxo inválido de 6000")


# ============================================================================================ §5 (b) sombra
def secao_sombra(c: Checagens, build, politica, ref_py: dict, bib) -> None:
    env = sitl.criar_env(build, 20.0, "sombra", biblioteca=bib)
    t0 = time.perf_counter()
    r = sitl.voar(env, politica, 20.0, seed=0)
    s = env.resumo_sombra()
    c.ok("[§5] (b) SHADOW: voo de 20 s (política real_1950_voo_final, modo comando, sem vento, perfil WASDQE) "
         f"completo com {s['passos']} passos de 500 Hz comparados ({time.perf_counter() - t0:.1f} s de parede)",
         s["passos"] == 10000 and not r["terminou"], f"decisões={r['decisoes']}")
    c.ok(f"[§5] SHADOW motores: max|Δu| C++ − Python = {s['du_max']:.2e} (RMS {s['du_rms']:.1e}) ≤ "
         f"{TOL_SOMBRA_U:.0e}", s["du_max"] <= TOL_SOMBRA_U, "por motor: " + " ".join(
             f"{v:.1e}" for v in s["du_por_motor_max"]))
    fora = _tolerado(s["est_max"])
    c.ok("[§5] SHADOW estimativas passo a passo: max|Δ| " + " ".join(f"{k} {v:.1e}" for k, v in s["est_max"].items()),
         not fora, str(fora) if fora else "dentro das tolerâncias float32")
    exercidos = all(s["flags"] & b for b in (sitl.FLAG_ARMADO,))
    c.ok("[§5] o shadow viu o núcleo armado em todo o voo e sem falhas numéricas",
         exercidos and not (s["flags"] & (sitl.FLAG_FALHA_NUMERICA | sitl.FLAG_NAO_INICIADO)), f"flags={s['flags']:#x}")
    # (a planta do MuJoCo não é reprodutível BIT a bit de uma execução para outra — dois voos só-Python com a
    #  mesma semente divergem ~1e-4 m nas métricas por ruído numérico da planta, medido; a sombra é só-leitura:
    #  devolve o `u` do Python — por isso o critério é a banda desse ruído, não a igualdade exata)
    d_xy = abs(r["xy_rms"] - ref_py["voo"]["xy_rms"])
    d_dz = abs(r["dz_medio"] - ref_py["voo"]["dz_medio"])
    c.ok("[§5] a sombra NÃO perturba o voo: as métricas coincidem com as do mesmo voo só com Python dentro do ruído "
         f"da planta (‖xy‖ RMS {r['xy_rms']:.4f} vs {ref_py['voo']['xy_rms']:.4f} m, |Δz| {r['dz_medio']:.4f} vs "
         f"{ref_py['voo']['dz_medio']:.4f} m)", d_xy <= 5e-3 and d_dz <= 2e-3,
         f"Δ‖xy‖ {d_xy * 1e3:.2f} mm (≤ 5) · Δ|Δz| {d_dz * 1e3:.3f} mm (≤ 2)")
    # extra: a mesma equivalência passo a passo com vento forte + rajadas e com domain randomization
    for nome, kw in CONDICOES_EXTRA:
        e2 = sitl.criar_env(build, 20.0, "sombra", biblioteca=bib, **kw)
        r2 = sitl.voar(e2, politica, 20.0, seed=3)
        s2 = e2.resumo_sombra()
        fora2 = _tolerado(s2["est_max"])
        c.ok(f"[§5] SHADOW extra «{nome}»: {s2['passos']} passos — max|Δu| {s2['du_max']:.2e} ≤ {TOL_SOMBRA_U:.0e} e "
             "estimativas " + " ".join(f"{k} {v:.1e}" for k, v in s2["est_max"].items()),
             s2["du_max"] <= TOL_SOMBRA_U and not fora2 and not r2["terminou"],
             str(fora2) if fora2 else f"voo sobreviveu (‖xy‖ RMS {r2['xy_rms']:.3f} m)")


# ============================================================================================ §6 (c) malha fechada
def secao_malha_fechada(c: Checagens, build, politica, ref_py: dict, bib, cfg) -> None:
    linhas = []
    for nome_cen, perfil in (("perfil WASDQE", sitl.PERFIL_VOO), ("pairagem pura", HOLD)):
        for seed in SEMENTES:
            if nome_cen == "perfil WASDQE" and seed == 0:
                py = ref_py["voo"]                                      # o voo já feito (gravado)
            else:
                py = sitl.voar(sitl.criar_env(build, 20.0, "python"), politica, 20.0, seed=seed, perfil=perfil)
            cpp = sitl.voar(sitl.criar_env(build, 20.0, "sitl", biblioteca=bib), politica, 20.0, seed=seed,
                            perfil=perfil)
            d_xy = abs(cpp["xy_rms"] - py["xy_rms"])
            d_dz = abs(cpp["dz_medio"] - py["dz_medio"])
            ok = (not cpp["terminou"] and not py["terminou"] and d_xy <= TOL_REL_METRICA * py["xy_rms"] + TOL_ABS_XY
                  and d_dz <= TOL_ABS_DZ)
            linhas.append((nome_cen, seed, py, cpp, ok))
            c.ok(f"[§6] (c) MALHA FECHADA «{nome_cen}» semente {seed}: o C++ manda nos motores e a política vê "
                 f"as estimativas do C++ — sobrevive 20 s; ‖xy‖ RMS C++ {cpp['xy_rms']:.3f} m vs Python "
                 f"{py['xy_rms']:.3f} m · |Δz| médio {cpp['dz_medio']:.3f} vs {py['dz_medio']:.3f} m "
                 f"(máx {cpp['dz_max']:.3f} vs {py['dz_max']:.3f})", ok,
                 f"Δ‖xy‖ {d_xy * 100:.1f} cm (≤ {100 * (TOL_REL_METRICA * py['xy_rms'] + TOL_ABS_XY):.1f}) · "
                 f"Δ|Δz| {d_dz * 1000:.1f} mm (≤ {TOL_ABS_DZ * 1000:.0f})")
    rel = [abs(cpp["xy_rms"] - py["xy_rms"]) / max(py["xy_rms"], 1e-9) for _, _, py, cpp, _ in linhas]
    c.ok(f"[§6] resumo: {len(linhas)} voos C++ vs Python — diferença relativa de ‖xy‖ RMS: máx {max(rel) * 100:.1f} % "
         f"(mediana {np.median(rel) * 100:.1f} %)", max(rel) <= TOL_REL_METRICA, "")
    for nome, kw in CONDICOES_EXTRA:
        py2 = sitl.voar(sitl.criar_env(build, 20.0, "python", **kw), politica, 20.0, seed=3)
        cpp2 = sitl.voar(sitl.criar_env(build, 20.0, "sitl", biblioteca=bib, **kw), politica, 20.0, seed=3)
        d_xy2, d_dz2 = abs(cpp2["xy_rms"] - py2["xy_rms"]), abs(cpp2["dz_medio"] - py2["dz_medio"])
        c.ok(f"[§6] (c) MALHA FECHADA extra «{nome}»: o C++ sobrevive 20 s; ‖xy‖ RMS C++ {cpp2['xy_rms']:.3f} m vs "
             f"Python {py2['xy_rms']:.3f} m · |Δz| médio {cpp2['dz_medio']:.3f} vs {py2['dz_medio']:.3f} m",
             not cpp2["terminou"] and not py2["terminou"]
             and d_xy2 <= TOL_REL_METRICA * py2["xy_rms"] + TOL_ABS_XY and d_dz2 <= TOL_ABS_DZ,
             f"Δ‖xy‖ {d_xy2 * 100:.1f} cm · Δ|Δz| {d_dz2 * 1000:.1f} mm")
    # INTERFACE PRONTA para os laços externos: um comando em modo VELOCIDADE (campos vx,vy,vz,yaw_taxa) chega ao núcleo
    # pelo gancho do SITL, é tratado como CTBR (os laços externos ainda NÃO existem) e levanta kFlagModoReservado
    env_v = sitl.criar_env(build, 6.0, "sitl", biblioteca=bib)
    vistos = []

    def gancho(cmd, _sens):
        cmd.modo = sitl.MODO_VELOCIDADE
        cmd.vx, cmd.vy, cmd.vz, cmd.yaw_taxa = 0.5, -0.2, 0.1, 0.05
        vistos.append(int(env_v.nucleo.saida.flags))

    env_v.fc.preparar_comando = gancho
    rv = sitl.voar(env_v, politica, 6.0, seed=0, perfil=HOLD)
    c.ok("[§6] interface preparada para os laços externos: um Comando em modo VELOCIDADE (vx,vy,vz,yaw_taxa) chega ao "
         "núcleo pelo gancho do SITL e é tratado como CTBR com kFlagModoReservado — o voo não muda (sobrevive 6 s)",
         not rv["terminou"] and len(vistos) > 1000 and bool(vistos[-1] & sitl.FLAG_MODO_RESERVADO),
         f"{len(vistos)} passos com o modo VELOCIDADE; flags no fim = {vistos[-1]:#x}")
    # NÃO-TAUTOLOGIA: um núcleo corrompido (sinal da guinada na mistura trocado) NÃO passa o mesmo critério
    k = bib.Config.from_buffer_copy(cfg)
    for i in range(4):
        k.mix[i][2] = -k.mix[i][2]
    env_mau = sitl.criar_env(build, 20.0, "sitl", biblioteca=bib, cfg=k)
    mau = sitl.voar(env_mau, politica, 20.0, seed=0)
    py0 = ref_py["voo"]
    degradou = mau["terminou"] or abs(mau["xy_rms"] - py0["xy_rms"]) > TOL_REL_METRICA * py0["xy_rms"] + TOL_ABS_XY
    c.ok("[§6] NÃO-TAUTOLOGIA: com a guinada da mistura trocada de sinal o voo C++ cai ou sai do critério "
         f"(caiu={mau['terminou']}, ‖xy‖ RMS {mau['xy_rms']:.2f} m vs {py0['xy_rms']:.2f} m)", degradou)


# ============================================================================================ §7 (e) mutações
def mutar_config(bib, cfg, nome: str):
    k = bib.Config.from_buffer_copy(cfg)
    if nome == "sinal da mistura (guinada)":
        for i in range(4):
            k.mix[i][2] = -k.mix[i][2]
    elif nome == "sinal da mistura (roll)":
        for i in range(4):
            k.mix[i][0] = -k.mix[i][0]
    elif nome == "kd = 0 (sem termo D)":
        for e in range(3):
            k.kd[e] = 0.0
    elif nome == "idle = 0":
        k.idle = 0.0
    elif nome == "limite do integral ×4":
        k.limite_i = 4 * k.limite_i
    elif nome == "ki roll −10 %":
        k.ki[0] = 0.9 * k.ki[0]
    else:
        raise KeyError(nome)
    return k


MUTACOES_CONFIG = ("sinal da mistura (guinada)", "sinal da mistura (roll)", "kd = 0 (sem termo D)", "idle = 0",
                   "limite do integral ×4", "ki roll −10 %")
# (ficheiro, âncora EXATA, substituição, descrição, detetor) — a âncora tem de existir UMA vez (senão o teste falha:
# uma mutação que já não se aplica não pode passar em silêncio). Detetor "equiv" = o teste de equivalência C++ ≡
# Python; "estresse" = o driver de estresse com sanitizers (entradas hostis: o que NÃO muda o comportamento
# normal — o saneamento — só se vê com NaN/inf/extremos).
MUTACOES_FONTE = (
    ("taxa.hpp", "+ integral_[e] - c.kd[e] * d_f_[e]", "+ integral_[e] + c.kd[e] * d_f_[e]",
     "sinal do termo D", "equiv"),
    ("taxa.hpp", "+ c.mix[i][2] * u_eixos[2];", "- c.mix[i][2] * u_eixos[2];",
     "sinal da guinada na mistura", "equiv"),
    ("taxa.hpp", "limita(integral_[e] + c.ki[e] * erro * dt, -c.limite_i, c.limite_i)",
     "integral_[e] + c.ki[e] * erro * dt", "anti-windup removido", "equiv"),
    ("taxa.hpp", "if (umax > 1.0f) {", "if (umax > 1.5f) {", "airmode para baixo desligado (limiar)", "equiv"),
    ("taxa.hpp", "if (umin < c.idle) {", "if (umin < 0.0f) {", "airmode para cima desligado", "equiv"),
    ("taxa.hpp", "return dt / (rc + dt);", "return dt / rc;", "coeficiente do PT1", "equiv"),
    ("taxa.hpp", "const float faixa = 1.0f - c.idle;", "const float faixa = 1.0f;",
     "faixa do diferencial sem o idle", "equiv"),
    ("estimador.hpp", "const float vy_m = -s.tof_d * (s.fluxo[0] + p);",
     "const float vy_m = s.tof_d * (s.fluxo[0] + p);", "sinal do fluxo em vy", "equiv"),
    ("estimador.hpp", "const float k_v = c.w_altura * c.w_altura * periodo;",
     "const float k_v = 0.5f * c.w_altura * c.w_altura * periodo;",
     "ganho de velocidade do observador de altura", "equiv"),
    ("estimador.hpp", "roll += dt * (droll + c.k_atitude * envolve(roll_a - roll));",
     "roll += dt * (droll + 0.8f * c.k_atitude * envolve(roll_a - roll));",
     "peso do acelerómetro no roll (−20 %)", "equiv"),
    ("estimador.hpp", "vx *= c.decai_fluxo;\n            vy *= c.decai_fluxo;", "vx *= 1.0f;\n            vy *= 1.0f;",
     "decaimento da velocidade sem fluxo", "equiv"),
    ("estimador.hpp", "psi = envolve(psi + dt * dpsi);", "psi = psi + dt * dpsi;",
     "volta do rumo (sem envolver)", "equiv"),
    ("estimador.hpp", "const bool ct_ok = absf(ct_) > 1e-3f;", "const bool ct_ok = true;",
     "guarda |cosθ| ≤ 1e-3 removido (singularidade de Euler)", "equiv"),
    ("nucleo.cpp", "bool consumida = dedupe_pendente_ && mesma_amostra(s, amostra_calibracao_);",
     "bool consumida = dedupe_pendente_ && !mesma_amostra(s, amostra_calibracao_);",
     "idempotência da calibração por conteúdo (invertida)", "equiv"),
    # o saneamento não muda NADA com entradas normais: só o estresse (NaN/inf/extremos) o vê
    ("nucleo.cpp", "if (!motores_ok) {", "if (false) {",
     "saneamento dos motores removido (NaN chegaria aos ESC)", "estresse"),
    ("nucleo.cpp", "if (!est_ok) {", "if (!est_ok && false) {",
     "saneamento do estimador removido (NaN persistente)", "estresse"),
    ("taxa.hpp", "for (int i = 0; i < 4; ++i) u[i] = limita(u[i], c.idle, 1.0f);",
     "for (int i = 0; i < 4; ++i) u[i] = u[i] + 0.0f * c.idle;",
     "corte final dos motores a [idle, 1] removido", "estresse"),
)


def equivalencia_rapida(bib, cfg, env, gravacao: dict) -> dict:
    """Os critérios de equivalência num formato curto (para o C++ intacto e para cada mutante)."""
    du = 0.0
    onde = ""
    for nome, n in (("realista", 1500), ("saturacao", 500), ("airmode_baixo_motor", 500),
                    ("airmode_alto_motor", 500), ("desarmar_rearmar", 1000), ("windup", 700)):
        r = rodar_taxa(bib, cfg, env, nome, n)
        if r["du_max"] > du:
            du, onde = r["du_max"], nome
    est = comparar_estimador(bib, cfg, gravacao["reset"], gravacao["est0"], gravacao["entradas"][:5000],
                             gravacao["saidas"][:5000])
    fl = fluxo_sintetico(7, 6000)
    py = python_do_fluxo(fl)
    est2 = comparar_estimador(bib, cfg, fl["reset"], py["est0"], fl["entradas"], py["saidas"])
    fg = fluxo_sintetico(7, 1500, tumble=True)
    pg = python_do_fluxo(fg)
    est3 = comparar_estimador(bib, cfg, fg["reset"], pg["est0"], fg["entradas"], pg["saidas"])
    # idempotência da calibração por conteúdo (SITL: calibra e o 1.º tick relê a MESMA leitura)
    idem = _idempotencia(bib, cfg)
    pior = {k: max(est["max"][k], est2["max"][k], est3["max"][k]) for k in est["max"]}
    fora = _tolerado(pior)
    if max(est["psi_max"], est2["psi_max"], est3["psi_max"]) > math.pi + 1e-5:
        fora = [*fora, "ψ fora de [−π, π]"]
    if du > TOL_U:
        motivo = f"|Δu| = {du:.1e} no cenário «{onde}»"
    elif fora:
        motivo = "estimador: " + ", ".join(fora[:3])
    elif not idem:
        motivo = "idempotência da calibração"
    else:
        motivo = ""
    return {"passa": not motivo, "motivo": motivo, "du": du, "est": pior}


def _idempotencia(bib, cfg) -> bool:
    """Semântica de calibrar(): (i) calibrar(S) seguido de passo(S) (a MESMA leitura) não integra S duas vezes e
    ≡ passo(S) sozinho (auto-calibração); (ii) calibrar(S0) seguido de passo(S1) com S1 ≠ S0 INTEGRA S1."""
    def novo_nucleo():
        n = NucleoCpp(cfg, bib).exigir_iniciado()
        n.reiniciar()
        sitl.preencher_sensores(n.sens, (0.1, 0.2, 0.3), (0.3, 0.2, 9.7), 1.0, True, 5, (0.1, 0.1), True, 5)
        sitl.definir_comando_ctbr(n.cmd, 0.0, (0, 0, 0))
        return n
    a, b, c2 = novo_nucleo(), novo_nucleo(), novo_nucleo()
    a.calibrar()
    cal = a.estimativas()
    a.passo(DT)
    depois_a = a.estimativas()
    b.passo(DT)                                       # auto-calibração no 1.º passo
    depois_b = b.estimativas()
    i_ok = depois_a == cal and depois_b == cal        # nada se integrou: o estado é o da calibração
    c2.calibrar()
    roll_cal = c2.estimativas()["roll"]
    c2.sens.giro[0] = 1.0                             # leitura NOVA depois de calibrar
    c2.passo(DT)
    ii_ok = abs(c2.estimativas()["roll"] - roll_cal) > 1e-3
    for n in (a, b, c2):
        n.close()
    return bool(i_ok and ii_ok)


def _compilar_mutante(idx: int, ficheiro: str, antigo: str, novo: str, base: Path) -> Path | str:
    """Copia o núcleo, aplica a mutação (a âncora tem de existir UMA vez) e compila a .so. Devolve o caminho
    da pasta de firmware do mutante (contém `nucleo/` e `out/`) ou a mensagem de erro."""
    raiz = base / f"mut_{idx}"
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


def _avaliar_mutante(raiz: Path, detetor: str, cfg, env, gravacao: dict, config_bin: Path) -> dict:
    """Aplica o detetor do mutante: equivalência C++ ≡ Python ("equiv") ou estresse com sanitizers ("estresse")."""
    if detetor == "equiv":
        so = next((raiz / "out").glob("libnucleo-*.so"))
        mbib = sitl.BibliotecaNucleo(so, raiz / "nucleo" / "config.hpp")
        r = equivalencia_rapida(mbib, cfg, env, gravacao)
        return {"apanhado": not r["passa"], "motivo": r["motivo"]}
    exe = raiz / "estresse"
    rc = compilar_estresse("g++", raiz, exe)
    if rc.returncode != 0:
        return {"apanhado": False, "motivo": f"o estresse do mutante não compila: {rc.stderr[:200]}"}
    e = correr_estresse(exe, config_bin)
    return {"apanhado": not e["ok"], "motivo": (f"estresse: {e['violacoes']} violações dos invariantes"
                                                 + (f" · {e['erro']}" if e["erro"] else ""))}


def secao_mutacoes(c: Checagens, tmp: Path, bib, cfg, env, gravacao: dict, config_bin: Path, com_fonte: bool) -> None:
    base = equivalencia_rapida(bib, cfg, env, gravacao)
    c.ok("[§7] (e) CONTROLO: o C++ intacto passa o critério de equivalência rápido usado nas mutações "
         f"(|Δu| {base['du']:.1e}, estimador dentro das tolerâncias)", base["passa"], base["motivo"])
    # --- mutações da Config (o C++ intacto com parâmetros corrompidos)
    for nome in MUTACOES_CONFIG:
        k = mutar_config(bib, cfg, nome)
        r = equivalencia_rapida(bib, k, env, gravacao)
        c.ok(f"[§7] mutação de CONFIG «{nome}» é APANHADA pelo teste de equivalência", not r["passa"],
             f"{r['motivo']}" if not r["passa"] else "NÃO FOI APANHADA")
    if not com_fonte:
        return
    # --- mutações da FONTE C++ (compiladas de verdade, em paralelo) — cada uma com o seu detetor
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(_compilar_mutante, i, f, a, n, tmp) for i, (f, a, n, _d, _t) in enumerate(MUTACOES_FONTE)]
        raizes = [fu.result() for fu in futs]
    for (ficheiro, _a, _n, desc, detetor), raiz in zip(MUTACOES_FONTE, raizes, strict=True):
        if isinstance(raiz, str):
            c.ok(f"[§7] mutação de FONTE «{desc}» ({ficheiro}) aplicável e compilável", False, raiz)
            continue
        r = _avaliar_mutante(raiz, detetor, cfg, env, gravacao, config_bin)
        nome_det = "pelo teste de equivalência" if detetor == "equiv" else "pelo ESTRESSE com sanitizers"
        c.ok(f"[§7] mutação de FONTE «{desc}» ({ficheiro}) é APANHADA {nome_det}", r["apanhado"],
             r["motivo"] if r["apanhado"] else "NÃO FOI APANHADA")
    c.ok(f"[§7] {len(MUTACOES_FONTE)} mutantes da fonte C++ compilados e avaliados em "
         f"{time.perf_counter() - t0:.0f} s", True)


# ============================================================================================ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Prova do núcleo de firmware C++ (equivalência, SITL, cross-compile).")
    ap.add_argument("--rapido", action="store_true", help="sem a malha fechada (§6) nem mutações da fonte")
    ap.add_argument("--secoes", default="0,1,2,3,4,5,6,7", help="secções a correr (depuração), ex.: 0,1,4")
    args = ap.parse_args(argv)
    quais = {int(s) for s in args.secoes.split(",") if s.strip()}
    if not MODELO_VOO.is_file():
        print(f"[teste] falta a política do voo: {MODELO_VOO}", flush=True)
        return 1
    c = Checagens("nucleo")
    tmp = Path(tempfile.mkdtemp(prefix="teste_nucleo_"))
    t0 = time.perf_counter()
    try:
        tamanhos = {}
        bib = sitl.carregar_biblioteca()
        politica, build, env = _env_de_referencia()
        cfg = sitl.config_de_hardware(env.hw, env.model, env.dt)
        config_bin = tmp / "config.bin"
        config_bin.write_bytes(bytes(cfg))
        if 0 in quais:
            print("§0 — regras de firmware no código", flush=True)
            secao_regras(c)
        if 1 in quais:
            print("§1 — compilação no host (g++ / clang++) + estresse com sanitizers", flush=True)
            secao_host(c, tmp, config_bin)
        if 2 in quais:
            print("§2 — compilação cruzada Cortex-M4 / Cortex-M7 (clang)", flush=True)
            tamanhos = secao_cruzada(c, tmp)
        if 3 in quais:
            print("§3 — layout, Config da planta, saneamento", flush=True)
            secao_layout_config(c, tmp, bib, env)
        if 4 in quais:
            print("§4 — equivalência unitária C++ ≡ Python (taxa+mistura e estimador)", flush=True)
            secao_taxa(c, bib, cfg, env)
        gravacao = gravar_voo_python(build, politica, seed=0) if quais & {4, 5, 6, 7} else None
        if 4 in quais:
            secao_estimador(c, bib, cfg, gravacao)
        if 5 in quais:
            print("§5 — SHADOW: voo de 20 s com o C++ em paralelo", flush=True)
            secao_sombra(c, build, politica, gravacao, bib)
        if 6 in quais and not args.rapido:
            print("§6 — MALHA FECHADA: o C++ manda nos motores", flush=True)
            secao_malha_fechada(c, build, politica, gravacao, bib, cfg)
        if 7 in quais:
            print("§7 — mutações (o teste TEM de as apanhar)", flush=True)
            secao_mutacoes(c, tmp, bib, cfg, env, gravacao, config_bin, com_fonte=not args.rapido)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n[teste] {len(c.linhas) - len(c.falhas)}/{len(c.linhas)} checagens OK "
          f"({time.perf_counter() - t0:.0f} s)", flush=True)
    if tamanhos:
        print("[teste] tamanhos medidos do núcleo (clang -Os, só nucleo.o; libm à parte):", flush=True)
        for cpu, m in tamanhos.items():
            print(f"        {cpu}: text {m['text']} B · data {m['data']} B · bss {m['bss']} B · "
                  f"RAM do estado {m['ram_estado']} B", flush=True)
    if c.falhas:
        for nome in c.falhas:
            print(f"[teste] FALHOU: {nome}", flush=True)
        return 1
    print("[teste] o núcleo de firmware C++ cumpre o contrato: regras de firmware, compila (host + Cortex-M4/M7) "
          "sem malloc/new/__cxa_*, é equivalente ao Python (unitário + shadow de 20 s), voa o MuJoCo em malha "
          "fechada e o teste apanha as mutações", flush=True)
    return 0


def _main_seguro() -> int:
    try:
        return main()
    except FileNotFoundError as erro:                 # ferramenta/ficheiro em falta: falha ALTO, nunca salta
        print(f"[teste] FALHOU: {erro}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(_main_seguro())
