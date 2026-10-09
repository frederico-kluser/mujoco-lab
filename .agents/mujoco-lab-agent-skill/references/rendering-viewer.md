# Renderização, vídeo e viewers do MuJoCo (EGL, GLFW, `mujoco.Renderer`, `mujoco.viewer`, Studio)

Imagens e vídeo sem janela, backends OpenGL, viewer interativo, Studio/Filament e `mjpython` — no Linux Wayland + NVIDIA deste laboratório (com nota macOS).

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: ficha `pesquisas/conhecimento/Q2.md`; `docs/upstream/mujoco/doc/{python.rst,programming/{visualization,ui,samples}.rst,skills/{rendering,studio}/SKILL.md}`; `docs/upstream/mujoco/python/mujoco/{viewer.py,rendering/classic/,egl/,glfw/,osmesa/,mjpython/}`; scripts `mjkit`, `render_video`, `view_model`, `env_check`; testes locais offscreen (nenhum viewer aberto).
> **Re-verificado em 2026-10-08** (§Backends, `MUJOCO_GL` no import): `.venv` (mujoco 3.15.0), um subprocesso por valor — variável ausente, `egl`, `osmesa`, inválida e `disable`.

## Quando ler este arquivo
- Gerar vídeo/GIF/tira de quadros ou imagens RGB/profundidade/segmentação **sem janela** (agente, CI, SSH), ou depurar erro de EGL/OSMesa/GLFW.
- Abrir janela (`launch`, `launch_passive`), entender Studio/Filament, os avisos `libdecor`/`0x502` do KDE Wayland ou o `mjpython` do macOS.
- Conferir o §3.2 do relatório do dono (macOS, `mjpython`, Homebrew).

Legenda: ✔ testado aqui · ⚠ armadilha · Δ doc = a documentação diverge do medido · «não verificado» = exigiria abrir janela (como verificar indicado). Os `skills/{rendering,studio}/SKILL.md` oficiais têm 4 erros verificados aqui (todos marcados Δ doc): não os copie sem testar.

## Decisão rápida
| Quero… | Use | Seção |
|---|---|---|
| vídeo/GIF/tira, dataset, CI, agente | `MUJOCO_GL=egl` + `mjkit.record` ou `render_video.py` | Vídeo |
| RGB / profundidade / segmentação | `mujoco.Renderer` com EGL | Renderer |
| inspecionar com mouse (pausar, passo, perturbar) | `scripts/view_model.py modelo.xml` (= `viewer.launch`) | Viewers |
| meu controlador com janela | `viewer.launch_passive` (`mjkit.run_viewer`) | Viewers |

## Backends OpenGL (`MUJOCO_GL`)
| Backend | `MUJOCO_GL` | Requisitos | Limitações | Neste laptop | Quando usar |
|---|---|---|---|---|---|
| **EGL** | `egl` | libEGL + driver com `EGL_EXT_platform_device`; **sem** display | contexto preso à thread; ordem dos dispositivos varia | ✔ NVIDIA RTX 4070, OpenGL 4.6.0 NVIDIA 610.57.04; ✔ idêntico sem `DISPLAY`/PRIME | **padrão do lab**: vídeo, dataset, CI, agente |
| GLFW | vazio, `glfw`, `glx` (alias) | libglfw do wheel `glfw` + servidor gráfico | cria janela GLFW **oculta** só para ter contexto; sem display falha | ✔ módulo carrega; ✔ `Renderer` roda em Wayland (janela oculta) com aviso `0x502`; ✔ sem display → `FatalError` | só p/ o mesmo contexto do viewer; **evite em agente/CI** |
| OSMesa | `osmesa` | `libOSMesa` + PyOpenGL | rasterização por software (CPU) | ✘ ausente: `import mujoco` quebra (`AttributeError … 'glGetError'`); `pacman -Ss osmesa` vazio | CPU: EGL device 3 (llvmpipe ✔: ~13 ms/quadro a 320×240, ~25 ms a 1280×720; a NVIDIA faz 0,4 / 1,3 ms) |
| Filament | — (não é valor) | `mujoco.rendering.filament`, Studio; build C `MUJOCO_USE_FILAMENT=1` | **experimental**; o `Renderer` do wheel é *classic* (`mjr_getRendererInfo` → `renderer='classic'`, `backend='opengl'` ✔) | ✔ Vulkan offscreen NVIDIA sem `DISPLAY`; OpenGL exige X | PBR/sombras suaves; fora do pipeline padrão |
| desligado | `disable`, `0`, `off`, `false` | — | sem contexto GL: `Renderer` inutilizável | ✔ `import` ok | só física |

macOS: padrão `cgl` (contexto sem janela; offscreen fora da main thread desde a 2.3.4; cai em `glfw` se falhar). `mujoco.GLContext(w, h)` (+ `make_current()`, `free()`) é o contexto manual p/ `mjr_*` (`python.rst`; o EGL ignora `w`/`h`).

