# Site do experimento 09 — drone a pairar (política RL ao vivo)

Aplicação **React + TypeScript + Vite + Tailwind/shadcn**, construída com a skill `motion-plus-ui`
(registry `@motion`) e servida pelo backend `sim_site.py`, que também expõe a API. Uma página, sem
navegação: cabeçalho · curvas · rede 16→64→64→4 · **Raspberry Pi 5** · observação/ação · controlos
(vento constante + **vento dinâmico**) · botão **«?»** com a ajuda.

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

## Contrato da API (é o que o site consome)

| pedido | resposta |
|---|---|
| `GET /api/sim` | `{estado:"a_correr"\|"episodio_terminado", ep, passo, retorno, vento:{vel,azimute,elevacao,ativo}, vento_dinamico:{modo,params,ativo}, vento_atual:{vec,[vel,azimute,elevacao],modo,fonte}, rpi5:{…}, linhas:[{t,estado,ep,passo,retorno,z,dist_xy,yaw_err,vento_vel,vento_azim,vento_vec[3],vento_modo,obs[16],act[4],h1[64],h2[64],ctrl?[4]}]}` |
| `GET /api/state` | resumo; o site lê **`modelo_nome`** primeiro (`pasta/ficheiro.zip`, o rótulo legível) e só depois `modelo`/`model`/… — e, se existirem, `mg`, `thrust_max`, `momento_max`, `tau_escala`, `rpi5` |
| `POST /api/vento` | `{vel 0–5, azimute 0–360, elevacao −90–90}` → 200/400 |
| `POST /api/vento-dinamico` | `{modo:"nenhum"\|"rajadas"\|"frente"\|"dryden"\|"rajada_agora", params?, ativo?}` → 200/400 |
| `POST /api/reiniciar` | → `{contador: n}` |
| `POST /api/loop` | `{ativo: bool}` → 200 |

Polling de `GET /api/sim` a **2,9 Hz** (350 ms, dentro dos 2–5 Hz do contrato); sem websockets.
O histórico é acumulado por `ep:passo`, portanto tanto serve um backend que devolva tudo como um que
devolva só a cauda; episódio novo ⇒ histórico novo.

**Vento em vigor:** o vetor lido é `vento.vec` (contrato) **ou** `vento_atual.vec` (o que o `sim_site.py`
publica, com `modo` e a indicação de que veio da telemetria do runner); em último recurso usa-se o
`vento_vec` da última linha. O modo em vigor vem de `vento_atual.modo`, senão de `vento_modo` da linha,
senão do `vento_dinamico` pedido — por essa ordem, para o mostrador nunca ficar sem saber o que a física
está a fazer.

**Parâmetros dinâmicos** (os do treino, `env.valida_vento_dinamico`): `rajadas` `{p:0,02, duracao:10
passos, u_max:3,0}` · `dryden` `{sigma:0,5, L:10, v_min:1}` · `rajada_agora` `{duracao:25, u, azimute,
elevacao}` · `frente` `{vel, azimute, elevacao}` = **degrau IMEDIATO** que substitui o vento base (o
backend aceita este formato direto; a frente do treino, `{u_max,t_s}`, é outra coisa e não é o que o
painel envia). O site manda sempre este payload e mostra o 400 do servidor como aviso, sem reescrever o
pedido noutro formato.

