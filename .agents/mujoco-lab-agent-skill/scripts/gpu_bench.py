#!/usr/bin/env python3
"""gpu_bench.py — mede SPS (passos/s × nworld) e VRAM de MJX-JAX, MJX-Warp, MuJoCo Warp (nativo) e da baseline CPU (mujoco.rollout).

    # GPU: rode com a venv de GPU (.venv-gpu); cwd FORA da raiz do projeto (o MuJoCo grava MUJOCO_LOG.TXT no cwd)
    .venv-gpu/bin/python .agents/mujoco-lab-agent-skill/scripts/gpu_bench.py --backend warp --model docs/upstream/mujoco/model/humanoid/humanoid.xml --nworld 4096 --steps 50
    .venv-gpu/bin/python .agents/mujoco-lab-agent-skill/scripts/gpu_bench.py --backend mjx --impl jax  --model MODELO.xml --nworld 4096 --steps 50 [--iterations 6 --ls-iterations 6]
    .venv-gpu/bin/python .agents/mujoco-lab-agent-skill/scripts/gpu_bench.py --backend mjx --impl warp --model MODELO.xml --nworld 4096 --steps 50 [--graph-mode WARP_STAGED]
    # CPU (mujoco.rollout com pool de threads): roda em QUALQUER das duas venvs (não importa jax nem warp)
    .venv/bin/python .agents/mujoco-lab-agent-skill/scripts/gpu_bench.py --backend cpu --model MODELO.xml --nworld 4096 --steps 50 --threads 32

Backends: warp = MuJoCo Warp nativo (mujoco_warp.put_model/put_data/step, passo capturado em CUDA graph) · mjx --impl jax = MJX-JAX (jit + lax.scan + vmap)
· mjx --impl warp = MJX-Warp (JAX FFI → MuJoCo Warp; precisa de warp-lang) · cpu = mujoco.rollout (nthread; float64).
Carga de trabalho IDÊNTICA nos backends: estado inicial = keyframe --keyframe (padrão 0; -1 usa qpos0) + ruído gaussiano em qvel (--qvel-noise) + ctrl constante
aleatório por mundo (±--ctrl-noise × meia-faixa do ctrlrange), mesma semente; cada repetição recomeça desse estado e roda --steps passos.
Protocolo: 1ª execução = JIT/captura de grafo (medida à parte) → aquecimento (--warmup execuções e ≥ --min-warm-s s, p/ o clock da GPU subir) → --reps repetições cronometradas
(sincronizadas) → mediana. SPS = nworld × steps / tempo. VRAM = nvidia-smi (processo e dispositivo; pico amostrado a cada 0,5 s fora das repetições cronometradas).
Segurança da GPU compartilhada: JAX roda com XLA_PYTHON_CLIENT_PREALLOCATE=false e MEM_FRACTION=0.85 (use --prealloc p/ o padrão do JAX: 75 % pré-alocados) e um vigia encerra
o processo se a VRAM livre do dispositivo cair abaixo de --min-free-mib. --budget-s reduz --reps (mín. 3) para não saturar a GPU por muito tempo.
Saída: resumo legível + uma linha `RESULT_JSON {...}`. Exit 0 ok · 2 uso/erro · 3 sem memória (OOM) / abortado pelo vigia de VRAM.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from importlib import metadata

# ---------------------------------------------------------------------------------------------------------------------------------------------
# argumentos


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", required=True, choices=["mjx", "warp", "cpu"], help="mjx (JAX/MJX) · warp (MuJoCo Warp nativo) · cpu (mujoco.rollout)")
    ap.add_argument("--model", required=True, help="caminho do .xml/.mjb (use caminho absoluto se o cwd não for a raiz do projeto)")
    ap.add_argument("--nworld", type=int, default=4096, help="mundos/trajetórias em paralelo (padrão 4096)")
    ap.add_argument("--steps", type=int, default=100, help="passos por repetição (padrão 100)")
    ap.add_argument("--reps", type=int, default=5, help="repetições cronometradas; reporta a mediana (padrão 5)")
    ap.add_argument("--warmup", type=int, default=2, help="execuções completas de aquecimento após a 1ª (JIT/captura) (padrão 2)")
    ap.add_argument("--min-warm-s", type=float, default=1.5, help="aquecimento mínimo em segundos (clock da GPU sobe de P8) (padrão 1,5)")
    ap.add_argument("--budget-s", type=float, default=60.0, help="orçamento de GPU saturada (aquecimento+repetições); reduz --reps até o mínimo 3 (padrão 60)")
    ap.add_argument("--impl", choices=["jax", "warp"], default="jax", help="só p/ --backend mjx: implementação do MJX (padrão jax)")
    ap.add_argument("--graph-mode", choices=["WARP", "WARP_STAGED", "WARP_STAGED_EX"], default=None, help="só p/ mjx --impl warp (padrão do MJX: WARP)")
    ap.add_argument("--keyframe", type=int, default=0, help="keyframe inicial; -1 = qpos0 (padrão 0, como o mjwarp-testspeed)")
    ap.add_argument("--qvel-noise", type=float, default=0.01, help="desvio-padrão do ruído em qvel inicial (padrão 0,01)")
    ap.add_argument("--ctrl-noise", type=float, default=0.1, help="ctrl constante por mundo = centro + U(-1,1)·este·meia-faixa (padrão 0,1)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--solver", choices=["newton", "cg"], default=None, help="sobrescreve opt.solver do modelo (padrão: o do modelo)")
    ap.add_argument("--iterations", type=int, default=None, help="sobrescreve opt.iterations (padrão: o do modelo)")
    ap.add_argument("--ls-iterations", type=int, default=None, help="sobrescreve opt.ls_iterations (padrão: o do modelo)")
    ap.add_argument("--nconmax", type=int, default=None, help="warp/mjx-warp: contatos POR MUNDO (padrão: heurística do MuJoCo Warp)")
    ap.add_argument("--njmax", type=int, default=None, help="warp/mjx-warp: restrições por mundo, limite estrito (padrão: heurística do MuJoCo Warp)")
    ap.add_argument("--threads", type=int, default=0, help="só cpu: threads do mujoco.rollout (padrão: nº de CPUs lógicas)")
    ap.add_argument("--device", default="cuda:0", help="dispositivo Warp (padrão cuda:0)")
    ap.add_argument("--mem-fraction", type=float, default=0.85, help="JAX: XLA_PYTHON_CLIENT_MEM_FRACTION com PREALLOCATE=false (padrão 0,85)")
    ap.add_argument("--prealloc", action="store_true", help="JAX: deixa o padrão do JAX (pré-aloca 75 %% da VRAM) em vez de PREALLOCATE=false")
    ap.add_argument("--min-free-mib", type=float, default=500.0, help="vigia: encerra se a VRAM livre do dispositivo < este valor (0 desliga) (padrão 500)")
    ap.add_argument("--json", action="store_true", help="imprime SÓ a linha RESULT_JSON")
    a = ap.parse_args(argv)
    if a.nworld < 1 or a.steps < 1 or a.reps < 1:
        ap.error("--nworld, --steps e --reps devem ser ≥ 1")
    if a.backend != "mjx" and (a.graph_mode or a.impl != "jax"):
        ap.error("--impl/--graph-mode só valem com --backend mjx")
    if a.graph_mode and a.impl != "warp":
        ap.error("--graph-mode só vale com --impl warp")
    return a


def configure_env(a: argparse.Namespace) -> None:
    """Variáveis que precisam existir ANTES de importar jax (valores já exportados no ambiente têm prioridade)."""
    if a.backend == "mjx":
        if not a.prealloc:
            os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
            os.environ.setdefault("XLA_PYTHON_CLIENT_MEM_FRACTION", str(a.mem_fraction))
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "1")
    if a.backend == "cpu":  # evita que a baseline use BLAS multithread por baixo (não usa, mas deixa explícito)
        os.environ.setdefault("OMP_NUM_THREADS", "1")


# ---------------------------------------------------------------------------------------------------------------------------------------------
# VRAM via nvidia-smi


def _smi(args: list[str]) -> str:
    try:
        r = subprocess.run(["nvidia-smi", *args], capture_output=True, text=True, timeout=10)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def smi_device() -> tuple[float, float] | None:
    """(usada MiB, total MiB) da GPU 0, ou None se o nvidia-smi falhar."""
    try:
        used, total = _smi(["-i", "0", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"]).strip().splitlines()[0].split(",")
        return float(used), float(total)
    except (IndexError, ValueError):
        return None


def smi_process(pid: int) -> float | None:
    """VRAM (MiB) do processo `pid` segundo o nvidia-smi (contexto CUDA + alocações), ou None se não listado."""
    for line in _smi(["--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"]).strip().splitlines():
        try:
            p, mem = [x.strip() for x in line.split(",")]
            if int(p) == pid:
                return float(mem)
        except ValueError:
            continue
    return None


class VramMonitor(threading.Thread):
    """Amostra a VRAM do processo/dispositivo (pico) e encerra o processo se a VRAM livre cair demais (protege o desktop)."""

    def __init__(self, min_free_mib: float, interval: float = 0.5):
        super().__init__(daemon=True)
        self.pid, self.min_free, self.interval = os.getpid(), min_free_mib, interval
        self.baseline = smi_device()  # antes de o processo criar contexto CUDA
        self.peak_proc: float | None = None
        self.peak_dev: float | None = None
        self.paused = threading.Event()
        self.stop_flag = threading.Event()

    def sample(self) -> tuple[float | None, float | None]:
        proc, dev = smi_process(self.pid), smi_device()
        if proc is not None:
            self.peak_proc = proc if self.peak_proc is None else max(self.peak_proc, proc)
        if dev is not None:
            self.peak_dev = dev[0] if self.peak_dev is None else max(self.peak_dev, dev[0])
            if self.min_free > 0 and dev[1] - dev[0] < self.min_free:
                print(f"\nABORTADO pelo vigia: VRAM livre {dev[1] - dev[0]:.0f} MiB < {self.min_free:.0f} MiB (protege o desktop). Use menos --nworld.", flush=True)
                os._exit(3)
        return proc, dev[0] if dev else None

    def run(self) -> None:
        while not self.stop_flag.wait(self.interval):
            if not self.paused.is_set():
                self.sample()


# ---------------------------------------------------------------------------------------------------------------------------------------------
# modelo e estado inicial (idêntico em todos os backends)


def load_model(a: argparse.Namespace):
    import mujoco

    m = mujoco.MjModel.from_binary_path(a.model) if a.model.endswith(".mjb") else mujoco.MjModel.from_xml_path(a.model)
    if a.solver:
        m.opt.solver = {"newton": mujoco.mjtSolver.mjSOL_NEWTON, "cg": mujoco.mjtSolver.mjSOL_CG}[a.solver]
    if a.iterations is not None:
        m.opt.iterations = a.iterations
    if a.ls_iterations is not None:
        m.opt.ls_iterations = a.ls_iterations
    return m


def make_initial(m, a: argparse.Namespace) -> dict:
    """Estado inicial comum: d0 (MjData no keyframe, após mj_forward), qvel[nworld,nv] e ctrl[nworld,nu] (float64; os backends convertem)."""
    import mujoco
    import numpy as np

    d0 = mujoco.MjData(m)
    if a.keyframe >= 0 and m.nkey > 0:  # modelo sem keyframes: usa qpos0
        if a.keyframe >= m.nkey:
            raise SystemExit(f"--keyframe {a.keyframe} inexistente (o modelo tem {m.nkey}); use -1 para qpos0")
        mujoco.mj_resetDataKeyframe(m, d0, a.keyframe)
    mujoco.mj_forward(m, d0)
    rng = np.random.default_rng(a.seed)
    qvel = d0.qvel[None, :] + a.qvel_noise * rng.standard_normal((a.nworld, m.nv))
    if m.nu:
        lim = m.actuator_ctrllimited.astype(bool)
        mid = np.where(lim, 0.5 * (m.actuator_ctrlrange[:, 0] + m.actuator_ctrlrange[:, 1]), 0.0)
        half = np.where(lim, 0.5 * (m.actuator_ctrlrange[:, 1] - m.actuator_ctrlrange[:, 0]), 1.0)
        ctrl = mid[None, :] + a.ctrl_noise * half[None, :] * rng.uniform(-1, 1, (a.nworld, m.nu))
    else:
        ctrl = np.zeros((a.nworld, 0))
    return {"d0": d0, "qvel": qvel, "ctrl": ctrl}


# ---------------------------------------------------------------------------------------------------------------------------------------------
# backends: cada um devolve um Runner com prepare() (fora do cronômetro), execute() (cronometrado, sincronizado) e health()


def default_contact_limits(m, d0, nconmax: int | None, njmax: int | None) -> tuple[int, int]:
    """nconmax (por mundo) e njmax: o valor pedido ou a heurística do MuJoCo Warp (_default_nconmax/_default_njmax, API privada; fallback 64/128)."""
    if nconmax is not None and njmax is not None:
        return nconmax, njmax
    try:
        try:
            from mujoco_warp._src import io as wio
        except ImportError:  # só mujoco-mjx[warp] instalado: o MuJoCo Warp vai vendorizado dentro do mjx
            from mujoco.mjx.third_party.mujoco_warp._src import io as wio
        return (nconmax if nconmax is not None else int(wio._default_nconmax(m, d0))), (njmax if njmax is not None else int(wio._default_njmax(m, d0)))
    except (ImportError, AttributeError):
        print("AVISO: heurística nconmax/njmax indisponível; usando 64/128 (ajuste com --nconmax/--njmax)", file=sys.stderr)
        return (nconmax or 64), (njmax or 128)


def decode_overflow(ov, overflow_type) -> dict:
    """Decodifica Data.overflow (bitmask por mundo). ITERATIONS/LS_ITERATIONS = solver parou no limite (benigno); o resto = estouro de buffer (comportamento indefinido)."""
    limit = int(getattr(overflow_type, "ITERATIONS", 0)) | int(getattr(overflow_type, "LS_ITERATIONS", 0))
    cap = ov & ~limit
    names = [f.name for f in overflow_type if f.value and not (f.value & (f.value - 1)) and int(cap.max(initial=0)) & f.value]
    return {"overflow_worlds": int((cap != 0).sum()), "overflow_flags": names, "solver_limit_worlds": int(((ov & limit) != 0).sum())}


class Runner:
    name = ""
    detail = ""
    extra: dict = {}

    def prepare(self) -> None: ...

    def execute(self) -> None: ...

    def health(self) -> dict:
        return {}


class CpuRunner(Runner):
    def __init__(self, m, init: dict, a: argparse.Namespace):
        import mujoco
        import numpy as np
        from mujoco import rollout

        self.np, self.m, self.steps = np, m, a.steps
        nthread = a.threads or os.cpu_count() or 1
        spec = mujoco.mjtState.mjSTATE_FULLPHYSICS
        nstate = mujoco.mj_stateSize(m, spec)
        base = np.zeros(nstate)
        mujoco.mj_getState(m, init["d0"], base, spec)
        probe = mujoco.MjData(m)  # descobre a fatia de qvel no vetor de estado (layout: time, qpos, qvel, act, …)
        z = np.zeros(nstate)
        mujoco.mj_getState(m, probe, z, spec)
        probe.qvel[:] = 7.0
        z2 = np.zeros(nstate)
        mujoco.mj_getState(m, probe, z2, spec)
        idx = np.flatnonzero(z2 != z)
        self.states = np.tile(base, (a.nworld, 1))
        if m.nv:
            self.states[:, idx.min(): idx.max() + 1] = init["qvel"]
        self.control = init["ctrl"][:, None, :] if m.nu else None
        self.datas = [mujoco.MjData(m) for _ in range(nthread)]
        self.out = np.empty((a.nworld, a.steps, nstate))
        self.pool = rollout.Rollout(nthread=nthread)
        self.name = "cpu"
        self.detail = f"mujoco {mujoco.__version__} · mujoco.rollout · {nthread} threads · float64"
        self.extra = {"threads": nthread}

    def execute(self) -> None:
        self.pool.rollout(self.m, self.datas, self.states, self.control, nstep=self.steps, state=self.out)

    def health(self) -> dict:
        np = self.np
        return {"nan_worlds": int((~np.isfinite(self.out[:, -1, :]).all(axis=1)).sum())}


class WarpRunner(Runner):
    """MuJoCo Warp nativo: put_model/put_data(nworld)/step capturado em CUDA graph (como o mjwarp-testspeed)."""

    def __init__(self, m, init: dict, a: argparse.Namespace):
        import numpy as np
        import warp as wp

        wp.config.log_level = wp.LOG_WARNING  # silencia o banner e as linhas "Module … load" (têm de vir antes do 1º uso)
        import mujoco_warp as mjw

        self.np, self.wp, self.mjw, self.steps, self.nworld = np, wp, mjw, a.steps, a.nworld
        wp.set_device(a.device)
        self.dev = wp.get_device()
        self.mw = mjw.put_model(m)
        self.d = mjw.put_data(m, init["d0"], nworld=a.nworld, nconmax=a.nconmax, njmax=a.njmax)
        d0 = init["d0"]
        self.qpos = np.tile(d0.qpos, (a.nworld, 1)).astype(np.float32)
        self.act = np.tile(d0.act, (a.nworld, 1)).astype(np.float32) if m.na else None
        self.qvel = init["qvel"].astype(np.float32)
        self.ctrl = init["ctrl"].astype(np.float32) if m.nu else None
        self.prepare()
        t0 = time.perf_counter()
        with wp.ScopedCapture() as cap:  # compila/carrega os kernels (cache em ~/.cache/warp) e grava o grafo de UM passo
            mjw.step(self.mw, self.d)
        self.graph = cap.graph
        self.capture_s = time.perf_counter() - t0
        self.name = "warp"
        self.detail = f"mujoco_warp {metadata.version('mujoco-warp')} · warp-lang {wp.__version__} · {self.dev.name} · naconmax/mundo={self.d.naconmax // a.nworld} njmax={self.d.njmax}"
        self.extra = {"nconmax_per_world": self.d.naconmax // a.nworld, "njmax": self.d.njmax, "capture_s": round(self.capture_s, 3)}

    def prepare(self) -> None:
        d = self.d
        d.qpos.assign(self.qpos)
        d.qvel.assign(self.qvel)
        if self.ctrl is not None:
            d.ctrl.assign(self.ctrl)
        if self.act is not None:
            d.act.assign(self.act)
        d.qacc_warmstart.zero_()
        d.time.zero_()
        self.wp.synchronize_device(self.dev)

    def execute(self) -> None:
        wp, g = self.wp, self.graph
        for _ in range(self.steps):
            wp.capture_launch(g)
        wp.synchronize_device(self.dev)

    def health(self) -> dict:
        np, d = self.np, self.d
        q = d.qpos.numpy()
        return {
            "nan_worlds": int((~np.isfinite(q).all(axis=1)).sum()),
            **decode_overflow(d.overflow.numpy(), self.mjw.OverflowType),
            "mean_ncon_per_world": round(float(d.nacon.numpy()[0]) / self.nworld, 2),
            "mean_nefc_per_world": round(float(d.nefc.numpy().mean()), 1),
            "max_nefc": int(d.nefc.numpy().max()),
        }


class MjxRunner(Runner):
    """MJX: jit(lax.scan(vmap(mjx.step))). impl='jax' (XLA) ou impl='warp' (JAX FFI → MuJoCo Warp)."""

    def __init__(self, m, init: dict, a: argparse.Namespace):
        try:  # warp antes do mjx: silencia o banner do Warp (mujoco.mjx importa o warp se estiver instalado)
            import warp as wp

            wp.config.log_level = wp.LOG_WARNING
        except ImportError:
            wp = None
        import jax
        import jax.numpy as jnp
        import numpy as np
        from mujoco import mjx

        if jax.default_backend() != "gpu":
            raise SystemExit(f"JAX NÃO enxerga a GPU (backend={jax.default_backend()}): instale jax[cuda12] (ou cuda13) na .venv-gpu — ver references/gpu-benchmarks.md")
        self.jax, self.jnp, self.np, self.steps, self.nworld, self.impl = jax, jnp, np, a.steps, a.nworld, a.impl
        kw_put, kw_data, extra = {}, {}, {}
        if a.impl == "warp":
            if wp is None:
                raise SystemExit("--impl warp exige warp-lang instalado na venv")
            import mujoco.mjx.warp as mjxw
            if a.graph_mode:
                kw_put["graph_mode"] = getattr(mjxw.types.GraphMode, a.graph_mode)  # Δ doc: NÃO é mjxw.GraphMode
            nconmax, njmax = default_contact_limits(m, init["d0"], a.nconmax, a.njmax)
            kw_data = {"naconmax": a.nworld * nconmax, "njmax": njmax}  # naconmax = contatos de TODOS os mundos
            extra = {"nconmax_per_world": nconmax, "njmax": njmax, "graph_mode": a.graph_mode or "WARP"}
        self.mx = mjx.put_model(m, impl=a.impl, **kw_put)
        template = mjx.make_data(m, impl=a.impl, **kw_data)
        d0 = init["d0"]
        qpos0, act0 = jnp.asarray(d0.qpos, jnp.float32), jnp.asarray(d0.act, jnp.float32)
        self.qvel_b, self.ctrl_b = jnp.asarray(init["qvel"], jnp.float32), jnp.asarray(init["ctrl"], jnp.float32)
        steps = a.steps
        vstep = jax.vmap(mjx.step, in_axes=(None, 0))

        def make_one(qv, ct):
            return template.replace(qpos=qpos0, qvel=qv, ctrl=ct, act=act0)

        self.make_batch = jax.jit(jax.vmap(make_one))

        def rollout(mx, b):
            out, _ = jax.lax.scan(lambda c, _: (vstep(mx, c), None), b, None, length=steps)
            return out

        self.rollout = jax.jit(rollout, donate_argnums=(1,))  # donate: o lote de entrada vira o carry (sem cópia extra de VRAM)
        self.batch, self.out = None, None
        self.name = "mjx-" + a.impl
        self.detail = f"mujoco-mjx {metadata.version('mujoco-mjx')} impl={a.impl} · jax {jax.__version__} · {jax.devices()[0].device_kind}" + (
            f" · warp-lang {wp.__version__}" if a.impl == "warp" else "")
        self.extra = extra

    def prepare(self) -> None:
        self.out = None
        self.batch = self.make_batch(self.qvel_b, self.ctrl_b)
        self.jax.block_until_ready(self.batch)

    def execute(self) -> None:
        batch, self.batch = self.batch, None
        self.out = self.rollout(self.mx, batch)
        self.jax.block_until_ready(self.out)

    def health(self) -> dict:
        jnp, o = self.jnp, self.out
        h = {"nan_worlds": int((~jnp.isfinite(o.qpos).all(axis=1)).sum())}
        st = self.jax.devices()[0].memory_stats() or {}
        h["jax_peak_bytes_in_use_mib"] = round(st.get("peak_bytes_in_use", 0) / 2**20)
        h["jax_bytes_limit_mib"] = round(st.get("bytes_limit", 0) / 2**20)
        if self.impl == "warp":
            ov = getattr(o._impl, "overflow", None)
            if ov is not None:
                import mujoco.mjx.warp as mjxw

                h.update(decode_overflow(self.np.asarray(ov), mjxw.mjwp_types.OverflowType))
        return h


# ---------------------------------------------------------------------------------------------------------------------------------------------
# protocolo de medição


def measure(r: Runner, a: argparse.Namespace, mon: VramMonitor | None) -> dict:
    t0 = time.perf_counter()
    r.prepare()
    r.execute()  # JIT (jax) / 1º lançamento do grafo (warp) / 1ª rollout (cpu)
    first_s = time.perf_counter() - t0
    warm_t0, n, last = time.perf_counter(), 0, 0.0
    while n < a.warmup or time.perf_counter() - warm_t0 < a.min_warm_s:
        r.prepare()
        t1 = time.perf_counter()
        r.execute()
        last = time.perf_counter() - t1
        n += 1
        if time.perf_counter() - warm_t0 > a.budget_s / 2:
            break
    reps = a.reps
    if last > 0 and last * reps > a.budget_s and reps > 3:
        reps = max(3, int(a.budget_s / last))
        print(f"AVISO: cada repetição leva ~{last:.1f} s; --reps reduzido de {a.reps} para {reps} (--budget-s {a.budget_s:g})", file=sys.stderr)
    if mon:
        mon.paused.set()  # sem nvidia-smi durante o trecho cronometrado
    times = []
    for _ in range(reps):
        r.prepare()
        t1 = time.perf_counter()
        r.execute()
        times.append(time.perf_counter() - t1)
    if mon:
        mon.paused.clear()
    sps = [a.nworld * a.steps / t for t in times]
    return {"first_run_s": first_s, "warmup_runs": n, "reps": reps, "rep_seconds": times, "sps_median": statistics.median(sps), "sps_min": min(sps), "sps_max": max(sps)}


def versions() -> dict:
    out = {}
    for pkg in ("mujoco", "mujoco-mjx", "mujoco-warp", "warp-lang", "jax", "jaxlib", "jax-cuda12-plugin", "jax-cuda13-plugin", "numpy"):
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            pass
    return out


def is_oom(exc: BaseException) -> bool:
    s = f"{type(exc).__name__}: {exc}".lower()
    return any(k in s for k in ("resource_exhausted", "out of memory", "failed to allocate", "cuda error 2", "cudamalloc", "oom"))


def main(argv: list[str] | None = None) -> int:
    a = parse_args(argv)
    configure_env(a)
    gpu = a.backend != "cpu"
    mon = VramMonitor(a.min_free_mib) if gpu and smi_device() else None
    if mon:
        mon.start()
    t_start = time.perf_counter()
    try:
        m = load_model(a)
        init = make_initial(m, a)
        t0 = time.perf_counter()
        r = {"cpu": CpuRunner, "warp": WarpRunner, "mjx": MjxRunner}[a.backend](m, init, a)
        setup_s = time.perf_counter() - t0
        res = measure(r, a, mon)
        health = r.health()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        oom = is_oom(e)
        print(f"FALHA ({'sem memória/OOM' if oom else type(e).__name__}): {str(e).splitlines()[0][:300] if str(e) else ''}", file=sys.stderr)
        if not oom:
            import traceback

            traceback.print_exc()
        return 3 if oom else 2
    finally:
        if mon:
            mon.stop_flag.set()
    proc_final = dev_final = None
    if mon:
        proc_final, dev_final = mon.sample()
    ts = res["rep_seconds"]
    out = {
        "backend": a.backend, "impl": a.impl if a.backend == "mjx" else None, "runner": r.name, "model": os.path.abspath(a.model), "nworld": a.nworld, "steps": a.steps,
        "nv": int(m.nv), "nu": int(m.nu), "solver": int(m.opt.solver), "iterations": int(m.opt.iterations), "ls_iterations": int(m.opt.ls_iterations), "timestep": float(m.opt.timestep),
        "setup_s": round(setup_s, 3), "first_run_s": round(res["first_run_s"], 3), "warmup_runs": res["warmup_runs"], "reps": res["reps"],
        "rep_seconds": [round(t, 4) for t in ts], "sps_median": round(res["sps_median"]), "sps_min": round(res["sps_min"]), "sps_max": round(res["sps_max"]),
        "us_per_step_world": round(1e6 / res["sps_median"], 3), "realtime_factor": round(res["sps_median"] * float(m.opt.timestep) / a.nworld, 2),
        "vram_process_final_mib": proc_final, "vram_process_peak_mib": mon.peak_proc if mon else None,
        "vram_device_used_peak_mib": mon.peak_dev if mon else None, "vram_device_baseline_mib": mon.baseline[0] if mon and mon.baseline else None,
        "vram_total_mib": mon.baseline[1] if mon and mon.baseline else None, "health": health, "extra": r.extra, "versions": versions(), "total_s": round(time.perf_counter() - t_start, 1),
    }
    if not a.json:
        mname = os.path.basename(a.model)
        print(f"== gpu_bench: {r.name}  modelo={mname} (nv={m.nv} nu={m.nu} dt={m.opt.timestep:g} solver={'newton' if m.opt.solver == 2 else 'cg' if m.opt.solver == 1 else 'pgs'} it={m.opt.iterations}/{m.opt.ls_iterations})")
        print(f"   {r.detail}")
        print(f"   nworld={a.nworld} steps={a.steps} reps={res['reps']} (aquecimento: {res['warmup_runs']} exec.) · python {platform.python_version()} · CPU lógicas {os.cpu_count()}")
        print(f"   setup {setup_s:.2f} s · 1ª execução (JIT/captura) {res['first_run_s']:.1f} s")
        print(f"   SPS mediana: {res['sps_median']:,.0f}  (min {res['sps_min']:,.0f} · máx {res['sps_max']:,.0f}) · {out['us_per_step_world']} µs/passo/mundo · tempo real ×{out['realtime_factor']} por mundo")
        print(f"   tempos das repetições (s): {[round(t, 4) for t in ts]}")
        if mon:
            print(f"   VRAM processo (nvidia-smi): final {proc_final} MiB · pico {mon.peak_proc} MiB · dispositivo: pico {mon.peak_dev}/{out['vram_total_mib']:.0f} MiB (base {out['vram_device_baseline_mib']:.0f} MiB antes do processo)")
        else:
            print("   VRAM: n/a (backend cpu)" if a.backend == "cpu" else "   VRAM: nvidia-smi indisponível")
        print(f"   saúde: {health}")
        if health.get("nan_worlds"):
            print(f"   AVISO: {health['nan_worlds']} mundo(s) com NaN — simulação instável (ajuste --iterations/--ls-iterations/--ctrl-noise): o SPS NÃO é representativo")
        if health.get("overflow_worlds"):
            print(f"   AVISO: estouro de buffer {health.get('overflow_flags')} em {health['overflow_worlds']} mundo(s): aumente --nconmax/--njmax (comportamento indefinido no MuJoCo Warp)")
    print("RESULT_JSON " + json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
