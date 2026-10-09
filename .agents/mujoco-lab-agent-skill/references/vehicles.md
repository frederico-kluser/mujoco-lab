# Veículos de rodas no MuJoCo (carros, rovers e bases de robôs)

Modelar, controlar e validar veículos de rodas: o carro oficial, um carro Ackermann de 4 rodas do zero, contato pneu-solo, suspensão, limites do contato e escala em GPU.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: ficha `pesquisas/conhecimento/Q9.md` (+ Q4 contato, Q7 atuadores), `docs/upstream/mujoco/model/car/car.xml`, `docs/upstream/mujoco/doc/{modeling,XMLreference,mjx}.rst` e `computation/index.rst`, Menagerie, template `assets/templates/car/`. Números reexecutados com `.venv/bin/python`; todos os blocos de código foram rodados. Marcadores: ✔ = testado nesta sessão · ⚠ = armadilha · Δ doc = a doc diverge do medido.

## Quando ler este arquivo
- Criar carro, rover ou base diferencial (rodas, direção, tração, suspensão) ou estender o template `car`.
- Regular atrito, `condim`, cone, `impratio`/`noslip` de pneus; diagnosticar patinação, creep em rampa, subesterço.
- Decidir se o MuJoCo basta (não há modelo de pneu), validar contra a cinemática ou escalar em GPU.

## 1. Exemplo oficial `model/car/car.xml` (tração diferencial)
Carro de 0,543 kg (chassi 0,430 + 2 rodas × 0,0566; adicionado na 2.3.7), `compiler autolimits="true"`, `option` padrão (Euler, dt 0,002, cone piramidal, impratio 1, noslip 0): nq 9 · nv 8 · nu 2 · 5 geoms.

| Peça | Definição | Efeito |
| --- | --- | --- |
| corpo `car` | `freejoint` + `mesh chasis` (só vértices → casco convexo) | chassi |
| rodas | `class="wheel"`: cilindro `size=".03 .01"`, corpo com `zaxis="0 1 0"`, 1 `hinge` (`left`/`right`) | 2 contatos dim 3 por roda |
| `front wheel` | esfera r=.015, `condim="1" priority="1"` | apoio SEM atrito (o priority vence o condim 3 do piso) |
| `default/joint` | `damping=".03"`, `actuatorfrcrange="-0.5 0.5"` | o amortecimento fixa a velocidade máxima: ω = 0,5/0,03 = 16,67 rad/s → v = ω·r = 0,498 m/s |
| tendões `fixed` | `forward` (coef .5/.5) e `turn` (−.5/.5) | modo comum e modo diferencial das duas rodas |
| atuadores | 2 `motor` (`ctrlrange` ±1), um por tendão | ctrl=1 → força de tendão 1 → 0,5 N·m por roda |
| sensores | 2 `jointactuatorfrc` | torque TOTAL na junta, depois da soma e do clamp (`actuatorfrc` lê antes do clamp) |

O limite fica na JUNTA (`actuatorfrcrange`), não no atuador: dois atuadores somam-se em cada roda, então (forward=1, turn=.5) pede 0,25/0,75 N·m e a roda direita é cortada em 0,5 (`modeling.rst` §Force limits: "similar to a Dubin's Car"). Medido ✔ testado:

| ctrl (forward; turn) | resultado |
| --- | --- |
| (1; 0) | rodas 16,667 rad/s · v = 0,498 m/s |
| (0; 1) | gira no lugar: ψ̇ ≈ 7,05 rad/s |
| (1; 0,5) | v ≈ 0,38 m/s · ψ̇ ≈ 1,82 rad/s · R = v/ψ̇ ≈ 0,21 m (±0,5% conforme a janela); torque L/R = 0,25/0,5 |
| (1; 0,25) | R ≈ 0,51 m |

Em repouso: 5 contatos (esfera dim 1 + 2 dim 3 por roda), `nefc` = 17.

```python
import mujoco, numpy as np
m = mujoco.MjModel.from_xml_path("docs/upstream/mujoco/model/car/car.xml")   # a partir da raiz do projeto
d = mujoco.MjData(m)
print(m.nq, m.nv, m.nu, m.ngeom, round(mujoco.mj_getTotalmass(m), 4), mujoco.mjtIntegrator(m.opt.integrator).name)
def go(fwd, turn, T=5.0):
    mujoco.mj_resetData(m, d)
    for _ in range(int(T / m.opt.timestep)):
        d.ctrl[:] = [fwd, turn]                        # ordem: forward, turn (nenhum atuador multi-entrada)
        mujoco.mj_step(m, d)
    Rm = d.body("car").xmat.reshape(3, 3)
    return (Rm.T @ d.qvel[:3])[0], (Rm.T @ d.qvel[3:6])[2]       # v no corpo (m/s), guinada (rad/s)
for fwd, turn in [(1, 0), (0, 1), (1, .5), (1, .25)]:
    v, w = go(fwd, turn)
    print(f"forward={fwd} turn={turn}: v={v:.3f} m/s yaw={w:.3f} rad/s R={v / w if fwd and w > .1 else float('nan'):.3f} m  torque L/R={d.sensor('left').data[0]:.2f}/{d.sensor('right').data[0]:.2f}")
```

