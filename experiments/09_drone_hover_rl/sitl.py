#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/sitl.py — SITL: o núcleo de FIRMWARE C++ (`firmware/nucleo/`) a voar o MuJoCo.

O dono decidiu que estimador + estabilização (e depois movimentação e olhar) correm num ARDUINO com
algoritmos clássicos. Esta é a ponte de simulação: compila o MESMO código C++ do firmware para uma .so
(g++, cache por hash das fontes em `out/firmware/`) e corre-o no lugar do `ControladorFC` +
`EstimadorBordo` (Python) sobre o `DroneRealEnv`, a 500 Hz, com os sensores MEDIDOS da planta
(`lab/drone_rpi`): lê os sensores → chama o núcleo → aplica `u` ao `pl.passo`. A física é SEMPRE o `mj_step`.

    ┌ planta (mj_step 500 Hz) ┐  sensores medidos   ┌ firmware/nucleo (C++ float32) ┐
    │ IMU · ToF · fluxo · INA │ ───────────────────▶ │ estimador → laço de taxa → mix │
    │ motores+ESC+bateria     │ ◀─────  u[4] ─────── │      (ctypes: nucleo_passo)    │
    └─────────────────────────┘                      └────────────────────────────────┘

PEÇAS
  · `estruturas_do_header` — LÊ os `struct` de `firmware/nucleo/config.hpp` e gera as structs de ctypes
    (Config/Sensores/Comando/Saida): uma só fonte da verdade, o layout nunca diverge (e confere-se com os
    `sizeof` da .so);
  · `compilar_nucleo` / `carregar_biblioteca` — g++ → `out/firmware/libnucleo-<hash>.so` (cache);
  · `config_de_hardware(hw, model, dt)` — a `Config` pelas MESMAS fórmulas do `fc.py` (planta → kp/ki/kd,
    mistura, idle, α…); `exportar_config_hpp` grava-a como `constexpr Config` para o .ino;
  · `NucleoCpp` — uma instância do núcleo (pool estático da .so) com `reiniciar/armar/calibrar/passo`;
  · `DroneRealEnvNucleo` — o `DroneRealEnv` com o C++ no lugar do FC+estimador (`modo_nucleo="sitl"`: o C++
    manda nos motores e a política vê as estimativas do C++) ou em SOMBRA (`"sombra"`: o Python voa e o C++
    corre em paralelo sobre os MESMOS sensores, comparando motores e estimativas passo a passo);
  · `voar` — o voo de uma política (modo comando) com perfil WASDQE e as métricas.

GANCHO para os laços externos (próxima atividade): `env.fc.preparar_comando = f(cmd, sens)` é chamado a cada
passo de 500 Hz com o `Comando` CTBR já preenchido pelo env — `f` pode mudar `cmd.modo` e os campos reservados
(vx, vy, vz, yaw_taxa) sem tocar no `env_real.py`.

    uv run --group hover-rl python experiments/09_drone_hover_rl/sitl.py compilar
    uv run --group hover-rl python experiments/09_drone_hover_rl/sitl.py config --header out/firmware/config.hpp
    uv run --group hover-rl python experiments/09_drone_hover_rl/sitl.py voo --segundos 20 [--python | --sombra]

Ordem do passo (o que o firmware real faz a cada tick de 500 Hz): ler sensores → núcleo → escrever motores.
O estimador processa a leitura MAIS RECENTE no início do passo (no Python processava-a no fim do passo
anterior): a sequência de leituras é a mesma e só muda QUANDO a estimativa fica disponível para a política
— a observação vê as estimativas com 1 amostra (2 ms) de atraso, o que é intrínseco ao laço de um FC real.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import ctypes
import hashlib
import inspect
import math
import os
import re
import subprocess
import sys
import time
import weakref
from functools import lru_cache
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

import controlo_classico as _cc
import estimador as _estimador
import fc as _fc
import numpy as np
from env import VOO_Z_MIN as VOO_Z_MIN_CONTRATO
from env_real import DroneRealEnv, build_do_hardware

FIRMWARE_DIR = _AQUI / "firmware"
NUCLEO_DIR = FIRMWARE_DIR / "nucleo"
CABECALHO_CONFIG = NUCLEO_DIR / "config.hpp"
OUT_FIRMWARE = _AQUI / "out" / "firmware"
CXX = os.environ.get("CXX", "g++")
# os mesmos avisos-como-erro do firmware (mais -ffp-contract=off: aritmética float32 sem FMA, determinística)
FLAGS_BASE = ["-std=c++17", "-O2", "-fno-exceptions", "-fno-rtti", "-ffp-contract=off",
              "-Wall", "-Wextra", "-Wdouble-promotion", "-Werror"]
FLAGS_SO = [*FLAGS_BASE, "-fPIC", "-shared"]
MODELO_VOO = _AQUI / "out" / "real_1950_voo_final" / "final.zip"

# perfil de comandos WASDQE do voo de 20 s: (t_início s, v_ref m/s no mundo) — cobre pairagem, W, A, Q, E e uma
# diagonal, para o estimador ver velocidades horizontais/verticais e inclinações ≠ 0
PERFIL_VOO = (
    (0.0, (0.0, 0.0, 0.0)),        # descolar e segurar
    (3.0, (1.0, 0.0, 0.0)),        # W: frente 1 m/s
    (6.0, (0.0, 0.0, 0.0)),
    (8.0, (0.0, 1.0, 0.0)),        # A: esquerda 1 m/s
    (11.0, (0.0, 0.0, 0.0)),
    (12.0, (0.0, 0.0, 0.7)),       # Q: subir 0,7 m/s
    (14.0, (0.0, 0.0, 0.0)),
    (15.0, (0.0, 0.0, -0.7)),      # E: descer 0,7 m/s
    (17.0, (-0.7, -0.7, 0.0)),     # S+D: diagonal para trás-direita
    (19.0, (0.0, 0.0, 0.0)),
)
T_METRICAS_S = 5.0                 # as métricas ignoram a descolagem (primeiros 5 s)


# =========================================================================================== layout (ctypes)
_TIPOS_C = {"float": ctypes.c_float, "int32_t": ctypes.c_int32, "uint32_t": ctypes.c_uint32}


