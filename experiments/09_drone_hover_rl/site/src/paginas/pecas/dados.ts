/**
 * Dados da página das PEÇAS 3D — o JSON de `GET /api/pecas3d` (gerado por `lab/drone_rpi/detalhes/exportar.py` a
 * partir do MESMO modelo que o simulador compila). Metros, quaternions do MuJoCo `[w, x, y, z]`, eixo z para cima;
 * vetores binários em base64 little-endian (float32 / uint16 | uint32).
 */

export interface MaterialPecas {
  rgba: [number, number, number, number]
  specular: number
  shininess: number
  reflectance: number
  emission: number
  textura: string | null
}

export interface MalhaPecas {
  nv: number
  nf: number
  v: string
  i: string
  itipo: "u16" | "u32"
  uv?: string
}

export interface JuntaPecas {
  nome: string
  eixo: [number, number, number]
  pos: [number, number, number]
  limites_graus: [number, number] | null
}

export interface CorpoPecas {
  nome: string
  pai: number
  pos: [number, number, number]
  quat: [number, number, number, number]
  junta: JuntaPecas | null
}

export interface AnimGeom {
  tipo: "rotor" | "semfim" | "biela"
  k: number
  /** na biela do ombro de fuso: o corpo do atuador, o fuso (gira) ou a porca (vai com o braço) */
  papel?: "base" | "veio" | "porca"
}

/** A biela de um ombro de fuso: A(q) = R_y(q)·a, B = h + b (corpo do drone), L = |R_y(q)·a − b|. */
export interface BielaPecas {
  k: number
  junta: string
  corpo_base: number
  corpo_braco: number
  h: [number, number, number]
  a: [number, number, number]
  b: [number, number, number]
  passo: number
}

export interface GeomPecas {
  corpo: number
  nome: string
  tipo: "box" | "cylinder" | "capsule" | "sphere" | "ellipsoid" | "mesh"
  size: [number, number, number]
  pos: [number, number, number]
  quat: [number, number, number, number]
  material: string | null
  rgba?: [number, number, number, number]
  grupo: number
  malha?: number
  faces?: [number, number]
  peca: string
  inst: number
  anim?: AnimGeom
}

export interface ItemCusto {
  tipo: "comprada" | "impressa" | "ferragem" | "cabo"
  fonte: string
  unitario_usd: number
  qtd: number
  total_usd: number
}

export interface CustoPeca {
  itens: ItemCusto[]
  total_usd: number
  total_brl: number
}

export interface FichaPeca {
  nome: string
  categoria: string
  resumo: string
  como_funciona: string
  /** PORQUE esta peça é necessária para o projeto (em detalhe) */
  porque?: string
  specs: [string, string][]
  fontes: string[]
  instancias?: number[]
  quantidade?: number
  massa_medida_g?: number
  impressa?: boolean
  custo?: CustoPeca | null
}

export interface PecaImpressa {
  peca: string
  inst: number
  nome: string
  /** quaternion [w, x, y, z]: do referencial do corpo para a posição de impressão (face de apoio para −z) */
  orientacao: [number, number, number, number]
  nota: string
  massa_g: number
  volume_cm3: number
  impresso_cm3: number
  tempo_h: number
  aberta: boolean
  custo_usd: number
  /** o STL desta peça no ZIP (as cópias iguais partilham o mesmo) */
  arquivo?: string
  dims_mm?: [number, number, number]
  cabe_mesa?: boolean
  fechada?: boolean
  copias?: number
  instancias_iguais?: number[]
  orientacao_auto?: boolean
  triangulos?: number
}

export interface Custos {
  moeda: string
  cambio_usd_brl: number
  data: string
  total_usd: number
  total_brl: number
  por_categoria: Record<string, number>
  por_peca: Record<string, CustoPeca>
  filamento_usd_kg: number
  impressas_g: number
  impressas_h: number
}

export interface MalhaFerragem {
  material: string
  nv: number
  nf: number
  v: string
  i: string
  itipo: "u16" | "u32"
}

export interface TipoFerragem {
  descricao: string
  tipo: string
  norma?: string
  rosca?: string
  comp_mm?: number | null
  material?: string
  binario_nm?: number | null
  malhas: MalhaFerragem[]
  qtd: number
}

export interface InstanciaFerragem {
  tipo: string
  corpo: number
  pos: [number, number, number]
  quat: [number, number, number, number]
  peca: string
  inst: number
  modulo: string
  /** false = a ferragem já está desenhada dentro da malha da peça (não se instancia por cima; conta na lista) */
  desenhada?: boolean
}

