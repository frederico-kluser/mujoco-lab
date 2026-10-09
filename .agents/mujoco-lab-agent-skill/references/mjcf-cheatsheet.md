# Cheat-sheet MJCF (MuJoCo 3.15)

Formato XML de modelos do MuJoCo 3.15: seções de topo, corpos/juntas/geoms, inércia e massa, malhas, defaults, composição, `<visual>` e o que mudou desde 3.0.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: fichas `pesquisas/conhecimento/Q5.md` e `Q16.md`; `docs/upstream/mujoco/doc/{XMLreference,modeling,XMLschema,changelog}.rst`; modelos do laboratório (`models/`, templates da skill); testes locais (`.venv`, mujoco 3.15.0).

## Quando ler este arquivo
- Ao escrever, editar ou depurar um `.xml` MJCF: estrutura, defaults/classes, malhas, massa/inércia, `include`/`attach`/`replicate`/`flexcomp`.
- Quando um modelo antigo (pré-3.9) não compila ou muda de comportamento: §7 (removidos/renomeados e a nova semântica de `margin`/`gap`).
- Quando a massa sai errada (ex.: dobrada) ou o compilador reclama: §3 e a tabela de armadilhas do fim.
- Marcadores: `✔ testado` (executado em 3.15.0) · `⚠ armadilha` · `Δ doc` (a doc diverge do medido) · `Correção ao relatório do usuário` (§8). Busca rápida: `python3 .agents/mujoco-lab-agent-skill/scripts/docs_search.py --elem geom` · `--attr compiler.angle` · `--changelog <termo>`.

## 1. Esqueleto mínimo e seções de topo
Modelo com as 17 seções ✔ compila (`nbody=4 njnt=3 ngeom=5 nflex=1 neq=2 ntendon=1 nu=1 nsensor=1 nkey=1`). O mínimo real é `<mujoco><worldbody>…</worldbody></mujoco>`; apague o que não usar.
```xml
<mujoco model="esqueleto">                              <!-- raiz única; 17 seções filhas, todas opcionais -->
  <compiler angle="degree" autolimits="true"/>          <!-- globais do parser/compilador (valores padrão 3.15) -->
  <option timestep="0.002"/>                            <!-- física: gravity 0 0 -9.81, integrator Euler, solver Newton -->
  <size memory="2M"/>                                   <!-- só o que não se infere; padrão memory=-1 (automático) -->
  <statistic center="0 0 0.5" extent="1.5"/>            <!-- sobrescreve estatísticas (câmera livre, escalas visuais) -->
  <visual><global offwidth="1280" offheight="720"/></visual>   <!-- teto da resolução offscreen -->
  <default>                                             <!-- classe de topo "main" (não renomeável) -->
    <geom rgba="0.8 0.3 0.1 1"/>
    <default class="visual"><geom contype="0" conaffinity="0" group="2" mass="0"/></default>
    <default class="collision"><geom group="3"/></default>
  </default>
  <asset>
    <texture name="grade" type="2d" builtin="checker" rgb1="0.2 0.3 0.4" rgb2="0.1 0.15 0.2" width="64" height="64"/>
    <material name="piso" texture="grade" texrepeat="4 4" texuniform="true"/>
    <mesh name="tet" vertex="0 0 0  1 0 0  0 1 0  0 0 1" scale="0.1 0.1 0.1"/>   <!-- só vertex ⇒ casco convexo -->
  </asset>
  <worldbody>                                           <!-- corpo "world": sem joint/inertial; filhos = árvore cinemática -->
    <light pos="0 0 3" dir="0 0 -1"/>
    <camera name="cam" pos="0 -2 1" xyaxes="1 0 0 0 0.4 1"/>
    <geom name="chao" type="plane" size="3 3 0.1" material="piso"/>
    <body name="elo" pos="0 0 0.5">
      <joint name="j" type="hinge" axis="0 1 0" range="-90 90"/>        <!-- sem joint ⇒ corpo soldado ao pai -->
      <geom name="haste" class="collision" type="capsule" fromto="0 0 0 0.4 0 0" size="0.02"/>
      <geom class="visual" type="mesh" mesh="tet"/>
      <site name="ponta" pos="0.4 0 0"/>                <!-- sem massa nem colisão: âncora de sensor/atuador/tendão -->
      <body name="elo2" pos="0.4 0 0"><joint name="j2" axis="0 1 0"/><geom type="sphere" size="0.03"/></body>
    </body>
    <body name="bola" pos="1 0 1"><freejoint/><geom type="sphere" size="0.05"/></body>
  </worldbody>
  <deformable><flex name="f" dim="1" body="elo elo2" vertex="0 0 0 0 0 0" element="0 1"/></deformable>
  <contact><exclude body1="elo" body2="elo2"/></contact>              <!-- também: <pair> (par explícito) -->
  <equality><weld body1="elo2" body2="bola"/><flex flex="f"/></equality>
  <tendon><fixed name="t"><joint joint="j" coef="1"/><joint joint="j2" coef="-1"/></fixed></tendon>
  <actuator><motor name="m" joint="j" gear="10"/></actuator>
  <sensor><jointpos name="s" joint="j"/></sensor>
  <keyframe><key name="k0" qpos="0.3 0 1 0 1 1 0 0 0" time="1"/></keyframe>   <!-- j, j2, free(x y z w x y z) -->
  <custom><numeric name="esperado" data="1 2 3"/></custom>
  <extension><plugin plugin="mujoco.elasticity.cable"/></extension>
</mujoco>
```

