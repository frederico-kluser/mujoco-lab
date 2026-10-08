# Mapa da documentação oficial 3.15, histórico de quebras 3.0→3.15 e erros das skills oficiais

Onde achar cada tema no espelho `docs/upstream/` (tag 3.15.0), o que mudou ou quebrou entre 3.0.0 e 3.15.0, como validar um snippet antigo e o que está errado nas skills oficiais `doc/skills/*`.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: ficha Q16; `docs/upstream/mujoco/doc/{index,overview,modeling,XMLreference,python,mjx,changelog}.rst`, `doc/{programming,computation,mjwarp,skills}/*`, `VERSIONING.md`, READMEs de `mujoco_warp`, `mujoco_playground`, `mujoco_mpc`, `mujoco_menagerie`; testes locais (venv 3.15.0, gcc).

## Quando ler este arquivo
- Antes de usar API, atributo ou snippet "de memória" (seu treino conhece ≤ 3.3) ou de tutorial antigo: §3 (tabela de quebras) e §2 (probe executável).
- Para saber **onde** a doc oficial local trata de um tema e qual modo do `docs_search.py` usar: §1.
- Antes de copiar código das skills oficiais `doc/skills/*`: §4 (erros verificados) e §5 (inconsistências da própria doc).
- Para saber o que é experimental/opt-in (Studio, Filament, OpenUSD, sleeping, `discrete`): §6. Legenda: ✔ testado · ⚠ armadilha (muda SEM erro) · Δ doc (a doc diverge do medido).

## 1. Onde procurar o quê
Caminhos sem prefixo são relativos a `docs/upstream/mujoco/` (`doc/` = capítulos Sphinx); repositórios irmãos ficam em `docs/upstream/<repo>/`. Os 13 itens da toctree (`doc/index.rst`) são: overview, computation, modeling, XMLreference, programming, APIreference, python, mjx, mjwarp, unity, OpenUSD, models, changelog.

| Tema | Arquivo(s) | Quando usar |
|---|---|---|
| Resumos curados da skill (já corrigidos) | `.agents/mujoco-agent-skill/references/` (`mjcf-cheatsheet`, `physics-tuning`, `actuators-sensors`, `python-api`, `rendering-viewer`, `gpu-mjx-warp`, `robots`, `drones`, `vehicles`, `install-linux`, `experiments-playbook`, `telemetry-rerun`, `relatorio-auditoria`, todos `.md`) | **comece por aqui**; vá ao espelho só para o detalhe ou a versão exata |
| Conceitos, modelo mental, "Clarifications" | `doc/overview.rst` (Introduction L4, Model elements L343, Clarifications L735) | 1º contato; "por que colidiu/não colidiu" (`SurprisingCollisions`), unidades, softness/slip, ids e nomes |
| Sintaxe MJCF: elementos, atributos, tipos, **padrões** | `doc/XMLreference.rst` (454 KB; âncoras `elemento-atributo`; árvore em `doc/XMLschema.rst`) | qualquer atributo/padrão; **busque com `--attr/--elem`**, não leia inteiro |
| Guia de uso do MJCF (autoria) | `doc/modeling.rst` (Default settings L70, Solver parameters L205, Contact parameters L424, Actuators L589, Sensors L1045, Delays L1133, Deformable L1342, URDF L1497, Tips and tricks L1632) | como modelar: defaults, frames, solref/solimp, atuadores, slip, backlash, restituição, desempenho |
| Matemática e algoritmos | `doc/computation/index.rst` (Soft contact L25, General framework L140, integradores L489, Constraint solver L1146, Collision L1739, Sleeping L2158, Reproducibility L2354) + `doc/computation/fluid.rst` | semântica numérica exata e equações (42 blocos `.. math::` em `index.rst`, 31 em `fluid.rst`); `discrete` (L722); fluidos (voo, natação, drones) |
| C API: tipos, funções, globais | `doc/APIreference/{APItypes,APIfunctions,APIglobals}.rst` (+`functions.rst`), `include/mujoco/*.h` (`mujoco.h`, `mjmodel.h`, `mjdata.h`, `mjspec.h`, `mjtype.h`, `mjxmacro.h`) | assinatura/campo exato (`--api`, `--type`); no venv: `mujoco.introspect.{functions,structs,enums}` e `site-packages/mujoco/include/` (exatos da versão instalada) |
| Programação C/C++ | `doc/programming/index.rst` (Versions L196, Naming L227), `doc/programming/simulation.rst` (loop L86, State/control L240, mjModel changes L638, Errors/logging L895, Sleeping L1231) | ciclo mjModel/mjData, threads, o que pode mudar em runtime, logging |
| Edição procedural (mjSpec) | `doc/programming/modeledit.rst` (attach, defaults `meDefault`, recompile `meRecompilation`, `.mjz`), `doc/python.rst` (Model editing L482), `python/mjspec.ipynb.md` | MjSpec em C/Python: attach, delete, encode, recompile |
| Visualização, UI, extensões, samples | `doc/programming/{visualization,ui,extension,samples}.rst` (Filament L493; plugins L11, decoders L342, providers L531) | mjv/mjr, Filament, plugins/decoders, samples `testspeed/basic/record/render` |
| Python | `doc/python.rst` (viewer L48, named access L362, rollout L866, minimize L942, USD L955, mujoco-py L1127), `python/README.md`, `python/{tutorial,rollout,LQR,least_squares}.ipynb.md`, `python/mujoco/sysid/{README.md,sysid.ipynb.md}`, `python/mujoco/usd/README.md` | bindings, viewer passivo, rollout multithread, sysid; **testes como exemplo**: `python/mujoco/{bindings,specs,rollout,viewer,renderer}_test.py` |
| MJX (JAX e Warp) | `doc/mjx.rst` (Implementations L90, Feature Parity L446, Sharp Bits L623), `mjx/README.md`, `mjx/tutorial.ipynb.md`, `mjx/mujoco/mjx/_src/io.py` | GPU/TPU/diferenciável; **assinaturas reais** (`put_data`, `make_data`) |
| MuJoCo Warp | `doc/mjwarp/index.rst` (When to use L31, Batch sizes L136, Overflow L460, FAQ L1017, Differences L1189), `docs/upstream/mujoco_warp/{README.md,notebooks/tutorial.ipynb.md,mujoco_warp/_src/io.py}` | lotes em GPU NVIDIA; `nworld`, `nconmax/naconmax`, `njmax`; render em lote |
| Changelog | `doc/changelog.rst` (3.15.0 L5 … 3.0.0 L2354; 2.x depois) | **migração entre versões** (`--changelog`) |
| Versionamento | `VERSIONING.md`, `doc/programming/index.rst` L196, `README.md` | §2 |
| Skills oficiais para agentes | `doc/skills/README.md` + `doc/skills/<skill>/SKILL.md` com `<skill>` = `python`, `spec_editing`, `rendering`, `accelerated`, `gui`, `studio` (fora da toctree e do changelog) | checklist de gotchas do upstream; **contêm erros (§4)** |
| Modelos oficiais | `model/` (`humanoid`, `flex`, `replicate`, `sleep`, `surfacevel`, `tactile`, `slider_crank`, `tendon_arm`, `cards`, `arch`, `plugin/…`, `model/car/car.xml`) | copiar padrões: flex, esteira, sleeping, SDF, veículo |
| Plugins, samples, USD, Unity, WASM | `plugin/{actuator,elasticity,sdf,sensor}/README.md`; `sample/*.cc`; `doc/OpenUSD/*.rst`; `doc/unity.rst`; `wasm/README.md` | pid legado, cable, SDF, touch_grid; C mínimo (`sample/basic.cc`, `sample/render.cc`); USD (experimental); Unity; WASM |
| Galeria de modelos | `doc/models.rst` → `docs/upstream/mujoco_menagerie/` (`README.md`, `FAQ.md`, `python/DOC.md`, `<modelo>/README.md`, ex.: `skydio_x2`, `bitcraze_crazyflie_2`) | robôs e drones prontos (o README de cada um traz a versão mínima do MuJoCo); pacote `mujoco-menagerie` |
| RL em GPU, controle preditivo | `docs/upstream/mujoco_playground/{README.md,CHANGELOG.md,learning/}`; `docs/upstream/mujoco_mpc/{README.md,docs/OVERVIEW.md}` | ambientes MJX/Warp (locomoção, manipulação); iLQG e Predictive Sampling (último commit espelhado do MJPC: 2025-05-27) |

O `INDEX.md` lista só a raiz e `doc/` do repositório principal; o full-text do `docs_search.py` indexa TODO texto do espelho (`.rst .md .py .h .cc .xml`…: modelos, testes, fontes MJX/Warp, samples). Fora do espelho (não verificável aqui): `src/` (parser; `src/xml/mjcf.schema` desde a 3.12.0), `simulate/`, `unity/`, `test/` — só pelo GitHub. Proveniência de cada repositório espelhado: `docs/upstream/<repo>/SOURCE.json` (ref, commit, data) — `mujoco` (3.15.0) e `mujoco_warp` (v3.15.0) estão fixados na versão instalada; `mujoco_playground`, `mujoco_mpc` e `mujoco_menagerie` são `main` e podem exigir outra versão do MuJoCo (confira o README do modelo/projeto); atualizar/trocar a versão: `sync_docs.py [--only mujoco] [--version X.Y.Z]` (clone esparso, só texto; precisa de rede).