**Nome do modelo no cabeçalho:** mostra sempre `pasta/ficheiro.zip` (nunca o caminho absoluto — é um
rótulo de painel, não um explorador de ficheiros, e a página pode ser partilhada). `lib/sim.ts`
(`nomeModeloLegivel`) aceita `/` e `\`, ignora barras finais e, acima de **34 caracteres**
(`MODELO_LEGIVEL_MAX`), corta no **miolo** para o fim do ficheiro continuar legível (`final.zip` vs
`best_model.zip`). 34 e não 26 porque os nomes deste laboratório cabem inteiros
(`vento_r9_polir_vento3/final.zip` = 31, `out/runs/seed0/best_model.zip` = 29).

**Semântica:** o site **nunca** reinicia sozinho. `estado=episodio_terminado` mostra
«episódio N terminado — clica REINICIAR»; com o **LOOP** ligado quem reinicia é o **backend**. Nenhum
controlo de vento (constante ou dinâmico) reinicia o episódio: todos escrevem no ficheiro de controlo e a
física muda no passo de decisão seguinte.

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
catálogo, `<dialog>` nativo, arrastável) com uma secção por elemento visível da página: cabeçalho/selos,
curvas, rede, obs (o que é cada rótulo `dp`/`rpy`/`v`/`ω`/`a_prev`), ação, vento constante, vento
dinâmico, rosa dos ventos, RPi 5 e episódio/estados. O conteúdo é **estrutura de dados** (`SECOES_AJUDA`)
e o componente só a percorre: acrescentar uma explicação é acrescentar um objeto, sem tocar em JSX.

## Estrutura

```
src/
  main.tsx                    MotionUIThemeProvider (uma vez, tema de ../motion.theme) + ThemeProvider
  App.tsx                     grelha: cabeçalho · principal (curvas/rede/RPi5/obs/ação) · controlos (sticky) · ajuda · toasts
  lib/sim.ts                  tipos do contrato, normalização defensiva, rótulos das 16 obs/4 ações
  lib/api.ts                  fetch dos 5 endpoints (erros legíveis; `?api=` para testes)
  hooks/use-sim.ts            polling, fusão do histórico, estado de ligação, ações (POST)
  components/sim/cabecalho.tsx    estado do episódio, contadores, modelo, ligação
  components/sim/curvas.tsx       z(t) com a linha do alvo 1,0 · yaw_err · retorno · vento_vel
  components/sim/rede.tsx         ativações 16→64→64→4 (SVG, cor por |a|)
  components/sim/rpi5.tsx         painel do alvo: imagem, specs, medidores e semáforo
  components/sim/rosa-ventos.tsx  bússola viva: seta do vetor em vigor, seleção, N/E/S/O, rajada
  components/sim/ajuda.tsx        botão «?» + SECOES_AJUDA (o que é cada elemento)
  components/sim/observacoes.tsx  tabela das 16 obs (obs/cru/barra) + ação (empuxo em N e momentos)
  components/sim/controlos.tsx    vento (sliders + APLICAR/PARAR) · dinâmico · REINICIAR (hold) · LOOP
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
| **PARAR VENTO** | velocidade 0 m/s no mesmo azimute/elevação |
| **PARADO · RAJADAS · DRYDEN** | modo dinâmico CONTÍNUO (`segmented-toggle`); `PARADO` envia `{"modo":"nenhum","ativo":false}` |
| **p · duração · u_max** | parâmetros das rajadas, editáveis no modo escolhido |
| **sigma · L · v_min** | parâmetros da turbulência Dryden |
| **RAJADA AGORA** | rajada única imediata com a força/azimute/elevação dos sliders e a duração do campo; fica «RAJADA EM CURSO» enquanto dura |
| **FRENTE AGORA** | degrau de vento imediato (interruptor: clicar outra vez desliga) |
| **duração da rajada** | passos de decisão (25 = 0,5 s a 50 Hz) |
| **PARAR DINÂMICO** | `{"modo":"nenhum","ativo":false}` |
| **REINICIAR (manter 1 s)** | `hold-to-confirm` — o ÚNICO caminho para reiniciar |
| **LOOP** | auto-reset pelo BACKEND (off por omissão) |

A **rosa dos ventos** (`rosa-ventos.tsx`) mostra duas setas: a **sólida** é o vetor EM VIGOR
(base + dinâmica, da telemetria) e a **tracejada** é a seleção dos sliders; tem N/E/S/O com graus
(E 0° · N 90° · O 180° · S 270°, azimute anti-horário a partir de +x), marca de 30° em 30°, anel a pulsar
enquanto há dinâmica ativa e a elevação no centro.

## Componentes `@motion` usados

| componente | onde |
|---|---|
| `sparkline` | as 4 curvas (`curvas.tsx`), com a linha do alvo na `grid` |
| `animated-number` | contadores do cabeçalho, valor de cada curva e % dos medidores do RPi 5 |
| `stagger-reveal` | entrada do título do cabeçalho (`splitText` linha a linha + seguidor) |
| `progress-bar` | barras da observação/ação e os 3 medidores do RPi 5 (p50, p99, CPU) |
| `hold-to-confirm` | botão **REINICIAR** (manter 1 s) |
| `multi-state-button` | **APLICAR VENTO**, **RAJADA AGORA** e **FRENTE AGORA** (pronto/a enviar/ok/erro/ativo) |
| `segmented-toggle` | **LOOP** e o modo dinâmico contínuo (**PARADO/RAJADAS/DRYDEN**) |
| `sheet` (`Sheet`/`SheetBackdrop`/`SheetPanel`/`SheetClose`/`useSheet`) | folha da **ajuda «?»** |
| `accordion` (`Accordion`/`AccordionItem`/`AccordionTrigger`/`AccordionPanel`/`AccordionChevron`) | secções da ajuda |
| `toast-stack` | avisos das ações e erros da API |
| `skeleton` (`SkeletonReveal`) | estado de carregamento antes da primeira linha |
| `ui-theme`, `motion.theme.ts` | tokens de movimento (`snap`/`ui`/`gentle`/…) |

Passo 4 da cascata (código novo), com justificação de uma linha cada:

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
- contra o **backend real** (`sim_site.py --sem-janela --sem-browser --port N`): os modos pedidos
  aparecem em `vento_dinamico`, em `vento_atual.modo` e no `vento_modo`/`vento_vec` das linhas da
  telemetria, o painel mostra os números do benchmark e o contador de reinícios do servidor não mexe.
