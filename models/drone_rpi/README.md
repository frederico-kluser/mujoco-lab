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

## Os builds (2026-10-11, números derivados do catálogo)

> **2026-10-11 — o módulo de câmara FPV entrou no orçamento**: todos os builds ganharam a **Raspberry Pi
> Camera Module 3 Wide** (Sony IMX708, 4 g, `componentes.json` → `cameras`), montada **à frente** do
> drone e ligada ao RPi 5 por CSI-2. Os números das tabelas são DEPOIS da câmara; antes o build ativo era
> 1663,6 g · 133,2 W · 99,0 min (a câmara custa 4 g e ~0,4 min de autonomia).
>
> **2026-10-11 — WHEELBASE ×3 no build ativo (650 → 1950 mm, frame `diy_tubo_carbono_1950`)**, pedido do
> dono para ganhar estabilidade. Só o `endurance_15pol_p50b` migra (os outros builds mantêm os frames de
> 650/750 mm como alternativas do catálogo). Tubos **25×23 mm** (16 mm seria flexível demais a ~850 mm de
> braço), frame+pernas **800 g** (faixa da pesquisa 750–850 g, fórmula no catálogo).
>
> **Arma fixa no topo — Glock 25 (.380 Auto, `componentes.json` → `armas.glock_g25`)**: montada fixa no topo da
> pilha central, apontada para $+x$ (boca do cano em `site="boca_cano"`), com **785 g** (carregador cheio de 15
> tiros; 645 g vazia; 575 g sem carregador), projétil 95 gr (6,156 g) a 296 m/s ($E_0 = 269,7\text{ J} \approx 270\text{ J}$),
> impulso de recuo $J_{\text{tiro}} = 1,9162\text{ N}\cdot\text{s}$ ($F = 95,81\text{ N}$ em 20 ms, $\Delta v = -0,6457\text{ m/s}$
> em $-\hat{x}_{\text{corpo}}$ e cabragem $\Delta\omega_y = -1,025\text{ rad/s}$). Com a Glock 25 no topo, o
> `endurance_15pol_p50b` passa a **2968 g, 314,2 W em pairagem (9,44 g/W), T/W 1,93 e 40,7 min de autonomia**
> (e o `endurance_15pol_arduino` passa a **2922 g, 302,1 W, T/W 1,96 e 42,5 min**). O que a mudança faz
> (medições do modelo + `pesquisas/relatorio-bracos-3x-estabilidade.md`):
>
> | grandeza | 650 mm | 1950 mm | fator |
> |---|---|---|---|
> | J (roll/pitch/yaw) 0,0218/0,0230/0,0429 → 0,2343/0,2355/0,4674 kg·m² = ×10,75/×10,25/×10,91
> | J guinada (MEDIDO) | 0,0218 kg·m² | 0,234 kg·m² | ×10,7 |
> | torque roll/pitch (τ = L·ΔT) | τ | 3τ | ×3 |
> | aceleração angular máx. (τ/J) | α | ≈0,26 α | **÷3,7** |
> | aceleração de GUINada (o par das hélices não escala com L) | αψ | ≈0,09 αψ | **÷10–12** |
> | ganhos do FC (MEDIDOS: `kp = 1/(α·4ζ²·tm)`, derivados DA PLANTA) | — | roll ×4,05 · pitch ×3,87 · yaw ×12,35 | retuning **automático** (pesquisa esperava ×3,5–4 e ×10–11) |
> | massa total | 1668 g | **2183 g** | +31 % (pesquisa: 2150–2250 ✓) |
> | pairagem | 2742 rpm | **3137 rpm** | +14 % (pesquisa ~3150 ✓) |
> | potência de pairagem | 133,6 W | **198,1 W** | +48 % (pesquisa 190–206 W ✓) |
> | autonomia (modelo) | 98,6 min | **65,8 min** | −33 % (pesquisa 64–70 min ✓) |
> | T/W | 3,43 | **2,62** | (pesquisa 2,5–2,7 ✓) |
>
> **Estabilidade vs agilidade**: atitude mais "pesada" (J ×11) ⇒ menos sensível a ruído/assimetrias e
> menos twitchy, mas ~3,7× mais lenta em roll/pitch e ~10× em guinada — e a **deriva lateral em vento piora**
> (área frontal dos braços ×4,7 vs massa +31 %: drift ×3,6). "Mais estável" = mais calmo, não mais
> resistente a vento. O `VOO_VEL` mantém-se 1,0 m/s (o dono pediu LIBERDADE de espaço, não menos
> velocidade) — a planta nova é menos ágil e o rastreio a altas velocidades pode degradar.
> **Riscos ditos** (não modelados): (1) o **1.º modo de flexão dos braços (~35–45 Hz) colide com o prop
> passing (46–51 Hz)** — o simulador assume CORPO RÍGIDO; (2) o download mútuo cai (rotores a 3,6 D) e o
> ground effect enfraquece — o `perda_download` mantém-se 5 % até medir (a pesquisa sugere −2 a −4 %);
> (3) políticas treinadas no 650 ficam FORA da planta (retreino à parte); (4) o FC retuning é automático,
> mas a banda útil continua limitada pela constante de tempo do motor (τm ≈ 56 ms, inalterada).

