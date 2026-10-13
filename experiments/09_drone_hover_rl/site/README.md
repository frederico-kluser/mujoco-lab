# Site do experimento 09 — o COCKPIT do drone

Aplicação **React 19 + TypeScript + Vite 8 + Tailwind 4** servida pelo backend `sim_site.py` (que também
expõe a API). Desde 2026-10-12 (contrato **r13**, `../INTERFACE.md` §0) o site é um **cockpit**: um ecrã
único de 100svw × 100svh, **sem scroll de página**, onde a vista do drone é o fundo e tudo o resto se
sobrepõe ou se abre a pedido.

O que o dono pediu e onde está:

| pedido | resposta |
|---|---|
| «sem scroll, sempre a visão em 1.ª ou 3.ª pessoa» | a **VISTA** (stream MJPEG) cobre o viewport; `F` troca; a outra fica numa miniatura |
| «chamo os controles como janelas que posso abrir» | a **DOCA** abre **JANELAS** flutuantes (arrastáveis, posição guardada) |
| «o modo de controlar já vem ativado» | não há ARMAR: as teclas valem desde o arranque (`ativo: true` em todos os `POST /api/voo`) |
| «não quero opções, quero o melhor» | sem seletor de controlador nem de loop — voa o que ganhou na medição |
| vento com três botões | janela **Vento**: LIGADO · INTENSIDADE · ALEATORIEDADE (+ a direção numa bússola) |
| seguir a bola | janela **Bola** / tecla `B`: retículo sobre a bola e erro de centragem no HUD |

A avaliação UX que motivou o redesenho (9 achados) está em `pesquisas/ux-cockpit-avaliacao-antes.json`.

## Arranque

```bash
npm install            # precisa de MOTION_TOKEN (registry @motionplus) — ver .npmrc
npm run build          # tsc -b && vite build → dist/ (o sim_site.py serve-o na mesma origem)
npm run dev            # desenvolvimento: /api/* é encaminhado para o sim_site.py (porto 8080)
SIM_API=http://127.0.0.1:8793 npm run dev   # …ou para outro backend
npm run lint && npm run typecheck
```

Em produção quem serve o `dist/` é o `sim_site.py` (mesma origem ⇒ sem CORS). Para apontar um `dist/`
estático a outro porto: `index.html?api=http://host:porto` ou `window.__SIM_API_BASE__` — só funciona se
esse servidor anunciar CORS (o `sim_site.py` não anuncia: em desenvolvimento usa-se o proxy do Vite).

## O ecrã

```
┌ ● A VOAR │ MANUAL            ── fita de rumo ──             ▭ 97 %  24,7 V  62 min ┐
│  (▲ À PROCURA erro 2,3°)      [ ■ CAIU  manter R ]  ← avisos                      │
│                                                                                    │
│        VEL                        ─ ─                             ALT             │
│        0,4 m/s  (◦)          ──── ─∨─ ────   ← horizonte + mira   1,02 m  ▲ 0,1   │
│                                   ─ ─        (só 1.ª pessoa)                      │
│ ┌──────────┐                                                                      │
│ │ miniatura│                                              ⊙ VENTO 2,1 m/s  Q W E  │
│ └──────────┘                                                 DE FRENTE     A S D  │
│ [⇄ 1.ª PESSOA F]        [ 1 2 3 4 5 6 7 8 │ ⟲ REINICIAR R ]                Z X C  │
└────────────────────────────────────────────────────────────────────────────────────┘
```

1. **VISTA** (`components/cockpit/vista.tsx`) — `<img>` com `GET /api/fpv.mjpg` (1.ª pessoa) ou
   `GET /api/simulacao.mjpg` (3.ª pessoa), `object-fit: cover`. A miniatura (em baixo à esquerda, a
   convenção das estações de solo) mostra a OUTRA vista pelos `.jpg` a ~4 fps — não um segundo MJPEG: o
   HTTP/1.1 só dá 6 ligações por origem e já há um stream e o SSE abertos. Em 3.ª pessoa **arrasta-se a
   própria vista** para orbitar, a roda aproxima e o duplo clique repõe (`POST /api/camera`, ≤ 20
   envios/s + envio final). Sem quadros diz-se **SEM IMAGEM** com o motivo (sem ligação · sem câmara ·
   câmara desligada, com o botão LIGAR · câmara parada · stream caído, a religar).
