# Auditoria do relatório técnico do usuário (MuJoCo 3.15.0)

Auditoria completa de `docs/relatorio-tecnico-original.md` («Arquitetura, Configuração e Simulação Avançada de Dinâmica de Corpos Rígidos com MuJoCo»): cada afirmação com veredito, correção, evidência e onde a skill a detalha; mais o código do §4.2 corrigido e executado.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: fichas `pesquisas/conhecimento/Q1..Q16.md` e `_auditoria_bruta.md`; `docs/upstream/mujoco/doc/{overview,computation/index,python,mjx,mjwarp/index}.rst`, `README.md`; `viewer.py` do wheel; testes próprios (✔, abaixo).

## Quando ler este arquivo

- Antes de citar ou reutilizar qualquer afirmação, número, tabela ou trecho de código de `docs/relatorio-tecnico-original.md` — é um bom ponto de partida, não verdade verificada.
- Para saber o que está correto, parcial, incorreto, desatualizado ou não verificado, e em qual `references/*.md` está a correção detalhada (última coluna).
- Para copiar o snippet do §4.2 já corrigido (seção «Código do relatório, corrigido»).

> **Evidência:** `Qn` = ficha `pesquisas/conhecimento/Qn.md` (`Fx` = fonte dentro dela); `doc:` = `docs/upstream/mujoco/doc/` (arquivo:linhas); ✔ = reexecutado nesta redação (`.venv`, mujoco 3.15.0): **A** tombo livre × 5 integradores · **B** mola rígida ω=100, h=0,019/0,021/0,1 · **C** padrões de `<option>` e voo de 10 s a 10 m/s · **D** `qfrc_bias` × `gravcomp` · **E** `<compiler>` × `<option>` · **F** URDF nativo + `balanceinertia` · **G** `MjVfs`, `sensordata`/`noise`, `MjModel` mutável, `mjx` ausente · **H** views × `.copy()` · **I** derivados defasados após `mj_step` · **P** `pkg-config`, `pacman.conf`, `ld.so` · **S** snippet original com viewer falso · **V** `viewer.py` do wheel (scripts efêmeros; a descrição basta para reproduzir). `install-linux`, `robots`, `telemetry-rerun`, `python-api` ✔ = testes dos redatores dessas referências (venvs descartáveis), citados quando corroboram uma linha.
>
> Uma linha de tabela = uma afirmação; as repetidas em fichas diferentes foram unificadas. Vereditos: CORRETA · PARCIAL · INCORRETA · DESATUALIZADA · NÃO VERIFICADO · FORA DO ESCOPO.

## Placar

99 afirmações auditadas (1 linha de tabela = 1 afirmação; ver legenda acima): **31 CORRETA · 47 PARCIAL · 10 INCORRETA · 2 DESATUALIZADA · 3 NÃO VERIFICADO · 6 FORA DO ESCOPO**. Em proporção: 31% corretas como escritas, 47% corretas com ressalva ou imprecisas, 12% incorretas ou desatualizadas e 9% não verificáveis ou fora do escopo. O relatório é um bom ponto de partida; as correções abaixo evitam que seus erros virem conhecimento persistente.

| Seção do relatório | CORRETA | PARCIAL | INCORRETA | DESATUALIZADA | NÃO VERIFICADO | FORA DO ESCOPO | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| §1 | 1 | 2 | 0 | 0 | 0 | 1 | 4 |
| §2.1 | 4 | 2 | 0 | 0 | 1 | 0 | 7 |
| §2.2 | 1 | 2 | 2 | 2 | 0 | 0 | 7 |
| §2.3 | 3 | 2 | 0 | 0 | 1 | 0 | 6 |
| §2.4 | 2 | 3 | 0 | 0 | 0 | 0 | 5 |
| §2.5 | 3 | 5 | 0 | 0 | 0 | 0 | 8 |
| §3.1 | 2 | 5 | 1 | 0 | 0 | 1 | 9 |
| §3.2 | 0 | 3 | 1 | 0 | 0 | 0 | 4 |
| §4.1 | 1 | 4 | 0 | 0 | 1 | 1 | 7 |
| §4.2 | 4 | 4 | 1 | 0 | 0 | 0 | 9 |
| §4.3 | 3 | 5 | 2 | 0 | 0 | 0 | 10 |
| §5 | 1 | 0 | 0 | 0 | 0 | 1 | 2 |
| §5.1 | 1 | 4 | 1 | 0 | 0 | 0 | 6 |
| §5.2 | 1 | 4 | 0 | 0 | 0 | 1 | 6 |
| §6 | 4 | 2 | 2 | 0 | 0 | 1 | 9 |
| **Total** | **31** | **47** | **10** | **2** | **3** | **6** | **99** |

**O que o usuário mais precisa saber** (correções de maior impacto prático):

1. **CMake**: `pkg_search_module(MUJOCO mujoco)` não funciona — o MuJoCo oficial não instala `mujoco.pc` (✔P `pkg-config --exists mujoco` → 1); use `find_package(mujoco CONFIG REQUIRED)` + `target_link_libraries(app PRIVATE mujoco::mujoco)` (linhas 3.1-7/8).
2. **RK4 NÃO «preserva (h·\|ω\|)²»**: esse fator é o amortecimento leve que `implicit`/`implicitfast` impõem a corpos em tombo; RK4 conserva a energia (KE/KE0 = 1,000000 vs Euler 1,112 e implicit 0,903 ✔A), custa ~4× e não serve a contato/biomecânica (linhas 2.2-3/4).
3. **`implicit` NÃO é incondicionalmente estável** e não trata rigidez de molas (só o novo `discrete`, 3.13). Euler é o padrão da biblioteca, mas o recomendado é `implicitfast` (custo ≈ Euler); a tabela do relatório omite os dois (linhas 2.2-2/5/6/7).
4. **2,96 M e 2,33 M SPS são ambos MJX-Warp (JAX FFI) em cenas diferentes** — Humanoid e Aloha Pot (`mjx.rst:187-202`); MJWarp puro = 3,35 M/2,45 M; MJX-JAX no humanoide: 950 K (A100). Hardware não declarado: nenhum vale para a RTX 4070 (linhas 4.3-8/9).
5. **`urdf2mjcf` não faz CoACD nem «nivelamento» de inércia**: balancear é `compiler/balanceinertia` do MuJoCo; `class="decomposed_collision"` vem do `mujoco_ros2_control`/obj2mjcf; e o MuJoCo já carrega URDF nativamente (linhas 6-3/5/8).
6. **macOS**: `viewer.launch_passive` sem `mjpython` levanta `RuntimeError`, não SegFault (✔V `viewer.py:574-593`); `pip install mujoco` basta (sem Homebrew/GLFW); o render offscreen não tem restrição de main thread (seção §3.2).
7. **Código do §4.2**: acesso por nome (`model.actuator('x')` → KeyError) em vez de `mj_name2id` (−1 → `ctrl[-1]` silencioso); `actuator_ctrladr` com atuadores multi-entrada; `time.time`+`sleep` deriva (0,962×) → ancorar em `perf_counter` (1,000×); o modelo tem bug (haste × base soldada: \|θ\|máx 0,005 rad); VFS é `MjVfs` (seção §4.2).
8. **A gravidade está em `qfrc_bias`**, não em `qfrc_passive`/`qfrc_applied` (só `gravcomp` e o fluido entram em `qfrc_passive`); `qfrc_applied`/`xfrc_applied` são entradas persistentes; após `mj_step` os derivados ficam um passo atrás → `mj_forward` antes de logar; `mj_contactForce` vem no frame do contato (linhas 5.2-3/4/5).
9. **O ar não atenua «fortemente»**: com `density=viscosity=0` (padrão) não há atenuação; em ar o efeito vem do arrasto QUADRÁTICO (`density`): 10 m/s → 3,12 m/s em 10 s contra 9,9957 só com viscosidade (razão ≈ 2e-4) (linha 5.1-6).
10. **Equação do movimento**: M·v̇ + c = τ + Jᵀ·f (o relatório omite Jᵀ·f); `mjData.qM` foi removido na 3.11 (use `data.M`, CSR); `MjModel` não é imutável — a estrutura é fixa, os parâmetros reais são graváveis (linhas 2.1-4/7 e 4.1-2).
11. **Contato**: `solref` tem formato direto (negativo) e exige `timeconst ≥ 2·timestep` (`refsafe`); `solimp` tem 5 números; só `condim` 1/3/4/6 existem; condim 4/6 *opõem-se* (não «bloqueiam») e rendem com `cone="elliptic"`; «essencial» é exagero (o `car.xml` oficial usa condim 3) (seções §2.3 e §2.4).
12. **Instalação Linux**: o wheel basta (`libmujoco.so.3.15.0` ao lado das extensões, RUNPATH `$ORIGIN` → sem `LD_LIBRARY_PATH`); `python-mujoco` do AUR está em 3.3.7 e não empacota binários; x86-64-v3 do CachyOS vale para pacotes de repositório, não para o wheel (seção §3.1).

Reconciliações entre fichas: **(a)** 2.2-1 — Q3 CORRETA × Q14 PARCIAL → CORRETA + ressalva de Q14; **(b)** 3.1-7/8 — Q1 deu um PARCIAL ao par de comandos CMake → dividi em INCORRETA (`pkg_search_module`) e PARCIAL (`PUBLIC`); **(c)** linhas 2.4 — Q4 (tabela condim CORRETA) × Q9 (PARCIAL em «bloqueia»/«essencial») → linhas separadas; **(d)** 5.2-5 — Q13 lê «gravítico compensatório» como gravidade, mas `gravcomp` vive em `qfrc_passive` (✔D) → PARCIAL; **(e)** Q10 («repositórios… o relatório não os enumera») não corresponde a texto do relatório → anexada à linha 6-1; **(f)** Q5/Q12 (URDF «sem otimização»), Q9/Q11 (4096 carros), Q6/Q11 (rollout) e Q12/Q16 (Computation/XML Reference) contadas 1×. **Não executados aqui:** Rerun, JAX/Warp (GPU), macOS, janela real, `urdf2mjcf` — vereditos vindos das fichas e da doc.