def _sem_comentarios(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", texto)


def _parse_estruturas(texto: str, origem, conhecidas: dict[str, type]) -> dict[str, type]:
    """As structs de ctypes de UM texto C++ (sem comentários). Um membro pode ser de um struct já declarado — antes
    neste texto ou em `conhecidas` (ex.: os PODs de `visao_tipos.hpp`), com ou sem qualificação de namespace."""
    enums = {n: _TIPOS_C[b] for n, b in re.findall(r"\benum\s+(?:class\s+)?(\w+)\s*:\s*(\w+)\s*\{", texto)}
    achadas: dict[str, type] = {}
    for m in re.finditer(r"\bstruct\s+(\w+)\s*\{([^{}]*)\};", texto):
        nome, corpo = m.group(1), m.group(2)
        campos = []
        for decl in corpo.split(";"):
            decl = decl.strip()
            if not decl:
                continue
            mm = re.fullmatch(r"((?:\w+\s*::\s*)*\w+)\s+(\w+)((?:\s*\[\s*\d+\s*\])*)", decl)
            if mm is None:
                raise ValueError(f"struct {nome}: declaração não suportada pelo parser de layout: {decl!r}")
            tipo, campo, dims = mm.groups()
            tipo = re.split(r"\s*::\s*", tipo)[-1]
            base = enums.get(tipo) or _TIPOS_C.get(tipo) or achadas.get(tipo) or conhecidas.get(tipo)
            if base is None:
                raise ValueError(f"struct {nome}.{campo}: tipo não suportado {tipo!r}")
            for d in reversed([int(x) for x in re.findall(r"\[\s*(\d+)\s*\]", dims)]):
                base = base * d
            campos.append((campo, base))
        achadas[nome] = type(nome, (ctypes.Structure,), {"_fields_": campos})
    return achadas


def estruturas_do_header(caminho: Path = CABECALHO_CONFIG, extras: list[Path] | None = None) -> dict[str, type]:
    """Gera as structs de ctypes a partir dos `struct` do `config.hpp` (uma só fonte da verdade).

    Formato suportado (estrito — qualquer outra linha dentro de um `struct` levanta `ValueError`, para o
    layout nunca divergir em silêncio): `tipo nome;`, `tipo nome[N];`, `tipo nome[N][M];`, uma declaração por
    linha, com tipo ∈ {float, int32_t, uint32_t, enum de tipo fixo declarado no mesmo ficheiro, OUTRO struct já
    declarado (nesse ficheiro ou nos `extras`)}. Os `extras` por omissão são o `visao_tipos.hpp` da mesma pasta (os
    PODs da atividade C: Camera, ConfigSeguidor, SaidaSeguidor…), cujas structs também ficam no resultado.
    """
    caminho = Path(caminho)
    if extras is None:
        vt = caminho.parent / "visao_tipos.hpp"
        extras = [vt] if vt.is_file() else []
    conhecidas: dict[str, type] = {}
    for ex in extras:
        conhecidas.update(_parse_estruturas(_sem_comentarios(Path(ex).read_text(encoding="utf-8")), ex, conhecidas))
    estruturas = dict(conhecidas)
    estruturas.update(_parse_estruturas(_sem_comentarios(caminho.read_text(encoding="utf-8")), caminho, conhecidas))
    for nome in ("Config", "Sensores", "Comando", "Saida"):
        if nome not in estruturas:
            raise ValueError(f"{caminho}: falta o struct {nome}")
    return estruturas


def constantes_do_header(caminho: Path = CABECALHO_CONFIG) -> dict[str, int]:
    """`kFlag*`, `kVersaoInterface` e os enumeradores (Modo) do `config.hpp`, por nome."""
    texto = _sem_comentarios(Path(caminho).read_text(encoding="utf-8"))
    cons = {n: int(v) for n, v in re.findall(r"constexpr\s+int32_t\s+(k\w+)\s*=\s*(\d+)\s*;", texto)}
    cons.update({n: int(v) for n, v in re.findall(r"constexpr\s+uint32_t\s+(k\w+)\s*=\s*(\d+)u\s*;", texto)})
    for corpo in re.findall(r"\benum\s+\w+\s*:\s*\w+\s*\{([^}]*)\}", texto):
        for nome, valor in re.findall(r"(\w+)\s*=\s*(\d+)", corpo):
            cons[nome] = int(valor)
    return cons


def versao_da_interface(caminho: Path = CABECALHO_CONFIG) -> int:
    m = re.search(r"kVersaoInterface\s*=\s*(\d+)u?\s*;", _sem_comentarios(Path(caminho).read_text(encoding="utf-8")))
    if m is None:
        raise ValueError(f"{caminho}: kVersaoInterface não encontrado")
    return int(m.group(1))


ESTRUTURAS = estruturas_do_header()
Config, Sensores, Comando, Saida = (ESTRUTURAS[n] for n in ("Config", "Sensores", "Comando", "Saida"))
_CONST = constantes_do_header()
FLAG_ARMADO, FLAG_DIF_ESCALADO, FLAG_AIRMODE_BAIXO, FLAG_AIRMODE_ALTO = 1, 2, 4, 8
FLAG_MODO_RESERVADO, FLAG_FALHA_NUMERICA, FLAG_NAO_INICIADO = 16, 32, 64
FLAG_SAT_INCLINACAO, FLAG_SAT_YAW_TAXA, FLAG_SAT_YAW_ACEL = (_CONST[k] for k in (
    "kFlagSatInclinacao", "kFlagSatYawTaxa", "kFlagSatYawAcel"))
FLAG_SAT_COLETIVO, FLAG_CALIBRANDO, FLAG_FALHA_CASCATA, FLAG_SAT_TAXA_RP = (_CONST[k] for k in (
    "kFlagSatColetivo", "kFlagCalibrando", "kFlagFalhaCascata", "kFlagSatTaxaRP"))
MODO_CTBR, MODO_VELOCIDADE, MODO_OLHAR, MODO_YAW_ALVO = 0, 1, 2, 3
MODOS_COMANDO = {"ctbr": MODO_CTBR, "velocidade": MODO_VELOCIDADE, "olhar": MODO_OLHAR, "yaw_alvo": MODO_YAW_ALVO}
CAMPOS_ESTIMATIVA = ("roll", "pitch", "psi", "h", "vz", "vx", "vy", "x", "y")


# =========================================================================================== compilação
@lru_cache(maxsize=4)
def _versao_do_compilador(cxx: str) -> str:
    r = subprocess.run([cxx, "--version"], capture_output=True, text=True, check=True)
    return r.stdout.splitlines()[0].strip()


def fontes_do_nucleo(pasta: Path = NUCLEO_DIR) -> list[Path]:
    """Cabeçalhos e fontes do núcleo, em ordem estável (a entrada do hash de cache)."""
    return sorted(Path(pasta).glob("*.hpp")) + sorted(Path(pasta).glob("*.cpp"))


def hash_das_fontes(pasta: Path = NUCLEO_DIR, flags: list[str] | None = None, cxx: str = CXX) -> str:
    h = hashlib.sha256()
    h.update(_versao_do_compilador(cxx).encode())
    h.update(" ".join(FLAGS_SO if flags is None else flags).encode())
    for f in fontes_do_nucleo(pasta):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def compilar_nucleo(pasta: Path = NUCLEO_DIR, destino: Path = OUT_FIRMWARE, cxx: str = CXX,
                    flags: list[str] | None = None, limpar: bool = True) -> Path:
    """Compila `pasta/*.cpp` numa .so (cache por hash das fontes+flags+compilador). Devolve o caminho.

    Compila para um ficheiro temporário e renomeia (atómico: dois processos a construir ao mesmo tempo não se
    pisam). Um erro de compilação (os avisos são erros) levanta `RuntimeError` com a saída do compilador.
    """
    pasta, destino = Path(pasta), Path(destino)
    flags = list(FLAGS_SO if flags is None else flags)
    alvo = destino / f"libnucleo-{hash_das_fontes(pasta, flags, cxx)}.so"
    if alvo.is_file():
        return alvo
    destino.mkdir(parents=True, exist_ok=True)
    cpps = sorted(pasta.glob("*.cpp"))
    if not cpps:
        raise FileNotFoundError(f"sem fontes .cpp em {pasta}")
    tmp = destino / f".{alvo.name}.{os.getpid()}.tmp"
    r = subprocess.run([cxx, *flags, *map(str, cpps), "-o", str(tmp), "-lm"], capture_output=True, text=True,
                       check=False)
    if r.returncode != 0:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise RuntimeError(f"falha a compilar o núcleo ({cxx}):\n{r.stderr}")
    os.replace(tmp, alvo)
    if limpar:                                  # mantém as 4 compilações mais recentes
        antigas = sorted(destino.glob("libnucleo-*.so"), key=lambda p: p.stat().st_mtime, reverse=True)[4:]
        for p in antigas:
            with contextlib.suppress(OSError):
                p.unlink()
    return alvo


class BibliotecaNucleo:
    """A .so carregada + as structs de ctypes geradas dos cabeçalhos (com o layout conferido)."""

    def __init__(self, caminho_so: Path, cabecalho: Path = CABECALHO_CONFIG):
        self.caminho = Path(caminho_so)
        self.estruturas = estruturas_do_header(cabecalho)
        for nome, cls in self.estruturas.items():          # Config, Sensores, Comando, Saida, ReferenciasTaxa, Camera…
            setattr(self, nome, cls)
        self.const = constantes_do_header(cabecalho)
        self.lib = lib = ctypes.CDLL(str(self.caminho))
        c_i32, c_u32, c_f = ctypes.c_int32, ctypes.c_uint32, ctypes.c_float
        P = ctypes.POINTER
        lib.nucleo_versao.restype = c_u32
        for nome in ("config", "sensores", "comando", "saida", "nucleo", "referencias"):
            fn = getattr(lib, f"nucleo_tamanho_{nome}")
            fn.restype = c_u32
        lib.nucleo_criar.restype = c_i32
        lib.nucleo_liberar.argtypes = [c_i32]
        lib.nucleo_iniciar.argtypes = [c_i32, P(self.Config)]
        lib.nucleo_iniciar.restype = c_i32
        lib.nucleo_reiniciar.argtypes = [c_i32]
        lib.nucleo_armar.argtypes = [c_i32, c_i32]
        lib.nucleo_calibrar.argtypes = [c_i32, P(self.Sensores)]
        lib.nucleo_calibrar_chao.argtypes = [c_i32, c_i32]
        lib.nucleo_travar_referencias.argtypes = [c_i32, c_i32, c_f]
        lib.nucleo_estimativas.argtypes = [c_i32, P(self.Saida)]
        lib.nucleo_passo.argtypes = [c_i32, P(self.Sensores), P(self.Comando), c_f, P(self.Saida)]
        lib.nucleo_planear.argtypes = [c_i32, P(self.Sensores), P(self.Comando), c_f, P(self.ReferenciasTaxa),
                                       P(self.Saida)]
        lib.nucleo_atuar.argtypes = [c_i32, P(self.ReferenciasTaxa), P(self.Sensores), c_f, P(self.Saida)]
        # peças da interface 2 testáveis SOZINHAS (golden vectors do protótipo Python)
        lib.cascata_criar.restype = c_i32
        lib.cascata_liberar.argtypes = [c_i32]
        lib.cascata_iniciar.argtypes = [c_i32, P(self.ConfigCascata)]
        lib.cascata_armar.argtypes = [c_i32, c_i32]
        lib.cascata_travar.argtypes = [c_i32, P(self.Saida), c_i32, c_f]
        lib.cascata_passo.argtypes = [c_i32, P(self.ConfigCascata), P(self.Saida), P(c_f), P(self.Comando), c_f,
                                      P(c_f), P(c_i32), P(self.Saida)]
        lib.estcl_criar.restype = c_i32
        lib.estcl_liberar.argtypes = [c_i32]
        lib.estcl_zerar.argtypes = [c_i32]
        lib.estcl_iniciar_com.argtypes = [c_i32, P(self.Sensores)]
        lib.estcl_janela.argtypes = [c_i32, P(self.Config), c_i32]
        lib.estcl_passo.argtypes = [c_i32, P(self.Config), P(self.Sensores), c_f, P(self.Saida)]
        # a atividade C (detetor/seguidor) vai na MESMA .so (capi_visao.cpp): configuração por omissão do seguidor
        lib.seguidor_config_padrao.argtypes = [c_i32, c_i32, c_f, c_i32, P(self.ConfigSeguidor)]
        self._conferir_layout()

    def _conferir_layout(self) -> None:
        for nome, cls in (("config", self.Config), ("sensores", self.Sensores),
                          ("comando", self.Comando), ("saida", self.Saida),
                          ("referencias", self.ReferenciasTaxa)):
            c, py = int(getattr(self.lib, f"nucleo_tamanho_{nome}")()), ctypes.sizeof(cls)
            if c != py:
                raise RuntimeError(f"layout divergente em {nome}: C++ sizeof={c} · ctypes sizeof={py}")
        if int(self.lib.nucleo_versao()) != versao_da_interface():
            raise RuntimeError("versão da interface da .so ≠ a do config.hpp")

    @property
    def tamanho_nucleo(self) -> int:
        return int(self.lib.nucleo_tamanho_nucleo())

    def config_seguidor_padrao(self, largura: int, altura: int, fovy_graus: float, modelo: int = 2):
        """`visao::config_padrao` (C++) para uma câmara largura×altura com FoV vertical `fovy_graus` (modelo 2 = KF-CA)."""
        cfg = self.ConfigSeguidor()
        self.lib.seguidor_config_padrao(int(largura), int(altura), float(fovy_graus), int(modelo), cfg)
        return cfg


def carregar_biblioteca(pasta: Path = NUCLEO_DIR, destino: Path = OUT_FIRMWARE, cxx: str = CXX) -> BibliotecaNucleo:
    """Compila (se preciso) e carrega o núcleo. As structs vêm do `config.hpp` da MESMA pasta."""
    so = compilar_nucleo(pasta, destino, cxx)
    return BibliotecaNucleo(so, Path(pasta) / "config.hpp")


_BIB: BibliotecaNucleo | None = None


def biblioteca_padrao() -> BibliotecaNucleo:
    global _BIB
    if _BIB is None:
        _BIB = carregar_biblioteca()
    return _BIB


# =========================================================================================== uma instância
class NucleoCpp:
    """Uma instância do núcleo C++ (do pool estático da .so) — `iniciar/reiniciar/armar/calibrar/passo`.

    Os buffers `sens`, `cmd` e `saida` são reutilizados: preencha `sens`/`cmd`, chame `passo(dt)` e leia
    `saida` (é sobrescrita a cada chamada — copie o que precisar).
    """

    def __init__(self, cfg, bib: BibliotecaNucleo | None = None):
        self.bib = bib or biblioteca_padrao()
        self.id = int(self.bib.lib.nucleo_criar())
        if self.id < 0:
            raise RuntimeError("pool de instâncias do núcleo esgotado (16)")
        self.cfg = self.bib.Config.from_buffer_copy(cfg)
        self.sens = self.bib.Sensores()
        self.cmd = self.bib.Comando()
        self.saida = self.bib.Saida()
        self.ref = self.bib.ReferenciasTaxa()
        self._p_cfg = ctypes.byref(self.cfg)
        self._p_sens = ctypes.byref(self.sens)
        self._p_cmd = ctypes.byref(self.cmd)
        self._p_saida = ctypes.byref(self.saida)
        self._p_ref = ctypes.byref(self.ref)
        self.iniciado = bool(self.bib.lib.nucleo_iniciar(self.id, self._p_cfg) == 1)

    def exigir_iniciado(self) -> NucleoCpp:
        if not self.iniciado:
            raise ValueError("o núcleo recusou a Config (versão/NaN/frequências inválidas)")
        return self

    def reiniciar(self) -> None:
        self.bib.lib.nucleo_reiniciar(self.id)

    def armar(self, armado: bool) -> None:
        self.bib.lib.nucleo_armar(self.id, 1 if armado else 0)

    def calibrar(self) -> None:
        """Calibra o estimador com `sens` e atualiza `saida` com as estimativas."""
        self.bib.lib.nucleo_calibrar(self.id, self._p_sens)
        self.bib.lib.nucleo_estimativas(self.id, self._p_saida)

    def passo(self, dt: float):
        self.bib.lib.nucleo_passo(self.id, self._p_sens, self._p_cmd, dt, self._p_saida)
        return self.saida

    def calibrar_chao(self, ativa: bool) -> None:
        """Abre/fecha a janela de calibração do giroscópio com o drone PARADO no chão (estimador clássico)."""
        self.bib.lib.nucleo_calibrar_chao(self.id, 1 if ativa else 0)

    def travar_referencias(self, com_z_alvo: bool = False, z_alvo: float = 0.0) -> None:
        """Trava as referências da cascata (x, y, ψ, altura) nas estimativas atuais; `com_z_alvo` = descolar até `z_alvo`."""
        self.bib.lib.nucleo_travar_referencias(self.id, 1 if com_z_alvo else 0, float(z_alvo))

    def planear(self, dt: float):
        """Passos 1–2 (estimador + laços externos): devolve a `ReferenciasTaxa` (buffer `self.ref`, reutilizado)."""
        self.bib.lib.nucleo_planear(self.id, self._p_sens, self._p_cmd, dt, self._p_ref, self._p_saida)
        return self.ref

    def atuar(self, ref, dt: float):
        """Passos 3–4 (laço de taxa + mistura + saneamento) com as referências `ref`; completa `self.saida`."""
        self.bib.lib.nucleo_atuar(self.id, ctypes.byref(ref), self._p_sens, dt, self._p_saida)
        return self.saida

    def motores(self) -> np.ndarray:
        return np.array(self.saida.motor, dtype=float)

    def estimativas(self) -> dict[str, float]:
        return {k: float(getattr(self.saida, k)) for k in CAMPOS_ESTIMATIVA}

    def close(self) -> None:
        if getattr(self, "id", -1) >= 0:
            with contextlib.suppress(Exception):
                self.bib.lib.nucleo_liberar(self.id)
            self.id = -1

    def __del__(self) -> None:
        self.close()


def preencher_sensores(s, giro, acc, tof_d: float, tof_ok: bool, n_tof: int,
                       fluxo, fluxo_ok: bool, n_fluxo: int, v_bat: float = 0.0) -> None:
    """Escreve leituras (arrays/escalares Python) numa struct `Sensores`."""
    for k in range(3):
        s.giro[k] = float(giro[k])
        s.acc[k] = float(acc[k])
    s.tof_d = float(tof_d)
    s.tof_ok = 1 if tof_ok else 0
    s.n_tof = int(n_tof)
    s.fluxo[0] = float(fluxo[0])
    s.fluxo[1] = float(fluxo[1])
    s.fluxo_ok = 1 if fluxo_ok else 0
    s.n_fluxo = int(n_fluxo)
    s.v_bat = float(v_bat)


def sensores_da_planta(pl, s) -> None:
    """Lê os sensores MEDIDOS da planta (`lab.drone_rpi.Planta`) para a struct `Sensores` do núcleo."""
    if pl.tof is None or pl.fluxo is None:
        raise ValueError("o núcleo precisa do ToF e do fluxo ótico (o build não os tem)")
    tof, fl = pl.tof, pl.fluxo
    preencher_sensores(s, pl.imu.giro.medicao, pl.imu.acc.medicao, tof.distancia, tof.valido, tof.s.n_amostras,
                       fl.fluxo, fl.valido, fl.s.n_amostras, pl.monitor.tensao)


def definir_comando_ctbr(c, coletivo: float, taxas) -> None:
    c.modo = MODO_CTBR
    c.coletivo = float(coletivo)
    for k in range(3):
        c.taxas[k] = float(taxas[k])
    c.vx = c.vy = c.vz = c.yaw_taxa = 0.0


def definir_comando_dict(c, d: dict | None) -> None:
    """Escreve num `Comando` o dict do protótipo Python (`CascataClassica.passo`): `vx vy vz yaw_taxa` (referencial do
    RUMO), `modo` ∈ {velocidade, yaw_alvo, olhar, ctbr}, `yaw` (rumo absoluto), `z_alvo` (descolar). `None`/{} = pairar."""
    d = d or {}
    c.modo = MODOS_COMANDO[d.get("modo", "velocidade")]
    c.coletivo = float(d.get("coletivo", 0.0))
    for k in range(3):
        c.taxas[k] = float(d.get("taxas", (0.0, 0.0, 0.0))[k])
    c.vx, c.vy, c.vz = (float(d.get(k, 0.0)) for k in ("vx", "vy", "vz"))
    c.yaw_taxa = float(d.get("yaw_taxa", 0.0))
    c.yaw = float(d["yaw"]) if d.get("yaw") is not None else 0.0
    z = d.get("z_alvo")
    c.tem_z_alvo, c.z_alvo = (0, 0.0) if z is None else (1, float(z))


# =========================================================================================== Config da planta
def inercia_do_corpo(model) -> np.ndarray:
    """Diagonal da inércia no frame do CORPO (o MuJoCo guarda-a nos eixos principais): I = R·diag·Rᵀ."""
    import mujoco
    corpo = model.body("drone").id
    r = np.zeros(9)
    mujoco.mju_quat2Mat(r, model.body_iquat[corpo])
    r = r.reshape(3, 3)
    return np.diag(r @ np.diag(model.body_inertia[corpo]) @ r.T).copy()


# Literais do protótipo Python (controlo_classico.py) que a Config do núcleo também transporta — nenhum é «afinado» aqui:
# espelham os números do `CascataClassica.passo` / `EstimadorClassico.passo` (o teste de equivalência prova que batem).
LITERAIS_CASCATA = {"lim_i_vel": 2.0, "lim_i_z": 0.4, "tol_alvo_z": 0.01, "tol_alvo_vz": 0.05, "v_trava": 0.03,
                    "fz_min_frac": 0.2, "cos_incl_min": 0.2}
LITERAIS_ESTIMADOR = {"lim_bias_acc": 0.5, "lim_bias_pi": 0.02}
T_CALIBRACAO_GIRO_S = 1.0          # s parado no chão antes de armar a cascata (o do avaliar_classico.py)
N_ESC_MAX = 16                     # nós da curva do ESC que a Config comporta


def deslocamento_sensor_cm(model) -> float:
    """Altura do CM acima do sensor de baixo (o ToF mede a altura do SENSOR; o env mede a do CM) — geometria do build."""
    return -float(model.site_pos[model.site("baixo").id][2])


def u_pairagem_de_tensao(hw, omega_pairagem: float, v: float, u_nominal: float) -> float:
    """O `DroneRealEnv.acelerador_pairagem()` para uma tensão `v` EXPLÍCITA (a original lê o monitor da planta):
    acelerador que sustenta a pairagem (ω nominal) com o barramento a `v`; monitor inválido ⇒ o nominal."""
    if not v > 0.5 * hw.bateria.v_nominal:
        return u_nominal
    d = hw.duty_para_omega(omega_pairagem, v)
    return float(min(hw.duty_para_acelerador(min(d, hw.duty_max)), 1.0))


def _preencher_cascata(cfg, hw, g, decimacao: int) -> None:
    """`ConfigCascata` ← `GanhosCascata` (mesmos nomes), a decimação do laço e a compensação de tensão da planta."""
    cc = cfg.cascata
    for nome, _tipo in cc._fields_:
        if hasattr(g, nome):
            v = getattr(g, nome)
            setattr(cc, nome, int(v) if isinstance(v, (bool, int)) else float(v))
    cc.decimacao = int(decimacao)
    cc.ref_posicao_trava = 1 if g.ref_posicao == "trava" else 0
    for nome, valor in LITERAIS_CASCATA.items():
        setattr(cc, nome, float(valor))
    omega = float(hw.ponto_pairagem(hw.bateria.v_nominal)["omega"])
    u, d = hw.curva_esc
    if len(u) > N_ESC_MAX:
        raise ValueError(f"a curva do ESC tem {len(u)} nós (máximo {N_ESC_MAX})")
    cfg.upv_k = float(hw.duty_para_omega(omega, 1.0))          # duty = K/V (K = ke·ω + R·I em regime)
    cfg.n_esc = len(u)
    for i in range(len(u)):
        cfg.esc_u[i], cfg.esc_d[i] = float(u[i]), float(d[i])
    cfg.v_bat_valida_min = 0.5 * float(hw.bateria.v_nominal)


def _preencher_estimador_classico(cfg, opcoes: dict | None) -> None:
    """`ConfigEstimadorClassico` ← os defaults de `EstimadorClassico.__init__` (lidos por introspeção) + `opcoes`."""
    padrao = {k: v.default for k, v in inspect.signature(_cc.EstimadorClassico.__init__).parameters.items()
              if v.default is not inspect.Parameter.empty}
    padrao.update(opcoes or {})
    e = cfg.est_cl
    e.cal_giro, e.portao_acc, e.bias_acc_z = int(padrao["cal_giro"]), int(padrao["portao_acc"]), int(padrao["bias_acc_z"])
    e.a_portao, e.ki_mahony = float(padrao["a_portao"]), float(padrao["ki_mahony"])
    e.tau_acc_portao = float(_cc.TAU_ACC_PORTAO)
    e.lim_bias_acc, e.lim_bias_pi = LITERAIS_ESTIMADOR["lim_bias_acc"], LITERAIS_ESTIMADOR["lim_bias_pi"]
    cfg.k_atitude = float(padrao["k_atitude"])


def config_de_hardware(hw, model, dt: float, estruturas: dict[str, type] | None = None, *, env=None, ganhos=None,
                       ganhos_kw: dict | None = None, estimador_classico: bool = False, opcoes_estimador: dict | None = None,
                       camera: dict | None = None, bib=None):
    """A `Config` do núcleo calculada da PLANTA pelas MESMAS fórmulas do `fc.py` (`ControladorFC.__init__`):

        ω̇ ≈ α·u_mix,   α_eixo = 4·braço_eixo·(dT/du)/I_eixo   (yaw: 4·(kq/kf)·(dT/du)/I_zz)
        K_p = 1/(α·4ζ²·τ_m),  K_i = K_p·ω_c/4,  K_d = 0,15·K_p·τ_m,  ω_c = 1/(2·τ_m),  ζ = 0,7
        mistura X: roll +sign(y) · pitch −sign(x) · yaw −s_i

    e as constantes do estimador (`estimador.py`). Reimplementa-as (não instancia o `ControladorFC`) para que
    o teste possa conferir as duas derivações uma contra a outra.

    INTERFACE 2 (opcional; sem `env`/`ganhos` a Config é a da v1: só CTBR e EstimadorBordo):
      · `estimador_classico` — liga o `EstimadorClassico` (`opcoes_estimador` = `cal_giro`, `portao_acc`, `a_portao`,
        `bias_acc_z`, `ki_mahony`, `k_atitude`);
      · `env` (um `DroneRealEnv`) ou `ganhos` (uma `GanhosCascata` já calculada) — liga a CASCATA: a `ConfigCascata` sai
        de `ganhos_de_hardware(env, **ganhos_kw)` (planta → ganhos e limites; `ganhos_kw` = u_yaw_por_taxa identificado,
        altura_min…), a decimação do laço do env e a compensação de tensão (curva do ESC + K do ciclo de pairagem);
      · `camera` (dict `largura, altura, fovy_graus, atraso_s[, raio_alvo_m, dist_alvo_m, seguidor={…}]`) + `bib` — liga o
        olhar: `ConfigSeguidor` = `visao::config_padrao` (C++) da câmara, com os limites de yaw/velocidade IGUAIS aos
        da cascata (o IBVS não pode pedir mais yaw do que a planta tem).
    """
    est = estruturas or ESTRUTURAS
    inercia = inercia_do_corpo(model)
    v = hw.bateria.v_nominal
    ph = hw.ponto_pairagem(v)
    w_h = ph["omega"]
    kt = ke = hw.motor.ke
    b = kt * ke / hw.r_motor + 0.5 * kt * hw.motor.i0 / hw.omega0 + 2.0 * hw.kq * w_h
    dw_du = (kt * v / hw.r_motor) / b * hw.inclinacao_esc(ph["acelerador"])
    tau_motor = hw.j_rotor / b
    dt_du = 2.0 * hw.kf * w_h * dw_du
    a = hw.braco / math.sqrt(2.0)
    alfa = np.array([4.0 * a * dt_du / inercia[0], 4.0 * a * dt_du / inercia[1],
                     4.0 * (hw.kq / hw.kf) * dt_du / inercia[2]])
    kp = 1.0 / (alfa * 4.0 * _fc.ZETA * _fc.ZETA * tau_motor)
    wc = 1.0 / (2.0 * tau_motor)
    ki = kp * wc / 4.0
    kd = 0.15 * kp * tau_motor
    pos = hw.pos_rotores
    mix = np.stack([np.sign(pos[:, 1]), -np.sign(pos[:, 0]), -hw.GIRO], axis=1)

    cfg = est["Config"]()
    cfg.versao = versao_da_interface()
    cfg.dt_nominal = float(dt)
    for e in range(3):
        cfg.kp[e], cfg.ki[e], cfg.kd[e] = float(kp[e]), float(ki[e]), float(kd[e])
    cfg.limite_i = _fc.LIMITE_I
    cfg.fc_giro_hz = _fc.FILTRO_GIRO_HZ
    cfg.fc_d_hz = _fc.FILTRO_D_HZ
    cfg.idle = float(hw.esc.idle)
    for i in range(4):
        for e in range(3):
            cfg.mix[i][e] = float(mix[i, e])
    cfg.u_pairagem = float(ph["acelerador"])
    cfg.gravidade = _estimador.G
    cfg.k_atitude = _estimador.K_ATITUDE
    cfg.w_altura = _estimador.W_ALTURA
    cfg.zeta_altura = _estimador.ZETA_ALTURA
    cfg.periodo_tof_min = 1.0 / 30.0           # `max(dt, 1/30)` do estimador (taxa mínima assumida do ToF)
    cfg.alfa_fluxo = _estimador.ALFA_FLUXO
    cfg.decai_fluxo = _estimador.DECAI_FLUXO

    # ---- interface 2
    if estimador_classico:
        cfg.estimador_classico = 1
        _preencher_estimador_classico(cfg, opcoes_estimador)
    if ganhos is None and env is not None:
        ganhos = _cc.ganhos_de_hardware(env, **(ganhos_kw or {}))
    if ganhos is not None:
        cfg.usa_cascata = 1
        _preencher_cascata(cfg, hw, ganhos, int(env.decimation) if env is not None else 10)
    if camera is not None:
        if ganhos is None:
            raise ValueError("`camera` (olhar) exige a cascata (`env` ou `ganhos`)")
        biblioteca = bib or biblioteca_padrao()
        sc = biblioteca.config_seguidor_padrao(camera["largura"], camera["altura"], camera["fovy_graus"],
                                               camera.get("modelo", 2))
        sc.atraso_nominal_s = float(camera.get("atraso_s", sc.atraso_nominal_s))
        sc.yaw_max, sc.yaw_acel_max = float(ganhos.taxa_yaw_max), float(ganhos.acel_yaw_max)
        sc.vx_max, sc.vz_max = float(ganhos.vel_xy_max), float(ganhos.vel_z_max)
        for k in ("raio_alvo_m", "dist_alvo_m"):
            if k in camera:
                setattr(sc, k, float(camera[k]))
        for k, val in (camera.get("seguidor") or {}).items():
            if not hasattr(sc, k):
                raise AttributeError(f"ConfigSeguidor não tem o campo {k!r}")
            setattr(sc, k, val)
        ctypes.memmove(ctypes.addressof(cfg.seguidor), ctypes.addressof(sc), ctypes.sizeof(sc))
        cfg.usa_visao = 1
    return cfg


def config_para_dict(cfg) -> dict:
    """A struct (com arrays aninhados) como dict/listas Python — para imprimir e comparar."""
    def valor(v):
        if isinstance(v, ctypes.Structure):
            return config_para_dict(v)
        return [valor(x) for x in v] if hasattr(v, "_length_") else v
    return {nome: valor(getattr(cfg, nome)) for nome, _ in cfg._fields_}


def _lit_cpp(v) -> str:
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValueError(f"a Config tem um valor não finito ({v}): não se exporta para o .ino")
        s = f"{v:.9g}"
        return (s if any(c in s for c in ".eEn") else s + ".0") + "f"
    return f"{int(v)}u" if int(v) >= 0 else f"{int(v)}"


def exportar_config_hpp(cfg, caminho: Path, nome: str = "kConfig", cabecalho: str = "nucleo/config.hpp") -> Path:
    """Grava a `Config` como `constexpr nucleo::Config` para o .ino (`#include` + `g_nucleo.iniciar(kConfig)`).

    O número de cada campo sai com 9 dígitos significativos (round-trip exato de float32), na ORDEM do struct.
    """
    def fmt(v) -> str:
        if isinstance(v, ctypes.Structure):                       # struct aninhada: chavetas por campo, na ordem
            return "{" + ", ".join(fmt(getattr(v, n)) for n, _ in v._fields_) + "}"
        if hasattr(v, "_length_"):
            return "{" + ", ".join(fmt(x) for x in v) + "}"
        return _lit_cpp(v)

    linhas = [f"    /* {n} */ {fmt(getattr(cfg, n))}," for n, _ in cfg._fields_]
    corpo = "\n".join(linhas).rstrip(",")
    texto = (f"// GERADO por experiments/09_drone_hover_rl/sitl.py (config_de_hardware) — NÃO EDITAR À MÃO.\n"
             f"// Regerar: sitl.py config --header <ficheiro>\n#pragma once\n\n#include \"{cabecalho}\"\n\n"
             f"constexpr nucleo::Config {nome} = {{\n{corpo}\n}};\n")
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
    return caminho


# =========================================================================================== env com o núcleo
class _AdaptadorFC:
    """Faz de `ControladorFC` para o `DroneRealEnv.step`: lê os sensores medidos da planta, chama o núcleo
    C++ e devolve o acelerador por motor. Em SOMBRA o Python é quem manda: corre o `ControladorFC` e compara."""

    def __init__(self, env, nucleo: NucleoCpp, fc_py=None, est_py=None):
        self.env, self.nucleo = env, nucleo
        self.fc_py, self.est_py = fc_py, est_py
        self.sombra = fc_py is not None
        self.passos = 0
        # GANCHO para os laços externos (próxima atividade): `f(cmd, sens)` chamada a cada passo DEPOIS de o `Comando`
        # CTBR vindo do env estar preenchido — pode mudar `cmd.modo` e os campos vx/vy/vz/yaw_taxa (ver o config.hpp)
        self.preparar_comando = None
        self.du = []          # |u_cpp − u_py| por passo (4) — só em sombra
        self.de = []          # estimativas (9): cpp − py por passo — só em sombra
        self.flags_vistas = 0

    def reiniciar(self) -> None:
        if self.sombra:
            self.fc_py.reiniciar()
        self.nucleo.reiniciar()

    def armar(self, armado: bool) -> None:
        if self.sombra:
            self.fc_py.armar(armado)
        self.nucleo.armar(armado)

    def passo(self, acelerador, taxas_sp, giro_medido) -> np.ndarray:
        n = self.nucleo
        sensores_da_planta(self.env.planta, n.sens)
        for k in range(3):                                  # o giro que o env passou é o `pl.imu.giro.medicao`
            n.sens.giro[k] = float(giro_medido[k])
        definir_comando_ctbr(n.cmd, acelerador, taxas_sp)
        if self.preparar_comando is not None:
            self.preparar_comando(n.cmd, n.sens)
        if not self.sombra:
            return np.array(n.passo(self.env.dt).motor, dtype=float)
        py = self.est_py                                    # estado do estimador Python ANTES deste passo
        antes = (py.roll, py.pitch, py.psi, py.h, py.vz, py.vx, py.vy, py.x, py.y)
        u_py = self.fc_py.passo(acelerador, taxas_sp, giro_medido)
        out = n.passo(self.env.dt)
        self.du.append(np.array(out.motor, dtype=float) - u_py)
        self.de.append(np.array([getattr(out, k) for k in CAMPOS_ESTIMATIVA]) - np.array(antes))
        self.flags_vistas |= int(out.flags)
        self.passos += 1
        return u_py


class _AdaptadorEstimador:
    """Faz de `EstimadorBordo` para o env em SITL: as estimativas são as do núcleo C++ (lidas da última
    `Saida`); o `passo` não faz nada porque o núcleo já estimou dentro de `_AdaptadorFC.passo`."""

    def __init__(self, adaptador_fc: _AdaptadorFC):
        self._fc = adaptador_fc

    def reiniciar(self, acc=None, tof_d: float = 0.0, tof_ok: bool = False) -> None:
        # o env chama-o logo a seguir a reiniciar a planta: calibra o núcleo com as leituras de agora
        env = self._fc.env
        n = self._fc.nucleo
        sensores_da_planta(env.planta, n.sens)
        n.calibrar()

    def passo(self, *args, **kwargs) -> None:
        return None

    def _saida(self):
        return self._fc.nucleo.saida

    roll = property(lambda self: float(self._saida().roll))
    pitch = property(lambda self: float(self._saida().pitch))
    psi = property(lambda self: float(self._saida().psi))
    h = property(lambda self: float(self._saida().h))
    vz = property(lambda self: float(self._saida().vz))
    vx = property(lambda self: float(self._saida().vx))
    vy = property(lambda self: float(self._saida().vy))
    x = property(lambda self: float(self._saida().x))
    y = property(lambda self: float(self._saida().y))


class _AdaptadorCascata(_AdaptadorFC):
    """Faz de `ControladorFC` para o `DroneRealEnv.step` no modo CASCATA: o C++ manda em TUDO (estimador clássico →
    cascata → laço de taxa → mistura) e vê SÓ os sensores medidos da planta (+ a câmara, se houver); a ação do env é ignorada.

    Entre a decisão da cascata (`planear`: 50 Hz) e o laço de taxa (`atuar`: 500 Hz) fica o ATRASO DO COMANDO da planta
    (`env.atraso_comando`, o RPi→FC do simulador: 8 ms nominais, sorteado com DR) — é uma propriedade da PLANTA, por isso
    vive aqui e não no firmware; com `atraso_passos=0` mede-se a arquitetura de um só MCU (sem ligação entre os laços).
    O comando de voo (dict do protótipo: `vx vy vz yaw_taxa modo yaw z_alvo`, referencial do rumo) é o que `definir_comando`
    guardou; por omissão pairar.
    """

    def __init__(self, env, nucleo: NucleoCpp, atraso_passos: int | None = None):
        super().__init__(env, nucleo)
        self.idle = float(env.fc.idle)                      # o `SondaFC` do avaliar_classico.py lê-o
        self.integral = np.zeros(3)                         # idem: o integral do PID de yaw do FC Python (não exposto)
        self.camera = None                                  # `sitl_camera.CameraSITL` (olhar) ou None
        self.atraso_passos = atraso_passos                  # None = o da planta
        self._fila: collections.deque = collections.deque()
        self._cmd: dict = {}
        self.t_primeira_decisao = None
        self.atuacoes = 0

    def definir_comando(self, cmd: dict | None) -> None:
        self._cmd = dict(cmd or {})

    def _atraso(self) -> int:
        if self.atraso_passos is not None:
            return int(self.atraso_passos)
        return round(float(self.env.atraso_comando) / float(self.env.dt))

    def reiniciar(self) -> None:
        self.nucleo.reiniciar()
        self._fila.clear()
        for _ in range(self._atraso()):                     # comando anterior ao arranque: neutro (como o env)
            self._fila.append(self.nucleo.bib.ReferenciasTaxa())
        self._cmd = {}
        if self.camera is not None:
            self.camera.reiniciar()

    def _sensores(self) -> None:
        n, env = self.nucleo, self.env
        sensores_da_planta(env.planta, n.sens)
        n.sens.t_us = round(float(env.data.time) * 1e6) & 0xFFFFFFFF
        if self.camera is not None:
            self.camera.atualizar(env, n.sens.camera)

    def passo(self, acelerador, taxas_sp, giro_medido) -> np.ndarray:
        n, env = self.nucleo, self.env
        self._sensores()
        definir_comando_dict(n.cmd, self._cmd)
        ref = n.planear(env.dt)
        self._fila.append(n.bib.ReferenciasTaxa.from_buffer_copy(ref))
        atrasada = self._fila.popleft()
        n.atuar(atrasada, env.dt)
        self.passos += 1
        self.flags_vistas |= int(n.saida.flags)
        return np.array(n.saida.motor, dtype=float)

    def calibrar_no_chao(self, segundos: float = T_CALIBRACAO_GIRO_S) -> None:
        """Pré-voo: o estimador clássico acumula giroscópio/acelerómetro com o drone PARADO no chão (motores em idle) —
        o «gyro calibration» de qualquer FC —, SEM avançar o relógio do episódio (`env.passos`, plano e `p_ref` não andam).
        A física é a do `mj_step`, com o laço de taxa do C++ a manter os motores em idle (comando CTBR nulo)."""
        n, env = self.nucleo, self.env
        n.calibrar_chao(True)
        definir_comando_dict(n.cmd, {"modo": "ctbr"})
        for _ in range(round(segundos / env.dt)):
            self._sensores()
            ref = n.planear(env.dt)
            n.atuar(ref, env.dt)
            env.planta.passo(np.array(n.saida.motor, dtype=float))
        n.calibrar_chao(False)

    def travar(self, z_alvo: float | None) -> None:
        """Trava as referências (x, y, ψ, altura) nas estimativas de agora; `z_alvo` (m, do sensor de baixo) = descolar."""
        self.nucleo.travar_referencias(z_alvo is not None, 0.0 if z_alvo is None else float(z_alvo))


class DroneRealEnvNucleo(DroneRealEnv):
    """`DroneRealEnv` com o núcleo de firmware C++ no lugar do `ControladorFC` + `EstimadorBordo`.

    `modo_nucleo="sitl"`    — o C++ manda nos motores e a política vê as estimativas do C++ (malha fechada, CTBR).
    `modo_nucleo="sombra"`  — o Python voa; o C++ corre em paralelo sobre os MESMOS sensores e compara
                              motores e estimativas passo a passo (`resumo_sombra()`).
    `modo_nucleo="cascata"` — INTERFACE 2: o C++ manda em TUDO (estimador clássico + cascata clássica + laço de taxa) e vê
                              SÓ os sensores; não há política (a ação do `step` é ignorada). `cascata={...}`:
                              `ganhos_kw` (de `ganhos_de_hardware`; por omissão o `altura_min` do contrato r11 e o
                              `u_yaw_por_taxa` identificado), `estimador` (opções do EstimadorClassico), `camera`
                              (dict de `config_de_hardware` → liga o olhar), `atraso_passos` (None = o da planta),
                              `calibracao_chao_s`. O comando de voo entra por `env.fc.definir_comando(dict)`.

    O laço de 500 Hz continua a ser o `DroneRealEnv.step` (10 passos de física por decisão, recompensa…): só o FC e o
    estimador são trocados por adaptadores. Só o modo de ação `ctbr`.
    """

    def __init__(self, *args, modo_nucleo: str = "sitl", biblioteca: BibliotecaNucleo | None = None,
                 cfg=None, cascata: dict | None = None, **kwargs):
        if modo_nucleo not in ("sitl", "sombra", "cascata"):
            raise ValueError(f"modo_nucleo tem de ser 'sitl', 'sombra' ou 'cascata' (recebido {modo_nucleo!r})")
        super().__init__(*args, **kwargs)
        if self.modo_acao != "ctbr":
            raise NotImplementedError("o núcleo C++ só implementa o modo CTBR (modo_acao='ctbr')")
        self.modo_nucleo = modo_nucleo
        self.cascata_opcoes = dict(cascata or {})
        if cfg is None:                                  # `cfg` explícita: ensaios com uma Config corrompida
            if modo_nucleo == "cascata":
                cfg = self._config_cascata(biblioteca)
            else:
                cfg = config_de_hardware(self.hw, self.model, self.dt)
        self.nucleo = NucleoCpp(cfg, biblioteca).exigir_iniciado()
        fc_py, est_py = self.fc, self.estimador          # os do Python (o `__init__` do pai criou-os)
        ref = weakref.proxy(self)                        # sem ciclo env ↔ adaptador: a instância do pool liberta-se
        if modo_nucleo == "sombra":                      # logo que o env sai de âmbito
            self.fc = _AdaptadorFC(ref, self.nucleo, fc_py=fc_py, est_py=est_py)
        elif modo_nucleo == "cascata":
            self.fc = _AdaptadorCascata(ref, self.nucleo, self.cascata_opcoes.get("atraso_passos"))
            self.estimador = _AdaptadorEstimador(self.fc)
        else:
            self.fc = _AdaptadorFC(ref, self.nucleo)
            self.estimador = _AdaptadorEstimador(self.fc)
        self.fc_python, self.estimador_python = fc_py, est_py
        self.camera_sitl = None
        cam = self.cascata_opcoes.get("camera")
        if modo_nucleo == "cascata" and cam:             # OLHAR: a câmara mono renderizada + o detetor C++ no laço
            from sitl_camera import CameraSITL
            self.camera_sitl = CameraSITL(self, **{k: v for k, v in cam.items() if k in (
                "largura", "altura", "fps", "latencia_s", "alvo_branco")})
            self.fc.camera = self.camera_sitl

    def _config_cascata(self, biblioteca):
        """A Config do modo cascata: estimador clássico + cascata (ganhos da PLANTA) [+ olhar]."""
        op = self.cascata_opcoes
        kw = {"altura_min": VOO_Z_MIN_CONTRATO - deslocamento_sensor_cm(self.model)}
        if op.get("u_yaw_por_taxa") is not None:
            kw["u_yaw_por_taxa"] = float(op["u_yaw_por_taxa"])
        kw.update(op.get("ganhos_kw") or {})
        camera = None
        if op.get("camera"):                             # o FoV é o do build (a câmara `fpv` do modelo); o resto é do caminho
            camera = {"largura": 320, "altura": 240, "latencia_s": 0.116, **op["camera"]}
            camera["fovy_graus"] = float(self.model.cam_fovy[self.model.camera("fpv").id])
            camera["atraso_s"] = float(camera["latencia_s"])
        return config_de_hardware(self.hw, self.model, self.dt, env=self, ganhos_kw=kw, estimador_classico=True,
                                  opcoes_estimador=op.get("estimador"), camera=camera, bib=biblioteca)

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        obs, info = super().reset(seed=seed, options=options)
        if self.modo_nucleo == "cascata":
            # B0: calibra o giroscópio no chão e arma a cascata (trava x, y, ψ; descola até `alvo_z`, altura do SENSOR)
            self.fc.calibrar_no_chao(float(self.cascata_opcoes.get("calibracao_chao_s", T_CALIBRACAO_GIRO_S)))
            self.fc.travar(self.alvo_z - deslocamento_sensor_cm(self.model))
            obs = self.observacao()
        return obs, info

    def resumo_sombra(self) -> dict:
        """Diferenças C++ − Python por passo (só em modo sombra): máximos e RMS de |Δu| e das 9 estimativas."""
        if self.modo_nucleo != "sombra" or not self.fc.du:
            raise RuntimeError("sem dados de sombra (modo_nucleo='sombra' e pelo menos 1 passo)")
        du = np.abs(np.array(self.fc.du))
        de = np.abs(np.array(self.fc.de))
        return {"passos": int(du.shape[0]), "du_max": float(du.max()), "du_rms": float(np.sqrt(np.mean(du ** 2))),
                "du_por_motor_max": du.max(axis=0).tolist(),
                "est_max": {k: float(de[:, i].max()) for i, k in enumerate(CAMPOS_ESTIMATIVA)},
                "est_rms": {k: float(np.sqrt(np.mean(de[:, i] ** 2))) for i, k in enumerate(CAMPOS_ESTIMATIVA)},
                "flags": int(self.fc.flags_vistas)}

    def close(self) -> None:
        if self.camera_sitl is not None:
            self.camera_sitl.fechar()
        self.nucleo.close()
        super().close()


# =========================================================================================== voo com política
def comando_do_perfil(t: float, perfil=PERFIL_VOO) -> tuple[float, float, float]:
    """v_ref (m/s, mundo) em vigor no instante `t` do perfil de segmentos (t_início, v_ref)."""
    v = perfil[0][1]
    for t0, vref in perfil:
        if t + 1e-9 >= t0:
            v = vref
    return v


def carregar_politica(caminho: Path = MODELO_VOO):
    """(modelo SB3, build, dados do hardware.json) — como o `avaliar_real.py`."""
    import json

    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1)               # MLP pequeno a 50 Hz: 1 fio é mais rápido e não esgota a máquina
    caminho = Path(caminho)
    hw_json = caminho.parent / "hardware.json"
    dados = json.loads(hw_json.read_text(encoding="utf-8")) if hw_json.is_file() else None
    build, _ = build_do_hardware(dados)
    return PPO.load(str(caminho), device="cpu"), build, dados


