"""lab/drone_rpi/detalhes/estrutura.py — ESTRUTURA realista (frame DIY de carbono) e o MECANISMO dos braços
articulados (ombro com servo + sem-fim autobloqueante, cotovelo de acionamento direto), com as FERRAGENS reais (cada
parafuso num furo real, cabeça assente, porca autoblocante com rosca de fora) — só VISUAL: massa 0, sem contacto,
grupo 3 (as regras do `Contexto`); a física fica igual bit a bit (`python -m lab.drone_rpi.detalhes.ver --so estrutura`).

O QUE SE DESENHA (mm; peça do registo entre parênteses; «estimado» = sem cota publicada, com a razão)

  frame (todos os builds)
    · placa de baixo 208 × 208 × 3 (`placa_inferior`) em carbono 3K tafetá (textura embutida: xadrez de mechas de 2,5),
      cantos chanfrados no rígido / ENTALHES no articulado (caixa do redutor, encoder e o varrimento do cubo), furo de
      cablagem, os rasgos das cintas da bateria que a eletrónica publica (`notas["rasgos_cintas"]`) e furos de alívio — e os FUROS de todos os parafusos que a atravessam (os
      nossos e os da eletrónica/motores, lidos do registo de ferragens: eixo vertical e haste a cruzar a laje); o furo
      de alívio de (0,77·L, −0,29·L) é a SUBIDA DO FPC da câmara CSI: Ø 14 nas placas pequenas (x500, compacto) e, quando
      cai por cima da bateria (lipo, semissólido, x500, compacto), passa para |y| = meia-largura do pack + 7 (a maior
      das variantes do painel) — `_fpc_placa_carbono`; nos outros builds fica onde sempre esteve;
    · placa de cima (`placa_superior`, o mesmo geom reestilizado) com a janela da pilha, rasgos de alívio, os furos dos
      parafusos e, no articulado, 4 ORELHAS (a mesa dos servos do ombro) e a passagem do veio de cada sem-fim;
    · 4 espaçadores de alumínio Ø5 × 12,8 M3 fêmea-fêmea (`espacadores`: os geoms `espacador_placa_*` reestilizados),
      1 ISO 4762 M3 × 8 por cima e outro por baixo (≥ 1,5·d de rosca metida em cada ponta);
  build rígido (tubo 25 × 23 do catálogo, eixo a −10 mm: o TOPO a +2,5 mm, onde a eletrónica assenta os ESC)
    · abraçadeira do canto da placa (`abracadeira_tubo`): 2 metades CNC pretas à volta do tubo, 4 × M3 + porca ISO 10511
      nas orelhas, e as MAXILAS da metade de cima que abraçam o canto da placa (2 × M3 verticais + porca); quando o
      ESC À VISTA do `eletronica` passa por cima do meio das maxilas (frames de 650/750), os 2 M3 vão para ORELHAS
      laterais das maxilas, 0,55 mm por fora dele (`_maxila_fora_do_esc`; só se couberem na placa);
    · suporte do motor (`suporte_motor`): abraçadeira de 2 metades vermelha no fim do tubo + a PLACA do motor (o geom
      `suporte_motor_k` reestilizado, de pos−size até à base do motor: assim os parafusos dos motores assentam) com os
      furos de `motores.padrao_base(hw.motor)` + o furo central + alívios e o entalhe por onde entra a abraçadeira (que
      pára antes das cabeças dos parafusos do motor);
    · varões de travamento Ø8 (`trelica`: os geoms `trelica_estab_*`): abraçadeira de fenda no tubo com 2 linguetas,
      e em cada ponta do varão um casquilho com GARFO que abraça a lingueta com um pino (M3 + porca) — os varões
      chegam aos tubos a 45°; a abraçadeira vai para onde couber entre as outras peças (0,34 do braço no 1950); com as
      balas das fases do `motores` logo a seguir a ela (x500, compacto) o anel leva uma face plana 1,5 mm mais baixa;
    · trem de pouso (`perna`): abraçadeira de 2 metades no tubo (1 × M3 + porca de cada lado), casquilho da perna com perno
      DIN 916, perna de carbono Ø12 (a cápsula física) e pé de borracha com o fundo no ponto de contacto da cápsula;
  build articulado (cada peça no CORPO que roda como ela; laranja = as peças que RODAM com uma junta)
    OMBRO (eixo y a 150 mm do centro, no plano da placa de baixo)
      · caixa do redutor (`ombro_caixa`, corpo `drone`): paredes de 6 mm com os 2 × 6800ZZ (10×19×5) nas faces de fora
        e rebordo de 1 mm, fundo e tampa com os 2 × 685ZZ (5×11×5) do sem-fim (ressaltos Ø15) e os rebaixos dos anéis E,
        aba aparafusada à placa de baixo (2 × M3 + porca), janela de policarbonato à frente (4 × ISO 4762 M2,5 inox
        nas paredes: mostra a coroa e o cubo com os pernos) e janela de inspeção na parede de dentro (2 × M2,5: mostra
        o sem-fim a engrenar), e a escala −40…+40° na face de fora;
      · veio de saída Ø10 (`ombro_veio`, corpo `braco{k}`) retido por 2 anéis E DIN 6799 (ranhura 8) contra os anéis
        interiores dos 6800, coroa de bronze z = 20, m 0,8, dentes de flanco a 20° TORCIDOS do avanço λ = 3,81° (a
        hélice do sem-fim) com cubo de 2 pernos DIN 916 M2,5 × 2, e o íman diametral Ø6 na ponta de dentro;
      · sem-fim de aço de 1 entrada (d₁ 12 → Ø13,6, passo π·m = 2,513, rosca DIREITA nos 4 braços: o espelho dos braços 3
        e 4 troca a mão no canónico), veio Ø5 nos 2 × 685ZZ com anéis E (ranhura 4), acoplamento de alumínio aparafusado
        ao horn (4 × ISO 4762 M2 × 4 nos furos roscados do horn) com o perno DIN 916 M3 × 3 a apertar o veio, e o horn
        HN12-N101 do servo com o parafuso central WB M2,5 × 6: tudo isto GIRA 20× o ombro — geoms `semfim{k}_rotor_*`
        (um por material) no corpo `drone`, eixo em `ctx.eixo("semfim{k}", …, razao=20, sentido=−sx)`: rosca direita do
        lado −x da coroa → o sem-fim roda −20·q em torno de +z quando o ombro roda +q em torno de +y (do lado +x: +20·q);
      · servo XH430 do ombro (`ombro_servo`) deitado com o horn para baixo, 12,3 mm acima da placa de cima (o espaço do
        acoplamento e do perno), preso pelos 2 TOPOS (2 × M2,5 × 4 em cada um) a 2 cantoneiras de alumínio de 2 mm
        aparafusadas à placa de cima — a do lado do horn com 2 × M3 × 10 que roscam na tampa da caixa do redutor (e
        apertam a placa contra ela), a outra com 2 × M3 + porca por baixo da placa;
      · encoder AS5048A (`ombro_encoder`): placa 22 × 28 em 4 pilares M2,5 × 6 macho-fêmea de latão roscados na parede
        de dentro, 4 × ISO 4762 M2,5 × 5, chip a 0,75 mm do íman (entreferro 0,5–2), barra de 6 pinos (SPI);
      · cubo do braço (`ombro_cubo`, laranja): abraçadeira de fenda no veio (1 × M3 + porca, fenda a 225°: longe do
        ponteiro) unida ao casquilho do tubo a 45° (fenda por baixo, 2 × M3 + porca), ponteiro vermelho sobre a escala;
    COTOVELO (eixo y na ponta do braço; o servo É o pivô)
      · servo XH430 (`cotovelo_servo`, corpo `braco{k}`) de lado, preso por baixo ao BERÇO com 4 × M2,5 × 5 nos furos da
        face lateral; berço + casquilho do tubo (`abracadeira_tubo`, fenda de lado, 2 × M3 + porca); escala −60…+60°;
      · no corpo `mastro{k}` (RODAM com o cotovelo): o horn HN12-N101 e o idler HN12-I101 (`cotovelo_servo` /
        `cotovelo_garfo`), o GARFO laranja no padrão FR12-H101K (braços de 3 mm, 4 × ISO 4762 M2 × 5 em cada lado nos
        furos M2 DP2.0 do horn e do idler, ponte a 39 mm do eixo: passa por cima da caixa do servo em ±60°), a
        abraçadeira de fenda do mastro (1 × M3), o tubo Ø16 (`mastro`) e, em cima, a abraçadeira da placa do motor
        (1 × M3) com o pescoço que deixa livres as cabeças dos parafusos do motor e a placa do motor (`suporte_motor`).
    Folgas MEDIDAS (distância exata triângulo a triângulo entre o que roda e o que fica, em todo o curso — ombro ±40°,
    cotovelo ±60°, mira ±35° com a IK, extremos combinados — com o sem-fim a girar 20×, braços 1 e 3 (espelhado)):
    engrenamento sem-fim/coroa 0,142 mm (folga de 0,12·p, constante: perfis conjugados), anel E do sem-fim ↔ caixa
    0,22, anel E do veio ↔ blindagem do 6800 0,25, horn/idler ↔ rebaixo do servo 0,30, ponteiro ↔ escala 0,55, íman ↔
    chip 0,75 (o entreferro), acoplamento ↔ placa de cima 0,80; tudo o resto > 1 mm. Nenhum contacto. Em repouso
    (número de enrolamento dos vértices, > 0,3 mm): nenhuma peça da estrutura dentro de outra, nem da eletrónica/motores.

  build ACESSÍVEL `articulado_15pol_abs` (mecanismo `ombro_fuso_impresso_cotovelo_servo`, frame `…_1950_abs`; o código
  entra por `hw.bracos.id` — os builds antigos desenham-se exatamente como antes, malha a malha) — peças compradas
  baratas + IMPRESSAS em ABS (materiais `est_abs_*`; cada peça impressa = lajes extrudidas fechadas que se tocam,
  registada em `notas["impressas"]["<peça>#<k>"]` com o nome, a orientação de impressão e o volume pela malha)
    OMBRO = dobradiça + ATUADOR LINEAR DE FUSO (a geometria A/B é a do catálogo, `mecanismos_braco.<id>.ombro.fuso`,
    que este desenho publicou: alavanca a = (−50, 24, 0), base b = (−38,1, 24, 75,1) mm do eixo H no quadrante +x+y,
    espelhados x → sx·x, y → sy·y; braço de alavanca 38,2–50 mm, L(q) monótono 42,9→107,2 mm, fuso de 150)
      · `ombro_forquilha` (ABS, drone): 2 faces em D com os 608ZZ (assentos abertos para fora, rebordo de 1,5 por
        dentro), costas, aba debaixo da placa de baixo (2 × M3 em insertos) e topo debaixo da placa de cima (2 × M3);
      · `ombro_veio`: varão Ø8 h8 (cruzado pelos rebordos), colar Ø16 × 8 com perno M4 do lado do encoder, espaçador
        do lado do cubo e íman diametral Ø6 × 2,5; `ombro_encoder`: AS5048A em 4 pilares M2,5 × 15 macho-fêmea;
      · `ombro_cubo` (ABS laranja, braço): aperto de fenda no veio (M3), casquilho do tubo Ø25 a 45° (2 × M4), alma,
        e a ALAVANCA — 2 braços com um MR85ZZ cada no pivô A;
      · atuador no plano y = 24 mm (fora da placa): `ombro_bloco` (ABS: 2 × 608ZZ, campânula com janelas, prato do
        motor, 2 insertos M4 do pivô B), `ombro_motor` (JGB37-520 1:18,8 com encoder, veio EXCÊNTRICO), `ombro_fuso`
        (acoplamento 6→8 Ø19 × 25, 2 colares Ø8 a fixar o fuso, fuso Tr8×2 de 1 entrada à direita), `ombro_porca`
        (porca de latão de flange Tr8 em carro impresso, 4 × M3 em insertos, 2 insertos M4 do pivô A);
      · pivôs A e B: 2 parafusos de ombro ISO 7379 Ø5 × 6 (M4) cada, num MR85ZZ por braço do garfo, com espaçador
        e anilha (o ombro aperta a pilha; o anel exterior roda livre); `ombro_suporte` (ABS): torre na placa de cima
        (4 × M3 de baixo para cima em insertos) com o garfo do pivô B e a ponte por trás do bloco;
      · geoms animados (a animação é da planta): `ombro{k}_fuso_base_*` e `ombro{k}_fuso_veio_*` (corpo `drone`,
        rodam em torno de B; o «veio» também gira sobre o fuso) e `ombro{k}_fuso_porca_*` (corpo `braco{k}`, roda em
        torno de A); eixos declarados `ombro{k}_pivo_a/b` (pino) e `ombro{k}_fuso`;
    COTOVELO: `cotovelo_servo` DS3218MG (40 × 20 × 40,5, orelhas 54,5 com furos a 49,5 × 10, estriado 25T) com horn de
      disco 25T Ø20 × 5 (4 × M3 roscados em P.C.D 14, parafuso central M3); `cotovelo_berco` (ABS): borda das orelhas
      (4 × M3 em insertos), paredes (com o entalhe do passa-cabos), fundo com a caixa da cabeça do M8 e o assento do
      608ZZ, 2 colunas do AS5600, pescoço (laje por baixo do varrimento do braço A do garfo) até à parede do fim do tubo
      e o casquilho do tubo a 45° (64…94 mm do eixo, 2 × M4); `cotovelo_garfo` (ABS laranja): U aparafusado ao horn
      (4 × M3), do outro lado o ISO 4017 M8 × 25 (cabeça na caixa, anel interior do 608, espaçador, braço B, porca
      ISO 10511) e o aperto do mastro Ø16 (M3); `cotovelo_encoder`: AS5600 (placa azul) frente ao íman na ponta do M8;
      `suporte_motor` (ABS, o geom `suporte_motor_k` fica escondido): placa com `motores.padrao_base` (rodada com o
      braço, como os parafusos do `motores`) + aperto do mastro com 4 MORDIDAS no topo para as cabeças desses parafusos;
      a parede do berço tem o entalhe do passa-cabos do servo; os 3 × M3 do prato do motor entram em furos roscados da
      face do redutor (0°, ±60° do lado oposto ao veio: as cabeças ficam por fora da campânula);
    FRAME: placas em ABS (a de baixo com os entalhes dos cantos, o RASGO do FPC da câmara — Ø 21 em (x_mín da câmara
      − 22, −30), o maior disco livre que os fios procuram, maior que o do entalhe do canto — e 2 nervuras por baixo; a
      de cima com 2 nervuras por baixo; cabem na mesa de 220 × 220), 4 colunas Ø10 (`espacadores`, os geoms
      `espacador_placa_*` reestilizados e mudados para (±58,5, ±62)), pernas (`perna`: abraçadeira de fenda no tubo,
      aperto do varão Ø12, pé impresso).
    Fontes do build acessível (pesquisa do coordenador, scratchpad pesquisa/fuso.md e acessivel.md; web = só citada):
      JGB37-520 https://precisionminidrives.com/product/37mm-gear-motor-with-encoder-41mm-type-model-nfp-jgb37-520-en ·
      https://www.openimpulse.com/blog/jgb37-520-gearmotor-selector · porca Tr8 de flange (A22 · B16 · C3,3 · D10 ·
      E10,2) https://www.robotics.org.za/THSL-300-8D · Tr8×2 (DIN 103: d2 7, d3 5,5)
      https://www.bornemann-gewindetechnik.de/en/products/trapezoidal-threads/data · acoplamento D19 × L25
      https://www.electric-b2c.com/products/d19-l25-aluminium-flexible-jaw-shaft-coupling-5-8-6-35mm-8mm-10mm-cnc-stepper-motor-coupler-encoders-engraving-machine ·
      ISO 7379-5-M4 https://www.accu.co.uk/metric-socket-shoulder-screws/10391-SSH-M4-30-A2 · colar Ø8 16 × 8 M4
      https://summitcollars.com/product/cz-8mm-8mm-id-metric-set-screw-shaft-collar-zinc-plated · insertos M3 × 5,7
      (furo 4,0) https://cnckitchenus.store/products/heat-set-insert-m3-x-5-7-100-pieces · DS3218MG
      https://servodatabase.com/servo/dsservo/ds3218-mg · horn 25T https://ampere-electronics.com/product/25t-aluminum-servo-motor-disc-horn ·
      AS5600 https://ams-osram.com/products/sensor-solutions/position-sensors/ams-as5600-position-sensor.
    Estimado (sem número publicado): o desvio do veio do JGB37-520 (7 mm) e o círculo dos 6 × M3 (Ø25, usam-se 3),
      a altura das orelhas do DS3218 (7,5–10 mm abaixo do topo), o P.C.D dos furos do horn de disco (14), a placa do
      AS5600 (22 × 28, 2 furos Ø2,6), as espessuras das peças impressas (paredes ≥ 3 mm, faces dos rolamentos 8,5–10).

ÂNCORAS no build acessível (cada uma com `corpo`, `ponto`, `direcao` e uma `nota`; as que giram com um grupo animado
trazem `grupo`): `servo_ombro{k}_ficha_a` = ficha PH2.0-6P do JGB37-520 (motor + encoder Hall) na tampa do encoder,
do lado de DENTRO do atuador (corpo `drone`, `grupo` = `ombro{k}_fuso_base`: gira 0…−9° em torno de B no curso ±40°);
`ombro{k}_pivo_b_cabos` = no eixo do pivô B, 3 mm por fora da cabeça do parafuso de ombro do lado de dentro (fixo no
drone E no atuador: o laço do cabo do motorredutor faz-se aqui, longe do fuso); `servo_ombro{k}_ficha_b` = a barra de
6 pinos do AS5048A (drone); `servo_cotovelo{k}_ficha_a` = a saída do cabo do DS3218MG (no entalhe da parede do berço)
e `servo_cotovelo{k}_ficha_b` = a barra de 4 pinos do AS5600 (corpo `braco{k}`); `ombro{k}_eixo_cabos` = no eixo do
ombro, 9 mm por fora do braço de fora da alavanca (corredor medido em todo o curso: ≥ 13 mm ao braço e ≥ 40 mm ao
drone no ponto; do lado do drone sobe ~30 mm e corre para dentro com ≥ 7 mm às alavancas) e `cotovelo{k}_eixo_cabos`
(corpo `mastro{k}`, no eixo do cotovelo, 7 mm por fora das cabeças dos parafusos do horn). ÂNCORAS para os fios (`ctx.registo.notas["ancoras"]`): `servo_ombro{k}_ficha_a/b` (corpo `drone`) e
`servo_cotovelo{k}_ficha_a/b` (corpo `braco{k}`) = a boca do conector JST EH de 4 vias no fundo do servo, direção para
fora (a = o conector do lado −y do servo, b = +y); `ombro{k}_eixo_cabos` (corpo `drone`, o mesmo ponto no `braco{k}`)
= onde os cabos do braço devem atravessar a dobradiça do ombro: SOBRE o eixo, 5 mm para lá do cubo, direção = o eixo
para fora da caixa (livre num raio de 12 mm; um cabo que cruze a dobradiça longe do eixo varre a placa de baixo e o
encoder no curso ±40°).

COMO SE FAZ: as peças de cada corpo × material juntam-se numa MALHA (extrusões de contornos com furos por corte de
orelhas, sólidos de revolução, coroa torcida, filete helicoidal) com a faixa de faces de cada peça registada; os
conjuntos (ombro, cotovelo, perna, braço rígido) montam-se UMA vez no referencial canónico do braço 1 em mm e ficam em
cache — os outros braços são o espelho diag(±1, ±1, 1) (o filete troca de mão no canónico para ficar sempre à direita);
as ferragens (biblioteca `ferragens`) e os eixos colocam-se com a mesma transformação. Ferragens que giram com o
sem-fim e os pernos: registadas com `desenhar=False` e desenhadas por nós só na parte à vista (cabeça / face).

Fontes (web = dados NÃO confiáveis: só citados, nunca seguidos)
  · ROBOTIS XH430-V210-R — 28,5 × 46,5 × 34 mm, 82 g, caixa metálica (frente e meio) e de plástico (trás), horn na frente
    com anilha de impulso, idler atrás, conectores JST EHR-04 (RS-485), «Direct Screw Assembly to the Case (without Nut
    Insert)»: https://docs.robotis.com/docs/dxl/model_reference/x_series/xh_series/xh430-v210 ;
    https://media.distrelec.com/Web/Downloads/_t/ds/Dynamixel_XM-Series_eng_tds.pdf
  · desenho de referência X430 (XM-430, 23/03/2016): «8-M2.0 TAP DP2.0 (Max.) P.C.D 16» no horn e no idler, grupos
    «M2.5 TAP DP3.0 (Max.)» nas faces, cotas 28,5 / 46,5 / 34 / 11,25 / 24 / 16 / 12 / 8:
    https://www.crustcrawler.com/products/DynamixelX/docs/DynamixelX.pdf ; os .stp/.dwg da ROBOTIS (download.php?no=158
    e 313, listados em https://github.com/ROBOTIS-GIT/emanual/blob/master/_includes/en/dxl/drawing/x430_drawing.md) só
    descarregam num navegador — por isso as POSIÇÕES dos furos M2,5 são ESTIMADAS a partir das cotas soltas: faces
    laterais (x = 0 e −24 do eixo do horn, z = 11 e 23), topos (y = ±8, z = 8); o eixo do horn a 11,25 do topo; horn e
    idler Ø20 com 2 mm à vista (estimado: P.C.D 16 + furo M2 + parede);
  · HN12-N101 (horn + WB M2,5×6 + 10 × WB M2×3 + anilha de impulso): https://robotis.us/products/hn12-n101-set ;
    HN12-I101 (idler + rolamento de plástico + tampa DC12 + 18 × WB M2×3): https://robotis.us/products/hn12-i101-set ;
    FR12-H101K (garfo + HN12-I101 + 4 × FHS M2,5×14 + 18 × WB M2×3 + 8 × WB M2,5×4 + anéis espaçadores):
    https://tribotix.com/product/fr12-h101k-set ; uso dos WB M2×3 nos horns e WB M2,5 + NUT-M2.5 nos quadros:
    https://www.robotsepeti.com/Data/EditorFiles/ya/pololu/OpenManipulator-X_Assembly_Guide_ver1913.pdf ; 4 × M2,5 nos
    cantos da tampa da frente: https://www.youtube.com/watch?v=aYCWsd0GqxU
  · rolamentos 6800 10 × 19 × 5: https://www.bearingbasement.com/en/NTN-6800-Deep-Groove-Ball-Bearings-10x19x5mm/m-65889.aspx ;
    685ZZ 5 × 11 × 5: https://iskbearing.com/product-details/685zz
  · anel E DIN 6799 (veio Ø10 → ranhura 8, Ø16,3, 1,0; Ø5 → ranhura 4, Ø9,3, 0,7):
    https://www.westfieldfasteners.co.uk/Standards/Clip-EClip.html ; https://www.beneri.com/en/prodotto/din-6799
  · AS5048A, placa adaptadora 28 × 22 mm com 4 furos de 2,6 mm, entreferro 0,5–2 mm:
    https://twen.rs-online.com/web/p/sensor-development-tools/2018309 ; https://docs.rs-online.com/0657/A700000006921305.pdf
    (posição dos furos ESTIMADA: a 2,5 mm das bordas)
  · binários de aperto: os de oficina da biblioteca `ferragens` (M2,5 no alumínio da caixa do XH430 ≈ 0,45 N·m, M3 em
    alumínio ≈ 0,8 N·m, aço 12.9 M3 ≈ 1,0 N·m); a ROBOTIS não publica os dos quadros (só avisa para não exceder a
    profundidade dos furos: DP 2,0 no horn, 3,0 na caixa — os comprimentos aqui respeitam-nas);
  · abraçadeiras/suportes CNC para tubo de carbono (a forma):
    https://rcdrone.top/products/aluminum-alloy-drone-tube-clamp-16mm-18mm-20mm-22mm-25mm-30mm-cnc-uav-frame-arm-connector-for-carbon-fiber-tube
  · catálogo do laboratório (`models/drone_rpi/componentes.json`): tubo 25 × 23, placa 208, sem-fim (m 0,8, 1 entrada,
    d₁ 12, z₂ 20, λ 3,81°), raio do ombro 150, mastro Ø16, batentes das juntas, `mecanismos_braco`/`servos`.
"""
from __future__ import annotations

import functools
import heapq
import math
import re
import warnings
from collections import Counter

import mujoco
import numpy as np

from . import ferragens as fer

MM = 1e-3
_TAU = 2.0 * math.pi
LADRILHO_MM = 5.0                      # textura do carbono 3K tafetá: 2 × 2 mechas de 2,5 mm

# ===================================================================================================== medidas (mm)
# DYNAMIXEL XH430-V210-R (ROBOTIS): 28,5 × 46,5 × 34; desenho X430 «FOR REFERENCE ONLY»: 8-M2 DP2.0 em P.C.D 16 no horn
# e no idler, M2,5 DP3.0 nas faces (ver o docstring); referencial do servo: x = altura (topo do lado do horn), y =
# largura, z = profundidade (face do horn em z = 0, trás em z = 34); origem no eixo do horn
SERVO_W, SERVO_H, SERVO_D = 28.5, 46.5, 34.0
HORN_TOPO = 11.25                      # eixo do horn → topo da caixa (cota 11,25 do desenho de referência)
HORN_R, HORN_E, HORN_DENTRO = 10.0, 2.0, 0.7     # horn HN12-N101: Ø20, 2 mm à vista + 0,7 mm no rebaixo (estimado)
REBAIXO_R, REBAIXO_P = 10.4, 1.0                  # rebaixo da caixa à volta do horn/idler (estimado)
PCD_HORN = 16.0                        # 8 furos M2 DP2.0 em P.C.D 16 (desenho)
FUROS_LADO = ((0.0, 11.0), (0.0, 23.0), (-24.0, 11.0), (-24.0, 23.0))   # (x, z) M2,5 DP3.0 nas faces ±y (estimado)
FUROS_TOPO = ((-8.0, 8.0), (8.0, 8.0))                                   # (y, z) M2,5 DP3.0 nos topos ±x (estimado)
CONECTORES = ((-6.6, 30.6), (6.6, 30.6))                                 # (y, z) JST EH 4 vias na face do fundo
DIV_FRENTE, DIV_TRAS = 6.8, 27.2       # frente (metal) | meio (metal) | trás (plástico)
X0_SERVO, X1_SERVO = HORN_TOPO - SERVO_H, HORN_TOPO

R6800 = (5.0, 9.5, 5.0)                # rolamento 6800ZZ 10 × 19 × 5: raio do furo, raio exterior, largura
R685 = (2.5, 5.5, 5.0)                 # rolamento 685ZZ 5 × 11 × 5
MOD, Z2, D1 = 0.8, 20, 12.0            # sem-fim (catálogo): módulo, dentes da coroa, diâmetro primitivo do sem-fim
PASSO_AX = math.pi * MOD               # passo axial = avanço (1 entrada) = 2,513 mm
RP2 = 0.5 * MOD * Z2                   # raio primitivo da coroa (8 mm)
ENTRE = 0.5 * (D1 + MOD * Z2)          # entre-eixos 14 mm
LAMBDA = math.atan(MOD / D1)           # ângulo de avanço 3,81°
FURO_PASSANTE = {"M2": 2.4, "M2.5": 2.9, "M3": 3.4, "M4": 4.5, "M5": 5.5, "M6": 6.6}   # ISO 273 médio

# ombro (referencial canónico do braço 1, mm, origem no eixo da dobradiça: a = x, b = y, z)
B_C = -28.0                            # plano médio da coroa, do sem-fim e do servo do ombro
A_W = -ENTRE                           # eixo vertical do sem-fim
Z_FACE_SERVO_OMBRO = 29.0              # face do horn do servo do ombro (acima da placa de cima: cabe o acoplamento)


# ===================================================================================================== malhas (mm)
def _parte(v, f, t=None):
    v = np.asarray(v, float).reshape(-1, 3)
    f = np.asarray(f, np.int64).reshape(-1, 3)
    t = np.zeros((len(v), 2)) if t is None else np.asarray(t, float).reshape(-1, 2)
    return v, f, t


@functools.cache
def _torno(perfil: tuple, n: int = 24, fase: float = 0.0):
    """Sólido de revolução em torno de z (perfil = polilinhas (r, z) anti-horárias, como `ferragens._torno`)."""
    v, f = fer._torno([list(s) for s in perfil], n, fase)
    ang = np.arctan2(v[:, 1], v[:, 0])
    return _parte(v, f, np.column_stack([ang * np.hypot(v[:, 0], v[:, 1]), v[:, 2]]))


def _comprimentos(c):
    d = np.linalg.norm(np.diff(np.vstack([c, c[:1]]), axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(d)])[:len(c)]


@functools.cache
def _anel_polar(th: tuple, r_ext: tuple, r_int, z0: float, z1: float):
    """Sólido entre dois contornos polares (r(θ) estrelado à volta da origem) de z0 a z1; `r_int=None` = maciço."""
    th = np.asarray(th, float)
    n = len(th)
    re_ = np.asarray(r_ext, float)
    c, s = np.cos(th), np.sin(th)
    P = np.stack([re_ * c, re_ * s], 1)
    V, F, T = [], [], []

    def add(x, y, z, u, w):
        V.append((x, y, z))
        T.append((u, w))
        return len(V) - 1

    arc = _comprimentos(P)
    lo = [add(P[j, 0], P[j, 1], z0, arc[j], z0) for j in range(n)]
    hi = [add(P[j, 0], P[j, 1], z1, arc[j], z1) for j in range(n)]
    for j in range(n):
        j1 = (j + 1) % n
        F += [(lo[j], lo[j1], hi[j1]), (lo[j], hi[j1], hi[j])]
    if r_int is None:
        for z, sinal in ((z0, -1), (z1, 1)):
            ic = add(0.0, 0.0, z, 0.0, 0.0)
            ids = [add(P[j, 0], P[j, 1], z, P[j, 0], P[j, 1]) for j in range(n)]
            for j in range(n):
                a, b = ids[j], ids[(j + 1) % n]
                F.append((ic, a, b) if sinal > 0 else (ic, b, a))
    else:
        ri = np.asarray(r_int, float)
        Q = np.stack([ri * c, ri * s], 1)
        arcq = _comprimentos(Q)
        loq = [add(Q[j, 0], Q[j, 1], z0, arcq[j], z0) for j in range(n)]
        hiq = [add(Q[j, 0], Q[j, 1], z1, arcq[j], z1) for j in range(n)]
        for j in range(n):
            j1 = (j + 1) % n
            F += [(loq[j], hiq[j1], loq[j1]), (loq[j], hiq[j], hiq[j1])]
        for z, sinal in ((z0, -1), (z1, 1)):
            ip = [add(P[j, 0], P[j, 1], z, P[j, 0], P[j, 1]) for j in range(n)]
            iq = [add(Q[j, 0], Q[j, 1], z, Q[j, 0], Q[j, 1]) for j in range(n)]
            for j in range(n):
                j1 = (j + 1) % n
                if sinal > 0:
                    F += [(iq[j], ip[j], ip[j1]), (iq[j], ip[j1], iq[j1])]
                else:
                    F += [(iq[j], ip[j1], ip[j]), (iq[j], iq[j1], ip[j1])]
    return np.array(V), np.array(F, dtype=np.int64), np.array(T)


def _theta(n: int, fase: float = 0.0) -> tuple:
    return tuple(round(fase + _TAU * i / n, 9) for i in range(n))


def _cil(r, z0, z1, n=20, fase=0.0):
    return _anel_polar(_theta(n, fase), (round(r, 6),) * n, None, round(z0, 6), round(z1, 6))


def _anel(r_ext, r_int, z0, z1, n=20, fase=0.0):
    return _anel_polar(_theta(n, fase), (round(r_ext, 6),) * n, (round(r_int, 6),) * n, round(z0, 6), round(z1, 6))


def _sext(af, z0, z1, r_furo=None):
    """Prisma sextavado (af entre faces)."""
    rc = 0.5 * af / math.cos(math.pi / 6.0)
    return _anel_polar(_theta(6, math.pi / 6.0), (round(rc, 6),) * 6, None if r_furo is None else (round(r_furo, 6),) * 6,
                       round(z0, 6), round(z1, 6))


