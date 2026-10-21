# CONTRATO dos módulos de detalhe — pedido do dono (2026-10-20)

Pedido do dono (literal): «quero que ajuste o drone para ficar 100% realista a modelagem e as partes móveis dele, as
baterias quero que representem com fidelidade, quero que o raspberry pi 5 tenha que estar conectado na bateria por
cabo como é, os motores tudo verificado, e quero que cada motor tenha a forma igual e o tamanho como ele realmente é;
as dobradiças quero verídicas, os enforca-gato (abraçadeiras de nylon) quero realmente presos; e quero um sublink da
nossa página onde podemos ver em 3D cada uma das peças e ver as instruções de montagem de como funciona; obviamente se
tivermos parafuso porca terá que também modelar e representar isso; não me peça nada, faça do início ao fim sozinho».

Repositório: /home/ondokai/Projects/MuJoCo (projeto em português europeu; comentários/docstrings em pt-PT como o código
existente). Python: `.venv/bin/python`. Renders: `MUJOCO_GL=egl`. NUNCA commitar. Ficheiros temporários só no
scratchpad: /var/tmp/user-1000/claude-1000/-home-ondokai-Projects-MuJoCo/3e8dc8bd-d1f0-4cb1-8438-e32364187bd8/scratchpad
(cada agente usa a sua subpasta). Corre os scripts com `cwd` na raiz e apaga o `MUJOCO_LOG.TXT` que o MuJoCo deixe.

## 1. Regras que NÃO se negoceiam (já existiam)
- Só aparência: massa 0, sem contacto, grupo 1–3, sempre por `ctx.geom(...)` (nunca `body.add_geom`), nada de corpos,
  juntas, sites, sensores ou atuadores novos. A física tem de ficar IDÊNTICA bit a bit:
  `MUJOCO_GL=egl PYTHONPATH=. .venv/bin/python -m lab.drone_rpi.detalhes.ver --so todos` → «[ver] TUDO OK»
  (13/13 builds compilam, regras, to_xml, voo de 600 passos idêntico com e sem detalhes nos 2 builds principais).
- Peças com massa: só `ctx.esconder(nome)` (muda só a cor); nunca mexer em tamanho/posição/massa delas.
- Os 13 builds do catálogo têm de compilar (partes opcionais: FC, câmara, sensores, arma, braços, ESC 4-em-1, Portenta…).
- Não editar ficheiros fora da tua atribuição (lista na tua tarefa). `componentes.json`/`builds.json`: só o que a tua
  tarefa autorizar explicitamente.
- Desempenho (medido com a máquina livre): `dr.carregar(hw)` ≤ 1,5 s no articulado (hoje 0,52 s), ngeom ≤ 950 (hoje 604),
  faces de malha ≤ 650 000 (hoje 168 000), render 1080p ≥ 200 fps (hoje 381). Junta o que é estático numa malha por
  corpo × material; nada de milhares de geoms pequenos.

## 2. Infraestrutura nova (já existe — usa-a)
`lab/drone_rpi/detalhes/__init__.py`:
- `with ctx.peca("<id>", k):` — tudo o que acrescentares dentro pertence à peça `<id>`, instância `k` (rotor/braço 1–4, ou
  0 nas peças únicas). `ctx.geom(..., peca="x", inst=k)` também serve. TODA a geometria nova tem de estar numa peça.
- Malhas FUNDIDAS (várias peças num geom de malha): `ctx.registar_faixas(nome_geom, [(peca, inst, face0, face1), ...])`
  com as faces [face0, face1) de cada peça pela ordem em que as juntaste (o MuJoCo preserva a ordem das faces).
