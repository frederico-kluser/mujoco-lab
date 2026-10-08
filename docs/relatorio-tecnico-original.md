<!--
  PROVENIÊNCIA: texto fornecido pelo utilizador (owner) em 2026-10-07, ao iniciar o laboratório MuJoCo.
  Conteúdo preservado; só a formatação Markdown foi restaurada (títulos, listas, tabelas, bloco de código).
  ATENÇÃO: é material de PARTIDA, não verdade verificada. A auditoria (correta/parcial/incorreta/desatualizada) vive em
  pesquisas/ (dossiê Tavily) e em .agents/mujoco-agent-skill/references/relatorio-auditoria.md. Não editar este ficheiro.
-->

# Relatório Técnico: Arquitetura, Configuração e Simulação Avançada de Dinâmica de Corpos Rígidos com MuJoCo

## 1. Introdução à Simulação Robótica Determinística

A simulação computacional de sistemas robóticos, veículos autónomos e corpos rígidos articulados exige um compromisso rigoroso entre a fidelidade física e a estabilidade numérica. No panorama tecnológico atual, o motor MuJoCo (Multi-Joint dynamics with Contact), suportado pela Google DeepMind, estabelece um paradigma de excelência. Desenvolvido especificamente para controlo ótimo, biomecânica e aprendizagem automática, a sua infraestrutura diverge fundamentalmente dos motores concebidos para a indústria de videojogos, ao priorizar a formulação de coordenadas generalizadas, o contacto analítico inversível e a elevada eficiência em cálculo diferencial. O presente relatório disseca a arquitetura matemática da plataforma, orquestra a configuração ambiental em sistemas Linux e macOS, explicita a expansão computacional para Unidades de Processamento Gráfico (GPU) via MJX e detalha a integração de telemetria avançada com ferramentas multimodais de observabilidade.

## 2. Compreensão Arquitetural da Plataforma

### 2.1 Coordenadas Generalizadas e Algoritmos de Featherstone

A esmagadora maioria dos simuladores físicos tradicionais (como o Unity com PhysX ou o Unreal Engine com Chaos) recorre a coordenadas maximizadas, representando cada corpo rígido no espaço tridimensional com seis graus de liberdade Cartesianos. Posteriormente, estes motores impõem restrições algébricas (joints) para forçar a união dos corpos. Sob regimes de simulação sujeitos a forças extremas, este método resulta frequentemente em instabilidade, originando a separação artificial das juntas.

O MuJoCo subverte esta abordagem adotando coordenadas generalizadas. Nesta formulação, as juntas não são restrições matemáticas a aplicar sobre corpos separados, mas sim os próprios graus de liberdade fundamentais que ditam o movimento relativo entre um "corpo-pai" e um "corpo-filho" numa árvore cinemática.

A dinâmica temporal contínua governa-se pela equação fundamental do movimento:

$$\tau = M(q)\dot{v} + c(q, v)$$

onde $q$ representa as posições no espaço das juntas, $v$ a velocidade correspondente, $\dot{v}$ a aceleração vetorial, $\tau$ o vetor das forças aplicadas (incluindo atuadores, aerodinâmica e passivas), $M(q)$ a matriz de inércia e $c(q, v)$ as forças de viés.

O cálculo destas matrizes tira partido de algoritmos otimizados desenvolvidos por Roy Featherstone. Para o cálculo exato do vetor de viés $c(q,v)$ — que agrega forças centrífugas, de Coriolis e forças gravitacionais — o MuJoCo utiliza o algoritmo de Newton-Euler Recursivo (RNE). A matriz de inércia do espaço de juntas $M(q)$ é gerada através do algoritmo de Corpo Rígido Composto (CRB). Devido à sua natureza de árvore cinemática, esta matriz é tipicamente esparsa. Para efetuar multiplicações vetoriais pelo inverso de $M(q)$ de forma ultrarrápida, o simulador computa uma fatorização rigorosa $L^T D L$ e resolve as expressões mediante retro-substituição esparsa.

### 2.2 Integradores Numéricos e Conservação Dinâmica

A evolução do estado no tempo é processada através de opções robustas de integração numérica que transacionam derivadas contínuas. A precisão e estabilidade destes integradores dependem do passo de tempo adotado ($dt$ ou $h$), que, se for demasiado elevado, induz explosão algébrica.

