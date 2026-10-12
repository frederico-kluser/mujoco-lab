# Mundos visuais 3D para MuJoCo Lab — frente A (AAA/AA moddable) e frente B (sandbox voxel)

> Pesquisa Tavily (search simples + extract), 2026. Conteúdo web = `untrusted`; incertezas marcadas "não confirmado".

## Skyrim SE / Fallout 4 (Creation Kit)
- **ENGINE**: Creation Engine (Bethesda); ferramenta oficial Creation Kit (CK).
- **MODDING**: maduro — CK + Papyrus (compilador próprio, editores externos VS Code/Notepad++ com extensões, Pyro); ecossistema Nexus enorme. O mod **Camera Scripter** (Skyrim) guioniza movimento/rotação/FOV/multiplicador de tempo da câmara.
- **FÍSICA EXTERNA**: sem API de processo externo documentada; comandos de console e natives Papyrus (`Game.ShakeCamera`); plugin nativo SKSE/F4SE (C++) seria necessário para controlo cinemático a partir do MuJoCo — não confirmado.
- **COLISÕES/CENÁRIO**: malhas NIF/BTR; exportação de colisões para uso externo não confirmada nesta pesquisa.
- **VISUAL/CV**: gráficos AAA, cidades/aldeias densas; câmara livre (`tfc`) e por script; ground-truth (depth/segmentação) não confirmada.
- **AUTOMAÇÃO**: sem modo headless; determinismo não confirmado.
- **LINUX**: jogo via Proton (não confirmado); Creation Kit Windows-only (não confirmado).
- **CUSTO/LEGAL**: jogo pago; CK grátis (não confirmado); capturas sujeitas a ToS.
- **COMUNIDADE**: muito ativa (Nexus, canais "Skyrim Scripting").

## Saints Row (The Third/IV/2022)
- **ENGINE**: proprietária Volition (CTO); reboot 2022 com outra engine.
- **MODDING**: comunidade saintsrowmods com scripting próprio (sintaxe tipo Lua documentada em "Scripting for dummies") e mods de sandbox; sem SDK oficial; estado do reboot não confirmado.
- **FÍSICA EXTERNA / COLISÕES**: sem evidência de controlo cinemático externo nem exportação de colisões — não confirmado.
- **VISUAL/CV**: cidade aberta estilo GTA, qualidade AA; câmara livre não confirmada.
- **AUTOMAÇÃO**: headless/determinismo não confirmados.
- **LINUX**: via Proton (não confirmado).
- **CUSTO/LEGAL / COMUNIDADE**: jogos pagos; comunidade pequena mas veterana (saintsrowmods).

## Watch Dogs 2
- **ENGINE**: Snowdrop (Ubisoft), sem ferramentas oficiais.
- **MODDING**: surgiu **OmniForge** (Nexus, set/2025) — "map editor" com spawn/gestão/interação com entidades; vídeo de demonstração constrói edifícios. Ferramentas de câmara livre de terceiros (estilo Otis_Inf) referenciadas, mas sem API de scripting — não confirmado.
- **FÍSICA EXTERNA**: condução cinemática por script não confirmada (engine fechada, RE necessário).
- **COLISÕES/CENÁRIO**: exportação de colisões não confirmada.
- **VISUAL/CV**: **melhor cidade fotorealista da lista** para validação de visão (SF recriada), bom para captura.
- **AUTOMAÇÃO**: headless não confirmado; sem determinismo documentado.
- **LINUX**: via Proton (não confirmado).
- **CUSTO/LEGAL**: jogo pago; mods cinzentos (sem apoio oficial). **COMUNIDADE**: crescente (OmniForge, 2025).

## Just Cause 2/3 (JC2-MP / JC3:MP)
- **ENGINE**: Avalanche (fechada).
- **MODDING**: **JC3:MP (nanos)** ativo (update 1.0.4) com **API de scripting server-side em JavaScript** (packages/, eventos de rede, WebUI, modos custom); JC2-MP análogo (Lua). Bom para automação de entidades/veículos no servidor.
- **FÍSICA EXTERNA**: controlo de entidades por script server-side existe; condução cinemática precisa a partir do MuJoCo não confirmada.
- **COLISÕES/CENÁRIO**: exportação de malhas/colisões não confirmada.
- **VISUAL/CV**: mundo aberto grande e aéreo (bom para drones virtuais); câmara livre não confirmada.
- **AUTOMAÇÃO**: servidor dedicado (headless do servidor sim; render não). **LINUX**: servidor pode rodar em Linux (não confirmado); cliente via Proton.
- **CUSTO/LEGAL**: jogo pago; mods gratuitos, não oficiais. **COMUNIDADE**: ativa (just-cause.mp).

