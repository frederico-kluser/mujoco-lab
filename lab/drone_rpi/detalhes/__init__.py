"""lab/drone_rpi/detalhes — DETALHE VISUAL realista do drone (2026-10-19): só APARÊNCIA, nunca física.

Pedido do dono: «modelagem 3D realista — o Raspberry Pi 5, o drone, os motores, o mecanismo dos braços (que tem de se
mexer na simulação do MuJoCo), os fios, tudo». Cada subsistema vive num módulo deste pacote, com uma função
`adicionar(ctx: Contexto) -> None`, e o `modelo._montar` chama-os NO FIM da construção (depois de todas as peças com
massa já estarem no spec):

    eletronica   Raspberry Pi 5 (+ Active Cooler), FC H7, 4 ESC, PDB, sensores, câmara, bateria 6S2P, regulador de 24 V
    motores      motores T-Motor (sino, estator, base CNC, eixo, parafusos) e hélices de carbono (pás com forma real)
    estrutura    placas de carbono, espaçadores, parafusos, abraçadeiras dos tubos, pernas — e o MECANISMO dos braços
                 articulados (servos DYNAMIXEL, caixa do sem-fim, dobradiças, suportes) nos corpos que RODAM
    fios         fases dos motores, alimentação dos ESC, cabos da bateria (XT90), barramento dos servos, FPC da câmara,
                 cabos dos sensores e abraçadeiras — com segmentos por corpo nos braços articulados (dobram nas juntas)

REGRAS (impostas pelo `Contexto.geom` — usar SEMPRE ele, nunca `body.add_geom` direto):
  · massa 0, sem contacto (contype = conaffinity = 0): a física fica IGUAL bit a bit (`ver.py` prova-o);
  · grupo 3 por omissão (o «fios e detalhes» do cockpit: visível no 3D, ESCONDIDO da câmara do detetor da bola, que
    só vê o grupo 0) — os grupos 1/2 só para o que já os usa (hélices animadas, efeitos); o grupo 0 é proibido;
  · nada de corpos, juntas, sites, sensores ou atuadores novos (a árvore e o estado do MuJoCo não mudam);
  · âncoras pelos NOMES do modelo (`ctx.pos_geom("el_rpi5")`, `ctx.corpo("braco1")`…), não por números copiados.

`DRONE_DETALHES` (variável de ambiente) escolhe os módulos: «todos» (omissão), «nenhum», ou uma lista «eletronica,fios».
"""
from __future__ import annotations

import importlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field

import mujoco
import numpy as np

MODULOS = ("eletronica", "motores", "estrutura", "fios")
GRUPO_DETALHE = 3
GRUPOS_PERMITIDOS = (1, 2, 3)
# texto custom do modelo com as peças com massa que um detalhe esconde e a cor que tinham («nome r g b a;…»): com os
# detalhes desligados no cockpit (grupo 3 oculto) a câmara volta a desenhá-las (`camera_rpi`), para o drone não ficar
# sem motores nem eletrónica
TEXTO_ESCONDIDOS = "detalhes_escondidos"


def modulos_ativos(pedido: tuple[str, ...] | None = None) -> tuple[str, ...]:
    """Os módulos a montar: `pedido` explícito, senão a variável `DRONE_DETALHES`, senão TODOS."""
    if pedido is not None:
        return tuple(m for m in pedido if m)
    bruto = os.environ.get("DRONE_DETALHES")
    if bruto is None or bruto.strip().lower() in ("", "todos", "all"):
        return MODULOS
    if bruto.strip().lower() in ("nenhum", "none", "0"):
        return ()
    nomes = tuple(m.strip() for m in bruto.split(",") if m.strip())
    desconhecidos = [m for m in nomes if m not in MODULOS]
    if desconhecidos:
        raise ValueError(f"DRONE_DETALHES: módulos desconhecidos {desconhecidos} (válidos: {MODULOS})")
    return nomes