def criar_env(build, segundos: float, modo: str = "python", biblioteca=None, cascata: dict | None = None, **kwargs):
    """Env do voo: `modo` ∈ {"python", "sitl", "sombra", "cascata"} (planta idêntica; só muda quem estima/controla).
    `cascata` (só no modo cascata) = opções de `DroneRealEnvNucleo` (`ganhos_kw`, `camera`, `atraso_passos`…)."""
    comum = {"build": build, "comando": True, "episodio_s": float(segundos), "modo_acao": "ctbr", **kwargs}
    if modo == "python":
        return DroneRealEnv(**comum)
    return DroneRealEnvNucleo(**comum, modo_nucleo=modo, biblioteca=biblioteca, cascata=cascata)


class PoliticaCascata:
    """Faz de «política» no `voar()` do modo cascata: não decide nada — passa ao núcleo o `v_ref` do env (o plano WASDQE,
    que o env integra) como comando de VELOCIDADE no referencial do rumo (como o `ControladorCascata` do protótipo) e devolve
    a ação nula: quem manda nos motores é o C++."""

    def __init__(self, env, cmd_fn=None):
        self.env, self.cmd_fn = env, cmd_fn

    def predict(self, _obs, deterministic: bool = True):
        env = self.env
        cmd = self.cmd_fn(env) if self.cmd_fn else {"vx": float(env.v_ref[0]), "vy": float(env.v_ref[1]),
                                                     "vz": float(env.v_ref[2])}
        env.fc.definir_comando(cmd)
        return np.zeros(4, dtype=np.float32), None


