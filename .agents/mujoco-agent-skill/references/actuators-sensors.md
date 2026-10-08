# Atuadores, sensores, tendões, equality, mocap e keyframes

Como acionar e medir robôs, drones e veículos no MuJoCo 3.15: atalhos de atuador ↔ `general`, transmissões, limites, os 49 sensores, tendões, equality, mocap e keyframes.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: ficha `pesquisas/conhecimento/Q7.md`; `docs/upstream/mujoco/doc/{XMLreference.rst (actuator, sensor, tendon, equality, keyframe), computation/index.rst, modeling.rst, mjx.rst, dcmotor/dcmotor.tex}`; `docs/upstream/mujoco/model/{tendon_arm,slider_crank,car,humanoid}/`; templates `arm`/`car`/`quadrotor`; `scripts/mjkit.py`. `✔` = `✔ testado`: executado com `.venv/bin/python`.

## Quando ler este arquivo
- Escolher/parametrizar um atuador (servo PD, torque, velocidade, gripper, `pid`, `dcmotor`) ou converter atalho ↔ `general`.
- Ler sensores (IMU, contato, rangefinder), simular ruído/atraso, acoplar juntas (tendão, equality), usar mocap e keyframes.
- Depurar «o atuador não responde / grava no slot errado / diverge»: §5 e *Armadilhas*.

## 1. Como o MuJoCo calcula a força
- Atuador = **transmissão** (comprimento `L`, braços `∇L`) + **dinâmica** (`dyntype`, estado `act`) + **força** (`gaintype`/`biastype`). Internamente só existe `general`; os atalhos preenchem seus campos (o MJCF salvo grava tudo como `general`).
- Cadeia: `ctrl` →[`ctrlrange`]→ `u` → `act' = dyn(u, act)` → `F = gain·(act se há estado, senão u) + bias` →[`forcerange`]→ `actuator_force` → `qfrc_actuator = Σ ∇L·F` →[`actuatorfrcrange` da junta/tendão].
- `gain`: `fixed` = `gainprm[0]`; `affine` = `gainprm[0] + gainprm[1]·L + gainprm[2]·V`. `bias`: `none` = 0; `affine` = `biasprm[0] + biasprm[1]·L + biasprm[2]·V` (`L` = `actuator_length`, `V` = `actuator_velocity`). Servo: `F = kp·(u − L) − kv·V`.
- `dyntype`: `none` · `integrator` (`act' = u`) · `filter` (`(u − act)/dynprm[0]`) · `filterexact` (idem, exato: estável p/ qualquer τ > 0; `filter` diverge se τ < Δt) · `pid` · `dcmotor` · `muscle` · `user`. `gaintype` ∈ fixed, affine, muscle, dcmotor, pid, so3, user; `biastype` ∈ none, affine, muscle, dcmotor, so3, user (`so3` só em par).
- Padrões de `general`: dyn `none`, gain `fixed`, bias `none`, `dynprm=[1,0…]`, `gainprm=[1,0…]`, `biasprm=[0…]` (10 elementos), `gear="1 0 0 0 0 0"`, `actearly="false"`.
- Forças sem atuador: `d.qfrc_applied` (nv, em juntas) e `d.xfrc_applied` (nbody×6, cartesiana no body); somam-se a `qfrc_actuator`.

## 2. Atalhos → `general`
✔ Compilei cada atalho e li `actuator_{dyn,gain,bias}type` e `_{dyn,gain,bias}prm`. Num `<default>` use o MESMO atalho do atuador (ver Armadilhas).

| Atalho | `general` equivalente (dyn · gain · bias) | Atributos próprios (omissão) | Usar quando |
|---|---|---|---|
| `motor` | none · fixed `[1]` · none (= padrão) | só os comuns | força/torque direto: `F = ctrl`, `qfrc = gear·F`. Rotor: `site`; carro: roda ou `tendon` |
| `position` | none (ou `filterexact` se `timeconst>0`: +1 `act`) · fixed `[kp]` · affine `[0,−kp,−kv]` | `kp`=1 `kv`=0 `dampratio`=0 (excl. `kv`) `timeconst`=0 `inheritrange`=0 (excl. `ctrlrange`) | servo PD de junta/tendão: ctrl = alvo (rad, m) |
| `velocity` | none · fixed `[kv]` · affine `[0,0,−kv]` | `kv`=1 | ctrl = velocidade alvo (rad/s); rodas |
| `intvelocity` | integrator · fixed `[kp]` · affine `[0,−kp,−kv]` | `kp`=1 `kv`=0 `dampratio` `inheritrange` (→ `actrange`) | ctrl = velocidade do *setpoint*; `act` = setpoint de posição (1 estado) |
| `damper` | none · affine `[0,0,−kv]` · none; `ctrllimited` | `kv`=1 (≥0); `ctrlrange` ≥ 0 **obrigatório** | freio ativo `F = −kv·V·u` |
| `cylinder` | filter · fixed `[area]` · affine `bias(3)` | `timeconst`=1 `area`=1 `diameter` (vence; π(d/2)²) `bias`=0 0 0 | pneumático/hidráulico (1ª ordem) |
| `muscle` | muscle · muscle · muscle; `gainprm=biasprm=[range0 .75, range1 1.05, force −1, scale 200, lmin .5, lmax 1.6, vmax 1.5, fpmax 1.3, fvmax 1.2]`; `dynprm=[.01,.04,0]` | `timeconst`(2) `tausmooth` `range`(2) `force` `scale` `lmin` `lmax` `vmax` `fpmax` `fvmax` | **único** com Force-Length-Velocity (biomecânica; tendão/junta com `lengthrange`) |
| `adhesion` | none · fixed `[gain]` · none; trn `body`; `ctrllimited` | `body` (obrig.) `gain`=1; `ctrlrange` ≥ 0 **obrigatório** | ventosa/gecko: força normal nos contatos do body; à distância: `gap>0` nas geoms |
| `dcmotor` (3.7) | dcmotor · dcmotor · dcmotor, prm calculados (gain `[R,K,α,T0,kp,ki,kd,Vmax]`) | `resistance` `motorconst` `nominal` `inductance` `thermal` `saturation` `cogging` `lugre` `input`="voltage" `controller` | motor DC de datasheet (V → torque, back-EMF, saturação): sim-to-real. Sem `forcerange` (use `saturation`) |
| `pid` (3.12) | none/pid · pid `[ki]` · affine `[0,−kp,−kv]`; `dynprm=[imax, slewmax]` | `kp`=1 `kv`=0 `dampratio` `ki`=0 `imax`=0 `slewmax`=0 `input`="pos vel" `posrange` `velrange` `ffrange` `inheritrange` | setpoint de pos+vel(+ff), integral anti-windup. **Multi-entrada** |
| `orientation` (3.11) | none · so3 `[kp]` · so3 `[0,−kp,−kv]`; trn `so3` | `kp`=1 `kv`=0 `dampratio` `input`="expmap" (3) ou "quat" (4) | servo geodésico em SO(3): *ball joint* ou site+`refsite`. **Multi-entrada** ✔ expmap `[0,0,.8]` → quat `[.9211,0,0,.3894]` |

