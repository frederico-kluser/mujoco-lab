"""experiments/09_drone_hover_rl/sitl_camera.py — a CÂMARA no laço do SITL: frames mono renderizados → detetor C++ → `Camera`.

O núcleo de firmware (`firmware/nucleo/`) vê o alvo pela struct `Camera{valido, u, v, raio, n, t}` que o detetor
(`firmware/nucleo/visao.hpp`, atividade C) entrega por frame. Aqui o frame é RENDERIZADO de verdade no MuJoCo (EGL; a cena
real do lab: a câmara `fpv` montada à frente do drone, a esfera-marcador mocap) e o detetor C++ corre sobre ele — nada de
projeção ideal:

    estado do simulador ──(mj_copyData + mj_forward, cópia privada)──▶ render QVGA RGB ──▶ luma BT.601 (mono 8 bit)
        ──▶ `Detetor::detetar` (C++) ──▶ Camera ──▶ [fila com a LATÊNCIA do caminho] ──▶ `Sensores::camera` do núcleo

CADÊNCIA e LATÊNCIA são do TEMPO DE SIMULAÇÃO (`data.time`), não do relógio de parede: um frame é capturado a cada 1/fps
(30 Hz por omissão) e só chega ao núcleo `latencia_s` depois (116 ms = pipeline Pi/JPEG do build ativo p50b;
≈ 21 ms = caminho DCMI do build `endurance_15pol_arduino`, `lab.camera_rpi.latencia_modelada`). `Camera.t` é o instante
da CAPTURA (µs): é por ele que o estimador do alvo (alvo.hpp) compensa o atraso com o histórico de atitude.

A esfera passa a BRANCA emissiva (câmara monocromática: o alvo distingue-se por brilho — o magenta do marcador dá luma
0,51 — como no `teste_visao.py`); é só a cor visual do marcador (corpo mocap, sem massa nem colisão): a física não muda.

Não é hardware: sem ruído de sensor, sem rolling shutter, sem desfoque (o render é instantâneo e nítido) — o detetor foi
provado à parte nesses defeitos (`teste_visao.py` §4). O custo do render (host) mede-se em `estatisticas()`.
"""
from __future__ import annotations

import collections
import contextlib
import math
import time

import numpy as np

LARGURA, ALTURA, FPS = 320, 240, 30.0
LATENCIA_PI_S = 0.116          # pipeline Pi (CSI + ISP + JPEG + rede): lab.camera_rpi.latencia_modelada ≈ 118 ms; o enunciado usa 116
LATENCIA_DCMI_S = 0.021        # caminho DCMI do Arduino (QVGA60: leitura 1 período + processamento + comando M7→M4)
RAIO_ALVO_M = 0.05             # RAIO_PONTO do lab/camera_rpi.py


def para_cinza(rgb: np.ndarray) -> np.ndarray:
    """RGB uint8 `(H, W, 3)` → cinzento uint8 por luma ITU-R BT.601 (a de `lab.camera_rpi.para_cinza`)."""
    return np.rint(rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114).astype(np.uint8)


