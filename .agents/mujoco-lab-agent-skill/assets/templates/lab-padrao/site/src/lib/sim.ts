/**
 * sim.ts — TIPOS + CONFIGURAÇÃO do site do template `lab-padrao`.
 *
 * ★ É AQUI QUE SE ADAPTA O SITE A OUTRO ROBÔ: a secção «CONFIGURAÇÃO» (métricas e rótulos) é a única que
 *   precisa de mudar quando se copia o template. Nada de tamanhos fixos: os vetores (`obs`/`act`) têm o
 *   tamanho que o backend mandar e o site desenha N entradas e M saídas.
 *
 * Leitura DEFENSIVA do JSON do backend (`sim_site.py`): campo em falta ou com o tipo errado → `null`/«—»,
 * nunca um número inventado. O site mostra sempre o que o MuJoCo mediu.
 */

// ─────────────────────────────────────────────────────────────────────────── CONFIGURAÇÃO (ADAPTAR)
/** Uma curva/painel do site: chave na telemetria → rótulo, unidade, cor e casas decimais. */
export interface Metrica {
  chave: "theta" | "erro" | "omega" | "vento_vel"
  rotulo: string
  curta: string
  unidade: string
  cor: string
  casas: number
  /** Linha de referência (2 pontos, desenhada no sparkline): `true` = usa o alvo do alvo do episódio. */
  referencia?: "alvo" | "zero"
}

/**
 * As 4 curvas do painel. Ao copiar o template para outro robô: troca `chave` pelas tuas 3–4 grandezas
 * (o `sim_view.py` publica-as em `amostra()`) e ajusta rótulo/unidade/casas.
 */
export const METRICAS: Metrica[] = [
  { chave: "theta", rotulo: "θ — ângulo da haste", curta: "θ", unidade: "°", cor: "#ffa24a", casas: 2, referencia: "alvo" },
  { chave: "erro", rotulo: "erro em relação ao alvo", curta: "erro", unidade: "°", cor: "#7dd3fc", casas: 2, referencia: "zero" },
  { chave: "omega", rotulo: "θ̇ — velocidade angular", curta: "θ̇", unidade: "°/s", cor: "#c4b5fd", casas: 1, referencia: "zero" },
  { chave: "vento_vel", rotulo: "vento (perturbação) em vigor", curta: "vento", unidade: "m/s", cor: "#86efac", casas: 2 },
]

/** Rótulo de cada entrada da observação (o nº real vem da telemetria; o que faltar cai em `obs[i]`). */
export const ROTULOS_OBS: string[] = ["cos θ", "sin θ", "θ̇/10", "erro/π"]
/** Rótulo de cada saída da ação (idem: o que faltar cai em `act[i]`). */
export const ROTULOS_ACT: string[] = ["Δτ (normalizado)"]
/** Unidade física do comando publicado em `ctrl` (o backend manda o comando REAL aplicado). */
export const UNIDADE_CTRL = "N·m"
/** Rótulo do comando físico (`ctrl`). */
export const ROTULO_CTRL = "τ aplicado"
/** Nome curto do robô/experimento, usado no título. */
export const NOME_EXPERIMENTO = "{{NOME_EXPERIMENTO}}"
/** Limites do vento aceites pela API (têm de bater com o `sim_site.py`). */
export const VENTO_LIMITES = { vel: [0, 5], azimute: [0, 360], elevacao: [-90, 90] } as const
// ─────────────────────────────────────────────────────────────────────── fim da CONFIGURAÇÃO

export type EstadoEpisodio = "a_correr" | "pausado" | "episodio_terminado" | "sem_dados"

/** Uma amostra da telemetria (as chaves e a ordem do contrato do `sim_view.py`). */
export interface LinhaSim {
  t: number
  estado: EstadoEpisodio
  ep: number
  passo: number
  retorno: number
  theta: number | null
  erro: number | null
  omega: number | null
  vento_vel: number | null
  vento_azim: number | null
  obs: number[]
  act: number[]
  ctrl: number[]
  h1: number[]
  h2: number[]
}

export interface VentoEstado {
  vel: number
  azimute: number
  elevacao: number
  ativo: boolean
}

export interface RespostaSim {
  estado: EstadoEpisodio
  ep: number | null
  passo: number | null
  retorno: number | null
  vento: VentoEstado | null
  linhas: LinhaSim[]
  modelo_nome: string | null
  sim_vivo: boolean | null
  loop: boolean | null
}

export interface ResumoEstado extends Omit<RespostaSim, "linhas"> {
  contador_reiniciar: number | null
  n_linhas: number | null
  modelo_motivo: string | null
}

export interface CorpoVento {
  vel: number
  azimute: number
  elevacao: number
}

// ───────────────────────────────────────────────────────────────────────────── leitura defensiva
export function numero(bruto: unknown): number | null {
  if (typeof bruto === "number" && Number.isFinite(bruto)) return bruto
  if (typeof bruto === "string" && bruto.trim() !== "") {
    const v = Number(bruto)
    return Number.isFinite(v) ? v : null
  }
  return null
}

function vetor(bruto: unknown): number[] {
  if (!Array.isArray(bruto)) return []
  return bruto.map((v) => numero(v)).filter((v): v is number => v !== null)
}

function objeto(bruto: unknown): Record<string, unknown> {
  return bruto && typeof bruto === "object" && !Array.isArray(bruto) ? (bruto as Record<string, unknown>) : {}
}

function estado(bruto: unknown): EstadoEpisodio {
  return bruto === "a_correr" || bruto === "pausado" || bruto === "episodio_terminado" || bruto === "sem_dados"
    ? bruto
    : "sem_dados"
}

