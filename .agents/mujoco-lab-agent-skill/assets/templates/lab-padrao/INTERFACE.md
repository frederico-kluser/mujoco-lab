# INTERFACE.md — tudo o que é visível no `{{NOME_EXPERIMENTO}}`

Guia das interfaces do experimento, para se ler ao lado do ecrã: **o que é cada número, cada botão, cada tecla
e cada ficheiro por baixo**. Escrito para o padrão do laboratório `padrao-simulacao-clean-site`.

> Princípio: **a janela do MuJoCo mostra só a simulação 3D; o site mostra tudo o resto.** Nada de HUD sobre o
> 3D no modo padrão; nada de ciclo automático — o episódio termina, a física **congela** e espera pelo
> **REINICIAR** (ou pelo LOOP ligado).

---

## 1. Como arrancar (um comando)

```bash
uv run --group hover-rl python experiments/NN_{{NOME_EXPERIMENTO}}/sim_site.py
```

Um comando arranca três coisas (é o `sim_site.py`):

1. o **runner** `sim_view.py` como subprocesso — abre a janela limpa e escreve a telemetria;
2. um servidor HTTP local (só stdlib) que serve o **site** (`site/dist/`) e a **API** (5 rotas);
3. imprime o URL (`[site] site em http://127.0.0.1:8080`) e **abre o browser**.

| flag | para quê |
|---|---|
| `--model CAMINHO.zip` | política PPO a pilotar; sem ela a ação é **nula** (`ctrl = τ_trim` = equilíbrio no alvo) |
| `--sem-janela` | **sem** janela 3D: só site + API + telemetria (validação/teste) |
| `--port N` | porta (padrão **8080**; se estiver ocupada tenta a seguinte e imprime o URL real; `0` = livre) |
| `--host H` | interface de escuta (padrão `127.0.0.1` — só a tua máquina) |
| `--controlo` / `--telemetria` | onde vivem o ficheiro de controlo e a telemetria (padrões em `out/`) |
| `--fator-tempo F` | ritmo: **1** = tempo real, 0,5 = metade, 2 = dobro, **0** = sem travão |
| `--seed N` | semente do reset (o episódio *k* usa `N + k`) |
| `--loop` | arranca já com auto-reset no fim do episódio (o normal é **off**) |
| `--sem-browser` / `--verboso` | não abre o browser / mostra cada pedido HTTP |
| `Ctrl+C` | fecha servidor **e** runner, sem órfãos |

Pré-requisito do site (uma vez por clone): `cd site && node ensure-setup.mjs && npm run build` (precisa do
token Motion+ em `~/.secrets` — ver `site/LEIAME.md`). Sem `dist/`, o servidor serve uma página a dizer
exatamente isso — e a API funciona na mesma.

## 2. A janela do MuJoCo (CLEAN) e a bancada (`view.py`)

**Modo padrão (`sim_site.py` → `sim_view.py`):** vê-se **só a simulação 3D** — a haste, o suporte, o chão, as
câmaras. **Não há** HUD, texto, gráficos nem painéis: o runner abre o viewer com `show_left_ui=False`,
`show_right_ui=False` e chama `clear_texts()` no arranque (nunca `set_texts`/`set_figures`). O que se vê
acontecer: a haste a manter (ou a perder) o alvo; o deslocamento do alvo quando o vento aperta; a **paragem
física** no fim do episódio (não há teleporte — o robô fica onde a física o deixou).

| tecla | efeito |
|---|---|
| **ESPAÇO** | pausa / retoma a física (a janela continua viva; a telemetria passa a 1 Hz) |
| **Q** ou **Esc** | fecha a janela (e o processo do runner) |

Não há mais teclas **de propósito**: vento, REINICIAR e LOOP são do site.

**Bancada (`view.py`, para depurar):** aqui HÁ HUD — painel de texto (`t`, `ep`, `passo`, `θ`, alvo, erro, `θ̇`,
`ctrl`, trim, vento, retorno, política) e 2 gráficos (θ(t) com a linha do alvo, erro(t) com o zero).
Teclado: **ESPAÇO** pausa · **R** reinicia · **V** vento ±1 m/s · **X** vento = 0 · **A/Z** alvo ±10° · **Q**
fecha. REPL no terminal: `vento 3 45` · `alvo 60` · `reset` · `sair`. Com `--sem-janela` não abre nada:
imprime a tabela de desempenho e escreve `out/vista_resumo.json`.

## 3. O SITE (todas as métricas e todos os controlos)

### 3.1 Cabeçalho
`episódio` · `passo` · `retorno` (retorno acumulado do episódio) · `reinícios` (contador de pedidos do site) ·
`amostras` (linhas no ficheiro de telemetria) · `estado` (`a correr` / `em pausa` / `episódio terminado —
clica REINICIAR`) · `política` (nome do `.zip` em uso, ou `trim (sem política)`) · `ligação` (verde = a
receber, com a idade do último dado) · `LOOP` (ligado/desligado).

