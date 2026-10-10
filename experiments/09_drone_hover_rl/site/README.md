# Site do experimento 09 — drone a pairar (política RL ao vivo)

Aplicação **React + TypeScript + Vite + Tailwind/shadcn**, construída com a skill `motion-plus-ui`
(registry `@motion`) e servida pelo backend `sim_site.py`, que também expõe a API. Uma página, sem
navegação, organizada em **SECÇÕES selecionáveis** — «eu escolho o que ver, para melhorar a monitoria
enquanto o drone opera»: **Operação** (vigiar o voo) · **Rede** · **Vento** · **Bordo** (RPi 5) ·
**Tudo** (layout completo) — mais o botão **«?»** com a ajuda e uma **barra fixa** do topo que nunca se
esconde (seletor de secções · **REINICIAR** · **LOOP** · estado crítico).

## Arranque

```bash
npm install          # precisa de MOTION_TOKEN (registry @motionplus) — ver .npmrc
npm run dev          # desenvolvimento (o proxy da API é a mesma origem: usa o sim_site.py)
npm run build        # tsc -b && vite build → dist/ (index.html + assets/, caminhos absolutos)
npx tsc -b           # só o type-check
```

Em produção quem serve o `dist/` é o `sim_site.py` (mesma origem ⇒ `fetch("/api/sim")` funciona sem
CORS nem configuração). Para apontar o `dist/` estático a **outro** porto (testes):
`index.html?api=http://127.0.0.1:8765` ou `window.__SIM_API_BASE__`. A ajuda também se abre já aberta
por link: `index.html?ajuda=1` (útil para partilhar e para provas de DOM em headless).

## Secções selecionáveis (monitoria em voo)

O seletor fica na **barra fixa do topo** (`smooth-tabs` do registry `@motion`) com 5 secções; **só uma
fica visível de cada vez** e a escolha é **persistente** — guardada em `localStorage` sob
`09_drone_hover_rl:seccao` e recuperada ao reabrir a página.

| secção | tecla | para que serve |
|---|---|---|
| **Operação** | `1` | vigiar o voo: cabeçalho (selo de estado, contadores, modelo), **valores atuais** (z, dist_xy, yaw_err, vento_vel) e as 4 curvas **grandes** (z, yaw_err, retorno, vento_vel) |
| **Rede** | `2` | a política a decidir: rede 16→64→64→4 com ativações ao vivo, observação (16 canais) e ação (4 canais) |
| **Vento** | `3` | comandar o vento: sliders constantes, rosa dos ventos, APLICAR/PARAR e vento dinâmico (rajadas, rajadas aleatórias, Dryden, frente) |
| **Bordo** | `4` | computador de bordo: painel do Raspberry Pi 5 |
| **Tudo** | `5` | layout completo: todas as secções, com a coluna de controlos à direita (como antes do seletor) |

- **atalhos 1–5** (documentados no «?» e visíveis nas abas): saltam de secção; as setas do teclado
  percorrem as abas; os atalhos **não atuam** enquanto se escreve num campo (input/textarea/select ou
  conteúdo editável) nem com o rato/foco sobre um slider (alvo, foco real ou `pointerover` dentro de
  `[role="slider"], [data-slider], [data-slot="slider"], [aria-valuenow]`).
- **o que nunca se esconde**: a faixa de **estado crítico** (API em baixo — o único estado com
  `role="alert"`; o fim do episódio sem reinício é uma linha NEUTRA, porque a física continua; com a API
  em baixo o alerta de ligação tem prioridade porque o estado do episódio já
  é velho) e os controlos **REINICIAR/CONTINUIDADE** — ambos na barra fixa, em qualquer secção.
- **updates continuam com a secção escondida**: os blocos escondem com o atributo `hidden` **sem se
  desmontarem** (`BlocoSecao`), logo o polling (`GET /api/sim`) continua, os widgets mantêm o estado
  (sliders e params dinâmicos não perdem o rascunho) e, ao voltar à secção, os valores estão frescos.

## Contrato da API (é o que o site consome — **8 rotas** `/api/*`, 2 GET + 6 POST)

