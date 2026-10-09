# INTERFACE.md — tudo o que é visível no experimento 09

Guia das duas interfaces do drone a pairar (política RL do `experiments/09_drone_hover_rl/`):
a **janela do MuJoCo** (só a simulação, limpa) e o **SITE** (todas as métricas e todos os controlos).
Escrito para se ler ao lado do ecrã: o que é cada número, cada botão, cada tecla e cada ficheiro por baixo.

> Princípio do laboratório (padrão CoALA `padrao-simulacao-clean-site`): **a janela mostra a simulação;
> o site mostra tudo o resto.** Nada de HUD sobre o 3D; nada de loop automático — o episódio termina e
> espera pelo **REINICIAR** do site.

---

## 1. Como arrancar (um comando)

```bash
uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py
```

Um comando arranca as três coisas (é o `sim_site.py`):

1. o **runner** `sim_view.py` como subprocesso — é ele que abre a janela limpa e escreve a telemetria;
2. um servidor HTTP local (só stdlib) que serve o **site** (`site/dist/`) e a **API** que o site consome;
3. imprime o URL no terminal (`[site] site em http://127.0.0.1:8080`) e **abre o browser**.

| flag | para quê |
|---|---|
| `--model CAMINHO.zip` | política a pilotar. Por omissão usa a **mesma cascata do `sim_view.py`**: 1) o modelo da **última validação com sucesso** em `out/avaliacao_vento/*.json` que ainda exista em disco (hoje o **campeão da ronda 10**, `out/vento_r10_ft_dryden_600k/best_model.zip` — 57/57 no critério e 144/144 no stress); 2) o `out/vento_*/final.zip` mais recente; 3) `out/runs/*/final.zip`; 4) qualquer `best_model.zip`. O motivo da escolha sai impresso no arranque |
| `--sem-janela` | **sem** janela 3D: só o site + API (útil para testar/gravar) |
| `--port N` | porta (default **8080**; se estiver ocupada, tenta a seguinte e imprime o URL real; `--port 0` = livre) |
| `--host H` | interface de escuta (default `127.0.0.1` — só a tua máquina) |
| `--controlo CAMINHO` / `--telemetria CAMINHO` | onde vivem o ficheiro de controlo e a telemetria (defaults em `out/`) |
| `--fator-tempo F` | ritmo da simulação: **1** = tempo real (default), 0,5 = metade, 2 = o dobro, **0** = sem travão (o mais rápido possível) |
| `--loop` | arranca já com auto-reset no fim do episódio (o normal é **off**: espera pelo REINICIAR) |
| `--sem-browser` | não abre o browser (o URL sai na mesma) |
| `--verboso` | mostra cada pedido HTTP no terminal |
| `Ctrl+C` (SIGINT/SIGTERM) | fecha servidor **e** runner, sem órfãos |

Pré-requisito do site (uma vez por clone): `cd site && npm install && npm run build` (precisa do token
Motion+ em `~/.secrets` — ver §5). Se o `dist/` não existir, o servidor diz
`corra npm run build em …/site/` e serve só essa mensagem.

---

## 2. A janela do MuJoCo (CLEAN)

O que se vê: **só a simulação 3D** — o drone (Crazyflie do menagerie, corpo intocado), o chão e a câmara.
**Não há** HUD, texto, gráficos, painéis laterais nem qualquer número: por desenho, o runner nunca chama
`set_texts`/`set_figures` (chama `clear_texts()` no arranque) e abre o viewer com
`show_left_ui=False, show_right_ui=False`. Toda a informação está no site.

### Teclas (com o foco na janela)

| tecla | efeito |
|---|---|
| **ESPAÇO** | pausa / retoma a física (a janela continua viva e a responder) |
| **Q** ou **Esc** | fecha a janela (e o processo do runner) |

Não há mais teclas de propósito: o vento, o REINICIAR e o LOOP são do site — é o que mantém o 3D limpo.

### O que se vê acontecer

- O drone **arranca pousado** (motores a zero, assenta pela física) e a política leva-o até **z = 1,0 m**,
  mantendo a posição em x,y e a **orientação fixa** (yaw ≈ 0) mesmo com vento.