### `docs_search.py`: um exemplo por modo (executados; exit 0 achou · 1 nada · 2 uso inválido · 3 espelho ausente)
```bash
cd /home/ondokai/Projects/MuJoCo; DS=".venv/bin/python .agents/mujoco-agent-skill/scripts/docs_search.py"
$DS --attr option.timestep               # [real, "0.002"] + texto (XMLreference.rst:325); formato elemento.atributo
$DS --elem actuator/dcmotor              # intro + atributos com tipo/padrão (input: string, "voltage"; ...)
$DS --api mj_fullM                       # mujoco.h:614  mj_fullM(const mjModel*, const mjData*, mjtNum* dst)
$DS --type mjtIntegrator                 # enum (mjtype.h:185) — inclui mjINT_DISCRETE
$DS --changelog "mjData.qM"              # por versão: 3.11.0 removido · 3.10.0 mj_fullM · 3.8.1 aviso
$DS --changelog "Breaking API changes"   # 25 versões 3.x casam (3.8.1 só por "Future breaking"; 3.4.0 é só ABI); --changelog "" dá exit 2
$DS "sleeping islands wake" --limit 3    # full-text BM25 (simulation.rst:1309, ...)
$DS "naconmax njmax" --repo mujoco_warp --limit 2   # restringe a um repositório
$DS --list                               # arquivos por repositório + commit do espelho
```
⚠ `--changelog` é busca por *substring* sem distinção de caixa: `qM` também casa ids de vídeo (`xHDS0n5DpqM`, 3.1.4) — use o nome qualificado (`mjData.qM`); termo ausente → exit 1; termo vazio (`--changelog ""`) → exit 2 (para listar por versão use `"Breaking API changes"` ou `"Version 3."`). `--attr` exige `elemento.atributo` (exit 2 se faltar o elemento); sem acerto → exit 1 e sugere `--elem`.

## 2. Política de versionamento

| Item | Regra (`VERSIONING.md`) |
|---|---|
| Esquema (desde 3.5.0) | `SUPERMAJOR.MAJOR.MINOR_OR_PATCH`: SUPERMAJOR = quebras e/ou grandes novidades · MAJOR = quebras, talvez novidades · MINOR_OR_PATCH = novidades ou correções |
| O que é garantido | **só** MINOR_OR_PATCH garante compatibilidade retroativa de API. Quebra apenas de ABI (ex.: remover campo não usado de struct) conta como MINOR e vai ao changelog. **Reprodutibilidade numérica nunca é garantida** (`doc/computation/index.rst` §Reproducibility) |
| Consequência em 3.x | cada `3.N.0` é um bump MAJOR: de 3.5.0 a 3.15.0 todas as versões, exceto 3.8.1 (só "Future breaking"), têm bloco "Breaking API changes" (contagem no changelog); só um `3.15.x` seria MINOR_OR_PATCH. A cadência real de 3.9.0 a 3.15.0 foi de 26, 35, 24, 19, 14 e 13 dias entre releases (o README mira "a primeira semana de cada mês"): fixe a versão e leia o changelog a cada atualização |
| Antes de 3.5.0 | sem semântica (3.0.0 só marcou a chegada do MJX); `mj_version()` era a concatenação dos dígitos (3.2.7 → 327) |
| Números | `mj_version()` = `SUPERMAJOR*1e6 + MAJOR*1e3 + MINOR_OR_PATCH` → 3.15.0 = `3015000` ✔ (igual a `mujoco.mjVERSION_HEADER`; `mj_versionString()` = "3.15.0"). PyPI `mujoco` tem o mesmo `X.Y.Z` (+`.postN` opcional) e exige Python ≥ 3.10. Checagem C recomendada: `if (mjVERSION_HEADER != mj_version()) complain();` |

### Como saber se um snippet antigo ainda vale
1. Compare a versão do snippet com `mujoco.__version__`: qualquer coisa ≤ 3.14 pode cruzar linhas da §3 (quem aprendeu ≤ 3.3: leia sobretudo as linhas ⚠).
2. Para cada símbolo: `docs_search.py --changelog <nome qualificado>`, depois `--api/--attr/--type` para a forma atual. No venv, `from mujoco.introspect import functions, structs, enums` lista TODA a API C da versão instalada (✔ 541 funções em 3.15.0: `"mj_addBody" in functions.FUNCTIONS` → False) e `help(mujoco.mj_fullM)` mostra a assinatura do binding.
3. Rode o probe abaixo (64 checagens das linhas da §3). XML removido dá `Schema violation` em `MjModel.from_xml_string`, mas **mudança de padrão/semântica não dá erro algum** (linhas ⚠): confira os defaults com `<mujoco/>` vazio e meça a grandeza física, nunca bits.
4. Rode o snippet num modelo mínimo antes de usá-lo e registre o resultado na memória do laboratório.

