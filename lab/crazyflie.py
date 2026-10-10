"""lab.crazyflie — MODOS, CONTROLES e LEITURAS do Crazyflie 2 (Bitcraze) para você criar algoritmos.

Modelo base: `models/bitcraze_crazyflie_2/` (mujoco_menagerie, MIT) — INTACTO. Esta camada:

  1. acrescenta SENSORES via MjSpec (sem editar os XMLs upstream);
  2. expõe CONTROLES como funções (empuxo, momentos, mixer de 4 rotores);
  3. expõe MODOS como funções abertas (roteiros sem realimentação, para demonstrar/testar);
  4. expõe LEITURAS dos sensores como funções.

NÃO há estabilização, PID, IK, atitude-lock nem código do firmware/ROS da Bitcraze — os algoritmos
são seus. Modelo nativo: 4 canais de atuação num site no CM (`body_thrust` 0–0,35 N + `x/y/z_moment`
±1e-5 N·m); a massa é 0,027 kg e o keyframe `hover` tem empuxo = peso (0,26487 N).

    from lab import crazyflie as cf
    modelo, data = cf.carregar()
    cf.hover(modelo, data)                         # empuxo = peso (equilíbrio aberto)
    cf.definir_wrench(modelo, data, 0.30, (0, 0, 0))
    cf.comandar_rotores(modelo, data, [0.07, 0.07, 0.07, 0.07])
    imu = cf.ler_imu(modelo, data)                 # {'giro', 'acc', 'quat'}
    est = cf.ler_estado(modelo, data)              # {'pos', 'vel', 'vel_ang'}

Sensores: os 3 que já vêm no modelo (`body_gyro`, `body_linacc`, `body_quat`, site `imu`) +
`posicao` (framepos), `vel` (velocímetro, corpo) e `acc_corpo`... ver `SENSORES`.
"""
from __future__ import annotations

from pathlib import Path

import mujoco
import numpy as np

from lab import mjkit  # noqa: F401  (garante MUJOCO_GL antes de import mujoco em quem consome o módulo)

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "models" / "bitcraze_crazyflie_2" / "cf2.xml"
CENA = RAIZ / "models" / "bitcraze_crazyflie_2" / "scene.xml"

# ----------------------------------------------------------------------------------------------- constantes
MASSA = 0.027                 # kg (inertial do cf2.xml; datasheet CF2.0 = 27 g de peso de decolagem)
GRAVIDADE = 9.81
PESO = MASSA * GRAVIDADE      # 0.26487 N = ctrl[0] do keyframe `hover` ✔
EMPUXO_MAX = 0.35             # N (ctrlrange de body_thrust — "arbitrário" segundo o README do menagerie)

MOTORES = ("body_thrust", "x_moment", "y_moment", "z_moment")

# posições dos rotores no plano do corpo (m), medidas na malha das hélices (cf2_0.obj):
# 4 hélices a ±0,0325 m → raio 0,0457 m → diagonal motor-a-motor ≈ 92 mm ✔ (datasheet CF2.0)
POS_ROTORES = ((0.0325, 0.0325), (0.0325, -0.0325), (-0.0325, 0.0325), (-0.0325, -0.0325))  # (FL, FR, RL, RR)
GIRO = (1.0, -1.0, -1.0, 1.0)  # hélices em pares CW/CCW (diagonais giram igual) — sinal do momento de guinada
KM = 0.016                    # m: razão momento-de-reatção/empuxo do rotor (parâmetro livre — ajuste ao seu hardware)

# faixa física dos momentos derivada da geometria dos rotores (o gear upstream ±1e-5 N·m é admitido
# "arbitrário" no README do menagerie — `carregar(momentos="nativo")` preserva-o):
BRAÇO = 0.0325                          # m: |x| = |y| de cada rotor
T_ROTOR_MAX = EMPUXO_MAX / 4            # N por rotor (Σ = EMPUXO_MAX)
MOMENTOS_MAX = (2 * BRAÇO * T_ROTOR_MAX,   # roll:  5.69e-3 N·m
                2 * BRAÇO * T_ROTOR_MAX,   # pitch: 5.69e-3 N·m
                2 * KM * T_ROTOR_MAX)     # yaw:   2.80e-3 N·m

SENSORES = ("body_gyro", "body_linacc", "body_quat", "posicao", "vel")