| Variável | Efeito |
|---|---|
| `MUJOCO_GL` | lida **no import do módulo** (`mujoco/rendering/classic/gl_context.py:24`, trazido por `mujoco/__init__.py:76`) — não no uso do `Renderer`; valor inválido → `RuntimeError: invalid value for environment variable MUJOCO_GL: x` ✔; defini-la **depois** do `import mujoco` não muda nada ✔ |
| `PYOPENGL_PLATFORM` | vazio ou igual ao backend (`egl`); `mujoco.egl` define `egl` se vazio. ⚠ Conflito (ex.: `glx` com `egl`) → `ImportError` **engolido** por `mujoco/__init__.py`: o import passa e **`mujoco.Renderer`/`GLContext` somem** ✔ |
| `MUJOCO_EGL_DEVICE_ID` | índice base 0 em `eglQueryDevicesEXT()` (≠ índice CUDA); fora de `0..N-1` → `RuntimeError`; texto → `ValueError` ✔. Sem ela: 1º dispositivo que inicializa |
| `__EGL_VENDOR_LIBRARY_FILENAMES` | filtra o GLVND: `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` → 1 dispositivo (NVIDIA); `50_mesa.json` → 3 (1º = iGPU Intel) ✔. Forma robusta de fixar a GPU |
| `PYGLFW_LIBRARY_VARIANT`, `PYGLFW_LIBRARY` | `wayland`/`x11` escolhe a libglfw do wheel (padrão `wayland` se `XDG_SESSION_TYPE=wayland`) ✔; `PYGLFW_LIBRARY` = caminho de outra libglfw (ficha F23) |
| PRIME (`__NV_PRIME_RENDER_OFFLOAD`, `__GLX_VENDOR_LIBRARY_NAME`, `__VK_LAYER_NV_optimus`) | já exportadas nesta sessão; **irrelevantes ao EGL por dispositivo** ✔ (render idêntico sem elas) |

⚠ **`MUJOCO_GL` vale mesmo sem render nenhum** — não é "irrelevante em treino headless": como a leitura é no import, um valor inválido mata o `import mujoco` antes de qualquer física. Medido em 2026-10-08 (`.venv`, mujoco 3.15.0): `MUJOCO_GL=osmesa` → o import falha em `OpenGL/raw/GL/_errors.py:4` (`AttributeError: 'NoneType' object has no attribute 'glGetError'`; falta `libOSMesa`); `MUJOCO_GL=lixo` → `RuntimeError`; **sem a variável** (padrão `glfw`), com `egl` ou com `disable` → import OK (o `glfw` só falha ao **criar** contexto, não ao importar). Regra para treino/CI/agente: `MUJOCO_GL=egl` ou não tocar na variável — nunca `osmesa` nesta máquina.

Dispositivos EGL aqui (✔ `eglQueryDevicesEXT`, 4): **0** NVIDIA GeForce RTX 4070 Laptop GPU · **1** falha (`MESA-EGL: warning: egl: failed to create dri2 screen` → `ImportError: Cannot initialize a EGL device display`) · **2** Mesa Intel (RPL-S, iGPU) · **3** llvmpipe (CPU). A ordem varia entre máquinas: confira `GL_RENDERER`. O código `mujoco/egl` do 3.15 não usa `CUDA_VISIBLE_DEVICES` (✔ valor vazio não muda o dispositivo); ordem diferente da CUDA em multi-GPU: relato na issue #3245 (3.4.0).

```python
import os
os.environ.setdefault("MUJOCO_GL", "egl")          # ANTES de importar mujoco (e de qualquer lib que importe PyOpenGL)
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")  # robustez: em sessão X11, PyOpenGL importado antes prende o GLX ✔
import mujoco
from OpenGL import GL
m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><light pos="0 0 3"/><geom type="sphere" size=".2" rgba="1 0 0 1"/></worldbody></mujoco>')
d = mujoco.MjData(m); mujoco.mj_forward(m, d)
with mujoco.Renderer(m, 240, 320) as r:            # `with` libera o contexto GL mesmo com exceção
    r.update_scene(d); img = r.render()
    print(img.shape, img.dtype, GL.glGetString(GL.GL_RENDERER).decode())   # (240, 320, 3) uint8 NVIDIA GeForce RTX 4070 Laptop GPU/PCIe/SSE2
```
Diagnóstico rápido: `.venv/bin/python .agents/mujoco-lab-agent-skill/scripts/env_check.py` (EGL em subprocesso; rode da raiz). `--gl all` cria janela GLFW oculta — evite em agente. Δ: a dica de `env_check` p/ OSMesa (`pacman -S mesa`) não serve: o `mesa` 26.2.1 já instalado não traz `libOSMesa`.

## `mujoco.Renderer`
| Membro | Detalhe |
|---|---|
| `Renderer(model, height=240, width=320, max_geom=10000, font_scale=mjFONTSCALE_150)` | `ValueError` se `width`/`height` > `<visual><global offwidth offheight>` (padrão **640×480**); cena maior que `max_geom` é truncada com `WARNING: Pre-allocated visual geom buffer is full` ✔ (contatos desenhados contam: 1 contato = +2 geoms ✔) |
| `update_scene(data, camera=-1, scene_option=None)` | `camera`: id, nome ou `MjvCamera`; usa `data` **como está** — chame `mj_forward`/`mj_step` antes ✔ (sem isso a imagem não se move) |
| `render(*, out=None)` | RGB `(H,W,3)` uint8 · profundidade `(H,W)` float32 · segmentação `(H,W,2)` int32 |
| `enable_/disable_depth_rendering()`, `enable_/disable_segmentation_rendering()` | exclusivos entre si; o modo vale até desabilitar |
| `scene`, `model`, `height`, `width`; `close()` / `with` | `close()` idempotente; `render()` depois → `RuntimeError: render cannot be called after close.` ✔ |