2. **HUD** (`components/cockpit/hud.tsx`, `pointer-events: none`) — ver «HUD» abaixo.
3. **DOCA** (`components/cockpit/doca.tsx`) — 8 ícones com o nome por baixo e o número do atalho no canto e o **REINICIAR** de
   manter premido (0,9 s; o gesto é o `hold-to-confirm` do Motion UI, que a tecla `R` também conduz).
4. **JANELAS** (`components/cockpit/janela.tsx` + `janela-*.tsx`):

| tecla | janela | conteúdo | precisa do `/api/sim`? |
|---|---|---|---|
| `1` | **Voo** | mapa das teclas (também se primem com o rato), velocidade pedida, rumo: rodar/fixar | não |
| `2` | **Bola** | interruptor SEGUIR A BOLA, velocidade da bola, alvo ao vivo, erro e distância | não |
| `3` | **Vento** | LIGADO · INTENSIDADE 0–5 m/s · ALEATORIEDADE · bússola da direção · vento de agora (real) · «o drone sente» (estimado a bordo, `vento_bordo` do HUD) | não |
| `4` | **Sensores** | `PainelVoo` (estimado vs real, sensores) | sim |
| `5` | **Energia** | carga, V, A, W, autonomia, 4 motores, RECARREGAR; detalhe (`PainelBateria`, `PainelMotores`) recolhido | só com o detalhe aberto |
| `6` | **Gráficos** | `Curvas` | sim |
| `7` | **Sistema** | quem voa (`QuemFazOQue`, sem seletor), streams medidos, `PainelHardware`; com a política RL: `Rede`, `TabelaObs`, `PainelAct`, `PainelRpi5` | só em modo RL |
| `8` / `?` | **Ajuda** | as teclas e como ler o ecrã | não |

Com tudo fechado o ecrã tem **12 controlos interativos** (8 da doca, REINICIAR, miniatura, fechar
miniatura, trocar vista).

### Teclas (sempre ativas, exceto com o foco num campo de TEXTO)

`W` `S` `A` `D` frente/trás/esquerda/direita do nariz · `Q` `E` subir/descer · `Z` `C` rodar (manter) ·
`X` fixar o rumo · `B` seguir a bola · `V` vento · `F` trocar a vista · `R` (manter) reiniciar · `1`–`8`
janelas · `?` ajuda · `Esc` fecha a janela da frente. Com Ctrl/Meta/Alt nada é interceptado. Um slider
ou um botão com foco **não** largam o teclado de voo (`eCampoDeTexto`); perder o foco do browser ou
esconder a página solta todas as teclas.

## De onde vêm os dados (e o que NÃO se sonda)

| fonte | ritmo | para quê |
|---|---|---|
| `GET /api/hud` (SSE) | 50 Hz | os instrumentos do HUD e as leituras ao vivo das janelas |
| `GET /api/hud.json` | 5 Hz, **só** se não chega amostra há > 400 ms | fallback do SSE (a idade é a do servidor) |
| `GET /api/state` | ~1 Hz, sempre | `vento_simples`, `bola`, `fpv`/`simulacao`, `hardware`, `controlador`, `voo.pedido` |
| `GET /api/sim` | ~3 Hz, **só com uma janela de detalhe aberta** | histórico de telemetria (200 linhas, ~500 kB por resposta) |
| `…/fpv.jpg` · `…/simulacao.jpg` | ~4 fps, só com a miniatura aberta | a miniatura |

`precisaDeSim` (`lib/cockpit.ts`) decide: Sensores, Gráficos, Energia com o detalhe aberto, ou
Sistema com a política RL. **Medido** (10 s, tudo fechado): 0 pedidos a `/api/sim`, 8 a `/api/state`.
Com a página escondida (`document.hidden`) fecha-se o stream, o SSE, a miniatura e as duas sondagens;
ao voltar reabre tudo.

Escritas: `POST /api/voo` (estado COMPLETO, só quando muda), `/api/vento-simples` e `/api/bola`
(parciais; a arrastar ≤ 10 Hz + envio final), `/api/camera`, `/api/reiniciar`, `/api/bateria`,
`/api/fpv` (só o LIGAR A CÂMARA do estado «sem imagem»).

## HUD