## §1 Introdução à simulação robótica determinística

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 1-1 | «A simulação… exige um compromisso rigoroso entre fidelidade física e estabilidade numérica»; «o presente relatório disseca…» (resumo do conteúdo) | FORA DO ESCOPO | Generalidade/sumário: nada a verificar; cada tema é auditado nas seções seguintes. | — | — |
| 1-2 | «MuJoCo (Multi-Joint dynamics with Contact), suportado pela Google DeepMind» | CORRETA | Sigla e mantenedor conferem: adquirido e liberado pela DeepMind em out/2021, código aberto em mai/2022; repositório «maintained by Google DeepMind». | doc: `overview.rst:7-13`, `README.md:17-23`; Q10 | `docs-map` |
| 1-3 | «Desenvolvido especificamente para controlo ótimo, biomecânica e aprendizagem automática» | PARCIAL | A doc o define como «general purpose physics engine» para robótica, biomecânica, gráficos/animação e ML — e também «simulador tradicional, inclusive jogos»; usos citados: síntese de controle, estimação de estado, identificação de sistemas, projeto de mecanismos, dinâmica inversa, amostragem paralela. | doc: `overview.rst:7-9, 22-25` | `docs-map` |
| 1-4 | «diverge dos motores de jogos ao priorizar coordenadas generalizadas, o contacto analítico inversível e a elevada eficiência em cálculo diferencial» | PARCIAL | Coordenadas generalizadas e «analytically-invertible contact dynamics» (dinâmica inversa bem definida) constam da doc. «Eficiência em cálculo diferencial» não tem benchmark: derivadas por diferenças finitas (`mjd_transitionFD`, `mjd_inverseFD`; o D dos implícitos é analítico); o MJX-JAX é diferenciável, o MJX-Warp/MJWarp não. | doc: `overview.rst:35-55`, `computation/index.rst:634`; Q6, Q11 | `physics-tuning`, `gpu-mjx-warp` |

## §2.1 Coordenadas generalizadas e algoritmos de Featherstone

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 2.1-1 | «A esmagadora maioria dos simuladores tradicionais… recorre a coordenadas maximizadas (6 DoF/corpo) + restrições algébricas → instabilidade, separação das juntas» | PARCIAL | Vale para motores de JOGO: a doc diz que usam a representação cartesiana «over-specified», com juntas «enforced numerically and can be violated»; no MuJoCo elas «are implicit in the representation and cannot be violated». Mas os motores tradicionais de robótica/biomecânica já usavam coordenadas generalizadas — a novidade é combiná-las com contato por otimização. Nuance: laços fechados por `connect`/`weld` são restrições macias e abrem folga (3e-12 … 2,4e-4 m). | doc: `overview.rst:35-44, 983-1001`; Q7 | `physics-tuning` |
| 2.1-2 | «(como o Unity com PhysX ou o Unreal Engine com Chaos)» | NÃO VERIFICADO | A doc do MuJoCo só fala em «gaming engines» em geral e nenhuma ficha cobre PhysX/Chaos. Confira nas docs desses motores (p.ex. se oferecem articulações em coordenadas reduzidas) antes de repetir a comparação nominal. | — | — |
| 2.1-3 | «as juntas não são restrições… mas os próprios graus de liberdade» | CORRETA | `<joint>` ADICIONA DoF ao filho (corpo sem junta = soldado ao pai); free 7 qpos/6 qvel, ball 4/3, slide e hinge 1/1 (nq ≠ nv com quaternions). | doc: `overview.rst:482-485, 983-993`; Q5 | `mjcf-cheatsheet` |
| 2.1-4 | «τ = M(q)·v̇ + c(q,v)», τ «incluindo atuadores, aerodinâmica e passivas» | PARCIAL | Equação contínua: M·v̇ + c = τ + Jᵀ·f — o relatório omite a força de restrição Jᵀ·f (contatos, limites, equality, frictionloss); inversa: τ = M·v̇ + c − Jᵀ·f. τ = `qfrc_passive` + `qfrc_actuator` + `qfrc_applied` (+ `xfrc_applied`); «aerodinâmica» = forças passivas de fluido (`qfrc_fluid`, density/viscosity > 0); c = `qfrc_bias`. | Q3 (F1) | `physics-tuning` |
| 2.1-5 | «algoritmos otimizados desenvolvidos por Roy Featherstone» | CORRETA | A doc cita Featherstone (*Rigid Body Dynamics Algorithms*, Springer, 2008) como referência padrão, na qual «our implementation of the RNE and CRB algorithms as well as sparse inertia factorization are based». A autoria histórica de cada algoritmo não é discutida na doc local. | doc: `computation/index.rst:2442-2446` | `docs-map` |
| 2.1-6 | «c(q,v)… pelo RNE (Coriolis, centrífuga e gravidade); M(q) pelo CRB» | CORRETA | c = RNE com aceleração 0 (`qfrc_bias`); M = CRB, armazenada esparsa. ✔D: corpo de 1 kg → `qfrc_bias` = 9,81 com `qfrc_passive` = `qfrc_applied` = 0. | Q3 (F1); ✔D | `physics-tuning`, `python-api` |
| 2.1-7 | «M(q) esparsa; fatorização LᵀDL e retro-substituição esparsa» | CORRETA | Confere. Nuances: Euler + damping fatora M̂ = M+hD por LᵀL (`qH`); `implicit` por LU (`qLU`); `implicitfast` por LᵀL. `mjData.qM` foi REMOVIDO na 3.11 (hoje só `data.M`, CSR) e `mj_fullM(m, d, dst)` mudou na 3.10 — Δ doc: o capítulo Computation ainda cita `qM`. | Q3; Q16#13 | `python-api`, `docs-map` |

## §2.2 Integradores numéricos e conservação dinâmica

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 2.2-1 | «a estabilidade depende do passo de tempo (dt ou h), que, se demasiado elevado, induz explosão algébrica» | CORRETA | Essência certa; «explosão algébrica» não é termo do MuJoCo: o erro cresce geometricamente (≈ ×171/passo no teste de Q14) até \|qacc\| > 1e10 → `mjWARN_BADQACC` + `mj_resetData` (`autoreset`, padrão). Limite da parte explícita: h ≲ 2/ω (mola ω=100: estável a h=0,019, diverge a 0,021 ✔B). Q14 a deu PARCIAL por ignorar outras causas (penetração inicial, `solref` < 2·dt sem `refsafe`, inércia inválida, razão de massas); o relatório não afirma exclusividade. | Q3, Q14; ✔B | `physics-tuning` |
| 2.2-2 | Tabela: Euler semi-implícito = «desempenho computacional máximo»; «padrão em Aprendizagem por Reforço» | PARCIAL | Euler é o PADRÃO da biblioteca (`mjINT_EULER` = 0 ✔C), mas a doc recomenda `implicitfast` («similar computational cost to Euler», «strict improvement», «the recommended integrator for most models»): humanoide Euler 24,0 µs vs implicitfast 26,1 µs (+9% numa máquina/modelo: trate como faixa). Em RL: o Playground fixa Euler em 9 XMLs e implicitfast em 7; na Menagerie 58 de 61 usam implicitfast. | doc: `computation/index.rst:765-772`; Q3; ✔C | `physics-tuning` |
| 2.2-3 | Tabela: RK4 «Preserva rotações e rácio conservador de energia (h\|ω\|)²» | INCORRETA | (h·\|ω\|)² é a taxa POR PASSO do amortecimento leve que `implicit`/`implicitfast` impõem a corpos livres em tombo — por isso a doc manda usar RK4 para conservação de energia de longo prazo. Tombo livre (I = diag(1,2,3), 10 s, h = 2 ms) ✔A: KE/KE0 = Euler 1,112185; RK4 1,000000; implicit = implicitfast = discrete 0,902806. «Preserva rotações» vale para todos (norma do quaternion ≤ 1,2e-15). | doc: `computation/index.rst:623-626`; Q3; ✔A | `physics-tuning`, `experiments-playbook` |
| 2.2-4 | Tabela: RK4 para «sistemas pendulares, biomecânica e robôs orbitais» | PARCIAL | A doc indica RK4 para sistemas conservativos ou quase (pêndulos; tombo em vácuo). Biomecânica (músculos, amortecimento, contatos): sem benefício documentado (pilha de contatos: idêntico ao Euler com 3,4× o custo). RK4: ~4× o custo, vira Euler em `mj_step1`/`mj_step2`, sem `mjd_transitionFD`/`mjd_inverseFD` nem sleeping. | Q3 | `physics-tuning` |
| 2.2-5 | Tabela: Implícito = «Estabilidade incondicional» | INCORRETA | `implicit` é implícito só em VELOCIDADE (D = −∂(τ−c)/∂v); a doc só reivindica estabilidade incondicional de elementos rígidos para o `discrete` (3.13). ✔B mola rígida (ω = 100 rad/s): Euler, implicit e implicitfast divergem em h = 0,021; cadeia de 3 elos: `implicit` diverge em h = 5 ms (Q3). | doc: `computation/index.rst:111, 781`; Q3; ✔B | `physics-tuning` |
| 2.2-6 | Tabela: Implícito «Trata rigidez extrema acoplando molas», p/ «fluidodinâmica ou flexibilidade elástica maciça» | DESATUALIZADA | Fluidos: correto (forças dependentes de velocidade; a doc recomenda implicit/implicitfast). Rigidez de posição (`stiffness`, `kp`): NÃO — só o `discrete` (M̂ = M+hD+h²K): ✔B estável até h = 0,1 s (Q3: até 1,0 s). Flex elástico: o tratamento implícito sob implicit/implicitfast foi removido na 3.13; hoje exige `integrator="discrete"` (senão FatalError). | Q3; ✔B | `physics-tuning` |
| 2.2-7 | Tabela com 3 integradores (Euler, RK4, Implícito) | DESATUALIZADA | A 3.15 tem 5: Euler (0), RK4 (1), implicit (2), `implicitfast` (3, recomendado), `discrete` (4, novo na 3.13). Nomes do XML sensíveis a maiúsculas (`rk4` → invalid keyword). Solvers: PGS, CG, Newton (padrão) + NoSlip opcional. | Q3; ✔C | `physics-tuning` |

