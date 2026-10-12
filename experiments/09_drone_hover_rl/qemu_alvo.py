"""experiments/09_drone_hover_rl/qemu_alvo.py — o MESMO código do firmware a correr em Cortex-M4 e Cortex-M7 EMULADOS (QEMU).

A pergunta do dono («tudo no Arduino») tem uma parte que se responde sem placa: o código C++ do núcleo (`firmware/nucleo/`: estimador
clássico + cascata + laço de taxa + IBVS + detetor) compila, liga e CORRE num Cortex-M real do ponto de vista do conjunto de instruções
(ARMv7E-M Thumb-2, FPU de precisão simples FPv4-SP no M4 / FPv5 no M7) e dá os MESMOS bits que no host. Este módulo faz o ciclo completo:

    registos de um voo gravados no SITL ──▶ driver_replay.cpp ──┬─▶ host (x86-64), libm PRÓPRIA     ──▶ saida_host.bin
                                                                 ├─▶ QEMU mps2-an386 (Cortex-M4)      ──▶ saida_m4.bin   } comparados
                                                                 └─▶ QEMU mps2-an500 (Cortex-M7)      ──▶ saida_m7.bin   } BIT A BIT

  · a imagem é BARE-METAL, sem libc nem libm (`cross/qemu/`: arranque, mapa de memória, semihosting, runtime mínimo, `libm_minima.cpp`:
    sinf/cosf/atan2f próprios, ≤ 2 ULP; o sqrtf é a instrução da FPU, exatamente arredondada nos dois lados);
  · `-ffp-contract=off` em todos os lados (sem FMA), sem -ffast-math: a aritmética float32 IEEE é a mesma em SSE e em VFP;
  · um comparador COM DENTES (compilar um dos lados com `-ffp-contract=fast` ou mudar uma constante faz-o apontar a divergência);
  · o traço de instruções do QEMU (`-d exec` com uma instrução por bloco) dá a CONTAGEM EXATA de instruções por passo (instruction-accurate,
    não cycle-accurate: o DWT->CYCCNT não existe no QEMU) e alimenta o `llvm-mca` (ciclos ESTIMADOS do M7).

HONESTIDADE: o QEMU prova a EXATIDÃO (bits) e conta instruções — NÃO mede tempo. A libm do host de comparação é a `libm_minima` (a real do
Arduino/newlib não existe aqui: sem sysroot ARM); contra a glibc mede-se o erro em ULP à parte.

    uv run --group hover-rl python experiments/09_drone_hover_rl/qemu_alvo.py auto-teste
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import math
import os
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

FIRMWARE_DIR = _AQUI / "firmware"
QEMU_DIR = FIRMWARE_DIR / "cross" / "qemu"
OUT_QEMU = _AQUI / "out" / "qemu"
MAGIA = 0x3143554E
OPS = {"passo": 0, "reiniciar": 1, "armar": 2, "desarmar": 3, "calibrar": 4, "calibrar_chao_on": 5, "calibrar_chao_off": 6,
       "travar": 7, "detetar": 8}
CPUS = {"m4": {"mcpu": "cortex-m4", "mfpu": "fpv4-sp-d16", "maquina": "mps2-an386", "rotulo": "Cortex-M4 (FPv4-SP)"},
        "m7": {"mcpu": "cortex-m7", "mfpu": "fpv5-d16", "maquina": "mps2-an500", "rotulo": "Cortex-M7 (FPv5)"}}
FLAGS_COMUNS = ["-std=c++17", "-ffp-contract=off", "-fno-math-errno", "-fno-exceptions", "-fno-rtti", "-Wall", "-Wextra",
                "-Wdouble-promotion", "-Werror"]
FLAGS_ALVO = ["--target=thumbv7em-none-eabihf", "-mthumb", "-mfloat-abi=hard", "-ffreestanding", "-fno-threadsafe-statics",
              "-DNUCLEO_ALVO_BARE"]


# =========================================================================================== utilitários
def _correr(cmd: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, check=False, **kw)


def _ferramenta(*nomes: str) -> str:
    for n in nomes:
        p = shutil.which(n)
        if p:
            return p
    raise FileNotFoundError(f"ferramenta não encontrada: {nomes}")


def _hash_fontes(firmware_dir: Path, extra: str) -> str:
    h = hashlib.sha256(extra.encode())
    for f in sorted(Path(firmware_dir).glob("nucleo/*.[ch]pp")) + sorted(QEMU_DIR.glob("*.[chS]*")) + sorted(
            (QEMU_DIR / "shim").glob("*.h")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def estruturas(firmware_dir: Path = FIRMWARE_DIR) -> dict[str, type]:
    """As structs de ctypes geradas do `config.hpp` do firmware indicado (a mesma fonte única do `sitl.py`)."""
    import sitl
    return sitl.estruturas_do_header(Path(firmware_dir) / "nucleo" / "config.hpp")


def registo_cls(est: dict[str, type]) -> type:
    """O `Registo` do driver: {i32 op; f32 dt; i32 semente; f32 extra[4]; Sensores s; Comando c}."""
    return type("Registo", (ctypes.Structure,), {"_fields_": [("op", ctypes.c_int32), ("dt", ctypes.c_float),
                                                                 ("semente", ctypes.c_int32), ("extra", ctypes.c_float * 4),
                                                                 ("s", est["Sensores"]), ("c", est["Comando"])]})


def escrever_entrada(caminho: Path, cfg, registos: list, est: dict[str, type], versao: int) -> None:
    """Grava `entrada.bin` (cabeçalho + registos) e deixa `config.bin` ao lado."""
    caminho = Path(caminho)
    cab = np.array([MAGIA, versao, ctypes.sizeof(est["Config"]), ctypes.sizeof(est["Sensores"]),
                    ctypes.sizeof(est["Comando"]), ctypes.sizeof(est["Saida"]), len(registos)], dtype="<u4")
    with open(caminho, "wb") as f:
        f.write(cab.tobytes())
        f.writelines(bytes(r) for r in registos)
    (caminho.parent / "config.bin").write_bytes(bytes(cfg))


def ler_saidas(caminho: Path, classe_saida: type, classe_deteccao: type | None, ops: list[int]) -> list:
    """Lê `saida.bin`: um bloco por registo (`Saida` ou, na op 8, `Deteccao`)."""
    dados = Path(caminho).read_bytes()
    out, i = [], 0
    for op in ops:
        cls = classe_deteccao if op == OPS["detetar"] else classe_saida
        n = ctypes.sizeof(cls)
        if i + n > len(dados):
            raise ValueError(f"saída truncada: {len(dados)} B para {len(ops)} registos")
        out.append(cls.from_buffer_copy(dados[i:i + n]))
        i += n
    if i != len(dados):
        raise ValueError(f"saída com {len(dados) - i} B a mais")
    return out


# =========================================================================================== compilação
def _compilar(cxx: str, flags: list, fonte: Path, saida: Path, incs: list) -> None:
    r = _correr([cxx, *flags, *incs, "-c", fonte, "-o", saida])
    if r.returncode != 0:
        raise RuntimeError(f"falha a compilar {fonte.name} ({cxx}):\n{r.stderr[:2000]}")


def compilar_imagem(cpu: str, firmware_dir: Path = FIRMWARE_DIR, destino: Path = OUT_QEMU, opt: str = "-O2",
                    extra: tuple = (), clang: str | None = None) -> Path:
    """Compila e liga a imagem bare-metal (arranque + núcleo + driver + libm própria + runtime) para `cpu` ∈ {m4, m7}.

    Cache por hash das fontes+flags; devolve o ELF. `extra` = flags a mais (ex.: `("-ffp-contract=fast",)` para provar que o
    comparador tem dentes). Os avisos são erros (-Wall -Wextra -Wdouble-promotion -Werror), como no firmware.
    """
    info = CPUS[cpu]
    clang = clang or _ferramenta("clang++")
    firmware_dir, destino = Path(firmware_dir), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    flags = [*FLAGS_COMUNS, *FLAGS_ALVO, f"-mcpu={info['mcpu']}", f"-mfpu={info['mfpu']}", opt, *extra]
    chave = _hash_fontes(firmware_dir, f"{cpu} {' '.join(flags)} {firmware_dir}")
    elf = destino / f"imagem_{cpu}_{chave}.elf"
    if elf.is_file():
        return elf
    obj = destino / f"obj_{cpu}_{chave}"
    obj.mkdir(exist_ok=True)
    incs = ["-I", firmware_dir, "-I", QEMU_DIR, "-isystem", QEMU_DIR / "shim"]
    objs = []
    for nome, fonte in (("nucleo", firmware_dir / "nucleo" / "nucleo.cpp"), ("driver", QEMU_DIR / "driver_replay.cpp"),
                        ("libm", QEMU_DIR / "libm_minima.cpp"), ("rt", QEMU_DIR / "rt_minimo.cpp")):
        o = obj / f"{nome}.o"
        _compilar(clang, flags, fonte, o, incs)
        objs.append(o)
    arr = obj / "arranque.o"
    r = _correr([_ferramenta("clang"), "--target=thumbv7em-none-eabihf", "-mthumb", f"-mcpu={info['mcpu']}", f"-mfpu={info['mfpu']}",
                 "-mfloat-abi=hard", "-c", QEMU_DIR / "arranque.S", "-o", arr])
    if r.returncode != 0:
        raise RuntimeError(f"falha a montar arranque.S:\n{r.stderr[:1500]}")
    tmp = elf.with_suffix(f".{os.getpid()}.tmp")
    r = _correr([_ferramenta("ld.lld"), "-T", QEMU_DIR / "mps2.ld", "-nostdlib", "--gc-sections", arr, *objs, "-o", tmp])
    if r.returncode != 0:
        raise RuntimeError(f"falha a ligar a imagem {cpu}:\n{r.stderr[:2500]}")
    os.replace(tmp, elf)
    for antigo in sorted(destino.glob(f"imagem_{cpu}_*.elf"), key=lambda p: p.stat().st_mtime, reverse=True)[8:]:
        antigo.unlink(missing_ok=True)
    return elf


def tamanho_imagem(elf: Path) -> dict:
    """text/data/bss do ELF (`llvm-size -B`) — o que ocuparia em flash (text+data) e em RAM (data+bss)."""
    linha = _correr([_ferramenta("llvm-size"), "-B", elf]).stdout.strip().splitlines()[-1].split()
    t, d, b = int(linha[0]), int(linha[1]), int(linha[2])
    return {"text": t, "data": d, "bss": b, "flash": t + d, "ram": d + b}


def compilar_host(libm: str = "minima", cxx: str = "g++", firmware_dir: Path = FIRMWARE_DIR, destino: Path = OUT_QEMU,
                  opt: str = "-O2", extra: tuple = ()) -> Path:
    """Compila o driver para o host: `libm="minima"` (a MESMA libm própria da imagem: o que se compara bit a bit com o QEMU) ou
    `"glibc"` (a libm do sistema: só para medir a diferença em ULP)."""
    firmware_dir, destino = Path(firmware_dir), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    flags = [*FLAGS_COMUNS, opt, *extra]
    chave = _hash_fontes(firmware_dir, f"host {libm} {cxx} {' '.join(flags)} {firmware_dir}")
    exe = destino / f"host_{libm}_{Path(cxx).name}_{chave}"
    if exe.is_file():
        return exe
    incs = ["-I", firmware_dir, "-I", QEMU_DIR]
    fontes = [firmware_dir / "nucleo" / "nucleo.cpp", QEMU_DIR / "driver_replay.cpp"]
    if libm == "minima":
        incs += ["-isystem", QEMU_DIR / "shim"]
        fontes.append(QEMU_DIR / "libm_minima.cpp")
    tmp = exe.with_suffix(f".{os.getpid()}.tmp")
    r = _correr([cxx, *flags, *incs, *fontes, "-o", tmp] + (["-lm"] if libm == "glibc" else []))
    if r.returncode != 0:
        raise RuntimeError(f"falha a compilar o host ({libm}, {cxx}):\n{r.stderr[:2500]}")
    os.replace(tmp, exe)
    return exe


# =========================================================================================== execução
def correr_host(exe: Path, config_bin: Path, entrada_bin: Path, saida_bin: Path, timeout_s: float = 120.0) -> dict:
    """Corre o driver no host numa pasta de trabalho com os 3 ficheiros (nomes fixos, como no alvo)."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(config_bin, d / "config.bin")
        shutil.copy(entrada_bin, d / "entrada.bin")
        t0 = time.perf_counter()
        r = _correr([exe], cwd=d, timeout=timeout_s)
        dt = time.perf_counter() - t0
        if (d / "saida.bin").is_file():
            shutil.copy(d / "saida.bin", saida_bin)
    return {"codigo": r.returncode, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()[:500], "duracao_s": dt}


