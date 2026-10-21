"""lab/drone_rpi/detalhes/motores.py — MOTORES T-Motor e HÉLICES de carbono com a FORMA e o TAMANHO REAIS (só aparência).

Pedido do dono (2026-10-20): «os motores tudo verificado, e quero que cada motor tenha a forma igual e o tamanho como
ele realmente é». Cada motor é desenhado aqui a partir das COTAS MEDIDAS nos modelos 3D OFICIAIS da T-Motor (STEP do
centro de downloads, tesselados e cortados fora do repositório — `pesquisas/2026-10-20-motores-tmotor-medidas.md` tem
o método, as cotas e as fontes) e das fichas do fabricante; as malhas são NOSSAS (perfis de revolução, plantas
trianguladas e lajes com o perfil de alturas real), não cópias do CAD. Tudo pelo `Contexto.geom` (massa 0, sem
contacto; grupo 3 = motor, grupo 1 = hélice) e numa PEÇA (`motor` / `helice`, instância k = rotor).

MOTORES (referencial do motor: z = 0 na face de BAIXO da base, eixo z para cima, x ao longo do braço para FORA):
  série Antigravity (MN4004, MN4006, MN5006, MN2806) — base CNC aberta (rins/cruz/janelas reais, 4 furos M3), estator
  visível de lado (dentes com sapatas, bobinas de cobre), anel de aço do rotor, tampa com 6 RAIOS e janelas em lente
  (as da T-Motor: duas circunferências e o filete da ponta medidos no CAD), furos M3 da hélice no topo, veio com o pino
  que centra a hélice e o anel E por baixo; cabos de fase de FIO ESMALTADO (ficha: «Lead: Enameled Wire»).
  série Navigator (MN3508) — copo fechado (sino de alumínio PRATEADO), base com 4 braços e saia, 6 raios no topo; cabos
  de silicone 18 AWG (600 mm na ficha: só se desenha o arranque).
  2306 genérico (5″ FPV, referência do plano) — classe T-Motor F40 PRO: sino Ø27,9 × 16,5 mm, base 16 × 16 M3, perno M5.

  motor{k}                  o cilindro com MASSA e colisão fica, INVISÍVEL (`esconder`): as peças abaixo representam-no
                            (o cilindro tem a cota do catálogo; a malha tem a REAL — ver o relatório: no MN5006 e no
                            MN2806 a ficha soma o veio à altura)
  motor{k}_base_cnc         base: placa com a planta real (rins/cruz/janelas/braços), furos M3 roscados e o tubo dos
                            rolamentos com o assento do estator — alumínio anodizado (preto; prata no MN3508)
  motor{k}_estator_nucleo   pacote de chapas: coroa, N dentes e sapatas (as do CAD no MN4004)
  motor{k}_estator_cobre    as N bobinas (fio esmaltado: espiras na textura)
  motor{k}_sino_anel        anel de aço do rotor (+ ímanes por dentro)
  motor{k}_raio_1           TAMPA do rotor (cubo, placa do topo com os furos M3, 6 raios, aro) — GIRA com a hélice
  motor{k}_eixo             veio (Ø e pino reais), face do rolamento de baixo e, no MN5006, o copo de retenção
  motor{k}_manga            fio esmaltado: manga termorretrátil sobre os 3 condutores, da saída REAL do motor (entre a
                            base e o sino, virada para o centro do drone; no MN2806 pelo entalhe da base) até ao PONTO
                            COMUM dos cabos (por cima da placa, fora de todos os motores do painel)
  motor{k}_saida_{a,b,c}    (silicone: MN3508, 2306) os 3 fios lado a lado da saída ao ponto comum, em vez da manga
  motor{k}_fase_{a,b,c}     os 3 condutores de fase do ponto comum até às balas (cobre esmaltado / silicone preto)
  motor{k}_fase_{x}_conector  bala macho de 3,5 mm dourada — o módulo `fios` liga-se AQUI: ponta livre = `fromto[3:6]`,
                            raio da bala = `size[0]`
  ESC 4 em 1 (`hw.esc.dados["formato"] == "4em1"`, hoje só o 5″): SEM balas — num 5″ os 3 fios do motor vão soldados
  direto às ilhas do 4 em 1. Os fios de silicone vão do ponto comum (lado a lado, passo 2,1 mm) deitados no topo do
  braço, do lado +n do eixo (as cabeças M3 do braço e os espaçadores da pilha estão NO eixo), até à saída da raiz do
  braço (3 mm para fora do espaçador e da placa de cima), e acabam numa ponta descarnada e ESTANHADA de 3 mm:
  motor{k}_fase_{x}_ponta   o condutor estanhado (Ø1,1 mm no 18 AWG); a ponta livre = `fromto[3:6]`
  ÂNCORAS `registo.notas["ancoras"]["mot{k}_fio_fim_{a,b,c}"]` = {corpo, ponto (a ponta livre do condutor, no eixo
                            dele), direcao (de saída: para o centro do drone), bitola, d_fio_mm, d_condutor_mm, ponta_mm,
                            isolamento_fim, geom, fase} — os `fios` fazem a continuação até às ilhas, com a solda
  ferragens (`ctx.ferragens`): 4 × ISO 4762 M3 por baixo da placa do motor (`suporte_motor_{k}`, comprimento normalizado
  com a rosca da base toda metida e sem passar da `prof_rosca_max_mm`), o anel E DIN 6799 do veio e (MN5006) o parafuso
  de cabeça de embeber que segura o copo; os 2 parafusos da hélice estão desenhados em `helice{k}_parafusos` (rodam) e
  só registados (`desenhar=False`).

TROCA AO VIVO (`ctx.registar_variante("motor", id, …)`): por rotor, cada modelo do `CATALOGO_MOTORES_PAINEL` tem as suas
peças (malhas partilhadas pelos 4 rotores) — `motor{k}_v_<curto>_base`, `_nucleo`, `_cobre`, `_anel`, `_eixo`, a saída
dos cabos (`_manga` ou `_saida_{a,b,c}`) e o topo `motor{k}_raio_v_<curto>` (gira; <curto> = mn4004, mn4006, mn5006,
mn2806, mn3508); o motor do build é a variante ativa com os nomes de sempre (registada também quando não está no
painel, para a troca o esconder) e o KV300 e o KV400 do MN4004 partilham as peças (mecanicamente iguais). Todas assentam
na placa do motor e levam os cabos ao mesmo ponto comum; `dz` = topo da variante − topo do motor do build (a hélice
sobe/desce isso para assentar no topo). Os parafusos da base são os do motor do build (a furação da placa é a dele).

HÉLICE — T-Motor P15×5 CF «polish» no build ativo (381 × 127 mm, 21 g, 2 pás; cubo T-mount: furo Ø6 + 2 furos M3 a
12 mm; a hélice ASSENTA no topo do motor — sem adaptador):
  helice{k}                 o disco translúcido do cockpit (grupo 2, massa 0, sem contacto) passa a COROA no plano
                            REAL das pás, do cubo à ponta (o borrão não tapa o cubo nem os parafusos; o site r{k} não muda)
  helice{k}_cubo            cubo de carbono (Ø22 × 6 mm, estimado) — a face de baixo no topo do motor
  helice{k}_pa{b}_raiz/_ponta/_faixa  pá b com a forma real (corda, torção do passo, perfil arqueado; CW/CCW espelhadas)
  helice{k}_centro          anel de latão de centragem (Ø6 por fora, Ø do pino por dentro) à volta do pino do veio
  helice{k}_tampa           tampa de aperto de alumínio anodizado preto sobre o cubo
  helice{k}_parafusos       2 × ISO 4762 M3×10 (12.9 preto) no círculo de 12 mm, roscados nos furos M3 do topo do motor
  helice{k}_porca           (hélices de furo central: 5″ no perno M5, APC no adaptador M6) porca autoblocante ISO 10511

O site `r{k}` fica transparente (só `rgba`). ANIMAÇÃO: `Planta` roda RÍGIDAS as peças `helice{k}_*` e `motor{k}_raio_*`.

Fontes (dados `untrusted`, só citados; detalhe e cotas em `pesquisas/2026-10-20-motores-tmotor-medidas.md`):
  · STEP oficiais T-Motor: https://cn.tmotor.com/uploadfile/downloads/tmotor-mn4004-motor-3d-model.step (NX, 2021),
    …-mn4006-motor-3d-model.step (NX, 2020), …-mn5006-motor-3d-model.step (CATIA, 2019), …-mn2806-motor-3d-model.step,
    …-mn3508-motor-3d-model.step (NX, 2021) — Ø, alturas, perfis do sino/tampa/base, janelas, furos, veio, rolamentos;
  · fichas: https://store.tmotor.com/product/mn4004-kv300-motor-antigravity-type.html (Φ44,35×19, 53 g, cabo 50 mm,
    18N24P) · …/mn4006-kv380-motor-antigravity-type.html (Φ44,35×21, 68 g) · …/mn4006-EVO-kv380-motor-antigravity-type.html
    («Lead: Enameled Wire 50mm», 694ZZ) · …/mn5006-kv450-motor-antigravity-type.html (Φ55,6×30, 106 g, «Lead Cable
    80mm», 696ZZ) · …/mn2806-motor-antigravity-type.html (Φ35×26, 46 g, «Enameled Wire 50mm», saída lateral-baixo,
    694ZZ) · …/mn3508-motor-navigator-type.html (Φ41,8×26,5, estator 35×8, cabo 600 mm 18 AWG, 82/103 g) ·
    https://rcdrone.top/products/src-mn3508_kv380-mn3508-multirotor-fixed-wing-uav-motor-kv380-kv580-kv700 («silver housing», 4-M3 Φ25, Φ12) ·
    https://rcdrone.top/products/src-mn5006-mn5006-antigravity-type-4-6s-uav-motor-kv300 (hélice: 2 × M3×10, anel de
    latão e tampa preta) · https://www.facebook.com/groups/1737736206469442/posts/3016248608618189 (T-mount: furo Ø6, 2 × Ø3
    a 12 mm) · https://dronehitech.com/t-motor-f40-pro-vs-f40iii (2306: 27,9 × 16,5 mm, 16 × 16, M5) ·
    https://store.tmotor.com/product/polish-carbon-fiber-15x5-prop.html (P15×5: 381 × 127 mm, 21 ± 1,5 g).
  · ESTIMADO (sem cota oficial): enrolamentos (o CAD não os traz: sobra 1,2–1,5 mm), estator do MN5006/MN2806/MN3508
    (só a ficha: Ø × altura), cubo da P15×5 (Ø22 × 6 mm: o pino de 6 mm e os M3×10 da T-Motor fecham com 6 mm), tampa de
    aperto, anel de latão, ímanes, o 2306 inteiro (classe F40 PRO) e as cores das bobinas/núcleo.
"""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass

import mujoco
import numpy as np

_MM = 1e-3
_TAU = 2.0 * math.pi
_GRUPO_HELICE = 1          # pás 3D: o «mostrar_helices» do cockpit (como as de sempre)
_GRUPO_MOTOR = 3           # detalhes: o «fios e detalhes» do cockpit
# texturas: SÓ procedimentais (`builtin` do MuJoCo — o `to_xml` não exporta imagens em memória). O tecido de carbono é um
# xadrez fino de dois pretos (cada casa = um cabo de fibra 3K de ~2 mm) e as espiras das bobinas o mesmo xadrez lido
# numa só coluna (riscas alternadas de dois tons de cobre, uma por espira).
_CABO_FIBRA = 0.002
_PERIODO_TECIDO = 2.0 * _CABO_FIBRA
_TEX_CARBONO = np.eye(2)
_PASSO_ESPIRA = 0.0007
_CHEIA = 2.5               # expoente da queda da corda depois do pico (pá «cheia» a meio, como as P-series)


# =========================================================================================== desenhos (mm)
@dataclass(frozen=True)
class _Desenho:
    """Cotas de UM modelo de motor, em mm, no referencial do motor (z = 0 na face de baixo da base). Os perfis (r, z)
    são polilinhas encadeadas no sentido anti-horário (cada polilinha tem arestas vivas nas pontas)."""

    chave: str
    nome: str
    serie: str                # antigravity | navigator | fpv
    d: float                  # Ø exterior do sino
    h: float                  # corpo: face de baixo da base → topo da tampa (sem o pino do veio)
    cor: str                  # preto | prata (acabamento do corpo)
    # base
    base: tuple               # (tipo, {parâmetros}) da planta da placa
    t_base: float             # espessura da placa (= rosca útil dos furos M3)
    furos_base: tuple         # ((r, ângulo°), …) dos furos M3 no referencial do motor
    tubo: tuple               # perfis do tubo dos rolamentos / assento do estator
    extra_base: tuple         # perfis de revolução extra da base (anel de suporte do MN5006…)
    # estator
    est: tuple                # (r_furo, r_coroa, r_ext, z0, z1, n, larg_dente, r_sapata, meia_abertura_sapata°, sobra)
    # rotor
    anel: tuple               # perfis do anel de aço (+ ímanes)
    aro: tuple                # perfil do aro da tampa (revolução): o fundo das janelas
    tampa_top: tuple          # z do topo da tampa (r, z) — cubo, placa e cone dos raios até r_cut
    tampa_bot: tuple          # z da face de baixo (r, z)
    pontas_top: tuple         # z do topo das pontas dos raios sobre o aro (r, z), de r_cut ao Ø exterior
    r_furo_tampa: float       # furo do veio na tampa
    z_aro: float
    r_cut: float              # raio de dentro do aro (fim das janelas)
    janela: tuple             # (n, D, R, δ°, D_filete, r_filete, fase°): janelas em lente com o filete da ponta
    furos_topo: tuple         # ((r, ângulo°, Ø), …) furos M3 da hélice
    # veio
    veio: tuple               # perfis do veio (r = 0 nas pontas)
    rolamento: tuple          # perfis da face do rolamento de baixo (ou vazio)
    extra_aco: tuple          # perfis extra de aço (copo de retenção do MN5006…)
    anel_e: tuple             # (z da face de cima, Ø do veio) do anel E por baixo, ou ()
    pino: tuple               # (Ø, altura acima da tampa) do pino que centra a hélice
    # cabos
    cabo: tuple               # (tipo, comprimento mm, raio do condutor mm, ponto de saída (x, y, z), cor)
    # contrato com a estrutura (furação da base)
    prof_rosca_max: float     # o parafuso não pode passar desta cota acima da face de baixo da base (bobinas, anel)
    furo_central: float       # Ø do furo da placa do motor para o veio/anel E
    massa_g: float
    fonte: str


def _p(*pts) -> tuple:
    return tuple((float(r), float(z)) for r, z in pts)


def _fechado(*pts) -> tuple:
    """Perfil fechado → polilinhas de 2 pontos (todas as arestas vivas)."""
    pts = list(pts)
    return tuple(_p(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))


_ROL_694 = _fechado((2.0, 0.0), (2.8, 0.0), (2.8, 0.2), (4.68, 0.2), (4.68, 0.0), (5.49, 0.0), (5.49, 4.0), (2.0, 4.0))
_URL = "https://cn.tmotor.com/uploadfile/downloads/tmotor-{}-motor-3d-model.step"

