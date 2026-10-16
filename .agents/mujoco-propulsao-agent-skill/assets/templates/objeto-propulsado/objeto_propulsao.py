"""objeto_propulsao — camada de API do objeto propulsado (motores · propulsão · carga explosiva).

Padrão do laboratório (igual ao de `lab/<robo>.py`): `carregar()` → `(model, data, ctrl)` · `definir_*()`
(controles em unidades físicas) · `MODOS` (roteiros ABERTOS `f(model, data, ctrl, carga)`, sem realimentação)
· `ler_*()` (leituras). Quem escreve algoritmos e experimentos é o dono do projeto.

Três elementos prontos a adaptar:
  · **Propulsão multi-eixo** — atuadores por SITE (`empuxo_x/y/z`, ctrl em NEWTON). Mais direções =
    mais `<site>` (eixo z do site = direção da força) + `<general site=... gear="0 0 1">` no XML.
  · **Motor** — `motor_volante` (torque direto na junta, ctrl em N·m). Um motor real (DC de datasheet)
    usa antes o atuador `dcmotor` (ver `references/motores-propulsao.md`).
  · **Carga explosiva** — impulso J (N·s) aplicado como FORÇA externa ao longo de N passos de
    `mj_step` (nada de escrever `qvel`), com libertação do "parafuso" (equality weld) e ação-reação.
"""
from __future__ import annotations

import numpy as np

import mujoco

GRAVIDADE = 9.81          # m/s² (o modelo usa o mesmo valor; lê de model.opt.gravity se mudares)
PASTA = __import__("pathlib").Path(__file__).resolve().parent
XML_PADRAO = PASTA / "modelo.xml"


# --------------------------------------------------------------------------- atuadores (por NOME)
class Ctrl:
    """Escreve em `data.ctrl` pelo NOME do atuador usando `actuator_ctrladr/ctrlnum`.

    ARMADILHA 3.15: atuadores multi-entrada (`pid`, `dcmotor`, `orientation`) têm `nu ≠ nactuator` e
    `data.actuator('x').ctrl` grava no slot ERRADO. Este helper serve para todos. (Espelho do
    `lab.mjkit.Ctrl` do laboratório; fica aqui para o template ser autónomo.)
    """

    def __init__(self, model: mujoco.MjModel):
        self.slots: dict[str, tuple[int, int]] = {}
        for i in range(model.nu):
            nome = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
            self.slots[nome] = (int(model.actuator_ctrladr[i]), int(model.actuator_ctrlnum[i]))

    def set(self, data: mujoco.MjData, nome: str, valor) -> None:
        adr, n = self.slots[nome]
        v = np.atleast_1d(np.asarray(valor, dtype=float))
        if v.size == 1 and n > 1:
            v = np.repeat(v, n)
        if v.size != n:
            raise ValueError(f"atuador '{nome}' tem {n} ctrl(s); recebeu {v.size} valor(es)")
        data.ctrl[adr:adr + n] = v


def carregar(xml=None) -> tuple[mujoco.MjModel, mujoco.MjData, Ctrl]:
    """Carrega o modelo (por omissão o `modelo.xml` ao lado deste ficheiro). Devolve `(model, data, ctrl)`."""
    modelo = XML_PADRAO if xml is None else xml
    model = mujoco.MjModel.from_xml_path(str(modelo))
    data = mujoco.MjData(model)
    return model, data, Ctrl(model)


def massa_total(model: mujoco.MjModel) -> float:
    """Massa total do sistema (soma de todas as massas dos corpos) — kg."""
    return float(np.sum(model.body_mass))


def dof_de(model: mujoco.MjModel, junta: str) -> int:
    """Primeiro índice DOF da junta `junta` (`model.joint('x').dofadr` devolve um array em 3.15;
    o campo chama-se `jnt_dofadr`)."""
    jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, junta)
    return int(model.jnt_dofadr[jid])


def qpos_de(model: mujoco.MjModel, junta: str) -> int:
    """Primeiro índice QPOS da junta `junta` (para leituras/escritas de estado por nome)."""
    jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, junta)
    return int(model.jnt_qposadr[jid])


