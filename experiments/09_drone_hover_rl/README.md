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
- `run.py` — validação do ambiente por **fórmulas fechadas**, 146/146 checagens, exit 0/1.
- `helices_render.py` — prova **visual** (offscreen/EGL) da animação das hélices: 2 imagens em `out/`.

## Planta REAL — o drone do dono, com peças reais (2026-10-10)

O `plano-drone-real.md` (raiz) está implementado: além do Crazyflie histórico (`env.py`, intocado), o v09 tem
o **drone que o dono vai construir**, gerado das **peças reais** do catálogo `models/drone_rpi/` e com a
política a ver **só o que o hardware mede**. Peças trocáveis sem código (`hardware.py`), os dados das peças
gravados ao lado de cada política (`hardware.json`), e tudo validado por fórmulas fechadas.

```bash
uv run python experiments/09_drone_hover_rl/hardware.py comparar            # builds com peças reais
uv run python experiments/09_drone_hover_rl/hardware.py usar <build>        # trocar motores/bateria/hélices
uv run --group hover-rl python experiments/09_drone_hover_rl/valida_real.py # 96 checagens (também no run.py)
uv run --group hover-rl python experiments/09_drone_hover_rl/train.py --planta real --n-envs 12 \
    --timesteps 6000000 --out-dir experiments/09_drone_hover_rl/out/real_<nome>   # PPO, DR, crítico assimétrico
uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py   # escolhe a política out/real_* sozinho
uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --model experiments/09_drone_hover_rl/out/real_<nome>/best_model.zip
```

**Build ativo** `endurance_15pol_p50b`: T-Motor MN4004 KV300 + P15×5 CF, 6S2P Molicel P50B (216 Wh), ESC T-Motor
AIR 40A, frame DIY 650 mm, RPi 5 + FC H7, BMI088 + VL53L1X + PMW3901 + INA226 → **1664 g · 133 W em pairagem
(12,5 g/W) · T/W 3,4 · 99 min de pairagem no modelo** (~80–90 min reais esperados). Detalhe, alternativas e
fontes: `models/drone_rpi/README.md`.

| Peça do simulador | Ficheiro | O que faz (tudo pelo `mj_step` a 500 Hz) |
|---|---|---|
| Catálogo → física | `lab/drone_rpi/componentes.py`, `modelo.py` | massa/inércia das peças (MJCF gerado por MjSpec, CM na origem), kf/kq da tabela do fabricante (+7,5 % de realismo), curva do ESC, ω_max(V), pairagem, autonomia |
| Motores + ESC | `lab/drone_rpi/propulsao.py` | modelo elétrico DC (I = (d·V − K_e·ω)/R, Q₀(ω), J·ω̇), travagem ativa, DShot11; empuxo e reação por rotor |
| Bateria | `lab/drone_rpi/bateria.py` | Thevenin 1-RC, SoC por Coulomb, R₀(T, SoC, SoH), térmica, desgaste persistente (SoH/ciclos/“reformar”) |
| Ar | `lab/drone_rpi/aero.py` | efeito de solo (Sanchez-Cuevas), inflow BEMT (ajustado à APC 15×5.5MR), VRS, arrasto de rotor, download do frame, giroscópico — tudo desligável (`FlagsAero.base()` = bit-idêntico a T = kf·ω²) |
| Sensores | `lab/drone_rpi/sensores.py` | IMU (bias/deriva/ruído/escala/saturação/LSB/atraso/vibração), ToF ao chão, fluxo ótico (com a parte rotacional), barómetro, monitor V/I |
| Passo de física | `lab/drone_rpi/planta.py` | `mj_step1` → cinemática dos rotores (raio ao solo, ar relativo) → κ_T/κ_Q → **Newton bateria↔ESC** → rotores → forças → `mj_step2` → bateria → sensores |
| FC dedicado | `fc.py` | malha de taxa a 500 Hz (PID com ganhos calculados da planta, D na medida, PT1), mistura X, airmode, idle |
| Estimador de bordo | `estimador.py` | o que o RPi 5 calcula SÓ com sensores: atitude (complementar), rumo, altura/v_z (ToF + acc), v_xy (fluxo), odometria |
| Ambiente | `env_real.py` | `DroneRealEnv` (herda o vento base/dinâmico do `HoverEnv`), DR por episódio, pack que persiste em `options={"manter_bateria": True}` |
| Política | `politica.py` | ator-crítico ASSIMÉTRICO: o ator só vê `obs[:21]`; o crítico vê também o privilegiado |

