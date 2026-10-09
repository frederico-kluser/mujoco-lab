# **Relatório Técnico: Arquitetura, Configuração e Simulação Avançada de Dinâmica de Corpos Rígidos com MuJoCo**

## **1\. Introdução à Simulação Robótica Determinística**

A simulação computacional de sistemas robóticos, veículos autónomos e corpos rígidos articulados exige um compromisso rigoroso entre a fidelidade física e a estabilidade numérica. No panorama tecnológico atual, o motor MuJoCo (Multi-Joint dynamics with Contact), suportado pela Google DeepMind, estabelece um paradigma de excelência1. Desenvolvido especificamente para controlo ótimo, biomecânica e aprendizagem automática, a sua infraestrutura diverge fundamentalmente dos motores concebidos para a indústria de videojogos, ao priorizar a formulação de coordenadas generalizadas, o contacto analítico inversível e a elevada eficiência em cálculo diferencial2. O presente relatório disseca a arquitetura matemática da plataforma, orquestra a configuração ambiental em sistemas Linux e macOS, explicita a expansão computacional para Unidades de Processamento Gráfico (GPU) via MJX e detalha a integração de telemetria avançada com ferramentas multimodais de observabilidade.

## **2\. Compreensão Arquitetural da Plataforma**

### **2.1 Coordenadas Generalizadas e Algoritmos de Featherstone**

A esmagadora maioria dos simuladores físicos tradicionais (como o Unity com PhysX ou o Unreal Engine com Chaos) recorre a coordenadas maximizadas, representando cada corpo rígido no espaço tridimensional com seis graus de liberdade Cartesianos. Posteriormente, estes motores impõem restrições algébricas (joints) para forçar a união dos corpos2. Sob regimes de simulação sujeitos a forças extremas, este método resulta frequentemente em instabilidade, originando a separação artificial das juntas.  
O MuJoCo subverte esta abordagem adotando coordenadas generalizadas2. Nesta formulação, as juntas não são restrições matemáticas a aplicar sobre corpos separados, mas sim os próprios graus de liberdade fundamentais que ditam o movimento relativo entre um "corpo-pai" e um "corpo-filho" numa árvore cinemática2.  
A dinâmica temporal contínua governa-se pela equação fundamental do movimento:  
![][image1]  
onde ![][image2] representa as posições no espaço das juntas, ![][image3] a velocidade correspondente, ![][image4] a aceleração vetorial, ![][image5] o vetor das forças aplicadas (incluindo atuadores, aerodinâmica e passivas), ![][image6] a matriz de inércia e ![][image7] as forças de viés2.  
O cálculo destas matrizes tira partido de algoritmos otimizados desenvolvidos por Roy Featherstone. Para o cálculo exato do vetor de viés ![][image7] — que agrega forças centrífugas, de Coriolis e forças gravitacionais — o MuJoCo utiliza o algoritmo de Newton-Euler Recursivo (RNE)2. A matriz de inércia do espaço de juntas ![][image6] é gerada através do algoritmo de Corpo Rígido Composto (CRB). Devido à sua natureza de árvore cinemática, esta matriz é tipicamente esparsa. Para efetuar multiplicações vetoriais pelo inverso de ![][image6] de forma ultrarrápida, o simulador computa uma fatorização rigorosa ![][image8] e resolve as expressões mediante retro-substituição esparsa2.

### **2.2 Integradores Numéricos e Conservação Dinâmica**

A evolução do estado no tempo é processada através de opções robustas de integração numérica que transacionam derivadas contínuas. A precisão e estabilidade destes integradores dependem do passo de tempo adotado (![][image9] ou ![][image10]), que, se for demasiado elevado, induz explosão algébrica2.

| Integrador | Característica Principal | Aplicação Recomendada |
| :---- | :---- | :---- |
| **Euler Semi-Implícito** | Desempenho computacional máximo. | Simulações padrão em Aprendizagem por Reforço. |
| **RK4 (Runge-Kutta 4\)** | Preserva rotações e rácio conservador de energia ![][image11]. | Sistemas pendulares, biomecânica e robôs orbitais2. |
| **Implícito** | Estabilidade incondicional. Trata rigidez extrema acoplando molas. | Simulações fluidodinâmicas ou de flexibilidade elástica maciça5. |

### **2.3 Mecânica de Contacto Suave (Soft Contacts) vs. Motores LCP**

Em motores de videojogos focados no aspeto visual, o contacto é tipicamente modelado sob a forma de um Problema de Complementaridade Linear (LCP)1. O LCP exige estrita complementaridade: a força e a velocidade de separação entre dois corpos não podem ser simultaneamente não-nulas. Esta premissa assume corpos infinitamente duros. Na robótica real, quando os pés de um droide impactam o solo ou quando um atuador agarra um objeto, os materiais sofrem deformação mecânica.  
O MuJoCo descarta a complementaridade estrita e reformula o cálculo de colisões como um problema de otimização convexa, permitindo o relaxamento matemático através de "soft contacts" (contactos suaves)1. Esta arquitetura tolera interpenetrações subtis, nas quais o material empurra os corpos em direções opostas enquanto a força normal e a velocidade permanecem simultaneamente ativas. Esta divergência do padrão LCP mitiga a instabilidade estrutural, acelera as derivadas para algoritmos de machine learning e reflete fidedignamente o perfil dos materiais no design robótico1.  
A otimização matemática subjacente recorre a uma equação diferencial parametrizada pelas grandezas relativas de impedância do constrangimento (![][image12]), rigidez da resposta (![][image13]) e amortecimento associado (![][image14])9:  
![][image15]  
As variáveis são ajustadas pelo projetista através de dois atributos primordiais nos modelos mecânicos: solref e solimp.

* **solimp**: Determina a impedância espacial do material variando entre limites estritos (d0 e d\_width). Funciona como a camada macia do objeto.  
* **solref**: Define a dinâmica temporal do contacto, formulada tipicamente como constante de tempo (timeconst) e rácio de amortecimento (dampratio)9.

### **2.4 Fricção e Geometria do Cone de Atrito**

Para assegurar o impedimento de escorregamentos incorretos em manipuladores articulados, o simulador expande as forças friccionais baseando-se em cones elíticos ou piramidais, configuráveis globalmente10. Para materiais industriais que rotacionam sobre si (pneus de carros ou esferas), o atributo dimensional condim na configuração da geometria é essencial12.

| Valor condim | Fricção Calculada | Implicação Física |
| :---- | :---- | :---- |
| **1** | Apenas Normal | Contacto sem atrito (ideal para partículas puras). |
| **3** | Tangencial (2 eixos) | O atrito de deslizamento linear padrão opõe-se ao vetor movimento. |
| **4** | Torsional (+1 eixo) | Bloqueia a rotação em torno da normal (ex: pneu de carro fixo no asfalto)9. |
| **6** | Rolamento (+2 eixos) | Adiciona o atrito de rolamento impedindo giro infinito de esferas ou cilindros9. |

### **2.5 Arquitetura MJCF (MuJoCo Modeling XML)**

Contrariamente ao formato URDF do ROS (que especifica hierarquias topológicas sem otimização direta de dados), o formato MJCF atua quase como um compilador para a memória da simulação, assegurando que geometrias e propriedades são convertidas em ponteiros puros13.  
Um ficheiro base subdivide-se nos seguintes nós de compilação:

* \<compiler\> e \<option\>: Definem o passo temporal, vetores gravíticos, viscosidade de fluidos e algoritmos do solver14.  
* \<worldbody\>: Raiz do ambiente e sistema cartesiano global.  
* \<body/\>: Unidade orgânica de massa inercial15.  
* \<joint/\>: Acoplada ao corpo filho, instaura restrições como dobradiças (hinge) ou esferas (ball)15.  
* \<geom/\>: Dissocia o aspeto (class="visual") da malha de interação e impacto (class="collision"). A inércia pode ser inferida a partir de um volume calculando por oposição à densidade nativa assumida pela água, caso não seja fornecida15.  
* \<tendon/\> e \<actuator/\>: Modelam a anatomia biomecânica de músculos através de leis FLV (Force-Length-Velocity) e atuadores elétricos operacionais mapeados a transmissões mecânicas de juntas9.

## **3\. Instalação e Configuração Específica do Ambiente Computacional**

A orquestração do MuJoCo no nível de engenharia subjacente demanda ambientes devidamente capacitados para resolução gráfica assíncrona paralela e compilação híbrida nativa C/C++ vinculada com Python via pybind1117.

### **3.1 Instalação Avançada em CachyOS (Baseado em Arch Linux)**