- **Fim de episódio = congelar**: quando o episódio acaba (`terminated` — choque/capotamento/saída de
  limites — ou `truncated` — 10 s), a física **para**. A janela fica viva, o drone fica onde está, e não
  há episódio seguinte nenhum. Só o **REINICIAR** do site (ou `loop: true` / `--loop`) recomeça.
- Se usares as teclas embutidas do viewer (F2 = painel de informação, F5 = fullscreen, Tab/Shift+Tab =
  painéis) aparecem UI do próprio MuJoCo — é opcional e não faz parte do padrão.

---

## 3. O SITE (todas as métricas e controlos)

Uma página, sem navegação, em duas colunas: **métricas** (esquerda, larga) e **controlos** (direita,
`sticky`). Tem um link «saltar para os controlos» para teclado. Feito com `motion-plus-ui` (React +
shadcn/Tailwind; componentes do registry `@motion`) e atualizado por **polling a `GET /api/sim` a 2,9 Hz**
(350 ms). Sem websockets.

### 3.1 Cabeçalho (topo)

| elemento | o que é |
|---|---|
| título | **«Drone a pairar · política ao vivo»** (o `<title>` da página é «Drone a pairar · política ao vivo — exp. 09»); entrada animada do registry |
| **selo de estado** | `a correr` (token `primary`, ponto a pulsar) ou `episodio_terminado` (token `destructive`, ponto fixo). Em `episodio_terminado` o cartão **Controlos** ganha um anel `ring-destructive/40` e a faixa **«episódio N terminado — clica REINICIAR»** — o site nunca reinicia sozinho (se o LOOP estiver ligado, quem reinicia é o backend) |
| selo de **ligação** | `API ligada` (com «· última há N s» quando a última amostra tem ≥2 s), `à espera da API…` ou `API em baixo` — se a API cair, aparece um banner e os valores ficam a «—» (nunca `undefined`) |
| contadores | **episódio** (`ep`), **passos** (passos de decisão do episódio; 0–500 a 50 Hz = 10 s) e **retorno** (soma da recompensa v2b acumulada no episódio, 2 casas; quanto maior, melhor; um episódio perfeito ronda os +500) |
| **modelo** | `pasta/ficheiro.zip` que está a pilotar (ex.: `vento_r9_polir_vento3/final.zip`). O `/api/sim` e o `/api/state` anunciam **os dois** campos: `modelo_nome` (este rótulo legível) e `modelo` (o caminho absoluto, que só serve de tooltip). O site prefere o `modelo_nome`; se só vier o caminho, deriva o rótulo com `nomeModeloLegivel()` (`lib/sim.ts`). Sem modelo anunciado aparece «— (o /api/state não anunciou modelo)» |

### 3.2 Curvas (4 gráficos)

Cada cartão tem **título**, a **nota** por baixo do título, o valor atual (número animado, com unidade) e
um `sparkline` com o histórico local (acumulado por `ep:passo`; episódio novo ⇒ histórico novo). Títulos,
notas e casas decimais **reais**:

| curva (título real) | nota do cartão | o que mostra |
|---|---|---|
| **`z(t)`** | «altitude · linha fina = alvo 1,0 m» | altitude do centro de massa, em m (3 casas); é o **único** cartão com **linha fina de referência no alvo 1,0 m** |
| **`yaw_err(t)`** | «erro de guinada (rad) · alvo 0» | erro de orientação (yaw atual − yaw alvo 0), em rad (3 casas); perto de 0 = a apontar sempre para o mesmo lado (sem giro) |
| **`retorno(t)`** | «retorno acumulado do episódio» | recompensa acumulada no episódio, sem unidade (2 casas); soma passo a passo e cai a pique quando há choque (−100) |
| **`vento_vel(t)`** | «velocidade do vento aplicado (m/s)» | velocidade do vento em vigor, em m/s (2 casas); é o que está aplicado à física, não o slider |

### 3.3 Rede neural 16 → 64 → 64 → 4 (ao vivo)

O cartão chama-se **«Rede da política · ativações ao vivo»** e o canto direito repete o resumo
`16 → 64 → 64 → 4 · cor = |a| / máx da camada`.

- **16 entradas** = a observação normalizada do `env.py`; **64 + 64** = as duas camadas escondidas
  (`h1`, `h2`); **4 saídas** = a ação (média da Gaussiana da política).