| build | massa | pack | Wh | pairagem | g/W | acelerador | T/W | autonomia (modelo) |
|---|---|---|---|---|---|---|---|---|
| **`endurance_15pol_p50b`** (ATIVO, wheelbase ×3) | 2183 g | 871 g | 216 | 198,1 W | 11,0 | 63,0 % | 2,62 | **65,8 min** |
| `endurance_15pol_arduino` (o p50b com **Portenta H7 + Vision Shield** em vez de RPi 5 + FC + Pi Camera; NÃO é o ativo) | 2137 g | 871 g | 216 | 186,7 W | 11,4 | 62,1 % | 2,67 | 70,0 min |
| `articulado_15pol_mn5006` (**braços articulados**, 2026-10-19: 8 juntas com servos + Glock 25 de 785 g; MN5006 KV450; NÃO é o ativo) | 4464 g | 871 g | 216 | 557,0 W | 8,0 | 61,5 % | 2,58 | 22,0 min |
| `articulado_15pol_abs` (**braços articulados ACESSÍVEIS**, 2026-10-20: peças impressas em ABS, ombro de fuso Tr8×2 + JGB37-520, cotovelo DS3218MG; MASSAS MEDIDAS na geometria; o que o cockpit voa; NÃO é o ativo) | 6601 g | 871 g | 216 | 981,0 W | 6,7 | 75,9 % | 2,31 | 11,3 min |
| `endurance_15pol_semisolido` | 1597 g | 800 g | 266 | 125,5 W | 12,7 | 50,7 % | 3,58 | 127,2 min |
| `endurance_15pol_tarot` (frame comercial 750 g) | 2133 g | 871 g | 216 | 197,6 W | 10,8 | 62,9 % | 2,68 | 66,0 min |
| `endurance_16pol_m50lt` | 1664 g | 855 g | 218 | 132,0 W | 12,6 | 48,0 % | 3,66 | 97,6 min |
| `endurance_17pol_4s` (MN5006 KV450 + P17×5.8, 4S3P) | 1939 g | 871 g | 216 | 147,4 W | 13,2 | 45,8 % | 5,47 | 89,0 min |
| `pesado_18pol_6s3p` (MN5006 KV300 + P18×6.1) | 2390 g | 1298 g | 324 | 182,2 W | 13,1 | 42,7 % | 5,77 | 108,6 min |
| `independente_mn4006_mf1302` (ensaio Tyto) | 1708 g | 871 g | 216 | 148,5 W | 11,5 | 56,4 % | 3,85 | 88,5 min |
| `lipo_15pol_mn4006_4s` (LiPo Tattu 4S 10 Ah) | 1797 g | 940 g | 148 | 140,7 W | 12,8 | 63,2 % | 2,66 | 63,1 min |
| `x500_13pol_p45b` (Holybro X500 V2) | 1935 g | 837 g | 194 | 216,8 W | 8,9 | 77,8 % | 1,94 | 53,8 min |
| `compacto_12pol_mn2806` | 1497 g | 443 g | 108 | 162,8 W | 9,2 | 60,2 % | 2,95 | 39,3 min |
| `referencia_5pol` (o 5″ do plano) | 533 g | 184 g | 22 | 106,0 W | 5,0 | 30,1 % | 11,5 | 12,6 min |

