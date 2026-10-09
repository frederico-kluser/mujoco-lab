# Auditoria UX — secções selecionáveis (site do 09_drone_hover_rl)

Skill `uxui-evaluator` · interface tipo **dashboard** · Parts **1 / 2 / 4** (cognitive load 7±2, Miller/chunking,
Hick, progressive disclosure, visual hierarchy, Fitts, feedback, error prevention) · `api_enriched: false`
(`UXUI_API_KEY` ausente no env e em `~/.secrets` → aplicado por conhecimento interno do framework).

**Antes: score 43 (fair) · Depois: score 94 (excellent)** — JSON estruturado em `ux_audit_seccoes.json`.

## Antes (43 · fair) — principais violações

| # | princípio | gravidade | problema |
|---|---|---|---|
| 1 | F.1.1.02 Cognitive Load | critical | ~20 blocos simultâneos (curvas, rede 16→64→64→4, RPi 5, obs 16, act 4, vento, dinâmico, episódio) vs. 7±2 |
| 2 | I.2.2.02 Fitts | critical | REINICIAR/LOOP no FIM da coluna lateral — fora do ecrã ao vigiar o voo, ação crítica com scroll |
| 3 | D.1.1.01 Progressive Disclosure | warning | sem vistas por tarefa: tudo exposto sempre |
| 4 | F.2.2.03 Hick | warning | ~15 decisões de controlo visíveis ao mesmo tempo |
| 5 | F.1.1.04 Miller/chunking | warning | blocos sem «chunks» nomeados e escolhíveis |
| 6 | F.1.1.06 Serial Position | suggestion | «episódio terminado» escondido dentro do cartão lateral |
| 7 | C.1.4.01 Error Prevention | suggestion | sem atalhos documentados nem guardas de erro |

## O que foi aplicado (fixes)

1. **Seletor de secções** (`smooth-tabs` do catálogo Motion UI — cascata `motion-ui.mjs search`):
   **Operação** (selo de estado + modelo + valores atuais z/dist_xy/yaw_err/vento_vel + 4 curvas **grandes**),
   **Rede** (rede 16→64→64→4 + obs + ações), **Vento** (sliders + rosa + dinâmico), **Bordo** (RPi 5),
   **Tudo** (layout completo). Só uma secção visível de cada vez; blocos escondem com `hidden` **sem
   desmontar** → os updates (GET /api/sim) continuam com a secção escondida e os valores chegam frescos.
2. **Persistência**: secção ativa em `localStorage` (`09_drone_hover_rl:seccao`), recuperada ao reabrir;
   atalhos **1–5** documentados na ajuda «?» e nas abas (kbd), desativados dentro de campos.
3. **Crítico nunca se esconde**: faixa `role="alert"` na barra fixa (episódio terminado · API em baixo),
   com prioridade para a falha de ligação (o estado do episódio fica velho quando a API cai).
4. **Barra fixa do topo**: seletor + **REINICIAR** (hold 1 s) + **LOOP** acessíveis de QUALQUER secção.
5. **Ajuda «?»** alargada: secção nova explica o seletor, o que cada secção serve, atalhos, persistência
   e que os updates continuam com a secção escondida.
6. Semântica preservada: nenhum auto-restart; nenhum controlo de vento reinicia; rosa, RPi 5, todos os
   controlos dinâmicos e os 0 `POST /api/reiniciar` automáticos mantidos.

## Depois (94 · excellent)

Forças reconhecidas: carga cognitiva (≤ 5 blocos por vista), progressive disclosure por tarefa, chunking
nomeado (F.1.1.04), Hick (5 opões estáveis + atalhos), Fitts (barra fixa, sem scroll), error prevention
(alert sempre visível + guarda de atalhos + hold-to-confirm), mental model («Operação = vigiar o voo»,
escolha persistente).

Restam 2 sugestões (−6 pts): «Tudo» reexpor o conjunto completo (deliberado, vista de diagnóstico) e a
guarda de atalhos ainda não cobrir alvos `role="slider"`.

## Evidência (provas headless, mock /api/sim a evoluir)

- `chrome --headless=new --dump-dom`: seletor com 5 abas (`role="tab"`, `aria-selected`) + barra crítica.
- Puppeteer (Chrome do sistema): **24/24 provas** — secções exclusivas (blocos alheios `hidden`), «Tudo»
  completo, crítico (terminado e API em baixo) visível em todas, `localStorage` após reload, valores
  frescos com «Operação» escondida (z 1,4725 → 1,4905 escondido; 1,4995 ao voltar), REINICIAR/LOOP
  presentes em qualquer secção, atalhos 1–5 + guarda em campos, **0 POST /api/reiniciar**, **0 erros JS**.
- Funcional: hold de 1 s → `POST /api/reiniciar` (1); LOOP ON → `POST /api/loop` (1); APLICAR VENTO →
  `POST /api/vento` (1); 0 erros JS.
- `npx tsc -b` e `npm run build` com exit 0.