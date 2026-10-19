---
tipo: nota-pesquisa
versao: 1
pergunta: "Como treinar e melhorar os braços articulados, a mira e o tiro — e que metodologias comparar, com e sem vento, para que a adversidade seja a mesma em todos os treinos (semeada, sem ficar num padrão) e a comparação chegue à perfeição?"
criado: 2026-10-19
atualizado: 2026-10-19
estado: proposta
---

# Treinar e comparar os braços articulados, a mira e o tiro — com e sem vento semeado

**Considerações e ideias: nada disto está implementado.** O documento parte de duas fontes:
- uma leitura do código a 2026-10-19, feita por 5 leitores: mecanismo dos braços, mira e treino TensorFlow, vento e sementes, pilha de treino, resultados medidos;
- uma pesquisa web feita só com a `tavily-agent-skill`, sem `--deep-research`. O conteúdo web é `untrusted` e aparece apenas como citação [Sx].

O pedido do dono tem quatro partes:
1. Como treinar e melhorar mais os braços móveis, o acerto no alvo e o resto.
2. Que metodologias testar e como compará-las até chegar à perfeição.
3. Considerar os modos **com** e **sem** vento.
4. Nos treinos, as variações de vento repetem-se em **todos** os treinos, para a adversidade não ser fator de sorte. Mas mudam muitas vezes, sem ficar num mesmo padrão aleatório, e são geradas por semente.

Convenções:
- **PROPOSTA** marca um ficheiro, função ou campo que ainda não existe.
- «estimativa» marca uma conta ou um juízo meu.
- ‡ marca uma conta sobre a geometria ou sobre um modelo analítico, feita na leitura do código e não medida em voo.
- Os caminhos são relativos a `experiments/09_drone_hover_rl/`, exceto os que começam por `lab/`, `models/`, `pesquisas/` ou `.agents/`.
- «Medido fora do repositório» quer dizer: com scripts de verificação dos leitores, em `$TMPDIR`, que não ficam versionados.

> Processo: o workflow que juntou este material foi parado a pedido do dono antes da verificação adversarial final.
> As afirmações-chave sobre o código foram conferidas à mão (lista na secção 10).

---

## Em resumo

1. **Hoje, a adversidade do treino é sorte.**
   - O vento sai do mesmo `np_random` que a planta consome; a planta fica com 99,4 % dos sorteios (medido fora do repositório).
   - Por isso dois métodos com a mesma semente sentem ventos diferentes. O build rígido e o articulado, com a mesma semente, partilham **0 de 120** passos de vento.
   - A cadeia da mira (dados TF, portão, 3 cenários, validação) **nunca viu vento**.
2. **A proposta central é uma «fita de vento» determinística.**
   - É gerada por um gerador baseado em contador (Philox; `jax.random.fold_in`) com a chave (versão, fita-mestra, família, índice).
   - Troca de regime a cada 1,5–4,5 s: calmo, constante, rajadas 1−cos, Dryden, viragens, correntes verticais, cisalhamento.
   - Sorteia parâmetros novos em cada segmento. É infinita e não tem ciclo.
   - No treino lê-se pelo **tempo de voo** de cada ambiente paralelo, para que as quedas não a desloquem. Na avaliação lê-se por **episódio**.
3. **Todos os métodos treinam e avaliam na MESMA fita** (números aleatórios comuns [S1]).
   - O que se faz variar é a aleatoriedade do algoritmo, com ≥ 5 sementes por método.
   - A conclusão repete-se em 3 fitas-mestras, que funcionam como blocos.
4. **«Sem vento» é a mesma fita com o vento nulo.** A bola, o ruído e a DR ficam iguais bit a bit, por isso a diferença entre os dois modos, calculada aos pares, mede o custo do vento de cada método.
5. **Perfeição é uma ordem pré-registada**: 0 quedas → limite superior da taxa de erros abaixo da meta → cauda (CVaR) da pior célula → média → Pareto (estação, tremor, energia e desgaste dos servos).
   - Hoje cada célula tem ~60 tiros, o que só prova erro ≤ ~5 %. É o próprio ponto de equilíbrio 1/21 do K = 20.
6. **Ordem das metodologias de controlo:**
   - M0 re-medido;
   - M1 (sep-CMA-ES dos parâmetros, como no IBVS);
   - M2 (alocação: vetorização em x a sério, guinada por inclinação diferencial com ~4× de binário‡, INDI/UDE);
   - oráculo MPPI na GPU, para medir o teto;
   - RL residual só onde o clássico falhar;
   - NMPC + destilação só se o oráculo mostrar folga;
   - RL de ponta a ponta como controlo científico.
7. **Decisão de tiro:**
   - calibrar P (temperature scaling), para a regra de Chow ser exata;
   - controlo de risco conformal, para GARANTIR uma taxa de erros;
   - ensemble, para se abster quando o vento põe o estado fora da distribuição;
   - torneio de preditores do alvo.
8. **Mecanismo:**
   - antecipar o recuo pelos cotovelos (o instante do tiro é conhecido);
   - alinhar os envelopes (coplanar 34,14°‡);
   - anti-windup com a saturação dos servos e trim do CM;
   - amortecer o cotovelo;
   - DR do mecanismo e deteção de falhas por braço.
9. **Comparação:**
   - mesmo orçamento para todos, corrida e successive halving;
   - torneio triagem → validação → teste selado, mais ablações;
   - 36 células de experiência;
   - as gerações v6+ entram no benchmark oficial.
10. **Custo nesta máquina** (estimativa a partir de débitos medidos): uma ronda sem RL leva ≈ 2 h; com RL somam-se ≈ 15 h, para correr de noite.

## Primeiros passos — o que eu faria já

1. **Fita e fluxos de semente.**
   - Criar `sementes.py` + `vento_semeado.py` (PROPOSTA), com um gerador próprio para cada fonte exógena.
   - Escrever os testes de identidade T1–T4 (§3.10). Sem isto nenhuma comparação se interpreta.
2. **Levar a fita à mira.**
   - Campo `OpcoesEpisodio.fita` e vento real nos tiros virtuais.
   - Recolha com DR.
   - Tirar à mira o estado VERDADEIRO (o oráculo).
3. **Re-medir o M0** com e sem vento, em bancos disjuntos:
   - com a configuração que REALMENTE voa (a anti-tremor) e com a variante de projeto;
   - com ≥ 62 tiros por célula, e depois ≥ 299.
4. **`calibracao_mira.py`** (PROPOSTA; corre já, sem treinar): diagrama de fiabilidade, ECE/Brier e Clopper–Pearson por célula.
5. **Primeiros A/B físicos e afinação:**
   - M1, uma sep-CMA-ES com a restrição de margem de fase ≥ 45° na configuração voada;
   - recuo antecipado pelos cotovelos;
   - cotovelo amortecido.
6. **Só depois:** M2 (interface 5), o oráculo MPPI e o RL residual.

---

## 1. Onde estamos

### 1.1 Linhas de base medidas (o que qualquer método tem de bater)