**Unidade do `ctrl`**: `motor` N·m (N); `position` rad (m); `velocity`/`intvelocity` rad/s; `muscle` 0–1 (excitação); `damper`/`adhesion` ≥ 0, tipicamente 0–1 (adhesion: força = ctrl·`gain`); `dcmotor` V (ou `pos` rad, `vel` rad/s, `ff` N·m); `pid` `pos` rad, `vel` rad/s, `ff` N·m; `orientation` rad (expmap) ou quaternion `[w x y z]`.

## 3. Limites, unidades e `gear`
| Limite | Atua em | Notas |
|---|---|---|
| `ctrlrange` (+`ctrllimited`) | entrada `u` | `auto` liga o clamp se `ctrlrange` dado e `autolimits=true` (padrão); com `autolimits="false"` sem `ctrllimited` = erro ✔; global: bit `mjDSBL_CLAMPCTRL` em `m.opt.disableflags` (XML: `flag clampctrl="disable"`) ✔ |
| `forcerange` (+`forcelimited`) | `F` (`actuator_force`) | útil em servos ✔; em `orientation` limita a **norma** do torque (inferior = 0) |
| `joint/actuatorfrcrange` | Σ forças de todos os atuadores na junta | leia com `jointactuatorfrc` (pós-clamp); `actuatorfrc` é pré-clamp da junta ✔ (1.0 vs 0.3) |
| `tendon/actuatorfrcrange` | idem, no tendão | `actuatorfrclimited="auto"` só é padrão desde 3.14.0 (antes ignorado em silêncio) |
| `actrange` (+`actlimited`) | estado `act` | `intvelocity`: `auto` só liga com `actrange` ✔ |
| `group` + `opt.disableactuator` | grupos 0..30 | `m.opt.disableactuator = 1 << g` → sem força ✔ (alterne torque/posição) |
| `nsample` + `delay` | `ctrl` do atuador | `delay = n·Δt` com `nsample=n` (mín. 1 passo) ✔ n=3: força 0 nos 3 primeiros passos, depois 1,0 |

- **Unidades**: `ctrlrange`, `actrange`, `lengthrange` são nativos (rad, m), **NÃO convertidos de graus** mesmo com `compiler angle="degree"` ✔ (`ctrlrange="-90 90"` → ±90 rad). `inheritrange="1"` copia o `range` da junta/tendão já em rad ✔ (±1,5708; `X<1` encolhe em torno do ponto médio; erro se o alvo não tem `range`). `kp`: N·m/rad; `kv`: N·m·s/rad.
- `gear` escala `L`, `∇L`, `V` e `F`; o ganho só escala `F` ✔ (`motor gear=2`, ctrl 0,5: `actuator_force` 0,5, `qfrc` 1,0). `damping`/`armature` do atuador são refletidos ×`gear²`; `kv` não precisa (já está no espaço do atuador).

## 4. Transmissões
| Atributo | `L` | `gear` | Uso |
|---|---|---|---|
| `joint` | hinge/slide: `gear[0]·q`; ball: eixo `gear[0:3]` no frame filho (L circular); free: 0 | free: `gear[0:3]` translação (mundo) + `gear[3:6]` rotação (filho) | braços, rodas |
| `jointinparent` | como `joint`, eixo de ball/free no frame do **pai** | idem | não testado |
| `tendon` | `gear[0]·ten_length` (fixed ou spatial) | `gear[0]` | tração diferencial, gripper, músculos ✔ |
| `site` | 0 | 6D no **frame do site** `[fx fy fz tx ty tz]` | hélices/jatos ✔ (2 rotores `gear="0 0 1 0 0 ±.02"`, ctrl = m·g/2 → qacc linear 0; ver `references/drones.md`) |
| `site`+`refsite` | `gear`·pose relativa (m ou rad) | normalizado, só os 3 primeiros **ou** só os 3 últimos ≠ 0 | `position` **cartesiano** sem IK ✔ (2 elos, `gear="1 0 0 0 0 0"` e `"0 0 1 0 0 0"`, kp=400 kv=40: ctrl `[.5,−.4]` → ponta (0,500; −0,400)) |
| `body` | 0 | — | `adhesion` |
| `cranksite`+`slidersite`+`cranklength` | posição do pistão × `gear` (desliza em +Z de `slidersite`) | `gear[0]` | biela-manivela ✔ `slider_crank.xml`: L = 0,068; 0,046; 0,118 |
| so3 (`orientation`) | 3 saídas (força 3D no frame filho) | — | ball joint, site+`refsite` |

## 5. ⚠ Atuadores multi-entrada e o acessor por nome
`ctrlnum` = nº de entradas: `pid` (`input="pos vel"` por omissão: 2), `dcmotor` com `input` em `pos vel ff voltage` (omissão `voltage` = 1) e `orientation` (3 ou 4; 3 saídas de força). Logo `nu = Σ ctrlnum ≥ nactuator` e `nout = Σ outnum`: há **três espaços de índice**.

| Espaço | Tamanho | Campos | Bloco do atuador `i` |
|---|---|---|---|
| atuador | `nactuator` | `gainprm biasprm dynprm *type forcerange forcelimited actrange trnid group ctrladr ctrlnum outadr outnum` | `[i]` |
| controle | `nu` | `data.ctrl`, `actuator_ctrlrange`, `actuator_ctrllimited` | `[actuator_ctrladr[i] : +actuator_ctrlnum[i]]` |
| saída | `nout` | `data.actuator_force/length/velocity/moment`, `actuator_gear`, `actuator_lengthrange` | `[actuator_outadr[i] : +actuator_outnum[i]]` |

