# Drones (quadricópteros): fluido, receita mínima, controle, Menagerie e limites

Modelar, controlar e validar quadricópteros no MuJoCo 3.15: modelo de fluido (ar/vento), `motor` em `site`, alocação, PD e controle geométrico, Skydio X2/Crazyflie 2 e o que o motor NÃO simula.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: ficha `pesquisas/conhecimento/Q8.md` («Q8»); `docs/upstream/mujoco/doc/computation/fluid.rst`; `docs/upstream/mujoco/doc/XMLreference.rst` (`option-wind` l.357, `option-density` l.372, `option-viscosity` l.380, `body-geom-fluidshape` l.2940, `actuator-general-dyntype` l.5755); `docs/upstream/mujoco_menagerie/{skydio_x2,bitcraze_crazyflie_2}/`; template `assets/templates/quadrotor/{model.xml,run.py}`; testes próprios (`✔ testado`).

## Quando ler este arquivo
- Vai criar/ajustar um drone (MJCF do zero, template `quadrotor`, Menagerie) ou ligar ar/vento em qualquer corpo.
- O drone cai, gira, planeia, «não sente o vento» ou o `fluidcoef` «não faz nada»: veja `## Armadilhas`.
- Antes de prometer realismo: o que o MuJoCo simula (arrasto do corpo) e o que não simula (efeito de solo, aerodinâmica de rotor, ESC/bateria).
- Ver também: `references/actuators-sensors.md` (`general`, `dcmotor`, IMU), `references/physics-tuning.md` (integradores), `references/robots.md` (Menagerie); o MJPC tem a tarefa «Quadrotor» (`docs/upstream/mujoco_mpc/docs/OVERVIEW.md:256`; o `task.xml` não está no espelho).

## 1. Modelo de fluido
Dois modelos fenomenológicos SEM ESTADO (sem esteira nem vórtices; `fluid.rst` §`flInertia` e §`flEllipsoid`), ligados por `density>0` e/ou `viscosity>0` (padrão 0 = vácuo: sem arrasto e o `wind` não faz nada). A doc recomenda `implicit`/`implicitfast` (derivadas analíticas dos dois modelos); em ar de drone Euler, `implicitfast` e RK4 deram o mesmo voo (Q8). A força de fluido fica em `data.qfrc_fluid` (parte de `qfrc_passive`).

| | Caixa de inércia (padrão) | Elipsoide (`fluidshape="ellipsoid"`) |
|---|---|---|
| Vale quando | nenhum geom do corpo marcado | ≥ 1 geom do corpo marcado (padrão `none`) |
| Forma usada | caixa equivalente do CORPO: meias-dimensões de `body_mass`/`body_inertia`, eixos principais `body_iquat`; os geoms só contam via massa/inércia | elipsoide equivalente de CADA geom marcado (`size`: semi-eixos; esfera = r) |
| Termos | arrasto quadrático por eixo (D) + Stokes da esfera equivalente (V) | massa adicionada (A) + arrasto (D) + Kutta (K) + Magnus (M) + Stokes (V) |
| Ajuste | nenhum (muda ao mudar massa/inércia) | `fluidcoef`, 5 números por geom |

**Regra de seleção, POR CORPO** (✔ testado, bloco do §1):
- Nenhum geom do corpo marcado → vale a caixa de inércia do corpo todo. Basta UM geom marcado → a caixa é DESLIGADA para esse corpo, só contam os geoms marcados e os não marcados do mesmo corpo dão força ZERO. Outros corpos do modelo mantêm a sua regra.
- `fluidcoef` só age em geom marcado (nos demais `model.geom_fluid` é todo zero; layout `(ngeom, 12)` = [flag, 5 coefs, 3 massa virtual/ρ, 3 inércia virtual/ρ]). `<visual><global ellipsoidinertia="true"/>` (scene.xml do Menagerie) só muda o DESENHO da inércia.
- Decisão rápida: hover/voo lento → a caixa de inércia basta; arrasto sob controle → some um geom elipsoide SEM massa (`mass="0"`) com `fluidshape="ellipsoid"`, `size` = semi-eixos do envelope e `fluidcoef` próprio (✔ teste à parte: `size=".17 .17 .05"`, 4 m/s → 0.5757 N = fórmula da doc); asa/pá → elipsoide por geom com calibração própria (§5). O changelog 2.1.2 (`docs/upstream/mujoco/doc/changelog.rst` l.3515) diz que a caixa de inércia «is very rarely a good approximation».

| Atributo | Padrão | Unidade | O que faz | Ar |
|---|---|---|---|---|
| `option/density` | 0 | kg/m³ | liga os termos QUADRÁTICOS (D, K, M, A) | 1.225 (Menagerie; `docs/upstream/mujoco/model/cards/cards.xml`) |
| `option/viscosity` | 0 | Pa·s (dinâmica) | liga o termo linear (Stokes); NÃO é escalada por `fluidcoef` | 1.8e-5 (água 8.9e-4) |
| `option/wind` | `0 0 0` | m/s, mundo | subtraído SÓ da velocidade translacional; uniforme; reescreva a cada passo p/ rajadas | — |
| `geom/fluidcoef` | `0.5 0.25 1.5 1.0 1.0` | adim. | [C_blunt, C_slender, C_angular, C_Kutta, C_Magnus] | — |

`Δ doc`: `fluid.rst` chama β de viscosidade «kinematic» (1.48e-5 m²/s), mas a força medida é 6π·μ·r·v com μ = `opt.viscosity` em Pa·s (✔ bloco do §1; a XMLreference: ar «around 0.00002», água «around 0.0009»). `fluid.rst` também liga os modelos com `density` e `viscosity` positivas, mas na prática cada uma liga a sua parcela (✔ só μ → só Stokes).

**Equações** (`v`, `ω` no referencial do corpo/geom, `v` relativa ao vento; reproduzidas pelo motor: erro 2e-15 na caixa, ≤ 6e-7 no elipsoide, Q8):
- Caixa: `r_x = √(3/(2M)·(I_yy+I_zz−I_xx))` (cíclico) · `f_D,i = −2ρ·r_j·r_k·|v_i|·v_i` (≡ Cd = 1 sobre a face 4·r_j·r_k) · `g_D,i = −½ρ·r_i·(r_j⁴+r_k⁴)·|ω_i|·ω_i` · `f_V = −6π·μ·r_eq·v` · `g_V = −8π·μ·r_eq³·ω` · `r_eq = (r_x+r_y+r_z)/3`.
- Elipsoide: `f = f_A+f_D+f_M+f_K+f_V`, `g = g_A+g_D+g_V` · `f_D = −ρ[C_blunt·A_proj + C_slender(A_max−A_proj)]·‖v‖·v` (`A_max = π·r_max·r_mid`) · `g_D = −ρ·‖ω∘[C_ang·I_D + C_slender(I_max−I_D)]‖·ω` · `f_M = C_M·ρ·V·ω×v` · `f_K = C_K·ρ·A_proj·(v̂·n̂)(n̂×v)×v` · Stokes com `r_D = (r_x+r_y+r_z)/3`. `C_blunt = 0.5` ⇔ Cd clássico 1.0 (a fórmula é `ρ·C·A·v²`, sem o ½).