```python
import os; os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco, numpy as np
XML = """<mujoco><visual><global offwidth="1280" offheight="720"/></visual>
<worldbody><light pos="0 0 3" dir="0 0 -1"/>
  <geom name="chao" type="plane" size="3 3 .1" rgba=".7 .7 .7 1"/>
  <body name="bola" pos="0 0 .5"><freejoint/><geom name="g_bola" type="sphere" size=".1" rgba="1 0 0 1"/></body>
  <camera name="topo" pos="0 0 2"/></worldbody></mujoco>"""   # <camera> sem rotação olha para −Z, ou seja, para baixo
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m); mujoco.mj_forward(m, d)
with mujoco.Renderer(m, height=240, width=320) as r:
    r.update_scene(d, camera="topo"); rgb = r.render()                                      # (240,320,3) uint8
    r.enable_depth_rendering(); r.update_scene(d, camera="topo"); depth = r.render()        # (240,320) float32, metros
    r.enable_segmentation_rendering(); r.update_scene(d, camera="topo"); seg = r.render()   # (240,320,2) int32: [objid, objtype]
    r.disable_segmentation_rendering()                                                      # volta ao RGB
bola = (seg[..., 1] == mujoco.mjtObj.mjOBJ_GEOM) & (seg[..., 0] == m.geom("g_bola").id)     # máscara por nome
print(rgb.shape, depth.shape, seg.shape, "| prof. no centro", depth[120, 160].round(3), "m; canto", depth[0, 0], "m | px da bola", int(bola.sum()))
```
- **Profundidade** ✔: metros ao longo do eixo óptico (*z-depth*, não distância euclidiana: plano perpendicular → constante 2.0 m); pixel sem geometria = `vis.map.zfar × stat.extent` (35.0 = 50 × 0,7) → mascare `depth >= 0.999*zfar` antes de estatísticas.
- **Segmentação** ✔: `[objid, objtype]` por pixel; fundo `(-1,-1)`; `objtype == mjOBJ_GEOM (5)`; sem antialiasing (changelog 2.2.0).
- **Buffer** ✔: `render()` devolve array **novo** a cada chamada (`np.shares_memory` falso): guardar quadros em lista **não** exige `.copy()` — Δ doc: o `skills/rendering/SKILL.md` diz que o buffer é reutilizado. Só com `out=buf` o mesmo buffer volta (aliasing) → `.copy()`. `out` = `(H,W,3)` uint8 ou `(H,W)` float32 (Δ doc: a docstring diz `(width,height)`); em segmentação `out=` é ignorado.
- ⚠ **Thread** ✔: o contexto GL é da thread que criou o `Renderer`; criar na principal e renderizar em outra → `EGLError … EGL_BAD_ACCESS … eglMakeCurrent`; criar+usar+fechar na mesma thread funciona. Vários `Renderer` vivos (tamanhos diferentes) funcionam ✔. Crie **um** fora do loop (aloca framebuffers).
- **Tempo** ✔ (cena trivial, `update_scene`+`render`): ~0,4 ms (320×240), ~1,4 ms (640×480 e 1280×720); o custo real é PIL/GIF/encode.
- **Framebuffer** ✔: ajuste no XML `<visual><global offwidth="1280" offheight="720"/></visual>`, em `MjSpec` (`spec.visual.global_.offwidth`) ou em tempo de execução **antes** de criar o `Renderer` (`model.vis.global_.offwidth = 1920`). `<visual>` repetido é **mesclado** por atributo (2 blocos mantêm `offwidth`) — Δ doc: o `SKILL.md` oficial diz que o último "reseta"; `<global>` duas vezes no mesmo bloco → `XML Error: Schema violation: unique element 'global' found 2 times`. `<quality offsamples>` (padrão 4; `0` desliga o MSAA offscreen).

| Câmera | Como | Fato ✔ |
|---|---|---|
| fixa do modelo | `camera="frontal"` ou índice | nome inexistente → `ValueError: The camera "x" does not exist.`; id fora de `[-1, ncam)` → `ValueError` |
| livre padrão | `camera=-1` | `mjv_defaultFreeCamera`: lookat = `stat.center`, distância = 1,5 × `stat.extent`, azimute/elevação de `<visual><global>` (90/−45) |
| livre própria | `MjvCamera()` com `lookat`, `distance`, `azimuth`, `elevation` | padrão: FREE, distance 2.0, azimuth 90, elevation −45, lookat 0 |
| tracking | `cam.type = mjCAMERA_TRACKING; cam.trackbodyid = m.body("x").id` | lookat := centro de massa da subárvore; centra já no 1º `update_scene` (sem suavização perceptível) e grava em `cam.lookat` |
| no MJCF | `<camera mode="trackcom">` (`track`, `targetbody`, `targetbodycom`) | `templates/car/model.xml`: `seguir` (`render_video.py --camera seguir`); `targetbody` aponta p/ `target=` |
| orientação | a câmera olha para **−Z local** (+X direita, +Y cima) | sem `quat` olha para baixo; Δ doc: `quat=[0.707,0.707,0,0]` "para baixo" do `rendering/SKILL.md` olha para **+Y** (horizontal) |

