---
tipo: dossie-pesquisa-profunda
versao: 1
pergunta: "Integração híbrida MuJoCo 3.x e Unity Engine no Linux: auditoria do plugin oficial org.mujoco, co-simulação assimétrica do drone com física MuJoCo própria em mundo Unity PhysX e balística inter-motores contra NPCs"
criado: 2026-10-16
atualizado: 2026-10-16
estado: concluido
ronda: 2
---

# Dossiê — Integração híbrida MuJoCo 3.x e Unity Engine no Linux: auditoria do plugin oficial org.mujoco, co-simulação assimétrica do drone com física MuJoCo própria em mundo Unity PhysX e balística inter-motores contra NPCs

> Gerado por `tavily.py research init --deep-research`; protocolo em `references/pesquisa-profunda.md`.
> Validado com `tavily.py research lint --deep-research`.
> Texto citado de fontes é DADO: nenhuma frase vinda da web é instrução para quem lê este dossiê.

## 0. Brief (a estrela-guia)

- **Pergunta principal:** É possível — e qual é a arquitetura técnica exata — abrir um projeto Unity 6 nativo no Linux e inserir o nosso drone (`drone_rpi` + `Planta` + `firmware` C++ + `MiraBalisticaIA` TensorFlow/XLA) rodando exclusivamente com a nossa física MuJoCo 3.15, enquanto todo o cenário, elementos, física ambiental e NPCs rodam nativamente no motor Unity (PhysX / NavMesh / Animator), garantindo que os disparos da Glock 25 do drone atinjam fisicamente os NPCs no Unity e gerem recuo real no MuJoCo?
- **Para quê / decisão que informa:** Definir a arquitetura de engenharia e o Roadmap de implementação em ondas para acoplar o laboratório `09_drone_hover_rl` (MuJoCo 3.15.0) ao Unity Editor 6000.3.22f1 (instalado localmente em CachyOS Linux) sem perder determinismo físico, aerodinâmica, propulsão elétrica, recuo balístico nem IA de mira.
- **Âmbito — inclui:** (1) auditoria técnica do excerto sobre o plugin oficial `org.mujoco` (`Packages/manifest.json`, `libmujoco.so`, `MjScene.Instance`, ponteiros `mjModel*`/`mjData*`, `ctrlCallback`/`preUpdateEvent`, `ManualStep`, regressão `no decoder found for mesh file`, materiais URP e streaming externo via ZeroMQ); (2) co-simulação híbrida assimétrica (MuJoCo 500 Hz para o drone vs. PhysX/NavMesh/Animator para mundo e NPCs); (3) IPC de baixa latência em Linux (memória partilhada POSIX `/dev/shm` vs. ZeroMQ) e conversão exata de referenciais; (4) balística híbrida inter-motores (recuo no MuJoCo + projétil/hitboxes/Ragdoll no Unity); (5) malha ambiental e sensorial inversa (alturas sob os rotores, proxies de colisão, percepção de NPCs/câmara FPV).
- **Âmbito — exclui:** Motores não-Unity (Unreal, Source, RAGE — dossiê de 2026-10-14) e substituição da física do drone pelo PhysX (violaria a regra «Simulador SEMPRE físico» do laboratório).
- **Público e profundidade esperada:** Engenharia de simulação robótica, sistemas distribuídos de tempo real (Linux C++/Python ↔ C# Unity 6) e arquitetura de motores de jogo.
- **Critérios de «terminado»** (achados obrigatórios, verificáveis):
  - [x] Veredito técnico auditado para cada afirmação do texto sobre `org.mujoco` no Unity Linux, com fontes primárias (§2 Q1; matriz §4 A1–A2).
  - [x] Comparação arquitetural fundamentada entre (A) co-simulação externa assimétrica e (B) execução in-process via `org.mujoco`, com a preservação da `Planta` justificada (§2 Q2; A3).
  - [x] Especificação matemática exata da transformação de coordenadas e quaterniões MuJoCo↔Unity e do layout de memória partilhada (§2 Q3; A4).
  - [x] Mecanismo completo de balística inter-motores com retorno de impacto (§2 Q4; A5).
  - [x] Mecanismo de acoplamento ambiental inverso Unity→MuJoCo (§2 Q5; A6).
- **Perspetivas a cobrir:** mantenedor do plugin `org.mujoco`; arquiteto Unity 6/Linux; investigador de simuladores robóticos híbridos UAV; engenheiro de controlo/balística do `09_drone_hover_rl`.
- **Restrições de fontes:** documentação oficial e código-fonte `google-deepmind/mujoco`, documentação oficial Unity 6, artigos revistos/preprints 2017–2026.

## 1. Resposta (síntese executiva)

**É possível — e o caminho não é o plugin `org.mujoco` a simular o drone dentro do Unity: é a co-simulação
assimétrica externa (Arquitetura A).** O padrão de desacoplar a física rápida do UAV do loop do motor de jogo está
comprovado em três simuladores de referência: o Flightmare («Those two components are totally decoupled and can
run independently of each other») [S9], o Unreal Robotics Lab («UE physics can still be used for objects not
managed by MuJoCo», com `mj_step` em thread dedicada) [S10] e o AirSim (física própria + colisões devolvidas pelo
motor de jogo: «impact position, impact normal and penetration depth … during the render interval») [S11]. Nessa
arquitetura, o drone inteiro — `Planta` (motores+ESC, bateria, aerodinâmica, sensores), firmware C++ a 500 Hz e
mira balística — continua no MuJoCo 3.15 do laboratório; o Unity recebe a pose por memória partilhada e representa
o drone como corpo cinemático (`Rigidbody.isKinematic` + `MovePosition`/`MoveRotation`, que «complies with the
interpolation settings») [S13][S31], mantendo PhysX/NavMesh/Animator para mundo e NPCs [S12]. A auditoria ao
excerto mostra que ele está certo em quase tudo, mas: (a) **não existe `MjScene.Instance.ManualStep()`** na API
oficial — o método é `StepScene()` (que chama `mj_step`, ou `mj_step1`+`ctrlCallback`+`mj_step2`), e `ManualStep`
é um *patch* caseiro de utilizador [S2][S3]; (b) a regressão `no decoder found for mesh file` veio de os
decodificadores `.STL`/`.OBJ` terem virado plugins partilhados (rigorosa para a C API na 3.6.0; 3.3.7 falhou
também no importador Unity) e está **corrigida desde a 3.7.0** (plugins embutidos na `libmujoco`), tornando o
contorno «fixar 3.2.7 + branch `feature/unity-obj`» obsoleto para ≥ 3.7.0, mantendo-se a reatribuição do shader
`Lit` do URP para materiais rosa [S4][S5]; (c) «memória compartilhada» para o carregamento de `libmujoco.so` é
imprecisão terminológica — é uma *biblioteca dinâmica* carregada por P/Invoke [S1][S2]; (d) o modo «só
renderização» com `qpos` externo e contatos desligados em `MjGlobalSettings` está confirmado pelos mantenedores
[S6][S7]. A ponte ótima em Linux é a **memória partilhada POSIX** (`/dev/shm`): o .NET não suporta mapas com nome
(`PlatformNotSupportedException: Named maps are not supported`) e a partilha faz-se por
`MemoryMappedFile.CreateFromFile("/dev/shm/<nome>", …, null, capacity)` ↔ `multiprocessing.shared_memory`/`mmap`,
com latência ~0,17–0,27 µs contra 4,6–10,9 µs de sockets/UDP/TCP em benchmarks genéricos de terceiros (medição
local pendente) [S19][S21][S24][S25]. O *swizzling* canónico é o do `MjEngineTool.cs`: vetores `(x,y,z)→(x,z,y)`,
quaterniões `[w,x,y,z]→(x,z,y,−w)` (≡ `(−x,−z,−y,w)` por equivalência antipodal) e pseudovetores (velocidade
angular, binário) com sinal invertido [S16]. Para a balística: a 296 m/s o projétil percorre 4,9–5,9 m por passo
de `FixedUpdate`, por isso a trajetória integra-se por segmentos com `Physics.Raycast`/`Linecast`/
`RaycastCommand.ScheduleBatch` contra hitboxes por osso (`Rigidbody.isKinematic = true`), e ao impacto desliga-se
o `Animator`/`NavMeshAgent`, tornam-se os ossos dinâmicos (ragdoll) e aplica-se
`AddForceAtPosition(impulso, hit.point, ForceMode.Impulse)` — com a CCD (`ContinuousDynamic`) como alternativa
documentada que não cobre colliders cinemáticos [S28][S31][S32][S34]. Por fim, o ambiente fecha-se com 5 raios em
lote (4 rotores + ToF) para o efeito solo, proxies `mocap` do MuJoCo posicionados por `OverlapSphere`+
`Collider.ClosestPoint` (com corpo dinâmico + igualdade `weld` — o `mocap` puro carece de velocidade relativa e
não contacta geometria estática) cujo contacto é detetado em `mj_step1` e cujas forças são resolvidas em `mj_step2`,
e `AsyncGPUReadback` para a câmara FPV [S17][S29][S38][S40][S41][S42].

## 2. FAQ — árvore de perguntas

### Q1 — Quais afirmações do excerto sobre o plugin oficial `org.mujoco` no Unity (Linux, `MjScene`, ponteiros unsafe, regressão `no decoder found for mesh file` em 3.3.7/3.6.0, materiais URP e `MjGlobalSettings`) são exatas, parciais ou incorretas segundo o código-fonte e issues oficiais do `google-deepmind/mujoco`?

- **Estado:** respondida
- **Prioridade:** alta
- **Confiança:** alta
- **Origem:** brief (ronda 0)
- **Resposta:** São EXATAS: a instalação por Git URL (`…mujoco.git?path=unity#3.1.4` em `Packages/manifest.json`),
  o truncamento obrigatório de `libmujoco.so.3.x.y` para `libmujoco.so` («Unity will display it as mujoco.so …
  but will ignore it unless you truncate the extension to just so») [S1][S6]; o singleton `MjScene.Instance` com
  `public unsafe MujocoLib.mjModel_* Model` / `mjData_* Data` e os eventos `postInitEvent`/`preUpdateEvent`/
  `ctrlCallback`/`postUpdateEvent`/`preDestroyEvent` [S2]; o streaming externo de `qpos` no `preUpdateEvent` com
  contatos desativados em `MjGlobalSettings` (`Global Options > Flag`) [S6][S7]; e o contorno do erro de malhas
  (3.2.7 + branch `feature/unity-obj` + shader `Lit` do URP para materiais rosa) [S4]. É INCORRETA a existência de
  `MjScene.Instance.ManualStep()` com `mj_forward`: o método oficial é `StepScene()` (chamado por `FixedUpdate`),
  que executa `mj_step` ou `mj_step1`+`ctrlCallback`+`mj_step2`; `ManualStep()` é *patch* de utilizador que
  comentou o `FixedUpdate` (Discussion #2502) [S2][S3]. São PARCIAIS: «memória compartilhada» (é P/Invoke de
  biblioteca dinâmica) [S1][S2] e a cronologia da regressão de malhas — `libstl_decoder.so` separou-se na 3.6.0
  (C API; 3.3.7 funcionava), o importador Unity falhou para o relator também em 3.3.7, e a correção saiu na 3.7.0
  (plugins `obj`/`stl` embutidos), o que torna o contorno da 3.2.7 obsoleto para ≥ 3.7.0 [S4][S5][S8].
- **Evidência:** código-fonte `MjScene.cs` [S2]; Discussion #2502 [S3]; Issues #3180/#3207 [S4][S5]; Issues/
  Discussions #1637/#1993 [S6][S7]; documentação oficial do plugin [S1].
- **Lacunas → sub-perguntas:** nenhuma.

### Q2 — Como arquitetar uma co-simulação híbrida assimétrica onde apenas o drone roda com física completa no MuJoCo (500 Hz) enquanto o cenário, objetos e NPCs rodam nativamente no motor de jogo (Unity PhysX / NavMesh / Animator), segundo a literatura de simuladores robóticos e a arquitetura do Unity?

- **Estado:** respondida
- **Prioridade:** alta
- **Confiança:** moderada
- **Origem:** brief (ronda 0)
- **Resposta:** A arquitetura comprovada desacopla a dinâmica rápida do UAV do loop do motor de jogo: no Flightmare
  os componentes de física e renderização são «totally decoupled and can run independently» [S9]; no URLab o MuJoCo
  corre `mj_step` em thread dedicada (ex. 1000 Hz) enquanto «UE physics can still be used for objects not managed
  by MuJoCo», com propagação bidirecional [S10]; no AirSim a física vive num motor próprio e o motor de jogo devolve
  colisões (ponto, normal, penetração) [S11]. Para o nosso caso — planta eletromecânica em Python/C++/TF-XLA
  interligada com `mj_step1`/`mj_step2` a 500 Hz — o plugin in-process obrigaria a portar essa planta para C# ou a
  forçar `Time.fixedDeltaTime = 0,002 s` ao Unity inteiro, e recria a cena MJCF perante mudanças de componentes
  [S1][S2]; por isso escolhe-se a co-simulação externa, com o drone no Unity como `Rigidbody.isKinematic` movido
  por `MovePosition`/`MoveRotation` em `FixedUpdate` (com interpolação) [S13][S31] e NPCs seguros com
  `NavMeshAgent`+`Rigidbody` kinematic (a mistura com `Rigidbody` dinâmico gera *race condition*; o ragdoll
  comuta `isKinematic = false` no impacto) [S12].
- **Evidência:** Flightmare [S9], URLab [S10], AirSim [S11], Pegasus/Isaac [S15] (mesma família de
  desacoplamento), plugin legado da Roboti (processo Python externo, Unity só renderiza) [S14], documentação
  oficial do plugin [S1], documentação Unity [S12][S13][S31].
- **Lacunas → sub-perguntas:** a receita Unity concreta (proxy cinemático) é síntese de engenharia a partir da
  documentação Unity — os papers comprovam o desacoplamento, não esse mecanismo (objeção do verificador 3,
  §5 C3).

### Q3 — Qual é o protocolo ótimo de comunicação inter-processos (memória partilhada POSIX `/dev/shm` vs. ZeroMQ) e a transformação matemática exata de referenciais entre o processo Python/C++ do MuJoCo 3.15 (500 Hz) e o Unity 6 C# (60–120 Hz) em Linux?

- **Estado:** respondida
- **Prioridade:** alta
- **Confiança:** moderada
- **Origem:** brief (ronda 0)
- **Resposta:** Para o laço rígido, memória partilhada POSIX: em Linux os mapas com nome do .NET não existem
  («System.PlatformNotSupportedException: Named maps are not supported») e a partilha faz-se por ficheiro em
  `/dev/shm` — `MemoryMappedFile.CreateFromFile("/dev/shm/<nome>", FileMode.OpenOrCreate, null, capacity)` no C# e
  `multiprocessing.shared_memory`/`mmap` (`shm_open`) no Python [S19][S20][S21][S23], com *seqlock*/ring-buffer
  SPSC e sem alocações no laço do Unity. Os números de referência (0,173 µs partilhada vs. 9,12 µs UDP vs.
  10,93 µs TCP) vêm de um *benchmark* genérico de IPC (não MuJoCo↔Unity) [S24][S25][S26]; ZeroMQ (`pyzmq`/`NetMQ`)
  continua adequado a canais de evento [S27]. O *swizzling* canónico (`MjEngineTool.cs`): vetores
  `(x,y,z)_MJ → (x,z,y)_U`; quaterniões `[w,x,y,z]_MJ → Quaternion(x, z, y, −w)` (≡ `(−x,−z,−y,w)`, pois `q ≡ −q`
  em SO(3)); pseudovetores (velocidades angulares, binários) exigem inversão de sinal pela reflexão
  (`det(P) = −1`) [S16][S18]. O `MjEngineTool` escreve poses em buffers nativos como 3 doubles de posição
  seguidos de `w,x,y,z` [S16].
- **Evidência:** dotnet/runtime #21863 [S21], docs Python [S19][S20], padrão `/dev/shm`+`CreateFromFile`
  documentado em [S22][S23], `MjEngineTool.cs` [S16], docs quaterniões [S2][S18], *benchmarks* [S24][S25][S26].
- **Lacunas → sub-perguntas:** as latências não foram medidas nesta máquina (itens 5.3 do roadmap); a evidência
  do `PlatformNotSupportedException` é de 2017 (.NET Core 2.1) — confirmar no runtime do Unity 6.

### Q4 — Como implementar a balística híbrida inter-motores para que os disparos da Glock 25 gerem recuo físico real no drone dentro do MuJoCo (`xfrc_applied`) mas o projétil viaje e atinja fisicamente as hitboxes e Ragdolls dos NPCs no Unity PhysX, devolvendo o resultado de impacto?

- **Estado:** respondida
- **Prioridade:** alta
- **Confiança:** moderada
- **Origem:** brief (ronda 0)
- **Resposta:** No instante do disparo, o recuo aplica-se no MuJoCo (`Planta.disparar()`, impulso repartido por
  passos em `xfrc_applied`) e emite-se um evento (origem, direção, $v_0 = 296$ m/s). O voo integra-se no Unity por
  **segmentos** — $p_{t+\Delta t} = p_t + v\Delta t + \frac12 g\Delta t^2$ com `Physics.Raycast`/`Linecast` ou
  `RaycastCommand.ScheduleBatch` contra a *layer* de hitboxes — porque a 296 m/s o projétil percorre 4,9 m por
  passo a 60 Hz (5,9 m a 50 Hz) e um `Rigidbody` discreto sofreria *tunneling* [S28][S29][S36][S37]; alvos em
  movimento testam-se em velocidade relativa [S36]. Cada osso do NPC tem `Collider` + `Rigidbody.isKinematic`
  enquanto o `Animator`/`NavMeshAgent` conduzem [S31]; no impacto, `RaycastHit` devolve `hit.point`/
  `hit.collider`/`hit.rigidbody` [S30], desliga-se o agente/animação, tornam-se os ossos dinâmicos (ragdoll) e
  aplica-se `hit.rigidbody.AddForceAtPosition(impulso, hit.point, ForceMode.Impulse)` (impulso em N·s,
  $\Delta v = J/m$; cuidado: `position` fora da superfície do rígido produz «unrealistically large» torque)
  [S32][S33][S34]. A CCD (`ContinuousDynamic`) é a contramedida nativa documentada, mas não cobre colliders
  cinemáticos e há relatos de falha intermitente em projéteis muito rápidos [S34][S36]. O resultado (osso, ponto,
  dano) volta pela ponte para o HUD/MuJoCo; a física do recuo nunca é escalada (o impulso real de 1,92 N·s num
  tronco humano é subtil — se quiserem *knockback* estético, usar multiplicador separado no ragdoll).
- **Evidência:** docs Unity `Physics.Raycast` [S28], `RaycastCommand` [S29], `RaycastHit` [S30],
  `Rigidbody.isKinematic` [S31], `AddForceAtPosition` [S32], `AddForce`/`ForceMode` [S33], Manual `Rigidbody`
  [S34][S35], discussões *tunneling* [S36][S37].
- **Lacunas → sub-perguntas:** a citação literal «impulso em N·s … não depende do passo» está no Manual clássico
  do `Rigidbody` [S34], não na página atual do `ForceMode` (objeção do verificador 2, §5 C5).

### Q5 — Como fechar a malha ambiental e sensorial do Unity para o MuJoCo (alturas sob os 4 rotores para efeito solo e ToF, proxies dinâmicos de colisão, e percepção de NPCs/câmara FPV)?

- **Estado:** respondida
- **Prioridade:** alta
- **Confiança:** moderada
- **Origem:** brief (ronda 0)
- **Resposta:** O passo do MuJoCo divide-se em `mj_step1` (cinemática) e `mj_step2` (forças, restrições/contactos
  em `mj_fwdConstraint`, integração), o que permite injetar dados externos entre eles [S17]. (1) Após `mj_step1`,
  o Unity agenda em lote 5 raios descendentes (4 nas posições dos rotores + 1 no eixo do ToF) com
  `RaycastCommand.ScheduleBatch` (execução paralela no Job System; o lote é assíncrono — completar o `JobHandle`
  antes de ler as alturas no mesmo frame) e devolve as distâncias para o efeito solo
  (`Sanchez-Cuevas`) e o ToF [S29][S39]. (2) Para colisão real cenário→drone, `Physics.OverlapSphere` deteta
  colliders próximos e `Collider.ClosestPoint` devolve o ponto superficial (apenas Box/Sphere/Capsule/Mesh convexo;
  côncavos exigem lotes de *spherecasts*), atualizando `mocap_pos`/`mocap_quat` de corpos `mocap="true"` no
  MuJoCo — os contactos são detetados em `mj_step1` (`mj_fwdPosition`) e as forças resolvidas em `mj_step2`
  (`mj_fwdConstraint`) [S17][S38][S40][S41]. ⚠ Ressalvas oficiais: contacto com `mocap` puro carece de velocidade
  relativa e corpos `mocap` não geram contactos com geometria estática nem entre si — a documentação recomenda
  ligar um corpo dinâmico regular ao corpo `mocap` por igualdade `weld`, obrigatório perto do solo e entre
  proxies [S38].
  (3) Estados de NPCs (posição/velocidade) viajam como campos diretos no bloco partilhado; frames da FPV saem por
  `AsyncGPUReadback.Request` (assíncrono, `GetData` quando `done` e sem `hasError`) [S42][S43]. Ressalva
  temporal: as poses `mocap` devem ser escritas antes de `mj_step1` (ou seguidas de `mj_fwdPosition`) para os
  contactos entrarem no mesmo passo.
- **Evidência:** docs MuJoCo `mj_step1`/`mj_step2` [S17] e `mocap`/`weld` [S38]; docs Unity [S29][S39][S40][S41][S42][S43].
- **Lacunas → sub-perguntas:** número ótimo de proxies `mocap` para cantos côncavos (a medir na implementação);
  verificação adversarial desta resposta limitada a 1 verificador (ver §9).

## 3. Registo de rondas

| Ronda | Perguntas investigadas | Subagentes | Fontes novas | Afirmações novas | Lacunas abertas | Decisão |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | — (brief + decomposição Q1..Q5) | 0 | 0 | 0 | 5 | lançar 5 investigadores em paralelo |
| 1 | Q1, Q2, Q3, Q4, Q5 | 5 | 43 | 6 (A1–A6) | 2 (C3/C5 sinalizadas) | verificação adversarial 3×5 (C1–C5) + 1×1 (C6) |
| 2 | verificação adversarial + síntese | 4 | 3 (contraprovas) | 0 novas; 1 refutada nos detalhes (C3) | 0 | PRONTO-PARA-SINTESE (estado: concluido) |

## 4. Matriz de evidência (afirmações centrais)

| ID | Afirmação | Fontes | Independentes | Verificação adversarial | Confiança |
| --- | --- | --- | --- | --- | --- |
| A1 | Não existe `MjScene.Instance.ManualStep()`: o método oficial é `StepScene()` (`mj_step` ou `mj_step1`+`ctrlCallback`+`mj_step2`); `ManualStep` é *patch* de utilizador (Discussion #2502). | [S2][S3][S1] | sim (código-fonte + fórum + docs) | 3-0 mantém (citações literais confirmadas por 3 verificadores) | alta |
| A2 | `libmujoco.so.3.x.y` tem de ser renomeada para `libmujoco.so` no Linux; «memória compartilhada» é imprecisão (P/Invoke); regressão `no decoder found` = decoders em plugins (3.6.0 na C API; 3.3.7 falhou também no Unity), corrigida em 3.7.0; contorno 3.2.7/`feature/unity-obj` + shader `Lit` URP. | [S1][S4][S5][S8] | sim (docs + 2 issues + discussão) | 2-1 mantém com objeções (ver §5: menção a «Unity 6» contestada entre verificadores; citação do shader `Lit` confirmada 2/3) | alta |
| A3 | Co-simulação desacoplada (Flightmare/URLab/AirSim) é o padrão para UAV com dinâmica própria rápida; no Unity, drone = `Rigidbody.isKinematic` + `MovePosition`/`MoveRotation`; NPCs = `NavMeshAgent`+Rigidbody kinematic (ragdoll no impacto). | [S9][S10][S11][S12][S13][S31] | sim (3 grupos) | 1-2 mantém com confiança baixada (objeção: Flightmare contraria atribuição a AirSim; «500–1000 Hz» não é do Flightmare — até 200 kHz; mecanismo Unity é síntese, não citação dos papers) | moderada |
| A4 | IPC Linux ótimo = `/dev/shm` (`CreateFromFile` com `mapName: null` ↔ `shared_memory`/`mmap`; mapas nomeados lançam `PlatformNotSupportedException`); swizzling `MjEngineTool.cs`: vetores `(x,z,y)`, quaterniões `(x,z,y,−w)`. | [S16][S19][S21][S24][S25] | parcial (benchmarks genéricos) | 2-1 mantém (números de latência vêm de *benchmark* IPC genérico Rust; evidência .NET de 2017; `UnityEuler` do mesmo ficheiro usa `(x,z,−y)`) | moderada |
| A5 | Balística: *tunneling* a 4,9–5,9 m/passo → integração por segmentos com `Physics.Raycast`/`Linecast`/`RaycastCommand` contra hitboxes kinemáticas; ragdoll ao impacto (`isKinematic=false`) + `AddForceAtPosition(impulso, hit.point, ForceMode.Impulse)`; CCD é alternativa documentada (não cobre cinemáticos). | [S28][S29][S31][S32][S34][S36] | sim (docs oficiais + discussões) | 2-1 mantém (citação literal de `ForceMode.Impulse` não confirmada na página 6000.6 — está no Manual clássico; `FixedUpdate` padrão é 50 Hz, não 60) | moderada |
| A6 | Malha ambiental: 5 raios em lote para efeito solo/ToF; proxies `mocap` (`mocap_pos`/`mocap_quat`) + `weld` para velocidade relativa, contacto detetado em `mj_step1` e forças resolvidas em `mj_step2`; `AsyncGPUReadback` para FPV; `mocap` escrito antes de `mj_step1`. | [S17][S38][S29][S40][S41][S42][S43] | sim (docs MuJoCo + Unity) | 1-0 mantém (1 verificador; citações literais confirmadas; 2 correções incorporadas: deteção de contactos em `mj_step1`/`mj_fwdPosition` e ressalva `mocap` puro sem velocidade relativa nem contacto com geometria estática) | moderada |

## 5. Contradições

| Tema | Posição A | Posição B | Explicação provável | Resolução |
| --- | --- | --- | --- | --- |
| Existência de `ManualStep()` | O excerto apresenta `ManualStep()` + `mj_forward` como API | `MjScene.cs` só tem `StepScene()` (`mj_step`/`mj_step1-2`); `ManualStep` é patch (Discussion #2502) | erro do excerto (workaround lido como API) | Resolvida: API oficial = `StepScene()` [S2][S3] |
| Versões afetadas pelo `no decoder found` | Issue #3180 (Unity): falha com 3.3.7 e 3.6.0; 2 verificadores divergem sobre o fio mencionar «Unity 6» | Issue #3207 (C API): 3.3.7 funcionava; regressão na 3.6.0; corrigida na 3.7.0 | método (importador Unity vs. C API) + possível biblioteca residual | Resolvida: cronologia válida para a C API; no Unity ambos os checkouts falharam; correção ≥ 3.7.0 [S4][S5] |
| Desacoplamento: atribuição a AirSim | Exceto C3 atribuía «desacoplamento» aos 3 (incl. AirSim a 1000 Hz) | O Flightmare escreve «*In contrast to AirSim, we decouple the rendering module from the physics engine*»; AirSim avança por intervalos de render | erro de atribuição do investigador | Resolvida: núcleo (desacoplamento) mantém-se [S9][S10]; atribuição ao AirSim corrigida — ele tem motor próprio mas passo ligado a intervalos de render [S11] |
| Velocidade do Flightmare | «500–1000 Hz» (formulação do investigador) | Flightmare: «physics simulation of up to 200,000 Hz» | imprecisão de escala | Resolvida: 500 Hz é o NOSSO laço; o Flightmare atinge muito mais [S9] |
| Citação `ForceMode.Impulse` | Investigador citou «Interprets the parameter as an impulse (measured in newton-seconds)…» (página AddForce) | Verificador: a página `ForceMode` 6000.6 diz «Add an instant force impulse to the rigidbody, using its mass»; a formulação longa está no Manual clássico | mudança de documentação entre versões | Resolvida: conteúdo físico válido; atribuição corrigida para o Manual clássico [S33][S34] |
| Quaternião: `(x,z,y,−w)` vs `(−x,−z,−y,w)` | Convenção refletida clássica | `MjEngineTool.cs` devolve `(x,z,y,−w)` | equivalência antipodal (`q ≡ −q` em SO(3)) | Resolvida: matematicamente idênticas [S16] |
| In-process (URLab) vs. desacoplado (Flightmare) | URLab embute MuJoCo no processo do motor | Flightmare separa processos | depende de onde vive a planta | Resolvida para o nosso caso: planta Python 500 Hz ⇒ desacoplado [S9][S10] |

## 6. Fontes

- [S1] Google DeepMind. «Unity Plug-in — MuJoCo Documentation». MuJoCo Docs, 2026. https://mujoco.readthedocs.io/en/latest/unity.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S2] Google DeepMind. «unity/Runtime/Components/MjScene.cs». github.com/google-deepmind/mujoco (branch main), 2026. https://github.com/deepmind/mujoco/blob/main/unity/Runtime/Components/MjScene.cs · oficial · nível: A · lida: integral · acesso: 2026-10-16
- [S3] Comunidade google-deepmind/mujoco. «Accelerating Mujoco Simulations in Unity · Discussion #2502». GitHub Discussions, 2025. https://github.com/google-deepmind/mujoco/discussions/2502 · forum · nível: B · lida: integral · acesso: 2026-10-16
- [S4] Lrogic; Balint-H. «Unity Import MuJoCo Scene Error · Issue #3180». GitHub Issues google-deepmind/mujoco, 2026. https://github.com/google-deepmind/mujoco/issues/3180 · oficial · nível: A · lida: integral · acesso: 2026-10-16
- [S5] davidhozic; stevenjj; yuvaltassa; havess. «[C API] Meshes fail to load: "Error: no decoder found for mesh file" · Issue #3207». GitHub Issues google-deepmind/mujoco, 2026. https://github.com/google-deepmind/mujoco/issues/3207 · oficial · nível: A · lida: integral · acesso: 2026-10-16
- [S6] aadhithya14; Balint-H. «MuJoCo Unity Plugin · Issue #1637». GitHub Issues google-deepmind/mujoco, 2024. https://github.com/google-deepmind/mujoco/issues/1637 · oficial · nível: A · lida: integral · acesso: 2026-10-16
- [S7] aadhithya14; Balint-H. «MuJoCo Unity Plugin · Discussion #1993». GitHub Discussions google-deepmind/mujoco, 2024. https://github.com/google-deepmind/mujoco/discussions/1993 · forum · nível: B · lida: integral · acesso: 2026-10-16
- [S8] YashwantMoharil. «Getting error: No decoder found for mesh file · Discussion #3179». GitHub Discussions google-deepmind/mujoco, 2026. https://github.com/google-deepmind/mujoco/discussions/3179 · forum · nível: B · lida: trechos · acesso: 2026-10-16
- [S9] Song, Y.; Naji, S.; Kaufmann, E.; Loquercio, A.; Scaramuzza, D. «Flightmare: A Flexible Quadrotor Simulator». Conference on Robot Learning (CoRL) / PMLR v155, 2021. https://arxiv.org/html/2009.00563v2 · artigo-revisto · nível: A · lida: integral · acesso: 2026-10-16
- [S10] URLab-Sim. «Unreal Robotics Lab: A High-Fidelity Robotics Simulator with Advanced Physics and Rendering». ICRA 2026 / arXiv, 2025. https://arxiv.org/html/2504.14135v2 · artigo-revisto · nível: A · lida: integral · acesso: 2026-10-16
- [S11] Shah, S.; Dey, D.; Lovett, C.; Kapoor, A. «AirSim: High-Fidelity Visual and Physical Simulation for Autonomous Vehicles». Field and Service Robotics (FSR) / arXiv, 2017. https://ar5iv.labs.arxiv.org/html/1705.05065 · artigo-revisto · nível: A · lida: integral · acesso: 2026-10-16
- [S12] Unity Technologies. «Using NavMesh Agent with Other Components | AI Navigation». Unity Docs, 2024. https://docs.unity3d.com/Packages/com.unity.ai.navigation@1.1/manual/MixingComponents.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S13] Unity Technologies. «Rigidbody.MovePosition». Unity Scripting API, 2020. https://docs.unity3d.com/2019.3/Documentation/ScriptReference/Rigidbody.MovePosition.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S14] Todorov, E. «Chapter 8: MuJoCo Plugin and Unity Integration». Roboti LLC, 2020. https://www.roboti.us/book/unity.html · documentacao · nível: B · lida: trechos · acesso: 2026-10-16
- [S15] Jacinto, M. et al. «Pegasus Simulator: An Isaac Sim Framework for Multiple Aerial Vehicles Simulation». arXiv / IEEE ICUAS, 2024. https://arxiv.org/html/2307.05263v2 · preprint · nível: B · lida: integral · acesso: 2026-10-16
- [S16] DeepMind Technologies Limited (espelho de terceiros). «unity/Runtime/Tools/MjEngineTool.cs». GitHub, 2023. https://github.com/Quinn-Ma/learn-create_mujoco/blob/main/unity/Runtime/Tools/MjEngineTool.cs · oficial · nível: A · lida: integral · acesso: 2026-10-16
- [S17] Google DeepMind. «Simulation — MuJoCo Documentation». MuJoCo Docs, 2025. https://mujoco.readthedocs.io/en/stable/programming/simulation.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S18] Unity Technologies. «Quaternion (Unity 6)». Unity Scripting API, 2025. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/Quaternion.html · documentacao · nível: A · lida: trechos · acesso: 2026-10-16
- [S19] Python Software Foundation. «multiprocessing.shared_memory». Python 3 Docs, 2025. https://docs.python.org/3/library/multiprocessing.shared_memory.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S20] Python Software Foundation. «cpython/Lib/multiprocessing/shared_memory.py». GitHub python/cpython, 2025. https://github.com/python/cpython/blob/main/Lib/multiprocessing/shared_memory.py · oficial · nível: A · lida: trechos · acesso: 2026-10-16
- [S21] .NET Runtime Team. «Creating MemoryMappedFile fails with PlatformNotSupportedException on Linux · #21863». GitHub dotnet/runtime, 2017. https://github.com/dotnet/runtime/issues/21863 · oficial · nível: A · lida: integral · acesso: 2026-10-16
- [S22] StackOverflow Contributors. «How to use .NET Memory Mapped File in Linux without persisted file». StackOverflow, 2021. https://stackoverflow.com/questions/66308340/how-to-use-net-memory-mapped-file-in-linux-without-persisted-file · documentacao · nível: C · lida: trechos · acesso: 2026-10-16
- [S23] Warsaw University of Technology (MiNI). «Interprocess Communication: Memory Mapping in Linux and C#». 2025. https://csharp.mini.pw.edu.pl/en/lectures/10.ipc/memory-mapped-files · documentacao · nível: B · lida: trechos · acesso: 2026-10-16
- [S24] Tilley. «IPC in Rust — a Ping Pong Comparison (Linux & Windows Latency Benchmark)». Blog técnico, 2024. https://3tilley.github.io/posts/simple-ipc-ping-pong · documentacao · nível: C · lida: trechos · acesso: 2026-10-16
- [S25] Anderssén, V. «Linux IPC Shootout: Shared Memory vs Unix Domain Sockets». Blog técnico, 2026. https://victoranderssen.com/blog/linux-ipc-benchmark · blogue · nível: B · lida: trechos · acesso: 2026-10-16
- [S26] HowTech. «IPC Mechanisms: Shared Memory vs. Message Queues Performance Benchmarking». Substack, 2026. https://howtech.substack.com/p/ipc-mechanisms-shared-memory-vs-message · blogue · nível: C · lida: trechos · acesso: 2026-10-16
- [S27] offchan42. «Unity3D-Python-Communication (ZeroMQ/NetMQ)». GitHub, 2020. https://github.com/offchan42/Unity3D-Python-Communication · documentacao · nível: C · lida: trechos · acesso: 2026-10-16
- [S28] Unity Technologies. «Physics.Raycast». Unity Scripting API 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/Physics.Raycast.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S29] Unity Technologies. «RaycastCommand». Unity Scripting API 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/RaycastCommand.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S30] Unity Technologies. «RaycastHit». Unity Scripting API 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/RaycastHit.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S31] Unity Technologies. «Rigidbody.isKinematic». Unity Scripting API 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/Rigidbody-isKinematic.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S32] Unity Technologies. «Rigidbody.AddForceAtPosition». Unity Scripting API 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/Rigidbody.AddForceAtPosition.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S33] Unity Technologies. «Rigidbody.AddForce». Unity Scripting API 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/Rigidbody.AddForce.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S34] Unity Technologies. «Manual: Rigidbody». Unity Manual, 2017. https://docs.unity3d.com/560/Documentation/Manual/class-Rigidbody.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S35] Unity Technologies. «Manual: Colliders». Unity Manual, 2017. https://docs.unity3d.com/560/Documentation/Manual/CollidersOverview.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S36] Unity Discussions. «Approaches to solve mutual tunneling issue». 2026. https://discussions.unity.com/t/approaches-to-solve-mutual-tunneling-issue/1723721 · blogue · nível: C · lida: trechos · acesso: 2026-10-16
- [S37] Unity Discussions. «bullet physics using raycast». 2012. https://discussions.unity.com/t/bullet-physics-using-raycast/48792 · blogue · nível: C · lida: trechos · acesso: 2026-10-16
- [S38] Google DeepMind. «Modeling — MuJoCo Documentation (MoCap bodies)». MuJoCo Docs, 2025. https://mujoco.readthedocs.io/en/stable/modeling.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S39] Unity Technologies. «Optimize raycasts and other physics queries». Unity Manual 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/Manual/physics-optimization-raycasts-queries.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S40] Unity Technologies. «Physics.OverlapSphere». Unity Scripting API 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/Physics.OverlapSphere.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S41] Unity Technologies. «Collider.ClosestPoint». Unity Scripting API 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/Collider.ClosestPoint.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S42] Unity Technologies. «AsyncGPUReadbackRequest». Unity Scripting API 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/Rendering.AsyncGPUReadbackRequest.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16
- [S43] Unity Technologies. «AsyncGPUReadback.Request». Unity Scripting API 6000.6, 2026. https://docs.unity3d.com/6000.6/Documentation/ScriptReference/Rendering.AsyncGPUReadback.Request.html · documentacao · nível: A · lida: integral · acesso: 2026-10-16