| Integrador | Característica Principal | Aplicação Recomendada |
| --- | --- | --- |
| Euler Semi-Implícito | Desempenho computacional máximo. | Simulações padrão em Aprendizagem por Reforço. |
| RK4 (Runge-Kutta 4) | Preserva rotações e rácio conservador de energia $(h\vert{}\omega\vert{})^2$. | Sistemas pendulares, biomecânica e robôs orbitais. |
| Implícito | Estabilidade incondicional. Trata rigidez extrema acoplando molas. | Simulações fluidodinâmicas ou de flexibilidade elástica maciça. |

### 2.3 Mecânica de Contacto Suave (Soft Contacts) vs. Motores LCP

Em motores de videojogos focados no aspeto visual, o contacto é tipicamente modelado sob a forma de um Problema de Complementaridade Linear (LCP). O LCP exige estrita complementaridade: a força e a velocidade de separação entre dois corpos não podem ser simultaneamente não-nulas. Esta premissa assume corpos infinitamente duros. Na robótica real, quando os pés de um droide impactam o solo ou quando um atuador agarra um objeto, os materiais sofrem deformação mecânica.

O MuJoCo descarta a complementaridade estrita e reformula o cálculo de colisões como um problema de otimização convexa, permitindo o relaxamento matemático através de "soft contacts" (contactos suaves). Esta arquitetura tolera interpenetrações subtis, nas quais o material empurra os corpos em direções opostas enquanto a força normal e a velocidade permanecem simultaneamente ativas. Esta divergência do padrão LCP mitiga a instabilidade estrutural, acelera as derivadas para algoritmos de machine learning e reflete fidedignamente o perfil dos materiais no design robótico.

A otimização matemática subjacente recorre a uma equação diferencial parametrizada pelas grandezas relativas de impedância do constrangimento ($d$), rigidez da resposta ($k$) e amortecimento associado ($b$):

$$a_1 + d \cdot (b v + k r) = (1 - d) \cdot a_0$$

As variáveis são ajustadas pelo projetista através de dois atributos primordiais nos modelos mecânicos: solref e solimp.

- **solimp**: Determina a impedância espacial do material variando entre limites estritos (d0 e d_width). Funciona como a camada macia do objeto.
- **solref**: Define a dinâmica temporal do contacto, formulada tipicamente como constante de tempo (timeconst) e rácio de amortecimento (dampratio).

### 2.4 Fricção e Geometria do Cone de Atrito

Para assegurar o impedimento de escorregamentos incorretos em manipuladores articulados, o simulador expande as forças friccionais baseando-se em cones elíticos ou piramidais, configuráveis globalmente. Para materiais industriais que rotacionam sobre si (pneus de carros ou esferas), o atributo dimensional condim na configuração da geometria é essencial.

| Valor condim | Fricção Calculada | Implicação Física |
| --- | --- | --- |
| 1 | Apenas Normal | Contacto sem atrito (ideal para partículas puras). |
| 3 | Tangencial (2 eixos) | O atrito de deslizamento linear padrão opõe-se ao vetor movimento. |
| 4 | Torsional (+1 eixo) | Bloqueia a rotação em torno da normal (ex: pneu de carro fixo no asfalto). |
| 6 | Rolamento (+2 eixos) | Adiciona o atrito de rolamento impedindo giro infinito de esferas ou cilindros. |

### 2.5 Arquitetura MJCF (MuJoCo Modeling XML)

Contrariamente ao formato URDF do ROS (que especifica hierarquias topológicas sem otimização direta de dados), o formato MJCF atua quase como um compilador para a memória da simulação, assegurando que geometrias e propriedades são convertidas em ponteiros puros.

Um ficheiro base subdivide-se nos seguintes nós de compilação:

- `<compiler>` e `<option>`: Definem o passo temporal, vetores gravíticos, viscosidade de fluidos e algoritmos do solver.
- `<worldbody>`: Raiz do ambiente e sistema cartesiano global.
- `<body/>`: Unidade orgânica de massa inercial.
- `<joint/>`: Acoplada ao corpo filho, instaura restrições como dobradiças (hinge) ou esferas (ball).
- `<geom/>`: Dissocia o aspeto (class="visual") da malha de interação e impacto (class="collision"). A inércia pode ser inferida a partir de um volume calculando por oposição à densidade nativa assumida pela água, caso não seja fornecida.
- `<tendon/>` e `<actuator/>`: Modelam a anatomia biomecânica de músculos através de leis FLV (Force-Length-Velocity) e atuadores elétricos operacionais mapeados a transmissões mecânicas de juntas.

## 3. Instalação e Configuração Específica do Ambiente Computacional

