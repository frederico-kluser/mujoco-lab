---
name: mujoco-agent-skill
description: >-
  Controla TODO o MuJoCo 3.15 (Google DeepMind) neste laboratório — instalar e diagnosticar o ambiente, modelar em MJCF e MjSpec, simular (mj_step, integradores, contato),
  renderizar vídeo/GIF sem janela (EGL) ou abrir o viewer, depurar instabilidade, importar URDF/malhas, escalar em GPU (MJX / MuJoCo Warp), telemetria com Rerun e construir
  experimentos físicos/mecânicos, robôs (braços), drones (quadricópteros) e veículos — com a documentação oficial offline, scripts e templates testados. Use SEMPRE que o pedido
  mencionar MuJoCo, MJCF, mjx, mj_step, MjModel/MjData/MjSpec, simulação de corpos rígidos, solref/solimp, quadricóptero/drone, robô/braço, veículo/carro, URDF, Menagerie,
  Playground ou "criar um experimento/simulação" neste projeto.
---

# mujoco-agent-skill — controle total do MuJoCo 3.15 neste laboratório

Skill de **controle e conhecimento verificado** (MuJoCo **3.15.0**, verificado em 2026-10-07 nesta máquina: CachyOS · KDE Wayland · RTX 4070 Laptop 8 GB · Python 3.13 em `.venv`).
Tudo aqui foi **executado e conferido** — não confie na memória de treino sobre a API: o MuJoCo muda a cada 2–5 semanas e cada `3.N.0` pode quebrar código (ver `references/docs-map.md` §3).
A memória do projeto (decisões, resultados, o que já foi testado) está na skill **`mujoco-lab-agent-skill`** (CoALA); este arquivo cobre o *como controlar o MuJoCo*.

## Protocolo (siga em ordem)

0. **Orientar-se**: `python3 .agents/mujoco-lab-agent-skill/scripts/coala.py recall "<tarefa>" --budget 1500` (o que já se sabe/decidiu) e, se for a 1ª sessão ou algo falhar,
   `.venv/bin/python .agents/mujoco-agent-skill/scripts/env_check.py` (Python, pacotes, EGL, GPU, docs).
1. **Consultar a documentação oficial local ANTES de afirmar** nome de API/atributo/valor padrão (espelho 3.15.0 em `docs/upstream/`):
   `python3 .agents/mujoco-agent-skill/scripts/docs_search.py "termos" | --attr geom.friction | --elem actuator/position | --api mj_step | --type mjtIntegrator | --changelog "Breaking API changes"`.
2. **Modelar/estender a partir de um template testado**: `python3 .agents/mujoco-agent-skill/scripts/new_experiment.py <nome> --template blank|pendulum|arm|quadrotor|car` → `experiments/NN_nome/`.
3. **Validar o modelo** antes de simular a sério: `.venv/bin/python .agents/mujoco-agent-skill/scripts/inspect_model.py <modelo.xml> --tree` (contagens, massa, atuadores, sensores, riscos, teste de fumaça) e
   compare **massa, inércia, tempo de queda livre e altura de repouso** com fórmulas fechadas (como em `experiments/01_triangulo_invertido/`).
4. **Simular sem janela** (`lab.mjkit`: `load`, `Ctrl`, `record`, `plot`, `run_viewer`) com critérios de aceitação e *exit code* 0/1; gerar vídeo/GIF/gráficos em `out/`.
5. **Depurar** com `references/physics-tuning.md` (sintoma → causa → correção) e `inspect_model.py`; instabilidade quase sempre é `timestep`/`solref`/massa/penetração inicial.
6. **Registrar** o que for durável: `coala.py add --type episodic|semantic|procedural --content "…" --key "experimento/NN_nome"`; resultados e parâmetros no `README.md` do experimento.

Só abra **janela** (viewer) quando o usuário pedir — ela aparece na tela dele; para agentes use render offscreen.

## Mapa de referências (carregue só o que o tema pedir)

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
| Telemetria: Rerun, forças de contato, gráficos | `references/telemetry-rerun.md` | visualizar/registrar dados |
| Experimentos: método de validação + catálogo com valores analíticos | `references/experiments-playbook.md` | planejar um experimento novo |
| Mapa da documentação oficial, mudanças/quebras 3.0→3.15, inconsistências da doc | `references/docs-map.md` | achar algo na doc, código antigo quebrou |
| Errata das skills oficiais da DeepMind (snippets que falham) | `references/official-skills-errata.md` | antes de copiar qualquer trecho de `doc/skills/*` |
| Auditoria do relatório técnico do usuário (correto/parcial/incorreto) | `references/relatorio-auditoria.md` | citar ou reutilizar o relatório original |

## Scripts (`.agents/mujoco-agent-skill/scripts/`, rodar com `.venv/bin/python`)