"autonomia (modelo)" = pairagem em ar parado até à tensão de pouso (Li-ion 3,0 V/célula sob carga; LiPo 3,5 V;
semi-sólido 2,88 V do fabricante), com download do frame, queda de tensão, BEC e eletrónica de bordo.

**Computador de bordo Arduino (2026-10-12)**: o catálogo tem `eletronica.arduino_portenta_h7` (+ `arduino_nicla_vision` e
`arduino_giga_r1`, só para comparação) e `cameras.portenta_vision_shield_hm0360` / `_hm01b0` (câmaras MONOCROMÁTICAS de
8 bit, DVP → DCMI, sem CSI-2). Os números vêm das fichas oficiais da Arduino/Himax; o que não tem número oficial (massa do
Portenta, lente/FoV das shields) está em `estimado` com a razão e a fonte. O build `endurance_15pol_arduino` troca só o
computador/câmara do p50b (o Portenta não tem IMU: fica o BMI088). Detalhe e ressalvas: secção «Computador de bordo Arduino»
de `experiments/09_drone_hover_rl/README.md`; prova: `teste_arduino_catalogo.py`.

**Braços articulados (2026-10-19)**: o catálogo ganhou `servos` (DYNAMIXEL XH430-V210-R — o escolhido —, XH430-V350-R e
XH540-V270-R, números das fichas ROBOTIS), `sensores.ams_as5048a` (encoder de 14 bits na saída do ombro) e
`mecanismos_braco.ombro_semfim_cotovelo_mastro`: ombro com **sem-fim 20:1 autobloqueante** (λ = 3,81° < φ = 5,71°,
η = 0,397; batentes ±40°, folga 0,5°) e cotovelo direto com **mastro = raio da hélice + 40 mm** (batentes ±60°), os 8 eixos
paralelos ao y do corpo; massas de mastros, dobradiças e regulador de 24 V entram no orçamento (o parser recusa um sem-fim
declarado autobloqueante que não o seja). O build `articulado_15pol_mn5006` declara também **`fc_margem_fase_min_graus: 45`**:
o MN5006 a 4,5 kg é rápido (τ_motor 24,5 ms) e as fórmulas do FC punham a malha de taxa a 30° de margem — com a chave os
ganhos saem de um τ de projeto de 36,9 ms (`fc.tau_de_projeto`). Nenhum outro build tem a chave (ficam bit a bit iguais).
Detalhe, números medidos e prova: secção «BRAÇOS ARTICULADOS» de `experiments/09_drone_hover_rl/README.md`,
`teste_bracos.py`.