function lerVento(bruto: unknown): VentoEstado | null {
  const o = objeto(bruto)
  if (Object.keys(o).length === 0) return null
  return {
    vel: numero(o.vel) ?? 0,
    azimute: numero(o.azimute) ?? 0,
    elevacao: numero(o.elevacao) ?? 0,
    ativo: o.ativo === true,
  }
}

/** Uma linha da telemetria → `LinhaSim` (ou `null` se não tiver os campos mínimos). */
export function lerLinha(bruto: unknown): LinhaSim | null {
  const o = objeto(bruto)
  const t = numero(o.t)
  const passo = numero(o.passo)
  if (t === null || passo === null) return null
  return {
    t,
    estado: estado(o.estado),
    ep: numero(o.ep) ?? 1,
    passo,
    retorno: numero(o.retorno) ?? 0,
    theta: numero(o.theta),
    erro: numero(o.erro),
    omega: numero(o.omega),
    vento_vel: numero(o.vento_vel),
    vento_azim: numero(o.vento_azim),
    obs: vetor(o.obs),
    act: vetor(o.act),
    ctrl: vetor(o.ctrl),
    h1: vetor(o.h1),
    h2: vetor(o.h2),
  }
}

export function temAtivacoes(linha: LinhaSim | null): boolean {
  return !!linha && (linha.h1.length > 0 || linha.h2.length > 0)
}

export function lerSim(bruto: unknown): RespostaSim {
  const o = objeto(bruto)
  const linhas = Array.isArray(o.linhas) ? o.linhas.map(lerLinha).filter((l): l is LinhaSim => l !== null) : []
  return {
    estado: estado(o.estado),
    ep: numero(o.ep),
    passo: numero(o.passo),
    retorno: numero(o.retorno),
    vento: lerVento(o.vento),
    linhas,
    modelo_nome: typeof o.modelo_nome === "string" ? o.modelo_nome : null,
    sim_vivo: typeof o.sim_vivo === "boolean" ? o.sim_vivo : null,
    loop: typeof o.loop === "boolean" ? o.loop : null,
  }
}

export function lerResumo(bruto: unknown): ResumoEstado {
  const o = objeto(bruto)
  const base = lerSim(o)
  return {
    ...base,
    contador_reiniciar: numero(o.contador_reiniciar),
    n_linhas: numero(o.n_linhas),
    modelo_motivo: typeof o.modelo_motivo === "string" ? o.modelo_motivo : null,
  }
}

/** Chave única de uma amostra (o histórico acumula-se por `ep:passo`). */
export function chaveLinha(l: LinhaSim): string {
  return `${l.ep}:${l.passo}`
}

// ─────────────────────────────────────────────────────────────────────────────────── derivados
/** Alvo do episódio em graus, DEDUZIDO da telemetria (`erro = theta − alvo`): nada de constantes inventadas. */
export function alvoGraus(linha: LinhaSim | null): number | null {
  if (!linha || linha.theta === null || linha.erro === null) return null
  return ((linha.theta - linha.erro) * 180) / Math.PI
}

/** Valor de uma métrica em GRAUS (a telemetria publica `theta`/`erro`/`omega` em rad e rad/s). */
export function valorMetrica(l: LinhaSim, m: Metrica): number | null {
  switch (m.chave) {
    case "theta":
      return l.theta === null ? null : (l.theta * 180) / Math.PI
    case "erro":
      return l.erro === null ? null : (l.erro * 180) / Math.PI
    case "omega":
      return l.omega === null ? null : (l.omega * 180) / Math.PI
    case "vento_vel":
      return l.vento_vel
    default:
      return null
  }
}

export const MODELO_LEGIVEL_MAX = 34

/** `pasta/ficheiro.zip` — rótulo de painel (nunca o caminho absoluto); corta no MIOLO se for comprido. */
export function nomeModeloLegivel(caminho: string | null): string | null {
  if (!caminho) return null
  const partes = caminho.split(/[/\\]+/).filter((p) => p !== "")
  const curto = partes.slice(-2).join("/")
  if (curto.length <= MODELO_LEGIVEL_MAX) return curto
  const metade = Math.floor((MODELO_LEGIVEL_MAX - 1) / 2)
  return `${curto.slice(0, metade)}…${curto.slice(-metade)}`
}

// ─────────────────────────────────────────────────────────────────────────────────── formatação
export function fmt(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—"
  return valor.toFixed(casas)
}

export function fmtSinal(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—"
  return `${valor >= 0 ? "+" : ""}${valor.toFixed(casas)}`
}

export function fmtGraus(valor: number | null | undefined, casas = 0): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—"
  return `${valor >= 0 ? "+" : ""}${valor.toFixed(casas)}°`
}

export function fmtInteiro(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—"
  return Math.round(valor).toString()
}

export function rotuloObs(i: number): string {
  return ROTULOS_OBS[i] ?? `obs[${i}]`
}

export function rotuloAct(i: number): string {
  return ROTULOS_ACT[i] ?? `act[${i}]`
}

/** Cor de uma ativação (azul→laranja por |a|): o catálogo não tem visualizador de redes, é código novo. */
export function corAtivacao(valor: number, maximo: number): string {
  const escala = maximo > 0 ? Math.min(1, Math.abs(valor) / maximo) : 0
  const r = Math.round(70 + 185 * escala)
  const g = Math.round(130 - 40 * escala)
  const b = Math.round(220 - 150 * escala)
  return `rgb(${r} ${g} ${b})`
}

export function corTextoAtivacao(valor: number, maximo: number): string {
  const escala = maximo > 0 ? Math.min(1, Math.abs(valor) / maximo) : 0
  return escala > 0.55 ? "#0e1420" : "#e6ebf5"
}