Os acessores nomeados (`data.actuator('x').ctrl/.force/.length`, `model.actuator('x').ctrlrange/.gear`) usam o **ID** do atuador nos três espaços (1 slot só: `d.actuator('x').ctrl.shape == (1,)`): só valem se os atuadores anteriores forem todos de 1 controle e 1 saída (✔ `d.actuator('mot').force` = 0.0 em vez de 2.0; `m.actuator('mot').gear[0]` = 1 em vez de 7). Reproduzido abaixo (ver também `references/python-api.md` §2, `bind()`); o teste upstream (`bindings_test.py`) codifica `data.ctrl[actuator_id]` — não se sabe se é limitação ou bug.
```python
import sys, mujoco
sys.path.insert(0, ".agents/mujoco-agent-skill/scripts")  # cwd = raiz do projeto (ou: from lab import mjkit)
import mjkit
XML = """<mujoco><worldbody>
  <body><joint name="j1" axis="0 1 0"/><geom size=".05"/></body>
  <body pos="1 0 0"><joint name="j2" axis="0 1 0"/><geom size=".05"/></body>
  <body pos="2 0 0"><joint name="j3" axis="0 1 0" range="-1 1"/><geom size=".05"/></body></worldbody>
  <actuator><motor name="mot" joint="j1"/><pid name="pid" joint="j2" kp="10" kv="1"/>
            <position name="pos" joint="j3" kp="10" ctrlrange="-1 1"/></actuator></mujoco>"""
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m)
print(m.nactuator, m.nu, m.nout, m.actuator_ctrladr, m.actuator_ctrlnum)    # 3 4 3 [0 1 3] [1 2 1]
print([mujoco.mj_actuatorInputName(m, 1, k) for k in range(2)])             # ['pos', 'vel']  (entradas do pid)
d.actuator("pos").ctrl[:] = 99                                              # ✗ usa o ID do atuador (2) como índice
print(d.ctrl, m.actuator("pos").ctrlrange)                                  # [ 0.  0. 99.  0.] [0. 0.]  ← slot e range errados
def slots(m, name):                                                         # ✔ blocos de controle e de saída do atuador
    i = m.actuator(name).id; c, o = m.actuator_ctrladr[i], m.actuator_outadr[i]
    return slice(c, c + m.actuator_ctrlnum[i]), slice(o, o + m.actuator_outnum[i])
d.ctrl[:] = 0; cs, outs = slots(m, "pos"); d.ctrl[cs] = 99
mujoco.mj_forward(m, d)
print(d.ctrl, m.actuator_ctrlrange[cs], d.actuator_force[outs])              # [ 0.  0.  0. 99.] [[-1.  1.]] [10.]  (= kp·(clamp(99)=1 − 0))
mjkit.Ctrl(m).set(d, "pid", [0.5, 0.0]); print(d.ctrl)                      # [ 0.   0.5  0.  99. ]
```
- `mj_actuatorInputName(m, i, k)`: nomes `pos vel ff` (pid), `rx ry rz` ou `qw qx qy qz` (orientation), `pos vel ff voltage` (dcmotor). `mj_resetCtrl` (3.11): neutro = 0, exceto `quat` = `[1,0,0,0]` (✔ `ctrl=0` com `input="quat"` = quaternion nulo → sem torque). `nsample`/`mj_readCtrl` guardam `ctrlnum` valores por amostra (3.14). ⚠ `mjkit.Ctrl.set(d, "pid", 0.5)` com **escalar** replica em todas as entradas (pos=vel=0.5): passe o vetor `[pos, vel]`.
- Ferramentas que indexam `actuator_ctrlrange[i]`/`actuator_gear[i]` por ID erram aqui (✔ em 2026-10-07 o `inspect_model.py` mostrou `ctrlrange None`/`gear 1` para um `motor` `ctrlrange="-2 2" gear="7"` depois de `pid`+`orientation`).

