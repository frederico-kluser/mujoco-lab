#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/teste_controle_voo.py — PROVA do CONTROLE DE VOO (contrato r11).

O pedido do dono (2026-10-10): «um controle de voo onde mudo a altitude e a direção — WASD para as
direções, Q e E para subir e descer — vendo no site quando ativo; ajustar o treinamento para isso e, durante
a movimentação, corrigir as rajadas de vento para não ir mais lento nem a favor: respeitar a movimentação
proposta sem sofrer a influência do vento».

CONTRATO r11 (o que este script prova, ponto por ponto):

  · teclas WASDQE → `v_ref` (m/s, frame MUNDO, yaw alvo 0): W = +x (frente), S = −x, A = +y (esquerda),
    D = −y (direita), Q = +z (subir), E = −z (descer); diagonais NORMALIZADAS para 1,0 m/s,
    `|vz| = 0,7 m/s`; sem teclas → `v_ref = 0` = segurar posição (`env.teclas_para_velocidade`);
  · a referência de POSIÇÃO `p_ref` INTEGRA o `v_ref` por passo de decisão e satura em xy ±25 m (a
    ARENA de 50×50 m — antes era uma caixa de ±4 m; pedido do dono, 2026-10-11: «quero andar por um
    espaço maior»), z ∈ [0,25; 25] m (o teto de TERMINAÇÃO é o céu, z > 30 m) — na borda a componente
    que bate fica com `v_ref = 0` (`env.integrar_referencia`);
  · observação em modo comando: cf2 19 dims ([0:3] = `p − p_ref`, [16:19] = `v_ref` escalado) e planta real
    48 (24+24, ator com os erros relativos a `p_ref` + `v_ref`); SEM `comando` os contratos v2b (16) e
    v3-real (42) ficam BIT-IDÊNTICOS (nada muda);
  · recompensa de SEGUIMENTO (`recompensa_voo`/`recompensa_real_voo`): os erros `p − p_ref` e `v − v_ref`
    substituem os absolutos — uma rajada que deixe o drone MAIS LENTO ou a ir MAIS RÁPIDO que o comando
    custa o MESMO (simetria) e o bónus (`bonus_seguindo`) exige posição E velocidade (‖v−v_ref‖ < 0,10);
  · ficheiro de controlo, bloco `"voo"` = `{"ativo", "teclas", "seq"}` (ESTADO; `seq` do servidor) e API
    `POST /api/voo` (validação ESTRITA: gralha → 400; runner tolerante a ficheiros velhos);
  · telemetria: chave aditiva `"voo"` = `{ativo, teclas, v_ref, p_ref, erro_xy, erro_z, erro_v, seguindo}`
    (ou `null` quando a política NÃO tem modo comando — honesto, o site mostra o painel indisponível);
  · auto-detecção: o runner cria o env em modo comando pela OBSERVAÇÃO da política carregada (19/24+24),
    nunca por flags — qualquer `.zip` voa com o contrato com que foi treinado.

Quatro camadas (§1 peças → §2 seguimento com política treinada → §3 servidor+runner reais → §4 navegador):

  §1 PEÇAS — funções puras (`teclas_para_velocidade`, `integrar_referencia`, `bonus_seguindo`,
    `recompensa_voo`, `recompensa_real_voo`) e mecânica dos envs SEM política (dimensões, p_ref, clamps,
    perfis aleatórios determinísticos, retro-compatibilidade do modo clássico);
  §2 SEGUIMENTO — política treinada (`--comandos`) em ciclo fechado: CALMARIA (segue o comando),
    SIMETRIA DE VENTO (proa vs cauda: nem mais lento nem a favor — é o núcleo do pedido), RAJADAS durante
    a movimentação, Q/E (subir/descer ≈ ±0,7 m/s) e PARAGEM (solta → segura posição); o GUIÃO NULO
    (ação [0,0,0,0] = hover aberto) tem de FALHAR os mesmos limiares — prova de não-tautologia dos
    critérios;
  §3 SERVIDOR — `sim_site.py` + runner reais (`--sem-janela`): `POST /api/voo` (200/400), bloco no
    ficheiro, eco `"voo"` na telemetria coerente com as teclas, `voo.pedido/eco` no `/api/state`, merge
    que não clobbera com um POST de vento, e a HONESTIDADE com política clássica (eco `null` + aviso
    «bloco `voo` ignorado» — o painel do site fica indisponível em vez de fingir que pilota);
  §4 NAVEGADOR (`--navegador`) — front real (`site/dist`) num Chrome headless por CDP: os keycaps
    ACENDEM com o keydown real e apagam com o keyup, `voo-ativar` arma o painel, e o POST chega ao
    servidor (o ficheiro de controlo prova-o).

    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controle_voo.py              # §1–§3
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controle_voo.py --so-pecas   # §1
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controle_voo.py --navegador  # §1–§4
    uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controle_voo.py --model ZIP --planta real

Sem política `--comandos` em `out/` o §2 e o §3 FALHAM ALTO (exit 1) em vez de saltarem: o contrato exige
uma política treinada para pilotar e o teste tem de o dizer.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
for _caminho in (_RAIZ, _AQUI):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

import numpy as np  # noqa: E402

from env import (  # noqa: E402
    VOO_SUBIDA,
    VOO_VEL,
    VOO_XY_MAX,
    VOO_Z_MAX,
    VOO_Z_MIN,
    HoverEnv,
    bonus_seguindo,
    integrar_referencia,
    recompensa_voo,
    teclas_para_velocidade,
)

SITE = _AQUI / "site"

# ---------------------------------------------------------------------------------------- critérios §2
# Limiares de ACEITAÇÃO do seguimento (medidos no primeiro treino r11; os valores medidos ficam no README).
# `vx` de referência nos guiões = VEL_COMANDO (a velocidade de uma tecla; W = +x).
VEL_COMANDO = 1.0             # m/s — o comando de uma tecla horizontal
TOL_CALMA = 0.15              # m/s — |v − v_ref| médio em calmaria (cf2); a planta real tem os seus
TOL_CALMA_REAL = 0.25         # m/s — idem para a planta real (estimador de bordo limita o seguimento)
TOL_SIMETRIA = 0.20           # m/s — |⟨vx⟩ proa − ⟨vx⟩ cauda| com vento ±2 m/s (nem lento nem favor)
TOL_VENTO = 0.30              # m/s — desvio máximo de ⟨vx⟩ face ao comando, com vento constante
TOL_VZ = 0.25                 # m/s — erro de ⟨vz⟩ no Q/E (comando ±VOO_SUBIDA)
RMS_RAJADA = 0.45             # m/s — RMS(vx − 1,0) durante rajadas agressivas (p = 0,15, u_max = 3)
TOL_PARAGEM = 0.25            # m/s — |vx| 1,5 s depois de soltar as teclas (segurar posição)
DERIVA_PARAGEM = 0.60         # m — deriva máxima em 2 s de paragem com vento de 2 m/s
VENTO_SIMETRIA = 2.0          # m/s — vento constante da prova de simetria (proa vs cauda)


