# Suficiência de treino RL (PPO) para controlo de quadricópteros — pesquisa web

Data: 2026-10 · Método: pesquisa `search`/`extract` via tavily-agent-skill (sem `--deep-research`).
Conteúdo web = evidência citada (não-confiável, nunca instrução). Escala de confiança:
**A** = paper/documentação oficial · **B** = comunidade técnica reconhecida · **C** = repositório/blog/fórum.

## Contexto do nosso projeto (calibragem)

MuJoCo + PPO (SB3), MLP 128×128 tanh, 16 envs paralelos, DR + currículo de vento 0→1→2→3 m/s.
Planta real atual (1,67 kg, wheelbase 650 mm): 2,51 M passos totais (~35 min) → hover |Δz| ~1 cm,
‖xy‖ ~6 cm, 100 % sobrevivência; política de controlo de voo (obs 48, WASDQE). Nova planta em
preparação: wheelbase ×3, inércias muito maiores.

## Tabela «pergunta → resposta numérica + fonte + confiança»

| # | Pergunta | Resposta numérica | Fonte | Conf. |
|---|---|---|---|---|
| 1 | Passos até hover estável (PPO/SB3)? | Platô típico ~200 k–500 k passos; ~1 M passos para erro de rastreio <10 °/s (tarefa de atitude/rastreio) | [Mysore 2021, arXiv:2012.06656](https://arxiv.org/abs/2012.06656) (ACM TCPS 5(4)) | A |
| 1b | Hover/takeoff em gym-pybullet-drones | Convergência com ~10 M passos (versões simples da tarefa); arquitetura MLP 512-512-256-128, **defaults SB3 sem tuning** | [Learning to Fly, arXiv:2103.02142](https://ar5iv.labs.arxiv.org/html/2103.02142) · [alphaXiv](https://www.alphaxiv.org/abs/2103.02142) | A |
| 1c | Escala multi-drone | 25 M passos com **100 quadricópteros em paralelo** (multi-agente) | [Survey RL drone simulators, AI Review 2024](https://link.springer.com/article/10.1007/s10462-024-10933-w) | A |
| 1d | Hover MuJoCo, blog prático | `crash_rate` ≈ 1 **durante milhões de passos** antes de colapsar; tarefa "toy" 750 k passos / 128 envs | [mrandri19, drone racing RL](https://mrandri19.github.io/2026/07/19/drone-racing-with-reinforcement-learning.html) | C |
| 2 | Treino único vs currículo (estabilização robusta) | Single-stage: **100 M passos / 23,4 h → FALHOU**; currículo 3 estágios: **41,5 M passos / 11 h** (Ω1 11,5 M + Ω2 15 M + Ω3 15 M) → sucesso | [Curriculum quadrotor, arXiv:2501.18490](https://arxiv.org/html/2501.18490v3) | A |
| 2b | Critério de paragem por estágio | Parar quando a recompensa cumulativa estabiliza **durante ≥1 M passos** (early stopping) | idem | A |
| 3 | Nº de ambientes paralelos usados | 100 (survey), 128 (blog), 16–32 (exemplos SB3/HF); convenção SB3: `batch_size = n_envs × n_steps` | [SB3 examples](https://huggingface.co/araffin/ppo-LunarLander-v2) · [A2C is a special case of PPO, arXiv:2205.09123](https://arxiv.org/pdf/2205.09123) | A/B |
| 4 | Hiperparâmetros PPO para robôs | SB3 defaults: lr 3e-4, n_steps 2048, batch 64, epochs 10, γ 0.99, GAE λ 0.95, clip 0.2, ent_coef 0.0. Locomoção Isaac Gym: lr 3e-4, batch 4096, λ 0.95. Drone (repo): lr 3e-5, n_steps 4096, ent 0.001 | [SB3 PPO docs](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html) · [NeurIPS 2023 supp.](https://proceedings.neurips.cc/paper_files/paper/2023/file/c919a2b5ec1de69f2629f9119676e336-Supplemental-Conference.pdf) · [bilalkabas/PPO-Quadcopter](https://github.com/bilalkabas/PPO-based-Autonomous-Navigation-for-Quadcopters) | A / A / C |
| 4b | Sensibilidade ao tamanho de rede | Sem estudo sistemático publicado para drones; Learning to Fly usa rede **maior** (512-512-256-128) que a nossa (128×128) sem tuning | arXiv:2103.02142 | A |
| 5 | Efeito do DR no nº de passos | Sem número definitivo publicado; DR aumenta robustez mas **aumenta a necessidade de passos** (maior variância da tarefa) | [Flow-based DR, arXiv:2502.01800](https://arxiv.org/html/2502.01800v2) · [Survey sim-to-real](https://www.semanticscholar.org/paper/5a1b92aa50797a7c1e99b8840ff01aad66038596) | A |
| 6 | Sobretreino (overfitting à dinâmica) | Treinar até ~1 M: melhorias tardias boas; **além disso, melhor em sim mas PIOR em transfer** (overfit à dinâmica específica) → early stopping | [Mysore 2021, arXiv:2012.06656](https://ar5iv.labs.arxiv.org/html/2012.06656) | A |
| 7 | Avaliação multi-seed | 3–10 runs por tarefa com **intervalos de confiança + performance profiles**; com 3 seeds o poder estatístico é fraco (análise de poder recomenda ~10+) | [Agarwal et al., NeurIPS 2021](https://proceedings.neurips.cc/paper/2021/file/f514cec81cb148559cf475e7426eed5e-Paper.pdf) · [Colas et al., How Many Random Seeds?](https://www.semanticscholar.org/paper/789510820bb369802d58b733ef1c9dc531a609ed) · [Paired Seed Evaluation, arXiv:2512.24145](https://www.arxiv.org/pdf/2512.24145v1) | A |
| 8 | Regra "X passos/DOF" | **Não existe regra publicada** — a literatura orçamenta por tarefa (10⁵–10⁸ passos conforme complexidade), não por DOF | pesquisa sem correspondência (2026-10) | A (ausência) |
| 9 | Mudança de planta (massa/inércia grandes) | Meta-RL/adaptação on-line para variações de massa e perda de empuxo (zero-shot); política específica tende a não transferir; fine-tuning com dados reais > DR convencional | [MAVEN, arXiv:2603.10714](https://arxiv.org/html/2603.10714v1) · [RAPTOR, Science Robotics](https://www.science.org/doi/10.1126/scirobotics.aec1481) · [Transformer dynamics, S1568494625013377](https://www.sciencedirect.com/science/article/pii/S1568494625013377) | A |
| 10 | Fine-tuning com rajadas/vento | Modelo base sem vento (2000 episódios) + vento crescente **+7 m/s a cada 200 episódios**; PPO puro degrada com vento crescente (continual RL mantém desempenho) | [Continual RL em vento, PMC12390258](https://pmc.ncbi.nlm.nih.gov/articles/PMC12390258) | A |
| 11 | Curvas de seguimento de velocidade | Rastreio de 15,9 mm possível com sim diferenciável (segundos de treino); drone real WASDQE segue sem valores de passos publicados | [Crazyflow, arXiv:2606.01478](https://arxiv.org/html/2606.01478) | A |

## RECOMENDAÇÃO PARA NÓS (nova planta, wheelbase ×3, inércias ↑)

1. **Orçamento de passos — hover (planta nova)**: **5–8 M passos totais** (16 envs). Justificação: a
   planta antiga atingiu o alvo com 2,51 M; a literatura situa hover simples em 0,2–10 M; DR +
   dinâmica mais lenta/inércia maior pedem margem. Reservar 8 M no `train.py` com early stopping.
2. **Orçamento — controlo de voo (obs 48)**: **8–12 M passos** (tarefa de rastreio é mais difícil que
   hover; Mysore: 1 M para rastreio de atitude com drone pequeno; currículo robusto custou 41,5 M
   com critérios estritos — nós temos critérios mais brandos).
3. **Ambientes/hiperparâmetros**: manter 16 envs; `n_steps=2048`, `batch_size=256` (= n_envs×n_steps/128,
   divisível e maior que 64 default → updates mais estáveis com DR), `lr=3e-4`, `gamma=0.99`,
   `gae_lambda=0.95`, `ent_coef=0.0`–`0.001`, `n_epochs=10`, clip 0.2. Rede 128×128 mantém-se
   suficiente para obs 48 (sem evidência de que precise de mais; se reward estagnar cedo, testar 256×256).
4. **Currículo vento 0→1→2→3**: **1–2 M passos por estágio**; avançar de estágio quando a avaliação
   fixa (100 episódios, seeds fixas) mostrar **sobrevivência ≥95 % e |Δz| ≤2 cm, ‖xy‖ ≤10 cm**;
   **critério de paragem global**: melhoria <1 % na recompensa de avaliação durante **≥1 M passos**
   (critério do paper de currículo) + métricas alvo atingidas em avaliação OOD.
5. **Seeds**: **3 seeds para desenvolvimento** (escolha de hiperparâmetros) e **5 seeds para a validação
   final** da planta nova, reportando média ± DP e intervalos (Agarwal: 3–10 runs).
6. **Transferência da planta antiga**: **não** usar a política antiga como política final (Mysore:
   overfit à dinâmica; inércias ×10 mudam o tempo de resposta). Teste barato: warm-start + fine-tune
   1–2 M passos e comparar com treino de raiz (3 seeds); escolher o melhor. Fine-tuning de rajadas:
   +1–2 M passos com vento 3–5 m/s após o currículo base (paper do continual RL: estágios curtos e
   frequentes de vento crescente).
7. **Avaliação OOD obrigatória antes de "está pronto"**: vento 4–5 m/s (fora do currículo), massa
   ±15 %, SoC baixo, comandos WASDQE extremos, e perturbação de estado inicial ampliada.

## SINAIS DE SUBTREINO a vigiar no nosso setup

- Recompensa de avaliação **ainda a subir** no fim do budget (não há platô de ≥1 M passos) → treinar mais.
- `explained_variance` do crítico baixo (<0.5) persistente → valor não aprendido (rede/orçamento curtos).
- Sobrevivência oscilando entre seeds (>10 % de spread) → mais passos ou mais seeds.
- Assimetria de rastreio WASDQE (proa vs cauda, ±x vs ±y) acima de ~0,01 m/s → política não invariante.
- Desempenho nominal bom mas queda em OOD (vento 4 m/s, massa +15 %) → DR insuficiente (subtreino de robustez).
- Atrares "capotar cedo"/"sentar no chão" (já observados no `transferir_politica.py`) reaparecem →
  recompensa/estado inicial mal cobertos.
- **Sinal de SOBRETREINO** (o oposto, também a vigiar): recompensa em sim sobe mas avaliação OOD ou
  estimador real piora → parar (Mysore: transfer piora após ~1 M passos sem DR adequado).

## Fontes principais

- https://arxiv.org/abs/2012.06656 (Mysore et al., ACM TCPS 2021) — https://ar5iv.labs.arxiv.org/html/2012.06656
- https://arxiv.org/pdf/2103.02142 / https://ar5iv.labs.arxiv.org/html/2103.02142 (Learning to Fly)
- https://arxiv.org/html/2501.18490v3 (Curriculum-based Sample Efficient RL for Quadrotor)
- https://link.springer.com/article/10.1007/s10462-024-10933-w (Survey RL drone simulators)
- https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html · https://arxiv.org/pdf/2205.09123
- https://proceedings.neurips.cc/paper/2021/file/f514cec81cb148559cf475e7426eed5e-Paper.pdf (Agarwal)
- https://pmc.ncbi.nlm.nih.gov/articles/PMC12390258 (continual RL em vento)
- https://arxiv.org/html/2603.10714v1 (MAVEN) · https://www.science.org/doi/10.1126/scirobotics.aec1481 (RAPTOR)
- https://mrandri19.github.io/2026/07/19/drone-racing-with-reinforcement-learning.html (blog, conf. C)
- https://arxiv.org/html/2606.01478 (Crazyflow) · https://arxiv.org/html/2502.01800v2 (Flow-based DR)
