"""Regressão da camada `lab.drone_rpi` (o drone REAL do dono: peças do catálogo → física) — CPU, sem gym/torch.

Contratos fixados (fórmulas fechadas; a validação completa é o `experiments/09_drone_hover_rl/valida_real.py`):

  · todos os builds de `models/drone_rpi/builds.json` resolvem, compilam e têm massa = Σ orçamento das peças;
  · motor BLDC: o regime integrado é a raiz da quadrática e T_max = kf·ω_max² decresce com a tensão;
  · bateria: contagem de Coulomb exata e queda I·R₀ coerente com a tensão aberta;
  · efeito de solo = Sanchez-Cuevas 2017 eq. (7), por CONTA FECHADA (não por um limiar fixo): igual à fórmula escrita
    à mão, com a geometria do modelo compilado, ≥ rotor isolado de Cheeseman & Bennett a meio diâmetro (+6,7 %) e ≈ 1
    a 5 m; o ganho a 0,5·D depende do espaçamento dos rotores (+20 % no frame de 650 mm, +7,4 % no de 1950 mm);
  · com as flags aerodinâmicas desligadas o voo é bit-idêntico entre corridas (aerodinâmica base).
"""
from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def dr():
    from lab import (
        drone_rpi,
        mjkit,  # noqa: F401  (MUJOCO_GL antes do mujoco)
    )
    return drone_rpi


def test_builds_resolvem_e_massa_bate(dr):
    builds = dr.carregar_builds()
    assert builds["ativo"] in builds["builds"]
    for nome in builds["builds"]:
        hw = dr.hardware(nome)
        model, _ = dr.carregar(hw)
        assert abs(float(model.body_mass.sum()) - hw.massa_total) < 1e-9
        assert hw.kf > 0 and hw.kq > 0 and hw.j_rotor > 0


def test_motor_regime_e_limite_de_rotacao(dr):
    hw = dr.hardware()
    p = dr.Propulsao(hw)
    p.armar(True)
    v = hw.bateria.v_nominal
    p.definir_acelerador([0.6] * 4)
    for _ in range(4000):
        p.passo(0.002, v)
    assert abs(p.omega[0] - hw.omega_regime(p.duty[0], v)) / p.omega[0] < 1e-9
    w_cheia, w_vazia = hw.omega_max(hw.bateria.v_cheia), hw.omega_max(0.85 * hw.bateria.v_cheia)
    assert w_vazia < w_cheia
    assert abs(hw.empuxo_max(hw.bateria.v_cheia) - hw.kf * w_cheia ** 2) < 1e-12


def test_bateria_coulomb_e_queda(dr):
    hw = dr.hardware()
    b = dr.ModeloBateria(hw, soc0=0.8)
    b.c_termica = 1e30
    soc0, e_aberta, r0 = b.soc, b.tensao_aberta(), b.r0()
    b.passo(20.0, 1.0)
    assert abs((soc0 - b.soc) - 20.0 / (3600.0 * b.capacidade_ah)) < 1e-12
    assert abs(b.v - (e_aberta - 20.0 * r0)) < 1e-12


GANHO_SOLO_TETO = 1.6      # teto do módulo (a expressão diverge com o rotor encostado ao chão)


def _decresce(valores) -> bool:
    """Estritamente decrescente."""
    return all(x > y for x, y in itertools.pairwise(valores))