```python
# legacy_probe.py — rode com cwd FORA da raiz do projeto (o MuJoCo grava MUJOCO_LOG.TXT no cwd)
import mujoco as mj, numpy as np
M = mj.MjModel.from_xml_string("<mujoco/>"); D = mj.MjData(M); S = mj.MjSpec(); res = []
def chk(tag, label, ok):                        # ok=True => 3.15.0 confere com a linha do changelog
    res.append(bool(ok)); ok or print(f"DIVERGE [{tag}] {label}")
# 1) nomes removidos têm de estar ausentes / nomes novos presentes (tag = versão do changelog)
for tag, o, n in [("3.0.0", D, "solver_iter"), ("3.0.0", M, "nstack"), ("3.0.0", M, "eq_active"), ("3.0.0", M.opt, "collision"), ("3.2.1", M, "tex_rgb"),
                  ("3.2.3", M.opt, "mpr_tolerance"), ("3.2.7", D, "qLDiagSqrtInv"), ("3.3.7", M.opt, "apirate"), ("3.5.0", M, "cam_orthographic"),
                  ("3.6.0", D, "ten_J_rownnz"), ("3.10.0", D, "efc_diagApprox"), ("3.11.0", D, "qM"), ("3.12.0", D, "efm_L_rownnz"),
                  ("3.2.0", mj, "mj_makeEmptyFileVFS"), ("3.2.5", mj, "mju_rotVecMat"), ("3.5.0", mj, "mju_rayFlex"), ("3.10.0", mj, "mju_error_i"),
                  ("3.3.6", mj.mjtDisableBit, "mjDSBL_PASSIVE"), ("3.3.6", mj.mjtEnableBit, "mjENBL_ISLAND"), ("3.3.6", mj.mjtMouse, "mjMOUSE_SELECT"),
                  ("3.3.5", mj.mjtVisFlag, "mjVIS_FLEXBVH"), ("3.7.0", mj.mjtWarning, "mjWARN_VGEOMFULL")]:
    chk(tag, f"{n} deveria estar ausente", not hasattr(o, n))
for tag, o, n in [("3.0.0", D, "solver_niter"), ("3.0.0", M, "narena"), ("3.0.0", D, "eq_active"), ("3.2.1", M, "tex_data"), ("3.2.3", M.opt, "ccd_tolerance"),
                  ("3.5.0", M, "cam_projection"), ("3.6.0", M, "ten_J_rownnz"), ("3.10.0", D, "efc_diagA"), ("3.11.0", D, "M"), ("3.3.6", mj.mjtDisableBit, "mjDSBL_ISLAND"),
                  ("3.3.6", mj.mjtDisableBit, "mjDSBL_SPRING"), ("3.2.5", mj, "mju_mulMatVec3"), ("3.5.0", mj, "mj_rayFlex"), ("3.13.0", mj.mjtIntegrator, "mjINT_DISCRETE"),
                  ("3.14.0", mj.mjtEnableBit, "mjENBL_IPC"), ("3.8.1", mj, "MjVfs")]:
    chk(tag, f"{n} deveria existir", hasattr(o, n))
# 2) XML: atributos/valores removidos têm de ser REJEITADOS pelo parser
X = lambda body="", tail="", head="": f"<mujoco>{head}<worldbody>{body}</worldbody>{tail}</mujoco>"
J = "<body><joint name='j'/><geom size='.1'/></body>"
for tag, xml in [("3.0.0", X(head="<option collision='all'/>")), ("3.2.3", X(head="<option mpr_tolerance='1e-6'/>")), ("3.2.5", X(head="<compiler exactmeshinertia='true'/>")),
                 ("3.3.6", X(head="<option><flag passive='disable'/></option>")), ("3.5.0", X("<camera orthographic='true'/>")),
                 ("3.3.0", X("<body><composite type='grid' count='3 3 1'/></body>")), ("3.3.0", X("<body><composite type='particle' count='3 3 1'/></body>")),
                 ("3.12.0", X(J, "<actuator><dcmotor joint='j' motorconst='.1' resistance='1' input='position'/></actuator>"))]:
    try: mj.MjModel.from_xml_string(xml); ok = False
    except ValueError: ok = True
    chk(tag, f"parser deveria rejeitar {xml[:80]}", ok)
# 3) aceitos SEM erro, mas com comportamento novo (⚠ silencioso)
m = mj.MjModel.from_xml_string(X("<body><joint range='0 1'/><geom size='.1'/></body>")); chk("3.0.0", "autolimits=true: range sem limited vale", m.jnt_limited[0] == 1)
m = mj.MjModel.from_xml_string(X("<light directional='true'/>")); chk("3.3.3", "directional legado ainda aceito", m.light_type[0] == mj.mjtLightType.mjLIGHT_DIRECTIONAL)
m = mj.MjModel.from_xml_string(X(J, "<sensor><jointpos joint='j' noise='5'/></sensor>")); d = mj.MjData(m); d.qpos[0] = .3; mj.mj_forward(m, d)
chk("3.1.4", "noise= só guarda σ; sensordata sem ruído", m.sensor_noise[0] == 5 and d.sensordata[0] == .3)
chk("3.3.0/3.3.6/3.8.0", "nativeccd, island, multiccd ligados e sleep desligado (flags 0)", M.opt.disableflags == 0 and M.opt.enableflags == 0)
chk("3.11.0", "sleep_tolerance == 1e-3", abs(M.opt.sleep_tolerance - 1e-3) < 1e-12); chk("3.12.0", "bvactive == 0", M.vis.global_.bvactive == 0)
chk("3.15.0", "integrador padrão = Euler (implicitfast NÃO é padrão)", M.opt.integrator == mj.mjtIntegrator.mjINT_EULER)
g = mj.MjModel.from_xml_string(X("<geom type='plane' size='2 2 .1'/><body pos='0 0 .2'><freejoint/><geom type='sphere' size='.1' margin='.05' gap='.10'/></body>",
                                 head="<option gravity='0 0 0'/>")); gd = mj.MjData(g); r = []
for z in (.30, .20, .14):                       # dist = z - 0.1 ; margin+gap = 0.15 ; margin = 0.05
    gd.qpos[2] = z; mj.mj_forward(g, gd); r.append((gd.ncon, gd.contact.efc_address.tolist()))
chk("3.9.0", f"margin/gap: dist .20/.10/.04 -> {r}", r == [(0, []), (1, [-1]), (1, [0])])  # sem contato / contato sem força / com força
q = mj.MjModel.from_xml_string(X("<body><freejoint/><geom size='.1'/></body>")); qd = mj.MjData(q); qd.qpos[3:7] = [2, 0, 0, 0]; mj.mj_forward(q, qd); a0 = qd.qpos[3]; mj.mj_step(q, qd)
chk("3.2.0", "mj_forward não normaliza quaternion de qpos; mj_step normaliza", a0 == 2 and abs(qd.qpos[3] - 1) < 1e-9)
f = mj.MjModel.from_xml_string(X("<geom type='plane' size='2 2 .1'/><body pos='0 0 .15'><freejoint/><geom type='box' size='.1 .1 .1'/></body>")); fd = mj.MjData(f)
[mj.mj_step(f, fd) for _ in range(50)]; w0 = fd.qacc_warmstart.copy(); [mj.mj_forward(f, fd) for _ in range(5)]
chk("3.3.6", "mj_forward idempotente: qacc_warmstart não muda ao repetir", np.abs(fd.qacc_warmstart - w0).max() == 0)
# 4) MjSpec, Python e assinaturas
chk("3.7.0", "spec.strippath existe; spec.compiler.strippath não", hasattr(S, "strippath") and not hasattr(S.compiler, "strippath"))
j = S.worldbody.add_body().add_joint()
try: j.stiffness = 1.0; ok = False
except TypeError: ok = True
chk("3.7.0", "joint.stiffness = v -> TypeError; é array (3,): use stiffness[0] = v", ok and j.stiffness.shape == (3,))
chk("3.3.7", "spec.meshdir (depreciado) ainda existe ao lado de spec.compiler.meshdir", hasattr(S, "meshdir") and hasattr(S.compiler, "meshdir"))
chk("3.3.4", "body.delete() não existe; spec.delete(el) existe", not hasattr(S.worldbody, "delete") and hasattr(S, "delete"))
inc = b"<mujoco><worldbody><geom size='.1'/></worldbody></mujoco>"; main = "<mujoco><include file='inc.xml'/></mujoco>"
with mj.MjVfs() as v:
    v["inc.xml"] = inc; n1 = mj.MjModel.from_xml_string(main, vfs=v).ngeom
    try: mj.MjModel.from_xml_string(main, assets={"inc.xml": inc}, vfs=v); both = False
    except ValueError: both = True
chk("3.8.1", "MjVfs ok; dict assets ainda aceito; assets+vfs = ValueError", n1 == 1 and mj.MjModel.from_xml_string(main, assets={"inc.xml": inc}).ngeom == 1 and both)
try: mj.mj_fullM(M, np.zeros((0, 0)), D.M); old_ok = True            # ordem antiga (m, dst, M)
except TypeError: old_ok = False
mj.mj_fullM(M, D, np.zeros((M.nv, M.nv))); chk("3.10.0", "mj_fullM(m, d, dst) ok; (m, dst, M) -> TypeError", not old_ok)
chk("3.14.0", "mj_readCtrl(m, d, id, time, result, interp)", all(k in mj.mj_readCtrl.__doc__ for k in ("result", "interp")))
a = mj.MjModel.from_xml_string(X("<body><joint name='j1'/><geom size='.1'/><body pos='1 0 0'><joint name='j2'/><geom size='.1'/></body></body>",
                                 "<actuator><pid name='a_pid' joint='j1' kp='10' kv='1'/><motor name='a_motor' joint='j2'/></actuator>")); ad = mj.MjData(a)
ad.actuator("a_motor").ctrl = 5.0
chk("3.11.0-3.12.0", f"nu={a.nu} != nactuator={a.nactuator}; actuator('a_motor').ctrl grava no slot errado: {ad.ctrl.tolist()}", a.nu == 3 and a.nactuator == 2 and ad.ctrl.tolist() == [0, 5, 0])
print(f"{len(res)} verificações, {len(res) - sum(res)} divergências (mujoco {mj.__version__})")
```
Saída (executado, 3.15.0): `64 verificações, 0 divergências`. Qualquer `DIVERGE` = linha da §3 já não vale na versão instalada.

## 3. Mudanças e quebras 3.0.0 → 3.15.0
Gerada lendo `doc/changelog.rst` L5–L2572 por bloco de versão (itens menores e correções sem efeito no usuário foram omitidos). Tipos: MJCF, C, Py, ABI, padrão, semântica, MJX. ✔ = confirmado pelo probe (§2) ou pelos testes da §4 (linhas sem ✔ vêm só do changelog: não testadas aqui); ⚠ = **muda sem erro**.

