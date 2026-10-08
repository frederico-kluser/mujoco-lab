# Física do MuJoCo 3.15 — integradores, solvers, contato, estabilidade e desempenho
Integradores, solvers, parâmetros de contato (`solref`/`solimp`/`margin`/`gap`/`condim`/`friction`/`cone`), filtros de colisão, diagnóstico de instabilidade e desempenho em CPU.
> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: fichas `pesquisas/conhecimento/{Q3,Q4,Q14}.md` (citadas «Q3»…); `docs/upstream/mujoco/doc/{computation/index.rst,modeling.rst,XMLreference.rst,overview.rst,programming/simulation.rst}`; `experiments/01_triangulo_invertido/README.md`; `assets/templates/pendulum/README.md`; testes próprios com `.venv/bin/python`.

## Quando ler este arquivo
- Escolher/ajustar `integrator`, `solver`, `timestep`, `cone`, `iterations`; conferir os valores por omissão de `model.opt.*`.
- Modelar/depurar contato: penetração, ressalto, deslize, atrito torsional/rolamento, filtros de colisão, mistura de parâmetros entre geoms.
- Diagnosticar «explodiu», `BADQACC`, tremor, peça que atravessa, é ejetada ou não repousa; medir tempo/energia; escalar em CPU (threads, `rollout`).
- Conferir uma afirmação do relatório do usuário (§2.1–§2.4): seção 6 deste arquivo.

Aprofundar (docs locais): `docs/upstream/mujoco/doc/computation/index.rst` (`geIntegrators`, `soAlgorithms`, `soParameters`, `coMarginGap`, `coCondim`, «Collision detection»), `modeling.rst` (`CSolver`, `CContact`, `CAlgorithms`, `CPerformance`, `CSlippage`), `XMLreference.rst` (`option` l.315, `option/flag` l.519, `body/geom` `contype`…`gap` l.2659–2826, `contact/pair` l.4246), `overview.rst#Divergence`, `programming/simulation.rst` (`siMultithread`, `siDiagnostics`), `python.rst` (rollout). Busca: `docs_search.py --attr option.integrator`, `--changelog implicitfast`. Exemplos: `assets/templates/pendulum/` (integradores), `experiments/01_triangulo_invertido/` (dampratio/repouso). Nesta pasta: `relatorio-auditoria.md` (auditoria completa do relatório), `drones.md` (fluido/hélices), `vehicles.md` (pneus, condim 4/6), `mjcf-cheatsheet.md`, `python-api.md`.

Marcadores: ✔ = testado (executado com `.venv/bin/python`) · ⚠ armadilha · Δ doc (a doc diverge do medido) · «Q3/Q4/Q14» = valor da ficha, sem reteste.

## 1. Integradores (`<option integrator>` · `model.opt.integrator`)
| `integrator` (enum) | O que faz | Custo¹ | Quando usar | Limitações / estabilidade |
|---|---|---|---|---|
| `Euler` (`mjINT_EULER`=0) — **padrão ao compilar** | Semi-implícito (v⁺=v+h·a; q⁺=q+h·v⁺); só o *joint damping* é implícito (D diagonal, `qH`, flag `eulerdamp`) | 1,00× | Só por compatibilidade com modelos antigos | Viscosidade/arrasto, damping de tendão, `kv` de atuador e **toda rigidez de posição** ficam explícitos; ganha energia em tombo |
| `implicitfast` (3, desde 2.3.3) — **recomendado** | Implícito em velocidade; D sem as derivadas de Coriolis/centrípeta, simetrizada (Cholesky); corpo livre isolado recebe o termo giroscópico (3.11) | 1,09× | **A maioria dos modelos** (doc: «strict improvement» sobre o Euler) | Rigidez de posição (`stiffness`, `kp`) segue explícita (diverge com ω·h>2, como o Euler); perde energia em tombo; cadeia girando rápido ganha energia |
| `implicit` (2, desde 2.2.0) | Idem + derivadas de Coriolis/centrípeta (D assimétrica, LU `qLU`; esparsidade de M: sem damping de tendão entre ramos) | 1,93× | Rotação **acoplada** rápida (pêndulos multi-elo) | **Não é incondicionalmente estável** (mola rígida diverge com h>2/ω); ignora derivadas de restrição |
| `RK4` (1) | Runge-Kutta 4ª ordem, passo fixo: dinâmica+colisão+solver 4×/passo | 3,42× | Sistemas **conservativos** sem contato nem servo rígido; tombo de longo prazo | Instável com forças de velocidade fortes; sem ganho em contato; `mj_step1/2` vira Euler; sem `mjd_transitionFD`/`mjd_inverseFD` (FatalError) nem *sleeping* |
| `discrete` (4, **3.13.0**, «sob desenvolvimento ativo») | Restrições + atualização implícita juntas, na métrica M̂=M+hD+h²K; **único implícito em posição**; `qacc`=(v⁺−v)/h | 1,06× | Mola/servo de posição rígido ou damping forte **com contato**; linhas `solref` estáveis em qualquer h | Um pouco mais amortecido que `implicitfast`; com PGS, tendão/atuador ficam explícitos; sem derivadas de Coriolis; *sleep* exige `island`; flex elástico **exige** `discrete` |

¹ vs Euler no humanoide (nv=27; Q3: Euler 24,0 µs/passo). ✔ re-medido: implicitfast 0,96–1,13×, discrete 1,09–1,23×, implicit 1,7–2,0×, RK4 3,5–3,8× (±10% com a carga da máquina).

**Recomendação oficial** (`computation/index.rst`, «Choosing timestep and integrator»): `implicitfast` («recommended integrator for most models»); `Euler` só por compatibilidade; `implicit` p/ giroscopia acoplada; `discrete` p/ molas/servos rígidos + contato; `RK4` p/ sistemas (quase) conservativos. O `timestep` (0,002 s) é «perhaps the single most important parameter»: h menor melhora todos; o padrão foi escolhido por estabilidade, não por eficiência. **Fixe `integrator` no XML**: o padrão é Euler, mas o changelog 2.3.3 promete `implicitfast` como padrão «in a future version». Adoção ✔: Menagerie 58/61 XMLs que fixam integrador usam `implicitfast` (Euler 2, RK4 1); Playground 9 Euler / 7 `implicitfast`. Em aberto (Q3, drones): o Crazyflie 2 da Menagerie usa `RK4` com `density`/`viscosity` (✔ `docs/upstream/mujoco_menagerie/bitcraze_crazyflie_2/cf2.xml`), contra a doc (`implicit`/`implicitfast` p/ forças de fluido) — teste os dois no seu drone. **Correção ao relatório do usuário** (§2.2, seção 6): Euler não é o recomendado, RK4 não preserva (h\|ω\|)² e o implícito não é incondicionalmente estável.

**Estabilidade medida** ✔ (linhas 1–3: maior h estável por bisseção, até 2 s; linhas 4–5: h=2 ms):