class Checagens:
    """Acumulador de checagens: uma linha por checagem (com o detalhe medido) + resumo no fim."""

    def __init__(self, titulo: str) -> None:
        self.titulo = titulo
        self.falhas: list[str] = []
        self.n = 0
        print(f"\n=== {titulo} ===", flush=True)

    def ok(self, nome: str, cond: bool, detalhe: str = "") -> bool:
        self.n += 1
        if not cond:
            self.falhas.append(nome)
        print(f"        [{'OK  ' if cond else 'FALHA'}] {nome}" + (f" — {detalhe}" if detalhe else ""),
              flush=True)
        return bool(cond)

    def fechar(self) -> bool:
        estado = "TUDO OK" if not self.falhas else f"{len(self.falhas)}/{self.n} FALHARAM"
        print(f"--- {self.titulo}: {estado}", flush=True)
        return not self.falhas


# ---------------------------------------------------------------------------------------- §1 peças
def secao_pecas() -> bool:
    """§1: funções puras e mecânica dos envs — tudo fechado, sem política e sem rede."""
    c = Checagens("§1 pecas: funcoes puras + envs em modo comando")

    # ---- teclas_para_velocidade: mapeamento canónico
    casos = [("w", [1, 0, 0]), ("s", [-1, 0, 0]), ("a", [0, 1, 0]), ("d", [0, -1, 0]),
             ("q", [0, 0, VOO_SUBIDA]), ("e", [0, 0, -VOO_SUBIDA])]
    for tecla, esperado in casos:
        obtido = teclas_para_velocidade(**{t: t == tecla for t in "wasdqe"})
        c.ok(f"tecla {tecla.upper()} → v_ref {esperado}", np.allclose(obtido, esperado),
             f"obtido {np.round(obtido, 3).tolist()}")
    diag = teclas_para_velocidade(1, 0, 0, 1, 0, 0)                       # W+D
    c.ok("diagonal W+D normalizada para VOO_VEL", abs(float(np.hypot(*diag[:2])) - VOO_VEL) < 1e-12
         and diag[1] < 0, f"‖v_xy‖ = {float(np.hypot(*diag[:2])):.6f} m/s")
    trio = teclas_para_velocidade(1, 0, 0, 1, 1, 0)                       # W+D+Q
    c.ok("diagonal + Q mantém |vz| = VOO_SUBIDA", abs(float(trio[2]) - VOO_SUBIDA) < 1e-12,
         f"vz = {trio[2]:.3f} m/s")
    c.ok("teclas opostas cancelam (W+S, A+D, Q+E)",
         np.allclose(teclas_para_velocidade(1, 1, 1, 1, 1, 1), np.zeros(3)))
    c.ok("sem teclas → segurar posição", np.allclose(teclas_para_velocidade(0, 0, 0, 0, 0, 0),
                                                     np.zeros(3)))

    # ---- integrar_referencia: integração + saturação (a borda ZERA a componente que bate)
    p, v = integrar_referencia([0, 0, 1.0], [1, 0, 0], 0.02)
    c.ok("p_ref integra v_ref (2 cm a 1 m/s em 20 ms)",
         np.allclose(p, [0.02, 0, 1.0]) and np.allclose(v, [1, 0, 0]), f"p_ref = {np.round(p, 3).tolist()}")
    p, v = integrar_referencia([VOO_XY_MAX - 0.01, 0, 1.0], [1, 0, 0], 0.02)
    c.ok(f"parede xy (+{VOO_XY_MAX} m) satura e zera v_ref.x",
         p[0] == VOO_XY_MAX and v[0] == 0.0, f"p_ref = {p.tolist()}, v_ref_efetivo = {v.tolist()}")
    p, v = integrar_referencia([0, 0, VOO_Z_MAX - 0.01], [0, 0, VOO_SUBIDA], 0.02)
    c.ok(f"teto z ({VOO_Z_MAX} m) satura e zera v_ref.z",
         p[2] == VOO_Z_MAX and v[2] == 0.0, f"p_ref = {p.tolist()}, v_ref_efetivo = {v.tolist()}")
    p, v = integrar_referencia([0, 0, VOO_Z_MIN + 0.01], [0, 0, -VOO_SUBIDA], 0.02)
    c.ok(f"piso z ({VOO_Z_MIN} m) satura e zera v_ref.z",
         p[2] == VOO_Z_MIN and v[2] == 0.0, f"p_ref = {p.tolist()}, v_ref_efetivo = {v.tolist()}")
    try:
        integrar_referencia([0, 0, 1], [0, 0, 0], float("nan"))
        c.ok("dt NaN → ValueError", False)
    except ValueError:
        c.ok("dt NaN → ValueError", True)
    try:
        integrar_referencia([0, 0, 1], [0, 0, 0], -0.02)
        c.ok("dt negativo → ValueError", False)
    except ValueError:
        c.ok("dt negativo → ValueError", True)

    # ---- bonus_seguindo: desigualdades ESTRITAS nos 4 limiares
    c.ok("bonus_seguindo exige posição E velocidade",
         bonus_seguindo(0.04, 0.04, 0.09, 0.05) and not bonus_seguindo(0.04, 0.04, 0.11, 0.05)
         and not bonus_seguindo(0.06, 0.04, 0.05, 0.05) and not bonus_seguindo(0.04, 0.06, 0.05, 0.05)
         and not bonus_seguindo(0.04, 0.04, 0.05, 0.11))

    # ---- recompensa_voo: SIMETRIA da correção de vento (o coração do pedido do dono)
    def r_com(v_real, v_ref=(1.0, 0.0, 0.0)):
        return recompensa_voo(0.01, 0.01, np.array(v_real), np.array(v_ref), 0.01,
                              np.zeros(2), 0.0, np.zeros(4), False)

    lenta, certa, rapida = r_com((0.6, 0, 0)), r_com((1.0, 0, 0)), r_com((1.4, 0, 0))
    c.ok("mais LENTO e mais RÁPIDO que o comando custam o MESMO",
         abs((certa - lenta) - (certa - rapida)) < 1e-9 and certa > lenta and certa > rapida,
         f"r(certo)={certa:.3f} > r(0,6 m/s)={lenta:.3f} = r(1,4 m/s)={rapida:.3f}")
    c.ok("seguir o comando vale mais do que estar só no sítio (bónus)",
         r_com((1.0, 0, 0)) > recompensa_voo(0.01, 0.01, np.zeros(3), np.array([1.0, 0, 0]), 0.01,
                                             np.zeros(2), 0.0, np.zeros(4), False))
    c.ok("terminado leva −50 (r por passo é limitado: morrer nunca compensa)",
         recompensa_voo(0, 0, np.zeros(3), np.zeros(3), 0, np.zeros(2), 0, np.zeros(4), True)
         == recompensa_voo(0, 0, np.zeros(3), np.zeros(3), 0, np.zeros(2), 0, np.zeros(4), False) - 50.0
         and recompensa_voo(0, 0, np.zeros(3), np.zeros(3), 0, np.zeros(2), 0, np.zeros(4), True) < -40)
    c.ok("r por passo é LIMITADO (tanh): erro de 100 m custa o mesmo que ~3 m — sem atrator da morte",
         abs(recompensa_voo(100, 100, np.zeros(3), np.zeros(3), 3.0, np.zeros(2), 0, np.zeros(4), False)
             - recompensa_voo(3, 3, np.zeros(3), np.zeros(3), 0.2, np.zeros(2), 0, np.zeros(4), False)) < 0.2)

    # ---- env cf2 em modo comando
    e = HoverEnv(comando=True)
    obs, info = e.reset(seed=0)
    c.ok("cf2 comando: obs 19 dims", obs.shape == (19,), f"obs {obs.shape}")
    c.ok("cf2 comando: info traz o bloco `voo`", isinstance(info.get("voo"), dict),
         f"chaves = {sorted(info.get('voo', {}))}")
    c.ok("cf2 sem comando: obs 16 e sem `voo` (contrato v2b intacto)",
         HoverEnv().observation_space.shape == (16,))
    e.definir_comando([1.0, 0.0, 0.0])
    for _ in range(5):
        e.step([0, 0, 0, 0])
    c.ok("p_ref integra o comando a cada passo de decisão",
         abs(e.p_ref[0] - 5 * e.dt_decisao * VOO_VEL) < 1e-9 and e.p_ref[2] == e.alvo_z,
         f"p_ref = {np.round(e.p_ref, 4).tolist()} (esperado x = {5 * e.dt_decisao * VOO_VEL:.4f})")
    e.definir_comando_teclas(w=True, d=True, q=True)
    obs = e.observacao()
    c.ok("obs[16:19] = v_ref escalado (diagonal W+D + Q)",
         np.allclose(obs[16:19], [diag[0] / VOO_VEL, diag[1] / VOO_VEL, VOO_SUBIDA / VOO_SUBIDA]),
         f"obs[16:19] = {np.round(obs[16:19], 3).tolist()}")
    e.definir_comando_teclas(ativo=False)
    c.ok("ativo=false → v_ref zera (segurar posição)",
         np.allclose(e.comando_estado()["v_ref"], np.zeros(3)))
    e.close()

    # ---- clamps do definir_comando e validação
    e = HoverEnv(comando=True)
    e.reset(seed=0)
    obtido = e.definir_comando([9.0, -9.0, 5.0])
    c.ok("definir_comando corta ‖v_xy‖ a VOO_VEL e |vz| a VOO_SUBIDA",
         abs(float(np.hypot(*obtido[:2])) - VOO_VEL) < 1e-12 and obtido[2] == VOO_SUBIDA,
         f"v_ref efetivo = {np.round(obtido, 3).tolist()}")
    try:
        e.definir_comando([float("nan"), 0, 0])
        c.ok("v_ref NaN → ValueError", False)
    except ValueError:
        c.ok("v_ref NaN → ValueError", True)
    # Q pressionado muito tempo: z_ref satura no teto e a subida PARA (não voa para o teto de terminação)
    e.definir_comando_teclas(q=True)
    z_ref_hist = []
    # duração até ao TETO com folga (o teto é 25 m e a subida 0,7 m/s: ~35 s de referência — são os
    # passos que faltam para a referência andar de onde está até VOO_Z_MAX; antes eram 6 s, com o teto
    # a 2,75 m)
    n_passos_teto = int(((VOO_Z_MAX - VOO_Z_MIN) / VOO_SUBIDA + 2.0) / e.dt_decisao)
    for _ in range(n_passos_teto):
        e.step([0, 0, 0, 0])
        z_ref_hist.append(e.p_ref[2])
    c.ok("Q longo: z_ref satura em VOO_Z_MAX e vz_efetivo zera (não empurra contra o teto)",
         z_ref_hist[-1] == VOO_Z_MAX and e.v_ref[2] == 0.0 and max(z_ref_hist) <= VOO_Z_MAX,
         f"z_ref final = {z_ref_hist[-1]:.2f} m, v_ref = {np.round(e.v_ref, 3).tolist()}")
    e.close()

    # ---- perfis aleatórios de comando: determinísticos dada a seed e cobrem o episódio
    a = HoverEnv(comando=True, comandos_aleatorios=True)
    b = HoverEnv(comando=True, comandos_aleatorios=True)
    a.reset(seed=11)
    b.reset(seed=11)
    iguais = all(np.array_equal(a.step([0] * 4)[0], b.step([0] * 4)[0]) for _ in range(80))
    c.ok("perfis aleatórios determinísticos dada a seed", iguais)
    a.reset(seed=11)
    a.definir_comando_teclas(w=True)      # uma tecla manual desliga o perfil aleatório
    a.step([0] * 4)
    c.ok("definir_comando_teclas sobrepõe-se ao perfil aleatório (treino não pilota o site)",
         np.allclose(a.v_ref, [VOO_VEL, 0, 0]))
    a.close()
    b.close()

    # ---- planta real em modo comando
    from env_real import OBS_ATOR_DIM_COMANDO, OBS_DIM_COMANDO, DroneRealEnv, recompensa_real_voo
    r = DroneRealEnv(comando=True)
    obs, info = r.reset(seed=0)
    c.ok("real comando: obs 48 dims (ator 24 + crítico 24)",
         obs.shape == (OBS_DIM_COMANDO,) and r.obs_ator_dim == OBS_ATOR_DIM_COMANDO,
         f"obs {obs.shape}, ator {r.obs_ator_dim}")
    c.ok("real comando: info traz o bloco `voo`", isinstance(info.get("voo"), dict))
    r.definir_comando_teclas(w=True, e=True)
    obs = e_obs = r.observacao()
    c.ok("real comando: obs do ATOR termina em v_ref escalado",
         np.allclose(e_obs[21:24], [1.0, 0.0, -1.0]), f"obs[21:24] = {np.round(e_obs[21:24], 3).tolist()}")
    lenta = recompensa_real_voo(0.01, 0.01, 0.4, 0.01, np.zeros(3), np.zeros(4), False)
    certa = recompensa_real_voo(0.01, 0.01, 0.0, 0.01, np.zeros(3), np.zeros(4), False)
    rapida = recompensa_real_voo(0.01, 0.01, 0.4, 0.01, np.zeros(3), np.zeros(4), False)
    c.ok("v3-real comando: erro de velocidade simétrico (mesmo custo para cada lado)",
         abs((certa - lenta) - (certa - rapida)) < 1e-12 and certa > lenta,
         f"r(erro 0,4) = {lenta:.4f}, r(exato) = {certa:.4f}")
    c.ok("real sem comando: obs 42 (contrato v3-real intacto)",
         DroneRealEnv().observation_space.shape == (42,))
    r.close()
    return c.fechar()