### 3.2 Curvas (4 painéis)
`θ` (ângulo, graus, com a linha do **alvo** do episódio) · `erro` (θ − alvo, graus, com o **zero**) · `θ̇`
(graus/s, zero) · `vento em vigor` (m/s). Cada painel mostra o valor atual (número animado), a unidade e o
histórico desde o arranque da página. Eixo x = tempo; janela = últimos 600 pontos.

### 3.3 Rede da política
Ativações das camadas `obs → h1 → h2 → act`, uma caixa por nó (cor por |a|, número dentro). **Sem arestas**:
o contrato traz ativações, não pesos. Sem política carregada aparece «— sem ativações» (nada de zeros
inventados).

### 3.4 Observação e ação
Tabela das entradas da observação (rótulo, valor cru, barra) e painel da ação: cada `act[i]` (normalizado) e,
por baixo, o **`ctrl` FÍSICO** que o backend aplicou (em N·m) — é o número que corresponde ao que o robô faz.
Nas linhas de evento (arranque/reinício, `passo = 0`) a ação vale «—» porque **nenhuma** ação foi aplicada.

### 3.5 Controlos
`velocidade do vento` (0–5 m/s) · `azimute` (0–360°) · `elevação` (−90–90°) · **APLICAR VENTO** (botão
multi-estado: pronto → a enviar → aplicado/erro) · **PARAR VENTO** (velocidade 0 no mesmo azimute) ·
**rosa dos ventos** (direção/elevação em vigor; o comprimento do vetor é a velocidade) · **REINICIAR**
(manter premido 1 s — é o ÚNICO caminho de reinício) · **LOOP OFF/ON** (OFF por omissão) · `pedidos de
reinício` (contador).

### 3.6 Estados honestos
400 (valor/faixa inválida), 404 (rota/asset/path traversal), 500; `—` quando não há dados; o site **nunca**
reinicia sozinho e **nunca** inventa números. Quando o episódio termina, a física está mesmo parada: a
telemetria continua a 1 Hz só como prova de vida (`estado: episodio_terminado`).

## 4. Os ficheiros por baixo (contratos)

| ficheiro | conteúdo |
|---|---|
| `out/sim_telemetria.jsonl` | 1 linha JSON por amostra (0,1 s de tempo **simulado** a correr; 1 Hz de parede parado): `t, estado, ep, passo, retorno, theta, erro, omega, vento_vel, vento_azim, obs[], act[], ctrl[], h1[], h2[]` |
| `out/controle_vento.json` | `{vel, azimute, elevacao, ativo, reiniciar, loop, t}` — escrito **atomicamente** pelo site, lido a cada passo de decisão pelo runner |
| `out/runs/<ronda>/` | treino: `final.zip`, `best_model.zip`, `checkpoints/ppo_<passos>.zip`, `treino.jsonl`, `resumo_treino.json` |
| `out/resumo.json` | validação do `run.py`: as 7 checagens com critério/esperado/medido/ok |
| `out/vista_resumo.json` | desempenho do `view.py --sem-janela` |
| `out/deploy_report.json` | relatório do `deploy.py` (ONNX, validação, benchmark, multi-IA) |

**Invariante da telemetria:** nas linhas com ação aplicada (`passo > 0`) vale `ctrl == acao_para_ctrl(act)`.
Nas linhas de arranque/reinício (`passo = 0`, `t = 0`) vale `act == ctrl == []`: é "nenhuma ação", não um
comando inventado.

## 5. Treino e sonda (terminal, sem janelas)

- `train.py` — barra de progresso `rich` (opcional), uma linha de telemetria em `out/runs/<ronda>/treino.jsonl`
  cada `--relatorio-cada` passos (`passos`, `fase`, `alvo_graus`, `vento_max`, `fps`, `retorno_medio`,
  `comprimento_medio`, `erro_medio_graus`, `melhor_retorno`), `best_model.zip` quando a avaliação melhora,
  checkpoints periódicos e `final.zip` no fim. `--retomar CAMINHO.zip` continua de onde ficou.
- `dashboard.py` — relatório/gestão das rondas no terminal (tabela por ronda + comando para retomar/avaliar).
- `net_probe.py` — sonda a rede passo a passo: para uma observação (aleatória, de um `.zip` ou de um estado
  imposto) mostra `obs`, `h1`, `h2`, `act` e o `ctrl` resultante; **sem auto-loop por omissão**.
- `deploy.py` — export **ONNX** (entrada estática, opset 17) + validação numérica contra o PyTorch +
  **benchmark proxy RPi** (p50/p99, «cabe a 50 Hz?») + **multi-IA** (N processos, cada um com a sua sessão).

## 6. Limites conhecidos (deste exemplo)

Modelo rígido de 1 DOF com pivô fixo; sem atrito nem folgas; a perturbação é um arrasto quadrático no site
(sem velocidade relativa — o modelo de fluido do MuJoCo, usado no drone do exp. 09, já a considera);
`<motor>` sem dinâmica (comando instantâneo). Ao adaptar, mantém esta secção: os limites são parte da
interface.
