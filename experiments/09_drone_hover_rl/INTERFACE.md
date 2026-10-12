# INTERFACE.md — tudo o que é visível no experimento 09

Guia das duas interfaces do drone a pairar (política RL do `experiments/09_drone_hover_rl/`):
a **janela do MuJoCo** (só a simulação, limpa) e o **SITE** (todas as métricas e todos os controlos).
Escrito para se ler ao lado do ecrã: o que é cada número, cada botão, cada tecla e cada ficheiro por baixo.

> Princípio do laboratório (padrão CoALA `padrao-simulacao-clean-site`): **a janela mostra a simulação;
> o site mostra tudo o resto.** Nada de HUD sobre o 3D. O **LOOP** decide o que acontece no fim do
> episódio: **SEM REINÍCIO** (**padrão** desde 2026-10-09, pedido do dono) deixa a **física continuar** no
> estado em que ficou — nunca reinicia sozinha e nunca congela — e o **REINICIAR** do site é o único reset
> que existe; **CONTÍNUO** (`--com-loop` no arranque, ou o `POST /api/loop` depois) reinicia sozinho
> (ep+1). O arranque é **autoritativo** (corrige o `loop` do ficheiro de controlo) e depois só o
> `POST /api/loop` o muda (*sticky*).

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
| `--controlador rl\|classico` | **SELETOR DE CONTROLADOR** (contrato r12): `rl` = a política de sempre (**PADRÃO** — o comportamento não muda) ou `classico` = a cascata clássica C++ do firmware (via ctypes; yaw livre, WASDQE relativo ao rumo, «olhar» IBVS). Mostra-se no arranque; depois, o `POST /api/controlador` troca ao vivo (§4.7) |
| `--com-loop` (alias `--loop`) | **CONTÍNUO**: auto-reset no fim do episódio (ep+1, passo 0). **Não** é o padrão. Autoritativo no arranque: vence um `loop: false` velho do ficheiro de controlo, que fica corrigido para `true` (o site mostra o estado verdadeiro). O alias `--loop` é o nome antigo desta flag |
| `--sem-loop` | **SEM REINÍCIO** — é o **padrão** desde 2026-10-09; a flag fica aceite como pedido explícito e idempotente. No fim do episódio a física CONTINUA no estado em que ficou (nunca reinicia sozinha e nunca congela) e só um REINICIAR recomeça. Autoritativo no arranque: vence um `loop: true` velho do ficheiro, que fica corrigido para `false`. As duas flags juntas são recusadas (`exit 2`) |
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

Não há mais teclas de propósito: o vento, a CÂMARA e o REINICIAR são do site — é o que mantém o 3D limpo.
A câmara da janela (bloco «Câmara», §3.5) obedece a cada comando do site e, **entre comandos, o rato do
viewer continua livre** (orbitar/rodar/zoom na janela não é desfeito: só o próximo comando manda — os
**ângulos e a distância sobrevivem**). A exceção é o **PAN**: o `lookat` é reescrito pelo `seguir_drone` a
cada frame (§4.4) e por isso arrastar o alvo para longe do drone é **sempre sobreposto** — a câmara é
terceira-pessoa e o alvo não sai do drone.

### O que se vê acontecer

- O drone **arranca pousado** (motores a zero, assenta pela física) e a política leva-o até **z = 1,0 m**,
  mantendo a posição em x,y e a **orientação fixa** (yaw ≈ 0) mesmo com vento.
- As **4 hélices giram** na janela: `|ω| = 63,72·√t_i` rad/s (3 rev/s com um rotor no empuxo máximo; escala
  **VISUAL** ≈ 1/100 da rotação real, senão a 50 Hz seria ilegível) com o sentido de cada rotor (diagonais no
  mesmo sentido, vizinhas no oposto); com os motores a zero abrandam (τ = 0,35 s) e **param**. É só
  apresentação: 4 geoms visuais acrescentados em runtime (malha upstream intacta), fora do `mj_step` — a
  física é idêntica ao bit com a animação ligada ou desligada.
- **Fim de episódio — com SEM REINÍCIO (padrão desde 2026-10-09, `loop: false`)**: **a física NÃO para e
  nada reinicia**. O drone continua a ser integrado (`mj_step` a 50 Hz) no estado em que ficou — se caiu,
  fica onde a física o deixou (a política continua a comandar, mas o estado é o que a física decidir); se
  pairava, continua a pairar — e a telemetria segue a ~10 Hz com `passo`/`t` a crescer (muito além dos 500
  passos do episódio) e `retorno` congelado no valor com que o episódio fechou. Só o **REINICIAR** do site
  começa outro episódio.
- **Fim de episódio — com CONTÍNUO** (`--com-loop` no arranque, ou o toggle depois): quando o episódio
  acaba (`terminated` — choque/capotamento/saída de limites — ou `truncated` — 10 s), o runner faz reset e
  **arranca já o seguinte** (ep+1, passo 0); a transição é discreta (o vento e o modo dinâmico
  atravessam-na).
- Se usares as teclas embutidas do viewer (F2 = painel de informação, F5 = fullscreen, Tab/Shift+Tab =
  painéis) aparecem UI do próprio MuJoCo — é opcional e não faz parte do padrão.

---

## 3. O SITE (todas as métricas e controlos)

Uma página, sem navegação, em duas colunas: **métricas** (esquerda, larga) e **controlos** (direita,
`sticky`). Tem um link «saltar para os controlos» para teclado. Feito com `motion-plus-ui` (React +
shadcn/Tailwind; componentes do registry `@motion`) e atualizado por **polling a `GET /api/sim` a 2,9 Hz**
(350 ms). Sem websockets.

**CONTROLO DE VOO** (contrato r11 + r12, secção «Operação» — ver §4.5 e §4.7): o painel das teclas
**WASDQE** com os keycaps a ACENDER ao vivo quando pressionados (estado otimista, imediato), armado/desarmado
explícito, o `v_ref` comandado ao instante + o eco do runner ao lado, e os erros de seguimento em cm/(m/s).
Só fica ativo com política `--comandos` (autodetetada); com política clássica diz «modo comando
indisponível» e desativa os controlos. Os `data-testid` (`controlo-voo`, `tecla-w`…`tecla-e`, `voo-ativar`,
`voo-vref`, `voo-seguindo`, `voo-indisponivel`) são os que o `teste_controle_voo.py` §4 usa na prova de
navegador. **Yaw (r12)**: 4 keycaps novos — **Z** = rodar à esquerda (`yaw_taxa` +0,5 rad/s), **C** = à
direita (−0,5), **X** = FIXAR RUMO (`yaw_alvo` = o `rumo` atual da telemetria), **V** = SEGUIR/«OLHAR»
(`segui_alvo`, o IBVS do núcleo) — com `data-testid="tecla-z|c|x|v"`, a leitura `voo-rumo` (rumo atual em
graus) e `voo-rumo-avanco` (o avanço/lateral **relativos ao RUMO** em modo clássico; no RL a nota diz que
o yaw é fixo — contrato r11). Os campos de yaw só VOAM no modo CLÁSSICO; no RL aceitam-se e validam-se,
mas o eco `"controlador"` mostra-os a zero e o painel diz «yaw livre só no modo CLÁSSICO».

**SELETOR DE CONTROLADOR** (r12, cartão «Controlador» acima do painel de voo) e **«QUEM FAZ O QUÊ»**
(tabela FC · controlador · perceção · estimador com as latências medidas/estimadas e o semáforo de
orçamento) — ver §4.7. O painel do computador de bordo (secção Bordo) mostra os **DOIS alvos possíveis**
(RPi 5 + FC H7 = build atual `endurance_15pol_p50b`; Arduino Portenta H7 + Vision Shield =
`endurance_15pol_arduino`) com os ciclos/instruções por passo, µs @480 MHz vs o orçamento de 2 ms, text/RAM
e a latência da câmara (116 ms CSI-2 do Pi vs 21 ms DCMI do Arduino).

### 3.1 Cabeçalho (topo)

| elemento | o que é |
|---|---|
| título | **«Drone a pairar · política ao vivo»** (o `<title>` da página é «Drone a pairar · política ao vivo — exp. 09»); entrada animada do registry |
| **selo de estado** | `a correr` (token `primary`, ponto a pulsar) ou `episodio_terminado` (token `destructive`, ponto fixo). `episodio_terminado` = **o episódio fechou** (z fora dos limites, passo máximo, etc.); com o LOOP desligado isso **não** quer dizer que a física parou — ela continua no estado em que ficou. O cartão **Controlos** ganha um contorno discreto e a faixa diz «episódio N terminado · sem reinício: a física continua no estado em que ficou (REINICIAR = episódio novo)» — **sem** alarme, porque nada é exigido. Com o LOOP ligado quem reinicia é o backend e a transição é neutra |
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
- **Planta real — «Entradas da rede · 21 canais»** (avaliação de UX de 2026-10-10): cada canal com um
  **nome simples** («rotação em rolamento (p)», «altura em relação ao alvo»…, o nome de código por baixo),
  o **valor** numa unidade do dia a dia (°/s, g, °, cm, cm/s, sim/não), o número **na rede** (normalizado,
  secundário) e uma **barra centrada no zero com a escala física do canal** (±60 °/s, ±0,5 g, ±20°, ±50 cm…;
  vermelha = fora da faixa) — antes era uma barra relativa ao canal mais ativo, e o acc_z ≈ 1 g achatava
  todas as outras; a dica de cada linha explica o canal. A ação real mostra o coletivo como empuxo pedido
  («0,96× o peso») e as taxas em rad/s e °/s com as faixas que o backend publica (`hardware.taxa_max`).
- **Ação · 4 canais**: o cartão descrito em §3.3 — barra do empuxo (com o traço de hover), 3 barras de
  momento em mN·m e a lista `a bruta (política)` com os 4 valores crus de `act`.

### 3.5 Controlos (coluna direita, sempre à vista)

O cartão tem o título **«Controlos»**, a nota «vento físico em tempo real · o site nunca reinicia
sozinho» e, no topo, a faixa de estado: «episódio a correr · modo contínuo (o backend reinicia ao
terminar)» / «episódio a correr · sem reinício (a física continua depois do fim)» e, no fim do episódio,
«episódio N terminado · modo contínuo: o backend arranca já o seguinte» ou «episódio N terminado · sem
reinício: a física continua no estado em que ficou (REINICIAR = episódio novo)» — as duas **neutras**.