- Cada **retângulo** é um neurónio; a **cor/opacidade** é proporcional a `|ativação|` **normalizada ao
  máximo da própria camada** (a camada mais "acesa" tem sempre um neurónio a 100%).
- **A cor tem significado**: `primary` = ativação positiva · `destructive` = negativa (tokens shadcn, sem
  hex); com o episódio terminado o SVG fica esbatido (opacidade 0,45).
- **Não há arestas** (linhas entre neurónios): o contrato de telemetria traz **ativações**, não pesos —
  desenhar ligações seria inventar dados.
- Sem ativações, a legenda do cartão diz exatamente **«o stream ainda não traz h1/h2 — as ativações
  aparecem quando o backend as publicar»** em vez de fingir zeros.

**As 16 entradas, por grupo** (índice → nome → unidade, e a escala fixa do `env.py`):

| idx | nome | unidade | escala |
|---|---|---|---|
| 0–2 | `dp_x`, `dp_y`, `dp_z` | m | ÷ 1 m |
| 3–5 | `roll/π`, `pitch/π`, `yaw/π` | rad | ÷ π |
| 6–8 | `v_x`, `v_y`, `v_z` (velocidade no corpo) | m/s | ÷ 1 m/s |
| 9–11 | `ω_x`, `ω_y`, `ω_z` | rad/s | ÷ 10 rad/s |
| 12–15 | `a_prev` (ação anterior: empuxo, mx, my, mz) | [-1,1] | 1:1 |

**As 4 saídas (ação)**: `a₀·empuxo`, `a₁·momento x`, `a₂·momento y`, `a₃·momento z` — são a **média crua**
da Gaussiana da política (pode sair de [-1,1]); quem corta é o `env.py` ao aplicar. No cartão
**«Ação · 4 canais»** (ao lado da tabela da observação; §3.4) o site mostra os valores **físicos**: empuxo
em **N** (0 … 0,589 N; a barra tem um traço de referência no **empuxo de hover = mg = 0,26487 N**) e os
momentos em **mN·m** (máximos 5,69 / 5,69 / 2,8 mN·m). A etiqueta do cartão diz **«ctrl do backend»**
quando a linha da telemetria traz o campo `ctrl` (é o comando físico que a física usou — §4.2) e
**«derivado da ação»** quando o site reconstrói o comando a partir do `act` (fórmula do
`HoverEnv.acao_para_ctrl`). As constantes físicas vêm do `/api/state` **se** forem anunciadas; hoje não
são, e o site usa os valores de recurso `FISICA_PADRAO` (`lib/sim.ts`).

### 3.4 Tabela da observação (e cartão da ação)

Dois cartões lado a lado (`xl:grid-cols-2`):

- **Tabela da observação**: 16 linhas na mesma ordem do grupo acima, com o valor **normalizado** (o que a
  rede vê; coluna `obs`) e, ao lado, o valor **cru** na unidade física (coluna `cru` = `obs × escala`),
  mais uma `progress-bar` por linha.
- **Ação · 4 canais**: o cartão descrito em §3.3 — barra do empuxo (com o traço de hover), 3 barras de
  momento em mN·m e a lista `a bruta (política)` com os 4 valores crus de `act`.

### 3.5 Controlos (coluna direita, sempre à vista)

O cartão tem o título **«Controlos»**, a nota «vento físico em tempo real · o site nunca reinicia
sozinho» e, no topo, a faixa de estado: «episódio N terminado — clica REINICIAR» (vermelha) ou «episódio
a correr · LOOP ligado (o backend reinicia ao terminar)» / «episódio a correr · sem auto-restart».

