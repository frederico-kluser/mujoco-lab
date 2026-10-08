# API Python do MuJoCo 3.15 — ciclo de vida, acesso por nome, simulação, derivadas e rollout

Cobre `MjSpec → MjModel → MjData`, acesso nomeado e `bind()`, `mj_step`/estado, contatos, derivadas, callbacks, `mujoco.rollout`/`minimize` e as correções às skills oficiais e ao §4 do relatório do usuário.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: fichas `pesquisas/conhecimento/{Q6,Q7,Q14}.md`; `docs/upstream/mujoco/doc/{python.rst,programming/{simulation,modeledit}.rst,APIreference/*,skills/{python,spec_editing}/SKILL.md}`; `python/mujoco/{bindings_test,rollout,minimize}.py` e notebooks `python/*.ipynb.md`; `scripts/mjkit.py`; testes executados em `.venv` (Python 3.13, 32 CPUs lógicos).

## Quando ler este arquivo
- Vai escrever ou depurar código Python com MuJoCo: MjSpec, acesso por nome, laço de simulação, estado, contatos, derivadas, callbacks, rollout.
- Código copiado das skills oficiais ou do relatório do usuário falhou ou deu resultado estranho (§10, §11).
- Legenda: ✔ testado neste laboratório · ⚠ armadilha · Δ doc (a doc diverge do medido) · «ficha» = veio da ficha, não reexecutado.
- Outros temas: MJCF → `references/mjcf-cheatsheet.md`; atuadores/sensores → `references/actuators-sensors.md`; instabilidade → `references/physics-tuning.md`; viewer/render → `references/rendering-viewer.md`.

## 1. Ciclo de vida: MjSpec → compile → MjModel → MjData

| Objeto | Como criar | Notas |
| --- | --- | --- |
| `MjSpec` | `MjSpec()`, `MjSpec.from_string(xml)`, `from_file(path)`, `from_zip(f)` | blueprint **mutável**, segue editável após `compile()`; `spec.body('x')` devolve `None` (não `KeyError`) se não existir |
| `MjModel` | `spec.compile()`, `MjModel.from_xml_string(xml, assets=None, vfs=None)`, `from_xml_path(p)`, `from_binary_path(p.mjb)` | **sem construtor** (`MjModel()` → `TypeError`); estrutura (`nq`, `nv`, `nbody`…) somente leitura, reais graváveis |
| `MjData` | `MjData(model)` | estado + entradas + derivados; `copy.copy`, `pickle` e `mj_copyData` copiam |

```python
import mujoco

spec = mujoco.MjSpec()                                   # blueprint mutável (timestep padrão 0.002)
braco = spec.worldbody.add_body(name="braco", pos=[0, 0, 1])
braco.add_joint(name="junta", type=mujoco.mjtJoint.mjJNT_HINGE, axis=[0, 1, 0], damping=0.02)
braco.add_geom(name="haste", type=mujoco.mjtGeom.mjGEOM_CAPSULE, fromto=[0, 0, 0, 0, 0, -0.5], size=[0.02, 0, 0], mass=1.0)
braco.add_site(name="ponta", pos=[0, 0, -0.5], size=[0.01, 0, 0])
motor = spec.add_actuator(name="motor", trntype=mujoco.mjtTrn.mjTRN_JOINT, target="junta", ctrllimited=True, ctrlrange=[-5, 5])
motor.set_to_motor()                                     # só ganhos: a transmissão (trntype/target) é obrigatória à parte
spec.add_sensor(name="theta", type=mujoco.mjtSensor.mjSENS_JOINTPOS, objtype=mujoco.mjtObj.mjOBJ_JOINT, objname="junta")
spec.add_sensor(name="acc", type=mujoco.mjtSensor.mjSENS_ACCELEROMETER, objtype=mujoco.mjtObj.mjOBJ_SITE, objname="ponta")
spec.add_key(name="inicio", qpos=[0.3])

model = spec.compile()                                   # MjSpec -> MjModel
data = mujoco.MjData(model)                              # MjModel -> MjData
mujoco.mj_resetDataKeyframe(model, data, model.key("inicio").id)
slot = model.actuator_ctrladr[model.actuator("motor").id]  # posição em data.ctrl (≠ id com atuador multi-entrada, §2)
for _ in range(500):                                     # 1 s
    data.ctrl[slot] = 0.5
    mujoco.mj_step(model, data)
mujoco.mj_forward(model, data)                           # sensores e xpos coerentes com o qpos atual (§3)
print("theta", data.sensor("theta").data, "| acc local", data.sensor("acc").data.round(3), "| ponta", data.site("ponta").xpos.round(3))   # ✔ theta≈0.250

b2 = spec.worldbody.add_body(name="bola", pos=[1, 0, 1]); b2.add_geom(size=[0.1, 0, 0]); b2.add_freejoint()
model2, data2 = spec.recompile(model, data)              # NOVO par (tupla), estado preservado; o par antigo segue válido
print("nq", model.nq, "->", model2.nq, "| qpos[0] preservado:", data2.qpos[0] == data.qpos[0])   # ✔ 1 -> 8
```

- **Serializar** ✔: `spec.to_xml()` (string), `spec.encode("m.xml")`, `spec.encode("m.mjb", model=model)` (binário do `MjModel`, específico da versão), `spec.to_zip(f)` + `MjSpec.from_zip(f)`; `spec.encode('m.mjz', model=model)` (com assets) carrega com `MjSpec.from_file('m.mjz')` — Δ doc: `MjModel.from_xml_path('m.mjz')` falha (`ValueError: XML parse error`); `spec.copy()`; `pickle` e `copy.copy` de `MjModel`/`MjData`.
- ⚠ `spec.recompile(model, data)` **devolve tupla nova** (o `mj_recompile` do C é in-place) e preserva `time/qpos/qvel`; reatribua sempre. Após edição estrutural, `data.bind(...)` com o par antigo → `ValueError: The mjSpec does not match mjData`.
- Edição: nome duplicado → `ValueError` no próprio `add_*`; remover = `spec.delete(elem)` (não há `delete_body`); ⚠ um `add_*` que falha na validação pode deixar o elemento residual e quebrar o próximo `compile()` (✔ `add_equality`; correção: `spec.delete(spec.equalities[-1])`).
- Assets: `with mujoco.MjVfs() as vfs: vfs["a.obj"] = bytes` e `vfs=vfs` em `from_xml_string/from_file/compile`. Δ doc: o dict `assets=` ainda funciona em 3.15.0, sem aviso, mas a doc o declara depreciado.
- `MjModel` compilado: reais graváveis (`m.opt.timestep`, `m.body_mass`, `m.geom_friction`); após mudar massa/inércia/`qpos0` chame `mujoco.mj_setConst(m, d)` (✔ `body_subtreemass` só atualiza depois); inteiros estruturais → `AttributeError`. Tabela de segurança: `programming/simulation.rst` §«mjModel changes».

