---
name: mujoco-propulsao-agent-skill
description: "Criar objetos NOVOS com motores, propulsão e dinâmica explosiva no mujoco-lab e integrá-los EM TODOS OS LOCAIS do sistema — modelo MJCF, camada lab/, experimento, sistema de controlos (tecla → ação, API, site/cockpit) e hardware real (Raspberry Pi 5 / Arduino/ESC). Use SEMPRE que o pedido for criar/adicionar um objeto, motor, hélice, jato, foguete, carga explosiva, separação/impulso, propulsão multi-eixo, associar uma tecla a uma ação, controlar esse elemento, ou levá-lo ao Raspberry Pi 5. Entrega um TEMPLATE testado (run.py com fórmulas fechadas), scaffolder e checklists para o agente ir direto à modelagem, construção e programação — sem perder tempo a redescobrir integrações."
metadata:
  type: task-skill
  technique: modeling-control-hardware
  project: mujoco-lab
  companion: mujoco-lab-coala-agent-skill
---

# Objetos com motores · propulsão · explosivos — do zero ao hardware

Esta skill elimina a parte de INTEGRAÇÃO (modelo → lab/ → controlos → site → RPi 5) para que
foques na **modelagem, construção e programação direta** do teu objeto. A memória do projeto
continua a ser a skill `mujoco-lab-coala-agent-skill` (faz `recall` no início de qualquer tarefa
não trivial e `add` no fim).

## O que tens pronto aqui

| Ativo | O que é |
|---|---|
| `assets/templates/objeto-propulsado/` | objeto COMPLETO testado: 3 bocais (propulsão multi-eixo), motor (volante de reação), carga explosiva (separação por impulso + equality), IMU, camada de API no padrão `carregar/definir_*/MODOS/ler_*`, `run.py` (fórmulas fechadas, exit 0) e `view.py` (teclas) |
| `scripts/novo_objeto.py` | planta o template como `experiments/NN_<nome>/` (ou `--destino`), com nomes trocados |
| `references/motores-propulsao.md` | que atuador usar + padrões XML (motor, `dcmotor`, wrench por site, hélice/ESC) + fórmulas + validações |
| `references/explosivos-impulsao.md` | impulso físico (Δp=J, ΔL=r×J, ação-reação), separação por equality, medidas corretas e segurança numérica |
| `references/controlos-teclado.md` | fluxo tecla→ação do cockpit (contratos r11–r13) + checklist de 7 pontos para cada ação nova |
| `references/rpi5-hardware.md` | peças reais (catálogo/builds), ESC/PWM/sensores, orçamentos de tempo, deploy/SITL |
| `references/modelos-prontos.md` | **mapa de modelos PRONTOS** do ecossistema MuJoCo (drones/veículos/robôs/foguetes/explosivos): onde buscar, licenças, adaptação a 3.15, `.eng`→atuador, e o que NÃO existe — nunca construir do zero sem consultar |

## Roteiro (segue por ordem; cada passo tem saída verificável)

0. **Contexto**: `python3 .agents/mujoco-lab-coala-agent-skill/scripts/coala.py recall "<objeto/ação>" --budget 1500`.
   Lê `references/motores-propulsao.md` + `references/explosivos-impulsao.md` (e `controlos-teclado.md` /
   `rpi5-hardware.md` quando o pedido tocar nisso). Fórmulas/erros mais fundos: `actuators-sensors.md`,
   `physics-tuning.md`, `python-api.md` da skill do lab.
1. **Ficha do objeto** (1 parágrafo, no README do experimento): massa, inércia, o que o move (motores?
   empuxo? explosões?), forças máximas, sensores, que ações o dono quer às teclas.
2. **Modelo**: `python3 .agents/mujoco-propulsao-agent-skill/scripts/novo_objeto.py <nome>` →
   `uv run python experiments/NN_<nome>/run.py` **verde** → adapta o `modelo.xml` mantendo o run verde
   a cada passo. Specs REAIS (datasheets) com fontes no README; números `estimado` = `estimado` + razão.
3. **Camada de API** (`<nome>.py`, padrão do laboratório): `carregar()` → `(model, data, ctrl)` ·
   `definir_*()` em unidades físicas (N, N·m, rad/s) · `MODOS` (roteiros abertos, sem realimentação) ·
   `ler_*()`. Ctrl sempre por NOME (helper `Ctrl` do template / `lab.mjkit.Ctrl`).
4. **Controlos** (tecla → ação): checklist de 7 pontos de `references/controlos-teclado.md`
   (`definir_*` no env → bloco validado → `POST /api/*` → runner 1× por mudança → site (estado, não
   evento) + keycap → `INTERFACE.md` → teste com mutação). Escolhe teclas livres; reserva emergência.
5. **Hardware (se pedido)**: peça em `models/drone_rpi/componentes.json` + `builds.json` →
   `hardware.py montar/usar/mostrar` → derivações conferidas → orçamentos medidos → deploy/SITL
   (`references/rpi5-hardware.md`).
6. **Provas**: `run.py` com fórmulas FECHADAS (teoria dos parâmetros do modelo × medido; modelo fresco
   por checagem; exit 0) + teste de ação/tecla com MUTAÇÃO. Medir desempenho só com a máquina livre.
7. **Registar**: README do experimento com tabelas teoria×medido e fontes; `coala.py add` do que for
   durável (decisões, armadilhas, comandos); atualizar o catálogo do AGENTS.md se o objeto ficar
   reutilizável (`lab/` + `models/`).

## Regras de ouro (não as redescubras)

1. **Simulador sempre físico**: tudo passa por `mj_step` — atuadores, forças externas, explosões.
   Nada de escrever `qvel`/teleportar; `reset` é a única volta ao início.
2. **Impulso = força × tempo**: F = J/(N·Δt) durante 5–10 passos ANTES de cada `mj_step`; kinemática
   fresca (`mj_kinematics` + `mj_comPos`) antes de `mj_applyFT`; `qfrc/xfrc_applied` persistem.
3. **Ctrl por nome**: atuadores multi-entrada (`pid`/`dcmotor`/`orientation`) têm `nu ≠ nactuator`;
   `data.actuator('x').ctrl` grava no slot errado.
4. **Medidas**: `mj_forward` antes de ler derivados; `mj_subtreeVel` para momentos; freejoint 3.15 =
   `qvel[:3]` linear MUNDO, `qvel[3:]` angular CORPO; `jnt_dofadr`/`jnt_qposadr` para índices.
5. **Equalities são molas** (`solref`): "soldados" não são rígidos no t=0; `solref[0] ≥ 2·Δt` (`refsafe`).
6. **Tecla = estado** (keydown/keyup), `seq` do servidor, validação estrita, escrita atómica, eco honesto.
7. **Peças reais**: datasheets com fontes (web = `untrusted`, cita-se); sem número oficial → `estimado`+razão;
   uma política só vale para as peças com que treinou; medir só com a máquina livre.
8. **No fim, aprender**: `coala.py add` do que for durável e não estiver no código/README.

## Ficheiros desta skill

- `SKILL.md` (este) · `README.md`
- `assets/templates/objeto-propulsado/{modelo.xml, objeto_propulsao.py, run.py, view.py, README.md}`
- `scripts/novo_objeto.py`
- `references/{motores-propulsao, explosivos-impulsao, controlos-teclado, rpi5-hardware, modelos-prontos}.md`