| Seção | Filhos principais | Essencial (padrões 3.15) |
|---|---|---|
| `option` | `flag` | `timestep` 0.002 · `gravity` 0 0 −9.81 · `integrator` Euler (`RK4` `implicit` `implicitfast` `discrete`) · `solver` Newton · `cone` pyramidal · `iterations` 100 · `tolerance` 1e-8 · `impratio` 1. `flag`: 20 `enable` (spring, damper, gravity, contact, limit, refsafe, nativeccd, multiccd, island…) e 7 `disable` (`override energy fwdinv invdiscrete sleep diagexact ipc`) |
| `compiler` | `lengthrange` | só afeta parse/compilação: `angle` degree · `autolimits` true · `eulerseq` xyz · `meshdir` `texturedir` `assetdir` · `inertiafromgeom` auto · `inertiagrouprange` 0 5 · `balanceinertia` `boundmass` `settotalmass` · `fusestatic` `discardvisual` false (true em URDF) · `alignfree` false · `conflict` warning |
| `size` | — | `memory` −1 (auto; "16M") · `nkey` · `nuserdata` · `nuser_*`; legado `njmax` `nconmax` `nstack` aceitos (`njmax`/`nstack` + `memory` ⇒ erro ✔) |
| `statistic` | — | `center` `extent` `meansize` `meanmass` `meaninertia` (sobrescrevem o calculado) |
| `asset` | `mesh hfield texture material model` | nomes obrigatórios (mesh/texture/hfield tomam o do arquivo se omitido); `skin` aqui é legado |
| `worldbody` | `body geom site camera light frame replicate attach composite flexcomp` | `body` aninhado = árvore; dentro de `body`: `inertial joint freejoint` |
| `deformable` | `flex skin` | `flex` é baixo nível; prefira `flexcomp` |
| `contact` | `pair exclude` | `pair`: par de geoms predefinido com propriedades próprias (único jeito de atrito anisotrópico); `exclude body1 body2`: sem colisão entre dois corpos |
| `equality` | `connect weld joint tendon flex flexvert flexstrain` | restrições suaves (`solref`/`solimp`) |
| `tendon` | `spatial fixed` | |
| `actuator` · `sensor` | `motor position velocity intvelocity damper cylinder muscle adhesion pid orientation dcmotor general plugin` · `jointpos accelerometer touch contact …` | fora deste arquivo: ver a referência da skill sobre atuadores e sensores |
| `keyframe` | `key` | `name time qpos qvel act ctrl mpos mquat`; ver §5 |
| `visual` · `default` | `global quality headlight map scale rgba` · classes | §6 · §5 |
| `custom` · `extension` | `numeric text tuple` · `plugin` | dados do usuário no `mjModel` · plugins de motor (`<plugin plugin="…"/>`) |

- Seções **repetem e podem vir em qualquer ordem**; só importam a ordem das `<joint>` num `body`, a dos elementos de um tendão `spatial` e a dos atalhos de atuador num mesmo default. ✔ Atributo repetido: vale o último; `<worldbody>`, `<asset>` e `<option><flag>` repetidos são fundidos.
- Cada sub-elemento (`<global>`, `<flag>`…) só 1× por bloco: `unique element 'global' found 2 times` ✔.
- Meta-elementos: `include`, `frame`, `replicate` (fora do schema) e `composite`, `flexcomp`, `attach` (no schema); expandem em elementos comuns (o `frame` é preservado ao salvar desde 3.14.0).

## 2. Corpos, juntas, geoms e orientação
A árvore é `<body>` aninhado em `<worldbody>` (o "world" não aceita `joint`, `inertial` nem atributos). Uma `<joint>` **cria** graus de liberdade entre o corpo e o pai (não "restrições"); sem junta o corpo é **soldado ao pai**; várias juntas no mesmo corpo se aplicam em ordem (sem corpos fictícios). `body geom site camera light frame inertial` têm `pos` + orientação; `joint` só tem `pos`/`axis` (`euler` ⇒ `unrecognized attribute` ✔).

| `joint type` | qpos/qvel | Notas ✔ |
|---|---|---|
| `hinge` (padrão) | 1/1 | `axis` 0 0 1; `range` em graus se `angle="degree"` |
| `slide` | 1/1 | `range` em metros: **não** converte graus |
| `ball` | 4/3 | quaternion; `range` = ângulo máx. (só o 2º valor conta); `ball`+`hinge` ⇒ erro; `ball`+`slide` OK (nq 5, nv 4) |
| `free` | 7/6 | só em filho direto do `worldbody` e sozinho no corpo; `range` aceito e **ignorado** (`jnt_limited=0`); use `<freejoint/>` |

| geom `type` | `size` | Notas |
|---|---|---|
| `sphere` (padrão) | r | `size` padrão `0 0 0` é inválido: `size 0 must be positive in geom` |
| `capsule` `cylinder` | r, meia-altura | ou `fromto="x1 y1 z1 x2 y2 z2"` + só r |
| `box` `ellipsoid` | 3 meios-lados · 3 raios | `fromto` também; em `sphere` ⇒ erro |
| `plane` | meio-x, meio-y, passo da grade | 0 = infinito; só no mundo/estático; normal = +Z do geom |
| `mesh` `hfield` `sdf` | — (vêm do asset/plugin) | exigem `mesh=` / `hfield=` / plugin (SDF não verificado aqui); `type="box" mesh="m"` ajusta uma primitiva à malha ✔ |
| `cone` `arrow` `torus` | — | não existem: `invalid keyword` ✔ |

| Elemento | Padrões (✔ conferidos no modelo compilado ou na doc) |
|---|---|
| `geom` | `contype` 1 · `conaffinity` 1 (colide se `ct₁&ca₂≠0` ou `ct₂&ca₁≠0`) · `condim` 3 (1/3/4/6) · `group` 0 · `friction` 1 0.005 0.0001 · `solref` 0.02 1 · `solimp` 0.9 0.95 0.001 0.5 2 · `margin` 0 · `gap` 0 · `density` 1000 · `rgba` 0.5 0.5 0.5 1 · `priority` 0 · `solmix` 1 |
| `joint` | `axis` 0 0 1 · `pos` 0 · `range` 0 0 · `limited` auto · `damping` `stiffness` `armature` `frictionloss` 0 · `ref` `springref` 0 · `solreflimit` 0.02 1 · `margin` 0; `stiffness`/`damping` aceitam até 3 coeficientes (polinômio, 3.7.0) ✔ |
| `body` / `site` | `body`: `mocap` false (só filho do world, sem junta) · `gravcomp` 0 · `sleep` auto. `site`: `type` sphere · `size` 0.005 · não altera a massa ✔ |