A orquestração do MuJoCo no nível de engenharia subjacente demanda ambientes devidamente capacitados para resolução gráfica assíncrona paralela e compilação híbrida nativa C/C++ vinculada com Python via pybind11.

### 3.1 Instalação Avançada em CachyOS (Baseado em Arch Linux)

O ecossistema Arch Linux modificado do CachyOS apresenta bibliotecas recompiladas para hardware suportando as extensões vectoriais de alta performance x86-64-v3, ideais para o cálculo de matrizes esparsas.

Na raiz deste sistema, exige-se a preparação de pacotes essenciais de integração do compilador nativo utilizando a arquitetura de ferramentas de pacote. O gestor oficial pacman e o utilitário AUR (Arch User Repository) processam as dependências, que integram sistemas cmake de estruturação e as bibliotecas gráficas glfw primárias para janelamento. O isolamento das dependências processa-se em ambiente Python virtual, obviando as históricas manipulações exaustivas de partições de bibliotecas no repositório LD_LIBRARY_PATH das antigas versões do MuJoCo.

Embora repositórios como o AUR ofereçam esquemas como python-mujoco empacotando os binários sistémicos, a prática de engenharia moderna encoraja o estabelecimento de um ambiente Python robusto:

1. Aferir a instalação de compiladores e suporte gráfico: As bibliotecas gcc-libs, glibc, e o sistema multi-tarefa ninja devem ser garantidos nativamente.
2. Criar uma virtual environment Python local.
3. Emitir a instalação de bibliotecas compiladas predefinidas: Executar o processo através da roda de Python (wheel) padrão acoplada à DeepMind. O processo é imediato chamando a interface Pypi que alberga não só os bindings, mas também as dependências C compiladas dinâmicas associadas.

Caso surja a necessidade estrita de escrever controladores híbridos C++ (como em nós de interface ros2_control), a formulação é executada no CMakeLists.txt procurando pelo módulo em `pkg_search_module(MUJOCO mujoco)` e interligando os binários compilados dinâmicos através da rotina imperativa `target_link_libraries(my_app PUBLIC mujoco::mujoco)`.

### 3.2 O Fluxo Correto e Restrições O.S. no macOS (Apple Silicon - M1/M2/M3)

Nos processadores baseados na topologia ARM da Apple, o sistema de instalação de componentes gráficos depende profundamente de gestão alternativa via Homebrew para fornecimento da biblioteca basilar Open Graphics Library. Todavia, a barreira técnica manifesta-se essencialmente na arquitetura de visualização que impõe restrições profundas na thread ativa.

O sistema macOS proíbe expressamente operações do OpenGL ou solicitações de janelas GLFW de decorrerem fora da cadeia lógica e gráfica principal, denominada main thread. Na simulação robótica Python, em que o engenheiro tipicamente insta a matemática densa e submete uma diretriz como `viewer.launch_passive()`, lançando assim um buffer em background, o macOS reage emitindo uma interrupção fatal (SegFault) originada no compositor de janelas do SO.

Para contornar esta formidável limitação técnica, a framework oferece o pacote utilitário integrado mjpython. O fluxo de uso difere assim do convencional:

1. Proceder à instalação formal: Utilizar a chamada `pip install mujoco`.
2. Assegurar as bibliotecas complementares via Homebrew (instalação paralela de GLFW).
3. Invocar os ficheiros de simulação não com o binário python, mas através da macro `mjpython simulacao.py`. O sub-comando atua como barreira delegadora, forçando as representações passivas no fio de processamento central, permitindo que algoritmos complexos iterem o ambiente vetorial noutras frações da CPU.

## 4. Programação Vetorial, Expansão e Controlo Numérico

A transição dos alicerces computacionais da teoria física à manipulação da matriz na memória volátil requer clareza na interface da framework, a qual rejeita profundamente o paradigma clássico de Objetos em função do puro paralelismo empacotado.

### 4.1 Arquitetura da Memória: MjModel e MjData

Para obter desempenho ótimo na linguagem Python sob a biblioteca de ponteiros gerados por pybind11, o simulador recusa a desfragmentação associada a arrays aninhados. Em vez disso, aloca grandes blocos contíguos representados pelas estruturas fundamentais `mujoco.MjModel` e `mujoco.MjData`.

O `MjModel` consubstancia o plano estático irredutível da simulação, encapsulando geometrias, referências quaterniônicas, hierarquia inercial e restrições. Ele retém parâmetros constantes após conversão abstrata de MJCF.