_MN4004 = _Desenho(
    chave="mn4004", nome="T-Motor Antigravity MN4004", serie="antigravity", d=44.35, h=19.0, cor="preto",
    base=("rins", {"r": 15.0, "furo": 5.49, "r_rim": 11.0, "meia_larg": 2.5, "meio_vao": 19.1,
                   "centros": (0.0, 90.0, 180.0, 270.0)}),
    t_base=2.3, furos_base=((12.5, 45.0), (12.5, 135.0), (12.5, 225.0), (12.5, 315.0)),
    tubo=_fechado((5.49, 2.3), (8.0, 2.3), (8.0, 6.85), (7.84, 7.0), (7.49, 7.0), (7.49, 10.7), (7.19, 11.0),
                  (5.79, 11.0), (5.49, 10.7), (5.49, 7.0), (4.5, 7.0), (4.5, 4.0), (5.49, 4.0)),
    extra_base=(),
    est=(7.49, 10.0, 19.5, 7.0, 11.0, 18, 2.0, 18.85, 6.88, 1.2),
    anel=_fechado((20.77, 6.0), (22.17, 6.0), (22.17, 12.0), (21.37, 12.0), (21.37, 6.6), (20.77, 6.6)),
    aro=_fechado((20.25, 8.0), (21.07, 8.0), (21.37, 8.3), (21.37, 12.0), (22.17, 12.0), (22.17, 12.75), (20.25, 12.75)),
    tampa_top=_p((2.0, 18.7), (2.3, 19.0), (10.0, 19.0), (20.25, 14.88)),
    tampa_bot=_p((2.0, 11.3), (2.3, 11.0), (3.24, 11.0), (5.48, 14.0), (5.50, 16.7), (13.57, 16.7), (19.62, 14.27),
                 (19.94, 14.06), (20.16, 13.75), (20.25, 13.34)),
    pontas_top=_p((20.25, 14.88), (20.92, 14.61), (21.25, 14.44), (21.57, 14.19), (21.81, 13.90), (22.00, 13.57),
                  (22.14, 13.13), (22.17, 12.75)),
    r_furo_tampa=2.0, z_aro=12.75, r_cut=20.25,
    janela=(6, 24.47, 18.012, 24.1, 13.23, 4.5, 75.0),
    furos_topo=((6.0, 0.0, 2.48), (6.0, 90.0, 2.48), (6.0, 180.0, 2.48), (6.0, 270.0, 2.48)),
    veio=(_p((0.0, -2.3), (1.32, -2.3)), _p((1.32, -2.3), (1.60, -2.29), (1.79, -2.20), (1.96, -1.99), (2.0, -1.8)),
          _p((2.0, -1.8), (2.0, -0.8)), _p((2.0, -0.8), (1.75, -0.8)), _p((1.75, -0.8), (1.75, -0.2)),
          _p((1.75, -0.2), (2.0, -0.2)), _p((2.0, -0.2), (2.0, 18.5)), _p((2.0, 18.5), (1.5, 19.0)),
          _p((1.5, 19.0), (1.48, 24.65)), _p((1.48, 24.65), (1.34, 24.87), (1.10, 24.99), (0.0, 25.0))),
    rolamento=_ROL_694, extra_aco=(), anel_e=(-0.2, 4.0), pino=(3.0, 6.0),
    cabo=("esmaltado", 50.0, 0.6, (-15.9, 0.0, 4.2), "cobre"),
    prof_rosca_max=5.3, furo_central=9.0, massa_g=53.0, fonte=_URL.format("mn4004"))

_MN4006 = _Desenho(
    chave="mn4006", nome="T-Motor Antigravity MN4006", serie="antigravity", d=44.35, h=21.0, cor="preto",
    base=_MN4004.base, t_base=2.3, furos_base=_MN4004.furos_base,
    tubo=_fechado((5.49, 2.3), (8.0, 2.3), (8.0, 6.85), (7.84, 7.0), (7.49, 7.0), (7.49, 12.7), (7.19, 13.0),
                  (5.79, 13.0), (5.49, 12.7), (5.49, 7.0), (4.5, 7.0), (4.5, 4.0), (5.49, 4.0)),
    extra_base=(),
    est=(7.49, 10.0, 19.5, 7.0, 13.0, 18, 2.0, 18.85, 6.88, 1.2),
    anel=_fechado((20.77, 6.0), (22.17, 6.0), (22.17, 14.0), (21.37, 14.0), (21.37, 6.6), (20.77, 6.6)),
    aro=_fechado((20.25, 7.0), (21.37, 7.0), (21.37, 14.0), (22.17, 14.0), (22.17, 14.75), (22.12, 15.2), (20.25, 15.2)),
    tampa_top=_p((2.0, 21.0), (9.99, 21.0), (20.25, 16.88)),
    tampa_bot=_p((2.0, 13.3), (2.3, 13.0), (3.25, 13.0), (5.48, 16.0), (5.50, 18.7), (13.57, 18.7), (19.79, 16.18),
                 (20.07, 15.91), (20.16, 15.75), (20.25, 15.34)),
    pontas_top=_p((20.25, 16.88), (20.92, 16.61), (21.26, 16.43), (21.56, 16.19), (21.81, 15.91), (22.00, 15.57),
                  (22.13, 15.15), (22.17, 14.75)),
    r_furo_tampa=2.0, z_aro=15.2, r_cut=20.25, janela=_MN4004.janela, furos_topo=_MN4004.furos_topo,
    veio=(_p((0.0, -2.5), (1.59, -2.49)), _p((1.59, -2.49), (1.89, -2.31), (2.0, -2.0)), _p((2.0, -2.0), (2.0, -1.0)),
          _p((2.0, -1.0), (1.75, -1.0)), _p((1.75, -1.0), (1.75, -0.4)), _p((1.75, -0.4), (2.0, -0.4)),
          _p((2.0, -0.4), (2.0, 21.0)), _p((2.0, 21.0), (1.5, 21.0)), _p((1.5, 21.0), (1.5, 26.3)),
          _p((1.5, 26.3), (1.45, 26.51), (1.34, 26.66), (1.10, 26.79), (0.0, 26.8))),
    rolamento=_ROL_694, extra_aco=(), anel_e=(-0.4, 4.0), pino=(3.0, 5.8),
    cabo=("esmaltado", 50.0, 0.6, (-15.9, 0.0, 4.2), "cobre"),
    prof_rosca_max=5.3, furo_central=9.0, massa_g=68.0, fonte=_URL.format("mn4006"))

_MN5006 = _Desenho(
    chave="mn5006", nome="T-Motor Antigravity MN5006", serie="antigravity", d=55.6, h=25.0, cor="preto",
    base=("cruz", {"r_disco": 8.5, "meia_larg": 2.5, "r": 15.0, "canto": 1.2, "furo": 7.7,
                   "bracos": (45.0, 135.0, 225.0, 315.0), "pilar": (8.3, 11.25, 7.0)}),
    t_base=3.5, furos_base=((12.5, 45.0), (12.5, 135.0), (12.5, 225.0), (12.5, 315.0)),
    tubo=_fechado((7.7, 3.5), (8.5, 3.5), (8.5, 15.0), (7.5, 15.0), (7.5, 4.0), (7.7, 4.0)),
    extra_base=(_fechado((12.0, 6.0), (13.0, 6.0), (13.0, 8.9), (12.75, 8.9), (12.75, 15.0), (12.0, 15.0)),),
    est=(12.75, 15.8, 25.0, 9.0, 15.0, 24, 2.6, 24.3, 5.21, 1.5),
    anel=_fechado((26.5, 8.25), (27.8, 8.25), (27.8, 16.75), (26.8, 16.75), (26.8, 10.65), (26.9, 10.65), (26.9, 8.65),
                  (26.5, 8.65))
    + _fechado((25.5, 9.5), (26.8, 9.5), (26.8, 15.25), (25.5, 15.25)),
    aro=_fechado((25.5, 15.25), (26.8, 15.25), (26.8, 16.75), (27.8, 16.75), (27.8, 18.5), (25.5, 18.5)),
    tampa_top=_p((3.0, 23.4), (3.98, 23.4), (4.0, 25.0), (11.99, 25.0), (25.5, 21.37)),
    tampa_bot=_p((3.0, 15.0), (3.98, 15.0), (5.49, 18.0), (5.50, 21.0), (5.58, 21.39), (5.67, 21.56), (5.94, 21.83),
                 (6.31, 21.98), (6.5, 22.0), (13.52, 22.0), (25.13, 18.88), (25.30, 18.80), (25.45, 18.61),
                 (25.5, 18.4)),
    pontas_top=_p((25.5, 21.37), (25.58, 21.35), (26.10, 21.15), (26.58, 20.86), (27.00, 20.48), (27.34, 20.04),
                  (27.58, 19.59), (27.74, 19.02), (27.80, 18.45)),
    r_furo_tampa=3.0, z_aro=18.5, r_cut=25.5,
    janela=(6, 27.03, 15.90, 11.54, 19.51, 7.01, 75.0),
    furos_topo=((6.0, 0.0, 2.5), (6.0, 90.0, 2.5), (6.0, 180.0, 2.5), (6.0, 270.0, 2.5),
                (9.0, 45.0, 2.5), (9.0, 135.0, 2.5), (9.0, 225.0, 2.5), (9.0, 315.0, 2.5)),
    veio=(_p((1.5, 2.1), (2.76, 2.1)), _p((2.76, 2.1), (2.92, 2.2), (2.99, 2.34)), _p((2.99, 2.34), (2.99, 2.9)),
          _p((2.99, 2.9), (2.74, 2.9)), _p((2.74, 2.9), (2.74, 3.6)), _p((2.74, 3.6), (2.99, 3.6)),
          _p((2.99, 3.6), (3.0, 23.4)), _p((3.0, 23.4), (3.93, 23.4)), _p((3.93, 23.4), (3.93, 24.9)),
          _p((3.93, 24.9), (2.0, 24.9)), _p((2.0, 24.9), (2.0, 29.6)), _p((2.0, 29.6), (1.7, 29.9)),
          _p((1.7, 29.9), (0.0, 29.9)), _p((0.0, 12.1), (1.5, 12.1)), _p((1.5, 12.1), (1.5, 2.1))),
    rolamento=(),
    extra_aco=(_fechado((2.99, 0.2), (4.8, 0.2), (5.0, 0.4), (5.0, 2.8), (4.8, 3.0), (2.99, 3.0), (2.99, 2.1),
                        (1.59, 2.1), (1.59, 1.9), (2.99, 0.5)),
               _fechado((0.0, 0.55), (2.9, 0.55), (1.55, 1.9), (0.0, 1.9))),
    anel_e=(), pino=(4.0, 4.9),
    cabo=("esmaltado", 80.0, 0.7, (-15.9, 0.0, 5.8), "cobre"),
    prof_rosca_max=6.5, furo_central=12.0, massa_g=106.0, fonte=_URL.format("mn5006"))

_MN2806 = _Desenho(
    chave="mn2806", nome="T-Motor Antigravity MN2806", serie="antigravity", d=35.0, h=18.4, cor="preto",
    base=("janelas2806", {"r": 15.0, "furo": 5.5, "r_in": 7.5, "r_out": 13.5, "rc": 2.0, "a_in": 16.7, "a_out": 22.0,
                          "centros": (0.0, 90.0, 180.0, 270.0), "entalhe": (180.0, 2.3, 11.0)}),
    t_base=2.3, furos_base=((12.5, 45.0), (9.5, 135.0), (12.5, 225.0), (9.5, 315.0)),
    tubo=_fechado((5.5, 2.3), (7.3, 2.3), (6.91, 6.6), (6.49, 6.6), (6.5, 12.5), (6.3, 12.7), (5.7, 12.7), (5.5, 12.5),
                  (5.5, 8.7), (4.69, 8.7), (4.69, 4.1), (4.79, 4.0), (5.5, 4.0)),
    extra_base=(),
    est=(6.5, 8.6, 14.0, 6.6, 12.6, 12, 2.6, 13.3, 11.3, 1.2),
    anel=_fechado((16.02, 5.9), (17.5, 5.9), (17.5, 13.7), (16.52, 13.7), (16.52, 6.4), (16.02, 6.4))
    + _fechado((15.3, 6.9), (16.52, 6.9), (16.52, 9.7), (15.3, 9.7)),
    aro=_fechado((15.3, 9.7), (16.52, 9.7), (16.52, 13.7), (17.5, 13.7), (17.5, 14.7), (15.3, 14.7)),
    tampa_top=_p((2.0, 17.05), (2.25, 17.3), (3.0, 17.3), (3.02, 18.15), (3.25, 18.4), (8.70, 18.4), (15.3, 16.67)),
    tampa_bot=_p((2.0, 12.7), (3.0, 12.7), (5.5, 14.2), (5.52, 16.2), (12.75, 16.2), (14.73, 15.66), (14.90, 15.56),
                 (15.16, 15.27), (15.28, 14.94), (15.3, 14.76)),
    pontas_top=_p((15.3, 16.67), (16.53, 16.35), (17.5, 15.09)),
    r_furo_tampa=2.0, z_aro=14.7, r_cut=15.3,
    janela=(6, 18.48, 11.336, 14.4, 12.18, 4.0, 75.0),
    furos_topo=((6.0, 0.0, 2.5), (6.0, 90.0, 2.5), (6.0, 180.0, 2.5), (6.0, 270.0, 2.5)),
    veio=(_p((0.0, -2.1), (1.5, -2.1)), _p((1.5, -2.1), (1.61, -2.09), (1.89, -1.91), (2.0, -1.6)),
          _p((2.0, -1.6), (2.0, -1.1)), _p((2.0, -1.1), (1.75, -1.1)), _p((1.75, -1.1), (1.75, -0.5)),
          _p((1.75, -0.5), (2.0, -0.5)), _p((2.0, -0.5), (2.0, 17.3)), _p((2.0, 17.3), (2.85, 17.3)),
          _p((2.85, 17.3), (3.0, 17.45)), _p((3.0, 17.45), (3.0, 18.15)), _p((3.0, 18.15), (2.85, 18.3)),
          _p((2.85, 18.3), (2.0, 18.3)), _p((2.0, 18.3), (2.0, 23.4)),
          _p((2.0, 23.4), (1.95, 23.62), (1.81, 23.79), (1.61, 23.89), (0.0, 23.9))),
    rolamento=_fechado((2.0, 0.0), (2.8, 0.0), (2.8, 0.2), (4.68, 0.2), (4.68, 0.0), (5.5, 0.0), (5.5, 4.0), (2.0, 4.0)),
    extra_aco=(), anel_e=(-0.5, 4.0), pino=(4.0, 5.5),
    cabo=("esmaltado", 50.0, 0.55, (-15.3, 0.0, 1.4), "cobre"),
    prof_rosca_max=4.9, furo_central=8.0, massa_g=46.0, fonte=_URL.format("mn2806"))

_MN3508 = _Desenho(
    chave="mn3508", nome="T-Motor Navigator MN3508", serie="navigator", d=41.8, h=26.5, cor="prata",
    base=("navigator", {"r_disco": 8.0, "r": 14.5, "bracos": (45.0, 135.0, 225.0, 315.0), "rc": 4.0, "dc": 11.94,
                        "ac": 13.7, "furo": 5.5, "flange": (14.4, 17.0, 0.8, 15.7),
                        "saia": (22.5, 11.0)}),
    t_base=2.6, furos_base=((12.5, 45.0), (12.5, 135.0), (12.5, 225.0), (12.5, 315.0)),
    tubo=(_p((5.5, 2.6), (8.3, 2.6)),
          _p((8.3, 2.6), (7.93, 2.65), (7.39, 2.91), (7.18, 3.11), (6.95, 3.44), (6.84, 3.76), (6.8, 4.1)),
          _p((6.8, 4.1), (6.8, 8.9)), _p((6.8, 8.9), (5.0, 8.9)), _p((5.0, 8.9), (5.0, 4.0)), _p((5.0, 4.0), (5.5, 4.0)),
          _p((5.5, 4.0), (5.5, 2.6))),
    extra_base=((_p((15.67, 0.0), (17.95, 0.03), (18.29, 0.22), (18.42, 0.39)),
                 _p((18.42, 0.39), (18.78, 1.42), (18.98, 1.80), (19.34, 2.33)), _p((19.34, 2.33), (19.34, 3.40)),
                 _p((19.34, 3.40), (18.84, 2.90), (18.51, 2.45), (17.99, 1.48), (17.77, 0.80)),
                 _p((17.77, 0.80), (15.67, 0.80)), _p((15.67, 0.80), (15.67, 0.0))),),
    est=(6.8, 9.6, 17.5, 8.9, 16.9, 12, 3.2, 16.7, 11.7, 1.5),
    anel=_fechado((19.7, 4.0), (20.9, 4.0), (20.9, 5.05), (20.3, 5.05), (20.3, 6.3), (20.9, 6.3), (20.9, 7.5), (19.7, 7.5))
    + _fechado((19.55, 8.2), (20.9, 8.2), (20.9, 8.9), (21.0, 8.9), (21.0, 16.9), (20.05, 16.9), (20.05, 8.8),
               (19.55, 8.8))
    + _fechado((18.0, 8.9), (20.05, 8.9), (20.05, 16.85), (18.0, 16.85)),
    aro=_fechado((18.81, 16.9), (20.9, 16.9), (20.9, 20.0), (18.6, 20.0)),
    tampa_top=_p((2.0, 26.2), (2.3, 26.5), (10.0, 26.5), (18.6, 22.66)),
    tampa_bot=_p((2.0, 17.3), (2.3, 17.0), (3.0, 17.0), (3.98, 20.0), (5.48, 20.0), (5.50, 24.2), (11.47, 24.2),
                 (17.86, 21.35), (18.14, 21.17), (18.37, 20.93), (18.53, 20.64), (18.6, 20.21)),
    pontas_top=_p((18.6, 22.66), (19.65, 22.19), (20.9, 20.36)),
    r_furo_tampa=2.0, z_aro=20.0, r_cut=18.6,
    janela=(6, 34.95, 31.49, 45.45, 12.63, 3.91, 30.0),
    furos_topo=((6.0, 0.0, 2.5), (6.0, 90.0, 2.5), (6.0, 180.0, 2.5), (6.0, 270.0, 2.5)),
    veio=(_p((0.0, -2.4), (1.5, -2.4)), _p((1.5, -2.4), (1.63, -2.38), (1.85, -2.25), (1.95, -2.12), (2.0, -1.9)),
          _p((2.0, -1.9), (2.0, -0.9)), _p((2.0, -0.9), (1.75, -0.9)), _p((1.75, -0.9), (1.75, -0.3)),
          _p((1.75, -0.3), (2.0, -0.3)), _p((2.0, -0.3), (2.0, 32.2)),
          _p((2.0, 32.2), (1.86, 32.45), (1.64, 32.58), (0.0, 32.6))),
    rolamento=_fechado((2.0, 0.0), (2.8, 0.0), (2.8, 0.2), (4.3, 0.2), (4.3, 0.0), (5.0, 0.0), (5.0, 4.0), (2.0, 4.0)),
    extra_aco=(), anel_e=(-0.3, 4.0), pino=(4.0, 6.1),
    cabo=("silicone", 600.0, 0.95, (-18.0, 0.0, 2.0), "preto"),
    prof_rosca_max=6.5, furo_central=9.0, massa_g=103.0, fonte=_URL.format("mn3508"))

