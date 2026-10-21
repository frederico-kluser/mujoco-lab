# Baterias do catálogo — dados para modelação 3D fiel (pesquisa 2026-10-19)

**Método.** Só a CLI Tavily (`search` / `extract`). Todo o conteúdo web é dado não-confiável: daqui só saem
números e factos, com a URL. Nenhum ficheiro do repositório foi alterado. Os ficheiros brutos das pesquisas
estão em `pesquisa/raw_bat/` (scratchpad).

**Confiança** (por número): **fabricante** (ficha/catálogo oficial ou distribuidor oficial da marca, p.ex. genstattu
para Gens Ace/Tattu) · **revendedor** · **fórum** (inclui revisores independentes como HKJ/lygte-info e Mooch) ·
**estimado** (derivado por mim, com a conta à vista) · **não encontrado**.

---

## 0. O que contradiz o catálogo atual (`models/drone_rpi/componentes.json` → `celulas`)

| item | catálogo hoje | encontrado | confiança | nota |
|---|---|---|---|---|
| P50B `dims_mm` | [21.7, 70.2] | **Ø 21.55 × 70.15 mm máx.** (ficha 80122); nominal **21.40 ± 0.15 × 70.00 ± 0.15** (spec v0.1); 71 g máx (ficha) / 70.0 g máx (spec) | fabricante | 21.7 × 70.2 é o envelope genérico antigo (o da P42A); `lab/drone_rpi/detalhes/eletronica.py` já usa 21.55 × 70.15, por isso o `componentes.json` e a malha 3D não batem certo |
| P45B `dims_mm` | [21.7, 70.2] | **Ø 21.55 × 70.15 mm máx., 70 g máx.** (ficha v1.2); DNK: 21.6 × 70.2 máx, 69 g máx | fabricante | a mesma origem antiga |
| P45B `massa_g` | 66.0 | 66.0 g (tabela About:Energy, que parece calculada: 16.2 Wh / 245 Wh/kg = 66.1 g); NKON 68 g; ficha ≤ 70 g | revendedor/fabricante | 66 g parece baixo; para a massa visual/física, 68 g é mais defensável (estimado) |
| M50LT `dims_mm` | [21.1, 70.15] | **Ø ≤ 21.44 mm (medido a 4 mm do topo) × H ≤ 70.65 mm**; TTS 0 +0.00/−0.55 mm (spec LG 2021-02-01, a mesma fonte que o catálogo cita); M50T nominal 21.1 × 70.2; HKJ mediu o M50T a 21.1 × 70.5 | fabricante | 70.15 não aparece em fonte nenhuma (todas dão 70.2–70.65) |
| M50LT `massa_g` | 67.5 | 67.5 ± 1.0 g **"without washer"** (LG); DNK/Tenergy: 68.2 ± 1.0 g (TBD) | fabricante | ok |
| 50E | [21.25, 70.8], 69 g | 21.25 / 70.80 máx. com manga (V1.0, 2018-07-11) ✓; massa **69.5 g máx.** (V1.0; a V0.2 dizia 69 g máx.); medido (HKJ) 21.1 × 70.6; revendedor 68.7 g | fabricante | dims ok; o valor típico real anda pelos 68.7 g |
| SA102 `dims_mm` | [80, 50, 6] (estimado) | **L1 56.5 ± 1.5 · L2 53.0 ± 1.5 · W1 49.5 ± 1.5 · T1 5.5 ± 0.4 mm** (@30 % SoC); 33.1 ± 0.8 g | fabricante (TDS AMP-TDS-SA102-P5) | 80 mm está errado; a massa (33.1 g) está certa. Capacidade: o cabeçalho diz "4.24 Ah", mas a tabela dá 4370 mAh típ. / 4300 mín. @C/10 |
| Tattu 12 Ah | célula [194, 71, 5.3], pack 800 g, 194 × 71 × 32 | página Tattu: **194 × 71 × 32 mm, 800 g, XT90S-F** ✓; tabela da série Grepow: **192 × 71.5 × 32 mm, 860 g**, 120 A burst | fabricante (as duas) | as fontes oficiais divergem; 194 mm é o pack (a célula sem abas/saída é mais curta, ver B.2) |
| G-Tech 4S 10 Ah | célula [169, 65, 9.75] | pack **169 × 65 × 39 mm (±5/±2/±2), 940 ± 20 g** ✓ (39/4 = 9.75) | fabricante | 169 é o pack, não a célula |
| Gens Ace 5000 45C | célula [140, 45, 9] (estimado) | 4S Deans: **158 × 46 × 31 mm, 480 g** → 7.75 mm/célula; 6S G-Tech: **157 × 46 × 44 mm, 682 g** → 7.33 mm/célula | fabricante (genstattu) | a espessura de 9 mm está alta; o comprimento do corpo deve ficar ~145–150 mm (estimado) |
| LiPo 1500 4S | célula [72, 35, 9], 44 g | packs 75C reais: Lumenier **75 × 34 × 34 mm, 169 g**; TBS Graphene 77 × 39 × 34, 188 g → 8.5 mm/célula, ~38–42 g/célula | revendedor / estimado | a massa de 44 g está um pouco alta |
| XT90 (`eletronica.py`) | contactos a ±5.25 mm (passo 10.5) | passo **≈ 11.0 mm** entre centros | fórum (fonte única) | ajuste de 0.5 mm, a confirmar com paquímetro |

---

## A. Células cilíndricas 21700

### A.1 Dimensões e massa

