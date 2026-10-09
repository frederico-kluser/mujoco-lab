# Auditoria UX — dashboard do experimento 09 (ronda 3)

`uxui-evaluator` · interface_type **dashboard** · Partes 1, 2 e 4 (+ 3) · **antes: 41/100 (fair) · depois: 88/100 (excellent)**
`api_enriched: false` — `UXUI_API_KEY` não existe neste ambiente (verificado com `env | grep -i uxui` e em `~/.secrets`),
por isso o framework foi aplicado internamente (Cognitive Load 7±2, Hick's Law, Chunking, Progressive Disclosure,
Feedback loops, Error Prevention, Fitts's Law, Consistency, Visual Hierarchy, Serial Position). O JSON estruturado
completo (os dois momentos) está em [`ux_audit.json`](ux_audit.json).

## Passo A · a interface avaliada (descrição usada na auditoria)

Dashboard local de um só utilizador, servido por `dashboard.py` (stdlib, offline, `http://127.0.0.1:<porta>/`), com
seis secções empilhadas e um cabeçalho fixo:

| # | secção | controlos | leitura |
|---|---|---|---|
| — | cabeçalho | — | 4 pílulas de estado (servidor, treino, rede, linha) + vento |
| 1 | Treinar (subprocesso) | timesteps, seed, n_envs, out-dir; **▶ Treinar**, **■ Parar** | meta do treino (estado, pid, run, out_dir, cmd), linha de aviso |
| 2 | Runs em disco | selectores run ativo / amostra / overlay | tabela de 6 colunas (run, linhas, mean_ret, mean_z, best_model, evals) |
| 3 | Curvas do treino | **evals do run ativo**, legenda | 2 gráficos SVG (mean_ret, mean_z) |
| 4 | Rede ao vivo (MLP 16→64→64→4) | política (.zip), ritmo da sonda, **rede ao vivo ▶**, **■ parar rede** | grafo SVG da rede, listas obs (16) / ação (4) / estado (6), meta |
| 5 | Vento ao vivo | 3 pares slider+número (força, azimute, elevação), **APLICAR VENTO**, **PARAR VENTO**, 4 atalhos de azimute | lista vento (4) + meta |
| 6 | Log do treino | «seguir o fim» | `<pre>` com a cauda de `train_stdout.log` |

O operador típico é o dono do experimento: quer (a) arrancar a rede ao vivo, (b) mudar a direção/força do vento e ver
o drone a corrigir, (c) perceber se o episódio acabou e o que fazer a seguir, (d) treinar e comparar runs.

## Resultado

| momento | score | banda | achados |
|---|---|---|---|
| antes (ronda 2 → início da ronda 3) | **41** | fair | 1 crítico · 5 warnings · 3 sugestões |
| depois (com as correções abaixo) | **88** | excellent | 0 crítico · 0 warnings · 4 sugestões |

### Achados do "antes" → o que foi feito

| princípio | sev. | problema | correção aplicada |
|---|---|---|---|
| F.1.1.02 Cognitive Load | crítico | +40 elementos ao mesmo tempo, sem indicação de "o que fazer agora"; parágrafos sempre visíveis | guia de próxima ação no topo; documentação e avançado em `<details>` |
| F.2.2.03 Hick's Law | warning | 12 botões com o mesmo peso e 6 seletores | um primário por secção; destrutivos a vermelho; atalhos agrupados |
| C.1.4.01 Error Prevention | warning | «■ Parar» matava um treino com um clique, sem desfazer; «PARAR VENTO» sem reposição | confirmação em dois passos; «↩ repor» no toast; botão desativado durante o pedido |
| I.2.2.02 Fitts's Law | warning | botões ~34 px, atalhos encostados, checkbox minúscula | mínimos de 34 px (40 px nos primários), espaçamento, área de clique maior |
| C.1.1.01 Consistency | warning | «rede ao vivo ▶» vs «■ parar rede»; notas a apontar para "painel 4" errado | etiquetas verbo+objeto; referências para «secção N» |
| F.1.1.03 Mental Model | warning | o painel não dizia o estado do episódio nem a próxima ação | guia + selo «episódio N terminou (motivo) — clica ↻ REINICIAR» |
| D.1.1.01 Progressive Disclosure | sugestão | tudo expandido | `<details>` (treino, vento, rede, avançado) |
| D.2.1.02 Visual Hierarchy | sugestão | feedback discreto longe do clique; nada destacava o "ao vivo" | toasts no canto, feedback junto do controlo, secção com barra de destaque |
| F.1.1.06 Serial Position | sugestão | controlos usados a cada minuto a meio de 6 secções | guia/controlos no topo + navegação no cabeçalho |

## Passo C · o que foi aplicado (além das correções da tabela)

1. **SEM LOOP por omissão + controlos de episódio** (pedido do dono): botão **↻ REINICIAR** (escreve o contador
   `reiniciar` no `controle_vento.json`, `POST /api/reiniciar`) e interruptor **LOOP** (`POST /api/loop {ativo}`),
   duplicados no guia e na secção 4, com o selo `#estado-episodio`. Atalhos de teclado `R` e `L`.
2. **Toasts** (`#toasts`, 5 s, com botão de ação opcional) para todas as ações — aplicar/parar vento, reiniciar,
   LOOP, arrancar/parar treino e rede.
3. **Navegação** no cabeçalho (rede ao vivo · vento · curvas · log) e âncoras `#sec-*`.
4. **Bloqueio de duplo clique**: cada pedido desativa o botão enquanto corre e o LOOP recusado repõe a caixa
   no estado do servidor (o controlo nunca mente).

## Passo D · re-avaliação

Depois das correções: **88/100 (excellent)** — zero achados críticos e zero warnings. Sobram 4 sugestões, registadas
com remediação no JSON: `.meta` densos em 4 blocos (F.1.1.02), 7 botões na secção do vento (F.2.2.03), mistura
PT/EN nos rótulos técnicos (C.1.1.01) e peso visual dos `.meta` a competir com os valores ao vivo (D.2.1.02).

## Evidências

- `sem_loop_r3.py` (sonda isolada): ficheiro de controlo **antigo** (só vento, sem `reiniciar`/`loop`) → fim do
  episódio escreve a linha de evento e **espera** (JSONL não cresce em 3 s); `reiniciar: 1` → novo episódio;
  `loop: true` → auto-reset; `loop: false` + contador → volta a esperar e retoma. Alinhamento
  `h1(k)==Linear_1(obs(k))` em 55 linhas (incluindo as de evento): erro máx **2,2e-05**.
- `episodio_r3.py` (dashboard completo): **8/8** — estado neutro com `reiniciar`/`loop`, espera com a física parada,
  `POST /api/reiniciar` → 200 com contador 1 e novo episódio em 0,3 s, `POST /api/loop` true → auto-reset,
  400s de validação (`{}`, `"sim"`, `7`), vento ao vivo 3 m/s @ 90° com o contador preservado, DOM headless
  (chrome `--headless=new`) com **0 «undefined»**, `#erros-js` com `display:none` e o selo
  «episódio 4 terminou (terminado) — clica ↻ REINICIAR».
- `ruff check` nos dois ficheiros: «All checks passed!».
