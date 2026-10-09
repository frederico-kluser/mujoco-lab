/**
 * Contrato do backend `sim_site.py` (experiments/09_drone_hover_rl) e normalização defensiva.
 *
 * Nada aqui assume que o servidor está vivo nem que o JSON vem completo: TODA a leitura passa por
 * `numero()`/`vetor()` e o que faltar sai do ecrã como "—" (nunca `undefined`/`NaN` no DOM).
 */

export type EstadoEpisodio = "a_correr" | "episodio_terminado"

/** Nº de entradas/saídas da política e das camadas escondidas (16 → 64 → 64 → 4). */
export const N_OBS = 16
export const N_ACT = 4
export const N_H1 = 64
export const N_H2 = 64

/** Alvo de altitude do episódio (m) — linha de referência da curva z(t). */
export const ALVO_Z = 1.0

export interface LinhaSim {
  t: number
  estado: EstadoEpisodio
  ep: number
  passo: number
  retorno: number
  z: number
  dist_xy: number
  yaw_err: number
  vento_vel: number
  vento_azim: number
  /** Vetor do vento EM VIGOR `[vx,vy,vz]` (base + dinâmica), ou `null` se a linha não o trouxer. */
  vento_vec: [number, number, number] | null
  /** Modo dinâmico que produziu esta linha (`"nenhum"`/`"rajadas"`/…), ou `null` se não vier. */
  vento_modo: ModoVentoDinamico | null
  obs: number[]
  act: number[]
  h1: number[]
  h2: number[]
  /** Comando físico opcional `[empuxo N, mx, my, mz]` (se o backend o enviar). */
  ctrl: number[] | null
}

export interface VentoEstado {
  vel: number
  azimute: number
  elevacao: number
  ativo: boolean
  /** Vetor em vigor anunciado pelo backend (m/s, mundo); `null` quando só há a forma polar. */
  vec: [number, number, number] | null
  /** Modo dinâmico em vigor anunciado pela API (`vento_atual.modo`); `null` se não vier. */
  modo: ModoVentoDinamico | null
}

export interface RespostaSim {
  estado: EstadoEpisodio
  ep: number
  passo: number
  retorno: number
  vento: VentoEstado
  ventoDinamico: VentoDinamico
  /**
   * Modo de continuidade do BACKEND: `true` = reinicia sozinho ao terminar o episódio (por omissão no
   * `sim_site.py` novo), `false` = para no fim à espera de REINICIAR; `null` = esta resposta não o diz.
   */
  loop: boolean | null
  /** Painel do Raspberry Pi 5; `null` quando o backend ainda não publica `rpi5`. */
  rpi5: Rpi5 | null
  linhas: LinhaSim[]
}

/** Resumo de `GET /api/state` — só os campos que o site usa, todos opcionais. */
export interface ResumoEstado {
  modelo: string | null
  mg: number | null
  thrustMax: number | null
  momentoMax: [number, number, number] | null
  tauEscala: number | null
  np: number | null
  /** Modo dinâmico em vigor (o `/api/state` também o publica; serve de reforço ao `/api/sim`). */
  ventoDinamico: VentoDinamico
  /** Painel do RPi 5, quando o resumo o traz (`null` se não vier). */
  rpi5: Rpi5 | null
  /** Continuidade do backend como o `/api/state` a anuncia (`null` se não vier). */
  loop: boolean | null
}

/** `true`/`false` quando o valor é mesmo booleano; `null` para tudo o resto (nunca se inventa). */
function booleano(bruto: unknown): boolean | null {
  return typeof bruto === "boolean" ? bruto : null
}

/** Constantes físicas de recurso (lab/crazyflie.py + env.py) usadas SÓ para derivar valores de ecrã. */
export const FISICA_PADRAO = {
  mg: 0.26487,
  thrustMax: 0.589,
  momentoMax: [5.69e-3, 5.69e-3, 2.8e-3] as [number, number, number],
  tauEscala: 0.1,
}

/** Número finito ou `null` (nunca NaN/Infinity a caminho do ecrã). */
export function numero(bruto: unknown): number | null {
  const v = typeof bruto === "string" ? Number(bruto) : bruto
  return typeof v === "number" && Number.isFinite(v) ? v : null
}

