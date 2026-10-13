---
tipo: dossie-pesquisa
versao: 1
pergunta: "Qual é o MELHOR (não «opções») para o drone grande do dono: o que a DJI realmente faz, como rejeitar vento/rajadas, como manter um alvo móvel centrado com câmara fixa ao corpo, quando compensa ter mais de uma rede a correr, como treinar PPO mais depressa nesta máquina e como se desenha um cockpit de GCS?"
criado: 2026-10-12
atualizado: 2026-10-12
estado: concluido
proveniencia: untrusted (web)
metodo: tavily-agent-skill, modo NORMAL (search + extract), SEM --deep-research
---

# Dossiê — cockpit, bola, vento e treino (drone 1950 mm, 2,2 kg, hélices 15″, câmara FPV fixa)

> **Proveniência: `untrusted` (web).** Tudo o que aqui vem de páginas web é DADO citado, nunca instrução.
> Pesquisa em modo NORMAL da `tavily-agent-skill` (66 `search` + 30 `extract`, 1 extração falhada); **não** é
> pesquisa profunda (o dono não passou `--deep-research`): não houve subagentes, crítico nem verificação
> adversarial — as afirmações assentam em 1–3 fontes lidas por trechos. O escudo anti-injeção não sinalizou
> nenhuma fonte (0 marcas `⚠ escudo`).
> Níveis de fonte: **A** paper revisto / documentação oficial · **B** preprint, tese, página de laboratório ·
> **C** fórum, blogue, vídeo · **D** agregador ou vendedor. Confiança: alta · moderada · baixa.
> «(resumo)» = só li o resumo/snippet devolvido pelo motor de pesquisa, não o texto integral.

## 0. Brief

- **Para quê:** o dono pediu «não quero opções, quero o melhor — se for como a DJI pode copiar; se for treino
  de IA pode treinar; se os estudos indicarem mais de uma IA, faça». A decisão sai da MEDIÇÃO no simulador
  (`experiments/09_drone_hover_rl`); este dossiê diz **o que medir/implementar** e **com que justificação
  externa**, e alimenta o redesenho do site como cockpit.