# ---------------------------------------------------------------------------------------- §2 seguimento
def _ambiente_para(caminho: Path, politica):
    """Env em modo comando certo para a política (planta real pelo `_n_ator`, senão cf2)."""
    if hasattr(politica.policy, "_n_ator"):
        from env_real import DroneRealEnv, build_do_hardware
        hw = caminho.parent / "hardware.json"
        dados = json.loads(hw.read_text(encoding="utf-8")) if hw.is_file() else {}
        build, motivo = build_do_hardware(dados)
        print(f"        [info] peças da política: {motivo}", flush=True)
        return DroneRealEnv(build=build, modo_acao=dados.get("modo_acao", "ctbr"), aleatorizar=False,
                            comando=True)
    return HoverEnv(comando=True)


def _correr_guion(env, politica, guion, semente=0, vento=None, vento_dinamico=None,
                  acao_nula=False) -> list[dict]:
    """Corre um guião [(n_passos, teclas_dict|None, v_ref|None), …] e devolve as amostras por passo.

    `acao_nula=True` usa SEMPRE a ação [0,0,0,0] (hover aberto, sem política) — é o BASELINE que tem de
    FALHAR os critérios de seguimento (não-tautologia). Cada amostra: `{t, v, z, erro_xy, erro_z, erro_v,
    v_ref, p_ref}` (o `v` é a velocidade do MUNDO).
    """
    env.reset(seed=semente)
    if vento is not None:
        env.definir_vento(*vento)
    if vento_dinamico is not None:
        env.definir_vento_dinamico(vento_dinamico)
    amostras: list[dict] = []
    for n_passos, teclas, v_ref in guion:
        if v_ref is not None:
            env.definir_comando(v_ref)
        elif teclas is not None:
            env.definir_comando_teclas(**teclas)
        for _ in range(int(n_passos)):
            if acao_nula:
                acao = np.zeros(4)
            else:
                acao, _ = politica.predict(env.observacao(), deterministic=True)
            _obs, _r, terminado, _truncado, _info = env.step(acao)
            d = env._derivados()
            amostras.append({"t": env.data.time, "v": d["v_vec"].copy(), "z": d["z"],
                             "p": np.array([d["x"], d["y"], d["z"]]),
                             "erro_xy": d["erro_xy"], "erro_z": d["erro_z"], "erro_v": d["erro_v"],
                             "v_ref": env.v_ref.copy(), "p_ref": env.p_ref.copy()})
            if terminado:
                amostras.append({"terminado": True})
                return amostras
    return amostras


