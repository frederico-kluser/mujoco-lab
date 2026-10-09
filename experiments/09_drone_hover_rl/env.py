"""experiments/09_drone_hover_rl/env.py — ambiente Gymnasium de RL: "o drone trava-se em (0, 0, 1) m com a
orientação fixa, mesmo com vento".

Crazyflie 2 (Bitcraze) do `mujoco_menagerie` (INTACTO em `models/bitcraze_crazyflie_2/`) com a camada de
sensores/controles de `lab/crazyflie.py`. Aqui só existe AMBIENTE: física, vento, observação, ação,
recompensa e terminação — nada de treino, viewer, dashboard, ONNX ou render (headless).

    import sys; sys.path[:0] = ["<raiz do laboratório>", "experiments/09_drone_hover_rl"]
    from env import HoverEnv
    env = HoverEnv(alvo_z=1.0, decimation=10, thrust_realista=True, tau_escala=0.1,
                   ruido_obs=0.0, episodio_s=10.0, vento=None, vento_aleatorio=None)
    obs, info = env.reset(seed=0)
    obs, r, terminated, truncated, info = env.step(env.action_space.sample())
    env.definir_vento(5.0, 0.0)          # vento CONSTANTE: 5 m/s a norte (azimute 0°), horizontal
    env.definir_vento_aleatorio(0.0, 2.0)  # currículo: U ~ [0, 2] m/s, reamostrado em CADA reset

CONTRATO (as peças train/view/dashboard/deploy/net_probe importam-no)
  · física a 500 Hz (`dt=0.002 s`, RK4) · `decimation=10` passos de física por `step()` → política a 50 Hz;
  · ação `Box(-1, 1, (4,))` = [empuxo, momento x, momento y, momento z] centrada no hover (a=0 → empuxo = peso):
      a₀ ≤ 0 → empuxo = mg·(1+a₀)   (a₀=-1 → 0 N)
      a₀ > 0 → empuxo = mg + (thrust_max − mg)·a₀   (a₀=+1 → thrust_max)
      momentos_i = tau_escala · momento_max_i · a_i, tudo cortado às faixas físicas dos canais;
  · RECOMPENSA v2b (substitui a literal do mjdg; por passo de DECISÃO). Com `xy = (x, y)`, `v` = ‖v‖ no mundo,
    `ω_xy` = 2 primeiros componentes angulares no CORPO, `ω_z` o terceiro e `Δa` = ação atual − ação anterior:
      r = −1.0·‖xy‖ − 1.0·|z−alvo_z| − 0.2·|yaw_err| − 0.05·‖v‖ − 0.05·‖ω_xy‖ − 0.1·|ω_z|
          − 0.05·‖Δa‖ + 1.0·𝟙[bonus] − 100·𝟙[terminated]
    com `yaw_err` = yaw (ZYX do `body_quat`, quaternion MuJoCo [w x y z]) ENVOLVIDO em [−π, π] e alvo 0 rad
    (orientação fixa; o reset traz jitter ±5° → a política aprende a corrigir) e
      bonus = ‖xy‖ < 0.05 ∧ |z−alvo_z| < 0.05 ∧ |yaw_err| < 0.10   (desigualdades ESTRITAS);
    v2b: pesos de yaw/ωz/Δa ajustados após campanha de 20 treinos — chatter de momentos (as políticas saturavam
    |a|≈0,8 com ~70 trocas de sinal em 70 passos e capotavam aos 1,3 s; a penalidade de taxa de ação é o
    remédio padrão). O resto da fórmula é IDÊNTICO ao v2: xy 1.0, z 1.0, v/ω_xy 0.05, bónus 1.0 com limiares
    0.05/0.05/0.10 e crash −100;
  · VENTO (física REAL): escreve-se `mjOption.wind` (vector velocidade do ar em m/s, frame MUNDO); o MuJoCo
    subtrai-o à velocidade de cada corpo e converte a diferença em força/torque pelo modelo de fluido por
    inércia — já ativo neste modelo porque o `cf2.xml` traz `<option density="1.225" viscosity="1.8e-5"/>`.
    O chão é estático (sem dofs) → imune. NÃO se usa `xfrc_applied` para o caso constante.
    ⚠ Duas convenções DIFERENTES (de propósito, para não quebrar quem já as usa):
      · `vento=(vx, vy, vz)` — CARTESIANO (frame mundo, m/s), fixo no reset: `HoverEnv(vento=(3, 0, 0))` são
        3 m/s em +x, mas `HoverEnv(vento=(3, 45, 0))` são ‖w‖ = 45,1 m/s (NÃO é polar!); exige 3 componentes
        finitas, senão `ValueError`;
      · `vento_aleatorio=(U_min, U_max)` — amostrado NO RESET: norma U ~ U[U_min, U_max] m/s, azimute
        ~ U[0, 2π) e elevação ~ U[−20°, +20°] (tudo pelo `np_random` → determinístico dada a seed);
      · `definir_vento(vel, azimute_graus, elevacao_graus=0)` — POLAR: `definir_vento(3, 45)` são 3 m/s a 45°
        (≈2,12 m/s em +x e +y) — é a forma que a UI usa. Muda o vento em runtime e LIMPA o aleatório;
      · `definir_vento_aleatorio(u_min, u_max)` — liga o currículo (amostra já uma vez) e LIMPA o constante.
    VENTO DINÂMICO (`vento_dinamico=dict | None`, por omissão `None` → NADA muda em relação ao contrato v2b):
    o vento base acima continua a ser o piso do episódio e, POR CIMA dele, atua um segundo processo FÍSICO
    escrito no MESMO `model.opt.wind` (nada de `xfrc_applied` nem forças mágicas), a partir do 1.º passo de
    decisão — é o que dá robustez a frentes/rajadas a meio do voo (o treino anterior só tinha vento
    CONSTANTE por episódio). Três modos:
      · `{"modo": "rajadas", "p": 0.02, "duracao": 10, "u_max": 3.0}` — GUST: a cada passo de decisão, com
        probabilidade `p`, começa uma rajada `u ~ U[0, u_max]` m/s (azimute ~ U[0, 2π), elevação ~ U[−20°, 20°])
        mantida `duracao` passos com o envelope `sin(π·k/(N+1))` (k = 1…N → sobe 0→u e volta a 0) aplicado à
        VELOCIDADE da rajada e SOMADA ao vento base; entre rajadas fica só o vento base. Uma rajada em curso
        não é interrompida por outra (só se sorteia quando a anterior termina — com `p=1` as rajadas ficam
        encostadas umas às outras);
      · `{"modo": "frente", "u_max": 3.0, "t_s": 2.0}` — WIND FRONT: no instante `t_s` do episódio o vento
        muda em DEGRAU para `u ~ U[0,5; u_max]` m/s (azimute ~ U[0, 2π), elevação ~ U[−20°, 20°]), que
        SUBSTITUI o vento base até ao fim do episódio (é a frente de vento apanhada em voo). O degrau entra no
        passo de decisão cujo intervalo `[t, t+0,02)` contém `t_s` (nunca a meio de um passo: o vento é
        constante dentro do passo); `t_s` tem de cair dentro do episódio, senão o passo da frente passaria de
        `max_passos` e a frente nunca chegaria (`ValueError` claro no `__init__`);
      · `{"modo": "dryden", "sigma": 0.5, "L": 10.0, "u_max": 3.0}` — TURBULÊNCIA OU de 1.ª ordem por passo
        sobre o vento base (Dryden; valores de referência do `mujoco-drones-gym`, CoALA #7979):
        `x ← α·x + σ·√(1−α²)·ξ` com `α = exp(−Δt·V/L)`, `Δt` = 0,02 s (passo de decisão), `ξ ~ N(0,1)³`
        independente por componente e `V = max(‖vento base‖, v_min)` — o piso `v_min` (1 m/s por omissão)
        existe porque com vento base NULO a escala de tempo `L/V` seria infinita (`α = 1`) e a turbulência
        congelava em zero. O vento aplicado é `base + x`, SATURADO em norma a `u_max` (o estado `x` do OU não é
        saturado, para o processo continuar a ser o da fórmula);
    `u_max` é o teto do modo dinâmico (amplitude máxima da rajada/frente ou teto de saturação da turbulência);
    `u_max = 0` é aceite e significa modo INERTE em TODOS os modos: `opt.wind` fica exatamente o vento BASE
    (a frente não faz degrau nenhum, a turbulência não entra e não se sorteia NADA do `np_random`) — é o que
    torna o estágio 0 do currículo ar parado a sério e o que mantém um run com `--vento-dinamico` bit-idêntico
    a um sem ele enquanto o teto for 0. A frente usa o piso de 0,5 m/s SÓ quando o teto o permite (com
    `0 < u_max < 0,5` a frente vale `u_max`; com `u_max = 0` não há frente).
    A config é validada com `ValueError` claro: `modo` em falta ou desconhecido, chave desconhecida
    (apanha gralhas como `durancao`), `p` fora de [0, 1], `duracao` que não seja inteiro ≥ 1, `t_s < 0`,
    `sigma`/`L`/`v_min` ≤ 0 e `u_max < 0`. `definir_vento_dinamico(config)` troca/reconfigura/desliga o modo
    em RUNTIME (mesma validação; é o que o treino usa quando o estágio do currículo sobe).
    VENTO/AÇÃO com NaN ou inf → `ValueError` com mensagem clara (nunca entram em silêncio em `opt.wind` ou
    `data.ctrl`, onde envenenariam a física); se mesmo assim o estado divergir (vento absurdo mas finito, ou
    `qpos` corrompido por fora), o `step` levanta `RuntimeError` em vez de devolver obs/recompensa NaN para
    sempre. `alvo_z` é validado em [0,10, 2,90] m (abaixo disso o bónus sairia de graça com o drone pousado
    e acima ficaria inalcançável, colado ao teto de terminação z > 3 m).
  · observação `Box(-inf, inf, (16,))` JÁ normalizada por escalas FIXAS (sem VecNormalize — o grafo do
    deploy fica puro). Ordem e escalas (ver constantes `ESCALA_*` abaixo):
      [0:3]   (p − p_alvo)/1 m        (p = sensor `posicao`, que é o CM do corpo; p_alvo = [0, 0, alvo_z])
      [3:6]   (roll, pitch, yaw)/π    (do sensor `body_quat`, quaternion MuJoCo [w x y z]; o ALVO de yaw é 0,
                                       logo `obs[5]` é o erro de guinada/π a menos do envolvimento em [−π, π])
      [6:9]   v_corpo/1 m·s⁻¹         (velocidade no frame do CORPO: R(quat)ᵀ · v_mundo)
      [9:12]  ω/10 rad·s⁻¹            (sensor `body_gyro`, frame do corpo)
      [12:16] ação anterior           (já em [-1, 1])
    `ruido_obs>0` acrescenta ruído gaussiano σ=ruido_obs à observação (treino com ruído de sensor);
  · terminação: z < 0.005 m (caiu — o piso impede z<0) ∨ max(|φ|, |θ|) > π/2 ∨ z > 3 m;
    truncagem: `episodio_s` segundos (10 s = 500 passos de decisão);
  · `reset(seed)`: `mj_resetDataKeyframe` + keyframe `hover` do lab (z = 0.1 m), MOTORES DESLIGADOS, jitter xy
    ±2 cm e yaw ±5° (determinístico dada a seed), vento ZERADO e assentamento físico no chão (SEM teleporte);
    só depois o vento do episódio é escrito em `model.opt.wind` — o drone arranca pousado e em ar parado, e a
    física decide o resto. Devolve `(obs, info)`;
  · ARRANQUE — o drone NÃO "some" aos 0 s: o episódio começa SEMPRE com o drone POUSADO no chão (assentado
    pela física, motores desligados, CM a ≈0,0125 m) e o vento do episódio (BASE + DINÂMICO) JÁ está em
    `model.opt.wind` quando o `reset` devolve, logo o 1.º passo de decisão da política é contra esse vento
    (com `frente` a `t_s = 0` a frente já lá está no 1.º passo; com `rajadas` `p = 1` a 1.ª rajada também).
    Quem levanta é a política, com comando de empuxo/momentos: não há apoio, impulso externo, teleporte nem
    "mágica" — só `mj_step` e a física do fluido do `cf2.xml`;
  · `step`/`reset` devolvem `info = {"z", "dist_xy", "v", "no_alvo", "yaw_err", "vento_vel", "vento_atual",
    "vento_azim"}` (`no_alvo` = condição do bónus; `vento_azim` em GRAUS [0, 360); `vento_vel` e `vento_atual`
    são a MESMA norma do vector de vento ATIVO em `model.opt.wind` — `vento_atual` é o alias explícito pedido
    pelo contrato do vento dinâmico, e ⚠ a PROPRIEDADE `env.vento_atual` é o VECTOR, não a norma);
  · `data.ctrl` fica em UNIDADES FÍSICAS, 1:1 com os 4 canais (`nu = nactuator = 4`): [0] empuxo em N,
    [1:4] momentos em N·m. O `cf2.xml` upstream nunca é tocado — a faixa do empuxo (`thrust_max`) e o gear
    dos momentos são ajustados SÓ na cópia em memória deste ambiente; o wrench aplicado é idêntico ao de
    `cf.carregar(momentos="fisico")` (gear × ctrl dá o mesmo torque).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import ClassVar

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
from lab import mjkit  # noqa: F401, I001  (MUJOCO_GL=egl antes de `import mujoco`: ordem de imports intencional)
from lab import crazyflie as cf  # (carregar/sensores/constantes físicas do Crazyflie 2)

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces

# ----------------------------------------------------------------------------------------- escalas da observação
ESCALA_DELTA_POS = 1.0    # m      → [0:3]   (p − p_alvo)/1 m
ESCALA_ANG = np.pi        # rad    → [3:6]   rpy/π  (≈ [-1, 1] para atitudes válidas)
ESCALA_VEL = 1.0          # m/s    → [6:9]   v_corpo/1 m·s⁻¹
ESCALA_GIRO = 10.0        # rad/s  → [9:12]  ω/10 rad·s⁻¹

# ----------------------------------------------------------------------------------------- física/limites
THRUST_MAX_REAL = 0.589   # N — datasheet CF2.1: 4 × 15 gf ≈ 0,589 N (T/W ≈ 2,2); o upstream usa 0,35 N "arbitrário"
Z_TERMINA = 0.005         # m — "caiu": o CM em repouso fica a ≈0,0125 m, logo este limiar só apanha impactos
Z_TETO = 3.0              # m — teto do episódio (subiu demais)
TILT_MAX = np.pi / 2      # rad — capotou
PENALIDADE_TERMINAL = 100.0
# faixa VÁLIDA do alvo (validada no __init__): abaixo de ALVO_Z_MIN o bónus sairia de GRAÇA — o drone em
# repouso assenta com o CM a ≈0,0125 m e o bónus só exige |z−alvo_z| < 0,05 m (logo tudo abaixo de ≈0,0625 m
# dava +1/passo com os motores desligados); acima de ALVO_Z_MAX o alvo ficaria a <0,10 m do teto de terminação.
ALVO_Z_MIN = 0.10         # m
ALVO_Z_MAX = 2.90         # m
# tetos de SANIDADE do estado (o `step` levanta `RuntimeError` fora deles): o envelope do episódio é
# z ∈ [0,005, 3] m e a aceleração líquida máxima é (thrust_max−mg)/m ≈ 12 m/s², logo um estado legítimo fica
# MUITO abaixo destes valores; acima disto há um vento absurdo (ou estado corrompido por fora) e o MuJoCo só
# avisa, devolvendo "huge values" que envenenariam o treino (e a obs estoura em float32 → inf).
SANIDADE_POS_MAX = 1.0e3  # m
SANIDADE_V_MAX = 1.0e3    # m/s
SANIDADE_OMEGA_MAX = 1.0e5  # rad/s

# ----------------------------------------------------------------------------------------- recompensa v2b
# (v2b: yaw 0.5→0.2, ω_z 0.2→0.1 e Δa 0.01→0.05 após a campanha de 20 treinos/25 M passos — o v2 tinha um
#  ATRATOR de chatter: as políticas saturavam os momentos (|a|≈0,8, ~70 trocas de sinal em 70 passos) e
#  capotavam aos 1,3 s, enquanto a política v1 pairava com |a|≈0,01.)
YAW_ALVO = 0.0            # rad — ORIENTAÇÃO FIXA: o alvo de guinada é 0 (e o reset traz jitter ±5°)
PESO_XY = 1.0             # 1/m   — −1.0·‖xy‖
PESO_Z = 1.0              # 1/m   — −1.0·|z−alvo_z|
PESO_YAW = 0.2            # 1/rad — −0.2·|yaw_err| (era 0.5: a pressão de yaw puxava correções agressivas)
PESO_V = 0.05             # s/m   — −0.05·‖v‖
PESO_OMEGA_XY = 0.05      # s/rad — −0.05·‖ω_xy‖
PESO_OMEGA_Z = 0.1        # s/rad — −0.1·|ω_z| (era 0.2)
PESO_DELTA_A = 0.05       # 1/1   — −0.05·‖Δa‖ (era 0.01: penalidade de taxa de ação contra o chatter)
BONUS_ALVO = 1.0
BONUS_XY = 0.05           # m     — raio do bónus em xy (ESTRITO)
BONUS_Z = 0.05            # m     — tolerância do bónus em z (ESTRITA)
BONUS_YAW = 0.10          # rad   — tolerância do bónus em guinada (ESTRITA)
ALVO_TOL = BONUS_XY       # m     — compatibilidade: o raio "no alvo" das peças de UI é o do bónus em xy

# ----------------------------------------------------------------------------------------- vento
VENTO_ELEV_MAX = np.radians(20.0)   # rad — elevação máxima do vento aleatório (±20°)

# vento DINÂMICO (frentes/rajadas/turbulência por cima do vento base; ver o docstring do módulo)
VENTO_DINAMICO_MODOS = ("rajadas", "frente", "dryden")
VENTO_DINAMICO_CHAVES = frozenset({"modo", "u_max", "p", "duracao", "t_s", "sigma", "L", "v_min"})
RAJADAS_P_PADRAO = 0.02           # 1/passo de decisão — probabilidade de começar uma rajada
RAJADAS_DURACAO_PADRAO = 10       # passos de decisão (0,2 s a 50 Hz) — duração da rajada
FRENTE_T_S_PADRAO = 2.0           # s — instante do episódio em que a frente chega
FRENTE_U_MIN = 0.5                # m/s — piso da amostra da frente (U[0,5; u_max] quando o teto o permite)
DRYDEN_SIGMA_PADRAO = 0.5         # m/s — desvio-padrão estacionário da turbulência
DRYDEN_L_PADRAO = 10.0            # m — escala de comprimento do Dryden
DRYDEN_V_MIN_PADRAO = 1.0         # m/s — piso de V = max(‖vento base‖, v_min) na correlação α = exp(−Δt·V/L)
VENTO_DINAMICO_U_MAX_PADRAO = 3.0  # m/s — teto do modo (amplitude da rajada/frente ou saturação da turbulência)

# jitter do reset e assentamento inicial (a queda de 9 cm do keyframe tem de terminar antes do episódio)
JITTER_XY = 0.02          # m
JITTER_YAW = np.radians(5.0)   # rad
ASSENTAR_T_MIN = 0.2      # s — só aceita "pousado" depois de largar o keyframe
ASSENTAR_Z_MAX = 0.05     # m
ASSENTAR_V = 1e-3         # m/s
ASSENTAR_QUIETOS = 10     # passos consecutivos
ASSENTAR_MAX_S = 1.0      # s — teto de segurança


# ----------------------------------------------------------------------------------------- puros (funções fechadas)
def finito(nome: str, valor) -> float:
    """Converte para `float` e EXIGE um valor finito — `ValueError` claro em vez de NaN/inf silencioso."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"`{nome}` tem de ser um número (recebido {valor!r})") from None
    if not np.isfinite(v):
        raise ValueError(f"`{nome}` tem de ser FINITO, sem NaN/inf (recebido {valor!r})")
    return v