**Contrato do `DroneRealEnv`.** Ação `Box(-1,1,(4,))` em `ctbr` (padrão): coletivo LINEAR EM EMPUXO à volta da
pairagem (u = u_pair(V)·√(1+a₀): −1 → 0, 0 → pairagem, +1 → 2× o peso) + taxas p, q, r até ±[2; 2; 1] rad/s, com o
atraso de comando do RPi (8 ms, FIFO por passo de física); `motores` = 4 aceleradores (RPi sozinho). O u_pair é
calculado à tensão MEDIDA da bateria (INA226) — a compensação de tensão do Betaflight (`vbat_sag_compensation`):
a política não vê a bateria, mas o seu "0" é pairar a qualquer SoC (medido: voa igual a 100/50/25 % de SoC).
Observação (42,) = **ator (21)**: giro/2, acc/9,81, roll̂, pitcĥ, Δψ̂/π, ĥ − alvo, v̂_z, v̂_x, v̂_y, x̂, ŷ,
ToF válido, fluxo válido, ação anterior — **sem nenhum dado privilegiado** — + **crítico (21)**: p − p_alvo,
v, (roll, pitch, yaw_err)/π, ω, ω_rotor/ω_max, SoC, V/V_nom, vento. **Recompensa v3-real** (xyz privilegiado é
permitido): r = 1 − 0,35·tanh(‖xy‖) − 0,35·tanh(|Δz|/0,5) − 0,1·tanh(|ψ−ψ₀|/0,5) − 0,1·tanh(‖v‖) −
0,05·tanh(‖ω‖/2) − 0,05·min(‖Δa‖, 1) + 0,5·bónus − 50·𝟙[terminou] — limitada, com estar vivo SEMPRE ≥ 0: a v2b do
cf2 (penalidades ilimitadas, −100 no fim) ensinou a política real a "cair cedo" quando derivava (1.º treino:
z médio a 0,56 m aos 0,8 M passos); com a v3-real a mesma configuração paira a 1 m. DR por episódio: massa ±5 %, inércia ±10 %,
CM ±4 mm, kf ±8 % (+±2 % por motor), kq ±10 %, J −20/+25 %, R −10/+15 %, KV ±3 %, I₀ ±20 %, η, SoC₀ 30–100 %,
SoH 80–100 %, R da bateria ×0,8–1,3, 5–35 °C, atraso 0–12 ms, ruído dos sensores ×0,5–2, arrasto de rotor
0,20–0,45 s⁻¹, efeito de solo ×0,7–1,3, VRS ×0,5–1,5.

**Validação** (`valida_real.py`, chamado pelo `run.py`): 96/96 — catálogo (massa = Σ peças em todos os builds,
modelo vs tabela do fabricante: rpm ≤ 1 %, corrente ≤ 5 % no build ativo), motor (regime = quadrática exata,
balanço de potência, τ = 57,4 ms medido vs 57,6 ms linearizado, travagem ativa 159 ms vs roda livre 2,4 s,
DShot, atraso de 4 passos), bateria (Coulomb e RC exatos, OCV, ×2,25 de R a 0 °C, sag ×1,5 no fim de vida,
desgaste por ciclo, persistência, ledger e Newton exatos), ar (+20 % de empuxo a 0,5·D e +5 % a 1,75·D,
a = −d·v, BEMT vs APC ±0,011, VRS 25 % a v_h = 3,8 m/s, base bit-idêntica), sensores (σ do giro 0,00263 vs
0,00260, atraso, ToF = h/cos θ, fluxo e a sua inversão), contrato (ator invariante a xy; recompensa não;
`check_env`), FC (mistura desacoplada, t90 = 206 ms ≈ 3,6·τ) e autonomia (analítica 99,0 min vs bancada
97,4 min; meta de 60 min cumprida).

**Treino da política do drone real (2026-10-10).** PPO + crítico assimétrico, MLP 128×128 tanh, 16 ambientes com
DR, currículo de vento 0→1→2→3 m/s (avança quando ≥ 50 % dos passos têm xy E z dentro de 5 cm), recompensa
v3-real: `out/real_endurance15/` (1,5 M passos, ~23 min a ~1100 passos/s) e *fine-tune* com rajadas dinâmicas
sobre o vento base até 3 m/s em `out/real_endurance15_rajadas/` (`--retomar`, +1 M passos). Curva do treino
principal (avaliação determinística em ar parado, bateria cheia, 10 episódios):

| passos | retorno (máx. ≈ 750) | z médio | ‖xy‖ médio | xy+z ≤ 5 cm | vento de treino |
|---|---|---|---|---|---|
| 64 k | 311 | 0,89 m | 0,89 m | 0 % | 0 |
| 256 k | 451 | 0,97 m | 0,12 m | 11 % | 0 |
| 448 k | 595 | 0,96 m | 0,037 m | 71 % | 0 → 1 m/s |
| 576 k | 607 | 0,96 m | 0,029 m | 86 % | 1 → 2 m/s |
| 704 k | 645 | 0,97 m | 0,029 m | 83 % | 2 → 3 m/s |
| 1,0–1,5 M | 560–650 | 0,96–0,98 m | 0,03–0,06 m | 33–91 % | 3 m/s |

**Política final** = o *fine-tune* `out/real_endurance15_rajadas/final.zip` (2,51 M passos) — a que o site carrega
por omissão e a que o `deploy.py` exportou. Grelha de condições (`avaliar_real.py`, 5 episódios por condição com as
MESMAS seeds 5000–5004, 2.ª metade de cada episódio de 10 s — já depois de descolar; vento com uma direção diferente
por episódio):

