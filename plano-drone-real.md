# Drone real — pesquisa, bateria (1 h), limite de rotação, consumos e plano de integração no v09

> **Estado (2026-10-09) — documento ÚNICO de referência, na raiz do projeto.** Por decisão do dono:
> a experiência separada `experiments/10_drone_rpi` foi **apagada**; tudo o que aqui está **incrementa o
> `09_drone_hover_rl`**. Este documento **funde** o antigo `experiments/09_drone_hover_rl/parecer_sim2real.md`
> (§7) com a pesquisa nova (bateria para 1 h de voo, limite de rotação, desgaste/percentagem no site,
> consumo do RPi 5 e do giroscópio) e com o **plano de implementação completo** (§6). Quem executa o
> plano é o próximo modelo (o dono vai usar um modelo mais potente). Conteúdo web = `untrusted`,
> citado como evidência factual; parâmetros a confirmar por SysID quando o hardware existir.

---

## 0. Estado da implementação (2026-10-10) — o plano está FEITO

Implementado de ponta a ponta no `09_drone_hover_rl`, com **peças reais trocáveis** (catálogo com fontes) e
validado por fórmulas fechadas (`run.py` → `valida_real.py`: **96 checagens da planta real, todas [OK]**).

| Item do plano | Onde está | Validação |
|---|---|---|
| B0 — o veículo é o do dono | `lab/drone_rpi/` gera o MJCF a partir do **build ativo** (`models/drone_rpi/builds.json`) | A1–A4 (massa = Σ peças, CM, geometria, kf/kq) |
| Peças reais trocáveis | `models/drone_rpi/componentes.json` (motores T-Motor com tabelas de ensaio, hélices, células, frames, ESC, eletrónica, sensores) + `hardware.py listar/comparar/mostrar/usar/montar/coala` + memória CoALA (`drone/peca/*`, `drone/build-ativo`) | A5 (modelo vs tabela do fabricante) |
| P0.1 motores brushless reais | `propulsao.py`: modelo elétrico DC (I = (d·V − K_e·ω)/R, Q₀(ω), J·ω̇), travagem ativa, **curva do ESC calibrada na tabela**, DShot11, empuxo/reação e saturação POR ROTOR, atraso de comando 8 ms | B1–B8 |
| P0.2 bateria | `bateria.py` (Thevenin 1-RC, Coulomb, R₀(T, SoC, SoH), térmica, desgaste persistente) + Newton bateria↔ESC na `planta.py` | C1–C10, H1 |
| P0.3 observação REAL | `env_real.py`: ator = 21 entradas de sensores + estimação de bordo + ação anterior; crítico assimétrico com o privilegiado (`politica.py`) | F1–F4 |
| P0.4 consumidores no ledger | RPi 5 (5 W), FC, IMU, ToF, fluxo, INA226, perdas do BEC | C9, C11 (pairagem medida na planta = catálogo), C12 (autonomia restante) |
| P1.5 sensores + DR | `sensores.py` (bias, deriva, ruído, escala, saturação, quantização, atraso, vibração) + DR de massa/inércia/CM/kf/kq/J/R/KV/I₀/η/SoC/SoH/R_bat/T/atraso/ruído/arrasto/solo/VRS | E1–E5, F4 |
| P1.6 site: bloco Bateria | `sim_view.py` (telemetria `bateria/motores/potencia/aero/estimador`, pack persistente em `out/bateria/`), `sim_site.py` (`POST /api/bateria`), blocos Bateria/Motores/Hardware no site | `INTERFACE.md` §8 |
| P1.7 arquitetura FC | `fc.py`: malha de taxa 500 Hz (PID com ganhos calculados da planta), mistura X, airmode, idle; política `ctbr` a 50 Hz | G1–G2 |
| P1.8 / §8.2–8.3 solo + arrasto de rotor | `aero.py` (Sanchez-Cuevas 2017; Faessler & Franchi) | D1–D4 |
| P2.9 inflow, VRS, download, giroscópico, frio | `aero.py` (BEMT ajustado à APC 15×5.5MR), `bateria.py` (Arrhenius) | D5, D5b, D6, D8, C4 |
| Validações §6/§8.5 | `valida_real.py` (ligado ao `run.py`) | 96/96 |
| Treino com os dados das peças | `train.py --planta real` grava `hardware.json` (peças + derivados + DR) ao lado da política; `deploy.py` exporta só o ator `(1, 21)` | `avaliar_real.py` (grelha de 9 condições) |

**Decisão do §3 (1 h ⇒ classe ≥ 10″ + Li-ion) — tomada com peças reais**: build ativo
`endurance_15pol_p50b` = T-Motor **MN4004 KV300** + **P15×5 CF**, **6S2P Molicel P50B** (216 Wh), frame DIY 650 mm,
RPi 5 + FC H7 + BMI088/VL53L1X/PMW3901/INA226 → **1664 g, 133 W em pairagem (12,5 g/W), T/W 3,4,
autonomia de pairagem 99 min no modelo** (~80–90 min reais esperados; ver `models/drone_rpi/README.md`).
Alternativas no catálogo: semi-sólido Tattu (128 min, só dados do fabricante), 17″ 4S (89 min), frame comercial
Tarot 650 (66 min), X500 V2 13″ (54 min), o 5″ do plano (13 min).

**Correções ao plano** (impostas pela implementação e pela pesquisa verificada de 2026-10-10):

1. **§5 "ω_max = KV·V_terminal" sobrestima o teto**: a 100 % de acelerador o rpm real é 0,64–0,80·KV·V (tabelas
   T-Motor, verificado 3-0). O ω_max vem da **curva do ESC** calibrada linha a linha na tabela (com KV/R físicos);
   sem ela o T/W do build ativo sairia 4,9 em vez de 3,4. O decaimento com a descarga mantém-se (−29 % de T_max
   de 100 % a 10 % de SoC).
