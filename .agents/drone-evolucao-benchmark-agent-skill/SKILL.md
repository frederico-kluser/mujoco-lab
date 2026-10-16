---
name: drone-evolucao-benchmark-agent-skill
description: Ciclo completo de evolução científica do drone no mujoco-lab — (1) pesquisar algoritmos/IA na internet (via tavily-agent-skill), (2) explicar a lógica física/matemática e onde entra o TensorFlow seletivo, (3) treinar na GPU (RTX 4070 JAX + TensorFlow OpenXLA) com movimento aleatório da bola e rajadas aleatórias, (4) capturar o benchmark determinístico (movimento PROGRAMADO da bola + cenário FIXO de vento) medindo Estabilidade (ω_RMS, jitter, recuperação pós-tiro), Tiros por Minuto (TPM) e Desvio sob Vento Fixo nos 6 presets calibrados, e (5) renderizar `evolucao_drone.png` na raiz e atualizar `README.md`, `AGENTS.md` e `CLAUDE.md`.
---

# drone-evolucao-benchmark-agent-skill — Pesquisa → Explicação → Treino GPU (Aleatório) → Benchmark (Programado/Fixo) → Gráfico e Docs

Esta skill governa toda a evolução de estabilidade, mira balística, visão computacional e presets de propulsão do drone (`experiments/09_drone_hover_rl/`). Garante que **o treino usa aleatoriedade** para generalizar, mas **a medição (benchmark) usa sempre o mesmo cenário programado da bola e o mesmo cenário fixo de vento**, atualizando o gráfico `evolucao_drone.png` na raiz do projeto e as tabelas em `README.md`, `AGENTS.md` e `CLAUDE.md`.

## Quando usar

- Sempre que o utilizador pedir para **melhorar a estabilidade, mira, seguimento da bola, recuperação pós-tiro, visão computacional ou presets de motores/bateria** do drone.
- Sempre que pedir para **acompanhar a evolução**, **medir tiros por minuto (TPM)**, **rodar o benchmark de bola programada / vento fixo** ou **atualizar o gráfico `evolucao_drone.png`**.

## O Protocolo de 5 Passos (Obrigatório em Cada Evolução)

### 1. Pesquisar na Internet (`tavily-agent-skill`)
Antes de alterar controladores ou redes neurais, pesquise na literatura (IEEE, *Science Robotics*, *RSS*, *MDPI Drones/Actuators*, documentação PX4/ArduPilot/Betaflight):
```bash
python3 .agents/drone-evolucao-benchmark-agent-skill/scripts/evoluir_e_benchmark.py --pesquisar "<tema técnico da melhoria>"
```
(Usa `tavily.py search --depth advanced`; se o utilizador pedir `--deep-research`, siga o protocolo de dossiê em `pesquisas/`).

### 2. Explicar a Lógica Física e o Papel Seletivo do TensorFlow
Documente claramente:
- **O que é resolvido por Física e Geometria Analítica** (cinemática de corpo rígido, filtro complementar Mahony, alocação BEMT $u_{\text{pairagem}}(V_{\text{bus}}, m)$, balística parabólica $z_{\text{boca}} - \frac{1}{2}g\tau_{\text{voo}}^2$, e *Control Barrier Function* de altitude $z \ge 0,72\text{ m}$);
- **Onde entra o TensorFlow (`@tf.function(jit_compile=True)` OpenXLA)** — **apenas** onde há resíduo não-linear ou acoplamento multi-preset:
  1. `CompensadorEstabilidadeTF` (`mlp_recuo_tf`, `8 → 24 → 24 → 1`): adapta o ganho de amortecimento ativo de recuo a $500\text{ Hz}$ ao KV, $R_{\text{int}}$, $V_{\text{bus}}$ e massa;
  2. `VisaoBalisticaTF` (`mlp_visao_tf`, `8 → 24 → 24 → 3`): prediz o resíduo de aceleração não-estacionária da bola no horizonte $t + \tau_{\text{voo}}$;
  3. `RedeDistanciaEstavelTF` (`mlp_standoff_tf`, `6 → 24 → 24 → 1`): calcula o recuo automático de distância segura $D^*(v_{\text{bola}}, a_{\text{bola}})$ quando a bola é rápida, permitindo acompanhar por rotação no eixo em vez de translações laterais bruscas.

### 3. Treinar em GPU + TensorFlow XLA com Cenário Aleatório
O treino corre **sem renderização 3D** na RTX 4070 (`CudaDevice(id=0)`) com **movimento aleatório da bola (Ornstein–Uhlenbeck)** e **perturbações estocásticas**:
```bash
.venv-gpu/bin/python experiments/09_drone_hover_rl/treinar_mira_gpu.py
```

### 4. Capturar os Dados em Cenário Determinístico (Bola Programada + Vento Fixo)
A avaliação **nunca** usa sorteio livre sem cenário fixo:
- **Bola Programada (`modo="programado"`)**: trajetória Lissajous 3D analítica determinística ($v = 0,55\text{ m/s}, r = 1,35\text{ m}, 15,0\text{ s}$) com `AUTO SHOOT` ativo → mede **Tiros Certeiros por Minuto (TPM)**, `% Acerto` e `Inclinação Máxima (°)`;
- **Vento Fixo Determinístico**: Fase A ($0\text{ m/s}$ ar calmo: $\omega_{\text{RMS}}$, *jitter* e recuperação pós-tiro em $\text{s}$) $\to$ Fase B ($3,0\text{ m/s} @ 90^\circ$) $\to$ Fase C ($5,0\text{ m/s} @ 45^\circ$).
```bash
.venv/bin/python experiments/09_drone_hover_rl/benchmark_evolucao.py
```

### 5. Atualizar `evolucao_drone.png`, `README.md`, `AGENTS.md`, `CLAUDE.md` e CoALA
- O script grava `/home/ondokai/Projects/MuJoCo/evolucao_drone.png` (gráfico de 4 painéis na raiz) e `experiments/09_drone_hover_rl/out/evolucao/evolucao_estabilidade.json`.
- Inspecione sempre `evolucao_drone.png` com `read_image`.
- Atualize as tabelas de evolução em `README.md` (raiz e experimento), `AGENTS.md` e `CLAUDE.md`, e registe na memória CoALA (`coala.py add`).

## Comandos Rápidos do Script da Skill

```bash
# Verificar estado atual do benchmark, JSON e imagem na raiz + imprimir tabela Markdown:
.venv/bin/python .agents/drone-evolucao-benchmark-agent-skill/scripts/evoluir_e_benchmark.py --check

# Executar ciclo completo (Pesquisa opcional + Treino GPU + Benchmark Determinístico + Gráfico):
.venv/bin/python .agents/drone-evolucao-benchmark-agent-skill/scripts/evoluir_e_benchmark.py --ciclo-completo
```
