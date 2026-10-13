#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/sitl_visao.py — ponte ctypes da atividade C (visão + alvo + IBVS) para o SITL.

Compila `firmware/nucleo/capi_visao.cpp` (que inclui `visao.hpp`, `alvo.hpp`, `ibvs.hpp`) numa .so (g++, cache por
hash das fontes em `out/firmware/libvisao-<hash>.so`) e expõe, em Python, as MESMAS classes C++ do firmware:

  · `DetetorCpp`  — `Detetor::detetar(frame, W, H, limiar, params) → Deteccao`;
  · `SeguidorCpp` — `Seguidor::passo(t_us, atitude, camera) → SaidaSeguidor` (estimador do alvo + lei IBVS +
                    máquina de estados), uma instância do pool estático por objeto Python.

As structs de ctypes são GERADAS lendo `firmware/nucleo/visao_tipos.hpp` (uma só fonte da verdade: o layout nunca
diverge; confere-se com os `sizeof` da .so). Não depende do `sitl.py` do núcleo de voo (não o altera nem o importa):
quando o núcleo aceitar `Camera`/`ComandoVoo`, a integração liga o `Seguidor` ao `nucleo::Nucleo` (ver README).

    uv run --group hover-rl python experiments/09_drone_hover_rl/sitl_visao.py compilar