| Script | Para quê |
| --- | --- |
| `env_check.py` | diagnóstico do ambiente: Python/pacotes, EGL/OSMesa/GLFW, GPU, sessão gráfica, espelho de docs (`--gl all`, `--gpu`, `--json`) |
| `docs_search.py` | busca BM25 na doc oficial local + atributo MJCF, elemento, função C, tipo/enum, changelog |
| `inspect_model.py` | compila e relata modelo (MJCF/URDF/mjb): contagens, massa, árvore, atuadores, sensores, riscos, teste de fumaça |
| `render_video.py` | MP4/GIF/tira de quadros de qualquer modelo, sem janela (`--ctrl`, `--keyframe`, `--track`, `--contacts`) |
| `view_model.py` | abre qualquer modelo no viewer (UI completa ou `--passivo`); só a pedido do usuário |
| `new_experiment.py` | cria `experiments/NN_nome/` a partir de template e liga `lab/mjkit.py` |
| `mjkit.py` | biblioteca: `load`, `Ctrl` (controle seguro por nome), `record(consistent=…)`, `plot`, `contact_sheet`, `run_viewer` |
| `sync_docs.py` | (re)espelha a documentação oficial (tag = mujoco instalado) em `docs/upstream/` |
| `gpu_bench.py` | benchmark MJX/Warp/CPU (precisa de `.venv-gpu`; ver `gpu-benchmarks.md`) |

## Templates testados (`assets/templates/`, cada um com `model.xml`, `run.py`, `README.md`; `run.py` valida e sai com 0/1)

| Template | O que faz / valida |
| --- | --- |
| `blank` | chão + caixa; esqueleto com controlador, métricas, vídeo e checagens |
| `pendulum` | período exato (integral elíptica) × Euler/RK4/implicit/implicitfast; deriva de energia |
| `arm` | braço 3 GDL: servos `position`, IK diferencial por Jacobiano, alvo mocap; RMS ≈ 4 mm |
| `quadrotor` | quadricóptero: alocação construída do modelo, controlador geométrico SO(3), waypoints, vento (`--ar --vento`); erro nos waypoints ≤ 4 cm |
| `car` | carro 4 rodas, Ackermann, tração traseira; guinada vs modelo cinemático de bicicleta (Δ ≈ 6%), `--atrito` mostra o subesterço |

Experimentos prontos: `experiments/01_triangulo_invertido` (demo: queda de prisma/tetraedro triangular, validada), `experiments/02_pendulo`. Testes da skill: `uv run pytest .agents/mujoco-agent-skill/tests -q`.

## Regras de ouro (cada uma já mordeu alguém — verificadas em 3.15.0)

1. **API mudou**: `mjData.qM` foi removido (`data.M`, CSR) · `mj_fullM(m, d, dst)` · `spec.delete(elemento)` (não existe `delete_body`) · `spec.strippath` · C: `mjs_addBody` (não `mj_addBody`) · dict `assets=` → `mujoco.MjVfs`. Em dúvida: `docs_search.py --changelog <símbolo>`.
2. **Atuadores multi-entrada** (`pid`, `dcmotor`, `orientation`): há 3 espaços de índice — atuador, controle (`actuator_ctrladr[i] : +ctrlnum`) e saída (`actuator_outadr[i] : +outnum`: `actuator_force/length/gear…`).
   Os acessores nomeados (`data.actuator('x').ctrl/.force`, `model.actuator('x').ctrlrange/.gear`) usam o ID e **erram**. Use `lab.mjkit.Ctrl` (vetor do tamanho `ctrlnum`) ou os índices acima.
3. **Massa dobrada**: geoms visual+collision no mesmo corpo somam massa (`compiler inertiagrouprange` padrão `0 5`) → `mass="0"`/`density="0"` nos visuais, `inertiagrouprange="3 3"` ou `<inertial>`.
4. **Malhas**: o geom precisa de `type="mesh"` (senão vira esfera, sem erro); colisão usa o **casco convexo** (côncavo → vários geoms convexos); `<mesh vertex=…>` já gera o casco; a malha é recentrada no CM.
5. **MJCF silencioso**: `euler/axisangle/xyaxes/zaxis` herdado de `<default>` VENCE um `quat` explícito; `eulerseq` minúsculo = intrínseco (inverso do SciPy); `autolimits` com range invertido desliga o limite sem erro;
   `ctrlrange`/`actrange` NÃO são convertidos de graus (use `inheritrange="1"` ou rad); quaternion `[w x y z]`; XML em graus, runtime em radianos.
   ⚠ `mujoco.MjSpec()` nasce com `spec.compiler.degree = True`: `range=[-1.57, 1.57]` vira ±0,027 rad (junta quase travada) e `axisangle` gira em graus — defina `spec.compiler.degree = False` ao editar em radianos.
6. **`<visual>` repetido é mesclado** por atributo (sem "reset"); sub-elemento único por bloco; resolução offscreen ≤ `<visual><global offwidth offheight>`.
7. **Views e atraso de 1 passo**: `data.qpos`, `data.body('x').xpos`… são views (→ `.copy()` ao guardar). Após `mj_step`, os campos derivados (`xpos/xipos/xmat`, `sensordata`, contatos, `data.energy`) são do estado ANTERIOR à integração:
   `mj_forward` antes de ler (ou `mjkit.record(consistent=True)`). `Renderer.render()` devolve array novo (só `out=` reutiliza). `qpos[2]` é a origem do corpo (CM = `data.xipos`).