class ControladorNucleo:
    """O `ControladorCascata` do `avaliar_classico.py` para o C++: mesma interface (`preparar/reiniciar/acao`), mas o
    controlo é o do núcleo no `DroneRealEnvNucleo` (modo cascata). `cmd_fn(t)` devolve o dict do comando de voo (referencial
    do rumo); por omissão lê o `v_ref` do próprio env, como o protótipo."""

    nome = "nucleo_cpp"

    def __init__(self, cmd_fn=None):
        self.cmd_fn = cmd_fn

    def preparar(self, env) -> None:
        pass

    def reiniciar(self, env, obs) -> None:             # a calibração no chão e o armar já aconteceram no `env.reset`
        pass

    def acao(self, env, t: float):
        cmd = self.cmd_fn(t) if self.cmd_fn else {"vx": float(env.v_ref[0]), "vy": float(env.v_ref[1]),
                                                   "vz": float(env.v_ref[2])}
        env.fc.definir_comando(cmd)
        return np.zeros(4, dtype=np.float32)


def voar(env, politica, segundos: float = 20.0, seed: int = 0, perfil=PERFIL_VOO, opcoes=None) -> dict:
    """Um voo (política determinística, modo comando) com o perfil WASDQE. Devolve as séries e as métricas.

    Métricas (depois da descolagem, t ≥ `T_METRICAS_S`): ‖xy‖ RMS e |Δz| médio/máximo — erros de
    SEGUIMENTO (relativos à referência `p_ref`, que integra o `v_ref` do perfil).
    """
    obs, _ = env.reset(seed=seed, options=opcoes)
    n_dec = round(segundos / env.dt_decisao)
    t_s, exy, ez, ev, cm = [], [], [], [], []
    terminou = False
    for k in range(n_dec):
        t = k * env.dt_decisao
        env.definir_comando(comando_do_perfil(t, perfil))
        acao, _ = politica.predict(obs, deterministic=True)
        obs, _r, term, trunc, info = env.step(acao)
        voo = info["voo"]
        t_s.append(t + env.dt_decisao)
        exy.append(voo["erro_xy"])
        ez.append(voo["erro_z"])
        ev.append(voo["erro_v"])
        cm.append(info["z"])
        if term:
            terminou = True
            break
        if trunc:
            break
    t_s, exy, ez, ev, cm = (np.array(a) for a in (t_s, exy, ez, ev, cm))
    janela = t_s >= T_METRICAS_S
    return {"terminou": terminou, "decisoes": len(t_s), "t": t_s, "erro_xy": exy, "erro_z": ez,
            "erro_v": ev, "z": cm,
            "xy_rms": float(np.sqrt(np.mean(exy[janela] ** 2))) if janela.any() else float("nan"),
            "dz_medio": float(np.mean(ez[janela])) if janela.any() else float("nan"),
            "dz_max": float(np.max(ez[janela])) if janela.any() else float("nan"),
            "z_min": float(np.min(cm)) if len(cm) else float("nan"),
            "soc_final": float(info["soc"]) if len(t_s) else float("nan")}