"""
from __future__ import annotations

import contextlib
import ctypes
import hashlib
import math
import os
import random
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
FIRMWARE_DIR = _AQUI / "firmware"
NUCLEO_DIR = FIRMWARE_DIR / "nucleo"
TIPOS_HPP = NUCLEO_DIR / "visao_tipos.hpp"
CAPI_CPP = NUCLEO_DIR / "capi_visao.cpp"
OUT_FIRMWARE = _AQUI / "out" / "firmware"
CXX = os.environ.get("CXX", "g++")
# os mesmos avisos-como-erro do firmware (+ -ffp-contract=off: aritmética float32 sem FMA, determinística)
FLAGS_BASE = ["-std=c++17", "-O2", "-fno-exceptions", "-fno-rtti", "-ffp-contract=off",
              "-Wall", "-Wextra", "-Wdouble-promotion", "-Werror"]
FLAGS_SO = [*FLAGS_BASE, "-fPIC", "-shared"]
FICHEIROS_VISAO = ("visao_tipos.hpp", "visao.hpp", "alvo.hpp", "ibvs.hpp", "ibvs_ganhos.hpp", "capi_visao.cpp")
# A lei que `SeguidorCpp(lei=None)` usa: "v2" = a por omissão do firmware (`visao::config_padrao`: «seguir a bola», com v_y e as
# compensações — provada no simulador completo pelo `teste_bola.py`); "v1" = a da atividade C (`visao::config_versao1`: guinada +
# v_z + v_x, v_y = 0), que é a que o `teste_visao.py` caracteriza na planta cinemática deste módulo.
LEIS = ("v2", "v1")
LEI_OMISSAO = "v2"

_TIPOS_C = {"float": ctypes.c_float, "int32_t": ctypes.c_int32, "uint32_t": ctypes.c_uint32}


# =========================================================================================== layout (ctypes)
def _sem_comentarios(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", texto)


def estruturas_do_header(caminho: Path = TIPOS_HPP) -> dict[str, type]:
    """Gera as structs de ctypes a partir dos `struct` do `visao_tipos.hpp` (uma só fonte da verdade).

    Formato suportado (estrito — qualquer outra linha dentro de um `struct` levanta `ValueError`): `tipo nome;`,
    `tipo nome[N];`, uma declaração por linha, com tipo ∈ {float, int32_t, uint32_t, enum de tipo fixo declarado
    no mesmo ficheiro}.
    """
    texto = _sem_comentarios(Path(caminho).read_text(encoding="utf-8"))
    enums = {n: _TIPOS_C[b] for n, b in re.findall(r"\benum\s+(?:class\s+)?(\w+)\s*:\s*(\w+)\s*\{", texto)}
    estruturas: dict[str, type] = {}
    for m in re.finditer(r"\bstruct\s+(\w+)\s*\{([^{}]*)\};", texto):
        nome, corpo = m.group(1), m.group(2)
        campos = []
        for decl in corpo.split(";"):
            decl = decl.strip()
            if not decl:
                continue
            mm = re.fullmatch(r"(\w+)\s+(\w+)((?:\s*\[\s*\d+\s*\])*)", decl)
            if mm is None:
                raise ValueError(f"struct {nome}: declaração não suportada pelo parser de layout: {decl!r}")
            tipo, campo, dims = mm.groups()
            base = enums.get(tipo) or _TIPOS_C.get(tipo)
            if base is None:
                raise ValueError(f"struct {nome}.{campo}: tipo não suportado {tipo!r}")
            for d in reversed([int(x) for x in re.findall(r"\[\s*(\d+)\s*\]", dims)]):
                base = base * d
            campos.append((campo, base))
        estruturas[nome] = type(nome, (ctypes.Structure,), {"_fields_": campos})
    for nome in ("Camera", "ParamsDetetor", "Deteccao", "Atitude", "ComandoVoo", "ConfigSeguidor", "SaidaSeguidor"):
        if nome not in estruturas:
            raise ValueError(f"{caminho}: falta o struct {nome}")
    return estruturas


def constantes_do_header(caminho: Path = TIPOS_HPP) -> dict[str, int]:
    """`kFlag*`, `kVersaoVisao` e os enumeradores (Estado, ModeloAlvo, Motivo) do cabeçalho, por nome."""
    texto = _sem_comentarios(Path(caminho).read_text(encoding="utf-8"))
    cons = {n: int(v) for n, v in re.findall(r"constexpr\s+(?:u?int32_t)\s+(k\w+)\s*=\s*(\d+)u?\s*;", texto)}
    cons.update({n: int(v) for n, v in re.findall(r"constexpr\s+uint32_t\s+(k\w+)\s*=\s*(\d+)u\s*;", texto)})
    for corpo in re.findall(r"\benum\s+\w+\s*:\s*\w+\s*\{([^}]*)\}", texto):
        for nome, valor in re.findall(r"(\w+)\s*=\s*(\d+)", corpo):
            cons[nome] = int(valor)
    return cons


# =========================================================================================== compilação
@lru_cache(maxsize=4)
def _versao_do_compilador(cxx: str) -> str:
    r = subprocess.run([cxx, "--version"], capture_output=True, text=True, check=True)
    return r.stdout.splitlines()[0].strip()


def hash_das_fontes(pasta: Path = NUCLEO_DIR, flags: list[str] | None = None, cxx: str = CXX) -> str:
    h = hashlib.sha256()
    h.update(_versao_do_compilador(cxx).encode())
    h.update(" ".join(FLAGS_SO if flags is None else flags).encode())
    for nome in FICHEIROS_VISAO:
        f = Path(pasta) / nome
        h.update(nome.encode())
        h.update(f.read_bytes() if f.is_file() else b"")
    return h.hexdigest()[:16]


def compilar_visao(pasta: Path = NUCLEO_DIR, destino: Path = OUT_FIRMWARE, cxx: str = CXX,
                   flags: list[str] | None = None, limpar: bool = True) -> Path:
    """Compila `pasta/capi_visao.cpp` numa .so (cache por hash das fontes+flags+compilador). Devolve o caminho.

    Escreve num ficheiro temporário e renomeia (atómico). Um erro de compilação (os avisos são erros) levanta
    `RuntimeError` com a saída do compilador.
    """
    pasta, destino = Path(pasta), Path(destino)
    flags = list(FLAGS_SO if flags is None else flags)
    alvo = destino / f"libvisao-{hash_das_fontes(pasta, flags, cxx)}.so"
    if alvo.is_file():
        return alvo
    destino.mkdir(parents=True, exist_ok=True)
    tmp = destino / f".{alvo.name}.{os.getpid()}.tmp"
    r = subprocess.run([cxx, *flags, "-I", str(pasta), str(pasta / "capi_visao.cpp"), "-o", str(tmp), "-lm"],
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise RuntimeError(f"falha a compilar a visão ({cxx}):\n{r.stderr}")
    os.replace(tmp, alvo)
    if limpar:                                  # mantém as 6 compilações mais recentes
        antigas = sorted(destino.glob("libvisao-*.so"), key=lambda p: p.stat().st_mtime, reverse=True)[6:]
        for p in antigas:
            with contextlib.suppress(OSError):
                p.unlink()
    return alvo


class BibliotecaVisao:
    """A .so carregada + as structs de ctypes geradas do cabeçalho (com o layout conferido)."""

    def __init__(self, caminho_so: Path, cabecalho: Path = TIPOS_HPP):
        self.caminho = Path(caminho_so)
        self.estruturas = estruturas_do_header(cabecalho)
        self.const = constantes_do_header(cabecalho)
        for nome, cls in self.estruturas.items():
            setattr(self, nome, cls)
        self.lib = lib = ctypes.CDLL(str(self.caminho))
        c_i32, c_u32, c_f, c_u8 = ctypes.c_int32, ctypes.c_uint32, ctypes.c_float, ctypes.c_uint8
        P = ctypes.POINTER
        lib.visao_versao.restype = c_u32
        for nome in ("camera", "params_detetor", "deteccao", "detetor", "config_seguidor", "saida_seguidor",
                     "atitude", "seguidor"):
            fn = getattr(lib, f"visao_tamanho_{nome}", None)
            if fn is not None:
                fn.restype = c_u32
        lib.detetor_criar.restype = c_i32
        lib.detetor_liberar.argtypes = [c_i32]
        lib.detetor_params_padrao.argtypes = [c_i32, c_i32, P(self.ParamsDetetor)]
        lib.detetor_detetar.argtypes = [c_i32, P(c_u8), c_i32, c_i32, c_i32, P(self.ParamsDetetor),
                                        P(self.Deteccao)]
        lib.visao_janela_de_previsao.argtypes = [P(self.SaidaSeguidor), P(self.ParamsDetetor)]
        if hasattr(lib, "seguidor_criar"):
            lib.seguidor_criar.restype = c_i32
            lib.seguidor_liberar.argtypes = [c_i32]
            lib.seguidor_config_padrao.argtypes = [c_i32, c_i32, c_f, c_i32, P(self.ConfigSeguidor)]
            if hasattr(lib, "seguidor_config_versao1"):         # as .so de antes da versão 2 não a têm (o `teste_bola.py` carrega uma)
                lib.seguidor_config_versao1.argtypes = [P(self.ConfigSeguidor)]
            lib.seguidor_iniciar.argtypes = [c_i32, P(self.ConfigSeguidor)]
            lib.seguidor_iniciar.restype = c_i32
            lib.seguidor_reiniciar.argtypes = [c_i32]
            lib.seguidor_passo.argtypes = [c_i32, c_u32, P(self.Atitude), P(self.Camera), P(self.SaidaSeguidor)]
            lib.seguidor_estado.argtypes = [c_i32]
            lib.seguidor_estado.restype = c_i32
        self._conferir_layout()

    def _conferir_layout(self) -> None:
        for nome, cls in (("camera", self.Camera), ("params_detetor", self.ParamsDetetor),
                          ("deteccao", self.Deteccao), ("atitude", self.Atitude),
                          ("config_seguidor", self.ConfigSeguidor), ("saida_seguidor", self.SaidaSeguidor)):
            fn = getattr(self.lib, f"visao_tamanho_{nome}", None)
            if fn is None:
                continue
            c, py = int(fn()), ctypes.sizeof(cls)
            if c != py:
                raise RuntimeError(f"layout divergente em {nome}: C++ sizeof={c} · ctypes sizeof={py}")
        if int(self.lib.visao_versao()) != self.const["kVersaoVisao"]:
            raise RuntimeError("versão da interface da .so ≠ a do visao_tipos.hpp")


def carregar_biblioteca(pasta: Path = NUCLEO_DIR, destino: Path = OUT_FIRMWARE, cxx: str = CXX) -> BibliotecaVisao:
    """Compila (se preciso) e carrega a visão. As structs vêm do `visao_tipos.hpp` da MESMA pasta."""
    return BibliotecaVisao(compilar_visao(pasta, destino, cxx), Path(pasta) / "visao_tipos.hpp")


_BIB: BibliotecaVisao | None = None


def biblioteca_padrao() -> BibliotecaVisao:
    global _BIB
    if _BIB is None:
        _BIB = carregar_biblioteca()
    return _BIB


def como_dict(s) -> dict:
    """Uma struct de ctypes → dict de Python (escalares e listas)."""
    saida = {}
    for campo, _tipo in s._fields_:
        v = getattr(s, campo)
        saida[campo] = list(v) if hasattr(v, "__len__") else v
    return saida


# =========================================================================================== detetor
class DetetorCpp:
    """Uma instância do `Detetor` C++ (pool estático da .so)."""

    def __init__(self, bib: BibliotecaVisao | None = None):
        self.bib = bib or biblioteca_padrao()
        self.id = int(self.bib.lib.detetor_criar())
        if self.id < 0:
            raise RuntimeError("pool de detetores esgotado (16)")
        self.params = self.bib.ParamsDetetor()
        self.saida = self.bib.Deteccao()
        self._p_params = ctypes.byref(self.params)
        self._p_saida = ctypes.byref(self.saida)

    def params_padrao(self, largura: int, altura: int, **alteracoes):
        """Põe em `self.params` os parâmetros por omissão de um frame largura×altura (+ `alteracoes`)."""
        self.bib.lib.detetor_params_padrao(int(largura), int(altura), self._p_params)
        for k, v in alteracoes.items():
            if not hasattr(self.params, k):
                raise AttributeError(f"ParamsDetetor não tem o campo {k!r}")
            setattr(self.params, k, v)
        return self.params

    def detetar(self, frame: np.ndarray, limiar: int = 0, **alteracoes):
        """Deteta no frame `(H, W)` uint8 (`limiar` > 0 = fixo; 0 = adaptativo). Devolve uma CÓPIA da `Deteccao`.

        `alteracoes` sobrepõe campos de `ParamsDetetor` só nesta chamada (os de `self.params` ficam).
        """
        f = np.ascontiguousarray(frame, dtype=np.uint8)
        if f.ndim != 2:
            raise ValueError(f"esperava um frame (H, W), recebi {f.shape}")
        h, w = f.shape
        if alteracoes:
            p = self.bib.ParamsDetetor.from_buffer_copy(self.params)
            for k, v in alteracoes.items():
                if not hasattr(p, k):
                    raise AttributeError(f"ParamsDetetor não tem o campo {k!r}")
                setattr(p, k, v)
            ptr_p = ctypes.byref(p)
        else:
            ptr_p = self._p_params
        self.bib.lib.detetor_detetar(self.id, f.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), w, h, int(limiar),
                                     ptr_p, self._p_saida)
        return self.bib.Deteccao.from_buffer_copy(self.saida)

    def close(self) -> None:
        if getattr(self, "id", -1) >= 0:
            with contextlib.suppress(Exception):
                self.bib.lib.detetor_liberar(self.id)
            self.id = -1

    def __del__(self) -> None:
        self.close()


# =========================================================================================== seguidor
class SeguidorCpp:
    """Uma instância do `Seguidor` C++ (estimador do alvo + lei IBVS + máquina de estados) do pool estático da .so.

    `cfg` = campos de `ConfigSeguidor` a sobrepor aos de `config_padrao(largura, altura, fovy, modelo)`; `lei` = "v2" (a por
    omissão do firmware) ou "v1" (`config_versao1` aplicada antes do `cfg`); None = `LEI_OMISSAO`.
    Os buffers `att`, `cam` e `saida` são reutilizados (a `saida` é sobrescrita a cada passo — copie o que precisar).
    """

    def __init__(self, largura: int = 320, altura: int = 240, fovy_graus: float = 55.4, modelo: int = 2,
                 cfg: dict | None = None, bib: BibliotecaVisao | None = None, lei: str | None = None):
        self.bib = bib or biblioteca_padrao()
        self.lei = LEI_OMISSAO if lei is None else lei
        if self.lei not in LEIS:
            raise ValueError(f"lei tem de ser uma de {LEIS} (recebido {self.lei!r})")
        self.id = int(self.bib.lib.seguidor_criar())
        if self.id < 0:
            raise RuntimeError("pool de seguidores esgotado (16)")
        self.cfg = self.bib.ConfigSeguidor()
        self.bib.lib.seguidor_config_padrao(int(largura), int(altura), float(fovy_graus), int(modelo), self.cfg)
        if self.lei == "v1":
            self.bib.lib.seguidor_config_versao1(self.cfg)
        for k, v in (cfg or {}).items():
            if not hasattr(self.cfg, k):
                raise AttributeError(f"ConfigSeguidor não tem o campo {k!r}")
            setattr(self.cfg, k, v)
        self.att = self.bib.Atitude()
        self.cam = self.bib.Camera()
        self.saida = self.bib.SaidaSeguidor()
        self._p_att, self._p_cam, self._p_saida = (ctypes.byref(self.att), ctypes.byref(self.cam),
                                                   ctypes.byref(self.saida))
        self.iniciado = int(self.bib.lib.seguidor_iniciar(self.id, self.cfg)) == 1

    def reiniciar(self) -> None:
        self.bib.lib.seguidor_reiniciar(self.id)

    @property
    def estado(self) -> int:
        return int(self.bib.lib.seguidor_estado(self.id))

    def passo(self, t_us: int, roll: float, pitch: float, psi: float, camera: tuple | None = None,
              vx: float = 0.0, vy: float = 0.0, vz: float = 0.0):
        """Um passo. `camera` = (valido, u, v, raio, n, t_captura_us) ou None (repete a última). Devolve a `saida`."""
        a = self.att
        a.roll, a.pitch, a.psi, a.vx, a.vy, a.vz = roll, pitch, psi, vx, vy, vz
        if camera is not None:
            c = self.cam
            c.valido, c.u, c.v, c.raio, c.n, c.t = (int(camera[0]), float(camera[1]), float(camera[2]),
                                                    float(camera[3]), int(camera[4]), int(camera[5]) & 0xFFFFFFFF)
        self.bib.lib.seguidor_passo(self.id, int(t_us) & 0xFFFFFFFF, self._p_att, self._p_cam, self._p_saida)
        return self.saida

    def close(self) -> None:
        if getattr(self, "id", -1) >= 0:
            with contextlib.suppress(Exception):
                self.bib.lib.seguidor_liberar(self.id)
            self.id = -1

    def __del__(self) -> None:
        self.close()


# =========================================================================================== planta cinemática
# Planta SIMPLES só para provar o laço IBVS (NÃO é o simulador MuJoCo nem a cascata de voo — essa integração fica
# para depois): yaw de 2.ª ordem (integrador + lag τ_yaw da taxa), velocidades com lag τ_v e limite de aceleração,
# inclinação (roll/pitch) como consequência da aceleração, câmara pinhole à frente do corpo a `fps` com atraso fixo
# e ruído, atitude estimada com ruído. O alvo segue as leis do `env_real.definir_trajetoria_ponto`.
G = 9.81


def trajetoria_alvo(modo: str, vel: float = 0.5, raio: float = 1.5, inicio: tuple = (2.0, 0.0, 1.0)):
    """Posição do alvo no mundo, `f(t)`, pelas MESMAS leis do `env_real.definir_trajetoria_ponto` (parado, círculo,
    oito), partindo de `inicio` (À FRENTE do drone)."""
    ini = tuple(float(v) for v in inicio)
    if modo == "parado":
        return lambda t: ini
    if modo == "vertical":       # sobe e desce ±raio/3 m com a velocidade de pico `vel` (extra: exercita o v_z)
        amp = raio / 3.0
        w = float(vel) / max(amp, 1e-6)
        return lambda t: (ini[0], ini[1], ini[2] + amp * math.sin(w * t))
    w = float(vel) / max(float(raio), 0.1)
    if modo == "circulo":
        c = (ini[0] - raio, ini[1], ini[2])
        return lambda t: (c[0] + raio * math.cos(w * t), c[1] + raio * math.sin(w * t), c[2])
    if modo == "oito":
        return lambda t: (ini[0] + raio * math.sin(w * t), ini[1] + raio * math.sin(w * t) * math.cos(w * t), ini[2])
    raise ValueError(f"trajetória desconhecida: {modo!r}")


def _rot_zyx(roll: float, pitch: float, yaw: float):
    cr, sr, cp, sp, cy, sy = (math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch),
                              math.cos(yaw), math.sin(yaw))
    return ((cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
            (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
            (-sp, cp * sr, cp * cr))


def simular_laco(alvo, T: float = 30.0, largura: int = 320, altura: int = 240, fovy: float = 55.4, modelo: int = 2,
                 cfg: dict | None = None, atraso: float = 0.116, fps: float = 25.0, tau_yaw: float = 0.45,
                 tau_v: float = 0.5, tau_att: float = 0.12, a_max: float = 2.0, sigma_px: float = 0.3,
                 sigma_raio: float = 0.25, sigma_att: float = 0.0026, sigma_v: float = 0.05, yaw_bias: float = 0.0,
                 seed: int = 0, ocultar: tuple = (), t0_us: int = 0, drone0: tuple = (0.0, 0.0, 1.0, 0.0),
                 passo: float = 0.005, passo_ctrl: float = 0.01, r_alvo: float = 0.05,
                 bib: BibliotecaVisao | None = None, series: bool = True, yaw_script=None,
                 comando_yaw_inverte: bool = False, tau_ruido_att: float = 0.5, p_outlier: float = 0.0,
                 guardar_saidas: bool = False) -> dict:
    """Laço fechado cinemático: câmara → [atraso] → Seguidor C++ → (v, yaw_taxa) → planta → câmara.

    `alvo` = `f(t) → (x, y, z)` no mundo; `ocultar` = ((t_ini, t_fim), …) em que a câmara não vê o alvo (oclusão);
    `t0_us` = origem do relógio do MCU (use perto de 2³² para exercitar a volta); `p_outlier` = probabilidade de um frame
    trazer uma «deteção» FALSA (píxel e raio sorteados na imagem). O erro da atitude ESTIMADA é um
    processo de Gauss–Markov (σ = `sigma_att` = 0,15°, correlação `tau_ruido_att` = 0,5 s: o erro de um complementar
    com giroscópio integrado é lento, não branco) + 0,02° branco. `yaw_script` = `f(t) → ψ` (rad):
    ABRE o laço — o drone fica parado e roda como mandado (para avaliar só o ESTIMADOR sob rotação própria); a lei
    corre na mesma mas não age. O alvo conta como «no campo» se o disco inteiro cabe na imagem com 1 px de margem
    (o que o gate de borda do detetor exige) e tem ≥ 2 px de raio.

    Séries (por passo de controlo): erro de centragem na imagem (ângulo entre o eixo óptico e a linha de vista),
    erro de rumo/elevação reais (referencial do mundo, desrodado), distância, estado, comandos e — para o estimador —
    az/el reais e previstos AGORA e as duas referências «sem previsão»: `az_velho` (a última medida desrodada pela
    atitude da captura, sem extrapolar o alvo) e `az_cam_velho` (a última medida SEM desrodar: o bearing da câmara
    velho + o rumo atual).
    """
    rng = random.Random(seed)
    seg = SeguidorCpp(largura, altura, fovy, modelo, cfg, bib)
    if not seg.iniciado:
        raise ValueError("o seguidor recusou a Config")
    f, cx, cy = float(seg.cfg.f_px), float(seg.cfg.cx), float(seg.cfg.cy)
    d_est = float(seg.cfg.dist_alvo_m)
    x, y, z, psi = (float(v) for v in drone0)
    r = vx = vy = vz = roll = pitch = 0.0
    cmd = (0.0, 0.0, 0.0, 0.0)
    fila: list = []                      # (t_entrega, amostra, az_inercial_na_captura, az_camara)
    cam_atual = (0, 0.0, 0.0, 0.0, 0, int(t0_us))
    az_velho = az_cam_velho = None
    n_frame = 0
    prox_cap = 0.0
    prox_ctrl = 0.0
    nsteps = round(T / passo)
    chaves = ("t", "e_centro", "dist", "d_err", "no_campo", "estado", "yaw", "vx", "vz", "e_psi_real", "e_psi_est",
              "taxa_est", "taxa_real", "psi", "flags", "az_real", "az_pred", "el_real", "el_pred", "az_velho",
              "az_cam_velho", "raio_real", "raio_pred", "e_elev_real", "u_real", "v_real", "u_pred", "v_pred")
    S = {k: [] for k in chaves} if series else {}
    if series and guardar_saidas:
        S["saidas"] = []
    est_cont = [0, 0, 0, 0]
    ult_az = None
    psi_ant = psi
    rho_n = math.exp(-passo_ctrl / max(tau_ruido_att, 1e-6))
    ruido = [0.0, 0.0, 0.0]                      # erro lento da atitude estimada (roll, pitch, psi)
    for k in range(nsteps):
        t = k * passo
        if yaw_script is not None:
            psi = yaw_script(t)
            r = (psi - psi_ant) / passo if k else 0.0
            psi_ant = psi
        pt = alvo(t)
        rot = _rot_zyx(roll, pitch, psi)
        d_w = (pt[0] - x, pt[1] - y, pt[2] - z)
        pb = tuple(rot[0][i] * d_w[0] + rot[1][i] * d_w[1] + rot[2][i] * d_w[2] for i in range(3))   # Rᵀ·d
        dist = math.sqrt(sum(c * c for c in pb))
        # ---- câmara: captura a `fps`, entrega com atraso
        if t + 1e-9 >= prox_cap:
            prox_cap += 1.0 / fps
            n_frame += 1
            valido = 0
            u = v = rr = 0.0
            az_i = az_c = 0.0
            oculto = any(a <= t < b for a, b in ocultar)
            if not oculto and pb[0] > 0.05:
                uu = cx + f * (-pb[1] / pb[0])
                vv = cy + f * (-pb[2] / pb[0])
                r_px = f * r_alvo / math.sqrt(max(dist * dist - r_alvo * r_alvo, 1e-9))
                if (2.0 <= r_px <= 0.2 * altura and 1.0 + r_px <= uu <= largura - 2.0 - r_px
                        and 1.0 + r_px <= vv <= altura - 2.0 - r_px):
                    valido = 1
                    u, v, rr = uu + rng.gauss(0, sigma_px), vv + rng.gauss(0, sigma_px), r_px + rng.gauss(0, sigma_raio)
                    if p_outlier > 0.0 and rng.random() < p_outlier:        # deteção falsa (outro objeto brilhante)
                        u, v, rr = rng.uniform(10, largura - 10), rng.uniform(10, altura - 10), rng.uniform(3.0, 12.0)
                    # bearing medido: da câmara e desrodado (atitude VERDADEIRA da captura) — só para as referências
                    xn, yn = (u - cx) / f, (v - cy) / f
                    db = (1.0, -xn, -yn)
                    dw = tuple(sum(rot[i][j] * db[j] for j in range(3)) for i in range(3))
                    az_i = math.atan2(dw[1], dw[0])
                    az_c = math.atan2(db[1], db[0])
            fila.append((t + atraso, (valido, u, v, rr, n_frame, (t0_us + round(t * 1e6)) & 0xFFFFFFFF),
                         az_i, az_c))
        while fila and fila[0][0] <= t + 1e-9:
            _te, cam_atual, az_i, az_c = fila.pop(0)
            if cam_atual[0]:
                az_velho, az_cam_velho = az_i, az_c
        # ---- controlo a passo_ctrl
        if t + 1e-9 >= prox_ctrl:
            prox_ctrl += passo_ctrl
            t_us = (t0_us + round(t * 1e6)) & 0xFFFFFFFF
            for q in range(3):
                ruido[q] = rho_n * ruido[q] + math.sqrt(1.0 - rho_n * rho_n) * sigma_att * rng.gauss(0, 1)
            o = seg.passo(t_us, roll + ruido[0] + rng.gauss(0, 3.5e-4), pitch + ruido[1] + rng.gauss(0, 3.5e-4),
                          psi + ruido[2] + yaw_bias * t + rng.gauss(0, 3.5e-4), cam_atual,
                          vx + rng.gauss(0, sigma_v), vy + rng.gauss(0, sigma_v), vz + rng.gauss(0, sigma_v))
            if yaw_script is None:
                cmd = (o.vx, o.vy, o.vz, -o.yaw_taxa if comando_yaw_inverte else o.yaw_taxa)
            est_cont[o.estado] += 1
            if series:
                az_real = math.atan2(d_w[1], d_w[0])
                el_real = math.atan2(d_w[2], math.hypot(d_w[0], d_w[1]))
                e_ang = math.degrees(math.acos(max(-1.0, min(1.0, pb[0] / max(dist, 1e-9)))))
                in_fov = (pb[0] > 0.05 and 3.0 <= cx + f * (-pb[1] / pb[0]) <= largura - 3.0 and
                          3.0 <= cy + f * (-pb[2] / pb[0]) <= altura - 3.0)
                ep = (az_real - psi + math.pi) % (2 * math.pi) - math.pi
                S["t"].append(t); S["e_centro"].append(e_ang); S["dist"].append(dist)
                S["d_err"].append(dist - d_est); S["no_campo"].append(1 if in_fov else 0)
                S["estado"].append(o.estado); S["yaw"].append(o.yaw_taxa); S["vx"].append(o.vx); S["vz"].append(o.vz)
                S["e_psi_real"].append(ep); S["e_psi_est"].append(o.e_psi); S["taxa_est"].append(o.taxa_bearing)
                S["psi"].append(psi); S["flags"].append(o.flags)
                S["az_real"].append(az_real); S["az_pred"].append(o.az_pred if o.estado != 2 else float("nan"))
                S["el_real"].append(el_real); S["el_pred"].append(o.el_pred if o.estado != 2 else float("nan"))
                S["az_velho"].append(az_velho if az_velho is not None else float("nan"))
                S["az_cam_velho"].append((az_cam_velho + psi) if az_cam_velho is not None else float("nan"))
                S["raio_real"].append(f * r_alvo / math.sqrt(max(dist * dist - r_alvo * r_alvo, 1e-9)))
                S["raio_pred"].append(o.raio_pred if o.estado != 2 else float("nan"))
                S["e_elev_real"].append(el_real)
                S["u_real"].append(cx + f * (-pb[1] / pb[0]) if pb[0] > 1e-6 else float("nan"))
                S["v_real"].append(cy + f * (-pb[2] / pb[0]) if pb[0] > 1e-6 else float("nan"))
                S["u_pred"].append(o.u_pred); S["v_pred"].append(o.v_pred)
                if guardar_saidas:
                    S["saidas"].append(SaidaSeguidor_copia(seg.bib, o))
                if ult_az is not None:
                    dd = (az_real - ult_az + math.pi) % (2 * math.pi) - math.pi
                    S["taxa_real"].append(dd / passo_ctrl)
                else:
                    S["taxa_real"].append(0.0)
                ult_az = az_real
        # ---- planta
        if yaw_script is None:
            r += (cmd[3] - r) / tau_yaw * passo
            psi += r * passo
            a_cmd = []
            for v_i, c_i in ((vx, cmd[0]), (vy, cmd[1]), (vz, cmd[2])):
                a_cmd.append(max(-a_max, min(a_max, (c_i - v_i) / tau_v)))
            vx += a_cmd[0] * passo
            vy += a_cmd[1] * passo
            vz += a_cmd[2] * passo
            pitch += (math.atan2(a_cmd[0], G) - pitch) / tau_att * passo   # + = nariz para baixo (acelera para a frente)
            roll += (-math.atan2(a_cmd[1], G) - roll) / tau_att * passo
            cpsi, spsi = math.cos(psi), math.sin(psi)
            x += (cpsi * vx - spsi * vy) * passo
            y += (spsi * vx + cpsi * vy) * passo
            z += vz * passo
    seg.close()
    saida = {"estados": est_cont, "T": T}
    if series:
        saida["series"] = S
    return saida


def SaidaSeguidor_copia(bib, o):
    return bib.SaidaSeguidor.from_buffer_copy(o)


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def metricas_laco(res: dict, t_aquec: float = 4.0) -> dict:
    """RMS/máximo do erro de centragem (graus), de rumo, de distância (m), % do tempo com o alvo no campo, % em A_SEGUIR."""
    S = res["series"]
    idx = [i for i, t in enumerate(S["t"]) if t >= t_aquec]
    if not idx:
        raise ValueError("sem amostras depois do aquecimento")
    ec = [S["e_centro"][i] for i in idx]
    ep = [math.degrees(S["e_psi_real"][i]) for i in idx]
    de = [abs(S["d_err"][i]) for i in idx]
    n = len(idx)
    return {"rms_centro_graus": math.sqrt(sum(e * e for e in ec) / n), "max_centro_graus": max(ec),
            "rms_rumo_graus": math.sqrt(sum(e * e for e in ep) / n), "max_rumo_graus": max(abs(e) for e in ep),
            "erro_dist_medio_m": sum(de) / n, "erro_dist_max_m": max(de),
            "frac_campo": sum(S["no_campo"][i] for i in idx) / n,
            "frac_seguir": sum(1 for i in idx if S["estado"][i] == 0) / n,
            "yaw_max_rad_s": max(abs(S["yaw"][i]) for i in idx), "vx_max": max(abs(S["vx"][i]) for i in idx),
            "vz_max": max(abs(S["vz"][i]) for i in idx)}


def erro_previsao(res: dict, t_aquec: float = 3.0) -> dict:
    """Erro de previsão do estimador AGORA (graus): RMS/máx do azimute e da elevação previstos vs reais, e das
    referências sem previsão (`az_velho`: desrodada mas não extrapolada; `az_cam_velho`: nem desrodada)."""
    S = res["series"]
    def rms(seq):
        v = [e for e in seq if not math.isnan(e)]
        return (math.sqrt(sum(e * e for e in v) / len(v)) if v else float("nan")), (max(abs(e) for e in v) if v else float("nan"))
    idx = [i for i, t in enumerate(S["t"]) if t >= t_aquec]
    ea = [math.degrees(_wrap(S["az_pred"][i] - S["az_real"][i])) for i in idx if not math.isnan(S["az_pred"][i])]
    ee = [math.degrees(S["el_pred"][i] - S["el_real"][i]) for i in idx if not math.isnan(S["el_pred"][i])]
    ev = [math.degrees(_wrap(S["az_velho"][i] - S["az_real"][i])) for i in idx if not math.isnan(S["az_velho"][i])]
    ec = [math.degrees(_wrap(S["az_cam_velho"][i] - S["az_real"][i])) for i in idx
          if not math.isnan(S["az_cam_velho"][i])]
    # o que o controlador de yaw vê: o erro de RUMO previsto (azimute previsto − rumo estimado) vs o real — a parte
    # lenta do erro da atitude estimada cancela-se entre o instante da captura e o de agora
    ep = [math.degrees(_wrap(S["e_psi_est"][i] - S["e_psi_real"][i])) for i in idx
          if not math.isnan(S["az_pred"][i])]
    out = {}
    for nome, seq in (("az", ea), ("el", ee), ("az_velho", ev), ("az_cam_velho", ec), ("epsi", ep)):
        m, mx = rms(seq)
        out[f"rms_{nome}_graus"], out[f"max_{nome}_graus"] = m, mx
    out["n"] = len(ea)
    return out


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "compilar":
        so = compilar_visao()
        print(so)
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
