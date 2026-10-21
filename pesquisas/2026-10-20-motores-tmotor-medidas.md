# Motores T-Motor e hélice P15×5 — medidas REAIS para o detalhe visual (2026-10-20)

Pedido do dono: «os motores tudo verificado, e quero que cada motor tenha a forma igual e o tamanho como ele realmente
é». Este documento é a base factual de `lab/drone_rpi/detalhes/motores.py`: para cada motor do catálogo
(`models/drone_rpi/componentes.json`) e do painel da troca ao vivo (`CATALOGO_MOTORES_PAINEL`), as cotas, de onde saíram e
o que ficou estimado. Conteúdo web = dado não confiável, só citado.

## 1. Método

1. **Modelos 3D oficiais da T-Motor** (centro de downloads, STEP): o texto dos ficheiros veio pela CLI Tavily (`extract`)
   e foi reconstruído e tesselado (gmsh 4.15 / OpenCASCADE) **fora do repositório** (scratchpad), só para MEDIR:
   cortes meridionais (perfis r–z), cortes horizontais (contornos), plantas rasterizadas (largura dos raios do topo) e os
   parâmetros analíticos da B-rep (cilindros: furos, janelas). As malhas do simulador são NOSSAS (perfis, plantas
   trianguladas e lajes geradas por código a partir destas cotas), não cópias do CAD.

   | STEP | origem | ficheiro |
   |---|---|---|
   | https://cn.tmotor.com/uploadfile/downloads/tmotor-mn4004-motor-3d-model.step | Siemens NX 10, 2021-09-25 | 7 sólidos (tampa, veio, anel, base, 2 rolamentos, estator) |
   | https://cn.tmotor.com/uploadfile/downloads/tmotor-mn4006-motor-3d-model.step | NX 7.5, 2020-05-19 | 1 sólido (fundido, estator simplificado) |
   | https://cn.tmotor.com/uploadfile/downloads/tmotor-mn5006-motor-3d-model.step | CATIA V5, 2019-11-01 | 5 sólidos (anel, veio, copo, tampa, base; sem estator) |
   | https://cn.tmotor.com/uploadfile/downloads/tmotor-mn2806-motor-3d-model.step | Creo, 2023-11-15 | 17 sólidos (tampa, anel, veio, base, 2 × 694, anel E) |
   | https://cn.tmotor.com/uploadfile/downloads/tmotor-mn3508-motor-3d-model.step | NX 10, 2021-06-30 | 1 sólido (interior simplificado) |

2. **Fichas do fabricante** (store.tmotor.com / uav-en.tmotor.com) para massa, cabos, configuração e rolamentos; lojas
   (rcdrone.top, getfpv) para o que a T-Motor não escreve (cor, montagem da hélice); dronehitech para o 2306.
3. **Verificação na malha COMPILADA** (`scratchpad/motores/tools/medir.py`): Ø, altura do corpo e total, furos da base
   contra `padrao_base`, base assente na placa e hélice assente no topo — para o motor de cada build e para cada variante
   (resultado na secção 5). `folgas.py`: nenhum cabo/pá atravessa o motor, a placa ou o braço, com cada variante ligada.

Convenção (todas as cotas em mm): z = 0 na face de BAIXO da base, eixo z para cima; «corpo» = da face de baixo da base
ao topo da tampa do rotor; «total» = com o pino do veio por cima e a ponta do veio por baixo.

## 2. Motores

### T-Motor Antigravity MN4004 (KV300 e KV400 — mecanicamente iguais)
- **Ø 44,35 · corpo 19,0** (CAD = ficha «Φ44.35×19mm»: a ficha NÃO conta o veio) · total 27,3 (pino Ø3 × 6,0 por cima,
  ponta Ø4 × 2,3 por baixo com a ranhura do anel E Ø3,5). Fonte: STEP; https://store.tmotor.com/product/mn4004-kv300-motor-antigravity-type.html
