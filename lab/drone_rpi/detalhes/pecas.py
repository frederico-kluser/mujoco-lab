"""lab/drone_rpi/detalhes/pecas.py — o CATÁLOGO das peças reais do drone para a página 3D (`/pecas`): nome, categoria,
especificações (tiradas do catálogo do build — `models/drone_rpi/componentes.json` — sempre que lá estão), «como
funciona», fontes, e os PASSOS DE MONTAGEM pela ordem real de uma bancada.

Os identificadores das peças são os que os módulos de detalhe registam (`with ctx.peca("motor", k)`); a instância é o
braço/rotor k (1–4) ou 0 nas peças únicas. A lista de ferragens de cada passo é CONTADA no modelo pelo `exportar.py`
(nunca escrita à mão aqui), e os binários de aperto vêm de `ferragens.BINARIO_NM`.

Nada aqui muda o simulador: é texto e números para pessoas.
"""
from __future__ import annotations

import math

CATEGORIAS = [
    {"id": "estrutura", "nome": "Estrutura"},
    {"id": "mecanismo", "nome": "Braços articulados"},
    {"id": "propulsao", "nome": "Propulsão"},
    {"id": "eletronica", "nome": "Eletrónica"},
    {"id": "energia", "nome": "Energia"},
    {"id": "cablagem", "nome": "Cablagem"},
    {"id": "outros", "nome": "Outros"},
]


def _fmt(v, casas=1, un=""):
    if v is None:
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    s = f"{x:.{casas}f}".replace(".", ",")
    return f"{s} {un}".strip()


def _d(obj, chave, omissao=None):
    dados = getattr(obj, "dados", None) or {}
    return dados.get(chave, omissao)



def acessivel(hw) -> bool:
    """O build é a versão ACESSÍVEL (peças impressas em ABS, ombro com motorredutor + sem-fim de catálogo)?"""
    b = getattr(hw, "bracos", None)
    return str(getattr(hw.frame, "id", "")).endswith("_abs") or (b is not None and "impresso" in str(b.id))