def _ganho_solo_a_mao(z: float, raio: float, d: float, b: float, kb: float = 2.0) -> float:
    """T_IGE/T_OGE de Sanchez-Cuevas, Heredia & Ollero (2017), eq. (7), termo a termo em escalares `math`.

        T_IGE/T_OGE = [1 − (R/4z)² − R²z/√((d²+4z²)³) − (R²/2)·z/√((2d²+4z²)³) − 2R²z·K_b/√((b²+4z²)³)]⁻¹

    z = altura do rotor ao solo; d = distância entre eixos VIZINHOS; b = distância entre eixos OPOSTOS (a diagonal
    = wheelbase); K_b = 2 (sustentação do corpo, empírico). É a conta fechada contra a qual se mede `ganho_solo`
    (vetorizado, com teto), sem lhe reutilizar código. O 1.º termo é o rotor ISOLADO (Cheeseman & Bennett 1955,
    modelo de imagem: T_IGE/T_OGE = 1/(1 − (R/4z)²)); os outros três são a interferência dos vizinhos, do oposto e do
    corpo, e SOMAM-SE a ele — logo o ganho nunca fica abaixo do rotor isolado e cai quando os rotores se afastam.
    """
    s = ((raio / (4.0 * z)) ** 2                                            # rotor isolado
         + raio ** 2 * z / math.sqrt((d ** 2 + 4.0 * z ** 2) ** 3)          # 2 vizinhos, a d
         + 0.5 * raio ** 2 * z / math.sqrt((2.0 * d ** 2 + 4.0 * z ** 2) ** 3)   # 1 oposto, a √2·d
         + 2.0 * raio ** 2 * z * kb / math.sqrt((b ** 2 + 4.0 * z ** 2) ** 3))   # corpo
    return min(1.0 / (1.0 - s), GANHO_SOLO_TETO) if s < 1.0 else GANHO_SOLO_TETO


def _confere_ganho_do_build(dr, nome: str) -> None:
    """Propriedades do ganho de solo de UM build, com a geometria do modelo COMPILADO (os sites `r1..r4`).

    Fórmula = conta à mão (várias alturas) e = soma das IMAGENS dos outros 3 rotores (derivação independente);
    piso do rotor isolado; decaimento com a altura; ≈ 1 a 5 m. O modelo de imagem: cada outro rotor é uma fonte de
    fluxo π·R²·v_i e a sua imagem (a √(ℓ²+4z²) do rotor) induz, na vertical, ½·R²·z/√((ℓ²+4z²)³)·v_i — somados os 3
    dão os termos dos vizinhos (coeficiente 1 = 2 × ½) e do oposto (½); o corpo (K_b = 2, empírico) acrescenta-se.
    """
    hw = dr.hardware(nome)
    r = hw.helice.raio
    model, _ = dr.carregar(hw)
    sites = np.array([model.site(f"r{i}").pos[:2] for i in range(1, 5)])
    dist = np.sort(np.linalg.norm(sites[1:] - sites[0], axis=1))     # de r1 aos outros 3: [d, d, b] num X
    d, b = float(dist[0]), float(dist[-1])
    assert dist[1] == pytest.approx(d, rel=1e-9), nome
    assert d == pytest.approx(hw.frame.wheelbase / math.sqrt(2.0), rel=1e-9), nome      # vizinhos
    assert b == pytest.approx(hw.frame.wheelbase, rel=1e-9), nome                       # opostos = a diagonal
    aero = dr.Aerodinamica(hw)                                  # a geometria do aero é a do modelo que o MuJoCo simula
    assert aero.d_vizinhos == pytest.approx(d, rel=1e-9) and aero.b_opostos == pytest.approx(b, rel=1e-9), nome

    diametro = 2.0 * r
    for z in (0.25 * diametro, 0.5 * diametro, diametro, 1.75 * diametro, 5.0):
        assert float(dr.ganho_solo(z, r, d, b)) == pytest.approx(_ganho_solo_a_mao(z, r, d, b), rel=1e-12), (nome, z)

    z = r                                                       # meio diâmetro
    imagens = sum(0.5 * r ** 2 * z / math.sqrt((ell ** 2 + 4.0 * z ** 2) ** 3) for ell in dist)
    corpo = 2.0 * r ** 2 * z * 2.0 / math.sqrt((b ** 2 + 4.0 * z ** 2) ** 3)
    g_perto = float(dr.ganho_solo(z, r, d, b))
    assert g_perto == pytest.approx(1.0 / (1.0 - ((r / (4.0 * z)) ** 2 + imagens + corpo)), rel=1e-12), nome
    # o piso do ganho a meio diâmetro é o do rotor isolado (a interferência só ADICIONA): ×16/15 = +6,7 %
    isolado = 1.0 / (1.0 - (r / (4.0 * z)) ** 2)
    assert isolado == pytest.approx(16.0 / 15.0, rel=1e-12)
    assert isolado - 1e-12 <= g_perto < GANHO_SOLO_TETO, (nome, g_perto)

    gs = [float(dr.ganho_solo(zz * diametro, r, d, b)) for zz in (0.25, 0.5, 1.0, 1.75)]
    g_longe = float(dr.ganho_solo(5.0, r, d, b))
    assert _decresce(gs) and gs[-1] > g_longe > 1.0, (nome, gs, g_longe)       # cai com a altura
    assert abs(g_longe - 1.0) < 3e-3, (nome, g_longe)                            # ≈ 1 a 5 m
    assert float(dr.ganho_solo(0.0, r, d, b)) == pytest.approx(GANHO_SOLO_TETO)   # encostado ao chão: o teto


