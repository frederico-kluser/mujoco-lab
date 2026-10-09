# GPU: MJX (JAX) e MuJoCo Warp (MJWarp) no MuJoCo 3.15

Simulação em lote na GPU: mapa dos backends, limites frente ao motor C, instalação e uso (RTX 4070 Laptop 8 GB, driver 610.57, Python 3.13), desempenho publicado, domain randomization e memória.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: ficha Q11; `docs/upstream/mujoco/doc/{mjx.rst,mjwarp/index.rst,skills/accelerated/SKILL.md,changelog.rst}`; `docs/upstream/mujoco/mjx/`; `docs/upstream/mujoco_warp/`; `docs/upstream/mujoco_playground/{CHANGELOG.md,pyproject.toml}`; testes em CPU num venv descartável (jax 0.11.2, warp-lang 1.17.0 e 1.18.0, mujoco-mjx e mujoco-warp 3.15.0).
> **Re-verificado em 2026-10-08** (§2.1, atuadores × backends): `.venv-gpu` (mujoco-mjx, mujoco-warp e warp-lang instalados), `JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES=""`; enums por introspeção e `put_model` de cada atuador.

## Quando ler este arquivo
- Escolher entre MuJoCo C, MJX-JAX, MJX-Warp e MJWarp antes de escalar RL/otimização em GPU.
- Instalar JAX/Warp (CUDA 12 × 13, `warp-lang` 1.17 × 1.18) sem sujar o `.venv` do laboratório (ele não tem JAX nem Warp).
- Portar uma cena do C para a GPU: o que é rejeitado e, pior, o que é **aceito e ignorado em silêncio**.
- Dimensionar `nworld`, `naconmax`, `njmax` e VRAM. Medições nesta máquina: `gpu-benchmarks.md`.

Legenda: **✔** = verificado por mim (execução em CPU com `JAX_PLATFORMS=cpu` e GPU escondida, `uv pip install --dry-run`, `nvidia-smi` ou conta); **não verificado em GPU** = só doc/código.

## 1. Mapa dos backends