| Versão | Mudança | Impacto em código/modelos antigos | Substituto / migração |
|---|---|---|---|
| 3.0.0 | MJCF/C: `mjOption.collision` e `<option collision>` removidos | ✔ `<option collision=…>` → Schema violation | `all`: apague o atributo · `dynamic`: apague os `<pair>` · `predefined`: `<default><geom contype="0" conaffinity="0"/></default>` + `<pair>` |
| 3.0.0 | ABI: `nstack`→`narena` (bytes); `solver_iter`→`solver_niter` (vetor por ilha); `mjData.solver` = `mjNISLAND×mjNSOLVER` (20×200) | ✔ `data.solver_iter`, `model.nstack` → AttributeError | `data.solver_niter[0]`, `narena` |
| 3.0.0 | Py/C: `mjModel.eq_active`→`eq_active0`; o estado do usuário passa a ser `mjData.eq_active` | ✔ `model.eq_active` não existe mais | `data.eq_active[i] = 0/1` |
| 3.0.0 | padrão: `compiler/autolimits` false→true; composites `rope`/`cloth` removidos; `actuatorforcerange`→`actuatorfrcrange` (e `…limited`→`…frclimited`) | ✔ `range` sem `limited` agora vale (só quebrava modelos que já não carregavam desde 2.2.2) | `cable` (plugin) / flexcomp; novos nomes `actuatorfrc*` |
| 3.0.0 | C: `mjMARKSTACK/mjFREESTACK` e `mj_stackAlloc` removidos. Novos: MJX, SDF, `flex/flexcomp`, ilhas, thread pool, flags `eulerdamp`/`invdiscrete` | C não compila | `mj_markStack/mj_freeStack`, `mj_stackAllocNum` |
| 3.1.0 | MJX: `put_data/put_model/get_data` substituem `device_put/device_get_into` (removidos na 3.1.5); novos `<frame>` e `kv` (position/intvelocity) | código MJX da 3.0 quebra | `mjx.put_data`, `mjx.get_data_into` |
| 3.1.2 | Py: `mujoco.rollout` passa a usar `mjSTATE_FULLPHYSICS`, controles configuráveis e saídas sempre 3D | ⚠ código que lia o formato antigo quebra | ajuste índices (`doc/python.rst` §rollout) |
| 3.1.3 | C: `mj_makeEmptyFileVFS` depreciado (removido na 3.2.0) | ✔ ausente na 3.15.0 | `mj_addBufferVFS`; Python: `MjVfs` (3.8.1) |
| 3.1.4 | semântica: ruído nativo de sensores removido; `noise=` só guarda σ em `sensor_noise` | ⚠ ✔ aceito sem erro; `sensordata` fica sem ruído | adicione o ruído no seu código |
| 3.1.6 | novo: `mj_geomDistance`; sensores `distance/normal/fromto`; `position/timeconst` e `position/dampratio` | — | (a semântica de `dampratio` muda na 3.15.0) |
| 3.2.0 | novo: mjSpec (instável até a 3.2.5); VFS reescrito (`mj_findFileVFS` e `mjMAXVFS*` removidos; `mj_defaultVFS` exige `mj_deleteVFS`); `mjUSEDOUBLE`→`mjUSESINGLE`; `mj_kinematics` deixa de normalizar in place os quaternions de `qpos`/`mocap_quat` | ⚠ ✔ `qpos[3:7]` pode estar não normalizado após `mj_forward`; `mj_step` normaliza | normalize você mesmo se ler antes do 1º passo |
| 3.2.1 | ABI: `tex_rgb`→`tex_data`; flag `autoreset`; sub-elementos PBR em `material` | ✔ `model.tex_rgb` → AttributeError | `tex_data` |
| 3.2.3 | MJCF/C: `mpr_tolerance/mpr_iterations`→`ccd_tolerance/ccd_iterations` (XML e `mjOption`); `mjs_findMesh/findKeyframe`→`mjs_findElement`; plugins de elasticidade em composite removidos | ✔ XML com `mpr_*` é rejeitado | `ccd_*`; flexcomp |
| 3.2.3 | novo: flag `nativeccd`; `connect/weld` por 2 sites; `alignfree` (padrão false: ligar muda a semântica de `qpos/qvel` e invalida keyframes antigos); attach funde keyframes; `mj_jacDot` | — | `alignfree` só em modelos novos |
| 3.2.4 | removido: plugins `solid/membrane` (flex virou engine); `mjs_setActivePlugins`→`mjs_activatePlugin`; Python 3.8 | modelos com esses plugins quebram | flex nativo |
| 3.2.5 | removido: `exactmeshinertia` (→ `mesh/inertia`), `convexhull`, `mju_rotVecMat(T)`, `mjv_makeConnector`, composites `box/cylinder/sphere`; PBR vira `<layer>`; mjSpec "estável" | ✔ XML rejeita `exactmeshinertia`; `mju_rotVecMat` ausente | `mju_mulMatVec3/mju_mulMatTVec3`; flexcomp |
| 3.2.6 | Py: composites `rope/loop` removidos; `bind()` e remoção do atributo `id` dos objetos mjSpec; `rollout` aceita sequência de `MjModel` e perde `nroll` | código que usa `.id` quebra | nomes ou `bind()` |
| 3.2.7 | ABI: `mjData.qLDiagSqrtInv` removido (`mj_solveM2` ganhou argumento) | ✔ ausente | — |
| 3.3.0 | padrão: `nativeccd` ligado (libccd sai do caminho padrão) | ⚠ ✔ `disableflags == 0`; contatos entre convexos mudam | `<flag nativeccd="disable"/>` |
| 3.3.0 | semântica: `geom/shellinertia` ignorado em malhas (→ `asset/mesh/inertia`; na `XMLreference`: padrão `legacy`, `convex` recomendado); inércia volumétrica que falha vira ERRO (antes: recuo silencioso p/ superfície) | malhas finas/abertas deixam de compilar | `<mesh inertia="shell"/>` ou `convex` |
| 3.3.0 | removido: composites `grid`/`particle`; attach vira cópia rasa (`mjs_setDeepCopy`) | ✔ erro "use flex" / "use replicate" | flexcomp / `replicate`; `mjs_setDeepCopy(spec, 1)` p/ cópia profunda |
| 3.3.1 | padrão: contatos `internal` de flex true→false (removidos na 3.15.0); `mjs_attach*` unificados em `mjs_attach`; `mj_jacDot` corrigido (faltava um termo) | ⚠ Jacobianas dot da 3.2.3–3.3.0 estavam erradas | atualize |
| 3.3.3 | MJCF: `light/directional`→`light/type`; `texture/colorspace`; `mj_makeM` no lugar de `mj_crb`; plugin `shell` e `mjv_sceneState` removidos; `fusestatic` só funde corpos não referenciados | ✔ `directional` ainda é aceito; ⚠ PNG sRGB renderiza diferente | `colorspace="linear"` restaura o visual antigo |
| 3.3.4 | API: `mjs_detachBody/Default`→`mjs_delete`; Py `element.delete()`→`spec.delete(el)`; `mjs_setName` (campo `name` sai dos `mjs*`) | ✔ `body.delete` ausente | `spec.delete(spec.body('x'))` |
| 3.3.5 | removido: plugin SdfLib (SDF nativo), `mjVIS_FLEXBVH`→`mjVIS_MESHBVH`. Novo: sensores `insidesite/contact/tactile`; MJX backend Warp ("beta"); wheels `manylinux_2_28` | ✔ `mjVIS_FLEXBVH` ausente | `mjVIS_MESHBVH` |
| 3.3.6 | padrão/semântica: ilhas ligadas (`mjENBL_ISLAND`→`mjDSBL_ISLAND`); `qacc_warmstart` passa a ser atualizado no fim de `mj_step` | ⚠ ✔ `mj_forward` idempotente (viewer pausado não "converge" mais); RK4 muda numericamente, sem volta | legado: `qacc_warmstart ← qacc` após `mj_forward`; `<flag island="disable"/>` |
| 3.3.6 | removido: `mjDSBL_PASSIVE`→`mjDSBL_SPRING` + `mjDSBL_DAMPER` (os dois juntos desligam TODAS as forças passivas: gravcomp, fluido, `mjcb_passive`, plugins); `mjMOUSE_SELECT` | ✔ XML `<flag passive=…>` rejeitado | os dois flags em `disable` |
| 3.3.7 | API: `meshdir/texturedir`→`compiler.meshdir/texturedir` no mjSpec; `mjOption.apirate` removido; C++20; MJX `make_data`: `nconmax/njmax` default `None` | ✔ `spec.meshdir` ainda existe (depreciado) | `spec.compiler.meshdir` |
| 3.4.0 | novo: sleeping islands (preliminar, opt-in); `mj_fwdKinematics`, `mj_extractState/copyState`; `mjtSize` = `int64_t`; nome duplicado dá erro também no parse; `mjx.Model.tex_data` vira ndarray (Madrona abandonado) | — | §6 |
| 3.5.0 | API: funções de raio ganham o argumento `normal` (`mj_ray`, `mj_multiRay`, `mju_rayGeom`, `mj_rayFlex`, `mj_rayHfield`, `mj_rayMesh`); `mju_rayFlex`→`mj_rayFlex` | ✔ `mju_rayFlex` ausente | C: passe `NULL`; Python: opcional (exceto `mj_multiRay`) |
| 3.5.0 | MJCF/ABI: `cam_orthographic`→`cam_projection` (`mjtProjection`); `camera/orthographic`→`projection="perspective"` ou `"orthographic"` | ✔ XML rejeita `orthographic` | `projection=` |
| 3.5.0 | semântica: `margin` e `gap` de DOIS geoms passam a ser SOMADOS (antes: máximo) | ⚠ contatos entre geoms com margens diferentes mudam | revise as margens por geom |
| 3.5.0 | ABI: tamanhos de alocação do `mjModel` em 64 bits (campos `mjtSize`, tipo da 3.4.0) | ✔ gcc: `printf("%d", m->nbody)` avisa (`long`) | `%ld` ou cast |
| 3.5.0 | novo/removido: MJWarp oficial; `mujoco.sysid`; atraso e histórico (`mjData.history`); `flexvert`; rangefinder por câmera; semver; sensores de colisão idênticos deixam de compartilhar cálculo; `getdir` sai de `mjpResourceProvider`; OpenUSD vira plugin `mjpDecoder` | possível perda de desempenho com sensores de colisão duplicados | `sensor/fromto` + cálculo manual |
| 3.6.0 | ABI: `ten_J` sempre esparso; `ten_J_rownnz/rowadr/colind` saem de mjData e vão para mjModel | ✔ `data.ten_J_rownnz` ausente | `model.ten_J_rownnz` |
| 3.7.0 | API: `stiffness` e `damping` de `mjsJoint/mjsTendon` viram `mjtNum[mjNPOLY+1]` | ✔ `joint.stiffness = v` → TypeError | `joint.stiffness[0] = v` |
| 3.7.0 | padrão: o parser de URDF deixa de forçar `strippath="true"` | ⚠ malhas de URDF em subpastas não são achadas | `<compiler strippath="true"/>` ou `spec.strippath = True` (Δ doc: o snippet `spec.compiler.strippath` do changelog → AttributeError ✔) |
| 3.7.0 | novo/removido: `dcmotor` (v1); damping/armature de atuador; rigidez e amortecimento polinomiais (`mjNPOLY`); ponto médio p/ corpos livres; termo J̇v em connect/weld; `mjpEncoder`/`mj_encode`; `mjWARN_VGEOMFULL` e `mjsFlex.vertcollide` removidos; `mjPLUGIN_LIB_INIT(nome)` | ✔ `mjWARN_VGEOMFULL` ausente | — |
| 3.8.0 | padrão: `multiccd` ligado; attach resolve assets do filho relativos ao diretório do filho; `mj_maxContact`; Python 3.14 | ⚠ contatos de convexos mudam | `<flag multiccd="disable"/>` |
| 3.8.1 | semântica/API: ponto médio só em `implicitfast` e desligado com fluido; PGS com ilhas (ordem pseudo-aleatória); `MjSpec.encode`; `mujoco.MjVfs`; dict `assets` depreciado | ✔ o dict ainda funciona sem warning; `assets`+`vfs` → ValueError | `with mujoco.MjVfs() as vfs: vfs['inc.xml'] = bytes` |
| 3.9.0 | semântica: `margin` = inflação da superfície, `gap` = buffer extra de detecção; contato existe se `dist < margin+gap` e gera força se `dist < margin`; entre os dois fica em `mjData.contact` com `efc_address = -1` | ⚠ ✔ esfera/plano, margin .05, gap .10: dist .20 → 0 contatos · .10 → 1 sem força · .04 → força; sem efeito se `gap = 0` | `margin_novo = margin_antigo − gap_antigo`, `gap_novo = gap_antigo`; mantenha `margin+gap ≥ 0` |
| 3.9.0 | C/ABI: `mjtBool` substitui `mjtByte`; `mjtnum.h`→`mjtype.h`; `mjfCollision` preenche `mjPreContact`; `tactile` reporta profundidade bruta; MJX: `nconmax` removido; novos `mjassert.h` e flag `diagexact`; flexes podem dormir | quebra em C e MJX | `naconmax` |
| 3.10.0 | API: `mj_fullM(m, dst, M)`→`mj_fullM(m, d, dst)` | ✔ a ordem antiga → TypeError | ou `mju_sym2dense(dst, d->M, nv, M_rownnz, M_rowadr, M_colind)` |
| 3.10.0 | ABI/C: `efc_diagApprox`→`efc_diagA`; `mjthread.h` removido; `mju_{error,warning}_{i,s}` removidos; log unificado (`mju_user_error/warning` depreciados) | ✔ `efc_diagApprox`, `mju_error_i` ausentes | `mju_threadpool`, `mju_setLogHandler` |
| 3.10.0 | novo: `compiler/conflict` para attach (padrão "warning"; futuro: "merge"); `mjs_numWarnings`; `mjs_makeFlex` (`body.make_flex()`); CG com Hager-Zhang | — | — |
| 3.11.0 | removido: `mjData.qM` (só `mjData.M`, em CSR); `mjd_inverseFD`: `DmDq` passa de nv×nM a nv×nC | ✔ `data.qM` → AttributeError | `data.M` + `mju_sym2dense`, ou `mj_fullM(m, d, dst)` |
| 3.11.0 | padrão: `sleep_tolerance` 1e-4→1e-3; `mju_round` desempata para longe de zero; `mjv_moveCamera` sem `mjvScene` | ✔ 1e-3 | — |
| 3.11.0 | semântica: `implicitfast` troca o ponto médio por derivadas giroscópicas dos corpos livres | ⚠ giro não ganha energia, mas o tumbling é levemente amortecido | RK4 p/ conservação no vácuo; `invdiscrete` não afeta mais a dinâmica direta |
| 3.11.0 | novo/ABI: atuadores MIMO (`ctrlnum/outnum`; `nu = Σ ctrlnum` ≠ `nactuator`), `orientation`, `mj_resetCtrl`, `mj_actuatorInputName`; `surfacevel`, `adhesion`; `flg_gravcomp/flg_surfacevel` (`ngravcomp` depreciado) | ⚠ ✔ `data.actuator('x').ctrl` grava no slot ERRADO com atuador multi-entrada | `data.ctrl[ctrladr[i]:ctrladr[i]+ctrlnum[i]]` |
| 3.11.0 | semântica: `intvelocity/actlimited` passa a "auto" (antes fixo em true); position/intvelocity em juntas esféricas usam o círculo; `mj_encode` devolve `mjtSize` | ⚠ `intvelocity` sem `actrange` deixa de ser limitado | declare `actrange` |
| 3.12.0 | removido: texturas só PNG/KTX (formato binário próprio e fallback por extensão) | texturas antigas não carregam | converta para PNG |
| 3.12.0 | novo: atuador `pid` (input padrão `pos vel` = 2 controles; `ki`, `imax`, `slewmax`) substitui o plugin `mujoco.pid`; schema MJCF em fonte única (`src/xml/mjcf.schema`) | — | — |
| 3.12.0 | semântica: `dcmotor` redesenhado — `input` é uma assinatura (subconjunto de `pos vel ff voltage`), ganhos em espaço de torque, back-EMF compensado, `none` = passivo | ✔ `input="position"/"velocity"` → erro; o motor por tensão (padrão) segue igual | `pos`/`vel`; ganhos × K/R e `kd += K²/R` |
| 3.12.0 | padrão: `visual/global/bvactive` true→false; corpos mocap viram raiz do próprio weld group (`body_weldid` = id) | ⚠ ✔ `bvactive` 0; filhos de mocap ganham filtro pai-filho; mocap deixa de ser geometria estática no raycast e sensores de contato agregam sob o corpo mocap (não sob o mundo) | — |
| 3.12.0 | visual: UVs canônicas nas primitivas (planos finitos ancorados no canto); `light/softness` (0,2; luzes PBR/Filament); `mjx.render*` devolve `d` por último | ⚠ checkers de planos finitos mudam de fase | `softness="1"`; `rgb, depth, d = mjx.render(...)` |
| 3.12.0 | ABI: `efm_L_rownnz/rowadr/colind` removidos; `mjsActuator.velrange/ffrange`; `mjtGain/mjtDyn` ganham `pid` (desloca `*_USER`); `mjResource.args`; contatos `passive` de flex ficam implícitos (trocado na 3.13) | ✔ `efm_L_rownnz` ausente | — |
| 3.13.0 | novo: integrador `discrete` (`mjINT_DISCRETE`; métrica efetiva M + hD + h²K). Elasticidade e contato passivo de flex exigem `discrete` (erro de runtime sob implicit/implicitfast); sob `discrete`, `refsafe` troca linhas rígidas demais pela mais rígida de restituição zero | ✔ enum existe; Euler continua o padrão | `integrator="discrete"` |
| 3.13.0 | correção com efeito: clamp de pivôs ≤ 0 na fatoração esparsa restaurado (+ `mjWARN_INERTIA`) | ⚠ desde a 3.3.0 massas singulares davam acelerações não finitas em silêncio (resets "misteriosos") | corrija a inércia |
| 3.13.0 | visual/colisão: fallback PBR de `metallic` agora branco; colisor plano-malha reescrito; multiccd para cilindros; sites `type="mesh"` + `mj_insideSite`; Python 3.15 | ⚠ contatos plano-malha mudam | — |
| 3.14.0 | API: `mj_readCtrl(m, d, id, time, result, interp)` (igual a `mj_readSensor`; devolve `const mjtNum*`; o histórico guarda `ctrlnum` valores por amostra) | ✔ assinatura nova | `result` com `actuator_ctrlnum[id]` posições |
| 3.14.0 | correção com efeito: torque do `weld` em `mj_rnePostConstraint` (faltava `0.5·torquescale` e a rotação ao mundo); forças de tendões espaciais entram nos sensores force/torque | ⚠ sensores force/torque em corpos presos por weld com torque estavam ERRADOS | releia medições antigas com cautela |
| 3.14.0 | semântica: `tendon/actuatorfrclimited` padrão "auto" (antes `actuatorfrcrange` era ignorado sem o flag); `mjWARN_INERTIA` também em implicitfast/Euler (antes mudo) e implicit (antes fatal); `mjsElement.signature` = 0 até compilar; `mjd_transitionFD/inverseFD` erram com sleeping; `<frame>` preservado ao salvar MJCF; flag `ipc` (experimental) | ⚠ limites de força de tendão passam a valer; XML salvo muda de forma | — |
| 3.15.0 | semântica: `dampratio` usa a inércia operacional `(J M⁻¹ Jᵀ)⁻¹` em `qpos0` (doc de `position/dampratio`) | ⚠ cadeias multi-elo: amortecimento MENOR; tendões/sites multi-junta: mais exato (antes superamortecido) | reajuste o `dampratio` |
| 3.15.0 | removido: opção `internal` de flex e `evpair`. Novo: `mj_saveModel/mj_loadModelBuffer` com `mjtSize`; SNH experimental (`mjsFlex.elastic3d=1`); multicontato de cápsula; `insidesite/enclosed` | — | — |

