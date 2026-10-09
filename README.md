<div align="center">

# MuJoCo Lab

**Laboratório de simulação física com o MuJoCo 3.15: experimentos validados contra a física analítica, robôs, drones e veículos — e uma agent skill que dá a qualquer agente de IA controle total da ferramenta, com a documentação oficial offline.**

![MuJoCo](https://img.shields.io/badge/MuJoCo-3.15.0-orange)
![Python](https://img.shields.io/badge/Python-3.13-blue)
![uv](https://img.shields.io/badge/gerenciado%20por-uv-7c3aed)
![Testes](https://img.shields.io/badge/testes-29%20passando-brightgreen)
![Plataforma](https://img.shields.io/badge/Linux-Wayland%20·%20EGL%20·%20RTX%204070-lightgrey)

<img src="docs/media/exp01_queda.gif" width="760" alt="Prisma triangular de cabeça para baixo caindo, quicando e tombando até repousar com 4 contatos">

*Demo: um prisma triangular de cabeça para baixo cai, quica, tomba e repousa. O `run.py` confere massa, instante do impacto, energia e altura de repouso contra fórmulas fechadas.*

</div>

> **TL;DR (English):** a MuJoCo 3.15 lab where every experiment is checked against analytic physics and exits `0/1`; a ready-to-load **agent skill** (16 verified references, tested templates for an arm, a quadrotor and a car, offline docs search); an audited deep-research dossier (337 searches, 99 claims of a technical report checked, 38 independent re-executions); and measured MJX / MuJoCo Warp numbers on an RTX 4070 laptop. Docs are in Portuguese; code and identifiers in English.

## Por que isso existe

Modelos de IA (e muita gente) aprenderam MuJoCo na versão 3.3 ou antes — e ele muda a cada poucas semanas: `mjData.qM` foi removido, atuadores multi-entrada quebram o acesso por nome, o `margin/gap` mudou de semântica, o integrador recomendado não é o padrão. Este projeto troca "achismo" por **conhecimento verificado**: cada afirmação virou um teste executado ou uma citação literal, e tudo foi empacotado numa skill que um agente pode carregar antes de mexer na ferramenta.

## O que tem aqui

- **Experimentos que se auto-validam** — cada `run.py` compara ≥ 3 grandezas com a física analítica e sai com código `0/1`; geram vídeo, GIF, tira de quadros e gráficos.
- **[`mujoco-lab-agent-skill`](.agents/mujoco-lab-agent-skill/SKILL.md)** — a skill única do laboratório: a **memória CoALA local** (episódica, semântica, procedimental e working memory orçamentada) **e** o controle verificado do MuJoCo 3.15 — 16 referências de MuJoCo (+ o schema da memória), 10 scripts, 5 templates testados e uma suíte `pytest` (29 testes).
- **Documentação oficial offline** — espelho da tag 3.15.0 (MuJoCo, MuJoCo Warp, Playground, MJPC, Menagerie) + busca por texto, atributo MJCF, elemento, função C, enum e changelog ([`docs_search.py`](.agents/mujoco-lab-agent-skill/scripts/docs_search.py)).
- **Pesquisa profunda auditada** — [dossiê](pesquisas/2026-10-07-qual-e-a-forma-correta-e-atual-mujoco-3-15-x-out-2026-de-ins.md) com 16 perguntas, 362 fontes citadas e [verificação independente](pesquisas/verificacao/independente.md) por reexecução.
- **Benchmarks de GPU reais** — MJX e MuJoCo Warp medidos numa RTX 4070 Laptop de 8 GB ([resultados](.agents/mujoco-lab-agent-skill/references/gpu-benchmarks.md)).

## Regra de ouro: sempre simulador físico

Tudo o que corre aqui é **simulação física de verdade**, do primeiro ao último passo (`mj_step` com
gravidade, arrasto, contactos, atuadores e sensores). Não há cinemática, teleporte (só `reset` explícito
do simulador), corpos congelados nem "apoios mágicos": os robôs só se mexem por **comandos de atuador**
— os algoritmos são do utilizador — e a física decide o resto. Na prática:

- os programas **arrancam** nesse estado: o drone (`08_crazyflie_motores`) começa com **motores
  desligados** e assenta no chão pela física (`T` descolar · `H` pairar · `D` desligar); o Spot
  (`07_spot_motores`) começa de pé na postura `home`, sustentado pelos próprios servos;
- o que a simulação faz de facto (inclusive quando diverge da teoria de corpo rígido, como o acoplamento
  aerodinâmico do drone acima de ~1 m/s ou o acoplamento pelos pés no Spot) é **medido, registado nos
  READMEs e guardado na memória CoALA** — nada fica "na cabeça".

## Começar

Requisitos: Linux (testado em CachyOS/Arch, KDE Wayland), [`uv`](https://docs.astral.sh/uv/) e Python 3.13. GPU NVIDIA só é necessária para MJX/Warp.

```bash
git clone https://github.com/frederico-kluser/mujoco-lab && cd mujoco-lab
uv sync                                                        # .venv com mujoco 3.15, numpy, scipy, matplotlib, imageio
uv run python experiments/01_triangulo_invertido/run.py        # demo + validação física → experiments/01_…/out/ (mp4, gif, gráficos)
uv run python experiments/01_triangulo_invertido/view.py       # a mesma cena numa janela interativa
uv run pytest .agents/mujoco-lab-agent-skill/tests -q              # 29 testes (scripts, templates, experimentos, armadilhas; 1 só roda após o sync_docs.py abaixo)
python3 .agents/mujoco-lab-agent-skill/scripts/sync_docs.py        # (opcional) espelha a documentação oficial em docs/upstream/ (~17 s)
python3 .agents/mujoco-lab-agent-skill/scripts/env_check.py        # diagnóstico: Python, MuJoCo, GL/EGL, GPU, docs
```

Sem janela (CI/agentes) o render usa `MUJOCO_GL=egl`. Novos experimentos: `python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py <nome> --template blank|pendulum|arm|quadrotor|car`.

## Como criar um projeto neste laboratório (o padrão)

Todo projeto novo segue o mesmo caminho — **memória primeiro, física sempre, interface CLEAN + site, validação sem janelas**. O [`09_drone_hover_rl`](experiments/09_drone_hover_rl/README.md) é a implementação de referência de ponta a ponta (é a base a copiar em cada projeto novo; o template `lab-padrao` empacota este conjunto).

### 0 · Começar pela memória
```bash
python3 .agents/mujoco-lab-agent-skill/scripts/coala.py recall "<o que quero fazer>" --budget 1500
python3 .agents/mujoco-lab-agent-skill/scripts/coala.py recall "<o que quero fazer>" --type episodic --budget 600
```
O que já foi decidido e testado está aqui — não duplicar trabalho. No fim de cada etapa, `add` do que for durável (o ciclo completo está no [`SKILL.md`](.agents/mujoco-lab-agent-skill/SKILL.md)).

### 1 · Pegar algo do GitHub (robô/modelo pronto)
Preferir modelos de boa reputação (ex.: `mujoco_menagerie`) a construir de zero. Clone *sparse* só da pasta do robô para `$TMPDIR`; **vendorizar em `models/<robo>/` INTACTO** (XMLs + `assets/` + `LICENSE`/`README`/`CHANGELOG`); o espelho `docs/upstream/` serve de referência mas não traz malhas. Cruzar com as specs **reais** do fabricante (datasheets) e citar as fontes no README do experimento (conteúdo web = `untrusted`, só se cita).

### 2 · Camada `lab/<robo>.py` (toda a adaptação em runtime)
Nunca editar o upstream: sensores (via MjSpec), escalas de atuadores e modos vivem em `lab/`. Padrão: `carregar()` → `(model, data)` com sensores · `definir_*()` em unidades físicas, cortados às faixas do modelo · `MODOS` (roteiros abertos `f(model, data, tau)`, sem realimentação) · `ler_*()`. **Sem código pronto de estabilização, controle, IK, marcha ou voo** — os algoritmos são do dono. Sensores são desejáveis: quadrúpede → IMU + encoders + forças dos pés (`touch`); drone → IMU + posição/velocidade.

### 3 · Experimento (`run.py` valida, `view.py` mostra)
```bash
python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py <nome> --template blank|pendulum|arm|quadrotor|car
```
`experiments/NN_nome/`: `run.py` (validação por **fórmulas fechadas em condições isoladas** — modelo fresco, sem histórico — com `exit 0/1`), `view.py`, `README.md` (tabelas medido × teoria + fontes) e `out/` (gerado, ignorado pelo git). Antes de simular a sério: `.venv/bin/python .agents/mujoco-lab-agent-skill/scripts/inspect_model.py <modelo.xml> --tree`.

### 4 · RL (quando a tarefa é *aprender* uma política)
- **`env.py`** (Gymnasium): observação normalizada **no próprio env** (sem `VecNormalize` → o grafo ONNX do deploy fica puro), ação `Box(-1,1)` **centrada no hover**, recompensa densa (posição + altitude + orientação + taxa de ação) e vento físico (`definir_vento`, `vento_aleatorio`, vento dinâmico). Física 500 Hz, decisão 50 Hz; reset pousado com assentamento físico (nada de teleporte).
- **`train.py`**: PPO (SB3, `MlpPolicy` 64×64), `n_envs` 8, L2 1e-4, `log_std_init −0,5`, **currículo de vento com critério alcançável** (`frac_xy_z ≥ --avanco-frac`), `--retomar` para fine-tune, telemetria `train_log.jsonl` (13 campos) e `--sem-painel` para CI.
- **Lições medidas** (a memória tem os números): penalizar a **taxa de ação** (Δa 0,05) — sem isso a política satura os momentos e capota (*chatter*); currículo cujo critério nunca é atingido = DR nunca liga; **nunca “polir” sem vento** (degrada) e o vento tem de estar *no treino*.
- **Critério de aceitação**: grelha de vento `{0,1,2,3} m/s × 4 direções` — `|z−1| ≤ 0,05 m`, `‖xy‖ ≤ 0,10 m` (0,15 a 3 m/s), `|yaw| ≤ 0,10 rad`, **0 quedas**.

### 5 · Interface padrão: simulação CLEAN + site (`padrao-simulacao-clean-site`)
```bash
cd experiments/NN_nome/site && npm install && npm run build      # 1.ª vez (fazer `source ~/.secrets` antes — token Motion+)
uv run --group hover-rl python experiments/NN_nome/sim_site.py  # o comando único: janela + site
```
- **`sim_view.py`** — janela 100 % **CLEAN** (só o 3D: `show_left_ui=False`, `show_right_ui=False`, `clear_texts`, zero `set_texts`/`set_figures`), telemetria JSONL (~10 Hz) e **sem auto-loop**: o fim do episódio **congela** a física e só o botão REINICIAR (contador atómico no ficheiro de controlo) recomeça.
- **`site/`** — React construído com a skill **`motion-plus-ui`** (cascata `search`→`add`→`compor`; `../motion.theme`; npm, **não** pnpm): *todas* as métricas e controlos (curvas, rede 16→64→64→4 ao vivo, obs/ações, vento em tempo real, REINICIAR, LOOP). Nunca reinicia sozinho.
- **`INTERFACE.md`** — tudo o que é visível, elemento a elemento; auditoria `uxui-evaluator` (41 → 88/100).
- Contratos: `out/controle_vento.json` (7 campos) · `out/sim_telemetria.jsonl` (15 chaves) · API de 5 rotas.

### 6 · Deploy no alvo (Raspberry Pi 5)
```bash
uv run --group hover-rl python experiments/NN_nome/deploy.py --model <final.zip> [--int8] [--nproc 4 --pinned]
```
SB3 → ONNX (exporter legacy `dynamo=False`, opset 17, batch = 1 estático; comparar com a **média** da política, não com amostras), validação numérica (medida: `max|Δ|` 5,7e-06), benchmark `p50/p99/max` com `intra_op=1` e multi-IA em processos com o mapa de cores decidido no pai. Regra: **o limite do alvo aplica-se na RUN; o treino usa o poder máximo**.

### 7 · Validação e qualidade
`run.py` dos experimentos → `exit 0/1` · `uv run pytest .agents/mujoco-lab-agent-skill/tests -q` (29 passed) · `ruff check` · verificadores adversariais por peça e um do conjunto no fim · `git status` limpo. **Validação SEM janelas** (regra do dono): agentes nunca abrem viewer/janela — provam por headless, mocks e handles falsos; o smoke visual é do dono.

### 8 · Registar (nada fica “na cabeça”)
README do experimento com as tabelas medido × teoria e as fontes · `coala.py add` (episódico/semântico/procedural — chaves estáveis por assunto e **supersessão em vez de reescrita**) · catálogo de robôs adaptados no [`AGENTS.md`](AGENTS.md).

## Experimentos

| # | Experimento | O que valida | Resultado medido (MuJoCo 3.15.0) |
| --- | --- | --- | --- |
| [01](experiments/01_triangulo_invertido/README.md) | Triângulo de cabeça para baixo caindo | massa = ρ·V, impacto = queda livre, energia, repouso, altura = raio inscrito | 20,7846 kg (= analítico) · impacto em 0,398 s (previsto 0,396 s) · repouso a 0,1155 m (= raio inscrito) |
| [02](experiments/02_pendulo/README.md) | Pêndulo físico | período exato (integral elíptica) × Euler/RK4/implicit/implicitfast | erro de período ≤ 0,0002 % · RK4 conserva a energia; os demais derivam +0,0024 % em 10 períodos |
| [03](experiments/03_haste_relatorio/README.md) | Haste articulada de um relatório técnico | o modelo original trava por colisão; correção; pêndulo forçado × EDO | \|θ\|máx 0,005 → 2,24 rad · RMS de 0,54 mrad contra a EDO não linear |
| [04](experiments/04_drone_quadricoptero/README.md) | Quadricóptero | controlador geométrico SO(3), waypoints, vento | decola em 1,08 s · erro ≤ 0,3 cm nos waypoints (≤ 4 cm com vento de 8 m/s) |
| [05](experiments/05_carro_ackermann/README.md) | Carro de 4 rodas | direção Ackermann × modelo cinemático de bicicleta | guinada 6,3 % abaixo da previsão (μ = 1); derrapa com μ = 0,35 |
| [06](experiments/06_braco_3gdl/README.md) | Braço robótico 3 GDL | cinemática inversa por Jacobiano + servos PD | erro RMS de 4 mm · torque máximo de 1,6 N·m |
| [07](experiments/07_spot_motores/README.md) | Spot (menagerie) | 12 servos `position` + 32 sensores (IMU, pés `touch`, encoders) via MjSpec; modos e controles como funções | `run.py` 9/9 `[OK]` · arranca de pé na postura `home`, sustentado pelos servos |
| [08](experiments/08_crazyflie_motores/README.md) | Crazyflie 2 (menagerie) | 4 canais wrench (`body_thrust` + 3 momentos); sensores IMU/posição/velocidade | `run.py` 8/8 `[OK]` · arranca com motores desligados e assenta no chão pela física |
| [09](experiments/09_drone_hover_rl/README.md) | Drone com RL: pairar a 1 m sob vento | PPO (SB3) sobre obs 16 e ação centrada no hover; vento físico (`opt.wind`), currículo + **vento dinâmico** (rajadas/frente/turbulência), interface CLEAN + site | critério do dono: **57/57** (16 condições constantes 0–3 m/s + 3 dinâmicas, 3 seeds; pior ‖xy‖ 0,108 m · \|yaw\| ≤ 0,020 rad · 0 quedas) e **144/144** no stress denso — campeão `out/vento_r10_ft_dryden_600k/best_model.zip` · `run.py` 121/121 · ONNX 5,7e-06 |

<table>
  <tr>
    <td align="center"><img src="docs/media/exp04_drone.png" alt="Quadricóptero voando um quadrado de waypoints"><br><sub>04 · quadricóptero</sub></td>
    <td align="center"><img src="docs/media/exp05_carro.png" alt="Carro Ackermann em curvas à esquerda e à direita"><br><sub>05 · carro Ackermann</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/media/exp06_braco.png" alt="Braço de 3 graus de liberdade seguindo um alvo circular"><br><sub>06 · braço 3 GDL</sub></td>
    <td align="center"><img src="docs/media/exp03_pendulo.png" alt="Pêndulo forçado validado contra a EDO não linear"><br><sub>03 · pêndulo forçado</sub></td>
  </tr>
</table>

## A agent skill

Peça ao agente para carregar `mujoco-lab-agent-skill` antes de qualquer trabalho com MuJoCo (ela é descoberta por `.agents/skills/` e `.claude/skills/`, symlinks já versionados). Ela impõe um protocolo com a **memória primeiro**: `coala.py recall` do que já se sabe → consultar a documentação local antes de afirmar → partir de um template testado → validar o modelo → simular sem janela com critérios de aceitação → depurar → `coala.py add` do que ficou durável.

| Referência | Para quê |
| --- | --- |
| [`mjcf-cheatsheet`](.agents/mujoco-lab-agent-skill/references/mjcf-cheatsheet.md) · [`python-api`](.agents/mujoco-lab-agent-skill/references/python-api.md) | modelar e programar (o que mudou de 3.0 a 3.15) |
| [`physics-tuning`](.agents/mujoco-lab-agent-skill/references/physics-tuning.md) · [`actuators-sensors`](.agents/mujoco-lab-agent-skill/references/actuators-sensors.md) | integradores, contato, estabilidade; atuadores e sensores |
| [`robots`](.agents/mujoco-lab-agent-skill/references/robots.md) · [`drones`](.agents/mujoco-lab-agent-skill/references/drones.md) · [`vehicles`](.agents/mujoco-lab-agent-skill/references/vehicles.md) | braços e URDF, quadricópteros e aerodinâmica, rodas e pneus |
| [`gpu-mjx-warp`](.agents/mujoco-lab-agent-skill/references/gpu-mjx-warp.md) · [`gpu-benchmarks`](.agents/mujoco-lab-agent-skill/references/gpu-benchmarks.md) | MJX e MuJoCo Warp: limites, receita e medições |
| [`rendering-viewer`](.agents/mujoco-lab-agent-skill/references/rendering-viewer.md) · [`telemetry-rerun`](.agents/mujoco-lab-agent-skill/references/telemetry-rerun.md) · [`install-linux`](.agents/mujoco-lab-agent-skill/references/install-linux.md) | render/viewer em Wayland+NVIDIA, Rerun, instalação |
| [`docs-map`](.agents/mujoco-lab-agent-skill/references/docs-map.md) · [`official-skills-errata`](.agents/mujoco-lab-agent-skill/references/official-skills-errata.md) | mapa da doc e quebras por versão; 63 blocos das skills oficiais executados (12 falham) |
| [`experiments-playbook`](.agents/mujoco-lab-agent-skill/references/experiments-playbook.md) · [`relatorio-auditoria`](.agents/mujoco-lab-agent-skill/references/relatorio-auditoria.md) | método de validação e catálogo de experimentos; auditoria de um relatório técnico |

## Pesquisa e verificação

A pesquisa usou o modo profundo da [`tavily-agent-skill`](https://github.com/frederico-kluser/tavily-agent-skill): **16 investigadores em paralelo, 337 consultas, 585 fontes lidas, 400 afirmações com citação literal**, um crítico de contexto limpo e uma etapa de **reexecução independente** (38 checagens contra o MuJoCo instalado, AUR, PyPI e GitHub — 38/38 confirmadas). Um relatório técnico de partida foi auditado afirmação por afirmação (99): 31 corretas, 47 parciais, 10 incorretas, 2 desatualizadas, 3 não verificadas, 6 fora do escopo. Destaques:

- `pkg_search_module(MUJOCO mujoco)` não funciona (o MuJoCo não instala `mujoco.pc`); o caminho é `find_package(mujoco CONFIG)`.
- O RK4 **não** preserva «(h|ω|)²» e o integrador implícito **não** é incondicionalmente estável; o recomendado é o `implicitfast`.
- Os 2,96 M e 2,33 M de passos/s da documentação são ambos **MJX-Warp** (Humanoid e Aloha Pot), não "MJX contra MuJoCo Warp".
- Com atuadores multi-entrada (`pid`, `dcmotor`, `orientation`) o acessor `data.actuator('x').ctrl` grava no slot errado.
- `urdf2mjcf` não faz CoACD nem balanceia a inércia; e um exemplo de haste articulada travava a própria junta por colisão (experimento 03).

## GPU: MJX e MuJoCo Warp (RTX 4070 Laptop, 8 GB)

Humanoide, 4096 mundos, mediana de execuções (receita, protocolo e armadilhas em [`gpu-benchmarks.md`](.agents/mujoco-lab-agent-skill/references/gpu-benchmarks.md)):

| Backend | Passos/s | VRAM |
| --- | ---: | ---: |
| MuJoCo Warp (nativo) | ≈ 1,9 M | 370 MiB |
| MJX-Warp | ≈ 1,8 M | 480 MiB |
| MJX-JAX | 27 K – 87 K | 1,2 GB |
| CPU, 32 threads (`mujoco.rollout`) | ≈ 0,25 M | — |

Os números oficiais (2,96 M / 3,35 M) não foram reproduzidos: a documentação não declara o hardware.

## Estrutura

```text
.
├── pyproject.toml · uv.lock          # ambiente (grupos opcionais: viz, urdf, rl, dmc, gpu)
├── models/                           # MJCF reutilizáveis
├── experiments/NN_nome/              # run.py (validação) · view.py · README.md · out/ (gerado, ignorado)
│   └── 09_drone_hover_rl/            # o padrão completo: env.py · train.py · sim_view.py · sim_site.py · site/ · INTERFACE.md
├── lab/mjkit.py                      # symlink para a biblioteca da skill (Ctrl, record, plot…)
├── .agents/mujoco-lab-agent-skill/   # SKILL.md · references/ · scripts/ (coala.py incluído) · assets/templates/ · tests/ · memory/ (CoALA local, fora do git)
├── pesquisas/                        # dossiê, fichas de conhecimento, retornos dos investigadores, verificação
├── docs/                             # relatório original, mídia do README, texto do LinkedIn, docs/upstream (gerado)
└── AGENTS.md                         # regras do projeto para agentes
```

## Notas e limites

- Verificado em MuJoCo **3.15.0** (2026-10-07); o estado de pacotes (AUR, PyPI) envelhece em dias — a skill indica como reverificar.
- A janela interativa do viewer só foi exercitada num teste de 3 s; o MuJoCo Studio (experimental) não roda em Wayland e não foi testado.
- MJX/MuJoCo Warp exigem um venv separado (`.venv-gpu`); o `uv sync --group gpu` não foi testado.
- A memória CoALA local do laboratório **não é versionada** (o motor vem de uma skill privada): veja [`.agents/mujoco-lab-agent-skill/README.md`](.agents/mujoco-lab-agent-skill/README.md). Sem ela nada quebra.
- Texto para divulgação: [`docs/linkedin-about.md`](docs/linkedin-about.md).

## Licença e créditos

Sem licença: todos os direitos reservados ao autor. O [MuJoCo](https://github.com/google-deepmind/mujoco) é da Google DeepMind (Apache-2.0) e a documentação oficial espelhada em `docs/upstream/` **não** é versionada aqui (é gerada por `sync_docs.py`).

Autor: [@frederico-kluser](https://github.com/frederico-kluser).
