"""lab/drone_rpi/detalhes/fios.py — CABLAGEM realista do drone (só APARÊNCIA: massa 0, sem contacto, grupo 3).

Cada cabo é um TUBO varrido ao longo de uma curva suave (fichas e cabeças de abraçadeira são prismas, as fitas são
perfis retangulares fechados) e tudo o que tem o mesmo material no mesmo corpo junta-se numa MALHA — um geom por
corpo × material — com o INTERVALO DE FACES de cada peça real registado (`ctx.registar_faixas`): `cabo_bateria`,
`cabo_esc` k, `cabo_fases` k, `cabo_rpi5_5v`, `cabo_uart`, `cabo_i2c`, `fpc_camera`, `cabo_sensores`, `cabo_dxl` k,
`cabo_servo` k (cabo do servo do cotovelo no build acessível e a derivação do PWM dele ao Pico; k = 0 o servo-rail e,
sem os Pico, a fita PWM), `cabo_fonte24`, `cabo_atuadores` n (12 V do pack aos bucks e aos DRV8871), `cabo_motorredutor`
k (e os sinais do DRV8871 k), `cabo_sensores_braco` k (Hall, AS5048A e AS5600 do braço k), `cabo_controlador` n (UART e
5 V do Pico n; 0 = o tronco de 5 V), `manga` k, `abracadeira` n e `cablagem` (fichas partilhadas). Cada cabo declara de que âncora sai e a que âncora chega
(`ctx.ligacao`, os pontos extremos no referencial de cada corpo, a TOCAR na âncora) e a polilinha de cada tubo fica em
`registo.notas["fios_cabos"]` (a auditoria confere folgas e cruzamentos com ela; os troços que rodam com um grupo animado
da planta levam `"grupo"`). Os RABICHOS (cabo + ficha JST-GH solta, sem ligação: o FC não tem ficha publicada para esses
sinais) ficam em `registo.notas["fios_rabichos"]`.

O que se desenha (bitolas, cores e fichas REAIS — fontes no fim; Ø = diâmetro exterior do fio de silicone):
  · ENERGIA — a cadeia completa está declarada: células → (pack, `eletronica`) → XT90 fêmea `conector_xt90` → XT90 macho
    `el_xt90_macho` / copos `el_xt90_copo_pos/neg` → 10 AWG (Ø 5,5 mm) vermelho/preto por trás e por cima da placa de
    cima (no Arduino deitados nela, por fora da base do carregador da arma, que desce a 5 mm da placa; onde o caminho
    entraria nalguma peça por baixo, sobe o que falta — medido) → ilhas `el_pdb_bat_pos/neg` → (placa de energia, BEC 5 V/5 A) → ilhas `el_pm_5v_pos/neg` → par 20 AWG
    (Ø 1,8 mm, vermelho 5 V / preto GND) → ficha USB-C macho na `rpi5_usbc`. Os troços que são da eletrónica (o pack, o
    encaixe do XT90, as pistas da placa) declaram-se como `tipo` «interno»/«encaixe»/«pista» se ela não os declarar.
  · Raspberry Pi 5 — FICHA USB-C de soldar com sobremoldagem a 90° (saída lateral, para trás): casca metálica 8,25 ×
    2,40 mm METIDA 6,65 mm no recetáculo `rpi5_usbc` (0,4 mm de casca à vista), corpo 12,0 × 6,5 × 9,0 mm (a norma
    admite 12,35 × 6,5) e manga de alívio de onde saem os 2 fios, um por cima do outro. O corpo fica por BAIXO da placa
    de cima (0,35 mm de folga): a janela da placa só deixa 2,8 mm entre o recetáculo e a borda dela, por isso uma ficha
    direita ou a 90° para cima/baixo não cabe. O corpo e a manga MEDEM-SE (`_folga_usbc`, raios para baixo, para cima e
    para o lado oposto à manga): no 5″, com o Pi na janela da placa de cima, sobe e encolhe até ao mínimo de uma ficha de
    SOLDAR em termo-retráctil (3,0 × 10,4 mm, «estimado»); e se nem assim cabe à frente da boca (5″: a cabeça de um
    M3 a 3 mm dela), é uma ficha em ÂNGULO RETO virada para o lado livre — à frente da boca só um colar fino à volta
    da casca e o corpo fundo do lado da manga (`_usbc_corpo_l`, medido). O par 20 AWG (Ø 1,8, encostados) corre ao longo da borda −y por baixo da
    placa de cima, sobe pela folga da janela entre o micro-HDMI e o FPC da câmara (medida com raios), junta-se POR FORA
    ao par de sinal de um ESC que corre ao lado do FC e uma abraçadeira T18R prende os 4 fios (o par roda pelo caminho
    até ficar de pé ao lado do sinal); depois sobe por fora da placa de energia e cada fio vai à sua ilha
    `el_pm_5v_pos/neg` (cordão de solda) — primeiro o da ilha mais perto, o outro passa-lhe POR CIMA se o cruza. Sem as
    ilhas, entra numa ficha lateral na `el_pm_saida_5v`.
  · FASES — 3 fios 16 AWG (Ø 3,0 mm) laranja-escuro por motor: o «motor cable» dos ESC T-Motor (16 AWG, 65 mm),
    emendado (termo-retráctil preto, ASSENTE no que o cabo tem por baixo: sobe os décimos que faltam, medidos) com
    extensões da mesma bitola até às balas de 3,5 mm dos cabos do motor
    (`motor{k}_fase_{a,b,c}_conector`, módulo `motores`), com a fêmea em termo-retráctil enfiada na bala. No build
    articulado seguem numa manga entrançada de PET desde a emenda, cruzam o COTOVELO por um caminho à volta do servo
    (medido; validado em todo o curso ±60°) e, no topo do mastro, o triângulo das 3 fases roda até ter o vértice virado
    para as balas e os fios abrem em leque. ESC 4-em-1 central (5″): os fios do motor não têm balas (o `motores`
    publica as pontas estanhadas `mot{k}_fio_fim_{a,b,c}`) e continuam como o MESMO fio até à ilha da fase, soldados
    (`_fases_soldadas`, só onde a ilha está acessível — hoje as ilhas do 4 em 1 ficam debaixo dos braços de carbono:
    pendente em `notas["fios_pendentes"]`); nada de balas, extensões nem do troço de reserva. (Com balas dentro da
    pegada do 4 em 1: só a fêmea, curta e assente no braço, soldada à ilha.)
  · ESC — par vermelho/preto 14 AWG (Ø 3,5 mm) da saída de entrada do ESC às ilhas `el_pdb_esc{k}_pos/neg` e SINAL em par
    ENTRANÇADO branco/preto até à ficha JST-GH do FC (`el_fc_con_esc`) (as 2 abraçadeiras de cada ESC são da
    `eletronica`; nenhum cabo daqui as cruza). RÍGIDO: no topo do tubo e da abraçadeira do canto o perfil mede-se no eixo
    E por baixo do próprio cabo (as cabeças dos parafusos ao lado); na placa de baixo os 3 sobem ao lado da pilha por 3
    pontos de subida MEDIDOS (raios para a pilha — a ponte de carbono do FC sai da caixa do Pi — e para a janela da placa
    de cima) pela mesma ordem lateral em que chegam: cada fio deixa o feixe onde cruza a SUA faixa (paralela à face da
    pilha, 4 mm por faixa) e só entra na folga junto à sua subida; desviam-se dos postes entre placas; assentam na placa e
    passam POR CIMA de um fio já desenhado onde o cruzam. Da subida à ilha rentes à placa de energia (por baixo do
    suporte da arma): se as 2 ilhas estão em fila, o fio da de lá vai por uma faixa ao lado da de cá; se os caminhos se
    cruzam, o 2.º passa por cima do 1.º à altura exata que o tira dele. Placa de energia POR CIMA de uma placa de cima
    sem janela (Arduino: o Portenta entre as placas, `_esc_por_rasgos`): os 14 AWG vão ENTRE AS PLACAS (mapa 2,5D:
    postes, colunas M3 da pilha, Portenta), sobem pelo RASGO da placa de cima do lado da ilha (rasgos medidos com
    raios), deitam-se nela e sobem à ilha pela borda da placa de energia; o sinal fica entre as placas, num rabicho
    com a ficha JST-GH junto ao Portenta (não há ficha publicada para os sinais dos ESC).
  · FC — UART (Dupont 1×3 nos pinos 6 GND / 8 TXD / 10 RXD do GPIO: colunas `el_rpi5_gpio_pino03..05` do
    `rpi5_gpio_40p`) até ao JST-GH `el_fc_con_uart`; I2C (JST-GH) do `el_fc_con_i2c` ao INA226 (`el_pm_con_i2c`);
    sensores de baixo (PMW3901 + VL53L1X, saltador de 4 fios entre as placas) até ao `el_fc_con_sensores`.
  · FPC da câmara: 15 vias de 1 mm (16 mm) na Camera Module 3 → 22 vias de 0,5 mm (11,5 mm) no `el_rpi5_cam_disp0`,
    por um percurso MEDIDO (`_rota_fpc`): sai por baixo da trava do conector da câmara, desce à frente da borda da placa
    de baixo, passa POR BAIXO das porcas M3 do suporte da câmara (10,5 mm entre elas: o FPC não cabe entre elas) e à
    frente da bateria, com curvas no plano (FPC à medida, «estimado») até ao RASGO da placa (o maior disco livre, medido),
    sobe por ele, corre rente à face de baixo da placa de cima por fora das subidas dos cabos e entra na janela; DOBRA
    a 45° por cima do conector do Pi (o pilar de latão e o `el_rpi5_ffc_disp1` não deixam a dobra ao nível dele) e entra
    nele num laço em U. Sem rasgo que sirva (braços curtos, bateria por baixo do rasgo, 5″) fica o percurso antigo com
    aviso. O par de 5 V sobe entre os 2 micro-HDMI (o FPC ocupa a folga ao lado do conector). Quando o desenho de
    sempre não cabe (x500, compacto: o pack encosta à placa e fica a 10–15 mm da câmara), um 2.º modo mede a BATERIA
    só pelas malhas visíveis dela DENTRO da zona (as variantes inativas, alfa 0, e o `bateria` com massa, escondido, não
    contam; um raio que nasce dentro do pack dava o «fundo» pelas faces de dentro dele) com folgas de 0,5/0,3 mm e
    curvas no plano de 7/6 mm. No semissólido também (desde 2026-10-20: a eletrónica baixou 2 mm o pé do suporte da
    câmara e afastou as porcas para ±9,5 mm — antes as pontas dos M3 tocavam no topo do pack e ficava o percurso antigo).
  · Build ACESSÍVEL (`articulado_15pol_abs`, cotovelo com servo PWM DS3218MG, ombro com motorredutor JGB37-520 + fuso):
    sem DYNAMIXEL. ENERGIA dos atuadores: o UBEC de 6,8 V (`el_ubec_entrada`) em 18 AWG do lado de dentro dos copos do
    XT90 (`cabo_fonte24`); os 12 V em «Y» dos lados de fora dos copos, emenda em termo-retráctil por baixo da placa de
    baixo, até aos 2 bucks e de cada buck aos seus 2 DRV8871 (`cabo_atuadores`, pares 18 AWG encostados, por baixo da
    placa pelo planeador 2,5D; o perfil fica do lado livre com inclinação ≤ 45°: os degraus de 5–13 mm por baixo dos
    drivers e da bateria torciam o par sobre si). SERVOS: o cabo do servo (redondo, 3 × 22 AWG castanho GND / vermelho 6,8 V / laranja
    PWM, condutores à vista nas pontas) vai do servo pelo lado do tubo e pelo feixe do ombro até à placa de cima e daí,
    em estrela pelo planeador (DEITADO na placa), a um servo-rail (4 × 3 pinos) na saída do UBEC (`el_ubec_saida`).
    OMBRO: o cabo de 6 vias do JGB37-520 (fita PH2.0: motor ±,
    encoder GND/VCC/A/B; cores «estimado», as das listagens) sai da ficha `servo_ombro{k}_ficha_a`; o troço do atuador
    RODA com ele (geoms `ombro{k}_fuso_base_fios_*`, do grupo animado `ombro{k}_fuso_base`: a planta roda-os) e chega ao
    EIXO de B com os 6 fios um atrás do outro ao longo do eixo (ligados em qualquer ângulo: medido 0,000 mm em ±40°);
    daí, fixo no drone, um laço de ¾ de volta em mola de relógio em `ombro{k}_pivo_b_cabos` (longe do fuso), a fita
    desce por fora da torre e o par do motor vai por baixo da placa de baixo ao `el_drv{k}_motor`.
    CONTROLADORES DOS BRAÇOS (2 × Raspberry Pi Pico 2, `el_pico{n}_*`, n = 1 do lado +y para os braços 1 e 3, n = 2 do
    −y para os 2 e 4; fichas JST-GH de entrada por cima: a ficha do cabo entra 1,4 mm, o cabo sai para cima e desce pela
    borda da placa do Pico — as descidas de todos ficam reservadas no mapa 2,5D): o PWM de cada servo sai do Pico
    (`el_pico{n}_servo{k}`, sinal + GND, 2 × 28 AWG) e DERIVA-SE no cabo do servo (emenda em termo na parte deitada,
    ≥ 16 mm antes do rail) — o servo-rail fica só com V+/GND e já não há fita PWM ao FC; os sinais dos DRV8871 (IN1/IN2/
    GND, Dupont de 3 vias no cabeçalho) vêm do `el_pico{n}_drv{k}` pela faixa da placa de baixo; os 4 do encoder Hall
    vão da separação da fita do JGB37-520 à `el_pico{n}_hall{k}`; o AS5048A (SPI, Dupont de 6 vias nos pinos dele) sobe
    ao lado das placas e vai pela de cima à `el_pico{n}_spi{k}`; o AS5600 (I²C, Dupont de 4 vias nos pinos dele) desce por
    baixo do suporte e do servo do cotovelo (fora do curso do garfo), segue colado POR BAIXO ao cabo do servo até ao
    feixe do ombro, entra na manga entrançada antes da termo da ponta, cruza o ombro dentro dela e sai do lado do drone
    para a `el_pico{n}_i2c{k}`; a UART do Pico 2 (GND, 5 V, TX, RX) vai à ficha GPS do FC (`el_fc_con_gps`, uma UART
    livre) e a do Pico 1 à 2.ª UART do FC (`el_fc_con_uart2`, JST-SH de 4 vias de entrada lateral na borda +y: a ficha
    metida 1,5 mm, o cabo passa por cima do que lá está e desce pela 1.ª coluna livre até à placa — medidas; sem ela,
    rabicho com a ficha solta junto ao FC); o 5 V dos 2 Pico sai das ilhas do
    BEC 5 V (`el_pm_5v_pos/neg`, 2.º fio em cada uma) por um tronco que sobe pela coluna livre ao lado do FC e se divide
    num Y (emenda em termo) para as `el_pico{n}_alimentacao`. Sem os Pico: rabichos com ficha JST-GH solta (encoder,
    AS5048A, AS5600) e a fita de 4 PWM + GND (5 × 28 AWG) do rail ao `el_fc_con_pwm`.
  · Build ARTICULADO — barramento DYNAMIXEL («Robot Cable-X4P», 21 AWG, fichas JST EHR-04): o regulador de 24 V
    (`el_fonte24_borne_saida`) alimenta em estrela os servos do ombro e cada um passa ao do cotovelo; o regulador é
    alimentado em 18 AWG a partir das ilhas da bateria. As fichas dos servos vêm de `registo.notas["ancoras"]`
    (`servo_ombro{k}_ficha_a/b`, `servo_cotovelo{k}_ficha_a/b`, publicadas pela `estrutura`); sem elas, a fórmula do
    XH430 (e publicam-se aqui, marcadas «fios (fórmula)»).

ABRAÇADEIRAS DE NYLON 66 (todas iguais às das fichas, PRESAS): a face de dentro da fita é o invólucro convexo da SECÇÃO
REAL do feixe naquele ponto — as peças medidas com raios no plano da abraçadeira (em 3 planos ao longo da largura da
fita) e os cabos que lá passam de facto (a polilinha de cada um cortada pelo plano), com 0,03 mm de folga —; a fita
contorna os cantos com o raio da própria espessura, a CABEÇA de lingueta assenta na fita e a PONTA cortada sai 1,3 mm da
cabeça (corte rente). O tamanho escolhe-se pelo perímetro do feixe (Ø máx. da ficha): T18R 100 × 2,5 × 1,0 mm (cabeça
4,8 × 4,45 × 3,7, feixe Ø 1,5–22), T30R 150 × 3,5 × 1,1 (cabeça 5,5 × 6,0 × 4,5, Ø ≤ 35) e T18L 205 × 2,5 × 1,2 (cabeça
4,8 × 4,5 × 3,5, Ø ≤ 50). Cada uma é a peça `abracadeira` n e fica na lista de ferragens (`ctx.ferragens.registar`,
com o laço da face de dentro). Interpretação («estimado»): a altura H da cabeça conta-se a partir da face de fora da fita.

JUNTAS (articulado): um cabo que cruza uma junta parte-se num troço POR CORPO (drone / braco{k} / mastro{k}) e os troços
encontram-se num ponto do EIXO da junta, por fora da dobradiça — fixo nos dois corpos, por isso o cabo fica ligado em
qualquer ângulo e DOBRA ali quando a junta roda (o «service loop» real). No OMBRO o ponto é a âncora da estrutura
`ombro{k}_eixo_cabos` (no eixo, fora da dobradiça); do lado do drone o feixe (manga Ø 9) desce lá por um corredor
MEDIDO por baixo do servo do ombro e as 4 vagas da ponta da manga (anel de 2,55 mm) levam cada cabo sem cruzar os
outros; folgas validadas em todo o curso (ombro ±40°, cotovelo ±60° e combinações) com mapas de folga varridos.

MALHAS: os tubos têm 5/6/8/10 lados por Ø (`_lados_tubo`: < 1,1 / < 2,6 / < 4,5 mm / maiores), cada fio do par
entrançado 6 lados e 5 anéis por volta, os 6 fios da fita do JGB37-520 são quadrados — o orçamento de faces do modelo
(≤ 650 000 no acessível, com os 2 Pico) sem soltar as abraçadeiras (A1 da auditoria: com pares de 5 lados ficavam a
0,34 mm).

MEDIÇÕES: raios (Möller–Trumbore) contra as malhas visíveis de cada corpo — com as FERRAGENS ainda por fundir — numa
grelha 3D por corpo (células de 10 mm e de 60 mm para os triângulos grandes; o resultado é o de uma busca exaustiva);
contam as peças VISÍVEIS do build (as variantes inativas da troca ao vivo, com alfa 0, não).

PLANEADOR 2,5D (`_Mesa`, build acessível): mapa de células de 1 mm de uma região de um corpo com, por célula, o CHÃO
(o topo mais alto do que está por baixo, peças e cabos já desenhados) e o TETO (o fundo do que está por cima e as
paredes que atravessam a faixa), das malhas visíveis (os triângulos grandes horizontais por linhas, os verticais pela
projeção); um cabo passa por cima dos que já lá estão (iterativo), não entra em frestas nem em zonas proibidas (a pilha
do FC), e o caminho é uma busca em largura de 8 vizinhos com atalhos; `invertido` = colado por BAIXO de uma placa.

CACHE: o resultado inteiro (malhas, cabos, ligações, âncoras novas, abraçadeiras registadas, avisos) fica em disco
(na cache do utilizador, `~/.cache/mujoco-lab/fios/` com 0700 — `DRONE_DETALHES_CACHE_DIR` muda-a), com a impressão digital de tudo o que entra — o código de lab/drone_rpi e
lab/*.py, os dados de models/drone_rpi, o Hardware do build, as versões do MuJoCo/numpy, `DRONE_DETALHES` e
`DRONE_RPI_ESCALAR`, os geoms do spec (nomes, tipos, poses, tamanhos, cores), as âncoras, as ligações e as ferragens
por fundir —: com as mesmas entradas o próximo processo lê-a em ~0,06 s (calcular: 1,5–2,6 s); medido igual bit a bit
(modelo compilado, registo e notas). `DRONE_DETALHES_CACHE=0` desliga-a.

ADAPTAÇÃO: o módulo corre DEPOIS de eletronica/motores/estrutura e ancora nas peças deles pelo NOME (acima); quando não
existem (`DRONE_DETALHES=fios`) usa as peças COM MASSA (esc{k}/esc, motor{k}, el_rpi5, el_fc_h7, el_cablagem, camera,
bateria, sensores_baixo, servo_*, fonte_servos) com a MESMA disposição que a eletrónica usa (as tabelas de reserva abaixo
são as cotas dela). Tudo é opcional (builds sem FC, sem RPi, com ESC 4-em-1, sem câmara CSI, sem braços…).

Fontes (web = dado não confiável, só citado):
  abraçadeiras: https://www.hellermanntyton.com/products/cable-ties-inside-serrated/t18r/111-91819 (T18R)
    · https://www.hellermanntyton.com/sg/products/cable-ties-inside-serrated/t30r/111-03260 (T30R)
    · https://www.hellermanntyton.com/si/proizvodi/cable-ties-inside-serrated/t18l/111-02159 (T18L)
    · https://www.farnell.com/datasheets/1537060.pdf (Panduit PLT1M-C: 2,5 × 1,1 mm, cabeça 4,7 × 4,8, Ø ≤ 22)
  USB-C: https://www.usb.org/sites/default/files/USB%20Type-C%20Spec%20R2.0%20-%20August%202019.pdf
    · https://electronics.stackexchange.com/questions/475901/what-are-the-max-overmold-dimensions-for-usb-c-plugs
      (sobremoldagem ≤ 12,35 × 6,5 mm) · https://www.accesscomms.com.au/usb-connector-dimensions (abertura 8,34 × 2,56,
      inserção ≈ 6,65 mm)
  silicone (Ø exterior): https://www.amazon.com/BNTECHGO-Silicone-Flexible-Strands-Stranded/dp/B017TGYW3S (10 AWG 5,5 mm)
    · https://bntechgo.com/bntechgo-14-gauge-silicone-wire-kit-ultra-flexible-200-ft-black-and-red-each-color-100-ft-high-temp-200-c-600v-14-awg-silicone-wire-400-strands-of-tinned-copper-wire-stranded-wire-stranded-wire-for-model-battery
      (14 AWG 3,5 mm) · https://vxb.com/products/16-gauge-silicone-wire-dual-color-spool-red-and-bl (16 AWG 3,0 mm)
    · https://bntechgo.com/bntechgo-20-gauge-silicone-wire-kit-ultra-flexible-6-colors-each-100-ft-high-temp-200-c-600v-20-awg-silicone-wire-100-strands-of-tinned-copper-wire-stranded-wire-for-model-battery
      (20 AWG 1,8 mm)
  ESC T-Motor: https://store.tmotor.com/product/air-40a-6s-esc.html (AIR 40A: cabo de sinal em par entrançado)
    · https://www.ligpower.com/product/alpha-40a-6s-esc.html (alimentação: silicone vermelho/preto 14 AWG 150 mm)
    · https://store.tmotor.com/product/v40a-bldc-foc-drone-esc-14s-60v.html (motor: silicone laranja-escuro 16 AWG 65 mm)
  XT90: https://maxamps.com/products/xt90-male-connector (31 × 21 × 10 mm) · https://www.tme.com/us/en-us/details/xt90s-f/dc-power-connectors/amass (10 AWG)
  Raspberry Pi 5: https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-mechanical-drawing.pdf (85 × 56, furos 3,5/49)
    · https://www.raspberrypi.com/documentation/accessories/camera.html (CAM/DISP na borda dos micro-HDMI, até à Ethernet)
    · https://www.pishop.us/product/raspberry-pi-camera-cable-standard-mini-200mm-v2 (22 vias 0,5 mm ↔ 15 vias 1 mm)
    · https://www.kadidisplay.com/blog-news/15-pin-vs-22-pin-raspberry-pi-dsi-connectors-cable-pinout-and-compatibility (11,5 mm)
    · https://raspberry.tips/en/raspberry-pi-gpio-pinout (pinos 2/4 5 V, 6 GND, 8 TXD, 10 RXD)
  JST-GH 1,25 mm (portas Pixhawk): https://docs.px4.io/main/en/flight_controller/amovlab_flycore
  sensores e atuadores do build acessível (fichas técnicas dos fabricantes, citadas pelo nome): ams AS5048A (SPI:
    CSn, CLK, MISO, MOSI + VDD/GND → 6 vias), ams AS5600 (I²C: SDA, SCL + VDD/GND → 4 vias), TI DRV8871 (bornes OUT1/
    OUT2 do motor), servo DS3218MG (cabo castanho/vermelho/laranja, o padrão JR); JGB37-520 com encoder Hall: ficha PH2.0
    de 6 vias (motor ±, encoder VCC/GND/A/B) segundo as listagens dos vendedores — as CORES são «estimado»
  DYNAMIXEL: https://docs.robotis.com/docs/dxl/model_reference/x_series/xh_series/xh430-w350 (RS-485: JST EHR-04, GND/VDD/D+/D−)
    · https://docs.robotis.com/docs/parts/interface/dxl_bridge (21 AWG) · https://robotis.us/products/dynamixel-xh430-v210-r
      (traz o «Robot Cable-X4P 180 mm») · https://uk.rs-online.com/web/p/wire-housings-plugs/3116221 (EHR-4: 12 × 3,8 mm)
"""
from __future__ import annotations

import itertools
import math
import os
import re
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from typing import ClassVar

import mujoco
import numpy as np

_G = mujoco.mjtGeom
_PRIMITIVAS = {int(_G.mjGEOM_BOX), int(_G.mjGEOM_CAPSULE), int(_G.mjGEOM_CYLINDER), int(_G.mjGEOM_SPHERE),
               int(_G.mjGEOM_ELLIPSOID)}
MM = 0.001
EZ = np.array([0.0, 0.0, 1.0])

# ------------------------------------------------------------------ bitolas (Ø exterior, m) e medidas
D_BAT = 0.0055          # 10 AWG
D_ESC = 0.0035          # 14 AWG
D_FASE = 0.0030         # 16 AWG
D_18 = 0.0023           # 18 AWG (alimentação do regulador de 24 V)
D_20 = 0.0018           # 20 AWG (5 V do Raspberry Pi)
D_SINAL = 0.0008        # cada fio do par entrançado do sinal do ESC
D_JST = 0.0009          # 28 AWG (JST-GH)
D_DUPONT = 0.0012       # 26 AWG (fios Dupont)
D_DXL = 0.0032          # cabo DYNAMIXEL X4P (4 × 21 AWG torcidos)
D_SERVO = 0.0012        # cada fio do cabo de servo (22 AWG em PVC; 3 entrançados: envolvente Ø ≈ 2,6 mm)
D_CABO_SERVO = 0.0026   # o cabo do servo (os 3 entrançados) — o envolvente
D_28 = 0.0009           # 28 AWG (sinais PWM do servo-rail ao FC)
D_PWM = 0.0026          # os 5 × 28 AWG (4 PWM + GND) do servo-rail ao FC numa manga termo-retráctil
D_MANGA = 0.0080        # manga entrançada das 3 fases (articulado)
D_FEIXE = 0.0090        # manga do feixe do ombro (articulado)
L_RABICHO = 0.065       # «motor cable» de fábrica dos ESC T-Motor (65 mm)
PASSO_PAR = 0.020       # passo do par entrançado do sinal (cabos de acelerador: ~2 cm por volta)
LADOS_PAR = 6           # cada fio do par entrançado: hexágono (com 5 lados as abraçadeiras ficavam a 0,34 mm: A1) …
ANEIS_VOLTA_PAR = 5.0   # … com 5 anéis por volta (orçamento de faces; à distância do cockpit não se distingue)


def _lados_tubo(d: float) -> int:
    """Lados do tubo de um cabo de Ø d (orçamento de faces: ≤ 650 000 no articulado acessível, com os 2 Pico; as
    abraçadeiras continuam presas — auditoria A1 — nos 3 builds principais)."""
    return 5 if d < 0.0011 else 6 if d < 0.0026 else 8 if d < 0.0045 else 10
XT90_MACHO = (0.019, 0.020, 0.010)          # parte do macho fora da fêmea: comprimento × largura × altura
FPC_LARG_RPI, FPC_LARG_CAM, FPC_ESP = 0.0115, 0.016, 0.0003
FOLGA_PILHA = 0.0021    # cabos que sobem ao lado da RPi: centro a 2,1 mm da borda (a janela da placa de cima dá 4 mm)
# XH430 da estrutura (para achar as fichas dos servos que ela desenha): largura, altura, profundidade, horn ao topo
SERVO_W, SERVO_H, SERVO_D, HORN_TOPO = 0.0285, 0.0465, 0.034, 0.013
# ficha USB-C (norma USB Type-C R2.0): casca 8,25 × 2,40 metida 6,65 mm; sobremoldagem (corpo a 90°) 12,0 × 6,5 × 9,0
USBC_CASCA = (0.00825, 0.0024)
USBC_METIDA = 0.00665
USBC_VISTA = 0.0004                         # casca à vista entre a face do recetáculo e o corpo
USBC_CORPO = (0.0120, 0.0065, 0.0090)       # largura × espessura × comprimento (ao longo do eixo de encaixe)
USBC_MANGA = 0.0045                         # manga de alívio (saída lateral) — comprimento
D_SOLDA = 0.0022                            # cordão de solda na ponta de um fio 20 AWG numa ilha


@dataclass(frozen=True)
class _Ficha:
    """Abraçadeira de nylon 66 (medidas da ficha do fabricante, m)."""

    modelo: str
    comp_mm: float
    larg: float
    esp: float
    feixe_max: float
    cab_comp: float          # cabeça: ao longo da fita
    cab_larg: float          # cabeça: ao longo do feixe
    cab_alt: float           # cabeça: para fora do feixe


FICHAS = (_Ficha("T18R", 100.0, 0.0025, 0.0010, 0.022, 0.0048, 0.00445, 0.0037),
          _Ficha("T30R", 150.0, 0.0035, 0.0011, 0.035, 0.0055, 0.0060, 0.0045),
          _Ficha("T18L", 205.0, 0.0025, 0.0012, 0.050, 0.0048, 0.0045, 0.0035))
PONTA_ABRAC = 0.0013        # ponta cortada que fica a sair da cabeça (corte rente)
FOLGA_ABRAC = 0.00003       # face de dentro da fita → feixe

_MATERIAIS = {
    "fios_vermelho": {"rgba": [0.80, 0.06, 0.05, 1.0], "specular": 0.35, "shininess": 0.5},
    "fios_preto": {"rgba": [0.05, 0.05, 0.055, 1.0], "specular": 0.35, "shininess": 0.5},
    "fios_laranja": {"rgba": [0.95, 0.40, 0.05, 1.0], "specular": 0.35, "shininess": 0.5},     # «deep orange» T-Motor
    "fios_branco": {"rgba": [0.90, 0.90, 0.88, 1.0], "specular": 0.3, "shininess": 0.4},
    "fios_amarelo": {"rgba": [0.95, 0.80, 0.10, 1.0], "specular": 0.3, "shininess": 0.4},
    "fios_verde": {"rgba": [0.10, 0.62, 0.25, 1.0], "specular": 0.3, "shininess": 0.4},
    "fios_azul": {"rgba": [0.12, 0.35, 0.85, 1.0], "specular": 0.3, "shininess": 0.4},
    "fios_nylon": {"rgba": [0.07, 0.07, 0.075, 1.0], "specular": 0.55, "shininess": 0.7},      # abraçadeiras PA66 preto
    "fios_termo": {"rgba": [0.03, 0.03, 0.035, 1.0], "specular": 0.15, "shininess": 0.25},     # termo-retráctil
    "fios_manga": {"rgba": [0.17, 0.17, 0.19, 1.0], "specular": 0.6, "shininess": 0.8},        # manga entrançada PET
    "fios_xt90": {"rgba": [0.96, 0.74, 0.05, 1.0], "specular": 0.45, "shininess": 0.6},
    "fios_ouro": {"rgba": [0.86, 0.68, 0.25, 1.0], "specular": 0.8, "shininess": 0.8},
    "fios_fpc": {"rgba": [0.94, 0.92, 0.86, 1.0], "specular": 0.25, "shininess": 0.3},         # FPC branco
    "fios_jst": {"rgba": [0.93, 0.90, 0.81, 1.0], "specular": 0.3, "shininess": 0.4},          # nylon natural JST
    "fios_dupont": {"rgba": [0.06, 0.06, 0.065, 1.0], "specular": 0.4, "shininess": 0.5},
    "fios_dxl": {"rgba": [0.11, 0.11, 0.12, 1.0], "specular": 0.4, "shininess": 0.5},
    "fios_castanho": {"rgba": [0.36, 0.20, 0.10, 1.0], "specular": 0.3, "shininess": 0.4},     # GND do cabo de servo
    "fios_aco": {"rgba": [0.72, 0.73, 0.75, 1.0], "specular": 0.8, "shininess": 0.8},          # casca niquelada
    "fios_sobremolde": {"rgba": [0.045, 0.045, 0.05, 1.0], "specular": 0.18, "shininess": 0.3},  # PVC/TPE da ficha
    "fios_estanho": {"rgba": [0.70, 0.70, 0.68, 1.0], "specular": 0.75, "shininess": 0.7},     # solda Sn-Ag-Cu
}

# peças que NÃO são a superfície de um braço/mastro (os cabos não sobem para cima delas)
_NAO_SUPERFICIE = re.compile(r"^(fios_|esc|el_|motor|perna|helice|servo|sem_fim|rpi5|camera|bateria|cinta|sensores|"
                             r"arma|conector|dobradica|corneta|marca_|garfo|projetil|caminho_tiro)", re.IGNORECASE)
_SO_FIOS = re.compile(r"^(fios_|helice|caminho_tiro|projetil)", re.IGNORECASE)
_SO_FIOS_ARMA = re.compile(r"^(fios_|helice|caminho_tiro|projetil|arma)", re.IGNORECASE)
_NADA = re.compile(r"(?!x)x")            # nenhum geom (abraçadeiras que só abraçam cabos)


# ====================================================================================== geometria
def _cruz(a, b) -> np.ndarray:
    """Produto externo de vetores 3D (com difusão): as MESMAS operações que `np.cross` (resultado igual bit a bit),
    sem o custo fixo dela — os raios-triângulo chamam-no milhares de vezes por montagem."""
    a0, a1, a2 = a[..., 0], a[..., 1], a[..., 2]
    b0, b1, b2 = b[..., 0], b[..., 1], b[..., 2]
    return np.stack((a1 * b2 - a2 * b1, a2 * b0 - a0 * b2, a0 * b1 - a1 * b0), axis=-1)


def _u(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _rot_z(z) -> np.ndarray:
    z = _u(z)
    a = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x = _u(np.cross(a, z))
    return np.column_stack([x, np.cross(z, x), z])


def _base(ex, ez) -> np.ndarray:
    """Matriz (colunas = eixos) com x = ex e z o mais perto possível de ez."""
    ex = _u(ex)
    ez = np.asarray(ez, dtype=float) - float(np.dot(ez, ex)) * ex
    if float(np.linalg.norm(ez)) < 1e-9:
        ez = np.cross(ex, EZ) if abs(ex[2]) < 0.9 else np.cross(ex, [1.0, 0.0, 0.0])
    ez = _u(ez)
    return np.column_stack([ex, np.cross(ez, ex), ez])


def _mat_quat(q) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    q = q / max(float(np.linalg.norm(q)), 1e-12)
    r = np.zeros(9)
    mujoco.mju_quat2Mat(r, q)
    return r.reshape(3, 3)


def _pose(g):
    """(tipo, pos, R 3×3, size) de um geom do spec no referencial do corpo dele — resolve o `fromto`."""
    t = int(g.type)
    size = np.array(g.size, dtype=float)
    ft = np.array(g.fromto, dtype=float)
    if (not np.isnan(ft[0]) and float(np.linalg.norm(ft[3:] - ft[:3])) > 1e-9
            and t in (int(_G.mjGEOM_CAPSULE), int(_G.mjGEOM_CYLINDER), int(_G.mjGEOM_BOX), int(_G.mjGEOM_ELLIPSOID))):
        a, b = ft[:3], ft[3:]
        meio = 0.5 * float(np.linalg.norm(b - a))
        size = (np.array([size[0], meio, 0.0]) if t in (int(_G.mjGEOM_CAPSULE), int(_G.mjGEOM_CYLINDER))
                else np.array([size[0], size[1], meio]))
        return t, 0.5 * (a + b), _rot_z(b - a), size
    return t, np.array(g.pos, dtype=float), _mat_quat(g.quat), size


def _aabb(g):
    """Caixa alinhada (lo, hi) de um geom primitivo no referencial do corpo dele (None para malhas/planos)."""
    t, pos, r, s = _pose(g)
    if t in (int(_G.mjGEOM_BOX), int(_G.mjGEOM_ELLIPSOID)):
        h = s
    elif t == int(_G.mjGEOM_SPHERE):
        h = np.array([s[0]] * 3)
    elif t == int(_G.mjGEOM_CAPSULE):
        h = np.array([s[0], s[0], s[1] + s[0]])
    elif t == int(_G.mjGEOM_CYLINDER):
        h = np.array([s[0], s[0], s[1]])
    else:
        return None
    ext = np.abs(r) @ h
    return pos - ext, pos + ext


def _visivel(g) -> bool:
    """Peça que se VÊ (grupos 0/3; alfa 0 = escondida ou variante inativa da troca ao vivo — o MuJoCo não a desenha)."""
    if int(g.group) not in (0, 3):          # 1/2 = hélices e efeitos (rodam/piscam), 4/5 = escondidos
        return False
    return float(g.rgba[3]) > 0.0


def _sem_repetidos(pts, tol: float = 1e-6) -> list:
    out = []
    for p in pts:
        p = np.asarray(p, dtype=float)
        if not out or float(np.linalg.norm(p - out[-1])) > tol:
            out.append(p)
    return out


def _curva(pts, raio: float = 0.006, n: int = 6, ang_min: float = 0.05) -> list:
    """Polilinha com os cantos arredondados (Bézier quadrática com `n` pontos em cada vértice de viragem > ang_min rad)."""
    pts = _sem_repetidos(pts)
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, p, b = out[-1], pts[i], pts[i + 1]
        la, lb = float(np.linalg.norm(p - a)), float(np.linalg.norm(b - p))
        if la < 1e-7 or lb < 1e-7:
            continue
        ua, ub = (p - a) / la, (b - p) / lb
        if math.acos(max(-1.0, min(1.0, float(np.dot(ua, ub))))) < ang_min:
            out.append(p)
            continue
        d = min(raio, 0.45 * la, 0.45 * lb)
        pa, pb = p - d * ua, p + d * ub
        ang = math.acos(max(-1.0, min(1.0, float(np.dot(ua, ub)))))
        nj = max(1, min(n, math.ceil(ang / (math.pi / 12.0))))        # ~1 ponto por cada 15° de viragem
        out.append(pa)
        for j in range(1, nj + 1):
            t = j / (nj + 1)
            out.append((1 - t) ** 2 * pa + 2 * (1 - t) * t * p + t ** 2 * pb)
        out.append(pb)
    out.append(pts[-1])
    return out


def _simplificar(pts, tol: float = 0.0004) -> list:
    """Douglas–Peucker: tira os pontos que se afastam < tol da corda (um tubo liso dá um só troço)."""
    pts = _sem_repetidos(pts)
    if len(pts) < 3:
        return pts
    p = np.asarray(pts, dtype=float)
    manter = np.zeros(len(p), dtype=bool)
    manter[0] = manter[-1] = True
    pilha = [(0, len(p) - 1)]
    while pilha:
        i0, i1 = pilha.pop()
        if i1 - i0 < 2:
            continue
        a, ab = p[i0], p[i1] - p[i0]
        lab = float(np.linalg.norm(ab))
        q = p[i0 + 1:i1] - a
        dist = (np.linalg.norm(_cruz(q, ab), axis=1) / lab) if lab > 1e-12 else np.linalg.norm(q, axis=1)
        j = int(np.argmax(dist))
        if dist[j] > tol:
            manter[i0 + 1 + j] = True
            pilha += [(i0, i0 + 1 + j), (i0 + 1 + j, i1)]
    return [p[i] for i in np.flatnonzero(manter)]


def _reamostrar(pts, passo: float) -> list:
    pts = _sem_repetidos(pts)
    if len(pts) < 2:
        return pts
    out = [pts[0]]
    for a, b in itertools.pairwise(pts):
        m = max(1, math.ceil(float(np.linalg.norm(b - a)) / passo))
        out += [a + (b - a) * j / m for j in range(1, m + 1)]
    return out


def _quadros(pts, n0=None):
    """Tangentes e normais por transporte paralelo (sem torção) ao longo da polilinha (`n0` = normal inicial)."""
    p = np.asarray(pts, dtype=float)
    n = len(p)
    seg = np.diff(p, axis=0)
    seg = seg / np.maximum(np.linalg.norm(seg, axis=1, keepdims=True), 1e-12)
    t = np.zeros((n, 3))
    t[0], t[-1] = seg[0], seg[-1]
    if n > 2:
        t[1:-1] = seg[:-1] + seg[1:]
        fraco = np.linalg.norm(t[1:-1], axis=1) < 1e-9
        t[1:-1][fraco] = seg[1:][fraco]
    t = t / np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    a = (EZ if abs(t[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])) if n0 is None else np.asarray(n0, dtype=float)
    nn = np.zeros((n, 3))
    v = a - float(a @ t[0]) * t[0]
    nn[0] = v / np.linalg.norm(v)
    for i in range(1, n):
        v = nn[i - 1] - float(nn[i - 1] @ t[i]) * t[i]
        nv = float(np.sqrt(v @ v))
        nn[i] = v / nv if nv > 1e-9 else nn[i - 1]
    return t, nn, _cruz(t, nn)


def _casca(pontos2d) -> np.ndarray:
    """Invólucro convexo (cadeia monótona de Andrew), no sentido anti-horário."""
    pts = sorted({(round(float(x), 7), round(float(y), 7)) for x, y in pontos2d})
    if len(pts) < 3:
        return np.array(pts)

    def cruz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    baixo, cima = [], []
    for p in pts:
        while len(baixo) >= 2 and cruz(baixo[-2], baixo[-1], p) <= 0:
            baixo.pop()
        baixo.append(p)
    for p in reversed(pts):
        while len(cima) >= 2 and cruz(cima[-2], cima[-1], p) <= 0:
            cima.pop()
        cima.append(p)
    return np.array(baixo[:-1] + cima[:-1])


def _limpar_casca(h: np.ndarray, tol: float = 2e-5) -> np.ndarray:
    """Tira vértices quase colineares/coincidentes do invólucro (arestas < tol)."""
    out = []
    for p in h:
        if not out or float(np.linalg.norm(p - out[-1])) > tol:
            out.append(p)
    if len(out) > 2 and float(np.linalg.norm(out[0] - out[-1])) <= tol:
        out.pop()
    return np.array(out)


def _offset_convexo(h: np.ndarray, d: float, passo: float = math.radians(18.0)) -> np.ndarray:
    """Contorno de um polígono convexo CCW deslocado `d` para fora (soma de Minkowski com um disco): arestas paralelas
    e arcos de raio d nos vértices — o caminho do eixo da fita à volta do feixe."""
    n = len(h)
    out = []
    for i in range(n):
        a, p, b = h[i - 1], h[i], h[(i + 1) % n]
        e1, e2 = _u(p - a), _u(b - p)
        n1 = np.array([e1[1], -e1[0]])            # normais exteriores das arestas de entrada e de saída (CCW)
        n2 = np.array([e2[1], -e2[0]])
        a1, a2 = math.atan2(n1[1], n1[0]), math.atan2(n2[1], n2[0])
        da = (a2 - a1) % (2.0 * math.pi)
        if da > math.pi:                          # quase colinear com ruído: sem arco
            da = 0.0
        k = max(1, math.ceil(da / passo)) if da > 1e-6 else 0
        for j in range(k + 1):
            ang = a1 + da * j / max(k, 1)
            out.append(p + d * np.array([math.cos(ang), math.sin(ang)]))
    return np.array(out)


def _dist_poligono(q, h: np.ndarray) -> float:
    """Distância (com sinal: > 0 fora) de q ao polígono convexo CCW h."""
    q = np.asarray(q, dtype=float)
    h = np.asarray(h, dtype=float)
    n = len(h)
    if n < 3:
        return float(min(np.linalg.norm(q - p) for p in h)) if n else math.inf
    a, b = h, np.roll(h, -1, axis=0)
    e = b - a
    L2 = np.einsum("ij,ij->i", e, e)
    ok = L2 > 1e-24
    a, e, L2 = a[ok], e[ok], L2[ok]
    nrm = np.column_stack([e[:, 1], -e[:, 0]]) / np.sqrt(L2)[:, None]
    sd = np.einsum("ij,ij->i", q - a, nrm)
    if np.all(sd <= 0.0):
        return float(sd.max())
    t = np.clip(np.einsum("ij,ij->i", q - a, e) / L2, 0.0, 1.0)
    return float(np.min(np.linalg.norm(q - (a + t[:, None] * e), axis=1)))


# ====================================================================================== malhas por corpo × material
class _Malhas:
    """Tubos, fitas e prismas acumulados por (corpo, material) e emitidos no fim como UMA malha (geom) por lote, com o
    intervalo de faces de cada PEÇA (`with malhas.peca(id, k):`) registado; os tubos ficam também numa lista (polilinha,
    raio, peça) — a secção das abraçadeiras e a auditoria usam-na."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.lotes: dict[tuple[str, str], list] = {}
        self.tag = ("cablagem", 0)
        self.cabos: list[dict] = []

    @contextmanager
    def peca(self, peca: str, inst: int = 0):
        anterior = self.tag
        self.tag = (str(peca), int(inst))
        try:
            yield
        finally:
            self.tag = anterior

    def _juntar(self, corpo: str, mat: str, v, f) -> None:
        self.lotes.setdefault((corpo, mat), []).append((self.tag, np.asarray(v, dtype=float),
                                                        np.asarray(f, dtype=np.int64)))

    def _varrer(self, corpo, mat, aneis, tampas=True, fechada=False, apices=None):
        """Faces entre anéis (cada anel com m pontos à volta da tangente) + tampas; normais para fora."""
        nr, m = len(aneis), len(aneis[0])
        f = []
        for i in range(nr - (0 if fechada else 1)):
            i2 = (i + 1) % nr
            for j in range(m):
                j2 = (j + 1) % m
                a, b, c, d = i * m + j, i * m + j2, i2 * m + j, i2 * m + j2
                f += [(a, b, c), (b, d, c)]
        verts = np.vstack([np.asarray(a, dtype=float) for a in aneis])
        if tampas and not fechada:
            ini, fim = apices if apices is not None else (np.mean(aneis[0], axis=0), np.mean(aneis[-1], axis=0))
            k0 = len(verts)
            verts = np.vstack([verts, ini, fim])
            for j in range(m):
                j2 = (j + 1) % m
                f.append((k0, j2, j))
                f.append((k0 + 1, (nr - 1) * m + j, (nr - 1) * m + j2))
        self._juntar(corpo, mat, verts, f)

    def tubo(self, corpo: str, mat: str, pts, d: float, lados: int | None = None, cabo: bool = True,
             ident: str = "", simplificar: bool = True) -> None:
        """Cabo redondo de Ø d ao longo dos pontos (já suaves), com as pontas abauladas."""
        pts = _simplificar(pts, min(0.00015, 0.08 * d)) if simplificar else _sem_repetidos(pts)
        if len(pts) < 2:
            return
        r = 0.5 * d
        # lados por Ø (`_lados_tubo`): os fios finos (≤ 2,6 mm) são hexágonos/pentágonos — à distância do cockpit não se
        # distinguem de um círculo (os 6 fios da fita do JGB37-520, colados lado a lado, são quadrados)
        m = lados or _lados_tubo(d)
        t, nn, bb = _quadros(pts)
        ang = np.linspace(0.0, 2.0 * math.pi, m, endpoint=False)
        cs, sn = np.cos(ang)[:, None], np.sin(ang)[:, None]
        p = np.asarray(pts, dtype=float)
        aneis = [p[0] - 0.62 * r * t[0] + 0.78 * r * (cs * nn[0] + sn * bb[0])]
        aneis += [p[i] + r * (cs * nn[i] + sn * bb[i]) for i in range(len(p))]
        aneis += [p[-1] + 0.62 * r * t[-1] + 0.78 * r * (cs * nn[-1] + sn * bb[-1])]
        self._varrer(corpo, mat, aneis, apices=(p[0] - r * t[0], p[-1] + r * t[-1]))
        if cabo:
            n_id = sum(1 for c in self.cabos if c["peca"] == self.tag[0] and c["inst"] == self.tag[1])
            self.cabos.append({"id": ident or f"{self.tag[0]}{self.tag[1]}_{mat.removeprefix('fios_')}_{n_id}",
                               "corpo": corpo.split("@")[0], "pts": p.copy(), "r": r, "peca": self.tag[0],
                               "inst": self.tag[1], "material": mat, "aneis": np.array(aneis[1:-1]),
                               "grupo": corpo.split("@")[1] if "@" in corpo else None})

    def par(self, corpo: str, mat_a: str, mat_b: str, pts, d: float, passo: float = PASSO_PAR, ident: str = "") -> None:
        """Par ENTRANÇADO (dois fios de Ø d em hélice um à volta do outro) ao longo dos pontos."""
        pts = _reamostrar(_simplificar(pts, 0.0002), passo / ANEIS_VOLTA_PAR)   # (a hélice tem 0,4 mm de raio)
        if len(pts) < 2:
            return
        _t, nn, bb = _quadros(pts)
        s = np.concatenate([[0.0], np.cumsum([np.linalg.norm(b - a) for a, b in itertools.pairwise(pts)])])
        fi = 2.0 * math.pi * s / passo
        p = np.asarray(pts, dtype=float)
        h = (np.cos(fi)[:, None] * nn + np.sin(fi)[:, None] * bb) * (0.5 * d)
        self.tubo(corpo, mat_a, p + h, d, lados=LADOS_PAR, ident=f"{ident}_a" if ident else "", simplificar=False)
        self.tubo(corpo, mat_b, p - h, d, lados=LADOS_PAR, ident=f"{ident}_b" if ident else "", simplificar=False)

    def tres(self, corpo: str, mats, pts, d: float, passo: float = 0.024, ident: str = "") -> None:
        """3 fios de Ø d ENTRANÇADOS (triângulo de raio d/√3 a rodar) ao longo dos pontos — o cabo de um servo."""
        pts = _reamostrar(_simplificar(pts, 0.0002), passo / 9.0)
        if len(pts) < 2:
            return
        _t, nn, bb = _quadros(pts)
        s_ = np.concatenate([[0.0], np.cumsum([np.linalg.norm(b - a) for a, b in itertools.pairwise(pts)])])
        p = np.asarray(pts, dtype=float)
        rho = d / math.sqrt(3.0) + 0.0001             # (0,17 mm entre fios: nas curvas não se encavalitam)
        for i, mat in enumerate(mats):
            fi = 2.0 * math.pi * s_ / passo + 2.0 * math.pi * i / 3.0
            h = (np.cos(fi)[:, None] * nn + np.sin(fi)[:, None] * bb) * rho
            self.tubo(corpo, mat, p + h, d, lados=5, ident=f"{ident}_{i}" if ident else "", simplificar=False)

    def paralelos(self, corpo: str, mats, pts, d: float, n0, sep: float | None = None, ident: str = "",
                  torcao=None) -> list:
        """Fios de Ø d LADO A LADO (encostados) ao longo da polilinha: o i-ésimo afastado (i − (n−1)/2)·sep da linha
        central na normal transportada (`n0` = direção do afastamento no 1.º ponto), rodada de `torcao(s)` rad (s = o
        comprimento ao longo da linha) — o par vai rodando sobre si. Devolve as polilinhas."""
        pts = _sem_repetidos(pts)
        if len(pts) < 2:
            return []
        sep = d + 0.00005 if sep is None else sep
        _t, nn, bb = _quadros(pts, n0=n0)
        if torcao is not None:
            sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.asarray(pts), axis=0), axis=1))])
            ang = np.array([float(torcao(x)) for x in sl])
            nn = np.cos(ang)[:, None] * nn + np.sin(ang)[:, None] * bb
        p = np.asarray(pts, dtype=float)
        k = len(mats)
        out = []
        for i, mat in enumerate(mats):
            q = p + nn * ((i - 0.5 * (k - 1)) * sep)
            self.tubo(corpo, mat, q, d, ident=f"{ident}_{i}" if ident else "")
            out.append(q)
        return out

    def fita(self, corpo: str, mat: str, pts, larg, w_dir, esp: float, fechada: bool = False) -> None:
        """Perfil retangular (FPC, abraçadeira): `larg`/`w_dir` = largura e direção da largura (escalares ou por ponto;
        a direção é ortogonalizada à tangente)."""
        p0 = np.asarray(pts, dtype=float)
        n0 = len(p0)
        larg = np.broadcast_to(np.asarray(larg, dtype=float), (n0,))
        w_dir = np.asarray(w_dir, dtype=float)
        w_dir = np.broadcast_to(w_dir, (n0, 3)) if w_dir.ndim == 1 else w_dir
        manter = [0] + [i for i in range(1, n0) if float(np.linalg.norm(p0[i] - p0[i - 1])) > 1e-6]
        if fechada and len(manter) > 2 and float(np.linalg.norm(p0[manter[0]] - p0[manter[-1]])) < 1e-7:
            manter = manter[:-1]
        if len(manter) < 2:
            return
        p, larg, w_dir = p0[manter], larg[manter], w_dir[manter]
        n = len(p)
        aneis = []
        for i in range(n):
            a, b = (p[(i - 1) % n], p[(i + 1) % n]) if fechada else (p[max(i - 1, 0)], p[min(i + 1, n - 1)])
            t = _u(b - a)
            w = _u(w_dir[i] - float(np.dot(w_dir[i], t)) * t)
            nz = np.cross(t, w)
            hw, he = 0.5 * larg[i], 0.5 * esp
            aneis.append(np.array([p[i] + hw * w + he * nz, p[i] - hw * w + he * nz, p[i] - hw * w - he * nz,
                                   p[i] + hw * w - he * nz]))
        self._varrer(corpo, mat, aneis, tampas=not fechada, fechada=fechada)

    def caixa(self, corpo: str, mat: str, c, r, h) -> None:
        """Prisma retangular de centro c, eixos = colunas de r e meias-medidas h."""
        c, r, h = np.asarray(c, dtype=float), np.asarray(r, dtype=float), np.asarray(h, dtype=float)
        if float(np.linalg.det(r)) < 0.0:
            r = r.copy()
            r[:, 2] *= -1.0
        v = [c + r @ (np.array([(i & 1) * 2 - 1, ((i >> 1) & 1) * 2 - 1, ((i >> 2) & 1) * 2 - 1]) * h) for i in range(8)]
        f = [(0, 4, 6), (0, 6, 2), (1, 3, 7), (1, 7, 5), (0, 1, 5), (0, 5, 4), (2, 6, 7), (2, 7, 3), (0, 2, 3),
             (0, 3, 1), (4, 5, 7), (4, 7, 6)]
        self._juntar(corpo, mat, v, f)

    def prisma(self, corpo: str, mat: str, perfis, centros, eu, ev) -> None:
        """Sólido entre perfis 2D CONVEXOS (CCW no plano (eu, ev)) colocados nos `centros` (≥ 2, ao longo de um eixo):
        casca de ficha, corpo sobremoldado, manga de alívio cónica."""
        eu, ev = _u(eu), _u(ev)
        aneis = [np.asarray(c, dtype=float) + np.outer(np.asarray(p, dtype=float)[:, 0], eu)
                 + np.outer(np.asarray(p, dtype=float)[:, 1], ev) for p, c in zip(perfis, centros, strict=True)]
        eixo = np.asarray(centros[-1], dtype=float) - np.asarray(centros[0], dtype=float)
        if float(np.dot(np.cross(eu, ev), eixo)) < 0.0:          # o anel tem de rodar à volta do eixo (normais p/ fora)
            aneis = [a[::-1] for a in aneis]
        self._varrer(corpo, mat, aneis, apices=(np.mean(aneis[0], axis=0), np.mean(aneis[-1], axis=0)))

    def criar(self) -> int:
        n = 0
        for (corpo, mat), pedacos in self.lotes.items():
            if not pedacos:
                continue
            pedacos = sorted(pedacos, key=lambda x: x[0])
            vs, fs, faixas = [], [], []
            nv = nf = 0
            for tag, v, f in pedacos:
                vs.append(v)
                fs.append(f + nv)
                if faixas and faixas[-1][0] == tag[0] and faixas[-1][1] == tag[1] and faixas[-1][3] == nf:
                    faixas[-1] = (tag[0], tag[1], faixas[-1][2], nf + len(f))
                else:
                    faixas.append((tag[0], tag[1], nf, nf + len(f)))
                nv += len(v)
                nf += len(f)
            if "@" in corpo:
                # troço que RODA com um grupo animado da planta (p. ex. o corpo do atuador do ombro de fuso): o geom
                # chama-se pelo prefixo do grupo (a planta roda os geoms `<grupo>*`) e fica no corpo real
                corpo_real, grupo = corpo.split("@", 1)
                nome = f"{grupo}_fios_{mat.removeprefix('fios_')}"
            else:
                corpo_real, nome = corpo, f"fios_{corpo}_{mat.removeprefix('fios_')}"
            me = self.ctx.spec.add_mesh(name=f"m_{nome}")
            me.uservert = np.vstack(vs).ravel().tolist()
            me.userface = np.vstack(fs).ravel().tolist()
            me.inertia = mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL
            self.ctx.geom(corpo_real, nome, type=_G.mjGEOM_MESH, meshname=me.name, material=mat)
            self.ctx.registar_faixas(nome, faixas)
            n += 1
        notas = self.ctx.registo.notas
        notas["fios_cabos"] = [{"id": c["id"], "corpo": c["corpo"], "d": round(2.0 * c["r"], 6), "peca": c["peca"],
                                "inst": c["inst"], "material": c["material"],
                                "pts": [[round(float(x), 7) for x in q] for q in c["pts"]],
                                **({"grupo": c["grupo"]} if c.get("grupo") else {})} for c in self.cabos]
        return n


# ====================================================================================== sonda (raios)
@dataclass
class _Caixa:
    corpo: str
    lo: np.ndarray
    hi: np.ndarray

    @property
    def c(self) -> np.ndarray:
        return 0.5 * (self.lo + self.hi)

    @property
    def h(self) -> np.ndarray:
        return 0.5 * (self.hi - self.lo)

    def extensao(self, d) -> float:
        return float(np.abs(np.asarray(d, dtype=float)) @ self.h)

    def topo(self) -> np.ndarray:
        return np.array([self.c[0], self.c[1], self.hi[2]])

    def contem(self, q, tol: float = 1e-6) -> bool:
        q = np.asarray(q, dtype=float)
        return bool(np.all(q >= self.lo - tol) and np.all(q <= self.hi + tol))


class _GrelhaTri:
    """Triângulos de um corpo (referencial do corpo) com DUAS grelhas 3D para consultas por caixa: a fina (10 mm) para
    os triângulos pequenos e a grossa (60 mm) para os grandes (placas, invólucros); os enormes ficam à parte. Em 3D (e
    não só em xy) para que a pilha (placas, PCB, bateria, arma umas por cima das outras) não dê candidatos de outras
    alturas: o resultado é o mesmo (o filtro final por caixa não muda), só mais depressa."""

    CEL = 0.010
    CEL_G = 0.060
    _B = 8192                       # base das chaves (índices de célula em [−4096, 4096): ±41 m a 10 mm)

    @classmethod
    def _chave(cls, ix, iy, iz):
        b, o = cls._B, cls._B // 2
        return ((ix + o) * b + (iy + o)) * b + (iz + o)

    @classmethod
    def _indexar(cls, lo, hi, c, idx_base):
        i0 = np.floor(lo / c).astype(np.int64)
        i1 = np.floor(hi / c).astype(np.int64)
        nx, ny, nz = (i1 - i0 + 1).T
        ncel = nx * ny * nz
        poucas = ncel <= 32
        idx = np.flatnonzero(poucas)
        rep = np.repeat(idx, ncel[idx])
        ini = np.repeat(np.cumsum(ncel[idx]) - ncel[idx], ncel[idx])
        j = np.arange(len(rep)) - ini
        nxr, nyr = nx[rep], ny[rep]
        chave = cls._chave(i0[rep, 0] + j % nxr, i0[rep, 1] + (j // nxr) % nyr, i0[rep, 2] + j // (nxr * nyr))
        ordem = np.argsort(chave, kind="stable")
        return chave[ordem], idx_base[rep[ordem]], idx_base[np.flatnonzero(~poucas)]

    def __init__(self, nomes: list, T: np.ndarray, dono: np.ndarray, cel: float | None = None):
        self.nomes = nomes
        self.T = T
        self.dono = dono
        self.lo, self.hi = T.min(axis=1), T.max(axis=1)
        self.cel = cel or self.CEL
        todos = np.arange(len(T))
        self.chaves, self.idx, grandes = self._indexar(self.lo, self.hi, self.cel, todos)
        self.chaves_g, self.idx_g, self.grandes = self._indexar(self.lo[grandes], self.hi[grandes], self.CEL_G, grandes)

    @classmethod
    def _celulas(cls, chaves, idx, lo, hi, c):
        a0 = np.floor(np.asarray(lo, dtype=float) / c).astype(np.int64)
        a1 = np.floor(np.asarray(hi, dtype=float) / c).astype(np.int64)
        n = a1 - a0 + 1
        if int(n[0]) * int(n[1]) * int(n[2]) > 20000:
            return None
        b, o = cls._B, cls._B // 2
        ks = ((((np.arange(a0[0], a1[0] + 1) + o) * b)[:, None, None] + (np.arange(a0[1], a1[1] + 1) + o)[None, :, None])
              * b + (np.arange(a0[2], a1[2] + 1) + o)[None, None, :]).ravel()
        i0 = np.searchsorted(chaves, ks, side="left")
        i1 = np.searchsorted(chaves, ks, side="right")
        tem = i1 > i0
        return [idx[a:b] for a, b in zip(i0[tem], i1[tem], strict=True)]

    def indices(self, lo, hi, aceita_dono: np.ndarray | None = None) -> np.ndarray:
        """Índices dos triângulos cuja caixa toca na caixa (lo, hi) (e cujo dono é aceite)."""
        finas = self._celulas(self.chaves, self.idx, lo, hi, self.cel)
        grossas = self._celulas(self.chaves_g, self.idx_g, lo, hi, self.CEL_G)
        if finas is None or grossas is None:
            cand = np.arange(len(self.T))
        else:
            partes = [self.grandes, *finas, *grossas]
            cand = np.concatenate(partes) if len(partes) > 1 else self.grandes   # repetidos não fazem mal
        if not len(cand):
            return cand
        ok = np.all(self.hi[cand] >= lo, axis=1) & np.all(self.lo[cand] <= hi, axis=1)
        if aceita_dono is not None:
            ok &= aceita_dono[self.dono[cand]]
        return cand[ok]

    def consulta(self, lo, hi, aceita_dono: np.ndarray):
        idx = self.indices(lo, hi, aceita_dono)
        return self.T[idx] if len(idx) else np.zeros((0, 3, 3))


class _Triangulos:
    """Triângulos das malhas visíveis de cada corpo (no referencial do corpo), calculados uma vez por montagem — com
    as FERRAGENS ainda por fundir dos outros módulos (o coletor partilhado só cria as malhas no fim): os cabos passam
    por cima das cabeças dos parafusos em vez de as atravessar."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.por_corpo: dict[str, _GrelhaTri | None] = {}
        self._malhas = None

    def de(self, corpo: str) -> _GrelhaTri | None:
        if corpo not in self.por_corpo:
            if self._malhas is None:
                self._malhas = {m.name: m for m in self.ctx.spec.meshes}
            nomes, partes, donos = [], [], []
            for g in self.ctx.spec.geoms:
                if (g.parent is None or g.parent.name != corpo or int(g.type) != int(_G.mjGEOM_MESH)
                        or (g.name or "").startswith("fios_") or not _visivel(g)):
                    continue
                me = self._malhas.get(g.meshname)
                if me is None:
                    continue
                v = np.asarray(me.uservert, dtype=float).reshape(-1, 3)
                f = np.asarray(me.userface, dtype=np.int64).reshape(-1, 3)
                if len(v) == 0 or len(f) == 0:
                    continue
                esc = np.asarray(me.scale, dtype=float) if hasattr(me, "scale") else np.ones(3)
                vb = (v * esc) @ _mat_quat(g.quat).T + np.array(g.pos, dtype=float)
                partes.append(vb[f])
                donos.append(np.full(len(f), len(nomes)))
                nomes.append(g.name or "")
            fer = getattr(self.ctx.ferragens, "pecas", None) or []
            for q in fer:
                if q.corpo != corpo or not len(q.f):
                    continue
                partes.append(np.asarray(q.v, dtype=float)[np.asarray(q.f, dtype=np.int64)])
                donos.append(np.full(len(q.f), len(nomes)))
                nomes.append(f"{q.material}_{corpo}")
            self.por_corpo[corpo] = (_GrelhaTri(nomes, np.concatenate(partes), np.concatenate(donos))
                                     if partes else None)
        return self.por_corpo[corpo]

    def lista(self, corpo: str, nome: str) -> np.ndarray:
        """Os triângulos de um geom de malha (pelo nome) deste corpo."""
        gr = self.de(corpo)
        if gr is None or nome not in gr.nomes:
            return np.zeros((0, 3, 3))
        return gr.T[gr.dono == gr.nomes.index(nome)]


class _Sonda:
    """Raios contra as peças VISÍVEIS de um ou mais corpos num referencial comum (juntas a 0: os corpos filhos só estão
    TRANSLADADOS — `corpos` = {nome: origem do corpo}). Primitivas por `mju_rayGeom`; malhas por raio-triângulo
    (Möller–Trumbore vetorizado) sobre a GRELHA de cada corpo (feita uma vez por montagem: criar uma sonda não copia
    triângulos) — `zona` = (lo, hi) corta o que está longe, `teto` ignora os toques de malha acima, `excluir`/`incluir`
    = filtros pelo nome do geom."""

    def __init__(self, cena, corpos: dict, excluir=None, zona=None, teto: float | None = None, incluir=None):
        self.teto = teto
        self.perfis: dict = {}
        self.r_tubo: float | None = None
        self.itens = []
        self.zona = None if zona is None else (np.asarray(zona[0], dtype=float), np.asarray(zona[1], dtype=float))

        def aceita(nome):
            if excluir is not None and excluir.search(nome):
                return False
            return incluir is None or bool(incluir.search(nome))

        chave_f = (excluir.pattern if excluir is not None else None, incluir.pattern if incluir is not None else None)
        aceites = cena.__dict__.setdefault("_aceites", {})
        if chave_f not in aceites:
            aceites[chave_f] = [aceita(g[1]) for g in cena.geoms_primitivas()]
        for (corpo, _nome, t, pos, r, s, bb), ok in zip(cena.geoms_primitivas(), aceites[chave_f], strict=True):
            if not ok or corpo not in corpos:
                continue
            nome = _nome
            off = np.asarray(corpos[corpo], dtype=float)
            lo, hi = bb[0] + off, bb[1] + off
            if self.zona is not None and (np.any(hi < self.zona[0]) or np.any(lo > self.zona[1])):
                continue
            self.itens.append((t, np.ascontiguousarray(pos + off), np.ascontiguousarray(r.flatten()),
                               np.ascontiguousarray(s), nome, lo, hi))
        self.grelhas = []
        for corpo, off in corpos.items():
            gr = cena.tri.de(corpo)
            if gr is None:
                continue
            mask = np.array([aceita(nm) for nm in gr.nomes], dtype=bool)
            if np.any(mask):
                self.grelhas.append((gr, np.asarray(off, dtype=float), mask))
        self.A = True if self.grelhas else None           # (compatibilidade: «há malhas»)

    def recorte(self, lo, hi) -> _Sonda:
        """A mesma sonda só com o que toca na caixa (lo, hi)."""
        lo, hi = np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)
        out = object.__new__(_Sonda)
        out.teto, out.perfis, out.r_tubo, out.grelhas, out.A = self.teto, {}, self.r_tubo, self.grelhas, self.A
        out.itens = [it for it in self.itens if not (np.any(it[6] < lo) or np.any(it[5] > hi))]
        if self.zona is not None:
            lo, hi = np.maximum(lo, self.zona[0]), np.minimum(hi, self.zona[1])
        out.zona = (lo, hi)
        return out

    def _cand(self, lo, hi):
        """Triângulos (n, 3, 3) — já no referencial comum — cuja caixa toca em (lo, hi) ∩ zona."""
        if self.zona is not None:
            lo, hi = np.maximum(lo, self.zona[0]), np.minimum(hi, self.zona[1])
            if np.any(lo > hi):
                return np.zeros((0, 3, 3))
        partes = []
        for gr, off, mask in self.grelhas:
            idx = gr.indices(lo - off, hi - off, mask)
            if len(idx):
                partes.append(gr.T[idx] + off)
        return np.concatenate(partes) if partes else np.zeros((0, 3, 3))

    @staticmethod
    def _mt(P, V, T, dmax, teto):
        """Möller–Trumbore de cada raio (P, V: (n, 3)) contra os triângulos T (m, 3, 3) → distância mínima (n,)."""
        out = np.full(len(P), np.inf)
        if not len(T) or not len(P):
            return out
        a, e1, e2 = T[None, :, 0], (T[:, 1] - T[:, 0])[None], (T[:, 2] - T[:, 0])[None]
        pv = _cruz(V[:, None, :], e2)
        det = np.einsum("nmk,nmk->nm", pv, np.broadcast_to(e1, pv.shape))
        ok = np.abs(det) > 1e-14
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = P[:, None, :] - a
        uu = np.einsum("nmk,nmk->nm", tv, pv) * inv
        qv = _cruz(tv, e1)
        vv = np.einsum("nmk,nk->nm", qv, V) * inv
        tt = np.einsum("nmk,nmk->nm", np.broadcast_to(e2, qv.shape), qv) * inv
        m = ok & (uu >= 0.0) & (uu <= 1.0) & (vv >= 0.0) & (uu + vv <= 1.0) & (tt > 1e-7) & (tt <= dmax)
        if teto is not None:
            m &= (P[:, None, 2] + tt * V[:, None, 2]) <= teto
        tt = np.where(m, tt, np.inf)
        return tt.min(axis=1)

    def _malhas(self, p, v, dmax):
        q = p + dmax * v
        T = self._cand(np.minimum(p, q) - 1e-9, np.maximum(p, q) + 1e-9)
        if not len(T):
            return None
        d = float(self._mt(p[None], v[None], T, dmax, self.teto)[0])
        return d if math.isfinite(d) else None

    def raio(self, p, v, dmax: float, z_passa: float | None = None):
        """Distância da primeira peça ao longo de p + λ·v (λ ≤ dmax), ou None. `z_passa`: das PRIMITIVAS só as que
        passam por essa cota (± 2 mm) — o tubo de um braço, não a placa de cima."""
        p = np.ascontiguousarray(p, dtype=float)
        v = np.ascontiguousarray(_u(v))
        melhor = self._malhas(p, v, dmax)
        for t, pos, mat, s, _nome, lo, hi in self.itens:
            if z_passa is not None and not (lo[2] <= z_passa + 0.002 and hi[2] >= z_passa - 0.002):
                continue
            d = mujoco.mju_rayGeom(pos, mat, s, p, v, t, None)
            if 0.0 <= d <= dmax and (melhor is None or d < melhor):
                melhor = d
        return melhor

    def raios_verticais(self, P, sinal: float, dmax: float, z_passa: float | None = None) -> np.ndarray:
        """Raios verticais (para −z se `sinal` < 0) de vários pontos → distâncias (inf onde não toca)."""
        P = np.asarray(P, dtype=float)
        V = np.repeat(np.array([[0.0, 0.0, 1.0 if sinal > 0 else -1.0]]), len(P), axis=0)
        return self.raios(P, V, dmax, z_passa=z_passa, _lotes=8)

    def raios(self, P, V, dmax: float, z_passa: float | None = None, _lotes: int = 0) -> np.ndarray:
        """Vários raios de uma vez (P, V: (n, 3)) → distâncias (n,), inf onde não toca."""
        P = np.asarray(P, dtype=float)
        V = np.asarray(V, dtype=float)
        V = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-12)
        out = np.full(len(P), np.inf)
        Q = P + dmax * V
        lotes = [np.arange(len(P))] if not _lotes else np.array_split(np.arange(len(P)), max(1, len(P) // _lotes))
        for idx in lotes:
            if not len(idx):
                continue
            lo = np.minimum(P[idx], Q[idx]).min(axis=0) - 1e-9
            hi = np.maximum(P[idx], Q[idx]).max(axis=0) + 1e-9
            T = self._cand(lo, hi)
            if len(T):
                out[idx] = np.minimum(out[idx], self._mt(P[idx], V[idx], T, dmax, self.teto))
        for t, pos, mat, s, _nome, lo_, hi_ in self.itens:
            if z_passa is not None and not (lo_[2] <= z_passa + 0.002 and hi_[2] >= z_passa - 0.002):
                continue
            for i in range(len(P)):
                d = mujoco.mju_rayGeom(pos, mat, s, np.ascontiguousarray(P[i]), np.ascontiguousarray(V[i]), t, None)
                if 0.0 <= d <= dmax and d < out[i]:
                    out[i] = d
        return out


@dataclass
class _Braco:
    """p(s, δ, dz) = o + s·u + δ·n + dz·ẑ no referencial do `corpo` (o = eixo do tubo)."""

    k: int
    corpo: str
    o: np.ndarray
    u: np.ndarray
    n: np.ndarray
    h0: float = 0.05        # altura (sobre o eixo) de onde partem os raios de cima

    def p(self, s: float, d: float = 0.0, dz: float = 0.0) -> np.ndarray:
        return self.o + s * self.u + d * self.n + np.array([0.0, 0.0, dz])

    def s(self, q) -> float:
        return float(np.dot(np.asarray(q, dtype=float) - self.o, self.u))

    def d(self, q) -> float:
        return float(np.dot(np.asarray(q, dtype=float) - self.o, self.n))

    def dz(self, q) -> float:
        return float(np.asarray(q, dtype=float)[2] - self.o[2])


def _topo(sonda: _Sonda, b: _Braco, s: float, d: float, omissao: float, lim=(0.0015, 0.03)) -> float:
    """dz do TOPO da superfície do braço em (s, δ): raio de cima (malhas abaixo do teto; primitivas pelo eixo)."""
    h0 = b.h0
    dist = sonda.raio(b.p(s, d, h0), -EZ, h0 + 0.03, z_passa=float(b.o[2]))
    if dist is None:
        return omissao
    dz = h0 - dist
    return dz if lim[0] - 0.012 <= dz <= lim[1] else omissao


def _fundo(sonda: _Sonda, b: _Braco, s: float, d: float, omissao: float) -> float:
    h0 = 0.045
    dist = sonda.raio(b.p(s, d, -h0), EZ, h0 + 0.03, z_passa=float(b.o[2]))
    if dist is None:
        return omissao
    dz = dist - h0
    return dz if -0.04 <= dz <= 0.0 else omissao


def _meia_largura(sonda: _Sonda, b: _Braco, s: float, dz: float, omissao: float) -> float:
    w = []
    for lado in (1.0, -1.0):
        dist = sonda.raio(b.p(s, lado * 0.03, dz), -lado * b.n, 0.03, z_passa=float(b.o[2]))
        w.append(0.03 - dist if dist is not None else omissao)
    v = max(w)
    return v if 0.003 <= v <= 0.03 else omissao


def _perfil(sonda: _Sonda, b: _Braco, s0: float, s1: float, d: float, r: float, omissao: float,
            passo: float = 0.004, largura: float = 0.0) -> list:
    """Pontos de um cabo de raio r deitado no topo do braço de s0 a s1 (sobe às abraçadeiras; simplificado). O perfil
    do topo mede-se UMA vez por troço, no eixo do braço (partilhado pelos cabos lado a lado); num tubo redondo o cabo
    afastado δ do topo assenta a √((R + r)² − δ²) do eixo."""
    n = max(2, int(abs(s1 - s0) / passo) + 1)
    ss = np.linspace(s0, s1, n)
    chave = (round(s0, 5), round(s1, 5), n, round(largura, 5))
    cache = sonda.perfis
    if chave not in cache:
        h0 = b.h0
        zs = np.full(n, -np.inf)
        for dl in ((0.0,) if largura <= 0.0 else (-largura, 0.0, largura)):
            dist = sonda.raios_verticais(np.array([b.p(sv, dl, h0) for sv in ss]), -1.0, h0 + 0.03,
                                         z_passa=float(b.o[2]))
            for i, dd in enumerate(dist):
                dz = h0 - dd if np.isfinite(dd) else omissao
                dz = dz if 0.0015 - 0.012 <= dz <= 0.03 else omissao
                zs[i] = max(zs[i], dz)               # fora do eixo o tubo redondo está mais baixo: só conta o que sobe
        zs = list(zs)
        # o cabo não desce a buracos estreitos entre peças e sobe ANTES dos ressaltos (a curva de 8–12 mm não corta a
        # esquina): máximo deslizante de ±12 mm
        k_j = max(1, math.ceil(0.012 / passo))
        cache[chave] = [max(zs[max(0, i - k_j): i + k_j + 1]) for i in range(n)]
    if sonda.r_tubo is None:
        s_m = 0.5 * (s0 + s1)
        dz_t, dz_b = _topo(sonda, b, s_m, 0.0, 0.005), _fundo(sonda, b, s_m, 0.0, -0.005)
        w = _meia_largura(sonda, b, s_m, 0.5 * (dz_t + dz_b), 0.012)
        sonda.r_tubo = w if abs(w - 0.5 * (dz_t - dz_b)) < 0.0035 else 0.0
    rt = sonda.r_tubo
    # e por baixo do PRÓPRIO cabo (afastado do eixo: as cabeças dos parafusos da abraçadeira do canto ficam ao lado)
    zs_d = None
    if abs(d) > 0.001 or largura < r:
        chave_d = (*chave, round(d, 5), round(r, 5))
        if chave_d not in cache:
            h0 = b.h0
            k_j = max(1, math.ceil(0.012 / passo))
            z_ax = np.asarray(cache[chave], dtype=float)
            # só onde o topo NÃO é o tubo nu (abraçadeiras, placa: topo plano) — e a ±12 mm disso
            plano = ~((rt > 0.0) & (abs(d) < rt + r) & (np.abs(z_ax - rt) <= 0.0003))
            perto = np.array([bool(np.any(plano[max(0, i - k_j): i + k_j + 1])) for i in range(n)], dtype=bool)
            zd = np.full(n, -np.inf)
            sel = np.flatnonzero(perto)
            if len(sel):
                for dl in (d - r, d, d + r):                  # a largura toda do cabo
                    dist = sonda.raios_verticais(np.array([b.p(ss[i], dl, h0) for i in sel]), -1.0, h0 + 0.03,
                                                 z_passa=float(b.o[2]))
                    for i, dd in zip(sel, dist, strict=True):
                        if np.isfinite(dd) and 0.0015 - 0.012 <= h0 - dd <= 0.03:
                            zd[i] = max(zd[i], h0 - dd)
            cache[chave_d] = [max(zd[max(0, i - k_j): i + k_j + 1]) for i in range(n)]
        zs_d = cache[chave_d]
    pts = []
    for i, (s, z) in enumerate(zip(ss, cache[chave], strict=True)):
        z_d = zs_d[i] if zs_d is not None else -np.inf
        if rt > 0.0 and abs(d) < rt + r and abs(z - rt) <= 0.0003:
            # tubo redondo: o centro do cabo fica a R + r do eixo (o topo medido menos o raio), 0,03 mm por fora
            dz = max((z - rt) + math.sqrt(max((rt + r) ** 2 - d * d, 0.0)), z_d + r) + 0.00003
        else:
            # outra peça (abraçadeira, suporte, placa: topo plano); +0,12 mm porque a simplificação (0,15 mm) pode
            # baixar a corda entre os pontos que ficam — o cabo nunca afunda no topo plano
            dz = max(z, z_d) + r + 0.00015
        pts.append(b.p(s, d, dz))
    return _simplificar(pts, 0.00015)


def _arco_tubo(b: _Braco, s0: float, s1: float, d0: float, dz0: float, d1: float, dz1: float, rho: float,
               sentido: float, dz_eixo: float = 0.0, n: int = 10) -> list:
    """Pontos de um cabo que CONTORNA o tubo (raio `rho` do eixo, que fica a `dz_eixo` de b.o) de (d0, dz0) a (d1, dz1)
    pelo lado `sentido` (−1: por baixo, passa por −90°; +1: por cima, por +90°), enquanto avança de s0 a s1."""
    a0 = math.atan2(dz0 - dz_eixo, d0)
    a1 = math.atan2(dz1 - dz_eixo, d1)
    alvo = -0.5 * math.pi if sentido < 0 else 0.5 * math.pi

    def contem(a, b_, x):                  # x (mod 2π) está no arco de a a b_ (b_ pode ser < a)
        lo, hi = min(a, b_), max(a, b_)
        return any(lo <= x + 2.0 * math.pi * k <= hi for k in (-2, -1, 0, 1, 2))
    desc = a1 if a1 < a0 else a1 - 2.0 * math.pi        # a descer
    asc = a1 if a1 > a0 else a1 + 2.0 * math.pi         # a subir
    a1 = desc if contem(a0, desc, alvo) else asc
    out = []
    for j in range(n + 1):
        t = j / n
        a = a0 + (a1 - a0) * t
        out.append(b.p(s0 + (s1 - s0) * t, rho * math.cos(a), dz_eixo + rho * math.sin(a)))
    return out


def _perfil_lado(sonda: _Sonda, b: _Braco, s0: float, s1: float, lado: float, dz: float, r: float, d_min: float,
                 passo: float = 0.003, folga: float = 0.0005) -> list:
    """Cabo de raio r ao LADO do braço (δ com o sinal `lado`, à altura dz) de s0 a s1: afasta-se das peças que saem
    para o lado (abraçadeiras das pernas, ponteiras) — raios de fora para o eixo, máximo deslizante."""
    n = max(2, int(abs(s1 - s0) / passo) + 1)
    ss = np.linspace(s0, s1, n)
    P = np.array([b.p(sv, lado * 0.05, dzz) for sv in ss for dzz in (dz - r, dz, dz + r)])
    V = np.repeat((-lado * b.n)[None], len(P), axis=0)
    t = sonda.raios(P, V, 0.05, _lotes=6).reshape(n, 3)
    ext = np.where(np.isfinite(t), 0.05 - t, 0.0).max(axis=1)
    k_j = max(2, math.ceil(0.012 / passo))               # ±12 mm: o arredondamento (8–12 mm) não corta o ressalto
    ext = [float(max(ext[max(0, i - k_j): i + k_j + 1])) for i in range(n)]
    pts = [b.p(sv, lado * max(d_min, e + r + folga), dz) for sv, e in zip(ss, ext, strict=True)]
    return _simplificar(pts, 0.0003)


# ====================================================================================== cena (âncoras)
class _Cena:
    def __init__(self, ctx, malhas: _Malhas):
        self._geoms_prim = None
        self.ctx, self.m = ctx, malhas
        self.hw = ctx.hw
        self.tri = _Triangulos(ctx)
        self.art = bool(ctx.articulado)
        self.servo_pwm = self.art and _tipo_servo(self.hw, "cotovelo") == "servo_pwm"
        self.juncao_servo: dict = {}        # k → (ponto, direção, âncora do servo, ponto na ficha do servo)
        self.rail_servos = None             # (centro do rail, face do UBEC, direção da face, z do rail, portas)
        self.servo_linhas: dict = {}        # k → linha do cabo do servo (do rail à junção no feixe do ombro)
        self.hall_ini: dict = {}            # k → (início do cabo do Hall na separação do motorredutor, para dentro)
        self.pico_reservas: dict = {}       # n → [(ficha, cabeça, raio)] das descidas pela borda de dentro do Pico n
        self.servo_braco: dict = {}         # k → (linha do cabo do servo no braço, corpo, _Braco, dz do eixo, meia largura)
        self.feixe_ombro: dict = {}         # k → (ponta A no braço, dir. dela, corpo, ponta W2 no drone, dir., linha no drone)
        self.placa = self.caixa("placa")
        self.rpi = self.caixa("el_rpi5")
        self.portenta = self.caixa("el_arduino_portenta_h7")
        self.computador = self.rpi if self.rpi is not None else self.portenta
        self.fc = self.caixa("el_fc_h7")
        self.pdb_massa = self.caixa("el_cablagem")
        self.bat = self.caixa("bateria")
        self.cam = self.caixa("camera")
        self.baixo = self.caixa("sensores_baixo")
        self.fonte = self.caixa("fonte_servos")
        self.esc4 = self.caixa("esc")
        self.z_topo = float(self.placa.hi[2]) if self.placa is not None else 0.0
        g = ctx.geom_existente("placa_superior")
        self.z_sup = float(g.pos[2]) if g is not None else None
        try:
            self.sinais = [(1.0 if x >= 0 else -1.0, 1.0 if y >= 0 else -1.0) for x, y in self.hw.pos_rotores]
        except Exception:  # noqa: BLE001
            self.sinais = [(1.0, 1.0), (-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0)]
        cam = getattr(self.hw, "camera", None)
        self.cam_csi = cam is not None and str(cam.dados.get("tipo", "")) == "modulo_camera_csi"
        self.n_abrac = 0
        self.sinal_lado: dict[int, tuple] = {}
        notas = ctx.registo.notas
        self.ancoras = notas.setdefault("ancoras", {})

    # ---------------------------------------------------------------- consultas
    def caixa(self, *nomes) -> _Caixa | None:
        lo = hi = corpo = None
        for nome in nomes:
            g = self.ctx.geom_existente(nome)
            if g is None:
                continue
            bb = _aabb(g)
            if bb is None:
                continue
            cg = g.parent.name
            if corpo is None:
                corpo = cg
            elif cg != corpo:
                continue
            lo = bb[0] if lo is None else np.minimum(lo, bb[0])
            hi = bb[1] if hi is None else np.maximum(hi, bb[1])
        return None if lo is None else _Caixa(corpo, lo, hi)

    @staticmethod
    def local(caixa: _Caixa, x0, x1, y0, y1, z0, z1) -> _Caixa:
        """Caixa (mm) no referencial de uma placa: origem no canto (−x, −y) de baixo da caixa com massa."""
        o = np.array([caixa.lo[0], caixa.lo[1], caixa.lo[2]])
        return _Caixa(caixa.corpo, o + np.array([x0, y0, z0]) * MM, o + np.array([x1, y1, z1]) * MM)

    @staticmethod
    def centrada(caixa: _Caixa, x0, x1, y0, y1, z0, z1) -> _Caixa:
        """Caixa (mm) no referencial centrado em xy da caixa com massa, z a partir do fundo dela."""
        o = np.array([caixa.c[0], caixa.c[1], caixa.lo[2]])
        return _Caixa(caixa.corpo, o + np.array([x0, y0, z0]) * MM, o + np.array([x1, y1, z1]) * MM)

    def nome_ancora(self, nome: str, reserva_nome: str | None) -> str | None:
        """O nome a declarar na ligação: a âncora se existe; senão a peça com massa onde a reserva vive."""
        if self.ctx.geom_existente(nome) is not None:
            return nome
        return reserva_nome if reserva_nome and self.ctx.geom_existente(reserva_nome) is not None else None

    def ancora(self, nome: str, reserva) -> _Caixa | None:
        """A peça `nome` da eletrónica, se existe; senão a caixa de reserva com a mesma disposição (ou None)."""
        cx = self.caixa(nome)
        if cx is not None:
            return cx
        try:
            return reserva()
        except Exception:  # noqa: BLE001 — peça opcional: sem âncora, o cabo não se desenha
            return None

    def geoms_primitivas(self) -> list:
        """As primitivas VISÍVEIS do spec (menos as dos fios), com pose e caixa — calculadas UMA vez por cena: as sondas
        liam e convertiam as ~600 peças de cada vez. Os fios só acrescentam `fios_*` no fim, que as sondas ignoram."""
        if self._geoms_prim is None:
            lista = []
            for g in self.ctx.spec.geoms:
                nome = g.name or ""
                if nome.startswith("fios_") or not _visivel(g):
                    continue
                t = int(g.type)
                if t not in _PRIMITIVAS:
                    continue
                _t, pos, r, s = _pose(g)
                lista.append((g.parent.name if g.parent is not None else "", nome, t, pos, r, s, _aabb(g)))
            self._geoms_prim = lista
        return self._geoms_prim

    def sonda(self, corpos: dict, zona, teto=None, excluir=_NAO_SUPERFICIE, incluir=None) -> _Sonda:
        return _Sonda(self, corpos, excluir, zona=zona, teto=teto, incluir=incluir)

    # ---------------------------------------------------------------- ligações (registo)
    def ligar(self, ident: str, de: str | None, para: str | None, c0: str, p0, c1: str, p1, bitola: str,
              peca: str, inst: int = 0, **extra) -> None:
        if de is None or para is None:
            return
        self.ctx.ligacao(ident, de=de, para=para, corpos=(c0, c1), pontos=(np.asarray(p0, float), np.asarray(p1, float)),
                         bitola=bitola, peca=peca, inst=inst, **extra)

    def ponto_ancora(self, nome: str):
        """(corpo, ponto, direção) de uma âncora publicada em `registo.notas["ancoras"]`, ou None."""
        a = self.ancoras.get(nome)
        if not isinstance(a, dict) or "ponto" not in a:
            return None
        return str(a.get("corpo", "drone")), np.asarray(a["ponto"], dtype=float), _u(a.get("direcao", [1.0, 0.0, 0.0]))

    # ---------------------------------------------------------------- âncoras da eletrónica (ou a mesma disposição)
    _PDB: ClassVar[dict] = {"el_pdb_bat_pos": (-29.5, -23.5, 2.0, 10.0, 1.6, 2.0), "el_pdb_bat_neg": (-29.5, -23.5, -10.0, -2.0, 1.6, 2.0),
            "el_pm_con_i2c": (25.4, 29.6, -5.0, 5.0, 1.6, 5.85), "el_pm_saida_5v": (-6.0, 6.0, 12.0, 16.5, 1.6, 6.5),
            "el_pm_5v_pos": (-7.0, -3.0, -19.6, -16.4, 1.6, 2.0), "el_pm_5v_neg": (-1.0, 3.0, -19.6, -16.4, 1.6, 2.0)}

    def pdb_pad(self, nome: str) -> _Caixa | None:
        """Ilhas/fichas da placa de energia (`el_pdb_*` / `el_pm_*`), ou as mesmas na caixa `el_cablagem`."""
        def reserva():
            pm = self.pdb_massa
            if pm is None:
                return None
            if nome in self._PDB:
                return self.centrada(pm, *self._PDB[nome])
            mt = re.match(r"el_pdb_esc(\d)_(pos|neg)", nome)
            if mt:
                sx, sy = self.sinais[int(mt.group(1)) - 1]
                xc = 24.75 if mt.group(2) == "pos" else 19.25
                hx = 2.25 if mt.group(2) == "pos" else 2.0
                return self.centrada(pm, sx * xc - hx, sx * xc + hx, sy * 14.5 - 3.0, sy * 14.5 + 3.0, 1.6, 1.95)
            return None
        return self.ancora(nome, reserva)

    _FC: ClassVar[dict] = {"el_fc_con_esc": (-17.8, -13.55, -4.5, 4.5, 1.6, 4.5), "el_fc_con_gps": (13.4, 17.6, -9.4, -0.6, 1.6, 5.85),
           "el_fc_con_i2c": (13.4, 17.6, 2.4, 8.6, 1.6, 5.85), "el_fc_con_uart": (-11.5, -5.5, 13.75, 18.0, 1.6, 5.85),
           "el_fc_con_sensores": (4.4, 11.6, 13.75, 18.0, 1.6, 5.85)}

    def fc_con(self, nome: str) -> _Caixa | None:
        return self.ancora(nome, lambda: self.centrada(self.fc, *self._FC[nome]) if self.fc is not None else None)

    _RPI: ClassVar[dict] = {"rpi5_usbc": (6.73, 15.67, -1.2, 6.3, 1.6, 4.8), "el_rpi5_cam_disp0": (46.0, 50.5, 2.0, 16.6, 1.6, 3.6),
            "el_rpi5_cam_disp0_trava": (50.5, 51.5, 2.3, 16.3, 1.6, 3.9),
            "rpi5_gpio_40p": (7.1, 57.9, 49.96, 55.04, 1.6, 4.1)}

    def rpi_peca(self, nome: str) -> _Caixa | None:
        mt = re.match(r"el_rpi5_gpio_pino(\d\d)$", nome)
        if mt:
            xc = 8.37 + 2.54 * (int(mt.group(1)) - 1)
            caixa = (xc - 0.32, xc + 0.32, 50.91, 54.09, 4.1, 10.1)
        else:
            caixa = self._RPI.get(nome)
        return self.ancora(nome, lambda: self.local(self.rpi, *caixa) if (self.rpi is not None and caixa) else None)

    # ---------------------------------------------------------------- ESC e motores
    def esc_saidas(self, k: int, u: np.ndarray, corpo_braco: str):
        """(corpo, ponto da entrada, ponto das fases, eixo do ESC para fora, eixo lateral, nome da âncora das entradas,
        nome da âncora das fases): as faces das saídas do AIR 40A da eletrónica, ou as pontas da caixa `esc{k}` ao
        longo do braço. ESC 4-em-1: só as fases (do centro)."""
        ge, gf = self.ctx.geom_existente(f"el_esc{k}_saida_entrada"), self.ctx.geom_existente(f"el_esc{k}_saida_fases")
        if ge is not None and gf is not None:
            _t, pe, re_, se = _pose(ge)
            _t, pf, rf, sf = _pose(gf)
            return (ge.parent.name, pe - re_[:, 0] * se[0], pf + rf[:, 0] * sf[0], rf[:, 0], rf[:, 1],
                    f"el_esc{k}_saida_entrada", f"el_esc{k}_saida_fases")
        n = np.array([-u[1], u[0], 0.0])
        esc = self.caixa(f"esc{k}")
        if esc is not None:
            c = esc.c.copy()
            corpo = esc.corpo
            if self.art and esc.corpo == "drone" and self.ctx.existe_corpo(corpo_braco):
                c = c - np.array(self.ctx.corpo(corpo_braco).pos, dtype=float)
                corpo = corpo_braco
            e = esc.extensao(u)
            return corpo, c - e * u, c + e * u, u, n, f"esc{k}", f"esc{k}"
        if self.esc4 is not None and not self.art:
            e = 0.8 * self.esc4.extensao(u)
            return self.esc4.corpo, None, self.esc4.c + e * u, u, n, None, "esc"
        return None

    def balas(self, k: int):
        """As 3 balas de 3,5 mm dos cabos do motor (módulo `motores`): [(corpo, ponta livre, direção, raio da bala)]."""
        out = []
        for f in "abc":
            g = self.ctx.geom_existente(f"motor{k}_fase_{f}_conector")
            if g is None:
                return None
            ft = np.array(g.fromto, dtype=float)
            if np.isnan(ft[0]):
                return None
            out.append((g.parent.name, ft[3:6], _u(ft[3:6] - ft[:3]), float(g.size[0])))
        return out


# ====================================================================================== abraçadeiras de nylon
def _ficha_para(perimetro: float) -> _Ficha:
    """A abraçadeira mais pequena cujo feixe máximo (Ø da ficha) abraça este perímetro."""
    for f in FICHAS:
        if perimetro <= math.pi * f.feixe_max:
            return f
    return FICHAS[-1]


def _seccao(cena: _Cena, corpo: str, c, e1, e2, rho: float, incluir=None, excluir=_SO_FIOS, n_ang: int = 40,
            meia_larg: float = 0.00175, cabos_ids=None, cabos_raio: float | None = None):
    """Secção do feixe no plano (c; e1, e2) — pontos 2D da superfície das peças (raios no plano, do raio `rho` para
    dentro, em 3 planos ao longo da largura da fita) e dos cabos que atravessam o plano encostados ao feixe (cortes da
    polilinha de cada tubo, elipse do corte). Devolve (pontos 2D, cabos incluídos)."""
    c = np.asarray(c, dtype=float)
    e1, e2 = _u(e1), _u(e2)
    e3 = np.cross(e1, e2)
    z = np.full(3, rho + 0.004)
    sonda = cena.sonda({corpo: np.zeros(3)}, (c - z, c + z), excluir=excluir, incluir=incluir)
    ang = np.linspace(0.0, 2.0 * math.pi, n_ang, endpoint=False)
    d2 = np.column_stack([np.cos(ang), np.sin(ang)])
    d3 = np.outer(d2[:, 0], e1) + np.outer(d2[:, 1], e2)
    pts = []
    planos = (0.0,) if meia_larg <= 0.0 else (-meia_larg, 0.0, meia_larg)
    for delta in planos:
        cd = c + delta * e3
        t = sonda.raios(cd + rho * d3, -d3, rho)
        ok = np.isfinite(t)
        pts += list(d2[ok] * (rho - t[ok])[:, None])
    # cortes dos cabos pelo plano (os 3 planos da largura)
    cand = []
    for cab in cena.m.cabos:
        if cab["corpo"] != corpo or (cabos_ids is not None and cab["id"] not in cabos_ids):
            continue
        P, r, A = cab["pts"], cab["r"], cab["aneis"]
        # os fios finos do par entrançado andam em hélice: na largura toda da fita mudavam de sítio (a fita ficava longe
        # deles no plano do meio) — contam só perto do meio (a fita aperta-os)
        for delta in (planos if r >= 0.0006 else tuple(0.4 * x for x in planos)):
            c_d = c + delta * e3
            s = (P - c_d) @ e3
            for i in np.flatnonzero(s[:-1] * s[1:] <= 0.0):
                sa, sb = float(s[i]), float(s[i + 1])
                if sa == sb:
                    continue
                q = P[i] + (P[i + 1] - P[i]) * (sa / (sa - sb))
                x, y = float((q - c) @ e1), float((q - c) @ e2)
                if math.hypot(x, y) > rho + r:
                    continue
                # o corte EXATO da malha do tubo: cada aresta longitudinal (vértice j do anel i ao do anel i+1, ou os
                # vizinhos se o plano cortar ao lado) cortada pelo plano — o polígono que a malha mostra
                el = []
                for j in range(A.shape[1]):
                    for i2 in (i, i - 1, i + 1):
                        if 0 <= i2 < len(A) - 1:
                            a3, b3 = A[i2, j], A[i2 + 1, j]
                            ta, tb = float((a3 - c_d) @ e3), float((b3 - c_d) @ e3)
                            if ta * tb <= 0.0 and ta != tb:
                                w3 = a3 + (b3 - a3) * (ta / (ta - tb))
                                el.append(np.array([float((w3 - c) @ e1), float((w3 - c) @ e2)]))
                                break
                if len(el) < 3:
                    continue
                cand.append((cab["id"], np.array([x, y]), r, el))
    incluidos: list = []
    pontos = list(pts)
    restantes = list(cand)
    if not pontos and restantes:                          # só cabos: começa pelo mais perto do centro
        restantes.sort(key=lambda it: float(np.linalg.norm(it[1])))
        pontos += restantes[0][3]
        incluidos.append(restantes.pop(0)[0])
    alcance = cabos_raio if cabos_raio is not None else 0.0017
    mudou = True
    while mudou and restantes:
        mudou = False
        h = _limpar_casca(_casca(pontos)) if len(pontos) >= 3 else np.array(pontos)
        for it in list(restantes):
            dist = _dist_poligono(it[1], h) - it[2] if len(h) >= 3 else 0.0
            if dist <= alcance or it[0] in incluidos:
                pontos += it[3]
                incluidos.append(it[0])
                restantes.remove(it)
                mudou = True
    return pontos, sorted(set(incluidos))


def _perimetro(h: np.ndarray) -> float:
    return float(sum(np.linalg.norm(h[(i + 1) % len(h)] - h[i]) for i in range(len(h))))


def _abracadeira(cena: _Cena, corpo: str, c, e1, e2, rho: float, lado, incluir=None, rotulo: str = "",
                 excluir=_SO_FIOS, membros: str = "", cabos_raio: float | None = None, cabos_ids=None) -> dict | None:
    """Abraçadeira de nylon PRESA no plano (c; e1, e2): a fita assenta no invólucro convexo da secção real do feixe
    (`_seccao`), a cabeça de lingueta na face do feixe virada para `lado` (2D), a ponta cortada a sair da cabeça.
    Registada como peça `abracadeira` n e na lista de ferragens."""
    c = np.asarray(c, dtype=float)
    e1, e2 = _u(e1), _u(e2)
    e3 = np.cross(e1, e2)
    # 1.ª passagem (só o plano do meio) → perímetro → a ficha; 2.ª com a largura real da fita (3 planos)
    pts, cabos = _seccao(cena, corpo, c, e1, e2, rho, incluir=incluir, excluir=excluir, cabos_raio=cabos_raio,
                         meia_larg=0.0, n_ang=24, cabos_ids=cabos_ids)
    if len(pts) < 3:
        return None
    h = _limpar_casca(_casca(pts))
    if len(h) < 3:
        return None
    f = _ficha_para(_perimetro(_offset_convexo(h, FOLGA_ABRAC)))
    pts, cabos = _seccao(cena, corpo, c, e1, e2, rho, incluir=incluir, excluir=excluir, cabos_raio=cabos_raio,
                         meia_larg=0.5 * f.larg - 0.00005, cabos_ids=cabos_ids)
    h = _limpar_casca(_casca(pts))
    if len(h) < 3:
        return None
    dentro = _offset_convexo(h, FOLGA_ABRAC)              # face de dentro (0,03 mm do feixe)
    perim = _perimetro(dentro)
    f2 = _ficha_para(perim)
    if f2.feixe_max > f.feixe_max:
        f = f2
    eixo2 = _offset_convexo(h, FOLGA_ABRAC + 0.5 * f.esp)
    p3 = [c + q[0] * e1 + q[1] * e2 for q in eixo2]
    cena.n_abrac += 1
    n = cena.n_abrac
    m = cena.m
    lado = _u(np.asarray(lado, dtype=float))
    # aresta do invólucro virada para `lado` (a cabeça assenta numa face; prefere as arestas que levam a cabeça inteira)
    melhor, info = -math.inf, None
    for i in range(len(h)):
        a, b = h[i], h[(i + 1) % len(h)]
        e = b - a
        L = float(np.linalg.norm(e))
        if L < 1e-6:
            continue
        nrm = np.array([e[1], -e[0]]) / L
        nota = float(np.dot(nrm, lado)) + 0.15 * min(L / f.cab_comp, 1.0)
        if nota > melhor:
            melhor, info = nota, (a, b, e / L, nrm)
    a, b, t2, n2 = info
    pm = 0.5 * (a + b)
    T = t2[0] * e1 + t2[1] * e2
    N = n2[0] * e1 + n2[1] * e2
    base = c + pm[0] * e1 + pm[1] * e2 + N * (FOLGA_ABRAC + f.esp)
    centro_cab = base + N * (0.5 * f.cab_alt)
    with m.peca("abracadeira", n):
        m.fita(corpo, "fios_nylon", p3, f.larg, e3, f.esp, fechada=True)
        R = np.column_stack([T, e3, N])
        m.caixa(corpo, "fios_nylon", centro_cab, R, [0.5 * f.cab_comp, 0.5 * f.cab_larg, 0.5 * f.cab_alt])
        ponta = (centro_cab + N * (0.5 * f.cab_alt + 0.5 * PONTA_ABRAC)
                 + T * (0.5 * f.cab_comp - 0.5 * f.esp - 0.0006))
        m.caixa(corpo, "fios_nylon", ponta, R, [0.5 * f.esp, 0.5 * f.larg, 0.5 * PONTA_ABRAC])
    laco = [[float(v) for v in (c + q[0] * e1 + q[1] * e2)] for q in dentro]
    if cena.ctx.ferragens is not None:
        cena.ctx.ferragens.registar(
            tipo="abracadeira", norma="abraçadeira de nylon 66", rosca="", comp_mm=f.comp_mm,
            largura_mm=round(f.larg / MM, 2), espessura_mm=round(f.esp / MM, 2), corpo=corpo, ponto=centro_cab,
            eixo=e3, peca="abracadeira", inst=n, modelo=f.modelo,
            descricao=f"Abraçadeira de nylon {f.larg / MM:g} × {f.comp_mm:g} mm (HellermannTyton {f.modelo})",
            laco=laco, perimetro_mm=round(perim / MM, 2), feixe_mm=round(perim / math.pi / MM, 2), cabos=cabos,
            membros=membros, local=rotulo, cabeca={"centro": [float(v) for v in centro_cab],
                                                  "dims_mm": [f.cab_comp / MM, f.cab_larg / MM, f.cab_alt / MM]},
            ponta_mm=PONTA_ABRAC / MM)
    return {"n": n, "ficha": f, "laco": laco, "cabos": cabos}


def _abracadeira_braco(cena: _Cena, b: _Braco, s: float, lado: float, rotulo: str, incluir=None,
                       rho: float = 0.024) -> dict | None:
    """Abraçadeira à volta do tubo do braço (e dos cabos que lá passam) na estação s; cabeça de lado (`lado` = ±n)."""
    return _abracadeira(cena, b.corpo, b.p(s), b.n, EZ, rho, (lado, -0.25), incluir=incluir, rotulo=rotulo,
                        excluir=_TUBO_EXCLUIR, membros="tubo do braço + cabos")


# peças que não são o feixe de um braço (as abraçadeiras não as abraçam: escolhem-se estações livres delas)
_TUBO_EXCLUIR = re.compile(r"^(fios_|helice|caminho_tiro|projetil|perna|motor|el_|esc|servo|arma|camera|bateria|"
                           r"conector|cinta|sensores)", re.IGNORECASE)


def _sonda_estacoes(cena: _Cena, b: _Braco, s0: float, s1: float, r: float = 0.040) -> _Sonda:
    """Sonda de TUDO o que está à volta do braço entre s0 e s1 (menos os fios): as estações das abraçadeiras escolhem-se
    com recortes dela."""
    a, c = b.p(s0), b.p(s1)
    return cena.sonda({b.corpo: np.zeros(3)}, (np.minimum(a, c) - r, np.maximum(a, c) + r),
                      excluir=re.compile(r"^(fios_|helice|caminho_tiro|projetil)", re.IGNORECASE))


def _estacao_livre(cena: _Cena, b: _Braco, sonda: _Sonda, s: float, s_min: float, s_max: float, r_max: float,
                   larg: float = 0.0040, passo: float = 0.003, n_max: int = 16) -> float | None:
    """A estação mais perto de s (em [s_min, s_max]) onde a secção do braço (tudo o que lá está, menos os fios) cabe
    num raio r_max à volta do EIXO do tubo — longe das abraçadeiras CNC, das pernas, das treliças e do ESC."""
    if s_max < s_min:
        return None
    ang = np.linspace(0.0, 2.0 * math.pi, 16, endpoint=False)
    d3 = np.outer(np.cos(ang), b.n) + np.outer(np.sin(ang), EZ)
    rho = r_max + 0.012

    def livre(sv):
        c = b.p(sv)
        sub = sonda.recorte(c - (rho + larg), c + (rho + larg))
        for delta in (-0.5 * larg, 0.0, 0.5 * larg):
            t = sub.raios(b.p(sv + delta) + rho * d3, -d3, rho)
            ok = np.isfinite(t)
            if not np.any(ok) or np.any(rho - t[ok] > r_max):
                return False
        return True

    # os cabos já desenhados à volta do tubo têm de estar ASSENTES e paralelos a ele na largura da fita (não a subir
    # para passar uma peça): a distância ao eixo constante a 0,15 mm
    cabos = [(np.asarray(c["pts"]), (np.asarray(c["pts"]) - b.o) @ b.u) for c in cena.m.cabos
             if c["corpo"] == b.corpo and len(c["pts"]) > 1 and c["r"] >= 0.0006]      # (o par entrançado ondula)
    dz_ax = _eixo_tubo(sonda, b, s)[0] if cabos else 0.0

    def assentes(sv):
        for P, s_ in cabos:
            raios = []
            for sq in (sv - 0.5 * larg - 0.0012, sv, sv + 0.5 * larg + 0.0012):
                idx = np.flatnonzero((s_[:-1] - sq) * (s_[1:] - sq) <= 0.0)
                if not len(idx):
                    break
                i = int(idx[0])
                t = (sq - s_[i]) / (s_[i + 1] - s_[i]) if s_[i + 1] != s_[i] else 0.0
                q = P[i] + (P[i + 1] - P[i]) * t
                raios.append(math.hypot(b.d(q), b.dz(q) - dz_ax))
            if len(raios) == 3 and min(raios) < r_max + 0.006 and max(raios) - min(raios) > 0.00015:
                return False
        return True

    for k in range(n_max):
        for sv in ((s + passo * k, s - passo * k) if k else (s,)):
            if s_min <= sv <= s_max and livre(sv) and assentes(sv):
                return sv
    return None


def _eixo_tubo(sonda: _Sonda, b: _Braco, s: float) -> tuple[float, float]:
    """(dz do eixo do tubo em relação a b.o, raio) medidos com raios de cima e de baixo na estação s (o tubo desenhado
    pela estrutura pode não estar à altura da caixa com massa)."""
    dz_t = _topo(sonda, b, s, 0.0, math.nan)
    dz_b = _fundo(sonda, b, s, 0.0, math.nan)
    if not (math.isfinite(dz_t) and math.isfinite(dz_b)) or dz_t <= dz_b:
        return 0.0, 0.0
    return 0.5 * (dz_t + dz_b), 0.5 * (dz_t - dz_b)


# ====================================================================================== peças repetidas
def _dist_seg_xy(a0, a1, b0, b1) -> float:
    """Distância (xy) entre os segmentos a0–a1 e b0–b1 (0 se se cruzam)."""
    if _cruzam_xy(a0, a1, b0, b1):
        return 0.0
    a0, a1, b0, b1 = (np.asarray(v, dtype=float)[:2] for v in (a0, a1, b0, b1))

    def ponto_seg(p, q0, q1):
        v = q1 - q0
        t = 0.0 if float(v @ v) < 1e-18 else min(max(float((p - q0) @ v) / float(v @ v), 0.0), 1.0)
        return float(np.linalg.norm(p - (q0 + t * v)))
    return min(ponto_seg(a0, b0, b1), ponto_seg(a1, b0, b1), ponto_seg(b0, a0, a1), ponto_seg(b1, a0, a1))


def _cruzam_xy(a0, a1, b0, b1) -> bool:
    """Os segmentos a0–a1 e b0–b1 (xy) cruzam-se?"""
    a0, a1, b0, b1 = (np.asarray(v, dtype=float)[:2] for v in (a0, a1, b0, b1))

    def lado(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (lado(a0, a1, b0) * lado(a0, a1, b1) < 0.0) and (lado(b0, b1, a0) * lado(b0, b1, a1) < 0.0)


def _troco_s(linha, b: _Braco, s0: float, s1: float) -> list:
    """O troço da polilinha `linha` entre as estações s0 e s1 do braço (interpolado nas pontas)."""
    P = np.asarray(linha, dtype=float)
    ss = np.array([b.s(q) for q in P])
    out = []
    for sv in (s0, s1):
        i = np.flatnonzero((ss[:-1] - sv) * (ss[1:] - sv) <= 0.0)
        if not len(i):
            return []
        i = int(i[0])
        t = (sv - ss[i]) / (ss[i + 1] - ss[i]) if ss[i + 1] != ss[i] else 0.0
        out.append(P[i] + t * (P[i + 1] - P[i]))
    meio = [q for q, sv in zip(P, ss, strict=True) if min(s0, s1) < sv < max(s0, s1)]
    if out[0] is not None and s1 < s0:
        meio = meio[::-1]
    return [out[0], *meio, out[1]]


def _bala_femea(cena: _Cena, corpo: str, p3, dvec, r_c: float) -> np.ndarray:
    """Fêmea de 3,5 mm em termo-retráctil enfiada na bala do motor; devolve o ponto onde o cabo da extensão entra."""
    p3 = np.asarray(p3, dtype=float)
    cena.m.tubo(corpo, "fios_termo", [p3 - 0.0035 * dvec, p3 + 0.011 * dvec], 2.0 * (r_c + 0.0007), lados=12,
                cabo=False)
    return p3 + 0.008 * dvec


def _bala_femea_curta(cena: _Cena, corpo: str, p3, dvec, r_c: float) -> np.ndarray:
    """Fêmea de 3,5 mm em termo-retráctil enfiada na bala do motor quando a bala acaba DENTRO da pegada do ESC 4 em 1
    (5″): só cobre a ponta da bala e o copo de solda (6,5 mm, sem a ponta de 11 mm da fêmea normal, que ia por cima das
    porcas de nylon e do condensador da pilha) e ASSENTA no braço — o eixo sobe o que faltar (medido com raios para
    baixo; ≤ 0,75 mm): a bala do `motores` está desenhada deitada no braço e, com a fêmea, ficaria esses 0,7 mm acima
    (estimado). Devolve o ponto da solda (para a ligação)."""
    p3 = np.asarray(p3, dtype=float)
    dvec = _u(dvec)
    r_f = r_c + 0.0007
    a, b = p3 - 0.0035 * dvec, p3 + 0.003 * dvec
    lo, hi = np.minimum(a, b) - r_f - 0.003, np.maximum(a, b) + r_f + 0.003
    sonda = cena.sonda({corpo: np.zeros(3)}, (lo, hi),
                       excluir=re.compile(r"^(fios_|helice|caminho_tiro|projetil|motor\d+_fase)", re.IGNORECASE))
    e1 = _u(np.cross(dvec, EZ)) if abs(float(dvec[2])) < 0.9 else np.array([1.0, 0.0, 0.0])
    base = np.array([a + t * (b - a) + w * e1 for t in np.linspace(0.0, 1.0, 7) for w in (-0.6 * r_f, 0.0, 0.6 * r_f)])
    d = sonda.raios(base, np.repeat(-EZ[None], len(base), axis=0), r_f + 0.002)
    sobe = 0.0
    if np.isfinite(d).any():
        sobe = min(max(0.0, r_f + 0.00015 - float(np.min(d))), 0.00075)
    dz = np.array([0.0, 0.0, sobe])
    cena.m.tubo(corpo, "fios_termo", [a + dz, b + dz], 2.0 * r_f, lados=12, cabo=False)
    return b - 0.001 * dvec


def _ficha_eh(cena: _Cena, corpo: str, q, dq) -> None:
    """Ficha JST EHR-04 (12 × 3,8 × 8,1 mm, nylon natural) encaixada no conector do servo, a sair na direção dq."""
    dq = _u(dq)
    cena.m.caixa(corpo, "fios_jst", np.asarray(q, dtype=float) + 0.0038 * dq, _base(dq, EZ), [0.0040, 0.0058, 0.0030])


def _cantos(cx: _Caixa) -> list:
    return [np.array([x, y, z]) for x in (cx.lo[0], cx.hi[0]) for y in (cx.lo[1], cx.hi[1])
            for z in (cx.lo[2], cx.hi[2])]


def _canto(caixa: _Caixa, b: _Braco) -> float:
    """s (ao longo do braço) a partir do qual o eixo do braço sai da projeção horizontal da caixa."""
    s_lim = math.inf
    for eixo in (0, 1):
        if abs(b.u[eixo]) > 1e-6:
            alvo = caixa.hi[eixo] if b.u[eixo] > 0 else caixa.lo[eixo]
            s_lim = min(s_lim, float((alvo - b.o[eixo]) / b.u[eixo]))
    return max(0.0, s_lim) if math.isfinite(s_lim) else 0.0


def _subida(cena: _Cena, k: int, i: int, d: float = D_ESC) -> np.ndarray | None:
    """Ponto (xy) por onde o cabo i do braço k sobe ao lado da pilha (RPi/Portenta): na folga entre a placa e a janela da
    placa de cima, longe dos cantos arredondados da janela e das portas que saem das bordas."""
    comp = cena.computador if cena.computador is not None else cena.pdb_massa
    if comp is None:
        return None
    cache = cena.__dict__.setdefault("_subidas", {})
    chave = (k, i, round(d, 6))
    if chave in cache:
        return cache[chave].copy()
    sx, sy = cena.sinais[k - 1]
    folga = FOLGA_PILHA + max(0.0, 0.5 * d - 0.00175)
    passo = 0.0038
    if sx > 0:      # braços da frente: sobem pela borda ±y perto do canto da frente (as portas USB/RJ45 saem em +x)
        q = np.array([comp.c[0] + comp.h[0] - 0.0105 - i * passo, comp.c[1] + sy * (comp.h[1] + folga)])
        e_f = np.array([0.0, sy, 0.0])
    else:           # braços de trás: sobem pela borda de trás (−x), fora do cartão microSD e do botão
        q = np.array([comp.c[0] - comp.h[0] - folga, comp.c[1] + sy * (comp.h[1] - 0.0065 - i * passo)])
        e_f = np.array([-1.0, 0.0, 0.0])
    # a folga MEDIDA ao longo da subida: raios do eixo do fio para a pilha (o que sai da caixa do computador — a ponte
    # do FC, os pilares) e para fora (a borda da janela da placa de cima); o fio fica ≥ 0,1 mm de ambos (ou ao meio)
    r, c = 0.5 * d, 0.0001
    pdb = cena.caixa("el_pdb_pcb") or cena.pdb_massa
    z_hi = max(float(comp.hi[2]), float(pdb.hi[2]) if pdb is not None else -np.inf) + 0.003
    zs = np.arange(float(comp.lo[2]) - 0.004, z_hi, 0.001)
    P = np.array([[q[0], q[1], z] for z in zs])
    zona = (P.min(axis=0) - 0.010, P.max(axis=0) + 0.010)
    # (as peças da arma por cima da pilha não contam: os fios passam por baixo delas — `_sob_tetos`)
    sonda = cena.sonda({"drone": np.zeros(3)}, zona, excluir=_SO_FIOS_ARMA)
    ida = sonda.raios(P, np.repeat((-e_f)[None], len(P), axis=0), 0.008, _lotes=8)
    volta = sonda.raios(P, np.repeat(e_f[None], len(P), axis=0), 0.008, _lotes=8)
    a = float(np.min(ida[ida > 2e-4], initial=0.008))
    b = float(np.min(volta[volta > 2e-4], initial=0.008))
    lo, hi = r + c - b, a - r - c                     # deslocamento t para a pilha (−e_f) que serve
    t = min(max(0.0, lo), hi) if lo <= hi else 0.5 * (lo + hi)
    q = q - t * e_f[:2]
    cache[chave] = q
    return q.copy()


def _toque_ilha(pad: _Caixa, q) -> np.ndarray:
    """Ponto de contacto de um fio soldado numa ilha: a ponta do fio projetada no topo da ilha (dentro dela)."""
    q = np.asarray(q, dtype=float)
    return np.array([min(max(float(q[0]), float(pad.lo[0])), float(pad.hi[0])),
                     min(max(float(q[1]), float(pad.lo[1])), float(pad.hi[1])), float(pad.hi[2])])


# ====================================================================================== pontas da manga do feixe
R_VAGA = 0.00255        # vagas dos 4 cabos na ponta da manga do feixe (Ø 9): anel de 2,55 mm — cabe lá qualquer um
VAGAS = {"A": 60.0, "B": 150.0, "C": 240.0, "D": 330.0}      # (Ø ≤ 3,5) e os vizinhos ficam a 3,6 mm; graus (lat, z)


@dataclass
class _PontaFeixe:
    """Ponta da manga do feixe: centro `c`, `dv` = direção de saída dos cabos (para fora da manga), `lat` = horizontal ⟂
    dv para o lado de DENTRO (o tubo, no braço; o eixo do drone, na placa de cima)."""

    c: np.ndarray
    dv: np.ndarray
    lat: np.ndarray

    def ponto(self, vaga: str, ao_longo: float) -> np.ndarray:
        a = math.radians(VAGAS[vaga])
        return self.c + ao_longo * self.dv + R_VAGA * (math.cos(a) * self.lat + math.sin(a) * EZ)


class _Feixe:
    """O que `_alimentacao_e_sinal` usa do feixe do ombro: `braco(i, p0)` = pontos do fio i no braço (da manga à
    entrada do ESC) e a ponta da manga na placa de cima (`ponta_d`)."""

    def __init__(self, braco, ponta_d: _PontaFeixe):
        self.braco = braco
        self.ponta_d = ponta_d


def _descolar(b: _Braco, P, s_a: float, s_b: float, fim, dz_eixo: float = 0.0, n: int = 12) -> list:
    """Cabo que sai de P (ao lado do tubo) e, entre s_a e s_b, dá a volta POR CIMA do tubo até `fim`: em polares à volta
    do eixo, o ângulo varia linearmente e o raio desce depressa para o de `fim` (nunca entra no tubo)."""
    d0, z0 = b.d(P), b.dz(P) - dz_eixo
    d1, z1 = b.d(fim), b.dz(fim) - dz_eixo
    a0, a1 = math.atan2(z0, d0), math.atan2(z1, d1)
    if a0 < -0.5 * math.pi:              # lado −δ abaixo do eixo: o caminho por cima passa por π, não por −π/2
        a0 += 2.0 * math.pi
    if a1 < -0.5 * math.pi:
        a1 += 2.0 * math.pi
    r0, r1 = math.hypot(d0, z0), math.hypot(d1, z1)
    out = []
    for j in range(n + 1):
        t = j / n
        a = a0 + (a1 - a0) * t
        r = r1 + (r0 - r1) * (1.0 - t) ** 2
        out.append(b.p(s_a + (s_b - s_a) * t, r * math.cos(a), dz_eixo + r * math.sin(a)))
    return out


def _par_linhas(ini, fim, via, raio: float = 0.008, passo: float = 0.0015):
    """Linhas de 2 fios ENCOSTADOS de ini[i] a fim[i] (pontas exatas): a linha central passa pelos meios e por `via`; o
    afastamento (transportado ao longo da linha) roda — o par torce, devagar nas pontas — da direção ini[1] − ini[0] para
    fim[1] − fim[0] e passa de |ini[1] − ini[0]| a |fim[1] − fim[0]|. Devolve (linha 0, linha 1, torção total, rad)."""
    a0, a1 = (np.asarray(x, dtype=float) for x in ini)
    b0, b1 = (np.asarray(x, dtype=float) for x in fim)
    c = np.asarray(_reamostrar(_curva([0.5 * (a0 + a1), *via, 0.5 * (b0 + b1)], raio), passo))
    t, nn, bb = _quadros(c, n0=a1 - a0)
    e = (b1 - b0) - float(np.dot(b1 - b0, t[-1])) * t[-1]
    ang_fim = math.atan2(float(np.dot(e, bb[-1])), float(np.dot(e, nn[-1])))
    sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))])
    f = sl / max(float(sl[-1]), 1e-9)
    ang = ang_fim * (3.0 * f * f - 2.0 * f ** 3)
    sep = (1.0 - f) * float(np.linalg.norm(a1 - a0)) + f * float(np.linalg.norm(b1 - b0))
    w = np.cos(ang)[:, None] * nn + np.sin(ang)[:, None] * bb
    q0, q1 = c - 0.5 * sep[:, None] * w, c + 0.5 * sep[:, None] * w
    q0[0], q1[0], q0[-1], q1[-1] = a0, a1, b0, b1
    return q0, q1, ang_fim


# ====================================================================================== energia e sinal dos ESC
LAT_SINAL_ESC = -0.75 * D_ESC - 0.5 * D_ESC - D_SINAL - 0.0004    # sinal: ao lado do +14 AWG (eixo uy do ESC)


def _esc_pelo_feixe(cena: _Cena, k: int, b: _Braco, p_ent, ux, uy, fios, nome_ent: str, feixe: _Feixe) -> None:
    """Articulado: os 2 fios de 14 AWG no braço (cada um da sua vaga do feixe à entrada do ESC) e, na placa de cima, o
    PAR ENCOSTADO das vagas de cima (A, B) às ilhas: sobe logo para dentro e torce de modo a chegar com cada fio à sua
    ilha (a atribuição das vagas é a de menos torção)."""
    m = cena.m
    r_e = 0.5 * D_ESC
    p0s = [p_ent + lat * uy + 0.003 * ux for _p, _m, lat in fios]
    for i, (_polo, mat, _lat) in enumerate(fios):
        m.tubo(b.corpo, mat, _curva(feixe.braco(i, p0s[i]), 0.006), D_ESC)
    pads = [cena.pdb_pad(f"el_pdb_esc{k}_{polo}") for polo, _m, _l in fios]
    if any(pd is None for pd in pads):
        return
    nomes = [cena.nome_ancora(f"el_pdb_esc{k}_{polo}", "el_cablagem") for polo, _m, _l in fios]
    alvos = [pd.topo() + np.array([0.0, 0.0, r_e - 0.0002]) for pd in pads]
    pf = feixe.ponta_d
    sx, sy = cena.sinais[k - 1]
    meio = 0.5 * (alvos[0] + alvos[1])
    # sobe por fora da placa de energia até à altura das ilhas e entra de lado (por baixo do que está por cima dela)
    z_v = float(meio[2]) + 0.0006
    via = [0.5 * (pf.ponto("A", 0.010) + pf.ponto("D", 0.010)),
           np.array([float(meio[0]) + 0.014 * sx, float(meio[1]) + 0.014 * sy, z_v]),
           np.array([float(meio[0]) + 0.006 * sx, float(meio[1]) + 0.006 * sy, z_v])]
    melhor = None
    for vg in (("A", "D"), ("D", "A")):
        q0, q1, tor = _par_linhas([pf.ponto(vg[0], -0.006), pf.ponto(vg[1], -0.006)], alvos, via)
        if melhor is None or abs(tor) < abs(melhor[2]):
            melhor = (q0, q1, tor)
    for i, (polo, mat, _lat) in enumerate(fios):
        m.tubo("drone", mat, list(melhor[i]), D_ESC)
        cena.ligar(f"esc{k}_{polo}", nome_ent, nomes[i], b.corpo, p0s[i], "drone", _toque_ilha(pads[i], alvos[i]),
                   "14 AWG", "cabo_esc", k, via="feixe do ombro")


def _desviar(b: _Braco, pts, desvio) -> list:
    """Os pontos de um troço deitado no braço desviados de lado `A` (rampas de 14 mm) entre s_lo e s_hi."""
    if desvio is None:
        return list(pts)
    s_lo, s_hi, A = desvio
    P = _reamostrar([np.asarray(q, dtype=float) for q in pts], 0.002)
    out = []
    for q in P:
        sv = b.s(q)
        if s_lo <= sv <= s_hi:
            w = 1.0
        elif s_hi < sv < s_hi + 0.014:
            w = 1.0 - (sv - s_hi) / 0.014
        elif s_lo - 0.014 < sv < s_lo:
            w = 1.0 - (s_lo - sv) / 0.014
        else:
            w = 0.0
        w = 3.0 * w * w - 2.0 * w ** 3
        out.append(q + A * w * b.n)
    return _simplificar(out, 0.0002)


def _desvio_postes(cena: _Cena, b: _Braco, s_a: float, s_b: float, dz: float, fios_d, folga: float = 0.0006):
    """Postes (espaçadores entre placas) no caminho de um feixe de fios deitado à cota dz (do eixo do braço) entre s_b
    (fora) e s_a (dentro): raios ao longo do braço à altura dos fios, de 1 em 1 mm de lado; devolve (s_lo, s_hi, A) — o
    troço onde há poste e o desvio lateral A (o menor, para um lado ou para o outro) que tira de lá todos os fios
    (`fios_d` = [(δ, r)]) — ou None se o caminho está livre."""
    d_lo = min(d - r for d, r in fios_d) - 0.016
    d_hi = max(d + r for d, r in fios_d) + 0.016
    ds = np.arange(d_lo, d_hi + 1e-9, 0.001)
    L = s_b - s_a
    if L <= 0.004:
        return None
    cantos = np.array([b.p(sv, dv, dz + dzz) for sv in (s_a, s_b) for dv in (d_lo, d_hi) for dzz in (-0.004, 0.004)])
    zona_lo, zona_hi = cantos.min(axis=0) - 0.002, cantos.max(axis=0) + 0.002
    sonda = cena.sonda({b.corpo: np.zeros(3)}, (zona_lo, zona_hi), excluir=_SO_FIOS)
    P = np.array([b.p(s_b, d, dz + dzz) for d in ds for dzz in (-0.0012, 0.0, 0.0012)])
    t = sonda.raios(P, np.repeat((-b.u)[None], len(P), axis=0), L, _lotes=6).reshape(len(ds), 3).min(axis=1)
    s_hit = np.where(np.isfinite(t), s_b - t, -np.inf)            # onde o raio bate (s); −inf = livre até s_a
    bloqueado = s_hit > s_a + 0.001

    def livre(A):
        for d, r in fios_d:
            sel = (ds >= d + A - r - folga) & (ds <= d + A + r + folga)
            if np.any(bloqueado[sel]):
                return False
        return True
    tocados = [any(bloqueado[(ds >= d - r - folga) & (ds <= d + r + folga)]) for d, r in fios_d]
    if not any(tocados):
        return None
    s_post = float(np.max(s_hit[bloqueado]))                     # a face de fora do poste mais de fora
    for A in sorted(np.arange(-0.016, 0.0161, 0.0005), key=abs):
        if livre(A):
            return s_post - 0.012, s_post, float(A)
    return None


def _rasgos_sup(cena: _Cena) -> list:
    """Os RASGOS da placa de cima, medidos (raios verticais numa grelha de 2 mm contra a malha dela): [(lo, hi)] em xy dos
    furos com ≥ 6 mm nos 2 lados que não tocam na borda (em cache na cena)."""
    if "_rasgos" in cena.__dict__:
        return cena.__dict__["_rasgos"]
    out: list = []
    pt = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
    if pt is not None:
        son = cena.sonda({"drone": np.zeros(3)}, (pt.lo - 0.002, pt.hi + 0.002), incluir=re.compile(r"^placa_superior"))
        h = 0.002
        xs = np.arange(float(pt.lo[0]) + h, float(pt.hi[0]) - 0.5 * h, h)
        ys = np.arange(float(pt.lo[1]) + h, float(pt.hi[1]) - 0.5 * h, h)
        P = np.array([[x, y, float(pt.hi[2]) + 0.003] for x in xs for y in ys])
        d = son.raios_verticais(P, -1.0, float(pt.hi[2] - pt.lo[2]) + 0.006)
        furo = ~np.isfinite(d).reshape(len(xs), len(ys))
        visto = np.zeros_like(furo)
        for i0, j0 in zip(*np.nonzero(furo), strict=True):
            if visto[i0, j0]:
                continue
            pilha, cel = [(i0, j0)], []
            visto[i0, j0] = True
            while pilha:
                i, j = pilha.pop()
                cel.append((i, j))
                for a, c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                    if 0 <= a < len(xs) and 0 <= c < len(ys) and furo[a, c] and not visto[a, c]:
                        visto[a, c] = True
                        pilha.append((a, c))
            ii, jj = np.array([c[0] for c in cel]), np.array([c[1] for c in cel])
            if ii.min() == 0 or jj.min() == 0 or ii.max() == len(xs) - 1 or jj.max() == len(ys) - 1:
                continue
            lo, hi = np.array([xs[ii.min()], ys[jj.min()]]), np.array([xs[ii.max()], ys[jj.max()]])
            if np.all(hi - lo >= 0.006):
                out.append((lo, hi))
    cena.__dict__["_rasgos"] = out
    return out


def _pilha_por_rasgos(cena: _Cena) -> bool:
    """A placa de energia fica POR CIMA de uma placa de cima sem janela (o computador de bordo — Portenta — fica entre as
    placas): os cabos dos ESC sobem pelos rasgos da placa de cima, não ao lado da pilha (`_esc_por_rasgos`)."""
    if cena.rpi is not None or cena.fc is not None or cena.computador is None or cena.pdb_massa is None:
        return False
    pt = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
    pad = cena.pdb_pad("el_pdb_esc1_pos")
    return pt is not None and pad is not None and float(pad.lo[2]) > float(pt.hi[2]) and bool(_rasgos_sup(cena))


def _esc_por_rasgos(cena: _Cena, k: int, b: _Braco, sonda: _Sonda, p_ent, ux, uy, nome_ent: str) -> list:
    """ESC do braço k com a placa de energia POR CIMA da placa de cima (build Arduino: o Portenta entre as placas): o par
    14 AWG corre no tubo, deita-se na placa de baixo e vai ENTRE AS PLACAS (mapa 2,5D: contorna os postes, as colunas M3
    da pilha e o Portenta) até por baixo do rasgo da placa de cima que fica do lado da ilha (ao longo do comprimento
    dela), sobe pelo rasgo, deita-se na placa de cima e vai (mapa 2,5D) até à borda da placa de energia, onde sobe e
    assenta na ilha. O par de sinal fica entre as placas, junto à borda do Portenta, num rabicho com ficha JST-GH solta
    (o Portenta não publica ficha para os sinais dos ESC). Devolve as estações das abraçadeiras do braço."""
    m = cena.m
    r_e = 0.5 * D_ESC
    s_e = b.s(p_ent)
    comp, pdb = cena.computador, cena.pdb_massa
    s_lim = max(0.035, _canto(comp, b) + 0.006)
    pt = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
    rasgos = _rasgos_sup(cena)
    z_pb = float(cena.placa.hi[2])
    z_lo_sup, z_top_sup = float(pt.lo[2]), float(pt.hi[2])
    pdb_lo, pdb_hi = pdb.lo, pdb.hi

    def corpo_ate_placa(p0, d_i, r):
        """O troço do braço (perfil do topo do tubo) até ao início do último troço deitado na placa de baixo."""
        prof = _perfil(sonda, b, s_e - 0.012, s_lim + 0.012, d_i, r, 0.005, largura=0.8 * r)
        z_b = z_pb + r + 0.00015
        j0 = len(prof) - 1
        while j0 > 0 and abs(float(prof[j0 - 1][2]) - z_b) < 0.0008:
            j0 -= 1
        return [p0, p0 - 0.006 * ux, *prof[: j0 + 1]], z_b

    def caixa_de(pts, folga):
        P = np.array([np.asarray(q, dtype=float) for q in pts])
        return P.min(axis=0) - folga, P.max(axis=0) + folga

    fios_ = (("pos", "fios_vermelho", -0.75 * D_ESC), ("neg", "fios_preto", 0.45 * D_ESC))
    with m.peca("cabo_esc", k):
        # o SINAL primeiro (os 14 AWG passam-lhe por cima onde se cruzam): entre as placas até à borda do Portenta do lado do braço, ficha JST-GH solta (rabicho)
        sx, sy = cena.sinais[k - 1]
        p0 = p_ent + LAT_SINAL_ESC * uy + 0.003 * ux
        arm, z_b = corpo_ate_placa(p0, b.d(p0), D_SINAL)
        # (a ponta fica por fora da cinta da bateria e longe das colunas M3 da pilha e dos parafusos do Portenta)
        alvo = np.array([sx * 0.0415, sy * (float(comp.hi[1]) + 0.0045), z_b])
        lo, hi = caixa_de([arm[-1], alvo], 0.015)
        mesa_s = _Mesa(cena, lo, hi, z_b, acima=max(0.003, z_lo_sup - z_b - D_SINAL - 0.0003))
        mesa_s.proibir(comp.lo - 0.002, comp.hi + 0.002)
        cam = mesa_s.rota(arm[-1], alvo, D_SINAL + 0.00005, folga=0.00015, soltar=0.002)
        if cam is not None:
            anc_pwm = cena.ponto_ancora(f"el_portenta_pwm{k}")
            if anc_pwm is not None:
                p_pwm = np.asarray(anc_pwm[1], dtype=float)
                p_out = np.array([float(p_pwm[0]), float(p_pwm[1]) + sy * 0.0055, z_b])
                p_in = np.array([float(p_pwm[0]), float(p_pwm[1]) + sy * 0.0020, float(p_pwm[2])])
                linha = [np.asarray(q, dtype=float) for q in _curva([*arm, *cam[1:], p_out, p_in], 0.003)]
                m.par("drone", "fios_branco", "fios_preto", linha, D_SINAL)
                m.caixa("drone", "fios_jst", np.array([float(p_pwm[0]), float(p_pwm[1]) + sy * 0.0012, float(p_pwm[2])]),
                        np.eye(3), [0.0021, 0.0015, 0.0016])
                cena.ligar(f"esc{k}_sinal", nome_ent, f"el_portenta_pwm{k}", b.corpo, p0, "drone", p_pwm,
                           "2 × 28 AWG (par entrançado)", "cabo_esc", k)
            else:
                linha = [np.asarray(q, dtype=float) for q in _curva([*arm, *cam[1:]], 0.004)]
                t = _u(linha[-1] - linha[-2])
                t = _u(np.array([t[0], t[1], 0.0])) if abs(float(t[2])) < 0.9 else np.array([1.0, 0.0, 0.0])
                lat_v = _u(np.cross(EZ, t))
                c = linha[-1] + t * 0.0032 + np.array([0.0, 0.0, 0.0022 - D_SINAL - 0.00005])
                # a ficha ASSENTA no que tiver por baixo (a cinta da bateria, um cabo): a ponta do par sobe o que faltar
                sd = cena.sonda({"drone": np.zeros(3)}, (c - 0.008, c + 0.008), excluir=_SO_FIOS)
                Pf = np.array([c + a * 0.0028 * t + b2 * 0.002 * lat_v for a in (-1.0, 0.0, 1.0) for b2 in (-1.0, 0.0, 1.0)])
                dd = sd.raios(Pf, np.repeat(-EZ[None], len(Pf), axis=0), 0.008)
                sobe = max(0.0, 0.0022 + 0.00015 - float(np.min(dd))) if np.isfinite(dd).any() else 0.0
                if sobe > 0.0:
                    sl = np.concatenate([[0.0], np.cumsum([np.linalg.norm(b2 - a) for a, b2 in itertools.pairwise(linha)])])
                    f = np.clip((sl - (sl[-1] - 0.008)) / 0.008, 0.0, 1.0)
                    linha = [q + sobe * (3.0 * x * x - 2.0 * x ** 3) * EZ for q, x in zip(linha, f, strict=True)]
                    c = c + sobe * EZ
                m.par("drone", "fios_branco", "fios_preto", linha, D_SINAL)
                m.caixa("drone", "fios_jst", c, np.column_stack([t, lat_v, EZ]), [0.0030, 0.0022, 0.0022])
                cena.ctx.registo.notas.setdefault("fios_rabichos", []).append(
                    {"id": f"esc{k}_sinal", "de": nome_ent, "braco": k, "vias": 2, "corpo": "drone",
                     "ponta": [round(float(v), 6) for v in c],
                     "nota": "sinal do ESC (par entrançado) até à borda do Portenta, entre as placas — ficha JST-GH de 2 "
                             "vias solta (o Portenta não publica ficha para os sinais dos ESC)"})
        for polo, mat, lat in fios_:
            pad = cena.pdb_pad(f"el_pdb_esc{k}_{polo}")
            nome_pad = cena.nome_ancora(f"el_pdb_esc{k}_{polo}", "el_cablagem")
            if pad is None:
                continue
            p0 = p_ent + lat * uy + 0.003 * ux
            arm, z_b = corpo_ate_placa(p0, b.d(p0), r_e)
            # o lado por onde se chega à ilha: ao longo do comprimento dela, pela borda da placa de energia desse lado
            eixo = 1 if float(pad.h[1]) >= float(pad.h[0]) else 0
            sgn = 1.0 if float(pad.c[eixo]) >= float(pdb.c[eixo]) else -1.0
            x_p = float(pad.c[1 - eixo])
            cand = [(lo, hi) for lo, hi in rasgos if lo[1 - eixo] + r_e + 0.0015 <= x_p <= hi[1 - eixo] - r_e - 0.0015
                    and sgn * 0.5 * float(lo[eixo] + hi[eixo]) > sgn * float(pad.c[eixo])]
            if not cand:
                warnings.warn(f"detalhes/fios: sem rasgo da placa de cima para o ESC {k} ({polo})", stacklevel=2)
                continue
            lo_r, hi_r = min(cand, key=lambda c: abs(0.5 * float(c[0][eixo] + c[1][eixo]) - float(pad.c[eixo])))
            y_r = 0.5 * float(lo_r[eixo] + hi_r[eixo])

            def P(u, v, z, eixo=eixo):
                """Ponto com a coordenada ao longo da ilha u e a transversal v."""
                q = np.zeros(3)
                q[eixo], q[1 - eixo], q[2] = u, v, z
                return q
            sob = P(y_r, x_p, z_b)
            # 1) entre as placas, do troço deitado até por baixo do rasgo
            lo, hi = caixa_de([arm[-1], sob], 0.015)
            mesa_b = _Mesa(cena, lo, hi, z_b, acima=max(0.003, z_lo_sup - z_b - r_e - 0.0003))
            mesa_b.proibir(comp.lo - 0.002, comp.hi + 0.002)
            cam_b = mesa_b.rota(arm[-1], sob, r_e + 0.00005, folga=0.00015, soltar=0.002)
            # 2) pela placa de cima, da saída do rasgo até à borda da placa de energia
            z_t = z_top_sup + r_e + 0.00015
            borda = float(pdb_hi[eixo]) if sgn > 0 else float(pdb_lo[eixo])
            sai = P(y_r - sgn * 0.004, x_p, z_t)
            chega = P(borda + sgn * (r_e + 0.0025), x_p, z_t)
            lo, hi = caixa_de([sai, chega], 0.012)
            mesa_t = _Mesa(cena, lo, hi, z_t, acima=0.006)
            mesa_t.proibir(pdb_lo - 0.0005, pdb_hi + 0.0005)
            cam_t = mesa_t.rota(sai, chega, r_e + 0.00005, folga=0.00015, soltar=0.002)
            if cam_b is None or cam_t is None:
                warnings.warn(f"detalhes/fios: sem caminho do ESC {k} ({polo}) pelo rasgo da placa de cima", stacklevel=2)
                continue
            # 3) sobe à ilha pela borda e assenta nela (ponta soldada ao longo da ilha)
            alvo = pad.topo() + np.array([0.0, 0.0, r_e - 0.0002])
            z_v = float(alvo[2]) + 0.0004
            fim_ilha = float(pad.hi[eixo]) if sgn > 0 else float(pad.lo[eixo])
            pts = [*arm, *cam_b[1:],
                   P(y_r, x_p, z_b + 0.004), P(y_r, x_p, z_t - 0.002), *cam_t,
                   P(borda + sgn * 0.0010, x_p, z_v), P(fim_ilha, x_p, z_v), alvo]
            linha = _curva(pts, 0.004)
            m.tubo("drone", mat, linha, D_ESC)
            cena.ligar(f"esc{k}_{polo}", nome_ent, nome_pad, b.corpo, p0, "drone", _toque_ilha(pad, alvo),
                       "14 AWG", "cabo_esc", k, via="rasgo da placa de cima")
    return [s_e - 0.05, 0.5 * (s_e + s_lim) + 0.01]


def _alimentacao_e_sinal(cena: _Cena, k: int, b: _Braco, sonda: _Sonda, p_ent, ux, uy, lado: float, nome_ent: str,
                         feixe=None) -> list:
    """Par 14 AWG da entrada do ESC às ilhas da placa de energia e o par entrançado do sinal até à ficha do FC.
    Rígido: correm no topo do tubo e sobem ao lado da pilha. Articulado (`feixe`): do ESC à ponta do feixe no braço e,
    no drone, da outra ponta do feixe (na placa de cima) direitos às ilhas/ficha. Devolve as estações das abraçadeiras
    pedidas no troço do braço (rígido)."""
    if feixe is None and _pilha_por_rasgos(cena):
        return _esc_por_rasgos(cena, k, b, sonda, p_ent, ux, uy, nome_ent)
    m = cena.m
    r_e = 0.5 * D_ESC
    s_e = b.s(p_ent)
    comp = cena.computador if cena.computador is not None else cena.pdb_massa
    s_lim = max(0.035, _canto(comp, b) + 0.006) if comp is not None else 0.05
    fios = (("pos", "fios_vermelho", -0.75 * D_ESC), ("neg", "fios_preto", 0.45 * D_ESC))
    # rígido: os 3 (14 AWG +, −, sinal) sobem ao lado da pilha por 3 pontos de subida — pela MESMA ordem lateral em
    # que chegam do braço (nenhum cruza outro a caminho da pilha); e desviam-se dos postes (espaçadores entre placas)
    subidas = {}
    desvio = None
    if feixe is None:
        sub3 = [_subida(cena, k, i, d=D_ESC) for i in range(3)]
        if all(q is not None for q in sub3):
            lats = {0: -0.75 * D_ESC, 1: 0.45 * D_ESC, 2: LAT_SINAL_ESC}
            ordem_f = sorted(lats, key=lambda i: b.d(p_ent + lats[i] * uy))
            ordem_s = sorted(range(3), key=lambda j: b.d(np.array([sub3[j][0], sub3[j][1], 0.0])))
            subidas = {i: sub3[j] for i, j in zip(ordem_f, ordem_s, strict=True)}
        fios_d = [(b.d(p_ent + (-0.75 * D_ESC) * uy), r_e), (b.d(p_ent + 0.45 * D_ESC * uy), r_e),
                  (b.d(p_ent + LAT_SINAL_ESC * uy), D_SINAL)]
        # os postes estão em cima da placa (dentro do quadro): o troço deitado na placa, de s_lim para fora, até onde
        # o perfil sobe (abraçadeira do canto / tubo) — aí, à altura dos fios, raios ao longo do braço
        ss_p = np.arange(s_lim + 0.012, s_e - 0.020, 0.003)
        if len(ss_p) > 3:
            prof0 = _perfil(sonda, b, float(ss_p[0]), float(ss_p[-1]), 0.0, r_e, 0.005, passo=0.003)
            dzs = np.array([b.dz(q) for q in _reamostrar(prof0, 0.003)])
            sp = np.array([b.s(q) for q in _reamostrar(prof0, 0.003)])
            z0 = float(dzs[0])
            sobe = np.flatnonzero(dzs > z0 + 0.0008)
            s_fora = float(sp[sobe[0]]) - 0.002 if len(sobe) else float(sp[-1])
            if s_fora > s_lim + 0.020:
                desvio = _desvio_postes(cena, b, s_lim + 0.012, s_fora, z0, fios_d)
    # fila indiana até às subidas: o fio que chega mais perto da pilha vai pela faixa de dentro e sobe primeiro (na
    # subida mais perto da chegada); os outros seguem por faixas paralelas, cada uma 4 mm mais para fora, e só entram
    # na folga junto à sua subida (os da frente já subiram) — nenhum passa por cima de outro
    faixas = {}
    if subidas and comp is not None:
        ent = b.p(s_lim + 0.012)
        ordem_r = sorted(subidas, key=lambda i: float(np.linalg.norm(subidas[i][:2] - ent[:2])))
        primeiro, ultimo = subidas[ordem_r[0]], subidas[ordem_r[-1]]
        e_b = np.array([*(ultimo - primeiro), 0.0])
        e_b = e_b / max(float(np.linalg.norm(e_b)), 1e-9)
        c_c = np.array([float(comp.c[0]), float(comp.c[1]), 0.0])
        e_o = np.array([float(primeiro[0]), float(primeiro[1]), 0.0]) - c_c
        e_o = e_o - float(e_o @ e_b) * e_b
        e_o = e_o / max(float(np.linalg.norm(e_o)), 1e-9)
        q0 = np.array([float(primeiro[0]), float(primeiro[1]), 0.0])
        for j, i in enumerate(ordem_r):
            faixas[i] = (j, np.array([float(subidas[i][0]), float(subidas[i][1]), 0.0]))

    def na_faixa(i, chegada, dir_c):
        """Pontos (xy) da faixa do fio i: entra nela a direito na direção em que chega (paralelo aos outros), corre nela
        até ficar à altura da sua subida e vai à subida a direito, ⟂ às faixas (as de dentro já estão vazias ali: os
        fios delas subiram antes)."""
        if i not in faixas:
            return []
        j, q = faixas[i]
        off = (D_ESC + 0.0005) * j * e_o
        t_sub = float((q - q0) @ e_b)
        t_ent = t_sub - 0.010
        M2 = np.array([[float(dir_c[0]), -float(e_b[0])], [float(dir_c[1]), -float(e_b[1])]])
        if abs(float(np.linalg.det(M2))) > 1e-9:
            lam, t_l = np.linalg.solve(M2, (q0 + off - chegada)[:2])
            if lam > 0.0:
                t_ent = min(float(t_l), t_sub)
        res = []
        if j == 0 or t_ent < t_sub - 1e-4:
            res.append(q0 + off + t_ent * e_b)
        if j > 0:
            res.append(q + off)
        if j == 0 and t_ent > t_sub - 1e-4:
            return []
        return res

    def corte_faixa(i, corpo):
        """Se o troço do braço (`corpo`, 3D) já atravessa a faixa do fio i (braços de trás: a faixa fica ao lado da
        pilha e o feixe chega-lhe de viés), o fio deixa o feixe ONDE a cruza pela 1.ª vez e segue nela até à subida
        (os de fora deixam-no primeiro, mais longe: ninguém cruza ninguém) → (nº de pontos a manter, pontos (3D) da
        faixa até ao nível da subida) — ou None."""
        if i not in faixas:
            return None
        j, q = faixas[i]
        off = (D_ESC + 0.0005) * j * e_o
        base = q0 + off
        t_sub = float((q - q0) @ e_b)

        def lado(p):
            return float((np.asarray(p, dtype=float)[:2] - base[:2]) @ e_o[:2])
        for a in range(len(corpo) - 1):
            la, lb = lado(corpo[a]), lado(corpo[a + 1])
            if la > 0.0 >= lb:
                P = corpo[a] + (la / (la - lb)) * (corpo[a + 1] - corpo[a])
                t_c = float((P[:2] - q0[:2]) @ e_b[:2])
                if t_c > t_sub - 0.006:
                    return None
                z = float(P[2])
                res = [P] + ([np.array([*(q + off)[:2], z])] if j > 0 else [])
                return a + 1, res
        return None
    # da subida à ilha: se os 2 caminhos direitos se cruzam, o 2.º passa por cima do 1.º; se só passam rente (as ilhas
    # em fila na direção em que vêm), o da ilha de lá vai por uma faixa paralela à fila, ao lado da ilha de cá, e entra
    # na sua a direito
    ilhas = {}
    for i, (polo, _mat, _lat) in enumerate(fios):
        pad = cena.pdb_pad(f"el_pdb_esc{k}_{polo}")
        if pad is not None and subidas.get(i) is not None:
            ilhas[i] = (np.asarray(subidas[i], dtype=float)[:2], np.asarray(pad.topo(), dtype=float)[:2])
    por_cima, faixa_ilha = False, {}
    if len(ilhas) == 2:
        (s0, a0), (s1, a1) = ilhas[0], ilhas[1]
        if _cruzam_xy(s0, a0, s1, a1):
            por_cima = True
        elif _dist_seg_xy(s0, a0, s1, a1) < D_ESC + 0.0004:
            f = 1 if _dist_seg_xy(a0, a0, s1, a1) < _dist_seg_xy(a1, a1, s0, a0) else 0
            (s_f, a_f), (s_n, a_n) = ilhas[f], ilhas[1 - f]
            e_r = _u([*(a_f - a_n), 0.0])[:2]
            e_p = np.array([-e_r[1], e_r[0]])
            o_f, o_n = float((s_f - a_n) @ e_p), float((s_n - a_n) @ e_p)
            sg = math.copysign(1.0, o_f) if abs(o_f) > 1e-4 else (-math.copysign(1.0, o_n) if abs(o_n) > 1e-4 else 1.0)
            lam = max(abs(o_f), (abs(o_n) if sg * o_n > 0.0 else 0.0) + D_ESC + 0.0004)
            via = [s_f + (sg * lam - o_f) * e_p] if abs(sg * lam - o_f) > 1e-4 else []
            faixa_ilha[f] = [*via, a_f + sg * lam * e_p]
    fio_0 = None
    with m.peca("cabo_esc", k):
        if feixe is not None:
            _esc_pelo_feixe(cena, k, b, p_ent, ux, uy, fios, nome_ent, feixe)
        for i, (polo, mat, lat) in enumerate(fios if feixe is None else ()):
            p0 = p_ent + lat * uy + 0.003 * ux
            d_i = b.d(p0)
            pad = cena.pdb_pad(f"el_pdb_esc{k}_{polo}")
            nome_pad = cena.nome_ancora(f"el_pdb_esc{k}_{polo}", "el_cablagem")
            alvo = None if pad is None else pad.topo() + np.array([0.0, 0.0, r_e - 0.0002])
            sub = subidas.get(i)
            corpo_pts = _desviar(b, _perfil(sonda, b, s_e - 0.012, s_lim + 0.012, d_i, r_e, 0.005,
                                            largura=0.8 * r_e), desvio)
            pts = [p0, p0 - 0.006 * ux, *corpo_pts]
            if alvo is not None and sub is not None:
                z_base = float(corpo_pts[-1][2])
                # da subida à ilha à altura da ponta soldada (+0,4 mm): rente à placa de energia — por baixo do suporte
                # da arma há lugar para o outro fio lhe passar por cima
                z_v = float(alvo[2]) + 0.0004
                if por_cima and i == 1:
                    z_v += D_ESC + 0.0003                       # passa por cima do outro fio a caminho da ilha
                dir_c = _u([*(corpo_pts[-1] - corpo_pts[-2])[:2], 0.0]) if len(corpo_pts) > 1 else -b.u
                # na placa, da ponta do troço do braço à subida: ASSENTA no que lá houver — onde passa por cima de um
                # fio já desenhado (o par de outro braço, o vizinho que entra na faixa dele), sobe-lhe por cima
                todos = [p0, p0 - 0.006 * ux, *corpo_pts]          # (o ESC pode estar já ao pé da pilha: braço curto)
                corte = corte_faixa(i, todos)
                if corte is not None:
                    n_c, faixa_c = corte
                    plano = _assentar(cena, [*faixa_c, np.array([sub[0], sub[1], float(faixa_c[-1][2])])], r_e)
                    pts = [*todos[:n_c], *plano]
                else:
                    plano = _assentar(cena, [corpo_pts[-1], *[np.array([q[0], q[1], z_base])
                                                              for q in na_faixa(i, corpo_pts[-1], dir_c)],
                                             np.array([sub[0], sub[1], z_base])], r_e)
                    pts = [p0, p0 - 0.006 * ux, *corpo_pts[:-1], *plano]
                pts += [np.array([sub[0], sub[1], max(z_v, float(plano[-1][2]) + 0.002)])]
                vias = faixa_ilha.get(i, [0.5 * (np.asarray(sub[:2], dtype=float) + alvo[:2])])
                pts += [np.array([float(v[0]), float(v[1]), z_v]) for v in vias]
                pts += [alvo + np.array([0, 0, min(0.0012, z_v - float(alvo[2]))]), alvo]
            linha = _curva(pts, 0.007)
            if alvo is not None and sub is not None:     # por baixo das peças da arma (base, suporte) até à ilha
                linha = [*_sob_tetos(cena, linha[:-1], r_e, float(alvo[2]) - 0.004), linha[-1]]
            if por_cima and i == 1 and fio_0 is not None and alvo is not None and sub is not None:
                # por cima do 1.º fio onde o cruza, da subida à ilha: à altura exata que o tira dele
                i_top = next((j for j, q in enumerate(linha) if float(q[2]) >= z_v - 0.0005), None)
                if i_top is not None and i_top < len(linha) - 2:
                    linha = [*linha[:i_top], *_sobre_cabos(linha[i_top:-1], [fio_0], r_e, r_e), linha[-1]]
            if i == 0:
                fio_0 = np.asarray(linha, dtype=float)
            m.tubo("drone", mat, linha, D_ESC)
            if alvo is not None and sub is not None:
                cena.ligar(f"esc{k}_{polo}", nome_ent, nome_pad, b.corpo, p0, "drone", _toque_ilha(pad, alvo),
                           "14 AWG", "cabo_esc", k)
        # sinal: par entrançado branco/preto ao lado do vermelho, até à ficha JST-GH do FC
        con = cena.fc_con("el_fc_con_esc")
        nome_con = cena.nome_ancora("el_fc_con_esc", "el_fc_h7")
        lat_s = LAT_SINAL_ESC
        p0 = p_ent + lat_s * uy + 0.003 * ux
        d_s = b.d(p0)
        if feixe is not None:
            # braço: da vaga do feixe à entrada do ESC; drone: da vaga D (por baixo, do lado de dentro) — o par de
            # 14 AWG sai por cima e sobe logo para as ilhas, o sinal fica por baixo dele
            m.par(b.corpo, "fios_branco", "fios_preto", _curva(feixe.braco(2, p0), 0.006), D_SINAL)
            pd = feixe.ponta_d
            pts = [pd.ponto("C", -0.006), pd.ponto("C", 0.004), pd.ponto("C", 0.016)]
            c_ini, p_ini = b.corpo, p0
        else:
            corpo_pts = _desviar(b, _perfil(sonda, b, s_e - 0.012, s_lim + 0.012, d_s, D_SINAL, 0.005,
                                            largura=D_SINAL), desvio)
            pts = [p0, p0 - 0.006 * ux, *corpo_pts]
            sub = subidas.get(2) if subidas else _subida(cena, k, 2, d=2 * D_SINAL)
            if sub is not None:
                z_b = float(pts[-1][2])
                dir_c = _u([*(corpo_pts[-1] - corpo_pts[-2])[:2], 0.0]) if len(corpo_pts) > 1 else -b.u
                todos = [p0, p0 - 0.006 * ux, *corpo_pts]
                corte = corte_faixa(2, todos)
                if corte is not None:
                    n_c, faixa_c = corte
                    plano = _assentar(cena, [*faixa_c, np.array([sub[0], sub[1], float(faixa_c[-1][2])])], D_SINAL)
                    pts = [*todos[:n_c], *plano]
                else:
                    plano = _assentar(cena, [corpo_pts[-1], *[np.array([q[0], q[1], z_b])
                                                              for q in na_faixa(2, corpo_pts[-1], dir_c)],
                                             np.array([sub[0], sub[1], z_b])], D_SINAL)
                    pts = [*pts[:-1], *plano]
            c_ini, p_ini = "drone", p0
        if con is not None and cena.fc is not None:
            sx, sy = cena.sinais[k - 1]
            z_c = float(con.c[2])
            z_cima = float(cena.fc.hi[2]) + 0.0035
            x_tras = float(con.lo[0]) - 0.0075
            # à ficha: os da frente por fora (dy ±3,4 mm), os de trás por dentro (±1,1)
            dy = {(1.0, 1.0): 0.0034, (1.0, -1.0): -0.0034, (-1.0, 1.0): 0.0011, (-1.0, -1.0): -0.0011}.get((sx, sy), 0.0)
            x_0 = float(pts[-1][0])
            if feixe is None and sx < 0 and x_0 < x_tras:
                # rígido, braço de trás: sobe atrás do Pi e segue direito para a frente até à ficha (por dentro dos 14 AWG)
                y_0 = float(pts[-1][1])
                pts += [np.array([x_0, y_0, z_cima]), np.array([x_0 + 0.006, y_0, z_cima]),
                        np.array([x_tras - 0.004, float(con.c[1]) + dy, z_c + 0.002]),
                        np.array([float(con.lo[0]) - 0.003, float(con.c[1]) + dy, z_c])]
            else:
                # ao lado do FC: uma faixa por braço desse lado (os de trás 1,9 mm mais acima e viram 3 mm mais atrás)
                faixa = (1 if feixe is None else -1) if sx < 0 else 0
                # (build acessível: +0,25 mm — a placa de energia, vermelha, tem lá o canto; com os Pico, +0,65 mm; e do
                # lado −y, onde o par de 5 V do Pi se junta a este com uma abraçadeira, +0,6 mm em todos: a fita dela,
                # de pé ao lado do sinal, passava 0,3–0,5 mm pela borda da placa de energia — medido)
                folga_l = (0.00345 if _pico_lados(cena) else 0.00305) if cena.servo_pwm else \
                    (0.0034 if sy < 0 else 0.0028)
                y_lado = float(cena.fc.c[1]) + sy * (float(cena.fc.h[1]) + folga_l)
                z_l = z_cima + 0.0019 * faixa
                x_t = x_tras - 0.003 * abs(faixa)
                if feixe is not None:
                    # da ponta do feixe em diagonal (a subir) ao início da faixa: os da frente a 45°, os de trás direitos
                    # ao fim dela (a ficha fica atrás)
                    x_l = x_0 - sx * abs(float(pts[-1][1]) - y_lado) if sx > 0 else x_t
                    # (os da frente entram na faixa à frente do FC: a ficha dos sensores, na borda dele, fica livre)
                    x_0 = max(x_l, x_t, float(cena.fc.hi[0]) - 0.002) if sx > 0 else x_t
                    pts += [np.array([x_0, y_lado, z_l])]
                else:
                    pts += [np.array([x_0, float(pts[-1][1]), z_l]), np.array([x_0, y_lado, z_l])]
                # (no build acessível o troço que entra na ficha vem 2,5 mm mais alto e só desce à entrada dela: por
                # baixo passam os cabos dos servos do cotovelo, por cima o cabo PWM)
                dz_e = 0.0025 if cena.servo_pwm else 0.0
                pts += [np.array([x_t, y_lado, z_l]), np.array([x_t - 0.002, float(con.c[1]) + dy, z_c + dz_e])]
                if dz_e:
                    pts.append(np.array([float(con.lo[0]) - 0.0065, float(con.c[1]) + dy, z_c + dz_e]))
                pts.append(np.array([float(con.lo[0]) - 0.003, float(con.c[1]) + dy, z_c]))
                cena.sinal_lado[k] = (y_lado, z_l, x_0, x_t)        # o troço direito ao lado do FC (o 5 V junta-se)
            m.par("drone", "fios_branco", "fios_preto", _curva(pts, 0.006), D_SINAL)
            cena.ligar(f"esc{k}_sinal", nome_ent, nome_con, c_ini, p_ini, "drone",
                       [float(con.lo[0]), float(con.c[1]) + dy, z_c], "2 × 28 AWG (par entrançado)", "cabo_esc", k)
        else:
            m.par("drone", "fios_branco", "fios_preto", _curva(pts, 0.006), D_SINAL)
    if feixe is None:
        return [s_e - 0.05, 0.5 * (s_e + s_lim) + 0.01]
    return []


# ====================================================================================== braços — RÍGIDO
def _fases_soldadas(cena: _Cena, k: int, fins) -> None:
    """ESC 4 em 1: a continuação de cada fio do motor k desde a ponta estanhada (`mot{k}_fio_fim_{a,b,c}`) até à ilha
    dessa fase, soldada (menisco de estanho), só onde a ilha está ACESSÍVEL (nada por cima dela até acima do topo do
    braço: raios para cima a partir da ilha). As ilhas do 4 em 1 são as de estanho da peça `esc` da eletrónica; enquanto
    ficarem debaixo do braço de carbono (5″, 2026-10-20: as ilhas a z 3,3–3,6 mm e os braços de 1,17 a 4,67 mm por cima
    delas) não há caminho — fica registado em `notas["fios_pendentes"]` e não se desenha nada (o fio do motor acaba na
    ponta estanhada dele)."""
    ilhas = [cena.ponto_ancora(f"el_esc_motor{k}_{f}") for f in "abc"]
    if not all(a is not None for a in ilhas):
        cena.ctx.registo.notas.setdefault("fios_pendentes", []).append(
            {"id": f"fases{k}", "de": [f"mot{k}_fio_fim_{f}" for f in "abc"], "para": "ilhas do ESC 4 em 1",
             "nota": "as ilhas das fases do 4 em 1 (estanho da peça `esc`) ficam debaixo do braço de carbono — sem "
                     "acesso para a solda; à espera de a eletrónica pôr o 4 em 1 por cima dos braços (ou publicar "
                     "`el_esc_motor{k}_{a,b,c}` acessíveis)"})
        return
    son = cena.sonda({"drone": np.zeros(3)}, (np.min([np.asarray(a[1]) for a in ilhas], axis=0) - 0.01,
                                              np.max([np.asarray(a[1]) for a in ilhas], axis=0) + 0.02),
                     excluir=_SO_FIOS)
    m = cena.m
    cx_esc = float(cena.esc4.c[0]) if cena.esc4 is not None else float(cena.placa.c[0])
    sx, sy = cena.sinais[k - 1]
    with m.peca("cabo_fases", k):
        for j, (f, fim, ilha) in enumerate(zip("abc", fins, ilhas, strict=True)):
            _c, p_t, d_t = fim
            _c2, q_i, _d_i = ilha
            p_t, d_t, q_i = np.asarray(p_t, dtype=float), _u(d_t), np.asarray(q_i, dtype=float)
            r = 0.0019 / 2.0
            if son.raio(q_i + np.array([0.0, 0.0, 0.0003]), EZ, max(0.004, float(p_t[2]) - float(q_i[2]) + 0.004)) \
                    is not None:
                continue
            z_alto = max(float(p_t[2]), float(q_i[2])) + 0.0015
            alvo = q_i + np.array([0.0, 0.0, 0.00055])
            x_corr = cx_esc + sx * (0.0240 + 0.0022 * j)
            p1 = p_t + 0.0030 * d_t
            pts = [p_t - 0.0030 * d_t, p_t + 0.0005 * d_t, p1,
                   np.array([x_corr, float(p1[1]) - sy * 0.0050, z_alto]),
                   np.array([x_corr, float(alvo[1]), z_alto]),
                   np.array([cx_esc + sx * 0.0195, float(alvo[1]), z_alto - 0.0004]), alvo]
            m.tubo("drone", "fios_preto", _curva(pts, 0.003), 2.0 * r)
            m.tubo("drone", "fios_estanho", [alvo - np.array([sx * 0.0012, 0.0, 0.0]),
                                             alvo + np.array([sx * 0.0012, 0.0, 0.0])], D_SOLDA, lados=10, cabo=False)
            geom_p = str((cena.ancoras.get(f"mot{k}_fio_fim_{f}") or {}).get("geom", f"motor{k}_fase_{f}_ponta"))
            cena.ligar(f"fase{k}_{f}", geom_p, f"el_esc_motor{k}_{f}", "drone", p_t, "drone", q_i,
                       "18 AWG (o fio do motor, soldado)", "cabo_fases", k)


def _braco_rigido(cena: _Cena, k: int) -> None:
    ctx, m = cena.ctx, cena.m
    mot = cena.caixa(f"motor{k}")
    if mot is None or cena.placa is None:
        return
    gb = ctx.geom_existente(f"braco{k}")
    z_eixo = float(gb.pos[2]) if gb is not None else float(cena.placa.c[2])
    o = np.array([cena.placa.c[0], cena.placa.c[1], z_eixo])
    u = _u([mot.c[0] - o[0], mot.c[1] - o[1], 0.0])
    n = np.array([-u[1], u[0], 0.0])
    h0 = 0.05 if cena.z_sup is None else min(0.05, cena.z_sup - 0.0025 - z_eixo)
    b = _Braco(k, "drone", o, u, n, h0=h0)
    s_mot = b.s(mot.c)
    a0, a1 = b.p(0.03), b.p(s_mot + 0.05)
    teto = None if cena.z_sup is None else cena.z_sup - 0.002
    sonda = cena.sonda({"drone": np.zeros(3)}, (np.minimum(a0, a1) - 0.06, np.maximum(a0, a1) + 0.06), teto=teto)
    # o eixo do tubo DESENHADO (a caixa com massa do braço fica no plano da placa, o tubo da estrutura mais abaixo)
    medidas = [_eixo_tubo(sonda, b, f * s_mot) for f in (0.30, 0.40, 0.50, 0.60, 0.70)]
    medidas = [x for x in medidas if 0.004 <= x[1] <= 0.02]
    if medidas:
        z_eixo += float(np.median([x[0] for x in medidas]))
        o = np.array([o[0], o[1], z_eixo])
        h0 = 0.05 if cena.z_sup is None else min(0.05, cena.z_sup - 0.0025 - z_eixo)
        b = _Braco(k, "drone", o, u, n, h0=h0)
    sonda_est = _sonda_estacoes(cena, b, 0.0, s_mot + 0.03)
    saidas = cena.esc_saidas(k, u, "drone")
    if saidas is None:
        return
    corpo_esc, p_ent, p_fas, ux, uy, nome_ent, nome_fas = saidas
    lado = 1.0 if k % 2 == 1 else -1.0
    r_f = 0.5 * D_FASE
    balas = cena.balas(k)
    fins = [cena.ponto_ancora(f"mot{k}_fio_fim_{f}") for f in "abc"]
    if balas is None and p_ent is None and all(a is not None for a in fins):
        # ESC 4 em 1 (5″): os 3 fios do motor (módulo `motores`, pontas estanhadas `mot{k}_fio_fim_*`) vão SOLDADOS
        # direto às ilhas dele — nada de balas, extensões nem do troço de reserva
        _fases_soldadas(cena, k, fins)
        return
    # ---------------- FASES: rabicho laranja do ESC → emenda (termo) → extensão → fêmea na bala do motor
    s_f = b.s(p_fas)
    s_fim = (min(b.s(q[1]) for q in balas) - 0.035) if balas is not None else s_mot - float(mot.h[0]) - 0.012
    curto = s_fim < s_f + 0.020           # as balas do motor logo ao pé das ilhas (ESC 4 em 1 no centro): ponte curta
    emendas = []
    with m.peca("cabo_fases", k):
        for i, lat in enumerate((-1.07 * D_FASE, 0.0, 1.07 * D_FASE)):
            p0 = p_fas + lat * uy - 0.003 * ux
            d_i = b.d(p0)
            # o perfil do topo vai até perto do ponto de aproximação à bala (não só até s_fim): a abraçadeira do suporte
            # do motor fica nesse troço e o cabo tem de lhe passar por cima
            s_fim_i = s_fim
            if balas is not None and not curto:
                c_b, p3, dv, r_c = balas[i]
                s_ap = b.s(np.asarray(p3, dtype=float) + 0.024 * np.asarray(dv, dtype=float)) - 0.003
                s_fim_i = max(s_fim, min(s_ap, s_fim + 0.030))
            corpo_pts = [] if curto else _perfil(sonda, b, s_f + 0.012, s_fim_i, d_i, r_f, 0.005)
            pts = [p0, p0 + 0.006 * ux, *corpo_pts]
            caixa_f = cena.caixa(nome_fas) if nome_fas == "esc" else None
            direto_esc = balas is not None and b.s(np.asarray(balas[i][1], dtype=float)) <= s_f + 0.003
            if curto and balas is not None and (direto_esc or (caixa_f is not None and
                    caixa_f.contem(np.asarray(balas[i][1]) + 0.011 * np.asarray(balas[i][2]), tol=0.0005))):
                # as balas do motor acabam logo na saída do ESC (X500/compacto) ou dentro da pegada do 4 em 1: só a fêmea
                # enfiada nelas — sem extensão
                c_b, p3, dv, r_c = balas[i]
                ent = _bala_femea_curta(cena, "drone", p3, dv, r_c)
                cena.ligar(f"fase{k}_{'abc'[i]}", nome_fas, f"motor{k}_fase_{'abc'[i]}_conector", corpo_esc,
                           p0 if direto_esc else ent, c_b, p3 - 0.001 * dv,
                           "16 AWG (fêmea de 3,5 mm na saída do ESC)", "cabo_fases", k)
                continue
            if balas is not None:
                c_b, p3, dv, r_c = balas[i]
                ent = _bala_femea(cena, "drone", p3, dv, r_c)
                pts += [ent + (0.006 if curto else 0.016) * dv, ent]
                if curto:
                    pts = [pts[0], *pts[2:]]
                destino, c_dest, p_dest = f"motor{k}_fase_{'abc'[i]}_conector", c_b, p3 - 0.001 * dv
            else:
                z_b = float(mot.lo[2]) - z_eixo + 0.0025
                pts += [b.p(s_mot - float(mot.h[0]) + 0.003, 0.7 * d_i, max(z_b, b.dz(corpo_pts[-1])))]
                destino, c_dest, p_dest = cena.nome_ancora(f"motor{k}", None), "drone", pts[-1]
            linha = _curva(pts, 0.008)
            m.tubo("drone", "fios_laranja", linha, D_FASE)
            cena.ligar(f"fase{k}_{'abc'[i]}", nome_fas, destino, corpo_esc, p0, c_dest, p_dest, "16 AWG",
                       "cabo_fases", k)
            emendas.append((linha, i))
        # emendas do rabicho de fábrica, desencontradas 18 mm (não engrossam o feixe), só onde o troço chega; a termo
        # (0,45 mm mais grossa do que o cabo) ASSENTA no que o cabo tem por baixo (o tubo, uma maxila): sobe o que
        # faltar, medido com raios para baixo, até à folga dela ao cabo (o cabo, flexível, levanta esses décimos)
        r_tm = 0.5 * (D_FASE + 0.0009)
        for linha, i in emendas:
            s_j = s_f + L_RABICHO + (i - 1) * 0.018
            if s_j < s_fim - 0.012:
                troco = _troco_s(linha, b, s_j - 0.008, s_j + 0.008)
                if len(troco) >= 2:
                    m.tubo("drone", "fios_termo", _assentar_manga(sonda, troco, r_tm, r_f), 2.0 * r_tm, cabo=False)
    # ---------------- ALIMENTAÇÃO 14 AWG + SINAL (par entrançado)
    estacoes_e = []
    if p_ent is not None:
        estacoes_e = _alimentacao_e_sinal(cena, k, b, sonda, p_ent, ux, uy, lado, nome_ent)
    # ---------------- abraçadeiras: fases no tubo, alimentação no tubo, e o ESC preso ao tubo
    r_t = sonda.r_tubo if sonda.r_tubo else 0.0125
    usadas: list[float] = []
    for s_ab in (s_f + 0.115, 0.5 * (s_f + s_fim) + 0.03, s_fim - 0.025):
        sv = _estacao_livre(cena, b, sonda_est, s_ab, s_f + 0.02, s_fim - 0.01, r_t + 0.0006)
        if sv is not None and all(abs(sv - q) > 0.03 for q in usadas):
            usadas.append(sv)
            _abracadeira_braco(cena, b, sv, lado, f"braço {k}: fases")
    if p_ent is not None:
        s_e = b.s(p_ent)
        comp = cena.computador if cena.computador is not None else cena.pdb_massa
        s_lim = max(0.035, _canto(comp, b) + 0.006) if comp is not None else 0.05
        for s_ab in estacoes_e:
            sv = _estacao_livre(cena, b, sonda_est, s_ab, s_lim + 0.015, s_e - 0.015, r_t + 0.0006)
            if sv is not None and all(abs(sv - q) > 0.03 for q in usadas):
                usadas.append(sv)
                _abracadeira_braco(cena, b, sv, -lado, f"braço {k}: alimentação do ESC")


def _assentar_manga(sonda: _Sonda, troco, r_ext: float, r_int: float) -> list:
    """O troço de uma manga/termo de raio r_ext à volta de um cabo de raio r_int, subido (em +z) o que faltar para a
    manga não entrar no que o cabo tem por baixo — medido com raios para baixo do eixo, no eixo e a ±60 % do raio para
    os lados; no máximo a folga r_ext − r_int (o cabo fica encostado ao topo dela)."""
    P = [np.asarray(q, dtype=float) for q in troco]
    amostras = []
    for a, b in itertools.pairwise(P):
        t = _u(b - a)
        lat = _u(np.cross(t, EZ)) if abs(float(t[2])) < 0.9 else np.array([1.0, 0.0, 0.0])
        for f in np.linspace(0.0, 1.0, 5):
            q = a + f * (b - a)
            amostras += [q, q + 0.6 * r_ext * lat, q - 0.6 * r_ext * lat]
    A = np.array(amostras)
    d = sonda.raios(A, np.repeat(-EZ[None], len(A), axis=0), r_ext + 0.003)
    if not np.isfinite(d).any():
        return P
    alt = np.where(np.arange(len(A)) % 3 == 0, r_ext, r_ext * 0.8)          # (a ±60 % do raio a casca está a 0,8 r)
    falta = float(np.max(np.where(np.isfinite(d), alt + 0.00015 - d, -1.0)))
    sobe = min(max(0.0, falta), max(0.0, r_ext - r_int))
    return [q + sobe * EZ for q in P]


def _troco_livre(sonda: _Sonda, a, b, r: float, n_ang: int = 16) -> bool:
    """O tubo de raio r de a a b não toca em nada da sonda: raios ao longo dele, pelo eixo e por n_ang geratrizes."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    v = b - a
    L = float(np.linalg.norm(v))
    if L < 1e-6:
        return True
    t = v / L
    e1 = _u(np.cross(t, EZ) if abs(t[2]) < 0.9 else np.cross(t, [1.0, 0.0, 0.0]))
    e2 = np.cross(t, e1)
    P = [a] + [a + r * (math.cos(f) * e1 + math.sin(f) * e2) for f in np.linspace(0, 2 * math.pi, n_ang, endpoint=False)]
    d = sonda.raios(np.array(P), np.repeat(t[None], len(P), axis=0), L, _lotes=4)
    return not bool(np.any(np.isfinite(d)))


def _travessia_ombro(cena: _Cena, k: int, S, M, A_d, r_h: float):
    """O feixe do ombro cruza a junta no ponto do EIXO que a estrutura publica (`ombro{k}_eixo_cabos`: fixo nos dois
    corpos, fora da dobradiça) e chega lá na direção da ponta do feixe no braço — o troço do braço roda com ele à
    volta desse ponto e nunca passa perto do drone. Do lado do drone, medido com raios: a ponta W2 fica na placa de
    cima, logo para dentro da pegada do servo do ombro (a apontar para o centro); o feixe corre por baixo do servo, à
    altura do meio da folga entre a placa e o servo, no x (entre o centro e a junta) com mais folga dos dois lados,
    sai para lá da borda da placa e desce até ao ponto do eixo. Devolve (X, pontos de W2 a X, dir_d) ou None."""
    anc = (cena.ctx.registo.notas.get("ancoras") or {}).get(f"ombro{k}_eixo_cabos")
    if anc is None or str(anc.get("corpo", "drone")) != "drone" or cena.z_sup is None:
        return None
    X = np.asarray(anc["ponto"], dtype=float)
    ex, ey = M @ np.array([1.0, 0.0, 0.0]), M @ np.array([0.0, 1.0, 0.0])      # para fora (canónicos)
    t0 = _u([float(A_d[0] - X[0]), float(A_d[1] - X[1]), 0.0])
    P_a = X - 0.020 * t0

    def Pc(cx, cy, z):                     # canónico (relativo ao eixo do ombro) → drone
        return np.array([S[0], S[1], 0.0]) + cx * ex + cy * ey + np.array([0.0, 0.0, z])
    cy0, cy1 = -0.085, max(0.0, float(np.dot(X - S, ey)))
    q0, q1 = Pc(-0.050, cy0, float(S[2]) - 0.01), Pc(0.008, cy1 + 0.008, cena.z_sup + 0.020)
    sonda = cena.sonda({"drone": np.zeros(3)}, (np.minimum(q0, q1), np.maximum(q0, q1)), excluir=_SO_FIOS)
    ys = np.arange(cy0, cy1 + 1e-9, 0.003)
    z0 = cena.z_sup + 0.006

    def corredor(cxs):
        """Para cada x candidato: (folga vertical, y de entrada, y de saída, cota) pelos raios verticais a partir de
        pouco acima da placa: o que está por baixo (topo da placa; acaba na borda) e por cima (servo, suportes)."""
        G = np.array([Pc(cx, cy, z0) for cx in cxs for cy in ys])
        dn = sonda.raios_verticais(G, -1.0, 0.030).reshape(len(cxs), len(ys))
        up = sonda.raios_verticais(G, 1.0, 0.030).reshape(len(cxs), len(ys))
        out = []
        for i, cx in enumerate(cxs):
            z_pl = z0 - dn[i]
            na_placa = np.isfinite(dn[i]) & (np.abs(z_pl - cena.z_sup) < 0.004)
            tecto = np.where(np.isfinite(up[i]), z0 + up[i], np.inf)
            if not np.any(na_placa):
                continue
            z_top = float(np.median(z_pl[na_placa]))
            com_servo = np.flatnonzero(tecto < z_top + 0.020)
            if not len(com_servo):
                continue
            i_s0 = int(com_servo[0])
            borda = np.flatnonzero(~na_placa & (np.arange(len(ys)) > i_s0))
            if not len(borda):
                continue
            y_in = float(ys[i_s0]) - r_h - 0.0035
            y_out = float(ys[int(borda[0])]) + r_h + 0.0025
            sel = (ys >= y_in) & (ys <= y_out)
            folga_v = float(np.min(tecto[sel])) - z_top
            if folga_v < 2.0 * r_h + 0.0008 or not np.all(na_placa[sel & (ys < float(ys[int(borda[0])]))]):
                continue
            out.append((float(cx), y_in, y_out, z_top + 0.5 * min(folga_v, 0.030), folga_v))
        return out

    def lateral(cx, y_in, y_out, z_c, alturas):
        L = np.array([Pc(cx, cy, z_c + dz) for cy in np.arange(y_in, y_out + 1e-9, 0.0015) for dz in alturas])
        dl = np.minimum(sonda.raios(L, np.repeat(-ex[None], len(L), axis=0), 0.03, _lotes=12),
                        sonda.raios(L, np.repeat(ex[None], len(L), axis=0), 0.03, _lotes=12))
        return float(np.min(dl))

    def valida(c):
        cx, y_in, y_out, z_c, folga_v = c
        lat = lateral(cx, y_in, y_out, z_c, (-0.7 * r_h, 0.0, 0.7 * r_h))
        if lat < r_h + 0.0006:
            return None
        a, b = Pc(cx, y_in, z_c), Pc(cx, y_out, z_c)
        if not (_troco_livre(sonda, a, b, r_h + 0.0003) and _troco_livre(sonda, b, P_a, r_h + 0.0003)):
            return None
        return (min(lat, 0.5 * folga_v), cx, y_in, y_out, z_c)

    melhor = None
    # os 4 braços são (quase) simétricos: o x do corredor do primeiro braço é a 1.ª tentativa dos outros
    if getattr(cena, "trav_cx", None) is not None:
        cand = corredor([cena.trav_cx])
        melhor = valida(cand[0]) if cand else None
    if melhor is None:
        cands = corredor(np.arange(-0.020, -0.0451, -0.003))
        cands.sort(key=lambda c: -min(lateral(c[0], c[1], c[2], c[3], (0.0,)), 0.5 * c[4]))
        for c in cands:
            melhor = valida(c)
            if melhor is not None:
                break
    if melhor is None:
        warnings.warn(f"fios: braço {k} — sem corredor medido do feixe do ombro até `ombro{k}_eixo_cabos`",
                      stacklevel=2)
        return None
    cena.trav_cx = melhor[1]
    _nota, cx, y_in, y_out, z_c = melhor
    # a ponta W2 (16 mm para dentro de W1, com a termo-retráctil de Ø 10,2) não toca em nada: W1 recua para dentro
    # (menos y canónico) até o troço W1–W2 ficar livre (parafusos dos suportes do servo)
    r_t = 0.5 * (D_FEIXE + 0.0012) + 0.0003
    D = Pc(cx, y_out, z_c)
    W1 = Pc(cx, y_in, z_c)
    L_w = 0.026                              # W1–W2: a curva (raio 12) e a termo-retráctil (14 mm) cabem no troço
    for y_w in np.arange(y_in, y_in - 0.0241, -0.0015):
        q = Pc(cx, y_w, z_c)
        if _troco_livre(sonda, q - 0.010 * ex, q - (L_w + 0.003) * ex, r_t) and _troco_livre(sonda, q, W1,
                                                                                              r_h + 0.0003):
            W1 = q
            break
    W2 = W1 - L_w * ex
    return X, [W2, W1, D, P_a, X], -ex


def _travessia_ombro_fuso(cena: _Cena, k: int, M, r_h: float):
    """Build ACESSÍVEL (ombro de fuso): o feixe cruza a junta no ponto do eixo que a estrutura publica
    (`ombro{k}_eixo_cabos`, 9 mm por fora do braço de fora da alavanca) e, do lado do drone, faz o corredor que ela
    mediu em todo o curso: SOBE 30 mm a direito, corre para dentro por cima do eixo do ombro (≥ 7 mm às alavancas e ao
    cubo, que rodam à volta dele) até à borda da placa de cima, desce em diagonal para a placa e segue deitado nela até à
    ponta W2 (a apontar para o centro, onde os cabos se separam — o mesmo sítio da ponta no articulado de DYNAMIXEL).
    Devolve (X, pontos de W2 a X, dir_d) ou None."""
    anc = (cena.ctx.registo.notas.get("ancoras") or {}).get(f"ombro{k}_eixo_cabos")
    pl = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
    if anc is None or str(anc.get("corpo", "drone")) != "drone" or cena.z_sup is None or pl is None:
        return None
    X = np.asarray(anc["ponto"], dtype=float)
    ex = M @ np.array([1.0, 0.0, 0.0])
    z_mesa = cena.z_sup + 0.0012 + r_h + 0.0002
    z_alto = float(X[2]) + 0.030
    xa, ya = abs(float(X[0])), abs(float(X[1]))
    xp, yp = float(pl.hi[0]), float(pl.hi[1])             # a placa de cima é simétrica: as bordas no quadrante +,+

    def P(x, y, z):
        return M @ np.array([x, y, 0.0]) + np.array([0.0, 0.0, z])
    y_w = min(yp - 0.038, 0.0521)
    # deitado na placa (com a termo-retráctil da ponta, Ø + 1,2): assenta no que lá houver (cabeças dos parafusos)
    r_t = r_h + 0.0006
    deitado = _drapejar(cena, [P(xa - 0.058, y_w, z_mesa + 0.0006), P(xa - 0.032, y_w, z_mesa + 0.0006),
                               P(xp - 0.004, yp - 0.010, z_mesa + 0.0006)], r_t, acima=0.008)
    pts = [*deitado, P(xa, yp + 0.014, max(z_alto, float(deitado[-1][2]) + 0.004)), P(xa, ya, z_alto),
           P(xa, ya, float(X[2]) + 0.012), X]
    return X, pts, -ex


# ====================================================================================== braços — ARTICULADO
def _folga_eixo(cena: _Cena, corpo_pai: str, corpo_filho: str, origem_filho, sinal: float, t_max: float = 0.10) -> float:
    """|t| a partir do qual o EIXO da junta (y do corpo, pela origem do filho) está livre do lado `sinal`: um raio sobre o
    próprio eixo, de fora para dentro, contra as peças visíveis dos dois corpos (primitivas e malhas)."""
    o = np.asarray(origem_filho, dtype=float)
    meia = np.array([0.003, t_max + 0.002, 0.003])     # só o que está à volta do próprio eixo
    sonda = cena.sonda({corpo_pai: np.zeros(3), corpo_filho: o}, (o - meia, o + meia),
                       excluir=re.compile(r"^fios_|^perna|^helice", re.IGNORECASE))
    dist = sonda.raio(o + np.array([0.0, sinal * t_max, 0.0]), [0.0, -sinal, 0.0], t_max)
    return t_max - dist if dist is not None else 0.0


def _estrutura_ativa(cena: _Cena, k: int, junta: str) -> bool:
    g = cena.ctx.geom_existente(f"servo_{junta}{k}")
    return g is not None and not _visivel(g)


def _servo_conectores(cena: _Cena, k: int, junta: str):
    """[(corpo, ponto na face da ficha JST EH, direção para fora, nome da âncora)] dos 2 conectores do servo: as âncoras
    que a `estrutura` publica em `registo.notas["ancoras"]` (`servo_{junta}{k}_ficha_a/b`), ou a fórmula do XH430
    desenhado por ela (deitado na placa de cima no ombro; no cotovelo com o eixo no da junta), ou a face da caixa com
    massa — e então publicam-se aqui, marcadas «fios (fórmula)», para as ligações terem âncora."""
    ctx = cena.ctx
    nomes = [f"servo_{junta}{k}_ficha_{x}" for x in ("a", "b")]
    pub = [cena.ponto_ancora(nm) for nm in nomes]
    if all(p is not None for p in pub):
        return [(c, p, d, nm) for (c, p, d), nm in zip(pub, nomes, strict=True)]
    sx, sy = cena.sinais[k - 1]
    M = np.diag([sx, sy, 1.0])
    x0 = HORN_TOPO - SERVO_H
    nome = f"servo_{junta}{k}"
    out = None
    if junta == "ombro":
        if _estrutura_ativa(cena, k, junta) and cena.z_sup is not None:
            P = np.array(ctx.corpo(f"braco{k}").pos, dtype=float)
            o = P + M @ np.array([-0.014, -0.028, 0.0])
            o[2] = cena.z_sup + 0.0012 + 0.003
            out = [("drone", o + M @ np.array([x0 - 0.0056, lado * 0.0068, 0.0262]), M @ np.array([-1.0, 0.0, 0.0]))
                   for lado in (-1.0, 1.0)]
        else:
            cx = cena.caixa(nome)
            if cx is None:
                return None
            x = cx.lo[0] if sx > 0 else cx.hi[0]
            out = [("drone", np.array([x, cx.c[1] + lado * 0.0068, cx.lo[2] + 0.010]), np.array([-sx, 0.0, 0.0]))
                   for lado in (-1.0, 1.0)]
    else:
        L = np.array(ctx.corpo(f"mastro{k}").pos, dtype=float)
        if _estrutura_ativa(cena, k, junta):
            out = [(f"braco{k}", L + M @ np.array([x0 - 0.0056, -0.5 * SERVO_D + 0.0262, lado * 0.0068]),
                    M @ np.array([-1.0, 0.0, 0.0])) for lado in (-1.0, 1.0)]
        else:
            cx = cena.caixa(nome)
            if cx is None:
                return None
            x = cx.lo[0] if sx > 0 else cx.hi[0]
            out = [(f"braco{k}", np.array([x, cx.c[1], cx.c[2] + lado * 0.0068]), np.array([-sx, 0.0, 0.0]))
                   for lado in (-1.0, 1.0)]
    res = []
    for (c, p, d), nm in zip(out, nomes, strict=True):
        cena.ancoras.setdefault(nm, {"corpo": c, "ponto": [float(v) for v in p], "direcao": [float(v) for v in d],
                                     "fonte": "fios (fórmula do XH430)"})
        res.append((c, p, d, nm))
    return res


def _tipo_servo(hw, junta: str) -> str | None:
    """Tipo do atuador de uma junta no catálogo do mecanismo («servo_pwm», «motorredutor_dc», …) — None se não há."""
    try:
        sv = getattr(getattr(hw.bracos, junta), "servo", None)
        return (getattr(sv, "dados", None) or {}).get("tipo")
    except AttributeError:
        return None


def _geom_ficha_servo(cena: _Cena, corpo: str, junta: str, k: int, ponto) -> str | None:
    """Nome de um GEOM que contém a ficha do servo (a auditoria só resolve geoms): a malha dos conectores que a
    `estrutura` desenha nesse corpo (se a ficha cai dentro da caixa dela), senão a caixa com massa do servo."""
    for nome in (f"est_{corpo}_conector", f"est_{corpo}_borracha", f"servo_{junta}{k}"):
        g = cena.ctx.geom_existente(nome)
        if g is None:
            continue
        if int(g.type) == int(_G.mjGEOM_MESH):
            tri = cena.tri.lista(corpo, nome)
            if len(tri):
                t3 = tri.reshape(-1, 3)
                lo, hi = t3.min(axis=0) - 0.0005, t3.max(axis=0) + 0.0005
                if np.all(np.asarray(ponto) >= lo) and np.all(np.asarray(ponto) <= hi):
                    return nome
            continue
        bb = _aabb(g)
        if bb is not None and np.all(np.asarray(ponto) >= bb[0] - 0.0005) and np.all(np.asarray(ponto) <= bb[1] + 0.0005):
            return nome
    return None


def _caixa_servo_cotovelo(cena: _Cena, k: int) -> _Caixa | None:
    """Extensão do servo do cotovelo no braço: o XH430 da estrutura (centrado no eixo, + garfo) ou a caixa com massa."""
    sx, sy = cena.sinais[k - 1]
    if _estrutura_ativa(cena, k, "cotovelo"):
        L = np.array(cena.ctx.corpo(f"mastro{k}").pos, dtype=float)
        x0 = HORN_TOPO - SERVO_H
        a = L + np.diag([sx, sy, 1.0]) @ np.array([x0, -0.0225, -0.5 * SERVO_W - 0.003])
        b = L + np.diag([sx, sy, 1.0]) @ np.array([HORN_TOPO, 0.0225, 0.5 * SERVO_W])
        return _Caixa(f"braco{k}", np.minimum(a, b), np.maximum(a, b))
    return cena.caixa(f"servo_cotovelo{k}")


def _raio_mastro(cena: _Cena, nm: str, z: float) -> float:
    """Raio da superfície do mastro à altura z (raios de fora para dentro): o tubo Ø16 da estrutura ou o da física."""
    sonda = cena.sonda({nm: np.zeros(3)}, (np.array([-0.05, -0.05, z - 0.01]), np.array([0.05, 0.05, z + 0.01])),
                       excluir=re.compile(r"^fios_|^motor|^helice|^suporte", re.IGNORECASE))
    out = []
    for v in ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)):
        dist = sonda.raio([0.05 * v[0], 0.05 * v[1], z], [-v[0], -v[1], 0.0], 0.05)
        if dist is not None:
            out.append(0.05 - dist)
    r = min(out) if out else 0.008
    return r if 0.004 <= r <= 0.02 else 0.008


def _zona_livre_mastro(cena: _Cena, nm: str, r_tubo: float, z0: float, z1: float, passo: float = 0.003):
    """(z_a, z_b) do maior troço do mastro (entre z0 e z1) onde só está o tubo (sem abraçadeiras CNC nem garfo)."""
    sonda = cena.sonda({nm: np.zeros(3)}, (np.array([-0.04, -0.04, z0 - 0.005]), np.array([0.04, 0.04, z1 + 0.005])),
                       excluir=re.compile(r"^(fios_|motor|helice|suporte)", re.IGNORECASE))
    zs = np.arange(z0, z1 + 1e-9, passo)
    ang = np.linspace(0.0, 2.0 * math.pi, 12, endpoint=False)
    d3 = np.column_stack([np.cos(ang), np.sin(ang), np.zeros_like(ang)])
    livre = []
    for z in zs:
        t = sonda.raios(np.array([0.0, 0.0, z]) + 0.03 * d3, -d3, 0.03)
        ok = np.isfinite(t)
        livre.append(bool(ok.any()) and float(np.max(0.03 - t[ok])) <= r_tubo + 0.0006)
    melhor, atual = (None, 0.0), None
    for z, lv in zip(zs, livre, strict=True):
        if lv:
            atual = (atual[0], z) if atual else (z, z)
            if atual[1] - atual[0] > melhor[1]:
                melhor = (atual, atual[1] - atual[0])
        else:
            atual = None
    return melhor[0]


def _braco_articulado(cena: _Cena, k: int) -> None:
    ctx, m = cena.ctx, cena.m
    nb, nm = f"braco{k}", f"mastro{k}"
    if not (ctx.existe_corpo(nb) and ctx.existe_corpo(nm)) or cena.placa is None:
        return
    S = np.array(ctx.corpo(nb).pos, dtype=float)          # eixo do ombro (no drone)
    E = np.array(ctx.corpo(nm).pos, dtype=float)          # eixo do cotovelo (no braço)
    u = _u([E[0], E[1], 0.0])
    n = np.array([-u[1], u[0], 0.0])
    l1 = float(np.linalg.norm(E[:2]))
    bb = _Braco(k, nb, np.zeros(3), u, n, h0=0.05)
    a0, a1 = bb.p(-0.02), bb.p(l1 + 0.02)
    sonda_b = cena.sonda({nb: np.zeros(3)}, (np.minimum(a0, a1) - 0.06, np.maximum(a0, a1) + 0.06))
    sx, sy = cena.sinais[k - 1]
    M = np.diag([sx, sy, 1.0])
    lado = 1.0 if k % 2 == 1 else -1.0
    saidas = cena.esc_saidas(k, u, nb)
    if saidas is None:
        return
    corpo_esc, p_ent, p_fas, ux, uy, nome_ent, nome_fas = saidas
    if corpo_esc == "drone":                 # ESC sem corpo do braço — passa para o referencial do braço
        p_ent = None if p_ent is None else p_ent - S
        p_fas = p_fas - S
        corpo_esc = nb
    servo_c = _caixa_servo_cotovelo(cena, k)
    s_servo = min(bb.s(c) for c in _cantos(servo_c)) if servo_c is not None else l1 - 0.05

    # ---------------- COTOVELO: a manga das fases cruza do lado do eixo com menos peças
    t_mais, t_menos = _folga_eixo(cena, nb, nm, E, 1.0), _folga_eixo(cena, nb, nm, E, -1.0)
    lado_c = -sy if abs(t_mais - t_menos) < 0.004 else (1.0 if t_mais < t_menos else -1.0)
    r_m = 0.5 * D_MANGA
    t_cot = max(t_mais if lado_c > 0 else t_menos, 0.022) + r_m + 0.002
    X_cb = E + np.array([0.0, lado_c * t_cot, 0.0])
    X_cm = np.array([0.0, lado_c * t_cot, 0.0])
    anc_c = cena.ponto_ancora(f"cotovelo{k}_eixo_cabos")
    if anc_c is not None and anc_c[0] == nm:
        # a estrutura publica o ponto do eixo do cotovelo por onde os cabos cruzam (livre em todo o curso)
        X_cm = np.asarray(anc_c[1], dtype=float)
        X_cb = E + X_cm
        lado_c = math.copysign(1.0, float(X_cm[1])) if abs(float(X_cm[1])) > 1e-6 else lado_c
        t_cot = abs(float(X_cm[1]))
    lado_d = math.copysign(1.0, bb.d(X_cb))

    # ---------------- FASES: rabichos → manga entrançada → cotovelo pelo eixo → mastro → balas do motor
    s_f = bb.s(p_fas)
    # a manga começa onde acabam os rabichos de fábrica — num troço só de tubo (a termo-retráctil da ponta, mais
    # grossa, não assenta numa abraçadeira/suporte): o mais perto de s_f + L_RABICHO (−30…+40 mm), medido
    top_tubo = _topo(sonda_b, bb, s_f + L_RABICHO + 0.040, 0.0, 0.0124)
    s_m0 = s_f + L_RABICHO
    cands = sorted(np.arange(s_f + L_RABICHO - 0.030, s_f + L_RABICHO + 0.0401, 0.002), key=lambda x: abs(x - s_m0))
    for sv in cands:         # a termo (−6…+10 mm) e o arranque da manga (até +24 mm) só sobre o tubo
        if all(_topo(sonda_b, bb, sv + dv, 0.0, 1.0) <= top_tubo + 0.0004
               for dv in (-0.012, -0.008, -0.004, 0.0, 0.004, 0.010, 0.016, 0.022, 0.026)):
            s_m0 = float(sv)
            break
    # a termo da ponta assenta no ponto mais alto do tubo debaixo dela (de −6 a +10 mm)
    dz_m0 = max(_topo(sonda_b, bb, s_m0 + ds, 0.0, 0.005) for ds in (-0.006, -0.002, 0.0, 0.002, 0.006, 0.010)) \
        + 0.5 * (D_MANGA + 0.0012) + 0.00003
    inicios = []
    # dentro da manga (Ø 8) as 3 fases (Ø 3) vão em triângulo: centros a 1,75 mm do eixo da manga, a 120°
    tri_f = [(1.75 * math.cos(a), 1.75 * math.sin(a)) for a in (math.radians(210), math.radians(90), math.radians(330))]
    with m.peca("cabo_fases", k):
        for i_f, lat in enumerate((-1.07 * D_FASE, 0.0, 1.07 * D_FASE)):
            p0 = p_fas + lat * uy - 0.003 * ux
            d0 = bb.d(p0)
            e_d, e_z = tri_f[i_f]
            # deitados no topo do tubo (perfil medido: passam por cima das abraçadeiras/suportes) até à manga; à entrada
            # dela o do meio sobe primeiro ao vértice de cima do triângulo e só depois os dos lados se juntam
            deitados = _perfil(sonda_b, bb, s_f + 0.030, s_m0 - 0.018, d0, 0.5 * D_FASE, 0.005)
            fim = [bb.p(s_m0 - 0.004, e_d * MM, dz_m0 + e_z * MM), bb.p(s_m0 + 0.004, e_d * MM, dz_m0 + e_z * MM)]
            if i_f == 1:
                meio = [bb.p(s_m0 - 0.011, e_d * MM, dz_m0 + e_z * MM)]
            else:
                meio = [bb.p(s_m0 - 0.011, d0, float(bb.dz(deitados[-1])))]
            pts = [p0, p0 + 0.008 * ux, *deitados, *meio, *fim]
            m.tubo(nb, "fios_laranja", _curva(pts, 0.008), D_FASE)
            inicios.append(p0)
    # a manga corre no topo do tubo até ao FIM dele (e da ponteira, medido: onde o raio vertical deixa de bater no
    # braço) e só aí desce para o lado do servo do cotovelo — o X4P vai pelo lado do tubo, por baixo dela
    ss_f = np.arange(s_servo - 0.12, s_servo + 1e-9, 0.002)
    dn_f = sonda_b.raios_verticais(np.array([bb.p(sv, 0.0, 0.05) for sv in ss_f]), -1.0, 0.08)
    tem = np.isfinite(dn_f) & (0.05 - dn_f > 0.005)
    s_fim = s_servo - 0.045
    if tem.any():
        i_t = int(np.flatnonzero(tem)[0])
        buraco = np.flatnonzero(~tem[i_t:])
        s_fim = float(ss_f[i_t + int(buraco[0]) - 1]) if len(buraco) else float(ss_f[-1])
    s_m1 = min(s_fim + 0.012, s_servo - 0.010)
    with m.peca("manga", k):
        manga = _perfil(sonda_b, bb, s_m0, s_m1, 0.0, r_m, 0.005, largura=0.85 * r_m)
        d_contorno = 0.026
        if servo_c is not None:
            d_contorno = max([abs(bb.d(c)) for c in _cantos(servo_c) if bb.d(c) * lado_d > 0] + [d_contorno])
        d_contorno = max(d_contorno, abs(bb.d(X_cb))) + r_m + 0.003
        contorno = bb.p(s_servo - 0.004, lado_d * d_contorno, 0.002)
        junto = bb.p(bb.s(X_cb) - 0.010, lado_d * d_contorno, 0.0)
        rota = [contorno, junto]
        if servo_c is not None:
            # à volta do servo do cotovelo, por fora do garfo do mastro em TODO o curso (±60°, medido no varrimento):
            # ainda alta, de lado; desce junto à face do servo virada para o braço; contorna a ponta do servo do lado do
            # ponto de travessia e chega ao eixo — no referencial canónico do cotovelo (x para o mastro, y para X_cb)
            ey_c = np.array([0.0, 1.0 if float(X_cb[1] - E[1]) >= 0.0 else -1.0, 0.0])
            ex_c = np.array([1.0 if float(E[0]) >= 0.0 else -1.0, 0.0, 0.0])

            def C(cx, cy, cz):
                return E + cx * ex_c + cy * ey_c + np.array([0.0, 0.0, cz])
            cs = np.array([[float((c - E) @ ex_c), float((c - E) @ ey_c)] for c in _cantos(servo_c)])
            xl, yh = float(cs[:, 0].min()), float(cs[:, 1].max())
            yl = float(cs[:, 1].min())
            dz_t = float(bb.dz(manga[-1]))
            rota = [C(xl - 0.014, yl - 0.007, dz_t), C(xl - 0.018, yl + 0.007, 0.006), C(xl - 0.012, 0.0, 0.0),
                    C(xl - 0.006, yh + 0.002, 0.0), C(-0.0015, yh + 0.008, 0.0)]
        if anc_c is not None and anc_c[0] == nm:
            # com o ponto do eixo publicado: do fim do troço no topo do tubo a direito (a descer) até ele — por fora do
            # berço e do braço A do garfo, que a estrutura deixou livres à volta do ponto
            fim_t = manga[-1]
            rota = [0.5 * (fim_t + X_cb) + np.array([0.0, 0.0, 0.25 * float(fim_t[2] - X_cb[2])])]
        m.tubo(nb, "fios_manga", _curva([*manga, *rota, X_cb], 0.008), D_MANGA)
        m.tubo(nb, "fios_termo", [bb.p(s_m0 - 0.006, 0.0, dz_m0), bb.p(s_m0 + 0.010, 0.0, dz_m0)], D_MANGA + 0.0012)
    balas = cena.balas(k)
    mot = cena.caixa(f"motor{k}")
    if mot is None:
        return
    # mastro: sobe por fora do garfo, passa à face de dentro (−u) acima da abraçadeira e sobe até às balas
    r_tubo_m = _raio_mastro(cena, nm, 0.11)
    z_fim = (min(float(q[1][2]) for q in balas) - 0.026) if balas is not None else float(mot.lo[2]) - 0.035
    zona = _zona_livre_mastro(cena, nm, r_tubo_m, 0.06, z_fim)
    z_alto = 0.078 if zona is None else max(0.078, zona[0] + 0.004)
    r_face = r_tubo_m + 0.5 * (D_MANGA + 0.0012) + 0.00003      # a termo-retráctil da ponta também encosta
    p_cima = np.array([0.0, lado_c * t_cot, 0.062])
    p_face = -u * r_face + np.array([0.0, 0.0, z_alto])
    p_fim = -u * r_face + np.array([0.0, 0.0, z_fim])
    # de cima do garfo à face de dentro do mastro: dá a volta ao tubo num arco (raio ≥ o da face), não pela corda
    ang0, ang1 = math.atan2(float(p_cima[1]), float(p_cima[0])), math.atan2(float(p_face[1]), float(p_face[0]))
    ang1 = ang0 + (ang1 - ang0 + math.pi) % (2.0 * math.pi) - math.pi
    r0 = float(np.hypot(p_cima[0], p_cima[1]))
    volta = [np.array([(r_face + (r0 - r_face) * (1.0 - t) ** 2) * math.cos(ang0 + (ang1 - ang0) * t),
                       (r_face + (r0 - r_face) * (1.0 - t) ** 2) * math.sin(ang0 + (ang1 - ang0) * t),
                       float(p_cima[2]) + (z_alto - float(p_cima[2])) * (3.0 * t * t - 2.0 * t ** 3)])
             for t in np.linspace(0.0, 1.0, 10)]
    with m.peca("manga", k):
        m.tubo(nm, "fios_manga", [*_curva([X_cm, p_cima - np.array([0.0, 0.0, 0.012]), p_cima], 0.010)[:-1], *volta,
                                  p_fim], D_MANGA)
        m.tubo(nm, "fios_termo", [p_fim - np.array([0, 0, 0.012]), p_fim + np.array([0, 0, 0.004])], D_MANGA + 0.0012)
    vagas = [p_fim + np.array([0.0, 0.0, 0.002]) + MM * (e_d * n + e_z * (-u)) for e_d, e_z in tri_f]
    if balas is not None:
        # à saída da manga o triângulo das 3 fases roda (dentro da manga) até ter o vértice virado para as balas: o fio
        # desse vértice vai à bala do meio, os 2 de trás às dos lados — abrem em leque sem se cruzarem
        c_v = p_fim + np.array([0.0, 0.0, 0.002])
        alvo_m = np.mean([q[1] for q in balas], axis=0)
        dir_m = _u([float(alvo_m[0] - c_v[0]), float(alvo_m[1] - c_v[1]), 0.0])
        lat_m = np.array([-dir_m[1], dir_m[0], 0.0])
        ob = sorted(range(3), key=lambda i: float((balas[i][1] - c_v) @ lat_m))
        pos = {ob[1]: (1.0, 0.0), ob[0]: (-0.5, -math.sqrt(3.0) / 2.0), ob[2]: (-0.5, math.sqrt(3.0) / 2.0)}
        vagas = [c_v + 1.75 * MM * (pos[i][0] * dir_m + pos[i][1] * lat_m) for i in range(3)]
    with m.peca("cabo_fases", k):
        for i, lat in enumerate((-1.07 * D_FASE, 0.0, 1.07 * D_FASE)):
            a = vagas[i]
            if balas is not None:
                c_b, p3, dv, r_c = balas[i]
                ent = _bala_femea(cena, nm, p3, dv, r_c)
                # os 2 de trás afastam-se primeiro para o lado (passam ao lado do da frente a ≥ 3,2 mm) e só depois
                # vão às balas dos lados; o da frente sobe e vai direito à do meio
                lat_a = float((a - c_v) @ lat_m)
                if abs(lat_a) > 0.0005:
                    lado_a = a + (math.copysign(0.0033, lat_a) - lat_a) * lat_m + np.array([0.0, 0.0, 0.003])
                    pts = [a, a + np.array([0.0, 0.0, 0.0015]), lado_a, lado_a + np.array([0.0, 0.0, 0.003]),
                           ent + 0.012 * dv, ent]
                else:
                    pts = [a, a + np.array([0.0, 0.0, 0.006]), ent + 0.012 * dv, ent]
                destino, c_dest, p_dest = f"motor{k}_fase_{'abc'[i]}_conector", c_b, p3 - 0.001 * dv
            else:
                r_mot = float(mot.h[0])
                pts = [a, a + np.array([0.0, 0.0, 0.006]),
                       -u * (r_mot - 0.004) + lat * n + np.array([0.0, 0.0, float(mot.lo[2]) + 0.004])]
                destino, c_dest, p_dest = cena.nome_ancora(f"motor{k}", None), nm, pts[-1]
            m.tubo(nm, "fios_laranja", _curva(pts, 0.006), D_FASE)
            cena.ligar(f"fase{k}_{'abc'[i]}", nome_fas, destino, nb, inicios[i], c_dest, p_dest, "16 AWG",
                       "cabo_fases", k, via="manga do cotovelo")
    # abraçadeira do mastro: à volta do tubo e da manga, no troço onde só lá estão eles
    if zona is not None and zona[1] - zona[0] > 0.006:
        z_ab = min(max(0.5 * (z_alto + z_fim) + 0.01, zona[0] + 0.003), zona[1] - 0.003)
        incl_m = re.compile(rf"^(est_mastro{k}_carbono|mastro{k}_tubo|mastro{k})$")
        _abracadeira(cena, nm, np.array([0.0, 0.0, z_ab]), [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], 0.022,
                     (float(n[0]), float(n[1])), incluir=incl_m, rotulo=f"mastro {k}", membros="mastro + manga das fases")

    # ---------------- OMBRO: feixe (alimentação + sinal + DYNAMIXEL) pelo eixo, do lado de fora do redutor (−b)
    r_h = 0.5 * D_FEIXE
    w_tubo = _meia_largura(sonda_b, bb, 0.10, 0.0, 0.012)
    anc = (ctx.registo.notas.get("ancoras") or {}).get(f"ombro{k}_eixo_cabos")
    trav = None
    if anc is not None and str(anc.get("corpo", "drone")) == "drone":
        # o feixe cruza a junta no ponto do eixo publicado pela estrutura (fixo nos dois corpos, fora da dobradiça)
        X_b = np.asarray(anc["ponto"], dtype=float) - S
        lado_h = math.copysign(1.0, bb.d(X_b)) if abs(bb.d(X_b)) > 1e-6 else -lado_d
        A = bb.p(0.090, lado_h * (w_tubo + 0.5 * (D_FEIXE + 0.0012) + 0.0002), 0.0)
        trav = (_travessia_ombro_fuso(cena, k, M, r_h) if _tipo_servo(cena.hw, "ombro") == "motorredutor_dc" else None) \
            or _travessia_ombro(cena, k, S, M, S + A, r_h)
    if trav is not None:
        X_d, pts_d, dir_d = trav
        W2 = pts_d[0]
        pts_b = [X_b, A]                      # braço: direito do ponto do eixo à ponta ao lado do tubo
        pts_d = _curva(pts_d, 0.012)
    else:                                     # sem a âncora: pelo lado do eixo com menos peças (como antes)
        lado_p = -sy
        t_omb = max(_folga_eixo(cena, "drone", nb, S, lado_p), 0.02) + r_h + 0.0015
        X_d = S + np.array([0.0, lado_p * t_omb, 0.0])
        X_b = np.array([0.0, lado_p * t_omb, 0.0])
        lado_h = math.copysign(1.0, bb.d(X_b)) if abs(bb.d(X_b)) > 1e-6 else -lado_d
        A = bb.p(0.090, lado_h * (w_tubo + r_h + 0.0005), 0.0)
        z_mesa = (cena.z_sup + 0.0012 if cena.z_sup is not None else cena.z_topo + 0.004) + r_h
        W1 = np.array([X_d[0], X_d[1], z_mesa])
        W2 = W1 + M @ np.array([-0.045, 0.0, 0.0])
        dir_d = _u(W2 - W1)
        pts_b = _curva([X_b, np.array([sx * 0.032, X_b[1], 0.004]), A], 0.014)
        pts_d = _curva([X_d, X_d + np.array([0, 0, 0.6 * (z_mesa - X_d[2])]), W1, W2], 0.012)
    dir_b = _u(pts_b[-1] - pts_b[-2])
    cena.feixe_ombro[k] = (np.asarray(A, dtype=float), dir_b, nb, np.asarray(pts_d[0], dtype=float),
                           _u(np.asarray(pts_d[0], dtype=float) - np.asarray(pts_d[1], dtype=float)),
                           [np.asarray(q, dtype=float) for q in pts_d])
    with m.peca("manga", k):                  # a manga entrançada do feixe do ombro (alimentação + sinal + DYNAMIXEL)
        m.tubo(nb, "fios_manga", pts_b, D_FEIXE)
        m.tubo("drone", "fios_manga", pts_d, D_FEIXE)
        for corpo, c, dv in ((nb, A, dir_b), ("drone", W2, dir_d)):      # termo-retráctil nas pontas do feixe
            # (no braço acaba na ponta da manga: o feixe chega ao lado do tubo em diagonal e 1 mm mais roçava nele)
            m.tubo(corpo, "fios_termo", [c - 0.014 * dv, c + (0.0002 if corpo == nb else 0.001) * dv], D_FEIXE + 0.0012)

    # ---- pontas da manga do feixe: 4 vagas (anel de 2,55 mm) — no BRAÇO, `lat` aponta para o tubo; na PLACA, para
    # o eixo do drone. Braço: o X4P sai da vaga D (por baixo, do lado do tubo) e é o primeiro a descolar — desce ao lado
    # do tubo e, se a ficha do servo do cotovelo estiver do outro lado, passa por baixo dele; os 3 que vão para cima do
    # tubo (2 × 14 AWG + sinal) saem das vagas A, B, C pela ordem do que vai mais longe (para o outro lado do topo) ao
    # que fica mais perto e descolam UM A UM, por essa ordem: cada um, quando dá a volta ao tubo, só passa por vagas já
    # vazias e fica do lado de lá dos que já lá estão — nenhum cruza outro. Depois assentam no topo (perfil medido) e
    # sobem à entrada do ESC.
    t_b = _u(np.cross(dir_b, EZ))
    if float(np.dot(t_b, -lado_h * bb.n)) < 0.0:
        t_b = -t_b
    pb = _PontaFeixe(A, dir_b, t_b)
    lat_d = _u(np.cross(EZ, dir_d))
    if float(np.dot(lat_d, [-W2[0], -W2[1], 0.0])) < 0.0:
        lat_d = -lat_d
    pd = _PontaFeixe(W2, dir_d, lat_d)
    s_A = bb.s(A)
    dz_ax = _eixo_tubo(sonda_b, bb, s_A + 0.03)[0]
    feixe_obj = None
    if p_ent is not None:
        lats = {0: -0.75 * D_ESC, 1: 0.45 * D_ESC, 2: LAT_SINAL_ESC}
        d_fins = {i: bb.d(p_ent + lt * uy + 0.003 * ux) for i, lt in lats.items()}
        ordem = sorted(d_fins, key=lambda i: lado_h * d_fins[i])          # do mais longe ao mais perto do feixe
        vaga_de = dict(zip(ordem, ("A", "B", "C"), strict=True))
        janela = dict(zip(ordem, ((s_A + 0.012, s_A + 0.028), (s_A + 0.028, s_A + 0.044), (s_A + 0.044, s_A + 0.058)),
                          strict=True))
        s_sobe = bb.s(p_ent) - 0.028

        def braco_fio(i, p0):
            r_i = D_SINAL if i == 2 else 0.5 * D_ESC
            s_a, s_b = janela[i]
            topo = _perfil(sonda_b, bb, s_b, s_sobe, bb.d(p0), r_i, 0.005)
            volta = _descolar(bb, pb.ponto(vaga_de[i], 0.004), s_a, s_b, topo[0], dz_ax)
            return [pb.ponto(vaga_de[i], -0.006), pb.ponto(vaga_de[i], 0.004), *volta, *topo[1:], p0 - 0.006 * ux, p0]

        feixe_obj = _Feixe(braco_fio, pd)
        _alimentacao_e_sinal(cena, k, bb, sonda_b, p_ent, ux, uy, lado, nome_ent, feixe=feixe_obj)
    # DYNAMIXEL: servo do ombro → feixe → braço (pelo lado do tubo) → servo do cotovelo
    so = _servo_conectores(cena, k, "ombro")
    sc = _servo_conectores(cena, k, "cotovelo")
    r_x = 0.5 * D_DXL
    if cena.servo_pwm and sc is not None:
        # build ACESSÍVEL: o cotovelo é um servo de passatempo (DS3218MG) com cabo de 3 fios (castanho GND, vermelho
        # 6,8 V, laranja PWM) que vem pelo feixe do ombro até ao servo-rail do UBEC; o ombro não leva cabo daqui
        with m.peca("cabo_servo", k):
            r_x = 0.5 * D_CABO_SERVO
            p_s = pd.ponto("B", 0.004)
            J = p_s + 0.004 * pd.dv + np.array([0.0, 0.0, 0.006])
            m.tubo("drone", "fios_dxl", _curva([J, p_s, pd.ponto("B", -0.006)], 0.006), D_CABO_SERVO)
            c_c, qc, dqc, nome_c = min(sc, key=lambda c: float(c[1][2]))
            lado_f = math.copysign(1.0, bb.d(qc)) if abs(bb.d(qc)) > 1e-6 else -lado_h
            rho_x = w_tubo + r_x + 0.0004
            dz_l = dz_ax - 0.002
            d_l = math.sqrt(max(rho_x * rho_x - 0.002 ** 2, 0.0))
            p_s = pb.ponto("D", 0.004)
            pts = [pb.ponto("D", -0.006), p_s, bb.p(s_A + 0.008, bb.d(p_s), bb.dz(p_s)),
                   bb.p(s_A + 0.018, lado_h * d_l, dz_l)]
            s_a = s_A + 0.022
            if lado_f != lado_h:
                pts += _arco_tubo(bb, s_A + 0.018, s_A + 0.048, lado_h * d_l, dz_l, lado_f * d_l, dz_l, rho_x, -1.0,
                                  dz_eixo=dz_ax)[1:]
                s_a = s_A + 0.052
            s_q = bb.s(qc + 0.022 * dqc)
            sonda_l = cena.sonda({nb: np.zeros(3)}, (np.minimum(a0, a1) - 0.06, np.maximum(a0, a1) + 0.06),
                                 excluir=_SO_FIOS)
            pts += _perfil_lado(sonda_l, bb, s_a, s_q - 0.012, lado_f, dz_l, r_x, rho_x)
            # o cabo do DS3218MG sai do passa-cabos do servo (a âncora): a bainha acaba à face dele, sem entrar
            pts += [qc + 0.022 * dqc, qc + (0.62 * r_x + 0.0002) * dqc]
            m.tubo(nb, "fios_dxl", _curva(pts, 0.008), D_CABO_SERVO)
            cena.servo_braco[k] = (np.asarray(_curva(pts, 0.008), dtype=float), nb, bb, dz_ax, w_tubo)
            cena.juncao_servo[k] = (J, pd.dv, _geom_ficha_servo(cena, c_c, "cotovelo", k, qc) or nome_c, c_c, qc)
            # o AS5600 do cotovelo (barra de 4 pinos na ponta do M8): rabicho até uma ficha JST-GH solta
            fb_c = cena.ponto_ancora(f"servo_cotovelo{k}_ficha_b")
            if fb_c is not None and fb_c[0] == nb and not _pico_lados(cena):
                q5, d5 = np.asarray(fb_c[1], dtype=float), _u(fb_c[2])
                with m.peca("cabo_sensores_braco", k):
                    _rabicho(cena, f"as5600_cotovelo{k}", [q5 + d5 * 0.0014, q5 + d5 * 0.007,
                                                           q5 + d5 * 0.016 + np.array([0.0, 0.0, -0.002]),
                                                           q5 + d5 * 0.026 + np.array([0.0, 0.0, -0.003])],
                             D_SENS4, 4, _geom_ficha_servo(cena, nb, "cotovelo", k, q5) or f"servo_cotovelo{k}_ficha_b",
                             k, "AS5600 do cotovelo (I²C: VCC, GND, SDA, SCL)", corpo=nb)
    elif so is not None and sc is not None:
        with m.peca("cabo_dxl", k):
            c_o, q, dq, nome_o = so[0]
            _ficha_eh(cena, c_o, q, dq)
            # placa: da vaga B (por cima, do lado de fora) sobe logo — o par de 14 AWG vai para dentro, o sinal sai por
            # baixo — e vai à ficha do servo do ombro por fora da face dela
            p_s = pd.ponto("B", 0.004)
            sobe = p_s + 0.004 * pd.dv + np.array([0.0, 0.0, 0.008])
            canto = np.array([float(q[0] + 0.014 * dq[0]), float(p_s[1]), float(q[2]) - 0.010])
            m.tubo("drone", "fios_dxl", _curva([q + 0.004 * dq, q + 0.014 * dq, canto, sobe, p_s, pd.ponto("B", -0.006)],
                                               0.008), D_DXL)
            # braço: a ficha do servo do cotovelo fica do lado do tubo OPOSTO ao feixe — o cabo desce ao lado do tubo,
            # passa por baixo dele logo a seguir à ponta do feixe, segue pelo outro lado e afasta-se da ponteira do tubo
            c_c, qc, dqc, nome_c = min(sc, key=lambda c: float(c[1][2]))
            _ficha_eh(cena, c_c, qc, dqc)
            lado_f = math.copysign(1.0, bb.d(qc)) if abs(bb.d(qc)) > 1e-6 else -lado_h
            rho_x = w_tubo + r_x + 0.0004
            dz_l = dz_ax - 0.002
            d_l = math.sqrt(max(rho_x * rho_x - 0.002 ** 2, 0.0))
            p_s = pb.ponto("D", 0.004)
            pts = [pb.ponto("D", -0.006), p_s, bb.p(s_A + 0.008, bb.d(p_s), bb.dz(p_s)),
                   bb.p(s_A + 0.018, lado_h * d_l, dz_l)]
            s_a = s_A + 0.022
            if lado_f != lado_h:              # passa para o outro lado POR BAIXO do tubo, colado a ele (arco)
                pts += _arco_tubo(bb, s_A + 0.018, s_A + 0.048, lado_h * d_l, dz_l, lado_f * d_l, dz_l, rho_x, -1.0,
                                  dz_eixo=dz_ax)[1:]
                s_a = s_A + 0.052
            # ao lado do tubo até à ficha do servo do cotovelo, afastando-se do que sai para o lado (pernas, ponteira)
            s_q = bb.s(qc + 0.022 * dqc)
            sonda_l = cena.sonda({nb: np.zeros(3)}, (np.minimum(a0, a1) - 0.06, np.maximum(a0, a1) + 0.06),
                                 excluir=_SO_FIOS)          # vê o ESC e as abraçadeiras dele (da eletrónica)
            pts += _perfil_lado(sonda_l, bb, s_a, s_q - 0.012, lado_f, dz_l, r_x, rho_x)
            pts += [qc + 0.022 * dqc, qc + 0.0045 * dqc]
            m.tubo(nb, "fios_dxl", _curva(pts, 0.008), D_DXL)
            cena.ligar(f"dxl_cotovelo{k}", _geom_ficha_servo(cena, c_o, "ombro", k, q) or nome_o,
                       _geom_ficha_servo(cena, c_c, "cotovelo", k, qc) or nome_c, c_o, q, c_c, qc,
                       "Robot Cable-X4P (4 × 21 AWG)", "cabo_dxl", k, via="feixe do ombro", ficha_de=nome_o,
                       ficha_para=nome_c)
    # abraçadeiras: troço da alimentação (com o DYNAMIXEL ao lado) — depois de os fios assentarem no topo e antes de
    # subirem ao ESC — e troço das fases
    r_t = _meia_largura(sonda_b, bb, 0.10, 0.0, 0.0125)
    sonda_est = _sonda_estacoes(cena, bb, 0.10, l1)
    if p_ent is not None:
        s_e = bb.s(p_ent)
        lo_e, hi_e = max(0.135, s_A + 0.064), s_e - 0.034
        sv = _estacao_livre(cena, bb, sonda_est, 0.5 * (lo_e + hi_e), lo_e, hi_e, r_t + 0.0006)
        if sv is not None:
            _abracadeira_braco(cena, bb, sv, -lado_d, f"braço {k}: alimentação + DYNAMIXEL", rho=0.026)
    sv = _estacao_livre(cena, bb, sonda_est, 0.5 * (s_m0 + s_m1), s_m0 + 0.012, s_m1 - 0.045, r_t + 0.0006)
    if sv is not None:
        _abracadeira_braco(cena, bb, sv, lado_d, f"braço {k}: manga das fases", rho=0.026)


# ====================================================================================== ombro de fuso (motorredutor)
D_ENC = 0.0010          # cada fio do cabo do JGB37-520 (6 vias PH2.0: motor ±, encoder GND/VCC/A/B), em fita
_CORES_JGB = ("fios_vermelho", "fios_branco", "fios_preto", "fios_azul", "fios_amarelo", "fios_verde")


def _cabo_motorredutor(cena: _Cena, k: int):
    """Build ACESSÍVEL: o cabo de 6 vias do JGB37-520 (fita PH2.0: vermelho/branco = motor ±, preto/azul/amarelo/verde =
    encoder GND/VCC/A/B). O troço do ATUADOR (que roda à volta do pivô B) é do grupo animado `ombro{k}_fuso_base` (a
    planta roda-o com o atuador): sai da ficha da tampa do encoder para cima, dobra para o lado de dentro, desce colada
    à lata do motor, por fora do bloco e do garfo, e perto de B torce 90° e chega de cima ao EIXO de B, junto à âncora
    `ombro{k}_pivo_b_cabos` (que não se mexe): os 6 fios ficam um atrás do outro AO LONGO do eixo, por isso continuam
    ligados em qualquer ângulo do atuador. Daí, fixo no drone: um LAÇO de ¾ de volta à volta do eixo (mola de relógio,
    rente à cabeça do parafuso de ombro e longe do fuso, a afastar-se dela para dentro), a fita desce por fora da torre
    até à altura da placa de cima — os 4 do encoder entram aí na bainha do rabicho — e o par do motor passa a borda da
    placa de baixo e vai por baixo dela ao borne `el_drv{k}_motor` do DRV8871. Devolve (ponto, direção para dentro) do
    início do rabicho do encoder (ou None)."""
    m = cena.m
    fa = cena.ponto_ancora(f"servo_ombro{k}_ficha_a")
    pb_ = cena.ponto_ancora(f"ombro{k}_pivo_b_cabos")
    anc = (cena.ctx.registo.notas.get("ancoras") or {}).get(f"servo_ombro{k}_ficha_a") or {}
    grupo = anc.get("grupo")
    mec = getattr(cena.hw, "bracos", None)
    fu = getattr(getattr(mec, "ombro", None), "fuso", None) if mec is not None else None
    if fa is None or pb_ is None or fu is None or not cena.ctx.existe_corpo(f"braco{k}"):
        return None
    F, dF = np.asarray(fa[1], dtype=float), _u(fa[2])
    Bk = np.asarray(pb_[1], dtype=float)
    h = np.array(cena.ctx.corpo(f"braco{k}").pos, dtype=float)
    a_v, b_v = (np.array(v, dtype=float) for v in fu.vetores(math.copysign(1.0, h[0]), math.copysign(1.0, h[1])))
    A_c, B_c = h + a_v, h + b_v
    u = _u(B_c - A_c)                                   # eixo do atuador, de A para B e para o motor
    sy = 1.0 if float(B_c[1]) >= 0.0 else -1.0
    dentro = np.array([0.0, -sy, 0.0])                  # o lado de dentro do atuador (para o eixo x do drone)
    # a superfície de dentro da lata/caixa do redutor (raio medido: raio de dentro para fora a meia altura)
    zona = (np.minimum(F, B_c) - 0.03, np.maximum(F, B_c) + 0.03)
    sonda = cena.sonda({"drone": np.zeros(3)}, zona, excluir=_SO_FIOS)
    t_top = float(np.dot(F - B_c, u))
    r_lata = 0.0
    for t_q in np.linspace(0.30 * t_top, 0.92 * t_top, 9):          # o maior raio ao longo da lata e do redutor
        q = B_c + t_q * u
        for dx in (-0.003, 0.0, 0.003):
            dd = sonda.raio(q + dentro * 0.040 + np.array([dx, 0.0, 0.0]), -dentro, 0.040)
            if dd is not None:
                r_lata = max(r_lata, 0.040 - dd)
    r_lata = r_lata or 0.0185
    y_l = float(B_c[1]) + float(dentro[1]) * (r_lata + 0.5 * D_ENC + 0.0006)

    def linha(t):                                      # o fio colado à face de dentro, a t de B ao longo do eixo
        p = B_c + t * u
        return np.array([float(p[0]), y_l, float(p[2])])
    t_F = float(np.dot(F - B_c, u))
    z_alto = float(Bk[2]) + 0.0125                      # por cima do garfo e da cabeça do parafuso de ombro
    t_baixo = (z_alto - float(B_c[2])) / max(float(u[2]), 1e-6)
    # o troço do atuador: a fita DEITADA na lata (a largura ao longo de w = eixo × dentro) até perto de B
    w = _u(np.cross(u, dentro))
    sep = D_ENC + 0.00005
    e_ax = dentro.copy()                                # o eixo de B (∥ y), para dentro
    # JUNÇÃO no eixo de B: os 6 fios chegam com a largura da fita AO LONGO do eixo (cada um num ponto do eixo: ficam
    # ligados em qualquer ângulo do atuador); o de fora a 1,1 mm da âncora (que está 3 mm por fora da cabeça)
    a0 = 2.5 * sep + 0.5 * D_ENC + 0.0006
    J = Bk + e_ax * a0
    F0 = F + 0.0022 * dF                                 # a fita sai por cima da ficha (por cima da tampa)
    centro_a1 = _curva([F0, F + 0.0065 * dF, F + 0.0085 * dF + dentro * 0.0045, linha(t_F - 0.006) + dF * 0.002,
                        linha(t_F - 0.014), linha(t_baixo + 0.010), linha(t_baixo)], 0.004)
    # a descida final (Bézier): continua ao longo da lata, TORCE 90° (a largura passa de w para o eixo de B) e chega
    # à junção a direito, de cima
    P0, P3 = linha(t_baixo), J
    P1, P2 = P0 - u * 0.004, P3 + np.array([0.0, 0.0, 0.005])
    ts = np.linspace(0.0, 1.0, 13)
    bez = [((1 - t) ** 3) * P0 + 3 * ((1 - t) ** 2) * t * P1 + 3 * (1 - t) * t * t * P2 + (t ** 3) * P3 for t in ts]
    centro_a = [*centro_a1, *bez[1:]]
    dws = [w] * len(centro_a1) + [_u((1.0 - sv) * w + sv * e_ax) for sv in (3.0 * ts[1:] ** 2 - 2.0 * ts[1:] ** 3)]
    nome_f = f"ombro{k}_fuso_base_conector"
    g_f = cena.ctx.geom_existente(nome_f)
    corpo_a = f"drone@{grupo}" if grupo else "drone"
    offs = [(i - 2.5) * sep for i in range(len(_CORES_JGB))]
    for i, mat in enumerate(_CORES_JGB):
        m.tubo(corpo_a, mat, [c + offs[i] * dw for c, dw in zip(centro_a, dws, strict=True)], D_ENC, lados=4,
               ident=f"jgb{k}_atuador_{i}")
    # o LAÇO (fixo no drone): ¾ de volta à volta do eixo de B — desce da junção, dá a volta por trás e por cima e sai
    # a descer pelo lado de FORA (longe da torre); cada fio no seu plano (a fita de largura ao longo do eixo, como
    # numa mola de relógio) e o laço AFASTA-SE da cabeça para dentro 7,2 mm na primeira meia volta: quando passa por
    # cima da junção já está para lá da fita que desce do atuador (sem se cruzarem)
    sx_k = 1.0 if float(B_c[0]) >= 0.0 else -1.0
    r_l, D_l = 0.005, 0.0072
    fi = np.linspace(0.0, 1.5 * math.pi, 40)

    def p_laco(f, off):
        th = -0.5 * math.pi - f
        r = r_l * math.sin(0.5 * math.pi * min(1.0, f / (math.pi / 3.0)))
        t = min(1.0, f / math.pi)
        return Bk + np.array([sx_k * r * math.cos(th), 0.0, r * math.sin(th)]) + e_ax * (a0 + off + D_l * (3.0 * t * t
                                                                                                         - 2.0 * t ** 3))
    # do laço para baixo, os 6 juntos (a largura ao longo do eixo de B) até à altura da placa de cima: aí os 4 do
    # encoder entram na bainha do rabicho (para dentro, na placa) e o par do motor segue por fora da borda da placa
    # de baixo e por baixo dela ao borne do DRV8871
    placa = cena.placa
    mot = cena.ponto_ancora(f"el_drv{k}_motor")
    cx_m = cena.caixa(f"el_drv{k}_motor")
    if placa is None or mot is None or cx_m is None or cena.z_sup is None:
        return None
    E_c = p_laco(fi[-1], 0.0)                            # centro da fita à saída do laço (a descer)
    pico = bool(_pico_lados(cena))
    if pico:
        # com os controladores dos braços (Pico): a fita desce até à placa de BAIXO (por fora da borda da de cima,
        # afastando-se dela 1,8 mm) — os 4 do encoder seguem dali, pela faixa da placa de baixo, até à ficha do Pico;
        # assenta no que lá estiver (cabeças de parafusos: medido por raios na pegada da fita e da bainha do Hall)
        fora_d = -e_ax * 0.0018
        b0 = np.array([float(E_c[0]), float(E_c[1]), 0.0]) + fora_d
        son_b = cena.sonda({"drone": np.zeros(3)}, (b0 - np.array([0.010, 0.010, 0.0]) + np.array([0, 0, float(placa.hi[2])
                                                                                                   - 0.001]),
                                                     b0 + np.array([0.010, 0.010, 0.0]) + np.array([0, 0, float(placa.hi[2])
                                                                                                    + 0.012])),
                           excluir=_SO_FIOS)
        G_b = np.array([b0 + e_ax * o + np.array([dx, 0.0, float(placa.hi[2]) + 0.010])
                        for o in np.linspace(-0.0034, 0.0034, 9) for dx in np.linspace(-0.0050, 0.0050, 11)])
        dd_b = son_b.raios_verticais(G_b, -1.0, 0.0105)
        chao_b = float(np.max(np.where(np.isfinite(dd_b), float(placa.hi[2]) + 0.010 - dd_b, float(placa.hi[2]))))
        z_sep = max(float(placa.hi[2]), chao_b) + 0.5 * D_ENC + 0.0006 + 0.0007
    else:
        z_sep = cena.z_sup + 0.0012 + 0.0030             # à altura da placa de cima
        fora_d = np.zeros(3)
    z_d0 = float(E_c[2]) - 0.004
    p_sep = np.array([float(E_c[0]), float(E_c[1]), z_sep]) + fora_d
    o_enc = sum(offs[2:]) / 4.0
    for i, mat in enumerate(_CORES_JGB):
        fio = [p_laco(f, offs[i]) for f in fi]
        zs_d = np.linspace(z_d0, z_sep, 8)
        for j, z in enumerate(zs_d):
            o = offs[i]
            if pico and i >= 2 and j >= len(zs_d) - 2:           # os 4 do encoder juntam-se para a bainha do Hall
                o = o_enc + (o - o_enc) * (0.62 if j == len(zs_d) - 2 else 0.30)
            fio.append(np.array([float(E_c[0]), float(E_c[1]), z]) + e_ax * o
                       + fora_d * min(1.0, max(0.0, (z_d0 - z) / 0.010)))
        m.tubo("drone", mat, fio, D_ENC, lados=4, ident=f"jgb{k}_laco_{i}")
    de_f = nome_f if g_f is not None else f"servo_ombro{k}_ficha_a"
    y_fora = sy * (float(placa.hi[1]) + 0.0025)                  # por fora da borda da placa de baixo
    d_m = _u(mot[2])
    f_m = float(cx_m.c[0]) + d_m[0] * float(cx_m.h[0])           # face do borne do motor
    q_m = np.array([f_m, float(cx_m.c[1]), float(mot[1][2])])
    # por baixo da placa de baixo e das nervuras dela (medido: o que pende por baixo dela na passagem)
    son = cena.sonda({"drone": np.zeros(3)}, (np.array([min(float(E_c[0]), f_m) - 0.01, min(y_fora, float(q_m[1]))
                                                        - 0.01, float(placa.lo[2]) - 0.02]),
                                              np.array([max(float(E_c[0]), f_m) + 0.01, max(y_fora, float(q_m[1]))
                                                        + 0.01, float(placa.lo[2]) + 0.001])), excluir=_SO_FIOS)
    P_s = np.array([[float(E_c[0]) + (f_m + 0.010 - float(E_c[0])) * t_, y_fora + (float(q_m[1]) - y_fora) * t_,
                     float(placa.lo[2]) - 0.02] for t_ in np.linspace(0.0, 1.0, 12)])
    up_ = son.raios(P_s, np.repeat([[0.0, 0.0, 1.0]], len(P_s), axis=0), 0.0205)
    fundo_p = float(np.min(P_s[np.isfinite(up_), 2] + up_[np.isfinite(up_)])) if np.any(np.isfinite(up_)) else \
        float(placa.lo[2])
    z_sob = min(float(placa.lo[2]) - 0.0035, fundo_p - 0.5 * D_ENC - 0.0007)
    c_par = p_sep + e_ax * (0.5 * (offs[0] + offs[1]))           # o par: os 2 fios de fora da fita
    centro_m = _curva([c_par, np.array([float(c_par[0]), y_fora, float(c_par[2])]) if pico else
                       c_par + np.array([0.0, 0.0, -0.004]),
                       np.array([float(c_par[0]), y_fora, float(placa.hi[2]) + 0.003]),
                       np.array([float(c_par[0]), y_fora, z_sob]),
                       np.array([f_m + d_m[0] * 0.010, float(q_m[1]) + 0.004 * sy, z_sob]),
                       q_m + d_m * 0.010, q_m + d_m * 0.0012], 0.005)
    for i, mat in enumerate(_CORES_JGB[:2]):
        off = (i - 0.5) * sep
        m.tubo("drone", mat, [c + off * e_ax if j < 3 else c + off * np.array([0.0, 0.0, 1.0])
                              for j, c in enumerate(centro_m)], D_ENC, lados=4, ident=f"jgb{k}_motor_{i}")
    cena.ligar(f"jgb{k}_motor", de_f, f"el_drv{k}_motor", "drone", F, "drone", q_m,
               "6 × 26 AWG (PH2.0) → par do motor (2 × 22 AWG)", "cabo_motorredutor", k, via=f"ombro{k}_pivo_b_cabos",
               nota="JGB37-520: fita pelo atuador, laço no eixo de B, par do motor ao DRV8871 (os 4 do encoder "
                    "seguem num rabicho)")
    return p_sep + e_ax * (sum(offs[2:]) / 4.0), dentro


D_SENS4 = 0.0024        # cabo redondo de 4 × 28 AWG (encoder, I²C) — bainha
D_SENS5 = 0.0026        # cabo redondo de 5 × 28 AWG (SPI do AS5048A) — bainha


def _rabicho(cena: _Cena, ident: str, pts, d: float, n_vias: int, nome_de: str, k: int, nota: str,
            corpo: str = "drone") -> None:
    """Cabo de sensor do braço k até uma ficha JST-GH SOLTA na ponta (à espera de ficha no FC: o FC não tem onde ligar
    estes sinais — ver o relatório): bainha preta Ø d pelos pontos e a ficha (caixa) na ponta, ao longo do cabo."""
    m = cena.m
    linha = [np.asarray(q, dtype=float) for q in _curva([np.asarray(q, dtype=float) for q in pts], 0.004)]
    t = _u(linha[-1] - linha[-2])
    lat = _u(np.cross(t, EZ)) if abs(float(t[2])) < 0.9 else np.array([1.0, 0.0, 0.0])
    up = np.cross(lat, t)
    larg = 0.5 * (n_vias * 0.00125 + 0.002)
    c = linha[-1] + t * 0.0034
    if abs(float(t[2])) < 0.5:
        # a ficha (4,4 mm de altura) ASSENTA no que houver por baixo: com a bainha deitada numa placa, a ponta do cabo
        # sobe (nos últimos 8 mm) o que faltar para a ficha não entrar nela (medido com raios para baixo)
        sd = cena.sonda({corpo: np.zeros(3)}, (c - 0.008, c + 0.008), excluir=_SO_FIOS)
        P = np.array([c + a * 0.0028 * t + b * 0.9 * larg * lat for a in (-1.0, 0.0, 1.0) for b in (-1.0, 0.0, 1.0)])
        dd = sd.raios(P, np.repeat(-EZ[None], len(P), axis=0), 0.006)
        sobe = max(0.0, 0.0022 * abs(float(up[2])) + 0.5 * larg * abs(float(lat[2])) + 0.00015 - float(np.min(dd))) \
            if np.isfinite(dd).any() else 0.0
        if sobe > 0.0:
            sl = np.concatenate([[0.0], np.cumsum([np.linalg.norm(b - a) for a, b in itertools.pairwise(linha)])])
            f = np.clip((sl - (sl[-1] - 0.008)) / 0.008, 0.0, 1.0)
            linha = [q + sobe * (3.0 * x * x - 2.0 * x ** 3) * EZ for q, x in zip(linha, f, strict=True)]
            c = c + sobe * EZ
    m.tubo(corpo, "fios_preto", linha, d)
    m.caixa(corpo, "fios_jst", c, np.column_stack([t, lat, up]), [0.0030, larg, 0.0022])
    # (sem ligação no registo: a ponta não chega a nenhuma âncora — fica a ficha solta à espera da do FC)
    cena.ctx.registo.notas.setdefault("fios_rabichos", []).append(
        {"id": ident, "de": nome_de, "braco": k, "vias": n_vias, "corpo": corpo,
         "ponta": [round(float(v), 6) for v in c],
         "nota": f"{nota} — ficha JST-GH de {n_vias} vias solta (o FC não tem ficha publicada para ela)"})


# ====================================================================================== controladores dos braços (Pico 2)
D_SINAL_SERVO = 0.0018   # sinal + GND de um servo (2 × 28 AWG numa bainha): do Pico ao topo do servo-rail
D_DRV_SINAL = 0.0021     # IN1, IN2, GND do DRV8871 (3 × 28 AWG)
D_PICO_5V = 0.0012       # cada fio do par de 5 V de um Pico (26 AWG, silicone)
GH_ACIMA = 0.0022        # a ficha do cabo (JST-GH) sai 2,2 mm acima da ficha da placa (e entra 1,4 mm nela)


def _pico_lados(cena: _Cena) -> dict:
    """{n: (sinal de y do lado, braços que serve)} dos controladores dos braços publicados (`el_pico{n}_uart`)."""
    out = {}
    for n in (1, 2):
        a = cena.ponto_ancora(f"el_pico{n}_uart")
        if a is None or a[0] != "drone":
            continue
        bracos = tuple(k for k in range(1, 5) if cena.ponto_ancora(f"el_pico{n}_drv{k}") is not None)
        out[n] = (1.0 if float(a[1][1]) >= 0.0 else -1.0, bracos)
    return out


def _ficha_pico(cena: _Cena, nome: str, peca: tuple = ("cablagem", 0)):
    """A ficha JST-GH do cabo metida DE CIMA na ficha `nome` da placa do Pico (desenhada na `peca` do cabo): (topo da
    ficha do cabo — o cabo sai daí para +z —, ponto da âncora) ou None."""
    anc, cx = cena.ponto_ancora(nome), cena.caixa(nome)
    if anc is None or cx is None:
        return None
    c = np.array([float(cx.c[0]), float(cx.c[1]), float(cx.hi[2]) + 0.0004])
    meia = [max(0.5 * float(cx.hi[0] - cx.lo[0]) - 0.0005, 0.001), max(0.5 * float(cx.hi[1] - cx.lo[1]) - 0.0005, 0.001),
            0.5 * GH_ACIMA + 0.0007]
    with cena.m.peca(*peca):
        cena.m.caixa("drone", "fios_jst", c, np.eye(3), meia)
    return np.array([float(cx.c[0]), float(cx.c[1]), float(cx.hi[2]) + GH_ACIMA]), np.asarray(anc[1], dtype=float)


def _cabeca_pico(topo, y_face: float, x_faixa: float, z_sobre: float, z_base: float, avanco: float = 0.0015) -> list:
    """Do topo da ficha do cabo: sobe a z_sobre, vai à faixa x_faixa (logo à saída) e à face (y = y_face), e desce por ela
    até z_base."""
    t = np.asarray(topo, dtype=float)
    s = 1.0 if y_face >= float(t[1]) else -1.0
    pts = [t, t + np.array([0.0, 0.0, 0.0012]), np.array([t[0], t[1] + s * avanco, z_sobre])]
    dx = x_faixa - float(t[0])
    if abs(dx) > 1e-6:
        pts.append(np.array([x_faixa, t[1] + s * (avanco + 0.002 + 1.4 * abs(dx)), z_sobre]))
    pts += [np.array([x_faixa, y_face - s * 0.002, z_sobre]), np.array([x_faixa, y_face, z_sobre - 0.0025]),
            np.array([x_faixa, y_face, z_base])]
    return pts


def _faces_pico(cena: _Cena, n: int, sg: float):
    """(y da borda de dentro do suporte, y da borda de fora) da placa do Pico n — 0,9 mm por fora das fichas da placa
    (o suporte impresso acaba aí; a borda de fora é também a da placa de cima)."""
    ys_d, ys_f = [], []
    for nome in cena.ancoras:
        if not nome.startswith(f"el_pico{n}_"):
            continue
        cx = cena.caixa(nome)
        if cx is None:
            continue
        ys_d.append(min(abs(float(cx.lo[1])), abs(float(cx.hi[1]))))
        ys_f.append(max(abs(float(cx.lo[1])), abs(float(cx.hi[1]))))
    if not ys_d:
        return None
    return sg * (min(ys_d) - 0.0009), sg * (max(ys_f) + 0.0009)


def _controladores_bracos(cena: _Cena) -> None:
    """Build ACESSÍVEL com os 2 controladores dos braços (Raspberry Pi Pico 2 numa placa de ligação com 12 fichas JST-GH
    de entrada por cima, `el_pico{n}_*`; n = 1 do lado +y — braços 1 e 3 —, n = 2 do lado −y — braços 2 e 4).

    Todas as fichas levam a ficha do cabo metida de cima; cada cabo sobe 1,2 mm, segue à altura do topo das fichas e
    desce pela face da placa do seu lado: os da fila de DENTRO pela borda de dentro do suporte, na sua faixa (o x da
    ficha); os da fila de FORA vão para fora (DRV, Hall) — exceto os sinais dos servos, que passam por cima da placa
    (por cima do Pico, entre os cabos do I²C e do SPI do seu braço) e descem pela borda de dentro. Daí, deitados na
    placa de cima pelo mapa 2,5D:
      · SERVOS: o rail do UBEC fica só com a alimentação (V+/GND das fichas dos servos); por cima dele, uma ficha de 2
        vias por servo (sinal + GND) e um cabo de 2 × 28 AWG até à ficha `el_pico{n}_servo{k}` (a 3.ª via fica livre)."""
    lados = _pico_lados(cena)
    pt = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
    if not lados or pt is None or cena.placa is None:
        return
    z_pc = float(pt.hi[2])                                      # topo da placa de cima
    tronco_5v = _tronco_5v(cena, z_pc)
    gps_de = None                                   # a ficha GPS do FC (uma UART livre): para o Pico do lado dela
    gps = cena.fc_con("el_fc_con_gps") if cena.ctx.geom_existente("el_fc_con_gps") is not None else None
    if gps is not None:
        gps_de = min(lados, key=lambda nn: abs(float(gps.c[1]) - lados[nn][0] * 0.06))
    faces = {n: _faces_pico(cena, n, sg) for n, (sg, _b) in lados.items()}
    lados = {n: v for n, v in lados.items() if faces[n] is not None}
    cena.pico_reservas = {n: _cabecas_dentro(cena, n, sg, bracos, faces[n], z_pc) for n, (sg, bracos) in lados.items()}
    # ordem: os sinais dos servos, as UART (a da ficha GPS primeiro: desce das fichas do Pi para a placa) e só depois
    # o 5 V (que dá a volta à janela por fora e passa por cima delas)
    for n, (sg, bracos) in sorted(lados.items()):
        _pico_servos(cena, n, sg, bracos, faces[n], z_pc)
        _pico_hall_drv(cena, n, sg, bracos, faces[n], so=("hall",))      # (os DRV já foram, antes do 12 V)
    for n in sorted(lados, key=lambda nn: nn != gps_de):
        _pico_uart(cena, n, lados[n][0], faces[n], z_pc, gps if gps_de == n else None)
    for n, (sg, bracos) in sorted(lados.items()):
        _pico_spi(cena, n, sg, bracos, faces[n], z_pc)
        _pico_i2c(cena, n, sg, bracos, faces[n], z_pc)
    for n, (sg, _b) in sorted(lados.items()):
        _pico_5v(cena, n, sg, faces[n], z_pc, tronco_5v)


def _faixas_servo(cena: _Cena, n: int, bracos) -> dict:
    """k → x da faixa do sinal do servo k pela borda de dentro da placa do Pico n: entre o cabo do I²C e o do SPI do
    mesmo braço (as faixas deles são o x das fichas)."""
    out = {}
    for k in bracos:
        ci, cs = cena.caixa(f"el_pico{n}_i2c{k}"), cena.caixa(f"el_pico{n}_spi{k}")
        if ci is None or cs is None:
            continue
        xi, xs = float(ci.c[0]), float(cs.c[0])
        s_ = 1.0 if xs > xi else -1.0
        out[k] = 0.5 * ((xi + s_ * 0.5 * D_SENS4) + (xs - s_ * 0.5 * D_SENS5))
    return out


def _cabecas_dentro(cena: _Cena, n: int, sg: float, bracos, faces, z_pc: float) -> list:
    """[(ficha, pontos, raio)] das cabeças de TODOS os cabos que descem pela borda de dentro da placa do Pico n (a fila
    de dentro e os sinais dos servos): reservadas nos mapas 2,5D da placa de cima — nenhum cabo passa pela descida
    de outro, desenhado antes ou depois."""
    out = []
    pedidos = [(f"el_pico{n}_spi{k}", D_SENS5, None) for k in bracos] + \
        [(f"el_pico{n}_i2c{k}", D_SENS4, None) for k in bracos] + \
        [(f"el_pico{n}_uart", D_PICO_UART, None), (f"el_pico{n}_alimentacao", D_PICO_CABO2, None)] + \
        [(f"el_pico{n}_servo{k}", D_SINAL_SERVO, x) for k, x in _faixas_servo(cena, n, bracos).items()]
    for nome, d, faixa in pedidos:
        cx = cena.caixa(nome)
        if cx is None:
            continue
        r = 0.5 * d
        topo = np.array([float(cx.c[0]), float(cx.c[1]), float(cx.hi[2]) + GH_ACIMA])
        sobre = float(topo[2]) + (0.0020 if faixa is not None else 0.0022)
        pts = _cabeca_pico(topo, faces[0] - sg * (r + 0.0005), float(topo[0]) if faixa is None else faixa, sobre,
                           z_pc + r + 0.00015)
        out.append((nome, pts, r))
    return out


def _reservar(mesa, cena: _Cena, n: int, exceto: str) -> None:
    """Junta ao mapa as cabeças reservadas do Pico n, menos a do próprio cabo (`exceto`)."""
    for nome, pts, r in cena.pico_reservas.get(n, []):
        if nome != exceto:
            mesa.juntar(np.asarray(_reamostrar([np.asarray(p, dtype=float) for p in pts], 0.001)), r)


def _pico_servos(cena: _Cena, n: int, sg: float, bracos, faces, z_pc: float) -> None:
    """Sinal PWM de cada servo do cotovelo servido pelo Pico n: derivação no cabo do servo (rail → feixe do ombro),
    16 mm antes da junção no feixe, e cabo de 2 × 28 AWG até à ficha `el_pico{n}_servo{k}` (pela borda de dentro da
    placa do Pico, por cima dela, entre os cabos do I²C e do SPI do mesmo braço)."""
    m = cena.m
    y_dentro = faces[0]
    if True:
        # ---- sinais dos servos: derivação no cabo do servo junto ao feixe do ombro → ficha do Pico
        r_s = 0.5 * D_SINAL_SERVO
        lanes = {k: x for k, x in _faixas_servo(cena, n, bracos).items() if k in cena.servo_linhas}
        if not lanes:
            return
        derivacoes = {}
        for k, x_l in lanes.items():
            linha = np.asarray(cena.servo_linhas[k], dtype=float)
            sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(linha, axis=0), axis=1))])
            # no troço do cabo do servo que assenta na placa de cima (não no que sobe para a junção no feixe), o mais
            # perto da faixa do sinal na borda do Pico — a derivação fica deitada e o cabo de sinal é curto
            s_d = max(float(sl[-1]) - 0.016, 0.5 * float(sl[-1]))
            alvo_d = np.array([x_l, y_dentro - sg * 0.006])
            dz_l = np.gradient(linha[:, 2], sl, edge_order=1) if len(sl) > 2 else np.zeros(len(sl))
            deitado = np.flatnonzero((linha[:, 2] <= z_pc + 0.5 * D_CABO_SERVO + 0.0035) & (np.abs(dz_l) < 0.15)
                                     & (sl <= float(sl[-1]) - 0.016) & (sl >= 0.012))
            if len(deitado):
                j = int(deitado[np.argmin(np.linalg.norm(linha[deitado, :2] - alvo_d, axis=1))])
                s_d = float(sl[j])
            S = np.array([np.interp(s_d, sl, linha[:, j]) for j in range(3)])
            t = np.array([np.interp(s_d + 0.001, sl, linha[:, j]) for j in range(3)]) - S
            t = _u(np.array([float(t[0]), float(t[1]), 0.0]))          # (a derivação e a saída do sinal: na horizontal)
            derivacoes[k] = (S, t)
        lo = np.array([min(*lanes.values(), *[float(d[0][0]) for d in derivacoes.values()]) - 0.025,
                       min(y_dentro, *[float(d[0][1]) for d in derivacoes.values()]) - 0.015, 0.0])
        hi = np.array([max(*lanes.values(), *[float(d[0][0]) for d in derivacoes.values()]) + 0.025,
                       max(y_dentro, *[float(d[0][1]) for d in derivacoes.values()]) + 0.015, 0.0])
        for k, (S, t) in derivacoes.items():
            mesa = _Mesa(cena, lo, hi, z_pc + r_s + 0.00015, acima=0.008)
            if cena.fc is not None:
                mesa.proibir(cena.fc.lo - 0.0015, cena.fc.hi + 0.0015)
            if cena.rpi is not None:
                mesa.proibir(cena.rpi.lo - 0.0015, cena.rpi.hi + 0.0015)
            _reservar(mesa, cena, n, exceto=f"el_pico{n}_servo{k}")
            fp = _ficha_pico(cena, f"el_pico{n}_servo{k}", ("cabo_servo", k))
            if fp is None:
                continue
            topo, anc_p = fp
            with m.peca("cabo_servo", k):
                # a derivação: termo-retráctil no cabo do servo; o laranja (com um GND) sai dela para o Pico — a termo
                # assenta na placa (o cabo do servo fica deitado nela: sobe o que faltar, ≤ a folga dela à bainha)
                r_t = 0.5 * (D_CABO_SERVO + 0.0012)
                sd = cena.sonda({"drone": np.zeros(3)}, (S - 0.012, S + 0.012), excluir=_SO_FIOS)
                dd = sd.raios(np.array([S + f * 0.006 * t for f in (-1.0, 0.0, 1.0)]),
                              np.repeat(-EZ[None], 3, axis=0), r_t + 0.003)
                sobe = min(max(0.0, r_t + 0.00015 - float(np.min(dd))), 0.0006) if np.isfinite(dd).any() else 0.0
                m.tubo("drone", "fios_termo", [S - 0.006 * t + sobe * EZ, S + 0.006 * t + sobe * EZ], 2.0 * r_t,
                       cabo=False)
                lat = _u(np.cross(EZ, t))
                if float(np.dot(lat, np.array([lanes[k], y_dentro, 0.0]) - S)) < 0.0:
                    lat = -lat
                # sai da termo encostado ao cabo do servo (não de dentro dele) e afasta-se para o lado do Pico
                encosto = S + lat * (0.5 * D_CABO_SERVO + r_s + 0.0002)
                encosto[2] = max(float(encosto[2]), z_pc + r_s + 0.00015)
                ini = encosto + t * 0.003
                z_b = z_pc + r_s + 0.00015
                cab = _cabeca_pico(topo, y_dentro - sg * (r_s + 0.0005), lanes[k], float(topo[2]) + 0.0020, z_b)
                cam = mesa.rota(ini, cab[-1], r_s + 0.00005, folga=0.00015, soltar=0.0012)
                if cam is None:
                    warnings.warn(f"detalhes/fios: sem caminho livre da derivação do servo {k} ao Pico {n}",
                                  stacklevel=2)
                    continue
                linha_s = _curva([encosto - t * 0.004, *cam[:-1], *cab[::-1]], 0.003)
                m.tubo("drone", "fios_preto", linha_s, D_SINAL_SERVO)
                mesa.juntar(np.asarray(_reamostrar(linha_s, 0.001)), r_s)
                _J, _dJ, nome_c, c_c, qc = cena.juncao_servo[k]
                cena.ligar(f"servo{k}_sinal", f"el_pico{n}_servo{k}", nome_c, "drone", anc_p, c_c, qc,
                           "2 × 28 AWG (sinal PWM + GND) até à derivação; daí o laranja do cabo do servo", "cabo_servo",
                           k, via="derivação no cabo do servo junto ao feixe do ombro",
                           nota=f"PWM do servo do cotovelo {k}: do Pico {n} à derivação no cabo do servo e por ele ao "
                                "DS3218MG")


D_HALL = D_SENS4         # o cabo do Hall (encoder do JGB37-520): 4 × 28 AWG


def _pico_drvs(cena: _Cena) -> None:
    """Os cabos de sinal dos DRV8871 (do Pico do seu lado), desenhados ANTES do 12 V dos drivers (`_alimentacao_atuadores`):
    o 12 V contorna-os por baixo da placa de baixo — ver `_pico_hall_drv`."""
    lados = _pico_lados(cena)
    for n, (sg, bracos) in sorted(lados.items()):
        faces = _faces_pico(cena, n, sg)
        if faces is not None:
            _pico_hall_drv(cena, n, sg, bracos, faces, so=("drv",))


def _pico_hall_drv(cena: _Cena, n: int, sg: float, bracos, faces, so=("hall", "drv")) -> None:
    """Fila de FORA da placa do Pico n — os dois que vão para baixo, pela face de fora da placa (a borda dela é a da
    placa de cima) até à faixa da placa de baixo que fica por fora da de cima (mapa 2,5D da placa de baixo):
      · HALL (encoder do JGB37-520, 4 vias): da separação do cabo do motorredutor (na faixa, onde os 4 do encoder entram
        na bainha) até debaixo da ficha `el_pico{n}_hall{k}`;
      · DRV8871 (IN1, IN2, GND): da ficha `el_pico{n}_drv{k}` pela faixa até à borda da placa de baixo, desce por fora
        dela, vai por baixo dela (mapa virado: por baixo do que lá pende) até debaixo da ficha `el_drv{k}_sinal` (pinos
        virados para baixo) e sobe para a ficha Dupont de 3 vias metida neles."""
    m, placa = cena.m, cena.placa
    if placa is None:
        return
    _y_d, y_f = faces
    z_pb = float(placa.hi[2])
    pedidos = []
    for k in bracos:
        if "hall" in so and k in cena.hall_ini:
            pedidos.append(("hall", k, D_HALL))
        if "drv" in so and cena.ponto_ancora(f"el_drv{k}_sinal") is not None and \
                cena.caixa(f"el_drv{k}_sinal") is not None:
            pedidos.append(("drv", k, D_DRV_SINAL))
    if not pedidos:
        return
    xs = [float(cena.caixa(f"el_pico{n}_{t}{k}").c[0]) for t, k, _d in pedidos
          if cena.caixa(f"el_pico{n}_{t}{k}") is not None] + [float(cena.hall_ini[k][0][0]) for t, k, _d in pedidos
                                                               if t == "hall"]
    if not xs:
        return
    r_max = 0.5 * max(d for _t, _k, d in pedidos)
    lo = np.array([min(xs) - 0.02, min(sg * 0.060, sg * (float(placa.hi[1]) + 0.004)), 0.0])
    hi = np.array([max(xs) + 0.02, max(sg * 0.060, sg * (float(placa.hi[1]) + 0.004)), 0.0])
    mesa = _Mesa(cena, lo, hi, z_pb + r_max + 0.00015, acima=0.006)
    # os Hall primeiro (correm ao longo da faixa); os do DRV atravessam-na para a borda e passam por cima deles
    for tipo, k, d in sorted(pedidos, key=lambda p: p[0] != "hall"):
        fp = _ficha_pico(cena, f"el_pico{n}_{tipo}{k}",
                         ("cabo_sensores_braco" if tipo == "hall" else "cabo_motorredutor", k))
        if fp is None:
            continue
        topo, anc_p = fp
        r = 0.5 * d
        z_b = z_pb + r + 0.00015
        y_face = y_f + sg * (r + 0.0005)
        cab = _cabeca_pico(topo, y_face, float(topo[0]), float(topo[2]) + 0.0022, z_b)
        if tipo == "hall":
            P0 = np.asarray(cena.hall_ini[k][0], dtype=float)
            # a bainha nasce onde os 4 do encoder se juntam e sai da fita para o lado do Pico (em x), já na faixa
            p_b = np.array([float(P0[0]), float(P0[1]), max(z_b, float(P0[2]) + r - 0.5 * D_ENC)])
            s_x = 1.0 if float(topo[0]) > float(P0[0]) else -1.0
            ini = np.array([float(p_b[0]) + s_x * 0.0060, float(p_b[1]), z_b])
            cam = mesa.rota(ini, cab[-1], r + 0.00005, folga=0.00015, soltar=0.0016)
            if cam is None:
                warnings.warn(f"detalhes/fios: sem caminho livre do Hall do braço {k} ao Pico {n}", stacklevel=2)
                continue
            with m.peca("cabo_sensores_braco", k):
                linha = _curva([p_b, *cam, *cab[::-1][1:]], 0.003)
                m.tubo("drone", "fios_preto", linha, d)
            mesa.juntar(np.asarray(_reamostrar(linha, 0.001)), r)
            nome_f = f"ombro{k}_fuso_base_conector"
            de = nome_f if cena.ctx.geom_existente(nome_f) is not None else f"servo_ombro{k}_ficha_a"
            fa = cena.ponto_ancora(f"servo_ombro{k}_ficha_a")
            if fa is not None:
                cena.ligar(f"hall{k}", de, f"el_pico{n}_hall{k}", "drone", np.asarray(fa[1], dtype=float), "drone",
                           anc_p, "6 × 26 AWG (PH2.0) → 4 × 28 AWG (GND, VCC, A, B)", "cabo_sensores_braco", k,
                           via=f"ombro{k}_pivo_b_cabos", nota=f"encoder Hall do JGB37-520 do braço {k} ao Pico {n}")
            continue
        # ---- DRV8871: a ficha de 3 vias nos pinos (virados para baixo) e o caminho por baixo da placa de baixo
        a_s, cx_s = cena.ponto_ancora(f"el_drv{k}_sinal"), cena.caixa(f"el_drv{k}_sinal")
        q_s = np.asarray(a_s[1], dtype=float)
        h_ficha = float(cx_s.lo[2]) - float(q_s[2])
        c_f = np.array([float(q_s[0]), float(q_s[1]), float(q_s[2]) + 0.5 * h_ficha])
        y_borda = sg * (abs(float(placa.hi[1] if sg > 0 else placa.lo[1])) + r + 0.0007)
        borda = np.array([float(q_s[0]), y_borda, z_b])
        cam = mesa.rota(cab[-1], borda, r + 0.00005, folga=0.00015, soltar=0.002)
        if cam is None:
            warnings.warn(f"detalhes/fios: sem caminho livre do sinal do DRV {k} à borda da placa de baixo", stacklevel=2)
            continue
        z_bb = float(placa.lo[2])
        lo_b = np.array([min(float(q_s[0]), float(borda[0])) - 0.012, min(float(q_s[1]), y_borda) - 0.010, 0.0])
        hi_b = np.array([max(float(q_s[0]), float(borda[0])) + 0.012, max(float(q_s[1]), y_borda) + 0.010, 0.0])
        mesa_b = _Mesa(cena, lo_b, hi_b, z_bb - r - 0.00015, acima=0.030, invertido=True)
        fim_b = np.array([float(q_s[0]), float(q_s[1]), float(q_s[2]) - 0.004])
        ini_b = np.array([float(borda[0]), y_borda, z_bb - r - 0.002])
        cam_b = mesa_b.rota(ini_b, fim_b, r + 0.00005, folga=0.00015, soltar=0.0025)
        if cam_b is None:
            warnings.warn(f"detalhes/fios: sem caminho livre por baixo da placa até ao DRV {k}", stacklevel=2)
            continue
        z_desce = min(float(p[2]) for p in cam_b)
        with m.peca("cabo_motorredutor", k):
            m.caixa("drone", "fios_dupont", c_f, np.eye(3), [0.00125, 0.0038, 0.5 * h_ficha])
            linha = _curva([*cab, *cam[1:-1], borda, np.array([float(borda[0]), y_borda, z_desce]), *cam_b[1:],
                            np.array([float(q_s[0]), float(q_s[1]), float(q_s[2]) - 0.0012]), q_s + np.array(
                                [0.0, 0.0, -0.0001])], 0.003)
            m.tubo("drone", "fios_preto", linha, d)
        mesa.juntar(np.asarray(_reamostrar(linha, 0.001)), r)
        cena.ligar(f"drv{k}_sinal", f"el_pico{n}_drv{k}", f"el_drv{k}_sinal", "drone", anc_p, "drone",
                   np.array([float(q_s[0]), float(q_s[1]), float(cx_s.lo[2])]), "3 × 28 AWG (IN1, IN2, GND)",
                   "cabo_motorredutor", k, nota=f"sinais do DRV8871 do braço {k}: do Pico {n}, por baixo da placa de baixo")


def _pinos_sensor(cena: _Cena, corpo: str, q, dq) -> tuple:
    """(nome do geom dos pinos, ponto na superfície deles, direção da fila) da barra de pinos de uma placa de sensor cuja
    âncora é `q` (pontas dos pinos, a apontar `dq`): o geom de pinos dourados mais perto (`est_<corpo>_ouro`), o ponto
    pelo raio de q para trás e a fila pelos triângulos dele à volta."""
    nome = f"est_{corpo}_ouro"
    if cena.ctx.geom_existente(nome) is None:
        return None, np.asarray(q, dtype=float), np.array([1.0, 0.0, 0.0])
    q, dq = np.asarray(q, dtype=float), _u(dq)
    T = cena.tri.lista(corpo, nome)
    toque = q
    if len(T):
        V = T.reshape(-1, 3)
        toque = V[int(np.argmin(np.linalg.norm(V - q, axis=1)))]           # um vértice dos pinos (na superfície)
        V = V[np.linalg.norm(V - q, axis=1) < 0.009]
        if len(V) > 3:
            ext = V.max(axis=0) - V.min(axis=0)
            ext = ext - abs(float(np.dot(ext, dq))) * np.abs(dq)
            fila = np.eye(3)[int(np.argmax(ext))]
            return nome, toque, fila
    return nome, toque, np.array([1.0, 0.0, 0.0])


def _pico_spi(cena: _Cena, n: int, sg: float, bracos, faces, z_pc: float) -> None:
    """SPI do AS5048A de cada ombro servido pelo Pico n (6 vias: VDD, GND, CSn, CLK, MISO, MOSI): ficha Dupont de 6 vias
    nos pinos da placa do sensor (na ponta de dentro do veio do ombro, por baixo das placas e por fora da borda delas),
    o cabo sobe a direito por fora das bordas (medido: livre) até acima da placa de cima, entra por cima dela e segue
    (mapa 2,5D) até à borda de dentro da placa do Pico e à ficha `el_pico{n}_spi{k}`."""
    m = cena.m
    pt = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
    if pt is None:
        return
    d = D_SENS5
    r = 0.5 * d
    z_b = z_pc + r + 0.00015
    for k in bracos:
        a = cena.ponto_ancora(f"servo_ombro{k}_ficha_b")
        fp = _ficha_pico(cena, f"el_pico{n}_spi{k}", ("cabo_sensores_braco", k))
        if a is None or a[0] != "drone" or fp is None:
            continue
        topo, anc_p = fp
        q, dq = np.asarray(a[1], dtype=float), _u(a[2])
        nome, toque, fila = _pinos_sensor(cena, "drone", q, dq)
        lat = _u(np.cross(dq, fila))
        c_f = q + dq * 0.003
        R_f = np.column_stack([fila, lat, dq])
        sx = 1.0 if float(q[0]) >= 0.0 else -1.0
        x_borda = sx * max(abs(float(pt.lo[0])), abs(float(pt.hi[0])))
        sai = q + dq * 0.0062
        sobe = sai + dq * 0.0030
        z_alto = z_pc + r + 0.0025
        x_dentro = x_borda - sx * 0.004
        cab = _cabeca_pico(topo, faces[0] - sg * (r + 0.0005), float(topo[0]), float(topo[2]) + 0.0022, z_b)
        ini = np.array([x_dentro - sx * 0.002, float(sobe[1]), z_b])
        lo = np.array([min(float(ini[0]), float(cab[-1][0])) - 0.015, min(float(ini[1]), float(cab[-1][1])) - 0.015,
                       0.0])
        hi = np.array([max(float(ini[0]), float(cab[-1][0])) + 0.015, max(float(ini[1]), float(cab[-1][1])) + 0.015,
                       0.0])
        # (pode passar por cima da manga do feixe do ombro, que está deitada na placa de cima entre a borda dela e o
        # Pico: Ø 9 — é a única passagem; por baixo dela só onde levanta, junto à borda)
        mesa = _Mesa(cena, lo, hi, z_b, acima=0.0115)
        if cena.rpi is not None:
            mesa.proibir(cena.rpi.lo - 0.004, cena.rpi.hi + 0.004)
        _reservar(mesa, cena, n, exceto=f"el_pico{n}_spi{k}")
        cam = mesa.rota(ini, cab[-1], r + 0.00005, folga=0.00015, soltar=0.002)
        if cam is None:
            warnings.warn(f"detalhes/fios: sem caminho livre do SPI do ombro {k} ao Pico {n}", stacklevel=2)
            continue
        with m.peca("cabo_sensores_braco", k):
            m.caixa("drone", "fios_dupont", c_f, R_f, [0.5 * (6 * 0.00254) + 0.0004, 0.00125, 0.003])
            acesso = [sai, sobe, np.array([float(sobe[0]), float(sobe[1]), float(sobe[2]) + 0.004]),
                      np.array([float(sobe[0]), float(sobe[1]), z_alto]), np.array([x_dentro, float(sobe[1]), z_alto]),
                      np.array([x_dentro - sx * 0.0015, float(sobe[1]), z_b + 0.0008])]
            linha = _curva([*acesso, *cam, *cab[::-1][1:]], 0.003)
            m.tubo("drone", "fios_preto", linha, d)
        if nome is not None:
            cena.ligar(f"spi{k}", nome, f"el_pico{n}_spi{k}", "drone", toque, "drone", anc_p,
                       "6 × 28 AWG (VDD, GND, CSn, CLK, MISO, MOSI)", "cabo_sensores_braco", k,
                       nota=f"AS5048A do ombro {k} (SPI) ao Pico {n}")


def _pico_i2c(cena: _Cena, n: int, sg: float, bracos, faces, z_pc: float) -> None:
    """I²C do AS5600 de cada cotovelo servido pelo Pico n (4 vias: VCC, GND, SDA, SCL), pelo FEIXE do ombro: ficha Dupont
    de 4 vias nos pinos da placa do sensor (na ponta do M8 do cotovelo, virados para fora); o cabo desce por fora da
    placa e do suporte dela, passa por baixo do suporte e do servo (fora do curso do garfo do mastro: o cabo é do braço),
    junta-se ao cabo do servo e segue colado a ele (por fora, em relação ao eixo do tubo) até à ponta da manga do feixe,
    onde entra por um lado dela; do lado do drone sai da manga 1 cm antes da ponta e vai pela placa de cima (mapa 2,5D)
    até à borda de dentro da placa do Pico e à ficha `el_pico{n}_i2c{k}`."""
    m = cena.m
    d = D_SENS4
    r = 0.5 * d
    z_b = z_pc + r + 0.00015
    for k in bracos:
        a = cena.ponto_ancora(f"servo_cotovelo{k}_ficha_b")
        fp = _ficha_pico(cena, f"el_pico{n}_i2c{k}", ("cabo_sensores_braco", k))
        if a is None or fp is None or k not in cena.servo_braco or k not in cena.feixe_ombro:
            continue
        topo, anc_p = fp
        linha_s, nb, bb, dz_ax, _w_tubo = cena.servo_braco[k]
        A, dir_b, nb_f, W2, dir_d, _pts_d = cena.feixe_ombro[k]
        if a[0] != nb or nb_f != nb:
            continue
        q, dq = np.asarray(a[1], dtype=float), _u(a[2])
        nome, toque, fila = _pinos_sensor(cena, nb, q, dq)
        lat = _u(np.cross(dq, fila))
        # ---- braço: ficha, descida por fora, por baixo do suporte e do servo até ao cabo do servo
        gr = cena.tri.de(nb)
        if gr is None:
            continue
        caixa_lo = np.array([float(q[0]) - 0.045, min(float(q[1]), float(linha_s[-1][1])) - 0.02, -0.08])
        caixa_hi = np.array([float(q[0]) + 0.045, max(float(q[1]), float(linha_s[-1][1])) + 0.02, 0.08])
        idx = gr.indices(caixa_lo, caixa_hi, np.array([not _SO_FIOS.search(nm) for nm in gr.nomes], dtype=bool))
        z_fundo = float(np.min(gr.T[idx][:, :, 2])) if len(idx) else float(q[2]) - 0.02
        z_low = z_fundo - r - 0.0012
        sai = q + dq * 0.0062
        y_desce = sai + dq * (0.0012 + r)
        # o ponto do cabo do servo onde o I²C se lhe junta: ~45 mm de cabo antes da ficha do servo
        sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(linha_s, axis=0), axis=1))])
        j_ju = int(np.searchsorted(sl, float(sl[-1]) - 0.045))
        r_x = 0.5 * D_CABO_SERVO

        def colado(p, bb=bb, dz_ax=dz_ax, r_x=r_x):
            """O ponto do I²C colado POR BAIXO ao cabo do servo em p, rodado para fora do eixo do tubo (no plano ⟂ ao
            tubo): por baixo da ponta da manga só sai o cabo do servo (os do ESC vão por cima do tubo)."""
            dd, zz = bb.d(p), bb.dz(p) - dz_ax
            rr = math.hypot(dd, zz)
            fora = np.array([dd / rr, zz / rr]) if rr > 1e-6 else np.array([0.0, -1.0])
            v = _u(np.array([0.35 * fora[0], 0.35 * fora[1] - 1.0, 0.0]))[:2]       # sobretudo para baixo
            off = r_x + r + 0.00025
            return bb.p(bb.s(p), dd + v[0] * off, dz_ax + zz + v[1] * off)
        # do ponto de junção até ao cabo do servo à saída da vaga D (o 2.º ponto dele, 4 mm fora da ponta da manga)
        ao_longo = [colado(p) for p in linha_s[1: j_ju + 1][::-1]]
        P_j = ao_longo[0]
        # entra na manga pelo lado do cabo do servo, 2 mm antes da ponta A (o fim fica dentro dela)
        lado_b = np.asarray(ao_longo[-1]) - A
        lado_b = _u(lado_b - float(np.dot(lado_b, dir_b)) * dir_b)
        # (pela malha, 17 mm antes da ponta: antes da termo-retráctil da ponta, onde os cabos das vagas ainda vão dentro
        # da manga; o I²C corre por fora da termo até lá)
        r_t = 0.5 * (D_FEIXE + 0.0012)
        ao_longo.append(A + dir_b * 0.004 + lado_b * (r_t + r + 0.0004))       # (afasta-se da ponta ainda por fora dela)
        ao_longo.append(A - dir_b * 0.003 + lado_b * (r_t + r + 0.0004))
        ao_longo.append(A - dir_b * 0.0145 + lado_b * (r_t + r + 0.0004))
        entra_b = A - dir_b * 0.017 + lado_b * (0.5 * D_FEIXE + r + 0.0003)
        dentro_b = A - dir_b * 0.0178 + lado_b * (0.5 * D_FEIXE - r - 0.0003)     # (passa a malha e acaba logo dentro)
        braco_pts = [sai, sai + dq * 0.0012, y_desce + np.array([0.0, 0.0, -0.004]),
                     np.array([float(y_desce[0]), float(y_desce[1]), z_low]),
                     np.array([float(P_j[0]), float(y_desce[1]) - dq[1] * 0.002, z_low]) if abs(dq[1]) > 0.5 else
                     np.array([float(y_desce[0]), float(P_j[1]), z_low]),
                     np.array([float(P_j[0]), float(P_j[1]), z_low]), *ao_longo, entra_b, dentro_b]
        # ---- drone: sai da manga pelo lado do Pico, 2 mm antes da ponta W2, e vai pela placa de cima
        alvo_xy = np.array([float(topo[0]), faces[0] - sg * 0.004])
        lado_d = np.array([float(alvo_xy[0] - W2[0]), float(alvo_xy[1] - W2[1]), 0.0])
        lado_d = _u(lado_d - float(np.dot(lado_d, dir_d)) * dir_d) if float(np.linalg.norm(lado_d)) > 1e-6 else \
            np.array([0.0, sg, 0.0])
        lado_d = _u(lado_d * 0.82 + np.array([0.0, 0.0, -0.57]))           # 35° abaixo da horizontal
        dentro_d = W2 - dir_d * 0.0178 + lado_d * (0.5 * D_FEIXE - r - 0.0003)
        sai_d = W2 - dir_d * 0.017 + lado_d * (0.5 * D_FEIXE + r + 0.0003)
        ini = np.array([float(sai_d[0]) + lado_d[0] * 0.003, float(sai_d[1]) + lado_d[1] * 0.003, z_b])
        cab = _cabeca_pico(topo, faces[0] - sg * (r + 0.0005), float(topo[0]), float(topo[2]) + 0.0022, z_b)
        lo = np.array([min(float(ini[0]), float(cab[-1][0])) - 0.015, min(float(ini[1]), float(cab[-1][1])) - 0.012, 0.0])
        hi = np.array([max(float(ini[0]), float(cab[-1][0])) + 0.015, max(float(ini[1]), float(cab[-1][1])) + 0.012, 0.0])
        mesa = _Mesa(cena, lo, hi, z_b, acima=0.0115)
        if cena.rpi is not None:
            mesa.proibir(cena.rpi.lo - 0.004, cena.rpi.hi + 0.004)
        _reservar(mesa, cena, n, exceto=f"el_pico{n}_i2c{k}")
        cam = mesa.rota(ini, cab[-1], r + 0.00005, folga=0.00015, soltar=0.002)
        if cam is None:
            warnings.warn(f"detalhes/fios: sem caminho livre do I²C do cotovelo {k} ao Pico {n}", stacklevel=2)
            continue
        with m.peca("cabo_sensores_braco", k):
            m.caixa(nb, "fios_dupont", q + dq * 0.003, np.column_stack([fila, lat, dq]),
                    [0.5 * (4 * 0.00254) + 0.0004, 0.00125, 0.003])
            m.tubo(nb, "fios_preto", [*_curva(braco_pts[:7], 0.004), *braco_pts[7:]], d)
            linha_d = _curva([dentro_d, sai_d, *cam, *cab[::-1][1:]], 0.003)
            m.tubo("drone", "fios_preto", linha_d, d)
        if nome is not None:
            cena.ligar(f"i2c{k}", nome, f"el_pico{n}_i2c{k}", nb, toque, "drone", anc_p,
                       "4 × 28 AWG (VCC, GND, SDA, SCL)", "cabo_sensores_braco", k, via="feixe do ombro",
                       nota=f"AS5600 do cotovelo {k} (I²C) ao Pico {n}, junto ao cabo do servo e pela manga do feixe")


D_PICO_CABO2 = 0.0020    # cabo de 2 vias (5 V + GND) de cada Pico
D_PICO_UART = D_SENS4    # 4 vias (GND, 5 V, TX, RX)


def _tronco_5v(cena: _Cena, z_pc: float):
    """O tronco do 5 V dos Pico: um par (vermelho/preto, 22 AWG) soldado nas ilhas da saída 5 V do BEC (`el_pm_5v_pos/neg`,
    2.º fio em cada ilha, por cima do do Pi 5: chega de cima), que sobe por cima dos fios do Pi, desce pela face −y da
    pilha numa coluna livre (medida) e passa a borda da janela da placa de cima até uma emenda em Y (termo-retráctil)
    na placa de cima — daí um cabo de 2 vias para cada Pico. Devolve (ponto da emenda, toques nas ilhas) ou None."""
    pos, neg = cena.pdb_pad("el_pm_5v_pos"), cena.pdb_pad("el_pm_5v_neg")
    if pos is None or neg is None or cena.fc is None:
        return None
    m = cena.m
    d = D_PICO_5V
    r = 0.5 * d
    sinal_y = -1.0 if float(pos.c[1]) < float(cena.fc.c[1]) else 1.0     # as ilhas estão na borda ∓y
    Pc, Rc = _amostras_cabos(cena, "drone")
    z_ilha = max(float(pos.hi[2]), float(neg.hi[2]))
    # altura de passagem: por cima dos cabos que lá estão (os do Pi 5 fazem arco por cima das ilhas)
    zona_c = (np.abs(Pc[:, 0] - 0.5 * float(pos.c[0] + neg.c[0])) < 0.014) & (np.abs(Pc[:, 1] - float(pos.c[1])) < 0.012)
    z_alto = max(z_ilha + 0.004, float(np.max(Pc[zona_c, 2] + Rc[zona_c])) + r + 0.0004 if np.any(zona_c) else z_ilha)
    # a coluna: o 1.º x (a partir do meio das ilhas, para +x) com a vertical livre de peças e de cabos
    jan = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
    y_col = float(cena.fc.c[1]) + sinal_y * (float(cena.fc.h[1]) + 0.0085)
    z_bx = z_pc + r + 0.0012
    son = cena.sonda({"drone": np.zeros(3)}, (np.array([-0.04, y_col - 0.01, z_bx - 0.002]),
                                               np.array([0.04, y_col + 0.01, z_alto + 0.002])), excluir=_SO_FIOS)
    x_mid = 0.5 * float(pos.c[0] + neg.c[0])
    x_col = None
    for dx in np.arange(0.0, 0.020, 0.0005):
        xc = x_mid + dx
        G = np.array([[xc + ox, y_col + oy, z_bx] for ox in (-0.0021, 0.0, 0.0021) for oy in (-0.0012, 0.0, 0.0012)])
        if np.any(np.isfinite(son.raios_verticais(G, 1.0, z_alto - z_bx))):
            continue
        perto = (np.abs(Pc[:, 0] - xc) < Rc + 0.0024) & (np.abs(Pc[:, 1] - y_col) < Rc + 0.0015) & \
            (Pc[:, 2] > z_bx - 0.001) & (Pc[:, 2] < z_alto + 0.001)
        if not np.any(perto):
            x_col = float(xc)
            break
    if x_col is None or jan is None:
        return None
    # (a borda da janela da placa de cima do lado da coluna: o 1.º y para fora em que um raio para baixo bate na placa)
    y_borda = None
    sb = cena.sonda({"drone": np.zeros(3)}, (np.array([x_col - 0.004, y_col - sinal_y * 0.001 - 0.03, z_pc - 0.01]),
                                              np.array([x_col + 0.004, y_col + sinal_y * 0.001 + 0.03, z_pc + 0.002])),
                    excluir=_SO_FIOS, incluir=re.compile(r"^(placa_superior|est_)"))
    for dy in np.arange(0.0, 0.025, 0.0005):
        if sb.raio(np.array([x_col, y_col + sinal_y * dy, z_pc + 0.001]), [0.0, 0.0, -1.0], 0.004) is not None:
            y_borda = y_col + sinal_y * dy
            break
    if y_borda is None:
        return None
    emenda = np.array([x_col, y_borda + sinal_y * 0.0045, z_pc + 0.0013])
    # a passagem da coluna à emenda (por cima da borda da janela): por cima dos cabos que lá estão
    ys_r = np.linspace(y_col, float(emenda[1]), 12)
    z_run = z_bx
    for yy in ys_r:
        perto = (np.abs(Pc[:, 0] - x_col) < Rc + 0.0024) & (np.abs(Pc[:, 1] - yy) < Rc + r + 0.0003)
        if np.any(perto):
            z_run = max(z_run, float(np.max(Pc[perto, 2] + Rc[perto])) + r + 0.0003)
    if z_run > z_bx + 1e-6:
        emenda[2] = max(float(emenda[2]), z_run)
    toques = {}
    with m.peca("cabo_controlador", 0):
        for polo, pad, mat, ox in (("pos", pos, "fios_vermelho", -0.0007), ("neg", neg, "fios_preto", 0.0007)):
            fim = np.array([float(pad.c[0]), float(pad.c[1]), z_ilha + 0.5 * D_20 + r - 0.0001])
            pts = [fim, fim + np.array([0.0, 0.0, 0.002]), np.array([fim[0], fim[1], z_alto]),
                   np.array([x_col + ox, y_col, z_alto]), np.array([x_col + ox, y_col, z_run]),
                   np.array([x_col + ox, y_borda + sinal_y * 0.002, z_run]), emenda + np.array([ox, -sinal_y * 0.003, 0.0])]
            m.tubo("drone", mat, _curva(pts, 0.002), d, ident=f"pico_5v_{polo}")
            m.tubo("drone", "fios_estanho", [fim - np.array([0.0, 0.0, 0.0008]), fim + np.array([0.0, 0.0, 0.0010])],
                   D_SOLDA, lados=10, cabo=False)
            toques[polo] = (_toque_ilha(pad, fim), "el_pm_5v_pos" if polo == "pos" else "el_pm_5v_neg")
        m.caixa("drone", "fios_termo", emenda, np.eye(3), [0.0024, 0.0035, 0.0013])
    return emenda, toques, sinal_y


def _pico_5v(cena: _Cena, n: int, sg: float, faces, z_pc: float, tronco) -> None:
    """Cabo de 2 vias da emenda em Y do tronco do 5 V à ficha `el_pico{n}_alimentacao` (pela placa de cima: o mapa
    2,5D, por fora da janela da placa, e a borda de dentro da placa do Pico)."""
    if tronco is None:
        return
    emenda, toques, sinal_y = tronco
    fp = _ficha_pico(cena, f"el_pico{n}_alimentacao", ("cabo_controlador", n))
    if fp is None:
        return
    topo, anc = fp
    m = cena.m
    r = 0.5 * D_PICO_CABO2
    z_b = z_pc + r + 0.00015
    cab = _cabeca_pico(topo, faces[0] - sg * (r + 0.0005), float(topo[0]), float(topo[2]) + 0.0022, z_b)
    ini = emenda + np.array([0.0, sinal_y * 0.0035, 0.0])
    lo = np.array([min(float(ini[0]), float(cab[-1][0])) - 0.06, min(float(ini[1]), float(cab[-1][1])) - 0.015, 0.0])
    hi = np.array([max(float(ini[0]), float(cab[-1][0])) + 0.06, max(float(ini[1]), float(cab[-1][1])) + 0.015, 0.0])
    if sg * sinal_y < 0:                     # o Pico do outro lado: dá a volta à janela por +x
        lo[0], hi[0] = min(lo[0], -0.05), max(hi[0], 0.075)
        lo[1], hi[1] = min(lo[1], -0.06), max(hi[1], 0.06)
    mesa = _Mesa(cena, lo, hi, z_b, acima=0.006)
    jan = (np.array([-0.0465, -0.0325, 0.0]), np.array([0.0465, 0.0325, 0.0]))
    if cena.rpi is not None:
        jan = (cena.rpi.lo - 0.004, cena.rpi.hi + 0.004)
    mesa.proibir(*jan)
    for nn in cena.pico_reservas:
        _reservar(mesa, cena, nn, exceto=f"el_pico{n}_alimentacao")
    cam = mesa.rota(ini, cab[-1], r + 0.00005, folga=0.00015, soltar=0.003)
    if cam is None:
        warnings.warn(f"detalhes/fios: sem caminho livre do 5 V ao Pico {n}", stacklevel=2)
        return
    with m.peca("cabo_controlador", n):
        linha = _curva([emenda + np.array([0.0, sinal_y * 0.0015, 0.0]), *cam, *cab[::-1][1:]], 0.003)
        m.tubo("drone", "fios_preto", linha, D_PICO_CABO2)
    for polo, (toque, nome_pad) in toques.items():
        cena.ligar(f"pico{n}_5v_{polo}", nome_pad, f"el_pico{n}_alimentacao", "drone", toque, "drone", anc,
                   "22 AWG (tronco) → 2 × 26 AWG", "cabo_controlador", n, polo=polo,
                   via="emenda em Y na placa de cima", nota=f"5 V do BEC da placa de energia ao Pico {n}")


def _pico_uart(cena: _Cena, n: int, sg: float, faces, z_pc: float, gps) -> None:
    """UART do Pico n ao FC (4 vias: GND, 5 V, TX, RX). Com a ficha GPS do FC (`el_fc_con_gps`, uma UART: entrada lateral
    pela face +x): a ficha do cabo nela, sai para +x por baixo da placa de energia, desce às fichas USB/Ethernet do Pi,
    segue por cima delas até à borda da janela e daí pela placa de cima até ao Pico. Senão, a 2.ª UART do FC do lado
    do Pico (`el_fc_con_uart2`, `_pico_uart2`); sem ficha livre: rabicho com a ficha JST-GH solta junto ao FC."""
    fp = _ficha_pico(cena, f"el_pico{n}_uart", ("cabo_controlador", n))
    if fp is None or cena.fc is None:
        return
    topo, anc = fp
    m = cena.m
    r = 0.5 * D_PICO_UART
    z_b = z_pc + r + 0.00015
    cab = _cabeca_pico(topo, faces[0] - sg * (r + 0.0005), float(topo[0]), float(topo[2]) + 0.0022, z_b)
    rpi = cena.rpi
    if gps is not None and rpi is not None:
        # a ficha do cabo na boca da ficha GPS (face +x, entra 1,5 mm)
        x_f = float(gps.hi[0])
        c_f = np.array([x_f + 0.00125, float(gps.c[1]), float(gps.c[2])])
        meia = [0.00275, 0.5 * float(gps.hi[1] - gps.lo[1]) - 0.0004, 0.5 * float(gps.hi[2] - gps.lo[2]) - 0.0004]
        sai = np.array([x_f + 0.0040, float(gps.c[1]), float(gps.c[2])])
        # por cima das fichas do Pi: o topo delas, medido por raios, entre a borda da ponte e a da janela
        son = cena.sonda({"drone": np.zeros(3)}, (np.array([x_f, float(gps.c[1]) - 0.004, z_pc - 0.01]),
                                                  np.array([float(rpi.hi[0]) + 0.006, float(gps.c[1]) + 0.004,
                                                            float(gps.hi[2])])), excluir=_SO_FIOS)
        xs = np.arange(x_f + 0.006, float(rpi.hi[0]) + 0.0045, 0.001)
        tops = []
        for xx in xs:
            dd = [son.raio(np.array([xx, float(gps.c[1]) + oy, float(gps.lo[2]) - 0.0005]), [0.0, 0.0, -1.0], 0.02)
                  for oy in (-r, 0.0, r)]
            tops.append(max(float(gps.lo[2]) - 0.0005 - v for v in dd if v is not None) if any(v is not None for v in dd)
                        else z_pc)
        tops = np.array(tops)
        x_desce = float(xs[0])
        z_sobre = float(np.max(tops[xs >= x_desce])) + r + 0.0003
        x_fora = float(rpi.hi[0]) + 0.0045
        ini = np.array([x_fora + 0.004, float(gps.c[1]), z_b])
        lo = np.array([min(float(ini[0]), float(cab[-1][0])) - 0.03, min(float(ini[1]), float(cab[-1][1])) - 0.015, 0.0])
        hi = np.array([max(float(ini[0]), float(cab[-1][0])) + 0.04, max(float(ini[1]), float(cab[-1][1])) + 0.015, 0.0])
        mesa = _Mesa(cena, lo, hi, z_b, acima=0.006)
        mesa.proibir(rpi.lo - 0.004, rpi.hi + 0.004)
        _reservar(mesa, cena, n, exceto=f"el_pico{n}_uart")
        cam = mesa.rota(ini, cab[-1], r + 0.00005, folga=0.00015, soltar=0.003)
        if cam is None:
            warnings.warn(f"detalhes/fios: sem caminho livre da UART do Pico {n} à ficha GPS do FC", stacklevel=2)
        else:
            with m.peca("cabo_controlador", n):
                m.caixa("drone", "fios_jst", c_f, np.eye(3), meia)
                acesso = [sai, np.array([x_desce, float(gps.c[1]), float(gps.c[2])]),
                          np.array([x_desce + 0.002, float(gps.c[1]), z_sobre]),
                          np.array([x_fora - 0.002, float(gps.c[1]), z_sobre]),
                          np.array([x_fora + 0.001, float(gps.c[1]), z_sobre - 0.002]),
                          np.array([x_fora + 0.002, float(gps.c[1]), z_b + 0.001])]
                linha = _curva([*acesso, *cam, *cab[::-1][1:]], 0.003)
                m.tubo("drone", "fios_preto", linha, D_PICO_UART)
            cena.ligar(f"pico{n}_uart", f"el_pico{n}_uart", "el_fc_con_gps", "drone", anc, "drone",
                       np.array([x_f, float(gps.c[1]), float(gps.c[2])]), "4 × 28 AWG (GND, 5 V, TX, RX)",
                       "cabo_controlador", n, nota=f"UART do Pico {n} na ficha GPS do FC (uma UART livre)")
            return
    # a 2.ª UART do FC (`el_fc_con_uart2`, JST-SH na borda do FC do lado deste Pico)
    a2 = cena.ponto_ancora("el_fc_con_uart2")
    u2 = cena.caixa("el_fc_con_uart2") if a2 is not None else None
    if u2 is not None and a2[0] == "drone" and float(np.dot(_u(a2[2]), [0.0, sg, 0.0])) > 0.7 and \
            _pico_uart2(cena, n, cab, anc, z_b, r, u2, a2):
        return
    # sem ficha UART livre no FC: rabicho junto ao FC, deitado na placa de cima à beira da janela
    alvo = np.array([float(cena.fc.c[0]) - 0.008, float(cena.fc.c[1]) + sg * (float(cena.fc.h[1]) + 0.016), z_b])
    lo = np.array([min(float(alvo[0]), float(cab[-1][0])) - 0.02, min(float(alvo[1]), float(cab[-1][1])) - 0.012, 0.0])
    hi = np.array([max(float(alvo[0]), float(cab[-1][0])) + 0.02, max(float(alvo[1]), float(cab[-1][1])) + 0.012, 0.0])
    mesa = _Mesa(cena, lo, hi, z_b, acima=0.006)
    if rpi is not None:
        mesa.proibir(rpi.lo - 0.004, rpi.hi + 0.004)
    _reservar(mesa, cena, n, exceto=f"el_pico{n}_uart")
    cam = mesa.rota(cab[-1], alvo, r + 0.00005, folga=0.00015, soltar=0.002)
    if cam is None:
        return
    with m.peca("cabo_controlador", n):
        _rabicho(cena, f"pico{n}_uart_fc", [*cab, *cam[1:]], D_PICO_UART, 4, f"el_pico{n}_uart", 0,
                 f"UART do Pico {n} (GND, 5 V, TX, RX): o FC não tem outra UART publicada (a `el_fc_con_uart` é do "
                 "Raspberry Pi 5 e a ficha GPS é do outro Pico)")


def _pico_uart2(cena: _Cena, n: int, cab, anc, z_b: float, r: float, u2: _Caixa, a2) -> bool:
    """UART do Pico n na 2.ª UART do FC (`el_fc_con_uart2`: JST-SH de 4 vias, entrada lateral na borda do FC do lado
    do Pico, publicada pela eletrónica): a ficha do cabo (JST-SH, «estimado» 1,5 mm metida na boca) e o cabo a sair
    para fora do FC à altura dela; sobe o que for preciso para passar por cima do que tiver por baixo (peças e cabos já
    desenhados, medidos), segue até à primeira COLUNA LIVRE até à placa de cima (raios e cabos), desce por ela e vai
    pela placa (mapa 2,5D) até à ficha `el_pico{n}_uart`. Devolve se desenhou."""
    m, rpi = cena.m, cena.rpi
    q = np.asarray(a2[1], dtype=float)                      # centro da boca
    s = 1.0 if float(a2[2][1]) > 0.0 else -1.0
    cx, y_f, cz = float(q[0]), float(q[1]), float(q[2])
    hx, hz = 0.5 * float(u2.hi[0] - u2.lo[0]), 0.5 * float(u2.hi[2] - u2.lo[2])
    c_f = np.array([cx, y_f + s * 0.00125, cz])
    meia = [hx - 0.0004, 0.00275, hz - 0.00035]
    y0 = y_f + s * 0.0040                                   # a traseira da ficha: o cabo sai daqui
    y_max = y0 + s * 0.045
    zona = (np.array([cx - 0.010, min(y0, y_max) - 0.004, z_b - 0.004]),
            np.array([cx + 0.010, max(y0, y_max) + 0.004, cz + 0.012]))
    son = cena.sonda({"drone": np.zeros(3)}, zona, excluir=_SO_FIOS)
    amostras = []
    for c in m.cabos:
        if c["corpo"] != "drone":
            continue
        P = np.asarray(c["pts"], dtype=float)
        if not np.any(np.all((P >= zona[0] - 0.01) & (P <= zona[1] + 0.01), axis=1)):
            continue
        Q = np.asarray(_reamostrar([p for p in P], 0.0005))
        Q = Q[np.all((Q >= zona[0] - 0.003) & (Q <= zona[1] + 0.003), axis=1)]
        amostras += [(p, float(c["r"])) for p in Q]
    CP = np.array([p for p, _r in amostras]) if amostras else np.zeros((0, 3))
    CR = np.array([rr for _p, rr in amostras]) if amostras else np.zeros(0)

    def altura(y1: float) -> float:
        """z do troço horizontal de y0 a y1: acima do topo do que lá está por baixo (peças e cabos)."""
        ys = np.arange(min(y0, y1), max(y0, y1) + 0.0005, 0.0005)
        P = np.array([[cx + dx, yy, cz + 0.001] for yy in ys for dx in (-r, 0.0, r)])
        d = son.raios(P, np.repeat(-EZ[None], len(P), axis=0), 0.02)
        topo = float(np.max(cz + 0.001 - d[np.isfinite(d)])) if np.isfinite(d).any() else -math.inf
        if len(CP):
            sel = (np.abs(CP[:, 0] - cx) < r + CR + 0.0002) & (CP[:, 1] >= min(y0, y1) - r) & \
                  (CP[:, 1] <= max(y0, y1) + r) & (CP[:, 2] < cz + 0.003)
            if np.any(sel):
                topo = max(topo, float(np.max(CP[sel, 2] + CR[sel])))
        return max(cz, topo + r + 0.00025)

    escolha = None
    for y_c in np.arange(y0 + s * 0.006, y_max, s * 0.0005):
        z_e = altura(float(y_c) + s * r)
        # teto do troço horizontal (o cabo não pode subir para dentro do que está por cima)
        P = np.array([[cx, yy, z_e] for yy in np.arange(min(y0, y_c), max(y0, y_c), 0.001)])
        if len(P):
            d = son.raios(P, np.repeat(EZ[None], len(P), axis=0), 0.01)
            if np.isfinite(d).any() and float(np.min(d)) < r + 0.0002:
                break
        # a coluna até à placa: nada entre z_e e a placa (peças e cabos)
        P = np.array([[cx + dx, float(y_c) + dy, z_e] for dx in (-r, 0.0, r) for dy in (-r, 0.0, r)])
        d = son.raios(P, np.repeat(-EZ[None], len(P), axis=0), z_e - z_b + 0.004)
        if np.isfinite(d).any() and float(np.min(d)) < z_e - z_b + r - 0.0002:
            continue
        if len(CP):
            hd = np.hypot(CP[:, 0] - cx, CP[:, 1] - float(y_c))
            if np.any((hd < r + CR + 0.0003) & (CP[:, 2] > z_b - 0.003) & (CP[:, 2] < z_e + r + 0.0003)):
                continue
        ini = np.array([cx, float(y_c) + s * 0.004, z_b])
        if rpi is not None and np.all(ini[:2] >= rpi.lo[:2] - 0.004) and np.all(ini[:2] <= rpi.hi[:2] + 0.004):
            continue
        escolha = (float(y_c), z_e, ini)
        break
    if escolha is None:
        return False
    y_c, z_e, ini = escolha
    acesso = [np.array([cx, y0, cz]), np.array([cx, y0 + s * 0.0015, cz])]
    if z_e > cz + 0.0002:
        acesso.append(np.array([cx, y0 + s * 0.0040, z_e]))
    acesso += [np.array([cx, y_c - s * 0.0030, z_e]), np.array([cx, y_c, z_e - 0.0030]),
               np.array([cx, y_c, z_b + 0.0030]), np.array([cx, y_c + s * 0.0030, z_b])]
    lo = np.array([min(float(ini[0]), float(cab[-1][0])) - 0.02, min(float(ini[1]), float(cab[-1][1])) - 0.012, 0.0])
    hi = np.array([max(float(ini[0]), float(cab[-1][0])) + 0.02, max(float(ini[1]), float(cab[-1][1])) + 0.012, 0.0])
    mesa = _Mesa(cena, lo, hi, z_b, acima=0.006)
    if rpi is not None:
        mesa.proibir(rpi.lo - 0.004, rpi.hi + 0.004)
    _reservar(mesa, cena, n, exceto=f"el_pico{n}_uart")
    cam = mesa.rota(ini, cab[-1], r + 0.00005, folga=0.00015, soltar=0.003)
    if cam is None:
        warnings.warn(f"detalhes/fios: sem caminho livre da UART do Pico {n} à 2.ª UART do FC", stacklevel=2)
        return False
    with m.peca("cabo_controlador", n):
        m.caixa("drone", "fios_jst", c_f, np.eye(3), meia)
        m.tubo("drone", "fios_preto", _curva([*acesso, *cam, *cab[::-1][1:]], 0.003), D_PICO_UART)
    cena.ligar(f"pico{n}_uart", f"el_pico{n}_uart", "el_fc_con_uart2", "drone", anc, "drone",
               np.array([cx, y_f, cz]), "4 × 28 AWG (GND, 5 V, TX, RX)", "cabo_controlador", n,
               nota=f"UART do Pico {n} na 2.ª UART do FC (JST-SH de 4 vias)")
    return True


def _ombros_fuso(cena: _Cena) -> None:
    """Build ACESSÍVEL (ombro de fuso): o cabo do motorredutor de cada braço (troço animado + laço no pivô B; daí o par
    do motor ao DRV8871, por baixo da placa de baixo) e os rabichos dos sensores do ombro: os 4 do encoder (da separação,
    para dentro da placa de cima) e o SPI do AS5048A (da barra de pinos, por baixo da placa de baixo), cada um até uma
    ficha JST-GH solta — o FC não tem fichas publicadas para estes sinais."""
    if _tipo_servo(cena.hw, "ombro") != "motorredutor_dc" or cena.z_sup is None:
        return
    pl = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
    if pl is None:
        return
    z_m = cena.z_sup + 0.0012 + 0.5 * D_SENS4 + 0.0002
    for k in range(1, 5):
        sx, _sy = cena.sinais[k - 1]
        with cena.m.peca("cabo_motorredutor", k):
            r = _cabo_motorredutor(cena, k)
        if r is not None and _pico_lados(cena):
            cena.hall_ini[k] = r                       # o cabo do Hall vai à ficha do Pico (`_controladores_bracos`)
        elif r is not None:
            p_sep, d_in = r
            # os 4 do encoder: da separação (onde os 4 fios da fita entram na bainha), por dentro da borda da placa de
            # cima, deitados nela (rabicho de ~3 cm)
            ini = p_sep + np.array([0.0, 0.0, 0.0008])
            pts = [ini, np.array([float(ini[0]), float(ini[1]), z_m]),
                   np.array([float(p_sep[0]), float(p_sep[1]) + float(d_in[1]) * 0.012, z_m]),
                   np.array([float(p_sep[0]) - sx * 0.006, float(p_sep[1]) + float(d_in[1]) * 0.028, z_m])]
            with cena.m.peca("cabo_sensores_braco", k):
                _rabicho(cena, f"encoder_ombro{k}", pts, D_SENS4, 4, f"ombro{k}_pivo_b_cabos", k,
                         "encoder Hall do JGB37-520 (GND, VCC, A, B)")
        fb = cena.ponto_ancora(f"servo_ombro{k}_ficha_b")
        if fb is not None and fb[0] == "drone" and not _pico_lados(cena):
            q, dq = np.asarray(fb[1], dtype=float), _u(fb[2])
            # AS5048A (ponta de dentro do veio do ombro, por baixo da placa de baixo): ficha na barra de pinos e um
            # rabicho de ~3 cm para dentro, por baixo da placa
            nome = _geom_ficha_servo(cena, "drone", "ombro", k, q) or f"servo_ombro{k}_ficha_b"
            pts = [q + dq * 0.0016, q + dq * 0.008, q + dq * 0.020 + np.array([0.0, 0.0, 0.002]),
                   q + dq * 0.030 + np.array([0.0, 0.0, 0.002])]
            with cena.m.peca("cabo_sensores_braco", k):
                _rabicho(cena, f"as5048a_ombro{k}", pts, D_SENS5, 6, nome, k,
                         "AS5048A do ombro (SPI: VDD, GND, CSn, CLK, MISO, MOSI)")


# ====================================================================================== perfis 2D (fichas)
def _ret_arred(du: float, dv: float, r: float, n: int = 4) -> np.ndarray:
    """Retângulo du × dv (centrado) com os cantos de raio r, CCW — `n` pontos por canto."""
    r = min(r, 0.5 * du, 0.5 * dv)
    cu, cv = 0.5 * du - r, 0.5 * dv - r
    pts = []
    for k, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        a0 = 0.5 * math.pi * k
        for j in range(n + 1):
            a = a0 + 0.5 * math.pi * j / n
            pts.append((sx * cu + r * math.cos(a), sy * cv + r * math.sin(a)))
    return np.array(pts)


def _estadio(du: float, dv: float, n: int = 6) -> np.ndarray:
    """Estádio du × dv (pontas semicirculares no lado maior), CCW."""
    return _ret_arred(du, dv, 0.5 * min(du, dv) - 1e-7, n)


def _drapejar(cena: _Cena, pts, r: float, corpo: str = "drone", folga: float = 0.0003, acima: float = 0.0065,
              acima_cabos: float | None = None, ignorar=(), fixar_inicio: bool = False) -> list:
    """Um cabo de raio r pelos pontos (x, y, z mínimo) que ASSENTA no que houver por baixo (raios verticais de `acima`
    sobre o z mínimo: 3 por amostra, no eixo e nas bordas do cabo) — sobe às peças, nunca as atravessa; dos cabos já
    desenhados só conta os que passam a menos de `acima_cabos` (por omissão `acima`) sobre ele (os mais altos passam
    por cima dele) e não estão em `ignorar` (ids: p. ex. o troço de que este é a continuação). Com `fixar_inicio` o 1.º
    ponto fica onde está (a ponta do troço anterior)."""
    acima_cabos = acima if acima_cabos is None else acima_cabos
    p_ini = np.asarray(pts[0], dtype=float).copy()
    pts = _reamostrar([np.asarray(q, dtype=float) for q in pts], 0.0015)
    if len(pts) < 2:
        return pts
    P = np.asarray(pts)
    # (a zona desce até ao fundo do cabo: o que fica entre o fundo e o eixo também o levanta)
    lo, hi = P.min(axis=0) - np.array([r + 0.002, r + 0.002, r + 0.002]), P.max(axis=0) + np.array([r + 0.002, r + 0.002,
                                                                                                    acima + 0.002])
    sonda = cena.sonda({corpo: np.zeros(3)}, (lo, hi), excluir=_SO_FIOS)
    t, _n, _b = _quadros(P)
    lat = _cruz(t, EZ)
    lat = lat / np.maximum(np.linalg.norm(lat, axis=1, keepdims=True), 1e-9)
    # os cabos já desenhados neste corpo (o fio deita-se POR CIMA deles, encostado)
    segs = [(c["pts"][:-1], c["pts"][1:], c["r"]) for c in cena.m.cabos
            if c["corpo"] == corpo and len(c["pts"]) > 1 and c["id"] not in ignorar]
    if segs:
        SA = np.concatenate([a for a, _b2, _r in segs])
        SB = np.concatenate([b2 for _a, b2, _r in segs])
        SR = np.concatenate([np.full(len(a), r2) for a, _b2, r2 in segs])
        ok = (np.minimum(SA[:, 2], SB[:, 2]) <= hi[2] + 0.01) & (np.maximum(SA[:, 0], SB[:, 0]) >= lo[0] - 0.01) & \
             (np.minimum(SA[:, 0], SB[:, 0]) <= hi[0] + 0.01) & (np.maximum(SA[:, 1], SB[:, 1]) >= lo[1] - 0.01) & \
             (np.minimum(SA[:, 1], SB[:, 1]) <= hi[1] + 0.01)
        SA, SB, SR = SA[ok], SB[ok], SR[ok]
    zs = []
    offs = (-r, -0.5 * r, 0.0, 0.5 * r, r) if r > 0.002 else (-r, 0.0, r)      # cabos grossos: mais raios pela largura
    for i, q in enumerate(P):
        z_top = q[2] - r - folga
        for off in offs:
            o = q + off * lat[i] + np.array([0.0, 0.0, acima])
            d = sonda.raio(o, -EZ, acima + r + 0.004)
            if d is not None and d > 1e-5:              # o raio parte de fora das peças (d = 0: começou dentro)
                z_top = max(z_top, float(o[2] - d))
        z_c = z_top + r + folga
        if segs and len(SA):
            ab = SB[:, :2] - SA[:, :2]
            l2 = np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-14)
            tt = np.clip(np.einsum("ij,ij->i", q[:2] - SA[:, :2], ab) / l2, 0.0, 1.0)
            pc = SA + tt[:, None] * (SB - SA)
            dxy = np.linalg.norm(q[:2] - pc[:, :2], axis=1)
            alc = r + SR + folga
            m_ = (dxy < alc) & (pc[:, 2] < q[2] + acima_cabos)
            if np.any(m_):
                z_c = max(z_c, float(np.max(pc[m_, 2] + np.sqrt(alc[m_] ** 2 - dxy[m_] ** 2))))
        zs.append(z_c)
    zs = [max(zs[max(0, i - 2): i + 3]) for i in range(len(zs))]
    res = _simplificar([np.array([q[0], q[1], max(q[2], z)]) for q, z in zip(P, zs, strict=True)], 0.0002)
    if fixar_inicio and res:
        res[0] = p_ini
    return res


# ====================================================================================== centro
def _xt90_proprio(cena: _Cena):
    """Sem a eletrónica: o XT90 macho + os 2 copos de solda atrás do `conector_xt90` (a mesma disposição dela).
    Devolve [(ponto dentro do copo, direção de saída do fio, nome da âncora)]."""
    g = cena.ctx.geom_existente("conector_xt90")
    if g is None or cena.bat is None:
        return None
    pos = np.array(g.pos, dtype=float)
    x_f1 = pos[0] + 0.010
    c_m = np.array([x_f1 - 0.0295, pos[1], pos[2]])
    cena.m.caixa("drone", "fios_xt90", c_m, np.eye(3), [0.5 * v for v in XT90_MACHO])
    copos = []
    for dy in (0.00525, -0.00525):
        a, b = np.array([x_f1 - 0.044, pos[1] + dy, pos[2]]), np.array([x_f1 - 0.039, pos[1] + dy, pos[2]])
        cena.m.tubo("drone", "fios_ouro", [a, b], 0.0052, lados=12, cabo=False)
        copos.append((a + np.array([0.0015, 0.0, 0.0]), np.array([-1.0, 0.0, 0.0]), "conector_xt90"))
    return copos


def _levantar_onde_entra(cena: _Cena, linha, r: float, folga: float = 0.00015) -> list:
    """O cabo (raio r) SOBE onde entraria no que lhe fica por baixo (raios para baixo, na faixa de 6 mm abaixo do eixo
    — o que está por cima não conta): o que falta + folga, em rampa de ±8 mm. Onde não entra fica tal e qual (a mesma
    polilinha)."""
    P0 = [np.asarray(q, dtype=float) for q in linha]
    if len(P0) < 3:
        return P0
    P = np.asarray(_reamostrar(P0, 0.001))
    s_p = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    dentro = (s_p > 0.008) & (s_p < s_p[-1] - 0.008)           # (as pontas assentam nas âncoras: não contam)
    if not np.any(dentro):
        return P0
    z_lo, z_hi = float(P[:, 2].min()) - 0.006, float(P[:, 2].max()) + r
    lo, hi = np.r_[P[:, :2].min(axis=0) - 0.004, z_lo], np.r_[P[:, :2].max(axis=0) + 0.004, z_hi]
    son = cena.sonda({"drone": np.zeros(3)}, (lo, hi), excluir=_SO_FIOS)
    falta = np.zeros(len(P))
    entra = 0.0
    # (raios no eixo e a 0,6 r e 0,9 r dele, em 8 direções: a casca do tubo, por baixo, está a √(r² − ρ²) do eixo)
    offs = [(0.0, 0.0)] + [(rho * math.cos(a), rho * math.sin(a)) for rho in (0.25, 0.45, 0.6, 0.75, 0.9)
                           for a in np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False)]
    for dx, dy in offs:
        Q = P + np.array([dx * r, dy * r, 0.0])
        d = son.raios(Q, np.repeat(-EZ[None], len(Q), axis=0), r + 0.006)
        alt = r * math.sqrt(max(0.0, 1.0 - dx * dx - dy * dy))
        falta = np.maximum(falta, np.where(np.isfinite(d) & dentro, alt + folga - d, 0.0))
        entra = max(entra, float(np.max(np.where(np.isfinite(d) & dentro, alt - d, 0.0))))
    if entra <= 0.0001:                       # (só onde ENTRA mais de 0,1 mm: o resto fica tal e qual)
        return P0
    sobe = np.zeros(len(P))
    for i in np.flatnonzero(falta > 0.0):
        sobe = np.maximum(sobe, falta[i] * np.clip(1.0 - np.abs(s_p - s_p[i]) / 0.008, 0.0, 1.0))
    P[:, 2] += sobe
    return list(P)


def _bateria(cena: _Cena) -> None:
    """Copos do XT90 macho → (10 AWG) por trás e por cima da placa de cima → ilhas da bateria da placa de energia (o
    balanceador é da bateria: desenha-o a `eletronica`, com a ficha `el_bat_balanco`)."""
    ctx, m, bat = cena.ctx, cena.m, cena.bat
    if bat is None or cena.placa is None:
        return
    r = 0.5 * D_BAT
    copos = []
    macho = cena.caixa("el_xt90_macho")
    for polo in ("pos", "neg"):
        anc = cena.ponto_ancora(f"el_xt90_copo_{polo}")
        if anc is not None and anc[0] == "drone":
            # a eletrónica publica a ponta do copo e a direção por onde o fio sai (XT90 deitado ou de pé)
            _c, ponta, dout = anc
            copos.append((np.asarray(ponta, dtype=float) - 0.0015 * dout, dout, f"el_xt90_copo_{polo}"))
            continue
        g = ctx.geom_existente(f"el_xt90_copo_{polo}")
        if g is not None:
            _t, pos, rr, s = _pose(g)
            a, b = pos - rr[:, 2] * s[1], pos + rr[:, 2] * s[1]
            ref = macho.c if macho is not None else pos + np.array([1.0, 0.0, 0.0])
            aberto, outro = (a, b) if np.linalg.norm(a - ref) > np.linalg.norm(b - ref) else (b, a)
            dout = _u(aberto - outro)
            copos.append((aberto - 0.0015 * dout, dout, f"el_xt90_copo_{polo}"))
    with m.peca("cabo_bateria"):
        if len(copos) != 2:
            copos = _xt90_proprio(cena)
        if copos is None:
            return
        cena.copos_xt90 = copos
        x_borda = float(cena.placa.lo[0])
        z_cima = (cena.z_sup + 0.0012 if cena.z_sup is not None else cena.z_topo + 0.016) + r + 0.0012
        comp = cena.computador
        faixa_ubec = _faixa_ao_lado_ubec(cena, r) if cena.servo_pwm else None
        if faixa_ubec is not None:
            z_cima = faixa_ubec[1]
        for polo, mat, (c, dout, nome_copo) in (("pos", "fios_vermelho", copos[0]), ("neg", "fios_preto", copos[1])):
            pad = cena.pdb_pad(f"el_pdb_bat_{polo}")
            nome_pad = cena.nome_ancora(f"el_pdb_bat_{polo}", "el_cablagem")
            # sobe por trás da placa de baixo; com a ficha já atrás dela (packs compridos), logo atrás da ficha — e
            # nunca através do que lá está (a barra da treliça de estabilização, medida com raios)
            x_r = min(float(c[0]) - 0.012, x_borda - 0.012)
            if float(c[0]) - 0.006 < x_borda - 0.006:
                x_r = float(c[0]) - 0.012
                for xr in np.arange(float(c[0]) - 0.012, float(c[0]) - 0.0035, 0.0005):
                    zs_r = np.linspace(float(c[2]), z_cima, 12)
                    P = np.array([[xr - r - 0.0004, float(c[1]), z] for z in zs_r])
                    if not np.any(np.isfinite(cena.sonda({"drone": np.zeros(3)},
                                                          (P.min(axis=0) - 0.01, P.max(axis=0) + 0.01),
                                                          excluir=_SO_FIOS).raios(
                            P, np.repeat([[1.0, 0.0, 0.0]], len(P), axis=0), 2.0 * r + 0.0008))):
                        x_r = float(xr)
                        break
            if float(dout[2]) > 0.7:
                # XT90 de pé (copos para cima): sobe a direito 9,5 mm, curva para a frente e segue à altura maior (a do
                # topo dos copos ou a da placa de cima) até passar a ficha — só depois desce ao caminho de sempre
                z_h = max(z_cima + 0.002, float(c[2]) + 0.0095 + 0.002)
                pts = [c, c + 0.0095 * dout, np.array([float(c[0]) + 0.006, c[1], z_h]),
                       np.array([max(float(c[0]) + 0.016, min(x_borda - 0.006, float(c[0]) + 0.030)), c[1], z_h])]
            else:
                pts = [c, c + 0.0095 * dout,
                       np.array([x_r, c[1], 0.5 * (c[2] + z_cima)]),
                       np.array([min(x_borda - 0.006, x_r + 0.006), c[1], z_cima + 0.002])]
            if pad is not None and faixa_ubec is not None:
                # build acessível: ao lado do UBEC (por fora do berço, por baixo do carregador) e, à frente dele, sobe
                # em diagonal para a ilha — por cima do servo-rail e da ponte do FC
                y_l, z_l, x_a, x_b = faixa_ubec
                sgn_p = 1.0 if float(pad.c[1]) >= 0.0 else -1.0
                y_i = (float(pad.lo[1]) + r + 0.0002) if sgn_p > 0 else (float(pad.hi[1]) - r - 0.0002)
                alvo = np.array([float(pad.lo[0]) + r + 0.0002, y_i, float(pad.hi[2]) + r - 0.0003])
                pts[-1] = np.array([float(pts[-1][0]), c[1], z_l])
                # à frente do UBEC sobe logo (ainda por fora, por baixo do carregador: `_sob_tetos`) e só vira para a
                # ilha já por cima do servo-rail — os cabos dos servos saem do rail por baixo dela
                z_s = float(alvo[2]) - 0.005
                pts += [np.array([x_a - 0.010, float(c[1]) + 0.4 * (sgn_p * y_l - float(c[1])), z_l]),
                        np.array([x_a, sgn_p * y_l, z_l]), np.array([x_b, sgn_p * y_l, z_l]),
                        np.array([x_b + 0.003, sgn_p * y_l, 0.5 * (z_l + z_s)]),
                        np.array([x_b + 0.006, sgn_p * y_l, z_s]),
                        np.array([float(alvo[0]) - 0.012, sgn_p * (y_l - 0.002), z_s + 0.002]),
                        alvo - np.array([0.005, 0.0, -0.001]), alvo]
            elif pad is not None and _pilha_por_rasgos(cena):
                # placa de energia POR CIMA da placa de cima (Arduino): o par desce à placa de cima logo depois da
                # borda dela e vai DEITADO nela (mapa 2,5D: contorna a base do carregador da arma, que desce a 5 mm da
                # placa — não cabe por baixo) até à frente da ilha, onde sobe e assenta nela
                sgn_p = 1.0 if float(pad.c[1]) >= 0.0 else -1.0
                y_i = (float(pad.lo[1]) + r + 0.0002) if sgn_p > 0 else (float(pad.hi[1]) - r - 0.0002)
                alvo = np.array([float(pad.lo[0]) + r + 0.0002, y_i, float(pad.hi[2]) + r - 0.0003])
                pt = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
                z_t = float(pt.hi[2]) + r + 0.00015
                x_e = float(pt.lo[0])
                # as peças da arma que descem até ao cabo deitado (caixas): passa-lhes AO LADO, já antes da borda
                y_l = float(c[1])
                for lo_a, hi_a in _tetos_arma(cena):
                    if float(lo_a[2]) < z_t + r + 0.0003 and float(hi_a[0]) > x_e and float(lo_a[0]) < float(alvo[0]):
                        y_l = sgn_p * max(abs(y_l), max(abs(float(lo_a[1])), abs(float(hi_a[1]))) + r + 0.0006)
                ini = np.array([x_e + 0.006, y_l, z_t])
                fim = np.array([float(alvo[0]) - 0.010, y_i, z_t])
                lo = np.minimum(ini, fim) - np.array([0.01, 0.012, 0.0])
                hi = np.maximum(ini, fim) + np.array([0.01, 0.012, 0.0])
                mesa = _Mesa(cena, lo, hi, z_t, acima=0.006, r_max=r)
                if cena.pdb_massa is not None:
                    mesa.proibir(cena.pdb_massa.lo - 0.0005, cena.pdb_massa.hi + 0.0005)
                cam = mesa.rota(ini, fim, r + 0.00005, folga=0.00015, soltar=0.002)
                if cam is not None:
                    pts += [np.array([x_e - 0.010, y_l, float(pts[-1][2])]), np.array([x_e - 0.003, y_l, z_t + 0.0015]),
                            *cam, np.array([float(alvo[0]) - 0.0055, y_i, float(alvo[2]) + 0.0005]), alvo]
                    linha = [*_curva(pts[:-len(cam) - 2], 0.010), *_curva([*cam, *pts[-2:]], 0.004)[1:]]
                    m.tubo("drone", mat, linha, D_BAT)
                    mesa_ok = True
                else:
                    mesa_ok = False
                if mesa_ok:
                    cena.ligar(f"bateria_{polo}", nome_copo, nome_pad, "drone", c, "drone", _toque_ilha(pad, alvo),
                               "10 AWG", "cabo_bateria")
                    continue
                x_p = float(cena.computador.lo[0]) if cena.computador is not None else float(alvo[0]) - 0.015
                z_ponte = max(z_cima, float(alvo[2]) - 0.009) + 0.002
                pts += [np.array([x_p - 0.016, y_i, z_cima + 0.002]), np.array([x_p - 0.004, y_i, z_ponte + 0.003]),
                        alvo - np.array([0.005, 0.0, -0.001]), alvo]
            elif pad is not None:
                # na ilha, do lado de DENTRO (o 18 AWG da fonte dos servos solda-se na mesma ilha, do lado de fora)
                sgn_p = 1.0 if float(pad.c[1]) >= 0.0 else -1.0
                y_i = (float(pad.lo[1]) + r + 0.0002) if sgn_p > 0 else (float(pad.hi[1]) - r - 0.0002)
                alvo = np.array([float(pad.lo[0]) + r + 0.0002, y_i, float(pad.hi[2]) + r - 0.0003])
                x_p = float(comp.lo[0]) if comp is not None else float(alvo[0]) - 0.015
                z_ponte = max(z_cima, float(alvo[2]) - 0.009) + 0.002
                pts += [np.array([x_p - 0.016, y_i, z_cima + 0.002]), np.array([x_p - 0.004, y_i, z_ponte + 0.003]),
                        alvo - np.array([0.005, 0.0, -0.001]), alvo]
            else:
                pts += [np.array([x_borda + 0.03, c[1], z_cima])]
            linha = _curva(pts, 0.010)
            if pad is not None:              # por baixo da base do carregador da arma (que passa por cima das ilhas)
                linha = [*_sob_tetos(cena, linha[:-1], r, z_cima), linha[-1]]
                linha = _levantar_onde_entra(cena, linha, r)
            m.tubo("drone", mat, linha, D_BAT)
            if pad is not None:
                cena.ligar(f"bateria_{polo}", nome_copo, nome_pad, "drone", c, "drone", _toque_ilha(pad, pts[-1]),
                           "10 AWG", "cabo_bateria")


def _faixa_ao_lado_ubec(cena: _Cena, r: float):
    """Build acessível: a faixa de um cabo de raio r AO LADO do UBEC (no berço da placa de cima, atrás da pilha):
    (|y| do eixo, z do eixo, x onde começa, x onde acaba) — z à altura dos bornes (por cima das cabeças dos parafusos do
    berço e das paredes dele, por baixo do carregador), |y| = o lado do UBEC medido com raios + r + 1,2 mm; None sem os
    bornes do UBEC."""
    cx_e, cx_s = cena.caixa("el_ubec_entrada"), cena.caixa("el_ubec_saida")
    if cx_e is None or cx_s is None:
        return None
    x0, x1 = sorted((float(cx_e.c[0]), float(cx_s.c[0])))
    z_l = float(cx_s.c[2]) + 0.0012
    zona = (np.array([x0 - 0.004, -0.045, z_l - r - 0.002]), np.array([x1 + 0.004, 0.045, z_l + r + 0.002]))
    sonda = cena.sonda({"drone": np.zeros(3)}, zona, excluir=_SO_FIOS_ARMA)
    P, V = [], []
    for x in np.linspace(x0 + 0.004, x1 - 0.004, 7):
        for dz in (-r, 0.0, r):
            for sg in (1.0, -1.0):
                P.append([x, sg * 0.040, z_l + dz])
                V.append([0.0, -sg, 0.0])
    d = sonda.raios(np.array(P), np.array(V), 0.040)
    lado = float(np.max(0.040 - d[np.isfinite(d)])) if np.any(np.isfinite(d)) else float(cx_s.h[1])
    return lado + r + 0.0012, z_l, x0 - 0.002, x1 + 0.0005


def _copos_xt90(cena: _Cena):
    """[(ponto dentro do copo +, direção de saída, nome), (… −)] — os que a bateria usou (`_bateria` corre antes)."""
    return getattr(cena, "copos_xt90", None)


def _tetos_arma(cena: _Cena) -> list:
    """As caixas (AABB) dos geoms visíveis `arma*` do drone (base do carregador, punho, suporte) — em cache na cena."""
    if getattr(cena, "_tetos", None) is None:
        cena._tetos = []
        for g in cena.ctx.spec.geoms:
            nm = g.name or ""
            if nm.startswith("arma") and g.parent is not None and g.parent.name == "drone" and _visivel(g):
                bb = _aabb(g)
                if bb is not None:
                    cena._tetos.append((np.asarray(bb[0], dtype=float), np.asarray(bb[1], dtype=float)))
    return cena._tetos


def _sob_tetos(cena: _Cena, pts, r: float, z_de: float) -> list:
    """Os pontos de um cabo de raio r baixados para passar POR BAIXO das peças da arma que lhe ficam por cima (base do
    carregador, punho, suporte): as caixas dos geoms visíveis `arma*` do drone com o fundo acima de `z_de`; o
    rebaixamento entra e sai em rampa (±8 mm)."""
    _tetos_arma(cena)
    P = np.asarray(_reamostrar([np.asarray(q, dtype=float) for q in pts], 0.0015))
    if not cena._tetos or len(P) < 2:
        return [np.asarray(q, dtype=float) for q in pts]
    zm = np.full(len(P), np.inf)
    for lo, hi in cena._tetos:
        if lo[2] <= z_de:
            continue
        dentro = ((P[:, 0] >= lo[0] - r - 0.0008) & (P[:, 0] <= hi[0] + r + 0.0008) & (P[:, 1] >= lo[1] - r - 0.0008)
                  & (P[:, 1] <= hi[1] + r + 0.0008))
        zm = np.where(dentro, np.minimum(zm, lo[2] - r - 0.0004), zm)
    if not np.any(P[:, 2] > zm):
        return [np.asarray(q, dtype=float) for q in pts]
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    z = P[:, 2].copy()
    for i in np.flatnonzero(P[:, 2] > zm):                   # rampa de ±8 mm à volta de cada ponto rebaixado
        w = np.clip(1.0 - np.abs(s - s[i]) / 0.008, 0.0, 1.0)
        z = np.minimum(z, zm[i] + (1.0 - w) * 1.0)
    out = P.copy()
    out[:, 2] = np.minimum(P[:, 2], z)
    return _simplificar(list(out), 0.0002)


def _cadeia_energia(cena: _Cena) -> None:
    """Os troços da cadeia de energia que são das peças da eletrónica (o pack, o encaixe do XT90, os copos do macho, as
    pistas da placa de energia até à saída 5 V do BEC) — declarados se ninguém os declarou, e só onde as peças se tocam."""
    ctx = cena.ctx

    def ja(a, b):
        return any({x["de"], x["para"]} == {a, b} for x in ctx.registo.ligacoes)

    def contacto(na, nb):
        ca, cb = cena.caixa(na), cena.caixa(nb)
        if ca is None or cb is None or ca.corpo != cb.corpo:
            return None
        p = np.minimum(np.maximum(cb.c, ca.lo), ca.hi)          # ponto de A mais perto do centro de B …
        q = np.minimum(np.maximum(p, cb.lo), cb.hi)             # … e o de B mais perto dele
        if float(np.linalg.norm(p - q)) > 0.0005:
            return None
        return ca.corpo, 0.5 * (p + q)

    def interno(ident, na, nb, tipo, peca, nota):
        if ja(na, nb):
            return
        c = contacto(na, nb)
        if c is None:
            return
        corpo, p = c
        cena.ligar(ident, na, nb, corpo, p, corpo, p, "", peca, tipo=tipo, nota=nota)

    pack = "bateria"
    interno("bateria_pack_xt90", pack, "conector_xt90", "interno", "bateria", "cabos do pack ao XT90 fêmea")
    interno("bateria_xt90_encaixe", "conector_xt90", "el_xt90_macho", "encaixe", "bateria", "XT90 fêmea ↔ macho")
    for polo in ("pos", "neg"):
        interno(f"bateria_xt90_copo_{polo}", "el_xt90_macho", f"el_xt90_copo_{polo}", "interno", "bateria",
                "contacto do macho ao copo de solda")
    # pistas da placa de energia: ilhas da bateria → (shunt + BEC 5 V/5 A) → saída de 5 V
    for polo in ("pos", "neg"):
        a, b = f"el_pdb_bat_{polo}", f"el_pm_5v_{polo}"
        if ctx.geom_existente(b) is None:
            b = "el_pm_saida_5v"
        ca, cb = cena.caixa(a), cena.caixa(b)
        if ca is None or cb is None or ja(a, b):
            continue
        cena.ligar(f"pdb_bec_5v_{polo}", a, b, ca.corpo, ca.topo(), cb.corpo, cb.topo(), "", "pdb", tipo="pista",
                   nota="pistas da placa de energia pelo BEC 5 V/5 A")


def _alvos_5v(cena: _Cena):
    """[(polo, caixa, nome da âncora, tipo)]: as ilhas da saída 5 V do BEC (`el_pm_5v_pos/neg`, «ilha»), ou a ficha
    `el_pm_saida_5v` («ficha»), ou a mesma ficha na caixa `el_cablagem` (reserva com a disposição da eletrónica)."""
    out = []
    for polo in ("pos", "neg"):
        cx = cena.pdb_pad(f"el_pm_5v_{polo}")
        nome = cena.nome_ancora(f"el_pm_5v_{polo}", "el_cablagem")
        if cx is not None and nome is not None:
            out.append((polo, cx, nome, "ilha"))
    if len(out) == 2:
        return out
    fx = cena.pdb_pad("el_pm_saida_5v")
    nome = cena.nome_ancora("el_pm_saida_5v", "el_cablagem")
    if fx is None or nome is None:
        return []
    return [("pos", fx, nome, "ficha"), ("neg", fx, nome, "ficha")]


def _portenta_alimentacao(cena: _Cena) -> None:
    """Portenta H7 (build Arduino) ligado ao BEC 5 V da placa de energia: par 20 AWG das ilhas `el_pm_5v_pos/neg` pela
    placa de cima, desce pelo rasgo −y e segue entre as placas até à ficha JST-GH `el_portenta_5v` da placa de suporte."""
    anc_5v = cena.ponto_ancora("el_portenta_5v")
    alvos = _alvos_5v(cena)
    pt = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
    rasgos = _rasgos_sup(cena)
    if anc_5v is None or not alvos or pt is None or cena.placa is None or cena.pdb_massa is None:
        return
    cand = [(lo, hi) for lo, hi in rasgos if 0.5 * float(lo[1] + hi[1]) < float(pt.c[1]) - 0.020]
    if not cand:
        return
    lo_r, hi_r = min(cand, key=lambda c: abs(0.5 * float(c[0][0] + c[1][0])))
    y_r = 0.5 * float(lo_r[1] + hi_r[1])
    r_5v = 0.5 * D_20
    z_b = float(cena.placa.hi[2]) + r_5v + 0.0002
    z_t = float(pt.hi[2]) + r_5v + 0.0002
    p_5v = np.asarray(anc_5v[1], dtype=float)
    y_borda = float(cena.pdb_massa.lo[1])
    m = cena.m
    with m.peca("cabo_rpi5_5v"):
        m.caixa("drone", "fios_jst", p_5v + np.array([0.0, -0.0015, 0.0]), np.eye(3), [0.0021, 0.0015, 0.0016])
        for polo, cx, nome, _tipo in alvos:
            mat = "fios_vermelho" if polo == "pos" else "fios_preto"
            dx_f = -0.000625 if polo == "pos" else 0.000625
            x_f = float(p_5v[0]) + dx_f
            x_i = float(cx.c[0])
            fim_ilha = np.array([x_i, float(cx.c[1]), float(cx.hi[2]) + r_5v - 0.0002])
            z_v = float(fim_ilha[2]) + 0.0005
            pts = [np.array([x_f, float(p_5v[1]) - 0.0008, float(p_5v[2])]),
                   np.array([x_f, float(p_5v[1]) - 0.0050, float(p_5v[2])]),
                   np.array([x_i, float(p_5v[1]) - 0.0090, z_b]),
                   np.array([x_i, y_r, z_b]),
                   np.array([x_i, y_r, z_t]),
                   np.array([x_i, y_borda - 0.0025, z_t]),
                   np.array([x_i, y_borda - 0.0010, z_v]),
                   np.array([x_i, float(cx.lo[1]), z_v]),
                   fim_ilha]
            m.tubo("drone", mat, _curva(pts, 0.003), D_20, ident=f"portenta_5v_{polo}")
            m.tubo("drone", "fios_estanho", [fim_ilha - np.array([0.0, 0.0012, 0.0]),
                                             fim_ilha + np.array([0.0, 0.0012, 0.0])], D_SOLDA, lados=10, cabo=False)
            cena.ligar(f"portenta_5v_{polo}", nome, "el_portenta_5v", "drone", _toque_ilha(cx, fim_ilha), "drone", p_5v,
                       "20 AWG", "cabo_rpi5_5v", polo=polo)


def _rpi5_alimentacao(cena: _Cena) -> None:
    """Raspberry Pi 5 ligado ao BEC 5 V da placa de energia: ficha USB-C a 90° (saída para a frente) no `rpi5_usbc`, par
    20 AWG por baixo da placa de cima e para cima pela folga da janela (entre o micro-HDMI e o FPC da câmara), preso
    com uma abraçadeira ao par de sinal de um ESC ao lado do FC (lado −y), e cada fio soldado à sua ilha
    (`el_pm_5v_pos/neg`) — ver o docstring do módulo."""
    m, rpi = cena.m, cena.rpi
    if rpi is None:
        if cena.portenta is not None:
            _portenta_alimentacao(cena)
        return
    usbc = cena.rpi_peca("rpi5_usbc")
    alvos = _alvos_5v(cena)
    if usbc is None or not alvos:
        return
    nome_usbc = cena.nome_ancora("rpi5_usbc", "el_rpi5")
    if float(usbc.lo[1]) > float(rpi.lo[1]) + 0.0005:      # o recetáculo tem de abrir na borda −y (desenho do Pi 5)
        return
    wv, av, hv = np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), EZ
    O = np.array([float(usbc.c[0]), float(usbc.lo[1]), float(usbc.c[2])])

    def P(w, a, h=0.0):
        return O + w * wv + a * av + h * hv

    L = USBC_CORPO[2]
    a_m = -USBC_VISTA - 0.5 * L
    w_m = 0.5 * USBC_CORPO[0]
    sep = D_20 + 0.00002                              # os 2 fios encostados um ao outro
    z_pl0 = (cena.z_sup - 0.0012) if cena.z_sup is not None else float(rpi.lo[2]) + 0.0068
    z_pl1 = z_pl0 + 0.0024
    # o corpo sobremoldado na folga MEDIDA à volta da ficha (no 5″ o Pi fica na janela da placa de cima)
    h_lo, h_hi, w_lo, h_mg = _folga_usbc(cena, O, wv, av, hv, L, w_m)
    t_c, w_c, h_c = h_hi - h_lo, 0.5 * (w_m - w_lo), 0.5 * (h_lo + h_hi)
    corpo_l = _usbc_corpo_l(cena, O, wv, av, hv, L, w_lo, w_m, h_lo, h_hi)
    with m.peca("cabo_rpi5_5v"):
        # --- a ficha: casca metida no recetáculo, corpo sobremoldado e manga de alívio lateral (+x)
        est = _estadio(*USBC_CASCA, 6)
        m.prisma("drone", "fios_aco", [est, est], [P(0, -USBC_VISTA - 0.0002), P(0, USBC_METIDA)], wv, hv)
        if corpo_l is None:
            ret = _ret_arred(w_m + w_lo, t_c, 0.0016, 4)
            ret2 = _ret_arred(w_m + w_lo - 0.0008, t_c - 0.0008, 0.0012, 4)
            m.prisma("drone", "fios_sobremolde", [ret2, ret, ret, ret2],
                     [P(w_c, -USBC_VISTA, h_c), P(w_c, -USBC_VISTA - 0.0005, h_c),
                      P(w_c, -USBC_VISTA - L + 0.0005, h_c), P(w_c, -USBC_VISTA - L, h_c)], wv, hv)
        else:
            # ficha em ÂNGULO RETO com o corpo virado para o lado livre (+x): à frente da boca só um colar fino à
            # volta da casca (o que cabe antes do que lá está — no 5″ a cabeça de um M3), e o corpo fundo só do
            # lado de +x, de onde sai o cabo (L de lado; «estimado» — há fichas USB-C a 90° assim)
            d_n, w_s = corpo_l
            ret = _ret_arred(w_m + w_lo, t_c, 0.0012, 4)
            m.prisma("drone", "fios_sobremolde", [ret, ret], [P(w_c, -USBC_VISTA, h_c),
                                                               P(w_c, -USBC_VISTA - d_n, h_c)], wv, hv)
            if w_m - w_s >= 0.003:
                ret_b = _ret_arred(w_m - w_s, t_c, 0.0016, 4)
                ret_b2 = _ret_arred(w_m - w_s - 0.0008, t_c - 0.0008, 0.0012, 4)
                wb = 0.5 * (w_m + w_s)
                m.prisma("drone", "fios_sobremolde", [ret_b, ret_b, ret_b2],
                         [P(wb, -USBC_VISTA - d_n + 0.0002, h_c), P(wb, -USBC_VISTA - L + 0.0005, h_c),
                          P(wb, -USBC_VISTA - L, h_c)], wv, hv)
        b0, b1 = _estadio(0.0028, h_mg, 5), _estadio(0.0023, h_mg - 0.0006, 5)
        m.prisma("drone", "fios_sobremolde", [b0, b1], [P(w_m - 0.0002, a_m, h_c), P(w_m + USBC_MANGA, a_m, h_c)],
                 av, hv)
        # --- o par: sai da manga para +x (um fio por cima do outro), corre por baixo da placa de cima, vira para +y e
        #     sobe pela folga da janela, junta-se ao sinal de um ESC (abraçadeira), sai para fora da placa de energia
        z0 = float(O[2])
        ini = P(w_m + USBC_MANGA - 0.0030, a_m, h_c)
        x_col, y_col = _coluna_5v(cena, rpi, float(usbc.hi[0]) + w_m + USBC_MANGA, sep)
        z_alto = _altura_topo_5v(cena, alvos)
        pts = [ini, P(w_m + USBC_MANGA + 0.0010, a_m, h_c), np.array([x_col - 0.006, float(O[1]) + a_m, z0]),
               np.array([x_col, float(O[1]) + a_m + 0.0025, z0]), np.array([x_col, y_col - 0.0012, z0 + 0.0020]),
               np.array([x_col, y_col, z0 + 0.0045]),
               # (no 5″ o Pi está na janela da placa de cima: o topo da folga fica ABAIXO da ficha — a coluna sobe sempre)
               np.array([x_col, y_col, z_pl1 + 0.0040 if z_pl1 + 0.0040 >= z0 + 0.0045 else z0 + 0.0065])]
        feixe = _feixe_5v(cena, alvos, x_col, sep)
        abrac = None
        base = list(pts)
        if feixe is not None:
            # junta-se por fora (−y) ao par de sinal que corre ao lado do FC, segue com ele até passar as ilhas e uma
            # abraçadeira prende os dois; depois sobe por fora da placa de energia e entra por cima até às ilhas
            y_s, z5, xa, xb, x_t, ids_s = feixe
            sg = math.copysign(1.0, xb - xa)

            # a subida final é monótona (sem gancho): acaba à altura das ilhas ou, se o troço ao lado do sinal já lá
            # estiver perto, 2 mm acima dele
            z_f5 = max(z_alto - 0.0012, z5 + 0.0020)

            def rota(y5):
                return _curva([*base, np.array([x_col, y_col, z5 - 0.0060]), np.array([x_col, y5, z5 - 0.0012]),
                               np.array([xa, y5, z5]), np.array([xb, y5, z5]),
                               np.array([xb + sg * 0.0030, y5 - 0.0004, z5 + min(0.0030, 0.55 * (z_f5 - z5))]),
                               np.array([xb + sg * 0.0030, y5 - 0.0004, z_f5])], 0.0028, n=5)
            # o par roda pelo caminho (normal transportada): no troço junto ao sinal, o fio mais perto encosta a ele
            # o par vai rodando sobre si desde o topo da coluna até ficar de pé (um fio por cima do outro) ao lado do
            # sinal — na abraçadeira os 4 fios ficam num feixe compacto, encostados (como a abraçadeira os aperta)
            y5 = y_s - (D_SINAL + 0.5 * D_20 + 0.00025)          # (o par entrançado ondula ±0,1 mm)
            centro = rota(y5)
            x_t = _fase_sinal(cena, ids_s, xa, xb, x_t)        # onde o par de sinal está de pé (lá fica a abraçadeira)
            sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.asarray(centro), axis=0), axis=1))])
            t_, nn, bb = _quadros(centro, n0=EZ)
            i_t = int(np.argmin([abs(float(q[0]) - x_t) + 10.0 * abs(float(q[2]) - z5) for q in centro]))
            i_0 = int(np.argmin([abs(float(q[2]) - (z_pl1 + 0.004)) + 10.0 * abs(float(q[0]) - x_col) for q in centro]))
            alvo_n = EZ - float(EZ @ t_[i_t]) * t_[i_t]
            phi = math.atan2(float(alvo_n @ bb[i_t]), float(alvo_n @ nn[i_t]))
            s0, st = float(sl[i_0]), float(sl[i_t])
            s1 = max(st, s0 + 1e-6)
            phi0, sa, sb = _torcao_coluna(centro, sl, nn, bb, x_col, y_col, z0)

            def torcao(x, _p=phi, _a=s0, _b=s1, _p0=phi0, _a0=sa, _b0=sb):
                return (_p0 * min(max((x - _a0) / (_b0 - _a0), 0.0), 1.0)
                        + (_p - _p0) * min(max((x - _a) / (_b - _a), 0.0), 1.0))
            abrac = (x_t, y5, z5, ids_s)
        else:
            centro = _curva([*pts, np.array([x_col, y_col, z_alto - 0.0012])], 0.0028, n=5)
            sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(np.asarray(centro), axis=0), axis=1))])
            _t, nn, bb = _quadros(centro, n0=EZ)
            phi0, sa, sb = _torcao_coluna(centro, sl, nn, bb, x_col, y_col, z0)

            def torcao(x, _p0=phi0, _a0=sa, _b0=sb):
                return _p0 * min(max((x - _a0) / (_b0 - _a0), 0.0), 1.0)
        mats = ("fios_vermelho", "fios_preto")
        if alvos[0][3] == "ilha":
            _tq, nq, bq = _quadros(centro, n0=EZ)
            ang = torcao(float(np.sum(np.linalg.norm(np.diff(np.asarray(centro), axis=0), axis=1)))) if torcao else 0.0
            n_fim = math.cos(ang) * nq[-1] + math.sin(ang) * bq[-1]
            q0, q1 = centro[-1] - 0.5 * sep * n_fim, centro[-1] + 0.5 * sep * n_fim
            c_pos = alvos[0][1].c
            if np.linalg.norm(q0[:2] - c_pos[:2]) > np.linalg.norm(q1[:2] - c_pos[:2]):
                mats = ("fios_preto", "fios_vermelho")
                alvos = [alvos[1], alvos[0]]
        fios = m.paralelos("drone", mats, centro, D_20, n0=EZ, sep=sep, ident="rpi5_5v", torcao=torcao)
        # --- ponta de cima: cada fio à sua ilha (ou à ficha da saída 5 V)
        _pontas_5v(cena, fios, alvos, z_alto, nome_usbc, sep)
        if abrac is not None:
            x_t, y5, z5, ids_s = abrac
            ids = {c["id"] for c in m.cabos if re.fullmatch(r"rpi5_5v_\d+", c["id"])} | ids_s     # o par (não as pontas)
            _abracadeira(cena, "drone", np.array([x_t, y5 + 0.0012, z5]), [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], 0.008,
                         (-1.0, 0.0), incluir=_NADA, rotulo="5 V do Pi + sinal do ESC (lado −y do FC)",
                         membros="par 20 AWG do 5 V + par de sinal do ESC", cabos_raio=0.0013, cabos_ids=ids)


def _usbc_corpo_l(cena: _Cena, O, wv, av, hv, L: float, w_lo: float, w_m: float, h_lo: float, h_hi: float):
    """Profundidade LIVRE à frente da boca do USB-C (raios ao longo do eixo de encaixe, para fora, a partir da face do
    corpo, numa grelha da secção dele): None se o corpo de catálogo (L) cabe; senão (profundidade do colar à volta da
    casca, w a partir do qual o corpo pode ter L) — a ficha em ângulo reto virada para o lado livre (+w, o da manga)."""
    cantos = [O + w * wv + a * av + h * hv for w in (-w_lo - 0.002, w_m + 0.002) for a in (-USBC_VISTA, -USBC_VISTA - L - 0.003)
              for h in (h_lo - 0.001, h_hi + 0.001)]
    son = cena.sonda({"drone": np.zeros(3)}, (np.min(cantos, axis=0), np.max(cantos, axis=0)), excluir=_SO_FIOS)
    ws = np.linspace(-w_lo + 0.0002, w_m - 0.0002, 25)
    hs = np.linspace(h_lo + 0.0002, h_hi - 0.0002, 7)
    Pr = np.array([O + w * wv - USBC_VISTA * av + h * hv for w in ws for h in hs])
    d = son.raios(Pr, np.repeat(-av[None], len(Pr), axis=0), L + 0.002).reshape(len(ws), len(hs)).min(axis=1)
    if np.all(d >= L + 0.00015):
        return None
    d_n = max(0.0015, min(L, float(np.min(d)) - 0.0003))
    livres = d >= L + 0.00015
    if not livres[-1]:
        return d_n, w_m
    i = len(ws) - 1
    while i > 0 and livres[i - 1]:
        i -= 1
    return d_n, float(ws[i]) + 0.0003


def _folga_usbc(cena: _Cena, O, wv, av, hv, L: float, w_m: float) -> tuple[float, float, float, float]:
    """(h de baixo, h de cima, meia largura do lado −w, altura da manga) do corpo da ficha USB-C a 90°, MEDIDOS com raios
    para baixo, para cima e para −w a partir do eixo da casca, na pegada do corpo (fora do recetáculo). Por omissão é o
    corpo sobremoldado de catálogo (12 × 6,5 mm, centrado na casca, manga de 4,6 mm); se uma peça lhe ficar por baixo
    (no 5″ o Pi está na janela da placa de cima: a placa fica 0,4 mm abaixo da casca) o corpo sobe, se lhe ficar por
    cima baixa o topo, e se lhe encostar do lado oposto à manga (a cabeça de um parafuso) estreita desse lado — até ao
    mínimo de uma ficha USB-C macho de SOLDAR (casca + placa) metida em termo-retráctil (0,3 mm à volta da casca;
    estimado). As 3 medidas repetem-se até a pegada estabilizar (o que encosta ao lado não conta como chão)."""
    t = USBC_CORPO[1]
    h_min = 0.5 * USBC_CASCA[1] + 0.0003
    w_min = 0.5 * USBC_CASCA[0] + 0.0003
    a0, a1 = -USBC_VISTA - L, -USBC_VISTA

    def P(w, a, h=0.0):
        return O + w * wv + a * av + h * hv
    cantos = [P(w, a, h) for w in (-w_m - 0.004, w_m + USBC_MANGA + 0.002) for a in (a0 - 0.001, a1)
              for h in (-t - 0.002, t + 0.004)]
    sonda = cena.sonda({"drone": np.zeros(3)}, (np.min(cantos, axis=0), np.max(cantos, axis=0)), excluir=_SO_FIOS)
    A = np.linspace(a0, a1 - 0.0002, 10)
    w_lo, h_lo, h_hi = w_m, -0.5 * t, 0.5 * t
    for _ in range(4):
        base = np.array([P(w, a) for w in np.linspace(-w_lo + 0.0003, w_m + USBC_MANGA, 12) for a in A])
        d_b = sonda.raios(base, np.repeat(-hv[None], len(base), axis=0), t + 0.002)
        d_c = sonda.raios(base, np.repeat(hv[None], len(base), axis=0), t + 0.004)
        h_lo = -0.5 * t
        if np.isfinite(d_b).any():
            h_lo = max(h_lo, -float(np.min(d_b)) + 0.00015)
        h_lo = min(h_lo, -h_min)
        h_hi = h_lo + t
        if np.isfinite(d_c).any():
            h_hi = min(h_hi, float(np.min(d_c)) - 0.00015)
        h_hi = max(h_hi, h_min)
        lado = np.array([P(0.0, a, h) for a in A for h in np.linspace(h_lo + 0.0002, h_hi - 0.0002, 8)])
        d_l = sonda.raios(lado, np.repeat(-wv[None], len(lado), axis=0), w_m + 0.002)
        w_novo = max(min(w_m, float(np.min(d_l)) - 0.0003), w_min) if np.isfinite(d_l).any() else w_m
        if abs(w_novo - w_lo) < 1e-5:
            break
        w_lo = w_novo
    return h_lo, h_hi, w_lo, min(0.0046, h_hi - h_lo - 0.0004)


def _torcao_coluna(centro, sl, nn, bb, x_col: float, y_col: float, z0: float) -> tuple[float, float, float]:
    """Torção do par de 5 V no troço deitado ATÉ à coluna (φ0, s de início e de fim): na coluna os 2 fios ficam lado a
    lado em x (a folga entre a borda do Pi e a janela da placa de cima, em y, só leva um fio de cada vez)."""
    P = np.asarray(centro, dtype=float)
    i_c = int(np.argmin(np.abs(P[:, 0] - x_col) + np.abs(P[:, 1] - y_col) + 10.0 * np.abs(P[:, 2] - (z0 + 0.0045))))
    ny, by = float(nn[i_c][1]), float(bb[i_c][1])
    phi0 = math.atan2(-ny, by)
    if phi0 > 0.5 * math.pi:
        phi0 -= math.pi
    elif phi0 < -0.5 * math.pi:
        phi0 += math.pi
    sb = max(float(sl[i_c]) - 0.004, 0.006)
    return phi0, min(0.003, sb - 0.002), sb


def _fase_sinal(cena: _Cena, ids, xa: float, xb: float, x_ref: float) -> float:
    """x (entre xa e xb, a ≥ 3 mm das pontas) onde os 2 fios do par entrançado de sinal estão um por cima do outro (o
    feixe com o par de 5 V fica um quadrado compacto na abraçadeira)."""
    fios = [c["pts"] for c in cena.m.cabos if c["id"] in ids]
    if len(fios) != 2:
        return x_ref
    lo, hi = min(xa, xb) + 0.003, max(xa, xb) - 0.003
    melhor, x_m = math.inf, x_ref
    for x in np.linspace(lo, hi, max(2, int((hi - lo) / 0.0003))):
        cs, d_vert = [], []
        for P in fios:
            sx = P[:, 0] - x
            i = np.flatnonzero(sx[:-1] * sx[1:] <= 0.0)
            if not len(i):
                break
            i = int(i[0])
            a, b = P[i], P[i + 1]
            cs.append(a + (b - a) * (sx[i] / (sx[i] - sx[i + 1]) if sx[i] != sx[i + 1] else 0.0))
            d_vert.append(float(x - min(a[0], b[0])))
        if len(cs) != 2 or (0.0004 < min(d_vert) < 0.0008):
            continue
        d = cs[1] - cs[0]
        nota = abs(float(d[1])) / max(float(np.linalg.norm(d[1:])), 1e-9) + 0.02 * abs(x - x_ref) / 0.01
        if nota < melhor:
            melhor, x_m = nota, float(x)
    return x_m


def _feixe_5v(cena: _Cena, alvos, x_col: float, sep: float):
    """O troço do par de SINAL de um ESC que corre direito ao lado −y do FC, entre a coluna do par de 5 V e as ilhas: o
    5 V corre encostado a ele por fora — (y do 5 V, z, x de entrada, x de saída, x da abraçadeira, ids do sinal)."""
    fc = cena.fc
    if fc is None or not cena.sinal_lado:
        return None
    x_ilhas = [float(cx.lo[0]) for _p, cx, _n, _t in alvos] + [float(cx.hi[0]) for _p, cx, _n, _t in alvos]
    sg = -1.0 if x_col > max(x_ilhas) else 1.0
    # passa as ilhas e volta a elas; o troço junto ao sinal tem ≥ 16 mm (o par de sinal fica de pé a cada 10 mm: a
    # abraçadeira vai onde ele está de pé, a ≥ 3 mm das pontas do troço)
    xb = (min(x_ilhas) - 0.0040) if sg < 0 else (max(x_ilhas) + 0.0040)
    xa = x_col + sg * 0.0030
    if abs(xb - xa) < 0.016:
        xb = xa + sg * 0.016
    for k, (ys, zs, x0, x1) in sorted(cena.sinal_lado.items()):
        if ys > float(fc.c[1]):
            continue
        lo, hi = min(x0, x1) + 0.003, max(x0, x1) - 0.003
        if not (lo <= min(xa, xb) and max(xa, xb) <= hi):
            continue
        ids = {c["id"] for c in cena.m.cabos if c["peca"] == "cabo_esc" and c["inst"] == k and c["r"] < 0.0006
               and c["corpo"] == "drone"}
        x_t = 0.5 * (xa + xb)
        return ys, zs, xa, xb, x_t, ids
    return None


def _coluna_5v(cena: _Cena, rpi: _Caixa, x_min: float, sep: float):
    """(x, y) da coluna por onde o par de 5 V sobe pela folga entre a borda −y do Pi e a janela da placa de cima: a meio
    do troço livre entre a última porta que sai da borda (micro-HDMI) e o FPC da câmara (que sobe mais à frente),
    a meio da folga em y (medida com raios à altura da placa de cima)."""
    hdmi = cena.caixa("rpi5_micro_hdmi_2")
    hdmi1 = cena.caixa("rpi5_micro_hdmi_1")
    x_lo = max(x_min, float(hdmi.hi[0]) if hdmi is not None else float(rpi.lo[0]) + 0.043)
    x_lo += 0.5 * sep + 0.5 * D_20 + 0.0012
    x_hi = float(rpi.lo[0]) + 0.052                     # o CAM/DISP 0 (e o FPC) começam a 46 mm da borda de trás
    con = cena.rpi_peca("el_rpi5_cam_disp0")
    trava = cena.rpi_peca("el_rpi5_cam_disp0_trava")
    if cena.cam_csi and con is not None and hdmi is not None and hdmi1 is not None:
        # o FPC da câmara sobe pela borda −y entre o micro-HDMI 2 e o pilar (e dobra por cima do conector): o par de
        # 5 V sobe ENTRE os 2 micro-HDMI (a folga de 5,9 mm, sem nada que saia da borda)
        x_lo = max(x_min, float(hdmi1.hi[0])) + 0.5 * sep + 0.5 * D_20 + 0.0010
        x_hi = float(hdmi.lo[0]) - (0.5 * sep + 0.5 * D_20 + 0.0010)
    elif cena.cam_csi and con is not None:
        x_tr = float(trava.hi[0]) if trava is not None else float(con.hi[0]) + 0.001
        x_hi = x_tr + 0.0015 - 0.5 * sep - 0.5 * D_20 - 0.0012     # borda de trás da dobra do FPC (x_d − ½·larg)
    x = 0.5 * (x_lo + x_hi) if x_hi > x_lo else x_lo
    # folga em y: da borda do Pi (ou das portas) à janela, medida com raios horizontais à altura da placa de cima
    z_pl = (cena.z_sup if cena.z_sup is not None else float(rpi.c[2]))
    zona = (np.array([x - 0.004, float(rpi.lo[1]) - 0.010, z_pl - 0.002]),
            np.array([x + 0.004, float(rpi.lo[1]) + 0.002, z_pl + 0.002]))
    sonda = cena.sonda({"drone": np.zeros(3)}, zona, excluir=_SO_FIOS)
    q = np.array([x, float(rpi.lo[1]) - 0.0005, z_pl])
    d = sonda.raio(q, [0.0, -1.0, 0.0], 0.010)
    y_janela = float(q[1]) - d if d is not None else float(rpi.lo[1]) - 0.004
    y = 0.5 * (y_janela + float(rpi.lo[1]))
    return x, y


def _sobre_cabos(pts, cabos, r: float, r_c: float, folga: float = 0.0004) -> list:
    """A polilinha `pts` (mantém as pontas) levantada onde passa a menos de r + r_c + folga dos `cabos` (polilinhas de
    raio r_c): à altura exata que a tira deles, com rampas suaves de 6 mm (um fio que passa por cima de outro)."""
    P = np.asarray(_reamostrar([np.asarray(q, dtype=float) for q in pts], 0.001))
    if len(P) < 3:
        return [q for q in P]
    alc = r + r_c + folga
    dz = np.zeros(len(P))
    for C in cabos:
        C = np.asarray(C, dtype=float)
        A, B = C[:-1], C[1:]
        AB = B - A
        L2 = np.maximum(np.einsum("ij,ij->i", AB[:, :2], AB[:, :2]), 1e-14)
        for k, q in enumerate(P):
            t = np.clip(np.einsum("ij,ij->i", q[:2] - A[:, :2], AB[:, :2]) / L2, 0.0, 1.0)
            pc = A + t[:, None] * AB
            dxy = np.linalg.norm(q[:2] - pc[:, :2], axis=1)
            perto = dxy < alc
            if np.any(perto):
                z_min = float(np.max(pc[perto, 2] + np.sqrt(alc ** 2 - dxy[perto] ** 2)))
                dz[k] = max(dz[k], z_min - float(q[2]))
    if not np.any(dz > 0.0):
        return [q for q in P]
    n = 6
    dz = np.array([max(dz[max(0, i - n): i + n + 1]) for i in range(len(dz))])      # patamar de ±6 mm …
    dz = np.convolve(np.pad(dz, n, mode="edge"), np.ones(2 * n + 1) / (2 * n + 1), mode="valid")   # … e rampas
    dz[0] = dz[-1] = 0.0
    Q = P.copy()
    Q[:, 2] += dz
    return _simplificar([q for q in Q], 0.0001)


def _assentar(cena: _Cena, pts, r: float) -> list:
    """Troço de um cabo deitado numa placa (do 1.º ponto, que fica, ao último): assenta nela e nas peças, e passa POR
    CIMA dos cabos já desenhados que cruza (raios de 3,5 mm acima do eixo: nunca de dentro da placa de cima/PCB)."""
    return _drapejar(cena, pts, r, acima=0.0035, acima_cabos=0.004, fixar_inicio=True)


def _altura_topo_5v(cena: _Cena, alvos) -> float:
    """z a que o par corre por cima da placa de energia até às ilhas: acima da placa e das peças dela."""
    cx = alvos[0][1]
    z = float(cx.hi[2])
    pdb = cena.caixa("el_pdb_pcb") or cena.pdb_massa
    if pdb is not None:
        z = max(z, float(pdb.hi[2]))
    return z + 0.5 * D_20 + 0.0003


def _pontas_5v(cena: _Cena, fios, alvos, z_alto: float, nome_usbc, sep: float) -> None:
    """Cada fio do par, do topo da coluna à sua ilha (assenta na placa de energia, nas peças dela e nos cabos que lá
    estão) — ou, sem as ilhas, à ficha `el_pm_saida_5v` (ficha de entrada lateral, na face virada para o par)."""
    m = cena.m
    _ = sep
    if alvos[0][3] == "ficha":
        cx = alvos[0][1]
        topo = 0.5 * (fios[0][-1] + fios[1][-1])
        lado = -1.0 if float(topo[1]) < float(cx.c[1]) else 1.0          # face y da ficha virada para o par
        y_face = float(cx.lo[1]) if lado < 0 else float(cx.hi[1])
        prof = 0.0045
        plug_c = np.array([float(cx.c[0]), y_face + lado * 0.5 * prof, float(cx.c[2])])
        m.caixa("drone", "fios_jst", plug_c, np.eye(3), [0.5 * float(cx.hi[0] - cx.lo[0]) - 0.0003, 0.5 * prof,
                                                         0.5 * float(cx.hi[2] - cx.lo[2]) - 0.0003])
    # os fios do par (de que cada ponta é a continuação) não contam para o assentar; vai primeiro o fio da ilha mais
    # perto da sua ponta — o outro, se tiver de o cruzar, passa por cima dele
    ids_par = {c["id"] for c in m.cabos if c["id"].startswith("rpi5_5v_")}
    ordem = list(zip(alvos, fios, strict=True))
    if alvos[0][3] == "ilha":
        ordem.sort(key=lambda a_q: float(np.linalg.norm(np.asarray(a_q[0][1].c)[:2] - np.asarray(a_q[1][-1])[:2])))
    for (polo, cx, nome, tipo), q in ordem:
        mat = "fios_vermelho" if polo == "pos" else "fios_preto"
        topo = q[-1]
        if tipo == "ilha":
            fim = np.array([float(cx.c[0]), float(cx.c[1]), float(cx.hi[2]) + 0.5 * D_20 - 0.0002])
            d_xy = _u([fim[0] - topo[0], fim[1] - topo[1], 0.0])
            pre = fim - 0.004 * d_xy
            guia = [topo, np.array([topo[0], topo[1], z_alto]), np.array([pre[0], pre[1], z_alto])]
            # se a ponta do OUTRO fio do par está à frente, rente ao caminho: este afasta-se dela para o lado antes de
            # seguir (não lhe passa por cima da ponta)
            outro = next((f[-1] for f in fios if f is not q), None)
            if outro is not None:
                rel = np.asarray(outro, dtype=float)[:2] - topo[:2]
                lat_v = np.array([-d_xy[1], d_xy[0]])
                ao_l, lat = float(rel @ d_xy[:2]), float(rel @ lat_v)
                if 0.0 < ao_l < float(np.linalg.norm(pre[:2] - topo[:2])) and abs(lat) < D_20 + 0.0004:
                    desv = -math.copysign(1.0, lat if abs(lat) > 1e-9 else 1.0) * (D_20 + 0.00045 - abs(lat))
                    lado_p = topo[:2] + desv * lat_v + (ao_l + 0.002) * d_xy[:2]
                    guia = [topo, np.array([topo[0], topo[1], z_alto]),
                            np.array([lado_p[0], lado_p[1], z_alto]), np.array([pre[0], pre[1], z_alto])]
            pts = _drapejar(cena, guia, 0.5 * D_20, ignorar=ids_par, fixar_inicio=True)
            pts = [*pts, pre + np.array([0.0, 0.0, 0.5 * D_20]), fim]
            m.tubo("drone", mat, _curva(pts, 0.003, n=3), D_20, ident=f"rpi5_5v_{polo}_ilha")
            m.tubo("drone", "fios_estanho", [fim - 0.0012 * d_xy, fim + 0.0012 * d_xy], D_SOLDA, lados=10, cabo=False)
            toque = _toque_ilha(cx, fim)
        else:
            dx = -0.00125 if polo == "pos" else 0.00125
            fim = np.array([float(cx.c[0]) + dx, y_face + lado * (prof - 0.0008), float(cx.c[2])])
            fora = fim + np.array([0.0, lado * 0.006, 0.0])
            guia = [topo, np.array([topo[0], topo[1], z_alto]), np.array([fora[0], fora[1], z_alto])]
            pts = _drapejar(cena, guia, 0.5 * D_20, ignorar=ids_par, fixar_inicio=True)
            pts = [*pts, np.array([fora[0], fora[1], max(float(fora[2]), float(pts[-1][2]) - 0.001)]), fim]
            m.tubo("drone", mat, _curva(pts, 0.003, n=3), D_20, ident=f"rpi5_5v_{polo}_ficha")
            toque = np.array([fim[0], y_face, fim[2]])
        cena.ligar(f"rpi5_5v_{polo}", nome, nome_usbc, "drone", toque, "drone", _ponto_usbc(cena), "20 AWG",
                   "cabo_rpi5_5v", polo=polo, ficha="USB-C macho a 90° (sobremoldada)")


def _ponto_usbc(cena: _Cena) -> np.ndarray:
    """Ponto de contacto da ficha no recetáculo: o fundo da casca metida (dentro do `rpi5_usbc`)."""
    usbc = cena.rpi_peca("rpi5_usbc")
    return np.array([float(usbc.c[0]), float(usbc.lo[1]) + USBC_METIDA - 0.0005, float(usbc.c[2])])


def _rpi_fc(cena: _Cena) -> None:
    """UART RPi ↔ FC; I2C FC ↔ INA226; ficha dos sinais dos ESC no FC; sensores de baixo."""
    m, rpi, fc = cena.m, cena.rpi, cena.fc
    # ---- UART: Dupont 1×3 nos pinos 6/8/10 (colunas 3–5 do GPIO, fila de fora) → JST-GH no `el_fc_con_uart`
    uart = cena.fc_con("el_fc_con_uart")
    nome_uart = cena.nome_ancora("el_fc_con_uart", "el_fc_h7")
    gpio = cena.rpi_peca("rpi5_gpio_40p")
    if rpi is not None and uart is not None and gpio is not None:
        with m.peca("cabo_uart"):
            pinos = [cena.rpi_peca(f"el_rpi5_gpio_pino{c:02d}") for c in (3, 4, 5)]
            nomes_p = [cena.nome_ancora(f"el_rpi5_gpio_pino{c:02d}", "el_rpi5") for c in (3, 4, 5)]
            x_p = [float(p.c[0]) for p in pinos]
            y_p = float(rpi.lo[1]) + 53.77 * MM
            z_b = float(gpio.hi[2])
            z_pino = float(pinos[0].hi[2])
            z_c = z_b + 0.014
            m.caixa("drone", "fios_dupont", np.array([x_p[1], y_p, 0.5 * (z_b + z_c)]), np.eye(3),
                    [0.0038, 0.00127, 0.007])
            f_u = np.array([float(uart.c[0]), float(uart.hi[1]) + 0.0021, float(uart.c[2])])
            m.caixa("drone", "fios_jst", f_u, np.eye(3), [0.0030, 0.0021, 0.0015])
            # na ficha do FC pela mesma ordem em que saem dos pinos (o passo encolhe de 2,54 para 1,25 mm sem cruzar)
            sg_x = 1.0 if x_p[2] >= x_p[0] else -1.0
            for j, (x, mat, dx, sinal) in enumerate(((x_p[0], "fios_preto", -0.00125 * sg_x, "GND (pino 6)"),
                                                      (x_p[1], "fios_amarelo", 0.0, "TXD (pino 8)"),
                                                      (x_p[2], "fios_verde", 0.00125 * sg_x, "RXD (pino 10)"))):
                # os 3 seguem em fila ao longo da fila de pinos: cada um a 1,1 mm de altura do vizinho (fita de pé)
                dz_f = (1 - j) * 0.0011
                # (no build acessível passa rasa: os cabos dos servos do cotovelo cruzam por cima dela, por baixo dos
                # sinais dos ESC)
                z_sobe = 0.0015 if cena.servo_pwm else 0.004
                pts = [np.array([x, y_p, z_pino]), np.array([x, y_p, z_c + z_sobe + dz_f]),
                       np.array([f_u[0] + dx, f_u[1] + 0.007, f_u[2] + 0.002 + dz_f]),
                       np.array([f_u[0] + dx, float(uart.hi[1]) + 0.0008, f_u[2]])]
                m.tubo("drone", mat, _curva(pts, 0.004), D_JST)
                cena.ligar(f"uart_{('gnd', 'txd', 'rxd')[j]}", nomes_p[j], nome_uart, "drone", pts[0], "drone",
                           [f_u[0] + dx, float(uart.hi[1]), f_u[2]], "26 AWG", "cabo_uart", sinal=sinal)
    # ---- I2C: FC → INA226 da placa de energia
    i2c, i2c_p = cena.fc_con("el_fc_con_i2c"), cena.pdb_pad("el_pm_con_i2c")
    if i2c is not None and i2c_p is not None:
        with m.peca("cabo_i2c"):
            a = np.array([float(i2c.hi[0]) + 0.0021, float(i2c.c[1]), float(i2c.c[2])])
            b = np.array([float(i2c_p.hi[0]) + 0.0021, float(i2c_p.c[1]), float(i2c_p.c[2])])
            for c in (a, b):
                m.caixa("drone", "fios_jst", c, np.eye(3), [0.0021, 0.0030, 0.0015])
            for j, mat in enumerate(("fios_preto", "fios_vermelho", "fios_amarelo", "fios_azul")):
                dy = (j - 1.5) * 1.25 * MM
                pts = [a + np.array([0.0012, dy, 0.0]), a + np.array([0.008, dy, 0.002]),
                       b + np.array([0.008, dy, -0.002]), b + np.array([0.0012, dy, 0.0])]
                m.tubo("drone", mat, _curva(pts, 0.004), D_JST, lados=6)
            cena.ligar("i2c_ina226", cena.nome_ancora("el_fc_con_i2c", "el_fc_h7"),
                       cena.nome_ancora("el_pm_con_i2c", "el_cablagem"), "drone",
                       [float(i2c.hi[0]), float(i2c.c[1]), float(i2c.c[2])], "drone",
                       [float(i2c_p.hi[0]), float(i2c_p.c[1]), float(i2c_p.c[2])], "4 × 28 AWG (JST-GH)", "cabo_i2c")
    # ---- ficha JST-GH dos sinais dos 4 ESC no `el_fc_con_esc`
    con = cena.fc_con("el_fc_con_esc")
    if con is not None and fc is not None:
        m.caixa("drone", "fios_jst", np.array([float(con.lo[0]) - 0.0021, float(con.c[1]), float(con.c[2])]),
                np.eye(3), [0.0021, 0.0044, 0.0015])
    _sensores(cena)


def _dilatar(g: np.ndarray, k: int = 1) -> np.ndarray:
    """Dilatação binária 3D pelo cubo 3×3×3 (vizinhança 26), k vezes — separável (3 passagens 1D), só numpy."""
    g = g.copy()
    for _ in range(k):
        for ax in range(3):
            a = np.moveaxis(g, ax, 0)
            b = a.copy()
            b[1:] |= a[:-1]
            b[:-1] |= a[1:]
            g = np.moveaxis(b, 0, ax)
    return g


def _caminho_livre(cena: _Cena, corpo: str, lo, hi, ini, fim, r: float, h: float = 0.0015,
                   excluir=_SO_FIOS, com_cabos: bool = False, rapido: bool = False) -> list | None:
    """Caminho de um cabo de raio r de `ini` a `fim` por entre as peças visíveis do corpo, dentro da caixa (lo, hi):
    superfícies amostradas numa grelha de voxels de h (os triângulos grandes partidos e cortados à caixa), as peças
    engordadas de r + 0,4 mm (dilatação), frente de onda (26 vizinhos) do início ao fim — primeiro com 1,5 mm de folga
    a mais, se houver caminho — e atalhos em linha reta pelos voxels livres. Só numpy. Devolve os pontos ou None.
    `com_cabos`: os cabos já desenhados no corpo também são obstáculos. `rapido`: em vez das amostras, os triângulos
    partidos até à aresta ≤ h marcam os voxels dos 8 cantos da caixa deles (conservador; ~10× mais depressa)."""
    lo, hi = np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)
    forma = tuple(int(v) for v in np.ceil((hi - lo) / h))
    if min(forma) < 3 or int(np.prod(forma)) > 400000:
        return None
    partes = []
    gr = cena.tri.de(corpo)
    if gr is not None:
        aceita = np.array([not excluir.search(nm) for nm in gr.nomes], dtype=bool)
        idx = gr.indices(lo - 0.002, hi + 0.002, aceita)
        if len(idx):
            partes.append(gr.T[idx])
    for c_, nome, _t, _pos, _rr, _sz, bb in cena.geoms_primitivas():
        if c_ != corpo or excluir.search(nome) or bb is None or np.any(bb[1] < lo) or np.any(bb[0] > hi):
            continue
        q = np.array([[a, b, c] for a in (0, 1) for b in (0, 1) for c in (0, 1)], dtype=float)
        V = bb[0] + q * (bb[1] - bb[0])             # a caixa da primitiva (conservador) em 12 triângulos
        F = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6),
                      (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
        partes.append(V[F])
    occ = np.zeros(forma, dtype=bool)
    if partes:
        T = np.concatenate(partes)
        lmax_alvo = (1.0 if rapido else 5.0) * h
        for _ in range(24):              # bissecção da aresta mais comprida (os bocados fora da caixa saem)
            E = np.stack([np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 1], axis=1),
                          np.linalg.norm(T[:, 0] - T[:, 2], axis=1)], axis=1)
            grande = E.max(axis=1) > lmax_alvo
            if not np.any(grande):
                break
            G = T[grande]
            k = np.argmax(E[grande], axis=1)                 # aresta (k, k+1) é a maior
            ar = np.arange(len(G))
            A, B, C = G[ar, k], G[ar, (k + 1) % 3], G[ar, (k + 2) % 3]
            Mm = 0.5 * (A + B)
            novos = np.concatenate([np.stack([C, A, Mm], axis=1), np.stack([C, Mm, B], axis=1)])
            dentro = np.all(novos.max(axis=1) >= lo - h, axis=1) & np.all(novos.min(axis=1) <= hi + h, axis=1)
            T = np.concatenate([T[~grande], novos[dentro]])
        if rapido:
            # arestas ≤ h: a caixa de cada triângulo toca no máximo 2 voxels por eixo — os dos 8 cantos dela
            lo_t, hi_t = T.min(axis=1), T.max(axis=1)
            ij_lo = np.floor((lo_t - lo) / h).astype(np.int64)
            ij_hi = np.floor((hi_t - lo) / h).astype(np.int64)
            for ax_ in (ij_lo[:, 0], ij_hi[:, 0]):
                for ay_ in (ij_lo[:, 1], ij_hi[:, 1]):
                    for az_ in (ij_lo[:, 2], ij_hi[:, 2]):
                        ok = ((ax_ >= 0) & (ax_ < forma[0]) & (ay_ >= 0) & (ay_ < forma[1]) & (az_ >= 0)
                              & (az_ < forma[2]))
                        occ[ax_[ok], ay_[ok], az_[ok]] = True
        else:
            # amostras baricêntricas fixas (lado ≤ 5h, 8 divisões: ≤ 0,63 h entre amostras — cada voxel que a
            # superfície atravessa leva pelo menos uma)
            ns = 8
            u, v = np.meshgrid(np.arange(ns + 1), np.arange(ns + 1), indexing="ij")
            ok = (u + v) <= ns
            u, v = (u[ok] / ns)[None, :, None], (v[ok] / ns)[None, :, None]
            P = (T[:, None, 0] + u * (T[:, None, 1] - T[:, None, 0]) + v * (T[:, None, 2] - T[:, None, 0])).reshape(-1,
                                                                                                                     3)
            ij = np.floor((P - lo) / h).astype(np.int64)
            ok = np.all((ij >= 0) & (ij < np.array(forma)), axis=1)
            ij = ij[ok]
            occ[ij[:, 0], ij[:, 1], ij[:, 2]] = True
    if com_cabos:
        # os cabos já desenhados neste corpo também são obstáculos: os voxels a menos do raio deles do eixo (amostrado
        # de 1 em 1 mm), além da dilatação
        Pc, Rc = _amostras_cabos(cena, corpo)
        if len(Pc):
            perto = np.all(Pc >= lo - 0.005, axis=1) & np.all(Pc <= hi + 0.005, axis=1)
            Pc, Rc = Pc[perto], Rc[perto]
            nr = np.ceil(Rc / h - 0.5).astype(np.int64)
            for n_r in np.unique(nr):
                sel = nr == n_r
                g_ = np.arange(-int(n_r), int(n_r) + 1)
                offs = np.stack(np.meshgrid(g_, g_, g_, indexing="ij"), axis=-1).reshape(-1, 3)
                ij = (np.floor((Pc[sel] - lo) / h).astype(np.int64)[:, None, :] + offs[None, :, :]).reshape(-1, 3)
                ok = np.all((ij >= 0) & (ij < np.array(forma)), axis=1)
                occ[ij[ok, 0], ij[ok, 1], ij[ok, 2]] = True

    def no(p, livre):
        i = np.clip(np.floor((np.asarray(p, dtype=float) - lo) / h).astype(int), 0, np.array(forma) - 1)
        if livre[tuple(i)]:
            return tuple(i)
        cand = np.argwhere(livre)
        if not len(cand):
            return None
        d = np.linalg.norm(cand - i, axis=1)
        j = int(np.argmin(d))
        return tuple(cand[j]) if d[j] <= 4 else None

    k1 = max(1, math.ceil((r + 0.0004) / h))
    caminho = None
    for k in (k1 + max(1, round(0.0015 / h)), k1):
        livre = ~_dilatar(occ, k)
        a_i, b_i = no(ini, livre), no(fim, livre)
        if a_i is None or b_i is None:
            continue
        dist = np.full(forma, -1, dtype=np.int32)
        dist[a_i] = 0
        frente = np.zeros(forma, dtype=bool)
        frente[a_i] = True
        passo = 0
        while not frente[b_i] and frente.any() and passo < 600:
            passo += 1
            frente = _dilatar(frente) & livre & (dist < 0)
            dist[frente] = passo
        if dist[b_i] < 0:
            continue
        cam = [b_i]
        while dist[cam[-1]] > 0:
            x, y, z = cam[-1]
            dv = dist[x, y, z] - 1
            viz = [(x + a, y + b, z + c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)
                   if (a or b or c) and 0 <= x + a < forma[0] and 0 <= y + b < forma[1] and 0 <= z + c < forma[2]
                   and dist[x + a, y + b, z + c] == dv]
            # o vizinho mais alinhado com o início (caminho mais direito)
            alvo_i = np.array(a_i)
            cam.append(min(viz, key=lambda q: float(np.linalg.norm(np.array(q) - alvo_i))))
        caminho, livre_ok = cam[::-1], livre
        break
    if caminho is None:
        return None
    P = [np.asarray(ini, dtype=float), *[lo + (np.array(q) + 0.5) * h for q in caminho[1:-1]],
         np.asarray(fim, dtype=float)]

    def reta(p, q):
        n = max(2, int(np.linalg.norm(q - p) / (0.5 * h)))
        Q = np.array([p + (q - p) * t for t in np.linspace(0.0, 1.0, n)])
        ij = np.clip(np.floor((Q - lo) / h).astype(int), 0, np.array(forma) - 1)
        return bool(np.all(livre_ok[ij[:, 0], ij[:, 1], ij[:, 2]]))
    out, i = [P[0]], 0
    while i < len(P) - 1:
        j = len(P) - 1
        while j > i + 1 and not reta(P[i], P[j]):
            j -= 1
        out.append(P[j])
        i = j
    return out


class _Mesa:
    """Mapa 2,5D (células de h em xy) de uma região de um corpo para cabos que correm DEITADOS a uma altura mínima
    `z_nom`: por célula, o CHÃO (o topo mais alto do que está por baixo — peças e cabos — até `z_nom + acima`) e o TETO
    (o fundo mais baixo do que sobe acima disso: o que está por cima e as paredes que atravessam a faixa). Um cabo de
    raio r passa numa célula com o eixo a z_c = max(z_nom, chão ⊕ r + folga) se o teto ⊖ (r + folga) ficar acima do
    topo dele. Triângulos das malhas visíveis (os grandes partidos até ≤ 2 células) e caixas das primitivas, como nas
    sondas; os cabos amostrados de 1 em 1 mm. Partilhado pelos cabos da mesma região e altura (`juntar` acrescenta os
    que se vão desenhando)."""

    def __init__(self, cena: _Cena, lo, hi, z_nom: float, acima: float = 0.004, h: float = 0.001,
                 corpo: str = "drone", excluir=_SO_FIOS, r_max: float = 0.003, invertido: bool = False):
        lo, hi = np.asarray(lo, dtype=float)[:2], np.asarray(hi, dtype=float)[:2]
        self.cena, self.corpo, self.lo, self.h = cena, corpo, lo, h
        self.forma = tuple(int(v) for v in np.ceil((hi - lo) / h))
        # `invertido`: cabos COLADOS POR BAIXO de uma placa (z virado: o «chão» é a face de baixo dela, e o que está
        # pendurado é contornado por baixo) — as alturas guardam-se viradas e as rotas voltam ao referencial do corpo
        self.sz = -1.0 if invertido else 1.0
        self.z_nom, self.z_sonda = self.sz * float(z_nom), self.sz * float(z_nom) + acima
        self.chao = np.full(self.forma, -np.inf)
        self.teto = np.full(self.forma, np.inf)
        # só conta o que pode tocar num cabo de raio ≤ r_max deitado entre z_nom e z_nom + acima (+ o que ele sobe)
        z_lo, z_hi = self.z_nom - r_max - 0.001, self.z_sonda + 2.0 * r_max + 0.004
        if invertido:
            z_lo, z_hi = -z_hi, -z_lo
        clo, chi = np.array([lo[0], lo[1], z_lo]), np.array([hi[0], hi[1], z_hi])
        partes = []
        gr = cena.tri.de(corpo)
        if gr is not None:
            aceita = np.array([not excluir.search(nm) for nm in gr.nomes], dtype=bool)
            idx = gr.indices(clo - 0.002, chi + 0.002, aceita)
            if len(idx):
                partes.append(gr.T[idx])
        q = np.array([[a, b, c] for a in (0, 1) for b in (0, 1) for c in (0, 1)], dtype=float)
        F = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6),
                      (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
        for c_, nome, _t, _pos, _rr, _sz, bb in cena.geoms_primitivas():
            if c_ != corpo or excluir.search(nome) or bb is None or np.any(bb[1] < clo) or np.any(bb[0] > chi):
                continue
            partes.append((bb[0] + q * (bb[1] - bb[0]))[F])
        if partes:
            T = np.concatenate(partes)
            if invertido:
                T = T.copy()
                T[:, :, 2] *= -1.0
                z_lo, z_hi = -z_hi, -z_lo
            # os grandes HORIZONTAIS (placas, tampos) rasterizam-se de vez (centros das células dentro deles, z do plano);
            # os VERTICAIS (paredes) pela projeção, que é um segmento; só os inclinados se partem
            ext = T[:, :, :2].max(axis=1) - T[:, :, :2].min(axis=1)
            grande = ext.max(axis=1) > 10.0 * h
            if np.any(grande):
                nrm = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
                nz = np.abs(nrm[:, 2]) / np.maximum(np.linalg.norm(nrm, axis=1), 1e-18)
                hor, ver = grande & (nz > 0.995), grande & (nz < 0.02)
                self._horizontais(T[hor])
                self._verticais(T[ver])
                T = T[~(hor | ver)]
            for _ in range(24):            # parte os que cobrem mais de 2 células em xy (os de fora da região saem)
                ext = T[:, :, :2].max(axis=1) - T[:, :, :2].min(axis=1)
                grande = ext.max(axis=1) > 2.0 * h
                if not np.any(grande):
                    break
                G = T[grande]
                E = np.stack([np.linalg.norm(G[:, 1] - G[:, 0], axis=1), np.linalg.norm(G[:, 2] - G[:, 1], axis=1),
                              np.linalg.norm(G[:, 0] - G[:, 2], axis=1)], axis=1)
                k = np.argmax(E, axis=1)
                ar = np.arange(len(G))
                A, B, C = G[ar, k], G[ar, (k + 1) % 3], G[ar, (k + 2) % 3]
                Mm = 0.5 * (A + B)
                novos = np.concatenate([np.stack([C, A, Mm], axis=1), np.stack([C, Mm, B], axis=1)])
                dentro = (np.all(novos[:, :, :2].max(axis=1) >= lo - h, axis=1)
                          & np.all(novos[:, :, :2].min(axis=1) <= hi + h, axis=1)
                          & (novos[:, :, 2].max(axis=1) >= z_lo) & (novos[:, :, 2].min(axis=1) <= z_hi))
                T = np.concatenate([T[~grande], novos[dentro]])
            zmn, zmx = T[:, :, 2].min(axis=1), T[:, :, 2].max(axis=1)
            i0 = np.floor((T[:, :, :2].min(axis=1) - lo) / h).astype(np.int64)
            i1 = np.floor((T[:, :, :2].max(axis=1) - lo) / h).astype(np.int64)
            self._espalhar(i0, i1, zmn, zmx)
        self._lotes: list = []
        self.proibido = np.zeros(self.forma, dtype=bool)
        Pc, Rc = _amostras_cabos(cena, corpo)
        if len(Pc):
            self.juntar(Pc, Rc)

    def proibir(self, lo, hi) -> None:
        """Nenhum cabo passa por cima desta caixa em xy (p. ex. a pilha do FC: nunca entre as placas dela)."""
        a = np.floor((np.asarray(lo, dtype=float)[:2] - self.lo) / self.h).astype(int)
        b = np.ceil((np.asarray(hi, dtype=float)[:2] - self.lo) / self.h).astype(int)
        a, b = np.clip(a, 0, np.array(self.forma)), np.clip(b, 0, np.array(self.forma))
        self.proibido[a[0]:b[0], a[1]:b[1]] = True

    @staticmethod
    def _por_celula(arr, ix, iy, v, fn) -> None:
        """arr[ix, iy] = fn(arr[ix, iy], v) com repetidos (ordenação + reduceat: muito mais rápido que ufunc.at)."""
        if not len(v):
            return
        flat = ix * arr.shape[1] + iy
        o = np.argsort(flat, kind="stable")
        fs, vs = flat[o], v[o]
        u, ini = np.unique(fs, return_index=True)
        red = fn.reduceat(vs, ini)
        arr.flat[u] = fn(arr.flat[u], red)

    def _horizontais(self, T) -> None:
        """Triângulos grandes e horizontais (placas, tampos), de uma vez, por linhas: em cada faixa de células em y, o
        troço em x que o triângulo lá ocupa (vértices e cruzamentos das arestas com as 2 bordas da faixa); agrupados por
        altura, cada grupo marca-se com somas acumuladas (sem partir os triângulos)."""
        if not len(T):
            return
        h, (nx, ny) = self.h, self.forma
        y0t, y1t = T[:, :, 1].min(axis=1), T[:, :, 1].max(axis=1)
        r0 = np.clip(np.floor((y0t - self.lo[1]) / h).astype(np.int64), 0, ny - 1)
        r1 = np.clip(np.floor((y1t - self.lo[1]) / h).astype(np.int64), 0, ny - 1)
        nr = r1 - r0 + 1
        it = np.repeat(np.arange(len(T)), nr)
        row = r0[it] + (np.arange(len(it)) - np.repeat(np.cumsum(nr) - nr, nr))
        ya = self.lo[1] + row * h
        yb = ya + h
        V = T[it][:, :, :2]                                     # (m, 3, 2)
        xs = [np.where((V[:, i, 1] >= ya) & (V[:, i, 1] <= yb), V[:, i, 0], np.nan) for i in range(3)]
        for i in range(3):
            A, B = V[:, i], V[:, (i + 1) % 3]
            dy = B[:, 1] - A[:, 1]
            seguro = np.where(np.abs(dy) < 1e-15, 1e-15, dy)
            for yl in (ya, yb):
                t = (yl - A[:, 1]) / seguro
                ok = (t >= 0.0) & (t <= 1.0) & (np.abs(dy) >= 1e-15)
                xs.append(np.where(ok, A[:, 0] + t * (B[:, 0] - A[:, 0]), np.nan))
        X = np.stack(xs, axis=1)
        tem = ~np.all(np.isnan(X), axis=1)
        xa, xb = np.nanmin(np.where(tem[:, None], X, 0.0), axis=1), np.nanmax(np.where(tem[:, None], X, 0.0), axis=1)
        c0 = np.clip(np.floor((xa - self.lo[0]) / h).astype(np.int64), 0, nx)
        c1 = np.clip(np.floor((xb - self.lo[0]) / h).astype(np.int64) + 1, 0, nx)
        val = tem & (c1 > c0) & (xb >= self.lo[0]) & (xa <= self.lo[0] + nx * h)
        z = T[:, :, 2].mean(axis=1)[it]
        zq = np.round(z / 0.00005).astype(np.int64)
        for q in np.unique(zq[val]):
            sel = val & (zq == q)
            d = np.zeros((nx + 1, ny), dtype=np.int32)
            np.add.at(d, (c0[sel], row[sel]), 1)
            np.add.at(d, (c1[sel], row[sel]), -1)
            cob = np.cumsum(d, axis=0)[:nx] > 0
            zz = float(q) * 0.00005
            if zz <= self.z_sonda:
                self.chao[cob] = np.maximum(self.chao[cob], zz)
            else:
                self.teto[cob] = np.minimum(self.teto[cob], zz)

    def _verticais(self, T) -> None:
        """Triângulos grandes e verticais (paredes), de uma vez: a projeção é um segmento — as células ao longo dele, com a
        altura toda do triângulo."""
        if not len(T):
            return
        xy = T[:, :, :2]
        d01 = np.linalg.norm(xy[:, 1] - xy[:, 0], axis=1)
        d12 = np.linalg.norm(xy[:, 2] - xy[:, 1], axis=1)
        d20 = np.linalg.norm(xy[:, 0] - xy[:, 2], axis=1)
        k = np.argmax(np.stack([d01, d12, d20], axis=1), axis=1)
        ar = np.arange(len(T))
        a, b = xy[ar, k], xy[ar, (k + 1) % 3]
        L = np.linalg.norm(b - a, axis=1)
        n = np.maximum(2, (L / (0.5 * self.h)).astype(np.int64) + 1)
        rep = np.repeat(ar, n)
        t = (np.arange(len(rep)) - np.repeat(np.cumsum(n) - n, n)) / np.repeat(n - 1, n)
        P = a[rep] + (b - a)[rep] * t[:, None]
        c = np.floor((P - self.lo) / self.h).astype(np.int64)
        zmn, zmx = T[:, :, 2].min(axis=1)[rep], T[:, :, 2].max(axis=1)[rep]
        ok = (c[:, 0] >= 0) & (c[:, 1] >= 0) & (c[:, 0] < self.forma[0]) & (c[:, 1] < self.forma[1])
        baixo = zmx <= self.z_sonda
        a_, b_ = ok & baixo, ok & ~baixo
        self._por_celula(self.chao, c[a_, 0], c[a_, 1], zmx[a_], np.maximum)
        self._por_celula(self.teto, c[b_, 0], c[b_, 1], zmn[b_], np.minimum)

    def _espalhar(self, i0, i1, zmn, zmx) -> None:
        nx, ny = self.forma
        baixo = zmx <= self.z_sonda
        IX, IY, VC, JX, JY, VT = [], [], [], [], [], []
        for dx in (0, 1, 2):
            for dy in (0, 1, 2):
                ix, iy = i0[:, 0] + dx, i0[:, 1] + dy
                ok = (ix <= i1[:, 0]) & (iy <= i1[:, 1]) & (ix >= 0) & (iy >= 0) & (ix < nx) & (iy < ny)
                a, b_ = ok & baixo, ok & ~baixo
                IX.append(ix[a]), IY.append(iy[a]), VC.append(zmx[a])
                JX.append(ix[b_]), JY.append(iy[b_]), VT.append(zmn[b_])
        self._por_celula(self.chao, np.concatenate(IX), np.concatenate(IY), np.concatenate(VC), np.maximum)
        self._por_celula(self.teto, np.concatenate(JX), np.concatenate(JY), np.concatenate(VT), np.minimum)

    def juntar(self, P, R) -> None:
        """Acrescenta cabos (amostras P (n, 3) de raios R): por célula da pegada, o fundo e o topo — se um cabo novo passa
        por cima ou por baixo deles decide-se em `via` (pelo raio dele)."""
        P, R = np.atleast_2d(np.asarray(P, dtype=float)), np.broadcast_to(np.asarray(R, dtype=float), (len(P),))
        if self.sz < 0.0:
            P = P * np.array([1.0, 1.0, -1.0])
        nx, ny = self.forma
        sel = ((P[:, 0] >= self.lo[0] - 0.006) & (P[:, 1] >= self.lo[1] - 0.006)
               & (P[:, 0] <= self.lo[0] + nx * self.h + 0.006) & (P[:, 1] <= self.lo[1] + ny * self.h + 0.006)
               & (P[:, 2] + R >= self.z_nom - 0.004) & (P[:, 2] - R <= self.z_sonda + 0.010))
        P, R = P[sel], R[sel]
        if not len(P):
            return
        nr = np.ceil(R / self.h).astype(np.int64)
        FL, ZN, ZX = [], [], []
        for n_r in np.unique(nr):
            g, Q = R[nr == n_r], P[nr == n_r]
            c = np.floor((Q[:, :2] - self.lo) / self.h).astype(np.int64)
            for dx in range(-int(n_r), int(n_r) + 1):
                for dy in range(-int(n_r), int(n_r) + 1):
                    if dx * dx + dy * dy > (n_r + 0.5) ** 2:
                        continue
                    ix, iy = c[:, 0] + dx, c[:, 1] + dy
                    ok = (ix >= 0) & (iy >= 0) & (ix < nx) & (iy < ny)
                    FL.append(ix[ok] * ny + iy[ok])
                    ZN.append(Q[ok, 2] - g[ok])
                    ZX.append(Q[ok, 2] + g[ok])
        fl, zn, zx = np.concatenate(FL), np.concatenate(ZN), np.concatenate(ZX)
        o = np.argsort(fl, kind="stable")
        fl, zn, zx = fl[o], zn[o], zx[o]
        u, ini = np.unique(fl, return_index=True)
        self._lotes.append((u, ini, zn, zx, {}))

    @staticmethod
    def _filtro(a, k: int, fn):
        out = a.copy()
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                if dx * dx + dy * dy > (k + 0.5) ** 2 or (dx == 0 and dy == 0):
                    continue
                sh = np.full_like(a, -np.inf if fn is np.maximum else np.inf)
                xs = slice(max(dx, 0), a.shape[0] + min(dx, 0))
                xd = slice(max(-dx, 0), a.shape[0] + min(-dx, 0))
                ys = slice(max(dy, 0), a.shape[1] + min(dy, 0))
                yd = slice(max(-dy, 0), a.shape[1] + min(-dy, 0))
                sh[xd, yd] = a[xs, ys]
                out = fn(out, sh)
        return out

    def _expandir(self, lote, k: int):
        """As entradas de um lote de cabos espalhadas pela pegada (disco de k células) de quem passa — ordenadas por
        célula, com os inícios dos grupos (guardado por k)."""
        cache = lote[4]
        if k not in cache:
            u, ini, zn, zx = lote[:4]
            cel = np.repeat(u, np.diff(np.append(ini, len(zn))))
            nx, ny = self.forma
            ix, iy = cel // ny, cel % ny
            FL, ZN, ZX = [], [], []
            for dx in range(-k, k + 1):
                for dy in range(-k, k + 1):
                    if dx * dx + dy * dy > (k + 0.5) ** 2:
                        continue
                    jx, jy = ix + dx, iy + dy
                    ok = (jx >= 0) & (jy >= 0) & (jx < nx) & (jy < ny)
                    FL.append(jx[ok] * ny + jy[ok])
                    ZN.append(zn[ok])
                    ZX.append(zx[ok])
            fl, zn2, zx2 = np.concatenate(FL), np.concatenate(ZN), np.concatenate(ZX)
            o = np.argsort(fl, kind="stable")
            fl, zn2, zx2 = fl[o], zn2[o], zx2[o]
            uu, ii = np.unique(fl, return_index=True)
            cache[k] = (uu, ii, np.repeat(uu, np.diff(np.append(ii, len(fl)))), zn2, zx2)
        return cache[k]

    def via(self, r: float, folga: float = 0.0003, rv: float | None = None):
        """(z do eixo, livre) por célula para um cabo de raio r (meia-espessura `rv` na vertical: fitas): assenta nas
        peças de baixo (as que não passam de z_nom + acima) e, dos cabos já desenhados na pegada dele, SOBE por cima dos
        que tocaria até nenhum lhe tocar (os que ficam por cima dele passam-lhe por cima; um que lhe toque e seja alto
        demais para ele passar por cima é parede). Nunca entre duas peças com pouca folga, nem no que se proibiu."""
        rv = r if rv is None else rv
        k = max(1, math.ceil((r + folga) / self.h - 0.25))
        e = rv + folga
        z_c = np.maximum(self.z_nom, self._filtro(self.chao, k, np.maximum) + e)
        teto_p = self._filtro(self.teto, k, np.minimum)
        parede = np.zeros(self.forma, dtype=bool)
        lotes = [self._expandir(lt, k) for lt in self._lotes]
        for _ in range(6):                     # sobe por cima dos cabos que tocaria, até parar
            z_novo = z_c.copy()
            for uu, ii, cel, zn, zx in lotes:
                toca = zn < z_c.flat[cel] + e
                chao_l = np.where(toca & (zx <= self.z_sonda), zx, -np.inf)
                z_novo.flat[uu] = np.maximum(z_novo.flat[uu], np.maximum.reduceat(chao_l, ii) + e)
            if np.allclose(z_novo, z_c, atol=1e-7):
                break
            z_c = z_novo
        for uu, ii, cel, zn, zx in lotes:
            toca = zn < z_c.flat[cel] + e
            alto = np.maximum.reduceat((toca & (zx > self.z_sonda)).astype(np.int8), ii).astype(bool)
            parede.flat[uu] |= alto
        livre = (teto_p >= z_c + e) & ~parede
        fresta = teto_p - self._filtro(self.chao, k, np.maximum)
        livre &= ~(fresta < 2.0 * e + 0.0025)
        if self.proibido.any():
            livre &= ~self._filtro(self.proibido.astype(float), k, np.maximum).astype(bool)
        return z_c, livre

    def rota(self, ini, fim, r: float, folga: float = 0.0003, raio_curva: float = 0.004,
             rv: float | None = None, soltar: float = 0.0, meio_y: float = 0.0, so_ini: bool = False) -> list | None:
        """Pontos 3D de um cabo de raio r de `ini` a `fim` pelas células livres (frente de onda de 8 vizinhos, atalhos em
        linha reta), com a altura do mapa (assenta no que estiver por baixo, passa por cima dos cabos baixos). `soltar`:
        raio à volta das pontas onde as células ficam livres à altura delas (saídas de fichas lado a lado)."""
        if self.sz < 0.0:
            ini = np.asarray(ini, dtype=float) * np.array([1.0, 1.0, -1.0])
            fim = np.asarray(fim, dtype=float) * np.array([1.0, 1.0, -1.0])
        z_c, livre = self.via(r, folga, rv)
        nx, ny = self.forma
        h = self.h
        if meio_y:                    # só deste lado do eixo x do corpo (a mais de |meio_y| do lado de lá)
            gy = self.lo[1] + (np.arange(ny) + 0.5) * h
            livre = livre & ((gy * math.copysign(1.0, meio_y)) >= -abs(meio_y))[None, :]
        if soltar > 0.0:
            gx = self.lo[0] + (np.arange(nx) + 0.5) * h
            gy = self.lo[1] + (np.arange(ny) + 0.5) * h
            for q in ((np.asarray(ini, dtype=float),) if so_ini else (np.asarray(ini, dtype=float),
                                                                       np.asarray(fim, dtype=float))):
                perto = (gx[:, None] - q[0]) ** 2 + (gy[None, :] - q[1]) ** 2 <= soltar * soltar
                livre = livre | perto
                z_c = np.where(perto, float(q[2]), z_c)

        def celula(p):
            i = np.floor((np.asarray(p, dtype=float)[:2] - self.lo) / h).astype(int)
            i = np.clip(i, 0, np.array(self.forma) - 1)
            if livre[tuple(i)]:
                return tuple(i)
            cand = np.argwhere(livre[max(0, i[0] - 8):i[0] + 9, max(0, i[1] - 8):i[1] + 9])
            if not len(cand):
                return None
            cand = cand + np.array([max(0, i[0] - 8), max(0, i[1] - 8)])
            j = int(np.argmin(np.linalg.norm(cand - i, axis=1)))
            return tuple(cand[j])
        a, b = celula(ini), celula(fim)
        if a is None or b is None:
            return None
        dist = np.full(self.forma, -1, dtype=np.int32)
        dist[a] = 0
        frente = np.zeros(self.forma, dtype=bool)
        frente[a] = True
        passo = 0
        while not frente[b] and frente.any() and passo < 4 * (nx + ny):
            passo += 1
            f2 = frente.copy()
            f2[1:] |= frente[:-1]
            f2[:-1] |= frente[1:]
            f3 = f2.copy()
            f3[:, 1:] |= f2[:, :-1]
            f3[:, :-1] |= f2[:, 1:]
            frente = f3 & livre & (dist < 0)
            dist[frente] = passo
        if dist[b] < 0:
            return None
        cam = [b]
        alvo = np.array(a)
        while dist[cam[-1]] > 0:
            x, y = cam[-1]
            dv = dist[x, y] - 1
            viz = [(x + i, y + j) for i in (-1, 0, 1) for j in (-1, 0, 1) if (i or j) and 0 <= x + i < nx
                   and 0 <= y + j < ny and dist[x + i, y + j] == dv]
            cam.append(min(viz, key=lambda q: float(np.linalg.norm(np.array(q) - alvo))))
        cam = cam[::-1]
        C = [self.lo + (np.array(q) + 0.5) * h for q in cam]

        forma_m1 = np.array(self.forma) - 1

        def reta(p, q):
            n = max(2, int(np.linalg.norm(q - p) / (0.4 * h)))
            Q = p[None, :] + (q - p)[None, :] * np.linspace(0.0, 1.0, n)[:, None]
            ij = np.clip(np.floor((Q - self.lo) / h).astype(int), 0, forma_m1)
            return bool(np.all(livre[ij[:, 0], ij[:, 1]]))
        # atalhos: do ponto i, o mais longe visível (procura por saltos que dobram e depois bissecção)
        xy, i = [C[0]], 0
        while i < len(C) - 1:
            passo_j, j_ok = 1, i + 1
            while j_ok + passo_j <= len(C) - 1 and reta(C[i], C[j_ok + passo_j]):
                j_ok += passo_j
                passo_j *= 2
            a_, b_ = j_ok, min(len(C) - 1, j_ok + passo_j)
            while b_ - a_ > 1:
                mid = (a_ + b_) // 2
                if reta(C[i], C[mid]):
                    a_ = mid
                else:
                    b_ = mid
            j = b_ if b_ != j_ok and reta(C[i], C[b_]) else a_
            xy.append(C[j])
            i = j
        ini, fim = np.asarray(ini, dtype=float), np.asarray(fim, dtype=float)
        linha = _reamostrar([np.array([ini[0], ini[1], 0.0]), *[np.array([q[0], q[1], 0.0]) for q in xy],
                             np.array([fim[0], fim[1], 0.0])], 0.001)
        ij = np.clip(np.floor((np.array(linha)[:, :2] - self.lo) / h).astype(int), 0, np.array(self.forma) - 1)
        zs = z_c[ij[:, 0], ij[:, 1]]
        kk = max(2, math.ceil(r / 0.001) + 1)
        zs = np.array([float(np.max(zs[max(0, i - kk):i + kk + 1])) for i in range(len(zs))])
        zs[0], zs[-1] = float(ini[2]), float(fim[2])
        pts = [np.array([q[0], q[1], z]) for q, z in zip(linha, zs, strict=True)]
        suave = _curva(_simplificar(pts, 0.0002), raio_curva)
        # o arredondar das esquinas não pode baixar o cabo para dentro do que passou por cima (nem da altura do mapa
        # nas células por onde a curva passa): sobe-se ao mapa ponto a ponto (fora das pontas)
        S_ = np.asarray(_reamostrar(suave, 0.0008))
        ij = np.clip(np.floor((S_[:, :2] - self.lo) / h).astype(int), 0, np.array(self.forma) - 1)
        zm = z_c[ij[:, 0], ij[:, 1]]
        zm = np.array([float(np.max(zm[max(0, i - kk):i + kk + 1])) for i in range(len(zm))])
        sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(S_[:, :2], axis=0), axis=1))])
        longe = (sl > soltar + 0.0005) & (sl < sl[-1] - soltar - 0.0005)
        S_[:, 2] = np.where(longe, np.maximum(S_[:, 2], zm), S_[:, 2])
        S_[:, 2] *= self.sz
        return _simplificar(list(S_), 0.0001)


def _caixa_malha(cena: _Cena, nome: str, corpo: str = "drone") -> _Caixa | None:
    """Caixa (lo, hi) de um geom de MALHA (pelos triângulos dele, no referencial do corpo)."""
    T = cena.tri.lista(corpo, nome)
    if not len(T):
        return None
    V = T.reshape(-1, 3)
    return _Caixa(corpo, V.min(axis=0), V.max(axis=0))


def _furo_placa(cena: _Cena, z_cima: float, z_baixo: float, lo_xy, hi_xy, r: float, perto) -> np.ndarray | None:
    """Centro (x, y) de um furo/rasgo da placa entre z_baixo e z_cima onde passa um cabo de raio r (5 raios verticais
    livres: o centro e 4 à volta a r + 0,6 mm), o mais perto de `perto`, procurado na janela (lo_xy, hi_xy)."""
    lo = np.array([lo_xy[0], lo_xy[1], z_baixo - 0.002])
    hi = np.array([hi_xy[0], hi_xy[1], z_cima + 0.002])
    sonda = cena.sonda({"drone": np.zeros(3)}, (lo, hi), excluir=_SO_FIOS)
    xs = np.arange(lo_xy[0], hi_xy[0] + 1e-9, 0.001)
    ys = np.arange(lo_xy[1], hi_xy[1] + 1e-9, 0.001)
    G = np.array([[x, y, z_cima + 0.001] for y in ys for x in xs])
    livre = ~np.isfinite(sonda.raios_verticais(G, -1.0, z_cima - z_baixo + 0.002)).reshape(len(ys), len(xs))
    k = max(1, math.ceil((r + 0.0006) / 0.001))
    ok = livre.copy()
    for dj, di in ((k, 0), (-k, 0), (0, k), (0, -k)):
        sh = np.zeros_like(livre)
        sh[max(0, dj):len(ys) + min(0, dj), max(0, di):len(xs) + min(0, di)] = \
            livre[max(0, -dj):len(ys) - max(0, dj), max(0, -di):len(xs) - max(0, di)]
        ok &= sh
    if not ok.any():
        return None
    jj, ii = np.nonzero(ok)
    P = np.column_stack([xs[ii], ys[jj]])
    return P[int(np.argmin(np.linalg.norm(P - np.asarray(perto[:2], dtype=float), axis=1)))]


def _sensores(cena: _Cena) -> None:
    """PMW3901 (por baixo da travessa de PETG) + VL53L1X (por cima dela), na posição do build: saltador de 4 fios
    entre as placas POR FORA da ponta da travessa (os parafusos estão a meio dela) e cabo JST-GH da ficha do PMW3901
    ao FC — por baixo da bateria até à ponta de trás dela, por um furo da placa de baixo (medido), entre as placas e
    pela folga da janela da placa de cima ao lado do computador."""
    m, bat, fc = cena.m, cena.bat, cena.fc
    nome_fc = "el_fc_con_sensores" if cena.ctx.geom_existente("el_fc_con_sensores") is not None else None
    if nome_fc is None and cena.ctx.geom_existente("el_fc_con_gps") is not None:
        nome_fc = "el_fc_con_gps"
    alvo = cena.fc_con(nome_fc or "el_fc_con_sensores")
    nome_fc = nome_fc or cena.nome_ancora("el_fc_con_sensores", "el_fc_h7")
    fluxo = cena.caixa("el_fluxo_pcb")
    tof = cena.caixa("el_tof_pcb")
    if fluxo is None:
        fluxo = cena.baixo
    if fluxo is None or bat is None or alvo is None:
        return
    petg = None
    for g in cena.ctx.spec.geoms:
        nm = g.name or ""
        if nm.startswith("el_v_sens") and nm.endswith("_petg") and g.parent is not None and _visivel(g):
            petg = _caixa_malha(cena, nm, g.parent.name)
            break
    with m.peca("cabo_sensores"):
        r = 0.5 * D_JST * 2.3
        con = cena.caixa("el_fluxo_conector")
        ini = (np.array([float(con.lo[0]) - 0.001, float(con.c[1]), float(con.c[2])]) if con is not None
               else np.array([float(fluxo.lo[0]) + 0.003, float(fluxo.c[1]), float(fluxo.lo[2]) - 0.001]))
        comp = cena.computador
        z_c = float(alvo.c[2])
        lateral = alvo.hi[1] > (fc.hi[1] - 0.001 if fc is not None else alvo.hi[1])
        if lateral:          # ficha de entrada lateral na borda +y do FC
            f_g = np.array([float(alvo.c[0]), float(alvo.hi[1]) + 0.0021, z_c])
            m.caixa("drone", "fios_jst", f_g, np.eye(3), [0.0042, 0.0021, 0.0015])
            toque = np.array([float(alvo.c[0]), float(alvo.hi[1]), z_c])
            entrada = [np.array([f_g[0], f_g[1] + 0.008, z_c + 0.002]), np.array([f_g[0], float(alvo.hi[1]) + 0.0008,
                                                                                   z_c])]
        else:
            f_g = np.array([float(alvo.hi[0]) + 0.0021, float(alvo.c[1]), z_c])
            m.caixa("drone", "fios_jst", f_g, np.eye(3), [0.0021, 0.0042, 0.0015])
            toque = np.array([float(alvo.hi[0]), float(alvo.c[1]), z_c])
            entrada = [np.array([f_g[0] + 0.006, f_g[1], z_c]), f_g + np.array([-0.0013, 0.0, 0.0])]
        z_cima = (float(fc.hi[2]) + 0.0030) if fc is not None else z_c + 0.004
        y_lado = float(np.sign(alvo.c[1]) or 1.0)
        pts = None
        if comp is not None and cena.placa is not None:
            # placa de baixo: a 1.ª coisa por cima do topo da bateria, junto à ponta de trás dela
            x_t = float(bat.lo[0])
            sonda = cena.sonda({"drone": np.zeros(3)}, (np.array([x_t - 0.03, -0.05, float(bat.hi[2])]),
                                                        np.array([x_t + 0.03, 0.05, float(bat.hi[2]) + 0.03])),
                               excluir=_SO_FIOS)
            d_pl = sonda.raio(np.array([x_t + 0.010, 0.0, float(bat.hi[2]) + 0.0005]), EZ, 0.03)
            if d_pl is not None:
                z_pl0 = float(bat.hi[2]) + 0.0005 + d_pl          # face de baixo da placa de baixo
                d_t = sonda.raio(np.array([x_t + 0.010, 0.0, z_pl0 + 0.0001]), EZ, 0.01)
                z_pl1 = z_pl0 + (d_t if d_t is not None else 0.003)   # (o raio sai da placa pela face de cima)
                furo = _furo_placa(cena, z_pl1 + 0.0002, z_pl0 - 0.0002,
                                   (x_t - 0.030, 0.0 if y_lado > 0 else -0.050),
                                   (x_t + 0.004, 0.050 if y_lado > 0 else 0.0), r,
                                   np.array([x_t - 0.008, y_lado * float(bat.hi[1])]))
                if furo is not None:
                    z_e = z_pl1 + r + 0.0003                            # deitado em cima da placa de baixo
                    y_s = float(comp.c[1]) + y_lado * (float(comp.h[1]) + FOLGA_PILHA)
                    x_s = min(float(alvo.c[0]) + 0.004, float(comp.hi[0]) - 0.010)
                    # a subida ao lado da pilha (pela janela da placa de cima): se algo a tapa por cima da janela (no
                    # build acessível a `ponte_fc` sai da pegada da pilha), passa a janela, desvia para fora por baixo
                    # disso e só então sobe (medido com raios verticais)
                    son_v = cena.sonda({"drone": np.zeros(3)},
                                       (np.array([x_s - 0.004, min(y_s, y_s + y_lado * 0.008) - 0.004, z_e]),
                                        np.array([x_s + 0.004, max(y_s, y_s + y_lado * 0.008) + 0.004, z_cima])),
                                       excluir=_SO_FIOS)

                    def sobe(yy, z0, z1):
                        G = np.array([[x_s + ox, yy + oy, z0] for ox in (-r, 0.0, r) for oy in (-r, 0.0, r)])
                        return son_v.raios_verticais(G, 1.0, z1 - z0)
                    desvio = None
                    up0 = sobe(y_s, z_e + r + 0.0006, z_cima - r - 0.0006)
                    if np.any(np.isfinite(up0)):
                        z_j = z_e + r + 0.0006 + float(np.min(up0[np.isfinite(up0)])) - r - 0.0012
                        for dy in np.arange(0.0005, 0.00801, 0.0005):
                            yy = y_s + y_lado * float(dy)
                            if z_j > z_e + 2.0 * r and not np.any(np.isfinite(sobe(yy, z_j, z_cima - r - 0.0006))):
                                desvio = [np.array([x_s, y_s, z_j]), np.array([x_s, yy, z_j]), np.array([x_s, yy, z_cima])]
                                break
                    # da ficha do PMW3901 até por baixo do furo: o caminho livre entre a bateria, as cintas, a
                    # fivela, a travessa e os fios da bateria (procurado numa grelha de 1,5 mm)
                    a_c = ini - np.array([0.004, 0.0, 0.0])
                    b_c = np.array([furo[0], furo[1], z_pl0 - r - 0.0012])
                    # 1) pendurado por baixo da bateria (por baixo das cintas, da fivela e da travessa: raios para
                    #    cima de baixo de tudo) até à esquina de trás do lado do furo; 2) daí ao furo pelo caminho livre
                    P_c = np.array([float(bat.lo[0]) + 0.012, float(furo[1]) - y_lado * 0.006, 0.0])
                    lin = [a_c + (P_c - a_c) * t for t in np.linspace(0.0, 1.0, 24)]
                    z_lo = min(float(bat.lo[2]), float(fluxo.lo[2])) - 0.020
                    zona_h = (np.array([min(a_c[0], P_c[0]) - 0.004, min(a_c[1], P_c[1]) - 0.004, z_lo]),
                              np.array([max(a_c[0], P_c[0]) + 0.004, max(a_c[1], P_c[1]) + 0.004, float(bat.lo[2])]))
                    sonda_h = cena.sonda({"drone": np.zeros(3)}, zona_h, excluir=_SO_FIOS)
                    G = np.array([[q[0] + dy * 0.0, q[1] + dy, z_lo] for q in lin for dy in (-r, 0.0, r)])
                    up = sonda_h.raios_verticais(G, 1.0, float(bat.lo[2]) - z_lo + 0.001)
                    z_h = float(np.min(np.where(np.isfinite(up), z_lo + up, float(bat.lo[2])))) - r - 0.0008
                    P_c[2] = z_h
                    lo_c = np.array([float(furo[0]) - 0.012, min(P_c[1], b_c[1]) - 0.014, z_h - 0.006])
                    hi_c = np.array([P_c[0] + 0.012, max(P_c[1], b_c[1]) + 0.014, z_pl0 - 0.0001])
                    cam = _caminho_livre(cena, "drone", lo_c, hi_c, P_c, b_c, r, h=0.002)
                    if cam is not None:
                        cam = [a_c, np.array([a_c[0] - 0.004, a_c[1], z_h]), *cam]
                        # deitado na placa de baixo, por cima dos fios que lá estão (os 14 AWG dos braços de trás)
                        na_placa = _assentar(cena, [np.array([furo[0] + 0.006, furo[1], z_e]),
                                                    np.array([float(comp.lo[0]) - 0.004, y_s, z_e]),
                                                    np.array([x_s, y_s, z_e])], r)
                        pts = [ini, *cam, np.array([furo[0], furo[1], z_e + 0.002]), *na_placa,
                               *(desvio or [np.array([x_s, y_s, z_cima])]),
                               np.array([entrada[0][0], entrada[0][1] + 0.004, z_cima]), *entrada]
        if pts is None:          # sem furo medido: ao lado da bateria e da pilha (como dantes)
            y_sobe = float(bat.hi[1]) + r + 0.0018
            if comp is not None:
                y_sobe = max(y_sobe, float(comp.hi[1]) + FOLGA_PILHA)
            x_sobe = float(comp.c[0]) + 0.012 if comp is not None else float(fluxo.c[0])
            z_fundo = min(float(fluxo.lo[2]), float(ini[2])) - 0.003
            pts = [ini, ini - np.array([0.005, 0.0, 0.0]), np.array([ini[0] - 0.008, ini[1], z_fundo]),
                   np.array([ini[0] - 0.008, float(bat.hi[1]) - 0.004, z_fundo]),
                   np.array([x_sobe, y_sobe, float(bat.lo[2]) + 0.004]), np.array([x_sobe, y_sobe, z_cima]),
                   np.array([entrada[0][0], entrada[0][1] + 0.004, z_cima]), *entrada]
        m.tubo("drone", "fios_preto", _curva(pts, 0.006), 2.0 * r)
        nome_ini = cena.nome_ancora("el_fluxo_conector", "sensores_baixo")
        p_ini = (np.array([float(con.lo[0]), float(con.c[1]), float(con.c[2])]) if con is not None else ini)
        cena.ligar("sensores", nome_ini, nome_fc, "drone", p_ini, "drone", toque, "4 × 28 AWG (JST-GH)", "cabo_sensores")
        if tof is not None and fluxo is not cena.baixo:
            # saltador: dos furos da fila de pinos do VL53L1X (por cima) à borda −x do PMW3901 (por baixo), pela ponta
            # da travessa (x < a ponta dela), longe da ficha JST e dos parafusos
            x_fora = min(float(tof.lo[0]), float(fluxo.lo[0]), float(petg.lo[0]) if petg is not None else 1.0) - 0.0013
            y_p = float(tof.hi[1]) - 0.0013                     # a fila de pinos ao longo da borda de cima
            y_f = float(fluxo.lo[1]) + 0.0035
            z_t = float(tof.hi[2]) + 0.5 * D_JST - 0.0001
            z_f = float(fluxo.lo[2]) - 0.5 * D_JST + 0.0001
            z_t += 0.0002
            z_top_p = (float(petg.hi[2]) if petg is not None and float(petg.hi[2]) < z_t else float(tof.lo[2]))
            z_top_p = min(z_top_p, float(tof.lo[2]))
            for j, mat in enumerate(("fios_preto", "fios_vermelho", "fios_azul", "fios_amarelo")):
                x_p = float(tof.lo[0]) + 0.0015 + j * 0.00254
                a = np.array([x_p, y_p, z_t])
                b = np.array([float(fluxo.lo[0]) + 0.0018, y_f + j * 0.0011, z_f - 0.0001])
                x_j = x_fora - (3 - j) * 0.0011
                pts = [a, np.array([float(tof.lo[0]) - 0.0004, y_p - j * 0.0011, z_t]),
                       np.array([x_j, y_p - j * 0.0011, z_top_p + 0.5 * D_JST + 0.0002]),
                       np.array([x_j - 0.0006, 0.5 * (y_p + y_f), 0.5 * (z_t + z_f)]),
                       np.array([x_j, b[1], float(fluxo.lo[2]) - 0.5 * D_JST - 0.0002]),
                       np.array([float(fluxo.lo[0]) - 0.0004, b[1], b[2]]), b]
                m.tubo("drone", mat, _curva(pts, 0.003), D_JST, lados=6)
            cena.ligar("sensores_saltador", "el_tof_pcb", "el_fluxo_pcb", "drone",
                       np.array([float(tof.lo[0]) + 0.0015, y_p, float(tof.hi[2])]), "drone",
                       np.array([float(fluxo.lo[0]) + 0.0018, y_f, float(fluxo.lo[2])]), "4 × 28 AWG",
                       "cabo_sensores")


def _amostras_cabos(cena: _Cena, corpo: str = "drone") -> tuple[np.ndarray, np.ndarray]:
    """Os cabos já desenhados num corpo, amostrados de 1 em 1 mm: (pontos (n, 3), raios (n,))."""
    P, Rr = [], []
    for c in cena.m.cabos:
        if c["corpo"] != corpo or len(c["pts"]) < 2:
            continue
        Q = np.asarray(_reamostrar([np.asarray(q, dtype=float) for q in c["pts"]], 0.001))
        P.append(Q)
        Rr.append(np.full(len(Q), float(c["r"])))
    if not P:
        return np.zeros((0, 3)), np.zeros(0)
    return np.concatenate(P), np.concatenate(Rr)


def _livre_laje(sonda: _Sonda, cabos, lo, hi, folga_cabo: float = 0.0004, passo: float = 0.002) -> bool:
    """A laje (caixa lo–hi, fina em z) está livre de peças (raios verticais e horizontais por dentro dela) e dos cabos
    (`cabos` = `_amostras_cabos`: nenhum a menos de r + folga da caixa)?"""
    lo, hi = np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)
    Pc, Rc = cabos
    if len(Pc):
        perto = np.all(Pc >= lo - (Rc + folga_cabo)[:, None], axis=1) & np.all(Pc <= hi + (Rc + folga_cabo)[:, None],
                                                                              axis=1)
        if np.any(perto):
            return False
    xs = np.arange(lo[0], hi[0] + 1e-9, passo)
    ys = np.arange(lo[1], hi[1] + 1e-9, passo)
    if not len(xs) or not len(ys):
        return True
    P = np.array([[x, y, hi[2]] for x in xs for y in ys])
    if np.any(np.isfinite(sonda.raios(P, np.repeat([[0.0, 0.0, -1.0]], len(P), axis=0), float(hi[2] - lo[2]),
                                      _lotes=64))):
        return False
    for zz in (lo[2], hi[2]):
        Px = np.array([[lo[0], y, zz] for y in ys])
        if np.any(np.isfinite(sonda.raios(Px, np.repeat([[1.0, 0.0, 0.0]], len(Px), axis=0), float(hi[0] - lo[0]),
                                          _lotes=32))):
            return False
        Py = np.array([[x, lo[1], zz] for x in xs])
        if np.any(np.isfinite(sonda.raios(Py, np.repeat([[0.0, 1.0, 0.0]], len(Py), axis=0), float(hi[1] - lo[1]),
                                          _lotes=32))):
            return False
    return True


def _direcoes_largura(pts, w0) -> np.ndarray:
    """Direção da largura de uma fita que corre em curvas NO PLANO horizontal e dobra à volta de eixos horizontais:
    horizontal e ⟂ à tangente (nas subidas mantém a anterior), sem trocar de sinal."""
    wd, ant = [], np.asarray(w0, dtype=float)
    for i in range(len(pts)):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        t = b - a
        th = np.array([t[0], t[1], 0.0])
        if float(np.linalg.norm(th)) > 0.25 * max(float(np.linalg.norm(t)), 1e-12):
            v = _u(np.cross(EZ, th))
            if float(v @ ant) < 0.0:
                v = -v
        else:
            v = ant
        wd.append(v)
        ant = v
    return np.array(wd)


def _rota_fpc(cena: _Cena, con_cam: _Caixa, con: _Caixa, trava) -> tuple | None:
    """Percurso MEDIDO do FPC da câmara (sem atravessar nada) — ou None se alguma medida falha (fica o percurso antigo):

    1. sai por baixo da TRAVA do conector da câmara (a parte metida no conector não se desenha) e desce à frente da borda
       da placa de baixo; 16 mm nos primeiros 4 mm, estreita para 11,5 mm (o adaptador 15 → 22 vias);
    2. por baixo da placa de baixo POR BAIXO do que pende dela (as porcas do suporte da câmara deixam 10,5 mm entre si:
       o FPC não passa entre elas) e à frente/ao lado da bateria (que encosta à placa), com curvas no plano, até ao
       RASGO medido da placa de baixo (o maior disco livre perto do sítio de sempre);
    3. sobe pelo rasgo e corre entre as placas rente à face de baixo da placa de cima, por fora das subidas dos cabos
       (y medido), vira para +y e entra na janela por cima dos conectores MIPI do Pi;
    4. DOBRA a 45° por cima do `el_rpi5_cam_disp0` (a dobra rente ao conector, ao nível dele, não cabe: o pilar de latão e
       o `el_rpi5_ffc_disp1` estão logo a seguir) e desce num laço em U até entrar no conector ao longo de −x.
    Devolve ([(pontos, larguras, direções da largura), …] — um troço por cada lado da dobra —, ponto de ligação na
    câmara)."""
    rpi, placa = cena.rpi, cena.placa
    e, w_c, w = FPC_ESP, FPC_LARG_CAM, FPC_LARG_RPI
    x_c, y_c = float(con_cam.c[0]), float(con_cam.c[1])
    y_con = float(con.c[1])
    if y_con >= float(rpi.c[1]):
        return None                                   # (o conector do Pi fica do lado −y em todos os builds de hoje)
    x_tr = float(trava.hi[0]) if trava is not None else float(con.hi[0]) + 0.001
    z_pb, z_pt = float(placa.lo[2]), float(placa.hi[2])
    zona = (np.array([float(rpi.lo[0]) - 0.02, -0.075, z_pb - 0.03]),
            np.array([x_c + 0.01, 0.03, float(rpi.hi[2]) + 0.01]))
    sonda = cena.sonda({"drone": np.zeros(3)}, zona, excluir=_SO_FIOS)
    cabos = _amostras_cabos(cena)
    # --- 1. a trava por baixo do conector e a borda da placa
    d_up = sonda.raio(np.array([x_c, y_c, z_pb - 0.012]), EZ, 0.05)
    if d_up is None:
        return None
    z_lat = z_pb - 0.012 + d_up
    if z_lat < z_pt - 0.0005 or z_lat > float(con_cam.hi[2]):
        return None                                   # por baixo do conector há placa: não é este desenho
    for dy in (-0.5 * w_c + 0.0005, 0.0, 0.5 * w_c - 0.0005):
        if sonda.raio(np.array([x_c - 0.5 * e - 0.0002, y_c + dy, 0.5 * (z_pb + z_pt)]), [-1.0, 0.0, 0.0],
                      0.0006) is not None:
            return None
    # --- 2. o rasgo: grelha de 1 mm (raios verticais só contra a placa) → o maior disco livre
    pl = cena.sonda({"drone": np.zeros(3)}, (np.array([x_c - 0.07, -0.08, z_pb - 0.001]),
                                             np.array([x_c, 0.0, z_pt + 0.001])), excluir=_SO_FIOS,
                    incluir=re.compile(r"^(est_|placa)"))
    gx = np.arange(max(x_c - 0.060, float(placa.lo[0]) + 0.008), min(x_c - 0.010, float(placa.hi[0]) - 0.008), 0.001)
    gy = np.arange(max(-0.060, float(placa.lo[1]) + 0.008), -0.012, 0.001)
    if not len(gx) or not len(gy):
        return None
    G = np.array([[a, b, z_pt + 0.0005] for a in gx for b in gy])
    aberto = ~np.isfinite(pl.raios(G, np.repeat([[0.0, 0.0, -1.0]], len(G), axis=0), (z_pt - z_pb) + 0.001,
                                   _lotes=128))
    if not np.any(aberto) or np.all(aberto):
        return None
    A, F = G[aberto][:, :2], G[~aberto][:, :2]
    r_in = np.array([float(np.min(np.linalg.norm(F - q, axis=1))) for q in A]) - 0.0005
    alvo = np.array([float(cena.cam.lo[0]) - 0.022 if cena.cam is not None else x_c - 0.025, -0.030])
    nota = r_in - 0.05 * np.linalg.norm(A - alvo, axis=1)
    j = int(np.argmax(nota))
    if r_in[j] < 0.5 * w + 0.00015:
        return None
    x_s, y_s = float(A[j][0]), float(A[j][1])
    # --- profundidade por baixo da placa: abaixo do que pende dela (porcas, pontas dos parafusos) na zona do percurso
    xs_r = np.arange(x_s, x_c + 1e-9, 0.002)
    ys_r = np.arange(y_s - 0.5 * w - 0.001, y_c + 0.5 * w_c + 0.001, 0.002)
    P = np.array([[xx, yy, z_pb - 0.012] for xx in xs_r for yy in ys_r])
    U = np.repeat([[0.0, 0.0, 1.0]], len(P), axis=0)
    _BAT = re.compile(r"^(el_v_bat|bateria|cinta)", re.IGNORECASE)

    def caixas_bateria(modo, z_d):
        """modo 0: as caixas INTEIRAS das malhas visíveis do corpo do pack (invólucro, células) e das cintas, e a do
        geom `bateria`; modo 1: por malha visível da bateria (todas, também as pretas/vermelhas dos fios do pack) a
        caixa só dos triângulos DENTRO da zona do percurso (os fios do pack que vão ao XT90 não contam) — o `bateria`
        com massa só se se vê."""
        out = []
        if modo == 1:
            gr = cena.tri.de("drone")
            if gr is None:
                return out
            lo_z = np.array([x_s - 0.01, y_s - 0.5 * w - 0.002, z_d - 0.5 * e - 0.002])
            hi_z = np.array([x_c + 0.01, y_c + 0.5 * w_c + 0.002, z_pb + 0.0005])
            aceita = np.array([bool(_BAT.search(nm)) for nm in gr.nomes], dtype=bool)
            idx = gr.indices(lo_z, hi_z, aceita)
            for dono in np.unique(gr.dono[idx]) if len(idx) else ():
                V = np.clip(gr.T[idx[gr.dono[idx] == dono]].reshape(-1, 3), lo_z, hi_z)
                out.append(_Caixa("drone", V.min(axis=0), V.max(axis=0)))
            g_b = cena.ctx.geom_existente("bateria")
            if g_b is not None and _visivel(g_b) and cena.caixa("bateria") is not None:
                out.append(cena.caixa("bateria"))
            return out
        for g in cena.ctx.spec.geoms:
            nm = g.name or ""
            # (só o CORPO do pack — invólucro, células — e as cintas: as malhas fundidas dos fios do pack (preto,
            # vermelho, branco) vão até ao XT90 e ao balanceador e a caixa delas cobriria meia placa)
            corpo_pack = re.match(r"^el_v_bat", nm) and re.search(r"(_bat_pvc|_bat_kapton|_cel_)", nm)
            if (g.parent is not None and g.parent.name == "drone" and (corpo_pack or re.match(r"^(bateria|cinta)", nm))
                    and int(g.type) == int(_G.mjGEOM_MESH) and _visivel(g)):
                cx = _caixa_malha(cena, nm, "drone")
                if cx is not None:
                    out.append(cx)
            elif nm in ("bateria",):
                cx = cena.caixa(nm)
                if cx is not None:
                    out.append(cx)
        return out

    def por_baixo(modo):
        """(z_d, x_v, R) do troço por baixo da placa — ou None. Modo 0 = o desenho de sempre; modo 1 (quando o 0
        falha): a BATERIA fica fora dos raios (um raio que nasce dentro do pack dava o «fundo» pelas faces de dentro
        dele, ~11 mm abaixo da placa) e conta pelas caixas locais das malhas VISÍVEIS dela; folgas de 0,5/0,3 mm (em vez
        de 1/0,5) e curvas no plano de 7 ou 6 mm (≥ meia largura: a borda de dentro não dobra)."""
        son = sonda if modo == 0 else sonda_sb
        dd = son.raios(P, U, 0.0125, _lotes=64)
        pende = np.isfinite(dd) & (z_pb - 0.012 + dd < z_pb - 0.0002)
        fundo = (z_pb - 0.012 + float(np.min(dd[pende]))) if np.any(pende) else z_pb
        z_d = min(z_pb, fundo) - 0.5 * e - 0.0003
        # colunas bloqueadas: algo cruza a laje do FPC (a bateria, que vem de baixo até à placa)
        bloq = []
        for (xx, yy, _z), t in zip(P, dd, strict=True):
            if np.isfinite(t) and z_pb - 0.012 + t < z_d - 0.5 * e - 0.0002:
                bloq.append((float(xx), float(yy)))
        # e a BATERIA do build (as malhas VISÍVEIS: as variantes inativas da troca ao vivo têm alfa 0 e não contam),
        # pelas caixas delas: um raio que nasce dentro de um bloco não o vê
        caixas_b = caixas_bateria(modo, z_d)
        mg, dil = (0.001, 0.0005) if modo == 0 else (0.0005, 0.0003)
        retangulos = []                  # modo 1: as caixas contam EXATAS (a grelha de 2 mm deixava passar até ~1,7 mm)
        for cx in caixas_b:
            if float(cx.hi[2]) < z_d - 0.5 * e - 0.0003 or float(cx.lo[2]) > z_pb:
                continue
            if modo == 1:
                retangulos.append((float(cx.lo[0]) - dil, float(cx.hi[0]) + dil, float(cx.lo[1]) - dil,
                                   float(cx.hi[1]) + dil))
                continue
            for xx in xs_r:
                for yy in ys_r:
                    if cx.lo[0] - dil <= xx <= cx.hi[0] + dil and cx.lo[1] - dil <= yy <= cx.hi[1] + dil:
                        bloq.append((float(xx), float(yy)))
        B = np.array(bloq) if bloq else np.zeros((0, 2))
        # a subida pelo rasgo (da profundidade z_d à placa) também tem de estar fora das baterias
        for cx in caixas_b:
            if (cx.lo[0] - dil <= x_s <= cx.hi[0] + dil and cx.lo[1] - 0.5 * w - dil <= y_s
                    <= cx.hi[1] + 0.5 * w + dil and float(cx.hi[2]) > z_d - 0.5 * e and float(cx.lo[2]) < z_pb):
                return None

        def livre_banda(x0, x1, y0, y1):
            if any(a0 < x1 and x0 < a1 and b0 < y1 and y0 < b1 for a0, a1, b0, b1 in retangulos):
                return False
            return not len(B) or not np.any((B[:, 0] >= x0) & (B[:, 0] <= x1) & (B[:, 1] >= y0) & (B[:, 1] <= y1))
        for R in ((0.007,) if modo == 0 else (0.007, 0.006)):
            m2 = 2.0 * mg
            for xv in np.arange(x_s + R + m2, x_c - R - m2, 0.0005):
                if (livre_banda(xv - 0.5 * w - mg, xv + 0.5 * w + mg, y_s, y_c)
                        and livre_banda(x_s - mg, xv, y_s - 0.5 * w - mg, y_s + 0.5 * w + mg)
                        and livre_banda(xv, x_c, y_c - 0.5 * w_c - mg, y_c + 0.5 * w_c + mg)):
                    return z_d, float(xv), R
        return None

    res = por_baixo(0)
    if res is None:
        sonda_sb = cena.sonda({"drone": np.zeros(3)}, zona,
                              excluir=re.compile(r"^(fios_|helice|caminho_tiro|projetil|el_v_bat|bateria|cinta)",
                                                 re.IGNORECASE))
        res = por_baixo(1)
    if res is None:
        return None
    z_d, x_v, R = res
    # --- 3. entre as placas: a face de baixo da placa de cima por cima do rasgo
    d_t = sonda.raio(np.array([x_s, y_s, z_pt + 0.001]), EZ, 0.05)
    if d_t is None:
        return None
    z_r = z_pt + 0.001 + d_t - 0.5 * e - 0.00025
    if z_r - z_pt < 0.003:
        return None
    # --- 4. no Pi: o troço de baixo por cima das travas, o laço antes do pilar / ffc_disp1, e a dobra por cima
    z_con = float(con.c[2])
    xs_b = np.arange(x_tr - 0.0005, x_tr + 0.012, 0.001)
    ys_b = np.arange(y_con - 0.5 * w, y_con + 0.5 * w + 1e-9, 0.0015)
    Pb = np.array([[xx, yy, z_r] for xx in xs_b for yy in ys_b])
    db = sonda.raios(Pb, np.repeat([[0.0, 0.0, -1.0]], len(Pb), axis=0), z_r - z_con + 0.003, _lotes=64)
    if not np.any(np.isfinite(db)):
        return None
    z_low = z_r - float(np.min(db)) + 0.5 * e + 0.00025
    z_dob = z_r + e                                   # o troço de cima da dobra assenta no de baixo
    if z_dob - z_low < 0.0016:
        return None
    rho = 0.5 * (z_dob - z_low)
    Pu = np.array([[x_tr + 0.0012, float(yy), float(zz)] for yy in ys_b
                   for zz in np.linspace(z_low - 0.5 * e, z_dob + 0.5 * e, 4)])
    du = sonda.raios(Pu, np.repeat([[1.0, 0.0, 0.0]], len(Pu), axis=0), 0.02, _lotes=32)
    dmin = float(np.min(du)) if np.any(np.isfinite(du)) else 0.012
    x_U = x_tr + 0.0012 + dmin - 0.5 * e - 0.00045
    x_dob = x_U - rho - 0.5 * w - 0.0002              # a dobra: o quadrado de 11,5 mm acaba onde o laço começa
    if x_dob - 0.5 * w < x_tr - 0.012:
        return None
    # x da dobra: o maior que deixa a dobra e o troço +y livres (cabos e peças)
    x_v2 = None
    for xv2 in np.arange(x_dob, x_dob - 0.012, -0.0005):
        lo_b = np.array([xv2 - 0.5 * w - 0.0003, float(rpi.lo[1]) - 0.004, z_r - 0.5 * e - 0.0003])
        hi_b = np.array([xv2 + 0.5 * w + 0.0003, y_con + 0.5 * w, z_dob + 0.5 * e + 0.0002])
        if _livre_laje(sonda, cabos, lo_b, hi_b):
            x_v2 = float(xv2)
            break
    if x_v2 is None:
        return None
    # y do troço entre as placas: o 1.º (a partir do Pi, para fora) livre ao longo de todo o troço
    y_run = None
    for yr in np.arange(min(y_s, float(rpi.lo[1]) - 0.5 * w - 0.003), y_s - 0.035, -0.001):
        lo_r = np.array([x_v2 - 0.5 * w, float(yr) - 0.5 * w - 0.0004, z_r - 0.5 * e - 0.0003])
        hi_r = np.array([x_s - 0.006, float(yr) + 0.5 * w + 0.0004, z_r + 0.5 * e + 0.0001])
        if _livre_laje(sonda, cabos, lo_r, hi_r):
            y_run = float(yr)
            break
    if y_run is None:
        return None

    def planar(pts, z, raio):
        return [np.array([q[0], q[1], z]) for q in _curva([np.array([a, b, z]) for a, b in pts], raio, n=10)]
    rho1 = 0.0015
    # (1) câmara: da trava para baixo e a dobra para −x
    pts = [np.array([x_c, y_c, z_lat - 0.0002]), np.array([x_c, y_c, z_d + rho1])]
    pts += [np.array([x_c - rho1 * (1.0 - math.cos(t)), y_c, z_d + rho1 * (1.0 - math.sin(t))])
            for t in np.linspace(0.0, 0.5 * math.pi, 7)[1:]]
    # (2) por baixo da placa até ao rasgo, (3) sobe por ele e dobra para −x por baixo da placa de cima
    pts += planar([(x_c - rho1, y_c), (x_v, y_c), (x_v, y_s), (x_s + rho1, y_s)], z_d, R)[1:]
    pts += [np.array([x_s + rho1 * math.cos(t), y_s, z_d + rho1 * math.sin(t)])
            for t in np.linspace(0.0, 0.5 * math.pi, 7)[1:]]
    pts.append(np.array([x_s, y_s, z_r - rho1]))
    pts += [np.array([x_s - rho1 * (1.0 - math.cos(t)), y_s, z_r - rho1 * (1.0 - math.sin(t))])
            for t in np.linspace(0.0, 0.5 * math.pi, 7)[1:]]
    x_a = x_s - rho1 - 0.004
    pts += planar([(x_s - rho1, y_s), (x_a, y_s), (x_a - 0.014, y_run), (x_v2, y_run), (x_v2, y_con + 0.5 * w)],
                  z_r, R)[1:]
    pts = _sem_repetidos(pts)
    comp = np.concatenate([[0.0], np.cumsum([np.linalg.norm(b - a) for a, b in itertools.pairwise(pts)])])
    larg = [w_c if c <= 0.004 else max(w, w_c - (w_c - w) * (c - 0.004) / 0.006) for c in comp]
    troco_a = (pts, larg, _direcoes_largura(pts, [0.0, -1.0, 0.0]))
    # (4) depois da dobra a 45°: para +x por cima do troço de baixo, laço em U e entra no conector
    pb = [np.array([x_v2 - 0.5 * w, y_con, z_dob]), np.array([x_U - rho, y_con, z_dob])]
    pb += [np.array([x_U - rho + rho * math.sin(t), y_con, z_low + rho + rho * math.cos(t)])
           for t in np.linspace(0.0, math.pi, 12)[1:]]
    pb += [np.array([x_tr + 0.0005, y_con, z_low]), np.array([float(con.c[0]), y_con, z_con])]
    pb = _sem_repetidos(pb)
    troco_b = (pb, [w] * len(pb), np.repeat([[0.0, 1.0, 0.0]], len(pb), axis=0))
    return [troco_a, troco_b], np.array([x_c, y_c, float(con_cam.lo[2])])


def _fpc_camera(cena: _Cena) -> None:
    """FPC da Camera Module 3 (15 vias, 16 mm) ao `el_rpi5_cam_disp0` (22 vias, 11,5 mm) — ver o docstring do módulo."""
    if not cena.cam_csi or cena.cam is None or cena.rpi is None or cena.placa is None:
        return
    m, cam, rpi, placa = cena.m, cena.cam, cena.rpi, cena.placa
    con_cam = cena.ancora("el_cam_conector_fpc",
                          lambda: _Caixa("drone", np.array([cam.lo[0] + 0.002, cam.c[1] - 0.0104, cam.lo[2]]),
                                         np.array([cam.lo[0] + 0.0045, cam.c[1] + 0.0104, cam.lo[2] + 0.005])))
    con = cena.rpi_peca("el_rpi5_cam_disp0")
    trava = cena.rpi_peca("el_rpi5_cam_disp0_trava")
    if con_cam is None or con is None:
        return
    rota = None
    try:
        rota = _rota_fpc(cena, con_cam, con, trava)
    except Exception as erro:  # noqa: BLE001 — sem a medida, fica o percurso antigo
        warnings.warn(f"detalhes/fios: FPC medido falhou ({type(erro).__name__}: {erro})", stacklevel=2)
    if rota is not None:
        trocos, p_lig = rota
        with m.peca("fpc_camera"):
            for pts_f, larg_f, wd_f in trocos:
                m.fita("drone", "fios_fpc", pts_f, larg_f, wd_f, FPC_ESP)
        cena.ligar("fpc_camera", cena.nome_ancora("el_cam_conector_fpc", "camera"),
                   cena.nome_ancora("el_rpi5_cam_disp0", "el_rpi5"), "drone", p_lig, "drone",
                   np.array([float(con.c[0]), float(con.c[1]), float(con.c[2])]), "FPC 15 vias 1 mm → 22 vias 0,5 mm",
                   "fpc_camera")
        return
    if float(placa.h[0]) >= 0.06:
        warnings.warn("detalhes/fios: FPC pelo percurso antigo (sem rasgo/folgas medidas neste build)", stacklevel=2)
    e = FPC_ESP
    z_top, z_bot = float(placa.hi[2]), float(placa.lo[2])
    x_c, y_c = float(con_cam.c[0]), float(con_cam.c[1])
    w = FPC_LARG_RPI
    x_tr = float(trava.hi[0]) if trava is not None else float(con.hi[0]) + 0.001
    z_con = float(con.c[2])
    z_lay = float(rpi.lo[2]) + 0.0042 + 0.5 * e          # por cima dos 2 conectores MIPI e das travas
    y_con = float(con.c[1])
    x_d = x_tr + 0.5 * w + 0.0015                         # centro da dobra à frente da trava
    y_borda = float(rpi.lo[1])
    y_fora = y_borda - 0.0125
    x_rasgo = float(cam.lo[0]) - 0.022
    zb = z_bot - 0.0006 - 0.5 * e
    zt = z_top + 0.0004 + 0.5 * e
    with m.peca("fpc_camera"):
        # (1) do conector da câmara para baixo (à frente da borda da placa) e por baixo da placa até ao rasgo
        pts1 = [np.array([x_c, y_c, float(con_cam.lo[2]) + 0.0025]), np.array([x_c, y_c, zb - 0.002]),
                np.array([x_c - 0.008, y_c, zb]), np.array([x_rasgo + 0.012, y_c, zb]),
                np.array([x_rasgo + 0.004, 0.5 * (y_c + y_fora), zb]), np.array([x_rasgo, y_fora, zb])]
        m.fita("drone", "fios_fpc", _curva(pts1, 0.004, n=4), FPC_LARG_CAM, [0.0, 1.0, 0.0], e)
        # (2) sobe pelo rasgo e corre na placa (largura em y; estreita para 11,5 mm) até à 1.ª dobra
        pts2 = _curva([np.array([x_rasgo, y_fora, zb]), np.array([x_rasgo, y_fora, zt]),
                       np.array([x_rasgo - 0.008, y_fora, zt]), np.array([x_d + 0.5 * w, y_fora, zt])], 0.003, n=4)
        comp = np.concatenate([[0.0], np.cumsum([np.linalg.norm(b - a) for a, b in itertools.pairwise(pts2)])])
        larg = [FPC_LARG_CAM + (w - FPC_LARG_CAM) * min(1.0, max(0.0, (c - 0.5 * comp[-1]) / (0.35 * comp[-1])))
                for c in comp]
        m.fita("drone", "fios_fpc", pts2, larg, [0.0, 1.0, 0.0], e)
        # (3) 1.ª dobra (45°): corre em +y (largura em x), sobe à borda −y da RPi e assenta por cima dos conectores
        pts3 = [np.array([x_d, y_fora - 0.5 * w, zt + e]), np.array([x_d, y_borda - 0.006, zt + e]),
                np.array([x_d, y_borda - 0.0008, z_lay]), np.array([x_d, y_con + 0.5 * w, z_lay])]
        m.fita("drone", "fios_fpc", _curva(pts3, 0.003, n=4), w, [1.0, 0.0, 0.0], e)
        # (4) 2.ª dobra (45°) à frente da trava: entra no conector ao longo de −x (largura em y) até ao centro dele
        pts4 = [np.array([x_d + 0.5 * w, y_con, z_lay + e]), np.array([x_tr + 0.0005, y_con, z_lay + e]),
                np.array([float(con.c[0]), y_con, z_con])]
        m.fita("drone", "fios_fpc", pts4, w, [0.0, 1.0, 0.0], e)
    cena.ligar("fpc_camera", cena.nome_ancora("el_cam_conector_fpc", "camera"),
               cena.nome_ancora("el_rpi5_cam_disp0", "el_rpi5"), "drone", pts1[0], "drone",
               np.array([float(con.c[0]), y_con, z_con]), "FPC 15 vias 1 mm → 22 vias 0,5 mm", "fpc_camera")


def _fonte_e_barramento(cena: _Cena) -> None:
    """Articulado: 18 AWG das ilhas da bateria à entrada do regulador de 24 V; cabos X4P da saída do regulador a cada
    servo do ombro (em estrela: sobem pela folga de trás da RPi e seguem deitados na placa de cima)."""
    m, fonte = cena.m, cena.fonte
    if fonte is None or not cena.art:
        return
    # a mesma disposição da eletrónica (bornes de 7 × 10,2 mm nas pontas da placa, z de 1,6 a 11 mm); no build
    # acessível o regulador é o UBEC de 6,8 V dos servos (`el_ubec_entrada/saida`, se a eletrónica os publicar)
    n_ent, n_sai = "el_fonte24_borne_entrada", "el_fonte24_borne_saida"
    if cena.servo_pwm and cena.ponto_ancora("el_ubec_saida") is not None:
        _ubec_acessivel(cena)                 # build acessível: UBEC, bucks, drivers e servos (caminhos procurados)
        return
    ent = cena.ancora(n_ent, lambda: cena.centrada(
        fonte, -1000 * float(fonte.h[0]), -1000 * float(fonte.h[0]) + 7.0, -5.1, 5.1, 1.6, 11.0))
    sai = cena.ancora(n_sai, lambda: cena.centrada(
        fonte, 1000 * float(fonte.h[0]) - 7.0, 1000 * float(fonte.h[0]), -5.1, 5.1, 1.6, 11.0))
    nome_ent = cena.nome_ancora(n_ent, "fonte_servos")
    nome_sai = cena.nome_ancora(n_sai, "fonte_servos")
    z_mesa = (cena.z_sup + 0.0012) if cena.z_sup is not None else cena.z_topo + 0.016
    x_borda = float(cena.placa.lo[0]) if cena.placa is not None else float(fonte.lo[0]) - 0.02
    if ent is not None:
        with m.peca("cabo_fonte24"):
            for j, (polo, mat) in enumerate((("pos", "fios_vermelho"), ("neg", "fios_preto"))):
                alvo = cena.pdb_pad(f"el_pdb_bat_{polo}")
                if alvo is None:
                    continue
                dy = (0.5 - j) * 0.0026
                p0 = np.array([float(ent.lo[0]) + 0.0015, float(ent.c[1]) + dy, float(ent.c[2])])
                sgn_p = 1.0 if float(alvo.c[1]) >= 0.0 else -1.0
                y_f = (float(alvo.hi[1]) - 0.0007) if sgn_p > 0 else (float(alvo.lo[1]) + 0.0007)     # lado de fora
                y_run = y_f + sgn_p * 0.0015
                q = np.array([float(alvo.hi[0]) - 0.0016, y_f, float(alvo.hi[2]) + 0.5 * D_18 - 0.0002])
                z_c = z_mesa + 0.5 * D_18 + 0.0045
                pts = [p0, p0 - np.array([0.006, 0.0, 0.0]),
                       np.array([x_borda - 0.010, p0[1] + 0.012 * (1 - 2 * j), z_c - 0.01]),
                       np.array([x_borda - 0.004, p0[1] + 0.012 * (1 - 2 * j), z_c]),
                       np.array([float(q[0]) - 0.03, y_run, z_c]),
                       np.array([float(q[0]) - 0.012, y_run, float(q[2]) + 0.004]),
                       np.array([float(q[0]) - 0.005, y_run, float(q[2]) + 0.002]), q]
                linha = _curva(pts, 0.008)
                linha = [*_sob_tetos(cena, linha[:-1], 0.5 * D_18, z_c), linha[-1]]
                m.tubo("drone", mat, linha, D_18)
                cena.ligar(f"fonte24_{polo}", cena.nome_ancora(f"el_pdb_bat_{polo}", "el_cablagem"), nome_ent, "drone",
                           _toque_ilha(alvo, q), "drone", p0, "18 AWG", "cabo_fonte24")
    if sai is None or cena.computador is None:
        return
    comp = cena.computador
    if cena.servo_pwm:
        _estrela_servos(cena, sai, nome_sai, z_mesa)
        return
    r = 0.5 * D_DXL
    x_sobe0 = float(comp.lo[0]) - FOLGA_PILHA - 0.0002
    # os da FRENTE sobem mais para fora (y) e vão pela faixa de dentro (x); os de TRÁS sobem mais perto do meio e vão
    # pela faixa de fora — nas subidas e nas faixas nenhum cabo cruza outro
    ys = {1: 0.0108, 3: 0.0075, 2: -0.0075, 4: -0.0108}
    portas = {1: 0.00495, 3: 0.00165, 2: -0.00165, 4: -0.00495}      # 4 saídas da ficha, pela ordem das subidas
    hub_c = np.array([float(sai.hi[0]) + 0.0018, float(sai.c[1]), float(sai.c[2])])
    with m.peca("cabo_dxl", 0):
        m.caixa("drone", "fios_jst", hub_c, np.eye(3), [0.0017, 0.0066, 0.0040])     # ficha de 4 saídas (JST EH)
    for k in range(1, 5):
        so = _servo_conectores(cena, k, "ombro")
        if so is None:
            continue
        with m.peca("cabo_dxl", k):
            c_s, q, dq, nome_s = so[1]
            _ficha_eh(cena, c_s, q, dq)
            sx, sy = cena.sinais[k - 1]
            y_s = float(comp.c[1]) + ys.get(k, 0.0)
            p0 = np.array([float(sai.hi[0]) + 0.0035, float(sai.c[1]) + portas.get(k, 0.0), float(sai.c[2])])
            z_t = z_mesa + r
            alvo = q + 0.0045 * dq
            fora = alvo + 0.024 * dq
            x_sobe = min(x_sobe0, float(p0[0]) + r + 0.0006)
            # faixas na placa de cima, por dentro das pontas dos feixes dos ombros: os da FRENTE viram para a frente a
            # 12 mm da borda do computador; os de TRÁS 4,5 mm mais para fora, seguem para a frente até à vertical da
            # ficha e só aí vão para fora (por dentro dos fios que saem dos feixes, que já vão altos)
            x_faixa = x_sobe - (0.004 if sx > 0 else 0.009)
            y_lado = float(comp.c[1]) + sy * (float(comp.h[1]) + 0.012)
            # sobe na folga de trás do computador: na vertical da sua saída e, desencontrados, os de fora (frente) passam
            # primeiro para o seu y e os de dentro (trás) depois — nunca lado a lado a mudar de y
            z0 = float(p0[2]) + (0.0015 if sx > 0 else 0.0055)
            pts = [p0, p0 + np.array([0.0012, 0.0, 0.0]), np.array([x_sobe, p0[1], z0]),
                   np.array([x_sobe, y_s, z0 + 0.004]), np.array([x_sobe, y_s, max(z0 + 0.0045, z_t + 0.004)]),
                   np.array([x_faixa, y_s, z_t])]
            if sx > 0:
                via = [np.array([x_faixa, y_lado, z_t]), np.array([float(fora[0]) - 0.006, y_lado, z_t]),
                       np.array([fora[0], fora[1], z_t])]
            else:
                y_v = y_lado + sy * 0.0045
                via = [np.array([x_faixa, y_v, z_t]), np.array([float(fora[0]), y_v, z_t]),
                       np.array([fora[0], fora[1], z_t])]
            # deitado na placa: passa POR BAIXO dos cabos que vão mais altos (18 AWG da fonte, bateria)
            deitado = _drapejar(cena, _curva([pts[-1], *via], 0.010), r, acima_cabos=0.0035)
            pts = [*pts[:-1], *deitado, fora + np.array([0, 0, 0.002]), alvo]
            m.tubo("drone", "fios_dxl", _curva(pts, 0.008), D_DXL)
            cena.ligar(f"dxl_ombro{k}", nome_sai, _geom_ficha_servo(cena, c_s, "ombro", k, q) or nome_s, "drone",
                       np.array([float(sai.hi[0]), p0[1], p0[2]]), c_s, q, "Robot Cable-X4P (4 × 21 AWG)", "cabo_dxl", k,
                       ficha_para=nome_s)


def _polos(cx: _Caixa, dirc, sep: float = 0.0035) -> list:
    """Os 2 polos (+, −) de um borne de 2 vias (caixa da âncora, direção por onde o fio sai): ao longo do lado maior da
    face, a ±sep do centro, na face de saída."""
    dirc = _u(dirc)
    h = np.asarray(cx.h, dtype=float).copy()
    h[int(np.argmax(np.abs(dirc)))] = 0.0
    eixo = np.zeros(3)
    eixo[int(np.argmax(h))] = 1.0
    face = cx.c + dirc * float(np.abs(dirc) @ cx.h)
    return [face + sep * eixo, face - sep * eixo]


def _par_encostado(ini, fim, via, d: float, passo: float = 0.0008, pontas: float = 0.0055):
    """Linhas de 2 fios de Ø d ENCOSTADOS de ini[i] a fim[i] (pontas exatas) pela linha central que passa pelos meios
    e por `via`: o afastamento é o do par encostado (d) e só nos `pontas` mm de cada ponta abre/fecha para a distância
    entre os polos; a direção dele (transportada ao longo da linha) roda devagar — o par torce — de ini[1] − ini[0] para
    fim[1] − fim[0] (cada fio chega ao seu polo). Devolve (linha 0, linha 1)."""
    a0, a1 = (np.asarray(x, dtype=float) for x in ini)
    b0, b1 = (np.asarray(x, dtype=float) for x in fim)
    c = np.asarray(_reamostrar([0.5 * (a0 + a1), *[np.asarray(v, dtype=float) for v in via], 0.5 * (b0 + b1)], passo))
    t, nn, bb = _quadros(list(c), n0=a1 - a0)
    t, nn, bb = np.asarray(t), np.asarray(nn), np.asarray(bb)
    e = (b1 - b0) - float(np.dot(b1 - b0, t[-1])) * t[-1]
    ang_fim = math.atan2(float(np.dot(e, bb[-1])), float(np.dot(e, nn[-1])))
    sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))])
    L = max(float(sl[-1]), 1e-9)
    # a torção acaba antes de as pontas abrirem (e começa depois de fecharem)
    f = np.clip((sl - pontas) / max(L - 2.0 * pontas, 1e-6), 0.0, 1.0)
    ang = ang_fim * (3.0 * f * f - 2.0 * f ** 3)
    d_t = d + 0.0002                       # (0,2 mm entre os fios: nas curvas do caminho o de dentro não toca no outro)
    u0 = np.clip(sl / pontas, 0.0, 1.0)
    u1 = np.clip((L - sl) / pontas, 0.0, 1.0)
    sep = d_t + (float(np.linalg.norm(a1 - a0)) - d_t) * (1.0 - u0) ** 2 + (float(np.linalg.norm(b1 - b0)) - d_t) * (1.0 - u1) ** 2
    w = np.cos(ang)[:, None] * nn + np.sin(ang)[:, None] * bb
    q0, q1 = c - 0.5 * sep[:, None] * w, c + 0.5 * sep[:, None] * w
    q0[0], q1[0], q0[-1], q1[-1] = a0, a1, b0, b1
    return list(q0), list(q1)


def _par_mesa(cena: _Cena, mesa, ident: str, pa, pb, qa, qb, d: float, mats, bitola: str, de: str, de_neg: str,
              para: str, peca: str, inst: int, ini=None, fim=None, raio: float = 0.0015, toque_de=None,
              recuo_para=None) -> bool:
    """Par ENCOSTADO (Ø d cada) dos polos (pa +, pb −) aos polos (qa +, qb −) pelo caminho do mapa 2,5D `mesa` entre
    `ini` e `fim` (por omissão os meios dos polos): o par torce devagar ao longo do caminho de modo a cada fio chegar ao
    polo da sua polaridade (`_par_linhas`; o caminho procura-se com folga para os 2 fios um por cima do outro). Regista as
    2 ligações (pontas declaradas em `toque_de`, se dadas) e junta o par ao mapa. Devolve se desenhou."""
    m = cena.m
    pa, pb, qa, qb = (np.asarray(v, dtype=float) for v in (pa, pb, qa, qb))
    A = 0.5 * (pa + pb) if ini is None else np.asarray(ini, dtype=float)
    B = 0.5 * (qa + qb) if fim is None else np.asarray(fim, dtype=float)
    cam = mesa.rota(A, B, d + 0.0001, folga=0.00015, soltar=0.003, rv=d + 0.0002)
    if cam is None:
        return False
    rq = np.zeros(3) if recuo_para is None else np.asarray(recuo_para, dtype=float)
    # (sem o serrilhado da grelha de 1 mm junto às pontas: o par torcia aos saltos e o fio de dentro cruzava o outro)
    meio = [np.asarray(q, dtype=float) for q in cam[1:-1]
            if float(np.linalg.norm(np.asarray(q) - A)) > 1.5 * d and float(np.linalg.norm(np.asarray(q) - B)) > 1.5 * d]
    # a rota cola-se ao que tem por cima (mapa virado) ou por baixo: por baixo de um driver (pinos e dissipador
    # pendurados) e ao sair de baixo da bateria dava degraus de 5–13 mm em menos de 1 mm e o par torcia-se sobre si
    # (até 0,98 mm) — o perfil passa a ser o mais perto dele que fica do lado LIVRE (longe do que o cabo encosta) com
    # inclinação ≤ 45° (medida na horizontal, ao longo do caminho), com os vértices arredondados (média de ±3 mm, sem
    # nunca passar para o lado do que o cabo encosta)
    if len(meio) >= 3:
        Pm = np.array(meio)
        sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pm[:, :2], axis=0), axis=1))])
        zs = Pm[:, 2] * mesa.sz
        zl = np.max(zs[None, :] - np.abs(sl[:, None] - sl[None, :]), axis=1)
        janela = np.abs(sl[:, None] - sl[None, :]) <= 0.003
        zm = (janela * zl[None, :]).sum(axis=1) / janela.sum(axis=1)
        Pm[:, 2] = mesa.sz * np.maximum(zm, zl)               # (zl ≥ zs: nunca do lado do que o cabo encosta)
        meio = list(Pm)
    via = _simplificar([A, *meio, B], 0.0004)
    if fim is not None and float(B[2]) < float(0.5 * (qa[2] + qb[2])) - 0.003:
        # chega por baixo: sobe à frente da face e só então entra (curva de 90°, sem dar a volta ao borne)
        via.append(np.array([float(B[0]), float(B[1]), 0.5 * float(qa[2] + qb[2])]))
    l0, l1 = _par_encostado((pa, pb), (qa + rq, qb + rq), via, d)
    for linha, mat in ((l0, mats[0]), (l1, mats[1])):
        pts = _simplificar(list(linha), 0.0001)
        m.tubo("drone", mat, pts, d)
        mesa.juntar(np.asarray(_reamostrar(pts, 0.001)), 0.5 * d)
    td = toque_de if toque_de is not None else (pa, pb)
    cena.ligar(f"{ident}_pos", de, para, "drone", td[0], "drone", qa, bitola, peca, inst, polo="pos")
    cena.ligar(f"{ident}_neg", de_neg, para, "drone", td[1], "drone", qb, bitola, peca, inst, polo="neg")
    return True


def _alimentacao_atuadores(cena: _Cena) -> None:
    _pico_drvs(cena)                       # os sinais dos drivers (do Pico) primeiro: o 12 V passa à volta deles
    _alimentacao_atuadores_12v(cena)


def _alimentacao_atuadores_12v(cena: _Cena) -> None:
    """Build ACESSÍVEL, por baixo da placa de baixo: um par de 18 AWG soldado por FORA dos copos do XT90 (vermelho no +,
    preto no −) desce por trás do macho, passa por baixo dele, sobe em frente da ficha e divide-se num Y (manga
    termo-retráctil) atrás da bateria — um par para cada buck de 12 V (às ilhas de entrada, por baixo) — e de cada buck
    um par de 20 AWG a cada um dos 2 drivers DRV8871 do seu lado (ao borne da alimentação, pela face dele). Os caminhos
    são os do mapa 2,5D por baixo da placa (`_Mesa` virada): colados à placa, por baixo do que lá está pendurado."""
    copos = _copos_xt90(cena)
    bat, placa = cena.bat, cena.placa
    if copos is None or len(copos) != 2 or bat is None or placa is None:
        return
    m = cena.m
    (_c_p, _d_p, n_p), (_c_n, _d_n, n_n) = copos
    g_p, g_n = cena.caixa(n_p), cena.caixa(n_n)
    mx = cena.caixa("el_xt90_macho") or _caixa_malha(cena, "el_xt90_macho")
    cx_x = cena.caixa("conector_xt90") or _caixa_malha(cena, "conector_xt90")
    if g_p is None or g_n is None or mx is None:
        return
    r18 = 0.5 * D_18
    z_b = float(placa.lo[2]) - r18 - 0.0003            # colado por baixo da placa de baixo
    x_fr = float(cx_x.hi[0] if cx_x is not None else mx.hi[0]) + 0.004
    x_y = 0.5 * (x_fr + float(bat.lo[0]))               # o Y: entre a ficha e a bateria
    z_y = z_b - 0.004
    S = np.array([x_y, 0.0, z_y])
    with m.peca("cabo_atuadores", 0):
        # 1) do copo (por fora) ao Y — cada fio pelo seu lado do macho (por fora dos fios do próprio pack, que vão da
        #    ficha à bateria), sobe à frente da ficha e entra no Y por trás
        meio_y = {}
        for g, mat, sg, nome in ((g_p, "fios_vermelho", 1.0, n_p), (g_n, "fios_preto", -1.0, n_n)):
            y_f = float(g.c[1]) + sg * (float(g.h[1]) + r18 + 0.0001)
            x_c = float(g.c[0])
            p0 = np.array([x_c, y_f, float(g.c[2])])
            toque = np.array([x_c, float(g.c[1]) + sg * float(g.h[1]), float(g.c[2])])
            y_l = sg * (float(mx.hi[1]) + r18 + 0.0003)        # ao lado do macho e da ficha
            y_j = sg * 0.0016
            x_r = x_fr - 0.0019
            pts = [p0, np.array([x_c + 0.003, y_l, float(g.c[2])]), np.array([x_r - 0.004, y_l, float(g.c[2])]),
                   np.array([x_r, y_l, float(g.c[2]) + 0.004]), np.array([x_r, y_l, z_y - 0.004]),
                   np.array([x_r + 0.004, 0.5 * (y_l + y_j), z_y]), S + np.array([-0.0055, y_j, 0.0]),
                   S + np.array([-0.002, y_j, 0.0])]
            m.tubo("drone", mat, _curva(pts, 0.004), D_18)
            meio_y[sg] = (toque, nome)
        m.caixa("drone", "fios_termo", S, np.eye(3), [0.0045, 0.0045, 0.0026])
    # 2) do Y a cada buck e de cada buck aos seus 2 drivers, pelo mapa por baixo da placa
    lo = np.array([float(bat.lo[0]) - 0.020, float(placa.lo[1]) + 0.004])
    hi = np.array([float(bat.hi[0]) + 0.010, float(placa.hi[1]) - 0.004])
    sem_bat = re.compile(r"^(fios_|el_v_bat|bateria|cinta_bateria)", re.IGNORECASE)
    mesa = _Mesa(cena, lo, hi, z_b, acima=0.030, invertido=True, excluir=sem_bat)
    mesa.proibir(bat.lo - 0.0015, bat.hi + 0.0015)

    for n in (1, 2):
        ent = cena.ponto_ancora(f"el_buck12_{n}_borne_entrada")
        sai = cena.ponto_ancora(f"el_buck12_{n}_borne_saida")
        cx_e, cx_s = cena.caixa(f"el_buck12_{n}_borne_entrada"), cena.caixa(f"el_buck12_{n}_borne_saida")
        if ent is None or cx_e is None:
            continue
        sy = 1.0 if float(ent[1][1]) > 0.0 else -1.0
        qa, qb = _polos(cx_e, ent[2])
        if float(qa[1]) * sy < float(qb[1]) * sy:              # o + do lado de fora
            qa, qb = qb, qa
        sep = 0.5 * D_18 + 0.00003
        pa = S + np.array([sep, sy * 0.0040, 0.0])
        pb = S + np.array([-sep, sy * 0.0040, 0.0])
        with m.peca("cabo_atuadores", n):
            ok = _par_mesa(cena, mesa, f"buck{n}_entrada", pa, pb, qa, qb, D_18, ("fios_vermelho", "fios_preto"),
                           "18 AWG", meio_y[1.0][1], meio_y[-1.0][1], f"el_buck12_{n}_borne_entrada",
                           "cabo_atuadores", n, ini=S + np.array([0.0, sy * 0.013, 0.0]),
                           fim=0.5 * (qa + qb) + _u(ent[2]) * 0.0095, toque_de=(meio_y[1.0][0], meio_y[-1.0][0]),
                           recuo_para=_u(ent[2]) * 0.0007)
        if not ok:
            warnings.warn(f"detalhes/fios: sem caminho por baixo da placa do XT90 ao buck {n}", stacklevel=2)
        if sai is None or cx_s is None:
            continue
        pa0, pb0 = _polos(cx_s, sai[2])
        if float(pa0[1]) * sy < float(pb0[1]) * sy:
            pa0, pb0 = pb0, pa0
        for k in range(1, 5):
            al = cena.ponto_ancora(f"el_drv{k}_alimentacao")
            cx_d = cena.caixa(f"el_drv{k}_alimentacao")
            if al is None or cx_d is None or (float(al[1][1]) > 0.0) != (sy > 0.0):
                continue
            d_al = _u(al[2])
            # cada par na metade da ilha do lado para onde vai (os 2 pares não se sobrepõem)
            dx_s = math.copysign(0.0011, float(al[1][0]) - float(cx_s.c[0]))
            pa, pb = pa0 + np.array([dx_s, 0.0, 0.0]), pb0 + np.array([dx_s, 0.0, 0.0])
            face = float(cx_d.c[0]) + d_al[0] * float(cx_d.h[0])
            # 2 polos ao longo de y, à altura da entrada (a meio da caixa do borne)
            q_c = np.array([face, float(cx_d.c[1]), float(al[1][2])])
            qa, qb = q_c + np.array([0.0, 0.0019, 0.0]), q_c - np.array([0.0, 0.0019, 0.0])
            with m.peca("cabo_atuadores", 4 + k):
                ok = _par_mesa(cena, mesa, f"drv{k}_12v", pa, pb, qa, qb, D_20, ("fios_vermelho", "fios_preto"),
                               "20 AWG", f"el_buck12_{n}_borne_saida", f"el_buck12_{n}_borne_saida",
                               f"el_drv{k}_alimentacao", "cabo_atuadores", 4 + k,
                               ini=0.5 * (pa + pb) + _u(sai[2]) * 0.0095,
                               fim=q_c + d_al * 0.0065 + np.array([0.0, 0.0, -0.0075]),
                               recuo_para=d_al * 0.0012)
            if not ok:
                warnings.warn(f"detalhes/fios: sem caminho por baixo da placa do buck {n} ao driver {k}", stacklevel=2)


def _ubec_acessivel(cena: _Cena) -> None:
    """Build ACESSÍVEL: o UBEC de 6,8 V num berço na placa de cima, atrás da pilha, com a entrada virada para trás —
    derivação de 18 AWG soldada no lado de DENTRO de cada copo do XT90 (entre os 2 fios de 10 AWG, que sobem por fora):
    sobe por trás com eles e entra a direito na entrada do UBEC; servo-rail na saída e daí os cabos dos servos e a fita
    PWM; e os bucks/drivers por baixo da placa de baixo."""
    m = cena.m
    ent = cena.ponto_ancora("el_ubec_entrada")
    cx_e, cx_s = cena.caixa("el_ubec_entrada"), cena.caixa("el_ubec_saida")
    copos = _copos_xt90(cena)
    if ent is not None and cx_e is not None and copos is not None and len(copos) == 2:
        d_e = _u(ent[2])
        qa, qb = _polos(cx_e, d_e, 0.0015)
        f_e = float(cx_e.c[0]) + d_e[0] * float(cx_e.h[0])            # face da entrada
        rr = 0.5 * D_18
        with m.peca("cabo_fonte24"):
            for (c, dout, nome_copo), polo, mat, q in zip(copos, ("pos", "neg"), ("fios_vermelho", "fios_preto"),
                                                         (qa, qb) if float(qa[1]) >= float(qb[1]) else (qb, qa),
                                                         strict=True):
                c = np.asarray(c, dtype=float)
                sg = 1.0 if float(c[1]) >= 0.0 else -1.0
                g = cena.caixa(nome_copo)
                r_copo = float(g.h[1]) if g is not None else 0.0027
                y_c = float(g.c[1]) if g is not None else float(c[1])
                y_d = sg * max(0.0, abs(y_c) - r_copo - rr - 0.0001)     # ao lado do copo, por dentro
                y_f = sg * max(rr + 0.0004, abs(y_c) - 0.5 * D_BAT - rr - 0.0002)   # entre os 10 AWG
                x_m = float(g.c[0]) if g is not None else float(c[0])
                p0 = np.array([x_m + 0.0005, y_d, float(c[2])])
                toque = np.array([x_m + 0.0005, sg * (abs(y_c) - r_copo), float(c[2])])
                x_tr = float(c[0]) + float(dout[0]) * 0.0085
                pts = [p0, np.array([x_tr, y_f, float(c[2])]),
                       np.array([x_tr - 0.002, y_f, float(c[2]) + 0.004]),
                       np.array([x_tr - 0.002, y_f, float(q[2]) - 0.006]),
                       np.array([x_tr + 0.004, y_f, float(q[2])]),
                       np.array([f_e + d_e[0] * 0.008, float(q[1]), float(q[2])]), q - d_e * 0.0006]
                m.tubo("drone", mat, _curva(pts, 0.004), D_18)
                cena.ligar(f"ubec_{polo}", nome_copo, "el_ubec_entrada", "drone", toque, "drone", q, "18 AWG",
                           "cabo_fonte24", polo=polo, nota="derivação no copo do XT90 → entrada do UBEC")
    _alimentacao_atuadores(cena)
    if cx_s is None:
        return
    sai = cena.ponto_ancora("el_ubec_saida")
    _estrela_servos_ubec(cena, cx_s, sai[2] if sai is not None else np.array([1.0, 0.0, 0.0]))


def _estrela_servos_ubec(cena: _Cena, cx_s: _Caixa, d_s) -> None:
    """Servo-rail (4 fichas de 3 pinos) na face de saída do UBEC, POR CIMA da ponte do FC; daí a fita de 4 PWM + GND
    até à ficha `el_fc_con_pwm` (primeiro: fica com o caminho mais baixo e direito) e cada cabo de servo (redondo Ø 3,2)
    até à junção na ponta do feixe do ombro — pelo mapa 2,5D da placa de cima (`_Mesa`): deitados no que lá estiver,
    por cima dos cabos baixos, à volta do resto."""
    m = cena.m
    d_s = _u(d_s)
    face = cx_s.c + d_s * float(np.abs(d_s) @ cx_s.h)
    # o rail encosta à parte de cima da face (a ponte do FC fica por baixo): 4 fichas lado a lado em y
    z_r = float(cx_s.hi[2]) - 0.0026
    rail_c = np.array([float(face[0]) + d_s[0] * 0.0013, float(face[1]), z_r])
    with m.peca("cabo_servo", 0):
        m.caixa("drone", "fios_dupont", rail_c, np.eye(3), [0.0013, 0.0066, 0.0024])
    # os de trás nas fichas de fora (viram primeiro), os da frente nas de dentro: as saídas não se cruzam
    portas = {3: 0.00495, 1: 0.00165, 4: -0.00165, 2: -0.00495}
    saidas = {}
    for k in (3, 2, 1, 4):
        if k not in cena.juncao_servo:
            continue
        with m.peca("cabo_servo", k):
            y_p = float(face[1]) + portas.get(k, 0.0)
            ficha = np.array([float(rail_c[0]) + d_s[0] * 0.0028, y_p, z_r])
            m.caixa("drone", "fios_preto", ficha, np.eye(3), [0.0015, 0.00125, 0.0022])
            p0 = ficha + d_s * 0.0045
            vias = ("fios_castanho", "fios_vermelho") if _pico_lados(cena) else ("fios_castanho", "fios_vermelho",
                                                                                 "fios_laranja")
            for j, mat in enumerate(vias):
                dz = (j - 1) * 0.0012
                m.tubo("drone", mat, [ficha + d_s * 0.0015 + np.array([0.0, 0.0, dz]),
                                      p0 - d_s * 0.0015 + np.array([0.0, 0.0, 0.4 * dz]), p0], D_SERVO)
            saidas[k] = (p0, y_p)
    # ---- os 4 cabos dos servos (rail → feixe do ombro) — primeiro; o cabo PWM (mais fino) passa depois por onde der
    J_ = np.array([cena.juncao_servo[k][0] for k in saidas]) if saidas else np.zeros((0, 3))
    if saidas:
        lo = np.minimum(J_.min(axis=0), rail_c) - np.array([0.012, 0.012, 0.0])
        hi = np.maximum(J_.max(axis=0), rail_c) + np.array([0.012, 0.012, 0.0])
        # deitados no que lá estiver: a ponte do FC e as fichas do Pi na janela, a placa de cima por fora dela (antes
        # flutuavam à altura do rail, 12 mm acima da placa); o rail e a junção no feixe estão mais altos (soltar)
        pt_s = cena.caixa("placa_superior") or _caixa_malha(cena, "placa_superior")
        z_ms = (float(pt_s.hi[2]) + 0.5 * D_CABO_SERVO + 0.00015) if pt_s is not None else min(z_r, float(J_[:, 2].min()))
        mesa = _Mesa(cena, lo, hi, z_ms, acima=max(0.0045, min(z_r, float(J_[:, 2].min())) - z_ms + 0.0045))
        if cena.fc is not None:
            mesa.proibir(cena.fc.lo - 0.001, cena.fc.hi + 0.001)
        cx_pw, anc_pw = cena.caixa("el_fc_con_pwm"), cena.ponto_ancora("el_fc_con_pwm")
        if cx_pw is not None and anc_pw is not None:        # a chegada do cabo PWM (desenhado a seguir) fica livre
            d_pw = _u(anc_pw[2])
            q0 = cx_pw.c + d_pw * float(np.abs(d_pw) @ cx_pw.h)
            q1 = q0 + d_pw * 0.0085
            mesa.proibir(np.minimum(q0, q1) - 0.0016, np.maximum(q0, q1) + 0.0016)
    r_s = 0.5 * D_DXL
    # ordem: os de trás (vão direitos ao seu lado), depois os da frente — o de −y primeiro (contorna o FC por −y, por
    # fora do cabo PWM) e o de +y a seguir (pelo seu lado, se der; senão por fora do primeiro)
    for k in sorted(saidas, key=lambda kk: (abs(float(saidas[kk][1] - face[1])) < 0.003,
                                            float(cena.juncao_servo[kk][0][1]) > 0.0)):
        p0, y_p = saidas[k]
        J, dJ, nome_c, c_c, qc = cena.juncao_servo[k]
        with m.peca("cabo_servo", k):
            # saída: os de fora (braços de trás) viram logo para o lado deles; os de dentro seguem a direito e só depois
            # de passarem as saídas dos de fora se afastam do eixo (cada um cruza os sinais dos ESC do seu lado)
            fora = abs(float(y_p - face[1])) > 0.003
            sy = 1.0 if float(J[1]) >= 0.0 else -1.0
            lat_s = _u(np.cross(EZ, d_s)) * (1.0 if float(np.cross(EZ, d_s)[1]) * sy >= 0.0 else -1.0)
            saida = [p0 + d_s * 0.0025] if fora else [p0 + d_s * 0.0035, p0 + d_s * 0.0065 + lat_s * 0.00155]
            cam = mesa.rota(saida[-1], J + 0.010 * _u(dJ), r_s + 0.00005, folga=0.00012, soltar=0.0026,
                            meio_y=sy * 0.0005)
            if cam is None and not fora:
                cam = mesa.rota(saida[-1], J + 0.010 * _u(dJ), r_s + 0.00005, folga=0.00012, soltar=0.0026)
            if cam is None:
                warnings.warn(f"detalhes/fios: sem caminho livre do servo-rail ao feixe do ombro {k}", stacklevel=2)
                continue
            linha = _curva([p0, *saida[:-1], *cam, J], 0.004)
            m.tubo("drone", "fios_dxl", linha, D_CABO_SERVO)
            mesa.juntar(np.asarray(_reamostrar(linha, 0.001)), r_s)
            cena.servo_linhas[k] = linha
            pico = bool(_pico_lados(cena))
            cena.ligar(f"servo_cotovelo{k}", "el_ubec_saida", nome_c, "drone",
                       np.array([float(face[0]), y_p, z_r]), c_c, qc,
                       "3 × 22 AWG (castanho GND, vermelho 6,8 V, laranja PWM)", "cabo_servo", k,
                       via="feixe do ombro",
                       nota=("extensão do servo DS3218MG: V+/GND no servo-rail do UBEC; o sinal (laranja) sai numa "
                             "derivação junto ao feixe do ombro para o Pico do seu lado") if pico else
                       "extensão do servo DS3218MG no servo-rail do UBEC")
    cena.rail_servos = (rail_c, face, d_s, z_r, dict(portas))
    if _pico_lados(cena):
        return                    # os sinais PWM dos servos vêm dos Pico (`_controladores_bracos`): sem a fita ao FC
    # ---- a fita PWM (rail → FC)
    pwm = cena.ponto_ancora("el_fc_con_pwm")
    cx_p = cena.caixa("el_fc_con_pwm")
    if pwm is None or cx_p is None:
        warnings.warn("detalhes/fios: build acessível — sem a âncora `el_fc_con_pwm` a fita PWM não se desenha",
                      stacklevel=2)
    else:
        with m.peca("cabo_servo", 0):
            d_p = _u(pwm[2])
            f_p = cx_p.c + d_p * float(np.abs(d_p) @ cx_p.h)          # face da ficha
            fim = f_p - d_p * 0.0004
            chega = f_p + d_p * 0.007
            # cabo REDONDO de 5 × 28 AWG (4 PWM + GND) numa manga termo-retráctil de Ø 2,6: só as pontas mostram os fios
            a = np.array([float(rail_c[0]), float(face[1]), z_r + 0.0024 + 0.00045])
            sobe = a + np.array([0.004, 0.0, 0.0011])
            r_f = 0.5 * D_PWM
            lo = np.minimum(sobe, chega) - np.array([0.010, 0.010, 0.0])
            hi = np.maximum(sobe, chega) + np.array([0.010, 0.010, 0.0])
            mesa_f = _Mesa(cena, lo, hi, float(chega[2]), acima=0.0045)
            if cena.fc is not None:
                mesa_f.proibir(cena.fc.lo - 0.0005, cena.fc.hi + 0.0005)
            cam = mesa_f.rota(sobe, chega + d_p * 0.002, r_f + 0.00005, folga=0.00012, soltar=0.0022)
            if cam is None:
                warnings.warn("detalhes/fios: sem caminho livre do servo-rail à ficha PWM do FC", stacklevel=2)
            else:
                linha = _curva([sobe, *cam[1:-1], chega + d_p * 0.002], 0.004)
                m.tubo("drone", "fios_preto", linha, D_PWM)
                lat = _u(np.cross(d_p, EZ)) if abs(float(d_p[2])) < 0.9 else np.array([1.0, 0.0, 0.0])
                # os 5 condutores saem da manga num pentágono (raio 0,85 mm: cabem na manga Ø 2,6 e ficam a 1,0 mm uns
                # dos outros), pela ordem lateral da fila de pinos; em leque, primeiro abrem de lado à altura a que
                # saem e só depois descem à fila (nunca se tocam)
                pent = sorted((0.00085 * math.cos(math.radians(90.0 + 72.0 * i)),
                               0.00085 * math.sin(math.radians(90.0 + 72.0 * i))) for i in range(5))
                # (no rail: o referencial da manga no início dela — e1 ao longo dela, e_l a largura (y), e_v ⟂)
                e1 = _u(np.asarray(linha[1]) - np.asarray(linha[0]))
                e_l = _u(np.array([0.0, 1.0, 0.0]) - e1[1] * e1)
                e_v = np.cross(e1, e_l)
                for j, mat in enumerate(("fios_preto", "fios_laranja", "fios_laranja", "fios_laranja", "fios_laranja")):
                    off = (j - 2) * (D_28 + 0.00005)
                    cl, cz = pent[j]
                    q_m = sobe + 0.0015 * e1 + cl * e_l + cz * e_v              # 1,5 mm dentro da manga
                    q_p = a + np.array([0.0, off, 0.0])
                    ax_m, ax_p = float(np.dot(q_m - sobe, e1)), float(np.dot(q_p - sobe, e1))
                    q_meio = sobe + 0.5 * (ax_m + ax_p) * e1 + float(np.dot(q_p - sobe, e_l)) * e_l + cz * e_v
                    m.tubo("drone", mat, [q_p, q_meio, q_m], D_28)
                    # no FC (manga ao longo de d_p, largura em `lat`)
                    q_m = linha[-1] - 0.0015 * d_p + cl * lat + cz * EZ
                    q_p = fim + off * lat
                    q_meio = q_m + 0.5 * float(np.dot(q_p - q_m, d_p)) * d_p + (off - cl) * lat
                    m.tubo("drone", mat, [q_m, q_meio, q_p], D_28)
                cena.ligar("servos_pwm", "el_ubec_saida", "el_fc_con_pwm", "drone",
                           np.array([float(face[0]), float(face[1]), z_r]), "drone", fim,
                           "5 × 28 AWG (4 PWM + GND) em manga Ø 2,6", "cabo_servo", nota="servo-rail → saídas PWM do FC")

def _estrela_servos(cena: _Cena, sai: _Caixa, nome_sai: str, z_mesa: float) -> None:
    """Build ACESSÍVEL: servo-rail (4 × 3 pinos) na saída do UBEC de 6,8 V e daí, em estrela, a extensão de 3 fios
    (22 AWG) de cada servo do cotovelo até à junção à saída do feixe do ombro (pelo mesmo caminho que o DYNAMIXEL
    fazia: sobe pela folga de trás da pilha e segue deitada na placa de cima); e a fita de 5 fios (4 PWM + GND) do
    rail ao FC."""
    m, comp = cena.m, cena.computador
    r = 0.5 * D_DXL
    x_sobe0 = float(comp.lo[0]) - FOLGA_PILHA - 0.0002
    ys = {1: 0.0108, 3: 0.0075, 2: -0.0075, 4: -0.0108}
    portas = {1: 0.00495, 3: 0.00165, 2: -0.00165, 4: -0.00495}   # 4 fichas de 3 pinos, pela ordem das subidas
    # servo-rail: 4 × 3 pinos de 2,54 mm na face da saída do UBEC (as fichas de pé, lado a lado em y)
    rail_c = np.array([float(sai.hi[0]) + 0.0013, float(sai.c[1]), float(sai.c[2])])
    with m.peca("cabo_servo", 0):
        m.caixa("drone", "fios_dupont", rail_c, np.eye(3), [0.0013, 0.0066, 0.0040])
    for k in range(1, 5):
        jc = cena.juncao_servo.get(k)
        if jc is None:
            continue
        J, dJ, nome_c, c_c, qc = jc
        with m.peca("cabo_servo", k):
            sx, sy = cena.sinais[k - 1]
            y_s = float(comp.c[1]) + ys.get(k, 0.0)
            # a ficha de 3 pinos no rail (de frente para +x); o cabo REDONDO (bainha preta Ø 3,2, os 3 condutores
            # castanho/vermelho/laranja só à vista nas pontas) faz o caminho que o DYNAMIXEL fazia
            y_p = float(sai.c[1]) + portas.get(k, 0.0)
            ficha = np.array([float(rail_c[0]) + 0.0013 + 0.0015, y_p, float(sai.c[2])])
            m.caixa("drone", "fios_preto", ficha, np.eye(3), [0.0015, 0.00125, 0.0038])
            p0 = np.array([float(ficha[0]) + 0.0015 + 0.0060, y_p, float(sai.c[2])])
            for j, mat in enumerate(("fios_castanho", "fios_vermelho", "fios_laranja")):
                dz = (j - 1) * 0.00254
                m.tubo("drone", mat, [np.array([float(ficha[0]) + 0.0015, y_p, float(sai.c[2]) + dz]),
                                      p0 + np.array([-0.002, 0.0, 0.33 * dz]), p0], D_SERVO)
            z_t = z_mesa + r
            fora = J + 0.024 * dJ
            x_sobe = min(x_sobe0, float(p0[0]) + r + 0.0006)
            x_faixa = x_sobe - (0.004 if sx > 0 else 0.009)
            y_lado = float(comp.c[1]) + sy * (float(comp.h[1]) + 0.012)
            z0 = float(p0[2]) + (0.0015 if sx > 0 else 0.0055)
            pts = [p0, p0 + np.array([0.0012, 0.0, 0.0]), np.array([x_sobe, p0[1], z0]),
                   np.array([x_sobe, y_s, z0 + 0.004]), np.array([x_sobe, y_s, max(z0 + 0.0045, z_t + 0.004)]),
                   np.array([x_faixa, y_s, z_t])]
            if sx > 0:
                via = [np.array([x_faixa, y_lado, z_t]), np.array([float(fora[0]) - 0.006, y_lado, z_t]),
                       np.array([fora[0], fora[1], z_t])]
            else:
                y_v = y_lado + sy * 0.0045
                via = [np.array([x_faixa, y_v, z_t]), np.array([float(fora[0]), y_v, z_t]),
                       np.array([fora[0], fora[1], z_t])]
            deitado = _drapejar(cena, _curva([pts[-1], *via], 0.010), r, acima_cabos=0.0035)
            pts = [*pts[:-1], *deitado, fora + np.array([0.0, 0.0, 0.002]), J]
            m.tubo("drone", "fios_dxl", _curva(pts, 0.008), D_CABO_SERVO)
            cena.ligar(f"servo_cotovelo{k}", nome_sai, nome_c, "drone", np.array([float(sai.hi[0]), y_p, float(sai.c[2])]),
                       c_c, qc, "3 × 22 AWG (castanho GND, vermelho 6,8 V, laranja PWM)", "cabo_servo", k,
                       via="feixe do ombro", nota="extensão do servo DS3218MG no servo-rail do UBEC")
    # a fita de sinais do rail ao FC (4 PWM + GND) só com a ficha PWM do FC publicada pela eletrónica
    pwm = cena.fc_con("el_fc_con_pwm") if cena.ctx.geom_existente("el_fc_con_pwm") is not None else None
    if pwm is None:
        warnings.warn("detalhes/fios: build acessível — sem a âncora `el_fc_con_pwm` (saídas PWM do FC) a fita dos "
                      "sinais dos servos não se desenha", stacklevel=2)
        return
    with m.peca("cabo_servo", 0):
        a = np.array([float(rail_c[0]), float(sai.c[1]), float(rail_c[2]) + 0.0040 + 0.0006])
        b_ = np.array([float(pwm.lo[0]) - 0.0012, float(pwm.c[1]), float(pwm.c[2])])
        pts = [a, a + np.array([0.0, 0.0, 0.004]), np.array([x_sobe0, float(a[1]), float(a[2]) + 0.006]),
               np.array([x_sobe0, float(a[1]), float(b_[2]) + 0.004]), b_ - np.array([0.006, 0.0, -0.002]), b_]
        m.paralelos("drone", ("fios_preto", "fios_laranja", "fios_laranja", "fios_laranja", "fios_laranja"),
                    _curva(pts, 0.006), D_28, n0=np.array([0.0, 1.0, 0.0]), ident="servos_pwm")
        cena.ligar("servos_pwm", nome_sai, "el_fc_con_pwm", "drone",
                   np.array([float(sai.hi[0]), float(sai.c[1]), float(sai.c[2])]), "drone",
                   np.array([float(pwm.lo[0]), float(pwm.c[1]), float(pwm.c[2])]), "5 × 28 AWG (4 PWM + GND)",
                   "cabo_servo", nota="servo-rail → saídas PWM do FC")


# ====================================================================================== entrada
_ANTIGOS = ("fio_motor{k}_a", "fio_motor{k}_b", "fio_motor{k}_c", "abracadeira_braco{k}_1", "abracadeira_braco{k}_2")


def _chave_cache(ctx) -> str | None:
    """Impressão digital de TUDO o que entra na cablagem: o código e os dados do drone (lab/drone_rpi/**.py,
    models/drone_rpi/*), o Hardware do build, as versões do MuJoCo/numpy, as variáveis de ambiente que mudam o modelo e
    o estado do spec a esta altura (nomes, tipos, poses e tamanhos dos geoms) — None se a cache está desligada
    (`DRONE_DETALHES_CACHE=0`) ou se algo falha."""
    if os.environ.get("DRONE_DETALHES_CACHE", "1") == "0":
        return None
    try:
        import hashlib
        import pickle
        from pathlib import Path
        h = hashlib.blake2b(digest_size=16)
        raiz = Path(__file__).resolve().parents[1]
        for f in sorted([*raiz.rglob("*.py"), *raiz.parent.glob("*.py")]):     # lab/drone_rpi/** + lab/*.py
            h.update(f.relative_to(raiz.parent).as_posix().encode())
            h.update(f.read_bytes())
        dados = raiz.parents[1] / "models" / "drone_rpi"
        if dados.is_dir():
            for f in sorted(dados.iterdir()):
                if f.is_file():
                    h.update(f.name.encode())
                    h.update(f.read_bytes())
        h.update(pickle.dumps(ctx.hw))
        h.update("|".join([mujoco.__version__, np.__version__, os.environ.get("DRONE_DETALHES", ""),
                           os.environ.get("DRONE_RPI_ESCALAR", "")]).encode())
        for g in ctx.spec.geoms:
            par = g.parent.name if g.parent is not None else ""
            h.update(f"{g.name}|{int(g.type)}|{par}|{g.meshname}|{g.material}|{int(g.group)}".encode())
            h.update(np.concatenate([np.asarray(g.pos, float), np.asarray(g.quat, float), np.asarray(g.size, float),
                                     np.asarray(g.rgba, float)]).tobytes())
        import json
        h.update(json.dumps([ctx.registo.notas.get("ancoras", {}), ctx.registo.ligacoes], sort_keys=True,
                            default=str).encode())
        for q in getattr(ctx.ferragens, "pecas", None) or []:       # ferragens ainda por fundir (a sonda vê-as)
            h.update(f"{q.corpo}|{q.material}".encode())
            h.update(np.asarray(q.v, float).tobytes())
            h.update(np.asarray(q.f, np.int64).tobytes())
        return h.hexdigest()
    except Exception:  # noqa: BLE001 — sem cache, calcula
        return None


def _categoria(nome: str) -> type[Warning]:
    """A classe de aviso com este nome (das embutidas; senão UserWarning)."""
    import builtins
    c = getattr(builtins, nome, None)
    return c if isinstance(c, type) and issubclass(c, Warning) else UserWarning


def _pasta_cache() -> str | None:
    """A pasta da cache: a do UTILIZADOR (`DRONE_DETALHES_CACHE_DIR`, senão `$XDG_CACHE_HOME/mujoco-lab/fios`, por
    omissão `~/.cache/mujoco-lab/fios`), criada com 0700 — nunca a temporária global (regra do laboratório, e um pickle
    numa pasta partilhada seria código de outra pessoa a correr aqui). None (sem cache) se a pasta não for só nossa."""
    base = os.environ.get("DRONE_DETALHES_CACHE_DIR")
    if not base:
        base = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
                            "mujoco-lab", "fios")
    try:
        os.makedirs(base, mode=0o700, exist_ok=True)
        st = os.stat(base)
        if st.st_uid != os.getuid() or (st.st_mode & 0o022):      # de outro utilizador ou gravável por outros
            return None
    except OSError:
        return None
    return base


def adicionar(ctx) -> None:
    """Cablagem completa do build (ver o docstring do módulo); cada parte é opcional e independente. O resultado (malhas,
    cabos, ligações, âncoras novas, abraçadeiras registadas, avisos) fica numa cache em disco (a do utilizador,
    `~/.cache/mujoco-lab/fios/<impressão digital>.pkl`): com as mesmas entradas o próximo processo só a lê — o cockpit e os
    treinos arrancam depressa. `DRONE_DETALHES_CACHE=0` desliga-a."""
    for k in range(1, 5):
        for modelo_nome in _ANTIGOS:
            nome = modelo_nome.format(k=k)
            if ctx.geom_existente(nome) is not None:
                ctx.apagar(nome)
    for nome in ("cabo_bateria_pos", "cabo_bateria_neg"):      # NUNCA o `conector_xt90` (a eletrónica recria-o)
        if ctx.geom_existente(nome) is not None:
            ctx.apagar(nome)
    for nome, kw in _MATERIAIS.items():
        ctx.material(nome, **kw)
    malhas = _Malhas(ctx)
    t_ini = time.perf_counter()
    chave = _chave_cache(ctx)
    pasta = _pasta_cache() if chave else None
    arq = os.path.join(pasta, f"{chave}.pkl") if pasta else None
    notas = ctx.registo.notas
    if arq is not None and os.path.exists(arq):
        try:
            import pickle
            with open(arq, "rb") as fh:
                d = pickle.load(fh)
            malhas.lotes, malhas.cabos = d["lotes"], d["cabos"]
            ctx.registo.ligacoes.extend(d["ligacoes"])
            notas.setdefault("ancoras", {}).update(d["ancoras"])
            if d["rabichos"]:
                notas["fios_rabichos"] = d["rabichos"]
            if ctx.ferragens is not None:
                for kw in d["ferragens"]:
                    ctx.ferragens.registar(**kw)
            for cat, msg in d["avisos"]:
                warnings.warn(msg, _categoria(cat), stacklevel=2)
            malhas.criar()
            if os.environ.get("FIOS_TEMPOS"):
                print("fios:", f"total {time.perf_counter() - t_ini:.3f} s (da cache)")
            return
        except Exception:  # noqa: BLE001 — cache estragada: calcula de novo
            malhas = _Malhas(ctx)
    cena = _Cena(ctx, malhas)
    partes = [(f"braço {k}", (_braco_articulado if cena.art else _braco_rigido), (cena, k)) for k in range(1, 5)]
    partes += [("bateria", _bateria, (cena,)), ("Raspberry Pi 5 (5 V)", _rpi5_alimentacao, (cena,)),
               ("RPi/FC", _rpi_fc, (cena,)), ("FPC", _fpc_camera, (cena,)), ("barramento", _fonte_e_barramento, (cena,)),
               ("ombros de fuso", _ombros_fuso, (cena,)), ("controladores dos braços", _controladores_bracos, (cena,)),
               ("cadeia de energia", _cadeia_energia, (cena,))]
    tempos = {}                 # FIOS_TEMPOS=1 → tempo de cada parte (medir com a máquina livre)
    n_lig = len(ctx.registo.ligacoes)
    ancoras_antes = set(notas.get("ancoras", {}))
    reg_fer = []
    fer = ctx.ferragens
    registar0 = fer.registar if fer is not None else None
    if fer is not None:
        def registar(**kw):
            reg_fer.append(dict(kw))
            return registar0(**kw)
        fer.registar = registar
    try:
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            for nome, fn, args in partes:
                t0 = time.perf_counter()
                try:
                    with malhas.peca("cablagem", 0):
                        fn(*args)
                except Exception as e:  # noqa: BLE001 — um detalhe visual nunca pode derrubar o simulador
                    warnings.warn(f"detalhes/fios: {nome} não desenhado ({type(e).__name__}: {e})", stacklevel=2)
                tempos[nome] = time.perf_counter() - t0
    finally:
        if fer is not None:
            fer.registar = registar0
    textos = [(w.category.__name__, str(w.message)) for w in avisos]
    for cat, msg in textos:
        warnings.warn(msg, _categoria(cat), stacklevel=2)
    if arq is not None:
        try:
            import pickle
            import tempfile
            os.makedirs(os.path.dirname(arq), exist_ok=True)
            d = {"lotes": malhas.lotes, "cabos": malhas.cabos, "ligacoes": ctx.registo.ligacoes[n_lig:],
                 "ancoras": {k: v for k, v in notas.get("ancoras", {}).items() if k not in ancoras_antes},
                 "rabichos": notas.get("fios_rabichos", []), "ferragens": reg_fer, "avisos": textos}
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(arq), suffix=".pkl")
            with os.fdopen(fd, "wb") as fh:
                pickle.dump(d, fh, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, arq)
            velhos = sorted((os.path.join(os.path.dirname(arq), f) for f in os.listdir(os.path.dirname(arq))
                             if f.endswith(".pkl")), key=os.path.getmtime)
            for f in velhos[:-28]:                       # guarda as 28 mais recentes (~4 MB cada)
                os.remove(f)
        except Exception:  # noqa: BLE001, S110 — sem cache, segue
            pass
    t0 = time.perf_counter()
    malhas.criar()
    tempos["criar"] = time.perf_counter() - t0
    if os.environ.get("FIOS_TEMPOS"):
        print("fios:", f"total {time.perf_counter() - t_ini:.3f} s", {k: round(v, 3) for k, v in tempos.items()})