## 6. Receitas testadas
- **PD (`position`)**: ctrl = alvo em rad. `dampratio=1` = criticamente amortecido (`kv = 2·√(kp·m_refletida)`, ignora `damping`/`frictionloss` passivos); `kv=0` oscila. **Regra do `kv`**: é termo do atuador, **explícito no Euler** (padrão): instável se `kv·Δt/J > 2`, J = inércia refletida (✔ kv=9 estável, kv=11 diverge com J=0,01, Δt=0,002). Use `implicitfast`/`implicit` (a doc recomenda), ou `damping` da junta/atuador (implícito até no Euler).
- **Torque** (`motor`): ctrl = F do atuador, `qfrc = gear·ctrl`; humanoid usa `gear` 20–120 com `ctrlrange ±1`.
- **Velocidade**: `velocity` (só feedback; a doc o chama de instável na prática) ou `intvelocity` (integra o ctrl num setpoint de posição; o modo usual em hardware).
```python
import mujoco, numpy as np
def sim(act, u, J=0.1, integ="implicitfast", T=3.0, jx=""):              # 1 hinge sem gravidade, inércia J; devolve (m, d, |q|máx)
    m = mujoco.MjModel.from_xml_string(f"""<mujoco><option timestep="0.002" integrator="{integ}" gravity="0 0 0"/><worldbody>
      <body><inertial pos="0 0 0" mass="1" diaginertia="{J} {J} {J}"/><joint name="j" axis="0 1 0" {jx}/></body></worldbody>
      <actuator>{act}</actuator></mujoco>""")
    d = mujoco.MjData(m); d.ctrl[0] = u; pk = 0.0
    for _ in range(int(T / m.opt.timestep)):
        mujoco.mj_step(m, d); pk = max(pk, abs(d.qpos[0]))
        if pk > 1e3: break
    return m, d, pk
m, d, pk = sim('<position joint="j" kp="100" dampratio="1"/>', 0.8)       # PD criticamente amortecido: kv = 2·√(kp·J)
print(m.actuator_biasprm[0, :3].round(4), d.qpos[0].round(4), round(pk, 3)) # [  0.   -100.     -6.3246] 0.8 0.8 → sem overshoot
print(round(sim('<position joint="j" kp="100"/>', 0.8)[2], 2))              # 1.6 → kv=0 oscila (pico = 2× o alvo)
for integ in ("Euler", "implicitfast"):                                     # kv·Δt/J = 20 ≫ 2
    print(integ, sim('<position joint="j" kp="100" kv="100"/>', 0.5, J=0.01, integ=integ, T=1)[2] > 1e3)   # Euler True (diverge) | implicitfast False
print(round(sim('<position joint="j" kp="100"/>', 0.5, J=0.01, integ="Euler", T=1, jx='damping="100"')[2], 2))  # 0.32 → estável: damping é implícito até no Euler
m, d, _ = sim('<motor joint="j" gear="2"/>', 0.5, T=0.002)                  # torque: ctrl é a força do atuador; qfrc = gear·F
print(d.actuator_force[0], d.qfrc_actuator[0])                              # 0.5 1.0
m, d, _ = sim('<velocity joint="j" kv="5"/>', 2.0, T=2); print(d.qvel[0].round(4))                         # 2.0 rad/s
m, d, _ = sim('<intvelocity joint="j" kp="100" kv="10" actrange="-1 1"/>', 0.5, T=1); print(d.act[0].round(3))  # 0.5 = ∫ctrl dt (setpoint de posição)
```
**Gripper** (receita do Franka Panda, Menagerie): tendão `fixed` `split` (coef .5/.5) + `equality joint` (espelha os dedos) + `general` no tendão com `ctrlrange 0–255` remapeado a 0–0,04 m (`gainprm[0] = 0,04·kp/255`, `kp=100`). **`general` precisa de `biastype="affine"`**: sem ele (padrão `none`) o `biasprm` é ignorado em silêncio e o servo não existe. A Robotiq 2F85 acrescenta 2 `connect` (laço fechado). Alternativa por contato: `adhesion` (`ctrlrange 0 1`, `gap>0`).
```python
import mujoco
G = """<mujoco><option gravity="0 0 0"/>
<default><geom type="box" size=".01 .005 .03" mass=".015" contype="0" conaffinity="0"/></default>
<worldbody><body name="mao" pos="0 0 .5"><geom size=".05 .05 .01" mass="1"/>
  <body pos="0 0 -.04"><joint name="f1" type="slide" axis="0 1 0" range="0 .04"/><geom/></body>
  <body pos="0 0 -.04" quat="0 0 0 1"><joint name="f2" type="slide" axis="0 1 0" range="0 .04"/><geom/></body></body></worldbody>
<tendon><fixed name="split"><joint joint="f1" coef=".5"/><joint joint="f2" coef=".5"/></fixed></tendon>
<equality><joint joint1="f1" joint2="f2" solimp=".95 .99 .001" solref=".005 1"/></equality>
<actuator><general name="grip" tendon="split" ctrlrange="0 255" forcerange="-100 100"
          gainprm="0.01568627451" biasprm="0 -100 -10" biastype="affine"/></actuator></mujoco>"""
for tag, xml in (("affine", G), ("sem biastype", G.replace(' biastype="affine"', ""))):
    for u in (255, 128, 0):                          # ctrl 0–255 → abertura 0–0,04 m (gainprm[0] = 0,04·kp/255, kp = 100)
        m = mujoco.MjModel.from_xml_string(xml); d = mujoco.MjData(m); d.ctrl[0] = u
        for _ in range(1000): mujoco.mj_step(m, d)
        print(f"{tag:13s} ctrl={u:3d} f1={d.qpos[0]:.4f} f2={d.qpos[1]:.4f} alvo={u * .04 / 255:.4f}")
# affine: 0.0400 / 0.0201 / 0.0000 (= alvo) · sem biastype: 0.0427 / 0.0413 / 0.0000 (não servoa; ctrl=128 deveria dar 0.0201)
```
**`pid`** — `ctrl = [pos, vel]` (`input` escolhe o subconjunto de `pos vel ff`); com `vel`=0 é idêntico a `position`. `ki>0` liga a integral (+1 `act`, exige `pos`); `imax` limita `act` em rad·s (força integral ≤ `ki·imax`); `slewmax` limita a taxa do setpoint (+1 `act`). A gravidade "afunda" um servo P/PD (erro −0,0128 rad abaixo): use `ki` ou `gravcomp="1"` no body (✔ erro 0,0; template `arm`).
**`dcmotor`** — ctrl = tensão (V) por omissão (`input="voltage"`); `nominal="V τ_stall ω_vazio"` dá `K=V/ω0`, `R=K·V/τ_stall`; `τ = K/R·(V − K·ω)`. `input="pos vel ff"` liga o PID de bordo: `controller="kp ki kd slewmax Imax Vmax"` em **espaço de torque** (ganho de datasheet em V × `K/R`); `Vmax` só limita a tensão do controlador, o `voltage` cru é limitado por `ctrlrange`. `inductance`, `thermal`, `lugre`, `ki`, `slewmax` criam estados (+1 `act` cada) que **não podem** alternar zero↔positivo após compilar; `input="none"` = passivo (atrito/cogging/freio por back-EMF).
```python
import mujoco
def build(act, g="0 0 -9.81"):                      # braço de 1 grau de liberdade (haste de 1 kg, 0,3 m) sob gravidade
    return mujoco.MjModel.from_xml_string(f"""<mujoco><option timestep="0.002" integrator="implicitfast" gravity="{g}"/><worldbody>
      <body pos="0 0 1"><joint name="j" axis="0 1 0"/><geom type="capsule" fromto="0 0 0 .3 0 0" size=".02" mass="1"/></body></worldbody>
      <actuator>{act}</actuator></mujoco>""")
def hold(act, ctrl, T=4):                           # erro estacionário de posição (alvo 0,5 rad)
    m = build(act); d = mujoco.MjData(m); a = m.actuator_ctrladr[0]; d.ctrl[a:a + m.actuator_ctrlnum[0]] = ctrl
    for _ in range(int(T / m.opt.timestep)): mujoco.mj_step(m, d)
    return round(0.5 - d.qpos[0], 5)
print(hold('<position joint="j" kp="100" kv="10"/>', [0.5]))                          # -0.01282: a gravidade "afunda" o servo P/PD
print(hold('<pid joint="j" kp="100" kv="10" ki="300" imax="1"/>', [0.5, 0.0]))        # ≈ 0: ki zera o erro; ctrl = [pos, vel]
print(hold('<pid joint="j" kp="100" kv="10" ki="300" imax=".001"/>', [0.5, 0.0]))     # -0.00979: imax satura ∫erro (força integral máx = ki·imax = 0,3 N·m)
try: build('<pid joint="j" kp="100" kv="10" ki="300" slewmax="1"/>')                  # ki + slewmax juntos: 3.15.0 NÃO compila (a doc diz que sim)
except ValueError as e: print(e.args[0].splitlines()[0])                              # Error: actdim > 1 is only allowed for dyntype 'user' and 'dcmotor'
m = build('<dcmotor joint="j" nominal="12 .5 100"/>', g="0 0 0"); d = mujoco.MjData(m)   # nominal = "V  torque_stall  vel_vazio" → R, K
print(m.actuator_gainprm[0, :2])                                                      # [2.88 0.12]  (R em Ω, K em N·m/A)
for w in (0, 50, 100):                              # curva torque–velocidade a 12 V: τ = K/R·(V − K·ω)
    d.qvel[0] = w; d.ctrl[0] = 12; mujoco.mj_forward(m, d); print(w, d.qfrc_actuator[0].round(4))   # 0 0.5 | 50 0.25 | 100 0.0
```
✔ `dcmotor` (J=0,01): 12 V por 10 s → 99,325 rad/s (analítico 99,326; `t_m = R·J/K² = 2 s`); `saturation="0.3 0 0"` → `forcerange ±0.3`; `inductance="0 .01"` → `na=1`; `input="none"` → `nu=0`; `input="pos vel" controller="2 0 .05 0 0 12"` → alvo 0,5 rad atinge 0,5003. Não testados: térmica, LuGre, cogging, `slewmax/Imax/Vmax` do `dcmotor` e qualquer validação contra motores reais. MjSpec: `set_to_pid(kp, kv, dampratio, ki, imax, slewmax, …)` — passe por **palavra-chave** (o 3º posicional é `dampratio`).