@dataclass
class Contexto:
    """O que um módulo de detalhe recebe: o spec, o hardware, a função `p` do `_montar` (posição no referencial do
    corpo `drone` já com o deslocamento do CM) e o registo do que se acrescentou."""

    spec: mujoco.MjSpec
    hw: object
    p: Callable[[float, float, float], list]
    modulo: str = ""
    geoms: list = field(default_factory=list)

    # ------------------------------------------------------------------ materiais
    def material(self, nome: str, rgba, **kw) -> str:
        """Acrescenta o material se ainda não existe (nomes partilhados entre módulos: o primeiro ganha) e devolve o nome.
        Procura-se na LISTA `spec.materials`: no MuJoCo 3.15 `spec.material(nome)` devolve None para um nome que não
        existe e — medido — também para materiais acrescentados DEPOIS de um `spec.delete` (o `apagar`)."""
        if not any(m.name == nome for m in self.spec.materials):
            self.spec.add_material(name=nome, rgba=list(rgba), **kw)
        return nome

    def obter_material(self, nome: str):
        """O OBJETO do material (para lhe pôr texturas…), procurado na lista — `spec.material(nome)` falha (None) para
        materiais acrescentados depois de um `spec.delete` no 3.15. `None` se não existir."""
        return next((m for m in self.spec.materials if m.name == nome), None)

    # ------------------------------------------------------------------ peças
    def geom(self, corpo, nome: str, grupo: int = GRUPO_DETALHE, **kw):
        """Uma peça SÓ VISUAL no corpo `corpo` (objeto do spec ou nome): massa 0, sem contacto, grupo 3 (ou 1/2)."""
        if grupo not in GRUPOS_PERMITIDOS:
            raise ValueError(f"{nome}: grupo {grupo} proibido nos detalhes (permitidos {GRUPOS_PERMITIDOS})")
        for chave in ("mass", "density", "contype", "conaffinity", "group"):
            if chave in kw:
                raise ValueError(f"{nome}: `{chave}` é imposto pelo Contexto (detalhe = só visual)")
        if isinstance(corpo, str):
            corpo = self.corpo(corpo)
        g = corpo.add_geom(name=nome, group=grupo, mass=0.0, contype=0, conaffinity=0, **kw)
        self.geoms.append(nome)
        return g

    def apagar(self, nome: str) -> None:
        """Apaga um detalhe VISUAL que já existia (grupo 1–3, massa 0, sem contacto) para o substituir por um melhor —
        recusa peças com massa, com contacto ou do grupo 0 (a física e a câmara do detetor não podem mudar)."""
        g = self.geom_existente(nome)
        if g is None:
            raise KeyError(f"geom {nome!r} não existe neste build")
        if int(g.group) not in GRUPOS_PERMITIDOS or g.contype or g.conaffinity or float(g.mass) != 0.0:
            raise ValueError(f"{nome}: não é um detalhe só visual (grupo {g.group}, massa {g.mass}, contype {g.contype}) — "
                             "use `esconder` para uma peça com massa")
        self.spec.delete(g)

    def esconder(self, nome: str) -> None:
        """Torna INVISÍVEL (rgba alfa 0) uma peça com massa que um detalhe vai representar — só muda a cor: tamanho,
        posição, massa, grupo e contacto ficam (a física é a mesma). Nenhuma peça do drone com massa aparece na câmara
        do detetor (medido: segmentação da câmara `fpv` com o grupo 0), por isso o detetor não muda."""
        g = self.geom_existente(nome)
        if g is None:
            raise KeyError(f"geom {nome!r} não existe neste build")
        cor = list(g.rgba)
        if g.material:
            mat = self.obter_material(g.material)
            if mat is not None and list(g.rgba) == [0.5, 0.5, 0.5, 1.0]:   # rgba por omissão: vale a cor do material
                cor = list(mat.rgba)
        if cor[3] > 0.0:
            linha = f"{nome} " + " ".join(f"{float(v):.4f}" for v in cor)
            registo = next((t for t in self.spec.texts if t.name == TEXTO_ESCONDIDOS), None)
            if registo is None:
                self.spec.add_text(name=TEXTO_ESCONDIDOS, data=linha)
            else:
                registo.data = f"{registo.data};{linha}"
        g.material = ""
        g.rgba = [0.0, 0.0, 0.0, 0.0]

    # ------------------------------------------------------------------ âncoras
    def corpo(self, nome: str):
        """O corpo do spec com esse nome (KeyError se não existir neste build — o 3.15 devolve None em vez de lançar)."""
        b = self.spec.body(nome)
        if b is None:
            raise KeyError(f"corpo {nome!r} não existe neste build")
        return b

    def existe_corpo(self, nome: str) -> bool:
        return self.spec.body(nome) is not None

    def geom_existente(self, nome: str):
        """O geom do spec com esse nome, ou `None` (o 3.15 devolve None quando não existe)."""
        return self.spec.geom(nome)

    def pos_geom(self, nome: str) -> np.ndarray:
        """Posição (no corpo dele) de um geom que já existe — a âncora certa para pôr detalhes à volta."""
        g = self.geom_existente(nome)
        if g is None:
            raise KeyError(f"geom {nome!r} não existe neste build")
        return np.array(g.pos, dtype=float)

    def tamanho_geom(self, nome: str) -> np.ndarray:
        g = self.geom_existente(nome)
        if g is None:
            raise KeyError(f"geom {nome!r} não existe neste build")
        return np.array(g.size, dtype=float)

    @property
    def articulado(self) -> bool:
        return getattr(self.hw, "bracos", None) is not None


