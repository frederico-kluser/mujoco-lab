<!-- criado de assets/templates/car por new_experiment.py -->
# Carro de 4 rodas — Ackermann, tração traseira e comparação com o modelo de bicicleta

Carro de 2,74 kg (entre-eixos 0,30 m, bitola 0,22 m, roda r = 0,05 m): tração por 2 motores de torque nas rodas traseiras (PI de velocidade), direção Ackermann por 2 servos `<position>` (`inheritrange="1"`),
pneus `friction="1.0 0.02 0.005"`, `condim="4"`, cone elíptico (`impratio=10`). `run.py` acelera a 1,5 m/s, faz uma curva à esquerda, uma à direita (δ de bicicleta = 20°) e freia.
Previsão cinemática: R = L/tanδ = 0,82 m, taxa de guinada ψ̇ = v·tanδ/L, deriva do CG β = atan(½·tanδ) ≈ 10,3°.
Resultados medidos (MuJoCo 3.15.0, implicitfast, dt 2 ms):

| Cenário | ψ̇ simulado × bicicleta | Observação |
| --- | --- | --- |
| μ = 1,0 · v = 1,5 m/s · δ = 20° (padrão) | +1,705 × +1,819 rad/s (Δ 6,3%) | subesterço leve; β = 9,2° (cinemático 10,3°) |
| μ = 1,0 · v = 2,5 m/s · δ = 15° | +2,013 × +2,233 rad/s (Δ 9,8%) | mais velocidade → mais subesterço |
| μ = 0,5 · v = 1,5 m/s · δ = 20° | +1,459 × +1,819 rad/s (Δ 19,8%) | aderência no limite: falha as checagens (esperado) |
| μ = 0,35 · v = 2,0 m/s · δ = 20° | +0,807 × +2,429 rad/s (Δ 67%), inclinação 16° | derrapagem: o carro sai de frente |

Botões: `--vel`, `--delta`, `--atrito`, `--camera`, `--view`. Limites: não existe modelo de pneu tipo Pacejka nem plugin em 3.15.0; a força lateral depende da velocidade de deslizamento, não do ângulo de deriva;
sem suspensão (o "amortecimento" é o contato macio). Ver `references/vehicles.md`.
