#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/multi_ia.py — MECANISMO MULTI-IA de bordo: IAs em ritmos próprios.

O dono pediu (2026-10-11): «várias IAs a correr em simultâneo, cada uma com o seu papel». A
arquitetura DECIDIDA (ATIVIDADE B) é esta — e a decisão mais importante é uma SUBTRAÇÃO:

    · **FC H7 (determinístico, NÃO-IA) faz a ESTABILIDADE** — `fc.py`, PID de taxa a 500 Hz com os
      ganhos derivados da planta. **NÃO se substitui por IA**: o hardware real tem um FC dedicado
      (Betaflight/ArduPilot num H7) que fecha as taxas mesmo que a RPi 5 falhe; pôr uma rede a fazer
      o trabalho de um FC dedicado seria caro, lento e menos seguro. As IAs mandam-lhe SETPOINTS.

    · **IA-1 «voo»** (treinada; `out/real_1950_voo_final/final.zip`, modo comando): `v_ref` → ação
      `ctbr` [acelerador, p, q, r] a **50 Hz** (o período de decisão do RPi 5 = 20 ms).

    · **IA-2 «seguimento»** (outra frente; NÃO se depende dela): observação do ponto na imagem →
      `v_ref` a **25 Hz** (= taxa da câmara) para a IA-1. Sem política treinada o mecanismo corre
      MESMO ASSIM — estado honesto `sem_politica` e o `v_ref` vem do WASDQE do site (como hoje).

FLUXO (o que corre em simultâneo, cada um no seu ritmo):

    câmara (25 Hz) → [IA-2 seguimento] ─v_ref─┐
                                              ├→ [IA-1 voo] (50 Hz) ─ação─→ [FC H7 500 Hz] → motores
    site WASDQE ────────────v_ref (fallback)──┘

WATCHDOG/FAIL-SAFE (uma cascata só é confiável se o escalamento for explícito — testado em
`teste_multi_ia.py`):
    · IA-2 ausente/`sem_politica`/em falha → o `v_ref` vem do COMANDO WASDQE do site (o bloco `voo`
      continua a funcionar) — nunca se fica sem controlo;
    · IA-2 sem observação nova dentro do timeout (100–300 ms na literatura: PX4 `COM_OF_LOSS_T`,
      Betaflight failsafe 100 ms) → volta ao WASDQE enquanto não voltar;
    · IA-1 a falhar (sem política ou exceção na inferência) → AÇÃO NEUTRA `ctbr = [0, 0, 0, 0]`
      (= pairagem + taxas zero, pela escala de ação do `env_real._comando`) + estado `erro` e AVISO —
      o FC mantém o drone estabilizado enquanto o operador vê o que se passou;
    · estados por IA (visíveis no site/telemetria): `a_correr` · `sem_politica` · `fallback` · `erro`
      (`sem_politica` e `erro` são pegajosos: só saem com `recuperar()`).

CONTA POR IA (estilo `deploy.py`): nº de inferências, latência medida em µs com **p50/p99/max**,
última observação e última ação (compactos) — é o que o painel RPi 5 soma contra o período de 20 ms.

API PARA O RUNNER (duas funções, nada mais):
    `acao = cascata.passo(t, obs)`   · t em segundos (`time.perf_counter`), obs do env — a IA-1
                                      consome a obs COM o `v_ref` substituído pelo da IA-2 quando há
    `estado = cascata.estado()`      · dict para a telemetria (`"multi_ia"`) e para o site
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

# --------------------------------------------------------------------------------- taxas da cascata
TAXA_IA_VOO_HZ = 50.0            # IA-1 «voo» — o período de decisão do RPi 5 (20 ms)
TAXA_IA_SEGUIMENTO_HZ = 25.0     # IA-2 «seguimento» — 25–50 Hz na literatura; 25 = taxa da câmara
TAXA_FC_HZ = 500.0               # FC H7 (determinístico, NÃO-IA) — fora das IAs, só documentado

# ---------------------------------------------------------------------------------------- fail-safe
TIMEOUT_SEGUIMENTO_S = 0.30      # 300 ms sem observação nova do ponto → volta ao WASDQE (literatura:
                                 # PX4 COM_OF_LOSS_T · Betaflight failsafe 100 ms → banda 100–300 ms)