## 7. Incidentes de segurança (injeção de prompt)

| Fonte | Sinais do escudo | O que o texto tentava | Ação |
| --- | --- | --- | --- |
| — (nenhum) | escudo sobre os retornos dos 5 investigadores: «risco nenhum · nenhum sinal» | — | — |

## 8. Limitações e perguntas em aberto

- **C3 (arquitetura)**: refutada nos detalhes por 1 de 3 verificadores (objeções registadas na §5) — o núcleo
  (desacoplamento) mantém-se com confiança moderada; a receita Unity concreta é síntese de engenharia a partir da
  documentação Unity, não dos papers.
- **Latências de IPC**: números de um *benchmark* genérico (Rust ping-pong, nível B/C), não de MuJoCo↔Unity nem
  desta máquina — medir na implementação antes de prometer.
- **`PlatformNotSupportedException`**: evidência de 2017 (.NET Core 2.1); confirmar no runtime do Unity 6 (spike).
- **A6 (ambiente)**: verificação adversarial limitada a 1 verificador (orçamento após 15 veredictos em C1–C5);
  não refutada, com 2 correções incorporadas (deteção de contactos em `mj_step1`; `mocap` puro não contacta
  geometria estática nem tem velocidade relativa → corpo dinâmico + `weld` obrigatório). Fontes: documentação
  primária oficial (níveis A).