## 7. Sensores
Saídas concatenadas em `sensordata` (não entram na física). Leia por nome: `d.sensor('acc').data` (view: `.copy()`), `m.sensor('acc').adr/.dim`. ✔ Dimensões/estágios conferidos compilando 47 dos 49 tipos de `mjtSensor` (7+2+8+6+3+9+3+4+2+5 = 49 na tabela) (`tactile` e `plugin` por doc); nomes do enum ≠ XML: `jointactfrc`/`tendonactfrc`/`geomdist`/`geomnormal`/`geomfromto` = `jointactuatorfrc`/`tendonactuatorfrc`/`distance`/`normal`/`fromto`.

| Grupo | Elementos XML → dim | Notas |
|---|---|---|
| Site | `touch` 1 · `accelerometer` 3 · `velocimeter` 3 · `gyro` 3 · `force` 3 · `torque` 3 · `magnetometer` 3 | frame **local** do site. `accelerometer` inclui a gravidade ✔. `force`/`torque`: filho→pai no frame do site (body "dummy" soldado). `touch` ≥ 0: contatos na zona do site, só geoms do mesmo body |
| Raio/câmera | `rangefinder` 1 por site (raio no **+Z**; −1 sem acerto) ou W×H por `camera` (olha **−Z**) ✔ 4×3=12 · `camprojection` 2 | `data="dist dir origin point normal depth"` = 1+3+3+3+3+1 por raio (ordem fixa); pixels com origem sup. esq., sem recorte |
| Junta | `jointpos` 1 · `jointvel` 1 (só hinge/slide) · `ballquat` 4 · `ballangvel` 3 · `jointactuatorfrc` 1 · `jointlimitpos/vel/frc` 1 | limite: `efc_pos − margin` (<0 se violado), 0 se livre |
| Tendão | `tendonpos` · `tendonvel` · `tendonactuatorfrc` · `tendonlimitpos/vel/frc` (todos 1) | |
| Atuador | `actuatorpos` · `actuatorvel` · `actuatorfrc` (1 por saída) | `actuatorfrc` = F antes do `actuatorfrcrange` |
| Frame | `framepos` 3 · `framequat` 4 · `framexaxis/yaxis/zaxis` 3 · `framelinvel` 3 · `frameangvel` 3 · `framelinacc` 3 · `frameangacc` 3 | `objtype`: body (frame **inercial**), xbody, geom, site, camera; `reftype/refname` = referencial (não nos `*acc`) |
| Subárvore | `subtreecom` 3 · `subtreelinvel` 3 · `subtreeangmom` 3 | |
| Geometria | `insidesite` 1 · `distance` 1 · `normal` 3 · `fromto` 6 | independem do pipeline de colisão; `cutoff` = distância máx. (padrão 0 = só penetração); `insidesite enclosed="true"` mede quanto o objeto sai do site |
| Contato | `contact` num × campos · `tactile` 3 × vértices da malha | campos em ordem fixa: `found`1 `force`3 `torque`3 `dist`1 `pos`3 `normal`3 `tangent`3; `reduce` none/mindist/maxforce/netforce; `tactile`: só geoms SDF |
| Globais | `e_potential` 1 · `e_kinetic` 1 · `clock` 1 · `user` (`dim`, `mjcb_sensor`) · `plugin` (dim do plugin) | |