| pedido | resposta |
|---|---|
| `GET /api/sim` | `{estado:"a_correr"\|"episodio_terminado", ep, passo, retorno, loop?, vento:{vel,azimute,elevacao,ativo}, vento_dinamico:{modo,params,ativo}, vento_atual:{vec,[vel,azimute,elevacao],modo,fonte}, rpi5:{…}, camera_padrao:{azimute,elevacao,distancia}, camera_atual:{azimute,elevacao,distancia,alvo:[x,y,z]}\|null, linhas:[{t,estado,ep,passo,retorno,z,dist_xy,yaw_err,vento_vel,vento_azim,vento_vec[3],vento_modo,loop?,obs[16],act[4],h1[64],h2[64],ctrl?[4],camera:{azimute,elevacao,distancia,alvo:[x,y,z]}\|null}]}` — cada linha de telemetria tem **19 chaves** (`../INTERFACE.md` §4.2); o `alvo` do `camera`/`camera_atual` é só **LEITURA** (o `lookat` real = drone+offset) e nunca é campo de comando (§4.3) |
| `GET /api/state` | resumo; o site lê **`modelo_nome`** primeiro (`pasta/ficheiro.zip`, o rótulo legível) e só depois `modelo`/`model`/… — e, se existirem, `mg`, `thrust_max`, `momento_max`, `tau_escala`, `rpi5`, `camera_atual`/`camera_padrao` |
| `POST /api/vento` | `{vel 0–5, azimute 0–360, elevacao −90–90}` → 200/400 |
| `POST /api/vento-dinamico` | `{modo:"nenhum"\|"rajadas"\|"aleatoria"\|"frente"\|"dryden"\|"rajada_agora", params?, ativo?}` → 200/400 |
| `POST /api/parar` | **PARAR VENTO — PARA TUDO** numa só escrita atómica: cancela todas as rajadas dinâmicas (a one-shot e os modos contínuos) **e** zera o vento base (mantém azimute/elevação, `ativo: false`) → 200 |
| `POST /api/reiniciar` | → `{contador: n}` |
| `POST /api/loop` | `{ativo: bool}` → 200 |
| `POST /api/camera` | **contrato v2**: subconjunto de `{azimute, elevacao, distancia}` → 200/400 — **sem** `alvo` (o alvo é do backend: `body(CAM_CORPO).xpos + CAM_OFFSET` do `sim_view.py` = drone+offset, seguido a cada frame) nem `seq` no comando (o `seq` do corpo é **ignorado** — o servidor incrementa-o). **Exceções reais do contrato** (`../INTERFACE.md` §4.3): `{}` e `{"seq": n}` são **aceites com 200** («toque»: mantém os valores e carimba `seq` novo); `null` presente → 400 e chave desconhecida (ex. `alvo` do contrato v1) → 400; faixas UI: azimute 0–360 (wrap 360↔0), elevação −90…90, distância 0,1–10 m (o backend aceita ]0,20]) |

Polling de `GET /api/sim` a **2,9 Hz** (350 ms, dentro dos 2–5 Hz do contrato); sem websockets.
O histórico é acumulado por `ep:passo`, portanto tanto serve um backend que devolva tudo como um que
devolva só a cauda; episódio novo ⇒ histórico novo.

**Vento em vigor:** o vetor lido é `vento.vec` (contrato) **ou** `vento_atual.vec` (o que o `sim_site.py`
publica, com `modo` e a indicação de que veio da telemetria do runner); em último recurso usa-se o
`vento_vec` da última linha. O modo em vigor vem de `vento_atual.modo`, senão de `vento_modo` da linha,
senão do `vento_dinamico` pedido — por essa ordem, para o mostrador nunca ficar sem saber o que a física
está a fazer.

