# Site do experimento 09 — drone a pairar (política RL ao vivo)

Aplicação **React + TypeScript + Vite + Tailwind/shadcn**, construída com a skill `motion-plus-ui`
(registry `@motion`) e servida pelo backend `sim_site.py`, que também expõe a API. Uma página, sem
navegação: cabeçalho · curvas · rede 16→64→64→4 · observação/ação · controlos.

## Arranque

```bash
npm install          # precisa de MOTION_TOKEN (registry @motionplus) — ver .npmrc
npm run dev          # desenvolvimento (o proxy da API é a mesma origem: usa o sim_site.py)
npm run build        # tsc -b && vite build → dist/ (index.html + assets/, caminhos absolutos)
npx tsc -b           # só o type-check
```

Em produção quem serve o `dist/` é o `sim_site.py` (mesma origem ⇒ `fetch("/api/sim")` funciona sem
CORS nem configuração). Para apontar o `dist/` estático a **outro** porto (testes):
`index.html?api=http://127.0.0.1:8765` ou `window.__SIM_API_BASE__`.

## Contrato da API (é o que o site consome)

| pedido | resposta |
|---|---|
| `GET /api/sim` | `{estado:"a_correr"\|"episodio_terminado", ep, passo, retorno, vento:{vel,azimute,elevacao,ativo}, linhas:[{t,estado,ep,passo,retorno,z,dist_xy,yaw_err,vento_vel,vento_azim,obs[16],act[4],h1[64],h2[64],ctrl?[4]}]}` |
| `GET /api/state` | resumo; o site lê **`modelo_nome`** primeiro (`pasta/ficheiro.zip`, o rótulo legível) e só depois `modelo`/`model`/… — e, se existirem, `mg`, `thrust_max`, `momento_max`, `tau_escala` |
| `POST /api/vento` | `{vel 0–5, azimute 0–360, elevacao −90–90}` → 200/400 |
| `POST /api/reiniciar` | → `{contador: n}` |
| `POST /api/loop` | `{ativo: bool}` → 200 |

Polling de `GET /api/sim` a **2,9 Hz** (350 ms, dentro dos 2–5 Hz do contrato); sem websockets.
O histórico é acumulado por `ep:passo`, portanto tanto serve um backend que devolva tudo como um que
devolva só a cauda; episódio novo ⇒ histórico novo.

**Nome do modelo no cabeçalho:** mostra sempre `pasta/ficheiro.zip` (nunca o caminho absoluto — é um
rótulo de painel, não um explorador de ficheiros, e a página pode ser partilhada). `lib/sim.ts`
(`nomeModeloLegivel`) aceita `/` e `\`, ignora barras finais e, acima de **34 caracteres**
(`MODELO_LEGIVEL_MAX`), corta no **miolo** para o fim do ficheiro continuar legível (`final.zip` vs
`best_model.zip`). 34 e não 26 porque os nomes deste laboratório cabem inteiros
(`vento_r9_polir_vento3/final.zip` = 31, `out/runs/seed0/best_model.zip` = 29).

**Semântica:** o site **nunca** reinicia sozinho. `estado=episodio_terminado` mostra
«episódio N terminado — clica REINICIAR»; com o **LOOP** ligado quem reinicia é o **backend**.

## Estrutura

```
src/
  main.tsx                    MotionUIThemeProvider (uma vez, tema de ../motion.theme) + ThemeProvider
  App.tsx                     grelha: cabeçalho · principal · controlos (sticky) · pilha de avisos
  lib/sim.ts                  tipos do contrato, normalização defensiva, rótulos das 16 obs/4 ações
  lib/api.ts                  fetch dos 4 endpoints (erros legíveis; `?api=` para testes)
  hooks/use-sim.ts            polling, fusão do histórico, estado de ligação, ações (POST)
  components/sim/cabecalho.tsx    estado do episódio, contadores, modelo, ligação
  components/sim/curvas.tsx       z(t) com a linha do alvo 1,0 · yaw_err · retorno · vento_vel
  components/sim/rede.tsx         ativações 16→64→64→4 (SVG, cor por |a|)
  components/sim/observacoes.tsx  tabela das 16 obs (obs/cru/barra) + ação (empuxo em N e momentos)
  components/sim/controlos.tsx    sliders de vento + APLICAR/PARAR · REINICIAR (hold) · LOOP
  components/sim/avisos.tsx       toasts das ações (toast-stack)
  components/motion-ui/**     componentes do registry @motion (source do CLI — não editar)
  components/ui/**            primitivos shadcn (button, card, slider)
```

## Componentes `@motion` usados

| componente | onde |
|---|---|
| `sparkline` | as 4 curvas (`curvas.tsx`), com a linha do alvo na `grid` |
| `animated-number` | contadores do cabeçalho e valor atual de cada curva |
| `stagger-reveal` | entrada do título do cabeçalho (`splitText` linha a linha + seguidor) |
| `progress-bar` | barras da observação e da ação (com `referenceTick` no empuxo de hover) |
| `hold-to-confirm` | botão **REINICIAR** (manter 1 s) |
| `multi-state-button` | **APLICAR VENTO** (pronto/a enviar/ok/erro) |
| `segmented-toggle` | **LOOP** (OFF por omissão) |
| `toast-stack` | avisos das ações e erros da API |
| `skeleton` (`SkeletonReveal`) | estado de carregamento antes da primeira linha |
| `segmented-toggle`, `ui-theme`, `motion.theme.ts` | tokens de movimento (`snap`/`ui`/`gentle`/…) |

Passo 4 da cascata (código novo), com justificação de uma linha cada:

- **`rede.tsx`** — o catálogo não tem visualizador de ativações (`sparkline` é série temporal,
  `progress-bar` é barra): grelha SVG por camada, cor por `|a|`. Sem arestas porque o contrato só traz
  ativações, não pesos — desenhar ligações seria inventar dados.
- **`controlos.tsx` · rosa dos ventos** — mostrador polar de azimute/elevação, também ausente do
  catálogo; 30 linhas de SVG com `transform: rotate` (só transform).
- **`controlos.tsx` · `key={geracao}` no REINICIAR** — o `hold-to-confirm` instalado é de **um disparo**
  (o `done` interno só volta com `reset()`, que ele não expõe em `mode="callback"`): remontar por `key`
  volta a armar o botão e repõe a escala, sem tocar no source instalado.
- **`stats-live-panel` (avaliado, descartado)** — foi instalado durante a avaliação da cascata e
  removido: é uma secção-demo **fechada**, que gera os próprios números de engagement e só aceita
  `eventsBaseline`/`tickIntervalMs` — não dá para lhe passar telemetria real. Ficou a dependência que
  ele trouxe, `animated-number`, e o padrão de painel; os valores no ecrã são do MuJoCo.

## Testar contra um backend falso

Qualquer servidor stdlib que responda ao contrato serve. O teste feito nesta máquina: mock em `$TMPDIR`
que serve o `dist/` **e** a API, com os pedidos registados em JSONL, mais
`google-chrome-stable --headless=new --dump-dom` (0 erros de JS, 0 `undefined`) e Puppeteer para a
interação (sliders → `POST /api/vento {vel,azimute,elevacao}`, segurar REINICIAR → `POST /api/reiniciar`,
LOOP → `POST /api/loop {ativo}`).