function vetor(bruto: unknown, n: number): number[] {
  const lista = Array.isArray(bruto) ? bruto : []
  const saida = new Array<number>(n).fill(0)
  for (let i = 0; i < n; i += 1) saida[i] = numero(lista[i]) ?? 0
  return saida
}

function objeto(bruto: unknown): Record<string, unknown> {
  return typeof bruto === "object" && bruto !== null
    ? (bruto as Record<string, unknown>)
    : {}
}

function estado(bruto: unknown): EstadoEpisodio {
  return bruto === "episodio_terminado" ? "episodio_terminado" : "a_correr"
}

/**
 * `vento` do controlo (o que foi pedido) + `vento_atual` da API (o que a física leva).
 *
 * O contrato diz `vento.vec`; o `sim_site.py` publica o mesmo em `vento_atual.vec` (com o modo dinâmico em
 * vigor) — lê-se o primeiro que existir, para o mostrador nunca ficar sem o vetor.
 */
function lerVento(bruto: unknown, atualBruto?: unknown): VentoEstado {
  const o = objeto(bruto)
  const atual = objeto(atualBruto)
  const vel = numero(o.vel) ?? numero(atual.vel) ?? 0
  const azimute = numero(o.azimute) ?? numero(atual.azimute) ?? 0
  const elevacao = numero(o.elevacao) ?? numero(atual.elevacao) ?? 0
  return {
    vel,
    azimute,
    elevacao,
    ativo: o.ativo === true || vel > 0,
    vec: lerVetor3(o.vec) ?? lerVetor3(atual.vec),
    modo: lerModo(o.modo) ?? lerModo(atual.modo),
  }
}

/** `[x,y,z]` finito, ou `null` (nunca `[0,0,0]` a fingir de vetor que não veio). */
function lerVetor3(bruto: unknown): [number, number, number] | null {
  if (!Array.isArray(bruto) || bruto.length < 3) return null
  const x = numero(bruto[0])
  const y = numero(bruto[1])
  const z = numero(bruto[2])
  return x === null || y === null || z === null ? null : [x, y, z]
}

/** Uma linha do stream → `LinhaSim`, ou `null` se nem `t` nem `passo` forem numéricos. */
export function lerLinha(bruto: unknown): LinhaSim | null {
  const o = objeto(bruto)
  const t = numero(o.t)
  const passo = numero(o.passo)
  if (t === null && passo === null) return null
  const ctrl = Array.isArray(o.ctrl) ? vetor(o.ctrl, 4) : null
  return {
    t: t ?? 0,
    estado: estado(o.estado),
    ep: numero(o.ep) ?? 0,
    passo: passo ?? 0,
    retorno: numero(o.retorno) ?? 0,
    z: numero(o.z) ?? 0,
    dist_xy: numero(o.dist_xy) ?? 0,
    yaw_err: numero(o.yaw_err) ?? 0,
    vento_vel: numero(o.vento_vel) ?? 0,
    vento_azim: numero(o.vento_azim) ?? 0,
    vento_vec: lerVetor3(o.vento_vec),
    vento_modo: lerModo(o.vento_modo),
    obs: vetor(o.obs, N_OBS),
    act: vetor(o.act, N_ACT),
    h1: vetor(o.h1, N_H1),
    h2: vetor(o.h2, N_H2),
    ctrl,
  }
}

/** Ativações presentes no stream? (se não vierem, a vista da rede di-lo em vez de fingir zeros) */
export function temAtivacoes(linha: LinhaSim | null): boolean {
  if (!linha) return false
  return linha.h1.some((v) => v !== 0) || linha.h2.some((v) => v !== 0)
}

/** `GET /api/sim` → `RespostaSim` (lista de linhas sem entradas inválidas). */
export function lerSim(bruto: unknown): RespostaSim {
  const o = objeto(bruto)
  const linhas = (Array.isArray(o.linhas) ? o.linhas : [])
    .map(lerLinha)
    .filter((l): l is LinhaSim => l !== null)
  const ultima = linhas.length > 0 ? linhas[linhas.length - 1] : null
  return {
    estado: estado(o.estado ?? ultima?.estado),
    ep: numero(o.ep) ?? ultima?.ep ?? 0,
    passo: numero(o.passo) ?? ultima?.passo ?? 0,
    retorno: numero(o.retorno) ?? ultima?.retorno ?? 0,
    vento: lerVento(o.vento, o.vento_atual),
    ventoDinamico: lerVentoDinamico(o.vento_dinamico),
    loop: booleano(o.loop),
    rpi5: lerRpi5(o.rpi5),
    linhas,
  }
}