_FPV2306 = _Desenho(
    chave="fpv2306", nome="motor FPV 2306 (classe T-Motor F40 PRO)", serie="fpv", d=27.9, h=16.5, cor="preto",
    base=("fpv", {"r": 13.4, "furo": 4.5, "respiros": (7.6, 2.4, (0.0, 90.0, 270.0)), "entalhe": (180.0, 3.2, 9.5)}),
    t_base=2.0, furos_base=((11.314, 45.0), (11.314, 135.0), (11.314, 225.0), (11.314, 315.0)),
    tubo=_fechado((4.5, 2.0), (6.0, 2.0), (6.0, 10.0), (4.5, 10.0)),
    extra_base=(),
    est=(6.0, 7.6, 11.5, 4.0, 10.0, 12, 2.2, 10.9, 11.0, 1.0),
    anel=_fechado((12.75, 2.6), (13.95, 2.6), (13.95, 12.5), (12.75, 12.5))
    + _fechado((12.0, 3.8), (12.75, 3.8), (12.75, 10.2), (12.0, 10.2)),
    aro=_fechado((12.0, 12.5), (13.95, 12.5), (13.95, 13.2), (12.0, 13.2)),
    tampa_top=_p((2.6, 16.5), (7.0, 16.5), (12.0, 14.6)),
    tampa_bot=_p((2.6, 12.8), (4.5, 12.8), (4.52, 15.0), (9.0, 15.0), (12.0, 13.6)),
    pontas_top=_p((12.0, 14.6), (13.4, 14.05), (13.95, 13.5)),
    r_furo_tampa=2.6, z_aro=13.2, r_cut=12.0,
    janela=(6, 13.86, 8.5, 14.4, 9.14, 3.0, 30.0),
    furos_topo=(),
    veio=(_p((0.0, -1.6), (1.75, -1.6)), _p((1.75, -1.6), (2.0, -1.35)), _p((2.0, -1.35), (2.0, -0.9)),
          _p((2.0, -0.9), (1.75, -0.9)), _p((1.75, -0.9), (1.75, -0.4)), _p((1.75, -0.4), (2.0, -0.4)),
          _p((2.0, -0.4), (2.0, 16.4)), _p((2.0, 16.4), (2.5, 16.5)), _p((2.5, 16.5), (2.5, 29.2)),
          _p((2.5, 29.2), (2.2, 29.5)), _p((2.2, 29.5), (0.0, 29.5))),
    rolamento=_fechado((2.0, 0.0), (2.5, 0.0), (2.5, 0.15), (3.8, 0.15), (3.8, 0.0), (4.5, 0.0), (4.5, 3.0), (2.0, 3.0)),
    extra_aco=(), anel_e=(-0.4, 4.0), pino=(5.0, 13.0),
    cabo=("silicone", 100.0, 0.95, (-13.6, 0.0, 1.0), "preto"),
    prof_rosca_max=4.0, furo_central=8.0, massa_g=32.0, fonte="https://dronehitech.com/t-motor-f40-pro-vs-f40iii")

_DESENHOS = {d.chave: d for d in (_MN4004, _MN4006, _MN5006, _MN2806, _MN3508, _FPV2306)}


def _chave_motor(motor) -> str:
    """O desenho de um motor do catálogo (pelo id/modelo): KV300/KV400 da mesma série têm a mesma mecânica."""
    texto = f"{getattr(motor, 'id', '')} {getattr(motor, 'modelo', '')}".lower()
    for chave in ("mn4004", "mn4006", "mn5006", "mn2806", "mn3508"):
        if chave in texto:
            return chave
    if "2306" in texto:
        return "fpv2306"
    d = float(getattr(motor, "dados", {}).get("diametro_mm", 44.35))
    return min(_DESENHOS, key=lambda k: abs(_DESENHOS[k].d - d))   # motor sem desenho próprio: o mais parecido


def _desenho(motor) -> _Desenho:
    return _DESENHOS[_chave_motor(motor)]


def padrao_base(motor) -> dict:
    """Furação da BASE do motor — o CONTRATO com a estrutura (que corta estes furos na placa do motor) e com as
    ferragens (os parafusos sobem por baixo da placa e roscam na base). Referencial do motor: origem no eixo, na face
    de baixo da base, x ao longo do braço para FORA, z para cima; medidas em mm (medidas no STEP oficial da T-Motor).

    {"furos_mm": [(x, y), …], "rosca": "M3", "circulo_mm": Ø do círculo dos furos (ou None num padrão misto),
     "prof_rosca_max_mm": até onde a ponta do parafuso pode subir acima da face de baixo da base (mais alto toca nas
     bobinas/anel), "rosca_util_mm": espessura roscada da base (a rosca que trabalha), "furo_central_mm": Ø do furo da
     placa para o veio/anel E, "fonte": «fabricante» | «estimado», "url": modelo 3D/ficha de onde saiu}"""
    ds = _desenho(motor)
    furos = [(round(r * math.cos(math.radians(a)), 4), round(r * math.sin(math.radians(a)), 4)) for r, a in ds.furos_base]
    raios = {round(r, 3) for r, _ in ds.furos_base}
    return {"furos_mm": furos, "rosca": "M3", "circulo_mm": round(2.0 * raios.pop(), 3) if len(raios) == 1 else None,
            "prof_rosca_max_mm": ds.prof_rosca_max, "rosca_util_mm": ds.t_base, "furo_central_mm": ds.furo_central,
            "fonte": "estimado" if ds.serie == "fpv" else "fabricante", "url": ds.fonte}


# =========================================================================================== malhas (utilitários)
class _Malha:
    """Acumula pedaços de malha: vértices, triângulos (anti-horários vistos de fora) e, se pedido, coordenadas de
    textura. Arestas vivas = vértices próprios de cada face (o MuJoCo não os funde: normais nítidas)."""

    def __init__(self) -> None:
        self._v: list[np.ndarray] = []
        self._f: list[np.ndarray] = []
        self._t: list[np.ndarray] = []
        self._n = 0

    def juntar(self, v, f, t=None, rot_z: float = 0.0, desloc=(0.0, 0.0, 0.0), espelho_y: bool = False,
               espelho_z: bool = False, escala: float = 1.0) -> _Malha:
        v = np.array(v, dtype=float).reshape(-1, 3) * escala
        f = np.asarray(f, dtype=np.int64).reshape(-1, 3)
        if len(f) == 0:
            return self
        if espelho_y:
            v[:, 1] *= -1.0
        if espelho_z:
            v[:, 2] *= -1.0
        if espelho_y != espelho_z:                       # um espelho inverte a orientação das faces
            f = f[:, ::-1]
        if rot_z:
            c, s = math.cos(rot_z), math.sin(rot_z)
            v[:, :2] = v[:, :2] @ np.array([[c, s], [-s, c]])
        v += np.asarray(desloc, dtype=float)
        self._v.append(v)
        self._f.append(f + self._n)
        self._t.append(np.zeros((len(v), 2)) if t is None else np.asarray(t, dtype=float).reshape(-1, 2))
        self._n += len(v)
        return self

    def vazia(self) -> bool:
        return self._n == 0

    def saida(self, textura: bool = False, mtex=None, escala: float = 1.0) -> tuple:
        v = np.concatenate(self._v) * escala
        f = np.concatenate(self._f)
        a = np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
        f = f[a > 1e-14 * max(escala, 1e-9) ** 2]                    # tira faces degeneradas
        t = np.concatenate(self._t) if textura else None
        if t is not None and mtex is not None:
            t = t @ np.asarray(mtex, dtype=float).T
        return (tuple(v.ravel().tolist()), tuple(f.ravel().tolist()),
                None if t is None else tuple(t.ravel().tolist()))


def _revolucao(segmentos, n: int = 48, tex=None, a0: float = 0.0, a1: float | None = None):
    """Sólido de revolução em torno de z. `segmentos` = polilinhas (r, z) que, encadeadas, percorrem o perfil no sentido
    ANTI-HORÁRIO (r → direita, z ↑); cada uma tem vértices próprios (aresta viva entre elas); r = 0 vira um só vértice.
    `tex`: None, ou um código por segmento — "p" (projeção plana xy: topos) ou "c" (cilíndrica: paredes; com costura).
    `a0`/`a1`: só um setor (sem tampas nas pontas)."""
    setor = a1 is not None
    v, f, t = [], [], []
    for k_seg, seg in enumerate(segmentos):
        cil = tex is not None and tex[k_seg] == "c"
        m = n + 1 if (cil or setor) else n
        phi = a0 + (np.arange(m) * ((a1 - a0) / n if setor else _TAU / n))
        cphi, sphi = np.cos(phi), np.sin(phi)
        anel = []
        for r, z in seg:
            if r < 1e-12:
                anel.append([len(v)] * m)
                v.append((0.0, 0.0, z))
                t.append((0.0, 0.0))
            else:
                b = len(v)
                v.extend(zip((r * cphi).tolist(), (r * sphi).tolist(), [z] * m, strict=True))
                if cil:
                    t.extend(zip((phi * r / _PERIODO_TECIDO).tolist(), [z / _PERIODO_TECIDO] * m, strict=True))
                else:
                    t.extend(zip((r * cphi / _PERIODO_TECIDO).tolist(), (r * sphi / _PERIODO_TECIDO).tolist(), strict=True))
                anel.append(list(range(b, b + m)))
        for j in range(len(seg) - 1):
            a, c = anel[j], anel[j + 1]
            for i in range(n):
                i2 = i + 1 if (cil or setor) else (i + 1) % n
                if a[i] != a[i2]:
                    f.append((a[i], a[i2], c[i2]))
                if c[i2] != c[i]:
                    f.append((a[i], c[i2], c[i]))
    return np.array(v), np.array(f, dtype=np.int64).reshape(-1, 3), (np.array(t) if tex is not None else None)


def _superelipsoide(a: float, b: float, c: float, e: float = 0.32, nu: int = 16, nv: int = 8):
    """Superelipsoide |x/a|^(2/e) + |y/b|^(2/e) + |z/c|^(2/e) ≈ 1 (e pequeno = caixa de cantos redondos): vértices
    (com polos únicos), faces e o parâmetro u ∈ [0, 1) de cada vértice."""
    def pw(w, ex):
        return np.sign(w) * np.abs(w) ** ex
    us = np.arange(nu) * _TAU / nu
    vs = np.linspace(-0.5 * math.pi, 0.5 * math.pi, nv + 1)[1:-1]
    v = [(0.0, 0.0, -c)]
    par = [0.0]
    for lat in vs:
        cv, sv = pw(math.cos(lat), e), pw(math.sin(lat), e)
        for u in us:
            v.append((a * cv * pw(math.cos(u), e), b * cv * pw(math.sin(u), e), c * sv))
            par.append(u / _TAU)
    v.append((0.0, 0.0, c))
    par.append(0.0)
    f = []
    topo = len(v) - 1
    for i in range(nu):
        f.append((0, 1 + (i + 1) % nu, 1 + i))
    for j in range(len(vs) - 1):
        r0, r1 = 1 + j * nu, 1 + (j + 1) * nu
        for i in range(nu):
            i2 = (i + 1) % nu
            f.extend([(r0 + i, r0 + i2, r1 + i2), (r0 + i, r1 + i2, r1 + i)])
    rl = 1 + (len(vs) - 1) * nu
    for i in range(nu):
        f.append((rl + i, rl + (i + 1) % nu, topo))
    return np.array(v), np.array(f), np.array(par)


def _prisma(poligono, z0: float, z1: float):
    """Prisma reto de um polígono CONVEXO anti-horário (xy): topos em leque, faces laterais com vértices próprios."""
    p = np.asarray(poligono, float)
    k = len(p)
    v, f = [], []
    for z, cima in ((z1, True), (z0, False)):
        b = len(v)
        v.append((float(p[:, 0].mean()), float(p[:, 1].mean()), z))
        v.extend((float(x), float(y), z) for x, y in p)
        for i in range(k):
            t = (b, b + 1 + i, b + 1 + (i + 1) % k)
            f.append(t if cima else t[::-1])
    for i in range(k):
        a, c = p[i], p[(i + 1) % k]
        b = len(v)
        v.extend([(a[0], a[1], z0), (c[0], c[1], z0), (c[0], c[1], z1), (a[0], a[1], z1)])
        f.extend([(b, b + 1, b + 2), (b, b + 2, b + 3)])
    return np.array(v), np.array(f)


def _arco(r0: float, r1: float, z0: float, z1: float, n: int = 48):
    """Coroa circular (tubo curto) r0..r1 × z0..z1, arestas vivas."""
    return _revolucao([[(r0, z0), (r1, z0)], [(r1, z0), (r1, z1)], [(r1, z1), (r0, z1)], [(r0, z1), (r0, z0)]], n=n)


# ------------------------------------------------------------------- plantas 2D trianguladas e lajes (mm)
def _circ(cx: float, cy: float, r: float, passo: float = 0.75, a0: float = 0.0, a1: float = _TAU):
    """Pontos e normais (para fora do círculo) de um arco — candidatos a fronteira de uma planta."""
    n = max(12, math.ceil(abs(a1 - a0) * r / passo))
    a = a0 + (a1 - a0) * np.arange(n + (0 if abs(a1 - a0 - _TAU) < 1e-9 else 1)) / n
    nrm = np.column_stack([np.cos(a), np.sin(a)])
    return np.column_stack([cx + r * nrm[:, 0], cy + r * nrm[:, 1]]), nrm


