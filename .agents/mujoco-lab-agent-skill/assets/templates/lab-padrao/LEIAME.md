# LEIAME.md — `{{NOME_EXPERIMENTO}}`: criado do TEMPLATE BASE `lab-padrao` (adapta isto ao teu robô)

Este é o template que se copia para **todo** experimento novo com RL + interface. O que fizemos no
`experiments/09_drone_hover_rl/` **é o padrão** e está aqui dentro, reduzido a um exemplo que arranca de raiz
(uma **haste com junta hinge e alvo de ângulo**, accionada por torque, com perturbação externa = "vento").

```bash
# 1) criar o experimento a partir DESTE template (o script faz o número NN e o lab/mjkit.py)
python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py <nome> --template lab-padrao

# 2) validar de raiz (headless, sem janelas) — tem de dar exit 0
uv run --group hover-rl python experiments/NN_<nome>/run.py

# 3) treinar no terminal (headless; o painel rich é opcional)
uv run --group hover-rl python experiments/NN_<nome>/train.py --timesteps 200000 --nome base

# 4) ARRANQUE DO PADRÃO: UM comando = janela 3D limpa + site com todas as métricas e controlos
cd experiments/NN_<nome>/site && node ensure-setup.mjs && npm run build && cd -
uv run --group hover-rl python experiments/NN_<nome>/sim_site.py --model experiments/NN_<nome>/out/runs/base/best_model.zip
```

---

## 1. O que adaptar PRIMEIRO (por ordem)

| # | sítio | o que muda |
|---|---|---|
| 1 | `model.xml` | o **modelo**: o teu MJCF simples, ou o teu `models/<robo>/` vendorizado carregado por MjSpec numa camada `lab/<robo>.py`. Mantém nomes sensatos (`pivo`/`torque`/`ponta`) **ou** adapta a secção «nomes lidos do modelo» do `env.py`. |
| 2 | `env.py` → `observacao()` | a **observação NORMALIZADA** (≈[-1,1], sem unidades cruas). Muda `N_OBS`. |
| 3 | `env.py` → `acao_para_ctrl()` | a **ação centrada no alvo**: `ctrl = trim + a·Δmax`. Sem isto a política gasta capacidade a redescobrir a gravidade/empuxo de equilíbrio. Muda `N_ACT`. |
| 4 | `env.py` → `recompensa()` | o que a política aprende: parcelas explícitas (erro, velocidade, esforço, taxa de ação) **em unidades normalizadas** + bónus no alvo + terminação com penalidade. |
| 5 | `env.py` → `_forca_vento()` | a **perturbação física** (no drone é o modelo de fluido do MuJoCo; aqui é arrasto quadrático no site, sem velocidade relativa). Faixas `VENTO_VEL_MAX`. |
| 6 | `run.py` | as tuas **fórmulas fechadas** em condições isoladas (o que é verificável sem treino), com critério/esperado/medido e exit 0/1. |
| 7 | `sim_view.py` → `amostra()` | as **3 métricas** do painel (aqui `theta`, `erro`, `omega`) — e o mesmo em `site/src/lib/sim.ts` (`METRICAS`). |
| 8 | `site/src/lib/sim.ts` | a secção **CONFIGURAÇÃO**: `METRICAS`, `ROTULOS_OBS`, `ROTULOS_ACT`, `UNIDADE_CTRL`, `NOME_EXPERIMENTO`. É a ÚNICA parte do site a mexer. |
| 9 | `train.py` → `FASES` | o **currículo** (alvo/vento por fase) e o `VentoAleatorio` (DR). |

## 2. O que NUNCA mudar (é o que faz o padrão valer)

**Contratos do ficheiro de controlo, da telemetria e da API** (o site, o `deploy.py` e o `dashboard.py` dependem deles):

- **Telemetria** `out/sim_telemetria.jsonl` — 1 linha JSON por amostra, chaves **por esta ordem**:
  `t, estado, ep, passo, retorno, theta, erro, omega, vento_vel, vento_azim, obs[], act[], ctrl[], h1[], h2[]`;
  `estado ∈ {a_correr, pausado, episodio_terminado}`. Cadência: **0,1 s de tempo SIMULADO** a correr
  (determinística: o mesmo rollout dá sempre o mesmo ficheiro) e **1 Hz de parede** com o episódio parado.
- **Ficheiro de controlo** `out/controle_vento.json` — `{vel, azimute, elevacao, ativo, reiniciar, loop, t}`,
  escrito de forma **ATÓMICA** (`os.replace`) e lido a **cada passo de decisão**.
- **API de 5 rotas** — `GET /api/sim` · `GET /api/state` · `POST /api/vento` · `POST /api/reiniciar` ·
  `POST /api/loop`. Estados honestos: 400/404/500, «—» quando não há dados, **nunca números inventados**.