- **IMU = `accelerometer` + `gyro` (+ `framequat` `objtype="site"`, + `magnetometer`) no mesmo site; NÃO existe `imu`** (como no Skydio X2 e no Crazyflie 2 do Menagerie; ver o template `quadrotor`).
- **`noise` NÃO injeta ruído** (removido na 3.1.4): só guarda σ em `sensor_noise` ✔. Some o ruído você mesmo. `cutoff>0` limita |valor| ✔. `delay = n·Δt` com `nsample ≥ n` lê n passos atrás ✔ (`delay` sem `nsample` = erro). `interval="período fase"` exige `nsample ≥ 1`: sem ele é **ignorado em silêncio** ✔ (com `nsample=1 interval=".01"` e Δt=0,002 o sensor atualiza a cada 5 passos).
- `contact` (declarativo, tamanho fixo `num × campos`, força no frame do contato — x = normal, que aponta do 1º ao 2º) × `data.contact` (variável; `mj_contactForce`): sensor para observações de RL/lógica, `data.contact` para análise ✔.
- ⚠ `mj_step` = `mj_forward` (calcula os sensores) + integração: depois do passo, `sensordata` está 1 passo atrás de `qpos` ✔ (`jointpos` 0,008 vs `qpos` 0,01); chame `mj_forward(m, d)` antes de ler se precisar do estado atual.
- `accelerometer`, `force`, `torque`, `framelinacc`, `frameangacc` disparam `mj_rnePostConstraint` (custo extra).
```python
import mujoco, numpy as np
np.set_printoptions(precision=4, suppress=True)
XML = """<mujoco><option timestep="0.002"/><worldbody><geom type="plane" size="5 5 .1"/>
 <body name="caixa" pos="0 0 .5"><freejoint/><geom type="box" size=".1 .1 .1" mass="1"/>
   <site name="imu"/><site name="raio" zaxis="0 0 -1"/></body>
 <body pos="2 0 1"><joint name="eixo" axis="0 1 0"/><geom size=".1" mass="1"/><site name="s2"/></body></worldbody>
<sensor><accelerometer name="acc" site="imu"/><gyro name="gyro" site="imu" noise=".5"/>
  <framequat name="quat" objtype="site" objname="imu"/><rangefinder name="alt" site="raio"/>
  <gyro name="gyro_cut" site="s2" cutoff="2"/><jointpos name="pos" joint="eixo"/>
  <jointpos name="atrasada" joint="eixo" nsample="2" delay=".004"/>
  <contact name="ct" body1="caixa" num="2" data="found force dist normal" reduce="maxforce"/></sensor></mujoco>"""
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m); d.qvel[6] = 5.0           # a roda gira a 5 rad/s
for _ in range(50): mujoco.mj_step(m, d)
print(d.sensor("acc").data)                                   # [0. 0. 0.]      queda livre: o acelerômetro mede força específica
for _ in range(750): mujoco.mj_step(m, d)
s = m.sensor("acc"); print(d.sensor("acc").data, s.adr, s.dim)   # [0. 0. 9.81] [0] [3]   repouso: +g no z local
print(d.sensor("gyro").data)                                  # [0. 0. 0.]      noise=.5 não injeta nada: o ruído é por sua conta
print(d.sensor("gyro_cut").data)                              # [0. 2. 0.]      ω = 5 rad/s com cutoff=2
print(d.sensor("alt").data, d.sensor("quat").data)            # [0.0999] [1. 0. 0. 0.]   rangefinder no +Z do site (apontado p/ baixo)
print(d.sensor("pos").data - d.sensor("atrasada").data)       # [0.02]          = ω·2·dt: delay=.004 lê 2 passos atrás
print(d.sensor("ct").data.reshape(2, 8))                      # 2 slots [found, F(n,t1,t2), dist, normal] = [4, 2.4525, 0, 0, -0.0001, 0, 0, -1]
f, tot = np.zeros(6), 0.0
for i in range(d.ncon): mujoco.mj_contactForce(m, d, i, f); tot += f[0]
print(d.ncon, round(tot, 2))                                  # 4 9.81   o mesmo contato em data.contact (tamanho variável); Σ normal = m·g
sigma = m.sensor("gyro").noise; print(d.sensor("gyro").data + np.random.default_rng(0).normal(0, sigma, 3))   # ruído gaussiano com o σ guardado
```

## 8. Tendões
- **`fixed`**: `L = Σ coef·q` (só juntas escalares), Jacobiano constante: acopla juntas sem geometria. `car.xml`: `forward` (coef .5/.5) e `turn` (−.5/.5) + 2 `motor` (`ctrlrange −1 1`) = tração diferencial ✔ (forward=1 → `qfrc` das rodas `[0.5, 0.5]`; turn=1 → `[−0.5, 0.5]`; ctrl=3 é clampado a 1) com `actuatorfrcrange` por junta e sensor `jointactuatorfrc`. `humanoid.xml`: `hamstring` (`hip_y` 0,5, `knee` −0,5) só limitado.
- **`spatial`**: caminho mínimo por `<site>`; `<geom>` de wrapping **só esfera/cilindro** (box = erro ✔), `sidesite` escolhe o lado (dentro da geom = passa por dentro), `<pulley divisor>`. ✔ 2 sites a 2 m → 2,0; esfera r=0,5 no caminho → 2,25565 (analítico 2,255650). `arm26.xml`: 6 `spatial` + `muscle`.
- Comuns: `limited`/`range` (+`margin`, `solreflimit`), `stiffness`/`damping` (polinômio a,b,c), `springlength` (1 valor; 2 = banda morta; −1 = de `qpos0`), `frictionloss`, `armature`, `actuatorfrcrange`. Sem atuador e com `range="0 X"` age como cabo (só puxa esticado).

## 9. Equality (`<equality>`)
| Tipo | Restrições | Para quê |
|---|---|---|
| `connect` | 3 | ponto fixo entre 2 bodies (laços): `body1`+`anchor` [+`body2`; omitido = mundo] ou `site1`+`site2`. 2 connects no par = hinge; ≥3 não colineares ≈ weld |
| `weld` | 6 | pose relativa: `relpose`, `torquescale` (0 ⇒ connect) ou `site1`+`site2`; mocap + weld |
| `joint` | 1 | `y−y₀ = a₀+a₁(x−x₀)+…+a₄(x−x₀)⁴`, `polycoef` (padrão `0 1 0 0 0`); só hinge/slide; sem `joint2` fixa `joint1`: engrenagens |
| `tendon` | 1 | idem para comprimentos de tendão |
| `flex` · `flexvert` · `flexstrain` | 1/aresta · 2/vértice (dim 2) · 26 (trilinear) ou 162 (quadrático)/elemento (dim 3) | deformáveis ✔ `plate`/`poncho`/`strain.xml` compilam |

Todos têm `active`, `solref`, `solimp`; em runtime `d.eq_active[i]` (inicial `m.eq_active0`) ✔. **Δ doc**: `computation/index.rst` diz «cinco tipos» (inclui `distance` e omite `flex*`); `mjtEq` tem 8 membros e `mjEQ_DISTANCE` foi removido na 2.2.2. A doc desaconselha juntas comuns por equality (mais lento/impreciso que a árvore): use para laços e juntas macias.
```python
import mujoco, numpy as np
def run(xml, T=4.0, **ctrl):
    m = mujoco.MjModel.from_xml_string(xml); d = mujoco.MjData(m); d.ctrl[:] = list(ctrl.values())
    for _ in range(int(T / m.opt.timestep)): mujoco.mj_step(m, d)
    return m, d
# engrenagem: equality joint  j2 − j2₀ = −2·(j1 − j1₀)
GEAR = """<mujoco><option gravity="0 0 0"/><worldbody>
  <body><joint name="j1" axis="0 1 0" damping=".1"/><geom size=".05"/></body>
  <body pos="1 0 0"><joint name="j2" axis="0 1 0" damping=".1"/><geom size=".05"/></body></worldbody>
  <equality><joint joint1="j2" joint2="j1" polycoef="0 -2 0 0 0"/></equality><actuator><motor joint="j1"/></actuator></mujoco>"""
m, d = run(GEAR, T=1.0, u=1.0); print((d.qpos[1] / d.qpos[0]).round(3))            # -1.985 (≈ −2; restrição macia cede sob carga)
m = mujoco.MjModel.from_xml_string(GEAR); d = mujoco.MjData(m); d.eq_active[0] = 0; d.ctrl[0] = 1.0   # desliga em runtime
for _ in range(500): mujoco.mj_step(m, d)
print(d.qpos[1])                                                                   # 0.0 → j2 solta
# 4 barras (paralelogramo manivela–acoplador–balanço) fechado por connect; geoms sem colisão (contato espúrio nas pontas)
FOUR = """<mujoco><option gravity="{g}"/><default><geom type="capsule" size=".02" contype="0" conaffinity="0"/>
  <joint axis="0 1 0" damping=".5"/></default><worldbody>
  <body><joint name="a"/><geom fromto="0 0 0 0 0 .5"/>
    <body name="acoplador" pos="0 0 .5"><joint name="b"/><geom fromto="0 0 0 1 0 0"/><site name="c1" pos="1 0 0"/></body></body>
  <body name="balanco" pos="1 0 0"><joint name="c"/><geom fromto="0 0 0 0 0 .5"/><site name="c2" pos="0 0 .5"/></body></worldbody>
  <equality><connect body1="acoplador" body2="balanco" anchor="1 0 0" {soft}/></equality>
  <actuator><position joint="a" kp="200" kv="20"/></actuator></mujoco>"""
for g, soft in (("0 0 0", ""), ("0 0 -9.81", ""), ("0 0 -9.81", 'solref=".005 1" solimp=".95 .99 .001"')):
    m, d = run(FOUR.format(g=g, soft=soft), u=0.5); print(d.qpos.round(3), f"{np.linalg.norm(d.site_xpos[0] - d.site_xpos[1]):.1e}")
    # [ 0.5 -0.5  0.5] 2.8e-12 | [ 0.524 -0.524  0.524] 2.7e-04 | [ 0.524 -0.524  0.524] 8.9e-06   ← distância c1–c2 (folga do laço)
```