- Estator (CAD): **Ø39 × 4**, furo Ø15, coroa Ø20, **18 dentes** de 2,0 mm com sapatas de ±6,88° (abertura 2,06 mm) —
  «18N24P» (ficha). Veio Ø4 (a ficha diz «Shaft Diameter 40mm»: gralha). Rolamentos 4 × 11 × 4 (694ZZ) no CAD.
- **Base** (CAD): disco Ø30, placa **2,3 mm**, **4 × M3 (Ø2,4 roscado) no Ø25** (0°/90°/180°/270° do CAD), 4 janelas
  em rim (r 8,5–13,5, pontas r 2,5 a ±19,1° do eixo da janela, a 45° do CAD), tubo dos rolamentos Ø16 até z 7,0 e o
  assento do estator Ø15 até z 11. A rosca útil é a espessura da placa: 2,3 mm (= 0,77·d — é o desenho da T-Motor).
- **Rotor** (CAD): anel de aço 0,8 mm (r 21,37–22,17) de z 6 a 12 com o lábio de baixo; tampa de alumínio de z 8 a 19:
  placa do topo 2,3 mm (z 16,7–19), cone de ~22° de r 10 a r 20,9, filete até ao aro (topo do aro z 12,75). **6 raios**
  com janelas em LENTE: duas circunferências R 18,012 de centro a 24,47 mm, a ±24,1° do eixo da janela (cada uma limita o
  lado oposto) e a ponta arredondada por um filete r 4,5 centrado a 13,23 (ponta a r 8,73). Topo: **4 × M3 (Ø2,48) no
  Ø12** (a 45° do CAD) — a fixação T-mount das hélices T-Motor.
- Cabos: **50 mm** (ficha «Lead 50mm»), fio ESMALTADO (a série escreve «Lead: Enameled Wire» nas fichas do MN4006 EVO e
  do MN2806 — o tipo no MN4004 é inferido). Massa **53 g** com cabo (ficha; getfpv 52 g).
- Cor: **preto** (alumínio anodizado; getfpv «2 Black Motors», rcdrone «black housing, exposed copper windings»).

### T-Motor Antigravity MN4006 KV380
- **Ø 44,35 · corpo 21,0** (= ficha «Φ44.35×21mm») · total 29,3 (pino Ø3 × 5,8; ponta 2,5 por baixo). Fonte: STEP;
  https://store.tmotor.com/product/mn4006-kv380-motor-antigravity-type.html
- Igual ao MN4004 (mesma base, mesmos furos, mesma tampa e janelas — cilindros idênticos no STEP) com o estator de
  **6 mm** (z 7–13); o CAD traz o estator simplificado num bloco (Ø37,7): usa-se a chapa do MN4004 (Ø39), ESTIMADO.