def _ret_arred(hx: float, hy: float, r: float, n: int = 3):
    r0 = min(r, hx, hy)

    def f(recuo: float = 0.0):
        ax, ay = hx - recuo, hy - recuo
        if r0 <= 1e-9:
            return np.array([(ax, ay), (-ax, ay), (-ax, -ay), (ax, -ay)])
        rr = max(r0 - recuo, 0.25 * r0)
        pts = []
        for cx, cy, a0 in ((ax - rr, ay - rr, 0.0), (-ax + rr, ay - rr, 90.0), (-ax + rr, -ay + rr, 180.0),
                           (ax - rr, -ay + rr, 270.0)):
            for i in range(n + 1):
                a = math.radians(a0 + 90.0 * i / n)
                pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        return np.array(pts)
    return f


@functools.cache
def _prisma(hx: float, hy: float, r: float, n: int, z0: float, z1: float, bisel: float = 0.0):
    """Prisma de retângulo arredondado (centrado) com bisel nas arestas de cima e de baixo."""
    fcont = _ret_arred(hx, hy, r, n)
    aneis = ([(fcont(bisel), z0), (fcont(0.0), z0 + bisel), (fcont(0.0), z1 - bisel), (fcont(bisel), z1)]
             if bisel > 0.0 else [(fcont(0.0), z0), (fcont(0.0), z1)])
    m = len(aneis[0][0])
    V, F, T = [], [], []
    for c, z in aneis:
        s = _comprimentos(c)
        for j in range(m):
            V.append((c[j, 0], c[j, 1], z))
            T.append((s[j], z))
    for i in range(len(aneis) - 1):
        a0, b0 = i * m, (i + 1) * m
        for j in range(m):
            j1 = (j + 1) % m
            F += [(a0 + j, a0 + j1, b0 + j1), (a0 + j, b0 + j1, b0 + j)]
    for (c, z), sinal in ((aneis[0], -1), (aneis[-1], 1)):
        cen = c.mean(axis=0)
        i0 = len(V)
        V.append((cen[0], cen[1], z))
        T.append((cen[0], cen[1]))
        for j in range(m):
            V.append((c[j, 0], c[j, 1], z))
            T.append((c[j, 0], c[j, 1]))
        for j in range(m):
            a, b = i0 + 1 + j, i0 + 1 + (j + 1) % m
            F.append((i0, a, b) if sinal > 0 else (i0, b, a))
    return np.array(V), np.array(F, dtype=np.int64), np.array(T)


def _caixa(x0, x1, y0, y1, z0, z1, r=0.0, bisel=0.0, n=3):
    """Caixa pelos limites (arestas verticais arredondadas de raio r, bisel em cima/baixo)."""
    v, f, t = _prisma(round(0.5 * (x1 - x0), 6), round(0.5 * (y1 - y0), 6), round(r, 6), n, round(z0, 6), round(z1, 6),
                      round(bisel, 6))
    return v + np.array([0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.0]), f, t


@functools.cache
def _elipsoide(rx, ry, rz, n=10, meia=False):
    """Elipsoide (malha UV); `meia` = só a metade de baixo com tampa (pés de borracha)."""
    V, F = [], []
    ni = n if not meia else n // 2
    for i in range(ni + 1):
        ph = math.pi * i / n - math.pi / 2
        for j in range(2 * n):
            th = math.pi * j / n
            V.append((rx * math.cos(ph) * math.cos(th), ry * math.cos(ph) * math.sin(th), rz * math.sin(ph)))
    for i in range(ni):
        for j in range(2 * n):
            a, b = i * 2 * n + j, i * 2 * n + (j + 1) % (2 * n)
            F += [(a, b, b + 2 * n), (a, b + 2 * n, a + 2 * n)]
    if meia:
        c = len(V)
        V.append((0.0, 0.0, 0.0))
        top = ni * 2 * n
        for j in range(2 * n):
            F.append((c, top + (j + 1) % (2 * n), top + j)[::-1])
    return np.array(V), np.array(F, dtype=np.int64), np.zeros((len(V), 2))