def escondidos_do_modelo(model: mujoco.MjModel) -> list[tuple[int, list[float]]]:
    """[(id do geom, cor original rgba)] das peças com massa que os detalhes esconderam (vazio sem detalhes)."""
    i = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_TEXT, TEXTO_ESCONDIDOS)
    if i < 0:
        return []
    adr, n = int(model.text_adr[i]), int(model.text_size[i])
    texto = bytes(model.text_data[adr:adr + n]).rstrip(b"\x00").decode("utf-8", errors="replace")
    saida = []
    for item in texto.split(";"):
        partes = item.split()
        if len(partes) != 5:
            continue
        gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, partes[0])
        if gid >= 0:
            saida.append((gid, [float(v) for v in partes[1:]]))
    return saida


def acrescentar_escondidos(scene, model: mujoco.MjModel, data: mujoco.MjData, escondidos) -> int:
    """Desenha na CENA (não no modelo — nada partilhado muda) as peças escondidas, na pose atual e com a cor original:
    é o que a câmara usa quando o grupo 3 (detalhes) está desligado. Devolve quantas acrescentou."""
    n = 0
    for gid, cor in escondidos:
        if scene.ngeom >= scene.maxgeom:
            break
        tipo = int(model.geom_type[gid])
        if tipo == int(mujoco.mjtGeom.mjGEOM_MESH):
            continue
        g = scene.geoms[scene.ngeom]
        mujoco.mjv_initGeom(g, tipo, model.geom_size[gid], data.geom_xpos[gid], data.geom_xmat[gid],
                            np.asarray(cor, dtype=np.float32))
        g.objtype = int(mujoco.mjtObj.mjOBJ_GEOM)
        g.objid = gid
        g.category = int(mujoco.mjtCatBit.mjCAT_DYNAMIC)
        scene.ngeom += 1
        n += 1
    return n


def adicionar_detalhes(spec: mujoco.MjSpec, hw, p, modulos: tuple[str, ...] | None = None) -> dict[str, int]:
    """Monta os módulos de detalhe pedidos (import tardio: um módulo só é carregado se for usado). Devolve
    {módulo: nº de peças acrescentadas}."""
    contagem: dict[str, int] = {}
    for nome in modulos_ativos(modulos):
        mod = importlib.import_module(f"{__name__}.{nome}")
        ctx = Contexto(spec=spec, hw=hw, p=p, modulo=nome)
        mod.adicionar(ctx)
        contagem[nome] = len(ctx.geoms)
    return contagem


__all__ = ["GRUPO_DETALHE", "MODULOS", "TEXTO_ESCONDIDOS", "Contexto", "acrescentar_escondidos", "adicionar_detalhes",
           "escondidos_do_modelo", "modulos_ativos"]