```python
import os; os.environ.setdefault("MUJOCO_GL", "egl")
import mujoco
XML = """<mujoco><worldbody><light pos="0 0 3" dir="0 0 -1"/>
  <geom name="chao" type="plane" size="9 9 .1" rgba=".7 .7 .7 1"/>
  <body name="bola" pos="2 0 .5"><freejoint/><geom type="sphere" size=".15" rgba="1 0 0 1"/></body>
  <geom name="aux" group="3" type="capsule" fromto="-.5 0 .1 -.5 0 .6" size=".05" rgba="0 1 0 1"/>
  <camera name="mira" pos="0 -2 1" mode="targetbody" target="bola"/></worldbody></mujoco>"""
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m); mujoco.mj_forward(m, d)
free = mujoco.MjvCamera(); free.type = mujoco.mjtCamera.mjCAMERA_FREE              # livre: você define tudo
free.lookat[:] = [2, 0, .5]; free.distance, free.azimuth, free.elevation = 2.0, 90, -20
track = mujoco.MjvCamera(); track.type = mujoco.mjtCamera.mjCAMERA_TRACKING        # segue o centro de massa do corpo
track.trackbodyid = m.body("bola").id; track.distance, track.azimuth, track.elevation = 2.0, 90, -20
opt = mujoco.MjvOption(); opt.geomgroup[3] = 1                                       # grupo 3 (oculto por padrão: [1 1 1 0 0 0])
opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True; opt.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] = True
with mujoco.Renderer(m, 240, 320) as r:
    for nome, cam in (("fixa (MJCF)", "mira"), ("livre", free), ("tracking", track)):
        r.update_scene(d, camera=cam, scene_option=opt); print(f"{nome:12s}", r.render().shape)
```
| Opção (`MjvOption`, passada em `scene_option=`) | Padrão ✔ | Efeito |
|---|---|---|
| `geomgroup[0..5]` (idem os outros 6 arrays `*group`) | `[1 1 1 0 0 0]` | grupos 3–5 invisíveis até ligar (✔ geom `group="3"` só aparece com `geomgroup[3]=1`) |
| `flags[mjtVisFlag.mjVIS_CONTACTPOINT / _CONTACTFORCE]` | off | pontos/forças de contato; tamanho em `<visual><scale contactwidth contactheight forcewidth>`, `<map force>` |
| `flags[mjVIS_TRANSPARENT]`, `_COM`, `_JOINT`, `_INERTIA`, `_CONVEXHULL`… | off (únicas ligadas por padrão: TEXTURE, TENDON, RANGEFINDER, PERTOBJ, STATIC, SKIN, FLEXEDGE, FLEXSKIN) | transparência/decorações; ✔ TRANSPARENT: px vermelhos 1021→656 |
| `frame = mjtFrame.mjFRAME_BODY/GEOM/SITE/WORLD`, `label = mjtLabel.mjLABEL_BODY…` | NONE | eixos e rótulos de texto no quadro ✔ |
| `renderer.scene.flags[mjtRndFlag.mjRND_WIREFRAME / _SHADOW / _REFLECTION / _SKYBOX / _FOG / _HAZE]` | ligadas: SHADOW, REFLECTION, SKYBOX, HAZE, CULL_FACE | flags de **cena** (≠ `MjvOption`): persistem entre quadros ✔; SHADOW/REFLECTION custam passes extras (`visualization.rst`) |

## Vídeo, GIF e tira de quadros
`mjkit.record` simula `duration` segundos (tempo simulado), chama `controller(model, data)` antes de cada `mj_step` e grava (código em `scripts/mjkit.py`; cópia em `lab/mjkit.py`; também `contact_sheet`, `plot`, `run_viewer`). Sem `mp4`/`gif`/`sheet` **não cria Renderer** (só simula).

