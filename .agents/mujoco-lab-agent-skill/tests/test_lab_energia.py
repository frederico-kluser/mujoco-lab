"""Regressão do parâmetro `energia` de `lab.spot.carregar` / `lab.crazyflie.carregar` (CPU, sem jax/torch).

Contrato fixado aqui:

  · `carregar()` sem argumentos → `mjENBL_ENERGY` LIGADA e `data.energy` a produzir valores reais
    (os experimentos `07_spot_motores`/`08_crazyflie_motores` dependiam disso — removidos em 2026-10-08,
    histórico no git; o contrato mantém-se: `mjkit.record` regista pe/ke);
  · `carregar(energia=False)` → flag DESLIGADA e `data.energy` a ZEROS — é o que o MJX exige
    (`mjx.put_model` não implementa a flag), mas o registro de energia sai a zero em silêncio;
  · as chamadas posicionais antigas (`carregar(True)`, `carregar(True, True)`) continuam válidas.
"""
from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pytest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODELOS = ("spot", "crazyflie")
PASSOS = 50  # 0,1 s de simulação: chega para haver potencial/cinética != 0


def _lab(nome: str):
    """Módulo `lab.<nome>` — import tardio para o `mjkit` fixar MUJOCO_GL antes do mujoco."""
    return importlib.import_module(f"lab.{nome}")


def _carregar(nome: str, **kw):
    """(mujoco, model, data) do robô `nome`."""
    import mujoco

    model, data = _lab(nome).carregar(**kw)
    return mujoco, model, data


def _energia_ligada(mujoco, model) -> bool:
    return bool(int(model.opt.enableflags) & int(mujoco.mjtEnableBit.mjENBL_ENERGY))


def _simula(mujoco, model, data, passos: int = PASSOS):
    for _ in range(passos):
        mujoco.mj_step(model, data)
    mujoco.mj_forward(model, data)  # sem isto a energia ainda reflete o estado anterior ao último passo
    return data


@pytest.mark.parametrize("nome", MODELOS)
def test_default_liga_energia(nome):
    """(a) `carregar()` sem argumentos mantém a flag ligada e a energia com valores reais."""
    mujoco, model, data = _carregar(nome)
    assert _energia_ligada(mujoco, model)
    pot, cin = _simula(mujoco, model, data).energy
    assert pot > 0.0  # potencial gravítica: os dois robôs estão acima do solo
    assert abs(pot) + abs(cin) > 0.0


@pytest.mark.parametrize("nome", MODELOS)
def test_energia_false_zera_energy(nome):
    """(b) `energia=False` (preparação para o MJX) desliga a flag e deixa `data.energy` a zeros."""
    mujoco, model, data = _carregar(nome, energia=False)
    assert not _energia_ligada(mujoco, model)
    assert list(_simula(mujoco, model, data).energy) == [0.0, 0.0]


@pytest.mark.parametrize("nome", MODELOS)
def test_retrocompatibilidade_posicional(nome):
    """(c) as chamadas posicionais antigas seguem válidas e a ordem dos parâmetros não mudou."""
    mujoco, model, data = _carregar(nome, energia=True)
    m_pos, d_pos = _lab(nome).carregar(True, True)  # cena, sensores — posicional, como antes
    for m, d in ((model, data), (m_pos, d_pos)):
        assert _energia_ligada(mujoco, m)
        assert m.nsensor > 0
        assert d.energy[0] != 0.0

    assinatura = inspect.signature(_lab(nome).carregar)
    esperado = ["cena", "sensores", "keyframe"] + (["momentos"] if nome == "crazyflie" else []) + ["energia"]
    # Os parâmetros ANTIGOS mantêm nome, ordem e predefinição; params novos só podem entrar NO FIM
    # (`crazyflie` ganhou `helices` em 2026-10-09 — animação visual, desligada por omissão).
    assert list(assinatura.parameters)[: len(esperado)] == esperado
    assert list(assinatura.parameters)[len(esperado):] == (["helices"] if nome == "crazyflie" else [])
    assert assinatura.parameters["energia"].default is True
    for extra in list(assinatura.parameters)[len(esperado):]:
        assert assinatura.parameters[extra].default is False