Bases com rodas no Menagerie (`docs/upstream/mujoco_menagerie/`; conferido nos XML/README do espelho):

| Modelo | Esquema de rodas |
| --- | --- |
| `hello_robot_stretch` | igual ao car.xml: tendões `forward`/`turn` ±.5 + `motor ctrlrange="-1 1" gear="3" forcerange="-100 100"`, joint `damping=".3"`; `implicitfast`, `cone="elliptic"`, `impratio="1"`, `noslip_iterations="2"`, `solref="0.005 1"`; roda de colisão cilindro `.05 .0125`; rodízio esfera `condim="1" priority="1"` |
| `pal_tiago` | 1 `velocity kv="100" ctrlrange="-5 5"` por roda, `actuatorfrcrange="-100 100"`, rodas em malha, rodízios de 2 hinges com `condim="6"`, `implicitfast` |
| `stanford_tidybot` | NÃO simula rodas: base = `slide` x + `slide` y + `hinge` com `position` (x/y kp 1e6 kv 5e4; th kp 5e4 kv 1e3) |
| `robot_soccer_kit` | rolos omni passivos como juntas (20 por roda), colisão por cilindros, `noslip_iterations="1"` |

## 2. Receita: carro de 4 rodas do zero
Convenção do template: +X frente, +Y esquerda, +Z cima. Ordem de trabalho: geometria → juntas → atuadores → tração → suspensão → validar (`inspect_model.py <xml> --tree`, depois §4).

| Item | Receita | Por quê |
| --- | --- | --- |
| roda | `type="cylinder" size="r meia_largura"`; o eixo do cilindro é o z local → `zaxis="0 1 0"` (ou `euler="90 0 0"`); `mass` no geom (I_giro = ½·m·r²) | cilindro: 2 contatos (bordas); esfera/elipsoide 1; cápsula 2; caixa 0–4 (rolando oscila) ✔ |
| giro | `hinge axis="0 1 0"` (giro + = rola para +x); `damping` pequeno (0,0005) | v terminal = r·Στ_rodas/Σdamping: 0,04·(2·0,15)/(4·0,0005) = 6,0 → 5,93 m/s medido; car.xml: 0,03·1/0,06 = 0,5 → 0,498 |
| direção | `hinge axis="0 0 1"` no MESMO corpo da roda | juntas do mesmo corpo se compõem na ordem do XML: `slide z` (suspensão) → `hinge z` (direção) → `hinge y` (giro) |
| chassi | `contype="0" conaffinity="0"` (só pneus colidem) ou, como no template, `contype="2" conaffinity="0"` com piso `conaffinity="3"` (chassi toca só o piso) | evita contato chassi-roda |
| massa | CG e I_zz comandam a guinada: `<inertial>` explícito ou geoms de caixa; visuais com `mass="0"` | visual+collision dobra a massa |

**Atuadores** (todos compilados no XML abaixo): `drive` = velocidade das rodas; `steer_*` = servo de posição.

| Função | Atuador | Notas |
| --- | --- | --- |
| tração por torque | `motor` por roda (template: `ctrlrange` ±1,5 N·m + PI de velocidade em Python, kp 2, ki 3, anti-windup) | limite o torque por roda a ≲ μ·N·r (≈ μ·m·g·r/4), senão patina (§4–§5) |
| tração por velocidade | `velocity kv` na roda ou no tendão; ctrl em rad/s | erro estático ≈ Σdamping/kv (2% previsto, 2,5% medido); `kv` → `implicitfast`; ⚠ `ctrl=0` FREIA (roda livre: zere `gainprm[0]` e `biasprm[2]`) |
| PI de velocidade | Python (template) | ⚠ `<pid input="vel" ki=…>` não compila: "pid controller states require the pos input" |
| direção | `position kp="50" dampratio="1"` + junta `armature="0.002"` `damping="0.05"` | `dampratio=1` → kv = 0,638; ctrl em rad |

**Ackermann** (L entre-eixos, t bitola, δ ângulo de bicicleta, + = esquerda):
R = L/tanδ (eixo traseiro); R_CG = √(R² + l_r²); δ_int = atan(L/(R − t/2)); δ_ext = atan(L/(R + t/2)) (forma robusta: `arctan2(L·tanδ, L ∓ t/2·tanδ)`); ψ̇ = v·tanδ/L; β = atan(l_r·tanδ/L); ω_ext/ω_int = (R + t/2)/(R − t/2).