**Build ACESSÍVEL `articulado_15pol_abs` (2026-10-20)**: frame `diy_tubo_carbono_1950_abs` (as placas, colunas,
abraçadeiras, suportes dos motores, pés e os suportes da eletrónica IMPRESSOS em ABS — o plástico das peças LEGO; os tubos
de carbono 25×23 ficam comprados) e mecanismo `ombro_fuso_impresso_cotovelo_servo`: o OMBRO é uma dobradiça (veio Ø8 em 2 ×
608ZZ numa forquilha impressa) movida por um **atuador linear de fuso** — motorredutor `motorredutor_jgb37_520_12v_1_18_8_enc`
(JGB37-520 12 V, enrolamento rápido, 1:18,8, encoder Hall) + fuso Tr8×2 + porca de latão numa ALAVANCA do cubo impresso
(`ombro.fuso`: a geometria da biela — alavanca, base, passo, d₂, flanco, μ, massas e CM — é a mesma na física, na animação e
na página; o parser deriva dela a redução local N(q), o λ e o φ' da rosca trapezoidal e recusa um fuso declarado
autobloqueante que não o seja); o COTOVELO é um servo DS3218MG a 6,0 V num berço impresso com 608ZZ do outro lado
(`servo_ds3218mg_270`); a energia dos atuadores é 2 × buck 12 V + 4 × DRV8871 + UBEC 6S a 6,0 V (`fonte_servos`, com o
`cm_mm` medido), e os sensores e atuadores de cada lado ligam a um **Raspberry Pi Pico 2** (`eletronica.pico2_bracos`: o H743
não tem entradas para 4 Hall + 4 AS5048A + 4 AS5600 nem PWM para 4 DRV8871 + 4 servos; os Picos falam com o FC por UART). Porque o sem-fim saiu: a pairar o ombro segura ~6,8 N·m e um par sem-fim m1 (ou o m0,8 de 19/10) partiria os
dentes (~470–550 N no dente). As MASSAS do frame, das pernas, das dobradiças, do fuso, do cotovelo, dos mastros, dos
suportes e o «extra» (cabos, abraçadeiras, ferragens soltas e as que prendem as peças com ficha) foram MEDIDAS na geometria
(`python -m lab.drone_rpi.detalhes.massas --build articulado_15pol_abs --atualizar-catalogo`): ABS 1,04 g/cm³ com casca de
1,2 mm + 40 % de enchimento, metais e carbono pela densidade, ferragens pelas malhas das normas, cabos por volume —
6601 g no total (o build de 19/10, 4464 g, não contava cabos, ferragens nem o mecanismo real). Custo de referência
R$ 8.536 (US$ 1.690) e 26 STL para imprimir (1103 g de ABS, ~88 h) — página `/pecas` do cockpit. Pesquisa (medidas e
preços, web = `untrusted`): `pesquisas/2026-10-20-materiais-acessiveis-precos.md`. Provas: `teste_ombro_fuso.py`,
`teste_pecas3d.py`.

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
| 6S1P | 1747 g | 435 g | 108 | 143,0 W | 12,2 | 3,27 | 45,0 min |
| **6S2P** (ativo) | 2183 g | 871 g | 216 | 198,1 W | 11,0 | 2,62 | **65,8 min** |
| 6S3P | 2618 g | 1306 g | 324 | 260,0 W | 10,1 | 2,18 | 75,4 min |
| 6S4P | 3053 g | 1741 g | 432 | 328,1 W | 9,3 | 1,87 | 79,7 min (T/W < 2) |
| 6S5P | 3488 g | 2176 g | 540 | 402,2 W | 8,7 | 1,64 | 78,5 min (T/W < 2) |

Cada grama de bateria pede mais empuxo (g/W cai): com o frame ×3, o 6S2P ainda cumpre a meta
de 1 h (65,8 min) mas o 6S3P passa à frente em autonomia (75,4 min) com T/W 2,18 — a escolha
depois do ×3 é entre autonomia e margem de controlo (antes o 6S2P era o ponto doce).

## O build ativo: `endurance_15pol_p50b`