/** `GET /api/state` → resumo tolerante a nomes alternativos das mesmas chaves. */
export function lerResumo(bruto: unknown): ResumoEstado {
  const o = objeto(bruto)
  const aninhado = objeto(o.probe)
  const primeiro = (...chaves: string[]): unknown => {
    for (const c of chaves) {
      if (o[c] !== undefined && o[c] !== null) return o[c]
      if (aninhado[c] !== undefined && aninhado[c] !== null) return aninhado[c]
    }
    return undefined
  }
  // `modelo_nome` PRIMEIRO: o `sim_site.py` envia os dois e o `modelo_nome` já é o rótulo legível
  // (`pasta/ficheiro.zip`); o `modelo` é o caminho ABSOLUTO (só serve de tooltip).
  const nome = primeiro(
    "modelo_nome",
    "nome_modelo",
    "modelo",
    "model",
    "politica",
    "policy",
    "run"
  )
  const momentos = primeiro("momento_max", "momentos_max")
  const listaMomentos = Array.isArray(momentos)
    ? momentos.map((m) => numero(m))
    : []
  const momentoMax =
    listaMomentos.length === 3 && listaMomentos.every((m) => m !== null)
      ? ([listaMomentos[0], listaMomentos[1], listaMomentos[2]] as [
          number,
          number,
          number,
        ])
      : null
  return {
    modelo: typeof nome === "string" && nome.length > 0 ? nome : null,
    mg: numero(primeiro("mg", "peso")),
    thrustMax: numero(primeiro("thrust_max", "empuxo_max")),
    momentoMax,
    tauEscala: numero(primeiro("tau_escala")),
    np: numero(primeiro("np", "np_random")),
    ventoDinamico: lerVentoDinamico(primeiro("vento_dinamico")),
    rpi5: lerRpi5(primeiro("rpi5")),
    loop: booleano(primeiro("loop")),
  }
}

/** Chave estável de uma linha (o `t` reinicia em cada episódio; o par ep/passo não). */
export function chaveLinha(l: LinhaSim): string {
  return `${l.ep}:${l.passo}`
}

/**
 * Comprimento máximo do rótulo do modelo no cabeçalho (decidido: 34 caracteres, não 26).
 *
 * Razão: os nomes reais deste laboratório cabem — `vento_r9_polir_vento3/final.zip` (31) e
 * `out/runs/seed0/best_model.zip` (29) — e assim o cabeçalho mostra o nome INTEIRO em vez de o cortar.
 * Acima disto corta-se no MIOLO (nunca no fim): a pasta dá o contexto e o fim do ficheiro distingue
 * `final.zip` de `best_model.zip`. O caminho absoluto completo vive no `title` (tooltip).
 */
export const MODELO_LEGIVEL_MAX = 34

/**
 * Rótulo legível do modelo: **nunca o caminho absoluto**.
 *
 * `pasta/ficheiro.zip` (ou só `ficheiro.zip` sem pasta); acima de `MODELO_LEGIVEL_MAX` corta no MIOLO.
 * Aceita separadores `/` e `\` (o backend pode anunciar um caminho Windows) e ignora barras finais.
 */
export function nomeModeloLegivel(caminho: string | null): string | null {
  if (caminho === null) return null
  const limpo = caminho.trim().replace(/[\\/]+$/, "")
  if (limpo.length === 0) return null
  const partes = limpo.split(/[\\/]+/).filter((p) => p.length > 0)
  if (partes.length === 0) return null
  const ficheiro = partes[partes.length - 1]
  const pasta = partes.length > 1 ? partes[partes.length - 2] : ""
  const rotulo = pasta.length > 0 ? `${pasta}/${ficheiro}` : ficheiro
  if (rotulo.length <= MODELO_LEGIVEL_MAX) return rotulo
  const inicio = Math.ceil((MODELO_LEGIVEL_MAX - 1) / 2)
  const fim = MODELO_LEGIVEL_MAX - 1 - inicio
  const cauda = rotulo.slice(rotulo.length - fim).replace(/^[\\/]+/, "")
  return `${rotulo.slice(0, inicio)}…${cauda}`
}

