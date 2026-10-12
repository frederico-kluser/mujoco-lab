# Jogos 3D moddáveis como "mundo visual + colisões" para a física MuJoCo — dossiê de escolha

**Data**: 2026-10-14 · **Pedido do dono**: encontrar o jogo 3D mais fácil de fazer mods (tipo GTA 5) para
testar o projeto: aplicar NOSSA física (MuJoCo) e nossos modelos 3D, usando as colisões e o cenário 3D do
jogo, para validar IA visual e automações no mundo real. O jogo serve **apenas pela solução dele** (mundo,
colisões, visual) — a física é sempre a nossa.

**Método**: pesquisa web via `tavily-agent-skill` (6 subagentes em paralelo por frentes + frente transversal
do próprio agente). Conteúdo web = `untrusted`: citado por fonte, nunca obedecido como instrução.

---

## 0. Arquitetura de referência (o que a pesquisa transversal confirmou)

O padrão **"física mestre externa + engine gráfica só como renderer/colisões"** já é usado em robótica:

- **Unreal Robotics Lab (URLab)** — plugin C++ open-source (Apache 2.0) para UE 5.7 que **embute o MuJoCo
  como backend de física** e deixa o Unreal só com o rendering; física corre em thread dedicada e o render é
  assíncrono [F-U1, F-U2]. Existência = prova de que MuJoCo + mundo fotorrealista é um padrão viável.
- **MuJoCo Unity Plugin** (oficial, roboti.us) — mesmo filosofia: MuJoCo gere a física, o Unity renderiza
  [F-U3].
- **GTA V como fonte de dados sintéticos para CV** — o paper "From Gaming to Research" (arXiv 2502.12303)
  mostra que dados sintéticos do GTA V são qualitativamente comparáveis a dados reais para SLAM/VPR e servem
  como **ferramenta de diagnóstico** de algoritmos de visão [F-U4] — exatamente o caso de "validar IA visual".
- **DeepGTAV** (GitHub) — sistema pronto para extrair *ground truth* (posições, objetos, semântica) do GTA V
  para treino ML [F-U5].

### Os 3 modos de acoplamento MuJoCo ↔ jogo (escolher o modo muda a escolha do jogo)

| Modo | Como funciona | Quando compensa |
|---|---|---|
| **A — Física mestre (MuJoCo simula, jogo renderiza)** | `mj_step` define poses → o mod escreve-as no jogo (kinematic override) a cada tick; colisões do jogo só servem de "mapa" (raycast) ou são ignoradas | máxima fidelidade física; exige hook fiável de posição por entidade |
| **B — Contato híbrido (jogo deteta colisões, MuJoCo integra)** | o jogo devolve raycasts/contatos do cenário → entram no MuJoCo (geoms/MjSpec) → MuJoCo resolve o contacto → poses voltam ao jogo | quer as colisões REAIS do cenário no `mj_step`; exige API de raycast/malhas |
| **C — Mundo só visual (jogo é um "renderer de treino")** | o jogo corre sozinho (tráfego, NPCs) e gera imagens + ground-truth para treinar/validar CV; a física MuJoCo valida-se separadamente | validar IA visual sem acoplamento físico; o mais fácil de todos |

CARLA/SUMO/NS-3 mostram que co-simulação (modo B/C) é prática estabelecida em investigação de veículos
autónomos [F-U6]; o URLab-Sim prova o modo A dentro de UE5 [F-U2].

### Modelo mental para as opções abaixo

Para cada candidato, o que importa é responder a 5 perguntas:

1. **Física externa**: dá para desativar/ignorar a física do jogo e conduzir entidades com poses vindas do
   `mj_step` (cinemática por tick)? Qual o custo (script hook, socket, shared memory)?
2. **Colisões/cenário**: dá para extrair/acessar a geometria de colisão do mundo (malhas, raycasts) para
   alimentar o MuJoCo (contato real) ou só serve para o jogo?
3. **Visual/CV**: câmara livre, captura de ecrã/vídeo, ground-truth para rotular dados, FOV/resolução.
4. **Automação**: scripting do mundo (tráfego, clima, NPCs), determinismo/replay, headless.
5. **Plataforma/custo**: Linux (nativo ou Proton), preço, licença/EULA, comunidade viva.

