# 07 · Spot (Boston Dynamics) — motores e juntas, sem locomoção

Demo do quadrúpede **Spot** da Boston Dynamics usando o modelo **pronto** do
[mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/main/boston_dynamics_spot)
(`models/boston_dynamics_spot/`, BSD-3-Clause, derivado do URDF público do
[spot_ros2](https://github.com/bdaiinstitute/spot_ros2)). O objetivo é **mexer nas juntas e nos motores**
— não há marcha, equilíbrio, IK nem política de RL. Se empurrar o robô, ele cai.

- `lab/spot.py` — **MODOS, CONTROLES e LEITURAS como funções** (para criar algoritmos e experimentos).
- `run.py` — demo "motor show" headless: cada uma das 12 juntas faz uma senoide completa, uma de cada
  vez, com o robô de pé; grava vídeo/GIF/folha de quadros/gráficos e valida com exit code 0/1.
- `view.py` — janela interativa: teclado + REPL no terminal para mover juntas, mudar posturas e varrer motores.

```bash
uv run python experiments/07_spot_motores/run.py                 # demo + validação + out/spot_motores.mp4/gif
uv run python experiments/07_spot_motores/run.py --sem-video     # só números
uv run python experiments/07_spot_motores/view.py                # janela interativa (ver teclas abaixo)
uv run python experiments/07_spot_motores/view.py --alvo "fl_hy=1.2,fl_kn=-1.6"
```

## A API (`lab/spot.py`) — o que se chama

```python
from lab import spot
modelo, data = spot.carregar()                    # modelo do menagerie + sensores + keyframe home

# CONTROLES (alvos dos 12 servos PD, cortados para os limites das juntas)
spot.definir_alvo(modelo, data, "fl_hy", 1.2)
spot.definir_alvos(modelo, data, {"fl_kn": -1.6, "fr_kn": -1.6})
spot.postura(modelo, data, "agachar")             # home/zero/agachar/sentar/esticar

# MODOS (funções (model, data, tau) — posturas e varredura de motores, sem realimentação)
spot.MODOS["varrer"](modelo, data, tau)

# LEITURAS (sensores)
spot.ler_imu(modelo, data)      # {'giro', 'acc', 'quat', 'vel'} — acc = aceleração própria
spot.ler_juntas(modelo, data)   # {'pos': {...}, 'vel': {...}} — encoders das 12 juntas
spot.ler_pes(modelo, data)      # {'FL': .., 'FR': .., 'HL': .., 'HR': ..} N de contato
spot.ler_torques(modelo, data)  # torque de cada atuador (N·m)
spot.ler_tudo(modelo, data)
```

## Sensores (adicionados pela camada, sem editar o modelo upstream)

Revisados para um quadrúpede — os que importam para algoritmos e treino:

| sensor | o que mede | porquê |
|---|---|---|
| `imu_gyro` · `imu_acc` · `imu_quat` · `imu_vel` | taxa, aceleração própria, orientação, velocidade (site `imu` no tronco) | atitude/odometria — sem IMU não há estabilização |
| `junta_pos_*` · `junta_vel_*` (×12) | encoder de cada junta | retroação dos 12 servos |
| `pe_FL/FR/HL/HR` (touch ×4) | força de contacto de cada pé | fase de apoio, impacto e carga — o que distingue um quadrúpede de um braço |

Os torques dos atuadores lêem-se por `ler_torques` (`qfrc_actuator`) — não precisa de sensor dedicado.
Adicionados via **MjSpec em runtime** (`models/boston_dynamics_spot/` fica intocado); lembrete verificado:
o sensor `touch` só conta contactos cujo ponto cai no **volume do site** — os sites dos pés são a esfera
exata do geom do pé (r = 0,036 m).

## O modelo (o que vem do menagerie, sem alterações)

`models/boston_dynamics_spot/` contém `spot.xml` (robô), `scene.xml` (robô + chão + céu),
`spot_arm.xml`/`scene_arm.xml` (variante com braço/garra — não usada aqui), `assets/` (23 malhas `.obj`)
e `LICENSE`. Requisito: MuJoCo ≥ 3.1.3 (aqui: 3.15.0).

- **12 juntas** `hinge`, 3 por perna: `hx` (rotação do quadril, eixo X), `hy` (flexão do quadril, eixo Y),
  `kn` (joelho, eixo Y). Base flutuante (`freejoint`), 50,3 kg no total.
- **12 servos `<position>`** (PD) com o mesmo nome das juntas: `kp=500`, `kv=40`, `inheritrange="1"`
  (portanto `ctrlrange` = limites da junta) e `joint actuatorfrcrange="-1000 1000"`.
  O README do menagerie diz *"Added position actuators (not tuned)"*.
- **Keyframe `home`**: `qpos`/`ctrl` iguais (equilíbrio nominal: servo sem erro em repouso).
- `option integrator="implicitfast" cone="elliptic" impratio="100"` · `dt=0.002 s`.
- O `meshdir="assets"` resolve em relação ao ficheiro MJCF **principal**: carregue sempre `scene.xml`
  ou `spot.xml` diretamente da pasta do modelo (um `<include>` a partir de outra pasta quebra as malhas).

### Limites das juntas (o modelo bate com o Spot real)

| junta | faixa no modelo (rad) | faixa real (docs Boston Dynamics) |
|---|---|---|
| hx | ±0,785 (±45°) | ±45° da vertical |
| hy | −0,899 … 2,295 (≈ −51,5° … 131,5°) | ±91° com viés de 50° da vertical |
| kn | −2,793 … −0,254 (≈ −160° … −14,6°) | 14°–160° da reta |

Torques reais dos motores (BD, *Supplemental Data*): HX/HY = 51:1 × 0,88 N·m ≈ **45 N·m**;
KN = ratio variável, **37–97 N·m** conforme o ângulo. No modelo o limite é `actuatorfrcrange ±1000 N·m`
(não afinado) — os torques medidos na demo ficam nos **46–72 N·m**, a mesma ordem de grandeza do robô real.

## Validação (run.py, exit 0/1)

1. **Estrutura** — 12 servos `position` 1:1 com as 12 juntas (transmissão `joint`, sem dinâmica interna).
2. **Keyframe home** — `ctrl == qpos` (desvio 0,00e+00) e dentro de `ctrlrange`: o servo não esforça em repouso.
3. **Servo puro = teoria PD** ✔ físico — em **queda livre** (carregando `spot.xml`, sem chão), cada junta `hx`
   recebe uma senoide de 0,2 rad a 0,5 Hz e a resposta ajustada por mínimos quadrados é comparada com
   `H(ω) = kp / (I(jω)² + kv·jω + kp)`, com `I = M[dof,dof]` via `mj_fullM`:
   **ganho medido 0,972 vs teoria 0,971 · atraso 13,8° vs 14,1°** (Δ ≤ 0,001 / 0,4° — tolerância 5%/5°).
4. **Rastreio em pé** — ganho de amplitude ≥ 0,5 em todas as juntas (medido 0,55–0,79).
5. **Limites de junta** respeitados em toda a trajetória (folga de 2 mm).
6. **Base de pé no fim** (z > 0,35 m, inclinação < 0,3 rad).
7. **Sensor IMU** — em repouso, `acc ≈ +g` (aceleração própria, verificada: [0.11 0.03 9.81] m/s²).
8. **Sensores dos pés** — Σ forças de contacto ≈ peso (verificado: 493,8 N vs 493,8 N).
9. **Sem NaN**.

### Achado verificado: o chão degrada o servo

Com os pés apoiados, mover UMA junta arrasta toda a estrutura pelos contactos (pés esféricos
`condim=6`, atrito 0,8, `solref 0.004 1`): a resposta passa de **ganho 0,97 / atraso 14°** (servo puro)
para **ganho 0,55–0,79 / atraso 17–32°** a 0,5 Hz (±0,2 rad). Não é bug nem erro de modelação dos
atuadores — é o acoplamento multibody + contato, e por isso o `--tol-ganho` do rastreio em pé (0,5)
é mais folgado do que a checagem analítica do servo puro. Comandos mais lentos acompanham melhor.

## view.py — mexer nas juntas e motores

Teclado (foco na janela): `TAB`/`N` próxima junta · `B` anterior · `↑`/`↓` alvo ±0,05 rad ·
`PGUP`/`PGDN` ±0,2 rad · `H` postura home · `Z` zeros (dentro dos limites) · `1..4` posturas
(home/agachar/sentar/esticar) · `S` varrer a junta selecionada (senoide ±0,25 rad a 0,25 Hz) ·
`L` listar · `P` pausa · `R` reiniciar.

REPL no terminal: `set fl_hy 1.2` · `pose agachar` · `sweep fl_kn 0.3` · `sweep off` · `list` · `home` · `quit`.
Todos os alvos são cortados para `ctrlrange` (limites reais das juntas).

## Saídas de `run.py` (`out/`, ignorado pelo git)

`spot_motores.mp4` (720p, 28 s) · `spot_motores.gif` · `folha.png` (8 quadros com o motor ativo no HUD) ·
`rastreio.png` (alvo × posição das 12 juntas) · `motores.png` (torque dos motores e altura da base).

## Fontes pesquisadas (web, conteúdo não confiável — só citado)

- [mujoco_menagerie · boston_dynamics_spot](https://github.com/google-deepmind/mujoco_menagerie/tree/main/boston_dynamics_spot) — modelo MJCF usado (cópia local espelhada + clone sparse para as malhas).
- [Boston Dynamics · About Spot](https://dev.bostondynamics.com/docs/concepts/about_spot.html) — 12 GDL, faixas das juntas (HX ±45°, HY ±91° com viés 50°, KN 14°–160°).
- [Boston Dynamics · Supplemental Data](https://dev.bostondynamics.com/docs/concepts/joint_control/supplemental_data.html) — ratios e torques máximos dos motores.
- [Boston Dynamics · Knee Torque Limits](https://dev.bostondynamics.com/docs/concepts/joint_control/knee_torque_limits.html) — torque do joelho variando com o ângulo (37–97 N·m).
- [spot_ros2 (bdaiinstitute)](https://github.com/bdaiinstitute/spot_ros2) — URDF de origem do modelo.
- [MuJoCo Playground (arXiv 2502.08844)](https://arxiv.org/html/2502.08844v1) — contexto: locomoção com RL (fora do âmbito desta demo).
- [High-Performance RL on Spot (arXiv 2504.17857)](https://arxiv.org/html/2504.17857v1) — kp=60/kd=1,5 no controlo de baixo nível do robô real (vs 500/40 do modelo).