## 10. Mocap e keyframes
- **Mocap**: `<body mocap="true">` só como filho direto do mundo, sem juntas; a pose vem de `d.mocap_pos` (nmocap×3) e `d.mocap_quat` (nmocap×4, `[w x y z]`), padrão = pose do XML; `body_mocapid` = −1 nos demais (✔ mocap aninhado = erro). Para a dinâmica é **fixo**: o contato com ele não vê velocidade relativa (força fraca, pode instabilizar). Receita estável: corpo dinâmico + `weld` ao mocap, com `solref`/`solimp` equilibrando weld × contato. Mocap não gera contato com geometria estática nem entre mocaps. Template `arm`: o alvo é um mocap só visual.
- **Keyframes** `<key name time qpos qvel act ctrl mpos mquat>`: tamanhos `nq`, **`nv`**, `na`, `nu`, `3·nmocap`, `4·nmocap`. **Δ doc**: `XMLreference` diz `qvel` = `nq`; vale **nv** ✔ (`invalid qvel size, expected 7, got 8`). Vetores curtos são completados (qpos0 / 0); longos = erro. `mj_resetDataKeyframe(m, d, i)` copia `time qpos qvel act ctrl mocap_pos mocap_quat`; dados em `m.key_qpos` `(nkey, nq)`, `key_qvel` `(nkey, nv)`, `key_ctrl`, `key_mpos`, `key_mquat`. Não participam da física.
- `<custom>` guarda dados do usuário no modelo: `<numeric name data>` → `m.numeric('ganhos').data` ✔, `<tuple>` → `m.tuple('par').objtype/objid/objprm` ✔; `<text>` **não tem** acessor nomeado em Python 3.15 ✔ (use `m.text_data/text_adr/text_size`).
```python
import mujoco, numpy as np
np.set_printoptions(precision=4, suppress=True)
XML = """<mujoco><option timestep=".002"/><worldbody>
  <body name="alvo" mocap="true" pos="0 0 1"><geom type="sphere" size=".03" contype="0" conaffinity="0"/></body>
  <body name="mao" pos="0 0 1"><freejoint/><geom type="box" size=".05 .05 .05" mass="1"/>
    <body pos=".3 0 0"><joint name="h" axis="0 1 0"/><geom size=".05" mass=".1"/></body></body></worldbody>
  <equality><weld body1="alvo" body2="mao" solref=".02 1"/></equality><actuator><motor joint="h"/></actuator>
  <keyframe><key name="k1" time="2" qpos="0 0 2  1 0 0 0  .5" qvel="1 0 0  0 0 0  .1" ctrl=".3" mpos="3 3 3"/></keyframe></mujoco>"""
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m)
print(m.body_mocapid, m.nmocap, d.mocap_pos, d.mocap_quat)       # [-1  0 -1 -1] 1 [[0. 0. 1.]] [[1. 0. 0. 0.]]   (quat w x y z)
i = m.body("alvo").mocapid[0]                                    # acesso por nome → índice do mocap
d.mocap_pos[i] = [0.5, -0.2, 1.3]; d.mocap_quat[i] = [np.cos(0.2), 0, 0, np.sin(0.2)]    # 0,4 rad em z
for _ in range(1500): mujoco.mj_step(m, d)                       # 3 s com gravidade: o corpo livre segue o alvo pelo weld
print(f"{np.linalg.norm(d.body('mao').xpos - d.mocap_pos[i]):.1e}")   # 2.1e-04 m
print(m.nq, m.nv, m.key_qpos.shape, m.key_qvel.shape)            # 8 7 (1, 8) (1, 7)   ← qvel tem nv (não nq) valores
mujoco.mj_resetDataKeyframe(m, d, 0)                             # copia time/qpos/qvel/act/ctrl/mocap_pos/mocap_quat
print(d.time, d.qpos, d.qvel, d.ctrl, d.mocap_pos)               # 2.0 [0 0 2 1 0 0 0 .5] [1 0 0 0 0 0 .1] [.3] [[3 3 3]]
m.key_qpos[0] = d.qpos; m.key_time[0] = d.time                   # gravar o estado atual no keyframe (runtime)
try: mujoco.MjModel.from_xml_string(XML.replace('qvel="1 0 0  0 0 0  .1"', 'qvel="1 0 0 0 0 0 0 0"'))
except ValueError as e: print(e.args[0].splitlines()[0])         # Error: keyframe 'k1': invalid qvel size, expected 7, got 8
```

