# O padrão do DRONE — o que é, para que serve e como tudo se integra
> Documento de arquitetura do laboratório. Explica **um** experimento — o drone
> (`experiments/09_drone_hover_rl/`) — como **implementação de referência** do padrão que este
> laboratório usa para **qualquer** robô: do modelo pronto do GitHub até uma política a correr num alvo
> real, passando por física validada, treino por RL e uma interface de operação.
>
> Verificado contra o código e os artefactos em disco a **2026-10-08**. Onde os documentos do repositório
> e o código divergem, este documento diz qual é o caso real (ver §9).
>
> **Errata 2026-10-09** — isto é o registo datado de 2026-10-08 (a fotografia; o documento vivo é
> [`docs/o-padrao-do-drone.md`](docs/o-padrao-do-drone.md)), e o experimento mudou depois. Duas correções ao
> que se lê abaixo: **(1) o `loop` mudou de semântica** — `true` = **CONTÍNUO** (o runner reinicia sozinho no
> fim do episódio) e `false` / `--sem-loop` = **SEM REINÍCIO** (a física **nunca pára nem reinicia**: no fim
> do episódio continua a integrar no estado em que ficou, com `passo` e `t` a crescer e o `retorno` fixo);
> o **REINICIAR** (contador `reiniciar`) é o único reset e vale com e sem `loop`; o `loop` é **sticky**
> (`--sem-loop` é autoritativo no arranque e depois só o `POST /api/loop` o muda; escritas parciais nunca
> tocam em `loop`/`reiniciar`); `episodio_terminado` na telemetria quer dizer «o episódio fechou, a física
> continua» — **não** que a física parou. **(2) os modos de vento dinâmico são** `nenhum`, `rajadas`,
> `aleatoria`, `frente`, `dryden` e `rajada_agora` (rajada única): o `aleatoria` (novo) faz rajadas com
> direção e força **totalmente aleatórias** dentro das faixas disponíveis (U[0, 5] m/s, azimute U[0, 360°),
> elevação U[±90°]), aplicadas por **mistura** `base + sin(π·k/(N+1))·(rajada − base)`, com `p`/`duracao`
> (0,02 / 10), **live-apply ≈300 ms** no site e `u_max = 0` inerte em todos os modos. A telemetria passou a
> **18 chaves** (15 campos + `loop`, `vento_modo` e `ctrl`), publicada a ~10 Hz sempre.
---
## 1. Em uma página
O **padrão do drone** é a resposta a uma pergunta prática: *como é que eu pego um robô que não é meu, faço-o
mexer-se numa física que eu confio, aprendo uma política que o controla, e vejo/operho isso como um produto
— sem mentir a mim mesmo em nenhum passo?*
A resposta tem **sete camadas**, e cada camada tem um contrato estrito:
```text
┌──────────────────────────────────────────────────────────────────────────────┐
│  7. DEPLOY       deploy.py   → ONNX → validação numérica → benchmark → multi-IA│
│  6. INTERFACE    sim_site.py → UM comando: janela 3D LIMPA + site (5+1 rotas) │
│  5. RL           train.py    → PPO + currículo de vento + domain randomization│
│  4. AMBIENTE     env.py      → Gymnasium: obs, ação, recompensa, vento físico │
│  3. EXPERIMENTO  run.py      → validação por fórmulas fechadas, exit 0/1      │
│  2. CAMADA LAB   lab/*.py    → sensores + controles + leituras (só runtime)   │
│  1. MODELO       models/*    → vendorizado do upstream, INTACTO               │
└──────────────────────────────────────────────────────────────────────────────┘
        ↑ todas as camadas obedecem a uma regra transversal:
          SIMULADOR SEMPRE FÍSICO (tudo passa por mj_step)
```
**O que este padrão serve para produzir**, concretamente, no caso do drone: uma política de rede neural
(MLP 16→64→64→4) que faz um **Crazyflie 2 subir do chão e pairar a 1 m**, com **posição e orientação
fixas**, **resistindo a vento até 3 m/s** — validada em **57/57** condições do critério do dono e
**144/144** num stress denso, com **zero quedas**, e exportada para ONNX a correr em 4,67 µs (p50) por
inferência.
**Porque é que isto é um *padrão* e não um *projeto*:** as sete camadas são independentes e reutilizáveis.
O `models/` e o `lab/` já servem dois robôs diferentes (o drone e o Spot quadrúpede). O `env.py`/`train.py`/
`sim_site.py`/`deploy.py` foram **empacotados** no template `lab-padrao` da skill, e o
`new_experiment.py --template lab-padrao` gera um experimento novo já com as sete camadas montadas.
O drone é a **prova de que o padrão fecha ponta a ponta** — é a base a copiar.
---
## 2. As sete camadas, uma a uma
### Camada 1 · `models/<robo>/` — o modelo, vendorizado e **intacto**
**O que é:** uma cópia de um modelo MJCF de boa reputação, trazida do GitHub e guardada **exatamente como
veio**. No caso do drone, `models/bitcraze_crazyflie_2/` — o Crazyflie 2 do
[mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/main/bitcraze_crazyflie_2)
(MIT), com XMLs, malhas, `LICENSE`/`README`/`CHANGELOG`.
**O contrato:** *nunca* se edita um ficheiro upstream. Nem um atributo. A razão é de engenharia: se o
modelo local divergir do original, deixa de ser possível comparar o que medimos com o que a comunidade
mede — e um dia o upstream muda e já não sabemos o que tínhamos.
**O que o `cf2.xml` já traz de fábrica** (e que é a base física de tudo, `models/bitcraze_crazyflie_2/cf2.xml`):
| linha | conteúdo | porque importa |
|---|---|---|
| 2 | `<option integrator="RK4" density="1.225" viscosity="1.8e-5"/>` | **o arrasto aerodinâmico já existe** (densidade e viscosidade do ar). O drone não "desliza" no vácuo; é um corpo num fluido. |
| 118 | `body_thrust` `ctrlrange="0 0.35"` `gear="0 0 1 0 0 0"` | o canal de empuxo, em N, escrito no eixo **z** de um *wrench* 6D. |
| 119–121 | `x/y/z_moment` `ctrlrange="-1 1"` `gear="...-0.00001..."` | os 3 canais de momento, com gear `1e-5` — que o README do menagerie admite ser *"arbitrary"*. |
| 130–132 | `<keyframe>` com a pose `hover` | a pose de partida (é de onde o `reset` larga o drone). |
Nota fina: os quatro atuadores são do tipo **`motor` com `gear` de wrench 6D** — não são "4 hélices" com
`ctrl` em rpm. São **4 canais de força/binário**: empuxo + 3 momentos. É isso que a camada `lab/` tem de
respeitar.
### Camada 2 · `lab/<robo>.py` — a camada de adaptação, **toda em runtime**
**O que é:** um módulo Python que compila o modelo upstream e **acrescenta-lhe o que falta**, sem tocar em
disco. No drone: `lab/crazyflie.py` (252 linhas).
**O contrato do padrão** (quatro famílias de funções, todas documentadas no `SKILL.md`):
```python
carregar()            → (model, data)   # compila + injeta sensores; devolve o par pronto
definir_*()           → unidades FÍSICAS, cortadas às faixas do modelo
MODOS                 → roteiros ABERTOS f(model, data, tau), SEM realimentação
ler_*()               → leituras de sensores, em unidades SI
```
**Regra dura desta camada:** não há cá código pronto de estabilização, controlo, IK, marcha ou voo. Nada de
PD, nada de PID, nada de "sobe e mantém". O `lab/` dá **acesso** ao robô; os **algoritmos são do dono**.
**Sensores injetados em runtime via `MjSpec`** (`lab/crazyflie.py:99`, `_adiciona_sensores`): o modelo
upstream não tem posição nem velocidade absolutas, por isso a camada cria um `site` chamado `cm` no centro
de massa e dois sensores que o medem:
```python
corpo.add_site(name="cm", pos=[0, 0, 0], size=[0.005])
spec.add_sensor(name="posicao", type=mjSENS_FRAMEPOS,   objtype=mjOBJ_SITE, objname="cm")
spec.add_sensor(name="vel",     type=mjSENS_VELOCIMETER, objtype=mjOBJ_SITE, objname="cm")
```
Isso junta-se aos sensores **nativos** do modelo. O conjunto final (`SENSORES`) é:
| sensor | grandeza | frame |
|---|---|---|
| `body_gyro` | velocidade angular (rad/s) | corpo |
| `body_linacc` | aceleração própria (m/s²) | corpo |
| `body_quat` | orientação, quaternion `[w x y z]` | mundo |
| `posicao` | posição do **CM** (m) — ➕ injetado | mundo |
| `vel` | velocidade linear (m/s) — ➕ injetado | mundo |
Ou seja: o drone tem a **IMU completa + posição/velocidade** exatamente como o padrão pede ("drone → IMU +
posição/velocidade"). São *ground truth* para algoritmos e treino — nunca controlo.
**A constante que o próprio upstream admite ser arbitrária.** O `ctrlrange` do empuxo vale `0.35 N`, e o
README do menagerie classifica-o de *"arbitrary and need to be further tuned"*. Com 0,35 N e 27 g de massa
dá **T/W = 1,32** — o drone mal sai do chão. O datasheet real do Crazyflie 2.1 dá 4 × 15 gf ≈ **0,589 N**,
logo **T/W ≈ 2,22**. É por isso que o `env.py` tem `THRUST_MAX_REAL = 0.589` e um interruptor
`thrust_realista=True` (padrão) — e a checagem 1 do `run.py` cobre o caso `False`, que reproduz o
comportamento do upstream. **O XML em disco nunca é tocado**: a faixa do empuxo e o gear dos momentos
são reescritos só na cópia do modelo em memória.
**O trap dos atuadores de múltiplas entradas.** Isto é a armadilha mais importante da camada. Os 4 canais
não são 4 atuadores independentes de 1 entrada: são atuadores cujo `gear` é um **wrench 6D**. Escrever
`data.ctrl[i]` com o índice do atuador *funciona por acaso* aqui (porque `nu == nactuator == 4`), mas o
valor certo não é o valor físico — é o valor físico **dividido pelo gear**. A camada resolve isto com
`GEAR_EIXO` (o índice do componente dentro do wrench) e `_slot()`, que devolve a posição real em
`data.ctrl`, o gear escalar e os limites físicos:
```python
GEAR_EIXO = {"body_thrust": 2, "x_moment": 3, "y_moment": 4, "z_moment": 5}  # fx fy fz tx ty tz
def _slot(model, nome):        # → (adr, gear, lo, hi);  lo/hi = ctrlrange × gear
```
E é isso que faz `definir_empuxo(model, data, newtons)` ser honesto: recebe **newtons**, corta à faixa
física e escreve `data.ctrl[adr] = v / gear`. O resultado é que `data.ctrl` fica 1:1 em unidades físicas
([N] e [N·m]) — o que torna a telemetria legível e o `run.py` capaz de validar por fórmulas fechadas.
**A API completa do drone** (`lab/crazyflie.py`):
| função | assinatura | devolve / notas |
|---|---|---|
| `carregar` | `(cena=True, sensores=True, keyframe="hover", momentos="fisico", energia=True)` | `(model, data)` pronto a simular. `sensores=True` injeta `posicao`/`vel`; `momentos="fisico"` escala o gear dos momentos para a faixa física (o `"nativo"` preserva o gear upstream ±1e-5); `energia=False` é **só** para MJX (`mjx.put_model` não implementa `mjENBL_ENERGY` — e com a flag desligada o `data.energy` fica a **zeros em silêncio**) |
| `definir_empuxo` | `(model, data, newtons)` | empuxo **aplicado** (N), após corte |
| `definir_momentos` | `(model, data, mx, my, mz)` | 3 momentos aplicados (N·m), após corte |
| `definir_wrench` | `(model, data, empuxo, momentos)` | empuxo + momentos de uma vez |
| `comandar_rotores` | `(model, data, empuxos)` | **mixer** de 4 rotores → wrench (configuração X) |
| `desligar` | `(model, data)` | motores a zero (queda livre) |
| `hover` | `(model, data)` | empuxo = peso (`0,26487 N`); equilíbrio **aberto** |
| `MODOS` | dict de 7 roteiros | `desligado`, `hover`, `empuxo`, `momento_x/y/z`, `rotores` — `f(model, data, tau)`, **sem realimentação** |
| `ler_imu` | `(model, data)` | `{giro, acc, quat}` |
| `ler_estado` | `(model, data)` | `{pos, vel, vel_ang}` |
| `ler_motores` | `(model, data)` | `{empuxo, momentos, ctrl}` **em unidades físicas** |
| `ler_tudo` | `(model, data)` | tudo junto + `qpos` |
**O mixer é física, não controle.** `comandar_rotores` converte 4 empuxos de rotor no wrench do corpo,
com a geometria medida na própria malha:
```python
F_z = Σ tᵢ          τ_x = Σ r_y·tᵢ          τ_y = −Σ r_x·tᵢ          τ_z = Σ giroᵢ·KM·tᵢ
POS_ROTORES = ((0.0325, 0.0325), (0.0325, -0.0325), (-0.0325, 0.0325), (-0.0325, -0.0325))  # FL FR RL RR
GIRO = (1.0, -1.0, -1.0, 1.0)       # pares CW/CCW nas diagonais → sinal do yaw
KM = 0.016                          # m — razão momento-de-reação/empuxo (parâmetro livre)
```
Constantes derivadas (`lab/crazyflie.py:39-56`): `MASSA = 0.027 kg` · `PESO = MASSA·9.81 = 0.26487 N` ·
`EMPUXO_MAX = 0.35 N` (upstream) · `BRAÇO = 0.0325 m` · `T_ROTOR_MAX = 0.0875 N` ·
`MOMENTOS_MAX = (5.69e-3, 5.69e-3, 2.80e-3) N·m`.
### Camada 3 · `experiments/NN_nome/` — o experimento que se auto-valida
**O que é:** a pasta do experimento, com o `run.py` a ser a peça central. No drone:
`experiments/09_drone_hover_rl/`.
**O contrato:** o `run.py` valida por **fórmulas fechadas em condições isoladas** — cada checagem usa um
**modelo fresco** (o `env.py` compila o seu próprio `MjModel` em cada `HoverEnv(...)`), impõe estados à mão
e compara com o que a teoria diz, **sem histórico de simulação** — e sai com **exit 0/1**.
No drone são **121 checagens** em 8 secções:
| secção | o que prova |
|---|---|
| 1 · ação → `ctrl` | o mapeamento em unidades físicas, com cortes, e o caso `thrust_realista=False` |
| 2 · recompensa | cada termo da equação isolado à mão; o bónus **nos limiares exatos**; terminação → −100; e a recompensa do `step` contra uma implementação **independente** |
| 3 · física | empuxo = peso paira (`|Δz| < 2 mm` em 1 s); `a=+1` sobe; `a=−1` desce; vento lateral não muda a altitude |
| 4 · vento | `definir_vento` escreve `opt.wind` e o drone **deriva** (física de fluido real); `vento_aleatorio` amostra por reset; `vento=None` → ar parado |
| 5 · observação | forma (16,), escalas por bloco, coerência do bloco de yaw, transformação mundo→corpo, ruído |
| 6 · Gymnasium | `reset(seed)` determinístico (incluindo o vento sorteado), `info` com 8 chaves, truncagem, e o **`check_env` do Stable-Baselines3** |
| 7 · contrato do modelo | `nu`, sensores, `dt`, `decimation`, `ctrladr` 1:1 — e **`cf2.xml` upstream intacto** |
| 8 · vento dinâmico | `rajadas` contra o envelope `u·sin(π·k/(N+1))`, `frente` com o degrau em `floor(t_s/0,02)+1`, `dryden` contra o OU `x ← α·x + σ·√(1−α²)·ξ` |
Duas ideias que valem a pena reter: (a) a secção 7 **verifica por hash/atributo que o XML upstream não foi
tocado** — o contrato da camada 1 é testado, não só prometido; (b) a secção 2 compara a recompensa do
`step` com uma **reimplementação independente** da fórmula, que é a defesa contra "o código concorda
consigo mesmo".
### Camada 4 · `env.py` — o ambiente Gymnasium (onde vive a física do problema)
**O que é:** `HoverEnv` (875 linhas) — o contrato que todas as outras peças importam. É a peça mais
importante da camada de RL, porque é aqui que se decide **o que a política vê, o que pode fazer, e o que
lhe interessa**.
**Física:** `dt = 0,002 s` (**500 Hz**, integrador RK4) × `decimation = 10` → **50 Hz de decisão**.
Um passo de política = 10 passos de física. Episódio de **10 s = 500 passos de decisão**.
**Observação `(16,)` — normalizada no próprio ambiente.** Não há `VecNormalize`: isto é uma **decisão de
desenho**, e o motivo é o deploy — assim o grafo ONNX fica **puro**, sem estatísticas de corrida agarradas
a um wrapper.
| índice | conteúdo | escala |
|---|---|---|
| `[0:3]` | `p − p_alvo` (posição do CM) | ÷ 1 m |
| `[3:6]` | `roll, pitch, yaw` do quaternion | ÷ π |
| `[6:9]` | velocidade no **frame do corpo** | ÷ 1 m/s |
| `[9:12]` | velocidade angular (corpo) | ÷ 10 rad/s |
| `[12:16]` | **ação anterior** | já em `[-1, 1]` |
**Ação `(4,)` — centrada no hover.** Este é um detalhe de projeto que economiza capacidade de política:
```text
a₀ ≤ 0:  empuxo = mg · (1 + a₀)                  (a₀ = −1 → 0 N;  a₀ = 0 → mg = hover)
a₀ > 0:  empuxo = mg + (thrust_max − mg) · a₀    (a₀ = +1 → thrust_max)
momentos_i = 0,1 · momento_max_i · a_i           (tau_escala = 0,1 → 10 % da autoridade máxima)
```
`a = 0` **é** o hover. A caixa é assimétrica em torno do zero **de propósito**: a metade "para baixo" só
precisa de cobrir o peso, a metade "para cima" tem de cobrir o dobro. Sem isto, a política gastaria parte
da sua capacidade a redescobrir a gravidade.
**Recompensa v2b** — a versão que resultou de uma campanha falhada inteira (§5):
```text
r = −1,0·‖xy‖ − 1,0·|z − alvo_z| − 0,2·|yaw_err| − 0,05·‖v‖ − 0,05·‖ω_xy‖
    − 0,1·|ω_z| − 0,05·‖Δa‖
    + 1,0 · 𝟙[ ‖xy‖ < 0,05 ∧ |z − alvo_z| < 0,05 ∧ |yaw_err| < 0,10 ]
    − 100 · 𝟙[ terminou ]
```
Cada termo tem uma história: `‖xy‖` com peso 1,0 (dez vezes a v1) *prende* o drone no mesmo ponto;
`yaw_err` a 0,2 é o "**não girar**" (o alvo de guinada é 0); `‖Δa‖` a 0,05 é a **penalidade de taxa de
ação** — o remédio padrão para *chatter*, e o termo que salvou a campanha (era 0,01).
**Terminação** (não confundir com truncagem): `z < 0,005 m` (caiu), `max(|φ|,|θ|) > π/2` (capotou) ou
`z > 3 m` (subiu demais). A truncagem aos 500 passos **não** é terminação e não leva a penalidade.
**O vento é físico, e isto é o coração do realismo.** O vento **não** é uma força somada à mão. É o
mecanismo oficial do MuJoCo: o vetor **velocidade do ar** (`model.opt.wind`, frame mundo, m/s), que o
solver de fluido subtrai à velocidade do corpo no cálculo do arrasto inercial. Como o `cf2.xml` já traz
`density`/`viscosity`, o arrasto já existia — faltava a corrente de ar. É física a sério, dentro do
`mj_step`; o chão é estático e imune.
| API | unidades | comportamento |
|---|---|---|
| `HoverEnv(vento=(vx,vy,vz))` | cartesiano (m/s) | vetor mundo fixo no episódio |
| `HoverEnv(vento_aleatorio=(u_min,u_max))` | m/s | **DR por episódio**: norma U[u_min,u_max], azimute U[0,360°), elevação U[−20°,+20°], semeado por `np_random` |
| `definir_vento(vel, azimute_graus, elevacao_graus)` | **polar** | reescreve `opt.wind` **já** — o episódio em curso sente logo |
| `definir_vento_dinamico(config)` | — | o vento passa a mudar **dentro** do episódio (§ abaixo) |
Magnitudes de referência (m = 27 g, W = 0,265 N): a **3 m/s** o arrasto inercial vale ≈10 % do peso; a
5 m/s ≈29 %.
**Vento dinâmico (ronda 10)** — três modos, validados por `env.valida_vento_dinamico()`:
| modo | o que faz a cada passo de decisão (50 Hz) |
|---|---|
| `rajadas` | com prob. `p` (0,02) sorteia uma rajada que **soma** ao vento base durante `duracao` (10 passos = 0,2 s) |
| `frente` | no instante `t_s` (2,0 s) chega uma frente que **substitui** o vento base até ao fim |
| `dryden` | **turbulência** OU de 1.ª ordem (filtro de Dryden discreto), saturada em ±`u_max` |
Detalhe de desenho que denuncia cuidado: **`u_max = 0` é inerte nos três modos** e, importante, **não
consome o `np_random`** — logo um estágio sem vento é indistinguível do contrato v2b. Sem essa guarda, os
modos não-`rajadas` consumiriam números aleatórios e mudariam silenciosamente o comportamento.
**O `reset` não teleporta — e isto é a regra do dono a aparecer no código.** O reset faz
`mj_resetDataKeyframe` (keyframe `hover`, z = 0,1 m), **zera o `ctrl` (motores desligados)**, aplica
jitter determinístico (xy ± 2 cm, yaw ± 5°) e depois **deixa a física assentar o drone** — a queda de ~9 cm
corre em `mj_step` até 10 passos consecutivos com `z < 5 cm` e `‖v‖ < 1 mm/s`. O drone começa o episódio
**pousado** (z ≈ 0,0125 m). Com vento, o assentamento corre **em ar parado** e o vento entra logo depois:
o estado inicial é sempre uma pose estável, e a política tem de **descolar e recuperar** contra o vento que
chega. Nota fina: o keyframe do lab trazia `ctrl = peso`, e o `reset` **zera-o** — é literalmente "motores
desligados" como manda a regra.
**Guardas de honestidade numérica:** ação não finita → `ValueError` **sem corromper o estado**; estado a
divergir (NaN/inf, posição > 1e3 m, velocidade > 1e3 m/s) → **`RuntimeError`** com uma mensagem que
explica que um `reset()` sozinho não chega se a causa for vento absurdo. A alternativa — devolver
recompensa NaN com `terminated=False` para sempre — envenenaria o treino em silêncio.
### Camada 5 · `train.py` — a aprendizagem (PPO + currículo + DR)
**O que é:** PPO (Stable-Baselines3, `MlpPolicy` MLP **64×64 tanh**) sobre o `HoverEnv`, em
`SubprocVecEnv`, headless.
**Como o padrão ataca um problema difícil — vento — em vez de o sofrer:**
1. **Domain randomization por episódio** — cada `reset` sorteia um vento (norma, azimute, elevação).
2. **Currículo de vento** — `--curriculo-vento 0,1,2,3` sobe o teto do DR em estágios, e **só avança
   quando a política atinge o critério** (`frac_xy_z ≥ --avanco-frac`).
3. **`--retomar`** — fine-tune a partir de um checkpoint, em vez de treinar de zero.
4. **Vento dinâmico no treino** — `--vento-dinamico rajadas|frente|dryden`, mudando **dentro** do episódio.
**Defaults reais do CLI** (fase v2b): `n_envs 8`, `n_steps 512`, `lr 1e-4`, `ent_coef 0,001`,
`log_std_init −0,5`, `weight_decay 1e-4`, `--curriculo-vento 0,1,2,3`.
Duas armadilhas do SB3 que o código trata explicitamente e que valem como aviso: o `EvalCallback` conta
**chamadas do callback**, e cada chamada é um passo do *vec* (`n_calls = timesteps / n_envs`), não um passo
de ambiente; e o `learn()` tem `reset_num_timesteps=True` por omissão — no fine-tune tem de ser `False`,
senão o contador reinicia e o treino recomeça do zero.
Telemetria: `train_log.jsonl` com **13 campos** por avaliação, incluindo `u_vento` (o teto do estágio) e
`frac_no_alvo`.
### Camada 6 · `sim_site.py` — o padrão de interface `padrao-simulacao-clean-site`
**Esta é a camada que transforma o experimento num produto operável.** A regra do dono, instituída em
2026-10-08, é uma só frase:
> **A janela mostra a simulação. O site mostra tudo o resto.**
E ela é implementada de forma absoluta:
**A janela é 100 % limpa** (`sim_view.py:765-773`):
```python
with mjviewer.launch_passive(env.model, env.data, key_callback=teclas.ao_teclar,
                             show_left_ui=False, show_right_ui=False) as viewer:
    viewer.clear_texts()      # garante zero overlay (nunca se usa set_texts)
```
Zero HUD, zero texto, zero gráfico, zero painel. As **únicas** teclas são **ESPAÇO** (pausa/retoma) e
**Q/Esc** (fecha) — porque o vento, o REINICIAR e o LOOP são do site, e é isso que mantém o 3D limpo.
**Um comando arranca as três coisas** (`sim_site.py`):
```bash
uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py
```
1. o **runner** `sim_view.py` como **subprocesso** — é ele que abre a janela limpa e escreve a telemetria;
2. um **servidor HTTP local (só stdlib)** que serve o site (`site/dist/`) e a API JSON;
3. imprime o URL (`[site] site em http://127.0.0.1:8080`) e **abre o browser**.
**Escolha do modelo por cascata** — se não se passar `--model`, o `sim_site.py` procura, por ordem: (1) o
modelo da **última validação com sucesso** em `out/avaliacao_vento/*.json` que ainda exista em disco
(hoje o campeão r10); (2) o `out/vento_*/final.zip` mais recente; (3) `out/runs/*/final.zip`; (4) qualquer
`best_model.zip`. **O motivo da escolha sai impresso no arranque** — não há magia silenciosa. Se a porta
estiver ocupada, tenta a seguinte e imprime o URL real. `Ctrl+C` fecha servidor **e** runner, sem órfãos.
**A comunicação é por dois ficheiros, não por sockets.** Esta é a decisão de arquitetura central:
```text
   site (browser)  ──POST /api/…──▶  servidor  ──escrita ATÓMICA──▶  out/controle_vento.json
                                                                             │
                                                              (o runner lê a CADA passo de decisão)
                                                                             ▼
   site (browser)  ──GET /api/sim──▶  servidor  ◀──escrita c/ flush──  out/sim_telemetria.jsonl
```
**`out/controle_vento.json` — o site escreve, o runner lê** (7 campos, escrito **atomicamente** com
`tmp` + `os.replace`, portanto o runner nunca lê um ficheiro meio escrito):
```json
{"vel":0.0,"azimute":197.0,"elevacao":-41.0,"ativo":false,"reiniciar":6,"loop":true,"t":1791511585.19}
```
| campo | significado |
|---|---|
| `vel` | velocidade do vento, 0–5 m/s |
| `azimute` | direção horizontal, 0–360° (**0° = +x, 90° = +y**, anti-horário) |
| `elevacao` | componente vertical, −90…90° |
| `ativo` | `false` ⇒ vento **0** na física (direção/força ficam guardadas) |
| `reiniciar` | **contador inteiro**; quando **muda**, o runner faz `env.reset()` — é o **ÚNICO** caminho para recomeçar |
| `loop` | `true` liga o auto-reset no fim do episódio; **campo ausente = não mexe** — *(errata 2026-10-09: `true` = CONTÍNUO, `false`/`--sem-loop` = SEM REINÍCIO, a física nunca pára nem reinicia; sticky, só o `POST /api/loop` o muda; ver a nota no topo)* |
| `t` | carimbo de tempo (informativo) |
| **`dinamico`** | *(opcional, acrescentado na ronda 10)* `{modo, params, ativo, seq}` — liga o **vento dinâmico ao vivo** (`rajadas`/`frente`/`dryden`/`nenhum`) **sem reiniciar o episódio**. Ver §9, ponto 1 — *(errata 2026-10-09: os modos são `nenhum`/`rajadas`/`aleatoria`/`frente`/`dryden`, mais `rajada_agora`; ver a nota no topo)* |
O runner deteta mudanças pela assinatura `mtime_ns + tamanho` — logo **escrever o ficheiro à mão também
funciona** (é um contrato de ficheiro, não uma API privada). E o padrão de "campo ausente = não mexe"
aplica-se a `loop`, `reiniciar` e `dinamico`: um ficheiro escrito à mão só com `{"vel":2}` continua
válido e não reinicia nada nem desliga o loop.
**`out/sim_telemetria.jsonl` — o runner escreve, o site lê** (15 campos, uma linha JSON por amostra,
sempre com `flush`):
| campo | significado |
|---|---|
| `t` | tempo de **simulação** do episódio (s); volta a 0 em cada reset |
| `estado` | `a_correr` ou `episodio_terminado` |
| `ep` · `passo` | nº do episódio · passo de decisão (0–500 = 10 s a 50 Hz) |
| `retorno` | recompensa v2b acumulada |
| `z` · `dist_xy` · `yaw_err` | as **3 métricas** de voo |
| `vento_vel` · `vento_azim` | vento **em vigor na física** (não o slider) |
| `obs` (16) · `act` (4) | o que a rede viu · o que a rede mandou (média crua) |
| `ctrl` (4) | o comando **físico** que a ação produziu: `[empuxo N, mx, my, mz N·m]` |
| `h1` (64) · `h2` (64) | ativações das camadas escondidas, **na mesma linha** que `obs`/`act` — logo alinhadas |
Cadência: **~10 Hz** com o episódio a correr, **1 Hz** com ele parado (batimento, porque o estado não
muda) e **uma linha imediata** no instante em que termina.
**A API: 5 rotas documentadas — mas são 6 no código.** Ver §9 (é a única divergência real que encontrei
entre a documentação e a implementação).
| rota | resposta |
|---|---|
| `GET /api/sim` | estado do episódio + vento + as **≤200** últimas amostras da telemetria |
| `GET /api/state` | resumo: `sim_vivo`, `pid`, `porta`, `amostras`, `idade_telemetria_s`, `loop`, `reiniciar`, `modelo` + `modelo_nome` |
| `POST /api/vento` | `{vel,azimute,elevacao}` (qualquer subconjunto; faixas 0–5 / 0–360 / −90..90; NaN/inf → **400**) |
| `POST /api/reiniciar` | incrementa `reiniciar` → `{"contador": n}` |
| `POST /api/loop` | `{"ativo": bool}` → liga/desliga o auto-reset |
| **`POST /api/vento-dinamico`** | **`{modo, params?, ativo?}`** — liga a dinâmica de vento ao vivo, **sem** reiniciar o episódio (o site usa-o; ver §9) |
| `GET /` e `/assets/...` | o site de `site/dist/`; caminho desconhecido → `index.html`; **path traversal → 404** |
Estados honestos: **400** (valor/faixa inválidos, com `{"erro","codigo"}`), **404** (rota/asset/traversal),
**500** (falha interna — nenhum pedido mata o servidor). No site, quando não há dados mostra-se «—»,
**nunca números inventados**.
**(2026-10-08) Sem auto-loop, e isto era uma decisão de operação, não uma limitação.** No fim do episódio
(`terminated` ou `truncated`) a física **parava no estado em que estava** — era essa a semântica da altura:
a janela continuava viva, o drone ficava onde estava e não havia episódio seguinte nenhum; só o
**REINICIAR** do site (ou `loop: true` / `--loop`) recomeçava. **Errata 2026-10-09:** isto já não é assim —
hoje `loop: true` = **CONTÍNUO** (o runner reinicia sozinho no fim do episódio) e `false` / `--sem-loop` =
**SEM REINÍCIO**, em que a física **continua a integrar** no estado em que ficou (nunca pára nem reinicia) e
o REINICIAR é o único reset; ver a nota no topo. O runner imprimia a geometria completa aqui — quem
estivesse a ver percebia *como* o episódio acabou.
**O site** (`experiments/09_drone_hover_rl/site/`) é React 19 + Vite 8 + Tailwind 4, construído com a
skill **`motion-plus-ui`** (registry `@motion`), com **polling a `GET /api/sim` a 2,9 Hz**
(`INTERVALO_POLLING_MS = 350`) — **sem websockets**. Uma página, duas colunas: **métricas** (esquerda) e
**controlos** (direita, `sticky`).
| zona | conteúdo |
|---|---|
| cabeçalho | título · **selo de estado** (`a correr` / `episodio_terminado`) · selo de ligação (`API ligada` / `à espera` / `API em baixo`) · contadores (`ep`, `passos`, `retorno`) · **modelo em uso** |
| 4 curvas | `z(t)` (com linha de alvo 1,0 m) · `yaw_err(t)` · `retorno(t)` · `vento_vel(t)` |
| rede ao vivo | **16 → 64 → 64 → 4**, cada retângulo um neurónio; cor/opacidade = `|ativação|` normalizada ao máximo da camada; **primary** = positiva, **destructive** = negativa |
| obs + ação | tabela das 16 obs (valor normalizado **e** cru) + cartão da ação com empuxo em N (com traço de referência no hover) e momentos em mN·m |
| controlos | sliders de força/azimute/elevação + **rosa dos ventos** (SVG) · **APLICAR VENTO** (`multi-state-button`) · **PARAR VENTO** · **REINICIAR** (`hold-to-confirm`, manter ~1 s) · **LOOP** (`segmented-toggle`, OFF por omissão) |
Dois detalhes que revelam a filosofia: a rede **não desenha arestas** entre neurónios, porque o contrato de
telemetria traz **ativações, não pesos** — desenhar ligações seria inventar dados; e sem ativações a
legenda do cartão di-lo literalmente, em vez de fingir zeros. O **REINICIAR** exige manter o botão ~1 s
(`hold-to-confirm`) para não reiniciar por clique acidental.
### Camada 7 · `deploy.py` — do `.zip` ao alvo real
**O que é:** o caminho de saída — política → ONNX → validação numérica → benchmark → multi-IA. Tudo **CPU,
sem render**.
| passo | o que faz | número medido |
|---|---|---|
| **export ONNX** | exporter *legacy* (`dynamo=False`), entrada **estática `(1,16)` float32**, opset **17** | `policy.onnx`, 23 507 B, IR 8, `onnx.checker` OK |
| **validação** | grafo vs **média da gaussiana** da política, sobre 1 024 obs **reais** | `max|Δ| = 5,72e-06` (limiar 1e-5) |
| **benchmark** (proxy de 1 core) | `intra_op_num_threads=1`, p50/p99/max | **4,67 µs p50** · 5,06 µs p99 · 212 320 inferências/s |
| **int8** | `quantize_dynamic` | 6,03 µs — **mais lento** que fp32 (0,24–0,77×) no x86 |
| **multi-IA** | 4 processos a 50 Hz, cada um com a sua sessão ORT | p99 **241,5 µs** · **0 perdas** de deadline em 1 996 iterações |
Três lições embutidas nesta camada: (a) o que se compara é a **ação determinística** (a média), **não** uma
amostra — e o `max|Δ|` de 10,17 contra `model.predict` **não é erro numérico**, é o `predict` a cortar a
ação a `[-1,1]` e o grafo a não cortar; (b) o `EvalCallback`/grafos não cortam, quem corta é o `env`; (c) a
latência é de um **proxy x86**, não do Raspberry Pi 5 — e o estudo externo citado indica que no
Cortex-A76 quem compensa é a quantização **estática**, precisamente a variante que este experimento **não**
usa. O `deploy.py` regista o `/proc/loadavg` antes e depois em todos os relatórios exatamente por isso.
**A regra de ouro do alvo:** o limite de 1 core aplica-se **na RUN**; o **treino** usa o poder máximo
(32 threads). E `--pinned` valida a afinidade de core com 16 processos — um por core, 16/16 distintos.
---
## 3. Como tudo se integra — o fluxo completo
```text
                     ┌─────────────────────── GitHub: mujoco_menagerie ───────────────────────┐
                     │  clone SPARSE só da pasta do robô → $TMPDIR                            │
                     └───────────────────────────────┬────────────────────────────────────────┘
                                                     │ vendorizar INTACTO
                                                     ▼
  ╔══════════════════════════════════════════════════════════════════════════════════════════╗
  ║  models/bitcraze_crazyflie_2/     cf2.xml (RK4, density 1.225, 4 canais wrench)          ║
  ║                                   NUNCA EDITADO (a checagem 7 do run.py prova-o)         ║
  ╚═════════════════════════════════╤════════════════════════════════════════════════════════╝
                                    │ compilado por MjSpec
                                    ▼
  ╔══════════════════════════════════════════════════════════════════════════════════════════╗
  ║  lab/crazyflie.py     + sensores (cm/posicao/vel)  + definir_*() em N e N·m              ║
  ║                       + MODOS (roteiros abertos)   + ler_*()                             ║
  ║                       ⚠ toda a adaptação é RUNTIME — nada em disco                       ║
  ╚═══════════════════════════════╤══════════════════════════════════════════════════════════╝
                                  │ importado por
                                  ▼
  ╔══════════════════════════════════════════════════════════════════════════════════════════╗
  ║  experiments/09_drone_hover_rl/                                                          ║
  ║                                                                                          ║
  ║   env.py ── HoverEnv (Gymnasium)   obs(16) normalizada · ação(4) centrada no hover       ║
  ║            ├─ recompensa v2b       ├─ vento FÍSICO via opt.wind                          ║
  ║            ├─ reset POUSADO        └─ guardas NaN → RuntimeError                         ║
  ║            │                                                                             ║
  ║            ├──▶ run.py       121 checagens por fórmulas fechadas ......... exit 0/1      ║
  ║            │                                                                             ║
  ║            ├──▶ train.py     PPO + currículo + DR ──▶ best_model.zip / final.zip         ║
  ║            │                        │                                                    ║
  ║            │                        ▼                                                    ║
  ║            ├──▶ sim_view.py  janela CLEAN + telemetria JSONL ◀── controle_vento.json     ║
  ║            │        ▲               │                             ▲                      ║
  ║            │        │ subprocesso   │ sim_telemetria.jsonl        │ POST /api/…          ║
  ║            ├──▶ sim_site.py ────────┴─────────────────────────────┴── site/ (React)      ║
  ║            │     UM comando: janela + servidor stdlib + API 5+1 rotas + browser          ║
  ║            │                                                                             ║
  ║            ├──▶ view.py       bancada com HUD (alternativa, para depurar)                ║
  ║            ├──▶ dashboard.py  UI de TREINO (outra peça, não é o padrão)                  ║
  ║            ├──▶ net_probe.py  sonda da rede em JSONL (h1/h2)                             ║
  ║            └──▶ deploy.py     ONNX → validação → benchmark → multi-IA ──▶ Raspberry Pi 5 ║
  ╚══════════════════════════════════════════════════════════════════════════════════════════╝
                                  │
                                  ▼  no fim: README do experimento (medido × teoria) +
                                     coala.py add (episódico/semântico/procedural) +
                                     catálogo de robôs no AGENTS.md
```
**O ponto de integração mais importante é o `env.py`.** Todas as peças importam o ambiente e mais nada:
o `run.py` valida-o, o `train.py` treina-o, o `sim_view.py`/`net_probe.py` correm-no com uma política, o
`deploy.py` usa-o para gerar observações **reais** para validar o ONNX. É por isso que o contrato da
observação (16) e da ação (4) é estável e está escrito em tabela: mudá-lo obriga a mexer no site, no
`net_probe`, no `deploy` e na telemetria ao mesmo tempo.
**A integração site ↔ simulação é deliberadamente "burra" e robusta.** Não há websockets, não há RPC, não
há estado partilhado em memória: há **dois ficheiros** e **uma API HTTP de stdlib**. O ganho é que cada
peça pode ser testada, reiniciada ou substituída sozinha — e a validação de tudo isto foi feita **sem
janelas**, com `--sem-janela`, mocks e Chrome headless.
**Uma peça que NÃO faz parte do padrão:** o `dashboard.py` (gestão de *treino*, com gráficos multi-run e
painel de vento; auditoria UX 41 → 88/100). Está no experimento, mas é uma ferramenta de bancada; o padrão
de operação é `sim_site.py`.
---
## 4. A regra transversal: simulador **sempre físico**
Esta regra do dono (2026-10-08) atravessa todas as sete camadas e é o que impede o experimento de se
tornar uma demo de animação:
> Tudo passa por `mj_step` — gravidade, arrasto, contactos, atuadores e sensores a cada passo. **Nada** de
> cinemática, teleporte (só `reset` explícito do simulador), corpos congelados ou "apoios mágicos": os
> robôs só se mexem por **comandos de atuador** e a física decide o resto.
Como isto aparece no código do drone:
| manifestação | onde |
|---|---|
| o programa **arranca com os motores desligados** e o drone **assenta no chão pela física** | `env.reset()` → `_assentar()` |
| o **vento** é `opt.wind` (mecanismo oficial do MuJoCo), não uma força somada à mão | `env.py`, `definir_vento` |
| o **único** reinício é um `reset()` explícito, pedido pelo contador `reiniciar` do site | `sim_view.py` ← `controle_vento.json` |
| a **rede não desenha arestas** porque a telemetria não traz pesos | `site/src/components/sim/rede.tsx` |
| quando a física diverge, o programa **para com `RuntimeError`** em vez de devolver NaN | `HoverEnv.step` |
O corolário cultural, que também está escrito no `README.md`: **o que a simulação faz de facto — inclusive
quando diverge da teoria de corpo rígido — é medido, registado no README e guardado na memória CoALA.**
Nada fica "na cabeça".
---
## 5. Para que serve: o que este padrão já produziu (e o que ensinou)
### Resultado final do drone
**Política campeã: `out/vento_r10_ft_dryden_600k/best_model.zip`** (verificado em disco), obtida por
**3 fine-tunes encadeados** a partir da v2b — rajadas → frente → turbulência Dryden — sempre com vento
ativo no treino.
| prova | resultado |
|---|---|
| **critério do dono** — 19 condições (16 constantes {0,1,2,3} m/s × {0,90,180,270}° + 3 dinâmicas) × 3 seeds | **57/57 PASS**, **0 terminações** |
| **stress denso** — 4 velocidades × 8 azimutes × 3 seeds + 24 dinâmicas duras + 24 sequências | **144/144** (o único dos 4 candidatos **sem nenhuma falha**) |
| pior caso a 3 m/s | `‖xy‖ = 0,084–0,096 m` — **abaixo do limite estrito de 0,10** |
| subida | atinge a faixa [0,95, 1,05] m em **59–66 passos** (≈1,2 s) e fica lá |
| `z` mínimo de todo o episódio | **0,015 m** — é o repouso no chão do 1.º passo, com motores desligados (o `reset` não teleporta) |
| ambiente | `run.py` **121/121** · suíte do laboratório **29 passed** |
### O que o padrão ensinou (e que está registado para não se repetir)
A primeira campanha de re-treino (**7 rondas, 20 treinos, ~25 M passos, 22 modelos avaliados**) deu
**0/16** em todas as políticas. O bloqueio **não era o vento**. Três achados, todos contra-intuitivos:
1. **Um atrator de *chatter* pode vir da recompensa.** As políticas v2 saturavam os canais de momento
   (|a| médio 0,74–0,90, ~70 trocas de sinal em 70 passos) e **capotavam aos ~1,3 s**, enquanto a política
   v1 — que paira 500/500 — usava **1 %** dessa autoridade. A réplica exata da receita v1 sob a recompensa
   v2 caía no mesmo platô: o atrator vinha da **recompensa**, não dos hiperparâmetros. Remédio:
   `PESO_DELTA_A` 0,01 → **0,05**.
2. **Um currículo com critério inatingível nunca liga.** O avanço pedia `frac_no_alvo ≥ 0,8` com o yaw
   **incluído**, mas a política v1 — que paira bem — mede **0,10**. Resultado: o DR de vento nunca ligava
   (`u_vento = 0` até ao fim). Remédio: medir `frac_xy_z` (**sem** yaw) com `--avanco-frac 0,5`.
3. **O bloqueio real era o yaw.** A base v1 já rejeitava o vento de posição, mas tinha o yaw livre
   (0,18 rad de *offset*). Um fine-tune de **160 k passos** baixou-o para 0,02 rad → **14/16**.
Achados operacionais que valem como regras: **`lr 3e-4` oscila** (16/16 ↔ 12/16 entre checkpoints)
enquanto `lr 1e-4`/`2e-4` é estável; **polir SEM vento degrada** (16/16 → 13/16 em 200 k passos — a
política "esquece" a rejeição de vento), logo **o vento tem de ficar no treino**; e o `--retomar` do SB3
precisa de `reset_num_timesteps=False`.
### Os limites, declarados sem maquilhagem
O padrão inclui a obrigação de **declarar os limites**. No drone: o envelope fiável é **≤3 m/s**
sustentado (a 4 m/s dá 0,189 m e a 5 m/s 0,285 m de deriva — degradação **suave**, com **zero quedas** até
5 m/s); o `best_model.zip` é escolhido pelo retorno medido **sem vento**, logo a certificação de robustez
vem de um **avaliador independente**, não do `train_log.jsonl`; e a política **não é um controlador de voo
certificado** — não foi treinada com atraso de atuador, ruído de IMU nem variação de massa/ganhos.
---
## 6. O padrão é reutilizável — a prova
O mesmo desenho serve máquinas completamente diferentes. Isto não é teoria: já está aplicado a dois robôs
do menagerie.
| aspeto | **Crazyflie 2** (drone) | **Spot** (quadrúpede) |
|---|---|---|
| camada lab | `lab/crazyflie.py` (252 l.) | `lab/spot.py` |
| modelo vendorizado | `models/bitcraze_crazyflie_2/` | `models/boston_dynamics_spot/` |
| atuadores | 4 canais *wrench* (empuxo + 3 momentos) | 12 servos `position` |
| sensores pedidos pelo padrão | IMU + posição/velocidade | IMU + encoders + forças dos pés (`touch`) |
| experimento de motores | `08_crazyflie_motores` · **8/8 [OK]** | `07_spot_motores` · **9/9 [OK]** |
| arranque físico (regra do dono) | motores desligados, **assenta no chão** | servos na postura `home`, **de pé pelos próprios motores** |
| RL + interface + deploy | `09_drone_hover_rl` (o padrão completo) | — (o padrão está pronto a aplicar) |
**O que é partilhado:** as sete camadas, os contratos de ficheiro/API, a janela limpa, a regra do
simulador físico, a validação por fórmulas fechadas, o ciclo de registo na memória.
**O que muda por robô:** o `model.xml`/`models/<robo>/`, a camada `lab/<robo>.py` (sensores e atuadores
certos para a máquina) e — no `env.py` — a observação, a ação e a recompensa. O `lab-padrao` formaliza
isto numa tabela "o que adaptar primeiro" com 9 pontos, e "o que NUNCA mudar".
**A versão empacotada do padrão** vive em `.agents/mujoco-lab-agent-skill/assets/templates/lab-padrao/`
(56 ficheiros): `model.xml`, `env.py`, `run.py`, `train.py`, `view.py`, `sim_view.py`, `sim_site.py`,
`site/`, `dashboard.py`, `net_probe.py`, `deploy.py`, `LEIAME.md`, `INTERFACE.md` — um exemplo que arranca
de raiz (uma haste com junta hinge) e que o `new_experiment.py --template lab-padrao` gera já montado.
---
## 7. A skill e a memória: o que torna o padrão transmissível
O padrão não vive só no código — vive na **`mujoco-lab-agent-skill`**, que é a *única* skill do
laboratório e junta duas coisas:
1. **A memória CoALA local** (`memory/coala.sqlite`, motor `scripts/coala.py`) — o que já se decidiu,
   testou e verificou. É o **primeiro passo de qualquer tarefa**:
   `coala.py recall "<tarefa>" --budget 1500` e `recall "<tarefa>" --type episodic --budget 600`.
   A memória tem proveniência (`owner` > `agent` > `untrusted`), **supersessão em vez de reescrita**
   (nada se apaga: o antigo fica com `superseded_by` + `valid_until`) e working memory **orçamentada**
   (nunca um *dump*).
2. **O conhecimento verificado do MuJoCo 3.15** — 16 referências, 10 scripts, 5 templates testados, a
   documentação oficial offline e uma suíte de 29 testes. Existe porque **a API muda a cada 2–5 semanas** e
   cada `3.N.0` pode quebrar código: `mjData.qM` foi removido, atuadores multi-entrada quebram o acesso
   por nome, o integrador recomendado não é o padrão.
**O ciclo que o padrão impõe a quem trabalha aqui:** orientar (`recall`) → recuperar (`search`/`graph`) →
agir (código, com a doc verificada antes de afirmar) → **aprender** (`add` do que for durável; `ingest` do
material novo). É isto que faz o padrão **transmissível**: um agente novo que siga o ciclo herda não só o
código mas as **razões** — incluindo as 20 tentativas falhadas que produziram os três achados da §5.
E há um detalhe que fecha o círculo: **o próprio drone está na memória**. O registo episódico da sessão de
2026-10-08 (noite) descreve o padrão `padrao-simulacao-clean-site` instituído, a arquitetura escolhida
(*"Plan B, após pesquisa"*), o comando único, o bug real corrigido pelo caminho (o travão `--fator-tempo`
ficava desligado após uma espera e o episódio reiniciado corria ~9× e morria em 0,1 s — corrigido
re-baseando o ritmo em cada `env.reset`) e até o facto de a janela nunca ter sido aberta por ordem do dono.
Quem pegar neste projeto a seguir começa exatamente onde esta sessão parou.
---
## 8. Como usar o padrão num robô novo (receita)
```bash
# 0) a memória primeiro — o que já se sabe
python3 .agents/mujoco-lab-agent-skill/scripts/coala.py recall "<o que quero fazer>" --budget 1500
python3 .agents/mujoco-lab-agent-skill/scripts/coala.py recall "<o que quero fazer>" --type episodic --budget 600
# 1) o modelo: clone SPARSE só da pasta do robô → vendorizar em models/<robo>/ INTACTO
#    (cruzar com o datasheet real do fabricante e citar a fonte no README)
# 2) inspecionar antes de acreditar
.venv/bin/python .agents/mujoco-lab-agent-skill/scripts/inspect_model.py models/<robo>/<x>.xml --tree
# 3) a camada lab/<robo>.py: carregar() · definir_*() · MODOS · ler_*()   (sem algoritmos!)
# 4) criar o experimento já no padrão
python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py <nome> --template lab-padrao
# 5) adaptar, pela ordem do LEIAME: model.xml → obs → acao_para_ctrl → recompensa →
#    perturbação → run.py → sim_view.amostra → site/src/lib/sim.ts → train.FASES
# 6) validar SEM JANELAS (regra do dono: agentes nunca abrem viewer)
uv run --group hover-rl python experiments/NN_<nome>/run.py          # exit 0/1
# 7) treinar, operar e fazer deploy
uv run --group hover-rl python experiments/NN_<nome>/train.py --timesteps 1000000 --seed 0
uv run --group hover-rl python experiments/NN_<nome>/sim_site.py     # UM comando: janela + site
uv run --group hover-rl python experiments/NN_<nome>/deploy.py --skip-multi
# 8) registar: README com medido × teoria + fontes · coala.py add · catálogo no AGENTS.md
```
---
## 9. Divergências encontradas entre a documentação e o código
Escrevo-as porque o ponto deste laboratório é exatamente **não** deixar afirmações por verificar. Todas
foram confirmadas a 2026-10-08.
1. **A API tem 6 rotas, não 5.** `README.md:100`, `INTERFACE.md` §4.3 e o `LEIAME.md` do `lab-padrao`
   falam de "API de 5 rotas" e listam `GET /api/sim`, `GET /api/state`, `POST /api/vento`,
   `POST /api/reiniciar`, `POST /api/loop`. O código tem **mais uma**:
   **`POST /api/vento-dinamico`** (`sim_site.py:494`, handler em `_post_vento_dinamico`), que liga a
   dinâmica de vento ao vivo (rajadas/frente/dryden) **sem** reiniciar o episódio — e que **o site usa**
   (`site/src/lib/api.ts:116`, `App.tsx:111`). Não é código morto: é uma rota integrada que ficou fora da
   documentação. É a única divergência **material** que encontrei.
2. **`INTERFACE.md` §3.5 diz que as dinâmicas de treino "existem no ambiente e no treino, não neste
   painel".** Isso já não é verdade para o site: existe um controlo de vento dinâmico ao vivo
   (`POST /api/vento-dinamico`, com `modo`/`params`/`ativo` e um `seq` para re-disparos), e o ficheiro de
   controlo ganhou o bloco `dinamico`. O `INTERFACE.md` descreve o painel da ronda 9; a ronda 10
   acrescentou-lhe a dinâmica.
3. **Os "7 campos" do `controle_vento.json` são o caso base.** O exemplo real em disco tem exatamente
   `vel, azimute, elevacao, ativo, reiniciar, loop, t` — a contagem está certa. Mas a rota dinâmica
   acrescenta um **bloco `dinamico`** (`{modo, params, ativo, seq}`, validado pelo **próprio**
   `env.valida_vento_dinamico` — as regras não são duplicadas), que o runner lê a cada passo de decisão.
   Logo o ficheiro tem **8 chaves** quando a dinâmica está a ser usada. A documentação descreve o estado
   anterior à ronda 10.
4. **`INTERFACE.md` §3.4/§3.6 vs. o site**: a documentação diz que o site usa os valores de recurso
   `FISICA_PADRAO` porque o `/api/state` **não** anuncia as constantes físicas. O `README.md` e o
   `INTERFACE.md` concordam entre si — não encontrei contradição, mas fica registado que
   `/api/state` **não** publica `mg`/`thrust_max`/`momento_max`/`tau_escala`: quem mexer no site tem de
   saber que esses números estão duplicados no TypeScript.
Nada disto afeta a física, o treino ou os resultados — as 121 checagens do `run.py`, os 57/57 e os 144/144
foram todos reproduzidos/confirmados contra os artefactos em disco. São divergências **de documentação**,
e a correção delas é trabalho de minutos.
---
## 10. Ficheiros de referência
| peça | caminho |
|---|---|
| o padrão completo (implementação de referência) | [`experiments/09_drone_hover_rl/`](experiments/09_drone_hover_rl/) |
| o que é o drone e os números medidos | [`README.md`](experiments/09_drone_hover_rl/README.md) |
| tudo o que é visível (janela, teclas, cada campo do site) | [`INTERFACE.md`](experiments/09_drone_hover_rl/INTERFACE.md) |
| camada de adaptação do drone | [`lab/crazyflie.py`](lab/crazyflie.py) |
| o ambiente Gymnasium | [`env.py`](experiments/09_drone_hover_rl/env.py) |
| validação por fórmulas fechadas | [`run.py`](experiments/09_drone_hover_rl/run.py) |
| treino PPO | [`train.py`](experiments/09_drone_hover_rl/train.py) |
| runner da janela limpa | [`sim_view.py`](experiments/09_drone_hover_rl/sim_view.py) |
| o comando único (janela + site + API) | [`sim_site.py`](experiments/09_drone_hover_rl/sim_site.py) |
| o site React | [`site/`](experiments/09_drone_hover_rl/site/) |
| deploy ONNX / benchmark / multi-IA | [`deploy.py`](experiments/09_drone_hover_rl/deploy.py) |
| o padrão empacotado (template base) | [`.agents/mujoco-lab-agent-skill/assets/templates/lab-padrao/`](.agents/mujoco-lab-agent-skill/assets/templates/lab-padrao/) |
| o padrão em 8 passos + experimentos | [`README.md`](README.md) |
| regras do projeto para agentes | [`AGENTS.md`](AGENTS.md) |
| a skill única (memória CoALA + MuJoCo 3.15) | [`.agents/mujoco-lab-agent-skill/SKILL.md`](.agents/mujoco-lab-agent-skill/SKILL.md) |
**Fontes externas citadas** (conteúdo web = `untrusted`, só se cita):
[mujoco_menagerie · bitcraze_crazyflie_2](https://github.com/google-deepmind/mujoco_menagerie/tree/main/bitcraze_crazyflie_2)
(modelo MIT e a nota de que os `ctrlrange` são *"arbitrary"*) ·
[MuJoCo-Drones-Gym, arXiv 2606.08039](https://arxiv.org/pdf/2606.08039) (origem da equação de recompensa) ·
[Datasheet Crazyflie 2.0, Bitcraze](https://www.bitcraze.io/documentation/hardware/crazyflie_2_0/crazyflie_2_0-datasheet.pdf)
(27 g; base do `thrust_max = 0,589 N`) ·
[INT8 on Raspberry Pi 5 / Cortex-A76, Zenodo](https://zenodo.org/records/22163336) (quantização estática vs dinâmica).