| controlo | detalhe |
|---|---|
| **força** (slider 0–5 m/s, passo 0,1) | velocidade do vento; 0 = sem vento. O cabeçalho da secção mostra o vento atual (`agora X m/s · Y°`) |
| **azimute** (slider 0–360°, passo 1°) | direção no plano horizontal: **0° = +x, 90° = +y** (sentido anti-horário, convenção matemática) |
| **elevação** (slider −90…90°, passo 1°) | componente vertical: positivo = vento a subir, negativo = a descer |
| **rosa dos ventos** | seta polar (SVG) que mostra a direção selecionada e o comprimento pela força |
| **APLICAR VENTO** | envia `POST /api/vento {vel, azimute, elevacao}` e escreve o ficheiro de controlo; o `multi-state-button` mostra o estado (`pronto → a enviar → ok/erro`) e confirma com um toast |
| **PARAR VENTO** | **PARA TUDO num só pedido** (`POST /api/parar`, uma única escrita atómica do controlo): põe a velocidade a 0 (mantém a direção guardada) **e** desliga o vento dinâmico no mesmo instante. Depois do clique não fica nenhuma rajada ativa nem pendente — nem a one-shot a meio, nem o modo contínuo (`rajadas`/`aleatoria`/`dryden`), nem o estado do modo no env — e o `opt.wind` passa a ser exatamente o vento base comandado (0 m/s). Antes desta rota, o botão fazia só `POST /api/vento {vel: 0}`: o vento *constante* parava, mas as rajadas continuavam a atuar (era o bug «na hora de parar só paramos a última») |
| **REINICIAR** | botão **com confirmação por toque** (`hold-to-confirm`): carrega e **mantém ~1 s** (o preenchimento confirma, para não reiniciar por clique acidental) → `POST /api/reiniciar` → o episódio recomeça do zero (pousado, jitter novo, vento em vigor). A etiqueta é «REINICIAR (manter 1 s)» e é o **único reset que existe**, válido em qualquer estado (a correr, com o episódio terminado sem reinício, ou a meio) |
| **LOOP** | interruptor `segmented-toggle` com dois modos, **SEM REINÍCIO por omissão** (2026-10-09): **SEM REINÍCIO** = o backend **não reinicia nada**: no fim do episódio a física continua no estado em que ficou (nunca congela) e só o REINICIAR começa outro episódio; **CONTÍNUO** = o **backend** reinicia automaticamente no fim do episódio (ep+1, sem congelar). O interruptor segue o `loop` do backend (o arranque já corrigiu o ficheiro de controlo) e só muda por `POST /api/loop` |

Abaixo dos controlos: resumo em texto do vento em vigor e do estado do episódio.

O vento **constante** do site muda quando tu quiseres, em tempo real, mas mantém-se até ao próximo
APLICAR. Por baixo dele, a caixa **«vento dinâmico»** (`POST /api/vento-dinamico`, nunca reinicia o
episódio) tem um seletor segmentado com os modos **contínuos** — **PARADO · RAJADAS · ALEATÓRIA ·
DRYDEN** — mais dois botões instantâneos (**RAJADA AGORA** e **FRENTE AGORA**) e o **PARAR DINÂMICO**
(`{modo: "nenhum", ativo: false}`: corta a rajada one-shot em curso, desliga o modo contínuo e limpa o
estado do modo no env — rajada/turbulência/frente — deixando o vento no **vento base em vigor**; para
parar também o vento base, usa o PARAR VENTO):

| modo do seletor | params no painel | o que faz (física real, por `model.opt.wind`) |
|---|---|---|
| **PARADO** | — | desliga a dinâmica: fica só o vento constante em vigor |
| **RAJADAS** | `p` (0–1) · `duração` (1–200 passos) · `u_max` (0–5 m/s) | com probabilidade `p` começa uma rajada `U[0, u_max]` que **soma** ao vento base durante `duração` passos, com envelope `sin(π·k/(N+1))` |
| **ALEATÓRIA** | `p` (0–1) · `duração` (1–200 passos) | cada rajada re-sorteia **direção e força dentro das faixas disponíveis por inteiro** (0–5 m/s, azimute 0–360°, elevação ±90°) e é aplicada por **mistura** com o vento base pelo envelope `sin(π·k/(N+1))`: no pico do envelope o vento **é** o vector sorteado e nas pontas fica junto do base (nunca passa 5 m/s); o `u_max` não limita este modo (só `u_max = 0`, no treino, o deixa inerte) |
| **DRYDEN** | `sigma` (0,05–3) · `L` (0,5–40 m) · `v_min` (0,1–5 m/s) | turbulência OU de 1.ª ordem que passeia em torno do vento base |

Os mesmos modos existem no **ambiente e no treino** (`env.HoverEnv(vento_dinamico=…)`,
`train.py --vento-dinamico rajadas|aleatoria|frente|dryden`); o `out/controle_vento.json` guarda o bloco
`dinamico` (`{modo, params, ativo, seq}`) que o runner aplica ao env. Ver `README.md` §«Vento dinâmico
(r10)».

Nos modos contínuos, **editar um campo do painel aplica-se sozinho** (live-apply): passados ~300 ms sem
novas edições, o site reenvia o modo em vigor com os params atuais (`POST /api/vento-dinamico`, com o
mesmo contrato `{modo, ativo: true, params}` da troca de modo — o episódio nunca reinicia). Ao abrir a
página com um modo já a correr, o painel adota os params que o backend anuncia em vez de impor os
defaults; com PARADO os valores ficam só guardados e vão no POST da próxima ativação.

**Nenhuma rajada sobrevive ao PARAR** (correção do bug «na hora de parar só paramos a última»): o PARAR
DINÂMICO e o PARAR VENTO passam ambos pelo `Controlo._para_dinamica`, que corta o slot da rajada one-shot,
reescreve em `opt.wind` o vento base do controlo **em vigor** (é a fonte; o `PARAR VENTO` manda-o a 0) e
desliga o modo do env — o `env.definir_vento_dinamico(None)` limpa o estado do modo (rajada/turbulência/
frente) e volta a escrever o vento base, mesmo que o modo já estivesse desligado. Antes, o PARAR VENTO
escrevia só `{vel: 0}` e o bloco `dinamico` ficava intacto: as rajadas do modo contínuo e a one-shot a
meio continuavam a atuar (a telemetria continuava a mostrar `vento_modo = rajadas|rajada_agora|…`), e o
restauro do vento base usava o registo ANTERIOR do controlo. A prova repetível está em
`teste_parar_vento.py` (**15/15** verificações sem flags — os cenários/ciclos do PARAR no ciclo real do
runner mais a prova de concorrência in-process —, **16/16** com `--http` e **18/18** com
`--http --navegador`; o mesmo teste aceita `--legado REV` para correr contra o código de uma revisão
antiga).

**Bloco «Câmara da janela 3D»** (secções **Operação** e **Tudo**; v3 de 2026-10-10, avaliação de UX em
`out/ux/`) — move a câmara da **janela 3D** a partir do site (é **só apresentação**: nunca toca na física,
no episódio nem em nenhum comando de vento/loop). A câmara é **TERCEIRA-PESSOA CONTÍNUA** (contrato v2):
o alvo é **sempre o drone** — o runner escreve `viewer.cam.lookat = body(CAM_CORPO).xpos + CAM_OFFSET`
**a cada frame** (`seguir_drone`, §4.4) — e o site escolhe **de onde** se olha:

| elemento | detalhe |
|---|---|
| **leitura** «onde · altura · distância» | em português, relativa ao NARIZ do drone: «atrás, à direita · 35° por cima · 1,95 m» |
| **vista de cima** | o drone de cima com o **nariz para cima** (frente/trás/esquerda/direita do drone, pelo rumo real `verdade.yaw`) e o ícone da câmara **onde ela está**, com o cone de visão a apontar ao drone; arrastar/clicar põe a câmara noutro ponto da volta (azimute: a câmara fica em −(cos a, sin a) do drone, `pos = alvo − d·f`); ↺/↻ = ±15° |
| **vista de lado** | o drone de perfil e a câmara num arco: arrastar sobe/desce (ângulo acima do horizonte = −elevação, de −30° a 89°); o **chão à escala** (altura do drone ÷ distância) e o ícone a vermelho com aviso se a câmara ficar abaixo do chão; ▲/▼ = ±10° |
| **zoom** | slider **logarítmico** com −/+ (×1,25) e a **roda do rato** sobre as vistas; limites por planta: drone real 0,6–15 m, Crazyflie 0,1–5 m (o contrato aceita até 20 m) |
| **vistas rápidas** | Atrás (perseguição) · Frente · Esquerda · Direita · De cima · À altura — relativas ao rumo real do drone, mantêm o zoom; **Repor vista** = enviar o `camera_padrao` como um comando normal |
| **teclado** | com o foco numa vista: ← → orbitam, ↑ ↓ sobem/descem, + − zoom, Home repõe; as teclas 1–5 das secções continuam a funcionar (as vistas têm `data-atalhos-livres`) |
| estado | selo «sincronizada / a enviar / a aplicar / aplicada / falhou / sem janela 3D»; durante um gesto o widget é otimista e a telemetria nunca o sobrescreve; fora dele segue a câmara REAL (inclusive o rato da janela); sem viewer (`camera_atual: null`) o bloco diz porquê e desativa-se |
| envio | `POST /api/camera {azimute, elevacao, distancia}` — o site manda SEMPRE os **3 valores** do estado mostrado (ao vivo durante o gesto, 1 comando a cada ~150 ms com coalescência, + o final ao largar; vistas rápidas e Repor enviam já). O contrato continua a aceitar **subconjuntos** (sem `alvo`, sem `seq` — o servidor incrementa-o) e completa os campos em falta com o bloco em vigor ou, sem bloco, com o `camera_padrao` **do modelo em uso** |
| detalhes técnicos | recolhidos: azimute/elevação/distância exatos, alvo e posição da câmara, a convenção do MuJoCo e o envio |

Correções de 2026-10-10 (medidas no ecrã real, Xvfb + Chrome headless): (1) um comando só com ângulos era
completado no servidor com a distância do **Crazyflie (0,27 m)** no 1.º comando da sessão e a câmara do
drone real saltava para dentro dele — agora o site manda o corpo completo e o servidor completa com o
`camera_padrao` do modelo em uso; (2) um zoom feito com o rato na janela deixou de ser desfeito pelo
comando seguinte do site (o corpo completo leva a distância REAL mostrada).

