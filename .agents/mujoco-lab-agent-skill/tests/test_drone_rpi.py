"""Regressão da camada `lab.drone_rpi` (o drone REAL do dono: peças do catálogo → física) — CPU, sem gym/torch.

Contratos fixados (fórmulas fechadas; a validação completa é o `experiments/09_drone_hover_rl/valida_real.py`):

  · todos os builds de `models/drone_rpi/builds.json` resolvem, compilam e têm massa = Σ orçamento das peças;
  · motor BLDC: o regime integrado é a raiz da quadrática e T_max = kf·ω_max² decresce com a tensão;
  · bateria: contagem de Coulomb exata e queda I·R₀ coerente com a tensão aberta;
  · efeito de solo (Sanchez-Cuevas 2017) ≥ +15 % a meio diâmetro e ≈ 1 longe do chão;
  · com as flags aerodinâmicas desligadas o voo é bit-idêntico entre corridas (aerodinâmica base).
"""
from __future__ import annotations

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


def test_efeito_de_solo(dr):
    hw = dr.hardware()
    r = hw.helice.raio
    g_perto = float(dr.ganho_solo(r, r, hw.frame.wheelbase / np.sqrt(2), hw.frame.wheelbase))
    g_longe = float(dr.ganho_solo(5.0, r, hw.frame.wheelbase / np.sqrt(2), hw.frame.wheelbase))
    assert g_perto >= 1.15
    assert abs(g_longe - 1.0) < 2e-3


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
