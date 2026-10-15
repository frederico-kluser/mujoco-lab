# Laboratório — processo, scripts, templates, regras de ouro e manutenção (MuJoCo 3.15)

> Proveniência: conteúdo da skill única do laboratório (SKILL.md do motor v2.1.0, verificado 2026-10-08…12),
> preservado em `SKILL.md.bak-*` no upgrade para o motor CoALA v3 (2026-10-12) e passado para aqui.
> O uso da MEMÓRIA (níveis `map → recall → search/symbols/get → add`) vive na `SKILL.md` gerida pelo
> instalador; este ficheiro é o conhecimento do LABORATÓRIO (MuJoCo **3.15.0**, verificado nesta máquina:
> CachyOS · KDE Wayland · RTX 4070 Laptop 8 GB · Python 3.13 em `.venv`).

## 1. O processo do laboratório (GitHub → models → lab → experimento → RL → interface → deploy)

Os detalhes finos vivem no [`README.md`](../../../README.md) do projeto e na memória CoALA (busque por
`modelos`, `lab`, `experimento`, `RL`, `padrao-simulacao-clean-site`, `deploy`); aqui fica o contrato:

1. **Escolher e obter (GitHub)** — preferir SEMPRE modelos prontos e de boa reputação (`mujoco_menagerie`,
   Playground) a construir do zero. Clone *sparse* da pasta do robô para `$TMPDIR`; o espelho `docs/upstream/`
   serve de referência mas **não traz malhas** (o sync filtra `.obj`). Cruzar com specs REAIS do fabricante
   (datasheets/docs oficiais), citando as fontes no README (conteúdo web = `untrusted`, só se cita).
2. **Vendorizar em `models/<robo>/` INTACTO** — XMLs + `assets/` + LICENSE/README/CHANGELOG. Nunca editar
   ficheiros upstream: toda a adaptação (sensores, escala de atuadores) acontece em **runtime** na camada
   `lab/<robo>.py` (MjSpec), para o modelo de origem continuar comparável com o upstream.
3. **`lab/<robo>.py` — MODOS e CONTROLES como FUNÇÕES**, sem código pronto de estabilização, controle, IK,
   marcha ou voo (e sem código dos projetos originais: firmware/SDK/ROS proibidos). Padrão:
   `carregar()` → `(model, data)` com sensores · `definir_*()` (unidades físicas, cortadas às faixas do modelo) ·
   `MODOS` (roteiros abertos `f(model, data, tau)`, sem realimentação) · `ler_*()` (leituras de sensores).
   Quem escreve algoritmos e experimentos é o dono do projeto. Sensores SÃO desejáveis (quadrúpede → IMU +
   encoders + forças dos pés; drone → IMU + posição/velocidade) e entram por MjSpec.
4. **Experimento `experiments/NN_<nome>/`** — `run.py` (demo dos modos + validação por fórmulas fechadas em
   CONDIÇÕES ISOLADAS, modelo fresco sem histórico, + exit code 0/1), `view.py` (teclado + REPL), `README.md`
   com tabelas medido × teoria e fontes, `out/` ignorado pelo git. Comece por um template testado (§4).
5. **RL (opcional)** — grupo `hover-rl` (`stable-baselines3` + `gymnasium[mujoco]`, CPU): ambiente Gymnasium do
   lab (`env.py`), treino (`train.py`), política exportada para ONNX (`deploy.py`). Referência: `experiments/09_drone_hover_rl/`.
6. **Interface padrão** — regra do dono (`padrao-simulacao-clean-site`, memória CoALA): **a janela do MuJoCo
   mostra SÓ a simulação 3D** (sem HUD/overlays, sem auto-loop) e **TODAS as métricas e controlos ficam no
   site** (um comando arranca runner + servidor + site; controlos por ficheiro JSON atómico; telemetria JSONL;
   estados honestos). O site organiza-se em **SECÇÕES escolhíveis** (Operação · Rede · Vento · Bordo · Tudo,
   atalhos 1–5, escolha no `localStorage`, blocos escondidos com `hidden` sem desmontar e uma **barra crítica
   fixa** com REINICIAR/LOOP + estado sempre visível). O front e a conexão são o bundle reutilizável
   **`assets/templates/front-conexao/`** (uma só cópia; o `lab-padrao` reutiliza-o por composição). Guia:
   `experiments/09_drone_hover_rl/INTERFACE.md`.