```python
from lab import mjkit                 # raiz do projeto no sys.path (idioma `_RAIZ` dos templates); define MUJOCO_GL=egl antes do mujoco
model, data = mjkit.load("models/triangulo_invertido.xml")
res = mjkit.record(model, data, duration=3, fps=60, slowmo=0.5, width=640, height=360,
                   camera="frontal", contacts=True, mp4="out/queda.mp4", gif="out/queda.gif",
                   sheet="out/queda_sheet.png", sheet_times=[0, 0.4, 0.5, 0.6, 0.9, 1.5, 2.99],   # < duration: ver Armadilhas
                   probes={"z": lambda m, d: d.xipos[1, 2]}, hud=lambda m, d: [f"t = {d.time:4.2f} s", f"contatos: {d.ncon}"])
print(res["frames"], "quadros;", round(res["wall_s"], 1), "s; z final =", round(float(res["log"]["z"][-1]), 3), "m")   # 361 quadros; wall_s varia com a carga (3–11 s medidos); 0.115 m
```
```python
from lab import mjkit
model, data = mjkit.load(".agents/mujoco-lab-agent-skill/assets/templates/car/model.xml")
ctrl = mjkit.Ctrl(model)                                  # escreve em data.ctrl por NOME (seguro p/ atuadores multi-entrada)
def controlador(m, d):                                    # chamado ANTES de cada mj_step
    ctrl.set(d, "tr_e", 1.0); ctrl.set(d, "tr_d", 1.0)
res = mjkit.record(model, data, controlador, duration=3, track="carro", width=640, height=360, mp4="out/carro.mp4",
                   probes={"x": lambda m, d: d.body("carro").xpos[0]})        # track = MjvCamera TRACKING num corpo
print(res["frames"], "quadros; x final =", round(float(res["log"]["x"][-1]), 1), "m")   # 181 quadros; 13.6 m
```
| Parâmetro de `record` | Padrão e efeito |
|---|---|
| `duration`, `fps`, `slowmo` | 4.0 · 60 · 1.0; um quadro a cada `slowmo/fps` s simulados (0.5 = câmera lenta, 2× quadros) |
| `camera`, `track` | `None` = câmera livre (-1); nome/id de `<camera>`. `track="corpo"`: TRACKING (dist 2.5, az 120, el −20) e **vence** `camera` |
| `width`, `height` | 1280×720; precisa caber em `offwidth/offheight` do modelo (senão `ValueError`; corrija com `model.vis.global_.offwidth = …`) ✔ |
| `mp4`, `gif`, `sheet` | mp4: libx264, yuv420p, `+faststart`, `macro_block_size=2` · gif: `gif_width=480`, `gif_fps=15`, 64 cores · sheet: grade de 4 colunas; `sheet_times` padrão = 8 instantes de 0 a `duration` |
| `contacts`, `hud`, `probes`, `on_step` | `False` (liga `CONTACTPOINT`+`CONTACTFORCE`); `hud(m,d)->list[str]` (texto via PIL); `{nome: f(m,d)}` amostrado a cada passo; gancho por passo |
| retorno | `{"log": {"t","ncon","pe","ke", *probes}, "frames": n, "wall_s": s}` |

CLI sem escrever código — `render_video.py` roda **dinâmica passiva** (+ controles constantes `--ctrl nome=valor,…` via `Ctrl`):
```bash
S=.agents/mujoco-lab-agent-skill/scripts/render_video.py; T=.agents/mujoco-lab-agent-skill/assets/templates
python $S models/triangulo_invertido.xml --duration 3 --slowmo 0.5 --width 640 --height 360 --contacts --gif --sheet --out out/queda
python $S $T/car/model.xml --ctrl "tr_e=1,tr_d=1" --camera seguir --duration 3 --width 640 --height 360 --out out/carro
python $S $T/arm/model.xml --qpos "0 0.3 -0.5" --ctrl "a_ombro=0.5,a_cotovelo=-0.8" --camera frontal --duration 2 --width 640 --height 360 --out out/braco
python $S $T/car/model.xml --ctrl "tr_e=1,tr_d=1" --track carro --no-mp4 --gif --duration 2 --width 640 --height 360 --out out/carro_track
```
Flags: `--duration --fps --slowmo --width --height --camera --track --keyframe --qpos "nq valores" --ctrl --contacts --no-mp4 --gif --sheet --out prefixo` (mp4 por padrão; `<out>_sheet.png`). ✔ 361 quadros (640×360, sim+render+encode) em 3–11 s conforme a carga da máquina. Para controle real (PID, trajetória) escreva um `run.py` com `mjkit.record` (`assets/templates/*/run.py`, `experiments/01_triangulo_invertido/run.py`: pipeline completo com `--contatos`, `--slowmo`, `--saida`). Sem `mjkit`: `imageio.get_writer(...)` + `Renderer`:
```python
import os; os.environ.setdefault("MUJOCO_GL", "egl")
import imageio.v2 as imageio, mujoco
m = mujoco.MjModel.from_xml_path("models/triangulo_invertido.xml"); d = mujoco.MjData(m)
fps, n = 30, 0
with mujoco.Renderer(m, 360, 640) as r, imageio.get_writer("out/min.mp4", fps=fps, codec="libx264", pixelformat="yuv420p", macro_block_size=2) as w:
    while d.time < 2.0:
        mujoco.mj_step(m, d)
        if d.time >= n / fps:                          # 1 quadro a cada 1/fps s de tempo SIMULADO
            r.update_scene(d, camera="frontal"); w.append_data(r.render()); n += 1
print(n, "quadros")                                    # 61
```

## Viewers (`mujoco.viewer`)
O viewer é o `simulate` (GLFW + OpenGL *classic* + UI nativa `mjui`, `programming/ui.rst`) empacotado em Python; a UI Dear ImGui é do Studio. Não usa `MUJOCO_GL` (o contexto vem da libglfw direto). **Nenhum viewer foi aberto**: API validada por leitura de `viewer.py`, `inspect` e `python -m mujoco.viewer --help` (só `--mjcf`).