# =========================================================================================== CLI
def _cmd_compilar(_args) -> int:
    so = compilar_nucleo()
    bib = BibliotecaNucleo(so)
    print(f"núcleo compilado: {so}\n  hash {hash_das_fontes()} · {CXX}: {_versao_do_compilador(CXX)}\n"
          f"  sizeof: Config {ctypes.sizeof(bib.Config)} B · Sensores {ctypes.sizeof(bib.Sensores)} B · "
          f"Comando {ctypes.sizeof(bib.Comando)} B · Saida {ctypes.sizeof(bib.Saida)} B · "
          f"Nucleo (estado) {bib.tamanho_nucleo} B")
    return 0


def _cmd_config(args) -> int:
    import json

    _, build, _dados = carregar_politica(args.modelo)
    env = DroneRealEnv(build=build, modo_acao="ctbr")
    if args.cascata:                                     # a Config COMPLETA da interface 2: estimador clássico + cascata (+ olhar)
        u_yaw = args.u_yaw
        ref = MODELO_VOO.parents[1] / "classico" / "avaliacao.json"
        if u_yaw is None and ref.is_file():              # o `u/r` de yaw identificado no simulador pela B0
            u_yaw = json.loads(ref.read_text(encoding="utf-8"))["identificacao_yaw"]["u_yaw_por_taxa"]
        kw = {"altura_min": VOO_Z_MIN_CONTRATO - deslocamento_sensor_cm(env.model)}
        if u_yaw is not None:
            kw["u_yaw_por_taxa"] = float(u_yaw)
        camera = None
        if env.model.ncam:                               # câmara do build: FoV do modelo, QVGA mono, atraso nominal escolhido
            camera = {"largura": 320, "altura": 240, "fovy_graus": float(env.model.cam_fovy[env.model.camera("fpv").id]),
                      "atraso_s": args.atraso_camera}
        cfg = config_de_hardware(env.hw, env.model, env.dt, env=env, ganhos_kw=kw, estimador_classico=True, camera=camera)
    else:
        cfg = config_de_hardware(env.hw, env.model, env.dt)
    print(f"Config do build '{env.hw.nome}' (dt {env.dt * 1e3:g} ms):")
    print(json.dumps(config_para_dict(cfg), indent=1))
    if args.header:
        print(f"→ {exportar_config_hpp(cfg, Path(args.header))}")
    return 0