| Termo | Escala | Para um drone |
|---|---|---|
| D arrasto quadrático | ρ·v² | domina em ar; freia o drone e inclina o hover no vento |
| V Stokes | μ·v | ≈ 1e-3 do quadrático a 3 m/s (✔ bloco do §1); só importa a Re baixo |
| A massa adicionada | ρ·V | só termos giroscópicos, SEM inércia extra (✔ teste à parte: em repouso a ρ = 1000, `qfrc_fluid` = 0 e `qacc_z` = −9.81) |
| K Kutta / M Magnus | C_K·ρ·A_proj / C_M·ρ·V·ω | sustentação de placa (∝ sin 2α; zero em esfera) / força lateral de corpo que gira e translada |

```python
import mujoco, numpy as np
def fluido(*corpos, rho=1.225, mu=1.8e-5, wind="0 0 0"):          # um corpo livre por argumento (XML dos geoms)
    bodies = "".join(f"<body pos='{3*i} 0 0'><freejoint/>{g}</body>" for i, g in enumerate(corpos))
    m = mujoco.MjModel.from_xml_string(f'<mujoco><option density="{rho}" viscosity="{mu}" wind="{wind}"/><worldbody>{bodies}</worldbody></mujoco>')
    d = mujoco.MjData(m); d.qvel[:] = np.tile([3, 1, 0, 0, 0, 2], len(corpos)); mujoco.mj_forward(m, d)   # v (mundo, m/s), ω (corpo, rad/s)
    return m, d.qfrc_fluid.reshape(-1, 6).copy()                 # [força N | torque N·m] no CoM, 1 linha por corpo
esf = '<geom type="sphere" size="0.1" mass="0.5" fluidshape="ellipsoid"/>'; cx = '<geom type="box" size="0.3 0.2 0.05" mass="1"/>'
m, f = fluido(esf, cx)
print(m.geom_fluid[0, :6], m.geom_fluid[1].any())                # [1. .5 .25 1.5 1. 1.] False (caixa sem marca)
print("cada corpo com a sua regra:", np.allclose(f[0], fluido(esf)[1][0]), np.allclose(f[1], fluido(cx)[1][0]))
print("corpo misto (esfera marcada + caixa) == só a esfera:", np.allclose(fluido(esf + cx)[1][0], f[0]))
print("rho=mu=0 + vento:", fluido(cx, rho=0, mu=0, wind="5 0 0")[1][0, :3], "| só μ: %.1e N | só ρ: %.4f N" % (fluido(cx, rho=0)[1][0, 0], fluido(cx, mu=0)[1][0, 0]))
print("Stokes %.4e N = 6πμr‖v‖ %.4e N" % (np.linalg.norm(fluido(esf, rho=0)[1][0, :3]), 6 * np.pi * 1.8e-5 * 0.1 * np.hypot(3, 1)))
```