O `MjData` acolhe a evolução temporal da estrutura analítica contendo os vetores transitórios do momento. Engloba posições generalizadas (`data.qpos`), velocidades (`data.qvel`), forças aceleradoras resolvidas (`data.qacc`), os dados empíricos de telemetria base dos sensores (`data.sensordata`) e o vetor de manipulação cinemática pelo atuador mecânico subjacente (`data.ctrl`).

Uma manipulação perigosa (mas corriqueira) envolve a injeção estrita nos slices de Numpy. Como os campos vetoriais de MjData mapeiam posições brutas em C, uma alteração assíncrona feita sem cópias em Python através de referências sobrepõe os valores iterados, originando resultados físicos viciados. A obtenção e injeção requere a exploração segura da macro.

### 4.2 Lógica do Controlo (Script Base)

Para ilustrar o ciclo de injeção de força sobre peças em tempo real, desenvolve-se um excerto programático que carrega a malha estrutural através da VFS (Virtual File System) interna, avalia atuadores e aplica um torque variável ao motor.

```python
import time
import numpy as np
import mujoco
import mujoco.viewer

# Especificação MJCF para uma base com haste rotacional articulada
mjcf_xml = """
<mujoco>
    <option timestep="0.005" gravity="0 0 -9.81"/>
    <worldbody>
        <light pos="0 1 1" dir="0 -1 -1" diffuse="1 1 1"/>
        <geom type="plane" size="3 3 0.1" rgba="0.9 0.9 0.9 1"/>
        <body name="base_robotica" pos="0 0 0.5">
            <geom type="box" size="0.2 0.2 0.2" rgba="0.3 0.3 0.3 1"/>
            <body name="haste_articulada" pos="0 0.2 0">
                <joint name="junta_motor" type="hinge" axis="0 1 0"/>
                <geom type="cylinder" size="0.05 0.4" pos="0 0 0.4" rgba="0.8 0.2 0.2 1"/>
            </body>
        </body>
    </worldbody>
    <actuator>
        <motor name="atuador_principal" joint="junta_motor" gear="1.0"/>
    </actuator>
</mujoco>
"""

def simular_dinamica():
    # Inicialização estática do MuJoCo Model a partir de string
    modelo = mujoco.MjModel.from_xml_string(mjcf_xml)
    # Alocação estruturada das variáveis no tempo e matriz vetorial
    dados = mujoco.MjData(modelo)
    
    # Identificação nativa da ID do motor pretendido para injeção de tensores
    id_motor = mujoco.mj_name2id(modelo, mujoco.mjtObj.mjOBJ_ACTUATOR, "atuador_principal")

    # Orquestração do visualizador passivo (No macOS utilizar mjpython)
    with mujoco.viewer.launch_passive(modelo, dados) as viewer:
        while viewer.is_running():
            inicio_ciclo = time.time()
            
            # Dinâmica do Controlo Numérico: Torque senoidal (N.m) 
            torque = 15.0 * np.sin(dados.time * 2.0 * np.pi)
            dados.ctrl[id_motor] = torque
            
            # Submissão à Forward Dynamics: Integrando física e resoluções convexas
            mujoco.mj_step(modelo, dados)
            
            # Sincronização explícita entre buffers lógicos e renderização da GUI
            viewer.sync()
            
            # Mitigação para adequação da aceleração ao Real-Time (opcional na indústria)
            tempo_decorrido = time.time() - inicio_ciclo
            tempo_espera = modelo.opt.timestep - tempo_decorrido
            if tempo_espera > 0:
                time.sleep(tempo_espera)

if __name__ == "__main__":
    simular_dinamica()
```

O método base orquestra a injeção linear utilizando comandos como `mj_step` que invocam internamente a integração de dados `mj_forward` garantindo a tradução de torques em acelerações $\dot{v}$. Uma característica avançada envolve injetar controladores através da interceptação por Callbacks (como `mjcb_control` e `mjcb_sensor`). Estas funções, expostas pela API em C, podem receber funções de Python; contudo, a utilização massiva destas interrupções induz chamadas repetitivas ao Global Interpreter Lock (GIL) do Python durante as quatro derivações do integrador RK4 num único `mj_step`, paralisando consideravelmente o solver. Como mitigação de excelência para indústrias pesadas, o engenheiro deve recorrer a extensões partilhadas (ctypes) encapsulando blocos híbridos C.

### 4.3 Expansão Extrema via MuJoCo XLA (MJX) e Arquitetura GPU