| controlo | detalhe |
|---|---|
| **força** (slider 0–5 m/s, passo 0,1) | velocidade do vento; 0 = sem vento. O cabeçalho da secção mostra o vento atual (`agora X m/s · Y°`) |
| **azimute** (slider 0–360°, passo 1°) | direção no plano horizontal: **0° = +x, 90° = +y** (sentido anti-horário, convenção matemática) |
| **elevação** (slider −90…90°, passo 1°) | componente vertical: positivo = vento a subir, negativo = a descer |
| **rosa dos ventos** | seta polar (SVG) que mostra a direção selecionada e o comprimento pela força |
| **APLICAR VENTO** | envia `POST /api/vento {vel, azimute, elevacao}` e escreve o ficheiro de controlo; o `multi-state-button` mostra o estado (`pronto → a enviar → ok/erro`) e confirma com um toast |
| **PARAR VENTO** | põe a velocidade a 0 (mantém a direção guardada) — o vento para imediatamente na física |
| **REINICIAR** | botão **com confirmação por toque** (`hold-to-confirm`): carrega e **mantém ~1 s** (o preenchimento confirma, para não reiniciar por clique acidental) → `POST /api/reiniciar` → o episódio recomeça do zero (pousado, jitter novo, vento em vigor). A etiqueta é «REINICIAR (manter 1 s)» |
| **LOOP** | interruptor `segmented-toggle`, **OFF por omissão**: ligado, o **backend** reinicia automaticamente ao terminar o episódio; desligado, o episódio fica terminado até carregares REINICIAR |

Abaixo dos controlos: resumo em texto do vento em vigor e do estado do episódio.

O vento do site é **constante** (muda quando tu quiseres, em tempo real, mas mantém-se até ao próximo
APLICAR). As dinâmicas de treino da ronda 10 — `rajadas` (rajadas que somam ao vento base), `frente` (uma
frente que substitui o vento a meio do voo) e `dryden` (turbulência) — existem no **ambiente e no treino**
(`env.HoverEnv(vento_dinamico=…)`, `train.py --vento-dinamico`), **não** neste painel; o
`out/controle_vento.json` não tem campo de modo. Ver `README.md` §«Vento dinâmico (r10)».

### 3.6 Estados e avisos

| estado | o que aparece |
|---|---|
| **a carregar** | esqueleto (skeleton) nos cartões até chegar a primeira linha |
| **sem dados** | mensagem «o servidor responde mas ainda não publicou passos: as curvas e a rede ficam vazias até o episódio arrancar.» |
| **API em baixo** | selo `API em baixo` + banner vermelho; valores a «—»; os POSTs falham com toast legível |
| **ações** | pilha de **toasts** (canto): vento aplicado/parado, episódio reiniciado (com o nº do contador do servidor), LOOP ligado/desligado, erros da API |
| **400** | corpo ou valores fora das faixas → o servidor devolve `{"erro", "codigo"}` e o toast diz o motivo |
| **404** | rota `/api/*` desconhecida, asset em falta ou `path traversal` → 404 explícito |
| **500** | falha inesperada no servidor → 500 (nenhum pedido mata o servidor) |

---

## 4. Os ficheiros por baixo (o que liga site ↔ simulação)

### 4.1 `out/controle_vento.json` — o site escreve, o runner lê **a cada passo de decisão**

```json
{"vel": 0.0, "azimute": 90.0, "elevacao": -10.0, "ativo": false, "reiniciar": 2, "loop": false, "t": 1791502694.35}
```

| campo | significado |
|---|---|
| `vel` | velocidade do vento, 0–5 m/s |
| `azimute` | direção horizontal, 0–360° (0° = +x, 90° = +y) |
| `elevacao` | componente vertical, −90…90° |
| `ativo` | `false` ⇒ vento **0** na física (a direção/força ficam guardadas para o próximo APLICAR) |
| `reiniciar` | **contador inteiro**. Quando **muda**, o runner faz `env.reset()` — é o ÚNICO caminho para recomeçar (não há auto-loop). A 1.ª leitura é linha de base; um contador ≥1 que apareça sem ficheiro prévio conta como reinício já pedido |
| `loop` | `true` liga o auto-reset no fim do episódio; `false` volta a esperar; **campo ausente = não mexe** (um ficheiro antigo só com vento continua válido) |
| `t` | carimbo de tempo da escrita (informativo) |

Todas as escritas são **atrónicas** (ficheiro temporário + `os.replace`), portanto o runner nunca lê um
ficheiro meio escrito. Escrever à mão também funciona (é um contrato de ficheiro): o runner vê pela
assinatura `mtime_ns + tamanho`.

### 4.2 `out/sim_telemetria.jsonl` — o runner escreve, o site lê

