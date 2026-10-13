"""lab.drone_rpi.escalar — aritmética ESCALAR com o MESMO resultado, bit a bit, das operações NumPy que substitui.

PORQUÊ. A planta corre a 500 Hz com vetores de 3–4 elementos. Aí o custo de uma chamada NumPy (1–4 µs de despacho,
alocação e verificação de tipos) é ~100× o da conta: a mesma operação em `float` do Python custa 30–40 ns. Medido em
2026-10-12 (`experiments/09_drone_hover_rl/bench_treino.py`): 86 % do `env.step` era este despacho. O caminho quente da
`Planta` passou por isso a fazer as contas em escalares — mas uma otimização NÃO pode mudar a trajetória do simulador,
logo cada substituição tem de dar o mesmo `float64` até ao último bit:

  · `+ − × ÷ √` elemento a elemento são IEEE-754 exatos dos dois lados — iguais por construção (a ORDEM das operações
    de cada expressão é a mesma do código vetorial; o Python não funde `a*b + c` num FMA);
  · `x.sum()`, `np.sum`, `np.mean` e `M.sum(axis=0)` com menos de 8 parcelas somam em sequência A PARTIR DE +0,0:
    (((0 + x0) + x1) + x2) + x3 — o zero inicial só se nota no sinal de um resultado nulo (−0,0 nunca sai de uma soma);
  · `np.maximum(x, c)`/`np.minimum(x, c)` devolvem `c` em caso de empate (−0,0 vs +0,0) e propagam NaN — em escalar
    `x if (x > c or isnan(x)) else c`; os `max`/`min` do Python devolvem o 1.º argumento no empate e NÃO propagam
    NaN (servem onde o original já os usava, ou com a ordem dos argumentos certa); `np.clip` devolve o PRÓPRIO `x`
    quando está dentro da faixa (preserva o −0,0);
  · `np.round` arredonda para o par e preserva o sinal do zero (`rint`);
  · `np.interp` é `declive·(x − xp[j]) + fp[j]`, com os nós e os extremos devolvidos exatos (`Tabela`);
  · `A @ x` (BLAS `dgemv`) e `np.dot` (`ddot`) dependem do KERNEL do OpenBLAS desta máquina. Com o kernel Haswell
    (AVX2 + FMA — o desta máquina) uma linha de `A(·,3) @ x(3)` sai `0 + fma(a2, x2, fma(a0, x0, a1·x1))` e o `np.dot`
    de duas colunas (passo ≠ 1) de 4 elementos sai `(0 + (p0 + p2)) + (0 + (p1 + p3))` sem FMA (os acumuladores do
    kernel nascem a +0,0). Noutra CPU/BLAS pode ser diferente.

Por causa do último ponto nada aqui é assumido: `verificar()` COMPARA no arranque cada fórmula escalar com o NumPy
desta máquina (amostras fixas, com zeros de ambos os sinais misturados — é com eles que se distinguem as variantes;
~5 ms) e `OK` só fica `True` se TODAS baterem bit a bit (e se houver `math.fma`,
Python ≥ 3.13). Com `OK = False` a `Planta` usa o caminho vetorial ORIGINAL (`Planta._passo_vetorial`) — mais lento,
idêntico por definição. `DRONE_RPI_ESCALAR=0` no ambiente força esse caminho (é assim que o `bench_treino.py` o testa).
"""
from __future__ import annotations

import math
import os
from bisect import bisect_right

import numpy as np

fma = getattr(math, "fma", None)        # Python ≥ 3.13; sem ele não há caminho escalar (o dgemv usa FMA)
_nan = math.isnan

N_AMOSTRAS = 64                          # por operação, na verificação de arranque
SEMENTE = 20261012


def rint(x: float) -> float:
    """`np.round(x)` de um escalar: arredonda para o par e preserva o sinal do zero (−0,2 → −0,0); NaN/inf passam."""
    try:
        return math.copysign(float(round(abs(x))), x)
    except (OverflowError, ValueError):
        return x


def clip(x: float, a: float, b: float) -> float:
    """`np.clip(x, a, b)` de um escalar (devolve o próprio `x` dentro da faixa — o −0,0 e o NaN passam)."""
    return a if x < a else min(x, b)