## 2. Acesso por nome vs `bind()`

| API | O que existe de fato (✔ 3.15.0) |
| --- | --- |
| `model.<cat>(nome\|id)` | `body jnt/joint geom site cam/camera light mesh skin hfield tex/texture mat/material pair exclude eq/equality tendon actuator sensor numeric tuple key/keyframe`. **Δ doc**: python.rst lista também `ten` e `text`; `MjModel` NÃO os tem (`AttributeError`; texto em `m.text_data/text_adr`) |
| `data.<cat>(nome\|id)` | só `body jnt/joint geom site cam/camera light tendon/ten actuator sensor` |
| `.id`, `.name` | substituem `mj_name2id`/`mj_id2name`; nome inválido → `KeyError` (lista os válidos), índice inválido → `IndexError` |
| campos | `data.joint(j).qpos/qvel` (1, 4 ou 7 valores, conforme o tipo), `data.body(b).xpos/xquat/xmat/xipos/cvel`, `data.geom/site(x).xpos/xmat`, `data.actuator(a).ctrl/force/length`, `data.sensor(s).data`; `model.joint(j).qposadr/dofadr/range`, `model.body(b).mass/pos`, `model.geom(g).size/friction/rgba`, `model.actuator(a).gear/ctrlrange/gainprm`, `model.sensor(s).adr/dim`, `model.key(k).qpos` (escalares vêm como arrays de 1 elemento) |
| `model.bind(x)` / `data.bind(x)` | `x` = elemento do **spec** (`spec.joint('j')`) ou lista deles (leitura devolve lista); exige `model/data` compilados do mesmo spec, sem edição estrutural depois |
| `bind(...).set(...)` | **não existe** (`AttributeError`); escreva por atribuição: `data.bind(j).qpos = v` |

```python
import mujoco, numpy as np
XML = """<mujoco><worldbody><body name="bola" pos="0 0 2"><freejoint/><geom size=".1" mass="1"/></body>
<body name="b1"><joint name="j1" type="slide"/><geom size=".1" mass="1"/></body><body name="b2"><joint name="j2" type="slide"/><geom size=".1" mass="1"/></body></worldbody>
<actuator><motor name="m1" joint="j1"/><motor name="m2" joint="j2"/></actuator></mujoco>"""
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m)
ruim, bom = [], []
for _ in range(50):
    mujoco.mj_step(m, d); ruim.append(d.body("bola").xpos); bom.append(d.body("bola").xpos.copy())
print("sem .copy(): todos iguais =", all(np.array_equal(ruim[0], r) for r in ruim), "| com .copy():", all(np.array_equal(bom[0], b) for b in bom))
d.joint("j1").qpos = 0.5; d.qpos[8:] = 0.1                # atribuir COPIA para o mesmo buffer (tamanho errado → ValueError)
try: d.actuator("xx")
except KeyError as e: print("KeyError:", e)
i = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, "xx"); d.ctrl[:] = 0; d.ctrl[i] = 7.0
print("mj_name2id('xx') =", i, "→ ctrl[-1] = 7 grava no ÚLTIMO atuador:", d.ctrl)
spec = mujoco.MjSpec.from_string(XML); m = spec.compile(); d = mujoco.MjData(m)
d.bind(spec.joint("j1")).qpos = 0.5                       # bind: atribuição (não existe .set)
d.bind([spec.joint("j1"), spec.joint("j2")]).qpos = [1.0, 2.0]; print("qpos =", d.qpos[7:], "| leitura:", d.bind(spec.joint("j2")).qpos)
```

⚠ **Atuadores multi-entrada** (`pid` = 2 controles por padrão, `orientation` = 3 ou 4, `dcmotor` = 0–4): `nu = Σ actuator_ctrlnum ≠ nactuator`. `data.actuator('x').ctrl`, `data.bind(atuador_spec).ctrl` e `data.ctrl[id]` indexam pelo **id** e gravam no slot errado, sem erro; `.force` do acessor também usa o id em vez de `actuator_outadr`. Com todos os atuadores de 1 controle o acessor é correto. Receita segura (a de `lab.mjkit.Ctrl`: `ctrl.set(data, "mb", 5.0)`; mais em `references/actuators-sensors.md`):

```python
import mujoco
XML = """<mujoco><option integrator="implicitfast"/><worldbody><body pos="0 0 1"><joint name="ja" axis="0 1 0" armature="0.05"/><geom size=".05" mass="1"/></body>
<body pos="1 0 1"><joint name="jb" axis="0 1 0" armature="0.05"/><geom size=".05" mass="1"/></body></worldbody>
<actuator><pid name="servo" joint="ja" kp="30" kv="3"/><motor name="mb" joint="jb"/></actuator></mujoco>"""
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m)
print("nactuator", m.nactuator, "nu", m.nu, "ctrladr", m.actuator_ctrladr, "ctrlnum", m.actuator_ctrlnum, "| entradas do pid:", [mujoco.mj_actuatorInputName(m, 0, k) for k in range(2)])
d.actuator("mb").ctrl = 5.0; print("acessor (errado):", d.ctrl)
d.ctrl[:] = 0; i = m.actuator("mb").id; a = m.actuator_ctrladr[i]
d.ctrl[a : a + m.actuator_ctrlnum[i]] = 5.0; print("receita (certa) :", d.ctrl)
```

## 3. Simulação, estado e tempo real

