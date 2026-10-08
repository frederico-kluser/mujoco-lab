# GPU nesta máquina: MJX-JAX, MJX-Warp e MuJoCo Warp — receita, medições e armadilhas
Como instalar (`.venv-gpu`) e quanto rendem, de verdade, MJX/MJWarp na RTX 4070 Laptop 8 GB; teoria, API e limites ficam em `gpu-mjx-warp.md`.

> Verificado em MuJoCo 3.15.0. **Campanha A = 2026-10-07** (modelos upstream/menagerie: humanoide, Humanoide B, pêndulo). **Campanha B = 2026-10-08** (modelos do laboratório: Spot e Crazyflie; `put_model`, paridade e memória). Fontes: ficha `pesquisas/conhecimento/Q11.md`; `docs/upstream/mujoco/doc/{mjx.rst,mjwarp/index.rst}`; `docs/upstream/mujoco_warp/benchmarks/`; medições deste laboratório com `scripts/gpu_bench.py` (protocolo abaixo).

## Quando ler este arquivo
- Instalar JAX/Warp com GPU sem tocar no `.venv` (comandos e versões que funcionaram, combinações testadas).
- Escolher backend e `nworld` para esta GPU com SPS e VRAM reais, não os publicados.
- Saber o que os **modelos do laboratório** (Spot/Crazyflie) rendem em cada backend e o que **não** corre (§5–§8).
- Entender por que o seu número difere do 2,96 M / 2,33 M da doc, ou diagnosticar OOM, NaN, estouro de buffer, lentidão.

Legenda: ✔ medido/testado aqui · ⚠ armadilha · Δ doc = a doc diverge do medido · «não verificado» = lacuna.

## 1. Máquina e protocolo
- i9-14900HX (32 threads), 31 GiB RAM, **RTX 4070 Laptop** (sm_89, 36 SMs, 8188 MiB, teto 80 W), driver 610.57.04 (CUDA 13.3), CachyOS. GPU e CPU **compartilhadas** com o desktop KDE (307–781 MiB de VRAM já em uso antes de cada processo) e com outros agentes (load da CPU 5–60 durante a sessão).
- `gpu_bench.py`: 1 processo por medida (nunca 2 na GPU); mesmo estado inicial em todos os backends (keyframe 0 + ruído em `qvel`/`ctrl`, semente 0); 1ª execução (JIT/captura) → ≥ 1,5 s de aquecimento → 5 repetições sincronizadas (3 nas pesadas) → **mediana**. SPS = nworld·passos/tempo. VRAM = `nvidia-smi` do PID após as repetições. JAX com `PREALLOCATE=false` e `MEM_FRACTION=0.85`.
- **Campanha B (2026-10-08)** — mesmo protocolo (`gpu_bench.py`, 50 passos, mediana de 5 repetições pós-aquecimento, 1 processo de cada vez), condições registadas: **load da CPU 2–4**, GPU em repouso ≈ 316 MiB de VRAM. Modelos do lab carregados por `lab/spot.py`/`lab/crazyflie.py`; as linhas «CPU `mj_step` 1 thr» são loop puro de `mj_step` (sem `rollout`, sem render). Mín/máx por célula não transcritos nesta tabela.

## 2. Instalação que FUNCIONOU ✔ (~1 min, ~3,3 GiB baixados, `.venv-gpu` = 6 GB; `.gitignore` já cobre `.venv-*/`)
```bash
cd /home/ondokai/Projects/MuJoCo
uv venv --python 3.13 .venv-gpu                      # separado: o .venv (sem JAX/Warp) fica intacto
uv pip install --python .venv-gpu/bin/python "mujoco==3.15.0" "mujoco-mjx==3.15.0" "mujoco-warp==3.15.0" warp-lang "jax[cuda12]"
uv pip freeze --python .venv-gpu/bin/python           # 34 pacotes
```
Versões finais: mujoco / mujoco-mjx / mujoco-warp **3.15.0**, **warp-lang 1.18.0**, jax / jaxlib / jax-cuda12-plugin / jax-cuda12-pjrt **0.11.2**, numpy 2.5.3, scipy 1.18.1, trimesh 5.1.1, nvidia-*-cu12 12.9 (cudnn 9.27.0.42, cublas 12.9.2.10), Python 3.13.15, uv 0.12.7. Sem conflito de resolução.