**Depreciados que ainda funcionam em 3.15.0** (a doc só diz "próxima release"; se a 3.16.0 os remove: não verificado): dict `assets` → `MjVfs` ✔; `spec.meshdir/texturedir` → `spec.compiler.*` ✔; `mjModel.ngravcomp` → `flg_gravcomp` ✔; `light/directional` → `type` ✔; `mjs_isWarning` → `mjs_numWarnings(s) > 0` (C); `mju_user_error/warning` → `mju_setLogHandler`. **Futuros anunciados**: `compiler/conflict` "warning"→"merge" (3.10.0); `alignfree` pode virar true (3.2.3); unificar linear e polinomial em `stiffness/damping` (3.7.0).

**Padrões em 3.15.0** (`<mujoco/>` vazio, ✔ medido; coincidem com a `XMLreference`): `integrator` Euler · `solver` Newton · `cone` pyramidal · `jacobian` auto · `timestep` 0,002 · `iterations` 100 · `ls_iterations` 50 · `tolerance` 1e-8 · `ccd_iterations` 35 · `ccd_tolerance` 1e-6 · `impratio` 1 · `sleep_tolerance` 1e-3 · `disableflags` = `enableflags` = 0 (nativeccd, island, multiccd, refsafe, autoreset ligados; sleep, energy, ipc desligados) · compiler: `autolimits` true, `alignfree` false, `usethread` true, `conflict` warning, `angle` degree, `inertiagrouprange` 0 5, `strippath` false · `visual/global` 640×480, `bvactive` 0.