**Tração em curva** (minicar, δ=0,30, v_cmd 1,5 m/s; ω_ext/ω_int cinemático 1,230) ✔ testado:

| Esquema | ω_ext/ω_int | v real | Leitura |
| --- | --- | --- | --- |
| `velocity` num tendão `fixed` (coef .5/.5) | 1,220 | 1,456 m/s | diferencial aberto: regula a velocidade MÉDIA, metade do torque por roda |
| 2 × `velocity` (um por roda) | 1,128 | 1,410 | as rodas brigam entre si |
| `equality joint` (`rl_spin = rr_spin`) | 1,000 | 1,340 | eixo sólido: arrasta/subesterça |
| `motor` no tendão, ctrl=0,6 (sem servo) | roda interna 322 × externa 150 rad/s (8 s) | — | torque 0,3 N·m/roda > μ·N·r ≈ 0,18: patina, a interna dispara |

**Suspensão** por canto: `slide` z no corpo da roda com `stiffness`, `damping`, `range` e `springref = −m_s·g/k` (negativo: o chassi assenta em q=0), m_s = m_chassi/4 por canto: f_n = √(k/m_s)/2π, ζ = c/(2·√(k·m_s)), f_d = f_n·√(1−ζ²). ✔ Medido (1,5 kg, 1 cm de compressão inicial): k=400, c=10 → 4,85 Hz (teórica 4,75), ζ 0,411 (proj. 0,408); k=100, c=5 → 2,37 Hz (2,37), ζ 0,407.

**XML mínimo executado** (1,82 kg, L=0,24, t=0,16, r=0,04; tração traseira por tendão, rodas dianteiras esterçam; salve como `minicar.xml`):

```xml
<mujoco model="minicar">
  <compiler angle="radian" autolimits="true"/>
  <option timestep="0.002" integrator="implicitfast" cone="elliptic" impratio="1"/>
  <default>
    <geom friction="1 0.005 0.0001"/>
    <default class="wheel">
      <geom type="cylinder" size="0.04 0.0125" mass="0.08" rgba="0.15 0.15 0.15 1"/>
      <joint damping="0.0005"/>
    </default>
    <default class="susp">  <!-- springref = -(m_chassi/4)*g/k: o chassi assenta em q=0 -->
      <joint type="slide" axis="0 0 1" range="-0.02 0.02" stiffness="400" damping="10" springref="-0.0092"/>
    </default>
    <default class="steer">  <!-- angle="radian": range E ctrlrange em rad -->
      <joint type="hinge" axis="0 0 1" range="-0.5 0.5" damping="0.05" armature="0.002"/>
      <position kp="50" dampratio="1" ctrlrange="-0.5 0.5"/>
    </default>
  </default>
  <worldbody>
    <geom name="floor" type="plane" size="100 100 0.1"/>
    <body name="chassis" pos="0 0 0.0401">
      <freejoint name="root"/>
      <geom name="body" type="box" size="0.14 0.06 0.02" pos="0 0 0.02" mass="1.5" contype="0" conaffinity="0" rgba="0.8 0.2 0.2 1"/>
      <body name="fl" pos="0.12 0.08 0" childclass="wheel">
        <joint name="fl_susp" class="susp"/><joint name="fl_steer" class="steer"/><joint name="fl_spin" axis="0 1 0"/>
        <geom name="fl_tire" zaxis="0 1 0"/>
      </body>
      <body name="fr" pos="0.12 -0.08 0" childclass="wheel">
        <joint name="fr_susp" class="susp"/><joint name="fr_steer" class="steer"/><joint name="fr_spin" axis="0 1 0"/>
        <geom name="fr_tire" zaxis="0 1 0"/>
      </body>
      <body name="rl" pos="-0.12 0.08 0" childclass="wheel">
        <joint name="rl_susp" class="susp"/><joint name="rl_spin" axis="0 1 0"/>
        <geom name="rl_tire" zaxis="0 1 0"/>
      </body>
      <body name="rr" pos="-0.12 -0.08 0" childclass="wheel">
        <joint name="rr_susp" class="susp"/><joint name="rr_spin" axis="0 1 0"/>
        <geom name="rr_tire" zaxis="0 1 0"/>
      </body>
    </body>
  </worldbody>
  <tendon>  <!-- diferencial aberto: o servo regula a velocidade MÉDIA das rodas traseiras; cada roda recebe metade do torque -->
    <fixed name="rear_cage"><joint joint="rl_spin" coef="0.5"/><joint joint="rr_spin" coef="0.5"/></fixed>
  </tendon>
  <actuator>
    <velocity name="drive" tendon="rear_cage" kv="0.1" ctrlrange="-400 400" forcerange="-0.8 0.8"/>
    <position name="steer_l" joint="fl_steer" class="steer"/>
    <position name="steer_r" joint="fr_steer" class="steer"/>
  </actuator>
</mujoco>
```