export interface PassoMontagem {
  id: string
  n: number
  titulo: string
  texto: string
  pecas: string[]
  ferragens: {
    tipo: string
    qtd: number
    descricao: string
    binario_nm: number | null
  }[]
}

export interface EixoPecas {
  nome: string
  corpo: string
  ponto: [number, number, number]
  direcao: [number, number, number]
  tipo: string
  junta: string | null
  razao?: number
  sentido?: number
}

export interface RotorPecas {
  k: number
  giro: number
  corpo: number
  centro: [number, number, number]
}

export interface LigacaoPecas {
  id: string
  de: string
  para: string
  bitola: string
  peca: string
  inst: number
}

export interface DadosPecas {
  versao: number
  build: string
  massa_total_g: number
  gerado: string
  materiais: Record<string, MaterialPecas>
  malhas: MalhaPecas[]
  corpos: CorpoPecas[]
  geoms: GeomPecas[]
  pecas: Record<string, FichaPeca>
  categorias: { id: string; nome: string }[]
  ferragens: {
    tipos: Record<string, TipoFerragem>
    instancias: InstanciaFerragem[]
  }
  ligacoes: LigacaoPecas[]
  eixos: EixoPecas[]
  rotores?: RotorPecas[]
  impressas?: Record<string, PecaImpressa>
  impressao?: {
    mesa_mm: [number, number, number]
    definicoes: string
    zip: string
  }
  bielas?: BielaPecas[]
  custos?: Custos
  massas_parametros?: {
    rho_abs_g_cm3: number
    parede_mm: number
    enchimento: number
    taxa_cm3_h: number
  }
  passos: PassoMontagem[]
  estatisticas: {
    geoms: number
    malhas: number
    triangulos: number
    ferragens: number
    pecas: number
    sem_peca: string[]
    segundos: number
  }
}

/** Base da API: a mesma origem (o `sim_site.py` serve o site e a API) ou `?api=` / `window.__SIM_API_BASE__`. */
function baseApi(): string {
  const qs = new URLSearchParams(window.location.search).get("api")
  const global = (window as unknown as { __SIM_API_BASE__?: string })
    .__SIM_API_BASE__
  return (qs ?? global ?? "").replace(/\/$/, "")
}

/** URL de um STL das peças impressas (ou do ZIP com todos, sem `arquivo`) — servido pelo `sim_site.py`. */
export function urlStl(build: string, arquivo?: string): string {
  const q = `build=${encodeURIComponent(build)}`
  return arquivo
    ? `${baseApi()}/api/pecas3d/stl?${q}&arquivo=${encodeURIComponent(arquivo)}`
    : `${baseApi()}/api/pecas3d/stl.zip?${q}`
}

/** Lê as peças do build que o servidor voa (ou o `?build=` da página). */
export async function carregarPecas(sinal?: AbortSignal): Promise<DadosPecas> {
  const build = new URLSearchParams(window.location.search).get("build")
  const url = `${baseApi()}/api/pecas3d${build ? `?build=${encodeURIComponent(build)}` : ""}`
  const resp = await fetch(url, { signal: sinal })
  if (!resp.ok) {
    let motivo = `${resp.status} ${resp.statusText}`
    try {
      const corpo = (await resp.json()) as { erro?: string }
      if (corpo.erro) motivo = corpo.erro
    } catch {
      /* corpo sem JSON: fica o estado HTTP */
    }
    throw new Error(motivo)
  }
  return (await resp.json()) as DadosPecas
}

function bytes(b64: string): Uint8Array {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

export function float32(b64: string): Float32Array {
  const b = bytes(b64)
  return new Float32Array(b.buffer, b.byteOffset, b.byteLength / 4)
}

export function indices(
  b64: string,
  tipo: "u16" | "u32"
): Uint16Array | Uint32Array {
  const b = bytes(b64)
  return tipo === "u16"
    ? new Uint16Array(b.buffer, b.byteOffset, b.byteLength / 2)
    : new Uint32Array(b.buffer, b.byteOffset, b.byteLength / 4)
}

/** Chave de uma instância de peça («motor#2»). */
export const chavePeca = (peca: string, inst: number) => `${peca}#${inst}`

/** Número com vírgula decimal (pt-PT). */
export function num(v: number | null | undefined, casas = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—"
  return v.toLocaleString("pt-PT", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  })
}

/** Reais e dólares, lado a lado. */
export function preco(usd: number | null | undefined, cambio: number): string {
  if (usd === null || usd === undefined) return "—"
  const brl = usd * cambio
  return `R$ ${brl.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} · US$ ${usd.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
