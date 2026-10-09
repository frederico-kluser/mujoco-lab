# Evolution Plan — Política neural sensor→motor com orçamento Raspberry Pi 5 na RUN

> **Sessão de pesquisa:** 2026-10 · **Estado:** investigação concluída, **nada implementado**.
> **Proveniência:** 3 relatórios de pesquisa web (via `tavily-agent-skill`, sem `--deep-research`) + conhecimento local verificado do laboratório (skill única `mujoco-lab-agent-skill` — memória CoALA + controle do MuJoCo) + **verificação adversarial** de 10 afirmações centrais (as correções dessa verificação estão já incorporadas neste documento).
> **Regra de leitura:** cada facto vem marcado como **[MEDIDO]** (executado/medido nesta máquina ou doc oficial local), **[EXT]** (fonte externa citada com URL) ou **[GUESS]** (estimativa por confirmar).

---

## 0. Enquadramento: RUN vs TREINO (crítico — ler primeiro)

O limite "poder de Raspberry Pi 5 (hardware + clock)" aplica-se **apenas na RUN** (deploy/inferência no device). O **treino corre a poder máximo** do computador.

| Fase | O que limita | O que **não** limita |
|---|---|---|
| **RUN** (Raspberry Pi 5, deploy) | Hardware e clock do RPi 5: arquitetura tem de **caber** (params/ops), export **int8**, shapes **fixos batch=1**, taxa de controlo viável, jitter do SO, térmica. **Toda a validação de timing/atraso/jitter acontece aqui.** | — |
| **TREINO** (PC: i9-14900HX 32 threads + RTX 4070 Laptop 8 GB) | Apenas o **encaixe** da arquitetura: a rede treinada tem de ser exportável para o orçamento RUN (params ≤100k, ops suportadas, quantização viável). | CPU/GPU/RAM, número de mundos em paralelo, precisão, duração, tamanho de batch de treino. |

**Consequências operacionais (sobrepõem-se a qualquer recomendação anterior):**

1. **Não** se emula latência, jitter nem atraso do RPi 5 como restrição de treino. Nada de "política a 25 Hz com buffer de 200 ms" a travar o loop de treino.
2. A validação de taxa/atraso/jitter passa para a fase de **RUN no device** (secção 3.6), depois de o modelo estar treinado e exportado.
3. Robustez a atraso é uma medida **opcional de deploy** (treino com injeção de atraso) — nunca um travão do treino; só se a RUN mostrar que o loop real precisa dela.
4. As restrições de encaixe que **permanecem** no treino: arquitetura (MLP pequena, ops simples), shapes estáticos, quantização int8 viável, e a observação/ação têm de corresponder exatamente ao que o device verá.

---

## 1. Objetivo

Construir uma **rede neural de controlo** para os robôs do laboratório em que:

- **Entradas** = leituras de **sensores** (IMU, encoders, touch, posição/velocidade);
- **Saídas** = **comandos de todos os motores** (Spot: 12 servos; Crazyflie: 4 canais de wrench);
- a rede tem de **caber e correr no Raspberry Pi 5** dentro do orçamento de hardware/clock (**na RUN**);
- o **treino** usa **todo o poder do PC** (CPU + GPU, MJX/MuJoCo Warp, muitos mundos em paralelo), sem simular as limitações do device;
- existe um **visualizador** para ver o robô e a política a atuar;
- o **treino é headless** (sem render 3D, para máxima velocidade) com **métricas do treino visíveis no terminal**, e a **evolução da política** observável por checkpoints (vídeo/curvas).

---

## 2. Arquitetura sensores→rede→motores

### 2.1 Spot — 12 servos `position`, 32 sensores