def _curva(pts):
    """Pontos de uma polilinha (n, 2) e as normais (perpendiculares à tangente; o sentido não interessa ao filtro)."""
    p = np.asarray(pts, float)
    t = np.gradient(p, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    return p, np.column_stack([t[:, 1], -t[:, 0]])


def _segmento(a, b, passo: float = 0.3):
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = max(2, math.ceil(float(np.linalg.norm(b - a)) / passo) + 1)
    return _curva(a + (b - a) * np.linspace(0.0, 1.0, n)[:, None])


def _triangular(dentro, candidatos, r_max: float, aneis=(), passo: float = 1.0, r_min: float = 0.0, eps: float = 0.015):
    """Planta 2D triangulada (mm): `dentro(xy)` diz que pontos são material; `candidatos` = [(pontos, normais)] das
    curvas que podem ser fronteira (fica só o que é fronteira de verdade: o material muda de um lado para o outro);
    grelha polar interior de `passo` + `aneis` (raios das quebras do perfil de alturas). Delaunay, triângulos com o
    centróide e os meios das arestas dentro do material. Devolve (P, T anti-horários, arestas de fronteira orientadas
    com o material à esquerda)."""
    from scipy.spatial import Delaunay, cKDTree
    cand = [(np.asarray(p_, float), np.asarray(n_, float)) for p_, n_ in candidatos if len(p_)]
    if cand:
        pts = np.concatenate([c[0] for c in cand])
        nrm = np.concatenate([c[1] for c in cand])
        F = pts[dentro(pts + eps * nrm) != dentro(pts - eps * nrm)]   # só o que é fronteira de verdade
    else:
        F = np.zeros((0, 2))
    if len(F):
        _, i_un = np.unique(np.round(F / 0.02), axis=0, return_index=True)
        F = F[np.sort(i_un)]

    def aneis_pts(raios, passo_c, alternar):
        raios = np.asarray(raios, float)
        if not len(raios):
            return np.zeros((0, 2))
        n = np.maximum(6, np.ceil(_TAU * raios / passo_c).astype(int))
        r = np.repeat(raios, n)
        j = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
        meio = np.repeat((np.arange(len(raios)) % 2) * 0.5 if alternar else np.zeros(len(raios)), n)
        th = (j + meio) * _TAU / np.repeat(n, n)
        return np.column_stack([r * np.cos(th), r * np.sin(th)])
    I = aneis_pts(np.arange(max(r_min, 0.0) + 0.5 * passo, r_max + 1e-9, passo), passo, True)
    A = aneis_pts(list(aneis), 0.6 * passo, False)
    I, A = I[dentro(I)] if len(I) else I, A[dentro(A)] if len(A) else A
    if len(F):
        arv = cKDTree(F)
        if len(I):
            I = I[arv.query(I)[0] > 0.55 * passo]
        if len(A):
            A = A[arv.query(A)[0] > 0.25 * passo]
    if len(A) and len(I):
        I = I[cKDTree(A).query(I)[0] > 0.35 * passo]
    P = np.concatenate([F, A, I])
    T = Delaunay(P).simplices
    c = P[T].mean(axis=1)
    ok = dentro(c)
    for i, j in ((0, 1), (1, 2), (2, 0)):
        m = 0.5 * (P[T[:, i]] + P[T[:, j]])
        ok &= dentro(m + 0.08 * (c - m))
    T = T[ok]
    d = (P[T[:, 1], 0] - P[T[:, 0], 0]) * (P[T[:, 2], 1] - P[T[:, 0], 1]) - \
        (P[T[:, 1], 1] - P[T[:, 0], 1]) * (P[T[:, 2], 0] - P[T[:, 0], 0])
    T[d < 0] = T[d < 0][:, ::-1]
    E = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    n = len(P)
    chave, inversa = E[:, 0] * n + E[:, 1], E[:, 1] * n + E[:, 0]
    B = E[~np.isin(chave, inversa)]
    return P, T, B


def _laje(P, T, B, zb, zt, m: _Malha | None = None, periodo: float | None = None) -> _Malha:
    """Laje sobre a planta (P, T, B): topo a z = zt(P), fundo a zb(P) e paredes ao longo da fronteira (vértices
    próprios: arestas vivas). zb/zt: arrays (len(P),). Com `periodo` (mesmas unidades), coordenadas de textura:
    projeção plana nos topos e (x + y, z) nas paredes (o tecido de carbono do cubo da hélice)."""
    m = m or _Malha()
    zb, zt = np.asarray(zb, float), np.asarray(zt, float)
    n = len(P)
    v = np.vstack([np.column_stack([P, zt]), np.column_stack([P, zb])])
    f = np.vstack([T, T[:, ::-1] + n])
    m.juntar(v, f, None if periodo is None else np.vstack([P, P]) / periodo)
    i, j = B[:, 0], B[:, 1]
    alto = np.maximum(zt[i] - zb[i], zt[j] - zb[j]) > 1e-4
    i, j = i[alto], j[alto]
    k = len(i)
    if k:
        vw = np.vstack([np.column_stack([P[i], zb[i]]), np.column_stack([P[j], zb[j]]),
                        np.column_stack([P[j], zt[j]]), np.column_stack([P[i], zt[i]])])
        a = np.arange(k)
        fw = np.vstack([np.column_stack([a, a + k, a + 2 * k]), np.column_stack([a, a + 2 * k, a + 3 * k])])
        tw = None if periodo is None else np.column_stack([vw[:, 0] + vw[:, 1], vw[:, 2]]) / periodo
        m.juntar(vw, fw, tw)
    return m


def _perfil_z(tab):
    """Função z(r) por interpolação linear de uma tabela (r, z)."""
    r = np.array([p[0] for p in tab])
    z = np.array([p[1] for p in tab])
    return lambda P: np.interp(np.hypot(P[:, 0], P[:, 1]), r, z)


def _angulo(P):
    return np.arctan2(P[:, 1], P[:, 0])


def _dif_ang(a, b):
    return (a - b + math.pi) % _TAU - math.pi


# =========================================================================================== motor: janelas e plantas
def _meia_janela(ds: _Desenho, rho):
    """Meia-abertura angular (rad) da janela a cada raio: lente (duas circunferências R de centro a D, a ±δ do eixo
    da janela, cada uma limita o lado OPOSTO) com a ponta arredondada pelo filete (r_f centrado a D_f); −1 sem janela."""
    _, D, R, delta, Df, rf, _ = ds.janela
    rho = np.asarray(rho, float)
    out = np.full(rho.shape, -1.0)
    ok = rho > 1e-9
    c = np.clip((rho ** 2 + D * D - R * R) / (2.0 * np.maximum(rho, 1e-9) * D), -1.0, 1.0)
    lente = np.where(np.abs((rho ** 2 + D * D - R * R) / (2.0 * np.maximum(rho, 1e-9) * D)) <= 1.0,
                     np.arccos(c) - math.radians(delta), -1.0)
    cf = (rho ** 2 + Df * Df - rf * rf) / (2.0 * np.maximum(rho, 1e-9) * Df)
    filete = np.where(np.abs(cf) <= 1.0, np.arccos(np.clip(cf, -1.0, 1.0)), -1.0)
    rho_t = math.sqrt(max(Df * Df - rf * rf, 0.0))                # raio da maior abertura do filete
    ponta = rho <= rho_t
    alfa = np.where(ponta, np.minimum(np.where(filete >= 0, filete, -1.0), np.where(lente >= 0, lente, 9.0)), lente)
    alfa = np.where(ponta & (filete < 0), -1.0, alfa)
    out[ok] = alfa[ok]
    return out


def _em_janela(ds: _Desenho, P):
    n, *_r, fase = ds.janela
    rho = np.hypot(P[:, 0], P[:, 1])
    a = _meia_janela(ds, rho)
    th = _angulo(P)
    dentro = np.zeros(len(P), bool)
    for k in range(n):
        dentro |= np.abs(_dif_ang(th, math.radians(fase + k * 360.0 / n))) < a
    return dentro


def _bordas_janela(ds: _Desenho, r_fim: float, r_ini: float | None = None):
    """Candidatos de fronteira das janelas: os dois lados de cada janela (θ = θ_j ± α(ρ)) e o filete."""
    n, *_r, fase = ds.janela
    _, _d, _rr, _dl, Df, rf, _f = ds.janela
    r0 = r_ini if r_ini is not None else max(Df - rf, 0.2)
    rho = np.concatenate([np.linspace(r0, min(Df, r_fim), 11), np.linspace(min(Df, r_fim), r_fim, 17)])
    a = _meia_janela(ds, rho)
    ok = a >= 0
    rho, a = rho[ok], a[ok]
    out = []
    for k in range(n):
        tj = math.radians(fase + k * 360.0 / n)
        for s in (1.0, -1.0):
            th = tj + s * a
            out.append(_curva(np.column_stack([rho * np.cos(th), rho * np.sin(th)])))
        out.append(_circ(Df * math.cos(tj), Df * math.sin(tj), rf, passo=0.5))
    return out


def _planta_base(ds: _Desenho):
    """(dentro, candidatos, r_max, r_min) da placa da base, com os furos M3 de verdade."""
    tipo, q = ds.base
    furos = [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a))) for r, a in ds.furos_base]
    r_furo_m3 = 1.25

    def fora_furos(P):
        ok = np.ones(len(P), bool)
        for x, y in furos:
            ok &= np.hypot(P[:, 0] - x, P[:, 1] - y) > r_furo_m3
        return ok
    cand = [_circ(x, y, r_furo_m3, passo=0.5) for x, y in furos]
    if tipo == "rins":
        R, rf, rr, w, vao = q["r"], q["furo"], q["r_rim"], q["meia_larg"], math.radians(q["meio_vao"])

        def dentro(P):
            r = np.hypot(P[:, 0], P[:, 1])
            ok = (r <= R) & (r >= rf) & fora_furos(P)
            th = _angulo(P)
            for c in q["centros"]:
                tc = math.radians(c)
                d = _dif_ang(th, tc)
                rim = (np.abs(r - rr) < w) & (np.abs(d) < vao)
                for s in (1.0, -1.0):
                    cx, cy = rr * math.cos(tc + s * vao), rr * math.sin(tc + s * vao)
                    rim |= np.hypot(P[:, 0] - cx, P[:, 1] - cy) < w
                ok &= ~rim
            return ok
        cand += [_circ(0, 0, R), _circ(0, 0, rf, passo=0.35)]
        for c in q["centros"]:
            tc = math.radians(c)
            cand += [_circ(0, 0, rr - w, a0=tc - vao, a1=tc + vao), _circ(0, 0, rr + w, a0=tc - vao, a1=tc + vao)]
            for s in (1.0, -1.0):
                cand.append(_circ(rr * math.cos(tc + s * vao), rr * math.sin(tc + s * vao), w, passo=0.3))
        return dentro, cand, R, rf
    if tipo == "cruz":
        R, rd, w, rc, rf = q["r"], q["r_disco"], q["meia_larg"], q["canto"], q["furo"]
        rr_f = 1.5                                       # filete da raiz dos braços (CAD)
        uc = math.sqrt((rd + rr_f) ** 2 - (w + rr_f) ** 2)

        def dentro(P):
            r = np.hypot(P[:, 0], P[:, 1])
            ok = r <= rd
            for b in q["bracos"]:
                tb = math.radians(b)
                u = P[:, 0] * math.cos(tb) + P[:, 1] * math.sin(tb)
                v = np.abs(-P[:, 0] * math.sin(tb) + P[:, 1] * math.cos(tb))
                braco = (u >= 0) & (u <= R) & (v <= w)
                canto = (u > R - rc) & (v > w - rc)
                braco &= ~canto | (np.hypot(u - (R - rc), v - (w - rc)) <= rc)
                filete = (v > w) & (r > rd) & (u < uc) & (v * uc < (w + rr_f) * u) & \
                    (np.hypot(u - uc, v - (w + rr_f)) > rr_f)
                ok |= braco | filete
            return ok & (r >= rf) & fora_furos(P)
        cand += [_circ(0, 0, rd), _circ(0, 0, rf, passo=0.35)]
        for b in q["bracos"]:
            tb = math.radians(b)
            rot = np.array([[math.cos(tb), -math.sin(tb)], [math.sin(tb), math.cos(tb)]])
            for s in (1.0, -1.0):
                p, nn = _segmento((0.0, s * w), (R - rc, s * w), passo=0.5)
                cand.append((p @ rot.T, nn @ rot.T))
                p, nn = _circ(R - rc, s * (w - rc), rc, passo=0.2)
                cand.append((p @ rot.T, nn @ rot.T))
                p, nn = _circ(uc, s * (w + rr_f), rr_f, passo=0.2)
                cand.append((p @ rot.T, nn @ rot.T))
            p, nn = _segmento((R, -(w - rc)), (R, w - rc))
            cand.append((p @ rot.T, nn @ rot.T))
        return dentro, cand, R, rf
    if tipo == "janelas2806":
        R, rf, ri, ro, rc = q["r"], q["furo"], q["r_in"], q["r_out"], q["rc"]
        ai, ao = math.radians(q["a_in"]), math.radians(q["a_out"])
        ae, we, xe = q["entalhe"]

        def quad(c):                                   # os 4 centros dos cantos da janela centrada em c
            tc = math.radians(c)
            ri_c, ro_c = ri + rc, ro - rc
            return [(ri_c * math.cos(tc - ai), ri_c * math.sin(tc - ai)), (ro_c * math.cos(tc - ao), ro_c * math.sin(tc - ao)),
                    (ro_c * math.cos(tc + ao), ro_c * math.sin(tc + ao)), (ri_c * math.cos(tc + ai), ri_c * math.sin(tc + ai))]

        def dentro(P):
            r = np.hypot(P[:, 0], P[:, 1])
            ok = (r <= R) & (r >= rf) & fora_furos(P)
            th = _angulo(P)
            for c in q["centros"]:
                Q = np.array(quad(c))
                inq = np.ones(len(P), bool)
                for i in range(4):
                    a, b = Q[i], Q[(i + 1) % 4]
                    inq &= (b[0] - a[0]) * (P[:, 1] - a[1]) - (b[1] - a[1]) * (P[:, 0] - a[0]) >= 0
                dist = np.full(len(P), np.inf)
                for i in range(4):
                    a, b = Q[i], Q[(i + 1) % 4]
                    ab = b - a
                    t = np.clip(((P - a) @ ab) / (ab @ ab), 0.0, 1.0)
                    dist = np.minimum(dist, np.linalg.norm(P - (a + t[:, None] * ab), axis=1))
                d = np.abs(_dif_ang(th, math.radians(c)))
                janela = (inq | (dist < rc) | ((r <= ri + rc) & (d <= ai)) | ((r >= ro - rc) & (d <= ao))) & \
                    (r >= ri) & (r <= ro)                  # as bordas de dentro/fora são arcos (r 7,5 / 13,5)
                ok &= ~janela
            ta = math.radians(ae)
            u = P[:, 0] * math.cos(ta) + P[:, 1] * math.sin(ta)
            v = -P[:, 0] * math.sin(ta) + P[:, 1] * math.cos(ta)
            ok &= ~((u >= xe) & (np.abs(v) < we))
            return ok
        cand += [_circ(0, 0, R), _circ(0, 0, rf, passo=0.35)]
        for c in q["centros"]:
            Q = quad(c)
            tc = math.radians(c)
            cand += [_circ(0, 0, ri, a0=tc - ai, a1=tc + ai), _circ(0, 0, ro, a0=tc - ao, a1=tc + ao)]
            for x, y in Q:
                cand.append(_circ(x, y, rc, passo=0.2))
            for i in (0, 2):                                   # os lados (tangentes comuns entre cantos)
                a, b = np.array(Q[i]), np.array(Q[(i + 1) % 4])
                nrm = np.array([-(b - a)[1], (b - a)[0]]) / np.linalg.norm(b - a)
                for s in (1.0, -1.0):
                    cand.append(_segmento(a + s * rc * nrm, b + s * rc * nrm, passo=0.35))
        ta = math.radians(ae)
        rot = np.array([[math.cos(ta), -math.sin(ta)], [math.sin(ta), math.cos(ta)]])
        for s in (1.0, -1.0):
            p, nn = _segmento((xe - 1.0, s * we), (R + 0.5, s * we), passo=0.35)
            cand.append((p @ rot.T, nn @ rot.T))
        return dentro, cand, R, rf
    if tipo == "navigator":
        R, rd, rc, dc, ac, rf = q["r"], q["r_disco"], q["rc"], q["dc"], math.radians(q["ac"]), q["furo"]
        cortes = [b + 45.0 for b in q["bracos"]]

        def dentro(P):
            r = np.hypot(P[:, 0], P[:, 1])
            ok = (r <= R) & (r >= rf) & fora_furos(P)
            th = _angulo(P)
            for c in cortes:
                tc = math.radians(c)
                corte = (r > rd) & (np.abs(_dif_ang(th, tc)) < ac)
                for s in (1.0, -1.0):
                    corte |= (r > rd) & (np.hypot(P[:, 0] - dc * math.cos(tc + s * ac),
                                                  P[:, 1] - dc * math.sin(tc + s * ac)) < rc)
                ok &= ~corte
            return ok
        cand += [_circ(0, 0, R), _circ(0, 0, rd), _circ(0, 0, rf, passo=0.35)]
        for c in cortes:
            tc = math.radians(c)
            for s in (1.0, -1.0):
                cand.append(_circ(dc * math.cos(tc + s * ac), dc * math.sin(tc + s * ac), rc, passo=0.3))
                cand.append(_segmento((rd * math.cos(tc + s * ac), rd * math.sin(tc + s * ac)),
                                      ((R + 1) * math.cos(tc + s * ac), (R + 1) * math.sin(tc + s * ac)), passo=0.35))
        return dentro, cand, R, rf
    # fpv
    R, rf = q["r"], q["furo"]
    rr, rv, angs = q["respiros"]
    resp = [(rr * math.cos(math.radians(a)), rr * math.sin(math.radians(a))) for a in angs]
    ae, we, xe = q["entalhe"]
    ta = math.radians(ae)

    def dentro(P):
        r = np.hypot(P[:, 0], P[:, 1])
        ok = (r <= R) & (r >= rf) & fora_furos(P)
        for x, y in resp:
            ok &= np.hypot(P[:, 0] - x, P[:, 1] - y) > rv
        u = P[:, 0] * math.cos(ta) + P[:, 1] * math.sin(ta)
        v = -P[:, 0] * math.sin(ta) + P[:, 1] * math.cos(ta)
        return ok & ~((u >= xe) & (np.abs(v) < we))
    cand += [_circ(0, 0, R), _circ(0, 0, rf, passo=0.35)] + [_circ(x, y, rv, passo=0.3) for x, y in resp]
    rot = np.array([[math.cos(ta), -math.sin(ta)], [math.sin(ta), math.cos(ta)]])
    for s in (1.0, -1.0):
        p, nn = _segmento((xe, s * we), (R + 0.5, s * we), passo=0.35)
        cand.append((p @ rot.T, nn @ rot.T))
    p, nn = _segmento((xe, -we), (xe, we), passo=0.35)
    cand.append((p @ rot.T, nn @ rot.T))
    return dentro, cand, R, rf