| condição | vivo | \|Δz\| | ‖xy‖ | ≤ 5 cm | ≤ 10 cm | \|ψ − ψ₀\| | potência | autonomia mostrada |
|---|---|---|---|---|---|---|---|---|
| nominal, bateria cheia, ar parado | 100 % | 1,1 cm | 6,6 cm | 32 % | 83 % | 0,027 rad | 130,1 W | 103 min |
| SoC 50 % / SoC 25 % (tensão baixa) | 100 % | 1,1 cm | 6,6 cm | 32 / 33 % | 84 % | 0,027 rad | 130,1 W | 41 / 14,5 min |
| vento 2 m/s | 100 % | 1,2 cm | 6,1 cm | 37 % | 89 % | 0,026 rad | 131,7 W | 102 min |
| vento 3 m/s | 100 % | 1,3 cm | 6,0 cm | 40 % | 86 % | 0,027 rad | 134,0 W | 100 min |
| vento 3 m/s + rajadas (até +3 m/s) | 100 % | 1,3 cm | 6,3 cm | 35 % | 92 % | 0,030 rad | 134,2 W | 100 min |
| frente de vento 3 m/s aos 5 s | 100 % | 1,8 cm | 7,0 cm | 18 % | 93 % | 0,027 rad | 134,3 W | 100 min |
| DR (peças/bateria/sensores sorteados) | 100 % | 1,8 cm | 9,2 cm | 40 % | 52 % | 0,029 rad | 129,4 W | 70 min (SoC₀ 30–100 %) |
| DR + vento 2 m/s | 100 % | 1,9 cm | 9,1 cm | 40 % | 50 % | 0,030 rad | 131,0 W | 69 min |

Comparação na MESMA grelha (\|Δz\| nominal / sob DR; ‖xy‖ nominal / sob DR): checkpoint de 1,5 M 1,9 / 3,7 cm e
6,6 / 9,6 cm · `best_model` do *fine-tune* 1,4 / 3,1 cm e 6,3 / 9,5 cm · **`final` 1,1 / 1,8 cm e 6,6 / 9,2 cm**. O
*fine-tune* com rajadas melhorou sobretudo a altura (metade do erro sob DR); em xy as três empatam — com só 3
episódios o checkpoint de 1,5 M parecia melhor (4,9 cm, 100 % ≤ 10 cm): era amostragem de seeds.

**O ‖xy‖ é limitado pelo ESTIMADOR de bordo, não pela política** (medido episódio a episódio, mesmas seeds): a
política segura a posição que o RPi ESTIMA (fluxo ótico + odometria) a 1–5,5 cm do alvo, mas essa estimativa está
2–11 cm ao lado da verdade (deriva da odometria por fluxo; maior com o ruído dos sensores ×1,4–2 do DR) — o erro
verdadeiro é quase todo erro do estimador. Por isso o DR é bimodal: 2 de 5 episódios seguram < 5 cm e 3 de 5 ficam
com um desvio de 11–16 cm em que a estimativa está a 1–5,5 cm do alvo (os 40 % ≤ 5 cm e 52 % ≤ 10 cm). Para
melhorar o xy no drone real o caminho é o estimador (fusão fluxo + acelerómetro num Kalman, calibração da escala do
fluxo, ou uma referência absoluta — marcador visual, UWB, RTK), não mais treino.

A potência em pairagem medida no voo (130 W) bate com o modelo do catálogo (133 W, fora do efeito de solo: a 1 m
os rotores estão a z/D ≈ 2,7 e o efeito de solo dá +2,3 % de empuxo, ≈ −3 % de potência à mesma tração) e a
autonomia mostrada pelo site é a que o pack daria a essa potência, com 10 % de reserva no Li-ion. Na pairagem nominal as médias da política ficam dentro de [−1, 1]
(coletivo −0,026 ± 0,076, taxas ≈ 0); só a descolagem satura o coletivo (+1 = 2× o peso) durante ~1 s — no site,
com o pack cheio, o pico foi 66,5 A (74 % dos 90 A do 6S2P P50B; 16,6 A por ESC de 40 A) e a tensão mínima
21,9 V (3,65 V/célula).

**Deploy da política final** (`deploy.py --model out/real_endurance15_rajadas/final.zip`): ONNX de entrada (1, 21)
→ saída (1, 4) — só o ATOR, o crítico privilegiado não vai para o RPi —, 94,6 kB, opset 17; max\|Δ\| 4,8·10⁻⁶ face
ao PyTorch (limiar 10⁻⁵; em estados fora da distribuição as médias chegam a \|μ\| ≈ 10 e o arredondamento
float32 cresce com elas — o clip a [−1, 1] fica no env/RPi); p50 6,9 µs · p99 7,4 µs num core (proxy do A76) e
4 IAs em paralelo a 50 Hz sem perdas (p99 agregado 422 µs). `policy.onnx` e `deploy_report.json` ficam ao lado do
modelo — o painel RPi 5 do site lê esse relatório (e diz que o modelo medido é o que está a correr).
<!-- resultados-finais -->

## Como correr