| Chamada | Semântica (✔ testada) |
| --- | --- |
| `mj_step(m, d, nstep=1)` | `mj_checkPos/Vel` → `mj_forward` → `mj_checkAcc` → integrador. `nstep=N` ≡ N chamadas (bit a bit), repete o `ctrl` e não readquire o GIL entre passos (poupa ≈ 0,3 µs/chamada: só pesa em modelos minúsculos) |
| `mj_forward(m, d)` | calcula derivados e sensores do estado atual; **não integra nem avança `time`**. Euler: `mj_step ≡ mj_forward + mj_Euler` |
| `mj_step1` / `mj_step2` | só integradores de passo único (euler/implicit/implicitfast); com RK4 o `mj_step2` integra como **Euler** (≠ `mj_step`); `mjcb_control` roda dentro de `mj_step1` |
| `mj_resetData` | `qpos←qpos0`, mocap←pose do XML; `ctrl`, `qfrc/xfrc_applied`, `time`, warmstart e avisos ← 0; os derivados também ficam em 0 (não recalcula) |
| `mj_resetDataKeyframe(m, d, k)` | copia `time, qpos, qvel, act, ctrl, mocap` de `model.key('nome').id` (no spec: `spec.add_key(name=, qpos=…)`); sem recalcular derivados |
| `mj_stateSize(m, sig)`, `mj_getState/setState(m, d, s, sig)`, `mj_copyState(m, src, dst, sig)` | `sig` = bits de `mjtState`: `PHYSICS`=30 (nq+nv+na), `FULLPHYSICS`=8223 (+`time`; entrada do rollout), `INTEGRATION`=16383 (toda a entrada da dinâmica direta), `CTRL`=64. Custo (humanoide, µs): `MjData(m)` 580 · `copy.copy(d)` 650 · `mj_copyData` 7,9 · `getState+setState` 2,0 · `mj_copyState` 0,6 · `mj_step` 58 |

⚠ **Derivados atrasados**: após `mj_step`, `xpos`, `site_xpos`, `sensordata` e `energy` ainda refletem o estado **anterior** à integração (✔ `jointpos`=0.400000 com `qpos`=0.399955). Chame `mj_forward` antes de ler — também após `MjData(m)`, reset, keyframe ou escrita em `qpos`. Em amostragem aloque 1 `MjData` por thread e reinicialize com `mj_copyState`/`mj_setState`, nunca com `copy.copy`.

```python
import mujoco, numpy as np, copy
XML = """<mujoco><option timestep="0.002"/><worldbody><body pos="0 0 1"><joint name="j" axis="0 1 0"/><geom type="capsule" fromto="0 0 0 0 0 -.5" size=".02" mass="1"/></body></worldbody>
<sensor><jointpos name="jp" joint="j"/></sensor><keyframe><key name="baixo" time="1.5" qpos="0.4" qvel="0.1"/></keyframe></mujoco>"""
def novo(integ=mujoco.mjtIntegrator.mjINT_EULER):
    m = mujoco.MjModel.from_xml_string(XML); m.opt.integrator = integ; d = mujoco.MjData(m); d.qpos[0] = 0.4; return m, d
m, d = novo(); mujoco.mj_step(m, d); print("após mj_step: qpos %.6f, jointpos %.6f (atrasado)" % (d.qpos[0], d.sensordata[0]))
mujoco.mj_forward(m, d); print("após mj_forward: jointpos %.6f" % d.sensordata[0])
me, de = novo(); mujoco.mj_step(me, de, nstep=100)       # referência: Euler puro
for nome, integ in (("Euler", mujoco.mjtIntegrator.mjINT_EULER), ("RK4", mujoco.mjtIntegrator.mjINT_RK4)):
    m, d1 = novo(integ); _, d2 = novo(integ)
    for _ in range(100): mujoco.mj_step1(m, d1); mujoco.mj_step2(m, d1); mujoco.mj_step(m, d2)
    print(nome, "step1+2 == mj_step:", np.array_equal(d1.qpos, d2.qpos), "| == Euler puro:", np.array_equal(d1.qpos, de.qpos))
m, d = novo(); mujoco.mj_resetDataKeyframe(m, d, m.key("baixo").id); print("keyframe: time", d.time, "qvel", d.qvel, "| sensor antes do forward:", d.sensordata)
# estado: INTEGRATION reproduz a trajetória bit a bit; FULLPHYSICS não restaura o warmstart (erro ~1e-17..1e-15)
m = mujoco.MjModel.from_xml_string("""<mujoco><worldbody><geom type="plane" size="3 3 .1"/><body pos="0 0 .3" euler="30 20 10"><freejoint/><geom type="box" size=".1 .08 .06" mass="1"/></body></worldbody></mujoco>""")
d = mujoco.MjData(m); mujoco.mj_step(m, d, nstep=150)    # já em contato
for nome, sig in (("FULLPHYSICS", mujoco.mjtState.mjSTATE_FULLPHYSICS), ("INTEGRATION", mujoco.mjtState.mjSTATE_INTEGRATION)):
    s = np.empty(mujoco.mj_stateSize(m, sig)); mujoco.mj_getState(m, d, s, sig)
    ref = copy.copy(d); mujoco.mj_step(m, ref, nstep=500)
    d2 = mujoco.MjData(m); mujoco.mj_setState(m, d2, s, sig); mujoco.mj_step(m, d2, nstep=500)
    print(nome, "tamanho", s.size, "| erro máx de qpos após 500 passos:", np.abs(ref.qpos - d2.qpos).max())
```

**Como injetar controle** (✔ laço explícito ≡ callback ≡ step1/2, bit a bit, se o controle lê só `qpos/qvel/time`). `ctrl`, `qfrc_applied`, `xfrc_applied` e `mocap_*` são entradas: **persistem** entre passos (só `mj_resetData` as zera).

| Forma | Usar quando | Cuidado |
| --- | --- | --- |
| `data.ctrl[slot] = u; mj_step(m, d)` | padrão: controle em função do **estado** | se ler `sensordata`/`xpos`/contatos, vêm do passo anterior (✔ 400 passos: \|Δqpos\| = 4,5e-6) |
| `mj_step1` → grava `ctrl/qfrc_applied/xfrc_applied` → `mj_step2` | controle usa sensores/cinemática/contatos do instante atual | só Euler/implicit/implicitfast |
| `mujoco.set_mjcb_control(f)` | RK4 (único jeito de variar o controle entre os 4 sub-passos), plugins | GIL por chamada (§7) |
| `mj_step(m, d, nstep=N)` | malha aberta, `ctrl` constante, amostragem | `ctrl` repetido N vezes |