8. **Contato**: `solref=(timeconst, dampratio)` com `timeconst ≥ 2·timestep` (`refsafe`); `dampratio < 1` quica e muito baixo não repousa (limiar depende da geometria); `margin`/`gap` mudaram na 3.9; mistura entre geoms:
   friction = máx, solref/solimp = média por `solmix`; `noslip` só ajuda com cone elíptico. ⚠ O `dampratio` do ATUADOR `position` é outro (redefinido na 3.15: inércia refletida).
9. **Integradores**: padrão = Euler; **recomendado = `implicitfast`** (fixe no XML); RK4 só para sistemas suaves SEM contato; `discrete` (3.13) é o único estável com rigidez de posição alta; `kv` de atuador com Euler diverge; `data.energy` ignora a energia elástica do contato.
10. **Jacobianos**: `mj_jacSite`/`mj_jac*` exigem `mj_kinematics` + `mj_comPos` (ou `mj_forward`) antes. `mjd_transitionFD(flg_centered=True)` devolve D com **sinal trocado** (use `False`).
11. **Render/viewer**: `MUJOCO_GL=egl` **antes** de `import mujoco` (usa a NVIDIA); **nunca `osmesa`** (quebra o `import`); viewer = GLFW em Wayland nativo (`PYGLFW_LIBRARY_VARIANT=x11` força XWayland); o Studio não roda em Wayland.
12. **GPU**: MJX-JAX aceita e IGNORA em silêncio `noslip`, `fluidshape="ellipsoid"` e plugins; `pid`/`orientation` não existem em MJX/MJWarp; float32; os 2,96 M/2,33 M SPS oficiais são ambos MJX-Warp (Humanoid/Aloha Pot) — ver `gpu-mjx-warp.md`.
13. **Skills oficiais da DeepMind** (`docs/upstream/mujoco/doc/skills/*`) têm snippets que falham e afirmações falsas: consulte `official-skills-errata.md` antes de seguir qualquer trecho.
14. **Higiene**: temporários em `$TMPDIR` (nunca o diretório temporário global); o MuJoCo grava `MUJOCO_LOG.TXT` no cwd (está no `.gitignore`); não commitar sem pedido.
15. **Validar fisicamente**: todo experimento compara ≥ 3 grandezas com fórmulas fechadas e devolve exit code; fatos datados (estado de pacotes AUR/PyPI = 2026-10-07) envelhecem em dias — reverifique antes de afirmar.

## Fatos desta máquina

- `uv` + Python 3.13 em `.venv` (mujoco 3.15.0, numpy 2.5, scipy, matplotlib, imageio-ffmpeg); o sistema tem Python 3.14.7 *externally-managed* → sempre venv. Grupos opcionais no `pyproject.toml`: `viz`, `urdf`, `rl`, `gpu` (venv separado `.venv-gpu`).
- GPU: RTX 4070 Laptop 8 GB (driver 610.57) + iGPU Intel; EGL offscreen usa a NVIDIA (device 0 aqui: confira com `GL_RENDERER`). Sessão KDE **Wayland**; `DISPLAY=:0` existe, mas o GLFW usa o backend Wayland.
  MJX/MuJoCo Warp rodam no venv separado `.venv-gpu` (`jax[cuda12]` + `warp-lang` 1.18): humanoide a 4096 mundos ≈ 1,9 M SPS (MJWarp) / 1,8 M (MJX-Warp) / 27–87 K (MJX-JAX) vs ≈ 0,25 M da CPU de 32 threads — receita e tabelas em `references/gpu-benchmarks.md`.
- Avisos benignos ao abrir o viewer: `libdecor-gtk.so` e `OpenGL error 0x502 in or before mjr_makeContext`.
- Documentação 3.15.0 espelhada em `docs/upstream/` (mujoco, mujoco_warp, mujoco_playground, mujoco_mpc, mujoco_menagerie); `sync_docs.py` atualiza.
- Relatório técnico original do usuário: `docs/relatorio-tecnico-original.md` (auditado em `references/relatorio-auditoria.md`; dossiê completo e verificação independente em `pesquisas/`).

## Manutenção

- Nova versão do MuJoCo: `uv sync` → `sync_docs.py` → `docs_search.py --changelog "Breaking API changes"` (lista as versões com quebras) → rodar os `run.py` dos templates e a suíte `pytest` → atualizar as referências afetadas.
- Para promover esta skill a global (todas as sessões): copiar a pasta para `~/Agent-Skills/mujoco-agent-skill/` e adaptar o `scripts/link-skill-global.sh` de uma skill existente (ex.: `~/Agent-Skills/coala-agent-skill/`), que cria os symlinks nos skill roots da máquina — **pedir ao usuário antes** (hoje a skill é só deste projeto).