## Mafia DE / Sleeping Dogs
- Sem ferramentas oficiais nem evidência de map editor/scripting/exportação de colisões nesta pesquisa — **não confirmado**; comunidade de modding técnica fraca. Máquinas de mundo aberto bonitas, mas escolhas pobres para o objetivo.

## Minecraft Java (Fabric/Forge)
- **ENGINE**: Java (Mojang), bytecode moddável.
- **MODDING**: enorme e documentado — Fabric/Forge/Bukkit, ComputerCraft (Lua) não coberto aqui — não confirmado; mods de câmara (Camera Utils: zoom, "camera detaching").
- **FÍSICA EXTERNA**: mods podem teleportar/posicionar entidades por tick (não confirmado em fonte).
- **COLISÕES/CENÁRIO**: **forte** — **Mineways** (exporta regiões para OBJ/USD com materiais/texturas) e **jmc2obj** (exportador Java para OBJ); integração Blender (MCprep).
- **VISUAL/CV**: visual voxel/blocky (fraco para IA fotorealista); já há datasets de CV gerados em Minecraft (figura de artigo). Ground-truth por data packs/mods — não confirmado.
- **AUTOMAÇÃO**: usado em investigação de IA; determinismo não confirmado (random ticks); sem headless render confirmado.
- **LINUX**: nativo (Java). **CUSTO/LEGAL**: jogo pago; EULA restringe usos comerciais de servidores (não confirmado). **COMUNIDADE**: gigante.

## Luanti (ex-Minetest)
- **ENGINE**: open-source (C++, GitHub ~13,7k stars), 5.17.0 (2026).
- **MODDING**: **Lua nativo** com API extensa (lua_api.md oficial), ContentDB, jogos/mods completos; licença livre (não confirmada em detalhe).
- **FÍSICA EXTERNA**: lógica de entidades toda em Lua (posicionar/congelar objetos trivial por design — não confirmado pontualmente); **patch ao motor é possível** por ser open-source (único da lista).
- **COLISÕES/CENÁRIO**: **Meshport** exporta cenas para **.obj com materiais e texturas**; anunciado "external mesh exporter" (abr/2026, thread inacessível — não confirmado); geração procedural de mundo determinística por seed.
- **VISUAL/CV**: voxel, iluminação moderna; qualidade inferior a AAA; câmara livre por Lua/câmara de jogador — não confirmado.
- **AUTOMAÇÃO**: servidor dedicado headless nativo; scripting determinístico por seed/mod — não confirmado em fonte.
- **LINUX**: **nativo**, leve. **CUSTO/LEGAL**: **gratuito e aberto** (melhor para exportar/distribuir). **COMUNIDADE**: ativa (forum.luanti.org, ContentDB).