**Avisos** (Q14): `data.warning[i].number/.lastinfo` (7 tipos `mjtWarning`: INERTIA, CONTACTFULL, CNSTRFULL, BADQPOS, BADQVEL, BADQACC, BADCTRL). NaN/Inf/|x|>1e10 → aviso + **autoreset** (padrão): `qpos←qpos0` e `time←0` em silêncio (✔ `time` = 0,05 · 0,1 · **0,05** · 0,1…). Teste `d.warning.number.any()` e pare; `m.opt.disableflags |= mujoco.mjtDisableBit.mjDSBL_AUTORESET` mantém o estado divergente (✔ |qpos|≈2e29); `set_mju_user_warning(f)` captura as mensagens (✔); `ctrl` NaN → BADCTRL sem reset.

**Tempo real com `launch_passive`** (✔ stub sem janela: timestep 2 ms, `sync()` simulado 1,5 ms, 3 s): `step; sync; sleep(timestep)` → 0,51× · `sleep(timestep − gasto)` (python.rst, «will drift») → 0,94× · **âncora no relógio de parede** (avançar `mj_step` até `data.time` alcançar `perf_counter()−t0`, ≤ 50 passos de recuperação) → 1,00×; código em §11. `sync()` trava internamente; mexer em `viewer.opt/cam/pert` pede `with viewer.lock():`; `sync(state_only=True)` é mais rápido; no macOS use `mjpython`. Janela real: não testada (política do laboratório).

## 4. Convenções de estado

| Item | Convenção (✔) |
| --- | --- |
| Quaternion | `[w x y z]` (`qpos` livre/esférica, `xquat`, `mocap_quat`, `mju_*`). SciPy/ROS usam `[x y z w]`: `q_sp = q[[1,2,3,0]]`, `q_mj = q_sp[[3,0,1,2]]` |
| Junta livre | `qpos=[x y z qw qx qy qz]` (7), `qvel` 6: `qvel[:3]` linear no referencial do **mundo**; `qvel[3:]` angular no referencial do **corpo** (o `gyro` lê exatamente `qvel[3:]`; o `velocimeter` lê a linear no corpo) |
| `nq ≠ nv` | com quaternions use `mj_integratePos(m, qpos, qvel, dt)` / `mj_differentiatePos(m, dq, dt, qpos1, qpos2)`; nunca some/subtraia `qpos` |
| Matrizes | `xmat` (9) → `reshape(3,3)`: colunas = eixos do corpo no mundo. `contact.frame` (9) é **transposto**: eixos nas LINHAS |
| Euler | `mju_euler2Quat(q, e, 'xyz')`: minúsculas = intrínseco (≡ SciPy `'XYZ'`); maiúsculas = extrínseco |

```python
import mujoco, numpy as np
from scipy.spatial.transform import Rotation as R
m = mujoco.MjModel.from_xml_string("""<mujoco><option gravity="0 0 0"/><worldbody><body pos="0 0 1" quat="0.7071068 0 0 0.7071068"><freejoint/><geom size=".1" mass="1"/><site name="s"/></body></worldbody>
<sensor><velocimeter name="v" site="s"/><gyro name="w" site="s"/><framelinvel name="vw" objtype="site" objname="s"/></sensor></mujoco>""")
d = mujoco.MjData(m); d.qvel[:] = [1, 0, 0, 0, 0.5, 0]; mujoco.mj_forward(m, d)    # qvel[:3] MUNDO, qvel[3:] CORPO
print("nq, nv =", m.nq, m.nv, "| linear no mundo", d.sensor("vw").data, "| no corpo (velocimeter)", d.sensor("v").data.round(3), "| gyro", d.sensor("w").data)
q = np.zeros(4); mujoco.mju_axisAngle2Quat(q, np.array([0, 0, 1.0]), np.pi / 2)    # [w x y z]
M = np.zeros(9); mujoco.mju_quat2Mat(M, q); M = M.reshape(3, 3)
print("quat2Mat == SciPy:", np.allclose(M, R.from_quat(q[[1, 2, 3, 0]]).as_matrix()))
qe = np.zeros(4); mujoco.mju_euler2Quat(qe, np.array([.1, .2, .3]), "xyz")
print("euler2Quat('xyz') == SciPy 'XYZ':", np.allclose(qe[[1, 2, 3, 0]], R.from_euler("XYZ", [.1, .2, .3]).as_quat()))
```

## 5. Contatos, raios e sensores declarativos

- `data.contact`: struct-array de tamanho `ncon` (`geom` N×2, `dist`, `pos`, `frame` N×9, `dim`, `efc_address`, `exclude`…). Use `contact.geom`; `geom1/geom2` existem, mas estão deprecated no cabeçalho. Tamanho e ordem mudam a cada passo → **não use como observação de ML**: use sensores `<contact>` (tamanho fixo `num × campos`).
- `mj_contactForce(m, d, i, res6)` → `[força(3), torque(3)]` no **frame do contato** (normal = eixo x = `frame[0:3]`); mundo = `frame.reshape(3,3).T @ f`. A normal aponta de `geom[0]` para `geom[1]`; `f_mundo` é a força de `geom[0]` **sobre** `geom[1]`; a ordem segue o **tipo** do geom (plano antes de caixa/esfera), não o id. Torque ≠ 0 só com `condim` ≥ 4. Não leia `efc_force` cru (cone pirâmide).
- `mj_ray(m, d, pnt, vec, geomgroup, flg_static, bodyexclude, geomid, normal=None) → float`: x tal que `pnt + x·vec` toca a superfície (−1 se nada); `geomid` = `np.int32[1]` gravável; `geomgroup` = `uint8[6]` ou `None`; `bodyexclude=-1` inclui tudo. **Exige `mj_forward`/`mj_kinematics`** (após `MjData(m)` devolve −1).
- Sensor `<contact reduce="netforce">`: 1 contato sintético, força no referencial **global**, convenção geom1→geom2 (sinal oposto ao de `mj_contactForce` quando geom[0] é o piso). `touch` = escalar ≥ 0.