## 2. Receita mínima de quadricóptero
Os blocos `python` dos §2–§6 são CUMULATIVOS (um único `quad_min.py`; rode com `cwd` fora da raiz); o bloco do §1 é independente.
- Corpo livre com `<inertial>` explícito (evita massa dobrada de geoms visuais), 4 `<site>` nos rotores e `<motor site=… gear="0 0 1 0 0 g">`: força ao longo de +z do site; o momento r×F (roll/pitch) surge sozinho do braço; `g` é o torque reativo de guinada por N de empuxo (a doc: «can be used to model jets and propellers»).
- Sinais de `g` ALTERNADOS em torno do quadro (rotores adjacentes giram em sentidos opostos): (−,−) −k, (−,+) +k, (+,+) −k, (+,−) +k; k ≈ 0.02 m (X2: 0.0201). `ctrl` = empuxo em N, saturado em `ctrlrange` sem aviso (Q8). Hover = `A⁻¹·[m·g,0,0,0]` (= m·g/4 = 2.4525 N por rotor aqui, só se o CoM for simétrico).
- A matriz de alocação sai do modelo (`actuator_gear`, `site_xpos − xipos`), sem sinais à mão; testada no X2 e no CF2 (bloco §4).
```python
import mujoco, numpy as np                                      # quad_min.py — parte 1
XML = """<mujoco model="quad_min">
  <compiler autolimits="true"/><option timestep="0.002" integrator="implicitfast" density="1.225" viscosity="1.8e-5"/>
  <worldbody>
    <body name="quad" pos="0 0 1"><freejoint/>
      <inertial pos="0 0 0" mass="1.0" diaginertia="0.01 0.01 0.018"/>
      <geom type="box" size="0.21 0.01 0.01" euler="0 0 45" contype="0" conaffinity="0"/><geom type="box" size="0.21 0.01 0.01" euler="0 0 -45" contype="0" conaffinity="0"/>
      <site name="s1" pos="-0.15 -0.15 0"/><site name="s2" pos="-0.15 0.15 0"/><site name="s3" pos="0.15 0.15 0"/><site name="s4" pos="0.15 -0.15 0"/>
    </body>
  </worldbody>
  <actuator>
    <motor name="f1" site="s1" gear="0 0 1 0 0 -0.02" ctrlrange="0 8"/><motor name="f2" site="s2" gear="0 0 1 0 0 0.02" ctrlrange="0 8"/>
    <motor name="f3" site="s3" gear="0 0 1 0 0 -0.02" ctrlrange="0 8"/><motor name="f4" site="s4" gear="0 0 1 0 0 0.02" ctrlrange="0 8"/>
  </actuator>
</mujoco>"""
def alocacao(m, d, corpo):
    """A (6×nu): força e torque no CoM, no referencial do CORPO, por unidade de ctrl (linhas Fx Fy Fz τx τy τz)."""
    mujoco.mj_forward(m, d); b = m.body(corpo).id; R = d.xmat[b].reshape(3, 3); A = np.zeros((6, m.nu))
    for i in range(m.nu):
        s = m.actuator_trnid[i, 0]; Rs = d.site_xmat[s].reshape(3, 3); g = m.actuator_gear[i]; F, T = Rs @ g[:3], Rs @ g[3:]
        A[:3, i] = R.T @ F; A[3:, i] = R.T @ (np.cross(d.site_xpos[s] - d.xipos[b], F) + T)
    return A
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m); A = alocacao(m, d, "quad"); A4 = A[2:]    # [Fz, τx, τy, τz] = A4 @ u
print(A4.round(3)); print("sem força lateral:", abs(A[:2]).max() < 1e-12)
M = m.body_mass[1]; g = -m.opt.gravity[2]; u_hover = np.linalg.solve(A4, [M * g, 0, 0, 0])
d.ctrl[:] = u_hover; mujoco.mj_forward(m, d); print("hover u =", u_hover.round(4), "| |qacc| = %.1e" % abs(d.qacc).max())
d.ctrl[:] = [2.2, 2.7, 2.2, 2.7]; mujoco.mj_forward(m, d)       # +Δ nos rotores 2 e 4 → guinada
print("guinada: qacc[5] = %.4f rad/s² | k·Δ/Izz = %.4f" % (d.qacc[5], 0.02 * (2.7 + 2.7 - 2.2 - 2.2) / 0.018))
I = m.body_inertia[1]; r = np.sqrt(1.5 / M * np.array([I[1]+I[2]-I[0], I[2]+I[0]-I[1], I[0]+I[1]-I[2]]))   # caixa de inércia = origem do arrasto
m.opt.wind[0] = 4.0; mujoco.mj_forward(m, d); m.opt.wind[0] = 0.0
print("caixa r =", r.round(4), "| arrasto a 4 m/s: %.5f N | 2ρ·r_y·r_z·v² + Stokes = %.5f N" % (d.qfrc_fluid[0], 2 * 1.225 * r[1] * r[2] * 16 + 6 * np.pi * 1.8e-5 * r.mean() * 4))
```
✔ testado: Δ de empuxo → guinada 1.111 rad/s² (Q8: roll/pitch 15 rad/s² com Δ = 0.5 N em dois rotores). Sem realimentação a atitude não se corrige: 1° inicial → 1.000° após 3 s, deriva 0.767 m (Q8). `⚠ armadilha`: o arrasto vem da caixa de `body_mass`/`body_inertia` (r = 0.164 × 0.164 × 0.055 m aqui): mudar a inércia muda o arrasto.
Checklist de validação de um drone novo: (1) hover com `A⁻¹·[m·g,0,0,0]` dá `|qacc| ≈ 0`; (2) Δ de empuxo dá os sinais certos de roll/pitch/guinada; (3) arrasto previsto `2ρ·r_y·r_z·v²` confere; (4) queda livre sem planeio lateral (§4); (5) malha fechada sem sobressinal em altitude e com < 5 % de passos saturados (checagem do `run.py`).

## 3. Controle
### 3.1 PD em cascata (altitude + xy + atitude)
| Laço | Lei | Ganhos | Medido (✔ bloco abaixo, igual à Q8; t_s = banda de 2 % do degrau) |
|---|---|---|---|
| Altitude | `T = m(g + kp·e_z − kd·v_z)/cosθ` (peso em feedforward) | kp 16, kd 8 (polos −4, −4) | degrau 1→2 m: t_s 1.480 s, sobressinal 0, erro final 3e-14 m |
| Posição xy | `a = kp·e − kd·v` → `θ_d = a_x/g`, `φ_d = −a_y/g` (guinada 0), saturados em ±25° | kp 3, kd 3 | vento 4 m/s: offset 0.1175 m, arfagem −2.06° (arrasto 0.353 N); PID (ki 1) zera o offset (Q8) |
| Atitude | `τ = I(kp·e_R − kd·ω) + ω×Iω`, `e_R = mju_subQuat(q_des, q)` (vetor no corpo) | kp 400, kd 40 (ωn 20, ζ 1); guinada 40/12 | roll 10°/20°: t_s 0.298 s (`kxy=(0,0)`), sem perder altura |
| Alocação | `u = A⁻¹·[T, τx, τy, τz]`, clip em `ctrlrange` | — | — |

