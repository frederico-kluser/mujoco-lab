# `models/drone_rpi` — o drone que o dono vai construir, com PEÇAS REAIS trocáveis

> Plano e decisões: **`plano-drone-real.md`** (raiz) — implementado em 2026-10-10 (ver a secção 0 do plano).
> Camada de física: **`lab/drone_rpi/`** · ambiente RL: **`experiments/09_drone_hover_rl/env_real.py`** ·
> trocar peças: **`experiments/09_drone_hover_rl/hardware.py`**.

Não é um modelo vendorizado: não existe "modelo pronto" de um drone DIY com Raspberry Pi 5 a bordo. Em vez de
um XML desenhado à mão, o drone é **gerado das peças**: escolhe-se um *build* (frame + motor + hélice + pack
de bateria + ESC + eletrónica + sensores) e tudo o resto é derivado por fórmulas a partir dos dados do
fabricante — massa, inércia (o MuJoCo integra os geoms com as massas reais), kf/kq, constantes elétricas do
motor, curva do ESC, ω_max(V), pairagem, autonomia.

| Ficheiro | O que é |
|---|---|
| `componentes.json` | **catálogo de peças reais** com fontes e grau de confiança (`fabricante`/`medido`/`estimado`) |
| `builds.json` | combinações nomeadas e o **build ATIVO** (o que o treino, o site e a validação usam) |
| `drone_rpi.xml` | MJCF **gerado** do build ativo (`hardware.py xml`) — para inspecionar/abrir no viewer; não editar |

A memória CoALA tem uma cópia pesquisável do catálogo (`hardware.py coala` → chaves `drone/peca/<grupo>/<id>`,
`drone/build/<nome>`, `drone/build-ativo`): pergunte ao agente "que baterias temos?", "troca o motor para…".

## Trocar peças (motores, baterias, hélices, frame…)

```bash
uv run python experiments/09_drone_hover_rl/hardware.py listar              # peças e builds
uv run python experiments/09_drone_hover_rl/hardware.py comparar            # builds lado a lado
uv run python experiments/09_drone_hover_rl/hardware.py mostrar [build]     # orçamento, pairagem, ω_max(SoC)
uv run python experiments/09_drone_hover_rl/hardware.py dimensionar [--celula X --s N]   # quanta bateria?
uv run python experiments/09_drone_hover_rl/hardware.py usar <build>        # ATIVO + XML + CoALA
uv run python experiments/09_drone_hover_rl/hardware.py montar --nome meu --motor tmotor_mn4006_kv380 \
    --helice tmotor_p15x5 --celula molicel_p45b --s 6 --p 2 --usar         # build novo a partir do ativo
```

Peça nova = uma entrada em `componentes.json` com as fontes (para motores, a **tabela de ensaio** do
fabricante: acelerador, tensão, corrente, rpm, binário, empuxo). Depois: `run.py` (valida a física) e **um
treino novo** — o `train.py` grava o `hardware.json` (peças + derivados + domain randomization) ao lado de cada
política, porque uma política só vale para as peças com que treinou.

## Os builds (2026-10-10, números derivados do catálogo)

| build | massa | pack | Wh | pairagem | g/W | acelerador | T/W | autonomia (modelo) |
|---|---|---|---|---|---|---|---|---|
| **`endurance_15pol_p50b`** (ATIVO) | 1664 g | 871 g | 216 | 133,2 W | 12,5 | 53,2 % | 3,43 | **99,0 min** |
| `endurance_15pol_semisolido` | 1593 g | 800 g | 266 | 125,1 W | 12,7 | 50,7 % | 3,59 | 127,6 min |
| `endurance_15pol_tarot` (frame comercial 750 g) | 2129 g | 871 g | 216 | 197,0 W | 10,8 | 62,8 % | 2,68 | 66,2 min |
| `endurance_16pol_m50lt` | 1660 g | 855 g | 218 | 131,6 W | 12,6 | 48,0 % | 3,67 | 97,9 min |
| `endurance_17pol_4s` (MN5006 KV450 + P17×5.8, 4S3P) | 1935 g | 871 g | 216 | 147,0 W | 13,2 | 45,8 % | 5,48 | 89,2 min |
| `pesado_18pol_6s3p` (MN5006 KV300 + P18×6.1) | 2386 g | 1298 g | 324 | 181,8 W | 13,1 | 42,7 % | 5,78 | 108,9 min |
| `independente_mn4006_mf1302` (ensaio Tyto) | 1704 g | 871 g | 216 | 148,0 W | 11,5 | 56,3 % | 3,86 | 88,8 min |
| `lipo_15pol_mn4006_4s` (LiPo Tattu 4S 10 Ah) | 1793 g | 940 g | 148 | 140,3 W | 12,8 | 63,1 % | 2,67 | 63,3 min |
| `x500_13pol_p45b` (Holybro X500 V2) | 1931 g | 837 g | 194 | 216,1 W | 8,9 | 77,7 % | 1,95 | 54,0 min |
| `compacto_12pol_mn2806` | 1497 g | 443 g | 108 | 162,8 W | 9,2 | 60,2 % | 2,95 | 39,3 min |
| `referencia_5pol` (o 5″ do plano) | 533 g | 184 g | 22 | 106,0 W | 5,0 | 30,1 % | 11,5 | 12,6 min |