| teste | Euler | RK4 | implicit | implicitfast | discrete |
|---|---|---|---|---|---|
| mola `stiffness`=1e4, m=1 kg (ω=100 rad/s) | 20,0 ms (=2/ω) | 28,3 ms (≈2,83/ω) | 20,0 ms | 20,0 ms | sem limite (ω·h=200) |
| damping de junta 1e3 N·s/m, m=1 kg | sem limite; 2,0 ms com `eulerdamp` off | 2,8 ms | sem limite | sem limite | sem limite |
| viscosidade do meio 1000 Pa·s (esfera r=5 cm, 1 kg) | 2,8 ms | 3,8 ms | sem limite | sem limite | sem limite |
| pêndulo L=1 m, h=2 ms, 20 s: máx\|ΔE\| | 2,7e-2 J | 1,0e-10 J | 2,7e-2 | 2,7e-2 | 2,7e-2 |
| corpo livre em tombo (I=diag(1,2,3), ω0≈10 rad/s), 10 s: KE final/inicial | 1,112 | 1,000000 | 0,903 | 0,903 | 0,903 |

Template `pendulum` ✔ (θ0=5°, h=2 ms): erro de período ≤0,0002% em todos; deriva de energia RK4 ≈0 vs +0,0024% nos demais; com θ0=150°, h=50 ms: RK4 −0,013% (período)/−0,011% (energia) vs +0,11%/+0,28%. Moral: sem contato, RK4 conserva muito melhor; com contato/atuador rígido, `implicitfast`.

```python
import mujoco
XML = """<mujoco><option gravity="0 0 0"><flag autoreset="disable"/></option><worldbody><body>
<joint type="slide" axis="1 0 0" stiffness="1e4"/><inertial pos="0 0 0" mass="1" diaginertia="1 1 1"/></body></worldbody></mujoco>"""   # ω = 100 rad/s → 2/ω = 20 ms
def amplitude(integ, h, nstep=300):                       # máx|q|/q0 em nstep passos, ou DIVERGE
    m = mujoco.MjModel.from_xml_string(XML); m.opt.integrator = getattr(mujoco.mjtIntegrator, "mjINT_" + integ); m.opt.timestep = h
    d = mujoco.MjData(m); d.qpos[0] = 0.1; pico = 0.0
    for _ in range(nstep):
        mujoco.mj_step(m, d); pico = max(pico, abs(d.qpos[0]))
        if d.warning[mujoco.mjtWarning.mjWARN_BADQACC].number or pico > 100: return "DIVERGE"
    return f"{pico / 0.1:.2f}"
for h in (0.019, 0.021, 0.027, 0.029, 1.0):
    print(f"h={h:5.3f}", {i: amplitude(i, h) for i in ("EULER", "RK4", "IMPLICIT", "IMPLICITFAST", "DISCRETE")})
```

⚠ armadilha: `data.energy` lido logo após `mj_step` é a do estado no **início** do passo (RK4: de um estágio intermediário; erro 1,2e-7 J em vez de 1,0e-10 J) ✔ — chame `mj_forward(m, d)` antes de ler. Enumeradores XML são sensíveis a maiúsculas (`rk4` → «invalid keyword»; use `RK4`, `Euler`, `implicitfast`, `Newton`).

## 2. Solvers e opções (`model.opt.*`)
Valores por omissão ✔ (compilar `<mujoco/>`; bloco abaixo):

| opção | padrão | opção | padrão |
|---|---|---|---|
| `integrator` · `solver` | `Euler` · `Newton` | `noslip_iterations` · `noslip_tolerance` | 0 · 1e-6 |
| `cone` · `impratio` | `pyramidal` · 1 | `ccd_iterations` · `ccd_tolerance` | 35 · 1e-6 |
| `jacobian` | `auto` (denso se nv<60, senão esparso) | `gravity` · `wind` · `magnetic` | (0,0,−9,81) · 0 · (0,−0,5,0) |
| `timestep` | 0,002 s | `density` · `viscosity` | 0 · 0 (sem forças de fluido) |
| `iterations` · `ls_iterations` | 100 · 50 | flags ligadas (principais) | `refsafe` `filterparent` `nativeccd` `multiccd` `island` `eulerdamp` `autoreset` `warmstart` |
| `tolerance` · `ls_tolerance` | 1e-8 · 0,01 | flags desligadas | `energy` `fwdinv` `invdiscrete` `override` `sleep` `diagexact` |

Δ doc: a XMLreference diz «denso até 60»; medido: `mj_isSparse` = 0 em nv=59 e 1 em nv=60.

```python
import mujoco
o = mujoco.MjModel.from_xml_string("<mujoco/>").opt                       # tudo por omissão
print(o.timestep, o.iterations, o.ls_iterations, o.tolerance, o.ls_tolerance, o.impratio,
      mujoco.mjtIntegrator(o.integrator).name, mujoco.mjtSolver(o.solver).name, mujoco.mjtCone(o.cone).name, mujoco.mjtJacobian(o.jacobian).name)
# → 0.002 100 50 1e-08 0.01 1.0 mjINT_EULER mjSOL_NEWTON mjCONE_PYRAMIDAL mjJAC_AUTO
m = mujoco.MjModel.from_xml_string('<mujoco><option integrator="implicitfast" cone="elliptic" impratio="10" tolerance="1e-10"/></mujoco>')
m.opt.integrator = mujoco.mjtIntegrator.mjINT_DISCRETE                     # troca em runtime: a opção vive no MjModel (compartilhado entre MjData)
```

| Solver | Algoritmo | Quando usar | Limitações |
|---|---|---|---|
| `Newton` (2, **padrão**) | Primal, Newton exato (Hessiano Cholesky); ~5 iterações, raramente >20 | **Maioria**; `tolerance` agressiva (~1e-10) | Lento só com cone elíptico + muitos contatos deslizando (atualiza o Hessiano) ou muito fill-in → `CG` |
| `CG` (1) | Primal, gradiente conjugado (Hager-Zhang), sem setup | Modelos grandes em que o Newton desacelera | Convergência só linear: precisa de mais iterações |
| `PGS` (0) | Dual, Gauss-Seidel projetado (antigo padrão; Nesterov desde 3.11) | nv > nefc (raro); solução imprecisa tolerável | Sublinear; lento com razões de massa grandes; sequencial (quebra simetria); mais memória |
| NoSlip | Pós-processamento (`noslip_iterations`>0; use 1–3): refaz só o atrito (PGS, R=0) | Deslize lento (abaixo) | Não resolve um problema bem-definido; custo; inversa mal definida; pode instabilizar |