/** `POST /api/vento` — corpo validado (o backend responde 400 fora das faixas). */
export interface CorpoVento {
  vel: number
  azimute: number
  elevacao: number
}

/** Faixas do painel de vento (as mesmas do contrato). */
export const VENTO_LIMITES = {
  vel: [0, 5] as const,
  azimute: [0, 360] as const,
  elevacao: [-90, 90] as const,
}

/** Vento polar → vetor cartesiano do mundo (azimute 0° → +x, 90° → +y). */
export function ventoCartesiano(vento: CorpoVento): [number, number, number] {
  const az = (vento.azimute * Math.PI) / 180
  const el = (vento.elevacao * Math.PI) / 180
  const horizontal = vento.vel * Math.cos(el)
  return [
    horizontal * Math.cos(az),
    horizontal * Math.sin(az),
    vento.vel * Math.sin(el),
  ]
}

// ------------------------------------------------------------------------------ vento dinâmico

/**
 * Modos do vento dinâmico (ronda 10) aceites por `POST /api/vento-dinamico`.
 *
 * `nenhum` desliga; `rajadas`/`dryden` são CONTÍNUOS (ficam ligados até se desligar);
 * `frente` é um degrau imediato que substitui o vento base; `rajada_agora` é uma rajada única.
 */
export type ModoVentoDinamico =
  "nenhum" | "rajadas" | "frente" | "dryden" | "rajada_agora"

/** Defaults REAIS do ambiente (`env.valida_vento_dinamico`) — nunca inventados aqui. */
export const PARAMS_DINAMICOS_PADRAO = {
  rajadas: { p: 0.02, duracao: 10, u_max: 3 },
  dryden: { sigma: 0.5, L: 10, v_min: 1 },
  rajada_agora: { duracao: 25 },
} as const

/** Modos contínuos mostrados no seletor (os instantâneos têm botão próprio). */
export const MODOS_CONTINUOS = ["nenhum", "rajadas", "dryden"] as const
export type ModoContinuo = (typeof MODOS_CONTINUOS)[number]

/** Rótulos curtos dos modos (PT-PT) para selos e toasts. */
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
export const VENTO_DINAMICO_PARADO: VentoDinamico = {
  modo: "nenhum",
  params: {},
  ativo: false,
}

/** Corpo de `POST /api/vento-dinamico` (contrato: 200/400, sem reiniciar o episódio). */
export interface CorpoVentoDinamico {
  modo: ModoVentoDinamico
  params?: Record<string, number>
  ativo?: boolean
}

function lerModo(bruto: unknown): ModoVentoDinamico | null {
  return typeof bruto === "string" && bruto in ROTULO_MODO
    ? (bruto as ModoVentoDinamico)
    : null
}

/** `vento_dinamico` do backend → estado tolerante (modo desconhecido conta como `nenhum`). */
export function lerVentoDinamico(bruto: unknown): VentoDinamico {
  const o = objeto(bruto)
  const params: Record<string, number> = {}
  for (const [chave, valor] of Object.entries(objeto(o.params))) {
    const n = numero(valor)
    if (n !== null) params[chave] = n
  }
  return {
    modo: lerModo(o.modo) ?? "nenhum",
    params,
    ativo: o.ativo === true,
  }
}

/** Parâmetros em vigor → texto curto (`p=0,02 · duracao=10 · u_max=3`), ou "—". */
export function fmtParams(params: Record<string, number>): string {
  const entradas = Object.entries(params)
  if (entradas.length === 0) return "—"
  return entradas
    .map(
      ([chave, valor]) =>
        `${chave}=${fmt(valor, valor === Math.round(valor) ? 0 : 2)}`
    )
    .join(" · ")
}

// ------------------------------------------------------------------------------ vetor do vento

export interface DirecaoVento {
  /** Norma do vetor (m/s). */
  modulo: number
  /** Azimute em graus [0,360): 0° = +x, 90° = +y (anti-horário). */
  azimute: number
  /** Elevação em graus [-90,90]: positivo = vento a subir. */
  elevacao: number
  /** Componente horizontal ‖[vx,vy]‖ (m/s) — o que a rosa dos ventos desenha. */
  horizontal: number
}