# --- hélices: ANIMAÇÃO VISUAL (nunca física) — ver `preparar_helices`/`Helices` no fim do módulo
MALHA_HELICES = "cf2_0"       # malha upstream com as 4 hélices FUNDIDAS (4 grupos de 843 vértices, um por quadrante)
HELICES = ("helice_1", "helice_2", "helice_3", "helice_4")   # ordem = POS_ROTORES (FL, FR, RL, RR)
MALHAS_HELICES = tuple(f"malha_{n}" for n in HELICES)
REVOLUCOES_VISUAIS = 3.0      # rev/s VISUAIS com um rotor no empuxo máximo (T_ROTOR_MAX): ~1/100 da rotação real
ESCALA_VISUAL = 2.0 * np.pi * REVOLUCOES_VISUAIS / np.sqrt(T_ROTOR_MAX)   # rad/s por √N: |ω_vis| = ESCALA_VISUAL·√t
ABRANDAMENTO_S = 0.35         # s: constante de tempo do arranque/abrandamento VISUAL (1.ª ordem, sem salto)
LIMIAR_PARAGEM = 1e-2         # rad/s: abaixo disto a hélice fica PARADA (ω = 0 exato, ângulo congelado)


# ----------------------------------------------------------------------------------------------- carga
def carregar(cena: bool = True, sensores: bool = True, keyframe: str = "hover",
             momentos: str = "fisico", energia: bool = True,
             helices: bool = False) -> tuple[mujoco.MjModel, mujoco.MjData]:
    """Carrega o modelo (intocado em disco) e prepara a camada do laboratório.

    · `sensores=True` acrescenta `posicao`/`vel` via MjSpec;
    · `momentos="fisico"` (predefinição) escala o gear dos 3 canais de momento para a faixa física
      derivada da geometria dos rotores (`MOMENTOS_MAX`); `"nativo"` preserva o gear upstream (±1e-5 N·m);
    · `energia=True` (predefinição) liga `mjENBL_ENERGY` para que `data.energy` funcione — os experimentos
      contam com isso. Use `energia=False` para preparar o modelo para o MJX: `mjx.put_model` não implementa
      a flag de energia e falha com `NotImplementedError: mjtEnableBit.mjENBL_ENERGY` (MJX-JAX e MJX-Warp);
      o MuJoCo Warp nativo aceita-a.
      ⚠ Com `energia=False` o `data.energy` fica a ZEROS sem dar erro: `mjkit.record` grava `pe`/`ke` = 0 em
      silêncio — use esta opção só para treino/inferência em MJX, nunca para medir ou validar energia.
    · `helices=True` (desligado por omissão: o RL e o deploy não mudam) divide a malha `cf2_0` nas 4 hélices
      visuais `helice_1..4` — SÓ apresentação, para animar com `Helices` (ver o fim deste módulo: massa,
      inércia, contactos e resultados físicos ficam IDÊNTICOS).
    Devolve (model, data) já no keyframe `hover` (posição de cruzeiro, empuxo = peso)."""
    caminho = CENA if cena else MODELO
    if not sensores and not helices:
        model, data = mjkit.load(caminho, energy_flag=energia)
    else:
        spec = mujoco.MjSpec.from_file(str(caminho))
        if sensores:
            _adiciona_sensores(spec)
        if helices:
            preparar_helices(spec)
        model = spec.compile()
        if energia:
            model.opt.enableflags |= mujoco.mjtEnableBit.mjENBL_ENERGY
        data = mujoco.MjData(model)
    if momentos == "fisico":
        for i, nome in enumerate(MOTORES[1:]):
            aid = model.actuator(nome).id
            model.actuator_gear[aid] = 0.0
            model.actuator_gear[aid, 3 + i] = MOMENTOS_MAX[i]   # ctrl ±1 ↔ MOMENTOS_MAX[i] N·m
    if keyframe and model.nkey:
        mujoco.mj_resetDataKeyframe(model, data, model.key(keyframe).id)
    mujoco.mj_forward(model, data)
    return model, data


def _adiciona_sensores(spec: mujoco.MjSpec) -> None:
    """Só leituras (ground truth p/ algoritmos e treino) — nada de controlo. Sensores nativos permanecem."""
    corpo = spec.body("cf2")
    corpo.add_site(name="cm", pos=[0, 0, 0], size=[0.005])
    spec.add_sensor(name="posicao", type=mujoco.mjtSensor.mjSENS_FRAMEPOS,
                    objtype=mujoco.mjtObj.mjOBJ_SITE, objname="cm")
    spec.add_sensor(name="vel", type=mujoco.mjtSensor.mjSENS_VELOCIMETER,
                    objtype=mujoco.mjtObj.mjOBJ_SITE, objname="cm")