> Nota de honestidade: se o jogo "só serve pelo visual e colisões", há um tradeoff de fundo — **extrair as
> colisões para o MuJoCo é trabalho de engenharia em qualquer jogo AAA** (formatos proprietários). Nos
> simuladores dedicados (CARLA etc.) isso costuma ser API nativa.

---

## 1. Frentes pesquisadas (resultados dos subagentes)

6 frentes em paralelo; relatórios completos dos subagentes nesta mesma pasta
(`fronte-gta-v-rage.md`, `relatorio-fronte-unity-bepinex.md`, `jogos-conducao-modding-linux.md`,
`mundos-visuais-jogos-modding.md`).

### 1.1 GTA V / RAGE (subagente 1 · relatório completo em `fronte-gta-v-rage.md`)

**GTA V single-player (RAGE)** — o candidato "literal" do pedido:
- **Modding FÁCIL**: ScriptHookV (natives `.asi`; fecha no GTA Online → só SP), ScriptHookVDotNet (C#/.NET:
  `World.CreateVehicle`, `Camera`), Menyoo (Object Spooner), CodeWalker (RPF/YMAP/**YBN**/YDR), OpenIV
  (⚠ sem suporte ao Enhanced → OpenRPF/CodeWalker), Sollumz (Blender). Comunidade enorme; updates do jogo
  quebram temporariamente o ScriptHookV; mods antigos podem não correr no Enhanced.
- **Física externa = override cinemático por tick** (não existe hook para desligar o solver RAGE):
  `SET_ENTITY_COORDS(_NO_OFFSET)`, `SET_ENTITY_VELOCITY`, `FREEZE_ENTITY_POSITION`,
  `SET_ENTITY_COMPLETELY_DISABLE_COLLISION`. Padrão: MuJoCo ⇄ script ASI/C# por named pipe/TCP/ZeroMQ
  (**DeepGTAV usa ZeroMQ**). O MuJoCo calcula, o RAGE desenha; tráfego/peds mantêm física própria.
- **Colisões/cenário**: `.ybn` (colisão) explora/ edita no CodeWalker; Sollumz importa colisões para Blender;
  raycasts por natives (`START_SHAPE_TEST_*`); spawn com colisão (Menyoo Spooner). Pipeline YBN→geom MuJoCo
  **por construir** (não confirmado existir pronto).
- **Visual/CV EXCELENTE, com provas académicas**: DeepGTAV extrai ground truth por tick (frame, bbox2D,
  segmentação, LiDAR, pose de câmara); datasets validados (PreSIL, GTA5-seg, GTASynth, HRSD); arXiv
  2502.12303 usa GTA V para VPR/SLAM. Freecam + FOV/4K. Sem headless oficial (não confirmado) — captura em
  janela.
- **Automação**: natives de hora/clima/densidade de tráfego e peds, tasks, teleporte; motor não determinístico
  entre runs, mas com MuJoCo a mandar poses a reprodução é fiel.
- **Linux**: Windows-only nativo; roda em **Proton/Wine** (tutoriais Steam Deck/Lutris com SHVDN + .NET 4.8
  no prefix); estabilidade sob Proton = não confirmado. **Custo/legal**: jogo ~20–40 €; Mod Guidelines
  set/2026 permitem mods SP **não comerciais** (restrições novas a story/mapas/monetização; aplicação a
  investigação interna = não confirmado). Nunca usar GTA Online.

**FiveM / Cfx.re** (plataforma RAGE "autorizada" — da Rockstar desde 2023; única desde o fecho do alt:V em
fev/2026): resources Lua/JS/C#, physics no client dono da entidade (mesmo override por tick + rede),
**screenshot-basic** (captura orquestrável por servidor — manutenção desde 2022 = não confirmado), servidor
autoritativo com cenários repetíveis e multi-cliente (multi-agente); **servidor roda em Linux, cliente
exige Windows**; exige aceitar a Platform License Agreement (10/09/2026) sob as Mod Guidelines 2026.

**Tradeoffs do subagente**: SP = caminho mais curto (SHVDN + pipe → poses) com DeepGTAV como prova de CV;
FiveM = orquestração/screenshot/multi-agente, mas complexidade de rede + licença + cliente Windows. Em ambos
**a física do jogo não se desliga** — a integração real é "MuJoCo manda, RAGE desenha"; para colisões reais
dos atuadores com o cenário, importar `.ybn` para geoms MuJoCo (a construir). Sobre a regra "sempre físico"
do lab: este override é sincronização de RENDERIZAÇÃO de um agente externo — a física continua toda no
`mj_step` do MuJoCo (o jogo não é o simulador; não há teleporte de estado físico).