## Aprofundar
`python3 .agents/mujoco-agent-skill/scripts/docs_search.py --elem actuator/pid` (idem `--elem sensor/contact`, `--attr tendon/spatial.springlength`, `--type mjtSensor`); `docs/upstream/mujoco/doc/XMLreference.rst` (§ actuator, sensor, tendon, equality, keyframe), `modeling.rst` (§ Actuators, Sensors, Delays, MoCap bodies), `computation/index.rst` (§ Actuation model, Equality), `dcmotor/dcmotor.tex` (mapeamento de datasheet).
Templates: `arm` (position + `inheritrange` + mocap), `car` (motor + position), `quadrotor` (motor em site + IMU). `render_video.py modelo.xml --keyframe nome --ctrl "atuador=valor"` renderiza a partir de um keyframe (o `--ctrl` já usa `Ctrl` seguro).

## Correções ao relatório do usuário (§2.5: tendões/atuadores/FLV)
- **Correção ao relatório do usuário — PARCIAL.** Afirmação: «`<tendon>` e `<actuator>` modelam a anatomia biomecânica de músculos através de leis FLV e atuadores elétricos mapeados a transmissões de juntas».
  - Só o atalho `<muscle>` implementa FLV: `F = −F0·[FL(L)·FV(V)·act + FP(L)]`, `F0 = scale/actuator_acc0`, ativação 0,01/0,04 s (Millard 2013); modelo simplificado (tendão inelástico, sem ângulo de penação). ✔ `arm26.xml` (ctrl=1, 0,5 s): `actuator_force = mju_muscleGain·act + mju_muscleBias = −35,9087`; `mju_muscleDynamics(1, .5)` = 40,0.
  - `<actuator>` é só o contêiner (11 atalhos + `general`) e `motor` é fonte ideal (sem dinâmica elétrica): R, K, back-EMF, indutância, térmica, saturação e atrito LuGre só no `dcmotor` (3.7+).
  - `<tendon>` **não** tem lei muscular: `fixed` = combinação linear de juntas escalares; `spatial` = caminho mínimo por sites, com wrapping só em esfera/cilindro e polias. A transmissão não é só «de juntas»: 7 tipos (§4).
- **Correção ao relatório do usuário — CORRETA (com ressalvas).** `<motor name="atuador_principal" joint="junta_motor" gear="1.0"/>` num hinge, controlado por `data.ctrl`: ✔ executei o XML exato do relatório (compila, `nu=1`, `qfrc_actuator = ctrl`). `gear="1.0"` é redundante (padrão `1 0 0 0 0 0`); sem `ctrlrange` o ctrl é ilimitado (o relatório injeta 15·sin(2πt) N·m); `dados.ctrl[id_motor]` só equivale a `ctrladr` enquanto todos os atuadores têm 1 controle (§5); `mj_name2id` devolve −1 para nome inexistente e `ctrl[-1] = v` escreve no ÚLTIMO atuador sem erro ✔ (`model.actuator('nome')` dá `KeyError` com os nomes válidos).

## Armadilhas
| Sintoma | Causa | Correção |
|---|---|---|
| `data.actuator('x').ctrl=v` não move o atuador (ou move outro); `m.actuator('x').ctrlrange/.gear` ou `.force` com valor alheio | acessor nomeado indexa por ID; `ctrl`/`ctrlrange` são por controle (`nu`), `actuator_force/length/gear` por saída (`nout`) ✔ | `slots()` (§5) ou `mjkit.Ctrl` |
| servo `general` não segue o alvo (dedos 0,0413 m com ctrl=128; esperado 0,0201) | `biasprm` é ignorado com `biastype="none"` (padrão) ✔ | `biastype="affine"` |
| `kv` alto: `WARNING: Nan, Inf or huge value in QACC`, qpos explode | `kv` é explícito no Euler: estável só se `kv·Δt/J < 2` ✔ | `implicitfast`/`implicit`; `damping`; `dampratio` |
| servo vai a ±90 rad / ignora limite | `ctrlrange`/`actrange` em unidades nativas, sem conversão de graus ✔ | escreva em rad ou use `inheritrange` |
| `pid` com `ki` + `slewmax`: `actdim > 1 is only allowed…` | **Δ doc**: restrição de 3.15.0 (XML e MjSpec) ✔ | use um só; MjSpec por palavra-chave |
| `pid` não zera o erro estacionário | `imax` pequeno satura a integral (`ki·imax`) ✔; `ki` exige a entrada `pos` | `imax` maior ou `0` (sem limite) |
| `invalid control range for actuator` · `Lengthrange computation did not converge` · `kv and dampratio cannot both be defined` · `ctrlrange and inheritrange cannot both be defined` | `damper`/`adhesion` exigem `ctrlrange` ≥ 0; `muscle` sem limites de junta/tendão nem `lengthrange`; atributos exclusivos ✔ | dê `ctrlrange="0 1"`, `range` na junta ou `lengthrange`; escolha um dos exclusivos |
| `<general>` herdou ganho/bias de servo | atalho no `<default>` preenche todo `general` sem esses atributos ✔ | mesmo atalho no default e no atuador, ou classes separadas |
| `orientation`: `lower bound must be 0` / `requires a ball joint` | `forcerange` limita a norma; só ball joint ou site+`refsite` ✔ | `forcerange="0 τmax"`; hinge → use `position` |
| sensor com `noise` não tem ruído | removido na 3.1.4 (só guarda σ) ✔ | `rng.normal(0, σ)` por conta própria |
| leitura de sensor 1 passo atrasada · `interval` sem efeito | `sensordata` sai do `mj_forward` no início do passo; `interval` exige `nsample ≥ 1` ✔ | `mj_forward` antes de ler; `nsample=1` com `interval` |
| laço fechado vaza ≈ 2e-2 m com 1 contato espúrio (ncon=1) ✔ | geoms colidindo nas pontas do laço; `solref` padrão é macio | `contype="0"`/`<exclude>`; `solref=".005 1"` + `solimp=".95 .99 .001"` ✔ (2,7e-4 → 8,9e-6 m) |
| `invalid qvel size, expected nv` no keyframe | `qvel` tem **nv** valores (**Δ doc**: XMLreference diz `nq`) ✔ | passe `nv` valores |
| mocap «not a fixed child of world» / empurra fraco | só filho direto do mundo; fixo para a dinâmica ✔ | `weld` a um corpo dinâmico |
| modelo não vai para MJX-JAX | `mjx.rst` § Feature Parity (não testado: MJX/Warp ausentes): JAX só aceita gain fixed/affine/muscle, bias none/affine/muscle, dyn none/integrator/filter/filterexact/muscle, trn joint/jointinparent/site/tendon, equality connect/weld/joint/tendon; Warp: «All» | evite `pid`/`dcmotor`/`orientation`/`adhesion`/`slidercrank`/`flex*` em JAX; ver `references/gpu-mjx-warp.md` |
