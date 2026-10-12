# Telemetria e visualização — Rerun 0.38, forças de contato e alternativas leves
Registrar o estado de uma simulação MuJoCo no Rerun (`.rrd`), extrair forças de contato corretas no mundo, saber onde cada força vive em `mjData` e quando bastam `Renderer`/matplotlib.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: ficha `pesquisas/conhecimento/Q13.md`; `docs/upstream/mujoco/doc/{APIreference/functions.rst (mj_contactForce), programming/simulation.rst (Contacts, User inputs), programming/visualization.rst, XMLreference.rst (sensor/contact, geom/gap, visual), python.rst, computation/index.rst}`; `scripts/mjkit.py`; testes próprios com rerun-sdk 0.38.1 (venv descartável, Python 3.13) e o `.venv` do projeto. Legenda: ✔ = testado (executado e conferido); Δ doc = a doc/ficha diverge do medido; ⚠ = armadilha; «não verificado» = sem teste (diz como verificar).

## Quando ler este arquivo
- Vai gravar poses, forças e séries de uma simulação no Rerun (`.rrd`), ou decidir se isso compensa frente a vídeo + `mjkit.plot`.
- Precisa da força de contato **em coordenadas do mundo** (setas, somas, sensores) ou de saber onde estão gravidade, fluido e forças aplicadas.
- Achou código/tutorial de Rerun que falha (`set_time_seconds`, `rr.Scalar`, `rr.dataframe`…) ou vai revisar o §5.2 do relatório original.

## 1. Rerun 0.38.x — instalação e API atual
Não está no `.venv` do projeto (instalar é decisão do dono: `rerun-sdk` ≈ 264 MB + `pyarrow` ≈ 152 MB; exige numpy ≥ 2 e Python ≥ 3.10; ficha: 3.10 deprecado, a 0.39 exige 3.11). ✔ testado em venv à parte:
```bash
uv venv --python 3.13 venv-rerun && uv pip install --python venv-rerun/bin/python rerun-sdk mujoco numpy   # rerun-sdk 0.38.1
```
Assinaturas por `inspect.signature` (✔ 0.38.1; padrão `None` omitido nos kw opcionais):

| API | Assinatura | Notas |
|---|---|---|
| `rr.init` | `(application_id, *, recording_id=None, spawn=False, init_logging=True, default_enabled=True, strict=None, default_blueprint=None, send_properties=True)` | sem `init` nada é gravado, sem erro ✔; sem `save`/`spawn`/`connect_grpc` não há arquivo ✔. `strict` (padrão False; env `RERUN_STRICT`): uso errado vira só `RerunWarning` e o dado se perde ✔; `strict=True` levanta exceção |
| `rr.save` | `(path, default_blueprint=None, recording=None, *, write_footer=True)` | sink de arquivo. Δ doc/ficha («chame antes de logar»): ✔ logar ANTES do `save` não perde dados (buffer em RAM até haver sink); chame antes mesmo assim. `rr.disconnect()` fecha o arquivo (sem ele fecha ao sair ✔) |
| `rr.set_time` | `(timeline, *, recording=None, sequence=None, duration=None, timestamp=None)` | exatamente UM (senão `ValueError` ✔). Simulação: `duration=d.time` (s) → coluna `duration[ns]` ✔; por passo: `sequence=i` |
| `rr.log` | `(entity_path, entity, *extra, static=False, recording=None, strict=None)` | `static=True`: sem tempo (geometria, `ViewCoordinates`, `SeriesLines`, trajetória final) |
| `rr.send_columns` | `(entity_path, indexes, columns, *, recording=None, strict=None)` | colunar; exemplo e custo no §2 |
| `rr.Points3D` | `(positions, *, radii, colors, labels, show_labels, point_shading, class_ids, keypoint_ids)` | único com argumento posicional |
| `rr.Arrows3D` | `(*, vectors, origins=None, radii, colors, labels, show_labels, class_ids)` | TUDO kw-only (`TypeError` ✔); sem `origins` parte de (0,0,0) |
| `rr.Transform3D` | `(*, translation, rotation, rotation_axis_angle, quaternion, scale, mat3x3, from_parent, relation, child_frame, parent_frame)` | kw-only; cada `rr.log` REINICIA o transform (doc): logue translação+rotação juntas |
| `rr.Mesh3D` | `(*, vertex_positions, triangle_indices=None, vertex_normals, vertex_colors, vertex_texcoords, albedo_texture, albedo_factor, face_rendering, class_ids)` | aceita `mesh_vert` (float32) e `mesh_face` (int32) ✔ |
| `rr.Scalars` · `rr.SeriesLines` | `Scalars(scalars)` · `SeriesLines(*, colors, widths, names, visible_series, aggregation_policy, interpolation_mode)` | `Scalars` nunca `static` (o eixo X é o tempo); `SeriesLines` static dá nome/cor |