Controle e validação (acesso por nome é seguro: nenhum atuador é multi-entrada; para a velocidade local use um `velocimeter` num site do chassi):

```python
import numpy as np, mujoco
L, T, R_W = 0.24, 0.16, 0.04                          # entre-eixos, bitola, raio da roda (m)
XML = open("minicar.xml").read()

def ackermann(delta):                                 # δ de bicicleta (rad, + = esquerda) -> (esq, dir)
    t = np.tan(delta)
    return np.arctan2(L * t, L - T / 2 * t), np.arctan2(L * t, L + T / 2 * t)

def circle_fit(x, y):                                 # raio do círculo ajustado (Kåsa)
    c = np.linalg.lstsq(np.c_[2 * x, 2 * y, np.ones_like(x)], x**2 + y**2, rcond=None)[0]
    return np.sqrt(c[2] + c[0]**2 + c[1]**2)

def drive(v, delta, secs=8.0, xml=XML, tire=None):
    m = mujoco.MjModel.from_xml_string(xml); d = mujoco.MjData(m)
    hook = tire(m) if tire else None
    bid, log = m.body("chassis").id, []
    for _ in range(int(secs / m.opt.timestep)):
        t = d.time
        d.actuator("drive").ctrl = min(1, t) * v / R_W                                # rad/s, rampa de 1 s
        d.actuator("steer_l").ctrl, d.actuator("steer_r").ctrl = ackermann(delta * min(1, t / 0.5))   # rad
        if hook: hook(m, d)
        mujoco.mj_step(m, d)
        vb = d.xmat[bid].reshape(3, 3).T @ d.qvel[:3]                                 # velocidade no referencial do chassi
        log.append((d.time, *d.xipos[bid, :2], *vb[:2], d.qvel[5]))
    return np.array(log)

lg = drive(1.0, 0.30); w = lg[:, 0] >= 5                                              # regime: 5–8 s
v, psi = np.hypot(lg[w, 3], lg[w, 4]).mean(), lg[w, 5].mean()
beta = np.degrees(np.arctan2(lg[w, 4], lg[w, 3])).mean()
print(f"R_fit {circle_fit(lg[w,1], lg[w,2]):.3f} m (cinemático no CG {np.hypot(L/np.tan(.3), L/2):.3f}) · psi {psi:.3f} rad/s (v·tanδ/L {v*np.tan(.3)/L:.3f}) · beta {beta:.1f}° (atan(½tanδ) {np.degrees(np.arctan(.5*np.tan(.3))):.1f}°)")
print("reta v_cmd=2:", round(drive(2.0, 0.0, 6)[-1, 3], 3), "m/s")
```

**⚠ Unidades**: com `compiler angle="degree"` (padrão) o `range` do hinge é convertido para rad, o `ctrlrange` do atuador NÃO. ✔ testado: `range="-0.5 0.5"` vira ±0,5° e o servo ainda recebe ±0,5 rad → R = 2,30 m em vez de 0,80 m (esterço real 6,59° para 19,03° pedidos), sem erro. Correção: `angle="radian"` ou `range="-28.6 28.6"` + `inheritrange="1"` na `<position>` (ctrlrange = ±0,499 rad; R = 0,799 m).

### Template `car` (`assets/templates/car/`)
2,74 kg, L 0,30, t 0,22, r 0,05; 2 `motor` traseiros + PI, 2 `position` (`inheritrange="1"`), pneus `friction="1.0 0.02 0.005" condim="4"`, `cone="elliptic" impratio="10"`, sem suspensão. Criar a partir dele: `new_experiment.py <nome> --template car`. `run.py --sem-video --saida "$TMPDIR/x"` aceita `--vel --delta --atrito` e sai com 0/1; usa `lab.mjkit` (`Ctrl`, `record`, `plot`). ✔ Medido (δ = 20°, exceto linha 3):

| Cenário | ψ̇ sim × bicicleta (rad/s) | β sim × cin. | Leitura |
| --- | --- | --- | --- |
| μ 1,0 · 1,5 m/s | +1,705 × +1,819 (Δ 6,3%) | 9,2° × 10,3° | passa |
| μ 0,5 · 1,5 m/s | +1,459 × +1,819 (Δ 19,8%) | 7,3° × 10,3° | subesterço (FALHA esperada) |
| μ 1,0 · 2,5 m/s · δ 15° | +2,013 × +2,233 (Δ 9,8%) | 5,9° × 7,6° | passa |
| μ 0,35 · 2,0 m/s | +0,807 × +2,429 (Δ 67%) | 2,0° × 10,3° | derrapa, inclina 16° |