# PORQUE cada peça é necessária para ESTE projeto (um drone grande e estável, 1950 mm, que inclina o corpo para apontar a
# câmara sem sair do sítio, voa com controlo clássico num FC e faz a visão num Raspberry Pi 5) — em detalhe, peça a peça
PORQUE = {
    "placa_inferior": "É o chassis. Nela aparafusam-se as 4 caixas dos ombros (ou as abraçadeiras dos braços), as colunas "
        "que a afastam da placa de cima, a bateria e os sensores de baixo. Sem ela os quatro braços não ficam ligados "
        "entre si: cada mudança de empuxo de um motor torceria o drone, o FC veria essa torção como rotação e "
        "corrigiria contra o próprio frame (oscilação). É também o ponto de apoio da bateria — a maior massa do drone "
        "fica no centro e por baixo, o que baixa o centro de massa e torna o voo mais estável.",
    "placa_superior": "Fecha a «caixa de torção» com a placa de baixo: duas placas afastadas pelas colunas resistem à "
        "torção e à flexão como os dois banzos de uma viga em I — muito mais do que uma placa sozinha com a mesma "
        "massa. Leva a pilha de eletrónica (Pi 5, FC, placa de energia) e protege-a de pancadas por cima.",
    "espacadores": "Mantêm as duas placas à distância certa (é essa distância que dá a rigidez da caixa) e passam o "
        "esforço de uma placa à outra; o espaço entre elas é onde correm os cabos de energia.",
    "tubo_braco": "Leva o empuxo do motor até ao centro: em pairagem ~11 N a ~0,8 m do ombro, ou seja ~9 N·m que o tubo "
        "tem de aguentar sem dobrar. O tubo de carbono 25 × 23 mm é a peça mais rígida por grama para este esforço — "
        "um tubo de ABS com o mesmo diâmetro dobraria ~35 vezes mais (E ≈ 2 GPa contra ≈ 70 GPa) e vibraria à "
        "frequência da passagem das pás (~50 Hz), por isso é COMPRADO, não impresso.",
    "abracadeira_tubo": "Prende o tubo à placa sem o furar (um furo num tubo de carbono sob carga é onde ele parte): as "
        "duas metades apertadas por parafusos agarram o tubo por atrito e mantêm o braço a 45° certos.",
    "perna": "Mantém as hélices, a bateria e os sensores longe do chão na descolagem e na aterragem; o pé espalha o "
        "impacto e não escorrega. A perna é a mesma cápsula que o simulador usa para o contacto com o chão.",
    "suporte_motor": "É a interface entre o motor e o mastro/tubo: os 4 parafusos M3 da base do motor apertam-no, e é por "
        "ele que o empuxo e o binário de reação do motor passam para a estrutura. Centra o motor no eixo para a "
        "hélice rodar equilibrada.",
    "trelica": "Triangula os braços vizinhos: a reação de guinada dos motores e as vibrações laterais deixam de dobrar "
        "cada braço sozinho.",
    "ombro_caixa": "Segura os 2 rolamentos 608ZZ do veio do ombro e o sem-fim à distância EXATA da coroa (21 mm entre "
        "eixos). Se o sem-fim se afastasse da coroa sob carga saltava dentes; se se aproximasse, prendia. É também o "
        "que liga a dobradiça à placa: todo o binário do braço (~9 N·m) passa por esta caixa.",
    "ombro_semfim": "É o que torna o ombro AUTOBLOQUEANTE: o ângulo de avanço do sem-fim (4,8°) é menor do que o ângulo de "
        "atrito (5,7°), por isso o empuxo do braço NÃO consegue rodar o sem-fim para trás. Segurar o braço contra o "
        "empuxo não gasta energia nenhuma — o motor só trabalha quando o braço muda de ângulo. Sem isto o ombro teria "
        "de estar sempre a fazer força (dezenas de W só para não cair) e o voo duraria muito menos.",
    "ombro_veio": "O veio é a DOBRADIÇA do ombro: roda nos dois rolamentos e leva a coroa e o cubo do braço; o íman na "
        "ponta deixa o encoder ler o ângulo real do braço.",
    "ombro_servo": "Dá a força para MUDAR o ângulo do braço. É o ombro que inclina o corpo do drone para apontar a câmara "
        "para cima ou para baixo sem transladar o drone, enquanto os cotovelos mantêm os motores na vertical.",
    "ombro_forquilha": "É a metade fixa da dobradiça do ombro: segura os 2 rolamentos 608ZZ do veio no canto das placas e "
        "passa para o chassis todo o esforço do braço (o empuxo de ~13 N a 0,8 m dá ~6 N·m a pairar e o peso do braço "
        "no chão). Dois rolamentos afastados em vez de um casquilho: o braço não abana e roda sem folga.",
    "ombro_suporte": "Leva o pivô B do atuador preso ao drone, no sítio exato que a geometria da biela pede: se este "
        "ponto se mexesse, o ângulo do braço deixava de corresponder à posição da porca.",
    "ombro_bloco": "É o corpo do atuador linear: segura o motorredutor, o acoplamento e os 2 rolamentos 608ZZ que levam o "
        "IMPULSO AXIAL do fuso (até ~300 N) — o veio do motorredutor não aguenta forças axiais; o munhão deixa o atuador "
        "rodar à medida que o braço sobe e desce.",
    "ombro_motor": "É o motor que muda o ângulo do braço: roda o fuso, e o fuso move a porca, que empurra a alavanca. "
        "Um motorredutor de 12 V com encoder Hall é barato (~13 US$) e o FC fecha a malha de posição com ele e com o "
        "AS5048A do braço. Parado não gasta nada: o fuso autobloqueante segura o braço.",
    "ombro_fuso": "Transforma a rotação do motor em força linear MUITO grande com peças baratas (o mesmo fuso do eixo Z das "
        "impressoras 3D): cada volta avança 2 mm. É AUTOBLOQUEANTE — o ângulo da rosca (5,2°) é menor do que o de atrito "
        "(8,8°): o empuxo não o consegue fazer rodar, por isso o braço fica preso com o motor desligado. É o que um "
        "sem-fim pequeno não conseguia: segurar ~6 N·m sem partir os dentes.",
    "ombro_porca": "A porca de latão anda ao longo do fuso e empurra a alavanca do braço pelo pivô A; o latão desliza no aço "
        "com pouco desgaste e sem gripar. O carro impresso não a deixa rodar — é isso que faz o fuso empurrar em vez de a "
        "levar a rodar com ele.",
    "ombro_encoder": "Mede o ângulo REAL do braço, depois das folgas da transmissão: é este ângulo que o controlo usa para pôr "
        "os motores na vertical enquanto o corpo inclina. Medir no motor não chega (a folga e a flexão da caixa ficam "
        "fora dessa medida).",
    "ombro_cubo": "Liga o veio ao tubo do braço e passa-lhe os ~9 N·m; o aperto por fenda deixa trocar um braço partido "
        "sem desmontar o redutor.",
    "cotovelo_servo": "Inclina o MASTRO para que o motor fique sempre vertical enquanto o braço e o corpo inclinam: é o "
        "que permite apontar o corpo sem o empuxo empurrar o drone para o lado. Como o empuxo passa pelo eixo do "
        "cotovelo, este servo só segura o peso do mastro, o efeito giroscópico e o arrasto (< 0,5 N·m).",
    "cotovelo_garfo": "Liga o servo e o rolamento do lado oposto ao mastro: com dois apoios, o veio do servo deixa de "
        "levar a carga de flexão do mastro (que o partiria) e passa a levar só o binário.",
    "cotovelo_berco": "Prende o servo do cotovelo à ponta do tubo e leva o rolamento 608ZZ do eixo oposto — é a metade "
        "fixa da dobradiça do cotovelo.",
    "cotovelo_encoder": "Mede o ângulo REAL do cotovelo (o servo de passatempo não o devolve ao FC).",
    "mastro": "Põe o motor acima do braço o raio da hélice + 40 mm: a hélice nunca bate no braço em nenhum ângulo do "
        "cotovelo, e o empuxo passa pelo eixo do cotovelo (o servo quase não faz força).",
    "fonte_servos": "Os atuadores dos braços precisam de uma tensão FIXA e o pack varia de 19 a 25,2 V durante o voo: "
        "sem regulador a velocidade e a força dos braços mudariam com a carga da bateria.",
    "motor": "É o único que produz força para voar: transforma a energia da bateria em rotação da hélice. Os 4 juntos têm "
        "de levantar ~2,5× o peso do drone (margem para manobrar e para o vento).",
    "helice": "Gera o empuxo: cada pá é uma asa a rodar. A de 15″ de carbono move muito ar devagar — é o que dá voos "
        "longos com pouca potência (empuxo por watt alto).",
    "esc": "O motor sem escovas precisa de ser comutado nas 3 fases milhares de vezes por segundo no ângulo certo: o ESC "
        "faz isso a partir do comando digital do FC, com o rendimento alto que a autonomia exige.",
    "rpi5": "O computador de bordo: lê a câmara, deteta e segue a bola (o objeto a seguir), planeia o movimento e manda os comandos ao FC. É "
        "ele que torna o drone autónomo (o FC sozinho só estabiliza).",
    "fc": "Estabiliza o drone em tempo real: lê a IMU milhares de vezes por segundo e corrige os 4 motores antes que uma "
        "rajada o incline. Num computador de uso geral (como o Pi) os atrasos do sistema operativo seriam perigosos.",
    "pdb": "Distribui os até ~120 A da bateria pelos 4 ESC com o mínimo de perdas, mede a tensão e a corrente (é daí que "
        "sai a autonomia e o aviso de bateria fraca) e gera os 5 V / 5 A do Raspberry Pi.",
    "camera": "Os olhos do drone: a imagem FPV para quem pilota e para o detetor do objeto a seguir no Pi 5.",
    "sensor_fluxo": "Mede a velocidade horizontal em relação ao chão sem GPS (interior): sem isto o drone derivava "
        "devagar com o vento.",
    "sensor_tof": "Mede a altura ao chão com um laser: o barómetro sozinho tem erros de dezenas de centímetros.",
    "bandeja_sensores": "Segura o fluxo ótico e o laser a olhar para o chão, longe da sombra e da vibração.",
    "bateria": "A única fonte de energia: guarda os ~216 Wh que os motores, a eletrónica e os braços gastam. 21700 de "
        "alta descarga porque o drone puxa ~20–30 A em pairagem e picos acima de 100 A.",
    "cintas_bateria": "Seguram a bateria — a maior massa — contra as acelerações e as aterragens; o tapete não a deixa "
        "escorregar (se a bateria se mexesse, o centro de massa mudava a meio do voo).",
    "cablagem": "Liga energia e sinais com a bitola certa para a corrente: um cabo fino demais aquece e perde tensão.",
    "cabo_bateria": "Leva a corrente toda do drone (até ~120 A) da bateria à placa de energia: 10 AWG para perder pouco.",
    "cabo_esc": "Leva a corrente de cada motor (até ~30 A) da placa de energia ao seu ESC, em 14 AWG para não aquecer, e o "
        "sinal digital do FC ao ESC.",
    "cabo_fases": "As 3 fases que o ESC comuta para fazer rodar o motor sem escovas (16 AWG): trocar duas delas inverte o "
        "sentido de rotação.",
    "cabo_rpi5_5v": "Liga o Raspberry Pi 5 à bateria, através do BEC da placa de energia: é o cabo de que depende o "
        "computador de bordo (5 V / 5 A).",
    "cabo_uart": "É por aqui que o Raspberry Pi manda os comandos ao FC e recebe a telemetria (UART a 921 600 baud): "
        "sem ele o drone não seria autónomo.",
    "cabo_i2c": "O FC lê o INA226 (tensão e corrente da bateria) por aqui: é daí que saem a autonomia que falta e o aviso "
        "de bateria fraca.",
    "fpc_camera": "A fita plana que leva a imagem da câmara ao Raspberry Pi (MIPI CSI-2, 2 vias): tem de passar sem dobras "
        "vivas, que partem as pistas.",
    "cabo_sensores": "Liga o fluxo ótico (SPI) e o laser de distância (I²C) ao FC: são eles que seguram o drone no sítio e à "
        "altura certa sem GPS.",
    "cabo_dxl": "O barramento RS-485 que liga os 8 servos DYNAMIXEL dos braços ao FC e lhes leva os 24 V: um cabo por braço, "
        "em estrela.",
    "cabo_fonte24": "Leva a energia do pack ao regulador de 24 V dos servos dos braços (e daí ao barramento): sem ele os "
        "braços não se mexem.",
    "cabo_atuadores": "Liga os motorredutores, os servos e os encoders dos braços aos drivers e ao FC — energia e sinais "
        "de cada articulação.",
    "manga": "Protege as fases onde elas dobram nas juntas (a manga entrançada não deixa o silicone gastar-se).",
    "abracadeira": "Seguram os cabos ao tubo: um cabo solto bate nas hélices ou parte com a vibração.",
    "bandeja_fonte": "Segura os reguladores dos atuadores (o buck de 12 V e o UBEC) bem presos e afastados das hélices e "
        "dos cabos de potência: um regulador solto partia as soldas com a vibração; a bandeja também o deixa respirar "
        "(aquecem a meia carga).",
    "suporte_driver": "Segura cada driver DRV8871 junto ao seu ombro: os cabos do motor ficam curtos (menos ruído e menos "
        "queda de tensão) e a placa não toca em nenhum metal nem nos parafusos.",
    "ponte_fc": "Põe o FC por cima do Raspberry Pi, nos amortecedores, sem tocar no Active Cooler: o FC precisa de estar "
        "isolado da vibração (a IMU dele é que estabiliza o drone) e o Pi precisa do ar do ventilador.",
    "suporte_camera": "Segura a câmara no nariz, a olhar para a frente com o ângulo certo e sem vibrar — uma imagem tremida "
        "estraga a deteção do objeto a seguir.",
    "cabo_servo": "Leva o sinal PWM do FC e os 6,0 V do UBEC a cada servo do cotovelo (3 fios: castanho GND, vermelho V+, "
        "laranja sinal).",
    "cabo_motorredutor": "Liga cada motorredutor do ombro: M+/M− ao seu driver e o encoder Hall (4 fios) ao FC.",
    "cabo_encoder": "Liga os encoders magnéticos dos braços ao FC (SPI no AS5048A, I²C no AS5600).",
    "controlador_bracos": "O FC de voo não tem entradas para os 12 sensores dos braços (4 encoders Hall, 4 AS5048A, 4 "
        "AS5600 — estes todos no mesmo endereço I²C) nem saídas para os 4 drivers e os 4 servos: cada Pico 2 serve os 2 "
        "braços do seu lado e corre ali a malha de posição dos ombros (a banda morta, o PWM mínimo, a proteção de "
        "bloqueio e a trava dos ombros), e fala com o FC por UART. Custa ~5 US$ e pesa 3 g.",
    "cabo_controlador": "Liga cada controlador dos braços ao FC (UART: os comandos dos ângulos e a telemetria das 4 juntas "
        "do seu lado) e leva-lhe os 5 V do BEC da placa de energia: sem ele o Pico não recebia ordens nem energia.",
    "suporte_controlador": "Segura cada controlador dos braços (o Pico 2 na sua placa de ligação com as fichas JST-GH) "
        "por cima dos drivers do seu lado: os cabos dos sensores e dos drivers ficam curtos e as fichas não se soltam com "
        "a vibração; os insertos M2,5 deixam tirar a placa sem estragar o plástico.",
    "cabo_sensores_braco": "Os cabos dos sensores de cada braço — o encoder Hall do motorredutor, o AS5048A do ombro e o "
        "AS5600 do cotovelo — que dizem ao controlador onde está cada junta: sem eles o FC não fechava a malha de "
        "posição dos braços (terminam em fichas JST-GH).",
    "insertos": "Roscas de latão cravadas a quente nas peças de ABS: um parafuso M3 a roscar direto no plástico estragava a "
        "rosca à segunda montagem e soltava-se com a vibração; o inserto aguenta o binário de aperto e desmontagens.",
    "ferragens": "Parafusos, porcas e anilhas normalizados: é o que mantém tudo junto — e o que se aperta com o binário "
        "certo para não soltar com a vibração.",
}

