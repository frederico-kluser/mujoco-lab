# site/ — o FRONT do bundle `front-conexao` (todas as métricas e todos os controlos)

Aplicação **React + TypeScript + Vite + Tailwind/shadcn**, construída com a skill `motion-plus-ui`
(registry `@motion`) e servida pelo backend `sim_site.py`, que expõe também a API. Uma página, sem navegação:
organizada em **5 SECÇÕES escolhíveis** — **Operação** (cabeçalho, valores atuais, curvas grandes) ·
**Rede** (ativações, observação, ação) · **Vento** (sliders, rosa dos ventos viva, vento dinâmico) ·
**Bordo** (painel do computador de bordo, Raspberry Pi 5) · **Tudo** (layout completo) — com o seletor numa
**barra crítica fixa** (REINICIAR/LOOP e o estado sempre visíveis), atalhos de teclado **1–5**, escolha
persistida no `localStorage` e **ajuda «?»**. Os contratos estão no `../CONTRATOS.md`.

> Princípio do laboratório (`padrao-simulacao-clean-site`): **a janela do MuJoCo mostra só a simulação 3D;
> todas as métricas e todos os controlos estão aqui.** O site **nunca reinicia sozinho**: no fim do episódio a
> física congela e aparece «episódio terminado — clica REINICIAR» (ou liga-se o LOOP).

## Setup do zero (uma vez por clone)

```bash
source ~/.secrets                                    # MOTION_TOKEN do registry @motionplus (ver .npmrc)
npx shadcn@latest init -t vite -n site -b base -p nova --no-monorepo --no-rtl -y   # só se NÃO tiveres as fontes
node ensure-setup.mjs                                # idempotente: node/npm, token, deps e componentes que faltem
npm run build                                        # tsc -b && vite build → dist/ (é o que o sim_site.py serve)
```

Com as fontes do template (este caso) basta `node ensure-setup.mjs && npm run build`. O `dist/` **não** é
versionado: quem o constrói é este `npm run build`; o servidor `sim_site.py` serve-o em `http://127.0.0.1:8080`.

Comandos úteis: `npm run dev` (desenvolvimento), `npm run typecheck` (`tsc -b`), `npm run lint` (eslint),
`npm run format` (prettier). Em produção, `fetch("/api/sim")` é mesma origem — sem CORS. Para apontar um
`dist/` estático a **outro** porto (testes): `index.html?api=http://127.0.0.1:8765` ou `window.__SIM_API_BASE__`.

## Contrato da API (é o que o site consome)

| pedido | resposta |
|---|---|
| `GET /api/sim` | `{estado:"a_correr"\|"pausado"\|"episodio_terminado", ep, passo, retorno, vento:{vel,azimute,elevacao,ativo,vec:[vx,vy,vz],modo}, vento_dinamico:{modo,params,ativo}, vento_atual:{vec,vel,azimute,elevacao,modo,fonte}, rpi5:{…}, linhas:[{t,estado,ep,passo,retorno,theta,erro,omega,vento_vel,vento_azim,vento_vec[],vento_modo,obs[],act[],ctrl[],h1[],h2[]}], modelo_nome, sim_vivo, loop}` |
| `GET /api/state` | resumo (o mesmo sem `linhas`, mais `contador_reiniciar`, `n_linhas`, `modelo`, `modelo_motivo`, `pid`, `porta`, `idade_telemetria_s` e o painel `rpi5` completo) |
| `POST /api/vento` | `{vel 0–5, azimute 0–360, elevacao −90–90}` (subconjunto aceite) → 200/400 |
| `POST /api/vento-dinamico` | `{modo:"nenhum"\|"rajadas"\|"frente"\|"dryden"\|"rajada_agora", params:{…}, ativo:bool}` → 200/400 (**nunca** reinicia o episódio) |
| `POST /api/reiniciar` | → `{contador: n}` (o contador é o mecanismo: valor novo = um pedido) |
| `POST /api/loop` | `{ativo: bool}` → 200 |

Polling de `GET /api/sim` a **~2,9 Hz** (350 ms, dentro dos 2–5 Hz do contrato); **sem websockets**. O histórico
é acumulado por `ep:passo`, por isso tanto serve um backend que devolva tudo como um que devolva só a cauda;
episódio novo ⇒ histórico novo. Estados honestos: 400/404/500 e «—» no ecrã quando não há dados — nunca
números inventados. `theta`/`erro`/`omega` vêm em **rad** e **rad/s** e são convertidos para graus no site.

## Estrutura