## §2.3 Contacto suave (soft contacts) vs. motores LCP

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 2.3-1 | «motores de jogos modelam o contacto como LCP… estrita complementaridade… assume corpos infinitamente duros» | CORRETA | A doc diz que a abordagem moderna define as forças como solução de um LCP ou NCP (ambos NP-hard) e que o hard contact está na origem das dificuldades. Que motores específicos usam LCP não consta da doc. | doc: `overview.rst:46-50`, `computation/index.rst:44-59, 100-101` | `physics-tuning` |
| 2.3-2 | «O MuJoCo descarta a complementaridade estrita… otimização convexa… soft contacts… tolera interpenetrações subtis» | CORRETA | Confere: força única de um problema convexo (QP para cone piramidal; programa cônico para elíptico); sem atrito ≡ LCP. A penetração não é «subtil» por construção: ≈ 0,4 mm em repouso (esfera de 4,19 kg, defaults), mas 19,86 mm no impacto a 2,8 m/s com `solref` = (0.02, 1). | Q4 (F1, F16) | `physics-tuning` |
| 2.3-3 | «Esta divergência… mitiga a instabilidade estrutural, acelera as derivadas para ML e reflete fidedignamente o perfil dos materiais» | NÃO VERIFICADO | A doc destaca solução única e dinâmica inversa bem definida; nenhuma ficha prova «mais estável», «derivadas mais rápidas» ou «fidelidade de material» (solref/solimp são parâmetros de ajuste, sem validação contra materiais reais). | doc: `overview.rst:46-55` | — |
| 2.3-4 | «a1 + d·(b·v + k·r) = (1 − d)·a0» com d impedância, k rigidez, b amortecimento | CORRETA | É a equação de Modeling → Solver parameters, a_c + d(b v + k r) = (1−d) a_u, dada como dinâmica APROXIMADA; r = dist − margin nos contatos. b e k não são atributos: derivam de solref/solimp — padrão b = 2/(d_w·timeconst), k = d(r)/(d_w²·timeconst²·dampratio²). Penetração em repouso r = a_u(1−d)·timeconst²·dampratio² (4 dígitos). | Q4 (F2, F15, F16) | `physics-tuning` |
| 2.3-5 | «solimp: impedância espacial do material entre limites estritos (d0 e d_width)» | PARCIAL | `solimp` = 5 números (d_0, d_w, width, midpoint, power; padrão `0.9 0.95 0.001 0.5 2`): d(r) vai de d_0 (r = 0) a d_w (\|r\| ≥ width) por sigmoide; clamp [0,0001; 0,9999]; não é «limite estrito» (d_0 pode exceder d_w); é do constraint, não do «material»; combinada entre geoms por `priority`/`solmix`. «d_width» é a notação da doc 3.1.6 (3.15: d_w). | Q4 (F2, F11, F15) | `mjcf-cheatsheet`, `physics-tuning` |
| 2.3-6 | «solref: constante de tempo (timeconst) e rácio de amortecimento (dampratio)» | PARCIAL | Só no formato padrão (ambos > 0; default `0.02 1`; dampratio 1 = crítico, < 1 quica). Valores NEGATIVOS = formato direto (−rigidez, −amortecimento; `-1000 0` ⇒ restituição e ≈ 1,00). Regra `timeconst ≥ 2·timestep` (flag `refsafe` usa max(solref[0], 2·dt)). Esfera: dampratio 0,5 repousa em 0,52 s; 0,2 em 1,18 s; 0,1 não repousa em 30 s; o limiar depende da geometria (prisma de 4 contatos, dt 2 ms, timeconst 0,01: ≤ 0,45 não repousa em 8 s, ≥ 0,5 repousa). `refsafe` foi medido só com Euler; dt/(timeconst·dampratio) ≥ 2 também injeta energia (Q15). Entre dois geoms: média por `solmix` (mínimo se algum for direto). ⚠ Não confundir com o `dampratio` do ATUADOR (`position`/`intvelocity`/`orientation`), redefinido na 3.15 por inércia refletida. | Q4 (F2, F15, F16); Q15; `_overrides.json` | `physics-tuning`, `mjcf-cheatsheet` |

## §2.4 Fricção e geometria do cone de atrito

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 2.4-1 | «cones elíticos [sic] ou piramidais, configuráveis globalmente» | CORRETA | `<option cone="pyramidal\|elliptic"/>` (padrão pyramidal = 0; elliptic = 1), só global, independente do solver (PGS/CG/Newton aceitam ambos). A doc recomenda experimentar elíptico; o piramidal é anisotrópico (limite μ/√2 na diagonal: caixa de μ = 0,5 desliza a 18–20° em vez de 26,6°); `impratio`/`solreffriction` rendem com elíptico; NoSlip só zerou o deslize com cone elíptico ou contato único (piramidal com 2–4 contatos: sem efeito; causa desconhecida). | Q4 (F3, F19) | `physics-tuning`, `vehicles` |
| 2.4-2 | «Para pneus ou esferas, o atributo condim… é essencial» | PARCIAL | Exagero: o `car.xml` oficial usa condim 3 (padrão) nas rodas e condim 1 (`priority="1"`) na esfera de apoio e anda/curva normalmente (0,498 m/s; R = 0,21 m); condim 4/6 são refinamentos (resistência ao rolamento, amortecimento de guinada). | Q9 (F1, F20) | `vehicles` |
| 2.4-3 | Tabela: condim 1 = «só normal, sem atrito»; 3 = «tangencial (2 eixos)» | CORRETA | Só 1/3/4/6 são válidos (2 e 5 → «invalid condim»; padrão 3). Linhas por contato: elíptico 1/3/4/6, piramidal 1/4/6/10. `friction` tem 3 números [deslizamento, torsional, rolamento] (padrão `1 0.005 0.0001`; os dois últimos em METROS; 5 no `<pair>`). No contato, condim = máximo dos dois geoms, salvo `priority` maior. | Q4 (F14, F18); Q9 | `mjcf-cheatsheet`, `vehicles` |
| 2.4-4 | Tabela: condim 4 «Bloqueia a rotação em torno da normal (pneu parado no asfalto)» | PARCIAL | O atrito torsional OPÕE-SE ao giro (limite μ_t·N, regularização macia), não trava: giro de 10 rad/s → 1,11 rad/s em 2 s com condim 4 e cone elíptico (condim 3 mantém 10,0); com cone piramidal é bem mais fraco. | Q9 (F22); Q4 | `vehicles` |
| 2.4-5 | Tabela: condim 6 «Adiciona o atrito de rolamento impedindo giro infinito de esferas ou cilindros» | PARCIAL | É RESISTÊNCIA ao rolamento: `friction[2]` = μ_r em metros, μ_r = C_rr·r (r = 0,04 m, C_rr = 0,01 → 0,0004; medido 0,0908 vs 0,0902 m/s²); serve a qualquer par (pneu-estrada), não só esferas/cilindros; com cone piramidal o efeito cai à metade (0,0455). | Q9 (F23) | `vehicles` |

## §2.5 Arquitetura MJCF

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 2.5-1 | «URDF… sem otimização direta de dados»; MJCF «quase um compilador» que converte geometrias em «ponteiros puros» | PARCIAL | A analogia é do manual (MJCF/URDF → parser → mjSpec → compilador → mjModel «cross-indexed and optimized for runtime computation»), mas URDF e MJCF passam pelo MESMO pipeline. O mjModel são arrays planos num único buffer (`mjModel.buffer`) com referências por ÍNDICE inteiro; em Python são views NumPy (OWNDATA = False ✔H). | doc: `overview.rst:79-82`; Q5; ✔H | `mjcf-cheatsheet`, `python-api` |
| 2.5-2 | «`<compiler>` e `<option>`: definem o passo temporal, vetores gravíticos, viscosidade de fluidos e algoritmos do solver» | PARCIAL | Isso é do `<option>` (timestep 0,002; gravity 0 0 −9,81; density/viscosity/wind; integrator; solver; cone…). `<compiler>` controla a COMPILAÇÃO (angle, eulerseq, meshdir, autolimits, inertiafromgeom, balanceinertia, discardvisual, fusestatic…) e não aceita `timestep` (✔E «unrecognized attribute: 'timestep'»). | ✔E; Q3 | `mjcf-cheatsheet` |
| 2.5-3 | «`<worldbody>`: raiz do ambiente e sistema cartesiano global»; «`<body/>`: unidade de massa inercial» | CORRETA | `worldbody` é o corpo raiz «world» (não aceita `<inertial>` nem `<joint>`); `<body>` aninhado é o corpo rígido (massa e inércia, inferidas dos geoms se faltarem). | Q5 (F1, F2) | `mjcf-cheatsheet` |
| 2.5-4 | «`<joint/>`: acoplada ao corpo filho, instaura restrições como dobradiças (hinge) ou esferas (ball)» | PARCIAL | Junta não instaura restrições — ADICIONA graus de liberdade (o §2.1 do próprio relatório diz o contrário). 4 tipos: free, ball, slide, hinge (padrão); o relatório omite `free` (base flutuante) e `slide`. `ball` não combina com `hinge` no mesmo corpo. | Q5 (F21); doc: `overview.rst:482-486` | `mjcf-cheatsheet` |
| 2.5-5 | Lista de nós: compiler, option, worldbody, body, joint, geom, tendon, actuator | PARCIAL | Incompleta e mistura níveis: 17 seções de topo opcionais e repetíveis (option, compiler, size, statistic, asset, worldbody, deformable, contact, equality, tendon, actuator, sensor, keyframe, visual, default, custom, extension) + meta-elementos include/frame/replicate + macros attach/composite/flexcomp. body/joint/geom/site/camera/light/inertial são aninhados. `<visual>` repetido é MESCLADO por atributo (sub-elemento único por bloco). | Q5 (F2, F7, F8, F16) | `mjcf-cheatsheet` |
| 2.5-6 | «`<geom/>`: aspecto (class="visual") separado da colisão (class="collision")» | CORRETA | Padrão válido (Menagerie: visual = contype 0, conaffinity 0, group 2; collision = group 3); os nomes de classe são convenção. ⚠ Sem `<inertial>`, `inertiagrouprange` padrão `0 5` inclui os grupos 2 e 3 → a MASSA DOBRA (esfera r = 0,1: 8,3776 kg em vez de 4,1888): use `inertiagrouprange="3 3"`, `mass="0"`/`density="0"` no visual ou `<inertial>`; `discardvisual="true"` NÃO resolve. | Q5 (F11, F18) | `mjcf-cheatsheet` |
| 2.5-7 | «inércia inferida do volume pela densidade da água, se não fornecida» | CORRETA | `inertiafromgeom="auto"` (padrão) quando o corpo não tem `<inertial>`; `density` padrão do geom = 1000 kg/m³; `mass` do geom tem precedência; só massa/inércia do CORPO vão ao mjModel. Malhas: `mesh/inertia` padrão `legacy` superestima côncavas (U: 8617,5 kg vs 7000 exato) — use `convex`/`exact`. Prisma 0,0207846 m³ → 20,784610 kg. | Q5 (F18, F19); Q15 | `mjcf-cheatsheet`, `experiments-playbook` |
| 2.5-8 | «`<tendon/>` e `<actuator/>` modelam músculos com leis FLV e atuadores elétricos mapeados a transmissões das juntas» | PARCIAL | Só o atuador `<muscle>` (dyntype = gaintype = biastype = muscle) tem FLV (F0 = scale/acc0, scale 200; ativação 0,01/0,04 s; Millard 2013; tendão inelástico). `<tendon>` NÃO tem lei muscular (fixed: combinação linear de juntas escalares; spatial: caminho mínimo, wrapping só em esfera/cilindro). `motor` é força/torque ideal; a física elétrica é do `dcmotor` (3.7+). Há 7 transmissões (joint, jointinparent, slidercrank, tendon, site, body, so3). | Q7 | `actuators-sensors` |