| grandeza (v5, build `articulado_15pol_mn5006`) | valor | fonte |
|---|---|---|
| 3 cenários de altura (sementes 6200–6203, bola Lissajous, ar calmo), portão TF | 73/0 · 63/0 · 59/0 → **+109,5 · +94,5 · +88,5 pontos/min**; afastamento 30 · 31 · 28 cm; corpo +2,5° · −19,5° (nariz ↑) · +27,3° (nariz ↓) | `out/evolucao/evolucao_estabilidade.json` |
| idem, portão só-físico | 39/0 · 44/0 · 32/**1** | idem |
| idem, v4 rígido (translada para mirar) | 20/0 · 19/0 · 21/0 → 30 · 28,5 · 31,5 pontos/min; afastamento 80 · 124 · 157 cm | idem |
| validação da mira (sementes 90001–90004) | TF 73/0 · 63/0 · 54/0 (109,5/94,5/81,0 acertos/min); só-físico 36/0 · 37/1 · 29/1 | `out/mira_articulada/validacao.json` |
| benchmark de evolução (v5) | ω_RMS 1,82 °/s · *jitter* 1,52 % · recuperação 0,04 s (o piso da métrica) · 104 tiros/min · vento fixo 3/5 m/s 10,8/15,0 cm · estabilidade 79,5 (v4: 0,77 °/s · 0,68 % · 88,4) | idem |
| recuo | J 1,916 N·s → Δv 0,43 m/s → ~0,32 m de afastamento por tiro | `README.md:104-107` |
| margem de fase da malha de taxa | 45,0° no projeto; **41,0°‡** com a configuração que voa (PT1 40/22 Hz, Kd×0,45, `w_pert` 3,05) | `fc.py`; `sim_view.py:2293-2310` |
| custo da margem de 45° | validação 112,5/109,5/93,0 → 109,5/94,5/81,0 acertos/min; afastamento 21–24 → 28–31 cm; sempre 0 erros | `README.md:72-73` |
| tremor vs margem (articulado) | 40° 2,28 · 45° 1,73 · 50° 1,27 °/s; 0,70 °/s sem ruído de sensores | `README.md:62-67` |
| drone | 4463,6 g · T/W 2,58 · 557 W · 22,0 min | `README.md:48` |
| débitos | PPO no articulado 989/1416 passos/s (8/16 envs; rígido 3578); episódio de mira ≈ 6,6 s·núcleo (180 episódios em 54 s com 22 processos) | `README.md:79-80, 91` |
| cascata no Cortex-M7 | 4,3 µs a 500 Hz; 10,1 µs no passo com decisão (50 Hz); llvm-mca | `firmware/README.md:303-304` |

### 1.2 O que limita hoje (diagnóstico)

1. **A mira nunca viu vento.**
   - `criar_env` não passa vento (`cenarios_mira.py:62-67`), e os tiros virtuais usam `vento = np.zeros(3)` (`treinar_mira_articulada.py:120`).
   - O vento do benchmark é uma semente, com 2 degraus constantes a 90° e a 45°, medido só em pairagem e sem tiros. Quase não exercita o canal x dos servos.
2. **O vento de treino não é emparelhado.** Vem de três sítios:
   - sai do `np_random` do env (`env.py:768-778`), que a planta também usa (`env_real.py:433`);
   - o auto-reset do SB3 não leva semente;
   - o currículo reamostra o vento **a meio** do episódio, num instante que depende do desempenho (`train.py:704-720`).
3. **A estatística é curta.**
   - 59–73 tiros por célula limitam a taxa de erros a 4,0–4,95 % (95 %).
   - A Lissajous não depende da semente, por isso há ~1 trajetória por cenário.
   - Dois conjuntos de 4 sementes discordam no «acima» (59 vs 54 acertos).
4. **A configuração que voa não é a que se avaliou no vento.**
   - O cockpit e o benchmark aplicam `_afinar_cfg_anti_tremor` (`sim_view.py:2293-2310`; `w_pert` 3,05 rad/s).
   - O envelope «0 quedas até 5 m/s» é do p50b sem Glock, com `w_pert` 8,43, medido a 2026-10-13.
   - O articulado nunca passou pelo `avaliar_vento.py`.
5. **A perceção usa um oráculo.**
   - `estado_boca` lê a posição e a velocidade VERDADEIRAS da boca; o azimute e a câmara usam a guinada e a posição verdadeiras (`mira_articulada.py:119-131, 333-352`).
   - O rastreador é sintético: posição verdadeira + atraso de 116 ms + ruído gaussiano.
6. **O portão escolhe-se fora da política.**
   - A fase C é contrafactual. A validação serve três vezes: paragem antecipada, AUC e escolha entre 1248 regras.
   - O ótimo ficou na borda da grelha: ω_max 0,8 rad/s é o topo, o intervalo de 0,40 s é o fundo.
7. **A rede é sobreconfiante**: na banda [0,95; 0,97) prevê 0,961 e acerta 0,914 (`validacao_tf.npz`).
8. **O «acima» é o pior cenário** (88,5 e 81,0). A hipótese, inferida e não isolada por medição: com o nariz para baixo, o recuo tem uma componente para cima que esbarra no portão |vz| ≤ 0,25 m/s.
9. **Há métricas com defeito.**
   - A recuperação tem um piso de 0,04 s.
   - O índice de estabilidade penaliza a arfagem intencional.
   - O «erro de vento» do benchmark mede flutuação (desvio-padrão + |Δz| em 1,8 s), não o desvio médio.
   - O v1 e o v2 são emulações.
10. **Falta realismo.**
    - Não estão modelados o carregador de 15 tiros, a recarga e a massa que diminui (~140 g). Os 104 tiros/min seriam impossíveis com um só carregador.
    - A folga interna de 0,25° dos servos fica de fora (`lab/drone_rpi/servos.py:24-26`).
    - Não há DR do mecanismo.
    - O controlador dos braços só existe em Python, e a IK usa `asin`, que o núcleo C++ proíbe.
11. **Não há RL para o articulado.**
    - A política atual tem observação 48 e o build tem 64, por isso é recusada.
    - A ação 4-D CTBR não mira.
    - O RL treina em «lento», com o `fc.py` sem `prioridade_rp`, enquanto o cockpit voa a cascata C++.

---

## 2. O que é «perfeição», em métricas

A estatística nunca prova «0 erros». Por isso a perfeição é uma **ordem lexicográfica pré-registada**: segurança → erros → cauda → média → Pareto. O objetivo é baixar o limite superior da taxa de erros, e a cauda, até metas fixadas antes de medir.

| nível | métrica (definição operacional) | hoje | meta (PROPOSTA) |
|---|---|---|---|
| restrição | quedas por episódio | 0 em 25 regimes × 12 sementes, só no rígido p50b; o articulado nunca voou com vento | 0 em todas as células |
| restrição | taxa de erros por tiro: limite superior de Clopper–Pearson a 95 %, por célula [S7][S8] | 73/0 → 4,02 % · 63/0 → 4,64 % · 59/0 → **4,95 %** | já: < 1/(1+K) = 4,76 %; depois < 1 %; depois < 0,5 % |
| objetivo | pontos/min = (acertos − 20·erros)/min, na PIOR célula e em CVaR 10 % [S11]; o IQM como resumo [S3] | 109,5 · 94,5 · 88,5 (ar calmo); teto de 150 tiros/min com intervalo de 0,40 s | maximizar a pior célula COM vento; referência: ≥ 90 % do teto |
| Pareto | afastamento da estação (xy p95, \|Δz\| máx.) | 28–31 cm; o §7 do `teste_bracos.py` aceita até 0,40 m | ≤ 0,40 m e sem piorar |
| Pareto | tremor ω_RMS · *jitter* dos motores | 1,82 °/s · 1,52 % (v4: 0,77 · 0,68) | não piorar o v5; alvo: o v4 |
| Pareto | recuperação pós-tiro | 0,04 s, o piso da métrica | redefinir à resolução do passo de física |
| Pareto | Wh/acerto = Σ `energias_wh` dos 8 servos ÷ acertos | 15–36 W a mirar | medir; não piorar > 10 % |
| Pareto | curso/min (desgaste) = Σ\|Δq\| dos 8 servos por minuto | contadores em `lab/drone_rpi/servos.py` | medir; não piorar > 10 % |
| Pareto | fração do tempo saturado (servos, \|τ\| no limite, `kFlagDifEscalado`) | não há métrica | registar; não piorar |
| Pareto | pitch máximo usado (\|θ_corpo\|, \|τ\|) | +27,3° nos cenários; +34° no cockpit; coplanar até 34,14°‡ | ≥ 3° de margem ao limite coplanar |
| Pareto | CPU a bordo (ciclos no M7, flash, RAM) | cascata 4,3/10,1 µs; braços e mira só em Python | caber no período; medir com DWT |

**Ponto de equilíbrio e «regra dos três».**
- Com K = 20, cada tiro vale 1 − 21·p. Logo, atirar só compensa com p < p\* = 1/21 = 4,76 %.
- Com 0 erros em n tiros, o limite exato a 95 % é 1 − 0,05^(1/n) ≈ 3/n [S7].
- Quando há erros, usa-se Clopper–Pearson e nunca Wald, que com 0 eventos dá [0, 0] [S8].

| meta de p_erro | tiros seguidos sem erro, por célula | episódios de 10 s por célula (estimativa, 14–18 tiros/episódio em ar calmo) |
|---|---|---|
| 4,76 % = 1/(1+K) (valor esperado > 0) | 62 | 4–5 |
| 1 % | 299 | 17–22 |
| **0,5 %** | **598** | 34–43 |
| 0,1 % | 2995 | 167–214 |

Os tiros de um episódio partilham a rajada e a fase da bola, por isso o n efetivo é menor. Reporta-se também por episódio, com bootstrap por blocos [S3].

**Aceitação e paragem (PROPOSTA).**
- **Aceitação.** Um desafiante só substitui o campeão se cumprir três condições:
  - ganhar no objetivo COM vento;
  - não perder mais de 2 % SEM vento;
  - não violar nenhuma tolerância da tabela.
- **Paragem.** O ciclo termina quando duas condições se verificam:
  - em 2 rondas seguidas, o ganho emparelhado do campeão novo sobre o anterior (na pior célula com vento) fica abaixo da largura do seu IC a 95 %;
  - a restrição de erros já está certificada na meta.
- **Patamar antes da certificação.** Nesse caso o limite já não é o método, mas o hardware ou o firmware: o intervalo de 0,40 s, a câmara de 116 ms ou o recuo. A ronda seguinte muda essa alavanca.

---

## 3. Protocolo de vento semeado — a mesma adversidade em todos os treinos, sem ficar num padrão

Em termos de simulação, o pedido do dono são **números aleatórios comuns** (CRN): os mesmos números servem os mesmos eventos em todas as corridas. As comparações ficam emparelhadas e a variância das diferenças baixa [S1]. O CRN só ajuda se os métodos responderem ao vento de forma correlacionada: Var(A−B) = Var A + Var B − 2·Cov(A, B) [S2]. Por isso reporta-se a correlação ρ entre métodos e, se for baixa, aumenta-se o número de fitas.

### 3.1 Hoje

| peça | gerador hoje | igual entre métodos? | fonte |
|---|---|---|---|
| vento por episódio e vento dinâmico (`rajadas`, `aleatoria`, `frente`, `dryden`) | `self.np_random` do env, partilhado com a DR, o jitter, os comandos, o pitch-DR dos braços, os sensores e o VRS | **não** | `env.py:768-778, 886-952`; `env_real.py:433` |
| currículo do PPO | o mesmo gerador; subir de estágio reamostra o vento a meio do episódio | **não** | `train.py:704-720` |
| `VentoPareado` (avaliação) | `default_rng([seed, 0x7E])` + `reset(seed)` em cada episódio | sim, **só na avaliação** | `avaliar_vento.py:96` |
| `VentoNatural` (cockpit, regimes `natural_*`) | gerador próprio, mas **sem sal**: `default_rng(s)` é o mesmo fluxo que `env.reset(seed=s)` | sim, mas acoplado ao ruído do episódio | `vento_natural.py:97-98` |
| bola aleatória | `SeedSequence([s, 0xB01A])`, que não gasta o gerador do env | sim — **é o padrão a copiar** | `env_real.py:124, 592-599` |
| mira articulada (dados, TF, portão, 3 alturas) | sem vento | — | `cenarios_mira.py:62-67`; `treinar_mira_articulada.py:120` |
| benchmark oficial | degraus 0 → 3 m/s a 90° → 5 m/s a 45°, semente 6200 | sim (determinístico) | `benchmark_evolucao.py` |
| treino GPU da mira rígida | sem vento; `jax.random.split(key_lote, n_envs)` | muda com `n_envs` | `treinar_mira_gpu.py:256, 270` |

### 3.2 A «fita de vento» (PROPOSTA)

**O que é.** Uma fita é uma função pura `w(índice, n)`: o vento em m/s (3 eixos) no passo de voo `n`.

**Como se gera.** Com um gerador **baseado em contador** [S14][S15]: Philox no NumPy, com a chave derivada de uma `SeedSequence`, ou `jax.random.fold_in` no JAX [S16]. A chave junta versão, fita-mestra, família, índice, fluxo e um sal; o contador é o índice do segmento. Daí vêm três propriedades:
- acesso direto ao segmento j sem gerar os anteriores (os filtros de turbulência retomam do último marco gravado);
- uma fita **infinita e sem ciclo** para cada índice;
- nenhum gerador partilhado com o resto do env.

**Três camadas.**
1. **Calendário de regimes.**
   - É uma cadeia semi-Markov com a diagonal a zero, para que o regime nunca se repita seguido [S18].
   - A permanência em cada regime é U[1,5; 4,5] s.
   - Num esboço com 400 segmentos (cálculo): 0 repetições seguidas, permanência média de 3,0 s (≈ 20 trocas por minuto) e **pelo menos 2 trocas em qualquer janela de 10 s**, que é a janela de mira.
2. **Parâmetros por segmento.** São sorteados de novo em cada segmento (§3.4). Nunca há um processo único com parâmetros fixos, que é justamente o «mesmo padrão aleatório» a evitar.
3. **Síntese.**
   - Nas trocas, o estado dos filtros de turbulência não é reposto.
   - Só mudam σ, L e a média, numa rampa 1−cos de 0,6 s (o `TAU_RAMPA_S` de `vento_natural.py:50`).

| regime | forma | parâmetros por segmento (PROPOSTA) | hoje / fonte |
|---|---|---|---|
| calmo | w = 0 | P ≈ 0,25 do calendário: a fração «sem vento» do treino é fixa e igual para todos | modo sem vento |
| constante | W·(cos az, sen az, ·) | W 0,5–5 m/s; az **relativo ao nariz**, 0–360° | `definir_vento` (`env.py:735`) |
| rajadas 1−cos | base + rajadas | amplitude 0,3–0,7·W; subida 0,2–3 s; 2–20 rajadas/min | `VentoNatural`: Poisson a cada ~6 s, duração 1–3 s [S19] |
| turbulência Dryden | H_u de 1.ª ordem; H_v e H_w de 2.ª ordem | σ/W 0,1–0,3; L pela altitude (MIL) | o `VentoNatural` usa OU de 1.ª ordem [S20][S22] |
| mudança de direção | az(t) em rampa 1−cos | Δaz ±30° a ±180° em 1–3 s | modo `frente`; deriva OU de 15°/20 s |
| corrente vertical | elevação ≠ 0 | ±10° a ±30° | subida/descida a ±30° (`avaliar_vento.py:117`) |
| cisalhamento | W(z) logarítmico | z0 0,01–0,3 m | [S21]; exige `vento(z)` — hoje o `opt.wind` é global |

**Intensidade como escala de leitura.**
- A intensidade é um parâmetro **de leitura** (`teto_ms`): o calendário, as rajadas e as inovações estão normalizados por W.
- O `VentoNatural` já tem esta propriedade: o número de sorteios por passo não depende de W (`vento_natural.py:151-202`), por isso as rajadas caem nos mesmos instantes a 3 e a 5 m/s.
- É isto que permite o currículo «a mesma fita, escalada» (§3.8).

**Armazenamento.** Materializada em float32 a 50 Hz, a fita ocupa 36 kB por minuto (cálculo). Grava-se em `.npz`, com o `sha256` num manifesto.

### 3.3 Indexar pelo tempo de voo de cada ranhura, não pelo episódio

**Ranhura** é o ambiente paralelo i do `SubprocVecEnv`. No treino, o índice da fita é a ranhura, e `n` conta os passos de decisão **voados** por ela, acumulados entre episódios: um contador que o `reset` não zera.
- Conta-se em passos de voo, e não pelo `data.time`.
- A razão: a cascata calibra 1 s no chão em cada reinício sem avançar `env.passos` (`sitl.py:828-840`).

| | por tempo de voo da ranhura (TREINO) | por episódio (AVALIAÇÃO) |
|---|---|---|
| o que fica igual entre métodos | o vento em cada segundo do orçamento de amostras | o vento do episódio k, do princípio ao fim |
| quedas e reinícios | não mudam a sequência | quem cai mais gasta mais fitas e vê outras |
| emparelhamento por episódio | não (cada episódio começa noutra fase da fita) | sim (k ↔ k) |
| implementação | contador persistente; o auto-reset sem semente deixa de importar | `reset(seed=s_k)` explícito, como em `avaliar_vento.py` |

**Recomendação: treinar por tempo de voo, validar e testar por episódio.**
- Fixar o mesmo número de ranhuras (16, a omissão desta máquina) em todos os métodos comparados.
- Juntar ao `train.py` um `--episodio-s` (PROPOSTA; o `DroneRealEnv` já aceita `episodio_s`), por exemplo 20–30 s, para que o vento mude várias vezes dentro de cada episódio.

### 3.4 Cobertura uniforme em vez de sorteio aglomerado

**Segmentos de treino.**
- Os parâmetros contínuos de cada segmento formam d = 8 dimensões: W, azimute relativo ao nariz, elevação, σ/W, taxa e amplitude das rajadas, tempo de subida e permanência.
- Saem de uma sequência de **Sobol embaralhada** [S17], uma por ranhura. A ordem é permutada, com semente, dentro de blocos de 64 segmentos (≈ 3 min de voo).
- No esboço, com 64 pontos em 8 dimensões, a discrepância foi 0,016 com Sobol contra 0,057 com sorteio simples (cálculo).

**Bancos por episódio (avaliação).** Cada família tem 128 fitas, estratificadas por:
- cenário de altura;
- direção face ao nariz: **proa, través, cauda**;
- faixa de W: ≤ 3 m/s e 3–5 m/s.

A direção pesa: em x, os servos vetorizam o empuxo sem mexer o corpo, e a componente lateral fica no rolamento (`firmware/nucleo/cascata.hpp:549-558`).

### 3.5 Famílias de sementes disjuntas (bancos)

A chave de cada banco é `SeedSequence([VERSAO, MESTRA, família, índice, fluxo, SAL])` [S14].

| família / banco | uso | tamanho (estimativa) | regra |
|---|---|---|---|
| TREINO | PPO, TF e CMA-ES; fita por ranhura e 1024 fitas por episódio para a recolha da mira | — | **a mesma para todos os métodos**, pela mesma ordem |
| CALIBRAÇÃO | afinação caixa-preta, temperatura T, λ do controlo de risco conformal, τ_d do ensemble | ~1500 episódios | nunca entra nos relatórios |
| VALIDAÇÃO | paragem antecipada, escolha do portão, comparação de métodos com ≥ 5 sementes | 128–256 | nunca entra no veredicto |
| TESTE (selado) | veredicto, uma vez por geração | 512 | só com `--abrir-teste`; o treino recusa-o, como o `treinar_bola.py:190-192` já recusa as sementes de avaliação |
| STRESS | W 5–8 m/s, latências até ~150 ms, falhas | 32–64 | só diagnóstico, sem garantia |
| REGRESSÃO | sementes de hoje (5000–5011, 9000–9007, 6200–6211, 90001–90004, …) e o benchmark fixo | — | continuidade do `evolucao_drone.png` |

Os cruzamentos que existem hoje ficam por corrigir:
- a 6200 serve 4 fins: benchmark, IBVS, validação na GPU e `valida_real`;
- a 7301 serve 2;
- as sementes do rastreador (semente + 101 → 1101–1693) colidem com as do env (1000–1592).

### 3.6 Duas fontes de aleatoriedade, separadas

| fonte EXÓGENA (igual em todos os métodos) | hoje | fluxo PROPOSTO |
|---|---|---|
| vento | `np_random` (`env.py:768-778, 886-952`) | `vento` (a fita) |
| sensores e VRS | `planta.rng = self.np_random` (`env_real.py:433`) | `sensores`, reposicionado no 1.º passo de voo |
| DR física | `np_random` (`env_real.py:376-383`) | `dr`, por ranhura e episódio |
| jitter do arranque | `np_random` (`env_real.py:449-452`) | `arranque` |
| pitch-DR dos braços | `np_random` (`env_real.py:810-814`) | `bracos` |
| plano de comandos | `np_random` (`env.py:1016-1039`) | `comandos` |
| bola aleatória | `SeedSequence([s, 0xB01A])` | já está separada: manter |
| câmara/rastreador da mira | semente + 101 (`cenarios_mira.py:85`) | `camara` |
| viés dos encoders | `default_rng(0x5E40)` fixo (`lab/drone_rpi/servos.py:200`) | `mecanismo`, com DR por episódio |

A fonte do **algoritmo** é a que se faz variar, com ≥ 5 sementes por método [S4][S5][S6]. Hoje está em quatro sítios:
- o `seed` do PPO (`train.py:1394`);
- `tf.random.set_seed(20261019)` (`treinar_mira_articulada.py:203`);
- `PRNGKey(20261015)` (`treinar_mira_gpu.py:270`);
- a `default_rng(args.semente)` da CMA-ES (`treinar_bola.py:235`).

**Blocos.** A conclusão repete-se em **3 fitas-mestras** (M ∈ {1, 2, 3}). Só é aceite se o efeito tiver o mesmo sinal nos 3 blocos e se o IC emparelhado do conjunto excluir 0.

### 3.7 Modo SEM vento como controlo emparelhado

Cada fita k tem uma fita nula k⁰ (`sem_vento=True`). A chave dos outros fluxos não inclui o vento: a bola, os sensores, a DR e o arranque ficam iguais **bit a bit**, e só o vento muda.

O custo do vento de cada método é Δ_k = S(k) − S(k⁰), calculado aos pares. Daí leem-se três coisas:
- S(k⁰), a capacidade;
- S(k), a robustez;
- Δ, o custo do vento.

A bala quase não deriva: 0,095 mm a 5 m/s e a 2,5 m, contra um raio de colisão de 54,5 mm (cálculo). Logo, Δ mede a **plataforma**: atitude, deriva da estação e portões de estabilidade.

### 3.8 Currículos a comparar (sempre com as mesmas fitas)

| currículo | fita | quando muda | igualdade entre métodos |
|---|---|---|---|
| C0 sem vento | nula | — | total (é o treino atual da mira) |
| C1 vento desde o início | treino, teto de 5 m/s | — | total |
| C2 crescente 0 → 1 → 2 → 3 → 5 m/s | a **mesma** fita, na escala do estágio | orçamento fixo de passos (1–2 M por estágio, `pesquisas/relatorio-treino-rl-suficiencia.md`), numa fronteira de segmento | total |
| C3 i.i.d. por episódio | fita (treino, nº do episódio) | a cada episódio | parcial: depende das quedas |
| C4 ADR por níveis [S25] | níveis pré-gerados | quando se passa um limiar de desempenho | parcial: só no treino |
| C5 RARL [S26] | fita + adversário limitado (\|Δ\| ≤ 0,5·W, taxa limitada) | adaptativo | quebrada: só no treino |

**Notas sobre os currículos.**
- O C2 substitui duas coisas que dependem da política:
  - o avanço por `frac_xy_z ≥ 0,5`;
  - a reamostragem a meio do episódio.
- O C2 inteiro leva ≈ 1–2 h por semente no articulado (estimativa).
- O C4 e o C5 quebram a igualdade **por desenho**: o adversário reage ao aprendiz. Só servem para treinar. A avaliação faz-se sempre nas fitas de validação e de teste, e o adversário serve também para procurar o pior caso [S24].

### 3.9 Esboço de API (PROPOSTA) e o que muda em cada ficheiro

```python
# experiments/09_drone_hover_rl/sementes.py — PROPOSTA (ainda não existe)
from dataclasses import dataclass
import numpy as np

VERSAO = 1        # mudar a versão muda TODAS as fitas: uma versão publicada nunca se edita
SAL = 0x7E        # o sal do VentoPareado (avaliar_vento.py:96)
FAMILIAS = {"treino": 1, "calibracao": 2, "validacao": 3, "teste": 4, "stress": 5}
FLUXOS = {"vento": 1, "sensores": 2, "dr": 3, "arranque": 4, "bracos": 5,
          "comandos": 6, "camara": 7, "mecanismo": 8, "bola": 9}

@dataclass(frozen=True)
class EspecFita:
    mestra: int               # bloco: 3 fitas-mestras repetem a conclusão
    familia: str              # treino | calibracao | validacao | teste | stress
    indice: int               # ranhura (treino, por tempo de voo) ou nº do episódio (avaliação)
    teto_ms: float = 5.0      # escala de LEITURA (currículo C2: a mesma fita, outra escala)
    sem_vento: bool = False   # controlo emparelhado: não entra em nenhuma chave

def fluxo(e: EspecFita, nome: str, contador: int = 0) -> np.random.Generator:
    """Philox: chave = hash(versão, mestra, família, índice, fluxo, sal); contador = nº do segmento."""
    ss = np.random.SeedSequence([VERSAO, e.mestra, FAMILIAS[e.familia], e.indice, FLUXOS[nome], SAL])
    return np.random.Generator(np.random.Philox(key=ss.generate_state(2, np.uint64),
                                                counter=[0, 0, 0, contador]))

# experiments/09_drone_hover_rl/vento_semeado.py — PROPOSTA
class FitaVento:
    DT = 0.02                                                             # s: o vento muda uma vez por decisão
    def __init__(self, e: EspecFita): ...
    def segmento(self, j: int) -> dict: ...                              # regime + parâmetros (Sobol do bloco)
    def vento(self, n: int, z: float | None = None) -> np.ndarray: ...   # (3,) m/s no passo de voo n
    def materializar(self, n: int) -> np.ndarray: ...                    # float32 (n, 3): JAX, SITL, manifesto
    def sha256(self, n: int) -> str: ...
```

O `fluxo()` do esboço foi corrido no `.venv` (NumPy 2.5.3) com três resultados:
- a mesma `EspecFita` repete os bits;
- mudar a família muda-os;
- a fita nula partilha os fluxos `sensores`, `dr`, etc.

| ficheiro | o que muda (PROPOSTA) |
|---|---|
| `sementes.py`, `vento_semeado.py` (novos) | `EspecFita`, `fluxo()`, `FitaVento` e `BancoFitas` (manifesto `.json` + `.npz` com `sha256`, versão do NumPy e `VERSAO`) |
| `env.py` | `definir_fita(fita, indexacao="tempo" \| "episodio")`; o `_passo_vento` escreve `fita.vento(n)` sem tocar no `np_random`; contador `_n_fita` que só o modo «episodio» zera |
| `env_real.py` | fluxos próprios para `planta.rng`, DR, jitter e pitch-DR, atrás de uma opção: quebra a identidade bit a bit do `bench_treino.py`, por isso grava-se uma referência nova |
| `vento_natural.py` | aceitar um `Generator` em vez de `default_rng(semente)` e ser o motor do regime «natural»; Dryden com H_v e H_w de 2.ª ordem; o cockpit ganha `semente`/`fita` em `POST /api/vento-simples` |
| `train.py` | `--fita-mestra`, `--fita-indexacao`, `--curriculo-fita 0,1,2,3,5 --passos-estagio`, `--episodio-s`; avaliação em duas trilhas (fita nula + validação) com `reset(seed=s_k)` por episódio e `best_model` escolhido pela pior das duas; recusa a família de teste |
| `cenarios_mira.py`, `treinar_mira_articulada.py` | `OpcoesEpisodio.fita`; o `gancho_fisica` grava o `opt.wind` e `simular_bala` recebe o vento do instante do disparo; a fase C maximiza o pior caso de {3 cenários} × {k⁰, k}; o JSON do modelo guarda o `sha256` do banco |
| `treinar_mira_gpu.py` | `fold_in(fold_in(PRNGKey(M), família), episódio_global)` em vez de `split(key, n_envs)`; o vento entra como **array** materializado, porque os bits do threefry não são os do Philox; falta um termo de vento na dinâmica JAX |
| `avaliar_vento.py`, `avaliar_bola.py`, `benchmark_evolucao.py` | regimes `fita_*` lidos do banco; sal no `VentoNatural`; `--build` no `avaliar_vento.py`/`avaliar_bola.py`; o benchmark fixo mantém-se, com células novas nas fitas de validação e de teste |

### 3.10 Testes de reprodutibilidade (PROPOSTA `teste_vento_semeado.py`) e armadilhas

| teste | o que prova | mutação que o tem de fazer falhar |
|---|---|---|
| T1 identidade | `sha256` da fita igual em 2 processos, depois de `pickle` (SubprocVecEnv) e noutra máquina | `default_rng()` sem semente |
| T2 consumo | o `opt.wind` por passo é igual com 0 ou 5000 números gastos pela planta: rígido × articulado, DR ligada × desligada, cascata × RL (hoje: 0/120) | voltar a sortear do `np_random` |
| T3 quedas | duas sequências de ações com fins diferentes dão o mesmo vento no passo de voo n (modo tempo) e no episódio k (modo episódio) | zerar `_n_fita` no `reset` |
| T4 sem padrão | 0 regimes repetidos seguidos; ≥ 2 trocas em qualquer janela de 10 s; 0 colisões de `sha256` entre índices e famílias | permanência máxima de 6 s |
| T5 famílias | o treino recusa a família «teste»; validação ∩ teste = ∅ | tirar a guarda |
| T6 estatística | PSD de Welch por eixo contra o espectro de Dryden [S22]; σ_w/W ≈ 0,1 | trocar σ_w |
| T7 escala | a fita a 2 m/s é 0,4 × a fita a 5 m/s, com as rajadas nos mesmos instantes | reamostrar ao mudar de estágio |
| T8 CPU ↔ GPU | o array que entra no JAX tem o `sha256` do manifesto | regenerar o vento no JAX |

**Armadilhas.**
- **A semente não é o vento.** Guarda-se a fita materializada e regista-se a versão do NumPy e a `VERSAO`: a semente reproduz o gerador, o ficheiro reproduz o vento.
- **O relógio.** Usar um contador inteiro de passos de voo. Nunca `t += dt` em float, nem `data.time`.
- **Os sensores na cascata.** A calibração de 1 s no chão consome ruído que a RL não consome. Por isso o fluxo `sensores` é reposicionado no 1.º passo de voo.
- **TF/XLA.** Ligar `tf.config.experimental.enable_op_determinism()` e provar por repetição (`sha256` dos pesos) [S12]. Na fase C (JAX), desempatar o argmax por uma regra fixa.
- **Decorar a fita.** Mitigação:
  - banco grande;
  - nenhum tempo absoluto na observação;
  - vigiar a diferença treino–teste como alarme [S24].
- **A unidade estatística.** O bootstrap faz-se por fita/episódio, não por tiro [S3].
- **O vento uniforme.** O cisalhamento e um campo de vento amostrado em cada rotor [S23] exigem `vento(posição)`. A planta já calcula `v_ar` por rotor, mas o `opt.wind` é global: fica para uma fase 2.

---

## 4. Metodologias de controlo a comparar (braços + mira)

### 4.1 Regras comuns (sem elas a comparação volta a ser sorte)

1. **Mesma adversidade.** Todas as metodologias voam as MESMAS fitas (§3) e a condição «sem vento». O vento no instante t não pode depender do controlador, do build nem das quedas.
2. **Mesmas células, mesmo critério.**
   - Células: 3 alturas × {sem vento, fitas a 3 e a 5 m/s}, com vento de proa, de cauda e de través.
   - Decide a pontuação/min da **pior** célula.
   - Os erros levam o limite de Clopper–Pearson: «0 erros» só prova p_erro < 4,76 % com ≥ 62 tiros por célula.
3. **Mesmo orçamento de afinação para todos.** Um controlo ótimo mal afinado perde por falta de afinação, não por ser pior [S32].
4. **Mesma camada de decisão.**
   - Quem mudar a dinâmica re-treina o portão TF com a mesma receita (fases A–D, ~4 min).
   - Para separar o controlo do portão, mede-se também **oportunidades/min** (PROPOSTA): a fração dos instantes de decisão em que o tiro virtual acertaria e os portões de estabilidade passam.
5. **Mesma perceção, sem oráculo.** Trocar o estado verdadeiro pelo estimador em TODOS os métodos antes de medir com vento.
6. **Tudo contra o núcleo C++.**
   - Corre-se com `sitl.py` / `DroneRealEnvNucleo`, nunca contra o `fc.py`, que não tem `prioridade_rp`.
   - Promoção pela regra do `treinar_bola.py`: sementes de afinação disjuntas das de avaliação, Δ + EP < 0 emparelhado e 0 quedas.
   - A margem de fase ≥ 45° verifica-se na configuração que **realmente voa**.

### 4.2 As metodologias

**M0 — linha de base v5** (cascata + IK analítica + `MiraArticuladaIA` com portão TF).
- **Como funciona.**
  - A interface 4 da cascata C++ põe o empuxo diferencial a segurar o pitch do CORPO e pede aos servos `incl_ref = atan2(n̂·ĥ, n̂_z) − θ̂` (`cascata.hpp:549-558`).
  - Como o cockpit manda sempre `pitch_corpo`, o vento em x JÁ é vetorizado pelos servos; o y continua por rolamento.
  - Os braços (`bracos_controlo.py`) usam a IK fechada q₁ = τ + δ, q₂ = −δ, num esquema macro-mini: o ombro tem PT1 de 0,6 s e zona morta de 1°, e τ fica limitado a ≤ 99,8 °/s.
  - A mira usa um Kalman de aceleração constante, a balística com 2 iterações, guinada PI + avanço ω_LOS, mais as redes TF e o portão (limiar 0,987, intervalo 0,40 s).
- **O que fazer.** Congelar com impressão digital e re-medir com as regras comuns.
- **Variante M0-proj.** O mesmo sem `_afinar_cfg_anti_tremor`: é o primeiro A/B, grátis, entre anti-tremor e vento.
- **Riscos conhecidos.**
  - A saturação dos servos fica fora do anti-windup (`cascata.hpp:455-463`).
  - Não há trim do CM com τ.
  - Os envelopes não batem: coplanar 34,14°‡, cockpit ±35°, `tau_max` 100°.
  - O barramento corre a 250 Hz, e não aos 200 Hz do catálogo (`bracos_controlo.py:102`).

**M1 — a mesma estrutura, parâmetros re-otimizados** (sep-CMA-ES ou otimização bayesiana) sobre as fitas.
- **Porquê.** Repete o que resultou no IBVS: o `treinar_bola.py` afinou 10 ganhos com uma sep-CMA-ES própria (λ 12, σ₀ 0,15), sempre nas MESMAS sementes em cada geração. Ganhou Δcusto −0,487 ± 0,143 em 72 episódios emparelhados, com 0 quedas (`out/bola/afinacao.json`).
- **Espaço de busca.**
  - braços: `TAU_OMBRO_S`, `ZONA_MORTA_OMBRO`, `FRACAO_TAXA_TAU`, `K_LENTO` (`bracos_controlo.py:40-47`);
  - servos: `ACEL_PERFIL`, `ACEL_PERFIL_SEM_FIM`, `KI_CORRECAO_SEM_FIM`, `kp_duty`/`kd_duty`;
  - mira: os 15 `PARAMETROS_PADRAO` (`mira_articulada.py:50-66`);
  - cascata: `w_pert`, PT1 40/22 Hz, Kd×0,45 e a margem de projeto entre 45 e 55°.
- **Código.** PROPOSTA `treinar_bracos_mira.py`, que importa `SepCMAES`/`validar` do `treinar_bola.py`.
  - Restrição DURA: margem ≥ 45° na configuração voada (`controlo_classico.resposta_malha_taxa`).
  - O vencedor vai para um cabeçalho, como o `ibvs_ganhos.hpp` (PROPOSTA `bracos_ganhos.hpp`).
- **Objetivo.** A pior célula de oportunidades/min, menos penalizações de afastamento, ω_RMS e Wh dos servos.
  - Durante a busca usa-se o portão FÍSICO, porque o TF fica fora da distribuição a cada candidato.
  - O portão TF só se re-treina no top-3.
- **Custo.** Uma geração de 12 candidatos × 3 cenários × 4 fitas leva ~1 min com 16 processos (estimativa).
  - Usar ≥ 4 fitas por geração: com 2 sementes, o custo médio do IBVS oscilou entre 3,98 e 6,57 de geração para geração.
  - A otimização bayesiana só compensa com ≤ ~8 parâmetros caros, e não há `optuna` nem `cma` no `.venv`.
- **Porque pode ganhar.** O compromisso anti-tremor × vento nunca foi otimizado. O v1 desvia 5,1/9,4 cm e o v2–v5 desviam 10,5–10,8/14,9–15,1 cm. E o portão parado na borda da grelha sugere folga na cadência.

**M2 — alocação explícita/INDI com a inclinação como atuador.**

O mecanismo permite comando por braço, mas o software não o usa:
- a API aceita 8 alvos independentes (`ServosBracos.definir_alvos`, `Planta.definir_alvos_juntas`);
- o controlador dá o mesmo q₁ aos 4 ombros, e o firmware só conhece um τ.

Com os 8 eixos ∥ y, só o modo **esquerda/direita** é útil:
- M_z = 4·y·T·sen Δ = **1,05/2,63/5,24 N·m a ±2/±5/±10°‡**, com uma perda vertical de 0,06/0,38/1,52 %‡;
- hoje o arrasto dá ~0,40 N·m‡, e a cascata corta a guinada a 0,534 rad/s² e 0,50 rad/s;
- os modos frente/trás e diagonal dão ≈ 0, e nenhuma combinação gera força lateral;
- como o ombro só anda a ≤ 14,04 °/s, o diferencial tem de ir nos **cotovelos** (perfil a 280,8 °/s).

A ideia é uma alocação com prioridades: pitch do corpo > rolamento > F_z > F_x > guinada [S29][S31]. Mantém-se a separação macro-mini medida, porque com o ombro a seguir τ o pitch oscilava ±2° a 2,8 Hz. Três variantes, em fatorial:
- **M2a — vetorização em x a sério:**
  - anti-windup com a saturação e a taxa dos servos;
  - feed-forward do trim f(τ) (0,475/0,62 N·m a 25/34°‡);
  - um envelope único |τ| ≤ 34,14°‡;
  - a IK em C++ com `atan2f`/`sqrtf`.
- **M2b — guinada diferencial (interface 5):**
  - `Saida::incl_dif` e `Sensores::incl_motor_esq/dir` (PROPOSTA, no fim das structs, como na interface 4);
  - divisão em frequência: o arrasto fica com a alta frequência e a inclinação com a baixa (2,15 rad/s²‡ a ±5°, contra os 0,534 de hoje).
- **M2c — INDI na malha de taxa ou observador de BINÁRIO (UDE)** [S39]:
  - é para o recuo fora do CM e para o CM que se desloca com τ;
  - num túnel de vento, o INDI deu um desvio máximo > 7× menor do que um PID [S27];
  - a força por rotor, T·(sen τ, cos τ), não é afim nas entradas; uma alocação não linear aprendida fica de reserva [S28].

**Riscos do M2.**
- O INDI deriva o giroscópio, e o tremor do articulado já vem do ruído: 0,70 °/s sem ruído, contra 1,73 °/s.
- Há orientações críticas nos cantos do envelope [S30].
- Com um canal por braço, um erro δ num só braço dá M_z ≈ 7,55·sen δ N·m‡. A partir de δ ≈ 5° isso excede a capacidade de guinada, o que exige deteção por braço (§6.9).
- **M7: sim.** É código do mesmo tipo que o do núcleo (float32, sem heap). A interface 4 custou +1410 B de flash no M7.

**M3 — MPC: pitch do corpo + inclinação + empuxo + instante do tiro.**
- **Porquê.** O tiro é a perturbação mais previsível do sistema [S41]: o drone escolhe o instante e conhece J e a direção do cano. Um MPC põe os limites dos servos dentro do problema [S31] e faz duas coisas:
  - escolhe o **instante** do tiro: o de menor falha prevista, com a latência do gatilho incluída;
  - pré-compensa o recuo.
- **M3a — NMPC acados com SQP-RTI a 50 Hz** [S34][S35]: substitui a lei de mira e os laços externos. A malha de taxa e o misturador ficam.
- **M3b — MPPI na GPU** [S33]: em JAX sobre um modelo reduzido, como **oráculo** offline com o custo real descontínuo (acerto/erro com K = 20).
  - 1024 amostras × 50 passos ≈ 6 ms por decisão ao débito do substituto JAX (8,54 M passos/s), ≈ 3 s por episódio (estimativa).
  - O substituto tem de ser identificado contra o articulado no MuJoCo antes de ser usado.
- **Risco.** Até ~3 m/s, com estimador de perturbação, NMPC e PID quase empatam; o NMPC só se destaca perto da saturação (41–51 % a 10–12 m/s) [S36]. No envelope do dono, o **observador** pode contar mais do que a família do controlador. Por isso a comparação é fatorial: controlador × observador.
- **M7.** O M3a talvez embarque, mas o código gerado tem de cumprir as regras do núcleo, e a licença tem de ser verificada antes de vendorizar. O M3b não embarca: é professor e oráculo.
- **Porque pode ganhar.**
  - Com ω até 0,8 rad/s, a boca roda 0,73°‡ nos 16 ms do gatilho, contra uma tolerância de ≈ 1,25°‡ a 2,5 m.
  - Pode baixar o piso de 0,40 s entre tiros.
  - O oráculo mede quanto falta para a «perfeição» em cada célula.

**M4 — RL residual (PPO) limitado por cima do campeão clássico.**
- **M4a.** u = u_base + clip(π_res(obs), ±δ), com a última camada iniciada a zero: o pior caso é a base [S37].
  - Ação ao nível do comando da mira (Δpitch_corpo, Δtaxa de guinada, Δv_ref, Δincl_ref), com limites pequenos (por exemplo ±2° e ±0,1 rad/s; estimativa).
  - A observação junta o vento estimado a bordo (`Saida::pert`), como no DATT [S42], e o estado da mira e da saturação.
- **M4b — política exterior sobre a cascata congelada**, como o `env_seguimento.py`:
  - ação (vx, vy, vz, taxa de guinada, pitch_corpo, atirar) via `nuc.comando`;
  - recompensa densa pelos tiros virtuais + (acertos − 20·erros).
- **Custo.** O articulado treina a 1416 passos/s, por isso 3 M passos ≈ 35 min por semente e ≈ 3 h por variante com 5 sementes (estimativa).
- **Porque pode ganhar.** No rígido, a RL pura já era melhor onde a cascata é fraca: |Δz| com vento aleatório de 3 m/s e com ar descendente. E o residual arranca a voar, sem cair no atrator «sentar no chão».

**M5 — RL de ponta a ponta com os braços.**
- **A ideia.** A política comanda CTBR + τ (+ Δ esq/dir) + o pitch do corpo + o gatilho.
- **Arranque a quente.** Transferência 48 → 64 e/ou BC da cascata. A `Saida.coletivo` e as `taxas_ref` do núcleo são exatamente a ação CTBR, e o modo `sombra` dá um especialista em linha para o DAgger.
- **Riscos medidos.**
  - Do zero cai em «sentar no chão».
  - A 1.ª lei dos servos divergiu em 2 s.
  - O clássico já ganhou no vento (11,8 vs 35,2 cm a 5 m/s), e o IBVS ganhou 8–14× ao tracker PPO.
- **Estatuto.** É um **controlo científico**, não uma aposta: mede quanto se ganha ou perde sem estrutura. O Swift mostra até onde chega com resíduos ajustados a dados reais [S38].

**M6 — destilação (BC/DAgger) do M3 para uma rede embarcável, afinada por RL.**
- **Como funciona.**
  - O professor (o M3a no SITL ou o oráculo M3b) rotula os estados que a ALUNA visita [S40].
  - A aluna é um MLP pequeno na camada de 50 Hz.
  - Depois afina-se com PPO a partir da inicialização por BC [S35].
- **Regra.** O professor só vê o que a aluna vê, nunca o vento futuro da fita nem o estado verdadeiro.
- **M7.** O porte vai para `firmware/nucleo/rede_mira.hpp` (PROPOSTA), com os pesos `constexpr` e verificação bit a bit no QEMU.

### 4.3 Comparação (juízo meu, a confirmar pela medição)

| método | esforço | risco | potencial | embarcável no M7? | depende de |
|---|---|---|---|---|---|
| M0 v5 | baixo (re-medir) | baixo | referência | parcial (braços e mira por portar) | fitas |
| M1 CMA-ES/bayesiana | baixo | baixo | médio (vento, cadência) | sim (só a `Config`) | M0 re-medido |
| M2a vetorização x | médio | baixo | médio (afastamento, pitch) | sim | — |
| M2b guinada diferencial | médio | médio (avaria de um braço) | alto (azimute, ~4× binário‡) | sim | M2a |
| M2c INDI/UDE | médio-alto | médio-alto (ruído, margem) | médio-alto (rajadas) | sim | M2a |
| M3a NMPC acados | alto | alto (portabilidade) | alto nos cantos do envelope | a medir | modelo reduzido |
| M3b oráculo MPPI | médio-alto | médio | diagnóstico (teto) | não | modelo JAX identificado |
| M4 RL residual / exterior | médio | médio | médio (z, ar vertical) | sim | campeão M1/M2 |
| M5 RL ponta a ponta | alto | alto (atratores) | incerto | rede sim, certificação difícil | — |
| M6 DAgger + RL | alto | médio | alto se o M3b mostrar folga | sim | M3 |

### 4.4 Ordem recomendada

1. **Pré-requisitos e M0 re-medido**, com e sem vento, com ≥ 62 tiros por célula. Junta-se o A/B grátis M0 vs M0-proj.
2. **M1.** É o mais barato e tem os melhores indícios de folga. Passa a ser o campeão contra o qual tudo se mede e fixa o orçamento de afinação de cada método.
3. **M2a → M2b.** Primeiro a estrutura e a física; cada passo vai em A/B emparelhado.
4. **M3b em paralelo, na GPU**, que o treino em CPU deixa ociosa. Se o campeão estiver a menos de ~10 % do oráculo na pior célula (limiar meu), não se avança para MPC nem destilação.
5. **M4**, só onde a medição mostrar fraqueza do clássico (z com ar vertical, rajadas).
6. **M2c**, se a rejeição de rajadas for o que limita a pior célula.
7. **M3a + M6**, só se o oráculo mostrar folga.
8. **M5** por último, como controlo científico.

A ordem é: primeiro o que é barato e físico, e IA só onde a medição o exigir (regra do dono). Cada degrau só entra se ganhar na pior célula, com o mesmo vento, sem perder em ar calmo.

---

## 5. Decisão de tiro e previsão do alvo (o acerto)

### 5.1 O pipeline de hoje (fases A–D)

| fase | onde | o que faz | medido |
|---|---|---|---|
| A · dados | `treinar_mira_articulada.py` (`fase_dados`), sobre `cenarios_mira.correr_episodio` | 3 cenários; bola OU a 0,2–0,8 m/s, 2,0–3,4 m; a cada decisão (50 Hz) um tiro **virtual** voado por `simular_bala` em 12 passos, com vento 0 | 180 episódios, 109 440 amostras em 54 s; rótulo virtual = tiro real em 99,45 % de 2362 tiros (só no stdout, não fica em JSON) |
| B · TensorFlow | `RedeConfiancaTiroTF` (30→64→64→1) e `RedeCorrecaoMiraTF` (30→64→64→2, resíduo ±0,5°) | entropia cruzada / Huber, AdamW, fica a melhor época | AUC 0,980; RMS (el, az) 0,72/0,62° → 0,40/0,36° |
| C · portão na GPU | JAX vmap + scan | 1248 regras; argmax da PIOR pontuação/min dos 3 cenários | 0,89 s; limiar 0,98725, fator 0,9, ω_max 0,8, intervalo 0,40 s |
| D · validação | sementes 90001–90004, bola Lissajous | malha fechada no MuJoCo, TF vs só-físico | TF 73/0 · 63/0 · 54/0 |

**Mais limites do pipeline.**
- As 8 juntas valem na prática 2 sinais (correlação 0,998–1,000 entre os ombros e entre os cotovelos).
- Pela queda de AUC por permutação, a rede vive de e_el, pitch_est, e_az, elev_req e incerteza.
- A ablação está confundida: `usar_tf=False` desliga as duas redes **e** troca os limiares, passando o intervalo a 0,70 s (teto de 85,7 vs 150 tiros/min).

### 5.2 Dados de treino: fita, perturbações e geometria contínua

- **Vento da fita.** Campo `fita_vento` em `OpcoesEpisodio` (PROPOSTA). Nunca usar os modos de vento do env, que tiram do `np_random` partilhado.
- **Rótulos fiéis.** Gravar o `opt.wind` no `gancho_fisica` e passá-lo a `simular_bala`. Estender o voo virtual de 12 passos (≈ 7,1 m) até à distância real: hoje um alvo além de ~7 m conta sempre como «erro», e o p99 da distância é 7,8 m.
- **Perturbações e falhas**, cada uma no seu fluxo de semente:
  - recolher com `aleatorizar=True` (massa ±5 %, inércia ±10 %, kf ±8 %, atraso 0–12 ms, ruído ×0,5–2);
  - DR do mecanismo (§6.8);
  - latência da câmara de 21 a 116 ms;
  - episódios com um cotovelo desligado ou um encoder preso.
- **Geometria contínua.**
  - Sortear dz_alvo de ≈ −1,45 a +1,25 m, mais `z_drone`, distância (1,8–3,2 m, com cauda até ~7 m), velocidade da bola, W, azimute do vento face à linha de tiro e latência, num desenho Sobol [S17].
  - Os 3 cenários ficam como estratos de relatório e de regressão.
  - Numa fração dos episódios, cortar o pitch a ±35° como o cockpit: o treino viu de −46° a +49°.
- **Características (PROPOSTA; obriga a re-treinar).**
  - Trocar as 8 juntas por q_ombro médio, q_cotovelo médio e o desacordo máximo entre braços (deteta falhas).
  - Acrescentar o vento estimado a bordo (`pert`), τ_cmd − τ medido, o |ω| RMS dos últimos 0,2 s e o indicador `saturado`.

### 5.3 Calibração e a regra de Chow

**A regra.** Com acerto +1, erro −K e abstenção 0, atirar compensa se P − K(1 − P) ≥ 0, ou seja, **P ≥ K/(1+K) = 0,952**. É a regra de rejeição de Chow [S43] e exige duas coisas:
- **P calibrada**, que hoje falha: na banda [0,95; 0,97) o acerto real é 0,914, o que dá 21 × 0,914 − 20 ≈ −0,80 pontos por tiro;
- **abstenção grátis**, que também não é exata: esperar custa 20 ms num fluxo de oportunidades com intervalo ≥ 0,40 s. O ótimo fica acima do piso; é o «valor de esperar».

**O que fazer.**
- `calibracao_mira.py` (PROPOSTA). Lê o `validacao_tf.npz`, que já tem p e y, e produz:
  - a fiabilidade em bins finos [0,90; 1,00];
  - o ECE global e o do topo;
  - o Brier e o NLL, por cenário e, depois, por faixa de vento.
- **Temperature scaling** [S44]. Ajusta-se T no banco de CALIBRAÇÃO; a bordo é só z/T antes da sigmoide.
  - Não mexe na AUC, mas muda quem passa o piso de Chow.
  - Se uma T global não chegar, usa-se T por grupo ou regressão isotónica.
- **Parâmetros gravados à parte** no JSON: `temperatura` e `limiar_espera`. O piso de Chow fica analítico e a grelha da GPU decide só o valor de esperar.
- **Comparar as funções de confiança** (rede, ensemble, P física) pela curva risco-cobertura e pela área AURC [S45].

### 5.4 Controlo de risco conformal: garantir uma taxa máxima de erros

**Objetivo.** Garantir «erros por tiro ≤ α», em vez de contar «0 erros vistos». A unidade permutável é o **episódio**, não o estado a 50 Hz [S46][S47].

**Método CRC** [S46]:
- perda L_i(λ) = erros_i(λ)/25, em [0, 1], onde 25 é o máximo de tiros em 10 s;
- escolhe-se λ̂ = inf{λ : n/(n+1)·R̂ₙ(λ) + 1/(n+1) ≤ α};
- isso garante E[L] ≤ α.

**Quanto custa.** Precisa de n ≳ 1/α − 1. Para α = 1/1500 são ~1500 episódios de calibração, ≈ 7–8 min de recolha com 22 processos (estimativa).

**Cuidado com a monotonia.** Com o intervalo mínimo, subir λ desloca os tiros no tempo, e a perda pode deixar de ser monótona. Usa-se a perda por **oportunidade** (tiro ∧ erro), que é monótona por construção, e confirma-se em malha fechada.

**Variantes.**
- **Por grupos** (Mondrian) [S47]: garantia por célula, para a média não esconder «acima com rajadas de 5 m/s».
- **Em linha, ACI** [S48]: λ_{t+1} = λ_t + γ(erro_t − α).
  - Os rótulos chegam em retrospetiva: ~150 ms depois, a trajetória suavizada da bola diz se um tiro naquele instante teria acertado.
  - Compara-se λ fixo com ACI sob a mesma fita.

**Limite.** A garantia só vale para a distribuição do banco de calibração. As fitas de STRESS medem a degradação; não ficam garantidas.

### 5.5 Ensemble e abstenção fora da distribuição

- **Ensemble.** M = 5 redes de confiança, com sementes de inicialização diferentes [S49].
  - A bordo decide a média dos logits (já com T).
  - O desvio-padrão dos logits é o portão epistémico, com um limiar τ_d.
  - Calibra-se τ_d sem vento e verifica-se com vento, porque a calibração degrada sob mudança de distribuição [S50].
- **Detetores baratos complementares** [S51]:
  - Mahalanobis das características;
  - vento estimado fora do envelope de treino;
  - NIS do rastreador;
  - desacordo entre braços.
- **Política fora da distribuição.** Abster-se, ou cair no portão físico conservador, e registar o estado para a próxima ronda de treino.

### 5.6 Previsão do alvo: torneio de preditores

**O horizonte.** O que conta é T ≈ latência da câmara + gatilho (16 ms) + voo (~8 ms): ≈ 140 ms com a Pi e ≈ 45 ms com o DCMI do Portenta. Uma aceleração não modelada de 3 m/s² dá ≈ 30 mm de falha com a Pi e ≈ 3 mm com o DCMI, para um raio de colisão de 54,5 mm (estimativa). **A latência pesa mais do que o filtro.**

**O torneio** troca só o preditor; o portão, as sementes e as fitas ficam iguais.

| id | preditor | nota |
|---|---|---|
| P0 | KF de aceleração constante (`RastreadorAlvo` / `FiltroAlvo` em `alvo.hpp`) | base |
| P1 | P0 + resíduo `RedeCorrecaoMiraTF` | o que voa hoje |
| P2 | Singer (aceleração correlacionada) [S52] | +1 parâmetro |
| P3 | memória finita (mínimos quadrados nos últimos N frames) [S52] | robusto a erro de modelo |
| P4 | IMM CV + CA + curva coordenada [S53] | a probabilidade de manobra entra como veto |
| P5 | GRU/TCN pequeno (~1–5 mil parâmetros) | treinado com famílias de trajetória semeadas |

**Métricas e famílias de teste.** Mede-se o erro do ponto previsto no horizonte T (p50/p95) por família de trajetória: OU, Lissajous com parâmetros sorteados e manobras em degrau. O teste inclui uma família **nunca vista**.

**Ideias à volta do preditor.**
- **Disparo agendado** (PROPOSTA): ordenar o tiro para o instante previsto em que a boca cruza o ponto de impacto, contra o atual «só atira quieto».
- **Linha de base sem pesos** [S54]: P física = 1 − exp(−r_col²/2σ²), com σ propagado das covariâncias. Serve como portão, como característica ou como segundo voto. É a candidata natural ao Arduino.

### 5.7 Portão pelo pior caso alargado ao vento (CVaR)

- **Objetivo novo.** Hoje maximiza-se o pior de 3 números, que é o limite do CVaR e fica dominado por um episódio ruidoso. Proposta: maximizar o **CVaR₁₀ %** sobre as células (estrato × fita) [S11], ou o limite inferior do IC da pior célula.
- **Alargar a grelha** onde o ótimo bateu na fronteira:
  - ω_max acima de 0,8 rad/s;
  - intervalos de 0,30–0,35 s, só depois do recuo antecipado.
- **Fechar a malha.** Correr no MuJoCo as 10 melhores regras do contrafactual, nas MESMAS fitas, com os portões vz/vxy/roll incluídos.
- **Rondas na política** (PROPOSTA `--recolher-com-portao`): recolher com o portão implantado e re-treinar 2–3 vezes.

### 5.8 Torneio da decisão

| id | metodologia | pergunta |
|---|---|---|
| R0 | só portão físico | quanto vale a IA? |
| R1 | atual: TF + grelha GPU | campeão em ar calmo |
| R2 | R1 + temperatura + piso de Chow + limiar de espera | mais tiros com os mesmos erros? |
| R3 | R2 + λ por CRC | taxa de erros garantida |
| R4 | R3 + ensemble + fora da distribuição | menos erros com vento forte? |
| R5 | R4 + IMM (P4) ou sequencial (P5) | menos falhas com o alvo a manobrar? |
| R6 | P física analítica, sem pesos | linha de base do Arduino |
| R7 | R4 + ACI em linha | erro estável quando o regime de vento muda? |
| R8 | R4 + disparo agendado | mais cadência sem mais erros? |

**Duas versões de cada metodologia que aprende.**
- Treina-se uma vez com os dados de hoje (ar calmo) e outra com a fita + DR.
- Assim mede-se o que vale treinar com vento.

**A ablação fatorial.**
- Fatores: {confiança} × {correção} × {limiares com/sem TF} × {intervalo 0,30/0,35/0,40/0,55 s}.
- Separa o teto de cadência do mérito do portão.

**Critério de adoção**, por ordem:
1. 0 quedas;
2. limite de Clopper–Pearson < 4,76 % em cada célula do teste (meta 1 %, depois 0,5 %);
3. CVaR₁₀ % não pior do que o do campeão;
4. média com IC emparelhado que exclua 0;
5. regressão em ar calmo ≤ 2 %;
6. cabe no M7.

### 5.9 Quando re-treinar e implantação no M7

**Gatilhos de re-treino:** qualquer mudança de dinâmica ou de perceção.
- Exemplos: build/peças, ganhos e filtros do FC (incluindo o anti-tremor), interface do firmware, parâmetros dos braços, latência da câmara, arma, características, versão do banco de fitas.
- A prova: só a passagem da margem de 30° para 45° levou a validação de 112,5/109,5/93,0 para 109,5/94,5/81,0 acertos/min.

**Impressão digital (PROPOSTA `impressao_digital_mira()`).**
- Contém o `sha256` do build, das peças, do `config.hpp`, da configuração voada, da latência, dos parâmetros e das características, mais o hash do banco e o git SHA.
- Se não bater ao carregar: `usar_tf = False`, com aviso no HUD.
- A automação vai no `evoluir_e_benchmark.py --check`.

**Pipeline hermético.**
- A fase A não lê o modelo anterior (hoje lê: `treinar_mira_articulada.py:73`).
- O `--episodios` por omissão (40) passa a coincidir com o documentado (60).
- Determinismo do TF ligado.

**Implantação no Cortex-M7.**
- **Formato.** MLP float32 escrita à mão em `firmware/nucleo/portao_tiro.hpp` (PROPOSTA), com os pesos `constexpr` gerados do JSON.
- **Tamanho.** 12 483 parâmetros ≈ 49 KB e 12 224 MAC por decisão; com o ensemble de 5, ≈ 121 KiB (aritmética). Cabe nos 2 MB de flash.
- **Latência.** 25–100 µs a 480 MHz, ≤ 0,5 % dos 20 ms (estimativa); mede-se com `DWT->CYCCNT`.
- **Falta `expf`** na `libm_minima.cpp`: ou se acrescenta, ou se usa ReLU.
- **Verificação** no QEMU (`qemu_alvo.py`): 100 % de decisões iguais às do NumPy.
- **TFLM + CMSIS-NN** só para modelos maiores [S55].
- **Quantização int8** [S56]: medir a concordância perto do limiar, onde dP/dz é pequeno e os tiros de fronteira trocam.
- **Partição** [S57]: o M7 corre a cascata, o rastreador e o portão; o M4, a visão.

---

## 6. Melhorias do mecanismo dos braços

Cada ideia mede-se com o protocolo da secção 7: as mesmas fitas, A/B emparelhado, com e sem vento.

### 6.1 Recuo antecipado pelos cotovelos

O instante do tiro é conhecido (latência do gatilho de 16 ms, estimada no catálogo), assim como J = 1,916 N·s e a direção do cano.

**A proposta.** Inclinar o empuxo pelos cotovelos (o atuador rápido) ~8–10° durante ~0,25–0,3 s, de forma que m·g·sen δ·t ≈ J (estimativa).

**Variantes a comparar:**
- só realimentação, como hoje (28–31 cm de afastamento);
- feed-forward pelos cotovelos;
- feed-forward + pré-compensação vertical, crítica no «acima».

O compensador v3/v4 está desligado no articulado, porque o fazia divergir (`sim_view.py:2341-2348`).

**Métricas:**
- afastamento por tiro;
- recuperação (a métrica nova, sem piso);
- se permite baixar o intervalo de 0,40 s. Esse piso existe porque a 4 tiros/s a força média do recuo, 7,7 N, pede ~10° de inclinação permanente (`treinar_mira_articulada.py:370-372`).

### 6.2 Guinada por inclinação diferencial

É o M2b da secção 4: ±5° nos cotovelos → 2,63 N·m‡, contra os ~0,65 N·m de teto atual.

**Efeito esperado:** mais rapidez a apontar em azimute (a mira pede até 0,9 rad/s e a cascata corta a 0,50 rad/s) e menos tempo até ao 1.º tiro.

**Métricas:** erro de azimute, tempo até ao 1.º tiro, tiros/min, `kFlagDifEscalado` e energia dos servos.

### 6.3 Vento em x pelos servos e posição a favor do vento

**O que já acontece.** O vento em x já é vetorizado pelos servos sem mexer na mira, mas o benchmark quase não o exercita: só usa 90° e 45°.

**O que acrescentar ao benchmark:** células de vento de **proa e de cauda** (0°/180°).

**Ideia a medir.** Ao manter a distância à bola (`_manter_distancia_bola`), o drone podia escolher o lado da bola em que o vento fica alinhado com o eixo x do corpo. Assim os servos absorvem-no, e não o rolamento. Os critérios: o custo em tempo de reposicionamento contra o ganho no desvio.

### 6.4 Envelopes alinhados

**Hoje os envelopes não batem:**
- coplanar |τ| ≤ 34,14°‡;
- cockpit ±35° (`sim_view.py:2538`);
- `tau_max` de 100° (corte a ±97°);
- DR e validação a ±25°.

**O risco.** Como τ = θ_n − θ_corpo, uma inclinação de empuxo até 30° pode empurrar o τ para fora do coplanar e até saturar o cotovelo (±60°).

**Proposta:**
- `tau_max` = coplanar;
- uma IK de melhor esforço quando o ombro satura;
- recortar o pitch do corpo em função da inclinação de empuxo pedida.

### 6.5 Anti-windup com os servos e trim do CM

- **Anti-windup.** Passar à cascata o τ alcançável (limite e taxa), para a saturação dos servos entrar no integral de velocidade como a de `tilt_max`.
- **Trim.** Feed-forward f(τ) do deslocamento do CM (0,475 N·m a 25°, 0,62 N·m a 34°‡).
  - Métrica: o tempo até ±1° depois de cada mudança de mira.
  - O escalonamento dos ganhos com Iyy(τ) é secundário (−3 a −6 %‡).

### 6.6 Cotovelo subamortecido

**O problema.** Com `kd_duty` 0, a estimativa linear dá ζ ≈ 0,36‡ e ω_n ≈ 75 rad/s (~12 Hz)‡.

**Proposta.**
- Um teste de degrau de τ (sobre-elevação, assentamento, energia) em `teste_bracos.py`.
- Comparar `kd_duty` > 0 com feed-forward de velocidade.

### 6.7 Margem de fase da configuração que voa

**O problema.** A margem de 45° só está garantida no modelo de projeto. Com o anti-tremor aplicado depois, ficam 41,0°‡, e o `w_pert` passa de 13,38 para 3,05.

**Proposta.**
- Aplicar o `fc.tau_de_projeto` com os filtros que voam, ou co-projetar filtros e margem.
- Varrimento a fazer: margem 40–55°, PT1 vs notch dinâmico pelo RPM.

**Dados que já existem e o que falta.** A 50° o tremor baixa para 1,27 °/s, mas o custo em acertos não foi medido. Métricas: ω_RMS, recuperação, tiros/min, vento.

### 6.8 DR e realismo do mecanismo (sim-to-real)

**DR com semente própria (fluxo `mecanismo`):**
- `kp_duty` ±30 %;
- folga do sem-fim 0,25–1,0°;
- rigidez 2500–10 000 N·m/rad;
- μ 0,08–0,12 (verificando λ < φ);
- viés dos encoders por episódio;
- folga interna de 0,25° do cotovelo (`Servo.folga` é carregada mas não usada);
- latência e jitter do RS-485;
- queda dos 24 V.

**Modelo:**
- corrigir o barramento a 250 Hz (`round(2,5) = 2`): 200 Hz reais, ou declarar os 250 Hz;
- deslizamento do sem-fim por vibração (hoje o autobloqueio é só estático);
- temperatura e binário contínuo (0,52/4,13 N·m nunca impostos).

**Ressonâncias.** A passagem das pás deste build é 154,7 Hz‡ (486 rad/s, 2 pás), e não os «≈ 130 Hz» da nota do catálogo. O modo do braço (~30 Hz estimado) tem de ser rederivado.

**Bancada.** Quando houver hardware, medir a rigidez e a folga reais e corrigir o `componentes.json`.

### 6.9 Falhas por braço

**O que não está testado:**
- um cotovelo desligado (o mastro, com o CM 0,179 m acima do eixo, tomba até ao batente);
- um encoder preso;
- desacordo entre braços.

**Porque é grave.**
- O firmware só vê a média, por isso um erro de um braço fica diluído 4×.
- A telemetria «ligados» só lê o servo 0 (`lab/drone_rpi/planta.py:1477`).

**Proposta.**
- **Deteção por braço:** |alvo − medida|, corrente anómala, `saturado`, `ligado`.
- **Reconfiguração:** voltar a rígido e aterrar, ou compensar a guinada com os braços restantes.
- **Testes novos** com mutação em `teste_bracos.py`.

### 6.10 Interlock de aterragem

As pernas estão nos braços. Proposta: juntas a 0 (modo rígido) abaixo de uma altura ou ao descer para o chão.

### 6.11 Hardware alternativo (por fórmula fechada)

**Ombro com coroa mais curta.**
- O autobloqueio depende do ângulo de avanço λ, não da razão N.
- Uma coroa N 10–15 acelera o ombro para 31–21 °/s e mantém o autobloqueio.
- A saída fica em τ_b·N·η = 10,3–15,5 N·m‡, contra os ~4,4 N·m da pairagem.

**Saltos grandes de mira.**
- Hoje 50° de mira pedem ~58,8° de ombro: ≈ 4,2 s a 14 °/s, com o cotovelo (±60°) a carregar a diferença.
- Comparar também o XH430-V350 e o XH540, que já estão no catálogo.

### 6.12 Energia e desgaste

**Números de hoje.**
- Espera: 8,35 W na bateria.
- A mirar: 15–36 W.
- Sem a zona morta do ombro, os ombros traseiros puxavam 0,18 A em pairagem.

**Proposta.**
- Wh/acerto e curso/min como métricas de Pareto.
- Penalizá-las no objetivo do M1.
- Testar zonas mortas e filtros do ombro.

### 6.13 Porte para C++

**Conteúdo.** `firmware/nucleo/bracos.hpp` (PROPOSTA):
- IK com `atan2f`/`sqrtf`, porque o `asin` é proibido no núcleo;
- macro-mini;
- limites;
- HAL do RS-485;
- parâmetros na `Config`.

**Orçamento.** Entra no orçamento de flash do `teste_nucleo.py`, como os +1410 B da interface 4.

### 6.14 Realismo da arma

**O que falta modelar:** carregador de 15 tiros, recarga e massa que diminui (~140 g de munição).

**Métricas por carregador:** 15/15 acertos e o tempo até 15 acertos. O piso é 14 × 0,40 = 5,6 s.

---

## 7. Metodologia experimental — comparar e chegar à perfeição

As metodologias comparam-se como num ensaio controlado:
- **mesma adversidade** (CRN) e **mesmo orçamento** para todas;
- **regra de decisão escrita antes de medir**, como o `CRITERIO` de `avaliar_vento.py` e o protocolo que decidiu o laço vertical;
- **veredicto em sementes nunca vistas**.

### 7.1 Desenho emparelhado e análise

- **Blocos e condições.** Bloco = fita-mestra. Todos os métodos correm todos os blocos, com e sem vento.
- **Sementes de agente.** São ≥ 5 por método, num fluxo separado do do ambiente [S6]. A semente não é um hiperparâmetro: reportam-se todas.
  - O mesmo algoritmo já deu curvas estatisticamente diferentes em dois grupos de 5 sementes [S4]; um trabalho robótico avalia em 20 [S13].
  - Um método determinístico sem afinação conta com 1 semente.
- **Análise:**
  - IQM de pontos/min, com IC a 95 % por bootstrap **estratificado** (estratos altura × vento) e perfis de desempenho [S3];
  - entre dois métodos, a diferença por bloco, com Wilcoxon de postos sinalizados, IC emparelhado e P(A > B) [S3]. Nunca testes de amostras independentes [S1];
  - com k > 2 métodos, Friedman por blocos (o desenho do irace [S9]) com correção de Holm;
  - a cauda pelo CVaR 10 % [S11];
  - os erros por Clopper–Pearson, por célula e por episódio;
  - a correlação ρ entre métodos: o ganho do emparelhamento é ≈ 1/(1−ρ) [S2];
  - para o dono, um intervalo de **tolerância** («em 90 % das fitas a pontuação fica entre X e Y») [S6].
- **Cuidado com o IQM.** Corta os 25 % piores, precisamente onde caem os −20 por erro. Por isso nunca decide sozinho: os erros são restrição, e a cauda mede-se pelo CVaR.

### 7.2 Orçamento igual e poda cedo

**Unidade comum:** passos de decisão (50 Hz). Um episódio de avaliação tem ≈ 17,2 s simulados, ≈ 860 passos.

**O teto por família de métodos:**
- RL: os mesmos passos por semente;
- caixa-preta: os mesmos episódios de CALIBRAÇÃO;
- supervisionado: os mesmos passos de recolha + um teto de tempo de GPU;
- afinação de hiperparâmetros: o mesmo orçamento para todos [S32].

**Corridas** [S9] para os parâmetros contínuos (portão, braços, `w_pert`): avaliar bloco a bloco e deixar o Friedman eliminar os piores.

**Successive halving com η = 3** [S10]:
- 27 candidatos × 48 episódios → 9 × 144 → 3 × 432;
- são 3888 episódios, contra 11 664 sem poda.

**O RL não se poda por curvas precoces**, por causa do atrator «sentar no chão». Arranca-se a quente.

### 7.3 Torneio por fases

| fase | banco | sementes de agente | o que decide |
|---|---|---|---|
| 0 · pré-requisitos | — | — | identidade das fitas; teste A/A; o v5 reproduz-se numa worktree limpa do HEAD |
| 1 · triagem | CALIBRAÇÃO | 1 | poda por Friedman ou halving |
| 2 · avaliação completa | VALIDAÇÃO | ≥ 5 | a regra lexicográfica da secção 2 |
| 3 · teste final | TESTE selado (uma vez por geração) | o artefacto escolhido por regra pré-registada | certificação e geração vN |

**Lição da fase 0.** Compara-se sempre contra uma worktree limpa do HEAD [S4]. A tabela antiga dava 40/44 tiros/min ao v3/v4, e o HEAD mede 28/28.

**Depois da fase 3,** o banco de teste passa para a regressão e gera-se outro para a geração seguinte.

### 7.4 Ablações (emparelhadas contra o M0, nos mesmos blocos)

| ablação | como se liga | pergunta |
|---|---|---|
| sem portão TF | `usar_tf = False`, mais uma flag nova para separar os limiares (PROPOSTA) | quanto vale a rede, descontado o teto de cadência |
| sem correção | `desligar_correcao = True` (existe, mas nunca é usado) | quanto vale o resíduo de ±0,5° |
| braços travados | `ControladorBracos.definir_modo("rigido")`, com a MESMA perceção e o mesmo intervalo | o ganho dos braços, separado do ganho de informação (o v4 decide com oráculo) |
| sem observador de vento | `w_pert` = 0 · 3,05 · 13,38 | o observador ajuda com tiros e vento? |
| cadência | `cooldown_s` 0,30 · 0,35 · 0,40 · 0,55 s | quanto do ganho vem do teto de cadência |
| informação privilegiada | estimador em vez do estado verdadeiro | quanto se perde no hardware real |

### 7.5 Matriz de experiências

| fator | amostragem | estratos de análise |
|---|---|---|
| método | M0 + desafiantes + ablações | — |
| vento | fita nula · fita de vento (0–5 m/s, regimes que mudam a cada 1,5–4,5 s) | 2 |
| altura relativa Δh = z_alvo − z_drone | contínua, U[−1,2; +1,0] m | acima · igual · abaixo |
| velocidade da bola | 0,2–0,8 m/s: OU semeado e Lissajous com fase e amplitude da semente | ≤ 0,4 · 0,4–0,6 · > 0,6 |
| distância horizontal | U[1,8; 3,2] m | ≤ 2,5 · > 2,5 |

**36 células:** 3 alturas × 3 velocidades × 2 distâncias × 2 condições de vento. Dentro de cada estrato, os pontos saem de um Sobol embaralhado [S17], e os cantos raros aparecem numa proporção fixa, não por sorte.

**Células de fronteira.** Com Δh = −1,2 m e a bola a 1,8 m, a mira pede ~33,7° de elevação (estimativa): em cima do limite coplanar e do corte de 35°. É aí que os métodos se distinguem.

**Dimensionar n.** Faz-se por análise de potência com σ_d medido num piloto: n = ((1,96 + 0,84)·σ_d/Δ)² blocos [S5]. Com σ_d = 10, são 32 blocos para Δ = 5 e 88 para Δ = 3.

**Comparação e certificação são passos separados.**
- Os métodos comparam-se com ≥ 5 sementes na VALIDAÇÃO.
- A certificação de erros faz-se só com o artefacto que vai voar, no TESTE.

### 7.6 Ligação ao benchmark oficial

**O que fica.** O `benchmark_evolucao.py` mantém-se como trilho legado de regressão: 43,6 s, gerações v1–v5, 6 presets e 3 cenários. A métrica de vento dele mede dispersão.

**Gerações v6+.** Saem só do torneio, com dois trilhos: sem vento e com fita.
- O PROPOSTA `torneio.py` escreve três ficheiros em `out/torneio/<ronda>/`:
  - `plano.json`: os critérios, congelados antes de medir;
  - `episodios.jsonl`: uma linha por método × semente × bloco;
  - `resumo.json`.
- O `evolucao_estabilidade.json` ganha um bloco `torneio`.

**Campos mínimos de cada registo** [S4]:
- **origem:** `git_sha`, `worktree_limpa`, `build`, `hash_banco_fitas`, `banco`, `bloco`, `semente_agente` e as versões;
- **resultado:** `celula`, `acertos`, `erros`, `tiros`, `pontos_min`, `afast_xy_p95`, `dz_max`, `omega_rms`, `jitter`, `wh_acerto`, `curso_min`, `frac_saturado`, `pitch_max`;
- **só no resumo:** IQM com IC, CVaR, limite de Clopper–Pearson e ρ.

**Gráfico.** O `evolucao_drone.png` passa a ter barras de IC e o par sem/com vento. O `--check` da skill passa a exigir o bloco `torneio` nas gerações v6+ (PROPOSTA).

**Regressão.**
- Mantém-se a que existe: `teste_bracos.py --mira`, `teste_nucleo.py`, `bench_treino.py identidade` e o §1b do `teste_vento_classico.py`.
- O PROPOSTA `teste_torneio.py` junta quatro provas:
  1. identidade das fitas;
  2. bancos disjuntos;
  3. teste A/A (o mesmo método com dois grupos de sementes dá um IC que contém 0);
  4. mutação estatística: um «método» com 1° de viés na mira tem de perder.

### 7.7 Quanto custa nesta máquina

A máquina tem um i9-14900HX com 32 CPUs lógicos, 31 GiB de RAM e uma RTX 4070 de 8 GB. O TF instalado é de CPU; a GPU entra pelo JAX.

| tarefa | débito medido | custo (estimativa) |
|---|---|---|
| episódio de avaliação | 180 em 54 s com 22 processos (≈ 3,3/s) | triagem de 1 candidato ≈ 15 s; halving completo ≈ 19 min |
| avaliação completa de 1 método | idem | 64 blocos × 2 ventos × 5 sementes ≈ 3,2 min |
| certificação do campeão | idem | 36 células × 23 episódios ≈ 4,1 min |
| treino da mira TF (fases A–D) | ~4 min | ≈ 20 min para 5 sementes |
| portão na GPU | 1248 regras em 0,89 s | não é o gargalo |
| sep-CMA-ES da mira e dos braços | IBVS: 12 gerações em 40,5 min | ≈ 15 min para 30 gerações |
| PPO no articulado | 1416 passos/s (16 envs) | 3 M passos ≈ 35 min por semente; 5 métodos × 5 sementes ≈ 15 h |
| banco de fitas | — | 1024 × 60 s ≈ 37 MB |

**Duração de uma ronda.** Sem RL, ≈ 2 h; com RL, mais ≈ 15 h, de noite.

**Regras de uso da máquina.**
- As métricas em tempo simulado não sofrem com a carga.
- Fps e latências só se medem com a máquina livre (regra do `CLAUDE.md`).
- Os valores por omissão do `ab_treino.py` lançam 40 processos para 32 CPUs lógicos. É preferível usar ≤ 22 processos na avaliação.

---

## 8. Roteiro faseado

Cada ronda repete as fases 1–4 até ao critério de paragem da secção 2. As estimativas de esforço são minhas.

**Fase 0 — infraestrutura e higiene** (2–4 dias de trabalho; computação desprezável).
- *Entregáveis:*
  - `sementes.py`, `vento_semeado.py` e `BancoFitas`;
  - fluxos separados em `env.py`/`env_real.py`, atrás de uma opção, com uma nova referência bit a bit;
  - `teste_vento_semeado.py` (T1–T8, com mutações);
  - a fita na mira: `OpcoesEpisodio.fita`, vento real nos tiros virtuais;
  - fim do oráculo na mira;
  - impressão digital do modelo da mira, fase A hermética e determinismo do TF;
  - `--episodio-s` e `--build` onde faltam;
  - métricas novas: recuperação sem piso, desvio médio no vento, Wh/acerto, curso/min, saturação, tempo até ao 1.º tiro.
- *Critério:*
  - T1–T8 verdes, e as mutações falham;
  - rígido × articulado com a mesma fita: 120/120 passos de vento iguais (hoje 0/120);
  - o teste A/A passa.

**Fase 1 — linhas de base** (≈ 1 h de computação).
- *Entregáveis:*
  - M0 e M0-proj, R0 e R1, com e sem vento, nos bancos de validação, com ≥ 62 tiros por célula;
  - o `avaliar_vento.py` com `--build articulado_15pol_mn5006` e a configuração anti-tremor;
  - um piloto para medir σ_d e ρ.
- *Critério:* tabela completa por célula, com IC e Clopper–Pearson, e n dimensionado por potência.

**Fase 2 — candidatos baratos** (≈ 1 dia de computação).
- *Entregáveis:*
  - M1 (sep-CMA-ES);
  - R2/R3 (calibração + CRC);
  - M2a (anti-windup, trim, envelopes);
  - recuo antecipado (6.1);
  - cotovelo amortecido (6.6);
  - co-projeto margem/filtros (6.7).
- *Critério:* promoção pela regra lexicográfica; a pior célula com vento melhora com um IC emparelhado que exclui 0; regressão em ar calmo ≤ 2 %.

**Fase 3 — estrutura e candidatos caros** (2–4 noites de computação).
- *Entregáveis:*
  - M2b (interface 5) e M2c;
  - oráculo M3b (o teto por célula);
  - M4 residual/exterior (5 sementes × 3 M passos);
  - R4/R5 (ensemble, fora da distribuição, IMM);
  - disparo agendado;
  - testes de falha por braço.
- *Critério:* o mesmo da fase 2. Se o campeão estiver a menos de ~10 % do oráculo na pior célula, M3a/M6 ficam de fora.

**Fase 4 — torneio final e benchmark oficial** (≈ 2 h, mais o RL).
- *Entregáveis:*
  - teste selado nas 36 células;
  - certificação < 1 %, que exige ≥ 299 tiros sem erro por célula;
  - a geração v6 com o bloco `torneio`;
  - o `evolucao_drone.png` com IC e o par sem/com vento;
  - README/AGENTS/CLAUDE e CoALA atualizados.
- *Critério:* o `--check` da skill passa com o bloco `torneio`.

**Fase 5 — caminho para o hardware.**
- *Entregáveis:*
  - `bracos.hpp` e `portao_tiro.hpp` (+ `expf`);
  - QEMU bit a bit;
  - DWT na placa;
  - hardware-in-the-loop;
  - medição em bancada da folga e da rigidez, com correção do `componentes.json`.
- *Critério:*
  - 100 % de decisões iguais entre C++ e NumPy;
  - latência medida na placa;
  - o torneio repetido com os parâmetros medidos.

---

## 9. Riscos e armadilhas

- **Abster-se para sempre.** Um portão que nunca atira tem 0 erros. Por isso a cadência e os pontos/min da pior célula são o objetivo, e os erros são a restrição. No RL, vigiar o atrator «sentar no chão».
- **Decorar a fita ou o benchmark.** Mitigação:
  - banco grande;
  - nenhum tempo absoluto na observação;
  - famílias de trajetória da bola semeadas, com uma família nunca vista no teste;
  - a diferença entre TREINO e TESTE vigiada como alarme.
- **A semente não é o vento.** Guarda-se a fita materializada, com o `sha256` e a versão do NumPy.
- **Não-determinismo TF/XLA/GPU.** Ligar o determinismo ou medir a variância entre ≥ 5 treinos [S12].
- **Múltiplas comparações.** Holm e um plano pré-registado (`plano.json`); nada de escolher a métrica depois de ver os dados.
- **Unidade estatística.** É o episódio ou a fita, não o tiro.
- **Sim-to-real.** Os «0 erros» de hoje dependem de várias idealizações:
  - perceção idealizada;
  - nada de carregador;
  - folga, rigidez e latência do RS-485 estimadas.

  A fase 5 e a DR do mecanismo atacam isso.
- **Regra do simulador sempre físico.**
  - Os tiros virtuais são só RÓTULOS: não mexem no estado.
  - A fita e o adversário RARL atuam pelo vento, que é uma força física no `mj_step`.
  - Nada de teleporte nem de cinemática.
- **Licenças.**
  - Só o PX4 (BSD-3) é copiável. ArduPilot, Betaflight e Crazyflie são GPLv3: reimplementar.
  - Verificar a licença do código gerado pelo acados antes de o vendorizar.
- **Medições de desempenho.** Fps e latência medem-se só com a máquina livre.

---

## 10. Fontes, ficheiros e verificação

### 10.1 Fontes web (conteúdo `untrusted`, só citado)

Estatística e desenho experimental
- [S1] Keeping the Noise Down: Common Random Numbers for Disease Simulation Modeling — https://pmc.ncbi.nlm.nih.gov/articles/PMC2761656
- [S2] Some Guidelines and Guarantees for Common Random Numbers (Glasserman & Yao, Management Science 1992) — https://www.semanticscholar.org/paper/Some-Guidelines-and-Guarantees-for-Common-Random-Glasserman-Yao/b6ecc62a5745102605733181051ea10fecac5676
- [S3] Deep Reinforcement Learning at the Edge of the Statistical Precipice (NeurIPS 2021), página do projeto rliable — https://agarwl.github.io/rliable
- [S4] Deep Reinforcement Learning that Matters (AAAI 2018) — https://arxiv.org/html/1709.06560v3
- [S5] How Many Random Seeds? Statistical Power Analysis in Deep RL Experiments — https://inria.hal.science/hal-01890154/file/1806.08295.pdf
- [S6] Empirical Design in Reinforcement Learning (JMLR 2024) — https://arxiv.org/abs/2304.01315
- [S7] A Look at the Rule of Three (The American Statistician, 1997) — https://www.semanticscholar.org/paper/ec1b65ab49420fffb81af170f50ee8bb889323ad
- [S8] Limits when p or f are 0 (InfluentialPoints) — https://influentialpoints.com/Training/limits-when-p-or-f-are-zero.htm
- [S9] The irace package: Iterated racing for automatic algorithm configuration (2016) — https://ideas.repec.org/a/eee/oprepe/v3y2016icp43-58.html
- [S10] Hyperband: A Novel Bandit-Based Approach to Hyperparameter Optimization (JMLR 18, 2018) — https://www.jmlr.org/papers/volume18/16-558/16-558.pdf
- [S11] Near-Minimax-Optimal Risk-Sensitive Reinforcement Learning with CVaR (ICML 2023) — https://proceedings.mlr.press/v202/wang23m/wang23m.pdf
- [S12] Deterministic Implementations for Reproducibility in Deep Reinforcement Learning — https://arxiv.org/html/1809.05676v5
- [S13] Deep Black-Box Reinforcement Learning with Movement Primitives (CoRL 2022) — https://proceedings.mlr.press/v205/otto23a/otto23a.pdf

Vento, sementes e robustez
- [S14] Parallel random number generation — NumPy Manual — https://numpy.org/doc/2.4/reference/random/parallel.html
- [S15] Parallel Random Numbers: As Easy as 1, 2, 3 (Random123) — https://www.thesalmons.org/john/random123/papers/random123sc11.pdf
- [S16] jax.random module — JAX documentation — https://docs.jax.dev/en/latest/jax.random.html
- [S17] scipy.stats.qmc.Sobol — SciPy Manual — https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html
- [S18] Markov-switching autoregressive models for wind time series — https://www.sciencedirect.com/science/article/abs/pii/S1364815211002222
- [S19] Discrete Wind Gust Model — Aerospace Blockset — https://www.mathworks.com/help/aeroblks/discretewindgustmodel.html
- [S20] Dryden Wind Turbulence Model (Continuous) — Aerospace Blockset — https://www.mathworks.com/help/aeroblks/drydenwindturbulencemodelcontinuous.html
- [S21] Wind Shear Model — Aerospace Blockset — https://www.mathworks.com/help/aeroblks/windshearmodel.html
- [S22] Verifying Implementation of the Dryden Turbulence Model and MIL-F-8785 Gust Gradient (NASA) — https://ntrs.nasa.gov/api/citations/20190000875/downloads/20190000875.pdf
- [S23] Spatio-Temporal Wind Modeling for UAV Simulations — https://arxiv.org/pdf/1905.09954
- [S24] Robot Learning From Randomized Simulations: A Review — https://pmc.ncbi.nlm.nih.gov/articles/PMC9038844
- [S25] Solving Rubik's Cube with a robot hand (ADR) — https://openai.com/index/solving-rubiks-cube
- [S26] Robust Adversarial Reinforcement Learning (ICML 2017) — https://proceedings.mlr.press/v70/pinto17a.html

Controlo
- [S27] Cascaded incremental nonlinear dynamic inversion for MAV disturbance rejection — https://arxiv.org/html/1701.07254v2
- [S28] Improving INDI for Input Nonaffine Systems via Learning-Based Nonlinear Control Allocation — https://arxiv.org/html/2604.06337v1
- [S29] A Novel Overactuated Quadrotor UAV: Modeling, Control and Experimental Validation (Ryll et al.) — https://inria.hal.science/hal-01076419/file/2014-cst-ryll.pdf
- [S30] The Voliro Omniorientational Hexacopter (Kamel et al., IEEE RAM 2018) — https://ui.adsabs.harvard.edu/abs/2018IRAM...25d..34K/abstract
- [S31] Nonlinear Model Predictive Control of Tiltrotor Quadrotors using Feasible Control Allocation — https://link.springer.com/article/10.1007/s10846-025-02255-y
- [S32] Reaching the Limit in Autonomous Racing: Optimal Control versus Reinforcement Learning — https://arxiv.org/html/2310.10943v2
- [S33] Aggressive driving with model predictive path integral control (MPPI) — https://www.semanticscholar.org/paper/Aggressive-driving-with-model-predictive-path-Williams-Drews/528a8ef7277d81d337c8b4c4fe0a9df483031773
- [S34] Towards a modular software package for embedded optimization (acados) — https://www.sciencedirect.com/science/article/abs/pii/S2405896318327204
- [S35] Revisão sobre a síntese de MPC e RL (título truncado no resultado da pesquisa) — https://www.sciencedirect.com/science/article/pii/S1367578826000015
- [S36] Disturbance Estimation and Rejection for High-Precision Multirotor Position Control — https://arxiv.org/html/1908.03166
- [S37] Residual Reinforcement Learning for Robot Control — https://arxiv.org/pdf/1812.03201
- [S38] Champion-level drone racing using deep reinforcement learning (Swift) — https://www.nature.com/articles/s41586-023-06419-4
- [S39] Full state quaternion-based observer control for multirotor aerial vehicles (UDE; ICUAS 2025) — https://cnrs.hal.science/hal-05386252/file/ICUAS_2025_Observer.pdf
- [S40] Visual attention prediction improves performance of autonomous drone racing agents (DAgger com especialista MPC) — https://pmc.ncbi.nlm.nih.gov/articles/PMC8887736
- [S41] RL-based Control of UAS Subject to Significant Disturbance — https://research.utwente.nl/files/488604419/p2024_RL_for_Predectable_dist.pdf
- [S42] DATT: Deep Adaptive Trajectory Tracking for Quadrotor Control — https://proceedings.mlr.press/v229/huang23a/huang23a.pdf

Decisão, previsão e IA embarcada
- [S43] AUC-based Selective Classification (regra de Chow) — https://proceedings.mlr.press/v206/pugnana23a/pugnana23a.pdf
- [S44] On Calibration of Modern Neural Networks (Guo et al. 2017) — https://proceedings.mlr.press/v70/guo17a.html
- [S45] Selective Classification for Deep Neural Networks (NeurIPS 2017) — https://proceedings.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html
- [S46] Conformal Risk Control (ICLR 2024) — https://openreview.net/forum?id=33XGfHLtZg
- [S47] A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification — https://www.semanticscholar.org/paper/c3ea8eb80bc8ca0b21efa273b9e4a9fd059c65be
- [S48] Adaptive Conformal Inference Under Distribution Shift — https://openreview.net/forum?id=6vaActvpcp3
- [S49] Deep Ensembles: A Loss Landscape Perspective — https://ar5iv.labs.arxiv.org/html/1912.02757
- [S50] Can You Trust Your Model's Uncertainty? Evaluating Predictive Uncertainty Under Dataset Shift — https://dl.acm.org/doi/pdf/10.5555/3454287.3455541
- [S51] A survey of uncertainty in deep neural networks — https://link.springer.com/article/10.1007/s10462-023-10562-9
- [S52] Estimation and prediction for maneuvering target trajectories — https://www.semanticscholar.org/paper/Estimation-and-prediction-for-maneuvering-target-Berg/515cbc32794be947915e7ab7a5d7c2d40d1a17dc
- [S53] Interacting Multiple Model (IMM) Fifth-Degree Spherical Simplex-Radial Cubature Kalman Filter for Maneuvering Target Tracking — https://pmc.ncbi.nlm.nih.gov/articles/PMC5492340
- [S54] The Computational Model of Hitting Probability for Gun to Fire on Ground Target — https://ieeexplore.ieee.org/document/9236822
- [S55] TensorFlow Lite Micro: Embedded Machine Learning on TinyML Systems — https://arxiv.org/html/2010.08678v3
- [S56] Neural Network Quantization for Microcontrollers: A Comprehensive Survey — https://arxiv.org/html/2508.15008v4
- [S57] Hardware — Portenta H7 (Arduino) — https://www.arduino.cc/pro/hardware-product-portenta-h7

### 10.2 Ficheiros do projeto mais citados

- **Mira e treino TF:** `cenarios_mira.py`, `treinar_mira_articulada.py`, `mira_articulada.py`, `mira_balistica.py`, `treinar_mira_gpu.py`, `benchmark_evolucao.py`.
- **Vento e sementes:** `env.py`, `env_real.py`, `vento_natural.py`, `avaliar_vento.py`, `avaliar_bola.py`, `train.py`, `treinar_bola.py`, `ab_treino.py`, `bench_treino.py`.
- **Braços:** `bracos_controlo.py`, `lab/drone_rpi/servos.py`, `lab/drone_rpi/planta.py`, `lab/drone_rpi/modelo.py`, `models/drone_rpi/builds.json`, `models/drone_rpi/componentes.json`, `teste_bracos.py`.
- **Controlo e firmware:** `sim_view.py` (`_afinar_cfg_anti_tremor`, `PITCH_CORPO_MAX_COCKPIT`), `controlo_classico.py`, `fc.py`, `sitl.py`, `firmware/nucleo/{config,cascata,taxa,alvo}.hpp`, `firmware/README.md`.
- **Resultados:** `out/evolucao/evolucao_estabilidade.json`, `out/mira_articulada/{validacao,modelo_mira_articulada}.json`, `out/bola/afinacao.json`, `README.md` (secção «BRAÇOS ARTICULADOS»).
- **Notas anteriores:** `pesquisas/2026-10-19-bracos-articulados-mira-por-arfagem.md`, `pesquisas/relatorio-treino-rl-suficiencia.md`, `pesquisas/2026-10-12-cockpit-bola-vento-treino.md`.

### 10.3 Verificação

**Conferido à mão a 2026-10-19:**
- `cenarios_mira.py:62-67`;
- `treinar_mira_articulada.py:120, 368-373`;
- `env.py:768-778`;
- `env_real.py:124, 433, 592-599`;
- `avaliar_vento.py:96`;
- `vento_natural.py:97-98`;
- `sim_view.py:2293-2310, 2538`;
- `bracos_controlo.py:102`;
- `train.py:704-708`;
- `lab/drone_rpi/servos.py:24-26, 200`;
- `lab/drone_rpi/planta.py:1477`;
- `firmware/README.md:303-304`;
- `README.md:79-80`;
- os JSON `out/mira_articulada/validacao.json` e `out/evolucao/evolucao_estabilidade.json`.

**Contas refeitas:**
- a regra dos três: 62/299/598/2995 tiros; 4,02/4,64/4,95 % para 73/63/59 tiros;
- o successive halving: 3888 vs 11 664 episódios;
- a potência: 32/88 blocos;
- os custos por débito;
- a guinada diferencial: 1,05/2,63/5,24 N·m;
- o recuo antecipado: 8° durante ~0,31 s;
- o tamanho das redes: 12 483 parâmetros, 12 224 MAC.

**Não reconferido.** Os números marcados como medidos fora do repositório (99,4 %, 0/120, discrepâncias de Sobol, permanências do esboço) vêm dos scripts dos leitores, que não ficaram versionados. Os outros números de linha citados vêm das leituras e não foram todos reconferidos um a um.