def correr_qemu(elf: Path, cpu: str, config_bin: Path, entrada_bin: Path, saida_bin: Path, timeout_s: float = 180.0,
                extra_qemu: tuple = ()) -> dict:
    """Corre a imagem no QEMU (`mps2-an386` M4 / `mps2-an500` M7) com semihosting para os ficheiros do host.
    Um QEMU pendurado é MORTO ao fim de `timeout_s` e reportado (`timeout=True`)."""
    info = CPUS[cpu]
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        shutil.copy(config_bin, d / "config.bin")
        shutil.copy(entrada_bin, d / "entrada.bin")
        cmd = [_ferramenta("qemu-system-arm"), "-M", info["maquina"], "-cpu", info["mcpu"], "-nographic", "-monitor", "none",
               "-serial", "none", "-chardev", "stdio,id=con", "-semihosting-config", "enable=on,target=native,chardev=con",
               "-kernel", elf, *extra_qemu]
        t0 = time.perf_counter()
        try:
            r = subprocess.run([str(c) for c in cmd], cwd=d, capture_output=True, text=True, timeout=timeout_s, check=False)
            codigo, out, err, estourou = r.returncode, r.stdout.strip(), r.stderr.strip()[:500], False
        except subprocess.TimeoutExpired as e:
            codigo, out, err, estourou = -9, (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout", True
        dt = time.perf_counter() - t0
        if (d / "saida.bin").is_file():
            shutil.copy(d / "saida.bin", saida_bin)
    return {"codigo": codigo, "stdout": out, "stderr": err, "duracao_s": dt, "timeout": estourou}


# =========================================================================================== comparação
def _ordem_ulp(x: np.ndarray) -> np.ndarray:
    """Float32 → inteiro monótono (a distância entre dois inteiros é a distância em ULP)."""
    i = np.asarray(x, dtype=np.float32).view(np.int32).astype(np.int64)
    return np.where(i < 0, -(i & 0x7FFFFFFF), i)


def comparar_saidas(a_bin: Path, b_bin: Path, classe: type) -> dict:
    """Compara dois `saida.bin` de blocos `classe` (uma struct de ctypes só com campos de 4 bytes): bit a bit e, se divergir, por campo
    (máx |Δ| e máx ULP nos floats; contagem nos inteiros) e o 1.º bloco divergente."""
    a, b = Path(a_bin).read_bytes(), Path(b_bin).read_bytes()
    n = ctypes.sizeof(classe)
    res: dict = {"bytes_a": len(a), "bytes_b": len(b), "blocos": min(len(a), len(b)) // n, "bit_exact": a == b}
    if a == b:
        res.update({"primeiro_divergente": None, "campos": {}})
        return res
    m = min(len(a), len(b)) // n
    campos: dict = {}
    primeiro = None
    for nome, tipo in classe._fields_:
        off = getattr(classe, nome).offset
        tam = getattr(classe, nome).size
        nel = tam // 4
        is_float = tipo is ctypes.c_float or (hasattr(tipo, "_type_") and tipo._type_ is ctypes.c_float) or (
            hasattr(tipo, "_type_") and hasattr(tipo._type_, "_type_") and tipo._type_._type_ is ctypes.c_float)
        ia = np.frombuffer(a[: m * n], dtype="<u4").reshape(m, n // 4)[:, off // 4: off // 4 + nel]
        ib = np.frombuffer(b[: m * n], dtype="<u4").reshape(m, n // 4)[:, off // 4: off // 4 + nel]
        dif = ia != ib
        if not dif.any():
            continue
        linhas = np.nonzero(dif.any(axis=1))[0]
        if primeiro is None or linhas[0] < primeiro:
            primeiro = int(linhas[0])
        if is_float or nel > 1:
            fa, fb = ia.view("<f4"), ib.view("<f4")
            with np.errstate(invalid="ignore"):
                d = np.abs(fa - fb)
            campos[nome] = {"blocos_diferentes": int(dif.any(axis=1).sum()), "max_abs": float(np.nanmax(d)),
                            "max_ulp": int(np.abs(_ordem_ulp(fa) - _ordem_ulp(fb)).max())}
        else:
            campos[nome] = {"blocos_diferentes": int(dif.any(axis=1).sum())}
    res.update({"primeiro_divergente": primeiro, "campos": campos})
    return res


# =========================================================================================== registos
def novo_registo(RegistoCls: type, op: str, dt: float = 0.0, semente: int = 0, extra=(0.0, 0.0, 0.0, 0.0), s=None, c=None):
    r = RegistoCls()
    r.op, r.dt, r.semente = OPS[op], float(dt), int(semente)
    for i, v in enumerate(extra):
        r.extra[i] = float(v)
    if s is not None:
        ctypes.memmove(ctypes.addressof(r.s), ctypes.addressof(s), ctypes.sizeof(s))
    if c is not None:
        ctypes.memmove(ctypes.addressof(r.c), ctypes.addressof(c), ctypes.sizeof(c))
    return r


class GravadorNucleo:
    """Embrulha uma `NucleoCpp` e GRAVA tudo o que o núcleo recebe (as ops de ciclo de vida e cada `planear` como um `passo`):
    o que o firmware viu num voo do SITL fica como um fluxo de registos que o driver repete no host e no alvo.

    O voo do SITL põe um atraso entre `planear` e `atuar` (propriedade da planta) e o driver chama `passo` (sem atraso): as SAÍDAS da
    repetição não são as do voo — mas as ENTRADAS (sensores medidos, câmara, comandos) são as reais, e é isso que se quer comparar
    entre o host e o alvo."""

    def __init__(self, nucleo, RegistoCls: type, registos: list):
        self.n, self.R, self.registos = nucleo, RegistoCls, registos
        for nome in ("reiniciar", "armar", "calibrar", "calibrar_chao", "travar_referencias", "planear"):
            setattr(nucleo, nome, getattr(self, "_" + nome))
        self._orig = {nome: getattr(type(nucleo), nome) for nome in ("reiniciar", "armar", "calibrar", "calibrar_chao",
                                                                      "travar_referencias", "planear")}

    def _reg(self, op, **kw):
        self.registos.append(novo_registo(self.R, op, **kw))

    def _reiniciar(self):
        self._reg("reiniciar")
        return self._orig["reiniciar"](self.n)

    def _armar(self, armado):
        self._reg("armar" if armado else "desarmar")
        return self._orig["armar"](self.n, armado)

    def _calibrar(self):
        self._reg("calibrar", s=self.n.sens)
        return self._orig["calibrar"](self.n)

    def _calibrar_chao(self, ativa):
        self._reg("calibrar_chao_on" if ativa else "calibrar_chao_off")
        return self._orig["calibrar_chao"](self.n, ativa)

    def _travar_referencias(self, com_z_alvo=False, z_alvo=0.0):
        self._reg("travar", extra=(1.0 if com_z_alvo else 0.0, z_alvo, 0.0, 0.0))
        return self._orig["travar_referencias"](self.n, com_z_alvo, z_alvo)

    def _planear(self, dt):
        self._reg("passo", dt=dt, s=self.n.sens, c=self.n.cmd)
        return self._orig["planear"](self.n, dt)


def gravar_voo(segundos: float = 12.0, seed: int = 0, olhar: bool = False, firmware_dir: Path = FIRMWARE_DIR,
               latencia_s: float = 0.116) -> dict:
    """Voa o SITL em modo cascata (build ativo, sem vento) e GRAVA os registos que o núcleo recebeu.

    `olhar=False`: descola e executa uma sequência de manobras (W, A, Q, E, yaw 90°, yaw a taxa, arco) em VELOCIDADE/YAW_ALVO;
    `olhar=True`: descola, liga o IBVS e o alvo (esfera mocap) descreve um círculo a 0,5 m/s, com a câmara mono QVGA renderizada, o detetor C++
    e a latência `latencia_s`. Devolve {cfg, registos, est, RegistoCls, passos}."""
    import json

    import sitl
    from env_real import build_do_hardware
    dados = json.loads((sitl.MODELO_VOO.parent / "hardware.json").read_text(encoding="utf-8"))
    build, _ = build_do_hardware(dados)
    ref = sitl.MODELO_VOO.parents[1] / "classico" / "avaliacao.json"
    u_yaw = json.loads(ref.read_text(encoding="utf-8"))["identificacao_yaw"]["u_yaw_por_taxa"] if ref.is_file() else None
    opcoes: dict = {"u_yaw_por_taxa": u_yaw}
    if olhar:
        opcoes["camera"] = {"latencia_s": latencia_s}
    env = sitl.criar_env(build, segundos, "cascata", cascata=opcoes, com_alvo=olhar)
    est = estruturas(firmware_dir)
    R = registo_cls(est)
    registos: list = []
    GravadorNucleo(env.nucleo, R, registos)
    cfg = env.nucleo.cfg
    if olhar:
        env.ponto_modo, env.ponto_vel, env.ponto_raio = "parado", 0.5, 1.5
    env.reset(seed=seed)
    n = round(segundos / env.dt_decisao)
    for k in range(n):
        t = k * env.dt_decisao
        if olhar:
            if k == round(4.0 / env.dt_decisao):
                env.definir_trajetoria_ponto("circulo", vel=0.5, raio=1.5)
            cmd = {"modo": "olhar"} if t >= 4.0 else {}
        else:
            cmd = _manobras(t)
        env.fc.definir_comando(cmd)
        env.step(np.zeros(4, dtype=np.float32))
    passos = sum(1 for r in registos if r.op == OPS["passo"])
    env.close()
    return {"cfg": cfg, "registos": registos, "est": est, "RegistoCls": R, "passos": passos}


def _manobras(t: float) -> dict:
    """Sequência de manobras (referencial do rumo) que exercita yaw (taxa e rumo-alvo, incl. saturação), velocidade e altura."""
    if t < 3.0:
        return {}
    if t < 5.0:
        return {"vx": 1.0}
    if t < 6.5:
        return {"vy": 1.0}
    if t < 7.5:
        return {"vz": 0.7}
    if t < 8.5:
        return {"vz": -0.7}
    if t < 11.0:
        return {"modo": "yaw_alvo", "yaw": math.pi / 2}
    if t < 12.5:
        return {"yaw_taxa": 1.2}
    return {"vx": 1.0, "yaw_taxa": 0.5}


def registos_detetar(RegistoCls: type, n: int = 24, semente: int = 7) -> list:
    """`n` registos de deteção sintética (disco em posições/raios/ruídos variados, incl. casos sem alvo) para provar o detetor no alvo."""
    rng = np.random.default_rng(semente)
    out = []
    for i in range(n):
        u, v = rng.uniform(40, 280), rng.uniform(40, 200)
        raio = float(rng.choice([0.0, 3.0, 5.5, 8.0, 12.0, 20.0]))
        out.append(novo_registo(RegistoCls, "detetar", semente=int(rng.integers(1, 2**31 - 1)), extra=(u, v, raio, 0.0)))
    return out


# =========================================================================================== prova completa
def provar(registos: list, cfg, est: dict, trabalho: Path, firmware_dir: Path = FIRMWARE_DIR, opt: str = "-O2",
           com_glibc: bool = True, verboso: bool = True) -> dict:
    """host(libm própria) ≡ QEMU M4 ≡ QEMU M7 BIT A BIT (+ host glibc em ULP). Devolve o relatório."""
    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)
    versao = int(ctypes.c_uint32.from_buffer_copy(bytes(cfg)[:4]).value)
    entrada = trabalho / "entrada.bin"
    escrever_entrada(entrada, cfg, registos, est, versao)
    cfg_bin = trabalho / "config.bin"
    ops = [r.op for r in registos]
    rel: dict = {"registos": len(registos), "passos": ops.count(0), "deteccoes": ops.count(8), "bytes_entrada": entrada.stat().st_size}

    def dizer(msg: str) -> None:
        if verboso:
            print(msg, flush=True)

    exe_min = compilar_host("minima", "g++", firmware_dir, opt=opt)
    saida_host = trabalho / "saida_host.bin"
    rh = correr_host(exe_min, cfg_bin, entrada, saida_host)
    rel["host_minima"] = {"codigo": rh["codigo"], "stdout": rh["stdout"], "duracao_s": rh["duracao_s"]}
    dizer(f"  host (libm própria): {rh['stdout']}  [{rh['duracao_s']:.2f} s]")
    if rh["codigo"] != 0:
        rel["ok"] = False
        return rel
    for cpu in ("m4", "m7"):
        elf = compilar_imagem(cpu, firmware_dir, opt=opt)
        tam = tamanho_imagem(elf)
        saida_q = trabalho / f"saida_{cpu}.bin"
        rq = correr_qemu(elf, cpu, cfg_bin, entrada, saida_q)
        rel[cpu] = {"imagem": str(elf.name), "tamanho": tam, "codigo": rq["codigo"], "stdout": rq["stdout"],
                    "duracao_s": rq["duracao_s"], "timeout": rq["timeout"], "stderr": rq["stderr"]}
        dizer(f"  QEMU {CPUS[cpu]['rotulo']}: {rq['stdout']}  [{rq['duracao_s']:.2f} s; imagem text {tam['text']} B · data {tam['data']} B · bss {tam['bss']} B]")
        if rq["codigo"] != 0 or not saida_q.is_file():
            rel[cpu]["bit_exact"] = False
            continue
        cmp_ = _comparar_por_op(saida_host, saida_q, est, ops)
        rel[cpu]["comparacao"] = cmp_
        rel[cpu]["bit_exact"] = cmp_["bit_exact"]
        dizer(f"    ≡ host bit a bit: {cmp_['bit_exact']} ({cmp_['blocos']} blocos, {cmp_['bytes']} B)")
    if com_glibc:
        exe_g = compilar_host("glibc", "g++", firmware_dir, opt=opt)
        saida_g = trabalho / "saida_glibc.bin"
        rg = correr_host(exe_g, cfg_bin, entrada, saida_g)
        if rg["codigo"] == 0:
            rel["glibc"] = _comparar_por_op(saida_host, saida_g, est, ops)
            rel["glibc"]["stdout"] = rg["stdout"]
    rel["ok"] = all(rel.get(c, {}).get("bit_exact") for c in ("m4", "m7"))
    return rel


def _separar_blocos(dados: bytes, ops: list, est: dict) -> tuple[bytes, bytes]:
    """Separa um `saida.bin` nos blocos `Saida` (ops ≠ 8) e `Deteccao` (op 8), na ordem dos registos."""
    ns, nd = ctypes.sizeof(est["Saida"]), ctypes.sizeof(est["Deteccao"])
    saidas, deteccoes, i = bytearray(), bytearray(), 0
    for op in ops:
        n = nd if op == OPS["detetar"] else ns
        (deteccoes if op == OPS["detetar"] else saidas).extend(dados[i:i + n])
        i += n
    return bytes(saidas), bytes(deteccoes)


def _comparar_por_op(a_bin: Path, b_bin: Path, est: dict, ops: list) -> dict:
    """Compara dois `saida.bin` bloco a bloco respeitando o tipo de cada bloco (`Saida` ou `Deteccao`): bit a bit e, se divergirem,
    por campo (máx |Δ| e máx ULP)."""
    a, b = Path(a_bin).read_bytes(), Path(b_bin).read_bytes()
    out: dict = {"bytes": len(a), "bytes_b": len(b), "bit_exact": a == b, "blocos": len(ops)}
    if a == b:
        return out
    sa, da = _separar_blocos(a, ops, est)
    sb, db = _separar_blocos(b, ops, est)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for nome, x, y, cls in (("saida", sa, sb, est["Saida"]), ("deteccao", da, db, est["Deteccao"])):
            (d / "a").write_bytes(x)
            (d / "b").write_bytes(y)
            out[nome] = comparar_saidas(d / "a", d / "b", cls)
    return out


# =========================================================================================== traço de instruções e ciclos
EXTRA_TRACO = ("-DNUCLEO_SEM_CRC",)
RE_TRACO = re.compile(r"^Trace \d+: 0x[0-9a-f]+ \[[0-9a-f]+/([0-9a-f]+)/[0-9a-f]+/[0-9a-f]+\](?: (\S+))?")
RE_BRANCH = re.compile(r"^(b|bl|blx|bx)(eq|ne|cs|hs|cc|lo|mi|pl|vs|vc|hi|ls|ge|lt|gt|le)?(\.w|\.n)?$")
# Latências de TABELA da ARM para o Cortex-M4F (Cortex-M4 TRM + Generic User Guide, «instruction summary»; P = reenchimento do pipeline 1–3,
# tomado 2): só uma ESTIMATIVA por contagem de operações — o M4 do Portenta (480/240 MHz) não tem tabela pública mais fina.
CICLOS_M4 = {"vadd": 1, "vsub": 1, "vmul": 1, "vnmul": 1, "vabs": 1, "vneg": 1, "vcmp": 1, "vcmpe": 1, "vcvt": 1, "vcvtr": 1, "vmov": 1,
             "vmrs": 1, "vmsr": 1, "vsel": 1, "vmla": 3, "vmls": 3, "vnmla": 3, "vnmls": 3, "vfma": 3, "vfms": 3, "vfnma": 3, "vfnms": 3,
             "vdiv": 14, "vsqrt": 14, "vldr": 2, "vstr": 2, "ldr": 2, "ldrb": 2, "ldrh": 2, "ldrsb": 2, "ldrsh": 2, "str": 2, "strb": 2,
             "strh": 2, "mul": 1, "sdiv": 6, "udiv": 6}
P_PIPELINE = 2


def _classe_mnemonico(texto: str) -> str:
    m = texto.split()[0] if texto else ""
    m = re.sub(r"\.(w|n)$", "", m)
    base = m.split(".")[0]
    return base


def _ranges_dfilter(elf: Path, objs: dict[str, Path]) -> tuple[str, dict]:
    """O `-dfilter` do QEMU (só regista o PC nas funções do núcleo, da libm própria, do runtime e dos marcadores) + endereços úteis."""
    nm = _ferramenta("llvm-nm")
    def simbolos(path, so_definidos=True):
        out = _correr([nm, "-S", "--defined-only", path]).stdout.splitlines()
        res = {}
        for ln in out:
            p = ln.split()
            if len(p) >= 4 and p[2] in ("T", "t", "W", "w"):
                res[p[3]] = (int(p[0], 16), int(p[1], 16))
        return res
    final = simbolos(elf)
    nomes = set()
    for o in ("nucleo", "libm", "rt"):
        nomes |= {s for s in simbolos(objs[o])}
    faixas = []
    info = {}
    for nome in sorted(nomes | {"marcador_inicio", "marcador_fim"}):
        if nome in final:
            a, n = final[nome]
            a &= ~1
            if n > 0:
                faixas.append((a, n))
            info[nome] = (a, n)
    faixas.sort()
    fund = []
    for a, n in faixas:                      # funde faixas contíguas
        if fund and a <= fund[-1][0] + fund[-1][1]:
            fund[-1] = (fund[-1][0], max(fund[-1][0] + fund[-1][1], a + n) - fund[-1][0])
        else:
            fund.append((a, n))
    return ",".join(f"0x{a:x}+0x{n:x}" for a, n in fund), info


def _desmontar(elf: Path, cpu: str) -> dict[int, str]:
    """endereço → texto da instrução (`llvm-objdump -d` com o `-mcpu` do alvo: sem ele as instruções VFP saem `<unknown>`)."""
    out = _correr([_ferramenta("llvm-objdump"), "-d", "--no-show-raw-insn", f"--mcpu={CPUS[cpu]['mcpu']}",
                   "--triple=thumbv7em-none-eabihf", elf]).stdout
    mapa = {}
    for ln in out.splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+(.*)$", ln)
        if m:
            txt = re.split(r"\s*[@;]", m.group(2))[0].strip()
            mapa[int(m.group(1), 16)] = txt
    return mapa


def sequencia_para_mca(instrucoes: list[str]) -> str:
    """O traço (instruções na ordem de execução) como código reto para o `llvm-mca`: os saltos/chamadas ficam como `b #0`/`bx lr` (o
    corpo dos chamados já está no traço; o mca modela mal as chamadas), `cbz/cbnz` viram `cmp`, as restantes ficam como estão."""
    linhas = []
    for ins in instrucoes:
        mn = ins.split()[0]
        if RE_BRANCH.match(mn):
            cond = RE_BRANCH.match(mn).group(2) or ""
            if mn.startswith(("bx", "blx")):
                linhas.append(f"bx{cond} lr")               # a condição fica (dentro de um bloco IT tem de bater certo)
            else:
                linhas.append(f"b{cond} #0")
        elif mn in ("cbz", "cbnz"):
            linhas.append(f"cmp {ins.split()[1].rstrip(',')}, #0")
        elif mn in ("tbb", "tbh") or "<unknown>" in ins:
            linhas.append("nop")
        else:
            linhas.append(ins)
    return "\n".join(linhas) + "\n"


def ciclos_mca(instrucoes: list[str], cpu: str, tmp: Path) -> dict:
    """Ciclos ESTIMADOS (llvm-mca, modelo do `cpu` ∈ {m4, m7}; caches/flash/SRAM ideais, sem penalização de ramos) para executar a sequência."""
    f = Path(tmp) / f"seq_{cpu}.s"
    f.write_text(sequencia_para_mca(instrucoes), encoding="utf-8")
    r = _correr([_ferramenta("llvm-mca"), "-mtriple=thumbv7em-none-eabihf", f"-mcpu={CPUS[cpu]['mcpu']}", "-iterations=1",
                 "--instruction-info=false", "--resource-pressure=false", "-skip-unsupported-instructions=lack-sched", f])
    if r.returncode != 0:
        raise RuntimeError(f"llvm-mca falhou:\n{r.stderr[:800]}")
    m = re.search(r"Total Cycles:\s+(\d+)", r.stdout)
    n = re.search(r"Instructions:\s+(\d+)", r.stdout)
    return {"ciclos": int(m.group(1)), "instrucoes": int(n.group(1)), "ipc": int(n.group(1)) / max(int(m.group(1)), 1)}


def ciclos_tabela_m4(instrucoes: list[str]) -> dict:
    """Ciclos ESTIMADOS do Cortex-M4F por TABELA da ARM (`CICLOS_M4`; ramos tomados = 1 + P) — contagem de operações × ciclos."""
    total, hist = 0, {}
    for ins in instrucoes:
        mn = ins.split()[0]
        base = _classe_mnemonico(ins)
        hist[base] = hist.get(base, 0) + 1
        if RE_BRANCH.match(mn):
            total += 1 + P_PIPELINE
        elif base in ("ldm", "stm", "push", "pop", "vldm", "vstm", "vpush", "vpop"):
            total += 1 + max(ins.count(",") + 1, 1)
        else:
            total += CICLOS_M4.get(base, 1)
    return {"ciclos": total, "instrucoes": len(instrucoes), "histograma": dict(sorted(hist.items(), key=lambda kv: -kv[1]))}


def rastrear_instrucoes(cpu: str, registos: list, cfg, est: dict, trabalho: Path, firmware_dir: Path = FIRMWARE_DIR,
                        n_calibracao: int = 40, n_voo: int = 41, opt: str = "-O2") -> dict:
    """Corre os registos no QEMU com o traço `-d exec` (uma instrução por bloco, filtrado às funções do núcleo/libm/runtime) e devolve, por passo
    de voo, a CONTAGEM EXATA de instruções (instruction-accurate) e a sequência executada de dois passos (um com decisão da cascata — «tick» a
    50 Hz — e outro sem) com o texto de cada instrução; mais as chamadas à libm e o histograma por mnemónico.

    A sequência de registos é cortada: ciclo de vida + `n_calibracao` passos de calibração no chão + travar + `n_voo` passos de voo (o traço
    de um voo inteiro teria GB). O passo 0 do voo é um «tick» (a cascata decide no 1.º passo depois de travar e de 10 em 10)."""
    trabalho = Path(trabalho)
    trabalho.mkdir(parents=True, exist_ok=True)
    ops = [r.op for r in registos]
    i_on = ops.index(OPS["calibrar_chao_on"])
    i_off = ops.index(OPS["calibrar_chao_off"])
    i_trav = ops.index(OPS["travar"])
    corte = list(registos[: i_on + 1]) + [r for r in registos[i_on + 1: i_off] if r.op == OPS["passo"]][:n_calibracao]
    corte += list(registos[i_off: i_trav + 1])
    voo = [r for r in registos[i_trav + 1:] if r.op == OPS["passo"]][:n_voo]
    corte += voo
    entrada = trabalho / "entrada.bin"
    escrever_entrada(entrada, cfg, corte, est, int(ctypes.c_uint32.from_buffer_copy(bytes(cfg)[:4]).value))
    elf = compilar_imagem(cpu, firmware_dir, opt=opt, extra=EXTRA_TRACO)
    objs = {n: next(iter((Path(elf.parent) / f"obj_{cpu}_{elf.stem.split('_')[-1]}").glob(f"{n}.o"))) for n in ("nucleo", "libm", "rt")}
    dfiltro, info = _ranges_dfilter(elf, objs)
    desm = _desmontar(elf, cpu)
    log = trabalho / "traco.log"
    cmd = [_ferramenta("qemu-system-arm"), "-M", CPUS[cpu]["maquina"], "-cpu", CPUS[cpu]["mcpu"], "-nographic", "-monitor", "none",
           "-serial", "none", "-chardev", "stdio,id=con", "-semihosting-config", "enable=on,target=native,chardev=con",
           "-accel", "tcg,one-insn-per-tb=on", "-d", "exec,nochain", "-dfilter", dfiltro, "-D", log, "-kernel", elf]
    r = subprocess.run([str(c) for c in cmd], cwd=trabalho, capture_output=True, text=True, timeout=900, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"QEMU do traço falhou ({r.returncode}): {r.stdout[:300]} {r.stderr[:300]}")
    ini, fim = info["marcador_inicio"][0], info["marcador_fim"][0]
    libm = {n: info[n][0] for n in ("nucleo_sinf", "nucleo_cosf", "nucleo_atan2f") if n in info}
    contagens: list[int] = []
    atual: list[int] | None = None
    guardados: dict[int, list[int]] = {}
    chamadas: dict[int, dict] = {}
    k = -1
    with open(log, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            m = RE_TRACO.match(ln)
            if not m:
                continue
            pc = int(m.group(1), 16) & ~1
            if pc == ini:
                k += 1
                atual = []
                chamadas[k] = {n: 0 for n in libm}
            if atual is not None:
                atual.append(pc)
                for n, a in libm.items():
                    if pc == a:
                        chamadas[k][n] += 1
            if pc == fim and atual is not None:
                contagens.append(len(atual))
                guardados[k] = atual
                atual = None
    n_cal = len([r_ for r_ in corte if r_.op == OPS["passo"]]) - len(voo)
    voo_cont = contagens[n_cal:]
    ticks = [j for j in range(len(voo_cont)) if j % 10 == 0]
    nao = [j for j in range(len(voo_cont)) if j % 10 != 0]

    def texto(j: int) -> list[str]:
        return [desm[a] for a in guardados[n_cal + j] if a in desm]
    res = {"cpu": cpu, "passos_voo": len(voo_cont), "contagens_voo": voo_cont,
           "tick_instr": [voo_cont[j] for j in ticks], "normal_instr": [voo_cont[j] for j in nao],
           "chamadas_libm_tick": chamadas[n_cal + ticks[len(ticks) // 2]], "chamadas_libm_normal": chamadas[n_cal + nao[len(nao) // 2]],
           "tracos": {"tick": texto(ticks[len(ticks) // 2]), "normal": texto(nao[len(nao) // 2])},
           "calibracao_instr": contagens[:n_cal][-5:], "tamanho_log_mb": log.stat().st_size / 1e6}
    log.unlink(missing_ok=True)
    return res


# =========================================================================================== CLI
def _auto_teste(args) -> int:
    t0 = time.perf_counter()
    trab = Path(tempfile.mkdtemp(prefix="qemu_alvo_"))
    try:
        print("== voo SITL (cascata) → registos")
        voo = gravar_voo(segundos=args.segundos, seed=args.seed, firmware_dir=Path(args.firmware_dir))
        R = voo["RegistoCls"]
        regs = voo["registos"] + registos_detetar(R, 12)
        print(f"  {len(regs)} registos ({voo['passos']} passos de 500 Hz)")
        rel = provar(regs, voo["cfg"], voo["est"], trab, Path(args.firmware_dir))
        ok = bool(rel.get("ok"))
        print(f"\nRESULTADO: {'OK — host ≡ M4 ≡ M7 bit a bit' if ok else 'FALHOU'} ({time.perf_counter() - t0:.0f} s)")
        return 0 if ok else 1
    finally:
        shutil.rmtree(trab, ignore_errors=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="o MESMO código do firmware em Cortex-M4/M7 emulados (QEMU)")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("auto-teste", help="grava um voo do SITL e prova host ≡ QEMU M4 ≡ QEMU M7 bit a bit")
    a.add_argument("--segundos", type=float, default=14.0)
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--firmware-dir", default=str(FIRMWARE_DIR))
    a.set_defaults(f=_auto_teste)
    args = p.parse_args(argv)
    return args.f(args)


if __name__ == "__main__":
    raise SystemExit(main())