- `iterations`: sobe com restrições acopladas. ✔ Pilha de 10 cubos (3 s): estável com PGS ≥10, CG ≥10 (≥3 sob Euler), Newton ≥3 (≥1 sob Euler) — o limiar muda com o integrador; não confie em `iterations=1` (Playground usa 1–10).
- `tolerance`: PGS = melhora do custo; CG/Newton = menor entre melhora do custo e norma do gradiente (Newton: também o decremento de Newton); 0 desliga a parada antecipada; com warmstart o solver pode parar com 0 iterações (`solver_niter`).
- `ls_iterations`/`ls_tolerance`: limitam a busca linear (≤ `iterations`×`ls_iterations` por solve); efeito quantitativo **não documentado** (Playground: 4–10). Relato não confirmado (issue #3628): `ls_iterations=20` + elíptico + `impratio=10` deixou o Newton sem convergir, sem aviso — confira `solver_niter`/`fwdinv` (seção 4).
- `jacobian`: dense e sparse dão o mesmo resultado por caminhos distintos; teste os dois (✔ humanoid100, nv=627: dense ≈3–4× mais lento que sparse/auto).
- `cone`: `pyramidal` (padrão; 4 linhas por contato condim 3; às vezes mais rápido/robusto) é **anisotrópico** — μ efetivo cai na diagonal (✔ μ=0,5, rampa com a descida girada 45° no plano XY do mundo: desliza a 20° — previsto atan(μ/√2)=19,5° — em vez de só >26,6°=atan μ; com a descida a 0°, ou em `elliptic`, não); `elliptic` (3 linhas) é isotrópico e mais fiel; `impratio`, `solreffriction` e NoSlip só funcionam bem nele. A doc recomenda experimentar o elíptico; ✔ Menagerie: 40 de 42 XMLs que fixam `cone` usam `elliptic`, com `impratio`=10 (23 XMLs) ou 100 (16; ex.: anymal, spot, leap_hand) e `noslip_iterations` 1–5 em 7.
- `impratio` divide o regularizador R das linhas de atrito (atrito «mais duro» sem subir μ). ✔ Creep em rampa (caixa 1 kg, 30°, μ=1, Newton, 3 s), µm/s:

| cone | impratio 1 | 10 | 100 | com `noslip_iterations=3` (10 / 100) |
|---|---|---|---|---|
| `pyramidal` | 3349,5 | 340,9 | 34,1 | 445 / 85 (não ajuda) |
| `elliptic` | 1603,8 | 160,3 | 16,0 | 0,72 / 0,07 |

```python
import mujoco, numpy as np
XML = """<mujoco><option cone="{cone}" impratio="{imp}" noslip_iterations="{ns}"/><worldbody>
<geom type="plane" euler="0 30 0" size="2 2 .1" friction="1 0.005 0.0001"/>
<body pos="0.04995 0 0.086533" euler="0 30 0"><freejoint/><geom type="box" size=".1 .1 .1" mass="1" friction="1 0.005 0.0001"/></body></worldbody></mujoco>"""
def creep(cone, imp, ns, T=3.0):         # |v| em µm/s de uma caixa em rampa de 30° com μ=1 (tan 30° = 0,58 < μ: deveria ficar parada)
    m = mujoco.MjModel.from_xml_string(XML.format(cone=cone, imp=imp, ns=ns)); d = mujoco.MjData(m)
    mujoco.mj_step(m, d, int(T / m.opt.timestep)); return float(1e6 * np.linalg.norm(d.qvel[:3]))
for cone in ("pyramidal", "elliptic"):
    print(f"{cone:9s} impratio 1/10/100:", [round(creep(cone, i, 0), 1) for i in (1, 10, 100)], "| com noslip_iterations=3 (10/100):", [round(creep(cone, i, 3), 2) for i in (10, 100)])
```

## 3. Modelo de contato
**Soft constraint** resolvido por otimização convexa (QP no cone piramidal; programa cônico no elíptico), sem complementaridade estrita (força e velocidade normais podem ser ambas ≠0). Por linha escalar (aproximado: diagonal de A em `qpos0`): `a_c + d·(b·v + k·r) = (1−d)·a_u`, `a_ref = −b·v − k·r`, `R = (1−d)/d·Â_ii`. `r = dist − margin` (≤0 se ativo; **0** nas linhas de atrito elípticas e no `frictionloss` ⇒ k=0, 1ª ordem). O motor guarda `efc_KBIP=[K,B,I,imp']` com `k=K·I` (K **sem** o fator d(r)): `a_ref = −B·v − K·I·r`. `b` e `k` não são atributos: derivam de `solref`/`solimp`.

**`solref`** (2 números; padrão `0.02 1`): o sinal escolhe o formato.

| formato | números | b | k | penetração em repouso (d constante) |
|---|---|---|---|---|
| padrão (ambos >0) | (timeconst s, dampratio) | 2/(d_w·timeconst) | d(r)/(d_w²·timeconst²·dampratio²) | a_u(1−d)·timeconst²·dampratio² ✔ |
| direto (≤0) | (−stiffness, −damping) | damping/d_w | stiffness·d(r)/d_w² | a_u(1−d)/stiffness ✔ |

- timeconst = 1/(ζ·ω_n) (maior = mais macio); dampratio=1 crítico (sem ressalto), <1 quica, >1 sobreamortecido (=1 ⇔ damping=2√stiffness). **timeconst ≥ 2·timestep** (flag `refsafe`, seção 4).
- Direto: números independentes; `damping=0` ⇒ restituição perfeita (doc: recomendado p/ identificação de sistemas).
- Linhas de atrito elípticas (r≡0): só conta o timeconst (padrão) ou o damping (direto); `<pair solreffriction>` `0 0` = usar `solref`.

**`solimp`** (5 números; padrão `0.9 0.95 0.001 0.5 2`) = (d₀, d_w, width, midpoint, power): impedância d(r)∈(0,1), a «capacidade de gerar força». d₀ vale em r=0 e d_w em \|r\|≥width (m ou rad), com sigmoide: x=min(\|r\|/width,1); y = x^p/mid^(p−1) se x≤mid, senão 1−(1−x)^p/(1−mid)^(p−1) (p=1 ⇒ reta); d = d₀+y·(d_w−d₀). ✔ Fórmula exata (erro 0 em `efc_KBIP`): d₀ e d_w são clampados **individualmente** a [mjMINIMP, mjMAXIMP]=[1e-4, 0,9999] (d₀=0 ⇒ I(0)=1e-4; a doc recomenda d₀=0 para dinâmica diferenciável); d₀ pode exceder d_w.

```python
import mujoco, numpy as np
XML = """<mujoco><worldbody><geom type="plane" size="1 1 .1" solref="{sr}" solimp="{si}"/><body pos="0 0 0.1"><freejoint/>
<geom type="sphere" size="0.1" mass="4.19" solref="{sr}" solimp="{si}"/></body></worldbody></mujoco>"""     # mesmos solref/solimp nos 2 geoms: sem mistura
def d_of_r(r, si):                  # impedância d(r): sigmoide d0 (r=0) → dw (|r| ≥ width); d0 e dw clampados a [1e-4, 0.9999]
    d0, dw = np.clip(si[:2], 1e-4, 0.9999); w, mid, p = si[2:]; x = min(abs(r) / w, 1)
    y = x if p == 1 else (x**p / mid**(p - 1) if x <= mid else 1 - (1 - x)**p / (1 - mid)**(p - 1))
    return d0 + y * (dw - d0)
for sr, si, pen in (("0.02 1", (0.9, 0.95, 0.001, 0.5, 2), 5e-4), ("0.04 0.5", (0.5, 0.99, 0.01, 0.3, 4), 4e-3), ("-1000 -10", (0.9, 0.95, 0.001, 0.5, 2), 5e-4)):
    m = mujoco.MjModel.from_xml_string(XML.format(sr=sr, si=" ".join(map(str, si)))); d = mujoco.MjData(m)
    d.qpos[2] = 0.1 - pen; mujoco.mj_forward(m, d)           # esfera penetrando `pen` no plano, em repouso
    K, B, I, _ = d.efc_KBIP[0]; r = d.efc_pos[0] - d.efc_margin[0]; a, b = map(float, sr.split()); dw = np.clip(si[1], 1e-4, 0.9999)
    k, bb = (d_of_r(r, si) / (dw**2 * a**2 * b**2), 2 / (dw * a)) if a > 0 else (-a * d_of_r(r, si) / dw**2, -b / dw)   # a>0: (timeconst, dampratio); a≤0: (−stiffness, −damping)
    assert np.allclose([K * I, B, I], [k, bb, d_of_r(r, si)]), (K * I, B, I, k, bb)   # o motor guarda K SEM o fator d(r): k = K·I
    print(f"solref=({sr:9s}) r={r:+.4f}  K·I={K * I:9.2f}  B={B:7.2f}  I={I:.4f}  a_ref={d.efc_aref[0]:.4f} = -B·v - K·I·r")
```

Os mesmos `solref`/`solimp` existem em `joint` (`solreflimit`/`solimplimit`, `solreffriction`/`solimpfriction`), `tendon`, `equality` e `<pair>`. `<option override o_margin o_solref o_solimp o_friction>` (+flag `override`) os sobrescreve nos contatos.

**Efeito dos botões** (✔ medido; esfera de 4,19 kg sobre plano, padrão salvo indicação):

| Quero… | Mexa em | Efeito medido |
|---|---|---|
| menos penetração em repouso | ↑d (`solimp` d₀=d_w) ou ↓timeconst (≥2·dt) | r = a_u(1−d)·timeconst²·dampratio²: d=0,5/0,9/0,99 ⇒ 1,96/0,39/0,039 mm; timeconst 0,02→0,04 ⇒ ×4 (0,39→1,57 mm) |
| sem ressalto | `dampratio`=1 (padrão) | e=0; penetração máx. 19,9 mm no impacto a 2,8 m/s (queda de 0,4 m) |
| ressalto/restituição | `dampratio`<1 ou solref direto `(−k, −c)` | timeconst 0,02: dampratio 0,5/0,2/0,1 ⇒ e=0,26/0,59/0,73; `-1000 0` ⇒ e=1,004 (penetração máx. 89 mm) |
| repouso sem vibração | `dampratio` ≥0,5 | prisma de 4 contatos: ≤0,45 não repousa em 8 s, ≥0,5 repousa em ~0,8 s; esfera: 0,2 repousa, 0,1 vibra >30 s |
| contato antes do toque | `margin`>0 (força a dist ≤ margin); `gap`>0 só detecta (inativo; p/ adesão) | regimes abaixo |
| dinâmica diferenciável | `solimp` d₀=0 (cuidado com a mistura priority/solmix) | doc (`modeling.rst#solimp0`) |

**Mistura entre dois geoms** (contato dinâmico; `priority` padrão 0, `solmix` padrão 1):

| parâmetro | regra | ✔ exemplo |
|---|---|---|
| `condim` | maior `priority` vence; empate ⇒ **máximo** (Δ doc: a XMLreference omite a priority) | piso condim 1 + esfera 4 ⇒ dim=4; piso `priority=1` ⇒ dim=1 |
| `friction` | priority; empate ⇒ máximo elemento a elemento; 3 coef. do geom → 5 do contato [μ,μ,tors,roll,roll] | (0,3; 0,01; 0,001) + (0,8; 0,002; 0,0005) ⇒ [0,8; 0,8; 0,01; 0,001; 0,001] |
| `solref`, `solimp` | priority; empate ⇒ média ponderada por `solmix` (w₁=solmix₁/(solmix₁+solmix₂)); solref **direto** (≤0) em qualquer geom ⇒ mínimo elemento a elemento, ignora solmix | `0.04 0.5` + piso `0.02 1` ⇒ `0.03 0.75`; direto `-1000 -10` vs `0.04 0.5` ⇒ `-1000 -10` |
| `margin`, `gap` | **soma** dos dois geoms (priority ignorada) | — |
| `<pair>` | define tudo (condim, friction[5], solref, solreffriction, solimp, margin, gap) e ignora os geoms; só ele permite atrito anisotrópico | friction padrão `1 1 0.005 0.0001 0.0001` |

⚠ armadilha: mudar `solref` só no objeto não basta — o piso (padrão `0.02 1`) entra na média. Defina nos dois geoms, use `priority` ou `<pair>`.

```python
import mujoco, numpy as np
XML = """<mujoco><worldbody><geom name="chao" type="plane" size="1 1 .1" friction="0.3 0.01 0.001" condim="1" solref="0.02 1"/>
<body pos="0 0 0.0995"><freejoint/><geom name="esf" type="sphere" size="0.1" mass="1" friction="0.8 0.002 0.0005" condim="4" solref="0.04 0.5"/></body></worldbody></mujoco>"""
def contatos(m, d):                  # parâmetros EFETIVOS (já misturados) e força normal de cada contato
    f = np.zeros(6)
    for i, c in enumerate(d.contact):
        mujoco.mj_contactForce(m, d, i, f)                  # força no referencial do contato; f[0] = normal
        print(f"{m.geom(c.geom1).name}-{m.geom(c.geom2).name} dist={c.dist:+.4f} dim={c.dim} efc_address={c.efc_address} "
              f"Fn={f[0]:.2f} atrito={c.friction} solref={c.solref}")
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m); mujoco.mj_step(m, d, 500); contatos(m, d)
```

**`margin` e `gap`** (redesenhados na **3.9.0**; somam-se entre os geoms desde a 3.5.0, antes era o máximo; `margin` negativo é permitido com margin+gap ≥ 0). ✔ Testado (dist 0,005: margin 0,01 ⇒ ativo; gap 0,01 ⇒ inativo; dist 0,015 ⇒ nada).

| regime | condição (dist entre superfícies) | efeito |
|---|---|---|
| sem contato | dist > margin+gap | nada |
| inativo | margin < dist ≤ margin+gap | está em `data.contact` com `efc_address=-1`, sem força (útil p/ `adhesion`) |
| ativo | dist ≤ margin | força; impedância avaliada em r = dist − margin (≤0) |

⚠ Antes da 3.9.0 o `gap` era *subtraído* (força só se dist < margin−gap); migração (changelog 3.9.0): margin_novo = margin_antigo − gap_antigo, gap inalterado (`margin="0.1" gap="0.1"` ⇒ `margin="0" gap="0.1"`); com o padrão 0/0 nada muda.

**`condim` e `friction`**: só 1/3/4/6 são válidos (0, 2, 5, 7 ⇒ «invalid condim in geom»); padrão 3.

| condim | transmite | linhas piramidal / elíptico ✔ | uso |
|---|---|---|---|
| 1 | só normal (sem atrito) | 1 / 1 | partículas; com `priority` alta evita «grudar» |
| 3 | + atrito tangencial (2 eixos) | 4 / 3 | contato comum |
| 4 | + torsional (giro em torno da normal) | 6 / 4 | dedos moles, pneu parado, preensão estável |
| 6 | + rolamento (2 eixos) | 10 / 6 | esfera/cilindro/pneu que não deve rolar para sempre |

`friction` por geom = 3 números [deslizamento, torsional, rolamento], padrão `1 0.005 0.0001`; torsional e rolamento têm unidades de **comprimento** (≈ diâmetro do patch / profundidade da deformação). ✔ Esfera 1 s: giro ωz0=10 rad/s em torno da normal ⇒ condim 3 mantém 10,0, condim 4 (torsional 0,005) ⇒ 1,64 rad/s; rolamento puro vx0=1 m/s ⇒ condim 3 0,9995, condim 6 (rolling 0,002) ⇒ 0,926 m/s (a ficha Q4 mediu 0,21 rad/s e 0,86 m/s: qualitativo igual). ✔ Coeficiente <`mjMINMU`=1e-5 é clampado a 1e-5: `friction="0 0 0"` mantém condim 3 e 4 linhas; para atrito nulo use `condim=1`.

**Filtragem** (geração: pares de corpos por *broad-phase* + `<contact><pair geom1 geom2>`; depois filtros):
- tipos sem colisor (plane×plane) e esfera envolvente (com margin); mesmo corpo **nunca** colide; pai-filho não colide (flag `filterparent`; exceto pai = world; corpos soldados contam como um); pares sem nenhum corpo móvel (estáticos/mocap) são pulados.
- `contype`/`conaffinity` (máscaras de 32 bits, padrão 1/1): colide se `(contype1 & conaffinity2) || (contype2 & conaffinity1)` ≠ 0 ✔ ((1,0)×(1,0) ⇒ não; (1,0)×(0,1) ⇒ sim; (3,0)×(0,2) ⇒ sim; (2,2)×(1,1) ⇒ não).
- `<exclude body1 body2>` remove todos os pares entre dois corpos. `<pair>` contorna `contype`/`conaffinity`, pai-filho e mesmo corpo (✔ ncon 0→1) e **não é anulado** por `<exclude>` do mesmo par.
- ⚠ Comentar o `freejoint` da base a torna estática ⇒ o filtro pai-filho deixa de valer e surgem colisões novas (overview.rst, «Surprising Collisions»).

**Colisões suportadas** ✔ (`mj_maxContact`, `nativeccd`+`multiccd` ligados): plane×{sphere 1, capsule 2, ellipsoid 1, cylinder/box/mesh 4}; hfield×{sphere, capsule, ellipsoid, cylinder, box, mesh} até `mjMAXCONPAIR`=50; **plane×plane, plane×hfield, hfield×hfield = 0 (não suportados)**; sphere×qualquer 1; capsule×capsule 2; cylinder×cylinder 4; box×box 8; mesh×mesh 4. Δ doc: tabela da doc dá capsule×box=2, `mj_maxContact` devolve 4 (nunca >2 observado, Q4).
- **Malhas colidem como casco convexo** (qhull), mesmo não convexas (renderizadas como são; Q4: esfera sobre o entalhe de uma malha em L repousou no casco). Côncavo ⇒ decomponha em geoms convexos no mesmo corpo (ex.: CoACD); hfield = prismas triangulares. Mantenha `nativeccd` (GJK/EPA) e `multiccd` (várias pontas p/ face-face) ligados.

## 4. Estabilidade e diagnóstico
`mj_step` checa qpos/qvel no início e qacc após `mj_forward` (`mj_checkPos/Vel/Acc`); NaN/Inf ou \|x\|>`mjMAXVAL`=1e10 ⇒ aviso e, com `autoreset` (padrão; flag `autoreset="disable"`, `mjDSBL_AUTORESET`=1<<16), `mj_resetData` (qpos←qpos0, time←0): **o estado divergente se perde** — para depurar, desligue-o. Contadores: `data.warning[i].number` (desde o último reset) e `.lastinfo`; o texto sai só na 1ª ocorrência.

| `mjtWarning` | Significado | `lastinfo` ✔ | Observação |
|---|---|---|---|
| 0 `INERTIA` | inércia (quase) singular (desde 3.14 também em `implicitfast`/Euler+damping/`implicit`) | DOF (Q14) | massa/inércia >0, `armature` |
| 1 `CONTACTFULL` | contatos demais p/ a arena: os excedentes são **descartados** | nº máx. que coube | `<size memory>`; `maxuse_arena` |
| 2 `CNSTRFULL` | restrições demais: **solver desligado no passo** (nefc=0), sim continua | tamanho da arena (bytes) | idem; falta de pilha = FatalError |
| 3 `BADQPOS` · 4 `BADQVEL` · 5 `BADQACC` | NaN/Inf/\|x\|>1e10 (5 = divergência típica) | índice em qpos · qvel · DOF | `dof_jntid[info]` ⇒ junta |
| 6 `BADCTRL` | NaN/Inf em `ctrl`: **não reseta**, o atuador sai 0 | índice em ctrl | validar a política |

```python
import mujoco, numpy as np
XML = """<mujoco><option gravity="0 0 0" timestep="0.021"><flag autoreset="disable" energy="enable"/></option>
<worldbody><body><joint name="mola" type="slide" axis="1 0 0" stiffness="1e4"/><inertial pos="0 0 0" mass="1" diaginertia="1 1 1"/></body></worldbody></mujoco>"""
def primeiro_aviso(m, d, nstep=2000):
    """Passa até o 1º aviso mjtWarning; devolve (passo, aviso, culpado). autoreset desligado preserva o estado divergente em d."""
    antes = d.warning.number.copy()
    for i in range(nstep):
        mujoco.mj_step(m, d)
        novo = np.flatnonzero(d.warning.number > antes)
        if novo.size:
            k = int(novo[0]); info = int(d.warning.lastinfo[k]); alvo = info          # lastinfo: BADQPOS→índice em qpos; BADQVEL/BADQACC/INERTIA→DOF; BADCTRL→índice em ctrl
            if k in (4, 5): alvo = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, m.dof_jntid[info])
            return i + 1, mujoco.mjtWarning(k).name, alvo
m = mujoco.MjModel.from_xml_string(XML); d = mujoco.MjData(m); d.qpos[0] = 0.1      # h = 21 ms > 2/ω = 20 ms
print(primeiro_aviso(m, d), "| time =", round(d.time, 3), "| |qpos| =", f"{abs(d.qpos[0]):.2g}", "| energia (pot, cin) =", d.energy)
```

**Regras de ouro** (✔ = testado aqui):

| Regra | Evidência |
|---|---|
| **h < 2/ω_max** da parte explícita (rigidez de junta/`kp`, ganhos de velocidade sem integrador implícito; RK4 ≈2,83/ω) | ✔ `limite_dt` (bloco abaixo) = limite medido por bisseção (Euler): 1,523 ms; com `armature`=0,05: 4,724 ms |
| **timeconst ≥ 2·timestep**: `refsafe` (padrão) usa max(solref[0], 2·dt) por restrição ativa; `discrete`: substitui linhas com timeconst·dampratio<h pela linha mais rígida de restituição zero | ✔ dt=2 ms, timeconst 0,0005: com `refsafe` B=526 e a esfera repousa; sem ele a esfera é **ejetada sem aviso** (sobe a 5,2 m; com timeconst 1e-4: 302 m) em Euler/`implicitfast`; sob `discrete` fica estável |
| **`armature`>0** estabiliza mesmo pequeno (soma-se a `dof_M0`, baixa ω) | ✔ I=0,0058, dt=10 ms: `kv`=5 diverge ⇒ estável com 0,05; `stiffness`=1e4 diverge ⇒ estável com 0,5 |
| Euler só implicita *joint damping*; ganhos de velocidade/viscosidade ⇒ `implicitfast`/`implicit` | ✔ damping=5: estável (eulerdamp on) / diverge (off); `kv`=5 diverge em Euler, estável em `implicitfast` |
| Rigidez de posição (`stiffness`, `kp`) é explícita até no `implicitfast` ⇒ dt↓, `armature`↑ ou `discrete` | ✔ `kp`=1000, dt=10 ms: diverge em Euler/`implicitfast`; estável com dt=2 ms, armature 0,5 ou `discrete` |
| Razão de massas: sem limite oficial (PGS é lento com razões grandes) | ✔ 2 caixas empilhadas (Newton): razão 1 ⇒ folga −0,2 mm; 100 ⇒ −3,3 mm; ≥1e4 ⇒ a pesada **atravessa a leve sem aviso** |
| Sem sobreposição inicial | ✔ esfera com 5 cm de penetração e timeconst 0,004 é lançada a 6,25 m/s (z=2 m); com 0,02: 0,93 m/s |
| Limites de junta/equalities | evite `range` estreito como igualdade (use `<equality>`); `frictionloss` é restrição, não força |
| Solver mal convergido / escala de restrição imprecisa | compare `solver_niter` com `iterations`; `fwdinv` alto ⇒ considere `<flag diagexact="enable"/>` (inércia anisotrópica, longe de `qpos0`) |

```python
import mujoco, numpy as np
def limite_dt(m):                    # h_max ≈ 2/ω por junta escalar: rigidez de junta explícita; 2·I/c para damping NÃO implícito (RK4: ×1,4)
    for j in np.flatnonzero(np.isin(m.jnt_type, [mujoco.mjtJoint.mjJNT_HINGE.value, mujoco.mjtJoint.mjJNT_SLIDE.value])):
        a = m.jnt_dofadr[j]; I = m.dof_M0[a]; k = m.jnt_stiffness[j]; c = m.dof_damping[a]      # dof_M0 já inclui o armature
        print(f"{m.joint(j).name:8s} 2/ω = {2 / np.sqrt(k / I) * 1e3 if k > 0 else np.inf:8.3f} ms   2I/c = {2 * I / c * 1e3 if c > 0 else np.inf:8.3f} ms")
XML = '<mujoco><worldbody><body><joint name="j" axis="0 1 0" stiffness="1e4" armature="{}"/><inertial pos="0 0 0" mass="1" diaginertia=".0058 .0058 .0058"/></body></worldbody></mujoco>'
for arm in (0, 0.05): limite_dt(mujoco.MjModel.from_xml_string(XML.format(arm)))     # medido (Euler, bisseção): 1,523 ms e 4,724 ms
```

**Checklist de depuração** (Q14 + doc `overview.rst#Divergence`: divergência é «hint that the timestep is too large for the integrator»; se reduzir dt/trocar integrador não resolve, o culpado é outro):
1. Pare no 1º aviso (`primeiro_aviso`, `autoreset` off): `lastinfo` ⇒ DOF ⇒ junta. `inspect_model.py <modelo> --steps 2000` roda um teste de fumaça e sinaliza riscos (✔ `solref` timeconst<2·dt ⇒ `[ALTO]`, exit 1; segundo o docstring, também razão de massas e corpo sem massa).
2. `mujoco.mj_printModel(m, "m.txt")`/`mj_printData(m, d, "d.txt")`; massas/inércias >0; sem penetração inicial (`d.ncon`, `efc_pos`<0 em t=0).
3. Divida o `timestep` por 2 ou troque para `implicitfast`: se a divergência some, era dt × rigidez/ganhos.
4. Confira timeconst ≥ 2·dt, `kp`/`kv`/`damping`; adicione `armature`.
5. Ligue `energy` (instabilidade = energia crescente; sistemas sem contato/atuador/dissipação devem conservá-la) e `fwdinv`; compare `solver_niter` com `iterations`.
6. Perfile (`data.timer`, `testspeed`) **antes** de aumentar dt, trocar `jacobian`/solver ou mexer nas colisões.

```python
import mujoco
m = mujoco.MjModel.from_xml_path("/home/ondokai/Projects/MuJoCo/docs/upstream/mujoco/model/humanoid/humanoid.xml")
m.opt.enableflags |= mujoco.mjtEnableBit.mjENBL_ENERGY | mujoco.mjtEnableBit.mjENBL_FWDINV          # d.energy e d.solver_fwdinv
d = mujoco.MjData(m); mujoco.mj_step(m, d, 2000); mujoco.mj_forward(m, d)                         # mj_forward: energia do estado FINAL
for i in range(mujoco.mjtTimer.mjNTIMER):                                                          # data.timer: segundos no Python (em C exige mjcb_time)
    t = d.timer[i]
    if t.number: print(f"{mujoco.mjtTimer(i).name[8:]:15s}{1e6 * t.duration / t.number:8.2f} µs/chamada")
print(f"ncon={d.ncon} nefc={d.nefc} solver_niter={d.solver_niter[0]} fwdinv={d.solver_fwdinv} E(pot,cin)={d.energy} arena={100 * d.maxuse_arena / d.narena:.2f}%")
```

**Receitas** (sintoma → causa → correção; ✔ = testado):

| Sintoma | Causa provável | Correção |
|---|---|---|
| **Peça não repousa** (vibra em ciclo-limite) | Contato subamortecido: prisma de 4 contatos `dampratio` ≤0,45; esfera ≤0,1 (`models/triangulo_invertido.xml`) | ✔ `dampratio` ≥0,5 (padrão 1; repousa em ~0,8 s). Sozinhos **não** resolvem: `cone=elliptic`, `noslip`, `implicitfast`/`discrete`/`RK4`, dt/2; elíptico+`noslip_iterations=3` resgata só 0,3–0,45 (não ≤0,2) |
| **Trepida** (alta frequência) | Ganhos altos (`kp`, `kv`), damping explícito, contato com timeconst≈2·dt | `armature`, dt↓, `implicitfast` (damping/`kv`), `discrete` (`kp`/`stiffness`); contatos: timeconst ≥2·dt |
| **Atravessa** | (a) razão de massas ≥1e4; (b) impacto rápido em contato macio/geom fino: não há CCD contínuo (não verificado na doc) | (a) mantenha a razão baixa (100 ⇒ −3 mm ✔); solref mais duro ajuda ✔ (timeconst 0,004, dt 1 ms: −210 ⇒ −16 mm), não elimina. (b) ✔ esfera 1 kg contra parede de 10 cm: padrão (0,02) atravessa a ≥30 m/s; timeconst 0,004 bloqueia até 100 m/s — timeconst ↓ (≥2·dt), espessura ≳ v·dt, dt↓ |
| **Explode** (`BADQACC`/NaN) | h>2/ω da rigidez explícita; `kp`/`kv`; inércia inválida; sobreposição inicial; timeconst<2·dt sem `refsafe` | Checklist acima: dt↓, `armature`, integrador (`implicitfast`/`discrete`) |
| **É ejetada** (sem aviso) | Sobreposição inicial; `refsafe` desligado com timeconst<2·dt | ✔ posicione sem interpenetração; mantenha `refsafe`; timeconst ≥2·dt |
| **Desliza em rampa** | μ ≤ tan θ; cone piramidal anisotrópico; creep do contato macio | Doc: `cone="elliptic"` + `impratio` alto + Newton com `tolerance` ~1e-10 e, se não bastar, NoSlip. ✔ creep ∝ 1/impratio (10–100); `noslip_iterations` 1–3 só ajuda com elíptico; condim 4/6 p/ torque; `multiccd`/`nativeccd` ligados |

## 5. Desempenho em CPU
Ordem oficial de ajuste (`modeling.rst#CPerformance`; perfile antes): (1) `timestep` = o maior que raramente diverge; (2) `integrator` `implicitfast`; (3) `jacobian` dense×sparse; (4) solver/`iterations`/`tolerance` (Newton: a última iteração raramente importa); (5) colisões: `mju_threadpool`, `contype`/`conaffinity`, primitivas no lugar de malhas, malhas decimadas; (6) cone piramidal×elíptico; (7) float32 (raramente ajuda).

| Mecanismo ✔ (i9-14900HX, 32 CPUs lógicas, humanoide; absolutos variam muito com a carga) | Resultado | Notas |
|---|---|---|
| `rollout.rollout` / `rollout.Rollout(nthread=n)` | 24,8k passos/s (1 thread) ⇒ 2,05× / 3,3× / 5,5× / 7,7× com 2/4/8/16 threads; saída **bit-idêntica** para qualquer nthread | `data` = lista de nthread MjData (conteúdo prévio não afeta a saída); `model` pode ser uma sequência de nbatch MjModel de mesmo tamanho; estado `FULLPHYSICS` (time é o 1º elemento); trajetória divergente é congelada ⇒ `time` não crescente; em blocos, passe `initial_warmstart=data.qacc_warmstart` |
| Threads Python: 1 `MjModel` (const) + 1 `MjData`/thread | 30k ⇒ 170k passos/s (16 threads) | GIL liberada em cada chamada (doc); sob 8–16 threads `mj_step(m, d, nstep=N)` foi 1,2–1,9× mais rápido que o laço `for` ✔ (1 thread: igual); nunca compartilhe `MjData` |
| `mju_threadpool` (pool interno) | ≈1,3× no humanoid100 (Q14) | só narrowphase/ilhas; para amostragem prefira 1 MjData por thread |
| Copiar/criar `MjData` | `MjData(m)` 592 µs; `copy.copy` 578 µs (≈20 passos); `mj_copyData` 6,7 µs; `mj_getState`+`mj_setState` 1,6 µs; `mj_copyState` 0,5 µs | aloque 1 `MjData` por thread e reinicialize copiando só o estado |

⚠ `rollout.rollout(..., persistent_pool=True)` **não é thread-safe** (pode travar o interpretador; encerre com `rollout.shutdown_persistent_pool()`): para vários pools use `Rollout`. ✔ O C++ congela a trajetória em QUALQUER aviso (testado com `CONTACTFULL`: `time` parou no 1º passo).

```python
import mujoco, numpy as np, time
from mujoco import rollout
m = mujoco.MjModel.from_xml_path("/home/ondokai/Projects/MuJoCo/docs/upstream/mujoco/model/humanoid/humanoid.xml"); spec = mujoco.mjtState.mjSTATE_FULLPHYSICS
d0 = mujoco.MjData(m); mujoco.mj_forward(m, d0); s0 = np.empty(mujoco.mj_stateSize(m, spec)); mujoco.mj_getState(m, d0, s0, spec)
nbatch, nstep, nthread = 256, 200, 8
init = np.tile(s0, (nbatch, 1)); ctrl = 0.3 * np.random.default_rng(0).standard_normal((nbatch, nstep, m.nu))
datas = [mujoco.MjData(m) for _ in range(nthread)]                   # 1 MjData por thread; 1 MjModel (const) compartilhado
with rollout.Rollout(nthread=nthread) as r:                          # pool próprio, fechado pelo with
    t0 = time.perf_counter(); state, _ = r.rollout(m, datas, init, ctrl, nstep=nstep); dt = time.perf_counter() - t0
print(f"{nbatch * nstep / dt:,.0f} passos/s | divergiu: {bool((np.diff(state[:, :, 0], axis=1) <= 0).any())}")   # state[..., 0] = time; não crescente ⇒ divergiu
mujoco.mj_copyState(m, d0, datas[0], spec)                           # reinicializar um MjData = copiar só o estado (0,5 µs); copy.copy(MjData) ≈ 580 µs
```

## 6. Correções ao relatório do usuário (§2.1–§2.4)
| § do relatório | Afirmação | Veredito | Correção (✔ = testado aqui) |
|---|---|---|---|
| 2.1 | `τ = M(q)·v̇ + c(q,v)` | PARCIAL | É `M·v̇ + c = τ + Jᵀf`: falta a força de restrição Jᵀf (contatos, limites, equalities, frictionloss); inversa `τ = M·v̇ + c − Jᵀf`. c (`qfrc_bias`) = Coriolis+centrífuga+gravidade; τ = `qfrc_passive`+`qfrc_actuator`+`qfrc_applied` (+`xfrc_applied`); «aerodinâmica» = forças de fluido passivas (`density`/`viscosity`>0); empuxo de hélice entra por atuador |
| 2.1 | c via RNE, M via CRB, fatoração LᵀDL + retrossubstituição esparsa | CORRETA | Confere (Euler+damping fatora M̂=M+hD em `qH`; `implicit` usa LU `qLU`). A tabela da doc cita `mjData.qM`, **removido na 3.11**: hoje só `data.M` (CSR) |
| 2.2 | dt demasiado grande induz «explosão algébrica» | CORRETA no essencial (Q3) · PARCIAL (Q14) | Instabilidade ocorre quando h excede o limite da parte explícita (h<2/ω; RK4 ≈2,83/ω ✔); o crescimento é **geométrico** (≈×171/passo medido em Q14), não «algébrico»; dt não é a única causa (seção 4) e há «explosões» silenciosas sem aviso (`refsafe` off, sobreposição) ✔ |
| 2.2 | Euler: «desempenho máximo; padrão em RL» | PARCIAL | Euler é o padrão da biblioteca, **não o recomendado**: `implicitfast` custa ~+9% (0,96–1,13× ✔) e é mais estável. «Padrão em RL» só em parte ✔ (Playground 9 Euler/7 `implicitfast`; Menagerie 58/61 `implicitfast`) |
| 2.2 | RK4 «preserva rotações e o rácio de energia (h\|ω\|)²» | **INCORRETA** | (h\|ω\|)² é a taxa **por passo do amortecimento leve** que `implicit`/`implicitfast` impõem a corpos em tombo (daí a doc indicar RK4 p/ conservação de longo prazo). RK4 conserva a energia quase exatamente ✔ (KE final/inicial 1,000000 vs Euler 1,112; implicit/`implicitfast` 0,903). «Preserva rotações» não é do RK4: ‖q‖−1 ≤1,2e-15 em **todos** ✔; RK4 deriva menos o momento angular (1,9e-5 vs 5,0e-2 ✔) |
| 2.2 | RK4 indicado p/ pêndulos, biomecânica e robôs orbitais | PARCIAL | Doc: sistemas (quase) conservativos (pêndulo, tombo no vácuo) ✔. Biomecânica (músculos, damping, contato) não: sem ganho em contato (pilha de cubos idêntica ao Euler a ~3,4× o custo; doc antiga: «we have not observed significant benefits»); limites: sem *sleeping*/`mjd_transitionFD`, vira Euler em `mj_step1/2` |
| 2.2 | Implícito: «estabilidade incondicional» | **INCORRETA** | É implícito só em velocidade; a doc não afirma estabilidade incondicional. ✔ Mola rígida diverge com h>2/ω em `implicit`, `implicitfast` e Euler (idênticos); Q3: cadeia de 3 elos divergiu a 5 ms. Só o `discrete` (3.13) reivindica estabilidade em rigidez de posição e linhas de restrição |
| 2.2 | Implícito «trata rigidez extrema acoplando molas (fluido/elasticidade)» | DESATUALIZADA | Fluido: sim (viscosidade/arrasto dependem da velocidade; doc recomenda `implicit`/`implicitfast`; ✔ estáveis a qualquer h testado, Euler 2,8 ms, RK4 3,8 ms). Molas (`stiffness`, `kp`): **não** (posição explícita; issue #3443) ⇒ `discrete`. Flex elástico: o tratamento implícito sob `implicit`/`implicitfast`+CG (3.11) foi **removido na 3.13**; hoje exige `integrator="discrete"` (FatalError nos demais) |
| 2.3 | Contato como otimização convexa, «soft contacts», tolera «interpenetrações subtis» | CORRETA | QP (piramidal)/cônico (elíptico), sem complementaridade estrita. A penetração não é «sutil» por construção: é regida por solref/solimp/margin (≈0,4 mm em repouso com o padrão numa esfera de 4,19 kg; 19,9 mm no impacto a 2,8 m/s ✔) |
| 2.3 | `a₁ + d·(b·v + k·r) = (1−d)·a₀` | CORRETA (ressalva) | Equação **aproximada** (a₁=a_c, a₀=a_u); `r = dist − margin` (0 nas linhas de atrito); `b`, `k` derivam de solref/solimp (seção 3); o motor guarda K sem d(r) ✔ |
| 2.3 | `solimp`: «impedância entre limites estritos (d0 e d_width)» | PARCIAL | São **5** números (d₀, d_w, width, midpoint, power; `0.9 0.95 0.001 0.5 2`); d₀/d_w são os valores em r=0 e \|r\|≥width (não «limites estritos»; d₀ pode exceder d_w); a 3.15 usa d_w (3.1.6: d_width). É propriedade da **restrição**, mista por priority/solmix, e vale p/ todas as linhas do contato |
| 2.3 | `solref`: «timeconst e dampratio» | PARCIAL | Só no formato padrão (ambos >0; `0.02 1`); com valores ≤0 é o formato **direto** (−stiffness, −damping); timeconst ≥2·dt (`refsafe`); no atrito elíptico só o timeconst conta; entre geoms: média por `solmix` (mínimo se direto) |
| 2.4 | Cones elípticos/piramidais, «configuráveis globalmente» | CORRETA | `<option cone>`; padrão **pyramidal**; independente do solver (Δ doc: «determined by the choice of constraint solver» é texto legado); a doc recomenda experimentar elíptico; a pirâmide é anisotrópica ✔ |
| 2.4 | `condim` 1/3/4/6 (torsional «pneu parado»; rolamento p/ esferas/cilindros) | CORRETA (precisões) | Só 1/3/4/6 (2 e 5 ⇒ erro); padrão 3; torsional/rolamento em unidades de **comprimento**, no vetor `friction` de 3 números (5 no `<pair>`); condim 6 serve a qualquer par (pneu/estrada); entre geoms: priority, depois máximo ✔ |

## Armadilhas
| Sintoma | Causa | Correção |
|---|---|---|
| `data.energy` não bate com o estado final (RK4: 1,2e-7 em vez de 1,0e-10 J) | a energia é calculada dentro de `mj_forward` (estado do início do passo / último estágio) | `mj_forward(m, d)` após `mj_step` antes de ler ✔ |
| Meu `solref`/`friction` «não pega» | o outro geom (piso padrão) entra na mistura; solref direto ⇒ mínimo | defina nos dois geoms, `priority` ou `<pair>` ✔ |
| `friction="0 ..."` ainda tem atrito | `mjMINMU`=1e-5 | `condim=1` ✔ |
| `data.timer` zerado em C; `mj_timingStatus` não existe | Δ doc: em C só funciona com `mjcb_time`; os bindings Python instalam um timer padrão em **segundos** ✔ | ler `data.timer[i].duration/number` |
| Laço lento ao reiniciar | `copy.copy(MjData)` ≈20 passos | `mj_copyState` ✔ |
| `qacc` do `discrete` «mudou» com dt | é a diferença finita (v⁺−v)/h, não a aceleração contínua | compare sensores/dinâmica inversa sabendo disso (`fwdinv` segue válido) |
| `jacobian` «auto» não é o mais rápido | heurística por nv, não por nº de restrições | teste dense×sparse ✔ |
| `solver_niter` é vetor | 3.15: um valor por ilha (`mjNISLAND`=20) | use `solver_niter[0]` (1 ilha) ou `.sum()` ✔ |