- `group` 0–2 aparece no viewer e 3–5 fica oculto (`MjvOption.geomgroup=[1,1,1,0,0,0]` ✔).
- `autolimits` (padrão **true** desde 3.0.0): `range` liga o limite sozinho (idem `ctrllimited`/`forcelimited`/`actlimited` dos atuadores e `limited` de tendões). ⚠ ✔ `range` invertido ou nulo (`1 -1`, `0.5 0.5`) ⇒ **sem limite e sem erro**; com `limited="true"` ⇒ erro `range[0] should be smaller than range[1]`. Com `autolimits="false"`, `range` sem `limited` ⇒ erro.
- `<freejoint>` ≡ `<joint type="free" stiffness="0" damping="0" frictionloss="0" armature="0"/>` mas **não herda defaults de joint**. Com `align="true"` (ou `compiler alignfree="true"`) o frame do corpo livre vai para o frame inercial: geom em `pos="0.1 0 0" euler="0 0 30"` ⇒ `qpos0=[0.1 0 1 0.9659 0 0 0.2588]` (era `[0 0 1 1 0 0 0]` ✔), o que invalida keyframes antigos.

| Orientação (no máx. 1 por elemento) | Significado |
|---|---|
| `quat` (padrão `1 0 0 0`) | **[w x y z]** (SciPy/ROS: [x y z w]); é normalizado; `0 0 0 0` ⇒ erro |
| `axisangle="x y z a"` | eixo (qualquer norma) + ângulo |
| `euler="a b c"` | sequência `compiler eulerseq` (padrão `xyz`): minúsculas = intrínseco, MAIÚSCULAS = extrínseco (URDF "rpy" = `XYZ`) |
| `xyaxes="x1 x2 x3 y1 y2 y3"` | eixos X e Y (Y é ortogonalizado); natural em câmeras (X=direita, Y=cima) |
| `zaxis="x y z"` | rotação mínima de +Z até o vetor; ideal p/ geoms de revolução e luzes |
```python
import mujoco
def quat(attr, compiler=""):
    xml = f'<mujoco>{compiler}<worldbody><body name="b" {attr}><geom size=".1"/></body></worldbody></mujoco>'
    return mujoco.MjModel.from_xml_string(xml).body("b").quat.round(4)   # [w x y z]
for attr in ('quat="0.7071068 0 0 0.7071068"', 'axisangle="0 0 1 90"', 'euler="0 0 90"', 'xyaxes="0 1 0 -1 0 0"'):
    print(attr.ljust(32), quat(attr))                                      # as 4 formas = 90° em Z
print(quat('euler="30 40 50"', '<compiler eulerseq="xyz"/>'))              # xyz minúsculo = intrínseco (= SciPy 'XYZ')
print(quat('euler="30 40 50"', '<compiler eulerseq="XYZ"/>'))              # XYZ maiúsculo = extrínseco (= SciPy 'xyz')
try: quat('quat="1 0 0 0" euler="0 0 90"')
except ValueError as e: print(str(e).splitlines()[0])                       # multiple orientation specifiers are not allowed
```
- ⚠ ✔ A caixa (maiúscula/minúscula) do `eulerseq` é **o inverso** da do SciPy (acima). Um `euler`/`axisangle`/`xyaxes`/`zaxis` herdado de `<default>` **vence** um `quat` escrito no elemento (geom/site/camera): o `quat` é ignorado em silêncio; escrever `euler` no elemento sobrescreve. Evite orientação em defaults.
- Unidades: não impostas (qualquer sistema consistente; MKS recomendado; só `gravity` e `density` 1000 trazem valores MKS). `angle` padrão **degree** converte `euler`, `axisangle` e `range` de hinge/ball; `mjModel`/`mjData` são sempre rad; `camera fovy` e `light cutoff` são sempre graus.

## 3. Inércia e massa
- Corpo **sem `<inertial>`**: massa e inércia vêm da soma dos geoms com `group` ∈ `compiler inertiagrouprange` (padrão `0 5`; geom de grupo 6+ não conta ✔). `density` padrão **1000** kg/m³ (água); `mass` do geom vence `density`; `shellinertia="true"` (só primitivas) muda `density` para massa/área. Esfera r=0,1 ⇒ 4,1888 kg ✔. Só massa/inércia do corpo chegam ao `mjModel` (não há `geom_mass`).
- `compiler inertiafromgeom`: `auto` (padrão: infere só se faltar `<inertial>`) · `true` (geoms **sobrescrevem** `<inertial>` ✔) · `false` (exige `<inertial>`).
- `<inertial pos mass diaginertia|fullinertia>`: `pos` obrigatório; `fullinertia` = M11 M22 M33 M12 M13 M23 (diagonaliza sozinho ✔); a presença do elemento desliga a inferência. `Δ doc` ✔ sem `diaginertia`/`fullinertia` o erro é o genérico de massa nula (não "atributo obrigatório").
- Massa 0 num corpo móvel (sem geom, `mass="0"`, `inertiafromgeom="false"` sem `<inertial>`) ⇒ `mass and inertia of moving bodies must be larger than mjMINVAL` ✔. Remédios globais: `boundmass`/`boundinertia` (piso, 0 = off) · `settotalmass` (escala para a massa total; −1 = off) · `balanceinertia="true"` (corrige em silêncio inércia que viola A+B≥C).
- **Visual + collision no mesmo corpo dobram a massa** (grupos 2 e 3 ∈ `0 5`). Correções ✔ (bloco abaixo): `inertiagrouprange="3 3"` (só a colisão conta; ⚠ geoms de grupo 0 deixam de contar ⇒ corpo sem massa ⇒ erro) · `mass="0"`/`density="0"` na classe visual (⚠ se for o único geom ⇒ erro) · `<inertial>` explícito = **padrão da Menagerie** (`panda.xml`: 11 `<inertial>` em 11 corpos; nenhum XML do espelho local da Menagerie usa `inertiagrouprange`). `discardvisual="true"` **não** corrige (o compilador grava um `<inertial>` explícito com a massa já dobrada, conforme a doc).
- "visual" e "collision" são só **nomes de classe**: quem separa é `contype="0" conaffinity="0"` + `group` (visual 2, collision 3; é assim que a Menagerie define as classes).
```python
import mujoco
DEF = '<default><default class="visual"><geom contype="0" conaffinity="0" group="2" {v}/></default><default class="collision"><geom group="3"/></default></default>'
def massa(compiler="", v="", inertial=""):
    xml = f'''<mujoco>{compiler}{DEF.format(v=v)}<worldbody><body name="b"><freejoint/>{inertial}
      <geom class="visual" size="0.1"/><geom class="collision" size="0.1"/></body></worldbody></mujoco>'''
    return round(float(mujoco.MjModel.from_xml_string(xml).body("b").mass[0]), 4)
print(massa())                                                   # 8.3776  dobrou: grupos 2 e 3 ∈ inertiagrouprange "0 5"
print(massa('<compiler inertiagrouprange="3 3"/>'))              # 4.1888  só a colisão conta
print(massa(v='mass="0"'), massa(v='density="0"'))               # 4.1888 4.1888  visual sem massa
print(massa('<compiler discardvisual="true"/>'))                 # 8.3776  discardvisual NÃO corrige
print(massa(inertial='<inertial pos="0 0 0" mass="4.19" diaginertia="0.0168 0.0168 0.0168"/>'))   # 4.19  padrão Menagerie
```
**Malhas** (`<mesh inertia=…>`; também aceito em `<default><mesh>`): o padrão em 3.15 continua `legacy` (a doc 3.4 prometia `convex`; Δ doc). Prisma em U (volume exato 7 m³, casco convexo 9 m³, ρ=1000) ✔:

| `inertia` | Algoritmo | Massa |
|---|---|---|
| `legacy` (padrão) | algoritmo antigo; **superestima** o volume de malhas não convexas | 8617,5 kg |
| `convex` (recomendado) | volume do casco convexo | 9000 kg |
| `exact` | volume exato; exige malha estanque e com faces para fora | 7000 kg |
| `shell` | massa na superfície; `density` = massa/área | 30000 kg (área 30 m²) |
```python
import mujoco, numpy as np
P = [(0,0),(3,0),(3,3),(2,3),(2,1),(1,1),(1,3),(0,3)]                  # seção em U no plano XZ (CCW), área 7 m²
T = [(0,1,4),(0,4,5),(1,2,3),(1,3,4),(0,5,6),(0,6,7)]; n = len(P)     # triangulação das tampas
V = [(x,0,z) for x,z in P] + [(x,1,z) for x,z in P]                    # extrudada 1 m em Y ⇒ volume 7 m³, casco convexo 9 m³
F = [(i,k,j) for i,j,k in T] + [(n+i,n+j,n+k) for i,j,k in T]
F += [f for i in range(n) for f in ((i,(i+1)%n,n+(i+1)%n), (i,n+(i+1)%n,n+i))]   # laterais
V, F = np.array(V, float), np.array(F)
if sum(np.dot(V[a], np.cross(V[b], V[c])) for a, b, c in F) < 0: F = F[:, ::-1]  # volume com sinal > 0 ⇒ faces para fora
for modo in ("legacy", "convex", "exact", "shell"):
    xml = f'''<mujoco><asset><mesh name="u" vertex="{' '.join(map(str, V.ravel()))}" face="{' '.join(map(str, F.ravel()))}" inertia="{modo}"/></asset>
      <worldbody><body name="b"><freejoint/><geom type="mesh" mesh="u"/></body></worldbody></mujoco>'''
    print(modo.ljust(7), round(float(mujoco.MjModel.from_xml_string(xml).body("b").mass[0]), 1))
```
- `exact` com faces invertidas ⇒ `mesh volume is negative (misoriented triangles)`. `shellinertia="true"` num geom `mesh` (inclusive via default) é **erro** em 3.15 (a doc e o changelog 3.3.0 dizem "ignorado"; Δ doc) ⇒ use `mesh inertia="shell"`.
- `gravcomp` (no `<body>`, padrão 0): força para cima no CoM = fração do peso; `1` anula a gravidade (✔ `qacc_z=0`), `0.5` ⇒ metade (✔ −4,905), `>1` ⇒ flutuação. `joint actuatorgravcomp="true"` conta a compensação como força de atuador (respeita `actuatorfrcrange`).

## 4. Malhas e assets
- Fontes de malha: `file` (STL/OBJ; MSH legado), `vertex` (+ `face` opcional) ou `builtin` (`sphere hemisphere cone supersphere supertorus wedge plate` + `params`; ex.: `builtin="sphere" params="2"` ⇒ 162 vértices ✔; 3.3.5). Sem `name`, o nome da malha = arquivo sem caminho/extensão ✔.
- ✔ **`<mesh vertex="…">` sem `face` = nuvem de pontos ⇒ o compilador constrói o casco convexo** (é o que `docs/upstream/mujoco/model/car/car.xml` faz). Exige ≥ 4 vértices não coplanares (`at least 4 vertices required` / `coplanar vertices`). Tetraedro unitário ⇒ 166,667 kg.
- ⚠ ✔ `<geom mesh="m"/>` **sem `type="mesh"`** ajusta uma ESFERA à malha (`geom_dataid=-1`), sem erro nem aviso; escreva `type="mesh"` (ou use uma classe com `type="mesh"`, como a Menagerie).
- **Colisão usa o casco convexo** (formas côncavas: vários geoms convexos). `maxhullvert` (padrão −1 = sem limite; deve ser > 3, senão `maxhullvert must be larger than 3`) limita os vértices do casco: esfera de 162 vértices ⇒ casco de 20 / 8 / 4 ✔.
- ✔ **Recentragem**: o compilador move a malha para o centro de massa e a alinha aos eixos principais; `geom_pos`/`geom_quat` compilados ≠ XML (`pos="5 0 0"` ⇒ `geom_pos=[5.25 .25 .25]`; `mesh_pos`/`mesh_quat` guardam o deslocamento). Malhas com origem na junta funcionam sem ajuste; `refpos`/`refquat` re-referenciam vértices.
- `scale` (3 fatores; negativo espelha; ×2 ⇒ massa ×8 ✔) é a única forma de dimensionar: o `size` do geom é ignorado em `mesh`/`hfield`.
- Caminhos ✔: `compiler meshdir`/`texturedir` (`assetdir` define os dois) são relativos ao **diretório do XML principal**, não ao cwd (`from_xml_string` não tem XML principal: aí vale o **cwd**; use `from_xml_path` ou `meshdir` absoluto); sem `meshdir`, um arquivo em subdiretório ⇒ `Error opening file`; `strippath="true"` descarta o caminho presente no nome. Texturas só PNG/KTX (3.12.0).
- Texturas/materiais: `<texture type="2d|cube|skybox" builtin="checker|gradient|flat" rgb1 rgb2 width height>` + `<material texture texrepeat texuniform reflectance rgba>`; textura 2d/material sem `name` ⇒ `empty name` ✔ (skybox dispensa); em 3.3.3 `colorspace` passou a `auto` (PNG sRGB renderiza diferente; `linear` restaura).
- `<hfield name nrow ncol elevation size="rx ry zmax zbase">` ✔ (elevação normalizada a [0,1]; no `mjModel` as linhas ficam de baixo para cima) + `<geom type="hfield" hfield="…">`. `<asset><model name file/></asset>` declara sub-modelos para `<attach>` (§5).