**Removido/mudado** (✔ erro na 0.38.1; removidos na 0.28, deprecados desde a 0.23 segundo a ficha):

| Antigo | Hoje |
|---|---|
| `rr.set_time_seconds/_secs/_nanos/_sequence` (`AttributeError`) | `rr.set_time(tl, duration=s)` · `sequence=n` · `timestamp=t` |
| `rr.Scalar` (singular) · `TimeSequenceColumn/TimeSecondsColumn/TimeNanosColumn` | `rr.Scalars` · `rr.TimeColumn(tl, sequence=/duration=/timestamp=)` (versão exata da remoção do `Scalar`: não verificada; ver os guias `rerun.io/docs/reference/migration`) |
| `rr.new_recording` · `rr.connect/connect_tcp/serve/serve_web/log_components` | `rr.RecordingStream(app_id)` · `rr.connect_grpc`, `rr.serve_grpc` + `rr.serve_web_viewer` |
| `Transform3D(axis_length=…)` (`TypeError`) · `from_parent=True` (`DeprecationWarning`) | `rr.TransformAxes3D(axis_length)` · `relation=rr.TransformRelation.ChildFromParent` |
| `rr.dataframe.load_recording`, `rerun.recording` (`ModuleNotFoundError`) | `rerun.chunk.RrdReader(path).stream().to_chunks()`; CLI `rerun rrd print/stats/verify` |

**Quaternion**: Rerun = `[x,y,z,w]`, MuJoCo = `[w,x,y,z]` (`xquat`, `geom_quat`) → `np.roll(q, -1)`. ✔ `quaternion=` aceita `rr.Quaternion(xyzw=…)`, lista ou ndarray, todos lidos como xyzw (identidade `[1,0,0,0]` → gravada `[0,0,0,1]`). ✔ `mat3x3=` aceita `d.xmat[b].reshape(3,3)` (e o vetor plano de 9) e grava column-major sem transpor (Rz(90°) → `[0,1,0,-1,0,0,0,0,1]`). Δ doc: o `Transform3D` se contradiz sobre a ordem `mat3x3`×`translation` («ordem inversa da listagem» vs «após a translação») → **não verificado** sem viewer (teste: um ponto em (0,0,0) sob `Transform3D(mat3x3=Rz90, translation=[1,0,0])` e veja onde cai); use `translation`+`quaternion` (p_pai = R·p + t).

