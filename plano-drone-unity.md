# Drone no Unity 6 com física MuJoCo própria — estudo de viabilidade, arquitetura e ROADMAP

> **Estado (2026-10-16) — documento Único de referência, na raiz do projeto.** Responde a: «é possível abrir um
> projeto Unity, meter o NOSSO drone (só a nossa física MuJoCo) dentro dele, deixar o cenário/elementos/NPCs a
> correr no motor Unity, e ainda assim os nossos disparos atingirem os NPCs?». **Resposta: SIM — com uma
> co-simulação assimétrica de dois motores, ligados por memória partilhada em `/dev/shm`.** O ROADMAP (§6) está
> no formato de execução em ondas com worktrees nomeadas. Evidência: dossiê de pesquisa profunda
> `pesquisas/2026-10-16-integracao-hibrida-mujoco-unity-drone-balistica-npcs.md` (43 fontes, verificação
> adversarial 3×5). Conteúdo web = `untrusted`, citado como evidência factual.
>
> Máquina: CachyOS Linux · MuJoCo 3.15.0 (Python 3.13, `uv`) · **Unity Editor 6000.3.22f1 já instalado**
> (`/home/ondokai/Unity/Hub/Editor/6000.3.22f1/`) com ficheiro de licença em
> `~/.config/unity3d/Unity/licenses/UnityEntitlementLicense.xml` (confirmar login no Hub — ver §7).

---

## 0. Veredito (duas frases)

**É possível, e o caminho não é o plugin `org.mujoco` dentro do Unity — é a ARQUITETURA A: co-simulação
assimétrica externa**, em que o drone inteiro (propulsão elétrica, bateria, aerodinâmica, firmware C++ a 500 Hz,
mira balística e o recuo da Glock 25) continua a viver no `mj_step1`/`mj_step2` do MuJoCo 3.15 do laboratório,
enquanto o Unity 6 só recebe a pose do drone por memória partilhada (proxy cinemático) e manda de volta o que o
mundo tem para oferecer: chão e obstáculos sob os rotores, colisões para o solver do MuJoCo resolver, e as
hitboxes dos NPCs para onde os projéteis voam. **Os disparos atingem os NPCs porque o voo do projétil e o impacto
são detetados no Unity por *raycasts* por segmentos (sem *tunneling* a 296 m/s), enquanto o recuo físico entra no
MuJoCo — cada motor resolve o que sabe fazer melhor.**

---

## 1. O pedido, ponto por ponto

| Requisito do dono | Possível? | Como |
|---|---|---|
| Abrir projeto Unity (Linux) e meter o nosso drone lá dentro | **Sim** | Unity 6.3 LTS já instalado nesta máquina; drone entra como GameObject proxy + visual livre (malha qualquer) |
| Drone com **só** a nossa física (MuJoCo 3.15 + `Planta`) | **Sim** | MuJoCo continua mestre do drone a 500 Hz (`dt = 2 ms`) num processo/thread próprio; nada do drone passa pelo PhysX |
| Cenário, elementos, NPCs tudo no motor Unity | **Sim** | PhysX + NavMesh + Animator do Unity correm livremente a 60–120 Hz; é o mundo "de verdade" do jogo |
| Os nossos disparos atingirem os NPCs | **Sim** | Projétil integrado por segmentos com `Physics.Raycast`/`RaycastCommand` contra hitboxes por osso; ao impacto → ragdoll + impulso (`AddForceAtPosition`, `ForceMode.Impulse`) |
| Recuo ("soco") do tiro real no drone | **Sim (já existe)** | `Planta.disparar()` aplica $J_{\text{tiro}} = 1{,}9162\ \text{N·s}$ via `xfrc_applied` entre `mj_step1` e `mj_step2`; recuperação pós-tiro em 0,10 s já medida |
| Efeito solo / ToF sobre prédios e terreno do Unity | **Sim** | 5 raios verticais (4 rotores + ToF) por lote (`RaycastCommand.ScheduleBatch`) → `planta.altura_rotores` antes de `mj_step2` |
| O drone bater em paredes/obstáculos do Unity com física real | **Sim** | Proxies `mocap` do MuJoCo posicionados pelo Unity (`OverlapSphere` + `ClosestPoint`); o contacto é resolvido pelo solver do MuJoCo — regra «simulador sempre físico» intacta |
| Determinismo passo a passo do drone | **Sim (drone)** | O drone é bit-a-bit reprodutível (reset com seed); o mundo Unity **não** é determinístico entre máquinas → gravar *ground truth* por frame, nunca confiar em replay (lição do dossiê de 2026-10-14) |

## 2. Auditoria técnica do texto-base (o que é verdade e o que não é)

Cada afirmação do excerto sobre o plugin oficial `org.mujoco` foi verificada contra o código-fonte e as issues
oficiais do `google-deepmind/mujoco` (dossiê §2 Q1, verificação adversarial em §4).