# --------------------------------------------------------------------------- controles (definir_*)
def definir_empuxo(data: mujoco.MjData, ctrl: Ctrl, eixo: str, newtons: float) -> None:
    """Empuxo de um bocal em NEWTON. `eixo` ∈ "x" | "y" | "z" (ou o nome completo do atuador)."""
    nome = eixo if eixo.startswith("empuxo_") else f"empuxo_{eixo}"
    ctrl.set(data, nome, float(newtons))


def definir_motor(data: mujoco.MjData, ctrl: Ctrl, newton_metros: float) -> None:
    """Torque do motor do volante em N·m (positivo = anti-horário visto de cima)."""
    ctrl.set(data, "motor_volante", float(newton_metros))


# --------------------------------------------------------------------------- carga explosiva
class Carga:
    """Carga explosiva: impulso J (N·s) como FORÇA externa constante F = J/(N·Δt) durante N passos.

    Física sempre real: a força entra por `mj_applyFT` → `qfrc_applied` ANTES de cada `mj_step` e o
    integrador faz o resto (nada de escrever `qvel`/teleporte). O impulso entregue é exato:
    F·N·Δt = J por construção.

    · `detonar(data, J, ponto, corpo)` — impulso J (mundo) aplicado num PONTO (mundo) de um corpo;
    · `detonar_separacao(data, J, ponto)` — solta o parafuso (equality) e aplica +J à tampa e −J ao
      objeto no mesmo ponto (ação-reação: o momento total não muda);
    · `passo(data)` — chamar ANTES de cada `mj_step` enquanto houver cargas ativas.

    ARMADILHA: `qfrc_applied` PERSISTE entre passos e é um campo só. Este template tem a `Carga`
    como única escritora (ela zera o campo no início de cada `passo`); se o teu objeto tiver MAIS
    forças externas (vento, etc.), coordena todas as escritas num só passo de escrita por frame.
    """

    def __init__(self, model: mujoco.MjModel, duracao: float = 0.02):
        self.model = model
        self.dt = float(model.opt.timestep)
        self.n = max(1, int(round(duracao / self.dt)))   # ≥ 5–10 passos: ver explosivos-impulsao.md
        self._ativas: list[dict] = []                    # {bi, ponto_local, J, restantes}

    def _atualizar_cinematica(self, data: mujoco.MjData) -> None:
        """Kinemática fresca (`xpos/xmat/xipos/cdof`) para o ponto de aplicação e o `mj_applyFT`.

        ARMADILHA: sem isto a 1.ª aplicação (antes de qualquer `mj_forward`) sai com `cdof` a zeros
        e o impulso NÃO chega ao corpo (medido: 9/10 do impulso) — e os campos derivados ficam um
        passo atrás do `mj_step`. `mj_kinematics` + `mj_comPos` bastam (é o que o `mj_applyFT` lê).
        """
        mujoco.mj_kinematics(self.model, data)
        mujoco.mj_comPos(self.model, data)

    # -- arranque ------------------------------------------------------------------------------
    def detonar(self, data: mujoco.MjData, J, ponto, corpo: str = "objeto") -> None:
        """Impulso J (N·s, mundo) num ponto (mundo) do corpo `corpo`. Aplique-se por `passo()`."""
        self._atualizar_cinematica(data)
        bi = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, corpo)
        ponto = np.asarray(ponto, dtype=float)
        R = data.xmat[bi].reshape(3, 3)
        local = R.T @ (ponto - data.xpos[bi])            # guarda no frame do corpo (move com ele)
        self._ativas.append({"bi": bi, "ponto_local": local, "J": np.asarray(J, dtype=float),
                             "restantes": self.n})

    def separar(self, data: mujoco.MjData, nome: str = "parafuso") -> None:
        """Solta o 'parafuso explosivo' (equality weld `nome`) — `eq_active = 0` a meio do passo."""
        eid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_EQUALITY, nome)
        data.eq_active[eid] = 0

    def detonar_separacao(self, data: mujoco.MjData, J, ponto=None,
                          corpo_a: str = "tampa", corpo_b: str = "objeto") -> None:
        """Separação explosiva: solta o parafuso e aplica +J a `corpo_a` e −J a `corpo_b` (ação-reação)."""
        self.separar(data)
        if ponto is None:
            self._atualizar_cinematica(data)
            ponto = data.xpos[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, corpo_a)]
        self.detonar(data, np.asarray(J, dtype=float), ponto, corpo_a)
        self.detonar(data, -np.asarray(J, dtype=float), ponto, corpo_b)

    # -- passo ---------------------------------------------------------------------------------
    def ativa(self) -> bool:
        return bool(self._ativas)

    def passo(self, data: mujoco.MjData) -> None:
        """Aplica as forças do passo corrente. Chamar ANTES de `mj_step`."""
        data.qfrc_applied[:] = 0.0                       # ver ARMADILHA no docstring da classe
        if not self._ativas:
            return
        self._atualizar_cinematica(data)
        resto: list[dict] = []
        for c in self._ativas:
            F = c["J"] / (self.n * self.dt)              # F·N·Δt = J (impulso exato)
            bi = c["bi"]
            R = data.xmat[bi].reshape(3, 3)
            ponto = data.xpos[bi] + R @ c["ponto_local"]
            qf = np.zeros(self.model.nv)
            mujoco.mj_applyFT(self.model, data, F, np.zeros(3), ponto, bi, qf)
            data.qfrc_applied += qf
            c["restantes"] -= 1
            if c["restantes"] > 0:
                resto.append(c)
        self._ativas = resto

    def limpar(self, data: mujoco.MjData) -> None:
        """Cancela cargas pendentes e zera o que escreveu (para `reset` explícitos)."""
        self._ativas.clear()
        data.qfrc_applied[:] = 0.0