7. **Deploy** — política → ONNX (opset 17, entrada estática) → validação numérica contra o PyTorch sobre
   observações reais → benchmark (proxy RPi 5, `intra_op_num_threads=1`, p50/p99) → execução multi-IA (`net_probe.py`).
   Tudo CPU, sem render.
   **Todo projeto tem o Raspberry Pi 5 como computador de bordo**: o painel RPi 5 no site é PADRÃO (specs do
   alvo + inferência medida + uso ao vivo, com semáforo OK/ATENÇÃO contra o orçamento de 50 Hz = 20 ms), a
   latência valida-se com `deploy.py` e o relatório alimenta esse painel. O gargalo a 50 Hz é o **jitter do
   SO** (kernel normal ≈ 9,4 ms de pior caso; PREEMPT_RT ≤ 225 µs), **não** a inferência (MLP ≈ µs). Specs,
   orçamento, int8/SDOT, multi-IA e atribuição da imagem: `assets/templates/lab-padrao/LEIAME.md` §3
   («Computador de bordo: Raspberry Pi 5»).
8. **Registar o que foi feito** (nada fica "na cabeça"): README do experimento com as tabelas de valores medidos
   vs teoria e as fontes; `$COALA add` do durável; atualizar o catálogo de projetos adaptados no `AGENTS.md`.

**Simulador SEMPRE físico** (regra do dono, 2026-10-08): tudo passa por `mj_step` — gravidade, arrasto,
contactos, atuadores e sensores a cada passo. Nada de cinemática, teleporte (só `reset` explícito do
simulador), corpos congelados ou "apoios mágicos": os robôs só se mexem por comandos de atuador e a física
decide o resto. Os programas ARRANCAM nesse estado (drone: motores desligados, assenta no chão pela física;
Spot: servos na postura home, de pé pelos próprios motores). Só abra **janela** (viewer) quando o dono pedir —
ela aparece na tela dele; para agentes, render offscreen.

## 2. Mapa de referências (carregue só o que o tema pedir)

| Tema | Arquivo | Quando |
| --- | --- | --- |
| Instalação (uv/wheel/AUR/CMake), variáveis de ambiente, C/C++ | `references/install-linux.md` | instalar, atualizar, erro de import/linkagem |
| Render offscreen, vídeo, viewer, Wayland/NVIDIA, Studio | `references/rendering-viewer.md` | gerar imagens/vídeo, abrir janela, erro de GL |
| MJCF: elementos, inércia/massa, malhas, defaults, include/attach, removidos 3.0→3.15 | `references/mjcf-cheatsheet.md` | escrever/editar modelos XML |
| API Python: MjSpec, acesso por nome, simulação, derivadas, rollout, callbacks | `references/python-api.md` | escrever código Python com MuJoCo |
| Física: integradores, solvers, contato, atrito, estabilidade, desempenho CPU | `references/physics-tuning.md` | peça não repousa/trepida/explode, escolher integrador |
| Atuadores, sensores, tendões, equality, mocap, keyframes | `references/actuators-sensors.md` | controlar juntas, ler sensores |
| Robôs: Menagerie, URDF/malhas, PD/gravidade/IK, ecossistema (RL/MPC) | `references/robots.md` | braços, pernas, importar robô |
| Drones: fluido/vento, quadricóptero, controle, limites | `references/drones.md` | drone/hélice/aerodinâmica |
| Veículos: rodas, atrito, direção, suspensão, limites do pneu | `references/vehicles.md` | carros/robôs de rodas |
| GPU: MJX (JAX) e MuJoCo Warp; medições nesta RTX 4070 | `references/gpu-mjx-warp.md`, `references/gpu-benchmarks.md` | RL em larga escala, muitos mundos |
| Telemetria: Rerun, forças de contato, gráficos | `references/telemetry-rerun.md` | visualizar/registar dados |
| Experimentos: método de validação + catálogo com valores analíticos | `references/experiments-playbook.md` | planejar um experimento novo |
| Mapa da documentação oficial, mudanças/quebras 3.0→3.15, inconsistências da doc | `references/docs-map.md` | achar algo na doc, código antigo quebrou |
| Errata das skills oficiais da DeepMind (snippets que falham) | `references/official-skills-errata.md` | antes de copiar qualquer trecho de `doc/skills/*` |
| Auditoria do relatório técnico do dono (correto/parcial/incorreto) | `references/relatorio-auditoria.md` | citar ou reutilizar o relatório original |
| Processo do lab, scripts, templates, regras de ouro, fatos da máquina (este ficheiro) | `references/laboratorio.md` | fluxo de trabalho do laboratório |
| Esquema da memória CoALA (DDL canónico, índice BM25F, regras de origem) | `references/schema.md` | entender/estender a memória (gerido pelo instalador) |