/** Vetor do mundo → direção polar (azimute/elevação/norma). Vetor nulo → tudo a zero. */
export function direcaoDoVetor(vec: readonly number[]): DirecaoVento {
  const vx = numero(vec[0]) ?? 0
  const vy = numero(vec[1]) ?? 0
  const vz = numero(vec[2]) ?? 0
  const horizontal = Math.hypot(vx, vy)
  const modulo = Math.hypot(horizontal, vz)
  const azimute =
    horizontal === 0 && vz === 0
      ? 0
      : ((Math.atan2(vy, vx) * 180) / Math.PI + 360) % 360
  const elevacao = modulo === 0 ? 0 : (Math.asin(vz / modulo) * 180) / Math.PI
  return { modulo, azimute, elevacao, horizontal }
}

/** Ponto cardeal do azimute (só para o rótulo humano ao lado dos graus). */
export function pontoCardeal(azimute: number): string {
  const setores = ["E", "NE", "N", "NO", "O", "SO", "S", "SE"]
  const indice = Math.round((((azimute % 360) + 360) % 360) / 45) % 8
  return setores[indice]
}

// ------------------------------------------------------------------------------ Raspberry Pi 5

/**
 * TIPO da procedência dos números (cor do selo). O TEXTO mostrado é sempre o que o backend mandar
 * (o `sim_site.py` escreve «proxy x86 calibrado (1 core do A76; nao e o RPi)»): aqui só se classifica
 * pelo prefixo, para o painel poder pintar o selo sem reescrever a frase do backend.
 */
export type TipoFonteRpi5 = "real" | "proxy" | "sem_benchmark" | "outro"

export interface Rpi5Specs {
  cpu: string | null
  /** SoC (ex.: «Broadcom BCM2712»), quando anunciado. */
  soc: string | null
  /** RAM em GB (número) — quando o backend manda um número. */
  ramGb: number | null
  /** RAM como TEXTO (ex.: «LPDDR4X-4267, 1-16 GB (variante)») — o `sim_site.py` manda assim. */
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
  /** Frase do backend sobre o gargalo real (ex.: jitter do SO). */
  gargalo: string | null
  jitterMsStandard: number | null
  jitterUsPreemptRt: number | null
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

/** Estado do hardware (`vcgencmd get_throttled` e temperatura), quando o backend o publica. */
export interface Rpi5Hardware {
  /** Texto do `get_throttled` tal como vem (ex.: `0x0`) — o site não o interpreta. */
  throttled: string | null
  tempC: number | null
}

/** Classifica a frase da procedência pelo prefixo (o backend é livre de a detalhar). */
export function tipoFonteRpi5(bruto: string | null): TipoFonteRpi5 {
  if (bruto === null) return "sem_benchmark"
  const texto = bruto.toLowerCase()
  if (
    texto.startsWith("real") ||
    texto.includes("no proprio pi") ||
    texto.includes("no próprio pi")
  )
    return "real"
  if (texto.startsWith("proxy")) return "proxy"
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

/**
 * `rpi5` do backend → painel normalizado; `null` quando a chave não vem (o painel diz "sem benchmark").
 *
 * Nenhum valor é inventado: o que faltar fica `null` e o ecrã mostra "—".
 */
export function lerRpi5(bruto: unknown): Rpi5 | null {
  if (typeof bruto !== "object" || bruto === null) return null
  const o = objeto(bruto)
  if (Object.keys(o).length === 0) return null
  const specs = objeto(o.specs)
  // `inferencia` pode vir a `null` (o `sim_site.py` fá-lo quando não há benchmark): `objeto()` dá `{}`.
  const inferencia = objeto(o.inferencia)
  const uso = objeto(o.uso)
  const temBenchmark = numero(inferencia.p50_us) !== null
  const leitura: Rpi5 = {
    specs: {
      cpu: texto(specs.cpu),
      soc: texto(specs.soc),
      ramGb: numero(specs.ram_gb),
      ramTexto: texto(specs.ram),
      budgetMs: numero(specs.budget_ms),
      hz: numero(
        specs.hz ?? specs.freq_hz ?? specs.alvo_hz ?? specs.decisoes_s
      ),
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
      cabe50hz:
        typeof inferencia.cabe_50hz === "boolean" ? inferencia.cabe_50hz : null,
      modeloCoincide:
        typeof inferencia.modelo_coincide === "boolean"
          ? inferencia.modelo_coincide
          : null,
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
    temBenchmark,
  }
  return leitura
}

/** Orçamento de latência em ms: o que o backend disser ou `1000/hz`; `null` se não der para saber. */
export function budgetMs(rpi5: Rpi5): number | null {
  if (rpi5.specs.budgetMs !== null && rpi5.specs.budgetMs > 0)
    return rpi5.specs.budgetMs
  const hz = rpi5.specs.hz ?? rpi5.uso.decisoesS
  return hz !== null && hz > 0 ? 1000 / hz : null
}

/** Percentagem de um tempo (µs) face ao orçamento (ms); `null` quando não há orçamento. */
export function pctDoBudget(
  us: number | null,
  orcamentoMs: number | null
): number | null {
  if (us === null || orcamentoMs === null || orcamentoMs <= 0) return null
  return (us / 1000 / orcamentoMs) * 100
}

// --------------------------------------------------------------------------------------- formatação

/** Número → texto pt-PT com casas fixas; `null`/não finito → "—". */
export function fmt(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor))
    return "—"
  return valor.toLocaleString("pt-PT", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  })
}