| célula | Ø máx (mm) | H máx (mm) | nominal / medido | massa | fontes |
|---|---:|---:|---|---|---|
| **Molicel INR-21700-P50B** | **21.55** | **70.15** | nominal 21.40 ± 0.15 × 70.00 ± 0.15 (spec v0.1); NKON lista 21.4 × 70.15 e 21.7 × 70.2; volume 25.59 cm³ (About:Energy, calculado com os máx.) | **71 g máx** (ficha); 70.0 g máx (spec v0.1); 68.8 g (About:Energy); 68–70 g (NKON) | [P50B DS](https://www.molicel.com/wp-content/uploads/Product-Data-Sheet-of-INR-21700-P50B-80122.pdf), [P50B página](https://www.molicel.com/product/inr-21700-p50b), [spec v0.1 (DNK)](https://www.dnkpower.com/wp-content/uploads/2024/11/Molicel-INR21700P50B.pdf), [About:Energy](https://www.aboutenergy.io/post/molicel-p50b-vs-p45b-battery-performance), [NKON](https://www.nkon.nl/novat/molicel-inr21700-p50b-5000mah-50a.html) |
| **Molicel INR-21700-P45B** | **21.55** | **70.15** | DNK 21.6 × 70.2 máx; NKON 21.7 × 70.2 | **70 g máx** (ficha v1.2); 69 g máx (DNK); 68 g (NKON); 66.0 g (About:Energy) | [P45B DS v1.2](https://www.molicel.com/wp-content/uploads/INR21700P45B_1.2_Product-Data-Sheet-of-INR-21700-P45B-80109.pdf), [DNK](https://www.dnkpower.com/molicel-p45b-inr21700-p45b), [NKON](https://www.nkon.nl/en/molicel-inr21700-p45b-4500mah-45a.html) |
| **LG INR21700 M50LT** | **21.44** | **70.65** | TTS (topo↔ombro) 0 +0.00/−0.55 mm; M50T: 21.1 × 70.2 nominal, HKJ mediu 21.1 × 70.5; Cell Saviors: 21.44 × 70.8 | **67.5 ± 1.0 g sem anilha** (LG); 68.2 ± 1.0 g (DNK) | [spec LG M50LT](https://f.hubspotusercontent10.net/hubfs/6584819/Cell%20Spec%20Sheets/LG/Lithium%20Ion%20LG%20INR%2021700%20M50LT%202021-LSD-MBD-b00002_21700_M50LT_PS_Promotion_V1.pdf), [DNK](https://www.dnkpower.com/lg-inr21700-m50lt), [HKJ M50T](https://lygte-info.dk/review/batteries2012/LG%2021700%20M50T%205000mAh%20(Gray)%20UK.html) |
| **Samsung INR21700-50E** | **21.25** (topo, com manga) | **70.80** | HKJ mediu **21.1 × 70.6**; revendedores 21.1 × 70.7 | **69.5 g máx** (V1.0); 69 g máx (V0.2); 68.7 g (revendedor) | [spec V1.0](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/INR21700_2D00_50E-Cell-Specification_5F00_V1.0_5F00_180711.pdf), [HKJ índice](https://lygte-info.dk/info/batteryIndex.html), [IMR](https://imrbatteries.com/products/samsung-50e-21700-5000mah-9-8a-battery) |

Para a malha: usar o **nominal** quando há (P50B 21.40 × 70.00) ou o **medido** (50E 21.1 × 70.6), e o máximo só para o
envelope de folgas. Lata de **aço** (Molicel: "Can: Steel", fabricante).

### A.2 Aparência (manga, impressão, topo, anel, fundo)

| célula | cor da manga | impressão | topo (+) | anel isolador de fábrica | fundo (−) |
|---|---|---|---|---|---|
| P50B | **cinzento** ("Color: Gray": [Liion Wholesale, distribuidor autorizado](https://liionwholesale.com/products/molicel-npe-inr-21700-p50b-60a-5000mah-flat-top-21700-battery-authorized-distributor), revendedor); "**faixas cinzento-escuras junto ao polo +**" ([Reddit r/flashlight](https://www.reddit.com/r/flashlight/comments/1rylku3/purchased_molicel_p50bs_from_wurkkoscom_and_they), fórum) | desenho oficial da célula: **código 2D** (PPP LYMDD SS) + **código de data YMDDSS** + "**NOT FOR E-CIG OR VAPE**" ([spec v0.1](https://www.dnkpower.com/wp-content/uploads/2024/11/Molicel-INR21700P50B.pdf), fabricante); a Molicel usa esta frase como marca de autenticidade ([aviso Molicel](https://www.molicel.com/newsroom/important-notice-beware-of-counterfeit-molicel-inr-18650-p28a)) | **flat top** (fabricante/revendedores); válvula de segurança: "Safety Valve" (spec), nº de furos **não encontrado** | não encontrado | aço; aspeto não encontrado |
| P45B | **cinzento** ([Liion Wholesale](https://liionwholesale.com/products/molicel-npe-inr-21700-p45b-50a-4500mah-flat-top-21700-battery-authorized-distributor); [Cell Saviors](https://cellsaviors.com/cell-database/molicel-p45b)), revendedor | não encontrado (presume-se o padrão Molicel acima: estimado) | flat top | não encontrado | aço |
| M50LT | **conflito**: "mesma cor do M50T" (Mooch, citado no [ECF](https://www.e-cigarette-forum.com/threads/bench-test-results-lg-m50lt-14-4a-4932mah-21700.979634) e na [nightvision](https://nightvision.co.nz/lg-m50lt-21700-5000mah-15a-rechargeable-battery)); M50T = **Gray** (HKJ e [Cell Saviors](https://cellsaviors.com/cell-database/lg-m50t)) **vs** "Wrap color: **Clear**" ([Cell Saviors M50LT](https://cellsaviors.com/cell-database/lg-m50lt)) | não encontrado | flat top; **TTS 0/−0.55 mm** → o topo fica rente ao ombro ou até 0.55 mm abaixo (fabricante) | a LG pesa "sem anilha" (washer): há versão com anilha, cor não encontrada | aço |
| 50E | **ciano** ([HKJ "(Cyan)"](https://lygte-info.dk/review/batteries2012/Samsung%20INR21700-50E%205000mAh%20(Cyan)%20UK.html), fórum) | não encontrado | flat top; Ø do terminal + ≈ **9 mm** nas Samsung 21700 30T/40T ([esk8](https://forum.esk8.news/t/21700-battery-positive-terminal-size/26542), fórum) → 50E estimado igual | não encontrado | aço |

Cores RGB para o renderer: **estimadas** a partir do nome da cor, não medidas (ver JSON).

---

## B. Células pouch / LiPo e packs

### B.1 Amprius SiCore SA102 (pouch, ânodo de silício) — [TDS no catálogo Amprius](https://amprius.com/documents/Amprius_Product_Catalog.pdf) (fabricante, PRELIMINARY)

| campo | valor |
|---|---|
| formato | **pouch** (Packaging: Pouch; cátodo NMCA) |
| L1 / L2 / W1 / T1 | **56.5 ± 1.5 / 53.0 ± 1.5 / 49.5 ± 1.5 / 5.5 ± 0.4 mm** (T1 @30 % SoC) |
| massa | **33.1 ± 0.8 g** (About:Energy: 33.1 g, volume 17.15 cm³) |
| capacidade | 4370 mAh típ. / 4300 mín. @C/10 (14.85 / 14.62 Wh); o cabeçalho diz "4.24 Ah" |
| tensões | 3.40 V nominal · 4.25 V carga · 2.20 V corte |
| corrente | 4.3 A (1C) contínuos, 8.6 A (2C) ≤ 30 s; ACIR ≤ 30 mΩ |
| densidade | 450 Wh/kg; 950 Wh/L (catálogo 2026) ou 990 Wh/L (portefólio 2024) |
| montagem | **exige aperto externo de 30 PSI (≈ 207 kPa)** → o pack 3D precisa de placas de compressão/cintas (fabricante) |
| abas | **não encontrado** (o desenho só tem as cotas L1, L2, W1, T1). L1 − L2 = 3.5 mm; a minha leitura é que L1 inclui as abas/selagem e L2 é o corpo (estimado). Largura e posição das abas: não encontrado; em pouch pequena o habitual é as duas abas no mesmo lado curto (estimado) |

### B.2 Tattu 380 Wh/kg 12000 mAh 6S1P semi-sólido (TARBG3812K06S10X)

| campo | valor | confiança / fonte |
|---|---|---|
| pack L × W × T | **194 × 71 × 32 mm** | fabricante: [Tattu](https://www.tattuworld.com/products/tattu-380wh-kg-12000mah-6s1p-22-2v-10c-semi-solid-state-uav-lipo-battery.html), [gensace.de](https://gensace.de/products/tattu-semi-solid-state-380wh-kg-12000mah-10c-22-2v-6s1p-lipo-battery-pack-with-xt90s-f-plug) |
| (alternativa oficial) | **192 × 71.5 × 32 mm, 860 g**, 120 A burst | fabricante: [tabela da série Grepow](https://www.grepow.com/semi-solid-state-battery/380wh-kg-series-high-energy-density-battery-pack.html) |
| massa | **800 g** (Tattu) / 860 g (Grepow) | fabricante |
| conector | **XT90S-F** (anti-faísca, fêmea no pack); opções sob pedido: XT60, XT90, EC5, AS150U | fabricante |
| balanceamento | **G-Tech-7P** (Gens Ace/Tattu: JST-XH com um pino extra atrás, [Reddit](https://www.reddit.com/r/rccars/comments/13nbl20/battery_connector_question), fórum) | fabricante (gensace.de) |
| bitola dos cabos | **não publicada** para este SKU. Família Tattu: 6S 12000 30C UAV Classic = **10#**, cabo 150 mm, JST-XHR-7P 65 mm ([genstattu](https://genstattu.com/tattu-30c-22.2v-12000-6s1p-ec5.html)); semi-sólido 25 Ah = 8#, 150 mm, G-Tech-7P 85 mm ([genstattu](https://genstattu.com/tattu-semi-solid-state-330wh-kg-25000mah-10c-22-2v-6s1p-g-tech-lipo-battery-pack-with-xt90-s-plug)) → para este: **10 AWG, 150 mm; balanceador 65–85 mm** | estimado |
| elétrico | 36 A contínuos; 90 A ≤ 15 s; IR ≤ 7 mΩ; corte 15 V; "Soft Pack" | fabricante |
| cor do invólucro | **não encontrado** (nenhum texto descreve a cor) | — |
| célula (derivada) | espessura 32/6 = **5.33 mm** com invólucro; largura ≈ 70–71 mm; corpo ≈ 194 − (10–15) mm de abas/saída ≈ **180 mm** | estimado |

### B.3 Tattu G-Tech 4S 10000 mAh 25C

| campo | valor | fonte |
|---|---|---|
| pack | **169 × 65 × 39 mm** (±5/±2/±2), **940 ± 20 g** | fabricante: [Grepow](https://www.grepow.com/uav-battery/tattu-4s-10000mah-14-8v-25c-lipo-drone-battery.html), [genstattu (sem ficha)](https://genstattu.com/tattu-10000mah-14-8v-25c-4s1p-lipo-battery-pack-without-plug.html) |
| cabos | **AWG10#**, cabo de descarga 120 mm; balanceador **JST-XHR** (5P), 65 mm; versão "No Plug" | fabricante (genstattu) |
| variante Smart | 174 × 66 × 44 mm, 921 g | revendedor ([motionew](https://www.motionew.com/shop/power-solution/battery-lipo-4s-10000mah-25c-tattu-g-tech-smart)) |
| cor | **PVC preto com o logótipo "Tattu G-Tech" a branco** (anúncio do 6S 30C G-Tech; o 4S presume-se igual) | revendedor ([eBay](https://www.ebay.com/itm/227265083006)) / estimado |
| célula (derivada) | 39/4 = **9.75 mm**; corpo ≈ 155–160 × 63 mm | estimado |

### B.4 Gens Ace 5000 mAh 45C (soft case)

| versão | L × W × H (mm) | massa | conector / cabos | fonte |
|---|---|---|---|---|
| **4S Deans** (a fonte do catálogo) | **158 ± 5 × 46 ± 2 × 31 ± 2** | **480 ± 20 g** | Deans; **10#**; cabo de descarga 120 mm; **JST-XHR-5P** | fabricante ([genstattu](https://genstattu.com/gens-ace-5000mah-4s-45c-14-8v-lipo-battery-pack-with-dean-plug)) |
| 4S G-Tech EC5 | 156 × 47 × 30 | 468 g | EC5; balanceador G-Tech | revendedor ([AMain](https://www.amainhobbies.com/gens-ace-gtech-smart-4s-lipo-battery-45c-14.8v-5000mah-w-ec5-connector-gea504s45e5gt/p1527333)) |
| **6S G-Tech EC5** | **157 ± 5 × 46 ± 2 × 44 ± 2** | **682 ± 20 g** | EC5; **AWG10#**; 120 mm; **G-tech-7P**, 65 mm | fabricante ([genstattu](https://genstattu.com/gens-ace-5000mah-6s-45c-22-2v-g-tech-lipo-battery-pack-with-ec5-plug)); gensace.de: 155 × 46 × 44, 678 g |
| célula (derivada) | 4S: 31/4 = **7.75 mm**; 6S: 44/6 = **7.33 mm**; corpo ≈ 145–150 × 45 mm | ≈ 113–120 g | — | estimado |
| cor | **não encontrado** | | | |

### B.5 LiPo genérica 1500 mAh 4S 75C

| pack | L × W × H (mm) | massa | fonte |
|---|---|---|---|
| Lumenier 1500 4S 75C | **75 × 34 × 34** | 169 g | revendedor ([RDQ](https://www.racedayquads.com/products/lumenier-1500mah-4s-75c-lipo-battery)) |
| TBS Graphene 1500 4S 75C | 77 × 39 × 34 | 188 g; XT60 + JST-XH | revendedor ([Defiance](https://www.defiancerc.com/products/tbs-graphene-1500mah-4s-75c-lipo-battery)) |
| Hobby Wireless 1500 4S 75C | 90 × 34 × 27 | 164 g | revendedor ([Hobby Wireless](https://www.hobbywireless.com/hobby-wireless-1500mah-148v-4s-75c-lipo-battery-xt60-p-3932.html)) |
| célula (derivada) | ≈ **72 × 34 × 8.5** (34/4) | ≈ 38–42 g (pack menos 10–20 g de cabos/XT60) | estimado |

---

## C. Construção DIY de um pack 21700 6S2P (classe 50 A)

### C.1 Fita de níquel / cobre (corrente contínua por fita)

| fita | conservador (Micah Toll; "ótimo / aceitável") | otimista | fonte |
|---|---|---|---|
| Ni puro 0.15 × 7 mm | 4.7 / 7.0 A | 12–15 A | [customnickelstrips](https://customnickelstrips.com/the-ultimate-guide-to-sizing-nickel-strips-for-battery-packs); [renewspark](https://renewspark.com/blogs/news/nickel-strip-size-guide-battery-building) |
| Ni puro 0.15 × 8 mm | ~5.0 / 7.5 A | 10–15 A | idem; [themakerschest](https://themakerschest.com/blogs/spot-welding-hub/nickel-strip-vs-copper-strip-for-battery-packs-what-you-need-to-know) |
| Ni puro 0.20 × 7–8 mm | 6.4 / 9.6 A | 15–25 A | idem |
| Ni puro 0.20 × 10 mm | — | 30–40 A | renewspark |
| Ni puro 0.30 × 7–10 mm | 10 / 15 A | 40–60 A | idem |
| Cu 0.20 × 8 mm | — | 35–50 A | themakerschest |
| **sanduíche Cu + Ni** | Cu ≤ **0.10 mm** (até 0.15) por baixo de Ni 0.15 × 8 mm: soldar através do Ni | — | [Cell Saviors](https://cellsaviors.com/blog/copper-nickel-sandwich) (fórum); também há fita composta "0.3 mm Cu + 0.1 mm Ni" ([diy500amp](https://diy500amp.com/collections/collections-nickel-copper-strips), revendedor) |

**Para 50 A** (cada ligação série leva os 50 A; cada célula 25 A) o níquel sozinho não chega, mesmo pela tabela otimista:
usa-se **sanduíche Cu/Ni** ou barras de cobre. Exemplo real: um 6S2P de "140 A contínuos" montado com "tray and busbars …
copper/nickel sandwich" ([vídeo](https://www.youtube.com/watch?v=yKh0EeuMnTQ), fórum). Guia FPV: Ni 0.15 × 8 nas ligações série,
"duas camadas de 0.15 ou uma de 0.2" na saída principal, **2 pontos de solda por terminal (4 em corrente alta)**
([uavmodel](https://blog.uavmodel.com/diy-li-ion-battery-pack-building-for-long-range-fpv-drones-cells-welding-and-safety), fórum).
Recomendação para o modelo (estimado): Ni 0.15 × 8–10 mm sobre Cu 0.10 mm, cada ligação série a cobrir as 4 extremidades
(2 células do grupo k + 2 do grupo k+1).

### C.2 Disposição 6S2P

Packs comerciais 6S2P 21700 (revendedor):

| pack | L × W × H (mm) | massa | leitura da disposição (estimado) |
|---|---|---|---|
| [Wrekd 6S2P **Molicel P50B** 10 Ah](https://wrekd.com/products/6s2p-21-6v-molicel-p50b-10000mah-li-ion-battery-pack) | **139 × 48 × 72** | **900 g**; 120 A contínuos | 6 lado a lado (139) × 2 filas (48), eixo das células nos 72 mm |
| [Auline S70 Ultra 6S2P](https://www.au-line.com/products/21700-s70-ultra-10000mah-6s2p-22-2v-140a-xt60-xt90) | **75 × 43 × 132** | 849 g ± 15; 140 A | eixo nos 75; 2 filas (43 = 2 × 21.5); 6 lado a lado (132) |
| [Strix Power Stix 6S2P (Samsung 50S)](https://www.readymaderc.com/products/details/87049-strix-power-stix-10000mah-6s2p-21700-lithium-ion-xt60) | 129 × 79 × 45 | 915 g; **12 AWG**, 8 cm; XT60 | 6 lado a lado (129) × 2 filas (45), eixo nos 79 |
| [Lumenier NAV 10 Ah 6S](https://www.racedayquads.com/products/lumenier-nav-10000mah-6s-21700-lithium-ion-battery-xt60) | 150 × 55 × 65 | 975 g | outra disposição (2 × 3 em secção, 2 em comprimento) |

→ o padrão é **6 × 2 com todas as células paralelas** (o que o `eletronica.py` já faz). Envelope derivado com células
máximas: 6 × 21.55 = **129.3** × 2 × 21.55 = **43.1** × (70.15 + fitas + papel + feltro + manga) ≈ **73–75 mm** (estimado;
bate com o Auline 132 × 43 × 75). Massa: 12 × 68.8–71 g = 826–852 g de células; o Wrekd P50B pesa 900 g, logo
fitas, cabos, conector, manga e enchimento ficam em ≈ 50–75 g (estimado).

**Fitas e tomadas de balanceamento num 6 × 2** (derivação geométrica, estimado): cada grupo paralelo é uma coluna de 2
células com a mesma orientação, e as colunas alternam a polaridade. Na face A (as extremidades da frente) ficam as ligações
1→2, 3→4 e 5→6; na face B ficam 2→3, 4→5 e os dois terminais do pack (G1− e G6+). **Os dois terminais saem pela mesma face
(B), nas colunas das pontas.**

```
face A:  [G1+]==[G2−]   [G3+]==[G4−]   [G5+]==[G6−]        tomadas B1, B3, B5
face B:  [G1−]   [G2+]==[G3−]   [G4+]==[G5−]   [G6+]        tomadas B0 (P−), B2, B4, B6 (P+)
```

Ordem do JST-XH 7 pinos: **pino 1 = negativo do pack (G1−)**, pino 2 = junção G1+/G2−, …, **pino 7 = positivo do pack (G6+)**,
com fio de 22 AWG soldado em cada junção ([uavmodel](https://blog.uavmodel.com/diy-li-ion-battery-pack-building-for-long-range-fpv-drones-cells-welding-and-safety);
[blog Naver](https://m.blog.naver.com/mybrainz/220768647318): "Neg (−) at the top … Pos (+) at the bottom", fórum). Num 6S2P à mão, as
tomadas vão ao meio da fita e as dos extremos (+/−) à ponta ([vídeo](https://www.youtube.com/watch?v=9Zc5GL7IVL4), fórum).

### C.3 Isolamento, suportes e enchimento

| peça | valores | confiança / fonte |
|---|---|---|
| anel de papel de peixe 21700 (polo +) | **Ø ext. 19.8 / Ø int. 10.5 / 0.2 mm**; outra marca 21 / 12 / 0.2; anel preto ~18 / ~10 / ~0.3 mm, ~0.1 g | revendedor: [renewspark](https://renewspark.com/products/21700-insulator-rings-fish-paper), [eBay](https://www.ebay.com/itm/407152826433), [18650BS](https://www.18650batterystore.com/products/21700-insulator-black) |
| cores dos anéis | não há padrão: **ciano** (anúncio Amazon "Cyan Insulators"), **verde** ("green fish paper", esk8), **preto** (18650BS) | revendedor / fórum |
| feltro / papel / Kapton sobre as fitas | "felt strips … to stop the nickel strips cutting through the heat shrink" ([vídeo](https://www.youtube.com/watch?v=IOeYGLdTcxw)); "uma camada de papel de peixe ou Kapton e depois o termorretrátil de PVC" (uavmodel) | fórum |
| suportes de células 21700 | furo Ø **21.3–21.7 mm**, passo **23.0–23.4 mm** ([Fielect](https://www.amazon.com/Fielect-Battery-Brackets-Plastic-Lithium/dp/B082SKMYKH), [Bangteng](https://bangteng.en.made-in-china.com/product-group/RqMAIzuTJgko/21700-battery-holder-1.html)); espaçador 2P de 21.7 mm ([18650battery](https://18650battery.com/products/2p-battery-spacer-for-21700-cells-21-7mm)) | revendedor |
| suportes vs cola quente | o guia FPV refere suportes impressos em 3D ou comprados ("align cells … physical protection"); **sobre cola quente em packs de drone: não encontrado**. Os packs comerciais (Auline, 43 mm para 2 filas) só cabem com as células encostadas, sem suporte (estimado) | fórum / estimado |

### C.4 Manga exterior (termorretrátil de PVC)

| campo | valor | fonte |
|---|---|---|
| material / parede | PVC, **0.15 mm antes de encolher**; encolhe 40–45 % na transversal e 5–10 % na longitudinal; 90–100 °C | revendedor ([dee5shrink](https://dee5shrink.com/pvc-heat-shrink-sleeves-for-battery)) |
| cores | azul-céu, verde, preto, vermelho, **transparente (clear)**, amarelo; também "transparent blue" ([Liion Wholesale](https://liionwholesale.com/products/21700-pvc-heat-shrink-wraps-10-pack-transparent-blue)); azul, 100 mm de largura plana ([VXB](https://vxb.com/products/blue-pvc-battery-wrap-heat-shrink-tube-for-18650-2)) | revendedor |
| largura plana para o 6 × 2 | perímetro ≈ 2 × (130 + 44) = 348 mm → largura plana entre ~174 mm (justa) e ~316 mm (no limite do encolhimento); escolha típica ≈ 200–230 mm | estimado |

### C.5 Cabos

| cabo | valores | fonte |
|---|---|---|
| principal 10 AWG silicone | **1050 × 0.08 mm, Ø exterior 5.4–5.5 mm** | revendedor ([BNTECHGO](https://bntechgo.com/bntechgo-10-gauge-silicone-wire-spool-red-250-feet-ultra-flexible-high-temp-200-c-600v-10-awg-silicone-rubber-wire-with-1050-strands-of-tinned-copper-wire-stranded-wire-for-model-battery), [eBay](https://www.ebay.com/itm/206550431387)) |
| principal 8 AWG silicone | 1650 × 0.08 mm, **Ø 6.5 mm** | revendedor (eBay) |
| o que se usa | XT90: **10 AWG recomendado** pela AMASS (aceita 8–12 AWG); Gens Ace / Tattu 5–12 Ah: **10#**, 120–150 mm; Tattu semi-sólido 25 Ah: 8#; Strix 6S2P 45 A: 12 AWG, 8 cm. **Para 50 A: 10 AWG** (estimado) | fabricante / revendedor |
| balanceamento | **22 AWG silicone**, 150–200 mm à venda ([diy500amp](https://diy500amp.com/products/6s-jst-xh-7-pin-balance-connector-with-22awg-silicone-wire-200mm)); 65–85 mm nos packs Tattu/Gens Ace; os contactos JST-XH aceitam AWG 28–22 | revendedor / fabricante (JST) |

---

## D. Conectores

### D.1 AMASS XT90 / XT90-S

| campo | valor | confiança / fonte |
|---|---|---|
| contacto | **Ø 4.5 mm** (banana dourada, latão) | fabricante (tabela AMASS: [SMC](http://shop.smc-powers.com/XT90H-F.html); [LCSC](https://www.lcsc.com/product-detail/plug_Changzhou-Amass-Elec-XT90H-F-G-Y_C3040685.html)) |
| passo entre contactos | **≈ 11.0 mm** (XT60: 7.2 mm) | fórum ([mig-welding](https://www.mig-welding.co.uk/forum/threads/source-for-this-connector.143324)), fonte única |
| largura | **≈ 21 mm** | revendedor (MaxAmps, mjbots, Sharvi) |
| macho (XT90H-M) | **31 × 21 × 10 mm** com tampa, 8 g ([MaxAmps](https://maxamps.com/products/xt90-male-connector)); **6 g** ([PDF de revendedor](http://5.imimg.com/data5/SELLER/Doc/2026/2/581970612/SP/MV/TX/251800034/amas-xt90-male-connector-with-housing-1-pcs-xt90h-m-g-y.pdf)) | revendedor |
| fêmea (XT90H-F) | sem tampa **20 × 21 × 11 mm**, 6 g ([Sharvi](https://sharvielectronics.com/product/xt90-female-connector-without-cap)) | revendedor |
| XT90S-F (anti-faísca) | **31 × 21 × 9 mm, 9 g** ([mjbots](https://mjbots.com/products/xt90s-f)); 49 × 21 × 10 mm "com caixa" (Bharat, provavelmente com o cabo) | revendedor |
| cotas AMASS (OCR do catálogo antigo, [PDF](https://file.huaqiu.com/web2/M00/4D/94/poYBAGK5afaAMP1tARYUknMlSrQ604.pdf)) | XT90H-F **30.70 / 26.20**, XT90H-M **29.70 / 25.20**, XT90S-F **31.10 / 26.60** mm (comprimento com tampa / sem tampa, leitura minha); alturas 9.90 / 11.70 / 13.10; **a largura saiu ilegível no OCR** | fabricante, mas os eixos são atribuição minha (estimado) |
| cor | **amarelo** (sufixo .G.Y; LCSC "colour Yellow"; tampa amarela, código 40160010797); preto (.N.B) | fabricante ([catálogo AMASS 2026](https://www.china-amass.com/public/upload/20260207/7fa24f5a6f35ec66c7a115c07a34ab06.pdf)) |
| corrente | **45 A MAX (10 AWG, ΔT < 85 K)** no catálogo de 2026; "90 A / 120 A burst" é o rótulo antigo | fabricante |
| par | 12.8 g/par; "pulling force 60 N" | revendedor ([Pyrodrone](https://pyrodrone.com/products/amass-xt90-connector-male)) |

### D.2 AMASS XT60 (para comparação)

| campo | valor | fonte |
|---|---|---|
| contacto / passo | **Ø 3.5 mm** ([esskabel](https://www.esskabel.de/en/product/kab-xt60h-f-0190li-bk), revendedor) / **7.2 mm** ([Handson](https://www.handsontec.com/dataspecs/connector/XT60.pdf), revendedor; 7 mm medido no Reddit) |
| cotas AMASS (OCR) | XT60-F **20.5 × 16.0 × 8.1**, XT60-M **20.2 × 15.7 × 7.7**; XT60H com tampa: comprimento **23.8 (F) / 23.5 (M)**, tampa com 9.2 de altura (eixos atribuídos por mim) |
| outras | 17 × 15.5 × 7.5 mm (eBay); **35 A MAX (12 AWG)** no catálogo AMASS 2026 |

### D.3 JST-XH 7 pinos (balanceamento 6S) — [ficha JST eXH](https://www.jst-mfg.com/product/pdf/eng/eXH.pdf) (fabricante)

| campo | valor |
|---|---|
| caixa XHP-7 | **B = 19.8 mm** de largura; A = 15.0 mm (pino 1 a pino 7); **5.7 mm de profundidade; 7.5 mm de altura** (RS: 5.7 × 19.8 mm) |
| passo | **2.5 mm** (não 2.54) |
| material / cor | PA 6, natural (**branco**); a ficha da placa é PA 66 marfim |
| cabo / corrente | AWG 28–22 (contacto SXH-001T-P0.6); 3 A; 250 V |
| G-Tech-7P (Gens Ace/Tattu) | compatível com XH, com um pino extra atrás ([Reddit](https://www.reddit.com/r/rccars/comments/13nbl20/battery_connector_question), fórum); cotas não encontradas |

---

## E. Raspberry Pi
Fora do âmbito (é de outro agente).

## Lacunas (não encontrado)
- Furos de ventilação e diâmetro do terminal + da P50B, P45B e M50LT; cor do anel isolador de fábrica das quatro células; aspeto do fundo.
- Tom exato do cinzento Molicel (só há "Gray"); a cor da manga do M50LT tem fontes em conflito (cinzento vs transparente).
- Abas da SA102 (largura, posição, material).
- Cor dos packs Tattu semi-sólido e Gens Ace; bitola dos cabos do Tattu 12 Ah (só por analogia com a família).
- Cotas oficiais legíveis do XT90/XT60 (as fichas LCSC/SnapEDA não abriram; o OCR do catálogo AMASS é parcial).
- Cola quente em packs de drone (nenhuma fonte textual).

---

## JSON (valores para máquina)

```json
{
  "versao": "pesquisa-baterias-2026-10-19",
  "nota": "rgb_aprox = ESTIMADO a partir do nome da cor (0-1, sRGB); máx = envelope da ficha; nominal/medido para a malha",
  "celulas": {
    "molicel_p50b": {
      "diametro_mm": 21.40, "altura_mm": 70.00, "tolerancia_mm": 0.15,
      "diametro_max_mm": 21.55, "altura_max_mm": 70.15,
      "massa_g": 68.8, "massa_max_g": 71.0,
      "topo": "flat", "lata": "aco",
      "cor_involucro": "cinzento", "cor_involucro_rgb_aprox": [0.62, 0.64, 0.66],
      "detalhe_involucro": "faixas cinzento-escuras junto ao polo + (forum); rgb_aprox [0.26, 0.27, 0.29]",
      "impressao": ["Molicel", "INR-21700-P50B", "codigo 2D PPP LYMDD SS", "data YMDDSS", "NOT FOR E-CIG OR VAPE"],
      "cor_anel_isolador": null,
      "confianca": {"dims": "fabricante", "massa_g": "revendedor (About:Energy)", "cor": "revendedor+forum", "rgb": "estimado"},
      "fontes": ["https://www.molicel.com/wp-content/uploads/Product-Data-Sheet-of-INR-21700-P50B-80122.pdf",
                 "https://www.dnkpower.com/wp-content/uploads/2024/11/Molicel-INR21700P50B.pdf",
                 "https://liionwholesale.com/products/molicel-npe-inr-21700-p50b-60a-5000mah-flat-top-21700-battery-authorized-distributor"]
    },
    "molicel_p45b": {
      "diametro_mm": 21.55, "altura_mm": 70.15, "diametro_max_mm": 21.55, "altura_max_mm": 70.15,
      "massa_g": 68.0, "massa_max_g": 70.0,
      "topo": "flat", "lata": "aco",
      "cor_involucro": "cinzento", "cor_involucro_rgb_aprox": [0.58, 0.60, 0.63],
      "cor_anel_isolador": null,
      "confianca": {"dims": "fabricante (só máx.)", "massa_g": "revendedor (NKON)", "cor": "revendedor", "rgb": "estimado"},
      "fontes": ["https://www.molicel.com/wp-content/uploads/INR21700P45B_1.2_Product-Data-Sheet-of-INR-21700-P45B-80109.pdf",
                 "https://www.nkon.nl/en/molicel-inr21700-p45b-4500mah-45a.html",
                 "https://cellsaviors.com/cell-database/molicel-p45b"]
    },
    "lg_m50lt": {
      "diametro_mm": 21.1, "altura_mm": 70.5, "diametro_max_mm": 21.44, "altura_max_mm": 70.65,
      "topo_abaixo_do_ombro_max_mm": 0.55,
      "massa_g": 67.5, "massa_tol_g": 1.0, "massa_nota": "sem anilha (washer)",
      "topo": "flat", "lata": "aco",
      "cor_involucro": "CONFLITO: cinzento (igual ao M50T, Mooch/HKJ) vs transparente (Cell Saviors)",
      "cor_involucro_rgb_aprox": [0.42, 0.43, 0.45], "cor_alternativa_transparente_sobre_aco_rgb_aprox": [0.72, 0.72, 0.70],
      "cor_anel_isolador": null,
      "confianca": {"dims_max": "fabricante", "dims_nominal": "forum (HKJ mediu o M50T)", "massa_g": "fabricante", "cor": "forum (conflito)", "rgb": "estimado"},
      "fontes": ["https://f.hubspotusercontent10.net/hubfs/6584819/Cell%20Spec%20Sheets/LG/Lithium%20Ion%20LG%20INR%2021700%20M50LT%202021-LSD-MBD-b00002_21700_M50LT_PS_Promotion_V1.pdf",
                 "https://lygte-info.dk/review/batteries2012/LG%2021700%20M50T%205000mAh%20(Gray)%20UK.html",
                 "https://cellsaviors.com/cell-database/lg-m50lt"]
    },
    "samsung_50e": {
      "diametro_mm": 21.1, "altura_mm": 70.6, "diametro_max_mm": 21.25, "altura_max_mm": 70.80,
      "massa_g": 68.7, "massa_max_g": 69.5,
      "topo": "flat", "terminal_positivo_diam_mm_aprox": 9.0, "lata": "aco",
      "cor_involucro": "ciano", "cor_involucro_rgb_aprox": [0.22, 0.68, 0.80],
      "cor_anel_isolador": null,
      "confianca": {"dims_max": "fabricante", "dims_medidas": "forum (HKJ)", "massa_g": "revendedor", "cor": "forum (HKJ)", "terminal": "forum (30T/40T)", "rgb": "estimado"},
      "fontes": ["https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/INR21700_2D00_50E-Cell-Specification_5F00_V1.0_5F00_180711.pdf",
                 "https://lygte-info.dk/info/batteryIndex.html",
                 "https://lygte-info.dk/review/batteries2012/Samsung%20INR21700-50E%205000mAh%20(Cyan)%20UK.html"]
    }
  },
  "pouch": {
    "amprius_sa102": {
      "comprimento_mm": 56.5, "comprimento_corpo_mm": 53.0, "largura_mm": 49.5, "espessura_mm": 5.5,
      "tolerancias_mm": {"L1": 1.5, "L2": 1.5, "W1": 1.5, "T1": 0.4}, "espessura_soc": "30 %",
      "massa_g": 33.1, "massa_tol_g": 0.8,
      "aperto_externo_kpa": 207, "aperto_externo_psi": 30,
      "abas": {"largura_mm": null, "posicao": "não encontrado (estimado: as duas no mesmo lado curto; L1-L2 = 3.5 mm)", "material": null},
      "confianca": "fabricante (PRELIMINARY); abas não encontradas",
      "fonte": "https://amprius.com/documents/Amprius_Product_Catalog.pdf"
    },
    "tattu_semisolido_12ah_pack": {
      "comprimento_mm": 194, "largura_mm": 71, "espessura_mm": 32, "massa_g": 800,
      "alternativa_grepow": {"comprimento_mm": 192, "largura_mm": 71.5, "espessura_mm": 32, "massa_g": 860},
      "celulas": 6, "espessura_por_celula_mm": 5.33, "comprimento_corpo_celula_mm_estimado": 180,
      "conector": "XT90S-F", "balanceador": "G-Tech-7P",
      "cabo_awg_estimado": 10, "cabo_descarga_mm_estimado": 150, "cabo_balanceador_mm_estimado": [65, 85],
      "cor_involucro": null,
      "confianca": "fabricante (dims, massa, conectores); cabos e corpo da célula estimados",
      "fontes": ["https://www.tattuworld.com/products/tattu-380wh-kg-12000mah-6s1p-22-2v-10c-semi-solid-state-uav-lipo-battery.html",
                 "https://www.grepow.com/semi-solid-state-battery/380wh-kg-series-high-energy-density-battery-pack.html",
                 "https://gensace.de/products/tattu-semi-solid-state-380wh-kg-12000mah-10c-22-2v-6s1p-lipo-battery-pack-with-xt90s-f-plug"]
    },
    "tattu_gtech_4s_10ah_pack": {
      "comprimento_mm": 169, "largura_mm": 65, "espessura_mm": 39, "tolerancias_mm": [5, 2, 2], "massa_g": 940, "massa_tol_g": 20,
      "celulas": 4, "espessura_por_celula_mm": 9.75,
      "cabo_awg": 10, "cabo_descarga_mm": 120, "balanceador": "JST-XHR-5P", "cabo_balanceador_mm": 65, "conector": "sem ficha",
      "cor_involucro": "PVC preto, logótipo branco (estimado a partir do 6S 30C)", "cor_involucro_rgb_aprox": [0.06, 0.06, 0.07],
      "confianca": "fabricante (dims, massa, cabos); cor revendedor/estimado",
      "fontes": ["https://www.grepow.com/uav-battery/tattu-4s-10000mah-14-8v-25c-lipo-drone-battery.html",
                 "https://genstattu.com/tattu-10000mah-14-8v-25c-4s1p-lipo-battery-pack-without-plug.html"]
    },
    "gensace_5ah_45c_4s_pack": {
      "comprimento_mm": 158, "largura_mm": 46, "espessura_mm": 31, "tolerancias_mm": [5, 2, 2], "massa_g": 480,
      "espessura_por_celula_mm": 7.75, "conector": "Deans", "cabo_awg": 10, "cabo_descarga_mm": 120, "balanceador": "JST-XHR-5P",
      "cor_involucro": null, "confianca": "fabricante (genstattu)",
      "fonte": "https://genstattu.com/gens-ace-5000mah-4s-45c-14-8v-lipo-battery-pack-with-dean-plug"
    },
    "gensace_5ah_45c_6s_pack": {
      "comprimento_mm": 157, "largura_mm": 46, "espessura_mm": 44, "tolerancias_mm": [5, 2, 2], "massa_g": 682,
      "espessura_por_celula_mm": 7.33, "conector": "EC5", "cabo_awg": 10, "cabo_descarga_mm": 120,
      "balanceador": "G-tech-7P", "cabo_balanceador_mm": 65,
      "cor_involucro": null, "confianca": "fabricante (genstattu)",
      "fonte": "https://genstattu.com/gens-ace-5000mah-6s-45c-22-2v-g-tech-lipo-battery-pack-with-ec5-plug"
    },
    "lipo_1500_4s_75c_pack": {
      "comprimento_mm": 75, "largura_mm": 34, "espessura_mm": 34, "massa_g": 169,
      "celula_estimada_mm": [72, 34, 8.5], "massa_celula_g_estimada": 40,
      "conector": "XT60", "balanceador": "JST-XH-5P",
      "confianca": "revendedor (Lumenier/RDQ); célula estimada",
      "fonte": "https://www.racedayquads.com/products/lumenier-1500mah-4s-75c-lipo-battery"
    }
  },
  "pack_6s2p_21700": {
    "disposicao": "6x2, células paralelas; grupos = colunas de 2 com polaridade alternada",
    "faces": {"A": ["1-2", "3-4", "5-6"], "B": ["2-3", "4-5", "P- (G1-)", "P+ (G6+)"]},
    "balanceamento_pinos": ["1=P- (G1-)", "2=G1+/G2-", "3=G2+/G3-", "4=G3+/G4-", "5=G4+/G5-", "6=G5+/G6-", "7=P+ (G6+)"],
    "envelope_estimado_mm": [129.3, 43.1, 74.0],
    "referencias_comerciais_mm": {"wrekd_p50b": [139, 48, 72, 900], "auline_s70": [132, 43, 75, 849], "strix_50s": [129, 45, 79, 915]},
    "confianca": "disposição e faces: estimado (derivação); referências: revendedor"
  },
  "fitas": [
    {"material": "niquel_puro", "espessura_mm": 0.15, "largura_mm": 8, "corrente_A_conservador": 5.0, "corrente_A_aceitavel": 7.5, "corrente_A_otimista": [10, 15]},
    {"material": "niquel_puro", "espessura_mm": 0.20, "largura_mm": 8, "corrente_A_conservador": 6.4, "corrente_A_aceitavel": 9.6, "corrente_A_otimista": [15, 25]},
    {"material": "niquel_puro", "espessura_mm": 0.20, "largura_mm": 10, "corrente_A_otimista": [30, 40]},
    {"material": "niquel_puro", "espessura_mm": 0.30, "largura_mm": 8, "corrente_A_conservador": 10.0, "corrente_A_aceitavel": 15.0, "corrente_A_otimista": [40, 60]},
    {"material": "cobre", "espessura_mm": 0.20, "largura_mm": 8, "corrente_A_otimista": [35, 50]},
    {"material": "sanduiche_cobre_niquel", "espessura_cobre_mm": 0.10, "espessura_niquel_mm": 0.15, "largura_mm": 8, "nota": "Cu ≤ 0.10–0.15 mm para soldar através do Ni; recomendado para 50 A"}
  ],
  "isolamento": {
    "anel_papel_peixe_21700": {"diam_ext_mm": 19.8, "diam_int_mm": 10.5, "espessura_mm": 0.2, "alternativas": [[21, 12, 0.2], [18, 10, 0.3]], "cores_vistas": ["ciano", "verde", "preto"]},
    "suporte_21700": {"furo_mm": [21.3, 21.7], "passo_mm": [23.0, 23.4]},
    "termorretratil_pvc": {"parede_antes_mm": 0.15, "encolhimento_transversal": [0.40, 0.45], "cores": ["azul-ceu", "verde", "preto", "vermelho", "transparente", "amarelo", "azul transparente"]}
  },
  "cabos": {
    "awg10_silicone": {"fios": "1050x0.08mm", "diam_ext_mm": [5.4, 5.5]},
    "awg8_silicone": {"fios": "1650x0.08mm", "diam_ext_mm": 6.5},
    "balanceamento": {"awg": 22, "material": "silicone", "comprimento_mm": [65, 200]}
  },
  "conectores": {
    "xt90h": {"contacto_diam_mm": 4.5, "passo_mm": 11.0, "largura_mm": 21.0,
              "macho_com_tampa_mm": [31, 21, 10], "femea_sem_tampa_mm": [20, 21, 11],
              "amass_ocr_comprimentos_mm": {"F_com_tampa": 30.7, "F_sem_tampa": 26.2, "M_com_tampa": 29.7, "M_sem_tampa": 25.2},
              "massa_macho_g": 6, "massa_par_g": 12.8, "cor": "amarelo (G.Y) ou preto (N.B)", "cabo_awg_recomendado": 10, "corrente_A_amass_2026": 45,
              "confianca": {"contacto": "fabricante", "passo": "forum", "caixa": "revendedor", "ocr": "estimado"}},
    "xt90s_f": {"dims_mm": [31, 21, 9], "massa_g": 9, "amass_ocr_comprimentos_mm": {"com_tampa": 31.1, "sem_tampa": 26.6}, "anti_faisca": true, "confianca": "revendedor (mjbots)"},
    "xt60": {"contacto_diam_mm": 3.5, "passo_mm": 7.2, "femea_mm": [20.5, 16.0, 8.1], "macho_mm": [20.2, 15.7, 7.7],
             "xt60h_comprimento_com_tampa_mm": {"F": 23.8, "M": 23.5}, "corrente_A_amass_2026": 35,
             "confianca": {"passo": "revendedor", "dims": "fabricante via OCR (eixos estimados)"}},
    "jst_xh_7p": {"passo_mm": 2.5, "largura_mm": 19.8, "vao_pinos_mm": 15.0, "profundidade_mm": 5.7, "altura_mm": 7.5,
                  "material": "PA6 natural (branco)", "awg": [28, 22], "corrente_A": 3, "confianca": "fabricante (JST)"},
    "gtech_7p": {"descricao": "JST-XH compatível + pino extra atrás", "dims_mm": null, "confianca": "forum"}
  }
}
```