**Parâmetros dinâmicos** (os do treino, `env.valida_vento_dinamico`): `rajadas` `{p:0,02, duracao:10
passos, u_max:3,0}` · `aleatoria` `{p:0,02, duracao:10 passos}` (só `p` e `duracao` têm semântica: cada
rajada re-sorteia a direção e a força dentro das faixas disponíveis — `U[0,5]` m/s, azimute `U[0,360°)`,
elevação `U[±90°]` — e o `u_max` é aceite mas não limita este modo) · `dryden` `{sigma:0,5, L:10, v_min:1}`
· `rajada_agora` `{duracao:25, u, azimute,
elevacao}` · `frente` `{vel, azimute, elevacao}` = **degrau IMEDIATO** que substitui o vento base (o
backend aceita este formato direto; a frente do treino, `{u_max,t_s}`, é outra coisa e não é o que o
painel envia). O site manda sempre este payload e mostra o 400 do servidor como aviso, sem reescrever o
pedido noutro formato. Nos modos contínuos (`rajadas`, `aleatoria`, `dryden`) **editar um campo aplica-se
sozinho**: passados ≈300 ms sem novas edições o site reenvia o modo em vigor com os params atuais (mesmo
`POST /api/vento-dinamico`, sem reiniciar o episódio); com `PARADO` os valores ficam guardados e só vão no
POST da ativação seguinte. Ver `INTERFACE.md` §3.5.