def catalogo(hw, presentes: list[str]) -> dict:
    """{peça: {nome, categoria, resumo, como_funciona, specs: [[grandeza, valor]], fontes: [...]}} das peças presentes."""
    art = getattr(hw, "bracos", None) is not None
    mot, hel, bat, esc, fr = hw.motor, hw.helice, hw.bateria, hw.esc, hw.frame
    cel = bat.celula
    n_cel = bat.s * bat.p
    v_nom = bat.s * float(_d(cel, "v_nom", 3.6))
    wh = v_nom * bat.p * float(_d(cel, "capacidade_mah", 5000)) / 1000.0
    cons = {c.id: c for c in getattr(hw, "consumidores", [])}
    p: dict[str, dict] = {}

    # ------------------------------------------------------------------ estrutura
    placa = _d(fr, "placa_mm")
    p["placa_inferior"] = {
        "nome": "Placa de baixo (carbono 3K)", "categoria": "estrutura",
        "resumo": f"Placa de fibra de carbono 3K tafetá, {placa or '—'} mm de lado: o «chassis» onde tudo aperta.",
        "como_funciona": "É a placa que leva a carga: as abraçadeiras dos tubos (ou as caixas dos ombros, no "
                         "articulado), os espaçadores, as cintas da bateria e a bandeja dos sensores. A fibra de carbono "
                         "dá rigidez de flexão alta com pouca massa; os furos de alívio tiram massa onde a placa não "
                         "trabalha e os rasgos deixam passar as cintas da bateria.",
        "specs": [["Material", "Fibra de carbono 3K tafetá + epóxi"], ["Lado", f"{placa or '—'} mm"],
                  ["Frame", fr.modelo]],
        "fontes": list(_d(fr, "fontes", []) or [])}
    p["placa_superior"] = {
        "nome": "Placa de cima (carbono)", "categoria": "estrutura",
        "resumo": "A segunda placa do sanduíche: fecha a caixa de torção e leva a pilha de eletrónica"
                  + (" e os 4 servos dos ombros." if art else "."),
        "como_funciona": "As duas placas afastadas pelos espaçadores formam uma caixa: a torção e a flexão do centro do "
                         "drone passam a ser resistidas pelas duas placas em conjunto (o mesmo princípio de uma viga em "
                         "I). A janela central deixa subir os cabos para a pilha de eletrónica.",
        "specs": [["Material", "Fibra de carbono 3K"], ["Fixação", "4 espaçadores M3 + parafusos ISO 4762"]],
        "fontes": []}
    p["espacadores"] = {
        "nome": "Espaçadores das placas", "categoria": "estrutura",
        "resumo": "4 espaçadores de alumínio M3 (fêmea-fêmea) entre as placas.",
        "como_funciona": "Fixam a distância entre as placas e recebem um parafuso M3 de cada lado: apertados, as duas "
                         "placas ficam solidárias.", "specs": [["Rosca", "M3 fêmea nas duas pontas"]], "fontes": []}
    tubo = "25 × 23 mm" if "25" in str(_d(fr, "modelo", fr.modelo)) else "conforme o frame"
    p["tubo_braco"] = {
        "nome": "Tubo do braço (carbono)", "categoria": "estrutura",
        "resumo": f"Tubo de fibra de carbono {tubo} (exterior × interior).",
        "como_funciona": "O braço leva o empuxo do motor ao centro: trabalha à flexão. Um tubo redondo de carbono é a "
                         "forma mais rígida por grama para esse esforço; o de 25 mm aguenta o braço longo do frame de "
                         "1950 mm sem vibrar à frequência das pás.",
        "specs": [["Secção", tubo], ["Comprimento do braço", _fmt(hw.braco * 1000, 0, "mm")]], "fontes": []}
    p["abracadeira_tubo"] = {
        "nome": "Abraçadeira CNC do tubo", "categoria": "estrutura",
        "resumo": "Abraçadeira CNC de alumínio em 2 metades com maxilas que aperta o tubo à placa.",
        "como_funciona": "O tubo fica entre as duas metades; os parafusos com porca apertam-nas uma contra a outra e as "
                         "maxilas agarram o tubo por atrito, sem o furar (o carbono não aguenta furos sob carga). Os "
                         "parafusos verticais prendem a metade de baixo à placa.",
        "specs": [["Material", "Alumínio 6061-T6 anodizado"]], "fontes": []}
    p["perna"] = {
        "nome": "Trem de pouso", "categoria": "estrutura",
        "resumo": "Abraçadeira em T no tubo, perna de carbono Ø12 e pé de borracha.",
        "como_funciona": "Mantém as hélices e a bateria longe do chão; o pé de borracha amortece a aterragem e não "
                         "escorrega. A perna é a mesma cápsula que o MuJoCo usa para o contacto com o chão.",
        "specs": [["Perna", "Tubo de carbono Ø12 mm"], ["Pé", "Borracha EPDM"]], "fontes": []}
    p["suporte_motor"] = {
        "nome": "Placa do motor", "categoria": "estrutura",
        "resumo": "Placa CNC de alumínio onde o motor aparafusa por baixo.",
        "como_funciona": "Os 4 parafusos M3 sobem por baixo da placa e roscam na base do motor; o furo central deixa "
                         "passar o veio/circlip e o rolamento de baixo. Os rasgos aliviam massa.",
        "specs": [["Material", "Alumínio 6061 anodizado"], ["Furação", "a da base do motor (ver Motor)"]], "fontes": []}
    p["trelica"] = {
        "nome": "Varões de travamento", "categoria": "estrutura",
        "resumo": "Varões de carbono de 8 mm entre braços vizinhos.",
        "como_funciona": "Triangulam os braços: o momento de guinada e as vibrações laterais deixam de dobrar cada "
                         "braço sozinho.", "specs": [["Varão", "Carbono Ø8 mm"]], "fontes": []}
    p["estrutura"] = {"nome": "Estrutura (restante)", "categoria": "estrutura", "resumo": "", "como_funciona": "",
                      "specs": [], "fontes": []}

    # ------------------------------------------------------------------ mecanismo
    if art:
        mec = hw.bracos
        so, sc = mec.ombro, mec.cotovelo
        sv = so.servo
        lim_o = so.limites
        lim_c = sc.limites
        p["ombro_caixa"] = {
            "nome": "Ombro — caixa do redutor", "categoria": "mecanismo",
            "resumo": "Caixa de alumínio com 2 rolamentos 6800ZZ no veio de saída e 2 rolamentos 685ZZ no sem-fim.",
            "como_funciona": "É o mancal da dobradiça do ombro: os dois rolamentos 6800 (10 × 19 × 5 mm) seguram o veio "
                             "de saída Ø10 — o EIXO DA DOBRADIÇA — e os dois 685 (5 × 11 × 5 mm) seguram o sem-fim na "
                             "vertical, à distância certa da coroa (entre-eixos = (d₁ + d₂)/2 = 14 mm). A janela de "
                             "policarbonato deixa ver a coroa a engrenar.",
            "specs": [["Rolamentos do veio", "2 × 6800ZZ (10 × 19 × 5 mm)"], ["Rolamentos do sem-fim", "2 × 685ZZ (5 × 11 × 5 mm)"],
                      ["Entre-eixos", "14 mm"], ["Material", "Alumínio 6061 + janela de policarbonato"]],
            "fontes": ["https://www.bearingbasement.com/en/NTN-6800-Deep-Groove-Ball-Bearings-10x19x5mm/m-65889.aspx"]}
        p["ombro_semfim"] = {
            "nome": "Ombro — sem-fim e acoplamento", "categoria": "mecanismo",
            "resumo": f"Sem-fim de aço de 1 entrada, módulo 0,8, d₁ 12 mm, acionado pelo servo — redução {so.reducao:g}:1.",
            "como_funciona": "O servo roda o sem-fim; cada volta do sem-fim avança a coroa UM dente (1 entrada), logo o "
                             f"braço roda {so.reducao:g}× mais devagar e com {so.reducao:g}× o binário (menos as perdas). "
                             f"O ângulo de avanço λ = atan(m·z₁/d₁) = {so.angulo_avanco * 57.2958:.2f}° é menor do que o "
                             f"ângulo de atrito φ = atan(μ) = 5,71° (μ ≈ 0,10, bronze/aço lubrificado): o redutor é "
                             "AUTOBLOQUEANTE — o empuxo do motor não consegue rodar o sem-fim para trás, por isso segurar "
                             "o braço não gasta corrente. Na página o sem-fim gira 20 vezes por cada volta do braço.",
            "specs": [["Módulo", "0,8 mm"], ["Entradas", "1"], ["Ø primitivo", "12 mm (exterior 13,6 mm)"],
                      ["Passo axial", "π·m = 2,51 mm"], ["Redução", f"{so.reducao:g}:1"],
                      ["Autobloqueio", f"λ {so.angulo_avanco * 57.2958:.2f}° < φ 5,71°"],
                      ["Resistência (verificação de 2026-10-20)",
                       ("a pairar o ombro segura ~4,4 N·m → ~550 N no dente da coroa m0,8 (Ø16): σ ≈ 380 MPa pela "
                        "fórmula de Lewis — o bronze NÃO aguenta. O build acessível (articulado_15pol_abs) troca-o por um "
                        "fuso Tr8×2 numa alavanca.")]],
            "fontes": ["https://www.motioncontroltips.com/when-are-worm-gears-self-locking-and-where-is-this-useful"]}
        p["ombro_veio"] = {
            "nome": "Ombro — veio, coroa e íman", "categoria": "mecanismo",
            "resumo": "Veio de aço Ø10, coroa de bronze de 20 dentes e o íman diametral do encoder — rodam com o braço.",
            "como_funciona": "A coroa (z₂ = 20, d₂ = 16 mm) está presa ao veio; o veio roda nos rolamentos 6800 e leva o "
                             "cubo do braço. Na ponta de dentro, um íman diametral Ø6 roda à frente do AS5048A: o "
                             "encoder mede o ângulo REAL do braço (a jusante da folga do redutor).",
            "specs": [["Veio", "Aço Ø10 mm"], ["Coroa", "Bronze, z = 20, m 0,8, d₂ 16 mm"],
                      ["Íman", "NdFeB Ø6 × 2,5 mm diametral"]], "fontes": []}
        p["ombro_servo"] = {
            "nome": f"Ombro — servo {sv.modelo}", "categoria": "mecanismo",
            "resumo": f"{sv.fabricante} {sv.modelo}: {sv.binario_bloqueio:g} N·m de bloqueio a {sv.tensao:g} V, "
                      f"{sv.massa * 1000:g} g, deitado na placa de cima com o horn para baixo.",
            "como_funciona": "Servo inteligente com motor coreless, redutor metálico, encoder absoluto de 4096 passos e "
                             "controlador PID próprio no barramento RS-485 (Protocol 2.0). O horn desce pelo furo da "
                             "placa e aciona o sem-fim por um acoplamento aparafusado.",
            "specs": [["Binário de bloqueio", f"{sv.binario_bloqueio:g} N·m @ {sv.tensao:g} V"],
                      ["Velocidade em vazio", _fmt(sv.omega_vazio * 60 / 6.2832, 0, "rpm")],
                      ["Massa", _fmt(sv.massa * 1000, 0, "g")], ["Medidas", "28,5 × 46,5 × 34 mm"],
                      ["Encoder", "absoluto 4096 passos/volta"]],
            "fontes": list(_d(sv, "fontes", []) or [])}
        p["ombro_encoder"] = {
            "nome": "Ombro — encoder AS5048A", "categoria": "mecanismo",
            "resumo": "Sensor magnético absoluto de 14 bits na ponta do veio do ombro.",
            "como_funciona": "Um sensor de efeito Hall mede a direção do campo do íman diametral que roda à frente dele "
                             "(entreferro 0,5–2 mm): dá o ângulo absoluto do braço com 0,02° de resolução, sem contacto.",
            "specs": [["Resolução", "14 bits (16384/volta)"], ["Placa", "28 × 22 mm, 4 furos de 2,6 mm"],
                      ["Entreferro", "0,5–2 mm"]],
            "fontes": ["https://docs.rs-online.com/0657/A700000006921305.pdf"]}
        p["ombro_cubo"] = {
            "nome": "Ombro — cubo do braço", "categoria": "mecanismo",
            "resumo": "Cubo de alumínio (laranja: as peças que RODAM) que liga o veio ao tubo do braço.",
            "como_funciona": "Aperta o veio pela fenda do cubo e recebe o tubo do braço no encaixe; o ponteiro vermelho "
                             f"sobre a escala gravada mostra o ângulo do ombro ({lim_o[0]:g}…{lim_o[1]:g}°).",
            "specs": [["Curso", f"{lim_o[0]:g}° a {lim_o[1]:g}°"]], "fontes": []}
        p["cotovelo_servo"] = {
            "nome": f"Cotovelo — servo {sc.servo.modelo}", "categoria": "mecanismo",
            "resumo": "O servo É o pivô do cotovelo: horn de um lado, idler do outro, eixo = eixo da dobradiça.",
            "como_funciona": "O empuxo passa pelo eixo do cotovelo, por isso este servo só segura o peso do mastro, o "
                             "efeito giroscópico e o arrasto (< 0,5 N·m): vai direto, sem redutor. O idler do lado "
                             "oposto (com rolamento) fecha o garfo e tira a carga radial do veio do servo.",
            "specs": [["Curso", f"{lim_c[0]:g}° a {lim_c[1]:g}°"], ["Acionamento", "direto (1:1)"]],
            "fontes": list(_d(sc.servo, "fontes", []) or [])}
        p["cotovelo_garfo"] = {
            "nome": "Cotovelo — garfo", "categoria": "mecanismo",
            "resumo": "Garfo de alumínio (padrão do FR12-H101K da ROBOTIS) aparafusado ao horn e ao idler.",
            "como_funciona": "As duas faces do garfo aparafusam uma ao horn (que roda com o servo) e a outra ao idler; o "
                             "mastro sai do topo do garfo. Assim o mastro roda exatamente no eixo do servo.",
            "specs": [["Material", "Alumínio anodizado"]],
            "fontes": ["https://robotis.us/products/fr12-h101k-set"]}
        p["mastro"] = {
            "nome": "Mastro do motor", "categoria": "mecanismo",
            "resumo": f"Tubo de carbono Ø16 que leva o motor no topo, ao raio da hélice + {mec.folga_helice * 1000:g} mm.",
            "como_funciona": "Põe o motor acima do braço o suficiente para a hélice nunca bater nele, em qualquer ângulo "
                             "do cotovelo; as abraçadeiras de alumínio apertam-no ao garfo e à placa do motor.",
            "specs": [["Tubo", "Carbono Ø16 mm"], ["Massa", _fmt(mec.massa_mastro * 1000, 0, "g")]], "fontes": []}
        p["fonte_servos"] = {
            "nome": "Regulador 24 V / 5 A dos servos", "categoria": "eletronica",
            "resumo": "Conversor buck-boost: o pack varia de 19 a 25,2 V, os servos querem 24 V estáveis.",
            "como_funciona": "Comuta um MOSFET a centenas de kHz numa bobina toroidal (buck-boost): sobe ou desce a "
                             "tensão consoante o pack, com ~92 % de eficiência. Alimenta em estrela os 4 servos dos "
                             "ombros; cada ombro passa o barramento ao cotovelo.",
            "specs": [["Saída", f"{mec.fonte_tensao:g} V / 5 A"], ["Eficiência", _fmt(mec.fonte_eficiencia * 100, 0, "%")],
                      ["Massa", _fmt(mec.massa_fonte * 1000, 0, "g")]], "fontes": []}

    # ------------------------------------------------------------------ propulsão
    dm = mot.dados
    p["motor"] = {
        "nome": f"Motor {mot.fabricante} {mot.modelo}", "categoria": "propulsao",
        "resumo": f"Outrunner sem escovas {mot.kv:g} KV, Φ{_fmt(dm.get('diametro_mm'), 2)} × {_fmt(dm.get('altura_mm'), 1)} mm, "
                  f"{mot.massa * 1000:g} g.",
        "como_funciona": "O estator (bobinas de cobre fixas na base) cria um campo magnético rotativo comutado pelo ESC; "
                         "os ímanes colados por dentro do sino (o rotor, por fora) seguem esse campo e o sino roda com a "
                         "hélice. KV = rpm por volt sem carga: com 6S (22,2 V) roda até ≈ "
                         f"{mot.kv * 22.2:,.0f} rpm em vazio. O topo em raios funciona como ventoinha centrífuga e "
                         "arrefece as bobinas.".replace(",", " "),
        "specs": [["Modelo", f"{mot.fabricante} {mot.modelo}"], ["KV", f"{mot.kv:g} rpm/V"],
                  ["Medidas", f"Φ{_fmt(dm.get('diametro_mm'), 2)} × {_fmt(dm.get('altura_mm'), 1)} mm"],
                  ["Configuração", dm.get("configuracao", "—")], ["Massa", _fmt(mot.massa * 1000, 0, "g")],
                  ["Corrente máx.", _fmt(mot.i_max, 1, "A")], ["Potência máx.", _fmt(mot.p_max, 0, "W")],
                  ["Resistência interna", _fmt(mot.r_int * 1000, 0, "mΩ")]],
        "fontes": list(dm.get("fontes", []) or [])}
    p["helice"] = {
        "nome": f"Hélice {hel.fabricante} {hel.modelo}", "categoria": "propulsao",
        "resumo": f"{hel.pas} pás de fibra de carbono, {_fmt(hel.diametro * 39.37, 0)}″ × {_fmt(hel.passo * 39.37, 1)}″, "
                  f"{hel.massa * 1000:g} g.",
        "como_funciona": "Cada pá é uma asa a rodar: o perfil arqueado e a torção (passo geométrico P = 2πr·tan θ, "
                         "constante ao longo da pá) dão o mesmo ângulo de ataque efetivo da raiz à ponta. O empuxo "
                         "cresce com ω² (T = k_f·ω²). Presa ao topo do motor por 2 parafusos M3 e um pino de centragem.",
        "specs": [["Diâmetro × passo", f"{_fmt(hel.diametro * 1000, 0)} × {_fmt(hel.passo * 1000, 0)} mm"],
                  ["Pás", str(hel.pas)], ["Massa", _fmt(hel.massa * 1000, 1, "g")], ["Material", "Carbono + epóxi"]],
        "fontes": list(_d(hel, "fontes", []) or [])}
    p["esc"] = {
        "nome": f"ESC {esc.fabricante} {esc.modelo}", "categoria": "propulsao",
        "resumo": "Controlador eletrónico de velocidade (um por motor, deitado ao longo do braço).",
        "como_funciona": "6 MOSFETs em ponte trifásica comutam a tensão do pack nas 3 fases do motor; o MCU lê a "
                         "posição do rotor pela força contra-eletromotriz (sem sensores) e segue o comando DShot do FC. "
                         "O condensador eletrolítico na entrada absorve os picos de corrente da comutação.",
        "specs": [["Corrente máx.", _fmt(esc.i_max, 0, "A")], ["Protocolo", f"DShot{esc.dshot_bits if esc.dshot_bits else ''}"],
                  ["Eficiência", _fmt(esc.eficiencia * 100, 0, "%")]],
        "fontes": list(_d(esc, "fontes", []) or [])}

    # ------------------------------------------------------------------ eletrónica
    if "rpi5" in cons:
        p["rpi5"] = {
            "nome": "Raspberry Pi 5 + Active Cooler", "categoria": "eletronica",
            "resumo": "O computador de bordo: visão, planeamento e a ponte para o FC.",
            "como_funciona": "BCM2712 (4 × Cortex-A76 a 2,4 GHz) com o RP1 (o chip das E/S). Recebe a câmara pelo "
                             "MIPI CSI-2 (FPC de 22 vias), fala com o FC por UART (GPIO 14/15) e é ALIMENTADO A 5 V / 5 A "
                             "pelo USB-C a partir do BEC da placa de energia — que por sua vez vem da bateria pelo XT90: "
                             "bateria → XT90 → 10 AWG → placa de energia → BEC 5 V → cabo USB-C → Pi. O Active Cooler "
                             "(dissipador de alumínio + ventoinha radial de 30 mm) mantém o SoC abaixo de ~70 °C.",
            "specs": [["SoC", "Broadcom BCM2712, 4 × Cortex-A76 2,4 GHz"], ["Placa", "85 × 56 mm"],
                      ["Alimentação", "5 V / 5 A (USB-C, USB PD 27 W)"], ["Potência em voo", _fmt(cons['rpi5'].potencia.get('voo'), 1, "W")],
                      ["Fixação", "4 pilares M2,5 de latão (furação 58 × 49 mm)"]],
            "fontes": ["https://pip.raspberrypi.com/documents/RP-008347-DS-1-raspberry-pi-5-mechanical-drawing.pdf",
                       "https://pip.raspberrypi.com/documents/RP-008188-DS-active-cooler-product-brief.pdf"]}
    if "fc_h7" in cons:
        p["fc"] = {
            "nome": "Controlador de voo H7 (30 × 30)", "categoria": "eletronica",
            "resumo": "STM32H743 + IMU BMI088: estabiliza o drone a 1–8 kHz.",
            "como_funciona": "Lê a IMU (giroscópio + acelerómetro), corre a cascata de controlo (atitude → taxa → "
                             "misturador) e manda o DShot aos 4 ESC. Assenta em amortecedores de silicone (isolam a IMU "
                             "da vibração das hélices) na pilha M3 de nylon.",
            "specs": [["MCU", "STM32H743 (480 MHz)"], ["IMU", "BMI088"], ["Furação", "30,5 × 30,5 mm, M3"]],
            "fontes": ["https://docs.px4.io/main/en/flight_controller/zenfc_h743"]}
    if "cablagem" in cons:
        p["pdb"] = {
            "nome": "Placa de energia (PM + BEC 5 V / 5 A)", "categoria": "eletronica",
            "resumo": "Distribui a bateria aos 4 ESC, mede V/I (shunt + INA226) e gera os 5 V do Raspberry Pi.",
            "como_funciona": "As ilhas da bateria (10 AWG do XT90) ligam-se por cobre largo às ilhas de cada ESC. Um "
                             "shunt de poucos mΩ no negativo dá a corrente (INA226 por I²C ao FC). O BEC síncrono (CI + "
                             "bobina blindada + condensadores de polímero) baixa a tensão do pack para 5,1 V / 5 A: é "
                             "dele que sai o cabo USB-C do Raspberry Pi 5.",
            "specs": [["Entrada", f"{bat.s}S ({_fmt(bat.s * 3.0, 0)}–{_fmt(bat.s * 4.2, 1)} V)"], ["BEC", "5,1 V / 5 A"],
                      ["Medição", "INA226 + shunt"]], "fontes": []}
    if hw.camera is not None:
        p["camera"] = {
            "nome": hw.camera.nome, "categoria": "eletronica",
            "resumo": "A câmara do nariz: o FPV e os olhos do «seguir a bola».",
            "como_funciona": "O sensor envia as imagens pelo FPC ao conector CAM/DISP do Raspberry Pi (MIPI CSI-2); o "
                             "suporte em L de PETG aperta a placa com 4 parafusos M2 e deixa o FPC passar por baixo.",
            "specs": [["Sensor", str(hw.camera.dados.get("sensor", "—"))], ["FoV", str(hw.camera.dados.get("fov_graus", "—"))],
                      ["Interface", str(hw.camera.dados.get("interface", "—"))]],
            "fontes": list(hw.camera.dados.get("fontes", []) or [])}
    sens = getattr(hw, "sensores", {}) or {}
    if "fluxo" in sens:
        p["sensor_fluxo"] = {"nome": "Fluxo ótico PMW3901", "categoria": "eletronica",
                             "resumo": "Câmara de 30 × 30 px virada para o chão: mede a velocidade horizontal.",
                             "como_funciona": "Compara imagens sucessivas do chão (até 121 fps) e devolve o deslocamento "
                                              "em píxeis; com a altura do ToF dá a velocidade em m/s.",
                             "specs": [["Placa", "24 × 24 × 5 mm"]], "fontes": []}
    if "tof" in sens:
        p["sensor_tof"] = {"nome": "Distância laser VL53L1X", "categoria": "eletronica",
                           "resumo": "Tempo de voo de um laser de 940 nm: a altura ao chão até 4 m.",
                           "como_funciona": "Mede o tempo que os fotões do laser VCSEL levam a voltar ao SPAD.",
                           "specs": [["Placa", "13 × 18 × 2 mm (Pololu)"]], "fontes": ["https://www.pololu.com/product/3415"]}
    p["bandeja_sensores"] = {"nome": "Bandeja dos sensores", "categoria": "eletronica",
                             "resumo": "PETG impresso, presa pelas cintas da bateria.", "como_funciona": "",
                             "specs": [], "fontes": []}

    # ------------------------------------------------------------------ energia
    p["bateria"] = {
        "nome": f"Bateria {bat.s}S{bat.p}P {cel.fabricante} {cel.modelo}", "categoria": "energia",
        "resumo": f"{n_cel} células ({bat.s} em série × {bat.p} em paralelo), {_fmt(v_nom, 1)} V nominais, ≈ {_fmt(wh, 0)} Wh.",
        "como_funciona": f"Cada grupo de {bat.p} células em PARALELO soma as capacidades; os {bat.s} grupos em SÉRIE somam "
                         f"as tensões ({bat.s} × {_fmt(_d(cel, 'v_nom', 3.6), 2)} V). As fitas de níquel soldadas por pontos "
                         "ligam os polos; o balanceador leva um fio a cada junção entre grupos (S + 1 fios) para o "
                         "carregador igualar as células. Os cabos principais saem do primeiro e do último grupo para o "
                         "XT90.",
        "specs": [["Configuração", f"{bat.s}S{bat.p}P ({n_cel} células)"], ["Célula", f"{cel.fabricante} {cel.modelo}"],
                  ["Medidas da célula", " × ".join(_fmt(x, 2) for x in (_d(cel, 'dims_mm') or [])) + " mm"],
                  ["Tensão", f"{_fmt(bat.s * float(_d(cel, 'v_corte', 2.5)), 1)}–{_fmt(bat.s * float(_d(cel, 'v_max', 4.2)), 1)} V"],
                  ["Energia", _fmt(wh, 0, "Wh")], ["Corrente máx.", _fmt(bat.p * float(_d(cel, 'i_max_a', 0)), 0, "A")],
                  ["Conector", "XT90 + balanceador JST-XH"]],
        "fontes": list(_d(cel, "fontes", []) or [])}
    p["cintas_bateria"] = {"nome": "Cintas e tapete da bateria", "categoria": "energia",
                           "resumo": "2 cintas de 15 mm com fivela + tapete anti-derrapante.",
                           "como_funciona": "As cintas passam pelos rasgos da placa de baixo e apertam o pack contra o "
                                            "tapete de borracha, que não o deixa escorregar com as acelerações.",
                           "specs": [], "fontes": []}

    # ------------------------------------------------------------------ cablagem
    p["cablagem"] = {"nome": "Cablagem", "categoria": "cablagem",
                     "resumo": "Fios de silicone (10/14/16/20 AWG), sinais JST-GH, FPC da câmara, barramento DYNAMIXEL.",
                     "como_funciona": "A bitola segue a corrente: 10 AWG da bateria (até ~120 A em picos), 14 AWG para "
                                      "cada ESC, 16 AWG nas fases dos motores, 20 AWG nos 5 V do Pi. Nas juntas os cabos "
                                      "passam pelo eixo da dobradiça (o laço de serviço).",
                     "specs": [], "fontes": []}
    p["cabo_rpi5_5v"] = {"nome": "Cabo de alimentação do Raspberry Pi (USB-C)", "categoria": "cablagem",
                         "resumo": "Do BEC 5 V da placa de energia à ficha USB-C do Pi.",
                         "como_funciona": "Par 20 AWG (vermelho 5 V, preto GND) soldado à saída do BEC e à ficha USB-C "
                                          "que encaixa no conector de alimentação do Raspberry Pi 5.",
                         "specs": [["Bitola", "20 AWG"], ["Tensão", "5,1 V"], ["Corrente", "até 5 A"]], "fontes": []}
    p["abracadeira"] = {"nome": "Abraçadeira de nylon", "categoria": "cablagem",
                        "resumo": "Fita de nylon 66 com dentes e cabeça de lingueta: segura os cabos ao tubo.",
                        "como_funciona": "A fita entra na cabeça; a lingueta morde os dentes e só deixa apertar. "
                                         "Apertada, a fita assenta nos cabos e no tubo e o excesso corta-se rente à "
                                         "cabeça.", "specs": [["Medida", "2,5 × 100 mm"]], "fontes": []}
    p["ferragens"] = {"nome": "Ferragens", "categoria": "estrutura", "resumo": "Parafusos, porcas, anilhas e pilares.",
                      "como_funciona": "", "specs": [], "fontes": []}

    p["outros"] = {"nome": "Outros", "categoria": "outros", "resumo": "", "como_funciona": "", "specs": [], "fontes": []}

    if acessivel(hw):
        _fichas_acessivel(hw, p)
    for pid, nome, cat_, resumo in (
            ("bandeja_fonte", "Bandeja dos reguladores (ABS impresso)", "eletronica",
             "Bandeja impressa em ABS para o buck de 12 V e o UBEC dos atuadores."),
            ("suporte_driver", "Suporte do driver DRV8871 (ABS impresso)", "eletronica",
             "Suporte impresso em ABS de um driver de motor DC, junto ao seu ombro."),
            ("ponte_fc", "Ponte do FC (ABS impresso)", "eletronica",
             "Ponte impressa em ABS que eleva o FC por cima do Raspberry Pi, nos amortecedores."),
            ("suporte_camera", "Suporte da câmara (ABS impresso)", "eletronica",
             "Suporte impresso em ABS da câmara FPV, no nariz."),
            ("cabo_servo", "Cabos dos servos dos cotovelos", "cablagem", "Cabos de 3 fios 22 AWG (GND, V+, sinal)."),
            ("cabo_motorredutor", "Cabos dos motorredutores dos ombros", "cablagem",
             "6 fios: M+/M− ao driver e o encoder Hall (GND, VCC, A, B) ao FC."),
            ("cabo_encoder", "Cabos dos encoders dos braços", "cablagem", "SPI (AS5048A) e I²C (AS5600) até ao FC."),
            ("cabo_controlador", "Cabos dos controladores dos braços (UART + 5 V)", "cablagem",
             "JST-SH de 4 vias do FC a cada Pico 2 e o Y de 5 V a partir do BEC da placa de energia."),
            ("suporte_controlador", "Suporte do controlador dos braços (ABS impresso)", "eletronica",
             "Base impressa em ABS com 4 colunas e insertos M2,5 para a placa de ligação do Pico 2; 2 × M3 na placa de cima."),
            ("controlador_bracos", "Controladores dos braços (2 × Raspberry Pi Pico 2)", "eletronica",
             "Um Pico 2 (RP2350, 51 × 21 mm) por lado: drivers, servos e sensores dos 2 braços desse lado; UART ao FC."),
            ("cabo_sensores_braco", "Cabos dos sensores dos braços", "cablagem",
             "Encoder Hall (4 fios), AS5048A (SPI, 5 fios) e AS5600 (I²C, 4 fios) de cada braço, com fichas JST-GH."),
            ("cabo_atuadores", "Alimentação dos atuadores dos braços", "cablagem",
             "Do pack aos 2 bucks de 12 V, dos bucks aos 4 drivers e do UBEC aos servos dos cotovelos."),
            ("cabo_bateria", "Cabo da bateria (10 AWG)", "cablagem",
             "Par de 10 AWG de silicone do XT90 às ilhas da placa de energia."),
            ("cabo_esc", "Cabos dos ESC (14 AWG + sinal)", "cablagem",
             "14 AWG da placa de energia a cada ESC e o par de sinal do FC."),
            ("cabo_fases", "Fases dos motores (16 AWG)", "cablagem", "3 fios de 16 AWG por motor, com balas de 3,5 mm."),
            ("cabo_i2c", "Cabo I²C do monitor de energia", "cablagem", "4 fios do FC ao INA226."),
            ("cabo_sensores", "Cabos dos sensores de baixo", "cablagem", "Do FC ao fluxo ótico e ao laser de distância."),
            ("cabo_uart", "Cabo UART Raspberry Pi ↔ FC", "cablagem", "Dupont no GPIO do Pi, JST-GH no FC."),
            ("fpc_camera", "Fita FPC da câmara", "cablagem", "FPC de 22 → 15 vias (16 → 11,5 mm) da câmara ao CAM/DISP 0."),
            ("manga", "Manga entrançada das fases", "cablagem", "Protege as fases ao longo dos braços e nas juntas."),
            ("cabo_dxl", "Barramento dos servos DYNAMIXEL", "cablagem", "RS-485 + 24 V, um cabo por braço."),
            ("cabo_fonte24", "Alimentação do regulador de 24 V", "cablagem", "Do pack ao regulador dos servos."),
            ("cotovelo_encoder", "Cotovelo — encoder AS5600", "mecanismo",
             "Encoder magnético de 12 bits na ponta do parafuso M8 do cotovelo (I²C).")):
        if pid in presentes and pid not in p:
            p[pid] = {"nome": nome, "categoria": cat_, "resumo": resumo, "como_funciona": "", "specs": [], "fontes": []}
    for pid in presentes:                       # peças sem ficha: nome legível a partir do id
        if pid not in p:
            p[pid] = {"nome": pid.replace("_", " ").capitalize(), "categoria": "outros", "resumo": "",
                      "como_funciona": "", "specs": [], "fontes": []}
    for pid, f in p.items():
        f.setdefault("porque", PORQUE.get(pid, ""))
    return {k: v for k, v in p.items() if k in presentes}


