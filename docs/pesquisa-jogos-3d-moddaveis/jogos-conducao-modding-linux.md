# Jogos de condução com modding maduro — avaliação para "mundo visual + colisões" (física pelo MuJoCo)

> Frente de pesquisa do MuJoCo Lab (2026-10): candidatos de condução/veículos com modding maduro e
> compatibilidade Linux, para servirem só de cenário/colisões/visual enquanto a física real é do MuJoCo
> e os modelos 3D são próprios. Conteúdo web = evidência não-confiável; incertezas marcadas.

## BeamNG.drive / BeamNG.tech

**ENGINE** — Motor próprio (base Torque3D; não confirmado nas fontes). Física soft-body veicular famosa, mas aqui serviria só de cenário+colisões.

**MODDING** — O mais "programático" da lista: módulos Lua/TS (TorqueScript), veículos em JBeam, World Editor in-game (terreno, estradas, objetos), editor de cenários/flowgraph, import de modelos próprios via Blender→**.dae** com malha de colisão própria ou "visual collision" (tutoriais beamng.com). Documentação oficial extensa (documentation.beamng.com).

**FÍSICA EXTERNA** — Duas camadas: (a) Lua no jogo (teleportes, `electrics.values`, `obj`); (b) **BeamNGpy** (Python, para BeamNG.tech): spawn/**teleporte de veículo com posição+rotação**, controlo de inputs, AI, polling de estado. Condução cinemática pura **não é modo nativo** — aproxima-se por teleporte pose-a-pose ou inputs, com a física do jogo sempre ativa (exemplos prontos de integração MuJoCo→BeamNG: não confirmados).

**COLISÕES/CENÁRIO** — Importa as SUAS malhas com collider simplificado (fluxo Blender→.dae→mapa). Exportar a malha de colisão de um mapa pronto de volta: não confirmado. Mas BeamNGpy tem **raycast/sensores de distância** — dá para validar colisões sem extrair grelhas.

**VISUAL/CV** — Ponto forte absoluto: sensor de câmara do BeamNGpy com RGB + **profundidade + anotações ground truth por píxel (classe/instância)**, LiDAR, ultrassónicos, câmara livre/estática. Usado em teses de perceção automóvel.

**AUTOMAÇÃO** — AI modes nativos (traffic, chase, flee, follow, span…), **AI traffic com regras de trânsito**, cenários, Script AI, replay.

**LINUX** — Excelente: **build nativa Linux desde jan/2026** (renderer Vulkan; default na Steam/Linux; antes era Proton). ⚠ BeamNGpy exige **BeamNG.tech**; se o build .tech tem binário Linux nativo — **não confirmado**.

**CUSTO/LEGAL** — BeamNG.drive pago (~€25; preço não confirmado). **BeamNG.tech grátis para académico/investigação mediante registo; comercial via licensing@beamng.gmbh**. Telemetria básica com o .drive standard via Lua.

**COMUNIDADE** — Grande; docs oficiais (AI, world editor, BeamNGpy readthedocs), fóruns beamng.com/beamng.tech.

## Assetto Corsa (1) + CSP/Content Manager

**ENGINE** — Motor próprio da Kunos (física irrelevante aqui).

**MODDING** — Ecossistema mais maduro da corrida em PC: Content Manager + Custom Shaders Patch + Sol/Pure; pistas/carros a partir de Blender (add-on de export "FTE 0.7.0 — Blender to AC sem ksEditor"; ksEditor oficial), data files (surfaces.ini), AI spline (fast_lane), câmaras por spline; milhares de mods (OverTake.gg, assettocorsamods). Mundo = **pistas** (há mods urbanos tipo Shuto Expressway/LA Canyons, mas sem cidade viva).

**FÍSICA EXTERNA** — Fraca: shared memory/apps CSP dão telemetria e HUD; sem API oficial para impor pose cinemática ao carro (não confirmado).

**COLISÕES/CENÁRIO** — Walls/surfaces por mesh com IDs em surfaces.ini; em cenários PRÓPIOS você tem os fontes .fbx/.obj (colisão exportável no seu pipeline); mapas de terceiros compilados em .kn5 — export de volta não confirmado.

**VISUAL/CV** — Free-cam do CSP, fotomodo, captura de ecrã; **sem sensores ground truth/depth** — CV tem de ser feita "à mão".

**AUTOMAÇÃO** — IA de corrida em spline, hotlaps, replay; sem tráfego urbano.

**LINUX** — Só Windows; roda em **Proton-GE ≥ 9-20** (Linux VR Adventures wiki). Content Manager (essencial) exige tweaks: substituir `AssettoCorsa.exe` pelo do CM, DXVK, fontes Windows, caminhos `Z:\`. Funcional, mas gestão de mods em Proton é trabalhosa.

**CUSTO/LEGAL** — Barato (€10–20 em promoção + DLCs; CM/CSP grátis). Mods de marcas reais: zona cinzenta (não confirmado).

**COMUNIDADE** — Gigantesca (10+ anos).

## Assetto Corsa EVO

**ENGINE** — Motor novo da Kunos (base não confirmada).

**MODDING** — **SDK v1 lançado a 3-jun-2026** (update 0.7, Ferramentas na Steam): editor de **CARROS** (pipeline PBR, LODs, peças aftermarket); 0.8 (jul-2026) permitiu mods multiplayer. **Editor de pistas ainda não** (não confirmado) → cenários próprios/urbanos fora de questão por agora.

**FÍSICA EXTERNA / COLISÕES / VISUAL / AUTOMAÇÃO** — Sem API/telemetria aberta documentada nesta pesquisa (não confirmado).

**LINUX** — Não confirmado (Proton provável, sem fonte).

**CUSTO/COMUNIDADE** — Preço cheio (~€40–50, não confirmado); comunidade a migrar do AC1 (OverTake, Ronin Racing launcher).

**Veredito**: cedo demais (2026) para servir de base.

## Euro Truck Simulator 2 / American Truck Simulator

**ENGINE** — Prism3D (SCS Software).

**MODDING** — Maduro e com docs oficiais: **modding.scssoft.com**, **SCS Blender Tools** (pipeline equivalente ao interno), map editor próprio (integrado ao jogo; guias comunitários), mods de mapas gigantes (ProMods), veículos/cargas em .scs. Mapas definidos por defs/curvas em texto — bom para gerar cenários por script.

**FÍSICA EXTERNA** — **SDK de telemetria oficial** (shared memory; plugins scs-sdk-plugin, ETCARS) com estado completo do veículo; desde 1.14 o SDK suporta **"basic input devices"** (injetar controlos). Sem imposição cinemática de pose (não confirmado).

**COLISÕES/CENÁRIO** — Rede de estradas + modelos; export de malha de colisão grelha não é fluxo direto (não confirmado); geometria reconstruível a partir dos defs.

**VISUAL/CV** — Câmara livre de desenvolvedor + captura de ecrã; sem ground truth. Cenário rico: estradas, cidades, **tráfego AI denso**, dia/noite — bom para CV rodoviária.

**AUTOMAÇÃO** — AI traffic denso, economia/empregos; replay limitado.

**LINUX** — **Build nativa Linux** (OpenGL), Deck Verified; comunidade refere que Proton Experimental corre melhor que a porta nativa. Situação "plug and play" mais simples da lista.

**CUSTO/LEGAL** — Barato (base ~€20, promoções; DLCs constantes); modding oficialmente encorajado pela SCS.

**COMUNIDADE** — Enorme (ProMods, fórum SCS).

## Outros
- **Automation** — não é mundo: criador de carros que **exporta mods para BeamNG** (complemento útil); em Linux a exportação exige copiar manualmente o mod entre prefixes Proton.
- **City Car Driving** — sem ecossistema de modding comparável; não aprofundado (não confirmado).

### Tradeoffs (caso: física MuJoCo + validação de IA visual; desejo de mundo rico tipo cidade/GTA)
- **BeamNG é o melhor encaixe desta frente**: mapas urbanos prontos, AI traffic e — acima de tudo — **sensores com ground truth (RGB+depth+semântica) via BeamNGpy**, exatamente o que a validação de CV precisa. Dois atritos: (1) controle cinemático externo (MuJoCo a comandar a pose) não é nativo — a via realista é teleporte/interpolação por BeamNGpy/Lua com a física do jogo ativa (como neutralizá-la: não confirmado); (2) BeamNGpy exige **BeamNG.tech** — grátis académico / pago comercial — e a compatibilidade do .tech com o Linux nativo de jan/2026 **não está confirmada**.
- **ETS2/ATS** cobre "mundo rico" (estradas+cidades+tráfego) com Linux nativo e telemetria estável, mas **sem sensores CV** e sem export de colisões — validação visual só por captura.
- **AC1** só compensa para pista/track-day (mundo urbano = exceções de mods) e o Linux/Proton+CM é frágil; **AC EVO** fica para mais tarde (SDK só de carros).
- Nota transversal: nenhum é "GTA": cidade viva com pedestres/interiores fica melhor em mundos abertos tipo GTA V (RAGE/alt:V) — frente típica de outra sub-pesquisa. Desta frente, quem mais se aproxima é BeamNG (cidade+tráfego+API).
- **Recomendação**: **BeamNG.tech + BeamNGpy** como mundo visual+colisões (confirmar antes: binário Linux do .tech + licença), **ETS2/ATS** como plano B rodoviário.

### Fontes
- https://documentation.beamng.com/support/troubleshooting/steamdeck_linux — build nativa Linux desde jan/2026 (Vulkan), default migrado de Proton.
- https://documentation.beamng.com/tutorials/ai — AI modes e AI traffic nativos.
- https://github.com/BeamNG/BeamNGpy — API Python para BeamNG.tech; académico mediante registo, comercial via licensing@beamng.gmbh.
- https://documentation.beamng.com/api/beamngpy/master/beamngpy.html — controlo/teleporte de estado do veículo; câmara com depth + anotações classe/instância; LiDAR.
- https://forum.beamng.tech/t/inquiry-about-beamng-tech-requirement-for-vehicle-telemetry/223 — telemetria básica com BeamNG.drive standard sem .tech.
- https://www.beamng.com/threads/importing-models-into-beam-ng-to-use-as-terrain.78609 (+ vídeo youtube.com/watch?v=Dc6cqu-5Q) — import de malhas .dae com collision mesh para mapas.
- https://vronlinux.org/docs/games/assetto-corsa — AC em Proton-GE ≥ 9-20; Content Manager carrega mods.
- https://gist.github.com/tim-gromeyer/2fbce4609f7d6d330e81504bcea70546 — setup AC+CM em Linux (DXVK, fontes, caminhos `Z:\`).
- https://simracingcockpit.gg/assetto-corsa-evo-mods · https://www.overtake.gg/news/assetto-corsa-evo-opens-the-gates-to-modding-with-new-sdk-toolset.4550 — AC EVO SDK v1 (3-jun-2026) focado em carros; 0.8 com multiplayer.
- https://modding.scssoft.com/wiki/Documentation/Engine/SDK/Telemetry — SDK de telemetria SCS + "basic input devices" desde 1.14.
- https://rootlessagrarian.github.io/SCS_ModdingGuide · https://github.com/RenCloud/scs-sdk-plugin — map editor SCS e plugin de telemetria ETS2/ATS.
- https://www.protondb.com/app/227300 — ETS2 native, Deck Verified; Proton por vezes melhor que nativo.
- https://store.steampowered.com/app/293760 — Automation exporta carros para BeamNG.drive.