| Combinação (venv) | Resultado nesta máquina (driver 610.57) |
|---|---|
| `jax[cuda12]` 0.11.2 + `warp-lang` **1.18.0** (`.venv-gpu`) | ✔ JAX, Warp, MJX-JAX, MJWarp e MJX-Warp no mesmo processo; todas as medições abaixo |
| `jax[cuda12]` + `warp-lang` **1.17.0** (pin de `mujoco-mjx[warp]`) | ✔ JAX `cuda 12090`; MJX-Warp 1,19 M SPS @1024 (= 1.18.0); 1ª execução 34 s (compila os kernels da 1.17.0) |
| `jax[cuda13]` + `warp-lang` 1.18.0 (o que o grupo `gpu` do `pyproject.toml` instalaria) | ✔ JAX `cuda 13040`; @1024: MJX-Warp 1,16 M, MJWarp 1,30 M, MJX-JAX 6/6 82 K (−0…5 % vs cu12, no ruído) |
| `jax[cuda13]` + `warp-lang` 1.17.0 | não testado |
- Para o grupo `gpu` do `pyproject.toml`: `mujoco-mjx`, `mujoco-warp` (ambos `>=3.15,<3.16`), `warp-lang` **sem pin** (→ 1.18.0) e `jax[cuda12]` **ou** `jax[cuda13]`: as duas rodam; o extra `[warp]` não é necessário. Instale num venv à parte (`.venv-gpu`), não no `.venv`.
- Δ doc/ficha: o `warp-lang` 1.18.0 do PyPI é compilado com **CUDA Toolkit 13.4** (banner do Warp: `CUDA Toolkit 13.4, Driver 13.3`), não 12.9 (valor que a ficha Q11 dá para o 1.17.0); roda sem toolkit instalado e convive com o JAX CUDA 12.9 no mesmo processo.
- `uv sync --group gpu` instalaria no `.venv` do projeto: não use; esta receita é o caminho. Teste de GPU: `.venv-gpu/bin/python .agents/mujoco-agent-skill/scripts/gpu_bench.py ...` (§11).

## 3. Smoke tests ✔
| Teste | Resultado |
|---|---|
| (a) JAX vê a GPU | `jax 0.11.2`, `CudaDevice(id=0)`, `cuda 12090`, matmul 4096² ok; pool do JAX = 5876 MiB (75 % de 7834 MiB) |
| (b) Warp vê a GPU | `warp 1.18.0`, `cuda:0` RTX 4070 Laptop sm_89 8 GiB, mempool; kernel `saxpy` ok |
| (c) MJX-JAX, humanoide | `put_model`/`make_data` + `jit(vmap(mjx.step))`; 1 passo vs C: Δqpos 3,3e-6 (float32); JIT ≈ 17–28 s |
| (d) MJWarp nativo | `put_model`/`put_data(nworld)`/`step` + `wp.ScopedCapture`; 1 passo vs C: Δqpos 6,1e-8; captura 0,05–0,9 s |
| (e) MJX-Warp (`impl='warp'`) | ✔ com `jax[cuda12]` + `warp-lang` 1.18.0 no mesmo processo (sem ajuste); 1,2 M SPS @1024 |
| (f) Modelos do lab nos 3 caminhos | ✔ Spot e Crazyflie: `mujoco_warp.put_model` aceita-os como estão; MJX-JAX/MJX-Warp só depois de limpar a flag de energia (§6) |

## 4. Campanha A (2026-10-07) — modelos upstream: SPS · VRAM do processo em MiB; 50 passos; load da CPU 5–25 salvo nota
Humanoide `docs/upstream/mujoco/model/humanoid/humanoid.xml` (nv 27, Newton 100/50, dt 0,005):
| Backend | 1024 | 4096 | 8192 | 16384 | 32768 | 65536 |
|---|---|---|---|---|---|---|
| **MJWarp nativo** | 1,31 M · 242 | **1,89 M** · 370 | 1,80 M · 562 | 1,74 M · 914 | 1,68 M · 1682 | 1,55 M · 3218 |
| **MJX-Warp** | 1,20 M · 352 | 1,83 M · 480 | 1,78 M · 768 | 1,73 M · 1312 | 1,68 M · 2436 | — |
| MJX-JAX, opções do modelo (100/50) | 33,7 K · 452 | 27,0 K · 1220 | 30,6 K† · 2250 | 27,6 K† · 4298 | não cabe (extrapolado ≈ 8 GiB) | — |
| MJX-JAX, `iterations=6, ls_iterations=6` | 86,1 K · 452 | 87,2 K · 1222 | 81,9 K · 2250 | 74,3 K · 4296 | — | — |
| CPU `mujoco.rollout`, 32 threads (f64) | 202 K‡ | — | — | — | — | — |
| CPU `mujoco.rollout`, 32 threads (f64) — **campanha B, mesmo XML**, §5 | ≈ 552 K | ≈ 560 K | — | — | — | — |
† 20 e 10 passos, 3 repetições (orçamento de ~60 s de GPU). ‡ **campanha A**, load ≈ 8; **não comparar com a campanha B**: mesmo modelo, mas com load 50–60 deu 110–196 K, e a B (load 2–4, mediana de 5) é a referência atual de CPU. MJX-Warp e MJWarp: 0 NaN, 0 overflow.