| Entrada | Bloqueia? | Quem avança a física | Notas |
|---|---|---|---|
| `viewer.launch(model=None, data=None, *, loader=None, show_left_ui=True, show_right_ui=True)` | sim | thread do viewer | UI completa (pausa, passo, perturbação, sliders); indicado p/ plugins e callbacks de física (`mjcb_*`); `data` é modificado; sem `model` abre vazio (arrastar e soltar) |
| `viewer.launch_from_path(path)` / `python -m mujoco.viewer [--mjcf=m.xml]` | sim | thread do viewer | mesmo modo; `view_model.py` é o atalho do lab |
| `viewer.launch_passive(model, data, *, key_callback=None, show_left_ui=True, show_right_ui=True) -> Handle` | não | **seu loop** | chama `mj_forward` e abre; Linux: thread daemon + espera o modelo carregar; macOS: só com `mjpython`, senão `RuntimeError` |

`Handle` (`dir()` ✔): `m`, `d`, `cam`, `opt`, `perturb`, `user_scn`, `viewport`, `lock()`, `sync(state_only=False)`, `is_running()`, `close()`, `update_hfield/mesh/texture(id)`, `set_/clear_figures/texts/images`; usa-se como `with`. Δ doc: `python.rst` fala em `pert`, mas o atributo é **`perturb`**; `launch_repl` foi removida na 2.3.4.
- `sync()` é o único ponto em que o viewer lê/escreve `m`/`d` (traz perturbações, sliders e flags da GUI); sem ele a janela não atualiza. `sync(state_only=True)` copia só o estado de integração + `mj_forward` (mais rápido; **não** vê mudanças no `MjModel`).
- ⚠ `lock()`: obrigatório para `cam`/`opt`/`perturb`; o texto da doc também lista `m`/`d`, mas diz que o viewer só os toca dentro de `sync` (o exemplo oficial chama `mj_step` sem lock). Regra segura do lab: `with v.lock():` em volta de step + edições. `is_running()`/`close()` dispensam lock. Geoms próprios: `mjv_initGeom(v.user_scn.geoms[i], …)`, `user_scn.ngeom = n`, entram no próximo `sync()`.
- `key_callback(keycode: int)` recebe o código GLFW (`chr(k)` p/ letras maiúsculas). As 26 letras já são atalhos de flags do viewer (`programming/samples.rst`: R = Reflection, P = Contact Split…): colisão provável com `R`/`P` de `mjkit.run_viewer` — «não verificado» (exige janela). Atalhos de passo/pausa não agem no modo passivo.

```python
import time, mujoco, mujoco.viewer
m = mujoco.MjModel.from_xml_path("models/triangulo_invertido.xml"); d = mujoco.MjData(m)
with mujoco.viewer.launch_passive(m, d) as v:             # macOS: mjpython script.py
    while v.is_running():
        t0 = time.perf_counter()
        with v.lock():                                     # protege step + edições de opt/cam/perturb
            mujoco.mj_step(m, d)
            v.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = int(d.time % 2)
        v.sync()                                           # sem sync() a janela não atualiza (e entradas da GUI não chegam)
        time.sleep(max(0.0, m.opt.timestep - (time.perf_counter() - t0)))
```
Trecho acima: sintaxe e nomes de API conferidos; **execução com janela não feita por mim**. Implementações prontas (com `close_after`/`--fechar-apos` p/ teste automático): `mjkit.run_viewer(model, data, controlador, slowmo=1.0, close_after=None)`, `view_model.py --passivo`, `experiments/01_triangulo_invertido/view.py`. ⚠ Sem display (SSH/CI) ✔ o viewer **encerra o processo**: `GLFWError … X11: The DISPLAY environment variable is missing` + `ERROR: could not initialize GLFW`, exit 1 (não trava, não há exceção capturável) → headless = Renderer EGL. Atalhos úteis (`samples.rst`): Espaço/Backspace/setas, `[` `]` trocam câmera do modelo, Esc = câmera livre, `0`–`5` grupos de geom, `C`/`F` contato, `T` transparente, `Ctrl+P` screenshot, F1 ajuda.

**macOS e `mjpython`**: `launch_passive` exige `mjpython script.py` (substituto de `python`; `mjpython -m IPython`), introduzido na 2.3.3. É um trampolim (`mjpython/mjpython.py`): o interpretador roda **numa thread secundária** e a thread principal real fica livre para o Cocoa; o viewer delega o render loop a ela (`_MJPYTHON.launch_on_ui_thread`). `launch`/`python -m mujoco.viewer` não precisam. Não existe no wheel Linux (`which mjpython` → vazio ✔).