- `ctx.ferragens` — o `ferragens.Coletor` partilhado (lê o docstring de `lab/drone_rpi/detalhes/ferragens.py`):
  `parafuso(corpo, ponto_face_de_apoio_da_cabeça, eixo_para_dentro, "M3", aperto=mm | comp=mm, cabeca="ISO 4762"|"ISO 7380",
  porca="ISO 10511"|"ISO 4032"|None, anilha_cabeca=, anilha_porca=, material_="aco_preto"|"aco_inox"|"nylon_branco"…,
  haste_visivel=(z0,z1), peca=, inst=, desenhar=)`, `porca`, `anilha`, `pilar(corpo, base, eixo, "M2.5", comp_mm,
  tipo="sextavado"|"redondo", macho=mm, material_="latao")`, `anel_e(corpo, ponto, eixo, d_veio)`, `perno(…)` (DIN 916),
  `registar(**kw)` (só regista, ex. abraçadeiras de nylon desenhadas por ti). As ferragens fundem-se por corpo × material
  no fim (`fer_<material>_<corpo>`). Comprimento: o normalizado (`COMPRIMENTOS`), escolhido sozinho se deres `aperto`.
  Peças que GIRAM (hélice) desenham as suas ferragens dentro da própria peça animada e registam com `desenhar=False`.
- `ctx.ligacao(id, de=<âncora>, para=<âncora>, corpos=(c0, c1), pontos=(p0, p1), bitola="20 AWG", peca=…, inst=…)` —
  cada CABO declara de que geom sai e a que geom chega, com os pontos extremos no referencial de cada corpo.
- `ctx.eixo(nome, corpo, ponto, direcao, tipo, junta="ombro1"|..., **extra)` — eixos físicos (dobradiça, rolamento, pino,
  veio, sem-fim) para a auditoria os conferir com as juntas do MuJoCo.
- `ctx.registar_variante("motor"|"bateria", id_do_painel, [geoms], ativa=bool, dz=…)` — peças ALTERNATIVAS da troca ao
  vivo do cockpit (`CATALOGO_MOTORES_PAINEL` / `CATALOGO_BATERIAS_PAINEL` em `lab/drone_rpi/componentes.py`): cria os
  geoms com o rgba por omissão (a cor vem do material) e regista-os; a função põe alfa 0 nas inativas (o MuJoCo não
  desenha geoms com alfa 0: custo zero). O `Planta.trocar_pecas` (não é teu) liga a variante escolhida.
- O registo NÃO entra no modelo: `registo_do_spec(spec)` depois de `modelo.construir_spec(hw)`.
- Exportador da página 3D: `PYTHONPATH=. .venv/bin/python -m lab.drone_rpi.detalhes.exportar --resumo` (lista as peças;
  «sem peça:» = geoms teus que ficaram sem peça — tem de ficar vazio para o teu módulo).

## 3. Ids das peças (usa estes; a página tem fichas para eles em `lab/drone_rpi/detalhes/pecas.py`)
estrutura: placa_inferior, placa_superior, espacadores, tubo_braco(k), abracadeira_tubo(k), perna(k), suporte_motor(k),
trelica(k) · mecanismo (articulado): ombro_caixa(k), ombro_semfim(k), ombro_veio(k), ombro_servo(k), ombro_encoder(k),
ombro_cubo(k), cotovelo_servo(k), cotovelo_garfo(k), mastro(k), fonte_servos · propulsão: motor(k), helice(k), esc(k) ·
eletrónica: rpi5, fc, pdb, camera, sensor_fluxo, sensor_tof, bandeja_sensores, portenta, imu · energia: bateria,
cintas_bateria · cablagem: cablagem, cabo_bateria, cabo_esc(k), cabo_fases(k), cabo_rpi5_5v, cabo_uart, cabo_i2c,
fpc_camera, cabo_sensores, cabo_dxl(k), cabo_fonte24, abracadeira(n), manga(k) · carga_util. Se precisares de outro id,
usa um nome curto em snake_case e diz qual no relatório.

