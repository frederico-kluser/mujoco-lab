# Frente Unity/BepInEx — jogos Unity moddáveis (BepInEx / MelonLoader / UnityModManager)

**Data**: 2026-10-14 · **Âmbito**: jogos baseados em **Unity** onde injetar C# (BepInEx/MelonLoader/UMM),
desativar a física da engine e conduzir corpos por cinemática externa (MuJoCo). Conteúdo web = `untrusted`;
afirmações incertas marcadas **(não confirmado)**.

## Kerbal Space Program 1

- **ENGINE**: Unity 5.4 (Mono), build 64-bit.
- **MODDING**: maturíssimo — plugins C# (AssemblyLoader/KSPAddon/PartModule), Harmony; ecossistema CKAN.
  A documentação oficial da API desapareceu em 2025 (comunidade queixou-se no Reddit), mas o ecossistema mantém-se.
- **FÍSICA EXTERNA**: **precedente direto** — o mod *PhysicsHold* (gotmachine) desativa a física de vasos
  aterrados tornando **todos os rigidbodies cinemáticos** (força o estado "packed"/"on rails"). Seguir poses
  do MuJoCo por transform/tick por cima disso é exequível via VesselModule/PartModule.
- **COLISÕES/CENÁRIO**: colliders por peça (Unity), raycasts via `Physics.Raycast`; exportação de malhas do
  cenário sem ferramenta pronta **(não confirmado)**.
- **VISUAL/CV**: FOV ajustável, captura de ecrã trivial (`ScreenCapture`), poses de peças ground-truth via
  API do vaso; câmara livre dedicada **(não confirmado)**.
- **AUTOMAÇÃO**: sem headless; scripting de missões via kOS/KRPC; determinismo limitado (física Unity).
- **LINUX**: build nativa 64-bit — ok em CachyOS.
- **CUSTO/LEGAL**: pago (~40 €, promoções frequentes); mods permitidos pela EULA segundo a comunidade
  **(não confirmado no texto da EULA)**.
- **COMUNIDADE**: grande mas a envelhecer; ativa em 2025-2026 (fórum, CKAN, Reddit).

## Kerbal Space Program 2 (descartado)

Intercept Games encerrada pela Take-Two em 2024; Early Access abandonado sem API de mods estável; existe
esforço comunitário "KSP2 Redux" **(não confirmado)**. Não é candidato.

## Besiege

- **ENGINE**: Unity (Mono).
- **MODDING**: **mod loader oficial embutido em C#** (docs em mod.besiege.co.uk): custom Blocks, Level
  Objects/Entities, Logic Events; malhas/texturas carregadas via XML do mod + ModResource API. BepInEx/Harmony
  como escape hatch para hooks que a API oficial não cobre (indicação da comunidade).
- **FÍSICA EXTERNA**: o sandbox já tem gravidade ajustável; desativar a física dos blocos e conduzir por
  cinemática **sem precedente publicado (não confirmado)** — mas sendo Unity com C# injetável,
  `Rigidbody.isKinematic` + `transform.SetPositionAndRotation` por tick é viável.
- **COLISÕES/CENÁRIO**: colliders por bloco; malhas custom geram colliders; exportação da geometria do cenário
  **(não confirmado)**; raycasts via `Physics`.
- **VISUAL/CV**: câmara orbit livre do sandbox; captura via plugins transversais (Unity-FreeCam /
  CinematicUnityExplorer).
- **AUTOMAÇÃO**: sem headless; cenários sandbox configuráveis por XML.
- **LINUX**: nativo **(não confirmado)**; Proton deve funcionar **(não testado)**.
- **CUSTO/LEGAL**: pago (~15-20 €); modding oficial → legal.
- **COMUNIDADE**: ativa (mod.besiege.co.uk, Steam Workshop para contraptions), dimensão média.

## Trailmakers

- **ENGINE**: Unity.
- **MODDING**: **API oficial Lua** (código corre no servidor; custom maps) + wiki oficial ativa (2026);
  para além da API, a comunidade indica BepInEx ("a API oficial é decent but limited").
- **FÍSICA EXTERNA**: a API expõe set de massa/flutuabilidade, add forces/torques, spawn de objetos;
  controlo cinemático total por tick **(não confirmado)**.
- **COLISÕES/CENÁRIO**: **injeção de modelos 3D próprios CONFIRMADA** — `tm.physics.AddMesh`/`AddTexture` +
  `SpawnCustomObject`; raycast de terreno na API.
- **VISUAL/CV**: câmara livre do jogo; captura por plugin; ground truth de objetos **(não confirmado)**.
- **AUTOMAÇÃO**: execução server-side dos mods; headless **(não confirmado)**.
- **LINUX**: não nativo **(não confirmado)**; Proton.
- **CUSTO/LEGAL**: pago (~20 €); API oficial → legal.
- **COMUNIDADE**: ativa (trailmakers.wiki.gg, portal de docs, Discord).

## Stormworks: Build and Rescue

- **ENGINE**: Unity.
- **MODDING**: oficial: **component Lua API** (modelos 3D, sons, comportamento; Workshop) e, desde a v1.15.0
  (jul 2025), ficheiro de **valores para override de física/gameplay** (flutuação, aerodinâmica, etc.).
