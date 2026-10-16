# Sistema de controlos — associar teclas a ações e controlar o objeto

O fluxo completo de tecla → ação no mujoco-lab (contratos r11–r13, `experiments/09_drone_hover_rl/`),
e o checklist para acrescentar uma ação ao teu objeto sem perder tempo. Fontes verificadas:
`experiments/09_drone_hover_rl/INTERFACE.md` §0 (contrato), `sim_site.py` (rotas), `env.py`
(`definir_comando_teclas`), `site/src/lib/voo.ts` (teclado do site), CoALA `processo-interface-padrao`.

## Quando ler este arquivo
- Acrescentar uma tecla/ação ao teu objeto (ligar motor, detonar carga, trocar modo…).
- Criar um novo experimento com site/cockpit e perceber por onde passa um comando.
- Depurar "a tecla não faz nada" (o eco mostra o quê?).

## 1. O fluxo (estado, não evento)

```
tecla (site) ──keydown/keyup──► POST /api/<bloco>  {…, "seq": do SERVIDOR}
                                    │  validação estrita + escrita ATÓMICA
                                    ▼
                       ficheiro de controlo (out/controle_*.json)  ← bloco + assinatura
                                    │  runner lê a cada passo
                                    ▼
        runner (sim_view.py) ──1× por MUDANÇA de assinatura──► env.definir_*() ──► mj_step
                                    │
                                    ▼
        telemetria JSONL (~10 Hz) + HUD SSE (GET /api/hud, 50 Hz) ──► painel (ECO honesto)
```
Princípios do contrato (não os quebres):
- **Estado, não evento**: o site manda o ESTADO das teclas a cada keydown/keyup (keydown=true,
  keyup=false); quem aplica decide o que isso significa. Nunca mandes "dispara" sem estado.
- **`seq` é do servidor**: o corpo do POST nunca o leva; o servidor carimba e o eco devolve.
- **Validação estrita**: faixas/ tipos verificados (erros claros em stderr, exit 1); teclas em falta
  valem SOLTA e chaves desconhecidas são ignoradas em silêncio (um ficheiro com lixo não rebenta).
- **Escrita atómica** do ficheiro de controlo (lock + escrita completa) — uma escrita parcial nunca
  reescreve o que outro pedido legítimo escreveu.
- **ECO honesto**: o site mostra o pedido E o que está mesmo a ser aplicado (tecla→eco medido: 10 ms).

## 2. Checklist — adicionar UMA tecla/ação (7 pontos)

1. **API do ambiente** (`env.py` ou `lab/<obj>.py`): `definir_<acao>(...)` em unidades físicas +
   estado guardado + eco na telemetria (o que se pediu × o que se aplica).
2. **Bloco de controlo**: um campo novo no JSON (ex.: `"detonar": false` ou `"empuxo": {...}`) com
   faixas validadas; a assinatura do bloco muda SÓ quando o estado muda.
3. **Rota** (`sim_site.py`): `POST /api/<nome>` com validação estrita, escrita atómica no controlo,
   `seq` do servidor e erro claro (ver `POST /api/voo` em `sim_site.py:1134` como molde).
4. **Runner** (`sim_view.py`): aplica o bloco 1× por mudança de assinatura (não a cada passo!) via
   `env.definir_*` — e o reinício/loop não pode reverter um pedido legítimo (defeito medido em 2026-10-09).
   EXCEÇÕES idempotentes (verificado 2026-10-15): o eco do modo clássico (`_eco_voo`, r12) re-aplica
   `definir_comando_teclas/definir_v_ref` a cada passo de decisão, e `reaplicar()` re-aplica os blocos
   após `env.reset` — o «1×» vale para o GATILHO dos blocos-tecla, não como invariant de todo o runner.
5. **Site** (`site/src/lib/<bloco>.ts` + componente): funções PURAS de teclado (testáveis em node, sem
   DOM — molde `voo.ts`), keycap que acende com o ESTADO real, `fetch` do POST no keydown/keyup.
6. **Contrato** (`INTERFACE.md` §0): documenta tecla, semântica, faixas, eco. É literal — deploy e
   dashboard dependem dele.
7. **Prova** (`teste_*.py`): tecla → eco → física, com MUTAÇÃO (se a tecla não existisse, o teste falha?).
   Molde: `teste_cockpit.py` (5 secções + 7 mutações) e `teste_controle_voo.py`.

## 3. Teclas já ocupadas (contrato r13) — escolhe livres
| Ocupadas | Livres sugeridas |
|---|---|
| W A S D Q E (voo) · Z X C (yaw) · B (bola) · V (vento/olhar) · F (vista) · R (reiniciar) · 1–8 (janelas) | G H J K L · U I O P · T Y M N · 0 9 |
Na janela nativa (`view.py`/viewer): ESPAÇO pausa · Q/Esc fecha. Reserva sempre uma tecla de EMERGÊNCIA
(desligar tudo) e documenta-a no `INTERFACE.md`.

## 4. Objeto novo num experimento novo
- Começa pelos templates do laboratório: `lab-padrao` (env Gymnasium + run + train + view + deploy +
  site com painel RPi 5) e `front-conexao` (a PONTE site↔simulador: 2 JSON + 6 rotas, contrato literal em
  `assets/templates/front-conexao/CONTRATOS.md`) — `python3 .agents/mujoco-lab-coala-agent-skill/scripts/new_experiment.py <nome> --template lab-padrao`.
- O módulo do ambiente é a "interface do lado de lá": `novo_env()`, `acao_para_ctrl()`, `definir_vento*()`,
  métricas do painel — tudo o que o bridge espera está tabelado no `CONTRATOS.md`.
- Para o teu objeto: acrescenta `definir_<objeto>()` + um bloco novo e segue o checklist §2.
- Teclado do `view.py` (janela, sem site): `key_callback(keycode)` no `launch_passive` — só PREMÇÃO
  (sem keyup) ⇒ pulsos; para "segurar-tecla" usa o fluxo do cockpit acima.

## 5. Orçamentos e desempenho (medições reais desta máquina)
- Tecla→eco ~10 ms · HUD 50 Hz (SSE) · telemetria JSONL ~10 Hz · streams ~49,7 fps 1080p.
- **Medir só com a máquina livre** (avaliações em paralelo falseiam fps e tempo real).
- UX do cockpit 29→88/100 (`pesquisas/ux-cockpit-avaliacao-*.json`) — segue o padrão r13 (keycaps ao
  vivo, painel honesto, botões de 3 estados) quando integrares controlos novos.

## 6. Quando o controlo vai para o hardware (RPi 5/Arduino)
O MESMO contrato continua a valer do lado do simulador (SITL); o que muda é quem aplica o `definir_*`:
ver `references/rpi5-hardware.md` (PWM/GPIO/ESC, orçamentos de tempo, firmware portátil).
