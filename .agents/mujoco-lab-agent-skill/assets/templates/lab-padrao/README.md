# {{NOME_EXPERIMENTO}} — experimento do template base `lab-padrao` (RL + janela limpa + site)

Experimento criado a partir do **template base do laboratório** (`assets/templates/lab-padrao`): uma **haste
com junta hinge e alvo de ângulo**, accionada por torque, com perturbação externa ("vento"). O que vem pronto:

**física validada por fórmulas fechadas** (`run.py`, exit 0/1) · **ambiente Gymnasium** (`env.py`, com vento
base e **vento dinâmico**: rajadas/frente/turbulência) · **PPO headless com currículo e DR** (`train.py`) ·
**padrão `padrao-simulacao-clean-site`** (`sim_site.py`: janela MuJoCo 100 % limpa + site com todas as métricas
e controlos, **6 rotas de API** e **vento dinâmico ao vivo** sem reiniciar o episódio) · **painel do computador
de bordo — Raspberry Pi 5** no site (specs do alvo, p50/p99 vs orçamento de 20 ms, semáforo, int8, multi-IA) ·
**ajuda «?»** que explica cada elemento · **rosa dos ventos viva** · **vista de bancada com HUD** (`view.py`) ·
**gestão de treino e sonda da rede** (`dashboard.py`, `net_probe.py`) · **ONNX + benchmark proxy RPi + multi-IA**
(`deploy.py`, cujo relatório alimenta o painel do RPi 5).

> Começa pelo **`LEIAME.md`** (o que adaptar primeiro, o que NUNCA mudar, comandos). O guia de tudo o que é
> visível — janela, teclas, cada campo do site — é o **`INTERFACE.md`**.

## Arranque (3 passos)

```bash
uv run --group hover-rl python experiments/NN_{{NOME_EXPERIMENTO}}/run.py        # 1) valida (exit 0 = física sã)
uv run --group hover-rl python experiments/NN_{{NOME_EXPERIMENTO}}/train.py --timesteps 200000 --nome base   # 2) treina
uv run --group hover-rl python experiments/NN_{{NOME_EXPERIMENTO}}/sim_site.py   # 3) PADRÃO: janela limpa + site
```

O site precisa de um build uma vez: `cd site && node ensure-setup.mjs && npm run build` (ver `site/LEIAME.md`).

## Números medidos (modelo de exemplo, `run.py`)

| grandeza | medido | critério (fórmula) |
|---|---|---|
| trim no alvo 60° | 20,1572 N·m | `τ_trim = m·g·d·sin θ*` (m, d, g do modelo compilado) |
| equilíbrio com o trim | erro 0,0000° (repouso) | a haste fica no alvo em 3 s com amortecimento |
| período livre (θ0 = 5°) | 1,788665 s (erro −0,000 %) | `T0·(2/π)·K(sin²(θ0/2))`, `T0 = 2π√(I/(m·g·d))` |
| deriva de energia (dt 2 ms, implicitfast) | 0,346 % em 6 s | sem amortecimento |
| equilíbrio com vento 5 m/s @ 0° | 38,1474° (erro 0,0000°) | raiz de `τ_trim − m·g·d·sinθ − b·cosθ·F = 0` |
| vento fora da faixa | cortado ao teto (5 m/s) | `definir_vento` corta; NaN levanta `ValueError` |

Massa 3,0581 kg · braço CM 0,7759 m · inércia no pivô 1,88446 kg·m² (do `mj_getTotalmass` e `mj_fullM`).

## Estrutura

`model.xml` (haste + atuador de torque + site da ponta) · `env.py` (obs normalizada, ação centrada no trim,
recompensa com bónus/terminação, vento físico — base + dinâmico — guardas NaN) · `run.py` (7 checagens isoladas) ·
`sim_view.py` + `sim_site.py` + `site/` (o padrão) · `view.py` (HUD de bancada) · `train.py` · `dashboard.py` ·
`net_probe.py` · `deploy.py` · `LEIAME.md` · `INTERFACE.md`.

## Adaptar

Substitui o modelo (o teu `models/<robo>/` via MjSpec numa camada `lab/<robo>.py`, ou um MJCF simples), a
observação, a ação centrada no alvo e a recompensa — pela ordem da tabela §1 do `LEIAME.md`. Os **contratos** do
ficheiro de controlo, da telemetria (**15 + 2 chaves**) e da API (**6 rotas**) não se mudam: é o que faz o site e
o `deploy.py` funcionarem sem alterações.

Fontes/regras do laboratório: `.agents/mujoco-lab-agent-skill/SKILL.md`, memória CoALA
(`padrao-simulacao-clean-site`, `padrao-rpi5-computador-bordo`) e a referência canónica do padrão em
`experiments/09_drone_hover_rl/`. O computador de bordo é sempre o **Raspberry Pi 5** — ver a secção
«Computador de bordo» do `LEIAME.md`.