## 2. Padrão mínimo: estado MuJoCo → `.rrd` (poses, trajetória, contatos, séries)
Entidades: `world/bodies/<corpo>` = `Transform3D` da pose do CORPO (`xpos`/`xquat`); geoms = filhos `static` com a pose local (`geom_pos`/`geom_quat`; ✔ `xpos∘geom_pos` reproduz `geom_xpos`/`geom_xmat`, erro ≤ 3e-16); `world/contact/{force,point}`; `world/traj/<corpo>`; `plots/<nome>`.
```python
import numpy as np, mujoco, rerun as rr

XML = """<mujoco><option timestep="0.002"/><worldbody>
  <geom name="chao" type="plane" size="2 2 .1"/>
  <body name="caixa" pos="0 0 .4"><freejoint/><geom type="box" size=".1 .1 .1" mass="1"/></body>
  <body name="bola" pos=".5 0 .6"><freejoint/><geom type="sphere" size=".08" mass=".5"/></body>
</worldbody></mujoco>"""
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m)
xyzw = lambda q: np.roll(q, -1)                        # MuJoCo [w x y z] -> Rerun [x y z w]
P = lambda b: f"world/bodies/{rr.escape_entity_path_part(m.body(b).name)}"   # escapa espaço, '/' e '.'

rr.init("mujoco_lab", spawn=False, strict=True)        # spawn=False: sem viewer; strict: uso errado vira exceção
rr.save("run.rrd")                                      # sink de arquivo
rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)              # MuJoCo é Z para cima
rr.log("plots/fz", rr.SeriesLines(colors=[255, 160, 60], names="Fz total (N)", widths=2), static=True)
for g in range(m.ngeom):                               # geometria UMA vez (static), no frame do corpo
    s, t = m.geom_size[g], m.geom_type[g]
    if t == mujoco.mjtGeom.mjGEOM_BOX: shape = rr.Boxes3D(half_sizes=[s])                # size = meios-lados
    elif t == mujoco.mjtGeom.mjGEOM_SPHERE: shape = rr.Ellipsoids3D(half_sizes=[[s[0]] * 3])
    else: continue                                     # plano, cilindro, malha...: ver tabela
    rr.log(f"{P(m.geom_bodyid[g])}/geom{g}", shape, rr.Transform3D(translation=m.geom_pos[g], quaternion=xyzw(m.geom_quat[g])), static=True)

traj, f6 = [], np.zeros(6)
for _ in range(1500):                                  # 3 s simulados
    mujoco.mj_step(m, d)
    mujoco.mj_forward(m, d)                            # xpos/contatos/forças voltam a valer em d.time (senão: 1 passo atrás)
    rr.set_time("sim_time", duration=d.time)           # timeline em segundos simulados
    for b in range(1, m.nbody):                        # poses: um Transform3D por corpo
        rr.log(P(b), rr.Transform3D(translation=d.xpos[b], quaternion=xyzw(d.xquat[b])))
    traj.append(d.xpos[1].copy())
    act = np.flatnonzero(d.contact.efc_address >= 0)   # só contatos ativos
    if act.size:
        F = np.zeros((act.size, 3))
        for k, i in enumerate(act):
            mujoco.mj_contactForce(m, d, i, f6)                      # 6D no FRAME DO CONTATO
            F[k] = d.contact[i].frame.reshape(3, 3).T @ f6[:3]       # -> mundo (força de geom[0] SOBRE geom[1])
        rr.log("world/contact/force", rr.Arrows3D(origins=d.contact.pos[act], vectors=0.05 * F))    # 0,05 m/N
        rr.log("world/contact/point", rr.Points3D(d.contact.pos[act], radii=0.004))
        rr.log("plots/fz", rr.Scalars(F[:, 2].sum()))
    else:
        rr.log("world/contact", rr.Clear.recursive())      # sem contato ativo: apaga setas/pontos antigos (latest-at)
        rr.log("plots/fz", rr.Scalars(0.0))
rr.log("world/traj/caixa", rr.LineStrips3D([np.array(traj)], radii=0.002), static=True)    # trajetória inteira, 1 vez
rr.disconnect()                                         # fecha o .rrd
```
✔ (venv rerun, `strict=True`): 1500 passos → `run.rrd` 338 KB, 11 entity paths (10 + `/__properties`), timelines `sim_time` (`duration[ns]`) + `log_time` (relógio de parede); 1º contato em t = 0,248 s; no fim Fz = 14,715 N = (1+0,5)·g e setas de 0,1226 m (caixa) e 0,2453 m (bola) = 0,05·f. Posições/vetores ficam float32 no arquivo, `Scalars` float64. Grave `.rrd` em `experiments/NN/out/` (ignorado pelo git). O viewer (`rerun run.rrd`; ao vivo: `spawn=True` ou `rr.serve_grpc()` + `rr.serve_web_viewer()`) **não foi aberto**: aspecto visual, composição de transforms, `Clear` e escolha da timeline `sim_time` no painel de tempo: não verificados.

Ler de volta sem viewer (✔; os chunks variam entre execuções) — e a CLI `venv-rerun/bin/rerun rrd verify run.rrd` (também `stats`, `print`):
```python
import rerun.chunk as ch                               # rerun.dataframe / rerun.recording não existem mais
for c in ch.RrdReader("run.rrd").stream().to_chunks():
    if c.entity_path in ("/world/bodies/caixa", "/plots/fz") and not c.is_static:
        rb = c.to_record_batch(); col = rb.schema.names[-1]    # pyarrow.RecordBatch: timelines + componentes
        print(c.entity_path, c.num_rows, rb.schema.field("sim_time").type, rb.column("sim_time")[-1], col, rb.column(col)[-1].as_py())
```
| geom MuJoCo | Rerun (sob o caminho do corpo, `static`, + `Transform3D(geom_pos, geom_quat)`) | estado |
|---|---|---|
| `box` (size = meios-lados) · `sphere` | `Boxes3D(half_sizes=[size])` · `Ellipsoids3D(half_sizes=[[r,r,r]])` | ✔ |
| `cylinder` (size = [raio, meio-comp.]) | `Cylinders3D(lengths=[2*size[1]], radii=[size[0]])` (centrado) | chamada ✔; visual não verificado |
| `capsule` | `Capsules3D(lengths=[2*size[1]], radii=[size[0]], translations=[[0,0,-size[1]]])` (doc: uma ponta na origem) | chamada ✔; `lengths` não verificado |
| `mesh` | `Mesh3D(vertex_positions=m.mesh_vert[v0:v0+nv], triangle_indices=m.mesh_face[f0:f0+nf])`, `k=geom_dataid`, `v0,nv=mesh_vertadr/vertnum[k]`, `f0,nf=mesh_faceadr/facenum[k]` | ✔ faces com índices LOCAIS (2ª malha: `face.max=7`, `vertadr=4`); malha recentrada (`mesh_pos`≠0) ⇒ posicione pelo geom: `geom_xpos + geom_xmat@v` reproduziu o cubo em (3..4, 0..1, 1..2) |