**Nome do modelo no cabeçalho:** mostra sempre `pasta/ficheiro.zip` (nunca o caminho absoluto — é um
rótulo de painel, não um explorador de ficheiros, e a página pode ser partilhada). `lib/sim.ts`
(`nomeModeloLegivel`) aceita `/` e `\`, ignora barras finais e, acima de **34 caracteres**
(`MODELO_LEGIVEL_MAX`), corta no **miolo** para o fim do ficheiro continuar legível (`final.zip` vs
`best_model.zip`). 34 e não 26 porque os nomes deste laboratório cabem inteiros
(`vento_r9_polir_vento3/final.zip` = 31, `out/runs/seed0/best_model.zip` = 29).

**Semântica (ronda 11 — LOOP sticky; default revisto em 2026-10-09):** o site **nunca** reinicia sozinho e o
REINICIAR **nunca é preciso para continuar a trabalhar**. O backend arranca **SEM REINÍCIO** (`loop:false`,
pedido do dono em 2026-10-09): no fim do episódio a física **nunca para nem reinicia** — continua a correr no
estado determinado depois do fim —, o `passo`/`t` da telemetria continuam a subir, o `retorno` congela, a
faixa diz isso mesmo numa linha NEUTRA (sem `role="alert"` e sem anel de alarme no botão) e o **REINICIAR
explícito** (botão com hold) é o único reset que existe. No modo **CONTÍNUO** (`loop:true`, via
`POST /api/loop {ativo:true}`; `--com-loop` no arranque é autoritativo e corrige o `loop` do ficheiro de
controlo) ao terminar o episódio arranca logo o seguinte (ep+1, passo 0), a faixa fica NEUTRA («episódio a
correr · modo contínuo») e o site limita-se a um **toast discreto** «episódio N · contínuo». O arranque é
autoritativo nos dois sentidos e, depois dele, só o `POST /api/loop` muda o modo. O que
exige ação (API em baixo) fica sempre vermelho, em qualquer secção. Nenhum
controlo de vento (constante ou dinâmico) reinicia o episódio: todos escrevem no ficheiro de controlo e a
física muda no passo de decisão seguinte — e as escritas parciais (sem `loop`/`reiniciar`) não tocam
nesses dois campos.

## Painel do Raspberry Pi 5 (computador de bordo)

`components/sim/rpi5.tsx` — imagem do alvo + especificações + medidores que atualizam com o polling:

- **imagem**: `src/assets/rpi5.webp` (a que o dono indicou, 960×640 com alfa). É uma **ilustração do
  Raspberry Pi Model B+ (2014)**, não do Pi 5 — fica identificada como ilustração de referência, com a
  atribuição (Lucasbosch, Wikimedia Commons, **CC BY-SA 3.0**), e é mostrada reduzida (nunca ampliada).
- **medidores**: p50 e p99 vs orçamento (20 ms @ 50 Hz), % de CPU equivalente, modelo (KB), fator int8,
  pior caso, núcleos multi-IA, núcleos/NPU do alvo, estado do hardware (`vcgencmd get_throttled` +
  temperatura, quando o backend os publicar — senão «sem hardware»).
- **semáforo** derivado: `ERRO` acima de 100 % do orçamento (p99 ou pior caso), `ATENÇÃO` acima de 70 %.
- **latências** (`fmtLatencia`, a mesma régua no p50, no p99, no pior caso e na latência estimada):
  abaixo de **100 µs** mostra µs com 1 casa («4,6 µs», «6,8 µs») — a 2 casas em ms sairia «0,00 ms» e o
  valor medido desaparecia; a partir daí mostra ms com 2 casas («0,16 ms», «2,50 ms»), comparável com o
  orçamento de 20 ms que está ao lado.
- **procedência honesta**: o TEXTO da `fonte` é o que o backend manda (ex.: «proxy x86 calibrado (1 core
  do A76; nao e o RPi)»), só a cor é classificada por prefixo; sem `inferencia.p50_us` o painel diz «sem
  benchmark publicado pelo backend» e **não inventa tempos** (medidores a «—»).
- se o benchmark for de **outro** `.zip` (`inferencia.modelo_coincide === false`), avisa-se que os tempos
  são de outra política.

## Ajuda «?»

`components/sim/ajuda.tsx` — botão fixo (canto inferior direito) que abre uma **folha** (`sheet` do
catálogo, `<dialog>` nativo, arrastável) com uma secção por elemento visível da página: **seletor de
secções** (o que cada secção serve, atalhos 1–5, persistência e updates com a secção escondida),
cabeçalho/selos,
curvas, rede, obs (o que é cada rótulo `dp`/`rpy`/`v`/`ω`/`a_prev`), ação, vento constante, vento
dinâmico, rosa dos ventos, RPi 5 e episódio/estados. O conteúdo é **estrutura de dados** (`SECOES_AJUDA`)
e o componente só a percorre: acrescentar uma explicação é acrescentar um objeto, sem tocar em JSX.

## Estrutura

```
src/
  main.tsx                    MotionUIThemeProvider (uma vez, tema de ../motion.theme) + ThemeProvider
  App.tsx                     barra fixa (seletor · REINICIAR/CONTINUIDADE · estado crítico), `loop` lido da API, aviso de episódio novo + as secções (operacao/rede/vento/bordo/tudo) · ajuda · toasts
  lib/sim.ts                  tipos do contrato, normalização defensiva, rótulos das 16 obs/4 ações
  lib/api.ts                  fetch dos 5 endpoints (erros legíveis; `?api=` para testes)
  hooks/use-sim.ts            polling, fusão do histórico, estado de ligação, ações (POST)
  components/sim/seccoes.tsx      seletor de secções (smooth-tabs), persistência (localStorage), atalhos 1–5, faixa de estado, BlocoSecao
  components/sim/cabecalho.tsx    estado do episódio, contadores, modelo, ligação
  components/sim/curvas.tsx       valores atuais (z, dist_xy, yaw_err, vento_vel) + z(t) com a linha do alvo 1,0 · yaw_err · retorno · vento_vel
  components/sim/rede.tsx         ativações 16→64→64→4 (SVG, cor por |a|)
  components/sim/rpi5.tsx         painel do alvo: imagem, specs, medidores e semáforo
  components/sim/rosa-ventos.tsx  bússola viva: seta do vetor em vigor, seleção, N/E/S/O, rajada
  components/sim/ajuda.tsx        botão «?» + SECOES_AJUDA (o que é cada elemento)
  components/sim/observacoes.tsx  tabela das 16 obs (obs/cru/barra) + ação (empuxo em N e momentos)
  components/sim/controlos.tsx    ControlosVento (sliders + APLICAR/PARAR + dinâmico) · ControlosEpisodio (REINICIAR hold · continuidade, barra fixa)
  components/sim/camera.tsx       widget «Câmara» (vista 3.ª pessoa): pad (círculo + drone + esfera) + slider de distância + REPOR VISTA
  lib/camera-gestos.ts            mapeamento esfera↔ângulos + máquina de gestos (snapshot DEF-1, «—» DEF-2, throttle 150 ms)
  testes/                         camera-roundtrip.mts + camera-gestos.mts (`npm run test:camera`)
  components/sim/avisos.tsx       toasts das ações (toast-stack)
  assets/rpi5.webp            imagem do alvo (ilustração de referência; CC BY-SA 3.0)
  components/motion-ui/**     componentes do registry @motion (source do CLI — não editar)
  components/ui/**            primitivos shadcn (button, card, slider, input)
```

## Controlos

| controlo | o que faz |
|---|---|
| **força / azimute / elevação** | sliders do vento CONSTANTE (0–5 m/s · 0–360° · −90…90°) |
| **APLICAR VENTO** | `POST /api/vento {vel,azimute,elevacao}` (`multi-state-button`) |
| **PARAR VENTO** | **PARA TUDO** num só pedido (`POST /api/parar`): cancela todas as rajadas dinâmicas (a one-shot e o modo contínuo) **e** zera o vento base (mantém azimute/elevação) |
| **PARADO · RAJADAS · ALEATÓRIA · DRYDEN** | modo dinâmico CONTÍNUO (`segmented-toggle`); `PARADO` envia `{"modo":"nenhum","ativo":false}` |
| **p · duração · u_max** | parâmetros das rajadas, editáveis no modo escolhido; `ALEATÓRIA` só usa `p` e `duração` (a força e a direção são sorteadas a cada rajada nas faixas por inteiro — 0–5 m/s, 0–360°, ±90° — e o `u_max` não limita) |
| **editar um parâmetro** (com um modo contínuo ativo) | live-apply: ≈300 ms depois da última edição o site reenvia o modo em vigor com os params atuais, sem reiniciar o episódio |
| **sigma · L · v_min** | parâmetros da turbulência Dryden |
| **RAJADA AGORA** | rajada única imediata com a força/azimute/elevação dos sliders e a duração do campo; fica «RAJADA EM CURSO» enquanto dura |
| **FRENTE AGORA** | degrau de vento imediato (interruptor: clicar outra vez desliga) |
| **duração da rajada** | passos de decisão (25 = 0,5 s a 50 Hz) |
| **PARAR DINÂMICO** | `{"modo":"nenhum","ativo":false}` |
| **REINICIAR (manter 1 s)** | `hold-to-confirm` — o **único reset que existe** (barra fixa do topo, em qualquer secção; vale com e sem loop) |
| **CONTINUIDADE · CONTÍNUO / SEM REINÍCIO** | mostra o que o BACKEND faz (campo `loop` da API, não uma preferência do browser): **SEM REINÍCIO** (**por omissão** desde 2026-10-09) deixa a física continuar no estado em que ficou — não para nem reinicia — e só o REINICIAR começa outro episódio; **CONTÍNUO** reinicia sozinho ao terminar (ep+1). `POST /api/loop {ativo}` (barra fixa do topo) |
| **esfera do pad «Câmara»** | arrastar: horizontal = azimute (a direita aumenta; wrap 360↔0 nas bordas), vertical = elevação (**cima = câmara mais alta**; limites ±90° travam a esfera) |
| **distância (câmara)** | slider 0,1–10 m — zoom mantendo o alvo |
| **REPOR VISTA** | envia o `camera_padrao` `{azimute, elevacao, distancia}` (contrato v2) |

A **rosa dos ventos** (`rosa-ventos.tsx`) mostra duas setas: a **sólida** é o vetor EM VIGOR
(base + dinâmica, da telemetria) e a **tracejada** é a seleção dos sliders; tem N/E/S/O com graus
(E 0° · N 90° · O 180° · S 270°, azimute anti-horário a partir de +x), marca de 30° em 30°, anel a pulsar
enquanto há dinâmica ativa e a elevação no centro.

## Componentes `@motion` usados

| componente | onde |
|---|---|
| `smooth-tabs` (`SmoothTabs`/`SmoothTabsList`/`SmoothTabsTab`) | seletor de secções da barra fixa (pílula deslizante + foco nômade por setas) |
| `sparkline` | as 4 curvas (`curvas.tsx`), com a linha do alvo na `grid` |
| `animated-number` | contadores do cabeçalho, valor de cada curva e % dos medidores do RPi 5 |
| `stagger-reveal` | entrada do título do cabeçalho (`splitText` linha a linha + seguidor) |
| `progress-bar` | barras da observação/ação e os 3 medidores do RPi 5 (p50, p99, CPU) |
| `hold-to-confirm` | botão **REINICIAR** (manter 1 s) |
| `multi-state-button` | **APLICAR VENTO**, **RAJADA AGORA** e **FRENTE AGORA** (pronto/a enviar/ok/erro/ativo) |
| `segmented-toggle` | **CONTINUIDADE** (**CONTÍNUO/SEM REINÍCIO**) e o modo dinâmico (**PARADO/RAJADAS/ALEATÓRIA/DRYDEN**) |
| `sheet` (`Sheet`/`SheetBackdrop`/`SheetPanel`/`SheetClose`/`useSheet`) | folha da **ajuda «?»** |
| `accordion` (`Accordion`/`AccordionItem`/`AccordionTrigger`/`AccordionPanel`/`AccordionChevron`) | secções da ajuda |
| `toast-stack` | avisos das ações e erros da API |
| `skeleton` (`SkeletonReveal`) | estado de carregamento antes da primeira linha |
| `ui-theme`, `motion.theme.ts` | tokens de movimento (`snap`/`ui`/`gentle`/…) |

Passo 4 da cascata (código novo), com justificação de uma linha cada:

- **`seccoes.tsx` · painéis das secções (`hidden`)** — o `smooth-tabs` traz o crossfade de painéis com
  mount/unmount, mas a monitoria exige widgets vivos e estado (sliders) preservado com a secção
  escondida: usam-se os TABS do catálogo e os blocos escondem com `hidden` sem se desmontarem.

- **`rede.tsx`** — o catálogo não tem visualizador de ativações (`sparkline` é série temporal,
  `progress-bar` é barra): grelha SVG por camada, cor por `|a|`. Sem arestas porque o contrato só traz
  ativações, não pesos — desenhar ligações seria inventar dados.
- **`rosa-ventos.tsx`** — mostrador polar/bússola também ausente do catálogo (`sparkline` é série
  temporal, `progress-bar` é barra): SVG só com `transform`/`opacity`, com as duas setas
  (vigor vs seleção), N/E/S/O em graus e o anel de dinâmica.
- **`rpi5.tsx`** — o catálogo não tem cartão de especificações de hardware nem indicador de saúde ligado
  a telemetria: composição com `Card`/`ProgressBar`/`AnimatedNumber` e o semáforo derivado do p99.
- **`ajuda.tsx` · legenda (`dl` dos itens)** — a `accordion` do catálogo dá as secções mas não uma lista
  de definições; é texto com classes semânticas, sem CSS de layout próprio.
- **`controlos.tsx` · `key={geracao}` no REINICIAR** — o `hold-to-confirm` instalado é de **um disparo**
  (o `done` interno só volta com `reset()`, que ele não expõe em `mode="callback"`): remontar por `key`
  volta a armar o botão e repõe a escala, sem tocar no source instalado.
- **`stats-live-panel` (avaliado, descartado)** — foi instalado durante a avaliação da cascata e
  removido: é uma secção-demo **fechada**, que gera os próprios números de engagement e só aceita
  `eventsBaseline`/`tickIntervalMs` — não dá para lhe passar telemetria real. Ficou a dependência que
  ele trouxe, `animated-number`, e o padrão de painel; os valores no ecrã são do MuJoCo.

## Widget da câmara — pad de terceira-pessoa (bloco «Câmara», Operação e Tudo)

O controlo de câmara do dono (2026-10-09): um **CÍRCULO** com um glifo de **DRONE** ao centro e uma
**ESFERA arrastável** (horizontal = azimute, vertical = elevação), um **SLIDER de DISTÂNCIA**
(0,1–10 m) e o botão **REPOR VISTA**. Sem presets — o pad substitui-os. O efeito é de jogo de
terceira-pessoa: a câmara **orbita sempre o drone** (o backend faz o seguimento do alvo =
drone+offset; o front só comanda ângulo + distância). Implementação: `src/components/sim/camera.tsx`
(apresentação) + `src/lib/camera-gestos.ts` (mapeamento e máquina de gestos), contrato v2 em
`src/lib/sim.ts` (`CameraEstado`, `CorpoCamera`, `lerCamera`, `cameraReflete`).

**Mapeamento esfera ↔ ângulos** (coordenadas normalizadas `u` horizontal [direita +] e `w` vertical
[cima +]):

| gesto | efeito | fórmula |
|---|---|---|
| horizontal | azimute (0–360°, wrap 360↔0 passando nas bordas laterais: a esfera sai por um lado e entra pelo outro) | `u = azimute/180 − 1` · arrastar para a direita AUMENTA o azimute (a câmara orbita de +x para +y, anti-horário visto de cima) |
| vertical | elevação (−90…90°, a esfera TRAVA nas bordas superior/inferior) | `w = −elevacao/90` · **arrastar para CIMA põe a câmara MAIS ALTA**: a elevação fica mais **negativa** |
| slider | distância (zoom) | 0,1–10 m |
| REPOR VISTA | envia o `camera_padrao` `{azimute, elevacao, distancia}` | comando explícito, sempre enviado |

**Sinal da elevação (a parte contra-intuitiva):** na convenção do MuJoCo a elevação **negativa** vê
de cima (`pos = alvo − d·f`, `f = [cos e·cos a, cos e·sin a, sin e]` ⇒ `pos_z = alvo_z − d·sin(elev)`).
Por isso arrastar a esfera para cima diminui a elevação (mais negativa) e **sobe** a câmara; os
extremos: `−90°` = câmara por cima do alvo (`pos_z = alvo_z + d`), `+90°` = por baixo. A fórmula está
verificada contra o MuJoCo 3.15 (`MjvScene.camera[0/1]`, erro ≤ 2,3e-8 no `forward` — tabela
`GROUND_TRUTH` em `testes/camera-roundtrip.mts`).

**Comandos e gestos** (`lib/camera-gestos.ts`): comandos ao vivo ENQUANTO se arrasta — throttle de
**150 ms** com coalescência (os eventos entre disparos caem num só comando = **1 comando por mudança
final de valor**) — mais um **commit final imediato ao largar**. O corpo de `POST /api/camera` é
sempre o subconjunto do gesto: o pad manda `{azimute, elevacao}`, o slider manda `{distancia}`, o
REPOR VISTA manda `{azimute, elevacao, distancia}` (nunca `alvo` nem `seq`).

**Estados honestos — os 2 defeitos medidos do bloco anterior (sliders) estão corrigidos:**

- **DEF-1 (gestos perdidos, grave):** a telemetria (poll de 350 ms) substituía os valores do gesto
  entre o `pointerup` e o envio agendado (150 ms) e o POST levava valores velhos (~43 % dos gestos).
  Agora os valores enviados são **sempre os do gesto**: cada edição fixa um *snapshot* do corpo por
  enviar (fixado no fim do gesto e refrescado em cada envio a partir do estado do gesto) e a
  **telemetria nunca sobrescreve valores durante o arrasto nem enquanto há envio pendente** (snapshot
  por disparar ou envio por confirmar — a confirmação fecha-se por igualdade com a câmara real ou por
  expiração a 1500 ms).
- **DEF-2 (estados honestos):** `camera`/`camera_atual` a passar a `null` (janela fechada) mostra
  **«—» SEMPRE** e desativa o controlo (pad, slider e REPOR VISTA) — nunca se retém o valor antigo;
  `null`→valor→`null` termina em «—».

Fora de arrasto a esfera segue a **câmara real** (inclusive quando a mexes com o rato da própria
janela 3D); durante o arrasto o estado é otimista. A posição da esfera é **sempre** função dos ângulos
atuais (o desenho limita o raio a 1 para a esfera ficar dentro do círculo).

**Testes** (`npm run test:camera`): `testes/camera-roundtrip.mts` (round-trip pos↔alvo ≤ 1e-9,
ground truth do MuJoCo 3.15, contrato v2 da leitura/comando) + `testes/camera-gestos.mts`
(mapeamento esfera↔ângulos: wrap 360↔0, limites ±90 e o sinal da elevação provado com a fórmula;
DEF-1 com telemetria viva — incl. câmara externa a meio do arrasto, com a janela de confirmação
expirada (regressão M5); DEF-2; REPOR VISTA; coalescência) — 62 verificações, sem dependências
(Node ≥ 22.6, type-stripping). **Não-tautologia:** 8 mutações do código de produção (sinal da
elevação, wrap, guarda DEF-1, guarda do arrasto na `receberCamera` (M5), «—» DEF-2, snapshot vs
mostrado, `cameraReflete`) aplicadas a uma cópia staged em `$TMPDIR` — todas mortas (os testes
falham com cada mutação).

**Prova DOM/CDP** (Chrome headless + stub do contrato v2 em `$TMPDIR`, porta 8551, servindo o
`dist/` real; arrastos REAIS via `Input.dispatchMouseEvent`): arrastar a esfera manda
`POST /api/camera` com o azimute/elevação certos (wrap 360↔0 e limites ±90 incluídos), o slider manda
`{distancia}`, o REPOR VISTA manda o `camera_padrao`, sem dados mostra «—» e desativa-se, a esfera
acompanha a telemetria fora de arrasto, um gesto sob telemetria viva envia os valores do gesto
(DEF-1) e os restantes blocos/atalhos seguem como antes (vento, loop, operações, atalhos 1–5,
persistência da secção, barra crítica) — 37/37 verificações.

## Testar contra um backend falso

Qualquer servidor stdlib que responda ao contrato serve. O teste feito nesta máquina: mock em `$TMPDIR`
que serve o `dist/` **e** a API (com `rpi5` em quatro modos: `proxy`, `real`, `sem_benchmark` e
`ausente`), com os pedidos registados em JSONL, mais:

- `google-chrome-stable --headless=new --dump-dom "…/?ajuda=1"` — prova de DOM: ajuda com todas as
  secções, bússola, painel dinâmico, 0 `undefined`/`NaN`;
- **Puppeteer** (headless, `pipe: true`) — imagem do RPi carregada, 3 barras do catálogo, semáforo,
  arrastar o slider e clicar **RAJADA AGORA** (o payload leva `u` = valor do slider, a direção dos
  sliders e a duração do campo), **FRENTE AGORA**, **RAJADAS**, **PARAR DINÂMICO**
  (`{"modo":"nenhum","ativo":false}`), anel da rajada na rosa, e a prova de que **nenhum**
  `POST /api/reiniciar` sai do site;
- provas do **seletor de secções** (Puppeteer + mock `/api/sim` que evolui no tempo): as 5 secções
  presentes, cada uma a mostrar SÓ o seu conteúdo (blocos alheios `hidden`), «Tudo» completo, estado
  crítico (API em baixo) visível em qualquer secção, persistência da secção após
  reload, valores frescos com «Operação» escondida, atalhos 1–5 (e a guarda dentro de campos) e
  REINICIAR/LOOP acessíveis em qualquer secção;
- contra o **backend real** (`sim_site.py --sem-janela --sem-browser --port N`): os modos pedidos
  aparecem em `vento_dinamico`, em `vento_atual.modo` e no `vento_modo`/`vento_vec` das linhas da
  telemetria, o painel mostra os números do benchmark e o contador de reinícios do servidor não mexe.
  Nesse mesmo backend, o **live-apply** foi provado com Chrome `--headless=new` + CDP (o site a sério,
  sem cliques de aplicar): `RAJADAS` ligado → `p` de 0,02 para 0,5 no painel → `vento_dinamico.params.p`
  = 0,5 no `GET /api/sim`; `ALEATÓRIA` ligado → `duração` para 42 → `params.duracao` = 42. Quatro ações do
  utilizador, exatamente quatro aplicações no log do runner (sem duplicados nem ciclo de POSTs).
