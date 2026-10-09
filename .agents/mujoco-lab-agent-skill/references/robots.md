# Robôs no MuJoCo 3.15 — modelos prontos, URDF/malhas, controle e ecossistema de RL

Escopo: onde obter robôs (Menagerie e demais), importar URDF/CAD para MJCF, controlar manipuladores (PD, gravidade, IK, espaço operacional) e escolher framework de RL/MPC. Pernas e mãos: só ponteiros.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: fichas `pesquisas/conhecimento/{Q10,Q12,Q7}.md`; `docs/upstream/mujoco/doc/{XMLreference,modeling,overview,changelog}.rst` e `programming/{modeledit,simulation}.rst`; espelhos `docs/upstream/{mujoco_menagerie,mujoco_playground,mujoco_mpc}`; `uv.lock`; template `assets/templates/arm`; testes próprios (venv descartável com urdf2mjcf 0.2.39, trimesh 5.1.1, robot_descriptions 3.2.0, mujoco-menagerie 2026.10.1; e `.venv` do projeto, mujoco 3.15.0).

## Quando ler este arquivo
- Precisa de um robô pronto (braço, quadrúpede, humanoide, mão) ou de escolher entre Menagerie, robot_descriptions, Playground, dm_control, Gymnasium, MJPC, Brax e mjlab.
- Vai importar URDF, malhas (STL/OBJ/DAE) ou CAD, ou avaliar `urdf2mjcf`, obj2mjcf e CoACD.
- Vai controlar um braço: servo `position` (PD), gravidade, IK por Jacobiano, torque computado/espaço operacional, limites.
- Legenda: `✔ testado` (✔ nas tabelas) = executado aqui; `(espelho)`/`(lock)` = lido ou contado nos arquivos locais; `ficha` e células sem marca = só lido (ficha/doc), **não** executado. Atuadores/sensores: `actuators-sensors.md`; GPU: `gpu-mjx-warp.md`; drones: `drones.md`; veículos (a Menagerie não tem): `vehicles.md`.

## 1. Onde obter modelos e frameworks

