# LEIAME.md — `{{NOME_EXPERIMENTO}}`: criado do TEMPLATE BASE `lab-padrao` (adapta isto ao teu robô)

Este é o template que se copia para **todo** experimento novo com RL + interface. O que fizemos no
`experiments/09_drone_hover_rl/` **é o padrão** e está aqui dentro, reduzido a um exemplo que arranca de raiz
(uma **haste com junta hinge e alvo de ângulo**, accionada por torque, com perturbação externa = "vento").

O template traz já o padrão na versão **r11**: vento **dinâmico ao vivo** (rajadas/frente/turbulência, sem
reiniciar o episódio), **painel do computador de bordo (Raspberry Pi 5)** no site, botão de ajuda «?» que
explica cada elemento, **rosa dos ventos viva** e a API de **6 rotas**.

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

# 5) medir a latência no alvo (alimenta o painel RPi 5 do site; ver §3)
uv run --group hover-rl python experiments/NN_<nome>/deploy.py --int8       # ONNX + validação + benchmark
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
| 7 | `sim_view.py` → `amostra()` | as **3 métricas** do painel (aqui `theta`, `erro`, `omega`) — e o mesmo em `site/src/lib/sim.ts` (`METRICAS`). As chaves `vento_vec`/`vento_modo` ficam: são do contrato. |
| 8 | `site/src/lib/sim.ts` | a secção **CONFIGURAÇÃO**: `METRICAS`, `ROTULOS_OBS`, `ROTULOS_ACT`, `UNIDADE_CTRL`, `NOME_EXPERIMENTO`. É a ÚNICA parte do site a mexer. |
| 9 | `train.py` → `FASES` | o **currículo** (alvo/vento por fase) e o `VentoAleatorio` (DR). |
| 10 | `site/src/components/sim/ajuda.tsx` | os **textos** de `SECOES_AJUDA` (o desenho não muda): cada elemento do ecrã explicado para quem chega de novo. |

**Vento dinâmico: o mínimo honesto que este template traz.** O `env.py` tem os TRÊS modos do treino —
`rajadas` (envelope `sin(π·k/(N+1))` que SOMA ao vento base), `frente` (degrau que o SUBSTITUI a partir de
`t_s`) e `dryden` (turbulência OU de 1.ª ordem saturada em norma a `u_max`) — com `valida_vento_dinamico()`
(chaves/faixas validadas, gralhas recusadas) e `definir_vento_dinamico()` para trocar de modo **a quente**,
sem `reset()` e sem consumir o `rng` quando `u_max = 0` (é o que torna um run com dinâmica bit-idêntico a um
run sem ela). O `rajada_agora` (rajada **dirigida** one-shot) não existe no `env.py`: é do `sim_view.py`, que
a compõe sobre o vento base passo a passo — o mesmo caminho físico (`definir_vento` → `qfrc_applied`), nada
de forças mágicas. Se o teu robô tiver outro modelo de perturbação, adapta `_forca_vento()`/`_passo_dryden()`
e mantém os nomes dos modos e as chaves dos params (o site, o `train.py` e a API falam essa linguagem).

## 2. O que NUNCA mudar (é o que faz o padrão valer)

**Contratos do ficheiro de controlo, da telemetria e da API** (o site, o `deploy.py` e o `dashboard.py` dependem deles):

- **Telemetria** `out/sim_telemetria.jsonl` — 1 linha JSON por amostra, **15 + 2 chaves por esta ordem**:
  `t, estado, ep, passo, retorno, theta, erro, omega, vento_vel, vento_azim, vento_vec[], vento_modo,
  obs[], act[], ctrl[], h1[], h2[]`; `estado ∈ {a_correr, pausado, episodio_terminado}`. `vento_vec` é o
  vector `[vx,vy,vz]` (m/s) do vento que a FÍSICA leva e `vento_modo` o modo dinâmico em vigor. Cadência:
  **0,1 s de tempo SIMULADO** a correr (determinística: o mesmo rollout dá sempre o mesmo ficheiro) e
  **1 Hz de parede** com o episódio parado.
- **Ficheiro de controlo** `out/controle_vento.json` — `{vel, azimute, elevacao, ativo, reiniciar, loop,
  dinamico:{modo, params, ativo, seq}, t}`, escrito de forma **ATÓMICA** (`os.replace`) e lido a **cada passo
  de decisão**. O bloco `dinamico` só atua quando a sua **assinatura** muda (o `seq` é o que permite disparar
  duas rajadas iguais seguidas).
- **API de 6 rotas** — `GET /api/sim` · `GET /api/state` · `POST /api/vento` · `POST /api/vento-dinamico` ·
  `POST /api/reiniciar` · `POST /api/loop`. Estados honestos: 400/404/500, «—» quando não há dados, **nunca
  números inventados**. Os modos `rajadas`/`dryden`/`frente`(b) são validados pelo PRÓPRIO `env.py` (as
  mesmas regras do treino); o `frente`(a) é um degrau imediato do vento base.