def _confere_espacamento(dr) -> None:
    """O ganho a 0,5·D NÃO é uma constante do rotor: a interferência cai com o espaçamento (os termos em 1/ℓ³).

    Hélice de 15″ (R = 0,1905 m, D = 0,381 m), z = R, K_b = 2; conta em alta precisão (ver `_ganho_solo_a_mao`):

        wheelbase 650 mm  (vizinhos a d = 0,4596 m = 1,2 D, oposto a b = 0,65 m):
            1 − 1/16 − 0,03249 (vizinhos) − 0,00808 (oposto) − 0,06466 (corpo) = 0,83227  →  g = ×1,2015
        wheelbase 1950 mm (vizinhos a d = 1,3789 m = 3,6 D, oposto a b = 1,95 m):
            1 − 1/16 − 0,00236 (vizinhos) − 0,00044 (oposto) − 0,00353 (corpo) = 0,93117  →  g = ×1,0739

    O rotor isolado dá ×1,0667 em ambos: o frame compacto soma-lhe +12,6 % de interferência — é nele que vale o
    antigo «≥ +15 %» (×1,2015) —; no de 1950 mm sobra +0,7 % (×1,0739 < 1,15: rotores a 3,6 D quase não se veem).
    O limite de espaçamento infinito é o rotor isolado, 16/15.
    """
    r = 15 * 0.0254 / 2.0

    def g(wheelbase: float) -> float:
        return float(dr.ganho_solo(r, r, wheelbase / math.sqrt(2.0), wheelbase))

    isolado = 16.0 / 15.0
    assert g(0.650) == pytest.approx(1.201532, abs=1e-6) and g(0.650) >= 1.15
    assert g(1.950) == pytest.approx(1.073915, abs=1e-6) and isolado < g(1.950) < 1.15
    assert g(0.650) / isolado - 1.0 == pytest.approx(0.1264, abs=5e-4)
    assert g(1.950) / isolado - 1.0 == pytest.approx(0.0068, abs=5e-4)
    gs = [g(w) for w in (0.5, 0.65, 0.75, 1.0, 1.95, 5.0, 50.0)]
    assert _decresce(gs) and all(x > isolado for x in gs)                    # cai com o espaçamento
    assert g(1000.0) == pytest.approx(isolado, abs=1e-8)                      # → o rotor isolado


def test_efeito_de_solo(dr):
    """O ganho de solo é a eq. (7) de Sanchez-Cuevas 2017 — por conta fechada, não por um limiar fixo.

    O limiar antigo («≥ 1,15 a meio diâmetro») era o do frame de 650 mm e não é uma propriedade do rotor: a meio
    diâmetro (z = R) o ganho é o do rotor isolado (Cheeseman & Bennett: 1/(1 − 1/16) = ×1,0667) MAIS a interferência
    dos vizinhos, do oposto e do corpo, que cai com o espaçamento. Com o frame ativo de 1950 mm (wheelbase ×3: rotores
    a 3,6 D em vez de 1,2 D) a interferência quase desaparece e o ganho é ×1,0739 — a física, não um defeito do
    modelo (`valida_real.py` D1 valida o mesmo critério). Cada build do catálogo cumpre a conta fechada com a
    geometria do seu modelo compilado, e o efeito do espaçamento fica provado com a aritmética no docstring.
    """
    builds = dr.carregar_builds()
    assert builds["ativo"] in builds["builds"]
    for nome in builds["builds"]:
        _confere_ganho_do_build(dr, nome)
    _confere_espacamento(dr)


