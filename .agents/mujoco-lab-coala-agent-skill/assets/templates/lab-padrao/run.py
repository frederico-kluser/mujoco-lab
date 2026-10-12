#!/usr/bin/env python3
"""run.py — VALIDAÇÃO do template `lab-padrao` por fórmulas fechadas, em CONDIÇÕES ISOLADAS. Exit 0/1.

O que este ficheiro faz (é o contrato do laboratório para todo o experimento): NÃO é uma demo, é uma
BATERIA DE CHECAGENS. Cada checagem tem **critério** (a fórmula), **esperado**, **medido** e tolerância; o
exit code é 0 só se TODAS passarem. Cada checagem corre num MODELO FRESCO (sem histórico) e numa condição
isolada — uma coisa de cada vez —, para que um qualquer desvio seja imputável à física e não ao passado.

    uv run --group hover-rl python <exp>/run.py                 # bateria completa (headless, sem janelas)
    uv run --group hover-rl python <exp>/run.py --json          # imprime o resumo.json
    uv run --group hover-rl python <exp>/run.py --video         # + vídeo EGL (offscreen) em out/

Checagens (todas com fórmula fechada independente do `env.py`):
  1. `trim_formula`    τ_trim == m·g·d·sin θ*              (m, d e g lidos do MODELO compilado)
  2. `trim_equilibrio` com ctrl = τ_trim a haste FICA no alvo (|erro| < 0,25° em 3 s)
  3. `periodo_analitico` T medido (cruzamentos de zero) == T0·(2/π)·K(sin²(θ0/2)), T0 = 2π√(I/(m·g·d))
  4. `energia_conservada` sem amortecimento |ΔE|/E_osc < 0,5 % (integrador/timestep sãos)
  5. `vento_estatico`   com vento, θ_eq resolve m·g·d·sinθ − b·cosθ·F = τ_trim (raiz numérica)
  6. `vento_cortado`    vento fora da faixa é CORTADO (nunca NaN/inf na física)
  7. `guardas_nan`      ação e estado não finitos LEVANTAM exceção (nada passa em silêncio)

ADAPTAR ao teu robô: troca as fórmulas pelos teus invariantes (o que É verificável sem treino). O que NÃO
muda: uma lista de checagens com critério/esperado/medido, condições isoladas e o exit code 0/1.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lab import mjkit  # noqa: I001  (MJKP: MUJOCO_GL=egl fixado antes de `import mujoco`: ordem intencional)

import mujoco
import numpy as np
from scipy.optimize import brentq
from scipy.special import ellipk

import env as env_mod

AQUI = Path(__file__).resolve().parent
DEG = 180.0 / np.pi
AMORTECIMENTO_ESTATICO = 3.0   # N·m·s/rad — amortecimento imposto NAS CHECAGENS ESTÁTICAS (o modelo não tem):
# sem ele a haste oscila durante dezenas de segundos (ζ≈0,05) e uma "leitura estática" seria só um instantâneo.


def sanitiza(obj):
    """Converte tipos NumPy em tipos Python: o `json.dumps` não conhece `np.bool_`/`np.float64`."""
    if isinstance(obj, dict):
        return {k: sanitiza(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitiza(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


def constantes(e) -> dict:
    """Constantes do MODELO compilado, calculadas AQUI de forma independente (não se lê o `env.py`)."""
    b = e.model.body("haste").id
    mujoco.mj_forward(e.model, e.data)
    m = float(mujoco.mj_getTotalmass(e.model))
    d = float(np.linalg.norm(e.data.xipos[b] - e.data.xanchor[e.junta]))
    g = float(np.linalg.norm(e.model.opt.gravity))
    M = np.zeros((e.model.nv, e.model.nv))
    mujoco.mj_fullM(e.model, e.data, M)   # 3.10+: (m, d, dst); mjData.qM foi removido na 3.11
    return {"m": m, "d": d, "g": g, "inercia": float(M[e.dof, e.dof]), "braco_ponta": e.braco_ponta}


def simular(e, ctrl: float, segundos: float, damping: float = 0.0, theta0: float | None = None,
            vento: tuple[float, float, float] | None = None) -> dict:
    """Condição isolada: modelo FRESCO (`mj_resetData`), comando CONSTANTE, opcionalmente com amortecimento.

    Devolve o histórico amostrado (t, θ, θ̇, energia relativa) e o estado final. É o único caminho de
    simulação deste ficheiro: nada de controladores, nada de teleporte — só `mj_step` com um comando fixo.
    """
    mujoco.mj_resetData(e.model, e.data)
    e.model.dof_damping[e.dof] = damping
    e.data.qpos[e.qadr] = e.theta_alvo if theta0 is None else float(theta0)
    e.data.qvel[e.dof] = 0.0
    e.data.qfrc_applied[:] = 0.0
    mujoco.mj_forward(e.model, e.data)
    if vento is not None:
        e.definir_vento(*vento)
    d = e.data
    e.ctrl.set(d, env_mod.ATUADOR, [ctrl])             # comando constante e CONHECIDO (não passa pela ação)
    n = round(segundos / e.model.opt.timestep)
    k = constantes(e)
    hist = {"t": np.empty(n), "theta": np.empty(n), "omega": np.empty(n), "energia": np.empty(n)}
    theta0_real = float(d.qpos[e.qadr])
    e_osc = k["m"] * k["g"] * k["d"] * (1.0 - np.cos(theta0_real))  # energia potencial vs pendurado em baixo
    for i in range(n):
        e._aplica_vento()                              # a perturbação entra em CADA passo de física
        mujoco.mj_step(e.model, d)
        theta, omega = float(d.qpos[e.qadr]), float(d.qvel[e.dof])
        hist["t"][i], hist["theta"][i], hist["omega"][i] = float(d.time), theta, omega
        hist["energia"][i] = 0.5 * k["inercia"] * omega**2 + k["m"] * k["g"] * k["d"] * (1.0 - np.cos(theta))
    mujoco.mj_forward(e.model, d)
    return {"hist": hist, "theta": float(d.qpos[e.qadr]), "omega": float(d.qvel[e.dof]), "E_osc": float(e_osc)}


def cruzamentos_ascendentes(t: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Instantes em que x(t) passa por zero a subir (interpolação linear) — mede o período sem FFT."""
    i = np.where((x[:-1] < 0) & (x[1:] >= 0))[0]
    return t[i] - x[i] * (t[i + 1] - t[i]) / (x[i + 1] - x[i])


