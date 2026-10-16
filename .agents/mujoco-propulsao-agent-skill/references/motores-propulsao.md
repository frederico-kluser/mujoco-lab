# Motores e propulsão — padrões MJCF/Python verificados

Como acionar um objeto novo: motor elétrico, servo, hélice/ESC, jato/foguete ou propulsão multi-eixo,
no MuJoCo 3.15 deste laboratório. Verificado com `.venv/bin/python` em 2026-10-15 (template
`assets/templates/objeto-propulsado/`, cujo `run.py` prova cada fórmula). Fundo mais largo:
`mujoco-lab-coala-agent-skill/references/actuators-sensors.md` (atuadores) e `drones.md` (hélices).

## Quando ler este arquivo
- Escolher o tipo de atuador do teu objeto e escrever o `<actuator>` certo.
- Modelar hélice/ESC/motor DC com números de datasheet.
- Validar o empuxo/torque por fórmulas fechadas antes de avançar.

## 1. Qual mecanismo usar

| Necessidade | Mecanismo | ctrl (unidade) | Onde ver |
|---|---|---|---|
| Torque direto (volante, roda, rebatível) | `<motor joint gear>` | N·m | §2.1 |
| Servo PD (posição alvo) | `<position>` / `pid` (3.12) | rad (m) | actuators-sensors §2 |
| Motor DC de datasheet (V→τ, back-EMF, saturação) | `<dcmotor>` (3.7) | V | §2.2 |
| Hélice + ESC brushless (real: ω, corrente, bateria) | planta Python + wrench por site | 0–1 (acelerador) | §3 (`lab/drone_rpi/propulsao.py`) |
| Empuxo/jato/foguete (força em N) | `<general site gear="0 0 1">` | N | §2.3 |
| Empuxo multi-eixo ("todos os locais") | N sites orientados + N atuadores | N | §2.3 + template |
| Impulso curto/explosão | força externa por passos | N·s (ver `explosivos-impulsao.md`) | — |

## 2. Padrões XML

### 2.1 Motor em junta (torque direto)
```xml
<body name="volante"><joint name="volante_hinge" type="hinge" axis="0 0 1"/>
  <geom type="cylinder" size="0.05 0.01" mass="0.2"/></body>
<actuator><motor name="motor_volante" joint="volante_hinge" gear="1" ctrlrange="-0.5 0.5"/></actuator>
```
- `gear` escala `L`, `∇L`, `V` e `F` (o ganho só escala `F`); `damping`/`armature` do atuador refletem ×`gear²`.
- **Volante de reação** (torque INTERNO): o objeto contra-roda — ΣL_z ≈ 0; `q̇_hinge = τ/I_red` com
  `I_red = 1/(1/I_rotor + 1/I_base)` (base livre). Com a base apoiada no chão: `ω = τ·T/I_rotor`.
  Ambas as fórmulas provadas no `run.py` do template (secção «motor»).

### 2.2 Motor DC de datasheet (`dcmotor`, 3.7)
```xml
<dcmotor name="m" joint="j" gear="30" resistance="1.2" motorconst="0.05"
         nominal="12" ctrlrange="-12 12" saturation="2.0"/>
```
- ctrl em VOLTS; `resistance` Ω, `motorconst` N·m/A, `nominal` V; **sem `forcerange`** (a saturação é `saturation`).
- Sem parâmetros de datasheet, usa `motor` com `forcerange` e documenta a estimativa.

### 2.3 Empuxo/jato (wrench por SITE) — o padrão "para todos os locais"
```xml
<body name="objeto">…
  <site name="bocal_x" pos="0.15 0 0" euler="0 90 0"/>   <!-- eixo z do site = direção da força -->
  <site name="bocal_z" pos="0 0 0.05"/></body>
<actuator>
  <general name="empuxo_x" site="bocal_x" gear="0 0 1" ctrlrange="-50 50"/>   <!-- F (N) -->
  <general name="empuxo_z" site="bocal_z" gear="0 0 1" ctrlrange="0 50"/>
</actuator>
```
- `gear` de 3 = força `[fx fy fz]` no frame do site; de 6 = wrench `[fx fy fz tx ty tz]`.
- **Torque de reação de rotor** (par verificado em `models/drone_rpi/drone_rpi.xml:71-80`):
  `<general site="r1" gear="0 0 1"/>` (empuxo) + `<general site="r1" gear="0 0 0 0 0 1"/>` (τ de reação).
- Mais direções = mais `<site>` orientado (eixo z = direção) + mais atuador. O `euler` do compiler
  `angle="degree"`: `0 90 0` → z do site em +x; `-90 0 0` → z do site em +y (provado no `run.py`, secção «eixos»).