```python
import mujoco, numpy as np
m = mujoco.MjModel.from_xml_string("""<mujoco><option cone="elliptic"/><worldbody><geom name="piso" type="plane" size="3 3 .1"/>
<body pos="0 0 .06"><freejoint/><geom name="cx" type="box" size=".1 .08 .05" mass="2" condim="6"/></body></worldbody>
<sensor><contact name="net" geom1="cx" geom2="piso" data="found force" reduce="netforce"/></sensor></mujoco>""")
d = mujoco.MjData(m); gid = np.zeros(1, np.int32); cima, baixo = np.array([0., 0, 2]), np.array([0., 0, -1])
print("mj_ray antes do forward:", mujoco.mj_ray(m, d, cima, baixo, None, 1, -1, gid))             # -1.0
mujoco.mj_step(m, d, nstep=1500); mujoco.mj_forward(m, d)
f, res = np.zeros(3), np.zeros(6)
for i in range(d.ncon):
    mujoco.mj_contactForce(m, d, i, res)                                                          # frame do contato
    f += d.contact[i].frame.reshape(3, 3).T @ res[:3]                                             # → mundo
print("ncon", d.ncon, "| Σ força (mundo)", f.round(3), "| m·g", 2 * 9.81, "| geoms:", [m.geom(g).name for g in d.contact[0].geom])
print("sensor netforce [found, F]:", d.sensor("net").data.round(3), "| mj_ray:", round(mujoco.mj_ray(m, d, cima, baixo, None, 1, -1, gid), 4), m.geom(gid[0]).name)
```

## 6. Derivadas, Jacobianos, forças externas e `minimize`

| API | Forma / nota |
| --- | --- |
| `mjd_transitionFD(m, d, eps, flg_centered, A, B, C, D)` | `A` (2nv+na)², `B` (2nv+na)×nu, **`C` ns×(2nv+na)**, **`D` ns×nu** (ns=`nsensordata`); todas opcionais (`None`); estado no espaço tangente `[dq, dv, da]`. **Δ doc**: docstring e cabeçalho trocam C e D; o runtime exige `C=(ns, 2nv+na)` (`TypeError`). RK4 → `FatalError: RK4 integrator is not supported` |
| ⚠ **bug 3.15.0** | `flg_centered=True` devolve **D com sinal trocado** (A, B, C corretos; o LQR do notebook usa `True` só para A,B). Para D use `flg_centered=False` (ou `-D`) |
| `mjd_inverseFD(m, d, eps, flg_actuation, DfDq, DfDv, DfDa, DsDq, DsDv, DsDa, DmDq)` | todas anuláveis; `DfD*` nv×nv, `DsD*` nv×ns, `DmDq` nv×**nC** (nv×nM até 3.10); `DfDa ≈ M` (✔) |
| `mj_jac(m,d,jacp,jacr,point,body)`, `mj_jacBody/BodyCom/Geom/Site`, `mj_jacSubtreeCom(m,d,jacp,body)` | `jacp/jacr` (3,nv) ou `None`; exigem `mj_forward` **ou** `mj_kinematics`+`mj_comPos`: só `mj_kinematics` → zeros (✔) |
| `mj_applyFT(m,d,force,torque,point,body,qfrc)` | força/torque no ponto (mundo) → `qfrc` (nv). `xfrc_applied[b]` = wrench (força+torque, 6) no CoM do corpo, no mundo (✔ ≡ `mj_applyFT` com `point=xipos`) |

```python
import mujoco, numpy as np
from mujoco import minimize                                # não vem com `import mujoco`
m = mujoco.MjModel.from_xml_string("""<mujoco><option timestep="0.005" integrator="implicitfast"/><worldbody><body name="l1"><joint name="q1" axis="0 1 0" damping=".1"/>
<geom type="capsule" fromto="0 0 0 0 0 -.5" size=".02" mass="1"/><body name="l2" pos="0 0 -.5"><joint name="q2" axis="0 1 0"/><geom type="capsule" fromto="0 0 0 0 0 -.4" size=".02" mass=".5"/>
<site name="ponta" pos="0 0 -.4"/></body></body></worldbody><actuator><position name="p" joint="q1" kp="5"/></actuator>
<sensor><actuatorfrc name="af" actuator="p"/><jointpos name="jp" joint="q1"/><jointvel name="jv" joint="q1"/></sensor></mujoco>""")
d = mujoco.MjData(m); nx, ns = 2 * m.nv + m.na, m.nsensordata
def fd(centered):
    A, B = np.zeros((nx, nx)), np.zeros((nx, m.nu)); C, D = np.zeros((ns, nx)), np.zeros((ns, m.nu))
    mujoco.mjd_transitionFD(m, d, 1e-6, centered, A, B, C, D); return A, B, C, D
print("D[0] = ∂actuatorfrc/∂ctrl (esperado +kp = +5): não centrado", fd(False)[3][0], "| centrado", fd(True)[3][0])     # [5.] [-5.]
alvo = np.array([0.35, -0.55])                              # (x, z) da ponta
def residual(x):                                            # x: (nparam, npontos) → float64 (nres, npontos)
    r = np.empty((2, x.shape[1]))
    for k in range(x.shape[1]):
        d.qpos[:] = x[:, k]; mujoco.mj_kinematics(m, d); r[:, k] = d.site("ponta").xpos[[0, 2]] - alvo
    return r
x, trace = minimize.least_squares(np.array([-0.3, -0.3]), residual, bounds=[np.full(2, -2.5), np.full(2, 2.5)], verbose=minimize.Verbosity.SILENT)
print("IK: q =", x.round(4), "| erro", np.linalg.norm(residual(x.reshape(-1, 1))), "| iterações", len(trace))        # x tem shape (2,)
d2 = mujoco.MjData(m); d2.qpos[:] = x; J = np.zeros((3, m.nv)); s = m.site("ponta").id
mujoco.mj_kinematics(m, d2); mujoco.mj_jacSite(m, d2, J, None, s); print("Jac só com kinematics:", abs(J).max())      # 0.0
mujoco.mj_comPos(m, d2); mujoco.mj_jacSite(m, d2, J, None, s); print("Jac com comPos (ou mj_forward):", abs(J).max().round(3))
b = m.body("l2").id; qf = np.zeros(m.nv); mujoco.mj_applyFT(m, d2, np.array([1., 0, 0]), np.zeros(3), d2.xipos[b], b, qf); d2.qfrc_applied[:] = qf   # persiste
```
`minimize.least_squares(x0, residual, bounds=None, jacobian=None, norm=Quadratic(), eps=1.49e-8, mu_min=1e-6, mu_max=1e8, mu_factor=1.2589, xtol=1e-8, gtol=1e-8, max_iter=100, verbose=Verbosity.ITER, output=None, iter_callback=None, check_derivatives=False, x_scale=None) → (x, trace)`; sem `jacobian` usa diferenças finitas. Exemplos: `python/{least_squares,LQR}.ipynb.md`.

## 7. Callbacks `set_mjcb_*` e o GIL