O ecossistema Arch Linux modificado do CachyOS apresenta bibliotecas recompiladas para hardware suportando as extensões vectoriais de alta performance x86-64-v3, ideais para o cálculo de matrizes esparsas18.  
Na raiz deste sistema, exige-se a preparação de pacotes essenciais de integração do compilador nativo utilizando a arquitetura de ferramentas de pacote. O gestor oficial pacman e o utilitário AUR (Arch User Repository) processam as dependências, que integram sistemas cmake de estruturação e as bibliotecas gráficas glfw primárias para janelamento. O isolamento das dependências processa-se em ambiente Python virtual, obviando as históricas manipulações exaustivas de partições de bibliotecas no repositório LD\_LIBRARY\_PATH das antigas versões do MuJoCo4.  
Embora repositórios como o AUR ofereçam esquemas como python-mujoco empacotando os binários sistémicos, a prática de engenharia moderna encoraja o estabelecimento de um ambiente Python robusto19:

> 1. Aferir a instalação de compiladores e suporte gráfico: As bibliotecas gcc-libs, glibc, e o sistema multi-tarefa ninja devem ser garantidos nativamente20.  
> 2. Criar uma *virtual environment* Python local.  
> 3. Emitir a instalação de bibliotecas compiladas predefinidas: Executar o processo através da roda de Python (wheel) padrão acoplada à DeepMind. O processo é imediato chamando a interface Pypi que alberga não só os *bindings*, mas também as dependências C compiladas dinâmicas associadas17.  
> 4. Caso surja a necessidade estrita de escrever controladores híbridos C++ (como em nós de interface ros2\_control), a formulação é executada no CMakeLists.txt procurando pelo módulo em pkg\_search\_module(MUJOCO mujoco) e interligando os binários compilados dinâmicos através da rotina imperativa target\_link\_libraries(my\_app PUBLIC mujoco::mujoco)21.

### **3.2 O Fluxo Correto e Restrições O.S. no macOS (Apple Silicon \- M1/M2/M3)**

Nos processadores baseados na topologia ARM da Apple, o sistema de instalação de componentes gráficos depende profundamente de gestão alternativa via Homebrew para fornecimento da biblioteca basilar Open Graphics Library. Todavia, a barreira técnica manifesta-se essencialmente na arquitetura de visualização que impõe restrições profundas na *thread* ativa17.  
O sistema macOS proíbe expressamente operações do OpenGL ou solicitações de janelas GLFW de decorrerem fora da cadeia lógica e gráfica principal, denominada *main thread*17. Na simulação robótica Python, em que o engenheiro tipicamente insta a matemática densa e submete uma diretriz como viewer.launch\_passive(), lançando assim um *buffer* em *background*, o macOS reage emitindo uma interrupção fatal (SegFault) originada no compositor de janelas do SO.  
Para contornar esta formidável limitação técnica, a framework oferece o pacote utilitário integrado mjpython17. O fluxo de uso difere assim do convencional:

> 1. Proceder à instalação formal: Utilizar a chamada pip install mujoco.  
> 2. Assegurar as bibliotecas complementares via Homebrew (instalação paralela de GLFW).  
> 3. Invocar os ficheiros de simulação não com o binário python, mas através da macro mjpython simulacao.py17. O sub-comando atua como barreira delegadora, forçando as representações passivas no fio de processamento central, permitindo que algoritmos complexos iterem o ambiente vetorial noutras frações da CPU24.

## **4\. Programação Vetorial, Expansão e Controlo Numérico**

A transição dos alicerces computacionais da teoria física à manipulação da matriz na memória volátil requer clareza na interface da framework, a qual rejeita profundamente o paradigma clássico de Objetos em função do puro paralelismo empacotado.

### **4.1 Arquitetura da Memória: MjModel e MjData**

Para obter desempenho ótimo na linguagem Python sob a biblioteca de ponteiros gerados por pybind11, o simulador recusa a desfragmentação associada a arrays aninhados. Em vez disso, aloca grandes blocos contíguos representados pelas estruturas fundamentais mujoco.MjModel e mujoco.MjData13.  
O MjModel consubstancia o plano estático irredutível da simulação, encapsulando geometrias, referências quaterniônicas, hierarquia inercial e restrições. Ele retém parâmetros constantes após conversão abstrata de MJCF. O MjData acolhe a evolução temporal da estrutura analítica contendo os vetores transitórios do momento. Engloba posições generalizadas (data.qpos), velocidades (data.qvel), forças aceleradoras resolvidas (data.qacc), os dados empíricos de telemetria base dos sensores (data.sensordata) e o vetor de manipulação cinemática pelo atuador mecânico subjacente (data.ctrl)13.  
Uma manipulação perigosa (mas corriqueira) envolve a injeção estrita nos slices de Numpy. Como os campos vetoriais de MjData mapeiam posições brutas em C, uma alteração assíncrona feita sem cópias em Python através de referências sobrepõe os valores iterados, originando resultados físicos viciados. A obtenção e injeção requere a exploração segura da macro17.

### **4.2 Lógica do Controlo (Script Base)**

Para ilustrar o ciclo de injeção de força sobre peças em tempo real, desenvolve-se um excerto programático que carrega a malha estrutural através da VFS (Virtual File System) interna, avalia atuadores e aplica um torque variável ao motor.

Python  
import time  
import numpy as np  
import mujoco  
import mujoco.viewer

\# Especificação MJCF para uma base com haste rotacional articulada  
mjcf\_xml \= """  
\<mujoco\>  
    \<option timestep="0.005" gravity="0 0 \-9.81"/\>  
    \<worldbody\>  
        \<light pos="0 1 1" dir="0 \-1 \-1" diffuse="1 1 1"/\>  
        \<geom type="plane" size="3 3 0.1" rgba="0.9 0.9 0.9 1"/\>  
        \<body name="base\_robotica" pos="0 0 0.5"\>  
            \<geom type="box" size="0.2 0.2 0.2" rgba="0.3 0.3 0.3 1"/\>  
            \<body name="haste\_articulada" pos="0 0.2 0"\>  
                \<joint name="junta\_motor" type="hinge" axis="0 1 0"/\>  
                \<geom type="cylinder" size="0.05 0.4" pos="0 0 0.4" rgba="0.8 0.2 0.2 1"/\>  
            \</body\>  
        \</body\>  
    \</worldbody\>  
    \<actuator\>  
        \<motor name="atuador\_principal" joint="junta\_motor" gear="1.0"/\>  
    \</actuator\>  
\</mujoco\>  
"""

def simular\_dinamica():  
    \# Inicialização estática do MuJoCo Model a partir de string  
    modelo \= mujoco.MjModel.from\_xml\_string(mjcf\_xml)  
    \# Alocação estruturada das variáveis no tempo e matriz vetorial  
    dados \= mujoco.MjData(modelo)  
      
    \# Identificação nativa da ID do motor pretendido para injeção de tensores  
    id\_motor \= mujoco.mj\_name2id(modelo, mujoco.mjtObj.mjOBJ\_ACTUATOR, "atuador\_principal")

    \# Orquestração do visualizador passivo (No macOS utilizar mjpython)  
    with mujoco.viewer.launch\_passive(modelo, dados) as viewer:  
        while viewer.is\_running():  
            inicio\_ciclo \= time.time()  
              
            \# Dinâmica do Controlo Numérico: Torque senoidal (N.m)   
            torque \= 15.0 \* np.sin(dados.time \* 2.0 \* np.pi)  
            dados.ctrl\[id\_motor\] \= torque  
              
            \# Submissão à Forward Dynamics: Integrando física e resoluções convexas  
            mujoco.mj\_step(modelo, dados)  
              
            \# Sincronização explícita entre buffers lógicos e renderização da GUI  
            viewer.sync()  
              
            \# Mitigação para adequação da aceleração ao Real-Time (opcional na indústria)  
            tempo\_decorrido \= time.time() \- inicio\_ciclo  
            tempo\_espera \= modelo.opt.timestep \- tempo\_decorrido  
            if tempo\_espera \> 0:  
                time.sleep(tempo\_espera)

if \_\_name\_\_ \== "\_\_main\_\_":  
    simular\_dinamica()

O método base orquestra a injeção linear utilizando comandos como mj\_step que invocam internamente a integração de dados mj\_forward garantindo a tradução de torques em acelerações ![][image4]17. Uma característica avançada envolve injetar controladores através da interceptação por *Callbacks* (como mjcb\_control e mjcb\_sensor). Estas funções, expostas pela API em C, podem receber funções de Python; contudo, a utilização massiva destas interrupções induz chamadas repetitivas ao *Global Interpreter Lock* (GIL) do Python durante as quatro derivações do integrador RK4 num único mj\_step, paralisando consideravelmente o solver. Como mitigação de excelência para indústrias pesadas, o engenheiro deve recorrer a extensões partilhadas (ctypes) encapsulando blocos híbridos C17.

### **4.3 Expansão Extrema via MuJoCo XLA (MJX) e Arquitetura GPU**

