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

REGISTO DAS PEÇAS (2026-10-20 — a página 3D `/pecas`, a lista de ferragens e a auditoria de realismo leem-no): cada geom
acrescentado diz a que PEÇA REAL pertence (`with ctx.peca("rpi5"):` ou `ctx.geom(..., peca=…)`), as malhas fundidas
(estrutura/fios/ferragens: um geom por corpo × material) registam o INTERVALO DE FACES de cada peça
(`ctx.registar_faixas`) — o MuJoCo 3.15 preserva o número e a ordem das faces ao compilar (medido: 191 malhas, área de
cada face igual a 1e-5) —, cada parafuso/porca/anilha/pilar fica na lista de ferragens (`ctx.ferragens`, módulo
`ferragens`), cada cabo declara de que âncora sai e a que âncora chega (`ctx.ligacao`) e cada eixo de dobradiça,
rolamento ou pino fica em `ctx.eixo`. O registo NÃO entra no modelo (nem na física, nem no MJCF): vive no dicionário
`registo_do_spec(spec)` e é lido por `lab/drone_rpi/detalhes/exportar.py` e `auditoria.py`.
"""
from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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
# texto custom com as peças ALTERNATIVAS da troca ao vivo (`Planta.trocar_pecas`): «tipo|id|ativa|dz|g1,g2,…;…» — a
# variante ativa fica com a cor do material (rgba por omissão), as outras com alfa 0 (o MuJoCo não as desenha: custo 0)
TEXTO_VARIANTES = "detalhes_variantes"
RGBA_OMISSAO = [0.5, 0.5, 0.5, 1.0]
# texto custom com os EIXOS ANIMADOS (peças que rodam mais depressa do que a junta, ex. o sem-fim a 20× o ombro):
# «nome|corpo|px,py,pz|dx,dy,dz|junta|razao|sentido;…» — o `Planta` roda os geoms `<nome>_rotor*` desse corpo a
# razão·sentido·q(junta) em torno do eixo (só visual, como as hélices)
TEXTO_ANIMACOES = "detalhes_animacoes"


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
class Registo:
    """O que os detalhes acrescentaram, por PEÇA REAL — fora do modelo (a física e o MJCF não mudam).

    geoms      nome do geom → (peça, instância) — geoms inteiros de uma peça;
    faixas     nome do geom de MALHA FUNDIDA → [(peça, instância, face0, face1)] (faces [face0, face1) dessa peça);
    ferragens  um dicionário por parafuso/porca/anilha/pilar/anel/abraçadeira (ver `ferragens.Coletor`);
    ligacoes   um dicionário por cabo: {"id", "de", "para", "corpos", "pontos" (extremos no corpo), "bitola", "peca"};
    eixos      um dicionário por eixo declarado (dobradiça, rolamento, pino, veio): {"nome", "corpo", "ponto",
               "direcao", "tipo", "junta"?} — a auditoria confere-os com as juntas do MuJoCo;
    variantes  "motor:<id>" / "bateria:<id>" → [geoms] das peças ALTERNATIVAS da troca ao vivo (alfa 0 se inativas);
    notas      livre (dados que um módulo deixa para a página ou para a auditoria)."""

    geoms: dict = field(default_factory=dict)
    faixas: dict = field(default_factory=dict)
    ferragens: list = field(default_factory=list)
    ligacoes: list = field(default_factory=list)
    eixos: list = field(default_factory=list)
    variantes: dict = field(default_factory=dict)
    notas: dict = field(default_factory=dict)
    pilha: list = field(default_factory=list)          # a peça em curso (`with ctx.peca(…)`), partilhada pelos módulos
    modulo_atual: str = ""

    def peca_do_geom(self, nome: str) -> tuple[str, int] | None:
        return self.geoms.get(nome)


# registos dos últimos specs montados (por id do spec): `exportar`/`auditoria` constroem o spec e leem o registo dele
_REGISTOS: dict[int, Registo] = {}
_MAX_REGISTOS = 16


def registo_do_spec(spec: mujoco.MjSpec) -> Registo | None:
    """O registo das peças do spec (montado com detalhes neste processo), ou None."""
    return _REGISTOS.get(id(spec))


def _guardar_registo(spec: mujoco.MjSpec, reg: Registo) -> None:
    _REGISTOS[id(spec)] = reg
    while len(_REGISTOS) > _MAX_REGISTOS:
        _REGISTOS.pop(next(iter(_REGISTOS)))


@dataclass
class Contexto:
    """O que um módulo de detalhe recebe: o spec, o hardware, a função `p` do `_montar` (posição no referencial do
    corpo `drone` já com o deslocamento do CM) e o registo do que se acrescentou."""

    spec: mujoco.MjSpec
    hw: object
    p: Callable[[float, float, float], list]
    modulo: str = ""
    geoms: list = field(default_factory=list)
    registo: Registo = field(default_factory=Registo)
    ferragens: object = None              # `ferragens.Coletor` partilhado (fecha-se no fim de `adicionar_detalhes`)

    # ------------------------------------------------------------------ registo das peças
    @contextmanager
    def peca(self, peca: str, inst: int = 0) -> Iterator[None]:
        """Tudo o que se acrescentar dentro do `with` pertence à peça `peca` (instância `inst`: o braço/rotor k)."""
        self.registo.pilha.append((str(peca), int(inst)))
        try:
            yield
        finally:
            self.registo.pilha.pop()

    @property
    def peca_atual(self) -> tuple[str, int] | None:
        return self.registo.pilha[-1] if self.registo.pilha else None

    def registar_geom(self, nome: str, peca: str | None = None, inst: int | None = None) -> None:
        """Diz a que peça pertence um geom (já existente ou acabado de criar)."""
        if peca is None:
            atual = self.peca_atual
            if atual is None:
                return
            peca, inst = atual
        self.registo.geoms[nome] = (str(peca), int(inst or 0))

    def registar_faixas(self, nome_geom: str, faixas) -> None:
        """Malha fundida `nome_geom`: [(peça, instância, face0, face1)] — as faces [face0, face1) são dessa peça."""
        self.registo.faixas[nome_geom] = [(str(p), int(i), int(a), int(b)) for p, i, a, b in faixas if b > a]

    def ligacao(self, ident: str, de: str, para: str, corpos, pontos, bitola: str = "", peca: str = "cablagem",
                inst: int = 0, **extra) -> None:
        """Declara um CABO: sai da âncora `de` e chega à `para` (nomes de geoms/sítios do modelo); `corpos` e `pontos` =
        os corpos e os pontos (no referencial de cada corpo) das duas pontas. A auditoria confere que cada ponta toca
        mesmo na sua âncora e percorre a cadeia de energia (células → … → USB-C do Raspberry Pi 5)."""
        c0, c1 = corpos
        p0, p1 = pontos
        self.registo.ligacoes.append({"id": ident, "de": de, "para": para, "corpos": [str(c0), str(c1)],
                                      "pontos": [[float(v) for v in p0], [float(v) for v in p1]], "bitola": bitola,
                                      "peca": peca, "inst": int(inst), **extra})

    def registar_variante(self, tipo: str, ident: str, geoms, ativa: bool, dz: float = 0.0, **extra) -> None:
        """Peça ALTERNATIVA da troca ao vivo (`tipo` «motor»/«bateria», `ident` o id do catálogo do painel): os `geoms`
        (já criados com o rgba por omissão — a cor do material) ficam com alfa 0 se a variante não é a do build, e o
        `Planta.trocar_pecas` mostra-os quando o painel a escolhe. `dz` = deslocamento vertical das hélices que a
        variante pede (um motor mais alto levanta a hélice: só visual). Fica no registo e num texto do modelo."""
        nomes = [str(g) for g in geoms]
        for nome in nomes:
            g = self.spec.geom(nome)
            if g is None:
                raise KeyError(f"variante {tipo}:{ident}: geom {nome!r} não existe")
            if float(g.mass) != 0.0 or g.contype or g.conaffinity:
                raise ValueError(f"variante {tipo}:{ident}: {nome} não é um detalhe só visual")
            g.rgba = list(RGBA_OMISSAO) if ativa else [0.0, 0.0, 0.0, 0.0]
        chave = f"{tipo}:{ident}"
        anterior = self.registo.variantes.get(chave)
        if anterior:
            nomes = list(anterior["geoms"]) + nomes
        self.registo.variantes[chave] = {"tipo": tipo, "id": ident, "geoms": nomes, "ativa": bool(ativa),
                                         "dz": float(dz), **extra}
        linha = f"{tipo}|{ident}|{1 if ativa else 0}|{float(dz):.6f}|{','.join(nomes)}"
        registo = next((x for x in self.spec.texts if x.name == TEXTO_VARIANTES), None)
        if registo is None:
            self.spec.add_text(name=TEXTO_VARIANTES, data=linha)
        else:
            partes = [p for p in registo.data.split(";") if p and not p.startswith(f"{tipo}|{ident}|")]
            registo.data = ";".join([*partes, linha])

    def eixo(self, nome: str, corpo: str, ponto, direcao, tipo: str, junta: str | None = None, **extra) -> None:
        """Declara um EIXO físico (dobradiça, rolamento, pino, veio) no referencial do `corpo`: a auditoria confere-o
        com a junta do MuJoCo (`junta`) — mesma reta, ±0,1 mm e ±0,1°."""
        self.registo.eixos.append({"nome": nome, "corpo": str(corpo), "ponto": [float(v) for v in ponto],
                                   "direcao": [float(v) for v in direcao], "tipo": tipo, "junta": junta, **extra})
        if junta and "razao" in extra:
            d = np.asarray(direcao, dtype=float)
            d = d / max(float(np.linalg.norm(d)), 1e-12)
            linha = (f"{nome}|{corpo}|{','.join(f'{float(v):.7f}' for v in ponto)}|{','.join(f'{float(v):.7f}' for v in d)}|"
                     f"{junta}|{float(extra['razao']):.6f}|{float(extra.get('sentido', 1.0)):.1f}")
            registo = next((x for x in self.spec.texts if x.name == TEXTO_ANIMACOES), None)
            if registo is None:
                self.spec.add_text(name=TEXTO_ANIMACOES, data=linha)
            else:
                partes = [p for p in registo.data.split(";") if p and not p.startswith(f"{nome}|")]
                registo.data = ";".join([*partes, linha])

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
    def geom(self, corpo, nome: str, grupo: int = GRUPO_DETALHE, peca: str | None = None, inst: int | None = None,
             **kw):
        """Uma peça SÓ VISUAL no corpo `corpo` (objeto do spec ou nome): massa 0, sem contacto, grupo 3 (ou 1/2).
        Fica registada na peça `peca` (ou na do `with ctx.peca(…)` em curso)."""
        if grupo not in GRUPOS_PERMITIDOS:
            raise ValueError(f"{nome}: grupo {grupo} proibido nos detalhes (permitidos {GRUPOS_PERMITIDOS})")
        for chave in ("mass", "density", "contype", "conaffinity", "group"):
            if chave in kw:
                raise ValueError(f"{nome}: `{chave}` é imposto pelo Contexto (detalhe = só visual)")
        if isinstance(corpo, str):
            corpo = self.corpo(corpo)
        g = corpo.add_geom(name=nome, group=grupo, mass=0.0, contype=0, conaffinity=0, **kw)
        self.geoms.append(nome)
        self.registar_geom(nome, peca, inst)
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


def variantes_do_modelo(model: mujoco.MjModel) -> list[dict]:
    """[{tipo, id, ativa, dz, gids}] das peças alternativas da troca ao vivo (vazio sem detalhes)."""
    i = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_TEXT, TEXTO_VARIANTES)
    if i < 0:
        return []
    adr, n = int(model.text_adr[i]), int(model.text_size[i])
    texto = bytes(model.text_data[adr:adr + n]).rstrip(b"\x00").decode("utf-8", errors="replace")
    out = []
    for item in texto.split(";"):
        partes = item.split("|")
        if len(partes) != 5:
            continue
        gids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, g) for g in partes[4].split(",") if g]
        out.append({"tipo": partes[0], "id": partes[1], "ativa": partes[2] == "1", "dz": float(partes[3]),
                    "gids": [g for g in gids if g >= 0]})
    return out


def animacoes_do_modelo(model: mujoco.MjModel) -> list[dict]:
    """[{nome, corpo, ponto, direcao, junta, razao, sentido, gids}] dos eixos animados (vazio sem detalhes): os gids são
    os geoms `<nome>_rotor*` do corpo."""
    i = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_TEXT, TEXTO_ANIMACOES)
    if i < 0:
        return []
    adr, n = int(model.text_adr[i]), int(model.text_size[i])
    texto = bytes(model.text_data[adr:adr + n]).rstrip(b"\x00").decode("utf-8", errors="replace")
    nomes = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g) or "" for g in range(model.ngeom)]
    out = []
    for item in texto.split(";"):
        p = item.split("|")
        if len(p) != 7:
            continue
        b = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, p[1])
        if b < 0:
            continue
        gids = [g for g, nm in enumerate(nomes) if nm.startswith(f"{p[0]}_rotor") and int(model.geom_bodyid[g]) == b]
        out.append({"nome": p[0], "corpo": b, "ponto": np.array([float(v) for v in p[2].split(",")]),
                    "direcao": np.array([float(v) for v in p[3].split(",")]), "junta": p[4], "razao": float(p[5]),
                    "sentido": float(p[6]), "gids": gids})
    return out


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
    """Monta os módulos de detalhe pedidos (import tardio: um módulo só é carregado se for usado) com UM registo e UM
    coletor de ferragens partilhados (as ferragens de todos os módulos fundem-se por corpo × material no fim). Devolve
    {módulo: nº de peças acrescentadas}."""
    contagem: dict[str, int] = {}
    ativos = modulos_ativos(modulos)
    if not ativos:
        return contagem
    from .ferragens import Coletor
    reg = Registo()
    fer_ctx = Contexto(spec=spec, hw=hw, p=p, modulo="ferragens", registo=reg)
    coletor = Coletor(fer_ctx)
    for nome in ativos:
        mod = importlib.import_module(f"{__name__}.{nome}")
        ctx = Contexto(spec=spec, hw=hw, p=p, modulo=nome, registo=reg, ferragens=coletor)
        reg.modulo_atual = nome
        mod.adicionar(ctx)
        reg.pilha.clear()
        contagem[nome] = len(ctx.geoms)
    reg.modulo_atual = "ferragens"
    coletor.fechar()
    contagem["ferragens"] = len(fer_ctx.geoms)
    _guardar_registo(spec, reg)
    return contagem


__all__ = ["GRUPO_DETALHE", "MODULOS", "RGBA_OMISSAO", "TEXTO_ANIMACOES", "TEXTO_ESCONDIDOS", "TEXTO_VARIANTES",
           "Contexto", "Registo", "acrescentar_escondidos", "adicionar_detalhes", "animacoes_do_modelo",
           "escondidos_do_modelo", "modulos_ativos", "registo_do_spec", "variantes_do_modelo"]