**Custo** ✔ (cena mínima, 5000 passos): `mj_step` 4,5 µs; `+ mj_forward` 8,8 µs; `rr.log` ≈ 56 µs/chamada (2 por passo = 0,56 s) — o log domina: decime (30–100 Hz) ou use colunas: `rr.send_columns("world/bodies/caixa", indexes=[rr.TimeColumn("sim_time", duration=T)], columns=rr.Transform3D.columns(translation=POS, quaternion=QUAT))` (T `(N,)`, POS `(N,3)`, QUAT `(N,4)` xyzw): 10 000 linhas em 3,9 ms e 280 KiB (vs 389 KiB). `rr.Scalars.columns(scalars=S)` aceita `(N,)` ou `(N,3)`; nº VARIÁVEL por instante (contatos): `rr.Arrows3D.columns(vectors=V, origins=O).partition(lengths=ncon)` ✔ (`ncon=[0,4,4,5]` ⇒ linhas com 0, 4, 4 e 5 setas).

## 3. Forças de contato: `mj_contactForce`, `frame`, sinal, inativos, sensor
| Tema | Fato (✔ testado em 3.15.0) |
|---|---|
| Resultado | `mj_contactForce(m, d, i, f6)` com `f6` float64[6] gravável: força 3D + torque 3D NO FRAME DO CONTATO — `[Fn, Ft1, Ft2, Tn(torção), Tr1, Tr2]`. `condim` 1/3 ⇒ torque 0; ✔ bola girando (ωz = 5): `f6[3]` = −0,0075 (condim 4) / −0,0084 N·m (condim 6), oposto ao spin; bola rolando em +x (condim 6): só `f6[4]` ≠ 0 (−1,15 N·m, em torno de t1 = y). Unidades SI (N, N·m) |
| `contact[i].frame` | 9 números em coordenadas do MUNDO, matriz TRANSPOSTA: `reshape(3,3)` tem os eixos nas LINHAS (normal = 1ª linha `frame[0:3]`, depois t1, t2; ✔ ortonormal, det = +1) |
| Para o mundo | `f_w = frame.reshape(3,3).T @ f6[:3]` (torque: `f6[3:]`); vetorizado `np.einsum('nji,nj->ni', d.contact.frame.reshape(-1,3,3), F6[:, :3])`. ✔ caixa 1 kg, 4 contatos, cone piramidal e elíptico: Σ f_w = (0, 0, 9,81) N (2,4525 N cada). Cone piramidal: `efc_force` cru = forças em arestas redundantes e não ortogonais (✔ `nefc=16`, 0,613 cada) — use sempre `mj_contactForce` |
| Sinal | a normal vai de `geom[0]` a `geom[1]`; `f_w` = força de geom[0] SOBRE geom[1]; sobre geom[0] vale `−f_w`. A ordem não é fixa (plano antes de caixa; mesmo tipo: menor id): leia `contact[i].geom`. ✔ 2 ordens de declaração: `geom=(gA,gB)` ⇒ +9,81; `(gB,gA)` com normal (0,0,−1) ⇒ −9,81 |
| `ncon` | campo de `MjData`; `len(d.contact) == d.ncon` ✔ (4 = 4); vetorizados `.frame` (ncon,9), `.pos` (ncon,3), `.geom` (ncon,2), `.efc_address` (ncon,); tamanho e ordem mudam a cada passo |
| Inativos | detectados mas sem força: `efc_address == -1` (`exclude != 0`, p.ex. zona `gap`); `mj_contactForce` devolve zeros. ✔ margin 0,05, gap 0,05, dist 0,07: `exclude=1, efc_address=-1, nefc=0`. Filtre `d.contact.efc_address >= 0` |
```python
import numpy as np, mujoco
XML = """<mujoco><worldbody><geom name="chao" type="plane" size="5 5 .1"/>
  <body name="A" pos="0 0 .1"><freejoint/><geom name="gA" type="box" size=".1 .1 .1" mass="2"/></body>
  <body name="B" pos="0 0 .31"><freejoint/><geom name="gB" type="box" size=".1 .1 .1" mass="1"/></body></worldbody></mujoco>"""
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m)
for _ in range(2500): mujoco.mj_step(m, d)
mujoco.mj_forward(m, d); mujoco.mj_rnePostConstraint(m, d)       # derivadas em d.time; cfrc_ext p/ conferir
net, f6 = {1: np.zeros(3), 2: np.zeros(3)}, np.zeros(6)           # força de contato sobre os corpos A=1, B=2
for i in np.flatnonzero(d.contact.efc_address >= 0):             # ativos (efc_address >= 0)
    mujoco.mj_contactForce(m, d, i, f6)                           # 6D no frame do contato
    fw = d.contact[i].frame.reshape(3, 3).T @ f6[:3]              # mundo: força de geom[0] SOBRE geom[1]
    g0, g1 = (m.geom_bodyid[g] for g in d.contact[i].geom)
    if g1 in net: net[g1] += fw
    if g0 in net: net[g0] -= fw                                   # sobre o corpo de geom[0]: sinal oposto
print("ncon", d.ncon, "len", len(d.contact))
for b in net: print(m.body(b).name, "contatos:", net[b].round(3), "| cfrc_ext[3:6]:", d.cfrc_ext[b][3:6].round(3))
```
✔ saída: `ncon 8 len 8`; A = (0, 0, 19,62) N (chão +29,43 − B 9,81) e B = (0, 0, 9,81) N, iguais a `cfrc_ext[b][3:6]` (`cfrc_ext` é `[rot:lin]`).