Na topologia de formulações robustas impulsionadas pelo aprendizado automático (onde 4096 carros robóticos requerem exploração iterativa sob matrizes independentes), a versão sequencial do núcleo C (que atinge o estrangulamento latente da infraestrutura CPU multithreaded clássica exposta no módulo mujoco.rollout) cessa de escalar perante as ordens logarítmicas de paralelismo das Unidades GPU ou TPU Google29.  
A evolução profunda consolidou-se através do *MuJoCo XLA* (MJX), uma reimplementação do motor matricial construída totalmente na linguagem computacional do ecossistema Google JAX. O JAX compila as instruções de álgebra linear (XLA) gerando núcleos paralelizados eficientíssimos processados diretamente sobre tensores massivos de GPU32. O MJX reproduz o espetro determinístico mantendo as estruturas mjx.Model e mjx.Data, cujas memórias são transplantadas do hospedeiro para o dispositivo VRAM ativando dimensões "batch" (*batched environments*) simultâneas de extrema escala29.  
Nesta infraestrutura paralela, a integração de simulações com o mesmo robô, mas configurações topológicas mutáveis de inércia ou geometria (Domain Randomization), requer o envio pela orquestração mjx.put\_model e mjx.make\_data para alocação de registadores29. Para maximizar os constrangimentos LCP redefinidos, a equipa implementou o motor subjacente MJX-Warp, que otimiza de forma espetacular operações tensoriais em chips CUDA dedicados da NVIDIA sacrificando diferenciações analíticas mas incrementando massivamente o "Steps Per Second" (SPS)29.

| Contexto / Pipeline | Desempenho (SPS) Humanoid | Natureza Física e Limitante do Escalonamento |
| :---- | :---- | :---- |
| **MuJoCo (CPU Base)** | Otimizado para latência. | Desenhado para Teleoperação e MPC em tempo real. Estrangula no paralelismo de 4k instâncias. |
| **MJX (JAX)** | 2.33 Milhões SPS | Orientado à GPU. Ligeiras variações nos algoritmos de contacto convexo esparso de XLA para evitar dispersão de ramificações na VRAM29. |
| **MJWarp (CUDA/NVIDIA)** | 2.96 Milhões SPS | Focado na pura taxa de transferência sem recaptura gráfica forçada e suportado por blocos Cholesky altamente agressivos sem fator diferencial29. |

## **5\. Integração com Rerun.io: Extração Aerodinâmica e Telemetria de Atrito**

Para visualizações e diagnósticos multidimensionais, o ecrã nativo torna-se obsoleto, especialmente em simulações que exigem vetores isolados aerodinâmicos, mapeamentos compressivos, lidar volumétrico espelhado ou dinâmicas temporais fluídicas iteradas noutro local ou na nuvem34. A ferramenta de escolha primordial no panorama de vanguarda assenta no Rerun.io, um *data logger* construído sobre arquitetura vetorial orientada em coluna (*column-oriented*) escrita em Rust que engloba suporte imediato em Python34.

### **5.1 O Modelo Aerodinâmico e Viscosidade no MuJoCo**

A simulação complexa de drones ou geometrias aladas integra de forma transparente leis fluidodinâmicas se a estrutura MJCF incorporar parâmetros nas tags globais e de contacto da geometria30. Se parametrizada como fluidshape="ellipsoid", a matriz desativa os cálculos esféricos básicos orientados pela inércia e institui uma generalização do fluxo aerodinâmico em 3 dimensões para cada objeto (utilizando parâmetros derivados do Teorema de Kutta-Joukowski e do efeito Magnus rotacional)6.  
Os atributos de arrasto fluidodinâmico modelados pelo vetor fluidcoef estipulam forças restritivas6:

| Coeficiente Fluidodinâmico | Representação e Física Subjacente | Padrão MJCF |
| :---- | :---- | :---- |
| **Arrasto Franco (Blunt Drag)** | Resistência da barreira cruzada frontal linear ao fluxo (![][image16]). | 0.5 |
| **Arrasto Esbelto (Slender Drag)** | Resistência colinear no eixo esguio primário do cilindro (![][image17]). | 0.25 |
| **Arrasto Angular** | Força oposta gerada ao rotacionar os elipsoides no fluido denso. | 1.5 |
| **Sustentação Kutta (Kutta Lift)** | Resultante perpendicular traduzida pela circulação não simétrica perante fluxo denso (![][image18]). | 1.0 |
| **Efeito Magnus** | Rotação acoplada induzindo refração de ar e elevação (![][image19])6. | 1.0 |

Os fatores aerodinâmicos combinam-se ainda com a configuração density, viscosity e correntes de wind configuradas na aba \<option\>14. Como consequência destas simulações, que implicam resistência viscosa ao longo do trajeto, a energia atenua fortemente os objetos voadores submetendo-os às derivadas numéricas resultantes da oposição ao ar.

### **5.2 Orquestração Numérica Visual via Arquétipos e Logs**

No Rerun, em vez do ambiente gráfico ler a simulação, é o script central que escreve e exporta as coordenadas de rr.log a cada transição da árvore semântica (ECS), mapeadas em grupos lógicos como "drone/aerodinamica"34. O sistema utiliza construtores semânticos classificados como *Archetypes*, agrupando dados espaciais (nuvens rr.Points3D ou eixos rr.Arrows3D)37.  
Para visualizar o desgaste do atrito linear elítico ou o ponto fulcral aerodinâmico em 3D, deve extrair-se os componentes das matrizes originais em tempo real:

* **Colisões**: Através da matriz iterativa residente em data.contact, a estrutura expõe o número transitório local (ncon)2. Requisitando a API matemática C de mujoco.mj\_contactForce(model, data, index, force\_array), extrai-se a tradução convexa LCP aplicada ao bloco tridimensional e desenha-se um vetor exato de resistência no referencial do mundo visual5.  
* **Forças Acumuladas**: O cálculo aerodinâmico (ou gravítico compensatório) é injetado ciclicamente nas reações passivas e globais alocadas a data.qfrc\_passive e data.qfrc\_applied antes de mj\_step terminar2.

## **6\. Pipeline de Documentação e Otimização URDF Direta (urdf2mjcf)**

O repositório principal do motor físico, atualizado exaustivamente sob a égide computacional da Google DeepMind (albergado publicamente em github.com/google-deepmind/mujoco), inclui o guia matricial "Computation", que relata equações, bem como a documentação extensiva do dialeto MJCF em "XML Reference" para consulta exaustiva dos nós estruturais integrados da biblioteca base1. Contudo, no percurso desde o desenho CAD industrial até ao bloco XML orgânico final, persiste a lacuna topológica imposta pelo domínio pré-existente universal baseado no formato semântico robótico puro e imperfeito: URDF.  
O URDF é intrinsecamente limitado nas primitivas mecânicas de controlo e colisão vetorial exigidas para dinâmicas de contacto complexas (carecendo totalmente dos ajustes de soft contact descritos anteriormente). A fim de transpor os robôs, manipuladores 6-DoF complexos ou viaturas provindas deste esquema para o MJCF puramente vetorial, a comunidade de robótica avançada confia irredutivelmente na ferramenta modular urdf2mjcf suportada publicamente nos projetos da incubadora K-Scale Labs16.

### **Resolução Algorítmica e Decomposição Convexa (CoACD)**

A utilidade do módulo, instalável globalmente por infraestrutura pip (pip install urdf2mjcf), suplanta simples conversões topológicas através das suas reestruturações inerciais43. Durante o mapeamento a partir da linha de comando com urdf2mjcf robot.urdf \--output robot.mjcf, o conversor examina assimetrias indesejáveis nos componentes da diagonal da inércia vetorial impostos inadequadamente no passado por software generativo, procedendo ao seu nivelamento algébrico, prevenindo acelerações instáveis43. Mais do que a translação exata de eixos revolutos e prismáticos para juntas hinge e slide de MuJoCo45, o algoritmo separa formalmente as malhas importadas que servem para cálculo colisional (classificadas intrinsecamente sob class="collision") daquelas que apenas renderizam visualmente e de modo inofensivo a textura final (class="visual")15.  
Para cálculos da malha esparsa (*narrow-phase*) colisional nas matrizes convexas, a utilização de geometria intrincada importada por URDF (ficheiros .obj completos com arestas reentrantes) consome extrema carga computacional com forte instabilidade associada a polígonos côncavos falsos16. O script resolve a disfuncionalidade implementando a orquestração Decomposição Convexa (CoACD) sobre componentes assinalados, fundindo e subdividindo as curvaturas de um veículo ou braço articulado em múltiplas geometrias primitivas subjacentes estritamente convexas aglomeradas indissoluvelmente (atribuídas como peças lógicas no atributo class="decomposed\_collision" e tingidas cromativamente com as paletas inerentes do visualizador)16. Este protocolo converte peças complexas não determinísticas num espetro algébrico computacionalmente limpo, isento de pontos interpenetrantes fantasma, assegurando o balanço matemático crítico que consagra o motor físico na fronteira da evolução mecatrónica cibernética contemporânea.