## 3. Scripts (`scripts/`, rodar com `.venv/bin/python` — ou `python3` para o motor)

| Script | Para quê |
| --- | --- |
| `coala.py` | **o motor da memória** (Python 3 stdlib): níveis `map/recall/search/symbols/refs/get`, `add`, `supersede`, `sync`, `doctor`, `where`, `stats`, `backup`/`restore` (comandos completos: `$COALA --help`) |
| `env_check.py` | diagnóstico do ambiente: Python/pacotes, EGL/OSMesa/GLFW, GPU, sessão gráfica, espelho de docs (`--gl all`, `--gpu`, `--json`) |
| `docs_search.py` | busca BM25 na doc oficial local + atributo MJCF, elemento, função C, tipo/enum, changelog |
| `inspect_model.py` | compila e relata modelo (MJCF/URDF/mjb): contagens, massa, árvore, atuadores, sensores, riscos, teste de fumaça |
| `render_video.py` | MP4/GIF/tira de quadros de qualquer modelo, sem janela (`--ctrl`, `--keyframe`, `--track`, `--contacts`) |
| `view_model.py` | abre qualquer modelo no viewer (UI completa ou `--passivo`); só a pedido do dono |
| `new_experiment.py` | cria `experiments/NN_nome/` a partir de template e liga `lab/mjkit.py` |
| `mjkit.py` | biblioteca do lab: `load`, `Ctrl` (controle seguro por nome), `record(consistent=…)`, `plot`, `contact_sheet`, `run_viewer` |
| `sync_docs.py` | (re)espelha a documentação oficial (tag = mujoco instalado) em `docs/upstream/` |
| `gpu_bench.py` | benchmark MJX/Warp/CPU (precisa de `.venv-gpu`; ver `references/gpu-benchmarks.md`) |

Protocolo de trabalho com modelos: **consultar a doc antes de afirmar** (`docs_search.py`) → **partir de um
template testado** (`new_experiment.py`) → **validar o modelo** (`inspect_model.py --tree`, comparando massa,
inércia, tempo de queda livre e altura de repouso com fórmulas fechadas) → **simular sem janela** com critérios
de aceitação e exit code → **depurar** com `references/physics-tuning.md` (instabilidade quase sempre é
`timestep`/`solref`/massa/penetração inicial) → **registar** na memória.

## 4. Templates testados (`assets/templates/`, cada um com `model.xml`, `run.py`, `README.md`; `run.py` valida e sai com 0/1)