def periodo_analitico(k: dict, theta0: float) -> dict:
    """Período EXATO do pêndulo físico para amplitude θ0: T = T0·(2/π)·K(k²), k = sin(θ0/2)."""
    T0 = 2 * np.pi * np.sqrt(k["inercia"] / (k["m"] * k["g"] * k["d"]))
    return {"T0": float(T0), "T": float(T0 * (2 / np.pi) * ellipk(np.sin(theta0 / 2) ** 2))}


def theta_equilibrio_vento(k: dict, trim: float, forca: float) -> float:
    """Raiz de Στ = τ_trim − m·g·d·sinθ − b·cosθ·F = 0 (equilíbrio estático com vento horizontal em +X).

    Sinais verificados no modelo: a gravidade faz −m·g·d·sinθ (restaura para θ=0) e a força F em +X no site
    da ponta faz −b·cosθ·F (porque para θ>0 a ponta está do lado −X): o vento empurra a haste PARA BAIXO.
    """
    b = k["braco_ponta"]

    def f(th: float) -> float:
        return trim - k["m"] * k["g"] * k["d"] * np.sin(th) - b * np.cos(th) * forca

    return float(brentq(f, -np.pi / 2 + 1e-6, np.pi / 2 - 1e-6, xtol=1e-12))


# ----------------------------------------------------------------------------------------- bateria de checagens
def checagens(args) -> list[dict]:
    alvo = args.alvo
    out: list[dict] = []

    e = env_mod.novo_env(theta_alvo_graus=alvo, jitter=False)
    k = constantes(e)
    trim_formula = k["m"] * k["g"] * k["d"] * np.sin(np.radians(alvo))
    out.append({
        "nome": "trim_formula", "criterio": "τ_trim = m·g·d·sin θ*  (m, d, g do modelo compilado)",
        "esperado": trim_formula, "medido": e.trim, "tol": 1e-9 * max(1.0, abs(trim_formula)),
        "unidade": "N·m", "ok": abs(e.trim - trim_formula) <= 1e-9 * max(1.0, abs(trim_formula)),
        "detalhe": f"m={k['m']:.6f} kg · d={k['d']:.6f} m · g={k['g']:.6f} m/s² · I_pivô={k['inercia']:.6f} kg·m²",
    })

    r = simular(e, ctrl=e.trim, segundos=args.segundos_estatico, damping=AMORTECIMENTO_ESTATICO)
    erro_final = abs((r["theta"] - e.theta_alvo) * DEG)
    out.append({
        "nome": "trim_equilibrio",
        "criterio": "com ctrl = τ_trim a haste FICA no alvo (e chega ao REPOUSO)",
        "esperado": 0.0, "medido": erro_final, "tol": args.tol_estatico, "unidade": "°",
        "ok": bool(erro_final <= args.tol_estatico and abs(r["omega"]) <= 1e-3),
        "detalhe": f"{args.segundos_estatico:.1f} s de mj_step, amortecimento {AMORTECIMENTO_ESTATICO} N·m·s/rad, "
                   f"θ_final={r['theta'] * DEG:.4f}° (alvo {alvo:.2f}°) · θ̇_final={r['omega']:.2e} rad/s",
    })

    theta0 = np.radians(args.amplitude)
    e2 = env_mod.novo_env(theta_alvo_graus=alvo, jitter=False)
    an = periodo_analitico(k, theta0)
    r2 = simular(e2, ctrl=0.0, segundos=args.segundos_livre, damping=0.0, theta0=theta0)
    zc = cruzamentos_ascendentes(r2["hist"]["t"], r2["hist"]["theta"])
    medido = float(np.mean(np.diff(zc))) if len(zc) > 2 else float("nan")
    erro_pct = 100.0 * (medido - an["T"]) / an["T"]
    out.append({
        "nome": "periodo_analitico", "criterio": "T medido (cruzamentos de zero) = T0·(2/π)·K(sin²(θ0/2))",
        "esperado": an["T"], "medido": medido, "tol": args.tol_periodo / 100.0 * an["T"], "unidade": "s",
        "ok": bool(np.isfinite(medido) and abs(erro_pct) <= args.tol_periodo),
        "detalhe": f"θ0={args.amplitude:.1f}° · T0={an['T0']:.6f} s · {len(zc) - 1} períodos · erro {erro_pct:+.3f} %",
    })

    e3 = r2["hist"]["energia"]
    deriva = 100.0 * abs(float(e3[-1] - e3[0])) / max(r2["E_osc"], 1e-12)
    out.append({
        "nome": "energia_conservada", "criterio": "sem amortecimento |E_fim − E_0|/E_osc < tol",
        "esperado": 0.0, "medido": deriva, "tol": args.tol_energia, "unidade": "%",
        "ok": deriva <= args.tol_energia,
        "detalhe": f"E_osc={r2['E_osc']:.6f} J · E_0={e3[0]:.9f} J · E_fim={e3[-1]:.9f} J (integrador "
                   f"{mujoco.mjtIntegrator(e2.model.opt.integrator).name}, dt={e2.model.opt.timestep} s)",
    })

    e4 = env_mod.novo_env(theta_alvo_graus=alvo, jitter=False)
    e4.definir_vento(args.vento, args.vento_azimute, 0.0)
    forca = float(np.linalg.norm(e4._forca_vento()))
    theta_eq = theta_equilibrio_vento(k, e4.trim, forca)
    r4 = simular(e4, ctrl=e4.trim, segundos=args.segundos_estatico, damping=AMORTECIMENTO_ESTATICO,
                 theta0=theta_eq, vento=(args.vento, args.vento_azimute, 0.0))
    erro_eq = abs((r4["theta"] - theta_eq) * DEG)
    out.append({
        "nome": "vento_estatico", "criterio": "θ_eq resolve m·g·d·sinθ − b·cosθ·F = τ_trim (raiz numérica)",
        "esperado": theta_eq * DEG, "medido": r4["theta"] * DEG, "tol": args.tol_vento, "unidade": "°",
        "ok": erro_eq <= args.tol_vento,
        "detalhe": f"vento {args.vento:.2f} m/s azimute {args.vento_azimute:.0f}° → F={forca:.4f} N; "
                   f"deslocamento do alvo {(theta_eq - e4.theta_alvo) * DEG:+.3f}° · erro {erro_eq:.4f}°",
    })

    e5 = env_mod.novo_env(theta_alvo_graus=alvo, jitter=False)
    e5.definir_vento(99.0, 0.0, 0.0)
    vel_cortada = e5.vento_polar()[0]
    levantou_vento = False
    try:
        e5.definir_vento(float("nan"), 0.0, 0.0)
    except ValueError:
        levantou_vento = True
    out.append({
        "nome": "vento_cortado", "criterio": "vento fora da faixa é cortado ao teto; NaN levanta ValueError",
        "esperado": env_mod.VENTO_VEL_MAX, "medido": vel_cortada, "tol": 1e-12, "unidade": "m/s",
        "ok": abs(vel_cortada - env_mod.VENTO_VEL_MAX) <= 1e-12 and levantou_vento,
        "detalhe": f"pedido 99 m/s → {vel_cortada:.3f} m/s (teto {env_mod.VENTO_VEL_MAX}); NaN → ValueError: {levantou_vento}",
    })

    e6 = env_mod.novo_env(theta_alvo_graus=alvo, jitter=False)

    def estado_nan() -> None:
        e6.data.qpos[e6.qadr] = float("nan")
        e6._verifica_sanidade("teste")     # guarda da FÍSICA (o step chama-o sempre; aqui força-se o caso)

    casos = []
    for nome, gatilho in (("ação NaN", lambda: e6.step([float("nan")])),
                          ("ação com forma errada", lambda: e6.step([0.0, 0.0])),
                          ("estado NaN", estado_nan)):
        try:
            gatilho()
            casos.append((nome, False))
        except (ValueError, RuntimeError):
            casos.append((nome, True))
    todos = all(ok for _, ok in casos) and e6.nan_detetados >= 1
    out.append({
        "nome": "guardas_nan", "criterio": "ação/estado não finitos LEVANTAM ValueError/RuntimeError",
        "esperado": 1.0, "medido": float(sum(ok for _, ok in casos)), "tol": 1e-12, "unidade": "casos",
        "ok": bool(todos), "detalhe": " · ".join(f"{n}: {'levanta' if ok else 'PASSOU'}" for n, ok in casos),
    })

    if args.video:
        e7 = env_mod.novo_env(theta_alvo_graus=alvo, jitter=False)
        e7.model.dof_damping[e7.dof] = 0.5
        e7.definir_vento(args.vento, args.vento_azimute, 0.0)
        out.append(_video(e7, args))
    return out