```
src/
  main.tsx                       MotionUIThemeProvider (uma vez, tema de ../motion.theme) + ThemeProvider
  App.tsx                        grelha: cabeçalho · curvas · rede · obs/ação · RPi 5 · controlos · ajuda · avisos
  assets/rpi5.webp               imagem de referência do painel do computador de bordo (ver atribuição abaixo)
  lib/config.ts                  ★ CONFIGURAÇÃO (METRICAS, ROTULOS_OBS/ACT, unidades) — o ÚNICO ficheiro a adaptar
  lib/sim.ts                     tipos do contrato + leitura defensiva + helpers (re-exporta a configuração)
  lib/api.ts                     fetch dos endpoints do contrato (erros legíveis; `?api=` para testes)
  hooks/use-sim.ts               polling, fusão do histórico por ep:passo, estado de ligação, ações (POST)
  components/sim/cabecalho.tsx      estado do episódio, contadores, política em uso, ligação
  components/sim/curvas.tsx         as curvas de METRICAS (modo `grande`) + a faixa de VALORES ATUAIS
  components/sim/rede.tsx           ativações obs→h1→h2→act (SVG, cor por |a|; sem arestas = sem inventar pesos)
  components/sim/observacoes.tsx    tabela da observação (obs[i]) + painel da ação (act e o `ctrl` físico)
  components/sim/seccoes.tsx        SECÇÕES (seletor, atalhos 1–5, localStorage, blocos `hidden`, barra crítica)
  components/sim/controlos.tsx      ControlosVento (sliders + VENTO DINÂMICO) e ControlosEpisodio (REINICIAR/LOOP)
  components/sim/rosa-ventos.tsx    rosa dos ventos viva: seta cheia = vetor em vigor, tracejada = seleção
  components/sim/rpi5.tsx           painel do computador de bordo: specs, semáforo p50/p99, int8, multi-IA
  components/sim/ajuda.tsx          botão «?» + folha com o significado de CADA elemento (dados, não JSX)
  components/sim/avisos.tsx         toasts das ações e dos erros da API (`toast-stack`)
  components/motion-ui/**        componentes do registry @motion (source do CLI — não editar)
  components/ui/**               primitivos shadcn (button, card, slider)
```

## Componentes `@motion` usados

| componente | onde |
|---|---|
| `sparkline` | as 4 curvas (`curvas.tsx`), com a linha de referência na `grid` |
| `animated-number` | contadores do cabeçalho e valor atual de cada curva |
| `stagger-reveal` | entrada do título e dos contadores do cabeçalho |
| `progress-bar` | barras da observação, da ação e os medidores do painel RPi 5 |
| `hold-to-confirm` | botão **REINICIAR** (manter 1 s) |
| `multi-state-button` | **APLICAR VENTO**, **RAJADA AGORA**, **FRENTE AGORA** (pronto/a enviar/ok/erro/ativo) |
| `segmented-toggle` | **LOOP** e o modo dinâmico contínuo (PARADO/RAJADAS/DRYDEN) |
| `accordion` | as secções da folha de ajuda «?» |
| `sheet` | a própria folha de ajuda (diálogo nativo, foco preso, arrastar para fechar) |
| `smooth-tabs` | o seletor de SECÇÕES (pílula deslizante, setas do teclado, foco nômade) |
| `input` (shadcn) | campos numéricos dos parâmetros dinâmicos (`p`, `duração`, `u_max`, `sigma`, `L`, `v_min`) |
| `toast-stack` | avisos das ações e erros da API |
| `ui-theme` + `motion.theme.ts` | tokens de movimento (`snap`/`ui`/`gentle`/…) |

Código novo (o catálogo não tem equivalente — justificação de uma linha cada):

- **`rede.tsx`: visualizador de ativações** — o catálogo não traz visualizador de rede (`sparkline` é série
  temporal, `progress-bar` é barra): grelha SVG por camada, cor por `|a|`. **Sem arestas**, porque o contrato
  traz ativações e não pesos — desenhar ligações seria inventar dados.
- **`rosa-ventos.tsx`: rosa dos ventos viva** — mostrador polar de azimute/elevação, ausente do catálogo
  (`sparkline` é série temporal e `progress-bar` é barra): SVG com `transform`/`opacity` apenas.
- **`rpi5.tsx`: painel do computador de bordo** — o catálogo não tem cartão de especificações nem indicador de
  saúde ligado a telemetria; usa `Card` + `ProgressBar` + `AnimatedNumber` e classes semânticas.
- **`ajuda.tsx`: a folha de ajuda** — usa `sheet` + `accordion` do catálogo e guarda o conteúdo como DADOS
  (`SECOES_AJUDA`), para acrescentar uma explicação sem tocar em JSX.
- **`controlos.tsx`: `key={geracao}` no REINICIAR** — o `hold-to-confirm` instalado é de **um disparo** (o
  `done` interno só volta com `reset()`, que ele não expõe em `mode="callback"`): remontar por `key` volta a
  armar o botão sem tocar no source instalado.

## Adaptar ao teu robô

Muda **só** `src/lib/config.ts` (`METRICAS`, `ROTULOS_OBS`, `ROTULOS_ACT`, `UNIDADE_CTRL`, `ROTULO_CTRL`,
`NOME_EXPERIMENTO`). Os componentes, as SECÇÕES e os textos da ajuda «?» leem essa configuração — a adaptação
é um ficheiro. Nada de tamanhos fixos: o site desenha N entradas e M saídas conforme a telemetria.

## Testar contra um backend falso

Qualquer servidor stdlib que responda ao contrato serve (mock que serve o `dist/` e a API, com os pedidos
registados em JSONL). Verificação feita neste template: `npm run build` limpo (`tsc -b` + `vite build`) e
`google-chrome-stable --headless=new --dump-dom` sobre o `dist/` servido pelo `sim_site.py` **sem** erros de
JS nem `undefined` no DOM.

## Atribuição da imagem do painel

`src/assets/rpi5.webp` é uma **ilustração de referência** (Raspberry Pi **Model B+**, 2014 — não é um Pi 5):
Lucasbosch, Wikimedia Commons, **CC BY-SA 3.0**. A atribuição aparece no painel e nos textos da ajuda; os
números mostrados são do ALVO (Pi 5) e vêm citados no `RPI5_SPECS` do `sim_site.py`.