FALHAS_MAX = 3                   # 3 falhas seguidas → estado `erro` (pegajoso até `recuperar()`)
ACAO_NEUTRA_CTBR = (0.0, 0.0, 0.0, 0.0)   # pairagem + taxas zero (na escala de ação, 0 = pairar)
ESCALA_ACAO_R11 = (1.0, 1.0, 0.7)         # ação a → v_ref = a·(VOO_VEL, VOO_VEL, VOO_SUBIDA) —
                                             # a escala do TREINO (`env_seguimento.step`) e o
                                             # envelope r11: ±1,0 m/s xy, ±0,7 m/s z
SUCESSOS_REENGATE = 3                     # histerese: N sucessos seguidos antes de reengatar o
                                             # tracker (sem isto alterna tracker↔fallback: chatter)

# ------------------------------------------------------------------------------------------ estados
ESTADOS_IA = ("a_correr", "sem_politica", "fallback", "erro")

# Canais do `v_ref` ESCALADO dentro da observação do env (o `env_real.observacao`): o modo comando
# acrescenta [vx/VOO_VEL, vy/VOO_VEL, vz/VOO_SUBIDA] ao ATOR e ao CRÍTICO. A IA-2 produz `v_ref` em
# m/s e a cascata substitui ESTES canais antes de a IA-1 ver a obs — é assim que o `v_ref` do tracker
# "substitui o do WASDQE" sem tocar no env. Índices por comprimento da obs (modo comando):
#   24 (real ator)  → canais [21:24] · 48 (real total) → [21:24] e [45:48]
#   19 (cf2 ator)   → canais [16:19] · 38 (cf2 total)  → [16:19] e [35:38]
# Modo clássico (sem `v_ref` na obs: 21/42/16/32) não tem canais — a cascata substitui nada e o
# estado diz `v_ref_fonte: "wasdqe"` (documentado, nunca em silêncio).
CANAIS_V_REF = {
    24: ((21, 24),), 48: ((21, 24), (45, 48)),
    19: ((16, 19),), 38: ((16, 19), (35, 38)),
}
ESCALAS_V_REF = np.array([1.0, 1.0, 1.0])     # ver `configurar_escalas_v_ref` (VOO_VEL, VOO_VEL, VOO_SUBIDA)


def configurar_escalas_v_ref(vel: float = 1.0, subida: float = 0.7) -> None:
    """As escalas do `v_ref` na obs (o `env_real` usa vx/VOO_VEL, vy/VOO_VEL, vz/VOO_SUBIDA)."""
    global ESCALAS_V_REF
    ESCALAS_V_REF = np.array([float(vel), float(vel), float(subida)])


def _prever(politica, obs, deterministico: bool = True):
    """`predict` de uma política SB3 (objeto com `.predict`) OU de um callable (ex. o MLP do tracker)."""
    if hasattr(politica, "predict"):
        acao, _ = politica.predict(obs, deterministic=deterministico)
        return acao
    return politica(obs)


def _percentis(amostras_us) -> dict:
    """p50/p99/max/média (µs) — o MESMO formato do `deploy.py` (a referência de latências do lab)."""
    a = np.asarray(amostras_us, dtype=float)
    if a.size == 0:
        return {"n": 0, "p50_us": None, "p99_us": None, "max_us": None, "media_us": None}
    return {"n": int(a.size), "p50_us": round(float(np.percentile(a, 50)), 1),
            "p99_us": round(float(np.percentile(a, 99)), 1), "max_us": round(float(np.max(a)), 1),
            "media_us": round(float(np.mean(a)), 1)}