def _fichas_acessivel(hw, p: dict) -> None:
    """As fichas que mudam na versão ACESSÍVEL (ABS impresso + atuadores de catálogo comum)."""
    mec = hw.bracos
    for pid in ("placa_inferior", "placa_superior"):
        if pid in p:
            p[pid]["nome"] = p[pid]["nome"].replace("(carbono 3K)", "(ABS impresso)").replace("(carbono)", "(ABS impresso)")
            p[pid]["resumo"] = ("Impressa em ABS com nervuras — cabe numa impressora de mesa de 220 × 220 mm; insertos "
                                "de latão M3 cravados a quente onde os parafusos roscam.")
            p[pid]["specs"] = [["Material", "ABS (o plástico das peças LEGO)"],
                               ["Impressão", "paredes 1,2 mm · enchimento 40 % · camada 0,2 mm"],
                               ["Fixação", "insertos de latão M3 + parafusos ISO 4762"]]
    if "espacadores" in p:
        p["espacadores"]["nome"] = "Colunas entre as placas (ABS)"
        p["espacadores"]["resumo"] = "Colunas impressas em ABS com insertos M3 nas pontas."
    if "suporte_motor" in p:
        p["suporte_motor"]["nome"] = "Suporte do motor (ABS impresso)"
        p["suporte_motor"]["specs"] = [["Material", "ABS impresso"], ["Furação", "a da base do motor (padrão real)"]]
    if "perna" in p:
        p["perna"]["resumo"] = "Varão de carbono Ø12 (comprado) com a abraçadeira e o pé impressos em ABS."
    if mec is None:
        return
    so, sc = mec.ombro, mec.cotovelo
    fz = so.fuso
    srv = so.servo
    if fz is not None:
        sd = srv.dados or {}
        ped = {
            "ombro_forquilha": {
                "nome": "Ombro — forquilha da dobradiça (ABS impresso)", "categoria": "mecanismo",
                "resumo": "Forquilha impressa em ABS aparafusada às placas (insertos M3), com os 2 rolamentos 608ZZ do veio.",
                "como_funciona": "Os 608ZZ (8 × 22 × 7 mm, os de skate) entram à pressão nas sedes impressas; o veio Ø8 atravessa "
                                 "os dois e o cubo do braço roda entre eles.",
                "specs": [["Material", "ABS impresso"], ["Rolamentos", "2 × 608ZZ"], ["Fixação", "insertos M3 + ISO 4762"]],
                "fontes": []},
            "ombro_veio": {
                "nome": "Ombro — veio Ø8 da dobradiça", "categoria": "mecanismo",
                "resumo": "Varão retificado Ø8 (o das impressoras 3D) ou parafuso M8, com colares/porca a fixar e o íman do "
                          "encoder na ponta.",
                "como_funciona": "É o eixo da junta `ombro` do simulador; roda nos 608ZZ da forquilha.",
                "porque": "É o eixo da dobradiça do ombro: o braço roda nele, apoiado nos dois 608ZZ da forquilha, e o íman "
                          "na ponta deixa o AS5048A ler o ângulo REAL do braço.",
                "specs": [["Veio", "aço Ø8 h8"], ["Retenção", "colares Ø8 com perno M4"]], "fontes": []},
            "ombro_cubo": {
                "nome": "Ombro — cubo do braço com a alavanca (ABS impresso)", "categoria": "mecanismo",
                "resumo": f"Cubo impresso em ABS que aperta o tubo Ø25 (fenda + M4) e tem a alavanca de "
                          f"{1000 * math.hypot(fz.alavanca[0], fz.alavanca[2]):.0f} mm onde a porca empurra.",
                "como_funciona": "A porca do fuso empurra a ponta da alavanca (pivô A, parafuso de ombro M4 em 2 rolamentos "
                                 "MR84ZZ); a alavanca roda o cubo e o braço em torno do veio.",
                "porque": (f"Prende o tubo do braço ao veio e tem a ALAVANCA onde o atuador empurra: é por ela que o fuso "
                           f"consegue segurar o braço. Quanto mais comprida a alavanca, menos força a porca faz (a pairar "
                           f"~{7.0 / max(abs(fz.derivada(0.0)), 1e-3):.0f} N), mas mais o fuso tem de rodar para o mesmo "
                           f"ângulo — {1000 * math.hypot(fz.alavanca[0], fz.alavanca[2]):.0f} mm é o compromisso entre a "
                           f"força e a velocidade do braço que cabe sem colisões em todo o curso."),
                "specs": [["Material", "ABS impresso (enchimento 40 %)"],
                          ["Braço de alavanca efetivo", (f"{1000 * fz.braco_minimo(so.limites):.0f}–"
                                                         f"{1000 * abs(fz.derivada(0.0)):.0f} mm no curso")]],
                "fontes": []},
            "ombro_suporte": {
                "nome": "Ombro — suporte do pivô do atuador (ABS impresso)", "categoria": "mecanismo",
                "resumo": "Suporte impresso aparafusado às placas que leva o pivô B (munhão) do atuador.",
                "como_funciona": "", "specs": [["Material", "ABS impresso"]], "fontes": []},
            "ombro_bloco": {
                "nome": "Ombro — corpo do atuador linear (ABS impresso)", "categoria": "mecanismo",
                "resumo": "Peça impressa que junta o motorredutor (6 × M3 na face), o acoplamento e os 2 × 608ZZ que "
                          "seguram o fuso, com o munhão do pivô B.",
                "como_funciona": "O fuso passa nos dois 608ZZ e dois colares Ø8 prendem-no axialmente: o impulso da porca "
                                 "vai para os rolamentos e para a peça, não para o motor.",
                "specs": [["Material", "ABS impresso"], ["Rolamentos", "2 × 608ZZ (axial ≈ 0,5 × C₀ = 0,7 kN)"],
                          ["Pivô B", "2 × parafuso de ombro M4 + 2 × 684ZZ"]], "fontes": []},
            "ombro_motor": {
                "nome": f"Ombro — {srv.modelo}", "categoria": "mecanismo",
                "resumo": f"Motorredutor DC com encoder Hall de 11 PPR ({srv.massa * 1000:.0f} g), alimentado a "
                          f"{srv.tensao:g} V por um driver DRV8871.",
                "como_funciona": "O FC manda PWM ao DRV8871 e fecha a malha de posição com o encoder Hall do motor e o "
                                 "AS5048A do braço; dentro de ±0,05° o driver desliga e o fuso segura.",
                "specs": [["Tensão", f"{srv.tensao:g} V"],
                          ["Vazio", _fmt(srv.omega_vazio * 60 / 6.2832, 0, "rpm")],
                          ["Bloqueio", f"{srv.binario_bloqueio:g} N·m · {srv.corrente_bloqueio:g} A"],
                          ["Redutor", f"Ø37 × {float((sd.get('redutor_mm') or {}).get('comprimento', 21)):g} mm, 1:{srv.reducao_interna:g}"],
                          ["Veio", "Ø6 em D, excêntrico"], ["Massa", _fmt(srv.massa * 1000, 0, "g")]],
                "fontes": list(sd.get("fontes", []) or [])},
            "ombro_fuso": {
                "nome": "Ombro — fuso trapezoidal Tr8×2 + acoplamento", "categoria": "mecanismo",
                "resumo": f"Fuso inox Tr8×2 (1 entrada, 2 mm por volta) de {fz.comprimento * 1000:.0f} mm, ligado ao motor "
                          "por um acoplamento flexível 6 → 8 mm.",
                "como_funciona": f"λ = atan(p/(π·d₂)) = {math.degrees(fz.angulo_avanco):.1f}° < φ' = atan(μ/cos 15°) = "
                                 f"{math.degrees(math.atan(fz.atrito_efetivo)):.1f}° (μ = {fz.coef_atrito:g}, latão/aço "
                                 f"lubrificado): AUTOBLOQUEANTE, rendimento η = {so.eficiencia_subir:.2f}. A «redução» "
                                 f"varia com o ângulo: N(q) = 2π·L'(q)/p ≈ {so.reducao:.0f} com o braço a 0.",
                "specs": [["Rosca", "Tr8×2 (d₂ = 7,0 mm)"], ["Comprimento", _fmt(fz.comprimento * 1000, 0, "mm")],
                          ["Binário no braço (bloqueio, braço a 0)", _fmt(so.binario_bloqueio_saida, 1, "N·m")],
                          ["Velocidade do braço em vazio", _fmt(math.degrees(so.omega_vazio_saida), 0, "°/s")],
                          ["Acoplamento", "flexível 6 → 8 mm, Ø19 × 25 mm"]], "fontes": []},
            "ombro_porca": {
                "nome": "Ombro — porca de latão e carro (pivô A)", "categoria": "mecanismo",
                "resumo": "Porca de latão Tr8×2 de flange (Ø22, 4 × Ø3,5 a Ø16) aparafusada a um carro impresso com o pivô "
                          "para a alavanca.",
                "como_funciona": "", "specs": [["Porca", "latão, flange Ø22 × 3,5, corpo Ø10,2 × 15 mm"],
                                               ["Pivô A", "parafuso de ombro M4 + 2 × MR84ZZ"]], "fontes": []},
        }
        for k_, v_ in ped.items():               # o `catalogo` fica só com as presentes neste modelo
            p[k_] = v_
    if "cotovelo_servo" in p:
        s2 = sc.servo
        p["cotovelo_servo"] = {
            "nome": f"Cotovelo — servo {s2.modelo}", "categoria": "mecanismo",
            "resumo": f"Servo de passatempo de engrenagens metálicas ({s2.binario_bloqueio:g} N·m a {s2.tensao:g} V, "
                      f"{s2.massa * 1000:.0f} g).",
            "como_funciona": "Recebe um impulso PWM de 500–2500 µs (o ângulo); o eixo oposto do garfo roda num 608ZZ e "
                             "um AS5600 mede o ângulo real.",
            "specs": [["Binário de bloqueio", f"{s2.binario_bloqueio:g} N·m @ {s2.tensao:g} V"],
                      ["Velocidade em vazio", _fmt(s2.omega_vazio * 60 / 6.2832, 0, "rpm")],
                      ["Curso", f"{sc.limites[0] * 57.2958:.0f}° a {sc.limites[1] * 57.2958:.0f}°"],
                      ["Massa", _fmt(s2.massa * 1000, 0, "g")]], "fontes": list(_d(s2, "fontes", []) or [])}
    if "cotovelo_garfo" in p:
        p["cotovelo_garfo"]["nome"] = "Cotovelo — garfo (ABS impresso)"
        p["cotovelo_garfo"]["resumo"] = ("Garfo em U impresso em ABS: aparafusado ao horn 25T do servo de um lado e "
                                         "a rodar num 608ZZ com um parafuso M8 do outro.")
        p["cotovelo_garfo"]["specs"] = [["Material", "ABS impresso"], ["Eixo oposto", "608ZZ + parafuso M8 + porca autoblocante"]]
    if "cotovelo_berco" not in p:
        p["cotovelo_berco"] = {"nome": "Cotovelo — berço do servo (ABS impresso)", "categoria": "mecanismo",
                               "resumo": "Berço impresso em ABS apertado à ponta do tubo; leva o servo e o 608ZZ.",
                               "como_funciona": "", "specs": [["Material", "ABS impresso"]], "fontes": []}
    if "fonte_servos" in p:
        f_ = (mec.dados or {}).get("fonte_servos") or {}
        p["fonte_servos"] = {
            "nome": "Reguladores e drivers dos atuadores dos braços", "categoria": "eletronica",
            "resumo": f_.get("modelo", "buck de 12 V + UBEC + 4 drivers DRV8871"),
            "como_funciona": "O buck baixa os 19–25 V do pack para 12 V estáveis (os motorredutores dos ombros); cada "
                             "DRV8871 (ponte H) inverte e dosa a corrente de um motorredutor pelo PWM do FC, com o "
                             "limite de corrente na resistência ILIM (64/27 kΩ = 2,37 A); o UBEC dá 6,0 V aos 4 servos "
                             "dos cotovelos (o DS3218MG é dado até 6,8 V).",
            "specs": [["Ombros", "12 V · 4 × DRV8871 (ILIM 2,37 A)"], ["Cotovelos", "UBEC 6,0 V / 10 A (aceita 6S)"],
                      ["Massa", _fmt(float(f_.get("massa_g", 0.0)), 0, "g")]], "fontes": []}