Uma linha JSON por amostra (**15 campos**): **~10 Hz** com o episódio a correr; **1 Hz** com ele parado
(batimento — o estado não muda); e **uma linha imediata** no instante em que o episódio termina.

| campo | significado |
|---|---|
| `t` | tempo de **simulação** do episódio (s); volta a 0 em cada reset |
| `estado` | `a_correr` ou `episodio_terminado` |
| `ep` | número do episódio (1, 2, 3… a cada REINICIAR) |
| `passo` | passo de decisão dentro do episódio (0–500; 50 Hz ⇒ 10 s por episódio) |
| `retorno` | recompensa v2b acumulada até aqui |
| `z` | altitude do CM (m) — alvo 1,0 |
| `dist_xy` | distância horizontal ao ponto de referência (m) |
| `yaw_err` | erro de orientação (rad) |
| `vento_vel`, `vento_azim` | vento **em vigor na física** (m/s, graus) |
| `obs` | 16 números — a observação que entrou na rede (normalizada) |
| `act` | 4 números — a ação que a rede mandou (média crua) |
| `ctrl` | 4 números — o comando **físico** que essa ação produziu: `data.ctrl` = [empuxo N, momento x, momento y, momento z (N·m)]. Invariante: `ctrl == acao_para_ctrl(act)` quando `passo > 0` (ação aplicada); nas linhas de reset (`passo == 0`, `t == 0`) vale `[0,0,0,0]`, porque o `env.reset()` zera o `data.ctrl` e não houve ação nenhuma. É este campo que o site rotula **«ctrl do backend»** (§3.3); sem ele, o site deriva da ação |
| `h1`, `h2` | 64 + 64 ativações das camadas escondidas (forward hooks nos `nn.Linear`), **na mesma linha** que `obs`/`act`/`ctrl` ⇒ alinhadas |

Cada linha é escrita com `flush`, para o site ver sem esperar pelo fecho do ficheiro.

### 4.3 A API (5 rotas `/api/*` + os ficheiros do site, JSON, local)

| rota | resposta |
|---|---|
| `GET /api/sim` | `{"estado","ep","passo","retorno","vento":{vel,azimute,elevacao,ativo},"modelo","modelo_nome","linhas":[…]}` com as **≤200** últimas amostras da telemetria |
| `GET /api/state` | resumo: `sim_vivo`, `pid`, `porta`, `controlo`, `telemetria`, `amostras`, `idade_telemetria_s`, `site_pronto`, `loop`, `reiniciar`, e **`modelo` + `modelo_nome`**. **Não** anuncia hoje as constantes físicas (`mg`, `thrust_max`, `momento_max`, `tau_escala`): o site usa os valores de recurso `FISICA_PADRAO` |
| `POST /api/vento` | `{"vel","azimute","elevacao"}` (qualquer subconjunto; faixas 0–5 / 0–360 / −90..90; NaN/inf → **400**) → escreve o controlo e responde `{"ok": true, "vento": {…}}` |
| `POST /api/reiniciar` | incrementa `reiniciar` → `{"contador": n}` |
| `POST /api/loop` | `{"ativo": bool}` → liga/desliga o auto-reset e responde `{"ok": true, "loop": bool}` |
| `GET /` e `/assets/...` | o site (`site/dist/`); qualquer caminho desconhecido cai no `index.html`; path traversal → **404** |

---

## 5. Interfaces alternativas (o resto do experimento)