_CACHE_VERSAO: list[str] = []


def _versao_codigo() -> str:
    """Impressão digital deste ficheiro (+ numpy): a cache em disco das malhas só vale para este código."""
    if not _CACHE_VERSAO:
        import hashlib
        with open(__file__, "rb") as fh:
            _CACHE_VERSAO.append(hashlib.sha1(fh.read() + np.__version__.encode()).hexdigest()[:16])
    return _CACHE_VERSAO[0]


def _cache_disco(nome: str, calcular) -> dict:
    """{parte: (v, f, t)} de `calcular()` com cache em disco ($TMPDIR/mujoco-lab-cache/motores/<nome>-<versão>.npz,
    a versão = impressão digital deste ficheiro): poupa a triangulação (e o import do scipy) em cada processo novo —
    o cockpit e os treinos arrancam mais depressa. `DRONE_DETALHES_CACHE=0` desliga-a; qualquer erro de
    leitura/escrita cai no cálculo normal."""
    import hashlib
    import os
    import tempfile
    if os.environ.get("DRONE_DETALHES_CACHE", "1") == "0":
        return calcular()
    pasta = os.path.join(tempfile.gettempdir(), "mujoco-lab-cache", "motores")
    prefixo = hashlib.sha1(nome.encode()).hexdigest()[:12]
    arq = os.path.join(pasta, f"{prefixo}-{_versao_codigo()}.npz")
    try:
        with np.load(arq) as z:
            partes = sorted({k.rsplit("_", 1)[0] for k in z.files})
            return {p: (tuple(z[f"{p}_v"].tolist()), tuple(z[f"{p}_f"].tolist()),
                        tuple(z[f"{p}_t"].tolist()) if z[f"{p}_t"].size else None) for p in partes}
    except (OSError, KeyError, ValueError):
        pass
    out = calcular()
    try:
        os.makedirs(pasta, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=pasta, suffix=".npz")
        os.close(fd)
        np.savez(tmp, **{f"{p}_{c}": np.asarray(x if x is not None else (), dtype=np.int32 if c == "f" else float)
                         for p, (v, f, t) in out.items() for c, x in (("v", v), ("f", f), ("t", t))})
        os.replace(tmp, arq)
        for velho in os.listdir(pasta):                        # versões antigas desta malha
            if velho.startswith(prefixo + "-") and velho != os.path.basename(arq):
                os.remove(os.path.join(pasta, velho))
    except OSError:
        pass
    return out


@functools.lru_cache(maxsize=16)
def _malhas_motor_cache(chave: str) -> dict:
    """`_malhas_motor` com a cache em disco (`_cache_disco`)."""
    return _cache_disco(f"motor:{chave}", lambda: _malhas_motor(chave))


@functools.lru_cache(maxsize=16)
def _malhas_motor(chave: str) -> dict:
    """As malhas de um modelo de motor (metros, referencial do motor) — iguais nos 4 rotores (e nas variantes)."""
    ds = _DESENHOS[chave]
    out = {}
    # ---------------------------------------------------------------- base: placa (planta real) + tubo + extras
    dentro, cand, R, rf = _planta_base(ds)
    P, T, B = _triangular(dentro, cand, R, passo=3.2, r_min=rf)
    base = _laje(P, T, B, np.zeros(len(P)), np.full(len(P), ds.t_base))
    v, f, _ = _revolucao(ds.tubo, n=32)
    base.juntar(v, f)
    tipo, q = ds.base
    if tipo == "cruz":                                     # 4 pilares entre o tubo e o anel de suporte do estator
        r0, r1, z1 = q["pilar"]
        for b in q["bracos"]:
            tb = math.radians(b)
            c, s = math.cos(tb), math.sin(tb)
            w = q["meia_larg"]
            poli = [(r0 * c + w * s, r0 * s - w * c), (r1 * c + w * s, r1 * s - w * c), (r1 * c - w * s, r1 * s + w * c),
                    (r0 * c - w * s, r0 * s + w * c)]
            base.juntar(*_prisma(poli, ds.t_base, z1))
    if tipo == "navigator":                                # aba fina e a «saia» em 8 setores
        r0, r1, e, r0c = q["flange"]
        cortes = [math.radians(b + 45.0) for b in q["bracos"]]
        ac = math.radians(q["ac"])

        def dentro_aba(Pq):
            r = np.hypot(Pq[:, 0], Pq[:, 1])
            ok = (r >= r0) & (r <= r1)
            th = _angulo(Pq)
            for tc in cortes:
                corte = (r < r0c) & (np.abs(_dif_ang(th, tc)) < ac + 0.25)
                ok &= ~corte
            return ok
        cand_aba = [_circ(0, 0, r0), _circ(0, 0, r1), _circ(0, 0, r0c)]
        for tc in cortes:
            for s in (1.0, -1.0):
                a = tc + s * (ac + 0.25)
                cand_aba.append(_segmento((r0 * math.cos(a), r0 * math.sin(a)), (r0c * math.cos(a), r0c * math.sin(a)),
                                          passo=0.15))
        Pa, Ta, Ba = _triangular(dentro_aba, cand_aba, r1, passo=1.4, r_min=r0)
        _laje(Pa, Ta, Ba, np.zeros(len(Pa)), np.full(len(Pa), e), base)
        a_saia, meia = q["saia"]
        for k in range(8):
            ac0 = math.radians(a_saia + 45.0 * k)
            v, f, _ = _revolucao(ds.extra_base[0], n=10, a0=ac0 - math.radians(meia), a1=ac0 + math.radians(meia))
            base.juntar(v, f)
    else:
        for pf in ds.extra_base:
            v, f, _ = _revolucao(pf, n=48)
            base.juntar(v, f)
    out["base"] = base.saida(escala=_MM)

    # ---------------------------------------------------------------- estator: chapas (coroa, dentes, sapatas)
    r_b, r_y, r_e, z0, z1, n, w_d, r_s, a_s, sobra = ds.est
    a_s = math.radians(a_s)
    pas = _TAU / n

    def dentro_est(Pq):
        r = np.hypot(Pq[:, 0], Pq[:, 1])
        th = _angulo(Pq)
        j = np.round(th / pas)
        d = th - j * pas
        v = r * np.sin(d)
        dente = (np.abs(v) <= 0.5 * w_d) & (r <= r_s + 0.05) & (np.cos(d) > 0)
        sapata = (r >= r_s) & (r <= r_e) & (np.abs(d) <= a_s)
        return (r >= r_b) & ((r <= r_y) | dente | sapata)
    cand_e = [_circ(0, 0, r_b, passo=1.0), _circ(0, 0, r_y, passo=0.9), _circ(0, 0, r_e, passo=0.8), _circ(0, 0, r_s, passo=0.8)]
    for j in range(n):
        tj = j * pas
        c, s = math.cos(tj), math.sin(tj)
        rot = np.array([[c, -s], [s, c]])
        for sg in (1.0, -1.0):
            p, nn = _segmento((r_y - 0.3, sg * 0.5 * w_d), (r_s + 0.1, sg * 0.5 * w_d), passo=1.2)
            cand_e.append((p @ rot.T, nn @ rot.T))
            p, nn = _segmento((r_s - 0.05, 0.0), (r_e + 0.05, 0.0), passo=0.45)
            ca, sa = math.cos(sg * a_s), math.sin(sg * a_s)
            r2 = np.array([[ca, -sa], [sa, ca]])
            cand_e.append((p @ r2.T @ rot.T, nn @ r2.T @ rot.T))
    Pe, Te, Be = _triangular(dentro_est, cand_e, r_e, passo=4.5, r_min=r_b)
    out["nucleo"] = _laje(Pe, Te, Be, np.full(len(Pe), z0), np.full(len(Pe), z1)).saida(escala=_MM)

    # ---------------------------------------------------------------- bobinas (uma por dente, em cunha)
    cobre = _Malha()
    rho0, rho1 = r_y + 0.15, r_s - 0.2
    rho_c, a_r = 0.5 * (rho0 + rho1), 0.5 * (rho1 - rho0)
    psi_h = 0.44 * pas
    meia_z = 0.5 * (z1 - z0) + sobra
    zc = 0.5 * (z0 + z1)
    sv, sf, su = _superelipsoide(a_r, psi_h * rho_c, meia_z, e=0.30, nu=10, nv=5)
    for j in range(n):
        phi0 = j * pas
        rho = rho_c + sv[:, 0]
        ang = phi0 + sv[:, 1] / rho_c
        vv = np.column_stack([rho * np.cos(ang), rho * np.sin(ang), zc + sv[:, 2]])
        tt = np.column_stack([np.full_like(su, 0.25), rho * _MM / (2.0 * _PASSO_ESPIRA)])
        cobre.juntar(vv, sf, tt)
    out["cobre"] = cobre.saida(textura=True, escala=_MM)

    # ---------------------------------------------------------------- anel de aço (+ ímanes)
    v, f, _ = _revolucao(ds.anel, n=48)
    out["anel"] = _Malha().juntar(v, f).saida(escala=_MM)

    # ---------------------------------------------------------------- tampa: cubo + raios (A), aro (B), pontas (C)
    tampa = _Malha()
    fur = [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), 0.5 * dd) for r, a, dd in ds.furos_topo]

    def fora_furos_topo(Pq):
        ok = np.ones(len(Pq), bool)
        for x, y, rr in fur:
            ok &= np.hypot(Pq[:, 0] - x, Pq[:, 1] - y) > rr
        return ok

    def dentro_a(Pq):
        r = np.hypot(Pq[:, 0], Pq[:, 1])
        return (r >= ds.r_furo_tampa) & (r <= ds.r_cut) & ~_em_janela(ds, Pq) & fora_furos_topo(Pq)
    cand_a = [_circ(0, 0, ds.r_cut), _circ(0, 0, ds.r_furo_tampa, passo=0.4)] + _bordas_janela(ds, ds.r_cut + 0.5)
    cand_a += [_circ(x, y, rr, passo=0.55) for x, y, rr in fur]
    quebras = sorted({p[0] for p in ds.tampa_top + ds.tampa_bot if ds.r_furo_tampa + 0.1 < p[0] < ds.r_cut - 0.1})
    Pa, Ta, Ba = _triangular(dentro_a, cand_a, ds.r_cut, aneis=quebras, passo=2.8, r_min=ds.r_furo_tampa)
    _laje(Pa, Ta, Ba, _perfil_z(ds.tampa_bot)(Pa), _perfil_z(ds.tampa_top)(Pa), tampa)
    v, f, _ = _revolucao(ds.aro, n=48)
    tampa.juntar(v, f)
    zc_top = _perfil_z(ds.pontas_top)
    rs_c = np.linspace(ds.r_cut, ds.d * 0.5, 200)
    zz = zc_top(np.column_stack([rs_c, np.zeros_like(rs_c)]))
    alto = zz > ds.z_aro + 0.02
    r_c_max = float(rs_c[alto].max()) if alto.any() else ds.r_cut

    def dentro_c(Pq):
        r = np.hypot(Pq[:, 0], Pq[:, 1])
        return (r >= ds.r_cut) & (r <= r_c_max) & ~_em_janela(ds, Pq)
    if r_c_max > ds.r_cut + 0.05:
        cand_c = [_circ(0, 0, ds.r_cut, passo=0.35), _circ(0, 0, r_c_max, passo=0.35)] + \
            _bordas_janela(ds, r_c_max + 0.3, r_ini=ds.r_cut - 0.3)
        quebras_c = sorted({p[0] for p in ds.pontas_top if ds.r_cut + 0.05 < p[0] < r_c_max - 0.05})
        Pc, Tc, Bc = _triangular(dentro_c, cand_c, r_c_max, aneis=quebras_c, passo=1.5, r_min=ds.r_cut)
        _laje(Pc, Tc, Bc, np.full(len(Pc), ds.z_aro), np.maximum(zc_top(Pc), ds.z_aro), tampa)
    out["tampa"] = tampa.saida(escala=_MM)

    # ---------------------------------------------------------------- veio, rolamento, extras de aço
    aco = _Malha()
    v, f, _ = _revolucao(ds.veio, n=24)
    aco.juntar(v, f)
    if ds.rolamento:
        v, f, _ = _revolucao(ds.rolamento, n=24)
        aco.juntar(v, f)
    for pf in ds.extra_aco:
        v, f, _ = _revolucao(pf, n=24)
        aco.juntar(v, f)
    out["eixo"] = aco.saida(escala=_MM)
    return out



# =========================================================================================== hélice (pá paramétrica)
def _forma_pa(dh: _Helice) -> dict:
    """Parâmetros da planta da pá (x = r/R): pescoço no cubo, corda máxima em x_p, afunilamento até x_t, ponta elítica.
    A corda máxima sai da corda MÉDIA do catálogo (média de x_h a 1 = `corda_media`)."""
    fam = {"scimitar_cf": (0.27, 0.93, 0.035, 0.040), "mr_naca": (0.30, 0.90, 0.020, 0.045),
           "tri_pa_fpv": (0.38, 0.88, 0.015, 0.035)}.get(dh.perfil, (0.30, 0.91, 0.025, 0.040))
    x_p, x_t, varr, arq = fam
    x_h = dh.r_cubo / dh.r
    c_h = min(1.15 * dh.h_cubo, 1.6 * dh.r_cubo)
    lam = min(max(dh.afun, 0.15), 1.0)
    xs = np.linspace(x_h, 1.0, 4001)
    alfa, beta = np.zeros_like(xs), np.zeros_like(xs)
    sub = xs <= x_p
    s = np.sin(0.5 * math.pi * (xs[sub] - x_h) / max(x_p - x_h, 1e-9))
    alfa[sub], beta[sub] = 1.0 - s, s
    mid = (xs > x_p) & (xs <= x_t)
    beta[mid] = 1.0 - (1.0 - lam) * ((xs[mid] - x_p) / (x_t - x_p)) ** _CHEIA
    tip = xs > x_t
    beta[tip] = lam * np.sqrt(np.clip(1.0 - ((xs[tip] - x_t) / (1.0 - x_t)) ** 2, 0.0, 1.0))
    i_a, i_b = float(np.mean(alfa)), float(np.mean(beta))
    c_pico = max((dh.corda - c_h * i_a) / max(i_b, 1e-9), 1.3 * c_h)
    x_livre = (8.1 * _MM / dh.r) if dh.fixacao == "parafusos" else 0.0       # furos M3 a 6 mm (Ø3,2)
    return {"x_h": x_h, "x_p": x_p, "x_t": x_t, "c_h": c_h, "c_pico": c_pico, "lam": lam,
            "varr": varr * dh.r, "arq": arq, "d_off": 0.10 * c_pico, "x_livre": min(x_livre, 0.9 * x_h)}