## 4. Erros das skills oficiais (`doc/skills/*`) — regra: **não copie sem testar**
> A errata COMPLETA (63 blocos de código das 6 skills executados: 34 OK · 12 FALHA · 11 RESSALVA · 6 não executáveis, com a correção testada de cada item) está em [`official-skills-errata.md`](official-skills-errata.md); a tabela abaixo é o resumo.

O que valeu a pena nelas (✔ testado): `set_to_position()/set_to_motor()` não definem `trntype` (padrão `mjTRN_UNDEFINED` → "invalid transmission type"); `geom.classname = 'str'` → TypeError (passe o `MjsDefault`); tamanho 0 de geom é erro; `Renderer` devolve RGB `(H,W,3) uint8`, depth `(H,W) float32`, segmentação `(H,W,2) int32`; `mj_step(m, d, nstep=N)` existe. O resto (nomeado, `.copy()`, quaternion `[w x y z]`) já está no `AGENTS.md`. Os erros de Python também aparecem como "snippet → correção" em `references/python-api.md` §10 e os de GPU em `references/gpu-mjx-warp.md`. Erros confirmados:

| Skill §  | A skill diz | Verdade em 3.15.0 | Use |
|---|---|---|---|
| `python` §1, `spec_editing` §1 (C++) | `mj_addBody(spec, nullptr)`, `mjbBody*`, `mj_addGeom(body, mjGEOM_SPHERE, …)`, `mj_compile(spec, error, sizeof(error))` | ✔ nenhum desses nomes existe; `mj_compile(s, vfs)` tem 2 parâmetros | `mjs_findBody(spec,"world")`, `mjs_addBody`, `mjs_addGeom(body, NULL)`, `mj_compile(spec, NULL)`, erro em `mjs_getError(spec)` (C compilado abaixo) |
| `python` §2 | "write through bind — always use `.set()`" | ✔ `data.bind(j).set(...)` → AttributeError; `.set` é do `bind` do MJX (`mjx/mujoco/mjx/_src/support.py:517`) | `data.bind(j).qpos = v` |
| `python` §3 | "`mjINT_EULER` (default in earlier models)" | Δ doc: Euler **continua o padrão** em 3.15.0 ✔; a lista omite `mjINT_DISCRETE` (3.13.0) | ver §6 |
| `spec_editing` §2 | `axisangle=[x, y, z, angle_rad]` | ✔ o ângulo é em GRAUS por padrão (`spec.compiler.degree` = True): `[0,0,1,90]` = 90° | `compiler.degree = False` p/ radianos |
| `spec_editing` §3 | `parent.attach(arm1_spec, prefix='left_')`; `add_equality(…, anchor=[0,0,0])` | ✔ `ValueError: One of frame or site must be specified`; `anchor` não é kwarg; `connect` precisa de `objtype` | `p.attach(c, frame=p.worldbody.add_frame(), prefix='left_')`; `add_equality(type=mjEQ_CONNECT, objtype=mjOBJ_BODY, name1=…, name2=…, data=[ax,ay,az]+[0]*8)` ✔ |
| `spec_editing` §4 | `spec.delete_body/geom/joint/actuator('x')` | ✔ inexistentes (changelog 3.3.4) | `spec.delete(spec.body('x'))` |
| `spec_editing` §6 | "assign class post-creation: `geom.classname = rubber`" | ✔ só rotula (XML ganha `class="rubber"`, mas friction continua 1.0): defaults só valem na criação (`doc/programming/modeledit.rst` §meDefault) | `body.add_geom(rubber, …)` |
| `spec_editing` §8 | `spec.add_mesh(name=, vertex=, face=)` | ✔ TypeError | `uservert=`, `userface=` (arrays planos) |
| `rendering` §5 | câmera "overhead" com `quat=[0.707, 0.707, 0, 0]` "pointing down" | ✔ olha para +Y (horizontal): a câmera olha ao longo do seu −Z | olhar para baixo: quat identidade |
| `rendering` §6 | "só o ÚLTIMO `<visual>` vale; os anteriores são sobrescritos" | ✔ blocos **mesclados** por atributo (offwidth 1920 sobrevive); só o MESMO atributo repetido é sobrescrito; sub-elemento único por bloco | consolidar é só higiene |
| `accelerated` §2, §4, §5 (+ README) | `mjx.put_data` "pré-aloca contatos a partir de `data.ncon`"; sem `njmax` ⇒ contatos "silently ignored" | ✔ falso: `njmax` = máx. de **restrições por mundo**, usado só com `impl='warp'` (o ramo JAX chama `_put_data_jax(m, d, device)`; executado em CPU no `.venv-gpu`: com e sem `njmax=500` a esfera repousa igual, z = 0,0996, `ncon` = 1); `naconmax` = contatos de todos os mundos somados | MJX-Warp: `mjx.make_data(m, impl='warp', naconmax=…, njmax=…)` (`doc/mjx.rst` L97–L125) |
| `accelerated` §6 | `mjw.put_data(model, batch_size)` | ✔ a assinatura é `put_data(mjm, mjd, nworld=1, nconmax=None, …)`; executado: `AttributeError: 'int' object has no attribute 'ncon'` | `mjw.make_data(mjm, nworld=4096)` ou `put_data(mjm, mjd, nworld=…)`; sem `nconmax/njmax` há heurística e overflow é detectado (`doc/mjwarp/index.rst` L460) |
| `accelerated` §1 | tabela: "Constraint Islands: MJWarp ❌" | ✔ `mjw.island` e `mjw.DisableBit.ISLAND` existem (import no `.venv-gpu`); o MJWarp 3.15 agrupa corpos em ilhas p/ sleeping e tem solver compacto (`doc/mjwarp/index.rst` L360–L400) | ver Feature Parity em `doc/mjx.rst` |
| `accelerated` §8 | `jax_compilation_cache_dir` = `/tmp/jax_cache` | política do laboratório: nunca o `/tmp` literal (compartilhado e volátil) | `os.environ["TMPDIR"]` ou diretório do projeto fora do git |
| `rendering` §2 | `MUJOCO_GL=osmesa` "portátil" | ✔ neste laboratório `import mujoco` **falha** com `osmesa` (PyOpenGL sem libOSMesa) | `MUJOCO_GL=egl` |
| `gui`, `studio` | — | ✔ os 15 identificadores `módulo.nome` de `studio` e os 22 `imgui.*` de `gui` existem no wheel 3.15.0 (import); comportamento **não testado** (exige janela/servidor; o Studio não roda em Wayland, ver `AGENTS.md`) | guia de estilo/arquitetura, não de API |