### 1.1 MuJoCo Menagerie (fonte principal de modelos prontos)
| Item | Fato |
|---|---|
| Acervo | 71 entradas em 69 pastas, 11 categorias: Arms 25 · Humanoids 11 · End-effectors 11 · Quadrupeds 8 · Mobile Manipulators 7 · Biomechanical 3 · **Drones 2 (só Skydio X2 e Crazyflie 2)** · Bipeds 1 (Cassie) · Dual Arms 1 (ALOHA) · Mobile Bases 1 · Misc 1. **Sem categoria de veículos** (`mm.robots("vehicle") == []`) ✔ |
| Licença **por modelo** | cada pasta tem `LICENSE`; só o resto do repositório é Apache-2.0. Por pasta: Apache-2.0 30 · BSD-3-Clause 22 · MIT 13 · BSD-2-Clause 3 (Robotiq 2F-85 e v4, Allegro) · BSD-3-Clause-Clear 1 (Stretch 2); nenhum `LICENSE` copyleft/NC ✔. `mm.get(nome).license` dá a do modelo. Termos das malhas de terceiros: não verificado — leia o `LICENSE` da pasta antes de uso comercial |
| Obter | `pip install mujoco-menagerie` (2026.10.1; Python ≥3.10.12) · `uvx mujoco-menagerie view <nome>` · `git clone https://github.com/google-deepmind/mujoco_menagerie`. Cache `~/.cache/mujoco_menagerie` (`MENAGERIE_CACHE_DIR`; `MENAGERIE_ROOT` aponta um checkout). API: `docs/upstream/mujoco_menagerie/python/DOC.md` |
| Layout | `<robô>.xml` (só o robô) · `scene.xml` (inclui o robô + chão/luz; é o que `mm.load` compila) · `*_mjx.xml` (variante MJX; nem todos) · `assets/` · `LICENSE` · `README.md` (passos de como o MJCF foi gerado). Keyframe `home` em 40 pastas (`mujoco.mj_resetDataKeyframe(m, d, m.key("home").id)` ✔); site `attachment_site` (acoplar garra) em 10, quase todas braços (`FAQ.md`) ✔ |
| Versão mínima | cada README declara "Requires MuJoCo X or later" (de 2.2.2 a 3.3.0; 4 pastas sem declaração) ✔. Ficha: 96/99 `scene*.xml` e 21/21 `*mjx*.xml` compilam no 3.15.0 (malhas sintéticas; nenhuma falha de esquema) |
| ⚠ `dampratio` 3.15 | cálculo mudou (breaking, `changelog.rst` 3.15.0 #3); 11 pastas o usam: dynamixel_2r, pal_talos, pal_tiago, pal_tiago_dual, robot_soccer_kit, robotis_omy_3m, sharpa_wave, trossen_wx250s, trs_so_arm100, umi_gripper, unitree_g1 ✔ (grep). Em cadeias multi-elo o amortecimento fica MENOR que no 3.14 (§3.1) |
| Qualidade | notas A+/A/B/C ainda não aplicadas (README): "estável" ≠ "identificado". PD típico (UR5e): `<general gaintype="fixed" biastype="affine" gainprm="2000" biasprm="0 -2000 -400" forcerange="-150 150"/>` + `armature="0.1"` + `integrator="implicitfast"` |

```python
import mujoco_menagerie as mm              # venv com `pip install mujoco-menagerie`; as 3 linhas abaixo NÃO baixam nada
r = mm.get("franka_emika_panda")
print(len(mm.names()), r.display_name, r.license, r.default_scene, [len(mm.robots(c)) for c in ("arm", "drone", "vehicle")])
# → 69 Franka Emika Panda Apache-2.0 scene [25, 2, 0]
# model = mm.load("unitree_go2")           # baixa 1× p/ o cache e compila scene.xml; mm.get(n).spec() = MjSpec editável — NÃO testado (exige rede)
```

### 1.2 Ecossistema (estado em 2026-10-07; requisitos do Playground re-lidos no espelho em 2026-10-08)
| Pacote | Versão (data) | Python | Com MuJoCo 3.15.0 | Status e notas |
|---|---|---|---|---|
| `mujoco-menagerie` | 2026.10.1 (07/10/26) | ≥3.10.12 | ✔ instala junto do 3.15.0 | ativo; §1.1 |
| `robot_descriptions` (terceiros) | 3.2.0 (12/09/26) | ≥3.10 | ✔ importa; **fixa Menagerie `feadf76` (18/03/26)** — o pacote acima usa `0059d43` (07/10/26) | 192 descrições, 60 MJCF (49 da Menagerie); clona por git em `~/.cache/robot_descriptions` (rede; não testado). Modelos defasados: prefira `mujoco-menagerie` |
| `dm_control` | 1.0.48 (05/10/26) | ≥3.9 — **use 3.12**: `labmaze` 1.0.6 só tem wheels cp312 (`uv.lock`) | exige `mujoco>=3.15.0` (ficha) | ativo; Suite, PyMJCF, locomotion. ⚠ `uv sync --group rl` no `.venv` 3.13 tende a falhar no labmaze (não testado) |
| `gymnasium[mujoco]` | 1.4.0 (05/10/26) | ≥3.10 (3.13 desde a 1.2.0) | extra `mujoco>=2.1.5` sem teto (ficha; não testado) | 11 envs (Ant, HalfCheetah, Hopper, Humanoid, HumanoidStandup, InvertedDoublePendulum, InvertedPendulum, Pusher, Reacher, Swimmer, Walker2d); **use `v5`**; `v4` só p/ reproduzir; v2/v3 foram p/ gymnasium-robotics |
| `playground` | 0.2.0 (16/03/26; `main` ativo) | **≥3.11** (`pyproject.toml:12`); o README diz "Requires Python 3.10 or later" (`README.md:35`) — o `--python 3.12` do quickstart (`README.md:39`) é **sugestão de venv, não requisito** | `mujoco>=3.6.0`, `warp-lang>=1.18.0`, sem teto (pyproject do espelho); GPU exige `jax[cuda12]` (`README.md:41`; extra `cuda` em `pyproject.toml:42-44`); não testado | 54 envs: 25 DM Control Suite + 19 locomoção + 10 manipulação (contagem por script no espelho). Backends MJX/JAX e MuJoCo Warp: o padrão das configs é `impl="warp"`, mas `train-jax-ppo`/`train-rsl-ppo` usam `--impl jax` (espelho: `learning/train_jax_ppo.py`) → passe `--impl warp`. 1ª carga de locomoção/manipulação clona a Menagerie no commit fixo `1b86ece` (git + rede) |
| `brax` | 0.14.2 (15/03/26) | ≥3.11 | — | só `brax/training` é mantido; ambientes/física → Playground e MJX/Warp (ficha) |
| MJPC (C++) | v0.1.0; `main` parado desde 27/05/2025 (espelho) | API Python experimental (3.10) | CMake fixa MuJoCo `088079e`, não o 3.15.0 (espelho); não testado | "research prototype" (README): **dormente** |
| `mjlab` | 1.6.0 (09/08/26) | ≥3.10,<3.14 | ✖ **fixa `mujoco~=3.11.0`** (ficha) | RL manager-based (API do Isaac Lab) sobre MuJoCo Warp; treino exige GPU NVIDIA → venv próprio (`uv pip install mjlab`) ou `uvx --from mjlab --refresh demo` |
| `mujoco-mjx`, `mujoco-warp` | 3.15.0 (grupo `gpu` do `uv.lock`) | — | mesma versão (lock) | física em GPU: `gpu-mjx-warp.md` |

Grupos opcionais do `pyproject.toml`: `urdf` (urdf2mjcf, robot_descriptions, trimesh), `rl` (gymnasium[mujoco], dm_control), `gpu`. `mujoco-menagerie` não está em nenhum. Python 3.12 já existe aqui (`uv python list`).

### 1.3 Recomendação por objetivo
| Objetivo | Use | Notas |
|---|---|---|
| Aprender (MuJoCo + robótica) | `mujoco` puro + templates `arm`/`pendulum` + modelos da Menagerie (`mm.load`); notebooks Colab do Playground (README) para ver RL | sem extras de RL; comece pelo §3 |
| Controle clássico (PD, IK, OSC, torque computado) | braços da Menagerie (UR5e, Panda, iiwa) ou URDF próprio (§2) + §3 | tudo do §3 roda no `.venv` atual |
| RL em GPU | Playground em venv **≥3.11** (o quickstart do README sugere 3.12; §1.2) com `--impl warp`; `export JAX_DEFAULT_MATMUL_PRECISION=highest` (README: TF32 em GPUs RTX 30/40 prejudica o RL) | receita do README (não testada): `uv venv --python 3.12` → `uv pip install -U "jax[cuda12]"` → `uv --no-config sync --all-extras` → `train-jax-ppo --env_name CartpoleBalance --impl warp`. O grupo `gpu` do lab usa `jax[cuda13]`: conflito não verificado → `gpu-mjx-warp.md`. mjlab só em venv à parte. VRAM de 8 GB: requisitos não documentados |
| RL em CPU / benchmarks | Gymnasium `v5` ou dm_control Suite (venv 3.12) | render offscreen: `MUJOCO_GL=egl` |
| MPC | MJPC está dormente e pina MuJoCo antigo; sem alternativa mantida verificada → planejador próprio em Python (`mujoco.rollout`, `python-api.md`) | não testado aqui |

## 2. Importar URDF e malhas

### 2.1 Carregador nativo (`MjModel.from_xml_path/_string` e `MjSpec.from_file/_string` aceitam URDF; doc: `modeling.rst#CURDF`, `XMLreference.rst#compiler` e `#asset-mesh`)
| Tema | Comportamento (✔ 3.15.0 salvo indicação) |
|---|---|
| Bloco `<mujoco>` | filho de `<robot>`; só `compiler`, `option`, `size`. URDF **não** é validado por schema: typo de atributo é ignorado em silêncio (`modeling.rst#CURDF`) |
| Padrões mudam | URDF: `discardvisual=true`, `fusestatic=true`, `angle`=rad, `strippath=false` (MJCF: false/false/degree/false) ✔ |
| Inércia | exige os 6 termos (`required attribute missing: 'ixy'`). A+B<C → `inertia must satisfy A + B >= C` → `balanceinertia="true"` (média dos 3 eixos: (0,001; 0,001; 0,01) → 0,004 em cada). Massa 0 em corpo móvel → `boundmass`/`boundinertia`. Sem `<inertial>`: massa vem das geoms de colisão (esfera r=0,05 → 0,5236 kg); só visual → erro. `inertiafromgeom="true"` sobrescreve inércias absurdas |
| Juntas | revolute→hinge · continuous→hinge sem limite · prismatic→slide · fixed→sem junta · planar→`<n>_TX`,`<n>_TY` (slide) + `<n>_RZ` (hinge) · spherical→ball · floating→free (só filho de `world`) · `ball` → erro. `<mimic>`→`equality/joint` (`polycoef` offset·mult). `<limit lower/upper>`→`range`; `effort`→`actuatorfrcrange=±effort`; `<dynamics>`→`damping`,`frictionloss`; `velocity` ignorado (ficha) |
| Sem atuadores | `nu=0` ✔ (`<transmission>`, `<gazebo>`, `<safety_controller>` ignorados: ficha) → crie `position`/`motor` no MJCF. Contato nos padrões `solref=[0.02 1]`, `solimp=[0.9 0.95 0.001 0.5 2]` ✔ |
| Visual × colisão | `<collision>` → geom `contype=1 conaffinity=1 group=0`; `<visual>` → `contype=0 conaffinity=0 group=1 density=0` (não duplica massa); cor do `<material>` → `rgba`; `discardvisual=true` descarta visuais |
| Base | link raiz **soldado ao mundo**, fundido ao `worldbody` por `fusestatic` (2 links → nbody=2). Base flutuante: `spec.body("base").add_freejoint()` **antes do 1º `compile()`** (depois, `body("base")` é `None`) ou link `world` + junta `floating` (nq=7) |
| Malhas | STL **binário**, OBJ, MSH. STL ASCII → `decoder failed … perhaps this is an ASCII file?`; `.dae` → `no decoder found` (converta: Blender, MeshLab, trimesh). `scale` do `<mesh>` vale. Caminho relativo ao URDF (+`meshdir`); `package://` NÃO resolve (`Error opening file 'package:/pkg/…'`) → `<compiler strippath="true" meshdir="meshes"/>` |

```python
import mujoco
URDF = """<robot name="r2"><mujoco><compiler balanceinertia="true" discardvisual="false"/></mujoco>
 <link name="base"><inertial><mass value="2"/><inertia ixx="0.01" iyy="0.01" izz="0.01" ixy="0" ixz="0" iyz="0"/></inertial>
   <collision><geometry><cylinder radius="0.05" length="0.1"/></geometry></collision></link>
 <joint name="ombro" type="revolute"><parent link="base"/><child link="elo"/><origin xyz="0 0 0.1"/><axis xyz="0 1 0"/>
   <limit lower="-1.57" upper="1.57" effort="20" velocity="3"/><dynamics damping="0.1"/></joint>
 <link name="elo"><inertial><origin xyz="0.15 0 0"/><mass value="0.5"/><inertia ixx="0.001" iyy="0.001" izz="0.01" ixy="0" ixz="0" iyz="0"/></inertial>
   <collision><origin xyz="0.15 0 0"/><geometry><box size="0.3 0.04 0.04"/></geometry></collision></link></robot>"""
m = mujoco.MjModel.from_xml_string(URDF)         # base soldada ao mundo e fundida (fusestatic)
print(m.nbody, m.njnt, m.nu, m.jnt_range[0], m.jnt_actfrcrange[0], m.body_inertia[1])   # 2 1 0 [-1.57 1.57] [-20. 20.] [0.004 0.004 0.004]
spec = mujoco.MjSpec.from_string(URDF)           # mesmo carregador do MJCF; o spec continua editável
spec.body("base").add_freejoint()                # ANTES do 1º compile(): depois dele a base já foi fundida e body("base") é None
for me in spec.meshes: me.maxhullvert = 64       # (se houver malhas) o URDF não define maxhullvert; spec.default.mesh não vale após o load
m = spec.compile()
print(m.nq, m.nv, m.nbody)                       # 8 7 3
mujoco.mj_saveLastXML("r2.xml", m)               # URDF → MJCF; depois edite só o MJCF (ou spec.to_xml(), que compila internamente)
```
Δ doc: a nota de migração do changelog 3.7.0 manda `spec.compiler.strippath = True` → `AttributeError`; em Python é `spec.strippath = True` ✔.

### 2.2 `urdf2mjcf` (K-Scale Labs, MIT; `pip install urdf2mjcf`; 0.2.39 de 17/08/2025; Python ≥3.11) — o que faz de verdade ✔ (executado num URDF de 2 elos)
- CLI: `urdf2mjcf robot.urdf --output robot.xml [--copy-meshes] [--metadata-file m.json]`. ⚠ Saída `.mjcf`: `MjSpec.from_file` → `could not decode content`, `MjModel.from_xml_path` carrega com aviso → use `.xml`.
- **Faz** ✔: hinge (revolute; continuous sem `range`) e slide (prismatic); fixed/planar/spherical viram corpo rígido **sem aviso** e `<mimic>` é ignorado (a junta fica independente); `<default class="visual">` (`contype=0 conaffinity=0 group=2`) e `<default class="collision">` (`group=1 condim=3 contype=0 conaffinity=1 priority=1 solref="0.005 1" solimp="0.99 0.999 1e-05" friction="1 0.01 0.01"`) com cada geom marcado; um `<motor name="<junta>_ctrl">` por junta criada (**torque**, não servo); `<contact><exclude>` pai-filho; **base flutuante** (`<freejoint name="floating_base">`); site, 2 câmeras `track` e 5 sensores (`frame*`, `velocimeter`) na raiz.
- **Não faz**: balancear inércia — grava só `diaginertia="ixx iyy izz"` (termos fora da diagonal: aviso "will be ignored"); A+B<C passa e o MuJoCo recusa → ponha `balanceinertia="true"` no MJCF. Não importa `<dynamics>` nem `<limit effort>` (damping 0, ctrlrange 0); a CLI ignora `joint_name_to_metadata`/`actuator_type_to_metadata` do `--metadata` ("single empty 'motor' class"); descarta o bloco `<mujoco>` do URDF. Δ ficha: a saída **não** traz `<option integrator="implicitfast" cone="elliptic" impratio="100">` (`add_option` está comentada na 0.2.39) → Euler/pirâmide.
- **Massa**: remove o `<inertial>` do link raiz e a classe `visual` não tem `density=0` → massa inferida de visual+collision: base de 2,0 kg virou **1,5708 kg** (o nativo dá 2,0).
- **Quebra**: `<mesh scale>` vai p/ `<geom scale>` → `Schema violation: unrecognized attribute: 'scale'`; `package://` copiado sem resolver (`Error opening file`; com `--copy-meshes`: `FileNotFoundError`); `<link name="world"/>` explícito → `<body name="world">` → `repeated name 'world' in body`.
- **Decomposição convexa: nenhuma** (zero ocorrências de coacd/vhacd/decompos no pacote; `postprocess/collisions.py` só troca malhas de links nomeados por primitivas; `maxhullvert` só via metadata).
- Use para bootstrap (classes, sensores, exclusões); revise massa, inércia, escala e `world`. Para o resto, §2.1 + MJCF editado.

### 2.3 Malhas, colisão e decomposição convexa
- Colisão de malha = **casco convexo** (`overview.rst`, `computation/index.rst#coDecomposition`): objeto côncavo ⇒ decomponha em geoms convexos no mesmo corpo. ✔ Toro côncavo (288 vértices, casco 168): como malha única segura uma esfera (z=0,055 m); 24 peças convexas a deixam cair pelo furo.
- `maxhullvert` (`<mesh>`; padrão −1 = ilimitado; ≥4): casco 168 → 64/32/16/8/4 ✔. MJX: ≤64; MJX-JAX: ~200 vértices (malha×primitiva), <32 (convexo×convexo) (`mjx.rst`). ⚠ Via `MjSpec`, `0` ou `3` **derrubam o processo** (exit 139, `QH7093`) ✔; o XML rejeita ≤3 (`maxhullvert must be larger than 3`), mas a API Python não valida.
- Prefira primitivas à mão (cápsula/caixa/cilindro); `<geom type="box|capsule|sphere" mesh="m"/>` ajusta a primitiva à malha ✔ (`compiler fitaabb`). `<mesh inertia="convex">` (o padrão `legacy` superconta volume em não convexas; a doc recomenda `convex`).
- Ferramentas (**não testadas**: fora do venv permitido): CoACD (`pip install coacd`; `coacd.run_coacd(coacd.Mesh(V, F))` → cascos; threshold 0,05; ativo, v1.0.14); `obj2mjcf` (`pip install obj2mjcf`; Zakka, MIT; divide o OBJ por material/MTL e gera MJCF; com `--decompose` grava `<nome>_collision_<i>.obj` via CoACD — padrões: threshold 0,05, preprocess_resolution 50, mcts_iterations 100; cores aleatórias; último commit 15/10/2024); conversor do `mujoco_ros2_control` (origem de `class="decomposed_collision"`; "hacky and highly experimental"); fork `discoverse-dev/urdf-to-mjcf --collision-type decomposition`. V-HACD está arquivado (a Menagerie ainda o cita no Panda `link5`). `.xacro` não é URDF: converta antes (não verificado).

### 2.4 Pipeline recomendado (CAD/URDF → MJCF → validação; é o da Menagerie: `franka_emika_panda/README.md`, `universal_robots_ur5e/README.md`)
1. Malhas: STL binário/OBJ em metros, uma por link (`.dae` → OBJ no Blender; a Menagerie ainda passa o OBJ por `obj2mjcf`).
2. URDF: 6 termos de inércia por link, sem `package://`, e `<mujoco><compiler meshdir="meshes" strippath="true" balanceinertia="true" discardvisual="false"/></mujoco>` (+ `fusestatic="false"` para manter o link raiz como corpo).
3. Carregar (nativo) e **salvar** como MJCF (`mj_saveLastXML(path, model)` ou `spec.to_xml()`; `spec.to_file()` sem `compile()` → `Only compiled model can be written` ✔). Depois edite **só o MJCF** (`modeling.rst#CURDF`).
4. No MJCF: classes em `<default>`, atuadores `position`/`general` (kp/kv + `forcerange` do datasheet), `<contact><exclude>`, colisões simples à mão (visuais: `contype=0 conaffinity=0 group=2`), keyframe `home`, `scene.xml` separado, `solref/solimp`.
5. Validar:
```bash
urdf2mjcf robot.urdf --output robot.xml            # opcional (venv à parte: uv pip install urdf2mjcf trimesh); saída .xml, não .mjcf
/home/ondokai/Projects/MuJoCo/.venv/bin/python /home/ondokai/Projects/MuJoCo/.agents/mujoco-lab-agent-skill/scripts/inspect_model.py robot.xml --tree --steps 2000   # exit 0 ok · 1 risco · 2 erro
```
   Leia `penetração máx` e `contatos máx` do teste de fumaça. ✔ Exemplo (URDF com `world`+junta `fixed`, geoms sobrepostas): 24,6 mm e 4 contatos; com `<contact><exclude body1="base" body2="elo"/></contact>`: 0 mm e 0 (`overview.rst#SurprisingCollisions`: a exclusão pai-filho **não vale com pai estático**, mesmo com `fusestatic="false"`).

## 3. Controle de manipuladores (template `arm`)
`assets/templates/arm/{model.xml,run.py}`: braço 3 GDL (yaw Z, ombro Y, cotovelo Y; site `ponta`), servos `<position kp=400 kv=40 forcerange=±120 inheritrange=1>`, `gravcomp="1"`, alvo = corpo mocap. ✔ `run.py --sem-video`: RMS da ponta 3,96 mm (tol. 10), τ máx 1,6 N·m, juntas nos limites, exit 0. O `run.py` (`SeguidorIK`, L31–57; `pose_inicial`, L68–80; alvo = `d.mocap_pos[0]`) faz IK diferencial: `v = v_alvo + Kp·erro`; `dq = Jᵀ(JJᵀ+λ²I)⁻¹·v·dt`; `q_cmd += dq` → `ctrl` dos servos (o PD segue `q_cmd`); `pose_inicial` resolve a IK offline. Os blocos 3.0–3.6 são UM script (compartilham `T`, `m`, `d`, `ponta`) ✔ e cada um roda sozinho depois do 3.0.

```python
import mujoco, numpy as np
T = "/home/ondokai/Projects/MuJoCo/.agents/mujoco-lab-agent-skill/assets/templates/arm/model.xml"   # yaw, ombro, cotovelo; site "ponta"
m = mujoco.MjModel.from_xml_path(T); d = mujoco.MjData(m); ponta = m.site("ponta").id
print("kp", m.actuator_gainprm[0, 0], "kv", -m.actuator_biasprm[0, 2], "| ctrlrange == range (rad):", m.actuator_ctrlrange[0], m.jnt_range[0])
```

### 3.1 Servo PD (`position`)
Força = `kp·(ctrl − q) − kv·q̇` (`gainprm=[kp]`, `biasprm=[0,−kp,−kv]`; `ctrl` em rad), limitada por `forcerange`; padrão kp=1, kv=0. `kv` pede `implicitfast`/`implicit` (no Euler é explícito: instável se `kv·Δt/J > 2` — `actuators-sensors.md` §6 ✔). `dampratio` (exclusivo com `kv`; 1 = crítico) vale `kv = 2·dampratio·√(kp·m)` com `m = (J M⁻¹ Jᵀ)⁻¹` em `qpos0` — **inércia operacional**, sem `damping`/`frictionloss` da junta. ✔ Δ vs 3.14 (changelog: antes Σ dof_M0/J²; reproduzida, não rodada no 3.14):
```python
xml = open(T).read().replace('inheritrange="1"/>', 'inheritrange="1" dampratio="1"/>')   # troca kv por dampratio nos 3 servos
m1 = mujoco.MjModel.from_xml_string(xml); d1 = mujoco.MjData(m1); mujoco.mj_forward(m1, d1)
M = np.zeros((m1.nv, m1.nv)); mujoco.mj_fullM(m1, d1, M)                                  # mj_fullM(m, d, dst) desde a 3.10
kp, kv = m1.actuator_gainprm[:, 0], -m1.actuator_biasprm[:, 2]
print("kv 3.15:", kv.round(2), "| 2√(kp/Minv_ii):", (2*np.sqrt(kp / np.diag(np.linalg.inv(M)))).round(2), "| antigo 2√(kp·M_ii):", (2*np.sqrt(kp * np.diag(M))).round(2))
# → kv 3.15: [36.37 23.75  7.4] | 2√(kp/Minv_ii): [36.37 23.75  7.4] | antigo: [36.37 36.32 11.33]  (ombro −35 %, cotovelo −35 %)
```

### 3.2 Compensação de gravidade
| Método | Como | Resultado ✔ (pose `q*=[0,−0.5,1.0]`, kp=400) |
|---|---|---|
| nenhum | — | cede `g/kp`: erro [0, 0,0304, 0,0052] rad; `g = qfrc_bias` = [0, −12,03, −2,14] N·m |
| `gravcomp="1"` (body) | força passiva no CM (`qfrc_gravcomp` ⊂ `qfrc_passive`); o template já usa | erro 0 |
| `actuatorgravcomp="true"` (joint) | idem, mas somada a `qfrc_actuator` → respeita `actuatorfrcrange` | `qfrc_gravcomp` migra p/ `qfrc_actuator` |
| feedforward | servo: `ctrl = q* + qfrc_bias/kp` (gear 1); motor: `τ += qfrc_bias` | erro 0 |

⚠ `qfrc_bias` contém a gravidade **mesmo com `gravcomp=1`** (e Coriolis): com `gravcomp` ativo não some `qfrc_bias` de novo (conta 2×) — zere `body_gravcomp` (§3.4) ou use `qfrc_inverse`.
```python
def segura(mod, q, ctrl, seg=4.0):               # segura a pose q por seg s; devolve o erro estacionário (rad)
    dd = mujoco.MjData(mod); dd.qpos[:3] = q; dd.ctrl[:3] = ctrl
    for _ in range(int(seg / mod.opt.timestep)): mujoco.mj_step(mod, dd)
    return (dd.qpos[:3] - q).round(5)
q = np.array([0.0, -0.5, 1.0]); m0 = mujoco.MjModel.from_xml_path(T); m0.body_gravcomp[:] = 0       # m0 = template SEM gravcomp
d0 = mujoco.MjData(m0); d0.qpos[:3] = q; mujoco.mj_forward(m0, d0); g = d0.qfrc_bias[:3].copy()      # g(q*) em N·m
print(g.round(3), segura(m0, q, q), segura(m0, q, q + g / m0.actuator_gainprm[:3, 0]), segura(m, q, q))
# → [0. -12.025 -2.142] [0. 0.03035 0.00525] [0. 0. 0.] [0. 0. 0.]   (sem comp. · feedforward · gravcomp do template)
```

### 3.3 IK diferencial por Jacobiano
`mj_jacSite(m, d, jacp, jacr, site)` → J (3×nv); `jacp`/`jacr` aceitam `None`. Exige `mj_kinematics` **+** `mj_comPos` (ou `mj_forward`) com o `qpos` atual (doc de `mj_jac`). ✔ Erro máx de J vs diferenças finitas após mudar `qpos`: sem nada 0,62 · só `mj_kinematics` 0,39 · só `mj_comPos` 0,62 · os dois ou `mj_forward` 7,5e-11 (MjData novo: J=0). No laço de controle, `site_xpos`/J vêm do passo anterior (defasagem de 1 passo; `mj_step1` dá os frescos, §3.4). DLS (λ≈0,05) evita explosão perto de singularidade; limite o passo cartesiano p/ alvos longe; alvo inalcançável → "o mais perto" (cheque o erro residual). Em ball/free joints use `mj_integratePos`, não `qpos += dq`.
```python
def ik(m, d, alvo, it=300, lam=0.05, passo=1.0, tol=1e-5, max_e=0.1):
    """IK diferencial (mínimos quadrados amortecidos): itera q até o site 'ponta' chegar em `alvo` (m)."""
    J = np.zeros((3, m.nv)); s = m.site("ponta").id
    for k in range(it):
        mujoco.mj_kinematics(m, d); mujoco.mj_comPos(m, d)               # estágios que o mj_jacSite exige (ou mj_forward)
        mujoco.mj_jacSite(m, d, J, None, s)
        e = alvo - d.site_xpos[s]; n = np.linalg.norm(e)
        if n < tol: break
        e *= min(1.0, max_e / n)                                         # limita o passo cartesiano (alvo longe)
        dq = J.T @ np.linalg.solve(J @ J.T + lam**2 * np.eye(3), e)      # Jᵀ(JJᵀ+λ²I)⁻¹ e
        mujoco.mj_integratePos(m, d.qpos, dq, passo)                     # qpos += dq (certo também com ball/free joints)
        d.qpos[:] = np.clip(d.qpos, m.jnt_range[:, 0], m.jnt_range[:, 1])  # (todas as juntas deste modelo têm range)
    return k + 1, n
for alvo in ([0.55, 0, 0.55], [0.3, 0.3, 0.2], [2.0, 0, 0.3]):           # alcançável · alcançável · fora do alcance (braço: 0,9 m)
    d.qpos[:3] = [0, -1, 1.6]; k, n = ik(m, d, np.array(alvo)); print(alvo, f"{k} it, erro {n*1000:.3f} mm", d.qpos[:3].round(3))
# → 3 it, 0.008 mm, q=[0 -1.088 1.74] · 9 it, 0.002 mm, q=[0.785 -0.523 2.116] · 300 it, 1106.75 mm (braço esticado até o limite do cotovelo)
```

### 3.4 Torque computado e espaço operacional (atuadores `motor`)
Para torque, troque os servos por `<motor>`. ⚠ `spec.add_actuator` num spec cujo `<default>` tem `<position kp kv forcerange>` **herda** esses ganhos (✔ gainprm=[400,0,0], biastype affine): chame `.set_to_motor()`.
```python
spec = mujoco.MjSpec.from_file(T)                 # torque puro: troca os 3 servos <position> por <motor>
for a in list(spec.actuators): spec.delete(a)
for j in ("yaw", "ombro", "cotovelo"):            # set_to_motor(): sem ele o default <position kp kv> do template vazaria p/ o novo atuador
    spec.add_actuator(name="m_" + j, target=j, trntype=mujoco.mjtTrn.mjTRN_JOINT, ctrllimited=True, ctrlrange=[-120, 120]).set_to_motor()
mt = spec.compile(); mt.body_gravcomp[:] = 0; ponta = mt.site("ponta").id   # sem gravcomp passivo: o controlador compensa a gravidade
J, M = np.zeros((3, mt.nv)), np.zeros((mt.nv, mt.nv))

def tau_operacional(mt, dm, alvo, kp=400.0, kd=60.0):          # espaço operacional: τ = Jᵀ Λ (kp·e − kd·ẋ) + qfrc_bias
    mujoco.mj_jacSite(mt, dm, J, None, ponta); mujoco.mj_fullM(mt, dm, M)
    Lam = np.linalg.inv(J @ np.linalg.solve(M, J.T))           # Λ = (J M⁻¹ Jᵀ)⁻¹: massa operacional 3×3
    return J.T @ (Lam @ (kp * (alvo - dm.site_xpos[ponta]) - kd * (J @ dm.qvel))) + dm.qfrc_bias

def tau_computado(mt, dm, a_ref):                              # torque computado: a_ref = q̈d + Kp·e + Kd·ė → τ = dinâmica inversa
    dm.qacc[:] = a_ref; mujoco.mj_inverse(mt, dm); return dm.qfrc_inverse.copy()

dm = mujoco.MjData(mt); dm.qpos[:3] = [0, -1, 1.6]; alvo = np.array([0.55, 0, 0.55])
for _ in range(1500):                                           # 3 s
    mujoco.mj_step1(mt, dm)                                     # Jacobiano/M/bias frescos (mj_step daria os do passo anterior)
    dm.ctrl[:] = tau_operacional(mt, dm, alvo)
    mujoco.mj_step2(mt, dm)
print("OSC: erro final", np.linalg.norm(alvo - dm.site_xpos[ponta]) * 1000, "mm | τ final", np.abs(dm.actuator_force).max().round(1))
dm.qpos[:3] = [0.3, -0.7, 1.1]; dm.qvel[:3] = [0.5, -0.4, 0.8]; a = np.array([1.0, -2.0, 3.0])
dm.ctrl[:] = tau_computado(mt, dm, a); mujoco.mj_forward(mt, dm)
print("torque computado: erro de qacc =", np.abs(dm.qacc - a).max())   # → ~1e-15: a aceleração pedida é reproduzida exatamente
```
- ✔ `qfrc_inverse` = força que os atuadores devem dar para produzir `qacc` (inclui gravidade, Coriolis, passivas, `gravcomp` e restrições: `simulation.rst`). OSC converge a alvo estático (erro ~1e-6 mm em 3 s; τ final 7,2 N·m).
- `mj_step1`/`mj_step2` valem p/ Euler, implicit e implicitfast (não RK4) e dão estado fresco ao controlador (`simulation.rst`). 6D/redundância (espaço nulo): não testado.

### 3.5 Limites
| Mecanismo | Unidade / regra | Nota |
|---|---|---|
| `joint range` (+`limited`) | graus no XML (`angle=degree`), rad no modelo; `autolimits` liga `limited` se há `range` | limite macio (`solreflimit`/`solimplimit`) ✔: cotovelo (150°) sob 5/20/100 N·m excede o limite em 0,14°/0,54°/2,7° |
| `actuator ctrlrange` | **sempre rad** — NÃO converte de graus ✔ (`ctrlrange="-170 170"` → ±170 rad) | `inheritrange="1"` copia o `range` da junta já em rad ✔ |
| `actuator forcerange` | clampa a força do atuador ✔ (pedido 400 N·m → 120) | servos: sempre defina (datasheet) |
| `joint actuatorfrcrange` | clampa a SOMA dos atuadores na junta (e o `gravcomp` se `actuatorgravcomp`) | vem do `<limit effort>` do URDF ✔ |

### 3.6 Garras, mãos e pernas
Acoplar garra/mão: a Menagerie põe um site `attachment_site` nos braços (`FAQ.md` mostra a versão PyMJCF); com `MjSpec` ✔:
```python
BRACO = """<mujoco><worldbody><body name="elo"><joint name="j1" axis="0 1 0"/><geom size="0.05"/><site name="attachment_site" pos="0 0 0.3"/></body></worldbody>
  <actuator><position name="a1" joint="j1" kp="50"/></actuator></mujoco>"""
GARRA = """<mujoco><worldbody><body name="palma"><geom size="0.03"/><body name="dedo" pos="0.04 0 0"><joint name="jd" type="slide" axis="1 0 0" range="0 0.02"/><geom size="0.01"/></body></body></worldbody>
  <actuator><position name="ad" joint="jd" kp="200"/></actuator></mujoco>"""
arm, hand = mujoco.MjSpec.from_string(BRACO), mujoco.MjSpec.from_string(GARRA)
arm.attach(hand, prefix="g/", site=arm.site("attachment_site"))      # a garra vira filha do site; seus nomes ganham o prefixo
m_ag = arm.compile(); print(m_ag.nbody, m_ag.nu, [m_ag.actuator(i).name for i in range(m_ag.nu)])   # 4 2 ['a1', 'g/ad']
```
Com modelos da Menagerie: `mm.get("kuka_iiwa_14").spec()` + `mm.get("wonik_allegro").spec("left_hand")` (`python/DOC.md`; não testado). `modeledit.rst#meAttachment`: o filho compila com os flags do filho; conflito de atributos globais (ex. `integrator`) → aviso e o pai vence (`compiler/conflict`); depois de `attach` o filho não compila sozinho; keyframes só são reindexados após `compile()` (entre dois `attach`, compile; senão os do 1º se perdem).
- Menagerie — quadrúpedes: Unitree A1/Go1/Go2, ANYmal B/C, Spot, Barkour v0/vB; humanoides: G1, H1, T1, OP3, Apollo, TALOS, Berkeley Humanoid; bípede: Cassie; mãos/garras: Allegro, Shadow, LEAP, Sharpa Wave, Aero Hand, Robotiq 2F-85, mão do Panda. O README de cada pasta é a receita; atuação = PD `position`/`general`.
- Locomoção e destreza são RL: envs do Playground (`Go1JoystickFlatTerrain`, `G1JoystickFlatTerrain`, `H1JoystickGaitTracking`, `BarkourJoystick`, `PandaPickCube`, `LeapCubeReorient`, `AlohaHandOver`). Garra com tendão + equality + `general`: `actuators-sensors.md`.

## 4. Correções ao relatório do usuário (§6: urdf2mjcf/CoACD)
| Afirmação do relatório (§6) | Correção ao relatório do usuário — veredito (ficha Q12) | O que é verdade (✔ = testado aqui) |
|---|---|---|
| `pip install urdf2mjcf` + `urdf2mjcf robot.urdf --output robot.mjcf` | **correta, com ressalvas** | pacote real (K-Scale, MIT, 0.2.39; comunitário; último commit 26/09/2025). ✔ `.mjcf` não é decodificado pelo `MjSpec.from_file` → use `.xml`; base flutuante, `package://`, `scale` e `world` dão problema (§2.2) |
| examina assimetrias da diagonal da inércia e faz "nivelamento algébrico" | **incorreta** | ✔ só escreve `diaginertia` (fora da diagonal: ignora com aviso); A+B<C passa e o MuJoCo recusa. O "nivelamento" é o `compiler/balanceinertia="true"` do MuJoCo (padrão false; média dos 3 eixos) |
| separa `class="collision"` de `class="visual"` | **correta** (no urdf2mjcf) | ✔ classes `visual` (group 2, contype 0) e `collision` (group 1…); o nativo separa por atributos (`<visual>`: `contype=0 conaffinity=0 group=1 density=0`) |
| CoACD, `class="decomposed_collision"`, cores de paleta | **incorreta** | ✔ urdf2mjcf não decompõe (sem coacd/vhacd/decompos no pacote; só primitivas e `maxhullvert`). `decomposed_collision` é do conversor do `mujoco_ros2_control` (opt-in; obj2mjcf+CoACD; cor aleatória por peça, não paleta). Decompor: `obj2mjcf --decompose`, `coacd` ou `urdf-to-mjcf` (§2.3; não testados) |
| URDF não tem ajustes de soft contact (solref/solimp) | **correta** | ✔ nativo: `solref=[0.02 1]`, `solimp=[0.9 0.95 0.001 0.5 2]`; urdf2mjcf injeta `solref=[0.005 1]` e `solimp=[0.99 0.999 1e-05]` na classe `collision`; ajustes entram no MJCF |
| o repositório do MuJoCo traz "Computation" e "XML Reference" | **correta** | `docs/upstream/mujoco/doc/computation/index.rst` e `docs/upstream/mujoco/doc/XMLreference.rst` ✔ |
| malhas côncavas "geram instabilidade" e "polígonos côncavos falsos" | **parcial** (leitura minha; fora da auditoria Q12) | o MuJoCo colide pelo casco convexo: não instabiliza, mas trata a peça como sólido convexo (✔ toro, §2.3); decomponha ou use primitivas |

## Armadilhas
| Sintoma | Causa | Correção |
|---|---|---|
| `Error opening file 'package:/pkg/meshes/x.stl'` | `package://` não é resolvido (nativo e urdf2mjcf) | nativo: `<compiler strippath="true" meshdir="meshes"/>` no bloco `<mujoco>`; urdf2mjcf: reescreva os caminhos antes |
| `inertia must satisfy A + B >= C` | inércia não física (URDF/CAD) | `balanceinertia="true"` (no URDF ou no MJCF gerado pelo urdf2mjcf) |
| `mass and inertia of moving bodies must be larger than mjMINVAL` | link dummy/só visual sem `<inertial>` | `boundmass`, `<inertial>` ou geom de colisão |
| `required attribute missing: 'ixy'` | `<inertia>` sem os 6 termos | preencha com 0 |
| `decoder failed … ASCII file?` / `no decoder found` | STL ASCII / `.dae` | converta para STL binário ou OBJ |
| `could not decode content` ao abrir a saída do urdf2mjcf | extensão `.mjcf` (padrão sem `--output`) | `--output robot.xml` |
| `Schema violation: unrecognized attribute: 'scale'` | urdf2mjcf copia `<mesh scale>` para o `<geom>` | mova para `<mesh scale>` no MJCF |
| `repeated name 'world' in body` | `<link name="world"/>` no URDF passado ao urdf2mjcf | remova link/junta `world` ou use o nativo |
| `spec.body("base")` é `None` | `compile()` já fundiu o link raiz estático (`fusestatic`) | `add_freejoint()` antes do 1º compile ou `fusestatic="false"` |
| `AttributeError: 'MjsCompiler' … 'strippath'` | nota de migração do changelog 3.7.0 errada (Δ doc) | `spec.strippath = True` |
| penetração/contatos base↔1º elo; energia sobe sem atuadores | exclusão pai-filho não vale com pai estático | `<contact><exclude>`, `contype/conaffinity` ou corpo mocap |
| massa 2,0 → 1,57 kg depois do urdf2mjcf | raiz sem `<inertial>` + visual e collision somados | `<inertial>` explícito, `density="0"` na classe `visual` |
| processo morre (exit 139, `QH7093`) | `maxhullvert` 0 ou 3 via `MjSpec` | use ≥4 |
| esfera "dentro" do furo / colisão errada em peça côncava | colisão usa o casco convexo | decomponha em geoms convexos |
| PD com `kv` alto diverge | integrador Euler | `integrator="implicitfast"` |
| servo vai a ±170 "rad" | `ctrlrange` não converte graus | rad ou `inheritrange="1"` |
| atuador novo via `MjSpec` com kp/kv que ninguém pediu | `<default><position>` vaza para a classe | `a.set_to_motor()` / `set_to_position(...)` |
| J nulo/errado na IK | faltou `mj_kinematics` + `mj_comPos` | `mj_forward` ou os dois |
| torque computado erra por gravidade 2× | `gravcomp=1` e `qfrc_bias` juntos | `body_gravcomp[:] = 0` ou `qfrc_inverse` |
| modelo da Menagerie amortece diferente | `dampratio` mudou na 3.15 | compare `-actuator_biasprm[:,2]` (§3.1) |
| `uv sync --group rl` falha / mjlab rebaixa o mujoco | labmaze sem wheel cp313; mjlab fixa mujoco 3.11 | venv separado com Python 3.12 |
| 1º uso de Playground/robot_descriptions/`mm.load` trava | clonam/baixam a Menagerie (git + rede) | pré-baixe (`mm.prefetch([...])`) |
