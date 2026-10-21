/**
 * VISOR 3D da página das peças — three.js puro (sem React dentro): constrói o drone a partir do JSON do simulador
 * (`dados.ts`) com a MESMA árvore de corpos e as MESMAS juntas do MuJoCo, por isso as dobradiças mexem-se aqui como
 * lá: um pivô por junta no ponto e no eixo da junta (`jnt_pos`, `jnt_axis` no referencial do corpo filho).
 *
 *  · rotores: as peças `helice{k}_*` e o topo do sino giram num pivô no centro do rotor (site `r{k}`), no sentido
 *    real (CW nos rotores de `giro` −1);
 *  · sem-fim do ombro: as peças `semfim{k}_rotor_*` giram num pivô no eixo do sem-fim a razão·sentido·q do ombro
 *    (20 voltas do sem-fim por volta do braço) — o eixo vem do registo (`eixos`);
 *  · biela do ombro de fuso (`bielas`, a geometria do catálogo — a mesma da física): o corpo do atuador
 *    (`ombro{k}_fuso_base*`) roda em torno do pivô B para apontar para a alavanca, o fuso (`…_veio*`) gira
 *    2π·ΔL/p sobre o seu eixo e a porca (`…_porca*`, no braço) roda em torno do pivô A — como na planta;
 *  · ferragens: uma malha COMPLETA por tipo («ISO 4762 M3×8 …», com a haste roscada que no simulador fica escondida)
 *    e uma instância por parafuso/porca/anilha (InstancedMesh por tipo × material × corpo);
 *  · escolha com o rato (raio → peça e instância), destaque, isolar uma peça, vista explodida, passos de montagem.
 *
 * MuJoCo é z para cima e o three.js y para cima: a raiz roda −90° em x e tudo o resto fica nas unidades do MuJoCo.
 */
import * as THREE from "three"
import { OrbitControls } from "three/addons/controls/OrbitControls.js"
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js"

import {
  chavePeca,
  float32,
  indices,
  type DadosPecas,
  type GeomPecas,
  type InstanciaFerragem,
  type MaterialPecas,
} from "@/paginas/pecas/dados"

export type ModoVisor = "drone" | "peca" | "ferragem"

interface MeshPeca extends THREE.Mesh {
  userData: { peca: string; inst: number; nome: string; base: THREE.Vector3 }
}

interface Ferragens3d {
  malha: THREE.InstancedMesh
  inst: InstanciaFerragem[]
  base: THREE.Matrix4[]
}

const DESTAQUE = new THREE.Color("#58d6ff")
const METAIS =
  /(aco|alu|metal|ouro|latao|cobre|estanho|inox|zincado|titanio|bronze|iman|aresta|tampa_soc|mola|fer_aluminio)/

function quatMujoco(q: readonly number[]): THREE.Quaternion {
  return new THREE.Quaternion(q[1], q[2], q[3], q[0])
}

/** Texturas procedimentais (a mesma ideia das `builtin` do MuJoCo): tecido de carbono 3K e espiras de cobre. */
function texturaCarbono(): THREE.Texture {
  // tafetá 3K: 2 × 2 mechas por período (cada mecha com 3 fios de brilho), as vizinhas a 90°
  const c = document.createElement("canvas")
  c.width = c.height = 64
  const g = c.getContext("2d")!
  for (let y = 0; y < 2; y++)
    for (let x = 0; x < 2; x++) {
      const deitada = (x + y) % 2 === 0
      g.fillStyle = deitada ? "#1a1a1d" : "#232327"
      g.fillRect(x * 32, y * 32, 32, 32)
      g.fillStyle = deitada ? "#26262a" : "#303035"
      for (let k = 0; k < 4; k++) {
        if (deitada) g.fillRect(x * 32, y * 32 + k * 8 + 2, 32, 3)
        else g.fillRect(x * 32 + k * 8 + 2, y * 32, 3, 32)
      }
    }
  const t = new THREE.CanvasTexture(c)
  t.wrapS = t.wrapT = THREE.RepeatWrapping
  t.colorSpace = THREE.SRGBColorSpace
  t.anisotropy = 4
  return t
}

function texturaEspiras(): THREE.Texture {
  const c = document.createElement("canvas")
  c.width = 4
  c.height = 64
  const g = c.getContext("2d")!
  for (let y = 0; y < 64; y += 8) {
    g.fillStyle = "#e0802f"
    g.fillRect(0, y, 4, 4)
    g.fillStyle = "#93471a"
    g.fillRect(0, y + 4, 4, 4)
  }
  const t = new THREE.CanvasTexture(c)
  t.wrapS = t.wrapT = THREE.RepeatWrapping
  t.colorSpace = THREE.SRGBColorSpace
  return t
}