def _seccao_pa(dh: _Helice, fp: dict, x: float, nc: int = 12, inflar: float = 0.0) -> np.ndarray:
    """Laço da secção à estação x (pá ao longo de +x, a avançar para +y = sentido CCW visto de cima): extradorso do bordo
    de fuga ao de ataque e intradorso de volta — (2·nc − 1) × 3, em metros."""
    x_h, x_p, x_t, c_h, c_pk = fp["x_h"], fp["x_p"], fp["x_t"], fp["c_h"], fp["c_pico"]
    if x <= x_h:
        c, u_s = c_h, 0.0
    elif x <= x_p:
        u_s = math.sin(0.5 * math.pi * (x - x_h) / max(x_p - x_h, 1e-9))
        c = c_h + (c_pk - c_h) * u_s
    elif x <= x_t:
        u_s = 1.0
        c = c_pk * (1.0 - (1.0 - fp["lam"]) * ((x - x_p) / (x_t - x_p)) ** _CHEIA)
    else:
        u_s = 1.0
        c = None
    varr = fp["varr"] * max(0.0, (x - 0.55) / 0.45) ** 2
    y_le_reto = 0.5 * c_pk - fp["d_off"]
    if x <= x_t:
        y_mid = (-fp["d_off"] * u_s) if x <= x_p else (y_le_reto - 0.5 * c)
        y_mid -= varr
    else:                                                   # ponta elítica, simétrica em torno da linha média em x_t
        c_t = c_pk * fp["lam"]
        w = (x - x_t) / (1.0 - x_t)
        c = c_t * math.sqrt(max(1.0 - w * w, 0.0))
        y_mid = (y_le_reto - 0.5 * c_t) - varr
    # espessura (pescoço gordo → ponta fina), arqueamento e passo
    t_ponta = max(0.00055, 0.0048 * dh.r)
    t_raiz = 0.55 * dh.h_cubo
    t = t_raiz if x <= x_h else t_ponta + (t_raiz - t_ponta) * ((1.0 - x) / (1.0 - x_h)) ** 1.4
    th_g = math.atan2(dh.passo, _TAU * max(x * dh.r, 1e-6))
    th_max = math.radians(23.0)                              # junto ao cubo o passo real fica-se pelos ~21–23°
    theta = th_g * (1.0 + (th_g / th_max) ** 10) ** -0.1
    m_c, p_c = fp["arq"] * u_s, 0.40
    s = 0.5 * (1.0 - np.cos(np.linspace(0.0, math.pi, nc)))          # LE (0) → TE (1), cosseno
    tau = t / max(c, 1e-6)
    yt = 5.0 * tau * c * (0.2969 * np.sqrt(s) - 0.1260 * s - 0.3516 * s ** 2 + 0.2843 * s ** 3 - 0.1015 * s ** 4)
    yt += max(0.00008, 0.06 * t) * s + inflar
    yc = np.where(s < p_c, m_c / p_c ** 2 * (2 * p_c * s - s ** 2),
                  m_c / (1 - p_c) ** 2 * (1 - 2 * p_c + 2 * p_c * s - s ** 2)) * c
    y_le = y_mid + 0.5 * c + inflar
    eta = y_le - s * (c + 2.0 * inflar)
    y_rot = y_mid + 0.10 * c
    sup = np.column_stack([eta, yc + yt])[::-1]                         # TE → LE
    inf = np.column_stack([eta, yc - yt])[1:]                           # LE → TE
    laco = np.vstack([sup, inf])
    ct, st = math.cos(theta), math.sin(theta)
    de = laco[:, 0] - y_rot
    yy = y_rot + de * ct - laco[:, 1] * st
    zz = de * st + laco[:, 1] * ct
    return np.column_stack([np.full(len(laco), x * dh.r), yy, zz])


def _loft(lacos: list[np.ndarray], tex: bool = True):
    """Superfície fechada por estações: pele lisa (bordo de ataque redondo), faixa do bordo de fuga com vértices próprios
    (aresta viva) e tampas planas nas duas pontas. Orientação para fora (pá CCW)."""
    ns, npt = len(lacos), len(lacos[0])
    P = np.stack(lacos)                                                  # ns × npt × 3
    arc = np.concatenate([np.zeros((ns, 1)), np.cumsum(np.linalg.norm(np.diff(P, axis=1), axis=2), axis=1)], axis=1)
    v = [P.reshape(-1, 3)]
    t = [np.column_stack([P[:, :, 0].ravel(), arc.ravel()]) / _PERIODO_TECIDO]
    idx = np.arange(ns * npt).reshape(ns, npt)
    f = []
    for j in range(ns - 1):
        for i in range(npt - 1):
            a, b, c, d = idx[j, i], idx[j + 1, i], idx[j + 1, i + 1], idx[j, i + 1]
            f.extend([(a, b, c), (a, c, d)])
    base = ns * npt                                                      # bordo de fuga (último → primeiro ponto do laço)
    te = np.stack([P[:, -1], P[:, 0]], axis=1).reshape(-1, 3)
    v.append(te)
    t.append(np.column_stack([te[:, 0], te[:, 1]]) / _PERIODO_TECIDO)
    for j in range(ns - 1):
        a, b, c, d = base + 2 * j, base + 2 * (j + 1), base + 2 * (j + 1) + 1, base + 2 * j + 1
        f.extend([(a, b, c), (a, c, d)])
    n0 = base + 2 * ns
    for j, sinal in ((0, 1), (ns - 1, -1)):                              # tampas: raiz (−x) e ponta (+x)
        lac = P[j]
        cen = lac.mean(axis=0)
        v.append(np.vstack([cen, lac]))
        t.append(np.column_stack([np.r_[cen[0], lac[:, 0]], np.r_[cen[1], lac[:, 1]]]) / _PERIODO_TECIDO)
        for i in range(npt):
            i2 = (i + 1) % npt
            tri = (n0, n0 + 1 + i, n0 + 1 + i2)
            f.append(tri if sinal > 0 else tri[::-1])
        n0 += npt + 1
    return np.concatenate(v), np.array(f), (np.concatenate(t) if tex else None)


def _estacoes(fp: dict) -> tuple[np.ndarray, np.ndarray, tuple[float, float]]:
    """Estações da raiz (até 50 % do raio) e da ponta (com as bordas da faixa colorida como estações próprias)."""
    x_h, x_p, x_t = fp["x_h"], fp["x_p"], fp["x_t"]
    x0 = max(0.55 * x_h, fp.get("x_livre", 0.0))
    raiz = np.unique(np.concatenate([np.linspace(x0, x_h, 3), np.linspace(x_h, x_p, 7), np.linspace(x_p, 0.5, 5)]))
    f0, f1 = x_t - 0.055, x_t + 0.012
    w = np.sin(np.linspace(0.0, 0.5 * math.pi, 7))[1:] * 0.985
    ponta = np.unique(np.concatenate([np.linspace(0.5, f0, 7), np.linspace(f0, f1, 4),
                                      [x_t], x_t + (1.0 - x_t) * w]))
    return raiz, ponta, (f0, f1)



# =========================================================================================== hélice (dados, malhas)
@dataclass(frozen=True)
class _Helice:
    r: float          # raio (m)
    corda: float      # corda média (m)
    afun: float       # afunilamento c_ponta / c_máx
    passo: float      # passo geométrico (m)
    pas: int
    perfil: str       # scimitar_cf | mr_naca | tri_pa_fpv
    r_cubo: float     # raio do cubo (m)
    h_cubo: float     # espessura do cubo (m)
    fixacao: str      # "parafusos" (T-mount: 2 × M3 a 12 mm) | "porca" (furo central)
    furo: float       # Ø do furo central (m)


def _dims_helice(helice) -> _Helice:
    """Cubo e fixação por família (ESTIMADOS onde a T-Motor/APC não cotam): T-Motor P/MF — cubo T-mount Ø22 × 6 mm
    (o pino de 6 mm do MN4004 e os M3×10 da T-Motor fecham com 6 mm), furo Ø6 e 2 × M3 a 12 mm; 5″ tri-pá — cubo
    Ø15 × 6,5 mm no perno M5; APC MR — cubo Ø22 × 8,4 mm, furo de 1/4″ no adaptador M6."""
    perfil = str(helice.perfil)
    if perfil == "scimitar_cf":
        r_cubo, h_cubo, fix, furo = 0.011, 0.006, "parafusos", 0.006
    elif perfil == "tri_pa_fpv":
        r_cubo, h_cubo, fix, furo = 0.0075, 0.0065, "porca", 0.005
    else:
        r_cubo, h_cubo, fix, furo = 0.011, 0.0084, "porca", 0.00635
    return _Helice(r=float(helice.raio), corda=float(helice.corda_media), afun=float(helice.afunilamento),
                   passo=float(helice.passo), pas=max(int(helice.pas), 2), perfil=perfil, r_cubo=r_cubo, h_cubo=h_cubo,
                   fixacao=fix, furo=furo)


def _estacoes_impressao(fp: dict) -> tuple[float, float]:
    """A ESTAMPAGEM branca no extradorso junto ao cubo (o logótipo «T-MOTOR» e o «15*5 CW» das T-Motor/APC,
    simplificados numa tira ao longo da pá): é a marca que se vê a rodar."""
    x0 = max(fp["x_h"] + 0.05, 0.16)
    return x0, x0 + 0.15


def _seccao_estampa(dh: _Helice, fp: dict, x: float, s0: float = 0.30, s1: float = 0.58, nc: int = 41) -> np.ndarray:
    """Laço fino da tira estampada: o extradorso entre as frações de corda s0..s1, levantado 0,10 mm (por fora) e
    0,02 mm (por dentro)."""
    s = 0.5 * (1.0 - np.cos(np.linspace(0.0, math.pi, nc)))
    sup_idx = [i for i in range(nc) if s0 <= s[nc - 1 - i] <= s1]
    fora = _seccao_pa(dh, fp, x, nc=nc, inflar=0.00010)[sup_idx]
    dentro = _seccao_pa(dh, fp, x, nc=nc, inflar=0.00002)[sup_idx]
    return np.vstack([fora, dentro[::-1]])


@functools.lru_cache(maxsize=16)
def _malhas_helice(dh: _Helice) -> dict:
    """Malhas da hélice no referencial do cubo (plano médio do cubo em z = 0, pá 1 ao longo de +x): raiz, ponta e
    faixa estampada nas variantes CCW e CW (espelho) e o cubo de carbono."""
    fp = _forma_pa(dh)
    raiz_x, ponta_x, _ = _estacoes(fp)
    f0, f1 = _estacoes_impressao(fp)
    out = {}
    pecas = {"raiz": [_seccao_pa(dh, fp, x) for x in raiz_x],
             "ponta": [_seccao_pa(dh, fp, x) for x in ponta_x],
             "faixa": [_seccao_estampa(dh, fp, x) for x in np.linspace(f0, f1, 7)]}
    for nome, lacos in pecas.items():
        v, f, t = _loft(lacos, tex=(nome != "faixa"))
        for sent, esp in (("ccw", False), ("cw", True)):
            m = _Malha()
            m.juntar(v, f, t, espelho_y=esp)
            out[f"{nome}_{sent}"] = m.saida(textura=(nome != "faixa"), mtex=_TEX_CARBONO)
    r, h = dh.r_cubo / _MM, dh.h_cubo / _MM                     # mm
    ch = 0.1 * h
    rf = 0.5 * dh.furo / _MM
    furos = [(6.0, 0.0), (-6.0, 0.0)] if dh.fixacao == "parafusos" else []     # no eixo das pás (x do cubo)

    def dentro(P):
        rr = np.hypot(P[:, 0], P[:, 1])
        ok = (rr <= r) & (rr >= rf)
        for x, y in furos:
            ok &= np.hypot(P[:, 0] - x, P[:, 1] - y) > 1.6
        return ok
    cand = [_circ(0, 0, r, passo=0.5), _circ(0, 0, rf, passo=0.3), _circ(0, 0, r - ch, passo=0.5)] + \
        [_circ(x, y, 1.6, passo=0.25) for x, y in furos]
    P, T, B = _triangular(dentro, cand, r, aneis=(r - ch,), passo=1.4, r_min=rf)
    zt = _perfil_z(_p((rf, 0.5 * h), (r - ch, 0.5 * h), (r, 0.5 * h - ch)))(P)
    zb = _perfil_z(_p((rf, -0.5 * h), (r - ch, -0.5 * h), (r, -0.5 * h + ch)))(P)
    out["cubo"] = _laje(P, T, B, zb, zt, periodo=_PERIODO_TECIDO / _MM).saida(textura=True, mtex=_TEX_CARBONO,
                                                                            escala=_MM)
    return out


@functools.lru_cache(maxsize=32)
def _malhas_fixacao(dh: _Helice, pino: tuple) -> dict:
    """Peças de aperto da hélice (m), referencial do cubo com z = 0 na face de BAIXO do cubo (= topo do motor):
    anel de latão de centragem, cabeças ISO 4762 M3 em cima da tampa (T-mount) ou anilha + porca ISO 10511 (furo
    central), e o adaptador M6 (APC)."""
    from . import ferragens as fer
    out = {}
    d_pino, h_pino = pino
    h = dh.h_cubo / _MM
    if dh.fixacao == "parafusos":
        anel = _Malha()
        anel.juntar(*_arco(0.5 * d_pino + 0.02, 0.5 * dh.furo / _MM - 0.02, 0.0, min(h_pino, h) - 0.05, n=32)[:2])
        out["centro"] = anel.saida(escala=_MM)
        vc, fc = fer._cabeca_4762("M3")
        vc = np.array(vc, float)
        vc[:, 2] *= -1.0                                       # cabeça para cima (+z), face de apoio em z = 0
        par = _Malha()
        z_t = h + _ESP_TAMPA
        for sy in (1.0, -1.0):
            par.juntar(vc, np.asarray(fc)[:, ::-1], desloc=(0.0, sy * 6.0, z_t))
        out["parafusos"] = par.saida(escala=_MM)
        furos = [(0.0, 6.0), (0.0, -6.0)]                      # tampa de aperto Ø16 × 1,5: furo do pino + 2 × Ø3,2

        def dentro(P):
            rr = np.hypot(P[:, 0], P[:, 1])
            ok = (rr <= _R_TAMPA) & (rr >= 2.3)
            for x, y in furos:
                ok &= np.hypot(P[:, 0] - x, P[:, 1] - y) > 1.6
            return ok
        cand = [_circ(0, 0, _R_TAMPA, passo=0.4), _circ(0, 0, 2.3, passo=0.25)] + \
            [_circ(x, y, 1.6, passo=0.25) for x, y in furos]
        P, T, B = _triangular(dentro, cand, _R_TAMPA, passo=1.2, r_min=2.3)
        out["tampa"] = _laje(P, T, B, np.full(len(P), h), np.full(len(P), h + _ESP_TAMPA)).saida(escala=_MM)
    else:
        rosca = "M5" if dh.perfil == "tri_pa_fpv" else "M6"
        (vm, fm), (vn, fn) = fer._porca_10511(rosca)
        va, fa = fer._anilha_7089(rosca)
        z0 = h
        porca = _Malha()
        porca.juntar(va, fa, desloc=(0.0, 0.0, z0))
        z1 = z0 + fer.ISO7089[rosca][2]
        porca.juntar(vm, fm, desloc=(0.0, 0.0, z1)).juntar(vn, fn, desloc=(0.0, 0.0, z1))
        out["porca"] = porca.saida(escala=_MM)
        if rosca == "M6":                                        # adaptador M6 (flange nos 4 M3 do topo + perno)
            ad = _Malha()
            ad.juntar(*_revolucao([[(0.0, -3.0), (10.0, -3.0)], [(10.0, -3.0), (10.0, 0.0)], [(10.0, 0.0), (3.0, 0.0)],
                                   [(3.0, 0.0), (3.0, h + 9.0)], [(3.0, h + 9.0), (0.0, h + 9.0)]], n=40)[:2])
            out["adaptador"] = ad.saida(escala=_MM)
    return out