| | MuJoCo C | MJX-JAX | MJX-Warp | MJWarp nativo |
|---|---|---|---|---|
| Uso | `import mujoco` | `from mujoco import mjx` (`impl='jax'`, padrão) | `mjx.put_model(m, impl='warp')` | `import mujoco_warp as mjw` |
| PyPI | `mujoco` | `mujoco-mjx` | `mujoco-mjx[warp]` (extra = `warp-lang`; o MJWarp já vem no wheel do MJX, em `mujoco.mjx.third_party`) ✔ | `mujoco-warp` |
| Hardware | CPU | qualquer XLA: GPU NVIDIA/AMD, TPU, Apple, CPU | NVIDIA/CUDA; CPU só p/ desenvolvimento (✔) | NVIDIA/CUDA; CPU só p/ desenvolvimento (✔) |
| Precisão | float64 | float32 (`JAX_ENABLE_X64=1` → float64 ✔) | float32 | float32 |
| Autodiff | não (há `mjd_transitionFD`, diferenças finitas) | sim, "mostly supported" (§2) | **não**, "no immediate plans" | **não** (issue #500) |
| Batch | `mujoco.rollout` (threads) | `jax.vmap`/`jit` | `jax.vmap` + `naconmax` | `nworld` nativo |
| Quem mantém / estado | DeepMind | DeepMind; doc 3.15: "cenas pequenas e gradientes", sem aviso de descontinuação | DeepMind; beta em 3.3.5; "most fully-featured" em 3.15; padrão do Playground ≥ 0.2.0 | DeepMind + NVIDIA (projeto Newton); oficial em 3.5.0; wheel 3.15.0 ainda classificado **Alpha** |

- **Relação oficial:** MJX é a "API JAX para várias implementações". MJX-Warp ≠ MJWarp: APIs distintas sobre o mesmo motor Warp. ✔ A cópia embutida no `mujoco-mjx` 3.15.0 **não é idêntica** ao wheel `mujoco-warp` 3.15.0 (até ~470 linhas diferentes por arquivo, em `forward.py`; p.ex. sem `integrator=discrete`): instalar os dois dá 2 motores independentes, com recursos e SPS que podem diferir. O código tem ainda `impl='cpp'` (não documentado): `mjx.step` falha com `ValueError` (✔) — ignore.
- **Seleção:** `mjx.put_model` sem `impl` escolhe JAX, mesmo com Warp instalado; Warp só com `MJX_GPU_DEFAULT_WARP=true` + GPU CUDA + `warp-lang` (código `docs/upstream/mujoco/mjx/mujoco/mjx/_src/io.py`). `impl='warp'` sem `warp-lang` → `RuntimeError`.
- **Quando usar (síntese):** 1 instância, tempo real/MPC/viewer, plugins, PGS/noslip, float64, determinismo → **C** (`mujoco.rollout` para lotes em CPU). Milhares de mundos em NVIDIA → **MJWarp** (PyTorch: mjlab, Isaac Lab/Newton) ou **MJX-Warp** (JAX/Playground). Gradiente por autodiff, cena pequena → **MJX-JAX**. Batch de câmeras → batch renderer do MJX-Warp/MJWarp.
- Doc: MJX-JAX numa única cena pode ser **10× mais lento** que o C; MJWarp escala melhor que o MJX em muitos geoms/DoF, mas pior que o C numa árvore única acima de ~60 DoF (só com `sleeping` + islands chega a centenas).

## 2. Limites frente ao motor C

| Recurso | MuJoCo C | MJX-JAX | MJWarp / MJX-Warp |
|---|---|---|---|
| Precisão | float64; `tolerance` 1e-8 | float32 (x64 opcional) | float32; `tolerance` ≥ 1e-6 (clamp ✔: 1e-8 → 1e-6); contato/atrito pequeno pode divergir do C |
| Determinismo | repetível bit a bit ✔ | CPU repetível ✔; GPU n/d | GPU **não** determinística (doc: atomics); CPU determinística ✔ (`wp.set_device("cpu")`) |
| Solver | PGS, CG, Newton, noslip | CG, Newton. PGS → `NotImplementedError` ✔. **`noslip_iterations>0`: aceito e IGNORADO** ✔ | CG, Newton. PGS e noslip → `NotImplementedError` ✔ |
| Integrador | Euler, RK4, implicit, implicitfast, discrete | Euler, RK4, implicitfast; implicitfast + fluido → erro ✔; `implicit` → erro ✔; **`discrete`: `put_model` aceita, `mjx.step` falha** ✔ | MJWarp aceita todos ✔, sem o "midpoint" do implicitfast; **MJX-Warp rejeita `implicit` e `discrete`** ✔ |
| Plugins | todos | **plugin de atuador aceito e IGNORADO** ✔ (`mujoco.pid`: números errados sem erro nenhum; §2.1) | corpo/atuador/sensor → `NotImplementedError` ✔ (`Actuator plugins not supported.`, `io.py:357`); SDF só por hooks Python (`mjw._src.collision_sdf.user_sdf`) |
| Flex | completo | `NotImplementedError` ✔ | experimental (`put_model` aceita ✔) |
| Atuadores novos do 3.15 | `pid`, `dcmotor`, `orientation` | os três → `NotImplementedError` ✔ (campo que falha primeiro: `mjGAIN_PID`, `mjBIAS_DCMOTOR`, `mjBIAS_SO3`; §2.1) | `dcmotor` ✔ aceito e igual ao C (qvel 75,965); `pid` → `mjGAIN_PID`, `orientation` → `mjTRN_SO3` ✔ (Δ doc: a tabela diz "All") |
| Sensores | todos | subconjunto (lista na nota [2] de `mjx.rst`) | todos, exceto `PLUGIN` |
| Fluido | `flInertia` e `fluidshape="ellipsoid"` | só `flInertia`; **elipsoide IGNORADO** ✔ (caso de teste: `qfrc_passive` −0,013 vs −0,0695 no C) | ambos ✔ (−0,0695, igual ao C) |
| Geoms | todas | ELLIPSOID/CYLINDER só colidem com primitivos (nem todos os pares, nota [3]); BOX é malha; sem SDF; margem/gap em malha/hfield → erro | todas; SDF por hooks; `margin≠0` em alguns pares CCD → erro |
| Jacobiano, islands | dense/sparse; sim | só dense; sem islands | dense/sparse; islands existem (sleeping, compact solver) |
| Contatos/restrições | dinâmicos | tamanho fixado pelo modelo (humanoide: 177 contatos, 303 linhas) ✔; `njmax`/`naconmax` ignorados | buffers fixos `naconmax`/`njmax`; estouro = comportamento indefinido |
| Acesso nomeado | `data.body('x')` | `Data.bind(model, spec.body('x'))` | não há (issue #884) |

- ✔ da 4ª coluna = `mjw.put_model`; `mjx.put_model(impl='warp')` repete as rejeições de PGS, noslip e plugin de atuador, aceita flex e implicitfast + fluido, e rejeita também `implicit` e `discrete`.
- **Autodiff (MJX-JAX):** ✔ com `opt.iterations` padrão (100), `jax.grad` falha ("Reverse-mode … lax.while_loop"); `jax.jacfwd` funciona; com `opt.iterations = 1` ambos funcionam (issue #2259).
- Δ doc: `mjx.rst` afirma que o `put_model` levanta exceção para recurso não suportado — falso para noslip, plugin de atuador e fluido elipsoidal (MJX-JAX). Antes de confiar numa cena na GPU, rode `parity()` (§4).
- ⚠ O template `quadrotor` com ar ligado (`implicitfast` + `density>0`) não roda no MJX-JAX (`NotImplementedError` ✔): use o MJWarp ou desligue o fluido.

### 2.1 Matriz de atuadores × backend (✔ medido 2026-10-08, `.venv-gpu`, CPU)
Cada cena isolada: 1 junta, 1 atuador; enums lidos do `MjModel` compilado e o modelo passado a `mjx.put_model` e `mjw.put_model`. **A rejeição é por enum, não por nome do atalho** — o MJX-JAX procura primeiro no `biastype`, o MJWarp no `trntype`.

| Atuador | enums reais no C (3.15.0) | MJX-JAX | MuJoCo Warp |
|---|---|---|---|
| `motor` | trn joint · gain fixed · bias **none** | ✔ aceito | ✔ aceito |
| `position` | trn joint · gain fixed · bias **affine** | ✔ aceito | ✔ aceito |
| `general` com `gaintype=fixed` e `biastype` none ou affine | idem | ✔ aceito | ✔ aceito |
| `dcmotor` (com `motorconst`/`resistance`) | trn joint · dyn/gain/bias **dcmotor** | ✘ `NotImplementedError: [<mjtBias.mjBIAS_DCMOTOR: 3>] not supported` | ✔ aceito (paridade numérica com o C medida em 2026-10-07: §2) |
| `pid` (atalho; `nu=2`, `nactuator=1`) | trn joint · dyn none · gain **pid** · bias affine | ✘ `[<mjtGain.mjGAIN_PID: 5>] not supported` | ✘ `['mjGAIN_PID'] not supported.` |
| `orientation` (ball joint, ou site+`refsite`; `nu=nout=3`) | trn **so3** · gain so3 · bias so3 | ✘ `[<mjtBias.mjBIAS_SO3: 4>] not supported` | ✘ `['mjTRN_SO3'] not supported.` |
| `<plugin joint=… plugin="mujoco.pid">` (`pid.xml`, `nu=nactuator=4`) | `actuator_plugin=[0 1 2 3]` | ⚠ **ACEITO EM SILÊNCIO** — treina com números errados | ✘ `NotImplementedError: Actuator plugins not supported.` |

- **PERIGO (treino em GPU):** o plugin `mujoco.pid` é **aceite sem erro** pelo `mjx.put_model`; o MJX lê só os campos `general` do atuador — que no `pid.xml` são `gain fixed` (`gainprm[0]=1`), `bias none`, `dyn none`, `trn joint` — e o controlador PID do plugin não existe: o resultado é lixo silencioso. Medido em `docs/upstream/mujoco/model/plugin/actuator/pid.xml`, `ctrl = 0,1` nos 4 canais, 2000 passos: qpos no C `[0,1275 0,0897 0,1 0,1]` vs MJX-JAX `[112,56 112,56 −0,0904 −0,0904]` (max|Δ| ≈ 1,1e2). **Antes de treinar, verifique `(m.actuator_plugin != -1).any()`** ou rode `parity()` (§4) — a exceção do `put_model` não é garantia de suporte.
- **Atalhos × `general`:** o que o backend valida são os enums resultantes, não o elemento escrito — `position` é `general gaintype=fixed biastype=affine` e por isso passa; qualquer `general` com `biastype`/`gaintype`/`dyntype` fora dos conjuntos acima falha igual (`mjx/_src/io.py:374-387`; `mujoco_warp/_src/io.py:314-328`).
- **Modelos do laboratório** (✔ 2026-10-08): `models/boston_dynamics_spot/spot.xml` = 12× `position` (gain fixed/bias affine/trn joint, `nu=nactuator=12`) e `models/bitcraze_crazyflie_2/cf2.xml` = 4× `motor` (gain fixed/bias none/**trn site**, `nu=nactuator=4`); ambos com `nplugin=0` e `put_model` **aceito** nos dois backends (o resto da cena — malhas, sensores — não foi reavaliado aqui).
- **Flag de energia × MJX** (✔ 2026-10-08): `lab/spot.py` e `lab/crazyflie.py` ligam `mjENBL_ENERGY` (para `data.energy` nos experimentos), mas o **MJX não implementa a flag**: `mjx.put_model` falha com `NotImplementedError: mjtEnableBit.mjENBL_ENERGY` (MJX-JAX **e** `impl='warp'`); o MuJoCo Warp nativo (`mjw.put_model`) aceita-a. Para preparar um modelo do lab para o MJX use `spot.carregar(energia=False)` / `crazyflie.carregar(energia=False)` — a predefinição `energia=True` mantém o comportamento exato dos experimentos `07_spot_motores`/`08_crazyflie_motores` (o parâmetro vale nos dois caminhos de `carregar`, `sensores=True`/`False`).

## 3. Instalação

| Pacote (PyPI) | Versão | Requisitos / notas |
|---|---|---|
| `mujoco-mjx` | 3.15.0 | Python ≥ 3.10; deps jax, jaxlib, mujoco, scipy, trimesh; **pacote separado** (`from mujoco import mjx` falha no `.venv` ✔); extra `[warp]` = só `warp-lang==1.17.0` |
| `mujoco-warp` | 3.15.0 | Python ≥ 3.10; deps mujoco ≥ 3.12, numpy, `warp-lang>=1.15`; extras `cpu` (jax), `cuda` (`jax[cuda12]`) |
| `jax[cuda13]` / `jax[cuda12]` | 0.11.2 | Python ≥ 3.12; driver ≥ 580 (13) / ≥ 525 (12); cuda13 exige GPU SM ≥ 7.5 (esta: 8.9); `[cuda13]` ≈ 2,5 GB de wheels (soma dos tamanhos no PyPI) |
| `warp-lang` | 1.17.0 (pin do MJX) / 1.18.0 (último) | wheel do PyPI = CUDA 12.9 (driver ≥ 525), com NVRTC (sem toolkit); cache `~/.cache/warp/<versão>` |

```bash
# ✔ resolução testada com `uv pip install --dry-run` (uv 0.12.7, py3.13); instalação em GPU: não verificada aqui
V=.venv-gpu; [ -d $V ] || uv venv --python 3.13 $V    # venv separado do .venv do laboratório; reutilize se já existir
uv pip install --python $V/bin/python "mujoco-mjx[warp]" "jax[cuda12]"   # = CI do MuJoCo (mjx/cuda_requirements.txt)
#   ou "jax[cuda13]": recomendado pelo JAX (driver 610.57 e SM 8.9 atendem); coexistência com o Warp CUDA 12.9: não documentada
uv pip install --python $V/bin/python mujoco-warp          # opcional: API nativa `mjw` (com o 1.17.0 já presente, não muda o Warp)
```
- **CUDA 12 × 13:** o JAX recomenda 13 (vai abandonar o 12); o CI do MuJoCo (`mjx/cuda_requirements.txt`) fixa `jax-cuda12-plugin` + `warp-lang==1.17.0` e os extras `cuda` do `mujoco-warp` e do Playground são `jax[cuda12]`. Qual combinação roda nesta GPU: `gpu-benchmarks.md`.
- **`warp-lang` 1.17 × 1.18** (✔ dry-run): `mujoco-mjx[warp]` pina `==1.17.0`; `mujoco-warp` sozinho resolve para 1.18.0 (o grupo `gpu` do `pyproject.toml` do laboratório também: sem pin, sem `[warp]`); Playground `main` exige `>=1.18.0` (o `playground==0.2.0` do PyPI aceita `>=1.11`). ⚠ `"mujoco-mjx[warp]" "warp-lang>=1.18"` **não falha**: o uv rebaixa o `mujoco-mjx` para 3.3.4 (sem extra) e só avisa. MJX-Warp e MJWarp rodam com 1.18.0 ✔ (CPU).
- **Variáveis:** `JAX_PLATFORMS=cpu` força CPU (smoke test sem GPU ✔); `CUDA_VISIBLE_DEVICES=""` esconde a GPU do Warp (✔; imprime "Warp CUDA error 100", inofensivo). JAX pré-aloca 75 % da VRAM (6141 MiB de 8188): `XLA_PYTHON_CLIENT_PREALLOCATE=false` ou `XLA_CLIENT_MEM_FRACTION=.5` (nome novo no jaxlib 0.11.2; o antigo `XLA_PYTHON_CLIENT_MEM_FRACTION` é obsoleto e dá `ValueError` se ambos existirem — lido no código); `XLA_PYTHON_CLIENT_ALLOCATOR` ∈ default, platform, bfc, cuda_async, vmm, address. MJX-JAX: `XLA_FLAGS=--xla_gpu_triton_gemm_any=true` (doc: até +30 %).
- Diagnóstico do ambiente: `python3 .agents/mujoco-lab-agent-skill/scripts/env_check.py --gpu`.
- **Não verificado em GPU — como verificar** (no venv GPU, sem `JAX_PLATFORMS=cpu`): (1) `jax.devices()` mostra `cuda:0` e `wp.get_cuda_device_count() == 1`; (2) os blocos de §4 passam e `d0.qpos.devices()` / `d.qpos.device` indicam a GPU (testa a coexistência JAX CUDA 12/13 × Warp CUDA 12.9); (3) `nvidia-smi --query-gpu=memory.used --format=csv -l 1` durante o MJX-Warp, com e sem `XLA_PYTHON_CLIENT_PREALLOCATE=false`; (4) `mjwarp-testspeed … --memory`.

## 4. API mínima
Os blocos rodam sem GPU: `JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES="" python bloco.py` (o Warp cai em CPU). Em GPU o código é o mesmo — **não verificado em GPU**.

```python
# MJX: o mesmo código com impl='jax' (padrão) ou impl='warp'. ✔ testado (CPU)
import jax, jax.numpy as jnp, mujoco
import warp as wp; wp.config.log_level = wp.LOG_WARNING        # só p/ impl='warp': silencia o log de compilação
from mujoco import mjx

XML = "<mujoco><worldbody><geom type='plane' size='5 5 .1'/><body pos='0 0 .09'><freejoint/><geom type='box' size='.1 .1 .1' mass='1'/></body></worldbody></mujoco>"
mjm, NW = mujoco.MjModel.from_xml_string(XML), 8
for impl in ("jax", "warp"):
    kw = dict(naconmax=NW * 8, njmax=32) if impl == "warp" else {}   # buffers fixos só no Warp; naconmax = TODOS os worlds do vmap
    mx, d0 = mjx.put_model(mjm, impl=impl), mjx.make_data(mjm, impl=impl, **kw)
    batch = jax.vmap(lambda v: d0.replace(qvel=d0.qvel.at[2].set(v)))(jnp.linspace(0, 1, NW))   # NW mundos, v_z distinto
    step = jax.jit(jax.vmap(mjx.step, in_axes=(None, 0)))       # modelo sem batch (None), data com batch (0)
    for _ in range(50): batch = step(mx, batch)
    print(impl, batch.qpos.shape, batch.qpos.dtype, batch.qpos[:3, 2].round(4))
```
```python
# MuJoCo Warp nativo. ✔ testado (CPU); CUDA graph (wp.ScopedCapture) não verificado em GPU
import mujoco, numpy as np, warp as wp, mujoco_warp as mjw
wp.config.log_level = wp.LOG_WARNING

XML = "<mujoco><worldbody><geom type='plane' size='5 5 .1'/><body pos='0 0 .09'><freejoint/><geom type='box' size='.1 .1 .1' mass='1'/></body></worldbody></mujoco>"
mjm, NW = mujoco.MjModel.from_xml_string(XML), 8
m = mjw.put_model(mjm)                                          # modelo único; campos com batch: §6
d = mjw.make_data(mjm, nworld=NW, nconmax=8, njmax=32)           # POR world; None → heurística (48/64 p/ este modelo)
wp.copy(d.qvel, wp.array(np.tile([0, 0, 1.0, 0, 0, 0], (NW, 1)), dtype=float))
for _ in range(50): mjw.step(m, d)                              # in-place; GPU: wp.ScopedCapture() + wp.capture_launch(g)
print(d.qpos.numpy().shape, d.qpos.numpy().dtype, "overflow:", d.overflow.numpy())

tiny = mjw.make_data(mjm, nworld=NW, nconmax=1, njmax=2)         # limites pequenos DE PROPÓSITO
m.opt.warn_overflow = False                                      # sem wp.printf; o bitmask continua gravado
mjw.step(m, tiny)
print("overflow:", [mjw.OverflowType(int(v)).name for v in tiny.overflow.numpy()[:2]], "| nacon =", int(tiny.nacon.numpy()[0]), "> naconmax =", tiny.naconmax)
```
- **Overflow (MJWarp):** `nconmax` = contatos por world (um world pode exceder se a soma ≤ `nworld·nconmax`); `naconmax` = total de todos os worlds (vence o `nconmax`); `njmax` = restrições por world (estrito); idem `nccdmax`/`naccdmax`, `nvmax`. Estouro **não levanta exceção**: comportamento indefinido, bit em `Data.overflow` (`mjw.OverflowType`; inclui também `ITERATIONS`/`LS_ITERATIONS`). `nacon` passa de `naconmax` quando estoura (mede a demanda ✔). Leia `overflow` só em reset/fim de rollout (sincroniza host↔device). No MJX-Warp: `d._impl.overflow` ✔.
- MJX 3.15: `d.contact`/`d.efc_J` dão `DeprecationWarning` (✔) → `d._impl.contact`; no Warp leia contatos por sensores de contato. Reset parcial em batch: `data.where(done, reset_data)` (JAX e Warp). MJX não é JIT por padrão; a 1ª chamada compila (✔ ~9 s no humanoide, vmap 64, CPU). `jax.pmap` com MJX-Warp funciona desde 3.4.0 (changelog; a discussão de ago/2025 do Playground está desatualizada).
- Copiar de volta ao C (para renderizar): `mjx.get_data_into(mjd, mjm, d)` / `mjw.get_data_into(mjd, mjm, d)`; `mjw.put_data(mjm, mjd, nworld=N, …)` parte de um `MjData`; `mjw.reset_data(m, d)`. CUDA graph: `with wp.ScopedCapture() as c: mjw.step(m, d)` e `wp.capture_launch(c.graph)`; mudar um campo de `m.opt` pode exigir recapturar (doc).

```python
# Paridade C × MJX-JAX: roda os dois e compara qpos; acusa recurso aceito mas ignorado. ✔ testado (CPU)
import jax, mujoco, numpy as np
from mujoco import mjx

def parity(mjm, nstep=400):
    d = mujoco.MjData(mjm)
    for _ in range(nstep): mujoco.mj_step(mjm, d)
    mx, dx, step = mjx.put_model(mjm), mjx.make_data(mjm), jax.jit(mjx.step)
    for _ in range(nstep): dx = step(mx, dx)
    return float(np.abs(np.asarray(dx.qpos) - d.qpos).max())

INCL = "<mujoco><option noslip_iterations='{ns}' cone='elliptic'/><worldbody><geom type='plane' size='5 5 .1' euler='15 0 0'/><body pos='0 0 .12' euler='15 0 0'><freejoint/><geom type='box' size='.1 .1 .1' mass='1'/></body></worldbody></mujoco>"
for ns in (0, 5): print(f"noslip={ns}: max|qpos_C - qpos_MJX| = {parity(mujoco.MjModel.from_xml_string(INCL.format(ns=ns))):.2e}")
pid = mujoco.MjModel.from_xml_path("/home/ondokai/Projects/MuJoCo/docs/upstream/mujoco/model/plugin/actuator/pid.xml")
print("plugin mujoco.pid:", f"{parity(pid):.2e}")   # observado: 1,2e-5 · 4,3e-4 (noslip: o C muda, o MJX não) · ~9e-2 (plugin ignorado)
```

**Fluxo para portar uma cena:** (1) valide no C; (2) `put_model` no backend (exceção = recurso não suportado) e `parity()` — ou rode o MJWarp em CPU e compare com o C; (3) dimensione `nconmax`/`njmax` (`--measure_alloc`, `Data.overflow`; no MJX-Warp, `mjwarp-viewer`/`mjx-viewer` mostram os estouros); (4) escale `nworld` medindo SPS e VRAM (§5–§6); (5) só então randomize (§6).

## 5. Desempenho publicado × CPU medida
Tabela oficial `mjx.rst` § Graph Modes, "Steps per Second (SPS) for MJX-Warp Graph Modes" (**hardware, nworld e versão não declarados**):

| Configuração | Humanoid | Aloha Pot |
|---|---|---|
| MJWarp puro (sem JAX FFI) | 3,35 M | 2,45 M |
| **MJX-Warp** via JAX FFI, `WARP` (padrão em GPU; em CPU, `JAX`) | **2,96 M** | **2,33 M** |
| MJX-Warp, `WARP_STAGED` (buffers de staging: mais memória) | 2,67 M | 1,96 M |
| MJX-Warp, `WARP` com recaptura forçada do graph a cada passo | 0,80 M | 0,65 M |

- **Correção ao relatório do usuário (origem dos números):** 2,96 M é o **Humanoid** e 2,33 M é a cena **Aloha Pot**, ambos **MJX-Warp** (não MJX-JAX, não MJWarp nativo).
- `mjx.rst` § Sharp Bits (1 humanoide, MJX-JAX): 650 K (CPU Apple M3 Max), 1,8 M (CPU AMD 3995WX 64 núcleos), 950 K (A100, batch 8192), 2,7 M (TPU v5 × 8, batch 16384). `benchmarks/README.md` do MJWarp: saída de exemplo 2 729 192 SPS (humanoide, nworld 8192, hardware n/d) — não confundir com o 2,7 M do TPU.
- NVIDIA (blog; razões do fabricante, **não** SPS): MJWarp/MJX = 152× (locomoção) e 313× (manipulação) numa RTX 4090 (2025); 252× e 475× numa RTX PRO 6000 Blackwell (2026).
- **CPU medida nesta máquina** (ficha Q11/F20: i9-14900HX, 32 threads, máquina carregada; humanoide do benchmark: nv=27, dt 0,005, Newton): `mujoco.rollout` 32 threads (4096 × 100 passos) ≈ **0,26–0,29 M SPS**; 1 thread ≈ 34–40 K. Sem colapso em 4096; ≈ 10× abaixo dos 2,7–3,35 M publicados para Warp (hardware diferente). **GPU desta máquina:** `gpu-benchmarks.md`.
- Medir: `mjwarp-testspeed <xml> --nworld N --nconmax .. --njmax .. [--measure_alloc] [--memory] [--event_trace]` (`--measure_alloc` imprime contatos/restrições por passo, para dimensionar `nconmax`/`njmax`; padrões `--nworld=8192 --nstep=1000`; só GPU ✔: em CPU dá `ValueError: testspeed available for gpu only`) e `mjx-testspeed --mjcf=<xml> --batch_size=N` (padrões 1024, `--solver=cg --iterations=1 --ls_iterations=4`; o C usa 100/50).
- No MJX-JAX o custo depende de `opt.iterations`/`ls_iterations` (baixe-os até o limite da estabilidade; Newton converge com ~1 iteração); o MJWarp sai cedo quando todos os worlds convergem, então esses valores pesam menos (doc).

## 6. Domain randomization e memória
```python
# Domain randomization: UM modelo; os campos randomizados ganham eixo de batch. ✔ testado (CPU; MJX e MJWarp dão o mesmo resultado)
import jax, jax.numpy as jnp, mujoco, numpy as np, warp as wp, mujoco_warp as mjw
from mujoco import mjx
wp.config.log_level = wp.LOG_WARNING

XML = "<mujoco><worldbody><body pos='0 0 1'><joint type='hinge' axis='0 1 0' damping='.1'/><geom type='capsule' fromto='0 0 0 0 0 -.5' size='.02' mass='1'/></body></worldbody></mujoco>"
mjm, damp = mujoco.MjModel.from_xml_string(XML), np.array([0, .1, .5, 2.0], np.float32)   # 4 mundos, 4 amortecimentos

# MJX (impl='jax' ou 'warp'): campo -> array (NW, nv); in_axes marca com 0 o que tem batch
mx = mjx.put_model(mjm)
axes = jax.tree_util.tree_map(lambda x: None, mx).tree_replace({"dof_damping": 0})
mxb = mx.tree_replace({"dof_damping": jnp.asarray(damp)[:, None]})
d0 = mjx.make_data(mjm).replace(qvel=jnp.array([3.0]))
db, step = jax.vmap(lambda _: d0)(jnp.arange(4)), jax.jit(jax.vmap(mjx.step, in_axes=(axes, 0)))
for _ in range(100): db = step(mxb, db)
print("MJX   :", np.asarray(db.qvel[:, 0]).round(3))

# MJWarp: batch_sizes cria o eixo de batch; leitura = campo[worldid % shape[0]]
m = mjw.put_model(mjm, batch_sizes={"dof_damping": 4}); m.dof_damping.assign(damp[:, None])
d = mjw.make_data(mjm, nworld=4); wp.copy(d.qvel, wp.array(np.full((4, 1), 3.0), dtype=float))
for _ in range(100): mjw.step(m, d)
print("MJWarp:", d.qvel.numpy()[:, 0].round(3))
```
- ✔ O mesmo padrão `tree_replace` + `in_axes` funciona com `impl='warp'` (resultado idêntico); `mjx.put_model(..., batch_sizes=…)` existe para o Warp. Campos numpy "estruturais" do MJX (ex.: `jnt_limited`) forçam recompilação. Gravidade por mundo (MJWarp): `m.opt.gravity = wp.array([g, -g], dtype=wp.vec3f)` ✔ (mundos pares/ímpares). Malhas/geoms por mundo: compilar cada variante com `spec.compile()` e sobrescrever os campos por mundo (doc `mjwarp/index.rst` § Per-world assets; não verificado). Alterar `m.opt` pode exigir nova captura do graph.
- **Memória — ESTIMATIVA, não medição em GPU.** `nvidia-smi` (✔): 8188 MiB totais, ≈ 350 MiB em uso com o desktop ocioso (sobe com outros processos).

| Item | Valor |
|---|---|
| Reserva padrão do JAX | 75 % = 6141 MiB (sobram ~2 GB p/ o Warp no MJX-Warp: competição entre os pools é inferência, não verificada) |
| `mjw.Data` do humanoide (nv=27, `nconmax=24`, `njmax=64`), arrays declarados ✔ | 38 / 152 / 305 MiB para 1024 / 4096 / 8192 worlds (≈ 38 KiB/world); dominam `efc.J` (≈ 4·njmax·nv B/world, denso) e `qLD`/`qHLD` (≈ 4·nv² B cada) |
| `mjx.Data` (`impl='jax'`) do humanoide ✔ | ≈ 81 KiB/world (→ ≈ 650 MiB p/ 8192); contatos/restrições dimensionados pelo modelo |
| Cena pesada (doc): Aloha clutter, nv=136, 2048 worlds, `njmax=384` | `efc.J` denso 408 MiB (✔ conta) vs ≈ 84 MB esparso |
| **Fora dessa conta** (não medido) | workspace inline do solver/CCD ("Other memory" do `--memory`), buffers de staging do `WARP_STAGED`, temporários do XLA, malhas/CCD, render em lote |

- Conclusão (estimativa): humanoide com milhares de mundos cabe folgado em 8 GB (extrapolação linear só dos arrays declarados: 65 536 worlds ≈ 2,4 GiB); o limite vem de CCD/malhas/nv alto/render, não do `Data` básico. Reduza memória com `njmax`/`naconmax` mínimos, `nccdmax` < `nconmax`, sem `multiccd`, Jacobiano esparso (nv > 60), `sleeping` + `nvmax`. Número real: `mjwarp-testspeed … --memory` + `nvidia-smi` → `gpu-benchmarks.md`.

```python
# Bytes "declarados" de mjw.Data (mesma conta do `mjwarp-testspeed --memory`): mede em CPU antes de ir à GPU. ✔ testado (CPU)
import dataclasses, mujoco, warp as wp, mujoco_warp as mjw
wp.config.log_level = wp.LOG_WARNING

def declared(o):
    vals = (getattr(o, f.name) for f in dataclasses.fields(o))
    return sum(declared(v) if dataclasses.is_dataclass(v) else v.capacity if isinstance(v, wp.array) else 0 for v in vals)

mjm = mujoco.MjModel.from_xml_path("/home/ondokai/Projects/MuJoCo/docs/upstream/mujoco_warp/benchmarks/humanoid/humanoid.xml")
for nw in (1024, 4096): print(nw, "worlds:", round(declared(mjw.make_data(mjm, nworld=nw, nconmax=24, njmax=64)) / 2**20, 1), "MiB")
```

## Correções ao relatório do usuário (§4.3)

| # | O relatório diz | Veredito | Verdade em 3.15.0 |
|---|---|---|---|
| 1 | MJX = reimplementação JAX/XLA em GPU/TPU, `mjx.Model`/`mjx.Data` em batch, `put_model`/`make_data` | CORRETA (p/ MJX-JAX) | "MJX" agora é a API JAX com 2 implementações (`impl='jax'` padrão, `'warp'`); o batch vem de `jax.vmap`/`jit` (não é automático); `mujoco-mjx` é pacote separado. |
| 2 | MJX-Warp/MJWarp "otimiza operações tensoriais … sacrificando diferenciações analíticas" | PARCIAL | MJX-Warp e MJWarp são APIs distintas sobre o mesmo motor; não é compilador de tensores (XLA): são kernels CUDA SIMT em Warp (tiles só p/ álgebra densa, ex.: Cholesky). Nada é "sacrificado": o MJX-JAX tem autodiff, o MJX-Warp "has no immediate plans", o MJWarp não é diferenciável (issue #500). O motor é o MJWarp (DeepMind + NVIDIA); MJX-Warp é o frontend JAX. |
| 3 | CPU "otimizado para latência" (teleoperação/MPC) | CORRETA | MJWarp otimiza throughput, o C otimiza latência; um passo do MJWarp tende a ser mais lento. |
| 4 | Humanoid: MJX (JAX) 2,33 M; MJWarp 2,96 M SPS | INCORRETA | Ambos são **MJX-Warp** (FFI, modo `WARP`); 2,96 M = Humanoid, 2,33 M = **Aloha Pot**. MJWarp puro: 3,35 M / 2,45 M. MJX-JAX no humanoide (doc): 950 K (A100) e 2,7 M (TPU). "Sem recaptura forçada" é a linha `WARP` vs 0,80 M/0,65 M. Hardware n/d (§5). |
| 5 | CPU sequencial (inclui `mujoco.rollout`) "estrangula" com 4096 instâncias | PARCIAL | `mujoco.rollout` é multithread, não sequencial; sem colapso em 4096 (✔ 0,26–0,29 M SPS, 32 threads); ≈ 10× abaixo do Warp publicado. O gargalo típico de RL em CPU é a transferência host↔device. |
| 6 | DR "enviando modelos com inércia/geometria diferentes via `mjx.put_model`" | PARCIAL | Um só `put_model`; randomizam-se campos com eixo de batch (MJX: `tree_replace` + `in_axes`; MJWarp: `batch_sizes`); malhas por mundo exigem compilar cada variante no host (§6). |

## Armadilhas

| Sintoma | Causa | Correção |
|---|---|---|
| `ImportError: cannot import name 'mjx' from 'mujoco'` ✔ | `mujoco-mjx` é pacote separado; o `.venv` não o tem | venv GPU separado (§3); não instale no `.venv` |
| `RuntimeError: warp-lang is not installed` com `impl='warp'` ✔ (e `import mjx` imprime "Failed to import warp", inofensivo) | falta `warp-lang` | `pip install "mujoco-mjx[warp]"` |
| `"mujoco-mjx[warp]" "warp-lang>=1.18"` "instala", mas o MJX vira 3.3.4 ✔ | o extra pina 1.17.0; o uv rebaixa o MJX (só avisa) | não force `>=1.18` com o extra; ou instale sem o extra (Warp 1.18.0 roda ✔ CPU) |
| `AttributeError … 'GraphMode'` (Δ doc) ✔ | `mjx.rst` escreve `mjxw.GraphMode` | `mjxw.types.GraphMode.WARP_STAGED` (membros NONE, JAX, WARP, WARP_STAGED, WARP_STAGED_EX; `JAX` não funciona com Warp na GPU) |
| Resultado diverge do C **sem erro** (MJX-JAX) ✔ | noslip, plugin de atuador e fluido elipsoidal aceitos e ignorados | `parity()` (§4); `(m.actuator_plugin != -1).any()` como pré-checagem de treino (§2.1); use C ou MJWarp |
| `NotImplementedError: integrator 4 …` (MJX-JAX, no `mjx.step`) ou `mjINT_DISCRETE is unsupported` (MJX-Warp, no `put_model`) ✔ | `discrete`: o JAX só falha no passo; a cópia do Warp embutida no MJX não o tem | Euler/implicitfast; `discrete` só no MJWarp nativo |
| `NotImplementedError` no `mjw.put_model` ✔ | PGS, noslip, plugin de corpo/atuador/sensor, flex quadrático, `pid` (`mjGAIN_PID`) e `orientation` (`mjTRN_SO3`); no MJX-JAX também `dcmotor` (`mjBIAS_DCMOTOR`) | remover do XML (no C seguem válidos); p/ GPU use `motor`/`position`/`general` (ou `dcmotor` no MJWarp); §2.1 |
| `NotImplementedError: mjtEnableBit.mjENBL_ENERGY` no `mjx.put_model` ✔ | os modelos do lab ligam a flag de energia (`lab/spot.py`, `lab/crazyflie.py`) para `data.energy`; o MJX não a implementa (o MJWarp nativo aceita) | `spot.carregar(energia=False)` / `crazyflie.carregar(energia=False)` (§2.1) |
| Contatos somem / NaN no MJWarp, sem exceção | overflow de `naconmax`/`njmax`/`nccdmax`/`nvmax` | checar `d.overflow` e `nacon > naconmax`; `warn_overflow=True` (padrão) ao desenvolver e `False` em produção (o `wp.printf` serializa a GPU); `--overflow_behavior=error` (padrão do testspeed) |
| OOM ao usar MJX-Warp em 8 GB | provável (inferência): o JAX pré-aloca 75 % e o Warp aloca por fora | `XLA_PYTHON_CLIENT_PREALLOCATE=false` ou `XLA_CLIENT_MEM_FRACTION` (não verificado em GPU) |
| `jax.grad` falha "Reverse-mode … while_loop" ✔ | solver iterativo do MJX-JAX | `opt.iterations = 1` ou `jax.jacfwd` |
| `mjwarp-testspeed` → "testspeed available for gpu only" ✔ | só roda em GPU; a doc escreve `benchmark/` (typo) | `benchmarks/humanoid/humanoid.xml` (só no checkout `docs/upstream/mujoco_warp/`, não no wheel) |
| Logs "Module … load on device" na 1ª chamada | Warp compila kernels (cache `~/.cache/warp/<versão>`) | `wp.config.log_level = wp.LOG_WARNING` (`wp.config.quiet` é obsoleto ✔); `wp.clear_kernel_cache()` após atualizar |
| **Skill oficial `accelerated`:** "sem `njmax` em `mjx.put_data` os contatos são ignorados" | falso p/ `impl='jax'` ✔ (esfera repousa em z=0,1496; `njmax` é aceito e ignorado); só o Warp usa `njmax`/`naconmax` | não use essa regra no MJX-JAX |
| **Skill oficial:** `mjw.put_data(model, batch_size)` | assinatura errada: `AttributeError: 'int' object has no attribute 'ncon'` ✔ | `mjw.make_data(mjm, nworld=N)` ou `mjw.put_data(mjm, mjd, nworld=N)` |
| **Skill oficial:** "islands ❌ no MJWarp; monolítico" | falso: `mjw.island`, `DisableBit.ISLAND`, sleeping/compact solver (no MJX-JAX é verdade) | doc `mjwarp/index.rst` § Large scenes |
| **Skill oficial:** omite o MJX-Warp (`impl='warp'`, `naconmax`, `graph_mode`); cache em `/tmp/jax_cache` | skill desatualizada; este laboratório proíbe `/tmp` literal | use `~/.cache/jax` ou `"$TMPDIR/…"` em `jax_compilation_cache_dir` |