- **FÍSICA EXTERNA**: override de parâmetros de física é oficial; condução cinemática de corpos **(não
  confirmado)**; injeção C# via BepInEx em tese **(não confirmado para este jogo)**.
- **COLISÕES/CENÁRIO**: component mods trazem malhas custom; exportação do cenário **(não confirmado)**.
- **VISUAL/CV**: low-poly, mundo oceânico vasto; câmara livre **(não confirmado)**.
- **AUTOMAÇÃO**: microcontroladores Lua in-game; sem headless.
- **LINUX**: não nativo **(não confirmado)**; Proton.
- **CUSTO/LEGAL**: pago (~20 €); modding oficial → legal.
- **COMUNIDADE**: ativa (wiki Fandom, Steam).

## Unturned

- **ENGINE**: Unity (Mono), free-to-play.
- **MODDING**: RocketMod/OpenMod (plugins C#) + sistema de assets YAML com hot reload (`/reload`); SDK
  aberto (U3-SDK no GitHub, com discussões de física de veículos/WheelColliders).
- **FÍSICA EXTERNA**: *Vehicle Physics Profiles* tunam rigidbody raiz (massa/drag) e wheel colliders;
  override cinemático total sem precedente publicado **(não confirmado)** — plugins C# + Unity permitem
  `isKinematic` + transform por tick.
- **COLISÕES/CENÁRIO**: assets custom com malhas próprias (Unity bundles) e colliders configuráveis.
- **VISUAL/CV**: estética low-poly "blocky" — boa para segmentação/ground truth barato, má para CV fotorrealista.
- **AUTOMAÇÃO**: **servidor dedicado headless nativo Linux**; comandos de servidor; replay determinístico não.
- **LINUX**: cliente e servidor nativos.
- **CUSTO/LEGAL**: grátis; modding oficial → legal.
- **COMUNIDADE**: grande e ativa (docs.smartlydressedgames.com).

## From the Depths / Sub Rosa (resumo)

- **From the Depths**: Unity, Lua in-game (breadboards/LUA Box) e mods de blocos; override de física e
  injeção C# **(não confirmado)**; Windows **(não confirmado)**; comunidade nicho. Fraco para o objetivo.
- **Sub Rosa**: sem cena de modding relevante encontrada (apenas BepInEx genérico); comunidade minúscula.
  Não candidato.

### Tradeoffs (física MuJoCo + validação de IA visual)

- Padrão transversal viável em qualquer Unity: BepInEx/MelonLoader → `Rigidbody.isKinematic = true` +
  `transform.SetPositionAndRotation` por tick (+ `Physics.SyncTransforms`); precedente real = PhysicsHold do KSP1.
- **Melhor equilíbrio**: **Besiege** (mod loader oficial C# + malhas custom + sandbox) ou **KSP1** (precedente
  cinemático + ecossistema maduro); **Unturned** se pesarem Linux nativo, custo zero e servidor headless
  (aceitando visual blocky). **Trailmakers** é o único com injeção de malhas por API oficial documentada.
- Nenhum traz pipeline pronto de exportação de malhas de colisão nem ground truth de semântica: seria plugin
  próprio (`Physics.Raycast`/`MeshCollider` + `ScreenCapture`) — esforço comum a todos os candidatos.
- Riscos: updates das builds partem mods (mitigar com beta do Steam / versão fixa); sem headless renderizado;
  determinismo fraco → registar ground truth por frame em vez de depender de replay.

### Fontes

- `docs.unity3d.com/ScriptReference/Rigidbody-isKinematic.html` — isKinematic ignora forças/colisões/joints (base do controlo cinemático).
- `github.com/gotmachine/PhysicsHold` — KSP1: rigidbodies cinemáticos via estado "packed"/"on rails" (precedente de física externa).
- `mod.besiege.co.uk/articles/Introduction.html` — mod loader oficial do Besiege (blocos/entidades/events C#, meshes via XML, ModResource API).
- `trailmakers.wiki.gg/wiki/Modding:Getting_started` e `…/Modding:Custom_Maps` — API Lua oficial: AddMesh/AddTexture, SpawnCustomObject, raycast de terreno, execução server-side.
- `reddit.com/r/trailmakers/comments/1elq5wm` — API oficial "decent but limited"; hooks profundos via BepInEx.
- `stormworks.fandom.com/wiki/V1.15.0` + anúncio Steam (v1.15.0) — override de física via values file; component Lua API com modelos 3D.
- `docs.smartlydressedgames.com/en/stable/assets/vehicle-physics-profile-asset.html` — perfis de física de veículos do Unturned (massa/drag/wheel colliders).
- `pimylifeup.com/unturned-server-linux` — Unturned: servidor dedicado nativo Linux, jogo grátis.
- `github.com/TollyH/Unity-FreeCam` e `github.com/originalnicodr/CinematicUnityExplorer` — câmara livre + captura de ecrã em jogos Unity (BepInEx/MelonLoader).
- `en.wikipedia.org/wiki/Kerbal_Space_Program_2` + `gamedeveloper.com` — KSP2: Intercept Games encerrada em 2024.
- `reddit.com/r/KerbalSpaceProgram/comments/1ind1cy` — API docs do KSP1 desapareceram; afirmação sobre EULA/modding **(não confirmado no texto da EULA)**.
