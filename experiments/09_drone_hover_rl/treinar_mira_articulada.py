"""experiments/09_drone_hover_rl/treinar_mira_articulada.py — TREINO da mira por arfagem dos BRAÇOS ARTICULADOS.

O dono: «garanta um treinamento de TensorFlow e do que for necessário para termos a precisão nos 3 cenários (mesma
altura, abaixo e acima do círculo); a qualidade é quantos acertos faz num tempo curto, e a penalização do erro é muito
alta — para ele só atirar quando acha que vai acertar». Quatro fases, cada uma com saída verificável:

  A · DADOS (MuJoCo 3.15, `.venv`, multiprocesso, SEM render): episódios nos 3 cenários com a bola em movimento
      ALEATÓRIO (Ornstein–Uhlenbeck, 0,2–0,8 m/s), alturas/distâncias sorteadas à volta de cada cenário, tiros REAIS
      (com recuo, para haver estados pós-tiro) disparados por um portão físico com limiares sorteados — e, em CADA
      decisão (50 Hz), um TIRO VIRTUAL: a bala que sairia 16 ms depois (latência do gatilho), com o estado da boca do
      cano DESSE passo de física, voada pela balística EXATA da planta contra a trajetória VERDADEIRA da bola. Rótulos:
      acertou?, distância de passagem e o erro angular (elevação, azimute). As 30 características são as que o drone
      tem a bordo (as 8 juntas medidas pelos encoders incluídas) — `MiraArticuladaIA.caracteristicas`.
  B · TENSORFLOW (`.venv-gpu`, TF 2.21, `@tf.function(jit_compile=True)` = OpenXLA): duas redes —
        · `RedeConfiancaTiroTF` (30 → 64 → 64 → 1): P(acerto | o que o drone sabe), entropia cruzada (probabilidades
          calibradas ⇒ o limiar ótimo para um erro custar K acertos é K/(1+K));
        · `RedeCorrecaoMiraTF` (30 → 64 → 64 → 2): o resíduo SISTEMÁTICO de pontaria (elevação, azimute) — Huber.
  C · GPU (JAX na RTX 4070): os tiros virtuais dão o desfecho CONTRAFACTUAL de qualquer regra de disparo sobre os mesmos
      estados — o portão (limiar de confiança, fator do erro previsto, taxa angular máxima, intervalo mínimo ≥ 0,4 s, o
      limite físico de cadência medido) é escolhido por busca vetorizada na GPU a maximizar a PIOR das 3 pontuações por
      minuto = (acertos − K·erros)/min.
  D · VALIDAÇÃO no MuJoCo (sementes NUNCA vistas): os 3 cenários com a bola programada do benchmark; sem e com TF.

Uso:
    .venv/bin/python experiments/09_drone_hover_rl/treinar_mira_articulada.py                # tudo (A → D)
    .venv/bin/python experiments/09_drone_hover_rl/treinar_mira_articulada.py --fase dados --episodios 60
    .venv-gpu/bin/python experiments/09_drone_hover_rl/treinar_mira_articulada.py --fase tf
    .venv-gpu/bin/python experiments/09_drone_hover_rl/treinar_mira_articulada.py --fase gpu
    .venv/bin/python experiments/09_drone_hover_rl/treinar_mira_articulada.py --fase validar
Saídas: `out/mira_articulada/{dados.npz, modelo_mira_articulada.json, validacao.json}` (out/ não é versionado).
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path[:0] = [p for p in (str(_RAIZ), str(_AQUI)) if p not in sys.path]
PASTA = _AQUI / "out" / "mira_articulada"
DADOS = PASTA / "dados.npz"
MODELO = PASTA / "modelo_mira_articulada.json"
VALIDACAO = PASTA / "validacao.json"
PY_CPU = _RAIZ / ".venv" / "bin" / "python"
PY_GPU = _RAIZ / ".venv-gpu" / "bin" / "python"
CENARIO_ID = {"mesma": 0, "abaixo": 1, "acima": 2}


# =========================================================================================== A · dados (MuJoCo)
def _episodio_dados(args: tuple) -> dict:
    """Um episódio de recolha: grava as características em cada decisão e o estado da boca/bola em cada passo de
    física; rotula os tiros virtuais no fim (balística exata). Corre num processo próprio (MuJoCo não partilha)."""
    os.environ.setdefault("MUJOCO_GL", "egl")
    cenario, semente, janela_s = args
    import cenarios_mira as cm
    from mira_articulada import MiraArticuladaIA, estado_boca, simular_bala

    rng = np.random.default_rng(10_000 + semente)
    base = cm.CENARIOS[cenario]
    dz = float(base["z_alvo"] - base["z_drone"]) + float(rng.uniform(-0.25, 0.25))
    z_drone = float(base["z_drone"]) + float(rng.uniform(-0.15, 0.15))
    opc = cm.OpcoesEpisodio(cenario=cenario, semente=semente, modo_bola="aleatorio",
                            vel_bola=float(rng.uniform(0.2, 0.8)), distancia=float(rng.uniform(2.0, 3.4)),
                            aquisicao_s=2.0, janela_s=janela_s, atirar=False, usar_tf=False, dz_alvo=dz, z_drone=z_drone)
    fator = float(rng.uniform(0.35, 1.2))
    cooldown = float(rng.uniform(0.25, 0.9))
    fisica: list = []                       # (t, p_boca, ex, v_boca, p_bola) antes de cada passo de física
    decisoes: list = []                     # (t, características, portão físico passou?, k)
    reais: list = []                        # (k da ordem, acertou?) — os tiros REAIS, para conferir os rótulos virtuais
    pendente: list = []
    n_aq = int(round(opc.aquisicao_s / 0.02))

    def gancho_fisica(env):
        p_boca, ex, v_boca = estado_boca(env)
        fisica.append((float(env.data.time), p_boca, ex, v_boca, np.array(env.ponto_alvo, dtype=float)))

    def gancho_decisao(env, mira, k):
        if env.gancho_fisica is None:
            env.gancho_fisica = gancho_fisica
        pl = env.planta
        if pendente and pl.n_acertos_bola + pl.n_erros_bola > pendente[1] + pendente[2]:
            reais.append((pendente[0], pl.n_acertos_bola > pendente[1]))
            pendente.clear()
        if k < n_aq or not mira.ultimo:
            return
        x = mira.caracteristicas(env)
        portao = mira.portao_fisico(env)
        decisoes.append((float(env.data.time), x, portao, k))
        # tiros REAIS de exploração (recuo verdadeiro) com um portão de limiares sorteados
        r_col = env.planta.raio_bola + 0.0045
        pode = (float(env.data.time) - mira.t_ultimo_tiro >= cooldown and not env.planta._tiros_ativos
                and not env.tiros_pendentes)
        if pode and not pendente and mira.erro_previsto(env) <= fator * r_col:
            mira.t_ultimo_tiro = float(env.data.time)
            mira.atirar(env)
            pendente[:] = [k, pl.n_acertos_bola, pl.n_erros_bola]

    opc.gancho_decisao = gancho_decisao
    t0 = time.perf_counter()
    try:
        res = cm.correr_episodio(opc)
    except Exception as erro:  # noqa: BLE001 — um episódio que diverge não estraga a recolha (fica registado)
        return {"ok": False, "erro": repr(erro), "cenario": cenario, "semente": semente}
    # ---- rótulos dos tiros virtuais (16 ms de latência; a bala é a da planta)
    from lab.drone_rpi import componentes as comp
    hw = comp.resolver(cm.BUILD_ARTICULADO)
    lat = float(hw.arma.dados.get("latencia_disparo_ms", 16.0)) / 1000.0
    v0 = hw.arma.velocidade_boca
    raio_col = 0.05 + 0.0045                # o mesmo da planta (raio da esfera-alvo + raio do projétil)
    g = np.array([0.0, 0.0, -9.81])
    vento = np.zeros(3)
    tempos = np.array([f[0] for f in fisica])
    xs, ys, dist, ang, cen, port, ks = [], [], [], [], [], [], []
    for t_k, x, portao, k in decisoes:
        i = int(np.searchsorted(tempos + 1e-9, t_k + lat))
        if i + 12 >= len(fisica):
            continue
        _t, p_b, ex, v_b, _pb = fisica[i]
        acertou, d_min = simular_bala(p_b, v_b + v0 * ex, [f[4] for f in fisica[i:i + 12]], raio_col, 0.002, g, vento)
        # erro angular (elevação, azimute) da bala face à bola no instante da passagem mais próxima
        pb = fisica[i + 2][4]
        rel = pb - p_b
        d_hat = rel / max(float(np.linalg.norm(rel)), 1e-9)
        el_b = math.atan2(float(d_hat[2]), math.hypot(float(d_hat[0]), float(d_hat[1])))
        az_b = math.atan2(float(d_hat[1]), float(d_hat[0]))
        el_c = math.atan2(float(ex[2]), math.hypot(float(ex[0]), float(ex[1])))
        az_c = math.atan2(float(ex[1]), float(ex[0]))
        xs.append(x)
        ys.append(1.0 if acertou else 0.0)
        dist.append(d_min)
        ang.append((el_b - el_c, (az_b - az_c + math.pi) % (2.0 * math.pi) - math.pi))
        cen.append(CENARIO_ID[cenario])
        port.append(1.0 if portao else 0.0)
        ks.append(k)
    rotulo_k = dict(zip(ks, ys))
    conferidos = [(bool(rotulo_k[kr] > 0.5), bool(real)) for kr, real in reais if kr in rotulo_k]
    return {"ok": True, "cenario": cenario, "semente": semente, "X": np.array(xs), "y": np.array(ys),
            "conferidos": conferidos,
            "dist": np.array(dist), "ang": np.array(ang), "cen": np.array(cen), "portao": np.array(port),
            "k": np.array(ks), "res": res, "s": time.perf_counter() - t0}


def fase_dados(episodios_por_cenario: int, janela_s: float, processos: int, semente0: int = 1000) -> dict:
    tarefas = [(c, semente0 + 10 * i + j, janela_s) for i in range(episodios_por_cenario)
               for j, c in enumerate(("mesma", "abaixo", "acima"))]
    print(f"[A] {len(tarefas)} episódios ({episodios_por_cenario}/cenário, janela {janela_s:.0f} s) em {processos} "
          f"processos …", flush=True)
    t0 = time.perf_counter()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processos) as pool:
        resultados = pool.map(_episodio_dados, tarefas, chunksize=1)
    ok = [r for r in resultados if r.get("ok") and len(r["X"])]
    falhas = [r for r in resultados if not r.get("ok")]
    X = np.concatenate([r["X"] for r in ok])
    dados = {"X": X, "y": np.concatenate([r["y"] for r in ok]), "dist": np.concatenate([r["dist"] for r in ok]),
             "ang": np.concatenate([r["ang"] for r in ok]), "cen": np.concatenate([r["cen"] for r in ok]),
             "portao": np.concatenate([r["portao"] for r in ok]),
             "episodio": np.concatenate([np.full(len(r["X"]), i) for i, r in enumerate(ok)]),
             "k": np.concatenate([r["k"] for r in ok])}
    PASTA.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DADOS, **dados)
    reais = {"tiros": sum(r["res"]["tiros"] for r in ok), "acertos": sum(r["res"]["acertos"] for r in ok)}
    conf = [c for r in ok for c in r.get("conferidos", [])]
    reais["rotulos_conferidos"] = len(conf)
    reais["concordancia_virtual_real_pct"] = round(100.0 * sum(a == b for a, b in conf) / max(len(conf), 1), 2)
    print(f"[A] rótulo virtual × resultado do tiro REAL no mesmo instante: {reais['concordancia_virtual_real_pct']} % de "
          f"{len(conf)} tiros", flush=True)
    print(f"[A] {len(X)} tiros virtuais de {len(ok)} episódios ({len(falhas)} falharam) em "
          f"{time.perf_counter() - t0:.0f} s · taxa de acerto virtual {100 * dados['y'].mean():.1f} % · "
          f"tiros reais de exploração {reais['tiros']} ({100 * reais['acertos'] / max(reais['tiros'], 1):.0f} % acertos)",
          flush=True)
    for c, i in CENARIO_ID.items():
        m = dados["cen"] == i
        print(f"    {c:>6s}: {int(m.sum())} amostras · acerto virtual {100 * dados['y'][m].mean():.1f} % · com o portão "
              f"físico {100 * dados['y'][m & (dados['portao'] > 0)].mean():.1f} %", flush=True)
    return {"amostras": int(len(X)), "episodios": len(ok), "falhas": [f.get("erro") for f in falhas], "reais": reais}


# =========================================================================================== B · TensorFlow
def fase_tf(epocas: int = 400) -> dict:
    """As duas redes em TensorFlow 2.21 com `@tf.function(jit_compile=True)` (OpenXLA)."""
    import tensorflow as tf

    from mira_articulada import N_CARACTERISTICAS, NOMES_CARACTERISTICAS
    d = np.load(DADOS)
    X, y, ang, ep, cen = d["X"].astype(np.float32), d["y"].astype(np.float32), d["ang"].astype(np.float32), d["episodio"], d["cen"]
    assert X.shape[1] == N_CARACTERISTICAS
    rng = np.random.default_rng(20261019)
    eps = np.unique(ep)
    val_eps = set(rng.choice(eps, size=max(3, len(eps) // 5), replace=False).tolist())
    m_val = np.array([e in val_eps for e in ep])
    mu = X[~m_val].mean(axis=0)
    sigma = X[~m_val].std(axis=0) + 1e-3
    tf.random.set_seed(20261019)
    print(f"[B] TensorFlow {tf.__version__} · dispositivos {[x.device_type for x in tf.config.list_physical_devices()]} · "
          f"treino {int((~m_val).sum())} / validação {int(m_val.sum())} amostras (episódios separados)", flush=True)

    def construir(n_saida: int, camadas=(64, 64)):
        vs, dims = [], [N_CARACTERISTICAS, *camadas, n_saida]
        for a, b in zip(dims[:-1], dims[1:]):
            vs.append(tf.Variable(tf.random.normal((a, b), stddev=math.sqrt(2.0 / a))))
            vs.append(tf.Variable(tf.zeros((b,))))
        return vs

    def ln(z):
        m = tf.reduce_mean(z, axis=-1, keepdims=True)
        v = tf.math.reduce_variance(z, axis=-1, keepdims=True)
        return (z - m) / tf.sqrt(v + 1e-5)

    def frente(vs, xb):
        h = xb
        n = len(vs) // 2
        for i in range(n - 1):
            h = tf.nn.silu(ln(tf.matmul(h, vs[2 * i]) + vs[2 * i + 1]))
        return tf.matmul(h, vs[-2]) + vs[-1]

    Xn = ((X - mu) / sigma).astype(np.float32)
    Xt, Xv = tf.constant(Xn[~m_val]), tf.constant(Xn[m_val])

    # --- 1) RedeConfiancaTiroTF: P(acerto)
    vs_c = construir(1)
    opt_c = tf.keras.optimizers.AdamW(learning_rate=2e-3, weight_decay=1e-4)
    yt, yv = tf.constant(y[~m_val][:, None]), tf.constant(y[m_val][:, None])

    @tf.function(jit_compile=True)
    def passo_c(xb, yb):
        with tf.GradientTape() as fita:
            z = frente(vs_c, xb)
            perda = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(labels=yb, logits=z))
        gr = fita.gradient(perda, vs_c)
        gr, _ = tf.clip_by_global_norm(gr, 1.0)
        opt_c.apply_gradients(zip(gr, vs_c))
        return perda

    @tf.function(jit_compile=True)
    def avaliar_c(xb, yb):
        z = frente(vs_c, xb)
        return tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(labels=yb, logits=z)), tf.sigmoid(z)

    t0 = time.perf_counter()
    n_t = int(Xt.shape[0])
    lote = 4096
    melhor, melhor_vs, hist_c = 1e9, None, []
    for epoca in range(epocas):
        idx = rng.permutation(n_t)
        for i in range(0, n_t, lote):
            sel = idx[i:i + lote]
            passo_c(tf.gather(Xt, sel), tf.gather(yt, sel))
        if epoca % 10 == 9 or epoca == epocas - 1:
            pv, _ = avaliar_c(Xv, yv)
            pv = float(pv)
            hist_c.append({"epoca": epoca + 1, "perda_val": round(pv, 5)})
            if pv < melhor:
                melhor, melhor_vs = pv, [v.numpy().copy() for v in vs_c]
    for v, w in zip(vs_c, melhor_vs):
        v.assign(w)
    _, p_val = avaliar_c(Xv, yv)
    p_val = p_val.numpy()[:, 0]
    dt_c = time.perf_counter() - t0
    # calibração (fiabilidade) por decil e AUC
    yv_np = y[m_val]
    ordem = np.argsort(-p_val)
    tp = np.cumsum(yv_np[ordem])
    fp = np.cumsum(1 - yv_np[ordem])
    auc = float(np.trapezoid(tp / max(tp[-1], 1), fp / max(fp[-1], 1)))
    print(f"[B] RedeConfiancaTiroTF: perda val {melhor:.4f} · AUC {auc:.3f} · {dt_c:.1f} s", flush=True)

    # --- 2) RedeCorrecaoMiraTF: resíduo angular sistemático (só tiros perto do alvo: |erro| < 2°)
    m_perto = np.all(np.abs(ang) < math.radians(2.0), axis=1)
    escala = math.radians(0.5)
    a_alvo = np.clip(ang / escala, -0.999, 0.999).astype(np.float32)
    mt, mv = (~m_val) & m_perto, m_val & m_perto
    vs_r = construir(2)
    opt_r = tf.keras.optimizers.AdamW(learning_rate=1.5e-3, weight_decay=1e-4)
    Xrt, Xrv = tf.constant(Xn[mt]), tf.constant(Xn[mv])
    art, arv = tf.constant(np.arctanh(a_alvo[mt])), tf.constant(np.arctanh(a_alvo[mv]))

    @tf.function(jit_compile=True)
    def passo_r(xb, yb):
        with tf.GradientTape() as fita:
            perda = tf.reduce_mean(tf.keras.losses.huber(yb, frente(vs_r, xb), delta=0.5))
        gr = fita.gradient(perda, vs_r)
        gr, _ = tf.clip_by_global_norm(gr, 1.0)
        opt_r.apply_gradients(zip(gr, vs_r))
        return perda

    @tf.function(jit_compile=True)
    def avaliar_r(xb, yb):
        return tf.reduce_mean(tf.keras.losses.huber(yb, frente(vs_r, xb), delta=0.5))

    t1 = time.perf_counter()
    n_r = int(Xrt.shape[0])
    melhor_r, melhor_vr = 1e9, None
    for epoca in range(max(epocas // 2, 50)):
        idx = rng.permutation(n_r)
        for i in range(0, n_r, lote):
            sel = idx[i:i + lote]
            passo_r(tf.gather(Xrt, sel), tf.gather(art, sel))
        if epoca % 10 == 9:
            pv = float(avaliar_r(Xrv, arv))
            if pv < melhor_r:
                melhor_r, melhor_vr = pv, [v.numpy().copy() for v in vs_r]
    for v, w in zip(vs_r, melhor_vr):
        v.assign(w)
    pred = np.tanh(frente(vs_r, Xrv).numpy()) * escala
    real = ang[mv]
    rms_antes = np.degrees(np.sqrt(np.mean(real ** 2, axis=0)))
    rms_depois = np.degrees(np.sqrt(np.mean((real - pred) ** 2, axis=0)))
    print(f"[B] RedeCorrecaoMiraTF: erro angular RMS (elev, az) {np.round(rms_antes, 3)}° → resíduo "
          f"{np.round(rms_depois, 3)}° na validação · {time.perf_counter() - t1:.1f} s", flush=True)

    def exportar(vs) -> dict:
        n = len(vs) // 2
        out = {"n_camadas": n, "mu": mu.tolist(), "sigma": sigma.tolist()}
        for i in range(n):
            out[f"W{i + 1}"] = np.asarray(vs[2 * i].numpy(), dtype=float).round(7).tolist()
            out[f"b{i + 1}"] = np.asarray(vs[2 * i + 1].numpy(), dtype=float).round(7).tolist()
        return out

    modelo = json.loads(MODELO.read_text(encoding="utf-8")) if MODELO.is_file() else {}
    modelo.update({
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "tensorflow_versao": tf.__version__,
        "caracteristicas": list(NOMES_CARACTERISTICAS), "amostras_treino": int((~m_val).sum()),
        "amostras_validacao": int(m_val.sum()), "rede_confianca": exportar(vs_c), "rede_correcao": exportar(vs_r),
        "metricas_tf": {"perda_val_confianca": round(melhor, 5), "auc_validacao": round(auc, 4),
                        "erro_angular_rms_antes_graus": [round(float(v), 4) for v in rms_antes],
                        "erro_angular_rms_depois_graus": [round(float(v), 4) for v in rms_depois],
                        "historico_confianca": hist_c, "segundos": round(time.perf_counter() - t0, 1)},
    })
    MODELO.write_text(json.dumps(modelo, indent=1), encoding="utf-8")
    np.savez_compressed(PASTA / "validacao_tf.npz", p=p_val, y=yv_np, cen=cen[m_val], ep=ep[m_val], k=d["k"][m_val],
                        X=X[m_val], portao=d["portao"][m_val])
    print(f"[B] gravado {MODELO}", flush=True)
    return modelo["metricas_tf"]


# =========================================================================================== C · GPU (JAX)
def fase_gpu() -> dict:
    """Portão de disparo escolhido na GPU: para cada combinação (limiar de P, fator do erro previsto, taxa máxima,
    intervalo mínimo), simula a regra sobre os estados de VALIDAÇÃO (o desfecho de cada tiro é o do tiro virtual) e
    mede a pontuação por minuto = (acertos − K·erros)/min por cenário; escolhe a que maximiza a PIOR das 3 (robustez)."""
    import jax
    import jax.numpy as jnp

    from cenarios_mira import PENALIDADE
    from mira_articulada import NOMES_CARACTERISTICAS
    v = np.load(PASTA / "validacao_tf.npz")
    p, y, cen, ep, k, X = v["p"], v["y"], v["cen"], v["ep"], v["k"], v["X"]
    i_erro = NOMES_CARACTERISTICAS.index("erro_prev_r")
    i_gy, i_gz = NOMES_CARACTERISTICAS.index("giro_y"), NOMES_CARACTERISTICAS.index("giro_z")
    omega = np.hypot(X[:, i_gy], X[:, i_gz])
    erro_r = X[:, i_erro]
    # ordem temporal dentro de cada episódio (o intervalo mínimo entre tiros precisa dela)
    ordem = np.lexsort((k, ep))
    p, y, cen, ep, k, omega, erro_r = (a[ordem] for a in (p, y, cen, ep, k, omega, erro_r))
    k_pen = float(PENALIDADE)
    base = k_pen / (1.0 + k_pen)
    limiares = np.concatenate([[0.0], np.linspace(base, 0.995, 12)])
    fatores = np.array([0.4, 0.5, 0.6, 0.75, 0.9, 1.1])
    omegas = np.array([0.15, 0.25, 0.4, 0.8])
    # intervalo mínimo ≥ 0,4 s: medido no MuJoCo, um tiro recupera em 0,22 s, mas a 4 tiros/s (0,25 s) a força média do
    # recuo (7,7 N) obriga a ~10° de empuxo inclinado permanente e houve episódios a divergir — limite FÍSICO de cadência
    cooldowns = np.array([0.40, 0.45, 0.55, 0.70])          # s
    grelha = np.array(np.meshgrid(limiares, fatores, omegas, cooldowns, indexing="ij")).reshape(4, -1).T
    print(f"[C] JAX {jax.__version__} · {jax.default_backend()} {jax.devices()} · {len(grelha)} regras × "
          f"{len(p)} estados", flush=True)
    dt = 0.02
    p_j, y_j, cen_j, ep_j, k_j, om_j, er_j = (jnp.asarray(a) for a in (p, y, cen, ep, k, omega, erro_r))
    n_ep_cen = np.array([len(np.unique(ep[cen == c])) for c in range(3)], dtype=float)
    janela_ep = np.array([len(k[(ep == e)]) * dt for e in np.unique(ep)]).mean()

    def avaliar(regra):
        lim, fat, om_max, cd = regra[0], regra[1], regra[2], regra[3]
        quer = (p_j >= lim) & (er_j <= fat) & (om_j <= om_max)

        def corpo(estado, entrada):
            ultimo_t, ep_ant = estado
            q, yy, e, kk = entrada
            t = kk * dt
            ultimo_t = jnp.where(e != ep_ant, -10.0, ultimo_t)
            atira = q & (t - ultimo_t >= cd)
            ultimo_t = jnp.where(atira, t, ultimo_t)
            return (ultimo_t, e), (atira, atira & (yy > 0.5))

        _, (atira, acerta) = jax.lax.scan(corpo, (jnp.asarray(-10.0), jnp.asarray(-1, dtype=ep_j.dtype)),
                                          (quer, y_j, ep_j, k_j))
        res = []
        for c in range(3):
            m = cen_j == c
            ac = jnp.sum(acerta & m)
            er = jnp.sum(atira & m) - ac
            res.append(jnp.stack([ac, er]))
        return jnp.stack(res)

    t0 = time.perf_counter()
    todos = np.asarray(jax.jit(jax.vmap(avaliar))(jnp.asarray(grelha)))
    seg = janela_ep * n_ep_cen
    pont_min = (todos[:, :, 0] - k_pen * todos[:, :, 1]) / (seg[None, :] / 60.0)
    pior = pont_min.min(axis=1)
    i_best = int(np.argmax(pior))
    sem_tf = grelha[:, 0] == 0.0
    i_best_sem = int(np.argmax(np.where(sem_tf, pior, -1e9)))
    print(f"[C] {time.perf_counter() - t0:.2f} s na GPU", flush=True)

    def resumo(i):
        lim, fat, om, cd = grelha[i]
        return {"limiar_confianca": float(lim), "fator_seguranca": float(fat), "omega_max_tiro": float(om),
                "cooldown_s": float(cd),
                "por_cenario": {c: {"acertos": int(todos[i, j, 0]), "erros": int(todos[i, j, 1]),
                                    "pontuacao_por_min": round(float(pont_min[i, j]), 2)}
                                for c, j in CENARIO_ID.items()}}

    melhor, melhor_sem = resumo(i_best), resumo(i_best_sem)
    print(f"[C] melhor portão SEM a rede TF: {melhor_sem}", flush=True)
    print(f"[C] melhor portão COM a rede TF: {melhor}", flush=True)
    modelo = json.loads(MODELO.read_text(encoding="utf-8"))
    modelo["limiar_confianca"] = max(base, melhor["limiar_confianca"])
    par = dict(modelo.get("parametros") or {})
    par.update({"fator_seguranca": melhor["fator_seguranca"], "omega_max_tiro": melhor["omega_max_tiro"],
                "cooldown_s": melhor["cooldown_s"], "penalidade": k_pen})
    modelo["parametros"] = par
    modelo["portao_gpu"] = {"com_tf": melhor, "sem_tf": melhor_sem, "jax": jax.__version__,
                            "dispositivo": str(jax.devices()[0]), "regras": int(len(grelha))}
    MODELO.write_text(json.dumps(modelo, indent=1), encoding="utf-8")
    return modelo["portao_gpu"]


# =========================================================================================== D · validação (MuJoCo)
def _episodio_validar(args: tuple) -> dict:
    os.environ.setdefault("MUJOCO_GL", "egl")
    cenario, semente, usar_tf = args
    import cenarios_mira as cm
    opc = cm.OpcoesEpisodio(cenario=cenario, semente=semente, modo_bola="programado", vel_bola=0.55, usar_tf=usar_tf)
    return cm.correr_episodio(opc)


def fase_validar(processos: int, sementes=(90001, 90002, 90003, 90004)) -> dict:
    tarefas = [(c, s, tf_) for c in ("mesma", "abaixo", "acima") for s in sementes for tf_ in (False, True)]
    ctx = mp.get_context("spawn")
    with ctx.Pool(processos) as pool:
        res = pool.map(_episodio_validar, tarefas, chunksize=1)
    out = {}
    for c in ("mesma", "abaixo", "acima"):
        for tf_ in (False, True):
            rs = [r for r in res if r["cenario"] == c and r["usar_tf"] == tf_]
            ac, er, ti = sum(r["acertos"] for r in rs), sum(r["erros"] for r in rs), sum(r["tiros"] for r in rs)
            seg = sum(r["janela_s"] for r in rs)
            chave = f"{c}_{'tf' if tf_ else 'fisico'}"
            out[chave] = {
                "acertos": ac, "erros": er, "tiros": ti, "acertos_por_min": round(60.0 * ac / seg, 2),
                "pontuacao_por_min": round(60.0 * (ac - 20.0 * er) / seg, 2), "precisao_pct": round(100.0 * ac / max(ti, 1), 1),
                "desloc_max_m": round(max(r["desloc_max_m"] for r in rs), 3)}
            print(f"[D] {c:>6s} {'TF ' if tf_ else 'fís'}: {ac} acertos / {er} erros em {seg:.0f} s → "
                  f"{out[chave]['acertos_por_min']:.1f} acertos/min, pontuação {out[chave]['pontuacao_por_min']:+.1f}/min, "
                  f"deslocamento máx {out[chave]['desloc_max_m'] * 100:.0f} cm", flush=True)
    VALIDACAO.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fase", choices=("tudo", "dados", "tf", "gpu", "validar"), default="tudo")
    ap.add_argument("--episodios", type=int, default=40, help="episódios por cenário na recolha")
    ap.add_argument("--janela", type=float, default=12.0)
    ap.add_argument("--processos", type=int, default=max(2, min(24, (os.cpu_count() or 4) - 4)))
    ap.add_argument("--epocas", type=int, default=300)
    a = ap.parse_args(argv)
    if a.fase in ("tudo", "dados"):
        fase_dados(a.episodios, a.janela, a.processos)
    if a.fase == "tudo":                      # TF e JAX vivem no ambiente da GPU
        for f in ("tf", "gpu"):
            r = subprocess.run([str(PY_GPU if PY_GPU.is_file() else sys.executable), __file__, "--fase", f,
                                "--epocas", str(a.epocas)], check=False)
            if r.returncode != 0:
                return r.returncode
        fase_validar(a.processos)
        return 0
    if a.fase == "tf":
        fase_tf(a.epocas)
    elif a.fase == "gpu":
        fase_gpu()
    elif a.fase == "validar":
        fase_validar(a.processos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
