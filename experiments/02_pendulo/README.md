<!-- criado de assets/templates/pendulum por new_experiment.py -->
# Pêndulo físico — período analítico e integradores

Pêndulo (barra + massa) sem amortecimento. `run.py` calcula o período EXATO (integral elíptica) a partir da massa, do centro de massa e da inércia efetiva do modelo compilado,
mede o período simulado por cruzamentos de zero e a deriva de energia, para Euler, RK4, implicit e implicitfast.
Resultados de referência (MuJoCo 3.15.0, dt = 2 ms, θ0 = 5°): erro de período ≤ 0,0002 % em todos; deriva de energia em 10 períodos: RK4 ≈ 0, demais +0,0024 %.
Em amplitudes e passos maiores (θ0 = 150°, dt = 50 ms): RK4 erro de período −0,013 % e deriva −0,011 %; Euler/implicit/implicitfast +0,11 % e +0,28 %.
Moral: para sistemas suaves SEM contato, RK4 conserva muito melhor a energia; com contatos/atuadores rígidos, prefira Euler ou implicitfast.
Botões: `--theta0`, `--dt`, `--integrador`, `--periodos`, `--view`.