# ----------------------------------------------------------------------------------------------- controles
GEAR_EIXO = {"body_thrust": 2, "x_moment": 3, "y_moment": 4, "z_moment": 5}  # índice do componente em actuator_gear (wrench 6D: fx fy fz tx ty tz)


def _slot(model: mujoco.MjModel, nome: str) -> tuple[int, float, float, float]:
    """(posição em data.ctrl, gear escalar, limite físico lo, limite físico hi) do canal.
    Limites físicos = ctrlrange × gear (para os momentos dependem da escala usada em `carregar`)."""
    aid = model.actuator(nome).id
    adr = int(model.actuator_ctrladr[aid])
    gear = float(model.actuator_gear[aid, GEAR_EIXO[nome]])
    lo, hi = sorted((float(model.actuator_ctrlrange[aid, 0]) * gear, float(model.actuator_ctrlrange[aid, 1]) * gear))
    return adr, gear, lo, hi


def definir_empuxo(model: mujoco.MjModel, data: mujoco.MjData, newtons: float) -> float:
    """Empuxo coletivo (N) ao longo do eixo +z do corpo. Cortado para a faixa do canal. Devolve o valor aplicado."""
    adr, gear, lo, hi = _slot(model, "body_thrust")
    v = float(np.clip(newtons, lo, hi))
    data.ctrl[adr] = v / gear
    return v


def definir_momentos(model: mujoco.MjModel, data: mujoco.MjData, mx: float, my: float, mz: float) -> tuple[float, float, float]:
    """Momentos de corpo (N·m) em x (roll), y (pitch), z (yaw). Cortados para a faixa do canal. Devolve o aplicado."""
    v = np.array([mx, my, mz], float)
    for i, nome in enumerate(MOTORES[1:]):
        adr, gear, lo, hi = _slot(model, nome)
        v[i] = float(np.clip(v[i], lo, hi))
        data.ctrl[adr] = v[i] / gear
    return tuple(float(x) for x in v)


def definir_wrench(model: mujoco.MjModel, data: mujoco.MjData, empuxo: float, momentos) -> tuple[float, tuple[float, float, float]]:
    """Empuxo (N) + momentos (N·m) de uma vez. Devolve o wrench aplicado (após cortes)."""
    f = definir_empuxo(model, data, empuxo)
    m = definir_momentos(model, data, *momentos)
    return f, m


def comandar_rotores(model: mujoco.MjModel, data: mujoco.MjData, empuxos) -> tuple[float, tuple[float, float, float]]:
    """Mixer de 4 rotores (configuração X): empuxo de cada rotor (N) → wrench do corpo.

    F_z = Σt_i · τ_x = Σr_y·t_i · τ_y = −Σr_x·t_i · τ_z = Σ giro_i·KM·t_i
    Posições dos rotores (`POS_ROTORES`) medidas na malha do próprio modelo; `KM` é parâmetro livre.
    Devolve o wrench aplicado (após os cortes de ctrlrange)."""
    t = np.clip(np.asarray(empuxos, float).reshape(4), 0.0, None)
    fx = 0.0
    fy = 0.0
    fz = float(t.sum())
    tx = float(sum(p[1] * ti for p, ti in zip(POS_ROTORES, t)))
    ty = float(-sum(p[0] * ti for p, ti in zip(POS_ROTORES, t)))
    tz = float(sum(g * KM * ti for g, ti in zip(GIRO, t)))
    return definir_wrench(model, data, fz, (tx, ty, tz))


