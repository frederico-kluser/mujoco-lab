<!-- criado de assets/templates/arm por new_experiment.py -->
# Braço robótico 3 GDL — IK diferencial + servos PD

Braço de 3 juntas (yaw, ombro, cotovelo) com servos `<position>` (kp=400, kv=40, forcerange ±120 N·m), `gravcomp="1"` nos elos e um alvo MOCAP que percorre um círculo (r=0,15 m, T=4 s).
O controle é cartesiano: `v = v_alvo + Kp·(p_alvo − p_ponta)`, `dq = Jᵀ(JJᵀ + λ²I)⁻¹·v·dt` (mínimos quadrados amortecidos), integrado em `q_cmd` → `ctrl` dos servos.
Resultado de referência (MuJoCo 3.15.0, implicitfast, dt 2 ms): erro RMS da ponta após 1 s ≈ **4 mm**; |τ| máx ≈ 1,6 N·m; juntas dentro dos limites; sem NaN.
Botões: `--raio`, `--periodo`, `--tol`, `--view`. Em `model.xml`: `kp/kv/forcerange` (default), `gravcomp`, ranges das juntas.
Armadilhas verificadas: `mj_jacSite` exige `mj_kinematics` + `mj_comPos` (ou `mj_forward`) antes — sem isso o Jacobiano é de uma configuração antiga; com `compiler angle="degree"` o `ctrlrange` do atuador NÃO é convertido
(por isso `inheritrange="1"`); o hinge em Y com ângulo positivo leva +X para −Z (abaixa o braço).
