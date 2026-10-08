# Texto para o LinkedIn — About do MuJoCo Lab

Textos prontos para colar. Limites do LinkedIn: **Sobre** do perfil até 2.600 caracteres e **descrição de Projeto** até 2.000; os dois blocos abaixo cabem nos dois (1536 e 1416 caracteres).
Mídia sugerida para o post/Destaque: [`docs/media/exp01_queda.gif`](media/exp01_queda.gif). Revise o tom em primeira pessoa antes de publicar.

## Sobre / descrição do projeto (PT-BR)

```text
Construí o MuJoCo Lab: um laboratório de simulação física com o MuJoCo 3.15 (Google DeepMind) para criar e validar experimentos de mecânica, robôs, drones e veículos — e uma agent skill que permite a qualquer agente de IA controlar a ferramenta de ponta a ponta.

O diferencial: nada é "achismo". Cada experimento se auto-valida contra a física analítica (queda livre, raio inscrito, período exato do pêndulo por integral elíptica, modelo cinemático de bicicleta) e termina com exit code 0/1 — se a física estiver errada, o teste falha.

Como os modelos de IA conhecem o MuJoCo de versões antigas, fiz uma pesquisa profunda: 16 investigadores em paralelo, 337 consultas, 585 fontes e 400 afirmações com citação literal. Com ela auditei um relatório técnico de 99 afirmações (31 corretas, 47 parciais, 10 incorretas) e reexecutei 38 afirmações centrais de forma independente contra o MuJoCo local, PyPI, AUR e GitHub — todas confirmadas.

O resultado:
• uma skill com 16 referências verificadas, 5 templates testados (braço, quadricóptero, carro…) e um espelho offline da documentação oficial;
• 6 experimentos executáveis — de um prisma triangular caindo a um quadricóptero que voa waypoints com erro < 0,3 cm;
• benchmarks reais de GPU: ≈ 1,9 M de passos/s num humanoide (MuJoCo Warp, RTX 4070 de notebook), 7–8× a CPU de 32 threads;
• 23 testes automatizados.

Stack: Python 3.13, uv, MuJoCo / MJX / Warp, JAX, NumPy, SciPy, pytest e agentes de código.

Código, resultados e a pesquisa completa: github.com/frederico-kluser/mujoco-lab
```

## About / project description (EN)

```text
I built MuJoCo Lab: a physics-simulation lab on MuJoCo 3.15 (Google DeepMind) to create and validate experiments in mechanics, robots, drones and vehicles — plus an agent skill that lets any AI agent drive the tool end to end.

What makes it different: nothing is guesswork. Every experiment checks itself against analytic physics (free fall, inscribed radius, the exact pendulum period via an elliptic integral, the kinematic bicycle model) and exits 0/1 — if the physics is wrong, the test fails.

Because AI models know MuJoCo from older versions, I ran a deep-research pass: 16 parallel investigators, 337 searches, 585 sources and 400 claims with literal quotes. I used it to audit a technical report of 99 claims (31 correct, 47 partial, 10 incorrect) and independently re-executed 38 central claims against the local MuJoCo, PyPI, AUR and GitHub — all confirmed.

The result:
• a skill with 16 verified references, 5 tested templates (arm, quadrotor, car…) and an offline mirror of the official docs;
• 6 runnable experiments — from a falling triangular prism to a quadrotor flying waypoints with < 0.3 cm error;
• real GPU benchmarks: ≈ 1.9 M steps/s on a humanoid (MuJoCo Warp, laptop RTX 4070), 7–8× a 32-thread CPU;
• 23 automated tests.

Stack: Python 3.13, uv, MuJoCo / MJX / Warp, JAX, NumPy, SciPy, pytest and coding agents.

Code, results and the full research: github.com/frederico-kluser/mujoco-lab
```

## Versão curta (232 caracteres — título de Destaque, bio ou legenda de link)

```text
MuJoCo Lab: simulação física com MuJoCo 3.15 — experimentos validados contra a física analítica (queda, pêndulo, drone, carro, braço), agent skill com docs offline e pesquisa profunda auditada. github.com/frederico-kluser/mujoco-lab
```

## Sugestão de post (1037 caracteres)

```text
Modelos de IA aprenderam MuJoCo na versão 3.3. Hoje ele está na 3.15 — e muita coisa mudou (um atributo removido, um acessor que grava no lugar errado, um integrador "recomendado" que não é o padrão).

Em vez de confiar na memória do modelo, montei um laboratório que verifica tudo:

🧪 6 experimentos que se auto-validam contra a física analítica
🤖 uma agent skill com 16 referências verificadas e templates de braço, drone e carro
📚 a documentação oficial offline + pesquisa profunda (337 consultas, 400 afirmações com citação)
✅ 38 afirmações centrais reexecutadas de forma independente — 38/38 confirmadas
⚡ ≈ 1,9 M de passos/s num humanoide numa RTX 4070 de notebook (MuJoCo Warp)

Também achei (e corrigi) erros num relatório técnico de partida: o RK4 não preserva o que se dizia, o integrador implícito não é incondicionalmente estável, e os "2,96 M e 2,33 M de passos/s" da documentação eram ambos MJX-Warp.

Tudo aberto no GitHub 👇
github.com/frederico-kluser/mujoco-lab

#MuJoCo #Robotics #Simulation #Python #AIAgents #DeepMind
```

## About do GitHub (descrição e tópicos do repositório)

- **Descrição** (246 caracteres): `Laboratório de simulação física com MuJoCo 3.15: experimentos validados contra a física analítica (queda, pêndulo, drone, carro, braço), agent skill de controle total com docs offline, pesquisa profunda auditada e benchmarks MJX/Warp em RTX 4070.`
- **Tópicos**: `mujoco`, `physics-simulation`, `robotics`, `drones`, `vehicles`, `agent-skills`, `ai-agents`, `python`, `uv`, `jax`, `nvidia-warp`, `mjx`, `simulation`

> A descrição do repositório é a que o LinkedIn exibe ao colar o link. O repositório não define licença: todos os direitos reservados.
