#!/usr/bin/env python3
"""Gera pesquisas/briefs/Q<n>.md a partir da tabela abaixo (um brief por investigador).

Cada brief é lido por UM investigador (context-minimization): pergunta, porque importa, critério de resposta,
afirmações do relatório do utilizador a auditar (hipóteses), fronteiras, fontes locais e esforço.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "briefs"
RET = "/home/ondokai/Projects/MuJoCo/pesquisas/retornos"

Q = {}

Q["Q1"] = dict(
    pergunta="Qual é a última versão estável do MuJoCo, que versões de Python suporta e qual é o método de instalação oficial em Linux (wheel PyPI, binários, CMake) — incluindo o estado REAL dos pacotes Arch/AUR e de `find_package(mujoco)` / `pkg-config`?",
    porque="Base da skill: instalação reprodutível em CachyOS/Arch (x86-64-v3) com Python 3.13/3.14, e corrigir o §3.1 do relatório.",
    criterio="(1) versão estável + data + `requires-python` + wheels disponíveis (manylinux x86_64/aarch64; cp313/cp314) com fonte primária; (2) instruções oficiais de instalação em Linux (pip, binários .tar.gz, build do código-fonte, dependências de sistema); (3) estado dos pacotes no AUR/repos Arch (nomes exatos, mantenedor, versão, se estão atualizados em out/2026); (4) se a instalação oficial expõe `find_package(mujoco CONFIG)`, o alvo `mujoco::mujoco` e/ou `mujoco.pc` (pkg-config) — e como se liga um programa C/C++ ao MuJoCo; (5) se `LD_LIBRARY_PATH` ainda é preciso hoje (contraste com o antigo mujoco-py/2.1); (6) o que o pacote PyPI inclui (bindings, libmujoco, `mujoco.viewer`, `mjpython`, `simulate`).",
    afirmacoes=[
        "O wheel oficial da DeepMind instalado por pip traz os bindings E as bibliotecas C compiladas dinâmicas associadas.",
        "O AUR oferece `python-mujoco`, empacotando os binários do sistema (a prática moderna recomenda, ainda assim, um virtualenv + wheel).",
        "Em CMake liga-se com `pkg_search_module(MUJOCO mujoco)` e `target_link_libraries(my_app PUBLIC mujoco::mujoco)`.",
        "Um virtualenv evita as antigas manipulações de `LD_LIBRARY_PATH` das versões antigas do MuJoCo.",
        "No Arch/CachyOS convém garantir gcc-libs, glibc, ninja, cmake e glfw; o CachyOS recompila pacotes para x86-64-v3.",
    ],
    fronteiras="cobre instalação/empacotamento/versões; NÃO cobre renderização/GL (Q2) nem MJX/Warp (Q11).",
    locais="docs/upstream/mujoco/doc/overview.rst (Installation), doc/python.rst (Installation), python/README.md, python/pyproject.toml, doc/changelog.rst (topo), VERSIONING.md, CMakeLists.txt. Web: pypi.org/project/mujoco, github.com/google-deepmind/mujoco/releases, aur.archlinux.org, archlinux.org/packages.",
    esforco="6–10 consultas web; leitura integral das secções de instalação; 2–3 testes empíricos (ex.: `import mujoco; mujoco.__file__`, listar `site-packages/mujoco` para ver libmujoco, `mjpython`, `include/`, cmake config).",
)

Q["Q2"] = dict(
    pergunta="Como se renderiza e visualiza o MuJoCo 3.15 em Linux com Wayland + NVIDIA (laptop com PRIME offload; sessão KDE Plasma Wayland com XWayland, `DISPLAY=:0`): backends GLFW / EGL / OSMesa / Filament, variáveis `MUJOCO_GL` e `PYOPENGL_PLATFORM`, `mujoco.Renderer`, `mujoco.viewer` (`launch`, `launch_passive`, `python -m mujoco.viewer`), o app Studio/`simulate` e `mjpython` no macOS — e que problemas conhecidos existem?",
    porque="A skill precisa de uma matriz de decisão (janela interativa vs. vídeo headless) que funcione nesta máquina, e o §3.2 do relatório precisa de auditoria.",
    criterio="(1) matriz backend × requisitos × quando usar × limitações (GLFW com janela; EGL headless com GPU NVIDIA; OSMesa em CPU; Filament experimental); (2) comportamento do wheel `glfw` em Wayland/XWayland e o que fazer quando a janela não abre; seleção de GPU em EGL (`MUJOCO_EGL_DEVICE_ID`, PRIME); erros típicos (`GLFWError`, `X11: The DISPLAY`, `libEGL warning`, `OSMesa`) e soluções; (3) viewer: `launch` bloqueante vs `launch_passive` (`viewer.sync()`, `viewer.lock()`, `is_running`), regras de thread; `python -m mujoco.viewer --mjcf=…`; (4) o que é o MuJoCo Studio/`mujoco.experimental.studio` e como se corre; o binário `simulate`; (5) `mjpython` e a restrição de main thread no macOS (confirmar com fonte oficial).",
    afirmacoes=[
        "O macOS proíbe operações OpenGL/GLFW fora da main thread; chamar `viewer.launch_passive()` numa thread de background causa um SegFault.",
        "A solução é usar o `mjpython` em vez de `python`, que força a representação passiva na thread principal.",
        "No macOS instala-se `pip install mujoco` e o GLFW vem do Homebrew.",
    ],
    fronteiras="cobre renderização/viewers/GL em Linux (+ nota macOS); NÃO cobre instalação do pacote (Q1) nem GPU de simulação (Q11).",
    locais="docs/upstream/mujoco/doc/python.rst (Viewer, Renderer, MUJOCO_GL), doc/programming/visualization.rst, doc/overview.rst, doc/skills/rendering/SKILL.md, doc/skills/studio/SKILL.md, python/mujoco/{viewer.py,renderer.py,gl_context.py,egl/,glfw/,osmesa/,mjpython/,rendering/}.",
    esforco="8–12 consultas web (inclui issues do GitHub e fóruns sobre Wayland/NVIDIA/EGL); 3–4 testes empíricos OFFSCREEN (`MUJOCO_GL=egl` com `mujoco.Renderer`; tenta também `osmesa` e `glfw` apenas para ver se o MÓDULO carrega, sem abrir janela). Esta máquina TEM EGL a funcionar offscreen.",
)

Q["Q3"] = dict(
    pergunta="Que integradores (`mjtIntegrator`) e solvers de restrições (`mjtSolver`: PGS, CG, Newton; `noslip`) existem em 3.15, qual é o valor por omissão (confirmar compilando `<mujoco/>`), qual é a recomendação oficial e quais são as condições de estabilidade e uso de cada um (timestep, iterations, tolerance, ls_iterations, jacobian, cone, impratio)?",
    porque="Escolher integrador/solver é a decisão nº 1 de estabilidade em robôs, drones e veículos; o §2.2 do relatório pode estar impreciso.",
    criterio="Tabela completa: integrador → o que faz → custo → quando usar → limitações (RK4 com contactos? implicit vs implicitfast e as derivadas usadas?); solvers → quando usar; valores por omissão de `model.opt.*` por teste empírico (timestep, integrator, solver, iterations, ls_iterations, tolerance, cone, jacobian, impratio, gravity, density, viscosity, wind); recomendação oficial textual; quando aumentar `iterations`; efeito do `timestep`.",
    afirmacoes=[
        "A equação fundamental é τ = M(q)·v̇ + c(q,v), com c agregando Coriolis, centrífuga e gravidade; τ inclui atuadores, aerodinâmica e forças passivas.",
        "c(q,v) é calculado pelo algoritmo de Newton-Euler Recursivo (RNE); M(q) pelo Composite Rigid Body (CRB); a fatorização esparsa L^T D L resolve por retro-substituição.",
        "Euler semi-implícito dá o máximo de desempenho e é o padrão em RL.",
        "RK4 'preserva rotações e o rácio conservador de energia (h|ω|)²' e é indicado para pêndulos, biomecânica e robôs orbitais.",
        "O integrador implícito tem 'estabilidade incondicional' e trata rigidez extrema acoplando molas (fluidodinâmica/flexibilidade elástica).",
        "Um passo de tempo (dt) demasiado grande induz explosão algébrica.",
    ],
    fronteiras="cobre integradores, solvers e parâmetros de `<option>`; NÃO cobre o modelo de contacto (Q4) nem diagnóstico (Q14).",
    locais="docs/upstream/mujoco/doc/computation/index.rst (Integrators, Solvers), doc/XMLreference.rst (elemento `option`), doc/changelog.rst (grep implicitfast, integrator), doc/APIreference/APItypes.rst (mjtIntegrator, mjtSolver), doc/skills/python/SKILL.md.",
    esforco="4–8 consultas web (corroboração e experiência de uso); leitura integral das secções de computation; 3–5 testes empíricos (defaults de `opt`; um pêndulo conservativo com Euler/RK4/implicit/implicitfast medindo deriva de energia com `mjENBL_ENERGY`).",
)

Q["Q4"] = dict(
    pergunta="Como funciona o modelo de contacto do MuJoCo 3.15 e os seus parâmetros (solref, solimp, margin, gap, condim, friction, solmix, priority, contype/conaffinity, `<contact><pair>`/`<exclude>`, cone pyramidal/elliptic, impratio, noslip) e as afirmações dos §2.3 e §2.4 do relatório estão corretas?",
    porque="O contacto determina quedas, tombos, pneus e garras; é a parte mais mal compreendida do MuJoCo e a base do experimento de demonstração.",
    criterio="(1) fórmulas oficiais do soft constraint (a_ref = −b·v − k·r; impedância d(r); como timeconst/dampratio viram k e b; modo direto com valores negativos de solref); (2) significado EXATO de solimp (dmin, dmax, width, midpoint, power), com valores por omissão (empírico); (3) semântica de condim 1/3/4/6, do vetor `friction` (3 números) e como se combinam entre dois geoms (max? solmix? priority?); (4) cones (pyramidal vs elliptic), impratio, noslip; (5) filtragem de colisões: contype/conaffinity, parent-child, `<exclude>`, `<pair>`; (6) regra prática timeconst ≥ 2·timestep e outras regras oficiais; (7) matriz de pares geom×geom suportados e papel da malha (convex hull).",
    afirmacoes=[
        "O MuJoCo reformula o contacto como otimização convexa com 'soft contacts', ao contrário dos motores LCP de complementaridade estrita; tolera interpenetrações subtis.",
        "A dinâmica do constraint obedece a a1 + d·(b·v + k·r) = (1 − d)·a0, com d = impedância, k = rigidez, b = amortecimento.",
        "`solimp` 'determina a impedância espacial do material variando entre limites estritos (d0 e d_width)'.",
        "`solref` define 'constante de tempo (timeconst) e rácio de amortecimento (dampratio)'.",
        "Os cones de fricção podem ser elípticos ou piramidais, configuráveis globalmente.",
        "condim: 1 = sem atrito (só normal); 3 = tangencial (2 eixos); 4 = + torsional (pneu parado no asfalto); 6 = + rolamento (2 eixos) para esferas/cilindros.",
    ],
    fronteiras="cobre contactos e filtragem; NÃO cobre integradores (Q3) nem a receita completa de veículos (Q9).",
    locais="docs/upstream/mujoco/doc/computation/index.rst (Soft constraints, Contact), doc/XMLreference.rst (geom, pair, exclude, default, contact, option), doc/modeling.rst (Contact parameters/Solver parameters), doc/changelog.rst.",
    esforco="6–10 consultas web; leitura integral das secções de contacto; 5–8 testes empíricos (defaults de geom_solref/solimp/friction/condim; tabela de colisão; uma esfera a cair e a quicar com solref variável medindo penetração e ressalto).",
)

Q["Q5"] = dict(
    pergunta="Qual é a estrutura do MJCF em 3.15: elementos de topo e sub-elementos principais, defaults/classes, tipos de joint e de geom, inércia (`inertiafromgeom`, `density`, `inertia` legacy/exact/shell), malhas (`<mesh vertex=…>`, convex hull, `maxhullvert`, scale), `<include>`, `<attach>`, `<frame>`, `<replicate>`, `<flexcomp>`/composite, `<model>`, `<custom>`, `<extension>`, `<keyframe>`; e o que mudou ou foi descontinuado desde 3.0?",
    porque="Cheat-sheet de MJCF para a skill e auditoria do §2.5 do relatório (classes visual/collision, inércia por densidade).",
    criterio="Resumo estruturado e fiel: lista de elementos com atributos-chave e padrões; armadilhas (um só bloco `<visual>`; `compiler angle` em graus por omissão; quaternions wxyz; `autolimits`; `meshdir`; unidades SI; orientação mutuamente exclusiva quat/euler/axisangle/xyaxes/zaxis); como se faz herança de defaults; o que foi removido/depreciado ao longo de 3.x (com versão); suporte a inércia de malhas.",
    afirmacoes=[
        "O MJCF funciona 'quase como um compilador' que converte geometrias e propriedades em ponteiros puros na memória da simulação.",
        "Os nós principais são `<compiler>`, `<option>`, `<worldbody>`, `<body>`, `<joint>` (hinge, ball), `<geom>`, `<tendon>` e `<actuator>`.",
        "`<geom>` pode separar o visual (`class=\"visual\"`) do de colisão (`class=\"collision\"`) por classes de defaults.",
        "Se a inércia não for dada, é inferida do volume dos geoms usando a densidade padrão da água (1000 kg/m³).",
        "O URDF 'especifica hierarquias topológicas sem otimização direta de dados' ao contrário do MJCF.",
    ],
    fronteiras="cobre MJCF/modelagem; NÃO cobre a API MjSpec (Q6), atuadores/sensores em detalhe (Q7) nem URDF (Q12).",
    locais="docs/upstream/mujoco/doc/XMLreference.rst, doc/modeling.rst, doc/XMLschema.rst, doc/changelog.rst, model/*/ (exemplos: humanoid, car, replicate, flex, tendon_arm…), doc/skills/spec_editing/SKILL.md.",
    esforco="6–10 consultas web; leitura integral de modeling.rst e das secções-chave do XMLreference; 4–6 testes empíricos (compilar mini-modelos: defaults, density→massa, mesh vertex, attach/replicate, inertia exact).",
)

Q["Q6"] = dict(
    pergunta="Qual é a API Python moderna do MuJoCo 3.15 para modelar, simular e inspecionar (MjSpec→MjModel→MjData; named access; `bind()`; `mj_step(nstep)`; `mj_step1/2`; `mj_forward`; keyframes; `mj_getState/setState`; `mujoco.rollout`; `mjd_transitionFD`/`mjd_inverseFD`; `mj_contactForce`; `mj_ray`; callbacks `set_mjcb_*`; `mujoco.minimize`) e o que está incorreto ou desatualizado no §4 do relatório?",
    porque="Padrões corretos de código para a skill (e para os experimentos): evitar `mj_name2id`/índices crus, cópias vs views, quaternions wxyz.",
    criterio="Lista de funções/classes com assinaturas REAIS verificadas por introspecção em 3.15.0 (`help`, `inspect`, `dir`); semântica de views vs cópias; `MjSpec` mínimo funcional (criar corpo+geom+joint+atuador, compilar, recompilar); `mj_contactForce` (assinatura, frame do contacto, como converter para o mundo); o que são callbacks `set_mjcb_control`/`set_mjcb_sensor` em Python e o custo/GIL; `mujoco.rollout` (assinatura, multithread); o código do relatório corrigido e testado.",
    afirmacoes=[
        "`MjModel` é o plano estático (imutável após a conversão do MJCF) e `MjData` guarda o estado temporal: `qpos`, `qvel`, `qacc`, `sensordata`, `ctrl`.",
        "Atribuir via slices do NumPy aos campos de `MjData` mapeia memória C diretamente: uma referência sem cópia sobrepõe valores e pode viciar resultados.",
        "O código do relatório usa `mujoco.mj_name2id(modelo, mujoco.mjtObj.mjOBJ_ACTUATOR, \"atuador_principal\")` para obter o id do atuador e `data.ctrl[id] = torque`.",
        "O relatório usa `viewer.sync()` dentro de `launch_passive` e `time.sleep` para sincronizar com o tempo real.",
        "`mj_step` invoca internamente `mj_forward`.",
        "Callbacks `mjcb_control`/`mjcb_sensor` em Python 'induzem chamadas repetitivas ao GIL durante as quatro derivações do RK4 num único mj_step', paralisando o solver; a mitigação é usar extensões C via ctypes.",
        "`mujoco.rollout` oferece paralelismo multithread em CPU.",
    ],
    fronteiras="cobre a API Python e o ciclo de vida; NÃO cobre MJCF (Q5), render (Q2), GPU (Q11) nem estabilidade (Q14).",
    locais="docs/upstream/mujoco/doc/python.rst, doc/skills/python/SKILL.md, doc/skills/spec_editing/SKILL.md, python/mujoco/{__init__.py,bindings_test.py,minimize.py,rollout.py?,introspect/}, python/{mjspec,rollout,tutorial,LQR,least_squares}.ipynb.md, doc/APIreference/*.rst, doc/programming/{simulation,modeledit}.rst.",
    esforco="8–12 consultas web; leitura integral de python.rst e das skills oficiais; 6–10 testes empíricos de API (inclui executar o snippet do relatório sem viewer e a versão corrigida).",
)

Q["Q7"] = dict(
    pergunta="Que tipos de atuadores (motor, position, velocity, intvelocity, damper, cylinder, muscle, adhesion, dcmotor, general), sensores, tendões (fixed/spatial), restrições de igualdade, mocap e keyframes existem no 3.15 e quais são os parâmetros-chave (gaintype/biastype/dyntype, gear, ctrlrange, forcerange, kp/kv…) para controlar robôs?",
    porque="Robôs, drones e veículos precisam de atuadores e sensores corretos; a skill deve ter tabelas completas e fiéis.",
    criterio="(1) tabela de atuadores: atalho → equivalente `general` (gaintype/biastype/dyntype, gainprm/biasprm/dynprm) e parâmetros; novidade `dcmotor` (o que é, quando usar); (2) lista COMPLETA de sensores com o que medem e dimensão (inclui imu, framepos, framequat, gyro, accelerometer, force/torque, touch, rangefinder, contact, tendon*, actuator*, jointpos/vel, subtreecom, user…); (3) tendões e como acoplam juntas (differential, gear); (4) equality (connect, weld, joint, tendon, flex) e uso em engrenagens/mecanismos fechados; (5) mocap bodies; (6) receitas: PD, torque, velocidade, gripper.",
    afirmacoes=[
        "`<tendon>` e `<actuator>` modelam a anatomia biomecânica de músculos com leis FLV (Force-Length-Velocity) e atuadores elétricos mapeados a transmissões mecânicas das juntas.",
        "Exemplo mínimo: `<motor name=\"atuador_principal\" joint=\"junta_motor\" gear=\"1.0\"/>` num hinge, controlado por `data.ctrl`.",
    ],
    fronteiras="cobre atuadores/sensores/tendões/equality/mocap/keyframes; NÃO cobre contactos (Q4), drones (Q8), veículos (Q9).",
    locais="docs/upstream/mujoco/doc/XMLreference.rst (actuator, sensor, tendon, equality, keyframe, custom), doc/computation/index.rst (actuation), doc/dcmotor/dcmotor.tex, model/{tendon_arm,slider_crank,humanoid,adhesion,tactile}/.",
    esforco="6–10 consultas web; leitura integral das secções; 5–8 testes empíricos (listar `mujoco.mjtSensor`/`mjtGain`/`mjtBias`/`mjtDyn`, compilar atuadores de cada atalho e ler `actuator_gainprm/biasprm`).",
)

Q["Q8"] = dict(
    pergunta="Como se modela um DRONE (quadricóptero) no MuJoCo: modelo de fluido (`density`, `viscosity`, `wind`; inertia-box vs elipsoide `fluidshape`; `fluidcoef`), empuxo e binário reativo dos rotores, exemplos oficiais (Menagerie: Skydio X2, Crazyflie 2) e limites — e o §5.1 do relatório está correto?",
    porque="O utilizador quer criar drones; a skill precisa de uma receita VERIFICADA de quadricóptero com controlo de voo estacionário e de saber o que o MuJoCo NÃO modela.",
    criterio="(1) equações e valores por omissão de `fluidcoef` (confirmar 0.5/0.25/1.5/1.0/1.0 por teste empírico) e a regra de qual dos DOIS modelos de fluido é usado (inertia-box vs elipsoide), com a condição exata; (2) como os modelos oficiais Skydio X2 e Crazyflie 2 do Menagerie definem rotores/atuadores/sites/gear/massa/inércia (ler os XMLs locais); (3) uma receita mínima de quadricóptero (4 `motor` com `gear` no eixo z e torque de guinada ± por rotor), cálculo do empuxo de hover, e um controlador PD/PID de altitude+atitude TESTADO por si em simulação (reporta números: tempo de assentamento, erro final de altitude); (4) limites: aerodinâmica de pás, efeito de solo, bateria/ESC, vento turbulento, asa fixa.",
    afirmacoes=[
        "Com `fluidshape=\"ellipsoid\"` o MuJoCo desativa o cálculo esférico básico orientado pela inércia e usa um modelo aerodinâmico 3D por geom (com Kutta-Joukowski e efeito Magnus).",
        "`fluidcoef` por omissão: arrasto de corpo rombudo (blunt) 0.5; arrasto esbelto (slender) 0.25; arrasto angular 1.5; sustentação de Kutta 1.0; efeito Magnus 1.0.",
        "Os fatores combinam-se com `density`, `viscosity` e `wind` definidos em `<option>`.",
        "O modelo de fluido resulta numa forte atenuação de objetos voadores por resistência viscosa.",
    ],
    fronteiras="cobre fluido e drones; NÃO cobre veículos terrestres (Q9) nem GPU (Q11).",
    locais="docs/upstream/mujoco/doc/computation/fluid.rst, doc/XMLreference.rst (option, geom fluidshape/fluidcoef), doc/computation/index.rst, docs/upstream/mujoco_menagerie/{skydio_x2,bitcraze_crazyflie_2}/ (XML+README), model/ do mujoco.",
    esforco="10–15 consultas web (literatura de quadricópteros em MuJoCo, issues, projetos tipo gym/mujoco quadrotor, limites aerodinâmicos); leitura integral de fluid.rst; 8–12 testes empíricos (inclui a simulação de hover).",
)

Q["Q9"] = dict(
    pergunta="Como se modela um VEÍCULO de rodas no MuJoCo (pneus, atrito e condim, suspensão, direção, diferencial/tração), qual é o exemplo oficial (`model/car`) e quais são os limites do contacto pneu-solo?",
    porque="O utilizador quer criar veículos; a skill precisa de uma receita verificada de carro/robô de rodas e das boas práticas de contacto (condim 4/6, solref, cone).",
    criterio="(1) análise do exemplo oficial `docs/upstream/mujoco/model/car/` (como rodas, direção, suspensão e atuadores são definidos; parâmetros usados); (2) boas práticas de pneu: geom (cylinder/ellipsoid/capsule), `friction` (3 valores), `condim` 3/4/6, `solref/solimp`, cone elliptic, `impratio`, `noslip_iterations`; (3) direção (hinge + `position` actuator), tração (`velocity`/`motor`), suspensão (slide + stiffness/damping), diferencial (tendão fixed ou equality); (4) limitações (não há modelo de pneu tipo Pacejka nativo; escorregamento, instabilidade a alta velocidade; plugin?), alternativas; (5) um carro mínimo TESTADO por si (acelera, curva) com números (velocidade final, raio de curva).",
    afirmacoes=[
        "Para materiais que rodam sobre si (pneus), o atributo `condim` do geom é essencial: condim 4 adiciona atrito torsional (bloqueia rotação em torno da normal) e condim 6 adiciona atrito de rolamento.",
        "O relatório refere a simulação de 4096 'carros robóticos' em paralelo (GPU) como cenário de RL.",
    ],
    fronteiras="cobre veículos de rodas; NÃO cobre drones (Q8) nem o motor de contacto em abstrato (Q4).",
    locais="docs/upstream/mujoco/model/car/, doc/XMLreference.rst (geom friction/condim, actuator), doc/computation/index.rst (contact), docs/upstream/mujoco_playground (procurar ambientes com rodas), docs/upstream/mujoco_menagerie (procurar bases móveis com rodas: stretch, google_robot…).",
    esforco="10–15 consultas web (carros/rodas/pneus em MuJoCo, fóruns/issues, artigos); leitura integral do XML do carro; 8–12 testes empíricos (inclui simulação de condução).",
)

Q["Q10"] = dict(
    pergunta="Qual é o estado em 2026 do ecossistema de modelos e frameworks ao redor do MuJoCo: MuJoCo Menagerie (modelos e licenças), `robot_descriptions`, `dm_control`, Gymnasium (MuJoCo v5), MuJoCo Playground, MuJoCo MPC (MJPC), Brax, mjlab?",
    porque="A skill deve indicar a melhor fonte de modelos prontos e o framework certo para RL/controlo, com comandos de instalação atuais.",
    criterio="Para cada projeto: o que é, estado/atividade em out/2026 (última release/commit), como se instala (comando + Python suportado), para que serve, e relação com 3.15 (compatibilidade); Menagerie: categorias de modelos (braços, humanoides, quadrúpedes, drones, mãos, bases móveis) a partir do README local e a política de licenças POR modelo; Playground: lista de ambientes e backends (MJX/Warp); MJPC: estado; verifica se `mjlab` existe e o que é.",
    afirmacoes=[
        "Os repositórios principais da DeepMind (mujoco, mujoco_warp, mujoco_playground, mujoco_menagerie, mujoco_mpc) são públicos e mantidos; o relatório não os enumera.",
    ],
    fronteiras="cobre ecossistema/modelos/frameworks; NÃO cobre MJX/Warp em profundidade (Q11) nem URDF (Q12).",
    locais="docs/upstream/mujoco_menagerie/README.md e */README.md, docs/upstream/mujoco_playground/{README.md,CHANGELOG.md}, docs/upstream/mujoco_mpc/{README.md,docs/}, doc/models.rst. Web: PyPI (dm_control, gymnasium, robot_descriptions, playground, brax, mjlab), GitHub.",
    esforco="10–15 consultas web; 3–4 fontes lidas na íntegra; verificar versões/Python no PyPI; ler READMEs locais.",
)

Q["Q11"] = dict(
    pergunta="Qual é a relação oficial entre MJX (JAX) e MuJoCo Warp (MJWarp) no MuJoCo 3.15, como se instalam (CUDA, JAX, `warp-lang`), que limites têm face ao motor C (solvers, plugins, float32, `njmax`/`nconmax`), os números '2,33 M SPS (MJX) e 2,96 M SPS (MJWarp) no Humanoid' do relatório estão corretos, e uma RTX 4070 Laptop de 8 GB serve?",
    porque="Escalar RL/otimização em GPU é um objetivo; a skill precisa da verdade atual (o relatório fala em 'MJX-Warp' e em desempenho) e do caminho de instalação nesta máquina (driver NVIDIA 610.57, Python 3.13).",
    criterio="(1) estado oficial dos dois backends em 3.15 (qual é recomendado; MJX está em manutenção?); (2) instalação exata: pacotes PyPI (`mujoco-mjx`, `mujoco-warp`), extras (`jax[cuda13]`/`cuda12`), requisitos de driver/CUDA/Python; (3) API mínima (mjx.put_model/make_data/step + jax.vmap; mujoco_warp: put_model/make_data/step; batch, nworld), diferenças vs C (tabela de recursos suportados/não suportados); (4) NÚMEROS publicados de desempenho (paper/blog/docs/benchmarks locais): hardware, robô, SPS, e se 2,33 M / 2,96 M aparecem em alguma fonte; (5) diferenciabilidade (MJX: sim; Warp: ?); (6) adequação a 8 GB de VRAM.",
    afirmacoes=[
        "O MJX é uma reimplementação do motor em JAX/XLA que roda em GPU/TPU com `mjx.Model`/`mjx.Data` em batch; usam-se `mjx.put_model` e `mjx.make_data`.",
        "O MJX-Warp/MJWarp 'otimiza operações tensoriais em chips CUDA da NVIDIA, sacrificando diferenciações analíticas'.",
        "Tabela do relatório (Humanoid): MuJoCo CPU 'otimizado para latência'; MJX (JAX) 2,33 milhões de SPS; MJWarp (CUDA/NVIDIA) 2,96 milhões de SPS.",
        "A versão sequencial em CPU (inclui `mujoco.rollout` multithread) 'estrangula' com 4096 instâncias em paralelo.",
        "Domain randomization faz-se enviando modelos com inércia/geometria diferentes via `mjx.put_model`.",
    ],
    fronteiras="cobre MJX/MJWarp/GPU; NÃO instala nada (o orquestrador testa a instalação à parte); NÃO cobre RL/Playground em detalhe (Q10).",
    locais="docs/upstream/mujoco/doc/{mjx.rst,mjx_api.rst,mjwarp/index.rst,skills/accelerated/SKILL.md}, mjx/ (código e notebooks .md), docs/upstream/mujoco_warp/{README.md,AGENTS.md,.agent/,benchmarks/,notebooks/}, mujoco_playground. Web: arXiv do MuJoCo Warp/MJX/Playground, pypi.org/project/{mujoco-mjx,mujoco-warp,warp-lang,jax}.",
    esforco="12–15 consultas web (inclui arXiv/blog oficial/NVIDIA); 4 fontes lidas na íntegra; procure especificamente a origem dos números 2,33 M e 2,96 M SPS.",
)

Q["Q12"] = dict(
    pergunta="Como se importam URDF e malhas no MuJoCo 3.15: suporte nativo a URDF (extensão `<mujoco>` no URDF, opções do `compiler`), `urdf2mjcf` (K-Scale Labs), decomposição convexa (CoACD/VHACD), conversão de malhas — e o §6 do relatório está correto?",
    porque="Robôs reais chegam em URDF/CAD; a skill precisa do caminho correto de importação e de boas práticas de colisão convexa.",
    criterio="(1) como o MuJoCo carrega URDF diretamente e limitações (meshdir, inércia, `balanceinertia`, `discardvisual`, `fusestatic`, juntas não suportadas); (2) o que `urdf2mjcf` FAZ de facto (README/código no GitHub: instalação, comandos, opções, tratamento de inércia, classes visual/collision, CoACD?); (3) alternativas (obj2mjcf, `mujoco.MjSpec.from_file`, mesh convex hull automático, `maxhullvert`, SDF/plugin); (4) como lidar com malhas côncavas (decomposição convexa) e regras (nº máximo de vértices); (5) licenças e manutenção (último commit).",
    afirmacoes=[
        "`pip install urdf2mjcf` e `urdf2mjcf robot.urdf --output robot.mjcf` convertem URDF em MJCF (projeto da K-Scale Labs).",
        "O conversor examina assimetrias indesejáveis na diagonal da inércia e procede ao seu 'nivelamento algébrico'.",
        "Separa as malhas de colisão (`class=\"collision\"`) das puramente visuais (`class=\"visual\"`).",
        "Implementa decomposição convexa CoACD, gerando geometrias convexas com `class=\"decomposed_collision\"`, coloridas por paleta.",
        "O URDF não tem os ajustes de soft contact (solref/solimp) do MuJoCo.",
        "O repositório do MuJoCo traz o guia 'Computation' e a 'XML Reference'.",
    ],
    fronteiras="cobre importação URDF/malhas e decomposição; NÃO cobre MJCF em geral (Q5).",
    locais="docs/upstream/mujoco/doc/XMLreference.rst (compiler, mesh, URDF), doc/modeling.rst, doc/programming/modeledit.rst, doc/changelog.rst (grep URDF, convexhull, maxhullvert). Web: github.com/kscalelabs/urdf2mjcf, github.com/kevinzakka/obj2mjcf, github.com/SarahWeiii/CoACD.",
    esforco="8–12 consultas web; ler README/código do urdf2mjcf na íntegra; 2–4 testes empíricos (compilar um URDF mínimo de 2 links com o carregador nativo do MuJoCo 3.15).",
)

Q["Q13"] = dict(
    pergunta="Como se integra o MuJoCo com o Rerun (SDK Python atual, v0.38.x): API correta de `rr.init`, tempo (`rr.set_time…`), `rr.log`, `Points3D`, `Arrows3D`, `Transform3D`, `Mesh3D`, `Scalars`; existe exemplo oficial; como converter `mj_contactForce` para o referencial do mundo — e o §5.2 do relatório está correto?",
    porque="Telemetria multimodal de drones/veículos; a API do Rerun mudou várias vezes e o relatório pode usar nomes antigos.",
    criterio="(1) assinaturas ATUAIS (docs.rerun.io / PyPI rerun-sdk 0.38.x) e padrão mínimo de logging de um estado MuJoCo (poses de corpos, forças de contacto como setas, séries temporais); funções de tempo atuais vs removidas; (2) `mj_contactForce` (retorna 6 valores no frame do contacto: normal, tangenciais, torsional, rolamento), `data.contact[i].frame` (3×3, 1.ª linha = normal) e como rodar para o mundo; `data.ncon`; (3) se existe exemplo oficial MuJoCo+Rerun; (4) alternativas leves (flags de visualização do viewer, matplotlib).",
    afirmacoes=[
        "O Rerun é um data logger de arquitetura colunar (column-oriented) escrito em Rust com suporte Python imediato.",
        "O script escreve coordenadas com `rr.log` a cada transição, em entidades como \"drone/aerodinamica\", usando Archetypes como `rr.Points3D` e `rr.Arrows3D`.",
        "Colisões: a matriz `data.contact` expõe `ncon`; `mujoco.mj_contactForce(model, data, index, force_array)` extrai a força de contacto que se desenha como vetor no referencial do mundo.",
        "Forças acumuladas aerodinâmicas/gravíticas estão em `data.qfrc_passive` e `data.qfrc_applied` antes de `mj_step` terminar.",
    ],
    fronteiras="cobre Rerun/telemetria/forças de contacto para visualização; NÃO cobre instalação do Rerun (apenas a API).",
    locais="docs/upstream/mujoco/doc/APIreference/functions.rst (mj_contactForce), doc/computation/index.rst, doc/programming/simulation.rst, python/mujoco/. Web: rerun.io/docs, pypi.org/project/rerun-sdk, github.com/rerun-io/rerun (exemplos).",
    esforco="8–12 consultas web (docs oficiais do Rerun e exemplos); 2–3 fontes lidas na íntegra; testes empíricos só do lado MuJoCo (mj_contactForce + frame).",
)

Q["Q14"] = dict(
    pergunta="Quais são as causas típicas de instabilidade e 'explosão' numérica no MuJoCo, como se diagnostica (avisos `mjtWarning`, `mj_checkPos/Vel/Acc`, energia, `data.timer`/profiling, `mj_printModel`) e como se escala a simulação em CPU (multithread, `mujoco.rollout`, cópias de `MjData`)?",
    porque="Experimentos robóticos quebram por instabilidade; a skill precisa de um guia de diagnóstico de primeira linha e de regras de performance.",
    criterio="Guia oficial e prático: (1) lista de avisos e o que significam; reset automático em valores inválidos; (2) regras de ouro (timestep vs solref timeconst, razões de massa, `armature`, `damping`, `frictionloss`, limites de juntas, `margin`); (3) como medir energia, contactos, tempo por componente (`data.timer`, `mj_timingStatus` ou equivalente); (4) multithread: o que é thread-safe (MjModel partilhável; MjData por thread), `mujoco.rollout`; (5) checklist de depuração passo a passo.",
    afirmacoes=[
        "Um passo de tempo demasiado elevado induz 'explosão algébrica' e a estabilidade dos integradores depende de dt.",
    ],
    fronteiras="cobre diagnóstico/estabilidade/performance CPU; NÃO cobre escolha detalhada de integrador (Q3) nem contactos (Q4).",
    locais="docs/upstream/mujoco/doc/modeling.rst (troubleshooting/tuning), doc/computation/index.rst, doc/programming/simulation.rst (warnings, timing), doc/APIreference/{APItypes,functions}.rst (mjtWarning, mj_check*, mjTimer), python/rollout.ipynb.md.",
    esforco="6–10 consultas web; leitura integral das secções; 5–8 testes empíricos (provocar instabilidade com timestep grande/solref curto e ler `data.warning`; `mjENBL_ENERGY`; timers).",
)

Q["Q15"] = dict(
    pergunta="Como se modela e se verifica fisicamente a queda de um corpo triangular de cabeça para baixo (prisma triangular equilátero, tetraedro regular, pirâmide) com malha convexa (`<mesh vertex=…>`), e que experimentos básicos de mecânica existem nos exemplos oficiais (`model/`)?",
    porque="É a demonstração inicial do laboratório; precisamos de números de referência independentes (física analítica) para validar a simulação.",
    criterio="(1) um MJCF MÍNIMO e TESTADO por si em 3.15.0 de um prisma triangular equilátero (aresta 0.4 m, comprimento 0.3 m) com o vértice/aresta para baixo e de um tetraedro regular, com massa/inércia conferidas contra os valores analíticos (compare `model.body_mass` e `model.body_inertia` com as fórmulas; indica o efeito de `inertia=\"exact\"` vs padrão); (2) simulação de queda de 1 m: tempo de impacto ≈ sqrt(2h/g) (reporta o erro), energia total decrescente, estado final em repouso (|v| < 1e-3) com altura do centro de massa igual ao inradius/altura esperada, nº de contactos, tombamento e ressalto; efeito de `timestep` e `solref` no ressalto; (3) comportamento de malhas convexas (hull automático, `maxhullvert`); (4) lista de exemplos de mecânica em `model/` e para que servem.",
    afirmacoes=[
        "A inércia pode ser inferida do volume (geoms) com a densidade padrão da água.",
    ],
    fronteiras="cobre física/modelagem do experimento do triângulo e exemplos mecânicos; NÃO cobre renderização (Q2) nem contactos em abstrato (Q4) — apenas o necessário para validar a demonstração.",
    locais="docs/upstream/mujoco/doc/XMLreference.rst (asset/mesh, geom type mesh, inertia), doc/modeling.rst (Meshes, Inertia), model/{slider_crank,tendon_arm,hammock,cards,cube,balloons}/, doc/computation/index.rst.",
    esforco="4–8 consultas web; 8–12 testes empíricos (os da secção critério); reporta números reais.",
)

Q["Q16"] = dict(
    pergunta="Como está organizada a documentação oficial 3.15 (capítulos, ficheiros, skills oficiais em `doc/skills/`) e que mudanças ou quebras entre 3.0 e 3.15 afetam código/modelos antigos?",
    porque="Constrói o `docs-index` da skill e a lista de armadilhas de migração (o agente não pode usar API antiga por memória).",
    criterio="(1) mapa completo da doc: cada capítulo/ficheiro → para que serve → quando consultar (com caminhos locais); (2) leitura INTEGRAL do `doc/changelog.rst`: tabela por versão (3.0 → 3.15) de breaking changes, remoções, depreciações e novidades relevantes (MjSpec, implicitfast, flex, sleeping islands?, dcmotor, Filament, Studio, OpenUSD, skills…), cada item com versão e citação; (3) política de versionamento (`VERSIONING.md`) e estabilidade da API Python; (4) o que existe em `doc/skills/` e como complementa a skill do utilizador.",
    afirmacoes=[
        "O repositório principal inclui o guia 'Computation' (equações) e a 'XML Reference' (dialeto MJCF) como documentação de referência.",
    ],
    fronteiras="cobre estrutura da documentação e histórico de versões; NÃO repete o conteúdo técnico dos capítulos (Q3–Q9).",
    locais="docs/upstream/INDEX.md, docs/upstream/mujoco/doc/{changelog.rst,overview.rst,index.rst,python.rst,programming/*,computation/*,skills/*}, docs/upstream/mujoco/VERSIONING.md.",
    esforco="4–6 consultas web (releases GitHub); leitura integral do changelog (210 KB: usa rg por versão e sed -n por blocos) e dos índices.",
)


def render(qid: str, d: dict) -> str:
    af = "\n".join(f"- {a}" for a in d["afirmacoes"])
    return f"""# Brief {qid}

(Lê primeiro `/home/ondokai/Projects/MuJoCo/pesquisas/briefs/_PREAMBULO.md` e segue-o à risca.)

**PERGUNTA:** {d['pergunta']}

**PORQUE IMPORTA:** {d['porque']}

**CRITÉRIO DE RESPOSTA:** {d['criterio']}

**AFIRMAÇÕES DO RELATÓRIO DO UTILIZADOR A AUDITAR (hipóteses; dá um veredito a cada uma em `auditoria_relatorio`):**
{af}

**FRONTEIRAS:** {d['fronteiras']}

**FONTES LOCAIS SUGERIDAS (começa por aqui):** {d['locais']}

**ESFORÇO:** {d['esforco']}

**Ficheiro de retorno:** `{RET}/{qid}.json` — e responde APENAS `OK {qid} <nº de fontes> <estado>`.
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for qid, d in Q.items():
        (OUT / f"{qid}.md").write_text(render(qid, d), encoding="utf-8")
    print(f"{len(Q)} briefs escritos em {OUT}")


if __name__ == "__main__":
    main()
