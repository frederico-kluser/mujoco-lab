# Playbook de experimentos físicos e mecânicos

Como CRIAR, VALIDAR e REGISTRAR experimentos no laboratório: método, esqueleto executável, validação de energia, caso-estudo (triângulo invertido) e catálogo de 17 experimentos com valor analítico × medido.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: `pesquisas/conhecimento/Q15.md` (principal), `Q3.md`/`Q4.md`/`Q14.md` (consulta), `experiments/01_triangulo_invertido/`, `experiments/02_pendulo/` (ambos **removidos em 2026-10-08**; histórico no git), `.agents/mujoco-lab-agent-skill/scripts/{mjkit,new_experiment,inspect_model}.py`, `docs/upstream/mujoco/doc/{XMLreference,modeling,computation/index,computation/fluid}.rst`, `docs/upstream/mujoco/model/{slider_crank,arch,replicate}/` e testes locais (✔).

## Quando ler este arquivo
- Ao criar um experimento (`experiments/NN_nome/`) ou validar um modelo contra física analítica antes de confiar em resultados complexos.
- Ao escolher um teste de regressão no catálogo (§7): fórmula, tolerância e valor medido já conferidos.
- Ao depurar energia que "sobe", ressalto, atrito que depende da direção, rolamento ou pilhas que caem (§5, Armadilhas).
- Robôs, drones e veículos têm templates próprios (§8); aqui fica a mecânica-base que valida o resto.

## 1. O método do laboratório
Regra: **nunca "rodar e olhar o vídeo"** — todo experimento termina em critério numérico com exit code (0 = passou · 1 = falhou).

| # | Etapa | Como | Saída |
|---|---|---|---|
| 1 | Hipótese | Uma frase + valor esperado em fórmula fechada + tolerância, escritos antes de rodar | README: «esperado X ± tol» |
| 2 | Modelo MJCF | SI, +Z, quaternion `[w x y z]`, graus; `models/` (reutilizável) ou `experiments/NN/model.xml`; esperados em `<custom><numeric>` | compila (`from_xml_string`) |
| 3 | Massa/inércia/CM | Comparar `body_mass`, `body_inertia`, `body_ipos` com fórmulas fechadas (§3) ANTES de simular | erro ≲ 1e-6 |
| 4 | Simulação headless | Loop `mj_step` ou `mjkit.record`; `<flag energy="enable"/>`; sem janela (`MUJOCO_GL=egl`) | sem NaN/aviso |
| 5 | Métricas | Grandeza física a partir de `qpos`/`qvel` (não de `xpos`, atrasado 1 passo — Armadilhas; ou `record(..., consistent=True)`) | números |
| 6 | Critério | Lista `(nome, ok, detalhe)` com ≥ 3 grandezas comparadas a fórmulas fechadas; `sys.exit(0 if todos ok else 1)` | exit code |
| 7 | Convergência | Repetir com `dt/2`: a métrica converge na ordem esperada? (§4) | tabela erro × dt |
| 8 | Mídia | `mjkit.record(mp4=, gif=, sheet=)` + `mjkit.plot` → `out/` (ignorado pelo git); para um MJCF qualquer sem controlador: `render_video.py <modelo> --gif --sheet --camera frontal --out out/video` (✔) | vídeo, GIF, filmstrip, gráfico |
| 9 | README | Molde: `experiments/09_drone_hover_rl/README.md` (o molde original era o `experiments/01_triangulo_invertido/README.md`, removido em 2026-10-08 — histórico no git) — Rodar · Resultados analítico × simulado · O que observar · Botões · Como foi construído · Lições | `README.md` |
| 10 | Memória CoALA | `python3 .agents/mujoco-lab-agent-skill/scripts/coala.py add --type procedural --key experimento/NN_nome --tags experimento --content "<números e lições>"` (✔ sintaxe e supersessão por `--key` testadas num banco temporário via `--db`; `recall` no início da tarefa) | registro `#id` |

Critérios de aceitação típicos (✔ todos medidos aqui; relaxe só com motivo documentado):

| Grandeza | Tolerância sugerida | Medido |
|---|---|---|
| massa/inércia: primitivas · malhas | 1e-9 (float64) · 1e-6 (vértices float32) | 3.7e-8 … 9.3e-8 (malhas) |
| instante de impacto (cruzamento interpolado de `qpos`) | ±0.2·dt ao redor de √(2h/g) − dt/2 | exato |
| 1º contato visível em `data.ncon` | ≥ 3·dt | 1–2 passos |
| energia com contato | envelope: ≤ 0.5–1 % de E0 (+ ~1 J) | +0.3 % transitório |
| repouso · altura de repouso | \|v\| < 1e-3 m/s e \|ω\| < 1e-2 rad/s · ±3 mm (`run.py` do exp. 01 — removido em 2026-10-08; histórico no git) | 1e-12 · 0.108 mm de penetração |
| período/frequência (sem contato) | 0.5 % (`--tol` do exp. 02 — removido em 2026-10-08) | Euler 2 ms: 2e-4 %; RK4: ≲ 1e-6 % |
| atrito, rolamento, cone (contato mole) | 1–3 % | 0.1–2 % (E3–E5) |
| momento (forças internas) | 1e-12 relativo | 7e-16 (E10) |

## 2. Estrutura, ferramentas e esqueleto
- Pasta: `experiments/NN_nome/{model.xml, run.py, README.md, out/}`; `lab/mjkit.py` = symlink/cópia de `scripts/mjkit.py`.
- `new_experiment.py` (só stdlib): acha a raiz (`pyproject.toml`), escolhe o próximo NN (hoje **10** — existe só o `09_drone_hover_rl`), copia o template, cria `lab/mjkit.py` e `experiments/*/out/` no `.gitignore`; nunca sobrescreve; `--list`, `--dry-run`, `--template blank|pendulum|arm|quadrotor|car`.
- `mjkit` (importe ANTES de `mujoco`: define `MUJOCO_GL=egl`): `load(caminho|string)` liga `data.energy`; `Ctrl` escreve controles por NOME (correto p/ atuadores multi-entrada `pid`/`dcmotor`/`orientation`); `record(model, data, controller, duration, slowmo, camera, mp4, gif, sheet, probes, hud, contacts, track, consistent)` chama `controller` ANTES de cada `mj_step` (`consistent=True` faz `mj_forward` após o passo: sondas, contatos e energia correspondem a `data.time` — ✔ erro de `xipos` 1.96 mm → 0) → `{"log": {t, ncon, pe, ke, <probes>}, "frames", "wall_s"}`; `plot(log, keys, path, refs=)`.
- Esperados em `<custom><numeric name="esperado_x" data="…"/>` → `float(model.numeric("esperado_x").data[0])` (opcional: `mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_NUMERIC, nome) >= 0`, como fazia `numerico()` do exp. 01 — removido em 2026-10-08).
- Janela só a pedido do usuário (aparece na tela dele): `run.py --view` nos templates; `view.py`/`sim_view.py` nos experimentos.
- `inspect_model.py` precisa de numpy+mujoco: use `.venv/bin/python` (exit 0 ok · 1 WARN de risco · 2 erro). Rode scripts com cwd fora da raiz (o MuJoCo grava `MUJOCO_LOG.TXT` no cwd).