## 5. Defaults, composição, keyframes e custom
```xml
<mujoco>
  <default>                                          <!-- topo = "main"; nomes de classe únicos no modelo todo -->
    <joint damping="0.5" armature="0.01"/>
    <default class="visual"><geom type="mesh" contype="0" conaffinity="0" group="2"/></default>
    <default class="collision"><geom group="3" friction="0.8 0.005 0.0001"/></default>
    <default class="roda"><geom type="cylinder" size="0.1 0.03" euler="90 0 0"/></default>
  </default>
  <asset><mesh name="m" vertex="0 0 0  1 0 0  0 1 0  0 0 1" scale="0.1 0.1 0.1"/></asset>
  <worldbody>
    <body name="base" pos="0 0 0.5" childclass="collision">   <!-- descendentes herdam, salvo class= explícito -->
      <freejoint/>                                            <!-- NÃO herda damping/armature de <joint> -->
      <inertial pos="0 0 0" mass="2" diaginertia="0.01 0.01 0.01"/>   <!-- massa explícita: par visual+collision não dobra -->
      <geom name="col" type="box" size="0.1 0.1 0.05"/>
      <geom name="vis" class="visual" mesh="m"/>
      <body name="roda_e" pos="0 0.15 0"><joint name="eixo" axis="0 1 0"/><geom class="roda"/></body>
    </body>
  </worldbody>
</mujoco>
```
- **Defaults** (como CSS) ✔: filho herda do pai e sobrescreve; classe ativa = `class=` explícito > `childclass` do `<body>`/`<frame>` ancestral mais próximo > classe de topo (um `class=` **substitui** o `childclass`, não se funde: `roda` acima não herda `collision`). Valores escritos no elemento vencem os do default. Existem defaults para `mesh material joint geom site camera light pair equality tendon` e os atalhos de atuador (`<default><body/>` ⇒ `unrecognized element`).
- ⚠ Classe de topo: sem nome = `main`, **não renomeável** (`top-level default class 'main' cannot be renamed`; `Δ doc`: `modeling.rst` diz o contrário); nomes únicos no modelo inteiro (`repeated default class name`, até em ramos diferentes); `class`/`childclass` inexistente ⇒ `unknown default class name`. Dois `<default>` de topo se fundem.
- **`<include file>`** ✔: cola no parser os filhos da raiz do arquivo (caminho relativo ao XML principal); cada arquivo **só 1×** (`File … already included`); globais repetidos valem pela última definição (um `compiler angle="radian"` incluído muda o modelo todo); nomes continuam únicos. O manual prefere `attach`.
- **`<attach model body|frame prefix>`** (3.2.0; sem `model` = self-attach e `frame=` desde 3.11.0) ✔: opera no compilador; `prefix` **obrigatório** (`required attribute missing: 'prefix'`) e aplicado a corpos, juntas, geoms, atuadores, sensores, materiais…; sem `body`/`frame` anexa o mundo inteiro do filho num frame novo; o filho mantém o próprio `angle`; todos os assets do filho são copiados; keyframes: limitações. `compiler conflict` (3.10.0) decide globais divergentes (ex.: `timestep`): `warning` (padrão, o pai vence), `merge` (mínimo/máximo; o padrão vai mudar para ele), `error` ✔.
```python
import mujoco
filho = '<mujoco model="robo"><worldbody><body name="base"><geom size=".1"/><body name="braco" pos="0 0 .1"><joint name="j"/><geom size=".05"/></body></body></worldbody></mujoco>'
pai = '''<mujoco>
  <asset><model name="robo" file="robo.xml"/></asset>                  <!-- sub-modelo disponível para attach -->
  <worldbody>
    <frame pos="1 0 0" euler="0 0 90"><attach model="robo" body="base" prefix="r1_"/></frame>
    <attach model="robo" body="base" prefix="r2_"/>                     <!-- prefix é OBRIGATÓRIO -->
  </worldbody>
</mujoco>'''
with mujoco.MjVfs() as vfs:                                            # arquivos virtuais; com arquivos reais basta from_xml_path
    vfs["robo.xml"] = filho.encode()
    m = mujoco.MjModel.from_xml_string(pai, vfs=vfs)
print([m.body(i).name for i in range(m.nbody)], [m.joint(i).name for i in range(m.njnt)])   # r1_base r1_braco … r1_j r2_j
```
- **`<frame>`** (3.1.0): transformação pura dos filhos diretos (`pos`, orientação, `childclass`); não vira corpo; preservado ao salvar o XML desde 3.14.0. **`<replicate count sep offset euler>`** (3.1.5) ✔: duplica os filhos com deslocamento/rotação acumulados e sufixos de índice com o mínimo de dígitos (`count=12` ⇒ `b00…b11`); `<joint>` não pode ser filho direto (`joint cannot be a direct child of replicate`; envolva em `<body>`). `Δ doc`: o exemplo do manual não compila (`<accelerometer site=>` aponta para um `<geom>`; troque por `<site>`).
- **`composite`**: só resta `type="cable"` (cadeia de corpos com juntas ball; o `<plugin>` interno exige `<extension><plugin plugin="mujoco.elasticity.cable"/></extension>`, senão `unrecognized plugin` ✔). **`flexcomp`** = macro para `flex` + corpos com 3 juntas slide (`dof="full"`); `mujoco.mj_saveLastXML("saida.xml", m)` ✔ mostra a expansão (traz `<flex>`). `Δ doc` ✔: `edge equality` padrão é `false` (o exemplo do manual supõe `true`): sem ele o flex fica sem restrição (aviso `not rigid and has no equality constraints`).
```xml
<mujoco>
  <extension><plugin plugin="mujoco.elasticity.cable"/></extension>
  <worldbody>
    <frame name="mesa" pos="1 0 0" euler="0 0 90">                   <!-- transformação pura: não gera corpo -->
      <geom name="tampo" type="box" size="0.3 0.3 0.02"/>
    </frame>
    <replicate count="3" sep="_" offset="0.3 0 0">                    <!-- bola_0 bola_1 bola_2; joint só dentro de body -->
      <body name="bola" pos="0 0.5 0.5"><freejoint name="fj"/><geom name="g" size="0.05"/></body>
    </replicate>
    <flexcomp name="pano" type="grid" dim="2" count="4 4 1" spacing="0.1 0.1 0.1" pos="-1 0 1" radius="0.01" mass="0.2">
      <pin id="0 3"/><edge equality="true"/><contact selfcollide="none"/>   <!-- edge equality: padrão false em 3.15 -->
    </flexcomp>
    <body name="ancora" pos="0 -1 1">
      <composite prefix="c" type="cable" curve="s 0 0" count="6 1 1" size="0.5" initial="none">
        <plugin plugin="mujoco.elasticity.cable"><config key="bend" value="1e6"/><config key="twist" value="1e6"/></plugin>
        <joint kind="main" damping="0.01"/><geom type="capsule" size="0.005"/>
      </composite>
    </body>
  </worldbody>
</mujoco>
```
- **`<keyframe><key name time qpos qvel act ctrl mpos mquat/>`** ✔: vetores curtos são completados (qpos com `qpos0`; resto 0); longos ⇒ `invalid qpos size, expected N, got M`; `qvel` tem **nv** números (a doc escreve nq: `Δ doc`); `<size nkey>` reserva chaves extras (= `qpos0`). Carregar: `mujoco.mj_resetDataKeyframe(m, d, i)`. Em corpo com `free`, qpos = `x y z w x y z`.
- **`<custom>`** ✔: `numeric` (`name` obrigatório; `data` ou `size`), `text` (`data` ou CDATA, 3.13.0), `tuple` (`element objtype objname prm`). Python: `m.numeric("n").data`, `m.tuple("t")`; texto via `m.text_adr`/`m.text_data` (não existe `m.text(...)`). Bom lugar p/ valores esperados dos testes (templates da skill).