def test_aerodinamica_base_bit_identica(dr):
    import mujoco
    hw = dr.hardware()

    def rasto():
        model, data = dr.carregar(hw)
        pl = dr.Planta(hw, model, data, flags_aero=dr.FlagsAero.base(), rng=np.random.default_rng(1))
        data.qpos[2] = 0.5
        mujoco.mj_forward(model, data)
        pl.reiniciar(1.0, armado=True)
        for k in range(200):
            pl.passo([0.4 + 0.05 * np.sin(k / 10)] * 4)
        return np.concatenate((data.qpos, data.qvel)).copy()

    assert np.array_equal(rasto(), rasto())


def test_aero_caminho_rapido_igual_ao_vetorizado(dr):
    """`Aerodinamica.fatores` (escalares, caminho quente) = as funções vetorizadas, sem o ruído do VRS."""
    hw = dr.hardware()
    a = dr.Aerodinamica(hw)
    rng = np.random.default_rng(0)
    for _ in range(50):
        alt = rng.uniform(0.05, 3.0, 4)
        va = rng.uniform(-6.0, 4.0, 4)
        w = rng.uniform(0.2, 1.5, 4) * a.omega_h
        kt, kq, det = a.fatores(alt, va, w, 0.002, None)
        g = dr.ganho_solo(alt, a.raio, a.d_vizinhos, a.b_opostos)
        kti, kqi = a.fator_inflow(va, w)
        kv = a.fator_vrs(va, hw.kf * w ** 2 * g * kti, 0.002, None)
        assert np.allclose(det["solo"], g, rtol=1e-12, atol=1e-12)
        assert np.allclose(kq, kqi, rtol=1e-12, atol=1e-12)
        assert np.allclose(kt, g * kti * kv, rtol=1e-12, atol=1e-12)


def test_site_usa_as_constantes_do_ambiente_real():
    """O site (`site/src/lib/sim.ts`, `sensores.ts`) mostra os setpoints de taxa, converte o giroscópio e conta
    os canais com as MESMAS constantes do `env_real.py` — lidas do código-fonte (sem importar gym/torch).
    Regressão de 2026-10-10: o site mostrava ±2,5/2,5/1,5 rad/s com o ambiente a usar 2/2/1."""
    import re

    exp = ROOT / "experiments" / "09_drone_hover_rl"
    env = (exp / "env_real.py").read_text(encoding="utf-8")
    sim = (exp / "site" / "src" / "lib" / "sim.ts").read_text(encoding="utf-8")
    sensores = (exp / "site" / "src" / "lib" / "sensores.ts").read_text(encoding="utf-8")

    def numeros(texto: str) -> list[float]:
        return [float(x) for x in texto.split(",")]

    taxa_env = numeros(re.search(r"^TAXA_MAX = np\.array\(\[([^\]]+)\]\)", env, re.M).group(1))
    taxa_site = numeros(re.search(r"TAXA_MAX_CTBR: readonly \[number, number, number\] = \[([^\]]+)\]",
                                  sim).group(1))
    assert taxa_site == taxa_env
    assert float(re.search(r"export const ESCALA_GIRO_OBS = ([0-9.]+)", sensores).group(1)) == \
        float(re.search(r"^ESCALA_GIRO = ([0-9.]+)", env, re.M).group(1))
    assert int(re.search(r"export const N_OBS_REAL = (\d+)", sim).group(1)) == \
        int(re.search(r"^OBS_ATOR_DIM = (\d+)", env, re.M).group(1))