## §3.1 Instalação em CachyOS (inclui a introdução do §3)

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 3.1-1 | (intro do §3) «compilação híbrida nativa C/C++ vinculada com Python via pybind11» | CORRETA | Bindings em pybind11; o wheel cp313 traz 11 extensões pybind11 + `libmujoco.so.3.15.0`. | doc: `python.rst:6`; Q1 | `install-linux`, `python-api` |
| 3.1-2 | «CachyOS: bibliotecas recompiladas para x86-64-v3, ideais para o cálculo de matrizes esparsas» | PARCIAL | O CachyOS recompila PACOTES DE REPOSITÓRIO para x86-64-v3/v4/Zen4+ (✔P: `[cachyos-v3]`, `[cachyos-extra-v3]` e `[cachyos-core-v3]` no `pacman.conf`; CPU com AVX2/FMA/BMI2, sem AVX-512; `ld.so` aceita x86-64-v3), mas o wheel PyPI e o tarball upstream NÃO são recompilados, `mujoco` nem está nos repositórios oficiais do Arch, e «ideais para matrizes esparsas» não tem fonte. O MuJoCo exige CPU com AVX. | Q1 (F42); ✔P | `install-linux` |
| 3.1-3 | «exige-se preparar pacman/AUR, cmake, glfw; gcc-libs, glibc, ninja» | PARCIAL | Depende da rota. Wheel: só glibc (a `libmujoco.so.3.15.0` tem NEEDED libdl/libm/libpthread/libc/librt, sem libstdc++); o pacote PyPI `glfw` embute a libglfw (x11 e wayland). Build do fonte: CMake + compilador C++20 + git (FetchContent) — o mínimo é C++20 desde a 3.3.7; Δ doc: `programming/index.rst:95` ainda diz C++17; Ninja é opcional; glfw/X11/Wayland só para samples/simulate. | Q1; doc: `changelog.rst:1183` | `install-linux` |
| 3.1-4 | «O AUR oferece python-mujoco, empacotando os binários sistémicos» | PARCIAL | Existe, mas está em 3.3.7-1 (desatualizado desde 2025-12-18), NÃO empacota binários (compila os bindings do fonte contra um `mujoco` de sistema) e declara LGPL3 (upstream: Apache-2.0). AUR `mujoco` 3.15.0-1 e `mujoco-bin` 3.14.0-1 (consulta de 2026-10-07; muda rápido); não há `mujoco` nos repositórios oficiais do Arch. | Q1 (F29-F36) | `install-linux` |
| 3.1-5 | «o virtualenv evita as manipulações de LD_LIBRARY_PATH das versões antigas» | PARCIAL | Conclusão certa, causa errada: o wheel guarda a `libmujoco.so.3.15.0` ao lado das extensões (RUNPATH `$ORIGIN`; `import mujoco` funciona com `env -i`); o fim do `LD_LIBRARY_PATH` vem do abandono do mujoco-py (≤ 2.1.0). O venv é isolamento e exigência do PEP 668 no Python do Arch. | Q1 (F15, F28) | `install-linux` |
| 3.1-6 | Passos 2–3: venv + `pip` com «a roda padrão da DeepMind» (bindings + libs C) | CORRETA | `pip install mujoco` (Python ≥ 3.10; cp313 manylinux_2_27/2_28 x86_64: 11 extensões, `libmujoco.so.3.15.0`, 4 plugins, 72 headers). Não vêm `mjpython` (só macOS), `simulate`, `.pc` nem config CMake: o wheel serve ao Python, não ao desenvolvimento C/C++. | Q1 (F2, F14) | `install-linux` |
| 3.1-7 | «CMake: `pkg_search_module(MUJOCO mujoco)`» | INCORRETA | O MuJoCo oficial não instala `mujoco.pc` (tag 3.15.0 sem pkg-config; ✔P `pkg-config --exists mujoco` → 1): a chamada não acha nada e nem define `mujoco::mujoco`. Oficial: `find_package(mujoco CONFIG REQUIRED)` (lê `<prefix>/lib/cmake/mujoco/mujocoConfig.cmake`; fora de /usr: `-DCMAKE_PREFIX_PATH=<prefix>` ou `-Dmujoco_DIR=…`) e `#include <mujoco/mujoco.h>`. Não compilado nesta auditoria; o redator de `install-linux` testou com CMake 4.4.4 (`MUJOCO_FOUND=''`; «target mujoco::mujoco was not found»). | Q1 (F6-F9, F23-F25); ✔P; `install-linux` ✔ | `install-linux` |
| 3.1-8 | «`target_link_libraries(my_app PUBLIC mujoco::mujoco)`» | PARCIAL | O alvo `mujoco::mujoco` existe (NAMESPACE `mujoco::`) e os samples oficiais o usam sem palavra-chave; `PUBLIC` é desnecessário em executável (use PRIVATE) e o alvo só aparece após o `find_package`. | Q1 (F6-F8) | `install-linux` |
| 3.1-9 | «controladores C++ (nós de interface ros2_control)» | FORA DO ESCOPO | Fora do escopo do laboratório (nenhum teste com ROS 2). Existe o pacote comunitário `mujoco_ros2_control` (Q12 F30), não testado aqui. | Q12 | `robots` |

