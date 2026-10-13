"""experiments/09_drone_hover_rl/vento_natural.py — VENTO com TRÊS botões: ligar · intensidade · aleatoriedade.

Pedido do dono (2026-10-12): «refaça a questão do vento onde eu posso LIGAR, definir a INTENSIDADE e a
ALEATORIEDADE ativar ou não». Este módulo é o GERADOR desse vento — puro (só NumPy), determinístico pela
semente e independente do runner — para a interface (`sim_view.py`), os testes e qualquer harness de
avaliação/treino usarem EXATAMENTE o mesmo vento:

    gerador = VentoNatural(semente=0)
    gerador.definir(ligado=True, intensidade=3.0, aleatorio=True, direcao=45.0)
    vec = gerador.passo(dt)                     # [vx, vy, vz] m/s (frame mundo) deste passo de decisão
    env.definir_vento(*polar_do_vetor(vec))     # a física recebe-o em `opt.wind` (arrasto do MuJoCo)

O QUE CADA BOTÃO FAZ
  · `ligado=False`            → o vento desce a 0 (rampa suave) e fica em 0;
  · `intensidade` W (m/s)     → a velocidade MÉDIA do vento, vinda de `direcao` (azimute em graus, a
                                convenção do `env.definir_vento`: 0° sopra para +x, 90° para +y);
  · `aleatorio=False`         → vento CONSTANTE: exatamente W na direção escolhida;
  · `aleatorio=True`          → vento «de verdade»: a MESMA média W, mais três fenómenos sobrepostos,
                                todos proporcionais a W (com W = 0 não há nada):
      1. TURBULÊNCIA contínua (forma Dryden, processo de Ornstein–Uhlenbeck por eixo no referencial do
         vento): σ_u = σ_v = 0,20·W (ao longo e de lado) e σ_w = 0,10·W (vertical), com escalas
         L_h = 8 m e L_w = 1 m e constante de tempo τ = L / max(W, 1 m/s);
      2. RAJADAS discretas «1 − cos» (a forma do gust discreto das normas de qualidades de voo):
         chegadas de Poisson com intervalo médio 6 s, amplitude U[0,3; 0,7]·W, duração U[1; 3] s e
         direção sorteada à volta da média (σ = 30° em azimute, 10° em elevação);
      3. MUDANÇA LENTA de direção: o azimute médio deambula (OU com σ = 15°, τ = 20 s).
    O resultado é saturado em norma a `TETO_FATOR·W` (2,5×) — é o teto físico do modo, declarado.

Fontes (ideias e números de referência; o código é próprio):
  · MIL-HDBK-1797 / MIL-F-8785C, modelo de turbulência de DRYDEN a baixa altitude: σ_w = 0,1·W20,
    σ_u/σ_w = 1/(0,177 + 0,000823·h)^0,4 (≈ 2 a h ≈ 1 m ⇒ σ_u ≈ 0,2·W), L_w = h e
    L_u = h/(0,177 + 0,000823·h)^1,2 (≈ 8 m a h ≈ 1 m); e o gust DISCRETO «1 − cos»;
  · `env.py` `_passo_dryden` (a mesma discretização exata do OU: x ← α·x + σ·√(1−α²)·ξ, α = e^(−Δt/τ)).
A direção deambulante e a taxa das rajadas NÃO vêm da norma: são escolhas de cenário para a
aleatoriedade ser visível num voo de minutos (documentadas aqui e nos testes).

A intensidade pedida entra por uma RAMPA de 1.ª ordem (τ = 0,6 s): ligar o vento, desligá-lo ou arrastar o
slider nunca é um degrau instantâneo de vários m/s (o ar real não faz isso) e as mudanças ficam suaves.
"""
from __future__ import annotations

import math

import numpy as np