"autonomia (modelo)" = pairagem em ar parado até à tensão de pouso (Li-ion 3,0 V/célula sob carga; LiPo 3,5 V;
semi-sólido 2,88 V do fabricante), com download do frame, queda de tensão, BEC e eletrónica de bordo.

**Realismo — o que o modelo já desconta e o que não.** A pesquisa profunda (2026-10-10, 104 agentes,
verificação adversarial com 3 votos) confirmou: (1) os ensaios INDEPENDENTES ficam **6–9 % abaixo** das tabelas
T-Motor → o modelo soma **+7,5 % ao binário** das hélices calibradas por tabela (`CORRECAO_KQ_TABELA`);
(2) a 100 % de acelerador o rpm real é só **0,64–0,80·KV·V** → ω_max vem da tabela (curva do ESC), nunca de
KV·V; (3) **download do frame 5–15 %** (NASA) → 5 % no frame de tubo. Não descontado: interação rotor–rotor,
manobras e vento (a autonomia é de pairagem pura), frio. O caso real mais próximo (ArduPilot, MN4006 + 15″,
3,6 kg) voou 36 min contra 50–55 da tabela; o build com a medição INDEPENDENTE (Tyto) dá 11,5 g/W — em linha
com o melhor relato real com 15″ (~11,7 g/W). Expectativa honesta para o build ativo: **~80–90 min reais**,
com margem sobre a meta de 1 h. ⚠ **Baterias**: nenhuma alegação de células/packs passou a verificação 2/3
(fontes únicas — About:Energy, Mooch, fabricantes); estão marcadas no catálogo (`verificacao`) e devem ser
medidas (capacidade a 1C e DCIR) quando o pack existir.

**Quanta bateria?** (`hardware.py dimensionar`, o ponto fixo do §3 do plano com peças reais — mesmo frame,
motores e hélices, Molicel P50B em 6S):

| pack | massa total | pack | Wh | pairagem | g/W | T/W | autonomia |
|---|---|---|---|---|---|---|---|
| 6S1P | 1228 g | 435 g | 108 | 86,7 W | 14,2 | 4,65 | 75,6 min |
| **6S2P** (ativo) | 1664 g | 871 g | 216 | 133,2 W | 12,5 | 3,43 | **99,0 min** |
| 6S3P | 2099 g | 1306 g | 324 | 187,0 W | 11,2 | 2,72 | 105,8 min |
| 6S4P | 2534 g | 1741 g | 432 | 247,6 W | 10,2 | 2,25 | 106,4 min |
| 6S5P | 2970 g | 2176 g | 540 | 314,6 W | 9,4 | 1,92 | 104,6 min (T/W < 2) |

Cada grama de bateria pede mais empuxo (g/W cai): a partir de 2P quase não se ganha autonomia e perde-se
margem de controlo — o 6S2P é o ponto doce (o mesmo vale para o LG M50LT: 74 → 98 → 105 → 106 min).

## O build ativo: `endurance_15pol_p50b`