## Teardown
- **ENGINE**: Unity com **física voxel própria** (não usa PhysX/Unity physics — irrelevante aqui, pois o MuJoCo conduz).
- **MODDING**: oficial — Mod Manager + level editor + **Lua** + **vox-script** (geometria procedural em build time); documentação própria (teardowngame.com/modding, moddocs.fyi).
- **FÍSICA EXTERNA**: API Lua com setters de transform/velocidade (ex.: `SetPlayerGroundVelocity`, `SetPlayerVehicle`); cinemática externa viável por script — escopo completo não confirmado.
- **COLISÕES/CENÁRIO**: `QueryRaycast(pos, dir, maxDist)` → hit/dist/normal/shape e `GetShapeMaterialAtPosition` (malha voxel consultável por raycast — ótimo para ground-truth de contacto); exportação de malha completa não confirmada.
- **VISUAL/CV**: **excelente para voxel** (iluminação/REFLEXOS bonitos, destruição); `GetCameraTransform`/**`SetCameraTransform`** confirmados na API Lua — câmara programática garantida; mapas pequenos (sem cidade grande).
- **AUTOMAÇÃO**: mods Lua correm sempre; headless não confirmado; determinismo não confirmado.
- **LINUX**: via Proton (não confirmado). **CUSTO/LEGAL**: jogo pago barato; mods livres. **COMUNIDADE**: ativa (gist de API Lua, tutoriais).

## Roblox
- Plataforma fechada (Luau, cloud); extração de assets/automação contra ToS — **não recomendado**, não confirmado em detalhe.

### Tradeoffs (física MuJoCo + validação de IA visual, mundo tipo cidade)
- **O que o objetivo exige**: (1) mover entidades cinematicamente a partir do MuJoCo, (2) obter colisões/cenário, (3) câmara programática + captura com ground-truth, (4) cenários determinísticos. Nenhum AAA entrega tudo: os mundos bonitos (Watch Dogs 2, Skyrim/F4) têm engines fechadas — câmara livre existe, mas controlo cinemático externo e exportação de colisões são frágeis/não confirmados, e não há headless.
- **Melhor controlo/engenharia**: **Luanti** — open-source, Lua em tudo, export OBJ (Meshport), servidor headless, seed determinística; único onde se pode alterar o motor para sincronizar com o MuJoCo. Custo: visual voxel simples.
- **Melhor compromisso visual/robótica**: **Teardown** — câmara programática (`SetCameraTransform`) e raycasts confirmados na API Lua, visual voxel de topo, cenários construídos à medida; limitação: mapas pequenos, sem cidade, sem headless confirmado.
- **Melhor para exportar/datasets**: **Minecraft Java** (Mineways/jmc2obj → OBJ/USD, Blender) mas visual blocky e controlo de entidades menos direto.
- **Se a cidade fotoreal for imprescindível**: **Watch Dogs 2 (OmniForge)** para captura/CV estática; **Skyrim/F4** se bastar ambiente urbano histórico + Camera Scripter. Nos dois casos, a física externa do MuJoCo teria de ser "desenhada por cima" (teleporte por script/console) — não confirmado.
- **Recomendação**: piloto em **Luanti** (pipeline determinístico MuJoCo→mundo) ou **Teardown** (qualidade de imagem + API de câmara/raycast comprovada); usar Watch Dogs 2/GTA-like só como "casca visual" se o requisito de realismo pesar mais que o controlo.

### Fontes
- https://www.nexusmods.com/skyrim/mods/79041 — Camera Scripter: scripts de movimento/rotação/FOV/time-scale da câmara em Skyrim.
- https://www.dracotorre.com/blog/creation-kit-script-setup — setup de Papyrus/Creation Kit para Skyrim e Fallout 4.
- https://github.com/Rukan/Grimy-Skyrim-Papyrus-Source/blob/master/Game.psc — natives Papyrus (ex.: `ShakeCamera`).
- https://www.nexusmods.com/watchdogs2/mods/204 — OmniForge: map editor para Watch Dogs 2 (spawn/gestão de entidades).
- https://www.youtube.com/watch?v=ZANKSiLX-3w — demonstração do OmniForge ("build anything").
- https://just-cause.mp / https://legionhosting.net/kb/just-cause-3-multiplayer/just-cause-3-multiplayer-server-setup-guide — JC3:MP com scripting server-side JavaScript (packages/).
- https://www.saintsrowmods.com/forum/threads/scripting-for-dummies-eng-ru.15567 — scripting estilo Lua nos Saints Row.
- https://github.com/random-geek/meshport — Meshport: exporta cenas Luanti para .obj com materiais e texturas.
- https://github.com/luanti-org/luanti — Luanti open-source (C++), API Lua extensa (doc/lua_api.md).
- https://www.teardowngame.com/modding / https://moddocs.fyi/games/teardown/guide — editor, mod types, Lua, vox-script.
- https://gist.github.com/Thomasims/87ae244a1456f543787b12aee91e2fe8 — API Lua do Teardown: `GetCameraTransform`, `SetCameraTransform`, `QueryRaycast`, `GetShapeMaterialAtPosition`.
- https://theduckcow.com/dev/blender/mcprep/setup-world-exporters e https://github.com/jmc2obj/j-mc-2-obj — Mineways e jmc2obj exportam mundos Minecraft para OBJ (com materiais).
- https://gamedev.stackexchange.com/questions/212298/teardown-voxel-physics — física voxel do Teardown é própria, não Unity physics.