# --------------------------------------------------------------------------------------------- uma IA
@dataclass
class IA:
    """UMA IA de bordo: nome, papel, política, taxa e a conta do que faz (inferências/latências).

    `obs_de` (opcional) extrai a observação DO AMBIENTE para esta IA (a IA-2:
    `observacao_seguimento(env)`); sem ele a IA usa a observação que o `passo` recebe. A política
    aceita SB3 (`.predict`) ou callable; uma inferência que REBENTE conta como falha da IA e o
    fail-safe decide — nunca rebenta o runner.
    """

    nome: str
    papel: str
    taxa_hz: float
    politica: object | None = None
    obs_de: object | None = None            # () -> obs (a IA-2: `ObservacaoSeguimento` = builder do TREINO)
    conversor_acao: object | None = None    # ação -> v_ref (a IA-2: `ObservacaoSeguimento.definir_acao`)
    escala_acao: tuple | None = None        # ação a → v_ref = a·escala (default ESCALA_ACAO_R11)
    latencia_us: float | None = None        # ÚLTIMA inferência (µs); o histórico fica em `metricas()`
    estado: str = "sem_politica"
    motivo: str = ""
    falhas: int = 0                       # CONSECUTIVAS (o sucesso zera — é o fail-safe da literatura)
    n_falhas_total: int = 0               # total acumulado (só observabilidade; não escala nada)
    n_inferencias: int = 0
    ultima_obs: np.ndarray | None = None
    ultima_acao: np.ndarray | None = None
    _amostras_us: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.politica is None:
            self.estado = "sem_politica"
            self.motivo = "sem política carregada"
        else:
            self.estado = "a_correr"

    @property
    def periodo_s(self) -> float:
        return 1.0 / float(self.taxa_hz) if self.taxa_hz > 0 else float("inf")

    def inferir(self, obs, deterministico: bool = True):
        """Uma inferência com conta de latência (µs, `perf_counter` como o `deploy.py`)."""
        if self.politica is None:
            return None
        obs = np.asarray(obs, dtype=np.float32)
        t0 = time.perf_counter()
        try:
            acao = _prever(self.politica, obs, deterministico)
        except Exception as erro:  # noqa: BLE001
            # catch-all POR DESENHO: uma rede que rebente não pode rebentar o runner — conta como
            # FALHA da IA e o fail-safe decide (ação neutra / fallback), sem exceção a propagar
            self.falha(f"inferência rebentou: {type(erro).__name__}: {erro}")
            return None
        acao = np.asarray(acao, dtype=float).ravel()
        if not np.all(np.isfinite(acao)):
            # FIX (revisão 2026-10-12): NaN/Inf da rede NÃO se propaga — conta como FALHA e o
            # fail-safe decide (a obs da IA-1 nunca recebe NaN; o v_ref nunca contém NaN)
            self.falha(f"ação não finita da política (NaN/Inf): {acao[:4].tolist()}")
            return None
        self.latencia_us = (time.perf_counter() - t0) * 1e6
        self._amostras_us.append(self.latencia_us)
        if len(self._amostras_us) > 512:                # janela deslizante (o resto fica no histórico)
            del self._amostras_us[:256]
        self.n_inferencias += 1
        self.ultima_obs = obs[:12].copy()               # compacto: só o cabeçalho da obs
        self.ultima_acao = np.asarray(acao, dtype=float).ravel()[:8].copy()
        self.falhas = 0                   # sucesso: a contagem é de CONSECUTIVAS (fix 5 da revisão)
        if self.estado not in ("erro", "sem_politica"):
            self.estado = "a_correr"
            self.motivo = ""
        return acao

    def falha(self, motivo: str = "") -> str:
        """Regista uma FALHA CONSECUTIVA (o sucesso devolve o contador a zero — ver `inferir`)."""
        self.falhas += 1
        self.n_falhas_total += 1
        self.motivo = motivo or self.motivo
        self.estado = "erro" if self.falhas >= FALHAS_MAX else "fallback"
        return self.estado

    def recuperar(self) -> None:
        self.falhas = 0
        self.estado = "a_correr" if self.politica is not None else "sem_politica"

    def metricas(self) -> dict:
        return _percentis(self._amostras_us)

    def as_dict(self) -> dict:
        """O bloco COMPACTO de uma IA (telemetria `"multi_ia"` e site)."""
        return {"nome": self.nome, "papel": self.papel, "taxa_hz": round(float(self.taxa_hz), 1),
                "ativo": bool(self.politica is not None and self.estado == "a_correr"),
                "estado": self.estado, "motivo": (self.motivo or None), "falhas": self.falhas,
                "n_falhas_total": self.n_falhas_total,
                "n_inferencias": self.n_inferencias,
                "latencia_us": None if self.latencia_us is None else round(float(self.latencia_us), 1),
                "latencia": self.metricas(),
                "ultima_obs": (None if self.ultima_obs is None
                               else [round(float(x), 4) for x in self.ultima_obs]),
                "ultima_acao": (None if self.ultima_acao is None
                                else [round(float(x), 4) for x in self.ultima_acao])}