## 3. Contato pneu-solo
| Parâmetro | Regra (3.15.0) | Nota |
| --- | --- | --- |
| `friction` | 3 valores `[deslizamento, torsional, rolamento]`, padrão `1 0.005 0.0001`; os dois últimos em METROS (torsional ≈ diâmetro do patch; rolamento ≈ profundidade da deformação) | μ_r = C_rr·r; no contato, valores < 1e-5 viram 1e-5 (`friction=0` não zera; atrito nulo = `condim="1"`) |
| `condim` | 1 sem atrito · 3 padrão · 4 + torsional · 6 + rolamento; 0/2/5/7 → `Error: invalid condim in geom` | linhas por contato: elíptico 1/3/4/6, piramidal 1/4/6/10 |
| mistura | `condim`/`friction`: do geom de maior `priority`; empate → máximo (friction elemento a elemento). `solref`/`solimp`: média por `solmix`; `solref` direto (negativo) → mínimo | ✔ piso 0,5/0,005/0,0001 + roda 1/0,01/0,0002 → 1 1 0,01 0,0002 0,0002; com `priority=1` no piso → 0,5 0,5 0,005 …; solref 0,02+0,01 → 0,015 (solmix 1:3 → 0,0125) |
| `cone` | `option cone`: `pyramidal` (padrão) ou `elliptic`; global | Δ doc: `computation/index.rst` §condim diz "determined by the choice of constraint solver"; medido: PGS/CG/Newton aceitam os dois |
| `impratio` | padrão 1; razão atrito/normal da impedância (cone elíptico); ↑ endurece o atrito sem subir μ | piramidal: valores altos não recomendados (doc) |
| `noslip_iterations` | padrão 0; 1–3 | pós-processamento PGS; custo, pode instabilizar; fora da GPU |
| `solref`/`solimp` | `0.02 1` / `0.9 0.95 0.001 0.5 2` | `refsafe` (ligado) usa max(solref[0], 2·dt) |

**Mistura entre geoms (⚠)**: pneu de μ alto NÃO fica mais escorregadio num piso de μ baixo (máximo); para gelo use `priority` no piso ou `<contact><pair>`. O piso padrão (torsional 0,005) também vence um pneu com torsional 0,001 — ao ajustar `friction[1]`/`[2]` ajuste os dois geoms. Δ doc: `XMLreference` (condim) diz "máximo dos condim" e omite `priority`.

**condim 4 e 6** (esfera 1 kg, r=0,05; piso e esfera com `friction[1]`=0,001; cone elíptico) ✔ testado:
- Torsional: ω_z 10 rad/s → 10,0 (condim 3, nenhuma resistência) · 5,81 / 3,35 / 1,11 em 0,5 / 1 / 2 s (condim 4); piramidal 3,83 em 2 s. Δ doc (`modeling.rst` §Preventing slip): "condim 4 … preventing rotation around the normal" — na verdade AMORTECE (torque limitado por μ_t·N), não bloqueia.
- Rolamento (condim 6, `friction[2]` = μ_r = C_rr·r, minicar em roda livre, juntas sem damping): μ_r 0,0004 (C_rr 0,01) → 0,0907 m/s² (previsto μ_r·g/(r·(1+4I_w/(m·r²))) = 0,0902); 0,002 → 0,4512 (0,4509); 0,005 → 1,123 (1,127). Condim 3 ignora o coeficiente (0,000). Cone piramidal enfraquece o efeito (0,061 para 0,0004; a ficha mediu 0,046).

**Creep em rampa** (carro parado, 4 rodas travadas, μ=1, 10°, deriva em 5 s) ✔ testado:

| Cone / ajuste | piramidal (padrão) | elíptico impratio 1 | impratio 10 | impratio 100 | elíptico + `noslip_iterations=3` |
| --- | --- | --- | --- | --- | --- |
| deriva | 2,240 mm | 1,120 mm | 0,112 mm | 0,011 mm | 0,000 mm |

Doc (`modeling.rst` §Preventing slip): elíptico + `impratio` alto, depois `noslip` 1–3; não garante aderência exata. Limiar ≈ atan(μ): com μ=1, 44,5° fica parado (6,8 mm em 3 s) e 45,5° desliza (915 mm). O piramidal tem limite μ/√2 na diagonal (Q4).

**Frame tangente da roda cilíndrica** ✔: o eixo t1 do contato roda-plano fica FIXO no mundo (90°) para cilindro, esfera, elipsoide e caixa com a roda girada em yaw 0/30/60/90/135°; só a cápsula acompanha (90/120/150/180/−135°). O atrito anisotrópico (só em `<pair>`, `friction` com 5 valores) não separa longitudinal de lateral numa roda cilíndrica: para omni/mecanum use cápsulas ou rolos como juntas (`robot_soccer_kit`); Discussion #2749 sem resposta (ficha Q9).