| # | Afirmação do excerto | Veredito | Correção (com fonte) |
|---|---|---|---|
| 1 | Dependência `"org.mujoco": "https://github.com/google-deepmind/mujoco.git?path=unity#3.1.4"` (ou 3.2.7) em `Packages/manifest.json` | **EXATA** | É exatamente o modo de instalação UPM por Git URL; a tag fixa a versão [S1] |
| 2 | Copiar `libmujoco.so.3.1.3` para o projeto **truncando** para `libmujoco.so` (senão o Editor ignora) | **EXATA** | Citação oficial: *"Make sure the mujoco library is named libmujoco.so and not `libmujoco.so.3.1.3` … Unity will display it as mujoco.so even if its extension is longer, but will ignore it unless you truncate the extension to just so"* [S1][S6] |
| 3 | «o motor carrega a API C completa do MuJoCo em **memória compartilhada**» | **IMPRECISA** | O que se carrega é uma *biblioteca dinâmica* (`libmujoco.so`) no espaço do processo via P/Invoke (`DllImport`) — «shared object» ≠ memória partilhada (IPC) [S1][S2] |
| 4 | `MjScene.Instance` expõe ponteiros unsafe `Model` (`mjModel*`) e `Data` (`mjData*`) | **EXATA** | `public unsafe MujocoLib.mjModel_* Model = null; public unsafe MujocoLib.mjData_* Data = null;` + eventos `postInitEvent`/`preUpdateEvent`/`ctrlCallback`/`postUpdateEvent`/`preDestroyEvent` [S2] |
| 5 | Manipular `qpos`/`qvel` em `preUpdateEvent`/`ctrlCallback` | **EXATA** | Padrão confirmado pelos mantenedores para acoplamento externo [S2][S6] |
| 6 | `MjScene.Instance.ManualStep()` com chamada direta a `MujocoLib.mj_forward` | **INCORRETA** | **Não existe `ManualStep()` na API oficial.** O método é `StepScene()` (chamado pelo `FixedUpdate`), que executa `mj_step` — ou `mj_step1` + `ctrlCallback` + `mj_step2` quando há callback de controlo. `ManualStep()` é um *patch* caseiro de um utilizador que comentou o `FixedUpdate` (Discussion #2502) [S2][S3] |
| 7 | Regressão `no decoder found for mesh file` em `.STL`/`.OBJ` nas versões 3.3.7 e 3.6.0 | **PARCIAL** | O erro é real (Issue #3180 — reportado no Unity com MuJoCo 3.6.0 e reproduzido com 3.3.7; dois verificadores divergem sobre o fio mencionar «Unity 6», ver dossiê §5) e veio de os decodificadores de malha terem virado **plugins partilhados** (`libstl_decoder.so`) sem atualização do plugin Unity; a isolagem «regressão da 3.6.0» é rigorosa para a **C API** (3.3.7 carregava STL/OBJ; Issue #3207) e menos para o lado Unity; **corrigida na 3.7.0** — os plugins `obj`/`stl` voltaram a ser embutidos na `libmujoco` principal [S4][S5][S8] |
| 8 | Contorno: fixar 3.2.7 (ou branch `feature/unity-obj`) + reatribuir materiais URP | **EXATA, mas obsoleto ≥ 3.7.0** | Confirmado na Issue #3180: usar 3.2.7 com `feature/unity-obj` (converter para `.obj`) e mudar o shader do material para **`Lit` do URP** (o rosa vem do material default do antigo Built-in Renderer) [S4]. Com MuJoCo ≥ 3.7.0 o contorno da versão deixa de ser necessário (decoders embutidos na lib principal); a reatribuição do shader `Lit` continua a aplicar-se a qualquer importação |
| 9 | Operar MuJoCo externamente (Python) e transmitir `qpos` por ZeroMQ para renderização cinemática, desativando contatos em `MjGlobalSettings` | **EXATA** | Confirmado nas Issues/Discussions #1637/#1993: escrever `e.data->qpos`, zerar `qvel` no `preUpdateEvent`, e no componente `MjGlobalSettings` → `Global Options > Flag` desligar os elementos de simulação redundantes [S6][S7] |

**Consequência prática:** o excerto está certo em quase tudo, errado num ponto crítico (`ManualStep`) e desatualizado
noutro (a regressão de malhas está **corrigida desde a 3.7.0** — e o nosso MuJoCo 3.15.0 já traz `obj`/`stl`
embutidos). Mas — ver §3 — para o nosso caso o plugin é caminho **secundário**, não o principal.

## 3. Arquitetura escolhida (A) e a recusada (B)

### 3.1 Porque NÃO (B) — plugin `org.mujoco` in-process a simular o drone

O plugin é excelente para modelos MJCF puros, mas o nosso drone **não é um XML**: é o XML + `lab/drone_rpi/`
(`planta.py`, `propulsao.py`, `bateria.py`, `aero.py`, `sensores.py`) + firmware C++ a 500 Hz + TensorFlow/XLA —
~1300 linhas de física eletromecânica que se entrelaçam com `mj_step1`/`mj_step2` **em Python**. Com o plugin
in-process seria necessário portar tudo isso para C#, ou forçar `Time.fixedDeltaTime = 0,002 s` ao Unity inteiro
(PhysX dos NPCs a 500 Hz é desperdício e instabilidade), e qualquer adição/remoção de componentes recria a cena
MJCF inteira [S1][S2]. **Regra de ouro do laboratório: o drone passa sempre por `mj_step`.** (B) fica arquivado.

### 3.2 Porquê (A) — co-simulação assimétrica externa (estilo Flightmare/URLab/AirSim)

É a arquitetura comprovada na literatura para UAVs com dinâmica própria rápida dentro de motores de jogo:
- **Flightmare** (CoRL 2021): física do quadricóptero e motor de renderização/cena *«totally decoupled and can run
  independently»*, com frequências distintas [S9];
- **Unreal Robotics Lab** (ICRA 2026): MuJoCo numa thread dedicada de alta frequência, *«UE physics can still be
  used for objects not managed by MuJoCo»*, com propagação bidirecional de forças [S10];
- **AirSim**: física do veículo a 1000 Hz num motor próprio + colisões devolvidas pelo motor de jogo (posição,
  normal, penetração) [S11].

Honestidade sobre a evidência: os papers comprovam o **desacoplamento** (cada motor no seu ritmo) e a
**coexistência** de dois motores de física na mesma cena; a receita Unity concreta do §4 (proxy cinemático com
`Rigidbody.isKinematic` + `MovePosition`/`MoveRotation`) é síntese de engenharia a partir da documentação oficial
do Unity [S13][S31], não uma citação dos papers (no Flightmare a ligação é por mensageria entre processos; no
URLab o MuJoCo propaga forças às entidades do motor).

```
┌─────────────────────────────┐          /dev/shm/mjdrone           ┌─────────────────────────────┐
│  PROCESSO MUJOCO (Python)   │   poses 500 Hz ──────────────────▶  │      PROCESSO UNITY 6       │
│  dt = 2 ms · mj_step1/2     │   ◀──────────────────────────────   │  FixedUpdate 60–120 Hz      │
│  ─────────────────────────  │   alturas·proxies·impactos·NPCs     │  ─────────────────────────  │
│  Planta: motores+ESC+bateria│                                     │  Proxy drone (isKinematic)  │
│  aero: solo/inflow/VRS      │                                     │  PhysX: mundo + objetos     │
│  firmware C++ 500 Hz        │                                     │  NavMesh+Animator: NPCs     │
│  MiraBalisticaIA (TF/XLA)   │                                     │  RaycastCommand: 5 raios    │
│  Glock 25: recuo J=1.92 N·s │                                     │  Balística por segmentos    │
│  mj_forward + contactos     │                                     │  Ragdoll + impulso no NPC   │
└─────────────────────────────┘                                     └─────────────────────────────┘
        MESTRE DO DRONE (100 % física nossa)                                MESTRE DO MUNDO
```

**Modo opcional (A2) — plugin `org.mujoco` só como *renderer*:** para depuração de paridade visual, o padrão
#1637/#1993 continua válido (streaming de `qpos` no `preUpdateEvent` + `MjGlobalSettings` a desligar contatos).
Fica como ferramenta, não como dependência do caminho principal (A1 não precisa do plugin no Unity).

### 3.3 O que NÃO muda no laboratório

`lab/drone_rpi/*`, `experiments/09_drone_hover_rl/{env_real,fc,estimador,politica,hardware,valida_real,
mira_balistica,treinar_mira_gpu}.py`, `firmware/`, os testes e os benchmarks **ficam intactos**. A ponte é um
módulo novo que consome a `Planta` existente. O MuJoCo continua a ser o ÚNICO simulador físico do drone e o
contacto do drone com o mundo continua a ser resolvido pela física do MuJoCo (contacto detetado em `mj_step1`,
forças resolvidas em `mj_step2`; o Unity só informa *onde* estão as
superfícies).

## 4. Especificação técnica

### 4.1 Ciclo temporal (multi-*rate*)

| Laço | Frequência | Onde | O que faz |
|---|---|---|---|
| Física do drone | **500 Hz** (2 ms) | Python/MuJoCo | `mj_step1` → cinemática → `Planta.passo()` (motores, V_bus, κ_T/κ_Q, sensores, `xfrc_applied`) → `mj_step2` |
| Mundo + NPCs + render | 60–120 Hz | Unity | `FixedUpdate`: ler snapshot do drone, `MovePosition`/`MoveRotation`, PhysX, NavMesh, Animator, balística |
| Ambiental (alturas/proxies) | 50–60 Hz | Unity → MuJoCo | batch de raios + `OverlapSphere` → escrita no bloco partilhado antes do `mj_step1` seguinte |
| Eventos (tiro/impacto) | assíncrono | ambos | mensagens no mesmo bloco com *sequence number* |

Ordem por passo do MuJoCo (a malha fecha aqui):
1. Ler do `/dev/shm`: alturas sob os 4 rotores + ToF, proxies `mocap` do cenário, posições/velocidades dos NPCs.
2. `mj_step1` (cinemática atualizada).
3. `Planta.passo()` — efeito solo com as alturas vindas do Unity, sensores, `disparar()` se houver gatilho.
4. `mj_step2` (contactos do drone contra os proxies `mocap` resolvidos PELO MuJoCo + integração).
5. Publicar pose/velocidade/do drone, estado da arma e eventos no `/dev/shm`.

### 4.2 Ponte IPC — memória partilhada POSIX (`/dev/shm`)

Escolha fundamentada: a memória partilhada em `/dev/shm` (tmpfs em RAM) atinge **0,17–0,27 µs** por operação
(zero *syscalls* após o `mmap`) contra **4,6–10,9 µs** de Unix sockets/UDP/TCP loopback — 20–60× mais rápida e
sem pressão de GC [S24][S25][S26] (⚠ valores de *benchmarks* técnicos de terceiros, níveis B/C — a Onda 5 mede-os
nesta máquina antes de qualquer promessa). ZeroMQ/NetMQ (que o excerto sugere) continua válido para canais de
evento esporádicos, mas não para o laço rígido.

**Contrato do bloco** (`/dev/shm/mjdrone`, permissões 0600) — *seqlock* (escritor incrementa `seq` para ímpar,
escreve, incrementa para par; leitor relê `seq` e repete se mudou/ímpar):

```
offset  tipo      campo
0       u64       seq                    (seqlock)
8       f64       t_mujoco               tempo do MuJoCo (s)
16      3×f64     drone_pos              [x,y,z] MJ (m)
40      4×f64     drone_quat             [w,x,y,z] MJ
72      6×f64     drone_qvel             [v; ω] MJ (mundo)
120     4×f64     ctrl_rotor             empuxos (N)
152     5×f64     altura_rotor[4]+tof    alturas ao solo (m)  ← Unity escreve
192     4×3×f64   proxy_pos[4]           centros dos proxies mocap ← Unity escreve
320     4×4×f64   proxy_quat[4]
448     2×3×f64   npc_pos_vel[2]         alvos (pos+vel) ← Unity escreve
520     u64       evento_id              id do último disparo/impacto
528     u32       evento_tipo            1=disparo 2=impacto_npc 3=impacto_mundo
536     3×f64     evento_pos             origem/impacto (m)
568     f64       evento_impulso         N·s (para o ragdoll)
```

- **Python (produtor 500 Hz):** `multiprocessing.shared_memory.SharedMemory(name="mjdrone", create=True, size=…)`
  ou `os.open("/dev/shm/mjdrone") + mmap` — arrays NumPy sobre o `buffer`, sem serialização [S19][S20].
  ⚠ *Bug* conhecido do `resource_tracker` (Python ≤ 3.13): o consumidor deve usar `track=False` (ou abrir por
  `mmap` puro) senão o bloco é removido quando um processo termina.
- **C# (consumidor no Unity):** `MemoryMappedFile.CreateFromFile("/dev/shm/mjdrone", FileMode.OpenOrCreate, null, capacity)`
  + `CreateViewAccessor` + ponteiro `unsafe` sobre `struct` não gerida. **Proibido** `MemoryMappedFile.CreateOrOpen(mapName, …)`:
  em Linux lança `PlatformNotSupportedException` («Named maps are not supported») [S21] (⚠ evidência de 2017,
  .NET Core 2.1 — confirmar no *spike* da Onda 2 com o runtime exato do Unity 6).
- **GC:** zero alocações no laço — structs `unmanaged`, leitura por ponteiro, interpolação `Slerp`/`Lerp` entre os
  dois últimos *snapshots* para o render.

### 4.3 Referenciais e quaterniões (o *swizzling* oficial)

MuJoCo: **mão direita**, `+Z` cima, quaternião `[w,x,y,z]`. Unity: **mão esquerda**, `+Y` cima, `Quaternion(x,y,z,w)`.
A conversão canónica é a do `MjEngineTool.cs` do próprio plugin [S16][S18]:

```
vetor MJ (x,y,z)          → Unity (x, z, y)                 # involutivo, permuta y↔z
quaternião MJ [w,x,y,z]   → Unity (x, z, y, −w)             # ≡ (−x, −z, −y, w)  (q ≡ −q em SO(3))
vel. angular / binário MJ → Unity (−x, −z, −y)              # pseudovetores: reflexão (det P = −1) exige sinal
```

⚠ Atenção ao «frente»: o *swizzle* padrão põe o nariz do drone (MJ `+X`) em `+X` do Unity; se o *proxy* Unity
assumir `+Z` como frente (convenção usual de personagens), acrescentar a rotação fixa de `−90°` em torno de `Y`
no *proxy* e travá-la com testes de paridade (item 1.2 do ROADMAP).

### 4.4 Balística inter-motores (o tiro que atinge NPCs)

Instante do disparo (tudo o que é físico fica no MuJoCo):
1. `Planta.disparar()` — impulso $J_{\text{tiro}} = 1{,}9162\ \text{N·s}$ repartido por $N = 10$ passos de 2 ms em
   `xfrc_applied` na boca do cano (`boca_cano`), com $\Delta v = J/m$ e $\Delta\omega_{pitch} = -z_{cano}J/I_{yy}$
   (o cano está 129,5 mm acima do CM ⇒ o nariz «cabra»; recuperação medida em 0,10 s). O projétil sai com
   $v_0 = 296\ \text{m/s}$ + velocidade da boca.
2. Evento `{evento_id, tipo=1, origem, direção, v0}` publicado no bloco.

Voo e impacto (o que é do jogo fica no Unity):
3. A 296 m/s o projétil anda **4,93 m por passo de `FixedUpdate` a 60 Hz (5,92 m a 50 Hz — o `FixedUpdate` do
   Unity corre por omissão a 50 Hz)** — um `Rigidbody` comum atravessaria o NPC (*tunneling*). Por isso a
   trajetória $p_{t+\Delta t} = p_t + v\Delta t + \frac12 g \Delta t^2$ é integrada por **segmentos**, testando
   cada segmento com `Physics.Raycast`/`Linecast` (ou `RaycastCommand.ScheduleBatch` em lote paralelo) contra a
   *layer* de hitboxes + mundo [S28][S29]. Perto do alvo, subdividir o segmento
   ($k = \lceil |v|\Delta t / 0{,}5\,\text{m} \rceil$). Alvo em movimento: lançar o raio no espaço de velocidade
   relativa (subtrair o deslocamento do NPC) [S36]. A contramedida nativa documentada da Unity é a deteção
   contínua (CCD, `CollisionDetectionMode.ContinuousDynamic`) [S34], mas ela não cobre colisões contra colliders
   puramente cinemáticos (como as hitboxes por osso) e custa CPU; para projéteis de 296 m/s contra NPCs animados,
   o teste por segmentos é o padrão comum e mais fiável.
4. **Hitboxes dos NPCs:** cada osso tem `Collider` + `Rigidbody.isKinematic = true` enquanto o `Animator`/
   `NavMeshAgent` conduzem; o `RaycastHit` devolve `hit.collider` (osso), `hit.point`, `hit.normal` [S30][S31].
5. **Reação:** desativar `NavMeshAgent` + `Animator`, `isKinematic = false` nos ossos (ragdoll) e
   `hit.rigidbody.AddForceAtPosition(J_restante·dir, hit.point, ForceMode.Impulse)` — impulso em N·s,
   $\Delta v = J/m$, independente de `fixedDeltaTime`, com força **e** binário no ponto certo [S32][S33]
   (⚠ a formulação literal «impulso medido em newton-segundos … não depende do comprimento do passo de
   simulação» vem do Manual clássico do `Rigidbody` [S34]; a página atual do `ForceMode` diz apenas «instant
   force impulse … using its mass»).
6. Evento `{tipo=2, npc_id, osso, ponto, impulso}` → bloco → MuJoCo/HUD (`acertos_npc`, `erros_npc`, mira).
   ⚠ Realismo: $J = 1{,}92\ \text{N·s}$ num tronco de 30–80 kg dá $\Delta v \approx 0{,}02$–$0{,}06\ \text{m/s}$ —
   o ragdoll cai pela desativação do Animator; se quiserem "soco" visual maior, usar um multiplicador estético
   **separado e registado** (a física do drone nunca é escalada).

### 4.5 Malha ambiental inversa (Unity → MuJoCo)

| Necessidade | Mecanismo | Onde entra |
|---|---|---|
| Efeito solo (Sanchez-Cuevas) + ToF VL53L1X sobre prédios/mesas | 5 raios descendentes (4 sites de rotor + eixo do ToF) por `RaycastCommand.ScheduleBatch` (lote assíncrono: `JobHandle.Complete()` antes de ler no mesmo frame) | `planta.altura_rotores` / `planta.tof` antes de `mj_step2` [S17][S29][S39] |
| Drone bate em parede/obstáculo com física real | `Physics.OverlapSphere` à volta do drone + `Collider.ClosestPoint` (Box/Sphere/Capsule/Mesh convexo) → pose dos proxies `mocap` (`mocap_pos`/`mocap_quat`) escrita **antes** de `mj_step1` | contacto detetado em `mj_step1` (`mj_fwdPosition`) e forças resolvidas em `mj_step2` (`mj_fwdConstraint`) — o MuJoCo decide o ressalto/atrito [S17][S38][S40][S41] |
| Obstáculos móveis com velocidade relativa | corpo dinâmico regular ligado ao `mocap` por igualdade `weld` (recomendação oficial — **obrigatório**: `mocap` puro não contacta geometria estática nem entre si e carece de velocidade relativa) | impulso correto no contacto [S38] |
| Cantos côncavos (MeshCollider não convexo) | `ClosestPoint` não serve → lotes de `SpherecastCommand` orientados pelas normais | proxies orientados [S41] |
| Câmaras FPV / visão para a mira | `RenderTexture` + `AsyncGPUReadback.Request` (assíncrono, sem bloquear GPU nem física) | `MiraBalisticaIA` / overlay [S42][S43] |
| Posições dos NPCs para a mira | campos diretos no bloco partilhado (pos+vel por NPC) | preditor balístico (`prever_tiro_bola`) |

### 4.6 Instalação e versões (Linux, esta máquina)

1. **Projeto Unity 6 (URP)** — Hub + Editor `6000.3.22f1` já instalados; criar projeto pela suíte Unity desta
   máquina (nunca abrir um projeto com Editor de versão diferente sem avisar — upgrade irreversível).
2. **Caminho principal (A1):** sem plugin MuJoCo no Unity — o drone é um GameObject proxy + malha visual qualquer.
3. **Caminho opcional (A2, depuração):** plugin `org.mujoco` via Git URL na `Packages/manifest.json`, **tag
   coincidente com a versão do motor** (3.15.x — os decoders `obj`/`stl` são nativos desde a 3.7.0, logo o erro
   `no decoder found` não deve aparecer; se aparecer, fallback a `#3.2.7` + branch `feature/unity-obj`).
   Copiar `libmujoco.so.3.15.0` → **`libmujoco.so`** (truncar a extensão!) para dentro do projeto [S1][S6].
4. **URP:** materiais importados ficam rosa (shader Built-in) → atribuir shader **`Lit`** do URP [S4].
5. Nunca commitar `Library/`, `Temp/`, `.ulf`, `.alf`; testes EditMode/PlayMode pela suíte Unity desta máquina.

## 5. Resumo da arquitetura de dados

```
   teclas/WASDQE ──▶ firmware C++ 500 Hz ──▶ ctrl[4] ──▶ mj_step1 ──▶ Planta.passo() ──▶ mj_step2
                                                     │                                   │
                        alturas·proxys·npcs ◀── /dev/shm ──▶ pose·qvel·eventos ────────┘
                                                             │
                                       Unity FixedUpdate ◀───┘
                                       MovePosition(proxy) · PhysX(mundo) · NavMesh(NPCs)
                                       RaycastCommand(5 raios) · balística por segmentos
                                       impacto no NPC ──▶ ragdoll + AddForceAtPosition ──▶ evento ──▶ HUD
```

## 6. ROADMAP — execução em ondas (worktrees nomeadas, uma integração de cada vez)

**Princípios de execução** (para quem executar, humano ou agente):
- Cada sub-tarefa trabalha na sua **worktree nomeada** (branch `do/<nome>`, kebab-case, prefixo da onda), nunca
  direto no branch de integração.
- Integração **uma sub-tarefa por vez** (*squash-merge* + commit limpo com atribuição de culpa), sempre seguida do
  **gate** da onda; gate vermelho → nada se limpa, a sub-tarefa vira material de correção.
- Toda a sub-tarefa termina **integrada** ou **fechada com motivo registado** — nunca esquecida. O relatório final
  tem secção obrigatória «Não integrado» (escrever "nenhum" se vazia).
- Antes de abrir a onda N+1: sobras da onda N = 0 (portão inter-onda).
- Recursos *singleton* (contrato do bloco, `manifest.json`, portas/locks) mudam **só** no commit de preparação da
  onda, com um único dono.
- Recolha de memória no fim: o que foi durável e verificado vai para a memória do projeto (decisões, armadilhas).

### 6.1 Tabela de ondas

| Onda | Sub-tarefa | Worktree (branch `do/…`) | Entrega observável | Arquivos que toca | Pesquisa externa? |
|---|---|---|---|---|---|
| 0 · PREP | Contrato da ponte congelado | `onda0-contrato-ponte` | `UNITY_CONTRATO.md` + schema binário + stubs + `gate.sh` registado | `experiments/09_drone_hover_rl/{UNITY_CONTRATO.md,ponte_unity/,gate.sh}` | **não** |
| 1 · Ponte (Python) | Schema + *seqlock* + publisher 500 Hz | `onda1-schema-seqlock` | Bloco `/dev/shm/mjdrone` publicado a 500 Hz; teste de 10⁷ leituras sem corrupção | `ponte_unity/{schema.py,shm.py}` | **não** |
| 1 | Conversão de referenciais com paridade | `onda1-swizzle-referencial` | `coords.py` + testes de paridade contra `MjEngineTool.cs` (vetores, quaterniões, pseudovetores, rotação de frente) | `ponte_unity/coords.py`, `testes_ponte/` | **sim** — contrato de *swizzling* de fonte externa [S16] |
| 1 | Identidade da planta com a ponte ligada | `onda1-identidade-planta` | `bench_treino.py identidade` + `valida_real.py` continuam bit-a-bit (168/168, 319/319) | `ponte_unity/planta_ponte.py` | **não** |
| 2 · Unity | Projeto Unity 6 URP Linux + cena base | `onda2-projeto-unity-urp` | Projeto abre no Editor 6000.3.22f1 (Linux), cena com terreno + luz + câmara; EditMode tests verdes | `experiments/09_drone_hover_rl/unity/` | **sim** — versão/URP/licença Unity 6 |
| 2 | Leitor C# do `/dev/shm` | `onda2-reader-shm-csharp` | `MjDroneShm.cs` lê snapshots com *seqlock*, zero GC no Profiler, interpolação Slerp | `unity/Assets/Ponte/` | **sim** — `MemoryMappedFile` em Linux .NET [S21] |
| 2 | Proxy cinemático do drone | `onda2-proxy-drone-cinematico` | GameObject segue a pose do MuJoCo (erro < 1 mm / 0,1°), `isKinematic` + `NavMeshObstacle`, empurra objetos PhysX | `unity/Assets/Ponte/DroneProxy.cs` | **sim** — semântica `MovePosition` [S13] |
| 3 · NPCs e balística | NPC com hitboxes + ragdoll | `onda3-npc-hitboxes-ragdoll` | NPC anda (NavMesh+Animator), ossos com colliders kinematic; ao ser atingido vira ragdoll | `unity/Assets/NPCs/` | **sim** — Animator/NavMesh/Ragdoll [S12][S31] |
| 3 | Projétil por segmentos + impacto | `onda3-balistica-segmentada` | Tiro a 296 m/s detetado sem *tunneling* (100/100 acertos a 2 m em teste), impulso no osso certo | `unity/Assets/Balistica/` | **sim** — `RaycastCommand`/`AddForceAtPosition` [S29][S32] |
| 3 | Evento de disparo ↔ recuo MuJoCo | `onda3-disparo-recuo-sincronizado` | `Planta.disparar()` dispara junto do evento Unity; recuo medido igual ao de `valida_real.py`; HUD `acertos_npc` | `ponte_unity/eventos.py`, `unity/Assets/Balistica/` | **não** |
| 4 · Ambiente | 5 raios (rotores + ToF) em lote | `onda4-raycasts-rotores-tof` | Pairagem sobre telhado a 0,5 m usa as alturas reais do Unity (curva Sanchez-Cuevas D1–D4) | `unity/Assets/Ponte/RaiosAmbiente.cs`, `ponte_unity/` | **sim** — `RaycastCommand.ScheduleBatch` [S29] |
| 4 | Proxies `mocap` + `weld` de obstáculos | `onda4-mocap-proxies-weld` | Drone colide fisicamente com parede do Unity (deteção em `mj_step1`, forças em `mj_step2`); proxies seguem `ClosestPoint` | `ponte_unity/proxies.py`, MJCF runtime (MjSpec) | **sim** — `mocap`/`weld` [S17][S38] |
| 4 | Câmara FPV assíncrona | `onda4-fpv-async-readback` | Stream FPV do Unity para o site/`MiraBalisticaIA` sem bloquear GPU (< 2 ms de overhead) | `unity/Assets/Ponte/FpvReadback.cs` | **sim** — `AsyncGPUReadback` [S42] |
| 5 · Integração | HUD/telemetria (reaproveitar cockpit) | `onda5-hud-telemetria` | HUD mostra drone + acertos/erros em NPCs + bateria/motores (como `sim_site.py`, agora sobre o mundo Unity) | `unity/Assets/HUD/`, `ponte_unity/` | **não** |
| 5 | Cenários E2E determinísticos | `onda5-cenarios-e2e` | Cenário fechado: 10 disparos → 10 NPCs atingidos + recuo + efeito solo validados por asserção | `testes_ponte/e2e_*.py`, `unity/Assets/Tests/` | **não** |
| 5 | *Benchmark* de latência e *jitter* | `onda5-benchmark-latencia` | Relatório: p99 da ponte < 1 ms, *jitter* do laço 500 Hz < 1 %, ≥ 60 fps com 20 NPCs | `testes_ponte/bench_ponte.py` | **não** |

### 6.2 Grafo de dependências

```
onda0-contrato-ponte ─▶ onda1-schema-seqlock ─▶ onda1-identidade-planta ─┐
                        onda1-swizzle-referencial ───────────────────────┤
onda2-projeto-unity-urp ─▶ onda2-reader-shm-csharp ─▶ onda2-proxy-drone ┤
onda3-npc-hitboxes-ragdoll ─▶ onda3-balistica-segmentada ─▶ onda3-disparo-recuo ┤
onda4-raycasts-rotores-tof ─┐                                            ├─▶ onda5-*
onda4-mocap-proxies-weld ───┤ (dependem de onda2-proxy + onda1)          │
onda4-fpv-async-readback ───┘                                            ┘
```

### 6.3 Mapa de propriedade de ficheiros (dois sub-agentes nunca no mesmo ficheiro)

| Área | Dono único |
|---|---|
| `experiments/09_drone_hover_rl/UNITY_CONTRATO.md`, `ponte_unity/schema.py` | onda0 / onda1-schema (singleton) |
| `ponte_unity/*` (resto) | cada sub-tarefa da onda 1/3/4 na sua função |
| `unity/Packages/manifest.json`, `unity/ProjectSettings/*` | onda2-projeto-unity-urp (singleton) |
| `unity/Assets/Ponte/*` | sub-tarefas 2.2/2.3/4.1/4.3 por ficheiro próprio |
| `unity/Assets/{NPCs,Balistica,HUD,Tests}/*` | sub-tarefas 3.x/5.x por diretório próprio |
| `testes_ponte/*` | cada sub-tarefa escreve o(s) seu(s) ficheiro(s) de teste |

### 6.4 Portões e política de testes

- **Portão de integração** (roda em cada *merge*, no snapshot de integração):
  `GATE_BUILD` = `uv sync --frozen && uv run python -m compileall -q lab experiments/09_drone_hover_rl` ·
  `GATE_TEST` = `uv run pytest experiments/09_drone_hover_rl/testes_ponte -q` (a partir da onda 1; antes disso,
  `uv run python experiments/09_drone_hover_rl/teste_cockpit.py`) ·
  `GATE_LINT` = `uv run ruff check lab experiments/09_drone_hover_rl` (`ruff` entra como dev-dependency no PREP).
  Testes EditMode do Unity entram por `experiments/09_drone_hover_rl/unity/gate_unity.sh` (batchmode; **saltar com
  aviso** se a licença/Editor não estiver disponível — nunca travar o gate por ambiente).
- **Política de testes: full** — testes escritos ao fim de cada onda; sub-onda de Testing + sub-onda de Validation
  ao fim de cada onda (identidade da planta, testes de ponte, EditMode/PlayMode do Unity), correndo em paralelo
  com a onda seguinte e processadas antes do portão inter-onda.
- **Regra do laboratório respeitada:** tudo o que é físico do drone passa por `mj_step` — o override do Unity é
  sincronização de *renderização/ambiente* de um agente externo, nunca teleporte de estado físico.

## 7. Riscos e premissas

| Risco/premissa | Gravidade | Mitigação |
|---|---|---|
| Licença Unity: o preflight da suíte acusa «FALTA» (login no Hub por GUI não confirmado) | ALTO | Confirmar login no Hub → `unity-license.sh --status` **antes** da onda 2; sem Editor não há onda 2+ |
| Unity 6 × plugin `org.mujoco` (A2): compatibilidade da tag 3.15 com o Editor 6000.3 não testada | MÉDIO | A2 é opcional; A1 (proxy) não depende do plugin. Spike de 1 h na onda 2 para decidir |
| PhysX/NavMesh do Unity não são determinísticos entre execuções/máquinas | MÉDIO | *Ground truth* gravado por frame (nunca replay); cenários E2E com tolerâncias; determinismo exigido só ao drone |
| GC/alocações C# na ponte destruírem o laço 500 Hz | MÉDIO | Structs `unmanaged` + `unsafe`; teste de 10⁷ leituras + Profiler como critério de aceitação |
| `resource_tracker` do Python apagar o `/dev/shm` quando um processo termina | MÉDIO | `track=False` no consumidor ou `mmap` puro; teste de vida/morte de processos na onda 1 |
| `Collider.ClosestPoint` não suporta MeshCollider côncavo | BAIXO | *Spherecast* em lote para côncavos (§4.5) |
| Impulso físico do .380 em ragdoll é subtil (Δv 0,02–0,06 m/s) | BAIXO | Multiplicador estético separado e registado; física do drone nunca escalada |
| *Tunneling* mútuo (projétil e NPC ambos rápidos) | MÉDIO | Raio no espaço de velocidade relativa + subdivisão de segmento (§4.4) |
| Atualizações do Unity/plugins partirem o A2 | BAIXo | Versões fixadas (Editor 6000.3.22f1, tag do plugin); A1 imune |
| **NÃO VERIFICADA:** ganhos de desempenho da memória partilhada vêm de *benchmarks* técnicos de terceiros (níveis B/C), não de medição nesta máquina | — | O item 5.3 do ROADMAP mede localmente antes de qualquer promessa de latência |

## 8. Como verificar que funcionou (checklist de aceitação final)

1. `uv run python experiments/09_drone_hover_rl/run.py` → exit 0 (física do drone intacta, 319/319) e
   `bench_treino.py identidade` → bit-a-bit com a ponte ligada.
2. Ponte: round-trip pose→proxy→pose com erro < 1 mm / 0,1°; 10⁷ leituras *seqlock* sem corrupção; p99 < 1 ms.
3. Unity PlayMode: drone segue o MuJoCo; 20 NPCs a 60 fps; NPCs desviam-se do drone (`NavMeshObstacle`).
4. Balística: 10 disparos determinísticos a 2 m → 10 acertos em hitboxes distintas; ragdoll com impulso registado;
   `acertos_npc` no HUD; recuo no MuJoCo igual ao medido em `valida_real.py` (Δv = J/m, Δω_pitch = −z_cano·J/I_yy).
5. Ambiente: pairagem sobre telhado a 0,5 m reproduz a curva de efeito solo D1–D4; colisão contra parede do Unity
   resolvida por `mj_step2` (energia/reatação coerentes com `solref`/`solimp`).
6. FPV: stream a ≥ 30 fps sem bloquear o laço 500 Hz (jitter < 1 %).

## 9. Fora do escopo (deliberadamente)

- Substituir a física do drone pelo PhysX (proibido pela regra «simulador sempre físico» do laboratório).
- Física de NPCs/Mundo no MuJoCo (o mundo é do Unity, por decisão).
- Multi-jogador/rede, VR, produção comercial (licenças de assets/UI não avaliadas).
- Exportar a cidade inteira para MJCF (desnecessário na arquitetura A; proxies locais bastam).
- GTA V/RAGE/Unreal (avaliados no dossiê de 2026-10-14; este estudo é Unity).

## 10. Fontes-chave (detalhe e verificação adversarial no dossiê)

[S1] Documentação oficial Unity Plug-in (MuJoCo) · [S2] `MjScene.cs` (código oficial) · [S3] Discussion #2502
(`ManualStep` caseiro) · [S4] Issue #3180 (mesh decoder no Unity + URP «Lit») · [S5] Issue #3207 (regressão 3.6.0,
corrigida 3.7.0) · [S6] Issue #1637 (qpos externo + `MjGlobalSettings`) · [S9] Flightmare (arXiv 2009.00563) ·
[S10] URLab (arXiv 2504.14135) · [S11] AirSim (arXiv 1705.05065) · [S16] `MjEngineTool.cs` (swizzling) · [S17]
Documentação MuJoCo `mj_step1`/`mj_step2` + `mocap` · [S19–S21] `multiprocessing.shared_memory` ·
`MemoryMappedFile` Linux (dotnet/runtime #21863) · [S24–S26] *benchmarks* de IPC (níveis B/C) · [S28–S33]
Documentação Unity `Physics.Raycast`/`RaycastCommand`/`Rigidbody.isKinematic`/`AddForceAtPosition`/`ForceMode` ·
[S38] MuJoCo `mocap` + `weld` · [S42–S43] `AsyncGPUReadback`. Lista completa: dossiê §6.