```bash
python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py --list                            # blank pendulum arm quadrotor car
python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py queda_ressalto --template blank   # cria experiments/10_queda_ressalto/
# ... substitua model.xml e run.py pelos dois blocos abaixo ...
.venv/bin/python .agents/mujoco-lab-agent-skill/scripts/inspect_model.py experiments/10_queda_ressalto/model.xml --steps 500
.venv/bin/python experiments/10_queda_ressalto/run.py --sem-video; echo "exit=$?"   # sem a flag grava out/video.mp4, video.gif, filmstrip.png
```
✔ testado num projeto-espelho (cwd com `pyproject.toml`, 2 experimentos prévios). Esqueleto completo — queda de esfera com restituição, valores esperados no MJCF:
```xml
<mujoco model="queda_ressalto">
  <compiler angle="degree"/>
  <option timestep="0.002"/>
  <visual><global offwidth="1280" offheight="720"/></visual>
  <custom>   <!-- esperados moram no próprio MJCF: modelo e teste ficam juntos -->
    <numeric name="esperado_h_queda_m" data="0.9"/>      <!-- centro: de 1.0 m até r = 0.1 m -->
    <numeric name="esperado_e"         data="0.7292"/>   <!-- exp(−ζπ/√(1−ζ²)), ζ = c/(2√k) = 10/(2·50) = 0.1 -->
  </custom>
  <worldbody>
    <light pos="1 -2 4" dir="-0.2 0.5 -1"/>
    <camera name="frontal" pos="0 -3 0.8" xyaxes="1 0 0 0 0.05 1"/>
    <geom name="chao" type="plane" size="3 3 0.1" solref="-2500 -10"/>
    <body name="bola" pos="0 0 1.0">
      <freejoint/>
      <geom name="bola" type="sphere" size="0.1" mass="1" solref="-2500 -10" rgba="0.96 0.47 0.1 1"/>
    </body>
  </worldbody>
</mujoco>
```
```python
#!/usr/bin/env python3
"""Queda livre + ressalto (restituição via solref direto). Exit 0 = todas as checagens passaram · 1 = alguma falhou."""
import argparse, sys
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
from lab import mjkit  # noqa: E402  (define MUJOCO_GL=egl ANTES de importar mujoco)

import numpy as np  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--sem-video", action="store_true"); a = ap.parse_args()
AQUI = Path(__file__).resolve().parent
model, data = mjkit.load(AQUI / "model.xml")              # liga data.energy
esp = lambda nome: float(model.numeric(nome).data[0])     # esperados vêm do MJCF (<custom><numeric>)
R, G, dt, h = 0.1, 9.81, model.opt.timestep, esp("esperado_h_queda_m")
mid = {} if a.sem_video else dict(mp4=AQUI / "out/video.mp4", gif=AQUI / "out/video.gif", sheet=AQUI / "out/filmstrip.png")
res = mjkit.record(model, data, None, duration=2.0, slowmo=0.5, camera="frontal", probes={"z": lambda m, d: d.qpos[2]}, **mid)
t, z, E = res["log"]["t"], res["log"]["z"], res["log"]["pe"] + res["log"]["ke"]   # z = qpos (xpos ficaria 1 passo atrasado)
k = int(np.argmax(z - R < 0))                                       # 1º passo abaixo do contato
t_imp = t[k - 1] + dt * (z[k - 1] - R) / (z[k - 1] - z[k])          # cruzamento interpolado
pico = max(z[i] for i in range(k + 1, len(z) - 1) if z[i] > z[i - 1] and z[i] >= z[i + 1])
e = float(np.sqrt((pico - R) / h))
checks = [("t_impacto = √(2h/g) − dt/2", abs(t_imp - (np.sqrt(2 * h / G) - dt / 2)) < 0.2 * dt, f"{t_imp:.5f} s"),
          ("restituição e = esperada ±0.02", abs(e - esp("esperado_e")) < 0.02, f"e = {e:.4f}"),
          ("E(t) nunca excede E0 (+0.5 %)", float(E.max() - E[0]) < 0.005 * abs(E[0]), f"E0 = {E[0]:.3f} J, máx = {E.max():.3f} J")]
for nome, ok, det in checks:
    print(f"[{'OK ' if ok else 'FALHA'}] {nome:32s} {det}")
sys.exit(0 if all(ok for _, ok, _ in checks) else 1)
```
Controle por nome com `Ctrl` e sondas em `record` (alternativa ao `from lab import mjkit`: `sys.path` aponta para a skill):
```python
import sys
sys.path.insert(0, ".agents/mujoco-lab-agent-skill/scripts")      # raiz do projeto como cwd
import mjkit                                                  # define MUJOCO_GL=egl ANTES de importar mujoco

XML = """<mujoco><option timestep="0.001" gravity="0 0 0" integrator="implicitfast"/>
<worldbody><body name="A"><joint name="a" type="hinge" axis="0 1 0"/><inertial pos="0 0 0" mass="1" diaginertia="0.01 0.01 0.01"/></body></worldbody>
<actuator><motor name="mot" joint="a"/></actuator></mujoco>"""
model, data = mjkit.load(XML)                                 # caminho OU string MJCF; liga data.energy
ctrl = mjkit.Ctrl(model)                                      # escrita por NOME via actuator_ctrladr/ctrlnum
res = mjkit.record(model, data, lambda m, d: ctrl.set(d, "mot", 0.5), duration=1.0, probes={"w": lambda m, d: d.qvel[0]})
print(f"ω(1 s) = {res['log']['w'][-1]:.3f} rad/s (τ·t/J = 50) · chaves do log: {sorted(res['log'])}")
```

## 3. Validar massa, inércia e CM antes de simular