2. **§6 P0.1 τ_sub/τ_desc fixos** foram substituídos pelo modelo elétrico: τ = J/(K_t²/R + dQ₀/dω + 2·kq·ω)
   (= 58 ms no 15″, medido no B3 a 0,1 %); a assimetria vem da travagem ativa do ESC vs roda livre (B4).
3. **§8.2**: a fonte clássica é **Cheeseman & Bennett** (1955), não "Bishop"; para multirrotor usa-se
   Sanchez-Cuevas 2017 (+21 % a 0,5·D). A 1,75·D o multirrotor ainda tem **+5 %** (a sustentação do corpo decai
   devagar) — o "volta a igualar a > 1,75 D" só vale para o rotor isolado; ≈ 1 só a ~5 m.
4. **§8.5 (c) tinha o sinal trocado**: à mesma rotação, **subir REDUZ** o empuxo (−26 % a 3 m/s nesta 15″, J ≈ 0,17)
   e **descer aumenta-o** (+7 % a 1 m/s) até ao VRS — é o que dizem a teoria de momento e as curvas C_T(J)
   medidas (UIUC APC 14×7) e publicadas (APC 15×5.5MR).
5. **§2.3 η = 0,78**: a pesquisa verificada dá 0,65–0,80 (motor+ESC); o modelo usa a física (η ≈ 0,79 em pairagem)
   e ainda **+7,5 % de binário** porque os ensaios independentes ficam 6–9 % abaixo das tabelas T-Motor.
6. **§6 P0.3 "giroscópio + acelerómetro + ação anterior" não chega** — o próprio §7 A mostra que só com a IMU a
   pairagem não é observável. A observação do ator junta sensores REAIS e baratos (ToF VL53L1X + fluxo ótico
   PMW3901, o par do Flow deck) e a estimação de bordo que o RPi faria (atitude por filtro complementar, rumo
   integrado, altura/v_z, velocidade pelo fluxo, odometria) — nada privilegiado; xyz só na recompensa.
7. **Baterias**: nenhuma alegação de células/packs passou a verificação 2/3 da pesquisa (fontes únicas); os
   valores (About:Energy, Mooch, fabricantes) estão no catálogo marcados para medir no pack real.
8. **A recompensa v2b do cf2 não serve com sensores reais**: com penalidades ilimitadas por passo e −100 no fim,
   quando o drone deriva cada passo custa mais do que cair — o 1.º treino aprendeu a descer/cair (z médio 0,56 m
   aos 0,8 M passos). A planta real usa a **v3-real**, limitada (estar vivo vale sempre ≥ 0; ver o README do 09):
   com ela a política paira a 1 m com ~4 cm de deriva em < 0,5 M passos.
9. **O coletivo compensa a tensão MEDIDA da bateria** (como o `vbat_sag_compensation` do Betaflight; o INA226 é
   um sensor real de bordo): sem isso, com a bateria cheia o "acelerador de pairagem" nominal dava 1,34× o peso e
   o drone disparava. A política continua sem ver a bateria (só telemetria, como pede o §6 P1.6).

10. **O xy é limitado pelo estimador, não pela política**: com sensores reais a política segura a posição
    ESTIMADA a 1–5,5 cm, e a odometria por fluxo ótico deriva 2–11 cm da verdade em 10 s — o erro verdadeiro
    (~6 cm nominal, ~9 cm sob DR) é quase todo do estimador. O próximo ganho de precisão vem do estimador de bordo
    (ou de uma referência absoluta), não de mais treino.

**Resultado (política final, 2026-10-10)** — PPO + crítico assimétrico, 16 ambientes com DR, currículo de vento até
3 m/s e *fine-tune* com rajadas: `experiments/09_drone_hover_rl/out/real_endurance15_rajadas/final.zip`
(2,51 M passos, ~35 min de treino nesta máquina). Em 5 episódios por condição: **100 % de sobrevivência em todas as condições**
(nominal, SoC 50/25 %, vento 2–3 m/s, rajadas até +3 m/s, frente de vento, DR, DR + vento); \|Δz\| 1,1 cm
nominal e 1,8 cm sob DR; ‖xy‖ 6,0–7,0 cm nominal/vento (83–93 % ≤ 10 cm) e ~9 cm sob DR; 130 W em pairagem
(= o catálogo) → 103 min mostrados com o pack cheio. Igual a 100/50/25 % de SoC (a compensação de tensão
funciona). Deploy: ONNX (1, 21) → (1, 4), 94,6 kB, p99 7,4 µs num core (proxy do A76), 4 IAs a 50 Hz sem
perdas. Tabelas completas no README do 09.

Uso: `hardware.py comparar` → `hardware.py usar <build>` → `run.py` → `train.py --planta real --out-dir
experiments/09_drone_hover_rl/out/real_<nome>` → `sim_site.py` (escolhe sozinho a política `out/real_*`) →
`deploy.py --model …/final.zip` → `avaliar_real.py --model …/final.zip`.

---

## 1. Premissas do dono (2026-10-09)

1. **Hardware do drone que se vai construir**: 4 **motores brushless** (velocidade comandável, com
   dinâmica real de subida/descida), **Raspberry Pi 5** como computador de bordo, **sensor de
   giroscópio**; **bateria** agora **incluída** — dimensionada para **1 h de voo**, com **desgaste** e
   **percentagem** a aparecer **no site**.
2. **Realismo obrigatório**: treino e execução só com dados reais. A posição **xyz pode** entrar na
   **penalidade/recompensa**; **nunca** nas entradas da política.
3. Consumos reais de **todos** os consumidores contam para a bateria: motores (dominante), **RPi 5**,
   **módulo de giroscópio**, ESCs/BEC.
4. **Limite de rotação** dos motores considerado: o teto de RPM depende da tensão da bateria e decai
   com a descarga (e com o desgaste).
