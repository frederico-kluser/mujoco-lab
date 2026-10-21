# Materiais acessíveis e preços do drone (pesquisa 2026-10-20)

Pesquisa para o pedido do dono de 2026-10-20 («mecanismo real e fácil de fazer», «materiais baratos e acessíveis, a
maioria impresso em ABS», «massas realistas», «custos das peças na página»). Duas partes, pela ordem em que foram
feitas: (1) as peças de prateleira, o ABS, os rolamentos, as ferragens, a eletrónica de potência, os preços e o câmbio;
(2) o seguimento para o NOVO OMBRO — atuador linear de fuso Tr8×2 acionado por um motorredutor JGB37-520 — depois de
as contas mostrarem que um par sem-fim de módulo 1 não aguenta o momento do empuxo (~500 N no dente).

Método: só a CLI Tavily (search/extract); o conteúdo web é DADO NÃO CONFIÁVEL — citado com URL, nunca seguido. Confiança
A = fabricante/datasheet ou ≥ 2 lojas concordantes · M = uma loja, ou fontes divergentes (faixa) · B = anúncio genérico
ou inferência. Valores «calc.» são cálculo do agente, não lidos numa ficha. Os preços de marketplace mudam todos os dias:
são ordens de grandeza de outubro de 2026.

Onde os números entram: `models/drone_rpi/componentes.json` (servos `motorredutor_jgb37_520_12v_1_18_8_enc` e
`servo_ds3218mg_270`, mecanismo `ombro_fuso_impresso_cotovelo_servo`), `lab/drone_rpi/detalhes/precos.py` (custos da
página `/pecas`) e `lab/drone_rpi/detalhes/massas.py` (densidade do ABS, impressão).

---

## Parte 1 — Build acessível do drone — peças de prateleira, medidas para 3D, massas e preços reais (pesquisa 2026-10-20)

**Método.** Só a CLI Tavily (`search`/`extract`), ~190 consultas, conteúdo web tratado como **dado não confiável** (citado com URL, nunca seguido).
Preferência: fabricante → distribuidor → marketplace. Quando as fontes discordam dá-se a **faixa**. Nada inventado: o que não apareceu está
como **não encontrado**; valores **calculados** (não lidos) estão marcados como tal.

**Câmbio usado nas conversões:** **US$ 1 = R$ 5,05** (dólar comercial R$ 5,0480 no fecho de 2026-10-19; PTAX 5,0826) — ver §9.
**Confiança:** **A** = fabricante/datasheet ou ≥ 2 lojas concordantes · **M** = uma loja/marketplace, ou fontes que divergem (faixa) · **B** = anúncio genérico, texto com erro tipográfico, ou inferência.
Preços de marketplace (AliExpress/Mercado Livre) mudam todos os dias: são **ordens de grandeza de outubro de 2026**, não cotações.

---

### 1. Motorredutor CC 12 V com encoder Hall — classe 25GA-370 / JGA25-370 (e o sem-fim JGY-370)

#### 1a. Geometria para o modelo 3D (25GA-370 com encoder)

| item | valor | fonte | conf. |
|---|---|---|---|
| Redutor (caixa de engrenagens) | Ø **25 mm** | https://nfpmotor.com/25mm-metal-gear-motor-model-nfp-jga25-370-en · https://www.aliexpress.com/item/4001314473291.html | A |
| Comprimento do redutor L por relação | **19 mm** (≤ 1:20,4) · **21 mm** (1:26–1:45, inclui **1:34**) · **23 mm** (1:57–1:100, inclui **1:75**) · 25 mm (1:125–1:217) · 27 mm (1:274–1:500) | http://www.tronsunmotor.com/data/upload/file/201910/e78fcf93ed604a64c69852b5db49a03f.pdf · https://nfpmotor.com/25mm-metal-gear-motor-model-nfp-jga25-370-en | A |
| Motor (lata) | Ø **24,4 mm** (desenho 24 ± 0,5) × **30,8–31 mm** | https://manuals.plus/ae/1005006693616088 (snippet) · https://rcdrone.top/products/jga25-370-dc-gear-motor-with-encoder (snippet) | A |
| Encoder (tampa traseira) | **+8,7 mm** atrás do motor; corpo total sem veio ≈ **L + 40 mm** (1:34 ≈ 61 mm; 1:75 ≈ 63 mm — soma calculada) | rcdrone (snippet) · https://www.amazon.com/JGA25-370-Encoder-Torque-Electric-280rpm/dp/B0DJXL1B9Q ("Motor size 25*(L+40) mm") | M |
| Veio de saída | Ø **4 mm em D**, ressalto útil **9,5–9,8 mm** (≈ 12 mm total com o colar) | https://www.aliexpress.com/item/4001314473291.html · https://www.aslongdcmotor.com/news/high-performance-characteristics-of-jga25-370b-12v-dc-reduction-motor-197141.html · nfpmotor (12 mm) | A |
| Furos da face frontal | **2 × M3**, **17 mm** entre centros, 4,5 mm de profundidade | https://manuals.plus/ae/1005006693616088 (snippet; extração falhou) | M |
| Encoder | Hall AB bifásico, **11 PPR** no motor (22 polos), 3,3–5 V, conector PH2.0 6 vias; cabo ~142 mm | nfpmotor · https://www.amazon.com/25-370-Encoder-Measuring-Strong-Moment/dp/B0DN5GFBZK | A |
| Massa | **90–110 g** (99 g Seeed 1:34; 95 g Tronsun; ~110 g NFP) | https://people.ece.ubc.ca/~eng-services/files/courses/elec391-data_sheets/MOT4-info.pdf · tronsun PDF · nfpmotor | A |

#### 1b. Desempenho a 12 V por relação (a velocidade depende do enrolamento do motor: há várias versões "12 V" no mercado)

| relação | rpm em vazio | torque nominal (kg·cm) | torque de bloqueio (kg·cm) | corrente nominal / bloqueio | fonte | conf. |
|---|---|---|---|---|---|---|
| **1:34** | **126–250** (Seeed 126 rpm/46 mA; NFP 175; OpenImpulse 250) | 1,3 @ 130 rpm (NFP) | **3,8–4,5** (OpenImpulse 3,8; Seeed 4,2; NFP 4,5) | ≤ 0,18 A / **1–1,2 A** | UBC/Seeed PDF acima · https://nfpmotor.com/6v-12v-24v-dc-gearmotor-model-nfp-25-370 · https://www.openimpulse.com/blog/jga25-370-gearmotor-selector | M (faixa) |
| **1:50** | **não encontrado** (1:50 não é relação de catálogo da 370). Vizinhas: 1:45 = 130–188 rpm; 1:46,8 = 130 rpm | 1:45: 1,8 @ 100 rpm | 1:45: 5–6; 1:46,8: 4,4 | ≤ 0,18 A / 1–1,8 A | nfpmotor · openimpulse · https://www.ram-e-shop.com/shop/dc-jga25-370-enc-12v130r-25ga370-dc-geared-motor-with-encoder-12vdc-130-rpm-9331 | M |
| **1:75** (1:78) | **80–108** (NFP 80; OpenImpulse 1:78 = 108) | 3,0 @ 60 rpm (NFP) | **8,4–9** | ≤ 0,18 A / 1–1,2 A | nfpmotor · openimpulse | M |
| limite do redutor (Tronsun) | — | 21 mm: 2,0 nominal · 23 mm: 2,5 nominal | máx. instantâneo 6,0 (21 mm) · 7,0 (23 mm) | — | tronsun PDF | A |

| preço | valor | fonte | conf. |
|---|---|---|---|
| AliExpress (com encoder) | **US$ 6,83–12,01** (sem encoder desde US$ 4,55) | https://www.aliexpress.com/item/1005002598362488.html · https://www.aliexpress.com/item/1005001279982165.html · https://www.aliexpress.com/w/wholesale-jga25-370-12v.html | M |
| Brasil (Mercado Livre) | **R$ 55–131** (R$ 57,26 internacional; R$ 96 nacional; R$ 130,71) | https://www.mercadolivre.com.br/mys-motoredutor-12vdc-jga25-370-60-350rpm-encoder-/p/MLB2082386720 · https://www.mercadolivre.com.br/25-370-encoder-motor-12v-dc-140rpm/p/MLB2050915061 | M |

#### 1c. Alternativa autobloqueante: JGY-370 (sem-fim) 12 V

| item | valor | fonte | conf. |
|---|---|---|---|
| Redutor | **46 × 32 × 25 mm** (C × L × A); conjunto total **76,8 × 32 × 25 mm**; motor Ø24,4 × 30,8 mm; altura total 40,8 mm | https://www.linkedin.com/pulse/jgy-370-dc-worm-gear-motor-introduction-application-eric-wang-wrmpc · https://kitsguru.com/products/jgy370-dc-12v-90rpm-2kg-cm-metal-worm-gear-motor-pwm-forward-reverse | A |
| Veio | Ø **6 mm em D**, 14–15,6 mm (11,5 mm de corte em D); rosca central M3 × 10 | kitsguru · https://probots.co.in/jgy-370-12v-2-rpm-high-torque-self-locking-worm-gear-reduction-motor.html | A |
| Fixação | **4 × M3** na face, **33 × 18 mm** entre furos | kitsguru | M |
| Massa | **150–165 g** | kitsguru (150) · https://www.robotshop.com/products/aslong-motor-jgy370-12v-40rpm-high-torque-worm-gear-motor (162) · https://media.digikey.com/pdf/data%20sheets/seeed%20technology/108990007_web.pdf (165) | A |
| Torque (12 V) | depende da relação: 160 rpm (1:37,3) → 0,55 nominal / 2,2 bloqueio @ 1 A; 90 rpm → 2; 3 rpm → 12–25 kg·cm; anúncios até 24–35 kg·cm (limite do redutor); **autobloqueante** | Seeed PDF · kitsguru · https://www.amazon.com/Bringsmart-JGY-370-Turbine-Electric-Self-locking/dp/B07222K9ZC · https://www.aliexpress.com/item/1005002572123479.html | M |
| Preço | **US$ 8,59** (RobotShop, com tarifas EUA); AliExpress ≈ R$ 22,33 (~US$ 4,4); Brasil **R$ 88,50–137,99** (Saravati, ML) | https://www.robotshop.com/products/aslong-motor-jgy370-12v-30rpm-high-torque-worm-gear-motor · https://pt.aliexpress.com/item/4001339582443.html · https://www.saravati.com.br/motor-reversivel-de-alto-torque-jgy370-12v-100rpm.html · https://lista.mercadolivre.com.br/motor-dc-rosca-sem-fim | M |

---

### 2. Servos hobby de engrenagem metálica

| item | DS3218MG (20 kg) | MG996R | DS3235 (35 kg) | JX CLS6336HV (36 kg) |
|---|---|---|---|---|
| Corpo C × L × A | **40 × 20 × 40,5 mm** (A) | **40,7 × 19,7 × 42,9 mm** (A) | 40 × 20 × **38,5–40,5** mm (M; datasheet 38,5, lojas 40,5) | **40,5 × 20,5 × 40 mm** (A) |
| Orelhas | total **54,5 mm**, **49,5 mm** entre furos (B — fonte escreve "545 mm") ; Ø do furo e espessura: não encontrado | não encontrado | não encontrado | não encontrado |
| Estriado | **25T** (Ø 5,9 mm) (A) | **25T** (A) | 25T (M) | não encontrado |
| Horn incluído | braço 25T metálico (anúncios ML); disco 25T de alumínio **Ø20 × 5 mm, 4 g** vende-se à parte (M) | cruzeta plástica 4 braços (M) | não encontrado | não encontrado |
| Torque de bloqueio | **19 kg·cm @ 5 V · 21,5 @ 6,8 V** (A) | **9,4 @ 4,8 V · 11 @ 6 V** (A) | **23 @ 5 V · 30 @ 7,4 V · 35 @ 8,4 V** (A) | **27,8 @ 6,6 V · 35,6 @ 7,4 V** (A) |
| Velocidade (s/60°) | **0,16 @ 5 V · 0,14 @ 6,8 V** (A) | 0,17–0,19 @ 4,8 V · 0,14–0,15 @ 6 V (A) | 0,18 @ 5 V · 0,13 @ 7,4 V · 0,11 @ 8,4 V (A) | 0,14 @ 6,6 V · 0,11 @ 7,4 V (A) |
| Corrente de bloqueio | 1,8–2,6 A (M) | 1,4–2,5 A (A) | 2,2 / 2,9 / 3,2 A (5 / 7,4 / 8,4 V) (A) | não encontrado |
| Tensão | 4,8–6,8 V | 4,8–6,6 (7,2) V | 5–7,4 V (8,4 V na tabela) | 6,0–7,4 V (HV) |
| Massa | **60 g** (58 ± 2) (A) | **55 g** (A) | **60 g** (A) | **63 g** (A) |
| Ângulo | **180° ou 270°** (PWM 500–2500 µs) (A) | 180° (há 360° contínuo) | 180° / 270° (A) | 180° |
| Preço USD | **US$ 13,8–16,6** AliExpress; 17,99–22,99 lojas EUA (A) | US$ 2,52 (ElectroPeak, volume) – € 11,49 (Kiwi) (M; muitos clones) | **US$ 17,11** AliExpress; ~US$ 32 Amazon (M) | **US$ 28,54** AliExpress – 33,01 Banggood – 36,05 QWinOut (A) |
| Preço Brasil | **R$ 40–126** (ML: R$ 40,46 internacional; R$ 120,82; 3 por R$ 376) (M) | **R$ 24–42** (ML) (A) | **R$ 118–180** (ML) (M) | não encontrado |