_ESP_TAMPA = 1.5          # mm: tampa de aperto (alumínio anodizado preto) — ESTIMADO
_R_TAMPA = 8.0            # mm
_L_PARAF_HELICE = 10.0    # mm: M3×10 (T-Motor, hélices de 14–18″)


# =========================================================================================== materiais e texturas
def _por_nome(lista, nome: str):
    """O elemento do spec com esse nome, procurado na LISTA (texturas e malhas; o mesmo cuidado de `ctx.obter_material`:
    no MuJoCo 3.15 a procura por nome falha para elementos acrescentados depois de um `spec.delete`)."""
    return next((e for e in lista if e.name == nome), None)


def _textura(ctx, nome: str, rgb1, rgb2, lado: int = 64, **kw) -> None:
    """Xadrez 2 × 2 procedimental (`builtin` checker) — exporta-se no MJCF (`to_xml`), ao contrário de imagens em memória."""
    if _por_nome(ctx.spec.textures, nome) is None:
        ctx.spec.add_texture(name=nome, type=mujoco.mjtTexture.mjTEXTURE_2D, builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
                             rgb1=list(rgb1), rgb2=list(rgb2), width=lado, height=lado, **kw)


def _materiais(ctx, dh: _Helice) -> dict:
    """Materiais deste módulo (prefixo `det_mot_`/`det_hel_`) e os já existentes reutilizados (fios)."""
    _textura(ctx, "det_hel_tecido", (0.130, 0.135, 0.150), (0.080, 0.084, 0.095))
    _textura(ctx, "det_mot_espiras", (0.70, 0.37, 0.16), (0.52, 0.25, 0.09), lado=32)
    mat = {
        # alumínio 6061 anodizado preto acetinado (base, tampa) e o anel de aço com o mesmo acabamento preto
        "preto": ctx.material("det_mot_anodizado", [0.045, 0.047, 0.053, 1.0], specular=0.45, shininess=0.55),
        # alumínio anodizado natural (Navigator MN3508: «silver housing»)
        "prata": ctx.material("det_mot_prata", [0.66, 0.67, 0.70, 1.0], specular=0.75, shininess=0.65),
        "nucleo": ctx.material("det_mot_nucleo", [0.16, 0.165, 0.18, 1.0], specular=0.5, shininess=0.45),
        "cobre": ctx.material("det_mot_cobre", [1.0, 1.0, 1.0, 1.0], specular=0.85, shininess=0.8),
        "aco": ctx.material("det_mot_aco", [0.66, 0.67, 0.70, 1.0], specular=0.9, shininess=0.8),
        "termo": ctx.material("det_mot_termo", [0.035, 0.035, 0.04, 1.0], specular=0.15, shininess=0.25),
        "ouro": ctx.material("det_mot_ouro", [0.93, 0.73, 0.30, 1.0], specular=1.0, shininess=0.9),
        "fio_cobre": ctx.material("det_mot_fio_esmaltado", [0.70, 0.33, 0.14, 1.0], specular=0.8, shininess=0.75),
        "latao": ctx.material("det_hel_latao", [0.80, 0.64, 0.32, 1.0], specular=0.9, shininess=0.8),
        "estampa": ctx.material("det_hel_estampa", [0.88, 0.89, 0.90, 1.0], specular=0.3, shininess=0.4),
        "fio_preto": "fio_preto",
    }
    if dh.perfil == "scimitar_cf":
        mat["pa"] = ctx.material("det_hel_carbono", [1.0, 1.0, 1.0, 1.0], specular=0.85, shininess=0.92)
        tex = "det_hel_tecido"
    else:                                                   # APC / FPV: plástico injetado
        cinza = [0.55, 0.52, 0.46, 1.0] if dh.perfil == "mr_naca" else [0.10, 0.10, 0.11, 1.0]
        mat["pa"] = ctx.material("det_hel_plastico", cinza, specular=0.35, shininess=0.4)
        tex = None
    for chave, nome_tex in (("cobre", "det_mot_espiras"), ("pa", tex)):
        if nome_tex:
            ctx.obter_material(mat[chave]).textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = nome_tex
    return mat


def _malha(ctx, nome: str, dados: tuple) -> str:
    """Regista a malha (uma vez por spec) e devolve o nome."""
    if _por_nome(ctx.spec.meshes, nome) is None:
        v, f, t = dados
        kw = {"usertexcoord": list(t)} if t is not None else {}
        me = ctx.spec.add_mesh(name=nome, uservert=list(v), userface=list(f), **kw)
        me.inertia = mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL
    return nome


# =========================================================================================== montagem
_ANTIGOS_MOTOR = ("estator_cobre", "sino_anel", "base_cnc", "raio_1", "raio_2", "raio_3", "eixo")
_ANTIGOS_PA = ("raiz", "ponta", "faixa")
_PARTES = ("base", "nucleo", "cobre", "anel", "tampa", "eixo")


def _qz(ang: float) -> list[float]:
    return [math.cos(0.5 * ang), 0.0, 0.0, math.sin(0.5 * ang)]


def _rz(ang: float, x: float, y: float) -> np.ndarray:
    c, s = math.cos(ang), math.sin(ang)
    return np.array([c * x - s * y, s * x + c * y])


def _chave_id(ident: str) -> str:
    """O desenho de um id do painel (o painel não traz o objeto Motor: só o id)."""
    from types import SimpleNamespace
    return _chave_motor(SimpleNamespace(id=ident, modelo="", dados={}))


def _comprimento_parafuso_base(ds: _Desenho, e_placa: float) -> float:
    """O M3 normalizado mais curto com a rosca da base TODA metida (+0,5 mm de ponta) sem passar da cota máxima."""
    from .ferragens import COMPRIMENTOS
    minimo, maximo = e_placa + ds.t_base + 0.5, e_placa + ds.prof_rosca_max
    for L in COMPRIMENTOS["M3"]:
        if minimo - 1e-9 <= L <= maximo + 1e-9:
            return float(L)
    return float(min((L for L in COMPRIMENTOS["M3"] if L >= minimo), default=COMPRIMENTOS["M3"][-1]))


def _geoms_motor(ctx, corpo, k: int, ds: _Desenho, mat: dict, pos, quat, nomes: dict) -> list[str]:
    """As 6 peças de um modelo de motor (malhas partilhadas) com os nomes dados por parte; devolve os nomes."""
    mm = {p: _malha(ctx, f"det_mot_{ds.chave}_{p}", _malhas_motor_cache(ds.chave)[p]) for p in _PARTES}
    cor = mat["prata"] if ds.cor == "prata" else mat["preto"]
    material = {"base": cor, "nucleo": mat["nucleo"], "cobre": mat["cobre"], "anel": mat["preto"] if ds.serie != "navigator"
                else cor, "tampa": cor, "eixo": mat["aco"]}
    feitos = []
    for parte in _PARTES:
        nome = nomes[parte]
        ctx.geom(corpo, nome, _GRUPO_MOTOR, type=mujoco.mjtGeom.mjGEOM_MESH, meshname=mm[parte],
                 material=material[parte], pos=list(pos), quat=list(quat))
        feitos.append(nome)
    return feitos


# ---------------------------------------------------------------- cabos do motor SOLDADOS a um ESC 4 em 1 (5″)
_PONTA_ESTANHADA_MM = 3.0               # condutor descarnado e estanhado na ponta (18 AWG numa ilha: 2–3 mm)
_FAIXAS_SOLDADO_MM = (4.6, 6.7, 8.8)    # fases a, b, c lado a lado (Ø1,9 mm, passo 2,1 mm), do lado +n do eixo do braço
_FOLGA_RAIZ_MM = 3.0                    # da ponta à peça mais exterior da raiz do braço (espaçador / placa de cima)


def _condutor(ds: _Desenho) -> tuple[str, float]:
    """(bitola, raio do condutor ESTANHADO em mm) dos cabos de fase do motor: silicone 18 AWG (cobre Ø1,02 mm, ~1,1 mm
    estanhado) ou 20 AWG; no fio esmaltado é o próprio condutor (o esmalte raspa-se e estanha-se)."""
    tipo, _l, r_f, _p, _cor = ds.cabo
    if tipo == "silicone":
        return ("18 AWG", 0.55) if r_f >= 0.9 else ("20 AWG", 0.45)
    return (f"fio esmaltado Ø{2.0 * r_f:.1f} mm".replace(".", ","), r_f)


def _t_max_caixa(c, ex, ey, hx: float, hy: float, u, w) -> float | None:
    """Maior t com w + u·t dentro do retângulo (centro c, eixos ex/ey, meias-medidas hx/hy), tudo em 2D — None se a
    reta não o corta."""
    lo, hi = -math.inf, math.inf
    for e, h in ((ex, hx), (ey, hy)):
        a0, a1 = float((w - c) @ e), float(u @ e)
        if abs(a1) < 1e-12:
            if abs(a0) > h:
                return None
            continue
        t0, t1 = (-h - a0) / a1, (h - a0) / a1
        lo, hi = max(lo, min(t0, t1)), min(hi, max(t0, t1))
    return hi if hi >= lo else None


def _t_raiz_braco(ctx, corpo: str, o, u, nrm, faixas, r_f: float) -> float | None:
    """Até onde vem a RAIZ do braço, em t (m ao longo do braço desde o centro do motor `o`, negativo para o centro do
    drone): o ponto mais exterior dos espaçadores da pilha perto do eixo do braço (|n| ≤ 15 mm) e das placas da pilha
    nas faixas dos cabos (± o raio do fio + 0,5 mm). Lê os geoms do modelo físico (a estrutura desenha estas peças por
    cima deles, depois dos motores). None se não há nenhuma."""
    o2, u2, n2 = np.asarray(o, float)[:2], np.asarray(u, float)[:2], np.asarray(nrm, float)[:2]
    t_max = None
    for g in ctx.spec.geoms:
        nome = g.name or ""
        if g.parent is None or g.parent.name != corpo:
            continue
        c = np.array(g.pos, dtype=float)[:2]
        ts = []
        if nome.startswith("espacador") and int(g.type) == int(mujoco.mjtGeom.mjGEOM_CYLINDER):
            t_c, n_c = float((c - o2) @ u2), float((c - o2) @ n2)
            if t_c < 0.0 and abs(n_c) <= 0.015:
                ts.append(t_c + float(g.size[0]))
        elif nome in ("placa_superior", "placa_inferior") and int(g.type) == int(mujoco.mjtGeom.mjGEOM_BOX):
            R = np.zeros(9)
            mujoco.mju_quat2Mat(R, np.asarray(g.quat, dtype=float))
            R = R.reshape(3, 3)
            for n in faixas:
                for dn in (-r_f - 0.0005, r_f + 0.0005):
                    t = _t_max_caixa(c, R[:2, 0], R[:2, 1], float(g.size[0]), float(g.size[1]), u2, o2 + n2 * (n + dn))
                    if t is not None and t < 0.0:
                        ts.append(t)
        for t in ts:
            t_max = t if t_max is None else max(t_max, t)
    return t_max


def _cabos_soldados(ctx, corpo: str, k: int, ds: _Desenho, mat: dict, o, inicio, u, nrm, g_br, z0: float) -> None:
    """ESC 4 em 1 (5″): num 5″ não há balas — os 3 fios do motor vão SOLDADOS direto às ilhas do 4 em 1. Desenham-se
    do ponto comum, deitados no topo do braço e lado a lado do lado +n do eixo (as cabeças M3 do braço e os
    espaçadores da pilha estão NO eixo, |n| ≤ 3,3 mm), até à saída da raiz do braço (3 mm para fora do espaçador e da
    placa de cima), a acabar numa ponta descarnada e ESTANHADA de 3 mm (`motor{k}_fase_{x}_ponta`). Os `fios` fazem a
    continuação até às ilhas, com a solda, a partir das âncoras `mot{k}_fio_fim_{a,b,c}` em `registo.notas["ancoras"]`
    (corpo, ponto = a ponta livre do condutor no eixo dele, direção de saída para o centro, bitola e diâmetros)."""
    _tipo, _l, r_f, _p, cor = ds.cabo
    bitola, r_cu = _condutor(ds)
    m_fio = mat["fio_cobre"] if cor == "cobre" else mat["fio_preto"]
    m_sn = ctx.material("det_mot_estanho", [0.70, 0.70, 0.68, 1.0], specular=0.75, shininess=0.7)   # Sn-Ag-Cu
    o, u, nrm = (np.asarray(v, dtype=float) for v in (o, u, nrm))
    sinal_n = 1.0 if float(u[0] * u[1]) > 0.0 else -1.0
    faixas = [sinal_n * n * _MM for n in _FAIXAS_SOLDADO_MM]
    r_i, l_p = r_f * _MM, _PONTA_ESTANHADA_MM * _MM
    z_topo = float(g_br.pos[2]) + float(g_br.size[2]) if g_br is not None else z0
    z_w = z_topo + r_i + 0.00005                                    # deitados no braço (0,05 mm de folga)
    t_comum = float((np.asarray(inicio[1], dtype=float) - o)[:2] @ u[:2])
    t_raiz = _t_raiz_braco(ctx, corpo, o, u, nrm, faixas, r_i)
    t_ponta = t_comum - 0.020 if t_raiz is None else min(t_raiz + _FOLGA_RAIZ_MM * _MM, t_comum - 0.015)
    notas = ctx.registo.notas.setdefault("ancoras", {})
    for j, fase in enumerate("abc"):
        p3 = o + u * t_ponta + nrm * faixas[j]
        p3[2] = z_w                                                 # a ponta livre do condutor estanhado
        p2 = p3 + u * l_p                                           # onde acaba o isolamento (a cápsula fecha aí)
        ctx.geom(corpo, f"motor{k}_fase_{fase}", _GRUPO_MOTOR, type=mujoco.mjtGeom.mjGEOM_CAPSULE, size=[r_i, 0, 0],
                 fromto=[float(x) for x in inicio[j]] + [float(x) for x in p2 + u * r_i], material=m_fio)
        ctx.geom(corpo, f"motor{k}_fase_{fase}_ponta", _GRUPO_MOTOR, type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                 size=[r_cu * _MM, 0, 0], fromto=[float(x) for x in p2 + u * r_i] + [float(x) for x in p3],
                 material=m_sn)
        notas[f"mot{k}_fio_fim_{fase}"] = {
            "corpo": corpo, "ponto": [float(x) for x in p3], "direcao": [float(x) for x in -u],
            "bitola": bitola, "d_fio_mm": round(2.0 * r_f, 3), "d_condutor_mm": round(2.0 * r_cu, 3),
            "ponta_mm": _PONTA_ESTANHADA_MM, "isolamento_fim": [float(x) for x in p2],
            "geom": f"motor{k}_fase_{fase}_ponta", "fase": fase,
            "nota": f"fase {fase.upper()} do motor {k} ({ds.nome}, silicone {bitola}): ponta descarnada e estanhada — "
                    "soldar à ilha do ESC 4 em 1"}