def _video(e, args) -> dict:
    """Grava vídeo/GIF (EGL, offscreen) do controlo pelo trim com vento — é a única parte com render."""
    caminho = Path(args.saida)
    caminho.mkdir(parents=True, exist_ok=True)
    mujoco.mj_resetData(e.model, e.data)
    e.data.qpos[e.qadr] = e.theta_alvo
    mujoco.mj_forward(e.model, e.data)
    ctrl = [e.trim]

    def controlador(model, data):
        e._aplica_vento()
        e.ctrl.set(data, env_mod.ATUADOR, ctrl)

    res = mjkit.record(e.model, e.data, controlador, duration=4.0, fps=50, camera="frontal",
                       mp4=caminho / "haste_alvo.mp4", gif=caminho / "haste_alvo.gif", sheet=caminho / "haste_alvo.png",
                       probes={"theta": lambda m, d: float(d.qpos[e.qadr])})
    return {"nome": "video", "criterio": "grava mp4+gif+filmstrip (EGL, offscreen)", "esperado": 1.0,
            "medido": float(Path(caminho / "haste_alvo.mp4").stat().st_size), "tol": 0.0, "unidade": "bytes",
            "ok": Path(caminho / "haste_alvo.mp4").stat().st_size > 1000,
            "detalhe": f"{res['frames']} frames em {res['wall_s']:.2f} s de parede"}