**Sensor declarativo** (`XMLreference.rst` §sensor/contact): tamanho FIXO em `sensordata`; ignora contatos filtrados/sem força. `netforce` dá a força líquida no frame GLOBAL (as outras reduções, no frame do contato) e o sentido segue a ordem 1→2: ✔ `geom1="chao"` ⇒ (0,0,+9,81); `body1="caixa" body2="world"` ⇒ (0,0,−9,81); `found` = 4 (contatos casados); `data="found force torque"` = 7 números (saída do bloco ✔: `[4. 0. 0. 9.81 0. 0. 0.]`). No Rerun: `rr.log("plots/net", rr.Scalars(d.sensor("net").data[1:4]))` + `SeriesLines(names=["Fx","Fy","Fz"])` static (3 escalares por instante, constante).
```python
import numpy as np, mujoco
XML = """<mujoco><worldbody><geom name="chao" type="plane" size="5 5 .1"/>
  <body name="caixa" pos="0 0 .1"><freejoint/><geom name="gc" type="box" size=".1 .1 .1" mass="1"/></body></worldbody>
  <sensor><contact name="net" geom1="chao" geom2="gc" data="found force torque" reduce="netforce"/></sensor></mujoco>"""
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m)
for _ in range(1500): mujoco.mj_step(m, d)
mujoco.mj_forward(m, d)
print(d.sensor("net").data.round(3) + 0.0)       # [found Fx Fy Fz Tx Ty Tz], frame global (+ 0.0 apaga o −0)
```

## 4. Onde estão as forças (`M·qacc + qfrc_bias = qfrc_passive + qfrc_actuator + qfrc_applied + Jᵀ·efc_force`)
| Força | Campo | ✔ / nota |
|---|---|---|
| Gravidade, Coriolis, centrífuga | `qfrc_bias` = c(q,v), no lado ESQUERDO: a força gravitacional é −c | corpo livre 1 kg: `qfrc_bias[2]` = +9,81; `qfrc_passive` = `qfrc_applied` = `qfrc_actuator` = `qfrc_gravcomp` = 0 |
| Molas/amortecedores, gravcomp, fluido, `mjcb_passive` | `qfrc_spring`, `qfrc_damper`, `qfrc_gravcomp`, `qfrc_fluid` somam em `qfrc_passive` (atuadores: `qfrc_actuator`) | ✔ soma exata (mola, amortecimento, `gravcomp` 0,5, fluido): −2,38429 −0,40000 −0,85434 −0,00138 = −3,64001 = `qfrc_passive`; fluido isolado (`option density/viscosity` > 0, v = 10 m/s): `qfrc_fluid[0]` = `qfrc_passive[0]` = −1,44026 |
| Do usuário (aerodinâmica própria, perturbação) | `qfrc_applied` (nv) e `xfrc_applied` (nbody×6 = `[F(3), τ(3)]`, mundo, no CoM) | ENTRADAS: o simulador nunca as escreve nem zera ⇒ persistem ✔ (após 3 passos `xfrc_applied[1,0]`=2 e `qfrc_applied[2]`=3 intactos); escreva ANTES de `mj_step`. Seta no Rerun ✔: `rr.Arrows3D(origins=d.xipos[b], vectors=k*d.xfrc_applied[b,:3])` (hover: (0,0,9,81) em 1 kg ⇒ `qacc_z`=0) |
| Contato, limites, equality | `efc_force` (espaço de restrição), `qfrc_constraint` (juntas), `cfrc_ext` (`[rot:lin]`, só após `mj_rnePostConstraint`) | `cfrc_ext` inclui `xfrc_applied` e contatos, NÃO fluido/gravcomp (doc `functions.rst` §mj_rnePostConstraint) |