| Peça | Escolha | Dados |
|---|---|---|
| Motor ×4 | **T-Motor Antigravity MN4004 KV300** | 53 g, R 452 mΩ, I₀ 0,2 A @ 22 V, 9 A/216 W de pico, 4–6S — tabela de ensaio a 24 V com 13–17″ (fabricante) |
| Hélice ×4 | **T-Motor P15×5 CF** | 21 g; da tabela: **kf = 5,22×10⁻⁵ N/(rad/s)²**, **kq = 1,058×10⁻⁶ N·m/(rad/s)²** (9,84×10⁻⁷ da tabela +7,5 % de realismo; C_T ≈ 0,080 e C_P ≈ 0,025 — verificados 0,079–0,081 / 0,024–0,026) |
| ESC ×4 | **T-Motor AIR 40A 6S** | 26 g cada (o recomendado pela T-Motor; um 4-em-1 de ~15 g pouparia ~90 g) |
| Bateria | **6S2P Molicel P50B** (12 × 21700) | 10 Ah, 216 Wh, 871 g (248 Wh/kg), DCIR medido 15 mΩ/célula (About:Energy) → R₀ do pack 45 mΩ, 750 ciclos até 80 % |
| Frame | **DIY X 1950 mm** (tubo de carbono 25×23 mm + placas 1,5 mm — wheelbase ×3, 2026-10-11) | 700 g + 100 g de pernas, **ESTIMADO calibrado em frames reais; as placas ficam em 190–250 g conforme a densidade real do carbono (201 g pela calibração do 650) — PESAR e corrigir** (faixa 750–850 g; braço ≈100 g vs 106 g do Tarot X8); tubo de 16 mm seria flexível demais (1.º modo ~44 Hz vs prop passing 46–51 Hz); download 5 % (NASA) |
| Computador | **Raspberry Pi 5** + dissipador | 52 g, 5 W em voo (2,7 idle / 8,8 pico) |
| FC | H7 30×30 (Betaflight/ArduPilot) | 8 g, 0,6 W — faz a malha de taxa (o Linux não serve de FC primário) |
| Sensores | BMI088 (IMU) · VL53L1X (ToF) · PMW3901 (fluxo ótico) · INA226 (V/I) | ≈ 3 g, ≈ 0,12 W — o mínimo para a pairagem ser OBSERVÁVEL sem GPS (plano §7 A) |
| Câmara | **Raspberry Pi Camera Module 3 Wide** (Sony IMX708) | 4 g, 11,9 MP, FoV 120° diag (102°×67°), vídeo 1080p50/720p100/480p120, PDAF 5 cm–∞ — **montada à frente**, CSI-2 para o RPi 5 (comportamento emulado em `lab/camera_rpi.py`) |

Orçamento: frame 700 + pernas 100 + motores 212 + hélices 84 + ESC 104 + bateria 871 + RPi 5 52 + FC 8 +
cablagem/BEC 30 + sensores 3 + **câmara 4** + diversos 15 = **2183 g**. Pairagem a 21,6 V: 3137 rpm,
ciclo útil 50,5 % (acelerador 63,0 %), 191,6 W nos motores + 6,5 W de eletrónica = **198,1 W (11,0 g/W)**;
motor+ESC η ≈ 0,79 (verificado: 0,80 a 50 % nesta combinação). Rotor: J = 1,62×10⁻⁴ kg·m² ⇒ **τ ≈ 56 ms**.
Inércias de ATITUDE do corpo (MEDIDAS no modelo compilado): Jxx 0,467 · Jyy 0,236 · Jzz 0,234 kg·m²
(×10,9/×10,2/×10,7 face ao frame de 650 mm). O FC deriva os ganhos destes números a cada build
(`fc.py`: `kp = 1/(α·4ζ²·tm)` com `α = 4·a·dT/du / J`) — o retuning do wheelbase ×3 é AUTOMÁTICO
(kp roll ×4,05 · pitch ×3,87 · yaw ×12,35, medidos 650→1950).

**Limite de rotação** (sob a corrente de pairagem; decai com a descarga e com o desgaste):