5. Entrega deste documento: tudo o que deve ser feito, com os dados da pesquisa, num markdown na raiz.

---

## 2. Pesquisa — dados com fontes

### 2.1 Consumo elétrico (o que a bateria tem de alimentar)

| Consumidor | Consumo | Fonte |
|---|---|---|
| **Raspberry Pi 5** | **2,7–3,0 W** em idle (headless); **3,6 W** com periféricos; **4–8 W** em carga; **8,8 W** de pico | [raspberry.tips — consumo Pi 4/5](https://raspberry.tips/en/raspberrypi-tutorials/raspberry-pi-power-consumption-update-2026-all-models-compared) · [Tom's Hardware Pi 5](https://www.tomshardware.com/reviews/raspberry-pi-5) |
| **Sensor de giroscópio MPU6050** | 3,7 mA (só giro) / **3,9 mA** (giro+accel) a 3,3 V ≈ **13 mW** | [datasheet MPU-6050 (rev 3.4)](https://www.cdiweb.com/datasheets/invensense/mpu-6050_datasheet_v3%204.pdf) |
| **BMI088** (IMU de drone) | ≈ 5 mA giro (normal) / 5,15 mA total ≈ **17 mW** | [datasheet BMI088 (Bosch)](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi088-ds001.pdf) |
| **ESCs + BEC** | ~1–2 W (perdas + regulação 5 V do RPi) | estimativa de engenharia — medir no build |
| **Motores (hover)** | ver §3 — domina tudo (dezenas a centenas de W) | §3 |

Para o simulador: **`P_eletrónica ≈ 6 W`** (RPi 5 em voo ≈ 5 W + IMU ≈ 0,01 W + BEC/diversos ≈ 1 W).
O MPU6050 é *legacy* (sensores "not for new designs") — para o build real o **BMI088/ICM-20602** é a
escolha recomendada (vibração, ruído, SPI 10 MHz).

### 2.2 Bateria — energia, massa, tensão, resistência, desgaste

| Grandeza | Valor | Fonte |
|---|---|---|
| Densidade energética **LiPo** | **~150 Wh/kg** (140–200+ Wh/kg) | [UAVMODEL — LiPo vs Li-Ion](https://blog.uavmodel.com/fpv-drone-battery-guide-lipo-vs-li-ion-and-c-ratings-explained) · [Tyto Robotics — guide to LiPo](https://www.tytorobotics.com/blogs/articles/a-guide-to-lithium-polymer-batteries-for-drones) |
| Densidade energética **Li-ion (21700)** | **~250 Wh/kg** (até 265) | [UAVMODEL](https://blog.uavmodel.com/fpv-drone-battery-guide-lipo-vs-li-ion-and-c-ratings-explained) · [Grepow](https://www.grepow.com/blog/grepow-high-energy-density-battery-solutions-for-commercial-drone.html) |
| Descarga máxima | LiPo 50–150 C · Li-ion 10–35 C | [UAVMODEL](https://blog.uavmodel.com/fpv-drone-battery-guide-lipo-vs-li-ion-and-c-ratings-explained) |
| Tensão por célula | **4,20 V cheia · 3,7 V nominal · 3,5–3,6 V** = limite prático (preserva ciclos) · 3,0 V vazio | [UDPOWER — Li-ion voltage chart](https://udpwr.com/blogs/portable-power-station-knowledge/ultimate-guide-to-lithium-ion-battery-voltage-chart) · [Grepow 4S LiPo](https://www.grepow.com/blog/what-is-a-4s-lipo-battery.html) |
| Curva OCV vs SoC (célula, em repouso) | 100 % = 4,20 · 90 % = 4,05 · 80 % = 3,95 · 70 % = 3,85 · 60 % = 3,80 · 50 % = 3,75 · 40 % = 3,70 · 30 % = 3,65 · 20 % = 3,55 · 10 % = 3,45 V | [UDPOWER](https://udpwr.com/blogs/portable-power-station-knowledge/ultimate-guide-to-lithium-ion-battery-voltage-chart) (tabela OCV na curva standard Li-ion)(https://udpwr.com/blogs/portable-power-station-knowledge/ultimate-guide-to-lithium-ion-battery-voltage-chart) |
| Resistência interna (pack LiPo) | **2–5 mΩ/célula** novo (bom < 10 mΩ); 10–15 mΩ ok; > 20 mΩ = reforma | [ChinaHobbyLine — LiPo IR](https://chinahobbyline.com/blogs/news/lipo-internal-resistance-explained) · [Oscar Liang — quando reformar](https://oscarliang.com/when-retire-lipo-battery) |
| **Desgaste (SoH)** | cada ciclo perde capacidade e **aumenta R_int** (crescimento da camada SEI); **80 % de capacidade = fim de vida**; LiPo **300–500 ciclos** até 80 %; carga/descarga profundas e altas correntes **aceleram** | [Vozwin — SoH em drones (631 voos)](https://vozwin.com/en/guides/drone-battery-state-of-health-prediction) · [Herewin — comparação de químicas](https://www.herewinpower.com/blog/industrial-drone-batteries-2026-li-po-vs-lifepo4-vs-solid-state-comparison-selection-guide) |
| Estimativa de SoC | **contagem de Coulomb** (principal) + correção por OCV; EKF combina os dois (OCV sozinho é impreciso na curva plana do Li) | [Powertech — SoC measurement](https://www.powertechsystems.eu/tech-corner/lithium-ion-state-of-charge-soc-measurement) · [TI — Battery Gauging (SLUAAR3)](https://www.ti.com/lit/SLUAAR3) (V_medida = OCV − I·R) |

### 2.3 Eficiência de hover (quanto voo por watt)

| Referência | Medido |
|---|---|
| Build endurance 5″, 244 g a 2,2 A (~26,8 W) | **9,1 g/W** ([Endurance quad build](https://www.youtube.com/watch?v=BnOX6QdqdhE)) |
| Build endurance 5″, 31+ min de voo | 6,2 g/W ([RotorBuilds](https://rotorbuilds.com/build/25530)) |
| Classe 5″ típica (freestyle, LiPo) | 4–7 min de voo por pack ([UAVMODEL 5″ vs 7″](https://blog.uavmodel.com/5-inch-vs-7-inch-fpv-build-flight-characteristics-efficiency-and-component-selection-2026-guide)) |

A eficiência **cai com a massa** (carga de disco): calibramos dois modelos de hover que reproduzem os
medidos: **P_kq(M)** (o do nosso lab: `T = kf·ω²`, `P = Σkq·ω³/η`) e **P_emp(M) = 222·M^1,5 W**
(calibrado nos 26,8 W/244 g). Tabela de referência:

| M total | P (modelo kq) | g/W | P (empírico) | g/W |
|---|---|---|---|---|
| 0,40 kg | 66 W | 6,1 | 56 W | 7,1 |
| 0,60 kg | 121 W | 5,0 | 103 W | 5,8 |
| 0,80 kg | 186 W | 4,3 | 159 W | 5,0 |
| 1,00 kg | 260 W | 3,9 | 222 W | 4,5 |
| 1,30 kg | 385 W | 3,4 | 329 W | 4,0 |

---

## 3. Bateria para 1 h de voo — dimensionamento e O ACHADO CRÍTICO

Massa fixa do drone (sem bateria, do build de referência 5″): frame 100 g + 4× motor 2306 128 g +
4× ESC 24 g + **RPi 5 46 g** + HAT/cablagem 30 g = **328 g**. Bateria por ponto fixo:
`m_bat = (P_hover(m_fixo + m_bat) + P_eletrónica) · 1 h / (ρ · f_usável)` com `f_usável = 0,8`
(janela 4,2→3,5 V/célula; usar 100 %–0 % estraga o pack).

### 3.1 Resultado: **com propulsão 5″, 1 h de voo é FISICAMENTE INVIÁVEL**

| Química | ρ · f_usável | Resultado (ambos os modelos de P) |
|---|---|---|
| LiPo 195 Wh/kg | 156 Wh/kg | **DIVERGE** |
| Li-ion 21700 250 Wh/kg | 200 Wh/kg | **DIVERGE** |
| Li-ion 265 Wh/kg | 239 Wh/kg | **DIVERGE** |

O ponto fixo não existe: cada grama de bateria acrescentado exige mais hover do que a energia que
carrega. Condição de convergência: `1,5 · P_hover · 1 h < m_total · ρ_usável` (derivada de `P ∝ M^1,5`)
⇒ seria preciso **> 27 g/W** em hover com 200 Wh/kg — a classe 5″ faz 4–7 g/W. Isto **não se resolve
com mais bateria**; resolve-se com **mais eficiência** (hélices maiores) ou menos tempo.

### 3.2 O que É alcançável (números para decidir)

| Cenário (5″, m_fixo 328 g) | Bateria | M total | P hover | **Autonomia** |
|---|---|---|---|---|
| LiPo 4S 5000 mAh | 74 Wh, 380 g | 0,71 kg | 138–161 W | **22–26 min** |
| Li-ion 4S2P 21700 | 144 Wh, 560 g | 0,89 kg | 192–223 W | **31–36 min** |
| LiPo 6S 5000 mAh | 111 Wh, 570 g | 0,90 kg | 195–227 W | 23–27 min |

Com a bateria Li-ion 4S2P 21700 (560 g) chega-se aos **~35 min** — o máximo sensato da classe 5″.

### 3.3 Como obter 1 h: mudar a classe de propulsão

Com hélices de **10″ e motores de baixo KV** (classe endurance, ~11 g/W a ~0,6 kg), o ponto fixo
**converge**: `m_bat ≈ 0,25 kg` (Li-ion 21700, 4S1P ≈ 280 g) · **M total ≈ 0,58 kg** · **P ≈ 50 W** ·
**60 min**. Alternativas: 7–10″ com motores 2806/2212 low-KV, ou manter 5″ e aceitar 30 min.
**Decisão para o dono** (impacta frame/motores/hélices): *1 h ⇒ classe 10″ + Li-ion; 5″ ⇒ ≤ ~35 min.*

---

## 4. Modelo de bateria a implementar (simulador + site)

Tudo isto entra no v09 como camada física/telemetria (nada mágico: corrente vem do que os motores e a
eletrónica realmente puxam):

1. **Ledger de potência** (a cada passo de decisão):
   `P_total = P_motores + P_RPi5 + P_IMU + P_BEC`, com
   `P_motores = Σ_i kq·ω_i³/η` (η ≈ 0,78 motor+ESC — calibrar por SysID),
   `P_RPi5 = 5 W` (perfil voo; faixa 3–8,8 W), `P_IMU ≈ 0,013 W`, `P_BEC ≈ 1 W`.
2. **SoC por contagem de Coulomb** (o que o site mostra como **%**):
   `SoC(t) = SoC₀ − ∫ I dt / C_usável(SoH)` com `I = P_total / V_terminal`.
3. **Tensão terminal** (sag sob carga): `V_terminal = N_s · OCV_célula(SoC) − I · R_int(SoH, SoC)`
   (OCV da tabela §2.2; `N_s = 4`; R_int ≈ 12 mΩ de pack novo — 3 mΩ/célula).
4. **Desgaste (SoH)** — persistente entre episódios/ciclos:
   `C_usável(SoH) = C_novo · SoH` · `SoH ← SoH − fade_por_ciclo·(DoD, C-rate, temperatura)`,
   `R_int(SoH) = R_novo·(1 + k·(1−SoH))`. Calibração: 300–500 ciclos LiPo até 80 % ⇒ fade médio
   ≈ **0,04–0,07 %/ciclo** (mais com descargas profundas/correntes altas); **80 % = fim de vida** (o
   site pode mostrar "reformar").
5. **% no site**: bloco "Bateria" com **SoC %**, `V`, `I`, `P`, **autonomia restante (min)**,
   **SoH %**, **ciclos** e a curva de descarga; ligação ao contrato existente do `sim_site.py`
   (telemetria JSONL + controlo atómico por ficheiro — ver `experiments/09_drone_hover_rl/INTERFACE.md`).

## 5. Limite de rotação e empuxo vs estado da bateria

O teto de rotação dos motores é **`ω_max = KV · (V_terminal)`** (KV em rad/s por V) e o empuxo teto é
`T_max = kf·ω_max²` — logo **ambos decaem com a descarga**. Simulado com 2450 KV (2306, 4S),
I ≈ 20 A, R_int = 12 mΩ (valores em **%** do estado cheio — os absolutos dependem da calibração):

| SoC | V sob carga | ω_max | **T_max (4 rotores)** |
|---|---|---|---|
| 100 % | 16,56 V | 100 % | 100 % |
| 80 % | 15,56 V | 92,6 % | 85,8 % |
| 50 % | 14,76 V | 87,9 % | 77,2 % |
| 20 % | 13,96 V | 83,1 % | 69,0 % |
| 10 % | 13,56 V | 80,7 % | **65,1 %** |

⇒ ao fim da bateria o drone **perde ~1/3 do empuxo máximo** — o simulador deve refletir isto
(`OMEGA_MAX`, `T_ROTOR_MAX` dinâmicos em função de `V_terminal`), e o desgaste (R_int a subir)
agrava o sag. É exatamente o "limite de rotação" pedido: **velocidade máxima de rotação = f(tensão)**.

---

## 6. O que fazer — plano de implementação no `09_drone_hover_rl`

Prioridades **P0** (sem isto não há realismo) → **P2** (refinamentos). Onde há detalhe técnico já
resolvido, a referência está entre parênteses.

### P0 — planta, motores e observação real
1. **Motores brushless reais** no lugar dos 4 canais de wrench instantâneos (o `cf2.xml` upstream não
   se toca — adaptação em runtime via MjSpec/`lab`):
   - 4 velocidades de rotor ω com **lag de 1.ª ordem assimétrico** (τ_sub ≈ **11 ms**, τ_desc ≈
     **27 ms**; alternativa Tm ≈ 72 ms — §7 B2) integradas à taxa de física, escrevendo 1 canal de
     empuxo **por rotor** (`mjcb_act_dot` **não existe** no binding Python do 3.15 — verificado — por
     isso a camada ESC/Motor integra ω e as forças entram sempre via `mj_step`);
   - lei **T = kf·ω²**, momento de reação **±kq·ω²**, saturação **por rotor** (acabou a "caixa" de
     comandos impossíveis), quantização **DShot11**, atraso de comando **8 ms** (pior caso medido do
     RPi 5 com Linux normal; `PREEMPT_RT` = 28 µs);
   - parâmetros de referência 5″ 2306+5×4.3 4S: `T_max = 11,77 N/rotor`, `ω_max = 2827 rad/s
     (27 000 RPM)`, `kf = 1,4734e-6 N/(rad/s)²`, `kq/kf = 0,016 m` — **mas o veículo do v09 é o
     Crazyflie**; se o alvo for o drone do dono (RPi 5 a bordo), a massa/inércia/propulsão têm de
     passar para a escala certa (o CF2 de 27 g **não transporta um RPi 5 de 46 g** — ver §7 B0);
2. **Bateria** (§4): ledger de potência, SoC por Coulomb, V_terminal com sag, `ω_max/T_max` dinâmicos
   (§5), SoH/desgaste persistente, telemetria para o site;
3. **Observação REAL** (§7 A): remover da entrada da política a posição xyz, a velocidade ground-truth e
   a atitude ground-truth; ficar com **giroscópio medido** (bias pós-calibração + deriva + ruído +
   amostragem + atraso — presets MPU6050/BMI088 verificados no trabalho de 2026-10-09) **+ acelerómetro
   se a IMU o tiver** + ação anterior; xyz continua **na recompensa** (permitido);
4. **Consumidores reais no ledger**: RPi 5 (5 W voo) + módulo de giroscópio (13 mW) + BEC (§2.1).

### P1 — sensores, treino e site
5. **Modelo de sensor** completo (bias + random walk + ruído + atraso 1–4 ms) **na fonte das leituras**;
   domain randomization de `kf, kq, τ, massa, R_int, SoH, ganhos de sensor` (o estudo
   [SimpleFlight, arXiv 2412.11764](https://arxiv.org/html/2412.11764v2) aponta SysID de `m, I, kf, Tm`
   + randomização seletiva como fator crítico de sim-to-real);
6. **Site**: bloco "Bateria" (SoC %, V, I, W, autonomia min, SoH %, ciclos) + alerta de tensão baixa;
   a política não recebe nada disto — é telemetria;
7. **Arquitetura de controlo** (§7 C1): política na malha externa (50 Hz) sobre setpoints; malha
   interna de atitude a 250 Hz+ (PREEMPT_RT) ou FC dedicado — a documentação real diz que Linux puro
   não serve de FC primário ([arXiv 2604.19275](https://arxiv.org/pdf/2604.19275)).

### P1 (cont.) — aerodinâmica (detalhe e modelos em §8)
8. **Efeito de solo** (ganho `g(h)` por rotor — a descolagem acontece a **cada** episódio, +20–37 % de
   empuxo a < 1,75 D) e **arrasto de rotor** (linear no frame corpo, `d ≈ 0,26–0,43 s⁻¹`) — modelos,
   receitas em MuJoCo e fontes em §8.2/§8.3; validações correspondentes no `run.py` (§8.5).

### P2 — refinamentos físicos
9. **Aerodinâmica restante** (§8.1/§8.4): empuxo vs inflow (`c_T(v_a/(ωR))`), vortex ring em descida
   (`v_i = sqrt(T/(2ρA))`, perda acima de ~6 m/s), flapping/downwash; mais queda de tensão com
   temperatura, quantização ESC fina, variação de massa.

### Validações a acrescentar ao `run.py` (fórmulas fechadas, exit code)
- massa com bateria = soma do orçamento · `P_hover` medida ≈ modelos §2.3 (±20 %);
- SoC: 1 h de consumo constante ⇒ SoC desce à taxa `I/C` · Coulomb counting conserva carga;
- `V_terminal = OCV − I·R` exato · sag aumenta com R_int (SoH);
- **limite de rotação**: `ω_max(t)` decresce com SoC; `T_max = kf·ω_max²`;
- τ_sub/τ_desc medidos (63,2 %) · `T = kf·ω²` · saturação por rotor · DShot · atraso de comando;
- **contrato de realidade**: observação **invariante** a (x,y,z,v); recompensa **varia** com xyz;
- % de bateria e autonomia restante coerentes com o ledger.

---

## 7. Parecer de sim-to-real (fundo do antigo `parecer_sim2real.md` do 09 — fundido)

Premissa histórica: drone + giroscópio + 4 motores brushless; xyz só na penalidade. Veredito: com o
contrato antigo **não havia transferência para o real**. Classes de defeito:

**A — Informação que não existe na realidade (entradas da política).** A obs do 09 (`env.py`, 16 dim)
leva: `[0:3]` posição xyz absoluta (sensor `framepos` = mocap/GPS) ✗ · `[3:6]` atitude ground-truth
(`body_quat`) ⚠ (roll/pitch estimáveis de accel+gyro; **yaw não observável** só com giroscópio — alvo
`yaw=0` no frame mundo exige magnetómetro) · `[6:9]` velocidade ground-truth (`data.qvel`) ✗ ·
`[9:12]` ω do giroscópio ✔ · `[12:16]` ação anterior ✔. **9 de 16 componentes não existiam no
hardware.** Observabilidade: com **só giroscópio** o hover é **matematicamente impossível** (sem
referência de gravidade nem de altitude); mínimo = IMU 6 eixos; pairagem em posição exige
barómetro/fluxo ótico. A recompensa pode (e deve) continuar a usar xyz.

**B — Atuação irreal.** B0: o veículo tem de ser o do dono (um CF2 de 27 g não carrega um RPi 5) ·
B1: os "4 motores" eram um wrench de corpo instantâneo (cf2.xml:117–122), sem estado de rotor ·
B2: sem lag de motor/ESC (literatura: 11 ms subida / 27 ms descida; Tm ≈ 72 ms no CF2) — o chatter de
momentos documentado no próprio 09 era sintoma disto · B3: saturação em caixa (comandos infactíveis:
empuxo máx. **e** momento máx. — com 4 rotores saturados os momentos são nulos) · B4: sem zona morta
ESC/sag de bateria (o sag está agora resolvido em §5).

**C — Comportamentos inexistentes na realidade.** C1: torque comandado a 50 Hz sem malha interna (real:
cascata 50 Hz→1 kHz→ESC); C2: sem efeito de solo na descolagem; C3: sem arrasto de rotor; C4: sensores
perfeitos (`ruido_obs` nunca usado no treino); C5: sem atraso de transporte.

**D — Treino/deploy.** D1: ator e crítico com info privilegiada (remédio: *asymmetric actor-critic* —
xyz no crítico/recompensa, nunca no ator); D2: domain randomization só do vento (falta SysID `m, I,
kf, Tm` + parâmetros de bateria/sensor); D3: `OBS_DIM=16` do `deploy.py` dependia de entradas
impossíveis.

---

## 8. Aerodinâmica — o que considerar (pesquisa aprofundada, 2026-10-09)

**Estado atual**: o simulador tem **arrasto do corpo** (modelo de caixa de inércia: arrasto quadrático
anisotrópico + Stokes, ligado por `density/viscosity`) e **vento físico** — e **só isso**. O empuxo dos
motores é `T = kf·ω²` **constante**: no MuJoCo o empuxo é idêntico a qualquer velocidade de escoamento,
densidade ou altitude (verificado no Q8 #20: idêntico de z = 0,02 a 5 m e com v_z = ±8 m/s). Tudo o que
segue é o que falta e **vai ser considerado** (prioridades revistas em §6/§8.5).

### 8.1 Empuxo vs velocidade de escoamento (inflow / advance ratio)
- **Física**: o rotor é um disco atuador (teoria de momento: `T = 2ρAv_h²` em hover); com escoamento
  axial/oblíquo o coeficiente de empuxo `C_T` e o de potência `C_P` **caem não-linearmente** com o
  *advance ratio* `J = v/(n·D)` ([ENAC — propeller forces/moments](https://enac.hal.science/hal-01979077v1/document)).
  Modelos de momento clássicos falham a indução alta — o empuxo real continua a subir com a indução
  ([unified momentum model, 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11339364)).
  O modelo de **Gupta 2018** ([Wiley](https://onlinelibrary.wiley.com/doi/10.1155/2018/9632942)) liga
  velocidade de inflow a `C_T` com **291 pontos motor-hélice** — boa base de calibração.
- **Hoje no lab**: nada — `T = kf·ω²` aplanado.
- **Implementar**: correção multiplicativa do empuxo por rotor,
  `T_eff = kf·ω²·c_T(v_axial/(ω·R))` com `c_T` decrescente (ex.: `1 − k_v·(v_axial/(ω·R))`, cortada em
  `[0.4, 1.2]`, `k_v` por identificação); v_a positiva em descida (reduz) e negativa em subida (aumenta
  ligeiramente). Prioridade **P2** para hover; **P1** se houver descidas rápidas.

### 8.2 Efeito de solo (IGE) — afeta a DECOLAGEM de cada episódio
- **Física**: o solo limita a esteira, o ângulo de ataque das pás sobe e **o empuxo aumenta** (e a
  potência de hover cai) abaixo de ~1 raio de hélice do solo. Medido: **+20–30 %** de empuxo (MDPI 2025)
  e **até +37 %** abaixo de ~1,75 D ([Springer](https://link.springer.com/content/pdf/10.1007/978-981-95-7840-5_30.pdf);
  Q8 #22); *ducted fan* sobe exponencialmente até +26 % ([Springer 2024](https://link.springer.com/article/10.1186/s42774-024-00179-z));
  a potência necessária em hover desce "rapidamente" abaixo de 1 R ([UMD 2006](https://drum.lib.umd.edu/bitstreams/3ffcf0ad-dd75-4a7a-8a0f-2ae13b7a4ead/download)).
- **Hoje no lab**: nada (empuxo idêntico a 2 cm e a 5 m do solo — Q8).
- **Implementar**: ganho `g(h)` sobre o empuxo dos rotores, `h` = altura do rotor acima do solo, corte a
  ~1,75 D. Modelo clássico de momentum com "imagem" (usado em muitos simuladores):
  `T_IGE = T_OGE / (1 − (R/(4h))²)` — **confirmar na fonte primária (Cheeseman–Bishop) antes de fixar
  constantes**; alternativa empírica do `gym-pybullet-drones` (`_groundEffect()`, constante × (R/h)² com
  velocidades e raio das hélices — [Shi et al. 2019 / Forster 2015](https://ar5iv.labs.arxiv.org/html/2103.02142)).
  No MuJoCo: multiplicar na camada ESC/Motor (por rotor, a `h` de cada rotor) ou `xfrc_applied` com
  ganho `g(z)` (receita verificada no `drones.md` §5). **Prioridade P1** — entra logo a seguir ao P0.

### 8.3 Arrasto de rotor (força-H) e blade flapping — o erro nº 1 a velocidade
- **Física**: flapping + arrasto induzido das pás dão uma força **linear na velocidade do corpo**
  (frame corpo), proporcional à velocidade de rotação das hélices — distinta do arrasto do corpo.
  É o **principal erro de rastreio em voo rápido** (Faessler RAL17; Q8 #22).
- **Modelo identificado** ([Faessler & Franchi, arXiv 1712.02402](https://arxiv.org/html/1712.02402v3)):
  `a = −diag(d_x, d_y, d_z)·Rᵀ·v` com **`d_x = 0,425 s⁻¹` e `d_y = 0,256 s⁻¹`** identificados em
  trajetória circular (variam com a trajetória/empuxo — o arrasto real depende do empuxo, o modelo
  assume que não); preserva *differential flatness* (feed-forward exato). A ENAC estima `k/m` por
  mínimos quadrados ([IMAV 2022](https://enac.hal.science/hal-03859308/file/IMAV2022-4.pdf)). O
  `gym-pybullet-drones` usa arrasto ∝ velocidade × velocidades dos rotores com matriz de coeficientes
  (Forster 2015, Eq. 4.2 — [Panerati et al.](https://ar5iv.labs.arxiv.org/html/2103.02142)).
- **Hoje no lab**: só o arrasto do corpo (caixa de inércia) — **sem** arrasto de rotor.
- **Implementar**: força `F = −m·diag(d_x, d_y, d_z)·(Rᵀv)` aplicada por passo (camada `lab` →
  `xfrc_applied` no frame do corpo), com `d_z` a identificar; opção avançada: escalar `d_i` com
  `Σω_i` (como no Forster). **Prioridade P1** (com vento nos cenários de treino, entra já).

### 8.4 Vortex ring state (descida rápida) e downwash
- **VRS**: em descida a velocidade vertical aproxima-se/excede a **velocidade induzida**
  `v_i = sqrt(T/(2ρA))` e a esteira colapsa num anel de vórtices: empuxo imprevisível, vibração, perda
  de controlo ([NASA 1975](https://ntrs.nasa.gov/api/citations/19750024927/downloads/19750024927.pdf));
  em simulação de UAV pequeno o VRS começa **≈ 6 m/s de descida** ([tese UNCC](https://ninercommons.charlotte.edu/record/2980/files/Hahn_uncc_0694N_14030.pdf));
  modelos de velocidade induzida em descida acentuada/VRS: [NLR/Jimenez](https://dspace-erf.nlr.nl/server/api/core/bitstreams/b15977ea-0bd0-44bd-8a28-6969c08a5ddf/content).
  **Modelo simples**: penalizar o empuxo quando `v_desc > v_i` (ex.: `T_eff·= (1 − k_vrs·((v_desc−v_i)/v_i)²)`,
  corte em 30 %). **P2** (o nosso voo é hover; relevante pousar/descer depressa).
- **Downwash** (interferência entre drones) e esteira do corpo: só com múltiplos drones — **fora de
  âmbito** por agora (`gym-pybullet-drones` tem `_downwash()` pronto para quando for preciso).
- **Flapping puro** (aspeto dinâmico: momento de flapping em manobras agressivas): camada externa;
  o arrasto linear de rotor (§8.3) já capta o seu efeito dominante. **P2**.

### 8.5 Resumo — o que entra, quando e como se valida

| Efeito | Efeito no nosso caso | Modelo | Prioridade |
|---|---|---|---|
| Efeito de solo | descolagem de **cada** episódio (+20–37 % de empuxo a < 1,75 D) | ganho `g(h)` por rotor (§8.2) | **P1** |
| Arrasto de rotor (linear) | vento e voo lateral — erro dominante | `a = −diag(d)·Rᵀv`, d ≈ 0,26–0,43 s⁻¹ (§8.3) | **P1** |
| Empuxo vs inflow | descidas/subidas rápidas | `T_eff = kf·ω²·c_T(v_a/(ωR))` (§8.1) | P2 |
| VRS | descida > ~6 m/s | penalização para `v_desc > v_i` (§8.4) | P2 |
| Flapping / downwash / esteira | manobras agressivas / multi-drone | camada externa (§8.4) | P2 |

**Validações a acrescentar ao `run.py`** (além das do §6): (a) empuxo medido a 0,5 D do solo é ≥ 15 %
superior ao de 5 m (efeito de solo ligado) e volta a igualar a > 1,75 D; (b) arrasto de rotor: a 5 m/s no
eixo x, aceleração = `−d_x·5` ± 10 % (arrasto linear no frame corpo — girar o corpo muda a direção);
(c) empuxo em descida 3 m/s < empuxo em subida 3 m/s (inflow); (d) VRS: perda de empuxo só acima de
`v_i` calculada; (e) tudo desligável por flag (modo "aerodinâmica base" continua bit-idêntico).

---

## 9. Fontes (web = `untrusted`, citadas)

- Consumos: [raspberry.tips](https://raspberry.tips/en/raspberrypi-tutorials/raspberry-pi-power-consumption-update-2026-all-models-compared) ·
  [Tom's Hardware](https://www.tomshardware.com/reviews/raspberry-pi-5) ·
  [datasheet MPU-6050](https://www.cdiweb.com/datasheets/invensense/mpu-6050_datasheet_v3%204.pdf) ·
  [datasheet BMI088](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi088-ds001.pdf)
- Bateria: [UAVMODEL LiPo vs Li-Ion](https://blog.uavmodel.com/fpv-drone-battery-guide-lipo-vs-li-ion-and-c-ratings-explained) ·
  [Tyto Robotics LiPo guide](https://www.tytorobotics.com/blogs/articles/a-guide-to-lithium-polymer-batteries-for-drones) ·
  [Grepow](https://www.grepow.com/blog/grepow-high-energy-density-battery-solutions-for-commercial-drone.html) ·
  [UDPOWER voltage chart](https://udpwr.com/blogs/portable-power-station-knowledge/ultimate-guide-to-lithium-ion-battery-voltage-chart) ·
  [Grepow 4S LiPo](https://www.grepow.com/blog/what-is-a-4s-lipo-battery.html) ·
  [ChinaHobbyLine IR](https://chinahobbyline.com/blogs/news/lipo-internal-resistance-explained) ·
  [Oscar Liang — reforma de LiPo](https://oscarliang.com/when-retire-lipo-battery)
- Desgaste/SoC: [Vozwin SoH](https://vozwin.com/en/guides/drone-battery-state-of-health-prediction) ·
  [Herewin — químicas](https://www.herewinpower.com/blog/industrial-drone-batteries-2026-li-po-vs-lifepo4-vs-solid-state-comparison-selection-guide) ·
  [Powertech SoC](https://www.powertechsystems.eu/tech-corner/lithium-ion-state-of-charge-soc-measurement) ·
  [TI SLUAAR3](https://www.ti.com/lit/SLUAAR3)
- Voo/eficiência: [Endurance quad build](https://www.youtube.com/watch?v=BnOX6QdqdhE) ·
  [RotorBuilds 31+ min](https://rotorbuilds.com/build/25530) ·
  [UAVMODEL 5″ vs 7″](https://blog.uavmodel.com/5-inch-vs-7-inch-fpv-build-flight-characteristics-efficiency-and-component-selection-2026-guide)
- Sim-to-real/controle: [arXiv 2412.11764 (SimpleFlight)](https://arxiv.org/html/2412.11764v2) ·
  [arXiv 2404.07837 (SysID com motor delays)](https://arxiv.org/html/2404.07837v2) ·
  [Faessler RAL17](https://rpg.ifi.uzh.ch/docs/RAL17_Faessler.pdf) ·
  [arXiv 2604.19275 (PREEMPT_RT no RPi 5)](https://arxiv.org/pdf/2604.19275)
- Aerodinâmica: [ENAC — propeller forces/moments](https://enac.hal.science/hal-01979077v1/document) ·
  [Gupta 2018 — inflow vs C_T](https://onlinelibrary.wiley.com/doi/10.1155/2018/9632942) ·
  [unified momentum model (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11339364) ·
  [Faessler & Franchi — rotor drag](https://arxiv.org/html/1712.02402v3) ·
  [ENAC — drag coefficient (IMAV 2022)](https://enac.hal.science/hal-03859308/file/IMAV2022-4.pdf) ·
  [Springer — efeito de solo não-linear](https://link.springer.com/content/pdf/10.1007/978-981-95-7840-5_30.pdf) ·
  [Springer 2024 — ducted fan IGE](https://link.springer.com/article/10.1186/s42774-024-00179-z) ·
  [UMD 2006 — quad tilt rotor em hover](https://drum.lib.umd.edu/bitstreams/3ffcf0ad-dd75-4a7a-8a0f-2ae13b7a4ead/download) ·
  [gym-pybullet-drones (Panerati et al.)](https://ar5iv.labs.arxiv.org/html/2103.02142) ·
  [NASA — vortex ring state](https://ntrs.nasa.gov/api/citations/19750024927/downloads/19750024927.pdf) ·
  [UNCC — VRS em descida de UAV](https://ninercommons.charlotte.edu/record/2980/files/Hahn_uncc_0694N_14030.pdf) ·
  [NLR/Jimenez — velocidade induzida em VRS](https://dspace-erf.nlr.nl/server/api/core/bitstreams/b15977ea-0bd0-44bd-8a28-6969c08a5ddf/content)
- Locais: `references/drones.md` §3.3/§5 e `pesquisas/conhecimento/Q8.md` (lag de motor, efeito de solo,
  arrasto de rotor), `references/actuators-sensors.md` (`dcmotor`), `lab/drone_rpi.py` +
  `models/drone_rpi/` (camada de motores/sensores já escrita e validada em 2026-10-09 — reutilizar).