- **Disposição** (convenções QGroundControl / DJI Pilot e de fatores humanos): barra de cima = estado e
  avisos; velocidade à esquerda da mira, altitude à direita; o **centro só leva a mira, o horizonte e o
  retículo da bola** (nenhum texto); em baixo à direita o vento de agora e as teclas.
- **Cor**: seis cores com significado e **nunca só cor** — branco leitura ○ · verde ativo ● · ciano = o
  que o piloto manda (tecla cheia) · magenta = o alvo (a bola) · âmbar atenção ▲ · vermelho perigo ■.
- **Fontes**: `est` (sensores de bordo) para os instrumentos; `real` só onde não há `est` (cf2) e para
  rodar o vento do mundo para o nariz.
- **Estado em linguagem de voo**: A VOAR · NO CHÃO · CAIU · EM PAUSA · A LIGAR · SEM LIGAÇÃO (amostra com
  mais de 1 s) + MANUAL / A SEGUIR A BOLA. Nunca «episódio». Alertas (um de cada vez, o mais grave):
  CAIU («manter R para reiniciar») · SEM LIGAÇÃO · BATERIA CRÍTICA/FRACA · BOLA PERDIDA.
- **Horizonte e retículo CONFORMES**: projetam-se com a focal da câmara de bordo
  (`(H/2)/tan(fovy/2)` × a escala do `cover`) e com a amostra do instante em que o quadro à vista foi
  captado (`atrasoDaImagem`: `fpv.latencia_modelada_ms`, ~116 ms, + meio período do `fps_medido`). Os
  números são sempre os de agora.
  Medido: `erro_tan` = [−0,34456; 0,02345] com `fovy` = 67° cai em (679, 559) px; a bola estava em
  (679, 560).
- **Convenções medidas no runner** (documentadas no cabeçalho de `lib/cockpit.ts`): `roll` > 0 = asa
  direita em baixo; `pitch` > 0 = nariz em BAIXO; `psi` cresce para a ESQUERDA (a fita de rumo também);
  `est.vx/vy` no referencial do rumo; `voo.v_ref` e o vento no mundo; `bola.valido` é independente de
  `bola.estado`.

### Desempenho (requisito)

- A amostra de 50 Hz vive num store **fora do React** (`lib/hud-store.ts`); os instrumentos escrevem
  `transform`/`opacity` em todos os quadros e `textContent` a ≤ 10 Hz, por refs, dentro de **um**
  `requestAnimationFrame` partilhado (`useDesenhoHud`). Para o React só sai o `ResumoHud` (ligação,
  fase, seguidor, alerta), via `useSyncExternalStore`, quando muda.
- Nada mede o DOM por quadro: viewport e focal vêm das props e só mudam no `resize`.
- Animações só com `transform`/`opacity`; `prefers-reduced-motion` desliga a entrada das janelas e o
  pulsar dos alertas.
- Os painéis de detalhe (`components/sim/*`) são carregados a pedido (`components/cockpit/detalhe.tsx`,
  `React.lazy`): o arranque leva só a vista, o HUD e as três janelas principais.
- Arrastar uma janela escreve o `transform` diretamente; a posição só entra no estado ao largar.

## Controlos: estado otimista e «o último vence»

`lib/cockpit.ts` tem os três controlos (`ControloPiloto`, `ControloVento`, `ControloBola`) e o `Emissor`
que partilham; `lib/cockpit-controlos.ts` liga-os ao `fetch`. Regras:

- o ecrã muda **no instante** (os keycaps nunca esperam pela rede);
- nunca há dois POSTs em voo do mesmo controlo, e enquanto um não sai só fica o estado mais recente —
  a ordem das escritas no servidor é a ordem dos gestos;
- `pedir` respeita o intervalo (sliders e bússola ≤ 10 Hz), `largar` é o envio final e sai já;
- o que o `/api/state` diz só é adotado sem gesto local recente (carência de 1,5 s) nem envio a caminho;
  do voo adotam-se só os MODOS (`segui_alvo`, `yaw_alvo`) — recarregar a página a meio de «seguir a bola»
  não desliga o modo na primeira tecla —, e se alguém desarmar por fora o cockpit volta a armar;
- um POST recusado avisa (toast, sem repetir o mesmo erro durante 4 s) e o painel volta ao último que o
  servidor confirmou.

## Janelas