| Peça | Escolha | Dados |
|---|---|---|
| Motor ×4 | **T-Motor Antigravity MN4004 KV300** | 53 g, R 452 mΩ, I₀ 0,2 A @ 22 V, 9 A/216 W de pico, 4–6S — tabela de ensaio a 24 V com 13–17″ (fabricante) |
| Hélice ×4 | **T-Motor P15×5 CF** | 21 g; da tabela: **kf = 5,22×10⁻⁵ N/(rad/s)²**, **kq = 1,058×10⁻⁶ N·m/(rad/s)²** (9,84×10⁻⁷ da tabela +7,5 % de realismo; C_T ≈ 0,080 e C_P ≈ 0,025 — verificados 0,079–0,081 / 0,024–0,026) |
| ESC ×4 | **T-Motor AIR 40A 6S** | 26 g cada (o recomendado pela T-Motor; um 4-em-1 de ~15 g pouparia ~90 g) |
| Bateria | **6S2P Molicel P50B** (12 × 21700) | 10 Ah, 216 Wh, 871 g (248 Wh/kg), DCIR medido 15 mΩ/célula (About:Energy) → R₀ do pack 45 mΩ, 750 ciclos até 80 % |
| Frame | **DIY X 650 mm** (tubo de carbono 16 mm + placas 1,5 mm) | 235 g + 50 g de pernas, **massa ESTIMADA** pela densidade do carbono — pesar o frame montado e corrigir; braços finos ⇒ download 5 % (NASA) |
| Computador | **Raspberry Pi 5** + dissipador | 52 g, 5 W em voo (2,7 idle / 8,8 pico) |
| FC | H7 30×30 (Betaflight/ArduPilot) | 8 g, 0,6 W — faz a malha de taxa (o Linux não serve de FC primário) |
| Sensores | BMI088 (IMU) · VL53L1X (ToF) · PMW3901 (fluxo ótico) · INA226 (V/I) | ≈ 3 g, ≈ 0,12 W — o mínimo para a pairagem ser OBSERVÁVEL sem GPS (plano §7 A) |

Orçamento: frame 235 + pernas 50 + motores 212 + hélices 84 + ESC 104 + bateria 871 + RPi 5 52 + FC 8 +
cablagem/BEC 30 + sensores 3 + diversos 15 = **1664 g**. Pairagem a 21,6 V: 2739 rpm, ciclo útil 48,4 %
(acelerador 53,2 %), 126,7 W nos motores + 6,5 W de eletrónica = **133,2 W (12,5 g/W)**; motor+ESC η ≈ 0,79
(verificado: 0,80 a 50 % nesta combinação). Rotor: J = 1,62×10⁻⁴ kg·m² ⇒ **τ ≈ 58 ms**.

**Limite de rotação** (sob a corrente de pairagem; decai com a descarga e com o desgaste):

| SoC | V sob carga | ω_max | T_max (4 rotores) | T/W |
|---|---|---|---|---|
| 100 % | 24,90 V | 4898 rpm | 5,60 kgf | 3,37 |
| 80 % | 23,40 V | 4649 rpm | 5,05 kgf | 3,03 |
| 50 % | 22,20 V | 4447 rpm | 4,62 kgf | 2,77 |
| 20 % | 21,00 V | 4242 rpm | 4,20 kgf | 2,52 |
| 10 % | 20,40 V | 4138 rpm | 4,00 kgf | 2,40 |

## Como as peças viram física (o que o catálogo alimenta)

- **Hélice**: kf/kq por mínimos quadrados sobre a tabela do fabricante (empuxo e binário medidos vs ω²);
  sem tabela, C_T/C_P (convenção UIUC) com a forma C_T(J) da APC/UIUC.
- **Motor BLDC** (modelo DC equivalente): K_e = K_t = 60/(2π·KV), I = (d·V − K_e·ω)/R, perdas em vazio
  Q₀(ω) = K_t·I₀·(½ + ½·ω/ω₀), J·ω̇ = K_t·I − Q₀ − kq·ω². **Achado da calibração**: com o KV e a R do
  datasheet, a tabela T-Motor só fecha se o ESC entregar d ≈ 0,46 a 50 % e d ≈ 0,83 a 100 % de acelerador
  (perdas de comutação/limite do ESC) — a **curva acelerador→duty** é calibrada linha a linha e o modelo
  reproduz a tabela com erro ≤ 1 % em rpm e ≤ 5 % em corrente (`run.py` A5). Sem esta curva o T/W sairia
  4,9 em vez dos 3,4 reais (a pesquisa verificada confirma: com KV/R do datasheet o modelo DC explica só
  79–90 % da tensão a 100 % — perdas que crescem com a velocidade e a corrente).