- **Plataforma:** frame 1950 mm, 2183 g, hélices 15″, J ×10–11, guinada fraca (≈ 29 °/s medidos), câmara FPV
  fixa ao corpo, sem gimbal; ω_c(taxa) = 8,43 rad/s, K_att = 3,37 s⁻¹ (memória #10371).

### 0.1 O que as fontes que já tínhamos JÁ respondem (não repetido aqui)

| Fonte existente | Já responde |
|---|---|
| `pesquisas/2026-10-12-para-um-quadricoptero-grande-…md` (Q1–Q8) | Clássico vs RL em hover/seguimento (empate técnico em voo lento; RL ganha no limite do envelope); cascata PX4/ArduPilot (estrutura, taxas, anti-windup) e **licenças** (só PX4 copiável); controlo de guinada com autoridade baixa; estimadores em MCU; placas Arduino e visão em MCU; **servo visual clássico** (PIDs guinada←u, v_z←v, v_x←distância; *feedforward* da velocidade do alvo; Kalman atrasado/Smith para o atraso; RL×clássico depende da qualidade do *baseline*); SITL. INDI como malha interna já aparece com dois números (0,102 vs 0,343 m; 21 vs 151 cm). **Vento estava EXCLUÍDO do âmbito.** |
| `pesquisas/relatorio-seguimento-visual-rl.md` (memória #10020) | Cascata IA-seguimento→IA-voo: «congelar a interior, treinar a exterior»; observação 12D com propriocepção obrigatória; latência 33 ms@30 Hz; taxas (FC 500–1000 Hz, política 50 Hz, *tracker* 25–30 Hz); *watchdog* 100–300 ms; armadilhas de política-sobre-política. |
| `pesquisas/relatorio-treino-rl-suficiencia.md` (memória #9805) | Orçamentos de passos (hover 5–8 M, voo 8–12 M), hiperparâmetros SB3 de partida, currículo de vento por estágios, nº de *seeds*, sinais de sub/sobretreino. |
| Memória #10553 e #10371 (MEDIÇÃO de hoje) | Sem vento o clássico vence a RL em pairar (3,9 vs 13,0 cm), rodar e seguir («oito» 0,27 vs 1,4 m); a única vantagem da RL eram as rajadas; FF de aceleração e de taxa de inclinação é essencial; o limite do hover é o ESTIMADOR; latência 21 ms → rumo RMS 0,4–0,9°, 116 ms → 1,0–3,0°. |

### 0.2 Lacunas que este dossiê ataca

Q1 o que a DJI documenta de facto · Q2 rejeição de vento com números comparáveis e o que os firmwares abertos
usam · Q3 câmara fixa ao corpo (acoplamento inclinação↔imagem, câmara virtual, guinada + translação lateral,
latência) e RL vs IBVS · Q4 várias redes vs uma · Q5 débito de treino nesta máquina · Q6 padrões de cockpit/GCS.

## 1. Síntese executiva (o que muda decisões)

1. **DJI — não há nada para copiar.** Nenhuma fonte primária (paper, patente, documentação) descreve a lei de
   controlo dos A3/N3/consumo. O que está documentado aponta para uma **cascata clássica por eixo** com ganhos
   escalados pela **largura de banda da propulsão**, modos expostos em cascata (taxa ← atitude ← velocidade ←
   posição), IMU redundante e **estimativa de vento a bordo**; a identificação caixa-preta de um Matrice 100 dá
   uma malha de atitude de 1.ª ordem com τ ≈ 0,47 s — nada de exótico. «ADRC na DJI» é especulação sem fonte.
   O «melhor» documentado está na literatura aberta, não na DJI. *Confiança: moderada (ausência de evidência).*
2. **Vento — o melhor é clássico com realimentação de ACELERAÇÃO (INDI ou observador de perturbação), não RL
   pura.** Números reais: INDI vs PID 0,21 vs 1,51 m (−86 %) num túnel a 10 m/s; PID + estimador de perturbação
   −41 a −48 % do desvio máximo a 10–12 m/s (MPC + estimador −71 a −78 %); H∞ vs PX4 −50 % RMS a 12,8 m/s;
   RL residual sobre PID ≈ −50 %. A mesma política PPO passa de 36 % para 94,6 % de sucesso só por trocar o
   PID interno por INDI. PX4/ArduPilot/Betaflight **não** usam nada disto por omissão: rejeitam vento com o
   integrador de velocidade. **Mas num drone grande e lento o limite é físico** (tempo de inclinar e de
   acelerar hélices): nenhuma fonte tem números a 15″. *Confiança: alta na direção, baixa na magnitude para a
   nossa planta.*
3. **Câmara fixa — clássico, com DESROTAÇÃO de roll/pitch (câmara virtual) e guinada + translação lateral.**
   O acoplamento inclinação↔imagem é o problema documentado de câmara fixa; a solução padrão é reprojetar para
   um plano de imagem virtual nivelado. A RL só bate o clássico modular com alvo rápido/agressivo ou perceção
   suja; a baixa velocidade empatam. Nenhuma fonte trata veículos de guinada fraca. *Confiança: moderada.*
4. **Mais de uma rede — sim, mas separadas por FUNÇÃO, nunca empilhadas.** O padrão dos sistemas campeões é
   «1 rede de perceção + estimador clássico + 1 rede pequena de controlo». Evidência com números só para:
   política sobre malha interna clássica, residual sobre PID, e estimador de vento aprendido a alimentar o
   controlo (este só em simulação). *Ensembles* a bordo: sem evidência. *Confiança: moderada.*
5. **Treino — a GPU não ajuda um MLP 64–128 com simulador em CPU; o que rende é paralelismo de ambientes e
   lote grande.** O SB3 diz textualmente para correr PPO-MLP em CPU com `SubprocVecEnv`. O MuJoCo em CPU é
   competitivo para um corpo só (1,8 M passos/s em 64 núcleos vs 950 k do MJX-JAX numa A100). Referência de
   escala: Swift 10⁸ passos em 50 min (≈ 33 k passos/s). *Confiança: alta nas afirmações oficiais; baixa na
   transposição para a nossa planta em Python.*
6. **Cockpit — a convenção é estável entre QGC e DJI:** vídeo em ecrã inteiro, **PiP em baixo à esquerda** que
   troca com o principal ao clicar (redimensionável, ocultável, destacável), barra superior de estado com zona
   de aviso que fica âmbar/vermelha, velocidade à esquerda e altitude à direita, centro reservado a simbologia
   CONFORME (mira, horizonte, marcador do alvo). Fatores humanos: o HUD atrasa a deteção de eventos inesperados
   0,5–3,6 s por «tunelamento»; ≤ 6 cores de codificação; vermelho = aviso, âmbar = cautela. *Confiança: alta.*

## 2. Perguntas

### Q1 — DJI e afins: o que é publicamente documentado sobre a arquitetura de controlo

**Resposta.** Não encontrei NENHUMA fonte primária com a lei de controlo da DJI. Separando:

| Afirmação | Tipo | Fonte | Nível | Confiança |
|---|---|---|---|---|
| A DJI expõe por eixo um **«Basic Gain»** (pitch, roll, yaw, vertical) e um **«Attitude Gain»** (rapidez da resposta ao *stick*); ganho alto demais oscila a 5–10 Hz; existe um «I-Vertical» nos parâmetros avançados. Estrutura coerente com malhas em cascata por eixo (a leitura «cascata» é minha). | FACTO documentado | [F1] DJI, «What does parameter gain mean?» | A (fabricante) | alta |
| Nos N3/A3 há um parâmetro **«Power Bandwidth»** = largura de banda própria da propulsão (motores + ESC + hélices); alto demais → oscilação lenta em pairagem, baixo demais → tremor de alta frequência. Ou seja, a afinação é parametrizada pela banda do atuador. | FACTO (vídeo oficial + citação em fórum) | [F2] | B/C | moderada |
| O Onboard SDK expõe modos horizontais de **ângulo de atitude, velocidade, posição e taxa angular**, vertical de velocidade/posição/acelerador e guinada por ângulo/taxa; o «stable mode» pára e segura a posição com comando de velocidade nulo (sem ele «may flutter with the wind»). Limites: 35° e 30 m/s. | FACTO documentado | [F3] DJI OSDK | A | alta |
| Identificação caixa-preta do **Matrice 100**: a malha de atitude fechada do autopiloto ajusta-se a 1.ª ordem, roll 3,544/(s + 2,118) (τ = 0,472 s, ganho DC 1,673), pitch 3,827/(s + 2,43); há **zona morta** nos comandos sem API para a desligar; o simulador HIL do fabricante é «surpreendentemente próximo» do real. Com MPC + observador de perturbação por cima: RMS 2,1 / 1,6 / 2,9 cm. | FACTO medido por terceiros (ETH) | [F4] Sa et al. 2017 | B | moderada |
| IMU dupla/tripla com deteção de falha e comutação; «robust flight control algorithm» (sem pormenor). | FACTO de marketing | [F5] DJI N3 | A | alta (mas vazio de conteúdo técnico) |
| Resistência ao vento especificada: **12 m/s** (Mavic 3 / 3 Classic / 3M). | FACTO de especificação | [F6] | A | alta |
| O PFD do Matrice 300 mostra **velocidade e direção do vento «as detected by» a aeronave** → a DJI estima vento a bordo. Se entra no controlo como *feedforward*: não documentado. | FACTO (estimação) / LACUNA (uso) | [F7] DJI Enterprise | A | alta / — |
| Estimar vento pela atitude de um M300 dá erros < 0,7 m/s e < 20° face a torre meteorológica, mas a relação inclinação↔vento varia por modelo. | FACTO de terceiros (resumo) | [F9] ACP 2026 | A | baixa (só resumo) |
| «A DJI usa PID em cascata multi-malha com *tuning* adaptativo e filtros complementar/Kalman.» | Afirmação de agregador **sem fonte primária** | [F8] Patsnap | D | baixa — plausível, não provado |
| «A DJI usa ADRC / INDI / observadores de perturbação.» | **ESPECULAÇÃO**: a pesquisa não devolveu nenhuma fonte que o ligue à DJI | — | — | sem evidência |
| Patentes SZ DJI com a lei de controlo (feedforward, malha de aceleração angular, observador). | **NÃO ENCONTRADO** em 5 pesquisas dirigidas a patentes, 3 delas restritas a Google Patents/Justia (só devolveram patentes de *design*, estrutura e gimbal) | — | — | lacuna |
| Engenharia reversa do firmware (Ghidra, `dji-firmware-tools`) existe, mas as fontes lidas tratam DroneID/segurança e parâmetros, não a lei de controlo. | FACTO (existência) | [F10] | A/C | moderada |

**Leitura.** O que se pode «copiar» da DJI são três ideias, todas já ao nosso alcance: (i) ganhos derivados da
banda da propulsão — **já fazemos** (`ganhos_de_hardware`); (ii) modos em cascata com *hold* de posição quando
o comando de velocidade é zero — **já fazemos** (cascata + «trava»); (iii) estimar o vento a bordo e mostrá-lo
ao piloto — **não fazemos**. Referência útil: o M100 (multirrotor DJI da classe dos 3 kg — massa de memória, não verificada nesta pesquisa) tem τ_atitude ≈ 0,47 s; o nosso
K_att = 3,37 s⁻¹ dá ≈ 0,30 s, ou seja, a nossa malha não é mais lenta do que a de um DJI da mesma classe
(comparação grosseira: o ganho DC ≠ 1 indica unidades de comando do SDK).

**O que NÃO se conclui:** se a DJI usa PID, ADRC, INDI ou controlo baseado em modelo; se o vento estimado é
realimentado; taxas de malha e filtros. Não há base para «fazer como a DJI».

### Q2 — Rejeição de vento/rajadas em multirrotores

**Resposta.** A evidência com voo real converge: **medir/estimar a aceleração (ou a força de perturbação) e
compensá-la diretamente** reduz o erro de posição em rajada para metade ou menos face a PID com integrador. A RL
entra como *residual* ou como planeador por cima de uma malha clássica robusta — não como substituto.

**Números comparáveis (todos em voo real, salvo indicação):**

| Método vs *baseline* | Plataforma / condição | Resultado | Redução | Fonte | Nível |
|---|---|---|---|---|---|
| **INDI em cascata** vs PID | Bebop, entrada/saída de túnel a 10 m/s, média de 7 repetições | desvio 0,21 m (entrada) / 0,20 m (saída) vs **1,51 m** | **−86 %** | [F11] Smeur 2018 | A |
| INDI vs PID (rajada) | túnel de vento, erro médio em x | 6,4 cm vs 19,3 cm | −67 % | [F12] Smeur 2016 (resumo; extração falhou) | A |
| **PID + estimador de perturbação** vs PID | túnel, rajada a 10 / 12 m/s, desvio horizontal máx. | 10 / 23 cm vs 17 / 45 cm | **−41 % / −48 %** | [F14] Hentzen 2019, Tab. I | A/B |
| MPC (sem estimador) vs PID | idem | 19 / 39 cm | −12 % / +13 % (≈ igual) | [F14] | A/B |
| MPC + estimador vs PID | idem | 8 / 17 cm | −53 % / −62 % | [F14] | A/B |
| MPC + folga + estimador vs PID | idem | 5 / 10 cm | **−71 % / −78 %** | [F14] | A/B |
| **H∞ dependente da frequência** vs PX4 | octorrotor de rotores inclinados, túnel, 72 voos | RMS do erro de posição −50 % a 12,8 m/s; uso de atuadores **+25 %** | −50 % | [F15] tese Auckland | B |
| **L1 adaptativo** sobre geométrico | 11 tipos de incerteza/perturbação | erro de seguimento em média **5× menor** | −80 % | [F16] (resumo) | A/B |
| INDI vs PID (fabricante) | corrente de ar de 72 km/h | ≈ 35 cm vs «quase o dobro» | ≈ −50 % | [F17] Fusion Engineering | C/D |
| **Mesma política PPO**, malha interna INDI vs PID | quadricóptero de 50 g, 80 voos, ventoinhas até 3,5 m/s | sucesso **94,6 % vs 36,0 %**; RMSE até −50 % | — | [F18] GustPilot 2026 | B |
| **RL residual sobre PID em cascata** vs PID | treino só em simulação, exterior com vento > 13 m/s | desvio de posição ≈ −50 % (desvio-padrão −45 a −63 %); mantém com massa e coef. de sustentação entre 50 % e 150 % | **−50 %** | [F19] Ishihara 2023 | B |
| RL residual + **estimador de vento aprendido** vs PD | **só simulação**, turbulência 3–12 m/s | RMSE 1,315 → 0,684 m (−48 %); sem o canal de vento 0,985 m (−25 %); o vento estimado acrescenta −30,5 %; ganho cresce de 21,8 % (4 m/s) a 62,4 % (12 m/s) | −48 % | [F20] 2026 | B |
| PID com ganhos por DRL vs PID | (resumo; condição de ensaio não lida) | pico de RMSE 0,58 → 0,42 m | −30 % | [F28] | B |

**Porque funciona o INDI e onde pára** ([F13], A): a malha interna fechada do INDI **é a dinâmica do atuador**;
as perturbações de aceleração angular são rejeitadas com uma resposta fixada pela dinâmica do atuador, pelo
filtro e por um passo de atraso («se a aceleração angular for medida mais depressa, o drone responde mais
depressa»). Exige aplicar **o mesmo filtro** ao sinal de entrada (sincronização), senão o incremento acumula.
Não é mais rápido nem mais lento que um PID no seguimento de referência — ganha na perturbação. Só é preciso
conhecer a dinâmica do atuador quando se quer uma malha externa de alto desempenho. E, relevante para nós:
«por incorporar o **binário de aceleração do rotor** (*spin-up torque*), é possível controlo de guinada rápido,
tipicamente muito lento num quadricóptero».

**Limite físico em drones grandes** ([F17], C/D; [F26], C): «se tens um drone enorme com braços e rotores que
não aceleram depressa, esse é o fator limitante, não o INDI» — para segurar a posição o veículo tem primeiro de
inclinar, e a rapidez com que inclina fixa quanto é soprado. No fórum ArduPilot: guinada lenta «é um facto da
vida» em multirrotores grandes (inércia sobe e as hélices eficientes têm menos arrasto).

**O que os firmwares abertos realmente usam:**

| Firmware | Mecanismo contra vento | Fonte | Nível |
|---|---|---|---|
| **PX4** | Controlador de taxa K-PID; o integrador da velocidade horizontal (`MPC_XY_VEL_I_ACC`) existe «para eliminar o erro estacionário na presença de perturbações como o vento»; estimador de empuxo de pairagem; o EKF2 estima vento pela fusão de arrasto (`EKF2_DRAG_CTRL`, `EKF2_BCOEF_*`, `EKF2_MCOEF`) — documentado como ESTIMAÇÃO, não como *feedforward* de controlo. INDI: não está na documentação da linha principal; há utilizadores a tentar implementá-lo por conta própria. | [F21] docs PX4 · [F22] fórum | A · C |
| **ArduPilot** | Mesma cascata PID; o EKF3 estima o vento pelo arrasto (`EK3_DRAG_BCOEF_X/Y`, `EK3_DRAG_MCOEF`), «informação útil para o piloto» e usada para **compensar o barómetro** — não é *feedforward* de posição. | [F23] | A |
| **Betaflight** | PID + *feedforward* **do stick** (proporcional à velocidade e aceleração do comando): é resposta ao piloto, não rejeição de perturbação; a rejeição vem do P/I/D e dos filtros. | [F24] notas de afinação 4.2/4.3 | A |
| **Paparazzi** | É o único com INDI de série: módulos `stabilization_indi`, `stabilization_indi_simple`, `stabilization_heli_indi`, `stabilization_andi`, `stabilization_indi_hinf`. Licença GPL → reimplementar a partir dos papers de Smeur. | [F25] | A |

**Custo computacional.** Não encontrei tempos publicados de INDI/ESO em MCU (lacuna). Por construção (inferência
minha): INDI = 2–3 filtros de 2.ª ordem por eixo + um produto por uma matriz 4×4 constante; um observador de
perturbação/ESO linear = 2–3 estados por eixo — ordens de grandeza abaixo do nosso ciclo de 1438 instruções.
Para comparação, uma política de **3×64 neurónios corre a 500 Hz num FC de 32 bits** ([F38], B).

**Recomendação consensual para um quadricóptero grande e lento** (síntese; a parte «grande e lento» é
inferência, nenhuma fonte mede 15″):

1. Manter a cascata PID com integrador de velocidade (é o que PX4/ArduPilot fazem e o que já temos).
2. Acrescentar **realimentação de aceleração**: primeiro um estimador de perturbação na malha de
   velocidade/aceleração (o «PID + comp» de [F14]: −41 a −48 % com a menor alteração), depois INDI na malha de
   taxa se a medição o justificar (−67 a −86 % num Bebop, mas a vantagem encolhe com atuadores lentos).
3. Explorar no eixo de guinada o binário de aceleração do rotor (INDI de Smeur) — é precisamente onde a nossa
   planta é fraca.
4. RL só como **residual limitado** sobre essa cascata (≈ −50 % em [F19]) ou como planeador por cima de uma
   malha interna robusta ([F18]); nunca como substituto da malha interna.

**Cautelas.** (a) Todas as plataformas são pequenas (50 g a < 1 kg) exceto o octorrotor de Auckland; (b) os
ganhos medidos em simulação encolhem no campo — num barco autónomo o ADRC deu −30 a −40 % em simulação e só
−10 a −20 % em ensaio real ([F27], A, não é multirrotor); (c) o estudo com estimador de vento aprendido [F20]
compara com um PD (sem integrador) e é só simulação; (d) H∞ custou +25 % de uso de atuadores [F15] — medir
energia e saturação, não só erro.

### Q3 — Manter um alvo móvel centrado com câmara FIXA ao corpo (sem gimbal)

**Resposta.** Continua clássico. O problema específico da câmara fixa está identificado e tem solução padrão.

| Afirmação | Fonte | Nível | Confiança |
|---|---|---|---|
| «O uso de uma câmara fixa num multirrotor com servo visual **acopla naturalmente as variáveis controladas**»: a característica vertical f_v fica fortemente acoplada ao *pitch*, porque para seguir o alvo é preciso inclinar; essas variações entram no comando de altitude através do PD. Foi preciso desenhar **heurísticas de desacoplamento** para altitude e movimento lateral (correção do erro de seguimento com a atitude), que «reduzem muito» o acoplamento, embora ainda se note perto do fim do ensaio. | [F29] Pestana et al., ACC 2014 (AR.Drone 2.0, câmara frontal, PDs sobre f_u, f_v, f_Δ) | A | alta |
| A **heurística de desacoplamento guinada–lateral** melhorou a rejeição de vento (avaliação qualitativa, por vídeo — os autores dizem que é difícil quantificar). | [F29] | A | baixa (qualitativa) |
| **Câmara virtual:** reprojetar as características para um plano de imagem virtual compensa o roll e o pitch relativos; no plano virtual a dinâmica da imagem depende só da velocidade de translação e da taxa de guinada. Características usadas: momentos de imagem (centróide normalizado q_x, q_y e q_z = √(a*/a) pela área). Num sistema subatuado não se podem controlar todos os graus de liberdade pela imagem; resultados em simulação, melhores que os momentos esféricos. | [F30] Jabbari, Oriolo, Bolandi 2014 | A | moderada (simulação) |
| A abordagem esférica «não funciona bem na direção vertical»; a câmara virtual elimina a influência de roll/pitch. | [F35] (resumo) | B | baixa |
| Alternativa ótima: **MPC consciente da perceção** que mantém o ponto de interesse visível e minimiza a sua velocidade na imagem, lidando com a subatuação; voo circular a 3 m/s com o ponto sempre no campo de visão (o resumo do motor de pesquisa refere erro médio < 50 px do centro — não verifiquei no texto). | [F31] PAMPC, IROS 2018 | A | moderada |
| Há esquemas que dispensam a câmara virtual compensando a subatuação e impondo a restrição de visibilidade verdadeira. | [F36] AIM 2023 (resumo de vídeo) | C | baixa |
| **Latência de câmara de fotogramas:** entre t_f + t_T + t_E e 2·t_f; para 50 Hz, exposição 5 ms e USB 3 → **26 a 40 ms**. | [F32] Falanga, Kim, Scaramuzza, RA-L 2019 | A | alta |
| IBVS com **estimação do alvo atrasada** (observador EKF com modelo de imagem virtual e compensação de atraso) + restrições dinâmicas de campo de visão em coordenadas da imagem virtual; alvos com ≥ 17–18 m/s e ≥ 5 m/s²; só simulação e SITL. | [F33] Guo et al., CJA 2026 | A | moderada (sem voo real) |
| **RL vs modular clássico:** com alvo LENTO o D-VAT (DRL fim-a-fim, ator-crítico assimétrico) e os *baselines* modulares (detetor SiamRPN++ + PID ou LQG) têm desempenho semelhante; com alvo mais rápido e agressivo os modulares degradam e o D-VAT quase não. Causa apontada: o controlador assume posição relativa exata e recebe uma caixa delimitadora ruidosa. Avaliado em simulação e realidade mista. | [F34] D-VAT, RA-L 2024 | A | moderada |

**Como isto encaixa no que já medimos.** Os nossos 21 ms (DCMI) ficam abaixo do melhor caso de [F32] e os
116 ms (Pi) a ≈ 3× o pior caso de uma câmara de 50 Hz; a degradação medida (rumo RMS 0,4–0,9° → 1,0–3,0°) é
coerente com o tratamento por Kalman atrasado/Smith do dossiê anterior. A condição em que a RL bate o clássico
(alvo agressivo + medição suja + controlador desenhado para medição perfeita) **não é a nossa**: alvo lento,
esfera brilhante, e o clássico já ganhou 5× no «oito».

**Guinada + translação lateral num veículo de guinada fraca:** NENHUMA fonte trata o caso (lacuna). O que a
literatura dá é o mecanismo ([F29]: desacoplar guinada e lateral; [F30]: no plano virtual a imagem responde a
v_y e à taxa de guinada). Hipótese a medir (inferência minha): repartir o erro horizontal por frequência —
translação lateral para a parte rápida (limitada pela inclinação), guinada para a parte lenta (limitada a
≈ 29 °/s e 30 °/s²) — com o erro medido no plano **desrotacionado**.

**O que NÃO se conclui:** limites de erro em px/graus em função da latência (não há tabela publicada — só os
nossos números); ganho real da câmara virtual com alvo móvel em voo; qualquer coisa sobre guinada fraca.

### Q4 — Mais de uma rede a correr

**Resposta.** Os estudos indicam mais de uma rede **quando têm funções diferentes** (perceção vs controlo vs
estimação), e indicam que a peça que mais conta por baixo de uma política é um controlador **clássico** robusto.
Não indicam várias redes de controlo em paralelo nem *ensembles* a bordo.

| Arquitetura | Evidência (com números) | Fonte | Nível |
|---|---|---|---|
| **Perceção separada do controlo** (campeão) | Swift: detetor de portas (rede, 30 Hz) + VIO (100 Hz) fundidos por **filtro de Kalman** (100 Hz) → política **MLP 2×128** → empuxo coletivo + taxas → controlador de baixo nível. Modelos residuais (perceção e dinâmica) identificados com dados reais para afinar em simulação. | [F37] Nature 2023 | A |
| Idem, com menos malhas clássicas | MonoRace (vencedor A2RL 2025): rede de segmentação + estimador (EKF) + **uma** rede de guiamento e controlo **3×64** que emite comandos de MOTOR a 500 Hz no FC, sem malhas internas; 0–100 % em 22 ms. | [F38] arXiv 2026 | B |
| **Política de alto nível + malha interna clássica** | Políticas que comandam empuxo coletivo + taxas (seguidas por PID) são mais robustas a mudanças de dinâmica do que as que comandam motores, sem perder agilidade. | [F39] ICRA 2022 | A |
| A malha interna certa vale mais que a política | Mesma política PPO, mesma observação e recompensa: INDI por baixo 94,6 % de sucesso, PID 36,0 %. | [F18] | B |
| **Residual sobre clássico** | PID em cascata + rede residual: ≈ −50 % de desvio com vento > 13 m/s, treino só em simulação, robusto a ±50 % de massa. | [F19] | B |
| **Rede estimadora + rede de controlo** | Estimador de vento aprendido a alimentar uma política residual: o canal de vento acrescenta −30,5 % sobre a política «cega» (só simulação, *baseline* PD). | [F20] | B |
| **Modular por eixos fracamente acoplados** | Duas políticas (translação + guinada) convergem mais depressa e superam a monolítica, sobretudo a taxas de guinada altas (a monolítica falhava a 40 °/s); um módulo afina-se sem retreinar o outro. Só resultados qualitativos na fonte lida. | [F41] GWU | B/C |
| **Uma só rede fim-a-fim** | L2F: política única motor-a-motor treinada em segundos; sem ator-crítico assimétrico **e** sem currículo, a maioria das políticas ainda cai após 3 M passos. | [F42] RA-L 2024 | A |
| Fim-a-fim ganha quando a interface modular perde informação | D-VAT > detetor + PID/LQG com alvo agressivo (ver Q3). | [F34] | A |
| Taxonomia | RL «indireta» (afina ganhos), «semi-direta» (residual/feedforward: adequada a compensação local de perturbações; a segurança depende do *baseline* e dos limites do residual) e «fim-a-fim» (comando ágil; a segurança costuma depender da recompensa, salvo filtro de segurança). | [F40] revisão 2026 | A/B |
| Muitas redes no TREINO, uma em voo | RAPTOR: 1000 professores destilados numa política recorrente de 2084 parâmetros (já no relatório de suficiência; não relido). | relatório anterior | — |
| *Ensembles* de políticas a bordo | Pesquisa dirigida **não devolveu** nenhum resultado com números em drones. | — | lacuna |

**Quando ajuda:** (1) perceção difícil → rede de perceção + estimador clássico + controlo; (2) perturbação não
modelada → residual limitado sobre o controlador clássico; (3) grandeza não medida mas inferível (vento) → rede
estimadora, se bater o observador clássico; (4) eixos com dinâmica muito diferente (a nossa guinada) → módulos
separados. **Quando só complica:** política sobre política sem malha clássica no meio (erro composto — relatório
anterior), interfaces que perdem informação (caixa delimitadora → «posição exata»), e *ensembles* (sem evidência).

### Q5 — Eficiência do treino (PPO/SB3 + MuJoCo, 32 threads + RTX 4070 8 GB)

| Afirmação | Fonte | Nível | Confiança |
|---|---|---|---|
| «O PPO destina-se a correr sobretudo em **CPU**, especialmente sem CNN. Para melhorar a utilização do CPU, desligue a GPU e use `SubprocVecEnv` em vez do `DummyVecEnv`.» | [F43] docs SB3 (PPO) | A | alta |
| `DummyVecEnv` corre os ambientes em sequência no mesmo processo (melhor quando o passo é barato e o custo de comunicação domina); `SubprocVecEnv` compensa quando o ambiente é pesado; o nº de ambientes não deve exceder os núcleos lógicos. | [F44] docs SB3 (vec envs) + guia | A/C | moderada (parte por resumo) |
| EnvPool (C++): MuJoCo Ant com 1 ambiente num portátil 12 326 → 15 641 passos/s (1,27×); ≈ 3× o `subprocess` em 12 núcleos; 3 M passos/s de MuJoCo em 256 núcleos (19,2× o `subprocess`). | [F45] | A | alta |
| MuJoCo oficial, 1 humanoide: **650 k** passos/s (CPU Apple M3 Max), **1,8 M** (CPU AMD 3995WX de 64 núcleos), **950 k** (MJX-JAX numa A100, lote 8192), **2,7 M** (TPU v5 de 8 chips, lote 16 384). O MJX-JAX «funciona melhor com milhares ou dezenas de milhares de cenas em paralelo» e perde débito mais depressa que o MuJoCo quando os contactos aumentam. | [F46] docs MuJoCo 3.15 (cópia local) | A | alta |
| MJX-Warp: 3,35 M passos/s no Humanoid em Warp puro, 2,96 M via FFI do JAX, 0,80 M se o grafo CUDA for recapturado a cada passo (hardware não indicado no excerto). | [F46] | A | moderada |
| `mujoco.rollout` corre lotes em paralelo num *pool* de threads interno em C++ (um `MjData` por thread), fora do laço de Python; reparte por *chunks* e o tamanho por omissão é mau para rollouts de 1 passo. O caso «paralelo mas em malha fechada» tem custo próprio. | [F47] docs + discussão #1522 | A/C | alta / baixa |
| MuJoCo Playground (MJX): a maioria das tarefas de estado da DM Control treina em < 10 min numa GPU; políticas reais em ≈ 10 min numa RTX 4090; débito de PPO 38 k–487 k passos/s nas tarefas de manipulação; GPUs maiores reduzem o tempo até 3×. | [F48] | B | moderada |
| **Lote vs nº de ambientes:** com lote fixo, mais robôs → menos tempo, mas o desempenho cai se o horizonte por robô ficar curto demais; com poucos robôs as amostras ficam correlacionadas e o desempenho também cai; escala quase linear até ≈ 4000 robôs. Usaram 4096 × 24 = 98 304 e 1500 atualizações em < 20 min. | [F49] Rudin 2021 | A | alta |
| **Lotes grandes** (mais ambientes paralelos) melhoram o desempenho REAL de um quadricóptero até saturar; os outros 4 fatores: velocidade + matriz de rotação na entrada do ator, vetor de tempo no crítico, penalizar a diferença entre ações sucessivas, identificação do sistema com aleatorização seletiva. Erro de seguimento > 50 % menor que os melhores *baselines* de RL. | [F50] SimpleFlight, RA-L 2025 | A | alta |
| Ator-crítico assimétrico + currículo são as duas alterações «grandes»: sem ambas, a maioria das políticas ainda cai aos 3 M passos. | [F42] L2F | A | alta |
| Referência de escala: Swift treina 10⁸ interações em **50 min** (i9-12900K + RTX 3090) → ≈ 33 k passos/s; afinação 2×10⁷. Rede 2×128 com LeakyReLU. | [F37] | A | alta |

**Leitura para esta máquina** (inferência a partir das fontes + do nosso estado: `SubprocVecEnv`, `n_steps` 512 ×
`n_envs` 8, lote 256, ≈ 1450 passos/s medidos com 4 ambientes em máquina carregada — memória #7978):

- **GPU:** não ajuda um MLP 64–128 enquanto o simulador estiver em CPU ([F43]). Só passa a ajudar se a FÍSICA for
  para a GPU (MJX/Warp) com milhares de ambientes — e para um corpo rígido único o próprio MuJoCo em CPU já é
  competitivo ([F46]). Para a nossa planta isso obrigaria a reescrever em JAX/Warp a aerodinâmica, a bateria, os
  sensores e o FC que hoje vivem em Python: custo alto, benefício não demonstrado. **Não recomendado agora.**
- **Onde está o tempo:** estamos ≈ 20× abaixo do débito do Swift num hardware comparável; a física de um
  quadricóptero não explica isso. A hipótese forte é o trabalho em Python por subpasso (FC a 500 Hz, aero,
  sensores). **Perfilar `env.step` antes de mexer em qualquer outra coisa.**
- **Paralelismo:** subir `n_envs` até ao patamar de débito (testar 16 / 24 / 32, nunca acima dos 32 núcleos
  lógicos) e subir o lote em conjunto ([F49], [F50]); correr *seeds* em paralelo quando o gargalo é o ambiente.
- **EnvPool** só serve ambientes já portados para C++ (inferência: o nosso exigiria porte); o caminho natural
  é o núcleo C++ do firmware que já existe em SITL.

**O que NÃO se conclui:** o `n_envs` ótimo para o nosso ambiente (depende do custo do passo em Python); o ganho
de MJX/Warp numa GPU de 8 GB (nenhum *benchmark* publicado encontrado para esta classe); hiperparâmetros ótimos
para um drone de 2 kg (todos os estudos são em Crazyflie ou drones de corrida).

### Q6 — Padrões de interface de cockpit / GCS

**Como os produtos organizam o ecrã:**

| Produto | Organização documentada | Fonte | Nível |
|---|---|---|---|
| **QGroundControl — Fly View** | Elementos: seletor de vista, **indicadores de estado** (estado de voo, modo e componentes principais) na barra superior, **ações** (faixa de ferramentas), ferramentas de câmara, **vídeo**, **valores de telemetria configuráveis**, **atitude/bússola** (horizonte virtual + rumo), mapa. O vídeo aparece numa **janela comutadora em baixo à esquerda** do mapa; clicar em qualquer ponto dela **troca vídeo↔mapa** para primeiro plano; redimensiona-se arrastando o ícone do canto superior direito, oculta-se pelo botão do canto inferior esquerdo e **destaca-se** para uma janela do sistema (ícone superior esquerdo), voltando a encaixar ao fechar. | [F51] | A |
| **DJI Pilot 2 — Camera View** | **Barra superior** (estado da aeronave, modo de voo, qualidade de sinal), parâmetros de câmara, **projeção AR** (casa, pontos marcados e *waypoints* desenhados sobre o vídeo; o que sai do enquadramento fica preso à margem com seta de direção), **Navigation Display** (velocidade, altitude, orientação, casa), **Map View** (tocar para mostrar; maximizar/minimizar), comutador de câmaras. | [F52] manual Mavic 3E/3T | A |
| DJI Pilot 2 — barra de estado | A parte esquerda é a **zona de aviso**: «normal» se tudo bem; **laranja = cautela, vermelho = aviso**; tocar abre o detalhe. | [F53] vídeo | C |
| **DJI PFD (Matrice 300)** | **Mira central** (sempre no centro em FPV), **horizonte artificial** (duas linhas), **vetor de trajetória** (bola: direção e velocidade), **velocidade à esquerda** com vento por baixo, **altímetro à direita** com velocidade vertical e altitude ASL, barra de obstáculo vertical junto à mira. Herda do «six pack» da aviação condensado num PFD. | [F7] | A |
| **DJI Fly (consumo)** | **Miniatura do mapa em baixo à esquerda**; tocar troca para o **indicador de atitude** (orientação, inclinação, posições do comando e da casa); telemetria em baixo: H (distância vertical à casa), D (horizontal), velocidade vertical e horizontal. | [F54] manual Mini 3 | A |
| **Mission Planner — HUD** | Velocidade (do solo se não houver sensor), erro de rota e taxa de viragem, rumo, ângulo de inclinação, qualidade da ligação, hora GPS, altitude (barra azul = taxa de subida), atitude, estado do GPS, distância ao *waypoint*, **modo de voo**, bateria, horizonte artificial. | [F55] | A |
| **Betaflight OSD** | Elementos ligados por caixa de seleção e arrastados na pré-visualização; **3 perfis de OSD** comutáveis em voo; no mínimo ativar **Warnings** + tensão média por célula + qualidade de ligação/RSSI; alarmes por temporizador e por valor. Prática da comunidade (nível C): grelha 30×16, bateria em cima à esquerda, ligação em cima à direita, 2 colunas de margem. | [F56] | A / C |
| **INAV OSD** | Elementos posicionáveis por *layout*: RSSI, tensão, **mira**, **horizonte artificial**, **barras laterais do horizonte**. | [F57] | A |

**Convenções que se repetem** (≥ 2 produtos): PiP em baixo à esquerda que troca com o principal; barra superior
com modo + estado + ligação + bateria; velocidade à esquerda e altitude à direita; mira e horizonte ao centro;
avisos numa zona fixa que muda de cor; perfis/declutter.

**Fatores humanos para HUD:**

| Princípio | Evidência | Fonte | Nível |
|---|---|---|---|
| O HUD acelera as tarefas frequentes mas **atrasa a deteção de eventos inesperados** («tunelamento cognitivo»): tempo até iniciar a manobra evasiva 5,5–6,7 s de cabeça baixa vs 7,2 s (simbologia conforme) e **9,1 s (não conforme)** em HUD → +0,5 a +3,6 s. | 32 pilotos, 36 aproximações em simulador | [F58] NASA TM 2004 | A |
| Simbologia **conforme** (ligada à cena) reduz as falhas de deteção; remédios: simbologia ligada à cena, mostradores periféricos, **minimizar a desordem** e dar opções de *declutter*. | revisão | [F58] | A |
| A simbologia de HUD pode provocar tunelamento e a desordem dificulta identificar objetos. | experiência com pilotos (resumo) | [F61] Human Factors 2025 | A |
| Símbolos **isolados em locais espacialmente únicos** são mais atendidos do que símbolos agrupados. | citado em relatório FAA 2025 (resumo) | [F62] | A |
| **Vermelho = aviso, âmbar/amarelo = cautela**; progressão verde → âmbar → vermelho; uso consistente para não dessensibilizar. | norma | [F59] FAA AC 25-11B · [F60] | A |
| **≤ 6 cores** para codificar parâmetros; evitar pares de luminância semelhante (azul-marinho sobre preto, amarelo sobre branco). | boa prática | [F59] | A |
| Imagem de fundo (terreno, visão sintética — o nosso vídeo) pode usar mais cores, mas **não pode interferir** com a leitura da informação sobreposta. | norma | [F59] | A |
| HUD monocromático: realçar avisos com intermitência, caixa de contorno, brilho, tamanho e/ou **localização**; filosofia documentada e consistente por nível de alerta. | norma | [F59] Ap. F | A |
| Cores saturadas com parcimónia, só para informação crítica e temporária; **nunca só a cor** (codificação redundante); não exigir distinguir tons da mesma cor; evitar vermelho ou azul saturados sobre preto. | guia | [F60] FAA/Volpe | A |

**Tradução para o nosso cockpit** (síntese): centro = só o que é conforme (mira, horizonte, marcador/caixa da
bola, vetor de velocidade); velocidade à esquerda, altitude à direita, rumo em cima; barra superior com modo,
bateria, ligação e uma zona de aviso clicável que fica âmbar/vermelha; PiP da 3.ª pessoa (ou mapa) em baixo à
esquerda, com troca ao clicar, redimensionar, ocultar e destacar; tudo o resto (vento, telemetria, treino) em
janelas flutuantes periféricas, recolhíveis, com um botão de *declutter*; texto com contorno/sombra para manter
o contraste de luminância sobre vídeo (esta última é prática corrente, sem fonte específica lida).

## 3. Decisões que a evidência suporta

| # | Decisão | Evidência | Confiança | Ressalva |
|---|---|---|---|---|
| D1 | **Não «copiar a DJI»**: não há lei de controlo publicada. Adotar só as três ideias documentadas (ganhos pela banda da propulsão — já feito; *hold* a comando nulo — já feito; **estimar e MOSTRAR o vento no cockpit** — por fazer). | [F1]–[F7] | moderada | Ausência de evidência, não evidência de ausência. |
| D2 | **Vento = cascata clássica + realimentação de aceleração.** Ordem de implementação: (1) estimador de perturbação na malha de velocidade/aceleração; (2) INDI na malha de taxa, incluindo o binário de aceleração do rotor na guinada. | [F11] [F13] [F14] [F15] [F18] | alta (direção) | Magnitude desconhecida a 15″; limite físico da inclinação. |
| D3 | A RL de rajadas existente passa a **residual limitado** sobre a cascata (ou fica como *baseline* a bater), não a controlador principal. | [F19] [F18] [F39] [F40] | moderada | Só vale se (1)/(2) não igualarem a RL — critério por medição. |
| D4 | **Seguimento visual clássico**, com o erro medido no **plano de imagem desrotacionado** (câmara virtual) e desacoplamento explícito pitch↔vertical e guinada↔lateral. Nenhum retreino de *tracker* por RL. | [F29] [F30] [F31] [F34] + medição #10553 | moderada | Câmara virtual só validada em simulação com alvo; guinada fraca não tratada. |
| D5 | **Mais de uma rede só por função**: no máximo rede de perceção (se houver distratores/oclusão) + 1 rede pequena de controlo/residual (+ eventualmente estimador de vento aprendido, se bater o observador clássico). Sem política-sobre-política e sem *ensembles*. | [F37] [F38] [F18] [F20] [F41] | moderada | [F20] é só simulação contra PD. |
| D6 | **Treino em CPU** (`device="cpu"`), mais ambientes e lote maior; perfilar o `env.step` antes de qualquer migração; **não** migrar para MJX/Warp agora. | [F43] [F46] [F49] [F50] | alta / moderada | O `n_envs` ótimo é empírico. |
| D7 | Manter ator-crítico assimétrico e currículo; acrescentar penalização da diferença entre ações e, se houver retreino, velocidade + matriz de rotação na entrada do ator. | [F42] [F50] | alta | Estudos em Crazyflie. |
| D8 | **Cockpit**: vídeo em ecrã inteiro; PiP em baixo à esquerda com troca/redimensionar/ocultar/destacar; barra superior com zona de aviso âmbar/vermelha; velocidade à esquerda, altitude à direita; centro só com simbologia conforme; ≤ 6 cores; *declutter*. | [F51] [F52] [F7] [F54] [F58] [F59] [F60] | alta | — |

## 4. O que continua por medir no nosso simulador

| # | Medição | Porquê (lacuna da literatura) | Critério sugerido |
|---|---|---|---|
| M1 | **Rajadas, 5 controladores, mesmas sementes:** (a) cascata atual; (b) + estimador de perturbação; (c) + INDI na taxa; (d) RL de rajadas existente; (e) cascata + residual RL. | Nenhuma fonte mede 15″/2 kg; os −41 a −86 % vêm de drones < 1 kg com motores rápidos. | Desvio máximo à entrada/saída da rajada, RMS xy em Dryden, **energia e fração de saturação** (o H∞ custou +25 % de atuadores), sobrevivência. Adotar o mais simples que fique a ≤ 10 % do melhor. |
| M2 | **Piso físico da rajada:** desvio mínimo possível dado o tempo de inclinação (≈ a_pert·T²/2 com T ≈ 0,3–0,5 s — estimativa minha). | [F17]: em drones grandes o limite é mecânico. Separa «falta de algoritmo» de «falta de autoridade». | Se (b)/(c) já estiverem a < 1,5× do piso, parar aí. |
| M3 | **Guinada com binário de aceleração do rotor:** o modelo MuJoCo inclui a reação inercial das hélices de 15″? Quanto sobe a aceleração de guinada (hoje 30 °/s²)? | [F13] afirma guinada rápida via *spin-up torque*; nunca quantificado para hélices grandes. | Verificar primeiro se a planta modela o efeito; depois degrau de guinada e «oito» a 0,8 m/s (hoje satura). |
| M4 | **Câmara virtual (desrotação) vs erro em bruto** no seguimento da bola, a 21 ms e 116 ms. | [F30] só simula; [F29] só qualitativo. | Erro de centro RMS (px e graus) e erro de distância no círculo e no «oito». |
| M5 | **Repartição guinada/lateral por frequência** vs só guinada. | Lacuna total para guinada fraca. | Erro de rumo RMS e fração de tempo com a taxa de guinada saturada. |
| M6 | **Estimador de vento a bordo** (observador clássico pela inclinação/arrasto) — exatidão e utilidade como *feedforward* e como instrumento do cockpit. | A DJI mostra-o [F7]; PX4/ArduPilot estimam-no mas não o realimentam [F21] [F23]. | Erro < 0,7 m/s e < 20° (ordem de grandeza de [F9]); ganho em M1 quando realimentado. |
| M7 | **Perfil do `env.step` e curva passos/s vs `n_envs`** (8, 16, 24, 32) com `device="cpu"`. | Estamos ≈ 20× abaixo do débito do Swift; a causa é hipótese. | Identificar o gargalo; fixar `n_envs` no joelho da curva; subir o lote em conjunto. |
| M8 | **Cockpit:** tempo até o operador reparar num aviso inesperado (bateria, perda do alvo) com e sem *declutter*. | [F58]: o HUD atrasa eventos inesperados 0,5–3,6 s. | Teste de usabilidade simples; o aviso deve ser visível sem sair do centro (cor + forma + posição fixa). |

## 5. Contradições e cautelas

| Tema | Posição A | Posição B | Resolução |
|---|---|---|---|
| INDI é sempre melhor? | [F11] [F12]: −67 a −86 % em rajada num Bebop | Dossiê anterior: no Crazyflie o INDI do firmware (1,13 m) foi pior que o PID (0,72 m); [F17]: em drones grandes o limite é o atuador | O INDI ganha na PERTURBAÇÃO e com dinâmica do atuador bem modelada; medir na nossa planta (M1, M2). |
| Fim-a-fim ou modular? | [F34] D-VAT e [F38] MonoRace: fim-a-fim ganha no limite | [F39] [F18]: interface empuxo+taxas com malha clássica é mais robusta | Depende da agilidade exigida; o nosso regime é lento → modular com malha clássica. |
| MPC resolve o vento? | [F14]: MPC sem estimador ≈ PID (−12 % / +13 %) | [F14]: com estimador −53 a −78 % | O que conta é o **estimador de perturbação**, não o otimizador. |
| GPU acelera o treino? | [F48] [F49]: minutos em GPU com milhares de ambientes | [F43] [F46]: PPO-MLP em CPU; MuJoCo-CPU competitivo para um corpo | Só com a física na GPU; não é o nosso caso. |
| Simulação vs campo | [F20]: −48 % em simulação | [F27]: num barco, −30/−40 % em simulação viraram −10/−20 % no campo | Descontar os ganhos medidos só em simulação. |

## 6. Fontes

- [F1] DJI. «What does parameter gain mean?». dji.com/newsroom, 2013. https://www.dji.com/newsroom/news/what-does-parameter-gain-mean · oficial · A · trechos
- [F2] DJI. «N3 Flight Controller — Parameter Settings» (vídeo). https://www.youtube.com/watch?v=XmsD1fUr5k8 · B/C · transcrição parcial; + RCGroups «Official DJI A3 Owner's Thread» p. 148 https://www.rcgroups.com/forums/showthread.php?2647235-Official-DJI-A3-%2A%2A%2AOwner-s-Thread%2A%2A%2A%2Fpage148= · C · resumo
- [F3] DJI. «Basic Control — Onboard SDK Documentation». https://developer.dji.com/onboard-sdk/documentation/tutorial/basic-control.html · A · trechos; + «DJI::OSDK::Control Class Reference» https://developer.dji.com/onboard-api-reference/classDJI_1_1OSDK_1_1Control.html · A · resumo
- [F4] Sa, Kamel, Khanna, Popović, Nieto, Siegwart. «Dynamic System Identification, and Control for a cost effective open-source VTOL MAV». arXiv 1701.08623, 2017. https://arxiv.org/html/1701.08623v2 · B · trechos
- [F5] DJI. «N3» (página de produto). https://www.dji.com/n3 · A · resumo
- [F6] DJI. «Mavic 3 Classic — Specs». https://www.dji.com/mavic-3-classic/specs · A · resumo
- [F7] DJI Enterprise. «Introducing DJI's Primary Flight Display», 2020. https://enterprise-insights.dji.com/blog/dji-primary-flight-display · A · trechos
- [F8] Patsnap Eureka. «PID Controllers In Drone Flight Stabilization And Navigation», 2025. https://eureka.patsnap.com/report-pid-controllers-in-drone-flight-stabilization-and-navigation · D · resumo (sem fonte primária)
- [F9] «Wind estimation based on flight dynamics of unmanned aerial vehicle: influencing variables and its environmental application». Atmos. Chem. Phys. 26, 2026. https://acp.copernicus.org/articles/26/3607/2026/acp-26-3607-2026.html · A · resumo
- [F10] «Drone Security and the Mysterious Case of DJI's DroneID». NDSS 2023. https://www.ndss-symposium.org/wp-content/uploads/2023-217-paper.pdf · A · resumo; + `o-gs/dji-firmware-tools` https://github.com/o-gs/dji-firmware-tools · C
- [F11] Smeur, de Croon, Chu. «Cascaded incremental nonlinear dynamic inversion for MAV disturbance rejection». Control Engineering Practice 73, 2018. https://arxiv.org/html/1701.07254v2 · A · resumo (já [S9] no dossiê anterior)
- [F12] Smeur, de Croon, Chu. «Gust Disturbance Alleviation with Incremental Nonlinear Dynamic Inversion». IROS 2016. https://research.tudelft.nl/files/9188911/Gust_Disturbance_Alleviation_with_Incremental_Nonlinear_DynamicaInversion.pdf · A · só resumo (extração falhou)
- [F13] Smeur, Chu, de Croon. «Adaptive Incremental Nonlinear Dynamic Inversion for Attitude Control of Micro Air Vehicles». J. Guidance, Control, and Dynamics, 2016. https://ccc.inaoep.mx/~mdprl/documentos/14032018.pdf · A · trechos
- [F14] Hentzen, Stastny, Siegwart, Brockers. «Disturbance Estimation and Rejection for High-Precision Multirotor Position Control». arXiv 1908.03166, 2019. https://arxiv.org/pdf/1908.03166 · A/B · trechos
- [F15] «Aerodynamic Modelling and Wind Disturbance Rejection of Multirotor UAVs» (tese, Univ. of Auckland; autor não confirmado no excerto; artigo associado: «Frequency-dependent H∞ control for wind disturbance rejection of a fully actuated UAV», Robotica). https://researchspace.auckland.ac.nz/server/api/core/bitstreams/02acb239-7bb2-455a-afc1-59a603571064/content · B · trechos
- [F16] Wu et al. «L1 Adaptive Augmentation for Geometric Tracking Control of Quadrotors». https://par.nsf.gov/servlets/purl/10352479 ; «L1Quad». arXiv 2302.07208. https://arxiv.org/html/2302.07208v2 · A/B · resumo
- [F17] Fusion Engineering. «Intro to Incremental Non-Linear Dynamic Inversion (INDI)», 2022. https://fusion.engineering/intro-to-incremental-non-linear-dynamic-inversion-indi · C/D (fabricante) · trechos
- [F18] «GustPilot: A Hierarchical DRL-INDI Framework for Wind-Resilient Quadrotor Navigation». arXiv 2603.19966v2, 2026. https://arxiv.org/html/2603.19966v2 · B · trechos
- [F19] Ishihara et al. «Improving Wind Resistance Performance of Cascaded PID Controlled Quadcopters using Residual Reinforcement Learning». arXiv 2308.01648, 2023. https://arxiv.org/html/2308.01648v1 · B · trechos
- [F20] «Wind-Aware Reinforcement Learning Control of a Small Quadrotor Using Learned Onboard Wind Estimation in Simulated Atmospheric Turbulence». arXiv 2607.01528v1, 2026. https://arxiv.org/html/2607.01528v1 · B · trechos
- [F21] PX4. «Parameter Reference» (v1.12: `MPC_XY_VEL_I_ACC`; v1.14: `EKF2_MCOEF`/`EKF2_DRAG_CTRL`). https://docs.px4.io/v1.12/en/advanced_config/parameter_reference · https://docs.px4.io/v1.14/en/advanced_config/parameter_reference ; «Controller Diagrams». https://docs.px4.io/main/en/flight_stack/controller_diagrams · A · resumo
- [F22] PX4 Discuss. «INDI Controller on PX4», 2024. https://discuss.px4.io/t/indi-controller-on-px4/36293 · C · resumo
- [F23] ArduPilot. «Windspeed Estimation and Baro Compensation». https://ardupilot.org/copter/docs/airspeed-estimation.html · A · resumo
- [F24] Betaflight. «4.2 Tuning Notes» https://betaflight.com/docs/wiki/tuning/4-2-Tuning-Notes ; «4.3 Tuning Notes» https://betaflight.com/docs/wiki/tuning/4-3-Tuning-Notes · A · resumo
- [F25] PaparazziUAV. Documentação (lista de módulos). https://paparazzi-uav.readthedocs.io · A · resumo
- [F26] ArduPilot Discourse. «Tuning Large drone», 2025. https://discuss.ardupilot.org/t/tuning-large-drone-general-pixhawk-pid-help/133146 · C · resumo
- [F27] Trevisan et al. «Active Disturbance Rejection Control for Trajectory Tracking of a …» (USV). IROS 2025. https://autonomousrobots.nl/assets/files/publications/25-trevisan-iros-adrc.pdf · A · resumo (não é multirrotor)
- [F28] «Deep Reinforcement Learning-Based Wind Disturbance Rejection Control Strategy for UAV». Drones 8(11):632, 2024. https://www.mdpi.com/2504-446X/8/11/632 · B · resumo
- [F29] Pestana, Sanchez-Lopez, Saripalli, Campoy. «Computer Vision Based General Object Following for GPS-denied Multirotor Unmanned Vehicles». ACC 2014. https://orbilu.uni.lu/bitstream/10993/45807/1/06858831.pdf · A · trechos
- [F30] Jabbari Asl, Oriolo, Bolandi. «An Adaptive Scheme for Image-Based Visual Servoing of an Underactuated UAV». Int. J. Robotics and Automation 29(1), 2014. http://www.diag.uniroma1.it/~labrob/pub/papers/IJRA14.pdf · A · trechos
- [F31] Falanga, Foehn, Lu, Scaramuzza. «PAMPC: Perception-Aware Model Predictive Control for Quadrotors». IROS 2018. https://rpg.ifi.uzh.ch/docs/IROS18_Falanga.pdf · A · trechos
- [F32] Falanga, Kim, Scaramuzza. «How Fast Is Too Fast? The Role of Perception Latency in High-Speed Sense and Avoid». IEEE RA-L 4(2), 2019. https://rpg.ifi.uzh.ch/docs/RAL19_Falanga.pdf · A · trechos
- [F33] Guo, Song, Ye, Gu, Jiang. «Image-based visual servoing tracking control of a quadrotor with target estimation and field of view constraints». Chinese J. Aeronautics, 2026 (pré-prova). https://www.sciencedirect.com/science/article/pii/S100093612600292X · A · resumo
- [F34] Dionigi et al. «D-VAT: End-to-End Visual Active Tracking for Micro Aerial Vehicles». IEEE RA-L, 2024. https://arxiv.org/html/2308.16874v2 · A · trechos
- [F35] «Image-Based Adaptive Visual Control of Quadrotor UAV with Dynamics Uncertainties». Electronics 14(15):3114, 2025. https://www.mdpi.com/2079-9292/14/15/3114 · B · resumo
- [F36] «Perception-Aware Image-Based Visual Servoing of Aggressive Quadrotor UAVs» (AIM 2023, vídeo). https://www.youtube.com/watch?v=X2-SMGD99oA · C · resumo
- [F37] Kaufmann et al. «Champion-level drone racing using deep reinforcement learning». Nature 620, 2023. https://pmc.ncbi.nlm.nih.gov/articles/PMC10468397 · A · resumo (já [S1])
- [F38] «MonoRace: Winning Champion-Level Drone Racing with Robust Monocular AI». arXiv 2601.15222, 2026. https://arxiv.org/html/2601.15222v1 · B · trechos
- [F39] Kaufmann, Bauersfeld, Scaramuzza. «A Benchmark Comparison of Learned Control Policies for Agile Quadrotor Flight». ICRA 2022. https://rpg.ifi.uzh.ch/docs/ICRA22_Kaufmann.pdf · A · resumo (já [S3])
- [F40] «A Review of Reinforcement Learning for Multirotor UAVs from a Hierarchical Control Perspective: Biomimetic Architecture and Sim-to-Real». Drones 10(6):448, 2026. https://www.mdpi.com/2504-446X/10/6/448 · A/B · trechos
- [F41] Flight Dynamics and Control Lab (T. Lee, GWU). «Modular Reinforcement Learning for a Quadrotor UAV». https://www2.seas.gwu.edu/~tylee/reinforcement-learning-quadrotor · B/C · integral (página curta)
- [F42] Eschmann, Albani, Loianno. «Learning to Fly in Seconds». IEEE RA-L 9(7), 2024. https://arxiv.org/html/2311.13081v2 · A · trechos (já [S4])
- [F43] Stable-Baselines3. «PPO». https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html · A · resumo literal
- [F44] Stable-Baselines3. «Vectorized Environments». https://stable-baselines3.readthedocs.io/en/master/guide/vec_envs.html · A · resumo; + guia https://medium.com/@hoon33710/scaling-your-gym-environments-dummyvecenv-vs-subprocvecenv-40a5a03ef268 · C
- [F45] EnvPool. «Benchmark». https://envpool.readthedocs.io/en/latest/content/benchmark.html ; Weng et al., arXiv 2206.10558. https://arxiv.org/html/2206.10558v2 · A · resumo
- [F46] MuJoCo 3.15. «MuJoCo XLA (MJX)» — cópia local `docs/upstream/mujoco/doc/mjx.rst`; em linha https://mujoco.readthedocs.io/en/stable/mjx.html · A · lida localmente
- [F47] MuJoCo 3.15. «Python › rollout» — cópia local `docs/upstream/mujoco/doc/python.rst` e `python/rollout.ipynb.md`; em linha https://mujoco.readthedocs.io/en/stable/python.html ; discussão #1522 https://github.com/google-deepmind/mujoco/discussions/1522 · A / C · lida localmente / resumo
- [F48] Zakka et al. «MuJoCo Playground». arXiv 2502.08844, 2025. https://arxiv.org/html/2502.08844v1 · B · trechos
- [F49] Rudin, Hoeller, Reist, Hutter. «Learning to Walk in Minutes Using Massively Parallel Deep Reinforcement Learning». CoRL 2021. https://ar5iv.labs.arxiv.org/html/2109.11978 · A · trechos
- [F50] Chen et al. «What Matters in Learning A Zero-Shot Sim-to-Real RL Policy for Quadrotor Control? A Comprehensive Study» (SimpleFlight). IEEE RA-L 10, 2025. https://arxiv.org/html/2412.11764v4 · A · trechos
- [F51] QGroundControl. «Fly View» (guia, master). https://docs.qgroundcontrol.com/master/en/qgc-user-guide/fly_view/fly_view.html · A · trechos
- [F52] DJI. «Mavic 3E/3T User Manual» (DJI Pilot 2 — Camera View). https://dl.djicdn.com/downloads/DJI_Mavic_3_Enterprise/DJI_Mavic_3E_3T_User_Manual_EN.pdf · A · trechos
- [F53] «Understanding The DJI Pilot 2 Status Bar: Episode 3» (vídeo), 2022. https://www.youtube.com/watch?v=Hf3BUnRiUaQ · C · transcrição parcial
- [F54] DJI. «Mini 3 User Manual» (DJI Fly). https://dl.djicdn.com/downloads/DJI_Mini_3/UM/DJI_Mini_3_User_Manual_V1.0_EN.pdf · A · resumo
- [F55] ArduPilot. «Mission Planner — Flight Data Screen Overview». https://ardupilot.org/planner/docs/mission-planner-ground-control-station.html · A · resumo
- [F56] Betaflight. «Setup Guide › OSD Settings» https://betaflight.com/docs/wiki/getting-started/setup-guide ; «OSD Tab» https://betaflight.com/docs/wiki/app/osd-tab · A · resumo; + guia UAVMODEL https://blog.uavmodel.com/betaflight-osd-configuration-custom-layouts-warnings-and-post-flight-data-2026-guide · C
- [F57] INAV. «On Screen Display» (`docs/OSD.md`). https://github.com/iNavFlight/inav/blob/master/docs/OSD.md · A · resumo
- [F58] NASA. «Head-Up Displays and Attention Capture». Technical Memorandum, NTRS 20040065771, 2004. https://ntrs.nasa.gov/api/citations/20040065771/downloads/20040065771.pdf · A · trechos
- [F59] FAA. «AC 25-11B — Electronic Flight Displays», 2014. https://www.faa.gov/documentlibrary/media/advisory_circular/ac_25-11b.pdf · A · trechos
- [F60] FAA/Volpe. «General Guidance — Chapter 3, Section 7: Color», 2013. https://hfcc.dot.gov/publications/docs/GeneralGuidance/zz_FAA_GeneralGuidanceDoc_Chapter_03_Section_07.pdf · A · trechos
- [F61] Van der Burg et al. «Attentional Tunneling in Pilots During a Visual Tracking Task With a Head Mounted Display». Human Factors, 2025. https://journals.sagepub.com/doi/full/10.1177/00187208241236395 · A · resumo
- [F62] FAA Office of Aerospace Medicine. «Operational Human Factors Considerations for Head-Worn Displays», relatório 2025-07. https://www.faa.gov/data_research/research/med_humanfacs/oamtechreports/media/202507.pdf · A · resumo

## 7. Incidentes de segurança (injeção de prompt)

Nenhum: o escudo da skill não sinalizou nenhuma fonte e não vi instruções dirigidas ao agente nos textos lidos.

## 8. Limitações

- **Modo normal, sem verificação adversarial.** Cada afirmação assenta em 1–3 fontes lidas por trechos; as
  marcadas «(resumo)» só no snippet do motor de pesquisa. Três números vêm só de resumo e merecem releitura
  antes de irem para um README: 6,4 vs 19,3 cm [F12], «5× menor» [F16] e «< 50 px» [F31].
- **DJI:** a conclusão «não há lei de controlo publicada» é uma ausência após ≈ 12 pesquisas; não li patentes em
  chinês (CNIPA) nem teses de antigos engenheiros da DJI. Nomes de autores de [F15] não confirmados.
- **Vento:** nenhuma fonte com hélices ≥ 13″ exceto o octorrotor de [F15]; não há tempos de execução de
  INDI/ESO em MCU; ADRC em multirrotor ficou sem um número de voo real fiável (só simulação e um barco).
- **Câmara fixa:** sem tabela erro-vs-latência publicada; guinada fraca não tratada por ninguém.
- **Multi-rede:** [F20] e [F41] sem voo real quantificado; *ensembles* — ausência, não refutação.
- **Treino:** todos os débitos publicados são de outros ambientes; nada sobre GPUs de 8 GB.
- **Cockpit:** as normas de fatores humanos são de aviação tripulada; a transposição para um GCS de drone é
  analogia razoável, não resultado medido.

## 9. Metodologia

- Motor: `tavily-agent-skill` em modo NORMAL — 66 `search` (profundidade `advanced`, 5–6 resultados) e 30
  `extract` com `--query` (1 falhou: PDF da TU Delft). Sem `--deep-research`, sem subagentes.
- Documentação oficial do MuJoCo 3.15 lida na cópia local (`docs/upstream/`, `docs_search.py`).
- Estado do projeto usado para calibrar: memória CoALA #10020, #10553, #10371, #9805, #7978 e `train.py`.
- Regra de leitura: «facto documentado» exige fonte primária (fabricante, paper, documentação); tudo o que é
  dedução minha está marcado como inferência, hipótese ou síntese.