Atraso de 1 passo ✔ (doc «outdated by one time step», `programming/simulation.rst`): após `mj_step`, `qpos`/`time` estão em t+dt mas `xpos`, contatos e `qfrc_*` são do INÍCIO do passo (dt = 0,01: `qpos_z` = 4,999019, `xpos_z` = 5,000000; após `mj_forward`, 4,999019; `qfrc_passive` guardado −1,44026 vs recomputado −1,43612). Corrija com `mj_forward` antes de logar ou carimbe as derivadas com `d.time − m.opt.timestep`.

## 5. Alternativas leves (sem Rerun)
| Necessidade | Ferramenta |
|---|---|
| Contato no vídeo/imagem | flags `mjVIS_CONTACTPOINT`, `CONTACTFORCE`, `CONTACTSPLIT`, `PERTFORCE` (TODAS desligadas por padrão ✔); `mjkit.record(..., contacts=True)` liga POINT+FORCE; janela: `viewer.opt.flags[...] = 1` dentro de `with viewer.lock()` (`python.rst` §launch_passive; não testado, sem janela) |
| Série temporal / relatório | `mjkit.plot(res["log"], [...], "out/x.png")` (matplotlib Agg ✔; bloco `mjkit` abaixo) |
| Vários instantes na mesma imagem | `mujoco.mjv_addGeoms(m, d, opt, mujoco.MjvPerturb(), mujoco.mjtCatBit.mjCAT_DYNAMIC.value + mujoco.mjtCatBit.mjCAT_DECOR.value, scn)` sobre uma cena base (`programming/visualization.rst` §Scene update); ✔ 6→11 geoms e 4→8 setas; `pert=None` dá `TypeError` |
| Entrada de tamanho fixo (RL, lógica) | sensor `<contact>` (§3) |
```python
import os; os.environ.setdefault("MUJOCO_GL", "egl")      # offscreen, sem janela
import mujoco
m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><geom type="plane" size="2 2 .1"/><body pos="0 0 .1"><freejoint/><geom type="box" size=".1 .1 .1" mass="1"/></body></worldbody></mujoco>')
d = mujoco.MjData(m)
for _ in range(1000): mujoco.mj_step(m, d)
mujoco.mj_forward(m, d)
m.vis.map.force = 0.1                      # seta = |f|·map.force/stat.meanmass (padrão 0.005 -> 1,2 cm para 2,45 N)
opt = mujoco.MjvOption()                   # as flags de contato começam TODAS desligadas
for f in (mujoco.mjtVisFlag.mjVIS_CONTACTPOINT, mujoco.mjtVisFlag.mjVIS_CONTACTFORCE): opt.flags[f] = True   # + mjVIS_CONTACTSPLIT
with mujoco.Renderer(m, height=480, width=640) as r:
    r.update_scene(d, scene_option=opt)    # camera=... opcional
    img = r.render().copy()                # .copy(): render() devolve um buffer reutilizado
    n = {t: sum(g.type == t for g in r.scene.geoms[:r.scene.ngeom]) for t in (mujoco.mjtGeom.mjGEOM_ARROW, mujoco.mjtGeom.mjGEOM_CYLINDER)}
print(img.shape, "ncon", d.ncon, "| setas:", n[mujoco.mjtGeom.mjGEOM_ARROW], "cilindros (pontos):", n[mujoco.mjtGeom.mjGEOM_CYLINDER])
```
✔ 4 contatos: POINT ⇒ 4 cilindros; FORCE ⇒ 4 setas; +SPLIT ⇒ 8 setas (via `mjv_updateScene` sem GL). Comprimento da seta = |f|·`vis.map.force`/`stat.meanmass`: 0,0123 m (padrão 0,005), 0,2453 m (0,1), 1,2263 m (0,5) para 2,4525 N e meanmass 1; largura `vis.scale.forcewidth` (0,1 ✔), cor `vis.rgba.contactforce` (doc).
Com o `mjkit` do laboratório: ⚠ `probes`, `on_step` e `log["ncon"]/pe/ke` do `mjkit.record` rodam APÓS `mj_step` ⇒ contatos 1 passo atrasados (✔ pico de Fz de 273,125 N em t = 0,250 s; com `mj_forward` dentro do probe, em 0,248 s; a ordem dos probes importa).
```python
from lab import mjkit                      # lab/mjkit.py da raiz do projeto (rode com PYTHONPATH=<raiz>); importe ANTES de `mujoco`
import numpy as np, mujoco
model, data = mjkit.load('<mujoco><worldbody><geom type="plane" size="2 2 .1"/><body pos="0 0 .4"><freejoint/><geom type="box" size=".1 .1 .1" mass="1"/></body></worldbody></mujoco>')
f6 = np.zeros(6)
def fz(m, d):                              # probe: roda APÓS mj_step => mj_forward p/ coerência com d.time
    mujoco.mj_forward(m, d); s = 0.0
    for i in np.flatnonzero(d.contact.efc_address >= 0):
        mujoco.mj_contactForce(m, d, i, f6); s += (d.contact[i].frame.reshape(3, 3).T @ f6[:3])[2]
    return s
res = mjkit.record(model, data, None, duration=1.0, probes={"fz": fz})      # + contacts=True, mp4=..., sheet=... p/ vídeo com setas
mjkit.plot(res["log"], ["fz", "ncon"], "out/fz.png", "Fz de contato")      # refs={"m·g": 9.81} é desenhado em TODOS os painéis
print(res["log"]["fz"].max().round(3), res["log"]["fz"][-1].round(3), res["log"]["ncon"][-1])   # 273.125 9.81 4
```