Massa estimada 10 % baixa: o PD deixa +0.0681 m de erro (✔ bloco); PID de altitude (ki 10) zera, com sobressinal 10.2 % e t_s 3.76 s (Q8). Guinada 45°: 40/12 satura os rotores (0 e 8 N) e custa 4.7 cm de altitude; 10/6 não satura (t_s 1.67 s): limite ganho/taxa de guinada (Q8). Com o laço xy ligado o roll leva 0.94 s a assentar em ±0.2° (o laço de posição também pede inclinação; ✔); `kxy=(0,0)` isola a atitude, mas o drone desliza 1 m em 6 s.
```python
def controlador(m, d, corpo="quad", kz=(16, 8), kxy=(3, 3), ka=(400, 40), ky=(40, 12), tilt=25.0, mass_err=1.0):   # quad_min.py — parte 2
    b = m.body(corpo).id; M = m.body_mass[b] * mass_err; g = -m.opt.gravity[2]; lo, hi = m.actuator_ctrlrange.T
    R0 = np.zeros(9); mujoco.mju_quat2Mat(R0, m.body_iquat[b]); R0 = R0.reshape(3, 3); I = R0 @ np.diag(m.body_inertia[b]) @ R0.T   # inércia no corpo
    Ainv = np.linalg.inv(alocacao(m, d, corpo)[2:]); kp, kd = np.array([ka[0], ka[0], ky[0]]), np.array([ka[1], ka[1], ky[1]])
    def passo(d, p_ref, yaw=0.0):
        p, v, q, w = d.qpos[:3], d.qvel[:3], d.qpos[3:7], d.qvel[3:6]      # freejoint: v no MUNDO, ω no CORPO
        e = p_ref - p; ax, ay = kxy[0] * e[:2] - kxy[1] * v[:2]; c, s = np.cos(yaw), np.sin(yaw)
        th, ph = np.clip([(ax * c + ay * s) / g, (ax * s - ay * c) / g], -np.radians(tilt), np.radians(tilt))
        qd = np.zeros(4); mujoco.mju_euler2Quat(qd, [ph, th, yaw], "XYZ")  # R = Rz(yaw)·Ry(pitch)·Rx(roll)
        T = M * (g + kz[0] * e[2] - kz[1] * v[2]) / max(1 - 2 * (q[1]**2 + q[2]**2), 0.5)
        eR = np.zeros(3); mujoco.mju_subQuat(eR, qd, q)                    # q·quat(eR) = qd: rotação (no corpo) que leva q → qd
        return np.clip(Ainv @ [T, *(I @ (kp * eR - kd * w) + np.cross(w, I @ w))], lo, hi)
    return passo
def simular(m, d, ctl, T, ref=lambda t: (0, 0, 1), p0=(0, 0, 1), euler0=(0, 0, 0), vento=lambda t: (0, 0, 0), act0=None):
    mujoco.mj_resetData(m, d); d.qpos[:3] = p0; mujoco.mju_euler2Quat(d.qpos[3:7], euler0, "XYZ")   # ⚠ mj_resetData zera data.act
    if act0 is not None: d.act[:] = act0
    log = []
    for _ in range(round(T / m.opt.timestep)):
        m.opt.wind[:] = vento(d.time); d.ctrl[:] = ctl(d, np.array(ref(d.time), float)); mujoco.mj_step(m, d)
        R = np.zeros(9); mujoco.mju_quat2Mat(R, d.qpos[3:7]); log.append([d.time, *d.qpos[:3], np.degrees(np.arctan2(R[7], R[8])), np.degrees(-np.arcsin(R[6]))])
    return np.array(log).T                                                  # t, x, y, z, roll°, pitch°
def t_assent(t, y, y_final, banda, t0=0.0):
    fora = np.where((t >= t0) & (abs(y - y_final) > banda))[0]; return t[fora[-1] + 1] - t0 if fora.size else 0.0
t, x, y, z, roll, pitch = simular(m, d, controlador(m, d), 10, ref=lambda t: (0, 0, 2.0 if t >= 1 else 1.0))
print("altitude 1→2 m: t_s(2%%) = %.3f s | sobressinal %.2f %% | erro final %.1e m" % (t_assent(t, z, 2, 0.02, 1), max(0, z.max() - 2) * 100, abs(2 - z[-1])))
t, x, y, z, roll, pitch = simular(m, d, controlador(m, d, kxy=(0, 0)), 3, euler0=(np.radians(20), 0, 0))
print("roll 20° → 0: t_s(2%%) = %.3f s | queda de altura %.1e m" % (t_assent(t, roll, 0, 0.4), 1 - z.min()))
t, x, y, z, roll, pitch = simular(m, d, controlador(m, d), 40, vento=lambda t: (4, 0, 0))
print("vento 4 m/s (PD): offset x = %.4f m | arfagem = %.2f°" % (x[-1], pitch[-1]))
t, x, y, z, roll, pitch = simular(m, d, controlador(m, d, mass_err=0.9), 10, ref=lambda t: (0, 0, 2.0 if t >= 1 else 1.0))
print("massa estimada −10 %%: erro estacionário de altitude = %.4f m" % (2 - z[-1]))
```

### 3.2 Controlador geométrico do template (`assets/templates/quadrotor/run.py`)
Rodar: `.venv/bin/python .agents/mujoco-agent-skill/assets/templates/quadrotor/run.py --sem-video [--ar] [--vento 3] [--saida DIR]` (exit 0 = checagens OK; sem `--sem-video` grava também MP4/GIF, sempre `telemetria.png` e `resumo.json`; também `--altura --lado --vel --camera --view`; `--vento` implica `--ar`). ⚠ O `model.xml` do template começa em vácuo (`density="0"`). Classe `Quadricoptero(model, corpo="drone", wn_pos=3, zeta_pos=0.9, ki=1.2, wn_att=22, zeta_att=0.8, tilt_max_deg=35)`; `quad(data, p_ref, v_ref, a_ref, yaw)` → `u` (4,); `quad.reset()` zera a integral. Referência: min-jerk (`10s³−15s⁴+6s⁵`) por waypoints, com paradas. Experimento próprio: `python3 .agents/mujoco-agent-skill/scripts/new_experiment.py drone --template quadrotor` (copia `model.xml`/`run.py`/`README.md` para `experiments/NN_drone/`; `--dry-run` só mostra o plano ✔).

| Etapa | O que faz / ganhos |
|---|---|
| `a = −Kp·e_p − Kv·e_v − Ki·∫e_p + a_ref + g·ẑ` | PID de posição em aceleração: Kp = ωn² = 9, Kv = 2ζωn = 5.4 (ωn 3, ζ 0.9), Ki 1.2, integral limitada a ±1.5 |
| `F = m·a`; limite | `F_h ≤ tan(35°)·F_z` e `F_z ≥ 0.3·m·g`: não capota com erro grande |
| `b3d = F/‖F‖`, `Rd = [b2d×b3d, b2d, b3d]` | atitude desejada: eixo de empuxo ao longo de F, guinada por `b1c = (cosψ, sinψ, 0)` |
| `e_R = ½·vee(RdᵀR − RᵀRd)`, `T = F·b3` | erro em SO(3) (Lee et al.), sem Euler/singularidades; empuxo = F projetada no eixo atual |
| `τ = J(−ωn²·e_R − 2ζωn·ω) + ω×Jω` | PD de atitude com cancelamento giroscópico: ωn 22, ζ 0.8 (kp 484, kd 35.2) |
| `u = A⁻¹·[T, τ]`, clip `[0, umax]` | alocação do §2 (lê `actuator_gear`, `site_pos`); conta passos saturados |