def valida_vento_dinamico(config: dict | None) -> dict | None:
    """Valida e NORMALIZA a config do vento dinâmico (`None` = sem vento dinâmico).

    Devolve um dict NOVO, só com as chaves do modo e com os defaults preenchidos (o dict recebido nunca é
    tocado) — ou `None`. Levanta `ValueError` com mensagem clara para: config que não é dict, `modo` em falta
    ou desconhecido, chave desconhecida (apanha gralhas como `durancao`, que passariam em silêncio), valores
    não-finitos e faixas impossíveis. É usada pelo `__init__`, pelo `definir_vento_dinamico` e pelo treino
    (que valida os `--vento-dinamico-params` ANTES de criar os envs).

    `u_max = 0` é válido e significa modo INERTE (estágio 0 do currículo: ar parado, nada de dinâmica).
    """
    if config is None:
        return None
    if not isinstance(config, dict):
        raise ValueError(  # noqa: TRY004  (o contrato do experimento pede ValueError também para o tipo)
            f"`vento_dinamico` tem de ser um dict (ou None) — ex.: "
            f"{{'modo': 'rajadas', 'p': 0.02}} (recebido {config!r})")
    if "modo" not in config:
        raise ValueError(f"`vento_dinamico` precisa da chave `modo`, uma de {VENTO_DINAMICO_MODOS} "
                         f"(recebido {config!r})")
    modo = config["modo"]
    if modo not in VENTO_DINAMICO_MODOS:
        raise ValueError(f"`vento_dinamico['modo']` tem de ser um de {VENTO_DINAMICO_MODOS} (recebido {modo!r})")
    desconhecidas = set(config) - VENTO_DINAMICO_CHAVES
    if desconhecidas:
        raise ValueError(f"`vento_dinamico` tem chaves desconhecidas {sorted(desconhecidas)} — aceita "
                         f"{sorted(VENTO_DINAMICO_CHAVES)} (gralhas como `durancao` são recusadas à entrada, "
                         "em vez de ignoradas em silêncio)")
    u_max = finito("vento_dinamico['u_max']", config.get("u_max", VENTO_DINAMICO_U_MAX_PADRAO))
    if u_max < 0.0:
        raise ValueError(f"`vento_dinamico['u_max']` tem de ser ≥ 0 m/s (recebido {u_max!r}): 0 = modo inerte "
                         "(ar parado, nenhum vento dinâmico entra na física)")

    if modo == "rajadas":
        p = finito("vento_dinamico['p']", config.get("p", RAJADAS_P_PADRAO))
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"`vento_dinamico['p']` tem de estar em [0, 1] (recebido {p!r}): é a "
                             "probabilidade de começar uma rajada POR passo de decisão")
        duracao = config.get("duracao", RAJADAS_DURACAO_PADRAO)
        if isinstance(duracao, bool) or not isinstance(duracao, (int, np.integer)) or int(duracao) < 1:
            raise ValueError(f"`vento_dinamico['duracao']` tem de ser um inteiro ≥ 1 passos de decisão "
                             f"(recebido {duracao!r}): 0 não faria rajada nenhuma e um float não teria "
                             "envelope definido")
        return {"modo": modo, "u_max": u_max, "p": p, "duracao": int(duracao)}

    if modo == "frente":
        t_s = finito("vento_dinamico['t_s']", config.get("t_s", FRENTE_T_S_PADRAO))
        if t_s < 0.0:
            raise ValueError(f"`vento_dinamico['t_s']` tem de ser ≥ 0 s (recebido {t_s!r}): é o instante do "
                             "episódio em que a frente chega (0 = frente no 1.º passo de decisão)")
        return {"modo": modo, "u_max": u_max, "t_s": t_s}

    sigma = finito("vento_dinamico['sigma']", config.get("sigma", DRYDEN_SIGMA_PADRAO))
    if sigma <= 0.0:
        raise ValueError(f"`vento_dinamico['sigma']` tem de ser > 0 m/s (recebido {sigma!r}): é o "
                         "desvio-padrão estacionário da turbulência (σ = 0 seria um modo inerte)")
    L = finito("vento_dinamico['L']", config.get("L", DRYDEN_L_PADRAO))
    if L <= 0.0:
        raise ValueError(f"`vento_dinamico['L']` tem de ser > 0 m (recebido {L!r}): é a escala de comprimento "
                         "do modelo de Dryden (α = exp(−Δt·V/L))")
    v_min = finito("vento_dinamico['v_min']", config.get("v_min", DRYDEN_V_MIN_PADRAO))
    if v_min <= 0.0:
        raise ValueError(f"`vento_dinamico['v_min']` tem de ser > 0 m/s (recebido {v_min!r}): com vento base "
                         "nulo a escala de tempo L/V seria infinita (α = 1) e a turbulência congelava em zero")
    return {"modo": modo, "u_max": u_max, "sigma": sigma, "L": L, "v_min": v_min}