- **Bi-direcional vs bocal real**: `ctrlrange="-F F"` dá +/− (bom para teclado); um bocal físico só
  empurra (`ctrlrange="0 Fmax"`) — o sentido inverso pede um segundo bocal oposto.

## 3. Hélice + ESC brushless (modelo físico completo)
O modelo real do laboratório vive em `lab/drone_rpi/propulsao.py` (validado contra tabelas T-Motor):
```
V_m = d·V_bus            (ESC: ciclo útil d ∈ [0,1]; DShot quantiza a 2000 níveis com 11 bits)
I   = (V_m − K_e·ω)/R    (R = motor + ESC/cabos; I<0 = travagem "damped light")
J·ω̇ = K_t·I − Q₀(ω) − κ_Q·kq·ω²
T   = κ_T·kf·ω²          (empuxo; κ_T = solo/inflow/VRS — ver aero.py)
```
- **T = kf·ω²** e **Q = kq·ω²** são as fórmulas-chave; kf/kq vêm das tabelas do fabricante (pares
  empuxo/potência a vários RPM) — `models/drone_rpi/componentes.json` tem as tabelas com fontes.
- Integração Euler semi-implícita em ω (estável para qualquer dt de física).
- Atraso de subida/descida: `τ ≈ J/(K_t²/R + 2·kq·ω)`; `ω_max(V)` DECAI com a bateria.
- Em massa variável (foguete): `ṁ = F/(g₀·Isp)`; desconta a massa ao corpo por passo
  (`model.body_mass[b] -= ṁ·dt` + `mujoco.mj_setConst(m, d)`) e regista-o no README.

## 4. Unidades e limites (resumo; tabela completa em actuators-sensors §3)
- `ctrl`: `motor` N·m · `position` rad (m) · `velocity` rad/s · `dcmotor` V · `pid` pos/vel/ff · site wrench N (N·m).
- `ctrlrange`/`actrange`/`lengthrange` são NATIVOS (rad, m) — **não** convertidos de graus.
- `forcerange` limita F depois do ganho; `joint/actuatorfrcrange` limita a soma na junta.
- Atuadores multi-entrada (`pid`, `dcmotor`, `orientation`): `nu ≠ nactuator` — escreve por
  `model.actuator_ctrladr[i]`/`actuator_ctrlnum[i]` (helper `Ctrl` do template ou `lab.mjkit.Ctrl`).
  `data.actuator('x').ctrl` grava no slot ERRADO (armadilha registada em AGENTS.md).

## 5. Validação por fórmulas fechadas (fazer sempre, modelo fresco)
| Efeito | Fórmula | Condições |
|---|---|---|
| Pairagem | empuxo = m·g ⇒ qacc_z = 0 | sem contacto; `mj_forward` antes de ler |
| Empuxo | Δp = F·T (direção do site!) | plano sem gravidade no eixo medido, ou subtrai m·g·T |
| Motor (base fixa) | ω = τ·T/I | base apoiada/fricção |
| Motor (livre) | q̇ = τ·T/I_red · ΣL ≈ 0 | sem torque externo |
| Reação de rotor | ω̇_corpo = −τ/I_corpo | par empuxo+τ |
| Massa variável | Δv = −ve·ln(m₀/m_f) (Tsiolkovsky) | sem forças externas |

Medição de momentos: `mujoco.mj_subtreeVel(m, d)` preenche `subtree_linvel/subtree_angmom` (o
`flg_subtreevel` só regista a chamada); helper `momentos()` do `run.py` do template soma raízes +
termos orbitais. freejoint 3.15: `qvel[:3]` linear MUNDO · `qvel[3:]` angular CORPO. e índices de
junta por `model.jnt_dofadr`/`jnt_qposadr` (o acesso `model.joint('x').dofadr` devolve array).

## Armadilhas
1. `mj_applyFT`/`xpos`/`xipos` a zeros antes do 1.º forward → chama `mj_kinematics` + `mj_comPos`
   antes de aplicar forças (a `Carga` do template faz; medido: sem isto perde-se 1/10 do impulso).
2. Geoms visual+collision no mesmo corpo **dobram a massa** (`inertiagrouprange`): um geom só, ou
   `inertiagrouprange="3 3"`, ou `<inertial>` explícito.
3. `ctrlrange` com `autolimits="false"` sem `ctrllimited` = erro de compilação.
4. Após `mj_step` os campos derivados ficam um passo atrás: `mj_forward` antes de ler.
5. Sempre físico: o empuxo entra por atuador/força externa — nada de teleportar `qvel`/`qpos`.