**`timeconst`/`refsafe`** ✔: a dt=0,002, `solref="0.002 1"` e `"0.004 1"` dão a mesma penetração (0,0197 mm). Penetração estática média dos 8 contatos do minicar: 0,40 mm (solref 0,02), 0,12 (0,01), 0,031 (0,005) — com rodas rígidas, sem suspensão: 0,17 / 0,044 / 0,011; `solimp="0.99 0.99 …"` → 0,044 mm; `"0.5 0.5 …"` → 2,2 mm. `solreffriction` (só `<pair>`, só elíptico), `multiccd` e `nativeccd` em rodas: não verificado.

Aprofundar: `docs/upstream/mujoco/doc/computation/index.rst` (§condim, §Friction cones), `XMLreference.rst` (`geom/friction`, `option/cone`, `impratio`, `noslip_iterations`), `modeling.rst` (§Preventing slip); `docs_search.py --attr geom.condim`.

## 4. Validação com números (minicar, dt 0,002, implicitfast, μ=1) ✔ testado
| Grandeza | Medido | Esperado |
| --- | --- | --- |
| reta v_cmd 1/2/4/8 m/s | 0,975 / 1,950 / 3,899 / 7,799 (97,5%), t90 0,17/0,32/0,66/1,57 s, desvio lateral 0 | erro do servo P ≈ Σdamping/kv |
| R_fit (círculo ajustado), δ=0,30, v_cmd 0,5/1/2 | 0,797 / 0,799 / 0,787 m | R_CG = √(0,776² + 0,12²) = 0,785 m (R = L/tanδ = 0,776 m no eixo traseiro) |
| R_fit, v=1, δ 0,15/0,30/0,45 | 1,622 / 0,799 / 0,533 m | 1,593 / 0,785 / 0,511 (erro 1,9 / 1,7 / 4,3%) |
| ψ̇ a v=1, δ=0,30 | 1,221 rad/s | v·tanδ/L = 1,256 (97%) |
| β (deriva do CG) | +8,1° | atan(l_r·tanδ/L) = 8,8° (l_r = L/2) |

**Subesterço × atrito × velocidade.** Minicar acelerado a 0,2 m/s² já esterçado (δ=0,30; R_cin 0,785 m); célula = R_fit (m) · a_lat = v²/R_fit (m/s²); negrito = fora da cinemática:

| μ | 1 m/s | 2 m/s | 3 m/s | 4 m/s | desfecho |
| --- | --- | --- | --- | --- | --- |
| 0,5 | 0,80 · 1,1 | **0,94** · 4,0 | **2,31** · 3,8 | — | acaba girando (R 0,15 m) |
| 1,0 | 0,80 · 1,1 | 0,79 · 4,8 | **1,04** · 8,3 | **1,92** · 8,0 | platô 3,69 m/s: R 1,61 m, a_lat 8,47 (0,86·μ·g) |
| 1,5 | 0,80 · 1,1 | 0,79 · 4,8 | 0,79 · 10,6 | — | platô 3,00 m/s: R 0,79 m, a_lat 11,43 (0,78·μ·g): limite de tração |

R fica a < 2% da cinemática até a_lat ≈ 0,5–0,7·μ·g; perto de 0,8–0,86·μ·g o raio cresce 20–30% ou o carro gira. **Acelerar já em curva** com tração traseira é pior (μ=0,5, v_cmd 3): rampa de 1 s ou 3 s → giro (R 0,20 m, 0,79 m/s); rampa de 8 s → R 2,22 m (subesterço); torque ≤ 0,1 N·m/roda (μ·N·r ≈ 0,09) evita o giro (R 0,74–0,79 m, mas só chega a 1,3–1,7 m/s). Template `car` (δ=20°, entra na curva já em v), razão ψ̇ sim/bicicleta (✗ = checagem de 12% falha, exit 1):

| μ \ v (m/s) | 1,0 | 1,5 | 2,0 | 2,5 |
| --- | --- | --- | --- | --- |
| 1,0 | 0,94 | 0,94 | 0,91 | 0,79 ✗ |
| 0,7 | 0,93 | 0,91 | 0,78 ✗ | 0,54 ✗ |
| 0,5 | 0,89 | 0,80 ✗ | 0,54 ✗ | 0,35 ✗ |
| 0,35 | 0,80 ✗ | 0,55 ✗ | 0,33 ✗ (inclina 16°) | capota (180°) |