## 6. `<visual>`, luzes, câmeras, `<statistic>`
- `<visual>` pode **repetir**: os blocos são **mesclados atributo a atributo** (o último valor de cada atributo vence) ✔: `<global azimuth="60" offwidth="320"/>` + 2º bloco `<global elevation="-5"/>` ⇒ azimuth 60, elevation −5, offwidth 320. Sub-elementos 1× por bloco. A "regra do bloco único" de `docs/upstream/mujoco/doc/skills/rendering/SKILL.md` (reset silencioso) está errada (ficha Q16 + teste acima).
- `global`: `azimuth` 90 · `elevation` −45 · `fovy` 45 · `offwidth` 640 · `offheight` 480 (**teto do render offscreen** ✔: `Renderer(width=640)` com 320 ⇒ `Image width 640 > framebuffer width 320`) · `cameraid` −1. `quality`: `shadowsize` 4096, `offsamples` 4. `headlight`: `ambient` .1 `diffuse` .4 `specular` .5. `map`: `znear` .01 `zfar` 50 `force` `torque`. `scale`: tamanho de setas/juntas/contatos. `rgba`: `haze`, `contactpoint`…
- `<statistic>` ✔: `center`/`extent` (meia aresta do bounding box; a câmera livre começa a 1,5×`extent`), `meansize` (unidade das `visual/scale`), `meanmass`, `meaninertia`; omitidos, são calculados.
- `<light>`: `type` spot (padrão) `directional` `point` `image`; `directional="true"` é **legado** (aceito ✔; os templates do laboratório o usam): prefira `type="directional"`. `mode` fixed/track/trackcom/targetbody/targetbodycom, `dir` 0 0 −1, `castshadow` true, `diffuse` .7, `cutoff` 45° (sempre graus).
- `<camera>`: olha para −Z do próprio frame (+X direita, +Y cima; use `xyaxes`); `fovy` 45; `mode` `fixed` (padrão) · `track` (offset constante no mundo) · **`trackcom`** (offset relativo ao CoM da subárvore; no `worldbody` segue o modelo todo) · `targetbody`/`targetbodycom` (+`target`) ✔; `projection` perspective/orthographic (em orthographic `fovy` é comprimento); `resolution`/`focal`/`sensorsize` p/ intrínsecos.

## 7. Removidos ou renomeados entre 3.0 e 3.15
| Item (XML) | Versão | Substituto / efeito em 3.15 (✔ = erro medido) |
|---|---|---|
| `option collision` | 3.0.0 | removido ✔. `all`: apague; `dynamic`: apague os `<pair>`; `predefined`: `contype=conaffinity=0` global em `<default><geom>` |
| `joint actuatorforcerange` / `actuatorforcelimited` | 3.0.0 | `actuatorfrcrange` / `actuatorfrclimited` ✔ |
| `compiler autolimits` (padrão) | 3.0.0 | `false` → **`true`**: `range` sem `limited` passou a ligar o limite |
| `composite` `rope` `cloth` | 3.0.0 | removidos → `cable` / `flexcomp` com `elastic2d` (p/ `cloth` a mensagem ainda sugere `shell`, plugin removido em 3.3.3) ✔ |
| `sensor noise` · flag `sensornoise` | 3.1.4 | `noise` aceito mas **sem efeito** (só guarda o desvio) ✔; a flag ⇒ erro ✔ |
| `option mpr_iterations` / `mpr_tolerance` | 3.2.3 | `ccd_iterations` / `ccd_tolerance` ✔ |
| `compiler exactmeshinertia` · `compiler convexhull` | 3.2.5 | `mesh inertia="exact"` · removido (casco sempre calculado) ✔ |
| `composite` `box` `cylinder` `sphere` · `rope` `loop` | 3.2.5 · 3.2.6 | `flexcomp` · `cable`/`flexcomp`: `invalid keyword` / `composite type is deprecated` ✔ |
| `composite` `grid` `particle` | 3.3.0 | `flexcomp` · `replicate` ✔ |
| `geom shellinertia` em mesh | 3.3.0 | ignorado → em 3.15 é **erro** ✔; use `mesh inertia="shell"` |
| `light directional` | 3.3.3 | `type="spot/directional/…"`; o atributo antigo ainda é aceito ✔ |
| `option flag passive` | 3.3.6 | `flag spring` + `flag damper` ✔ (desligue os dois p/ o efeito antigo) |
| `camera orthographic` | 3.5.0 | `projection="orthographic"` ✔ (aceita `perspective`) |
| `margin`/`gap` de 2 geoms: máx. → **soma** | 3.5.0 | contato = soma dos `margin` ✔ |
| semântica de `margin`/`gap` | 3.9.0 | ver abaixo |
| textura binária própria (`image/vnd.mujoco.texture`) | 3.12.0 | só PNG e KTX |
| `visual global bvactive` (padrão) · `flex contact internal` | 3.12.0 · 3.15.0 | `true` → `false` · atributo removido ✔ |

