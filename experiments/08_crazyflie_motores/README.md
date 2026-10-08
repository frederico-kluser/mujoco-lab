# 08 · Crazyflie 2 (Bitcraze) — motores e controles, sem estabilização

Demo do quadricóptero **Crazyflie 2** da Bitcraze usando o modelo **pronto** do
[mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/main/bitcraze_crazyflie_2)
(`models/bitcraze_crazyflie_2/`, MIT, derivado do [crazyflie_ros](https://github.com/whoenig/crazyflie_ros))
+ a camada de funções **`lab/crazyflie.py`**. O objetivo é **criar os seus algoritmos sobre os motores**:
não há PID, atitude-lock, IK nem código do firmware/ROS da Bitcraze — só comandos abertos (e o drone
deriva, como manda a física).

- `lab/crazyflie.py` — **MODOS, CONTROLES e LEITURAS como funções** (é esta a entrega principal).
- `run.py` — demo dos modos + validação física com exit code + vídeo/GIF/gráficos.
- `view.py` — janela interativa: teclado + REPL no terminal.

```bash
uv run python experiments/08_crazyflie_motores/run.py                 # demo + validação + out/crazyflie_motores.mp4
uv run python experiments/08_crazyflie_motores/run.py --sem-video     # só números
uv run python experiments/08_crazyflie_motores/view.py                # janela interativa
```

## A API (`lab/crazyflie.py`) — o que se chama

```python
from lab import crazyflie as cf
modelo, data = cf.carregar()                      # modelo + sensores + keyframe hover

# CONTROLES (unidades físicas; tudo cortado para a faixa do canal)
cf.definir_empuxo(modelo, data, 0.30)             # N, eixo +z do corpo
cf.definir_momentos(modelo, data, 1e-6, 0, -1e-6) # N·m (roll, pitch, yaw)
cf.definir_wrench(modelo, data, 0.28, (0, 0, 0))  # os dois de uma vez
cf.comandar_rotores(modelo, data, [0.07, 0.07, 0.07, 0.07])  # mixer X: 4 empuxos → wrench
cf.hover(modelo, data)                            # empuxo = peso (equilíbrio ABERTO)
cf.desligar(modelo, data)

# MODOS (roteiros abertos, função (model, data, tau) — sem realimentação)
cf.MODOS["empuxo"](modelo, data, tau)             # desligado/hover/empuxo/momento_x/y/z/rotores
cf.modo_momento(modelo, data, tau, eixo=2, amp=1e-6, freq=0.25)

# LEITURAS (sensores)
cf.ler_imu(modelo, data)     # {'giro', 'acc', 'quat'} — acc = aceleração própria (em repouso: +g)
cf.ler_estado(modelo, data)  # {'pos', 'vel', 'vel_ang'} — ground truth p/ algoritmos e treino
cf.ler_motores(modelo, data) # {'empuxo', 'momentos', 'ctrl'}
cf.ler_tudo(modelo, data)
```

Constantes importantes: `MASSA=0.027` kg · `PESO=0.26487` N · `EMPUXO_MAX=0.35` N ·
`POS_ROTORES` (±0,0325 m) · `GIRO` (pares CW/CCW) · `KM=0.016` m (razão momento/empuxo — **parâmetro
livre**, ajuste ao seu hardware) · `MOMENTOS_MAX` (faixa física dos 3 momentos).

## O modelo e a camada de adaptação

`models/bitcraze_crazyflie_2/` fica **intocado** (cf2.xml, scene.xml, assets, LICENSE/README). O
`cf2.xml` nativo atua por um wrench num site no centro de massa: **4 canais** — `body_thrust`
(0–0,35 N) + `x/y/z_moment` (ctrl ±1 × gear 1e-5). Massa 0,027 kg, inércias do datasheet/identificação
do MIT, integrador RK4, densidade do ar 1,225 (arrasto ligado). Sensores nativos: `body_gyro`,
`body_linacc`, `body_quat` (site `imu`) — mantidos.

A camada `lab/crazyflie.py` faz, **em runtime** (sem editar ficheiros upstream):

1. **Sensores novos** via MjSpec: `posicao` (framepos) e `vel` (velocímetro) no centro de massa.
2. **Escala física dos momentos**: o gear upstream (±1e-5 N·m) é admitido *"arbitrary"* no README do
   menagerie e satura qualquer mixer real. `carregar(momentos="fisico")` (predefinição) ajusta o gear
   para a faixa derivada da geometria dos rotores (`MOMENTOS_MAX` = 5,7 mN·m roll/pitch, 2,8 mN·m yaw);
   `momentos="nativo"` preserva o upstream.
3. Funções de controlo/modos/leituras (acima).

### Mixer de rotores (geometria medida no próprio modelo)

As posições dos 4 rotores (`POS_ROTORES` = ±0,0325 m) foram medidas nos centróides da malha das
hélices (`assets/cf2_0.obj`): raio ≈ 0,0457 m → **diagonal motor-a-motor ≈ 92 mm**, igual aos 92×92 mm
do datasheet CF2.0. O mixer: `F_z = Σt_i`, `τ_x = Σr_y·t_i`, `τ_y = −Σr_x·t_i`, `τ_z = Σ giro_i·KM·t_i`.

## Validação (run.py, exit 0/1) — fórmulas fechadas em condições ISOLADAS

1. **Canais** — 4 atuadores com gear físico esperado; **sensores** prontos (3 nativos + 2).
2. **Keyframe hover** — `ctrl[0] == m·g` (0,26487 N, desvio < 1e-9).
3. **Mixer** — wrench aplicado == analítico (identidade algébrica, erro 0,00e+00).
4. **Empuxo→altitude** — modelo fresco e parado, ΔF em cosseno (0,01 N @ 0,25 Hz):
   amplitude de `z` medida **0,1501 m vs teoria ΔF/(m·ω²) = 0,1501 m**.
5. **Momentos→rotação** — modelo fresco por eixo, M em cosseno (0,5 µN·m @ 0,25 Hz):
   amplitude de `ω` medida **0,0133/0,0133/0,0098 vs teoria M/(I·ω)** (x/y/z) — erro < 1%.
6. **Demo** — comandos sempre dentro de `ctrlrange`; sem NaN.

### Achado verificado: o arrasto do ar acopla os eixos acima de ~1 m/s

O `cf2.xml` liga o modelo de fluido do MuJoCo (`density=1.225`, `viscosity=1.8e-5`) — realista para um
robô de 27 g. Numa sequência de modos, a inclinação de atitude deixa velocidade horizontal residual
(ex.: a fase de momento em x termina com ≈ 1,1 m/s) e, acima de ~1 m/s, os torques aerodinâmicos
acoplam os eixos: as amplitudes de `ω` deixam de bater com a teoria de corpo rígido (medido até 27× a
teoria na fase de guinada). Verificado por ablação: com `density=0` cada fase devolve `ω → 0`. Por isso
as checagens analíticas são feitas em condições isoladas (velocidades ≈ 0) e a demo usa amplitudes
modestas (`AMP_MOMENTO = 0,5 µN·m`).

## view.py — mexer nos motores e controles

**Arranque físico**: motores desligados — o drone assenta no chão pela física (z de repouso ≈ 0,013 m),
nada paira por magia. Para voar: `T` descolar (1,2× peso) → à altura desejada, `H` pairar (= peso) →
`D` desligar (cai). Tudo passa por `mj_step` (gravidade, arrasto, contactos) — só comandos de atuador.

Teclado: `1..7` modos · `↑/↓` empuxo ±0,01 N · `←/→` momento_x · `PGUP/PGDN` momento_y · `,/.` momento_z
(±0,5 µN·m) · `T` descolar · `H` hover · `D` desligar · `S` sensores · `L` listar · `P` pausa · `R` reiniciar.
REPL: `modo empuxo` · `empuxo 0.30` · `momento x 1e-6` · `rotores 0.07 0.07 0.07 0.07` · `descolar` ·
`sensores` · `list` · `hover` · `desligar` · `quit`.

## Saídas de `run.py` (`out/`, ignorado pelo git)

`crazyflie_motores.mp4` (720p, 30 s) · `crazyflie_motores.gif` · `folha.png` · `altitude.png` ·
`rotacao.png`.

## Fontes pesquisadas (web, conteúdo não confiável — só citado)

- [mujoco_menagerie · bitcraze_crazyflie_2](https://github.com/google-deepmind/mujoco_menagerie/tree/main/bitcraze_crazyflie_2) — modelo MJCF usado (cópia local + clone sparse para as malhas).
- [Datasheet Crazyflie 2.0 (Bitcraze)](https://www.bitcraze.io/documentation/hardware/crazyflie_2_0/crazyflie_2_0-datasheet.pdf) — 27 g, 92×92×29 mm motor-a-motor.
- [Thrust upgrade kit (Bitcraze)](https://www.bitcraze.io/2022/10/thrust-upgrade-kit-for-the-crazyflie-2-1) — ≈ 60 g de empuxo máximo total no setup stock (o modelo usa 35,7 g — `ctrlrange` "arbitrário").
- [crazyflie_ros (whoenig)](https://github.com/whoenig/crazyflie_ros) — URDF de origem do modelo.