- **Sem ciclo automático** — no fim do episódio a física **CONGELA** e espera; só o **REINICIAR** do site
  (campo `reiniciar` = **contador**) ou o `loop` ligado recomeçam. O `reset()` explícito é o único reinício.
- **Janela LIMPA** — `show_left_ui=False`, `show_right_ui=False`, `clear_texts()` no arranque e **nunca**
  `set_texts`/`set_figures`. A janela mostra só a simulação 3D; tudo o resto está no site.

**Regras do laboratório** (não são negociáveis):

- **Simulador SEMPRE físico**: tudo passa por `mj_step` (gravidade, arrasto, contactos, atuadores). Nada de
  cinemática, teleporte, corpos congelados ou "apoios mágicos"; a perturbação entra como força externa real.
- **Sem janelas em validação**: `run.py`, `view.py --sem-janela`, `train.py`, `deploy.py` e qualquer teste
  correm **sem** abrir janelas (o `mjkit` fixa `MUJOCO_GL=egl`, offscreen). Só `sim_view.py` (o padrão) e
  `view.py` (bancada) abrem janela — e só quando pedidos.
- **Temporários em `$TMPDIR`**, saídas em `out/` (ignorado pelo git), nunca `node_modules/`/`dist/` no git.
- **Unidades SI, +Z para cima, ângulos em graus no XML**; `import lab.mjkit` **antes** de `import mujoco`.

## 3. Mapa dos ficheiros

| ficheiro | para que serve |
|---|---|
| `model.xml` | modelo de exemplo (haste/alvo). Substitui pelo teu. |
| `env.py` | ambiente Gymnasium: obs normalizada, ação centrada no trim, recompensa, vento, guardas NaN. |
| `run.py` | **validação** por fórmulas fechadas em condições isoladas (7 checagens, exit 0/1) + `out/resumo.json`. |
| `sim_view.py` | **runner do padrão**: janela limpa + telemetria JSONL + leitura do controlo. |
| `sim_site.py` | **UM comando**: arranca o runner, serve `site/dist/` e a API de 5 rotas; abre o browser. |
| `site/` | app React (motion-plus-ui) com todas as métricas/controlos — ver `site/LEIAME.md`. |
| `view.py` | bancada: janela **com HUD** (θ(t), erro(t), teclado, REPL) e modo `--sem-janela`. |
| `train.py` | PPO SB3 headless: currículo, DR, `--retomar`, telemetria JSONL, checkpoints + `best_model.zip`. |
| `dashboard.py` | gestão de TREINO no terminal: rondas, melhor retorno, checkpoints, comando para retomar. |
| `net_probe.py` | sonda da REDE: ativações (h1/h2) passo a passo para uma observação/estado (sem auto-loop). |
| `deploy.py` | export **ONNX** + validação numérica + **benchmark proxy RPi** + **multi-IA** (N processos). |
| `README.md` | README do EXPERIMENTO (o que é, números medidos × teoria, fontes). |
| `INTERFACE.md` | guia de **tudo o que é visível** (janela, teclas, cada campo do site, ficheiros por baixo). |

## 4. Comandos do dia-a-dia

```bash
uv run --group hover-rl python <exp>/run.py --json            # validação + resumo
uv run --group hover-rl python <exp>/sim_view.py --sem-janela --max-segundos 3   # runner sozinho, sem janelas
uv run --group hover-rl python <exp>/sim_site.py              # padrão completo (runner + servidor + site)
uv run --group hover-rl python <exp>/view.py --sem-janela     # bancada sem janela
uv run --group hover-rl python <exp>/train.py --retomar <exp>/out/runs/base/final.zip --timesteps 100000
uv run --group hover-rl python <exp>/deploy.py --skip-multi   # ONNX + benchmark rápido
uv run --group hover-rl pytest .agents/mujoco-lab-agent-skill/tests -q   # testes da skill (29+)
ruff check <exp>/*.py && ruff check .agents/mujoco-lab-agent-skill/scripts/new_experiment.py
```

## 5. Números do exemplo (para comparar quando adaptares)

| grandeza | valor medido | fórmula |
|---|---|---|
| massa / braço CM / inércia no pivô | 3,0581 kg · 0,7759 m · 1,88446 kg·m² | modelo compilado (`mj_getTotalmass`, `mj_fullM`) |
| trim no alvo 60° | 20,1572 N·m | `m·g·d·sin θ*` |
| período livre (θ0=5°) | 1,78867 s (erro −0,000 %) | `T0·(2/π)·K(sin²(θ0/2))` |
| deriva de energia (dt=2 ms, implicitfast) | 0,346 % em 6 s | sem amortecimento |
| equilíbrio com vento 5 m/s @0° | 38,1474° (erro 0,0000°) | raiz de `τ_trim − m·g·d·sinθ − b·cosθ·F = 0` |

Guia do padrão na memória CoALA: `padrao-simulacao-clean-site` (e `experiments/09_drone_hover_rl/INTERFACE.md`
como referência canónica).