O runner aplica cada bloco `camera` ao `viewer.cam` **UMA VEZ por mudança de assinatura (`seq`+valores)**:
reescrever o ficheiro com o mesmo bloco (ex.: uma mudança de vento) **não** re-aplica a câmara — por isso
uma arrastadela do rato na janela sobrevive até ao próximo comando de câmara (**ângulos/distância livres
ao rato entre comandos**). O que o rato NÃO guarda é o **PAN**: o `lookat` é reescrito pelo `seguir_drone`
a cada frame (**o PAN é intencionalmente sobreposto** — num orbitar 3ª-pessoa o alvo não sai do drone).
A **câmara real** publica-se em cada amostra da telemetria (chave `camera`, §4.2 — `alvo` = `lookat` real =
drone+offset) e sai como `camera_atual` na API; o default (`camera_padrao`) é a constante `CAM_PADRAO` =
`{azimute, elevacao, distancia}` (sem `alvo`) — os 3 valores de `mjv_defaultFreeCamera(model)`, aplicados
também no arranque do runner (§4.4).

### 3.6 Estados e avisos

| estado | o que aparece |
|---|---|
| **a carregar** | esqueleto (skeleton) nos cartões até chegar a primeira linha |
| **sem dados** | mensagem «o servidor responde mas ainda não publicou passos: as curvas e a rede ficam vazias até o episódio arrancar.» |
| **API em baixo** | selo `API em baixo` + banner vermelho; valores a «—»; os POSTs falham com toast legível |
| **ações** | pilha de **toasts** (canto): vento aplicado/parado, episódio reiniciado (com o nº do contador do servidor), LOOP ligado («modo contínuo») / desligado («sem reinício: a física continua no estado em que ficou; só o REINICIAR recomeça»), erros da API |
| **400** | corpo ou valores fora das faixas → o servidor devolve `{"erro", "codigo"}` e o toast diz o motivo |
| **404** | rota `/api/*` desconhecida, asset em falta ou `path traversal` → 404 explícito |
| **500** | falha inesperada no servidor → 500 (nenhum pedido mata o servidor) |

### 3.7 Paragem fiável e comandos concorrentes (a garantia do «quando paro, tem de parar tudo»)

O PARAR tem de valer mesmo quando o clique cai em cima de outro pedido ou de um apply agendado. Duas
falhas de fiabilidade foram fechadas (nenhuma delas era regressão da correção do PARAR — são defeitos
pré-existentes que faziam o PARAR falhar no uso real):

**(1) POSTs concorrentes — 500 no meio da rajada.** O servidor é um `ThreadingHTTPServer` (uma thread por
pedido) e a escrita atómica do controlo usava um temporário com nome **partilhado por todas as threads**
(`.{nome}.tmp{pid}`): dois POSTs simultâneos escreviam no mesmo ficheiro e o segundo `os.replace` falhava
com `FileNotFoundError` → **HTTP 500** (`{"erro":"erro interno: [Errno 2] … .ctl.json.tmp<pid>"}`). O
ficheiro nunca ficava meio-escrito, mas um PARAR que devolve 500 **não para rajada nenhuma**. Agora:

- o temporário tem nome **único por escrita** (`nome_temporario`: pid + thread + contador monotónico) —
  dois pedidos nunca disputam o mesmo nome;
- cada pedido faz o seu **ler-modificar-escrever sob a mesma trava** (`trava_controlo`): sem ela, dois
  pedidos podiam ler o mesmo estado e o último a escrever revertia o outro (um REINICIAR a perder o
  incremento por causa de um POST de vento concorrente, ou um PARAR revertido por um vento);
- falha de escrita **não deixa `.tmp` órfãos** (o temporário é apagado antes de a exceção subir);
- `loop` e `reiniciar` continuam a nunca ser inventados por uma escrita parcial (§4.1).

À fiabilidade junta-se a **fila de ligações** do próprio `listen()`: o `ThreadingHTTPServer` do stdlib usa
`request_queue_size = 5` e, num **burst frio de 40 ligações simultâneas** (o dono a mandar vários comandos
de uma vez para um servidor que ainda não recebeu pedidos), as ligações que não cabiam ficavam **por
servir** — `ConnectionResetError`/silêncio do lado do cliente e POSTs que nunca chegam (medido com o código
de antes: 26–39 de 40 servidos por ronda, e as que passavam podiam demorar segundos em retransmissões).
O `sim_site.py` serve com `FILA_LIGACOES = 64` (`ServidorHTTP`) — folga para o burst de 40 provado no
`teste_camera.py` (§3: 40 ligações × 3 rondas, 120/120 POSTs servidos e aplicados).

**(2) Corrida do debounce do front — o modo voltava a ligar-se depois do PARAR.** O live-apply dos params
(§3.5) é um `setTimeout` de ~300 ms que só era cancelado quando o `modoContinuo` mudava — e isso depende
do **polling** (350 ms) mais o ida-e-volta do `POST /api/parar`. Um clique dentro dessa janela deixava
sair `{modo:"rajadas", ativo:true, params}` **depois** da paragem, e o servidor+runner honravam-no: o modo
voltava a `rajadas` depois de PARAR. Agora há duas guardas no cliente (`site/src/lib/paragem.ts` +
`use-sim.ts`), porque a paragem tem de ganhar **sempre**:

- **época de paragem**: cada PARAR VENTO incrementa um contador de forma **síncrona** no clique (antes de
  qualquer `await`). O apply agendado guarda a época do agendamento e confere-a ao disparar — época
  diferente = o apply é **descartado sem chegar à rede**. Não depende do polling nem de o React já ter
  re-renderizado o painel;
- **fila de POSTs**: os pedidos de controlo saem **um de cada vez, pela ordem em que foram pedidos**, logo
  o `POST /api/parar` é sempre a **última escrita** no ficheiro — um apply que já estava em voo no instante
  do clique assenta antes dele e não pode ressuscitar o modo;
- o painel não anuncia sucesso de um apply que perdeu a corrida (a época é conferida também na resposta).

Prova repetível (um comando, exit code):

```bash
# os dois defeitos: ~100 pares de POSTs concorrentes + a corrida do front, contra o servidor real
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_parar_vento.py --http --navegador
# defeito (1) contra as fontes de ANTES (a cópia pré-fix pode estar fora do repo): FALHA (59/120 escritas)
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_parar_vento.py --sem-cenarios \
    --fontes "$TMPDIR/antes-do-reparo/fontes"   # pasta com env.py · sim_view.py · sim_site.py
# defeito (2) contra o front de ANTES (compila com essas fontes, corre e repõe): FALHA nas janelas 0/50 ms
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_parar_vento.py --navegador \
    --front "$TMPDIR/antes-do-reparo/front"     # pasta com controlos.tsx · use-sim.ts · App.tsx
```

A prova do navegador liga o modo RAJADAS, **edita um param** (o que agenda o apply), espera a janela
pedida (**0/50/300/600 ms**) e clica PARAR VENTO, amostrando o estado do servidor durante 2,6 s com o poll
do site a correr: a partir da primeira amostra em `nenhum`, nenhuma pode voltar a um modo ativo e a
telemetria tem de acabar em `vento_modo=nenhum` com vento 0. Cada janela corre também **sem** o PARAR
(controlo positivo) — aí o apply tem de aparecer com o `p` novo, o que prova que o teste veria um apply
atrasado se ele existisse. O teste imprime ainda os **POSTs que o front mandou**, com o instante de cada um
relativo à edição: é aí que se vê o defeito (`/api/parar` aos 4 ms e `/api/vento-dinamico` aos 300 ms no
código de antes) e a correção (nenhum POST dinâmico depois do PARAR).

Com o poll **instantâneo** do loopback a janela do defeito tem só ~10 ms (o cancelamento chega antes de o
temporizador disparar) e o defeito escapa quase sempre; por isso o teste atrasa a **resposta** do
`GET /api/sim` em `--atraso-poll` (padrão 500 ms) nos cenários do PARAR — o que é fiel ao que acontece
nesta máquina: com a telemetria no teto de 4 MB que o `/api/sim` lê do fim, o pedido custa ~65 ms só de
parsing (medido), o site faz o poll a cada 350 ms e o runner compete pelo GIL. Com o poll lento a janela
deixa de ser de milissegundos e o defeito é determinístico. Os controlos correm com o atraso desligado
(para o painel estar em dia e a edição agendar mesmo o apply).

---

## 4. Os ficheiros por baixo (o que liga site ↔ simulação)

### 4.1 `out/controle_vento.json` — o site escreve, o runner lê **a cada passo de decisão**

```json
{"vel": 0.0, "azimute": 90.0, "elevacao": -10.0, "ativo": false, "reiniciar": 2, "loop": false,
 "camera": {"azimute": 30.0, "elevacao": -15.0, "distancia": 3.0, "seq": 4},
 "t": 1791502694.35}
```