`EstadoJanelas` = as abertas (pela ordem de empilhamento: a última é a da frente, a que o `Esc` fecha) +
a posição onde o dono deixou cada uma, guardado em `localStorage`
(`09_drone_hover_rl:cockpit:janelas:v1`; a vista e a miniatura em `…:cockpit:vista:v1`). A posição
desenhada passa sempre por `encaixar` (dentro do viewport: re-encaixa ao redimensionar) e a altura nunca
passa do espaço entre a barra de estado e a doca — as janelas de detalhe ganham scroll **interno**; as
três principais cabem sem scroll a 1366×768 (350, 438 e 397 px). A ordem no DOM é fixa; quem está à
frente decide-se pelo `z-index` (reordenar nós a meio de um `pointerdown` cancelava o arrasto).

## Estrutura

```
src/
  App.tsx                         composição: Vista + Hud + Doca + Janelas; o teclado; as ligações
  lib/cockpit.ts                  LÓGICA PURA: parser do HUD, projeção (cover), teclas e piloto, vento,
                                  bola, Emissor, controlos otimistas, janelas, órbita, formatação
  lib/cockpit-controlos.ts        as instâncias (piloto, vento, bola, câmara) ligadas à API e aos avisos
  lib/hud-store.ts                SSE + fallback + anel de amostras + o requestAnimationFrame do HUD
  lib/api.ts                      cliente HTTP (r13: enviarVentoSimples, enviarBola, buscarHudJson,
                                  lerCameraEmVigor; enviarCamera devolve o bloco confirmado)
  lib/sim.ts · voo.ts · controlador.ts · camera-gestos.ts · sensores.ts · paragem.ts
                                  contratos e parsers de sempre (o resumo ganhou ventoSimples e bola)
  hooks/use-sim.ts                /api/state a 1 Hz sempre; /api/sim só com `useSim({ ativo: true })`
  hooks/use-cockpit.ts            useResumoHud, useDesenhoHud, usePiloto/useVento/useBola, useJanelas,
                                  useVista, useViewport, usePaginaVisivel
  components/cockpit/             vista · hud · doca · janela · janela-{voo,bola,vento,energia,sistema,
                                  ajuda} · pecas (Interruptor, Deslizador, Tecla, Marca) · detalhe (lazy)
  components/sim/                 os painéis de detalhe reutilizados: painel-voo, bateria, motores,
                                  curvas, quem-faz-o-que, hardware, rede, observacoes, rpi5, avisos
  components/motion-ui/           animated-number, hold-to-confirm, multi-state-button, progress-bar,
                                  sparkline, toast-stack, ui-theme
```

**Tema**: escuro fixo. Tipos **B612** (algarismos de largura fixa e vírgula estreita — os números) e
**B612 Mono** (as etiquetas de estado e as teclas) — a família desenhada para ecrãs de cockpit. As
janelas, a doca e a miniatura são vidro (`.vidro`: fundo translúcido + `backdrop-filter`); o texto do
HUD é branco com contorno escuro (`.osd`), sem caixas a tapar a vista.

### `data-testid` estáveis

`cockpit` · `vista` (`data-vista`, `data-imagem`) · `vista-imagem` · `sem-imagem` · `miniatura` ·
`miniatura-fechar` · `miniatura-abrir` · `trocar-vista` · `vista-nome` · `hud` (`data-vivo`) ·
`hud-estado` (`data-estado`, `data-modo`) · `hud-fase` · `hud-modo` · `hud-alerta` · `hud-rumo` ·
`hud-vel` · `hud-alt` · `hud-vz` · `hud-bateria` · `hud-vento-vel` · `hud-vento-de` · `hud-rajada` ·
`hud-horizonte` · `hud-mira` · `hud-reticulo` · `hud-linha-bola` · `hud-bola` · `hud-seguidor` ·
`hud-bola-erro` · `tecla-{q,w,e,a,s,d,z,x,c}` (`data-estado="ativa|inativa"`) · `doca` ·
`doca-{id}` (`data-aberta`) · `botao-reiniciar` · `janela-{id}` · `janela-{id}-barra` ·
`janela-{id}-fechar` · `voo-tecla-{…}` · `voo-vref` · `voo-rumo` · `bola-seguir` · `bola-velocidade` ·
`bola-alvo` · `bola-seguidor` · `bola-erro` · `bola-distancia` · `vento-ligado` · `vento-intensidade` ·
`vento-aleatorio` · `vento-bussola` · `vento-agora-vel` · `energia-recarregar` · `energia-detalhe` ·
`sistema-quem-voa` · `sistema-streams`.