# --------------------------------------- observação da IA-2 = O BUILDER DO TREINO (env_seguimento)
class ObservacaoSeguimento:
    """A observação da IA-2 vem SEMPRE do builder do TREINO — `env_seguimento._observacao` (OBS_DIM=17).

    REGRAS do contrato do treino (o `env_seguimento.py` manda; medido na revisão crítica de 2026-10-12):
      · a obs é `[u_n, v_n, escala, flag, v_ref(3), erro_px(2), v̂/2(3), ω/2(3), roll/π, pitch/π]`
        (17 canais NORMALIZADOS) — construída pelo `_observacao` do treino, nunca por um placeholder;
      · o canal `v_ref(3)` da obs é a **AÇÃO CRUA** (o builder divide `self._v_ref` pela escala);
      · a ação `a` do tracker vira `v_ref = a·(VOO_VEL, VOO_VEL, VOO_SUBIDA)` = (1, 1, 0,7) — a MESMA
        escala do `env_seguimento.step` (sem isto o z errava +43 %, medido na revisão).

    `__call__()` devolve a obs para a IA-2; `definir_acao(a)` guarda a ação crua (para o canal da obs
    seguinte) e devolve o `v_ref` em m/s no envelope r11. Sem ponto (`env.ponto_alvo is None`) o caso é
    o do treino com `visivel: False` (a obs vem a zeros nos canais do ponto) — o fail-safe usa o WASDQE.
    """

    def __init__(self, env, resolucao: tuple[int, int] = (1920, 1080)):
        import env_seguimento as es  # o contrato é do TREINO (ficheiro da outra frente)
        self._es = es
        self.env = env
        self.resolucao = (int(resolucao[0]), int(resolucao[1]))
        self._v_ref = np.zeros(3)

    def __call__(self) -> np.ndarray:
        if getattr(self.env, "ponto_alvo", None) is None:
            vis = {"visivel": False, "u": None, "v": None, "raio_px": 0.0, "profundidade": None}
        else:
            vis = self._es.EnvSeguimento._ver_projecao(self)      # projeção EXATA do treino
        return self._es.EnvSeguimento._observacao(self, vis)      # builder EXATO do treino

    def definir_acao(self, acao) -> np.ndarray:
        """Ação crua `a` ∈ [-1,1]³ → `v_ref` em m/s COM A ESCALA DO TREINO (canal da obs = ação crua)."""
        a = np.clip(np.asarray(acao, dtype=float).ravel()[:3], -1.0, 1.0)
        self._v_ref = np.array([a[0] * self._es.VOO_VEL, a[1] * self._es.VOO_VEL,
                                a[2] * self._es.VOO_SUBIDA], dtype=float)   # envelope r11 (±1,0/±0,7)
        return self._v_ref.copy()


def observacao_seguimento(env) -> np.ndarray:
    """[DEPRECATED — usar `ObservacaoSeguimento`] placeholder 13 canais, SÓ para testes sem o treino.

    Obs da IA-2 «seguimento»: o estado do ponto e a sua projeção na câmara.

    A outra frente (que treina a IA-2) define a obs EXATA; enquanto ela não existir, este
    placeholder segue o layout da pesquisa (`pesquisas/relatorio-seguimento-visual-rl.md`, «≈12D»):
    `[u, v, raio, visivel, vx, vy, vz, wx, wy, wz, gx, gy, gz]` — **13 canais**: centroide normalizado
    (u, v) com raio/área como proxy de profundidade, flag `visivel` (a pesquisa conta-a no «≈12D») e a
    PRÓPRIOCEPÇÃO obrigatória (v, ω, gravidade; sem ela a sobrevivência na literatura cai de 97 % para
    4 %). A outra frente pode definir outra obs — o `IA.obs_de` é que a injeta.

    Lê o que existir em `env` (atributos `ponto_uv_raio`/`alvo_visual`/`deteccao_ponto`/
    `ponto_estado`); nada existe → o vetor vem a zeros com `visivel = 0` (a IA-2 não "vê" nada e o
    fail-safe usa o WASDQE) — NUNCA se inventa um ponto.
    """
    estado = None
    for nome in ("ponto_uv_raio", "alvo_visual", "deteccao_ponto", "ponto_estado"):
        if hasattr(env, nome):
            estado = getattr(env, nome)
            break
    u = v = raio = 0.0
    visivel = 0.0
    if isinstance(estado, dict):
        visivel = 1.0 if estado.get("visivel") else 0.0
        centro = estado.get("centro") or estado.get("uv") or [0.0, 0.0]
        u, v = float(centro[0]), float(centro[1])
        raio = float(estado.get("raio", 0.0))
    elif isinstance(estado, (tuple, list, np.ndarray)) and len(estado) >= 3:
        u, v, raio = (float(estado[0]), float(estado[1]), float(estado[2]))
        visivel = 1.0
    est = getattr(env, "estimador", None)
    v_est = [float(getattr(est, "vx", 0.0)), float(getattr(est, "vy", 0.0)), float(getattr(est, "vz", 0.0))]
    imu = getattr(getattr(env, "planta", None), "imu", None)
    medicao = getattr(getattr(imu, "giro", None), "medicao", None)
    giro = ([float(x) for x in np.asarray(medicao).ravel()[:3]]
            if medicao is not None else [0.0, 0.0, 0.0])   # sem planta: zeros documentados
    gravidade = [0.0, 0.0, -1.0]                        # frame do corpo (o estimador não expõe o quat)
    return np.asarray([u, v, raio, visivel, *v_est, *giro, *gravidade], dtype=np.float32)