class Tabela:
    """`np.interp(x, xp, fp)` para um `x` escalar, com os declives pré-calculados (xp ESTRITAMENTE crescente).

    Mesma conta do NumPy: fora da tabela devolve o extremo; num nó devolve o `fp` do nó; entre nós
    `declive·(x − xp[j]) + fp[j]` com `declive = (fp[j+1] − fp[j])/(xp[j+1] − xp[j])`. `exata` diz se a verificação
    contra o `np.interp` desta máquina passou (nós, pontos médios e pontos fora); quando não passa — ou quando o `xp`
    tem nós repetidos — `__call__` delega no `np.interp`.
    """

    def __init__(self, xp, fp):
        self.xp = [float(v) for v in xp]
        self.fp = [float(v) for v in fp]
        self.n = len(self.xp)
        self._np = (np.array(self.xp), np.array(self.fp))
        crescente = all(b > a for a, b in zip(self.xp, self.xp[1:], strict=False))
        self.declives = ([(self.fp[j + 1] - self.fp[j]) / (self.xp[j + 1] - self.xp[j]) for j in range(self.n - 1)]
                         if crescente else [])
        self.exata = False
        if crescente and self.n >= 2:
            self.exata = True                                   # provisório, para `_escalar` poder ser chamada
            self.exata = self._verifica()

    def _escalar(self, x: float) -> float:
        xp = self.xp
        if _nan(x):
            return x
        if x > xp[-1]:
            return self.fp[-1]
        if x < xp[0]:
            return self.fp[0]
        j = bisect_right(xp, x) - 1
        if j == self.n - 1 or xp[j] == x:
            return self.fp[j]
        return self.declives[j] * (x - xp[j]) + self.fp[j]

    def _verifica(self) -> bool:
        xp, fp = self._np
        g = np.random.default_rng(SEMENTE)
        vao = xp[-1] - xp[0]
        pontos = np.concatenate((xp, 0.5 * (xp[:-1] + xp[1:]), g.uniform(xp[0] - 0.1 * vao, xp[-1] + 0.1 * vao, 256),
                                 [xp[0] - vao, xp[-1] + vao, -0.0, 0.0]))
        ref = np.interp(pontos, xp, fp)
        meu = np.array([self._escalar(x) for x in pontos.tolist()])
        um_a_um = np.array([np.interp(x, xp, fp) for x in pontos[:32].tolist()])
        return ref.tobytes() == meu.tobytes() and um_a_um.tobytes() == meu[:32].tobytes()

    def __call__(self, x: float) -> float:
        if self.exata:
            return self._escalar(x)
        return float(np.interp(x, *self._np))


# --------------------------------------------------------------------------------------- verificação de arranque
def _bits(valores) -> bytes:
    return np.asarray(valores, dtype=float).tobytes()