## §3.2 macOS (Apple Silicon)

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 3.2-1 | «depende de Homebrew para a biblioteca OpenGL»; passo 2: «bibliotecas complementares via Homebrew (GLFW)» | PARCIAL | `pip install mujoco` basta: `glfw` e `pyopengl` são dependências do pacote, os wheels macOS do pyGLFW já trazem a libglfw e o `mujoco.Renderer` offscreen usa CGL (`mujoco.cgl`, fallback `mujoco.glfw`). Homebrew é só caminho de fallback do pyGLFW. «OpenGL via Homebrew»: não verificado (sem macOS aqui). | Q2 (F19, F23, F28) | `install-linux`, `rendering-viewer` |
| 3.2-2 | «o macOS proíbe OpenGL/janelas GLFW fora da main thread» | PARCIAL | Vale para JANELAS (GLFW/Cocoa; doc: «a platform limitation which requires the main thread to be one that does the rendering»). O render offscreen deixou de ser restrito à main thread na 2.3.4 (CGL). | doc: `python.rst:92-97`; Q2 (F9) | `rendering-viewer` |
| 3.2-3 | «`viewer.launch_passive()`… o macOS reage emitindo uma interrupção fatal (SegFault)» | INCORRETA | Sem `mjpython`, `launch_passive` levanta RuntimeError («launch_passive requires that the Python script be run under mjpython on macOS»; ✔V `viewer.py:574-593`). No Studio nativo (issue #3579, 3.13.0): `NSWindow should only be instantiated on the main thread!`, sem exceção nem SegFault. Segfaults históricos (#783/#790, 2.3.3) eram race com `mj_forward` (corrigida na 2.3.4) e crash do GLFW ao sair (2.3.7). | ✔V; Q2 (F2, F29, F31) | `rendering-viewer` |
| 3.2-4 | «`mjpython simulacao.py`… força as representações passivas no fio central; os algoritmos iteram noutras frações da CPU» | PARCIAL | Essência certa (drop-in do `python`; só macOS e só para `launch_passive`; o bloqueante `viewer.launch()` dispensa). Mecanismo: o `mjpython` roda o interpretador numa thread SECUNDÁRIA e deixa a thread principal real ao Cocoa (`_MJPYTHON.launch_on_ui_thread`); o script do usuário não roda na principal. Ausente no Linux (✔V `shutil.which('mjpython')` → None). | Q2 (F8, F24); ✔V | `rendering-viewer` |

## §4.1 MjModel e MjData

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 4.1-1 | «aloca grandes blocos contíguos (`MjModel`, `MjData`) sobre ponteiros gerados por pybind11, recusando arrays aninhados» | CORRETA | mjModel = arrays planos tipados num único buffer; mjData idem + arena/stack pré-alocada (zero alocações após a inicialização); em Python os campos são views NumPy sem cópia. | doc: `overview.rst:92-95, 107-112`; Q5 (F23); ✔H | `python-api` |
| 4.1-2 | «`MjModel`… plano estático… retém parâmetros constantes após a conversão» (imutável) | PARCIAL | A ESTRUTURA (nq, nv, nbody…) é fixa e somente leitura (✔G `m.nq = 99` → AttributeError), mas os parâmetros REAIS são graváveis em runtime (✔G `m.opt.timestep`, `m.body_mass`, `geom_friction`…; alguns exigem `mj_setConst`). Mudar a estrutura = editar o `MjSpec` + `spec.recompile(model, data)` (devolve um par NOVO). | doc: `overview.rst:89-91`; Q6; ✔G | `python-api` |
| 4.1-3 | «`MjData`: `qpos`, `qvel`, “forças aceleradoras resolvidas” (`qacc`), `sensordata`, `ctrl`» | PARCIAL | Estado físico = time + qpos + qvel + act (`mjSTATE_FULLPHYSICS`, 1+nq+nv+na). `ctrl`, `qfrc_applied`, `xfrc_applied` e `mocap_*` são ENTRADAS; `qacc` é ACELERAÇÃO (não força) e saída; `sensordata`/`xpos`/contatos são saídas derivadas (zeros até o 1º `mj_forward`; após `mj_step` ficam um passo atrás ✔I). | Q6 (F4, F31); ✔I | `python-api` |
| 4.1-4 | «os dados empíricos de telemetria base dos sensores (`data.sensordata`)» | PARCIAL | `sensordata` é dado SIMULADO dos sensores do MJCF (49 tipos; não existe `imu`: use gyro + accelerometer + framequat no mesmo site). `noise` NÃO injeta ruído desde a 3.1.4 (✔G noise = 0,5 → lê 0,3 exato; adicione o ruído você mesmo); `cutoff` limita; `delay`/`interval`/`nsample` existem. | Q7 (F28); ✔G | `actuators-sensors` |
| 4.1-5 | «injeção nos slices NumPy… alteração assíncrona sem cópias… origina resultados viciados» | PARCIAL | Mecanismo certo (views sobre memória C), risco mal descrito: ATRIBUIR (`d.qpos[:] = x`, `d.qpos = x`, `d.joint('j').qpos = x`) é a forma correta de definir estado (ValueError se o tamanho não bate); o que vicia é GUARDAR sem copiar (✔H lista de views → todos iguais; use `.copy()`). Derivados (`xpos`, `qacc`, `sensordata`) são reescritos a cada passo. | Q6 (F1, F27); ✔H | `python-api` |
| 4.1-6 | «requer a exploração segura da macro» | NÃO VERIFICADO | Não há «macro» na API Python. Formas seguras documentadas: `.copy()`, `mj_getState`/`mj_setState`/`mj_copyState` (`mjSTATE_INTEGRATION` reproduz bit a bit), `mj_resetDataKeyframe` + `mj_forward`. | Q6 (F4, F31) | `python-api` |
| 4.1-7 | (intro do §4) «a interface… rejeita profundamente o paradigma clássico de Objetos» | FORA DO ESCOPO | Retórica: a API expõe classes (`MjModel`, `MjData`, `MjSpec`, `Renderer`) sobre arrays planos. | — | — |

## §4.2 Lógica do controlo (script base)

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 4.2-1 | «carrega a malha estrutural através da VFS (Virtual File System) interna» | INCORRETA | O snippet usa `MjModel.from_xml_string` com primitivas: não há malha nem VFS. A VFS atual é `mujoco.MjVfs` (✔G `with mujoco.MjVfs() as v: v['tet.obj'] = bytes` + `MjModel.from_xml_string(xml, vfs=v)`); o dict `assets=` está depreciado. | Q16#11; ✔G | `python-api` |
| 4.2-2 | MJCF: base + haste (hinge em y) para «torque senoidal (N.m)» | PARCIAL | Compila, mas há BUG: a base não tem junta (soldada ao mundo) ⇒ o filtro pai-filho não vale ⇒ a haste (pivô y = 0,2, raio 0,05) penetra a caixa em 0,05 m: 2 contatos desde t = 0 e \|θ\|máx = 0,005 rad em 3 s (✔S); com pivô em y = 0,26 (ou `<exclude>`) \|θ\|máx = 2,24 rad. A haste parte invertida (m·g·d = 24,66 N·m > 15 N·m do motor): equilíbrio instável. `gravity="0 0 -9.81"` é o padrão (redundante). A doc avisa: «this exclusion is not applied if the parent is a static body». | ✔S; doc: `overview.rst:792-818`; Q4 (F20); `python-api` ✔ | `mjcf-cheatsheet`, `python-api` |
| 4.2-3 | `mj_name2id(modelo, mjOBJ_ACTUATOR, "atuador_principal")` + `dados.ctrl[id_motor]` | PARCIAL | Funciona (id = 0 ✔S), mas é o padrão desaconselhado: nome inexistente → −1 e `data.ctrl[-1] = x` escreve no ÚLTIMO atuador sem erro (✔S), enquanto `model.actuator('nome')` → KeyError com os nomes válidos. Com atuadores multi-entrada (`pid`, `dcmotor`, `orientation`: nu ≠ nactuator) o id NÃO é o índice em `data.ctrl` e `data.actuator('x').ctrl` grava no slot ERRADO: use `model.actuator_ctrladr[id]` (ou `lab.mjkit.Ctrl`); as saídas (`actuator_force` etc.) têm dimensão nout (`actuator_outadr`) e o acessor também erra nelas. | Q6 (F2, F27, F35); ✔S; `_overrides.json` (Q7) | `python-api`, `actuators-sensors` |
| 4.2-4 | `time.time()` + `time.sleep(timestep − tempo_decorrido)` «adequação ao Real-Time» | PARCIAL | É o padrão do `python.rst` («Rudimentary time keeping, will drift relative to wall clock»): ✔S 0,962× do tempo real com `sync()` de 1,5 ms (`python-api`: 0,94×; Q6: sleep fixo 0,517×; ancorar ao relógio 0,999×). `time.time` não é monotônico: use `time.perf_counter()` e ancore `data.time` ao relógio (✔ 1,000×). | doc: `python.rst:203-206`; Q6 (F34); ✔S | `rendering-viewer`, `python-api` |
| 4.2-5 | `launch_passive` como context manager, `viewer.is_running()`, `viewer.sync()` | CORRETA | Confere (✔V `Handle`: `is_running`, `sync(state_only)`, `lock`, `close`, `__enter__`/`__exit__`); macOS exige `mjpython`. `viewer.opt/cam/perturb` só dentro de `with viewer.lock()` (Δ doc: `python.rst` escreve `pert`; o atributo é `perturb` ✔V). mjModel/mjData podem ser alterados fora do lock (o viewer só os toca em `sync()`; o exemplo oficial chama `mj_step` fora do lock) — Δ doc: `python.rst:105-108` diz que também exigem o lock, `110-112` diz que não; a regra conservadora do laboratório (`rendering-viewer`) é envolver step + edições em `with viewer.lock()`. | doc: `python.rst:88-121, 186-206`; ✔V | `rendering-viewer` |
| 4.2-6 | «`mj_step` invoca internamente `mj_forward`… traduz torques em acelerações» | CORRETA | mj_step = mj_checkPos → mj_checkVel → mj_forward → mj_checkAcc → integrador; em Euler ≡ `mj_forward` + `mj_Euler` (bit a bit); `mj_forward` não avança `time`. ⚠ Após `mj_step` os derivados (`xpos`, `site_xpos`, `sensordata`) ficam no estado ANTERIOR (✔I: qpos = 0,999961; site z = 1,000000): chame `mj_forward` para lê-los. | Q6 (F4, F7, F20, F31); ✔I | `python-api`, `physics-tuning` |
| 4.2-7 | «callbacks (`mjcb_control`, `mjcb_sensor`)… expostas pela API C, podem receber funções de Python» | CORRETA | Em Python: `mujoco.set_mjcb_control` / `_sensor` / `_passive` / `_contactfilter` / `_time` / `_act_dyn` / `_act_gain` / `_act_bias` (`set_mjcb_x(None)` remove; globais do processo; exceções propagam). | Q6 (F13, F32) | `python-api` |
| 4.2-8 | «chamadas repetitivas ao GIL durante as quatro derivações do RK4… paralisando o solver»; mitigação: «extensões partilhadas (ctypes)» | PARCIAL | Os bindings readquirem o GIL a cada chamada e `mjcb_control` roda 4× por passo em RK4 (1/1/4 em Euler/implicitfast/RK4). Mas `mjcb_sensor` roda 1×/passo e nada é «paralisado» (≈ 0,6 µs/chamada: 1-DoF 1,45×; humanoide 1,02×) — o prejuízo é perder o escalonamento multithread (8 threads: 4,23× vs 2,03×). ctypes é a mitigação documentada (sem GIL, 1,00×); mais simples: `data.ctrl` antes de `mj_step`, `mj_step1`/`mj_step2` (RK4 cai em Euler), `mj_step(m, d, nstep=N)`, `mujoco.rollout`. | Q6 (F6, F13, F32) | `python-api`, `physics-tuning` |
| 4.2-9 | `<motor name="atuador_principal" joint="junta_motor" gear="1.0"/>` num hinge, controlado por `data.ctrl` | CORRETA | Válido: com J = 0,1 kg·m², ctrl = 0,5 → `qfrc_actuator` = 0,500 N·m e qacc = 5,000 rad/s². `gear="1.0"` é redundante (padrão `1 0 0 0 0 0`); sem `ctrlrange` o torque é ilimitado; `data.ctrl[i]` ≡ `data.actuator(nome).ctrl` só quando TODOS os atuadores têm 1 controle. | Q7 (F34, F36) | `actuators-sensors` |

## §4.3 MJX e arquitetura GPU

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 4.3-1 | «CPU multithreaded clássica exposta no módulo `mujoco.rollout`» | CORRETA | `from mujoco import rollout` (não vem com `import mujoco`); pool nativo C++ com o GIL liberado; só paraleliza se `data` for uma LISTA com N `MjData` (tupla falha); resultados idênticos bit a bit; 1,8×/3,1×/4,6×/6,8× com 2/4/8/16 MjData (Q14: 6,0× com 16 threads — registre faixa, não valor único). | Q6 (F11, F12, F33); Q14 | `python-api`, `gpu-mjx-warp` |
| 4.3-2 | «a versão sequencial do núcleo C… estrangula… cessa de escalar perante as ordens logarítmicas de paralelismo de GPU/TPU» | PARCIAL | O rollout não é sequencial e escala com os núcleos (doc, 1 humanoide: CPU AMD 3995WX de 64 núcleos = 1,8 M SPS; M3 Max = 650 K); medido aqui: ~34–40 K SPS (1 thread) e ~0,26–0,29 M (32 threads), sem colapso em 4096. A GPU ganha em lotes grandes; TPU só no MJX-JAX. | doc: `mjx.rst:664-676`; Q11 (F20) | `gpu-mjx-warp` |
| 4.3-3 | «MJX… reimplementação em JAX/XLA para GPU/TPU, estruturas `mjx.Model`/`mjx.Data` em batch» | CORRETA | `pip install mujoco-mjx` (pacote separado: ✔G `from mujoco import mjx` → ImportError); `mjx.put_model(m)` + `mjx.make_data(m)` (ou `put_data`) + `mjx.step`; o batch vem de `jax.vmap`/`jax.jit` (não é automático). Em 3.15, «MJX» = API JAX com duas implementações: `impl='jax'` (padrão) e `impl='warp'`. | Q11 (F1, F7); ✔G | `gpu-mjx-warp` |
| 4.3-4 | «O MJX reproduz o espetro determinístico»; «contacto convexo esparso de XLA para evitar dispersão de ramificações na VRAM» | PARCIAL | Paridade incompleta no MJX-JAX: sem flex, PGS, noslip, SDF; integradores só Euler/RK4/implicitfast; Jacobiano só DENSE (não «esparso»); fluido só inertia-box; elipsoide/cilindro só colidem com primitivos; float32 no MJWarp (tolerance ≥ 1e-6) e GPU não determinística. «Evitar ramificações» é real — o MJX-JAX usa um broad-phase sem ramificações, mais simples que o do MuJoCo. | doc: `mjx.rst:657-662`; Q11 #15-16 | `gpu-mjx-warp` |
| 4.3-5 | «Domain Randomization… requer o envio por `mjx.put_model` e `mjx.make_data`» | PARCIAL | Cria-se UM `mjx.Model` e randomiza-se trocando campos por arrays com dimensão de batch (`model.tree_replace({...})`: `geom_friction`, `body_mass`, `dof_armature`) + `in_axes` do `jax.vmap` (Playground: `domain_randomize(model, rng) -> (model, in_axes)`); MJWarp: `mjw.put_model(mjm, batch_sizes={...})`; geometria/malhas variáveis exigem compilar cada variante no host. | Q11 (F1, F3, F15) | `gpu-mjx-warp` |
| 4.3-6 | «MJX-Warp… maximiza os constrangimentos LCP redefinidos… operações tensoriais em chips CUDA… sacrificando diferenciações analíticas» | PARCIAL | Certo: só NVIDIA/CUDA e sem autodiff (MJX-Warp: «does not support automatic differentiation»; MJWarp: issue #500). Impreciso: MJX-Warp (`impl='warp'`) e MJWarp (`import mujoco_warp as mjw`) são APIs distintas sobre o mesmo motor (vendorizado em `mujoco.mjx.third_party.mujoco_warp`), que roda kernels CUDA SIMT em Warp (tiles só para álgebra densa, ex.: Cholesky) — não um compilador de tensores; o MJX-JAX é que tem autodiff; os constraints do MuJoCo não são «LCP». | Q11 (F1, F3, F12) | `gpu-mjx-warp` |
| 4.3-7 | Tabela: MuJoCo (CPU) «otimizado para latência… teleoperação e MPC em tempo real» | CORRETA | A doc: MJWarp = throughput; MuJoCo (C) = latência; o C é preferível a controle online (MPC) e interfaces interativas. | doc: `mjwarp/index.rst:34-59`; Q11 | `gpu-mjx-warp` |
| 4.3-8 | Tabela: «MJX (JAX) — 2.33 Milhões SPS» (Humanoid) | INCORRETA | 2,33 M é a cena Aloha Pot do MJX-Warp via JAX FFI (graph mode `WARP`), não Humanoid nem MJX-JAX. Valores da doc para 1 humanoide: MJX-JAX 950 K (A100, batch 8192) e 2,7 M (TPU v5 de 8 chips, batch 16384); CPU 650 K (M3 Max) e 1,8 M (3995WX). | doc: `mjx.rst:187-202, 664-676`; Q11 | `gpu-mjx-warp` |
| 4.3-9 | Tabela: «MJWarp (CUDA) — 2.96 Milhões SPS»; «blocos Cholesky agressivos sem fator diferencial»; «sem recaptura gráfica forçada» | INCORRETA | 2,96 M = Humanoid no MJX-Warp via JAX FFI (`WARP`); MJWarp puro (sem JAX FFI) = 3,35 M (Humanoid) / 2,45 M (Aloha Pot); `WARP_STAGED` 2,67 M/1,96 M; recaptura forçada 0,80 M/0,65 M; hardware não declarado — nenhum número vale para a RTX 4070 (SPS medidos nesta GPU: `gpu-benchmarks`). Os dois números do relatório são MJX-Warp em cenas diferentes. Cholesky: tiles Warp (Q11); «agressivos»: não verificável. | doc: `mjx.rst:187-202`; Q11 | `gpu-mjx-warp` |
| 4.3-10 | «4096 carros robóticos» como cenário de RL em GPU | PARCIAL | Plausível, mas não é cenário oficial: `batch_size = 4096` é o exemplo da skill oficial `accelerated`; o Playground treina locomoção com `num_envs=8192` e não tem veículo de rodas. Na GPU o contato roda-piso perde `noslip` (MJWarp: NotImplementedError; MJX: só CG/Newton), roda em float32 e, no MJX-JAX, `cylinder` só colide com primitivos. VRAM/SPS de 4096 carros numa RTX 4070 de 8 GB: não verificado aqui (JAX/Warp não instalados); medições reais desta GPU: `gpu-benchmarks`. | Q9 (F6-F11, F45) | `vehicles`, `gpu-mjx-warp` |

## §5 Integração com Rerun.io (introdução)

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 5-1 | «o ecrã nativo torna-se obsoleto» (vetores aerodinâmicos, «lidar volumétrico espelhado», nuvem) | FORA DO ESCOPO | Opinião. Fatos úteis: o visualizador nativo desenha forças de contato/perturbação (flags `mjVIS_CONTACTFORCE` etc., desligadas por padrão) e há alternativas leves (matplotlib/Agg); «lidar» não é termo do MuJoCo (há `rangefinder`). | Q13 #24 | `telemetry-rerun`, `rendering-viewer` |
| 5-2 | «Rerun.io, data logger de arquitetura colunar (column-oriented) em Rust, com suporte imediato em Python» | CORRETA | Armazenamento em chunks colunares (Apache Arrow); «Built in Rust on column-chunk storage… SDKs in Python, Rust, and C++»; `pip install rerun-sdk` (0.38.1; Python ≥ 3.10). Hoje se descreve como «data layer for physical AI»; `rr.log` é orientada a linhas (colunar = `rr.send_columns`). Não há exemplo oficial MuJoCo + Rerun (issue #8634 aberta). Não executado nesta auditoria; o redator de `telemetry-rerun` testou a API 0.38.1 num venv descartável. | Q13 (F14, F19-F21, F24); `telemetry-rerun` ✔ | `telemetry-rerun` |

## §5.1 Modelo aerodinâmico e viscosidade

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 5.1-1 | «drones… integram leis fluidodinâmicas se o MJCF tiver parâmetros nas tags globais e de contacto da geometria» | PARCIAL | Só há força de fluido com `<option density>`/`viscosity` > 0 (padrão 0 ⇒ nenhuma força, mesmo com `wind`). `fluidshape`/`fluidcoef` são atributos de `<geom>` (não de «contacto») e só valem com `fluidshape="ellipsoid"`; sem ele vale a caixa de inércia do corpo. Modelo fenomenológico sem estado: não é CFD (não modela pás, ESC nem efeito solo). | Q8 | `drones` |
| 5.1-2 | «`fluidshape="ellipsoid"` desativa os cálculos esféricos orientados pela inércia… Kutta-Joukowski e Magnus» | PARCIAL | Núcleo certo (elipsoide equivalente do geom: massa adicionada, arrasto blunt/slender/angular, Kutta, Magnus f_M = C_M·ρ·V·ω×v, Stokes). Mas o modelo desativado NÃO é «esférico»: é a caixa de inércia equivalente (arrasto quadrático por eixo principal); a troca é por CORPO (um geom marcado → corpo todo no modelo de elipsoide; os geoms não marcados contribuem com força zero); `<visual><global ellipsoidinertia>` só muda o desenho. | Q8 (F1, F11-F13) | `drones` |
| 5.1-3 | Tabela fluidcoef: blunt 0.5; slender 0.25; angular 1.5; Kutta 1.0; Magnus 1.0 | CORRETA | `fluidcoef` = `0.5 0.25 1.5 1.0 1.0` (confirmado em `model.geom_fluid[:, 1:6]`); sem `fluidshape="ellipsoid"` o vetor é todo zero (ignorado). Convenção: C_blunt = 0,5 ≡ Cd clássico 1,0 (F = ρ·C·A·v², sem ½). | Q8 (F1, F10) | `drones`, `mjcf-cheatsheet` |
| 5.1-4 | Tabela: descrições — «resistência… linear», angular = «força», Magnus = «refração de ar» | PARCIAL | O arrasto blunt/slender é QUADRÁTICO em v (não «linear»); o arrasto angular é um TORQUE ∝ \|ω\|ω; Magnus = sustentação C_M·ρ·V·ω×v (perpendicular a ω e a v), sem «refração». | Q8 (F1, F13) | `drones` |
| 5.1-5 | «os fatores combinam-se com density, viscosity e wind da aba `<option>`» | PARCIAL | `density` multiplica os termos quadráticos (arrasto, Kutta, Magnus, massa adicionada); `viscosity` aciona o Stokes e NÃO é escalada por `fluidcoef`; `wind` é subtraído só da velocidade translacional. `viscosity` é DINÂMICA (Pa·s; ar ≈ 1,8e-5; Stokes medido = 6π·μ·r·v) — Δ doc: `fluid.rst` a chama de «cinemática». `<option>` é tag, não «aba». | Q8 (F1, F2, F14) | `drones` |
| 5.1-6 | «a energia atenua fortemente os objetos voadores… resistência viscosa… derivadas numéricas» | INCORRETA | Por omissão (density = viscosity = 0) NÃO há atenuação. Em ar (ρ = 1,225; β = 1,8e-5), quad de 1 kg a 10 m/s, 10 s ✔C: só viscosidade 10,0000 → 9,9957 m/s; só densidade → 3,12 m/s: a perda vem do arrasto QUADRÁTICO (razão viscoso/quadrático ≈ 2e-4). Só é forte em meios densos (água: 0,056 m/s após 1 s). | Q8 (F24); ✔C | `drones` |

## §5.2 Orquestração visual via arquétipos e logs

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 5.2-1 | «o script escreve `rr.log` a cada transição da árvore semântica (ECS), em grupos como "drone/aerodinamica"» | PARCIAL | `rr.log(entity_path, entity, *extra, static=False)` e `'drone/aerodinamica'` (entity path válido) existem na 0.38.1. Faltam: `rr.init(...)` (senão tudo é no-op) + `spawn`/`save`/`connect_grpc`; `rr.set_time('sim_time', duration=data.time)` (sem isso só há tempo de parede; `set_time_sequence`/`_seconds`/`_nanos` foram REMOVIDOS na 0.28). «ECS» como nome do modelo de dados: não verificado. | Q13 (F13, F14, F16); `telemetry-rerun` ✔ (sem `init` nada é gravado) | `telemetry-rerun` |
| 5.2-2 | «Archetypes… nuvens `rr.Points3D` ou eixos `rr.Arrows3D`» | CORRETA | `rr.Points3D(positions, *, radii, colors, …)` e `rr.Arrows3D(*, vectors, origins=None, …)` (`vectors=` só por palavra-chave; setas, não eixos — eixos = `rr.TransformAxes3D`). Poses: `rr.Transform3D(translation=…, quaternion=rr.Quaternion(xyzw=[x,y,z,w]))` — o quaternion do Rerun é xyzw e o do MuJoCo é [w,x,y,z]. | Q13 (F13, F15); `telemetry-rerun` ✔ (`Arrows3D` só kw-only; `quaternion=` lido como xyzw) | `telemetry-rerun` |
| 5.2-3 | «a matriz iterativa `data.contact`… expõe o número `ncon`» | PARCIAL | `ncon` é campo de `MjData` (`len(data.contact) == data.ncon`), não da «matriz»; `data.contact` é uma lista de `mjContact` de tamanho e ordem variáveis. Contatos inativos (zona gap, `efc_address == -1`) têm força zero: filtre `data.contact.efc_address >= 0`. | Q13 (F3, F5, F9) | `telemetry-rerun`, `python-api` |
| 5.2-4 | «`mj_contactForce(model, data, index, force_array)` extrai a tradução convexa LCP… vetor exato no referencial do mundo» | PARCIAL | Assinatura ✔ (`result` float64[6] gravável: força 3D + torque 3D), mas o resultado vem no FRAME DO CONTATO. Mundo: `R = data.contact[i].frame.reshape(3,3)` (eixos nas LINHAS; normal = 1ª) e `f_mundo = R.T @ f[:3]` = força de geom[0] SOBRE geom[1] (sobre geom[0]: −R.T@f); teste: caixa de 1 kg, 4 contatos somam (0, 0, 9,81) N. Não é «LCP» (contradiz o §2.3). Cone piramidal: não use `efc_force` cru. | Q13 (F1-F4, F9) | `telemetry-rerun`, `python-api` |
| 5.2-5 | «forças aerodinâmicas (ou gravíticas compensatórias) injetadas ciclicamente em `qfrc_passive` e `qfrc_applied` antes de `mj_step` terminar» | PARCIAL | A GRAVIDADE está em `qfrc_bias` (✔D: `qfrc_bias` = 9,81; `qfrc_passive` = `qfrc_applied` = 0); só a gravidade COMPENSADA (`gravcomp`: ✔D `qfrc_passive` = 9,81) e o fluido do MuJoCo (`qfrc_fluid`) entram em `qfrc_passive`, recalculado a cada avaliação (não «acumula»; após `mj_step` reflete o INÍCIO do passo). `qfrc_applied`/`xfrc_applied` são ENTRADAS que o MuJoCo nunca escreve nem zera: sua aerodinâmica só aparece se você a escrever antes de `mj_step`. | Q13 (F1, F4, F10); ✔D | `telemetry-rerun`, `physics-tuning` |
| 5.2-6 | «visualizar o desgaste do atrito linear elítico ou o ponto fulcral aerodinâmico em 3D» | FORA DO ESCOPO | Sem definição operacional: a doc não tem modelo de desgaste (busca por «wear» em `doc/*.rst`: 0 ocorrências); a força de atrito = componentes tangenciais de `mj_contactForce`. | busca em `doc/*.rst`; Q13 | `telemetry-rerun` |

## §6 Documentação e URDF (urdf2mjcf)

| # | Afirmação do relatório (resumida, citando o trecho) | Veredito | Correção/ressalva (valores e nomes exatos) | Evidência (ficha/arquivo da doc/teste) | Onde está detalhado na skill (referência) |
| --- | --- | --- | --- | --- | --- |
| 6-1 | «repositório principal… atualizado exaustivamente sob a égide da Google DeepMind (github.com/google-deepmind/mujoco)», com «Computation» e «XML Reference» | CORRETA | `doc/computation/index.rst` e `doc/XMLreference.rst` estão na toctree (13 capítulos; guia de uso do MJCF = Modeling; manuais de referência = XML Reference e API Reference); a 3.15.0 saiu em 2026-10-05 (meta mensal). Ecossistema que o relatório omite: mujoco_warp, playground e menagerie são mantidos (Menagerie: licença POR modelo — Apache-2.0 em 30 pastas, BSD-3-Clause 22, MIT 13, BSD-2-Clause 3, BSD-3-Clause-Clear 1; `pip install mujoco-menagerie` 2026.10.1); mujoco_mpc está parado desde 27/05/2025; mjlab fixa mujoco~=3.11; dm_control 1.0.48 exige mujoco ≥ 3.15.0 (e o `labmaze` não tem wheels para Python 3.13). | Q16, Q12, Q10 | `docs-map`, `robots` |
| 6-2 | «URDF… carece totalmente dos ajustes de soft contact» | CORRETA | URDF não tem solref/solimp (o bloco `<mujoco>` só aceita `compiler`, `option`, `size`; `<gazebo>` é ignorado); as geoms ficam nos padrões `solref=[0.02 1]`, `solimp=[0.9 0.95 0.001 0.5 2]`, `friction=[1 0.005 0.0001]`: ajuste no MJCF por default class. | Q12 (F1, F2) | `robots`, `mjcf-cheatsheet` |
| 6-3 | «a comunidade confia irredutivelmente no `urdf2mjcf` (K-Scale Labs) para transpor robôs ao MJCF» | PARCIAL | O MuJoCo CARREGA URDF nativamente (`MjModel.from_xml_path`/`MjSpec.from_file`; ✔F carregou direto) e a doc recomenda carregar e salvar como MJCF (`mj_saveLastXML`, `spec.to_xml()`); padrões do carregador: `discardvisual=true`, `fusestatic=true`, radianos; `package://` só com `strippath="true"` + `meshdir`. `urdf2mjcf` é projeto comunitário (MIT; 0.2.39 de 17/08/2025; último commit 26/09/2025), uma entre várias opções (obj2mjcf, urdf-to-mjcf). | Q12 (F1, F4, F7, F20); ✔F | `robots` |
| 6-4 | «`pip install urdf2mjcf`; `urdf2mjcf robot.urdf --output robot.mjcf`» | CORRETA | Existe (0.2.39; Python ≥ 3.11; `--output`). Ressalvas: `MjSpec.from_file` não decodifica `.mjcf` na 3.15 (use `--output robot.xml`); base flutuante por padrão (freejoint); não resolve `package://`; copia o `scale` da malha para o `<geom>` (inválido; issue #35). Não executado nesta auditoria (instalar pacotes é proibido); o redator de `robots` o executou em venv descartável (0.2.39). | Q12 (F19-F24, F29); `robots` ✔ | `robots` |
| 6-5 | «examina assimetrias na diagonal da inércia e procede ao seu nivelamento algébrico» | INCORRETA | O `urdf2mjcf` só escreve `diaginertia="ixx iyy izz"` e ignora, com aviso, termos fora da diagonal (> 1e-6); não checa nem balanceia. O «nivelamento» é `compiler/balanceinertia="true"` do MuJoCo (padrão false): A+B ≥ C violada → média dos 3 (✔F (0,001; 0,001; 0,01) → 0,004 × 3); sem a opção: `inertia must satisfy A + B >= C; use 'balanceinertia' to fix`. | Q12 (F21, F25); ✔F; `robots` ✔ (urdf2mjcf executado: A+B<C passa e o MuJoCo recusa) | `robots`, `mjcf-cheatsheet` |
| 6-6 | «separa as malhas de colisão (class="collision") das visuais (class="visual")»; eixos revolutos/prismáticos → hinge/slide | CORRETA | O `urdf2mjcf` cria `<default class="visual">` (contype 0, conaffinity 0, group 2) e `<default class="collision">` (group 1, condim 3, contype 0, conaffinity 1, priority 1, solref `0.005 1`, solimp `0.99 0.999 0.00001`, friction `1 0.01 0.01`). Só revolute/continuous/prismatic geram junta (floating/planar/spherical viram corpo rígido sem aviso). Importador nativo: `<visual>` → contype 0, conaffinity 0, group 1, density 0. | Q12 (F21, F27, F6) | `robots` |
| 6-7 | «geometria .obj côncava… carga extrema e forte instabilidade… polígonos côncavos falsos» | PARCIAL | Para colisão toda malha vira o seu CASCO CONVEXO (qhull): o côncavo fica «preenchido» (toro único segurou a esfera em z = 0,045 m; 24 peças convexas a deixaram passar, z = −0,485 m), não «instável»; o custo cresce com os vértices do casco (`maxhullvert` padrão −1, mínimo 4; MJX: ≤ 64). Formatos: STL binário (1–200000 faces), OBJ, MSH; `.dae` não. ⚠ `maxhullvert` 0/3 via `MjSpec` derruba o processo (SIGSEGV). | Q12 (F3, F11, F12, F14); Q4 | `robots`, `mjcf-cheatsheet` |
| 6-8 | «o script implementa CoACD… `class="decomposed_collision"`… paletas inerentes do visualizador» | INCORRETA | O `urdf2mjcf` NÃO decompõe (`postprocess/collisions.py` só troca malhas de links nomeados por primitivas BOX/PARALLEL_CAPSULES/CORNER_SPHERES/SINGLE_SPHERE). `decomposed_collision` vem do conversor do `mujoco_ros2_control` (obj2mjcf + CoACD, opt-in); as cores do obj2mjcf são aleatórias (`np.random.rand(3)`), não paleta. Para decompor: `obj2mjcf --decompose`, `coacd` (MIT) ou o fork `discoverse-dev/urdf-to-mjcf`. V-HACD está arquivado. Ressalva: o relatório pode estar descrevendo o fork `discoverse-dev/urdf-to-mjcf` (que tem `--collision-type decomposition` com CoACD); para o pacote K-Scale (PyPI 0.2.39) é incorreto — confiança moderada (leitura de código + execução do redator de `robots`). | Q12 (F28, F30-F36, F43); `robots` ✔ (pacote sem coacd/vhacd); `_overrides.json` | `robots` |
| 6-9 | «converte peças não determinísticas num espetro algébrico limpo, isento de pontos interpenetrantes fantasma» | FORA DO ESCOPO | Retórica: a decomposição é aproximada (CoACD `threshold` padrão 0,05); sem garantia testada de ausência de interpenetração. | Q12 (F36) | `robots` |

## Código do relatório, corrigido

Snippet do §4.2 reescrito e **executado** (`.venv/bin/python`, mujoco 3.15.0, `cwd` privado, sem janela). O laço de «tempo real» roda com um viewer falso de mesmo contrato (`is_running`/`sync`); o modo `--janela` usa `mujoco.viewer.launch_passive` como no wheel (API conferida ✔V; **não aberto**, por regra do laboratório).

```python
"""§4.2 do relatório (haste articulada + motor), corrigido para o MuJoCo 3.15.0.
python haste_corrigida.py           -> sem janela (autoteste; CI/agentes)
python haste_corrigida.py --janela  -> viewer passivo em tempo real (macOS: mjpython haste_corrigida.py --janela)"""
import sys
import time
from types import SimpleNamespace

import mujoco
import numpy as np

MJCF = """
<mujoco>
  <option timestep="0.005"/>
  <worldbody>
    <light pos="0 1 1" dir="0 -1 -1" diffuse="1 1 1"/>
    <geom type="plane" size="3 3 0.1" rgba="0.9 0.9 0.9 1"/>
    <body name="base_robotica" pos="0 0 0.5">
      <geom type="box" size="0.2 0.2 0.2" rgba="0.3 0.3 0.3 1"/>
      <body name="haste_articulada" pos="0 0.26 0">
        <joint name="junta_motor" type="hinge" axis="0 1 0"/>
        <geom type="cylinder" size="0.05 0.4" pos="0 0 0.4" rgba="0.8 0.2 0.2 1"/>
      </body>
    </body>
  </worldbody>
  <actuator><motor name="atuador_principal" joint="junta_motor" gear="1"/></actuator>
</mujoco>
"""


def montar():
    modelo = mujoco.MjModel.from_xml_string(MJCF)
    atuador = modelo.actuator("atuador_principal")  # KeyError se o nome não existir (mj_name2id devolveria -1)
    slot = int(modelo.actuator_ctrladr[atuador.id])  # índice em data.ctrl (== id só se todos os atuadores têm 1 controle)
    return modelo, mujoco.MjData(modelo), slot


def passo(modelo, dados, slot):
    dados.ctrl[slot] = 15.0 * np.sin(2 * np.pi * dados.time)  # torque em N·m (gear=1), 1 Hz
    mujoco.mj_step(modelo, dados)


def rodar_sem_janela(modelo, dados, slot, t_fim):
    teta_max = 0.0
    while dados.time < t_fim:
        passo(modelo, dados, slot)
        teta_max = max(teta_max, abs(dados.qpos[0]))
    return teta_max


def rodar_tempo_real(modelo, dados, slot, viewer, max_atraso=50):
    """Ancora o tempo simulado ao relógio monotônico: sem deriva, mesmo com viewer.sync() lento."""
    parede0, sim0 = time.perf_counter(), dados.time
    while viewer.is_running():
        alvo, n = sim0 + time.perf_counter() - parede0, 0
        while dados.time < alvo and n < max_atraso:  # recupera atraso, sem espiral se a máquina não acompanhar
            passo(modelo, dados, slot)
            n += 1
        viewer.sync()
        time.sleep(0.001)


def rodar_com_janela(modelo, dados, slot):
    import mujoco.viewer  # tardio e em função própria: o caminho sem janela nunca toca no GLFW

    with mujoco.viewer.launch_passive(modelo, dados) as viewer:
        rodar_tempo_real(modelo, dados, slot, viewer)


def main():
    modelo, dados, slot = montar()
    if "--janela" in sys.argv:
        return rodar_com_janela(modelo, dados, slot)
    try:  # 1) nome errado: erro explícito
        modelo.actuator("atuador_pricipal")
        raise SystemExit("FALHA: esperava KeyError")
    except KeyError:
        pass
    dados.ctrl[slot] = 2.5  # 2) ctrl -> torque na junta (gear=1); acesso por nome equivale aqui
    mujoco.mj_forward(modelo, dados)
    assert np.isclose(dados.qfrc_actuator[0], 2.5) and dados.actuator("atuador_principal").ctrl[0] == 2.5
    mujoco.mj_resetData(modelo, dados)
    teta_max = rodar_sem_janela(modelo, dados, slot, 3.0)  # 3) a haste se move (no original: 0,005 rad)
    print(f"sem janela: |θ|máx={teta_max:.3f} rad, θ(3 s)={dados.qpos[0]:+.3f} rad")
    assert teta_max > 0.5
    modelo, dados, slot = montar()  # 4) o MESMO laço de tempo real, com viewer falso (sync custa 1,5 ms)
    falso = SimpleNamespace(is_running=lambda: dados.time < 3.0, sync=lambda: time.sleep(0.0015))
    t0 = time.perf_counter()
    rodar_tempo_real(modelo, dados, slot, falso)
    razao = dados.time / (time.perf_counter() - t0)
    print(f"tempo real: razão sim/parede = {razao:.3f}")
    assert 0.97 < razao < 1.03
    print("OK")


if __name__ == "__main__":
    main()
```

Saída ✔ (duas execuções: razão 1,001 e 1,000): `sem janela: |θ|máx=2.241 rad, θ(3 s)=+2.182 rad` · `tempo real: razão sim/parede = 1.000` · `OK`. Snippet ORIGINAL com o mesmo viewer falso ✔S: `id_motor=0`, 3,005 s simulados em 3,124 s de parede (**0,962×**), `qpos=[0.0001833]` (haste emperrada); nome errado → `mj_name2id` = −1 e `ctrl[-1] = 7` sem erro, enquanto `m.actuator('atuador_pricipal')` → `KeyError: Invalid name … Valid names: ['atuador_principal']`.

**Diferenças linha a linha**

| # | Relatório | Corrigido | Por quê |
| --- | --- | --- | --- |
| 1 | `time.time()` ×2 + `time.sleep(timestep − gasto)` | `time.perf_counter()` e `rodar_tempo_real`: avança `mj_step` até `data.time` alcançar o relógio (`alvo = sim0 + agora − parede0`; `max_atraso` = 50) | `time.time` não é monotônico; o sleep deriva (0,962× ✔S; Q6: fixo 0,517×, ancorado 0,999×; `python.rst:203`) |
| 2 | `id_motor = mujoco.mj_name2id(modelo, mjOBJ_ACTUATOR, "atuador_principal")` | `modelo.actuator("atuador_principal")` + `modelo.actuator_ctrladr[atuador.id]` | KeyError em vez de −1 (`ctrl[-1]` silencioso); `actuator_ctrladr` é o índice real de `data.ctrl` com atuadores multi-entrada (nu ≠ nactuator) |
| 3 | `dados.ctrl[id_motor] = torque` dentro do laço | `passo(modelo, dados, slot)` (ctrl + `mj_step`), compartilhado pelos dois modos | o mesmo código roda com e sem janela |
| 4 | `with mujoco.viewer.launch_passive(...)` direto em `simular_dinamica` | `rodar_com_janela` (import tardio) + `rodar_tempo_real(viewer)` independente do viewer; teste com `SimpleNamespace(is_running, sync)` | exercita o laço sem GLFW/janela. ⚠ `import mujoco.viewer` dentro de uma função torna `mujoco` local a ela (UnboundLocalError nos usos anteriores): por isso a função própria |
| 5 | `<body name="haste_articulada" pos="0 0.2 0">` | `pos="0 0.26 0"` | bug do modelo: base soldada ao mundo ⇒ haste × caixa colidem (2 contatos, dist −0,05 m; \|θ\|máx 0,005 → 2,241 rad ✔). Alternativa: `<contact><exclude body1="base_robotica" body2="haste_articulada"/></contact>` (a doc, `overview.rst:805-818`, lista 3 saídas: corpo mocap, manter a junta raiz, `contype`/`conaffinity` ou `<exclude>`) |
| 6 | `gravity="0 0 -9.81"`; `gear="1.0"` | omitido; `gear="1"` | são os padrões (gravity `0 0 -9.81`; gear `1 0 0 0 0 0`) |
| 7 | comentário «injeção de tensores» | — | são arrays NumPy; «tensores» é vocabulário JAX/MJX |
| 8 | (sem teste) | autoteste: KeyError, `ctrl` → `qfrc_actuator` (gear = 1, após `mj_forward`), \|θ\|máx > 0,5 rad, razão de tempo real 0,97–1,03 | roda em CI; ler `qfrc_actuator` exige `mj_forward` (derivados defasados ✔I) |
| 9 | `viewer.sync()` sem `viewer.lock()` | `sync()` a cada iteração; sem lock | `launch_passive` já chama `mj_forward` (`viewer.py:571`); o lock só é obrigatório para `viewer.opt/cam/perturb`; para mjModel/mjData a doc o dispensa (Δ doc em 4.2-5) — se preferir a regra conservadora do laboratório, envolva `passo(...)` em `with viewer.lock():` |
| 10 | — | forma com janela: `python haste_corrigida.py --janela` (macOS: `mjpython haste_corrigida.py --janela`) | não aberta aqui; alternativa do laboratório: `lab.mjkit.Ctrl` + `mjkit.run_viewer` |
| 11 | haste invertida (CM 0,40 m acima do pivô; m·g·d = 24,66 N·m) | mantida (fiel ao relatório) | o motor de 15 N·m não segura a vertical; para pêndulo estável use o cilindro em `pos="0 0 -0.4"` |

## Referências na skill

Nomes previstos (alguns arquivos ainda estão sendo escritos por outros redatores): destino de cada correção; ao serem concluídos, esses arquivos devem incorporar as ressalvas das linhas indicadas.

**Vereditos → referências**

| Veredito | Linhas | Onde a correção vive |
| --- | --- | --- |
| INCORRETA (10) | 2.2-3, 2.2-5, 3.1-7, 3.2-3, 4.2-1, 4.3-8/9, 5.1-6, 6-5, 6-8 | `drones`, `experiments-playbook`, `gpu-mjx-warp`, `install-linux`, `mjcf-cheatsheet`, `physics-tuning`, `python-api`, `rendering-viewer`, `robots` |
| DESATUALIZADA (2) | 2.2-6/7 | `physics-tuning` |
| PARCIAL (47) | 47 linhas | ressalva a manter ao citar: ver a última coluna de cada linha |
| CORRETA (31) | 31 linhas | citar com as nuances da linha (valores e nomes exatos) |
| NÃO VERIFICADO (3) | 2.1-2, 2.3-3, 4.1-6 | não promover a fato; a coluna «correção» diz como verificar |
| FORA DO ESCOPO (6) | 1-1, 3.1-9, 4.1-7, 5-1, 5.2-6, 6-9 | não migrar para a skill |

**Referência → linhas desta auditoria**

| Referência (`references/*.md`) | Linhas | Correções incorporadas |
| --- | --- | --- |
| `install-linux` | 3.1-1…8, 3.2-1 | wheel basta (RUNPATH `$ORIGIN`, sem `LD_LIBRARY_PATH`); `find_package(mujoco CONFIG)` em vez de pkg-config; AUR `python-mujoco` 3.3.7; CachyOS v3 só para pacotes de repositório; macOS sem Homebrew |
| `rendering-viewer` | 3.2-1…4, 4.2-4/5, 5-1 | `launch_passive` sem `mjpython` = RuntimeError; `mjpython` só no macOS; lock só para `opt/cam/perturb` (Δ doc); tempo real ancorado em `perf_counter`; flags `mjVIS_*` |
| `mjcf-cheatsheet` | 2.1-3, 2.3-5/6, 2.4-3, 2.5-1…7, 4.2-2, 5.1-3, 6-2, 6-5, 6-7 | `<option>` ≠ `<compiler>`; 17 seções de topo; tipos de junta; visual/collision e massa dobrada; `solimp` (5 números)/`solref` (formato direto); condim/friction/cone; importador URDF e casco convexo |
| `python-api` | 2.1-6/7, 2.5-1, 3.1-1, 4.1-1…3, 4.1-5/6, 4.2-1…4, 4.2-6…8, 4.3-1, 5.2-3/4 | views × `.copy()`; `MjModel` mutável; `model.actuator(nome)` × `mj_name2id`; `actuator_ctrladr`; `MjVfs`; `mj_step` × `mj_forward` (derivados defasados); callbacks/GIL; `rollout`; `mj_contactForce` |
| `physics-tuning` | 1-4, 2.1-1, 2.1-4, 2.1-6, 2.2-1…7, 2.3-1/2, 2.3-4…6, 2.4-1, 4.2-6, 4.2-8, 5.2-5 | M·v̇ + c = τ + Jᵀ·f; 5 integradores (padrão Euler, recomendado `implicitfast`); RK4 conserva energia, `implicit` não é incondicional, só `discrete` trata rigidez; `refsafe`; `qfrc_*` |
| `actuators-sensors` | 2.5-8, 4.1-4, 4.2-3, 4.2-9 | muscle × tendon × `dcmotor` e as 7 transmissões; `sensordata` simulado, sem ruído nativo, sem sensor `imu`; `actuator_ctrladr` |
| `robots` | 3.1-9, 6-1…9 | URDF nativo (`balanceinertia`, `strippath`); `urdf2mjcf` sem CoACD e sem balanceamento; obj2mjcf/`coacd`; casco convexo; ecossistema (Menagerie, MJPC parado, mjlab fixa 3.11) |
| `drones` | 5.1-1…6 | fluido só com `density`/`viscosity` > 0; caixa de inércia × elipsoide (por corpo); `fluidcoef` = `0.5 0.25 1.5 1.0 1.0`; atenuação do ar vem do arrasto quadrático |
| `vehicles` | 2.4-1…5, 4.3-10 | condim 4/6 amortecem (não bloqueiam) e rendem com cone elíptico; `car.xml` oficial usa condim 3; 4096 carros em GPU sem `noslip` |
| `gpu-mjx-warp` | 1-4, 4.3-1…10 | MJX-JAX × MJX-Warp × MJWarp; 2,96 M/2,33 M = MJX-Warp (Humanoid/Aloha Pot), MJWarp puro 3,35 M/2,45 M; paridade e float32; domain randomization por campos batcheados; rollout em CPU |
| `telemetry-rerun` | 5-1/2, 5.2-1…6 | API do rerun-sdk 0.38 (`rr.set_time`, `Transform3D` xyzw, `Arrows3D(vectors=)`); força de contato no frame do contato; `qfrc_bias` × `qfrc_passive`; `mj_forward` antes de logar |
| `experiments-playbook` | 2.2-3, 2.5-7 | validar com fórmulas fechadas: tombo livre KE/KE0 por integrador; inércia de prisma/tetraedro (20,784610 kg; 7,5424722 kg) |
| `docs-map` | 1-2/3, 2.1-5, 2.1-7, 6-1 | mapa da doc oficial; `qM` removido na 3.11; Δ doc (lock do viewer, `viscosity`); erros das skills oficiais |
