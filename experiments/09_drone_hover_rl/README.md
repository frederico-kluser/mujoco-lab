# 09 · Crazyflie 2 (Bitcraze) — hover a 1 m por RL (PPO → ONNX → deploy)

Política de **aprendizagem por reforço** que faz o quadricóptero **Crazyflie 2** da Bitcraze subir do
chão e estabilizar a **1 m**. Usa o modelo **pronto** do
[mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/main/bitcraze_crazyflie_2)
vendorizado em `models/bitcraze_crazyflie_2/` (MIT, **intocado**) com a camada de sensores/controles
`lab/crazyflie.py`. Aqui junta-se tudo o que um projeto do laboratório precisa: **ambiente Gymnasium**,
**treino PPO**, **UI web local**, **viewer com HUD da rede** e o **caminho de deploy** (ONNX →
validação numérica → benchmark → multi-IA).

O simulador é **sempre físico**: o drone arranca **pousado no chão, com os motores desligados**, e sobe
por empuxo comandado — sem teleporte, sem cinemática, sem corpo congelado. O `reset` larga-o a 1 dm do
chão (keyframe `hover` do lab) e deixa a **física** assentá-lo antes do episódio começar.

**Estado atual (v2b, 2026-10-08):** depois da primeira campanha (hover simples), o dono pediu mais:
o drone **para de girar**, fica **preso em (x, y, z) = (0, 0, 1) m com a orientação fixa** (yaw = 0) e
**corrige sob vento** — vento esse que é escolhido **pela interface** (força + direção). Isso mudou a
recompensa (`v2b`), acrescentou vento físico ao ambiente e um currículo de *domain randomization* ao
treino. Resumo em [Vento e orientação fixa](#vento-e-orientação-fixa-v2b) e
[Resultados v2b](#resultados-v2b-verificado).

- `env.py` — o **ambiente** (contrato que as outras peças importam).
- `train.py` · `view.py` · `dashboard.py` · `net_probe.py` · `deploy.py` — treino, visualização, UI, sonda
  da rede e deploy.
- `run.py` — validação do ambiente por **fórmulas fechadas**, 121/121 checagens, exit 0/1.

## Como correr

```bash
uv sync --group hover-rl                                   # stable-baselines3 + torch (CPU) + onnx/onnxruntime + rich/plotext

# 1) validar o ambiente (não treina nada): 121 checagens, exit 0
uv run --group hover-rl python experiments/09_drone_hover_rl/run.py

# 2) treinar (headless, ~11,5 min por seed nesta máquina, n_envs 4)
uv run --group hover-rl python experiments/09_drone_hover_rl/train.py \
    --timesteps 1000000 --n-envs 4 --seed 0 --sem-painel \
    --out-dir experiments/09_drone_hover_rl/out/runs/seed0

# 2b) receita v2b que passou o critério (fine-tune com vento em currículo, ~5 min)
uv run --group hover-rl python experiments/09_drone_hover_rl/train.py \
    --retomar experiments/09_drone_hover_rl/out/runs/seed2/best_model.zip \
    --timesteps 1000000 --n-envs 8 --seed 2 --sem-painel \
    --curriculo-vento 0,1,2,3 --lr 1e-4 --ent-coef 0.005 \
    --out-dir experiments/09_drone_hover_rl/out/vento_r9_curr_lr1e4_seed2

# 2c) receita do CAMPEÃO (ronda 10): vento DINÂMICO em 3 fine-tunes encadeados (~11 min no total)
#     rajadas (1 M) → frente (600 k) → turbulência dryden (600 k); sempre com vento ativo no currículo
uv run --group hover-rl python experiments/09_drone_hover_rl/train.py \
    --retomar experiments/09_drone_hover_rl/out/vento_r9_polir_vento3/final.zip \
    --timesteps 1000000 --n-envs 8 --seed 0 --sem-painel --curriculo-vento 1,2,3 \
    --lr 1e-4 --ent-coef 0.005 --log-std-init -0.5 \
    --vento-dinamico rajadas --vento-dinamico-params '{"p": 0.02, "duracao": 10}' \
    --out-dir experiments/09_drone_hover_rl/out/vento_r10_ft_raj_1M
#   os dois passos seguintes repetem o comando com --retomar o best_model.zip da etapa anterior:
#     --vento-dinamico frente --vento-dinamico-params '{"t_s": 2.0}' --timesteps 600000     → out/vento_r10_ft_frente_600k
#     --vento-dinamico dryden --vento-dinamico-params '{"sigma": 0.5, "L": 10}' --timesteps 600000
#                                                                        → out/vento_r10_ft_dryden_600k  ← CAMPEÃO

# 3) ver a política: janela 3D + HUD (ESPAÇO pausa · Q/Esc fecha) ou o mesmo ciclo sem janela
uv run --group hover-rl python experiments/09_drone_hover_rl/view.py                 # melhor de out/runs/*/
uv run --group hover-rl python experiments/09_drone_hover_rl/view.py --sem-janela --passos 300
uv run --group hover-rl python experiments/09_drone_hover_rl/view.py \
    --model experiments/09_drone_hover_rl/out/vento_r9_polir_vento3/final.zip --rapido

# 3b) vento ao vivo no viewer (sem passar pela UI): ficheiro de controlo ou flag
uv run --group hover-rl python experiments/09_drone_hover_rl/view.py \
    --model experiments/09_drone_hover_rl/out/vento_r9_polir_vento3/final.zip --vento-inicial 2,90

# 3c) PADRÃO do laboratório (CoALA `padrao-simulacao-clean-site`): janela CLEAN + site com TODAS as
#     métricas e controlos, num só comando; sem auto-loop (o episódio espera pelo REINICIAR do site)
uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py --sem-browser
#     sem --model, usa a política da última validação com sucesso (hoje o campeão r10 — ver §Resultados)

# 4) UI web local ("clicar para treinar" + rede ao vivo + painel de VENTO) — stdlib, offline, anuncia o URL
uv run --group hover-rl python experiments/09_drone_hover_rl/dashboard.py --port 8765 --out "$TMPDIR/runs"
#    no painel "5 · Vento ao vivo": força (0–5 m/s), azimute (0–360°), elevação (−90..90) → APLICAR/PARAR

# 5) a rede a correr em JSONL (usada pela UI) e o pipeline de deploy
uv run --group hover-rl python experiments/09_drone_hover_rl/net_probe.py \
    --model experiments/09_drone_hover_rl/out/vento_r9_polir_vento3/final.zip \
    --out "$TMPDIR/net.jsonl" --interval 0.05 --vento-inicial 3,45
uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --model out/vento_r9_polir_vento3/final.zip
uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --int8 --skip-multi
uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --nproc 4 --duracao 10
```

Flags principais (todas as peças têm `--help`):

| peça | o que faz | flags que importam |
|---|---|---|
| `train.py` | PPO headless (SB3) sobre `HoverEnv`; grava `best_model.zip`, `final.zip`, `ckpt/`, `evaluations.npz` e `train_log.jsonl` (**13 campos** por avaliação) | `--timesteps` · `--n-envs` · `--seed` · `--out-dir` · `--sem-painel` · `--eval-freq` · `--sucesso` · `--lr` · `--ent-coef` · `--log-std-init` · **`--curriculo-vento`** · `--vento-max` · `--sem-curriculo` · **`--avanco-frac`** · **`--retomar`** · **`--vento-dinamico`** · **`--vento-dinamico-params`** |
| `view.py` | viewer **passivo** do MuJoCo + HUD ASCII de **8 linhas** (obs resumidas, ações + comando físico, z/alvo/dz/dxy, **yaw_err/ω_z**, vento, retorno) e **3 figuras** (z(t) com linha do alvo, yaw_err, ações) | `--model` · `--sem-janela` · `--passos` · `--segundos` · `--episodios` · `--rapido`/`--tempo-real` · `--alvo-z` · `--seed` · **`--controlo`** · **`--vento-inicial`** |
| `dashboard.py` | servidor HTTP local (só stdlib) que **nunca treina no processo**: faz `Popen`/`SIGTERM` do `train.py` e do `net_probe.py`; API JSON + página única embutida com **painel de vento** | `--host` · `--port` · `--out` · `--net-out` · `--vento-out` · `--train-py` · `--verboso` |
| `net_probe.py` | a MLP [16, 64, 64, 4] a correr, com *forward hooks* nas `nn.Linear`: 1 linha JSONL por instante (`obs`, `h1`, `h2`, `act`, `z`, `dist_xy`, `no_alvo`, **`yaw_err`, `vento_vel`, `vento_azim`**) | `--model` (obrigatório) · `--out` · `--interval` · `--alvo-z` · **`--controlo`** · **`--vento-inicial`** · **`--fator-tempo`** |
| `deploy.py` | exporta o gráfico da política para **ONNX**, valida-o contra o PyTorch, mede latência (proxy de 1 core) e corre N processos a 50 Hz | `--model` · `--int8` · `--nproc` · `--duracao` · `--pinned` · `--threads` · `--threads-contraste` · `--skip-multi` · `--out` |
| `run.py` | valida o **ambiente** (ação→`ctrl`, recompensa, física, obs, Gymnasium, contrato do modelo, **robustez**) em condições isoladas | sem argumentos (e sem `--help`): corre tudo e sai com 0/1 |

## Arquitetura

| ficheiro | papel | não faz |
|---|---|---|
| `env.py` | `HoverEnv`: física, observação, ação, recompensa v2b, vento (`opt.wind`), terminação, `reset` com jitter e assentamento | treino, viewer, ONNX, render |
| `train.py` | PPO `MlpPolicy` MLP [64, 64] tanh, `SubprocVecEnv` com `Monitor`, currículo de vento (DR), avaliação e *checkpoints*; `--retomar` para fine-tune | tocar no `env.py`, abrir browser |
| `view.py` | viewer passivo + HUD ASCII de 8 linhas, 3 figuras (`launch_passive`, 50 Hz), vento ao vivo por ficheiro | treinar |
| `dashboard.py` | UI web local: botão treinar/parar, curvas, rede ao vivo, **painel de vento**, cauda do stdout | treinar no processo do servidor |
| `net_probe.py` | sonda da rede em JSONL (hooks nos `nn.Linear`) + vento ao vivo | render, rede, viewer |
| `deploy.py` | ONNX → validação → benchmark → int8 → multi-IA → relatório JSON | tocar nas outras peças |
| `run.py` | validação por fórmulas fechadas + robustez (exit 0/1) | treinar |

### Observação (16,) — já normalizada por escalas fixas

`Box(-inf, inf, (16,))`, float32. **Não há `VecNormalize`** (decisão de design): a observação sai
normalizada do ambiente, logo o gráfico ONNX do deploy fica **puro** — sem estatísticas de corrida
agarradas ao wrapper.

| índice | conteúdo | escala |
|---|---|---|
| `[0:3]` | `p − p_alvo` (`p` = sensor `posicao`, o **CM do corpo**; `p_alvo = [0, 0, alvo_z]`) | ÷ 1 m |
| `[3:6]` | `roll, pitch, yaw` do sensor `body_quat` (quaternion MuJoCo `[w x y z]`, ZYX intrínseco) | ÷ π |
| `[6:9]` | velocidade no **frame do corpo** (`R(quat)ᵀ · v_mundo`) | ÷ 1 m·s⁻¹ |
| `[9:12]` | velocidade angular do sensor `body_gyro` (frame do corpo) | ÷ 10 rad·s⁻¹ |
| `[12:16]` | **ação anterior** | já em `[-1, 1]` |

`ruido_obs > 0` soma ruído gaussiano σ = `ruido_obs` (treino com ruído de sensor); o padrão é 0.

### Ação (4,) — centrada no hover

`Box(-1, 1, (4,))` = `[empuxo, momento x, momento y, momento z]`, com **a = 0 igual ao hover** (não é uma
faixa de empuxo de 0 a máximo: a metade da caixa acima e abaixo do hover é assimétrica de propósito):

```
a₀ ≤ 0:  empuxo  = mg · (1 + a₀)                        (a₀ = −1 → 0 N; a₀ = 0 → mg)
a₀ > 0:  empuxo  = mg + (thrust_max − mg) · a₀          (a₀ = +1 → thrust_max)
momentos_i = tau_escala · momento_max_i · a_i           (tau_escala = 0,1 → 10 % da autoridade máxima)
```

Tudo cortado às faixas físicas dos canais. `data.ctrl` fica em **unidades físicas, 1:1** com os 4 canais
(`nu = nactuator = 4`): `[0]` empuxo em N, `[1:4]` momentos em N·m. O `cf2.xml` em disco **nunca é
tocado** — a faixa do empuxo e o gear dos momentos são ajustados só na cópia em memória do ambiente.

`thrust_realista=True` (padrão) usa `thrust_max = 0,589 N` (4 × 15 gf do datasheet CF2.1 → **T/W ≈ 2,22**)
em vez dos `0,35 N` do modelo do menagerie, que o próprio README classifica de *"arbitrary and need to be
further tuned"* (T/W = 1,32). Com o valor do upstream o drone mal sai do chão;
`thrust_realista=False` reproduz esse caso e é o que a checagem 1 do `run.py` cobre.

Faixas dos momentos (geometria dos rotores, `lab/crazyflie.py`): braço 0,0325 m, `T_rotor_max = 0,0875 N`
→ `momento_max = (5,69e-3, 5,69e-3, 2,80e-3) N·m` (roll, pitch, yaw).

### Recompensa v2b — fixação de posição **e** orientação (2026-10-08)

Por passo de **decisão**. A v1 era a equação **literal** do MuJoCo-Drones-Gym ([arXiv 2606.08039],
preprint); a v2b mantém a estrutura e ajusta os pesos depois de a campanha de re-treino ter mostrado um
**atrator de *chatter*** nos momentos (ver [Lição da campanha](#lição-da-campanha-r1r9)):

```
r = −1,0·‖xy‖ − 1,0·|z − alvo_z| − 0,2·|yaw_err| − 0,05·‖v‖ − 0,05·‖ω_xy‖
    − 0,1·|ω_z| − 0,05·‖Δa‖
    + 1,0 · 𝟙[ ‖xy‖ < 0,05 ∧ |z − alvo_z| < 0,05 ∧ |yaw_err| < 0,10 ]     (bónus "no alvo", 5 cm / 0,1 rad)
    − 100 · 𝟙[ terminou ]
```

- `‖xy‖ = √(x² + y²)` — **prender o drone no mesmo ponto** (peso 1,0, dez vezes a v1);
- `yaw_err` = yaw (ZYX do `body_quat` `[w x y z]`) **envolvido em [−π, π]**, alvo **0 rad** — é o
  "não girar" / "apontar sempre para o mesmo lado" (peso 0,2);
- `ω_xy` = 2 primeiros componentes da velocidade angular no corpo; `|ω_z|` com peso **0,1** (freio do giro);
- `Δa` = ação atual − ação anterior (**0,05**): penalidade de *taxa de ação*, o remédio padrão para
  *chatter*;
- o bónus é **estrito** nos três limiares (0,05 m / 0,05 m / 0,10 rad) e a terminação vale **−100** exatos.

Episódio de **10 s = 500 passos de decisão** (truncagem — truncar **não** é terminar). Terminação:
`z < 0,005 m` (caiu — o piso impede `z < 0`), `max(|φ|, |θ|) > π/2` (capotou) ou `z > 3 m` (subiu demais).

### Vento e orientação fixa (v2b)

O vento é **físico**: o `cf2.xml` já traz `density="1.225"` / `viscosity="1.8e-5"`, logo o **arrasto aerodinâmico por inércia**
já existe; o que faltava era o **vento**. Ele entra como o mecanismo oficial do MuJoCo — o vetor
**velocidade do ar** (`model.opt.wind`, frame mundo, m/s) subtraído à velocidade do corpo no cálculo do
fluido. É física a sério (`mj_step`), não uma força somada à mão; o chão é estático e imune.

| API | unidades | notas |
|---|---|---|
| `HoverEnv(vento=(vx, vy, vz))` | **cartesiano** (m/s) | vetor mundo fixo no episódio |
| `HoverEnv(vento_aleatorio=(u_min, u_max))` | m/s | **domain randomization**: por episódio, norma U[u_min, u_max], azimute U[0, 360°), elevação U[−20°, +20°]; semeado por `np_random` (reprodutível com a seed) |
| `definir_vento(vel, azimute_graus, elevacao_graus=0)` | **polar** | `vel` em m/s; reescreve `opt.wind` **já** (o episódio em curso sente logo) |
| `definir_vento_aleatorio(u_min, u_max)` | m/s | muda o teto do DR (usado pelo currículo do treino) |

Guardas: valores não finitos (NaN/inf) → `ValueError` com mensagem clara; ação não finita → `ValueError`
sem corromper o estado; divergência numérica → `RuntimeError` (com a explicação de que um `reset()`
sozinho não chega se a causa for o vento absurdo — usar `definir_vento` com valor são).

Magnitudes de referência para o Crazyflie 2 (m = 27 g, W = 0,265 N): a 3 m/s o arrasto inercial vale
≈10 % do peso; a 5 m/s ≈29 %; o CF2 real começa a perder posição por volta de **3 m/s**. O envelope
validado desta política é **≤3 m/s sustentado** (ver resultados).

### Vento dinâmico (r10) — rajadas · frente · turbulência

O vento por episódio (`vento`/`vento_aleatorio`) só muda **entre** episódios. A ronda 10 acrescentou
`vento_dinamico=dict`, que faz o vento mudar **dentro** do episódio, a cada passo de decisão (50 Hz),
sempre pelo mesmo mecanismo físico (`opt.wind`). A config é validada por `env.valida_vento_dinamico()`
(modos, chaves e faixas; erro claro) e o treino expõe-na por `--vento-dinamico` +
`--vento-dinamico-params '<json>'` — **só os envs de TREINO** a recebem (a avaliação fica no contrato v2b):

| modo | chaves (default) | o que faz a cada passo de decisão |
|---|---|---|
| `rajadas` | `p` 0,02 · `duracao` 10 passos (0,2 s) · `u_max` 3,0 m/s | com probabilidade `p` sorteia uma rajada (norma U[0, `u_max`], azimute novo, elevação ±20°) que **soma** ao vento base durante `duracao` passos; uma rajada em curso não é interrompida por outra |
| `frente` | `t_s` 2,0 s · `u_max` 3,0 m/s | no instante `t_s` chega uma **frente** — norma U[0,5 m/s, `u_max`], azimute novo — que **substitui** o vento base até ao fim do episódio (degrau dentro do passo, sem transiente artificial; `t_s = 0` = frente logo no 1.º passo e `t_s` tem de cair dentro do episódio) |
| `dryden` | `sigma` 0,5 · `L` 10,0 · `u_max` 3,0 m/s | **turbulência** OU de 1.ª ordem (filtro de Dryden discreto por passo): o vento passeia em torno do base, saturado em ±`u_max` |

`u_max` é o teto do **modo** (o teto do vento por episódio continua a ser o do currículo/`--vento-max`), e
**`u_max = 0` é inerte**: sem rajadas, sem frente e sem turbulência — e, importante, **não consome
`np_random`**, logo um estágio sem vento é indistinguível do contrato v2b (era a guarda que faltava aos
modos não-`rajadas`). O `info["vento_atual"]` passou a reportar o vetor **em vigor** (base + dinâmica).
Estes modos são do **treino/avaliação**: no site os sliders aplicam vento **constante em tempo real**
(`INTERFACE.md` §3.5).

### Vento pela interface (dashboard + viewer + sonda)

O ficheiro `experiments/09_drone_hover_rl/out/controle_vento.json`
(`{"vel", "azimute", "elevacao", "ativo", "t"}`) é o contrato comum:

- **`dashboard.py`** — painel **«5 · Vento ao vivo»**: sliders de força (0–5 m/s), azimute (0–360°) e
  elevação (−90..90) + botões **APLICAR VENTO**/**PARAR VENTO** e atalhos ±x/±y; `POST /api/vento`
  (400 fora de faixa/não numérico) escreve o ficheiro **atomicamente** (`tmp` + `os.replace`);
  `GET /api/vento` devolve o estado;
- **`net_probe.py`** — vigia o ficheiro a **cada passo de decisão** (gate por `mtime_ns`+tamanho) e chama
  `definir_vento`; a linha JSONL ganha `yaw_err`, `vento_vel`, `vento_azim`;
- **`view.py`** — lê o mesmo ficheiro a cada ~5 passos e mostra o vento no HUD (o modo janela é para o
  dono usar; `--vento-inicial v,az[,elev]` dispensa o ficheiro).

`--fator-tempo` na sonda: `0` = sem travão (≈28–30× o tempo real, medido), `1` = tempo real (a "rede ao
vivo" deixa de ser um borrão), `2` = 2× — a UI usa 1×.

### Decimação e física

`dt = 0,002 s` (**500 Hz**, integrador **RK4**) × `decimation = 10` → **50 Hz** de decisão (0,02 s por
`step()`). Um passo de política são 10 passos de física; `data.time` avança exatamente 0,02 s por
`step()` (checagem 6 do `run.py`).

### `reset` — sem teleporte

`mj_resetDataKeyframe` (keyframe `hover` do lab, `z = 0,1 m`) + `ctrl = 0` (**motores desligados**;
o keyframe do lab traz `ctrl = peso`, aqui é zerado), jitter determinístico `xy ± 2 cm` e `yaw ± 5°`,
e **assentamento físico**: a queda de ~9 cm até ao chão corre em `mj_step` até 10 passos consecutivos
com `z < 5 cm` e `‖v‖ < 1 mm/s` (teto de 1 s). O drone começa o episódio **pousado** (z ≈ 0,0125 m).

Com vento, o assentamento corre **em ar parado** (`opt.wind = 0`) e o vento do episódio entra **logo
depois** — decisão de desenho: o estado inicial é sempre uma pose pousada estável, e a política tem de
**descolar e recuperar** contra o vento que chega (é isso que o treino com DR ensina).

## Resultados medidos

Máquina: **i9-14900HX** (32 threads), CachyOS x86-64, Python 3.13.15, MuJoCo 3.15.0, torch 2.14.1+cpu,
Stable-Baselines3 2.9.0, gymnasium 1.4.0, onnx 1.23.2, onnxruntime 1.30.0, numpy 2.5.3.

### Treino — 3 seeds × 1 M passos (3 em paralelo, `loadavg` 17,81 no arranque)

Receita: PPO `MlpPolicy` MLP **[64, 64] tanh** · `lr 3e-4` · `n_steps 1024` · `batch 256` · `n_epochs 10`
· `gamma 0,99` · `gae_lambda 0,95` · `clip 0,2` · `ent_coef 0,01` · `vf_coef 0,5` · `max_grad_norm 0,5` ·
`n_envs 4` · `torch.set_num_threads(1)` · **sem VecNormalize**.

| seed | passos | avaliações | `mean_ret` final | `std_ret` | `mean_z` [m] | `dist_xy` [m] | no alvo | melhor `mean_ret` | passos/s | parede |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1 003 520 | 50 | **413,8** | 20,4 | 0,975 | 0,027 | 85,1 % | 431,4 | 1 454 | 690 s |
| 1 | 1 003 520 | 50 | **398,1** | 42,6 | 0,970 | 0,028 | 87,8 % | 431,6 | 1 446 | 693 s |
| 2 | 1 003 520 | 50 | **443,6** | 0,5 | 0,964 | 0,005 | 92,8 % | **444,4** | 1 461 | 684 s |

≈ **1 450 passos/s por seed** com as 3 em paralelo (12 processos de ambiente) → **1 M ≈ 11,5 min**.
O teto teórico de retorno é ≈ 500 (hover perfeito: bónus +1 por passo, penalidades ~0); o seed 2 fica a
`std_ret = 0,5` do seu próprio ótimo local.

⚠ Esta tabela é a corrida **v1** (recompensa original, sem vento). Os **defaults atuais** do `train.py` são
os da fase v2b — `n_envs 8`, `n_steps 512`, `lr 1e-4`, `ent_coef 0,001`, `log_std_init −0,5`,
`optimizer_kwargs weight_decay 1e-4` e `--curriculo-vento 0,1,2,3` — e a escala de `mean_ret` mudou
(v2b: ≈350 no hover perfeito, não ≈500). Ver [Resultados v2b](#resultados-v2b-verificado).

### Rollouts dos `best_model` (política determinística, 3 rollouts × 500 passos por seed)

Métrica calculada nos **últimos 5 s** (250 passos) de cada rollout; nenhum rollout terminou antes do fim.

| seed | z médio [m] | \|z − 1\| médio [m] | no alvo | terminações | passos | retorno |
|---|---|---|---|---|---|---|
| 0 | 1,011 | 0,011 | 100 % | **0** | 500/500 | 428,6 |
| 1 | 0,997 | 0,004 | 100 % | **0** | 500/500 | 435,4 |
| 2 | 0,999 | 0,001 | 100 % | **0** | 500/500 | 444,3 |

Duas medições independentes concordam dentro de ≈1,5 mm. **Critério do experimento cumprido 3/3**:
`z ≥ 0,90 m` ∧ `|z − 1| ≤ 0,10 m` (pior caso medido ≤ 1,2 cm, ~8× melhor que o limite) ∧ `no_alvo ≥ 0,5`
∧ **zero quedas**. Os `final.zip` também passam (`z` 0,994–1,011 m, 0 terminações), mas com
`no_alvo` 81–100 % — o `best_model` é visivelmente mais estável em regime.

### Resultados v2b (verificado)

**Política final: `out/vento_r9_polir_vento3/final.zip`** (sha256 `f8af4a05…`), treinada **com vento**
(U[0, 3] m/s, azimute aleatório) por fine-tune de 500 k passos a `lr 5e-5`, `ent 0` — 175 s, 2 743
passos/s. O envelope validado é **≤3 m/s sustentado**.

Grelha do critério — vento {0, 1, 2, 3} m/s × azimute {0°, 90°, 180°, 270°}, médias de **3 seeds** de
reset, métricas nos **últimos 5 s** de um rollout determinístico de 10 s:

| u (m/s) | azimutes | \|z − 1\| [m] | ‖xy‖ [m] | \|yaw_err\| [rad] | \|ω_z\| [rad/s] | terminações | veredicto |
|---|---|---|---|---|---|---|---|
| 0 | 0/90/180/270 | 0,0059 | 0,0048 | 0,0129 | 0,0001 | 0 | **PASS ×4** |
| 1 | 0 / 90 / 180 / 270 | 0,0056–0,0061 | 0,0083–0,0176 | 0,0111–0,0146 | ≤0,0001 | 0 | **PASS ×4** |
| 2 | 0 / 90 / 180 / 270 | 0,0045–0,0065 | 0,0454–0,0561 | 0,0057–0,0199 | ≤0,0001 | 0 | **PASS ×4** |
| 3 | 0 / 90 / 180 / 270 | 0,0023–0,0067 | 0,1013–0,1194 | 0,0028–0,0283 | ≤0,0003 | 0 | **PASS ×4** |

Limites do critério: `|z − 1| ≤ 0,05 m` · `‖xy‖ ≤ 0,10 m` (**≤0,15 m** a 3 m/s) · `|yaw_err| ≤ 0,10 rad` ·
`|ω_z| ≤ 0,30 rad/s` · **0 terminações**. Resultado: **16/16 PASS (100 %)** — as **12** condições ≤2 m/s
passam todas, e as 4 de 3 m/s também (o critério exigia no mínimo todas as ≤2 m/s e ≥14/16). Todos os rollouts correm **500/500 passos** (nunca
terminam antes do fim).

Confirmações independentes (agente de fecho, avaliador próprio, seeds 7001–7003 e 32 condições densas
com 0,5/1,5/2,5 × 8 azimutes + 3,0 × 8 azimutes): **16/16 PASS** e **32/32 PASS**, **0 terminações**,
métricas a bater ao 4.º decimal com a tabela acima. O treinador reporta ainda **56/56** na sua grelha densa
(7 velocidades × 8 azimutes × 3 seeds: 0 · 0,5 · 1 · 1,5 · 2 · 2,5 · 3 m/s), com os mesmos piores valores.

**Anti-*chatter*** (vento 2 m/s, medido): `|a|` médio por canal = **0,009–0,025** (≈**1,6 % da
autoridade**; máximos 0,12–0,25 nos momentos) e `‖Δa‖` médio = **0,0088**. A campanha falhada usava
74–90 % de autoridade em *chatter* de Nyquist (ver abaixo) — a diferença é o que separa "pairar 10 s" de
"capotar aos 1,3 s".

Outros números do run final (`out/vento_r9_polir_vento3/train_log.jsonl`, 13 campos): `mean_ret 350,0` ·
`mean_z 0,920` · `mean_dist_xy 0,0057` · `frac_no_alvo 0,802` · `mean_yaw_err 0,035` · `u_vento 3,0` a
2,16 M passos acumulados.

### Ronda 10 — vento dinâmico: campeão verificado

**Política final: `out/vento_r10_ft_dryden_600k/best_model.zip`** (sha256 `a72d381c…`), obtida por **3
fine-tunes encadeados** a partir da v2b (sempre com vento ATIVO no estágio — polir sem vento degrada, ver
a lição abaixo), trocando a dinâmica em cada etapa: rajadas → frente → dryden.

| run | pasta | dinâmica de treino | passos | wall | passos/s | melhor retorno |
|---|---|---|---|---|---|---|
| R1 | `out/vento_r10_ft_raj_1M` | `rajadas` p=0,02 d=10 | +1 003 520 | 307 s | 3 266 | 391,4 |
| R2a | `out/vento_r10_ft_frente_600k` | `frente` t_s=2,0 | +602 112 | 173 s | 3 486 | 399,5 |
| R2b | **`out/vento_r10_ft_dryden_600k`** | `dryden` σ=0,5 L=10 | +602 112 | 177 s | 3 400 | **408,7** |
| R3 (descartado) | `out/vento_r10_ft_raj_dur_250k` | `rajadas` p=0,05 d=25 | +253 952 | 78 s | 3 253 | 405,1 |

Todas com `--curriculo-vento 1,2,3 --lr 1e-4 --ent-coef 0.005 --log-std-init -0.5 --n-envs 8 --seed 0
--sem-painel` e `--retomar` do `best_model.zip` da etapa anterior (o currículo subiu 1→2→3 m/s nas duas
primeiras avaliações de cada run). O treino corre **só no terminal** (`--sem-painel`).

**Critério do dono — 57/57 PASS, 0 terminações.** 19 condições (16 constantes {0,1,2,3} m/s × {0,90,180,
270}° + 3 dinâmicas) × 3 seeds; a tabela é o **pior das 3 seeds**, últimos 5 s de um rollout
determinístico de 10 s:

| condição | ‖xy‖ sempre [m] | ‖xy‖ 5 s [m] | \|z−1\| 5 s [m] | \|yaw_err\| 5 s [rad] | \|ω_z\| 5 s [rad/s] | terminações |
|---|---|---|---|---|---|---|
| 0 m/s @4 azimutes | 0,018 | 0,007 | 0,001 | 0,012 | 0,000 | 0 |
| 1 m/s @4 azimutes | 0,015–0,022 | 0,005–0,016 | 0,001 | 0,011–0,013 | 0,000 | 0 |
| 2 m/s @4 azimutes | 0,039–0,056 | 0,034–0,046 | 0,000–0,001 | 0,009–0,015 | 0,000 | 0 |
| 3 m/s @4 azimutes | 0,084–0,108 | 0,084–0,096 | 0,000–0,002 | 0,005–0,020 | 0,000–0,001 | 0 |
| rajadas p=0,02 d=10 u≤3 | 0,046 | 0,008 | 0,001 | 0,012 | 0,007 | 0 |
| frente t_s=2 s u∈[0,5;3] | 0,074 | 0,073 | 0,002 | 0,006 | 0,000 | 0 |
| dryden σ=0,5 L=10 u≤3 | 0,018 | 0,008 | 0,011 | 0,011 | 0,001 | 0 |

Limites: sobe a 0,9–1,1 m em ≤4 s · ‖xy‖ ≤0,30 **sempre** · ‖xy‖ média ≤0,10 (≤0,15 a 3 m/s) · `|z−1|`
≤0,05 · `|yaw_err|` ≤0,15 · `|ω_z|` ≤0,30 nos últimos 5 s · **0 terminações**. O drone **sobe em 47–52
passos (0,94–1,04 s)**, entra na faixa [0,95, 1,05] em 59–66 passos e fica lá: a partir do 2.º segundo
`z ≥ 0,92 m` sempre, com `z` mínimo de TODO o episódio = 0,015 m (é o repouso no chão do 1.º passo, com os
motores desligados — o `reset` não teleporta). No pior caso a 3 m/s fica em 0,084–0,096 m de ‖xy‖, **abaixo
do limite estrito de 0,10** (não só do 0,15).

**Stress mais duro que o critério** (grelha densa 4 velocidades × 8 azimutes × 3 seeds + 24 dinâmicas
duras + 24 sequências vento+dinâmica): **144/144** — o único dos 4 candidatos **sem nenhuma falha**. Os
outros 3 fazem 143/144 (a falha única é `dryden σ=1,5` — 3× a σ de treino — com `|z−1|` = 0,055–0,059 m
>0,05 na média dos 5 s finais; nunca há queda, terminação nem deriva).

Escolha do campeão feita com os dados (§4 do relatório): maior margem no pior caso do stress (0,048 m de
`dz` contra 0,055–0,059 dos restantes), melhor rejeição das dinâmicas e o melhor retorno de treino (408,7).

Relatório completo: `out/RELATORIO_r10_vento_dinamico.md`; veredictos em JSON:
`out/avaliacao_vento/r10_*.json` (`r10_campeao.json` = 57/57, `r10_campeao_stress.json` = 144/144).

> **Honestidade dos dados:** `--sucesso 450` (paragem por retorno) **nunca dispara** com a recompensa v2/v2b
> — ela penaliza guinada e esforço, e o retorno satura abaixo disso; todas as runs terminam por **orçamento
> esgotado**. O `best_model` é escolhido pelo retorno médio do `EvalCallback` **sem vento**; por isso a
> certificação de robustez ao vento é o avaliador independente (§ acima), **não** o `train_log.jsonl`.
> Fora do envelope (>3 m/s constantes) não foi testado.

### Lição da campanha (r1–r9)

A primeira campanha de re-treino (7 rondas, **20 treinos**, ~**25 M passos**, 22 modelos avaliados) deu
**0/16** em todas as políticas. O bloqueio **não era o vento**:

1. **Atrator de *chatter* nos momentos**: as políticas v2 saturavam os canais de momento (|a₁|, |a₂|
   médios 0,74–0,90, ~70 trocas de sinal em 70 passos) e **capotavam aos ~1,3 s**; a política v1 (que
   paira 500/500) usa **1 %** dessa autoridade. A réplica exata da receita v1 sob a recompensa v2 caía no
   mesmo platô ⇒ o atrator vinha da **recompensa** (yaw forte + `Δa` fraco), não dos hiperparâmetros.
2. **Currículo com critério inatingível**: o avanço pedia `frac_no_alvo ≥ 0,8` com o yaw **incluído** no
   bónus; a política v1 — que paira bem — mede **0,10** ⇒ o DR de vento **nunca ligava** (`u_vento = 0`
   até ao fim). O critério passou a `frac_xy_z` (xy + z, **sem yaw**) com `--avanco-frac 0,5`.
3. **O bloqueio real era o yaw**: a base v1 já rejeitava o vento de posição, mas tinha o yaw livre
   (0,18 rad de *offset*). Um fine-tune de **160 k passos** baixou-o para 0,02 rad ⇒ 14/16.

As **três correções** que destravaram: `PESO_DELTA_A` 0,01 → **0,05**; avanço do currículo por
`frac_xy_z`; **`--retomar`** (fine-tune a partir dos checkpoints v1). Com elas: 16/16 de 1,08 M passos em
diante, replicado em 3 seeds independentes.

Achados operacionais: **`lr 3e-4` oscila** (16/16 ↔ 12/16 entre checkpoints, por yaw) enquanto
**`lr 1e-4`/`2e-4` é estável**; **polir SEM vento degrada** (16/16 → 13/16 em 200 k passos — a política
"esquece" a rejeição de vento), logo o vento tem de ficar no treino; e o `--retomar` do SB3 precisa de
`reset_num_timesteps=False` (senão o `learn()` reinicia o contador e retreina tudo de zero).

### Deploy — ONNX, validação numérica e latência

Exportação com o *exporter legacy* (`torch.onnx.export(..., dynamo=False)`; `dynamo=True` exigiria
`onnxscript`, que não está instalado), entrada **estática `(1, 16)` float32**, opset **17**,
`do_constant_folding=True`, sem `dynamic_axes`.

| item | valor medido |
|---|---|
| ops do grafo | `Gemm` ×3 · `Tanh` ×2 · `Cast` ×1 · `Flatten` ×1 (**sem `Clip`**) |
| ficheiro | `policy.onnx`, 23 507 B, IR 8, `onnx.checker` OK |
| validação | `max\|Δ\|` grafo vs **média da gaussiana** = **5,72e-06** (limiar 1e-5), 1 024 obs **reais** |
| contraprova | `_predict(deterministic=True)` vs média: `max\|Δ\|` = **0** |
| corte fora do grafo | 2 508 de 4 096 valores com `\|média\| > 1` → quem corta é o `env`/`predict`, não o grafo |

O que se compara é a **ação determinística** (`get_distribution().mode()` = média da gaussiana,
`squash_output=False`), **não** uma amostra. O `max|Δ|` de 10,17 contra `model.predict` **não** é erro
numérico: o `predict` corta a ação a `[-1, 1]` e o grafo não.

### Benchmark proxy de 1 core (o alvo de RUN é um Raspberry Pi 5, 4×A76 — isto é um **proxy**)

| medição | p50 | p99 | max | veredicto |
|---|---|---|---|---|
| fp32, 1 thread | **4,67 µs** | 5,06 µs | 72,0 µs | cabe a 50 Hz (20 000 µs) **e** a 100 Hz (10 000 µs) |
| fp32, 4 threads (contraste) | 4,75 µs | 6,66 µs | 165,9 µs | idem |
| int8 (`quantize_dynamic`, QInt8) | 6,03 µs | 6,73 µs | 10,6 µs | idem — mas **0,24–0,77× a velocidade do fp32** |

int8 reduz o ficheiro para **0,494×** (11 622 B) com `max|Δ|` vs fp32 de **0,21** — e no x86 sai **mais
lento** (0,24–0,77× conforme a medição): a quantização dinâmica não encontra aqui os *kernels* que a
tornam vantajosa. 212 320 inferências/s num core (fp32).

### Multi-IA — 4 processos a 50 Hz, cada um com a sua sessão ORT

| item | valor |
|---|---|
| processos / iterações | 4 · **1 996** |
| p99 agregado | **241,5 µs** (p50 86,5 µs, max 464 µs) |
| perdas de deadline (20 ms) | **0** |
| *throughput* total | 195 inferências/s (`parede` 10,24 s) |
| `loadavg` antes / depois | 1,35 / 1,44 |

`--pinned` foi validado à parte com **16 processos** (um por core): **16/16 cores distintos**, todos os
índices no core esperado, p99 agregado 381,0 µs, **0 perdas em 192 iterações**.

## Validação

| prova | comando | resultado |
|---|---|---|
| ambiente por fórmulas fechadas | `run.py` | **121/121 [OK]**, 0 falhas · ≈ 4 900–5 450 passos de decisão/s num env, validação completa em ~3–5 s |
| `HoverEnv` como `gym.Env` | `run.py` §5 | `check_env` do SB3, `reset(seed)` determinístico, `info` e truncagem corretos |
| robustez do ambiente | `run.py` §7 | não-finitos → `ValueError` (vento/ação/`alvo_z`), `alvo_z ∈ [0,10, 2,90] m`, divergência → `RuntimeError` |
| critério v2b (vento + orientação) | grelha 0–3 m/s × 4 azimutes × 3 seeds | **16/16 PASS, 0 terminações** — re-medido por um **agente independente** (16/16 e 32/32 na grelha densa própria) |
| suíte do laboratório | `uv run pytest .agents/mujoco-lab-agent-skill/tests -q` | **29 passed** |
| integração das peças (treino/UI/sonda/deploy) | verificação adversarial em 4 peças (v1) + 4 peças (v2) + 3 rondas de reparação | **9 PASS / 1 FAIL** (o FAIL era o `runs()` do `dashboard.py`; reparado e re-verificado) · v2: contratos todos PASS após reparações e re-verificações pontuais |

Condições de medida dos µs: máquina ociosa (`loadavg` 1 min **1,35** antes do benchmark, 1,44 depois);
o `deploy.py` regista o `/proc/loadavg` antes/depois em todos os relatórios exatamente por isso.

## Limites e nits conhecidos

- **Limite RPi 5 só na RUN, treino a poder máximo** — decisão do dono: o treino corre com os 32 threads
  disponíveis; o limite de 1 core é imposto **apenas** no *benchmark* (`--threads 1`, proxy do A76) e no
  `--pinned`.
- **A latência medida é de um proxy x86**, não do RPi 5. O ganho do int8 no alvo **não** está medido aqui:
  um estudo independente no Cortex-A76 reporta que a **quantização estática** (QOperator) corre
  1,25–2,70× mais rápido que o fp32, e que o determinante é *estática vs dinâmica* (mais de 4×) — este
  experimento usa `quantize_dynamic`, precisamente a variante que esse estudo aponta como perdedora em Arm
  ([Zenodo 22163336], conteúdo externo, não verificado nesta máquina).
- **Envelope de vento (medido)**: fiável até **3 m/s** (`‖xy‖ ≤ 0,12 m`); a **3,5 m/s** fica no fio do limite
  alargado (0,146 m contra 0,15 m), a **4 m/s** dá 0,189 m e a **5 m/s** 0,285 m — a degradação é **suave**
  (mais deriva, **zero quedas até 5 m/s** em 12 rollouts por velocidade). Altitude e orientação aguentam
  todo o envelope testado (`|z−1| ≤ 0,0045 m`, `|yaw_err| ≤ 0,03 rad`).
- **`--sucesso 450` não dispara com a recompensa v2b**: o `mean_ret` final do run que passou é **350,0**
  (a escala mudou com os pesos). Para paragem automática usar ≈ **330–345** (`--sucesso 340`).
- **A régua do currículo mede sem vento**: o avanço de estágio usa `frac_xy_z` medido nos rollouts de
  avaliação, que correm **sem vento** (régua estável entre estágios). Consequência assumida: um estágio
  pode subir sem que o vento desse estágio esteja dominado — a robustez ao vento mede-se à parte, com a
  grelha. Medido: `frac_xy_z` sobe a 0,80–0,92 logo na 1.ª avaliação e os estágios avançam 0→1→2→3.
- **`best_model.zip` é escolhido pelo retorno sem vento** (`EvalCallback` com env de avaliação em ar
  parado), logo pode **não** ser o melhor artefacto para vento — neste experimento o `final.zip` do run
  final é o artefacto validado. Selecionar por grelha dentro do `train.py` é trabalho futuro.
- **`alvo_z: true` é aceite** pela API do dashboard: `float(True)` dá `1,0` em Python (o `bool` é subclasse
  de `int`). A faixa é validada (`[0,10, 2,90] m`), o **tipo** não é estrito.
- **`plotext` 6.1.0** não expõe o `plot()/build()` clássico → o painel do `train.py` desenha a curva de
  retorno com uma *sparkline* própria em blocos Unicode, sem dependências.
- **SIGSEGV intermitente no fecho do viewer** (mujoco 3.15 + pyGLFW, KDE Wayland): fechar a janela e sair
  logo a seguir faz correr o `glfw.terminate()` do `atexit` ao mesmo tempo que a thread do viewer. Acontece
  **no fecho**, com o ciclo a devolver 0; mitigado em `view.py` com `esperar_fecho()` (espera que o handle
  perca a referência ao simulador, teto ~2 s).
- **`multiprocessing.Pool` reutiliza workers**: a afinidade de core tem de ser calculada no processo **pai**
  e passada ao filho (o filho só a aplica e confirma). Calcular o core dentro do filho herdaria a afinidade
  da tarefa anterior — é o que `mapear_nucleos` evita.
- **Contagem do SB3**: `EvalCallback`/`CheckpointCallback` contam **chamadas do callback**, e cada chamada é
  um passo do *vec* (`n_calls = timesteps / n_envs`), não um passo de ambiente. O `--eval-freq` está em
  passos do vec.
- **`--retomar` do SB3**: `learn()` tem `reset_num_timesteps=True` por omissão; usar `False` para a contagem
  acumular (senão o treino recomeça do zero). E o fine-tune **não** aplica `--log-std-init`/`policy_kwargs`
  (a arquitetura vem do checkpoint) — só `lr` e o L2 do CLI entram nos `param_groups`.
- **D2/D3 aceites (limites do desenho)**: uma **queda pousada não é morte** (o piso impede `z < 0` e o
  limiar de terminação é 0,005 m); e **ficar no chão é pior que terminar** — 500 passos parado acumulam
  ≈ **−493** contra ≈ **−101** de um episódio que termina cedo.
- **A política não é um controlador de voo certificado**: é robusta ao vento **dentro do envelope treinado**
  (≤3 m/s sustentado, elevação pequena). Não foi treinada com **atraso de atuador**, **ruído de IMU**
  (`ruido_obs` existe, padrão 0) nem **variação de massa/ganhos** — nada disso está garantido fora do
  simulado.

## Próximos passos

1. **Validar o modo janela com o dono** (`view.py`) — HUD de 8 linhas, 3 figuras e o `esperar_fecho()`
   foram exercitados **sem janela** por agentes; falta a confirmação visual no posto de trabalho
   (e o painel de vento do dashboard, que foi validado por DOM headless + CDP, não com olhos).
2. **Revalidar a latência no Raspberry Pi 5 real** — os 4,67 µs p50 são de um proxy x86; medir lá o fp32 e
   o int8 com a mesma sessão ORT de 1 thread.
3. **Decidir o int8 no alvo** — testar a quantização **estática** (QOperator) no RPi, que a evidência
   externa indica ser a variante que compensa em Cortex-A76, antes de adotar int8 por omissão.
4. **Estender o envelope e a robustez**: treinar com `--vento-max 4`–`5` (o `xy` a 3 m/s, 0,119 m, é o
   único termo perto do limite), e acrescentar **condições iniciais variáveis** (o `reset` atual é sempre a
   mesma pose pousada com jitter de ±2 cm) para uma medida de robustez estatisticamente mais forte.
5. **Selecionar o checkpoint por grelha dentro do `train.py`** (hoje o `best_model` é escolhido pelo retorno
   **sem** vento) e automatizar o avaliador da grelha como critério de fim do treino.

## Fontes citadas (conteúdo web = `untrusted`, só citado)

- [mujoco_menagerie · bitcraze_crazyflie_2](https://github.com/google-deepmind/mujoco_menagerie/tree/main/bitcraze_crazyflie_2) — modelo MJCF (cópia local em `models/`, MIT) e a nota de que os `ctrlrange` são *"arbitrary and need to be further tuned"*.
- **MuJoCo-Drones-Gym: A GPU-Accelerated Multi-Drone Simulator for Control and Reinforcement Learning** — [arXiv 2606.08039](https://arxiv.org/pdf/2606.08039) · preprint · nível B · lida: trechos — origem da equação de recompensa usada literalmente.
- [INT8 configuration study on Raspberry Pi 5 (Arm Cortex-A76)](https://zenodo.org/records/22163336) · software · MIT · conteúdo externo — latências de modelos quantizados em ORT no A76; quantização estática vs dinâmica e níveis de otimização de grafo.
- [crazyflie_ros (whoenig)](https://github.com/whoenig/crazyflie_ros) — URDF de origem do modelo, via menagerie.
- [Datasheet Crazyflie 2.0 (Bitcraze)](https://www.bitcraze.io/documentation/hardware/crazyflie_2_0/crazyflie_2_0-datasheet.pdf) — 27 g; base do `thrust_max = 0,589 N` (4 × 15 gf → T/W ≈ 2,22).

Para o modelo, a camada `lab/crazyflie.py`, os sensores e as constantes físicas do Crazyflie 2, ver
[`models/bitcraze_crazyflie_2/`](../../models/bitcraze_crazyflie_2/) e
[`lab/crazyflie.py`](../../lab/crazyflie.py) (o antigo experimento `08_crazyflie_motores` foi removido
em 2026-10-08 — histórico no git).