Configuração medida por execução nesta máquina: `nu=12, nactuator=12, nsensor=32, nq=19, dt=0,002 s (500 Hz), integrator=implicitfast` — [`lab/spot.py:57`](lab/spot.py#L57) `carregar()` (modelo Menagerie intocado + sensores via MjSpec).

| Grupo | Sensores | Unidades | Onde |
|---|---|---|---|
| IMU (site `imu` do tronco) | `gyro`, `accelerometer`, `framequat`, `velocimeter` | rad/s · m/s² · `[w x y z]` · m/s | [`lab/spot.py:87–95`](lab/spot.py#L87) |
| Força nos pés | `touch` ×4 | N — o site é a esfera exata do geom (r=0,036 m), senão o touch não apanha o contacto | [`spot.py:96–101`](lab/spot.py#L96) |
| Juntas | `jointpos` ×12, `jointvel` ×12 | rad · rad/s | [`spot.py:102–106`](lab/spot.py#L102) |
| Torques aplicados | `qfrc_actuator` ×12 | N·m | [`lab/spot.py:206`](lab/spot.py#L206) `ler_torques` |

**Motores:** 12 atuadores `<position>` (PD `kp=500, kv=40, inheritrange=1`); `ctrl` em **rad**, cortado aos limites da junta por `definir_alvo` ([`lab/spot.py:123`](lab/spot.py#L123)). Leitores prontos: `ler_imu` / `ler_juntas` / `ler_pes` / `ler_torques` / `ler_tudo` ([`spot.py:185–223`](lab/spot.py#L185)).

### 2.2 Crazyflie — 4 canais wrench, 5 sensores

Medido: `nu=4, nactuator=4, nsensor=5, nq=7, dt=0,002 s (500 Hz), integrator=RK4` — [`lab/crazyflie.py:64`](lab/crazyflie.py#L64).

| Grupo | Conteúdo | Unidades | Onde |
|---|---|---|---|
| Atuação (wrench no site do CM) | `body_thrust` + `x/y/z_moment` | N · N·m | [`lab/crazyflie.py:123–141`](lab/crazyflie.py#L123) |
| Mixer 4 rotores → wrench | `comandar_rotores` | N por rotor | [`lab/crazyflie.py:148`](lab/crazyflie.py#L148) |
| Sensores nativos (definidos no MJCF) | `body_gyro`, `body_linacc`, `body_quat` | rad/s · m/s² · quat | [`models/bitcraze_crazyflie_2/cf2.xml:124–128`](models/bitcraze_crazyflie_2/cf2.xml#L124) |
| Sensores adicionados (MjSpec) | posição, velocidade | m · m/s | [`crazyflie.py:103–106`](lab/crazyflie.py#L103) |

Leitores: `ler_imu` / `ler_estado` / `ler_motores` / `ler_tudo` ([`crazyflie.py:226–252`](lab/crazyflie.py#L226)).

### 2.3 Loop de controlo (comum aos dois robôs)

```text
        ┌──────────────── física 500 Hz (mj_step) ────────────────┐
        │  cada N passos (N = 5–10) → decisão da rede (50–100 Hz)  │
sensores ──► observação ──► MLP ──► ação ──► data.ctrl ──► mj_step ──► …
```

| Elemento | Regra verificada |
|---|---|
| **Observação** | `data.sensordata.copy()` (+ `qpos`/`qvel` + ação anterior). ⚠ **Após `mj_step`, os campos derivados (`sensordata`, `xpos`, contactos) são do estado ANTERIOR** → chamar `mj_forward` antes de ler (regra do lab, [`.agents/mujoco-lab-agent-skill/references/actuators-sensors.md:189`](.agents/mujoco-lab-agent-skill/references/actuators-sensors.md#L189)). Vistas NumPy invalidam-se a cada passo → `.copy()`. |
| **Ruído** | `noise=` no MJCF **não injeta ruído** (só guarda σ) — o ruído de sensor é responsabilidade do código ([`actuators-sensors.md:187`](.agents/mujoco-lab-agent-skill/references/actuators-sensors.md#L187)). |
| **Ação** | `data.ctrl` — `tanh` [-1,1] escalado ao `ctrlrange`/`gear` com `np.clip`. Ambos os robôs são de entrada única por atuador (12 `position`, 4 `motor`), logo `data.ctrl[:]` direto; para atuadores multi-entrada (`pid`/`dcmotor`/`orientation`) usar `actuator_ctrladr[i] : +actuator_ctrlnum[i]` ou `lab.mjkit.Ctrl`. |
| **Taxa** | Física `dt=0,002` (500 Hz); rede decide a **50–100 Hz** por decimation (`frame_skip=5–10`). O MuJoCo Playground infere políticas a 50 Hz via ONNX. |
| **Normalização** | Observações normalizadas para [-1,1]; `VecNormalize` (guardar as estatísticas para a avaliação e para o export). |

### 2.4 Arquitetura da rede (orçamento de encaixe)

| Parâmetro | Valor alvo | Razão |
|---|---|---|
| Tipo | MLP densa, 2 camadas ocultas | sem ops exóticas (LayerNorm/atenção) — tudo suportado por ONNX/TFLite |
| Largura | 64–128 unidades | custo de inferência e tamanho do export |
| Parâmetros | **10–30k** (teto **100k**) | orçamento RUN (secção 3) |
| Ativação de saída | `tanh` | ação contínua limitada |
| Entrada | vetor de observação normalizado, **shape fixo** | evita dynamic shapes no export |
| Batch | 1 | é controlo, não inferência em lote |
| Quantização | int8 (QAT no treino, se necessário) | aceleração real no A76 (SDOT) |

---

## 3. Orçamento Raspberry Pi 5 — **aplica-se na RUN**

### 3.1 Hardware

| Item | Valor | Fonte |
|---|---|---|
| SoC | Broadcom **BCM2712**, CPU **4× Cortex-A76 @ 2,4 GHz**, 512 KB L2/core + 2 MB L3 | [raspberrypi.com](https://www.raspberrypi.com/products/raspberry-pi-5) [EXT] |
| RAM | LPDDR4X-4267, 1–16 GB | product brief [EXT] |
| **NPU** | **Não existe** no SoC (só VideoCore VII GPU) | [EXT] |
| Addon AI | AI HAT+ = **Hailo-8L (13 TOPS)** / Hailo-8 (26 TOPS), PCIe Gen3 — **acelerador orientado a CNNs de visão**; documenta-se **rejeição de entradas 1D/vetoriais** e **ausência de exemplos densos/NLP**; **não é uma NPU para MLPs de controlo** (a Hailo descreve os aceleradores como "sem NPU cores", com mapeamento de camadas FC apenas dentro de CNNs) | [hailo.ai](https://hailo.ai/products/ai-accelerators/hailo-8l-ai-accelerator-for-ai-light-applications) · [community.hailo.ai/2158](https://community.hailo.ai/t/raspberry-pi-5-and-hailo-software/2158) · [18099](https://community.hailo.ai/t/raspberry-pi-ai-hat-disappointment/18099) [EXT] |
| Térmica | throttling a 80–85 °C, soft limit 85 °C, shutdown 90 °C; verificar `vcgencmd get_throttled` (0x0 = OK) e `measure_temp` | [fórum RPi](https://forums.raspberrypi.com/viewtopic.php?t=368073) [EXT] |
| Underclock (opcional) | `arm_freq=` em `/boot/firmware/config.txt` (+ `arm_freq_min`, governor `performance`) — usar para medir margem de clock | [fórum RPi](https://forums.raspberrypi.com/viewtopic.php?t=370344) · [Geerling](https://www.jeffgeerling.com/blog/2023/overclocking-and-underclocking-raspberry-pi-5) [EXT] |

**Conclusão:** a rede corre na **CPU**; o orçamento é de CPU (4× A76) e de jitter, não de NPU.

### 3.2 Jitter do SO e frequências viáveis

O inimigo do loop de controlo **não são os FLOPs, é o pico de latência do sistema operativo**:

| Cenário | Latência de pico | Fonte |
|---|---|---|
| Kernel padrão do RPi 5 | **8 450 µs (8,4 ms)** | [ohyaan](https://ohyaan.github.io/tips/real-time_robotics__building_and_configuring_a_preempt_rt_kernel_on_raspberry_pi_5) [EXT] |
| Kernel padrão, loop de 250 Hz, **sob stress** | **9,4 ms** (worst case) = **2,3×** o período de 4 ms do loop | [arXiv 2604.19275](https://arxiv.org/html/2604.19275v1) [EXT] |
| **PREEMPT_RT**, mesmo loop de 250 Hz, **sob stress** | **225 µs** (worst case) = **5,6 % do período** — o paper atribui este valor ao **PREEMPT_RT**, não ao kernel padrão; fórum relata até **800 µs** | [arXiv 2604.19275](https://arxiv.org/html/2604.19275v1) [EXT] |
| PREEMPT_RT, cyclictest sem carga | média 15 → **6 µs**, máximo → **28 µs** — este número é **UMA medição**, não o pico do SO | [ohyaan](https://ohyaan.github.io/tips/real-time_robotics__building_and_configuring_a_preempt_rt_kernel_on_raspberry_pi_5) [EXT] |

**Frequências viáveis (com o jitter como restrição):**

| Taxa de controlo | Viável? |
|---|---|
| **50–100 Hz** | Folgado em Python (ONNX Runtime/TFLite) — **alvo recomendado** |
| **500 Hz (2 ms)** | Ok em C++ (ORT/TFLite/ExecuTorch C API); arriscado em Python (GIL, GC, alocação) |
| **1 kHz** | Exige C++ **+** kernel PREEMPT_RT |

Planear pelo **pico (p99/max)**, nunca pela média. Python acrescenta jitter de ms; se a RUN exigir ≥500 Hz, o runtime tem de ser C++.

### 3.3 Frameworks de inferência (MLP densa, batch=1)

| Framework | Prós | Contras | Números citados |
|---|---|---|---|
| **ONNX Runtime** | export `torch.onnx` trivial; opset largo; kernels MLAS com SDOT int8 | mais pesado; overhead de `session.run` domina modelos minúsculos | YOLO no Pi5: **198/173 ms** (2/4 GB) [EXT] |
| **LiteRT / TFLite + XNNPACK** | backend CPU por omissão; micro-kernels NEON + **KleidiAI específicos para `fully connected`**; int8 maduro; C API leve | conversão desde PyTorch é a mais chata; ops exóticas falham | XNNPACK 0,613 s vs CPU-only 0,977 s (~1,6×) [EXT] |
| **ExecuTorch** | nativo PyTorch; `torch.export` → <300 Core ATen ops; backend XNNPACK; runtime C++ portátil; integra `torchao` | ecossistema mais novo, mais setup | [EXT] |
| **NCNN** | o mais rápido no benchmark Pi5 citado; NEON muito bom; binário pequeno | vem via ONNX (não de PyTorch direto) | **105/85 ms** (2/4 GB) [EXT] |
| PyTorch eager | zero fricção no treino | o mais lento no device (710/670 ms); runtime Python inteiro | [EXT] |
| TVM / microTVM | autotuning, gera C | microTVM é para **MCU/bare-metal**, não RPi 5 Linux | [EXT] |
| llama.cpp | ótimo para LLM | focado em transformer/GGUF — **ferramenta errada** para MLP densa | — |
| Hailo-8L | 13 TOPS | **visão (CNN)**, não MLP de controlo de baixa dimensão | [EXT] |

**Escolha prática:** exportar **ONNX** (fricção mínima a partir do PyTorch) e testar **ONNX Runtime** vs **TFLite/XNNPACK** no device; **NCNN** como alternativa se o benchmark no device o justificar.

### 3.4 Quantização

| Questão | Resposta verificada |
|---|---|
| int8 acelera no RPi 5? | **Sim, ~1,83×** (ResNet50V2, ONNX Runtime/MLAS: 144,95 → 79,08 ms) **porque o A76 tem a instrução `SDOT`** ([arXiv 2609.16085](https://arxiv.org/html/2609.16085v1) [EXT]). **Condição:** runtime com kernel SDOT — na mesma tabela, sem dot-product (Cortex-A53, i9) o int8 fica **1,65×/1,76× mais lento**. |
| fp16 acelera? | **Não** — mas é **limitação de software** (o PyTorch CPU não implementa matmul half: `addmm_impl_cpu_ not implemented for 'Half'`), **não** do hardware (o A76 implementa FP16 IEEE). fp16 serve para precisão/memória, não para velocidade. |
| Custo em qualidade | QuaRL ([arXiv 1910.01055v6](https://arxiv.org/html/1910.01055v6) [EXT]): int8 = **8,00 %** de perda em **PPO/Breakout** (fp32 400 → int8 368); fp16 = 0 % nesse jogo, mas **−5,2 % em SpaceInvaders**. O paper cobre também **DDPG (controlo contínuo, PyBullet)**; erro relativo médio global **2–5 %**. |
| Estratégia | **PTQ int8** para validar depressa → **QAT** (`torchao` / `torch.ao.quantization` / TFLite converter) para o modelo final. **Validar sempre a política quantizada no simulador** — benchmarks de RL quantizado são maioritariamente discretos. |
| FLOPs de referência | int8 SDOT GEMM **109 GOP/s** (48×48, 1 thread); fp32 NEON **29,8 GFLOP/s** (512, 1 thread) / 72,3 (4 threads); cross-check YOLOv8n ≈ **50 GFLOP/s efetivos** [EXT] |
| Estimativa da MLP | MLP ~20k params (20→128→128→4, ~39 kFLOPs): matemática pura ~1,3 µs fp32 / ~0,4 µs int8; **wall-clock [GUESS]: 20–200 µs em Python+ORT** (domina dispatch/alocação), **5–30 µs em C++ com buffers pré-alocados**. **Medir no device.** |

### 3.5 Pipeline RUN (do treino ao device)

1. **Fixar o orçamento antes do treino** (encaixe): params ≤100k (ideal 10–30k), batch=1, **shapes estáticos**, ≤2 ops não-lineares, latência-alvo ≤50 % do período de controlo; contar com `fvcore.nn.FlopCountAnalysis` (MACs ×2 = FLOPs) e/ou `thop`.
2. **Treinar** (poder máximo, secção 4) com QAT nas fases finais, se necessário.
3. **Exportar**: `torch.onnx.export(..., opset=17, dynamic_axes=None)` → shapes fixos.
4. **Validar no PC**: `onnx.checker` + ONNX Runtime vs PyTorch (**|Δ| < 1e-3** em fp32); conferir o grafo no **Netron** contra as ops suportadas pelo runtime alvo.
5. **Benchmark no device real**: latência **fim-a-fim** sensor→inferência→comando com `time.perf_counter_ns()`, ≥1000 iterações, reportar **p50/p99/max** (não a média), **com o robô a andar e IO ativo** (não em idle).
6. **Térmica**: `vcgencmd get_throttled` + `measure_temp` durante ≥10 min de carga; repetir com `arm_freq` reduzido (ex. 1 500 MHz) para medir margem.
7. **Se não couber**: destilação professor→aluno (KL sobre ações) e/ou reduzir para 1 camada oculta.

### 3.6 Atraso e robustez — **fase RUN, nunca restrição de treino**

| Precedente | O que é | Como usar aqui |
|---|---|---|
| **Buffer de atraso de 5 passos (200 ms a 25 Hz)** — [arXiv 2607.26434](https://arxiv.org/html/2607.26434v1) [EXT] | Buffer de **DEPLOYMENT** (ponte PD do MLP para o robô); o mesmo paper reporta 76 ms de transport delay com política a 50 Hz em simulação | Referência para o **runtime no device**; **não** é um modo de treino |
| **Injeção de atraso no treino** — [arXiv 2512.05964](https://arxiv.org/html/2512.05964v1) [EXT] | Delays amostrados 0–10 passos (até 200 ms a 50 Hz), π0.6, manipulação — política fica robusta a atraso | **Robustez OPCIONAL de deploy**: só ativar se a RUN mostrar que o loop real precisa; nunca como travão do treino |
| **"Real-Time Execution of Action Chunking Flow Policies"** — [arXiv 2506.07339](https://arxiv.org/html/2506.07339) [EXT] | Método de **INFERÊNCIA** ("without requiring re-training"), domínio VLA/manipulação — **não** é prova de treino com atraso | Não citar como receita de treino |

---

## 4. Treino a poder máximo (PC)

### 4.1 Ponto de partida em CPU — Stable-Baselines3 (PPO)

| Elemento | Recomendação | Nota |
|---|---|---|
| Algoritmo | **PPO** com `MlpPolicy` | PPO com MLP é **CPU-bound**: as docs dizem "PPO is meant to be run primarily on the CPU, especially when you are not using a CNN" — forçar GPU atrapalha |
| Env | `gymnasium.Env` próprio sobre [`lab/spot.py`](lab/spot.py#L57) / [`lab/crazyflie.py`](lab/crazyflie.py#L64) | `reset` → `mj_resetData`/keyframe; `step` → N × `mj_step`; obs/ação conforme secção 2.3 |
| Vetorização | `SubprocVecEnv` **quando o env for computacionalmente pesado**; `n_envs` ≤ núcleos lógicos; envs baratos → `DummyVecEnv` | docs SB3 |
| Normalização | `VecNormalize(norm_obs, norm_reward)` — **guardar as estatísticas** | reutilizar na avaliação e no export |
| Logging | `verbose=1` já imprime `rollout/ep_rew_mean`, `rollout/ep_len_mean`, `time/fps`, `train/*`; logger custom `configure(path, ["stdout","csv","json"])` | JSONL/CSV por rollout para as curvas |

Alternativas: **CleanRL** (`ppo_continuous_action.py`, single-file), **skrl** (modular, PyTorch/JAX/Warp), TorchRL (low-level), rl_games (colado a Isaac), dm_control (não é lib de RL — só envs).

### 4.2 Escala em GPU — MJX / MuJoCo Warp

| Aspeto | Estado |
|---|---|
| Stack | `mujoco_playground` (PPO brax + SAC + RSL-RL, 50+ envs) sobre **MJX (JAX)** ou **MuJoCo Warp** |
| Requisitos | **Python 3.10+** (README) / `>=3.11` (pyproject) — o "3.12" é só o quickstart; `jax[cuda12]`; `jax.default_backend() == 'gpu'` |
| Precisão | **float32** (MJWarp "utilizes floats in contrast to MuJoCo's default double"; XLA GPU é single precision) — pequenas forças/fricções divergem |
| Limites MJX | `max_contact_points`/`max_geom_pairs` obrigatórios; **sem warm-start**; exceção em features não suportadas; jit/CUDA-graph compila no 1º passo |
| Números do Playground (RTX 4090, batch 8192) [EXT] | PPO: 718k SPS (CartpoleBalance), 417k (Go1JoystickFlatTerrain), 106k (G1), 30k (BerkeleyHumanoidRough); SAC ~31k; Franka reach 95 % de sucesso em <3 min com 4096 envs MJX |
| **Números locais** [MEDIDO] | **Humanoide** (campanha A): MJWarp ≈1,89 M SPS @4096, MJX-Warp 1,83 M, MJX-JAX 27–87 K, CPU re-medida ≈560 K @4096/32 thr → ≈**3,4×** (campanhas diferentes: ordem de grandeza, não número exato). **Modelos do lab** (campanha B, @4096): Spot — CPU 290 K, MJWarp **812 K** (`njmax=256`; 802 K), MJX-Warp 705 K; Crazyflie — CPU 1,27 M, MJWarp **2,94 M**, MJX-Warp 2,34 M, MJX-JAX 37–45 K. No Spot o MJX-JAX **não corre** (`RESOURCE_EXHAUSTED`) |
| VRAM [MEDIDO] | MJWarp ≈195 MiB + 47 KiB/mundo; MJX-Warp 285 + 67; MJX-JAX 195 + 256; platô de SPS em 4096 mundos (0,4–0,9 GB) |
| Warp vs JAX [EXT] | O mantenedor do Playground mede **1,5–2×** mais throughput com Warp nos envs de manipulação ("many of the Playground manipulation environments have 1.5-2x higher throughput with Warp", [discussions/197](https://github.com/google-deepmind/mujoco_playground/discussions/197)); a NVIDIA anuncia 252×/475× vs MJX numa RTX PRO 6000 ([`gpu-mjx-warp.md:169`](.agents/mujoco-lab-agent-skill/references/gpu-mjx-warp.md#L169)) — razões do fabricante, hardware diferente, não comparáveis |
| Recomendação local | **MJWarp/MJX-Warp** a `nworld` 4096–16384; **MJX-JAX só se precisar de gradiente** |

### 4.3 Headless — desligar o render 3D para máxima velocidade

| Regra | Detalhe |
|---|---|
| `mj_step`/`mj_forward` **não criam contexto gráfico** | Confirmado por execução com `MUJOCO_GL=disable`; a doc oficial só exige contexto "before calling any of its `mjr_` rendering routines" (`doc/python.rst:427`) |
| **Nunca** criar `mujoco.Renderer` nem `mujoco.viewer` dentro do treino | O viewer tem loop próprio e bloqueia; o replay vai para script separado |
| `mjkit.record` **sem** `mp4`/`gif`/`sheet` **não cria Renderer** | Só simula — caminho headless já pronto no lab ([`.agents/mujoco-lab-agent-skill/references/rendering-viewer.md:131`](.agents/mujoco-lab-agent-skill/references/rendering-viewer.md#L131)); métricas via `probes=`/`on_step` |
| ⚠ `MUJOCO_GL` **é lido no import** do mujoco | `MUJOCO_GL=osmesa` **quebra o `import mujoco`** nesta máquina mesmo sem renderizar (falta libOSMesa); valor inválido → `RuntimeError` no import (`.venv/lib/python3.13/site-packages/mujoco/rendering/classic/gl_context.py:24,33–35`; o `mujoco/gl_context.py` é apenas um shim de 21 linhas). No treino usar `MUJOCO_GL=egl` (padrão validado do lab) ou não mexer na variável |
| Custo evitado | render offscreen ≈**0,4 ms** (320×240) e ≈**1,4 ms** (640×480 / 1280×720) por quadro [MEDIDO] ([`rendering-viewer.md:91`](.agents/mujoco-lab-agent-skill/references/rendering-viewer.md#L91)) vs ≈**58 µs** de `mj_step` de humanoide → renderizar no treino seria 7–24× o passo de física |
| Armadilha | `render_mode="rgb_array"` no env de treino cria contexto GL e mata a velocidade sem avisar |

### 4.4 Métricas do treino no terminal

| Ferramenta | Uso |
|---|---|
| **`rich.Live`** | painel (`Table`) com reward médio, loss, FPS, ep_len, KL/entropia, atualizado a ~4 Hz; `live.console.print` para logs acima do painel |
| `asciichartpy` / `plotext` | curvas ASCII dentro do painel / gráfico tipo matplotlib no terminal (`textual_plotext` para TUI) |
| **JSONL/CSV por rollout** | registo durável para as curvas depois (`on_rollout_end` → dict → painel + linha JSONL) |
| TensorBoard sem browser | serve só para escrever; ler scalars com `EventAccumulator` (ou `--load_fast=false` quando o RustBoard falha) |
| W&B | `wandb offline` durante o treino → `wandb sync` no fim |
| SB3 nativo | `verbose=1` + `tqdm` via `model.learn(progress_bar=True)` |

### 4.5 Evolução e checkpoints

| Item | Como |
|---|---|
| Checkpoints | `CheckpointCallback(save_freq, save_path)` |
| Melhor política | `EvalCallback(eval_env, eval_freq, best_model_save_path, deterministic=True)` — **estado inicial fixo** nos evals (só assim a diferença medida é a política) |
| Paragem | `StopTrainingOnNoModelImprovement` / `StopTrainingOnRewardThreshold` (via `callback_after_eval`) |
| Reprodutibilidade | seeds fixas (`seed=` em SB3; `PRNGKey` em JAX); mesma versão de MuJoCo e mesma arquitetura para replays |
| Curvas | JSONL/CSV → matplotlib (`Agg`, headless) ou plotext |

---

## 5. Visualizador e evolução

### 5.1 `view.py` — processo separado que lê checkpoints

- Corre em **processo separado** do treino; lê o checkpoint mais recente por **polling de mtime** (ou `watchdog`) — custo zero no treino (padrão de engenharia nossa, sem receita oficial).
- `mujoco.viewer.launch_passive(model, data, key_callback=…)` + `handle.sync()` por iteração + `with handle.lock():` em volta do `mj_step` — **confirmado por introspeção no 3.15** ([`rendering-viewer.md:190`](.agents/mujoco-lab-agent-skill/references/rendering-viewer.md#L190)). `sync()` é o **único** ponto que lê/escreve `m`/`d`; sem ele a janela congela. `sync(state_only=True)` é mais rápido mas ignora mudanças no `MjModel`; `launch()` bloqueia e é dono da física — não misturar com o loop próprio.
- **HUD**: `set_texts` (sensores, ações, retorno). **Curvas na janela**: `set_figures` + `MjvFigure` (**100 linhas × 1001 pontos** — `mjMAXLINE=100`, `mjMAXLINEPNT=1001`, confirmado em `mjvisualize.h:26–27`). `set_images` para câmaras.
- **Interação**: `key_callback` para pausa/passo.
- **Ambiente**: Wayland nativo funciona (avisos `libdecor-gtk.so` e `OpenGL error 0x502` são benignos); XWayland só com `PYGLFW_LIBRARY_VARIANT=x11`; **sem `DISPLAY` o viewer encerra o processo sem exceção**; MuJoCo Studio nativo não abre em Wayland.

### 5.2 Ver a evolução da política

1. **Rollout determinístico por checkpoint, do MESMO estado inicial** → `ckpt_000500.mp4`, `ckpt_001000.mp4`, … com `MUJOCO_GL=egl` (definido **antes** de `import mujoco`).
2. **Tira comparativa**: `ffmpeg -i a.mp4 -i b.mp4 -i c.mp4 -i d.mp4 -filter_complex "xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0" out.mp4` (ou `grid=2x2`, ffmpeg ≥4.3); GIF animado = 1–2 s por checkpoint no mesmo instante.
3. **Curvas + vídeo**: retorno/episódio vs step (TB/W&B) com o vídeo do checkpoint no mesmo step.
4. **Replay**: gravar `qpos` (`+qvel`, `act`, `ctrl`) em JSONL e reproduzir escrevendo o estado + `mj_forward` + `sync()` — replay visual/cinemático. Re-simulação **determinística** exige o estado de integração completo (incl. warmstart) e a mesma versão/arquitetura.
5. **MJX/Brax**: converter params JAX→NumPy no processo do viewer e **re-simular 1 env em CPU com `mj_step`** (nunca tentar ver o env vetorizado); `rscope` faz isto para o Playground.

### 5.3 Ferramentas complementares

| Ferramenta | O que dá | Custo |
|---|---|---|
| **Netron** | grafo estático da rede (ONNX): ops, shapes — valida o export | trivial (`pip install netron`) |
| **Rerun** | poses/geoms 3D, imagens, séries, live ou replay `.rrd` | **não instalado** (~400 MB de deps); `rr.log` ≈**56 µs**/chamada (medido) → decimar 30–100 Hz ou `send_columns` (10k linhas = 3,9 ms); ingestão pausa com janela escondida (issue #7427); sem exemplo oficial MuJoCo |
| **PlotJuggler** | séries temporais ao vivo por UDP/WS/MQTT — o melhor para "curvas" | baixo; não vê o robô |
| TensorBoard / W&B | escalares, histogramas de pesos, vídeo por step | baixo |
| `mjkit.plot` / `probes` | métricas e gráficos sem instalar nada | já no lab |

### 5.4 Armadilhas do visualizador e do render offscreen

- `MUJOCO_GL=egl` **e** `PYOPENGL_PLATFORM=egl` **antes** de importar mujoco; conflito → `ImportError` engolido e `mujoco.Renderer` "desaparece"; contexto preso à thread que criou o `Renderer`; resolução ≤ `offwidth/offheight` (640×480 por omissão); OSMesa quebrado nesta máquina.
- Vídeo offscreen e `video_size` do ffmpeg têm de coincidir; `macro_block_size=2` para yuv420p.
- Após `mj_step`, HUD/telemetria mentem se não se chamar `mj_forward` antes de ler (1 passo de atraso).
- ⚠ Exceção conhecida do lab (3.15): atuadores multi-entrada (`pid`, `dcmotor`, `orientation`) — os acessores nomeados usam o ID do atuador e gravam no **slot errado** quando `nu ≠ nactuator`; usar `actuator_ctrladr`/`lab.mjkit.Ctrl`. (Não afeta Spot/Crazyflie atuais.)

---

## 6. Escala GPU e armadilhas verificadas — checklist

- [x] **Errata do `gpu-benchmarks.md` registada** (2026-10-08): o ficheiro foi reescrito em campanhas — a **§4** (campanha A, modelos upstream) mantém 202 K @1024 e ≈1,89 M @4096, e a **§10** explica que o par comparável no humanoide é GPU 1,89 M (campanha A) vs CPU re-medido ≈560 K (campanha B) ≈ **3,4×**, campanhas diferentes (ordem de grandeza, não número exato). As referências antigas "≈0,25 M" e "7–8×" **já não existem** no ficheiro (a errata está registada lá). Verificado por adversarial (5 PASS/1 FAIL) e reparado: células `t = 1,0 s` preenchidas (8,30e-05 e 1,58e-07), protocolo de paridade documentado; a lacuna «dados brutos não persistidos» está declarada no próprio ficheiro.
- [x] **SPS medidos para o Spot e o Crazyflie** (campanha B, §5 do `gpu-benchmarks.md`): CPU 32 thr @4096 — Spot 290 K / Crazyflie 1,27 M; MJWarp nativo — Spot **812 K** (`njmax=256`) / Crazyflie **2,94 M**; MJX-Warp — 705 K / 2,34 M; MJX-JAX — Spot **não corre** (`RESOURCE_EXHAUSTED`, §6), Crazyflie 37–45 K. ⚠ No Spot, dimensionar `njmax` com folga (`njmax=64`: 4 de 4096 mundos com overflow NEFC).
- [x] **Flag de energia tornada condicional** (2026-10-08): `energia: bool = True` em [`lab/spot.py:58`](lab/spot.py#L58) e [`lab/crazyflie.py:65`](lab/crazyflie.py#L65), com `if energia:` em [`spot.py:76`](lab/spot.py#L76) e [`crazyflie.py:85`](lab/crazyflie.py#L85) — o default CPU fica inalterado (`data.energy` continua a funcionar nos experimentos) e `energia=False` prepara o modelo para o MJX. **Provado por execução**: `mjx.put_model` passa com `energia=False` (§6 do `gpu-benchmarks.md`); **6 testes de regressão** novos (suíte 29 passed) e aviso nas docstrings de que `data.energy` fica a zeros em silêncio com `energia=False`.
- [x] **Perigo do plugin `mujoco.pid` documentado** (2026-10-08): matriz **atuadores × backend** em [`gpu-mjx-warp.md` §2.1](.agents/mujoco-lab-agent-skill/references/gpu-mjx-warp.md#L56) (re-verificada por 2 verificadores) + nota **PERIGO** com medição (C `[0,1275 …]` vs MJX-JAX `[112,56 …]`, max|Δ| ≈ 1,1e2): o `mjx.put_model` **aceita sem erro** e o resultado é lixo silencioso. Pré-checagem obrigatória antes de treinar: `(m.actuator_plugin != -1).any()` ou `parity()`.
- [x] **Paridade CPU float64 ↔ GPU float32 medida** (§7 do `gpu-benchmarks.md`: 1000 passos, dt 0,002, mesmo estado inicial e semente): Spot MJWarp **≤2,23e-06** / MJX-JAX **≤2,07e-04**; Crazyflie **≤9,44e-07** em 2 s. Resta a verificação fina da cena do Spot em condições extremas (malhas `.obj`, cone elíptico, `impratio=100`); em MJWarp a cena corre desde que `njmax` seja dimensionado com folga (§5) — o MJX exige `max_contact_points`/`max_geom_pairs`, não faz warm-start e levanta exceção com features não suportadas.
- [x] **Requisitos do Playground documentados** (2026-10-08): **≥3.11** ([`robots.md:41`](.agents/mujoco-lab-agent-skill/references/robots.md#L41); `pyproject.toml:12`) — o README diz "Requires Python 3.10 or later" ([README:35](docs/upstream/mujoco_playground/README.md#L35)) e o `--python 3.12` do quickstart ([README:39](docs/upstream/mujoco_playground/README.md#L39)) é sugestão de venv, não requisito; GPU exige `jax[cuda12]` ([README:41](docs/upstream/mujoco_playground/README.md#L41)).
- [ ] **Dependências por instalar nos venvs** (ABERTO, 2026-10-08): `.venv` tem mujoco 3.15.0 + numpy 2.5.3 e **não tem** gymnasium, rerun-sdk, dm_control, torch, sklearn, onnxruntime nem `rich`; `.venv-gpu` tem mujoco/mujoco-mjx/mujoco-warp 3.15.0 + warp-lang 1.18.0 + jax/jaxlib 0.11.2 (sem torch). Instalar por grupo do `pyproject.toml` quando começar a implementação (`rl`, `viz`, `gpu`).
- [x] **Atuadores suportados por backend documentados** (2026-10-08): matriz em [`gpu-mjx-warp.md` §2.1](.agents/mujoco-lab-agent-skill/references/gpu-mjx-warp.md#L56) — MJX-JAX aceita `position` (gain FIXED, bias AFFINE; caso do Spot) e rejeita `pid`/`dcmotor`/`orientation`; Warp aceita `motor`/`dcmotor` (caso do Crazyflie) e rejeita `pid`/`orientation`; `put_model` OK com os dois modelos do lab (com `energia=False`).
- [x] **VRAM/RAM medidos @4096 mundos** (§8 do `gpu-benchmarks.md`, 2026-10-08): MJWarp — Spot **2 136 MiB** de processo, Crazyflie **276**; MJX-JAX — Crazyflie 792; RSS vários registados. Envs maiores que o humanoide continuam a exigir medição caso a caso.
- [ ] **Causa do OOM do MJX-JAX no Spot não isolada** (ABERTO): `RESOURCE_EXHAUSTED` a partir de 256 mundos (6,33 GiB @256; 38,27 GiB @1024), **invariante** a `naconmax`/`njmax`/autotune — declarado em §6/§8 do `gpu-benchmarks.md`; para o Spot usar MJWarp/MJX-Warp.
- [ ] **Validar Rerun** (ABERTO: `.rrd` gravado e lido de volta, mas o **viewer nunca foi aberto**; 0 usos em `lab/` e `experiments/`; não instalado, ~400 MB) antes de contar com ele.
- [ ] **Medir o ganho real treino com/sem render** (ABERTO) em loop state-based com `time.perf_counter` — o 1,5–10× citado é `GUESS`.
- [ ] **Mín/máx por célula dos benchmarks não transcritos** (ABERTO): as células registam a mediana de 5; os extremos não ficaram persistidos (lacuna «dados brutos não persistidos» declarada no `gpu-benchmarks.md`).
- [x] **Curvas de referência revistas** (2026-10-08): estado atual em [`robots.md` §1.2](.agents/mujoco-lab-agent-skill/references/robots.md#L34) — `dm_control`/`labmaze` → venv 3.12 (`:39`), Playground **≥3.11** (`:41`), `mjlab` fixa `mujoco~=3.11` (`:44`), grupos opcionais e `mujoco-menagerie` fora deles (`:47`). Re-verificar quando as versões mudarem.

---

## 7. Estado de verificação

| **[MEDIDO]** — executado / doc oficial local | **[EXT]** — externo, citado (URL nas secções/fontes) | **[GUESS]** — estimativa por confirmar |
|---|---|---|
| Sensores/atuadores e contagens do Spot (`nu=12, nsensor=32`) e Crazyflie (`nu=4, nsensor=5`), `dt=0,002`; atraso de 1 passo da `sensordata`; `noise=` não injeta ruído; `mjkit.record` sem mp4/gif não cria Renderer; EGL funciona aqui e `osmesa` quebra o import; API do viewer (`launch_passive`, `sync`, `lock`, `set_texts`, `set_figures`, `MjvFigure` 100×1001); SPS locais (humanoide MJWarp ≈1,89 M @4096; Spot 812 K / Crazyflie 2,94 M na campanha B); VRAM MJWarp ≈195 MiB + 47 KiB/mundo; introspeção `mjx.put_model`/`mjw.put_model`; paridade f64↔f32 | Specs e térmica do RPi 5; sem NPU; jitter 8,4–9,4 ms (padrão) e ≈225 µs (PREEMPT_RT sob stress); int8 1,83× via SDOT; QuaRL 2–5 % (8 % PPO/Breakout, inclui DDPG contínuo); frameworks de inferência e latências YOLO; precedentes de delay (2607.26434 deployment; 2512.05964 treino; 2506.07339 inferência); docs SB3 (PPO CPU, vec_envs, callbacks); números do Playground em RTX 4090 | Latência wall-clock de uma MLP de 10–30k params no RPi 5 em Python+ORT (20–200 µs) e em C++ (5–30 µs); perda de recompensa de uma **política contínua quantizada**; ganho exato treino com/sem render; `nworld` máximo em 8 GB para envs maiores; latência de pico do ORT sob carga concorrente no RPi 5 |

**Verificação adversarial (sessão 2026-10):** das 10 afirmações centrais, **2 PASS limpos**, **7 PASS parciais com correções** (já aplicadas neste documento) e **1 FAIL claro** (baseline CPU comparado a 1024 vs 4096 mundos). Correções-chave incorporadas: Hailo reformulado ("acelerador de visão", não "nunca executa MLPs"); jitter PREEMPT_RT dado como intervalo (225 µs medidos sob stress, relatos até 800 µs; 28 µs é uma medição de cyclictest); fp16 como limitação de stack; âmbito do QuaRL; buffer de 5 passos como deployment; `MUJOCO_GL` lido no import; modelos do lab e `mjENBL_ENERGY`; requisitos do Playground.

---

## 8. Fontes

**Web (principais):**

- Raspberry Pi 5 — <https://www.raspberrypi.com/products/raspberry-pi-5> · product brief: <https://pip.raspberrypi.com/documents/RP-008348-DS-raspberry-pi-5-product-brief.pdf>
- Hailo-8L / AI HAT+: <https://hailo.ai/products/ai-accelerators/hailo-8l-ai-accelerator-for-ai-light-applications> · <https://community.hailo.ai/t/what-can-be-done-with-hailo-8l/4371> · <https://community.hailo.ai/t/raspberry-pi-5-and-hailo-software/2158> · <https://community.hailo.ai/t/raspberry-pi-ai-hat-disappointment/18099>
- Térmica/underclock RPi 5: <https://forums.raspberrypi.com/viewtopic.php?t=368073> · <https://forums.raspberrypi.com/viewtopic.php?t=370344> · <https://www.jeffgeerling.com/blog/2023/overclocking-and-underclocking-raspberry-pi-5>
- Jitter / PREEMPT_RT: <https://ohyaan.github.io/tips/real-time_robotics__building_and_configuring_a_preempt_rt_kernel_on_raspberry_pi_5> · <https://arxiv.org/html/2604.19275v1>
- int8 no A76 (SDOT): <https://arxiv.org/html/2609.16085v1> · kernels: <https://github.com/n4hy/OptimizedKernelsForRaspberryPi5_NvidiaCUDA>
- Frameworks no Pi 5 (YOLO): <https://community.ultralytics.com/t/raspberry-pi-new-cheaper-raspberry-pi-released/208> · XNNPACK: <https://software-dl.ti.com/processor-sdk-linux/esd/AM62X/11_00_09_04/exports/docs/linux/Foundational_Components/Machine_Learning/tflite.html>
- ExecuTorch: <https://docs.pytorch.org/executorch/stable/intro-how-it-works.html> · ORT compatibilidade: <https://onnxruntime.ai/docs/reference/compatibility.html>
- Quantização em RL (QuaRL): <https://arxiv.org/html/1910.01055v6> · <https://zishenwan.github.io/publication/SysML2020.pdf>
- Delay/robustez: <https://arxiv.org/html/2607.26434v1> · <https://arxiv.org/html/2512.05964v1> · <https://arxiv.org/html/2506.07339> · destilação: <https://arxiv.org/html/2503.08299v1>
- Contagem FLOPs: <https://cvnote.ddlee.cc/2019/09/04/thop-pytorch-mac-flop-counter.html> · export ONNX: <https://jacks.se/blog/onnx-the-standard-that-actually-stuck>
- MuJoCo headless/render: <https://mujoco.readthedocs.io/en/stable/python.html> · MJX: <https://mujoco.readthedocs.io/en/stable/mjx.html> · MJWarp: <https://mujoco.readthedocs.io/en/3.5.0/mjwarp>
- MuJoCo Playground: <https://github.com/google-deepmind/mujoco_playground> · discussion: <https://github.com/google-deepmind/mujoco_playground/discussions/197> · issue MUJOCO_GL: <https://github.com/google-deepmind/mujoco/issues/1203>
- Comparação de libs RL: <https://isaac-sim.github.io/IsaacLab/main/source/overview/reinforcement-learning/rl_frameworks.html>
- SB3: <https://stable-baselines3.readthedocs.io/en/master/common/logger.html> · <https://stable-baselines3.readthedocs.io/en/master/guide/vec_envs.html> · <https://stable-baselines3.readthedocs.io/en/master/guide/callbacks.html>
- Terminal: <https://rich.readthedocs.io/en/latest/live.html> · <https://docs.cleanrl.dev/rl-algorithms/ppo> · <https://skrl.readthedocs.io/en/latest/intro/examples.html> · TensorBoard: <https://github.com/tensorflow/tensorboard/issues/4784>
- Visualização: <https://rerun.io/docs/overview/what-is-rerun> · <https://rerun.io/docs/howto/logging-and-ingestion/optimize-chunks> · <https://github.com/rerun-io/rerun/issues/7427> · <https://github.com/Reimagine-Robotics/rerun-loader-mjcf> · <https://github.com/Andrew-Luo1/rscope> · <https://github.com/lutzroeder/netron> · <https://github.com/PlotJuggler/plotjuggler> · <https://ottverse.com/stack-videos-horizontally-vertically-grid-with-ffmpeg> · gymnasium RecordVideo: <https://gymnasium.farama.org/introduction/record_agent> · W&B Video: <https://docs.wandb.ai/models/ref/python/data-types/video>

**Locais (com linha):**

- [`lab/spot.py:57`](lab/spot.py#L57) `carregar()` (`:58` parâmetro `energia`, `:76` `if energia:`) · `:85` `_adiciona_sensores` (`:87–95` IMU, `:96–101` touch, `:102–106` juntas) · `:123` `definir_alvo` · `:185–223` leitores (`ler_torques` em `:206`)
- [`lab/crazyflie.py:64`](lab/crazyflie.py#L64) `carregar()` (`:65` parâmetro `energia`, `:85` `if energia:`) · `:99–106` `_adiciona_sensores` (posição/velocidade) · `:123–141` comandos de wrench · `:148` mixer · `:226–252` leitores — sensores nativos definidos no MJCF: [`models/bitcraze_crazyflie_2/cf2.xml:124–128`](models/bitcraze_crazyflie_2/cf2.xml#L124)
- [`.agents/mujoco-lab-agent-skill/references/gpu-benchmarks.md`](.agents/mujoco-lab-agent-skill/references/gpu-benchmarks.md) — citado **por secção** (mais estável do que linhas, o ficheiro é reescrito): §4 campanha A · §5 campanha B (modelos do lab) · §6 `put_model`/flag de energia · §7 paridade f64↔f32 · §8 VRAM · §10 recomendação · §11 `gpu_bench.py` · «Armadilhas» · «Lacunas honestas»
- [`.agents/mujoco-lab-agent-skill/references/gpu-mjx-warp.md:37,41,43,169`](.agents/mujoco-lab-agent-skill/references/gpu-mjx-warp.md#L37) (precisão/float32, plugins ignorados em silêncio, atuadores novos do 3.15, razões do fabricante)
- [`.agents/mujoco-lab-agent-skill/references/rendering-viewer.md:91,131,190`](.agents/mujoco-lab-agent-skill/references/rendering-viewer.md#L91) (custos de render, `record` sem Renderer, `launch_passive`)
- [`.agents/mujoco-lab-agent-skill/references/telemetry-rerun.md:12,91,108`](.agents/mujoco-lab-agent-skill/references/telemetry-rerun.md#L12) (Rerun: custo e estado)
- [`.agents/mujoco-lab-agent-skill/references/actuators-sensors.md:26,187,189`](.agents/mujoco-lab-agent-skill/references/actuators-sensors.md#L187) (semântica de `ctrl` :26 · `noise=` não injeta ruído :187 · atraso de 1 passo :189)
- [`.agents/mujoco-lab-agent-skill/references/robots.md:34–56`](.agents/mujoco-lab-agent-skill/references/robots.md#L34) (ecossistema RL)
- [`.agents/mujoco-lab-agent-skill/references/experiments-playbook.md:14–23`](.agents/mujoco-lab-agent-skill/references/experiments-playbook.md#L14) (método do lab: critério numérico + exit code)
- [`pyproject.toml:19–30`](pyproject.toml#L19) (grupos `viz`/`urdf`/`rl`/`dmc`/`gpu`)
- Memória CoALA: `python3 .agents/mujoco-lab-agent-skill/scripts/coala.py recall "<tarefa>" --budget 1500` (não há entradas sobre RPi 5 nem sobre treino de política — terreno virgem)

---

## 9. Próximos passos (só lista — nada implementado)

1. **Env gymnasium** sobre [`lab/spot.py`](lab/spot.py#L57) e/ou [`lab/crazyflie.py`](lab/crazyflie.py#L64): observação (sensores + ação anterior), ação (`ctrl` via `tanh`), decimation 50–100 Hz, `mj_forward` antes de ler.
2. **Completar a linha de base**: custo de `mj_step` e custo da política (forward PyTorch, batch=1) no PC — os SPS do Spot/Crazyflie já estão medidos (campanha B, §5 do `gpu-benchmarks.md`).
3. **Treino PPO headless** (SB3 + `SubprocVecEnv` + `VecNormalize`) com painel `rich` + JSONL por rollout; nunca criar `Renderer`/viewer no treino.
4. **`view.py`** em processo separado (checkpoints por polling) + `EvalCallback` com estado inicial fixo + vídeo por checkpoint (`MUJOCO_GL=egl`) e grelha `xstack`.
5. **Escala GPU** (MJX / MuJoCo Warp via `mujoco_playground`) quando a CPU saturar: usar `energia=False` no caminho GPU (a flag já é condicional), tirar partido da paridade f64↔f32 já medida (§7 do `gpu-benchmarks.md`) e escolher o backend por modelo — **MJWarp/MJX-Warp para o Spot**, MJX-JAX só para o Crazyflie (e ainda assim o mais lento).
6. **Export int8** (ONNX/QAT) + validação (`onnx.checker`, ORT vs PyTorch) e **benchmark fim-a-fim no Raspberry Pi 5** (p50/p99/max, sob carga, com verificação térmica).
7. **Registar na memória CoALA** o que for durável (decisões, medições, o `Evolution-Plan.md` como referência do projeto).