| campo | significado |
|---|---|
| `vel` | velocidade do vento, 0–5 m/s |
| `azimute` | direção horizontal, 0–360° (0° = +x, 90° = +y) |
| `elevacao` | componente vertical, −90…90° |
| `ativo` | `false` ⇒ vento **0** na física (a direção/força ficam guardadas para o próximo APLICAR) |
| `reiniciar` | **contador inteiro**. Quando **muda**, o runner faz `env.reset()` — é o ÚNICO caminho para recomeçar um episódio (não há auto-reset fora do `loop`). A 1.ª leitura é linha de base; um contador ≥1 que apareça sem ficheiro prévio conta como reinício já pedido. Uma escrita **parcial** (sem esta chave) **não** mexe no contador e por isso não dispara reset nenhum |
| `loop` | `true` = **CONTÍNUO** (o runner reinicia sozinho no fim do episódio, ep+1); `false` = **SEM REINÍCIO** (a física continua no estado em que ficou — não congela — e só um REINICIAR recomeça); **campo ausente = não mexe** (um ficheiro antigo só com vento continua válido). É **STICKY** e o **padrão é `false`** (2026-10-09): o ARRANQUE é autoritativo e **corrige o ficheiro** — sem flag (ou com `--sem-loop`) um `loop: true` velho passa a `false`, e com `--com-loop` um `loop: false` velho passa a `true` — preservando vento, dinâmica e o contador `reiniciar`; depois do arranque, quem o muda é só o `POST /api/loop`. Escritas parciais nunca lhe tocam |
| `camera` | bloco **`{"azimute", "elevacao", "distancia", "seq"}`** — o comando de ORBITAR/zoom da câmara 3D (só apresentação: **nunca** toca na física nem nos outros campos). **SEM `alvo`** (contrato v2: o alvo é SEMPRE o drone — o `seguir_drone` escreve o `lookat = body(CAM_CORPO).xpos + CAM_OFFSET` a cada frame, §4.4). Faixas: `azimute` finito (normalizado **mod 360**), `elevacao` ∈ [−90, 90]°, `distancia` ∈ ]0, 20] m (a UI usa 0,1–10); `seq` inteiro ≥ 0, **incrementado a cada comando** pelo servidor (como o `dinamico.seq`) — a assinatura do bloco (`seq`+valores) é o que faz o runner **(re)aplicar UMA vez** os 3 valores ao `viewer.cam` (§4.4). Bloco ausente = não mexe na câmara; bloco com campos em falta/fora de faixa → o registo é ignorado com aviso (como o `dinamico`); **chaves desconhecidas** (ex. o `alvo` de ficheiros v1) são **ignoradas em silêncio** — ficheiros velhos não rebentam (o `POST /api/camera` é que as recusa com 400: a assimetria é intencional). O bloco é sempre COMPLETO (os 3 valores): quem o escreve é o `POST /api/camera` (que completa os campos **ausentes** a partir do bloco em vigor e carimba o `seq`; um campo **presente com valor `null`** é recusado com **400** — `null` não é «ausente») ou a mão |
| `voo` | bloco **`{"ativo", "teclas": {"w","a","s","d","q","e"}, "yaw_taxa"?, "yaw_alvo"?, "segui_alvo"?, "seq"}`** — o CONTROLE DE VOO (contratos r11 + r12, §4.5/§4.7): o **estado** das 6 teclas WASDQE, escrito COMPLETO a cada keydown/keyup do site. `W = +x (frente)`, `S = −x`, `A = +y (esquerda)`, `D = −y (direita)`, `Q = subir`, `E = descer` (frame **mundo** no RL; relativo ao **RUMO** no modo clássico); diagonais normalizadas para 1,0 m/s, `|vz| = 0,7 m/s`; `ativo: false` (ou teclas soltas) ⇒ `v_ref = 0` = o drone **segura posição**. **r12 (opcionais — ausência = defaults, um ficheiro r11 continua válido; o servidor escreve o bloco completo)**: `yaw_taxa` (rad/s, finito em [−2, 2] — teclas Z/C mandam ±0,5), `yaw_alvo` (**`null`** = sem alvo, que é um VALOR; ou rumo em rad **desde o armar**, normalizado a ]−π, π] — tecla X) e `segui_alvo` (booleano — tecla V = «olhar», o IBVS do núcleo segue o círculo). `seq` inteiro ≥ 0 incrementado a cada comando pelo servidor; o runner aplica o bloco UMA vez por mudança de assinatura. Bloco ausente = não mexe no comando; teclas em falta valem `false`; chaves desconhecidas **ignoradas em silêncio** no ficheiro (o `POST /api/voo` é que as recusa com 400). Só faz efeito com **política `--comandos`** (modo comando detetado pela observação da política): com política clássica o runner ignora o bloco com aviso e a telemetria publica `"voo": null` — o site mostra o painel como **indisponível** em vez de fingir que pilota. Os campos de yaw aplicam-se só no **modo clássico** (a política r11 mantém o rumo fixo) |
| `controlador` | bloco **`{"modo": "rl"|"classico", "seq"}`** — o SELETOR DE CONTROLADOR (r12, §4.7): `modo` é obrigatório e restrito aos dois valores (outro → o registo é ignorado com aviso, como os outros blocos) e `seq` inteiro ≥ 0 incrementado a cada `POST /api/controlador`. O runner troca de controlador quando o `modo` MUDA (reescrever o mesmo bloco não re-dispara). Bloco ausente = não mexe no modo em vigor |
| `fpv` | bloco **`{"ligada", "modo", "seq"}`** — o MÓDULO DE CÂMARA FPV de bordo (§4.6): `ligada` booleana (a alimentação/streaming do módulo) e `modo` = id de um modo EMULADO da tabela real (`1080p50` por omissão, `720p100`, `480p120`, `2304x1296p56`, `1536x864p120`, `4608x2592p14`; o HDR existe no hardware mas **não é emulado** e é recusado). `seq` inteiro ≥ 0 incrementado a cada comando pelo servidor. Bloco COMPLETO (`ligada` + `modo`) — quem o escreve é o `POST /api/fpv` (que completa o que não vem a partir do bloco em vigor e carimba o `seq`) ou a mão; o runner aplica UMA vez por mudança de assinatura. Bloco ausente = não mexe no módulo; chaves desconhecidas ignoradas em silêncio no ficheiro (o POST recusa-as com 400) |
| `t` | carimbo de tempo da escrita (informativo; o site e o runner carimbam-no quando escrevem) |

Todas as escritas são **atrónicas** (ficheiro temporário + `os.replace`), portanto o runner nunca lê um
ficheiro meio escrito. Escrever à mão também funciona (é um contrato de ficheiro): o runner vê pela
assinatura `mtime_ns + tamanho`. As escritas do site fazem **merge sobre o que o ficheiro já tem** — uma
escrita parcial (vento, vento dinâmico) **nunca** reescreve `loop` nem `reiniciar` com valores por omissão.
O temporário tem **nome único por escrita** (pid + thread + contador) e cada pedido faz o seu
ler-modificar-escrever sob a **mesma trava**: POSTs simultâneos não se atropelam nem se revertem (§3.7).
O bloco **`dinamico`** (`{"modo", "params", "ativo", "seq"}`) é o vento ao vivo: cada pedido a
`/api/vento-dinamico` incrementa o `seq` (é a assinatura que o runner compara para (re)agir). O
**PARAR VENTO** (`POST /api/parar`) é a exceção deliberada: numa só escrita põe `vel` a 0 (`ativo: false`)
**e** o bloco em `{"modo": "nenhum", "params": {}, "ativo": false, "seq": n+1}` — depois dela não fica
nenhuma rajada ativa nem pendente e o vento aplicado é exatamente o vento base comandado.

### 4.2 `out/sim_telemetria.jsonl` — o runner escreve, o site lê

Uma linha JSON por amostra (**15 campos** + os aditivos `loop`, `vento_modo`, `ctrl` e `camera` =
**19 chaves**, e depois mais aditivos: `planta`, `fim`, `voo`, **`fpv`** (módulo de câmara de bordo) e, na
planta real, os blocos de bordo e a `verdade`): **~10 Hz sempre** (com o episódio a correr ou já terminado
— não há batimento lento); e
**uma linha imediata** no instante em que o episódio termina e em cada REINICIAR.

| campo | significado |
|---|---|
| `t` | tempo de **simulação** do episódio (s); volta a 0 em cada reset. Com SEM REINÍCIO continua a crescer depois do fim do episódio (é a prova de que a física não parou nem reiniciou) |
| `estado` | `a_correr` ou `episodio_terminado`. **Mudança de semântica (ronda 11)**: `episodio_terminado` diz que o EPISÓDIO fechou e não houve reinício — **não** que a física parou (com SEM REINÍCIO ela continua a integrar no estado em que ficou) |
| `ep` | número do episódio (1, 2, 3… a cada REINICIAR ou auto-reset) |
| `passo` | passo de decisão dentro do episódio (0–500; 50 Hz ⇒ 10 s por episódio). Sem reinício continua a crescer para lá dos 500 (o `env.passos` só volta a 0 num `reset`) |
| `retorno` | recompensa v2b acumulada até aqui. Sem reinício **congela** no valor com que o episódio fechou (não se somam recompensas de um episódio que já acabou) |
| `z` | altitude do CM (m) — alvo 1,0 |
| `dist_xy` | distância horizontal ao ponto de referência (m) |
| `yaw_err` | erro de orientação (rad) |
| `vento_vel`, `vento_azim` | vento **em vigor na física** (m/s, graus) |
| `obs` | 16 números — a observação que entrou na rede (normalizada) |
| `act` | 4 números — a ação que a rede mandou (média crua) |
| `ctrl` | 4 números — o comando **físico** que essa ação produziu: `data.ctrl` = [empuxo N, momento x, momento y, momento z (N·m)]. Invariante: `ctrl == acao_para_ctrl(act)` quando `passo > 0` (ação aplicada); nas linhas de reset (`passo == 0`, `t == 0`) vale `[0,0,0,0]`, porque o `env.reset()` zera o `data.ctrl` e não houve ação nenhuma. É este campo que o site rotula **«ctrl do backend»** (§3.3); sem ele, o site deriva da ação |
| `h1`, `h2` | 64 + 64 ativações das camadas escondidas (forward hooks nos `nn.Linear`), **na mesma linha** que `obs`/`act`/`ctrl` ⇒ alinhadas |
| `camera` | **19.ª chave** (sempre no fim): a câmara **REAL** da janela, `{"azimute", "elevacao", "distancia", "alvo": [x,y,z]}` lida de `viewer.cam` — inclui arrastos do rato feitos entre comandos. O `alvo` é o **`lookat` real = drone+offset** (escrito pelo `seguir_drone` a cada frame, §4.4 — sem lag). **`null` sem viewer** (`--sem-janela`, testes): sem dados não se inventa câmara (é o que sai em `camera_atual` na API) |
| `fpv` | aditivo (2026-10-11): o **MÓDULO DE CÂMARA FPV de bordo** (§4.6), compacto — `{ligada, modo, saida, fps_nominal, fps_medido, bytes_medio, bitrate_mbps, quadros, latencia_ms, cpu_nucleos, host_ms}`. `cpu_nucleos` é o MODELO do Pi 5 (fontes no `lab/camera_rpi`) e `host_ms` é o MEDIDO nesta máquina — nunca misturados. **`null` sem módulo** (modelo sem câmara ou `--sem-fpv`): nunca se inventa uma câmara. A configuração completa fica em `out/fpv/estado.json` e na API |
| `voo` | **chave aditiva** (contrato r11, §4.5): o CONTROLE DE VOO em vigor = `{"ativo", "teclas": {w,a,s,d,q,e}, "v_ref": [vx,vy,vz], "p_ref": [x,y,z], "erro_xy", "erro_z", "erro_v", "seguindo"}` — o que se pediu (`v_ref`/`p_ref`, em m/s e m), o que se apanhou (erros: `erro_xy`/`erro_z` em m, `erro_v` = ‖v − v_ref‖ em m/s) e se o drone está a seguir a referência (`seguindo`, os limiares do bónus). **`null` quando a política em uso NÃO tem modo comando** — é o que faz o painel do site ficar honestamente indisponível em vez de fingir que pilota |
| `controlador` | **chave aditiva (r12, §4.7)**: quem pilota + o estado do yaw/olhar = `{"modo", "fonte", "yaw_taxa", "yaw_alvo", "segui_alvo", "v_ref_fonte", "pedido", "estado", "motivo", "rumo", "olhar"}` — `modo` é o EM VIGOR (eco do runner), `pedido` o que foi pedido, `estado` a honestidade (`pronto` · `trocando` · `erro`) com o `motivo`; `rumo` = ψ desde o armar (rad — é o que a tecla X fixa); `olhar` = `{"valido", "u_px", "v_px", "raio_px", "erro_px", "estado", "alvo_mundo"}` (alvo na imagem do IBVS, convenção ÍNDICE; `erro_px` = offset face ao centro — «alvo centrado» = erro ≈ [0,0] — e `alvo_mundo` = a posição do alvo mocap, que descreve o círculo), **`null` quando o «olhar» nunca ligou**; sem deteção válida os campos do alvo vêm `null` (o detetor devolve zeros quando não vê nada — não se mostra isso como deteção). No modo RL os campos de yaw vêm a zero/`null` (a política mantém o rumo fixo) |