| SoC | V sob carga | ω_max | T_max (4 rotores) | T/W |
|---|---|---|---|---|
| 100 % | 24,90 V | 4898 rpm | 5,60 kgf | 3,37 |
| 80 % | 23,40 V | 4649 rpm | 5,05 kgf | 3,03 |
| 50 % | 22,20 V | 4447 rpm | 4,62 kgf | 2,77 |
| 20 % | 21,00 V | 4242 rpm | 4,20 kgf | 2,52 |
| 10 % | 20,40 V | 4138 rpm | 4,00 kgf | 2,40 |

## Detalhe visual realista (2026-10-19) — `lab/drone_rpi/detalhes/`

O aspeto 3D das peças vive num pacote à parte, um módulo por subsistema, chamado no FIM do `modelo._montar` (depois de
todas as peças com massa). Feito por 4 agentes em paralelo (um módulo cada), com fichas/desenhos oficiais citados no
docstring de cada módulo:

| módulo | o que desenha (medidas reais) | peças (ativo · articulado) |
|---|---|---|
| `eletronica` | **Raspberry Pi 5** (placa 85×56, furos 58×49, todas as portas no sítio do desenho mecânico: USB 3 azuis junto à RJ45 com LEDs, 2× micro-HDMI, 2× FPC CAM/DISP, PCIe, GPIO 40 pinos, botão) com o **Active Cooler** oficial (63,5×42,5×13,7, alhetas, ventoinha de 30 mm); ponte de carbono + **FC H743** (36×36, grommets, MCU, BMI088, barómetro); placa de potência 60×40 com o INA226 e o BEC 5 V; **4× T-Motor AIR 40A** (55,6×25,2×11,3, termo-retrátil); **Camera Module 3 Wide** com suporte; PMW3901 e VL53L1X por baixo; **pack 6S2P de 21700 Molicel P50B** com rótulo, XT90, borracha e 2 fitas; no articulado o regulador de 24 V dos servos (no Arduino: Portenta H7) | 192 · 203 |
| `motores` | **T-Motor MN4004** (Φ44,35×19, 18N24P) / **MN5006** (Φ55,6×30, 24N28P): base com janelas e 4 braços, núcleo e bobinas de cobre, sino com aresta polida e topo de 6 raios curvos (RODA com a hélice), veio, rolamento, 4 M3, adaptador, manga e 3 fases com balas de 3,5 mm; **hélice P15×5 de carbono** (forma real: colo fino, corda máxima a ~27 % do raio, ponta arredondada, corda média = a do catálogo, torção do passo — 7,8° a 75 % do raio contra 8,05° do catálogo, perfil fino com curvatura), CW/CCW espelhadas, grampo com 2 parafusos | 108 · 108 |
| `estrutura` | placa de baixo 208×208×3 de carbono (textura builtin), furo de cabos, ranhuras das fitas, aligeiramentos; placa de cima com janela; espaçadores Ø5 M3 com parafusos ISO 4762; tubos de carbono 25×23; abraçadeiras CNC, suportes dos motores, varões de travamento, pernas com pé de borracha — e o **MECANISMO**: no ombro, caixa de alumínio com janelas (sem-fim de aço m 0,8 a engrenar a roda de bronze de 20 dentes), 2 rolamentos 6800, servo XH430 deitado na placa, placa AS5048A no veio, cubo LARANJA com ponteiro sobre escala −40…+40°; no cotovelo, XH430 com horn e polia, garfo LARANJA estilo FR12-H101K, ponteiro sobre escala −45…+45°, mastro Ø16 com abraçadeiras. Cada peça no corpo que RODA (`drone` / `braco{k}` / `mastro{k}`); sem interpenetração em todo o curso das juntas (verificado de 5 em 5°) | 6 · 105 (malhas fundidas por material) |
| `fios` | fases 3×16 AWG laranja (cabos do ESC) com junções termo-retrácteis e balas fêmea nas balas dos motores, braçadeiras; ESC → placa de potência 14 AWG + par trançado de sinal; bateria 10 AWG do XT90 às ilhas + balanceamento 6S; USB-C 5 V ao RPi 5, UART Dupont ↔ JST-GH na FC, I2C ao INA226, sensores de baixo; **FPC da câmara** (16 → 11,5 mm) a entrar no conector CAM pelo lado da trava; no articulado o **barramento DYNAMIXEL** (X4P, JST EHR-04) do regulador aos ombros e de cada ombro ao cotovelo, e mangas que CRUZAM cada junta em segmentos por corpo (dobram no eixo) | 13 · 65 (tubos varridos, malhas fundidas) |

