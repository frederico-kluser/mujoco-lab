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

**Bloco «Câmara»** (presente nas secções **Operação** e **Tudo**) — move a câmara da **janela 3D** a partir
do site (é **só apresentação**: nunca toca na física, no episódio nem em nenhum comando de vento/loop). A
câmara é **TERCEIRA-PESSOA CONTÍNUA** (contrato v2, 2026-10-10): o alvo é **sempre o drone** — o runner
escreve `viewer.cam.lookat = body(CAM_CORPO).xpos + CAM_OFFSET` **a cada frame** (`seguir_drone`, §4.4) —
e o site só comanda **ângulo + distância**:

| elemento | detalhe |
|---|---|
| **pad (círculo com glifo de drone + esfera arrastável)** | horizontal = **azimute** (0–360°; arrastar à direita aumenta — a câmara orbita de +x para +y, anti-horário visto de cima; passar nas bordas faz wrap 360↔0), vertical = **elevação** (−90…90°; **arrastar para cima põe a câmara mais alta** porque a `elevacao` fica mais negativa — `pos_z = alvo_z − d·sin(elev)`, §4.4; os limites travam a esfera) |
| **slider Distância** (0,1–10 m) | o zoom (`viewer.cam.distance`); o contrato aceita `distancia` até 20 m |
| **REPOR VISTA** | envia os valores de `camera_padrao` (`GET /api/state`) **como um comando normal** — não há mecanismo extra no backend |
| estado **otimista** no arrasto | o pad/slider respondem à mão imediatamente (sem esperar pelo polling); envio com **throttle ~150 ms** com **coalescência** (só o último estado arrastado segue para a rede) + commit imediato ao largar; os valores enviados são sempre os **do gesto** (a telemetria nunca os sobrescreve durante um arrasto nem com envio pendente); sem viewer (`camera_atual: null`) o controlo fica **desativado** com «—» |
| envio | `POST /api/camera {azimute, elevacao, distancia}` (qualquer **subconjunto**; **sem `alvo`** — o alvo é sempre o drone — e **sem `seq`**: o **servidor** incrementa-o a cada pedido; a resposta traz o bloco com o `seq` que ficou em vigor) |

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
**19 chaves**): **~10 Hz sempre** (com o episódio a correr ou já terminado — não há batimento lento); e
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

Cada linha é escrita com `flush`, para o site ver sem esperar pelo fecho do ficheiro.

### 4.3 A API (9 rotas `/api/*` + os ficheiros do site, JSON, local — a 9.ª, `POST /api/bateria`, é da planta real: §7)

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

## 5. Interfaces alternativas (o resto do experimento)