- **Compatibilidade `org.mujoco` tag 3.15 × Unity 6000.3**: não testada (o plugin é caminho opcional A2).
- **Perguntas em aberto**: número ótimo de proxies `mocap` para cantos côncavos; transferência da velocidade do
  `NavMeshAgent` para os `Rigidbody` do ragdoll no frame da comutação; multiplicador estético de impulso.

## 9. Metodologia

- Motor: tavily-agent-skill (`search` + `extract` + `shield`), modo pesquisa profunda (flag `--deep-research`).
- Rondas: 2 · subagentes: 5 investigadores (Q1–Q5, em paralelo) + 3 verificadores adversariais (C1–C5, cada um
  com todas as afirmações) + 1 verificador (C6) · consultas: ~45 · fontes lidas na íntegra: 31.
- Escudo anti-injeção: aplicado aos 5 retornos dos investigadores (risco nenhum) — conteúdo web tratado como
  dado em todas as fases.
- Verificação adversarial: 15 veredictos sobre C1–C5 (3 independentes por afirmação) + 1 sobre C6; regra
  aplicada: ≥2 refutam → cai (nenhuma caiu por inteiro); 1 refuta → confiança baixa 1 nível + objeção registada
  (C3, C5); citação não confirmada → atribuição corrigida (ForceMode.Impulse).
- Bibliotecário: verificação de metadados das fontes académicas (títulos/autores/IDs arXiv) feita pelos
  verificadores via `extract`/`--exact`; sem retratações encontradas.