def quat_para_matriz(q) -> np.ndarray:
    """Matriz de rotação 3×3 do frame do corpo para o mundo, a partir do quaternion MuJoCo `[w x y z]`."""
    w, x, y, z = (float(v) for v in q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def atitude(q) -> np.ndarray:
    """(roll, pitch, yaw) em rad a partir do quaternion `[w x y z]` (convenção ZYX intrínseca do MuJoCo)."""
    w, x, y, z = (float(v) for v in q)
    return np.array([
        np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)),
        np.arcsin(np.clip(2 * (w * y - z * x), -1.0, 1.0)),
        np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)),
    ])


def envolve_pi(angulo: float) -> float:
    """Envolve um ângulo em [−π, π] (é o que a recompensa v2 faz ao yaw para obter o `yaw_err`)."""
    return float((float(angulo) + np.pi) % (2.0 * np.pi) - np.pi)


def quat_yaw(yaw: float) -> np.ndarray:
    """Quaternion `[w x y z]` de uma rotação pura de guinada (roll = pitch = 0)."""
    return np.array([np.cos(yaw / 2.0), 0.0, 0.0, np.sin(yaw / 2.0)])


def _vetor_vento_rad(vel: float, azimute_rad: float, elevacao_rad: float) -> np.ndarray:
    """Vector de vento (m/s, frame mundo) a partir de ângulos em RADIANOS (núcleo de `vetor_vento`)."""
    e, a = float(elevacao_rad), float(azimute_rad)
    return float(vel) * np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])