/** Igual a `fmt`, com sinal explícito (para deltas e momentos). */
export function fmtSinal(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor))
    return "—"
  const texto = fmt(Math.abs(valor), casas)
  return valor < 0 ? `−${texto}` : `+${texto}`
}

export function fmtGraus(valor: number | null | undefined, casas = 0): string {
  return `${fmt(valor, casas)}°`
}

/** Inteiro com separador de milhares pt-PT; não finito → "—". */
export function fmtInteiro(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor))
    return "—"
  return Math.round(valor).toLocaleString("pt-PT")
}

/**
 * Latência em µs → texto com a unidade LEGÍVEL, pela MESMA régua em todo o painel:
 *  · abaixo de **100 µs** (0,1 ms) mostra µs com 1 casa — é aí que o número fino é o que interessa
 *    («4,6 µs», «6,8 µs»); a 2 casas em ms sairia «0,00 ms» e o valor medido desaparecia;
 *  · a partir de 100 µs mostra ms com 2 casas («0,16 ms», «2,50 ms»), comparável com o orçamento de
 *    20 ms que está ao lado.
 */
export function fmtLatencia(us: number | null | undefined): string {
  if (us === null || us === undefined || !Number.isFinite(us)) return "—"
  return us < LIMIAR_US_PARA_MS ? `${fmt(us, 1)} µs` : `${fmt(us / 1000, 2)} ms`
}

/** Fronteira µs↔ms da `fmtLatencia` (100 µs = 0,1 ms). */
export const LIMIAR_US_PARA_MS = 100

// --------------------------------------------------------------------------------------- derivados

export interface DerivadosAct {
  /** Empuxo em N, derivado da ação normalizada (ou lido de `linha.ctrl[0]` quando existe). */
  empuxo: number
  momentos: [number, number, number]
  /** `true` quando os valores vieram do backend (`ctrl`), não da derivação local. */
  doBackend: boolean
}

/**
 * Ação normalizada → comando físico. Reproduz `HoverEnv.acao_para_ctrl` (env.py):
 * metade inferior 0…mg, metade superior mg…thrust_max; momentos = `tau_escala · momento_max · a`.
 */
export function derivarAct(
  linha: LinhaSim | null,
  constantes = FISICA_PADRAO
): DerivadosAct | null {
  if (!linha) return null
  const a = linha.act
  if (linha.ctrl) {
    return {
      empuxo: linha.ctrl[0],
      momentos: [linha.ctrl[1], linha.ctrl[2], linha.ctrl[3]],
      doBackend: true,
    }
  }
  const a0 = a[0] ?? 0
  const empuxo =
    a0 <= 0
      ? constantes.mg * (1 + a0)
      : constantes.mg + (constantes.thrustMax - constantes.mg) * a0
  const momentos = [0, 1, 2].map(
    (i) => constantes.tauEscala * constantes.momentoMax[i] * (a[i + 1] ?? 0)
  ) as [number, number, number]
  return { empuxo, momentos, doBackend: false }
}

// --------------------------------------------------------------------------------------- rótulos

export interface RotuloObs {
  indice: number
  grupo: "dp" | "rpy" | "v" | "ω" | "a_prev"
  nome: string
  unidade: string
  /** Escala fixa da normalização (env.py) — a coluna "cru" = obs × escala. */
  escala: number
  escalaTexto: string
}