Regras (impostas pelo `Contexto.geom`): **massa 0, sem contacto, grupo 3** (o «fios e detalhes» do cockpit — a câmara
do detetor da bola só vê o grupo 0), nenhum corpo/junta/site/sensor/atuador novo. As caixas grosseiras com massa ficam
invisíveis (`esconder`: só a cor muda) quando um detalhe as representa — nenhuma peça do drone com massa aparece na
câmara do detetor (medido por segmentação da câmara `fpv`).

- `DRONE_DETALHES=nenhum` desliga (ou uma lista: `eletronica,fios`); por omissão todos. A física é a mesma com e sem.
- **Custo** (medido 2026-10-20, máquina livre): construir o modelo leva 0,37–0,52 s por env com a cache dos fios
  (`~/.cache/mujoco-lab/fios`, só do utilizador; a 1.ª montagem depois de mudar código recalcula: 2,0–3,3 s;
  `DRONE_DETALHES_CACHE=0` desliga) — os detalhes não entram na passagem do CM; render 1080p 425–435 fps (abs 893 geoms /
  635 mil faces; o cockpit precisa de 50). Para corridas sem render, `DRONE_DETALHES=nenhum`.
- **Cockpit**: com «fios e detalhes» desligado, a câmara volta a desenhar as caixas escondidas (`detalhes.acrescentar_escondidos`,
  na cena — o modelo não muda), para o drone não ficar sem motores nem eletrónica. Na **troca ao vivo** de motor/bateria
  (`trocar_pecas`) a caixa física muda de tamanho mas continua escondida; o sino do motor e o invólucro do pack mudam de
  COR, com o tamanho das peças do build (malhas não se redimensionam ao vivo).
- `modelo.exportar_xml` (`hardware.py xml`) exporta SEM o detalhe por omissão (~39 kB; com as malhas inline seriam 5–6 MB
  no git); `detalhes=True` exporta tudo.
- Prova e imagens: `MUJOCO_GL=egl .venv/bin/python -m lab.drone_rpi.detalhes.ver --so todos` — os 13 builds compilam,
  regras (massa, inércia e CM de TODOS os corpos iguais; MJCF exportável), o mesmo voo de 600 passos (pairar, arfar, tiro)
  com e sem detalhes nos dois builds principais (**idêntico bit a bit**) e as vistas (geral, centro, motor, braço,
  cotovelo, mira…).
- Estimado (sem número oficial): posições dos chips do RPi 5, base em L do cooler, círculo de furação da base dos
  motores, alturas internas, forma do horn do XH430 (só em .dwg), caixa do XT90, disposição do regulador.

### 2026-10-20 — «100 % realista» (fase 1) e a versão ACESSÍVEL (fase 2)

Pedido do dono: baterias fiéis, o Raspberry Pi 5 ligado à bateria por cabo, motores com a forma e o tamanho reais,
dobradiças verídicas, abraçadeiras presas, parafusos e porcas modelados, uma página com cada peça em 3D e a montagem;
depois o ombro real e fácil de fazer, as peças impressas em ABS, as massas realistas, os STL e os custos. O que mudou no
pacote `lab/drone_rpi/detalhes/`:

| ficheiro | o quê |
|---|---|
| `__init__.py` | o **REGISTO** por peça real (`registo_do_spec`: geoms e faixas de faces das malhas fundidas por peça × instância — o MuJoCo 3.15 preserva a ordem das faces —, ferragens, ligações dos cabos, eixos, variantes, notas), `ctx.peca(...)`, `ctx.ligacao(...)`, `ctx.eixo(...)` e as VARIANTES da troca ao vivo (os motores e packs reais do painel já no modelo, alfa 0 nas inativas — o `mjv_updateScene` não as desenha) |
| `ferragens.py` | parafusos ISO 4762/7380, porcas ISO 4032/10511, anilhas ISO 7089, anéis DIN 6799, pernos DIN 916, pilares, amortecedores e **insertos de latão** com a geometria das normas e a rosca ISO 68-1 helicoidal; comprimentos da série normal e binários de aperto; cada parafuso atravessa um furo real e a cabeça assenta |
| `bateria3d.py` | os packs célula a célula (21700/18650, fita de níquel, papel de peixe, balanceamento, XT90, termo-retráctil), com as variantes do painel; o XT90 de pé nos packs compridos |
| `eletronica.py` | RPi 5 + Active Cooler, FC H7 nos amortecedores, placa de energia com o BEC 5 V/5 A e o INA226, 4 ESC, câmara, sensores; no acessível os suportes IMPRESSOS (ponte do FC, suporte da câmara, bandeja dos sensores, bases dos bucks, berço do UBEC, suportes dos drivers) e a energia dos atuadores (2 × XL4016, 4 × DRV8871, UBEC Hobbywing 10A V2) |
| `motores.py` | cada T-Motor com a forma e as medidas da sua ficha (base, estator, bobinas, sino, veio, furação), as hélices com a planta e a torção reais; variantes do painel |
| `estrutura.py` | dobradiças com eixos = juntas do MuJoCo; no acessível o OMBRO DE FUSO (forquilha, cubo com alavanca, torre do pivô B, corpo do atuador com o JGB37-520, fuso Tr8×2 que gira, porca no carro), o cotovelo (berço, garfo, 608ZZ, M8), placas e colunas impressas, tubos 25×23 |
| `fios.py` | o Pi 5 alimentado pelo **cabo USB-C** do BEC da placa de energia (a cadeia bateria → XT90 → PDB → BEC → USB-C é auditada), 10/14/16 AWG, sinais, FPC da câmara num percurso medido, abraçadeiras PRESAS (folga ≤ 0,25 mm), mangas que cruzam as juntas; no acessível o cabo de cada servo do cotovelo e a energia dos atuadores |
| `auditoria.py` | `python -m lab.drone_rpi.detalhes.auditoria --build B`: F1–F4 (ferragens normalizadas, assentes, em furos, porcas com rosca de fora), C1 (cabos nas âncoras), C2 (cadeia de energia até ao computador de bordo: USB-C do Pi 5 ou ficha 5 V do Portenta H7), A1 (abraçadeiras presas), E1 (eixos = juntas), P1 (todos os geoms numa peça) — **14/14 builds `TUDO OK`** |
| `exportar.py` · `pecas.py` · `massas.py` · `impressao.py` · `precos.py` | a página `/pecas`: o JSON do MESMO modelo (corpos e juntas, malhas, ferragens, cabos, eixos, bielas), as fichas com o **porque** de cada peça e os passos de montagem, as **massas medidas** (`--atualizar-catalogo`), os **STL** das peças impressas (orientados na mesa, cópias iguais num só, conferidos fechados e a caber em 220 × 220 × 250 mm) e os **custos** de referência. A carga útil do topo não entra na página |

Prova: `ver.py --so todos` (14 builds, física idêntica bit a bit com e sem detalhes, 0 avisos), `auditoria` (14/14 builds TUDO OK), `teste_pecas3d.py` e
`teste_ombro_fuso.py`.

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