| peça | para quê | como |
|---|---|---|
| **`sim_site.py`** | ⭐ **o comando normal**: janela limpa + site (este documento) | `uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py` |
| **`sim_view.py`** | só a janela limpa (e telemetria), sem site; a animação das hélices desliga-se com `--sem-helices` | `… sim_view.py [--sem-helices] [--fator-tempo 0.5] [--sem-janela --max-segundos 20] [--com-loop/--sem-loop]` |
| **`view.py`** | viewer **alternativo** com HUD de 8 linhas e teclas de vento (para depurar a rede sem site): `ESPAÇO` pausa · `R` reinicia · `[` `]` força ±0,5 m/s · `,` `.` azimute ±15° · `v` vento 0 · `Q`/`Esc` fecha | `… view.py [--model …] [--vento-inicial 3,90] [--sem-janela]` |
| **`dashboard.py`** | gestão de **TREINO** num site próprio (▶ Treinar, ■ Parar, curvas multi-run, rede ao vivo, painel de vento, log) — auditoria UX 41 → **88/100** | `… dashboard.py --port 8765 --out out` |
| **`net_probe.py`** | sonda: corre a política e grava a rede em JSONL (é o que o dashboard usa); modo **sem-loop** por omissão | `… net_probe.py --model …zip --out net.jsonl --interval 0.05 [--loop/--sem-loop]` |
| **`train.py`** | treino PPO com painel `rich` no terminal (τ: `--timesteps`, `--n-envs`, `--seed`, `--out-dir`, `--curriculo-vento 0,1,2,3`, `--retomar`, `--lr`, `--ent-coef`, `--log-std-init`, `--sem-painel`) | `… train.py --timesteps 500000 --seed 0` |
| **`deploy.py`** | export ONNX + validação + benchmark (proxy RPi 5) + multi-IA | `… deploy.py --model …zip [--int8] [--nproc 4]` |
| **`run.py`** | validação do env por fórmulas fechadas (146/146) | `… run.py` |
| **`teste_arranque_loop.py`** | prova do **arranque SEM REINÍCIO** (68 checagens com o §4 do front; 65 com `--sem-navegador`, 25 com `--sem-http`): §1 peças (defaults/flags/`fixar_loop`), §2 ciclo real no contador da física (sem auto-reset sem REINICIAR; auto-reset com `--com-loop`), §3 servidor real (fresco, `loop: true` velho corrigido, `POST /api/loop` sticky, `--com-loop`) com o **§3e** (ficheiro de controlo apagado/corrompido a meio da execução: a recriação preserva o `loop` do último POST e o contador `reiniciar`), §4 front real no Chrome headless, §5 corrida de arranque; sem modelo encontrado FALHA (exit 1) em vez de saltar o §3/§4/§5 | `… teste_arranque_loop.py [--sem-http] [--sem-navegador] [--fator-tempo 3] [--fontes DIR]` |
| **`teste_parar_vento.py`** | prova do **PARAR** (nenhuma rajada sobrevive) + fiabilidade sob POSTs concorrentes (**15/15** sem flags); `--http` ponta a ponta pelo servidor real (**16/16**), `--navegador` dirige o front real num Chrome headless por CDP (**18/18** com `--http --navegador`) | `… teste_parar_vento.py [--http] [--navegador]` |
| **`teste_camera.py`** | prova dos **comandos de CÂMARA v2 (3ª-pessoa)** (50 checagens: 17 §1 peças — `CAM_PADRAO` SEM `alvo` (== `mjv_defaultFreeCamera` nos 3 valores), `aplicar_camera` (3 escritas, nunca o `lookat`), `seguir_drone` (`lookat == body(CAM_CORPO).xpos + CAM_OFFSET`, offset provado não-nulo), validadores (faixas, **`null` ≠ ausente**, alias `distandia`, **`{}`/`{seq:n}` aceites — decisão documentada**), merge, **convenção de sinais** provada contra a pose real da câmara, `ler_registo` (assimetria: `alvo` de ficheiro v1 ignorado); 15 §2 ciclo real com viewer falso INSTRUMENTADO — **seguimento provado escrita a escrita enquanto o drone se move pela física** (REINICIAR + empuxo; colagem exacta 1e-9, sem lag), 1 aplicação por mudança de assinatura, rato preservado, **PAN sobreposto**, `seq` novo re-aplica, REPOR VISTA, ficheiro v1, telemetria `camera.alvo` = drone+offset (`null` sem viewer); 13 §3 servidor real na porta **8561** — **burst FRIO de 40 ligações × 3 rondas (120/120 servidos E aplicados, sem resets nem JSON partido)**, 8 rotas, 400s (chaves desconhecidas incl. `alvo`, `null`, faixas, alias ambíguo), decisão `{}`/`seq`, `seq` no servidor, merge, `camera_padrao`/`camera_atual`; 5 §4 **não-tautologia** (cópias mutadas em `$TMPDIR`): seguimento removido, posição velha, assinatura sem `seq`, validação de chaves desconhecidas removida e validação de `null` removida têm de FALHAR) | `… teste_camera.py [--sem-http] [--so-ciclo] [--so-pecas] [--fontes DIR]` |
| **`site/`** | o código do site (React + `motion-plus-ui`); `npm run build` → `dist/`; `npm run test:camera` = **62/62** verificações (20 round-trip + 42 gestos, sem dependências) | `cd site && npm install && npm run build && npm run test:camera` |

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
  (o `seq` é do servidor) · 400 com o motivo para outra ação. São agora **9 rotas** `/api/*` (2 GET + 7 POST).
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

O site mostra estes dados nos blocos **Bateria** (SoC real e estimado, V/célula, I, W, autonomia, SoH, ciclos,
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

Verificação do front da planta real: `npm run typecheck` e `npm run build` limpos, `npm run test:camera`
(20/20 + 42/42) e **`npm run test:planta` (49/49 — parser das linhas reais, rótulos dos 21 canais, blocos e
indicador, comandos de bateria)**. O `npm run lint` acusa 13 erros que já existiam antes (componentes `motion-ui`,
`camera.tsx` e o `Date.now()` do `cabecalho.tsx`) — nenhum nos ficheiros da planta real.