- **Sem ciclo automático** — no fim do episódio a física **CONGELA** e espera; só o **REINICIAR** do site
  (campo `reiniciar` = **contador**) ou o `loop` ligado recomeçam. O `reset()` explícito é o único reinício.
- **Janela LIMPA** — `show_left_ui=False`, `show_right_ui=False`, `clear_texts()` no arranque e **nunca**
  `set_texts`/`set_figures`. A janela mostra só a simulação 3D; tudo o resto está no site.
- **Painel do RPi 5 no site** — todo projeto mostra o painel do computador de bordo (specs do alvo +
  inferência medida + uso ao vivo). Sem relatório do `deploy.py` diz «sem benchmark»; não se inventam tempos.

**Regras do laboratório** (não são negociáveis):

- **Simulador SEMPRE físico**: tudo passa por `mj_step` (gravidade, arrasto, contactos, atuadores). Nada de
  cinemática, teleporte, corpos congelados ou "apoios mágicos"; a perturbação entra como força externa real.
- **Sem janelas em validação**: `run.py`, `view.py --sem-janela`, `train.py`, `deploy.py` e qualquer teste
  correm **sem** abrir janelas (o `mjkit` fixa `MUJOCO_GL=egl`, offscreen). Só `sim_view.py` (o padrão) e
  `view.py` (bancada) abrem janela — e só quando pedidos.
- **Temporários em `$TMPDIR`**, saídas em `out/` (ignorado pelo git), nunca `node_modules/`/`dist/` no git.
- **Unidades SI, +Z para cima, ângulos em graus no XML**; `import lab.mjkit` **antes** de `import mujoco`.

## 3. Computador de bordo: Raspberry Pi 5 (OBRIGATÓRIO em todos os projetos)

Todos estes projetos correm num **Raspberry Pi 5** a bordo. O alvo não é uma máquina de treino: é um SBC com
orçamento de tempo real apertado, e é isso que decide o que cabe.

**Especificações do alvo (BCM2712)**

| grandeza | valor |
|---|---|
| CPU | 4× **Cortex-A76 @ 2,4 GHz** (512 kB de L2 por núcleo + 2 MB de L3 partilhados) |
| SoC / GPU | Broadcom **BCM2712** / VideoCore VII |
| RAM | **LPDDR4X-4267** (1–16 GB conforme a variante) |
| Alimentação | **5 V / 5 A** (27 W); pico ~12 W |
| Limite térmico | *throttling* aos **80 → 85 °C** (corte de 2,4 → 1,5 GHz) |
| Orçamento de decisão | **50 Hz = 20 ms** por passo (o `PERIODO_50HZ_US` do `deploy.py`) |

**A lição (medida, não suposta): o gargalo é o JITTER DO SO, não a inferência.** Num kernel normal o pior
caso de escalonamento é da ordem de **9,4 ms** — metade do período de 20 ms, e o suficiente para estourar
qualquer prazo. Com kernel **PREEMPT_RT** desce a **≤225 µs**. A inferência da política é ordens de grandeza
mais barata: no experimento 09 (MLP 16→64→64→4) o p50 no proxy x86 foi **≈4,6 µs** e com este template
(4→64→64→1, ONNX de 19 655 B) mediu-se **p50 4,8 µs · p99 6,2 µs · max 9,5 µs** — o custo é dominado pelo
overhead do ONNX Runtime, não pelo tamanho da MLP. Ou seja: **mede a cauda (p99/pior caso) e o jitter, não a
média** — é o que o painel do site faz (semáforo OK ≤70 % do orçamento, ATENÇÃO acima disso, ERRO acima de 100 %).

**Como medir no laboratório**: `deploy.py` exporta o ONNX (opset 17, batch 1 estático), valida o grafo contra
o PyTorch com observações reais (max|Δ| ~1e-08) e corre um **benchmark proxy** de 1 core do A76 com
`intra_op=1`, mais o **multi-IA** (1 **processo por política**, com afinidade de core mapeada no PAI; no 09:
2 processos = 100,0 inferências/s, 0 estouros de 20 ms). Escreve `out/deploy_report.json` — é esse ficheiro
que alimenta o painel RPi 5 do site (`sim_site.py --benchmark CAMINHO.json` aponta a outro). No Pi 5 a sério,
corre-se o mesmo `deploy.py` lá e o painel passa a dizer «real» em vez de «proxy x86 calibrado».

**`int8` só compensa com SDOT**: a quantização dinâmica QInt8 dá **1,83×** no A76 (que tem SDOT), mas no x86
desta máquina ficou **MAIS LENTA** (`fator_p50 < 1` — medido). O painel mostra o fator medido tal e qual, com
o sinal à vista; não se promete ganho nenhum.

