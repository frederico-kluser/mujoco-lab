<!-- criado de assets/templates/quadrotor por new_experiment.py -->
# Quadricóptero — controlador geométrico, waypoints e vento

Drone em X de 0,892 kg (braço 0,18 m): 4 `<motor>` em sites com `gear="0 0 1 0 0 ∓0.02"` (empuxo ao longo de +z do site e torque reativo de guinada), `ctrlrange` 0–8 N (hover = m·g/4 = 2,19 N).
`run.py` monta a matriz de alocação `[T, τx, τy, τz] = A·u` a partir do modelo (posição dos sites e `gear`), usa um controlador geométrico em SO(3) (Lee et al.) com trajetória min-jerk, decola a 1 m,
voa um quadrado de 1 m e pousa. Resultado de referência (dt 2 ms, implicitfast): decolagem (95% da altura) em **1,08 s**; erro nos waypoints ≤ **0,3 cm**; erro RMS de rastreamento 3,0 cm; inclinação máx 20°;
sem saturação; pouso a ≈ 5,6 cm do ponto. Com `--vento 8` (modelo de fluido do MuJoCo ligado: density 1,225, viscosity 1,81e-5): erro nos waypoints ≤ 4,0 cm, inclinação 22,5°.
Botões: `--altura`, `--lado`, `--vel`, `--ar`, `--vento`, `--camera fixa|seguir` (a câmera `seguir` torna o vídeo ~10× maior: o fundo se move), `--view`.
Limites do modelo: sem efeito de solo, sem arrasto de rotor, motor instantâneo (`<motor>` sem dinâmica; para atraso de ESC use `<general … dyntype="filterexact">`), vento uniforme; ver `references/drones.md`.