| Setter (+ `get_mjcb_*`) | Assinatura Python ✔ | Nota |
| --- | --- | --- |
| `control`, `passive` | `f(m, d)` | `control`: 1×/`mj_step`/`mj_forward`/`mj_step1` (Euler, implicit*) e **4×/`mj_step` com RK4** |
| `contactfilter` | `f(m, d, geom1, geom2) -> int` | |
| `sensor` | `f(m, d, stage)` | sensor `user`; 1×/passo **mesmo em RK4** (`stage`=2=VEL com `needstage=vel`) |
| `act_dyn`, `act_gain`, `act_bias` | `f(m, d, id) -> float` | atuador `user` |
| `time` | `f() -> float` | `None` restaura o timer padrão (segundos) |
| `set_mju_user_warning(f(str))`, `set_mju_user_malloc/free` | malloc/free só aceitam ponteiros ctypes | globais do processo: `try/finally` + `set_mjcb_x(None)`; exceção no callback propaga como a original (✔ `ValueError`) |

```python
import mujoco
XML = "<mujoco><worldbody><body><joint axis='0 1 0'/><geom size='.1'/></body></worldbody></mujoco>"
for integ in (mujoco.mjtIntegrator.mjINT_EULER, mujoco.mjtIntegrator.mjINT_RK4):
    m = mujoco.MjModel.from_xml_string(XML); m.opt.integrator = integ; d = mujoco.MjData(m); n = []
    mujoco.set_mjcb_control(lambda m_, d_: n.append(1))      # GLOBAL do processo: sempre desfaça
    try: mujoco.mj_step(m, d)
    finally: mujoco.set_mjcb_control(None)
    print(integ.name, "chamadas de mjcb_control por mj_step:", len(n))        # Euler 1 · RK4 4
```
**Custo medido** (✔ Python 3.13 com GIL, 32 CPUs, medianas): callback Python vazio ≈ **0,6–0,9 µs/chamada**: modelo 1-DoF Euler 1,88→2,76 µs/passo (1,46×), RK4 8,9→11,2 µs (1,26×, 4 chamadas); humanoide (27 DoF): dentro do ruído (±10 %). Ponteiro C via ctypes ≈ 1,0× (RK4 1-DoF: 6,67 = 6,67 µs/passo). O dano real é o **multi-thread**: 8 threads Python (humanoide, `mj_step(nstep=4000)` cada) levam 1,6× o tempo de 1 thread sem callback e **4,8×** com callback Python: o GIL degrada o escalonamento, mas não «paralisa» o solver. Mitigação ctypes (✔, o GIL **não** é adquirido): `printf 'typedef struct mjModel_ mjModel;\ntypedef struct mjData_ mjData;\nvoid ctrl_noop(const mjModel* m, mjData* d) {}\n' > cb.c; gcc -shared -fPIC -O2 -o libcb.so cb.c` e `mujoco.set_mjcb_control(ctypes.CDLL("./libcb.so").ctrl_noop)`. Alternativas mais simples: `ctrl` antes de `mj_step` (§3), `mj_step1/2`, `nstep`, `mujoco.rollout` (malha aberta). Builds free-threaded: não verificado.

## 8. `mujoco.rollout` (CPU, multithread nativo)

`rollout.rollout(model, data, initial_state, control=None, *, control_spec=mjSTATE_CTRL(64), skip_checks=False, nstep=None, initial_warmstart=None, state=None, sensordata=None, chunk_size=None, persistent_pool=False) → (state, sensordata)`

- `initial_state` (nbatch×nstate, `nstate = mj_stateSize(m, FULLPHYSICS)`, 1ª coluna = `time`) e `control` (nbatch×nstep×ncontrol) devem ser `np.ndarray` (lista → `ValueError`); saídas `state` (nbatch×nstep×nstate) e `sensordata` (nbatch×nstep×nsensordata). `model` pode ser uma sequência de nbatch modelos homogêneos. É **sem estado**: o conteúdo prévio do `MjData` não influi; em rollouts em blocos passe `initial_warmstart=d.qacc_warmstart` (ficha Q14).
- **Lista** de N `MjData` → N threads nativas (GIL liberado); 1 `MjData` roda no thread chamador; **tupla** → `RuntimeError` (só `list` conta como sequência). `persistent_pool=True` reutiliza o pool (não é thread-safe; `rollout.shutdown_persistent_pool()`); para vários pools use `rollout.Rollout(nthread=n)` (`with`/`close()`; ✔ exige `len(data)==n`, senão `ValueError`).
- ⚠ **Para no 1º aviso de qualquer tipo** (BAD*, CONTACTFULL, CNSTRFULL, INERTIA; ✔ com arena pequena, sem NaN) e preenche o resto com o estado atual: `time` deixa de crescer. Como o `autoreset` zera o estado, o `time` pode até **cair** (✔ 0,05 · 0,1 · 0,05 · 0,05…): `np.diff(state[..., 0], axis=1) <= 0` detecta rollouts divergentes.

```python
import mujoco, numpy as np
from mujoco import rollout                                 # não vem com `import mujoco`
m = mujoco.MjModel.from_xml_path("docs/upstream/mujoco/model/humanoid/humanoid.xml")   # relativo à raiz do projeto
sig = mujoco.mjtState.mjSTATE_FULLPHYSICS; d0 = mujoco.MjData(m); s0 = np.empty(mujoco.mj_stateSize(m, sig))
mujoco.mj_forward(m, d0); mujoco.mj_getState(m, d0, s0, sig)                           # s = [time, qpos, qvel, act]
nbatch, nstep = 64, 400; rng = np.random.default_rng(0)
init = np.tile(s0, (nbatch, 1)); init[:, 1:1 + m.nq] += 0.01 * rng.standard_normal((nbatch, m.nq))
ctrl = 0.1 * rng.standard_normal((nbatch, nstep, m.nu))
datas = [mujoco.MjData(m) for _ in range(8)]                                           # LISTA: 8 MjData = 8 threads
state, sens = rollout.rollout(m, datas, init, ctrl)
ref, _ = rollout.rollout(m, datas[0], init, ctrl)                                       # 1 MjData → thread chamador
print(state.shape, sens.shape, "| idêntico a 1 thread:", np.array_equal(state, ref), "| nstate", s0.size, "= 1+nq+nv+na")
with rollout.Rollout(nthread=4) as ro:                                                  # pool próprio
    st4, _ = ro.rollout(m, datas[:4], init, ctrl)
print("algum rollout divergiu:", bool((np.diff(st4[..., 0], axis=1) <= 0).any()))
```
Medido (✔ humanoide, 64×400 passos): 1,3×/3,0×/4,0×/6,5× com 2/4/8/16 `MjData` contra 1; resultados bit a bit idênticos. Alternativa: 1 `MjModel` compartilhado + 1 `MjData` por **thread Python** com `mj_step(m, d, nstep=N)` (GIL liberado; ✔ 8 threads ≈ 4,9× de vazão; o `mju_threadpool` interno rende ≈ 1,3×, ficha Q14). Só CPU; GPU = MJX/Warp (`references/gpu-mjx-warp.md`).