class CameraSITL:
    """Câmara mono QVGA do drone no laço: renderiza, deteta (C++) e entrega ao núcleo com latência.

    `atualizar(env, cam)` chama-se a CADA passo de física (antes do `planear`): captura se já é hora, e escreve em `cam` (a
    struct `Sensores.camera` do núcleo) o último frame JÁ CHEGADO — só muda `cam.n` quando há frame novo.
    """

    def __init__(self, env, largura: int = LARGURA, altura: int = ALTURA, fps: float = FPS,
                 latencia_s: float = LATENCIA_PI_S, alvo_branco: bool = True, detetor=None, camera: str = "fpv"):
        import mujoco
        import sitl_visao
        if not getattr(env, "com_alvo", False):
            raise ValueError("a câmara do SITL precisa do ponto-alvo: construir o env com `com_alvo=True`")
        self.mujoco = mujoco
        self.model = env.model
        self.camera = camera
        self.cid = int(self.model.camera(camera).id)
        self.largura, self.altura = int(largura), int(altura)
        self.fps, self.latencia_s = float(fps), float(latencia_s)
        self.fovy = float(self.model.cam_fovy[self.cid])        # o do build (Pi Wide 67° · HM0360 55,4°)
        self.focal_px = 0.5 * self.altura / math.tan(math.radians(self.fovy) / 2.0)
        self._local = mujoco.MjData(self.model)                 # cópia privada do estado (o render não toca na simulação)
        self._renderer = mujoco.Renderer(self.model, height=self.altura, width=self.largura)
        self.detetor = detetor if detetor is not None else sitl_visao.DetetorCpp()
        self.detetor.params_padrao(self.largura, self.altura)
        self._cor_original = None
        if alvo_branco:
            self._cor_original = self._pintar_alvo(True)
        self.reiniciar()

    # ------------------------------------------------------------------ cena
    def _pintar_alvo(self, branco: bool):
        mid, gid = self.model.material("ponto_mat").id, self.model.geom("ponto_esfera").id
        antigo = (self.model.mat_rgba[mid].copy(), self.model.geom_rgba[gid].copy())
        if branco:
            self.model.mat_rgba[mid] = (1.0, 1.0, 1.0, 1.0)
            self.model.geom_rgba[gid] = (1.0, 1.0, 1.0, 1.0)
        elif self._cor_original is not None:
            self.model.mat_rgba[mid], self.model.geom_rgba[gid] = self._cor_original
        return antigo

    def reiniciar(self) -> None:
        self._prox = 0.0
        self._fila: collections.deque = collections.deque()
        self._n = 0
        self._ultimo = None
        self.n_frames = self.n_validos = 0
        self.ms_render: list[float] = []
        self.ms_detetor: list[float] = []
        self.registo: list[tuple] = []        # (t_captura_s, valido, u, v, raio) — só para análise

    # ------------------------------------------------------------------ captura e entrega
    def capturar(self, data) -> tuple:
        """Um frame agora: render → luma → detetor. Devolve `(valido, u, v, raio)` (convenção do índice)."""
        t0 = time.perf_counter()
        self.mujoco.mj_copyData(self._local, self.model, data)
        self.mujoco.mj_forward(self.model, self._local)          # xpos/cam_xpos do estado ATUAL (o mocap entra aqui)
        self._renderer.update_scene(self._local, camera=self.camera)
        rgb = self._renderer.render()
        t1 = time.perf_counter()
        d = self.detetor.detetar(para_cinza(rgb))
        t2 = time.perf_counter()
        self.ms_render.append(1000.0 * (t1 - t0))
        self.ms_detetor.append(1000.0 * (t2 - t1))
        return int(d.valido), float(d.u), float(d.v), float(d.raio_px)

    def atualizar(self, env, cam) -> None:
        t = float(env.data.time)
        if t + 1e-9 >= self._prox:                               # hora de capturar
            valido, u, v, raio = self.capturar(env.data)
            self._n += 1
            self.n_frames += 1
            self.n_validos += valido
            t_us = round(t * 1e6) & 0xFFFFFFFF
            self._fila.append((t + self.latencia_s, self._n, t_us, valido, u, v, raio))
            self.registo.append((t, valido, u, v, raio))
            self._prox += 1.0 / self.fps
        while self._fila and self._fila[0][0] <= t + 1e-9:       # chegou ao núcleo
            self._ultimo = self._fila.popleft()
        if self._ultimo is not None:
            _te, n, t_us, valido, u, v, raio = self._ultimo
            cam.valido, cam.n, cam.t = int(valido), int(n), int(t_us)
            cam.u, cam.v, cam.raio = (float(u), float(v), float(raio)) if valido else (0.0, 0.0, 0.0)

    # ------------------------------------------------------------------ relatório e limpeza
    def estatisticas(self) -> dict:
        """O que se MEDIU: frames capturados, fração com deteção válida, custo do render e do detetor no host."""
        def med(v):
            return float(np.median(v)) if v else float("nan")
        return {"frames": self.n_frames, "validos": self.n_validos,
                "frac_validos": self.n_validos / self.n_frames if self.n_frames else float("nan"),
                "render_ms_mediana": med(self.ms_render), "detetor_ms_mediana": med(self.ms_detetor),
                "largura": self.largura, "altura": self.altura, "fps": self.fps, "latencia_s": self.latencia_s,
                "fovy_graus": self.fovy, "focal_px": self.focal_px}

    def fechar(self) -> None:
        if self._cor_original is not None:
            with contextlib.suppress(Exception):
                self._pintar_alvo(False)
        with contextlib.suppress(Exception):
            self._renderer.close()
        if hasattr(self.detetor, "close"):
            with contextlib.suppress(Exception):
                self.detetor.close()