def desligar(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    """Motores a zero (queda livre)."""
    for nome in MOTORES:
        adr, *_ = _slot(model, nome)
        data.ctrl[adr] = 0.0


def hover(model: mujoco.MjModel, data: mujoco.MjData) -> float:
    """Empuxo = peso (equilíbrio ABERTO: sem realimentação, qualquer perturração deriva)."""
    return definir_empuxo(model, data, PESO)


# ----------------------------------------------------------------------------------------------- modos (roteiros abertos)
def modo_desligado(model, data, tau: float) -> None:
    """Motores desligados."""
    desligar(model, data)


def modo_hover(model, data, tau: float) -> None:
    """Empuxo constante = peso."""
    hover(model, data)


def modo_empuxo(model, data, tau: float, amp: float = 0.01, freq: float = 0.25) -> None:
    """Empuxo em cosseno: peso + amp·cos(2π·freq·tau) — z oscila com amplitude amp/(m·ω²)."""
    hover(model, data)
    definir_empuxo(model, data, PESO + amp * np.cos(2 * np.pi * freq * tau))


def modo_momento(model, data, tau: float, eixo: int = 0, amp: float | None = None, freq: float = 0.25) -> None:
    """Momento em cosseno num eixo (0=x, 1=y, 2=z): ω oscila com amplitude amp/(I·ω). `amp=None` usa a faixa cheia."""
    hover(model, data)
    m = [0.0, 0.0, 0.0]
    m[eixo] = (MOMENTOS_MAX[eixo] if amp is None else amp) * np.cos(2 * np.pi * freq * tau)
    definir_momentos(model, data, *m)


def modo_rotores(model, data, tau: float, taxa: float = 0.5, duracao: float = 1.0) -> None:
    """Varredura pelos 4 rotores via mixer: um rotor de cada vez com pulso de `taxa`·peso/4 acima do hover."""
    base = PESO / 4
    i = int(tau / duracao) % 4
    t = [base, base, base, base]
    t[i] += taxa * base
    comandar_rotores(model, data, t)


MODOS = {
    "desligado": modo_desligado,
    "hover": modo_hover,
    "empuxo": modo_empuxo,
    "momento_x": lambda m, d, tau: modo_momento(m, d, tau, eixo=0),
    "momento_y": lambda m, d, tau: modo_momento(m, d, tau, eixo=1),
    "momento_z": lambda m, d, tau: modo_momento(m, d, tau, eixo=2),
    "rotores": modo_rotores,
}


# ----------------------------------------------------------------------------------------------- leituras
def _sens(data: mujoco.MjData, nome: str) -> np.ndarray:
    return data.sensor(nome).data.copy()


def ler_imu(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """IMU nativo do modelo (site `imu`): giro (rad/s, corpo) · acc (m/s², aceleração própria) · quat [w x y z]."""
    return {"giro": _sens(data, "body_gyro"), "acc": _sens(data, "body_linacc"), "quat": _sens(data, "body_quat")}


def ler_estado(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """Estado do corpo (ground truth para algoritmos/treino): pos (m, mundo) · vel (m/s, corpo) · vel_ang (rad/s, corpo)."""
    return {"pos": _sens(data, "posicao"), "vel": _sens(data, "vel"),
            "vel_ang": _sens(data, "body_gyro").copy()}


def ler_motores(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """Comandos atuais convertidos para unidades físicas: empuxo (N) · momentos (N·m) · ctrl (bruto)."""
    empuxo = float(data.ctrl[_slot(model, "body_thrust")[0]] * _slot(model, "body_thrust")[1])
    momentos = tuple(float(data.ctrl[_slot(model, n)[0]] * _slot(model, n)[1]) for n in MOTORES[1:])
    return {"empuxo": empuxo, "momentos": momentos,
            "ctrl": np.array([data.ctrl[_slot(model, n)[0]] for n in MOTORES])}


def ler_tudo(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    """Tudo de uma vez: imu · estado · motores · pos/quat do corpo (data)."""
    d = {}
    d.update(ler_imu(model, data))
    d.update(ler_estado(model, data))
    d["motores"] = ler_motores(model, data)
    d["qpos"] = data.qpos.copy()
    return d


# ----------------------------------------------------------------------------------------------- hélices (animação VISUAL)
# ANIMAÇÃO, NUNCA FÍSICA. A única coisa que estes dois objetos fazem é reescrever `model.geom_pos/geom_quat`
# de 4 geoms VISUAIS (contype = conaffinity = 0, density = 0) antes de cada render — fora do `mj_step`. Os
# 4 geoms nascem de geoms/malhas NOVAS em runtime (o XML upstream fica intacto): a malha `cf2_0` (que traz as
# 4 hélices fundidas) é FATIADA por quadrante do sinal de (x, y). O OBJ NÃO tem as hélices como ilhas
# separadas — é um "vertex soup" (medido: 3372 vértices para só 1592 coordenadas únicas, 3168 faces e
# 176 ilhas de aresta, a maior com 130 vértices) — mas NENHUMA das 3168 faces cruza os eixos x = 0 / y = 0 em
# coordenadas do ASSET, e é só isso que o fatiamento exige: cada quadrante leva exactamente 843 vértices /
# 792 faces / 44 ilhas. A malha original é apagada do spec. Prova de neutralidade: `run.py` §10.
def _matriz_de_quat(q) -> np.ndarray:
    """Matriz 3×3 de rotação do quaternion `[w x y z]` (convenção do MuJoCo)."""
    w, x, y, z = (float(v) for v in q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def _le_malha(model: mujoco.MjModel, nome: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(vértices [n,3] no frame da malha, faces [m,3] 0-indexadas, `mesh_pos`, `mesh_quat`) da malha `nome`.

    O compilador recentra a malha no seu CM e alinha os eixos principais com os eixos do frame: para voltar
    às coordenadas do ASSET (as do corpo, porque o geom upstream está em `pos`/`quat` nulos) aplica-se
    `v_corpo = R(mesh_quat)·v_malha + mesh_pos`. O próprio compilador faz o mesmo ao colocar o geom
    (`geom_pos`/`geom_quat` do geom compilado = `mesh_pos`/`mesh_quat`, confirmado em 3.15.0)."""
    mid = model.mesh(nome).id
    a, n = int(model.mesh_vertadr[mid]), int(model.mesh_vertnum[mid])
    fa, nf = int(model.mesh_faceadr[mid]), int(model.mesh_facenum[mid])
    verts = np.asarray(model.mesh_vert[a:a + n], dtype=float).reshape(-1, 3).copy()
    faces = np.asarray(model.mesh_face[fa:fa + nf], dtype=int).reshape(-1, 3).copy()
    return verts, faces, np.asarray(model.mesh_pos[mid], dtype=float).copy(), np.asarray(model.mesh_quat[mid], dtype=float).copy()


def _componentes(vertices: np.ndarray, faces: np.ndarray) -> list[np.ndarray]:
    """Componentes conexas (índices de vértices) do grafo vértice-aresta definido pelas faces."""
    pai = list(range(len(vertices)))

    def raiz(i: int) -> int:
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    for face in faces:
        for i, j in ((face[0], face[1]), (face[0], face[2])):
            ri, rj = raiz(int(i)), raiz(int(j))
            if ri != rj:
                pai[ri] = rj
    grupos: dict[int, list[int]] = {}
    for i in range(len(vertices)):
        grupos.setdefault(raiz(i), []).append(i)
    return list(grupos.values())


def eixo_do_rotor(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Eixo do rotor (ponto no plano xy do corpo) medido na malha de UMA hélice.

    As tampas do motor são as únicas componentes PERFEITAMENTE planas e de secção quadrada (o diâmetro do
    motor, 3,99 mm); o eixo é o centro delas. Se não as encontrar, cai para `POS_ROTORES` (documentado).
    Medido em `cf2_0.obj`: os 4 eixos ficam a 0,7–1,2 mm dos `POS_ROTORES` (±32,5 mm) — a malha do menagerie
    está ligeiramente descentrada em relação à origem do corpo, por isso medir é mais fiel do que assumir."""
    tampas = []
    for comp in _componentes(vertices, faces):
        v = vertices[comp]
        lo, hi = v.min(axis=0), v.max(axis=0)
        d = hi - lo
        if d[2] < 1e-9 and abs(d[0] - d[1]) < 0.02 * d[0] and 1e-3 < d[0] < 8e-3:
            tampas.append((lo + hi) / 2.0)
    if not tampas:
        return np.zeros(3)                                  # sem tampas: o chamador usa POS_ROTORES
    return np.mean(tampas, axis=0)


def preparar_helices(spec: mujoco.MjSpec, malha: str = MALHA_HELICES) -> tuple[str, ...]:
    """Divide a malha `malha` do spec nas 4 hélices visuais `helice_1..4` (runtime, upstream intacto).

    Cada hélice passa a ser uma malha própria (mesmos vértices e faces, reindexados) num geom VISUAL novo
    (`contype=conaffinity=0`, `density=0`, mesmo grupo/material do geom original) e o geom único original é
    apagado. Como o corpo `cf2` tem `<inertial>` explícito e o compilador tem `inertiafromgeom="false"`, a
    massa e a inércia do corpo (e portanto toda a física) não mudam — `run.py` §10 prova-o.
    Devolve os nomes dos geoms criados."""
    corpo = spec.body("cf2")
    alvo = next((g for g in corpo.geoms if g.meshname == malha), None)
    if alvo is None:
        raise ValueError(f"o corpo `cf2` não tem nenhum geom com a malha {malha!r} — modelo inesperado")
    verts, faces, mp, mq = _le_malha(spec.compile(), malha)   # sonda: os vértices de ficheiro só existem compilados
    vertices = verts @ _matriz_de_quat(mq).T + mp             # coordenadas do ASSET (== frame do corpo)
    quadrante = [(1 if v[0] > 0 else -1, 1 if v[1] > 0 else -1) for v in vertices]
    ordem = ((1, 1), (1, -1), (-1, 1), (-1, -1))              # == POS_ROTORES (FL, FR, RL, RR)
    if any(len({quadrante[i] for i in face}) > 1 for face in faces):
        raise ValueError(f"a malha {malha!r} tem faces a cruzar quadrantes — não é fatiável por sinal de (x, y)")
    for nome, chave, nome_malha in zip(HELICES, ordem, MALHAS_HELICES):
        idx = [i for i, k in enumerate(quadrante) if k == chave]
        if not idx:
            raise ValueError(f"quadrante {chave} vazio na malha {malha!r}")
        remapa = {antigo: novo for novo, antigo in enumerate(idx)}
        spec.add_mesh(name=nome_malha, material=alvo.material,
                      uservert=vertices[idx].reshape(-1).tolist(),
                      userface=[remapa[int(i)] for face in faces if int(face[0]) in remapa for i in face])
        corpo.add_geom(name=nome, type=mujoco.mjtGeom.mjGEOM_MESH, meshname=nome_malha,
                       contype=0, conaffinity=0, group=int(alvo.group), material=alvo.material, density=0)
    spec.delete(alvo)
    return HELICES


class Helices:
    """Animação VISUAL das 4 hélices: lê o wrench comandado (`data.ctrl`), tira dele o empuxo de cada rotor
    pelo MIXER INVERSO de `comandar_rotores` e roda o geom correspondente em torno do eixo vertical do rotor.

    · `|ω_vis,i| = ESCALA_VISUAL·√t_i` (a mesma lei do rotor real, T ∝ ω², com uma escala VISUAL legível:
      `REVOLUCOES_VISUAIS` rev/s no empuxo máximo — a rotação real seria ~100× mais rápida e ilegível);
    · o SENTIDO vem de `GIRO` (+1 = anti-horário visto de cima, -1 = horário): diagonais iguais, adjacentes
      opostos, coerente com o sinal do momento de guinada do mixer;
    · com o motor desligado (t_i = 0) a hélice ABRANDA com constante `ABRANDAMENTO_S` e, abaixo de
      `LIMIAR_PARAGEM`, para EXATAMENTE (ω = 0, ângulo congelado);
    · a escrita é só em `model.geom_pos/geom_quat` + `mj_kinematics` (para o renderer ver já este frame):
      NADA toca em `qpos/qvel/ctrl` nem em `mj_step` — a física é idêntica com e sem animação;
    · um reset (REINICIAR) não parte nada: o estado da animação é só ângulo/velocidade e os geoms são
      re-resolvidos por NOME se o modelo mudar; com `ctrl = 0` no reset as hélices abrandam e param.

    `Helices(modelo)` de um modelo SEM as hélices fica INERTE (`ativo = False`, `atualizar` não faz nada):
    é o que permite ligar a animação só em quem a pediu (`carregar(helices=True)`)."""

    def __init__(self, model: mujoco.MjModel, escala: float = ESCALA_VISUAL,
                 abrandamento: float = ABRANDAMENTO_S, limiar: float = LIMIAR_PARAGEM) -> None:
        self.escala = float(escala)
        self.abrandamento = float(abrandamento)
        self.limiar = float(limiar)
        self.angulos = np.zeros(4)
        self.velocidades = np.zeros(4)
        self._modelo: mujoco.MjModel | None = None
        self._geoms: list[int] = []
        self._repouso: list[tuple[np.ndarray, np.ndarray]] = []
        self._eixos: list[np.ndarray] = []
        self._mixer_inverso = np.linalg.inv(np.array(
            [[1.0] * 4] + [[p[1] for p in POS_ROTORES], [-p[0] for p in POS_ROTORES],
                           [g * KM for g in GIRO]], dtype=float))
        self.ativo = False
        self.ligar(model)

    def ligar(self, model: mujoco.MjModel) -> bool:
        """Resolve os 4 geoms por NOME e mede os eixos dos rotores; `False` se o modelo não os tiver."""
        self._modelo = model
        self._geoms, self._repouso, self._eixos = [], [], []
        for nome, pos in zip(HELICES, POS_ROTORES):
            gid = int(mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, nome))
            if gid < 0:                                     # modelo sem a adaptação: animação inerte
                self.ativo = False
                return False
            self._geoms.append(gid)
            self._repouso.append((np.asarray(model.geom_pos[gid], dtype=float).copy(),
                                  np.asarray(model.geom_quat[gid], dtype=float).copy()))
            eixo = self._eixo_da_malha(model, gid)
            self._eixos.append(eixo if np.any(eixo) else np.array([pos[0], pos[1], 0.0]))   # fallback POS_ROTORES
        self.ativo = True
        return True

    @staticmethod
    def _eixo_da_malha(model: mujoco.MjModel, gid: int) -> np.ndarray:
        """Eixo do rotor desta hélice, em coordenadas do ASSET (frame do corpo no repouso)."""
        mid = int(model.geom_dataid[gid])
        a, n = int(model.mesh_vertadr[mid]), int(model.mesh_vertnum[mid])
        fa, nf = int(model.mesh_faceadr[mid]), int(model.mesh_facenum[mid])
        verts = np.asarray(model.mesh_vert[a:a + n], dtype=float).reshape(-1, 3)
        faces = np.asarray(model.mesh_face[fa:fa + nf], dtype=int).reshape(-1, 3)
        vertices = verts @ _matriz_de_quat(model.mesh_quat[mid]).T + model.mesh_pos[mid]
        return eixo_do_rotor(vertices, faces)

    def empuxos(self, model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
        """Empuxo de cada rotor (N) implícito no comando atual: mixer INVERSO de `comandar_rotores`.

        O comando é o wrench que está em `data.ctrl` (empuxo + 3 momentos, o que `ler_motores` devolve em
        unidades físicas); o mixer inverso recupera `t_i` e os negativos (wrench inalcançável) são cortados
        a 0 — um rotor não empurra para baixo."""
        motores = ler_motores(model, data)
        wrench = np.array([motores["empuxo"], *motores["momentos"]], dtype=float)
        return np.clip(self._mixer_inverso @ wrench, 0.0, None)

    def atualizar(self, model: mujoco.MjModel, data: mujoco.MjData, dt: float) -> np.ndarray:
        """Avança a animação `dt` segundos e escreve a pose dos 4 geoms (devolve os ângulos, rad).

        `dt = 0` (pausa) não avança nada: só reescreve a pose atual. Não toca em nada da física."""
        if model is not self._modelo:                       # modelo novo: re-resolve os geoms por NOME
            self.ligar(model)
        if not self.ativo:
            return self.angulos.copy()
        t = self.empuxos(model, data)
        alvo = np.asarray(GIRO, dtype=float) * self.escala * np.sqrt(t)
        if dt > 0.0:
            peso = 1.0 - np.exp(-float(dt) / self.abrandamento)
            self.velocidades += (alvo - self.velocidades) * peso
            self.velocidades[np.abs(self.velocidades) < self.limiar] = 0.0     # pára EXATAMENTE
            self.angulos += self.velocidades * float(dt)
        for i, gid in enumerate(self._geoms):
            self._escreve(model, gid, i, float(self.angulos[i]))
        mujoco.mj_kinematics(model, data)                   # o renderer lê `data.geom_xpos/xmat`: atualiza já
        return self.angulos.copy()

    def _escreve(self, model: mujoco.MjModel, gid: int, i: int, theta: float) -> None:
        """Pose do geom `i` com a hélice rodada `theta` em torno do eixo vertical que passa pelo rotor."""
        p0, q0 = self._repouso[i]
        eixo = self._eixos[i]
        c, s = np.cos(theta), np.sin(theta)
        rz = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        gira = np.array([np.cos(theta / 2), 0.0, 0.0, np.sin(theta / 2)])   # rotação `theta` em torno de +z
        quat = np.zeros(4)
        mujoco.mju_mulQuat(quat, gira, q0)                  # R(quat) = Rz(theta)·R(q0)
        model.geom_pos[gid] = eixo + rz @ (p0 - eixo)       # roda o quadro do geom em torno do eixo
        model.geom_quat[gid] = quat