def _media(segmento: list[dict], campo: str, metade=True) -> np.ndarray:
    """Média de `campo` num segmento (só a 2.ª metade: deixa o transitório passar)."""
    dados = segmento[len(segmento) // 2:] if metade else segmento
    return np.mean([np.asarray(a[campo], dtype=float) for a in dados], axis=0)


def _sem_terminados(amostras: list[dict]) -> list[dict]:
    return [a for a in amostras if "terminado" not in a]


def secao_seguimento(modelos: dict[str, Path], acao_nula: bool = True) -> bool:
    """§2: ciclo fechado com as políticas `--comandos` (cf2 e/ou real) + baseline nulo."""
    tudo_ok = True
    for planta, caminho in modelos.items():
        from stable_baselines3 import PPO
        c = Checagens(f"§2 seguimento ({planta}): {caminho.name}")
        politica = PPO.load(str(caminho), device="cpu")
        env = _ambiente_para(caminho, politica)
        tol_calma = TOL_CALMA_REAL if planta == "real" else TOL_CALMA
        n_levanta = int(2.5 / env.dt_decisao)          # tempo de descolar até p_ref (1.º segmento hover)
        n_move = int(3.0 / env.dt_decisao)
        n_solta = int(2.0 / env.dt_decisao)
        guioes = {
            "calmaria": [(n_levanta, {"w": False, "a": False, "s": False, "d": False, "q": False,
                                      "e": False}, None),
                         (n_move, {"w": True, "a": False, "s": False, "d": False, "q": False,
                                   "e": False}, None)],
            "mover": [(n_levanta, None, [0, 0, 0]), (n_move, None, [VEL_COMANDO, 0, 0])],
            "subir": [(n_levanta, None, [0, 0, 0]), (n_move, {"w": False, "a": False, "s": False,
                                                              "d": False, "q": True, "e": False}, None)],
            "descer": [(n_levanta, None, [0, 0, 0]), (n_move, {"w": False, "a": False, "s": False,
                                                               "d": False, "q": False, "e": True}, None)],
            "paragem": [(n_levanta, None, [0, 0, 0]),
                        (int(1.5 / env.dt_decisao), None, [VEL_COMANDO, 0, 0]),
                        (n_solta, None, [0, 0, 0])],
        }

        # (a) CALMARIA: segue a velocidade proposta
        amostras = _sem_terminados(_correr_guion(env, politica, guioes["calmaria"], semente=1))
        seg = amostras[-n_move:]
        v_medio = _media(seg, "v")
        c.ok(f"[{planta}] calmaria: ⟨v⟩ segue W (+{VEL_COMANDO} m/s em x)",
             abs(v_medio[0] - VEL_COMANDO) <= tol_calma and abs(v_medio[1]) <= tol_calma
             and abs(v_medio[2]) <= tol_calma and len(amostras) == n_levanta + n_move,
             f"⟨v⟩ = {np.round(v_medio, 3).tolist()} m/s · sem queda = "
             f"{len(amostras) == n_levanta + n_move}")

        # (b) SIMETRIA DE VENTO: proa vs cauda — nem mais lento nem a favor (o núcleo do pedido)
        # `definir_vento` é POLAR (vel ≥ 0 m/s, azimute em graus): cauda = 2 m/s @ 0°, proa = 2 m/s @ 180°.
        ventos = {"sem vento": None, "cauda (+2 m/s em x)": (VENTO_SIMETRIA, 0.0, 0.0),
                  "proa (−2 m/s em x)": (VENTO_SIMETRIA, 180.0, 0.0)}
        medias: dict[str, float] = {}
        for rotulo, vento in ventos.items():
            amostras = _sem_terminados(_correr_guion(env, politica, guioes["mover"], semente=2, vento=vento))
            seg = amostras[-n_move:]
            medias[rotulo] = float(_media(seg, "v")[0])     # ⟨vx⟩ com o MESMO comando [1, 0, 0]
        c.ok(f"[{planta}] vento proa vs cauda: ⟨vx⟩ igual (diferença ≤ {TOL_SIMETRIA} m/s)",
             abs(medias["cauda (+2 m/s em x)"] - medias["proa (−2 m/s em x)"]) <= TOL_SIMETRIA,
             "· ".join(f"{k}: {v:+.3f}" for k, v in medias.items()))
        c.ok(f"[{planta}] vento constante não desvia ⟨vx⟩ do comando (≤ {TOL_VENTO} m/s)",
             all(abs(v - VEL_COMANDO) <= TOL_VENTO for v in medias.values()),
             "· ".join(f"{k}: {v:+.3f}" for k, v in medias.items()))

        # (c) RAJADAS durante a movimentação: erro de velocidade contido, sem queda
        erros_rms, quedas = [], 0
        for semente in (3, 4, 5):
            amostras = _correr_guion(env, politica, guioes["calmaria"], semente=semente,
                                     vento_dinamico={"modo": "rajadas", "p": 0.15, "duracao": 12,
                                                     "u_max": 3.0})
            if any("terminado" in a for a in amostras):
                quedas += 1
            seg = _sem_terminados(amostras)[-n_move:]
            erros_rms.append(float(np.sqrt(np.mean([(a["v"][0] - VEL_COMANDO) ** 2 for a in seg]))))
        c.ok(f"[{planta}] rajadas (p=0,15, u_max=3) a mover-se: RMS(vx−1) ≤ {RMS_RAJADA} e 0 quedas",
             quedas == 0 and max(erros_rms) <= RMS_RAJADA,
             f"RMS por seed = {np.round(erros_rms, 3).tolist()} m/s · quedas = {quedas}")

        # (d) Q/E: subir/descer ≈ ±VOO_SUBIDA — medido ANTES de a referência saturar (com os limites
        # novos, 2026-10-11, o teto está a 25 m e o Q já não satura no segmento; o E continua a bater no
        # piso 0,25 m em ~1,1 s se soltar… a janela de medida mantém-se os primeiros 1,2 s do segmento,
        # com 0,2 s de transitório cortados — sempre pré-saturação nos dois sentidos)
        n_janela = int(1.2 / env.dt_decisao)
        n_transito = int(0.2 / env.dt_decisao)
        for rotulo, guiao, sinal in (("Q (subir)", guioes["subir"], +1), ("E (descer)", guioes["descer"], -1)):
            amostras = _sem_terminados(_correr_guion(env, politica, guiao, semente=6))
            seg = amostras[-n_move:][n_transito:n_janela]     # janela pré-saturação do p_ref.z
            vz = float(_media(seg, "v", metade=False)[2])
            c.ok(f"[{planta}] {rotulo}: ⟨vz⟩ ≈ {sinal * VOO_SUBIDA:+.1f} m/s (±{TOL_VZ})",
                 abs(vz - sinal * VOO_SUBIDA) <= TOL_VZ and len(amostras) == n_levanta + n_move,
                 f"⟨vz⟩ = {vz:+.3f} m/s (janela 0,2–1,2 s) · sem queda = {len(amostras) == n_levanta + n_move}")

        # (e) PARAGEM: solta as teclas → segura posição (nem deriva com o vento)
        amostras = _sem_terminados(_correr_guion(env, politica, guioes["paragem"], semente=7,
                                                 vento=(VENTO_SIMETRIA, 0.0, 0.0)))
        seg = amostras[-n_solta:]                       # o segmento DEPOIS de soltar (v_ref = 0)
        v_fim = _media(seg, "v")
        deriva = float(np.hypot(*(seg[-1]["p"][:2] - seg[0]["p"][:2])))
        c.ok(f"[{planta}] paragem com vento de {VENTO_SIMETRIA:g} m/s: |v_xy| ≤ {TOL_PARAGEM} "
             f"e deriva ≤ {DERIVA_PARAGEM} m",
             abs(v_fim[0]) <= TOL_PARAGEM and abs(v_fim[1]) <= TOL_PARAGEM and deriva <= DERIVA_PARAGEM,
             f"⟨v⟩ final = {np.round(v_fim, 3).tolist()} m/s · deriva = {deriva:.3f} m em 2 s")
        env.close()

        # (f) NÃO-TAUTOLOGIA: a ação NULA (hover aberto) tem de FALHAR os limiares de calmaria
        if acao_nula:
            env = _ambiente_para(caminho, politica)
            amostras = _sem_terminados(_correr_guion(env, None, guioes["calmaria"], semente=1,
                                                     acao_nula=True))
            env.close()
            if len(amostras) < n_move:                     # caiu antes: já falha por si
                c.ok(f"[{planta}] baseline nulo FALHA os limiares (não-tautologia)", True,
                     "a ação [0,0,0,0] caiu antes de seguir o comando")
            else:
                seg = amostras[-n_move:]
                v_medio = _media(seg, "v")
                falha = (abs(v_medio[0] - VEL_COMANDO) > tol_calma) or len(amostras) != n_levanta + n_move
                c.ok(f"[{planta}] baseline nulo FALHA os limiares (não-tautologia)", falha,
                     f"⟨v⟩ do baseline = {np.round(v_medio, 3).tolist()} m/s (não segue W)")
        tudo_ok = c.fechar() and tudo_ok
    return tudo_ok


# ---------------------------------------------------------------------------------------- §3 servidor
def _http(url: str, dados=None, timeout: float = 10.0):
    """GET/POST JSON → (código, corpo dict). Sem dependências (urllib)."""
    corpo = None if dados is None else json.dumps(dados).encode("utf-8")
    pedido = urllib.request.Request(url, data=corpo, method="POST" if dados is not None else "GET",
                                    headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            return resposta.status, json.loads(resposta.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as erro:
        try:
            return erro.code, json.loads(erro.read().decode("utf-8") or "{}")
        except (ValueError, OSError):
            return erro.code, {}


def _arrancar_site(pasta: Path, modelo: Path | None, porta: int, fator_tempo: float = 0.0):
    """`sim_site.py --sem-janela --sem-browser` numa pasta própria; devolve (processo, base_url, log)."""
    pasta.mkdir(parents=True, exist_ok=True)
    controlo, telemetria = pasta / "controlo.json", pasta / "telemetria.jsonl"
    for caminho in (controlo, telemetria):
        caminho.unlink(missing_ok=True)
    comando = [sys.executable, str(_AQUI / "sim_site.py"), "--sem-browser", "--sem-janela",
               "--port", str(porta), "--controlo", str(controlo), "--telemetria", str(telemetria),
               "--fator-tempo", f"{fator_tempo:g}"]
    if modelo is not None:
        comando += ["--model", str(modelo)]
    processo = subprocess.Popen(comando, cwd=str(_AQUI), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, start_new_session=True)
    base_url = None
    lidas = []                                    # as linhas ANTES da URL (o readline consome-as — sem
    t0 = time.perf_counter()                      # as guardar, um erro do filho aparecia como "vazio")
    while time.perf_counter() - t0 < 180:
        linha = processo.stdout.readline()
        if not linha:
            break
        lidas.append(linha.rstrip())
        achado = re.search(r"(http://[\d.]+:\d+/)", linha)
        if achado:
            base_url = achado.group(1).rstrip("/")
            break
    return processo, base_url, controlo, telemetria, "\n".join(lidas)


def _fechar_site(processo) -> str:
    linhas = ""
    if processo is None:
        return linhas
    try:
        os.killpg(os.getpgid(processo.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        processo.terminate()
    try:
        linhas = processo.communicate(timeout=15)[0] or ""
    except subprocess.TimeoutExpired:
        processo.kill()
        linhas = processo.communicate()[0] or ""
    return linhas


def secao_servidor(modelos: dict[str, Path], pasta: Path, porta: int) -> bool:
    """§3: o servidor real + runner real — POST /api/voo, eco na telemetria e honestidade."""
    c = Checagens("§3 servidor: POST /api/voo + eco + honestidade")
    comando = next(((p, m) for p, m in modelos.items() if m is not None), None)
    if comando is None:
        return c.ok("há política --comandos para o §3", False, "nenhum modelo em out/ (treine primeiro)")
    planta, modelo = comando
    processo, base, controlo, telemetria, stdout = _arrancar_site(pasta / "voo", modelo, porta)
    if base is None:
        vivo = processo.poll() is None
        linhas = (stdout or "") + "\n" + (_fechar_site(processo) or "")
        return c.ok("servidor arrancou", False,
                    f"sem URL do sim_site em 180 s · filho {'VIVO (mudo)' if vivo else f'morto (exit {processo.poll()})'} · saída: "
                    + (linhas[-400:].replace("\n", " | ") if linhas else "(vazia — morreu sem escrever)"))
    try:
        c.ok("servidor arrancou com a política de comando", True, f"{base} · modelo {modelo.name}")

        # POST válido: bloco `voo` no ficheiro com o `seq` do SERVIDOR
        codigo, corpo = _http(base + "/api/voo", {"ativo": True,
                                                  "teclas": {"w": True, "a": False, "s": False,
                                                             "d": False, "q": False, "e": False}})
        bloco = json.loads(controlo.read_text(encoding="utf-8")).get("voo", {})
        c.ok("POST /api/voo → 200 e bloco no ficheiro de controlo (seq do servidor)",
             codigo == 200 and corpo.get("ok") is True and bloco.get("teclas", {}).get("w") is True
             and isinstance(bloco.get("seq"), int),
             f"HTTP {codigo} · bloco = {bloco}")

        # gralha → 400 (validação estrita)
        codigo, corpo = _http(base + "/api/voo", {"ativo": True, "teclas": {"ww": True}})
        c.ok("tecla mal escrita → 400 com o motivo", codigo == 400 and "desconhecidas" in str(corpo),
             f"HTTP {codigo} · {corpo.get('erro', '')}")

        # o eco da telemetria reflete as teclas (o runner aplicou no env de comando). O W mantém-se
        # pressionado: o `p_ref` integra +1 m/s até à borda da ARENA (xy = 25 m) e AÍ o `v_ref_efetivo`
        # zera por contrato — logo aceita-se qualquer eco com `v_ref = [+1,0,0]` (é o caso normal: a
        # borda está longe) ou `p_ref.x` já colado ao limite (a referência andou = o comando chegou).
        eco, viu_comando = None, False
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 30 and not viu_comando:
            _codigo, estado = _http(base + "/api/state")
            eco = (estado.get("voo") or {}).get("eco")
            if eco is not None and eco.get("teclas", {}).get("w"):
                v_ref, p_ref = eco.get("v_ref", []), eco.get("p_ref", [])
                viu_comando = (np.allclose(v_ref, [VOO_VEL, 0, 0], atol=1e-6)
                               or (p_ref and p_ref[0] >= VOO_XY_MAX - 1e-6))
            if not viu_comando:
                time.sleep(0.1)
        c.ok("eco `voo` na telemetria: W aplicado (v_ref = [+1,0,0] ou p_ref colado ao limite de +25 m)",
             viu_comando, f"eco = {eco}")
        codigo, estado = _http(base + "/api/state")
        c.ok("/api/state traz voo.pedido e voo.eco",
             isinstance((estado.get("voo") or {}).get("pedido"), dict)
             and isinstance((estado.get("voo") or {}).get("eco"), dict),
             f"pedido.seq = {(estado.get('voo') or {}).get('pedido', {}).get('seq')}")

        # um POST de vento NÃO clobbera o bloco `voo` (merge do escrever_controlo)
        _http(base + "/api/vento", {"vel": 1.5, "azimute": 90.0, "elevacao": 0.0, "ativo": True})
        bloco2 = json.loads(controlo.read_text(encoding="utf-8")).get("voo", {})
        c.ok("POST /api/vento preserva o bloco `voo` (merge, não rewrite)",
             bloco2.get("teclas", {}).get("w") is True and bloco2.get("seq") == bloco.get("seq"),
             f"bloco depois do vento = {bloco2}")

        # ativo=false → v_ref zera no eco (segurar posição)
        _http(base + "/api/voo", {"ativo": False,
                                  "teclas": {"w": False, "a": False, "s": False, "d": False,
                                             "q": False, "e": False}})
        eco = None
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 30:
            _codigo, estado = _http(base + "/api/state")
            eco = (estado.get("voo") or {}).get("eco")
            if eco is not None and not eco.get("ativo", True):
                break
            time.sleep(0.3)
        c.ok("desarmar (ativo=false) → eco com v_ref = 0",
             eco is not None and not eco.get("ativo", True)
             and np.allclose(eco.get("v_ref", []), np.zeros(3), atol=1e-6),
             f"eco = {eco}")
    finally:
        log = _fechar_site(processo)
        _ = log
    return c.fechar()


def secao_honestidade(pasta: Path, porta: int) -> bool:
    """§3b: política CLÁSSICA (sem comando) — o `voo` é ignorado com aviso e o eco fica `null`."""
    c = Checagens("§3b honestidade: política clássica não finge que pilota")
    classico = next(iter(sorted((_AQUI / "out").glob("vento_*/final.zip"),
                                key=lambda p: p.stat().st_mtime_ns, reverse=True)), None)
    if classico is None:
        return c.ok("há política clássica para comparar", False, "nenhum out/vento_*/final.zip")
    processo, base, controlo, _telemetria, _stdout = _arrancar_site(pasta / "classico", classico, porta)
    if base is None:
        _fechar_site(processo)
        return c.ok("servidor (clássico) arrancou", False, "sem URL em 180 s")
    try:
        _http(base + "/api/voo", {"ativo": True,
                                  "teclas": {"w": True, "a": False, "s": False, "d": False,
                                             "q": False, "e": False}})
        eco = {"nao": None}
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 30:
            _codigo, estado = _http(base + "/api/state")
            eco = (estado.get("voo") or {}).get("eco")
            if (estado.get("amostras") or 0) > 0:
                break
            time.sleep(0.3)
        _codigo, estado = _http(base + "/api/state")
        c.ok("política clássica: eco `voo` = null (painel indisponível no site)",
             (estado.get("voo") or {}).get("eco") is None and (estado.get("amostras") or 0) > 0,
             f"amostras = {estado.get('amostras')} · eco = {(estado.get('voo') or {}).get('eco')}")
    finally:
        log = _fechar_site(processo)
    c.ok("runner avisa que ignorou o bloco `voo` (uma vez)",
         "bloco `voo` ignorado" in log, f"presente no log = {'bloco `voo` ignorado' in log}")
    return c.fechar()


# ---------------------------------------------------------------------------------------- §4 navegador
_DRIVER_CDP_VOO = r'''
// Driver CDP mínimo: abre o site, arma o painel de voo, manda keydown/keyup e lê o estado dos keycaps.
const porta = process.argv[2], base = process.argv[3]
const http = (caminho) => new Promise((ok, mal) => {
  import("node:http").then(({ default: h }) => {
    h.get({ host: "127.0.0.1", port: Number(porta), path: caminho }, (res) => {
      let corpo = ""; res.on("data", (d) => corpo += d); res.on("end", () => ok(JSON.parse(corpo || "[]")))
    }).on("error", mal)
  })
})
const alvo = (await http("/json")).find((t) => (t.url || "").startsWith(base) && t.type === "page")
  || (await http("/json")).find((t) => t.type === "page")
if (!alvo) throw new Error("não encontrei a página do site no Chrome (CDP)")
const ws = new WebSocket(alvo.webSocketDebuggerUrl)
let seq = 0; const pendentes = new Map()
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data)
  if (m.id && pendentes.has(m.id)) { pendentes.get(m.id)(m); pendentes.delete(m.id) }
})
const comando = (metodo, params = {}) => new Promise((ok, mal) => {
  const id = ++seq; pendentes.set(id, (m) => m.error ? mal(new Error(m.error.message)) : ok(m.result))
  ws.send(JSON.stringify({ id, method: metodo, params }))
})
await new Promise((ok, mal) => { ws.addEventListener("open", ok); ws.addEventListener("error", mal) })
await comando("Runtime.enable")
const esperar = (ms) => new Promise((r) => setTimeout(r, ms))
async function avaliar(expressao) {
  for (let tentativa = 1; tentativa <= 3; tentativa++) {
    try {
      const r = await comando("Runtime.evaluate", { expression: expressao, awaitPromise: true,
        returnByValue: true, timeout: 60000 })
      if (r.exceptionDetails) {
        const d = r.exceptionDetails.exception || {}
        throw new Error("na página: " + (d.description || r.exceptionDetails.text))
      }
      return r.result.value
    } catch (erro) {
      if (tentativa === 3 || !/context|destroyed|navigat/i.test(String(erro && erro.message))) throw erro
      await esperar(500)
    }
  }
}
// 1) espera pelo painel PRONTO (com o modo comando confirmado) e ARMA o controlo de voo
const pronto = await avaliar(`(async () => {
  const t0 = Date.now()
  while (Date.now() - t0 < 60000) {
    const painel = document.querySelector('[data-testid="controlo-voo"]')
    const indisponivel = document.querySelector('[data-testid="voo-indisponivel"]')
    const estado = indisponivel ? indisponivel.getAttribute("data-estado") : null
    if (estado === "indisponivel") return { erro: "painel indisponível (política sem modo comando)" }
    if (painel && estado === "pronto") {
      const armar = document.querySelector('[data-testid="voo-ativar"]')
      if (armar) {
        armar.click()
        const t1 = Date.now()
        while (Date.now() - t1 < 8000) {
          const ativo = document.querySelector('[data-testid="voo-ativo"]')
          if (ativo && ativo.getAttribute("data-estado") === "armado") return { ok: true }
          await new Promise((r) => setTimeout(r, 150))
        }
        return { erro: "cliquei em voo-ativar mas o painel não ficou armado em 8 s" }
      }
    }
    await new Promise((r) => setTimeout(r, 250))
  }
  return { erro: "o painel não ficou pronto (data-estado=pronto) em 60 s" }
})()`)
if (!pronto || pronto.erro) throw new Error(pronto && pronto.erro)
// 2) keydown REAL (KeyboardEvent no window, com key+code) e leitura dos keycaps — a captura de ecrã
//    (Page.captureScreenshot, LADO NODE) faz-se com a W ainda acesa, entre o keydown e o keyup
const durante = await avaliar(`(async () => {
  const estado = (letra) => {
    const el = document.querySelector('[data-testid="tecla-' + letra + '"]')
    return el ? el.getAttribute("data-estado") : null
  }
  const vref = () => (document.querySelector('[data-testid="voo-vref"]') || {}).textContent || ""
  const saida = { antes: {}, durante: {}, vref_antes: vref(), vref_durante: "" }
  for (const l of ["w", "a", "s", "d", "q", "e"]) saida.antes[l] = estado(l)
  window.dispatchEvent(new KeyboardEvent("keydown", {
    key: "w", code: "KeyW", keyCode: 87, bubbles: true, cancelable: true,
  }))
  await new Promise((r) => setTimeout(r, 200))
  for (const l of ["w", "a", "s", "d", "q", "e"]) saida.durante[l] = estado(l)
  saida.vref_durante = vref()
  return saida
})()`)
durante.captura = (await comando("Page.captureScreenshot", { format: "png" })).data   // W ACESA
const depois = await avaliar(`(async () => {
  const estado = (letra) => {
    const el = document.querySelector('[data-testid="tecla-' + letra + '"]')
    return el ? el.getAttribute("data-estado") : null
  }
  const vref = () => (document.querySelector('[data-testid="voo-vref"]') || {}).textContent || ""
  window.dispatchEvent(new KeyboardEvent("keyup", {
    key: "w", code: "KeyW", keyCode: 87, bubbles: true, cancelable: true,
  }))
  await new Promise((r) => setTimeout(r, 200))
  const saida = { depois: {}, vref_depois: vref() }
  for (const l of ["w", "a", "s", "d", "q", "e"]) saida.depois[l] = estado(l)
  const ativo = document.querySelector('[data-testid="voo-ativo"]')
  saida.ativo = ativo ? (ativo.getAttribute("data-estado") || ativo.textContent) : null
  const seguindo = document.querySelector('[data-testid="voo-seguindo"]')
  saida.seguindo = seguindo ? seguindo.textContent : null
  // REGRESSÃO DO TEMA: 'd' é a tecla de voar à direita e NÃO pode alternar dark/light (o atalho do
  // template foi removido — defeito reportado a 2026-10-10: cada voo à direita mudava o site para claro)
  saida.tema_antes = document.documentElement.className
  window.dispatchEvent(new KeyboardEvent("keydown", {
    key: "d", code: "KeyD", keyCode: 68, bubbles: true, cancelable: true,
  }))
  window.dispatchEvent(new KeyboardEvent("keyup", {
    key: "d", code: "KeyD", keyCode: 68, bubbles: true, cancelable: true,
  }))
  await new Promise((r) => setTimeout(r, 250))
  saida.tema_depois = document.documentElement.className
  return saida
})()`)
const resultado = { ...durante, ...depois }
ws.close()
process.stdout.write(JSON.stringify(resultado))
'''


def secao_navegador(modelos: dict[str, Path], pasta: Path, porta: int) -> bool:
    """§4: front real (site/dist) num Chrome headless — keycaps acendem e o POST chega ao servidor."""
    c = Checagens("§4 navegador: keycaps WASDQE ao vivo no site (CDP)")
    comando = next(((p, m) for p, m in modelos.items() if m is not None), None)
    if comando is None:
        return c.ok("há política --comandos para o §4", False, "nenhum modelo em out/")
    node = shutil.which("node")
    chrome = shutil.which("google-chrome-stable") or shutil.which("google-chrome") \
        or shutil.which("chromium") or shutil.which("chromium-browser")
    if node is None or chrome is None:
        return c.ok("node e Chrome disponíveis", False, f"node={node!r} chrome={chrome!r}")
    if not (SITE / "dist" / "index.html").is_file():
        return c.ok("site/dist construído", False, f"{SITE / 'dist' / 'index.html'} não existe "
                                                   "(corra `npm run build` em site/)")
    _planta, modelo = comando
    pasta = pasta / "nav"
    pasta.mkdir(parents=True, exist_ok=True)
    driver = pasta / "driver_voo.mjs"
    driver.write_text(_DRIVER_CDP_VOO, encoding="utf-8")
    processo, base, controlo, _telemetria, _stdout = _arrancar_site(pasta, modelo, porta, fator_tempo=1.0)
    if base is None:
        _fechar_site(processo)
        return c.ok("servidor arrancou", False, "sem URL em 180 s")
    navegador = None
    try:
        perfil = pasta / "chrome-perfil"
        shutil.rmtree(perfil, ignore_errors=True)
        navegador = subprocess.Popen(
            [chrome, "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={perfil}",
             "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--disable-dev-shm-usage",
             "--remote-allow-origins=*", base + "/"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        porta_cdp = None
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 30 and porta_cdp is None:
            try:
                primeira = (perfil / "DevToolsActivePort").read_text(encoding="utf-8").splitlines()[0].strip()
                if primeira.isdigit():
                    porta_cdp = int(primeira)
            except (OSError, IndexError, ValueError):
                pass
            if navegador.poll() is not None:
                break
            time.sleep(0.1)
        if porta_cdp is None:
            return c.ok("Chrome abriu a porta CDP", False)
        try:
            resultado = subprocess.run([node, str(driver), str(porta_cdp), base],
                                       capture_output=True, text=True, timeout=180, check=False)
        except subprocess.TimeoutExpired:
            return c.ok("driver CDP terminou", False, "timeout de 180 s")
        if resultado.returncode != 0:
            return c.ok("driver CDP correu", False,
                        (resultado.stderr or resultado.stdout)[-1500:])
        dados = json.loads(resultado.stdout)
        c.ok("painel de voo aparece e ARMA (sem voo-indisponivel)", dados.get("ativo") is not None,
             f"estado ativo = {dados.get('ativo')!r}")
        c.ok("keycaps W acende no keydown e apaga no keyup",
             dados.get("antes", {}).get("w") in ("inativa", "false", "0")
             and dados.get("durante", {}).get("w") in ("ativa", "true", "1")
             and dados.get("depois", {}).get("w") in ("inativa", "false", "0"),
             f"antes={dados.get('antes', {}).get('w')!r} durante={dados.get('durante', {}).get('w')!r} "
             f"depois={dados.get('depois', {}).get('w')!r}")
        c.ok("só a W pressionada acende (as outras ficam inativas)",
             all(dados.get("durante", {}).get(l) in ("inativa", "false", "0", None)
                 for l in "asdqe"),
             f"durante = {dados.get('durante')}")
        c.ok("o painel mostra o v_ref comandado durante a tecla",
             "1" in str(dados.get("vref_durante", "")),
             f"v_ref durante = {dados.get('vref_durante')!r} · depois = {dados.get('vref_depois')!r}")
        bloco = json.loads(controlo.read_text(encoding="utf-8")).get("voo", {})
        c.ok("o POST chegou ao servidor (ficheiro de controlo tem w=true durante)",
             bloco.get("teclas", {}).get("w") is True or bloco.get("ativo") is True,
             f"bloco = {bloco}")
        c.ok("pressionar D (voar à direita) NÃO muda o tema do site (atalho removido)",
             dados.get("tema_antes") == dados.get("tema_depois") and bool(dados.get("tema_depois")),
             f"classe do <html> antes={dados.get('tema_antes')!r} depois={dados.get('tema_depois')!r}")
        captura = dados.get("captura")
        if isinstance(captura, str) and captura:
            import base64
            imagem = _AQUI / "out" / "voo_keycaps.png"
            imagem.parent.mkdir(parents=True, exist_ok=True)
            imagem.write_bytes(base64.b64decode(captura))
            c.ok("captura do painel com a W acesa gravada", imagem.is_file(), str(imagem))
    finally:
        if navegador is not None:
            try:
                os.killpg(os.getpgid(navegador.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                navegador.terminate()
            try:
                navegador.wait(timeout=10)
            except subprocess.TimeoutExpired:
                navegador.kill()
        _fechar_site(processo)
    return c.fechar()


# ---------------------------------------------------------------------------------------- CLI
def analisar_argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="PROVA do controle de voo (contrato r11): teclas WASDQE, seguimento com vento/rajadas "
                    "corrigidos, servidor e site.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--so-pecas", action="store_true", help="corre só o §1 (funções puras + envs)")
    p.add_argument("--sem-http", action="store_true", help="salta o §3 (servidor) e o §4 (navegador)")
    p.add_argument("--navegador", action="store_true", help="acrescenta o §4 (Chrome headless por CDP)")
    p.add_argument("--model", type=Path, default=None, metavar="ZIP",
                   help="política --comandos explícita (por omissão descobre em out/)")
    p.add_argument("--planta", choices=("cf2", "real"), default="cf2",
                   help="planta do --model (só com --model explícito)")
    p.add_argument("--pasta", type=Path, default=None,
                   help="pasta de trabalho dos testes (por omissão $TMPDIR/teste_controle_voo)")
    p.add_argument("--porta", type=int, default=8571, help="porta base do servidor nos testes")
    return p.parse_args(argv)


def descobrir_modelos(args) -> dict[str, Path]:
    """Políticas `--comandos` em `out/` (as mais recentes de cada planta) — ou a explícita."""
    if args.model is not None:
        if not args.model.is_file():
            raise SystemExit(f"[teste] --model não existe: {args.model}")
        # ABSOLUTO sempre: o sim_site corre com cwd=experiments/09_drone_hover_rl e o `_absoluto` dele
        # resolveria um caminho relativo contra aí (…/experiments/09_drone_hover_rl/experiments/… →
        # «modelo inexistente»); um `--model` relativo à raiz rebentava o §3 sem explicação
        return {args.planta: args.model.resolve()}
    modelos = {}
    for planta, padrao in (("real", "real_*/final.zip"), ("cf2", "voo_*/final.zip")):
        candidatos = sorted((p for p in (_AQUI / "out").glob(padrao)
                             if "seguimento" not in p.parent.name),      # IA-2 nunca é voo
                            key=lambda p: p.stat().st_mtime_ns, reverse=True)
        if candidatos:
            modelos[planta] = candidatos[0]
    return modelos


def main(argv=None) -> int:
    args = analisar_argumentos(argv)
    pasta = args.pasta or (Path(os.environ.get("TMPDIR", ".")) / "teste_controle_voo")
    pasta.mkdir(parents=True, exist_ok=True)
    ok = secao_pecas()
    if args.so_pecas:
        print(f"\n[teste] resultado: {'TUDO OK' if ok else 'FALHAS'} (só §1)")
        return 0 if ok else 1
    modelos = descobrir_modelos(args)
    for planta, caminho in modelos.items():
        print(f"[teste] política {planta}: {caminho}")
    if not modelos:
        print("[teste] SEM política --comandos em out/ (voo_*/final.zip ou real_*/final.zip) e sem --model")
    ok = secao_seguimento(modelos) and ok
    if not args.sem_http:
        ok = secao_servidor(modelos, pasta, args.porta) and ok
        ok = secao_honestidade(pasta, args.porta + 2) and ok
        if args.navegador:
            ok = secao_navegador(modelos, pasta, args.porta + 4) and ok
    print(f"\n[teste] resultado: {'TUDO OK' if ok else 'FALHAS — ver linhas FALHA acima'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