## 5. Limites
- **Sem modelo de pneu**: busca em todo `docs/upstream/` por "pacejka", "magic formula", "slip angle", "cornering stiffness" = 0 ocorrências; plugins oficiais: actuator, elasticity, sensor, sdf, decoders. Discussion #3569 sem resposta (ficha Q9). Pneus Pacejka/TMeasy/Fiala: Chrono::Vehicle (ficha Q9).
- **Força lateral por velocidade de deslizamento, não por ângulo de deriva** ✔: com vy0=0,05 m/s, t(1/e) da velocidade lateral = 16,0 ms para vx = 1, 2, 4 m/s (deriva 2,86°/1,43°/0,72°); com `solref` igual em piso e roda: 28/16/10/6 ms para 0,04/0,02/0,01/0,005; não muda com `impratio` 1/5/20 nem `noslip=3`. Não há rigidez de curva nem comprimento de relaxamento.
- **Alternativa `xfrc_applied`** ✔: roda em `condim="1"` + força tangencial própria no corpo da roda (torsor no CoM: F e (p − CoM)×F), Fz de `mj_contactForce` do passo anterior (atraso de 1 passo; `mjcb_control` não pode depender de forças do passo corrente — `APIglobals.rst`). Com B=10, C=1,3: t(1/e) = 8 / 20 / 36 ms para vx = 1 / 2 / 4 (cresce com vx) e R = 0,793 m (1 m/s), 0,996 m (3 m/s). Prova de conceito, não validada contra Pacejka real; o bloco abaixo continua o do §2 (usa `XML`, `drive`, `circle_fit`).

```python
def make_tire(m, B=10.0, C=1.3, MU=1.0, VMIN=0.5):    # Pacejka simplificado; contato roda-piso em condim=1
    wheels = {m.geom(n + "_tire").id: m.body(n).id for n in ("fl", "fr", "rl", "rr")}
    f6, res = np.zeros(6), np.zeros(6)
    def apply(m, d):                                   # chamar ANTES de mj_step (Fz do passo anterior)
        d.xfrc_applied[:] = 0
        fz, pc = {}, {}
        for k in range(d.ncon):
            c = d.contact[k]
            for g in (c.geom1, c.geom2):
                if g in wheels:
                    mujoco.mj_contactForce(m, d, k, f6)
                    b = wheels[g]; fz[b] = fz.get(b, 0) + f6[0]; pc[b] = pc.get(b, 0) + f6[0] * c.pos
        for b, N in fz.items():
            p = pc[b] / N                              # ponto de contato (média ponderada por Fz)
            xw = np.cross(d.xmat[b].reshape(3, 3)[:, 1], [0, 0, 1.0]); xw /= np.linalg.norm(xw)   # longitudinal
            yw = np.cross([0, 0, 1.0], xw)             # lateral
            mujoco.mj_objectVelocity(m, d, mujoco.mjtObj.mjOBJ_BODY, b, res, 0)
            vp = res[3:] + np.cross(res[:3], p - d.xipos[b])      # velocidade do material da roda no contato = deslizamento
            vref = max(abs(res[3:] @ xw), VMIN)
            fx, fy = (N * MU * np.sin(C * np.arctan(B * -(vp @ u) / vref)) for u in (xw, yw))
            s = np.hypot(fx, fy)
            if s > N * MU: fx, fy = fx * N * MU / s, fy * N * MU / s                              # círculo de atrito
            F = fx * xw + fy * yw
            d.xfrc_applied[b, :3], d.xfrc_applied[b, 3:] = F, np.cross(p - d.xipos[b], F)
    return apply

XML_T = XML.replace('<geom friction="1 0.005 0.0001"/>', '<geom friction="1 0.005 0.0001" condim="1"/>')   # só normal
for v in (1.0, 3.0):
    lg = drive(v, 0.30, xml=XML_T, tire=make_tire); w = lg[:, 0] >= 5
    print(f"pneu próprio v={v}: R_fit {circle_fit(lg[w,1], lg[w,2]):.3f} m")
```

- **Aderência lateral máxima** ✔: a_lat de pico ≈ 0,78–0,86·μ·g (§4). A 3,5 m/s e μ=1 (rampa de 1 s): cone piramidal 6,38 m/s² × elíptico 8,18 (−22%); `impratio=10` (8,18) e `noslip=2` (6,39) não mudam o limite.
- **Patinação em reta** ✔: v_cmd 15 m/s, μ=1: com 0,4 N·m/roda (> μ·N·r ≈ 0,18) as traseiras patinam e o carro sai da reta (|y| máx 6–9 m, caótico; ncon mín 0; sem aviso numérico); com 0,15 N·m/roda segue reto a 5,93 m/s; μ=1,5 + 0,4 N·m: reto a 14,62 m/s. A instabilidade é física (círculo de atrito): limite o torque ou use controle de tração. Template: μ 0,35 e v 2,5 m/s → o PI satura, a roda traseira dispara (700 rad/s) e o carro empina e capota.
- **Estabilidade numérica** ✔: curva δ=0,30, v_cmd 2 m/s: Euler dt 0,002/0,005 estável, dt 0,01 → BADQACC (vmax 2e5 m/s); `implicitfast` dt 0,01 estável. Direção kp=200 sem `armature`, `implicitfast` a dt 0,005 → BADQACC; com `armature="0.001"` estável.
- Não verificado: dados reais, escala de carro real (≥20 m/s, ~1500 kg), terreno não plano (hfield, degraus).