✔ medido (`run.py --sem-video`, 0.892 kg, T/W 3.66): z > 95 % em 1.08 s; erro nos waypoints ≤ 0.3 cm; RMS 3.0 cm; inclinação máx 20.2°; 0 % de passos saturados; pousa em z = 0.056 m (pernas). Com `--vento 3`: 0.6 cm / RMS 2.9 cm / 20.5°; `--vento 6`: 2.3 cm / 3.1 cm / 21.5°; `--vento 8`: 4.0 cm / 3.7 cm / 22.5°.
```python
import importlib.util                                           # quad_min.py — parte 3: reusar o controlador do template
T = "/home/ondokai/Projects/MuJoCo/.agents/mujoco-agent-skill/assets/templates/quadrotor"
spec = importlib.util.spec_from_file_location("tpl", f"{T}/run.py"); tpl = importlib.util.module_from_spec(spec); spec.loader.exec_module(tpl)
mq = mujoco.MjModel.from_xml_path(f"{T}/model.xml"); dq = mujoco.MjData(mq); mq.opt.density, mq.opt.viscosity = 1.225, 1.81e-5; quad = tpl.Quadricoptero(mq)
def voo(ref, vento, T_fim):
    mujoco.mj_resetData(mq, dq); quad.reset(); dq.qpos[:3] = [0, 0, 1]; X = []
    for _ in range(round(T_fim / mq.opt.timestep)):
        mq.opt.wind[0] = vento(dq.time); dq.ctrl[:] = quad(dq, np.array(ref(dq.time), float), np.zeros(3), np.zeros(3)); mujoco.mj_step(mq, dq); X.append((dq.time, *dq.qpos[:3]))
    return np.array(X).T
t, x, y, z = voo(lambda t: (1.0, 0, 1) if t >= 1 else (0, 0, 1), lambda t: 0.0, 30)
print("degrau de 1 m em x (sem trajetória): sobressinal %.1f %% | t_s(5%%) = %.2f s" % (max(0, x.max() - 1) * 100, t_assent(t, x, 1, 0.05, 1)))
t, x, y, z = voo(lambda t: (0, 0, 1), lambda t: 6.0 if t >= 2 else 0.0, 30)
print("vento 0→6 m/s em t = 2 s: pico |x| = %.3f m | < 2 cm em %.2f s | x(30 s) = %.1e m" % (abs(x).max(), t_assent(t, x, 0, 0.02, 2), x[-1]))
```
✔ Degrau em REFERÊNCIA (sem trajetória): sobressinal 7.2 % e t_s(5 %) 5.31 s (polo lento do integrador, −0.146 s⁻¹; a inclinação chega a 34.2° do limite de 35°): use trajetória suave ou reduza `ki`. Vento 0→6 m/s: pico 2.5 cm, volta a < 2 cm em 3.42 s, offset final 5e-4 m.

### 3.3 Atraso de motor/ESC
`<motor>` é direct-drive (`dyntype none`): `actuator_force` muda no mesmo passo. Atraso de 1ª ordem: `<general site=… gear=… dyntype="filterexact" dynprm="τ" gaintype="fixed" gainprm="1" biastype="none"/>` (`act` = empuxo real; `ctrl` = comando). Via `MjSpec` basta trocar `dyntype`/`dynprm[0]` dos `<motor>` (✔). Literatura (Q8): α_subida 11 ms, α_descida 27 ms. `dcmotor` (resistência, back-EMF; multi-entrada: use `mjkit.Ctrl`): testado como motor de junta em `references/actuators-sensors.md`; como rotor (empuxo ∝ ω²) NÃO testado.
```python
def com_atraso(tau):                                            # quad_min.py — parte 4
    spec = mujoco.MjSpec.from_string(XML)
    for a in spec.actuators: a.dyntype, a.dynprm[0] = mujoco.mjtDyn.mjDYN_FILTEREXACT, tau      # motor = general (gain 1, sem bias) + dinâmica
    return spec.compile()
ml = com_atraso(0.03); dl = mujoco.MjData(ml); dl.act[:] = u_hover[0]; dl.ctrl[:] = u_hover[0] + 1.0; t63 = None      # degrau de +1 N
for _ in range(150):
    mujoco.mj_step(ml, dl); t63 = t63 or (dl.time if dl.actuator_force[0] >= u_hover[0] + 1 - np.exp(-1) else None)
print("na = %d | 63.2 %% do degrau em %.3f s (τ = 0.030 s + 1 passo)" % (ml.na, t63))
mujoco.mj_resetData(ml, dl); print("⚠ act após mj_resetData:", dl.act); dl.ctrl[:] = u_hover[0]; mujoco.mj_step(ml, dl)   # filtro recomeça do ZERO
print("empuxo no 1º passo = %.3f N (esperado %.4f): qacc_z = %.2f m/s²" % (dl.actuator_force[0], u_hover[0], dl.qacc[2]))
for tau in (0.0, 0.01, 0.03, 0.05):                             # malha fechada, mesmos ganhos (kp 400, kd 40)
    mt = m if tau == 0 else com_atraso(tau); dt_ = mujoco.MjData(mt)
    t, x, y, z, roll, pitch = simular(mt, dt_, controlador(mt, dt_, kxy=(0, 0)), 4, euler0=(np.radians(10), 0, 0), act0=None if tau == 0 else u_hover[0])
    print("τ = %.2f s: roll 10° → 0 em t_s(2%%) = %.3f s" % (tau, t_assent(t, roll, 0, 0.2)))
```
✔ τ 0 / 0.01 / 0.03 / 0.05 s → t_s 0.298 / 0.308 / 0.310 / 0.792 s (0.05 s oscila: pico de 0.655° depois de 0.5 s, Q8). ⚠ `mj_resetData` zera `act`: reinicialize `d.act[:] = hover` ou use `<key act="…">` + `mj_resetDataKeyframe` (✔ testado à parte: `act` e 1º empuxo corretos).

## 4. Menagerie: Skydio X2 e Crazyflie 2
| | Skydio X2 (`skydio_x2/x2.xml`) | Crazyflie 2 (`bitcraze_crazyflie_2/cf2.xml`) |
|---|---|---|
| Massa/inércia | 1.325 kg = 4 rotores elipsoide `.13 .13 .01` de 0.25 kg + elipsoide invisível 0.325 kg (demais geoms `mass=0`); inércia calculada dos geoms | 0.027 kg, `<inertial pos="0 0 0" mass="0.027" diaginertia="2.3951e-5 2.3951e-5 3.2347e-5">`, `inertiafromgeom="false"` |
| Atuadores | 4 `motor` `thrust1..4` em sites nos rotores, `gear="0 0 1 0 0 g"`, g = −.0201, +.0201, −.0201, +.0201; `ctrlrange="0 13"` N (T/W 4.0) | 4 `motor` num ÚNICO site `actuation` (CoM): `body_thrust` (`gear="0 0 1 0 0 0"`, 0–0.35 N, T/W 1.32) + `x_moment`, `y_moment`, `z_moment` (`gear` −1e-5, `ctrlrange="-1 1"`) |
| Integrador | Euler (padrão), `timestep="0.01"` | `RK4`, dt 0.002 (padrão) |
| Fluido | `density="1.225" viscosity="1.8e-5"`, sem `fluidshape` ⇒ caixa de inércia | idem |
| Keyframe `hover` | `qpos="0 0 .3 1 0 0 0"`, `ctrl` 3.2495625 ×4 (= m·g/4) | `qpos="0 0 0.1 1 0 0 0"`, `ctrl="0.26487 0 0 0"` (= m·g) |
| Sensores | `gyro`, `accelerometer` (+9.81 em z no hover), `framequat` no site `imu` | idem |