```python
# skills_check.py — reproduz os erros ✔ da tabela (cwd fora da raiz; mjx/mujoco_warp não estão no venv: lê-se o código espelhado)
import ast, pathlib, mujoco as mj, numpy as np
from mujoco.introspect import functions as F, structs as S
UP = pathlib.Path("/home/ondokai/Projects/MuJoCo/docs/upstream"); res = []
def chk(skill, erro, ok): res.append(bool(ok)); print(("confirmado     " if ok else "NÃO CONFIRMADO ") + f"[{skill}] {erro}")
X = lambda body="": f"<mujoco><worldbody>{body}</worldbody></mujoco>"
# --- python/ e spec_editing/: C++ com nomes que não existem
chk("python §1, spec_editing §1", "mj_addBody/mj_addGeom/mjbBody NÃO existem; mjs_addBody/mjs_addGeom/mjsBody sim; mj_compile(s, vfs) tem 2 params",
    not {"mj_addBody", "mj_addGeom"} & set(F.FUNCTIONS) and "mjbBody" not in S.STRUCTS and {"mjs_addBody", "mjs_addGeom"} <= set(F.FUNCTIONS)
    and "mjsBody" in S.STRUCTS and [p.name for p in F.FUNCTIONS["mj_compile"].parameters] == ["s", "vfs"])
sp = mj.MjSpec(); b = sp.worldbody.add_body(name="b"); b.add_geom(size=[.1]); j = b.add_joint(name="j"); d = mj.MjData(sp.compile()); d.bind(j).qpos = 0.7
chk("spec_editing §4", "spec.delete_body/geom/joint/actuator não existem (use spec.delete(spec.body('x')))", not any(hasattr(sp, f"delete_{k}") for k in ("body", "geom", "joint", "actuator")))
chk("python §2", "data.bind(j).set('qpos', v) não existe em MjData (é do bind do MJX); atribuição direta funciona", not hasattr(d.bind(j), "set") and d.joint("j").qpos[0] == 0.7)
# --- spec_editing/
p, c = mj.MjSpec(), mj.MjSpec(); c.worldbody.add_body(name="hand").add_geom(size=[.05])
try: p.attach(c, prefix="left_"); e = ""
except ValueError as ex: e = str(ex)
p.attach(c, frame=p.worldbody.add_frame(), prefix="left_")
chk("spec_editing §3", "attach(child, prefix=) sem site/frame -> ValueError; com frame= funciona; add_equality sem kwarg 'anchor'", "frame or site" in e and "anchor" not in mj.MjSpec.add_equality.__doc__)
try: mj.MjSpec().add_mesh(name="m", vertex=[0.0], face=[0]); ok = False
except TypeError: ok = True
mj.MjSpec().add_mesh(name="m", uservert=np.zeros(9), userface=np.array([0, 1, 2], dtype=np.int32))
chk("spec_editing §8", "add_mesh(vertex=, face=) -> TypeError; os kwargs reais são uservert=/userface=", ok)
s2 = mj.MjSpec(); s2.worldbody.add_body(name="a", axisangle=[0, 0, 1, 90]).add_geom(size=[.1])
chk("spec_editing §2", "axisangle=[0,0,1,90] é 90 GRAUS (a skill diz angle_rad)", np.allclose(s2.compile().body("a").quat, [.7071, 0, 0, .7071], atol=1e-3))
s3 = mj.MjSpec(); rub = s3.add_default("rubber", s3.default); rub.geom.friction = [1.5, .01, .001]; bd = s3.worldbody.add_body()
bd.add_geom(rub, name="g1", size=[.1]); g2 = bd.add_geom(name="g2", size=[.1]); g2.classname = rub; m3 = s3.compile()
chk("spec_editing §6", "classname pós-criação só rotula: friction g1=1.5 (default no add_geom) x g2=1.0 (classname depois)", (m3.geom("g1").friction[0], m3.geom("g2").friction[0]) == (1.5, 1.0))
# --- rendering/
blk = mj.MjModel.from_xml_string("<mujoco><visual><global offwidth='1920' offheight='1080'/></visual><visual><headlight ambient='.3 .3 .3'/></visual><worldbody/></mujoco>")
chk("rendering §6", "dois <visual>: MESCLADOS (offwidth=1920 sobrevive ao 2º bloco), não 'só o último vale'", blk.vis.global_.offwidth == 1920 and blk.vis.headlight.ambient[0] > .29)
cm = mj.MjModel.from_xml_string(X("<camera name='a' pos='0 0 3' quat='0.707 0.707 0 0'/><camera name='b' pos='0 0 3'/>")); cd = mj.MjData(cm); mj.mj_forward(cm, cd)
look = lambda n: -cd.cam(n).xmat.reshape(3, 3)[:, 2]                      # câmera olha ao longo de seu -Z
chk("rendering §5", "quat=[.707,.707,0,0] olha p/ +Y (horizontal, não 'down'); quat identidade olha p/ -Z", np.allclose(look("a"), [0, 1, 0], atol=1e-2) and np.allclose(look("b"), [0, 0, -1]))
# --- accelerated/ (mjx e mujoco_warp NÃO estão no venv: assinaturas lidas do código espelhado)
def sig(path, fn): return [a.arg for a in next(n for n in ast.walk(ast.parse((UP / path).read_text())) if isinstance(n, ast.FunctionDef) and n.name == fn).args.args]
src = (UP / "mujoco/mjx/mujoco/mjx/_src/io.py").read_text()
chk("accelerated §6", "mjw.put_data(model, batch_size): a assinatura é put_data(mjm, mjd, nworld=…) (2º arg = MjData)", sig("mujoco_warp/mujoco_warp/_src/io.py", "put_data")[:3] == ["mjm", "mjd", "nworld"])
chk("accelerated §2/§4", "mjx.put_data aceita njmax mas o ramo JAX chama _put_data_jax(m, d, device) sem ele", "njmax" in sig("mujoco/mjx/mujoco/mjx/_src/io.py", "put_data") and "return _put_data_jax(m, d, device)" in src)
chk("accelerated §8", "a skill grava o cache XLA num diretório temporário global fixo (política do laboratório: use TMPDIR)", "/" + "tmp/jax_cache" in (UP / "mujoco/doc/skills/accelerated/SKILL.md").read_text())
print(f"{len(res)} erros inventariados, {len(res) - sum(res)} não confirmados (mujoco {mj.__version__})")
```
Saída (executado): `12 erros inventariados, 0 não confirmados (mujoco 3.15.0)`. As linhas `accelerated` também foram executadas no `.venv-gpu` (JAX e Warp em CPU, `CUDA_VISIBLE_DEVICES=""`, sem tocar a GPU); evidência complementar em `references/gpu-mjx-warp.md`. C corrigido (✔ `gcc -Wall -Wextra` contra o `libmujoco.so.3.15.0` do wheel; roda e imprime `nbody=2 ngeom=1`):

```c
// gcc t.c -I$W/include -L$W -l:libmujoco.so.3.15.0 -Wl,-rpath,$W     (W = .venv/lib/python3.13/site-packages/mujoco)
#include <stdio.h>
#include <mujoco/mujoco.h>
int main(void) {
  mjSpec* spec = mj_makeSpec();
  mjsBody* body = mjs_addBody(mjs_findBody(spec, "world"), NULL);   // NÃO existe mj_addBody(spec, ...) nem mjbBody
  mjsGeom* geom = mjs_addGeom(body, NULL);                          // NÃO existe mj_addGeom(body, tipo, ...)
  geom->type = mjGEOM_SPHERE; geom->size[0] = 0.1;
  mjModel* m = mj_compile(spec, NULL);                              // 2º arg = mjVFS*; o erro vem de mjs_getError(spec)
  if (!m) { puts(mjs_getError(spec)); return 1; }
  printf("nbody=%ld ngeom=%ld\n", (long)m->nbody, (long)m->ngeom);  // campos de tamanho são mjtSize (int64) desde 3.5.0
  mj_deleteModel(m); mj_deleteSpec(spec); return 0;
}
```

## 5. Inconsistências conhecidas da própria documentação (Δ doc)