## 9. O que `import mujoco` NÃO traz

`mujoco.rollout`, `mujoco.minimize`, `mujoco.viewer` (importa GLFW), `mujoco.usd` (exige `usd-core`) e `mujoco.sysid` não são carregados (✔ `hasattr(mujoco, 'rollout')` → `False`): `from mujoco import rollout, minimize`; `import mujoco.viewer`. Já estão no topo `MjVfs`, `Renderer`, `GLContext`, `mjtState` e toda a API C. MJX e MuJoCo Warp são pacotes à parte.

## 10. Snippets quebrados → correção (skills oficiais, python.rst, API removida)

| Onde | Snippet que FALHA em 3.15.0 | Erro | Correção ✔ |
| --- | --- | --- | --- |
| python/SKILL.md §2 | `data.bind(joint).set('qpos', 0.5)` | `AttributeError: no attribute 'set'` | `data.bind(joint).qpos = 0.5` |
| python/SKILL.md §2 | `data.actuator('motor').ctrl = 1.0` com `pid/dcmotor/orientation` | slot errado, sem erro | `data.ctrl[m.actuator_ctrladr[i] : +actuator_ctrlnum[i]]` ou `mjkit.Ctrl` |
| python/SKILL.md §2 | acessores `text`/`ten` em `MjModel`; `mesh`/`hfield`… em `MjData` | `AttributeError` | `m.tendon('x')`; texto em `m.text_data/text_adr` (§2) |
| spec_editing §4 | `spec.delete_body/geom/joint/actuator('x')` | `AttributeError` | `spec.delete(spec.body('x'))` |
| spec_editing §3 | `parent.attach(child, prefix='left_')` | `ValueError: One of frame or site must be specified` | `parent.attach(child, frame=fr, prefix=…)` ou `site=` |
| spec_editing §3 | `add_equality(type=CONNECT, name1=, name2=, anchor=[0,0,0])` | `TypeError` | `add_equality(type=…, objtype=mjOBJ_BODY, name1=, name2=, data=[ax,ay,az]+[0]*8)` (11 valores) |
| spec_editing §8 | `add_mesh(name=, vertex=, face=)` | `TypeError` | `add_mesh(name=, uservert=v.ravel(), userface=f.ravel())` |
| spec_editing §5 (aviso) | `set_to_motor()/set_to_position()` sem `trntype` | `ValueError: invalid transmission type` | `add_actuator(trntype=mjTRN_JOINT, target='junta')` antes |
| python.rst (VFS) | `MjSpec.from_string("model.xml", vfs=vfs)` | `ValueError: XML parse error` | `MjSpec.from_file("model.xml", vfs=vfs)` |
| removida | `data.qM`; `mj_fullM(m, dst, M)`; `spec.compiler.strippath` | `AttributeError` / `TypeError` | `data.M` (CSR: `m.M_rownnz/M_rowadr/M_colind`, `m.nM`, `m.nC`; simulation.rst «Data layout» ainda cita `qM`: obsoleto); `mj_fullM(m, d, dst)`; `spec.strippath = True` |
| depreciada | `from_xml_string(xml, assets={…})` | funciona, sem aviso | `MjVfs` (§1) |

## 11. Correções ao relatório do usuário (§4.1/4.2)

| # | Afirmação do relatório | Veredito | O que é verdade (✔ 3.15.0) |
| --- | --- | --- | --- |
| 1 | `MjModel` «imutável após a conversão»; `MjData` guarda `qpos, qvel, qacc, sensordata, ctrl` | **PARCIAL** | Só a **estrutura** é fixa (`m.nq = 99` → `AttributeError`); os reais são graváveis (`opt.timestep`, `body_mass`…; `mj_setConst`, §1). Em `MjData` o **estado** é `time+qpos+qvel+act` (`FULLPHYSICS`); `ctrl`, `qfrc/xfrc_applied`, `mocap_*` são **entradas**; `qacc`, `sensordata`, `xpos`, contatos são **saídas** derivadas |
| 2 | slices NumPy mapeiam memória C; referência sem cópia «vicia» resultados | **PARCIAL** | Mecanismo certo (views), risco mal descrito: **escrever** por slice/campo (`d.qpos[:] = x`, `d.joint('j').qpos = x`) é a forma correta de fixar o estado (depois `mj_forward`); o que vicia é **ler** sem `.copy()` (✔ todos os itens apontam para o último valor, §2). Derivados são sobrescritos no próximo step |
| 3 | `mj_name2id(…, "atuador_principal")` + `data.ctrl[id] = torque` | **PARCIAL** | Funciona, mas é o padrão desaconselhado: nome errado → `-1` → `ctrl[-1]` escreve no último atuador; com atuador multi-entrada `id ≠ slot`. Use `model.actuator(nome).id` (`KeyError`) + `actuator_ctrladr` |
| 4 | `viewer.sync()` em `launch_passive` + `time.sleep` | **PARCIAL** | É o padrão do python.rst, mas «will drift»: 0,51× (`sleep(timestep)`), 0,94× (`sleep(timestep−gasto)`), 1,00× (âncora no relógio de parede, §3) |
| 5 | `mj_step` invoca `mj_forward` | **CORRETA** | `mj_step = checkPos/Vel → mj_forward → checkAcc → integrador`; `mj_forward` **não integra**. Nuance: derivados pós-step ficam 1 passo atrás (§3) |
| 6 | callbacks `mjcb_control/sensor` em Python «induzem chamadas repetitivas ao GIL durante as quatro derivações do RK4», «paralisando o solver»; mitigação: ctypes | **PARCIAL** | Certo: GIL readquirido por chamada, `mjcb_control` 4×/step em RK4, ctypes não adquire o GIL. Exagero: «quatro» vale só para `mjcb_control` (`mjcb_sensor` 1×/passo); custo ≈ 0,6–0,9 µs/chamada (1,3–1,5× em 1 DoF, ruído no humanoide); o dano real é o multi-thread (4,8× vs 1,6× em 8 threads). Há mitigações mais simples (§7) |
| 7 | `mujoco.rollout` oferece paralelismo multithread em CPU | **CORRETA** | Com condições: `from mujoco import rollout`; **lista** de N `MjData` (tupla falha); resultados idênticos; 1,3–6,5× com 2–16 (§8) |