def adicionar(ctx) -> None:
    """Motores T-Motor e hélices reais nos 4 rotores, com as variantes da troca ao vivo (ver o docstring do módulo)."""
    from ..componentes import CATALOGO_MOTORES_PAINEL
    hw = ctx.hw
    ds = _desenho(hw.motor)
    dh = _dims_helice(hw.helice)
    mat = _materiais(ctx, dh)
    mh = {nome: _malha(ctx, f"det_hel_{nome}", v)
          for nome, v in _cache_disco(f"helice:{dh!r}", lambda: _malhas_helice(dh)).items()}
    mf = {nome: _malha(ctx, f"det_hel_{nome}_{ds.chave}", v)
          for nome, v in _cache_disco(f"fixacao:{dh!r}:{ds.pino!r}", lambda: _malhas_fixacao(dh, ds.pino)).items()}
    # variantes: um modelo por chave mecânica; o do build fica com os nomes de sempre
    painel: dict[str, list[str]] = {}
    for pid in CATALOGO_MOTORES_PAINEL:
        painel.setdefault(_chave_id(pid), []).append(pid)
    r_max = max([ds.d] + [_DESENHOS[c].d for c in painel]) * 0.5
    rot = np.asarray(hw.pos_rotores, dtype=float)
    giro = np.asarray(hw.GIRO, dtype=float)
    malha = mujoco.mjtGeom.mjGEOM_MESH
    cil, cap = mujoco.mjtGeom.mjGEOM_CYLINDER, mujoco.mjtGeom.mjGEOM_CAPSULE
    fer = ctx.ferragens
    for i in range(4):
        k = i + 1
        g_mot, g_hel = ctx.geom_existente(f"motor{k}"), ctx.geom_existente(f"helice{k}")
        if g_mot is None or g_hel is None:
            continue
        corpo = g_mot.parent.name
        c = np.array(g_mot.pos, dtype=float)
        # a base ASSENTA na face de baixo do motor físico (= face de cima da placa do motor: a estrutura desenha a placa
        # do fundo do cilindro `suporte_motor_{k}` até aí); os parafusos sobem da face de baixo dessa placa
        g_sup = ctx.geom_existente(f"suporte_motor_{k}")
        z0 = c[2] - float(g_mot.size[1])
        z_sup0 = float(g_sup.pos[2]) - float(g_sup.size[1]) if g_sup is not None else z0 - 0.005
        e_placa = (z0 - z_sup0) / _MM
        ux, uy = rot[i] / max(float(np.linalg.norm(rot[i])), 1e-9)
        ang = math.atan2(uy, ux)
        articulado = corpo != "drone"
        # ---- fora o detalhe antigo; o cilindro com massa fica, invisível (as peças abaixo representam-no todo)
        for suf in _ANTIGOS_MOTOR:
            if ctx.geom_existente(f"motor{k}_{suf}") is not None:
                ctx.apagar(f"motor{k}_{suf}")
        nomes_pa = [f"helice{k}_cubo"] + [f"helice{k}_pa{b}_{s}" for b in range(1, 9) for s in _ANTIGOS_PA]
        for nome in nomes_pa:
            if ctx.geom_existente(nome) is not None:
                ctx.apagar(nome)
        ctx.esconder(f"motor{k}")
        site = _por_nome(ctx.spec.sites, f"r{k}")
        if site is not None:
            site.rgba = [0.0, 0.0, 0.0, 0.0]
        pm, qm = [c[0], c[1], z0], _qz(ang)

        def no_corpo(x, y, z, _c=c, _z0=z0, _ang=ang):
            """Ponto do referencial do motor (mm) → corpo (m)."""
            xy = _rz(_ang, x * _MM, y * _MM)
            return np.array([_c[0] + xy[0], _c[1] + xy[1], _z0 + z * _MM])

        # ponto COMUM dos cabos (fora de todos os motores do painel e da placa, por cima dela): cada motor (e cada
        # variante) leva os seus condutores da saída real até aqui; daqui às balas os cabos são os mesmos
        r_placa = float(g_sup.size[0]) / _MM if g_sup is not None else 0.0
        # no articulado os cabos descem a direito ao lado do mastro: o ponto comum fica fora da placa do motor que a
        # estrutura desenha (até r ≈ 29,3 mm medido; 33 mm deixa a folga do raio dos cabos)
        r_comum = max(r_max + 3.0, r_placa + 3.0, 33.0 if articulado else 0.0)
        p_comum = no_corpo(-r_comum, 0.0, 2.4)
        u = np.array([ux, uy, 0.0])
        nrm = np.array([-uy, ux, 0.0])
        lat = (-0.0035, 0.0, 0.0035)
        # ESC 4 em 1 (5″): os fios do motor vão soldados direto às ilhas, sem balas (`_cabos_soldados`); os 3 fios de
        # silicone (Ø1,9 mm) ficam lado a lado sem se tocarem (passo 2,1 mm) desde o ponto comum
        soldado = not articulado and hw.esc.dados.get("formato", "4em1") == "4em1"
        sinal_n = (1.0 if float(ux * uy) > 0.0 else -1.0) if soldado else 1.0
        inicio = [p_comum + nrm * (sinal_n * (0.6 if soldado else 0.35) * l) for l in lat]

        def saida(prefixo, dsx, corpo=corpo, p_comum=p_comum, lat=lat, nrm=nrm, inicio=inicio, no_corpo=no_corpo):
            """Os condutores do motor `dsx` desde a saída real até ao ponto comum: fio esmaltado numa manga
            termorretrátil (um feixe) ou os 3 fios de silicone lado a lado (cabem entre a base e o sino)."""
            tipo, _l, r_f, ponto, cor = dsx.cabo
            p0 = no_corpo(*ponto)
            if tipo == "esmaltado":
                r_m = r_f * (1.0 + 2.0 / math.sqrt(3.0)) + 0.15            # 3 condutores juntos + a manga
                ctx.geom(corpo, f"{prefixo}manga", _GRUPO_MOTOR, type=cap, size=[r_m * _MM, 0, 0],
                         fromto=p0.tolist() + p_comum.tolist(), material=mat["termo"])
                return [f"{prefixo}manga"]
            nomes_s = []
            for j, l in enumerate(lat):
                a0 = p0 + nrm * (l * 0.57)
                ctx.geom(corpo, f"{prefixo}saida_{'abc'[j]}", _GRUPO_MOTOR, type=cap, size=[r_f * _MM, 0, 0],
                         fromto=a0.tolist() + inicio[j].tolist(),
                         material=mat["fio_cobre"] if cor == "cobre" else mat["fio_preto"])
                nomes_s.append(f"{prefixo}saida_{'abc'[j]}")
            return nomes_s

        with ctx.peca("motor", k):
            # ---- motor do build (nomes de sempre)
            nomes = {"base": f"motor{k}_base_cnc", "nucleo": f"motor{k}_estator_nucleo", "cobre": f"motor{k}_estator_cobre",
                     "anel": f"motor{k}_sino_anel", "tampa": f"motor{k}_raio_1", "eixo": f"motor{k}_eixo"}
            geoms_build = _geoms_motor(ctx, corpo, k, ds, mat, pm, qm, nomes) + saida(f"motor{k}_", ds)
            # ---- ferragens do motor: 4 × M3 por baixo da placa, anel E do veio, parafuso do copo (MN5006)
            L = _comprimento_parafuso_base(ds, e_placa)
            for x, y in padrao_base(hw.motor)["furos_mm"]:
                p = no_corpo(x, y, 0.0)
                p[2] = z_sup0
                fer.parafuso(corpo, p, (0.0, 0.0, 1.0), "M3", comp=L, aperto=e_placa, cabeca="ISO 4762",
                             material_="aco_preto", rosca_metida=L - e_placa, ref=(ux, uy, 0.0),
                             nota=f"motor → placa: rosca útil {ds.t_base:g} mm na base, ponta a {L - e_placa:.1f} mm "
                                  f"(máx. {ds.prof_rosca_max:g})")
            if ds.anel_e:
                z_face, d_veio = ds.anel_e
                fer.anel_e(corpo, no_corpo(0.0, 0.0, z_face), (0.0, 0.0, -1.0), d_veio, ref=(ux, uy, 0.0))
            if ds.chave == "mn5006":
                fer.registar(tipo="parafuso", norma="ISO 10642", rosca="M3", comp_mm=8.0, material="fer_aco_preto",
                             corpo=corpo, ponto=no_corpo(0.0, 0.0, 0.55).tolist(), eixo=(0.0, 0.0, 1.0),
                             nota="cabeça de embeber no copo de retenção, roscado no veio oco (desenhado no veio)")
            # ---- cabos de fase: do ponto comum até às balas de 3,5 mm (o módulo `fios` continua daí) — com o ESC 4 em 1
            #      soldados: sem balas, até à raiz do braço, com a ponta estanhada e as âncoras para os `fios`
            _tipo, l_cabo, r_f, _s, cor = ds.cabo
            m_fio = mat["fio_cobre"] if cor == "cobre" else mat["fio_preto"]
            r_c = 0.00175
            l_saida = float(np.linalg.norm(p_comum - no_corpo(*ds.cabo[3])))
            l_fio = min(max(0.020, l_cabo * _MM - l_saida - 0.004), 0.045)
            folga_esc = None
            if not articulado and hw.frame.esc_no_braco is not None:
                folga_esc = (hw.braco - r_comum * _MM) - (hw.frame.esc_no_braco + 0.0315)
                if folga_esc < 0.015:
                    l_fio = max(0.001, folga_esc - 0.008)
                else:
                    l_fio = min(l_fio, max(0.010, folga_esc - 0.031))
            g_br = ctx.geom_existente(f"braco{k}")
            if soldado:
                _cabos_soldados(ctx, corpo, k, ds, mat, c, inicio, u, nrm, g_br, z0)
            else:
                for f_idx, l in enumerate(lat):
                    fase = "abc"[f_idx]
                    p1 = inicio[f_idx]
                    if not articulado:
                        z_fio = (z0 + 0.0035) if (folga_esc is not None and folga_esc < 0.015) else \
                            ((float(g_br.pos[2]) + float(g_br.size[2]) if g_br is not None else z0) + r_c)
                        p2 = p_comum - u * l_fio + nrm * l
                        p2[2] = z_fio
                        p3 = p2 - u * 0.009
                    else:                              # desce a direito por fora da placa e da abraçadeira do mastro
                        p2 = p_comum + nrm * l + np.array([0.0, 0.0, -l_fio])
                        p3 = p2 + np.array([0.0, 0.0, -0.009])
                    ctx.geom(corpo, f"motor{k}_fase_{fase}", _GRUPO_MOTOR, type=cap, size=[r_f * _MM, 0, 0],
                             fromto=p1.tolist() + p2.tolist(), material=m_fio)
                    ctx.geom(corpo, f"motor{k}_fase_{fase}_conector", _GRUPO_MOTOR, type=cil, size=[r_c, 0, 0],
                             fromto=p2.tolist() + p3.tolist(), material=mat["ouro"])
            # ---- variantes do painel (malhas partilhadas pelos 4 rotores); a do build é a ativa
            for chave, ids in painel.items():
                if chave == ds.chave:
                    continue
                dv = _DESENHOS[chave]
                nv = {p: f"motor{k}_v_{chave}_{p}" for p in _PARTES}
                nv["tampa"] = f"motor{k}_raio_v_{chave}"
                gv = _geoms_motor(ctx, corpo, k, dv, mat, pm, qm, nv) + saida(f"motor{k}_v_{chave}_", dv)
                for pid in ids:
                    ctx.registar_variante("motor", pid, gv, ativa=False, dz=(dv.h - ds.h) * _MM, modelo=dv.nome)
            for pid in painel.get(ds.chave, []):
                if pid != hw.motor.id:
                    ctx.registar_variante("motor", pid, geoms_build, ativa=False, dz=0.0, modelo=ds.nome)
            ctx.registar_variante("motor", hw.motor.id, geoms_build, ativa=True, dz=0.0, modelo=ds.nome)

        # ---- hélice: ASSENTA no topo do motor (cubo T-mount, sem adaptador); pás perpendiculares ao braço em repouso
        with ctx.peca("helice", k):
            sent = "cw" if giro[i] < 0 else "ccw"
            z_h0 = z0 + ds.h * _MM + (0.003 if "adaptador" in mf else 0.0)
            ph = [c[0], c[1], z_h0 + 0.5 * dh.h_cubo]
            # o disco translúcido (efeito de rotação do cockpit, grupo 2, massa 0, sem contacto — não é peça) passa a
            # COROA no plano REAL das pás (do cubo à ponta): o borrão coincide com as pás e não tapa o cubo, a tampa e
            # os parafusos (o site r{k}, onde atua o empuxo, não muda)
            mat_disco, r_disco = g_hel.material, float(g_hel.size[0])
            meia_e = float(g_hel.size[1])
            ctx.apagar(f"helice{k}")
            nome_m = f"det_hel_disco_{round(r_disco * 1e4)}"
            if _por_nome(ctx.spec.meshes, nome_m) is None:
                r0 = dh.r_cubo + 0.0005
                ctx.spec.add_mesh(name=nome_m, uservert=_arco(r0, r_disco, -meia_e, meia_e, n=96)[0].ravel().tolist(),
                                  userface=_arco(r0, r_disco, -meia_e, meia_e, n=96)[1].ravel().tolist()
                                  ).inertia = mujoco.mjtMeshInertia.mjMESH_INERTIA_SHELL
            ctx.geom(corpo, f"helice{k}", 2, type=malha, meshname=nome_m, material=mat_disco, pos=ph)
            psi0 = ang + 0.5 * math.pi
            ctx.geom(corpo, f"helice{k}_cubo", _GRUPO_HELICE, type=malha, meshname=mh["cubo"], material=mat["pa"],
                     pos=ph, quat=_qz(psi0))
            for b in range(dh.pas):
                q = _qz(psi0 + _TAU * b / dh.pas)
                for parte, material in (("raiz", mat["pa"]), ("ponta", mat["pa"]), ("faixa", mat["estampa"])):
                    ctx.geom(corpo, f"helice{k}_pa{b + 1}_{parte}", _GRUPO_HELICE, type=malha,
                             meshname=mh[f"{parte}_{sent}"], material=material, pos=ph, quat=q)
            pf = [c[0], c[1], z_h0]
            if dh.fixacao == "parafusos":
                ctx.geom(corpo, f"helice{k}_centro", _GRUPO_HELICE, type=malha, meshname=mf["centro"],
                         material=mat["latao"], pos=pf, quat=_qz(ang))
                z_t = z_h0 + dh.h_cubo
                ctx.geom(corpo, f"helice{k}_tampa", _GRUPO_HELICE, type=malha, meshname=mf["tampa"], material=mat["preto"],
                         pos=pf, quat=_qz(ang))
                ctx.geom(corpo, f"helice{k}_parafusos", _GRUPO_HELICE, type=malha, meshname=mf["parafusos"],
                         material=mat["preto"], pos=pf, quat=_qz(ang))
                for sy in (1.0, -1.0):
                    xy = _rz(ang, 0.0, sy * 6.0 * _MM)
                    fer.parafuso(corpo, [c[0] + xy[0], c[1] + xy[1], z_t + _ESP_TAMPA * _MM], (0.0, 0.0, -1.0), "M3",
                                 comp=_L_PARAF_HELICE, aperto=dh.h_cubo / _MM + _ESP_TAMPA, cabeca="ISO 4762",
                                 material_="aco_preto", desenhar=False, ref=(ux, uy, 0.0),
                                 nota="hélice → topo do motor (furo M3 roscado da tampa do rotor)")
            else:
                if "adaptador" in mf:
                    ctx.geom(corpo, f"helice{k}_adaptador", _GRUPO_HELICE, type=malha, meshname=mf["adaptador"],
                             material=mat["prata"], pos=pf, quat=_qz(ang))
                ctx.geom(corpo, f"helice{k}_porca", _GRUPO_HELICE, type=malha, meshname=mf["porca"],
                         material=mat["aco"], pos=pf, quat=_qz(ang))
                rosca = "M5" if dh.perfil == "tri_pa_fpv" else "M6"
                z_t = z_h0 + dh.h_cubo
                fer.anilha(corpo, [c[0], c[1], z_t], (0.0, 0.0, 1.0), rosca, material_="aco_inox", desenhar=False)
                from .ferragens import ISO7089
                fer.porca(corpo, [c[0], c[1], z_t + ISO7089[rosca][2] * _MM], (0.0, 0.0, 1.0), rosca, norma="ISO 10511",
                          material_="aco_zincado", desenhar=False)