def verificar() -> dict:
    """Compara cada fórmula escalar com o NumPy DESTA máquina; devolve `{operação: bool}` (tudo True ⇒ `OK`)."""
    g = np.random.default_rng(SEMENTE)
    r: dict[str, bool] = {"fma": fma is not None}

    def escala() -> float:
        return float(10.0 ** g.uniform(-3.0, 3.0))

    def amostra(*forma) -> np.ndarray:
        """Normais com escala aleatória e ~1/3 de zeros de ambos os sinais (os zeros distinguem as variantes)."""
        a = g.normal(size=forma) * escala()
        nulos = g.random(forma) < 0.33
        a[nulos] = g.choice([0.0, -0.0], size=int(nulos.sum()))
        return a

    # A @ x (dgemv): matriz (3,3) contígua @ vetor contíguo; (4,3) @ coluna de uma (3,3) (passo 3); (4,3) @ contíguo
    ok_gemv = fma is not None
    for _ in range(N_AMOSTRAS if ok_gemv else 0):
        a33, x3 = amostra(3, 3), amostra(3)
        v43, rot = amostra(4, 3), amostra(3, 3)
        casos = [(a33, x3, a33 @ x3), (v43, rot[:, 2], v43 @ rot[:, 2]), (v43, rot[:, 0], v43 @ rot[:, 0]),
                 (v43, x3, v43 @ x3)]
        for a, x, ref in casos:
            x0, x1, x2 = x.tolist()
            meu = [0.0 + fma(l2, x2, fma(l0, x0, l1 * x1)) for l0, l1, l2 in a.tolist()]
            ok_gemv = ok_gemv and _bits(meu) == ref.tobytes()
    r["gemv (A @ x, 3 colunas)"] = ok_gemv

    # np.dot de duas COLUNAS (passo 3) de comprimento 4 — o `_cruz_soma` da planta
    ok_dot = True
    for _ in range(N_AMOSTRAS):
        p, q = amostra(4, 3), amostra(4, 3)
        for i, j in ((1, 2), (2, 1), (2, 0), (0, 2), (0, 1), (1, 0)):
            a0, a1, a2, a3 = p[:, i].tolist()
            b0, b1, b2, b3 = q[:, j].tolist()
            meu = (0.0 + (a0 * b0 + a2 * b2)) + (0.0 + (a1 * b1 + a3 * b3))
            ok_dot = ok_dot and _bits(meu) == _bits(np.dot(p[:, i], q[:, j]))
    r["ddot (colunas, n = 4)"] = ok_dot

    # somas curtas: sequenciais, a partir de +0,0
    ok_soma = True
    for _ in range(N_AMOSTRAS):
        v4, m43 = amostra(4), amostra(4, 3)
        a0, a1, a2, a3 = v4.tolist()
        s = (((0.0 + a0) + a1) + a2) + a3
        colunas = [(((0.0 + c[0]) + c[1]) + c[2]) + c[3] for c in m43.T.tolist()]
        ok_soma = (ok_soma and _bits(s) == _bits(v4.sum()) == _bits(np.sum(v4)) and _bits(s / 4) == _bits(np.mean(v4))
                   and _bits(colunas) == m43.sum(axis=0).tobytes())
    r["somas de 4 parcelas"] = ok_soma

    # máximos/mínimos/clip/round com zeros com sinal e NaN
    especiais = [-0.0, 0.0, float("nan"), -0.3, 0.3, -0.5, 0.5, 1.5, 2.5, -1.5, 1.0, -1.0, 7.25, -7.25]
    valores = especiais + (g.normal(size=64) * 3.0).tolist()
    arr = np.array(valores)
    ok_lim = True
    for c in (0.0, 1.0, -1.0, 0.3):
        ok_lim = (ok_lim
                  and _bits([x if (x > c or _nan(x)) else c for x in valores]) == np.maximum(arr, c).tobytes()
                  and _bits([x if (x < c or _nan(x)) else c for x in valores]) == np.minimum(arr, c).tobytes())
    ok_lim = (ok_lim and _bits([clip(x, -1.0, 1.0) for x in valores]) == np.clip(arr, -1.0, 1.0).tobytes()
              and _bits([clip(x, 0.0, 1.0) for x in valores]) == np.clip(arr, 0.0, 1.0).tobytes()
              and all(_bits(clip(x, 0.0, 1.0)) == _bits(np.clip(x, 0.0, 1.0)) for x in valores)
              and _bits([max(0.0, x) for x in valores]) == np.where(arr > 0.0, arr, 0.0).tobytes())
    r["maximum/minimum/clip/where"] = ok_lim
    r["round (para o par, sinal do zero)"] = (
        _bits([rint(x) for x in valores]) == np.round(arr).tobytes()
        and _bits([rint(x / 0.0072) * 0.0072 for x in valores]) == (np.round(arr / 0.0072) * 0.0072).tobytes())
    r["sqrt"] = _bits([math.sqrt(abs(x)) for x in valores]) == np.sqrt(np.abs(arr)).tobytes()

    # np.interp numa tabela qualquer (as tabelas reais — curva do ESC, OCV — verificam-se a si próprias)
    xp = np.sort(g.uniform(0.0, 1.0, 9))
    r["interp"] = Tabela(xp, np.sort(g.uniform(0.0, 4.0, 9))).exata

    # gerador: normal(0, s, n) ≡ s·standard_normal(n); normal(0, 1, n)·k ≡ standard_normal(n)·k; lote ≡ parcelas
    g1, g2 = np.random.default_rng(SEMENTE), np.random.default_rng(SEMENTE)
    ok_rng = True
    for s in (0.0035, 4.4721e-06, 1.0, 0.034):
        a = np.concatenate((g1.normal(0.0, s, 3), g1.normal(0.0, 1.0, 3) * s, g1.normal(0.0, 1.0, 4)))
        z = g2.standard_normal(10).tolist()
        ok_rng = ok_rng and a.tobytes() == _bits([s * v for v in z[:3]] + [v * s for v in z[3:6]] + z[6:])
    r["gerador (normal ≡ escala × standard_normal em lote)"] = ok_rng
    return r


VERIFICACAO = verificar()
FORCADO_VETORIAL = os.environ.get("DRONE_RPI_ESCALAR", "1").strip().lower() in ("0", "nao", "não", "false", "off")
OK = all(VERIFICACAO.values()) and not FORCADO_VETORIAL


def resumo() -> str:
    """Uma linha: que caminho a planta usa nesta máquina e porquê."""
    if OK:
        return "caminho ESCALAR ativo (todas as fórmulas verificadas bit a bit contra o NumPy/BLAS desta máquina)"
    if FORCADO_VETORIAL and all(VERIFICACAO.values()):
        return "caminho VETORIAL original (forçado por DRONE_RPI_ESCALAR=0)"
    falhas = ", ".join(k for k, v in VERIFICACAO.items() if not v)
    return f"caminho VETORIAL original — a aritmética escalar NÃO reproduz o NumPy desta máquina em: {falhas}"


__all__ = ["FORCADO_VETORIAL", "OK", "VERIFICACAO", "Tabela", "clip", "fma", "resumo", "rint", "verificar"]