- Cabos «Enameled Wire 50mm» e 694ZZ (https://store.tmotor.com/product/mn4006-EVO-kv380-motor-antigravity-type.html).
  Massa **68 g** com cabo (57 g sem). Cor preto.

### T-Motor Antigravity MN5006 (KV450 e KV300 — mecanicamente iguais)
- **Ø 55,6 · corpo 25,0 · total 29,9** — a ficha «Φ55.6*30mm» conta o PINO do veio (4,9 mm por cima). O cilindro com
  massa do catálogo (55,6 × 30) é, por isso, 5 mm mais alto do que o corpo real (a malha tem a cota real). Fonte: STEP;
  https://store.tmotor.com/product/mn5006-kv450-motor-antigravity-type.html
- **Base em CRUZ** (CAD): placa **3,5 mm**, disco Ø17 e 4 braços de 5 mm até Ø30 (cantos r 1,2), **4 × M3 (Ø2,5) no
  Ø25** nos braços, 4 pilares até z 7 e o anel de suporte do estator (r 12–13, z 6–15, com entalhes sobre os furos).
- Veio **Ø6 oco** (rosca M3 por dentro em baixo), colar Ø7,9 no topo da tampa e **pino Ø4 × 4,9**; em baixo um COPO de
  retenção Ø10 com um parafuso M3 de cabeça de embeber (a face fica 0,5 mm acima da face da base — nada sai por baixo).
  696ZZ (ficha). 24N28P (ficha).
- Rotor: anel de aço 1,0 mm (r 26,8–27,8) de z 8,25 a 16,75; 28 «dedos» que posicionam os ímanes (r 25,5–26,8); tampa
  com placa de 3,0 mm (z 22–25), cone de 15° até r 25,6, aro (topo z 18,5). Janelas em lente (ajustadas à planta
  rasterizada, erro máx. 0,28°): R 15,90 a 27,03 mm, ±11,54°; filete r 7,01 a 19,51 (ponta r 12,5). Topo: **8 × M3**:
  4 no **Ø12** e 4 no **Ø18**.
- Estator NÃO vem no STEP: **Ø50 × 6** (pela designação T-Motor), 24 dentes — ESTIMADO.
- Cabos: **80 mm** («Lead Cable 80mm», loja T-Motor; o rcdrone diz 60 mm). Massa **106 g** (KV450) / 108 g (KV300).
- Hélice: «2 × M3×10, tampa e adaptador» e o kit com «two socket-head screws, a brass spacer ring, and a round black
  adapter plate» — https://rcdrone.top/products/src-mn5006-mn5006-antigravity-type-4-6s-uav-motor-kv300 . Cor preto.

### T-Motor Antigravity MN2806 (KV400 e KV650)
- **Ø 35,0 · corpo 18,4 · total 26,0** — a ficha «Φ35*26» conta o VEIO (5,5 por cima + 2,1 por baixo); a ficha do EVO
  diz «Φ34\*26mm» (o CAD dá 35,0). Fonte: STEP; https://store.tmotor.com/product/mn2806-motor-antigravity-type.html ,
  https://store.tmotor.com/product/antigravity-mn2806-evo-motor.html
- **Base** (CAD): disco Ø30, placa 2,3 mm, **padrão MISTO: 2 × M3 no Ø25 (45°/225°) + 2 × M3 no Ø19 (135°/315°)**,
  4 janelas trapezoidais (r 7,5–13,5; cantos r 2 a (9,5 mm, ±16,7°) e (11,5 mm, ±22°)), **entalhe a 180°** (4,6 mm) —
  «Wires lead out from the side-bottom of the motor» (loja). Tubo com cone até ao assento do estator (r 6,5, z 12,7).
- Veio Ø4 com colar Ø6 no topo da tampa, **pino Ø4 × 5,5**; anel E por baixo (no CAD); 694ZZ × 2 (CAD e ficha).
- Rotor: anel de aço (r 16,02–17,5, z 5,9–13,7); tampa com placa 2,2 mm (z 16,2–18,4), janelas em lente R 11,336 a
  18,48 mm ±14,4°, filete r 4,0 a 12,18; topo **4 × M3 (Ø2,5) no Ø12**.
- Estator não vem no STEP: **Ø28 × 6** (designação), 12N14P (ficha) — ESTIMADO. Cabos «Enameled Wire 50mm».
  Massa **46 g** (EVO 45 g). Cor preto (rcdrone: «black housing, copper windings»).

### T-Motor Navigator MN3508 KV380 (série diferente — aspeto diferente)
- **Ø 41,8 (o CAD tem uma cinta de Ø42,0 a meio do copo) · corpo 26,5** (= ficha «Φ41.8×26.5mm») · total 35,0 (pino Ø4 ×
  6,1; ponta 2,4 por baixo). Fonte: STEP; https://store.tmotor.com/product/mn3508-motor-navigator-type.html
- **Copo FECHADO** (o rotor é uma lata cilíndrica de z 4 a 20, com dois frisos em baixo), tampa com 6 raios quase radiais
  (janelas: lente ajustada R 31,49 a 34,95 ±45,45°, filete r 3,91 a 12,63), topo **4 × M3 (Ø2,5) no Ø12** (0°/90°).
- **Base** (CAD): placa 2,6 mm com 4 braços (arcos de Ø29 nas pontas) e recortes circulares entre eles, **4 × M3 no
  Ø25** — rcdrone: «4-M3; Φ25; Φ12; Φ4» (https://rcdrone.top/products/src-mn3508_kv380-mn3508-multirotor-fixed-wing-uav-motor-kv380-kv580-kv700); aba
  de 0,8 mm até Ø34 e uma COROA em 8 setores que sobe até r 19,3 a z 3,4.
- Estator **Ø35 × 8** (ficha «Stator Diameter 35mm / Stator Height 8mm»), 12N14P; o CAD tem o interior num bloco.
- Cabos **600 mm, 18 AWG** silicone (ficha; desenha-se o arranque). Massa 103 g com cabo / 82 g sem.
- Cor: **PRATA** (rcdrone: «silver housing», «silver frame»).

### Motor 2306 genérico (5″ FPV — `ref_2306_2450kv`, referência do plano)
- Sem desenho oficial: classe **T-Motor F40 PRO** — **Ø27,9 × 16,5** (corpo), estator 23 × 6, 12N14P, veio Ø4 com o
  perno **M5** da hélice, montagem **16 × 16 M3**, cabos 18 AWG 100 mm (F40 PRO V: 20 AWG 150 mm, 27,8 × 31,4 mm com o
  veio). Fontes: https://dronehitech.com/t-motor-f40-pro-vs-f40iii e as lojas citadas nessa pesquisa. O catálogo diz
  28 × 18 (estimado): fica como está (a física usa-o); a malha usa 27,9 × 16,5 e o perno com 13 mm (total 31,1).

## 3. Hélice T-Motor P15×5 CF «polish» e a fixação ao motor

- 381 × 127 mm, 21 ± 1,5 g por pá, CF + epóxi, «2blades-integrated» — https://store.tmotor.com/product/polish-carbon-fiber-15x5-prop.html
- Cubo T-mount: **furo central Ø6 e 2 furos Ø3 a 12 mm entre centros** («prop shaft size 6mm · mounting bolt hole size
  3mm · spacing 12mm» — https://www.facebook.com/groups/1737736206469442/posts/3016248608618189). Os 2 furos caem em dois
  dos 4 furos M3 no Ø12 do topo do motor.
- Aperto (T-Motor, hélices de 14–18″): **2 × M3×10** de cabeça cilíndrica, uma **tampa** redonda preta por cima do cubo e
  um **anel de latão** de centragem entre o pino do veio e o furo Ø6 (kit do MN5006, rcdrone acima). A hélice ASSENTA no
  topo da tampa do rotor — sem adaptador.
- **ESTIMADO**: espessura do cubo **6,0 mm** (o pino do MN4004 tem 6,0 e os M3×10 fecham com tampa 1,5 + cubo 6 + 2,5 de
  rosca na placa de 2,3–3,0 mm do topo), Ø do cubo 22 mm, tampa Ø16 × 1,5 com furo Ø4,6, anel de latão Ø6 × (Ø do pino).
- Estampagem branca no extradorso junto ao cubo (logótipo/«15*5 CW»): simplificada numa tira.

## 4. Discrepâncias e o que o código faz

| caso | ficha / catálogo | real (CAD) | no simulador |
|---|---|---|---|
| MN5006 altura | 30 mm | corpo 25,0 + pino 4,9 | cilindro físico 55,6 × 30 (catálogo, não mexido); malha 25,0 + pino |
| MN2806 altura | 26 mm | corpo 18,4 + veio 5,5 + 2,1 | idem: malha real |
| MN2806 Ø | 35 (loja) / 34 (EVO) | 35,0 | 35,0 |
| MN3508 Ø | 41,8 | 41,8 com cinta de 42,0 | como o CAD |
| MN4004 veio | «40mm» | Ø4 (pino Ø3) | Ø4 / Ø3 |
| MN5006 cabos | 80 mm (T-Motor) | 60 mm (rcdrone) | 80 mm |
| 2306 | 28 × 18 (estimado) | F40 PRO 27,9 × 16,5 | malha 27,9 × 16,5 |
| plano das hélices | z do rotor físico = topo do cilindro + 8 mm (`modelo.py`) | a hélice assenta no topo do motor | as pás desenham-se assentes no topo (4 mm abaixo do plano físico no MN4004, 10 mm no MN5006) e o disco translúcido `helice{k}` (grupo 2) passa a coroa no plano das pás reais; o site `r{k}`, a física e a aero não mudam |

Cores do painel (`CATALOGO_MOTORES_PAINEL`): todas as Antigravity são PRETAS (anodizado) e a Navigator MN3508 é PRATEADA —
as cores antigas (prata-titânio, vermelho, azul, dourado, verde) não existem nestes motores.

## 5. Verificação (medido na malha compilada, 2026-10-20)

`medir.py` — Ø / corpo / total e o que a ficha conta (±0,3 mm), base assente na placa, hélice assente no topo (com o dz
da variante) e os 4 furos M3 da base (sem material no centro nem a 1,15 mm, material a 1,9 mm) = `padrao_base`:

| motor | Ø | corpo | total | ficha | furos |
|---|---|---|---|---|---|
| MN4004 KV300/KV400 | 44,34 | 19,00 | 27,30 | 44,35 × 19 (corpo) ✓ | 4/4 ✓ |
| MN4006 KV380 | 44,34 | 21,00 | 29,30 | 44,35 × 21 (corpo) ✓ | 4/4 ✓ |
| MN5006 KV450/KV300 | 55,60 | 25,00 | 29,90 | 55,6 × 30 (total) ✓ | 4/4 ✓ |
| MN2806 KV400 | 35,00 | 18,40 | 26,00 | 35 × 26 (total) ✓ | 4/4 ✓ |
| MN3508 KV380 | 42,00 | 26,50 | 35,00 | 41,8 × 26,5 (corpo) ✓ | 4/4 ✓ |
| 2306 (F40 PRO) | 27,90 | 16,50 | 31,10 | 27,9 × 16,5 (corpo) ✓ | 4/4 ✓ |

### Verificação final (todos os módulos, 2026-10-20 03:10)

- `medir.py` com `DRONE_DETALHES=todos` e `=motores` em 6 builds (endurance, articulado, referencia_5pol, compacto_12pol,
  pesado_18pol, lipo_15pol): **MEDIÇÃO OK**. A base assenta na face de baixo do motor físico (= topo da placa do motor que a
  `estrutura` desenha); a altura da placa vem do cilindro `suporte_motor_{k}` só para os parafusos (de baixo para cima).
- `folgas.py` (distância ponto–triângulo na malha compilada; o `mj_ray` não acerta em malhas só visuais): todas as variantes
  com folga ≥ +0,06 mm, sem interpenetração (no articulado os cabos descem a direito por fora da placa, r ≥ 33 mm).
- `ver --so todos` e `--so motores`: TUDO OK (13/13 builds; física idêntica bit a bit) · auditoria F1–F4/P1 TUDO OK ·
  `exportar --resumo` sem «sem peça».

Desempenho (RTX 4070; malhas na cache em disco; máquina com outros agentes a correr, carga ≈ 5 — números pessimistas):

| build | módulos | ngeom | faces | carregar 1.ª / 2.ª chamada (s) | fps 1080p |
|---|---|---:|---:|---|---:|
| articulado_15pol_mn5006 | todos | 786 | 537 372 | 1,61–1,88 / 1,40–1,62 | 349–363 |
| endurance_15pol_p50b | todos | 540 | 409 732 | 1,16 / 1,00 | 364 |
| articulado_15pol_mn5006 | motores | 409 | 84 144 | 0,07 / 0,05 (sem cache: 0,42) | 401 |
| endurance_15pol_p50b | motores | 342 | 85 408 | 0,07 / 0,05 | 410 |

Por módulo (articulado, chamada quente): motores 0,04 s; o resto do custo dos motores aparece nos `fios` (1,02 s contra
0,90 s com o motores.py antigo): a grelha de triângulos dos fios é só em **xy** (células de 10 mm), por isso cada sonda ao
longo do mastro vertical recolhe todos os triângulos visíveis do motor (MN5006: 16 k por rotor, já com o nível de detalhe
reduzido) antes de os filtrar por z. Uma grelha 3D (ou um filtro por z antes da recolha) no `_GrelhaTri` tira esse custo.