Outros modelos (mesmo protocolo; «Humanoide B» = `mujoco_warp/test_data/humanoid`, modelo diferente do humanoide acima):
| Modelo · backend | 1024 | 4096 | 8192 | 16384 |
|---|---|---|---|---|
| Humanoide B (`mujoco_warp/test_data/humanoid`, 10/20, eulerdamp off) · MJWarp | — | 1,99 M | 1,91 M | 1,89 M |
| B · MJX-Warp | — | 1,93 M | 1,90 M | 1,86 M |
| B · MJX-JAX (10/20) | 54,7 K | 56,0 K | 47,5 K | — |
| B · CPU 32 thr (load 6–17) | — | 248 K | 241 K | 229 K |
| Pêndulo `assets/templates/pendulum` (nv 1, sem contato; 1000 passos) · MJWarp · VRAM | 6,12 M · 208 | 16,9 M · 240 | — | 27,7 M · 400 |
| Pêndulo · MJX-Warp | 5,72 M | 16,5 M | — | 29,2 M · 740 |
| Pêndulo · MJX-JAX | 3,06 M | 8,51 M | — | 18,7 M · 450 |
| Pêndulo · CPU 32 thr | 4,01 M | 3,95 M | — | 4,06 M |
- **Memória** (reta ajustada): MJWarp ≈ 195 MiB + 47 KiB/mundo; MJX-Warp ≈ 285 MiB + 67 KiB/mundo; MJX-JAX ≈ 195 MiB + 256 KiB/mundo (→ teto ≈ 20–25 mil mundos com o pool a 85 %). Humanoide em MJWarp: ≈ 100 mil mundos caberiam em ~5 GB (extrapolado; medido até 65 536 = 3,2 GB).
- Platô: SPS máximo em 4096 mundos, perde ≤ 8 % até 16384 e ≈ 18 % em 65536. Estável: 0 NaN; contatos ≈ 6/mundo, `nefc` ≈ 27.

## 5. Campanha B (2026-10-08) — modelos do LABORATÓRIO: SPS · método explícito
Protocolo: §1 (load 2–4; mediana de 5; 1 processo por vez). Spot = `lab/spot.py` (nu 12, nsensor 32, dt 0,002, `implicitfast`, atuadores `position`); Crazyflie = `lab/crazyflie.py` (nu 4, nsensor 5, dt 0,002, RK4, atuadores `motor`/wrench).

| Modelo | Backend · método (threads) | 1024 | 4096 |
|---|---|---|---|
| Spot | CPU `mujoco.rollout` (32 thr, f64) | 284 K | 290 K |
| Spot | CPU `mj_step` puro (1 thr, f64) | 74,6 K | — |
| Spot | MJWarp nativo (`njmax=64`) | 651 K | 812 K ⚠ |
| Spot | MJWarp nativo (`--nconmax 64 --njmax 256`) | — | 802 K ✔ |
| Spot | MJX-Warp (`impl='warp'`) | 528 K | 705 K |
| Spot | MJX-JAX | — | — (não corre: OOM, §6) |
| Crazyflie | CPU `mujoco.rollout` (32 thr, f64) | 1,21 M | 1,27 M |
| Crazyflie | CPU `mj_step` puro (1 thr, f64) | 105,6 K | — |
| Crazyflie | MJWarp nativo | 1,12 M | 2,94 M |
| Crazyflie | MJX-Warp (`impl='warp'`) | 984 K | 2,34 M |
| Crazyflie | MJX-JAX | 45 K | 37 K |