def vetor_vento(vel: float, azimute_graus: float, elevacao_graus: float = 0.0) -> np.ndarray:
    """Vector de vento (m/s, frame mundo) de uma velocidade, um azimute e uma elevação (em GRAUS).

    Convenção: azimute 0° → +x, 90° → +y; elevação positiva → componente +z.
    """
    return _vetor_vento_rad(vel, np.radians(float(azimute_graus)), np.radians(float(elevacao_graus)))


def azimute_graus(vento) -> float:
    """Azimute (graus, [0, 360)) do vector de vento `vento` (m/s, frame mundo); vento nulo → 0°."""
    vx, vy = float(vento[0]), float(vento[1])
    if vx == 0.0 and vy == 0.0:
        return 0.0
    return float(np.degrees(np.arctan2(vy, vx)) % 360.0)


def bonus_no_alvo(dist_xy: float, dz: float, yaw_err: float) -> bool:
    """Bónus do alvo (desigualdades ESTRITAS): ‖xy‖ < 0,05 ∧ |z−alvo_z| < 0,05 ∧ |yaw_err| < 0,10."""
    return bool(dist_xy < BONUS_XY and dz < BONUS_Z and abs(float(yaw_err)) < BONUS_YAW)


def termina(z: float, phi: float, theta: float) -> bool:
    """Terminação do episódio: caiu (z < Z_TERMINA), capotou (|roll| ou |pitch| > π/2) ou subiu demais (z > Z_TETO)."""
    return bool(z < Z_TERMINA or z > Z_TETO or max(abs(phi), abs(theta)) > TILT_MAX)


def recompensa(x: float, y: float, z: float, v: float, yaw_err: float, omega_xy, omega_z: float,
               delta_a, terminado: bool, alvo_z: float) -> float:
    """Recompensa v2 do passo de decisão (fórmula no docstring do módulo) — pura, sem estado.

    `x, y, z` em m (mundo) · `v` = ‖v‖ em m/s · `yaw_err` em rad JÁ envolvido em [−π, π] (alvo 0) ·
    `omega_xy` (2,) e `omega_z` em rad/s no frame do CORPO · `delta_a` = ação atual − ação anterior (4 canais).
    """
    d = float(np.hypot(x, y))
    dz = abs(float(z) - float(alvo_z))
    r = (-PESO_XY * d - PESO_Z * dz - PESO_YAW * abs(float(yaw_err)) - PESO_V * abs(float(v))
         - PESO_OMEGA_XY * float(np.linalg.norm(np.asarray(omega_xy, dtype=float)))
         - PESO_OMEGA_Z * abs(float(omega_z))
         - PESO_DELTA_A * float(np.linalg.norm(np.asarray(delta_a, dtype=float))))
    if bonus_no_alvo(d, dz, yaw_err):
        r += BONUS_ALVO
    if terminado:
        r -= PENALIDADE_TERMINAL
    return float(r)