## Studio e Filament (experimental)
| Item | Fato |
|---|---|
| O que é | `mujoco.experimental.studio`: sucessor do `simulate` — Dear ImGui + ImPlot, render **Filament** (OpenGL/Vulkan/WebGL), plugins C++/Python, Web Viewer (NetImgui/WASM). Fonte: `skills/studio/SKILL.md`, ficha (F36) |
| Launchers | `launch_web` (recomendado: sem dependência gráfica nativa), `launch_native`, `launch_passive` (escolhe por `config.gfx`); cada um com `run(...)` bloqueante e `launch(...)` → `with … as h: while h.is_running(): model, data = h.sync(model, data)` |
| App | `python -m mujoco.experimental.studio.viewer --model=m.xml [--gfx=…] [--port=N] [--width] [--height]` — comando inferido do código, **não executado** (abre janela/servidor); `--gfx` ∈ `opengl opengl_headless opengl_software vulkan vulkan_software web webgl`; sem `--gfx` = janela nativa. `--gfx=web`: uma porta HTTP (≥ 8080) com bind em `'::'` (todas as interfaces) — ⚠ expor/tunelar a porta expõe o viewer inteiro |
| Wayland | README oficial (main): «does not yet work using Wayland on Linux, use X11 instead»; Filament OpenGL é GLX: sem `DISPLAY` → `Failed to open X display. (exiting).` ✔ exit 1. `SDL_VIDEODRIVER=x11` seria o contorno (inferência, não testada); alternativa: `--gfx=web` |
| Filament offscreen | ✔ `mujoco.experimental.studio.renderer.Renderer('vulkan')`: `Init(model)`, `Render(model, data, None, None, None, w, h)` → bytes RGB, na NVIDIA **sem** `DISPLAY`; `opengl*` exigem X. Δ doc: `classic`/`classic_headless` do `SKILL.md` do Studio → `ERROR: Unsupported graphics mode` ✔ |
| Status | `mujoco.Renderer`/`mjr_*` do wheel = *classic*; Filament só substitui `mjr_*` em builds C com `MUJOCO_USE_FILAMENT=1`; `mujoco.rendering.filament` (sobre `_render_filament`/mjrf) é baixo nível ✔ importa. Studio nativo não abre no macOS (NSWindow fora da main thread, issue #3579: mensagem + exit 1). **Para vídeo, fique no EGL classic** |

## Wayland, XWayland e NVIDIA neste laptop
- **Variante do GLFW** ✔ (sem `glfw.init()`): com `XDG_SESSION_TYPE=wayland` o pyGLFW carrega `glfw/wayland/libglfw.so` (`3.4.0 Wayland Null EGL OSMesa shared`, X11 = não suportado); o viewer repassa esse handle ao `_simulate` (`set_glfw_dlhandle`, `viewer.py`) → janela **Wayland nativa** (inferido; janela não aberta). XWayland só com `PYGLFW_LIBRARY_VARIANT=x11` (`3.4.0 X11 GLX …`; precisa de `DISPLAY=:0`). Δ doc: os docstrings de `view_model.py`/`mjkit.run_viewer` ("abre via XWayland") estão desatualizados.
- Qual GPU renderiza a janela (iGPU × NVIDIA) não foi testado. `eglinfo -B` (plataforma Wayland) lista NVIDIA com perfil de compatibilidade 4.6 — indício, não prova. Verificar: `nvidia-smi` com o viewer aberto (o processo Python aparece em *Processes*). `WARNING`/`ERROR` do MuJoCo vão ao stderr **e** a `MUJOCO_LOG.TXT` no cwd ✔ (rode fora da raiz).

| Aviso na abertura | Origem | Veredito |
|---|---|---|
| `Failed to load plugin 'libdecor-gtk.so'` | libdecor (decorações do GLFW-Wayland; plugins em `/usr/lib/libdecor/plugins-1/`: `cairo`, `gtk`; `LIBDECOR_PLUGIN_DIR`) ✔ string no `libdecor-0.so` | benigno (relato do lab; não reproduzido: sem janela) |
| `WARNING: OpenGL error 0x502 in or before mjr_makeContext` | `mjr_makeContext` (string em `libmujoco.so.3.15.0` ✔); ✔ reproduzido com `Renderer` sobre GLFW-Wayland (janela oculta): conclui sem exceção e devolve pixels não nulos (média 39, máx 255; não inspecionada). **Nunca** apareceu no caminho EGL | benigno (GL_INVALID_OPERATION pendente "em ou antes de" criar o contexto) |
| `GLFWError: (65548) … Wayland: The platform does not provide the window position` | Wayland não expõe posição de janela (`GLFW_FEATURE_UNAVAILABLE`; issue #2393) | benigno |

Janela não abre → (1) `echo $XDG_SESSION_TYPE $WAYLAND_DISPLAY $DISPLAY`; (2) `python -c "import glfw; print(glfw.get_version_string())"` mostra a variante; (3) tente `PYGLFW_LIBRARY_VARIANT=x11` (XWayland); (4) `X11: The DISPLAY environment variable is missing` / `could not initialize GLFW` = sem display → use EGL (§Backends); (5) sem janela mas com interatividade: Studio `--gfx=web`.

Aprofundar: `docs_search.py --attr visual/global.offwidth` · `--attr camera.mode` · `--type mjtVisFlag` · `--api mjv_defaultFreeCamera`; `doc/programming/visualization.rst` (Cameras, Buffers, Filament), `doc/python.rst` (Interactive viewer, Rendering), `doc/programming/samples.rst` (atalhos; C: `record`, `render` — fora do wheel), `changelog.rst` (2.3.3, 2.3.4, 2.3.7).

## Correção ao relatório do usuário (§3.2)
O §3.2 do `docs/relatorio-tecnico-original.md` trata do macOS (Apple Silicon); nada disso vale no Linux (aqui `python` basta). Veredito da ficha Q2:

| Afirmação do relatório | Veredito | O que é verdade |
|---|---|---|
| macOS proíbe OpenGL/GLFW fora da main thread; `launch_passive()` em background causa **SegFault** | **parcial** | Vale para **janelas** (GLFW/Cocoa; doc: "a platform limitation which requires the main thread to be one that does the rendering"). **Offscreen** (`mujoco.Renderer`) não é restrito desde a 2.3.4 (CGL, changelog). Sem `mjpython`, `launch_passive` levanta `RuntimeError("`launch_passive` requires that the Python script be run under `mjpython` on macOS")` (`viewer.py`) — **não** SegFault. Os crashes históricos do `launch_passive` (#783: race com `mj_forward`, corrigido na 2.3.4; #790: crash do GLFW ao encerrar o Python, 2.3.7 — changelog) não vinham da thread de UI do macOS |
| `mjpython` "força a representação passiva na thread principal" | **parcial** | Só `launch_passive` precisa dele. Mecanismo inverso: o **script do usuário** roda em thread secundária; quem usa a thread principal real é o viewer (docstring de `mjpython.py`). Vem no pacote `mujoco` (macOS) e é substituto de `python`; não existe no Linux |
| macOS: `pip install mujoco` + GLFW pelo Homebrew | **parcial/incorreto** | `pip install mujoco` basta: `glfw` e `pyopengl` são dependências do wheel (✔ `importlib.metadata`) e o wheel do pyGLFW traz a libglfw p/ macOS; OpenGL vem do sistema. Homebrew não é necessário (`/opt/homebrew/lib` é só caminho de busca de fallback). O `Renderer` offscreen nem usa GLFW no macOS (usa `mujoco.cgl`, com fallback `glfw`) |

## Armadilhas
| Sintoma | Causa | Correção |
|---|---|---|
| `AttributeError: module 'mujoco' has no attribute 'Renderer'` | `PYOPENGL_PLATFORM` ≠ backend (ImportError engolido) | `unset PYOPENGL_PLATFORM` ou `=egl` com `MUJOCO_GL=egl` |
| `import mujoco` → `AttributeError … 'glGetError'` | `MUJOCO_GL=osmesa` sem `libOSMesa` | `MUJOCO_GL=egl` (CPU: `MUJOCO_EGL_DEVICE_ID=3`) |
| `ImportError: Cannot initialize a EGL device display` | `MUJOCO_EGL_DEVICE_ID` num dispositivo que não inicializa (aqui 1), ou PyOpenGL importado antes em sessão X11 | remova a variável / fixe com `__EGL_VENDOR_LIBRARY_FILENAMES`; defina `MUJOCO_GL`/`PYOPENGL_PLATFORM` antes de qualquer import |
| `ValueError: Image width 1280 > framebuffer width 640` | `offwidth/offheight` padrão 640×480 | `<visual><global offwidth offheight>` ou `model.vis.global_.offwidth` **antes** do `Renderer` |
| `X11: The DISPLAY environment variable is missing` + `FatalError: an OpenGL platform library has not been loaded…` | `MUJOCO_GL` padrão (glfw) sem display | `MUJOCO_GL=egl` |
| `EGLError … EGL_BAD_ACCESS … eglMakeCurrent` | `Renderer` criado numa thread e usado noutra | criar, usar e fechar na mesma thread |
| `Exception ignored in … Renderer.__del__ … EGLError: <exception str() failed>` ao sair | `Renderer` vivo no `atexit` (não fechado, ou exceção antes do `close`); o erro real vem antes | `with mujoco.Renderer(...)` / `close()` em `finally` (`mjkit.record` não protege: câmera inválida deixa o ruído) |
| imagem não muda após editar `qpos` | faltou `mj_forward` antes de `update_scene` | `mj_forward(m, d)` |
| MP4 com altura 368 + `IMAGEIO … macro_block_size=16` | `get_writer` redimensiona p/ múltiplo de 16 | `macro_block_size=2` (par basta p/ yuv420p) ou `1` |
| tira `sheet` sem o último quadro (padrão: 7 de 8) | `mjkit.record` compara `data.time >= t` sem tolerância e `sheet_times` termina em `duration` | último instante `duration - 0.01` |
| `WARNING: Pre-allocated visual geom buffer is full` | cena > `max_geom` (10000) | `Renderer(..., max_geom=N)` |
| quadros guardados todos iguais | usou `out=buf` (buffer reutilizado) | `.copy()` ou não passe `out` (Δ doc: sem `out` não precisa) |
| `res["log"][k]` com todas as linhas iguais à última | `probes` devolveu **view** do `MjData` (`d.qpos[:3]`) ✔ | `.copy()` na lambda (escalares como `d.xipos[1, 2]` já são cópia) |
| `render_video.py` termina com traceback/exit 1 (câmera inexistente, resolução > `offwidth`) | erros do Renderer não são capturados (o docstring promete exit 2) | confira `--camera` (nomes do `<camera>`) e a resolução |