| Corpo | Fórmula | ✔ conferido |
|---|---|---|
| esfera maciça (r) | I = 2/5·m·r² | 2 kg, r=0.1 → 0.008 |
| caixa (lados completos a, b, c) | I_x = m(b²+c²)/12 | 0.2×0.4×0.6 m, ρ=1000 → (2.08, 1.6, 0.8) |
| cilindro (r, comprimento h) | I_eixo = ½mr²; I_⊥ = m(3r²+h²)/12 | m=2, r=0.1, h=0.2 → 0.01 / 0.011667 |
| casca cilíndrica fina | I_eixo = m·r² (use `<inertial>` e geom `mass="0"`) | E5 |
| prisma triangular equilátero (aresta a, comprimento L) | m = ρ(√3/4)a²L; I_eixo = ma²/12; I_⊥ = m(L²/12 + a²/24) | §6 |
| tetraedro regular (aresta a) | m = ρa³/(6√2); I = ma²/20 (isotrópico) | §6 |

API: `model.body_mass[b]`; `body_inertia[b]` = momentos PRINCIPAIS no frame inercial `body_iquat` (compare ordenados); `body_ipos[b]` = CM no frame do corpo; `data.xipos[b]` e `data.subtree_com[b]` = CM no mundo (após `mj_forward`); `model.body_subtreemass[b]`.
Inferência pelos geoms — afirmação do relatório («inércia a partir do volume, densidade da água») **correta com ressalvas** (ficha Q15): sem `<inertial>` o corpo soma os geoms com `density=1000` kg/m³; `<inertial>` explícito prevalece; `geom mass=` ignora a densidade; a inércia vem da FORMA (não só do volume); geoms de grupo dentro de `compiler inertiagrouprange` (padrão `0 5`) contam mesmo sem colisão (⚠ geom visual extra: 41.569 kg; `inertiagrouprange="0 0"` → 20.785 kg ✔); malhas têm precisão ~1e-7 (vértices float32).

## 4. Convergência em dt, integradores e reprodutibilidade
Procedimento: rode com `dt`, `dt/2`, `dt/4`; a métrica deve convergir na ordem do integrador. Se não converge, ela é dominada pelo contato/solver, não pelo integrador. Pêndulo de 60° (período exato por integral elíptica, sem contato):
```python
import numpy as np, mujoco
from scipy.special import ellipk

XML = """<mujoco><option timestep="0.002" gravity="0 0 -9.81"><flag contact="disable"/></option>
<worldbody><body pos="0 0 2"><joint name="q" type="hinge" axis="0 1 0"/>
<inertial pos="0 0 -1" mass="1" diaginertia="1e-12 1e-12 1e-12"/></body></worldbody></mujoco>"""
th0 = np.radians(60)
T_exato = 2 * np.pi * np.sqrt(1 / 9.81) * (2 / np.pi) * ellipk(np.sin(th0 / 2) ** 2)    # T0·(2/π)·K(sin²(θ0/2))

def periodo(integrador, dt, ciclos=6):
    m = mujoco.MjModel.from_xml_string(XML); m.opt.integrator = integrador; m.opt.timestep = dt
    d = mujoco.MjData(m); d.qpos[0] = th0; t, x = [], []
    for _ in range(int(ciclos * 2.2 / dt)):
        mujoco.mj_step(m, d); t.append(d.time); x.append(d.qpos[0])
    t, x = np.array(t), np.array(x); i = np.where((x[:-1] < 0) & (x[1:] >= 0))[0]
    return np.mean(np.diff(t[i] - x[i] * (t[i + 1] - t[i]) / (x[i + 1] - x[i])))       # cruzamentos ascendentes interpolados

dts = np.array([0.008, 0.004, 0.002, 0.001])
print("erro relativo do período para dt =", dts * 1000, "ms")
for nome in ("Euler", "implicitfast", "RK4"):
    err = [abs(periodo(getattr(mujoco.mjtIntegrator, "mjINT_" + nome.upper()), dt) / T_exato - 1) for dt in dts]
    print(f"{nome:13s}", " ".join(f"{e:.2e}" for e in err), "· razão entre dt consecutivos (2^ordem):", np.round(np.array(err[:-1]) / np.array(err[1:]), 1))
```
| Integrador | Usar quando | Medido ✔ |
|---|---|---|
| `Euler` (padrão) | geral, contato | bloco acima: 1.3e-5 / 3.3e-6 / 8.2e-7 / 2.0e-7 (razão 4.0 = ordem 2, símplético); queda livre: perde exatamente ½·m·g²·dt² por passo; corpo livre girando (E13): KE/KE0 = 1.112 |
| `implicitfast` (recomendado p/ a maioria) | atuadores kv/kp, amortecimento, fluidos | idêntico ao Euler no pêndulo; com `velocity kv=10..50` estável onde o Euler diverge; E13: KE/KE0 = 0.903 |
| `RK4` | sistemas conservativos sem contato | 1.4e-8 em 8 ms e ≈1e-10 abaixo disso (piso da medição por interpolação: para ver a ordem 4 use energia); E13: KE/KE0 = 1.000000; ≈3.7× mais caro (371 vs 99 µs/passo na torre do E17); sem ganho com contato |
| `implicit` | cadeias girando rápido | pião ω=200 rad/s (E12): estável, porém dissipativo (precessão −1.2 %) |
| `discrete` (3.13+) | molas/servos rígidos com contato | não explode com `solref 0.02 0.05` (Euler explode, Armadilhas); mas diverge no pião como o Euler |

Contato: o erro do 1º impacto é −dt/2 (Euler: z_n = z0 − ½·g·dt²·n(n+1)); a penetração em repouso NÃO depende de dt (0.1078 mm de 0.5 a 10 ms) e a penetração máxima depende (30.8 → 15.3 mm): não a use como métrica.
Reprodutibilidade ✔: o mesmo script dá `sha256(qpos, qvel)` idêntico em 3 processos separados, em laço ou em `mj_step(m, d, nstep=n)`, e após `mj_resetData`; `mjtNum` é float64; use `np.random.default_rng(seed)` para perturbações; `mujoco.rollout` dá o mesmo resultado para qualquer nº de threads (ficha Q14, não retestado). Caos: compare trajetórias só até t ≈ ln(tol/erro0)/λ (E7).