# ----------------------------------------------------------------- o orquestrador (a cascata multi-IA)
class CascataMultiIA:
    """O mecanismo: as IAs nos seus ritmos, o fail-safe e a conta por IA.

    `passo(t, obs)` corre a IA-2 quando o seu período passou (25 Hz) e a IA-1 a cada chamada
    (50 Hz); devolve a AÇÃO pronta para `env.step`. A IA-2 só substitui o `v_ref` quando produz um
    novo e fresco; caso contrário (ausente, `sem_politica`, em falha, fora do seu ritmo) o `v_ref`
    que vem na obs — o do WASDQE — continua a valer: **nunca se fica sem controlo**.
    """

    def __init__(self, ia_voo: IA, ia_seguimento: IA | None = None):
        self.voo = ia_voo
        self.seguimento = ia_seguimento or IA(nome="seguimento", papel="ver o ponto → v_ref",
                                              taxa_hz=TAXA_IA_SEGUIMENTO_HZ, politica=None)
        self._v_ref_tracker: np.ndarray | None = None
        self._sucessos_seg = 0                          # sucessos CONSECUTIVOS do tracker (histerese)
        self._t_v_ref: float | None = None              # quando o tracker produziu o v_ref em vigor
        self._proximo_tracker = -1.0
        self._fonte_v_ref = "wasdqe"
        self._aviso: str | None = None
        self.n_passos = 0

    # ------------------------------------------------------------------------- a API do runner
    def passo(self, t: float, obs, deterministico: bool = True) -> np.ndarray:
        """Uma iteração do laço: `obs` do env → AÇÃO `ctbr` (a IA-1) — com o fail-safe aplicado."""
        self.n_passos += 1
        obs = np.asarray(obs, dtype=np.float32)
        # 1) IA-2 «seguimento» no seu ritmo (25 Hz): ação → `v_ref` (m/s) COM A ESCALA DO TREINO
        if self.seguimento.politica is not None and float(t) >= self._proximo_tracker:
            self._proximo_tracker = float(t) + self.seguimento.periodo_s
            obs_seg = self.seguimento.obs_de() if self.seguimento.obs_de is not None else None
            if obs_seg is not None:
                acao_seg = self.seguimento.inferir(obs_seg, deterministico)   # não finitos já contam falha
                if acao_seg is None:
                    self._sucessos_seg = 0                 # falha: a histerese volta ao zero (fix 6)
                else:
                    v_ref = self._v_ref_da_acao(acao_seg)
                    if not np.all(np.isfinite(v_ref)):
                        self.seguimento.falha("v_ref não finito — descartado")
                        self._sucessos_seg = 0
                    else:
                        self._v_ref_tracker = v_ref
                        self._t_v_ref = float(t)
                        self._sucessos_seg += 1
        # 2) fonte do v_ref: tracker novo e fresco → substitui; senão → o da obs (WASDQE)
        obs_consumir, fonte = obs, "wasdqe"
        # histerese (fix 6): o tracker só REENGATA depois de SUCESSOS_REENGATE sucessos seguidos —
        # sem isto alterna-se tracker↔fallback a cada flutuação da deteção (chattering medido)
        fresco = (self._v_ref_tracker is not None and self._t_v_ref is not None
                  and self._sucessos_seg >= SUCESSOS_REENGATE
                  and self.seguimento.estado == "a_correr"
                  and 0.0 <= (float(t) - self._t_v_ref) <= TIMEOUT_SEGUIMENTO_S)
        if fresco:
            obs_consumir = self._substituir_v_ref(obs, self._v_ref_tracker)
            fonte = "seguimento"
        self._fonte_v_ref = fonte
        # 3) IA-1 «voo» (50 Hz): a obs (com o v_ref certo) → ação; em falha → AÇÃO NEUTRA + aviso
        acao = self.voo.inferir(obs_consumir, deterministico)
        if acao is None:
            self._aviso = ("IA-1 «voo» sem inferência (sem política ou em erro) — ação NEUTRA "
                           f"{list(ACAO_NEUTRA_CTBR)} (pairagem + taxas zero; o FC mantém o drone)")
            return np.asarray(ACAO_NEUTRA_CTBR, dtype=float)
        self._aviso = None
        return np.asarray(acao, dtype=float).ravel()

    def estado(self) -> dict:
        """Estado TUDO JUNTO para a telemetria (`"multi_ia"`) e para o site."""
        seg = self.seguimento.as_dict()
        voo = self.voo.as_dict()
        lat_voo = (voo.get("latencia") or {})
        lat_seg = (seg.get("latencia") or {})
        soma = lambda *valores: (None if not any(v is not None for v in valores)
                                 else sum(v or 0.0 for v in valores))
        return {"ias": [voo, seg],
                "v_ref_fonte": self._fonte_v_ref,
                "aviso": self._aviso,
                "fc": {"papel": "estabilidade (PID de taxa)", "taxa_hz": TAXA_FC_HZ, "ia": False,
                       "nota": "FC H7 determinístico — NÃO é IA e não se substitui (o hardware real "
                               "tem FC dedicado); as IAs mandam-lhe setpoints"},
                "latencia_total_us": {"p50_us": soma(lat_voo.get("p50_us"), lat_seg.get("p50_us")),
                                      "p99_us": soma(lat_voo.get("p99_us"), lat_seg.get("p99_us"))},
                "periodo_us": round(1e6 / TAXA_IA_VOO_HZ, 1),
                "n_passos": self.n_passos,
                "atualizado_em": round(time.time(), 3)}

    # ------------------------------------------------------------------------- internos
    def _v_ref_da_acao(self, acao_seg) -> np.ndarray:
        """Ação crua do tracker → `v_ref` em m/s: ESCALA DO TREINO `a·(1, 1, 0,7)` + envelope r11.

        Fix 2 (revisão 2026-10-12): a ação NÃO é v_ref em m/s (o z errava +43 %); o canal de obs da
        IA-2 é a AÇÃO CRUA (o `ObservacaoSeguimento.definir_acao` guarda-a para o builder do treino).
        Fix 4: o envelope é o CONTRATO ±1,0 xy / ±0,7 z — o clip de ±2,0 era violável.
        """
        if self.seguimento.conversor_acao is not None:
            v_ref = np.asarray(self.seguimento.conversor_acao(acao_seg), dtype=float).ravel()[:3]
        else:
            escala = np.asarray(self.seguimento.escala_acao or ESCALA_ACAO_R11, dtype=float)
            v_ref = np.clip(np.asarray(acao_seg, dtype=float).ravel()[:3], -1.0, 1.0) * escala
        return np.clip(v_ref, [-1.0, -1.0, -0.7], [1.0, 1.0, 0.7])   # envelope r11 (contrato)

    def _substituir_v_ref(self, obs: np.ndarray, v_ref_m_s) -> np.ndarray:
        """Substitui os canais do `v_ref` ESCALADO da obs pelo do tracker (canais ver `CANAIS_V_REF`)."""
        canais = CANAIS_V_REF.get(int(obs.shape[0]))
        if not canais:
            return obs                              # modo clássico: sem canais — nada a substituir
        obs = obs.copy()
        v_esc = np.asarray(v_ref_m_s, dtype=np.float32) / ESCALAS_V_REF
        for ini, fim in canais:
            obs[ini:fim] = v_esc[: fim - ini]
        return obs


__all__ = [
    "ACAO_NEUTRA_CTBR",
    "CANAIS_V_REF",
    "ESCALAS_V_REF",
    "ESCALA_ACAO_R11",
    "ESTADOS_IA",
    "FALHAS_MAX",
    "IA",
    "SUCESSOS_REENGATE",
    "TAXA_FC_HZ",
    "TAXA_IA_SEGUIMENTO_HZ",
    "TAXA_IA_VOO_HZ",
    "TIMEOUT_SEGUIMENTO_S",
    "CascataMultiIA",
    "ObservacaoSeguimento",
    "configurar_escalas_v_ref",
    "observacao_seguimento",
]