## 6. Existe exemplo oficial MuJoCo + Rerun?
Não (evidência por ausência, ficha Q13 [F22–F25]): nem `examples/python` do rerun-io/rerun (92 diretórios) nem a galeria têm MuJoCo/MJCF (o robótico mais próximo é URDF); a doc do MuJoCo 3.15 não cita o Rerun; a issue rerun-io/rerun#8634 «Support for MJCF Files» (2025-01-09, pede loader de referência) seguia aberta na pesquisa. ✔ local: 0 ocorrências de `mujoco`/`mjcf` nos textos do `rerun-sdk` 0.38.1 instalado. Só há o loader de terceiros `Reimagine-Robotics/rerun-loader-mjcf` (**nível C**, não oficial; `MJCFLogger`/`MJCFRecorder`, carimba `duration=data.time`): compatibilidade com MuJoCo 3.15 + rerun 0.38.1 **não testada** (instale num venv à parte e compare com o §2). O padrão do §2 é código do laboratório, não receita oficial.

## Correções ao relatório do usuário (§5.2)
| # | Afirmação do relatório | Veredito | Correção |
|---|---|---|---|
| 1 | Rerun = data logger colunar em Rust com suporte Python imediato | **CORRETA** (com ressalvas) | Armazenamento em chunks Arrow/colunar, núcleo Rust, `pip install rerun-sdk` (0.38.1) já traz o viewer. Ressalvas: hoje o projeto se descreve como «data layer for physical AI»; `rr.log` é orientado a linhas, o colunar é `rr.send_columns`/o armazenamento |
| 2 | `rr.log` a cada transição, entidades `drone/aerodinamica`, `rr.Points3D`/`rr.Arrows3D` | **PARCIAL** | Nomes atuais; `rr.log("drone/aerodinamica", Points3D/Arrows3D(vectors=…))` roda em `strict=True` ✔, mas sem `set_time` o `.rrd` só tem `log_time` ✔. Faltam `rr.set_time("sim_time", duration=d.time)`, `vectors=` por palavra-chave, `mj_forward` antes de logar (1 passo de atraso), poses via `Transform3D` + quaternion xyzw, `send_columns` p/ histórico longo. `/` em `application_id` vira «requires migration» (WARN) ✔ |
| 3 | `data.contact` expõe `ncon`; `mj_contactForce` extrai a força no referencial do mundo | **PARCIAL** | `ncon` é de `MjData` (`len(d.contact) == d.ncon` ✔). Assinatura `(m, d, i, f6[6])` certa, mas o resultado está no FRAME DO CONTATO: mundo = `frame.reshape(3,3).T @ f6[:3]` (geom[0] sobre geom[1]); filtre `efc_address < 0` |
| 4 | Forças aerodinâmicas/gravitacionais acumuladas em `qfrc_passive` e `qfrc_applied` | **PARCIAL** | Gravidade está em `qfrc_bias` (✔ +9,81 com passive = applied = 0). `qfrc_passive` é recalculado a cada avaliação (não acumula; fluido próprio em `qfrc_fluid`); `qfrc_applied`/`xfrc_applied` são entradas que persistem — a aerodinâmica só aparece lá se VOCÊ a escrever antes de `mj_step` |