Cada linha é escrita com `flush`, para o site ver sem esperar pelo fecho do ficheiro.

### 4.3 A API (16 rotas `/api/*` + os ficheiros do site, JSON, local — `POST /api/bateria` é da planta real: §7; as 4 do módulo FPV são da §4.6; `POST /api/voo` e `POST /api/controlador` são da §4.5/§4.7)

| rota | resposta |
|---|---|
| `GET /api/sim` | `{"estado","ep","passo","retorno","vento":{vel,azimute,elevacao,ativo},"modelo","modelo_nome","camera_padrao","camera_atual","linhas":[…]}` com as **≤200** últimas amostras da telemetria |
| `GET /api/state` | resumo: `sim_vivo`, `pid`, `porta`, `controlo`, `telemetria`, `amostras`, `idade_telemetria_s`, `site_pronto`, `loop`, `reiniciar`, **`modelo` + `modelo_nome`**, **`camera_padrao` + `camera_atual`**. **Não** anuncia hoje as constantes físicas (`mg`, `thrust_max`, `momento_max`, `tau_escala`): o site usa os valores de recurso `FISICA_PADRAO` |
| `POST /api/vento` | `{"vel","azimute","elevacao"}` (qualquer subconjunto; faixas 0–5 / 0–360 / −90..90; NaN/inf → **400**) → escreve o controlo e responde `{"ok": true, "vento": {…}}` |
| `POST /api/vento-dinamico` | `{"modo", "params"?, "ativo"?}` → liga/desliga/reconfigura o vento **dinâmico** ao vivo (`nenhum\|rajadas\|aleatoria\|frente\|dryden\|rajada_agora`), sem reiniciar o episódio; `seq` incrementado a cada pedido (é o que permite disparar duas rajadas iguais seguidas). Os modos do env são validados pelo próprio `env.py` (400 com o motivo); `frente` aceita `{vel,azimute,elevacao}` (degrau imediato do vento base) ou `{u_max,t_s}` |
| `POST /api/parar` | **PARAR VENTO** numa só escrita atómica: `vel` a 0 (mantém azimute/elevação, `ativo: false`) **e** bloco `dinamico` em `nenhum` com `seq` novo → responde `{"ok": true, "vento": {…}, "vento_dinamico": {…}}`. Depois dele não fica nenhuma rajada ativa nem pendente e o `opt.wind` é exatamente o vento base comandado (0 m/s). Não leva corpo |
| `POST /api/reiniciar` | incrementa `reiniciar` → `{"contador": n}`: reset **manual** e ÚNICO — válido em qualquer estado (a correr, com o episódio terminado sem reinício, ou a meio) |
| `POST /api/loop` | `{"ativo": bool}` → liga/desliga o contínuo (`false` = SEM REINÍCIO: a física continua no fim do episódio; só um REINICIAR recomeça) e responde `{"ok": true, "loop": bool}`. É a única forma de mudar o `loop` depois do arranque |
| `POST /api/camera` | `{"azimute","elevacao","distancia"}` (qualquer subconjunto; **SEM `alvo`** — a câmara é TERCEIRA-PESSOA e o alvo é sempre o drone — e **SEM `seq`**: o **servidor** incrementa-o a cada pedido, como o `dinamico.seq`; o alias **`distandia`** é aceite e mapeado para `distancia`, mas os dois juntos → 400) → orbita/zooma a câmara da janela 3D (só apresentação) e responde `{"ok": true, "camera": {…, "seq": n}}`. Faixas: azimute finito (mod 360), elevacao [−90,90]°, distancia ]0,20] m; fora → **400** com o motivo. **Regras de validação exatas**: campo **presente com valor `null` → 400** (`null` não é «ausente»: só a AUSÊNCIA do campo completa do bloco em vigor); **chave desconhecida** (incl. o `alvo` do contrato v1) → **400** (`camera` tem chaves desconhecidas […]); **`{}` e `{"seq": n}` são ACEITES com 200** (decisão v2: subconjunto vazio é um «toque» que mantém os valores e carimba `seq` novo, e o `seq` do corpo é um aviso do cliente **IGNORADO** — o servidor carimba sempre o seu; aceitar `{"seq": …}` deixa reenviar um bloco lido tal e qual). Escreve o bloco por merge (`escrever_controlo`): **nunca** toca em `loop`/`reiniciar`/vento/dinâmica. O runner aplica-o ao `viewer.cam` **1x por mudança de assinatura** (só os 3 valores — o `lookat` é do `seguir_drone`) e sem viewer ignora sem erro |
| `GET /` e `/assets/...` | o site (`site/dist/`); qualquer caminho desconhecido cai no `index.html`; path traversal → **404** |
| `GET /api/fpv.mjpg` | **stream MJPEG** do módulo de câmara FPV (§4.6): `multipart/x-mixed-replace`, partes `image/jpeg`, `Cache-Control: no-cache`; só o ÚLTIMO quadro (clientes lentos perdem frames em vez de acumular atraso); cada parte traz `X-Fpv-Seq`/`X-Fpv-Captura-Ms` |
| `GET /api/fpv.jpg` | o último quadro como imagem única (404 sem quadro) |
| `GET /api/fpv/estado` | `{"fpv": <estado do módulo>}` ou `{"fpv": null}` sem módulo |
| `POST /api/fpv` | `{"ligada"?, "modo"?}` (subconjunto; `seq` do servidor; `modo` = id EMULADO da tabela real; modo HDR/nada/chave desconhecida → **400**) → `{ok, fpv: {ligada, modo, seq}}`; escreve o bloco `fpv` por merge (nunca toca nos outros campos) |
| `GET /api/simulacao.mjpg` | **stream MJPEG** da CÂMARA DA SIMULAÇÃO (vista 3.ª-pessoa; mesmo padrão multipart do FPV, `X-Simulacao-Seq`) — a segunda fonte do bloco «Câmara FPV» do site |
| `GET /api/simulacao.jpg` | o último quadro da simulação (404 sem quadro) |
| `GET /api/simulacao/estado` | estado do módulo da simulação (com `estado_velho`); `custo_pi5: null` — não é hardware de bordo |

> **`multi_ia`** (mecanismo multi-IA de bordo, `multi_ia.py`): a telemetria publica a chave aditiva
> `"multi_ia"` = `{ias: [{nome, papel, taxa_hz, ativo, estado, n_inferencias, latencia: {p50_us,
> p99_us, …}, ultima_obs, ultima_acao}], v_ref_fonte, aviso, fc, latencia_total_us, periodo_us}` —
> `/api/state` publica-a em `multi_ia` e o custo no painel em `rpi5.multi_ia` (semáforo
> OK/ATENCAO/ERRO: p99 da soma das IAs vs o período de 20 ms; o FC 500 Hz NÃO é IA e não entra na
> conta). MECANISMO ESCOLHIDO: via TELEMETRIA (como o `fpv`) — sem ficheiro extra. `null` quando não
> há cascata (nada se inventa).

> **Honestidade da fonte `simulacao`**: entrega **imediata** (sem a latência do pipeline Pi — não é
> hardware de bordo, e aplicar-lhe o atraso de um módulo Pi seria mentir) e `custo_pi5: null`; só o
> `host_ms` medido se aplica. **Orçamento de host**: os DOIS streams a 1080p50 não sustentam 50 fps cada
> num host carregado (27–46 fps medidos; ~43 a PC livre) — é contenção de CPU/GPU do PC, não do módulo
> (a fidelidade ±10 % da taxa prova-se com o módulo isolado; ver `teste_fpv.py` §3).

`camera_padrao` = os valores da constante `CAM_PADRAO` = `{azimute, elevacao, distancia}` (**SEM `alvo`** —
o alvo é sempre o drone; §4.4) — o **REPOR VISTA** do site manda-os como um comando normal de
`POST /api/camera`. `camera_atual` = a câmara REAL da última amostra da telemetria (`null` sem viewer/sem
amostras — nunca um valor inventado).

### 4.4 Convenção de sinais ângulo→direção (câmara livre do MuJoCo) — o front tem de copiar ESTA fórmula

A câmara livre (`viewer.cam`, `mujoco.MjvCamera`) é definida por `lookat` (`alvo`), `distance`
(`distancia`), `azimuth` e `elevation`; a **posição da câmara no mundo** que daí resulta é:

```
pos = alvo − d · f(azim, elev)          ⇔          alvo = pos + d · f(azim, elev)
f(azim, elev) = [ cos(elev)·cos(azim), cos(elev)·sin(azim), sin(elev) ]     (azim, elev em RADIANOS)
```

- **`azimute` 0°** ⇒ a câmara olha para **+x**; **90°** ⇒ para **+y** (rotação anti-horária vista de
  cima — a MESMA convenção do vento); acrescentar 360° não muda a pose (o contrato normaliza mod 360);
- **`elevacao` positiva** põe a câmara **ABAIXO** do alvo a olhar para **cima** (`f_z = sin(elev) > 0` ⇒
  `pos_z = alvo_z − d·sin(elev)`); **−90°** = câmara por cima do alvo a olhar para baixo; o default −20°
  põe a câmara ligeiramente por cima a olhar para baixo;