def _cmd_voo(args) -> int:
    politica, build, _ = carregar_politica(args.modelo)
    modo = "python" if args.python else ("sombra" if args.sombra else "sitl")
    env = criar_env(build, args.segundos, modo)
    t0 = time.perf_counter()
    r = voar(env, politica, args.segundos, seed=args.seed)
    print(f"voo {args.segundos:g} s [{modo}] seed {args.seed}: {'CAIU' if r['terminou'] else 'sobreviveu'} · "
          f"‖xy‖ RMS {r['xy_rms']:.3f} m · |Δz| médio {r['dz_medio']:.3f} m (máx {r['dz_max']:.3f}) · "
          f"{time.perf_counter() - t0:.1f} s de parede")
    if modo == "sombra":
        s = env.resumo_sombra()
        print(f"  sombra: max|Δu| {s['du_max']:.2e} · estimativas max|Δ| "
              + " ".join(f"{k} {v:.1e}" for k, v in s["est_max"].items()))
    return 1 if r["terminou"] else 0


def _cmd_cascata(args) -> int:
    """Voo com a CASCATA CLÁSSICA (sem política): o C++ manda nos motores e vê só os sensores — o perfil WASDQE do `voo`."""
    import json
    dados = json.loads((MODELO_VOO.parent / "hardware.json").read_text(encoding="utf-8"))
    build, _ = build_do_hardware(dados)
    ident = None
    ref = MODELO_VOO.parents[1] / "classico" / "avaliacao.json"
    if args.u_yaw is not None:
        ident = args.u_yaw
    elif ref.is_file():                                  # o `u/r` identificado no simulador pela B0 (README «Limites de yaw»)
        ident = json.loads(ref.read_text(encoding="utf-8"))["identificacao_yaw"]["u_yaw_por_taxa"]
    opcoes = {"u_yaw_por_taxa": ident}
    if args.atraso_passos is not None:
        opcoes["atraso_passos"] = args.atraso_passos
    env = criar_env(build, args.segundos, "cascata", cascata=opcoes)
    t0 = time.perf_counter()
    r = voar(env, PoliticaCascata(env), args.segundos, seed=args.seed)
    print(f"voo {args.segundos:g} s [cascata C++] seed {args.seed}: {'CAIU' if r['terminou'] else 'sobreviveu'} · "
          f"‖xy−p_ref‖ RMS {r['xy_rms']:.3f} m · |Δz| médio {r['dz_medio']:.3f} m (máx {r['dz_max']:.3f}) · "
          f"{time.perf_counter() - t0:.1f} s de parede · Nucleo {env.nucleo.bib.tamanho_nucleo} B de estado")
    return 1 if r["terminou"] else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="SITL: núcleo de firmware C++ contra o MuJoCo.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("compilar", help="compila o núcleo para uma .so (cache por hash)").set_defaults(f=_cmd_compilar)
    c = sub.add_parser("config", help="mostra a Config do build da política (e grava o .hpp com --header)")
    c.add_argument("--modelo", type=Path, default=MODELO_VOO)
    c.add_argument("--header", type=Path, default=None)
    c.add_argument("--cascata", action="store_true", help="a Config COMPLETA da interface 2 (estimador clássico + cascata + olhar)")
    c.add_argument("--u-yaw", type=float, default=None, help="u/r de yaw identificado (omissão: o da avaliação da B0)")
    c.add_argument("--atraso-camera", type=float, default=0.116, help="atraso nominal da câmara para o seguidor (s; Pi 0,116 · DCMI 0,021)")
    c.set_defaults(f=_cmd_config)
    v = sub.add_parser("voo", help="voa a política (modo comando, perfil WASDQE) com o núcleo C++")
    v.add_argument("--modelo", type=Path, default=MODELO_VOO)
    v.add_argument("--segundos", type=float, default=20.0)
    v.add_argument("--seed", type=int, default=0)
    g = v.add_mutually_exclusive_group()
    g.add_argument("--python", action="store_true", help="referência: FC+estimador em Python")
    g.add_argument("--sombra", action="store_true", help="Python voa, C++ em sombra a comparar")
    v.set_defaults(f=_cmd_voo)
    k = sub.add_parser("cascata", help="voa a CASCATA clássica em C++ (estimador clássico + cascata + laço de taxa; sem política)")
    k.add_argument("--segundos", type=float, default=20.0)
    k.add_argument("--seed", type=int, default=0)
    k.add_argument("--u-yaw", type=float, default=None, help="u/r de yaw identificado (omissão: o da avaliação da B0)")
    k.add_argument("--atraso-passos", type=int, default=None, help="atraso cascata→taxa em passos de 2 ms (omissão: o da planta; 0 = um só MCU)")
    k.set_defaults(f=_cmd_cascata)
    args = p.parse_args(argv)
    return args.f(args)


if __name__ == "__main__":
    raise SystemExit(main())