## Armadilhas
| Sintoma | Causa | Correção |
|---|---|---|
| Fz/pose 1 passo atrasados (pico em t = 0,250 em vez de 0,248) | `mj_step` deixa `xpos`, contatos e `qfrc_*` no início do passo (também nos `probes` do `mjkit.record`) | `mj_forward` antes de logar/no probe, ou carimbe `d.time − m.opt.timestep` |
| `AttributeError: … 'set_time_seconds'/'Scalar'/'new_recording'`; `No module named 'rerun.dataframe'` | código/tutorial pré-0.28 | tabela de removidos (§1) |
| `TypeError: Arrows3DExt.__init__() takes 1 positional argument` | `Arrows3D`/`Transform3D` são kw-only | `Arrows3D(origins=…, vectors=…)` |
| Dado não aparece e só há `RerunWarning` (ex.: `translation=[1,2]`) ✔ | `strict` padrão = False: argumento inválido vira warning e o log é descartado | `rr.init(..., strict=True)` ou `RERUN_STRICT=1` ao desenvolver |
| Série sem tempo de simulação | faltou `rr.set_time` (só `log_time`); `Scalars` com `static=True` não dá erro ✔, mas a doc o proíbe (o eixo X é o tempo) | `rr.set_time("sim_time", duration=d.time)` a cada amostra |
| WARN «Timeline … changed type» (sem exceção) e, com `Transform3D` no meio, ERROR «Invalid chunk» ao fechar: `.rrd` sem footer, `rerun rrd verify` falha ✔ | `duration`/`sequence`/`timestamp` misturados na MESMA timeline | um tipo por nome (`sim_time` = duration; `step` = sequence) |
| WARN «Unescaped whitespace»; «Application ID requires migration» ✔ (`drone/aerodinamica` → `drone-aerodinamicaa98a`) | espaço, `/` ou `.` em nome de corpo; `/` em `application_id` | `rr.escape_entity_path_part(nome)`; `application_id` simples (`mujoco_lab`) |
| `.rrd` inexistente ✔ | nenhum sink (`save`/`spawn`/`connect_grpc`): o buffer é descartado | `rr.save(...)`; `rr.disconnect()` antes de ler no mesmo processo |
| Seta espelhada/torta; sinal invertido entre dois corpos | `f6[:3]` cru, ou `frame.reshape(3,3) @ f` sem `.T`; a ordem geom[0]/geom[1] varia | `frame.reshape(3,3).T @ f6[:3]`; leia `contact[i].geom`; sobre geom[0] = `−f_w` |
| Forças «fantasmas» ou antes do toque | contato inativo (`efc_address = -1`) ou `margin` > dist (✔ margin 0,2, dist 0,07 ⇒ 334 N) | filtre `efc_address >= 0`; revise `margin`/`gap` |
| `mjVIS_CONTACTFORCE` ligado e nada aparece | `vis.map.force` = 0,005 ⇒ seta de 1,2 cm para 2,45 N | `m.vis.map.force = 0.1` (ou `<visual><map force="0.1"/>`) |
| Gravidade «sumiu» de `qfrc_passive`/`qfrc_applied` | está em `qfrc_bias` (força = −c) | leia `qfrc_bias`; `qfrc_passive` = molas, amortecedores, gravcomp, fluido |
| Aerodinâmica própria «gruda» ou acumula; torque no campo errado | `xfrc_applied`/`qfrc_applied` persistem; `xfrc_applied` = `[F, τ]` mas `cfrc_ext`/`cvel`/`cacc` = `[τ, F]` | sobrescreva a cada passo antes de `mj_step` (zere os corpos sem uso) |
| `rr.log` domina o tempo (56 µs/chamada vs `mj_step` 4,5 µs) | log por passo a 500 Hz+ | decimar, ou `rr.send_columns` (3,9 ms para 10 000 linhas) |
| `rr.disable_timeline("log_time")` não remove o relógio de parede ✔ | só limpa timeline definida pelo usuário | `rr.get_global_data_recording().set_log_time_enabled(False)` (✔ −17 % de tamanho; fica só `sim_time`) |