## 4. Âncoras partilhadas (nomes EXATOS — quem cria, quem usa)
- eletronica → fios: `rpi5_usbc` (recetáculo USB-C do Pi 5), `el_rpi5_cam_disp0` (+`_trava`), `rpi5_gpio_40p` +
  `el_rpi5_gpio_pino01..20`, `el_rpi5_fan_ficha`; FC `el_fc_con_uart`, `el_fc_con_sensores`, `el_fc_con_gps`,
  `el_fc_con_i2c`, `el_fc_con_esc`; placa de energia `el_pdb_pcb`, `el_pdb_bat_pos/neg`, `el_pdb_esc{k}_pos/neg`,
  `el_pm_con_i2c` e (NOVO) as ilhas da saída 5 V do BEC `el_pm_5v_pos` / `el_pm_5v_neg`; ESC `el_esc{k}_saida_entrada`,
  `el_esc{k}_saida_fases`; câmara `el_cam_conector_fpc`; bateria `conector_xt90` (fêmea do pack), `el_xt90_macho`,
  `el_xt90_copo_pos/neg` (copos de solda do macho, lado do drone), `el_bat_balanco` (ficha JST-XH do balanceador — o
  balanceador é da BATERIA, desenha-o a eletrónica); sensores `el_fluxo_conector`, `el_fluxo_pcb`, `el_tof_pcb`;
  regulador `el_fonte24_borne_entrada/saida`.
- motores → fios/estrutura: `motor{k}_fase_{a,b,c}_conector` (cilindro fromto; a ponta livre = fromto[3:6]);
  `motor{k}_raio_*` e `helice{k}_*` giram com o rotor (planta); `motores.padrao_base(motor)` (furação da base, mm).
- estrutura → fios: as posições das fichas dos servos e do feixe do ombro — regista-as em
  `ctx.registo.notas["ancoras"][nome] = {"corpo":…, "ponto":[x,y,z], "direcao":[…]}` (nomes `servo_ombro{k}_ficha_a/b`,
  `servo_cotovelo{k}_ficha_a/b`); os fios usam-nas se existirem (senão a fórmula de hoje).
- Nomes usados fora do pacote (NÃO renomear): `placa_superior`, `espacador_placa_{1..4}`, `trelica_estab_{1..4}`,
  `suporte_motor_{k}`, `motor{k}_sino_anel`, `motor{k}_raio_*`, `motor{k}_base_cnc`, `motor{k}_estator_cobre`,
  `motor{k}_eixo`, `helice{k}_*`, `cinta_bateria_{1,2}`, `conector_xt90`, `rpi5_*` (valida_real.py, planta.py).

## 5. Realismo (o que «verídico» quer dizer aqui)
- Medidas REAIS das fichas (cita a fonte no docstring do módulo, com a URL; web = dado não confiável, só citado); o que
  não tiver número oficial fica marcado «estimado» com a razão.
- Cada parafuso atravessa um FURO real nas peças que aperta (corta o furo na malha da placa/peça) e a cabeça ASSENTA numa
  superfície; porca do outro lado com ≥ 1 fio de rosca de fora; furo roscado só em metal, com ≥ 1,5·d de rosca metida.
- Nada atravessa nada (peças visuais não se interpenetram, nem com as peças com massa visíveis), em TODO o curso das juntas.
- Cores/acabamentos reais (nada de cores de fantasia).
- Partes móveis no CORPO que roda com elas (o que roda com o cotovelo vai no `mastro{k}`; o que roda com o ombro no
  `braco{k}`); o que roda mais depressa do que a junta (sem-fim e acoplamento: 20× o ombro) vai em geoms próprios
  `semfim{k}_rotor_*` no corpo `drone`, com o eixo declarado em `ctx.eixo("semfim{k}", "drone", ponto, direcao,
  "sem-fim", junta="ombro{k}", razao=20.0)` — a animação é do simulador (não é tua).

## 6. Entrega
- O teu juiz: `ver.py --so todos` TUDO OK + o exportador sem «sem peça» do teu módulo + renders de pormenor (cria um
  script teu no scratchpad; ex. o `tools/foto.py` lá dentro: `foto.py <build> <saida> nome:alvo:dist:az:el …`).