- **`distancia`** = `‖pos − alvo‖` (o zoom), e o `alvo` é o ponto do mundo para onde a câmara olha;
- **em TERCEIRA-PESSOA (contrato v2) o `alvo` NÃO é comandado**: o runner escreve
  **`lookat = body(CAM_CORPO).xpos + CAM_OFFSET` a cada frame** (`sim_view.seguir_drone`) — colagem
  exacta e sem lag (provada escrita a escrita no `teste_camera.py` §2). `CAM_CORPO = "cf2"` é o corpo do
  drone (acesso por NOME) e `CAM_OFFSET = (0, 0, 0)` m é somado elemento a elemento a `xpos` (com o offset
  nulo de hoje o alvo é o centro exato do corpo); `CAM_OFFSET`/`CAM_CORPO` são constantes do `sim_view.py`,
  documentadas e testadas. A posição da câmara que se vê é então `pos = (drone+offset) − d·f` — a fórmula
  acima com `alvo` = drone+offset. O **PAN do rato** (mudar o `lookat` na janela) é **sobreposto** por este
  seguimento no frame seguinte; já os ângulos e a distância do rato **sobrevivem** até ao próximo comando.

**Como foi confirmada** (`teste_camera.py` §1, uma checagem): para 6 poses (0°/90°/37°/123°/300°/271,5°,
elevações de −89° a +60°, distâncias 0,4–7 m) a posição real dada pelo MuJoCo — média dos **dois olhos
estéreo** de `MjvScene.camera` após `mjv_updateScene` (`camera[0]` isolado traz o desvio do olho esquerdo)
— bate com `alvo − d·f` com desvio máximo **5,7e-8 m** (float32 do `mjvGLCamera`). A doc oficial
(`docs/upstream/mujoco/doc/programming/visualization.rst`) descreve a câmara livre como `lookat` +
`distance` + `azimuth` + `elevation`, sem torção em torno do eixo de visão.

**Os valores de `CAM_PADRAO`** (o default aplicado no arranque e publicado como `camera_padrao`) são os do
`mjv_defaultFreeCamera(model)` para o modelo deste experimento **nos 3 campos de ORBITAR/zoom**:
`azimute`/`elevacao` = −20°/−20° (os `<visual><global azimuth elevation>` do `scene.xml` do menagerie —
medido: sem eles o default é 90°/−45°) e `distancia` = `1.5 × model.stat.extent` (com as hélices visíveis =
a configuração por omissão do `sim_view.py`, que é a da janela). O `lookat` do default automático
(`model.stat.center`) **NÃO faz parte do contrato**: em v2 o alvo é sempre o drone (`seguir_drone`). A
constante guarda o `azimute` já **normalizado mod 360** (**340.0 ≡ −20.0**, a mesma pose) para o REPOR VISTA
fazer ida-e-volta exacta (`camera_padrao` = ficheiro = os 3 valores em `viewer.cam` = `camera_atual`); o
`teste_camera.py` §1 prova a igualdade (módulo 360 no azimute) e FALHA se o modelo mudar sem a constante
ser atualizada. Nota honesta: com `--sem-helices` o default automático do modelo seria ~0,02 m mais longe
(o `stat` muda com os geoms das hélices) — aplica-se na mesma a constante explícita, e a diferença é
invisível.

---

### 4.5 Controle de voo (WASDQE) — contrato r11 (2026-10-10)

O pedido do dono: «um controle de voo onde mudo a altitude e a direção — WASD para as direções, Q e E para
subir e descer — vendo no site quando ativo; e durante a movimentação corrigir as rajadas de vento para
não ir mais lento nem a favor: respeitar a movimentação proposta sem sofrer a influência do vento».

**Semântica** (frame **mundo**, yaw alvo 0 — «frente» é o +x): `W = +x`, `S = −x`, `A = +y (esquerda)`,
`D = −y (direita)`, `Q = subir (+z)`, `E = descer (−z)`. As teclas comandam o **`v_ref`** (velocidade
proposta em m/s): diagonais horizontais normalizadas para **1,0 m/s**, `|vz| = 0,7 m/s`, sem teclas →
`v_ref = 0` = **segurar posição**. O env integra o `v_ref` na referência de POSIÇÃO `p_ref` a cada passo
de decisão (50 Hz) e satura em **`xy ±25 m`** (a ARENA de 50×50 m) e **`z ∈ [0,25; 25]` m** — na borda a
componente que bate fica com `v_ref = 0` (a referência não empurra contra o limite). **Limites de
movimento (2026-10-11, pedido do dono «quero andar por um espaço maior»)**: antes era uma caixa de
**xy ±4 m** com teto de referência **2,75 m** e terminação por subida a **3 m**; agora a caixa desapareceu
(o limite é o cenário: chão texturado 50×50 m), o teto de referência vai a **25 m** e a terminação por
subida só a **30 m** (`Z_TETO` = o céu). O **piso mantém-se 0,25 m** (o chão é real) e as velocidades
**não mudam** (`VOO_VEL` 1,0 m/s, `VOO_SUBIDA` 0,7 m/s — semântica do contrato). O **REINICIAR** repõe
`p_ref = (0, 0, 1)` e o comando em vigor volta a ser aplicado (as teclas continuam pressionadas).

**O que a política faz dele** (só com política `--comandos`, treinada com `train.py --comandos`): segue a
**velocidade proposta** — e é aqui que entra a exigência do dono: a recompensa de seguimento pune
`tanh(‖v − v_ref‖)`, ou seja, uma rajada que deixe o drone **mais lento** OU a levando **mais rápido** que
o comando custa **exatamente o mesmo** (simetria provada em `teste_controle_voo.py` §1 e §2 — a prova §2
mede ⟨vx⟩ com vento de proa e de cauda: têm de ser iguais). O bónus exige posição **E** velocidade
(`‖v − v_ref‖ < 0,10 m/s`), e a referência **nunca** se perde: quando o vento desvia o drone, o erro de
posição acumulado manda-o voltar — «respeitar a movimentação proposta» significa isso mesmo.

**Cadeia completa** (tudo testado em `teste_controle_voo.py`): tecla do site → `POST /api/voo` (estado
completo das 6 teclas) → bloco `"voo"` no ficheiro de controlo (escrita atómica, `seq` do servidor) →
runner aplica em `env.definir_comando_teclas` (1× por mudança de assinatura) → a política vê o `v_ref` na
observação e comanda o drone → o eco `"voo"` de cada linha de telemetria volta ao site (`v_ref`/`p_ref`
aplicados, erros, `seguindo`). O painel do site acende os keycaps **ao instante** (estado otimista) e o
`v_ref` comandado imediatamente; o eco mostra ao lado o que o runner está mesmo a aplicar (honesto para
vários clientes). Com política **clássica** o runner ignora o bloco com aviso e o eco vem `null` — o
painel diz «modo comando indisponível: esta política não foi treinada com `--comandos`».

### 4.6 Módulo de câmara FPV (2026-10-11) — a câmara de bordo, à frente do drone (+ a câmara da SIMULAÇÃO, trocável no site)

A câmara que o **drone vê** (não a da janela 3D): um **módulo de câmara Raspberry Pi emulado**
(`lab/camera_rpi.py` — Camera Module 3/3 Wide, Sony IMX708) montado **na frente do corpo** (`<camera
fpv>`, a olhar para +x) e ligado ao RPi 5 por CSI-2. Reproduz a experiência do hardware real: os mesmos
**modos de sensor** (4608×2592@14,35 · 2304×1296@56,03 · 1536×864@120,13, com os crops → FoV certo por
modo), os mesmos **modos de vídeo** (1080p50 · 720p100 · 480p120), os mesmos **megapixels** (sensor
11,9 MP; saída por modo), **JPEG qualidade 50** (o default do `rpicam-vid`) e a **latência de pipeline**
(116 ms a 1080p50, faixa publicada 150–300 ms a 1080p30) — **cumprida na entrega** (cada quadro só fica
disponível `latencia_modelada()` ms depois da captura). O modo **HDR** existe no hardware mas **não é
emulado** (recusa-se com erro — nunca se finge).

**Fluxo**: thread própria captura ao ritmo do modo (relógio de parede — a pausa e o `--fator-tempo` não o
mudam) → render na proporção da janela de recorte → JPEG q50 → `out/fpv/quadro.jpg` + `out/fpv/estado.json`
(atómico, só o último quadro) → `GET /api/fpv.mjpg` para o site. A CPU do Pi 5 é MODELO por etapa
(aquisição CSI 0–3 % · controlo do ISP 8–12 % · cópias 8–15 % · **JPEG software 50–80 %** · transporte ~5 %
de 1 núcleo A76 a 1080p50 = 0,94 núcleo — o **Pi 5 não tem encoder hardware**; faixas e fontes em
`pesquisas/relatorio-pipeline-camera-rpi5-custo-cpu.md`) e o painel RPi 5 mostra-a SEPARADA da inferência
(`camera_nucleos`/`nucleos_total`), lado a lado com o `host_ms` MEDIDO nesta máquina.

**No site** (bloco «Câmara FPV», secção Operação/Tudo): imagem ao vivo, com SELETOR DE FONTE **FPV (bordo) | Simulação (3.ª pessoa)** que troca o `<img>` entre `/api/fpv.mjpg` e /api/simulacao.mjpg (o widget de câmara do site comanda a vista da simulação mesmo sem viewer) (`<img src="/api/fpv.mjpg">`),
modo + resolução/MP de saída e do sensor, fps nominal e medido, qualidade/bytes/bitrate reais, latência
de modelo (com a faixa publicada), nº de quadros, custo do Pi 5 por etapa (com as faixas) e o medido no
PC; controlos **LIGAR/DESLIGAR** e **seletor de modo** (`POST /api/fpv`). Estados honestos: «sem módulo»
quando a API traz `null`, «módulo desligado» quando `ligada: false` (a imagem fica parada, não se inventa
nada). Sem módulo (modelo sem câmara ou `--sem-fpv`) tudo isto desaparece sem erro.

---

### 4.7 Seletor de controlador e o modo clássico — contrato r12 (2026-10-12)

O dono: «quero o drone a RODAR (yaw livre), WASDQE relativo ao RUMO, olhar para o círculo, e ver no site
quem faz o quê». O contrato r12 (aditivo sobre o r11) junta DOIS caminhos de controlo, trocáveis ao vivo:

| modo | quem pilota | yaw | WASDQE | perceção |
|---|---|---|---|---|
| **`rl`** (PADRÃO — o de sempre) | a política RL (IA-1, PPO, 50 Hz) | **FIXO** (contrato r11: yaw alvo 0) | frame **mundo** (+x = frente) | IA-2 «seguimento» (tracker, 25 Hz) quando existe |
| **`classico`** | a **cascata clássica C++ do firmware** (`firmware/nucleo/`, **via ctypes**) | **LIVRE**: Z/C rodam ±0,5 rad/s, X fixa o rumo (`yaw_alvo`), V = «olhar» | relativo ao **RUMO** (W = avanço no nariz; A/D laterais ao rumo) | detetor + **IBVS** C++ (25–30 Hz) com a câmara mono QVGA |