| Onde | A doc diz | Verdade (medido ou no código) |
|---|---|---|
| `doc/changelog.rst` L897–L905 (3.7.0) | migrar URDF com `spec.compiler.strippath = True` | ✔ `strippath` é campo de `mjSpec`: `spec.strippath = True`; `spec.compiler.strippath` → AttributeError |
| `doc/programming/index.rst` L95, `doc/python.rst` L784 | "a working C++17 compiler" | `CMakeLists.txt` L59 usa `-std=c++20`; changelog 3.3.7: o mínimo é C++20 |
| `doc/python.rst` L862 | "two sub-modules: `mujoco.rollout` and `mujoco.minimize`" | ✔ o wheel também traz `sysid`, `usd`, `viewer`, `rendering.filament`, `experimental.studio`; o próprio `python.rst` L955 documenta "USD exporter" |
| changelog 3.3.3 × `doc/XMLreference.rst` L3289 | "`directional` substituído por `type`" × "atributo legado depreciado" | ✔ `directional="true"` ainda é aceito (`light_type` = directional); `type` aceita `spot, directional, point, image` |
| `doc/computation/index.rst` L186; `doc/programming/simulation.rst` L789–L792; `doc/APIreference/functions.rst` L1112 | ainda citam `mjData.qM` (tabela de M(q); "`qM` will be migrated to CSR in an upcoming change"; `mj_makeM` grava "both `qM` and `M`") | ✔ removido na 3.11.0: só existe `data.M` (CSR) |
| mensagem de erro do parser | `composite type="cloth"` → "Please use "shell" instead" | ✔ o plugin `shell` saiu na 3.3.3 (use flexcomp com `elastic2d`); `grid` → "flex", `particle` → "replicate", `rope` → "cable" |
| `doc/index.rst`, `doc/changelog.rst` | — | `doc/skills/` não está na toctree nem no changelog (0 ocorrências de "skill"); o Studio não tem capítulo (só a nota em `visualization.rst` L6–L11 e `skills/studio/SKILL.md`) |
| `README.md` | releases "na primeira semana de cada mês" | intervalos reais de 13 a 35 dias em 2026 (§2) |

As contradições skills × headers/bindings estão na §4 (nomes de API, `njmax`/`put_data`, blocos `<visual>`).

## 6. Experimental e opt-in em 3.15.0

| Recurso | Estado | Como usar / cuidado | Fonte |
|---|---|---|---|
| Sleeping islands | opt-in, "preliminary release for early testing" (3.4.0); desligado por padrão ✔ (`enableflags == 0`) | `<flag sleep="enable"/>` (`mjENBL_SLEEP`); `sleep_tolerance` 1e-3 (3.11.0); `mjd_transitionFD/inverseFD` erram com sleeping (3.14.0); estado compacto: salvar com `mj_copyData`; MJWarp suporta e tem solver compacto | `computation/index.rst` L2158, `programming/simulation.rst` L1231, `XMLreference.rst` L705 |
| Integrador `discrete` | "new (September 2026), under active development, and subject to change"; **não** é o padrão (Euler ✔; `implicitfast` é recomendado, não padrão) | exigido por elasticidade/contato passivo de flex; erro de runtime: flex elástico/passivo com PGS ou noslip, sleep sem ilhas, sleep+flex, flex interpolado preso a corpos móveis com Newton (exige CG) | `computation/index.rst` L722 |
| `ipc` e SNH | experimentais: `ipc` só com `discrete`+CG, sem replay exato do estado; SNH (`mjsFlex.elastic3d=1`) só via API, não salva em MJCF | `<flag ipc="enable"/>`; `elastic3d` exige `discrete` | `XMLreference.rst` L733 (flag `ipc`), `APIreference/APItypes.rst` L1853 |
| MuJoCo Studio | em desenvolvimento ativo; **sem capítulo** (a nota de `visualization.rst` promete atualizar a seção); único guia: `doc/skills/studio/SKILL.md` | Python `mujoco.experimental.studio` (`launch_web/native/passive`, `messages`, `viewer_app`) importa no wheel ✔; CMake `MUJOCO_BUILD_STUDIO` (OFF por padrão, `CMakeLists.txt` L45); neste laboratório **não roda em Wayland** (`AGENTS.md`: use X11); não executado aqui (sem janela/servidor) | `programming/visualization.rst` L6, `skills/studio/SKILL.md` |
| Filament | renderizador PBR alternativo: `MUJOCO_USE_FILAMENT=1` no CMake (OFF por padrão) troca as `mjr_*` por versões Filament e expõe `mjrf*`; Python `mujoco.rendering.filament` presente ✔ | `light/softness` (3.12.0), fallback PBR de `metallic` (3.13.0) e a amostra `render.cc` (3.13.0) dependem dele | `programming/visualization.rst` L493 |
| OpenUSD | "experimental and subject to frequent change" (todas as páginas `doc/OpenUSD/`); extra `mujoco[usd]`; CMake `MUJOCO_WITH_USD` (OFF); `mujoco.usd` presente ✔ | 3.12.0: schemas Newton 0.4.0 e atributos `mjc:*` depreciados | `doc/OpenUSD/index.rst` |
| MJX-Warp / MJWarp | MJWarp oficial desde 3.5.0; backend `impl='warp'` do MJX era "beta" na 3.3.5 (a doc 3.15 já não diz "beta"); sem autodiff; `mjx`, `mujoco_warp` e `jax` **não estão no `.venv`** (só no `.venv-gpu`; GPU não usada aqui; ver `references/gpu-mjx-warp.md`) | `mjx.make_data(m, impl='warp', naconmax=…, njmax=…)` | `doc/mjx.rst` L90–L125, `doc/mjwarp/index.rst` |
| Padrões conservadores que podem virar | `alignfree` false; `compiler/conflict` "warning" (futuro "merge"); dict `assets`, `spec.meshdir/texturedir`, `ngravcomp`, `mjs_isWarning` serão removidos | trate como dívida técnica: não use em código novo | §3 |

## 7. Correções ao relatório do usuário (§6: guias Computation/XML Reference)
Afirmação (§6 do relatório): o repositório principal "inclui o guia matricial 'Computation', que relata equações, bem como a documentação extensiva do dialeto MJCF em 'XML Reference'". **Veredito (Q16): correta, com nuances.** Correção ao relatório do usuário:
- ✔ Os dois existem em `google-deepmind/mujoco` e na toctree (`doc/index.rst`, 2º e 4º itens), publicados em mujoco.readthedocs.io: `doc/computation/index.rst` (148 KB) e `doc/XMLreference.rst` (454 KB).
- "Computation" é o guia **matemático e algorítmico** (equações: 42 blocos `.. math::` em `index.rst` + 31 em `fluid.rst`), não "matricial" nem manual de referência. Os manuais de referência autodeclarados são **XML Reference** (esquema + todos os elementos e atributos, com padrões) e **API Reference**; o guia de *uso* do MJCF é **Modeling** (`doc/modeling.rst`).
- São 2 dos 13 capítulos da toctree: o relatório omite Programming, API Reference, Python, MJX, MJWarp, Unity, OpenUSD, Model Gallery e o changelog, e ignora `doc/skills/` (6 skills oficiais fora da toctree, com erros: §4).
- Obsolescência: a tabela de M(q) em Computation ainda cita `mjData.qM`, removido na 3.11.0 (use `data.M`): Δ doc da §5. A gramática MJCF tem fonte única em `src/xml/mjcf.schema` desde a 3.12.0 (fora do espelho).
- O resto do §6 do relatório (urdf2mjcf, K-Scale, CoACD) está fora do escopo deste arquivo.

## Armadilhas

| Sintoma | Causa | Correção |
|---|---|---|
| `AttributeError` em `data.qM`, `solver_iter`, `model.nstack`, `tex_rgb`…; XML com `Schema violation: unrecognized attribute` | símbolo ou atributo removido/renomeado (§3) | rode o probe; `docs_search.py --changelog "<símbolo qualificado>"`, depois `--attr/--api` |
| Modelo antigo carrega, mas contatos, estabilidade ou amortecimento mudaram, sem erro | defaults e semântica (linhas ⚠: nativeccd, islands, multiccd, margin/gap, bvactive, dampratio, dcmotor…) | fixe flags (`<flag nativeccd="disable"/>`…) para comparar; meça a física; não espere igualdade bit a bit |
| `ValueError: One of frame or site must be specified` | `MjSpec.attach` exige `site=` ou `frame=` | `p.attach(c, frame=p.worldbody.add_frame(), prefix='x_')` |
| `delete_body`, `bind().set`, `add_mesh(vertex=…)`, `mj_addBody` não existem | snippet copiado das skills oficiais (§4) | use as formas da §4 e teste antes |
| `data.actuator('x').ctrl = v` escreve em outro atuador | `nu ≠ nactuator` (pid, dcmotor, orientation) | `data.ctrl[ctrladr[i]:ctrladr[i]+ctrlnum[i]]` |
| `docs_search.py --changelog qM` devolve ruído | busca por substring | `--changelog "mjData.qM"` |
| malhas de URDF somem; `joint.stiffness = v` dá TypeError; `mjx.render` desempacota errado | 3.7.0 (strippath, arrays) e 3.12.0 (retorno com `d`) | `spec.strippath = True`; `stiffness[0] = v`; `rgb, depth, d = …` |
| `import mujoco` falha com `MUJOCO_GL=osmesa` | falta libOSMesa neste laboratório | `MUJOCO_GL=egl` |
| cache ou temporários em `/tmp/...` bloqueados ou perdidos | skills oficiais assumem `/tmp` | `$TMPDIR` ou diretório do projeto |
| snippet C não compila (`mj_addBody`, `mj_compile(spec, err, n)`) | a API real é `mjs_*` e `mj_compile(spec, vfs)` | C da §4; `printf` de `m->nbody` com `%ld` |