⚠ **X2 planeia em queda**: a inércia calculada tem I_xz = −0.0021 kg·m² (`body_iquat` ≠ identidade: eixos principais girados ≈ 5°), a caixa de inércia do fluido fica inclinada e o drone cai a 11.08 m/s a 32° da vertical (igual com dt 0.01/0.002 e Euler/implicitfast); com I_xz = 0 cai vertical a 8.88 m/s. Correção ✔: zerar I_xz (bloco) ou somar um elipsoide sem massa marcado (§1; ✔ teste à parte: vertical, ≈ 13.0 m/s com `size="0.2 0.2 0.05"`). Issue upstream: não verificado.
⚠ **CF2 não tem 4 rotores**: a alocação já é `[T, τx, τy, τz]` direta (`ctrl` dos momentos é adimensional: ±1 ⇒ ±1e-5 N·m). Autoridade de momento ínfima: α_máx 0.418 rad/s² (roll/pitch), 0.309 (guinada); o README do Menagerie diz que os `ctrlrange` são «arbitrary and need to be further tuned».
⚠ O espelho `docs/upstream/mujoco_menagerie` NÃO traz `assets/` (`Error opening file 'assets/X2_lowpoly.obj'`): `sem_malhas()` remove malhas/texturas e compila só a física.
```python
import xml.etree.ElementTree as ET                              # quad_min.py — parte 5
MEN = "/home/ondokai/Projects/MuJoCo/docs/upstream/mujoco_menagerie"
def sem_malhas(arquivo):
    raiz = ET.parse(arquivo).getroot()
    for pai in raiz.iter():
        for f in list(pai):
            if f.get("mesh") or f.tag in ("mesh", "texture") or (f.tag == "material" and f.get("texture")): pai.remove(f)
    return mujoco.MjModel.from_xml_string(ET.tostring(raiz, encoding="unicode"))
x2 = sem_malhas(f"{MEN}/skydio_x2/x2.xml"); b = x2.body("x2").id; R = np.zeros(9); mujoco.mju_quat2Mat(R, x2.body_iquat[b]); R = R.reshape(3, 3)
Ib = R @ np.diag(x2.body_inertia[b]) @ R.T                                  # tensor de inércia no referencial do corpo
print("X2: m = %.3f kg | dt = %g | %s | T/W = %.2f | hover/rotor = %.4f N | Ixz = %.4f" % (x2.body_mass[b], x2.opt.timestep, mujoco.mjtIntegrator(x2.opt.integrator).name, 4 * 13 / (x2.body_mass[b] * 9.81), x2.body_mass[b] * 9.81 / 4, Ib[0, 2]))
dx = mujoco.MjData(x2); t, x, y, z, roll, pitch = simular(x2, dx, controlador(x2, dx, "x2"), 10, ref=lambda t: (0, 0, 2.0 if t >= 1 else 1.0))     # §3.1 no X2 (dt 0.01)
print("X2, mesmo PD: degrau 1→2 m t_s(2%%) = %.3f s | sobressinal %.2f %%" % (t_assent(t, z, 2, 0.02, 1), max(0, z.max() - 2) * 100))
def queda(model, T=40.0):                                                   # queda livre sem empuxo, a 5 km (sem chão)
    dx = mujoco.MjData(model); dx.qpos[2] = 5000.0
    for _ in range(round(T / model.opt.timestep)): mujoco.mj_step(model, dx)
    return dx.qvel[:3].round(3), np.linalg.norm(dx.qvel[:3]).round(3)
print("X2 original, queda 40 s: v =", *queda(x2), "m/s (planeia)")
x2.body_iquat[b] = [1, 0, 0, 0]; x2.body_inertia[b] = np.diag(Ib); mujoco.mj_setConst(x2, mujoco.MjData(x2))       # correção: Ixz := 0
print("X2 com Ixz = 0, queda 40 s: v =", *queda(x2), "m/s (vertical)")
cf = sem_malhas(f"{MEN}/bitcraze_crazyflie_2/cf2.xml"); b = cf.body("cf2").id; dc = mujoco.MjData(cf)
print("CF2: m = %.3f kg | %s | atuadores %s | T/W máx = %.2f | α_máx roll/yaw = %.3f/%.3f rad/s²" % (cf.body_mass[b], mujoco.mjtIntegrator(cf.opt.integrator).name,
      [cf.actuator(i).name for i in range(cf.nu)], 0.35 / (cf.body_mass[b] * 9.81), 1e-5 / cf.body_inertia[b][0], 1e-5 / cf.body_inertia[b][2]))
for k in (1, 100):                                                          # gear dos momentos ×1 (como distribuído) e ×100
    ka = (9, 4.2) if k == 1 else (400, 40)
    t, x, y, z, roll, pitch = simular(cf, dc, controlador(cf, dc, "cf2", kz=(9, 4), kxy=(0, 0), ka=ka), 6, p0=(0, 0, 0.5), ref=lambda t: (0, 0, 0.5), euler0=(np.radians(10), 0, 0))
    print("CF2 gear×%d (kp_att %d): roll 10° → 0 em t_s(2%%) = %.2f s" % (k, ka[0], t_assent(t, roll, 0, 0.2))); cf.actuator_gear[1:, 3:] *= 100
```
X2 com o PD do §3.1: t_s 1.52 s, sem sobressinal (✔ bloco; Q8: 1.51 s). Q8 (mesmo tipo de controlador, estado exato): X2 recupera 20° em 0.33 s (rotores saturam em 0 e 13 N) e, com vento 4 m/s e PID, termina com x ≈ 0 e arfagem −1.78°; CF2 como distribuído (PD) sobe 0.5→0.8 m com t_s 2.0 s e sobressinal 5.7 %.

