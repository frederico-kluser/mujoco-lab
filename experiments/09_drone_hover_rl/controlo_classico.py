"""experiments/09_drone_hover_rl/controlo_classico.py — CASCATA CLÁSSICA de voo (não-IA): protótipo de REFERÊNCIA.

Decisão do dono (2026-10-12): estabilização, rotação (yaw livre) e movimentação passam a ser um algoritmo
CLÁSSICO, reimplementado aqui em Python float64 limpo (escalares, sem numpy no laço) para ser PORTADO depois para o
firmware C++ (`firmware/`). Nada daqui é copiado: só as IDEIAS e as EQUAÇÕES publicadas (PX4 é BSD-3-Clause;
ArduPilot/Betaflight/Crazyflie/MultiWii são GPLv3 e NÃO foram lidos ao nível do código; os algoritmos não têm
copyright, o código sim).

        cmd (referencial do RUMO: frente/esquerda/cima, yaw_taxa)               [estimativas de bordo + giroscópio]
                  │                                                                      │
   conformador (acel./jerk-limitado, modelo de seguimento) ─────────────────────────────┤
                  │                                                                      │
   posição (P, raiz quadrada) ──▶ velocidade (PI(D) + FF de aceleração e de arrasto) ──▶ aceleração desejada
                                     − PERTURBAÇÃO observada (fase 2, VENTO: observador de estado estendido) │
              inclinação desejada + EMPUXO COLETIVO ÷ (cosφ·cosθ)  ◀─────────────────────┘
                  │
   atitude (P) com PRIORIDADE DE INCLINAÇÃO (Brescianini) + PESO DE YAW (MC_YAW_WEIGHT) + FF da taxa de inclinação
                  │
   taxas p, q, r ──▶ [FC, 500 Hz — fc.py: laço de taxa + mistura X + airmode]   (a mistura/saturação NÃO é daqui)

Interface do firmware (UMA chamada por decisão):

    coletivo, taxas_sp = CascataClassica(ganhos).passo(est, giro, cmd, dt)

  · `est`  — estimativas de bordo (atributos OU chaves `roll pitch psi h vz vx vy x y`, como o `estimador.py` e a
             struct `Saida` do núcleo C++): roll φ̂, pitch θ̂, rumo ψ̂ [rad, desde o armar], altura ĥ [m, do SENSOR de
             baixo], v̂_z [m/s], v̂_x v̂_y [m/s, no referencial do CORPO, do fluxo ótico], odometria x̂ ŷ [m];
  · `giro` — taxas MEDIDAS (p, q, r) [rad/s, corpo]: validadas (finitas) e registadas em `dados`; o laço de taxa do
             FC mede o giroscópio por conta própria, por isso o laço de atitude não precisa delas (D de atitude: futuro);
  · `cmd`  — `{vx, vy, vz, yaw_taxa, modo[, yaw, z_alvo]}`: v no REFERENCIAL DO RUMO (W = +vx frente, A = +vy
             esquerda, Q = +vz cima) [m/s]; `yaw_taxa` [rad/s, + = anti-horário visto de cima]; modo
             `velocidade` (v = 0 SEGURA a posição, como o modo Position do PX4; yaw_taxa = 0 MANTÉM o rumo) ou
             `yaw_alvo` (rumo absoluto `yaw` [rad, desde o armar]); `z_alvo` [m] = «subir/descer até esta altura»
             (descolar; os Q/E carregados a meio MOVEM o alvo, não o cancelam);
  · `dt`   — período da chamada [s];
  · devolve `coletivo` = EMPUXO COLETIVO normalizado pelo PESO (T/(m·g); 1,0 = pairagem; adimensional) e as
    taxas `(p, q, r)` [rad/s, corpo] para o laço de taxa. A conversão para a ação normalizada do env
    (`cmd_para_acao`) e para o acelerador do firmware (`acelerador_de_coletivo`, com a COMPENSAÇÃO DE TENSÃO da
    bateria) são funções À PARTE.

PEÇAS (todas com equações explícitas e unidades nos docstrings)
  `GanhosCascata` (dataclass) derivada da planta por `ganhos_de_hardware(env)` + `margens_cascata` (margens de fase
  dos laços em cascata com a resposta real da malha de taxa) · `CascataClassica` · `EstimadorClassico` (substituto
  direto do `EstimadorBordo`: calibração do giroscópio no chão, portão do acelerómetro, observador de altura de 3.ª
  ordem — as causas medidas do erro de hover; ver o README) · funções puras (`raiz_quadrada`, `direcao_empuxo`,
  `erro_atitude`, `velocidade_no_rumo`, `cmd_para_acao`, `acelerador_de_coletivo`).

FASE 2 — VENTO (2026-10-12; medido em `avaliar_vento.py`, provado em `teste_vento_classico.py`). Diagnóstico da fase 1 com
vento: o estimador NÃO é enganado (velocidade 2 cm/s, atitude 0,4° com e sem vento) e nada satura; quem perde é o INTEGRAL
da velocidade, a única coisa que rejeitava uma perturbação constante — lento (um degrau de vento de 3 m/s desvia 1,5 m e
leva 13 s a voltar) e limitado a 2 m/s² (5 m/s de vento pedem 2,1: o drone fica a 3,5 m). O que mudou:
  · um OBSERVADOR DE ESTADO ESTENDIDO no laço de velocidade horizontal (`CascataClassica.passo`, etapa 1b): estima a
    perturbação da velocidade medida contra a de um modelo (empuxo lido da atitude estimada − arrasto) e anula-a;
  · a velocidade do fluxo do `EstimadorClassico` deixou de levar a rotação do corpo (braço do sensor ao CM e alinhamento
    do giroscópio com a amostra do fluxo) — sem isso cada manobra de inclinação parecia vento ao observador.
A vertical ficou como na fase 1 (o observador vertical foi medido e não entrou).

FONTES (equações reimplementadas; nenhuma linha copiada)
  [PX4]   Controller Diagrams — docs.px4.io/main/en/flight_stack/controller_diagrams (cascata posição P →
          velocidade PID → aceleração → inclinação+empuxo → atitude P → taxa PID; o modo velocidade contorna a
          posição e trava-a ao parar); parâmetros MC_YAW_WEIGHT, MPC_TILTMAX_AIR, MPC_ACC_HOR, MPC_JERK_*,
          MC_YAWRATE_MAX, MPC_TKO_SPEED (Parameter Reference); anti-windup por retro-cálculo (tracking).
  [ARDU]  ArduPilot dev docs — «Copter Attitude Control» / «Position Control»: controlador raiz quadrada
          (aproximação sem sobressinal sob limite de aceleração), compensação ANGLE_BOOST do empuxo, limite de
          aceleração do yaw ATC_ACC_Y_MAX (ponto de partida 200/100/90 °/s² para hélices de 10/20/30″).
  [BRE18] Brescianini & D'Andrea, «Tilt-Prioritized Quadrocopter Attitude Control», IEEE T-CST 28(2),
          376–387, 2018 (erro de atitude q_e = q_red ⊗ q_yaw; o yaw é o primeiro a ser sacrificado).
  [FAE18] Faessler, Franchi & Scaramuzza, «Differential Flatness of Quadrotor Dynamics Subject to Rotor Drag for
          Accurate Tracking of High-Speed Trajectories», RA-L 3(2), 2018 (aceleração desejada → orientação+empuxo;
          arrasto de rotor linear em v).
  [AM08]  Åström & Murray, «Feedback Systems», 2008, §10.4 (windup do integral; retro-cálculo); Åström &
          Hägglund, «PID Controllers», 1995 (regras de separação de laços em cascata; PID de 2 graus de liberdade).
  [MAH08] Mahony, Hamel & Pflimlin, «Nonlinear Complementary Filters on the Special Orthogonal Group», IEEE TAC
          53(5), 2008 (filtro complementar P/PI de atitude; medido aqui: a parte I não ajuda em voo — README).
  [BF]    Betaflight docs `vbat_sag_compensation` (ideia: o acelerador de pairagem acompanha a tensão).
  [HAN09] Han, «From PID to Active Disturbance Rejection Control», IEEE Trans. Industrial Electronics 56(3), 2009 (o
          observador de estado estendido: a perturbação TOTAL é mais um estado, estimado e anulado — fase 2, vento).
  [GAO03] Gao, «Scaling and Bandwidth-Parameterization Based Controller Tuning», American Control Conference, 2003 (os
          ganhos do observador por UMA banda ω: polos duplos em −ω ⇒ 2ω e ω²).
  [SME18] Smeur, de Croon & Chu, «Cascaded Incremental Nonlinear Dynamic Inversion for MAV Disturbance Rejection»,
          Control Engineering Practice 73, 2018 (a alternativa MEDIDA e não adotada: realimentar a aceleração do
          acelerómetro — aqui o ruído de vibração piora a pairagem em ar parado; ver `avaliar_vento.py`).

Unidades SI; +Z para cima; ângulos ZYX (yaw ψ, pitch θ, roll φ): θ > 0 inclina o empuxo para +x (acelera para a
frente), φ < 0 inclina-o para +y (esquerda); ψ > 0 roda no sentido anti-horário visto de cima.
"""
from __future__ import annotations

import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace

G = 9.81                                  # m/s² — gravidade
TAXA_MAX_ENV = (2.0, 2.0, 1.0)            # rad/s — setpoints máx. de p, q, r da ação do env (espelha env_real.TAXA_MAX)
CAMPOS_EST = ("roll", "pitch", "psi", "h", "vz", "vx", "vy", "x", "y")
MODOS = ("velocidade", "yaw_alvo")


# ------------------------------------------------------------------------------------------ pequenas funções puras
def envolve_pi(a: float) -> float:
    """Ângulo → (−π, π]."""
    a = math.fmod(a + math.pi, 2.0 * math.pi)
    if a <= 0.0:
        a += 2.0 * math.pi
    return a - math.pi