```bash
uv sync --group hover-rl                                   # stable-baselines3 + torch (CPU) + onnx/onnxruntime + rich/plotext

# 1) validar o ambiente (não treina nada): 146 checagens, exit 0
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
#     métricas e controlos, num só comando; o LOOP arranca DESLIGADO («SEM REINÍCIO», padrão desde
#     2026-10-09): no fim do episódio a física continua no estado em que ficou — só o REINICIAR do site
#     recomeça. `--com-loop` liga o CONTÍNUO (auto-reset no fim do episódio) já no arranque
#     (ver §«Continuidade do episódio»)
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
| `sim_view.py` | runner da **janela limpa** + telemetria JSONL: lê vento/`reiniciar`/`loop` do ficheiro de controlo; CONTÍNUO reinicia no fim do episódio e SEM REINÍCIO deixa a física continuar (só o REINICIAR recomeça) | treinar, HUD, abrir browser |
| `sim_site.py` | **um comando**: arranca o `sim_view.py` + servidor local que serve o site (`site/dist/`) e a API (`/api/sim`, `/api/vento`, `/api/vento-dinamico`, `/api/reiniciar`, `/api/loop`) | treinar, mexer na física |
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

### Vento dinâmico (r10) — rajadas · rajadas aleatórias · frente · turbulência

O vento por episódio (`vento`/`vento_aleatorio`) só muda **entre** episódios. A ronda 10 acrescentou
`vento_dinamico=dict`, que faz o vento mudar **dentro** do episódio, a cada passo de decisão (50 Hz),
sempre pelo mesmo mecanismo físico (`opt.wind`). A config é validada por `env.valida_vento_dinamico()`
(modos, chaves e faixas; erro claro) e o treino expõe-na por `--vento-dinamico` +
`--vento-dinamico-params '<json>'` — **só os envs de TREINO** a recebem (a avaliação fica no contrato v2b):

| modo | chaves (default) | o que faz a cada passo de decisão |
|---|---|---|
| `rajadas` | `p` 0,02 · `duracao` 10 passos (0,2 s) · `u_max` 3,0 m/s | com probabilidade `p` sorteia uma rajada (norma U[0, `u_max`], azimute novo, elevação ±20°) que **soma** ao vento base durante `duracao` passos; uma rajada em curso não é interrompida por outra |
| `aleatoria` | `p` 0,02 · `duracao` 10 passos (0,2 s) | rajadas com o mesmo `p`/`duracao`/envelope de `rajadas`, mas cada uma re-sorteia **direção E força dentro das faixas disponíveis por inteiro**: norma U[0, 5] m/s, azimute U[0, 360°) e elevação U[−90°, +90°] (o `VENTO_ELEV_MAX` = 20° **não** se aplica aqui). Aplicação por **mistura vectorial** com o vento base, `w(k) = base + sin(π·k/(N+1))·(rajada − base)`: **no pico do envelope o vento É o vector sorteado** e nas pontas fica junto do base (entrada/saída suave), com `‖w‖ ≤ max(‖base‖, 5) m/s` — uma soma, com base forte, daria direções dominadas pelo base e normas até 10 m/s. Cada rajada tem o seu próprio vector — nada vaza para a seguinte. `u_max`/`sigma`/`L`/`v_min` são aceites (e validados, se vierem) mas **ignorados**: a amplitude não segue o teto do currículo (só `u_max = 0` continua a deixar o modo inerte, como em todos os modos) |
| `frente` | `t_s` 2,0 s · `u_max` 3,0 m/s | no instante `t_s` chega uma **frente** — norma U[0,5 m/s, `u_max`], azimute novo — que **substitui** o vento base até ao fim do episódio (degrau dentro do passo, sem transiente artificial; `t_s = 0` = frente logo no 1.º passo e `t_s` tem de cair dentro do episódio) |
| `dryden` | `sigma` 0,5 · `L` 10,0 · `u_max` 3,0 m/s | **turbulência** OU de 1.ª ordem (filtro de Dryden discreto por passo): o vento passeia em torno do base, saturado em ±`u_max` |

`u_max` é o teto do **modo** (o teto do vento por episódio continua a ser o do currículo/`--vento-max`), e
**`u_max = 0` é inerte em todos os modos**: sem rajadas, sem frente e sem turbulência — e, importante,
**não consome `np_random`**, logo um estágio sem vento é indistinguível do contrato v2b (era a guarda que
faltava aos modos não-`rajadas`). O `info["vento_atual"]` passou a reportar o vetor **em vigor**
(base + dinâmica).
Estes modos são do **treino/avaliação** e do **vento ao vivo** do site (a caixa «vento dinâmico» tem o
seletor PARADO/RAJADAS/**ALEATÓRIA**/DRYDEN, que escreve o modo sem reiniciar o episódio); os sliders
aplicam sempre vento **constante em tempo real** (`INTERFACE.md` §3.5).

### PARAR — nenhuma rajada sobrevive ao clique (2026-10-09)

O dono relatou «podemos mandar rajadas mas na hora de parar só paramos a última». Mecanismo **medido**
(não suposto): só existe **um** slot de rajada dirigida (`Controlo.rajada` — cada `RAJADA AGORA` substitui a
anterior, logo nunca houve rajadas simultâneas nesse slot); o que continuava a atuar depois do PARAR eram
(i) as rajadas dos **modos contínuos** (`rajadas`/`aleatoria`/`dryden`, geradas pelo próprio env) e (ii) a
rajada one-shot a meio do envelope — porque o botão **PARAR VENTO** escrevia só `POST /api/vento {vel: 0}`
(o vento *constante*) e **não tocava no bloco `dinamico`**: o runner continuava a escrever o envelope em
`model.opt.wind` e a telemetria continuava a mostrar `vento_modo = rajadas|rajada_agora|…`. Havia ainda
dois resíduos: o `definir_vento_dinamico(None)` do env não limpava `_rajada_k/_rajada_n/_rajada_vec/_turb/
_frente_vec`, e o restauro do vento base usava o registo **anterior** do controlo (um PARAR que também mexe
no vento — o do PARAR VENTO — escrevia a base velha em `opt.wind`).

Correção: `Controlo._para_dinamica` (caminho único do PARAR DINÂMICO **e** do PARAR VENTO) corta o slot da
rajada, reescreve em `opt.wind` o vento base do controlo **em vigor** e desliga o modo do env;
`env.definir_vento_dinamico(None)` passa a limpar o estado do modo e a escrever sempre o vento base; a troca
de modo larga a rajada por `cancelar_rajada` (com restauro) e o `_aplica` fixa o registo em vigor **antes**
do bloco dinâmico; e o novo **`POST /api/parar`** faz o PARAR VENTO numa só escrita atómica (vento base a 0
**+** dinâmica desligada), usado pelo botão do site.

Prova repetível (`teste_parar_vento.py`): **15/15 verificações** sem flags — todos os cenários/ciclos do
PARAR (one-shot e modos contínuos, com o PARAR a chegar no início/meio/fim do ciclo da rajada) no ciclo
REAL do `sim_view.correr`, mais a prova de concorrência in-process —; **16/16** com `--http` (ponta a ponta
pelo servidor real + ~100 pares de POSTs concorrentes) e **18/18** com `--http --navegador` (front real num
Chrome headless, janelas 0/50/100/300/600/1000 ms × 3 caminhos de paragem + controlo, e os cenários
multi-cliente). Com as fontes de antes (`--legado REV`, ou `--fontes DIR`) só passavam **3** verificações,
com as falhas exatamente nos cenários do PARAR VENTO (vento a oscilar 1,8–5,0 m/s com
`vento_modo` ainda `rajada_agora`/`rajadas`/`dryden`) e nos resíduos do env.



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

### Continuidade do episódio — LOOP, REINICIAR e o ficheiro de controlo (ronda 11)

O `sim_view.py` (runner da janela limpa) e o `sim_site.py` (site + API) partilham o ficheiro
`out/controle_vento.json`. Desde a ronda 11 o campo `loop` é **sticky e autoritativo**, e desde
2026-10-09 o **padrão é SEM REINÍCIO (`false`)** — o arranque corrige o ficheiro e, depois dele, só o
`POST /api/loop` muda o modo:

| situação | o que acontece |
|---|---|
| `loop: false` ou nada (PADRÃO desde 2026-10-09) − **SEM REINÍCIO** | **nunca reinicia sozinha e nunca congela**: no fim do episódio a física **continua** a integrar (`mj_step` a 50 Hz) no estado em que ficou — se caiu, fica onde a física o deixou; se pairava, continua a pairar — com a telemetria a ~10 Hz, `passo`/`t` a crescer para lá dos 500/10 s e `retorno` congelado no valor com que o episódio fechou. **Só o REINICIAR recomeça** |
| `loop: true` / `--com-loop` − **CONTÍNUO** | no fim do episódio (`terminated`/`truncated`, 500 passos = 10 s) o runner faz `env.reset()` e **arranca já o episódio seguinte** (ep+1, passo 0); a transição é discreta e o vento/modo dinâmico atravessam-na |
| REINICIAR (site, `POST /api/reiniciar`) | incrementa o contador `reiniciar` no ficheiro → `env.reset()` no passo de decisão seguinte. É o **único reset** e vale em qualquer estado (a correr, terminado sem reinício, ou a meio) |
| LOOP do site (`POST /api/loop`) | única forma de mudar `loop` **depois do arranque** (liga/desliga a quente, sem reiniciar nada por si) |
| `--com-loop` / `--sem-loop` no arranque | **autoritativos**: o arranque CORRIGE o `loop` do ficheiro — sem flag (ou `--sem-loop`) um `loop: true` velho passa a `false`; com `--com-loop` (alias antigo `--loop`) um `loop: false` velho passa a `true` — preservando vento, dinâmica e o contador `reiniciar`. As duas flags juntas são recusadas (`exit 2`) |

Escritas **parciais** no controlo (ex.: `POST /api/vento`, `/api/vento-dinamico`, que não trazem `loop`
nem `reiniciar`) fazem merge sobre o que o ficheiro já tem: **não** re-ligam o loop nem mexem no contador
de reinícios. `--max-segundos` e `--max-episodios` continuam a terminar o processo (são flags explícitas,
não auto-loop). Contrato e detalhes de UI: `INTERFACE.md` §4.1 e §3.5.

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

### Hélices — animação VISUAL (2026-10-09, fora do `mj_step`)

As 4 hélices **giram na janela 3D** com a velocidade e o sentido do rotor que está a ser comandado. É
**só apresentação**: a animação corre no runner (`sim_view.py` chama `cf.Helices.atualizar(...)` antes de
cada `viewer.sync()`) e escreve apenas `model.geom_pos`/`model.geom_quat` de 4 geoms **visuais**, mais um
`mj_kinematics` para o renderer ver já este frame. Nada toca em `qpos/qvel/ctrl` nem em `mj_step`.

- **Adaptação em runtime (upstream intacto):** a malha `cf2_0` do menagerie (as 4 hélices **fundidas**
  numa só) é fatiada por **quadrante do sinal de (x, y)**. O OBJ **não** tem as hélices como ilhas
  separadas — é um *vertex soup* (medido: 3372 vértices para só **1592 coordenadas únicas**, 3168 faces e
  **176 ilhas** de aresta, a maior com 130 vértices) —, mas **nenhuma das 3168 faces cruza os eixos
  x = 0 / y = 0** em coordenadas do ASSET (medido: 0 faces a cruzar), e é só isso que o corte pelo sinal
  exige: cada quadrante leva exactamente 843 vértices, 792 faces e 44 ilhas, os mesmos do OBJ. Daí saem 4
  malhas com 4 geoms novos `helice_1..4` (`contype = conaffinity = 0`, `density = 0`, grupo 2, material
  `propeller_plastic`); o geom original é apagado do spec. `models/bitcraze_crazyflie_2/` fica **intocado**.
- **Massa e inércia não mudam:** o corpo `cf2` tem `<inertial>` explícito e o compilador tem
  `inertiafromgeom="false"`, logo os geoms visuais não pesam — `m = 0,027 kg` e `diaginertia =
  2,3951e-5/2,3951e-5/3,2347e-5` iguais ao upstream, ao bit.
- **Eixo de rotação medido na própria malha:** as tampas do motor (as únicas faces perfeitamente planas
  e de secção quadrada, Ø 3,99 mm) dão o eixo; eles ficam a **0,7–1,2 mm** dos `POS_ROTORES` (±32,5 mm)
  — a malha do menagerie está ligeiramente descentrada da origem do corpo, por isso medir é mais fiel.
- **Lei de rotação:** `|ω_i| = ESCALA_VISUAL·√t_i` com `t_i` = empuxo de cada rotor (N) recuperado do
  wrench comandado pelo **mixer inverso** de `comandar_rotores`; o sinal é o de `GIRO` (**+1 = anti-horário
  visto de cima**), pelo que as **diagonais 1-4 e 2-3 giram no mesmo sentido e as vizinhas no oposto** —
  coerente com o sinal do momento de guinada do modelo.
- **ESCALA VISUAL (documentada):** `ESCALA_VISUAL = 2π·3/√T_ROTOR_MAX = **63,72 rad/s·N^(−1/2)**`, isto é
  **3 rev/s com um rotor no empuxo máximo** (0,0875 N) e ≈ 2,6 rev/s em hover — cerca de **1/100 da
  rotação real** (hélices CF2 a ~15 000 rpm ≈ 250 rev/s): a rotação verdadeira seria ilegível a 50 Hz
  (aliasing). A proporcionalidade entre rotores e os sentidos são **exatos**; só a escala é visual.
- **Motores desligados:** as hélices **abrandam** com 1.ª ordem (`ABRANDAMENTO_S = 0,35 s`) e, abaixo de
  `LIMIAR_PARAGEM = 0,01 rad/s`, **param exactamente** (ω = 0, ângulo congelado) — sem rodar para sempre.
- **REINICIAR não parte nada:** o estado da animação é só ângulo/velocidade, os geoms são re-resolvidos
  por **nome** se o modelo mudar e o `ctrl = 0` do `reset` trava as hélices até um comando novo.
- **Neutralidade provada (`run.py` §10, 13 checagens novas):** 500 passos de decisão (queda, repouso
  **com contactos** — até 24 por passo —, um `reset` a meio e comandos aleatórios) dão
  `qpos/qvel/ctrl/sensordata/energy/contactos` **idênticos ao bit** (max|Δ| = 0) com a animação **ligada**,
  **desligada** e com o modelo **upstream** do RL. O RL e o deploy não mudam: `cf.carregar()` e
  `HoverEnv()` continuam sem hélices por omissão (`HoverEnv(helices=True)` é opt-in, usado só pelo runner).
- **§10 à prova de regressão:** a checagem de rotação compara com um **θ derivado do COMANDO**
  (`ESCALA_VISUAL·√t_i` + avanço de 1.ª ordem), não com o θ lido do modelo — com θ = 0 ela era **vácia**
  (`Rz(0) = I` e os vértices em repouso batiam certo) e uma animação parada ou um ângulo errado (×1,5)
  passavam; se a adaptação faltar, o §10 **interrompe-se com uma FALHA limpa** (exit 1) em vez de rebentar
  com `ValueError` de broadcast.
- **Prova visual (2 imagens, offscreen EGL):**

  ```bash
  MUJOCO_GL=egl uv run --group hover-rl python experiments/09_drone_hover_rl/helices_render.py
  # → out/helices_1.png (passo 30, t = 0,60 s, θ = [5,415 −5,114 −5,114 5,415] rad)
  #   out/helices_2.png (passo 37, t = 0,74 s, θ = [7,434 −7,021 −7,021 7,434] rad)
  #   --sem-helices grava o par de controlo (out/helices_*_sem.png): modelo upstream, hélices paradas
  ```
- **Na janela:** `--sem-helices` desliga a animação (mesma física) e é a única forma de a desligar. O site
  **mostra** as hélices: o `sim_site.py` lança o `sim_view.py` (`comando_do_runner`, `sim_site.py:1117`)
  **sem** essa flag e é o `sim_view.py` que faz `HoverEnv(helices=not args.sem_helices)`. Quem fica **sem**
  hélices é o `view.py` (viewer com HUD, `HoverEnv()` em `view.py:994` → `cf.Helices` inerte) e, por
  omissão, o RL/deploy (`cf.carregar()` e `HoverEnv()`). Para animar também o `view.py`, ele passa a
  `HoverEnv(helices=True)` e acrescenta `cf.Helices(env.model).atualizar(env.model, env.data, dt)`
  antes do `sync()` (não foi feito: fora do âmbito desta peça).

### Câmara da janela 3D — TERCEIRA-PESSOA contínua, comandada pelo site (v2, 2026-10-10)

A janela mostra SÓ o 3D e a **câmara** é comandada pelo site (bloco «Câmara», `INTERFACE.md` §3.5) — tal
como o vento, é **só apresentação**: nunca toca na física, no episódio nem em nenhum comando. Em v2 a
câmara é **terceira-pessoa de jogo**: o alvo segue SEMPRE o drone e o site só comanda ângulo + distância.

- **Contrato:** bloco `"camera"` do `out/controle_vento.json` = `{"azimute","elevacao","distancia",
  "seq"}` — **SEM `alvo`** (faixas: azimute finito normalizado mod 360, elevacao [−90,90]°, distancia
  ]0,20] m; `seq` incrementado a CADA comando pelo servidor, como o `dinamico.seq`) +
  **`POST /api/camera`** (8.ª rota; corpo = subconjunto de `{azimute, elevacao, distancia}` + alias
  `distandia`; sem `seq` obrigatório — o `seq` do corpo é **ignorado** e o servidor carimba sempre o
  seu; merge parcial que nunca toca em
  `loop`/`reiniciar`/vento) + `camera_padrao`/`camera_atual` em `GET /api/state` e `GET /api/sim`.
- **Alvo SEMPRE no drone (`seguir_drone`, a cada frame):** `viewer.cam.lookat =
  body(CAM_CORPO).xpos + CAM_OFFSET` — COLA EXACTA a 1e-9, sem suavização (sem lag). `CAM_CORPO = "cf2"`
  (corpo do drone por nome) e `CAM_OFFSET = (0, 0, 0)` m (somado elemento a elemento a `xpos`; mudá-lo só
  muda o ponto olhado — a física nunca é tocada). Prova escrita a escrita no `teste_camera.py` §2.
- **Aplicação no runner:** os 3 valores de orbitar/zoom aplicam-se UMA VEZ por mudança de assinatura
  (`seq`+valores) nos atributos do `viewer.cam` — nunca a cada frame e nunca no `lookat`; entre comandos
  **o rato do viewer continua livre** (ângulos/distância sobrevivem até ao próximo comando) mas o **PAN é
  sobreposto** pelo seguimento (o alvo não sai do drone); sem viewer (`--sem-janela`) ignora sem erro.
- **Telemetria:** a 19.ª chave `"camera"` traz a câmara **REAL** (`{azimute, elevacao, distancia, alvo}`
  com `alvo` = `lookat` real = drone+offset), ou `null` sem viewer — é dela que sai o `camera_atual`
  (honestidade: sem dados não se inventa).
- **Default explícito:** `CAM_PADRAO` (constante = os 3 valores de `mjv_defaultFreeCamera(model)` deste
  modelo, **sem `alvo`**; azimute guardado mod 360, 340 ≡ −20 = a mesma pose) é aplicado no arranque e
  publicado como `camera_padrao`; **REPOR VISTA** = enviar os valores de `camera_padrao` como um comando
  normal.
- **Convenção de sinais** (a peça do front copia-a tal e qual, `INTERFACE.md` §4.4):
  `pos = alvo − d·f(azim,elev)` · `alvo = pos + d·f` com
  `f = [cos(elev)·cos(azim), cos(elev)·sin(azim), sin(elev)]` (graus→rad; azim 0° = +x, 90° = +y; elev
  positivo põe a câmara abaixo do alvo a olhar para cima; em v2 `alvo` = drone+offset). Confirmada
  empiricamente contra a pose real da câmara (`MjvScene.camera`, média dos 2 olhos estéreo): desvio máximo
  5,7e-8 m em 6 poses.
- **Validação exata do `POST /api/camera` (v2):** campo **presente** com valor `null` → **400** (`null`
  não é «ausente» — só a ausência completa do campo mantém o valor em vigor); **chave desconhecida**
  (incl. o `alvo` do contrato v1) → **400**; fora de faixa → 400; `distancia`+`distandia` juntos → 400
  (ambíguo). **Decisão documentada:** `{}` e `{"seq": n}` são **aceites com 200** — o subconjunto vazio é
  um «toque» que mantém os valores e carimba `seq` novo, e o `seq` do corpo é um aviso do cliente
  **IGNORADO** (o servidor carimba sempre o seu; deixa reenviar um bloco lido tal e qual). Assimetria
  intencional: no **ficheiro**, chaves desconhecidas (ex. `alvo` de ficheiros v1) são ignoradas em
  silêncio pelo runner (ficheiros velhos não rebentam); no **HTTP** rebentam com 400.
- **Robustez do backend (mini-reparo 2026-10-09, achados de verificação independente)**: o servidor usa
  `FILA_LIGACOES = 64` (`request_queue_size` do `ThreadingHTTPServer`, não o 5 do stdlib): num burst frio
  de 40 ligações simultâneas o código de antes deixava POSTs por servir (medido: 26–39 de 40 por ronda,
  `ConnectionResetError`/sem resposta, as que passavam demoravam segundos) e o de agora serve e aplica
  120/120 em 3 rondas (0,03 s/ronda), sem resets e sem JSON partido.

Prova repetível (`teste_camera.py`, **50/50** — §1 peças do contrato v2 e convenção de sinais (17) · §2
ciclo real com viewer falso instrumentado: seguimento provado escrita a escrita com o drone a MOVER-SE
pela física (REINICIAR + empuxo), rato preservado, PAN sobreposto, telemetria (15) · §3 servidor real na
porta **8561** (13): **burst frio de 40 ligações × 3 rondas**, 8 rotas, 400s (chaves desconhecidas, `null`,
faixas, alias) e a decisão `{}`/`seq` · §4 não-tautologia por mutação (5): seguimento removido, posição
velha, assinatura sem `seq`, validação de desconhecidas removida e validação de `null` removida fazem o
§1/§2 FALHAR):

```bash
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_camera.py   # 50/50, exit 0
```

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
| ambiente por fórmulas fechadas | `run.py` | **146/146 [OK]**, 0 falhas · ≈ 3 300–5 400 passos de decisão/s num env, validação completa em ~5–6 s |
| animação visual das hélices | `run.py` §10 (13 checagens) + `helices_render.py` | hélices rodam ∝ √t_i com o sentido de `GIRO` e param com os motores desligados; **física idêntica AO BIT** (max\|Δ\| = 0) com a animação ligada/desligada e vs o modelo upstream · 2 imagens EGL em `out/helices_1.png` e `out/helices_2.png` |
| `HoverEnv` como `gym.Env` | `run.py` §5 | `check_env` do SB3, `reset(seed)` determinístico, `info` e truncagem corretos |
| robustez do ambiente | `run.py` §7 | não-finitos → `ValueError` (vento/ação/`alvo_z`), `alvo_z ∈ [0,10, 2,90] m`, divergência → `RuntimeError` |
| critério v2b (vento + orientação) | grelha 0–3 m/s × 4 azimutes × 3 seeds | **16/16 PASS, 0 terminações** — re-medido por um **agente independente** (16/16 e 32/32 na grelha densa própria) |
| câmara v2 (contrato, seguimento, servidor) | `teste_camera.py` | **50/50** — 17 peças do contrato v2 · 15 ciclo real com viewer falso · 13 servidor real · 5 não-tautologia |
| PARAR (nenhuma rajada sobrevive) | `teste_parar_vento.py` | **15/15** sem flags · **16/16** com `--http` · **18/18** com `--http --navegador` |
| arranque SEM REINÍCIO (loop/REINICIAR/controlo) | `teste_arranque_loop.py` | **68/68** (65 com `--sem-navegador`, 25 com `--sem-http`) |
| site — comandos/gestos de câmara | `npm run test:camera` (em `site/`) | **62/62** (20 round-trip + 42 gestos), mais a prova DOM/CDP **37/37** |
| suíte do laboratório | `uv run pytest .agents/mujoco-lab-agent-skill/tests -q` | **30 passed** |
| integração das peças (treino/UI/sonda/deploy) | verificação adversarial em 4 peças (v1) + 4 peças (v2) + 3 rondas de reparação | **9 PASS / 1 FAIL** (o FAIL era o `runs()` do `dashboard.py`; reparado e re-verificado) · v2: contratos todos PASS após reparações e re-verificações pontuais |

Condições de medida dos µs: máquina ociosa (`loadavg` 1 min **1,35** antes do benchmark, 1,44 depois);
o `deploy.py` regista o `/proc/loadavg` antes/depois em todos os relatórios exatamente por isso.

## Limites e nits conhecidos

**Planta real (2026-10-10)** — o que falta medir ou ainda não cobre:

- **SysID do hardware**: kf/kq/curva do ESC vêm das tabelas T-Motor (+7,5 % de realismo); J do rotor, R efetiva,
  download e arrasto de rotor são estimados (a DR cobre as faixas). Medir em banco (empuxo, binário, rpm, corrente
  a 6S) e o pack (capacidade a 1C, DCIR) — nenhuma alegação de baterias passou a verificação adversarial.
- **Massa do frame DIY** (235 g + 50 g de pernas) é estimada pela densidade do carbono: pesar e corrigir no catálogo.
- `view.py`, `dashboard.py`, `net_probe.py` e `helices_render.py` continuam a ser ferramentas do **cf2** (16 obs);
  a planta real usa o site (`sim_site.py`), o `train.py`, o `deploy.py` e o `valida_real.py`.
- O FC simulado faz a malha de TAXA (modo acro); modos de ângulo/altitude do firmware não são simulados — quem
  estabiliza atitude e posição é a política (a decisão do dono).
- Sem magnetómetro o rumo absoluto não é observável: a recompensa usa o rumo relativo ao do arranque.
- A autonomia de 99 min é de pairagem pura em ar parado; o caso real publicado mais próximo voou ~30 % abaixo
  da tabela — espere ~80–90 min.
- **O xy (~6 cm nominal, ~9 cm sob DR) é limitado pelo estimador de bordo**, não pela política: ela segura a posição
  ESTIMADA a 1–5,5 cm, e a odometria por fluxo ótico deriva 2–11 cm da verdade em 10 s (medido; ver os
  resultados acima). Melhorar o estimador (Kalman fluxo + acelerómetro, escala do fluxo calibrada) ou dar-lhe uma
  referência absoluta vale mais do que treinar mais.
- **O treino corre em PyTorch (Stable-Baselines3)**, a stack do laboratório — não em TensorFlow. Os dados das peças
  entram no treino pelo ambiente (física gerada do catálogo, DR à volta dos valores das peças, `hardware.json` ao
  lado de cada política); o que vai para o RPi é um ONNX neutro (onnxruntime). Quem preferir TensorFlow Lite pode
  converter esse ONNX (ex.: `onnx2tf`) — não testado aqui.


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
6. **Planta real — do simulador ao drone**: (a) SysID em banco dos motores/hélices/ESC e do pack (corrigir o
   catálogo com os valores medidos e re-treinar com o mesmo comando); (b) melhorar o estimador de bordo (é ele que
   limita o xy); (c) medir no RPi 5 real a latência do ator (1, 21) e o jitter do loop a 50 Hz com o FC por UART;
   (d) voo cativo (preso por um cabo) antes do primeiro voo livre.

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