| Template | O que faz / valida |
| --- | --- |
| `blank` | chão + caixa; esqueleto com controlador, métricas, vídeo e checagens |
| `pendulum` | período exato (integral elíptica) × Euler/RK4/implicit/implicitfast; deriva de energia |
| `arm` | braço 3 GDL: servos `position`, IK diferencial por Jacobiano, alvo mocap; RMS ≈ 4 mm |
| `quadrotor` | quadricóptero: alocação construída do modelo, controlador geométrico SO(3), waypoints, vento (`--ar --vento`); erro nos waypoints ≤ 4 cm |
| `car` | carro 4 rodas, Ackermann, tração traseira; guinada vs modelo cinemático de bicicleta (Δ ≈ 6%), `--atrito` mostra o subesterço |
| **`front-conexao`** | o BUNDLE portátil **front + códigos de conexão** para colar em QUALQUER projeto: `site/` (React com o padrão `padrao-simulacao-clean-site` — **5 SECÇÕES** Operação·Rede·Vento·Bordo·Tudo com atalhos 1–5, persistência no `localStorage` e barra crítica fixa, vento dinâmico ao vivo, rosa dos ventos, painel do **Raspberry Pi 5**, ajuda «?»), `sim_view.py` + `sim_site.py` (runner + servidor de **6 rotas**, com `--env-modulo` e import tardio do env do projeto) e `CONTRATOS.md` (controlo atómico, telemetria 15+2, API, sem auto-loop). `new_experiment.py <nome> --template front-conexao`. Guia: `assets/templates/front-conexao/LEIAME.md` |
| **`lab-padrao`** | o PADRÃO do lab pronto a copiar: `new_experiment.py <nome> --template lab-padrao` cria o experimento completo — `env.py` (obs normalizada + ação centrada no trim + recompensa + vento base e **dinâmico**: rajadas/frente/dryden), `run.py` (7 fórmulas fechadas, 0/1), `view.py`, `train.py`, `dashboard.py`, `net_probe.py`, `deploy.py`; o **front e a conexão vêm do bundle `front-conexao`** (o script compõe as duas árvores — uma só cópia do front) e o exemplo traz o overlay `site/src/lib/config.ts` + `LEIAME.md`/`INTERFACE.md`. Guia: `assets/templates/lab-padrao/LEIAME.md` |

Experimentos prontos: `experiments/09_drone_hover_rl` (RL + interface + deploy; `run.py` = 242 checagens — 146 do cf2 +
96 da PLANTA REAL do drone do dono, exit 0). O drone do dono com PEÇAS REAIS trocáveis vive em `lab/drone_rpi/` +
`models/drone_rpi/componentes.json`/`builds.json` (trocar com `experiments/09_drone_hover_rl/hardware.py`; estado em
`plano-drone-real.md` §0).
Os experimentos `01_triangulo_invertido` … `08_crazyflie_motores` foram **removidos em 2026-10-08** por decisão
do dono (por enquanto fica só o drone) — histórico no git; `models/`, `lab/` e templates mantêm-se.
Testes desta skill: `uv run pytest .agents/mujoco-lab-coala-agent-skill/tests -q`.

## 5. Regras de ouro do MuJoCo 3.15 (cada uma já mordeu alguém — verificadas em 3.15.0)

(As regras da memória CoALA — proveniência, supersessão, recall orçamentado, sem segredos, chaves estáveis —
estão na `SKILL.md` gerida.)

1. **API mudou**: `mjData.qM` foi removido (`data.M`, CSR) · `mj_fullM(m, d, dst)` · `spec.delete(elemento)`
   (não existe `delete_body`) · `spec.strippath` · C: `mjs_addBody` (não `mj_addBody`) · dict `assets=` →
   `mujoco.MjVfs`. Em dúvida: `docs_search.py --changelog <símbolo>`.
2. **Atuadores multi-entrada** (`pid`, `dcmotor`, `orientation`): há 3 espaços de índice — atuador, controle
   (`actuator_ctrladr[i] : +ctrlnum`) e saída (`actuator_outadr[i] : +outnum`: `actuator_force/length/gear…`).
   Os acessores nomeados (`data.actuator('x').ctrl/.force`, `model.actuator('x').ctrlrange/.gear`) usam o ID e
   **erram**. Use `lab.mjkit.Ctrl` (vetor do tamanho `ctrlnum`) ou os índices acima.