| peça | para quê | como |
|---|---|---|
| **`sim_site.py`** | ⭐ **o comando normal**: janela limpa + site (este documento) | `uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py` |
| **`sim_view.py`** | só a janela limpa (e telemetria), sem site | `… sim_view.py [--fator-tempo 0.5] [--sem-janela --max-segundos 20]` |
| **`view.py`** | viewer **alternativo** com HUD de 8 linhas e teclas de vento (para depurar a rede sem site): `ESPAÇO` pausa · `R` reinicia · `[` `]` força ±0,5 m/s · `,` `.` azimute ±15° · `v` vento 0 · `Q`/`Esc` fecha | `… view.py [--model …] [--vento-inicial 3,90] [--sem-janela]` |
| **`dashboard.py`** | gestão de **TREINO** num site próprio (▶ Treinar, ■ Parar, curvas multi-run, rede ao vivo, painel de vento, log) — auditoria UX 41 → **88/100** | `… dashboard.py --port 8765 --out out` |
| **`net_probe.py`** | sonda: corre a política e grava a rede em JSONL (é o que o dashboard usa); modo **sem-loop** por omissão | `… net_probe.py --model …zip --out net.jsonl --interval 0.05 [--loop/--sem-loop]` |
| **`train.py`** | treino PPO com painel `rich` no terminal (τ: `--timesteps`, `--n-envs`, `--seed`, `--out-dir`, `--curriculo-vento 0,1,2,3`, `--retomar`, `--lr`, `--ent-coef`, `--log-std-init`, `--sem-painel`) | `… train.py --timesteps 500000 --seed 0` |
| **`deploy.py`** | export ONNX + validação + benchmark (proxy RPi 5) + multi-IA | `… deploy.py --model …zip [--int8] [--nproc 4]` |
| **`run.py`** | validação do env por fórmulas fechadas (121/121) | `… run.py` |
| **`site/`** | o código do site (React + `motion-plus-ui`); `npm run build` → `dist/` | `cd site && npm install && npm run build` |

**Notas de `motion-plus-ui`** (para quem for mexer no site): a cascata é *procurar no registry → instalar
(`npx shadcn@latest add @motion/<nome>`) → compor → só então código novo*; o token vive em `~/.secrets`
(`source ~/.secrets` antes de qualquer `npm`; usar **npm**, não pnpm 11); o tema importa-se com
`../motion.theme`; os ficheiros em `site/src/components/motion-ui/**` são do CLI (não editar — a
personalização vai em wrappers). Componentes usados: `sparkline` (curvas), `animated-number` (contadores),
`stagger-reveal` (título), `progress-bar` (barras de obs/ação), `hold-to-confirm` (REINICIAR),
`multi-state-button` (APLICAR VENTO), `segmented-toggle` (LOOP), `toast-stack` (avisos),
`skeleton`/`SkeletonReveal` (carregamento) e os tokens de movimento do `ui-theme`.

---

## 6. Limites conhecidos (honestos)

1. **A janela 3D nunca foi validada visualmente por um agente** — durante o desenvolvimento esteve (por
   ordem do dono) proibido abrir janelas; tudo o resto foi validado sem janela (`--sem-janela`, handles
   falsos, mock da API, Chrome headless). O smoke visual é do dono: abre e confirma que está limpa.
2. **`best_model.zip` é escolhido pelo retorno medido SEM vento.** Para vento, o artefacto validado é o
   **`out/vento_r10_ft_dryden_600k/best_model.zip`** (campeão da ronda 10: 57/57 no critério do dono e
   144/144 no stress; o anterior, `out/vento_r9_polir_vento3/final.zip`, fazia 16/16 na grelha 0–3 m/s).
   É este que o `--model` por omissão escolhe; aponta outro caminho se quiseres comparar.
3. **Envelope de vento fiável até 3 m/s** (acima disso a posição degrada suavemente: 3,5 m/s ⇒ ‖xy‖ ≈0,15 m;
   4 m/s ⇒ ≈0,19 m; não cai até 5 m/s). O slider vai até 5 m/s — acima de 3 é fora do envelope treinado.
4. **Precisão medida com 3 seeds degeneradas** (o ciclo fechado converge para o mesmo atrator; verificação
   independente confirma os valores, mas a estatística por condição é 1 trajetória efetiva).
5. **O site precisa do build** (`site/dist/`); `node_modules/` ≈299 MB (gitignored). Sem build, o servidor
   avisa e não há página.
6. **`MUJOCO_LOG.TXT`** é escrito no diretório de trabalho do runner (`experiments/09_drone_hover_rl/`,
   gitignored) — é normal do MuJoCo, não é erro.
7. **MCP `motion`** pode responder «tools fetch failed» (a env do MCP usa outra chave); a CLI
   (`motion-ui.mjs`) e o registry (`shadcn add`) funcionam — a cascata não depende do MCP.
8. **Multi-IA / deploy / RPi 5**: ver `README.md` (benchmark proxy, int8, multi-IA) — fora do âmbito deste
   guia, que descreve só o que é visível nas duas interfaces.