## 5. Energia: a armadilha e a validação correta
⚠ `data.energy = [potencial, cinética]` (exige `<flag energy="enable"/>`; também há sensores `e_potential`/`e_kinetic`). O potencial inclui gravidade e molas passivas de junta/tendão/flex, **mas não a energia elástica do contato nem de outras restrições** (`XMLreference.rst`, option/flag/energy). Efeito ✔ (prisma, queda de 1 m): E 250.985 → 23.522 J (m·g·r = 23.544 J), E(t) ≤ E0 sempre, porém 476 passos com ΔE > 0 (máx. +0.807 J = 0.3 % de E0) e E chega a 22.06 J, abaixo do valor final; berço de Newton: E/E0 = 0.9929 antes e depois do impacto (t = 0.207 s) mas cai a 0.927 durante ele.
Como validar (do mais barato ao mais rigoroso):
1. **Envelope**: `E.max() − E[0] < 0.5 % de E0` (+ ~1 J) — não exija monotonicidade passo a passo.
2. **Sem contato** (pêndulo, mola, corpo livre): deriva relativa pequena com RK4 ou `dt` pequeno (§4).
3. **Estado final**: E_final = m·g·r_inscrito (23.544 J) menos a penetração em repouso (23.522 J ✔); ressalto: pico = e²·h.
4. **Balanço de trabalho** (vale com contato): ΔE(t) = ∫ qvelᵀ·qfrc_constraint dt. Use a regra do TRAPÉZIO (v antes e depois do passo; só com v depois o resíduo vai a 30–98 J) e lembre que, após `mj_step`, `energy` e `qfrc_constraint` descrevem o INÍCIO do passo. Cobre contato, limites e `equality` (só `qfrc_constraint`); com atuadores some o trabalho de `qfrc_actuator` (não testado).
```python
import numpy as np, mujoco

XML = """<mujoco><option timestep="0.002"><flag energy="enable"/></option>
<worldbody><geom name="chao" type="plane" size="3 3 0.1" solref="-2500 -10"/>
<body pos="0 0 1"><freejoint/><geom type="sphere" size="0.1" mass="1" solref="-2500 -10"/></body></worldbody></mujoco>"""

def balanco_energia(m, d, T):
    """max|ΔE(t) − ∫ qvelᵀ·qfrc_constraint dt| (trapézio) e max|ΔE|. Exige <flag energy="enable"/>."""
    dt = m.opt.timestep; mujoco.mj_forward(m, d)
    E0, v, W, res, dEmax = d.energy.sum(), d.qvel.copy(), 0.0, 0.0, 0.0
    for _ in range(int(T / dt)):
        mujoco.mj_step(m, d)                      # após mj_step, energy e qfrc_constraint descrevem o INÍCIO do passo
        dE = d.energy.sum() - E0                  # estado de v (início do passo)
        res, dEmax = max(res, abs(dE - W)), max(dEmax, abs(dE))
        W += dt * d.qfrc_constraint @ (0.5 * (v + d.qvel)); v = d.qvel.copy()
    return res, dEmax

m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m)
res, dEmax = balanco_energia(m, d, 2.0)
print(f"resíduo máx {res:.3e} J  ({100 * res / dEmax:.3f} % de max|ΔE| = {dEmax:.3f} J)")   # ✔ 4.1e-02 J, 0.43 %
```
✔ Vale para Euler, `implicit`, `implicitfast` e `discrete` (0.43 % nos quatro); ⚠ com RK4 o resíduo vai a 22.7 % (após `mj_step`, `energy` e `qfrc_constraint` vêm de um estágio intermediário — `physics-tuning.md`). Mesmo resultado no prisma de face para baixo, queda de 1 m (resíduo 0.90 J de 210 J = 0.43 %; ΔE final −203.919 J = trabalho do contato −203.919 J). Não verificado: somar a energia elástica via `efc_KBIP·efc_pos` (discussão #2347 do GitHub, citada na ficha Q15).

## 6. Caso-estudo: triângulo de cabeça para baixo (experimento 01 — **removido em 2026-10-08**; histórico no git)
Prisma triangular equilátero (aresta 0.4 m, comprimento 0.3 m, 20.78 kg) solto a 1 m com a aresta para baixo; tomba e repousa numa face. O `experiments/01_triangulo_invertido/run.py [--modelo models/tetraedro_invertido.xml] [--sem-video] [--saida DIR]` validava tudo e dava exit 0/1 (✔ prisma e tetraedro passavam; o script foi removido em 2026-10-08 — histórico no git; os modelos `models/triangulo_invertido.xml` e `models/tetraedro_invertido.xml` mantêm-se). Script mínimo (MJCF + checagens; vértices relativos ao CM):
```python
import numpy as np, mujoco

XML = """<mujoco model="prisma_triangular_invertido">
  <option timestep="0.002"><flag energy="enable"/></option>
  <asset>
    <mesh name="prisma" inertia="convex"
          vertex="-0.15 0 -0.23094011  -0.15 -0.2 0.11547005  -0.15 0.2 0.11547005
                   0.15 0 -0.23094011   0.15 -0.2 0.11547005   0.15 0.2 0.11547005"/>
  </asset>
  <custom>   <!-- esperados analíticos: a = 0.4 m, L = 0.3 m, ρ = 1000 kg/m³ -->
    <numeric name="esperado_massa_kg" data="20.7846097"/>
    <numeric name="esperado_altura_repouso" data="0.11547005"/>   <!-- raio inscrito a/(2√3) -->
  </custom>
  <worldbody>
    <geom name="chao" type="plane" size="3 3 0.1"/>
    <body name="prisma" pos="0 0 1.23094011" euler="1 0 0">       <!-- 1° de tilt quebra a simetria -->
      <freejoint/>
      <geom name="prisma" type="mesh" mesh="prisma"/>            <!-- sem type="mesh" vira ESFERA -->
    </body>
  </worldbody>
</mujoco>"""
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m); b, g = m.body("prisma").id, m.geom("prisma").id
num = lambda nome: float(m.numeric(nome).data[0])
a, L = 0.4, 0.3
I_esp = sorted(num("esperado_massa_kg") * np.array([a * a / 12, L * L / 12 + a * a / 24, L * L / 12 + a * a / 24]))
print("massa", m.body_mass[b], "esperada", num("esperado_massa_kg"))
print("inércia principal", np.sort(m.body_inertia[b]), "esperada", np.round(I_esp, 7))
mujoco.mj_forward(m, d)
v = m.mesh_vert[m.mesh_vertadr[0]: m.mesh_vertadr[0] + m.mesh_vertnum[0]]            # vértices (float32) no frame da malha recentrada
h0 = (d.geom_xpos[g] + v @ d.geom_xmat[g].reshape(3, 3).T)[:, 2].min()               # ponto mais baixo ≈ 1.000035 m
t_prev, t_c = np.sqrt(2 * h0 / 9.81), None
for _ in range(3000):                                                               # 6 s
    mujoco.mj_step(m, d)
    if t_c is None and d.ncon: t_c = d.time
print(f"impacto previsto {t_prev:.4f} s · 1º contato {t_c:.4f} s (Δ = {1e3 * (t_c - t_prev):.1f} ms ≈ 1–2 passos)")
print(f"z_CM final {d.xipos[b, 2]:.7f} m (raio inscrito {num('esperado_altura_repouso'):.7f}) · contatos {d.ncon} · |v| {np.linalg.norm(d.qvel):.1e}")
```
| Verificação | Analítico | Medido ✔ (dt = 2 ms, Euler) |
|---|---|---|
| massa (prisma / tetraedro) | 20.7846097 / 7.5424723 kg | 20.7846105 (3.7e-8) / 7.5424722 (1.2e-8) |
| inércia principal do prisma (kg·m²) | 0.2771281 · 0.2944486 · 0.2944486 | 0.2771281 · 0.2944487 · 0.2944487 (≤ 9.3e-8); tetraedro 0.0603398 = m a²/20 |
| tempo do cruzamento z = 0 (vértice mais baixo, `mj_kinematics`, interpolado) | √(2h/g) = 0.451532 s | 0.450532 s (−1.000 ms = −dt/2) |
| 1º contato visível em `data.ncon` | idem | 0.454 s (1–2 passos depois; tol. ≥ 3·dt) |
| energia | E0 = 250.985 J → m·g·r = 23.544 J | 23.522 J; 476 passos com ΔE > 0 (máx. +0.807 J) |
| altura do CM em repouso | raio inscrito a/(2√3) = 0.115470 m (tetraedro a√6/12 = 0.081650) | 0.115362 m, 4 contatos (0.081508 m, 3 contatos) |
| tombamento com tilt de 1° (e de 0.1°) | face lateral: 60° (tetraedro: arccos(1/3) = 70.529°) | ±60° conforme o sinal do tilt; 70.529°; \|Δroll\|>30° em 0.936 s (1°) e 1.326 s (0.1°) |
| sem tilt (equilíbrio instável) | — | só tomba por ruído (≈ 7–8 s; sem significado físico): use SEMPRE perturbação explícita |

- ⚠ `<geom mesh=…>` **sem `type="mesh"`** vira esfera ajustada (`geom_type` 2; massa 12.581 kg em vez de 20.785 ✔). `<mesh vertex=…>` sem `face` = nuvem de pontos: o casco convexo é calculado (prisma: 8 faces; tetraedro: 4); < 4 vértices ou coplanares → erro de compilação ✔.
- A malha é **recentrada no CM** e alinhada aos eixos principais (`body_ipos ≈ 1e-18`, `body_iquat` = rotação): a altura do CM é `data.xipos[b, 2]` (após `mj_kinematics`), não `qpos[2]`. Para colisão toda malha vira seu casco **convexo** (côncava → vários geoms convexos); plano–malha dá ≤ 4 contatos (`mj_maxContact`, ficha Q15; ✔ 4 na face do prisma).
- `inertia=` (padrão `legacy`; doc recomenda `convex`): em malhas **convexas** `legacy`, `convex` e `exact` dão massa/inércia idênticas ✔; no **U côncavo** (volume real 8.0e-3 m³): `legacy` +39.7 %, `convex` +50 % (volume do casco), `exact` exato ✔ (exige malha fechada e bem orientada; `shell` reinterpreta density como kg/m²). `maxhullvert` (padrão −1; deve ser > 3) limita o casco: prisma com 5 → 13.856 kg (2/3) ✔.
- Ressalto (queda de 1 m, face para baixo, dt = 2 ms; e = √(pico/h)) ✔ — penetração em repouso = a_u(1−d)·timeconst²·dampratio² ÷ n contatos:

| `solref` | pen. máx. | ressalto | e | e linear exp(−ζπ/√(1−ζ²)) |
|---|---|---|---|---|
| `0.02 2` / `0.02 1` (padrão) | 35.8 / 30.5 mm | nenhum (rep. 0.367 / 0.108 mm) | 0 | — |
| `0.02 0.5` / `0.02 0.2` / `0.02 0.1` | 23.0 / 13.0 / 6.8 mm | 74.5 / 346 / 596 mm | 0.273 / 0.588 / 0.772 | 0.163 / 0.527 / 0.729 |
| `-2500 -10` / `-2500 0` (direto) | 74.8 mm / — | 542 mm / não repousa | 0.736 / 1.002 | 0.729 / 1 |
| `0.005 1` / `0.05 1` | 7.0 / 77.9 mm | 11.8 mm / nenhum | — | — |

Repouso no exp. 01 (removido em 2026-10-08; medições preservadas — histórico no git; `solref` timeconst 0.01, 4 contatos): `dampratio` ≥ 0.5 repousa em ~0.8 s; 0.3 e 0.4 não repousam em 8 s e 0.45 fica no limite ✔; numa esfera 0.2 repousa e ≲ 0.1 vibra > 30 s (ficha Q4). Não existe atributo `restitution` (✔ rejeitado: «unrecognized attribute»): use `solref` (doc: `modeling.rst`, §Restitution).

## 7. Catálogo de experimentos
Tabela A — o que cada um demonstra, como modelar e as pegadinhas. Tabela B — números (analítico × medido; os 17 foram executados em 3.15.0 = ✔, nenhum «não testado»; os scripts de medição, de 20–40 linhas, não foram versionados: reimplemente-os a partir das colunas «Modelo» e «Analítico», usando o esqueleto do §2).

| # | Experimento | Modelo / atributos-chave | Pegadinhas |
|---|---|---|---|
| E1 | Queda livre | `freejoint`, esfera, `plane`; medir `qpos` | contato só nasce com `dist<margin`; Euler: t = √(2h/g) − dt/2 |
| E2 | Ressalto (restituição) | `solref="-k -c"` (k em 1/s², c em 1/s, por unidade de massa; ζ = c/(2√k)); `-1000 0` = elástico (doc) | sem atributo `restitution`; solref do chão e do geom se misturam (média por `solmix`; ficha Q4); e varia com forma/massa/altura (`0.02 0.5`: 0.250 esfera 1 kg, 0.263 esfera 4.19 kg [Q4], 0.273 prisma) |
| E3 | Bloco com atrito | `box` achatado em `plane`; `friction="μ 0.005 0.0001"` | μ do contato = MÁX(geom1, geom2) (padrão 1); cubo com μ ≥ w/h tomba; meça a inclinação de v(t), não o instante em que v < ε (creep = deslize lento no fim) |
| E4 | Plano inclinado | plano `euler="0 θ 0"` (desce para +x); `cone`, `impratio` | cone `pyramidal` (padrão) é anisotrópico; abaixo do limiar há creep ~1e-3 m/s: use v(2 s) > 0.05 |
| E5 | Rolamento sem deslizar | `sphere`/`cylinder euler="90 0 0"`; casca: `<inertial>` + geom `mass="0"`; `condim` 3 vs 6 | `condim=6` + `friction[2]` (rolamento) freia; μ ≥ tanθ·k/(1+k), k = I/(m r²) |
| E6 | Pêndulo simples | template `pendulum` (o `experiments/02_pendulo` foi removido em 2026-10-08); I_pivô por `mj_fullM`, CM por `xipos` | `qpos` da junta em rad mesmo com `angle="degree"`; RK4 p/ energia |
| E7 | Pêndulo duplo (caos) | 2 hinges, massas pontuais `<inertial … diaginertia="1e-9 1e-9 1e-9">`, `<flag contact="disable"/>` | q2 é RELATIVO (θ2 = q1 + q2); referência = `scipy` DOP853; só compare até t_div |
| E8 | Massa-mola-amortecedor | `slide` com `stiffness`, `damping` + `<inertial>`; `gravity="0 0 0"` | `armature` soma à massa; mola explícita limita dt (ω·dt < 2); `data.energy` inclui a mola |
| E9 | Projétil com arrasto quadrático | `<option density viscosity integrator="implicitfast">`; geom `fluidshape="ellipsoid" fluidcoef="Cb 0.25 1.5 1 1"` ou modelo padrão (caixa de inércia) | F = ρ·C·A·v² SEM o ½ (C_D de livro = 2·Cb); caixa: f = 2ρ·r_j·r_k·\|v\|v (r = semi-lados da caixa equivalente: esfera r = R√(3/5)); sem empuxo (balões usam `gravcomp`) |
| E10 | Colisão elástica 1D | 2 esferas em `slide` X, `gravity="0 0 0"`, `condim="1"`, `friction="0 0 0"`, `solref="-1e4 0"` | só `solref="-k 0"` (c = 0) conserva E; o momento é conservado MESMO com contato amortecido |
| E11 | Berço de Newton | `docs/upstream/mujoco/model/replicate/newton_cradle.xml` (`<replicate>`, dt=1e-4, `solref="-1e8 -0"`, cordas = tendões `limited`) | cordas são forças externas: p ≠ constante (use E10); a energia tem queda transitória no impacto (§5) |
| E12 | Pião (precessão) | `joint type="ball"` no pivô + `<inertial pos="0 0 d" diaginertia="I1c I1c I3">` | qvel da ball joint no frame LOCAL; Euler/implicitfast/discrete explodem em rotação rápida; na fórmula use I1 = I1c + m·d² (o MuJoCo aplica Steiner sozinho) |
| E13 | Eixo intermediário (raquete de tênis / Dzhanibekov) | `freejoint` + `<inertial diaginertia="1 2 3">`, `gravity="0 0 0"` | `qvel[3:6]` no frame do corpo; Euler/implicit* perdem/ganham ~10 % de KE: use RK4 |
| E14 | Biela-manivela | hinge + hinge + slide + `<equality><connect body1 body2 anchor>`; `<velocity kv>`; oficial `slider_crank.xml` (`cranksite/slidersite/cranklength`) | `kv` + Euler diverge → `implicitfast`; `qpos` da slide é relativo (x = r+l+q); extremo da biela dentro do pistão cria contato → `contype="0" conaffinity="0"` |
| E15 | Engrenagens | `<equality><joint joint1="b" joint2="a" polycoef="0 -n 0 0 0"/>` (y−y0 = a0 + a1(x−x0)+…); `<motor>` | restrição mole (`solref` padrão 0.02 1 → 1.2 mrad); inércia refletida J_a + n²J_b |
| E16 | Quadrilátero articulado | 3 hinges + `<connect>` no pino do balancim; elos montados consistentes em `qpos0` (`euler` de cada elo); manivela por `<velocity>` | o compilador assume o laço fechado em `qpos0`; hinge Y positivo leva +X a −Z; a solução analítica tem 2 ramos: use o da montagem inicial |
| E17 | Torre/pilha de blocos | boxes com `freejoint` (folga 0.2 mm); `cone`, `impratio`, `solver`, `iterations`; oficial `arch/*` | PGS com poucas iterações colapsa; contato mole desloca o limiar de tombamento; empilhamento perfeito é adversarial (receita dos arcos oficiais: `integrator="discrete"`, `cone="elliptic"`, `impratio` 10–100, `solref="0.005 1..2"`, `noslip_iterations` 1–2, dt 6–8 ms) |

| # | Grandeza | Analítico | Medido ✔ | Tol. sugerida |
|---|---|---|---|---|
| E1 | t de impacto (esfera, h=0.9 m) | 0.428353 − dt/2 s | 0.427353 s (−dt/2 exato) | ±0.2·dt |
| E2 | e (esfera, k=2500; c = 0/5/10/20/50) | 1 / 0.854 / 0.729 / 0.527 / 0.163 | 1.000 / 0.853 / 0.731 / 0.546 / 0.238; `-1000 0`: picos 0.999–1.000 m (12 saltos); `0.02 0.5/0.2/0.1`: 0.250 / 0.524 / 0.716 | ±0.02 (ζ ≤ 0.1); fórmula subestima e p/ ζ ≥ 0.2 |
| E3 | a e distância (v0 = 2 m/s) | μ·g; v0²/(2μg) | μ=0.5: 4.895 (4.905), 0.4061 m (0.4077); μ=0.3: 2.947 (2.943); chão 1.0 + bloco 0.5: 9.596 (9.81 = μ_máx·g) | ±3 % |
| E4 | θ crítico e a (μ=0.5) | atan μ = 26.57°; g(sinθ − μcosθ) = 1.6088 em 35° | elliptic: v(2 s) 26° 0.0016, 27° 0.174 m/s; a = 1.6099; pyramidal alinhado 1.6113; **pyramidal a 45°: limiar 19–20° (atan(μ/√2) = 19.47°), a = 2.765 (+72 %)** | ±1° ; a ±1 % |
| E5 | a (θ=20°) | g·sinθ/(1+k): esfera 2.3966; cil. 2.2368; oco 1.6776 | 2.3942 / 2.2354 / 1.6760 (−0.10 / −0.07 / −0.10 %); `condim=6`: rolling 1e-4 → −0.08 %, 2e-3 → −4.3 %; μ=0.05 < μ_min=0.104: 2.894 | ±0.5 % |
| E6 | T (exp. 02 — removido em 2026-10-08) | T0·(2/π)·K(sin²(θ0/2)) | θ0=5°, 2 ms: −0.0002 % (RK4 0.0000 %), deriva E +0.0024 % (RK4 ≈ 0); θ0=150°, 50 ms: Euler +0.111 % (E +0.28 %), RK4 −0.013 % (−0.011 %) | 0.5 % (`--tol`) |
| E7 | θ1(t) vs scipy; λ | Lagrange (L1=1, L2=0.8, m=1/0.5; 120°, −10°) | RK4 1 ms: \|Δθ1\| 1.5e-10 (1 s) → 1.7e-6 (6 s); > 1e-3 só em 9.56 s; λ ≈ 1.17 s⁻¹; máx\|ΔE\| (5 ms): Euler 1.75 J, RK4 6.9e-4 J | \|Δθ\|<1e-3 até t_div |
| E8 | ω_d, T_d, ζ (m=2, k=800, c=8) | ω_n=√(k/m)=20; ζ=c/(2√(km))=0.1; ω_d=ω_n√(1−ζ²)=19.8997 → T_d=0.31574 s | Euler 2 ms: +0.184 %, −0.21 %; RK4: 0.000 %; Euler 10 ms: +0.83 %, −1.15 %; E0 = ½kx0² = 4.000 J | 0.3 % (Euler 2 ms) |
| E9 | v_t, v(t), alcance (r=0.05, m=0.1, ρ=1.2) | √(m g/k); v_t·tanh(g t/v_t) | caixa: k = 0.0036 → 16.5076 (16.5076), erro de v(t) ≤ 0.029 %; elipsoide Cb=0.5: 14.4283 (14.4283), Cb=0.235: 21.0452 (21.0458); alcance 30 m/s, 45°: 25.761 m (scipy 25.747; sem arrasto 91.74); Stokes (β=1): 1.34376 / 1.04087 exatos | 0.1 % |
| E10 | v1', v2', Δp/p, E/E0 | (m1−m2)/(m1+m2)·v; 2m1/(m1+m2)·v | 1:1 → (−0.0001, 1.0001); 2:1 → (0.33328, 1.33344) vs (0.33333, 1.33333); 1:3 → (−0.50012, 0.50004); E/E0 1.0001–1.0002; Δp/p ≤ 7e-16 (inclusive `0.02 1`: v' = 0.435/0.565, E/E0 = 0.51) | v' 1e-3; Δp/p 1e-12 |
| E11 | deslocamento das 2 esferas finais | 0.080 m (= o deslocamento inicial das 2 esferas soltas) | 0.079 / 0.081 m; esferas do meio ≤ 3.4 mm; E/E0 0.9929 (queda transitória a 0.927) | 5 % |
| E12 | φ̇ (m=1, d=0.1, I3=0.005, I1c=0.004, ω3=200, θ0=30°) | raiz lenta de I1·cosθ·φ̇² − I3·ω3·φ̇ + m·g·d = 0 → 0.99295 (aprox. m g d/(I3 ω3) = 0.981) | RK4 0.5 ms: 0.99212 (−0.084 %), θ = 30.000°; sem φ̇ inicial: 0.99202, θ 30.0–30.8°. Euler/implicitfast/discrete com dt ≥ 0.25 ms (Euler também 0.2 ms): \|ΔE\| > 50 % em 1.7–4.8 s; com 0.1 ms: −0.051 %; `implicit` 0.5 ms: −1.17 % | 0.2 % (RK4) |
| E13 | λ; KE; \|L\|; 1º flip (I = 1,2,3; ω2 = 10) | ω2·√((I3−I2)(I2−I1)/(I1·I3)) = 5.7735 s⁻¹ | 5.7984 (+0.43 %); eixos maior/menor: 1e-6 → ≤ 2e-6; 10 s, ω0 = (0.05, 10, 0.05): KE_f/KE0 Euler 1.112185, implicitfast 0.902806, RK4 1.000000; \|L\| 5.46 / 5.25 / 0.000 %; flip 1.218 / 1.208 / 1.212 s (scipy 1.212) | λ 1 %; RK4 1e-6 |
| E14 | x_pistão (r=0.1, l=0.3, ω=6) | r·cosθ + √(l² − r²·sin²θ) | `connect` padrão: rms 0.39 mm, máx 4.5 mm (t = 0.017 s, partida) e 0.28 mm após 0.5 s; `solref="0.004 1"`: rms 0.0044 mm, máx 0.133 mm (0.004 mm após 0.5 s) | rms < 0.5 mm (padrão) |
| E15 | razão e α_a (J_a=0.01, J_b=0.04, n=2, τ=1) | q_b = −2 q_a; τ/(J_a + n²J_b) = 5.8824 | −2.00000; 5.8824 (0.000 %); fechamento 1.18 mrad (0.10 mrad com `0.004 1`) | α 0.1 % |
| E16 | ângulo do balancim (a=.10, b=.25, c=.20, d=.28) | interseção de círculos | faixa −50.99°…10.00° idêntica; erro 0.0015° (t > 0.5 s), rms 0.063° | 0.01° pós-transiente |
| E17 | s* (n=4, w=0.2; s = sobressalência/crítica) e torre de 10 cubos (10 s) | s* = 1 ((w/2)·H_n = 0.20833 m) | s* = 0.946 (padrão), 0.972 (`solref 0.004 1`); torre: topo desloca 26.84 mm (pyramidal) / 8.62 (elliptic) / 2.25 (elliptic + `impratio 10`); PGS 100 it 26.85; **PGS 10 e 3 it: colapsa**; Newton converge em ≤ 3 it; arcos oficiais 30 s: 3.9 / 1.5 / 0.6 mm | s* ≥ 0.9 |

## 8. Ordem de aprendizado e próximos experimentos
1. Caso-estudo do experimento 01 (§6; o experimento foi removido em 2026-10-08) e E1 → E3/E4 (atrito, cone) → E6/E8 (osciladores e integradores) → E5 → E2/E10 (contato mole, restituição) → E9 (fluido) → E12/E13 (rotação) → E14–E16 (laços fechados) → E17 (redes de contato). Cada um é um `new_experiment.py <nome> --template blank` (E6 parte de `--template pendulum`).
2. **Robôs** (`robots.md`) — templates em `.agents/mujoco-lab-agent-skill/assets/templates/`: `arm/` (3 GDL, servos `<position>` kp=400 kv=40, IK por Jacobiano, alvo mocap; ✔ RMS da ponta 3.96 mm, tol. 10 mm, exit 0) — valide antes o servo como E8 (ω_n, ζ) e use `implicitfast`.
3. **Drones** (`drones.md`): `quadrotor/` (0.892 kg, 4 `<motor>` em sites, controlador geométrico SO(3); empuxo de pairar m·g/4 = 2.19 N por rotor ✔; waypoints ≤ 0.3 cm, RMS 3.0 cm ✔; `--ar --vento` usa o fluido do E9 — confira a convenção de C).
4. **Veículos** (`vehicles.md`): `car/` (modelo de bicicleta: R = L/tanδ = 0.82 m, ψ̇ = v·tanδ/L: 1.705 medido × 1.819 rad/s, Δ 6.3 % ✔; pneus `condim=4`, `cone="elliptic"`, `impratio=10`; use o que o E4 mostrou sobre o cone).
5. Oficiais em `docs/upstream/mujoco/model/` (compilam em 3.15.0 ✔): `slider_crank`, `tendon_arm/arm26` (músculos/tendões), `hammock` (flexcomp), `arch/*`, `sleep/dominos`, `replicate/newton_cradle`, `balloons`, `car`; `cards`, `cube`, `mug` NÃO compilam no espelho (faltam `.obj`/`.png` ✔). Em `model/` não há queda livre, pêndulo nem rampa dedicados (ficha Q15).
6. Candidatos (não testado): ângulo de tombamento de caixa em rampa atan(w/h) vs deslizamento atan μ; autofrequências de osciladores acoplados (autovalores de M⁻¹K); máquina de Atwood com tendão; propagação de dominós (`sleep`).
7. Para aprofundar: `physics-tuning.md` (contato, integradores, estabilidade); `docs/upstream/mujoco/doc/modeling.rst` (§Restitution, Solver parameters), `XMLreference.rst` (asset/mesh, option/flag, equality), `computation/fluid.rst` (modelos de fluido), `computation/index.rst` (estado e atraso após `mj_step`); `docs_search.py "<termo>"`.

## Armadilhas

| Sintoma | Causa | Correção |
|---|---|---|
| Massa 12.581 kg em vez de 20.785 (esfera) | `<geom mesh=…>` sem `type="mesh"` ✔ | declarar `type="mesh"` (ou default class) |
| «at least 4 vertices» / «coplanar vertices» | < 4 vértices ou casco degenerado ✔ | ≥ 4 vértices não coplanares, ou primitivo |
| Massa de malha côncava +40 % a +230 % | `inertia=legacy/convex` em côncava ✔ | `inertia="exact"` (malha fechada, faces orientadas) ou decompor em geoms convexos |
| Massa dobrada | geom visual conta (`inertiagrouprange 0 5`) ✔ | `inertiagrouprange`, `mass="0"` ou `<inertial>` |
| Altura/energia/contatos "1 passo atrás" | após `mj_step`, `xpos`/`xipos`/`geom_xpos`/sensores/`energy` descrevem o estado ANTERIOR (RK4: um estágio intermediário) (doc `computation/index.rst`; ✔ `z_n` exato só em `qpos`) | ler `qpos`, ou `mj_kinematics`/`mj_forward` antes de ler grandezas cartesianas |
| Energia sobe passo a passo | contato mole fora de `data.energy` (§5) | envelope + balanço de trabalho |
| Tombamento só depois de ~7 s | equilíbrio instável exato; ruído numérico | perturbação explícita (tilt 1°) |
| Distância/atrito ≠ μ pedido | μ do contato = MÁX dos dois geoms ✔ | definir μ nos dois (ou `priority`, `<pair>`) |
| Bloco tomba em vez de deslizar | μ ≥ w/h (cubo: μ ≥ 1) ✔ | bloco achatado |
| Limiar de deslize depende da direção (19.5° vs 26.6°; a +72 %) | cone `pyramidal` anisotrópico ✔ | `cone="elliptic"` (+ `impratio` 10 reduz creep) |
| Energia explode / peça ejetada no contato | `timeconst < 2·dt` sem `refsafe`, ou `dt/(timeconst·dampratio) ≥ 2` ✔ (Euler/implicitfast: `0.02 0.05` → 5680 J contra E0 = 227 J; `0.001 1` sem `refsafe` → 7946 J) | manter `timeconst ≥ 2·dt` E `dt/(timeconst·dampratio) < 2`; nunca `refsafe="disable"`; RK4/`discrete` toleram |
| Nunca repousa / vibra | `dampratio` do contato baixo (≲ 0.45 com 4 contatos; ≲ 0.1 numa esfera) ✔ | `dampratio` ≥ 0.5 (ficha Q4: depende de geometria e nº de contatos) |
| Atuador `velocity`/`position` diverge | kv/kp explícitos no Euler (kv=10 a 1 ms diverge) ✔ | `integrator="implicitfast"` ou `armature` |
| Pião/corpo girando rápido explode | ganho de energia giroscópica (Euler/implicitfast/discrete, ω=200 rad/s, dt ≥ 0.2 ms) ✔ | RK4, dt ≤ 0.1 ms ou `implicit` (dissipativo) |
| Arrasto 2× diferente do esperado | convenção: F = ρ·C·A·v² (sem ½); Stokes usa r_eq = 0.7746 R na caixa de inércia ✔ | `Cb = C_D/2`; confira k analítico. **Δ doc**: a doc chama β «viscosidade cinemática», mas f = 6π·r·β·v e o v_t medido pedem a DINÂMICA (Pa·s) |
| Laço fecha mal / forças espúrias | `connect` mole (`0.02 1`) e contato entre peças do mecanismo ✔ | `solref="0.004 1"` no `equality`; `contype="0" conaffinity="0"` |
| Corpo livre não sai do lugar após editar `body_pos` | `qpos0` fixado na compilação ✔ | escrever `data.qpos` |
| Divergência "some" (time volta a 0) | `autoreset` (padrão) zera o estado em NaN/\|x\|>1e10 ✔ | `<flag autoreset="disable"/>` (`mjDSBL_AUTORESET`) e testar NaN/\|ΔE\| |
| Torre cai com PGS | PGS com ≤ 10 iterações ✔ | `solver="Newton"` (converge em ≤ 3) ou PGS ≥ 100 |
| Trajetória caótica "não bate" com a referência | divergência exponencial (λ ≈ 1.2 s⁻¹ no E7) | comparar só até t_div; usar invariantes (energia, momento) |
| `inspect_model.py` falha com `No module named 'numpy'` | `python3` do sistema | `.venv/bin/python` ou `uv run python` |