## 5. Limites: o que o MuJoCo NÃO modela
| Efeito | Evidência | O que fazer |
|---|---|---|
| Efeito de solo (+20–37 % de empuxo na literatura) | ✔ empuxo idêntico de z = 0.02 a 5 m (bloco) | `xfrc_applied` com ganho `g(z)` calibrado (bloco) |
| Inflow/vortex ring; empuxo vs velocidade do escoamento | ✔ idêntico com vz = −8 m/s e com ρ = 0 (bloco) | modele `ctrl → empuxo` por fora; limite a razão de descida |
| Arrasto de rotor (linear em v; erro principal em alta velocidade, Faessler 2018) | só há arrasto do corpo (caixa/elipsoide) | `xfrc_applied` com `−k·R·[v_x, v_y, 0]` (v no corpo; bloco) |
| Flapping, esteira do corpo, downwash entre drones | não existe | camada externa (MuJoCo-Drones-Gym, preprint 2026: modos `MJC GND/DRAG/DW`) |
| ESC/motor/bateria | ✔ `motor` responde no mesmo passo | `filterexact` (§3.3); tensão da bateria: sua camada |
| Vento turbulento/rajada | só `opt.wind` uniforme e constante | reescrever `opt.wind` a cada passo (bloco: Ornstein-Uhlenbeck) |
| Flutuação (empuxo hidrostático) | ✔ repouso a ρ = 1000: força de fluido 0 | `gravcomp > 1` (`docs/upstream/mujoco/model/balloons/balloons.xml`: 7.2 = ρ_ar/ρ_hélio; ✔ 1.5 ⇒ +0.5 g) |
| Asa fixa realista | ✔ placa elíptica: L/D ≤ 1 (bloco) | ajustar `fluidcoef` à mão ou aplicar polar CL(α)/CD(α) própria via `xfrc_applied` |
| Ruído de sensor, atraso de ciclo, estimador | controladores testados com estado exato (Q8 e aqui) | adicione na sua camada; malha com `gyro`/`accelerometer`: não verificado |
| GPU | MJX só tem a caixa de inércia (`fluidshape="ellipsoid"` é aceito e IGNORADO em silêncio no MJX-JAX: força diferente da do C/MJWarp) e levanta `NotImplementedError` com `implicitfast` + fluido (`docs/upstream/mujoco/mjx/mujoco/mjx/_src/derivative.py:67-69`); MJWarp tem os dois (`docs/upstream/mujoco_warp/mujoco_warp/_src/passive.py`) | leitura do código no espelho; NÃO executei em GPU (ver `pesquisas/conhecimento/Q11.md`) |

Não verificado (lacunas Q8): rotores como corpos girantes (empuxo ∝ ω², giroscópico), `dcmotor`, validação contra voo real (k = 0.0201, `ctrlrange` e `gear` vêm do fabricante ou são «arbitrários»).
```python
for z, vz, rho in ((0.02, 0, 1.225), (5.0, 0, 1.225), (1.0, -8, 1.225), (1.0, 0, 0.0)):       # quad_min.py — parte 6: empuxo = ctrl × gear
    m.opt.density = rho; mujoco.mj_resetData(m, d); d.qpos[:3] = [0, 0, z]; d.qvel[2] = vz; d.ctrl[:] = 2.8; mujoco.mj_forward(m, d)
    print("z=%.2f vz=%+d ρ=%.3f: empuxo/rotor = %.1f N" % (z, vz, rho, d.actuator_force[0]))
m.opt.density = 1.225
def aero_extra(m, d, corpo="quad", k_ge=0.25, z_ge=0.3, k_rotor=0.2):       # constantes ILUSTRATIVAS: calibre com dados da sua hélice
    b = m.body(corpo).id; R = d.xmat[b].reshape(3, 3)
    ge = k_ge * d.actuator_force.sum() * np.exp(-d.xipos[b, 2] / z_ge)       # +k_ge·T junto ao chão, decai com z_ge (m)
    v_ar = R.T @ (d.qvel[:3] - m.opt.wind)                                   # velocidade relativa ao ar, no corpo
    d.xfrc_applied[b, :3] = ge * R[:, 2] - k_rotor * R @ [v_ar[0], v_ar[1], 0]   # força no CoM (mundo): empuxo extra ao longo de b3 − arrasto de rotor
for z in (0.05, 0.3, 1.0):
    mujoco.mj_resetData(m, d); d.qpos[2] = z; d.ctrl[:] = u_hover; mujoco.mj_forward(m, d); a0 = d.qacc[2]; aero_extra(m, d); mujoco.mj_forward(m, d)
    print("z=%.2f hover: qacc_z sem extra = %.3f | com efeito de solo = %.3f m/s²" % (z, a0, d.qacc[2]))
d.xfrc_applied[:] = 0                                                        # xfrc_applied PERSISTE entre passos: reescreva ou zere
rng = np.random.default_rng(0); ou = np.zeros(3); a_ = np.exp(-m.opt.timestep / 1.0); s_ = 1.5 * np.sqrt(1 - a_ * a_)          # OU: τ = 1 s, σ = 1.5 m/s
def vento_ou(t):
    global ou; ou = a_ * ou + s_ * rng.normal(size=3); return np.array([3.0, 0, 0]) + ou
t, x, y, z, roll, pitch = simular(m, d, controlador(m, d), 60, vento=vento_ou); k = t > 10
print("turbulência OU (média 3 m/s), PD: RMS horizontal = %.3f m | RMS de altitude = %.4f m" % (np.sqrt(np.mean(x[k]**2 + y[k]**2)), np.sqrt(np.mean((z[k] - 1)**2))))
def polar(coef, V=10.0, rho=1.225, a=0.1, b=0.5):                            # asa fixa: placa elíptica corda 0.2, envergadura 1.0, espessura 0.02 m
    mp = mujoco.MjModel.from_xml_string(f'<mujoco><option gravity="0 0 0" density="{rho}"/><worldbody><body><freejoint/><geom type="ellipsoid" size="{a} {b} .01" mass="1" fluidshape="ellipsoid" fluidcoef="{coef}"/></body></worldbody></mujoco>')
    dp = mujoco.MjData(mp); q = 0.5 * rho * V**2 * np.pi * a * b
    for al in (0, 15, 45):
        t = np.radians(al); v = V * np.array([np.cos(t), 0, np.sin(t)]); dp.qvel[:3] = v; mujoco.mj_forward(mp, dp); f = dp.qfrc_fluid[:3]
        CL, CD = -f @ [-np.sin(t), 0, np.cos(t)] / q, -f @ (v / V) / q; print("fluidcoef=%s α=%2d°: CL=%.3f CD=%.3f L/D=%.2f" % (coef, al, CL, CD, CL / CD))
polar("0.5 0.25 1.5 1 1"); polar("0.5 0.01 1.5 1 1")
```
✔ Asa fixa (Q8): `fluidcoef` padrão → CD(0°) = 0.550, CL ≈ C_K·sin 2α com máximo 0.995 em 45° (sem estol), L/D máx = 1.00; com C_slender = 0.01, CD0 cai a 0.118 e L/D segue ≤ 1: os coeficientes têm de ser ajustados à mão (a doc: simular fluidos «is beyond the scope of MuJoCo»). Turbulência OU: Q8 (3 sementes) RMS horizontal 0.086 m com PD e 0.053 m com PID; bloco (semente 0, PD) 0.099 m.