- Padrões que passaram a **ligados**: `nativeccd` (3.3.0), `island` (3.3.6), `multiccd` (3.8.0) ✔; `sleep_tolerance` 1e-4 → 1e-3 (3.11.0). Fora do XML: `mjData.qM` removido (3.11.0 ⇒ `data.M`) e `mj_fullM(m, d, dst)` (3.10.0).
- Adições para reconhecer: `frame` 3.1.0 · `replicate` 3.1.5 · `attach` 3.2.0 · `maxhullvert` 3.2.0 · `alignfree`/`freejoint align` 3.2.3 · `saveinertial` 3.3.1 · `mesh builtin` 3.3.5 · `compiler conflict` 3.10.0 · `geom surfacevel`/`adhesion` e `body simple` 3.11.0 · atuadores `dcmotor` 3.7.0, `orientation` 3.11.0, `pid` 3.12.0 · schema único `mjcf.schema` 3.12.0 · integrador `discrete` e `site type="mesh"` 3.13.0.
- **`margin`/`gap` (3.9.0)**: antes, `margin` = limiar de detecção e a força só vinha com `dist < margin − gap`. Agora `margin` = **inflação** do geom: detecta com `dist < margin + gap`, gera força com `dist < margin`; contatos em `[margin, margin+gap)` ficam em `data.contact` **inativos** (`efc_address = −1`; úteis p/ adesão). **Migração**: `margin_novo = margin_antigo − gap_antigo`, `gap_novo = gap_antigo` (padrão 0/0 não muda; `margin` negativo permitido, mantenha `margin + gap ≥ 0`); a soma dos `margin` dos dois geoms vale desde 3.5.0 (margens 0,02+0,03 ⇒ 0,05 ✔). Doc: `docs/upstream/mujoco/doc/computation/index.rst` (`coMarginGap`).
```python
import mujoco
def contato(margin="0", gap="0"):
    xml = f'''<mujoco><worldbody><geom type="plane" size="1 1 .1"/>
      <body pos="0 0 0.15"><freejoint/><geom size="0.1" margin="{margin}" gap="{gap}"/></body></worldbody></mujoco>'''
    m = mujoco.MjModel.from_xml_string(xml); d = mujoco.MjData(m); m.opt.gravity[:] = 0
    mujoco.mj_forward(m, d)                                      # distância real esfera–plano = 0.05
    return (d.ncon, d.contact[0].efc_address, d.nefc) if d.ncon else "sem contato"
print(contato())                  # sem contato
print(contato(gap="0.1"))         # (1, -1, 0)  detectado, INATIVO (efc_address=-1: sem força)
print(contato(margin="0.06"))     # (1, 0, 4)   ativo: gera força
```
- **Migrar um modelo antigo**: (1) compile e corrija cada `unrecognized attribute` pela tabela; (2) `gap > 0` ⇒ `margin -= gap`; (3) revise `range` sem `limited` e `mesh inertia` (`legacy` superestima); (4) keyframes de corpo livre: `align`/`alignfree` mudam `qpos0`; (5) rode `python3 .agents/mujoco-lab-agent-skill/scripts/inspect_model.py modelo.xml` (compila, lista riscos, teste de fumaça). O compilador acusa 1 erro por vez; este scanner ✔ lista todos os atributos legados de uma vez:
```python
import re
LEGADO = {  # padrão → o que fazer em 3.15 (tabela §7); o compilador acusa 1 erro por vez, o scanner lista todos
    r'<option[^>]*\bcollision=': 'removido (3.0.0)',
    r'\bactuatorforce(range|limited)=': 'actuatorfrcrange / actuatorfrclimited',
    r'\bmpr_(iterations|tolerance)=': 'ccd_iterations / ccd_tolerance',
    r'<compiler[^>]*\b(exactmeshinertia|convexhull)=': 'mesh inertia="exact" / removido (3.2.5)',
    r'<flag[^>]*\b(passive|sensornoise)=': 'flag spring + damper / removido',
    r'<camera[^>]*\borthographic=': 'projection="orthographic"',
    r'<composite[^>]*\btype="(particle|grid|rope|cloth|loop|box|cylinder|sphere|ellipsoid)"': 'flexcomp / replicate / cable',
    r'<light[^>]*\bdirectional=': 'type="directional" (legado, ainda aceito)',
    r'<contact[^>]*\binternal=': 'removido (3.15.0)',
}
def audita(xml): return [(m.group(0)[-30:], dica) for pat, dica in LEGADO.items() for m in re.finditer(pat, xml)]
legado = '<mujoco><option collision="all" mpr_iterations="9"/><worldbody><light directional="true"/><camera orthographic="true"/></worldbody></mujoco>'
for item in audita(legado): print(item)
print(audita('<mujoco><visual><global orthographic="true"/></visual><camera projection="orthographic"/></mujoco>'))   # [] (sem falso positivo)
```

## 8. Correções ao relatório do usuário (§2.5)
Fonte: `docs/relatorio-tecnico-original.md` §2.5 × ficha `pesquisas/conhecimento/Q5.md` (vereditos) + testes acima.