# ------------------------------------------------------------------------------------------- parâmetros
INTENSIDADE_MAX = 5.0        # m/s — teto do slider (a faixa do vento base do contrato; o envelope
#                              voável da cascata mede-se em `avaliar_vento.py`)
TETO_FATOR = 2.5             # o vento total nunca passa TETO_FATOR × intensidade (em norma)
TAU_RAMPA_S = 0.6            # s — constante de tempo da rampa da intensidade (ligar/desligar/slider)
SIGMA_H, SIGMA_W = 0.20, 0.10          # σ da turbulência ÷ W: horizontal (u, v) e vertical (w)
ESCALA_H_M, ESCALA_W_M = 8.0, 1.0      # m — escalas de comprimento da turbulência (Dryden, h ≈ 1 m)
V_MIN = 1.0                  # m/s — piso de V em τ = L/V (com W ≈ 0 a escala de tempo seria infinita)
RAJADA_INTERVALO_S = 6.0     # s — intervalo MÉDIO entre rajadas (chegadas de Poisson)
RAJADA_AMP = (0.3, 0.7)      # amplitude da rajada ÷ W (uniforme)
RAJADA_DURACAO_S = (1.0, 3.0)  # s — duração da rajada (uniforme)
RAJADA_SIGMA_AZ, RAJADA_SIGMA_EL = 30.0, 10.0   # graus — dispersão da direção da rajada
DERIVA_SIGMA, DERIVA_TAU_S = 15.0, 20.0         # graus, s — deambular do azimute médio (OU)
RESIDUO = 1e-3               # m/s — abaixo disto a rampa a descer considera-se 0 (desliga a sério)


def polar_do_vetor(vec) -> tuple[float, float, float]:
    """`[vx, vy, vz]` (m/s) → `(vel, azimute°, elevação°)` — os argumentos do `env.definir_vento`."""
    vx, vy, vz = (float(v) for v in vec)
    vel = math.sqrt(vx * vx + vy * vy + vz * vz)
    if vel < 1e-12:
        return 0.0, 0.0, 0.0
    return vel, math.degrees(math.atan2(vy, vx)) % 360.0, math.degrees(math.asin(max(-1.0, min(1.0, vz / vel))))


def validar(ligado, intensidade, aleatorio, direcao) -> dict:
    """Bloco `{ligado, intensidade, aleatorio, direcao}` validado (`ValueError` com o motivo).

    `intensidade` ∈ [0, INTENSIDADE_MAX] m/s e `direcao` finita (reduzida a [0, 360)°); os dois
    interruptores são booleanos ESTRITOS (um `1` ou um `"sim"` é gralha — recusa-se em vez de adivinhar).
    """
    for nome, valor in (("ligado", ligado), ("aleatorio", aleatorio)):
        if not isinstance(valor, bool):
            raise ValueError(f"`{nome}` tem de ser booleano (recebido {valor!r})")  # noqa: TRY004
    for nome, valor in (("intensidade", intensidade), ("direcao", direcao)):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(float(valor)):
            raise ValueError(f"`{nome}` tem de ser um número finito (recebido {valor!r})")
    if not 0.0 <= float(intensidade) <= INTENSIDADE_MAX:
        raise ValueError(f"`intensidade` tem de estar em [0, {INTENSIDADE_MAX:g}] m/s (recebido {intensidade!r})")
    return {"ligado": ligado, "intensidade": float(intensidade), "aleatorio": aleatorio,
            "direcao": float(direcao) % 360.0}


