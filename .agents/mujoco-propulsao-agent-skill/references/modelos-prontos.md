# Modelos PRONTOS a reutilizar — onde buscar, o que existe, como adaptar

Mapa operacional do ecossistema MuJoCo 3.15 (verificado por pesquisa profunda + verificação adversarial
21/21 + provas por execução, 2026-10-15; dossiê completo: `pesquisas/2026-10-15-modelos-prontos-mujoco.md`).
Serve para NUNCA construir do zero sem antes consultar esta tabela.

## 1. Acervos (por ordem de utilidade)

| Fonte | O que traz | Licença | Obter |
|---|---|---|---|
| `google-deepmind/mujoco_menagerie` | 69 modelos robóticos (drones, braços, humanoides, quadrúpedes, mãos, **bases móveis de rodas**): MJCF + assets + LICENSE + scene.xml (10 com variantes `scene_*.xml`) | **por subdiretório** — 69 auditados, todos permissivos (MIT/BSD/Apache) | `git clone --sparse` por pasta (procedimento AGENTS.md) ou `pip install mujoco-menagerie` |
| `google-deepmind/mujoco` `model/` | `car.xml` (carro com atuadores por tendões), humanoid, tendon_arm, exemplos de plugin | Apache-2.0 | já vem com o motor (`docs/upstream/mujoco/model/`) |
| `google-deepmind/mujoco_playground` | ambientes RL (JAX/MJX) com PPO; descarrega assets do menagerie na 1.ª carga | Apache-2.0 | git |
| `google-deepmind/dm_control` | Control Suite + **PyMJCF/Composer** para compor modelos | Apache-2.0 | `pip install dm_control` |
| `robot-descriptions/robot_descriptions.py` | 221 descrições URDF/MJCF com cache no 1.º import | por descrição (ver tabela do README) | `pip install robot_descriptions` |

## 2. O que existe por categoria (verificado ficheiro a ficheiro)

- **Drones**: exatamente 2 no menagerie — `bitcraze_crazyflie_2` (MIT; **wrench** agregado, `ctrlrange` arbitrário, gear de momento 1e-5) e `skydio_x2` (Apache-2.0; **4 motores por rotor** 0–13 N, guinada no gear ±0.0201, **IMU já no XML**). Comunidade: MuJoCo-Drones-Gym (CF2X/CF2P/RACE — MIT só auto-declarado), crazyflow (dinâmica em JAX!), MultiDroneSim (dormente). **Sem multirotores >2 kg** (maior pronto = X2, 1,325 kg).
- **Veículos**: `car.xml` oficial (corre em 3.15 sem avisos — smoke test replicado) · TurtleBot3 (ROBOTIS, fabricante) · robot_soccer_kit omni + pal_tiago + stretch + tidybot (menagerie) · MuSHR (legado mjkey — aproveitam-se só os MJCF). Sem rovers planetários.
- **Robôs**: menagerie (Spot 19 DoF BSD-3, Panda, H1/G1…) com convenção `attachment_site` para mãos; Adroit; Gymnasium-Robotics.
- **Foguete/jato**: `pkothare/mujoco-rocket-landing` (**MIT** — rocket.xml com TVC/grid fins/RCS verificado por dentro) · mjorbit e SmallSatSim (2026; licenças por confirmar) · Falcon9 repos SEM licença (= não copiar). Parâmetros: **RocketPy (MIT)** com `.eng`/`.csv`, JSBSim (LGPL-2.1), dados do thrustcurve.org (licença POR FICHEIRO).
- **Explosivos/separação**: **NADA pronto** → usar o template `objeto-propulsado` (receita validada).

## 3. Modelos prontos NÃO são verdade — calibrar primeiro

Não existe validação sim2real publicada dos modelos do menagerie (o HyperMPC usou o X2 só em simulação).
Receita de uso responsável (Q2.2 do dossiê): tratar como **ponto de partida**; calibrar **escala de
empuxo/torque** primeiro (maior fonte de erro); domain randomization **±10–20%** em massa/inércia/motor/
escalas; escalar entre classes com m~L³, I~L⁵, kM/kF~L (aproximação demonstrada até ~2,1 kg/500 mm —
para frames maiores, identificar por bancada: testbed força/torque + ajuste de trajetórias).

## 4. Adaptação a 3.15 (receita oficial + armadilhas provadas)

1. URDF→MJCF **uma vez**: extensão `<mujoco><compiler .../></mujoco>` no URDF → carregar e guardar MJCF →
   completar com `<include>`. URDF **não** valida schema (typos ignorados em silêncio — provado).
2. Breaking changes (versão exata): `actuatorfrcrange` (3.0.0) · composite→flexcomp/replicate (3.2.5) ·
   margin/gap (3.9.0) · `mj_fullM(m,d,dst)` (3.10.0) · **`mjData.qM` removido (3.11.0)** · texturas só PNG/KTX (3.12.0).
3. Colisão de `mesh` = **convex hull** (malhas cóncavas não colidem como parecem; SDF/flexes para côncavo).
4. `fusestatic` (default true em URDF) funde a base no worldbody — `fusestatic="false"` para manter.
5. Bug #3559 (rotação do `<inertial>` do URDF) **corrigido em 3.15.0** (provado por execução; 3.12.0 reproduz).
6. **Ctrl por nome** sempre (`lab.mjkit.Ctrl`): atuadores multi-entrada gravam no slot errado.
7. Licença: ler o `LICENSE` do subdiretório ANTES de vendorizar; sem licença = não usar; NC/GPL na comunidade.

## 5. Foguete: `.eng` (RASP) → atuador MuJoCo

`.eng` = cabeçalho 7 campos (nome · diâmetro mm · comprimento mm · atrasos · massa consumíveis kg · massa
total kg · fabricante) + pares tempo(s)/empuxo(N); (0,0) implícito; último ponto a 0 = queima. **Sem Isp**
(derivar: I = ∫F dt, Isp = I/(m_prop·g₀)). Em MuJoCo: F(t) interpolada → atuador `general` com transmissão
**site** (gear 6D; «jets and propellers») ou `xfrc_applied`; massa variável = propelente como corpo soldado
ao pai + `body_mass/body_inertia` por passo com `mj_setConst` (escalar massa e inércia juntos; a = F/m
verificado). Cuidado: `.eng` reais nem sempre terminam a 0; para CG variável usar `.rse`/RocketPy.

## 6. Explosivos: nada pronto → a receita do template

`mj_applyFT` (força/torque num ponto) ou `xfrc_applied` (wrench no CoM) por N passos (forças **persistem**,
API stateless — limpar depois); separação = weld/connect equality solta com `mjData.eq_active` (engine C
desde 3.0.0, **MJX desde 3.2.5**); nunca usar juntas como conectores de estágios. Validação: Δp=J,
ΔL=(p−CoM)×J, ação-reação (provado no `run.py` do template `objeto-propulsado`).