- ⚠ Spot em MJWarp com `njmax=64`: **4 de 4096 mundos com overflow NEFC**; com `--nconmax 64 --njmax 256` → **0 overflow** e 802 K (−1,2 % vs 812 K). Para treino, usar o dimensionamento folgado.
- Bónus medido: ligar a flag de energia (`<flag energy="enable"/>`) custa ≈ **1 %** no loop `mj_step` 1 thr (CPU).
- Sem SPS MJX-JAX para o Spot: o `put_model` passa, mas nenhum rollout ≥ 256 mundos aloca (§6) — a célula vazia é OOM, não falta de medição.

## 6. `put_model`: flag de energia e o teto do MJX-JAX ✔
| Modelo · backend | Com `mjENBL_ENERGY` ligada | Depois de limpar a flag em memória |
|---|---|---|
| Spot · MJX-JAX | `NotImplementedError: mjtEnableBit.mjENBL_ENERGY` | `put_model` OK — mas **nenhum rollout ≥ 256 mundos corre**: `RESOURCE_EXHAUSTED` com 6,33 GiB @256 e 38,27 GiB @1024, **invariante** a `naconmax`/`njmax`/autotune |
| Spot · MJX-Warp (`impl='warp'`) | `NotImplementedError` (idem) | OK → SPS na §5 |
| Crazyflie · MJX-JAX | `NotImplementedError` (idem) | OK → SPS na §5 |
| Crazyflie · MJX-Warp (`impl='warp'`) | `NotImplementedError` (idem) | OK → SPS na §5 |
| Spot / Crazyflie · **MuJoCo Warp nativo** (`mujoco_warp.put_model`) | ✔ aceita a flag tal como está | — |
- **Caminho oficial para MJX**: `lab.spot.carregar(energia=False)` e `lab.crazyflie.carregar(energia=False)` — parâmetro do lab, com `energia=True` por omissão (os experimentos que medem `data.energy` não mudam); ⚠ com `energia=False` o `data.energy` fica a zeros **em silêncio**.
- Mecanismo antigo (workaround de medição/legado, foi o usado na campanha B antes de o parâmetro existir): `model.opt.enableflags &= ~int(mujoco.mjtEnableBit.mjENBL_ENERGY)`.
- Leitura: a flag de energia é o **único** bloqueio dos modelos do lab no MJX; o Warp nativo não se importa. O MJX-JAX monta o modelo do Spot mas não aloca o lote — por isso **MJWarp/MJX-Warp são o caminho para o Spot**, e o MJX-JAX fica limitado ao Crazyflie (e a modelos simples).

## 7. Paridade CPU f64 ↔ GPU f32 ✔ (1000 passos, dt 0,002, mesmo estado inicial e semente)
| Modelo · backend | max\|Δqpos\| t=0,5 s | t=1,0 s | t=2,0 s | max\|Δxpos\| |
|---|---|---|---|---|
| Spot · MJWarp | 5,85e-07 | 6,07e-07 | 2,23e-06 | 6,9e-07 m |
| Spot · MJX-JAX | 2,76e-05 | 8,30e-05 | 2,07e-04 | 3,9e-05 m |
| Crazyflie · MJWarp e MJX-JAX | 1,17e-08 | 1,58e-07 | 9,44e-07 | 9,5e-07 m |
- **Protocolo (para terceiros re-derivarem)**: Crazyflie — keyframe `hover` (qpos/qvel do keyframe) com `ctrl` do keyframe **+ 1 µN·m no canal y** (índice 2), sem ruído; Spot — keyframe `home` **+ 0,05 rad nos 12 servos**; 1000 passos de `dt = 0,002 s` iguais em todos os backends, leituras em t = 0,5 / 1,0 / 2,0 s. `xpos(base) == qpos[:3]` verificado (junta livre do tronco/CM): a divergência da junta livre é a da base.
- **Re-execução (2026-10-08, harness próprio com o protocolo acima, MJX em `JAX_PLATFORMS=cpu`)**: no Crazyflie, CPU f64 ↔ GPU f32 deu 1,53e-09 / 3,79e-09 / 1,22e-06 e **MJWarp ↔ MJX-JAX ≤ 1,16e-10** — a coincidência entre os dois backends float32 **confirma-se** (mesma ordem do 4,7e-10 da campanha). Explicação correta: **não** são «os mesmos kernels Warp» — o MJX-JAX corre em **XLA** (`impl=Impl.JAX`, confirmado por introspeção); é um resultado **observado nesta trajetória** (lisa, sem contato), em que as duas implementações float32 praticamente coincidem entre si e se afastam ambas do f64.
- Os valores da tabela são os da **campanha B**; os da re-execução não batem célula a célula porque o estado inicial exato da campanha não está persistido (ver «Lacunas honestas») — as ordens de grandeza coincidem.
- ⚠ É **um** estado inicial, não um envelope: serve para dizer que o float32 acompanha o f64 a curto prazo, não para garantir divergência máxima em treino longo.

