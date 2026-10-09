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
  /** Vetor do vento EM VIGOR `[vx,vy,vz]` (base + dinâmica), ou `null` se a linha não o trouxer. */
  vento_vec: [number, number, number] | null
  /** Modo dinâmico que produziu esta linha (`"nenhum"`/`"rajadas"`/…), ou `null` se não vier. */
  vento_modo: ModoVentoDinamico | null
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
  /** Vetor em vigor anunciado pelo backend (m/s, mundo); `null` quando só há a forma polar. */
  vec: [number, number, number] | null
  /** Modo dinâmico em vigor anunciado pela API (`vento.modo`); `null` se não vier. */
  modo: ModoVentoDinamico | null
}

export interface RespostaSim {
  estado: EstadoEpisodio
  ep: number | null
  passo: number | null
  retorno: number | null
  vento: VentoEstado | null
  /** Modo/params pedidos ao backend (`POST /api/vento-dinamico`); nunca reinicia o episódio. */
  ventoDinamico: VentoDinamico
  /** Painel do computador de bordo (Raspberry Pi 5); `null` quando o backend ainda não o publica. */
  rpi5: Rpi5 | null
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

// ─────────────────────────────────────────────────────────────── configuração do projeto (★ ADAPTAR)
// Está em `config.ts` para o front poder ser reutilizado sem tocar nos componentes: aqui só se re-exporta.
export * from "./config"
import { ROTULOS_ACT, ROTULOS_OBS, type Metrica } from "./config"

// ───────────────────────────────────────────────────────────────── vento dinâmico (r11, ao vivo)
/**
 * Modos do vento dinâmico aceites por `POST /api/vento-dinamico`.
 *
 * `nenhum` desliga; `rajadas`/`dryden` são CONTÍNUOS (ficam ligados até se desligar); `frente` é um degrau
 * imediato que substitui o vento base; `rajada_agora` é uma rajada única dirigida.
 */
export type ModoVentoDinamico = "nenhum" | "rajadas" | "frente" | "dryden" | "rajada_agora"

/** Defaults REAIS do ambiente (`env.valida_vento_dinamico`) — nunca inventados aqui. */
export const PARAMS_DINAMICOS_PADRAO = {
  rajadas: { p: 0.02, duracao: 10, u_max: 3 },
  dryden: { sigma: 0.5, L: 10, v_min: 1 },
  rajada_agora: { duracao: 25 },
} as const

/** Modos contínuos mostrados no seletor (os instantâneos têm botão próprio). */
export const MODOS_CONTINUOS = ["nenhum", "rajadas", "dryden"] as const
export type ModoContinuo = (typeof MODOS_CONTINUOS)[number]

/** Rótulos curtos dos modos (PT-PT) para selos e avisos. */
export const ROTULO_MODO: Record<ModoVentoDinamico, string> = {
  nenhum: "sem dinâmica",
  rajadas: "rajadas contínuas",
  frente: "frente (degrau)",
  dryden: "turbulência Dryden",
  rajada_agora: "rajada única",
}

export interface VentoDinamico {
  modo: ModoVentoDinamico
  /** Parâmetros em vigor, já só com números finitos (`{}` quando não vêm). */
  params: Record<string, number>
  ativo: boolean
}

/** Estado de repouso do vento dinâmico (o mesmo que `{"modo":"nenhum","ativo":false}`). */
export const VENTO_DINAMICO_PARADO: VentoDinamico = { modo: "nenhum", params: {}, ativo: false }

/** Corpo de `POST /api/vento-dinamico` (contrato: 200/400, sem reiniciar o episódio). */
export interface CorpoVentoDinamico {
  modo: ModoVentoDinamico
  params?: Record<string, number>
  ativo?: boolean
}

function lerModo(bruto: unknown): ModoVentoDinamico | null {
  return typeof bruto === "string" && bruto in ROTULO_MODO ? (bruto as ModoVentoDinamico) : null
}

/** `vento_dinamico` do backend → estado tolerante (modo desconhecido conta como `nenhum`). */
export function lerVentoDinamico(bruto: unknown): VentoDinamico {
  const o = objeto(bruto)
  const params: Record<string, number> = {}
  for (const [chave, valor] of Object.entries(objeto(o.params))) {
    const n = numero(valor)
    if (n !== null) params[chave] = n
  }
  return { modo: lerModo(o.modo) ?? "nenhum", params, ativo: o.ativo === true }
}

/** Parâmetros em vigor → texto curto (`p=0,02 · duracao=10 · u_max=3`), ou "—". */
export function fmtParams(params: Record<string, number>): string {
  const entradas = Object.entries(params).filter(([chave]) => chave !== "modo")
  if (entradas.length === 0) return "—"
  return entradas.map(([chave, valor]) => `${chave}=${fmt(valor, valor === Math.round(valor) ? 0 : 2)}`).join(" · ")
}

// ─────────────────────────────────────────────────────────────────────── vetor do vento
export interface DirecaoVento {
  /** Norma do vetor (m/s). */
  modulo: number
  /** Azimute em graus [0,360): 0° = +x, 90° = +y (anti-horário). */
  azimute: number
  /** Elevação em graus [−90,90]: positivo = vento a subir. */
  elevacao: number
  /** Componente horizontal ‖[vx,vy]‖ (m/s) — o que a rosa dos ventos desenha. */
  horizontal: number
}

/** Vento polar → vetor cartesiano do mundo (azimute 0° → +x, 90° → +y). */
export function ventoCartesiano(vento: CorpoVento): [number, number, number] {
  const az = (vento.azimute * Math.PI) / 180
  const el = (vento.elevacao * Math.PI) / 180
  const horizontal = vento.vel * Math.cos(el)
  return [horizontal * Math.cos(az), horizontal * Math.sin(az), vento.vel * Math.sin(el)]
}

/** Vetor do mundo → direção polar (azimute/elevação/norma). Vetor nulo → tudo a zero. */
export function direcaoDoVetor(vec: readonly number[]): DirecaoVento {
  const vx = numero(vec[0]) ?? 0
  const vy = numero(vec[1]) ?? 0
  const vz = numero(vec[2]) ?? 0
  const horizontal = Math.hypot(vx, vy)
  const modulo = Math.hypot(horizontal, vz)
  const azimute = horizontal === 0 && vz === 0 ? 0 : ((Math.atan2(vy, vx) * 180) / Math.PI + 360) % 360
  const elevacao = modulo === 0 ? 0 : (Math.asin(vz / modulo) * 180) / Math.PI
  return { modulo, azimute, elevacao, horizontal }
}

/** Ponto cardeal do azimute (só para o rótulo humano ao lado dos graus). */
export function pontoCardeal(azimute: number): string {
  const setores = ["E", "NE", "N", "NO", "O", "SO", "S", "SE"]
  const indice = Math.round((((azimute % 360) + 360) % 360) / 45) % 8
  return setores[indice]
}

// ─────────────────────────────────────────────────────────────── computador de bordo (RPi 5)
/**
 * TIPO da procedência dos números (cor do selo). O TEXTO mostrado é sempre o que o backend mandar; aqui só
 * se classifica pelo prefixo, para o painel poder pintar o selo sem reescrever a frase do backend.
 */
export type TipoFonteRpi5 = "real" | "proxy" | "sem_benchmark" | "outro"

export interface Rpi5Specs {
  cpu: string | null
  soc: string | null
  /** RAM em GB (número) — quando o backend manda um número. */
  ramGb: number | null
  /** RAM como TEXTO (ex.: «LPDDR4X-4267, 1–16 GB (variante)») — o `sim_site.py` manda assim. */
  ramTexto: string | null
  /** Orçamento de latência por decisão (ms) — 20 ms @ 50 Hz. */
  budgetMs: number | null
  /** Frequência de decisão do alvo (Hz). */
  hz: number | null
  /** Núcleos físicos do alvo. */
  nucleos: number | null
  npu: string | null
  /** Nota de throttling térmico do alvo, quando anunciada. */
  throttle: string | null
}

export interface Rpi5Inferencia {
  p50Us: number | null
  p99Us: number | null
  maxUs: number | null
  modeloKb: number | null
  int8Fator: number | null
  /** O backend diz que cabe nos 50 Hz? `null` quando não se pronuncia. */
  cabe50hz: boolean | null
  /** O benchmark é do MESMO .zip que o runner carregou? `null` quando não dá para saber. */
  modeloCoincide: boolean | null
}

export interface Rpi5Uso {
  decisoesS: number | null
  latenciaEstimadaUs: number | null
  pctBudget: number | null
  pctCpuEquivalente: number | null
  nucleosMultiIa: number | null
  /** Frase do backend sobre o gargalo real (ex.: o jitter do SO). */
  gargalo: string | null
  jitterMsStandard: number | null
  jitterUsPreemptRt: number | null
}

/** Estado do hardware (`vcgencmd get_throttled` e temperatura), quando o backend o publica. */
export interface Rpi5Hardware {
  throttled: string | null
  tempC: number | null
}

export interface Rpi5 {
  specs: Rpi5Specs
  inferencia: Rpi5Inferencia
  uso: Rpi5Uso
  /** Estado do próprio hardware; `null` = sem Pi 5 ligado (o painel diz «sem hardware»). */
  hardware: Rpi5Hardware | null
  /** Texto CRU da procedência, tal como o backend o escreve (nunca reescrito pelo site). */
  fonte: string
  tipoFonte: TipoFonteRpi5
  /** O backend publicou mesmo um benchmark (inferência com números)? Se não, o painel não inventa nada. */
  temBenchmark: boolean
}

/** Classifica a frase da procedência pelo prefixo (o backend é livre de a detalhar). */
export function tipoFonteRpi5(bruto: string | null): TipoFonteRpi5 {
  if (bruto === null) return "sem_benchmark"
  const texto = bruto.toLowerCase()
  if (texto.startsWith("real") || texto.includes("no proprio pi") || texto.includes("no próprio pi")) return "real"
  if (texto.startsWith("proxy") || texto.includes("proxy x86")) return "proxy"
  if (texto.includes("sem benchmark")) return "sem_benchmark"
  return "outro"
}

function texto(bruto: unknown): string | null {
  return typeof bruto === "string" && bruto.trim().length > 0 ? bruto : null
}

/** `get_throttled` + temperatura, quando existirem (aceita `hardware` ou as chaves no topo). */
function lerHardwareRpi5(o: Record<string, unknown>): Rpi5Hardware | null {
  const h = objeto(o.hardware)
  const bruto = h.throttled ?? h.get_throttled ?? o.throttled
  const throttled = typeof bruto === "string" ? bruto : null
  const tempC = numero(h.temp_c ?? h.temperatura_c ?? o.temp_c)
  if (throttled === null && tempC === null) return null
  return { throttled, tempC }
}

/** `rpi5` do backend → painel normalizado; `null` quando a chave não vem (o painel diz "sem benchmark"). */
export function lerRpi5(bruto: unknown): Rpi5 | null {
  if (typeof bruto !== "object" || bruto === null) return null
  const o = objeto(bruto)
  if (Object.keys(o).length === 0) return null
  const specs = objeto(o.specs)
  // `inferencia` vem a `null` quando não há benchmark: `objeto()` dá `{}` e o painel mostra "—".
  const inferencia = objeto(o.inferencia)
  const uso = objeto(o.uso)
  return {
    specs: {
      cpu: texto(specs.cpu),
      soc: texto(specs.soc),
      ramGb: numero(specs.ram_gb),
      ramTexto: texto(specs.ram),
      budgetMs: numero(specs.budget_ms),
      hz: numero(specs.hz ?? specs.alvo_hz ?? specs.freq_hz),
      nucleos: numero(specs.nucleos ?? specs.n_cores ?? specs.cores),
      npu: texto(specs.npu),
      throttle: texto(specs.throttle),
    },
    inferencia: {
      p50Us: numero(inferencia.p50_us),
      p99Us: numero(inferencia.p99_us),
      maxUs: numero(inferencia.max_us),
      modeloKb: numero(inferencia.modelo_kb),
      int8Fator: numero(inferencia.int8_fator),
      cabe50hz: typeof inferencia.cabe_50hz === "boolean" ? inferencia.cabe_50hz : null,
      modeloCoincide: typeof inferencia.modelo_coincide === "boolean" ? inferencia.modelo_coincide : null,
    },
    uso: {
      decisoesS: numero(uso.decisoes_s),
      latenciaEstimadaUs: numero(uso.latencia_estimada_us),
      pctBudget: numero(uso.pct_budget),
      pctCpuEquivalente: numero(uso.pct_cpu_equivalente),
      nucleosMultiIa: numero(uso.nucleos_multi_ia),
      gargalo: texto(uso.gargalo),
      jitterMsStandard: numero(uso.jitter_ms_standard),
      jitterUsPreemptRt: numero(uso.jitter_us_preempt_rt),
    },
    hardware: lerHardwareRpi5(o),
    fonte: texto(o.fonte) ?? "sem benchmark",
    tipoFonte: tipoFonteRpi5(texto(o.fonte)),
    temBenchmark: numero(inferencia.p50_us) !== null,
  }
}

/** Orçamento de latência em ms: o que o backend disser ou `1000/hz`; `null` se não der para saber. */
export function budgetMs(rpi5: Rpi5): number | null {
  if (rpi5.specs.budgetMs !== null && rpi5.specs.budgetMs > 0) return rpi5.specs.budgetMs
  const hz = rpi5.specs.hz ?? rpi5.uso.decisoesS
  return hz !== null && hz > 0 ? 1000 / hz : null
}

/** Percentagem de um tempo (µs) face ao orçamento (ms); `null` quando não há orçamento. */
export function pctDoBudget(us: number | null, orcamentoMs: number | null): number | null {
  if (us === null || orcamentoMs === null || orcamentoMs <= 0) return null
  return (us / 1000 / orcamentoMs) * 100
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

/** Vetor de EXATAMENTE 3 números (o `vento_vec`); qualquer outra forma vale `null` (nada de `NaN` no DOM). */
function trio(bruto: unknown): [number, number, number] | null {
  if (!Array.isArray(bruto) || bruto.length !== 3) return null
  const valores = bruto.map((v) => numero(v))
  if (valores.some((v) => v === null)) return null
  return [valores[0] as number, valores[1] as number, valores[2] as number]
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
    vec: trio(o.vec),
    modo: lerModo(o.modo),
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
    vento_vec: trio(o.vento_vec),
    vento_modo: lerModo(o.vento_modo),
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
    ventoDinamico: lerVentoDinamico(o.vento_dinamico),
    rpi5: lerRpi5(o.rpi5),
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