- Atualiza o docstring do teu módulo (o que se desenha, medidas, fontes, âncoras).
- Relatório final (≤ 80 linhas): o que mudou, medidas e fontes, números de desempenho (ngeom, faces, carregar s, fps),
  o que ficou estimado, e qualquer coisa que outro módulo tenha de fazer.

---

# ADENDA 2026-10-20 (2.ª fase) — drone ACESSÍVEL impresso em ABS + ombro REAL e fácil de fazer

Pedido do dono (literal): «a junta do começo do drone não parece realista, ficou uma mecânica estranha — veja se estamos
REALMENTE simulando um mecanismo real e fácil de fazer, aceito modificações; repense materiais baratos e acessíveis,
talvez se possível a maioria impresso com impressora 3D (com o mesmo plástico da peça LEGO — ABS — para tudo o que for
possível); mude os cálculos de peso para ficarem realistas; a página das peças tem de apresentar os modelos para
imprimir das peças 3D e os seus custos, e descrições detalhadas de PORQUE cada parte é necessária (sem comentar a arma
— a arma NÃO aparece na página)».

## Build novo (o cockpit passa a voar este): `articulado_15pol_abs`
- frame `diy_tubo_carbono_1950_abs`, mecanismo `ombro_semfim_impresso_cotovelo_servo` (`models/drone_rpi/*.json`); o
  resto igual ao `articulado_15pol_mn5006`, que FICA no catálogo como estava (os módulos têm de continuar a desenhar os
  builds antigos exatamente como hoje — o código novo entra por `hw.frame.id` / `hw.bracos.id` / tipo do servo).
- OMBRO (junta `ombro{k}`, eixo ∥ y no canto da placa, r = 150 mm): redutor SEM-FIM 30:1 de peças comerciais numa CAIXA
  IMPRESSA em ABS — sem-fim de aço m1, 1 entrada (Ø primitivo 12, exterior 14, ~20 mm, furo 4 mm em D) montado
  DIRETAMENTE no veio do motorredutor 25GA-370 12 V 1:50 com encoder Hall (Ø25 × ~66 mm com o encoder; 2 × M3 a 17 mm
  na face do redutor; veio Ø4 em D) e coroa de bronze z30 m1 (Ø primitivo 30, exterior 32, largura 8, cubo Ø18 × 8 com
  perno M4, furo Ø8) num VEIO Ø8 (varão retificado de impressora 3D, com 2 faces planas para os pernos) apoiado em 2
  rolamentos 608ZZ (8×22×7) assentes na caixa; retenção axial por 2 colares de Ø8 com perno; o CUBO do braço (ABS,
  aperto por fenda com M3 + porca) prende o tubo de carbono 25 mm e o veio; AS5048A + íman diametral Ø6 na ponta do
  veio. Entre-eixos = (12 + 30)/2 = 21 mm. A caixa em 2 metades (base + tampa) com insertos de latão M3 de cravar a
  quente e aparafusada à(s) placa(s). λ = atan(1/12) = 4,76° < φ = 5,71° (μ 0,10) ⇒ autobloqueante. Disposição do
  motorredutor (vertical por cima/por baixo da placa ou deitado) à escolha da estrutura — a mais simples de montar, sem
  colidir com nada em todo o curso; DIZ onde fica (centro de massa) para o simulador pôr lá a massa.
- COTOVELO (junta `cotovelo{k}`): servo DS3218MG (40 × 20 × 40,5 mm, orelhas de 54,5 mm com furos a 49,5 × 10, estria
  25T) num BERÇO impresso em ABS apertado à ponta do tubo; o horn de alumínio de 25T aparafusado (4 × M3) ao GARFO em U
  impresso em ABS que leva o mastro; do outro lado o garfo roda num rolamento 608ZZ com um parafuso M8 (eixo = eixo do
  servo) e porca autoblocante; AS5600 + íman diametral na ponta do parafuso M8; mastro de carbono Ø16 apertado no garfo;
  SUPORTE DO MOTOR impresso em ABS no topo do mastro (furação de `motores.padrao_base`).