## 8. VRAM/RAM @4096 mundos (pico) ✔
| Combinação | VRAM processo / dispositivo | RSS do processo |
|---|---|---|
| MJWarp · Spot | 2 136 MiB / 2 470 MiB | 836 MiB |
| MJWarp · Crazyflie | 276 MiB / 610 MiB | 466 MiB |
| MJX-JAX · Crazyflie | 792 MiB (pool 386) | 2 416 MiB |
| CPU `mujoco.rollout` · Spot | — | 424 MiB |
- Numa GPU de 8 GiB com o desktop KDE a usar 0,3–0,8 GiB: MJWarp no Spot é o caso mais pesado medido (2,5 GiB de dispositivo a 4096 mundos) — cabe, mas é o que aperta primeiro.

## 9. Comparação com os números oficiais
- **2,96 M e 2,33 M** vêm da tabela «Steps per Second (SPS) for MJX-Warp Graph Modes» de `docs/upstream/mujoco/doc/mjx.rst` (§ Graph Modes; commit upstream `ccd282b0`, 2026-02-19, via API do GitHub), linha **MJX-Warp** «JAX FFI (`WARP`)»: 2,96 M = **Humanoid**, 2,33 M = **Aloha Pot**. MJWarp puro: 3,35 M / 2,45 M; `WARP_STAGED` 2,67 M / 1,96 M. Hardware, `nworld` e versão **não declarados** (nem na doc nem no patch). O README do MJWarp mostra 2,73 M (humanoide, nworld 8192), também sem hardware. Nenhum é «MJX-JAX 2,33 M» (correção ao relatório do usuário: `relatorio-auditoria.md`).
- **Nesta GPU**: MJWarp 1,89–1,99 M e MJX-Warp 1,83–1,93 M a 4096 mundos ≈ 56–59 % do 3,35 M e 62–65 % do 2,96 M publicados; razão MJX-Warp/MJWarp ≈ 0,97 (doc: 0,88). **`mjwarp-testspeed` oficial** (humanoide do benchmark, nworld 8192, nconmax 24, njmax 64, 1000 passos): **1,76 M SPS** (JIT 2,2 s; 8192/8192 convergidos; memória 402 MiB: `Data` 305 + «Other» 97) = 53 % do 3,35 M, 60 % do 2,96 M e 65 % do 2,73 M do README.
- MJX-JAX: a doc dá 950 K (A100, batch 8192); aqui 31–82 K (≈ 3–9 %). O ganho MJWarp/MJX-JAX medido é 22× (JAX 6/6) a 59× (JAX 100/50) a 8192 mundos (NVIDIA: 152–475× em outras tarefas/GPUs: razões do fabricante, não comparáveis).
- ⚠ O humanoide do benchmark (`benchmarks/humanoid/humanoid.xml`) ≠ o do laboratório: sem tendões, `eulerdamp` off, `nconmax=24`, `njmax=64`, nworld 8192. Para comparar com a doc, rode-o com esses valores.