def passos(hw, presentes: list[str]) -> list[dict]:
    """Os passos de montagem (ordem de bancada) que se aplicam a este build."""
    art = getattr(hw, "bracos", None) is not None
    lista = [
        {"id": "frame", "titulo": "Placa de baixo e espaçadores",
         "texto": "Pouse a placa de baixo e aparafuse os 4 espaçadores M3 por baixo. Ainda sem a placa de cima.",
         "pecas": ["placa_inferior", "espacadores"]},
    ]
    if art and acessivel(hw):
        lista = [
            {"id": "imprimir", "titulo": "Imprimir as peças em ABS",
             "texto": "Imprima em ABS (bico 0,4 mm, camada 0,2 mm, 3 perímetros, 40 % de enchimento, cama a 100 °C e "
                      "caixa fechada — o ABS empena com correntes de ar): placas, colunas, caixas e cubos dos ombros, "
                      "berços e garfos dos cotovelos, suportes dos motores, abraçadeiras e pés das pernas e os suportes "
                      "da eletrónica. Cada peça da lista tem o STL e a massa/tempo/custo. Crave os insertos de latão M3 "
                      "com o ferro de soldar a ~220 °C, a direito.",
             "pecas": ["placa_inferior", "placa_superior", "espacadores", "ombro_forquilha", "ombro_cubo", "ombro_suporte",
                       "ombro_bloco", "ombro_porca", "cotovelo_berco", "cotovelo_garfo", "suporte_motor", "perna"]},
            {"id": "frame", "titulo": "Placa de baixo e colunas",
             "texto": "Aparafuse as colunas impressas à placa de baixo (M3 nos insertos). Ainda sem a placa de cima.",
             "pecas": ["placa_inferior", "espacadores"]},
            {"id": "ombro", "titulo": "Dobradiças dos ombros",
             "texto": "Prense os 2 rolamentos 608ZZ nas sedes da forquilha (a direito, pelo anel exterior) e aparafuse-a "
                      "às placas (M3 nos insertos). Enfie o veio Ø8 pela forquilha e pelo cubo do braço, fixe-o com os "
                      "colares (ou a porca autoblocante do M8) sem apertar os rolamentos de lado, e cole o íman do "
                      "encoder na ponta. O cubo tem de rodar livre em todo o curso, sem pontos duros.",
             "pecas": ["ombro_forquilha", "ombro_veio", "ombro_cubo"]},
            {"id": "atuador", "titulo": "Montar os 4 atuadores de fuso",
             "texto": "Aparafuse o motorredutor ao corpo do atuador (M3 na face). Prense os 2 × 608ZZ no bloco, enfie o "
                      "fuso Tr8×2 e prenda-o com os 2 colares Ø8 encostados aos rolamentos (o fuso não pode ter folga "
                      "axial: é ali que vai a força). Ligue o veio do motor ao fuso com o acoplamento flexível (pernos nas "
                      "faces planas). Aparafuse a porca de latão ao carro impresso e enrosque-a no fuso; ponha massa "
                      "lubrificante na rosca (sem massa o latão gasta-se; com óleo fino a margem do autobloqueio fica "
                      "pequena). Rode o motor à mão: a porca tem de correr sem prender em todo o fuso.",
             "pecas": ["ombro_bloco", "ombro_motor", "ombro_fuso", "ombro_porca"]},
            {"id": "biela", "titulo": "Montar a biela: pivôs A e B",
             "texto": "Aparafuse o suporte do pivô B às placas. Monte o corpo do atuador no pivô B (parafusos de ombro M4 "
                      "em 2 × 684ZZ) e o carro da porca na ponta da alavanca do cubo (pivô A: parafuso de ombro M4 em 2 × "
                      "MR84ZZ). Os pivôs só apertam até deixarem de ter folga — têm de rodar livres. Rode o motor: o braço "
                      "sobe e desce de −40° a +40° sem o atuador tocar em nada, e empurrar o braço à mão NÃO o mexe "
                      "(autobloqueio).",
             "pecas": ["ombro_suporte", "ombro_bloco", "ombro_porca", "ombro_cubo"]},
            {"id": "encoder", "titulo": "Encoders magnéticos",
             "texto": "AS5048A centrado no veio do ombro a 0,5–2 mm do íman; AS5600 no parafuso M8 do cotovelo. Leia "
                      "os ângulos no FC antes de fechar: têm de mudar suavemente em todo o curso.",
             "pecas": ["ombro_encoder", "cotovelo_encoder"]},
            {"id": "placa_cima", "titulo": "Placa de cima",
             "texto": "Aparafuse a placa de cima às colunas e às caixas dos ombros.",
             "pecas": ["placa_superior"]},
            {"id": "bracos", "titulo": "Tubos dos braços e cotovelos",
             "texto": "Enfie cada tubo no cubo do ombro até ao batente e aperte a fenda. Aperte o berço na ponta do "
                      "tubo e o servo DS3218MG no berço (4 × M3). Ponha o servo no centro (1500 µs) ANTES de "
                      "aparafusar o horn ao garfo com o mastro na vertical; do outro lado o 608ZZ, o parafuso M8 e a "
                      "porca autoblocante (aperto só até o garfo deixar de ter folga). Aperte o mastro no garfo.",
             "pecas": ["ombro_cubo", "tubo_braco", "cotovelo_berco", "cotovelo_servo", "cotovelo_garfo", "mastro",
                       "perna"]},
            {"id": "reguladores", "titulo": "Reguladores e drivers dos atuadores",
             "texto": "Regule o buck para 12,0 V e ponha o UBEC em 6,0 V ANTES de ligar os atuadores (o DS3218MG é dado "
                      "até 6,8 V); confirme a resistência ILIM de 27 kΩ de cada DRV8871 (2,37 A). Ligue cada motorredutor "
                      "ao seu DRV8871 (M+/M−) e o encoder ao FC; os servos ao UBEC.",
             "pecas": ["fonte_servos"]},
        ]
    elif art:
        lista += [
            {"id": "ombro", "titulo": "Montar os 4 ombros (redutor sem-fim)",
             "texto": "Prense os 2 rolamentos 6800ZZ nas paredes da caixa e os 685ZZ nas tampas. Enfie o veio Ø10 com a "
                      "coroa (apertada pelos pernos), feche com os anéis E, meta o sem-fim nos 685 e confirme o "
                      "engrenamento SEM folga a rodar o sem-fim à mão: o braço tem de subir e descer sem pontos duros, "
                      "e não pode ser possível rodar o sem-fim empurrando o braço (autobloqueio). Aparafuse a caixa à "
                      "placa de baixo e monte o íman na ponta do veio.",
             "pecas": ["ombro_caixa", "ombro_veio", "ombro_semfim"]},
            {"id": "encoder", "titulo": "Encoder AS5048A",
             "texto": "Aparafuse a placa do AS5048A nos pilares, centrada no veio, com 0,5–2 mm até ao íman. Leia o "
                      "ângulo no FC antes de fechar: tem de mudar suavemente em todo o curso.",
             "pecas": ["ombro_encoder"]},
            {"id": "placa_cima", "titulo": "Placa de cima e servos dos ombros",
             "texto": "Aparafuse a placa de cima aos espaçadores. Aparafuse as 2 cantoneiras de cada servo XH430 à placa "
                      "(M3) e o servo às cantoneiras (M2,5), deitado, com o horn para baixo pelo furo da placa; "
                      "aparafuse o acoplamento ao horn (4 × M2) e aperte o perno M3 no veio do sem-fim (na face "
                      "plana do veio).",
             "pecas": ["placa_superior", "ombro_servo"]},
            {"id": "bracos", "titulo": "Tubos dos braços e cotovelos",
             "texto": "Enfie cada tubo no cubo do ombro até ao batente e aperte. Monte o servo do cotovelo no berço da "
                      "ponta do tubo; aparafuse o garfo ao horn e ao idler (ponteiro a 0° com o servo na posição "
                      "central 2048) e aperte o mastro no garfo.",
             "pecas": ["ombro_cubo", "tubo_braco", "cotovelo_servo", "cotovelo_garfo", "mastro", "perna"]},
            {"id": "fonte24", "titulo": "Regulador 24 V dos servos",
             "texto": "Fixe o regulador na placa, regule a saída a 24,0 V no trimmer ANTES de ligar os servos e ligue o "
                      "barramento DYNAMIXEL em estrela aos ombros (cada ombro passa ao seu cotovelo).",
             "pecas": ["fonte_servos"]},
        ]
    else:
        lista += [
            {"id": "bracos", "titulo": "Braços, abraçadeiras e trem de pouso",
             "texto": "Enfie os tubos nas abraçadeiras CNC dos cantos, alinhe-os pelas marcas a 45° e aperte. Monte as "
                      "abraçadeiras das pernas e os varões de travamento. Aparafuse a placa de cima.",
             "pecas": ["tubo_braco", "abracadeira_tubo", "perna", "trelica", "placa_superior", "estrutura"]},
        ]
    lista += [
        {"id": "motores", "titulo": "Placas dos motores e motores",
         "texto": "Aparafuse cada motor à sua placa POR BAIXO com 4 parafusos M3 do comprimento indicado (um parafuso "
                  "comprido demais toca nas bobinas e queima o motor). Freio de rosca médio. Os cabos de fase viram-se "
                  "para o centro do drone.",
         "pecas": ["suporte_motor", "motor"]},
        {"id": "esc", "titulo": "ESC nos braços",
         "texto": "Deite cada ESC ao longo do braço e prenda-o com abraçadeiras de nylon. Ligue as 3 fases às balas "
                    "do motor (a ordem decide o sentido de rotação — confirme-o antes de pôr as hélices).",
         "pecas": ["esc"]},
        {"id": "pilha", "titulo": "Pilha de eletrónica",
         "texto": "Pilares de latão M2,5 na placa, o Raspberry Pi 5 com o Active Cooler, a ponte de carbono, o FC nos "
                  "amortecedores (seta para a frente) e a placa de energia por cima, na pilha M3 de nylon.",
         "pecas": ["rpi5", "fc", "pdb", "portenta", "imu"]},
        {"id": "cabos", "titulo": "Cablagem de energia e sinais",
         "texto": "Solde o 10 AWG do XT90 às ilhas da bateria da placa de energia e o 14 AWG de cada ESC às ilhas do "
                  "seu canto. Ligue o cabo USB-C da saída 5 V do BEC ao Raspberry Pi 5, o UART Pi ↔ FC, o I²C do "
                  "INA226 e os sinais dos ESC. Prenda tudo com abraçadeiras: nenhum cabo pode tocar numa hélice.",
         "pecas": ["cablagem", "cabo_rpi5_5v", "abracadeira"]},
        {"id": "camera", "titulo": "Câmara e sensores de baixo",
         "texto": "Câmara no suporte do nariz (4 × M2) com o FPC por baixo da placa até ao CAM/DISP 0 do Pi; o "
                  "PMW3901 e o VL53L1X na bandeja, a olhar para o chão.",
         "pecas": ["camera", "sensor_fluxo", "sensor_tof", "bandeja_sensores"]},
        {"id": "bateria", "titulo": "Bateria",
         "texto": "Tapete na placa, pack por cima, as 2 cintas pelos rasgos e bem apertadas. Ligue o XT90 SÓ no fim, "
                  "com o drone pousado e longe das mãos.",
         "pecas": ["bateria", "cintas_bateria"]},
        {"id": "helices", "titulo": "Hélices (o último passo)",
         "texto": "Com a bateria DESLIGADA: cada hélice no seu motor (CW nos rotores 1 e 2, CCW nos 3 e 4 — a faixa "
                  "colorida diz qual é), pino de centragem no furo e os 2 parafusos M3 apertados em cruz.",
         "pecas": ["helice"]},
    ]
    if art and acessivel(hw):                    # os cabos dos atuadores dos braços (sem barramento DYNAMIXEL)
        for p_ in lista:
            if p_["id"] == "cabos":
                p_["texto"] += (" Nos braços: o cabo de 6 fios de cada motorredutor (M+/M− ao seu DRV8871, o encoder Hall "
                                "ao FC), o de 3 fios de cada servo do cotovelo (UBEC + sinal PWM do FC) e os dos encoders "
                                "(AS5048A por SPI, AS5600 por I²C) atravessam o ombro com um laço de folga junto ao pivô "
                                "do atuador — o atuador roda — e nunca encostam ao fuso, que gira.")
                p_["pecas"] = p_["pecas"] + ["cabo_motorredutor", "cabo_servo", "cabo_encoder", "manga"]
    for p_ in lista:
        p_["pecas"] = [x for x in p_["pecas"] if x in presentes]
    lista = [p_ for p_ in lista if p_["pecas"]]
    for i, p_ in enumerate(lista, 1):           # numerados DEPOIS de tirar os passos sem peças neste build
        p_["n"] = i
    return lista


__all__ = ["CATEGORIAS", "PORQUE", "acessivel", "catalogo", "passos"]