def imprimir(checks: list[dict], largura: int = 132) -> None:
    print("=" * largura)
    print("VALIDAÇÃO (condições isoladas, fórmulas fechadas) — template lab-padrao")
    print("=" * largura)
    for c in checks:
        marca = "OK  " if c["ok"] else "FALHA"
        print(f"[{marca}] {c['nome']}")
        print(f"         critério: {c['criterio']}")
        print(f"         esperado: {c['esperado']:.6f} {c['unidade']} ± {c['tol']:.6f}")
        print(f"         medido:   {c['medido']:.6f} {c['unidade']}")
        print(f"         detalhe:  {c['detalhe']}")
    n_ok = sum(c["ok"] for c in checks)
    print("-" * largura)
    print(f"{n_ok}/{len(checks)} checagens passaram" + ("" if n_ok == len(checks) else "  ← ver as FALHAS acima"))
    print("=" * largura)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Exit 0 = todas as checagens passaram; 1 = alguma falhou; 2 = uso inválido.")
    ap.add_argument("--modelo", type=Path, default=env_mod.MODELO_OMISSAO, help="MJCF a validar (padrão: model.xml)")
    ap.add_argument("--alvo", type=float, default=env_mod.ALVO_GRAUS, help="ângulo-alvo em graus")
    ap.add_argument("--saida", type=Path, default=AQUI / "out", help="pasta de saída (resumo.json, gráfico, vídeo)")
    ap.add_argument("--sem-video", action="store_true", help="aceite por compatibilidade: o vídeo JÁ está desligado por omissão")
    ap.add_argument("--video", action="store_true", help="grava vídeo/GIF/filmstrip (EGL, offscreen)")
    ap.add_argument("--json", action="store_true", help="imprime o resumo.json no fim")
    ap.add_argument("--amplitude", type=float, default=5.0, help="amplitude inicial da oscilação livre (graus)")
    ap.add_argument("--segundos-livre", type=float, default=6.0, help="duração da oscilação livre")
    ap.add_argument("--segundos-estatico", type=float, default=3.0, help="duração dos ensaios estáticos")
    ap.add_argument("--vento", type=float, default=5.0, help="velocidade do vento da checagem estática (m/s)")
    ap.add_argument("--vento-azimute", type=float, default=0.0, help="azimute do vento (graus a partir de +X)")
    ap.add_argument("--tol-periodo", type=float, default=0.5, help="tolerância do período em %% — padrão 0,5")
    ap.add_argument("--tol-energia", type=float, default=1.0,
                    help="tolerância da deriva de energia em %% — padrão 1,0 (medido 0,35 com dt=2 ms)")
    ap.add_argument("--tol-estatico", type=float, default=0.25, help="tolerância do equilíbrio estático (graus)")
    ap.add_argument("--tol-vento", type=float, default=0.5, help="tolerância do equilíbrio com vento (graus)")
    a = ap.parse_args(argv)
    if a.amplitude <= 0 or a.segundos_livre <= 1:
        ap.error("--amplitude tem de ser > 0 e --segundos-livre > 1")

    checks = checagens(a)
    imprimir(checks)
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    resumo = sanitiza({"template": "lab-padrao", "alvo_graus": a.alvo, "checks": checks,
              "n_ok": sum(c["ok"] for c in checks), "n_total": len(checks),
              "ok": all(c["ok"] for c in checks)})
    (saida / "resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"resumo: {saida / 'resumo.json'}")
    if a.json:
        print(json.dumps(resumo, indent=2, ensure_ascii=False))
    return 0 if resumo["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
