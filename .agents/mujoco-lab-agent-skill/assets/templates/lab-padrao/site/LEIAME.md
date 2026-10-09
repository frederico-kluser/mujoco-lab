# site/ — o site do `lab-padrao` (todas as métricas e todos os controlos)

Aplicação **React + TypeScript + Vite + Tailwind/shadcn**, construída com a skill `motion-plus-ui`
(registry `@motion`) e servida pelo backend `sim_site.py`, que expõe também a API. Uma página, sem navegação:
cabeçalho · curvas · rede da política · observação/ação · controlos (vento, REINICIAR, LOOP).

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
| `GET /api/sim` | `{estado:"a_correr"\|"pausado"\|"episodio_terminado", ep, passo, retorno, vento:{vel,azimute,elevacao,ativo}, linhas:[{t,estado,ep,passo,retorno,theta,erro,omega,vento_vel,vento_azim,obs[],act[],ctrl[],h1[],h2[]}], modelo_nome, sim_vivo, loop}` |
| `GET /api/state` | resumo (o mesmo sem `linhas`, mais `contador_reiniciar`, `n_linhas`, `modelo`, `modelo_motivo`) |
| `POST /api/vento` | `{vel 0–5, azimute 0–360, elevacao −90–90}` (subconjunto aceite) → 200/400 |
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
  App.tsx                        grelha: cabeçalho · curvas · rede · obs/ação · controlos · avisos
  lib/sim.ts                     ★ CONFIGURAÇÃO (METRICAS, ROTULOS_OBS/ACT, unidades) + tipos + leitura defensiva
  lib/api.ts                     fetch dos endpoints do contrato (erros legíveis; `?api=` para testes)
  hooks/use-sim.ts               polling, fusão do histórico por ep:passo, estado de ligação, ações (POST)
  components/sim/cabecalho.tsx      estado do episódio, contadores, política em uso, ligação
  components/sim/curvas.tsx         as 4 curvas de METRICAS, com a linha do alvo/zero
  components/sim/rede.tsx           ativações obs→h1→h2→act (SVG, cor por |a|; sem arestas = sem inventar pesos)
  components/sim/observacoes.tsx    tabela da observação (obs[i]) + painel da ação (act e o `ctrl` físico)
  components/sim/controlos.tsx      vento (sliders + rosa dos ventos) · REINICIAR (hold 1 s) · LOOP
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
| `progress-bar` | barras da observação e da ação |
| `hold-to-confirm` | botão **REINICIAR** (manter 1 s) |
| `multi-state-button` | **APLICAR VENTO** (pronto/a enviar/ok/erro) |
| `segmented-toggle` | **LOOP** (OFF por omissão) |
| `toast-stack` | avisos das ações e erros da API |
| `ui-theme` + `motion.theme.ts` | tokens de movimento (`snap`/`ui`/`gentle`/…) |

Código novo (o catálogo não tem equivalente — justificação de uma linha cada):

- **`rede.tsx`: visualizador de ativações** — o catálogo não traz visualizador de rede (`sparkline` é série
  temporal, `progress-bar` é barra): grelha SVG por camada, cor por `|a|`. **Sem arestas**, porque o contrato
  traz ativações e não pesos — desenhar ligações seria inventar dados.
- **`controlos.tsx`: rosa dos ventos** — mostrador polar de azimute/elevação, também ausente do catálogo
  (~30 linhas de SVG com `transform: rotate`).
- **`controlos.tsx`: `key={geracao}` no REINICIAR** — o `hold-to-confirm` instalado é de **um disparo** (o
  `done` interno só volta com `reset()`, que ele não expõe em `mode="callback"`): remontar por `key` volta a
  armar o botão sem tocar no source instalado.

## Adaptar ao teu robô

Muda **só** a secção «CONFIGURAÇÃO» de `src/lib/sim.ts` (`METRICAS`, `ROTULOS_OBS`, `ROTULOS_ACT`,
`UNIDADE_CTRL`, `NOME_EXPERIMENTO`) e, se preciso, o `sim_view.py` (as 3 métricas da linha `amostra()`).
Nada de tamanhos fixos: o site desenha N entradas e M saídas conforme a telemetria.

## Testar contra um backend falso

Qualquer servidor stdlib que responda ao contrato serve (mock que serve o `dist/` e a API, com os pedidos
registados em JSONL). Verificação feita neste template: `npm run build` limpo (`tsc -b` + `vite build`) e
`google-chrome-stable --headless=new --dump-dom` sobre o `dist/` servido pelo `sim_site.py` **sem** erros de
JS nem `undefined` no DOM.