### 1.2 Família Source/Valve (subagente 2)

**Garry's Mod** — Source 1 + GLua.
- **Modding FÁCIL**: addons Lua com hot-reload, spawn de props/NPCs/SENTs, Workshop, 20 anos de comunidade.
- **Física externa VIÁVEL**: `PhysObj:EnableMotion(false)` + `SetPos/SetAngles` por tick = corpo cinemático
  comandado pelo MuJoCo (a Physics Gun usa exatamente este mecanismo); `EnableGravity(false)` evita luta com
  VPhysics. IPC: HTTP embutido, `gmsv_chttp`/`gmsv_websocket`, ou TCP localhost (ex. GTerm, 127.0.0.1:27514).
  Latência = tick do servidor (dezenas de Hz, não confirmado) → suficiente para CV, curto para controlo
  fechado rápido.
- **Colisões/cenário**: `PhysObj:GetMesh()`/`GetMeshConvexes()` exportam a malha convexa real usada pela
  física (→ MuJoCo); `util.TraceLine/TraceHull` para raycasts; mapas `.bsp` + props de todos os jogos Source.
- **Visual/CV EXCELENTE**: `render.RenderView` + render targets de resolução arbitrária + `render.Capture`
  (PNG/JPEG); ground-truth grátis em Lua (poses, AABBs). Quirks conhecidos na captura (skybox, alfa com fog —
  issue Facepunch #2571), contornáveis.
- **Automação**: servidor dedicado SteamCMD headless em Linux (render de CV exige cliente com GPU); tudo por
  concommands/addons.
- **Linux NATIVO** (ProtonDB "Native"), ramo x86-64. Custo: jogo pago barato + conta Steam.
- **s&box (Source 2)**: C# (camada MIT desde nov/2025), mas *developer preview*, API instável, Linux imaturo,
  exportação de colisões/captura não documentadas → risco alto hoje. Reavaliar mais tarde.
- **Half-Life 2 / Source SDK 2013**: C++ aberto, controlo total, **melhor extração de colisões da família**
  (`VBSPINFO` → `LUMP_PHYSCOLLIDE`; BSPSource → VMF), mas iteração lenta (C++/Hammer/Wine) e **licença
  Source 1 SDK não-comercial** — trava qualquer produto futuro.

**Tradeoffs (veredito do subagente)**: GMod = melhor equilíbrio para "mundo visual+colisões" com física
MuJoCo mestre (modo A/B); HL2/SDK = plano B para controlo fino de colisões; s&box = só a médio prazo.
Contras: engine visual antiga (Source 1), captura exige cliente com GPU, tick limita sync, assets de outros
jogos Source exigem esses jogos.

### 1.3 Jogos Unity + BepInEx/MelonLoader (subagente 3 · relatório completo em `relatorio-fronte-unity-bepinex.md`)

Padrão transversal viável em qualquer jogo Unity: **BepInEx/MelonLoader → `Rigidbody.isKinematic=true` +
`transform.SetPositionAndRotation` por tick** (+ `Physics.SyncTransforms`) — o MuJoCo conduz, a Unity só
desenha. Precedente real: mod **PhysicsHold** (gotmachine) no KSP1 torna todos os rigidbodies de um vaso
cinemáticos ("packed"/"on rails").

- **KSP 1** (Unity, pago ~40 €, Linux nativo): modding C# maturíssimo (Harmony, CKAN), precedente cinemático
  direto; sem headless, docs da API desapareceram em 2025, comunidade a envelhecer. KSP 2 **descartado**
  (estúdio encerrado em 2024).
- **Besiege** (Unity, pago ~15–20 €): **mod loader OFICIAL C#** (blocos/entidades/Lógica; malhas custom via
  XML + ModResource), sandbox com gravidade ajustável; sem headless.
- **Trailmakers** (Unity, pago ~20 €): API oficial Lua com **injeção de modelos 3D próprios confirmada**
  (`tm.physics.AddMesh/AddTexture`, `SpawnCustomObject`) e raycast de terreno; controlo cinemático total
  não confirmado.
- **Stormworks** (Unity, pago ~20 €): override oficial de física via *values file* (v1.15.0, jul/2025) +
  componentes Lua com modelos 3D; visual low-poly oceânico.