# ----------------------------------------------------------------------------------------- ambiente
class HoverEnv(gym.Env):
    """Drone trava-se em (0, 0, alvo_z) com yaw = 0 e aguenta o vento — ambiente Gymnasium headless."""

    metadata: ClassVar[dict] = {"render_modes": []}

    def __init__(self, alvo_z: float = 1.0, decimation: int = 10, thrust_realista: bool = True,
                 tau_escala: float = 0.1, ruido_obs: float = 0.0, episodio_s: float = 10.0,
                 vento: tuple[float, float, float] | None = None,
                 vento_aleatorio: tuple[float, float] | None = None,
                 vento_dinamico: dict | None = None,
                 render_mode: str | None = None):
        """Cria o ambiente (contrato, recompensa v2 e vento no docstring do módulo).

        `vento=(vx, vy, vz)` é um vector CARTESIANO (frame mundo, m/s) fixo no reset — `vento=(3, 0, 0)` são
        3 m/s em +x (NÃO é polar: para 3 m/s a 45° use `definir_vento(3, 45)`); `vento_aleatorio=(U_min, U_max)`
        liga o currículo de vento amostrado no reset — são mutuamente exclusivos.

        `vento_dinamico={"modo": "rajadas"|"frente"|"dryden", …}` acrescenta vento DINÂMICO por cima do vento
        base (rajadas com envelope, frente de vento em degrau ou turbulência OU de Dryden) — os três modos, as
        fórmulas e os defaults estão no docstring do módulo e a validação é feita por `valida_vento_dinamico`
        (por omissão `None`: nada muda em relação ao contrato v2b).

        Levanta `ValueError` se `decimation` não for um inteiro ≥ 1 (é o nº de passos de física por passo de
        decisão — 0 deixaria `dt_decisao` a zero), se `episodio_s` ≤ 0, se `alvo_z` for não-finito ou estiver
        fora de [ALVO_Z_MIN, ALVO_Z_MAX] (abaixo o bónus sairia de graça com o drone pousado; acima o alvo
        ficaria inalcançável, colado ao teto), se vierem `vento` e `vento_aleatorio` ao mesmo tempo, se
        `vento` não tiver 3 componentes finitas, se as faixas de vento forem inválidas (não-finitas, negativas
        ou U_min > U_max) ou se a config do vento dinâmico for inválida (ver `valida_vento_dinamico`); com
        `modo="frente"`, se o passo da frente passar de `max_passos` (a frente nunca chegaria a entrar).
        """
        super().__init__()
        if isinstance(decimation, bool) or not isinstance(decimation, (int, np.integer)):
            raise ValueError(  # noqa: TRY004  (o contrato do experimento pede ValueError também para o tipo)
                f"decimation tem de ser um inteiro ≥ 1 (recebido {decimation!r}): é o número de "
                "passos de física (500 Hz) por passo de decisão da política")
        if int(decimation) < 1:
            raise ValueError(f"decimation tem de ser ≥ 1 (recebido {decimation!r}): com 0 não há passos de "
                             "física por decisão e `dt_decisao` seria 0 s")
        if float(episodio_s) <= 0.0:
            raise ValueError(f"episodio_s tem de ser > 0 s (recebido {episodio_s!r})")
        if vento is not None and vento_aleatorio is not None:
            raise ValueError("`vento` (constante) e `vento_aleatorio` (currículo) são exclusivos: escolha um")
        alvo_z = finito("alvo_z", alvo_z)
        if not ALVO_Z_MIN <= alvo_z <= ALVO_Z_MAX:
            raise ValueError(
                f"alvo_z tem de estar em [{ALVO_Z_MIN}, {ALVO_Z_MAX}] m (recebido {alvo_z!r}): abaixo de "
                f"{ALVO_Z_MIN} m o bónus sairia de graça — o drone em repouso assenta com o CM a ≈0,0125 m e o "
                f"bónus só pede |z−alvo_z| < {BONUS_Z} m — e acima de {ALVO_Z_MAX} m o alvo fica a menos de "
                f"0,10 m do teto de terminação (z > {Z_TETO} m)")
        self.alvo_z = alvo_z
        self.decimation = int(decimation)
        self.tau_escala = float(tau_escala)
        self.ruido_obs = float(ruido_obs)
        self.episodio_s = float(episodio_s)
        self.render_mode = render_mode          # NÃO há render: o parâmetro existe só por compatibilidade Gymnasium
        self.vento_dinamico = valida_vento_dinamico(vento_dinamico)   # dict normalizado (ou None → nada muda)

        # modelo do menagerie + sensores da camada lab/ (keyframe `hover`: z=0,1 m e ctrl = peso)
        self.model, self.data = cf.carregar()
        self.dt = float(self.model.opt.timestep)              # 0.002 s (500 Hz, RK4)
        self.dt_decisao = self.dt * self.decimation           # 0.02 s (50 Hz)
        self.max_passos = max(1, round(self.episodio_s / self.dt_decisao))
        self.alvo = np.array([0.0, 0.0, self.alvo_z])
        if (self.vento_dinamico is not None and self.vento_dinamico["modo"] == "frente"
                and self._passo_da_frente(self.vento_dinamico["t_s"]) > self.max_passos):
            raise ValueError(
                f"`vento_dinamico['t_s']` = {self.vento_dinamico['t_s']!r} s cai fora do episódio: a frente "
                f"entraria no passo de decisão {self._passo_da_frente(self.vento_dinamico['t_s'])} e o "
                f"episódio só tem {self.max_passos} passos ({self.episodio_s:g} s / {self.dt_decisao:g} s) — "
                "a frente nunca chegaria a atuar (baixe `t_s` ou aumente `episodio_s`)")

        # peso total do MODELO (nada hardcoded): Σm · |g| = 0,027 · 9,81 = 0,26487 N
        self.massa = float(self.model.body_mass.sum())
        self.gravidade = abs(float(self.model.opt.gravity[2]))
        self.mg = self.massa * self.gravidade
        self.thrust_max = THRUST_MAX_REAL if thrust_realista else float(cf.EMPUXO_MAX)

        # faixas FÍSICAS dos canais, em runtime e só nesta cópia do modelo (o XML em disco fica intacto):
        # empuxo 0..thrust_max N (gear do canal é 1) e momentos ±momento_max N·m (gear do lab → 1, ctrl = N·m)
        aid = self.model.actuator("body_thrust").id
        self.model.actuator_ctrlrange[aid] = (0.0, self.thrust_max)
        self.momento_max = np.asarray(cf.MOMENTOS_MAX, dtype=float).copy()
        for i, nome in enumerate(cf.MOTORES[1:]):
            aid = self.model.actuator(nome).id
            self.model.actuator_gear[aid, 3 + i] = 1.0
            self.model.actuator_ctrlrange[aid] = (-self.momento_max[i], self.momento_max[i])

        self.keyframe = self.model.key("hover").id
        self.passos = 0
        self.acao_anterior = np.zeros(4, dtype=np.float32)

        # vento: config do episódio (o `model.opt.wind` só é escrito no reset / nos `definir_*`)
        self.vento: tuple[float, float, float] | None = None
        self.vento_aleatorio: tuple[float, float] | None = None
        self._base_vento = np.zeros(3)      # vento BASE do episódio (constante ou amostrado do currículo)
        # estado do vento DINÂMICO (só é usado quando `vento_dinamico is not None` — o caminho por omissão
        # nunca chama `_passo_vento`, logo o comportamento sem vento dinâmico fica bit-idêntico ao v2b)
        self._din_passo = 0                 # passo de decisão cujo vento está em `opt.wind` (0 = nenhum)
        self._rajada_k = 0                  # passo dentro da rajada (0 = sem rajada ativa)
        self._rajada_n = 0                  # duração da rajada em curso (0 = sem rajada)
        self._rajada_vec = np.zeros(3)      # vector da rajada a amplitude cheia (o envelope escala-o)
        self._turb = np.zeros(3)            # estado x do OU de Dryden (m/s)
        self._frente_passo = 1              # passo de decisão em que a frente entra (1-based)
        self._frente_vec = np.zeros(3)      # vector da frente (degrau)
        if vento is not None:
            self.definir_vento(*self._vento_em_polar(vento))
        elif vento_aleatorio is not None:
            self.definir_vento_aleatorio(*vento_aleatorio)
        else:
            self.model.opt.wind[:] = 0.0
            self._base_vento[:] = 0.0
        if self.vento_dinamico is not None:
            self._reinicia_dinamico()       # plano do episódio (frente amostrada, rajada/turbulência a zero)

        self.action_space = spaces.Box(-1.0, 1.0, (4,), dtype=np.float32)
        self.observation_space = spaces.Box(-np.inf, np.inf, (16,), dtype=np.float32)

    # ------------------------------------------------------------------ vento
    @staticmethod
    def _vento_em_polar(v) -> tuple[float, float, float]:
        """(velocidade, azimute em graus, elevação em graus) de um vector CARTESIANO de vento (m/s, mundo).

        `ValueError` claro se `v` não tiver exactamente 3 componentes finitas (em vez do erro opaco de forma
        do NumPy, ou de um vento NaN a entrar em silêncio em `model.opt.wind`).
        """
        try:
            w = np.asarray(v, dtype=float).reshape(-1)
        except (TypeError, ValueError):
            raise ValueError(f"`vento` tem de ser um vector de 3 componentes (recebido {v!r})") from None
        if w.shape != (3,):
            raise ValueError(f"`vento` tem de ter 3 componentes — (vx, vy, vz) em m/s no frame mundo "
                             f"(recebido {v!r})")
        if not np.isfinite(w).all():
            raise ValueError(f"`vento` tem de ter 3 componentes FINITAS, sem NaN/inf (recebido {v!r})")
        vel = float(np.linalg.norm(w))
        if vel == 0.0:
            return 0.0, 0.0, 0.0
        elev = float(np.degrees(np.arcsin(np.clip(w[2] / vel, -1.0, 1.0))))
        return vel, azimute_graus(w), elev

    @property
    def vento_atual(self) -> np.ndarray:
        """Cópia do vector de vento ATIVO (m/s, frame mundo) — é o que está em `model.opt.wind`."""
        return np.array(self.model.opt.wind, dtype=float)

    def _escreve_vento(self, vel: float, azimute_rad: float, elevacao_rad: float) -> np.ndarray:
        """Escreve `model.opt.wind = vel·[cos e·cos a, cos e·sin a, sin e]` (rad) e devolve o vector escrito."""
        return self._escreve_vento_vetor(_vetor_vento_rad(vel, azimute_rad, elevacao_rad))

    def _escreve_vento_vetor(self, v) -> np.ndarray:
        """Escreve um VECTOR de vento (m/s, frame mundo) em `model.opt.wind` e devolve-o.

        É o ponto único de escrita do vento (o `vento_dinamico` entra por aqui, somado ao vento base): o MuJoCo
        converte a velocidade relativa de cada corpo em força/torque pelo modelo de fluido — nada de
        `xfrc_applied`, nada de "mágica".
        """
        self.model.opt.wind[:] = np.asarray(v, dtype=float).reshape(3)
        return self.vento_atual

    def definir_vento(self, vel: float, azimute_graus: float, elevacao_graus: float = 0.0) -> np.ndarray:
        """Vento CONSTANTE em POLAR: `vel` (m/s) e os ângulos em GRAUS → `model.opt.wind` (frame mundo).

        Exemplo: `definir_vento(3, 45)` são 3 m/s a 45° de azimute (≈2,12 m/s em +x e +y) — é a convenção da
        UI. Não confundir com o argumento `vento=(vx, vy, vz)` do `__init__`, que é CARTESIANO.

        Exige `vel ≥ 0` e os três valores FINITOS (`ValueError`); desliga o currículo
        (`vento_aleatorio = None`), ficando o vento fixo até nova chamada. Devolve o vector escrito.
        """
        vel, azimute_graus, elevacao_graus = (finito("vel", vel), finito("azimute_graus", azimute_graus),
                                              finito("elevacao_graus", elevacao_graus))
        if vel < 0.0:
            raise ValueError(f"`vel` tem de ser ≥ 0 m/s (recebido {vel!r})")
        v = self._escreve_vento(vel, np.radians(azimute_graus), np.radians(elevacao_graus))
        self.vento = (float(v[0]), float(v[1]), float(v[2]))
        self.vento_aleatorio = None
        self._base_vento = np.array(v, dtype=float)     # o vento dinâmico soma-se a ESTE vector
        return v

    def definir_vento_aleatorio(self, u_min: float, u_max: float) -> np.ndarray:
        """Currículo de vento: U ~ U[u_min, u_max] m/s, reamostrado em cada `reset` (pelo `np_random`).

        Amostra já um vento (para o episódio em curso ficar coerente), desliga o vento constante e devolve o
        vector amostrado. Azimute ~ U[0, 2π) e elevação ~ U[−20°, +20°]. Os limites têm de ser FINITOS e
        satisfazer 0 ≤ u_min ≤ u_max (`ValueError`).
        """
        u_min, u_max = finito("u_min", u_min), finito("u_max", u_max)
        if u_min < 0.0 or u_max < u_min:
            raise ValueError(f"faixa de vento inválida: precisa 0 ≤ u_min ≤ u_max (recebido {u_min!r}, {u_max!r})")
        self.vento = None
        self.vento_aleatorio = (u_min, u_max)
        return self._amostra_vento()

    def _amostra_vento(self) -> np.ndarray:
        """Amostra um vento do currículo pelo `np_random` (ordem fixa: norma, azimute, elevação)."""
        if self.vento_aleatorio is None:
            return self.vento_atual
        u_min, u_max = self.vento_aleatorio
        vel = float(self.np_random.uniform(u_min, u_max))
        azimute = float(self.np_random.uniform(0.0, 2.0 * np.pi))
        elevacao = float(self.np_random.uniform(-VENTO_ELEV_MAX, VENTO_ELEV_MAX))
        v = self._escreve_vento(vel, azimute, elevacao)
        self._base_vento = np.array(v, dtype=float)     # vento BASE do episódio (o dinâmico soma-se-lhe)
        return v

    # ------------------------------------------------------------------ vento dinâmico
    def _passo_da_frente(self, t_s: float) -> int:
        """Passo de decisão (1-based) em que a frente entra: o 1.º cujo intervalo `[t, t+dt)` contém `t_s`.

        `k = floor(t_s/Δt + 1e-9) + 1` com Δt = `dt_decisao` (0,02 s): o vento é constante DENTRO do passo,
        logo o degrau entra no passo que contém o instante `t_s` (e, se `t_s` cair exatamente numa fronteira,
        no passo que começa nesse instante). `t_s = 0` → passo 1 (a frente já atua no 1.º passo de decisão).
        """
        return int(np.floor(float(t_s) / self.dt_decisao + 1e-9)) + 1

    def _sorteia_frente(self) -> np.ndarray:
        """Amostra a frente pelo `np_random`: `u ~ U[min(0,5; u_max), u_max]`, azimute U[0, 2π), elevação ±20°.

        O piso de 0,5 m/s (`FRENTE_U_MIN`) só se aplica quando o teto o permite; com `0 < u_max < 0,5` a frente
        vale `u_max`. Com `u_max = 0` o modo é INERTE: devolve o vector nulo e NÃO consome o `np_random` (não
        há degrau nenhum — o `opt.wind` fica o vento base, ver `_passo_vento`).
        """
        cfg = self.vento_dinamico
        u_max = float(cfg["u_max"])
        if u_max == 0.0:
            return np.zeros(3)
        u = float(self.np_random.uniform(min(FRENTE_U_MIN, u_max), u_max))
        azimute = float(self.np_random.uniform(0.0, 2.0 * np.pi))
        elevacao = float(self.np_random.uniform(-VENTO_ELEV_MAX, VENTO_ELEV_MAX))
        return _vetor_vento_rad(u, azimute, elevacao)

    def _reinicia_dinamico(self) -> None:
        """Reinicia o estado do vento dinâmico no passo ATUAL do episódio (não toca no vento base).

        O relógio da dinâmica (`_din_passo`) arranca nos passos já decorridos, para o agendamento da frente
        continuar a usar o tempo do EPISÓDIO mesmo quando isto é chamado a meio (troca de modo/`u_max` pelo
        treino). A frente é reamostrada aqui; a turbulência arranca em `x = 0` (cresce até σ ao longo do
        episódio, na escala L/V — arranque calmo e determinístico) e não há rajada em curso.
        """
        self._din_passo = int(self.passos)
        self._rajada_k = 0
        self._rajada_n = 0
        self._rajada_vec = np.zeros(3)
        self._turb = np.zeros(3)
        self._frente_passo = 1
        self._frente_vec = np.zeros(3)
        if self.vento_dinamico is not None and self.vento_dinamico["modo"] == "frente":
            self._frente_passo = self._passo_da_frente(self.vento_dinamico["t_s"])
            self._frente_vec = self._sorteia_frente()

    def definir_vento_dinamico(self, config: dict | None) -> dict | None:
        """Liga/reconfigura/desliga o vento dinâmico em RUNTIME (mesma validação do `__init__`).

        Trocar de modo (ou ligar/desligar) re-planeia o RESTO do episódio: a frente é reamostrada e a
        rajada/turbulência recomeçam no passo de decisão seguinte (o vento já escrito para este passo mantém-se
        até lá). Manter o mesmo modo só troca os parâmetros — é o que o treino faz quando o estágio do
        currículo sobe (`u_max` novo): a rajada em curso, a turbulência e uma frente já chegada continuam, e
        uma frente ainda não chegada é reamostrada com o teto novo. Com `u_max = 0` o modo fica inerte (o
        `opt.wind` volta/fica no vento base, sem degrau nem turbulência e sem consumir o `np_random`).
        Devolve a config NORMALIZADA (ou `None`).
        """
        novo = valida_vento_dinamico(config)
        antigo = self.vento_dinamico
        mudou_modo = ((novo is None) != (antigo is None)
                      or (novo is not None and antigo is not None and novo["modo"] != antigo["modo"]))
        self.vento_dinamico = novo
        if novo is None:
            if antigo is not None:
                self._escreve_vento_vetor(self._base_vento)     # volta ao vento base, sem dinâmica
            return None
        if mudou_modo:
            self._reinicia_dinamico()
            self._passo_vento()                                 # o vento do próximo passo já é o dinâmico
        elif novo["modo"] == "frente" and self.passos + 1 < self._frente_passo:
            self._frente_vec = self._sorteia_frente()           # a frente ainda não chegou: teto novo
        return novo

    def _passo_vento(self) -> None:
        """Escreve em `model.opt.wind` o vento do passo de decisão que agora começa (BASE + dinâmico).

        Chamado UMA vez por passo de decisão: no fim do `reset` (passo 1, logo o arranque já é contra o vento)
        e no início de cada `step` — a guarda em `step` evita repetir o passo já aplicado.

        `u_max = 0` é o único caso de INÉRTEZ e é tratado AQUI, antes de qualquer modo: fica exatamente o
        vento base em `opt.wind` e NÃO se sorteia nada do `np_random` (nem rajada, nem frente, nem ξ da
        turbulência) — é o que faz o estágio 0 do currículo ser mesmo ar parado e o que mantém o run com
        vento dinâmico bit-idêntico a um run sem ele enquanto o teto for 0.
        """
        self._din_passo += 1
        cfg = self.vento_dinamico
        if cfg is None or float(cfg["u_max"]) == 0.0:
            self._escreve_vento_vetor(self._base_vento)
            return
        if cfg["modo"] == "rajadas":
            self._passo_rajada(cfg)
        elif cfg["modo"] == "frente":
            self._escreve_vento_vetor(self._frente_vec if self._din_passo >= self._frente_passo
                                      else self._base_vento)
        else:
            self._passo_dryden(cfg)

    def _passo_rajada(self, cfg: dict) -> None:
        """GUST: sorteia uma rajada com prob. `p` e aplica o envelope `sin(π·k/(N+1))` sobre o vento base."""
        if self._rajada_k >= self._rajada_n:                    # nenhuma rajada ativa → sorteia
            self._rajada_k = 0
            self._rajada_n = 0                                  # limpa a duração antiga (senão re-aplicava-a)
            if float(self.np_random.random()) < cfg["p"]:
                u = float(self.np_random.uniform(0.0, cfg["u_max"]))
                azimute = float(self.np_random.uniform(0.0, 2.0 * np.pi))
                elevacao = float(self.np_random.uniform(-VENTO_ELEV_MAX, VENTO_ELEV_MAX))
                self._rajada_vec = _vetor_vento_rad(u, azimute, elevacao)
                self._rajada_n = int(cfg["duracao"])
        if self._rajada_k < self._rajada_n:                     # rajada ativa: envelope 0→u→0
            self._rajada_k += 1
            env = float(np.sin(np.pi * self._rajada_k / (self._rajada_n + 1.0)))
            self._escreve_vento_vetor(self._base_vento + self._rajada_vec * env)
        else:                                                   # entre rajadas: fica o vento base
            self._escreve_vento_vetor(self._base_vento)

    def _passo_dryden(self, cfg: dict) -> None:
        """Turbulência OU por passo: `x ← α·x + σ·√(1−α²)·ξ`, `α = exp(−Δt·V/L)`, `V = max(‖base‖, v_min)`.

        O vento aplicado é `base + x`, saturado em NORMA a `u_max` quando há teto (`u_max > 0`; o estado `x`
        do OU não é saturado, para o processo continuar a ser exatamente o da fórmula). Com `u_max = 0` este
        método NÃO é chamado (o `_passo_vento` trata a inércia antes de escolher o modo).
        """
        v_ref = max(float(np.linalg.norm(self._base_vento)), float(cfg["v_min"]))
        alpha = float(np.exp(-self.dt_decisao * v_ref / float(cfg["L"])))
        xi = self.np_random.normal(0.0, 1.0, 3)
        self._turb = alpha * self._turb + float(cfg["sigma"]) * float(np.sqrt(1.0 - alpha * alpha)) * xi
        total = self._base_vento + self._turb
        norma = float(np.linalg.norm(total))
        u_max = float(cfg["u_max"])
        if u_max > 0.0 and norma > u_max:
            total = total * (u_max / norma)
        self._escreve_vento_vetor(total)

    # ------------------------------------------------------------------ ação → atuadores
    def _acao_valida(self, acao) -> np.ndarray:
        """Ação → vector (4,) em [-1, 1]; `ValueError` se não tiver 4 componentes FINITAS.

        Um NaN/inf aqui envenenaria `data.ctrl` e a física (o MuJoCo só avisa e o `step` passaria a devolver
        obs/recompensa NaN para sempre) — logo é recusado à entrada, como as restantes guardas. Valores
        finitos fora de [-1, 1] continuam a ser CORTADOS (comportamento documentado do contrato).
        """
        try:
            a = np.asarray(acao, dtype=float).reshape(-1)
        except (TypeError, ValueError):
            raise ValueError(f"ação tem de ser um vector de 4 valores em [-1, 1] (recebido {acao!r})") from None
        if a.shape != (4,):
            raise ValueError(f"ação tem de ter 4 componentes [empuxo, mx, my, mz] (recebido {acao!r})")
        if not np.isfinite(a).all():
            raise ValueError(f"ação tem de ter 4 componentes FINITAS, sem NaN/inf (recebido {acao!r})")
        return np.clip(a, -1.0, 1.0)

    def acao_para_ctrl(self, acao) -> tuple[float, np.ndarray]:
        """Ação [-1,1]⁴ → comando físico (empuxo N, momentos N·m), já cortado às faixas dos canais."""
        a = self._acao_valida(acao)
        if a[0] <= 0.0:                                   # metade inferior: 0 N (a₀=-1) .. mg (a₀=0 = hover)
            empuxo = self.mg * (1.0 + a[0])
        else:                                             # metade superior: mg .. thrust_max (a₀=+1)
            empuxo = self.mg + (self.thrust_max - self.mg) * a[0]
        empuxo = float(np.clip(empuxo, 0.0, self.thrust_max))
        momentos = self.tau_escala * self.momento_max * a[1:]
        momentos = np.clip(momentos, -self.momento_max, self.momento_max)
        return empuxo, momentos

    def aplicar_acao(self, acao) -> tuple[float, np.ndarray]:
        """Escreve `data.ctrl[:] = [empuxo, mx, my, mz]` (unidades físicas; `nu = nactuator = 4` → 1:1)."""
        empuxo, momentos = self.acao_para_ctrl(acao)
        self.data.ctrl[:] = (empuxo, momentos[0], momentos[1], momentos[2])
        return empuxo, momentos

    # ------------------------------------------------------------------ estado → observação
    def observacao(self) -> np.ndarray:
        """Observação (16,) normalizada por escalas fixas; `ruido_obs>0` injeta ruído gaussiano σ=ruido_obs."""
        pos = self.data.sensor("posicao").data            # m, mundo (site `cm` = CM do corpo)
        quat = self.data.sensor("body_quat").data         # [w x y z]
        giro = self.data.sensor("body_gyro").data         # rad/s, frame do corpo
        rpy = atitude(quat)
        v_corpo = quat_para_matriz(quat).T @ self.data.qvel[:3]   # v do corpo (mundo → corpo; junta livre)
        obs = np.concatenate(((pos - self.alvo) / ESCALA_DELTA_POS,
                              rpy / ESCALA_ANG,
                              v_corpo / ESCALA_VEL,
                              giro / ESCALA_GIRO,
                              self.acao_anterior))
        if self.ruido_obs > 0.0:
            obs = obs + self.np_random.normal(0.0, self.ruido_obs, obs.shape)
        return obs.astype(np.float32)

    def _derivados(self) -> dict:
        """Quantidades derivadas do estado ATUAL (chamar depois de `mj_forward`): sensores, yaw_err e vento."""
        pos = self.data.sensor("posicao").data
        x, y, z = (float(v) for v in pos)
        phi, theta, yaw = (float(v) for v in atitude(self.data.sensor("body_quat").data))
        d = float(np.hypot(x, y))
        dz = abs(z - self.alvo_z)
        yaw_err = envolve_pi(yaw - YAW_ALVO)
        return {"x": x, "y": y, "z": z, "phi": phi, "theta": theta, "yaw": yaw,
                "yaw_err": yaw_err, "dist_xy": d, "dz": dz,
                "v": float(np.linalg.norm(self.data.sensor("vel").data)),
                "omega": np.array(self.data.sensor("body_gyro").data, dtype=float)}

    def _info(self, d: dict | None = None) -> dict:
        """`info` do reset/step (as 8 chaves do contrato) a partir do estado atual.

        `vento_vel` e `vento_atual` são a MESMA grandeza (norma do vector ATIVO em `model.opt.wind`): `vento_vel`
        é o nome histórico do contrato v2b e `vento_atual` o alias explícito do contrato do vento dinâmico.
        ⚠ A propriedade `env.vento_atual` devolve o VECTOR (m/s); a chave `info["vento_atual"]` é a NORMA.
        """
        d = self._derivados() if d is None else d
        vento = self.vento_atual
        norma = float(np.linalg.norm(vento))
        return {"z": d["z"], "dist_xy": d["dist_xy"], "v": d["v"],
                "no_alvo": bonus_no_alvo(d["dist_xy"], d["dz"], d["yaw_err"]),
                "yaw_err": d["yaw_err"], "vento_vel": norma, "vento_atual": norma,
                "vento_azim": azimute_graus(vento)}

    # ------------------------------------------------------------------ API Gymnasium
    def reset(self, *, seed: int | None = None, options: dict | None = None):
        """Repõe o drone POUSADO no chão com jitter xy ±2 cm e yaw ±5°, e fixa o vento do episódio.

        O assentamento corre em AR PARADO (`opt.wind = 0`) e só no fim é que o vento do episódio (constante
        ou amostrado do currículo pelo `np_random`) é escrito — assim o arranque é sempre determinístico. Com
        vento dinâmico, o plano do episódio é reamostrado e o vento do 1.º passo de decisão (base + dinâmico)
        fica JÁ aplicado quando o `reset` devolve: a política arranca pousada e tem de levantar contra o vento.
        """
        super().reset(seed=seed)
        mujoco.mj_resetDataKeyframe(self.model, self.data, self.keyframe)
        self.data.ctrl[:] = 0.0                           # motores DESLIGADOS (o keyframe do lab traz ctrl = peso)
        self.data.qpos[0] += float(self.np_random.uniform(-JITTER_XY, JITTER_XY))
        self.data.qpos[1] += float(self.np_random.uniform(-JITTER_XY, JITTER_XY))
        self.data.qpos[3:7] = quat_yaw(float(self.np_random.uniform(-JITTER_YAW, JITTER_YAW)))
        self.model.opt.wind[:] = 0.0                      # o assentamento é em ar parado
        mujoco.mj_forward(self.model, self.data)
        self._assentar()                                  # a física decide: cai ~9 cm e fica pousado
        if self.vento_aleatorio is not None:
            self._amostra_vento()                         # vento do episódio (determinístico dada a seed)
        elif self.vento is not None:
            self.model.opt.wind[:] = self.vento
            self._base_vento = np.array(self.vento, dtype=float)
        else:
            self.model.opt.wind[:] = 0.0                  # vento=None → ar parado (o `opt.wind` não fica sujo)
            self._base_vento[:] = 0.0
        self.data.time = 0.0                              # tempo do episódio começa em 0 (nada aqui depende de t)
        self.passos = 0
        self.acao_anterior = np.zeros(4, dtype=np.float32)   # ctrl efetivo no reset = 0
        if self.vento_dinamico is not None:
            self._reinicia_dinamico()      # frente reamostrada / rajada e turbulência a zero, relógio no 0
            self._passo_vento()            # vento (base + dinâmico) do 1.º passo de decisão JÁ aplicado
        return self.observacao(), self._info()

    def step(self, acao):
        """Aplica a ação, roda `decimation` passos de física (0,02 s) e devolve (obs, r, terminated, truncated, info).

        Com vento dinâmico, o vento do passo de decisão que agora começa é escrito ANTES dos passos de física
        (base + rajada/frente/turbulência), uma única vez por passo.
        `ValueError` se a ação não tiver 4 componentes finitas (nunca se escreve NaN/inf em `data.ctrl`) e
        `RuntimeError` se, depois da física, o estado tiver divergido para NaN/inf — em vez de devolver
        obs/recompensa NaN com `terminated=False` para sempre (chame `reset()` antes de continuar).
        """
        a = self._acao_valida(acao)
        delta_a = a - self.acao_anterior.astype(float)    # ‖Δa‖ da recompensa v2 (suavidade)
        self.aplicar_acao(a)
        if self.vento_dinamico is not None and self._din_passo < self.passos + 1:
            self._passo_vento()                           # vento do passo de decisão que agora começa
        for _ in range(self.decimation):
            mujoco.mj_step(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)          # derivados/sensores consistentes com o estado integrado
        self.passos += 1
        self.acao_anterior = a.astype(np.float32)

        d = self._derivados()
        sanidade = (d["x"], d["y"], d["z"], d["v"], *d["omega"])
        if not np.isfinite(sanidade).all() or (abs(d["x"]) > SANIDADE_POS_MAX or abs(d["y"]) > SANIDADE_POS_MAX
                                               or abs(d["z"]) > SANIDADE_POS_MAX or d["v"] > SANIDADE_V_MAX
                                               or float(np.abs(d["omega"]).max()) > SANIDADE_OMEGA_MAX):
            raise RuntimeError(  # nunca devolver NaN/garbage em silêncio (o MuJoCo só avisa no stderr)
                f"simulação DIVERGIU: estado fora da sanidade após {self.decimation} passos de física "
                f"(p = ({d['x']!r}, {d['y']!r}, {d['z']!r}) m, ‖v‖ = {d['v']!r} m/s, "
                f"‖ω‖∞ = {float(np.abs(d['omega']).max())!r} rad/s, vento = {self.vento_atual!r} m/s) — a "
                "física deixou de ter sentido (vento absurdo, ainda que finito, ou estado corrompido por "
                "fora); chame reset() antes de continuar e, se a causa for o vento, use definir_vento com um "
                "valor são ANTES do reset (um reset sozinho reescreve o mesmo vento e diverge outra vez; um "
                "NaN silencioso envenenaria o treino)")
        terminado = termina(d["z"], d["phi"], d["theta"])
        r = recompensa(d["x"], d["y"], d["z"], d["v"], d["yaw_err"], d["omega"][:2], d["omega"][2],
                       delta_a, terminado, self.alvo_z)
        truncado = bool(self.passos >= self.max_passos)
        return self.observacao(), float(r), bool(terminado), truncado, self._info(d)

    def close(self) -> None:
        """Nada a libertar (sem render, sem threads, sem ficheiros)."""
        return

    # ------------------------------------------------------------------ interno
    def _assentar(self) -> None:
        """Passos de física com motores desligados até o drone pousar.

        O keyframe `hover` do lab está a z = 0,1 m; a queda de 9 cm bate no chão e, no impacto, o CM desce
        transitoriamente a ≈0,0035 m (< Z_TERMINA) — sem este assentamento o episódio terminava logo no
        primeiro instante. Critério: |v| < 1 mm/s e z < 5 cm durante 10 passos consecutivos (teto de 1 s).
        """
        quietos = 0
        for _ in range(int(ASSENTAR_MAX_S / self.dt)):
            mujoco.mj_step(self.model, self.data)
            mujoco.mj_forward(self.model, self.data)
            z = float(self.data.sensor("posicao").data[2])
            v = float(np.linalg.norm(self.data.sensor("vel").data))
            if self.data.time >= ASSENTAR_T_MIN and z < ASSENTAR_Z_MAX and v < ASSENTAR_V:
                quietos += 1
                if quietos >= ASSENTAR_QUIETOS:
                    return
            else:
                quietos = 0