3. **Massa dobrada**: geoms visual+collision no mesmo corpo somam massa (`compiler inertiagrouprange` padrão
   `0 5`) → `mass="0"`/`density="0"` nos visuais, `inertiagrouprange="3 3"` ou `<inertial>`.
4. **Malhas**: o geom precisa de `type="mesh"` (senão vira esfera, sem erro); colisão usa o **casco convexo**
   (côncavo → vários geoms convexos); `<mesh vertex=…>` já gera o casco; a malha é recentrada no CM.
5. **MJCF silencioso**: `euler/axisangle/xyaxes/zaxis` herdado de `<default>` VENCE um `quat` explícito;
   `eulerseq` minúsculo = intrínseco (inverso do SciPy); `autolimits` com range invertido desliga o limite sem
   erro; `ctrlrange`/`actrange` NÃO são convertidos de graus (use `inheritrange="1"` ou rad); quaternion
   `[w x y z]`; XML em graus, runtime em radianos.
   ⚠ `mujoco.MjSpec()` nasce com `spec.compiler.degree = True`: `range=[-1.57, 1.57]` vira ±0,027 rad (junta
   quase travada) e `axisangle` gira em graus — defina `spec.compiler.degree = False` ao editar em radianos.
6. **`<visual>` repetido é mesclado** por atributo (sem "reset"); sub-elemento único por bloco; resolução
   offscreen ≤ `<visual><global offwidth offheight>`.
7. **Views e atraso de 1 passo**: `data.qpos`, `data.body('x').xpos`… são views (→ `.copy()` ao guardar). Após
   `mj_step`, os campos derivados (`xpos/xipos/xmat`, `sensordata`, contatos, `data.energy`) são do estado
   ANTERIOR à integração: `mj_forward` antes de ler (ou `mjkit.record(consistent=True)`). `Renderer.render()`
   devolve array novo (só `out=` reutiliza). `qpos[2]` é a origem do corpo (CM = `data.xipos`).
8. **Contato**: `solref=(timeconst, dampratio)` com `timeconst ≥ 2·timestep` (`refsafe`); `dampratio < 1`
   quica e muito baixo não repousa (limiar depende da geometria); `margin`/`gap` mudaram na 3.9; mistura entre
   geoms: friction = máx, solref/solimp = média por `solmix`; `noslip` só ajuda com cone elíptico.
   ⚠ O `dampratio` do ATUADOR `position` é outro (redefinido na 3.15: inércia refletida).
9. **Integradores**: padrão = Euler; **recomendado = `implicitfast`** (fixe no XML); RK4 só para sistemas suaves
   SEM contato; `discrete` (3.13) é o único estável com rigidez de posição alta; `kv` de atuador com Euler
   diverge; `data.energy` ignora a energia elástica do contato.
10. **Jacobianos**: `mj_jacSite`/`mj_jac*` exigem `mj_kinematics` + `mj_comPos` (ou `mj_forward`) antes.
    `mjd_transitionFD(flg_centered=True)` devolve D com **sinal trocado** (use `False`).
11. **Render/viewer**: `MUJOCO_GL=egl` **antes** de `import mujoco` (usa a NVIDIA); **nunca `osmesa`** (quebra o
    `import`); viewer = GLFW em Wayland nativo (`PYGLFW_LIBRARY_VARIANT=x11` força XWayland); o Studio não roda
    em Wayland.
12. **GPU**: MJX-JAX aceita e IGNORA em silêncio `noslip`, `fluidshape="ellipsoid"` e plugins; `pid`/`orientation`
    não existem em MJX/MJWarp; float32; os 2,96 M/2,33 M SPS oficiais são ambos MJX-Warp (Humanoid/Aloha Pot) —
    ver `references/gpu-mjx-warp.md`.