## Testes

```bash
npm run test:cockpit       # lib/cockpit.ts — 157 verificações + 9 mutações (todas têm de ser apanhadas)
npm run test:voo           # lib/voo.ts
npm run test:controlador   # lib/controlador.ts + presença dos painéis (e AUSÊNCIA do seletor e do armar)
npm run test:camera        # lib/sim.ts (câmara) + lib/camera-gestos.ts
npm run test:planta        # planta real: parsers e sensores
npm run test:fpv           # parsers dos módulos de imagem
npm run test:multi-ia      # parser do custo multi-IA
```

Todos correm em node com type-stripping (≥ 22.6), sem dependências. O `cockpit.mts` corre o mesmo
conjunto de verificações contra cópias adulteradas do módulo (cover→contain, `ativo: false`, Z/C
trocados, sinal do pitch, limite de 1 s, janela Voo a obrigar ao `/api/sim`, vento sem teto, emissor sem
esperar, janelas sem encaixe): um teste que não falha com o código estragado não testa nada.

## O que saiu (2026-10-12)

Componentes apagados (histórico no git): `sim/controlos.tsx` (vento antigo: 18 botões, 8 campos),
`sim/controlador.tsx` (seletor RL/clássico), `sim/controlo-voo.tsx` (ARMAR + painel de teclas),
`sim/camera.tsx` (pads de órbita), `sim/fpv.tsx` (a imagem a 2929 px do topo; `CustoEtapaFpv` foi para
o `rpi5.tsx`), `sim/cabecalho.tsx`, `sim/seccoes.tsx`, `sim/resumo-bordo.tsx`, `sim/ajuda.tsx`,
`sim/rosa-ventos.tsx`, `ui/input.tsx`, `ui/slider.tsx` e os `motion-ui` que ficaram órfãos (`accordion`,
`segmented-toggle`, `sheet`, `skeleton`, `smooth-tabs`, `stagger-reveal`). Saiu também o teste
`testes/rajadas-ux.mts` (testava a região pura do painel de vento antigo).

O `use-sim` continua a expor as ações do contrato antigo (`aplicarVento`, `pararTudo`,
`aplicarVentoDinamico`, `definirLoop`, `definirControlador`, `aplicarCamera`): a API ainda as aceita, o
cockpit não as usa.

**Testes Python do backend que liam o front antigo** (não são deste diretório, ficam por atualizar):
`teste_parar_vento.py` (copia e conduz `controlos.tsx`: `botao-parar-vento`, `campo-rajadas-p`, …),
`teste_controlador.py` §4 (testids em `controlador.tsx` e `controlo-voo.tsx`) e `teste_controle_voo.py`
(`voo-ativar`, `voo-ativo`, `voo-seguindo`, `tecla-*`). O que se manteve com o mesmo nome: `tecla-{letra}`
(agora no HUD, só desenho), `voo-vref`, `voo-rumo`, `controlo-voo`, `voo-indisponivel`,
`quem-faz-o-que*`, `bordo-alvo*`.

## Limites conhecidos

- **FoV da câmara de bordo**: o runner só o publica em `hud.bola.fovy`, depois de o modo bola ligar pela
  1.ª vez. Até lá o horizonte usa `FOVY_BORDO_OMISSAO` = 67° (o do módulo do build ativo); a janela
  Sistema diz qual dos dois está em uso.
- **Câmara da 3.ª pessoa sem janela nativa**: `camera_atual` vem `null` no `/api/sim` e no `/api/state`;
  o cockpit lê a pose em vigor uma vez com o «toque» `POST /api/camera {}` e depois confia nas respostas
  dos seus próprios POSTs (outro cliente a mexer na câmara não é visto).
- **Atraso da imagem**: o HUD compensa a latência do MODELO da câmara (116 ms) e meio período do
  stream; o que o browser e a rede acrescentam não é medido — em manobras bruscas (e com a máquina
  carregada) o horizonte e o retículo podem adiantar-se uns píxeis à imagem.
- **Prova de vida da imagem**: um `<img>` MJPEG não avisa quando os quadros param; o estado «SEM IMAGEM»
  vem do `/api/state` (1 Hz), logo demora até ~1–2 s a aparecer.
- O retículo só se desenha em 1.ª pessoa (a posição é no referencial da câmara de bordo).