Fontes (servos): https://speedyfpv.com/products/ds3218mg-digital-servo-high-speed-high-torque-metal-gear-waterproof-20kg-torque-180-degrees-w-accessories ·
https://www.aliexpress.com/item/1005008618479316.html · https://images-na.ssl-images-amazon.com/images/I/81Lbgu+nG6L.pdf (Miuzei DS3218, relação 275) ·
https://rcdrone.top/products/dsservo-ds3218-digital-servo (54,5/49,5 com erro) · https://servodatabase.com/servo/dsservo/ds3218-mg ·
https://ampere-electronics.com/product/25t-aluminum-servo-motor-disc-horn · https://www.aliexpress.com/item/1005003444099992.html ·
https://itgresa.com/product/ds-servo-pro-20kg-combat-robot-servo · https://rcprinter.com/products/20kg-digital-servo-ds3218-with-metal-gears-and-metal-servo-arm ·
https://produto.mercadolivre.com.br/MLB-5080148072-servo-motor-miuzei-ds3218-de-alto-torque-20-kg-prova-dagu-_JM · https://www.mercadolivre.com.br/um-servo-digital-rc-de-180-graus-ds3218-20-kg-torque/p/MLB2110165175 ·
https://servodatabase.com/servo/towerpro/mg996r · https://www.electronicoscaldas.com/datasheet/MG996R_Tower-Pro.pdf · https://www.tinkered.ai/components/servo-mg996r-cross ·
https://www.kiwi-electronics.com/en/mg996r-180-digital-metal-gear-servo-11kg-cm-55g-3020 · https://lista.mercadolivre.com.br/servo-motor-mg996r ·
https://servodatabase.com/servo/dsservo/ds3235-sg · https://hajim.rochester.edu/me/sites/kelley/me240/DS3235-270_datasheet.pdf · https://aifitlab.com/products/dsservo-ds3235-sg-servo-motor ·
https://www.aliexpress.com/w/wholesale-ds3235-servo-35kg.html · https://www.mercadolivre.com.br/ds3235-35kg-metal-high-torsion-digital-steering-servo-for/p/MLB2049640530 ·
https://servodatabase.com/servo/jx-servo/cls6336hv · https://rcdrone.top/products/jx-servo-cls6336hv-cls6322hv-35kg-21kg-torque-high-voltage-high-precision-metal-coreless-digital-servo-for-rc-helicopter-car ·
https://www.aliexpress.com/item/4001355900312.html · https://usa-m.banggood.com/JX-Ecoboost-CLS6336HV-36KG-Large-Torque-180-CNC-DigitalCoreless-Servo-for-RC-Models-p-1314550.html
Nota: o DS3218 **PRO** dá 21 / 23,5 kg·cm e 0,12 / 0,10 s/60° (5 / 6,8 V) (https://aifitlab.com/products/dsservo-ds3218-pro-servo-motor). MG996R barato é quase sempre clone.

---

### 3. Par sem-fim + coroa módulo 1 (m1), 1 entrada, 1:20…1:40 — e m0,8

#### 3a. Referência dimensional de catálogo (KHK, m1, 1 entrada, ângulo de hélice 3°35′) — usar para o modelo 3D

| peça | dentes | Ø primitivo | Ø externo | largura | cubo | furo | comprimento total | material | preço | fonte | conf. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sem-fim **SW1-R1** | 1 entrada | **16 mm** | **18 mm** | rosca **20 mm** | — | **6 mm** (parafuso M4, a 5 mm da ponta) | **32 mm** | aço S45C | **US$ 23,25** (Zoro) | https://catalog.khkgears.us/item/worm-gears/steel-worms-sw/sw1-r1 · https://www.zoro.com/khk-usa-ground-and-machined-steel-worms-sw1-r1/i/G304671507 | A |
| Coroa **BG1-20R1** (1:20) | 20 | **20,05 mm** | garganta 22 · externo **23 mm** | **10 mm** | Ø16 × 10 mm | **6 mm H7** (M5) | 20 mm | bronze CAC502 | **US$ 46,76** (Grainger) | https://catalog.khkgears.us/item/worm-gears/bronze-worm-wheels-bg/bg1-20r1 · https://www.grainger.com/product/KHK-GEARS-Worm-Wheel-Reduction-Ratio-793AU3 | A |
| Coroa **BG1-30R1** (1:30) | 30 | 30,07 | 32 · **33** | 10 | Ø20 | 6 | — | bronze | não encontrado | https://catalog.khkgears.us/item/worm-gears/bronze-worm-wheels-bg/bg1-30r1 · https://logosfoundation.org/instrum_gwr/synchrochord/datasheets/Worm_Wheels_Section%25209.pdf | A |
| Coroa **BG1-40R1** (1:40) | 40 | 40,08 | 42 · **43** | 10 | Ø26 | 8 | — | bronze | não encontrado | idem (tabela da secção 9 KHK) | A |

Distância entre eixos (calculada = (16 + Ø primitivo da coroa)/2): **18,0 mm** (1:20, confere com o "mounting distance 18 mm" da KHK), 23,0 mm (1:30), 28,0 mm (1:40).
Autobloqueio: tan 3°35′ ≈ 0,063 — com bronze bem lubrificado (μ da mesma ordem) o autobloqueio **não é garantido**; o anúncio genérico afirma "self-locking" (cálculo; confirmar em bancada).

#### 3b. Kits baratos (AliExpress / Amazon / eBay)

| item | valor | fonte | conf. |
|---|---|---|---|
| "1 Set 1M Worm Gear with Rod", aço 45#, 1:15…1:100 | **US$ 10,07** (AliExpress); US$ 17,20 (Helpshift); AU$ 18,69 (variante); furo "de processo" 6–10 mm (varia por lote), sem têmpera nem furos de parafuso | https://www.aliexpress.com/item/1005005117237912.html · https://www.helpshift.com/products/industrial-helical-gear-1-set-1m-worm-gear-with-rod-reductio/250314590 · https://www.amazon.com/Worm-Gear-Rod-Reduction-Ratio/dp/B0H59XY9HJ · https://www.aliexpress.com/i/1005012927549076.html | M |
| Kits m1 uxcell/genéricos (Amazon) | **US$ 7,81–23,99** | https://www.amazon.com/worm-gear-sets-Industrial-Scientific/s?k=worm+gear+sets&rh=n%3A16310091 | B |
| Medidas do sem-fim/coroa destes kits | **não encontrado** ("ver variante"); usar a geometria KHK (Ø primitivo da coroa = m·z) | — | — |
| **m0,8** (latão + sem-fim inox, 20–60 dentes, furos 5–12 mm) | **US$ 11,41 por peça** (HomeDIYer); MISUMI m0,8/1,0 € 6,58 | https://homediyer.com/products/0-8-module-worm-gear-set-brass-worm-wheel-stainless-worm-rod · https://uk.misumi-ec.com/vona2/detail/110302194530 | M |
| m0,8 1:20 uxcell (latão) | coroa 20T: **Ø ext. 17,6 mm**, espessura 8 mm, altura total 16 mm, furo 4 mm | https://vxb.com/products/brass-worm-gear-set-with-20-teeth-and-08-module-fo | M |
| Brasil, m1 | **não encontrado** (ML só tem m0,5 em latão e m1,5) | https://produto.mercadolivre.com.br/MLB-5112775413-engrenagem-sem-fim-30-dentes-lato-05-modulo-eixo-32mm-_JM | — |

---

### 4. Rolamentos, veio Ø8 h6 e colar

| item | valor | fonte | conf. |
|---|---|---|---|
| **608ZZ** 8 × 22 × 7 | massa **12–13,6 g** (SKF 13 g); 7 esferas Ø3,969; C = 3,3 kN, C0 = 1,37 kN | https://www.123bearing.com/bearing-housing/deep-groove-bearing/single-row/608-zz-skf · https://www.kugellager-express.de/miniature-deep-groove-ball-bearing-608-ZZ-8x22x7-mm · https://www.bcprecision.com/products/608zz-8x22x7-shielded-greased-miniature-ball-bearings | A |
| 608ZZ preço (pacote de 10) | **US$ 5,57–6,25** AliExpress; US$ 7,14–8,88 eBay/Walmart/VXB → **~US$ 0,6–0,9/un** | https://www.aliexpress.us/w/wholesale-608zz-bearing.html · https://www.walmart.com/c/kp/608z-bearing · https://vxb.com/products/10-pack-608zz-ball-bearings-8x22x7mm | A |
| 608ZZ Brasil (10 un) | **R$ 16,14–57,00** (Casa dos Roletes 16,14; ML 20,71; Magalu 31,13; San Expedito 57) | https://www.casadosroletes.store/produtos/608-zz-kit-com-10-rolamentos-rigido-de-esfera-1jxwd · https://lista.mercadolivre.com.br/kit-rolamentos-608zz · https://www.magazineluiza.com.br/busca/kit+10+rolamentos+608zz | A |
| **688ZZ** 8 × 16 × 5 | massa **3,8–4,05 g** | https://www.tradebearings.com/688zz-bearing-8x16x5mm-product-28497.html · https://iskbearing.com/product-details/688zz · https://www.123bearing.com/bearing-housing/deep-groove-bearing/single-row/688-zz-inox | A |
| 688ZZ preço | US$ 0,16/un (Bulkman3D) – US$ 1,15/un (Lily, 20 por US$ 23); 10 un ≈ **US$ 2–12** | https://bulkman3d.com/product/688zz-ball-bearing · https://www.lily-bearing.com/products/688zz · https://handsontec.com/index.php/product/688zz-metal-shield-ball-bearings | M |
| 688ZZ Brasil | "10/40 peças" **R$ 140,33** (tamanho do pacote ambíguo); marcas NSK/EZO/DMR à unidade sem preço visível | https://lista.mercadolivre.com.br/8x16x5 | B |
| **Veio Ø8 mm** cromado/temperado | AliExpress 8 × 500 mm **US$ 3,6–9,3** (anúncio até 21,82) → **~US$ 7–19/m**; Walmart conjunto 2 × 500 mm US$ 31,44. Atenção: muitos são **h8**, não h6 | https://www.aliexpress.com/w/wholesale-8-500mm-linear-shaft.html · https://www.aliexpress.com/w/wholesale-linear-shaft-8mm-300.html · https://www.walmart.com/ip/8mm-x-500mm-Linear-Motion-Rod-Shaft-Set-Linear-Guide-Rails-for-3D-Printer/19388759173 · https://www.walmart.com/ip/Linear-Motion-Rods-8mm-x-500mm-Case-Hardened-Chrome-Plated-Linear-Motion-Rod-Shaft-or-3D-Printer-DIY-CNC-Metric-h8-Tolerance/2663477516 | M |
| Veio Ø8 Brasil | **R$ 105,85 / 600 mm** (≈ R$ 176/m, Datacombr); kit 7 peças R$ 220–232 (Eletrodex); Kalatec "eixo retificado aço cromo 8 mm, 45 HRC" (sem preço) | https://datacombr.com.br/index.php?route=product%2Fproduct&product_id=278 · https://www.eletrodex.net/cncimpressora-3d/impressora-3d/kits/kit-7-pecas-eixo-linear-8mm-em-aco-cromado-p-impressora-3d · https://www.kalatec.com.br/eixo-retificado-8mm | M |
| **Colar Ø8** com parafuso | aço zincado, **Ø ext. 16 mm × 8 mm de largura, parafuso M4**, **~8,5 g** (0,3 oz); variante 14 × 7 mm | https://summitcollars.com/product/cz-8mm-8mm-id-metric-set-screw-shaft-collar-zinc-plated · https://www.huyett.com/scm-008-ss · https://www.innerscene.com/tools/library/3d-parts/8-mm-set-screw-shaft-collar-52204035 (STEP CC0) | A |
| Colar preço | **US$ 10,26 / 10 un** (Walmart, 14 mm OD); Brasil **R$ 39,99 / 10 un** inox (ML "anel trava eixo 8 mm") | https://www.walmart.com/ip/10-Packs-Set-Screw-Collars-8mm-Bore-Shaft-Collars-14mm-OD-7mm-Width-Gear-Stopper-Wheel-Collar/5227789644 · https://www.mercadolivre.com.br/anel-trava-eixo-bitola-8mm-em-inox-pacote-de--10-pecas-/up/MLBU597496201 | M |

---

### 5. Insertos térmicos M3, parafusos M3 DIN 912 e porcas autotravantes

| item | valor | fonte | conf. |
|---|---|---|---|
| Inserto M3 "standard" (CNC Kitchen/Ruthex) | **M3 × 5,7 mm**, **Ø ext. 4,6 mm**, furo recomendado **4,0 mm** (latão sem chumbo, serrilhado duplo) | https://cnckitchenus.store/products/heat-set-insert-m3-x-5-7-100-pieces · https://www.aliexpress.com/item/1005004185759697.html ("M3×5,7×4,6") · https://partsbuilt.com/m3-heat-set-thread-insert-5mm-long-4-pack (OD 4,6 → furo 4,0) | A |
| Variantes curtas | M3 × 3,0 (CNC Kitchen "short"); M3 × 4 × OD 4,2 (AndyMark, furo 4 mm); M3 × 4 × 5 genérico | https://vector3d.shop/products/heat-set-insert-m3-short · https://andymark.com/products/m3-heat-set-threaded-insert | A |
| Preço / 100 (originais) | **US$ 10,90** CNC Kitchen USA; US$ 10,99 Prusa; € 9,29 Ruthex (3DJake) | https://www.prusa3d.com/product/heat-set-inserts-m3-standard-100-pcs · https://www.3djake.pt/ruthex/inserto-roscado-m3-100-unidades | A |
| Preço / 100 (genéricos) | ~US$ 7/100 "de qualidade razoável" (relato); AliExpress sem preço legível | https://www.reddit.com/r/3Dprinting/comments/trmo91/is_anything_better_than_heat_staking_a_threaded | B |
| Brasil / 100 | **R$ 42,68–89** (ML); R$ 112 (outro anúncio); kit 150 un M3 × 5,7 × 4,6 | https://produto.mercadolivre.com.br/MLB-4722656701-kit-150-insertos-roscados-lato-m2-m3-m4-para-impresso-3d-_JM · https://www.mercadolivre.com.br/kit-150-insertos-rosca-m3-para-impressao-3d-metalicos/up/MLBU5389980895 | M |
| Parafuso M3 DIN 912 / ISO 4762 (100 un) | **US$ 5** (classe 12.9, pneucons) – **US$ 17** (inox A2 a US$ 0,17/un, accu) | https://pneucons.com/m3-socket-head-cap-screws-din-912-grade-12-9-pack-of-100pcs · https://accu-components.com/us/metric-cap-head-screws/3817-SSCF-M3-6-A2 | M |
| Parafuso M3 Brasil (100 un) | **R$ 36,97** (M3 × 10 inox A2, Projette) · R$ 42,18 (M3 × 8, 12.9 preto) · R$ 48 (M3 × 30 inox) | https://projetteparafusos.com.br/parafuso-sextavado-interno-cabeca-cilindrica-din-912-m3-x-10-inox-a2 · https://www.mercadolivre.com.br/parafuso-allen-m3-x-16-cilindrica-din-912-50-pecas/up/MLBU2445368422 · https://www.mercadolivre.com.br/100-parafuso-allen-cilindrica-inox-a2-m3-x-30-din912/p/MLB2107283559 | A |
| Porca M3 autotravante (nyloc, DIN 985) 100 un | **US$ 6,39** (zincada, Parts Express) – US$ 18 (inox oxidado preto) | https://www.parts-express.com/M3-Nylock-Locknut-with-Nylon-Insert-Zinc-100-Pcs.-081-3205 · https://www.fastener-express.com/m3-nylon-insert-lock-nuts-stainless-black-oxide-Qty.-100.aspx | A |
| Porca M3 Brasil | **R$ 35,79 / 100** (Parlock inox 304) | https://produto.mercadolivre.com.br/MLB-5220613263-porca-auto-travante-parlock-m12-175-ma-100-pecas-_JM | M |

---

### 6. Filamento ABS (o plástico do LEGO) — propriedades, preço e impressão

| item | valor | fonte | conf. |
|---|---|---|---|
| Densidade | **1,04–1,05 g/cm³** (eSUN ABS 1,04; Polymaker PolyLite 1,04; Bambu 1,05; MG 1,05; eSUN ABS+ 1,04–1,06) | https://www.spoolscout.com/data-sheets/esun/abs-abs · https://shop.polymaker.com/products/polylite-abs · https://stemfinity.com/products/bambu-lab-abs · https://www.esun3d.com/abs-pro-product | A |
| Módulo de tração (impresso) | **2,25 GPa (XY) / 2,08 GPa (Z)** (PolyLite ABS, ISO 527); módulo de flexão eSUN ABS+ 1,87 (XY) / 1,51 GPa (Z); Bambu ABS flexão 1,88 GPa; ABS injetado 1,79–3,2 GPa | https://polymaker.com/wp-content/uploads/lana-downloads/TDS_Polymaker_PolyLite-ABS_V5.6_2025-12-30_EN.pdf · https://www.matterhackers.com/store/l/esun-abs-filament/sk/MX9UGRGL · https://shop3duniverse.com/products/bambu-lab-abs-1-75mm-1kg · https://juggerbot3d.com/3d-printing-material-capabilities/abs-filament-review | A |
| Resistência à tração | **33–43 MPa em XY** (PolyLite 33,4; Bambu 33 ± 3; Sunlu 35 ± 5; eSUN ABS+ 40,1; eSUN ABS 43); **entre camadas (Z): 14,9 MPa (eSUN ABS+) a 29,7 MPa (PolyLite)** → dimensionar pela direção Z | idem + https://www.sunlu.com/products/abs-3d-printing-filament | A |
| Preço USD/kg | **US$ 12–23**: eSUN ABS+ US$ 15,99 promo / 22,99 cheio (3+ = 13,60; 10+ = 12,00); Newegg 19,99; Sunlu ABS desde **US$ 10,69**; MatterHackers Build 19,99 | https://www.esun3d.com/abs-pro-product · https://esun3dstore.com/products/abs-pro · https://store.sunlu.com/collections/3d-printer-filament · https://www.newegg.com/p/2AR-00AT-00093 | A |
| Preço Brasil/kg | **Voolt3D R$ 96,51–105,16** (R$ 99,90 no Pix); **3D Fila ABS Premium R$ 104,93–129,90** (ML/Shopee; Magalu R$ 173,69 é fora da curva) | https://www.mercadolivre.com.br/voolt3d-filamento-abs-1kg-cor-natural/p/MLB36032132 · https://voolt3d.com.br/abs · https://produto.mercadolivre.com.br/MLB-3337188423-filamento-3dfila-abs-premium-1kg-175mm-varias-cores-_JM · https://shopee.com.br/Filamento-Abs-Premium-3dfila-Impress%C3%A3o-3d-1-75mm-1kg-i.404282089.13880869482 | A |
| Parâmetros para peças estruturais | **4 perímetros + 40 % de enchimento** (padrão das peças Voron em ABS); ABS rígido: 30–50 % de enchimento; as paredes são o caminho de carga ("2 perímetros a mais valem mais que +10 % de enchimento"); 4 perímetros de 0,45 mm ≈ 1,8 mm; teto prático 4 perímetros / 50 %; bico 230–270 °C, mesa 95–110 °C, ventoinha 0 %, câmara fechada | https://forum.prusa3d.com/forum/original-prusa-i3-mk3s-mk3-how-do-i-print-this-printing-help/settings-for-functional-strength · https://ultimaker.com/learn/3d-printing-infill-density-optimizing-strength-and-speed · https://www.youtube.com/watch?v=AmEaNAwFSfI · https://thevirtualfoundry.com/3d-printing-shells-and-infill | A |
| Vazão máxima (bico 0,4) | ABS **11 mm³/s** em hotend classe V6 (PLA 15); predefinição Bambu ABS **16 mm³/s**; P1S anuncia 32 mm³/s em ensaio de parede simples | https://grandpacad.com/en/tools/volumetric-flow-calculator · https://bambureviews.com/posts/bambu-filament-settings-guide · https://www.3dmag.com/3d-printers-comparison/prusa-vs-bambu-lab-mk4s-vs-p1s | A |
| **Débito real médio** | CoreXY rápida (X1C/P1S) **28–35 g/h**; "bedslinger" moderna (A1/MK4) **18–25 g/h**; Ender 3 de origem **8–12 g/h** → em ABS (1,04 g/cm³) **≈ 27–34 / 17–24 / 8–12 cm³/h** (conversão calculada) | https://filamentcalcs.com/guides/3d-print-time-expectations | M |

---

### 7. Eletrónica de potência, drivers e encoder magnético

| item | dimensões | massa | desempenho | preço USD | preço Brasil | fonte | conf. |
|---|---|---|---|---|---|---|---|
| **XL4016** buck 8 A | **61 × 41 × 27 mm** (com voltímetro 64 × 47 × 26) | ~48–50 g (com embalagem) | 4–40 V → 1,25–36 V, 8 A máx., 180 kHz | **não encontrado** em USD (₹ 329 Índia; ৳ 350–430 Bangladesh; EGP 190 Egito) | **≈ R$ 48/un** (10 por R$ 483, ML) | https://www.rytronics.in/product/xl4016-8a-200w-dc-dc-step-down-buck-converter · https://www.handsontec.com/dataspecs/power%20supply/8A%20XL4016E1%20DC-DC.pdf · https://www.mercadolivre.com.br/10-x-modulo-conversor-tensao-dc-dc-step-down-8a-xl4016-c-di/p/MLB2072890439 | M |
| Hobbywing **UBEC 8A (2–3S)** | 42 × 39 × 9 mm | 36–38 g | **entrada só 6–12,6 V (não serve em 6S)**; 5/6 V, 8 A / 15 A | US$ 18,49 (descontinuado na RMRC) | **R$ 229,90** (ML) | https://www.hobbywing.com/en/products/ubec-8a-2-3s100 · https://superstitionhobbies.com/products/hobbyiwng-ubec-8a · https://www.mercadolivre.com.br/hobbywing-8a-ubec-5v-6v-chave-liga-desliga-max-15a-aeromodel/p/MLB2106683619 | A |
| Hobbywing **UBEC-8A-6S** | 62 × 27,5 × 10 mm | 24,5 g | 2–6S (5,5–26 V) → **5,2 / 6,0 V @ 8 A**, 15 A 10 s (sem 7,4 V) | US$ 29,19 | não encontrado | https://valuehobby.com/hobbywing-8a-ubec-2s-6s.html · https://www.littohot.com/products/hobbywing-ubec-8a-6s-for-esc-electronic-speed-controller | M |
| **ZTW UBEC 8A G2** | **50 × 20 × 7 mm** | **14 g** | 2–8S (7–34 V) → **5 / 6 / 7,4 / 8,4 V**, 8 A / 15 A | **US$ 16,99–29,99** | não encontrado | https://www.altitudehobbies.com/products/ztw-8a-external-bec-2-8s-ubec · https://ztwesc.com/products/ztw-ubec-8a-g2-peak-15a-adjustable-output-voltage-5v-6v-7-4v-8-4v-external-bec · https://motionrc.com/products/ztw-ubec-8a-g2-peak-15a-adjustable-output-voltage-external-bec-ztw3040011 | A |
| **Holybro UBEC 12A** | 48 × 33,6 × 16,3 mm | 47,8 g | 3–14S → 6,0 / 7,2 / 8,0 / 9,2 V, **12 A** / 24 A | US$ 36,59–36,99 | não encontrado | https://holybro.com/products/ubec-12a · https://www.flyingtech.co.uk/product/holybro-12a-ubec-15026 | A |
| Castle **CC BEC 2.0** | não encontrado | 21–28 g | 2–14S → 4,75–12 V; 10 A @ 5–6 V, 9 A @ 7,25–8,5 V, 15 A pico | US$ 54,95–56,95 | não encontrado | https://www.offshoreelectrics.com/proddetail.php?prod=hh-cas-010-0153-00 · https://castlecreations.com/collections/voltage-regulators-becs | M |
| UBEC genérico "8A+4A 5,2/6,0/7,4 V" | — | — | — | — | R$ 151,84–157,66 (ML) | https://www.mercadolivre.com.br/hobbywing-ubec-5v6v-3a-de-2s-a-6s-p-drone-ou-aeromodelo/up/MLBU1756752373 | B |
| **Pololu D36V50F5** (5 V p/ RPi 5) | **25,4 × 25,4 × 9,5 mm** | **7 g** | 5,5–50 V → 5 V **5,5 A**, 80–95 % | **US$ 39,95** (RobotShop) – 43,40 (TME) | não encontrado | https://www.pololu.com/product/4091/specs · https://www.robotshop.com/products/5v-55a-step-down-voltage-regulator-d36v50f5 · https://www.tme.com/ca/en/details/pololu-4091/converter-modules/pololu/5v-5-5a-step-down-volt-reg-d36v50f5 | A |
| **Matek BEC12S-PRO** | **35 × 24 × 5,5 mm** | **5 g** | 9–55 V → 5,2 / 8 / 12 V, **5 A** / 9 A | **US$ 24,99** | não encontrado | https://rcdrone.top/products/matek-mateksys-bec12s-pro-9-55v-to-5v-8v-12v-5a · https://pyrodrone.com/products/matek-12s-pro-bec-12s-9-55v-input-5v-8v-12v-5a-output | A |
| Matek UBEC DUO | 58 × 36 × 8 mm | 32 g | 2–6S → saída 1: 5/6/7,2/12 V 4 A (6 A máx.); saída 2: 5 V 4 A | US$ 13,58 (promo AliExpress) – 22,37 | não encontrado | https://gadgetsdeal.in/shop/bec/matek-systems-ubec-duo-4a-512v-4a-5v-in-india · https://www.aliexpress.com/item/1005003596735617.html | M |
| Buck 12/24 → 5 V 5 A genérico (encapsulado) | 65 × 58 × 22 mm | não encontrado | entrada 12–24 V (6S cheio = 25,2 V: no limite) | US$ 3,90–8,04 | não encontrado | https://www.droking.com/DC-Step-Down-Voltage-Regulator-DC-12-24V-to-5V-5A-25W-Buck-Converter-Module-Waterproof-Car-Power-Supply · https://www.ebay.com/itm/405016226741 | M |
| **DRV8871** (Adafruit #3190) | **24,4 × 20,4 × 9,7 mm** | **2,2 g** | 6,5–45 V, **3,6 A pico**, 1 motor | **US$ 7,50** (6,75 a partir de 10) | R$ 57,53 (ML, pacote) – 111,84 | https://shop.pimoroni.com/en-us/products/adafruit-drv8871-dc-motor-driver-breakout-board-3-6a-max · https://www.adafruit.com/product/3190 · https://www.mercadolivre.com.br/drv8871-h-bridge-motor-driver-module-36a-pwm-driver-3pcs/p/MLB2088019012 | A |
| **TB6612FNG** (Pololu #713) | **15,2 × 20,3 mm** (0,6″ × 0,8″) | **1,5 g** | 4,5–13,5 V, 2 canais, ~1 A contínuo (3,2 A pico) | **US$ 4,95** (Digi-Key) | não encontrado | https://www.pololu.com/product/713/specs · https://www.digikey.com/en/products/detail/pololu/713/10450399 | A |
| **BTS7960** (IBT-2) 43 A | **50 × 50 × 43 mm** (46 × 46 × 38 noutra loja) | 54–66 g | 5,5–27 V, 43 A | US$ 1,91–10,80 | existe no ML, preço não legível | https://electropeak.com/bts7960-43a-high-power-motor-driver-module · https://handsontec.com/index.php/product/43a-high-power-bts7960-dc-motor-driver-module · https://www.tztstore.com/goods/show-5093.html | M |
| **AS5048A** placa adaptadora ams (AS5048A-TS_EK_AB) | não encontrado | não encontrado | 14 bit, SPI + PWM | **US$ 17,45–20,28** (Farnell 17,45; Mouser 18,09; DigiKey 19,40 descontinuado); RS £ 13,23 | não encontrado | https://www.mouser.com/ProductDetail/ams-OSRAM/AS5048A-TS_EK_AB?qs=Rt6VE0PE%2FOd5D%2Fkw9O7ofA%3D%3D · https://il.farnell.com/c/sensors-transducers/sensors/sensor-development-evaluation-kits?board-type=adapter-board&ic-module-used=as5048a · https://uk.rs-online.com/web/p/sensor-development-tools/2018309 | A |
| AS5048A módulo genérico (gimbal) | — | — | — | desde US$ 39,88 (AliExpress, provavelmente kit) | — | https://www.aliexpress.com/w/wholesale-as5048a-magnetic-encoder.html | B |

---

### 8. Preços das peças compradas do drone

| peça | preço USD (faixa) | preço Brasil | massa/medida útil | fonte | conf. |
|---|---|---|---|---|---|
| T-Motor **MN5006 KV450** | **US$ 84,99/un** (loja T-Motor, UnmannedRC, World Drone Market); € 73,93 (UE) | não encontrado | 106 g | https://store.tmotor.com/categorys/uav-mult-motor-antigravity-type · https://ozrobotics.com/shop/antigravity-drone-motor-for-extended-flight-time-t-motor-type-4-6s-mn5006-kv300-and-kv450 · https://www.worldronemarket.com/product/t-motor-mn5006 · https://www.uavmarketplace.in/products/t-motor-mn5006-450kv-antigravity-motor/895789000012592924 | A |
| T-Motor **MN4004 KV300** | **US$ 145,90 o par** (≈ 72,95/un, loja T-Motor e UnmannedRC); Ligpower US$ 62,9 (unidade ambígua) | não encontrado | — | https://store.tmotor.com/categorys/uav-mult-motor-antigravity-type · https://unmannedrc.com/products/mn4004-antigravity-type-4-6s-uav-motor-kv300-kv400-2pcs-set | A |
| T-Motor **P15×5** CF (par) | **US$ 55,90** (T-Motor); US$ 40 (Aerofly) | não encontrado | 21 ± 1,5 g por pá | https://shop.tmotor.com/collections/uav-propeller · https://www.ligpower.com/product/15x5-polish-carbon-fiber-propelller.html · https://www.aeroflyhobbies.com/propellers/42-t-motor-15x5-carbon-fiber-propeller.html | A |
| T-Motor **AIR 40A** ESC | **US$ 39,99** (37,99 a partir de 10) | não encontrado | 70 g | https://www.foxtechfpv.com/tmotor-air-40a-esc-p-1803.html · https://unmannedrc.com/products/air-40a-2-6s-multi-rotor-uav-drone-esc · https://irlock.com/collections/esc | A |
| **Raspberry Pi 5 4 GB** | **US$ 85 (preço oficial desde abril/2026, mantido em outubro/2026)**; retalho US$ 110 (CanaKit) | **R$ 780** (IdFlux, Anatel; de R$ 921) | — | https://www.tomshardware.com/raspberry-pi/component-shortages-drive-raspberry-pi-prices-up-by-up-to-23-percent-escalating-lpddr4-lpddr5-costs-trigger-the-third-price-hike-of-the-year · https://www.canakit.com/raspberry-pi-5-4gb.html · https://loja.idflux.com/produtos/raspberry-pi-5-4gb-model-b-anatel | A |
| RPi **Active Cooler** | **US$ 6–15** (Pimoroni 6 pré-venda; PiShop 10,95; CanaKit 11,95; Adafruit 13,50; SparkFun 15) | não encontrado | 63,5 × 42,5 × 13,7 mm (brief oficial); ~28 g (M) | https://www.pishop.us/product/raspberry-pi-active-cooler · https://shop.pimoroni.com/en-us/products/raspberry-pi-5-active-cooler · https://pip.raspberrypi.com/documents/RP-008188-DS-active-cooler-product-brief.pdf · https://www.robotics.org.za/W25939 | A |
| FC **H743 30×30** | Matek H743-MINI V3 **US$ 84,49–97,24**; H743-SLIM V3 116,49; Holybro Kakute H7 (v1.5) **US$ 55–62**; stack AeroSelfie H743 74,90 | não encontrado | — | https://www.lumenier.com/products/mateksys-h743-mini-v3-flight-controller · https://www.defiancerc.com/collections/flight-controller/brand_matek · https://www.racedayquads.com/products/matek-h743-slim-30x30-flight-controller · https://holybro.com/products/kakute-h7 | A |
| **Pi Camera Module 3 Wide** | **US$ 35** (preço de lançamento, 2023) – 45,05 (retalho: CanaKit 37,95; Adafruit 38,50; Cytron 39,88; SparkFun 45,05) | não encontrado | — | https://www.cnx-software.com/2023/01/23/raspberry-pi-camera-module-3-review-hdr-autofocus-wide-angle-and-noir-camera · https://www.canakit.com/raspberry-pi-camera-module-3.html · https://www.adafruit.com/product/5658 | A |
| **PMW3901** | Pimoroni PIM453 £ 20,70 (Pi Hut) / US$ 32,05 (Xonelec); Holybro (UART) **US$ 20,59**; Tindie 35,95–49,95 | **R$ 54,38** (módulo CJMCU-3901, ML) | — | https://thepihut.com/products/pmw3901-optical-flow-sensor-breakout · https://holybro.com/products/pmw3901-optical-flow-sensor · https://produto.mercadolivre.com.br/MLB-5060650115-modulo-de-sensor-de-fluxo-optico-pmw3901-translaco-xy-de-_JM | M |
| **VL53L1X** Pololu #3415 | **US$ 19,95** (Pololu); 24,04 (TME) | não encontrado (ML tem genéricos sem preço legível) | 12,7 × 17,8 mm (0,5″ × 0,7″; coluna da tabela comparativa da Pololu, B) | https://www.pololu.com/product/3415 · https://www.tme.eu/en/details/pololu-3415/distance-sensors/pololu/vl53l1x-time-of-flight-distance-sensor | M |
| **INA226** (CJMCU-226) | **US$ 0,88–2,05** (AliExpress); 1,25 (ElectroPeak) | **R$ 37** (ML) | — | https://www.aliexpress.com/item/1005005890074659.html · https://www.aliexpress.com/item/1005012445490081.html · https://lista.mercadolivre.com.br/ina226 | A |
| **Molicel P50B** 21700 | **US$ 8,99–13,99/célula** (Liion Wholesale 8,99; Battery Junction 11,35 → 10,50 com 10+, 9,25 com 200+; United Lithium 12,99) | não encontrado (ML só tem 21700 genéricas) | Ø21,55 × 70,15 mm | https://liionwholesale.com/products/molicel-npe-inr-21700-p50b-60a-5000mah-flat-top-21700-battery-authorized-distributor · https://www.batteryjunction.com/products/molicel-inr21700-p50b · https://imrbatteries.com/products/molicel-21700-p50b-5000mah-60a-battery | A |
| Fita de **níquel puro 0,15 × 8 mm** | **~US$ 0,9–3,1/m** (rolo 3 m US$ 2,77; 25 × 100 mm US$ 7,69) | não encontrado | — | https://sequremall.com/products/nickel-strip · https://www.walmart.com/c/kp/nickel-strip | B |
| **XT90** (par M+F) | Amass anti-faísca **US$ 5,99/par**; 5 pares US$ 4,26–5,99 (≈ 0,85–1,20/par) | **R$ 14–16/par** (3 pares R$ 41,65–49; 5 pares R$ 72,63–78) | — | https://www.buddyrc.com/products/amass-anti-spark-xt90-female-and-male-connector-set · https://sologood.net/products/amass-5-pairs-xt90-xt-90-male-female-bullet-connectors-power-plugs-for-rc-lipo-battery-motor · https://lista.mercadolivre.com.br/xt90-macho · https://lista.mercadolivre.com.br/conector-xt90 | A |
| **JST-XH 7 vias** (6S) | **~US$ 0,22/un** (10 por US$ 2,16) | **R$ 2,80–5,80/par** (10 pares R$ 28–58); extensão 6S 20 cm R$ 33 | — | https://www.aliexpress.com/item/1005007020576153.html · https://www.mercadolivre.com.br/3-pares-conector-jstxh-balanceamento--bateria-2s--3vias/up/MLBU5243376276 · https://www.mercadolivre.com.br/3pc-cabo-balanceamento-p-bateria-6s-c-conector-jstxh-femea/up/MLBU600694080 | M |
| Fio silicone **10 AWG** | **US$ 5,99–9,99/m** (GetFPV 5,99; Avid 6,00; Exalt 9,99); comparadores 2,84–14,40 | **R$ 10,80/m** (cabo Cofisil industrial) – **R$ 39/m** (rolo 10 m R$ 390) | Ø ext. 5,4 mm (Avid) | https://www.getfpv.com/accessories-390/wire.html · https://www.avidrc.com/product/p/2962/10awg-Silicone-Wire-Black-1-Meter · https://teamexalt.com/exalt-10awg-silicone-wire-1-meter · https://www.proelis.com.br/cabo-cofisil-10awg-200c-600v.php · https://lista.mercadolivre.com.br/fio-de-silicone-10-awg | A |
| Fio silicone **14 AWG** | **US$ 1,99–2,99/m** (RMRC 1,99; GetFPV 2,99) | não encontrado | — | https://www.getfpv.com/silicone-wire-14awg-1mtr.html · https://www.readymaderc.com/products/details/premium-silicone-wire-14ga-red-1m | A |
| Fio silicone **16 AWG** | **US$ 2,99–4,99/m** | não encontrado | — | https://www.getfpv.com/silicone-wire-16awg-1mtr.html · https://exceleraterc.com/16-awg-silicone-wire-1-meter | A |
| Fio silicone **20 AWG** | **US$ 0,99–4,40/m** (RMRC lista 0,99 e 4,40; DIYFPV 1,01/pé) | não encontrado | — | https://www.readymaderc.com/products/details/premium-silicone-wire-20ga-red-1m · https://www.diyfpv.com/product/20awg-silicone-wire-1-foot | B |
| Abraçadeiras **2,5 × 100** (100 un) | **~US$ 1–3** (NZ$ 1,50; € 2,40; a granel US$ 0,5–1,1/100) | **R$ 18,50–25,38** | — | https://constructionproducts.co.nz/products/cable-ties-2-5x100mm-black · https://www.yachtshop.eu/en/product_motomarine/2154925/Nylon+cable+ties+2.5x100mm+100pcs · https://www.mercadolivre.com.br/abracadeira-nylon-verde-25-x-100-mm-enforca-gato-100-unidades/p/MLB24430760 | M |
| Abraçadeiras **3,6 × 150** (100 un) | **US$ 1,76–3** (Ferrules Direct 1,76 UV; Microless 2,79; TME 0,03/un) | não encontrado | 75 g / 100 un | https://www.ferrulesdirect.com/products/cti150b · https://global.microless.com/product/cable-zip-tie-150mm-x-3-6mm-plastic-high-tensile-strength-durable-pack-of-100-white-zip-tie?currency=usd · https://accu-components.com/us/uv-resistant-cable-ties/767988-HCTUV-150-3-6-N-BL | M |
| Tubo CF **25 × 23 × 1000** | **US$ 32,89–39,09** (CarbonKevlarSupply promo; WindcatcherRC); € 39,93 (ClipCarbono) | **R$ 270** (ML) | **113,1 g/m** (anúncio ML); 3K enrolado | https://carbonkevlarsupply.com/products/copy-of-blue-black-carbon-fiber-tubing-25mm-x-23mm-x-500mm-3k-roll-wrapped-glossy · https://windcatcherrc.com/product/3k-carbon-fiber-tube-25mm-x-23mmx-1000mm-matte-finish · https://www.mercadolivre.com.br/tubo-fibra-de-carbono-3k-25mm-ext-e-23mm-int-x-100cm-1-metro/up/MLBU3112125701 | A |
| Tubo CF **Ø16** (16 × 14 × 1000) | **US$ 16,28–37,25** (Windcatcher 16,28–22,70; EasyComposites 37,25); pultrudido 16 × 12 (2 un) 27,99 | não encontrado | **74,2 g/m** (EasyComposites) | https://windcatcherrc.com/product/carbon-fiber-tube-16mm-x-14mm-x-1000mm · https://www.easycomposites.us/16mm-woven-finish-carbon-fiber-tube | A |
| Tubo CF **Ø12** (12 × 10 × 1000) | **US$ 10,86–13,99**; pultrudido 12 × 8: 14,99 | não encontrado | ≈ 54 g/m (calculado com a densidade implícita da EasyComposites, 1,57 g/cm³) | https://windcatcherrc.com/product/carbon-fiber-tube-12mm-x-10mm-x-1000mm · https://superstitionhobbies.com/products/cft1281-carbon-fiber-tube-12mm-x-10mm-x-1000mm | A |
| Malha PET expansível | **US$ 0,34–0,56/m** (Techflex 1000 pés US$ 105; 1/8″ 100 pés US$ 16,99); cores premium até US$ 2,30/pé | não encontrado | — | https://buyheatshrink.com/techflex-flexo-pet-colored-braided-cable-sleeving · https://www.lowes.com/pd/Unique-Bargains-100-Ft-1-8-Inch-Expandable-Braided-Cable-Sleeve-PET-Cable-Management-Wire-Sleeving-Cord-Protector-Wire-Wrap-Loom-Tube-for-TV-Computer-Audio-Office-Home-Devices-Black/8036484 | M |
| Termo-retrátil (kit) | **US$ 9,99** (560 peças, ServoCity) – 19,99 (198 peças 3:1 com cola, Powerwerx) | **R$ 25,83–38,90** (780 peças); R$ 29,08 (328 peças) | — | https://www.servocity.com/heat-shrink-tubing-560pc-assortment-pack · https://powerwerx.com/198pc-31-heat-shrink-adhesive-assortment · https://www.mercadolivre.com.br/kit-espaguete-termo-retratil-780-pc-colorido-fios-cabos/up/MLBU4246534282 | A |
| Fita de bateria **15 mm** | Foxeer 250 × 15 mm silicone, 3 un **US$ 7,99** (≈ 2,66/un); MEPS US$ 2,35 | não encontrado | 250 × 15 × 1,8 mm | https://www.foxeer.com/foxeer-1-8mm-thickness-silicon-durable-battery-strap-3pcs-250-15mm-g-359 · https://www.mepsking.shop/meps-battery-strap.html | A |

---

### 9. Câmbio USD → BRL (outubro de 2026) e custo de importação

| item | valor | fonte | conf. |
|---|---|---|---|
| Dólar comercial (fecho 2026-10-19, 17:18) | **R$ 5,0480** (−0,49 %) | https://valor.globo.com/valor-data | A |
| Dólar PTAX (2026-10-19) | **R$ 5,0826** | idem | A |
| Outras leituras | R$ 5,06 (Notícias Agrícolas, 19/10); 5,0646 (Investing.com); 5,0914 em 15/10 (Investing CA) | https://www.noticiasagricolas.com.br/cotacao-do-dolar · https://www.investing.com/currencies/usd-brl · https://ca.investing.com/currencies/usd-brl | A |
| **Usado neste relatório** | **5,05** | — | — |
| Imposto de importação, remessas ≤ US$ 50 (Remessa Conforme) | **0 %** desde 12/05/2026 (MP 1.357/2026, aprovada no Senado em 03/09/2026) + ICMS 17–20 % | https://www.serasa.com.br/blog/remessa-conforme · https://www.legisweb.com.br/noticia?id=34369 · https://www12.senado.leg.br/noticias/materias/2026/09/03/senado-zera-taxa-das-blusinhas-nas-remessas-internacionais-de-ate-us-50 | A |
| Remessas US$ 50,01–3000 | **60 %** com desconto de US$ 20 no imposto + ICMS ~17 % | https://simplifique.contmatic.com.br/blogs/imposto-de-importacao-2026-aliquotas-como-calcular | M |

**Estimativa de custo posto no Brasil (cálculo, não cotação), para peças que não se acham em loja brasileira:**
pedido > US$ 50: `BRL ≈ 5,05 × (V + máx(0; 0,6·V − 20)) / (1 − 0,17)`; pedido ≤ US$ 50: `BRL ≈ 5,05 × V / (1 − 0,17)`.
Exemplos: 4 × MN5006 (V = 339,96, frete grátis acima de US$ 200 na T-Motor) → ≈ **R$ 3 190** (≈ R$ 797/motor);
2 pares P15×5 (V = 111,80) → ≈ R$ 970; 4 × AIR 40A (V = 159,96) → ≈ R$ 1 440 (frete não incluído onde não é grátis).

---

### Observações para o modelo do laboratório (decorrem dos números, não substituem medição)

- O **eixo Z da impressão manda**: ABS impresso perde 11–63 % de resistência entre camadas (eSUN ABS+ 40,1 → 14,9 MPa; PolyLite 33,4 → 29,7 MPa) e o módulo cai ~7–20 %. Orientar as peças para que o esforço principal fique em XY; para o MuJoCo/MjSpec usar **ρ = 1,04 g/cm³** e, para a massa real, `massa ≈ ρ · (volume das paredes + enchimento × volume interior)`.
- **6S e UBEC**: o Hobbywing UBEC 8A clássico (2–3S) **não** aceita 6S; para servos a 6,8–7,4 V com bateria 6S os candidatos medidos nas fichas são o **ZTW 8A G2** (14 g, até 8,4 V) e o **Holybro 12A** (47,8 g, 7,2 V, 12 A contínuos). Oito DS3218 a bloquear juntos pedem 8 × 1,8–2,6 A ≈ 14–21 A, acima do contínuo de qualquer um destes.
- **RPi 5**: a Pololu D36V50F5 (7 g, 5,5 A) e a Matek BEC12S-PRO (5 g, 5 A) aceitam 6S cheio; o buck genérico 12–24 V fica no limite com 25,2 V.
- **Relação 1:50 do 25GA-370**: não existe em catálogo; as vizinhas reais são 1:45 / 1:46,8.

---

### Bloco JSON (valores legíveis por máquina)

Convenções: `*_faixa` = [mín, máx]; `null` = não encontrado; `*_calc` = calculado, não lido; preços de outubro de 2026; câmbio 5,05.

```json
{
 "data_pesquisa": "2026-10-20",
 "cambio_usd_brl": 5.05,
 "cambio_detalhe": {
  "comercial_fecho_2026_10_19": 5.048,
  "ptax_2026_10_19": 5.0826,
  "fontes": [
   "https://valor.globo.com/valor-data",
   "https://www.noticiasagricolas.com.br/cotacao-do-dolar"
  ]
 },
 "importacao_brasil_2026": {
  "ate_usd_50": {
   "imposto_importacao": 0.0,
   "icms": [
    0.17,
    0.2
   ],
   "desde": "2026-05-12 (MP 1.357/2026)"
  },
  "usd_50_a_3000": {
   "imposto_importacao": 0.6,
   "desconto_usd": 20,
   "icms": 0.17
  },
  "formula_brl": "5.05*(V+max(0,0.6*V-20))/(1-0.17) para V>50; 5.05*V/(1-0.17) para V<=50",
  "fontes": [
   "https://www.serasa.com.br/blog/remessa-conforme",
   "https://www12.senado.leg.br/noticias/materias/2026/09/03/senado-zera-taxa-das-blusinhas-nas-remessas-internacionais-de-ate-us-50",
   "https://simplifique.contmatic.com.br/blogs/imposto-de-importacao-2026-aliquotas-como-calcular"
  ]
 },
 "25ga370_comum_12v_encoder": {
  "dims_mm": {
   "redutor_diam": 25.0,
   "redutor_comprimento_por_relacao": {
    "<=1:20.4": 19,
    "1:26-1:45": 21,
    "1:57-1:100": 23,
    "1:125-1:217": 25,
    "1:274-1:500": 27
   },
   "motor_diam": 24.4,
   "motor_comprimento": 30.8,
   "encoder_extensao_traseira": 8.7,
   "corpo_total_sem_veio": "L+40",
   "veio_diam_D": 4.0,
   "veio_comprimento_util": [
    9.5,
    9.8
   ],
   "veio_comprimento_total": 12.0,
   "furos_frontais": {
    "quantidade": 2,
    "rosca": "M3",
    "entre_centros": 17.0,
    "profundidade": 4.5
   }
  },
  "massa_g": [
   90,
   110
  ],
  "encoder": {
   "ppr_motor": 11,
   "polos": 22,
   "tensao_v": [
    3.3,
    5.0
   ],
   "conector": "PH2.0 6 vias"
  },
  "preco_usd_faixa": [
   6.83,
   12.01
  ],
  "preco_brl_faixa": [
   55,
   131
  ],
  "confianca": "A (geometria) / M (furos, encoder)",
  "fontes": [
   "https://nfpmotor.com/25mm-metal-gear-motor-model-nfp-jga25-370-en",
   "http://www.tronsunmotor.com/data/upload/file/201910/e78fcf93ed604a64c69852b5db49a03f.pdf",
   "https://manuals.plus/ae/1005006693616088",
   "https://rcdrone.top/products/jga25-370-dc-gear-motor-with-encoder",
   "https://www.aliexpress.com/item/1005002598362488.html",
   "https://www.mercadolivre.com.br/mys-motoredutor-12vdc-jga25-370-60-350rpm-encoder-/p/MLB2082386720"
  ]
 },
 "25ga370_12v_1_34": {
  "dims_mm": {
   "redutor_diam": 25,
   "redutor_comprimento": 21,
   "corpo_total_sem_veio_calc": 61,
   "veio_diam_D": 4,
   "veio_comprimento_util": 9.5
  },
  "massa_g": 99,
  "rpm_vazio": 175,
  "rpm_vazio_faixa": [
   126,
   250
  ],
  "torque_nominal_kgcm": 1.3,
  "torque_bloqueio_kgcm": 4.2,
  "torque_bloqueio_faixa_kgcm": [
   3.8,
   4.5
  ],
  "corrente_nominal_a": 0.18,
  "corrente_bloqueio_a_faixa": [
   1.0,
   1.2
  ],
  "limite_redutor_kgcm": {
   "nominal": 2.0,
   "instantaneo": 6.0
  },
  "preco_usd": 9.0,
  "preco_usd_faixa": [
   6.83,
   12.01
  ],
  "preco_brl_faixa": [
   55,
   131
  ],
  "confianca": "M",
  "fontes": [
   "https://people.ece.ubc.ca/~eng-services/files/courses/elec391-data_sheets/MOT4-info.pdf",
   "https://nfpmotor.com/6v-12v-24v-dc-gearmotor-model-nfp-25-370",
   "https://www.openimpulse.com/blog/jga25-370-gearmotor-selector"
  ]
 },
 "25ga370_12v_1_50": {
  "nota": "1:50 nao encontrado em catalogo; valores das relacoes vizinhas 1:45 e 1:46.8",
  "dims_mm": {
   "redutor_comprimento": 21
  },
  "rpm_vazio_faixa": [
   130,
   188
  ],
  "torque_nominal_kgcm": 1.8,
  "torque_bloqueio_faixa_kgcm": [
   4.4,
   6.0
  ],
  "corrente_bloqueio_a_faixa": [
   1.0,
   1.8
  ],
  "preco_usd_faixa": [
   6.83,
   12.01
  ],
  "preco_brl_faixa": [
   55,
   131
  ],
  "confianca": "M",
  "fontes": [
   "https://nfpmotor.com/6v-12v-24v-dc-gearmotor-model-nfp-25-370",
   "https://www.openimpulse.com/blog/jga25-370-gearmotor-selector",
   "https://www.ram-e-shop.com/shop/dc-jga25-370-enc-12v130r-25ga370-dc-geared-motor-with-encoder-12vdc-130-rpm-9331"
  ]
 },
 "25ga370_12v_1_75": {
  "dims_mm": {
   "redutor_comprimento": 23,
   "corpo_total_sem_veio_calc": 63
  },
  "rpm_vazio": 80,
  "rpm_vazio_faixa": [
   80,
   108
  ],
  "torque_nominal_kgcm": 3.0,
  "torque_bloqueio_kgcm": 9.0,
  "torque_bloqueio_faixa_kgcm": [
   8.4,
   9.0
  ],
  "corrente_bloqueio_a_faixa": [
   1.0,
   1.2
  ],
  "limite_redutor_kgcm": {
   "nominal": 2.5,
   "instantaneo": 7.0
  },
  "preco_usd_faixa": [
   6.83,
   12.01
  ],
  "preco_brl_faixa": [
   55,
   131
  ],
  "confianca": "M",
  "fontes": [
   "https://nfpmotor.com/6v-12v-24v-dc-gearmotor-model-nfp-25-370",
   "https://www.openimpulse.com/blog/jga25-370-gearmotor-selector",
   "http://www.tronsunmotor.com/data/upload/file/201910/e78fcf93ed604a64c69852b5db49a03f.pdf"
  ]
 },
 "jgy370_12v_semfim": {
  "dims_mm": {
   "redutor": [
    46,
    32,
    25
   ],
   "conjunto": [
    76.8,
    32,
    25
   ],
   "motor_diam": 24.4,
   "motor_comprimento": 30.8,
   "altura_total": 40.8,
   "veio_diam_D": 6,
   "veio_comprimento": [
    14,
    15.6
   ],
   "furos": {
    "quantidade": 4,
    "rosca": "M3",
    "espacamento": [
     33,
     18
    ]
   }
  },
  "massa_g": [
   150,
   165
  ],
  "autobloqueante": true,
  "torque_kgcm_exemplos": {
   "160rpm_1:37.3": {
    "nominal": 0.55,
    "bloqueio": 2.2,
    "corrente_bloqueio_a": 1.0
   },
   "90rpm": 2.0,
   "3rpm": [
    12,
    25
   ]
  },
  "torque_anunciado_max_kgcm": [
   24,
   35
  ],
  "preco_usd": 8.59,
  "preco_usd_faixa": [
   4.4,
   12.5
  ],
  "preco_brl_faixa": [
   88.5,
   137.99
  ],
  "confianca": "M",
  "fontes": [
   "https://kitsguru.com/products/jgy370-dc-12v-90rpm-2kg-cm-metal-worm-gear-motor-pwm-forward-reverse",
   "https://media.digikey.com/pdf/data%20sheets/seeed%20technology/108990007_web.pdf",
   "https://www.robotshop.com/products/aslong-motor-jgy370-12v-30rpm-high-torque-worm-gear-motor",
   "https://www.saravati.com.br/motor-reversivel-de-alto-torque-jgy370-12v-100rpm.html"
  ]
 },
 "servo_ds3218mg": {
  "dims_mm": {
   "corpo": [
    40,
    20,
    40.5
   ],
   "orelhas_total_B": 54.5,
   "furos_entre_centros_B": 49.5,
   "estriado": "25T",
   "estriado_diam": 5.9
  },
  "massa_g": 60,
  "torque_kgcm": {
   "5.0V": 19.0,
   "6.8V": 21.5
  },
  "velocidade_s_60": {
   "5.0V": 0.16,
   "6.8V": 0.14
  },
  "corrente_bloqueio_a": [
   1.8,
   2.6
  ],
  "tensao_v": [
   4.8,
   6.8
  ],
  "angulos": [
   180,
   270
  ],
  "reducao": 275,
  "horn": "braco 25T metalico incluido; disco 25T Al d20x5 mm 4 g vendido a parte",
  "preco_usd": 15.0,
  "preco_usd_faixa": [
   13.8,
   22.99
  ],
  "preco_brl_faixa": [
   40.46,
   125.3
  ],
  "confianca": "A (desempenho) / B (orelhas)",
  "fontes": [
   "https://speedyfpv.com/products/ds3218mg-digital-servo-high-speed-high-torque-metal-gear-waterproof-20kg-torque-180-degrees-w-accessories",
   "https://images-na.ssl-images-amazon.com/images/I/81Lbgu+nG6L.pdf",
   "https://rcdrone.top/products/dsservo-ds3218-digital-servo",
   "https://servodatabase.com/servo/dsservo/ds3218-mg",
   "https://www.aliexpress.com/item/1005003444099992.html",
   "https://produto.mercadolivre.com.br/MLB-5080148072-servo-motor-miuzei-ds3218-de-alto-torque-20-kg-prova-dagu-_JM"
  ]
 },
 "servo_mg996r": {
  "dims_mm": {
   "corpo": [
    40.7,
    19.7,
    42.9
   ],
   "estriado": "25T"
  },
  "massa_g": 55,
  "torque_kgcm": {
   "4.8V": 9.4,
   "6.0V": 11.0
  },
  "velocidade_s_60": {
   "4.8V": [
    0.17,
    0.19
   ],
   "6.0V": [
    0.14,
    0.15
   ]
  },
  "corrente_bloqueio_a": [
   1.4,
   2.5
  ],
  "tensao_v": [
   4.8,
   7.2
  ],
  "angulos": [
   180
  ],
  "preco_usd_faixa": [
   2.52,
   12.5
  ],
  "preco_brl_faixa": [
   24,
   42.3
  ],
  "confianca": "A",
  "nota": "muitos clones",
  "fontes": [
   "https://servodatabase.com/servo/towerpro/mg996r",
   "https://www.electronicoscaldas.com/datasheet/MG996R_Tower-Pro.pdf",
   "https://www.tinkered.ai/components/servo-mg996r-cross",
   "https://lista.mercadolivre.com.br/servo-motor-mg996r"
  ]
 },
 "servo_ds3235": {
  "dims_mm": {
   "corpo": [
    40,
    20,
    [
     38.5,
     40.5
    ]
   ]
  },
  "massa_g": 60,
  "torque_kgcm": {
   "5.0V": 23,
   "7.4V": 30,
   "8.4V": 35
  },
  "velocidade_s_60": {
   "5.0V": 0.18,
   "7.4V": 0.13,
   "8.4V": 0.11
  },
  "corrente_bloqueio_a": {
   "5.0V": 2.2,
   "7.4V": 2.9,
   "8.4V": 3.2
  },
  "motor": "coreless",
  "angulos": [
   180,
   270
  ],
  "preco_usd": 17.11,
  "preco_usd_faixa": [
   17.11,
   32
  ],
  "preco_brl_faixa": [
   118.23,
   179.81
  ],
  "confianca": "A (desempenho) / M (preco)",
  "fontes": [
   "https://servodatabase.com/servo/dsservo/ds3235-sg",
   "https://hajim.rochester.edu/me/sites/kelley/me240/DS3235-270_datasheet.pdf",
   "https://aifitlab.com/products/dsservo-ds3235-sg-servo-motor",
   "https://www.aliexpress.com/w/wholesale-ds3235-servo-35kg.html",
   "https://www.mercadolivre.com.br/ds3235-35kg-metal-high-torsion-digital-steering-servo-for/p/MLB2049640530"
  ]
 },
 "servo_jx_cls6336hv": {
  "dims_mm": {
   "corpo": [
    40.5,
    20.5,
    40
   ]
  },
  "massa_g": 63,
  "torque_kgcm": {
   "6.6V": 27.8,
   "7.4V": 35.6
  },
  "velocidade_s_60": {
   "6.6V": 0.14,
   "7.4V": 0.11
  },
  "tensao_v": [
   6.0,
   7.4
  ],
  "motor": "coreless",
  "preco_usd": 28.54,
  "preco_usd_faixa": [
   28.54,
   58.9
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://servodatabase.com/servo/jx-servo/cls6336hv",
   "https://www.aliexpress.com/item/4001355900312.html",
   "https://usa-m.banggood.com/JX-Ecoboost-CLS6336HV-36KG-Large-Torque-180-CNC-DigitalCoreless-Servo-for-RC-Models-p-1314550.html"
  ]
 },
 "semfim_m1_khk_sw1_r1": {
  "dims_mm": {
   "diam_primitivo": 16,
   "diam_externo": 18,
   "rosca_comprimento": 20,
   "comprimento_total": 32,
   "furo": 6,
   "parafuso": "M4"
  },
  "material": "aco S45C",
  "entradas": 1,
  "angulo_helice": "3deg35min",
  "preco_usd": 23.25,
  "confianca": "A",
  "fontes": [
   "https://catalog.khkgears.us/item/worm-gears/steel-worms-sw/sw1-r1",
   "https://www.zoro.com/khk-usa-ground-and-machined-steel-worms-sw1-r1/i/G304671507"
  ]
 },
 "coroa_m1_khk_bg1_20r1": {
  "dentes": 20,
  "dims_mm": {
   "diam_primitivo": 20.05,
   "diam_garganta": 22,
   "diam_externo": 23,
   "largura": 10,
   "cubo_diam": 16,
   "cubo_largura": 10,
   "comprimento_total": 20,
   "furo": 6,
   "distancia_eixos": 18
  },
  "material": "bronze CAC502",
  "preco_usd": 46.76,
  "confianca": "A",
  "fontes": [
   "https://catalog.khkgears.us/item/worm-gears/bronze-worm-wheels-bg/bg1-20r1",
   "https://www.grainger.com/product/KHK-GEARS-Worm-Wheel-Reduction-Ratio-793AU3"
  ]
 },
 "coroa_m1_khk_bg1_30r1": {
  "dentes": 30,
  "dims_mm": {
   "diam_primitivo": 30.07,
   "diam_garganta": 32,
   "diam_externo": 33,
   "largura": 10,
   "cubo_diam": 20,
   "furo": 6,
   "distancia_eixos_calc": 23.0
  },
  "material": "bronze",
  "preco_usd": null,
  "confianca": "A",
  "fontes": [
   "https://catalog.khkgears.us/item/worm-gears/bronze-worm-wheels-bg/bg1-30r1"
  ]
 },
 "coroa_m1_khk_bg1_40r1": {
  "dentes": 40,
  "dims_mm": {
   "diam_primitivo": 40.08,
   "diam_garganta": 42,
   "diam_externo": 43,
   "largura": 10,
   "cubo_diam": 26,
   "furo": 8,
   "distancia_eixos_calc": 28.0
  },
  "material": "bronze",
  "preco_usd": null,
  "confianca": "A",
  "fontes": [
   "https://logosfoundation.org/instrum_gwr/synchrochord/datasheets/Worm_Wheels_Section%25209.pdf"
  ]
 },
 "semfim_m1_kit_diy": {
  "material": "aco 45# (sem tempera)",
  "relacoes": "1:15-1:100",
  "furo_mm": [
   6,
   10
  ],
  "dims_mm": null,
  "nota": "medidas nao encontradas; usar geometria KHK",
  "preco_usd": 10.07,
  "preco_usd_faixa": [
   7.81,
   23.99
  ],
  "preco_brl": null,
  "confianca": "M",
  "fontes": [
   "https://www.aliexpress.com/item/1005005117237912.html",
   "https://www.amazon.com/Worm-Gear-Rod-Reduction-Ratio/dp/B0H59XY9HJ"
  ]
 },
 "semfim_m08": {
  "material": "coroa latao + sem-fim inox",
  "dentes": [
   20,
   60
  ],
  "furo_mm": [
   5,
   12
  ],
  "exemplo_20T_uxcell": {
   "diam_externo": 17.6,
   "espessura": 8,
   "altura_total": 16,
   "furo": 4
  },
  "preco_usd_por_peca": 11.41,
  "preco_usd_misumi_eur": 6.58,
  "confianca": "M",
  "fontes": [
   "https://homediyer.com/products/0-8-module-worm-gear-set-brass-worm-wheel-stainless-worm-rod",
   "https://vxb.com/products/brass-worm-gear-set-with-20-teeth-and-08-module-fo",
   "https://uk.misumi-ec.com/vona2/detail/110302194530"
  ]
 },
 "rolamento_608zz": {
  "dims_mm": [
   8,
   22,
   7
  ],
  "massa_g": [
   12,
   13.6
  ],
  "carga_dinamica_kn": 3.3,
  "carga_estatica_kn": 1.37,
  "preco_usd_10": [
   5.57,
   8.88
  ],
  "preco_usd_un": [
   0.56,
   0.89
  ],
  "preco_brl_10": [
   16.14,
   57.0
  ],
  "confianca": "A",
  "fontes": [
   "https://www.123bearing.com/bearing-housing/deep-groove-bearing/single-row/608-zz-skf",
   "https://www.aliexpress.us/w/wholesale-608zz-bearing.html",
   "https://www.casadosroletes.store/produtos/608-zz-kit-com-10-rolamentos-rigido-de-esfera-1jxwd",
   "https://lista.mercadolivre.com.br/kit-rolamentos-608zz"
  ]
 },
 "rolamento_688zz": {
  "dims_mm": [
   8,
   16,
   5
  ],
  "massa_g": [
   3.8,
   4.05
  ],
  "preco_usd_un": [
   0.16,
   1.15
  ],
  "preco_usd_10": [
   2,
   12
  ],
  "preco_brl_pacote_10_40": 140.33,
  "confianca": "A (massa) / M (preco)",
  "fontes": [
   "https://iskbearing.com/product-details/688zz",
   "https://bulkman3d.com/product/688zz-ball-bearing",
   "https://www.lily-bearing.com/products/688zz",
   "https://lista.mercadolivre.com.br/8x16x5"
  ]
 },
 "eixo_8mm_cromado": {
  "nota": "muitos anuncios sao h8, nao h6",
  "preco_usd_500mm": [
   3.6,
   9.3
  ],
  "preco_usd_m": [
   7,
   19
  ],
  "preco_brl_600mm": 105.85,
  "preco_brl_m_calc": 176,
  "confianca": "M",
  "fontes": [
   "https://www.aliexpress.com/w/wholesale-8-500mm-linear-shaft.html",
   "https://www.walmart.com/ip/Linear-Motion-Rods-8mm-x-500mm-Case-Hardened-Chrome-Plated-Linear-Motion-Rod-Shaft-or-3D-Printer-DIY-CNC-Metric-h8-Tolerance/2663477516",
   "https://datacombr.com.br/index.php?route=product%2Fproduct&product_id=278"
  ]
 },
 "colar_eixo_8mm": {
  "dims_mm": {
   "furo": 8,
   "diam_externo": 16,
   "largura": 8,
   "parafuso": "M4"
  },
  "massa_g": 8.5,
  "preco_usd_10": 10.26,
  "preco_brl_10": 39.99,
  "confianca": "A (dims) / M (preco)",
  "fontes": [
   "https://summitcollars.com/product/cz-8mm-8mm-id-metric-set-screw-shaft-collar-zinc-plated",
   "https://www.innerscene.com/tools/library/3d-parts/8-mm-set-screw-shaft-collar-52204035",
   "https://www.walmart.com/ip/10-Packs-Set-Screw-Collars-8mm-Bore-Shaft-Collars-14mm-OD-7mm-Width-Gear-Stopper-Wheel-Collar/5227789644",
   "https://www.mercadolivre.com.br/anel-trava-eixo-bitola-8mm-em-inox-pacote-de--10-pecas-/up/MLBU597496201"
  ]
 },
 "inserto_m3_latao": {
  "dims_mm": {
   "comprimento": 5.7,
   "diam_externo": 4.6,
   "furo_recomendado": 4.0,
   "variante_curta_comprimento": 3.0
  },
  "preco_usd_100": 10.9,
  "preco_usd_100_faixa": [
   7,
   10.99
  ],
  "preco_brl_100": [
   42.68,
   89
  ],
  "confianca": "A",
  "fontes": [
   "https://cnckitchenus.store/products/heat-set-insert-m3-x-5-7-100-pieces",
   "https://partsbuilt.com/m3-heat-set-thread-insert-5mm-long-4-pack",
   "https://www.prusa3d.com/product/heat-set-inserts-m3-standard-100-pcs",
   "https://produto.mercadolivre.com.br/MLB-4722656701-kit-150-insertos-roscados-lato-m2-m3-m4-para-impresso-3d-_JM"
  ]
 },
 "parafuso_m3_din912": {
  "preco_usd_100": [
   5,
   17
  ],
  "preco_brl_100": [
   36.97,
   48
  ],
  "confianca": "M",
  "fontes": [
   "https://pneucons.com/m3-socket-head-cap-screws-din-912-grade-12-9-pack-of-100pcs",
   "https://accu-components.com/us/metric-cap-head-screws/3817-SSCF-M3-6-A2",
   "https://projetteparafusos.com.br/parafuso-sextavado-interno-cabeca-cilindrica-din-912-m3-x-10-inox-a2"
  ]
 },
 "porca_m3_nyloc": {
  "preco_usd_100": [
   6.39,
   18
  ],
  "preco_brl_100": 35.79,
  "confianca": "A",
  "fontes": [
   "https://www.parts-express.com/M3-Nylock-Locknut-with-Nylon-Insert-Zinc-100-Pcs.-081-3205",
   "https://produto.mercadolivre.com.br/MLB-5220613263-porca-auto-travante-parlock-m12-175-ma-100-pecas-_JM"
  ]
 },
 "abs_filamento": {
  "densidade_g_cm3": 1.04,
  "densidade_faixa": [
   1.02,
   1.06
  ],
  "modulo_tracao_gpa": {
   "xy": 2.25,
   "z": 2.08
  },
  "modulo_flexao_gpa": {
   "esun_abs_plus_xy": 1.87,
   "esun_abs_plus_z": 1.51,
   "bambu": 1.88
  },
  "resistencia_tracao_mpa": {
   "xy": [
    33,
    43
   ],
   "z": [
    14.9,
    29.7
   ]
  },
  "preco_usd_kg": [
   10.69,
   22.99
  ],
  "preco_usd_kg_tipico": 16,
  "preco_brl_kg": {
   "voolt3d": [
    96.51,
    105.16
   ],
   "3dfila": [
    104.93,
    129.9
   ]
  },
  "impressao": {
   "perimetros": 4,
   "enchimento_pct": [
    30,
    50
   ],
   "padrao_voron": "4 perimetros + 40%",
   "bico_c": [
    230,
    270
   ],
   "mesa_c": [
    95,
    110
   ],
   "ventoinha_pct": 0
  },
  "vazao_max_mm3_s": {
   "v6": 11,
   "bambu_preset": 16
  },
  "debito_real_g_h": {
   "corexy": [
    28,
    35
   ],
   "bedslinger": [
    18,
    25
   ],
   "ender3": [
    8,
    12
   ]
  },
  "debito_real_cm3_h_calc": {
   "corexy": [
    27,
    34
   ],
   "bedslinger": [
    17,
    24
   ],
   "ender3": [
    8,
    12
   ]
  },
  "confianca": "A (propriedades/preco) / M (debito)",
  "fontes": [
   "https://polymaker.com/wp-content/uploads/lana-downloads/TDS_Polymaker_PolyLite-ABS_V5.6_2025-12-30_EN.pdf",
   "https://www.matterhackers.com/store/l/esun-abs-filament/sk/MX9UGRGL",
   "https://www.spoolscout.com/data-sheets/esun/abs-abs",
   "https://stemfinity.com/products/bambu-lab-abs",
   "https://www.esun3d.com/abs-pro-product",
   "https://store.sunlu.com/collections/3d-printer-filament",
   "https://voolt3d.com.br/abs",
   "https://produto.mercadolivre.com.br/MLB-3337188423-filamento-3dfila-abs-premium-1kg-175mm-varias-cores-_JM",
   "https://forum.prusa3d.com/forum/original-prusa-i3-mk3s-mk3-how-do-i-print-this-printing-help/settings-for-functional-strength",
   "https://grandpacad.com/en/tools/volumetric-flow-calculator",
   "https://filamentcalcs.com/guides/3d-print-time-expectations"
  ]
 },
 "buck_xl4016_8a": {
  "dims_mm": [
   61,
   41,
   27
  ],
  "dims_com_display_mm": [
   64,
   47,
   26
  ],
  "massa_g": [
   48,
   50
  ],
  "entrada_v": [
   4,
   40
  ],
  "saida_v": [
   1.25,
   36
  ],
  "corrente_max_a": 8,
  "preco_usd": null,
  "preco_brl_un": 48.3,
  "confianca": "M",
  "fontes": [
   "https://www.rytronics.in/product/xl4016-8a-200w-dc-dc-step-down-buck-converter",
   "https://www.mercadolivre.com.br/10-x-modulo-conversor-tensao-dc-dc-step-down-8a-xl4016-c-di/p/MLB2072890439"
  ]
 },
 "ubec_hobbywing_8a_2_3s": {
  "dims_mm": [
   42,
   39,
   9
  ],
  "massa_g": [
   36,
   38
  ],
  "entrada_v": [
   6,
   12.6
  ],
  "saida_v": [
   5,
   6
  ],
  "corrente_a": {
   "continua": 8,
   "pico": 15
  },
  "serve_6s": false,
  "preco_usd": 18.49,
  "preco_brl": 229.9,
  "confianca": "A",
  "fontes": [
   "https://www.hobbywing.com/en/products/ubec-8a-2-3s100",
   "https://superstitionhobbies.com/products/hobbyiwng-ubec-8a",
   "https://www.mercadolivre.com.br/hobbywing-8a-ubec-5v-6v-chave-liga-desliga-max-15a-aeromodel/p/MLB2106683619"
  ]
 },
 "ubec_hobbywing_8a_6s": {
  "dims_mm": [
   62,
   27.5,
   10
  ],
  "massa_g": 24.5,
  "entrada_v": [
   5.5,
   26
  ],
  "saida_v": [
   5.2,
   6.0
  ],
  "corrente_a": {
   "continua": 8,
   "pico_10s": 15
  },
  "preco_usd": 29.19,
  "preco_brl": null,
  "confianca": "M",
  "fontes": [
   "https://valuehobby.com/hobbywing-8a-ubec-2s-6s.html",
   "https://www.littohot.com/products/hobbywing-ubec-8a-6s-for-esc-electronic-speed-controller"
  ]
 },
 "ubec_ztw_8a_g2": {
  "dims_mm": [
   50,
   20,
   7
  ],
  "massa_g": 14,
  "entrada": "2-8S (7-34 V)",
  "saida_v": [
   5,
   6,
   7.4,
   8.4
  ],
  "corrente_a": {
   "continua": 8,
   "pico": 15
  },
  "preco_usd": 16.99,
  "preco_usd_faixa": [
   16.99,
   29.99
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.altitudehobbies.com/products/ztw-8a-external-bec-2-8s-ubec",
   "https://ztwesc.com/products/ztw-ubec-8a-g2-peak-15a-adjustable-output-voltage-5v-6v-7-4v-8-4v-external-bec"
  ]
 },
 "ubec_holybro_12a": {
  "dims_mm": [
   48,
   33.6,
   16.3
  ],
  "massa_g": 47.8,
  "entrada": "3-14S",
  "saida_v": [
   6.0,
   7.2,
   8.0,
   9.2
  ],
  "corrente_a": {
   "continua": 12,
   "pico": 24
  },
  "preco_usd": 36.59,
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://holybro.com/products/ubec-12a",
   "https://www.flyingtech.co.uk/product/holybro-12a-ubec-15026"
  ]
 },
 "bec_castle_cc_2_0": {
  "dims_mm": null,
  "massa_g": [
   21,
   28
  ],
  "entrada": "2-14S",
  "saida_v": [
   4.75,
   12
  ],
  "corrente_a": {
   "5-6V": 10,
   "7.25-8.5V": 9,
   "pico": 15
  },
  "preco_usd": [
   54.95,
   56.95
  ],
  "preco_brl": null,
  "confianca": "M",
  "fontes": [
   "https://www.offshoreelectrics.com/proddetail.php?prod=hh-cas-010-0153-00",
   "https://castlecreations.com/collections/voltage-regulators-becs"
  ]
 },
 "bec_5v_pololu_d36v50f5": {
  "dims_mm": [
   25.4,
   25.4,
   9.5
  ],
  "massa_g": 7.0,
  "entrada_v": [
   5.5,
   50
  ],
  "saida_v": 5.0,
  "corrente_a": 5.5,
  "preco_usd": 39.95,
  "preco_usd_faixa": [
   39.95,
   43.4
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.pololu.com/product/4091/specs",
   "https://www.robotshop.com/products/5v-55a-step-down-voltage-regulator-d36v50f5"
  ]
 },
 "bec_5v_matek_bec12s_pro": {
  "dims_mm": [
   35,
   24,
   5.5
  ],
  "massa_g": 5,
  "entrada_v": [
   9,
   55
  ],
  "saida_v": [
   5.2,
   8,
   12
  ],
  "corrente_a": {
   "continua": 5,
   "pico": 9
  },
  "preco_usd": 24.99,
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://rcdrone.top/products/matek-mateksys-bec12s-pro-9-55v-to-5v-8v-12v-5a",
   "https://pyrodrone.com/products/matek-12s-pro-bec-12s-9-55v-input-5v-8v-12v-5a-output"
  ]
 },
 "bec_matek_ubec_duo": {
  "dims_mm": [
   58,
   36,
   8
  ],
  "massa_g": 32,
  "entrada": "2-6S (7-26 V)",
  "saida1_v": [
   5,
   6,
   7.2,
   12
  ],
  "saida1_a": {
   "continua": 4,
   "max": 6
  },
  "saida2": {
   "v": 5,
   "a_continua": 4,
   "a_max": 6
  },
  "preco_usd_faixa": [
   13.58,
   22.37
  ],
  "preco_brl": null,
  "confianca": "M",
  "fontes": [
   "https://gadgetsdeal.in/shop/bec/matek-systems-ubec-duo-4a-512v-4a-5v-in-india",
   "https://www.aliexpress.com/item/1005003596735617.html"
  ]
 },
 "buck_5v_5a_generico": {
  "dims_mm": [
   65,
   58,
   22
  ],
  "massa_g": null,
  "entrada_v": [
   12,
   24
  ],
  "preco_usd_faixa": [
   3.9,
   8.04
  ],
  "preco_brl": null,
  "nota": "6S cheio (25.2 V) no limite",
  "confianca": "M",
  "fontes": [
   "https://www.droking.com/DC-Step-Down-Voltage-Regulator-DC-12-24V-to-5V-5A-25W-Buck-Converter-Module-Waterproof-Car-Power-Supply",
   "https://www.ebay.com/itm/405016226741"
  ]
 },
 "driver_drv8871_adafruit": {
  "dims_mm": [
   24.4,
   20.4,
   9.7
  ],
  "massa_g": 2.2,
  "tensao_v": [
   6.5,
   45
  ],
  "corrente_pico_a": 3.6,
  "preco_usd": 7.5,
  "preco_brl_faixa": [
   57.53,
   111.84
  ],
  "confianca": "A",
  "fontes": [
   "https://shop.pimoroni.com/en-us/products/adafruit-drv8871-dc-motor-driver-breakout-board-3-6a-max",
   "https://www.adafruit.com/product/3190",
   "https://www.mercadolivre.com.br/drv8871-h-bridge-motor-driver-module-36a-pwm-driver-3pcs/p/MLB2088019012"
  ]
 },
 "driver_tb6612_pololu": {
  "dims_mm": [
   15.2,
   20.3
  ],
  "massa_g": 1.5,
  "tensao_v": [
   4.5,
   13.5
  ],
  "corrente_a": {
   "continua_canal": 1.0,
   "pico": 3.2
  },
  "canais": 2,
  "preco_usd": 4.95,
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.pololu.com/product/713/specs",
   "https://www.digikey.com/en/products/detail/pololu/713/10450399"
  ]
 },
 "driver_bts7960": {
  "dims_mm": [
   50,
   50,
   43
  ],
  "massa_g": [
   54,
   66
  ],
  "tensao_v": [
   5.5,
   27
  ],
  "corrente_a": 43,
  "preco_usd_faixa": [
   1.91,
   10.8
  ],
  "preco_brl": null,
  "confianca": "M",
  "fontes": [
   "https://electropeak.com/bts7960-43a-high-power-motor-driver-module",
   "https://handsontec.com/index.php/product/43a-high-power-bts7960-dc-motor-driver-module",
   "https://www.tztstore.com/goods/show-5093.html"
  ]
 },
 "encoder_as5048a_placa": {
  "dims_mm": null,
  "massa_g": null,
  "resolucao_bits": 14,
  "interface": [
   "SPI",
   "PWM"
  ],
  "preco_usd": 18.09,
  "preco_usd_faixa": [
   17.45,
   20.28
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.mouser.com/ProductDetail/ams-OSRAM/AS5048A-TS_EK_AB?qs=Rt6VE0PE%2FOd5D%2Fkw9O7ofA%3D%3D",
   "https://uk.rs-online.com/web/p/sensor-development-tools/2018309"
  ]
 },
 "tmotor_mn5006_kv450": {
  "massa_g": 106,
  "preco_usd": 84.99,
  "preco_brl": null,
  "preco_brl_importacao_estimado_un": 797,
  "confianca": "A",
  "fontes": [
   "https://store.tmotor.com/categorys/uav-mult-motor-antigravity-type",
   "https://www.worldronemarket.com/product/t-motor-mn5006",
   "https://www.uavmarketplace.in/products/t-motor-mn5006-450kv-antigravity-motor/895789000012592924"
  ]
 },
 "tmotor_mn4004_kv300": {
  "preco_usd_par": 145.9,
  "preco_usd": 72.95,
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://store.tmotor.com/categorys/uav-mult-motor-antigravity-type",
   "https://unmannedrc.com/products/mn4004-antigravity-type-4-6s-uav-motor-kv300-kv400-2pcs-set"
  ]
 },
 "tmotor_p15x5_par": {
  "massa_g_por_pa": 21,
  "preco_usd": 55.9,
  "preco_usd_faixa": [
   40,
   55.9
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://shop.tmotor.com/collections/uav-propeller",
   "https://www.ligpower.com/product/15x5-polish-carbon-fiber-propelller.html"
  ]
 },
 "tmotor_air40a_esc": {
  "massa_g": 70,
  "preco_usd": 39.99,
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.foxtechfpv.com/tmotor-air-40a-esc-p-1803.html",
   "https://unmannedrc.com/products/air-40a-2-6s-multi-rotor-uav-drone-esc"
  ]
 },
 "rpi5_4gb": {
  "preco_usd": 85,
  "preco_usd_retalho": 110,
  "preco_brl": 780,
  "confianca": "A",
  "fontes": [
   "https://www.tomshardware.com/raspberry-pi/component-shortages-drive-raspberry-pi-prices-up-by-up-to-23-percent-escalating-lpddr4-lpddr5-costs-trigger-the-third-price-hike-of-the-year",
   "https://www.canakit.com/raspberry-pi-5-4gb.html",
   "https://loja.idflux.com/produtos/raspberry-pi-5-4gb-model-b-anatel"
  ]
 },
 "rpi_active_cooler": {
  "dims_mm": [
   63.5,
   42.5,
   13.7
  ],
  "massa_g": 28,
  "preco_usd_faixa": [
   6,
   15
  ],
  "preco_brl": null,
  "confianca": "A (preco) / M (massa)",
  "fontes": [
   "https://www.pishop.us/product/raspberry-pi-active-cooler",
   "https://pip.raspberrypi.com/documents/RP-008188-DS-active-cooler-product-brief.pdf",
   "https://www.robotics.org.za/W25939"
  ]
 },
 "fc_h743_30x30": {
  "opcoes": {
   "matek_h743_mini_v3": [
    84.49,
    97.24
   ],
   "matek_h743_slim_v3": 116.49,
   "holybro_kakute_h7_v1_5": [
    55,
    62
   ]
  },
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.lumenier.com/products/mateksys-h743-mini-v3-flight-controller",
   "https://www.racedayquads.com/products/matek-h743-slim-30x30-flight-controller",
   "https://holybro.com/products/kakute-h7"
  ]
 },
 "rpi_camera_module_3_wide": {
  "preco_usd_lancamento": 35,
  "preco_usd_faixa": [
   37.95,
   45.05
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.canakit.com/raspberry-pi-camera-module-3.html",
   "https://www.adafruit.com/product/5658",
   "https://www.cnx-software.com/2023/01/23/raspberry-pi-camera-module-3-review-hdr-autofocus-wide-angle-and-noir-camera"
  ]
 },
 "pmw3901": {
  "preco_usd_faixa": [
   20.59,
   32.05
  ],
  "preco_gbp_pimoroni": 20.7,
  "preco_brl": 54.38,
  "confianca": "M",
  "fontes": [
   "https://holybro.com/products/pmw3901-optical-flow-sensor",
   "https://thepihut.com/products/pmw3901-optical-flow-sensor-breakout",
   "https://produto.mercadolivre.com.br/MLB-5060650115-modulo-de-sensor-de-fluxo-optico-pmw3901-translaco-xy-de-_JM"
  ]
 },
 "vl53l1x_pololu_3415": {
  "preco_usd": 19.95,
  "preco_usd_faixa": [
   19.95,
   24.04
  ],
  "preco_brl": null,
  "confianca": "M",
  "fontes": [
   "https://www.pololu.com/product/3415",
   "https://www.tme.eu/en/details/pololu-3415/distance-sensors/pololu/vl53l1x-time-of-flight-distance-sensor"
  ]
 },
 "ina226_modulo": {
  "preco_usd_faixa": [
   0.88,
   2.05
  ],
  "preco_brl": 37,
  "confianca": "A",
  "fontes": [
   "https://www.aliexpress.com/item/1005005890074659.html",
   "https://lista.mercadolivre.com.br/ina226"
  ]
 },
 "molicel_p50b": {
  "dims_mm": {
   "diam": 21.55,
   "altura": 70.15
  },
  "preco_usd": 10.5,
  "preco_usd_faixa": [
   8.99,
   13.99
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://liionwholesale.com/products/molicel-npe-inr-21700-p50b-60a-5000mah-flat-top-21700-battery-authorized-distributor",
   "https://www.batteryjunction.com/products/molicel-inr21700-p50b",
   "https://imrbatteries.com/products/molicel-21700-p50b-5000mah-60a-battery"
  ]
 },
 "fita_niquel_0_15x8_m": {
  "preco_usd_m_faixa": [
   0.9,
   3.1
  ],
  "preco_brl": null,
  "confianca": "B",
  "fontes": [
   "https://sequremall.com/products/nickel-strip",
   "https://www.walmart.com/c/kp/nickel-strip"
  ]
 },
 "xt90_par": {
  "preco_usd_par": 5.99,
  "preco_usd_par_lote5": [
   0.85,
   1.2
  ],
  "preco_brl_par": [
   14,
   16
  ],
  "confianca": "A",
  "fontes": [
   "https://www.buddyrc.com/products/amass-anti-spark-xt90-female-and-male-connector-set",
   "https://sologood.net/products/amass-5-pairs-xt90-xt-90-male-female-bullet-connectors-power-plugs-for-rc-lipo-battery-motor",
   "https://lista.mercadolivre.com.br/xt90-macho"
  ]
 },
 "jst_xh_7p": {
  "preco_usd_un": 0.22,
  "preco_brl_par": [
   2.8,
   5.8
  ],
  "confianca": "M",
  "fontes": [
   "https://www.aliexpress.com/item/1005007020576153.html",
   "https://www.mercadolivre.com.br/3-pares-conector-jstxh-balanceamento--bateria-2s--3vias/up/MLBU5243376276"
  ]
 },
 "fio_silicone_10awg_m": {
  "diam_externo_mm": 5.4,
  "preco_usd_m_faixa": [
   5.99,
   9.99
  ],
  "preco_brl_m_faixa": [
   10.8,
   39
  ],
  "confianca": "A",
  "fontes": [
   "https://www.getfpv.com/accessories-390/wire.html",
   "https://www.avidrc.com/product/p/2962/10awg-Silicone-Wire-Black-1-Meter",
   "https://www.proelis.com.br/cabo-cofisil-10awg-200c-600v.php",
   "https://lista.mercadolivre.com.br/fio-de-silicone-10-awg"
  ]
 },
 "fio_silicone_14awg_m": {
  "preco_usd_m_faixa": [
   1.99,
   2.99
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.getfpv.com/silicone-wire-14awg-1mtr.html",
   "https://www.readymaderc.com/products/details/premium-silicone-wire-14ga-red-1m"
  ]
 },
 "fio_silicone_16awg_m": {
  "preco_usd_m_faixa": [
   2.99,
   4.99
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.getfpv.com/silicone-wire-16awg-1mtr.html",
   "https://exceleraterc.com/16-awg-silicone-wire-1-meter"
  ]
 },
 "fio_silicone_20awg_m": {
  "preco_usd_m_faixa": [
   0.99,
   4.4
  ],
  "preco_brl": null,
  "confianca": "B",
  "fontes": [
   "https://www.readymaderc.com/products/details/premium-silicone-wire-20ga-red-1m",
   "https://www.diyfpv.com/product/20awg-silicone-wire-1-foot"
  ]
 },
 "abracadeira_2_5x100_100un": {
  "preco_usd_faixa": [
   1,
   3
  ],
  "preco_brl_faixa": [
   18.5,
   25.38
  ],
  "confianca": "M",
  "fontes": [
   "https://constructionproducts.co.nz/products/cable-ties-2-5x100mm-black",
   "https://www.mercadolivre.com.br/abracadeira-nylon-verde-25-x-100-mm-enforca-gato-100-unidades/p/MLB24430760"
  ]
 },
 "abracadeira_3_6x150_100un": {
  "massa_g_100un": 75,
  "preco_usd_faixa": [
   1.76,
   3.0
  ],
  "preco_brl": null,
  "confianca": "M",
  "fontes": [
   "https://www.ferrulesdirect.com/products/cti150b",
   "https://global.microless.com/product/cable-zip-tie-150mm-x-3-6mm-plastic-high-tensile-strength-durable-pack-of-100-white-zip-tie?currency=usd"
  ]
 },
 "tubo_cf_25x23_1m": {
  "dims_mm": {
   "ext": 25,
   "int": 23,
   "comprimento": 1000
  },
  "massa_g_m": 113.1,
  "preco_usd_faixa": [
   32.89,
   39.09
  ],
  "preco_brl": 270,
  "confianca": "A",
  "fontes": [
   "https://carbonkevlarsupply.com/products/copy-of-blue-black-carbon-fiber-tubing-25mm-x-23mm-x-500mm-3k-roll-wrapped-glossy",
   "https://windcatcherrc.com/product/3k-carbon-fiber-tube-25mm-x-23mmx-1000mm-matte-finish",
   "https://www.mercadolivre.com.br/tubo-fibra-de-carbono-3k-25mm-ext-e-23mm-int-x-100cm-1-metro/up/MLBU3112125701"
  ]
 },
 "tubo_cf_16x14_1m": {
  "dims_mm": {
   "ext": 16,
   "int": 14,
   "comprimento": 1000
  },
  "massa_g_m": 74.2,
  "preco_usd_faixa": [
   16.28,
   37.25
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://windcatcherrc.com/product/carbon-fiber-tube-16mm-x-14mm-x-1000mm",
   "https://www.easycomposites.us/16mm-woven-finish-carbon-fiber-tube"
  ]
 },
 "tubo_cf_12x10_1m": {
  "dims_mm": {
   "ext": 12,
   "int": 10,
   "comprimento": 1000
  },
  "massa_g_m_calc": 54,
  "preco_usd_faixa": [
   10.86,
   13.99
  ],
  "preco_brl": null,
  "confianca": "A (preco) / calculado (massa)",
  "fontes": [
   "https://windcatcherrc.com/product/carbon-fiber-tube-12mm-x-10mm-x-1000mm",
   "https://superstitionhobbies.com/products/cft1281-carbon-fiber-tube-12mm-x-10mm-x-1000mm"
  ]
 },
 "malha_pet_m": {
  "preco_usd_m_faixa": [
   0.34,
   0.56
  ],
  "preco_brl": null,
  "confianca": "M",
  "fontes": [
   "https://buyheatshrink.com/techflex-flexo-pet-colored-braided-cable-sleeving"
  ]
 },
 "termo_retratil_kit": {
  "preco_usd_faixa": [
   9.99,
   19.99
  ],
  "preco_brl_faixa": [
   25.83,
   38.9
  ],
  "confianca": "A",
  "fontes": [
   "https://www.servocity.com/heat-shrink-tubing-560pc-assortment-pack",
   "https://www.mercadolivre.com.br/kit-espaguete-termo-retratil-780-pc-colorido-fios-cabos/up/MLBU4246534282"
  ]
 },
 "fita_bateria_15mm": {
  "dims_mm": [
   250,
   15,
   1.8
  ],
  "preco_usd_pack3": 7.99,
  "preco_usd_un": 2.66,
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.foxeer.com/foxeer-1-8mm-thickness-silicon-durable-battery-strap-3pcs-250-15mm-g-359"
  ]
 }
}
```

---

## Parte 2 — Novo ombro: atuador linear de fuso trapezoidal acionado por motorredutor — peças, medidas e números (pesquisa 2026-10-20)

**Regras:** só a CLI Tavily (~60 consultas/extrações), conteúdo web = dado não confiável (citado, nunca seguido), confiança **A** (fabricante/datasheet ou ≥ 2 fontes concordantes) · **M** (uma fonte ou faixa) · **B** (anúncio genérico/inferência). Valores **calculados** estão marcados. Câmbio do relatório anterior: **US$ 1 = R$ 5,05**.

---

### 1. Motorredutor JGB37-520 com encoder Hall (12 V e 24 V)

#### 1a. Geometria (para o 3D)

| item | valor | fonte | conf. |
|---|---|---|---|
| Redutor | Ø **37 mm**; comprimento L por relação: **19 mm** (1:6,25–1:10) · **21 mm** (1:18,8–1:30) · **24 mm** (1:50–1:90; 1:56 = 24 mm) · **26,5 mm** (1:131–1:169) · **29 mm** (1:506) | https://nfpmotor.com/37mm-metal-gear-motor-model-nfp-gm37-520-en · https://www.ram-e-shop.com/shop/dc-jgb37520-self-balance-12v-jgb37-520-self-balancing-geared-motor-12vdc-107-rpm-torque-4-8-kg-cm-with-hall-encoder-9322 · https://www.openimpulse.com/blog/products-page/37d-gearmotors/jgb37-520-dc-gearmotor-12-rpm-12-v | A |
| Motor | Ø **33 mm** × **22–22,7 mm** de corpo (anúncios); conjunto com encoder ≈ **53 mm** de comprimento total sem veio para 1:30 (RobotShop "37 × 33 × 53 mm") | https://probots.co.in/jgb37-520-dc12v-66rpm-miniature-speed-reduction-gear-dc-motor.html · https://www.robotshop.com/products/aslong-motor-37mm-diameter-12v-200rpm-brushed-dc-gear-motor-w-encoder · https://www.alibaba.com/product-detail/JGB37-520-gearboxes-37mm-diameter-gear_1600639088222.html | M |
| Encoder (tampa) | comprimento próprio **não encontrado** (≈ 9 mm se 53 = 21 + 22,7 + tampa — inferência, B); disco magnético de **11 PPR** no motor, AB, 3,3–5 V; conector **PH2.0-6P** (Hiwonder) ou **XH2.54-6P** (outros) | https://www.hiwonder.com/products/hall-encoder-dc-geared-motor · https://www.amazon.com/building-JGB37-520-XH2-54-6PIN-Connector-Automatic/dp/B0C1B1JJ3N | A (encoder) / B (comprimento) |
| Veio de saída | Ø **6 mm em D**, **excêntrico** (fora do centro do redutor; valor do desvio **não encontrado**); **15 mm** de comprimento com **11,5 mm** de corte em D (5,5 mm no plano); versões com encoder vendidas com veio de **21–21,5 mm** | https://probots.co.in/jgb37-520-dc12v-7-rpm-miniature-speed-reduction-gear-dc-motor.html · https://www.amazon.com/JGB37-520-6v12v24v-XH2-54-6PIN-Connector-Automatic/dp/B0CH6B6VZS · https://dynamic.me/dc-motor-with-gearbox-and-encoder-jgb-37-520-12-v-178-rpm | A (Ø, corte) / M (comprimento) |
| Face frontal | **6 × M3 roscados** em círculo; face Ø31 mm com ressalto central Ø12 mm; **Ø do círculo de furos não encontrado** | https://probots.co.in/jgb37-520-dc12v-66rpm-miniature-speed-reduction-gear-dc-motor.html · https://ja.manuals.plus/m/1d7abd51b8cde5600ef8c45e658f07bbc789d3b88c49ea2ffdf961a3649ad398 | M |
| Massa com encoder | **144–196 g** (152 ± 1 g Hiwonder; 158 g 1:56; 144–170 g NFP; 196 g com veio de 21,5 mm) | Hiwonder · ram-e-shop · https://precisionminidrives.com/product/37mm-gear-motor-with-encoder-41mm-type-model-nfp-jgb37-520-en · dynamic.me | A |

#### 1b. Desempenho por relação (há **dois enrolamentos de 12 V** no mercado: "padrão" ≈ 1,2 A de bloqueio e "rápido" 2,4–3,9 A)

| relação | 12 V padrão: vazio rpm · nominal kg·cm @ A · bloqueio kg·cm @ A | 12 V rápido: vazio · bloqueio kg·cm @ A | 24 V: vazio · bloqueio kg·cm @ A | PPR na saída (11 × i) |
|---|---|---|---|---|
| 1:18,8 | 319 · 0,48 @ 0,2 · **1,9 @ 1,2** | 530 · 2,6 @ 2,4 | 319 · (0,15 — erro tipográfico da fonte) @ 0,8 | 207 |
| 1:30 | 200 · 0,75 @ 0,2 · **3,0 @ 1,2** (OpenImpulse 1,8) | 320–333 · 4,0–5,8 @ 2,4–3,2 | 200 · **2,4 @ 0,8** | 330 |
| 1:56 | 107 · 1,2 @ 0,2 · **4,8 @ 1,2** (OpenImpulse 3) | 170–178 · 7,2–9,2 @ 2,4–3,2 (1:60 Hiwonder) | 107 · **4 @ 0,8** | 616 |
| 1:90 | 66 · 2,0 @ 0,2 · **8 @ 1,2** (OpenImpulse 5) | 110 · 12–15 @ 2,4–3,2 | 66 · **7 @ 0,8** | 990 |
| 1:131 | 45 · 2,7 @ 0,2 · **10,8 @ 1,2** (OpenImpulse 7) | 76 · 15,6 @ 2,4 | 45 · **10 @ 0,8** | 1441 |
| 1:168–169 | 35 · 3,4 @ 0,3 · **13,6 @ 1,2** (OpenImpulse 10) | 60 · 20 @ 2,4 | 35 · **13 @ 0,8** | 1859 |
| 1:270 / 1:506 / 1:810 | 22 / 12 / 7 · bloqueio 16 / 30 / 48 @ 1,2 | — | 22 / 12 / 7 · bloqueio **20 / 40 / 64** @ 0,8 | 2970 / 5566 / 8910 |
| corrente em vazio | 0,05–0,1 A | 0,15 A | 0,03–0,1 A | — |
| binário nominal a 24 V | — | — | **não encontrado** (só bloqueio; GrabCAD: versão 7 rpm "16 kg·cm de carga") | — |

Fontes: https://precisionminidrives.com/product/37mm-gear-motor-with-encoder-41mm-type-model-nfp-jgb37-520-en (tabelas 12 V "padrão" e "rápido") ·
https://www.openimpulse.com/blog/jgb37-520-gearmotor-selector (12 V e 24 V, bloqueio) · https://www.hiwonder.com/products/hall-encoder-dc-geared-motor (1:20/30/60/90 com 3,2–3,9 A) ·
https://www.openimpulse.com/blog/products-page/37d-gearmotors/jgb37-520-dc-gearmotor-960-rpm-24-v (24 V: 100 mA vazio, 0,8 A bloqueio) · https://grabcad.com/library/jgb37-520-1 — confiança **A** nas tabelas; as duas fontes divergem até ~40 % no bloqueio (usar a mais baixa). PPR na saída: NFP lista 330 (1:30) e 990 (1:90); as restantes são **cálculo** 11 × i (×4 em quadratura).

| item | valor | fonte | conf. |
|---|---|---|---|
| **Limite do redutor** | **20–25 kg·cm** (NFP "max torque 21 kg·cm"; anúncio "max load 20 kgf·cm"; Alibaba "max 25 kg/cm") → os bloqueios de 30–64 kg·cm (1:506/1:810) **excedem o redutor** | https://precisionminidrives.com/product/37mm-diameter-miniature-dc-gear-motor-nfp-jgb37-520-dc-6v-12v-24v · https://www.aliexpress.com/item/1005006803196520.html · https://www.alibaba.com/product-detail/JGB37-520-gearboxes-37mm-diameter-gear_1600639088222.html | M |
| Preço USD (com encoder) | **US$ 7,36–21,45** (AliExpress 10,72–15,8 típicos); Hiwonder **US$ 12,99**; OzRobotics 22 | https://www.aliexpress.com/item/1005007204535740.html · https://www.aliexpress.com/item/4001339371886.html · https://www.hiwonder.com/products/hall-encoder-dc-geared-motor | A |
| Preço Brasil | JGB37-520 c/ encoder: anúncios **indisponíveis**; JGB37-545 c/ encoder **R$ 76,70**; JGB37-3530 c/ encoder R$ 343,35 | https://produto.mercadolivre.com.br/MLB-4927626223-motor-redutor-de-encoder-cc-jgb37-545-6v-12v24v-motor-cc-de-_JM · https://www.mercadolivre.com.br/12v-24v-37mm-high-torque-gear-motor-jgb37-520-encoder-resdi/p/MLB2085040289 | B |

---

### 2. Fuso trapezoidal T8 de 1 entrada (Tr8×2) e porcas

| item | valor | fonte | conf. |
|---|---|---|---|
| Existe à venda? | **Sim.** "Tr8x2 / T8 lead 2 mm, 1 start" (diferente do comum T8×8 de 4 entradas, passo 2 mm, avanço 8 mm): Fabreeko (370/470 mm), ReliaBot (150/300/370 mm), VXB (100 mm), KB-3D (porcas), robotics.org.za | https://www.fabreeko.com/products/tr8x2mm-lead-screws-for-ender-5-pro-and-ender-5-plus · https://www.amazon.com/ReliaBot-Tr8x2-Screw-Printer-Machine/dp/B07QZ159VV · https://vxb.com/products/tr8x2-lead-screws-set-of-2-100mm-stainless-steel-w · https://www.reddit.com/r/3Dprinting/comments/12vh067/difference_between_tr8x2_and_t8x2_lead_screw | A |
| Geometria Tr8×2 | **não está na tabela DIN 103** (o normalizado é Tr8×1,5). Pelas fórmulas DIN 103 (que reproduzem a linha Tr9×2 = 8 / 9,5 / 6,5 / 7): **d2 = 7,0 mm**, núcleo do fuso **d3 = 5,5 mm**, núcleo da porca D1 = 6,0 mm, fundo da porca D4 = 8,5 mm (cálculo) | https://www.bornemann-gewindetechnik.de/en/products/trapezoidal-threads/data · https://www.fasten.it/en/norms/norm/din_103 | A (regra) / calc. |
| Comprimentos de venda | 100, 150, 200, 300, 370, 400, 470, 500, 600 mm e até 1200 mm | fontes acima · https://lista.mercadolivre.com.br/fuso-trapezoidal-tr8-2mm | A |
| Massa por 100 mm | **~30–33 g** (T8 inox 300 mm = 91 g; Tr8 passo 2 de 1200 mm = 395 g com porca) — mesmo perfil de passo 2 mm | https://www.gobilda.com/3501-series-lead-screw-8mm-lead-4-start-300mm-length · https://www.robotics.org.za/TR8X8-P2-L1200 | M |
| Preço USD | 2 × 100 mm + porca **US$ 4,50**; eBay T8×2 **US$ 8,25–11,98**; porca avulsa US$ 3,49 (KB-3D) | https://jacourgentcare.com/products/2pcs-100mm-tr8x2-lead-screw-t8-brass-nut-2mm-pitch-1-start-2/250318010 · https://www.ebay.com/shop/t8-leadscrew?_nkw=t8+leadscrew · https://kb-3d.com/store/motion/600-tr8x2-1-start-lead-screw-nut-multiple-types-1634424201379.html | M |
| Preço Brasil | Tr8 passo 2 × 600 mm **com castanha R$ 60,80**; × 500 mm inox + castanha latão **R$ 117–130**; kit 3 × 500 mm sem castanha R$ 128,66; castanha de latão passo 2 avulsa **R$ 28** | https://www.mercadolivre.com.br/fuso-trapezoidal-tr8-500mm--porca-anti-folga-tr8-passo-2mm/up/MLBU2220446293 · https://www.mercadolivre.com.br/fuso-trapezoidal-t8-tr8-500mm-inox--castanha-escolher-passo/up/MLBU3236437180 · https://lista.mercadolivre.com.br/fuso-trapezoidal-tr8-2mm | A |
| **Porca de latão de flange T8** | flange **Ø22 × 3,5 mm** (3,3 noutra), corpo **Ø10,2 mm**, altura total **15 mm**, **4 furos Ø3,5 mm** num círculo de **Ø16 mm** (desenho eBay: A22 · B16 · C3,3 · D10 · E10,2 · F3,7) | https://www.amazon.com/MECCANIXITY-Screw-Trapezoidal-Pitch-Printer/dp/B09QSBXDYP · https://www.robotics.org.za/THSL-300-8D · https://www.ebay.com/itm/262531657553 | A |
| Massa da porca | **não encontrado**; ≈ **13 g** por cálculo (latão 8,5 g/cm³, geometria acima) | — | calc. |
| Carga axial admissível | **não encontrado** em ficha; ≈ **1,6–2,9 kN** por cálculo de pressão de contacto (aço/bronze, baixa velocidade, p = 10–17,5 MPa; 7,5 filetes × π·7 mm × 1 mm de flanco) — o latão é mais fraco que o bronze | https://vpmpme.files.wordpress.com/2018/07/ch-02_power-screw.pdf · https://www.mechanixcalc.com/powerscrew | B / calc. |
| Porca **POM anti-folga** (mola) | flange Ø22, furos para M3 em Ø16, comprimento 25 mm (versão latão), ~25 g; mola 40 mm; existe em passo 2 mm (1 entrada); **€ 3,30–4,61**; 2 un US$ 7,40 | https://www.olelectronics.com/product/t8-anti-backlash-spring-loaded-nut-for-8mm-lead-screw · https://stelltron.co.za/product/t8-anti-backlash-spring-loaded-nut · https://deluxcnc.eu/en/sliding-screws/922-pom-anti-backlash-spring-loaded-nut-t8.html · https://www.walmart.com/ip/WSTEER-2pcs-T8-Anti-Backlash-Spring-Loaded-Nut-Elimination-Gap-POM-Nut-8mm-Lead/13144107498 | M |
| Atrito aço/latão | **seco 0,15–0,35**; **lubrificado (óleo) 0,10–0,19** (Shigley/amesweb: 0,15–0,19 seco, 0,10–0,15 óleo; Roton: 0,35 seco, 0,19 lubrificado); aço/bronze 0,10–0,16 com óleo | https://amesweb.info/screws/screw-nut-collar-friction-table.aspx · https://www.roton.com/screw-university/screw-actions · https://www.firgelliauto.com/blogs/engineering-calculators/lead-screw-efficiency-back-driving-calculator | A |
| **Autobloqueio** | **Sim** para 1 entrada ("single-start trapezoidal lead screws are self-locking" — igus; regra: avanço < d/3). **Cálculo:** λ = atan(2 / π·7) = **5,20°**; autobloqueia se μ > tan λ · cos 15° = **0,088** → garantido em seco (0,15–0,35) e com óleo (0,10–0,19), mas com **pouca margem bem lubrificado** e pode deslizar com vibração. O T8×8 (λ = 20,0°, μ crítico 0,35) **não** autobloqueia | https://blog.igus.eu/self-locking-what-is-it · https://www.linearmotiontips.com/how-to-determine-if-a-screw-will-back-drive · https://forum.duet3d.com/topic/16660/lead-screw-pitch-any-thoughts | A (qualitativo) / calc. |
| Rendimento e binário (cálculo) | a subir, sem colar: **η ≈ 0,46** (μ 0,10) · **0,36** (μ 0,15) · 0,31 (μ 0,19); binário para 100 N de carga: **0,069–0,088 N·m** (0,70–0,89 kg·cm) | fórmulas de parafuso de potência (Shigley) | calc. |

---

### 3. Acoplamento flexível 6 → 8 mm e apoio do fuso

| item | valor | fonte | conf. |
|---|---|---|---|
| Acoplamento 6 × 8 mm | alumínio, **Ø19 × 25 mm** (helicoidal ou garras); massa **~16 g** (D19 × L25 5 × 6, mesma carcaça) | https://www.harfington.com/products/p-1120197 · https://www.jsumo.com/flexible-aluminum-coupling-5mm-to-6mm-hole · https://www.electric-b2c.com/products/d19-l25-aluminium-flexible-jaw-shaft-coupling-5-8-6-35mm-8mm-10mm-cnc-stepper-motor-coupler-encoders-engraving-machine | A (dims) / M (massa) |
| Preço | **US$ 3,06/un** (5 por 15,29, Walmart) – 10,66; Brasil: só em kits (Tr8 600 mm + acoplamento 6,35 × 8 **R$ 102,59–107,99**); avulso **não encontrado** | https://business.walmart.com/ip/5-Packs-Aluminum-Alloy-Shaft-Coupling-6mm-to-8mm-Flexible-Coupling-Motor-Connector-Joint-L25xD19/8862351186 · https://lista.mercadolivre.com.br/fuso-trapezoidal-8mm-passo-2-mm | M |
| **KP08** (mancal de pé) | **55 × 13 × 28–30 mm**, furo 8 mm, **2 furos a 42 mm**, Ø4,5–5 mm; zamak; **35–40 g** (70 g Mädler) | https://www.makerstore.com.au/product/bear-kp08 · https://www.robotics.org.za/KP08 · https://www.amazon.com/HiPicco-Pillow-Bearing-Mounted-Bearings/dp/B0C7111NKG · https://maedlernorthamerica.com/partshop/ball-pillow-block-bearing-kp-08-bore-8mm-material-zinc-die-cast-pn-62560800 | A |
| **KFL08** (flange losango) | **47–48 × 27 × 11–12,5 mm**, **2 furos a 36–37 mm**, Ø4,8–5,3 mm; **20–29 g** (50 g Mädler) | https://www.makerstore.com.au/product/bear-kfl08 · https://www.diyelectronics.co.za/store/rod-end-mounted-bearings/1666-8mm-flange-pillow-block-bearing-kfl08.html · https://electropeak.com/kfl-08-3d-printer-bearing · https://www.traceparts.com/en/product/madler-ball-flange-bearings-kfl-and-sskfl-light-series?CatalogPath=TRACEPARTS%3ATP01002002003001&Product=90-11032024-041760 | A |
| Preços KP08/KFL08 | KP08 € 1,04–1,17 (10+, Olimex) – € 6,60; KFL08 US$ 8,11 (Walmart); **Brasil: KFL08 R$ 18/un, 2 un R$ 36,93, 6 un R$ 78,99; KP08 4 un R$ 44,88** | https://olimex.com/Products/Robot-CNC-Parts/Bearings/KP08 · https://www.walmart.com/ip/tooloflife-Zinc-Alloy-Pillow-Block-Bearing-Flange-Block-Bearing-KFL08-KFL000-KFL001-KFL002/954825154 · Mercado Livre (busca "mancal KFL08 KP08 8mm") | M |
| 608ZZ em bloco impresso | **Confirmado como prática comum** (suporte superior do fuso T8 com 608ZZ em Ender 3 / P3Steel); 608ZZ = 8 × 22 × 7 mm, 12–13 g (relatório anterior) | https://www.thingiverse.com/thing:3049406 · https://www.printables.com/model/155188-p3steel-top-lead-screw-holder-with-608zz | A |

---

### 4. Pivôs: parafusos de ombro e rolamentos de 4 mm

| item | valor | fonte | conf. |
|---|---|---|---|
| ISO 7379 **M5** | ombro **Ø6,0 mm f9** (fornecedores) — a tabela ISO publicada indica **Ø6,5**; cabeça Ø10 × 4,5 mm; sextavado 3 mm; rosca 9,5 mm | https://www.woodstockindustrial.com/specs/iso-7379 · https://fullerfasteners.com/tech/iso-7379-specifications-hex-socket-head-shoulder-screws · https://accu-components.com/us/metric-socket-shoulder-screws/10470-SSH-M5-25-12-9 | M (Ø do ombro diverge) |
| Ombro **Ø5 / M4** (extensão "ISO 7379-5-M4") | cabeça **Ø8** (AMPG: 9) × **4 mm**; sextavado **2,5 mm**; rosca **5–8 mm** | https://www.accu.co.uk/metric-socket-shoulder-screws/10391-SSH-M4-30-A2 · https://ampg.com/wp-content/uploads/2022/12/AMPG-Shoulder-Screws-catalog.pdf · https://www.tme.com/us/en-us/details/iso7379-5-m4-10/shoulder-screws/elesa-ganter/iso-7379-5-m4-10 | A |
| Preços | Elesa ISO 7379-5-M4-10 (aço) **US$ 4,40 / 10 un**; M4 × Ø5 (10 un) desde US$ 8,95; inox M5/Ø6 US$ 3,28–4,65/un; Brasil: ISO 7379 **não encontrado** (só kits genéricos "ressalto 3 mm" R$ 24–35 por 4) | TME · https://www.instockfasteners.com/SearchResultsxhtmlsubcategoryid~105/criteria~1%7C94%7C/mea~2/plnk~1/search~2 · https://www.asmc.net/m5-x-m4-x-10-mm-coarse-thread-iso-7379-socket-shoulder-screw-stainless-steel-18-8 · https://maedlernorthamerica.com/partshop/shoulder-screw-similar-to-iso-7379-o6f9-m5-10mm-stainless-steel-1-4301-pn-619806010 | M |
| **MR84ZZ** | **4 × 8 × 3 mm**, **0,56–1 g**; 7 esferas Ø1,2 mm; 60 000 rpm | https://www.lily-bearing.com/products/mr84zz · https://www.123bearing.com/bearing-housing/deep-groove-bearing/single-row/mr-84-zz-ezo · https://www.smbbearings.com/firebrick/ckeditor/plugins/upload/Uploads/Documents/bearingpdfs/MR84ZZ-miniature-bearing-4x8x3mm.pdf | A |
| **684ZZ** | **4 × 9 × 4 mm**, **1,0 g**; C = **545 N**, C0 = **182 N**; 7 esferas Ø1,588 | https://www.fitrunbearing.com/product/684zz · https://www.tradebearings.com/684zz-miniature-bearing-4x9x4mm-product-196619.html | A |
| Preços | MR84ZZ **10 un US$ 9,49–9,99** (≈ US$ 1/un; Lily 1,15/un); 10 un sortidos (MR83/84/85) US$ 9,84; Brasil **não encontrado** | https://www.walmart.com/ip/MR84ZZ-Deep-Groove-Ball-Bearings-4mmx8mmx3mm-Double-Shielded-Chrome-Steel-P6-10pcs/189441676 · https://www.ebay.com/itm/116606390931 · https://www.aliexpress.com/item/4000021355060.html | A |

---

### 5. Drivers de motor DC para 2–5 A de bloqueio a 12–24 V

| item | valor | fonte | conf. |
|---|---|---|---|
| **DRV8871** (Adafruit 3190) | 24,4 × 20,4 × 9,7 mm, **2,2 g**, 6,5–45 V, 3,6 A pico, **US$ 7,50** (relatório anterior). Limite **I_TRIP (A) = 64 / R_ILIM (kΩ)**: placa vem com **30 kΩ → 2,13 A**; mínimo 15 kΩ → 4,2 A; ~2 A contínuos na prática. RθJA **41,1 °C/W** (placa JEDEC), R_DS(on) 565 mΩ (alto + baixo), proteções de sobrecorrente/térmica/UVLO | https://www.electrokit.com/upload/quick/6e/fa/0033_manual.pdf · https://forums.adafruit.com/viewtopic.php?t=204053 · https://download.mikroe.com/documents/datasheets/drv8871.pdf · https://forums.adafruit.com/viewtopic.php?t=223305 | A |
| DRV8871 com JGB37-520 **24 V** a bloquear | **Sim, com folga**: bloqueio 0,8 A < 2,13 A; dissipação 0,8² × 0,565 ≈ **0,36 W → +15 °C** (cálculo). Com o JGB37-520 **12 V "rápido"** (2,4–3,9 A) o chip fica a limitar a 2,13 A: ≈ 2,6 W → **+105 °C** (perto do corte térmico; não sustentável) | cálculo com os dados acima | calc. |
| **Pololu G2 18v17** | **33 × 20,3 mm** (1,3″ × 0,8″), **3,3 g**, 6,5–30 V, **17 A contínuos** sem dissipador, sensor de corrente e limite configurável; **US$ 44,95** | https://www.pololu.com/product/2991 · https://www.robotics-3d.com/controllo-motori/8903-pololu-g2-high-power-motor-driver-18v17.html · https://www.pololu.com/product/3751 (tabela de preços) | A |
| **Pololu G2 24v13** | **33 × 20,3 mm**, **3,3 g**, 6,5–40 V (28 V nominal), **13 A contínuos**; **US$ 44,95** | https://www.pololu.com/product/2992/specs · https://www.pololu.com/product/3751 | A |
| BTN8982 | CI meia-ponte 50 A (5,5–40 V) **US$ 3,48–6,27** (Mouser); shield Infineon (2 × BTN8982TA) **€ 18,48**, 35 g brutos; módulo genérico: medidas/massa **não encontrado** | https://www.mouser.com/en/ProductDetail/Infineon-Technologies/BTN8982TA?qs=y2kkmE52mdPcPfXmFEmVng%3D%3D · https://www.digikey.at/en/products/detail/infineon-technologies/DCMOTORCONTRBTN8982TOBO1/5878319 · https://www.tme.com/au/en/details/kit-mtctr-btn8982/development-kits-others/infineon-technologies/dcmotorcontrbtn8982t0b01 · https://www.jsumo.com/btn8982-half-bridge-dc-motor-driver-50a | M |
| "IBT-2" | é o **BTS7960** (não o BTN8982): 50 × 50 × 43 mm, **54–66 g**, 43 A (relatório anterior) | https://electropeak.com/bts7960-43a-high-power-motor-driver-module | A |

---

### 6. UBEC para 6S com ≥ 8 A para 4–8 servos DS3218MG

**Atenção:** o DS3218MG é especificado para **4,8–6,8 V** — 7,2/7,4 V já **passam do máximo da ficha**. Nenhum dos UBEC de saída fixa oferece 6,8 V; o único com ajuste fino é o Castle (passos de 0,25 V → 6,75 V).

| UBEC | entrada | saídas | contínuo / pico | dimensões | massa | preço | fonte | conf. |
|---|---|---|---|---|---|---|---|---|
| **Hobbywing UBEC 10A V2 (2–6S)** | 6–25,2 V | 6,0 / 7,4 / 8,4 V | **10 A / 15 A** | 45 × 20 × 16,2 mm | **34 g** | **US$ 24,99** (MAP) | https://www.hobbywingdirect.com/products/ubec-10a · https://www.readymaderc.com/products/details/hobby-wing-ubec-10a-v2 | A |
| Hobbywing UBEC 10A (versão 1, 2–6S) | 6–25,2 V | 5,0 / 6,0 / 7,4 / 8,4 V | 10 A / 20 A | 43,1 × 32,3 × 12,5 mm | 36 g | não encontrado | https://www.cmldistribution.co.uk/diagrams/HobbyWing/UBEC%2010A%202-6S%20Manual.pdf | A |
| Hobbywing UBEC 10A HV (3–14S) | 3–14S | 6,0 / 7,4 / 8,4 V | 10 A / 25 A | 55 × 25 × 12 mm | 35 g | não encontrado | https://www.hobbywing.com/en/products/ubec-10a-hv289 | A |
| **ZTW UBEC 8A G2** | 2–8S (7–34 V) | 5 / 6 / 7,4 / 8,4 V | 8 A / 15 A | 48–50 × 20–22 × 7 mm | **14 g** | **US$ 16,99–29,99** | https://motionrc.com/products/ztw-ubec-8a-g2-peak-15a-adjustable-output-voltage-external-bec-ztw3040011 · https://www.altitudehobbies.com/products/ztw-8a-external-bec-2-8s-ubec | A |
| **Holybro UBEC 12A** | 3–14S | 6,0 / 7,2 / 8,0 / 9,2 V | **12 A / 24 A** | 48 × 33,6 × 16,3 mm | 47,8 g | **US$ 36,59–36,99** | https://holybro.com/products/ubec-12a · https://www.flyingtech.co.uk/product/holybro-12a-ubec-15026 | A |
| Castle **CC BEC 2.0** | 2–14S | **4,75–12 V em passos de 0,25 V** | 10 A @ 5–6 V · 9 A @ 7,25–8,5 V · 15 A pico | não encontrado | 21–28 g | US$ 54,95–56,95 | https://www.manualslib.com/manual/1628799/Castle-Creations-Cc-Bec-2-0.html · https://www.offshoreelectrics.com/proddetail.php?prod=hh-cas-010-0153-00 | M |
| Hobbywing UBEC-8A-6S (só para comparação) | 2–6S | 5,2 / 6,0 V | 8 A / 15 A | 62 × 27,5 × 10 mm | 24,5 g | US$ 29,19 | relatório anterior | M |

Dimensionamento (cálculo, com o bloqueio de 1,8–2,6 A por DS3218): **4 servos** → até 7–10 A de pico (qualquer um dos três de cima, a 6,0 V); **8 servos** → até 14–21 A, acima do contínuo de todos — **Holybro 12A (24 A de pico)** ou **dois UBEC** (um por grupo de 4).

---

### Bloco JSON (valores legíveis por máquina)

Convenções: listas de 2 números = [mín, máx]; `null` = não encontrado; `*_calc` = calculado; câmbio 5,05.

```json
{
 "data_pesquisa": "2026-10-20",
 "cambio_usd_brl": 5.05,
 "jgb37_520_encoder": {
  "dims_mm": {
   "redutor_diam": 37,
   "redutor_comprimento_por_relacao": {
    "1:6.25-1:10": 19,
    "1:18.8-1:30": 21,
    "1:50-1:90": 24,
    "1:131-1:169": 26.5,
    "1:506": 29
   },
   "motor_diam": 33,
   "motor_comprimento": [
    22,
    22.7
   ],
   "total_sem_veio_1_30_com_encoder": 53,
   "encoder_tampa_comprimento": null,
   "veio": {
    "diam_D": 6,
    "plano_mm": 5.5,
    "comprimento": 15,
    "corte_D": 11.5,
    "comprimento_versoes_encoder": [
     21,
     21.5
    ],
    "excentrico": true,
    "desvio_mm": null
   },
   "face": {
    "furos": 6,
    "rosca": "M3",
    "diam_face": 31,
    "ressalto_central_diam": 12,
    "diam_circulo_furos": null
   }
  },
  "massa_g": [
   144,
   196
  ],
  "massa_g_tipica": 152,
  "encoder": {
   "ppr_motor": 11,
   "tensao_v": [
    3.3,
    5.0
   ],
   "conector": [
    "PH2.0-6P",
    "XH2.54-6P"
   ]
  },
  "por_relacao": {
   "1:18.8": {
    "ppr_saida": 207,
    "12v_padrao": {
     "rpm_vazio": 319,
     "nominal_kgcm": 0.48,
     "nominal_a": 0.2,
     "bloqueio_kgcm": 1.9,
     "bloqueio_a": 1.2
    },
    "12v_rapido": {
     "rpm_vazio": 530,
     "bloqueio_kgcm": 2.6,
     "bloqueio_a": 2.4
    },
    "24v": {
     "rpm_vazio": 319,
     "bloqueio_kgcm": null,
     "bloqueio_a": 0.8
    }
   },
   "1:30": {
    "ppr_saida": 330,
    "12v_padrao": {
     "rpm_vazio": 200,
     "nominal_kgcm": 0.75,
     "nominal_a": 0.2,
     "bloqueio_kgcm_faixa": [
      1.8,
      3.0
     ],
     "bloqueio_a": 1.2
    },
    "12v_rapido": {
     "rpm_vazio": [
      320,
      333
     ],
     "bloqueio_kgcm": [
      4.0,
      5.8
     ],
     "bloqueio_a": [
      2.4,
      3.2
     ]
    },
    "24v": {
     "rpm_vazio": 200,
     "bloqueio_kgcm": 2.4,
     "bloqueio_a": 0.8
    }
   },
   "1:56": {
    "ppr_saida": 616,
    "12v_padrao": {
     "rpm_vazio": 107,
     "nominal_kgcm": 1.2,
     "nominal_a": 0.2,
     "bloqueio_kgcm_faixa": [
      3.0,
      4.8
     ],
     "bloqueio_a": 1.2
    },
    "12v_rapido": {
     "rpm_vazio": [
      170,
      178
     ],
     "bloqueio_kgcm": [
      7.2,
      9.2
     ],
     "bloqueio_a": [
      2.4,
      3.2
     ]
    },
    "24v": {
     "rpm_vazio": 107,
     "bloqueio_kgcm": 4,
     "bloqueio_a": 0.8
    }
   },
   "1:90": {
    "ppr_saida": 990,
    "12v_padrao": {
     "rpm_vazio": 66,
     "nominal_kgcm": 2.0,
     "nominal_a": 0.2,
     "bloqueio_kgcm_faixa": [
      5,
      8
     ],
     "bloqueio_a": 1.2
    },
    "12v_rapido": {
     "rpm_vazio": 110,
     "bloqueio_kgcm": [
      12,
      15
     ],
     "bloqueio_a": [
      2.4,
      3.2
     ]
    },
    "24v": {
     "rpm_vazio": 66,
     "bloqueio_kgcm": 7,
     "bloqueio_a": 0.8
    }
   },
   "1:131": {
    "ppr_saida": 1441,
    "12v_padrao": {
     "rpm_vazio": 45,
     "nominal_kgcm": 2.7,
     "nominal_a": 0.2,
     "bloqueio_kgcm_faixa": [
      7,
      10.8
     ],
     "bloqueio_a": 1.2
    },
    "12v_rapido": {
     "rpm_vazio": 76,
     "bloqueio_kgcm": 15.6,
     "bloqueio_a": 2.4
    },
    "24v": {
     "rpm_vazio": 45,
     "bloqueio_kgcm": 10,
     "bloqueio_a": 0.8
    }
   },
   "1:168": {
    "ppr_saida": 1848,
    "12v_padrao": {
     "rpm_vazio": 35,
     "nominal_kgcm": 3.4,
     "nominal_a": 0.3,
     "bloqueio_kgcm_faixa": [
      10,
      13.6
     ],
     "bloqueio_a": 1.2
    },
    "12v_rapido": {
     "rpm_vazio": 60,
     "bloqueio_kgcm": 20,
     "bloqueio_a": 2.4
    },
    "24v": {
     "rpm_vazio": 35,
     "bloqueio_kgcm": 13,
     "bloqueio_a": 0.8
    }
   },
   "1:270": {
    "ppr_saida": 2970,
    "12v_padrao": {
     "rpm_vazio": 22,
     "bloqueio_kgcm": 16,
     "bloqueio_a": 1.2
    },
    "24v": {
     "rpm_vazio": 22,
     "bloqueio_kgcm": 20,
     "bloqueio_a": 0.8
    }
   },
   "1:506": {
    "ppr_saida": 5566,
    "12v_padrao": {
     "rpm_vazio": 12,
     "bloqueio_kgcm": 30,
     "bloqueio_a": 1.2
    },
    "24v": {
     "rpm_vazio": 12,
     "bloqueio_kgcm": 40,
     "bloqueio_a": 0.8
    }
   },
   "1:810": {
    "ppr_saida": 8910,
    "12v_padrao": {
     "rpm_vazio": 7,
     "bloqueio_kgcm": 48,
     "bloqueio_a": 1.2
    },
    "24v": {
     "rpm_vazio": 7,
     "bloqueio_kgcm": 64,
     "bloqueio_a": 0.8
    }
   }
  },
  "binario_nominal_24v": null,
  "limite_redutor_kgcm": [
   20,
   25
  ],
  "preco_usd_faixa": [
   7.36,
   21.45
  ],
  "preco_usd_tipico": 12.99,
  "preco_brl": null,
  "preco_brl_jgb37_545_encoder": 76.7,
  "confianca": "A (tabelas) / M (geometria) / B (preco BR)",
  "fontes": [
   "https://precisionminidrives.com/product/37mm-gear-motor-with-encoder-41mm-type-model-nfp-jgb37-520-en",
   "https://www.openimpulse.com/blog/jgb37-520-gearmotor-selector",
   "https://www.hiwonder.com/products/hall-encoder-dc-geared-motor",
   "https://nfpmotor.com/37mm-metal-gear-motor-model-nfp-gm37-520-en",
   "https://probots.co.in/jgb37-520-dc12v-66rpm-miniature-speed-reduction-gear-dc-motor.html",
   "https://www.robotshop.com/products/aslong-motor-37mm-diameter-12v-200rpm-brushed-dc-gear-motor-w-encoder",
   "https://www.aliexpress.com/item/1005007204535740.html",
   "https://produto.mercadolivre.com.br/MLB-4927626223-motor-redutor-de-encoder-cc-jgb37-545-6v-12v24v-motor-cc-de-_JM"
  ]
 },
 "fuso_tr8x2": {
  "existe": true,
  "entradas": 1,
  "avanco_mm": 2,
  "norma": "nao consta da DIN 103 (normalizado e Tr8x1.5)",
  "geometria_calc_din103_mm": {
   "d": 8.0,
   "d2": 7.0,
   "d3": 5.5,
   "D1": 6.0,
   "D4": 8.5
  },
  "comprimentos_mm": [
   100,
   150,
   200,
   300,
   370,
   400,
   470,
   500,
   600,
   1200
  ],
  "massa_g_100mm": [
   30,
   33
  ],
  "angulo_helice_graus_calc": 5.2,
  "mu_critico_autobloqueio_calc": 0.088,
  "autobloqueante": true,
  "rendimento_subida_calc": {
   "mu_0.10": 0.46,
   "mu_0.15": 0.36,
   "mu_0.19": 0.31
  },
  "binario_Nm_por_100N_calc": [
   0.069,
   0.088
  ],
  "preco_usd": {
   "2x100mm_com_porca": 4.5,
   "ebay_faixa": [
    8.25,
    11.98
   ]
  },
  "preco_brl": {
   "600mm_com_castanha": 60.8,
   "500mm_inox_com_castanha": [
    117.32,
    130
   ],
   "3x500mm_sem_castanha": 128.66
  },
  "comparacao_t8x8": {
   "angulo_helice_graus_calc": 20.0,
   "mu_critico_calc": 0.35,
   "autobloqueante_lubrificado": false
  },
  "confianca": "A (disponibilidade/regra DIN) / M (massa, preco) / calc.",
  "fontes": [
   "https://www.fabreeko.com/products/tr8x2mm-lead-screws-for-ender-5-pro-and-ender-5-plus",
   "https://www.bornemann-gewindetechnik.de/en/products/trapezoidal-threads/data",
   "https://www.gobilda.com/3501-series-lead-screw-8mm-lead-4-start-300mm-length",
   "https://www.robotics.org.za/TR8X8-P2-L1200",
   "https://blog.igus.eu/self-locking-what-is-it",
   "https://www.mercadolivre.com.br/fuso-trapezoidal-tr8-500mm--porca-anti-folga-tr8-passo-2mm/up/MLBU2220446293"
  ]
 },
 "porca_t8_latao_flange": {
  "dims_mm": {
   "flange_diam": 22,
   "flange_espessura": [
    3.3,
    3.5
   ],
   "corpo_diam": 10.2,
   "altura_total": 15,
   "furos": 4,
   "furo_diam": 3.5,
   "circulo_furos_diam": 16
  },
  "massa_g_calc": 13,
  "carga_axial_kN_calc": [
   1.6,
   2.9
  ],
  "preco_usd": 3.49,
  "preco_brl": 28,
  "confianca": "A (dims) / calc. (massa, carga)",
  "fontes": [
   "https://www.amazon.com/MECCANIXITY-Screw-Trapezoidal-Pitch-Printer/dp/B09QSBXDYP",
   "https://www.ebay.com/itm/262531657553",
   "https://vpmpme.files.wordpress.com/2018/07/ch-02_power-screw.pdf"
  ]
 },
 "porca_t8_pom_antifolga": {
  "dims_mm": {
   "flange_diam": 22,
   "circulo_furos_diam": 16,
   "comprimento": 25,
   "mola_comprimento": 40
  },
  "massa_g": 25,
  "preco_eur": [
   3.3,
   4.61
  ],
  "preco_usd_2un": 7.4,
  "confianca": "M",
  "fontes": [
   "https://www.olelectronics.com/product/t8-anti-backlash-spring-loaded-nut-for-8mm-lead-screw",
   "https://deluxcnc.eu/en/sliding-screws/922-pom-anti-backlash-spring-loaded-nut-t8.html"
  ]
 },
 "atrito_aco_latao": {
  "seco": [
   0.15,
   0.35
  ],
  "lubrificado": [
   0.1,
   0.19
  ],
  "aco_bronze_oleo": [
   0.1,
   0.16
  ],
  "confianca": "A",
  "fontes": [
   "https://amesweb.info/screws/screw-nut-collar-friction-table.aspx",
   "https://www.roton.com/screw-university/screw-actions"
  ]
 },
 "acoplamento_6x8": {
  "dims_mm": {
   "diam": 19,
   "comprimento": 25
  },
  "massa_g": 16,
  "preco_usd_faixa": [
   3.06,
   10.66
  ],
  "preco_brl": null,
  "confianca": "A (dims) / M (massa)",
  "fontes": [
   "https://business.walmart.com/ip/5-Packs-Aluminum-Alloy-Shaft-Coupling-6mm-to-8mm-Flexible-Coupling-Motor-Connector-Joint-L25xD19/8862351186",
   "https://www.jsumo.com/flexible-aluminum-coupling-5mm-to-6mm-hole"
  ]
 },
 "mancal_kp08": {
  "dims_mm": {
   "comprimento": 55,
   "largura": 13,
   "altura": [
    28,
    30
   ],
   "furos_entre_centros": 42,
   "furo_diam": [
    4.5,
    5.0
   ],
   "furo_eixo": 8
  },
  "massa_g": [
   35,
   40
  ],
  "preco_eur": [
   1.04,
   6.6
  ],
  "preco_brl_4un": 44.88,
  "confianca": "A",
  "fontes": [
   "https://www.makerstore.com.au/product/bear-kp08",
   "https://www.robotics.org.za/KP08",
   "https://olimex.com/Products/Robot-CNC-Parts/Bearings/KP08"
  ]
 },
 "mancal_kfl08": {
  "dims_mm": {
   "comprimento": [
    47,
    48
   ],
   "largura": 27,
   "altura": [
    11,
    12.5
   ],
   "furos_entre_centros": [
    36,
    37
   ],
   "furo_diam": [
    4.8,
    5.3
   ],
   "furo_eixo": 8
  },
  "massa_g": [
   20,
   29
  ],
  "preco_usd": 8.11,
  "preco_brl_un": 18,
  "preco_brl_2un": 36.93,
  "confianca": "A",
  "fontes": [
   "https://www.makerstore.com.au/product/bear-kfl08",
   "https://electropeak.com/kfl-08-3d-printer-bearing"
  ]
 },
 "apoio_608zz_impresso": {
  "pratica_comum": true,
  "fontes": [
   "https://www.thingiverse.com/thing:3049406",
   "https://www.printables.com/model/155188-p3steel-top-lead-screw-holder-with-608zz"
  ]
 },
 "parafuso_ombro_iso7379_m5": {
  "dims_mm": {
   "ombro_diam": [
    6.0,
    6.5
   ],
   "cabeca_diam": 10,
   "cabeca_altura": 4.5,
   "sextavado": 3,
   "rosca_comprimento": 9.5
  },
  "preco_usd_un": [
   3.28,
   4.65
  ],
  "confianca": "M",
  "fontes": [
   "https://www.woodstockindustrial.com/specs/iso-7379",
   "https://fullerfasteners.com/tech/iso-7379-specifications-hex-socket-head-shoulder-screws"
  ]
 },
 "parafuso_ombro_d5_m4": {
  "dims_mm": {
   "ombro_diam": 5,
   "cabeca_diam": [
    8,
    9
   ],
   "cabeca_altura": 4,
   "sextavado": 2.5,
   "rosca_comprimento": [
    5,
    8
   ]
  },
  "preco_usd_10un": 4.4,
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.accu.co.uk/metric-socket-shoulder-screws/10391-SSH-M4-30-A2",
   "https://www.tme.com/us/en-us/details/iso7379-5-m4-10/shoulder-screws/elesa-ganter/iso-7379-5-m4-10"
  ]
 },
 "rolamento_mr84zz": {
  "dims_mm": [
   4,
   8,
   3
  ],
  "massa_g": [
   0.56,
   1.0
  ],
  "preco_usd_10un": [
   9.49,
   9.99
  ],
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.lily-bearing.com/products/mr84zz",
   "https://www.walmart.com/ip/MR84ZZ-Deep-Groove-Ball-Bearings-4mmx8mmx3mm-Double-Shielded-Chrome-Steel-P6-10pcs/189441676"
  ]
 },
 "rolamento_684zz": {
  "dims_mm": [
   4,
   9,
   4
  ],
  "massa_g": 1.0,
  "carga_dinamica_n": 545,
  "carga_estatica_n": 182,
  "preco_usd_10un": null,
  "preco_brl": null,
  "confianca": "A",
  "fontes": [
   "https://www.fitrunbearing.com/product/684zz"
  ]
 },
 "driver_drv8871": {
  "dims_mm": [
   24.4,
   20.4,
   9.7
  ],
  "massa_g": 2.2,
  "tensao_v": [
   6.5,
   45
  ],
  "pico_a": 3.6,
  "itrip_formula": "I(A)=64/R_ILIM(kOhm)",
  "r_ilim_padrao_kohm": 30,
  "itrip_padrao_a": 2.13,
  "r_ilim_min_kohm": 15,
  "rds_on_ohm": 0.565,
  "rtheta_ja_c_w": 41.1,
  "preco_usd": 7.5,
  "jgb37_24v_bloqueio": {
   "corrente_a": 0.8,
   "dissipacao_w_calc": 0.36,
   "delta_t_c_calc": 15,
   "aguenta": true
  },
  "jgb37_12v_rapido_bloqueio": {
   "corrente_a": [
    2.4,
    3.9
   ],
   "limitado_a": 2.13,
   "dissipacao_w_calc": 2.56,
   "delta_t_c_calc": 105,
   "aguenta": "marginal (perto do corte termico)"
  },
  "confianca": "A (dados) / calc.",
  "fontes": [
   "https://www.electrokit.com/upload/quick/6e/fa/0033_manual.pdf",
   "https://download.mikroe.com/documents/datasheets/drv8871.pdf",
   "https://forums.adafruit.com/viewtopic.php?t=204053"
  ]
 },
 "driver_pololu_g2_18v17": {
  "dims_mm": [
   33.0,
   20.3
  ],
  "massa_g": 3.3,
  "tensao_v": [
   6.5,
   30
  ],
  "continua_a": 17,
  "preco_usd": 44.95,
  "confianca": "A",
  "fontes": [
   "https://www.pololu.com/product/2991",
   "https://www.pololu.com/product/3751"
  ]
 },
 "driver_pololu_g2_24v13": {
  "dims_mm": [
   33.0,
   20.3
  ],
  "massa_g": 3.3,
  "tensao_v": [
   6.5,
   40
  ],
  "continua_a": 13,
  "preco_usd": 44.95,
  "confianca": "A",
  "fontes": [
   "https://www.pololu.com/product/2992/specs",
   "https://www.pololu.com/product/3751"
  ]
 },
 "driver_btn8982": {
  "ci_preco_usd": [
   3.48,
   6.27
  ],
  "shield_infineon_preco_eur": 18.48,
  "shield_massa_bruta_g": 35,
  "modulo_generico_dims": null,
  "confianca": "M",
  "fontes": [
   "https://www.mouser.com/en/ProductDetail/Infineon-Technologies/BTN8982TA?qs=y2kkmE52mdPcPfXmFEmVng%3D%3D",
   "https://www.tme.com/au/en/details/kit-mtctr-btn8982/development-kits-others/infineon-technologies/dcmotorcontrbtn8982t0b01"
  ]
 },
 "driver_ibt2_bts7960": {
  "dims_mm": [
   50,
   50,
   43
  ],
  "massa_g": [
   54,
   66
  ],
  "continua_a": 43,
  "confianca": "A",
  "fontes": [
   "https://electropeak.com/bts7960-43a-high-power-motor-driver-module"
  ]
 },
 "ubec_6s": {
  "nota": "DS3218MG maximo 6.8 V; 7.2-7.4 V excede a ficha",
  "hobbywing_10a_v2_2_6s": {
   "entrada": "2-6S",
   "saida_v": [
    6.0,
    7.4,
    8.4
   ],
   "continua_a": 10,
   "pico_a": 15,
   "dims_mm": [
    45,
    20,
    16.2
   ],
   "massa_g": 34,
   "preco_usd": 24.99,
   "fontes": [
    "https://www.hobbywingdirect.com/products/ubec-10a"
   ]
  },
  "hobbywing_10a_v1_2_6s": {
   "saida_v": [
    5.0,
    6.0,
    7.4,
    8.4
   ],
   "continua_a": 10,
   "pico_a": 20,
   "dims_mm": [
    43.1,
    32.3,
    12.5
   ],
   "massa_g": 36,
   "preco_usd": null,
   "fontes": [
    "https://www.cmldistribution.co.uk/diagrams/HobbyWing/UBEC%2010A%202-6S%20Manual.pdf"
   ]
  },
  "hobbywing_10a_hv_3_14s": {
   "saida_v": [
    6.0,
    7.4,
    8.4
   ],
   "continua_a": 10,
   "pico_a": 25,
   "dims_mm": [
    55,
    25,
    12
   ],
   "massa_g": 35,
   "preco_usd": null,
   "fontes": [
    "https://www.hobbywing.com/en/products/ubec-10a-hv289"
   ]
  },
  "ztw_8a_g2": {
   "entrada": "2-8S",
   "saida_v": [
    5,
    6,
    7.4,
    8.4
   ],
   "continua_a": 8,
   "pico_a": 15,
   "dims_mm": [
    48,
    22,
    7
   ],
   "massa_g": 14,
   "preco_usd": [
    16.99,
    29.99
   ],
   "fontes": [
    "https://motionrc.com/products/ztw-ubec-8a-g2-peak-15a-adjustable-output-voltage-external-bec-ztw3040011"
   ]
  },
  "holybro_12a": {
   "entrada": "3-14S",
   "saida_v": [
    6.0,
    7.2,
    8.0,
    9.2
   ],
   "continua_a": 12,
   "pico_a": 24,
   "dims_mm": [
    48,
    33.6,
    16.3
   ],
   "massa_g": 47.8,
   "preco_usd": [
    36.59,
    36.99
   ],
   "fontes": [
    "https://holybro.com/products/ubec-12a"
   ]
  },
  "castle_cc_bec_2_0": {
   "entrada": "2-14S",
   "saida_v_ajuste": [
    4.75,
    12.0
   ],
   "passo_v": 0.25,
   "continua_a": {
    "5-6V": 10,
    "7.25-8.5V": 9
   },
   "pico_a": 15,
   "massa_g": [
    21,
    28
   ],
   "preco_usd": [
    54.95,
    56.95
   ],
   "fontes": [
    "https://www.manualslib.com/manual/1628799/Castle-Creations-Cc-Bec-2-0.html"
   ]
  },
  "dimensionamento_calc": {
   "pico_4_servos_a": [
    7.2,
    10.4
   ],
   "pico_8_servos_a": [
    14.4,
    20.8
   ]
  }
 }
}
```