**Δ modelo do §4.2:** a `haste_articulada` penetra **5 cm** a `base_robotica` e, como o pai é corpo **estático** (sem juntas), não há filtro pai-filho (`overview.rst` «Surprising Collisions»): contato permanente (`dist=-0.05`) e junta travada (✔ |qpos| máx 0,006 rad em 20 s com ±15 N·m). A linha `<contact><exclude …/></contact>` abaixo resolve (✔ |qpos| chega a 2,2 rad). **Código corrigido** (✔ com stub sem janela; janela real, só a pedido do usuário: `import mujoco.viewer` + `simular_dinamica(mujoco.viewer.launch_passive)`; também testado com um `pid` antes do motor: `nu=3`, `slot=2` ≠ `id=1`):

```python
import time
import numpy as np
import mujoco

mjcf_xml = """<mujoco><option timestep="0.005" gravity="0 0 -9.81"/><worldbody><geom type="plane" size="3 3 0.1"/>
<body name="base_robotica" pos="0 0 0.5"><geom type="box" size="0.2 0.2 0.2"/>
<body name="haste_articulada" pos="0 0.2 0"><joint name="junta_motor" type="hinge" axis="0 1 0"/><geom type="cylinder" size="0.05 0.4" pos="0 0 0.4"/></body></body></worldbody>
<contact><exclude body1="base_robotica" body2="haste_articulada"/></contact>
<actuator><motor name="atuador_principal" joint="junta_motor" gear="1.0"/></actuator></mujoco>"""

def simular_dinamica(abrir_viewer, xml=mjcf_xml, nome="atuador_principal", max_catchup=50):
    modelo = mujoco.MjModel.from_xml_string(xml)
    dados = mujoco.MjData(modelo)
    i = modelo.actuator(nome).id                 # KeyError (e não -1) se o nome não existir
    slot = modelo.actuator_ctrladr[i]            # posição real em data.ctrl (≠ i com atuador multi-entrada)
    with abrir_viewer(modelo, dados) as viewer:
        wall0, sim0 = time.perf_counter(), dados.time           # âncora no relógio de parede
        while viewer.is_running():
            alvo = sim0 + (time.perf_counter() - wall0)
            n = 0
            while dados.time < alvo and n < max_catchup:        # recupera o atraso (no máx. max_catchup passos)
                dados.ctrl[slot] = 15.0 * np.sin(dados.time * 2.0 * np.pi)   # torque (N·m)
                mujoco.mj_step(modelo, dados)
                n += 1
            viewer.sync()
            time.sleep(0.001)
    return modelo, dados

class StubViewer:                                # contrato mínimo de launch_passive (sem janela)
    def __init__(self, wall=2.0): self.t0, self.wall = time.perf_counter(), wall
    def is_running(self): return time.perf_counter() - self.t0 < self.wall
    def sync(self, state_only=False): time.sleep(0.0015)         # custo simulado do sync
    def __enter__(self): return self
    def __exit__(self, *a): return False

t = time.perf_counter(); m, d = simular_dinamica(lambda m, d: StubViewer()); wall = time.perf_counter() - t
print(f"sim {d.time:.2f} s em {wall:.2f} s de parede = {d.time / wall:.3f}x | qpos = {d.qpos.round(3)}")
try: simular_dinamica(lambda m, d: StubViewer(0.1), nome="errado")
except KeyError as e: print("nome errado → KeyError:", str(e)[:60])
```

## Armadilhas

| Sintoma | Causa | Correção |
| --- | --- | --- |
| Atuador errado se mexe / `ctrl` com valores nos vizinhos | atuador multi-entrada (`nu ≠ nactuator`): acessor/`bind`/`ctrl[id]` | `actuator_ctrladr[i]` ou `mjkit.Ctrl` (§2) |
| Histórico com todos os valores iguais | views NumPy (`xpos`, `qpos`, fatias) | `.copy()` ao guardar |
| `sensordata`/`xpos` zerados ou 1 passo atrás | falta `mj_forward` (início, reset, keyframe, escrita de estado, após `mj_step`) | `mj_forward` antes de ler (§3) |
| `ctrl[-1]` mexe no último atuador | `mj_name2id` com nome errado devolve −1 | `model.actuator('x').id` (`KeyError`) |
| `AttributeError` em `bind(...).set`, `spec.delete_body`, `model.text` | skills oficiais desatualizadas | §10 |
| `ValueError: The mjSpec does not match mjData` | spec editado depois do `compile` | `model, data = spec.recompile(model, data)` |
| `'NoneType' has no attribute add_geom`; `compile()` falha após `add_*` inválido | `spec.body('typo')` devolve `None`; elemento residual | checar `None`; `spec.delete(spec.equalities[-1])` (§1) |
| Simulação «recomeça» sozinha (`time` cai) | `autoreset` após BADQACC/BADQPOS/BADQVEL | `d.warning.number.any()` e parar (§3) |
| Rollout congela (`time` parado) / `RuntimeError` / `ValueError` | qualquer aviso; tupla de `MjData`; lista em vez de `ndarray` | corrigir o aviso; `list` de `MjData` e `np.ndarray` (§8) |
| `mjd_transitionFD`: D com sinal oposto / `TypeError` / `FatalError` | bug do `flg_centered=True`; C e D trocados na docstring; RK4 | `flg_centered=False` p/ D; `C=(ns,2nv+na)`; outro integrador (§6) |
| Jacobiano zerado; `mj_ray` = −1 | derivados não calculados | `mj_forward` antes (§5, §6) |
| Callback vaza entre modelos / threads lentas | `set_mjcb_*` é global; GIL por chamada | `set_mjcb_x(None)` em `finally`; sem callback Python em multi-thread (§7) |
| `module 'mujoco' has no attribute 'rollout'` | `import mujoco` não carrega submódulos | `from mujoco import rollout, minimize` (§9) |