**Decisão documentada (C++ ou Python?)** — ficou o **C++ via ctypes**, como o dono pediu (é o código que
voa no Arduino): o núcleo `firmware/nucleo/` é compilado para uma `.so` (`sitl.py`, cache por hash das
fontes) e instalado **no env em uso** pelos MESMOS adaptadores do `sitl.DroneRealEnvNucleo(modo_nucleo=
"cascata")` (`_AdaptadorCascata`/`_AdaptadorEstimador`): estimador clássico → cascata → laço de taxa →
mistura, tudo no C++, que vê só os sensores medidos. O que NÃO se fez foi trocar de ENV em runtime: o
viewer da janela 3D e os módulos de câmara FPV ficam ligados aos `model`/`data` criados no arranque e não
há API para os religar — instalar o núcleo no env em uso dá o MESMO voo (a equivalência C++ ↔ Python está
provada no `teste_cascata_nucleo.py`) sem apagar a janela. O `CascataClassica` do `controlo_classico.py`
ficou como referência/protótipo e NÃO é o que voa no runner.

**A TROCA reinicia o EPISÓDIO** (calibração do giroscópio no chão — 1 s de motores em idle, como o
`DroneRealEnvNucleo.reset` — e arma a cascata) e é HONESTA: o bloco `"controlador"` da telemetria publica
`estado: "trocando"` + `motivo` antes de a troca acontecer (o `/api/state` mostra `trocando` sempre que o
`pedido` ≠ o eco) e `estado: "erro"` + `motivo` quando a troca é RECUSADA (ex. planta cf2 — a cascata é do
hardware do dono; no cf2 só há a política) — nunca se finge uma troca nem um silêncio. O núcleo é criado
UMA vez e reutilizado nas trocas seguintes; voltar a `rl` repõe o FC/estimador Python.

**Teclas novas do painel de voo** (keycaps `tecla-z|c|x|v`, ativos com o controlo ARMADO):

| tecla | ação | campo r12 do bloco `voo` |
|---|---|---|
| **Z** / **C** (manter) | rodar à esquerda / à direita a ±0,5 rad/s | `yaw_taxa: ±0.5` (0 ao soltar; limpa o `yaw_alvo`) |
| **X** (pressão) | FIXAR RUMO = o `rumo` atual da telemetria (ψ desde o armar) | `yaw_alvo: <rumo>` (sem rumo na telemetria o site diz-o e não inventa) |
| **V** (pressão) | SEGUIR/«OLHAR» — o IBVS passa a seguir o alvo | `segui_alvo: true/false` |

Prioridade no runner: `segui_alvo` > `yaw_alvo` > `yaw_taxa`/velocidade. Com `segui_alvo` o ponto mocap
passa a descrever o **CÍRCULO** (0,5 m/s, raio 1,5 m — o protocolo da B0/`avaliar_nucleo`) e o IBVS
segue-o com a guinada; ao sair do olhar o alvo fica parado onde estiver (nada de teleportes). Sem alvo no
modelo (env criado sem `com_alvo`) o «olhar» é RECUSADO com aviso e o comando cai para a prioridade
seguinte. O eco `"controlador"` mostra o que está a ser aplicado; no modo RL os campos de yaw vêm a zero
(a política r11 mantém o rumo fixo) e o painel diz «yaw livre só no modo CLÁSSICO».

**No site**: o cartão «Controlador» (toggle **RL (IA-1)** | **CLÁSSICO (C++)** com o estado honesto e as
fontes), o painel **«Quem faz o quê»** (FC 500 Hz não-IA · controlador 50 Hz — IA-1 medida × cascata C++
estimada — · perceção 25–30 Hz — IA-2 tracker × detetor+IBVS — · estimador de bordo 500 Hz, com latências
e semáforo de orçamento) e o sub-bloco **«Alvos de bordo possíveis»** do painel do computador de bordo (os
DOIS builds: RPi 5 + FC H7 `endurance_15pol_p50b` e Arduino Portenta H7 + Vision Shield
`endurance_15pol_arduino`, com os ciclos/instruções por passo do firmware — M7 1438 instr de 500 Hz =
3016 com tick, 4,3/10,1 µs @480 MHz vs o orçamento de 2 ms, text 24 582 B, RAM 2 940 B — e a latência da
câmara 116 ms CSI-2 vs 21 ms DCMI; o que é estimativa estática diz-se estimativa).

**Prova**: `teste_controlador.py` (6 secções: contrato r12 validado/recusado · seletor com estado
honesto · WASDQE relativo ao rumo e yaw Z/C/X/V · painéis presentes · integração real com o seletor a
trocar ao vivo, o yaw a rodar, W a mudar de eixo a 90° e o «olhar» a centrar o alvo · 2 mutações que têm
de FALHAR) e `site/testes/controlador.mts` (`npm run test:controlador`, 52 verificações de front).

## 5. Interfaces alternativas (o resto do experimento)

| peça | para quê | como |
|---|---|---|
| **`sim_site.py`** | ⭐ **o comando normal**: janela limpa + site (este documento) | `uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py` |
| **`sim_view.py`** | só a janela limpa (e telemetria), sem site; a animação das hélices desliga-se com `--sem-helices` | `… sim_view.py [--seguimento-model ZIP | auto-descobre out/real_1950_seguimento_*] [--sem-helices] [--fator-tempo 0.5] [--sem-janela --max-segundos 20] [--com-loop/--sem-loop]` |
| **`view.py`** | viewer **alternativo** com HUD de 8 linhas e teclas de vento (para depurar a rede sem site): `ESPAÇO` pausa · `R` reinicia · `[` `]` força ±0,5 m/s · `,` `.` azimute ±15° · `v` vento 0 · `Q`/`Esc` fecha | `… view.py [--model …] [--vento-inicial 3,90] [--sem-janela]` |
| **`dashboard.py`** | gestão de **TREINO** num site próprio (▶ Treinar, ■ Parar, curvas multi-run, rede ao vivo, painel de vento, log) — auditoria UX 41 → **88/100** | `… dashboard.py --port 8765 --out out` |
| **`net_probe.py`** | sonda: corre a política e grava a rede em JSONL (é o que o dashboard usa); modo **sem-loop** por omissão | `… net_probe.py --model …zip --out net.jsonl --interval 0.05 [--loop/--sem-loop]` |
| **`train.py`** | treino PPO com painel `rich` no terminal (τ: `--timesteps`, `--n-envs`, `--seed`, `--out-dir`, `--curriculo-vento 0,1,2,3`, `--retomar`, `--lr`, `--ent-coef`, `--log-std-init`, `--sem-painel`) | `… train.py --timesteps 500000 --seed 0` |
| **`deploy.py`** | export ONNX + validação + benchmark (proxy RPi 5) + multi-IA | `… deploy.py --model …zip [--int8] [--nproc 4]` |
| **`run.py`** | validação do env por fórmulas fechadas (146/146) | `… run.py` |
| **`teste_arranque_loop.py`** | prova do **arranque SEM REINÍCIO** (68 checagens com o §4 do front; 65 com `--sem-navegador`, 25 com `--sem-http`): §1 peças (defaults/flags/`fixar_loop`), §2 ciclo real no contador da física (sem auto-reset sem REINICIAR; auto-reset com `--com-loop`), §3 servidor real (fresco, `loop: true` velho corrigido, `POST /api/loop` sticky, `--com-loop`) com o **§3e** (ficheiro de controlo apagado/corrompido a meio da execução: a recriação preserva o `loop` do último POST e o contador `reiniciar`), §4 front real no Chrome headless, §5 corrida de arranque; sem modelo encontrado FALHA (exit 1) em vez de saltar o §3/§4/§5 | `… teste_arranque_loop.py [--sem-http] [--sem-navegador] [--fator-tempo 3] [--fontes DIR]` |
| **`teste_parar_vento.py`** | prova do **PARAR** (nenhuma rajada sobrevive) + fiabilidade sob POSTs concorrentes (**15/15** sem flags); `--http` ponta a ponta pelo servidor real (**16/16**), `--navegador` dirige o front real num Chrome headless por CDP (**18/18** com `--http --navegador`) | `… teste_parar_vento.py [--http] [--navegador]` |
| **`teste_camera.py`** | prova dos **comandos de CÂMARA v2 (3ª-pessoa)** (50 checagens: 17 §1 peças — `CAM_PADRAO` SEM `alvo` (== `mjv_defaultFreeCamera` nos 3 valores), `aplicar_camera` (3 escritas, nunca o `lookat`), `seguir_drone` (`lookat == body(CAM_CORPO).xpos + CAM_OFFSET`, offset provado não-nulo), validadores (faixas, **`null` ≠ ausente**, alias `distandia`, **`{}`/`{seq:n}` aceites — decisão documentada**), merge, **convenção de sinais** provada contra a pose real da câmara, `ler_registo` (assimetria: `alvo` de ficheiro v1 ignorado); 15 §2 ciclo real com viewer falso INSTRUMENTADO — **seguimento provado escrita a escrita enquanto o drone se move pela física** (REINICIAR + empuxo; colagem exacta 1e-9, sem lag), 1 aplicação por mudança de assinatura, rato preservado, **PAN sobreposto**, `seq` novo re-aplica, REPOR VISTA, ficheiro v1, telemetria `camera.alvo` = drone+offset (`null` sem viewer); 13 §3 servidor real na porta **8561** — **burst FRIO de 40 ligações × 3 rondas (120/120 servidos E aplicados, sem resets nem JSON partido)**, 8 rotas, 400s (chaves desconhecidas incl. `alvo`, `null`, faixas, alias ambíguo), decisão `{}`/`seq`, `seq` no servidor, merge, `camera_padrao`/`camera_atual`; 5 §4 **não-tautologia** (cópias mutadas em `$TMPDIR`): seguimento removido, posição velha, assinatura sem `seq`, validação de chaves desconhecidas removida e validação de `null` removida têm de FALHAR) | `… teste_camera.py [--sem-http] [--so-ciclo] [--so-pecas] [--fontes DIR]` |
| **`teste_controlador.py`** | prova do **SELETOR DE CONTROLADOR (r12)** — 6 secções, **71 checagens + 2 mutações**: 19 §1 contrato (bloco `voo` com yaw validado/recusado no runner E no servidor, `yaw_alvo` normalizado, `null` = valor, `controlador.modo` restrito) · 8 §2 seletor (arranque no modo do CLI, recusa honesta em cf2 com `erro`+motivo que NÃO se repete, estado `trocando` do `/api/state`) · 9 §3 rumo (**W muda de eixo a 90°**, prioridades olhar > yaw_alvo > velocidade, diagonal normalizada, sem alvo o olhar cai) · 15 §4 painéis presentes (testids) · 18 §5 integração real (servidor+runner: o seletor troca ao vivo com a linha `trocando`+motivo e o episódio novo, Z roda, X fixa o rumo, V liga o IBVS com o **alvo centrado** (mediana 17,7 px com a aquisição na janela) e a mover-se no círculo, **W a 90° leva para +y**) · 2 mutações (rotação do `v_ref_mundo` e validação estrita do seletor removidas → têm de FALHAR) | `… teste_controlador.py [--so-pecas] [--sem-e2e] [--porta N]` |
| **`site/`** | o código do site (React + `motion-plus-ui`); `npm run build` → `dist/`; `npm run test:camera` = **62/62** verificações (20 round-trip + 42 gestos, sem dependências); `npm run test:controlador` = **52/52** (r12: parsers do `controlador`, rotação rumo↔mundo, teclas Z/C/X/V, «quem faz o quê», alvos de bordo e painéis presentes) | `cd site && npm install && npm run build && npm run test:camera` |

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

