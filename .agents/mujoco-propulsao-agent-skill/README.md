# mujoco-propulsao-agent-skill

Skill de TAREFA do mujoco-lab: **criar objetos novos com motores, propulsão e dinâmica explosiva e
integrá-los em todos os locais do sistema** (modelo MJCF → camada `lab/` → experimento → sistema de
controlos/teclas/site → Raspberry Pi 5/Arduino). Companheira da skill de memória
`mujoco-lab-coala-agent-skill` (continua a ser a entrada para contexto e o destino para `add`).

- **Entrada**: `SKILL.md` (roteiro + regras de ouro).
- **Template testado**: `assets/templates/objeto-propulsado/` (propulsão multi-eixo + motor + carga
  explosiva com separação; `run.py` valida por fórmulas fechadas, exit 0).
- **Scaffolder**: `scripts/novo_objeto.py <nome>` → `experiments/NN_<nome>/` pronto a adaptar.
- **Referências**: `references/` (motores/propulsão, explosivos/impulso, controlos/teclado, RPi 5).

Verificado em MuJoCo 3.15.0 (2026-10-15): todas as fórmulas do template provadas por execução.