- **Unturned** (Unity, grátis, Linux nativo + servidor headless): plugins C# (RocketMod/OpenMod), assets com
  hot reload; visual *blocky* — bom para segmentação barata, mau para CV fotorrealista.
- **Contra todos**: nenhum traz exportação de malhas de colisão nem ground-truth semântica pronto — seria
  plugin próprio (`Physics.Raycast`/`MeshCollider` + `ScreenCapture`); updates de build partem mods; sem
  headless renderizado; determinismo fraco → registar ground truth por frame, não por replay.

### 1.4 Simuladores de investigação (subagente 4)

- **CARLA 0.9.16 (set/2025, UE4.26 + ramo UE5.5)** — **melhor prontidão**: API Python, modo **síncrono por
  tick** (o cliente impõe pose/transform = "física custom" documentada, ex. RTIS-Lab/carla-custom-physics),
  integração **Project Chrono** para dinâmica externa (atenção: indisponível no build UE5.8 — issue #9937),
  tráfego/peões/LiDAR, sensores CV prontos (RGB/depth/segmentação semântica+instance/optical flow/bboxes),
  **Cosmos Transfer1 + NuRec + SimReady USD** para datasets, headless Docker, determinismo síncrono.
  Código MIT (UE EULA por cima); GPU ≥ 6–8 GB (RTX 4070 8 GB serve, apertado em UE5). Comunidade grande.
- **NVIDIA Isaac Sim/Isaac Lab** — referência absoluta em geração de dados (Replicator SDG: RGB, depth,
  segmentation, normals, bboxes), Apache 2.0; **mas**: não é "renderer de física externa" (acoplamento
  cinemático não confirmado como modo suportado) e os **requisitos oficiais apontam RTX 4080+ / 32 GB RAM**
  — abaixo do mínimo nesta máquina.
- **URLab (Unreal Robotics Lab, UE 5.7 + MuJoCo embutido, alpha, ICRA 2026)** — **é literalmente a
  arquitetura alvo**: MuJoCo mestre + UE render; "one-way kinematic coupling (mocap)", record & replay
  determinístico, CoACD para colisões, bridge Python. Mas é alpha jovem (65 forks) e exige dev de plugin UE;
  evitar UE 5.8 (regressões Vulkan/Linux).
- **MetaDrive** (Panda3D, pip, 1000+ FPS): forte para RL/trafego procedural e import nuScenes/Waymo, mas
  física embutida (sem acoplamento externo confirmado) e gráfica baixa/média.
- **Gazebo** (Harmonic/Jetty LTS, Apache 2.0) e **Webots** (R2025, Supervisor API permite setar poses):
  baselines seguras, headless/deterministas, segmentação desde Ionic (Gazebo) e *Recognition* (Webots),
  mas cenários visualmente fracos para "validar IA visual".
- **Descartados**: **AirSim** (repo morto 2022; Project AirSim morto 2023; só forks), **LGSVL/SVL** (sunset
  2022), **Flatland** (2D).
- **Leitura do subagente**: simuladores ganham em ground-truth pronto, síncronia/determinismo/replay,
  headless e licenças limpas (sem EULA de jogo/anticheat); jogos AAA ganham em **riqueza de cenário e visual
  "mundo real" a custo zero**. O acoplamento cinemático é caminho oficial no CARLA (tick/transform) e Webots
  (Supervisor); em jogo AAA seria hooks/SDK não oficial.

### 1.5 Jogos de condução (subagente 5 · relatório completo em `jogos-conducao-modding-linux.md`)

- **BeamNG.drive / BeamNG.tech** — **melhor encaixe da frente**: mapas urbanos + **AI traffic** com regras de
  trânsito, World Editor in-game, import dos SEUS modelos (Blender→`.dae` com collider) e — decisivo —
  **BeamNGpy**: câmara com RGB + **profundidade + anotações ground truth por píxel (classe/instância)**, LiDAR,
  teleporte de veículo por pose. **Build NATIVA Linux desde jan/2026** (Vulkan). Atritos: (1) condução
  cinemática pura não é modo nativo (teleporte pose-a-pose via BeamNGpy/Lua com a física do jogo sempre ativa;
  como neutralizá-la: não confirmado); (2) **BeamNGpy exige BeamNG.tech** (grátis académico com registo;
  comercial via licensing@beamng.gmbh) e o binário Linux nativo do `.tech` **não está confirmado** — verificar
  antes de decidir. .drive ~€25.
- **ETS2/ATS** (Prism3D) — plano B: mundo rico (estradas, cidades, **tráfego AI denso**, dia/noite),
  **Linux nativo** (Deck Verified), **SDK de telemetria oficial** + injeção de inputs desde 1.14, map editor
  próprio + SCS Blender Tools. Mas sem sensores CV e sem export de colisões direto.
- **Assetto Corsa 1** — modding gigante (CM/CSP/Sol), mas mundo = pistas (sem cidade viva), sem ground truth
  CV, Linux só via Proton-GE com tweaks frágeis. **AC EVO**: SDK v1 (3-jun-2026) só de **carros** — sem editor
  de pistas; cedo demais. **Automation**: só gerador de carros → exporta para BeamNG.

### 1.6 AAA/AA moddáveis + voxel/sandbox (subagente 6 · relatório completo em `mundos-visuais-jogos-modding.md`)

- **AAA/AA abertos** (Watch Dogs 2, Skyrim/Fallout 4, Saints Row, JC2/3-MP): mundos bonitos tipo cidade, mas
  **engines fechadas** — câmara livre e map editors existem (ex.: OmniForge p/ Watch Dogs 2, Camera Scripter
  p/ Skyrim, JC3:MP com scripting JS server-side), porém condução cinemática externa (MuJoCo), exportação de
  colisões e headless ficam **não confirmados**. Mafia DE e Sleeping Dogs eliminados (sem ferramentas).
- **Teardown** (Unity + física voxel própria): **API Lua com `SetCameraTransform`/`GetCameraTransform` e
  `QueryRaycast`/`GetShapeMaterialAtPosition` confirmados** — câmara programática e raycasts = ground-truth de
  contacto garantidos; visual voxel de topo (destruição, reflexos); mapas pequenos, sem cidade; Proton.
- **Luanti (ex-Minetest)** (open-source C++ ~13,7k stars, Lua nativo, ContentDB): **único candidato com o
  motor alterável** para sincronizar diretamente com o MuJoCo; export OBJ (Meshport), servidor headless
  nativo, gratuito/aberto. Custo: visual voxel simples.
- **Minecraft Java** (Fabric/Forge): export de mundos para OBJ/USD (Mineways, jmc2obj) + MCprep no Blender,
  comunidade gigante, já existem datasets de CV; mas visual blocky e EULA restritiva (não confirmado).
  Roblox descartado (plataforma fechada, extração contra ToS).
- **Recomendação do subagente**: piloto em **Luanti** (pipeline determinístico MuJoCo→mundo) ou **Teardown**
  (imagem + câmara/raycast comprovados); AAA só como "casca visual" se o realismo pesar mais que o controlo.

## 1.A Grelha de avaliação (critérios e pesos do caso de uso)

Cada candidato é avaliado em 6 eixos (0–5), com os pesos do caso de uso "física MuJoCo + validação de IA
visual + automações":

| Eixo | Peso | O que mede |
|---|---|---|
| **Física externa (MuJoCo mestre)** | 25 % | desligar/conduzir entidades por poses externas sem lutar com a engine |
| **Colisões/cenário acessíveis** | 20 % | extrair geometria de colisão para o MuJoCo + raycasts para validação |
| **Visual/CV (ground-truth incluído)** | 20 % | qualidade gráfica, câmara livre, captura, rótulos automáticos |
| **Automação/scripting do mundo** | 15 % | tráfego/NPCs/clima, determinismo, headless |
| **Facilidade de modding** | 10 % | ferramentas, docs, comunidade viva, tempo até ao primeiro mod |
| **Linux + custo/legal** | 10 % | roda nesta máquina (nativo/Proton), EULA permite, preço |

Escala de cada eixo: **5** = pronto e documentado hoje · **4** = viável com esforço pequeno · **3** =
exequível mas com engenharia própria relevante · **2** = frágil/não confirmado · **1** = impraticável.
A nota final = soma ponderada. Tudo o que os subagentes marcaram "não confirmado" conta como ≤ 3 nesse eixo
(pessimismo deliberado: incerteza não vira ponto).

---

## 3. Síntese — lista recomendada com tradeoffs

### 3.1 Tabela-mãe (notas 0–5 pela escala da §1.A; soma ponderada)

| Candidato | Física ext. (25 %) | Colisões (20 %) | Visual/CV (20 %) | Automação (15 %) | Modding (10 %) | Linux/custo (10 %) | **Total** |
|---|---|---|---|---|---|---|---|
| **Garry's Mod** | 5 | 5 | 4 | 4 | 5 | 5 | **4,65** |
| **CARLA** (simulador) | 5 | 3 | 5 | 5 | 4 | 4 | **4,40** |
| **Luanti** (ex-Minetest) | 5 | 4 | 2 | 4 | 5 | 5 | **4,05** |
| **GTA V (SP)** | 4 | 3 | 5 | 4 | 5 | 2 | **3,90** |
| **FiveM** | 4 | 3 | 4 | 5 | 4 | 2 | **3,75** |
| **BeamNG.tech** | 2 | 3 | 5 | 5 | 4 | 3 | **3,55** |
| **URLab (UE5+MuJoCo)** | 5 | 3 | 3 | 3 | 2 | 4 | **3,50** |
| **HL2/Source SDK** | 4 | 5 | 3 | 3 | 2 | 2 | **3,45** |
| **Teardown** | 3 | 4 | 4 | 2 | 4 | 3 | **3,35** |
| **KSP 1** | 4 | 3 | 3 | 2 | 4 | 4 | **3,30** |
| **Minecraft Java** | 3 | 4 | 2 | 3 | 5 | 3 | **3,20** |
| **ETS2/ATS** | 2 | 2 | 3 | 4 | 4 | 5 | **3,00** |

**Descartados**: s&box (developer preview, API instável), KSP2 (estúdio encerrado, 2024), AC EVO (SDK só de
carros; sem pistas), AirSim/LGSVL (projetos mortos 2022/2023), Watch Dogs 2/Skyrim/F4/Saints Row/JC-MP
(engines fechadas: câmara sim, controlo cinemático + export de colisões frágeis), Mafia DE/Sleeping Dogs
(sem ferramentas), Roblox (fechado, contra ToS), Automation (só gerador de carros), Flatland (2D).

### 3.2 A lista final (por perfil de uso)

**TIER A — começar por estes**

1. **Garry's Mod** — o melhor custo-benefício para provar o pipeline completo **já esta semana**.
   - *Porquê*: único onde os 3 requisitos estão prontos e documentados: (a) física externa **limpa**
     (`PhysObj:EnableMotion(false)` neutraliza a VPhysics de vez — nem luta com o solver, ao contrário do
     override por tick do GTA); (b) colisões reais exportáveis (`GetMesh/GetMeshConvexes` → geoms MuJoCo =
     modo B); (c) captura CV a resolução arbitrária + ground-truth por Lua. **Linux nativo**, jogo ~10 €.
   - *Tradeoffs*: visual Source 1 antigo (menos "rua real" para treinar CV de condução); captura exige
     cliente com GPU; tick limita sync (ok para datasets; curto para closed-loop >10 Hz); assets de outros
     jogos Source exigem esses jogos.
   - *Modo recomendado*: **B** (colisões do jogo → MuJoCo) com passeio em **A** (poses do `mj_step`).

2. **GTA V (single-player)** — o "tipo GTA 5" literal, quando o visual realista importar.
   - *Porquê*: mundo urbano rico pronto, ecossistema de ferramentas maduro (ScriptHookV/SHVDN/Menyoo/
     CodeWalker/Sollumz), e — decisivo para "validar IA visual" — é o **único com literatura académica
     provada**: DeepGTAV (ground truth por tick: bboxes, segmentação, pose), datasets PreSIL/GTA5-seg/
     GTASynth/HRSD, e o arXiv 2502.12303 (dados sintéticos comparáveis a reais em SLAM/VPR).
   - *Tradeoffs*: **Windows-only** (Proton/Wine com SHVDN+ .NET — estabilidade não confirmada); o solver
     RAGE **não se desliga** (override cinemático por tick — suficiente, pois a física é do MuJoCo); pipeline
     `.ybn`→MuJoCo **por construir**; sem headless (captura em janela); updates do jogo quebram mods;
     Mod Guidelines 2026 (SP não-comercial OK; alcance sobre mapas próprios = não confirmado).
   - *Modo recomendado*: **A** (MuJoCo manda, RAGE desenha) + modo C para gerar datasets de CV.

**TIER B — fortes em pontos específicos**

3. **CARLA** — se a prioridade for *ground-truth pronto + determinismo + headless* (não é "jogo", é
   simulador de condução): tick síncrono com pose imposta pelo cliente (física externa = caminho oficial),
   sensores CV prontos (seg/instance/depth/optical flow/bboxes), Cosmos/NuRec/SimReady USD para datasets,
   Traffic Manager, Docker headless. *Tradeoffs*: mundo = estradas/cidades de simulador (sem "vida" tipo
   GTA), build UE pesado, GPU 8 GB apertada no ramo UE5, export de geometria não confirmado.

4. **BeamNG.tech + BeamNGpy** — se o foco for **veículos + sensores CV prontos** (RGB+depth+anotações por
   píxel classe/instância, LiDAR), AI traffic real e import dos vossos modelos (.dae+collider). *Tradeoffs*:
   cinemática externa não nativa (teleporte pose-a-pose com a física do jogo ativa), BeamNGpy exige .tech
   (grátis académico) e o binário **Linux nativo do .tech não está confirmado**; mundo = condução.

5. **FiveM** — se quiserem **orquestração**: cenários repetíveis por resource, screenshot API, multi-cliente
   (testes multi-agente), servidor em Linux. *Tradeoffs*: cliente Windows-only, camada de rede, Platform
   License Agreement 2026, screenshot-basic sem commits desde 2022 (manutenção não confirmada).

6. **URLab (Unreal Robotics Lab)** — **a arquitetura exata do projeto** (MuJoCo mestre + UE5 render,
   mocap coupling, replay determinístico, Apache 2.0) mas alpha jovem: exige dev de plugin UE e terão de
   montar o cenário (não vem um "GTA pronto"). Reavaliar quando amadurecer — ou usar como referência de
   design para o vosso acoplamento.

**TIER C — nicho / só com motivo forte**

7. **Teardown** — câmara programática + raycasts **confirmados** na API Lua e visual voxel de topo; mas
   mapas pequenos e sem cidade. Bom para validar pipelines de câmara/contacto rapidamente.
8. **Luanti** — o único com o **motor aberto** (dá para sincronizar MuJoCo↔mundo a fundo), headless nativo,
   grátis; mas visual voxel simples = fraco para validar IA visual realista.
9. **HL2/Source SDK** — melhor extração de colisões da lista (`VBSPINFO`→`LUMP_PHYSCOLLIDE`, BSPSource) se
   precisarem do cenário em MuJoCo com precisão; custo: C++/Hammer/Wine + **licença não-comercial**.
10. **KSP 1** (precedente cinemático PhysicsHold), **Minecraft Java** (export OBJ/USD, mas blocky),
    **ETS2/ATS** (Linux nativo + tráfego denso, mas sem CV ground truth).

### 3.3 Justificação dos tradeoffs transversais (o que cada escolha "paga")

- **Mundo rico AAA × controlo**: jogos AAA dão ruas/interiores/tráfego orgânicos a custo zero, mas a
  integração física externa é sempre "por cima" (override por tick, hooks). Simuladores dão APIs oficiais e
  ground truth, mas mundos estéreis e curva de aprendizagem alta. **GMod fica no meio-termo**: controlo de
  simulador com um mundo pronto de sandbox.
- **Desligar a física do jogo**: só o GMod (`EnableMotion(false)`) e engines abertas (Luanti) o fazem de vez;
  no GTA/BeamNG a física nativa continua a correr e há que neutralizá-la caso a caso (freeze/collision off).
  Como a física de verdade é a nossa, basta o jogo não "empurrar" os corpos — e isso é exequível em todos os
  Tier A/B.
- **Colisões do cenário no `mj_step`** (modo B): grátis no GMod (`GetMesh*`) e parcial no HL2 (lumps); no GTA
  é trabalho novo (YBN→geom); no CARLA/BeamNG usa-se raycast em vez de exportar malha (bom o suficiente para
  contacto simples, não para contactos detalhados).
- **Ground truth de CV**: GTA (DeepGTAV+datasets) e BeamNG (sensores por píxel) ganham; GMod dá poses/AABB
  "de graça" mas sem semântica pronta; CARLA dá tudo pronto.
- **Linux nesta máquina (CachyOS/RTX 4070 8 GB)**: nativo = GMod, CARLA, Luanti, ETS2, Unturned; sob
  Proton = GTA V (não confirmado estável), BeamNG.drive (nativo desde jan/2026; .tech não confirmado);
  Windows-only real = FiveM cliente. Isaac Sim cai pelos requisitos (RTX 4080 mínimo).
- **Legal**: Source 1 SDK não-comercial (HL2), Mod Guidelines Rockstar 2026 (GTA/FiveM: SP não-comercial),
  BeamNG.tech com licença académica, MIT/Apache nos simuladores (CARLA, URLab, Gazebo, Webots, Isaac).

### 3.4 Recomendação executiva

**Começar pelo Garry's Mod (Tier A.1)** para montar e provar o acoplamento MuJoCo ↔ jogo (modo B com o
caminho A à mão) — é onde cada peça existe documentada e corre em Linux nativo. **Em paralelo, montar o
GTA V SP (Tier A.2)** como o alvo de validação de IA visual (o visual real só entra "caso queiras reininar um
modelo de visão computacional" — aí o GTA é a escolha com provas académicas). Se o objetivo deslizar para
"muitos dados com rótulos prontos e determinismo", **CARLA** é o próximo passo natural; se for para veículos,
**BeamNG.tech**.

### 3.5 Nota sobre a regra "simulador sempre físico" do laboratório

Em todos os modos A/B acima, **o MuJoCo é o único simulador físico**: tudo passa por `mj_step` e o jogo
recebe apenas poses/espelhos (não há teleporte de estado físico — há sincronização de renderização de um
agente externo, como o URLab faz com o mocap coupling). No modo B, as colisões do cenário entram como geoms
no MuJoCo e **o contacto é resolvido pelo MuJoCo**, não pelo jogo. Isto mantém a regra do dono intacta e
deve ser documentado assim em qualquer experimento futuro.

## 4. Fontes transversais (agente principal)

- **[F-U1]** Unreal Robotics Lab (GitHub, URLab-Sim/UnrealRoboticsLab) — plugin C++ UE 5.7 com MuJoCo
  embutido como física; Apache 2.0. <https://github.com/URLab-Sim/UnrealRoboticsLab>
- **[F-U2]** "Unreal Robotics Lab: A High-Fidelity Robotics Simulator with Advanced Physics and Rendering"
  (arXiv 2504.14135) — física MuJoCo em thread dedicada, render UE assíncrono, forças propagadas
  bidirecionalmente. <https://arxiv.org/html/2504.14135v2>
- **[F-U3]** MuJoCo Unity Plugin (documentação oficial roboti.us) — MuJoCo gere física, Unity renderiza e
  acede aos dados geométricos. <https://www.roboti.us/book/unity.html>
- **[F-U4]** "From Gaming to Research: GTA V for Synthetic Data" (arXiv 2502.12303) — dados sintéticos GTA V
  comparáveis a reais em SLAM/VPR; servem de diagnóstico de algoritmos de visão.
  <https://www.alphaxiv.org/abs/2502.12303>
- **[F-U5]** DeepGTAV (GitHub, David0tt/DeepGTAV) — extração de ground truth do GTA V para ML.
  <https://github.com/David0tt/DeepGTAV>
- **[F-U6]** Co-simulação CARLA + SUMO + NS-3 (arXiv 2512.11249; MODSIM 2023; Medium 2025) — padrão
  estabelecido de acoplar simuladores de tráfego/dinâmica em veículos autónomos.
  <https://arxiv.org/html/2512.11249v1>
- **[F-U7]** Sollumz (GitHub) — add-on Blender para criar/importar/exportar assets GTA V (modelos, mapas,
  interiores, animações, colisões). <https://github.com/Sollumz/Sollumz>
- **[F-U8]** Política de modding Rockstar 2026 (após aquisição da Cfx.re em 2023) — modding multiplayer
  limitado a plataformas licenciadas (FiveM/RedM como "casa licenciada"); afeta o modo como se pode usar
  GTA V/FiveM. <https://tech-insider.org/rockstar-gta-6-mod-policy-8-rules-2026> ·
  <https://www.gamesindustry.biz/rockstar-acquires-roleplay-modding-team-cfxre>
- **[F-U9]** Ecossistema de datasets sintéticos do GTA V para CV — **PreSIL** (object detection + LiDAR
  simulado, Waterloo WISE Lab), **GTASynth** (SLAM, poses + point clouds), **HRSD** (RGB-D para depth
  monocular), **GTA5** (segmentação semântica) — citados no arXiv 2502.12303.
  <https://uwaterloo.ca/waterloo-intelligent-systems-engineering-lab/projects/precise-synthetic-image-and-lidar-presil-dataset-autonomous>

*(restantes fontes nas secções de cada frente)*