## 6. Escala em GPU (só ponteiros: `references/gpu-mjx-warp.md`, `references/gpu-benchmarks.md`)
- Não existe ambiente de veículo de rodas no Playground (busca local nula). MJWarp: `noslip_iterations > 0` → `NotImplementedError("noslip solver not implemented.")` (`docs/upstream/mujoco_warp/mujoco_warp/_src/io.py`, linhas 351–352); MJX: PGS levanta erro e `noslip_iterations>0` é IGNORADO em silêncio no MJX-JAX (MJWarp: `NotImplementedError`), condim 1/3/4/6 (1 não com elíptico); cilindro só colide com primitivas — pares esfera/caixa/malha/hfield–cilindro não suportados, plano–cilindro não está na lista (`mjx.rst`). Raio de curva/creep sem `noslip`: refaça a validação do §3–§4 no backend de GPU. Não testado aqui.

## 7. Correções ao relatório do usuário
- **Correção ao relatório do usuário** (§2.4: "condim é essencial; 4 bloqueia a rotação em torno da normal; 6 impede giro infinito") — PARCIAL: a semântica está certa (4 = torsional, 6 = rolamento; a doc cita pneu-estrada), mas (1) não é "essencial": o car.xml oficial usa condim 3 nas rodas e 1 na esfera e anda/curva (0,498 m/s; R 0,21 m); (2) o torsional AMORTECE, não bloqueia (10 → 1,11 rad/s em 2 s); (3) os coeficientes são comprimentos, não adimensionais (μ_r = C_rr·r); (4) o condim do contato é o máximo dos dois geoms (ou o do maior `priority`); 2 e 5 são inválidos; (5) com cone piramidal o efeito é bem menor — use `cone="elliptic"`.
- **Correção ao relatório do usuário** (§4.3: "4096 carros robóticos em paralelo") — PARCIAL: plausível, não é cenário oficial nem testado. Há lotes em GPU (exemplo oficial `batch_size = 4096`; Playground `num_envs=8192` em locomoção) mas não há ambiente/receita de carro de rodas; sem `noslip` na GPU, float32, cilindro restrito no MJX. Desempenho/memória de 4096 carros numa RTX 4070 de 8 GB: não verificado.

## Armadilhas
| Sintoma | Causa | Correção |
| --- | --- | --- |
| Raio de curva 3× maior, sem erro | `ctrlrange` do atuador não é convertido de graus (`range` é) | `angle="radian"`, ou `range` em graus + `inheritrange="1"` |
| Servo de direção/roda diverge (BADQACC, velocidades 1e5) | kp alto sem `armature`; Euler com `velocity`/`position` rígidos; dt 0,01 | `armature="0.001"`+, `integrator="implicitfast"`, dt ≤ 0,005 |
| Pneu "de gelo" não escorrega mais | friction = máximo dos dois geoms | `priority` no piso ou `<contact><pair>` |
| `friction[1]`/`[2]` do pneu sem efeito | condim 3; ou o piso padrão (0,005 / 0,0001) vence; ou cone piramidal | `condim` 4/6, mesmos valores no piso, `cone="elliptic"` |
| Roda livre freia / carro não rola | `velocity` com ctrl=0 é um freio (kv·(0−ω)) | zere `gainprm[0]` e `biasprm[2]`, ou use `motor` |
| Carro desliza parado na rampa | cone piramidal + impratio 1 (2,24 mm/5 s a 10°) | `cone="elliptic"`, `impratio` 10–100, `noslip_iterations` 1–3 |
| Patina em reta, empina e capota (template: μ 0,35, v 2,5) | torque > μ·N·r; PI sem controle de tração | limite o torque por roda, anti-windup por patinação |
| Gira ao acelerar já em curva | tração traseira satura o círculo de atrito | torque ≲ μ·N·r, ou acelere antes de esterçar |
| Curva mais aberta que a cinemática | subesterço, ou R medido no ponto errado (R_CG ≠ R do eixo) | compare com R_CG; reduza v ou aumente μ |
| Atrito anisotrópico não separa longitudinal/lateral | frame tangente fixo no mundo (cilindro) | cápsulas ou rolos como juntas |
| Roda deitada; chassi colide com rodas; massa dobrada | eixo do cilindro é z local; sem filtro de colisão; visual+collision | `zaxis="0 1 0"` + `hinge axis="0 1 0"`; `contype`/`conaffinity`; visuais `mass="0"` |
| `data.actuator('x').ctrl` grava no slot errado | atuador multi-entrada (`pid`, `dcmotor`, `orientation`) no modelo | `lab.mjkit.Ctrl` ou `data.ctrl[actuator_ctrladr[i]:+actuator_ctrlnum[i]]` |