## 10. Recomendação para a RTX 4070 de 8 GB
1. Throughput: **MJWarp nativo** (PyTorch/NumPy) ou **MJX-Warp** (loop JAX/Playground). Razões **só dentro da mesma campanha**: Spot MJWarp 812 K vs CPU 290 K ≈ **2,8×**; Crazyflie MJWarp 2,94 M vs CPU 1,27 M ≈ **2,3×** (campanha B). No humanoide, o par comparável é GPU 1,89 M (campanha A) vs CPU re-medido ≈ 560 K (campanha B) ≈ **3,4×** — campanhas diferentes: ordem de grandeza, não número exacto. Use `nworld` ≈ 4096–16384 (VRAM 0,4–0,9 GB); acima de 32 K o ganho é nulo.
2. **MJX-JAX só se precisar de gradiente** (autodiff): no humanoide fica abaixo da CPU de 32 threads (≈ 87 K — 87,2 K medidos @4096 — vs ≈ 560 K re-medido) e exige baixar `iterations`/`ls_iterations` (6/6 estável; 1/4 dá NaN); **no Spot não corre de todo** (`RESOURCE_EXHAUSTED`, §6) e no Crazyflie dá 37–45 K. Para modelos simples (pêndulo, sem contato) supera a CPU a partir de ≈ 4096 mundos (8,5 M; 18,7 M a 16384).
3. JAX sempre com `XLA_PYTHON_CLIENT_PREALLOCATE=false` (+ `XLA_PYTHON_CLIENT_MEM_FRACTION=0.85`): o padrão reserva 5,9 GiB e deixa ~1,5 GB para Warp e desktop.
4. Modelos do laboratório: **MJWarp é o backend recomendado** (Spot 812 K; Crazyflie 2,94 M @4096); no Spot, dimensionar `njmax` com folga (⚠ NEFC, §5) e não tentar MJX-JAX. Custo de arranque: a compilação a frio do Warp/MJX é de dezenas de segundos por modelo/versão (só a 1ª vez).
5. Modelos minúsculos (pêndulo): GPU até ≈ **6,8×** a CPU a 16384 mundos (27,7 M vs 4,06 M SPS; só ≈ 1,5× a 1024 — campanha A). 4096 «carros» do relatório: o custo é o de um modelo de nv ≈ 12 (entre o pêndulo e o humanoide): cabe com folga; SPS do template `car` não medido.

## 11. Usar `gpu_bench.py` (`cwd` fora da raiz: o MuJoCo grava `MUJOCO_LOG.TXT`)
```bash
S=/home/ondokai/Projects/MuJoCo/.agents/mujoco-agent-skill/scripts/gpu_bench.py; H=/home/ondokai/Projects/MuJoCo/docs/upstream/mujoco/model/humanoid/humanoid.xml
cd "$TMPDIR" && /home/ondokai/Projects/MuJoCo/.venv-gpu/bin/python $S --backend warp --model $H --nworld 4096 --steps 50
/home/ondokai/Projects/MuJoCo/.venv-gpu/bin/python $S --backend mjx --impl warp --model $H --nworld 4096 --steps 50   # --impl jax [--iterations 6 --ls-iterations 6]
/home/ondokai/Projects/MuJoCo/.venv/bin/python $S --backend cpu --model $H --nworld 4096 --steps 50 --threads 32       # baseline: roda no .venv normal
```
Para os modelos do lab, o mesmo script com o XML do modelo (`models/boston_dynamics_spot/spot.xml`, `models/bitcraze_crazyflie_2/cf2.xml`) — mas para o Spot em MJX-JAX espere o `RESOURCE_EXHAUSTED` da §6.
Imprime SPS (mediana/mín/máx), VRAM (processo e dispositivo), saúde (NaN, overflow) e `RESULT_JSON`. Vigia: encerra (exit 3) se a VRAM livre < `--min-free-mib` (500). Rode **um** por vez e confira `nvidia-smi` antes.