Na topologia de formulações robustas impulsionadas pelo aprendizado automático (onde 4096 carros robóticos requerem exploração iterativa sob matrizes independentes), a versão sequencial do núcleo C (que atinge o estrangulamento latente da infraestrutura CPU multithreaded clássica exposta no módulo `mujoco.rollout`) cessa de escalar perante as ordens logarítmicas de paralelismo das Unidades GPU ou TPU Google.

A evolução profunda consolidou-se através do MuJoCo XLA (MJX), uma reimplementação do motor matricial construída totalmente na linguagem computacional do ecossistema Google JAX. O JAX compila as instruções de álgebra linear (XLA) gerando núcleos paralelizados eficientíssimos processados diretamente sobre tensores massivos de GPU. O MJX reproduz o espetro determinístico mantendo as estruturas `mjx.Model` e `mjx.Data`, cujas memórias são transplantadas do hospedeiro para o dispositivo VRAM ativando dimensões "batch" (batched environments) simultâneas de extrema escala.

Nesta infraestrutura paralela, a integração de simulações com o mesmo robô, mas configurações topológicas mutáveis de inércia ou geometria (Domain Randomization), requer o envio pela orquestração `mjx.put_model` e `mjx.make_data` para alocação de registadores.

Para maximizar os constrangimentos LCP redefinidos, a equipa implementou o motor subjacente MJX-Warp, que otimiza de forma espetacular operações tensoriais em chips CUDA dedicados da NVIDIA sacrificando diferenciações analíticas mas incrementando massivamente o "Steps Per Second" (SPS).

| Contexto / Pipeline | Desempenho (SPS) Humanoid | Natureza Física e Limitante do Escalonamento |
| --- | --- | --- |
| MuJoCo (CPU Base) | Otimizado para latência. | Desenhado para Teleoperação e MPC em tempo real. Estrangula no paralelismo de 4k instâncias. |
| MJX (JAX) | 2.33 Milhões SPS | Orientado à GPU. Ligeiras variações nos algoritmos de contacto convexo esparso de XLA para evitar dispersão de ramificações na VRAM. |
| MJWarp (CUDA/NVIDIA) | 2.96 Milhões SPS | Focado na pura taxa de transferência sem recaptura gráfica forçada e suportado por blocos Cholesky altamente agressivos sem fator diferencial. |

## 5. Integração com Rerun.io: Extração Aerodinâmica e Telemetria de Atrito

Para visualizações e diagnósticos multidimensionais, o ecrã nativo torna-se obsoleto, especialmente em simulações que exigem vetores isolados aerodinâmicos, mapeamentos compressivos, lidar volumétrico espelhado ou dinâmicas temporais fluídicas iteradas noutro local ou na nuvem. A ferramenta de escolha primordial no panorama de vanguarda assenta no Rerun.io, um data logger construído sobre arquitetura vetorial orientada em coluna (column-oriented) escrita em Rust que engloba suporte imediato em Python.

### 5.1 O Modelo Aerodinâmico e Viscosidade no MuJoCo

A simulação complexa de drones ou geometrias aladas integra de forma transparente leis fluidodinâmicas se a estrutura MJCF incorporar parâmetros nas tags globais e de contacto da geometria. Se parametrizada como `fluidshape="ellipsoid"`, a matriz desativa os cálculos esféricos básicos orientados pela inércia e institui uma generalização do fluxo aerodinâmico em 3 dimensões para cada objeto (utilizando parâmetros derivados do Teorema de Kutta-Joukowski e do efeito Magnus rotacional).

Os atributos de arrasto fluidodinâmico modelados pelo vetor `fluidcoef` estipulam forças restritivas:

| Coeficiente Fluidodinâmico | Representação e Física Subjacente | Padrão MJCF |
| --- | --- | --- |
| Arrasto Franco (Blunt Drag) | Resistência da barreira cruzada frontal linear ao fluxo ($C_{D, \text{blunt}}$). | 0.5 |
| Arrasto Esbelto (Slender Drag) | Resistência colinear no eixo esguio primário do cilindro ($C_{D, \text{slender}}$). | 0.25 |
| Arrasto Angular | Força oposta gerada ao rotacionar os elipsoides no fluido denso. | 1.5 |
| Sustentação Kutta (Kutta Lift) | Resultante perpendicular traduzida pela circulação não simétrica perante fluxo denso ($C_K$). | 1.0 |
| Efeito Magnus | Rotação acoplada induzindo refração de ar e elevação ($C_M$). | 1.0 |