**Imagem do painel**: `site/src/assets/rpi5.webp` é uma **ilustração de referência** — um Raspberry Pi
**Model B+ (2014)**, não um Pi 5 — de Lucasbosch (Wikimedia Commons), **CC BY-SA 3.0**; a atribuição aparece
no painel e nos textos de ajuda. Os números do painel são do alvo (Pi 5) e vêm citados no `RPI5_SPECS` do
`sim_site.py` (Product Brief RP-008348-DS + medições publicadas no A76).

## 4. Mapa dos ficheiros

| ficheiro | para que serve |
|---|---|
| `model.xml` | modelo de exemplo (haste/alvo). Substitui pelo teu. |
| `env.py` | ambiente Gymnasium: obs normalizada, ação centrada no trim, recompensa, vento base + **vento dinâmico** (rajadas/frente/dryden), guardas NaN. |
| `run.py` | **validação** por fórmulas fechadas em condições isoladas (7 checagens, exit 0/1) + `out/resumo.json`. |
| `sim_view.py` | **runner do padrão**: janela limpa + telemetria JSONL (15+2 chaves) + controlo (vento base, bloco `dinamico`, REINICIAR, LOOP) e a rajada dirigida one-shot. |
| `sim_site.py` | **UM comando**: arranca o runner, serve `site/dist/` e a API de **6 rotas**; monta o painel RPi 5; abre o browser. |
| `site/` | app React (motion-plus-ui) com todas as métricas/controlos — ver `site/LEIAME.md`. |
| `site/src/components/sim/` | `cabecalho`, `curvas`, `rede`, `observacoes`, `controlos` (vento + dinâmico), **`rosa-ventos`**, **`rpi5`** (computador de bordo), **`ajuda`** (o «?»), `avisos`, `estilo`. |
| `view.py` | bancada: janela **com HUD** (θ(t), erro(t), teclado, REPL) e modo `--sem-janela`. |
| `train.py` | PPO SB3 headless: currículo, DR, `--retomar`, telemetria JSONL, checkpoints + `best_model.zip`. |
| `dashboard.py` | gestão de TREINO no terminal: rondas, melhor retorno, checkpoints, comando para retomar. |
| `net_probe.py` | sonda da REDE: ativações (h1/h2) passo a passo para uma observação/estado (sem auto-loop). |
| `deploy.py` | export **ONNX** + validação numérica + **benchmark proxy RPi** (alimenta o painel) + **multi-IA**. |
| `README.md` | README do EXPERIMENTO (o que é, números medidos × teoria, fontes). |
| `INTERFACE.md` | guia de **tudo o que é visível** (janela, teclas, cada campo do site, ficheiros por baixo). |

## 5. Comandos do dia-a-dia

```bash
uv run --group hover-rl python <exp>/run.py --json            # validação + resumo
uv run --group hover-rl python <exp>/sim_view.py --sem-janela --max-segundos 3   # runner sozinho, sem janelas
uv run --group hover-rl python <exp>/sim_site.py              # padrão completo (runner + servidor + site)
uv run --group hover-rl python <exp>/view.py --sem-janela     # bancada sem janela
uv run --group hover-rl python <exp>/train.py --retomar <exp>/out/runs/base/final.zip --timesteps 100000
uv run --group hover-rl python <exp>/deploy.py --int8         # ONNX + validação + benchmark (+ painel RPi 5)
uv run --group hover-rl pytest .agents/mujoco-lab-agent-skill/tests -q   # testes da skill (31+)
ruff check <exp>/*.py && ruff check .agents/mujoco-lab-agent-skill/scripts/new_experiment.py
```

## 6. Números do exemplo (para comparar quando adaptares)

| grandeza | valor medido | fórmula |
|---|---|---|
| massa / braço CM / inércia no pivô | 3,0581 kg · 0,7759 m · 1,88446 kg·m² | modelo compilado (`mj_getTotalmass`, `mj_fullM`) |
| trim no alvo 60° | 20,1572 N·m | `m·g·d·sin θ*` |
| período livre (θ0=5°) | 1,78867 s (erro −0,000 %) | `T0·(2/π)·K(sin²(θ0/2))` |
| deriva de energia (dt=2 ms, implicitfast) | 0,346 % em 6 s | sem amortecimento |
| equilíbrio com vento 5 m/s @0° | 38,1474° (erro 0,0000°) | raiz de `τ_trim − m·g·d·sinθ − b·cosθ·F = 0` |

Guia do padrão na memória CoALA: `padrao-simulacao-clean-site` e `padrao-rpi5-computador-bordo`
(e `experiments/09_drone_hover_rl/INTERFACE.md` como referência canónica).