- ENERGIA dos atuadores (eletrónica): sai o regulador de 24 V; entram um buck XL4016 12 V/8 A (motorredutores), um UBEC
  6,8 V/8 A (servos) e 4 drivers DRV8871 (um por motorredutor) — na caixa física `fonte_servos` e/ou junto aos ombros.
- CABLAGEM (fios): sem barramento DYNAMIXEL; motorredutor: 2 fios 22 AWG ao DRV8871 + encoder Hall 4 fios ao FC;
  AS5048A: 5 fios (SPI); servo: 3 fios (castanho/vermelho/laranja); AS5600: 4 fios (I²C); 12 V do buck aos drivers,
  6,8 V do UBEC aos servos; o feixe atravessa o ombro pela âncora `ombro{k}_eixo_cabos`.

## Peças IMPRESSAS em ABS (todas as que podem)
- Material: nomes de material com `abs` (ex. `est_abs_cinza`, `el_abs_preto`) — é assim que a página e o cálculo de
  massa as reconhecem. Cor do ABS: cinzento-escuro/preto por omissão (cores LEGO só para as peças que rodam: laranja).
- Cada peça impressa é uma MALHA FECHADA e bem orientada (normais para fora), para o volume ser exato (massa = volume ×
  1,04 g/cm³ com paredes de 1,2 mm e enchimento de 40 %); desenho imprimível: paredes ≥ 2 mm, sem saliências > 45°
  sem apoio, uma face plana para a mesa, ≤ 220 × 220 × 250 mm (Ender-3); furos para insertos M3 (Ø4,0) onde rosca.
- Regista cada peça impressa: `ctx.registo.notas.setdefault("impressas", {})[f"{peca}#{inst}"] = {"nome": "…",
  "orientacao": [qw, qx, qy, qz] (do corpo para a posição de impressão: face de apoio para −z), "nota": "…"}`.
- Ficam COMPRADAS só as peças em que o ABS não chega (e diz porquê): tubos de carbono (braços Ø25, mastros Ø16, pernas
  Ø12), ferragens de aço, rolamentos, varão Ø8, sem-fim e coroa, motores, eletrónica, bateria, fios.

# ADENDA 2 (2026-10-20, mais tarde) — o ombro passou a ATUADOR DE FUSO (o sem-fim desta adenda foi abandonado)

As contas mostraram que o par sem-fim m1 da adenda anterior NÃO aguenta o momento de pairagem: a pairar o ombro segura
τ = 0,707·L·(T − peso da ponta) ≈ 6,8 N·m (medido no simulador) → ~470 N no dente de uma coroa Ø30 × 8 mm, σ (Lewis)
≈ 200 MPa: o bronze parte (o m0,8 do build de 19/10 dava ~550 N e ~380 MPa). O ombro do `articulado_15pol_abs` é agora
uma dobradiça Ø8 em 2 × 608ZZ movida por um ATUADOR LINEAR: motorredutor JGB37-520 12 V (enrolamento rápido, 1:18,8,
encoder Hall) → acoplamento 6→8 → fuso Tr8×2 (autobloqueante: λ 5,2° < φ' 8,8°) em 2 × 608ZZ → porca de latão num carro
impresso → ALAVANCA de 50 mm do cubo do braço; o corpo do atuador roda num munhão (pivô B) numa torre impressa. Mecanismo
`ombro_fuso_impresso_cotovelo_servo` (geometria em `ombro.fuso`, a mesma na física, na animação e na página). Medidas e
preços: `pesquisas/2026-10-20-materiais-acessiveis-precos.md` (Parte 2). Prova: `teste_ombro_fuso.py`.