export class Visor3D {
  readonly dados: DadosPecas
  private renderer: THREE.WebGLRenderer
  private cena = new THREE.Scene()
  private camara: THREE.PerspectiveCamera
  private controlos: OrbitControls
  private raiz = new THREE.Group()
  private conteudo: THREE.Object3D[] = []
  private juntas: {
    pivo: THREE.Object3D
    eixo: THREE.Vector3
    nome: string
  }[] = []
  private rotores: { pivo: THREE.Object3D; giro: number; k: number }[] = []
  private semfins: {
    pivo: THREE.Object3D
    eixo: THREE.Vector3
    fator: number
    junta: string
  }[] = []
  private bielas: {
    junta: string
    a: THREE.Vector3
    b: THREE.Vector3
    d0: THREE.Vector3
    l0: number
    passo: number
    base: THREE.Object3D
    veio: THREE.Object3D
    porca: THREE.Object3D
  }[] = []
  private malhas: MeshPeca[] = []
  private porPeca = new Map<string, MeshPeca[]>()
  private ferragens: Ferragens3d[] = []
  private centros = new Map<string, THREE.Vector3>()
  private centroDrone = new THREE.Vector3()
  private previa = new THREE.Group()
  private chao: THREE.Mesh
  private grelha: THREE.GridHelper
  private raio = new THREE.Raycaster()
  private materiaisBase = new Map<string, THREE.MeshStandardMaterial>()
  private texCarbono = texturaCarbono()
  private texEspiras = texturaEspiras()
  private relogio = new THREE.Timer()
  private anim = 0
  private sujo = true
  private destruido = false
  private ro: ResizeObserver
  private apontador = { x: 0, y: 0, t: 0 }

  // estado
  private modo: ModoVisor = "drone"
  private selecao: { peca: string; inst: number | null } | null = null
  private visiveis: Set<string> | null = null
  private destacadas: Set<string> = new Set()
  private explodir = 0
  private ombro = 0
  private cotovelo = 0
  private giroHelices = false

  aoEscolher: ((peca: string | null, inst: number) => void) | null = null

  private readonly caixa: HTMLElement

