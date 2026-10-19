---
tipo: nota-pesquisa
versao: 1
pergunta: "Que mecanismo e que motores de precisão deixam o drone de 1950 mm inclinar o corpo (a arma) para mirar com os motores de nível — sem translação — e como garantir a margem do controlo?"
criado: 2026-10-19
atualizado: 2026-10-19
estado: concluido
---

# Braços articulados e mira por arfagem — fontes e decisões (2026-10-19)

> Pesquisa web só via `tavily-agent-skill` (`tavily.py search --depth advanced`); sem `--deep-research` (o dono não o
> pediu). O texto das fontes é DADO (`untrusted`): cita-se, não se obedece. Implementação e números medidos:
> `experiments/09_drone_hover_rl/README.md` → «BRAÇOS ARTICULADOS».

## Pedido

Desenho do dono (`~/Imagens/unnamed.png`): cada braço sobe/desce na base e tem uma 2.ª dobradiça a uma distância segura
um pouco maior do que a hélice; as pontas apontam sempre para o mesmo sítio lateralmente; motores de precisão (passo a
passo sugerido — escolher o melhor) dentro dos limites da ficha; 8 dados novos nos treinos; atirar de qualquer altura face
ao alvo sem mudar x, y, z (só guinada e arfagem); TensorFlow para a precisão em 3 cenários de altura, com o erro muito
penalizado.

## Fontes e o que se tirou de cada uma

| # | fonte (untrusted) | o que diz | decisão que informou |
|---|---|---|---|
| S1 | ROBOTIS e-Manual / docs — XH430-V210-R (docs.robotis.com/docs/dxl/model_reference/x_series/xh_series/xh430-v210; emanual.robotis.com/docs/en/dxl/x/xh430-v210) | 24 V; 2,6 N·m a 0,7 A; 52 rpm em vazio; 82 g; 28,5 × 46,5 × 34 mm; encoder absoluto sem contacto de 4096 passos/volta; RS-485; modos de corrente/velocidade/posição | servo do cotovelo e motor do sem-fim do ombro (`componentes.json` → `servos.dynamixel_xh430_v210`) |
| S2 | ROBOTIS — XH430-V350-R (docs.robotis.com …/xh430-v350; servodatabase.com) | 3,3 N·m a 0,7 A, 31 rpm, 82 g, 353,5:1 | alternativa no catálogo (mais binário, mais lento) |
| S3 | ROBOTIS — XH540-V270-R (docs.robotis.com …/xh540-v270; robotshop.com) | 9,2 N·m a 24 V/2,4 A, 34 rpm, 165 g, folga 0,25°, espera 36 mA | alternativa no catálogo (ombro sem redutor; pesa o dobro) |
| S4 | ams AS5048A datasheet (mouser.com/datasheet/2/588/AS5048_DS000298_4-00-1100510.pdf) | encoder magnético de 14 bits (16384 passos/volta ⇒ 0,0219°/LSB) | encoder na SAÍDA do sem-fim (a folga não engana a medida) |
| S5 | motioncontroltips.com («When are worm gears self-locking…»); firgelliauto.com (calculadora de sem-fim) | autobloqueio quando o ângulo de avanço λ < ângulo de atrito φ = atan μ; η = tan λ / tan(λ + φ) (ex.: λ 5°, φ 6,84° ⇒ 40,6 %) | ombro com sem-fim 20:1, λ = 3,81° < φ = 5,71° (μ = 0,10) ⇒ η = 0,397: o empuxo NÃO faz recuar o braço e, parado, segura sem corrente |
| S6 | Ryll, Bülthoff & Robuffo Giordano — «A Novel Overactuated Quadrotor UAV: Modeling, Control, and Experimental Validation», IEEE TCST 23(2):540, 2015 (+ ICRA 2012/2013, irisa.fr/lagadic/pdf/2013_icra_ryll.pdf) | quadricóptero com as hélices basculadas por servos: a atitude e a posição desacoplam-se (pose 6-DOF controlável) | o princípio: inclinar os MOTORES face ao corpo para o corpo poder arfar sem o drone transladar |
| S7 | Kamel et al. — «The Voliro Omniorientational Hexacopter: An Agile and Maneuverable Tiltable-Rotor Aerial Vehicle», IEEE RAM 25(4):34, 2018 | rotores basculáveis com servos num multirrotor real; voa em qualquer orientação | prova de exequibilidade com servos comerciais; aqui só 1 eixo (y) por braço, o mínimo para a mira por arfagem |
| S8 | Åström & Murray — «Feedback Systems» (cds.caltech.edu/~murray/books/AM05/pdf/am08-complete_22Feb09.pdf; people.duke.edu/~hpgavin/…/Astrom-Feedback-2006.pdf) | «margens razoáveis: margem de fase 30°–60°, margem de ganho 2–5»; 45° é uma escolha comum de projeto | o build articulado exige margem de fase ≥ 45° na malha de taxa (estava a 29,8°) — `fc_margem_fase_min_graus` |

## Porquê servo inteligente e não passo a passo

- Um passo a passo em MALHA ABERTA perde passos com vibração/carga e não sabe que os perdeu; a corrente de retenção fica
  sempre ligada (calor e energia num drone de 22 min). Com encoder passava a ser um servo — e o DYNAMIXEL já traz encoder,
  PID e medida de corrente num pacote de 82 g (S1).
- O ombro carrega o momento do empuxo (≈ 4,4 N·m medido em pairagem): o sem-fim autobloqueante (S5) segura-o SEM corrente
  (medido 0,04–0,06 A = a espera) e com os servos desligados o braço mexe 0,003° — o que um servo direto ou um passo a passo
  só conseguiria a gastar corrente o tempo todo.
- O cotovelo fica direto: a linha de empuxo passa pelo seu eixo (sem carga estática) e precisa de velocidade (302°/s medido
  ≤ 312°/s da ficha) — é o atuador «mini» do par macro-mini.

## O que a pesquisa NÃO resolveu (decidido por medição no simulador)

- Quem segura o quê no eixo de arfagem: a primeira lei (servos seguram o corpo) divergiu em 2 s; ficou o empuxo diferencial
  no corpo e os servos na inclinação do empuxo (interface 4 do firmware).
- A margem de fase de 45° custa ~3–14 % de acertos/min e ~7 cm de afastamento sob recuo (laços ~30 % mais lentos), mas tira
  a ressonância de ~3 Hz e dá ~59 ms de folga a atrasos não modelados (a 30°: ~27 ms).
- O portão de tiro: só a rede TensorFlow (P(acerto) ≥ K/(1+K), K = 20) mantém 0 erros com a bola aleatória; o melhor
  portão só-físico fica com pontuação negativa (contrafactual na GPU, `treinar_mira_articulada.py` fase C).