## 6. Correções ao relatório do usuário (§5.1)
| # | Afirmação do relatório | Veredito | Correção |
|---|---|---|---|
| 1 | «Com `fluidshape="ellipsoid"` o MuJoCo desativa o cálculo esférico básico orientado pela inércia e usa um modelo aerodinâmico 3D por geom (com Kutta-Joukowski e efeito Magnus)» | PARCIAL | Núcleo certo. O modelo desativado é a CAIXA de inércia equivalente (arrasto quadrático anisotrópico por eixo principal; só o Stokes usa a esfera r_eq), não um cálculo «esférico». A desativação é POR CORPO: um geom marcado desliga a caixa do corpo e os não marcados passam a dar força zero; outros corpos mantêm a caixa. É fenomenológico e sem estado; `ellipsoidinertia` é só visual. |
| 2 | «`fluidcoef` por omissão: arrasto blunt 0.5; slender 0.25; arrasto angular 1.5; sustentação de Kutta 1.0; efeito Magnus 1.0» | CORRETA | Confirmado em `model.geom_fluid[:, 1:6]` (bloco do §1); só vale com `fluidshape="ellipsoid"`; C_blunt 0.5 ⇔ Cd clássico 1.0. |
| 3 | «Os fatores combinam-se com `density`, `viscosity` e `wind` definidos em `<option>`» | PARCIAL | `density` multiplica D, K, M e A; `viscosity` (dinâmica, Pa·s) liga o Stokes linear e NÃO é escalada por `fluidcoef` (nem a massa adicionada); `wind` só entra na velocidade translacional; sem `density`/`viscosity` > 0 não há força, mesmo com `wind` ≠ 0. |
| 4 | «O modelo de fluido resulta numa forte atenuação de objetos voadores por resistência viscosa» | INCORRETA | Por omissão não há atenuação alguma. Em ar a perda vem do arrasto QUADRÁTICO (`density`): quad de 1 kg a 10 m/s: 3.12 m/s após 10 s só com `density`; só com `viscosity`, 9.9957 m/s (−0.04 %) (bloco). Só é «forte» em meio denso (água) ou com coeficientes altos. A doc avisa que os termos viscosos do elipsoide «may overestimate dissipation» (Re baixo). |
```python
for rho, mu in ((0, 0), (0, 1.8e-5), (1.225, 0), (1.225, 1.8e-5), (1000, 8.9e-4)):       # quad_min.py — parte 7: voo livre (sem g nem empuxo) a 10 m/s
    mc = mujoco.MjModel.from_xml_string(XML); mc.opt.gravity[:] = 0; mc.opt.density, mc.opt.viscosity = rho, mu; dc = mujoco.MjData(mc); dc.qvel[0] = 10.0
    for _ in range(round(10 / mc.opt.timestep)): mujoco.mj_step(mc, dc)
    print("ρ = %-6g μ = %-7g → v(10 s) = %.4f m/s" % (rho, mu, dc.qvel[0]))
```
✔ Esperado (Q8): vácuo 10.0000; só μ 9.9957 (−0.04 %); só ρ 3.1206; ar 3.1197 (analítico `v₀/(1+k·v₀·t)` = 3.1201); água 0.0055; força viscosa/quadrática a 10 m/s = 2e-4.

## Armadilhas
| Sintoma | Causa | Correção |
|---|---|---|
| Vento/arrasto «não fazem nada» | `density` = `viscosity` = 0 (padrão e `model.xml` do template) | ligar ar (`1.225`, `1.8e-5`); no template, `--ar`/`--vento` |
| Esperava forte amortecimento viscoso | em ar domina o arrasto quadrático (μ dá −0.04 % em 10 s) | para só amortecer: `damping` de junta ou `implicitfast` (XMLreference l.380) |
| `fluidcoef` não muda nada | geom sem `fluidshape="ellipsoid"` (`geom_fluid` = 0) | marcar o geom; lembre: marcar UM desliga a caixa do corpo todo |
| O arrasto muda ao mexer em massa/inércia | a caixa de inércia deriva de `body_mass`/`body_inertia` | elipsoide sem massa (§1) com `fluidcoef` próprio |
| Quad gira/capota ao ligar o controle | sinais de `gear[5]` à mão; `mju_subQuat(res, q_des, q)` com argumentos trocados (✔ roll diverge a ±124°); quaternion `[x y z w]` | `A` do modelo (§2); quaternion MuJoCo é `[w x y z]` |
| Torque giroscópico errado | free joint: `qvel[:3]` no MUNDO, `qvel[3:6]` no CORPO (✔ testado) | `I` no corpo e `ω = qvel[3:6]` sem rotacionar |
| Realimentação 1 passo atrasada | `xpos/xmat/xipos` vêm do início do passo (✔ após `mj_step`: `xpos` 0.0000 com `qpos` 0.0020) | usar `qpos/qvel` ou `mj_kinematics` (o template usa `xipos/xmat`: 2 ms, inofensivo) |
| Hover «m·g/4» deriva | CoM fora do centro ou rotores assimétricos | `u = A⁻¹·[m·g, 0, 0, 0]` |
| Cai ~τ depois de `mj_resetData` | `act` do `filterexact` zerado | `d.act[:] = hover` ou `<key act>` + `mj_resetDataKeyframe` |
| Guinada agressiva derruba altitude | rotores saturam (autoridade de guinada = k·f) | limitar ganho/taxa de guinada; contar passos saturados |
| X2 planeia; CF2 «não gira» | I_xz ≠ 0 inclina a caixa; CF2 com momento 1e-5 N·m | §4: zerar I_xz; `gear` ×100 ou ganhos baixos (kp ≈ 9) |
| `from_xml_path` do Menagerie falha | espelho sem `assets/` | `sem_malhas()` (§4) ou clone completo do Menagerie |
| Degrau em referência + `ki` alto: sobressinal, cauda longa | polo lento do integrador (ki 1.2 ⇒ −0.146 s⁻¹) | trajetória min-jerk (template) ou `ki` menor |
| MJX: `NotImplementedError('fluid drag not supported for implicitfast')` | MJX sem derivadas de fluido; só caixa de inércia | MJWarp, ou sem fluido (não executado em GPU) |