/** Os 16 canais da observação, na ordem de `HoverEnv.observacao()`. */
export const ROTULOS_OBS: RotuloObs[] = [
  {
    indice: 0,
    grupo: "dp",
    nome: "dp_x",
    unidade: "m",
    escala: 1,
    escalaTexto: "÷1 m",
  },
  {
    indice: 1,
    grupo: "dp",
    nome: "dp_y",
    unidade: "m",
    escala: 1,
    escalaTexto: "÷1 m",
  },
  {
    indice: 2,
    grupo: "dp",
    nome: "dp_z",
    unidade: "m",
    escala: 1,
    escalaTexto: "÷1 m",
  },
  {
    indice: 3,
    grupo: "rpy",
    nome: "roll/π",
    unidade: "rad",
    escala: Math.PI,
    escalaTexto: "÷π",
  },
  {
    indice: 4,
    grupo: "rpy",
    nome: "pitch/π",
    unidade: "rad",
    escala: Math.PI,
    escalaTexto: "÷π",
  },
  {
    indice: 5,
    grupo: "rpy",
    nome: "yaw/π",
    unidade: "rad",
    escala: Math.PI,
    escalaTexto: "÷π",
  },
  {
    indice: 6,
    grupo: "v",
    nome: "v_x",
    unidade: "m/s",
    escala: 1,
    escalaTexto: "÷1 m/s",
  },
  {
    indice: 7,
    grupo: "v",
    nome: "v_y",
    unidade: "m/s",
    escala: 1,
    escalaTexto: "÷1 m/s",
  },
  {
    indice: 8,
    grupo: "v",
    nome: "v_z",
    unidade: "m/s",
    escala: 1,
    escalaTexto: "÷1 m/s",
  },
  {
    indice: 9,
    grupo: "ω",
    nome: "ω_x",
    unidade: "rad/s",
    escala: 10,
    escalaTexto: "÷10 rad/s",
  },
  {
    indice: 10,
    grupo: "ω",
    nome: "ω_y",
    unidade: "rad/s",
    escala: 10,
    escalaTexto: "÷10 rad/s",
  },
  {
    indice: 11,
    grupo: "ω",
    nome: "ω_z",
    unidade: "rad/s",
    escala: 10,
    escalaTexto: "÷10 rad/s",
  },
  {
    indice: 12,
    grupo: "a_prev",
    nome: "a_prev·empuxo",
    unidade: "[-1,1]",
    escala: 1,
    escalaTexto: "1:1",
  },
  {
    indice: 13,
    grupo: "a_prev",
    nome: "a_prev·mx",
    unidade: "[-1,1]",
    escala: 1,
    escalaTexto: "1:1",
  },
  {
    indice: 14,
    grupo: "a_prev",
    nome: "a_prev·my",
    unidade: "[-1,1]",
    escala: 1,
    escalaTexto: "1:1",
  },
  {
    indice: 15,
    grupo: "a_prev",
    nome: "a_prev·mz",
    unidade: "[-1,1]",
    escala: 1,
    escalaTexto: "1:1",
  },
]

/** Os 4 canais da ação, na ordem de `HoverEnv.aplicar_acao()`. */
export const ROTULOS_ACT = [
  { indice: 0, nome: "a₀ · empuxo", canal: "body_thrust", unidade: "N" },
  { indice: 1, nome: "a₁ · momento x", canal: "x_moment", unidade: "N·m" },
  { indice: 2, nome: "a₂ · momento y", canal: "y_moment", unidade: "N·m" },
  { indice: 3, nome: "a₃ · momento z", canal: "z_moment", unidade: "N·m" },
] as const

/** Cor semântica por sinal/|valor| (tokens shadcn, nunca hex): heat da rede e tabelas. */
export function corAtivacao(valor: number, maximo: number): string {
  const forca = maximo > 0 ? Math.min(1, Math.abs(valor) / maximo) : 0
  const percentagem = Math.round(8 + forca * 82)
  const token = valor < 0 ? "var(--destructive)" : "var(--primary)"
  return `color-mix(in srgb, ${token} ${percentagem}%, var(--background))`
}

/** Cor de texto legível sobre `corAtivacao`. */
export function corTextoAtivacao(valor: number, maximo: number): string {
  const forca = maximo > 0 ? Math.min(1, Math.abs(valor) / maximo) : 0
  return forca > 0.55 ? "var(--background)" : "var(--muted-foreground)"
}