Os fatores aerodinâmicos combinam-se ainda com a configuração density, viscosity e correntes de wind configuradas na aba `<option>`. Como consequência destas simulações, que implicam resistência viscosa ao longo do trajeto, a energia atenua fortemente os objetos voadores submetendo-os às derivadas numéricas resultantes da oposição ao ar.

### 5.2 Orquestração Numérica Visual via Arquétipos e Logs

No Rerun, em vez do ambiente gráfico ler a simulação, é o script central que escreve e exporta as coordenadas de `rr.log` a cada transição da árvore semântica (ECS), mapeadas em grupos lógicos como "drone/aerodinamica". O sistema utiliza construtores semânticos classificados como Archetypes, agrupando dados espaciais (nuvens `rr.Points3D` ou eixos `rr.Arrows3D`).

Para visualizar o desgaste do atrito linear elítico ou o ponto fulcral aerodinâmico em 3D, deve extrair-se os componentes das matrizes originais em tempo real:

- **Colisões**: Através da matriz iterativa residente em `data.contact`, a estrutura expõe o número transitório local (`ncon`). Requisitando a API matemática C de `mujoco.mj_contactForce(model, data, index, force_array)`, extrai-se a tradução convexa LCP aplicada ao bloco tridimensional e desenha-se um vetor exato de resistência no referencial do mundo visual.
- **Forças Acumuladas**: O cálculo aerodinâmico (ou gravítico compensatório) é injetado ciclicamente nas reações passivas e globais alocadas a `data.qfrc_passive` e `data.qfrc_applied` antes de `mj_step` terminar.

## 6. Pipeline de Documentação e Otimização URDF Direta (urdf2mjcf)

O repositório principal do motor físico, atualizado exaustivamente sob a égide computacional da Google DeepMind (albergado publicamente em github.com/google-deepmind/mujoco), inclui o guia matricial "Computation", que relata equações, bem como a documentação extensiva do dialeto MJCF em "XML Reference" para consulta exaustiva dos nós estruturais integrados da biblioteca base. Contudo, no percurso desde o desenho CAD industrial até ao bloco XML orgânico final, persiste a lacuna topológica imposta pelo domínio pré-existente universal baseado no formato semântico robótico puro e imperfeito: URDF.

O URDF é intrinsecamente limitado nas primitivas mecânicas de controlo e colisão vetorial exigidas para dinâmicas de contacto complexas (carecendo totalmente dos ajustes de soft contact descritos anteriormente). A fim de transpor os robôs, manipuladores 6-DoF complexos ou viaturas provindas deste esquema para o MJCF puramente vetorial, a comunidade de robótica avançada confia irredutivelmente na ferramenta modular urdf2mjcf suportada publicamente nos projetos da incubadora K-Scale Labs.

### Resolução Algorítmica e Decomposição Convexa (CoACD)

A utilidade do módulo, instalável globalmente por infraestrutura pip (`pip install urdf2mjcf`), suplanta simples conversões topológicas através das suas reestruturações inerciais. Durante o mapeamento a partir da linha de comando com `urdf2mjcf robot.urdf --output robot.mjcf`, o conversor examina assimetrias indesejáveis nos componentes da diagonal da inércia vetorial impostos inadequadamente no passado por software generativo, procedendo ao seu nivelamento algébrico, prevenindo acelerações instáveis. Mais do que a translação exata de eixos revolutos e prismáticos para juntas hinge e slide de MuJoCo, o algoritmo separa formalmente as malhas importadas que servem para cálculo colisional (classificadas intrinsecamente sob class="collision") daquelas que apenas renderizam visualmente e de modo inofensivo a textura final (class="visual").

Para cálculos da malha esparsa (narrow-phase) colisional nas matrizes convexas, a utilização de geometria intrincada importada por URDF (ficheiros .obj completos com arestas reentrantes) consome extrema carga computacional com forte instabilidade associada a polígonos côncavos falsos. O script resolve a disfuncionalidade implementando a orquestração Decomposição Convexa (CoACD) sobre componentes assinalados, fundindo e subdividindo as curvaturas de um veículo ou braço articulado em múltiplas geometrias primitivas subjacentes estritamente convexas aglomeradas indissoluvelmente (atribuídas como peças lógicas no atributo class="decomposed_collision" e tingidas cromativamente com as paletas inerentes do visualizador). Este protocolo converte peças complexas não determinísticas num espetro algébrico computacionalmente limpo, isento de pontos interpenetrantes fantasma, assegurando o balanço matemático crítico que consagra o motor físico na fronteira da evolução mecatrónica cibernética contemporânea.