13. **Skills oficiais da DeepMind** (`docs/upstream/mujoco/doc/skills/*`) têm snippets que falham e afirmações
    falsas: consulte `references/official-skills-errata.md` antes de seguir qualquer trecho.
14. **Higiene**: temporários em `$TMPDIR` (nunca o diretório temporário global); rode scripts com `cwd` fora da
    raiz se possível (o MuJoCo grava `MUJOCO_LOG.TXT` no cwd, que está no `.gitignore`); nunca versionar
    `memory/coala.sqlite`, `.venv/`, `docs/upstream/` nem `experiments/*/out/`; **não commitar sem pedido**.
15. **Validar fisicamente**: todo experimento compara ≥ 3 grandezas com fórmulas fechadas e devolve exit code;
    fatos datados (estado de pacotes AUR/PyPI = 2026-10-07) envelhecem em dias — reverifique antes de afirmar.

## 6. Fatos desta máquina

- `uv` + Python 3.13 em `.venv` (mujoco 3.15.0, numpy 2.5, scipy, matplotlib, imageio-ffmpeg); o sistema tem
  Python 3.14.7 *externally-managed* → sempre venv. Grupos opcionais no `pyproject.toml`: `viz`, `urdf`, `rl`,
  `dmc`, `hover-rl`, `gpu` (venv separado `.venv-gpu`). Rodar: `uv run python <script>` ou `.venv/bin/python <script>`.
- GPU: RTX 4070 Laptop 8 GB (driver 610.57) + iGPU Intel; EGL offscreen usa a NVIDIA (device 0 aqui: confira com
  `GL_RENDERER`). Sessão KDE **Wayland**; `DISPLAY=:0` existe, mas o GLFW usa o backend Wayland.
  MJX/MuJoCo Warp rodam no venv separado `.venv-gpu` (`jax[cuda12]` + `warp-lang` 1.18): humanoide a 4096 mundos
  ≈ 1,9 M SPS (MJWarp) / 1,8 M (MJX-Warp) / 27–87 K (MJX-JAX) vs ≈ 0,25 M da CPU de 32 threads — receita e
  tabelas em `references/gpu-benchmarks.md`.
- Avisos benignos no KDE Wayland: `Failed to load plugin 'libdecor-gtk.so'` e
  `OpenGL error 0x502 in or before mjr_makeContext` (o viewer funciona).
- Documentação 3.15.0 espelhada em `docs/upstream/` (mujoco, mujoco_warp, mujoco_playground, mujoco_mpc,
  mujoco_menagerie); índice em `docs/upstream/INDEX.md`; `scripts/sync_docs.py` atualiza.
- Relatório técnico original do dono: `docs/relatorio-tecnico-original.md` (material do dono — não editar;
  auditado em `references/relatorio-auditoria.md`; dossiê completo e verificação independente em `pesquisas/`).
- Convenções: unidades SI; **+Z para cima**; quaternions `[w x y z]` (SciPy/ROS usam `[x y z w]`); ângulos em
  **graus** no XML (`compiler angle="degree"`); acesso por NOME (`data.body('x').xpos`, `model.geom('g')`),
  nunca índices crus; integrador padrão 3.15 = Euler (novo: `discrete`); experimentos em `experiments/NN_nome/`.

## 6b. Regras de processo aprendidas a medir (2026-10-12/13)

- **Decidir por medição e tornar padrão** — o dono não quer escolher entre algoritmos na interface («não quero
  opções, quero o melhor»): mede-se no simulador com as mesmas sementes, o que ganha passa a ser o padrão
  (`sim_site.py --controlador auto`) e a escolha não aparece como botão.
- **Sementes de avaliação ≠ sementes de afinação**, e o resultado de um agente repete-se em sementes que ele não
  usou antes de ser aceite (foi assim que se confirmou o vento, a bola e a vertical, e se apanhou uma estimativa
  errada).