| Afirmação do relatório | Veredito | Correção ao relatório do usuário |
|---|---|---|
| MJCF "quase como um compilador" que converte geometrias em "ponteiros puros" | parcial | A analogia é do manual (parser → mjSpec → compilador → `mjModel`); o compilador calcula inércia, centraliza malhas, expande macros. "Ponteiros puros" é impreciso: o `mjModel` é um conjunto de arrays planos num buffer único (`m.nbuffer`), referências são **índices** (`geom_bodyid`, `body_geomadr`) e `m.geom_size` é uma view NumPy sem cópia (`OWNDATA=False` ✔) |
| "`<compiler>` e `<option>` definem passo, gravidade, viscosidade, solver" | parcial | Isso é `<option>` (cópia de `mjModel.opt`, editável em runtime). `<compiler>` só configura parse/compilação (`angle`, `meshdir`, inferência de inércia…) e não deixa rastro no `mjModel` |
| Nós principais: compiler, option, worldbody, body, joint (hinge, ball), geom, tendon, actuator | parcial | São 17 seções (§1); `body/joint/geom` vivem aninhados; `joint` tem 4 tipos (**free** e **slide** faltam); faltam `asset default sensor contact equality keyframe visual size statistic`. `<joint>` cria graus de liberdade, não "restrições" |
| `<geom>` separa visual (`class="visual"`) de colisão (`class="collision"`) | correta, com ressalvas | Nomes são convenção; quem separa é `contype/conaffinity/group`. Sem `<inertial>`, o par **dobra a massa** (8,3776 kg vs 4,1888); corrija com `inertiagrouprange="3 3"`, `mass/density="0"` no visual ou `<inertial>` (§3). `discardvisual` não corrige |
| Inércia inferida do volume dos geoms com densidade da água (1000) | correta, com precisões | Só se não houver `<inertial>`; só geoms em `inertiagrouprange`; `mass` do geom vence `density`; malhas `legacy` superestimam não convexas (8617,5 vs 7000 kg); MKS não é imposto |
| URDF "sem otimização direta de dados", ao contrário do MJCF | parcial | A diferença estrutural é real (links+joints vs árvore aninhada); "sem otimização" não tem respaldo: mesmo pipeline até o `mjModel`. URDF liga `fusestatic` e `discardvisual` e usa `angle=radian`; não é validado por schema (typos passam em silêncio) |

## Exemplos para copiar e aprofundar
- Laboratório: `.agents/mujoco-lab-agent-skill/assets/templates/{blank,pendulum,arm,quadrotor,car}/model.xml` (corpo livre; hinge + sensores; braço com `position`, mocap e `gravcomp`; motores em sites; carro com `condim=4`) e `models/triangulo_invertido.xml` (malha só por `vertex` + `<custom><numeric>` com valores esperados). Todos compilam em 3.15.0 ✔.
- Oficiais (espelho 3.15.0): `docs/upstream/mujoco/model/hammock/hammock.xml` (`<model>` + `<frame>` + `<attach>` + `flexcomp`), `docs/upstream/mujoco/model/{replicate,flex,humanoid}/`; Menagerie: `docs/upstream/mujoco_menagerie/franka_emika_panda/panda.xml` (classes `visual`/`collision` + `<inertial>` em todos os corpos).
- Doc: `docs/upstream/mujoco/doc/{XMLreference,modeling,overview,changelog,XMLschema}.rst` (âncoras `body-geom`, `compiler`, `asset-mesh`; `CDefault`, `COrientation`, `CInclude`, `CComposite`) e `docs/upstream/mujoco/doc/programming/modeledit.rst` (attach e `conflict`).

## Armadilhas
| Sintoma (mensagem ✔) | Causa | Correção |
|---|---|---|
| `Schema violation: unrecognized attribute/element` (`Element 'geom', line N`) | atributo removido/renomeado (§7) ou typo | `docs_search.py --attr elem.attr`; tabela §7 |
| `repeated name 'a' in geom` | nomes devem ser únicos por tipo (também no parse, desde 3.4.0) | renomeie; em `attach`/`replicate` use `prefix`/`sep` |
| `mass and inertia of moving bodies must be larger than mjMINVAL` | corpo móvel sem geom/`<inertial>`, `mass="0"`, geom fora de `inertiagrouprange`, `<inertial>` sem inércia | §3; `boundmass` |
| `multiple orientation specifiers are not allowed` | 2+ de `quat axisangle euler xyaxes zaxis` | deixe 1 (e evite orientação em defaults) |
| `size 1 must be positive in geom` | `size` omitido ou com menos números (box = 3) | complete o `size` |
| `inertia must satisfy A + B >= C; use 'balanceinertia'…` | inércia diagonal impossível | corrija ou `compiler balanceinertia="true"` |
| `Error opening file 'x.obj'` | `file` relativo ao XML principal (ao cwd em `from_xml_string`); falta `meshdir` | `from_xml_path`, `compiler meshdir`/`assetdir` (absoluto) ou `strippath` |
| `at least 4 vertices required` · `coplanar vertices` | `<mesh>` sem `file` nem vértices suficientes | ≥ 4 pontos não coplanares; placa fina ⇒ `box` |
| `mesh volume is negative (misoriented triangles)` | `inertia="exact"` com faces invertidas | triângulos CCW vistos de fora |
| `free joint can only be used on top level` | `freejoint` em corpo que não é filho do world | use `ball`/`hinge`/`slide` ou suba o corpo |
| `ball followed by rotation` · `more than 6 dofs` | `ball`+`hinge`; `free`+outra junta | um tipo rotacional por corpo; `free` sozinho |
| `File 'x.xml' already included` | mesmo `<include>` 2× | 1× só, ou `attach` com `prefix` |
| `required attribute missing: 'prefix'` | `<attach>` sem `prefix` | adicione `prefix` |
| `keyframe '': invalid qpos size, expected N, got M` | vetor da `<key>` longo demais | `nq` (qpos), **nv** (qvel), `nu` (ctrl) números |
| `unrecognized plugin 'x'` · `plugin x not found` | `<plugin>` sem `<extension>` · plugin inexistente | declare em `<extension>`; confira o nome |
| `mocap body '' is not a fixed child of world` · `plane only allowed in static bodies` | `mocap`/`plane` em corpo com junta ou fora do world | mocap: filho do world sem junta; plane: no world |
| `XML parse error 14` · `Unrecognized XML model type` | XML malformado · raiz ≠ `<mujoco>` | feche as tags; raiz `<mujoco>` |
| (silencioso) massa 2× maior | visual+collision no mesmo corpo | §3 |
| (silencioso) a malha não aparece/colide como esfera | `<geom mesh="m"/>` sem `type="mesh"` | `type="mesh"` ou classe com `type="mesh"` |
| (silencioso) `quat` do elemento ignorado | `euler`/… herdado de `<default>` vence o `quat` | use `euler` no elemento ou tire a orientação do default |
| (silencioso) junta sem limite apesar do `range` | `range` invertido/nulo com `autolimits` | `range="min max"` com min < max |
| (silencioso) ângulos "errados" num arquivo incluído | `compiler angle` do arquivo incluído vence (último) | mesma unidade em todos os arquivos, ou `attach` |