# ------------------------------------------------------------------------------- extrusão de contornos com furos
def _cruz(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def _triangular(exterior, furos=()):
    """Corte de orelhas com pontes de Eberly para os furos (puro Python): devolve (pontos, triângulos anti-horários)."""
    P = [tuple(map(float, p)) for p in exterior]
    if _area2(P) < 0:
        P.reverse()
    anel = list(range(len(P)))
    hs = []
    for h in furos:
        h = [tuple(map(float, p)) for p in h]
        if _area2(h) > 0:
            h.reverse()
        hs.append(h)
    hs.sort(key=lambda h: -max(p[0] for p in h))
    for h in hs:
        i0 = len(P)
        P.extend(h)
        idx_h = list(range(i0, i0 + len(h)))
        k = max(range(len(h)), key=lambda j: (h[j][0], -h[j][1]))
        M = h[k]
        melhor, bi, ix = math.inf, -1, None
        n = len(anel)
        for j in range(n):
            a, b = P[anel[j]], P[anel[(j + 1) % n]]
            if (a[1] - M[1]) * (b[1] - M[1]) > 0 or a[1] == b[1]:
                continue
            t = (M[1] - a[1]) / (b[1] - a[1])
            if t < 0 or t > 1:
                continue
            x = a[0] + t * (b[0] - a[0])
            if x >= M[0] - 1e-12 and x - M[0] < melhor:
                melhor, bi, ix = x - M[0], j, (x, M[1])
        pa, pb = bi, (bi + 1) % n
        cand_pos = pa if P[anel[pa]][0] > P[anel[pb]][0] else pb
        cand = anel[cand_pos]
        Pc = P[cand]
        tri = (M, ix, Pc) if _cruz(M, ix, Pc) > 0 else (M, Pc, ix)
        melhor_ang, escolhido, esc_pos = math.inf, cand, cand_pos
        for j in range(n):
            q = anel[j]
            if j == cand_pos or P[q] == Pc:
                continue
            pq = P[q]
            if _cruz(P[anel[j - 1]], pq, P[anel[(j + 1) % n]]) >= 0:
                continue
            if _cruz(tri[0], tri[1], pq) >= -1e-15 and _cruz(tri[1], tri[2], pq) >= -1e-15 and \
                    _cruz(tri[2], tri[0], pq) >= -1e-15:
                ang = abs(math.atan2(pq[1] - M[1], pq[0] - M[0]))
                if ang < melhor_ang - 1e-12 or (abs(ang - melhor_ang) < 1e-12 and pq[0] < P[escolhido][0]):
                    melhor_ang, escolhido, esc_pos = ang, q, j
        alvo = P[escolhido]
        pos = esc_pos
        for j in range(n):
            if P[anel[j]] != alvo:
                continue
            a, v, b = P[anel[j - 1]], alvo, P[anel[(j + 1) % n]]
            dentro = (_cruz(a, v, M) >= 0 and _cruz(v, b, M) >= 0) if _cruz(a, v, b) >= 0 else \
                (_cruz(a, v, M) >= 0 or _cruz(v, b, M) >= 0)
            if dentro:
                pos = j
                break
        hk = idx_h[k:] + idx_h[:k]
        anel = anel[:pos + 1] + hk + [hk[0], escolhido] + anel[pos + 1:]
    return P, _cortar_orelhas(P, anel)


def _cortar_orelhas(P, anel):
    """Corte de orelhas do anel (com as pontes): corta SEMPRE a 1.ª orelha pela ordem do anel — o resultado é o do
    algoritmo ingénuo (verificado igual triângulo a triângulo nos 260 contornos dos 13 builds), mas incremental:
    convexidade só dos vizinhos do vértice cortado, reflexos numa grelha, cada vértice reavaliado só quando o seu
    triângulo muda ou quando sai o reflexo que o bloqueava, e um monte (heap) pela ordem do anel. A maior placa (anel de
    586 vértices, 29 furos) passa de 65 ms para 6 ms."""
    n = len(anel)
    if n < 3:
        return []
    idx = list(anel)
    nxt = list(range(1, n)) + [0]
    prv = [n - 1] + list(range(n - 1))
    vivo = [True] * n
    cr = [_cruz(P[idx[prv[s]]], P[idx[s]], P[idx[nxt[s]]]) for s in range(n)]
    reflexos = Counter(idx[s] for s in range(n) if cr[s] <= 0)
    x0, y0 = min(p[0] for p in P), min(p[1] for p in P)
    h = max(max(p[0] for p in P) - x0, max(p[1] for p in P) - y0, 1e-9) / max(4.0, math.sqrt(len(reflexos) or 1))
    grelha = {}

    def celula(q):
        return int((P[q][0] - x0) // h), int((P[q][1] - y0) // h)

    for q in reflexos:
        grelha.setdefault(celula(q), set()).add(q)
    estado = [None] * n                 # None = por avaliar · False = não é orelha (as orelhas cortam-se logo)
    bloq = [None] * n                   # o reflexo que a bloqueou
    bloqueados = {}                     # reflexo → vértices que bloqueou
    heap = list(range(n))               # ordem do anel = número do vértice (os cortes preservam a ordem)
    cabeca, vivos, tris = 0, n, []

    def bloqueador(s):
        ia, ib, ic = idx[prv[s]], idx[s], idx[nxt[s]]
        a, b, c = P[ia], P[ib], P[ic]
        lmax = max((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2, (b[0] - c[0]) ** 2 + (b[1] - c[1]) ** 2,
                   (c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2)
        if cr[s] < 1e-6 * lmax:         # lasca: a tolerância do teste alarga muito a região → testam-se todos
            candidatos = reflexos
        else:
            m = 1e-6 * (1.0 + math.sqrt(lmax))
            bx0, bx1 = min(a[0], b[0], c[0]) - m, max(a[0], b[0], c[0]) + m
            by0, by1 = min(a[1], b[1], c[1]) - m, max(a[1], b[1], c[1]) + m
            i0, i1, j0, j1 = int((bx0 - x0) // h), int((bx1 - x0) // h), int((by0 - y0) // h), int((by1 - y0) // h)
            if (i1 - i0 + 1) * (j1 - j0 + 1) > len(reflexos):
                candidatos = [q for q in reflexos if bx0 <= P[q][0] <= bx1 and by0 <= P[q][1] <= by1]
            else:
                candidatos = [q for i in range(i0, i1 + 1) for j in range(j0, j1 + 1) for q in grelha.get((i, j), ())]
        for q in candidatos:
            if q == ia or q == ib or q == ic:
                continue
            pq = P[q]
            if pq == a or pq == b or pq == c:
                continue
            if _cruz(a, b, pq) >= -1e-15 and _cruz(b, c, pq) >= -1e-15 and _cruz(c, a, pq) >= -1e-15:
                return q
        return None

    def reavaliar(t):
        estado[t] = None
        heapq.heappush(heap, t)

    def sai_reflexo(q):
        reflexos[q] -= 1
        if reflexos[q] <= 0:
            del reflexos[q]
            grelha[celula(q)].discard(q)
            for t in bloqueados.pop(q, ()):
                if vivo[t] and estado[t] is False and bloq[t] == q:
                    reavaliar(t)

    def tirar(s):
        nonlocal cabeca, vivos
        p, q = prv[s], nxt[s]
        nxt[p], prv[q] = q, p
        vivo[s] = False
        if s == cabeca:
            cabeca = q
        vivos -= 1
        if cr[s] <= 0:
            sai_reflexo(idx[s])
        for t in (p, q):
            antes, cr[t] = cr[t], _cruz(P[idx[prv[t]]], P[idx[t]], P[idx[nxt[t]]])
            if (antes <= 0) != (cr[t] <= 0):
                if cr[t] <= 0:
                    if idx[t] not in reflexos:
                        grelha.setdefault(celula(idx[t]), set()).add(idx[t])
                    reflexos[idx[t]] += 1
                else:
                    sai_reflexo(idx[t])
            reavaliar(t)

    while vivos > 3:
        achou = None
        while heap:
            s = heap[0]
            if not vivo[s] or estado[s] is False:
                heapq.heappop(heap)
                continue
            if estado[s] is None:
                q = None if cr[s] > 1e-18 else -1
                if q is None:
                    q = bloqueador(s)
                estado[s] = q is None
                if q is not None:
                    bloq[s] = q
                    if q >= 0:
                        bloqueados.setdefault(q, set()).add(s)
            if estado[s]:
                achou = s
                break
            heapq.heappop(heap)
        if achou is None:               # degenerado (como o ingénuo): larga o 1.º vértice
            tirar(cabeca)
            continue
        tris.append((idx[prv[achou]], idx[achou], idx[nxt[achou]]))
        tirar(achou)
    if vivos == 3:
        s = cabeca
        tris.append((idx[s], idx[nxt[s]], idx[nxt[nxt[s]]]))
    return tris


@functools.cache
def _extrusao(exterior: tuple, furos: tuple, z0: float, z1: float):
    """Contorno + furos (em xy) extrudido de z0 a z1, com as paredes de todos os contornos."""
    P, tris = _triangular(exterior, furos)
    V, F, T = [], [], []
    npt = len(P)
    for z in (z0, z1):
        for x, y in P:
            V.append((x, y, z))
            T.append((x, y))
    for a, b, c in tris:
        if abs(_cruz(P[a], P[b], P[c])) < 1e-12:
            continue
        F.append((a, c, b))
        F.append((npt + a, npt + b, npt + c))
    for cont, sentido in [(exterior, 1)] + [(h, -1) for h in furos]:
        c = [tuple(map(float, p)) for p in cont]
        if (_area2(c) > 0) != (sentido > 0):
            c.reverse()
        s = _comprimentos(np.array(c))
        base, m = len(V), len(c)
        for j, (x, y) in enumerate(c):
            V.append((x, y, z0))
            T.append((s[j], z0))
            V.append((x, y, z1))
            T.append((s[j], z1))
        for j in range(m):
            j1 = (j + 1) % m
            a0, a1, b0, b1 = base + 2 * j, base + 2 * j1, base + 2 * j + 1, base + 2 * j1 + 1
            F += [(a0, a1, b1), (a0, b1, b0)]
    return np.array(V), np.array(F, dtype=np.int64), np.array(T)


def _ext(contorno, furos, z0, z1):
    """`_extrusao` com arredondamento das cotas (chave de cache estável)."""
    c = tuple((round(float(x), 5), round(float(y), 5)) for x, y in contorno)
    h = tuple(tuple((round(float(x), 5), round(float(y), 5)) for x, y in f) for f in furos)
    return _extrusao(c, h, round(float(z0), 5), round(float(z1), 5))


def _circulo(cx, cy, r, n=20, fase=0.0):
    return tuple((round(cx + r * math.cos(fase + _TAU * i / n), 5), round(cy + r * math.sin(fase + _TAU * i / n), 5))
                 for i in range(n))


def _rasgo(cx, cy, meio, r, ang=0.0, n=6):
    """Rasgo oblongo centrado em (cx, cy): meio-comprimento `meio` entre centros, raio `r`, ângulo `ang`."""
    pts = []
    ca, sa = math.cos(ang), math.sin(ang)
    for sinal, a0 in ((1.0, -90.0), (-1.0, 90.0)):
        for i in range(n + 1):
            a = math.radians(a0 + 180.0 * i / n)
            x, y = sinal * meio + r * math.cos(a), r * math.sin(a)
            pts.append((round(cx + ca * x - sa * y, 5), round(cy + sa * x + ca * y, 5)))
    return tuple(pts)


def _poligono_arred(vertices, r, n=4):
    """Arredonda os cantos (côncavos e convexos) de um polígono anti-horário com raio r."""
    out = []
    m = len(vertices)
    for i in range(m):
        p0, p1, p2 = (np.array(vertices[j % m], float) for j in (i - 1, i, i + 1))
        d0, d1 = p0 - p1, p2 - p1
        l0, l1 = np.linalg.norm(d0), np.linalg.norm(d1)
        d0, d1 = d0 / l0, d1 / l1
        ang = math.acos(max(-1.0, min(1.0, float(d0 @ d1))))
        rr = min(r, 0.45 * min(l0, l1) * math.tan(0.5 * ang))
        if rr <= 1e-6 or abs(math.pi - ang) < 1e-6:
            out.append((round(float(p1[0]), 5), round(float(p1[1]), 5)))
            continue
        t = rr / math.tan(0.5 * ang)
        a, b = p1 + d0 * t, p1 + d1 * t
        bis = (d0 + d1) / np.linalg.norm(d0 + d1)
        c = p1 + bis * (rr / math.sin(0.5 * ang))
        a0 = math.atan2(a[1] - c[1], a[0] - c[0])
        da = (math.atan2(b[1] - c[1], b[0] - c[0]) - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(n + 1):
            aa = a0 + da * k / n
            out.append((round(float(c[0] + rr * math.cos(aa)), 5), round(float(c[1] + rr * math.sin(aa)), 5)))
    return tuple(out)


def _ret(x0, x1, y0, y1, r=0.0):
    v = ((x1, y0), (x1, y1), (x0, y1), (x0, y0))
    return _poligono_arred(v, r) if r > 0 else tuple((round(x, 5), round(y, 5)) for x, y in v)


def _anel_c(r_in, r_out, folga, n=32):
    """Perfil em C (anel com a FENDA de largura `folga` do lado +x), anti-horário."""
    a_o = math.asin(min(0.99, 0.5 * folga / r_out))
    a_i = math.asin(min(0.99, 0.5 * folga / r_in))
    pts = []
    for i in range(n + 1):
        a = a_o + (_TAU - 2 * a_o) * i / n
        pts.append((r_out * math.cos(a), r_out * math.sin(a)))
    for i in range(n + 1):
        a = (_TAU - a_i) - (_TAU - 2 * a_i) * i / n
        pts.append((r_in * math.cos(a), r_in * math.sin(a)))
    return tuple((round(x, 5), round(y, 5)) for x, y in pts)


def _no_poligono(x, y, poly) -> bool:
    dentro, n = False, len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x0 + (y - y0) * (x1 - x0) / (y1 - y0) > x:
            dentro = not dentro
    return dentro


def _dist_segmento(x, y, a, b) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0.0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - ax - t * dx, y - ay - t * dy)


def _furos_que_cabem(contorno: tuple, furos: tuple, margem: float = 2.0, fixos: tuple = ()) -> tuple:
    """Só os furos que cabem no contorno (com `margem` às bordas, aos furos já aceites e aos `fixos`)."""
    aceites, caixas = [], []
    n = len(contorno)
    for f in fixos:
        xs, ys = [p[0] for p in f], [p[1] for p in f]
        caixas.append((min(xs) - margem, max(xs) + margem, min(ys) - margem, max(ys) + margem))
    for f in furos:
        if not all(_no_poligono(x, y, contorno) for x, y in f):
            continue
        if min(_dist_segmento(x, y, contorno[i], contorno[(i + 1) % n]) for x, y in f for i in range(n)) < margem:
            continue
        xs, ys = [p[0] for p in f], [p[1] for p in f]
        cx = (min(xs) - margem, max(xs) + margem, min(ys) - margem, max(ys) + margem)
        if any(cx[0] < c[1] and c[0] < cx[1] and cx[2] < c[3] and c[2] < cx[3] for c in caixas):
            continue
        aceites.append(f)
        caixas.append(cx)
    return tuple(aceites)


# ------------------------------------------------------------------------------- engrenagens
@functools.cache
def _coroa(z: int, m: float, z0: float, z1: float, r_furo: float, torcao: float, fase: float, n_fatias: int = 3,
           s_p: float = 0.44):
    """Coroa (eixo local z de z0 a z1) com dentes de EVOLVENTE (ângulo de pressão 20°: conjugados da secção axial de
    flancos retos do sem-fim), adendo m, dedendo 1,25 m, espessura `s_p`·p na primitiva (a folga para o filete),
    TORCIDOS de `torcao` rad/mm (a hélice do avanço do sem-fim) — furo r_furo."""
    p = math.pi * m
    alfa = math.radians(20.0)
    rp, ra, rf = 0.5 * m * z, 0.5 * m * z + m, 0.5 * m * z - 1.25 * m
    rb = rp * math.cos(alfa)
    tau = _TAU / z

    def inv(a):
        return math.tan(a) - a
    psi_p = 0.5 * s_p * p / rp

    def psi(r):                                   # meia espessura angular do dente no raio r
        if r <= rb:
            return psi_p + inv(alfa)
        return psi_p + inv(alfa) - inv(math.acos(rb / r))
    raios = [rf, max(rf, min(rb, ra))] + [rb + (ra - rb) * k / 3 for k in range(1, 4)]
    pts = []
    for i in range(z):
        c = fase + i * tau
        pts.append((c - tau / 2, rf))
        pts += [(c - psi(r), r) for r in raios]
        pts += [(c + psi(r), r) for r in raios[::-1]]
    th = np.array([q[0] for q in pts])
    rr = np.array([q[1] for q in pts])
    n = len(th)
    zs = np.linspace(z0, z1, n_fatias + 1)
    zm = 0.5 * (z0 + z1)
    V, F, T = [], [], []
    aneis = []
    for zz in zs:
        rot = torcao * (zz - zm)
        b = len(V)
        for j in range(n):
            V.append((rr[j] * math.cos(th[j] + rot), rr[j] * math.sin(th[j] + rot), zz))
            T.append((0.0, 0.0))
        aneis.append(b)
    for i in range(len(zs) - 1):
        a0, b0 = aneis[i], aneis[i + 1]
        for j in range(n):
            j1 = (j + 1) % n
            F += [(a0 + j, a0 + j1, b0 + j1), (a0 + j, b0 + j1, b0 + j)]
    for zz, sinal in ((z0, -1), (z1, 1)):
        rot = torcao * (zz - zm)
        bo = len(V)                                       # tampas: coroa de dentes ↔ furo, por setores
        for j in range(n):
            V.append((rr[j] * math.cos(th[j] + rot), rr[j] * math.sin(th[j] + rot), zz))
            T.append((0.0, 0.0))
        bi = len(V)
        for j in range(n):
            V.append((r_furo * math.cos(th[j] + rot), r_furo * math.sin(th[j] + rot), zz))
            T.append((0.0, 0.0))
        for j in range(n):
            j1 = (j + 1) % n
            q = [(bi + j, bo + j, bo + j1), (bi + j, bo + j1, bi + j1)]
            F += q if sinal > 0 else [t[::-1] for t in q]
    bf = len(V)                                           # parede do furo
    for zz in (z0, z1):
        for j in range(n):
            V.append((r_furo * math.cos(th[j]), r_furo * math.sin(th[j]), zz))
            T.append((0.0, 0.0))
    for j in range(n):
        j1 = (j + 1) % n
        F += [(bf + j, bf + n + j1, bf + j1), (bf + j, bf + n + j, bf + n + j1)]
    return np.array(V), np.array(F, dtype=np.int64), np.array(T)


@functools.cache
def _rosca_semfim(r0: float, r1: float, passo: float, z_lo: float, z_hi: float, mao: int, z_ref: float,
                  n_volta: int = 24):
    """Filete do sem-fim (eixo z): o centro do filete no ângulo φ (a partir de +x) está em z = z_ref + mao·passo·φ/2π;
    secção axial de flancos RETOS a 20° (a cremalheira da evolvente da coroa), 0,44·p na primitiva, núcleo r0 → crista r1."""
    t20 = math.tan(math.radians(20.0))
    r_pw = 0.5 * D1                                           # primitiva do sem-fim
    wp = 0.5 * 0.44 * passo                                   # meia espessura na primitiva (folga 0,12·p com a coroa)
    wc = wp - (r1 - r_pw) * t20                               # meia espessura na crista
    wr = wp + (r_pw - r0) * t20                               # meia espessura no núcleo
    sec = [(r0 - 0.01, -wr), (r1, -wc), (r1, wc), (r0 - 0.01, wr)]
    zc0, zc1 = z_lo + wr, z_hi - wr
    voltas = (zc1 - zc0) / passo
    K = max(math.ceil(voltas * n_volta), 2)
    V, F = [], []
    for e in range(3):
        base = len(V)
        for k in range(K + 1):
            zc = zc0 + (zc1 - zc0) * k / K
            phi = mao * (zc - z_ref) * _TAU / passo
            for rr, dz in (sec[e], sec[e + 1]):
                V.append((rr * math.cos(phi), rr * math.sin(phi), zc + dz))
        for k in range(K):
            p0, p1 = base + 2 * k, base + 2 * (k + 1)
            F += [(p0, p1, p1 + 1), (p0, p1 + 1, p0 + 1)]
    for zc_, sinal in ((zc0, -1), (zc1, 1)):                  # topos do filete
        phi = mao * (zc_ - z_ref) * _TAU / passo
        b = len(V)
        for rr, dz in sec:
            V.append((rr * math.cos(phi), rr * math.sin(phi), zc_ + dz))
        F += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    V = np.array(V)
    F = np.array(F, dtype=np.int64)
    # orientação: normal para fora do eixo nas tiras, para fora ao longo da hélice nos topos
    tri = V[F]
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    cen = tri.mean(axis=1)
    radial = np.column_stack([cen[:, 0], cen[:, 1], np.zeros(len(cen))])
    n_tiras = 3 * 2 * K
    # o flanco de baixo tem normal para baixo/fora; usa-se o sinal médio por tira (cada tira é coerente)
    for e in range(3):
        sl = slice(e * 2 * K, (e + 1) * 2 * K)
        ref = np.einsum("ij,ij->i", nrm[sl], radial[sl] + np.array([0.0, 0.0, 1.0]) * (np.array([-1, 0, 1])[e]) *
                        np.linalg.norm(radial[sl], axis=1)[:, None]).mean()
        if ref < 0:
            F[sl] = F[sl][:, ::-1]
    for i, sinal in ((n_tiras, -1), (n_tiras + 2, 1)):
        t_ = V[F[i]]
        nn = np.cross(t_[1] - t_[0], t_[2] - t_[0])
        tang = np.array([-math.sin(math.atan2(t_[0, 1], t_[0, 0])), math.cos(math.atan2(t_[0, 1], t_[0, 0])),
                         passo / (_TAU * r1)]) * mao * sinal
        if float(nn @ tang) < 0:
            F[i:i + 2] = F[i:i + 2][:, ::-1]
    return V, F, np.zeros((len(V), 2))


# ------------------------------------------------------------------------------- rotações
def _rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


@functools.cache
def _r_eixo_t(u: tuple):
    u = np.asarray(u, float) / np.linalg.norm(u)
    v = np.array([-u[1], u[0], 0.0])
    s, c = float(np.linalg.norm(v)), float(u[2])
    if s < 1e-12:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * K + (1 - c) * (K @ K)


def _r_eixo(u):
    """Rotação que leva o z local à direção `u`."""
    return _r_eixo_t(tuple(round(float(x), 9) for x in u))


def _base(x, y, z):
    """Matriz cujas colunas são os eixos locais (x, y, z) no referencial do conjunto."""
    return np.column_stack([np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)])


def _unit(v):
    v = np.asarray(v, float)
    return v / max(float(np.linalg.norm(v)), 1e-12)


# referenciais de extrusão usados muito: perfil (u, v) → eixo de extrusão w
R_XZ_Y = _base((1, 0, 0), (0, 0, 1), (0, 1, 0))      # perfil no plano xz, extrusão ao longo de +y
R_YZ_X = _base((0, 1, 0), (0, 0, 1), (1, 0, 0))      # perfil no plano yz, extrusão ao longo de +x
R_Y = _base((1, 0, 0), (0, 0, -1), (0, 1, 0))        # rotação própria: z local → +y, ângulo local π → −x


# ===================================================================================================== materiais
def _obter_material(ctx, nome: str):
    obter = getattr(ctx, "obter_material", None)
    if obter is not None:
        return obter(nome)
    return next((m for m in ctx.spec.materials if m.name == nome), None)


def _textura_carbono(ctx) -> str:
    nome = "est_carbono_3k"
    if not any(t.name == nome for t in ctx.spec.textures):
        ctx.spec.add_texture(name=nome, type=mujoco.mjtTexture.mjTEXTURE_2D,
                             builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
                             width=64, height=64, rgb1=[0.095, 0.095, 0.105], rgb2=[0.15, 0.15, 0.162],
                             mark=mujoco.mjtMark.mjMARK_EDGE, markrgb=[0.065, 0.065, 0.07])
    return nome


_MATERIAIS = {
    "carbono": ([1.0, 1.0, 1.0, 1.0], {"specular": 0.55, "shininess": 0.75, "texrepeat": [1.0, 1.0]}, True),
    "carbono_liso": ([0.10, 0.10, 0.11, 1.0], {"specular": 0.6, "shininess": 0.8}, False),
    "alu_preto": ([0.10, 0.10, 0.11, 1.0], {"specular": 0.45, "shininess": 0.55}, False),
    "alu_natural": ([0.66, 0.68, 0.71, 1.0], {"specular": 0.75, "shininess": 0.7}, False),
    "alu_laranja": ([0.96, 0.42, 0.04, 1.0], {"specular": 0.6, "shininess": 0.6}, False),
    "alu_vermelho": ([0.78, 0.12, 0.13, 1.0], {"specular": 0.6, "shininess": 0.6}, False),
    "aco": ([0.62, 0.64, 0.67, 1.0], {"specular": 0.9, "shininess": 0.9}, False),
    "aco_preto": ([0.16, 0.16, 0.17, 1.0], {"specular": 0.7, "shininess": 0.8}, False),
    "sextavado": ([0.02, 0.02, 0.02, 1.0], {"specular": 0.1, "shininess": 0.1}, False),
    "bronze": ([0.74, 0.52, 0.24, 1.0], {"specular": 0.75, "shininess": 0.7}, False),
    "servo_metal": ([0.075, 0.075, 0.085, 1.0], {"specular": 0.35, "shininess": 0.45}, False),
    "servo_plastico": ([0.12, 0.12, 0.13, 1.0], {"specular": 0.12, "shininess": 0.2}, False),
    "branco": ([0.93, 0.93, 0.91, 1.0], {"specular": 0.2, "shininess": 0.3}, False),
    "etiqueta": ([0.52, 0.54, 0.57, 1.0], {"specular": 0.45, "shininess": 0.5}, False),
    "vermelho": ([0.92, 0.06, 0.05, 1.0], {"specular": 0.4, "shininess": 0.5, "emission": 0.25}, False),
    "borracha": ([0.05, 0.05, 0.055, 1.0], {"specular": 0.05, "shininess": 0.1}, False),
    "pcb": ([0.06, 0.36, 0.17, 1.0], {"specular": 0.35, "shininess": 0.5}, False),
    "iman": ([0.45, 0.46, 0.50, 1.0], {"specular": 0.8, "shininess": 0.8}, False),
    "acrilico": ([0.78, 0.88, 0.96, 0.22], {"specular": 0.9, "shininess": 0.95}, False),
    "conector": ([0.94, 0.91, 0.80, 1.0], {"specular": 0.2, "shininess": 0.3}, False),
    "chip": ([0.03, 0.03, 0.03, 1.0], {"specular": 0.3, "shininess": 0.4}, False),
    "ouro": ([0.86, 0.68, 0.26, 1.0], {"specular": 0.9, "shininess": 0.85}, False),
    # ABS impresso (o build acessível): cinzento-escuro/preto; laranja LEGO só nas peças que rodam
    "abs_cinza": ([0.21, 0.22, 0.23, 1.0], {"specular": 0.22, "shininess": 0.35}, False),
    "abs_preto": ([0.06, 0.06, 0.065, 1.0], {"specular": 0.2, "shininess": 0.3}, False),
    "abs_laranja": ([0.95, 0.47, 0.09, 1.0], {"specular": 0.3, "shininess": 0.45}, False),
    "pcb_azul": ([0.08, 0.22, 0.55, 1.0], {"specular": 0.35, "shininess": 0.5}, False),
}


def _materiais(ctx) -> dict:
    tex = _textura_carbono(ctx)
    nomes = {}
    for chave, (rgba, kw, com_textura) in _MATERIAIS.items():
        nome = f"est_{chave}"
        existia = _obter_material(ctx, nome) is not None
        ctx.material(nome, rgba, **kw)
        if com_textura and not existia:
            _obter_material(ctx, nome).textures[int(mujoco.mjtTextureRole.mjTEXROLE_RGB)] = tex
        nomes[chave] = nome
    nomes.update({nome: nome for nome in fer.MATERIAIS})        # ferragens que GIRAM (desenhadas por nós)
    return nomes


# ===================================================================================================== conjuntos
class _Conj:
    """Conjunto CANÓNICO em mm: malhas por (etiqueta, material) com a PEÇA de cada faixa de faces, ferragens, eixos e
    âncoras — congela-se em cache e coloca-se (rotação/espelho + origem por etiqueta) uma vez por braço/instância."""

    def __init__(self):
        self.lotes: dict = {}
        self.fer: list = []
        self.eixos: list = []
        self.ancoras: list = []
        self.impressas: list = []
        self.peca = "estrutura"

    def j(self, etq, mat, parte, R=None, p=None, peca=None):
        V, F, T = parte
        V = np.asarray(V, float)
        F = np.asarray(F, np.int64)
        T = np.asarray(T, float)
        if R is not None:
            R = np.asarray(R, float)
            V = V @ R.T
            if np.linalg.det(R) < 0:
                F = F[:, ::-1]
        if p is not None:
            V = V + np.asarray(p, float)
        L = self.lotes.setdefault((etq, mat), {"v": [], "f": [], "t": [], "nv": 0, "nf": 0, "faixas": []})
        L["v"].append(V)
        L["f"].append(F + L["nv"])
        L["t"].append(T)
        pc = peca or self.peca
        a, b = L["nf"], L["nf"] + len(F)
        if L["faixas"] and L["faixas"][-1][0] == pc and L["faixas"][-1][2] == a:
            L["faixas"][-1] = (pc, L["faixas"][-1][1], b)
        else:
            L["faixas"].append((pc, a, b))
        L["nv"] += len(V)
        L["nf"] += len(F)

    def ferragem(self, qual, etq, ponto, eixo, peca=None, **kw):
        self.fer.append({"tipo": qual, "etq": etq, "ponto": np.asarray(ponto, float), "eixo": _unit(eixo),
                         "peca": peca or self.peca, "kw": kw})

    def parafuso(self, etq, ponto, eixo, rosca, **kw):
        self.ferragem("parafuso", etq, ponto, eixo, rosca=rosca, **kw)

    def eixo(self, etq, nome, ponto, direcao, tipo, **kw):
        self.eixos.append({"etq": etq, "nome": nome, "ponto": np.asarray(ponto, float), "direcao": _unit(direcao),
                           "tipo": tipo, "kw": kw})

    def ancora(self, etq, nome, ponto, direcao, **extra):
        """Âncora para os fios; `extra` (ex.: nota, grupo) vai também para a nota (as cadeias com {k} formatam-se)."""
        a = {"etq": etq, "nome": nome, "ponto": np.asarray(ponto, float), "direcao": _unit(direcao)}
        if extra:
            a["extra"] = dict(extra)
        self.ancoras.append(a)

    def congelar(self) -> tuple:
        lotes = tuple((chave, np.concatenate(L["v"]), np.concatenate(L["f"]), np.concatenate(L["t"]),
                       tuple(L["faixas"])) for chave, L in self.lotes.items() if L["nf"])
        return lotes, tuple(self.fer), tuple(self.eixos), tuple(self.ancoras), tuple(self.impressas)


class _Montador:
    """Os lotes FINAIS (corpo × prefixo × material) + a colocação dos conjuntos e a criação das malhas e geoms."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.mat = _materiais(ctx)
        self.lotes: dict = {}
        self.off = {"drone": np.asarray(ctx.p(0.0, 0.0, 0.0), float)}
        self.ferragens: list = []           # (corpo, ponto mm nominal, eixo, registo) das nossas ferragens

    def origem_m(self, corpo: str) -> np.ndarray:
        return self.off.get(corpo, np.zeros(3))

    def _juntar(self, corpo, prefixo, mat, V, F, T, faixas):
        L = self.lotes.setdefault((corpo, prefixo, mat), {"v": [], "f": [], "t": [], "nv": 0, "nf": 0, "faixas": []})
        L["v"].append(np.asarray(V, float))
        L["f"].append(np.asarray(F, np.int64) + L["nv"])
        L["t"].append(np.asarray(T, float))
        for pc, inst, a, b in faixas:
            L["faixas"].append((pc, inst, L["nf"] + a, L["nf"] + b))
        L["nv"] += len(V)
        L["nf"] += len(F)

    def juntar(self, corpo, mat, parte, peca, inst=0, R=None, p=None, prefixo="est"):
        """Uma peça diretamente no referencial nominal do corpo (mm)."""
        V, F, T = parte
        V = np.asarray(V, float)
        F = np.asarray(F, np.int64)
        if R is not None:
            V = V @ np.asarray(R, float).T
            if np.linalg.det(R) < 0:
                F = F[:, ::-1]
        if p is not None:
            V = V + np.asarray(p, float)
        self._juntar(corpo, prefixo, mat, V, F, T, [(peca, inst, 0, len(F))])

    def ponto_m(self, corpo, p_mm) -> np.ndarray:
        return np.asarray(p_mm, float) * MM + self.origem_m(corpo)

    def colocar(self, conj, corpos: dict, R=None, origens: dict | None = None, inst: int = 0, nomes: dict | None = None):
        """Põe um conjunto congelado: etiqueta → corpo (ou (corpo, prefixo do geom)), com a rotação/espelho R e a
        origem (mm, no referencial nominal do corpo) de cada etiqueta; ferragens e eixos vão para o registo."""
        lotes, fers, eixos, ancoras = conj[:4]
        impressas = conj[4] if len(conj) > 4 else ()
        R = np.eye(3) if R is None else np.asarray(R, float)
        espelho = np.linalg.det(R) < 0
        origens = origens or {}
        nomes = nomes or {}

        def destino(etq):
            d = corpos[etq]
            return d if isinstance(d, tuple) else (d, "est")

        for (etq, mat), V, F, T, faixas in lotes:
            corpo, prefixo = destino(etq)
            o = np.asarray(origens.get(etq, (0.0, 0.0, 0.0)), float)
            self._juntar(corpo, prefixo, mat, V @ R.T + o, F[:, ::-1] if espelho else F, T,
                         [(pc, inst, a, b) for pc, a, b in faixas])
        col = self.ctx.ferragens
        for fz in fers:
            corpo, prefixo = destino(fz["etq"])
            o = np.asarray(origens.get(fz["etq"], (0.0, 0.0, 0.0)), float)
            p_mm = R @ fz["ponto"] + o
            eixo = R @ fz["eixo"]
            kw = dict(fz["kw"])
            if kw.get("ref") is not None:
                kw["ref"] = R @ np.asarray(kw["ref"], float)
            gira = prefixo != "est"
            if col is None:
                continue
            anim = None
            if gira:                              # para a página 3D: gira/move-se com os geoms `<prefixo>_*`
                anim = {"tipo": "semfim" if "semfim" in prefixo else prefixo.replace(f"ombro{inst}_", ""),
                        "k": int(inst), "geoms": f"{prefixo}_*"}
            if fz["tipo"] == "registar":          # só regista (a geometria já está no conjunto: insertos, pinos…)
                kw2 = dict(kw)
                tipo_r = kw2.pop("tipo_reg", "registo")
                reg = col.registar(corpo=corpo, ponto=self.ponto_m(corpo, p_mm), eixo=eixo, peca=fz["peca"],
                                   inst=inst, tipo=tipo_r, **kw2)
                if anim is not None:
                    reg["anim"] = anim
                continue
            # o que GIRA com o sem-fim e os pernos (só a face à vista) desenham-se aqui; o resto desenha o Coletor
            desenhar = not gira and fz["tipo"] != "perno"
            reg = getattr(col, fz["tipo"])(corpo, self.ponto_m(corpo, p_mm), eixo, peca=fz["peca"], inst=inst,
                                           desenhar=desenhar, **kw)
            if not desenhar:
                self._desenhar_visivel(corpo, prefixo, reg)
            if anim is not None:
                reg["anim"] = anim
            self.ferragens.append((corpo, p_mm, eixo, reg))
        for e in eixos:
            corpo, _ = destino(e["etq"])
            o = np.asarray(origens.get(e["etq"], (0.0, 0.0, 0.0)), float)
            nome = e["nome"].format(k=inst, **nomes)
            self.ctx.eixo(nome, corpo, list(self.ponto_m(corpo, R @ e["ponto"] + o)), list(_unit(R @ e["direcao"])),
                          e["tipo"], **{k: (v.format(k=inst) if isinstance(v, str) else v) for k, v in e["kw"].items()})
        if impressas and hasattr(self.ctx, "registo"):
            notas_i = self.ctx.registo.notas.setdefault("impressas", {})
            for imp in impressas:
                vol = 0.0
                for (etq, mat), V, F, T, faixas in lotes:
                    if "abs" not in mat:
                        continue
                    for pc, a, b in faixas:
                        if pc == imp["peca"]:
                            vol += _volume_malha(V, F[a:b])
                chave = f"{imp['peca']}#{inst}"
                ant = notas_i.get(chave)
                if ant is not None and ant.get("nome") != imp["nome"]:
                    vol += float(ant.get("volume_mm3", 0.0))
                corpo_i, _ = destino(imp["etq"])
                notas_i[chave] = {"nome": imp["nome"] if ant is None or ant.get("nome") == imp["nome"]
                                  else f"{ant['nome']} + {imp['nome']}", "corpo": corpo_i,
                                  "orientacao": _quat_mesa(R @ imp["normal"]), "nota": imp["nota"],
                                  "volume_mm3": round(vol, 1)}
        notas = self.ctx.registo.notas.setdefault("ancoras", {}) if hasattr(self.ctx, "registo") else {}
        for a in ancoras:
            corpo, _ = destino(a["etq"])
            o = np.asarray(origens.get(a["etq"], (0.0, 0.0, 0.0)), float)
            ent = {"corpo": corpo, "ponto": [float(x) for x in self.ponto_m(corpo, R @ a["ponto"] + o)],
                   "direcao": [float(x) for x in _unit(R @ a["direcao"])]}
            for kx, vx in (a.get("extra") or {}).items():
                ent[kx] = vx.format(k=inst) if isinstance(vx, str) else vx
            notas[a["nome"].format(k=inst)] = ent

    def _desenhar_visivel(self, corpo, prefixo, reg):
        """A parte À VISTA de uma ferragem desenhada por nós (registada com `desenhar=False`): a cabeça de um parafuso
        (a haste está dentro das peças), a face do sextavado de um perno DIN 916 (rente à face plana do cubo) ou o anel
        E inteiro — nos geoms do sem-fim (`semfim{k}_rotor_*`) quando giram com ele, nos nossos geoms quando não."""
        q = np.asarray(reg.get("quat", [1.0, 0.0, 0.0, 0.0]), float)
        Rq = np.zeros(9)
        mujoco.mju_quat2Mat(Rq, q)
        Rq = Rq.reshape(3, 3)
        p = (np.asarray(reg["ponto"], float) - self.origem_m(corpo)) / MM
        t = reg.get("tipo")
        mat = reg.get("material", "fer_aco_preto")
        partes = []
        if t == "parafuso":
            cab = fer._cabeca_4762(reg["rosca"]) if reg.get("norma") == "ISO 4762" else fer._cabeca_7380(reg["rosca"])
            partes.append((mat, cab[0], cab[1]))
        elif t == "perno":
            d = fer.DIAMETRO[reg["rosca"]]
            s_ = {"M2": 0.9, "M2.5": 1.3, "M3": 1.5, "M4": 2.0, "M5": 2.5, "M6": 3.0}[reg["rosca"]]
            v1, f1, _t1 = _cil(0.5 * d * 0.97, -0.03, 0.4, 14)
            v2, f2, _t2 = _sext(s_, -0.05, -0.02)
            partes += [(mat, v1, f1), ("fer_aco_preto" if mat != "fer_aco_preto" else "est_sextavado", v2, f2)]
        elif t == "anel_e":
            v, f = fer._anel_e(float(reg.get("d_veio_mm", 5.0)))
            partes.append(("fer_mola", v, f))
        for mat_, v, f in partes:
            chave = "sextavado" if mat_ == "est_sextavado" else mat_
            vb = np.asarray(v, float) @ Rq.T + p
            self._juntar(corpo, prefixo, chave, vb, np.asarray(f, np.int64), np.zeros((len(vb), 2)),
                         [(reg["peca"], reg["inst"], 0, len(f))])

    def criar(self):
        ctx = self.ctx
        for nome_m, (rgba, spec, brilho, refl) in fer.MATERIAIS.items():
            if any(k[2] == nome_m for k in self.lotes):
                ctx.material(nome_m, rgba, specular=spec, shininess=brilho, reflectance=refl)
        for (corpo, prefixo, mat), L in self.lotes.items():
            if not L["nf"]:
                continue
            V = np.concatenate(L["v"]) * MM
            F = np.concatenate(L["f"])
            T = np.concatenate(L["t"]) / LADRILHO_MM
            nome = f"est_{corpo}_{mat}" if prefixo == "est" else f"{prefixo}_{mat}"
            _malha_no_spec(ctx, f"m_{nome}", V, F, T)
            ctx.geom(corpo, nome, type=mujoco.mjtGeom.mjGEOM_MESH, meshname=f"m_{nome}",
                     material=self.mat.get(mat, mat), pos=list(self.origem_m(corpo)))
            ctx.registar_faixas(nome, L["faixas"])


def _malha_no_spec(ctx, nome: str, v, f, t):
    me = ctx.spec.add_mesh(name=nome)
    me.uservert = np.asarray(v, float).ravel().tolist()
    me.userface = np.asarray(f, np.int64).ravel().tolist()
    me.usertexcoord = np.asarray(t, float).ravel().tolist()
    me.inertia = mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL     # massa 0: a inércia nunca conta, assim não falha
    return me


def _reestilizar_malha(ctx, g, nome_malha: str, parte_m, material: str, peca: str, inst: int = 0):
    """Um geom VISUAL que já existia (o nome fica) passa a ser uma malha nossa (vértices em m, no referencial do geom)."""
    v, f, t = parte_m
    _malha_no_spec(ctx, nome_malha, v, f, np.asarray(t, float) / LADRILHO_MM * 1000.0 * MM)
    g.type = mujoco.mjtGeom.mjGEOM_MESH
    g.meshname = nome_malha
    g.material = material
    g.quat = [1.0, 0.0, 0.0, 0.0]
    ctx.registar_geom(g.name, peca, inst)


# ===================================================================================================== peças comuns
def _escala(cj, etq, R, p, angulos, r0, r_menor, r_maior, maiores, peca, largura=0.8, n_arco=10):
    """Escala de traços brancos no plano xz do referencial R (relevo de 0,15 mm para −y local); o ângulo mede-se a
    partir de −x, positivo para +z (o sentido em que a junta roda o ponteiro com q > 0)."""
    for ang in angulos:
        a = math.radians(ang)
        r1 = r_maior if ang in maiores else r_menor
        d = np.array([-math.cos(a), 0.0, math.sin(a)])
        Rt = R @ _base(d, (0.0, 1.0, 0.0), np.cross(d, (0.0, 1.0, 0.0)))
        cj.j(etq, "branco", _caixa(r0, r1, -0.15, 0.0, -0.5 * largura, 0.5 * largura), Rt, p, peca)
    a0, a1 = math.radians(min(angulos)), math.radians(max(angulos))
    for i in range(n_arco):
        aa, bb = a0 + (a1 - a0) * i / n_arco, a0 + (a1 - a0) * (i + 1) / n_arco
        pa = np.array([-math.cos(aa), 0.0, math.sin(aa)]) * r0
        pb = np.array([-math.cos(bb), 0.0, math.sin(bb)]) * r0
        d = pb - pa
        comp = float(np.linalg.norm(d))
        d /= comp
        Rt = R @ _base(d, (0.0, 1.0, 0.0), np.cross(d, (0.0, 1.0, 0.0)))
        cj.j(etq, "branco", _caixa(-0.5 * comp - 0.2, 0.5 * comp + 0.2, -0.15, 0.0, -0.35, 0.35), Rt,
             p + R @ (0.5 * (pa + pb)), peca)


def _ponteiro(cj, etq, R, p, r0, r1, espessura, peca):
    """Ponteiro vermelho em cunha a apontar para −x (no plano xz do referencial R), espessura para −y local."""
    pts = ((-r1, 0.0), (-r0, 1.6), (-r0 + 2.0, 1.1), (-r0 + 2.0, -1.1), (-r0, -1.6))
    perfil = _ext(pts, (), -espessura, 0.0)
    cj.j(etq, "vermelho", perfil, R @ R_XZ_Y, p, peca)


def _rolamento(cj, etq_fixo, etq_movel, R, p, dims, peca_fixo, peca_movel, n=28):
    """Rolamento rígido de esferas com blindagens ZZ (eixo z local, de z = 0 a z = largura): anel exterior + blindagens
    (fixos) e anel interior (gira com o veio) — folga de 0,2 mm entre a blindagem e o anel interior."""
    r_i, r_e, w = dims
    r_oi = r_e - 0.18 * (r_e - r_i)              # face de dentro do anel exterior
    r_ii = r_i + 0.26 * (r_e - r_i)              # face de fora do anel interior
    r_b = r_ii + 0.35                             # a blindagem não toca no anel interior (folga de 0,35)
    cj.j(etq_fixo, "aco", _anel(r_e, r_oi, 0.0, w, n), R, p, peca_fixo)
    for z0, z1 in ((0.25, 0.45), (w - 0.45, w - 0.25)):
        cj.j(etq_fixo, "aco_preto", _anel(r_oi, r_b, z0, z1, n), R, p, peca_fixo)
    cj.j(etq_movel, "aco", _anel(r_ii, r_i, 0.0, w, n), R, p, peca_movel)


def _servo_xh430(cj, etq, R, p, peca, horn=None, idler=None, furos_tapados=(), conectores=True, rotulo=+1,
                 nome_ancora=None, etq_ancora=None):
    """DYNAMIXEL XH430 no referencial do servo (ver as constantes): caixa de 3 partes (frente e meio metálicos, trás
    em plástico), os 4 parafusos da tampa da frente nos cantos, os furos M2,5 das faces (os que nada tapa), o rebaixo
    do horn/idler, os 2 conectores JST EH no fundo e o rótulo. `horn`/`idler` = (etiqueta, peça) onde vão (giram com
    a junta) ou None. `furos_tapados` = nomes «lado±i»/«topo±i» que outra peça cobre (não se desenha o furo)."""
    W, D = SERVO_W, SERVO_D
    x0, x1 = X0_SERVO, X1_SERVO
    xc = 0.5 * (x0 + x1)
    hx, hy = 0.5 * SERVO_H, 0.5 * W
    pc = p + R @ np.array([xc, 0.0, 0.0])
    # frente: rebaixo do horn em z ∈ [0, 1] (furo r 10,3 descentrado: o eixo do horn está a −xc do centro)
    contorno = tuple((round(x, 5), round(y, 5)) for x, y in _ret_arred(hx, hy, 2.2, 3)(0.0))
    reb = _circulo(-xc, 0.0, REBAIXO_R, n=40)
    cj.j(etq, "servo_metal", _ext(contorno, (reb,), 0.0, REBAIXO_P), R, pc, peca)
    cj.j(etq, "servo_metal", _prisma(round(hx, 5), round(hy, 5), 2.2, 3, REBAIXO_P, DIV_FRENTE, 0.0), R, pc, peca)
    cj.j(etq, "servo_metal", _prisma(round(hx, 5), round(hy, 5), 2.2, 3, DIV_FRENTE + 0.4, DIV_TRAS, 0.0), R, pc, peca)
    cj.j(etq, "servo_metal", _prisma(round(hx - 0.5, 5), round(hy - 0.5, 5), 1.7, 3, DIV_FRENTE - 0.05, DIV_FRENTE + 0.45,
                                     0.0), R, pc, peca)                        # fundo do sulco frente/meio
    cj.j(etq, "servo_plastico", _prisma(round(hx - 0.5, 5), round(hy - 0.5, 5), 1.7, 3, DIV_TRAS - 0.05, DIV_TRAS + 0.45,
                                        0.0), R, pc, peca)
    tras = (_ext(contorno, (_circulo(-xc, 0.0, REBAIXO_R, n=40),), D - REBAIXO_P, D) if idler is not None else
            _prisma(round(hx, 5), round(hy, 5), 2.2, 3, D - REBAIXO_P, D, 0.25))
    cj.j(etq, "servo_plastico", _prisma(round(hx, 5), round(hy, 5), 2.2, 3, DIV_TRAS + 0.4, D - REBAIXO_P, 0.0), R, pc,
         peca)
    cj.j(etq, "servo_plastico", tras, R, pc, peca)
    if idler is None:                       # trás oca: o cubo do idler com o furo de passagem dos cabos
        cj.j(etq, "servo_plastico", _anel(8.6, 4.2, D, D + 0.5, 32), R, p, peca)
        cj.j(etq, "sextavado", _cil(4.2, D - 0.4, D + 0.3, 20), R, p, peca)
    # 4 parafusos M2,5 da tampa da frente (cabeça cilíndrica embutida nos cantos: só se vê o topo e o sextavado)
    for sx in (-1, 1):
        for sy in (-1, 1):
            q = np.array([xc + sx * (hx - 2.6), sy * (hy - 2.6), 0.0])
            cj.j(etq, "aco_preto", _cil(2.1, -0.06, 0.02, 14), R, p + R @ q, peca)
            cj.j(etq, "sextavado", _sext(2.0, -0.08, -0.04), R, p + R @ q, peca)
    # furos M2,5 DP3.0 das faces laterais (±y) e dos topos (±x): disco escuro (0,05 mm à frente da face)
    for lado in (-1, 1):
        for i, (xf, zf) in enumerate(FUROS_LADO):
            if f"lado{lado:+d}{i}" in furos_tapados:
                continue
            Rf = R @ _base((1, 0, 0), (0, 0, 1), (0, lado, 0)) if lado > 0 else R @ _base((1, 0, 0), (0, 0, -1),
                                                                                          (0, -1, 0))
            cj.j(etq, "sextavado", _cil(1.05, 0.0, 0.05, 12), Rf, p + R @ np.array([xf, lado * hy, zf]), peca)
    for topo, xt in ((-1, x0), (1, x1)):
        for i, (yf, zf) in enumerate(FUROS_TOPO):
            if f"topo{topo:+d}{i}" in furos_tapados:
                continue
            Rf = R @ _r_eixo((topo, 0, 0))
            cj.j(etq, "sextavado", _cil(1.05, 0.0, 0.05, 12), Rf, p + R @ np.array([xt, yf, zf]), peca)
    # rótulo lateral
    if rotulo:
        q = np.array([xc - 3.0, rotulo * (hy + 0.0), 0.5 * (DIV_FRENTE + DIV_TRAS) + 1.0])
        Rl = R @ _base((1, 0, 0), (0, 0, 1), (0, rotulo, 0)) if rotulo > 0 else R @ _base((1, 0, 0), (0, 0, -1),
                                                                                          (0, -1, 0))
        cj.j(etq, "etiqueta", _caixa(-9.5, 9.5, -6.5, 6.5, 0.0, 0.12, r=0.8), Rl, p + R @ q, peca)
    # conectores JST EH de 4 vias (RS-485) no FUNDO (x0), do lado de trás: recetáculo claro com a boca escura
    if conectores:
        for k_, (yc, zc) in enumerate(CONECTORES):
            Rc = R @ _base((0, 1, 0), (0, 0, 1), (-1, 0, 0))
            cj.j(etq, "conector", _caixa(-5.0, 5.0, -2.6, 2.6, 0.0, 0.35, r=0.3), Rc, p + R @ np.array([x0, yc, zc]),
                 peca)
            cj.j(etq, "sextavado", _caixa(-4.4, 4.4, -1.7, 1.7, 0.30, 0.40), Rc, p + R @ np.array([x0, yc, zc]), peca)
            if nome_ancora is not None:
                cj.ancora(etq_ancora or etq, nome_ancora + ("_a" if k_ == 0 else "_b"),
                          p + R @ np.array([x0 - 0.40, yc, zc]), R @ np.array([-1.0, 0.0, 0.0]))
    # horn HN12-N101 (gira): Ø20, 8 furos M2 em P.C.D 16, rebaixo do parafuso central (WB M2,5 × 6)
    if horn is not None:
        etq_h, peca_h = horn
        furos = tuple(_circulo(PCD_HORN / 2 * math.cos(_TAU * i / 8), PCD_HORN / 2 * math.sin(_TAU * i / 8), 0.8, n=10)
                      for i in range(8)) + (_circulo(0.0, 0.0, 2.45, n=16),)
        cj.j(etq_h, "alu_natural", _ext(_circulo(0.0, 0.0, HORN_R, n=48), furos, -HORN_E, -HORN_E + 2.5), R, p, peca_h)
        cj.j(etq_h, "alu_natural", _cil(HORN_R, -HORN_E + 2.5, HORN_DENTRO, 48), R, p, peca_h)
        cj.j(etq_h, "sextavado", _caixa(HORN_R - 1.6, HORN_R - 0.4, -0.25, 0.25, -HORN_E - 0.05, -HORN_E + 0.4), R, p,
             peca_h)                                                          # marca de indexação
    if idler is not None:
        etq_i, peca_i = idler
        furos = tuple(_circulo(PCD_HORN / 2 * math.cos(_TAU * i / 8), PCD_HORN / 2 * math.sin(_TAU * i / 8), 0.8, n=10)
                      for i in range(8)) + (_circulo(0.0, 0.0, 3.0, n=16),)
        cj.j(etq_i, "alu_natural", _ext(_circulo(0.0, 0.0, HORN_R, n=48), furos, D - HORN_DENTRO, D + HORN_E), R, p,
             peca_i)
        # rolamento de plástico do HN12-I101: casquilho fixo no cubo oco da tampa de trás (vê-se pelo furo do idler)
        cj.j(etq, "conector", _anel(2.7, 2.0, D - REBAIXO_P, D + HORN_E - 0.4, 20), R, p, peca_i)


# ------------------------------------------------------------------------------- abraçadeiras
def _abracadeira_fenda(cj, etq, mat, peca, C, U, W, r_in, r_out, u0, u1, us, folga=1.0, meio=6.75, rosca="M3",
                       porca="ISO 10511", topo=None):
    """Abraçadeira de FENDA numa só peça: anel r_in..r_out à volta do eixo C + U·u (u ∈ [u0, u1]) com a fenda do lado
    W e as 2 orelhas (furadas) de cada lado da fenda; os parafusos (perpendiculares ao plano da fenda) com a porca
    autoblocante do outro lado. `topo` (distância ao eixo do lado oposto à fenda) rebaixa o anel com uma face plana.
    Devolve (w_parafuso, meio)."""
    U, W = _unit(U), _unit(W)
    W = _unit(W - (W @ U) * U)
    N = np.cross(U, W)
    C = np.asarray(C, float)
    R_anel = _base(W, N, U)
    perfil_anel = _anel_c(r_in, r_out, folga)
    if topo is not None:
        perfil_anel = _poli([(max(x, -float(topo)), y) for x, y in perfil_anel])
    cj.j(etq, mat, _ext(perfil_anel, (), u0, u1), R_anel, C, peca)
    d_f = FURO_PASSANTE[rosca]
    w_e0 = math.sqrt(max(r_out ** 2 - meio ** 2, (r_in + 0.6) ** 2)) - 0.3
    w_s = r_out + 0.5 * d_f + 0.9
    w_e1 = w_s + 0.5 * fer.ISO4762[rosca][0] + 0.6
    R_or = _base(W, U, N)
    furos = tuple(_circulo(w_s, u, 0.5 * d_f, n=14) for u in us)
    perfil = _ret(w_e0, w_e1, u0, u1, r=0.8)
    for n0, n1 in ((0.5 * folga, meio), (-meio, -0.5 * folga)):
        cj.j(etq, mat, _ext(perfil, furos, n0, n1), R_or, C, peca)
    for u in us:
        cj.parafuso(etq, C + U * u + W * w_s + N * meio, -N, rosca, aperto=2.0 * meio, porca=porca,
                    anilha_porca=False, peca=peca, ref=U)
    return w_s, meio


def _abracadeira_dupla(cj, etq, mat, peca, C, U, V, r_t, u0, u1, us, parede=3.0, folga=0.5, h_orelha=7.5,
                       topo=None, fundo=None, rosca="M3", porca="ISO 10511"):
    """Abraçadeira de DUAS METADES (a de cima e a de baixo, separadas pela folga no plano do eixo) à volta de um tubo
    de raio r_t ao longo de U (eixo por C), com as orelhas dos parafusos para os lados ±V e os parafusos ao longo de
    N = U × V (cabeça em cima, porca em baixo). `topo`/`fundo` = cota (ao longo de N) da face de cima / de baixo
    (omissão: r_t + parede). Devolve {w_m, w_s, w_e, n_topo, n_fundo, h_orelha}."""
    U, V = _unit(U), _unit(V)
    V = _unit(V - (V @ U) * U)
    N = np.cross(U, V)
    C = np.asarray(C, float)
    n_topo = r_t + parede if topo is None else topo
    n_fundo = -(r_t + parede) if fundo is None else fundo
    g = 0.5 * folga
    w_m = r_t + 2.0
    d_f = FURO_PASSANTE[rosca]
    w_s = w_m + 0.5 * fer.ISO4762[rosca][0] + 0.4
    w_e = w_s + 0.5 * fer.ISO4762[rosca][0] + 0.7
    xg = math.sqrt(max(r_t ** 2 - g ** 2, 0.0))
    a0 = math.asin(g / r_t)
    arco = [(r_t * math.cos(a), r_t * math.sin(a)) for a in np.linspace(math.pi - a0, a0, 25)]
    R_c = _base(V, N, U)
    cima = [(w_m, g), (w_m, n_topo), (-w_m, n_topo), (-w_m, g), (-xg, g)] + arco[1:-1] + [(xg, g)]
    cj.j(etq, mat, _ext(_poligono_arred(tuple(cima), 0.6, 2), (), u0, u1), R_c, C, peca)
    arco_b = [(r_t * math.cos(a), -r_t * math.sin(a)) for a in np.linspace(a0, math.pi - a0, 25)]
    baixo = [(w_m, -g), (xg, -g)] + arco_b[1:-1] + [(-xg, -g), (-w_m, -g), (-w_m, n_fundo), (w_m, n_fundo)]
    cj.j(etq, mat, _ext(_poligono_arred(tuple(baixo), 0.6, 2), (), u0, u1), R_c, C, peca)
    R_o = _base(U, V, N)
    for lado in (-1, 1):
        furos = tuple(_circulo(u, lado * w_s, 0.5 * d_f, n=14) for u in us)
        perfil = _ret(u0, u1, w_m, w_e, r=0.8) if lado > 0 else _ret(u0, u1, -w_e, -w_m, r=0.8)
        cj.j(etq, mat, _ext(perfil, furos, g, min(h_orelha, n_topo)), R_o, C, peca)
        cj.j(etq, mat, _ext(perfil, furos, max(-h_orelha, n_fundo), -g), R_o, C, peca)
        for u in us:
            cj.parafuso(etq, C + U * u + V * (lado * w_s) + N * min(h_orelha, n_topo), -N, rosca,
                        aperto=min(h_orelha, n_topo) - max(-h_orelha, n_fundo), porca=porca, anilha_porca=False,
                        peca=peca, ref=U)
    return {"w_m": w_m, "w_s": w_s, "w_e": w_e, "n_topo": n_topo, "n_fundo": n_fundo, "h_orelha": h_orelha}


def _tubo(cj, etq, U, s0, s1, r, peca, C=(0.0, 0.0, 0.0), n=28, mat="carbono", parede=1.0):
    """Tubo de carbono ao longo de U de s0 a s1 (eixo por C), oco (parede 1 mm: vê-se nas pontas)."""
    cj.j(etq, mat, _anel(r, r - parede, s0, s1, n), _r_eixo(U), np.asarray(C, float), peca)


# ===================================================================================================== OMBRO
@functools.cache
def _ombro_canonico(zs0: float, zs1: float, esp: float, mao: int, r_t: float) -> tuple:
    """OMBRO do braço 1 no referencial canónico (mm, origem no eixo da dobradiça; a = x, b = y, z): etiquetas «fixo»
    (corpo `drone`), «rotor» (corpo `drone`, geoms `semfim{k}_rotor_*`: gira 20× o ombro) e «movel» (`braco{k}`).
    `zs0`/`zs1` = faces de baixo/cima da placa de cima, `esp` = meia espessura da placa de baixo, `mao` = mão do filete
    no canónico (+1 direita; o espelho dos braços 3 e 4 troca-a e o sem-fim fica sempre de rosca direita)."""
    cj = _Conj()
    F_, G_, M_ = "fixo", "rotor", "movel"
    XA0, XA1 = -26.0, 11.0                 # caixa do redutor: trás / frente (a janela)
    ZB0, ZB1 = -16.0, zs0                  # fundo / topo (a tampa encosta à placa de cima)
    YI0, YI1 = -42.0, -36.0                # parede de dentro (rolamento 6800 na face de fora, rebordo de 1 mm)
    YO0, YO1 = -20.0, -14.0                # parede de fora
    w6800 = R6800[2]
    # ------------------------------------------------------------------------------------------- caixa (fixa)
    cj.peca = "ombro_caixa"
    parede = _ret(XA0, XA1, ZB0, ZB1, r=1.5)
    # janela de inspeção na parede de DENTRO, por cima do sem-fim (a da frente mostra a coroa, esta o sem-fim)
    abertura = _poligono_arred(((-12.5, -8.0), (-12.5, 8.0), (-21.0, 8.0), (-21.0, -8.0)), 1.5)
    for y0, y1, r_f in ((YI0, YI0 + w6800, R6800[1]), (YI0 + w6800, YI1, 6.5), (YO0, YO0 + 1.0, 6.5),
                        (YO0 + 1.0, YO1, R6800[1])):
        extra = (abertura,) if y1 <= YI1 + 1e-9 else ()
        cj.j(F_, "alu_natural", _ext(parede, (_circulo(0.0, 0.0, r_f, 40),) + extra, y0, y1), R_XZ_Y)
    furos_ji = ((-16.75, -12.5), (-16.75, 12.0))
    cj.j(F_, "acrilico", _ext(_ret(-24.0, -12.0, -14.5, ZB1, r=1.5),
                              tuple(_circulo(x, z, 0.5 * FURO_PASSANTE["M2.5"], 12) for x, z in furos_ji),
                              YI0 - 1.5, YI0), R_XZ_Y)
    for x, z in furos_ji:
        cj.parafuso(F_, (x, YI0 - 1.5, z), (0, 1, 0), "M2.5", aperto=1.5, rosca_metida=3.75, material_="aco_inox",
                    peca="ombro_caixa")
    cj.j(F_, "alu_natural", _caixa(XA0, -22.0, YI1, YO0, ZB0, ZB1))                          # costas
    interior = _ret(-22.0, XA1, YI1, YO0)
    for z0, z1, r_f in ((ZB0, -12.0, 4.9), (-12.0, -9.5, R685[1]), (9.5, 12.0, R685[1]), (12.0, ZB1, 4.9)):
        cj.j(F_, "alu_natural", _ext(interior, (_circulo(A_W, B_C, r_f, 28),), z0, z1))    # fundo e tampa
    for z0, z1 in ((-9.5, -7.0), (7.0, 9.5)):                                                # ressaltos dos 685
        cj.j(F_, "alu_natural", _anel(7.5, R685[1], z0, z1, 28), None, (A_W, B_C, 0.0))
    # aba de fixação na placa de baixo (2 × M3 + porca autoblocante por baixo da placa)
    furos_aba = ((-32.0, -35.0), (-32.0, -21.0))
    cj.j(F_, "alu_natural", _ext(_poligono_arred(((XA0 + 1.0, -40.0), (XA0 + 1.0, -16.0), (-38.0, -16.0),
                                                   (-38.0, -40.0)), 2.0, 3),
                                 tuple(_circulo(x, y, 0.5 * FURO_PASSANTE["M3"], 14) for x, y in furos_aba),
                                 esp, esp + 4.0))
    for x, y in furos_aba:
        cj.parafuso(F_, (x, y, esp + 4.0), (0, 0, -1), "M3", aperto=4.0 + 2.0 * esp, porca="ISO 10511",
                    peca="ombro_caixa")
    # janela de policarbonato na frente (+a): mostra a coroa e o sem-fim a engrenar; 4 × M2,5 ISO 4762 inox nas paredes
    furos_jan = ((-39.0, -11.5), (-39.0, 9.5), (-17.0, -11.5), (-17.0, 9.5))
    cj.j(F_, "acrilico", _ext(_ret(YI0, YO1, -14.5, 12.5, r=1.5),
                              tuple(_circulo(y, z, 0.5 * FURO_PASSANTE["M2.5"], 12) for y, z in furos_jan),
                              XA1, XA1 + 2.0), R_YZ_X)
    for y, z in furos_jan:
        cj.parafuso(F_, (XA1 + 2.0, y, z), (-1, 0, 0), "M2.5", aperto=2.0, rosca_metida=3.75, material_="aco_inox",
                    peca="ombro_caixa")
    # escala −40…+40° na face de fora da parede de fora (do lado do cubo)
    _escala(cj, F_, np.diag([1.0, -1.0, 1.0]), np.array([0.0, YO1, 0.0]), (-40, -30, -20, -10, 0, 10, 20, 30, 40),
            16.5, 19.0, 20.0, (-40, -20, 0, 20, 40), "ombro_caixa")
    # rolamentos: 2 × 6800ZZ no veio de saída (anel interior gira com o braço), 2 × 685ZZ no sem-fim (gira com ele)
    for y0 in (YI0, YO1 - w6800):
        _rolamento(cj, F_, M_, R_Y, np.array([0.0, y0, 0.0]), R6800, "ombro_caixa", "ombro_veio")
    for z0 in (-12.0, 7.0):
        _rolamento(cj, F_, G_, None, np.array([A_W, B_C, z0]), R685, "ombro_caixa", "ombro_semfim", n=20)
    cj.eixo(F_, "ombro{k}_rolamento_dentro", (0.0, YI0 + 0.5 * w6800, 0.0), (0, 1, 0), "rolamento 6800ZZ",
            junta="ombro{k}")
    cj.eixo(F_, "ombro{k}_rolamento_fora", (0.0, YO1 - 0.5 * w6800, 0.0), (0, 1, 0), "rolamento 6800ZZ",
            junta="ombro{k}")
    cj.eixo(F_, "semfim{k}_rolamento_baixo", (A_W, B_C, -9.5), (0, 0, 1), "rolamento 685ZZ")
    cj.eixo(F_, "semfim{k}_rolamento_cima", (A_W, B_C, 9.5), (0, 0, 1), "rolamento 685ZZ")

    # ------------------------------------------------------------------------------- veio de saída, coroa (móveis)
    cj.peca = "ombro_veio"
    cj.j(M_, "aco", _cil(5.0, -45.2, 6.0, 28), R_Y)                                         # veio Ø10
    cj.j(M_, "iman", _cil(3.0, -45.5, -43.0, 20), R_Y)                                      # íman diametral Ø6
    for y, s_ in ((YI0, -1), (YO1, 1)):                                                     # anéis E DIN 6799
        cj.ferragem("anel_e", M_, (0.0, y, 0.0), (0, s_, 0), d_veio=10.0, peca="ombro_veio")
    torcao = mao * math.tan(LAMBDA) / RP2
    fase = math.pi - math.pi / Z2                     # um VÃO de dente em −x (onde engrena o sem-fim) com q = 0
    cj.j(M_, "bronze", _coroa(Z2, MOD, 0.0, 6.0, 5.0, round(torcao, 9), round(fase, 9)), R_Y, (0.0, B_C - 3.0, 0.0))
    cubo_coroa = _poligono_arred(tuple((round(7.0 * math.cos(a), 5), round(7.0 * math.sin(a), 5))
                                       for a in np.linspace(0.0, _TAU, 33)[:-1]), 0.0)
    cubo_coroa = tuple((min(x, 6.8), max(y, -6.8)) for x, y in cubo_coroa)      # 2 faces planas para os pernos
    cj.j(M_, "bronze", _ext(cubo_coroa, (_circulo(0.0, 0.0, 5.0, 28),), B_C + 3.0, -20.5), R_Y)
    y_p = 0.5 * (B_C + 3.0 - 20.5)
    cj.ferragem("perno", M_, (6.8, y_p, 0.0), (-1, 0, 0), rosca="M2.5", comp=2.0, peca="ombro_veio")
    cj.ferragem("perno", M_, (0.0, y_p, -6.8), (0, 0, 1), rosca="M2.5", comp=2.0, peca="ombro_veio")
    cj.eixo(M_, "ombro{k}_veio", (0.0, B_C, 0.0), (0, 1, 0), "veio de saída Ø10 (coroa e cubo do braço)",
            junta="ombro{k}")

    # ------------------------------------------------------------------------------- sem-fim e acoplamento (rotor)
    cj.peca = "ombro_semfim"
    # veio do sem-fim: munhões Ø5 nos 685, ressaltos Ø6,2 que encostam SÓ ao anel interior (o exterior é fixo) e o
    # núcleo Ø10 (fundo do filete) com cones de saída
    perfil = (((0.0, -13.5), (2.2, -13.5)), ((2.2, -13.5), (2.5, -13.2)), ((2.5, -13.2), (2.5, -7.0)),
              ((2.5, -7.0), (3.1, -7.0)), ((3.1, -7.0), (3.1, -6.8)), ((3.1, -6.8), (5.0, -6.2)), ((5.0, -6.2), (5.0, 6.2)),
              ((5.0, 6.2), (3.1, 6.8)), ((3.1, 6.8), (3.1, 7.0)), ((3.1, 7.0), (2.5, 7.0)),
              ((2.5, 7.0), (2.5, 24.2)), ((2.5, 24.2), (2.2, 24.5)), ((2.2, 24.5), (0.0, 24.5)))
    cj.j(G_, "aco", _torno(perfil, 24), None, (A_W, B_C, 0.0))
    cj.j(G_, "aco", _rosca_semfim(5.0, 6.8, round(PASSO_AX, 7), -6.2, 6.2, mao, 0.0), None, (A_W, B_C, 0.0))
    for z, s_ in ((-12.0, -1), (12.0, 1)):
        cj.ferragem("anel_e", G_, (A_W, B_C, z), (0, 0, s_), d_veio=5.0, peca="ombro_semfim")
    z_ac0, z_ac1 = zs1 + 0.8, Z_FACE_SERVO_OMBRO - HORN_E - 2.0       # cubo do acoplamento / flange
    cubo = tuple((min(x, 5.5), y) for x, y in _circulo(0.0, 0.0, 5.75, 28))
    cj.j(G_, "alu_natural", _ext(cubo, (_circulo(0.0, 0.0, 2.5, 20),), z_ac0, z_ac1), None, (A_W, B_C, 0.0))
    furos_fl = tuple(_circulo(8.0 * math.cos(b), 8.0 * math.sin(b), 1.2, 12) for b in (0.0, 0.5 * math.pi, math.pi,
                                                                                       1.5 * math.pi))
    cj.j(G_, "alu_natural", _ext(_circulo(0.0, 0.0, HORN_R, 48), furos_fl, z_ac1, z_ac1 + 2.0), None, (A_W, B_C, 0.0))
    cj.ferragem("perno", G_, (A_W + 5.5, B_C, 0.5 * (z_ac0 + z_ac1)), (-1, 0, 0), rosca="M3", comp=3.0,
                peca="ombro_semfim")
    for b in (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi):
        cj.parafuso(G_, (A_W + 8.0 * math.cos(b), B_C + 8.0 * math.sin(b), z_ac1), (0, 0, 1), "M2", aperto=2.0,
                    rosca_metida=2.0, peca="ombro_semfim")

    # ------------------------------------------------------------------------------- servo do ombro + suportes
    cj.peca = "ombro_servo"
    tapados = {"topo+10", "topo+11", "topo-10", "topo-11"}
    _servo_xh430(cj, F_, np.eye(3), np.array([A_W, B_C, Z_FACE_SERVO_OMBRO]), "ombro_servo", horn=(G_, "ombro_servo"),
                 furos_tapados=tapados, rotulo=-1, nome_ancora="servo_ombro{k}_ficha", etq_ancora=F_)
    # parafuso central do horn (WB M2,5 × 6 do HN12-N101): cabeça no rebaixo do horn, gira com ele
    cj.parafuso(G_, (A_W, B_C, Z_FACE_SERVO_OMBRO - HORN_E + 2.5), (0, 0, 1), "M2.5", comp=6.0, aperto=0.2,
                peca="ombro_servo")
    xt, xf = A_W + X1_SERVO, A_W + X0_SERVO              # topo (do lado do horn) e fundo da caixa do servo
    y_s0, y_s1 = B_C - 13.0, B_C + 13.0
    z_s = Z_FACE_SERVO_OMBRO + 8.0
    furos_v = tuple(_circulo(B_C + yf, Z_FACE_SERVO_OMBRO + zf, 0.5 * FURO_PASSANTE["M2.5"], 12) for yf, zf in FUROS_TOPO)
    perfil_v = _ret(y_s0, y_s1, zs1, z_s + 5.0, r=1.0)
    for x0_, x1_, x_h0, x_h1, sinal, porca in ((xt, xt + 2.0, xt + 2.0, xt + 13.25, -1.0, None),
                                              (xf - 2.0, xf, xf - 12.75, xf - 2.0, 1.0, "ISO 10511")):
        cj.j(F_, "alu_preto", _ext(perfil_v, furos_v, x0_, x1_), R_YZ_X)
        x_par = 0.5 * (x_h0 + x_h1) + (1.0 if sinal < 0 else -0.5)
        furos_h = tuple(_circulo(x_par, y, 0.5 * FURO_PASSANTE["M3"], 14) for y in (B_C - 9.0, B_C + 9.0))
        cj.j(F_, "alu_preto", _ext(_ret(x_h0, x_h1, y_s0, y_s1, r=1.0), furos_h, zs1, zs1 + 2.0))
        x_face = x1_ if sinal < 0 else x0_
        for yf, zf in FUROS_TOPO:
            cj.parafuso(F_, (x_face, B_C + yf, Z_FACE_SERVO_OMBRO + zf), (sinal, 0, 0), "M2.5", aperto=2.0,
                        rosca_metida=2.5, peca="ombro_servo")
        for y in (B_C - 9.0, B_C + 9.0):
            if porca is None:      # rosca na tampa da caixa do redutor (aperta também a placa de cima)
                cj.parafuso(F_, (x_par, y, zs1 + 2.0), (0, 0, -1), "M3", aperto=2.0 + (zs1 - zs0), rosca_metida=4.5,
                            peca="ombro_servo")
            else:
                cj.parafuso(F_, (x_par, y, zs1 + 2.0), (0, 0, -1), "M3", aperto=2.0 + (zs1 - zs0), porca=porca,
                            peca="ombro_servo")
    cj.furos = [(F_, (A_W, B_C), 4.0, "sup")]          # passagem do veio do sem-fim na placa de cima

    # ------------------------------------------------------------------------------- encoder AS5048A (fixo)
    cj.peca = "ombro_encoder"
    y_pcb0, y_pcb1 = -49.6, -48.0
    furos_pcb = tuple((x, z) for x in (-8.5, 8.5) for z in (-11.5, 11.5))
    cj.j(F_, "pcb", _ext(_ret(-11.0, 11.0, -14.0, 14.0, r=1.2), tuple(_circulo(x, z, 1.3, 12) for x, z in furos_pcb),
                         y_pcb0, y_pcb1), R_XZ_Y)
    cj.j(F_, "chip", _caixa(-2.65, 2.65, -3.1, 3.1, 0.0, 1.75), R_XZ_Y, (0.0, y_pcb1, 0.0))
    for i in range(6):                                                    # barra de 6 pinos (SPI) atrás, em baixo
        x = -6.35 + 2.54 * i
        cj.j(F_, "ouro", _caixa(x - 0.32, x + 0.32, -12.32, -11.68, 0.0, 8.0), R_XZ_Y,
             (0.0, y_pcb0 - 8.0, 0.0))
    cj.j(F_, "chip", _caixa(-7.62, 7.62, -13.27, -10.73, 0.0, 2.5), R_XZ_Y, (0.0, y_pcb0 - 2.5, 0.0))
    for x, z in furos_pcb:
        cj.ferragem("pilar", F_, (x, y_pcb1, z), (0, 1, 0), rosca="M2.5", comp=6.0,
                    tipo="sextavado", af=5.0, macho=4.0, material_="latao", peca="ombro_encoder")
        cj.parafuso(F_, (x, y_pcb0, z), (0, 1, 0), "M2.5", aperto=y_pcb1 - y_pcb0, rosca_metida=3.75,
                    peca="ombro_encoder")

    # ------------------------------------------------------------------------------- cubo do braço (gira)
    cj.peca = "ombro_cubo"
    ws = _unit((-1.0, 0.0, -1.0))
    _abracadeira_fenda(cj, M_, "alu_laranja", "ombro_cubo", (0.0, -12.5, 0.0), (0, 1, 0), ws, 5.0, 13.0, 0.0, 20.5,
                       (10.25,), folga=1.0, meio=6.0)
    u45 = np.array([math.sqrt(0.5), math.sqrt(0.5), 0.0])
    cj.j(M_, "alu_laranja", _ext(_anel_c(3.0, r_t + 3.0, 1.0), (), 9.0, 11.0), _base((0, 0, -1), np.cross(u45, (0, 0, -1)),
                                                                                       u45))
    _abracadeira_fenda(cj, M_, "alu_laranja", "ombro_cubo", (0.0, 0.0, 0.0), u45, (0.0, 0.0, -1.0), r_t, r_t + 3.0,
                       11.0, 46.0, (22.0, 38.0), folga=1.0, meio=7.0)
    _ponteiro(cj, M_, np.eye(3), np.array([0.0, -12.5, 0.0]), 10.5, 19.5, 0.8, "ombro_cubo")
    # passagem dos cabos do braço: SOBRE o eixo da dobradiça (o único sítio que não se mexe com o ombro), 5 mm para lá
    # do cubo (o cubo e o casquilho do tubo acabam a 31,1 mm do plano do braço, medido): livre num raio de 12 mm
    cj.ancora("fixo", "ombro{k}_eixo_cabos", (0.0, 36.0, 0.0), (0.0, 1.0, 0.0))
    return cj.congelar(), tuple(cj.furos)


# ===================================================================================================== COTOVELO
def _face_garfo(r_olho, z_topo, rc=3.0, n_arco=16, n_canto=4):
    """Contorno da face do garfo no plano (c, z), anti-horário: meia-lua de raio `r_olho` à volta do eixo (por baixo)
    e os dois lados até ao topo, com os cantos de cima arredondados."""
    pts = [(r_olho, 0.0), (r_olho, z_topo - rc)]
    for i in range(1, n_canto + 1):
        a = 0.5 * math.pi * i / n_canto
        pts.append((r_olho - rc + rc * math.cos(a), z_topo - rc + rc * math.sin(a)))
    pts.append((-r_olho + rc, z_topo))
    for i in range(1, n_canto + 1):
        a = 0.5 * math.pi + 0.5 * math.pi * i / n_canto
        pts.append((-r_olho + rc + rc * math.cos(a), z_topo - rc + rc * math.sin(a)))
    pts.append((-r_olho, 0.0))
    for i in range(1, n_arco):
        a = math.pi + math.pi * i / n_arco
        pts.append((r_olho * math.cos(a), r_olho * math.sin(a)))
    return tuple((round(x, 5), round(y, 5)) for x, y in pts)


@functools.cache
def _cotovelo_canonico(z_p0: float, r_neck: float, r_t: float) -> tuple:
    """COTOVELO do braço 1, canónico (mm, c = x, d = y, z, origem no eixo): etiqueta «braco» (servo, berço/abraçadeira
    do tubo, escala — no corpo `braco{k}`, deslocados para a ponta) e «mastro» (horn, idler, garfo, abraçadeiras e
    tubo do mastro — no `mastro{k}`: rodam com o cotovelo). `z_p0` = face de baixo da placa do motor."""
    cj = _Conj()
    B, Ms = "braco", "mastro"
    hd = 0.5 * SERVO_D
    u45 = np.array([math.sqrt(0.5), math.sqrt(0.5), 0.0])
    # servo: x do servo = +c (horn perto do topo +c), y = −z, z = +d (horn na face −d, idler na +d)
    R_s = _base((1, 0, 0), (0, 0, -1), (0, 1, 0))
    p_s = np.array([0.0, -hd, 0.0])
    tapados = {f"lado+1{i}" for i in range(4)}
    _servo_xh430(cj, B, R_s, p_s, "cotovelo_servo", horn=(Ms, "cotovelo_servo"), idler=(Ms, "cotovelo_garfo"),
                 furos_tapados=tapados, rotulo=-1, nome_ancora="servo_cotovelo{k}_ficha", etq_ancora=B)
    cj.eixo(B, "cotovelo{k}_servo", (0.0, 0.0, 0.0), (0, 1, 0), "veio de saída do XH430", junta="cotovelo{k}")
    cj.eixo(Ms, "cotovelo{k}_horn", (0.0, -hd - 1.0, 0.0), (0, 1, 0), "horn HN12-N101", junta="cotovelo{k}")
    cj.eixo(Ms, "cotovelo{k}_idler", (0.0, hd + 1.0, 0.0), (0, 1, 0), "idler HN12-I101 (rolamento de plástico)",
            junta="cotovelo{k}")
    # escala −60…+60° na face do horn (no braço) e o ponteiro no braço de dentro do garfo (no mastro)
    cj.peca = "cotovelo_servo"
    _escala(cj, B, np.eye(3), np.array([0.0, -hd, 0.0]), (-60, -45, -30, -15, 0, 15, 30, 45, 60), 12.6, 14.6, 15.8,
            (-60, -30, 0, 30, 60), "cotovelo_servo", largura=0.7)
    # ---------------------------------------------------------------- berço do servo + abraçadeira do tubo (braço)
    cj.peca = "abracadeira_tubo"
    zb1 = -0.5 * SERVO_W
    berco = ((9.0, -15.0), (9.0, 15.0), (-34.0, 15.0), (-34.0, -15.0), (-30.6, -15.0), (-60.8, -45.2), (-45.2, -60.8),
             (0.6, -15.0))
    furos_b = tuple((xf, zf - hd) for xf, zf in FUROS_LADO)
    cj.j(B, "alu_preto", _ext(_poligono_arred(berco, 2.0), tuple(_circulo(x, y, 0.5 * FURO_PASSANTE["M2.5"], 12)
                                                                  for x, y in furos_b), zb1 - 3.0, zb1))
    for x, y in furos_b:
        cj.parafuso(B, (x, y, zb1 - 3.0), (0, 0, 1), "M2.5", aperto=3.0, rosca_metida=2.5, peca="cotovelo_servo")
    w_lado = np.cross(u45, (0.0, 0.0, 1.0))
    cj.j(B, "alu_preto", _ext(_anel_c(3.0, r_t + 3.0, 1.0), (), 56.0, 60.0), _base(w_lado, np.cross(-u45, w_lado), -u45))
    _abracadeira_fenda(cj, B, "alu_preto", "abracadeira_tubo", (0.0, 0.0, 0.0), -u45, w_lado, r_t, r_t + 3.0, 60.0, 92.0,
                       (68.0, 84.0), folga=1.0, meio=7.0)
    # ---------------------------------------------------------------- garfo (padrão FR12-H101K) — roda com o cotovelo
    cj.peca = "cotovelo_garfo"
    z_ponte = 39.0
    face = _face_garfo(12.0, z_ponte + 6.0)
    furos_g = tuple(_circulo(0.5 * PCD_HORN * math.cos(_TAU * i / 8), 0.5 * PCD_HORN * math.sin(_TAU * i / 8),
                             0.5 * FURO_PASSANTE["M2"], 10) for i in range(0, 8, 2))
    for d0, d1, extra, sinal in ((-hd - HORN_E - 3.0, -hd - HORN_E, (), 1.0),
                                 (hd + HORN_E, hd + HORN_E + 3.0, (_circulo(0.0, 0.0, 3.0, 16),), -1.0)):
        cj.j(Ms, "alu_laranja", _ext(face, furos_g + extra, d0, d1), R_XZ_Y)
        d_ext = d0 if sinal > 0 else d1
        for i in range(0, 8, 2):
            a = _TAU * i / 8
            cj.parafuso(Ms, (0.5 * PCD_HORN * math.cos(a), d_ext, 0.5 * PCD_HORN * math.sin(a)), (0, sinal, 0), "M2",
                        aperto=3.0, rosca_metida=2.0, peca="cotovelo_garfo")
    cj.j(Ms, "alu_laranja", _caixa(-12.0, 12.0, -hd - HORN_E, hd + HORN_E, z_ponte, z_ponte + 6.0, r=1.0))
    # o ponteiro cola na face de dentro do braço do garfo, de r = 10,4 (fora do horn Ø20: medido, com r = 9 entrava
    # 0,72 mm no aro do horn) até r = 15,5, por cima dos traços da escala (1,2 mm à frente da face do servo)
    _ponteiro(cj, Ms, np.eye(3), np.array([0.0, -hd - HORN_E, 0.0]) + np.array([0.0, 0.8, 0.0]), 12.4, 15.5, 0.8,
              "cotovelo_garfo")
    # ---------------------------------------------------------------- mastro Ø16 e abraçadeira da placa do motor
    z_m0 = z_ponte + 6.0
    _abracadeira_fenda(cj, Ms, "alu_laranja", "cotovelo_garfo", (0.0, 0.0, z_m0), (0, 0, 1), (-1, 0, 0), 8.0, 12.0, 0.0,
                       16.0, (8.0,), folga=1.0, meio=5.5)
    cj.j(Ms, "carbono", _anel(8.0, 7.0, z_m0, z_p0 - 4.0, 28), None, None, "mastro")
    cj.peca = "suporte_motor"
    _abracadeira_fenda(cj, Ms, "alu_vermelho", "suporte_motor", (0.0, 0.0, z_p0 - 18.0), (0, 0, 1), (-1, 0, 0), 8.0,
                       12.0, 0.0, 14.0, (7.0,), folga=1.0, meio=5.5)
    cj.j(Ms, "alu_vermelho", _cil(min(r_neck, 12.0), z_p0 - 4.0, z_p0, 36), None, None, "suporte_motor")
    return cj.congelar()


# ===================================================================================================== TREM DE POUSO
@functools.cache
def _perna_canonica(s_leg: float, z_t: float, r_t: float, z_fundo: float) -> tuple:
    """Trem de pouso no referencial do braço (+x ao longo do braço, mm): abraçadeira de 2 metades no tubo (eixo a z_t),
    casquilho da perna por baixo (perno DIN 916), perna de carbono Ø12 e pé de borracha com o fundo em `z_fundo`
    (o ponto de contacto da cápsula física)."""
    cj = _Conj()
    cj.peca = "perna"
    info = _abracadeira_dupla(cj, "p", "alu_preto", "perna", (s_leg, 0.0, z_t), (1, 0, 0), (0, 1, 0), r_t, -11.0, 11.0,
                              (0.0,))
    z_bt = z_t + info["n_fundo"]
    z_b = z_bt - 16.0
    bossa = tuple((min(x, 8.8), y) for x, y in _circulo(0.0, 0.0, 9.0, 32))
    cj.j("p", "alu_preto", _ext(bossa, (_circulo(0.0, 0.0, 6.0, 24),), z_b, z_bt), None, (s_leg, 0.0, 0.0))
    cj.ferragem("perno", "p", (s_leg + 8.8, 0.0, z_b + 8.0), (-1, 0, 0), rosca="M3", comp=3.0, peca="perna")
    z_pe = z_fundo
    cj.j("p", "carbono_liso", _anel(6.0, 5.0, z_pe + 10.0, z_bt, 20), None, (s_leg, 0.0, 0.0))
    pe = (((0.0, z_pe), (5.5, z_pe + 0.3)), ((5.5, z_pe + 0.3), (9.0, z_pe + 1.6), (10.8, z_pe + 3.8), (11.2, z_pe + 6.0),
                                            (10.6, z_pe + 8.2), (9.0, z_pe + 10.2), (8.2, z_pe + 11.5)),
          ((8.2, z_pe + 11.5), (8.2, z_pe + 19.0)), ((8.2, z_pe + 19.0), (7.6, z_pe + 19.6)),
          ((7.6, z_pe + 19.6), (6.0, z_pe + 19.6)), ((6.0, z_pe + 19.6), (6.0, z_pe + 10.0)),
          ((6.0, z_pe + 10.0), (0.0, z_pe + 10.0)))
    cj.j("p", "borracha", _torno(pe, 28), None, (s_leg, 0.0, 0.0))
    return cj.congelar()


# ===================================================================================================== BRAÇO RÍGIDO
def _tubo_do_frame(hw):
    """Raio do tubo dos braços (m) a partir do catálogo («tubo(s) de carbono 25×23 mm», «… 16 mm»); `None` = braços em
    placa (frames de corrida de 5″); sem número, 16 mm (os X500/Tarot 650 usam tubo de 16 mm)."""
    texto = f"{getattr(hw.frame, 'modelo', '')} {hw.frame.dados.get('modelo', '')}"
    m = re.search(r"tubos? de carbono (\d+(?:[.,]\d+)?)", texto)          # «tubo»/«tubos» (o frame em ABS)
    if m:
        return 0.5 * float(m.group(1).replace(",", ".")) / 1000.0
    if hw.frame.wheelbase < 0.30:
        return None
    return 0.008


def _padrao_motor(hw) -> dict:
    """A furação da base do motor — SEMPRE a do módulo dos motores (`motores.padrao_base`), nunca números copiados."""
    from .motores import padrao_base
    pb = dict(padrao_base(hw.motor))
    pb["furos_mm"] = [tuple(float(v) for v in f) for f in pb.get("furos_mm", [])]
    return pb


def _frente_suporte(braco_mm: float, pb: dict, w_m: float) -> float:
    """Até onde (ao longo do braço) pode ir a abraçadeira do tubo por baixo da placa do motor sem tapar as cabeças dos
    parafusos do motor (que sobem por baixo da placa) nem o furo central."""
    rosca = pb.get("rosca", "M3")
    r_cab = 0.5 * fer.ISO4762.get(rosca, fer.ISO4762["M3"])[0] + 0.5
    s = braco_mm - 0.5 * float(pb.get("furo_central_mm", 9.0)) - 1.0
    for x, y in pb["furos_mm"]:
        if abs(y) < w_m + fer.ISO4762.get(rosca, fer.ISO4762["M3"])[0] + 1.0:
            s = min(s, braco_mm + x - r_cab)
    return s


@functools.cache
def _braco_rigido_canonico(braco: float, z_t: float, r_t: float, s_c: float, esp: float, l_c: float, s_m: float,
                           l_m: float, z_mot0: float, s_r: float, topo_r: float | None = None,
                           maxila: tuple | None = None) -> tuple:
    """Braço do build rígido no referencial do braço (mm, +x para fora, origem no centro da placa de baixo): tubo,
    abraçadeira de 2 metades no canto da placa (as maxilas apertam a placa), abraçadeira + placa do motor (a placa é o
    geom `suporte_motor_k`, à parte) e a abraçadeira das treliças com as 2 linguetas dos garfos (`s_r` < 0: sem)."""
    cj = _Conj()
    U, V = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    cj.peca = "tubo_braco"
    _tubo(cj, "d", (1, 0, 0), s_c + 0.5, s_m - 2.0, r_t, "tubo_braco", C=(0.0, 0.0, z_t), parede=1.0)
    # ---------------------------------------------------------------- abraçadeira do canto da placa
    cj.peca = "abracadeira_tubo"
    topo = esp + 4.0 - z_t
    info = _abracadeira_dupla(cj, "d", "alu_preto", "abracadeira_tubo", (0.0, 0.0, z_t), U, V, r_t, s_c, s_c + l_c,
                              (s_c + 0.25 * l_c, s_c + 0.75 * l_c), topo=topo)
    w_m = info["w_m"]
    g = 0.25
    # `maxila` = (s, |n|) dos 2 parafusos e as ORELHAS laterais onde eles ficam (s_e0, s_e1, |n| ≤ w_e) — quando o
    # ESC passa por cima do meio das maxilas; omissão: os parafusos em (s_c − 7, ±w_m/2), sem orelhas
    if maxila is None:
        s_mx, n_s = s_c - 7.0, 0.5 * w_m
        perfil_mx = _ret(s_c - 14.0, s_c, -w_m, w_m, r=1.0)
    else:
        s_mx, n_s, s_e0, s_e1, w_e = maxila
        v = [(s_c - 14.0, -w_m), (s_e0, -w_m), (s_e0, -w_e), (s_e1, -w_e), (s_e1, -w_m), (s_c, -w_m), (s_c, w_m),
             (s_e1, w_m), (s_e1, w_e), (s_e0, w_e), (s_e0, w_m), (s_c - 14.0, w_m)]
        perfil_mx = _poligono_arred(tuple(v), 1.0)
    furos_m = tuple(_circulo(s_mx, y, 0.5 * FURO_PASSANTE["M3"], 14) for y in (-n_s, n_s))
    cj.j("d", "alu_preto", _ext(perfil_mx, furos_m, esp, esp + 4.0))
    cj.j("d", "alu_preto", _ext(perfil_mx, furos_m, z_t + g, -esp))
    for y in (-n_s, n_s):
        cj.parafuso("d", (s_mx, y, esp + 4.0), (0, 0, -1), "M3", aperto=esp + 4.0 - (z_t + g),
                    porca="ISO 10511", peca="abracadeira_tubo")
    # ---------------------------------------------------------------- abraçadeira do motor (a ponta do tubo)
    cj.peca = "suporte_motor"
    info_m = _abracadeira_dupla(cj, "d", "alu_vermelho", "suporte_motor", (0.0, 0.0, z_t), U, V, r_t, s_m - l_m, s_m,
                                (s_m - 0.78 * l_m, s_m - 0.22 * l_m), topo=z_mot0 - z_t, parede=2.5)
    for z0, z1 in ((z_t + g, z_mot0), (z_t - r_t - 3.0, z_t - g)):          # tampa do fim do tubo (2 metades)
        cj.j("d", "alu_vermelho", _caixa(s_m - 2.0, s_m, -info_m["w_m"], info_m["w_m"], z0, z1))
    # ---------------------------------------------------------------- treliças: abraçadeira de fenda + linguetas
    if s_r > 0.0:
        cj.peca = "abracadeira_tubo"
        _abracadeira_fenda(cj, "d", "alu_preto", "abracadeira_tubo", (s_r - 11.0, 0.0, z_t), U, (0, 0, -1), r_t,
                           r_t + 3.0, 0.0, 22.0, (5.0, 17.0), folga=1.0, meio=6.0, topo=topo_r)
        for lado in (-1, 1):
            y_p = r_t + 3.0 + 9.0
            perfil = [(s_r - 6.0, r_t + 1.5), (s_r + 6.0, r_t + 1.5), (s_r + 6.0, y_p)]
            perfil += [(s_r + 6.0 * math.cos(a), y_p + 6.0 * math.sin(a)) for a in np.linspace(0.0, math.pi, 13)[1:-1]]
            perfil += [(s_r - 6.0, y_p)]
            if lado < 0:
                perfil = [(x, -y) for x, y in perfil][::-1]
            cj.j("d", "alu_preto", _ext(tuple(perfil), (_circulo(s_r, lado * y_p, 0.5 * FURO_PASSANTE["M3"], 14),),
                                        z_t - 2.5, z_t + 2.5))
    _ = braco                                     # (só para a chave da cache: o desenho é o mesmo em todos os braços)
    return cj.congelar(), info, info_m


def _ponta_trelica(mt, pino, direcao, z_t, idx):
    """Ponta de um varão de travamento (no corpo `drone`, mm nominais): garfo de alumínio com 2 orelhas à volta da
    lingueta da abraçadeira, pino M3 (parafuso + porca) e o casquilho onde o varão de carbono Ø8 entra. Devolve o
    ponto (mm) onde acaba o varão dentro do casquilho."""
    d = _unit((direcao[0], direcao[1], 0.0))
    R = _base(d, np.cross((0, 0, 1), d), (0, 0, 1))
    pino = np.array([pino[0], pino[1], z_t])
    perfil = [(16.0, -4.5), (16.0, 4.5)] + [(5.5 * math.cos(a), 5.5 * math.sin(a))
                                            for a in np.linspace(0.5 * math.pi, 1.5 * math.pi, 13)]
    perfil = tuple((round(x, 5), round(y, 5)) for x, y in perfil)
    furo = (_circulo(0.0, 0.0, 0.5 * FURO_PASSANTE["M3"], 14),)
    for z0, z1 in ((2.75, 5.25), (-5.25, -2.75)):
        mt.juntar("drone", "alu_natural", _ext(perfil, furo, z0, z1), "trelica", idx, R, pino)
    mt.juntar("drone", "alu_natural", _caixa(10.0, 16.0, -4.5, 4.5, -2.75, 2.75, r=0.0), "trelica", idx, R, pino)
    mt.juntar("drone", "alu_natural", _cil(5.5, 16.0, 30.0, 24), "trelica", idx, R @ _r_eixo((1, 0, 0)), pino)
    col = mt.ctx.ferragens
    if col is not None:
        p = pino + np.array([0.0, 0.0, 5.25])
        reg = col.parafuso("drone", mt.ponto_m("drone", p), (0, 0, -1), "M3", aperto=10.5, porca="ISO 10511",
                           anilha_porca=False, peca="trelica", inst=idx, ref=tuple(d))
        mt.ferragens.append(("drone", p, np.array([0.0, 0.0, -1.0]), reg))
    return pino + d * 22.0


def _placa_motor_malha(pb: dict, r_p: float, z0: float, z1: float, entalhe: float | None, w_entalhe: float,
                       rot: float) -> tuple:
    """Placa do motor (mm, no referencial do geom `suporte_motor_k`): disco com os furos M3 da base do motor
    (`motores.padrao_base`), o furo central do veio/circlip, rasgos de alívio e — no rígido — o entalhe por onde entra
    a abraçadeira do tubo (x < `entalhe` ao longo do braço)."""
    ca, sa = math.cos(rot), math.sin(rot)

    def rodar(x, y):
        return (round(ca * x - sa * y, 5), round(sa * x + ca * y, 5))
    n = 48
    x_b = -math.sqrt(max(r_p ** 2 - w_entalhe ** 2, 0.0))
    if entalhe is not None and entalhe > x_b + 0.5:
        ang_w = math.asin(min(0.999, w_entalhe / r_p))
        a0, a1 = math.pi + ang_w, 3.0 * math.pi - ang_w          # de (x_b, −w) à volta pela frente até (x_b, +w)
        m = max(int(n * (a1 - a0) / _TAU), 8)
        pts = [(r_p * math.cos(a), r_p * math.sin(a)) for a in np.linspace(a0, a1, m + 1)]
        pts += [(entalhe, w_entalhe), (entalhe, -w_entalhe)]
    else:
        pts = [(r_p * math.cos(_TAU * i / n), r_p * math.sin(_TAU * i / n)) for i in range(n)]
    contorno = tuple(rodar(x, y) for x, y in pts)
    if _area2(contorno) < 0:
        contorno = contorno[::-1]
    furos = [tuple(rodar(x, y) for x, y in _circulo(fx, fy, 0.5 * FURO_PASSANTE.get(pb.get("rosca", "M3"), 3.4), 14))
             for fx, fy in pb["furos_mm"]]
    rc = 0.5 * float(pb.get("furo_central_mm", 9.0))
    furos.append(tuple(rodar(x, y) for x, y in _circulo(0.0, 0.0, rc, 24)))
    alivio = []
    for i in range(4):
        b = math.pi / 4 + i * math.pi / 2 + math.pi / 4
        c = 0.5 * (rc + r_p) + 1.0
        alivio.append(tuple(rodar(x, y) for x, y in _rasgo(c * math.cos(b), c * math.sin(b),
                                                           0.18 * r_p, 0.09 * r_p + 0.6, ang=b + math.pi / 2)))
    furos = list(furos) + list(_furos_que_cabem(contorno, tuple(alivio), 1.5, fixos=tuple(furos)))
    return _ext(contorno, tuple(furos), z0, z1)


# ===================================================================================================== PLACAS
def _fpc_placa_carbono(ctx, L: float, gb):
    """(x, y, r) do furo de alívio de (0,77·L, −0,29·L) quando tem de mudar para servir de SUBIDA DO FPC da câmara CSI (os
    fios procuram aí um disco livre de Ø ≥ 12,2 fora da pegada das baterias) — ou None (fica como sempre esteve):
    · placas pequenas (x500, compacto: Ø 0,134·L < 12,6) → Ø 14;
    · o furo cai por cima da bateria do build (packs compridos; x500/compacto) → Ø 14 para o lado, em |y| = meia-largura
      + 7 (a maior entre o pack do build e as variantes do painel nos frames grandes). Os outros builds ficam iguais."""
    cam = getattr(ctx.hw, "camera", None)
    if cam is None or str(cam.dados.get("tipo", "")) != "modulo_camera_csi" or L < 60.0:
        return None                                   # (no 5″ o FPC fica pelo percurso antigo, como sempre)
    x, y, r = 0.77 * L, -0.29 * L, 0.067 * L
    x_n, y_n, r_n = x, y, (r if r >= 6.3 else 7.0)
    if gb is not None:
        meio_c, meio_l = float(gb.size[0]) / MM, float(gb.size[1]) / MM
        if float(ctx.hw.frame.wheelbase) >= 0.40:
            from ..componentes import CATALOGO_BATERIAS_PAINEL
            meio_l = max([meio_l] + [0.5 * float(v["dims_mm"][1]) for v in CATALOGO_BATERIAS_PAINEL.values()])
        if x <= meio_c + 1.0 and abs(y) <= meio_l + 6.75:
            y_n = -(meio_l + 7.0)
            r_n = max(r_n, 7.0)
    if (x_n, y_n, r_n) == (x, y, r):
        return None
    return (round(x_n, 4), round(y_n, 4), round(r_n, 4))


def _desenho_placas(art: bool, L: float, pin1: tuple, bateria, Ls: float, fpc=None):
    """(contorno, furos de alívio/cablagem) da placa de baixo e da de cima (mm) — desenhadas para a placa de 208 mm, à
    escala da placa do build; os furos de parafusos acrescentam-se à parte. `fpc` = (x, y, r) troca o furo de alívio
    de (0,77·L, −0,29·L) pela subida do FPC da câmara (`_fpc_placa_carbono`)."""
    if art:
        x_n, y_n = abs(pin1[0]) - 26.5, abs(pin1[1]) - 52.5      # entalhe da caixa do redutor + encoder + cubo
        v = [(L, -y_n), (L, y_n), (x_n, y_n), (x_n, L), (-x_n, L), (-x_n, y_n), (-L, y_n), (-L, -y_n),
             (-x_n, -y_n), (-x_n, -L), (x_n, -L), (x_n, -y_n)]
    else:
        c = 0.23 * L
        v = [(L, -L + c), (L, L - c), (L - c, L), (-L + c, L), (-L, L - c), (-L, -L + c), (-L + c, -L), (L - c, -L)]
    ext_b = _poligono_arred(tuple(v), 3.0)
    furos = [_poligono_arred(((0.22 * L, -0.125 * L), (0.22 * L, 0.125 * L), (-0.22 * L, 0.125 * L),
                              (-0.22 * L, -0.125 * L)), 0.048 * L)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            if bateria is not None:
                cb, lb = bateria
                furos.append(_rasgo(sx * 0.28 * cb, sy * (0.5 * lb + 6.5), 8.0, 2.0))
            furos.append(_circulo(sx * 0.29 * L, sy * 0.77 * L, 0.067 * L))
            if fpc is not None and (sx, sy) == (1, -1):
                furos.append(_circulo(fpc[0], fpc[1], fpc[2], 28))
            else:
                furos.append(_circulo(sx * 0.77 * L, sy * 0.29 * L, 0.067 * L))
    janela = _poligono_arred(((47.0, -32.0), (47.0, 32.0), (-47.0, 32.0), (-47.0, -32.0)), 6.0)
    furos_s = [janela]
    if art:
        x_h, y_h = abs(pin1[0]), abs(pin1[1])
        # quadrado ±Ls com 4 ORELHAS nos cantos (a mesa do servo do ombro e dos suportes): x ∈ [x_h−63, x_h+11,5],
        # y ∈ [y_h−44, y_h−13] (no braço 1; espelho nos outros), contorno anti-horário
        xo0, xo1 = x_h - 63.0, x_h + 11.5
        yo0, yo1 = y_h - 44.0, y_h - 13.0
        pts = [(xo1, -yo1), (xo1, -yo0), (Ls, -yo0), (Ls, yo0), (xo1, yo0), (xo1, yo1), (xo0, yo1), (xo0, Ls),
               (-xo0, Ls), (-xo0, yo1), (-xo1, yo1), (-xo1, yo0), (-Ls, yo0), (-Ls, -yo0), (-xo1, -yo0), (-xo1, -yo1),
               (-xo0, -yo1), (-xo0, -Ls), (xo0, -Ls), (xo0, -yo1)]
        ext_s = _poligono_arred(tuple(pts), 2.5)
        furos_s += [_rasgo(sx * 72.0 * Ls / 91.5, 0.0, 16.0, 7.0, ang=math.pi / 2) for sx in (-1, 1)]
        furos_s += [_rasgo(0.0, sy * 64.0 * Ls / 91.5, 24.0, 7.0) for sy in (-1, 1)]
    else:
        c = 0.197 * Ls
        v = [(Ls, -Ls + c), (Ls, Ls - c), (Ls - c, Ls), (-Ls + c, Ls), (-Ls, Ls - c), (-Ls, -Ls + c), (-Ls + c, -Ls),
             (Ls - c, -Ls)]
        furos_s += [_rasgo(sx * 0.765 * Ls, 0.0, 0.197 * Ls, 0.087 * Ls, ang=math.pi / 2) for sx in (-1, 1)]
        furos_s += [_rasgo(0.0, sy * 0.678 * Ls, 0.273 * Ls, 0.087 * Ls) for sy in (-1, 1)]
        ext_s = _poligono_arred(tuple(v), 3.0)
    return ext_b, tuple(furos), ext_s, tuple(furos_s)


def _furos_parafusos(ctx, mt, corpo: str, z0: float, z1: float) -> list:
    """Furos de passagem (mm, (x, y, raio)) de TODAS as ferragens já registadas (as dos outros módulos e as nossas)
    cujo eixo é vertical e cuja haste atravessa a laje z0..z1 (mm nominais) do corpo."""
    o = mt.origem_m(corpo) / MM
    out, vistos = [], set()
    for r in ctx.registo.ferragens:
        if r.get("corpo") != corpo:
            continue
        e = np.asarray(r.get("eixo", (0, 0, 1)), float)
        if abs(e[2]) < 0.99:
            continue
        p = np.asarray(r["ponto"], float) / MM - o
        t = r.get("tipo")
        if t == "parafuso":
            a, b = p, p + e * float(r.get("comp_mm") or 0.0)
        elif t == "pilar" and float(r.get("macho_mm") or 0.0) > 0.0:
            a = p + e * float(r["comp_mm"])
            b = a + e * float(r["macho_mm"])
        else:
            continue
        lo, hi = min(a[2], b[2]), max(a[2], b[2])
        if hi < z0 + 0.1 or lo > z1 - 0.1:
            continue
        chave = (round(p[0], 2), round(p[1], 2))
        if chave in vistos:
            continue
        vistos.add(chave)
        d = FURO_PASSANTE.get(r.get("rosca"), fer.DIAMETRO.get(r.get("rosca"), 3.0) + 0.4)
        out.append((float(p[0]), float(p[1]), 0.5 * d))
    return out


def _placas(mt: _Montador, art: bool, L: float, esp: float, zs0: float, zs1: float, pin1, furos_extra):
    """Placa de baixo (malha nova; a de massa fica invisível) e placa de cima (`placa_superior` reestilizada), com os
    furos de TODOS os parafusos que as atravessam (os nossos e os dos outros módulos) e os de alívio que cabem."""
    ctx = mt.ctx
    gb, g = ctx.geom_existente("bateria"), ctx.geom_existente("placa_superior")
    bateria = (round(2.0 * float(gb.size[0]) / MM, 5), round(2.0 * float(gb.size[1]) / MM, 5)) if gb is not None else None
    # os rasgos das cintas da bateria: os que a eletrónica publica (`notas["rasgos_cintas"]`: centro no corpo, 20 × 4,
    # eixo comprido) — se existirem substituem os de reserva (calculados pela caixa do pack)
    rasgos = []
    for r in (ctx.registo.notas.get("rasgos_cintas") or []):
        if r.get("corpo", "drone") != "drone":
            continue
        c = (np.asarray(r["centro"], float) - mt.origem_m("drone")) / MM
        comp, larg = float(r.get("comprimento_mm", 20.0)), float(r.get("largura_mm", 4.0))
        e = r.get("eixo_comprido", (1.0, 0.0, 0.0))
        rasgos.append(_rasgo(float(c[0]), float(c[1]), 0.5 * max(comp - larg, 0.0), 0.5 * larg,
                             ang=math.atan2(float(e[1]), float(e[0]))))
    Ls = round(float(g.size[0]) / MM, 5) if g is not None else round(0.88 * L, 5)
    ext_b, alivio_b, ext_s, alivio_s = _desenho_placas(art, round(L, 5), (round(pin1[0], 5), round(pin1[1], 5)),
                                                       None if rasgos else bateria, Ls, fpc=_fpc_placa_carbono(ctx, L, gb))
    for nome_p, ext, alivio, z0, z1 in (("inf", ext_b, alivio_b, -esp, esp), ("sup", ext_s, alivio_s, zs0, zs1)):
        furos_p = [_circulo(x, y, r, 14) for x, y, r in _furos_parafusos(ctx, mt, "drone", z0, z1)]
        furos_p += [_circulo(x, y, r, 18) for (x, y), r, placa in furos_extra if placa == nome_p]
        if nome_p == "inf":
            furos_p += rasgos
        furos_p = [f for f in furos_p if all(_no_poligono(x, y, ext) for x, y in f)]
        furos = tuple(furos_p) + _furos_que_cabem(ext, alivio, 2.0, fixos=tuple(furos_p))
        if nome_p == "inf":
            mt.juntar("drone", "carbono", _ext(ext, furos, z0, z1), "placa_inferior")
            ctx.esconder("placa")
        elif g is not None:
            zc = 0.5 * (zs0 + zs1)
            v, f, t = _ext(ext, furos, zs0 - zc, zs1 - zc)
            _reestilizar_malha(ctx, g, "m_est_placa_superior", (v * MM, f, t), mt.mat["carbono"], "placa_superior")


def _espacadores(mt: _Montador, esp: float, zs0: float, zs1: float, L: float):
    """Os 4 espaçadores de alumínio Ø5 M3 fêmea-fêmea (`espacador_placa_*`, reestilizados) entre as placas, com um
    parafuso ISO 4762 M3 por cima e outro por baixo (rosca metida ≥ 1,5·d nos espaçadores)."""
    ctx = mt.ctx
    a = 0.577 * L if L >= 90.0 else 0.78 * L
    perfil = (((0.0, 0.0), (2.2, 0.0)), ((2.2, 0.0), (2.5, 0.3)), ((2.5, 0.3), (2.5, zs0 - esp - 0.3)),
              ((2.5, zs0 - esp - 0.3), (2.2, zs0 - esp)), ((2.2, zs0 - esp), (0.0, zs0 - esp)))
    for i, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1)), start=1):
        g = ctx.geom_existente(f"espacador_placa_{i}")
        if g is None:
            continue
        x, y = sx * a, sy * a
        v, f, t = _torno(perfil, 20)
        g.pos = ctx.p(x * MM, y * MM, esp * MM)
        g.size = [0.0025, 0.5 * (zs0 - esp) * MM, 0.0]
        _reestilizar_malha(ctx, g, f"m_est_espacador_{i}", (v * MM, f, t), mt.mat["alu_natural"], "espacadores", 0)
        col = ctx.ferragens
        if col is not None:
            for p, e, aperto in (((x, y, zs1), (0, 0, -1), zs1 - zs0), ((x, y, -esp), (0, 0, 1), 2.0 * esp)):
                reg = col.parafuso("drone", mt.ponto_m("drone", p), e, "M3", aperto=aperto, rosca_metida=4.5,
                                   peca="espacadores", inst=0)
                mt.ferragens.append(("drone", np.asarray(p, float), np.asarray(e, float), reg))


# ===================================================================================================== frames
def _dados_perna(mt: _Montador, corpo: str, nome: str):
    """(raio ao longo do braço, z do fundo da cápsula) da perna física (mm, no referencial nominal do corpo)."""
    g = mt.ctx.geom_existente(nome)
    if g is None:
        return None
    ft = np.array(g.fromto, float)
    o = mt.origem_m(corpo)
    a, b = (ft[:3] - o) / MM, (ft[3:] - o) / MM
    return round(math.hypot(a[0], a[1]), 4), round(min(a[2], b[2]) - float(g.size[0]) / MM, 4)


def _faixa_esc(ctx, k: int):
    """(s0, s1) ao longo do braço ocupados pelo ESC AIR 40A que a eletrónica põe em cima do tubo (ou None)."""
    g = ctx.geom_existente(f"esc{k}")
    if g is None:
        return None
    p = np.array(g.pos, float) / MM
    s = math.hypot(p[0], p[1])
    return s - 32.0, s + 32.0


def _ocultar_visual(g) -> None:
    """Esconde um detalhe VISUAL do modelo base (massa 0, sem contacto) que neste build não existe: alfa 0 E sem material
    — com o material, o `mj_ray` (auditoria F2/F3, deteção) continuaria a bater nele (só ignora alfa 0 sem material)."""
    g.material = ""
    g.rgba = [0.0, 0.0, 0.0, 0.0]


def _tris_peca(ctx, corpo: str, peca: str, inst: int):
    """Triângulos (N, 3, 3; m, no referencial do corpo) das faces de uma peça (`registo.faixas`) nas malhas fundidas
    que já estão no spec (as dos módulos que correram antes) — ou None."""
    malhas = {me.name: me for me in ctx.spec.meshes}
    pts = []
    for nome, fx in ctx.registo.faixas.items():
        sel = [(a, b) for pc, i, a, b in fx if pc == peca and int(i) == int(inst)]
        if not sel:
            continue
        g = ctx.geom_existente(nome)
        if g is None or g.parent is None or g.parent.name != corpo:
            continue
        me = malhas.get(g.meshname)
        if me is None or not len(me.uservert):
            continue
        V = np.asarray(me.uservert, float).reshape(-1, 3)
        F = np.asarray(me.userface, np.int64).reshape(-1, 3)
        Rg = np.zeros(9)
        mujoco.mju_quat2Mat(Rg, np.asarray(g.quat, float))
        W = V @ Rg.reshape(3, 3).T + np.asarray(g.pos, float)
        pts.append(W[np.concatenate([F[a:b] for a, b in sel])])
    return np.concatenate(pts) if pts else None


def _maxila_fora_do_esc(ctx, hw, o, s_c: float, esp: float, w_m: float, L: float):
    """(s, |n| dos 2 M3 das maxilas, s_e0, s_e1, w_e das orelhas) quando o ESC À VISTA do braço 1 (a malha do
    `eletronica`, não a caixa física) cobre as cabeças dos 2 M3 das maxilas (s_c − 7, n = ±w_m/2): os parafusos vão
    para os lados, 0,55 mm por fora do ESC, em orelhas das maxilas que têm de caber na placa (octógono do rígido com
    1 mm de margem; o sítio dos parafusos recua até 3 mm se for preciso). None = fica como sempre."""
    T = _tris_peca(ctx, "drone", "esc", 1)
    if T is None or not len(T):
        return None
    a1 = math.atan2(hw.pos_rotores[0][1], hw.pos_rotores[0][0])
    u1 = np.array([math.cos(a1), math.sin(a1), 0.0])
    n1 = np.array([-u1[1], u1[0], 0.0])
    Q = T / MM - o                                         # (N, 3, 3) mm
    S, N, Z = Q @ u1, Q @ n1, Q[..., 2]
    r_cab = 0.5 * fer.ISO4762["M3"][0]
    s0, s1 = s_c - 14.0, s_c
    na_zona = (Z.max(axis=1) > esp + 0.05) & (S.max(axis=1) >= s0) & (S.min(axis=1) <= s1)
    sobre = na_zona & (N.min(axis=1) <= 0.5 * w_m + r_cab + 0.3) & (N.max(axis=1) >= -(0.5 * w_m + r_cab + 0.3))
    if not np.any(sobre):
        return None
    n_esc = float(np.max(np.abs(np.concatenate([N.min(axis=1)[na_zona], N.max(axis=1)[na_zona]]))))
    n_s = round(n_esc + r_cab + 0.55, 4)
    w_e = round(n_s + r_cab + 0.9, 4)
    c = 0.23 * L
    octo = ((L, -L + c), (L, L - c), (L - c, L), (-L + c, L), (-L, L - c), (-L, -L + c), (-L + c, -L), (L - c, -L))
    for recuo in np.arange(0.0, 3.01, 0.5):
        s_mx = s_c - 7.0 - float(recuo)
        s_e0, s_e1 = s_mx - r_cab - 1.25, s_mx + r_cab + 1.25
        cantos = [s_ * u1 + n_ * n1 for s_ in (s_e0, s_e1) for n_ in (-w_e - 1.0, w_e + 1.0)]
        if s_e0 >= s0 + 1.0 and all(_no_poligono(float(p_[0]), float(p_[1]), octo) for p_ in cantos):
            return (round(s_mx, 4), n_s, round(s_e0, 4), round(s_e1, 4), w_e)
    return None


def _frame_rigido(mt: _Montador, hw, esp: float, L: float):
    ctx = mt.ctx
    r_t_m = _tubo_do_frame(hw)
    braco = round(hw.braco / MM, 4)
    pb = _padrao_motor(hw)
    d_mot = float(hw.motor.dados.get("diametro_mm", 28.0))
    r_p = round(0.5 * d_mot + 1.5, 4)
    for k in range(1, 5):
        g = ctx.geom_existente(f"braco{k}")
        if g is not None:
            ctx.esconder(f"braco{k}")
    if r_t_m is None:
        _frame_corrida(mt, hw, esp, L, pb, r_p)
        return
    r_t = round(r_t_m / MM, 4)
    z_t = round(2.5 - r_t, 4)                   # topo do tubo a +2,5 mm: os ESC assentam aí (a eletrónica)
    s_c = round((2.0 * L - 0.23 * L) / math.sqrt(2.0), 4)
    w_m = r_t + 2.0
    g_sup = ctx.geom_existente("suporte_motor_1")
    o = mt.origem_m("drone") / MM
    z_mot0 = round(float(g_sup.pos[2]) / MM - o[2] + float(g_sup.size[1]) / MM - 1.0, 4) if g_sup is not None else 5.0
    g_mot = ctx.geom_existente("motor1")
    if g_mot is not None:
        z_mot0 = round(float(g_mot.pos[2]) / MM - o[2] - float(g_mot.size[1]) / MM, 4)
    z_p0 = round(float(g_sup.pos[2]) / MM - o[2] - float(g_sup.size[1]) / MM, 4) if g_sup is not None else z_mot0 - 4.0
    s_m = round(_frente_suporte(braco, pb, w_m), 4)
    l_m = round(min(2.0 * r_t + 6.0, 34.0), 4)
    perna = _dados_perna(mt, "drone", "perna1")
    s_leg = perna[0] if perna is not None else 0.55 * braco
    faixa = _faixa_esc(ctx, 1)
    l_c = 2.4 * 2.0 * r_t
    l_c = min(l_c, s_leg - 17.0 - s_c)
    if faixa is not None and faixa[0] > s_c + 13.0:
        l_c = min(l_c, faixa[0] - 1.0 - s_c)
    l_c = round(max(l_c, 12.0), 4)
    # a abraçadeira das treliças: 0,34 do braço (o sítio das físicas) se couber entre as outras peças
    ocupado = [(s_c - 15.0, s_c + l_c + 1.0), (s_leg - 16.0, s_leg + 16.0), (s_m - l_m - 1.0, braco + r_p)]
    if faixa is not None:
        ocupado.append(faixa)
    s_r_alvo = 0.34 * braco
    candidatos = [s_r_alvo] + [b + 13.0 for a, b in ocupado] + [a - 13.0 for a, b in ocupado]
    livres = [s for s in candidatos if all(s + 12.0 < a or s - 12.0 > b for a, b in ocupado) and s_c < s < s_m]
    s_r = round(min(livres, key=lambda s: abs(s - s_r_alvo)), 4) if livres else -1.0
    # as BALAS das fases (do `motores`, por cima do tubo) logo a seguir à abraçadeira das treliças (x500/compacto: 2 mm)
    # → o anel dela leva uma face plana em cima 1,5 mm mais baixa (parede de 1,5 mm), para a fêmea e o 16 AWG passarem
    topo_r = None
    if s_r > 0.0:
        a1 = math.atan2(hw.pos_rotores[0][1], hw.pos_rotores[0][0])
        u1 = np.array([math.cos(a1), math.sin(a1), 0.0])
        s_b, z_b = [], []
        for f in "abc":
            gb = ctx.geom_existente(f"motor1_fase_{f}_conector")
            ft = np.asarray(gb.fromto, float) if gb is not None else np.full(6, np.nan)
            if gb is None or not np.all(np.isfinite(ft)):
                continue
            for q in (ft[:3] / MM - o, ft[3:] / MM - o):
                s_b.append(float(q @ u1))
                z_b.append(float(q[2]) - float(gb.size[0]) / MM)
        if s_b and min(s_b) - (s_r + 11.0) < 12.0 and min(z_b) < z_t + r_t + 3.0 + 1.25:
            topo_r = round(r_t + 1.5, 4)
    conj, info, info_m = _braco_rigido_canonico(braco, z_t, r_t, s_c, round(esp, 4), l_c, s_m, l_m, z_mot0, s_r,
                                                topo_r)
    # o ESC do `eletronica` (malha à vista, não a caixa física) que passa por cima do canto da placa: os 2 M3 das
    # MAXILAS iam dar no termo-retráctil dele → vão para orelhas laterais das maxilas, por fora do ESC (se couberem
    # na placa); no resto dos builds fica tudo como estava
    mx = _maxila_fora_do_esc(ctx, hw, o, s_c, esp, info["w_m"], L)
    if mx is not None:
        conj, info, info_m = _braco_rigido_canonico(braco, z_t, r_t, s_c, round(esp, 4), l_c, s_m, l_m, z_mot0,
                                                    s_r, topo_r, mx)
    pinos = {}
    for i, (x, y) in enumerate(hw.pos_rotores):
        k = i + 1
        ang = math.atan2(y, x)
        R = _rot_z(ang)
        mt.colocar(conj, {"d": "drone"}, R, {}, inst=k)
        perna = _dados_perna(mt, "drone", f"perna{k}")
        if perna is not None:
            mt.colocar(_perna_canonica(perna[0], z_t, r_t, perna[1]), {"p": "drone"}, R, {}, inst=k)
            ctx.esconder(f"perna{k}")
        g = ctx.geom_existente(f"suporte_motor_{k}")
        if g is not None:                     # a placa do motor: disco com a furação do motor e o entalhe da abraçadeira
            zc = float(g.pos[2]) / MM - o[2]
            parte = _placa_motor_malha(pb, r_p, z_p0 - zc, z_mot0 - zc, s_m - braco, info_m["w_e"] + 0.0, ang)
            v, f, t = parte
            _reestilizar_malha(ctx, g, f"m_est_suporte_motor_{k}", (v * MM, f, t), mt.mat["alu_vermelho"],
                               "suporte_motor", k)
        if s_r > 0.0:
            u = np.array([math.cos(ang), math.sin(ang)])
            nlado = np.array([-u[1], u[0]])
            for lado in (-1, 1):
                pinos[(k, lado)] = u * s_r + nlado * lado * (r_t + 3.0 + 9.0)
    # varões de travamento (`trelica_estab_*`, os mesmos nomes): carbono Ø8 entre os garfos das abraçadeiras vizinhas
    pares = ((0, 2), (2, 1), (1, 3), (3, 0))
    for idx, (ia, ib) in enumerate(pares, start=1):
        g = ctx.geom_existente(f"trelica_estab_{idx}")
        if g is None:
            continue
        if s_r <= 0.0:
            _ocultar_visual(g)
            continue
        ka, kb = ia + 1, ib + 1
        pa = min((pinos[(ka, s)] for s in (-1, 1)), key=lambda q: np.linalg.norm(q - pinos[(kb, 1)]) +
                 np.linalg.norm(q - pinos[(kb, -1)]))
        pb_ = min((pinos[(kb, s)] for s in (-1, 1)), key=lambda q: np.linalg.norm(q - pa))
        da = pb_ - pa
        fa = _ponta_trelica(mt, pa, da, z_t, idx)
        fb = _ponta_trelica(mt, pb_, -da, z_t, idx)
        g.fromto = list(ctx.p(*(fa * MM))) + list(ctx.p(*(fb * MM)))
        g.size = [0.004, 0.0, 0.0]
        g.material = mt.mat["carbono_liso"]
        ctx.registar_geom(g.name, "trelica", idx)


def _frame_corrida(mt: _Montador, hw, esp: float, L: float, pb: dict, r_p: float):
    """Frame de corrida de 5″: braços em placa de carbono de 3,5 mm por cima da placa de baixo, presos por 2 × M3 com
    porca, e o motor aparafusado direto ao braço (a furação de `motores.padrao_base`), com uma chapa de reforço de
    0,5 mm por baixo da ponta (onde assentam as cabeças dos M3 do motor); os parafusos dos outros módulos que
    atravessam as raízes dos braços (o ESC 4-em-1) passam em furos."""
    ctx = mt.ctx
    braco = hw.braco / MM
    o = mt.origem_m("drone") / MM
    g_mot = ctx.geom_existente("motor1")
    z1 = float(g_mot.pos[2]) / MM - o[2] - float(g_mot.size[1]) / MM if g_mot is not None else esp + 3.5
    # os parafusos verticais dos OUTROS módulos que atravessam a laje dos braços (o ESC 4-em-1 aparafusa através das
    # raízes dos braços): furam o braço onde passam
    alheios = _furos_parafusos(ctx, mt, "drone", esp, z1)
    for i, (x, y) in enumerate(hw.pos_rotores):
        k = i + 1
        ang = math.atan2(y, x)
        R = _rot_z(ang)
        r_t = 14.0
        perfil = [(0.3 * L, -11.0), (braco - 6.0, -11.0)]
        for a in np.linspace(-0.5 * math.pi, 0.5 * math.pi, 15):
            perfil.append((braco + r_t * math.cos(a) * 1.0, r_t * math.sin(a)))
        perfil += [(braco - 6.0, 11.0), (0.3 * L, 11.0)]
        perfil = [(x_, max(-11.0, min(11.0, y_)) if x_ < braco - 6.0 else y_) for x_, y_ in perfil]
        furos = [_circulo(braco + fx, fy, 0.5 * FURO_PASSANTE.get(pb.get("rosca", "M3"), 3.4), 12) for fx, fy in pb["furos_mm"]]
        furos.append(_circulo(braco, 0.0, 0.5 * float(pb.get("furo_central_mm", 9.0)), 20))
        furos_b = [_circulo(s, 0.0, 0.5 * FURO_PASSANTE["M3"], 12) for s in (0.7 * L, 0.85 * L)]
        perfil = tuple((round(a, 5), round(b, 5)) for a, b in perfil)
        nossos = [(braco + fx, fy) for fx, fy in pb["furos_mm"]] + [(braco, 0.0), (0.7 * L, 0.0), (0.85 * L, 0.0)]
        ca, sa = math.cos(ang), math.sin(ang)
        for xg, yg, rg in alheios:
            s_, n_ = ca * xg + sa * yg, -sa * xg + ca * yg
            if _no_poligono(s_, n_, perfil) and all(math.hypot(s_ - a, n_ - b) > 1.0 for a, b in nossos):
                furos_b.append(_circulo(round(s_, 4), round(n_, 4), rg, 12))
        mt.juntar("drone", "carbono", _ext(perfil, tuple(furos + furos_b), esp, z1), "tubo_braco", k, R)
        col = ctx.ferragens
        for s in (0.7 * L, 0.85 * L):
            p = R @ np.array([s, 0.0, z1])
            if col is not None:
                reg = col.parafuso("drone", mt.ponto_m("drone", p), (0, 0, -1), "M3", aperto=z1 + esp,
                                   porca="ISO 10511", peca="tubo_braco", inst=k)
                mt.ferragens.append(("drone", p, np.array([0.0, 0.0, -1.0]), reg))
        g = ctx.geom_existente(f"suporte_motor_{k}")
        if g is not None:
            # num 5″ o motor aparafusa direto ao braço; o `motores` assenta as cabeças dos M3 no fundo do cilindro
            # `suporte_motor_k` (0,5 mm abaixo do braço): uma CHAPA DE REFORÇO de carbono na ponta do braço, por
            # baixo (a forma da ponta, com os furos do motor), fecha esse espaço e as cabeças assentam nela
            z_sup0 = float(g.pos[2]) / MM - o[2] - float(g.size[1]) / MM
            _ocultar_visual(g)
            if 0.05 < esp - z_sup0 <= 2.0:
                ponta = [(braco - 6.0, -11.0)] + [p_ for p_ in perfil if p_[0] >= braco - 1e-6] + [(braco - 6.0, 11.0)]
                mt.juntar("drone", "carbono", _ext(tuple(ponta), tuple(furos), round(z_sup0, 4), esp), "suporte_motor",
                          k, R)
        perna = _dados_perna(mt, "drone", f"perna{k}")
        if perna is not None:
            ctx.esconder(f"perna{k}")
            s_leg, z_f = perna
            mt.juntar("drone", "borracha", _torno((((0.0, z_f), (5.0, z_f + 0.3)), ((5.0, z_f + 0.3), (7.5, z_f + 3.0),
                                                                                   (7.5, -esp - 0.0)),
                                                   ((7.5, -esp), (0.0, -esp))), 20), "perna", k, R,
                      R @ np.array([s_leg, 0.0, 0.0]))
    for idx in range(1, 5):
        g = ctx.geom_existente(f"trelica_estab_{idx}")
        if g is not None:
            _ocultar_visual(g)


# ===================================================================================================== mecanismo
def _mecanismo(mt: _Montador, hw, esp: float, zs0: float, zs1: float):
    ctx = mt.ctx
    from ..modelo import geometria_bracos
    geo = geometria_bracos(hw)
    r_s, l1 = geo["r_s"] / MM, geo["l1"] / MM
    r_t = round((_tubo_do_frame(hw) or 0.0125) / MM, 4)
    pb = _padrao_motor(hw)
    d_mot = float(hw.motor.dados.get("diametro_mm", 28.0))
    r_p = round(0.5 * d_mot + 1.5, 4)
    rosca_m = pb.get("rosca", "M3")
    r_cab = 0.5 * fer.ISO4762.get(rosca_m, fer.ISO4762["M3"])[0]
    r_furo_min = min((math.hypot(x, y) for x, y in pb["furos_mm"]), default=r_p)
    r_neck = round(max(5.0, min(12.0, r_furo_min - r_cab - 0.5)), 4)
    furos_extra = []
    for i, (x, y) in enumerate(hw.pos_rotores):
        k = i + 1
        ang = math.atan2(y, x)
        ux, uy = math.cos(ang), math.sin(ang)
        sx, sy = math.copysign(1.0, ux), math.copysign(1.0, uy)
        M = np.diag([sx, sy, 1.0])
        mao = 1 if sx * sy > 0 else -1      # o espelho troca a mão do filete: assim o sem-fim fica sempre à direita
        P = np.array([r_s * ux, r_s * uy, 0.0])
        conj, furos_c = _ombro_canonico(round(zs0, 4), round(zs1, 4), round(esp, 4), mao, r_t)
        mt.colocar(conj, {"fixo": "drone", "movel": f"braco{k}", "rotor": ("drone", f"semfim{k}_rotor")}, M,
                   {"fixo": P, "rotor": P}, inst=k)
        for etq, (fx, fy), r, placa in furos_c:
            q = M @ np.array([fx, fy, 0.0]) + P
            furos_extra.append(((float(q[0]), float(q[1])), r, placa))
        # o sem-fim: eixo vertical a ENTRE mm do veio; sentido = sinal da rotação do sem-fim (em torno de +z) quando o
        # ombro roda +q (em torno de +y): sem-fim de rosca direita do lado −x da coroa → −1; do lado +x → +1
        p_w = M @ np.array([A_W, B_C, 0.0]) + P
        ctx.eixo(f"semfim{k}", "drone", list(mt.ponto_m("drone", p_w)), [0.0, 0.0, 1.0], "sem-fim", junta=f"ombro{k}",
                 razao=float(hw.bracos.ombro.reducao), sentido=-sx)
        gs = ctx.geom_existente(f"suporte_motor_{k}")
        z_sup_c = float(gs.pos[2]) / MM if gs is not None else (geo["l_m"] / MM - 40.0)
        z_p0 = round(z_sup_c - float(gs.size[1]) / MM, 4) if gs is not None else round(z_sup_c - 2.5, 4)
        z_mot0 = round(z_sup_c + float(gs.size[1]) / MM, 4) if gs is not None else z_p0 + 5.0
        mt.colocar(_cotovelo_canonico(z_p0, r_neck, r_t), {"braco": f"braco{k}", "mastro": f"mastro{k}"}, M,
                   {"braco": l1 * np.array([ux, uy, 0.0])}, inst=k)
        u = np.array([ux, uy, 0.0])
        cj = _Conj()
        _tubo(cj, "b", u, 16.0, l1 - 60.0, r_t, "tubo_braco")
        mt.colocar(cj.congelar(), {"b": f"braco{k}"}, None, {}, inst=k)
        if gs is not None:
            parte = _placa_motor_malha(pb, r_p, z_p0 - z_sup_c, z_mot0 - z_sup_c, None, 0.0, ang)
            v, f, t = parte
            _reestilizar_malha(ctx, gs, f"m_est_suporte_motor_{k}", (v * MM, f, t), mt.mat["alu_vermelho"],
                               "suporte_motor", k)
        perna = _dados_perna(mt, f"braco{k}", f"perna{k}")
        if perna is not None:
            mt.colocar(_perna_canonica(perna[0], 0.0, r_t, perna[1]), {"p": f"braco{k}"}, _rot_z(ang), {}, inst=k)
            ctx.esconder(f"perna{k}")
        for nome in (f"braco{k}_raiz", f"braco{k}_tubo", f"servo_ombro{k}", f"sem_fim{k}", f"servo_cotovelo{k}",
                     f"mastro{k}_tubo"):
            if ctx.geom_existente(nome) is not None:
                ctx.esconder(nome)
        antigos = [f"dobradica_ombro{k}", f"dobradica_cotovelo{k}", f"garfo_cotovelo{k}", f"sem_fim{k}_eixo"]
        antigos += [f"{t}_{j}{k}_{s}" for t in ("corneta", "marca") for j in ("ombro", "cotovelo") for s in ("a", "b")]
        for nome in antigos:
            if ctx.geom_existente(nome) is not None:
                ctx.apagar(nome)
    return furos_extra


# ===================================================================================================== ACESSÍVEL (ABS)
# Build `articulado_15pol_abs` (mecanismo `ombro_fuso_impresso_cotovelo_servo`, frame `diy_tubo_carbono_1950_abs`):
# peças de catálogo baratas + peças IMPRESSAS em ABS. Cada peça impressa é feita de LAJES extrudidas que só se TOCAM
# (malhas fechadas, normais para fora): o volume pela divergência é o volume da peça (registado em
# `notas["impressas"]`). Ver o docstring do módulo (secção ACESSÍVEL).
MECANISMOS_ABS = ("ombro_fuso_impresso_cotovelo_servo", "ombro_semfim_impresso_cotovelo_servo")
# geometria do atuador linear do ombro (braço do quadrante +x, +y; mm, relativa ao eixo H do ombro, junta a 0) — é a
# do catálogo (`mecanismos_braco.<id>.ombro.fuso`); estes valores de reserva são os mesmos que se publicaram
FUSO_PADRAO = {"alavanca_mm": [-50.0, 24.0, 0.0], "base_mm": [-38.1, 24.0, 75.1], "comprimento_fuso_mm": 150.0}
# motorredutor JGB37-520 12 V 1:18,8 com encoder (fichas; o desvio do veio e o círculo dos furos são estimados)
JGB = {"d_red": 37.0, "l_red": 21.0, "d_face": 31.0, "d_mot": 33.0, "l_mot": 22.7, "l_enc": 9.0, "d_veio": 6.0,
       "l_veio": 15.0, "exc": 7.0, "pcd": 25.0, "d_ress": 12.0, "h_ress": 4.0}
PORCA_TR8 = {"d_flange": 22.0, "e_flange": 3.5, "d_corpo": 10.2, "l": 15.0, "pcd": 16.0}
ACOPL = {"d": 19.0, "l": 25.0}
R608 = (4.0, 11.0, 7.0)
RMR85 = (2.5, 4.0, 2.5)                                  # MR85ZZ 5 × 8 × 2,5 (raios interior/exterior, largura)
TR8 = {"d": 8.0, "d3": 5.5, "passo": 2.0}
# atuador (s ao longo de B → longe de A, origem em B)
S_BLOCO = 14.0                    # o bloco dos 608 vai de −14 a 14 (rolamentos nas pontas, munhões a meio)
S_COLAR = 8.0
S_ACOPL0 = S_BLOCO + S_COLAR + 0.5
S_FACE = S_ACOPL0 + ACOPL["l"] + JGB["h_ress"] + 0.5     # face do redutor
MEIA_Y_ATUADOR = 12.0             # meia largura (em y) do bloco, da campânula e do carro da porca


def _circulo_achatado(r: float, ymax: float, n: int = 40):
    """Círculo de raio r com as faces |y| ≤ ymax planas (anti-horário)."""
    if ymax >= r:
        return _circulo(0.0, 0.0, r, n)
    t = math.asin(ymax / r)
    m = max(4, int(n * (math.pi - 2.0 * t) / _TAU) + 2)
    pts = _arco(0.0, 0.0, r, -t, t, m) + _arco(0.0, 0.0, r, math.pi - t, math.pi + t, m)
    return _poli(pts)


def _setor_anel(r_in: float, r_out: float, x_min: float, ymax: float, n: int = 16):
    """A parte do anel r_in…r_out que fica em x ≥ x_min e |y| ≤ ymax (anti-horário)."""
    a_o = min(math.acos(min(1.0, x_min / r_out)), math.asin(min(1.0, ymax / r_out)))
    a_i = math.acos(min(1.0, x_min / r_in))
    xo, yo = r_out * math.cos(a_o), r_out * math.sin(a_o)
    pts = _arco(0.0, 0.0, r_out, -a_o, a_o, n)
    if xo - x_min > 1e-6:
        pts.append((x_min, yo))
    pts += _arco(0.0, 0.0, r_in, a_i, -a_i, n)
    if xo - x_min > 1e-6:
        pts.append((x_min, -yo))
    return _poli(pts)


def _perfil_furos_laterais(hx: float, hy: float, meio_x: float, prof: float):
    """Retângulo ±hx × ±hy com 2 entalhes (|x| ≤ meio_x, profundidade `prof` a partir das faces ±y): os furos laterais
    dos insertos M4 dos pivôs numa peça extrudida ao longo do eixo do fuso (anti-horário)."""
    y_in = hy - prof
    pts = [(-hx, -hy), (-meio_x, -hy), (-meio_x, -y_in), (meio_x, -y_in), (meio_x, -hy), (hx, -hy), (hx, hy),
           (meio_x, hy), (meio_x, y_in), (-meio_x, y_in), (-meio_x, hy), (-hx, hy)]
    return _poli(pts)


def _e_mecanismo_abs(hw) -> bool:
    b = getattr(hw, "bracos", None)
    return b is not None and str(getattr(b, "id", "")) in MECANISMOS_ABS


def _e_frame_abs(hw) -> bool:
    return str(getattr(hw.frame, "id", "")).endswith("_abs")


def _fuso_do_hw(hw) -> dict:
    d = dict(FUSO_PADRAO)
    try:
        d.update({k: v for k, v in (((hw.bracos.dados or {}).get("ombro") or {}).get("fuso") or {}).items()
                  if k in FUSO_PADRAO})
    except AttributeError:
        pass
    return d


def _arco(cx, cy, r, a0, a1, n):
    """n + 1 pontos de um arco (ângulos em rad, de a0 a a1, inclusive)."""
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def _poli(pts):
    out = []
    for x, y in pts:
        p = (round(float(x), 5), round(float(y), 5))
        if not out or abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > 1e-5:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) + abs(out[0][1] - out[-1][1]) <= 1e-5:
        out.pop()
    return tuple(out)


def _ext_y(perfil_xz, furos_xz, y0, y1):
    """Laje ao longo de +y com o perfil no plano (x, z) — já no referencial do conjunto (faces para fora)."""
    v, f, t = _ext(perfil_xz, furos_xz, y0, y1)
    return v[:, [0, 2, 1]], f[:, ::-1], t


def _d_perfil(r: float, x_tras: float, z_cima: float, z_baixo: float | None = None, n: int = 28):
    """Perfil em «D» (plano xz) à volta de um eixo em y na origem: meia-volta de raio r do lado +x, reto até x_tras,
    cortado em z ≤ z_cima (anti-horário)."""
    zb = -r if z_baixo is None else z_baixo
    a0 = -0.5 * math.pi if zb <= -r else math.asin(max(-1.0, zb / r))
    a1 = 0.5 * math.pi if z_cima >= r else math.asin(z_cima / r)
    pts = [(x_tras, zb)] + _arco(0.0, 0.0, r, a0, a1, n) + [(x_tras, r * math.sin(a1))]
    return _poli(pts)


def _quat_mesa(normal_mesa) -> list:
    """Rotação do corpo para a posição de impressão: leva a normal (para fora) da face de apoio a −z."""
    n = _unit(normal_mesa)
    alvo = np.array([0.0, 0.0, -1.0])
    c = float(n @ alvo)
    if c > 1.0 - 1e-9:
        return [1.0, 0.0, 0.0, 0.0]
    if c < -1.0 + 1e-9:
        return [0.0, 1.0, 0.0, 0.0]
    eixo = np.cross(n, alvo)
    eixo = eixo / np.linalg.norm(eixo)
    a = math.acos(c)
    return [round(math.cos(0.5 * a), 6)] + [round(float(x), 6) for x in eixo * math.sin(0.5 * a)]


def _volume_malha(v, f) -> float:
    t = np.asarray(v, float)[np.asarray(f, np.int64)]
    return float(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6.0)


def _inserto(cj, etq, ponto, eixo, rosca, peca, comp=None):
    """Inserto de latão de cravar a quente (M3 × 5,7 Ø4,6 → furo Ø4,0; M2,5 × 4; M4 × 5): `ponto` = a boca do furo,
    `eixo` = para dentro da peça. Desenha-se o casquilho com o Ø do furo (o plástico fecha à volta do serrilhado
    quando se crava) e regista-se para a lista de ferragens."""
    d_ext, l_ = {"M3": (4.0, 5.7), "M2.5": (3.2, 4.0), "M4": (5.6, 5.0)}.get(rosca, (4.0, 5.7))
    l_ = comp or l_
    d_int = {"M3": 2.5, "M2.5": 2.05, "M4": 3.3}.get(rosca, 2.5)
    R = _r_eixo(eixo)
    cj.j(etq, "fer_latao", _anel(0.5 * d_ext - 0.03, 0.5 * d_int, 0.0, l_, 16), R, ponto, peca)
    cj.ferragem("registar", etq, ponto, eixo, peca=peca, tipo_reg="inserto", norma=f"inserto de latão {rosca}",
                rosca=rosca, comp_mm=float(l_), material="fer_latao",
                descricao=f"Inserto de latão {rosca} × {l_:g} mm (cravar a quente no ABS)")


def _impressa(cj, peca, nome, normal_mesa, nota, etq):
    cj.impressas.append({"peca": peca, "nome": nome, "normal": _unit(normal_mesa), "nota": nota, "etq": etq})


@functools.cache
def _rosca_tr(r_raiz: float, r_crista: float, passo: float, z0: float, z1: float, n_volta: int = 14, mao: int = 1):
    """Filete trapezoidal (Tr, 30° entre flancos) de 1 entrada no eixo z, de z0 a z1 (o núcleo de raio r_raiz
    desenha-se à parte); a crista tem 0,366·P; `mao` = +1 direita (no canónico espelhado passa-se −1)."""
    t15 = math.tan(math.radians(15.0))
    w_c = 0.5 * 0.366 * passo
    w_r = w_c + (r_crista - r_raiz) * t15
    sec = [(r_raiz - 0.02, -w_r), (r_crista, -w_c), (r_crista, w_c), (r_raiz - 0.02, w_r)]
    zc0, zc1 = z0 + w_r, z1 - w_r
    K = max(math.ceil((zc1 - zc0) / passo * n_volta), 2)
    V, F = [], []
    for e in range(3):
        base = len(V)
        for k in range(K + 1):
            zc = zc0 + (zc1 - zc0) * k / K
            phi = mao * (zc - z0) * _TAU / passo
            for rr, dz in (sec[e], sec[e + 1]):
                V.append((rr * math.cos(phi), rr * math.sin(phi), zc + dz))
        for k in range(K):
            p0, p1 = base + 2 * k, base + 2 * (k + 1)
            F += [(p0, p1, p1 + 1), (p0, p1 + 1, p0 + 1)]
    caps = []
    for zc_ in (zc0, zc1):
        phi = mao * (zc_ - z0) * _TAU / passo
        b = len(V)
        for rr, dz in sec:
            V.append((rr * math.cos(phi), rr * math.sin(phi), zc_ + dz))
        caps.append(b)
        F += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    V = np.array(V)
    F = np.array(F, dtype=np.int64)
    tri = V[F]
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    cen = tri.mean(axis=1)
    phi = np.arctan2(cen[:, 1], cen[:, 0])
    r_mid = 0.5 * (r_raiz + r_crista)
    # o centro do filete na mesma posição angular: z = z0 + passo·φ/2π (+ k·passo) — o mais perto do centroide
    zf = z0 + mao * np.mod(phi, _TAU) / _TAU * passo
    zf = zf + np.round((cen[:, 2] - zf) / passo) * passo
    dentro = np.column_stack([r_mid * np.cos(phi), r_mid * np.sin(phi), zf])
    trocar = np.einsum("ij,ij->i", nrm, cen - dentro) < 0
    F[trocar] = F[trocar][:, ::-1]
    return V, F, np.zeros((len(V), 2))


def _aperto_fenda_abs(cj, etq, mat, peca, C, U, W, r_in, r_out, u0, u1, us, rosca, meio=5.0, folga=1.0):
    """Abraçadeira de FENDA impressa sem sobreposições (o anel tem os entalhes onde assentam as orelhas): anel
    r_in…r_out à volta do eixo C + U·u (u ∈ [u0, u1]) com a fenda do lado W; 2 orelhas furadas e os parafusos
    perpendiculares ao plano da fenda com porca autoblocante. Devolve w do eixo dos parafusos."""
    U, W = _unit(U), _unit(W)
    W = _unit(W - (W @ U) * U)
    N = np.cross(W, U)
    C = np.asarray(C, float)
    d_f = FURO_PASSANTE[rosca]
    w_t = math.sqrt(max(r_out ** 2 - meio ** 2, 0.0))
    w_e0 = max(w_t, r_in + 0.6)                       # o entalhe das orelhas começa onde o arco de fora corta |n| = meio
    w_s = max(w_e0 + 0.5 * d_f + 1.2, r_out + 0.5 * d_f + 0.6)
    w_e1 = w_s + 0.5 * fer.ISO4762[rosca][0] + 0.8
    a_o = math.atan2(meio, w_t)
    a_i = math.asin(min(0.99, 0.5 * folga / r_in))
    w_i = math.sqrt(r_in ** 2 - (0.5 * folga) ** 2)
    pts = [(w_t, meio)] + _arco(0.0, 0.0, r_out, a_o, _TAU - a_o, 44)[1:]
    pts += [(w_e0, -meio), (w_e0, -0.5 * folga), (w_i, -0.5 * folga)]
    pts += _arco(0.0, 0.0, r_in, _TAU - a_i, a_i, 36)[1:-1]
    pts += [(w_i, 0.5 * folga), (w_e0, 0.5 * folga), (w_e0, meio)]
    cj.j(etq, mat, _ext(_poli(pts), (), u0, u1), _base(W, N, U), C, peca)
    R_or = _base(W, U, np.cross(W, U))                   # z local = W × U = N
    furos = tuple(_circulo(w_s, u, 0.5 * d_f, 14) for u in us)
    perfil = _poli(_ret(w_e0, w_e1, u0, u1))
    for n0, n1 in ((0.5 * folga, meio), (-meio, -0.5 * folga)):
        cj.j(etq, mat, _ext(perfil, furos, n0, n1), R_or, C, peca)
    for u in us:
        cj.parafuso(etq, C + U * u + W * w_s + N * meio, -N, rosca, aperto=2.0 * meio, porca="ISO 10511",
                    anilha_porca=False, peca=peca, ref=U)
    return w_s


def _parafuso_ombro(cj, etq, ponto_face, eixo, comp_ombro, peca, rosca="M4", d_ombro=5.0, l_rosca=6.5, dk=8.0, k=4.0):
    """Parafuso de ombro ISO 7379 (Ø5 × comp, M4): `ponto_face` = a face onde o OMBRO encosta (a da peça onde rosca),
    `eixo` = da cabeça para a rosca. Desenha-se inteiro (cabeça com sextavado, ombro e rosca) e regista-se."""
    R = _r_eixo(eixo)
    p = np.asarray(ponto_face, float)
    e = _unit(eixo)
    p_cab = p - e * comp_ombro                         # face de baixo da cabeça
    perfil = (((0.0, -k), (0.5 * dk - 0.4, -k)), ((0.5 * dk - 0.4, -k), (0.5 * dk, -k + 0.4)),
              ((0.5 * dk, -k + 0.4), (0.5 * dk, 0.0)), ((0.5 * dk, 0.0), (0.5 * d_ombro, 0.0)),
              ((0.5 * d_ombro, 0.0), (0.5 * d_ombro, comp_ombro)), ((0.5 * d_ombro, comp_ombro), (1.7, comp_ombro)),
              ((1.7, comp_ombro), (1.7, comp_ombro + l_rosca)), ((1.7, comp_ombro + l_rosca), (0.0, comp_ombro + l_rosca)))
    cj.j(etq, "aco_preto", _torno(perfil, 20), R, p_cab, peca)
    cj.j(etq, "sextavado", _sext(2.5, -k - 0.02, -k + 0.02), R, p_cab, peca)
    cj.ferragem("registar", etq, p_cab, eixo, peca=peca, tipo_reg="parafuso_ombro", norma="ISO 7379",
                rosca=rosca, comp_mm=float(comp_ombro), material="fer_aco_preto",
                descricao=f"Parafuso de ombro ISO 7379 Ø{d_ombro:g} × {comp_ombro:g} mm ({rosca}) — pivô")


def _pivo_duplo(cj, etq_peca, etq_garfo, centro, ym, peca_peca, peca_garfo, meia=MEIA_Y_ATUADOR, e_garfo=4.5):
    """Pivô ∥ y com 2 parafusos de ombro (um de cada lado): roscam em insertos M4 nas faces ±y da peça do meio
    (largura 2·meia) e o ombro roda num MR85ZZ assente em cada braço do garfo (de |y−ym| = meia+0,5 a meia+0,5+e)."""
    for sy in (-1.0, 1.0):
        face = np.array([centro[0], ym + sy * meia, centro[2]])
        _inserto(cj, etq_peca, face, (0.0, -sy, 0.0), "M4", peca_peca)
        y_b0 = meia + 0.5 + e_garfo - RMR85[2]           # assento do MR85 por fora
        _rolamento(cj, etq_garfo, etq_peca, R_Y if sy > 0 else _r_eixo((0.0, -1.0, 0.0)),
                   np.array([centro[0], ym + sy * y_b0, centro[2]]), RMR85, peca_garfo, peca_peca, n=16)
        # espaçador (Ø6,5 / Ø5) entre a face da peça e o anel interior do rolamento e anilha de 1 mm debaixo da cabeça
        # (o ombro de 6 mm aperta a pilha espaçador + anel interior + anilha; o anel exterior fica livre no garfo)
        R_ = R_Y if sy > 0 else _r_eixo((0.0, -1.0, 0.0))
        cj.j(etq_peca, "aco", _anel(3.25, 2.5, 0.0, y_b0 - meia, 16), R_, face, peca_peca)
        cj.j(etq_peca, "aco", _anel(3.25, 2.5, y_b0 + RMR85[2] - meia, 6.0, 16), R_, face, peca_peca)
        _parafuso_ombro(cj, etq_peca, face, (0.0, -sy, 0.0), 6.0, peca_peca)


def _furos_garfo_mr85(meia=MEIA_Y_ATUADOR, e_garfo=4.5):
    """[(y0, y1, raio do furo)] de um braço do garfo de um pivô (|y − ym|, de dentro para fora)."""
    a = meia + 0.5
    return ((a, a + e_garfo - RMR85[2], 3.5), (a + e_garfo - RMR85[2], a + e_garfo, RMR85[1]))


# ------------------------------------------------------------------------------------------- ombro de fuso
@functools.cache
def _ombro_fuso_canonico(esp: float, zs0: float, zs1: float, r_t: float, ax: float, az: float, bx: float, bz: float,
                         ym: float, l_fuso: float, mao: int = 1) -> tuple:
    """OMBRO ACESSÍVEL do braço 1 (mm, origem H no eixo da junta, y = eixo; junta a 0): DOBRADIÇA (veio Ø8 em 2 × 608ZZ
    numa forquilha impressa aparafusada às 2 placas), CUBO do braço com a ALAVANCA (até ao pivô A), AS5048A, o ATUADOR
    LINEAR (JGB37-520 + acoplamento 6→8 + fuso Tr8×2 num bloco impresso com 2 × 608ZZ; porca de latão num carro
    impresso) e a TORRE impressa do pivô B. Etiquetas: «fixo» (drone), «movel» (braco{k}), «base» / «veio» (drone,
    geoms `ombro{k}_fuso_base_*` / `ombro{k}_fuso_veio_*`) e «porca» (braco{k}, `ombro{k}_fuso_porca_*`)."""
    cj = _Conj()
    F_, M_ = "fixo", "movel"
    h = esp
    A = np.array([ax, ym, az])
    B = np.array([bx, ym, bz])
    # ===================================================================== dobradiça: forquilha (ABS), 2 × 608ZZ
    YB0, YB1 = -14.5, -7.5            # 608ZZ de fora: assento aberto para +y, rebordo por dentro
    YA0, YA1 = -39.5, -32.5           # 608ZZ de dentro: assento aberto para −y, rebordo por dentro
    FB0, FA1 = -16.0, -31.0
    XT = -24.0
    ZC, ZF = zs0, -15.0
    cj.peca = "ombro_forquilha"
    face_b = _d_perfil(15.0, XT, ZC, ZF)
    face_a = _d_perfil(17.5, XT, ZC, ZF)           # a face A leva também os 4 pilares do AS5048A
    furos_ins_a = tuple(_circulo(x, z, 1.6, 12) for x in (-11.5, 11.5) for z in (-8.5, 8.5))
    for y0, y1, r_f, extra, face in ((FB0, YB0, 9.0, (), face_b), (YB0, YB1, R608[1], (), face_b),
                                     (YA0, YA0 + 4.0, R608[1], furos_ins_a, face_a), (YA0 + 4.0, YA1, R608[1], (), face_a),
                                     (YA1, FA1, 9.0, (), face_a)):
        cj.j(F_, "abs_cinza", _ext_y(face, (_circulo(0.0, 0.0, r_f, 40),) + extra, y0, y1))
    furos_topo = ((XT + 4.0, -20.5), (XT + 4.0, -26.5))
    costas = _poli(_ret(XT, XT + 8.0, FA1, FB0))
    cj.j(F_, "abs_cinza", _ext(costas, tuple(_circulo(x, y, 2.0, 14) for x, y in furos_topo), ZC - 6.0, ZC))
    cj.j(F_, "abs_cinza", _ext(costas, (), ZF, ZC - 6.0))
    furos_aba = ((-30.0, -12.5), (-30.0, -34.0))
    cj.j(F_, "abs_cinza", _ext(_poli(_ret(-36.0, XT, YA0, YB1, r=2.0)),
                               tuple(_circulo(x, y, 2.0, 14) for x, y in furos_aba), -h - 6.0, -h))
    for x, y in furos_aba:
        _inserto(cj, F_, (x, y, -h), (0, 0, -1), "M3", "ombro_forquilha")
        cj.parafuso(F_, (x, y, h), (0, 0, -1), "M3", aperto=2.0 * h, rosca_metida=5.0, peca="ombro_forquilha")
    for x, y in furos_topo:
        _inserto(cj, F_, (x, y, ZC), (0, 0, -1), "M3", "ombro_forquilha")
        cj.parafuso(F_, (x, y, zs1), (0, 0, -1), "M3", aperto=zs1 - zs0, rosca_metida=5.0, peca="ombro_forquilha")
    _impressa(cj, "ombro_forquilha", "Forquilha da dobradiça do ombro (ABS)", (1, 0, 0),
              "Imprime-se pousada pela frente (+x, a face dos D): os assentos dos 608ZZ ficam na vertical; 4 insertos "
              "M3 (2 na aba de baixo, 2 no topo) e 4 M2,5 (pilares do AS5048A).", F_)
    for y0 in (YB0, YA0):
        _rolamento(cj, F_, M_, R_Y, np.array([0.0, y0, 0.0]), R608, "ombro_forquilha", "ombro_veio")
    cj.eixo(F_, "ombro{k}_rolamento_fora", (0.0, 0.5 * (YB0 + YB1), 0.0), (0, 1, 0), "rolamento 608ZZ",
            junta="ombro{k}")
    cj.eixo(F_, "ombro{k}_rolamento_dentro", (0.0, 0.5 * (YA0 + YA1), 0.0), (0, 1, 0), "rolamento 608ZZ",
            junta="ombro{k}")
    # veio Ø8 h8 + colar Ø16 × 8 (do lado do encoder) + espaçador (do lado do cubo) + íman diametral Ø6 × 2,5
    cj.peca = "ombro_veio"
    Y_VE0, Y_VE1 = -49.5, 10.0
    cj.j(M_, "aco", _cil(4.0, Y_VE0, Y_VE1, 28), R_Y)
    cj.j(M_, "aco", _anel(6.0, 4.0, YB1, YB1 + 1.5, 28), R_Y)
    cj.j(M_, "aco_preto", _anel(8.0, 4.0, YA0 - 8.0, YA0, 32), R_Y)
    cj.ferragem("perno", M_, (0.0, YA0 - 4.0, 8.0), (0, 0, -1), rosca="M4", comp=4.0, peca="ombro_veio")
    cj.j(M_, "iman", _cil(3.0, Y_VE0 - 2.5, Y_VE0, 20), R_Y)
    cj.eixo(M_, "ombro{k}_veio", (0.0, -20.0, 0.0), (0, 1, 0), "veio Ø8 da dobradiça", junta="ombro{k}")
    # AS5048A (fixo) em 4 pilares M2,5 × 15 macho-fêmea roscados em insertos na face A
    cj.peca = "ombro_encoder"
    y_p1 = YA0 - 15.0
    y_p0 = y_p1 - 1.6
    furos_pcb = tuple((x, z) for x in (-11.5, 11.5) for z in (-8.5, 8.5))
    cj.j(F_, "pcb", _ext_y(_ret(-14.0, 14.0, -11.0, 11.0, r=1.2), tuple(_circulo(x, z, 1.3, 12) for x, z in furos_pcb),
                           y_p0, y_p1))
    cj.j(F_, "chip", _caixa(-2.5, 2.5, y_p1, y_p1 + 1.0, -2.2, 2.2))
    for i in range(6):
        x = -6.35 + 2.54 * i
        cj.j(F_, "ouro", _caixa(x - 0.32, x + 0.32, y_p0 - 8.0, y_p0 - 2.5, -10.32, -9.68))
    cj.j(F_, "chip", _caixa(-7.62, 7.62, y_p0 - 2.5, y_p0, -11.27, -8.73))
    for x, z in furos_pcb:
        cj.ferragem("pilar", F_, (x, y_p1, z), (0, 1, 0), rosca="M2.5", comp=15.0, tipo="sextavado", af=5.0,
                    macho=4.0, material_="latao", peca="ombro_encoder")
        _inserto(cj, F_, (x, YA0, z), (0, 1, 0), "M2.5", "ombro_forquilha")
        cj.parafuso(F_, (x, y_p0, z), (0, 1, 0), "M2.5", aperto=1.6, rosca_metida=3.0, peca="ombro_encoder")
    cj.ancora(F_, "servo_ombro{k}_ficha_b", (0.0, y_p0 - 8.0, -10.0), (0, -1, 0))
    # ===================================================================== cubo do braço + alavanca (ABS laranja)
    cj.peca = "ombro_cubo"
    Y_CU0, Y_CU1 = YB1 + 1.5, Y_VE1
    W = _unit((-1.0, 0.0, -1.0))
    _aperto_fenda_abs(cj, M_, "abs_laranja", "ombro_cubo", (0.0, 0.0, 0.0), (0, 1, 0), W, 4.0, 12.0, Y_CU0, Y_CU1,
                      (Y_CU0 + 6.0,), "M3", meio=5.0)
    u45 = np.array([math.sqrt(0.5), math.sqrt(0.5), 0.0])
    t0, t1 = 24.0, 56.0
    _aperto_fenda_abs(cj, M_, "abs_laranja", "ombro_cubo", (0.0, 0.0, 0.0), u45, (0.0, 0.0, -1.0), r_t, r_t + 3.5,
                      t0, t1, (32.0, 48.0), "M4", meio=6.0)
    # alma horizontal (z ∈ [−4, 4]) do aperto do veio ao casquilho: a face em t = 24 fecha o casquilho (o tubo encosta)
    q_ = 0.7071067811865476
    alma = _poli([(11.4, Y_CU0), (q_ * (t0 + r_t + 3.5), q_ * (t0 - r_t - 3.5)),
                  (q_ * (t0 - r_t - 3.5), q_ * (t0 + r_t + 3.5)), (11.4, Y_CU1)])
    cj.j(M_, "abs_laranja", _ext(alma, (), -4.0, 4.0))
    # alavanca: 2 braços (|y − ym| ∈ [12,5; 17]) do veio ao pivô A, unidos por uma alma junto ao veio
    e = math.hypot(ax, az)
    th = math.atan2(az, ax)
    braco = _alavanca_perfil(e, th, 7.0, 8.0)
    for sy in (-1.0, 1.0):
        for a0, a1, r_f in _furos_garfo_mr85():
            y0, y1 = sorted((ym + sy * a0, ym + sy * a1))
            cj.j(M_, "abs_laranja", _ext_y(braco, (_circulo(ax, az, r_f, 20),), y0, y1))
    raiz = _poli(_ret(-20.0, -11.0, -6.0, 6.0))
    cj.j(M_, "abs_laranja", _ext_y(raiz, (), ym - 12.5, ym + 12.5))
    _impressa(cj, "ombro_cubo", "Cubo do braço com a alavanca (ABS laranja)", (0, 0, -1),
              "Imprime-se pousado pela alma de baixo (z = −4), com suportes debaixo do casquilho do tubo e dos braços "
              "da alavanca; aperto por fenda no veio (M3 + porca) e no tubo Ø25 (2 × M4 + porca); 2 × MR85ZZ no pivô A.",
              M_)
    # passagem dos cabos do braço: no eixo, 9 mm por fora do braço de fora da alavanca (medido em todo o curso ±40°:
    # ≥ 13 mm ao braço e ≥ 40 mm ao drone; por cima, a z = +10…+30, ≥ 9,7 mm; e a z = +30 para dentro, ≥ 7 mm)
    cj.ancora(F_, "ombro{k}_eixo_cabos", (0.0, ym + 26.0, 0.0), (0.0, 1.0, 0.0),
              nota="no eixo do ombro, 9 mm por fora do braço de fora da alavanca; corredor medido em todo o curso: do "
                   "lado do drone sobe na vertical até ~30 mm acima do eixo e corre para dentro a essa altura (folga "
                   "≥ 7 mm às alavancas e ao cubo); do lado do braço vai direto ao tubo (≥ 40 mm ao drone)")
    # ===================================================================== atuador linear (no plano y = ym)
    _atuador_fuso(cj, A, B, l_fuso, ym, mao)
    _torre_b(cj, B, ym, zs0, zs1)
    return cj.congelar(), ()


def _alavanca_perfil(e: float, th: float, meia: float, r_olho: float):
    """Perfil (xz) de um braço da alavanca: do veio (r = 10) até ao olho do pivô A (raio r_olho), largura 2·meia."""
    ux, uz = math.cos(th), math.sin(th)
    nx, nz = -uz, ux
    p0 = (10.0 * ux, 10.0 * uz)
    ang0 = math.atan2(nz, nx)
    pts = [(p0[0] + nx * meia, p0[1] + nz * meia)]
    pts += _arco(e * ux, e * uz, r_olho, ang0, ang0 - math.pi, 20)      # o olho dá a volta pelo lado de LÁ de A (+u)
    pts += [(p0[0] - nx * meia, p0[1] - nz * meia)]
    return _poli(pts)


def _atuador_fuso(cj, A, B, l_fuso: float, ym: float, mao: int = 1):
    """Motorredutor + acoplamento + fuso Tr8×2 num bloco impresso com 2 × 608ZZ (pivô B: 2 parafusos de ombro nos
    lados ±y) e a porca de latão num carro impresso (pivô A, igual). s ao longo de ê = (B − A)/|B − A| a partir de B,
    x_a no plano do mecanismo (para o lado do eixo do ombro), y_a = y."""
    BA, VE, PO = "base", "veio", "porca"
    ez = _unit(B - A)
    ey = np.array([0.0, 1.0, 0.0])
    ex = np.cross(ey, ez)
    if float(ex @ (-B)) < 0:
        ex = -ex
    Rb = _base(ex, np.cross(ez, ex), ez)
    my = MEIA_Y_ATUADOR
    # --- bloco dos 608 + campânula do motor (ABS, gira com o atuador em torno de B)
    cj.peca = "ombro_bloco"
    perfil_b = _poli(_ret(-14.0, 14.0, -my, my, r=2.0))
    for s0, s1, r_f in ((-S_BLOCO, -S_BLOCO + 7.0, R608[1]), (-S_BLOCO + 7.0, -2.8, 6.5), (2.8, S_BLOCO - 7.0, 6.5),
                        (S_BLOCO - 7.0, S_BLOCO, R608[1])):
        cj.j(BA, "abs_cinza", _ext(perfil_b, (_circulo(0.0, 0.0, r_f, 36),), s0, s1), Rb, B)
    cj.j(BA, "abs_cinza", _ext(_perfil_furos_laterais(14.0, my, 2.8, 5.0), (_circulo(0.0, 0.0, 6.5, 36),), -2.8, 2.8),
         Rb, B)
    for s0 in (-S_BLOCO, S_BLOCO - 7.0):
        _rolamento(cj, BA, VE, Rb, B + ez * s0, R608, "ombro_bloco", "ombro_fuso")
    # campânula (r 13 com as faces ±y planas a ±12): de s = 14 ao prato do motor, com 2 janelas nas faces ±y (por
    # onde se apertam os pernos do acoplamento)
    fora = _circulo_achatado(13.0, my, 40)
    dentro = _circulo(0.0, 0.0, 10.5, 32)
    s_p0 = S_FACE - 3.0
    s_j0, s_j1 = S_ACOPL0 + 2.0, S_ACOPL0 + ACOPL["l"] - 2.0
    cj.j(BA, "abs_cinza", _ext(fora, (dentro,), S_BLOCO, s_j0), Rb, B)
    for sinal in (1.0, -1.0):
        R_m = Rb if sinal > 0 else Rb @ np.diag([-1.0, -1.0, 1.0])
        cj.j(BA, "abs_cinza", _ext(_setor_anel(10.5, 13.0, 5.0, my), (), s_j0, s_j1), R_m, B)
    cj.j(BA, "abs_cinza", _ext(fora, (dentro,), s_j1, s_p0), Rb, B)
    exc = JGB["exc"]
    # 3 × M3 na face do redutor (P.C.D. 25 à volta do eixo do MOTOR) do lado oposto ao veio de saída (0°, ±60°): as
    # cabeças ficam por fora da campânula (r ≥ 17 do eixo do fuso) e longe do ressalto do veio
    ang_m = (0.0, math.radians(60.0), math.radians(-60.0))
    furos_m = tuple(_circulo(exc + 0.5 * JGB["pcd"] * math.cos(a), 0.5 * JGB["pcd"] * math.sin(a), 1.7, 12) for a in ang_m)
    prato = _circulo(exc, 0.0, 0.5 * JGB["d_face"], 48)
    cj.j(BA, "abs_cinza", _ext(prato, (_circulo(0.0, 0.0, 0.5 * JGB["d_ress"] + 0.4, 28),) + furos_m, s_p0, S_FACE),
         Rb, B)
    for a in ang_m:
        p = B + Rb @ np.array([exc + 0.5 * JGB["pcd"] * math.cos(a), 0.5 * JGB["pcd"] * math.sin(a), s_p0])
        cj.parafuso(BA, p, ez, "M3", aperto=3.0, rosca_metida=3.0, cabeca="ISO 7380", peca="ombro_bloco")
    _pivo_duplo(cj, BA, "fixo", B, B[1], "ombro_bloco", "ombro_suporte")
    cj.eixo(BA, "ombro{k}_pivo_b", B, (0, 1, 0), "pivô B do atuador (2 × ISO 7379 Ø5 em MR85ZZ)")
    _impressa(cj, "ombro_bloco", "Bloco do fuso com a campânula do motor (ABS)", ez,
              "Imprime-se de pé sobre o prato do motor: os assentos dos 608ZZ na vertical, sem suportes; 3 parafusos "
              "M3 do motor por dentro da campânula; 2 insertos M4 nos lados (os parafusos de ombro do pivô B).", BA)
    # --- motorredutor JGB37-520 (veio de saída excêntrico de `exc`; peças fixas do corpo do atuador)
    cj.peca = "ombro_motor"
    d_r, l_r, d_m, l_m, l_e = JGB["d_red"], JGB["l_red"], JGB["d_mot"], JGB["l_mot"], JGB["l_enc"]
    pm = B + Rb @ np.array([exc, 0.0, 0.0])
    s_f = S_FACE
    # face do redutor com os 3 furos roscados M3 (Ø 2,5, 4 mm de fundo) onde entram os parafusos do prato
    furos_r = tuple(_circulo(0.5 * JGB["pcd"] * math.cos(a), 0.5 * JGB["pcd"] * math.sin(a), 1.25, 12) for a in ang_m)
    cj.j(BA, "alu_natural", _ext(_circulo(0.0, 0.0, 0.5 * JGB["d_face"], 48), furos_r, s_f, s_f + 1.0), Rb, pm)
    cj.j(BA, "alu_natural", _ext(_circulo(0.0, 0.0, 0.5 * d_r, 48), furos_r, s_f + 1.0, s_f + 4.0), Rb, pm)
    cj.j(BA, "alu_natural", _torno((((0.0, s_f + 4.0), (0.5 * d_r, s_f + 4.0)),
                                    ((0.5 * d_r, s_f + 4.0), (0.5 * d_r, s_f + l_r - 0.6)),
                                    ((0.5 * d_r, s_f + l_r - 0.6), (0.5 * d_r - 0.6, s_f + l_r)),
                                    ((0.5 * d_r - 0.6, s_f + l_r), (0.0, s_f + l_r))), 40), Rb, pm)
    s_m0 = s_f + l_r
    cj.j(BA, "aco", _torno((((0.0, s_m0), (0.5 * d_m, s_m0)), ((0.5 * d_m, s_m0), (0.5 * d_m, s_m0 + l_m)),
                            ((0.5 * d_m, s_m0 + l_m), (0.0, s_m0 + l_m))), 40), Rb, pm)
    s_e0 = s_m0 + l_m
    cj.j(BA, "pcb", _torno((((0.0, s_e0), (0.5 * d_m + 0.5, s_e0)), ((0.5 * d_m + 0.5, s_e0), (0.5 * d_m + 0.5, s_e0 + 1.6)),
                            ((0.5 * d_m + 0.5, s_e0 + 1.6), (0.0, s_e0 + 1.6))), 40), Rb, pm)
    cj.j(BA, "servo_plastico", _torno((((0.0, s_e0 + 1.6), (0.5 * d_m - 0.5, s_e0 + 1.6)),
                                       ((0.5 * d_m - 0.5, s_e0 + 1.6), (0.5 * d_m - 0.5, s_e0 + l_e - 1.0)),
                                       ((0.5 * d_m - 0.5, s_e0 + l_e - 1.0), (0.5 * d_m - 1.5, s_e0 + l_e)),
                                       ((0.5 * d_m - 1.5, s_e0 + l_e), (0.0, s_e0 + l_e))), 40), Rb, pm)
    cj.j(BA, "conector", _caixa(-7.5, 7.5, -0.5 * d_m - 0.5, -0.5 * d_m + 4.5, s_e0 + 1.6, s_e0 + 7.6), Rb, pm)
    cj.ancora(BA, "servo_ombro{k}_ficha_a", pm + Rb @ np.array([0.0, -0.5 * d_m + 2.0, s_e0 + 7.6]), ez,
              grupo="ombro{k}_fuso_base",
              nota="ficha PH2.0 de 6 vias do JGB37-520 (motor ±, encoder VCC/GND/A/B) na tampa do encoder, virada "
                   "para fora do fuso; gira com o atuador em torno do pivô B (0…−9° no curso ±40° do ombro): o cabo "
                   "corre pelo lado de dentro do atuador e faz o laço em `ombro{k}_pivo_b_cabos`")
    cj.ancora("fixo", "ombro{k}_pivo_b_cabos", np.array([B[0], B[1] - 25.0, B[2]]), (0.0, -1.0, 0.0),
              nota="no eixo do pivô B, 3 mm por fora da cabeça do parafuso de ombro (lado de dentro): fixo no drone e "
                   "no corpo do atuador — o laço do cabo do motorredutor passa aqui")
    cj.j(BA, "alu_natural", _cil(0.5 * JGB["d_ress"], s_f - JGB["h_ress"], s_f, 28), Rb, B)
    # --- o que GIRA no eixo do fuso: veio do motor, acoplamento, colares, fuso (geoms `ombro{k}_fuso_veio_*`)
    cj.peca = "ombro_fuso"
    s_vt = s_f - JGB["h_ress"]
    cj.j(VE, "aco", _cil(0.5 * JGB["d_veio"], s_f - JGB["l_veio"], s_vt, 20), Rb, B)
    s_a1 = S_ACOPL0 + ACOPL["l"]
    cj.j(VE, "alu_natural", _cil(0.5 * ACOPL["d"], S_ACOPL0, s_a1, 32), Rb, B)
    for i, s_ in enumerate((S_ACOPL0 + 5.0, s_a1 - 5.0)):
        cj.ferragem("perno", VE, B + Rb @ np.array([0.0, 0.5 * ACOPL["d"], s_]), -Rb[:, 1], rosca="M4", comp=6.0,
                    peca="ombro_fuso")
    for s0, s1 in ((-S_BLOCO - S_COLAR, -S_BLOCO), (S_BLOCO, S_BLOCO + S_COLAR)):
        cj.j(VE, "aco_preto", _anel(8.0, 4.0, s0, s1, 32), Rb, B)
        cj.ferragem("perno", VE, B + Rb @ np.array([0.0, 8.0, 0.5 * (s0 + s1)]), -Rb[:, 1], rosca="M4", comp=4.0,
                    peca="ombro_fuso")
    s_top = S_ACOPL0 + 0.5 * ACOPL["l"] - 2.0
    s_bot = s_top - l_fuso
    cj.j(VE, "aco", _cil(0.5 * TR8["d3"], s_bot, s_top, 18), Rb, B)
    cj.j(VE, "aco", _rosca_tr(0.5 * TR8["d3"], 0.5 * TR8["d"], TR8["passo"], round(s_bot + 0.6, 4),
                              round(-S_BLOCO - S_COLAR - 0.4, 4), 14, mao), Rb, B)
    cj.eixo(BA, "ombro{k}_fuso", B, ez, "fuso Tr8×2 (eixo B → A)")
    # --- porca de latão + carro impresso (no braço, roda em torno de A) — geoms `ombro{k}_fuso_porca_*`
    cj.peca = "ombro_porca"
    e_fl, d_fl = PORCA_TR8["e_flange"], PORCA_TR8["d_flange"]
    s_c0, s_c1 = -11.0, 4.0                          # carro (relativo a A, ao longo de ê)
    perfil_c = _poli(_ret(-14.0, 14.0, -my, my, r=2.0))
    ang_p = tuple(math.radians(45.0 + 90.0 * i) for i in range(4))
    furos_fl = tuple(_circulo(0.5 * PORCA_TR8["pcd"] * math.cos(a), 0.5 * PORCA_TR8["pcd"] * math.sin(a), 2.0, 14)
                     for a in ang_p)
    furo_corpo = _circulo(0.0, 0.0, 0.5 * PORCA_TR8["d_corpo"] + 0.15, 28)
    cj.j(PO, "abs_cinza", _ext(perfil_c, (furo_corpo,), s_c0, -2.8), Rb, A)
    cj.j(PO, "abs_cinza", _ext(_perfil_furos_laterais(14.0, my, 2.8, 5.0), (furo_corpo,), -2.8, 2.8), Rb, A)
    cj.j(PO, "abs_cinza", _ext(perfil_c, (furo_corpo,), 2.8, s_c1 - 5.7), Rb, A)
    cj.j(PO, "abs_cinza", _ext(perfil_c, (furo_corpo,) + furos_fl, s_c1 - 5.7, s_c1), Rb, A)
    s_n0 = s_c1 - (PORCA_TR8["l"] - e_fl)
    cj.j(PO, "ouro", _anel(0.5 * PORCA_TR8["d_corpo"], 0.5 * TR8["d"] - 0.5, s_n0, s_c1, 24), Rb, A)
    fl = _circulo(0.0, 0.0, 0.5 * d_fl, 40)
    furos_fl35 = tuple(_circulo(0.5 * PORCA_TR8["pcd"] * math.cos(a), 0.5 * PORCA_TR8["pcd"] * math.sin(a), 1.75, 12)
                       for a in ang_p)
    cj.j(PO, "ouro", _ext(fl, (_circulo(0.0, 0.0, 0.5 * TR8["d"] - 0.5, 24),) + furos_fl35, s_c1, s_c1 + e_fl), Rb, A)
    for a in ang_p:
        c_ = np.array([0.5 * PORCA_TR8["pcd"] * math.cos(a), 0.5 * PORCA_TR8["pcd"] * math.sin(a), 0.0])
        cj.parafuso(PO, A + Rb @ (c_ + np.array([0.0, 0.0, s_c1 + e_fl])), -ez, "M3", aperto=e_fl, rosca_metida=5.0,
                    peca="ombro_porca")
        _inserto(cj, PO, A + Rb @ (c_ + np.array([0.0, 0.0, s_c1])), -ez, "M3", "ombro_porca")
    _pivo_duplo(cj, PO, "movel", A, A[1], "ombro_porca", "ombro_cubo")
    cj.eixo(PO, "ombro{k}_pivo_a", A, (0, 1, 0), "pivô A da porca (2 × ISO 7379 Ø5 em MR85ZZ)")
    _impressa(cj, "ombro_porca", "Carro da porca do fuso (ABS)", -ez,
              "Imprime-se de pé pela face de baixo; 4 insertos M3 (flange da porca) e 2 M4 (pivô A).", PO)


def _torre_b(cj, B, ym: float, zs0: float, zs1: float):
    """Torre impressa do pivô B: poste na placa de cima (4 × M3 de baixo para cima, em insertos), braço até ao garfo do
    pivô e a ponte por trás do bloco (o bloco roda ±10° em B; a campânula tem as faces ±y planas a ±12)."""
    F_ = "fixo"
    cj.peca = "ombro_suporte"
    bx, bz = float(B[0]), float(B[2])
    x0, x1 = bx - 32.0, bx - 24.0
    z0, z1 = bz - 11.0, bz + 11.0
    face = _poli([(x0, z0), (bx, z0)] + _arco(bx, bz, 11.0, -0.5 * math.pi, 0.5 * math.pi, 16)[1:-1] + [(bx, z1), (x0, z1)])
    for sy in (-1.0, 1.0):
        for a0, a1, r_f in _furos_garfo_mr85():
            y0, y1 = sorted((ym + sy * a0, ym + sy * a1))
            cj.j(F_, "abs_cinza", _ext_y(face, (_circulo(bx, bz, r_f, 20),), y0, y1))
    a_in = _furos_garfo_mr85()[0][0]
    cj.j(F_, "abs_cinza", _caixa(x0, x1, ym - a_in, ym + a_in, z0, z1))
    y_p0, y_p1 = -34.0, -16.0
    y_braco1 = ym - _furos_garfo_mr85()[-1][1]
    cj.j(F_, "abs_cinza", _caixa(x0, x0 + 24.0, y_p1, y_braco1, z0, z1))
    furos = ((x0 + 5.0, y_p0 + 4.5), (x0 + 19.0, y_p0 + 4.5), (x0 + 5.0, y_p1 - 4.5), (x0 + 19.0, y_p1 - 4.5))
    cj.j(F_, "abs_cinza", _ext(_poli(_ret(x0, x0 + 24.0, y_p0, y_p1)), tuple(_circulo(x, y, 2.0, 14) for x, y in furos),
                               zs1, zs1 + 6.0))
    cj.j(F_, "abs_cinza", _caixa(x0, x0 + 24.0, y_p0, y_p1, zs1 + 6.0, z1))
    for x, y in furos:
        _inserto(cj, F_, (x, y, zs1), (0, 0, 1), "M3", "ombro_suporte")
        cj.parafuso(F_, (x, y, zs0), (0, 0, 1), "M3", aperto=zs1 - zs0, rosca_metida=5.0, peca="ombro_suporte")
    _impressa(cj, "ombro_suporte", "Torre do pivô B (ABS)", (0, 0, -1),
              "Imprime-se pela base (a face que assenta na placa de cima); o braço do garfo sai em consola com a ponte "
              "por trás (suportes debaixo do braço); 4 insertos M3 na base e 2 × MR85ZZ.", F_)
    return furos


# ------------------------------------------------------------------------------------------- cotovelo acessível
# DS3218MG (fichas: corpo 40 × 20 × 40,5, orelhas de 54,5 com furos a 49,5 × 10, estriado 25T Ø5,9) — no referencial
# local do servo: x ao longo do comprimento (o estriado a 10 mm da ponta +x), y na largura, z do fundo (−36,5) para
# o topo da caixa (0); estriado e ressalto por cima (até 4).
DS_TOPO_Y = -22.4                 # a face de cima da caixa do servo (no referencial do cotovelo, y = eixo)
DS = {"x0": -30.0, "x1": 10.0, "w": 10.0, "z0": -36.5, "z_or0": -10.0, "z_or1": -7.5, "or_x0": -37.25,
      "or_x1": 17.25, "furo_x": (-34.75, 14.75), "furo_y": (-5.0, 5.0)}
HORN25 = {"r": 10.0, "z0": 1.05, "z1": 6.0, "pcd": 14.0}    # disco 25T de alumínio Ø20 × 5 (pesquisa)
Z_PONTE_ABS = 44.0


def _servo_ds3218(cj, etq_c, etq_h, R, p, peca):
    """Servo DS3218MG (caixa, orelhas com os 4 furos, etiqueta, saída do cabo) e o horn de disco 25T Ø20 × 5 com o
    parafuso central — a caixa no `etq_c` (braço), o horn no `etq_h` (mastro)."""
    x0, x1, w, z0 = DS["x0"], DS["x1"], DS["w"], DS["z0"]
    cj.j(etq_c, "servo_plastico", _caixa(x0, x1, -w, w, z0, DS["z_or0"], r=1.0), R, p, peca)
    furos_or = tuple(_circulo(x, y, 2.25, 14) for x in DS["furo_x"] for y in DS["furo_y"])
    orelha = _poli(_ret(DS["or_x0"], DS["or_x1"], -w, w, r=1.5))
    cj.j(etq_c, "servo_metal", _ext(orelha, furos_or, DS["z_or0"], DS["z_or1"]), R, p, peca)
    cj.j(etq_c, "servo_plastico", _caixa(x0, x1, -w, w, DS["z_or1"], -1.0, r=1.0), R, p, peca)
    cj.j(etq_c, "servo_plastico", _cil(9.5, -1.0, 0.0, 32), R, p, peca)             # tampa redonda das engrenagens
    cj.j(etq_c, "servo_plastico", _caixa(x0 + 1.0, x1 - 11.0, -w + 1.0, w - 1.0, -1.0, 0.0, r=1.0), R, p, peca)
    cj.j(etq_c, "servo_metal", _cil(5.5, 0.0, 1.0, 28), R, p, peca)
    cj.j(etq_c, "etiqueta", _caixa(x0 + 3.0, x1 - 3.0, w, w + 0.15, z0 + 3.0, DS["z_or0"] - 2.0), R, p, peca)
    cj.j(etq_c, "borracha", _caixa(x0 - 1.5, x0, -3.0, 3.0, z0 + 2.0, z0 + 6.0, r=0.8), R, p, peca)
    cj.ancora(etq_c, "servo_cotovelo{k}_ficha_a", p + R @ np.array([x0 - 1.5, 0.0, z0 + 4.0]), R @ np.array([-1.0, 0.0, 0.0]))
    # estriado 25T (no corpo do mastro: gira com o horn) e o horn de disco com 4 furos M3 roscados (P.C.D 14)
    cj.j(etq_h, "aco", _cil(2.95, HORN25["z0"], 4.0, 25), R, p, peca)
    furos_h = tuple(_circulo(0.5 * HORN25["pcd"] * math.cos(a), 0.5 * HORN25["pcd"] * math.sin(a), 1.25, 12)
                    for a in (math.radians(45.0 + 90.0 * i) for i in range(4)))
    disco = _circulo(0.0, 0.0, HORN25["r"], 48)
    cj.j(etq_h, "alu_natural", _ext(disco, (_circulo(0.0, 0.0, 2.95, 25),) + furos_h, HORN25["z0"], 4.0), R, p, peca)
    cj.j(etq_h, "alu_natural", _ext(disco, (_circulo(0.0, 0.0, 3.05, 24),) + furos_h, 4.0, HORN25["z1"]), R, p, peca)
    cj.parafuso(etq_h, p + R @ np.array([0.0, 0.0, 4.0]), -R[:, 2], "M3", aperto=0.1, rosca_metida=6.0, peca=peca)


@functools.cache
def _cotovelo_abs_canonico(r_t: float) -> tuple:
    """COTOVELO ACESSÍVEL do braço 1 (mm, origem no eixo do cotovelo, y = eixo): DS3218MG num BERÇO impresso (a caixa
    entra pelo lado do horn, as orelhas aparafusadas com 4 × M3 em insertos) apertado à ponta do tubo; do outro lado
    o garfo roda num 608ZZ assente no fundo do berço com um parafuso M8 (eixo = eixo do servo) e porca autoblocante;
    AS5600 em 2 colunas do berço, frente ao íman na ponta do M8. Etiquetas «braco» (braco{k}) e «mastro»."""
    cj = _Conj()
    BR, MA = "braco", "mastro"
    R_s = _base((1, 0, 0), (0, 0, 1), (0, -1, 0))
    p_s = np.array([0.0, DS_TOPO_Y, 0.0])
    cj.peca = "cotovelo_servo"
    _servo_ds3218(cj, BR, MA, R_s, p_s, "cotovelo_servo")
    y_or = DS_TOPO_Y - DS["z_or0"]                  # face de baixo das orelhas (= a borda do berço)
    y_fundo = DS_TOPO_Y - DS["z0"]                  # fundo da caixa do servo
    cj.eixo(BR, "cotovelo{k}_servo", (0.0, DS_TOPO_Y, 0.0), (0, 1, 0), "estriado 25T do DS3218MG", junta="cotovelo{k}")
    cj.eixo(MA, "cotovelo{k}_horn", (0.0, DS_TOPO_Y - 3.0, 0.0), (0, 1, 0), "horn de disco 25T", junta="cotovelo{k}")
    # ------------------------------------------------------------------ berço (ABS cinzento, no braço)
    cj.peca = "cotovelo_berco"
    corte = _poli(_ret(DS["x0"] - 0.25, DS["x1"] + 0.25, -DS["w"] - 0.25, DS["w"] + 0.25))
    furos_ins = tuple((x, y) for x in DS["furo_x"] for y in DS["furo_y"])
    borda = _poli(_ret(DS["or_x0"] - 1.25, DS["or_x1"] + 1.25, -13.5, 13.5, r=2.0))
    cj.j(BR, "abs_cinza", _ext_y(borda, (corte,) + tuple(_circulo(x, z, 2.0, 14) for x, z in furos_ins), y_or, y_or + 6.0))
    cj.j(BR, "abs_cinza", _ext_y(borda, (corte,), y_or + 6.0, y_or + 8.0))
    for x, z in furos_ins:
        _inserto(cj, BR, (x, y_or, z), (0, 1, 0), "M3", "cotovelo_berco")
        cj.parafuso(BR, (x, y_or - 2.5, z), (0, 1, 0), "M3", aperto=2.5, rosca_metida=5.0, peca="cotovelo_servo")
    paredes = _poli(_ret(DS["x0"] - 3.5, DS["x1"] + 3.5, -13.5, 13.5, r=2.0))
    # a parede tem um entalhe (|z| ≤ 3,5) por onde sai o passa-cabos de borracha do servo e o cabo (para −x)
    y_pc = DS_TOPO_Y - (DS["z0"] + 6.0) - 0.5          # começo do passa-cabos (y) com 0,5 de folga
    cj.j(BR, "abs_cinza", _ext_y(paredes, (corte,), y_or + 8.0, y_pc))
    X0, X1, Z0, Z1 = DS["x0"] - 3.5, DS["x1"] + 3.5, -13.5, 13.5
    xi0, xi1, zi = DS["x0"] - 0.25, DS["x1"] + 0.25, DS["w"] + 0.25
    parede_c = _poli([(X0, -3.5), (X0, Z0), (X1, Z0), (X1, Z1), (X0, Z1), (X0, 3.5), (xi0, 3.5), (xi0, zi), (xi1, zi),
                      (xi1, -zi), (xi0, -zi), (xi0, -3.5)])
    cj.j(BR, "abs_cinza", _ext_y(parede_c, (), y_pc, y_fundo))
    fundo = _poli(_ret(DS["x0"] - 3.5, DS["x1"] + 3.5, -19.0, 13.5, r=2.0))
    y_ass0 = y_fundo + 5.8                         # assento do 608ZZ (a cabeça do M8 roda na caixa antes dele)
    y_lab = y_ass0 + 7.0
    y_fora = y_lab + 1.0
    cj.j(BR, "abs_cinza", _ext_y(fundo, (_circulo(0.0, 0.0, 8.6, 36),), y_fundo, y_ass0))
    cj.j(BR, "abs_cinza", _ext_y(fundo, (_circulo(0.0, 0.0, R608[1], 40),), y_ass0, y_lab))
    cj.j(BR, "abs_cinza", _ext_y(fundo, (_circulo(0.0, 0.0, 9.0, 36),), y_lab, y_fora))
    _rolamento(cj, BR, MA, R_Y, np.array([0.0, y_ass0, 0.0]), R608, "cotovelo_berco", "cotovelo_garfo")
    cj.eixo(BR, "cotovelo{k}_rolamento", (0.0, y_ass0 + 3.5, 0.0), (0, 1, 0), "rolamento 608ZZ do cotovelo",
            junta="cotovelo{k}")
    # 2 colunas do AS5600 (abaixo do eixo: fora do varrimento do olho do garfo) com insertos M2,5 nas pontas
    y_pcb0 = y_fora + 22.0
    for x in (-6.0, 6.0):
        c = _circulo(x, -15.0, 3.5, 20)
        cj.j(BR, "abs_cinza", _ext_y(c, (), y_fora, y_pcb0 - 4.0))
        cj.j(BR, "abs_cinza", _ext_y(c, (_circulo(x, -15.0, 1.6, 12),), y_pcb0 - 4.0, y_pcb0))
        _inserto(cj, BR, (x, y_pcb0, -15.0), (0, -1, 0), "M2.5", "cotovelo_berco")
    # pescoço (laje em z, por BAIXO do varrimento do braço A do garfo e por fora da orelha do servo) até à parede do
    # fim do tubo (t = 62…64 ao longo de −u) e o casquilho do tubo (t = 64…94, fenda por baixo e 2 × M4): assim nem o
    # casquilho nem a parede entram no y do braço A do garfo (|y| ≤ 33,4) em todo o curso do cotovelo
    u45 = np.array([math.sqrt(0.5), math.sqrt(0.5), 0.0])
    T0, T1 = 62.0, 64.0
    q_ = math.sqrt(0.5)
    c0 = -q_ * T0
    r_s = r_t + 3.0
    x_b = DS["or_x0"] - 1.25                      # face −x da borda do berço
    n1 = (c0 - q_ * r_s, c0 + q_ * r_s)
    n2 = (c0 + q_ * r_s, c0 - q_ * r_s)
    pescoco = _poli([n1, n2, (x_b, y_or - 6.0), (x_b, y_or + 8.0), (x_b - 9.5, y_or + 8.0)])
    cj.j(BR, "abs_cinza", _ext(pescoco, (), -r_s, 2.0))
    R_u = _base(np.array([-q_, q_, 0.0]), np.array([0.0, 0.0, 1.0]), -u45)
    cj.j(BR, "abs_cinza", _ext(_circulo(0.0, 0.0, r_s, 48), (), T0, T1), R_u, np.zeros(3))
    _aperto_fenda_abs(cj, BR, "abs_cinza", "cotovelo_berco", (0.0, 0.0, 0.0), -u45, (0.0, 0.0, -1.0), r_t, r_s,
                      T1, T1 + 30.0, (T1 + 7.0, T1 + 23.0), "M4", meio=6.0)
    _impressa(cj, "cotovelo_berco", "Berço do servo do cotovelo (ABS)", (0, -1, 0),
              "Imprime-se pousado pela borda das orelhas (o fundo com o assento do 608ZZ para cima); o casquilho do tubo "
              "a 45° precisa de suportes; 4 insertos M3 (orelhas do servo) e 2 M2,5 (AS5600).", BR)
    # ------------------------------------------------------------------ garfo em U (ABS laranja, no mastro)
    cj.peca = "cotovelo_garfo"
    z_p = Z_PONTE_ABS
    y_a1 = DS_TOPO_Y - HORN25["z1"]               # face do horn (o braço A do garfo encosta-lhe)
    y_a0 = y_a1 - 4.5
    y_b0 = -y_a1                                  # braço B simétrico (por fora do lábio do berço)
    y_b1 = -y_a0
    face = _face_garfo(12.0, z_p + 6.0)
    furos_a = tuple(_circulo(0.5 * HORN25["pcd"] * math.cos(a), 0.5 * HORN25["pcd"] * math.sin(a), 1.7, 12)
                    for a in (math.radians(45.0 + 90.0 * i) for i in range(4)))
    cj.j(MA, "abs_laranja", _ext_y(face, (_circulo(0.0, 0.0, 3.5, 20),) + furos_a, y_a0, y_a1))
    cj.j(MA, "abs_laranja", _ext_y(face, (_circulo(0.0, 0.0, 4.25, 24),), y_b0, y_b1))
    cj.j(MA, "abs_laranja", _caixa(-12.0, 12.0, y_a1, y_b0, z_p, z_p + 6.0, r=1.0))
    for a in (math.radians(45.0 + 90.0 * i) for i in range(4)):
        x, z = 0.5 * HORN25["pcd"] * math.cos(a), 0.5 * HORN25["pcd"] * math.sin(a)
        cj.parafuso(MA, (x, y_a0, z), (0, 1, 0), "M3", aperto=4.5, rosca_metida=4.5, peca="cotovelo_garfo")
    # parafuso M8 (eixo do cotovelo): cabeça na caixa do fundo do berço, anel interior do 608, espaçador, braço B, porca
    y_cab1 = y_ass0
    y_cab0 = y_cab1 - 5.3
    L_m8 = 25.0
    cj.j(MA, "aco", _sext(13.0, y_cab0, y_cab1), R_Y)
    cj.j(MA, "aco", _cil(4.0, y_cab1, y_b1 + 8.0 - 0.6, 24), R_Y)
    vr, fr = fer._rosca_ext(8.0, 1.25, y_b1 + 8.0 - 0.6, y_cab1 + L_m8, True, n=14)
    cj.j(MA, "aco", (vr, fr, np.zeros((len(vr), 2))), R_Y)
    cj.ferragem("registar", MA, (0.0, y_cab1, 0.0), (0, 1, 0), peca="cotovelo_garfo", tipo_reg="parafuso_iso4017",
                norma="ISO 4017", rosca="M8", comp_mm=L_m8, material="fer_aco_zincado",
                descricao="Parafuso sextavado ISO 4017 M8 × 25 (eixo do cotovelo: roda no 608ZZ do berço)")
    cj.j(MA, "aco", _anel(6.0, 4.1, y_lab, y_b0, 28), R_Y)                              # espaçador
    cj.ferragem("porca", MA, (0.0, y_b1, 0.0), (0, 1, 0), rosca="M8", norma="ISO 10511", peca="cotovelo_garfo")
    cj.eixo(MA, "cotovelo{k}_m8", (0.0, y_ass0 + 3.5, 0.0), (0, 1, 0), "parafuso M8 do garfo", junta="cotovelo{k}")
    # aperto do mastro Ø16 em cima da ponte (fenda para −x, 1 × M3)
    _aperto_fenda_abs(cj, MA, "abs_laranja", "cotovelo_garfo", (0.0, 0.0, 0.0), (0, 0, 1), (-1.0, 0.0, 0.0), 8.0, 11.0,
                      z_p + 6.0, z_p + 22.0, (z_p + 14.0,), "M3", meio=4.5)
    _impressa(cj, "cotovelo_garfo", "Garfo do cotovelo com o aperto do mastro (ABS laranja)", (0, 0, 1),
              "Imprime-se de cabeça para baixo, pousado no topo do aperto do mastro (os braços do U para cima, sem "
              "suportes).", MA)
    # ------------------------------------------------------------------ AS5600 + íman diametral na ponta do M8
    cj.peca = "cotovelo_encoder"
    y_ponta = y_cab1 + L_m8
    cj.j(MA, "iman", _cil(3.0, y_ponta, y_ponta + 2.5, 20), R_Y)
    y_chip0 = y_pcb0 - 1.0
    cj.j(BR, "pcb_azul", _ext_y(_ret(-11.0, 11.0, -19.0, 9.0, r=1.0),
                                tuple(_circulo(x, -15.0, 1.3, 12) for x in (-6.0, 6.0)), y_pcb0, y_pcb0 + 1.6))
    cj.j(BR, "chip", _caixa(-2.5, 2.5, y_chip0, y_pcb0, -2.5, 2.5))
    for i in range(4):
        x = -3.81 + 2.54 * i
        cj.j(BR, "ouro", _caixa(x - 0.32, x + 0.32, y_pcb0 + 1.6, y_pcb0 + 8.0, 6.68, 7.32))
    cj.j(BR, "chip", _caixa(-5.08, 5.08, y_pcb0 + 1.6, y_pcb0 + 4.1, 5.73, 8.27))
    cj.ancora(BR, "servo_cotovelo{k}_ficha_b", (0.0, y_pcb0 + 8.0, 7.0), (0, 1, 0))
    for x in (-6.0, 6.0):
        cj.parafuso(BR, (x, y_pcb0 + 1.6, -15.0), (0, -1, 0), "M2.5", aperto=1.6, rosca_metida=3.0,
                    peca="cotovelo_encoder")
    cj.ancora(MA, "cotovelo{k}_eixo_cabos", (0.0, y_a0 - 10.0, 0.0), (0, -1, 0),
              nota="no eixo do cotovelo, 7 mm por fora das cabeças dos 4 parafusos do horn (braço A do garfo)")
    return cj.congelar()


def _suporte_motor_abs(pb: dict, r_p: float, z0: float, z1: float):
    """Suporte do motor impresso (ABS) no corpo `mastro{k}` (z0…z1 = a placa do geom `suporte_motor_k`, que fica
    escondido; mm): placa com a furação de `motores.padrao_base` e o furo central + aperto do mastro Ø16 por baixo
    (fenda e 1 × M3 com porca)."""
    cj = _Conj()
    cj.peca = "suporte_motor"
    furos = tuple(_circulo(x, y, 0.5 * FURO_PASSANTE.get(pb.get("rosca", "M3"), 3.4), 14) for x, y in pb["furos_mm"])
    furos += (_circulo(0.0, 0.0, 0.5 * float(pb.get("furo_central_mm", 9.0)), 24),)
    cj.j("m", "abs_cinza", _ext(_circulo(0.0, 0.0, r_p, 56), furos, z0, z1))
    # o aperto do mastro por baixo da placa; os 3,5 mm de cima são um anel com 4 MORDIDAS (r 3,1) onde assentam as
    # cabeças dos parafusos do motor (cabeça Ø 5,5 × 3 por baixo da placa)
    _aperto_fenda_abs(cj, "m", "abs_cinza", "suporte_motor", (0.0, 0.0, 0.0), (0, 0, 1), (-1.0, 0.0, 0.0), 8.0, 11.0,
                      z0 - 16.0, z0 - 3.5, (z0 - 9.5,), "M3", meio=4.5)
    mordidas = [(float(x), float(y), 3.1) for x, y in pb["furos_mm"]]
    pts = []
    for i in range(144):
        a = _TAU * i / 144
        d = np.array([math.cos(a), math.sin(a)])
        r = 11.0
        for x, y, rb in mordidas:
            c = np.array([x, y])
            t = float(c @ d)
            h2 = rb * rb - (float(c @ c) - t * t)
            if h2 > 0.0 and t - math.sqrt(h2) > 0.0:
                r = min(r, t - math.sqrt(h2))
        pts.append((r * d[0], r * d[1]))
    cj.j("m", "abs_cinza", _ext(_poli(pts), (_circulo(0.0, 0.0, 8.0, 48),), z0 - 3.5, z0))
    _impressa(cj, "suporte_motor", "Suporte do motor (ABS)", (0, 0, 1),
              "Imprime-se de cabeça para baixo, pousado na face onde assenta o motor (o aperto do mastro para cima).", "m")
    return cj.congelar()


@functools.cache
def _perna_abs_canonica(s_leg: float, r_t: float, z_fundo: float) -> tuple:
    """Perna ACESSÍVEL (ao longo de +x, braço 1): abraçadeira de fenda impressa no tubo (fenda de lado, 1 × M4) com uma
    almofada por baixo, aperto do varão de carbono Ø12 (fenda, 1 × M3) e o pé impresso no fundo da cápsula física."""
    cj = _Conj()
    P_ = "p"
    cj.peca = "perna"
    W = np.array([0.0, 1.0, 0.0])
    _aperto_fenda_abs(cj, P_, "abs_cinza", "perna", (0.0, 0.0, 0.0), (1, 0, 0), W, r_t, r_t + 3.5, s_leg - 12.0,
                      s_leg + 12.0, (s_leg,), "M4", meio=6.0)
    z_alm = -(r_t + 3.5) - 4.0
    cj.j(P_, "abs_cinza", _caixa(s_leg - 12.0, s_leg + 12.0, -9.0, 9.0, z_alm, -(r_t + 1.0)))
    _aperto_fenda_abs(cj, P_, "abs_cinza", "perna", (s_leg, 0.0, 0.0), (0, 0, -1), (1.0, 0.0, 0.0), 6.0, 9.5,
                      -z_alm, -z_alm + 22.0, (-z_alm + 11.0,), "M3", meio=4.0)
    z_vara0 = z_alm - 1.0
    z_pe1 = z_fundo + 16.0
    cj.j(P_, "carbono", _anel(6.0, 5.0, z_pe1 - 8.0, z_vara0, 24), None, (s_leg, 0.0, 0.0), "perna")
    perfil_pe = (((0.0, z_fundo), (5.0, z_fundo)), ((5.0, z_fundo), (8.0, z_fundo + 2.5)),
                 ((8.0, z_fundo + 2.5), (9.0, z_fundo + 6.0)), ((9.0, z_fundo + 6.0), (9.0, z_pe1)),
                 ((9.0, z_pe1), (6.0, z_pe1)), ((6.0, z_pe1), (6.0, z_pe1 - 8.0)), ((6.0, z_pe1 - 8.0), (0.0, z_pe1 - 8.0)))
    cj.j(P_, "abs_preto", _torno(perfil_pe, 32), None, (s_leg, 0.0, 0.0), "perna")
    _impressa(cj, "perna", "Abraçadeira da perna e pé (ABS)", (0, 0, -1),
              "2 peças: a abraçadeira imprime-se de lado (a fenda para cima) e o pé de pé pela base.", P_)
    return cj.congelar()


def _furo_fpc(mt: _Montador, r: float = 10.5):
    """O rasgo do FPC da câmara CSI na placa de baixo (mm, no referencial nominal do drone): disco de raio r em
    (x_min da câmara − 22, −30) — onde os fios procuram a subida do FPC (`fios._rota_fpc`). None sem câmara."""
    g = mt.ctx.geom_existente("camera")
    if g is None or g.type != mujoco.mjtGeom.mjGEOM_BOX:
        return None
    Rq = np.zeros(9)
    mujoco.mju_quat2Mat(Rq, np.asarray(g.quat, float))
    h = np.abs(Rq.reshape(3, 3)) @ np.asarray(g.size, float)
    o = mt.origem_m("drone")
    x_lo = (float(g.pos[0]) - float(h[0]) - float(o[0])) / MM
    return _circulo(round(x_lo - 22.0, 4), round((-0.030 - float(o[1])) / MM, 4), r, 40)


def _placas_abs(mt: _Montador, L: float, esp: float, zs0: float, zs1: float, pin1, furos_extra):
    """Placas IMPRESSAS em ABS (cabem na mesa de 220 × 220): a de baixo com os entalhes dos cantos (forquilhas dos
    ombros, encoder e varrimento do cubo) e 2 nervuras por baixo; a de cima inteira com 2 nervuras por baixo — com os
    furos de TODOS os parafusos que as atravessam e os rasgos das cintas da bateria."""
    ctx = mt.ctx
    g = ctx.geom_existente("placa_superior")
    rasgos = []
    for r in (ctx.registo.notas.get("rasgos_cintas") or []):
        if r.get("corpo", "drone") != "drone":
            continue
        c = (np.asarray(r["centro"], float) - mt.origem_m("drone")) / MM
        comp, larg = float(r.get("comprimento_mm", 20.0)), float(r.get("largura_mm", 4.0))
        e = r.get("eixo_comprido", (1.0, 0.0, 0.0))
        rasgos.append(_rasgo(float(c[0]), float(c[1]), 0.5 * max(comp - larg, 0.0), 0.5 * larg,
                             ang=math.atan2(float(e[1]), float(e[0]))))
    Ls = round(float(g.size[0]) / MM, 5) if g is not None else round(0.88 * L, 5)
    x_n, y_n = abs(pin1[0]) - 24.5, abs(pin1[1]) - 57.0
    v = [(L, -y_n), (L, y_n), (x_n, y_n), (x_n, L), (-x_n, L), (-x_n, y_n), (-L, y_n), (-L, -y_n),
         (-x_n, -y_n), (-x_n, -L), (x_n, -L), (x_n, -y_n)]
    ext_b = _poligono_arred(tuple(v), 3.0)
    ext_s = _poligono_arred(((Ls, -Ls), (Ls, Ls), (-Ls, Ls), (-Ls, -Ls)), 4.0)
    alivio_b = (_poligono_arred(((0.22 * L, -0.125 * L), (0.22 * L, 0.125 * L), (-0.22 * L, 0.125 * L),
                                 (-0.22 * L, -0.125 * L)), 0.048 * L),)
    # RASGO do FPC da câmara (Ø 21 em (x_cam − 22, −30): os fios procuram aí o maior disco livre, e este tem de ganhar
    # ao entalhe do canto) e os furos de alívio Ø14 (os mesmos da placa de carbono)
    furo_fpc = _furo_fpc(mt)
    alivio_b = ((furo_fpc,) if furo_fpc is not None else ()) + alivio_b
    alivio_b += tuple(_circulo(sx * a * L, sy * b * L, max(0.067 * L, 6.3), 28) for sx in (1, -1) for sy in (-1, 1)
                      for a, b in ((0.77, 0.29), (0.29, 0.77)))
    alivio_s = (_poligono_arred(((47.0, -32.0), (47.0, 32.0), (-47.0, 32.0), (-47.0, -32.0)), 6.0),)
    for nome_p, ext, alivio, z0, z1 in (("inf", ext_b, alivio_b, -esp, esp), ("sup", ext_s, alivio_s, zs0, zs1)):
        furos_p = [_circulo(x, y, r, 14) for x, y, r in _furos_parafusos(ctx, mt, "drone", z0, z1)]
        furos_p += [_circulo(x, y, r, 18) for (x, y), r, placa in furos_extra if placa == nome_p]
        if nome_p == "inf":
            furos_p += rasgos
        furos_p = [f for f in furos_p if all(_no_poligono(x, y, ext) for x, y in f)]
        furos = tuple(furos_p) + _furos_que_cabem(ext, alivio, 2.0, fixos=tuple(furos_p))
        if nome_p == "inf":
            if furo_fpc is not None and furo_fpc not in furos:
                warnings.warn("detalhes/estrutura: o rasgo do FPC da câmara não cabe na placa de baixo ABS (parafusos "
                              "perto)", stacklevel=2)
            mt.juntar("drone", "abs_cinza", _ext(ext, furos, z0, z1), "placa_inferior")
            for sy in (-1.0, 1.0):
                mt.juntar("drone", "abs_cinza", _caixa(-0.66 * L, 0.66 * L, sy * 70.0 - 1.5, sy * 70.0 + 1.5,
                                                       z0 - 6.0, z0), "placa_inferior")
            ctx.esconder("placa")
        elif g is not None:
            zc = 0.5 * (zs0 + zs1)
            v1, f1, t1 = _ext(ext, furos, zs0 - zc, zs1 - zc)
            partes = [(v1, f1, t1)]
            for sy in (-1.0, 1.0):
                partes.append(_caixa(-48.0, 48.0, sy * 62.0 - 1.5, sy * 62.0 + 1.5, zs0 - zc - 5.0, zs0 - zc))
            vs, fs, ts, nv = [], [], [], 0
            for vv, ff, tt in partes:
                vs.append(vv)
                fs.append(np.asarray(ff) + nv)
                ts.append(tt)
                nv += len(vv)
            _reestilizar_malha(ctx, g, "m_est_placa_superior", (np.concatenate(vs) * MM, np.concatenate(fs),
                                                                np.concatenate(ts)), mt.mat["abs_cinza"],
                               "placa_superior")
    ctx.registo.notas.setdefault("impressas", {})["placa_inferior#0"] = {
        "nome": "Placa de baixo (ABS)", "orientacao": _quat_mesa((0, 0, 1)),
        "nota": "Imprime-se com as nervuras para cima (a face de cima da placa na mesa); 208 × 208 mm cabe na mesa de "
                "220 × 220."}
    ctx.registo.notas["impressas"]["placa_superior#0"] = {
        "nome": "Placa de cima (ABS)", "orientacao": _quat_mesa((0, 0, 1)),
        "nota": "Imprime-se com as nervuras para cima (a face de cima na mesa)."}


def _colunas_abs(mt: _Montador, esp: float, zs0: float, zs1: float):
    """As 4 colunas impressas Ø10 entre as placas (os geoms `espacador_placa_*` reestilizados e mudados para fora das
    forquilhas dos ombros), com um inserto M3 em cada ponta e um ISO 4762 M3 por cima e outro por baixo."""
    ctx = mt.ctx
    h = zs0 - esp
    for i, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1)), start=1):
        g = ctx.geom_existente(f"espacador_placa_{i}")
        if g is None:
            continue
        x, y = sx * 58.5, sy * 62.0                   # (a cabeça do M3 de baixo fica fora do suporte do driver DRV8871)
        perfil = (((0.0, 0.0), (5.0, 0.0)), ((5.0, 0.0), (5.0, h)), ((5.0, h), (0.0, h)))
        v, f, t = _torno(perfil, 24)
        g.pos = ctx.p(x * MM, y * MM, esp * MM)
        g.size = [0.005, 0.5 * h * MM, 0.0]
        _reestilizar_malha(ctx, g, f"m_est_espacador_{i}", (v * MM, f, t), mt.mat["abs_cinza"], "espacadores", 0)
        for z, e in ((esp, (0.0, 0.0, 1.0)), (zs0, (0.0, 0.0, -1.0))):
            mt.juntar("drone", "fer_latao", _anel(1.97, 1.25, 0.0, 5.7, 16), "espacadores", 0, _r_eixo(e), (x, y, z))
            ctx.ferragens.registar(corpo="drone", ponto=mt.ponto_m("drone", (x, y, z)), eixo=e, peca="espacadores",
                                   inst=0, tipo="inserto", norma="inserto de latão M3", rosca="M3", comp_mm=5.7,
                                   material="fer_latao", descricao="Inserto de latão M3 × 5,7 mm (cravar a quente no ABS)")
        col = ctx.ferragens
        for p, e, aperto in (((x, y, zs1), (0, 0, -1), zs1 - zs0), ((x, y, -esp), (0, 0, 1), 2.0 * esp)):
            reg = col.parafuso("drone", mt.ponto_m("drone", p), e, "M3", aperto=aperto, rosca_metida=5.0,
                               peca="espacadores", inst=0)
            mt.ferragens.append(("drone", np.asarray(p, float), np.asarray(e, float), reg))
    ctx.registo.notas.setdefault("impressas", {})["espacadores#0"] = {
        "nome": "Colunas entre as placas (ABS, × 4)", "orientacao": _quat_mesa((0, 0, -1)),
        "nota": "Imprimem-se de pé; um inserto M3 em cada ponta."}


def _mecanismo_abs(mt: _Montador, hw, esp: float, zs0: float, zs1: float):
    """Os 4 braços ACESSÍVEIS: ombro de fuso, cotovelo DS3218MG, tubo, suporte do motor e perna impressos."""
    ctx = mt.ctx
    from ..modelo import geometria_bracos
    geo = geometria_bracos(hw)
    r_s, l1 = geo["r_s"] / MM, geo["l1"] / MM
    r_t = round((_tubo_do_frame(hw) or 0.0125) / MM, 4)
    fu = _fuso_do_hw(hw)
    ax, ym, az = (round(float(v), 4) for v in fu["alavanca_mm"])
    bx, _by, bz = (round(float(v), 4) for v in fu["base_mm"])
    l_fuso = round(float(fu["comprimento_fuso_mm"]), 4)
    pb = _padrao_motor(hw)
    d_mot = float(hw.motor.dados.get("diametro_mm", 28.0))
    r_p = round(0.5 * d_mot + 1.5, 4)
    furos_extra = []
    for i, (x, y) in enumerate(hw.pos_rotores):
        k = i + 1
        ang = math.atan2(y, x)
        ux, uy = math.cos(ang), math.sin(ang)
        sx, sy = math.copysign(1.0, ux), math.copysign(1.0, uy)
        M = np.diag([sx, sy, 1.0])
        mao = 1 if sx * sy > 0 else -1
        P = np.array([r_s * ux, r_s * uy, 0.0])
        conj, furos_c = _ombro_fuso_canonico(round(esp, 4), round(zs0, 4), round(zs1, 4), r_t, ax, az, bx, bz, ym,
                                             l_fuso, mao)
        mt.colocar(conj, {"fixo": "drone", "movel": f"braco{k}", "base": ("drone", f"ombro{k}_fuso_base"),
                          "veio": ("drone", f"ombro{k}_fuso_veio"), "porca": (f"braco{k}", f"ombro{k}_fuso_porca")},
                   M, {"fixo": P, "base": P, "veio": P}, inst=k)
        for etq, (fx, fy), r, placa in furos_c:
            q = M @ np.array([fx, fy, 0.0]) + P
            furos_extra.append(((float(q[0]), float(q[1])), r, placa))
        mt.colocar(_cotovelo_abs_canonico(r_t), {"braco": f"braco{k}", "mastro": f"mastro{k}"}, M,
                   {"braco": l1 * np.array([ux, uy, 0.0])}, inst=k)
        u = np.array([ux, uy, 0.0])
        cj = _Conj()
        _tubo(cj, "b", u, 25.0, l1 - 64.0, r_t, "tubo_braco")
        mt.colocar(cj.congelar(), {"b": f"braco{k}"}, None, {}, inst=k)
        gs = ctx.geom_existente(f"suporte_motor_{k}")
        if gs is not None:
            z_c = float(gs.pos[2]) / MM - float(mt.origem_m(f"mastro{k}")[2]) / MM
            hz = float(gs.size[1]) / MM
            _ocultar_visual(gs)
            # a furação do motor roda com o braço (como os parafusos do `motores`)
            mt.colocar(_suporte_motor_abs(pb, r_p, round(z_c - hz, 4), round(z_c + hz, 4)), {"m": f"mastro{k}"},
                       _rot_z(ang), {}, inst=k)
            # o mastro de carbono Ø16, da ponte do garfo até dentro do aperto do suporte do motor
            cjm = _Conj()
            cjm.j("m", "carbono", _anel(8.0, 7.0, Z_PONTE_ABS + 6.0, z_c - hz - 1.0, 28), None, None, "mastro")
            mt.colocar(cjm.congelar(), {"m": f"mastro{k}"}, None, {}, inst=k)
        perna = _dados_perna(mt, f"braco{k}", f"perna{k}")
        if perna is not None:
            mt.colocar(_perna_abs_canonica(perna[0], r_t, perna[1]), {"p": f"braco{k}"}, _rot_z(ang), {}, inst=k)
            ctx.esconder(f"perna{k}")
        for nome in (f"braco{k}_raiz", f"braco{k}_tubo", f"servo_ombro{k}", f"sem_fim{k}", f"servo_cotovelo{k}",
                     f"mastro{k}_tubo", f"ombro{k}_carro"):
            if ctx.geom_existente(nome) is not None:
                ctx.esconder(nome)
        antigos = [f"dobradica_ombro{k}", f"dobradica_cotovelo{k}", f"garfo_cotovelo{k}", f"sem_fim{k}_eixo"]
        antigos += [f"{t}_{j}{k}_{s}" for t in ("corneta", "marca") for j in ("ombro", "cotovelo") for s in ("a", "b")]
        for nome in antigos:
            if ctx.geom_existente(nome) is not None:
                ctx.apagar(nome)
    return furos_extra


# ===================================================================================================== entrada
def adicionar(ctx) -> None:
    """Estrutura realista (todos os builds) e, no articulado, o mecanismo dos braços — ver o docstring do módulo."""
    mt = _Montador(ctx)
    L, _, esp = (float(v) / MM for v in ctx.tamanho_geom("placa"))
    gsup = ctx.geom_existente("placa_superior")
    o = mt.origem_m("drone") / MM
    if gsup is not None:
        zc = float(np.array(gsup.pos)[2]) / MM - o[2]
        zs0, zs1 = zc - float(gsup.size[2]) / MM, zc + float(gsup.size[2]) / MM
    else:
        zs0, zs1 = esp + 12.8, esp + 15.2
    pin1 = (0.0, 0.0)
    furos_extra = []
    if ctx.articulado and _e_mecanismo_abs(ctx.hw):
        from ..modelo import geometria_bracos
        r_s = geometria_bracos(ctx.hw)["r_s"] / MM
        x, y = ctx.hw.pos_rotores[0]
        a = math.atan2(y, x)
        pin1 = (r_s * math.cos(a), r_s * math.sin(a))
        furos_extra = _mecanismo_abs(mt, ctx.hw, esp, zs0, zs1)
        _colunas_abs(mt, esp, zs0, zs1)
        _placas_abs(mt, L, esp, zs0, zs1, pin1, furos_extra)
        mt.criar()
        return
    if ctx.articulado:
        from ..modelo import geometria_bracos
        r_s = geometria_bracos(ctx.hw)["r_s"] / MM
        x, y = ctx.hw.pos_rotores[0]
        a = math.atan2(y, x)
        pin1 = (r_s * math.cos(a), r_s * math.sin(a))
        furos_extra = _mecanismo(mt, ctx.hw, esp, zs0, zs1)
    else:
        _frame_rigido(mt, ctx.hw, esp, L)
    _espacadores(mt, esp, zs0, zs1, L)
    _placas(mt, ctx.articulado, L, esp, zs0, zs1, pin1, furos_extra)
    mt.criar()