  constructor(caixa: HTMLElement, dados: DadosPecas) {
    this.caixa = caixa
    this.dados = dados
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
    })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    this.renderer.outputColorSpace = THREE.SRGBColorSpace
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.toneMappingExposure = 1.05
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFShadowMap
    this.renderer.domElement.className =
      "block size-full touch-none outline-none"
    this.renderer.domElement.setAttribute("data-testid", "visor-3d")
    caixa.appendChild(this.renderer.domElement)

    this.cena.background = new THREE.Color("#0c1016")
    const pmrem = new THREE.PMREMGenerator(this.renderer)
    this.cena.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    pmrem.dispose()
    this.cena.environmentIntensity = 0.55

    this.camara = new THREE.PerspectiveCamera(38, 1, 0.002, 60)
    this.camara.position.set(1.6, 1.1, 1.8)
    this.controlos = new OrbitControls(this.camara, this.renderer.domElement)
    this.controlos.enableDamping = true
    this.controlos.dampingFactor = 0.12
    this.controlos.screenSpacePanning = true
    this.controlos.addEventListener("change", () => (this.sujo = true))

    const hemi = new THREE.HemisphereLight("#dfe8f5", "#2a2520", 0.55)
    const sol = new THREE.DirectionalLight("#ffffff", 2.2)
    sol.position.set(2.5, 4.0, 2.0)
    sol.castShadow = true
    sol.shadow.mapSize.set(2048, 2048)
    sol.shadow.bias = -0.0004
    Object.assign(sol.shadow.camera, {
      left: -1.6,
      right: 1.6,
      top: 1.6,
      bottom: -1.6,
      near: 0.5,
      far: 12,
    })
    sol.shadow.normalBias = 0.002
    const contra = new THREE.DirectionalLight("#a8c4ff", 0.7)
    contra.position.set(-3, 1.5, -2)
    this.cena.add(hemi, sol, contra)

    this.raiz.rotation.x = -Math.PI / 2
    this.cena.add(this.raiz)
    this.previa.visible = false
    this.cena.add(this.previa)

    this.chao = new THREE.Mesh(
      new THREE.CircleGeometry(4, 64),
      new THREE.ShadowMaterial({ opacity: 0.32 })
    )
    this.chao.rotation.x = -Math.PI / 2
    this.chao.receiveShadow = true
    this.grelha = new THREE.GridHelper(4, 40, "#2b3644", "#1a222c")
    this.cena.add(this.chao, this.grelha)

    this.construir()
    this.enquadrar()
    sol.target.position.copy(this.controlos.target)
    this.cena.add(sol.target)

    this.ro = new ResizeObserver(() => this.redimensionar())
    this.ro.observe(caixa)
    this.redimensionar()
    const el = this.renderer.domElement
    el.addEventListener("pointerdown", this.aoPremir)
    el.addEventListener("pointerup", this.aoLargar)
    this.ciclo()
  }

  // ------------------------------------------------------------------ construção
  private material(
    nome: string | null,
    rgba?: readonly number[]
  ): THREE.MeshStandardMaterial {
    const chave = `${nome ?? "-"}|${rgba ? rgba.join(",") : ""}`
    const existente = this.materiaisBase.get(chave)
    if (existente) return existente
    const info: MaterialPecas | undefined = nome
      ? this.dados.materiais[nome]
      : undefined
    const cor = rgba ?? info?.rgba ?? [0.5, 0.5, 0.5, 1]
    const metal = nome ? METAIS.test(nome) : false
    const brilho = info?.shininess ?? 0.4
    const m = new THREE.MeshStandardMaterial({
      color: new THREE.Color().setRGB(
        cor[0],
        cor[1],
        cor[2],
        THREE.SRGBColorSpace
      ),
      metalness: metal ? 0.85 : 0.05,
      roughness: THREE.MathUtils.clamp(
        1 - brilho * 0.8,
        metal ? 0.18 : 0.3,
        0.95
      ),
      transparent: cor[3] < 0.999,
      opacity: cor[3],
      depthWrite: cor[3] >= 0.999,
      side: cor[3] < 0.999 ? THREE.DoubleSide : THREE.FrontSide,
    })
    if (info?.emission) {
      m.emissive = m.color.clone()
      m.emissiveIntensity = info.emission * 1.5
    }
    if (info?.textura === "carbono") {
      m.map = this.texCarbono
      m.roughness = 0.32
      m.metalness = 0.15
    } else if (info?.textura === "espiras") {
      m.map = this.texEspiras
      m.metalness = 0.75
      m.roughness = 0.35
    }
    this.materiaisBase.set(chave, m)
    return m
  }

  private geometriaMalhas = new Map<number, THREE.BufferGeometry>()

  private geometriaDaMalha(idx: number): THREE.BufferGeometry {
    const g0 = this.geometriaMalhas.get(idx)
    if (g0) return g0
    const md = this.dados.malhas[idx]
    const g = new THREE.BufferGeometry()
    g.setAttribute("position", new THREE.BufferAttribute(float32(md.v), 3))
    if (md.uv)
      g.setAttribute("uv", new THREE.BufferAttribute(float32(md.uv), 2))
    g.setIndex(new THREE.BufferAttribute(indices(md.i, md.itipo), 1))
    g.computeVertexNormals()
    this.geometriaMalhas.set(idx, g)
    return g
  }

  private geometria(gm: GeomPecas): THREE.BufferGeometry {
    const [a, b, c] = gm.size
    switch (gm.tipo) {
      case "box":
        return new THREE.BoxGeometry(2 * a, 2 * b, 2 * c)
      case "cylinder":
        return new THREE.CylinderGeometry(
          a,
          a,
          2 * b,
          Math.max(16, Math.min(48, Math.round(a * 4000)))
        ).rotateX(Math.PI / 2)
      case "capsule":
        return new THREE.CapsuleGeometry(a, 2 * b, 6, 16).rotateX(Math.PI / 2)
      case "sphere":
        return new THREE.SphereGeometry(a, 24, 16)
      case "ellipsoid":
        return new THREE.SphereGeometry(1, 24, 16).scale(a, b, c)
      case "mesh": {
        const base = this.geometriaDaMalha(gm.malha ?? 0)
        if (!gm.faces) return base
        const g = new THREE.BufferGeometry()
        for (const nome of ["position", "normal", "uv"]) {
          const at = base.getAttribute(nome)
          if (at) g.setAttribute(nome, at)
        }
        const idx = base.getIndex()!.array as Uint16Array | Uint32Array
        const sub = idx.subarray(gm.faces[0] * 3, gm.faces[1] * 3)
        g.setIndex(new THREE.BufferAttribute(sub, 1))
        // a caixa/esfera só dos vértices desta peça (o atributo é o da malha fundida inteira): enquadrar, explodir
        // e o raio do rato dependem disto
        const pos = base.getAttribute("position") as THREE.BufferAttribute
        const caixa = new THREE.Box3()
        const v = new THREE.Vector3()
        for (let i = 0; i < sub.length; i++)
          caixa.expandByPoint(v.fromBufferAttribute(pos, sub[i]))
        g.boundingBox = caixa
        g.boundingSphere = caixa.getBoundingSphere(new THREE.Sphere())
        return g
      }
    }
  }

  private construir() {
    const d = this.dados
    // corpos e juntas (pivô no ponto da junta; o conteúdo volta para trás desse ponto)
    for (const cp of d.corpos) {
      const no = new THREE.Group()
      no.name = cp.nome
      no.position.set(...cp.pos)
      no.quaternion.copy(quatMujoco(cp.quat))
      const pai = cp.pai >= 0 ? this.conteudo[cp.pai] : this.raiz
      pai.add(no)
      let alvo: THREE.Object3D = no
      if (cp.junta) {
        const pivo = new THREE.Group()
        pivo.position.set(...cp.junta.pos)
        const dentro = new THREE.Group()
        dentro.position.set(
          -cp.junta.pos[0],
          -cp.junta.pos[1],
          -cp.junta.pos[2]
        )
        pivo.add(dentro)
        no.add(pivo)
        this.juntas.push({
          pivo,
          eixo: new THREE.Vector3(...cp.junta.eixo).normalize(),
          nome: cp.junta.nome,
        })
        alvo = dentro
      }
      this.conteudo.push(alvo)
    }
    // pivôs dos rotores (centro = site r{k}, eixo = z do corpo) e dos sem-fins (eixo do registo)
    const pivoRotor = new Map<number, THREE.Object3D>()
    for (const r of d.rotores ?? []) {
      const pivo = new THREE.Group()
      pivo.position.set(...r.centro)
      this.conteudo[r.corpo].add(pivo)
      pivoRotor.set(r.k, pivo)
      this.rotores.push({ pivo, giro: r.giro, k: r.k })
    }
    const pivoSemfim = new Map<
      number,
      { pivo: THREE.Object3D; ponto: THREE.Vector3 }
    >()
    for (const e of d.eixos) {
      const mt = /^semfim(\d)$/.exec(e.nome)
      if (!mt || e.razao === undefined || !e.junta) continue
      const corpo = d.corpos.findIndex((c) => c.nome === e.corpo)
      if (corpo < 0) continue
      const pivo = new THREE.Group()
      pivo.position.set(...e.ponto)
      this.conteudo[corpo].add(pivo)
      const k = Number(mt[1])
      pivoSemfim.set(k, { pivo, ponto: new THREE.Vector3(...e.ponto) })
      this.semfins.push({
        pivo,
        eixo: new THREE.Vector3(...e.direcao).normalize(),
        fator: e.razao * (e.sentido ?? 1),
        junta: e.junta,
      })
    }
    // bielas dos ombros de fuso: pivô B no corpo do drone (com o fuso num pivô filho) e pivô A no braço
    const pivoBiela = new Map<
      string,
      { pivo: THREE.Object3D; ponto: THREE.Vector3 }
    >()
    for (const bl of d.bielas ?? []) {
      if (bl.corpo_braco < 0) continue
      const a = new THREE.Vector3(...bl.a)
      const b = new THREE.Vector3(...bl.b)
      const pontoB = new THREE.Vector3(...bl.h).add(b)
      const base = new THREE.Group()
      base.position.copy(pontoB)
      this.conteudo[bl.corpo_base].add(base)
      const veio = new THREE.Group()
      base.add(veio)
      const porca = new THREE.Group()
      porca.position.copy(a)
      this.conteudo[bl.corpo_braco].add(porca)
      const d0 = a.clone().sub(b)
      const l0 = d0.length()
      d0.normalize()
      pivoBiela.set(`${bl.k}|base`, { pivo: base, ponto: pontoB })
      pivoBiela.set(`${bl.k}|veio`, { pivo: veio, ponto: pontoB })
      pivoBiela.set(`${bl.k}|porca`, { pivo: porca, ponto: a })
      this.bielas.push({
        junta: bl.junta,
        a,
        b,
        d0,
        l0,
        passo: bl.passo,
        base,
        veio,
        porca,
      })
    }
    // geoms
    for (const gm of d.geoms) {
      const geo = this.geometria(gm)
      const mat = this.material(gm.material, gm.rgba).clone()
      mat.userData = {
        opacidade: mat.opacity,
        transparente: mat.transparent,
        profundidade: mat.depthWrite,
        emissivo: mat.emissive.clone(),
        intensidade: mat.emissiveIntensity,
      }
      const mesh = new THREE.Mesh(geo, mat) as unknown as MeshPeca
      mesh.castShadow = mat.opacity > 0.5
      mesh.receiveShadow = true
      let pai = this.conteudo[gm.corpo]
      const pos = new THREE.Vector3(...gm.pos)
      if (gm.anim?.tipo === "rotor" && pivoRotor.has(gm.anim.k)) {
        const pv = pivoRotor.get(gm.anim.k)!
        pai = pv
        pos.sub(pv.position)
      } else if (gm.anim?.tipo === "semfim" && pivoSemfim.has(gm.anim.k)) {
        const s = pivoSemfim.get(gm.anim.k)!
        pai = s.pivo
        pos.sub(s.ponto)
      } else if (
        gm.anim?.tipo === "biela" &&
        pivoBiela.has(`${gm.anim.k}|${gm.anim.papel}`)
      ) {
        const s = pivoBiela.get(`${gm.anim.k}|${gm.anim.papel}`)!
        pai = s.pivo
        pos.sub(s.ponto)
      }
      mesh.position.copy(pos)
      mesh.quaternion.copy(quatMujoco(gm.quat))
      mesh.userData = {
        peca: gm.peca,
        inst: gm.inst,
        nome: gm.nome,
        base: pos.clone(),
      }
      pai.add(mesh)
      this.malhas.push(mesh)
      const ch = chavePeca(gm.peca, gm.inst)
      if (!this.porPeca.has(ch)) this.porPeca.set(ch, [])
      this.porPeca.get(ch)!.push(mesh)
    }
    // ferragens instanciadas (tipo × material × corpo)
    const geoTipo = new Map<
      string,
      { geo: THREE.BufferGeometry; material: string }[]
    >()
    for (const [ch, t] of Object.entries(d.ferragens.tipos)) {
      geoTipo.set(
        ch,
        t.malhas.map((mf) => {
          const g = new THREE.BufferGeometry()
          g.setAttribute(
            "position",
            new THREE.BufferAttribute(float32(mf.v), 3)
          )
          g.setIndex(new THREE.BufferAttribute(indices(mf.i, mf.itipo), 1))
          g.computeVertexNormals()
          return { geo: g, material: mf.material }
        })
      )
    }
    const grupos = new Map<string, InstanciaFerragem[]>()
    for (const it of d.ferragens.instancias) {
      if (it.desenhada === false) continue // já faz parte da malha da peça (ex.: gira com o sem-fim ou a hélice)
      const ch = `${it.tipo}|${it.corpo}`
      if (!grupos.has(ch)) grupos.set(ch, [])
      grupos.get(ch)!.push(it)
    }
    for (const [ch, lista] of grupos) {
      const [tipo, corpoStr] = ch.split("|")
      for (const parte of geoTipo.get(tipo) ?? []) {
        const mat = this.material(parte.material).clone()
        const im = new THREE.InstancedMesh(parte.geo, mat, lista.length)
        const base: THREE.Matrix4[] = []
        lista.forEach((it, i) => {
          const mtx = new THREE.Matrix4().compose(
            new THREE.Vector3(...it.pos),
            quatMujoco(it.quat),
            new THREE.Vector3(1, 1, 1)
          )
          im.setMatrixAt(i, mtx)
          im.setColorAt(i, new THREE.Color(1, 1, 1))
          base.push(mtx)
        })
        im.castShadow = true
        im.receiveShadow = true
        im.userData = { ferragem: tipo }
        this.conteudo[Number(corpoStr)].add(im)
        this.ferragens.push({ malha: im, inst: lista, base })
      }
    }
    this.atualizarCentros()
  }

  /** Centros (no referencial do drone, juntas a 0) de cada peça × instância — a direção da vista explodida. */
  private atualizarCentros() {
    this.raiz.updateMatrixWorld(true)
    const inv = new THREE.Matrix4().copy(this.raiz.matrixWorld).invert()
    const tudo = new THREE.Box3()
    for (const [ch, lista] of this.porPeca) {
      const caixa = new THREE.Box3()
      for (const m of lista) caixa.expandByObject(m)
      if (caixa.isEmpty()) continue
      tudo.union(caixa)
      this.centros.set(
        ch,
        caixa.getCenter(new THREE.Vector3()).applyMatrix4(inv)
      )
    }
    this.centroDrone.copy(tudo.getCenter(new THREE.Vector3()).applyMatrix4(inv))
    const fundo = tudo.min.y
    this.chao.position.y = fundo - 0.0005
    this.grelha.position.y = fundo - 0.0003
  }

  // ------------------------------------------------------------------ ciclo e câmara
  private redimensionar() {
    const w = Math.max(1, this.caixa.clientWidth)
    const h = Math.max(1, this.caixa.clientHeight)
    this.renderer.setSize(w, h, false)
    this.camara.aspect = w / h
    this.camara.updateProjectionMatrix()
    this.sujo = true
  }

  private ciclo = (agora?: number) => {
    if (this.destruido) return
    this.anim = requestAnimationFrame(this.ciclo)
    this.relogio.update(agora)
    const dt = Math.min(this.relogio.getDelta(), 0.05)
    if (this.giroHelices) {
      for (const r of this.rotores)
        r.pivo.rotateZ(r.giro * 2 * Math.PI * 3.2 * dt)
      this.sujo = true
    }
    if (this.controlos.update()) this.sujo = true
    if (this.sujo) {
      this.renderer.render(this.cena, this.camara)
      this.sujo = false
    }
  }

  /** Enquadra o que está visível (ou uma caixa dada). */
  enquadrar(caixa?: THREE.Box3) {
    this.cena.updateMatrixWorld(true)
    const b = caixa ?? new THREE.Box3()
    if (!caixa) {
      if (this.modo === "ferragem") b.expandByObject(this.previa)
      else
        for (const m of this.malhas)
          if (m.visible && (m.material as THREE.Material).opacity > 0.5)
            b.expandByObject(m)
      if (b.isEmpty()) for (const m of this.malhas) b.expandByObject(m)
    }
    if (b.isEmpty()) return
    const c = b.getCenter(new THREE.Vector3())
    const raio = Math.max(b.getSize(new THREE.Vector3()).length() * 0.5, 0.004)
    const dist =
      (raio / Math.sin(THREE.MathUtils.degToRad(this.camara.fov * 0.5))) * 1.05
    const dir = this.camara.position
      .clone()
      .sub(this.controlos.target)
      .normalize()
    if (dir.lengthSq() < 0.5) dir.set(0.6, 0.45, 0.66).normalize()
    this.controlos.target.copy(c)
    this.camara.position.copy(c.clone().addScaledVector(dir, dist))
    this.camara.near = Math.max(dist / 500, 0.0005)
    this.camara.far = dist * 40
    this.camara.updateProjectionMatrix()
    this.sujo = true
  }

  // ------------------------------------------------------------------ escolha com o rato
  private aoPremir = (e: PointerEvent) => {
    this.apontador = { x: e.clientX, y: e.clientY, t: performance.now() }
  }

  private aoLargar = (e: PointerEvent) => {
    const mov = Math.hypot(
      e.clientX - this.apontador.x,
      e.clientY - this.apontador.y
    )
    if (mov > 5 || performance.now() - this.apontador.t > 600) return // foi orbitar, não escolher
    const r = this.renderer.domElement.getBoundingClientRect()
    const ndc = new THREE.Vector2(
      ((e.clientX - r.left) / r.width) * 2 - 1,
      -((e.clientY - r.top) / r.height) * 2 + 1
    )
    this.raio.setFromCamera(ndc, this.camara)
    const alvos: THREE.Object3D[] = [
      ...this.malhas.filter((m) => m.visible),
      ...this.ferragens.map((f) => f.malha),
    ]
    for (const hit of this.raio.intersectObjects(alvos, false)) {
      const obj = hit.object
      if (obj instanceof THREE.InstancedMesh) {
        const f = this.ferragens.find((x) => x.malha === obj)
        const it =
          f && hit.instanceId !== undefined ? f.inst[hit.instanceId] : undefined
        if (!it || !this.instanciaVisivel(it)) continue
        this.aoEscolher?.(it.peca, it.inst)
        return
      }
      const m = obj as MeshPeca
      if ((m.material as THREE.Material).opacity < 0.3) continue
      this.aoEscolher?.(m.userData.peca, m.userData.inst)
      return
    }
    this.aoEscolher?.(null, 0)
  }

  // ------------------------------------------------------------------ estado → cena
  private visivel(peca: string, inst: number): boolean {
    if (this.modo === "ferragem") return false
    if (this.modo === "peca" && this.selecao) {
      return (
        peca === this.selecao.peca &&
        (this.selecao.inst === null || inst === this.selecao.inst)
      )
    }
    if (this.visiveis) return this.visiveis.has(peca)
    return true
  }

  private instanciaVisivel(it: InstanciaFerragem): boolean {
    return this.visivel(it.peca, it.inst)
  }

  private aplicar() {
    const temSel = this.selecao !== null && this.modo === "drone"
    // offsets da vista explodida, no referencial do pai de cada malha
    this.raiz.updateMatrixWorld(true)
    const off = (
      peca: string,
      inst: number,
      pai: THREE.Object3D
    ): THREE.Vector3 => {
      if (this.explodir <= 0) return new THREE.Vector3()
      const c = this.centros.get(chavePeca(peca, inst))
      if (!c) return new THREE.Vector3()
      const v = c.clone().sub(this.centroDrone)
      v.z *= 1.8
      v.multiplyScalar(this.explodir * 1.4)
      // drone → mundo → pai
      const w = v.applyMatrix3(
        new THREE.Matrix3().setFromMatrix4(this.raiz.matrixWorld)
      )
      const inv = new THREE.Matrix3().setFromMatrix4(pai.matrixWorld).invert()
      return w.applyMatrix3(inv)
    }
    for (const m of this.malhas) {
      const { peca, inst, base } = m.userData
      const vis = this.visivel(peca, inst)
      m.visible = vis
      const mat = m.material as THREE.MeshStandardMaterial
      const ud = mat.userData as {
        opacidade: number
        transparente: boolean
        profundidade: boolean
        emissivo: THREE.Color
        intensidade: number
      }
      const destacada =
        this.destacadas.has(peca) ||
        (temSel &&
          this.selecao!.peca === peca &&
          (this.selecao!.inst === null || this.selecao!.inst === inst))
      const fantasma = temSel && !destacada
      mat.opacity = fantasma ? Math.min(ud.opacidade, 0.13) : ud.opacidade
      mat.transparent = fantasma || ud.transparente
      mat.depthWrite = !fantasma && ud.profundidade
      mat.emissive.copy(destacada ? DESTAQUE : ud.emissivo)
      mat.emissiveIntensity = destacada ? 0.32 : ud.intensidade
      m.castShadow = !fantasma && ud.opacidade > 0.5
      if (vis && m.parent) m.position.copy(base).add(off(peca, inst, m.parent))
      else m.position.copy(base)
    }
    const zero = new THREE.Matrix4().makeScale(0, 0, 0)
    const branco = new THREE.Color(1, 1, 1)
    const realce = new THREE.Color(0.55, 1.35, 1.75)
    const apagado = new THREE.Color(0.22, 0.22, 0.24)
    for (const f of this.ferragens) {
      const pai = f.malha.parent!
      f.inst.forEach((it, i) => {
        const vis = this.instanciaVisivel(it)
        if (!vis) {
          f.malha.setMatrixAt(i, zero)
          return
        }
        const o = off(it.peca, it.inst, pai)
        const mtx = f.base[i].clone()
        mtx.elements[12] += o.x
        mtx.elements[13] += o.y
        mtx.elements[14] += o.z
        f.malha.setMatrixAt(i, mtx)
        const destacada =
          this.destacadas.has(it.peca) ||
          (temSel &&
            this.selecao!.peca === it.peca &&
            (this.selecao!.inst === null || this.selecao!.inst === it.inst))
        f.malha.setColorAt(i, destacada ? realce : temSel ? apagado : branco)
      })
      f.malha.instanceMatrix.needsUpdate = true
      if (f.malha.instanceColor) f.malha.instanceColor.needsUpdate = true
      f.malha.computeBoundingSphere()
    }
    this.previa.visible = this.modo === "ferragem"
    this.sujo = true
  }

  // ------------------------------------------------------------------ API
  selecionar(peca: string | null, inst: number | null = null) {
    this.selecao = peca ? { peca, inst } : null
    if (!peca && this.modo === "peca") this.modo = "drone"
    this.aplicar()
  }

  definirModo(modo: ModoVisor) {
    this.modo = modo
    this.aplicar()
    this.enquadrar()
  }

  definirExplodir(f: number) {
    this.explodir = THREE.MathUtils.clamp(f, 0, 1)
    if (this.explodir > 0) this.definirJuntas(0, 0, false)
    this.aplicar()
  }

  /** Ângulos (graus) de TODOS os ombros e cotovelos — como no MuJoCo; o sem-fim roda a razão·sentido·q do ombro. */
  definirJuntas(ombroGraus: number, cotoveloGraus: number, aplicar = true) {
    this.ombro = ombroGraus
    this.cotovelo = cotoveloGraus
    const q = new Map<string, number>()
    for (const j of this.juntas) {
      const th = THREE.MathUtils.degToRad(
        j.nome.startsWith("ombro")
          ? ombroGraus
          : j.nome.startsWith("cotovelo")
            ? cotoveloGraus
            : 0
      )
      j.pivo.quaternion.setFromAxisAngle(j.eixo, th)
      q.set(j.nome, th)
    }
    for (const s of this.semfins)
      s.pivo.quaternion.setFromAxisAngle(
        s.eixo,
        s.fator * (q.get(s.junta) ?? 0)
      )
    const eixoY = new THREE.Vector3(0, 1, 0)
    for (const bl of this.bielas) {
      const qy = new THREE.Quaternion().setFromAxisAngle(
        eixoY,
        q.get(bl.junta) ?? 0
      )
      const dv = bl.a.clone().applyQuaternion(qy).sub(bl.b)
      const comp = dv.length()
      const qb = new THREE.Quaternion().setFromUnitVectors(
        bl.d0,
        dv.normalize()
      )
      bl.base.quaternion.copy(qb)
      bl.veio.quaternion.setFromAxisAngle(
        bl.d0,
        (2 * Math.PI * (comp - bl.l0)) / bl.passo
      )
      bl.porca.quaternion.copy(qy.clone().invert().multiply(qb))
    }
    if (aplicar) this.aplicar()
    this.sujo = true
  }

  get juntasAtuais() {
    return { ombro: this.ombro, cotovelo: this.cotovelo }
  }

  definirGiroHelices(on: boolean) {
    this.giroHelices = on
    this.sujo = true
  }

  /** Só as peças `visiveis` (null = todas) e com destaque nas `destacadas` (os passos de montagem). */
  definirVisiveis(
    visiveis: Set<string> | null,
    destacadas: Set<string> = new Set()
  ) {
    this.visiveis = visiveis
    this.destacadas = destacadas
    this.aplicar()
  }

  /** Mostra uma ferragem INTEIRA sozinha (pré-visualização do tipo). */
  mostrarFerragem(tipo: string) {
    this.previa.clear()
    const t = this.dados.ferragens.tipos[tipo]
    if (!t) return
    const g = new THREE.Group()
    for (const mf of t.malhas) {
      const geo = new THREE.BufferGeometry()
      geo.setAttribute("position", new THREE.BufferAttribute(float32(mf.v), 3))
      geo.setIndex(new THREE.BufferAttribute(indices(mf.i, mf.itipo), 1))
      geo.computeVertexNormals()
      const m = new THREE.Mesh(geo, this.material(mf.material))
      m.castShadow = true
      g.add(m)
    }
    // de pé e assente no chão: parafusos e pernos de cabeça para cima (a haste vai para +z no referencial deles: x +90°
    // leva +z para −y); porcas, anilhas, pilares e anéis com a face de apoio em baixo (+z para cima: x −90°)
    g.rotation.x =
      t.tipo === "parafuso" || t.tipo === "perno" ? Math.PI / 2 : -Math.PI / 2
    this.previa.add(g)
    this.previa.updateMatrixWorld(true)
    const caixa = new THREE.Box3().setFromObject(g)
    g.position.y += this.chao.position.y + 0.0004 - caixa.min.y
    this.modo = "ferragem"
    this.aplicar()
    this.enquadrar()
  }

  /** Destaca todas as instâncias de um tipo de ferragem no drone. */
  destacarFerragem(tipo: string | null) {
    const branco = new THREE.Color(1, 1, 1)
    const realce = new THREE.Color(0.55, 1.35, 1.75)
    for (const f of this.ferragens) {
      const ch = (f.malha.userData as { ferragem: string }).ferragem
      f.inst.forEach((_it, i) =>
        f.malha.setColorAt(i, tipo && ch === tipo ? realce : branco)
      )
      if (f.malha.instanceColor) f.malha.instanceColor.needsUpdate = true
    }
    this.sujo = true
  }

  destruir() {
    this.destruido = true
    cancelAnimationFrame(this.anim)
    this.ro.disconnect()
    this.controlos.dispose()
    const el = this.renderer.domElement
    el.removeEventListener("pointerdown", this.aoPremir)
    el.removeEventListener("pointerup", this.aoLargar)
    this.cena.traverse((o) => {
      const m = o as THREE.Mesh
      if (m.geometry) m.geometry.dispose()
      const mat = m.material as THREE.Material | THREE.Material[] | undefined
      if (Array.isArray(mat)) mat.forEach((x) => x.dispose())
      else mat?.dispose()
    })
    this.renderer.dispose()
    el.remove()
  }
}