#### **Referências citadas**

> 1. mujoco/doc/computation/index.rst at main \- GitHub, [https\://github.com/google-deepmind/mujoco/blob/main/doc/computation/index.rst](https://github.com/google-deepmind/mujoco/blob/main/doc/computation/index.rst)  
> 2. Computation \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/stable/computation/index.html](https://mujoco.readthedocs.io/en/stable/computation/index.html)  
> 3. MuJoCo Inverse Dynamics and Gravity Compensation | PDF \- Scribd, [https\://www\.scribd.com/document/756209481/Convex-and-analytically-invertible-dynamics-with-contacts-and-constraints-Theory-and-implementation-in-MuJoCo](https://www.scribd.com/document/756209481/Convex-and-analytically-invertible-dynamics-with-contacts-and-constraints-Theory-and-implementation-in-MuJoCo)  
> 4. Installing and Using MuJoCo \- ORCD Docs, [https\://orcd-docs.mit.edu/recipes/mujoco/](https://orcd-docs.mit.edu/recipes/mujoco/)  
> 5. API Reference — MuJoCo documentation, [https\://mujoco.readthedocs.io/en/2.3.0/APIreference.html](https://mujoco.readthedocs.io/en/2.3.0/APIreference.html)  
> 6. Fluid forces \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/stable/computation/fluid.html](https://mujoco.readthedocs.io/en/stable/computation/fluid.html)  
> 7. Refining Differentiable Simulators for Learning and Control \- arXiv, [https\://arxiv.org/html/2506.14186v1](https://arxiv.org/html/2506.14186v1)  
> 8. Predictable behavior during contact simulation: a comparison of, [http\://graphics.cs.cmu.edu/nsp/papers/ChungCAVW2016.pdf](http://graphics.cs.cmu.edu/nsp/papers/ChungCAVW2016.pdf)  
> 9. Modeling \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/stable/modeling.html](https://mujoco.readthedocs.io/en/stable/modeling.html)  
> 10. Computation \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/3.0.0/computation/](https://mujoco.readthedocs.io/en/3.0.0/computation/)  
> 11. XML Reference \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/stable/XMLreference.html](https://mujoco.readthedocs.io/en/stable/XMLreference.html)  
> 12. Modeling \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/2.3.7/modeling.html](https://mujoco.readthedocs.io/en/2.3.7/modeling.html)  
> 13. Programming — MuJoCo documentation, [https\://mujoco.readthedocs.io/en/2.3.0/programming/](https://mujoco.readthedocs.io/en/2.3.0/programming/)  
> 14. Model Editing \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/stable/programming/modeledit.html](https://mujoco.readthedocs.io/en/stable/programming/modeledit.html)  
> 15. MuJoCo Documentation: Overview, [https\://mujoco.readthedocs.io/](https://mujoco.readthedocs.io/)  
> 16. URDF to MJCF Conversion \- ROS2\_Control, [https\://control.ros.org/rolling/doc/mujoco\_ros2\_control/mujoco\_ros2\_control/docs/tools.html](https://control.ros.org/rolling/doc/mujoco_ros2_control/mujoco_ros2_control/docs/tools.html)  
> 17. Python \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/stable/python.html](https://mujoco.readthedocs.io/en/stable/python.html)  
> 18. Optimized Repositories \- CachyOS, [https\://wiki.cachyos.org/features/optimized\_repos/](https://wiki.cachyos.org/features/optimized_repos/)  
> 19. AUR (en) \- python-mujoco \- Arch Linux User Repository, [https\://aur.archlinux.org/packages/python-mujoco](https://aur.archlinux.org/packages/python-mujoco)  
> 20. AUR (en) \- ninja-kitware \- Arch Linux, [https\://aur.archlinux.org/packages/ninja-kitware?all\_reqs=1](https://aur.archlinux.org/packages/ninja-kitware?all_reqs=1)  
> 21. Minimal Mujoco CMake build example \- TechOverflow, [https\://techoverflow.net/2025/09/11/minimal-mujoco-cmake-build-example/](https://techoverflow.net/2025/09/11/minimal-mujoco-cmake-build-example/)  
> 22. How to use Mujoco in CMake project? \- Stack Overflow, [https\://stackoverflow.com/questions/77374919/how-to-use-mujoco-in-cmake-project](https://stackoverflow.com/questions/77374919/how-to-use-mujoco-in-cmake-project)  
> 23. Python Bindings \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/3.1.2/python.html](https://mujoco.readthedocs.io/en/3.1.2/python.html)  
> 24. Changelog \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/3.0.1/changelog.html](https://mujoco.readthedocs.io/en/3.0.1/changelog.html)  
> 25. mujoco/doc/programming/simulation.rst at main \- GitHub, [https\://github.com/google-deepmind/mujoco/blob/main/doc/programming/simulation.rst](https://github.com/google-deepmind/mujoco/blob/main/doc/programming/simulation.rst)  
> 26. Simulation \- MuJoCo Documentation \- Read the Docs, [https\://mujoco.readthedocs.io/en/stable/programming/simulation.html](https://mujoco.readthedocs.io/en/stable/programming/simulation.html)  
> 27. Functions \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/3.1.6/APIreference/APIfunctions.html](https://mujoco.readthedocs.io/en/3.1.6/APIreference/APIfunctions.html)  
> 28. Globals \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/stable/APIreference/APIglobals.html](https://mujoco.readthedocs.io/en/stable/APIreference/APIglobals.html)  
> 29. MuJoCo XLA (MJX), [https\://mujoco.readthedocs.io/en/stable/mjx.html](https://mujoco.readthedocs.io/en/stable/mjx.html)  
> 30. MuJoCo Warp (MJWarp), [https\://mujoco.readthedocs.io/en/3.5.0/mjwarp/](https://mujoco.readthedocs.io/en/3.5.0/mjwarp/)  
> 31. Changelog \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/stable/changelog.html](https://mujoco.readthedocs.io/en/stable/changelog.html)  
> 32. MuJoCo 3 · google-deepmind mujoco · Discussion \#1101 \- GitHub, [https\://github.com/google-deepmind/mujoco/discussions/1101](https://github.com/google-deepmind/mujoco/discussions/1101)  
> 33. MuJoCo XLA (MJX), [https\://mujoco.readthedocs.io/en/3.1.5/mjx.html](https://mujoco.readthedocs.io/en/3.1.5/mjx.html)  
> 34. Chunks \- Rerun.io, [https\://rerun.io/docs/concepts/logging-and-ingestion/chunks](https://rerun.io/docs/concepts/logging-and-ingestion/chunks)  
> 35. Examples \- Rerun.io, [https\://rerun.io/examples](https://rerun.io/examples)  
> 36. A Gentle Introduction to Rerun (Series Overview) \- YouTube, [https\://www\.youtube.com/watch?v=kzafl642qqs](https://www.youtube.com/watch?v=kzafl642qqs)  
> 37. Exploring Rerun — An Open-Source Logging and Visualization, [https\://medium.com/@turingmotors/7-exploring-rerun-an-open-source-logging-and-visualization-tool-derek-4667015dc965](https://medium.com/@turingmotors/7-exploring-rerun-an-open-source-logging-and-visualization-tool-derek-4667015dc965)  
> 38. XML Reference \- MuJoCo Documentation, [https\://mujoco.readthedocs.io/en/2.3.6/XMLreference.html](https://mujoco.readthedocs.io/en/2.3.6/XMLreference.html)  
> 39. MuJoCo Warp (MJWarp), [https\://mujoco.readthedocs.io/en/latest/mjwarp/](https://mujoco.readthedocs.io/en/latest/mjwarp/)  
> 40. Log and Ingest \- Rerun.io, [https\://rerun.io/docs/getting-started/data-in](https://rerun.io/docs/getting-started/data-in)  
> 41. GitHub \- kscalelabs/urdf2mjcf: Convert from URDF file format to, [https\://github.com/kscalelabs/urdf2mjcf](https://github.com/kscalelabs/urdf2mjcf)  
> 42. urdf2mjcf \- PyPI, [https\://pypi.org/project/urdf2mjcf/0.0.3/](https://pypi.org/project/urdf2mjcf/0.0.3/)  
> 43. How to convert URDF to Mujoco using urdf2mjcf \- TechOverflow, [https\://techoverflow.net/2025/02/11/how-to-convert-urdf-to-mujoco-using-urdf2mjcf/](https://techoverflow.net/2025/02/11/how-to-convert-urdf-to-mujoco-using-urdf2mjcf/)  
> 44. urdf2mjcf \- PyPI, [https\://pypi.org/project/urdf2mjcf/](https://pypi.org/project/urdf2mjcf/)  
> 45. URDF2MJCF: Claude Code Skill \- AIMarketly, [https\://www\.aimarketly.com/skill/plurigrid--urdf2mjcf](https://www.aimarketly.com/skill/plurigrid--urdf2mjcf)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAaCAYAAACO5M0mAAABQUlEQVR4Xm1SO05DQQy0O0SERMEdEAFxAcqkA4mKhgNQ5AbJBSJxBmrICSKkNBE5QSp6CkQNQihVGH/W6/exsvZ4PPY67z2ilnE6xIFKKSNOpYI4613mXG3P07Ujd3Xv0YsaE/IoTYvC04hlhY7vNZ+RtylEnCB7rbVnsIlMySHkU8AN8BpnBnyP4tyEtscB4BvQEsmRjaAn4D3ig+eipkd4kHxaKZoaR8Oy1wnCH+lEIWwP+Fes8uV9atdknTJBDdoBwi/UC2fU34gQ3eP0x8bCAU9MqMbHcN84dyLC7xzuA0iEF75e2AjZCsQak58R35F/Nt6yWvpAUZJHtQN4qZyLtK+2Xum1xJPWOLP4LuP58aVXCh/TzhBWiD8mpC0z3+oypsnXdpb3UNj2LsEbCF017m1uQE3EdbtJyf6dGqTaP6blJZS581rKAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAZCAYAAADnstS2AAABKUlEQVR4Xm1TK45CQRCc0SgEClYhsBjCBdZzBOyuIkFiMFyBkGBIwO0VMEjCFdZvNuEQUNOf6e7Mm5eerq6prumXl5dSyniwZ868DHHl6nhkjO25uCmWXq272lvKtNxnJlEsLHN+F1QLJ9QIUiMdkKzXdzSagz8uKQpdQ30B0jcCXUTMkc/Id8SMbfMH8C9i5aUjpCtAD/gBfJGjAeo/8Df7gjltEJ8ox6heiLUb4hv7UXB4iZ2Ihzw2cUvEF9U0GgvLCEW4pVZ2mCBOhNxVtCP/Y98L0Qf+KdlExVm7UloAPpHvyAfkKdM8hC0ax4PoEueoYrccET+YMqGj3iVmchs3RG8V1abq6JbeZI6dx1Y3E4VF/6BXtH6B0Wu50FP9DfxhKONI1RYGb6xNFSSUwov3AAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAYCAYAAAAs7gcTAAABL0lEQVR4Xm1SoU5DQRDc0xUEUdcqBBbTYCvqcf2AOhQJEsNXEJIaEnD9gJqKIpvaSjwh8BFlbnfvbvbazZvbvdmdvXv7nogkfQJ605JzSdfGlROJKCNqnlxvdh4Ec/iLWlRP8w0FC+CI8KMwoXPZuJ8Cv+ifRZWN/egoe/Oa6UOKXKSgdh6ek5TTjGE+c7dg3hHugIkVpDHcF/DQCkVGwAbhAJs9Yp0CbIj4G/6TP8MTMENwBfII/1hy8PfAMlzD7YD7bNsksqU1llGjLBiIfoj0nIs9dw28aUnQ2/KD9cUrL4FV9u1fSW0s+CHu4P7EJvIK3HjKz/LK8iGCujHNulzI6hWyPtGbRD0fSbQRTaVrpwvc6Viod03SFbQziSgVzSYRi3nT1cdt3yybXUnkHykTGP85xsALAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAbCAYAAACqenW9AAABHklEQVR4XoVSO6oCQRCcDgQzY8GTGAvewiMIRi+QzT2EYGRsprngRR4ve4dYy/73KNjLzHRVV9f0LttaI30iXrkzuVCDvCgNnba4JPKzYc8afu/PW09mpnsDcoHiSPtbpNtZKoiz5E3qLBTvZu1XRPsM64I1Ao98NpKTMZ1ZhZiAuKp4wDoCPzQfcOXrXIkn0R7bVlJmfrB2UuOdeZnGZ/K4A69jQhMXDccc5Ah6UVhz7uK7OLpogzv/HRrr8+RpqJ2Abga5YMoyh4BfiA/5xaJWp55i/WEto5SHDTZythORl9yZdGatqLQAwUllgvLxzcjZVJPoCrmerwx3bSl63pNKySjm9k+hGj7MhxNvJP1i3b+lQPq5Mxgj3SRIjidUFxefur/fiwAAAABJRU5ErkJggg==>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAaCAYAAADxNd/XAAAD40lEQVR4Xr1XS4gVRxS95UyMKBpchPghMMRE1ASjOC78gCBCRGcRQvxtZJQsxMRFEjeKih8U/4KiIAjOTh0QRDBBDEkYMw4KIm6GAcEMihpBMCAIKqLn1q3qvt11+70eEA+cV9XnnrpVXV1V3Y+oEVxZKKJJOEHiT4T3jDr9a08df4LQqHGeVLGkBIknETIsBvf6mvdUGZ2OdIEz8sumMJImt21MR4AhRUwCe8Dh/qqBsYRxsN5COb66UZWejtxAlV6IfAjeBGeafkPK4YNrwEuGXomvwWvgK/ANeK8YTpp3kPiYAwieYDH3uA34uRrqmWrCDvMEPAHbtWhboyzFabCXZGDy6APU4Maivpm8xx3IHQVcBzureqwJHss5LRTSJblF4LW3ieQGvtBhhVXgFvjZw5s0Q8j5OUn7T6Ka9FUPa0lWxAcFNSbTSUN9OskJsIJkAN9khghH3+FnImp/ov4c5cig62I1+L9UFZrchTEenkAex2wVagBHP5N0Pouk4bqgR4wGvw/lS/BKFiniMHhDC6WxfwoeI1mqvQjyftoDLpewng3HT4AntBGy9BfBCeBHJDcg53cOXlot4BLiuKOtLBoz1w1eVrJAgry8HoA7wRYn+6wfQe5vSm7O8Bie9WXRAq+zPnX9EEllA0nHnSRPhrGf5AbnhesM4QYugGcLAYYE+aS7A7aqyG/k+ytB/AMo/EQ1wwLwoLrmF1BcBqPAn1Ssz8ka14PwUE+gu7RsGP7ohb5bPbZW1J9RPG3SRv2QdpTFHHmDXSQdRL0Lv09D/QeKJ4GjMSQnw3mjs4iTFJdQ0bOP5MnNV9rCoP2oNI1H4C9lMYGTc3tM1qOjbWFd8gbi0yliadD5RVUF3juyHLN0Hrz0XlPxyfFe4HxfKU2D/cskgZ6N4szw226QZIMKnD+NrIHyG5f1yXJpPoY1JG/RMhaRtP04XC8DX5DMsoW2MFnTyoGIdvTPM893yUbeSB3hZueSHJPDgvcIeF98PulDeI6KNUeof0aSb2o6c/Qr+Af4D/QjTnxnKiaCnz4v4zgGQZqzCkN4g6Z38S+40UqgpLj+k2MyeA6hdjwf7xDGE9GwQcOgf2fcLoslyCeLU+s/z8mn0yDKL+1ubDVHEk+EDOnke4xA/S7KOSVd43fo/1kJnHwHnVKRIaKixyGCB/8XFU4dn3glir9Jlg+TP7vbco//COyBR76zTMQBVg3U0L1k6E3wLbi9dlvx8Fvc+EtZaw9oUw17AVX+Kv0dQneRdJcIplRCc0fNGW2CZOT1UtrWRDAlD0NPpEQowR6ElqqCRV37kxaGYEi6yJEIRbwFtWWUTfBYVPMAAAAASUVORK5CYII=>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADcAAAAaCAYAAAAT6cSuAAAEGElEQVR4XsVYSagVRxS9rcYJIRHEEUEMDnHChYobXbhwIiBCgm5cKIoQFUXciAhOOKErEQXFAZxxICQKTihCDBFnxGkhguCEOCAo5iN6bldV162qW++9/xE8cLrrnjtUdVV3db9H9A1RFEUslShI1+ujRh67nNu1ZXg+Ne/JIciQnWoQuhlTLtAi69Y7CurpubrKgGclTr/GeoxcBb/AuQgZk2APOFwKuUuMkAgapoJbK6uhFAGOb24OBSndwRsQenjJogxqYQfAQPAB2D52VGhZ3UyeFIOAmeBJKXiIOLUmZfUj4FrdqxXNxNX0G2geobUDX4EjvCRQJzlSyvNP4Aewd+X2vgxq+RwaifEQ0bvBw970UCrGUmzTHPBWLKpIUinVYpshtKqZNhxmQWmC/EMoJ3FktayDsYPETGmRKpLARBDQfFmtH/gFHBmoGbQG54JXEPUfQveyLRKugpudoRQaTebi/wHPknke/gR7acEKuqIq78LczwwnIvU0TseqKKM5NIHTvMm+tLMOxAMp6Drcv1jtb/ATgluZcsVLHJZVGSH49fA/ONmW7g9+BJ8ofWngqPPgz2Qm8InwnSFeoYI3EV/Mtl6Af1RiBlyQB8fFLYptOKyzbT68A+d5f6X3BN/YlXZqWzLx+52WR1ljDLjKGg/BEyJgMHhf2BKsL+eGu+x4LnuBTRD/qpQqIgjllVsgBYuNZO79CULjwbI2X2gU1iuMGY5mPJm86ULrQ/lJuov8lbEoS07Btw4XXCg0Dz+Ae8S3pfgusq3LaL3HWe5aK+DkmkPD64nnNUb5zPHrppOIXEriYqMSz8DFzjCucAIn24Fo34pjRZs3Cl6lGP8i/0K0AhfA51KAuzOOM6ncuLIXyX2cE/42ZJ7FaLuv8Bn8nRtJRSt0Ah9ROPAfMUOrcT4gtF3gUW5EhfhZuV22zFa1icytdVDEMPbZSVyUDMTjEHiNzMVwNV5J3oVTFNSHTD+D4gHFGEa8AkQXkcXb+HEyO6AEz/rTuBDMjmTegbxlX7Ft7jTexdaQmWk5YTEGgHfITPZ28Lca4+ZXADYyahU7mgfTQ18ygx4lNA0ryMQNiXRGF3CvN9OZku18FyV4h69+nWRjQ4ceZlVenS2BI8Up4hWOYPOngLODTSHoTu/bQXj5WXxM5jWRQi9T9zJ5NV6T+8nDAWEQ628L7YPWPI9ncOyaunRD6d9ps8CdgSNCGacVkFD8S8ANigc/hegmdL4l+dVQbj4C48CJzkiyG4FJ6gZeIvOsV6JHndmpjTJjPThJ2Hkk7liIbYdYr2zsqEXwN0OAuu/Sugg/T1tcrogrfSf4ITRnMLnY5uoK6s2upjWMctb1GppWGyYjyUsEi5wu0UhMhWxw1lHBRZhbsH5846hd6yv204fjrIwp5QAAAABJRU5ErkJggg==>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADkAAAAaCAYAAAANIPQdAAADqUlEQVR4Xr2XS6hOURTH17nkuqQrlChmwkCRia4orwzIwMAYpQglwgSJKBSFgVLKRMpAkQmirudAXnmllBSK8kyibvzXWfuc/Vh7f2d/180v/+/us177+Z1vI6opbNN78u2WVLyPsiuDT4Nb0RzfHBFgEgoahM830F3oCvTWPHP7JtSHmCESnIk7llS7Xf4lF8yDtjrPt6DNzvNZp21o6LHBnSK1Hq3L1ZtlDZH2LqjaqS7Yf8M+o4oCe512U48DRDud5MVOdNoLoc9QhzyWBSY4bR+1iD6lPeJUJtfQ0qnpgZ+/Vx+gP9BP6B50Stx+snniXbvkOUJs2iroKklt1h2S7zGL2z9IjrpZJMVaktgqnxeX3wGb3CCfIhx2zXmSIjNDh6U+utegbZ4rRHfyDnrhWWQLJ+HjJfQKGuP5GanTUcjk3kOdunQKP5KPHe+kPwgXGz8U+gXNri0V6d6nkCzgsdBhWEKlv9gfOgzTSfJPhA6FLFxoLZlF3iDcF49iPpy/8bezfFJFo5kbYef6S+PuslYf1Bt3F3xqOH9F6MmnoB0kRZaHLgcc42InyffhO3QSWuyHJLkA8cKM8Kx2Rl1oc/98ZCMLR5dJxjfaNTKJRQkNJb0kg+hO+KPYUNOK5/IEvpH0EaFM6iGZBF80QoaTjO126Mik7KCbIkclPt52KassIpnAbmtSVCfpcOgAy0h8+xK5PvoUlPAR5SJ7QodhCzRWmjo5gwMkL5U5LbIfkRzXqaEDHCH5PvNvswI1D4aG2MNxkkkuqC2WUSTXN0NqmCl7yQPoKzQ4dBiqRU69OR+TvM2HhQ6SUxLbfcVzkiJ89l145KfxZ31gN/gTU6dE2nxL4glcdDwu/NPyCaHn8Jf/AxAynuQUXI8s40joITRNHiMRQjGZZBB8o3DB3ZSOkrxF+Ttbo+eRQJwrSeq7F3uGf9BXI+YjArdTutQaknx+q7uMg27w5AO7oSj/zSWZGK8EF+HbCD/fh74YG+tMlVaRGk1gXwc9IVvnKdmrHF/xHkGHqN6FgII24INjX5Of/4zk2lnV5X5aoLZEGXyMyQ3NSWtJu/EuTbnZ42rpdIkEZnfiY0PbSMrHL/rPXahtHgCyywWB7sqpVVRFW95pG4hkprpRuIHN0Yp+pETwq+TUzInJpr+T7z/+9vyXrpOTjNgiJkpZmbSnGZvbbpV0vJ1rOibpUvbILsVjlNXg21NRKZrjqwh3ECpLGdLkhJq+skPddk5ShL8oBZK2hBeVDgAAAABJRU5ErkJggg==>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAaCAYAAAC6nQw6AAABwElEQVR4Xq1VMS9EQRCejQonLqKgo0CivlBQuUJCo6DTaDR+gUZyEi1R6EShkGgUJEQU8hK1SqO9RlQSIhKK883bfW9n3+x7V/Al387stzOzs/OSOzLkkfpu8bqKCKUYypLlBf+EikLqSD0tbOYP3cmnhYiPItim3hz4DHawuyvENsDZ4AJ1kXwC0TA8LtTK2oLpgfMKHpZ0qhVgHeyATaHNIxSaWUl3QZqqkQ/7DP4XbK+I2QZ/wLrvyAQ1BsFjCC+wCbgLvoEXLuaIeFZEHyDHsH9ujzIY6sfyAO8a/oArz0X5WZv+MtOH5Rvcs2nZ4nEAhZOmhMZP4FmMe8k0DWuGFtOdP0gxQnagibiZlxvwKZes3jK2o5qXvOXqXIg7yFCD/gm7LzQGz+4+2xSftkz6E7PP2hI4A24hgbvgbnZc8hjMaZ4B1MF3cDXdGZrG0nazGCUbzHOa4DlCX4M/BP8W/mRexXW2QPZzJhCuYBvQ27CXiNgQ3Z+Q1R85xssFiIQAcd2pwaBiWhFSl4GVSSSPVIUQ3Qp5RIIikkB4Go8t/5Hr1nglSuNVURVZ9o+S+e5AnVei7L9Pb3OoLqRx/i+5AD2inowq2AAAAABJRU5ErkJggg==>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAaCAYAAACD+r1hAAABLUlEQVR4XoVPO4pCQRCcYRNx0TMI3sBYTAURjASDDU30BBoaCouXWDbRl5kJJgaC4Zp4CEVNDIy03pvP656exxb0dE9VdU+PUlFokrRLIahgawFNG6mJvhAMp1MDNkykirwvZkQwhX6H6YV6FHmPVdkF16FtqHGFHQw/iD/bzE1yfZ2WZ8TcU4UwXQ2kdJ0x4hf1GvwWdZ9aKSbKNCSIiuUWmHbLLRwbxAlTPz2js/WuWvzWmJ5gZ46wOCCW7kL7usqs03QCpLrh9Jd3GSlDuusF+YNI34gH+PQ/bcSAaOoIgT2NQXscK1zKyvyv6saXkK/IneBnPcQOkYBveTYzBU77gq/zJIw5hCQIxnCVDReNdANb/beNgGywjBhSuGWhQAj5TKRPNAfITXwqpd6jkCMVaYlzCgAAAABJRU5ErkJggg==>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADYAAAAXCAYAAABAtbxOAAAEH0lEQVR4XqVXWehXRRQ+44ZmLiiICIK0GZJKiog+yF8lMAyrl6CQ0sQFixQUwZVEfFD0wSVbsCAMzVa0KEpQnyTx0UTc8EG0rKB6kgKx78yZuffMmZnf/5d+8M3ynTNz58zMnTuXqIFTWShr1PQatGutnEGPQaOma3T9kPtHx247GgMKPgVJYzh4EDwDfgs+npoZjvoj+QKlsa2kzb1ihE+9YzctU72tOemnxToYF1r/gHfBOb7k4Ed0KbGGJu+AL2ihdyQBbEbyVtSz0Lrukw75tPXvA54CZzdKhKPvkO4MtXEQ7kVDxCvgV03tvuAD67GqRS0+pZ9oiw0eBW/BZ4hUs2lj9IAhMAHPyE1wnhYDnkW7a8jvoflhazSQwPTyZFFkQgknKl7HwbVWbODoU6Qfa2kBeNWbyniClxjGxVGoOFZWrOJdR2nFAPc6yQIMyCxEr5IENVDrh2DYFyt6GKG8lGSJRytTabx5YLlPSTJwlRVzjzkZhxwWLZ6GvpsdwEdEkh4uIXuzcbNwdBQJH6dWj0nM8sCINoALjaaBvulto8mKlaO7Dq5R9ZFw5MNmNvx7kG8X2dEwkll4Pnqa/vqCv4N7SFb1M/AncBPJu6mh3jGPh8GzlGyPpHe234J00VgqW9HjB3A/F4L/MZLxB7o70XFyEGdFwaN9ykyU2c7fh3FhlV4kaTO18fLQp6J3XIVsQTZVDby+BDyXSjowvSN8chTZES7Xeo2YRnLiTUzUthWvzL8QnmqNNJ8ksClKY9it+D3YT9VngDcoffn5+R82tSywDB9QZ3szdr9iTnJj9Mlp8GSq0y7wNtW2omAoSWAa74HXzUwvp/AOKr0ycO/BfbTjCSitHl+fOLCwFRMXfv/uguuVzsHwrL8fBQUd2CTKP/hfo594S6DQ548UrmLtkx1r5dESb0PupwDjP5hkWz0n1cQq75JL3iX+5rH/XHAUuEPZ9OExAdkvKD8UbLwj/gAPhDpjI7hV1SMksDJ4F+y1Yg4ZBB+hq1KDB58+v1G65TgQ1vi05G0x06vSjz48BkL6E4WfwdMo/0MyKJ6UKyS38b8dr5Zvm0xop8AugyusWMNH4CdWBE7icVuM9iTJkfsNxrLM2Da79PB4jeSm8Bf0lfDnyfiSJGC+no1vw0kDS2oMCZ4vCDwx043eVO1+XEy8Cv63xZoiyqqBPe7r6GyurJjjb+0FqzaIfaq++QT7FXyptyfmM5TAHvf/A8msy4rlj+FdtTpRgk/iatq9AYH/QB8EXQRW+7AmIyytGP8Znydzyc1hendyQPDx/ExqMSjNUAt5x7LpThtl5hw2MB4bHzwTWqnwI9sBg8DPwTHWwGgbV6N7GQw3lO6iyCwibDMqvqO0yGj18WSdPjD0LHbXe9mrtl0DOk6Wo/8AzfqgAObod10AAAAASUVORK5CYII=>

[image12]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAZCAYAAADnstS2AAABRElEQVR4XnWSrU5DQRCFdyVpCAgEyCoSNMHguI5aJAaD4QmQ8AK8QBWiEgEJCBRJH6EGW4MkwSDLtzszu7P3XqY983fOzmzTDSHGEPiaSeoalnsie6/xlgb+a7rM0OdGqjYODtV1Q0pspK+tU/AJNuC9T5bJrt4LIr4rXfkh6VNrLS6DiDslhvfIC2L+Lsh+wZYQVbMD5uAL9QfxHvKb+FQlsnOCW4JXsK3MnA1cIV43IykewIbWoRH4W0LqTaO71z4uNdPqOiOGNzQrSUWY3CzKhM4t69ImcE5+Am6M26X5w6ELPX7ExHUaQH4AHpk8FWm+TjwL8i+lq7zQOyauwTO4MlnRN41+3RBaSKh+TFMKX+fc3ko+accVwrUPoOTKqWufks5UqplqTdWqFY0Rkreq/nOVanygmOc0L0Q1KWyZVtn/Afr5I5XjQclJAAAAAElFTkSuQmCC>

[image13]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAbCAYAAACqenW9AAABYElEQVR4XpWTsUoDQRCGbzkFO4u0PoigxsbCF1AQtEkhgin0AXwLOzshIKSLla2CVSofwF4LEUub+M3Ozu3s5lK4Yfb+mf+fnf/2SNP4FYrMpRWRVx8RespSiEUlgz97SZyW1UNU+JZ62ckldJyCMfEJWhDXeW7nrWwkO0cj4t3Vs21eCBPAN6j1ZPxVdlq2D9BDFiXGiaxrm2QBHCWbexBTuDl438njfsOO37BFekF+Bh4h/gFfJrEoY8MzHW88r4ijaCM0h+A74Kb3PBALjV7bnBjDrQthIv1A/xeHY6C83JBEPL8T98aqJINb4otmu98pIf5lnRIHSRhbhHh03TPGPpG2xIRYM2YD/S/PExFHfWh22F7Ar2TD/Gorl0j0KxZi/fo5E2ux4l5K3br7667JVEb5Z/FfqA3KFDehK+aC4m4vJ2ghYtvqCUbU9TLvNdlzTWkVDlUoo5eleoAe9AeZ2SesXOCdugAAAABJRU5ErkJggg==>

[image14]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAaCAYAAABl03YlAAABBUlEQVR4XoVSuw5BQRCdVWgleo1CSGh9g0IUKmqF79Bp/AAd0VHpJSoq4QM0Hr1I1Jx9zN3Zu1ec5Mzsnjk7s3tziTSUiQLKSpHOhVAS2W28KeNAjH8WWU95++AV/IBjLQQXF+aO0iZF7UQJOtnNBHyCeVkyRfGiM8LaFxl+ZonsfVZYH5BP4BYs+k6KBs60BAtWoj3SXI5bgBcxWocNeJfKDZy5rowr1kfuVCMzSvWSMlFF2c8xZVMDQZvqvgmNwDdY5tY55Ady141rIr7AIZ9gVFHVr9nAtMO6FTxCjEi0JHEINiL9gKzK3zfolLalNy5kT8pWDeJxXg7BUlSKBEq1jZPBF1sgIVK1jnaAAAAAAElFTkSuQmCC>

[image15]: <data:image/png;base64,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>

[image16]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADoAAAAXCAYAAABaiVzAAAAD9UlEQVR4Xq1XW6hOQRRe45JrihC5PbgUeXAJL3JCUgpReCA51BF1TpHikCNHpDic8HAeJJdcIg/ILYUQxYMHSVJS8kREoZT41p7Ze2bWzPx7H/nq+/eeb61ZM2uu+ydyoRLvHuIGqcpyVZTVK+yqzLeWNWoTYjAYuRCtbFFiLrVnqOSUobpnTSTCJGQXFVxKUSsG26J2FVVj+E8z1wm4oeL9jIoWJWaq4lEFMopXzgoqdAqgHUI3o4QGL2zM7GIUXFrAe3h/Cz4BX4Brjf0gbHX6NexsWfAU4vVqqPanAtjP990J/gAfg/PBHkbvCraCz4y9Z7oNbfDNSecaloqQAaJlXzwB/gEbw/wzpRt+3oM3uOja83dP8wLEvfWbUzvSKRdpi4EJEfg5QhMKnGSLlSiWwS1wU1GqAb+xoOlAkWUX0ibLVTEY/Aq+AbsLm8R+cFy1pqr4MOJDYtV0nHxNmEIpDpFespVmqhLSjfKenwGOsVLhzFtjGjhe2rJfN6aq1YSAs4dekU50cqG4EBFF8QLp1fASvAPeBT/CabPnZVEH2yM82yId5SQ5xkm/kYhnCUyNOa6GEVac5E/SJ2s4ehbLwRHCxnW+gfMcrR/4FFzqaBYqO9nbpGwa3UicqCdJREWDwjYEbJfyO9Iz2qswBFC9SY92l7ySeUwBf4F9RfvN8LjqKRaJRDOsJzfRUkST7gOeBdvZ6nq0UnbiKmcGlOsxAK/caW8pGDSBD4pSXkfRHtJ3bgzbYX+I51bSd/MlsL+xNZBNlA8+ngDWBpFeJTyojHrwE7gL5LbOgStM+9xPnhTeIjyoE3QVng2i2+AHcFYucm9RbybpK2WS1T1wJ/dKEbhCev/GgNmmM055G9o6at7dRBmXjcYYSTZR7hvbTpt+jiZ9x+fgBO3SLaCyj4E14H3SI8dTz3fqauKvoDh4f34GF1gpG1L2/wIuFnoOTvSYU15ItpMNyk+UZypPdDg5iSLmRfxscGzfnXYSiRpEVzxpvbDZ5TkV1PvTRyN4M/NghEFlootIryZ2lTPKM59IlM57NpUdqDncRGNbzkfYRw/8NcV7LYPxXQVeAwfmOjAMXMcv5krjRE85dr7HD5j34tQ18Y6TnbXZEH9bU7ZtooOg9DdBB+lv8h2FGkUxjYEDL1nu2DvwOeklzvuRZ7GewgorSR8qY025GQ5b8FyL5xHSiWK5q+kgnwf8T2mJ8eV79zrpK4kPHo7Dd/Uy8DXpNueCh41tt6nHX3s8mB0q+5KLwXRT9lYq7kd76BtgHZz4bksgHSGwSEGW45KESMYrlSPhjxWg9knRR3J0O4Xy6uUeSciqsgwMBSdK8d8QiV4gbfsLDGCNbjeZ96oAAAAASUVORK5CYII=>

[image17]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEMAAAAXCAYAAABQ1fKSAAAEn0lEQVR4Xq1YXcgWRRQ+k0Vm2kWWFCKVVBAE/UhSJAZCBEFESd1U0g98pZCUQWmhUKJoikJ5EUT1hYTRD6VBZUVFQYEWBiJeBClI3gSlQUbd2PPsObs7MzuzO+/79cCzO3POmbNnz8ycnfcVMbjonka/Ngk3xhixJ403NILnhM2p+HSjjB4ydcMm/xfC5wxPdV5TgKGZ66g6gjExop/WvGjg1KcrPQsREttFJV351FHgs+y1C0wMQ5aBfsi4BLWPjC/d0qaMbbx+rErAqw5OLsF1HfgV+Av4PXgQ8ofNYit4i7VHQDqMpHQo+CF9Alm7rEJkLXgK/A68DTzb5NPAF8D9pp9ucoNfanu8Ryi3HBX0XNOXdeEtgkD6Oq6nwcd9sYczYXQM949D8cBDUsgou+JI0jVoZF1VVxIjYVGJVoomgtsjUgXNT8EnW2mrGBkF70n48sAm08n5KcUc8CSc/Iz7WbEywibwyliYxkBYsTruG4LCmESfLoEB822iq6Ka8exMZL3k5MXA9pMbwKtixZhgfVuIuLL+khHb5/+waDKuq2StNjNKYaq3wZPoHcL9c/BLKH6DblXHMgWddCaCYydDZRo93mosAL8Q89dnH+v4tWAi/hbNaIDI+F5wXiSfhmX8J+63tiI5D9wH3u3JIqgHL/Er0Jlseo08JxiCe0wKk9vAnnFUNCHneKoYM0Rn74xIfj34LzhTJ7nBGnCPNove5FHJBm/j65sr8jghWX8ZmFOeH5iMaiYTDzpf9MWWVL3QgF+hbxLy9QiaZ5KOAnhR9Jk8vK03mR88a8jL4A5wu1T7Xy4EPwMPgM+AG8Cd4Ewbw8K/GXxXNKY3JUzGCnAX+DziWYb7peDXCI0rmPFYrOLocC/4K7jYhDUWiX5Or20kzbtVDT58Q+eFnewWrSeBELgRfM160106GU+BG619uehXjuAq5KTVX7M3pBpX+V2F5H9gckpWS+uPNeTbWgccAS8TPUWfgu0FoofNBpyNB6XN1ltSnTmqLEanzQasMb/D2e2B1FUv+QdadwZyBWvOX6JHfSZijqVxwrXB8/T7vmiAJLcntrC7Br6Pmw3xCvi0tT8Bn9Bm5XGltDWIK+YHaf29A94kOtFcaT7qWeU9mmHCRAnNAmf1whc6PcEyOG+Iq3uzRWeYQXHrfWgGE17wP4EsgHFkV+PGE3ANJoMrgODXY7U3gFtl0noviU5ujEVOC/24CFLCB/rLD2p3P64fOV16tXAuLo9YZym43NqzRFcIwT09ae3nwPesTbBG8KuHrYqfA20ITMYa69PnLk9n26QScDvwB+e5pmPtu1m0JGgygtcqQjOC22OL6FfoAMTcTqwPXA0P+YYVnNwnutevAJc6LXxcGSyCDGih07p0ELxL1P9WjEM9cqwf94iekl8F/xHdGndgzI+iyaQPjsHydzwhMzbWMm4pftUY0AOiBfhZ4eHSyXzROE6IHjpZCkZPSR8S/+HUj+DKuCgUFWIE4z7TPt2UEU9/T5eztjE2aY06igRim/J+rFGk/t3tfYdQ0P3HgtfOiBQuFi1+heaGpK3LyGv0KWNd/RZ6/w9JvKGP+IhLjQAAAABJRU5ErkJggg==>

[image18]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABoAAAAXCAYAAAAV1F8QAAACUUlEQVR4Xo1UO2tWQRCdNdE8EMEUdsEutcFOgoIIFnYWBpsgdikUjWJnilQWkkos7UQQC1ERJYVWChFshIQgxBD1B4SAgiLxzM4+Zmcn8B2+c+fumdfu3t2PAhExe1Q1BB75URmNN8Ybh5/uqapxp3gZSekcXraemrVdYxVboJLaPC+Y4tZ56GQzGTYqt8wnWf01VEY1CjyxXs3IlfePIDoO9yIi3uF9E/yIhC8YX03p98Ez/NL1UeNuwhpocBfmF/gBo/MQRpJrCFyC9in5R3OOhle8TEb1ewTuQbhWpcY/jMF32NcsSgF3tmbYCteJm/CWJcRCmRVvwJtO+YFwDNwBv6LqQRbq3suLKnwPnKrDjEFaB1oOcTV5pmVfGmTFboVobSs7zlgnaTStRbuqFlE7AD7D+26QGg+SZxSPb3j9K34BTlXYg/M33oe8kmp+l8DJVo+nknMvlLUGOgl7GTxqN2YL5GZjsWRytjFhHI8VWF6FKGJOwf6DPUKywtvgbI5J/8jxjR+4H/FYX6wBTaMJ8AWEs1USIOYO8Z0LsdEr8FzxNJDxYZi3sD8xPm1u2AwMH+kTSWyAiJcwT0C+FhsYz9vDYlsOg1fA9+Aq+BgBi+Acef8Cks1XYRdcTnu0APKhsLUNlLs9cX4eYmZITutECuH7+IfiwRgU+W/B7VE25xb4uarx8RT2edZcxHRd2GmSpEMUt4u2wR/gjeTme7hGssqHiObPsX8ZWYv9pBWNXgZOvBXspfJRJ1HG/DM7oPqqjIEaaKQEXdCspC8pwf8BMaRC+pcQfBYAAAAASUVORK5CYII=>

[image19]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABwAAAAXCAYAAAAYyi9XAAACaklEQVR4XpVVPWgUQRR+ozk8g9UVdppgYaEpTrDzD2xEJI2FRQJ6CF6Xgyuv8IorxEKvtxFELAQrBaOIaOWBiZWFhRACYuCwCBbGMn5v5u3Mm5ndPfzgm3nvez8zO7O3R2TIQ5mRXY0iy0QFM2pD2Jg01ejorEa1cLXSoa7Vf0d8Txkq0ig/k+rMmdClURvvBDVfJt1IiV0LU52rll3AMAQ/gFvgBMGvmG9LwgPwktgCqa5q7pEn3AX3wE/gFYQPiX4QySPkb0i8mZUWQhbQhxkHH4P74JqNRSGrzGH4Ab5OI1WIeiQNe8SLGXuUGVTuG7BfFqgF56nco+Bv8DvURlkPpd0HTwaXYeofxSPoY7JHafqldXaualKH5LGCSN/I3d0ZpQniIm+Fh3oC/iJ7OlmsJTq/6c9dBG+hcYv9Jfsm5nDFdrwBHtMx4AD4lFwPfqn0gdwCv4Bd/QiMbXIFhxPdQhrMY3xHbgGNNthBnDd8XDU+C14j1/d0kBmGRhK4Ln4xFGjBfYn5ciGoaA/f4kVy13LBq4ZWMC6DO/qMbQT2ERhvYfwEL+puMM8b91Noh43ozZixuOv4Ta9K86sY+OjvYX4meVEVg8+/A34EP4OcOETSTczN9Ashjfl4+Q1nPAIHhnOJ7oj2Hn5XbFkw62Mb5Vrke4vvqWg+gM6L8gb5c9gA/0A7VSRXIl2PUWjJLvnrtCQujpM2KdwjX8XUWmUNMyRP5b0gvwCncCfgCdjnEOTfGuc8xMj/LrvgK9E0xDOxXrKI5JRtOUvyCs8qmhdbJZcz5Cmpolb1UiSU7z2IyV69H1fFapz/D66JSB26KG5GAAAAAElFTkSuQmCC>