def limita(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else min(x, hi)


def raiz_quadrada(erro: float, k: float, lim: float) -> float:
    """CONTROLADOR RAIZ QUADRADA (ArduPilot `sqrt_controller`; [ARDU]): erro → «velocidade» desejada.

    Perto de zero é linear (v = k·e); longe, é a velocidade de que se TRAVA a `lim` constante até parar no erro
    zero (v² = 2·lim·d), sem sobressinal. Junção contínua e com derivada contínua em |e| = lim/k²:

        |e| ≤ lim/k² :  v = k·e         |e| > lim/k² :  v = sinal(e)·√(2·lim·(|e| − lim/(2k²)))

    (dedução: igualar valor e declive de k·e e √(2·lim·(e − e₀)) dá e₁ = lim/k² e e₀ = lim/(2k²)).
    """
    if lim <= 0.0 or k <= 0.0:
        return 0.0
    e = abs(erro)
    if e <= lim / (k * k):
        return k * erro
    v = math.sqrt(2.0 * lim * (e - 0.5 * lim / (k * k)))
    return v if erro > 0.0 else -v


def velocidade_no_rumo(phi: float, theta: float, vbx: float, vby: float, vz: float) -> tuple[float, float]:
    """Velocidade horizontal no referencial do RUMO (alinhado com o yaw, vertical = gravidade).

    O fluxo ótico dá (v_bx, v_by) nos eixos do CORPO e o observador dá v_z no MUNDO. v_H = R_y(θ)·R_x(φ)·v_b:

        v_H,z = −sθ·v_bx + cθ·sφ·v_by + cθ·cφ·v_bz   (= v_z medido  ⇒  v_bz = (v_z + sθ·v_bx − cθ·sφ·v_by)/(cθ·cφ))
        v_H,x =  cθ·v_bx + sθ·(sφ·v_by + cφ·v_bz)     v_H,y = cφ·v_by − sφ·v_bz

    (≈ v_bx + θ·v_z e v_by − φ·v_z para ângulos pequenos).
    """
    sf, cf = math.sin(phi), math.cos(phi)
    st, ct = math.sin(theta), math.cos(theta)
    den = ct * cf
    if den < 0.2:                                   # quase de cabeça para baixo: sem correção (nunca acontece em voo)
        return vbx, vby
    vbz = (vz + st * vbx - ct * sf * vby) / den
    return ct * vbx + st * (sf * vby + cf * vbz), cf * vby - sf * vbz


def direcao_empuxo(ax: float, ay: float, az: float, g: float, tilt_max: float,
                   c_min: float, c_max: float) -> tuple[float, float, float, float, bool]:
    """Aceleração desejada [m/s²] (mundo) → direção do empuxo n̂ e EMPUXO COLETIVO normalizado (÷ cosφ·cosθ).

    Força específica desejada F = a + g·ẑ (a = aceleração; ENU). O empuxo tem de a produzir: n̂ = F/‖F‖ (eixo z do
    corpo desejado) e T/(m·g) = ‖F‖/g = (g + a_z)/(g·n_z) com n_z = cosφ_d·cosθ_d (o cosseno da inclinação
    desejada) — a «compensação 1/(cosφ·cosθ)»: a componente VERTICAL do empuxo fica m·(g + a_z) por maior que
    seja a inclinação (PX4: «collective_thrust = thrust_z / cos_ned_body»; ArduPilot: ANGLE_BOOST).

    LIMITE DE INCLINAÇÃO: se a inclinação pedida passa de `tilt_max`, a aceleração horizontal é escalada para
    tan(tilt_max)·(g + a_z) (a vertical tem PRIORIDADE). O coletivo é cortado a [c_min, c_max].
    Devolve (n_x, n_y, n_z, coletivo, saturou_inclinacao).
    """
    fz = max(g + az, 0.2 * g)                       # nunca apontar o empuxo para baixo (queda livre pedida)
    axy = math.hypot(ax, ay)
    lim = fz * math.tan(tilt_max)
    saturou = False
    if axy > lim:
        ax, ay = ax * lim / axy, ay * lim / axy
        saturou = True
    mod = math.sqrt(ax * ax + ay * ay + fz * fz)
    return ax / mod, ay / mod, fz / mod, limita(mod / g, c_min, c_max), saturou


def erro_atitude(phi: float, theta: float, psi: float, n: tuple[float, float, float],
                 psi_des: float) -> tuple[float, float, float]:
    """Erro de atitude com PRIORIDADE DE INCLINAÇÃO ([BRE18]): devolve (e_x, e_y, γ).

    Atitude desejada: eixo z do corpo = n̂ (empuxo) e eixo x tão perto de (cosψ_d, sinψ_d, 0) quanto n̂ permite.
    O erro quaternião q_e = q⁻¹ ⊗ q_d decompõe-se como q_e = q_red ⊗ q_yaw — primeiro a rotação MÍNIMA que
    alinha o eixo z (a INCLINAÇÃO, sem componente z), depois a rotação γ em torno do z desejado (o YAW):

        (e_x, e_y) = (−n_by, n_bx)/cos(α/2)  = 2·(parte vetorial de q_red)      α = ângulo entre z_b e n̂
        γ          = atan2(ŷ_red·x_d, x̂_red·x_d)  (eixos de q_red·(x̂, ŷ) e x_d, no referencial do corpo)

    com n_b = Rᵀ·n̂ (n̂ nos eixos do corpo) e, em eixos do corpo, x̂_red = (cα + n_by²/(1+cα), −n_bx·n_by/(1+cα),
    −n_bx), ŷ_red = (−n_bx·n_by/(1+cα), cα + n_bx²/(1+cα), −n_by). O erro de inclinação NÃO depende do yaw
    desejado: um erro de yaw, por enorme que seja, não perturba as taxas p, q (é a «prioridade»).
    """
    sf, cf = math.sin(phi), math.cos(phi)
    st, ct = math.sin(theta), math.cos(theta)
    sp, cp = math.sin(psi), math.cos(psi)
    # colunas de R (corpo → mundo): ZYX
    xb = (cp * ct, sp * ct, -st)
    yb = (cp * st * sf - sp * cf, sp * st * sf + cp * cf, ct * sf)
    zb = (cp * st * cf + sp * sf, sp * st * cf - cp * sf, ct * cf)
    nx, ny, nz = n
    nbx = xb[0] * nx + xb[1] * ny + xb[2] * nz
    nby = yb[0] * nx + yb[1] * ny + yb[2] * nz
    nbz = zb[0] * nx + zb[1] * ny + zb[2] * nz
    nbz = limita(nbz, -1.0, 1.0)
    um_mais = max(1.0 + nbz, 1e-3)
    e_x = -nby / math.sqrt(0.5 * um_mais)                # −n_by / cos(α/2),  cos(α/2) = √((1 + n_bz)/2)
    e_y = nbx / math.sqrt(0.5 * um_mais)
    # eixo x desejado (mundo): y_d = normalize(n̂ × ĥ_d), x_d = y_d × n̂
    hx, hy = math.cos(psi_des), math.sin(psi_des)
    yx, yy, yz = -nz * hy, nz * hx, nx * hy - ny * hx     # n̂ × ĥ_d
    mod = math.sqrt(yx * yx + yy * yy + yz * yz)
    if mod < 1e-6:                                         # n̂ ∥ ĥ_d (inclinação de 90°): sem yaw definido
        return e_x, e_y, 0.0
    yx, yy, yz = yx / mod, yy / mod, yz / mod
    dx = yy * nz - yz * ny
    dy = yz * nx - yx * nz
    dz = yx * ny - yy * nx
    # x_d nos eixos do corpo
    xdb = (xb[0] * dx + xb[1] * dy + xb[2] * dz, yb[0] * dx + yb[1] * dy + yb[2] * dz,
           zb[0] * dx + zb[1] * dy + zb[2] * dz)
    xr = (nbz + nby * nby / um_mais, -nbx * nby / um_mais, -nbx)
    yr = (-nbx * nby / um_mais, nbz + nbx * nbx / um_mais, -nby)
    gama = math.atan2(yr[0] * xdb[0] + yr[1] * xdb[1] + yr[2] * xdb[2],
                      xr[0] * xdb[0] + xr[1] * xdb[1] + xr[2] * xdb[2])
    return e_x, e_y, gama


def acelerador_de_coletivo(coletivo: float, u_pairagem: float) -> float:
    """Empuxo coletivo T/(m·g) → acelerador [0,1] do firmware: u = u_pair(V)·√c (T ∝ ω² ∝ u²).

    `u_pairagem` é o acelerador de pairagem À TENSÃO MEDIDA da bateria (COMPENSAÇÃO DE TENSÃO, [BF]): o «1,0»
    do coletivo continua a ser «pairar» de 100 % a 10 % de carga. É a MESMA conta do `DroneRealEnv._comando`.
    """
    return limita(u_pairagem * math.sqrt(max(coletivo, 0.0)), 0.0, 1.0)


def cmd_para_acao(coletivo: float, taxas_sp, taxa_max=TAXA_MAX_ENV) -> list[float]:
    """Saída da cascata → ação normalizada [-1, 1]⁴ do `DroneRealEnv` (modo `ctbr`).

    a₀ = c − 1 (o env faz u = u_pair·√(1 + a₀), ou seja T/T_pair = 1 + a₀) e a₁..₃ = taxas/TAXA_MAX.
    Tudo cortado a [-1, 1] (como o env faz).
    """
    return [limita(coletivo - 1.0, -1.0, 1.0)] + [limita(float(r) / float(m), -1.0, 1.0)
                                                   for r, m in zip(taxas_sp, taxa_max, strict=True)]


# ------------------------------------------------------------------------------------------ planta e ganhos
@dataclass(frozen=True)
class PlantaLinear:
    """O que a cascata precisa de saber da planta (números extraídos do `fc.py`/hardware por `ganhos_de_hardware`)."""

    omega_taxa: float          # rad/s — frequência de cruzamento da malha de taxa roll/pitch (fc.py), ωc
    tau_motor: float           # s — constante de tempo do rotor em pairagem
    alfa_yaw: float            # rad/s² por unidade de acelerador diferencial (yaw)
    inercia_zz: float          # kg·m²
    c_yaw: float               # N·m·s/rad — amortecimento aerodinâmico de yaw (arrasto de rotor)
    u_pairagem: float          # acelerador de pairagem nominal
    idle: float                # acelerador mínimo com o FC armado
    dt_decisao: float = 0.02   # s — período da cascata
    u_yaw_por_taxa: float | None = None   # (acelerador diferencial)/(rad/s) em equilíbrio — IDENTIFICADO no simulador;
    #                            sem ele usa-se a fórmula c_yaw/(J_zz·α_z) (arrasto de rotor)
    # --- o sensor de fluxo ótico (de onde vem a velocidade medida que o observador de perturbação usa)
    atraso_vel: float = 0.0    # s — atraso da velocidade do fluxo: transporte + PT1 do estimador + meia amostra
    braco_fluxo: float = 0.0   # m — altura do CM acima do sensor de fluxo
    atraso_fluxo: int = 0      # passos de física entre uma leitura do giroscópio e a amostra de fluxo do mesmo instante


@dataclass(frozen=True)
class GanhosCascata:
    """Todos os ganhos e limites da cascata (unidades no nome/comentário). Derivados por `de_planta`.

    Regras de DERIVAÇÃO (fórmulas fechadas; `razao_lacos` = separação entre laços consecutivos, ponto de
    partida ≈ 4 da pesquisa 2026-10-12, Q2.1; `razao_atitude` = a do laço de atitude sobre a malha de taxa):
        K_att = ω_c/razão_atitude    K_vel = K_att/razão_lacos    K_pos = K_vel/razão_posicao  (ω_c = cruzamento da taxa)
        K_vz  = 1/(τ_m·razão_lacos)  K_pz  = K_vz/razão_lacos
        K_i   = K²/razão_integral    (zero do integral uma «razão» abaixo do cruzamento do laço; vertical: razão_lacos)
    As razões de ATITUDE e de POSIÇÃO são 2,5 e não 4 porque a margem de fase de cada laço, calculada com a resposta REAL
    da malha de taxa (fc.py + atrasos) em cascata (`margens_cascata`), é ≥ 60° até aí: atitude 62° a 2,5 (48° a 2,0),
    posição 65° a 2,5 (57° a 2,0); a de velocidade fica em 4 (PM 62° com K_i = K_v²/4) e o integral horizontal usa
    `razao_integral` = 2 (PM_vel ≈ 50°: o preço de acomodar o desvio de arrasto/viés de atitude depressa; medido nas
    sementes de calibração: hover −29 % de ‖xy‖, seguimento com DR −15 %, sem mais sobressinal). Ver o README.
        tilt_max = min(30°, acos(reserva_vertical/c_max))      a_xy,max = g·tan(tilt_max)
        yaw: u_yaw = f_yaw·folga (folga = min(1 − u_pair, u_pair − idle)); a_yaw = α_z·u_yaw;
             r_yaw = u_yaw/(u/r) com u/r = c_yaw/(J_zz·α_z) (arrasto de rotor) ou o valor IDENTIFICADO no simulador
        comandos: a_cmd = g·tan(17°), jerk = a_cmd·ω_att/2 (ω_att = √(K_att·ω_c)), K_conf = K_att, τ_modelo = 1/ω_c;
                  vertical: a_z = ½·(c_max − 1)·g, jerk_z = a_z/(2·τ_m), K_conf_z = 1/(2·τ_m)
        observador de perturbação (fase 2, VENTO; só na horizontal): ω_obs = ω_c/razão_pert (razão 1: a banda do laço
                  mais rápido que o corpo segue; ganhos 2·ω_obs e ω_obs² = polos duplos [GAO03]); limite = a autoridade
                  da inclinação, g·tan(tilt_max); τ_vel = atraso da velocidade do fluxo (transporte + PT1 do estimador +
                  meia amostra).
    As escolhas da fase 2 foram MEDIDAS nas sementes de calibração (`avaliar_vento.py --calibrar`; números no docstring
    desse ficheiro): a banda do observador, o que cada peça do modelo vale, e o que NÃO entrou — um observador pelo
    acelerómetro (o ruído de vibração piora a pairagem em ar parado) e um observador VERTICAL (segura a altitude mas
    troca-a por deriva horizontal quando o empuxo satura, e piora o degrau de subida).
    """

    razao_lacos: float = 4.0
    razao_atitude: float = 2.5
    razao_posicao: float = 2.5
    razao_integral: float = 2.0
    omega_taxa: float = 8.43               # rad/s
    # atitude [BRE18] — os valores por omissão são os derivados da build `endurance_15pol_p50b`
    k_att: float = 3.37                    # s⁻¹  P de inclinação (roll/pitch)
    k_yaw: float = 3.37                    # s⁻¹  P de yaw (a «cheio»; o efetivo é peso_yaw·k_yaw)
    peso_yaw: float = 0.7                  # (0, 1]  como MC_YAW_WEIGHT (PX4: 0,4; a varredura 0,4→1 só mexe no assentamento)
    taxa_rp_max: float = 1.5               # rad/s  teto das taxas p, q
    taxa_yaw_max: float = 0.51             # rad/s  teto da taxa de yaw (equilíbrio com o arrasto, u/r identificado)
    acel_yaw_max: float = 0.53             # rad/s² teto da aceleração de yaw (binário máx./J_zz × quota)
    folga_yaw: float = 0.6                 # quota do acelerador diferencial dada ao yaw (resto: inclinação)
    u_yaw_por_taxa: float = 0.44           # (acelerador diferencial)/(rad/s) de yaw em equilíbrio (identificado)
    alfa_yaw: float = 2.38                 # rad/s² por unidade de acelerador diferencial (yaw)
    u_pairagem: float = 0.63               # acelerador de pairagem nominal
    avanco_yaw_max: float = 0.35           # rad  avanço máximo da referência de rumo sobre o rumo medido
    # velocidade horizontal (saída = aceleração) e posição
    k_vel: float = 0.84                    # s⁻¹   [(m/s²)/(m/s)]
    ki_vel: float = 0.356                  # s⁻²
    kd_vel: float = 0.0                    # s     (D sobre a MEDIDA filtrada; 0 = desligado)
    tau_d_vel: float = 0.3                 # s     filtro do termo D
    k_pos: float = 0.337                   # s⁻¹   [(m/s)/m]
    avanco_pos_max: float = 1.5            # m     avanço máximo da referência de posição sobre a medida
    vel_corr_pos_max: float = 0.8          # m/s   teto da correção de velocidade pelo erro de posição
    acc_pos: float = 1.0                   # m/s²  aceleração da aproximação raiz-quadrada (posição → velocidade)
    # vertical
    k_pz: float = 1.12                     # s⁻¹
    k_vz: float = 8.95                     # s⁻¹   [(m/s²)/(m/s)]
    ki_vz: float = 8.0                     # s⁻²   (também adapta o empuxo de pairagem: massa/kf)
    vel_corr_z_max: float = 0.7            # m/s
    # limites
    tilt_max: float = math.radians(30.0)   # rad
    coletivo_min: float = 0.3
    coletivo_max: float = 2.0
    vel_xy_max: float = 1.0                # m/s   (VOO_VEL)
    vel_z_max: float = 0.7                 # m/s   (VOO_SUBIDA)
    vel_goto_z: float = 1.5                # m/s   velocidade máx. de «ir até z_alvo» (descolar; PX4 MPC_TKO_SPEED = 1,5)
    altura_min: float = 0.0                # m (do SENSOR) — piso de altitude em voo (0 = sem piso)
    altura_max: float = 1e9                # m (do SENSOR) — teto de altitude; `ganhos_de_hardware` põe 90 % do alcance do ToF
    # conformador dos comandos (acelera/jerk-limitado), no referencial do rumo
    acc_cmd_xy: float = 3.0                # m/s²   g·tan(17°)
    jerk_cmd_xy: float = 8.0               # m/s³   acc·ω_att/2
    k_conf: float = 3.37                   # s⁻¹   ganho do conformador de velocidade (horizontal) = K_att
    k_conf_z: float = 8.95                 # s⁻¹   idem, vertical = 1/(2·τ_m)
    tau_modelo_z: float = 0.066            # s     modelo de seguimento vertical (τ_motor + dt/2; 0 = sem, a lei da fase 1)
    acc_cmd_z: float = 3.92                # m/s²   ½·(c_max − 1)·g
    jerk_cmd_z: float = 35.1               # m/s³   acc/(2·τ_m)
    ref_posicao: str = "trava"             # horizontal — "trava": p_sp = p̂ em movimento, trava ao parar (como o PX4); "integrada": p_sp integra a velocidade
    tau_modelo: float = 0.119              # s     atraso do MODELO de seguimento = 1/ω_c (a realimentação compara com v_sp atrasada)
    k_ff_acc: float = 1.0                  # escala do feed-forward da aceleração conformada (0 = só realimentação)
    k_arrasto: float = 0.30                # s⁻¹   feed-forward do arrasto linear (a = d·v_modelo); d do rotor da planta
    aw_ganho: float = 2.0                  # anti-windup por retro-cálculo: k_aw = aw_ganho/K_vel (0 = sem anti-windup)
    # rejeição de perturbação (VENTO, fase 2): OBSERVADOR DE ESTADO ESTENDIDO no laço de velocidade horizontal
    # [HAN09][GAO03] — a perturbação (vento, arrasto mal modelado, viés de atitude) é estimada da velocidade MEDIDA contra a
    # do modelo e anulada na aceleração pedida, sem esperar pelo integral (ver `passo`, etapa 1b)
    w_pert: float = 8.43                   # rad/s  banda do observador (polos duplos em −w) = ω_c/razão_pert; 0 = fase 1
    lim_pert: float = 5.66                 # m/s²   |perturbação| ≤ g·tan(tilt_max): o que a inclinação consegue anular
    tau_vel: float = 0.034                 # s      atraso da velocidade medida pelo fluxo (o modelo do observador leva o mesmo)
    # velocidade do fluxo no `EstimadorClassico` (geometria e sensores do build — ver `EstimadorClassico.configurar_fluxo`)
    braco_fluxo: float = 0.041             # m      altura do CM acima do sensor de fluxo (v_cm = v_sensor − ω × r)
    atraso_fluxo: int = 4                  # passos a amostra do fluxo chega N passos de física depois do giroscópio que lhe corresponde
    ff_atitude: bool = True                # feed-forward da taxa de inclinação (ω = n̂ × dn̂/dt) — segue rampas sem atraso
    tau_ff: float = 0.08                   # s     filtro da derivada de n̂ (rejeita o ruído do fluxo)
    comp_yaw_empuxo: bool = True           # pré-compensa o empuxo extra do diferencial de yaw (ver `passo`)
    comp_yaw_acel: float = 0.0             # peso do termo de ACELERAÇÃO de yaw na compensação (0 = só o equilíbrio; 1 piorou)
    g: float = G
    # --- diagnóstico: de onde vieram (não usados pelo controlo)
    notas: dict = field(default_factory=dict, compare=False, hash=False)

    @classmethod
    def de_planta(cls, p: PlantaLinear, razao: float = 4.0, *, razao_atitude: float = 2.5,
                  razao_posicao: float = 2.5, razao_integral: float = 2.0, tilt_max_graus: float = 30.0,
                  tilt_cmd_graus: float = 17.0, f_yaw: float = 0.6, peso_yaw: float = 0.7, c_max: float = 1.8,
                  reserva_vertical: float = 1.3, razao_pert: float = 1.0, razao_vz: float = 2.0,
                  razao_integral_z: float = 10.0, coletivo_teto: float = 2.0, **extra) -> GanhosCascata:
        """Ganhos e limites por FÓRMULAS FECHADAS a partir da planta (ver o docstring da classe).

        VERTICAL (2026-10-13 — a altitude com rajadas era o único sítio onde a cascata perdia para a política RL): o
        laço de velocidade vertical passa a fechar a `razao_vz` = 2 do motor (era 4 — `k_vz` = 1/(τ_motor·razao_vz),
        o dobro da rigidez), com o integral a `k_vz²/razao_integral_z` (10: mais lento em relação ao proporcional do
        que na fase 1, para o degrau de subida não ganhar sobressinal), um modelo de seguimento vertical de constante
        `τ_motor + dt/2` (a referência chega ao laço ao ritmo a que o rotor consegue responder) e o teto do coletivo
        em `coletivo_teto` = 2,0 (T/W 2,6: há empuxo). `k_pz` fica onde estava (1/(τ_motor·razao²)). Margens do laço
        de velocidade vertical com isto (`margens_cascata`, build ativo): fase 57,3° → 50,7°, ganho 21,7 → 15,8 dB.
        Medido (`avaliar_vento.py`): |Δz| com vento aleatório de 3/4/5 m/s 11,5/23,9/40,6 → 6,5/13,5/24,9 cm, sem
        custo horizontal nem de esforço dos motores. A lei de antes: `razao_vz=4, razao_integral_z=4,
        tau_modelo_z=0, coletivo_teto=1.8`.
        """
        if min(razao, razao_atitude, razao_posicao, razao_integral) <= 1.0:
            raise ValueError("as razões entre laços têm de ser > 1 "
                             f"(recebido {razao!r}, {razao_atitude!r}, {razao_posicao!r}, {razao_integral!r})")
        if razao_pert <= 0.0:
            raise ValueError(f"razao_pert tem de ser > 0 (recebido {razao_pert!r})")
        if razao_vz <= 1.0 or razao_integral_z <= 1.0:
            raise ValueError(f"as razões do laço vertical têm de ser > 1 (recebido {razao_vz!r}, {razao_integral_z!r})")
        k_att = p.omega_taxa / razao_atitude
        k_vel = k_att / razao
        k_pos = k_vel / razao_posicao
        k_vz = 1.0 / (p.tau_motor * razao_vz)
        k_pz = 1.0 / (p.tau_motor * razao * razao)                  # a malha de ALTURA fica onde estava
        tilt_max = min(math.radians(tilt_max_graus), math.acos(min(reserva_vertical / c_max, 1.0)))
        folga = min(1.0 - p.u_pairagem, p.u_pairagem - p.idle)
        u_yaw_max = f_yaw * folga                                   # acelerador diferencial reservado ao yaw
        u_por_taxa = (p.u_yaw_por_taxa if p.u_yaw_por_taxa is not None
                      else p.c_yaw / (p.inercia_zz * p.alfa_yaw))   # equilíbrio: J·α·u = c·r
        acel_yaw = p.alfa_yaw * u_yaw_max                           # rad/s² — binário de yaw máx. usável / J_zz
        taxa_yaw = u_yaw_max / u_por_taxa                           # rad/s — equilíbrio binário = arrasto
        acc_cmd = G * math.tan(math.radians(tilt_cmd_graus))        # aceleração horizontal máx. dos COMANDOS
        omega_att = math.sqrt(k_att * p.omega_taxa)                 # ωn da malha de atitude (2.ª ordem)
        acc_cmd_z = 0.5 * (c_max - 1.0) * G                         # metade da reserva de empuxo vertical
        notas = {"folga_acelerador": folga, "omega_atitude": omega_att, "tilt_cmd_graus": tilt_cmd_graus}
        dados = {
            "razao_lacos": razao, "razao_atitude": razao_atitude, "razao_posicao": razao_posicao,
            "razao_integral": razao_integral, "omega_taxa": p.omega_taxa,
            "k_att": k_att, "k_yaw": k_att, "peso_yaw": peso_yaw, "folga_yaw": f_yaw,
            "k_vel": k_vel, "ki_vel": k_vel * k_vel / razao_integral, "k_pos": k_pos,
            "k_vz": k_vz, "k_pz": k_pz, "ki_vz": k_vz * k_vz / razao_integral_z,
            "tau_modelo_z": p.tau_motor + 0.5 * p.dt_decisao,
            "tilt_max": tilt_max, "coletivo_max": coletivo_teto,
            "acel_yaw_max": acel_yaw, "taxa_yaw_max": taxa_yaw, "u_yaw_por_taxa": u_por_taxa,
            "alfa_yaw": p.alfa_yaw, "u_pairagem": p.u_pairagem,
            "acc_cmd_xy": acc_cmd, "jerk_cmd_xy": acc_cmd * omega_att / 2.0, "k_conf": k_att,
            "tau_modelo": 1.0 / p.omega_taxa,
            "acc_cmd_z": acc_cmd_z, "jerk_cmd_z": acc_cmd_z / (2.0 * p.tau_motor),
            "k_conf_z": 1.0 / (2.0 * p.tau_motor),
            "w_pert": p.omega_taxa / razao_pert, "lim_pert": G * math.tan(tilt_max), "tau_vel": p.atraso_vel,
            "braco_fluxo": p.braco_fluxo, "atraso_fluxo": int(p.atraso_fluxo),
            "notas": notas,
        }
        dados.update(extra)
        return cls(**dados)

    def com(self, **mudancas) -> GanhosCascata:
        """Cópia com campos alterados (sem mutar: o dataclass é imutável)."""
        validos = {f.name for f in fields(self)}
        desconhecidos = set(mudancas) - validos
        if desconhecidos:
            raise ValueError(f"campos desconhecidos em GanhosCascata: {sorted(desconhecidos)}")
        return replace(self, **mudancas)


def resposta_malha_taxa(kp: float, ki: float, kd: float, alfa: float, tau_motor: float, atraso: float,
                        fc_giro_hz: float, fc_d_hz: float, w):
    """Resposta em frequência da malha de taxa do `fc.py` (um eixo) em ω = `w` [rad/s]: devolve (T, L).

    Planta ω̇ = α·u (motor de 1.ª ordem τ_m, atraso puro `atraso`); controlador do fc.py — PID com D sobre a
    MEDIDA e PT1 no giroscópio e no termo D:  u = (kp + ki/s)·(ω_sp − F_g·ω) − kd·s·F_d·F_g·ω.
        L = G·(C₁ + kd·s·F_d)·F_g      T = ω/ω_sp = G·C₁/(1 + L)      G = α·e^{−s·atraso}/(s·(τ_m·s + 1))
    `w` pode ser escalar ou ndarray.
    """
    import numpy as np
    s = 1j * np.asarray(w, dtype=float)
    f_g = 1.0 / (1.0 + s / (2.0 * math.pi * fc_giro_hz))
    f_d = 1.0 / (1.0 + s / (2.0 * math.pi * fc_d_hz))
    g = alfa * np.exp(-s * atraso) / (s * (tau_motor * s + 1.0))
    c1 = kp + ki / s
    ll = g * (c1 + kd * s * f_d) * f_g
    return g * c1 / (1.0 + ll), ll


def cruzamento_ganho(w, ll) -> float:
    """Primeira frequência [rad/s] em que |L(jω)| cai abaixo de 1 (interpolação log-log)."""
    import numpy as np
    mag = np.abs(ll)
    idx = np.nonzero(mag < 1.0)[0]
    if idx.size == 0 or idx[0] == 0:
        return float(w[-1])
    i = int(idx[0])
    w0, w1 = float(w[i - 1]), float(w[i])
    m0, m1 = math.log(float(mag[i - 1])), math.log(float(mag[i]))
    return math.exp(math.log(w0) + (0.0 - m0) / (m1 - m0) * (math.log(w1) - math.log(w0)))


def _malha_taxa_do_env(env):
    """(w, T, L, ω_c) da malha de taxa roll do `fc.py` do env: atraso = comando + meia retenção + giroscópio."""
    import fc as _fc_mod
    import numpy as np
    fc, hw = env.fc, env.hw
    atraso = (float(env.atraso_comando) + 0.5 * float(env.dt_decisao)
              + float(hw.sensores["imu"]["giro"].get("atraso_s", 0.0)))
    w = np.logspace(-2.0, 2.5, 6000)
    t, ll = resposta_malha_taxa(float(fc.kp[0]), float(fc.ki[0]), float(fc.kd[0]), float(fc.alfa[0]),
                                float(fc.tau_motor), atraso, _fc_mod.FILTRO_GIRO_HZ, _fc_mod.FILTRO_D_HZ, w)
    return w, t, ll, cruzamento_ganho(w, ll)


def ganhos_de_hardware(env, razao: float = 4.0, razao_atitude: float = 2.5, razao_posicao: float = 2.5,
                       u_yaw_por_taxa: float | None = None, **opcoes) -> GanhosCascata:
    """`GanhosCascata` derivada da PLANTA de um `DroneRealEnv` (peças, FC, inércia, arrasto de rotor).

    · malha de taxa — ganhos/filtros do `ControladorFC` do env: ω_c = cruzamento de ganho de L(jω) (com o
      atraso de comando, meia retenção da decisão e o atraso do giroscópio);
    · yaw — α_z do FC e a folga do acelerador (`min(1 − u_pair, u_pair − idle)`), amortecimento de yaw do arrasto
      de rotor c_yaw = d·m·r² (d = `aero.d_xy` s⁻¹, r = braço = ½·wheelbase); `u_yaw_por_taxa` (IDENTIFICADO no
      simulador por `avaliar_classico.identificar_yaw`) substitui a fórmula quando dado;
    · arrasto — `k_arrasto` = d do rotor (feed-forward do arrasto linear);
    · teto de altitude — 90 % do alcance do ToF (VL53L1X: 3,6 m): acima, ĥ e o fluxo (escala) deixam de existir;
    · sensor de fluxo — o atraso da velocidade medida, o braço ao CM e o desfasamento giroscópio/fluxo (catálogo de
      sensores + geometria do modelo): o que o observador de perturbação e o `EstimadorClassico` precisam;
    · tudo o resto: fórmulas fechadas de `GanhosCascata.de_planta`.
    """
    import numpy as np
    fc, hw = env.fc, env.hw
    _w, _t, _ll, omega_c = _malha_taxa_do_env(env)
    d_arrasto = float(np.mean(env.planta.aero.d_xy))
    r_braco = 0.5 * float(hw.frame.wheelbase)
    opcoes.setdefault("k_arrasto", d_arrasto)
    tof = hw.sensores.get("tof")
    if tof is not None:        # o ToF só mede até `alcance_max` (3,6 m): acima o drone perde a altura (e o fluxo a escala)
        opcoes.setdefault("altura_max", 0.9 * float(tof.get("alcance_max", 1e9)))
    # sensor de fluxo: atraso da velocidade medida (transporte + PT1 do estimador, τ = T·(1/α − 1), + meia amostra), braço
    # ao CM (o fluxo e o ToF partilham o site `baixo`) e passos entre o giroscópio e a amostra de fluxo do mesmo instante
    fluxo = hw.sensores.get("fluxo")
    atraso_vel, braco_fluxo, atraso_fluxo = 0.0, 0.0, 0
    if fluxo is not None:
        periodo = 1.0 / float(fluxo.get("taxa_hz", 1.0 / float(env.dt)))
        atraso_s = float(fluxo.get("atraso_s", 0.0))
        atraso_vel = atraso_s + periodo * (1.0 / ALFA_FLUXO - 1.0) + 0.5 * periodo
        atraso_giro = float(hw.sensores["imu"]["giro"].get("atraso_s", 0.0))
        atraso_fluxo = max(0, round((atraso_s - atraso_giro) / float(env.dt)))
        braco_fluxo = -float(env.model.site_pos[env.model.site("baixo").id][2])
    planta = PlantaLinear(
        omega_taxa=omega_c, tau_motor=float(fc.tau_motor), alfa_yaw=float(fc.alfa[2]),
        inercia_zz=float(fc.inercia[2]), c_yaw=d_arrasto * float(env.massa) * r_braco * r_braco,
        u_pairagem=float(env.u_pairagem), idle=float(fc.idle), dt_decisao=float(env.dt_decisao),
        u_yaw_por_taxa=u_yaw_por_taxa, atraso_vel=atraso_vel, braco_fluxo=braco_fluxo, atraso_fluxo=atraso_fluxo)
    return GanhosCascata.de_planta(planta, razao, razao_atitude=razao_atitude, razao_posicao=razao_posicao,
                                   **opcoes)


def _margens(w, ll) -> dict:
    """Cruzamento de ganho [rad/s], margem de fase [°] e de ganho [dB] de uma resposta em malha aberta L(jω)."""
    import numpy as np
    mag, fase = np.abs(ll), np.unwrap(np.angle(ll))
    ic = int(np.argmax(mag < 1.0))
    i180 = np.nonzero(fase < -math.pi)[0]
    gm = 20.0 * math.log10(1.0 / float(mag[i180[0]])) if i180.size else float("inf")
    return {"wc_rad_s": float(w[ic]), "pm_graus": 180.0 + math.degrees(float(fase[ic])), "gm_db": gm}


def margens_cascata(env, gn: GanhosCascata) -> dict:
    """Margens (PM/GM) dos laços da cascata em CASCATA, com a resposta REAL da malha de taxa do env (fc.py + atrasos).

    Cada laço externo vê o interno em malha fechada, T = L/(1 + L):
        taxa        L_r  (fc.py)                            atitude   L_a = (K_att/s)·T_r
        velocidade  L_v = (K_v + K_i/s)/s · T_a              posição   L_p = (K_pos/s)·T_v
        vertical    L_vz = (K_vz + K_iz/s)·e^{−sτ}/(s(τ_m s + 1))       altura   L_pz = (K_pz/s)·T_vz
    (a inclinação desejada → aceleração é um ganho unitário: a = g·tan θ ≈ g·θ). Verificação analítica; os degraus
    medidos no simulador confirmam (README).
    """
    import numpy as np
    w, t_r, l_r, _ = _malha_taxa_do_env(env)
    s = 1j * w
    l_a = gn.k_att / s * t_r
    t_a = l_a / (1.0 + l_a)
    l_v = (gn.k_vel + gn.ki_vel / s) / s * t_a
    t_v = l_v / (1.0 + l_v)
    l_p = gn.k_pos / s * t_v
    tau_m = float(env.fc.tau_motor)
    atraso_z = float(env.atraso_comando) + 0.5 * float(env.dt_decisao)
    l_vz = (gn.k_vz + gn.ki_vz / s) * np.exp(-s * atraso_z) / (s * (tau_m * s + 1.0))
    t_vz = l_vz / (1.0 + l_vz)
    l_pz = gn.k_pz / s * t_vz
    return {"taxa": _margens(w, l_r), "atitude": _margens(w, l_a), "velocidade": _margens(w, l_v),
            "posicao": _margens(w, l_p), "velocidade_vertical": _margens(w, l_vz), "altura": _margens(w, l_pz)}


# ------------------------------------------------------------------------------------------ a cascata
def _finito(nome: str, v) -> float:
    v = float(v)
    if not math.isfinite(v):
        raise ValueError(f"`{nome}` não finito: {v!r}")
    return v


def _ler_est(est) -> tuple[float, ...]:
    if isinstance(est, Mapping):
        return tuple(_finito(k, est[k]) for k in CAMPOS_EST)
    return tuple(_finito(k, getattr(est, k)) for k in CAMPOS_EST)


def _ler_cmd(cmd) -> dict:
    d = {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_taxa": 0.0, "modo": "velocidade", "yaw": None, "z_alvo": None}
    d.update(cmd or {})
    modo = d["modo"]
    if modo not in MODOS:
        raise ValueError(f"modo desconhecido {modo!r} (válidos: {MODOS})")
    out = {"modo": modo}
    for k in ("vx", "vy", "vz", "yaw_taxa"):
        out[k] = _finito(k, d[k])
    out["yaw"] = None if d["yaw"] is None else _finito("yaw", d["yaw"])
    out["z_alvo"] = None if d["z_alvo"] is None else _finito("z_alvo", d["z_alvo"])
    if modo == "yaw_alvo" and out["yaw"] is None:
        raise ValueError("modo `yaw_alvo` exige `yaw` (rumo absoluto, rad)")
    return out


class CascataClassica:
    """Cascata posição → velocidade → inclinação+empuxo → atitude (ver o docstring do módulo).

    Estado (referências e integradores) vive na instância; `armar(True, est)` trava as referências no estado
    atual (posição, altura, rumo). Desarmada devolve `(0, (0, 0, 0))` — NEUTRO: sem empuxo, sem taxas.
    """

    def __init__(self, ganhos: GanhosCascata):
        self.g = ganhos
        self.reiniciar()

    # -------------------------------------------------------------------- estado
    def reiniciar(self) -> None:
        """Desarma e limpa todos os estados."""
        self.armado = False
        self._iniciado = False
        self.p_sp = [0.0, 0.0]            # m — referência de posição (referencial de arranque «O»)
        self.z_sp = 0.0                   # m — referência de altura
        self.psi_sp = 0.0                 # rad — referência de rumo
        self.r_ref = 0.0                  # rad/s — taxa de yaw conformada (referência)
        self.v_sp_h = [0.0, 0.0]          # m/s — velocidade conformada no referencial do rumo
        self.v_mod_h = [0.0, 0.0]         # m/s — a mesma, atrasada pelo modelo de seguimento da malha de atitude
        self.v_mod_z = 0.0
        self.a_sp_h = [0.0, 0.0]          # m/s²
        self.v_sp_z = 0.0
        self.a_sp_z = 0.0
        self.i_vel = [0.0, 0.0]           # m/s² — integrais da velocidade horizontal (referencial O)
        self.i_z = 0.0                    # m/s² — integral vertical (adapta o empuxo de pairagem)
        self.d_filt = [0.0, 0.0]          # filtro do termo D
        self.v_ant = None
        self.z_alvo = None
        self._n_ant = None                # direção do empuxo do passo anterior (feed-forward de taxa)
        self._dn = [0.0, 0.0, 0.0]
        self._zerar_observador()
        self.dados: dict = {}

    def _zerar_observador(self) -> None:
        """Estados do observador de perturbação (fase 2), no referencial de arranque."""
        self.v_obs = None                 # m/s — velocidade horizontal do modelo (None = arranca na 1.ª medida)
        self.d_obs = [0.0, 0.0]           # m/s² — perturbação horizontal observada
        self.a_emp = [0.0, 0.0]           # m/s² — aceleração do empuxo (da atitude estimada), atrasada como a medida
        self.az_ref = 0.0                 # m/s² — aceleração vertical pretendida na decisão anterior (sem o integral)

    def armar(self, armado: bool, est=None, z_alvo: float | None = None) -> None:
        """Arma/desarma. Ao armar com `est`, trava referências (x, y, ψ) no estado atual; `z_alvo` [m] = altura a
        atingir (DESCOLAR); sem ele trava a altura medida."""
        if armado and not self.armado:
            self._zerar_estados()
            if est is not None:
                self._travar(_ler_est(est), z_alvo)
        elif not armado:
            self._zerar_estados()
            self._iniciado = False
        self.armado = bool(armado)

    def _zerar_estados(self) -> None:
        self.v_sp_h, self.a_sp_h = [0.0, 0.0], [0.0, 0.0]
        self.v_mod_h, self.v_mod_z = [0.0, 0.0], 0.0
        self.v_sp_z = self.a_sp_z = self.r_ref = 0.0
        self.i_vel, self.i_z, self.d_filt, self.v_ant = [0.0, 0.0], 0.0, [0.0, 0.0], None
        self.z_alvo = None
        self._n_ant, self._dn = None, [0.0, 0.0, 0.0]
        self._zerar_observador()

    def _travar(self, e: tuple[float, ...], z_alvo: float | None) -> None:
        _phi, _theta, psi, h, _vz, _vx, _vy, x, y = e
        self.p_sp = [x, y]
        self.psi_sp = psi
        self.z_sp = h
        self.z_alvo = z_alvo
        self._iniciado = True

    # -------------------------------------------------------------------- um passo
    def passo(self, est, giro, cmd, dt: float) -> tuple[float, tuple[float, float, float]]:
        """Uma decisão: estimativas + taxas medidas + comando → (empuxo coletivo T/(m·g), (p, q, r) [rad/s]).

        Etapas: 1 velocidade medida no rumo/arranque · 1b observador de perturbação (vento) · 2 yaw (conformador de taxa +
        referência de rumo) · 3 conformador de velocidade e de altura (+ modelo de seguimento) · 4 referência de posição ·
        5 laço de posição (raiz quadrada) e de velocidade (PI + FF − perturbação observada) → aceleração · 6 laço de
        altura/velocidade vertical → a_z · 7 inclinação desejada e coletivo (÷ cosφ·cosθ; anti-windup) · 8 atitude com
        prioridade de inclinação → taxas. Estado de diagnóstico em `self.dados`.
        """
        dt = _finito("dt", dt)
        if dt <= 0.0:
            raise ValueError(f"dt tem de ser > 0 (recebido {dt!r})")
        e = _ler_est(est)
        r_giro = _finito("giro[2]", giro[2])
        _finito("giro[0]", giro[0])
        _finito("giro[1]", giro[1])
        c = _ler_cmd(cmd)
        if not self.armado:
            return 0.0, (0.0, 0.0, 0.0)
        if not self._iniciado:
            self._travar(e, None)
        gn = self.g
        phi, theta, psi, h, vz, vbx, vby, x, y = e
        cs, sn = math.cos(psi), math.sin(psi)

        # ---- 1. velocidade medida: corpo → referencial do rumo (H) → referencial de arranque (O)
        vhx, vhy = velocidade_no_rumo(phi, theta, vbx, vby, vz)
        vox, voy = cs * vhx - sn * vhy, sn * vhx + cs * vhy
        sf, cf = math.sin(phi), math.cos(phi)
        st, ct = math.sin(theta), math.cos(theta)

        # ---- 1b. OBSERVADOR DE PERTURBAÇÃO horizontal (estado estendido [HAN09]; fase 2: vento), no referencial O
        # Modelo:      v̇ = a_emp − d_arr·v + d      a_emp = (g + a_z)·(ẑ_b)_xy/(ẑ_b)_z — a aceleração que o EMPUXO dá, lida
        #                                           da atitude ESTIMADA (não da pedida: o atraso da malha de atitude e a
        #                                           saturação da inclinação já vêm lá dentro, sem windup)
        # Observador:  v̂' = a_emp,f − d_arr·v̂ + d̂ + 2ω·(v − v̂)       d̂' = ω²·(v − v̂)        (polos duplos em −ω [GAO03])
        # `d` é tudo o que o modelo não explica: vento, arrasto mal modelado, viés da atitude estimada. a_emp,f é a_emp com o
        # atraso da velocidade medida (τ_vel): modelo e medida comparam-se no MESMO instante (sem isto, cada manobra
        # parecia uma perturbação — medido: sobressinal do degrau de velocidade 10 % → 3 %).
        if gn.w_pert > 0.0:
            den = ct * cf
            if den < 0.2:                               # quase de cabeça para baixo: sem modelo (nunca acontece em voo)
                atx = aty = 0.0
            else:
                fz = (gn.g + self.az_ref) / den
                atx, aty = fz * (cs * st * cf + sn * sf), fz * (sn * st * cf - cs * sf)
            if self.v_obs is None:
                self.v_obs, self.a_emp = [vox, voy], [atx, aty]
            am = dt / (gn.tau_vel + dt)
            for i, (vm, at) in enumerate(((vox, atx), (voy, aty))):
                self.a_emp[i] += am * (at - self.a_emp[i])
                e_o = vm - self.v_obs[i]
                self.v_obs[i] += dt * (self.a_emp[i] - gn.k_arrasto * self.v_obs[i] + self.d_obs[i]
                                       + 2.0 * gn.w_pert * e_o)
                self.d_obs[i] = limita(self.d_obs[i] + dt * gn.w_pert * gn.w_pert * e_o, -gn.lim_pert, gn.lim_pert)

        # ---- 2. YAW: conformador da taxa (limite de taxa e de aceleração) + referência de rumo
        yaw_aut = c["modo"] == "yaw_alvo"
        if yaw_aut:
            e_psi = envolve_pi(c["yaw"] - self.psi_sp)
            r_des = raiz_quadrada(e_psi, gn.peso_yaw * gn.k_yaw, gn.acel_yaw_max)
        else:
            r_des = c["yaw_taxa"]
        r_des = limita(r_des, -gn.taxa_yaw_max, gn.taxa_yaw_max)
        r_ant = self.r_ref
        self.r_ref += limita(r_des - self.r_ref, -gn.acel_yaw_max * dt, gn.acel_yaw_max * dt)
        e_av = envolve_pi(self.psi_sp - psi)
        if (e_av > gn.avanco_yaw_max and self.r_ref > 0.0) or (e_av < -gn.avanco_yaw_max and self.r_ref < 0.0):
            r_int = 0.0                       # a referência já vai à frente do que a planta consegue: não avança
        else:
            r_int = self.r_ref
        self.psi_sp = envolve_pi(self.psi_sp + r_int * dt)

        # ---- 3. conformador de velocidade (referencial do rumo): v_cmd → (v_sp, a_sp)
        vmax = gn.vel_xy_max
        vcx, vcy = c["vx"], c["vy"]
        nv = math.hypot(vcx, vcy)
        if nv > vmax:
            vcx, vcy = vcx * vmax / nv, vcy * vmax / nv
        for i, vc in enumerate((vcx, vcy)):
            a_des = limita(raiz_quadrada(vc - self.v_sp_h[i], gn.k_conf, gn.jerk_cmd_xy),
                           -gn.acc_cmd_xy, gn.acc_cmd_xy)
            self.a_sp_h[i] += limita(a_des - self.a_sp_h[i], -gn.jerk_cmd_xy * dt, gn.jerk_cmd_xy * dt)
            self.v_sp_h[i] += self.a_sp_h[i] * dt
        # vertical: velocidade comandada (Q/E) e/ou «ir até z_alvo» (descolar). Com um z_alvo pendente os comandos de
        # velocidade MOVEM o alvo (o descolar não é cancelado por um Q carregado a meio: o alvo = descolagem + ∫vz).
        if c["z_alvo"] is not None:
            self.z_alvo = c["z_alvo"]
        vcz_man = limita(c["vz"], -gn.vel_z_max, gn.vel_z_max)
        if self.z_alvo is not None:
            self.z_alvo = limita(self.z_alvo + vcz_man * dt, gn.altura_min, gn.altura_max)
            vcz = limita(vcz_man + raiz_quadrada(self.z_alvo - self.z_sp, gn.k_pz, gn.acc_cmd_z),
                         -gn.vel_goto_z, gn.vel_goto_z)           # feed-forward do Q/E + aproximação ao alvo
            if abs(self.z_alvo - self.z_sp) < 0.01 and abs(self.v_sp_z) < 0.05 and abs(vcz_man) < 1e-9:
                self.z_sp = self.z_alvo                       # chegou: trava exatamente na altura pedida
                self.z_alvo = None
        else:
            vcz = vcz_man
        a_des_z = limita(raiz_quadrada(vcz - self.v_sp_z, gn.k_conf_z, gn.jerk_cmd_z), -gn.acc_cmd_z, gn.acc_cmd_z)
        self.a_sp_z += limita(a_des_z - self.a_sp_z, -gn.jerk_cmd_z * dt, gn.jerk_cmd_z * dt)
        self.v_sp_z += self.a_sp_z * dt

        # modelo de seguimento: a planta (malha de atitude) ATRASA a resposta; a realimentação compara com a referência
        # atrasada para não «contar duas vezes» o atraso que o feed-forward já aceita (evita o sobressinal)
        if gn.tau_modelo > 0.0:
            am = dt / (gn.tau_modelo + dt)
            self.v_mod_h[0] += am * (self.v_sp_h[0] - self.v_mod_h[0])
            self.v_mod_h[1] += am * (self.v_sp_h[1] - self.v_mod_h[1])
        if gn.tau_modelo_z > 0.0:
            self.v_mod_z += (dt / (gn.tau_modelo_z + dt)) * (self.v_sp_z - self.v_mod_z)
        else:
            self.v_mod_z = self.v_sp_z
        if gn.tau_modelo <= 0.0:
            self.v_mod_h = list(self.v_sp_h)
        # ---- 4. referência de posição («segura» quando v = 0)
        vsx, vsy = cs * self.v_mod_h[0] - sn * self.v_mod_h[1], sn * self.v_mod_h[0] + cs * self.v_mod_h[1]
        if gn.ref_posicao == "trava":
            # estilo PX4 (modo Position): em movimento a referência acompanha a medida (laço de posição inativo);
            # ao parar, TRAVA onde ficou — o drone é depois «seguro» nesse ponto
            if (abs(c["vx"]) + abs(c["vy"]) > 1e-6) or math.hypot(*self.v_sp_h) > 0.03:
                self.p_sp[0], self.p_sp[1] = x, y
        else:
            self.p_sp[0] += vsx * dt
            self.p_sp[1] += vsy * dt
        self.z_sp += self.v_mod_z * dt        # a altitude integra sempre (a resposta vertical é rápida e sem lead)
        if self.z_sp < gn.altura_min or self.z_sp > gn.altura_max:      # piso/teto de altitude em voo
            self.z_sp = limita(self.z_sp, gn.altura_min, gn.altura_max)
            if (self.z_sp <= gn.altura_min) == (self.v_sp_z < 0.0):
                self.v_sp_z = self.a_sp_z = self.v_mod_z = 0.0
        ex, ey = self.p_sp[0] - x, self.p_sp[1] - y
        dist = math.hypot(ex, ey)
        if dist > gn.avanco_pos_max:                      # referência demasiado à frente: não acumula
            k = gn.avanco_pos_max / dist
            self.p_sp[0], self.p_sp[1] = x + ex * k, y + ey * k
            ex, ey, dist = ex * k, ey * k, gn.avanco_pos_max

        # ---- 5. laço de posição (P, com aproximação raiz-quadrada) + velocidade (PI(D)) → aceleração
        if dist > 1e-9:
            v_corr = limita(raiz_quadrada(dist, gn.k_pos, gn.acc_pos), 0.0, gn.vel_corr_pos_max)
            ux, uy = ex / dist * v_corr, ey / dist * v_corr
        else:
            ux = uy = 0.0
        vdx, vdy = vsx + ux, vsy + uy
        evx, evy = vdx - vox, vdy - voy
        if gn.kd_vel > 0.0:
            if self.v_ant is None:
                self.v_ant = [vox, voy]
            alfa_d = dt / (gn.tau_d_vel + dt)
            self.d_filt[0] += alfa_d * ((vox - self.v_ant[0]) / dt - self.d_filt[0])
            self.d_filt[1] += alfa_d * ((voy - self.v_ant[1]) / dt - self.d_filt[1])
            self.v_ant = [vox, voy]
        # feed-forward: aceleração conformada + centrípeta (ω × v) da referência
        axh = gn.k_ff_acc * self.a_sp_h[0] - self.r_ref * self.v_sp_h[1]
        ayh = gn.k_ff_acc * self.a_sp_h[1] + self.r_ref * self.v_sp_h[0]
        aff_x, aff_y = cs * axh - sn * ayh, sn * axh + cs * ayh
        # o empuxo vence o arrasto linear a = −d·v [FAE18] — na velocidade que o MODELO de seguimento prevê (a verdadeira
        # ainda não chegou à referência: usar v_sp ultrapassa o regime e dá sobressinal)
        aff_x += gn.k_arrasto * vsx
        aff_y += gn.k_arrasto * vsy
        # … e a perturbação observada é ANULADA (o vento é compensado à velocidade do laço de atitude, sem esperar pelo
        # integral, que fica só com o resíduo)
        ax = aff_x + gn.k_vel * evx + self.i_vel[0] - gn.kd_vel * self.d_filt[0] - self.d_obs[0]
        ay = aff_y + gn.k_vel * evy + self.i_vel[1] - gn.kd_vel * self.d_filt[1] - self.d_obs[1]

        # ---- 6. laço vertical: altura (P) → velocidade (PI) → aceleração
        ez = self.z_sp - h
        v_corr_z = limita(raiz_quadrada(ez, gn.k_pz, gn.acc_cmd_z), -gn.vel_corr_z_max, gn.vel_corr_z_max)
        evz = self.v_mod_z + v_corr_z - vz
        # a aceleração vertical PRETENDIDA fica guardada para o modelo do observador (etapa 1b da decisão seguinte); o
        # integral não entra nela: só adapta o empuxo de pairagem (massa, kf), não é aceleração
        self.az_ref = self.a_sp_z + gn.k_vz * evz
        az = self.az_ref + self.i_z

        # ---- 7. inclinação desejada + empuxo coletivo (÷ cosφ·cosθ)
        nx, ny, nz, coletivo, sat_incl = direcao_empuxo(ax, ay, az, gn.g, gn.tilt_max,
                                                        gn.coletivo_min, gn.coletivo_max)
        # o diferencial de yaw do FC acrescenta empuxo (T ∝ u²: Σ(u₀ ± d)² = 4u₀² + 4d²): pré-compensa-se
        # c_eff = c − (d/u_pair)², com d = acelerador diferencial estimado da referência de yaw (u/r·r + ṙ/α_z)
        if gn.comp_yaw_empuxo:
            d_yaw = (gn.u_yaw_por_taxa * abs(self.r_ref)
                     + gn.comp_yaw_acel * abs(self.r_ref - r_ant) / dt / gn.alfa_yaw)
            coletivo = max(coletivo - (d_yaw / gn.u_pairagem) ** 2, gn.coletivo_min)
        # anti-windup (retro-cálculo na horizontal; integração condicional na vertical) [AM08][PX4]
        a_prod = math.hypot(ax, ay)
        if sat_incl and a_prod > 1e-9:
            lim = (gn.g + az) * math.tan(gn.tilt_max)
            fator = lim / a_prod
            ax_s, ay_s = ax * fator, ay * fator
        else:
            ax_s, ay_s = ax, ay
        k_aw = gn.aw_ganho / max(gn.k_vel, 1e-6)
        self.i_vel[0] = limita(self.i_vel[0] + gn.ki_vel * dt * (evx + k_aw * (ax_s - ax)), -2.0, 2.0)
        self.i_vel[1] = limita(self.i_vel[1] + gn.ki_vel * dt * (evy + k_aw * (ay_s - ay)), -2.0, 2.0)
        sat_cima = coletivo >= gn.coletivo_max - 1e-9 and evz > 0.0
        sat_baixo = coletivo <= gn.coletivo_min + 1e-9 and evz < 0.0
        if not (sat_cima or sat_baixo):
            self.i_z = limita(self.i_z + gn.ki_vz * dt * evz, -0.4 * gn.g, 0.4 * gn.g)

        # ---- 8. atitude com prioridade de inclinação → taxas
        n_des = (nx, ny, nz)
        e_x, e_y, gama = erro_atitude(phi, theta, psi, n_des, self.psi_sp)
        # taxa de yaw do MUNDO (ψ̇ = r_ref) nos eixos do corpo: ω_b = Rᵀ·(ψ̇·ẑ) = ψ̇·(−sθ, sφ·cθ, cφ·cθ)
        p_ff, q_ff, r_ff = -st * self.r_ref, sf * ct * self.r_ref, cf * ct * self.r_ref
        # feed-forward da taxa de inclinação: n̂ roda com ω = n̂ × dn̂/dt (mundo); as componentes x, y do corpo são p, q
        if gn.ff_atitude and self._n_ant is not None:
            alfa_f = dt / (gn.tau_ff + dt)
            for i in range(3):
                self._dn[i] += alfa_f * ((n_des[i] - self._n_ant[i]) / dt - self._dn[i])
            wx = ny * self._dn[2] - nz * self._dn[1]
            wy = nz * self._dn[0] - nx * self._dn[2]
            wz = nx * self._dn[1] - ny * self._dn[0]
            cp_, sp_ = cs, sn
            xb = (cp_ * ct, sp_ * ct, -st)
            yb = (cp_ * st * sf - sp_ * cf, sp_ * st * sf + cp_ * cf, ct * sf)
            p_ff += xb[0] * wx + xb[1] * wy + xb[2] * wz
            q_ff += yb[0] * wx + yb[1] * wy + yb[2] * wz
        self._n_ant = n_des
        p_sp = limita(gn.k_att * e_x + p_ff, -gn.taxa_rp_max, gn.taxa_rp_max)
        q_sp = limita(gn.k_att * e_y + q_ff, -gn.taxa_rp_max, gn.taxa_rp_max)
        r_sp = limita(r_ff + gn.peso_yaw * gn.k_yaw * gama, -gn.taxa_yaw_max, gn.taxa_yaw_max)
        self.dados = {"a_des": (ax, ay, az), "n_des": n_des, "coletivo": coletivo, "e_tilt": (e_x, e_y),
                      "gama": gama, "v_h": (vhx, vhy), "v_o": (vox, voy), "v_sp_h": tuple(self.v_sp_h),
                      "p_sp": tuple(self.p_sp), "z_sp": self.z_sp, "psi_sp": self.psi_sp, "r_ref": self.r_ref,
                      "sat_incl": sat_incl, "i_vel": tuple(self.i_vel), "i_z": self.i_z, "r_giro": r_giro,
                      "pert": tuple(self.d_obs)}
        return coletivo, (p_sp, q_sp, r_sp)


# ------------------------------------------------------------------------------------------ estimador melhorado
K_ATITUDE = 0.5          # 1/s — peso do acelerómetro no filtro complementar (o mesmo do `estimador.py`)
W_ALTURA = 4.0           # rad/s — banda do observador de altura
ZETA_ALTURA = 0.7
ALFA_FLUXO = 0.35        # PT1 da velocidade do fluxo, por amostra nova
DECAI_FLUXO = 0.995      # sem fluxo válido, a velocidade estimada decai devagar (por passo de física)
TAU_ACC_PORTAO = 0.5     # s — constante do PT1 que dá a aceleração horizontal ao «portão» do acelerómetro
ATRASO_FLUXO_MAX = 16    # passos — tamanho da fila do giroscópio que alinha a rotação com a amostra do fluxo (firmware)


class EstimadorClassico:
    """Estimador de bordo com CALIBRAÇÃO DO GIROSCÓPIO no chão — substituto direto do `EstimadorBordo`.

    O `EstimadorBordo` (estimador.py) integra o giroscópio SEM tirar o viés: o viés b (σ = 3,5 mrad/s neste
    BMI088, sorteado por voo) entra em (i) o RUMO ψ̂ (deriva b·t) e (ii) a velocidade do FLUXO, v = d·(q − Ω_y),
    como um viés de velocidade d·b (3,5 mm/s a 1 m de altura ⇒ 10 cm em 30 s de odometria à deriva). Aqui:

      · `calibrar(True)` … `calibrar(False)`: com o drone PARADO no chão (motores em idle) acumulam-se o giroscópio
        e o acelerómetro; no fim, b̂ = média do giroscópio e a atitude inicial sai da MÉDIA do acelerómetro (o
        `EstimadorBordo` usa UMA amostra). É o «gyro calibration» que PX4/ArduPilot fazem ao ligar (ideia pública);
      · depois do armar, o giroscópio entra com b̂ subtraído (atitude, rumo e compensação do fluxo);
      · opcional `portao_acc`: o acelerómetro de um multirrotor mede o EMPUXO (sempre ao longo de z_corpo) e não a
        gravidade quando o drone ACELERA — a correção «para o acelerómetro» puxa a inclinação para ZERO (enviesa
        durante as manobras). O ganho é escalado por 1/(1 + (‖a_h‖/a_portão)²), com ‖a_h‖ a aceleração horizontal
        estimada da derivada filtrada da velocidade do fluxo;
      · ALTURA: observador de 3.ª ordem (ĥ, v̂_z e o VIÉS do acelerómetro na vertical, com o ToF): um viés b do acelerómetro
        (σ = 0,05 m/s² + 0,5 % de escala ≈ 0,1 m/s²) dá, no de 2.ª ordem, um viés de velocidade 0,35·b ≈ 4 cm/s e o
        laço de altitude segura ĥ 3–4 cm abaixo do alvo; com o 3.º estado o viés é estimado e a altura assenta;
      · opcional `ki_mahony` (parte INTEGRAL de Mahony et al. [MAH08] sobre roll/pitch, com o mesmo portão): desligada por
        omissão — MEDIDO que não ajuda (hover −5 % com 0,02 /s², seguimento pior com 0,1 e instável com 0,5);
      · VELOCIDADE DO FLUXO sem os artefactos da ROTAÇÃO (`configurar_fluxo`; fase 2 — é desta velocidade que o observador de
        perturbação da cascata vive, e cada manobra de inclinação enganava-o): (i) o sensor de fluxo mede a velocidade
        DELE, a `braco_fluxo` do CM — v_cm = v_sensor − ω × r, ou seja v̂_x += b·q e v̂_y −= b·p (4 cm × 1 rad/s = 4 cm/s
        a mudar em décimas de segundo); (ii) a amostra do fluxo sai `atraso_fluxo` passos depois do giroscópio do mesmo
        instante — a rotação que se lhe tira (q − Ω_y) é a do giroscópio DESSE instante (fila de N amostras), não a de
        agora. MEDIDO no núcleo C++ com o observador ligado (degrau de comando, sementes de calibração): sobressinal 11,3 %
        sem as duas correções → 2,6 % com elas;
      · tudo o resto é igual ao `EstimadorBordo` (cinemática ZYX, v̂_xy do fluxo no corpo, odometria) — mesmas
        fórmulas, escalares Python.

    Interface idêntica: `reiniciar`, `passo` e os atributos `roll pitch psi h vz vx vy x y` (e `bias_giro`).
    """

    def __init__(self, dt: float, *, cal_giro: bool = True, portao_acc: bool = True, a_portao: float = 0.15,
                 k_atitude: float = K_ATITUDE, bias_acc_z: bool = True, ki_mahony: float = 0.0,
                 braco_fluxo: float = 0.0, atraso_fluxo: int = 0):
        self.dt = float(dt)
        self.bias_acc_z = bool(bias_acc_z)
        self.ki_mahony = float(ki_mahony)
        self.cal_giro = bool(cal_giro)
        self.portao_acc = bool(portao_acc)
        self.a_portao = float(a_portao)
        self.k_atitude = float(k_atitude)
        self.configurar_fluxo(atraso_fluxo, braco_fluxo)
        self.reiniciar()

    def configurar_fluxo(self, atraso_passos: int, braco: float) -> None:
        """Geometria e tempos do sensor de fluxo (os da `GanhosCascata` da planta: `atraso_fluxo`, `braco_fluxo`):
        `atraso_passos` = passos entre o giroscópio e a amostra de fluxo do mesmo instante (0 = usa o giroscópio de agora,
        como o `EstimadorBordo`); `braco` [m] = altura do CM acima do sensor (0 = sem correção ω × r)."""
        if int(atraso_passos) < 0 or int(atraso_passos) >= ATRASO_FLUXO_MAX:
            raise ValueError(f"atraso_passos tem de estar em [0, {ATRASO_FLUXO_MAX - 1}] (recebido {atraso_passos!r})")
        self.atraso_fluxo = int(atraso_passos)
        self.braco_fluxo = float(braco)
        self._fila_pq: deque = deque(maxlen=self.atraso_fluxo + 1)       # (p, q) sem viés dos últimos N + 1 passos

    def reiniciar(self, acc=(0.0, 0.0, G), tof_d: float = 0.0, tof_ok: bool = False) -> None:
        ax, ay, az = (float(v) for v in acc)
        self.roll = math.atan2(ay, az)
        self.pitch = math.atan2(-ax, math.hypot(ay, az))
        self.psi = 0.0
        self.h = tof_d * math.cos(self.roll) * math.cos(self.pitch) if tof_ok else 0.0
        self.vz = self.vx = self.vy = self.x = self.y = 0.0
        self.bias_giro = [0.0, 0.0, 0.0]
        self.bias_acc = 0.0                 # m/s² — viés do acelerómetro na VERTICAL (3.º estado do observador de altura)
        self.b_pi = [0.0, 0.0]              # rad/s — viés residual do giroscópio em p, q estimado pelo integral (Mahony PI)
        self._calibrando = False
        self._n_cal = 0
        self._soma_giro = [0.0, 0.0, 0.0]
        self._soma_acc = [0.0, 0.0, 0.0]
        self._ultimo_tof = (tof_d, tof_ok)
        self._n_tof = -1
        self._n_fluxo = -1
        self._a_h = 0.0
        self._v_lenta = (0.0, 0.0)
        self._fila_pq.clear()

    def calibrar(self, ativo: bool) -> None:
        """`True` abre a janela de calibração (drone PARADO); `False` fecha-a e aplica b̂ e a atitude inicial."""
        if ativo:
            self._calibrando = True
            self._n_cal = 0
            self._soma_giro = [0.0, 0.0, 0.0]
            self._soma_acc = [0.0, 0.0, 0.0]
            return
        if self._calibrando and self._n_cal > 0:
            n = float(self._n_cal)
            if self.cal_giro:
                self.bias_giro = [s / n for s in self._soma_giro]
            ax, ay, az = (s / n for s in self._soma_acc)
            self.roll = math.atan2(ay, az)
            self.pitch = math.atan2(-ax, math.hypot(ay, az))
            d, ok = self._ultimo_tof
            self.h = d * math.cos(self.roll) * math.cos(self.pitch) if ok else self.h
            self.psi = 0.0
            self.vz = self.vx = self.vy = self.x = self.y = 0.0
            self._fila_pq.clear()
        self._calibrando = False

    def passo(self, giro, acc, tof_d: float, tof_ok: bool, n_tof: int, fluxo, fluxo_ok: bool,
              n_fluxo: int) -> None:
        dt = self.dt
        if self._calibrando:
            for i in range(3):
                self._soma_giro[i] += float(giro[i])
                self._soma_acc[i] += float(acc[i])
            self._n_cal += 1
            self._ultimo_tof = (tof_d, tof_ok)
            return
        p = float(giro[0]) - self.bias_giro[0] - self.b_pi[0]
        q = float(giro[1]) - self.bias_giro[1] - self.b_pi[1]
        r = float(giro[2]) - self.bias_giro[2]
        ax, ay, az = (float(v) for v in acc)
        sf, cf = math.sin(self.roll), math.cos(self.roll)
        ct = math.cos(self.pitch)
        tt = math.tan(self.pitch) if abs(ct) > 1e-3 else 0.0
        droll = p + (q * sf + r * cf) * tt
        dpitch = q * cf - r * sf
        dpsi = (q * sf + r * cf) / ct if abs(ct) > 1e-3 else 0.0
        k = self.k_atitude
        if self.portao_acc:
            k = k / (1.0 + (self._a_h / self.a_portao) ** 2)
        roll_a = math.atan2(ay, az)
        pitch_a = math.atan2(-ax, math.hypot(ay, az))
        e_roll = envolve_pi(roll_a - self.roll)
        e_pitch = pitch_a - self.pitch
        if self.ki_mahony > 0.0:          # parte INTEGRAL do filtro de Mahony (viés do giroscópio), com o mesmo portão
            ki = self.ki_mahony * k / self.k_atitude
            self.b_pi[0] = min(max(self.b_pi[0] - ki * e_roll * dt, -0.02), 0.02)
            self.b_pi[1] = min(max(self.b_pi[1] - ki * e_pitch * dt, -0.02), 0.02)
        self.roll += dt * (droll + k * e_roll)
        self.pitch += dt * (dpitch + k * e_pitch)
        self.psi = envolve_pi(self.psi + dt * dpsi)
        sf, cf = math.sin(self.roll), math.cos(self.roll)
        st, ct = math.sin(self.pitch), math.cos(self.pitch)
        a_z = -st * ax + sf * ct * ay + cf * ct * az - G - self.bias_acc
        self.vz += a_z * dt
        self.h += self.vz * dt
        if n_tof != self._n_tof:
            self._n_tof = n_tof
            if tof_ok:
                periodo = max(dt, 1.0 / 30.0)
                e = tof_d * cf * ct - self.h
                if self.bias_acc_z:
                    # observador de 3.ª ordem (h, v_z, viés), polos triplos em −ω₀: (s + ω₀)³
                    self.h += min(1.0, 3.0 * W_ALTURA * periodo) * e
                    self.vz += 3.0 * W_ALTURA * W_ALTURA * periodo * e
                    self.bias_acc = min(max(self.bias_acc - W_ALTURA ** 3 * periodo * e, -0.5), 0.5)
                else:                                   # 2.ª ordem do `estimador.py` (ζ = 0,7)
                    self.h += min(1.0, 2.0 * ZETA_ALTURA * W_ALTURA * periodo) * e
                    self.vz += W_ALTURA * W_ALTURA * periodo * e
        self._fila_pq.append((p, q))
        if n_fluxo != self._n_fluxo:
            self._n_fluxo = n_fluxo
            if fluxo_ok and tof_ok:
                fx, fy = (float(v) for v in fluxo)
                # a rotação do instante da amostra de fluxo (N passos atrás; enquanto a fila não enche, a de agora) e a
                # velocidade do CM: v_cm = v_sensor − ω × r, com o sensor `braco_fluxo` abaixo do CM
                p_f, q_f = self._fila_pq[0] if len(self._fila_pq) == self._fila_pq.maxlen else (p, q)
                self.vx += ALFA_FLUXO * (tof_d * (q_f - fy) + self.braco_fluxo * q_f - self.vx)
                self.vy += ALFA_FLUXO * (-tof_d * (fx + p_f) - self.braco_fluxo * p_f - self.vy)
        if not (fluxo_ok and tof_ok):
            self.vx *= DECAI_FLUXO
            self.vy *= DECAI_FLUXO
        if self.portao_acc:          # ‖a_h‖ ≈ ‖v̂ − v̂_lenta‖/τ (derivada suave: v̂_lenta = PT1 de τ = 0,5 s)
            a_l = dt / (TAU_ACC_PORTAO + dt)
            self._v_lenta = (self._v_lenta[0] + a_l * (self.vx - self._v_lenta[0]),
                             self._v_lenta[1] + a_l * (self.vy - self._v_lenta[1]))
            self._a_h = math.hypot(self.vx - self._v_lenta[0], self.vy - self._v_lenta[1]) / TAU_ACC_PORTAO
        cpsi, spsi = math.cos(self.psi), math.sin(self.psi)
        self.x += dt * (cpsi * self.vx - spsi * self.vy)
        self.y += dt * (spsi * self.vx + cpsi * self.vy)