class VentoNatural:
    """Gerador do vento dos três botões (ver o cabeçalho). Um `passo(dt)` por passo de decisão.

    Determinístico pela `semente`: a mesma semente e a mesma sequência de `definir`/`passo` dão o mesmo
    vento, bit a bit. Com `aleatorio=False` (ou W = 0) não se consome NADA do gerador de números — o
    vento constante é exatamente `W·[cos az, sin az, 0]` depois da rampa.
    """

    def __init__(self, semente: int | None = 0):
        self._rng = np.random.default_rng(semente)
        self.ligado = False
        self.aleatorio = False
        self.intensidade = 0.0          # W pedido (m/s)
        self.direcao = 0.0              # azimute pedido (graus)
        self._w = 0.0                   # W em vigor (depois da rampa)
        self._turb = np.zeros(3)        # estado OU da turbulência ÷ W, no referencial do vento (u, v, w)
        self._deriva = 0.0              # deambular do azimute (graus)
        self._rajada: dict | None = None   # rajada em curso: {vec ÷ W (mundo), t, duracao}
        self.vetor = np.zeros(3)        # último vento devolvido (m/s, mundo)
        self.n_rajadas = 0              # rajadas iniciadas (auditoria/testes)

    # ------------------------------------------------------------------ comandos
    def definir(self, ligado: bool, intensidade: float, aleatorio: bool, direcao: float = 0.0) -> dict:
        """Aplica os três botões (+ a direção). Devolve o bloco validado.

        Desligar a aleatoriedade (ou o vento) ESQUECE a turbulência, a deriva e a rajada em curso: o vento
        volta a ser a média constante sem nada pendente — é a mesma garantia do PARAR do contrato antigo.
        """
        bloco = validar(ligado, intensidade, aleatorio, direcao)
        self.ligado, self.aleatorio = bloco["ligado"], bloco["aleatorio"]
        self.intensidade, self.direcao = bloco["intensidade"], bloco["direcao"]
        if not (self.ligado and self.aleatorio):
            self._turb[:] = 0.0
            self._deriva = 0.0
            self._rajada = None
        return bloco

    def repor(self) -> None:
        """Vento a ZERO já, sem rampa, e nada pendente (botões desligados; o gerador de números não recua).

        É para quando o gerador deixa de MANDAR no vento (o bloco dos 3 botões saiu do controlo e voltou a
        valer o contrato antigo): daí em diante ninguém chama `passo`, por isso a rampa não desce sozinha —
        sem isto o nível ficava congelado e reaparecia como um «vento fantasma» no 1.º passo do bloco seguinte.
        """
        self.ligado = self.aleatorio = False
        self.intensidade = 0.0
        self._w = 0.0
        self._turb[:] = 0.0
        self._deriva = 0.0
        self._rajada = None
        self.vetor = np.zeros(3)

    @property
    def alvo(self) -> float:
        """A intensidade para onde a rampa caminha: W pedido, ou 0 com o vento desligado."""
        return self.intensidade if self.ligado else 0.0

    @property
    def em_rajada(self) -> bool:
        return self._rajada is not None

    # ------------------------------------------------------------------ um passo
    def passo(self, dt: float) -> np.ndarray:
        """Vento `[vx, vy, vz]` (m/s, mundo) do passo de decisão de duração `dt` que agora começa."""
        dt = float(dt)
        if not dt > 0.0 or not math.isfinite(dt):
            raise ValueError(f"`dt` tem de ser um número finito > 0 (recebido {dt!r})")
        self._w += (self.alvo - self._w) * (1.0 - math.exp(-dt / TAU_RAMPA_S))     # rampa de 1.ª ordem
        if self.alvo == 0.0 and self._w < RESIDUO:
            self._w = 0.0
        w = self._w
        if w == 0.0:
            self.vetor = np.zeros(3)
            return self.vetor.copy()
        azimute = math.radians(self.direcao)
        if not (self.ligado and self.aleatorio):
            self.vetor = w * np.array([math.cos(azimute), math.sin(azimute), 0.0])
            return self.vetor.copy()

        v = max(w, V_MIN)                                       # τ = L / V (Dryden)
        for eixo, (sigma, escala) in enumerate(((SIGMA_H, ESCALA_H_M), (SIGMA_H, ESCALA_H_M),
                                                (SIGMA_W, ESCALA_W_M))):
            alfa = math.exp(-dt * v / escala)
            self._turb[eixo] = alfa * self._turb[eixo] + sigma * math.sqrt(1.0 - alfa * alfa) * float(
                self._rng.normal())
        alfa = math.exp(-dt / DERIVA_TAU_S)                     # deambular lento do azimute
        self._deriva = alfa * self._deriva + DERIVA_SIGMA * math.sqrt(1.0 - alfa * alfa) * float(
            self._rng.normal())
        az = azimute + math.radians(self._deriva)
        c, s = math.cos(az), math.sin(az)
        u, lat, vert = 1.0 + self._turb[0], self._turb[1], self._turb[2]      # ÷ W, referencial do vento
        total = np.array([c * u - s * lat, s * u + c * lat, vert])

        if self._rajada is None and float(self._rng.random()) < 1.0 - math.exp(-dt / RAJADA_INTERVALO_S):
            amp = float(self._rng.uniform(*RAJADA_AMP))
            az_r = az + math.radians(float(self._rng.normal(0.0, RAJADA_SIGMA_AZ)))
            el_r = math.radians(float(self._rng.normal(0.0, RAJADA_SIGMA_EL)))
            self._rajada = {"vec": amp * np.array([math.cos(el_r) * math.cos(az_r),
                                                   math.cos(el_r) * math.sin(az_r), math.sin(el_r)]),
                            "t": 0.0, "duracao": float(self._rng.uniform(*RAJADA_DURACAO_S))}
            self.n_rajadas += 1
        if self._rajada is not None:
            r = self._rajada
            r["t"] += dt
            if r["t"] >= r["duracao"]:
                self._rajada = None
            else:
                total = total + r["vec"] * (0.5 * (1.0 - math.cos(2.0 * math.pi * r["t"] / r["duracao"])))

        norma = float(np.linalg.norm(total))
        if norma > TETO_FATOR:
            total = total * (TETO_FATOR / norma)
        self.vetor = w * total
        return self.vetor.copy()