- **Bateria** (Thevenin 1-RC): OCV(SoC) da química, R₀(T, SoC, SoH), térmica do pack, desgaste por ciclo
  calibrado nos ciclos do datasheet — `lab/drone_rpi/bateria.py`.
- **Aerodinâmica**: efeito de solo (Sanchez-Cuevas 2017), inflow axial (BEMT com σa ajustado à curva C_T(J)
  publicada da APC 15×5.5MR: 0,707 vs 0,709 a J = 0,19), VRS, arrasto de rotor
  (Faessler & Franchi), download do frame, giroscópico — `lab/drone_rpi/aero.py`.
- **Sensores**: erro de datasheet (bias, deriva, ruído, escala, saturação, quantização, atraso) + vibração.

## Fontes (web = `untrusted`, citadas como evidência; detalhe por peça em `componentes.json`)

- Motores (tabelas de ensaio): [T-Motor MN4004](https://store.tmotor.com/product/mn4004-kv400-motor-antigravity-type.html) ·
  [MN4006](https://store.tmotor.com/product/mn4006-kv380-motor-antigravity-type.html) ·
  [MN2806](https://store.tmotor.com/product/mn2806-motor-antigravity-type.html) ·
  [MN5006](https://store.tmotor.com/product/mn5006-kv450-motor-antigravity-type.html) · caso real
  [ArduPilot — endurance](https://discuss.ardupilot.org/t/endurance-of-drone/117451)
- Hélices: [T-Motor P15×5](https://store.tmotor.com/product/polish-carbon-fiber-15x5-prop.html) ·
  [APC PER3 15×5.5MR](https://www.apcprop.com/files/PER3_15x55MR.dat) ·
  [UIUC vol. 4](https://m-selig.ae.illinois.edu/props/volume-4/propDB-volume-4.html) ·
  [Deters et al. 2017](https://m-selig.web.engr.illinois.edu/pubs/DetersKleinkeSelig-2017-AIAA-Paper-2017-3743.pdf) ·
  [NASA Ames 2016 (FOM, download)](https://rotorcraft.arc.nasa.gov/Publications/files/72-2016-374.pdf)
- Células/packs: [About:Energy P50B vs P45B](https://www.aboutenergy.io/post/molicel-p50b-vs-p45b-battery-performance) ·
  [Mooch P50B](https://www.e-cigarette-forum.com/threads/bench-test-results-molicel-p50b-60a-5000mah-21700.986092) ·
  [LG M50LT](https://f.hubspotusercontent10.net/hubfs/6584819/Cell%20Spec%20Sheets/LG/Lithium%20Ion%20LG%20INR%2021700%20M50LT%202021-LSD-MBD-b00002_21700_M50LT_PS_Promotion_V1.pdf) ·
  [Samsung 50E](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/INR21700_2D00_50E-Cell-Specification_5F00_V1.0_5F00_180711.pdf) ·
  [Amprius](https://amprius.com/documents/Amprius_Product_Catalog.pdf) ·
  [Tattu semi-sólido 6S 12 Ah](https://www.tattuworld.com/products/tattu-380wh-kg-12000mah-6s1p-22-2v-10c-semi-solid-state-uav-lipo-battery.html) ·
  [Tattu G-Tech 4S 10 Ah](https://www.grepow.com/uav-battery/tattu-4s-10000mah-14-8v-25c-lipo-drone-battery.html) ·
  [Endless-Sphere — ciclos](https://endless-sphere.com/sphere/threads/cycle-life-tests-of-high-power-density-cylindrical-cells.114473)
- Frames/ESC/builds: [Holybro X500 V2](https://holybro.com/products/x500-v2-kits) ·
  [Tarot 650 Sport](https://www.readymaderc.com/products/details/86704-tarot-tl65s01-650-sport-carbon-quad-frame-w-retracting-gear) ·
  [T-Motor AIR 40A](https://store.tmotor.com/product/air-40a-6s-esc.html) ·
  [1 h com 250 g (ArduPilot)](https://discuss.ardupilot.org/t/how-to-build-a-1-hour-250g-ardupilot-quadcopter/115400) ·
  [HSKRC 3S3P 1 h](https://rotorbuilds.com/build/20411)