- **Critérios fixos ANTES de medir**; se um candidato falha por pouco e ainda assim se quer adotar, faz-se uma
  SEGUNDA medição independente (outras sementes, com randomização de domínio, margens de estabilidade) com
  critérios também fixos antes — e diz-se ao dono que foi contra o critério inicial e como se reverte.
- **Desempenho só com a máquina livre** — avaliações em paralelo (EGL e CPU) falseiam fps, tempo real e débito
  de treino: com carga 30 o simulador correu a 0,38× e os streams a 18 fps; livre, 0,999× e 49,7 fps. Uma
  estimativa de escala feita sob carga («16 ambientes dão +12 %») estava errada (medido livre: +48 %).
- **Nenhum teste toca em estado persistente do dono** — o pack de bateria do drone (`out/bateria/`) só se usa
  na sessão real; suítes e instâncias de desenvolvimento definem `DRONE_PASTA_BATERIA` para uma pasta temporária
  ANTES de importar o runner. Os worktrees de subagentes partilham o `out/` real por symlink.
- **Um teste de servidor confirma que o runner continua vivo** (amostras a chegar), não só que arrancou: um
  runner morto atrás de um site de pé passou despercebido até a prova o exigir.
- **Interface do drone = cockpit** (contrato r13): um ecrã sem scroll, a vista em 1.ª/3.ª pessoa sempre visível,
  HUD por cima, controlos em janelas que se abrem, controlo já ativo, vocabulário de voo (a voar / no chão /
  caiu). A janela nativa do MuJoCo deixou de abrir por omissão (`--com-janela`).
- **Commits**: ramo efémero → PR (o `CONTRIBUTING.md`); `git add` por ficheiro; `.claude/` não se versiona.
- **Shell**: `pkill -f padrão` mata o próprio shell se o padrão aparecer na linha de comandos — usar `'[x]padrão'`.

## 7. Manutenção

- **Ficheiros geridos pelo instalador** (`coala-install`): `SKILL.md`, `scripts/coala.py`,
  `references/schema.md` e `memory/.gitignore`. Os restantes (`references/` do MuJoCo, `scripts/` do MuJoCo,
  `assets/`, `tests/`, `ingest.json`, `coala.json`, este ficheiro) são do projeto e **nunca são tocados**.
  - `install` **preserva** um ficheiro gerido personalizado (compara sha256; relata
    `conflito (personalizado, preservado)`). **`--force` substitui-o** pelo template — não use.
  - `upgrade` (v2 → v3…) **substitui** os geridos, deixando o personalizado em `SKILL.md.bak-<data>` — é
    assim que este `laboratorio.md` nasceu (2026-10-12); depois de um upgrade, rever o `.bak`.
  - Comandos: `python3 ~/Agent-Skills/coala-agent-skill/scripts/coala-install.py install|upgrade --project <raiz>` ·
    diagnóstico: `... doctor --project <raiz>` (aí `SKILL.md personalizado` = WARN esperado, não é falha).
- **Nova versão do MuJoCo**: `uv sync` → `scripts/sync_docs.py` → `docs_search.py --changelog "Breaking API changes"`
  (lista as versões com quebras) → rodar os `run.py` dos templates e a suíte `pytest` → atualizar as referências
  afetadas → `$COALA sync` + `$COALA doctor` e registar a mudança na memória.
- **Política git**: `ignore` para a base (nunca versionada). Ficam versionados `references/` e `scripts/` do
  MuJoCo, `assets/`, `tests/`, `ingest.json` e `coala.json`; ficam FORA do git (cópia vendorizada da memória,
  não publicada) `SKILL.md`, `scripts/coala.py` e `references/schema.md` — ver `.gitignore`.
  Sem a memória nada quebra: o conhecimento verificado é o que está versionado nesta pasta e em `pesquisas/`.
- **Promover esta skill a global** (todas as sessões): copiar a pasta para `~/Agent-Skills/mujoco-lab-coala-agent-skill/`
  e adaptar o `scripts/link-skill-global.sh` de uma skill existente — **pedir ao dono antes** (hoje é só deste projeto).