## 7. Planta REAL — o drone do dono (2026-10-10, `plano-drone-real.md`)

Com uma política da planta real (`out/real_*/final.zip` com `hardware.json` ao lado — tem **precedência** na
escolha automática do modelo, no `sim_site.py` e no `sim_view.py`), o runner cria o `DroneRealEnv` NOMINAL
(sem DR) com o build e o modo de ação do `hardware.json`, a câmara de arranque passa a ser a do modelo gerado
(`mjv_defaultFreeCamera`, ~1,5 m — o drone tem 650 mm) e o alvo da câmara é o corpo `drone`. Com uma política
cf2 nada muda.

**Pack de bateria FÍSICO e persistente.** O estado do pack (SoH, ciclos equivalentes, recargas, histórico e o
ciclo em curso: SoC, temperatura, Ah/Wh descarregados) vive em `out/bateria/<pack_id>.json` e é regravado a cada
30 s, em cada comando e no fim. **REINICIAR mantém o pack** (pousar e voltar a descolar não carrega a bateria);
só o comando de bateria a muda:

- ficheiro de controlo: `"bateria": {"acao": "recarregar" | "nova", "seq": int}` — um `seq` NOVO dispara a ação
  uma vez (o do arranque é linha de base, nunca se repete); `recarregar` fecha o ciclo e aplica o desgaste
  (ΔSoH pela profundidade, C-rate e temperatura do ciclo) e põe o pack a 100 %; `nova` = pack novo (SoH 100 %);
- API: **`POST /api/bateria`** `{"acao": "recarregar"|"nova"}` → 200 `{"ok": true, "bateria": {"acao", "seq"}}`
  (o `seq` é do servidor) · 400 com o motivo para outra ação. São agora **14 rotas** `/api/*` (5 GET + 9 POST).
- `GET /api/state` e `GET /api/sim` trazem `"planta": "real"|"cf2"`; o `/api/state` traz ainda `"hardware"`
  (build, peças, massa, T/W, pairagem W e g/W, autonomia estimada, origem do kf/kq, DR) lido do `hardware.json`.

**Telemetria (chaves ADITIVAS em cada linha JSONL)** — com `"planta": "real"`:

| Chave | Conteúdo |
|---|---|
| `obs` | os **21** canais do ATOR (sensores + estimação de bordo + ação anterior); no cf2 continuam 16 |
| `act` | ação `[coletivo, p, q, r]` em [-1, 1] (modo `ctbr`: o FC fecha a malha de taxa) |
| `ctrl` | **empuxo de cada rotor** (N, r1..r4) — no cf2 era `[empuxo, mx, my, mz]` |
| `bateria` | `soc` (real), `soc_estimado` (OCV no arranque + Coulomb com a corrente MEDIDA pelo INA226, sobre a capacidade NOMINAL — diverge do real quando o pack envelhece), `v`, `v_celula`, `i`, `p`, `temp_c`, `soh`, `ciclos_eq`, `n_recargas`, `r0_mohm`, `ah_voo`, `wh_voo`, `alerta` (`""`/`tensao_baixa`/`critica`), `reformar` (SoH ≤ 80 %), `autonomia_min` (ou `null`), `s`, `p_paralelo`, `quimica`, `capacidade_ah`, `pack_id`, `v_pouso_celula`, `v_corte_celula`, `v_medida`, `i_medida`, `i_media`, `ultimo_ciclo` |
| `motores` | `rpm[4]`, `duty[4]`, `empuxo_n[4]`, `i_fase[4]`, `omega_max_rpm` e `t_max_n` (teto ATUAL, decai com a tensão), `t_max_frac` (T_max atual / com a bateria cheia), `armado`, `brownout` |
| `potencia` | ledger em W: `motores`, `eletronica`, `bec_perdas`, `total`, `consumidores_5v` {rpi5, fc, sensores…} |
| `aero` | `kappa_t[4]` (solo × inflow × VRS), `altura_rotores[4]` (m; 50 = sem chão no raio) |
| `estimador` | o que o RPi estima SÓ com os sensores: `roll`, `pitch`, `psi`, `h`, `vz`, `vx`, `vy`, `x`, `y` |
| `verdade` | o estado EXATO do simulador nos MESMOS referenciais do estimador (só para o site comparar — a política nunca o vê): `x`, `y` (m, referencial de arranque = o da odometria) e `alvo_xy`, `z` e `alvo_z`, `roll`, `pitch`, `psi` (= ψ − ψ₀), `yaw` (absoluto, rad — o das vistas rápidas da câmara), `vx`, `vy` (m/s, referencial do nariz), `vz`, `p`, `q`, `r` |
| `fim` | porque fechou o episódio: `"tempo"` (os 10 s) ou `"queda"` (caiu/capotou); `null` a correr — o selo do site só fica vermelho na queda |
| `h1`, `h2` | as ativações do ATOR com o tamanho REAL das camadas (128 + 128; antes o runner cortava a 64 e publicava zeros, e o bloco «Rede» ficava vazio) |

Na secção **Operação** (e **Tudo**) estes dados aparecem como cockpit: o **Painel de voo** (horizonte
artificial, rumo, fita de altura com o alvo, mapa de posição visto de cima com a posição ESTIMADA — ponto
cheio — e a REAL — contorno — ligadas pelo **erro do estimador** em cm, giroscópio em °/s e acelerómetro em
g com barras centradas, estado do ToF e do fluxo ótico; tudo em `site/src/lib/sensores.ts`) e o resumo
**«Bateria e motores»** (SoC real e estimado, autonomia, V e V/célula, corrente, potência, rotação média, uso
do teto de empuxo, estado dos ESC e o alerta). O site mostra ainda estes dados nos blocos **Bateria** (SoC real e estimado, V/célula, I, W, autonomia, SoH, ciclos,
temperatura, R₀, curva de descarga, alerta de tensão baixa/crítica, selo REFORMAR e os botões RECARREGAR / PACK
NOVO), **Motores e potência** (rpm/duty/empuxo/corrente por rotor com o sentido de rotação, teto ω_max/T_max que
decai com a tensão, ledger de potência e κ_T) e **Hardware (peças reais)** da secção Bordo (e em Tudo), e um
**indicador compacto de SoC + alerta** na barra crítica fixa — tudo só com `planta === "real"`; na observação, o
site usa os 21 rótulos do ator (`ROTULOS_OBS_REAL` em `site/src/lib/sim.ts`) e o `ctrl` passa a ser o empuxo por
rotor.

**Painel RPi 5 com a política real.** O benchmark vem do `deploy_report.json` que o `deploy.py` grava AO LADO do
modelo em uso (a política real: entrada `(1, 21)`); sem ele, do histórico `out/deploy_r10/deploy.json`. O campo
`inferencia.json` (e `rpi5.benchmark`) diz de qual dos dois veio, e `inferencia.modelo_coincide` compara o modelo
medido com o que o runner carregou resolvendo caminhos relativos contra a pasta do experimento E contra a raiz
(o `deploy.py` grava o caminho relativo ao sítio onde correu) — antes, um deploy corrido na raiz dava `false` e
o painel avisava "tempos de outra política" para a mesma política.

Teste ponta a ponta (2026-10-10, `sim_site.py --sem-janela` com `out/real_endurance15_rajadas/final.zip`):
`/api/state` com `planta: "real"`, `hardware.build = endurance_15pol_p50b` e o RPi 5 a ler o relatório da própria
política (p50 6,9 µs, `modelo_coincide: true`); telemetria com `obs` de 21, `ctrl` = empuxo por rotor e os blocos
`bateria/motores/potencia/aero/estimador`; `POST /api/vento` 3 m/s + `POST /api/vento-dinamico` rajadas aplicados
(numa amostra: posição estimada a ~7 cm do alvo, rolamento estimado de 6°, 164,6 W com o vento a soprar); `POST /api/bateria`
`recarregar` → 200 (ciclo fechado com o desgaste, `n_recargas` 1) e ação inválida → 400; `GET /` serve o site.

Verificação do front (2026-10-10, depois da avaliação de UX): `npm run typecheck` e `npm run build` limpos,
`npm run test:camera` (**20/20 + 67/67** — a geometria das vistas de cima/de lado provada contra
`pos = alvo − d·f` do MuJoCo, as vistas rápidas para vários rumos, o zoom logarítmico, o corpo completo dos
comandos e a máquina de gestos DEF-1/DEF-2) e **`npm run test:planta` (72/72** — parser das linhas reais,
rótulos e escalas dos 21 canais, `verdade`/`fim`, taxas 2/2/1 rad/s e coletivo linear em empuxo, o painel de
voo em graus/cm/g com o erro do estimador, e 2000 linhas de lixo sem exceções nem NaN). O pytest da skill
compara as constantes do site com as do `env_real.py`. O `npm run lint` acusa só 5 erros + 2 avisos, todos nos
componentes do catálogo `motion-ui` (código instalado, não editado); os de `camera.tsx` e do `cabecalho.tsx`
foram corrigidos. Prova visual: capturas antes/depois em `out/ux/` (Chrome headless + a janela 3D real num
Xvfb), com a avaliação `avaliacao_antes.json` / `avaliacao_depois.json`.