## Armadilhas
| Sintoma | Causa | Correção |
|---|---|---|
| `Warp CUDA error 2: out of memory` já no 1º `put_data` ✔ | outro processo ocupava 7,3 GB (testes EGL de outro agente; contextos gráficos NÃO aparecem em `nvidia-smi --query-compute-apps`) | `nvidia-smi --query-gpu=memory.used --format=csv` antes; esperar |
| `NotImplementedError: mjtEnableBit.mjENBL_ENERGY` no `put_model` ✔ (MJX-JAX **e** MJX-Warp; Spot e Crazyflie) | `<flag energy="enable"/>` no modelo (o lab liga-a) | carregar com **`carregar(energia=False)`** (§6); workaround de medição/legado: limpar o bit em memória; o Warp nativo aceita a flag |
| `RESOURCE_EXHAUSTED` (6,33 GiB @256; 38,27 GiB @1024) no MJX-JAX com o Spot ✔ | lote do MJX-JAX com o modelo de malhas do Spot; invariante a `naconmax`/`njmax`/autotune | não usar MJX-JAX no Spot; usar MJWarp ou MJX-Warp |
| `Data.overflow` no Spot com `njmax=64` (4/4096 mundos, NEFC) ✔ | `njmax` subdimensionado para os contatos do Spot | `--nconmax 64 --njmax 256` → 0 overflow, −1,2 % SPS |
| `AssertionError: Leaf node ndim (2) … cdof_tri_col` ou BFC «ran out of memory» ao montar o lote do MJX-Warp ✔ | `tree.map(broadcast_to)` replicou também os buffers de contato (`_impl`, tamanho `naconmax`) | `jax.vmap(make_um)` partindo de `mjx.make_data(m, impl='warp', naconmax=nworld·nconmax, njmax=…)` |
| MJX-Warp 5,6× mais lento (150 K vs 850 K SPS a 1024 mundos) ✔ | loop Python de `jit(vmap(step))`: despacho e cópia dos buffers a cada passo | `lax.scan` dentro de um `jit` com `donate_argnums` (como o `gpu_bench.py`) |
| NaN em 986 de 1024 mundos (MJX-JAX) ✔ | `iterations=1, ls_iterations=4` (padrão do `mjx-testspeed`) é instável no humanoide | 6/6: estável, 86 K SPS |
| `Data.overflow != 0`, mas nada falhou ✔ | o bitmask inclui `ITERATIONS`/`LS_ITERATIONS` (solver no limite; 2904/4096 mundos com 10/20) | mascare esses bits; só NEFC/BROADPHASE/NARROWPHASE/CCD… são estouro (`decode_overflow`) |
| `AttributeError … 'GraphMode'` ✔ (Δ doc) | `mjx.rst` escreve `mjxw.GraphMode` | `mjxw.types.GraphMode.WARP_STAGED` |
| Centenas de linhas «Module … load» ✔ | log INFO do Warp | `wp.config.log_level = wp.LOG_WARNING` antes do 1º uso (`wp.config.quiet` não existe e é ignorado) |
| 1ª repetição ~2× mais lenta (0,077 s vs 0,038 s) ✔ | GPU em P8 (210 MHz) sobe com a carga | aquecer ≥ 1,5 s antes de cronometrar |
| 1ª execução de Warp demora (cache frio: 34 s no MJX-Warp 1.17.0; pêndulo: 28 s no setup) ✔ | NVRTC compila os kernels; cache em `~/.cache/warp/<versão>` | normal; só a 1ª vez por modelo/versão |
| Mundos idênticos, SPS irreal | `mjw.put_data` replica o mesmo estado | ruído por mundo (`gpu_bench.py` faz) |
| `XLA_FLAGS=--xla_gpu_triton_gemm_any=true` «+30 %» ✔ (Δ doc) | aqui: 86,1 K → 88,1 K (+2 %) | opcional |
| Baseline de CPU oscila 2× ✔ | load da máquina (outros agentes): 110 K com load 50 vs 250 K com load 6 | confira `uptime`; reporte o load |
| `XLA_PYTHON_CLIENT_MEM_FRACTION` ✔ | funciona no jaxlib 0.11.2 (pool = fração × 7834 MiB, sem aviso); o nome novo `XLA_CLIENT_MEM_FRACTION`: não verificado | usar o antigo |

## Lacunas honestas
- **Campanha B**: mínimo/máximo por célula não transcritos (tabelas dão a mediana de 5 repetições); threads do `rollout` não varridas (só 32 thr no vetorizado e 1 thr no `mj_step`); SPS MJX-JAX do Spot impossível de medir (OOM, §6); paridade medida num único estado inicial (não é envelope); VRAM do Spot em MJX-Warp não medida.
- **Os dados brutos da campanha B (JSON/CSV por medição) não estão persistidos no repositório** — ficaram no registo da sessão; as tabelas são a transcrição das medianas, e a paridade da §7 foi re-derivada por re-execução (protocolo documentado na própria §7).
- Não medidos (campanha A): VRAM do processo com a pré-alocação padrão do JAX (só o pool: 5876 MiB); MJX-Warp com pré-alocação (limite de OOM); tempo de compilação a frio do humanoide (só indicativo acima); modelos com malhas/CCD (agora parcialmente coberto pelo Spot na campanha B), Aloha e `car`; float64; `XLA_CLIENT_MEM_FRACTION`; `jax[cuda13]` com `warp-lang` 1.17.0.