# --------------------------------------------------------------------------- leituras (ler_*)
def ler_estado(model: mujoco.MjModel, data: mujoco.MjData,
               carga: Carga | None = None) -> dict:
    """Leituras do objeto em unidades SI (chamar `mujoco.mj_forward` antes, se quiseres derivados coerentes)."""
    bi = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "objeto")
    dof = dof_de(model, "objeto_livre")
    return {
        "pos": [float(x) for x in data.xpos[bi]],
        "vel": [float(x) for x in data.qvel[dof:dof + 3]],      # linear, MUNDO (freejoint 3.15)
        "omega": [float(x) for x in data.qvel[dof + 3:dof + 6]],  # angular, CORPO
        "omega_volante": float(data.qvel[dof_de(model, "volante_hinge")]),
        "acc_imu": [float(x) for x in data.sensor("acc").data],
        "giro_imu": [float(x) for x in data.sensor("giro").data],
        "carga_ativa": bool(carga.ativa()) if carga is not None else False,
    }


# --------------------------------------------------------------------------- MODOS (roteiros abertos)
def modo_hover(model: mujoco.MjModel, data: mujoco.MjData, ctrl: Ctrl, carga: Carga | None = None) -> None:
    """Segura o peso: empuxo_z = m·g (sem realimentação — é um roteiro, não um controlador)."""
    definir_empuxo(data, ctrl, "z", massa_total(model) * GRAVIDADE)


def modo_frente(model: mujoco.MjModel, data: mujoco.MjData, ctrl: Ctrl, carga: Carga | None = None) -> None:
    """5 N no bocal +X."""
    definir_empuxo(data, ctrl, "x", 5.0)


def modo_separar(model: mujoco.MjModel, data: mujoco.MjData, ctrl: Ctrl, carga: Carga | None = None) -> None:
    """Detona a separação (1 N·s) na primeira chamada; depois só mantém o hover."""
    if carga is not None and not carga.ativa():
        carga.detonar_separacao(data, np.array([1.0, 0.0, 0.0]))
    modo_hover(model, data, ctrl, carga)


MODOS = {"hover": modo_hover, "frente": modo_frente, "separar": modo_separar}
