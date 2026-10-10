/**
 * Contrato do backend `sim_site.py` (experiments/09_drone_hover_rl) e normalização defensiva.
 *
 * Nada aqui assume que o servidor está vivo nem que o JSON vem completo: TODA a leitura passa por
 * `numero()`/`vetor()` e o que faltar sai do ecrã como "—" (nunca `undefined`/`NaN` no DOM).
 */

export type EstadoEpisodio = "a_correr" | "episodio_terminado"

/**
 * Que PLANTA física o runner está a simular: o Crazyflie histórico (`cf2`, 16 obs, ctrl = wrench) ou o
 * drone REAL do dono (`real`, 21 obs do ator, ação ctbr, ctrl = empuxo por rotor, bateria/motores).
 * Chave aditiva (`planta`) das linhas de telemetria, do `/api/sim` e do `/api/state`; ausente = cf2.
 */
export type Planta = "real" | "cf2"

/** `"real"`/`"cf2"`, ou `null` quando não vem (ou vem outra coisa) — nunca se adivinha a planta. */
export function lerPlanta(bruto: unknown): Planta | null {
  return bruto === "real" || bruto === "cf2" ? bruto : null
}

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
  /** CâMARA real da janela nesta linha (`camera`), ou `null` se não vier. */
  camera: CameraEstado | null
  /**
   * Planta que produziu esta linha (`planta`); `null` = a linha não o diz (runner antigo ⇒ cf2). Na
   * planta real `obs` tem 21 canais (ator) e `ctrl` é o EMPUXO de cada rotor (N), não o wrench do cf2.
   */
  planta: Planta | null
  /** Planta real: pack de bateria (`bateria`); `null` no cf2 ou quando não vem. */
  bateria: BateriaTelemetria | null
  /** Planta real: os 4 motores + teto de rotação/empuxo (`motores`); `null` no cf2. */
  motores: MotoresTelemetria | null
  /** Planta real: ledger de potência (`potencia`); `null` no cf2. */
  potencia: PotenciaTelemetria | null
  /** Planta real: fatores aerodinâmicos por rotor (`aero`); `null` no cf2. */
  aero: AeroTelemetria | null
  /** Planta real: estimativas de BORDO (`estimador`); `null` no cf2. */
  estimador: EstimadorTelemetria | null
  /**
   * Planta real: a VERDADE do simulador nos referenciais do estimador (`verdade`) — só para o ecrã comparar
   * «o que o drone acha» com «o que é»; a política nunca a vê. `null` no cf2 ou num runner antigo.
   */
  verdade: VerdadeTelemetria | null
  /** Porque fechou o episódio (`fim`): `tempo` (os 10 s) ou `queda`; `null` a correr ou sem a chave. */
  fim: MotivoFim | null
}

/** Motivo do fim do episódio publicado pelo runner (`fim`). */
export type MotivoFim = "tempo" | "queda"

/** `"tempo"`/`"queda"`, ou `null` (a correr, runner antigo ou outro valor — nunca se adivinha). */
export function lerFim(bruto: unknown): MotivoFim | null {
  return bruto === "tempo" || bruto === "queda" ? bruto : null
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
   * `sim_site.py`), `false` = sem reinício (a física CONTINUA no estado em que ficou — não congela — e só
   * um REINICIAR recomeça); `null` = esta resposta não o diz.
   */
  loop: boolean | null
  /** Painel do Raspberry Pi 5; `null` quando o backend ainda não publica `rpi5`. */
  rpi5: Rpi5 | null
  /** CâMARA real da telemetria (`camera`); `null` sem janela/sem chave. */
  camera: CameraEstado | null
  /** CâMARA real tal como `camera_atual` a anuncia; `null` se não vier. */
  cameraAtual: CameraEstado | null
  /** Valores por omissão da câmara (`camera_padrao`) — o que o REPOR VISTA envia. */
  cameraPadrao: CameraEstado | null
  /**
   * A resposta trouxe ALGUMA informação de câmara (`camera`/`camera_atual`/`camera_padrao`, mesmo
   * que `null`)? `false` = backend que ainda não publica a câmara (aí retém-se o que já se sabia).
   */
  cameraPublicada: boolean
  /** Planta anunciada pelo servidor (`planta`); `null` se a resposta não a trouxer. */
  planta: Planta | null
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
  /** CâMARA real da telemetria (`camera`); `null` se não vier. */
  camera: CameraEstado | null
  /** CâMARA real (`camera_atual`); `null` se não vier. */
  cameraAtual: CameraEstado | null
  /** Valores por omissão da câmara (`camera_padrao`); `null` se não vier. */
  cameraPadrao: CameraEstado | null
  /** Houve informação de câmara na resposta (mesmo que `null`)? Ver `RespostaSim.cameraPublicada`. */
  cameraPublicada: boolean
  /** Planta anunciada pelo `/api/state` (`planta`); `null` se não vier. */
  planta: Planta | null
  /** Peças reais do modelo em uso (`hardware`, só na planta real); `null` se não vier. */
  hardware: Hardware | null
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

/** Teto de neurónios por camada aceite na planta real (defesa contra uma lista absurda no JSON). */
const MAX_NEURONIOS = 1024

/**
 * Lista numérica com o tamanho que VIER (planta real: a rede do ator pode ter 128 neurónios por camada),
 * ou `n` zeros quando não vem lista — o mesmo «sem dados» que o `vetor()` dá no cf2.
 */
function vetorLivre(bruto: unknown, n: number): number[] {
  return Array.isArray(bruto) && bruto.length > 0
    ? vetor(bruto, Math.min(bruto.length, MAX_NEURONIOS))
    : vetor(bruto, n)
}

/** Uma linha do stream → `LinhaSim`, ou `null` se nem `t` nem `passo` forem numéricos. */
export function lerLinha(bruto: unknown): LinhaSim | null {
  const o = objeto(bruto)
  const t = numero(o.t)
  const passo = numero(o.passo)
  if (t === null && passo === null) return null
  const ctrl = Array.isArray(o.ctrl) ? vetor(o.ctrl, 4) : null
  const planta = lerPlanta(o.planta)
  // cf2 (ou planta ausente): EXATAMENTE o parser de sempre (16 obs, 64+64 ativações). Planta real: 21 obs
  // do ator e as ativações com o tamanho publicado (o ator real pode ser 128-128).
  const real = planta === "real"
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
    obs: vetor(o.obs, real ? N_OBS_REAL : N_OBS),
    act: vetor(o.act, N_ACT),
    h1: real ? vetorLivre(o.h1, N_H1) : vetor(o.h1, N_H1),
    h2: real ? vetorLivre(o.h2, N_H2) : vetor(o.h2, N_H2),
    ctrl,
    camera: lerCamera(o.camera),
    planta,
    bateria: lerBateria(o.bateria),
    motores: lerMotores(o.motores),
    potencia: lerPotencia(o.potencia),
    aero: lerAero(o.aero),
    estimador: lerEstimador(o.estimador),
    verdade: lerVerdade(o.verdade),
    fim: lerFim(o.fim),
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
    camera: lerCamera(o.camera),
    cameraAtual: lerCamera(o.camera_atual),
    cameraPadrao: lerCamera(o.camera_padrao),
    cameraPublicada:
      "camera" in o || "camera_atual" in o || "camera_padrao" in o,
    planta: lerPlanta(o.planta),
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
    camera: lerCamera(primeiro("camera")),
    cameraAtual: lerCamera(primeiro("camera_atual")),
    cameraPadrao: lerCamera(primeiro("camera_padrao")),
    cameraPublicada:
      ["camera", "camera_atual", "camera_padrao"].some((c) => c in o || c in aninhado),
    planta: lerPlanta(primeiro("planta")),
    hardware: lerHardware(primeiro("hardware")),
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
 * `nenhum` desliga; `rajadas`/`aleatoria`/`dryden` são CONTÍNUOS (ficam ligados até se desligar);
 * `frente` é um degrau imediato que substitui o vento base; `rajada_agora` é uma rajada única.
 */
export type ModoVentoDinamico =
  "nenhum" | "rajadas" | "aleatoria" | "frente" | "dryden" | "rajada_agora"

/**
 * Defaults REAIS do ambiente (`env.valida_vento_dinamico`) — nunca inventados aqui.
 *
 * `aleatoria` só usa `p` e `duracao` (o `u_max` não limita a amostragem: a força sai de U[0, 5] m/s e a
 * elevação de ±90°); os restantes parâmetros são aceites pelo backend mas ignorados nesse modo.
 */
export const PARAMS_DINAMICOS_PADRAO = {
  rajadas: { p: 0.02, duracao: 10, u_max: 3 },
  aleatoria: { p: 0.02, duracao: 10 },
  dryden: { sigma: 0.5, L: 10, v_min: 1 },
  rajada_agora: { duracao: 25 },
} as const

/** Modos contínuos mostrados no seletor (os instantâneos têm botão próprio). */
export const MODOS_CONTINUOS = ["nenhum", "rajadas", "aleatoria", "dryden"] as const
export type ModoContinuo = (typeof MODOS_CONTINUOS)[number]

/** Rótulos curtos dos modos (PT-PT) para selos e toasts. */
export const ROTULO_MODO: Record<ModoVentoDinamico, string> = {
  nenhum: "sem dinâmica",
  rajadas: "rajadas contínuas",
  aleatoria: "rajadas aleatórias",
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

// --------------------------------------------------------------------------------------- câmara

/**
 * CÂMARA da janela 3D, na parametrização abstrata do MuJoCo (`mjvCamera`): ponto de olhar (`alvo`),
 * `distancia` até ele e os ângulos `azimute`/`elevacao` (GRAUS, a convenção do `viewer.cam`).
 *
 * Este é o objeto que o backend publica (`camera` = câmara REAL na telemetria, `camera_atual` no
 * `/api/sim` e `/api/state`; `camera_padrao` = `{azimute, elevacao, distancia}`, sem `alvo`).
 * `POST /api/camera` recebe um SUBCONJUNTO de `{azimute, elevacao, distancia}` (contrato v2) — sem
 * `alvo` (o alvo é do backend: drone+offset) nem `seq` (o servidor incrementa-o).
 */
export interface CameraEstado {
  /** Azimute em graus, normalizado para [0,360) na leitura (contrato: finito, mod 360). */
  azimute: number
  /** Elevação em graus [−90,90] — CONVENÇÃO MuJoCo: NEGATIVO vê de cima (câmara acima do alvo). */
  elevacao: number
  /** Distância da câmara ao alvo, em m (contrato: ]0,20]; UI 0,1–10). */
  distancia: number
  /**
   * Ponto de olhar `[x,y,z]` no mundo (m) — a câmara REAL publica-o (`alvo` = drone+offset, o
   * ponto onde a câmara olha); `camera_padrao` (contrato v2) NÃO o traz ⇒ `null`. Nunca se inventa
   * um alvo: sem ele não há posição derivada e o ecrã mostra «—» na parte do alvo.
   */
  alvo: [number, number, number] | null
}

/**
 * Corpo de `POST /api/camera` (CONTRATO v2) — um SUBCONJUNTO de `{azimute, elevacao, distancia}`:
 * envia-se só o que o gesto manda mudar (o pad manda ângulos, o slider manda distância, o REPOR
 * VISTA manda o `camera_padrao` inteiro). **SEM** `alvo` (o alvo é do backend: drone+offset, que
 * ele segue) e **SEM** `seq` (o servidor incrementa-o); `null` e campos desconhecidos são
 * recusados com 400.
 */
export interface CorpoCamera {
  azimute?: number
  elevacao?: number
  distancia?: number
}

/**
 * Faixas da UI (pad + slider do widget «Câmara») e do CONTRATO (validação do servidor no ficheiro
 * de controlo). A UI nunca manda fora das suas faixas; o contrato aceita mais (`distancia` até 20 m).
 */
export const CAMERA_UI_LIMITES = {
  azimute: [0, 360] as const,
  elevacao: [-90, 90] as const,
  distancia: [0.1, 10] as const,
}

/** Faixas do CONTRATO de câmara (o backend recusa fora disto com 400). */
export const CAMERA_CONTRATO_LIMITES = {
  elevacao: [-90, 90] as const,
  /** `]0,20]` — o 0 é excluído (uma distância nula não é uma câmara). */
  distancia: [0, 20] as const,
}

/** Azimute → [0,360) (contrato: «normalizar mod 360»). */
export function normalizarAzimute(graus: number): number {
  if (!Number.isFinite(graus)) return 0
  return ((graus % 360) + 360) % 360
}

/**
 * Direção de visão UNITÁRIA `f(azimute, elevacao)` na convenção do MuJoCo.
 *
 * Verificado empiricamente contra o MuJoCo 3.15 (`MjvScene.camera[0].forward` após `mjv_updateScene`;
 * erro ≤ 3e-8, que é o `float` do `mjvGLCamera`):
 *
 * ```
 * f = [cos(elev)·cos(azim), cos(elev)·sin(azim), sin(elev)]     (azim e elev em RADIANOS)
 * ```
 *
 * · `azimute` 0° ⇒ a câmara olha para **+x** (sita-se do lado −x); 90° ⇒ olha para +y;
 * · `elevacao` **negativa** ⇒ a câmara fica ACIMA do alvo e olha para baixo (convenção MuJoCo:
 *   `mjvCamera.elevation = -90` vê de cima, `+90` de baixo) — o inverso do vento do painel.
 */
export function direcaoVisao(
  azimute: number,
  elevacao: number
): [number, number, number] {
  const a = (normalizarAzimute(azimute) * Math.PI) / 180
  const e = (elevacao * Math.PI) / 180
  const horizontal = Math.cos(e)
  return [horizontal * Math.cos(a), horizontal * Math.sin(a), Math.sin(e)]
}

/**
 * POSIÇÃO da câmara no mundo: `pos = alvo − d·f(azim,elev)` (a câmara olha DE `pos` PARA o alvo).
 *
 * É a pose da câmara abstrata do MuJoCo. (O `MjvScene.camera[0].pos` medido difere desta por um
 * desvio lateral constante de 0,034 m: o `mjv_updateScene` constrói um par pseudo-estreoscópico
 * `camera[0]`/`camera[1]` a ±0,034·(up×f) — a média dos dois é EXATAMENTE `alvo − d·f`.)
 */
export function posicaoCamera(
  azimute: number,
  elevacao: number,
  distancia: number,
  alvo: readonly number[]
): [number, number, number] {
  const f = direcaoVisao(azimute, elevacao)
  return [
    (alvo[0] ?? 0) - distancia * f[0],
    (alvo[1] ?? 0) - distancia * f[1],
    (alvo[2] ?? 0) - distancia * f[2],
  ]
}

/** ALVO a partir da posição da câmara: `alvo = pos + d·f(azim,elev)` (inverso exato de `posicaoCamera`). */
export function alvoCamera(
  azimute: number,
  elevacao: number,
  distancia: number,
  pos: readonly number[]
): [number, number, number] {
  const f = direcaoVisao(azimute, elevacao)
  return [
    (pos[0] ?? 0) + distancia * f[0],
    (pos[1] ?? 0) + distancia * f[1],
    (pos[2] ?? 0) + distancia * f[2],
  ]
}

/**
 * Qualquer objeto `camera` do backend → `CameraEstado`, ou `null` se vier incompleto/não finito
 * (nunca se inventa uma câmara: sem dados o ecrã mostra «—»). O azimute normaliza-se mod 360.
 * O `alvo` é OPCIONAL (contrato v2: `camera_padrao` não o traz) → `null` quando ausente.
 */
export function lerCamera(bruto: unknown): CameraEstado | null {
  const o = objeto(bruto)
  const azimute = numero(o.azimute)
  const elevacao = numero(o.elevacao)
  const distancia = numero(o.distancia)
  const alvo = lerVetor3(o.alvo)
  if (
    azimute === null ||
    elevacao === null ||
    distancia === null ||
    distancia <= 0
  )
    return null
  return {
    azimute: normalizarAzimute(azimute),
    elevacao,
    distancia,
    alvo,
  }
}

/** Duas câmaras «a dizer o mesmo»? (azimute circular; ε por omissão 1e-6) */
export function cameraIgual(
  a: CameraEstado,
  b: CameraEstado,
  eps = 1e-6
): boolean {
  const d = Math.abs(normalizarAzimute(a.azimute - b.azimute))
  const az = Math.min(d, 360 - d)
  const alvoIgual =
    (a.alvo === null && b.alvo === null) ||
    (a.alvo !== null &&
      b.alvo !== null &&
      a.alvo.every((v, i) => Math.abs(v - b.alvo![i]) <= eps))
  return (
    az <= eps &&
    Math.abs(a.elevacao - b.elevacao) <= eps &&
    Math.abs(a.distancia - b.distancia) <= eps &&
    alvoIgual
  )
}

/**
 * A câmara REAL `cam` reflete o comando `corpo`? (confirmação do envio: compara SÓ os campos que o
 * comando levava — o corpo v2 é um subconjunto — com o azimute circular).
 */
export function cameraReflete(
  cam: CameraEstado,
  corpo: CorpoCamera,
  eps = 1e-6
): boolean {
  if (corpo.azimute !== undefined) {
    const d = Math.abs(normalizarAzimute(cam.azimute - corpo.azimute))
    if (Math.min(d, 360 - d) > eps) return false
  }
  if (corpo.elevacao !== undefined && Math.abs(cam.elevacao - corpo.elevacao) > eps)
    return false
  if (corpo.distancia !== undefined && Math.abs(cam.distancia - corpo.distancia) > eps)
    return false
  return true
}

/**
 * Fusão HONESTA da câmara real entre respostas (estados honestos, DEF-2): sem dados ⇒ `null` (o
 * painel mostra «—»), NUNCA uma câmara inventada nem a retenção de valores que a API já desmentiu.
 *
 * · `null` explícito de `camera_atual`/`camera` PROPAGA-se (ex.: a janela do viewer fechou a meio
 *   da sessão — `null`→valor→`null` termina em «—», e não num valor antigo);
 * · o valor anterior retém-se SÓ quando a resposta não publica câmara nenhuma (`publicada: false`,
 *   backend antigo/mock) — enquanto há dados eles mandam, quando deixam de haver mostra-se «—»;
 * · `atual ?? telemetria` é o reforço do contrato: `camera_atual` é a fonte principal e a `camera`
 *   da telemetria entra enquanto houver dados numa delas.
 */
export function fundirCamera(
  anterior: CameraEstado | null,
  atual: CameraEstado | null,
  telemetria: CameraEstado | null,
  publicada: boolean
): CameraEstado | null {
  if (!publicada) return anterior
  return atual ?? telemetria ?? null
}

/**
 * Assinatura estável de um comando de câmara (dedupe de envios: um corpo v2 é um subconjunto de
 * `{azimute, elevacao, distancia}`; o azimute normaliza-se para 360 ≡ 0).
 */
export function assinaturaCamera(cam: CorpoCamera): string {
  return JSON.stringify([
    cam.azimute === undefined ? null : normalizarAzimute(cam.azimute),
    cam.elevacao ?? null,
    cam.distancia ?? null,
  ])
}

// ------------------------------------------------------------------------------ Raspberry Pi 5

/**
 * TIPO da procedência dos números (cor do selo). O TEXTO mostrado é sempre o que o backend mandar
 * (o `sim_site.py` escreve «proxy x86 calibrado (1 núcleo do A76; não é o RPi)»): aqui só se classifica
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
 *
 * SÓ cf2: na planta real o `ctrl` é o empuxo de CADA ROTOR e a ação é ctbr — derivar daqui um
 * empuxo/momentos do `HoverEnv` seria inventar um comando que a física não usou (devolve `null`).
 */
export function derivarAct(
  linha: LinhaSim | null,
  constantes = FISICA_PADRAO
): DerivadosAct | null {
  if (!linha) return null
  if (linha.planta === "real") return null
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

/** Grupos da observação: os 5 do cf2 (`env.py`) + os da planta real (`env_real.py`, ator). */
export type GrupoObs =
  | "dp"
  | "rpy"
  | "v"
  | "ω"
  | "a_prev"
  | "giro"
  | "acc"
  | "atitude"
  | "rumo"
  | "vertical"
  | "fluxo"
  | "odometria"
  | "validade"

export interface RotuloObs {
  indice: number
  grupo: GrupoObs
  nome: string
  unidade: string
  /** Escala fixa da normalização (env.py) — a coluna "cru" = obs × escala. */
  escala: number
  escalaTexto: string
  /** Canal binário (0/1, planta real: ToF/fluxo válidos) — a coluna «cru» diz sim/não. */
  flag?: boolean
  /** Nome em linguagem simples (planta real) — o `nome` de código fica ao lado, pequeno. */
  titulo?: string
  /** O que o canal é, numa frase (dica da tabela). */
  ajuda?: string
  /**
   * Leitura AMIGÁVEL (planta real): `valor físico × fator` na `unidade` (°, °/s, cm, cm/s, g…), com
   * `casas` decimais; `faixa` = meia-largura típica para a barra centrada no zero (fora dela a barra satura).
   */
  amigavel?: { unidade: string; fator: number; casas: number; faixa: number }
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

// ================================================================================== planta REAL
//
// O drone do dono (`env_real.py` + `lab/drone_rpi`): bateria, motores, ledger de potência, aero e o
// estimador de bordo chegam em chaves ADITIVAS de cada linha (`planta: "real"`); as peças vêm do
// `hardware` do `/api/state`. Tudo opcional: o que faltar (ou vier inválido) fica `null` e o ecrã
// mostra «—» — nada é inventado, nada rebenta. Com `planta` cf2/ausente estas chaves não existem.

/** Nº de canais da observação do ATOR na planta real (`env_real.OBS_ATOR_DIM`). */
export const N_OBS_REAL = 21

/**
 * Setpoints de taxa máximos do modo ctbr (`env_real.TAXA_MAX`, rad/s): p, q, r. É o RECURSO quando o
 * `/api/state` não publica `hardware.taxa_max` (o backend lê-o do próprio `env_real`); o pytest da skill
 * compara este valor com o do ambiente, para o painel nunca voltar a mostrar setpoints errados.
 */
export const TAXA_MAX_CTBR: readonly [number, number, number] = [2, 2, 1]

/** Coletivo +1 = 2× o peso por omissão (o `DroneRealEnv` é linear em empuxo: u = u_pair·√(1+a₀)). */
export const COLETIVO_MAX_PESO = 2

/** Gravidade da normalização do acelerómetro (`env.gravidade` = |opt.gravity_z| = 9,81 m/s²). */
export const GRAVIDADE = 9.81

/** rad → graus. */
export const GRAUS_POR_RAD = 180 / Math.PI

/** Altura de rotor que o backend usa para «sem chão no raio» (`ALTURA_SEM_SOLO` = 50 m). */
export const ALTURA_SEM_SOLO_M = 50

/** Objeto com pelo menos uma chave, ou `null` (lista, `null`, `{}` ou outro tipo = sem dados). */
function objetoComDados(bruto: unknown): Record<string, unknown> | null {
  if (typeof bruto !== "object" || bruto === null || Array.isArray(bruto))
    return null
  const o = bruto as Record<string, unknown>
  return Object.keys(o).length > 0 ? o : null
}

/** `n` leituras numéricas (uma por rotor); o que faltar/for inválido fica `null` — nunca um 0 fingido. */
function vetorOuNulos(bruto: unknown, n: number): (number | null)[] {
  const lista = Array.isArray(bruto) ? bruto : []
  return Array.from({ length: n }, (_, i) => numero(lista[i]))
}

// ------------------------------------------------------------------------------------ bateria

/** Alerta do pack: `nenhum` (`""`), abaixo da tensão de POUSO da química, ou abaixo do CORTE. */
export type AlertaBateria = "nenhum" | "tensao_baixa" | "critica"

/** Resumo do último ciclo FECHADO pelo `POST /api/bateria` (`ultimo_ciclo`). */
export interface UltimoCicloBateria {
  /** `recarregar` (fechou o ciclo com desgaste) ou `nova` (pack novo) — texto do backend. */
  acao: string | null
  /** Profundidade de descarga do ciclo (0–1). */
  dod: number | null
  ah: number | null
  wh: number | null
  /** C-rate médio do ciclo. */
  cMedio: number | null
  tMedioC: number | null
  iPico: number | null
  vMin: number | null
  duracaoS: number | null
  /** SoH DEPOIS de aplicado o desgaste do ciclo (0–1). */
  soh: number | null
}

/** Pack de bateria da planta real (`bateria` de cada linha) — frações em 0–1, SI no resto. */
export interface BateriaTelemetria {
  /** SoC REAL do modelo (0–1). */
  soc: number | null
  /** SoC que o RPi estima: OCV em repouso no arranque + Coulomb com a corrente MEDIDA (0–1). */
  socEstimado: number | null
  /** Tensão terminal do pack (V) e por célula (V). */
  v: number | null
  vCelula: number | null
  /** Corrente (A) e potência (W) reais do pack. */
  i: number | null
  p: number | null
  tempC: number | null
  /** Estado de saúde (capacidade atual / nominal, 0–1). */
  soh: number | null
  ciclosEq: number | null
  nRecargas: number | null
  r0Mohm: number | null
  /** Consumo desde a última recarga (o ciclo em curso). */
  ahVoo: number | null
  whVoo: number | null
  alerta: AlertaBateria | null
  /** SoH ≤ 80 % (fim de vida, convenção da indústria). */
  reformar: boolean | null
  /** Minutos até à reserva de pouso com a corrente média; `null` = sem corrente média (motores parados). */
  autonomiaMin: number | null
  s: number | null
  pParalelo: number | null
  quimica: string | null
  capacidadeAh: number | null
  packId: string | null
  vPousoCelula: number | null
  vCorteCelula: number | null
  /** Leituras do monitor de bateria (o que o RPi vê): tensão e corrente medidas, corrente média. */
  vMedida: number | null
  iMedida: number | null
  iMedia: number | null
  ultimoCiclo: UltimoCicloBateria | null
}

function lerAlerta(bruto: unknown): AlertaBateria | null {
  if (bruto === "") return "nenhum"
  return bruto === "tensao_baixa" || bruto === "critica" ? bruto : null
}

function lerUltimoCiclo(bruto: unknown): UltimoCicloBateria | null {
  const o = objetoComDados(bruto)
  if (o === null) return null
  return {
    acao: texto(o.acao),
    dod: numero(o.dod),
    ah: numero(o.ah),
    wh: numero(o.wh),
    cMedio: numero(o.c_medio),
    tMedioC: numero(o.t_medio_c),
    iPico: numero(o.i_pico),
    vMin: numero(o.v_min),
    duracaoS: numero(o.duracao_s),
    soh: numero(o.soh),
  }
}

/** `bateria` de uma linha → leitura tolerante; `null` quando a chave não vem (cf2) ou vem vazia. */
export function lerBateria(bruto: unknown): BateriaTelemetria | null {
  const o = objetoComDados(bruto)
  if (o === null) return null
  return {
    soc: numero(o.soc),
    socEstimado: numero(o.soc_estimado),
    v: numero(o.v),
    vCelula: numero(o.v_celula),
    i: numero(o.i),
    p: numero(o.p),
    tempC: numero(o.temp_c),
    soh: numero(o.soh),
    ciclosEq: numero(o.ciclos_eq),
    nRecargas: numero(o.n_recargas),
    r0Mohm: numero(o.r0_mohm),
    ahVoo: numero(o.ah_voo),
    whVoo: numero(o.wh_voo),
    alerta: lerAlerta(o.alerta),
    reformar: booleano(o.reformar),
    autonomiaMin: numero(o.autonomia_min),
    s: numero(o.s),
    pParalelo: numero(o.p_paralelo),
    quimica: texto(o.quimica),
    capacidadeAh: numero(o.capacidade_ah),
    packId: texto(o.pack_id),
    vPousoCelula: numero(o.v_pouso_celula),
    vCorteCelula: numero(o.v_corte_celula),
    vMedida: numero(o.v_medida),
    iMedida: numero(o.i_medida),
    iMedia: numero(o.i_media),
    ultimoCiclo: lerUltimoCiclo(o.ultimo_ciclo),
  }
}

/** Química do pack em texto curto (`li-ion` → «Li-ion», `lipo` → «LiPo»; outra → tal como vem). */
export function rotuloQuimica(quimica: string | null): string | null {
  if (quimica === null) return null
  const q = quimica.toLowerCase()
  if (q === "li-ion" || q === "liion") return "Li-ion"
  if (q === "lipo") return "LiPo"
  return quimica
}

// ------------------------------------------------------------------------------------ motores

/** Os 4 motores da planta real (`motores`), na ordem r1..r4. */
export interface MotoresTelemetria {
  rpm: (number | null)[]
  /** Ciclo útil do ESC (0–1). */
  duty: (number | null)[]
  /** Empuxo de cada rotor (N) — o mesmo valor do `ctrl` da linha. */
  empuxoN: (number | null)[]
  /** Corrente de fase de cada motor (A). */
  iFase: (number | null)[]
  /** Teto de rotação com a tensão ATUAL (rpm). */
  omegaMaxRpm: number | null
  /** Empuxo máximo POR ROTOR com a tensão atual (N). */
  tMaxN: number | null
  /** T_max atual / T_max com a bateria cheia (0–1): o «limite de rotação» que decai com a descarga. */
  tMaxFrac: number | null
  armado: boolean | null
  brownout: boolean | null
}

export function lerMotores(bruto: unknown): MotoresTelemetria | null {
  const o = objetoComDados(bruto)
  if (o === null) return null
  return {
    rpm: vetorOuNulos(o.rpm, 4),
    duty: vetorOuNulos(o.duty, 4),
    empuxoN: vetorOuNulos(o.empuxo_n, 4),
    iFase: vetorOuNulos(o.i_fase, 4),
    omegaMaxRpm: numero(o.omega_max_rpm),
    tMaxN: numero(o.t_max_n),
    tMaxFrac: numero(o.t_max_frac),
    armado: booleano(o.armado),
    brownout: booleano(o.brownout),
  }
}

/** Um rotor da planta real: nome, posição no frame em X e sentido de rotação VISTO DE CIMA. */
export interface RotorReal {
  indice: number
  nome: string
  posicao: string
  sentido: "CW" | "CCW"
}

/**
 * Os 4 rotores (`componentes.Hardware.pos_rotores` + `GIRO`): frame em X, frente = +x, esquerda = +y.
 * Diagonais com o mesmo sentido — r1 (frente-esq) e r2 (trás-dir) CW; r3 (trás-esq) e r4 (frente-dir) CCW.
 */
export const ROTORES_REAIS: readonly RotorReal[] = [
  { indice: 0, nome: "r1", posicao: "frente-esq", sentido: "CW" },
  { indice: 1, nome: "r2", posicao: "trás-dir", sentido: "CW" },
  { indice: 2, nome: "r3", posicao: "trás-esq", sentido: "CCW" },
  { indice: 3, nome: "r4", posicao: "frente-dir", sentido: "CCW" },
]

/** Ordem de desenho em VISTA DE CIMA com a frente para cima: frente-esq, frente-dir, trás-esq, trás-dir. */
export const ROTORES_VISTA_DE_CIMA: readonly number[] = [0, 3, 2, 1]

// ------------------------------------------------------------------------------------ potência

export interface ConsumidorPotencia {
  /** Chave do backend (`rpi5`, `fc_f7`, `sensor_imu`, …). */
  id: string
  w: number
}

/** Ledger de potência do passo (W): total = motores + eletrónica; eletrónica = Σ 5 V + perdas do BEC. */
export interface PotenciaTelemetria {
  motores: number | null
  eletronica: number | null
  becPerdas: number | null
  total: number | null
  /** Consumidores do barramento de 5 V, pela ordem do backend (só os valores finitos). */
  consumidores5v: ConsumidorPotencia[]
}

export function lerPotencia(bruto: unknown): PotenciaTelemetria | null {
  const o = objetoComDados(bruto)
  if (o === null) return null
  const consumidores5v: ConsumidorPotencia[] = []
  for (const [id, valor] of Object.entries(objeto(o.consumidores_5v))) {
    const w = numero(valor)
    if (w !== null) consumidores5v.push({ id, w })
  }
  return {
    motores: numero(o.motores),
    eletronica: numero(o.eletronica),
    becPerdas: numero(o.bec_perdas),
    total: numero(o.total),
    consumidores5v,
  }
}

const ROTULO_CONSUMIDOR: Record<string, string> = {
  rpi5: "Raspberry Pi 5",
  cablagem: "HAT de energia/cablagem",
  sensor_imu: "IMU (giro + acc)",
  sensor_tof: "ToF (altura)",
  sensor_fluxo: "fluxo ótico",
  sensor_monitor: "monitor de bateria",
}

/**
 * Nome legível de um consumidor de 5 V (a chave do backend fica visível ao lado, em mono). O catálogo de
 * peças muda (`fc_f7`, `fc_h7`, …): as famílias conhecidas reconhecem-se pelo prefixo e uma chave nova
 * aparece tal como vem — nunca se esconde um consumidor por não ter rótulo.
 */
export function rotuloConsumidor(id: string): string {
  const conhecido = ROTULO_CONSUMIDOR[id]
  if (conhecido !== undefined) return conhecido
  if (id.startsWith("fc_")) return `controlador de voo (${id.slice(3).toUpperCase()})`
  if (id.startsWith("sensor_")) return `sensor ${id.slice(7)}`
  return id
}

// ------------------------------------------------------------------------------- aero · estimador

/** Fatores aerodinâmicos por rotor: κ_T = efeito de solo × inflow × VRS (1 = ar livre). */
export interface AeroTelemetria {
  kappaT: (number | null)[]
  /** Altura de cada rotor ao chão (m); `ALTURA_SEM_SOLO_M` = sem chão no raio. */
  alturaRotores: (number | null)[]
}

export function lerAero(bruto: unknown): AeroTelemetria | null {
  const o = objetoComDados(bruto)
  if (o === null) return null
  return {
    kappaT: vetorOuNulos(o.kappa_t, 4),
    alturaRotores: vetorOuNulos(o.altura_rotores, 4),
  }
}

/** Estimativas de BORDO (o que o RPi sabe): atitude e rumo (rad), altura (m), velocidades (m/s), odometria (m). */
export interface EstimadorTelemetria {
  roll: number | null
  pitch: number | null
  psi: number | null
  h: number | null
  vz: number | null
  vx: number | null
  vy: number | null
  x: number | null
  y: number | null
}

export function lerEstimador(bruto: unknown): EstimadorTelemetria | null {
  const o = objetoComDados(bruto)
  if (o === null) return null
  return {
    roll: numero(o.roll),
    pitch: numero(o.pitch),
    psi: numero(o.psi),
    h: numero(o.h),
    vz: numero(o.vz),
    vx: numero(o.vx),
    vy: numero(o.vy),
    x: numero(o.x),
    y: numero(o.y),
  }
}

/**
 * VERDADE do simulador (`verdade`, planta real) nos MESMOS referenciais do estimador de bordo: posição no
 * referencial de ARRANQUE (origem e rumo do armar — o da odometria), velocidade horizontal no referencial
 * de RUMO do corpo, rumo desde o armar. SI: m, rad, m/s, rad/s. Só para o ecrã — a política nunca a vê.
 */
export interface VerdadeTelemetria {
  x: number | null
  y: number | null
  /** O alvo de posição nesse referencial (m); `null` se não vier. */
  alvoXy: [number, number] | null
  /** Altura do CM (m) e o alvo de altura (m). */
  z: number | null
  alvoZ: number | null
  roll: number | null
  pitch: number | null
  /** Rumo desde o armar (ψ − ψ₀, rad) — comparável com o `estimador.psi`. */
  psi: number | null
  /** Rumo ABSOLUTO no mundo (rad) — o das vistas rápidas da câmara («atrás do drone»…). */
  yaw: number | null
  vx: number | null
  vy: number | null
  vz: number | null
  p: number | null
  q: number | null
  r: number | null
}

export function lerVerdade(bruto: unknown): VerdadeTelemetria | null {
  const o = objetoComDados(bruto)
  if (o === null) return null
  const alvo = Array.isArray(o.alvo_xy) ? o.alvo_xy : []
  const ax = numero(alvo[0])
  const ay = numero(alvo[1])
  return {
    x: numero(o.x),
    y: numero(o.y),
    alvoXy: ax === null || ay === null ? null : [ax, ay],
    z: numero(o.z),
    alvoZ: numero(o.alvo_z),
    roll: numero(o.roll),
    pitch: numero(o.pitch),
    psi: numero(o.psi),
    yaw: numero(o.yaw),
    vx: numero(o.vx),
    vy: numero(o.vy),
    vz: numero(o.vz),
    p: numero(o.p),
    q: numero(o.q),
    r: numero(o.r),
  }
}

// ------------------------------------------------------------------------------------ hardware

/** Pack do build (`hardware.bateria` do `/api/state`). */
export interface HardwareBateria {
  id: string | null
  quimica: string | null
  s: number | null
  p: number | null
  ah: number | null
  wh: number | null
  massaG: number | null
  whKg: number | null
  r0Mohm: number | null
}

/** Peças reais do modelo em uso (`hardware` do `/api/state`, lido do `hardware.json` do modelo). */
export interface Hardware {
  build: string | null
  /** `ctbr` (FC dedicado fecha a malha de taxa) ou `motores` (4 aceleradores). */
  modoAcao: string | null
  motor: string | null
  helice: string | null
  celula: string | null
  frame: string | null
  esc: string | null
  bateria: HardwareBateria | null
  massaTotalG: number | null
  /** Relação empuxo/peso com a bateria cheia. */
  tW: number | null
  omegaMaxRpm: number | null
  pPairagemW: number | null
  gPorW: number | null
  autonomiaMin: number | null
  kf: number | null
  kq: number | null
  origemKfKq: string | null
  /** Domain randomization ligada no treino da política. */
  dr: boolean | null
  /** Setpoints de taxa máximos do ctbr (`env_real.TAXA_MAX`, rad/s: p, q, r); `null` = não veio. */
  taxaMax: [number, number, number] | null
  /** Coletivo +1 = este múltiplo do PESO (ctbr linear em empuxo: −1 → 0, 0 → pairar, +1 → 2× o peso). */
  coletivoMaxPeso: number | null
}

function lerHardwareBateria(bruto: unknown): HardwareBateria | null {
  const o = objetoComDados(bruto)
  if (o === null) return null
  return {
    id: texto(o.id),
    quimica: texto(o.quimica),
    s: numero(o.s),
    p: numero(o.p),
    ah: numero(o.ah),
    wh: numero(o.wh),
    massaG: numero(o.massa_g),
    whKg: numero(o.wh_kg),
    r0Mohm: numero(o.r0_mohm),
  }
}

/** `hardware` do `/api/state` → peças; `null` no cf2 (o servidor manda `null`) ou sem a chave. */
export function lerHardware(bruto: unknown): Hardware | null {
  const o = objetoComDados(bruto)
  if (o === null) return null
  return {
    build: texto(o.build),
    modoAcao: texto(o.modo_acao),
    motor: texto(o.motor),
    helice: texto(o.helice),
    celula: texto(o.celula),
    frame: texto(o.frame),
    esc: texto(o.esc),
    bateria: lerHardwareBateria(o.bateria),
    massaTotalG: numero(o.massa_total_g),
    tW: numero(o.t_w),
    omegaMaxRpm: numero(o.omega_max_rpm),
    pPairagemW: numero(o.p_pairagem_w),
    gPorW: numero(o.g_por_w),
    autonomiaMin: numero(o.autonomia_min),
    kf: numero(o.kf),
    kq: numero(o.kq),
    origemKfKq: texto(o.origem_kf_kq),
    dr: booleano(o.dr),
    taxaMax: lerVetor3Positivo(o.taxa_max),
    coletivoMaxPeso: numero(o.coletivo_max_peso),
  }
}

/** `[a,b,c]` finito e > 0 (faixas de taxa), ou `null`. */
function lerVetor3Positivo(bruto: unknown): [number, number, number] | null {
  const v = lerVetor3(bruto)
  return v !== null && v.every((x) => x > 0) ? v : null
}

// ------------------------------------------------------------------- rótulos da planta real

/** Os 21 canais da observação do ATOR na planta real, na ordem de `DroneRealEnv.observacao()`. */
export const ROTULOS_OBS_REAL: RotuloObs[] = [
  { indice: 0, grupo: "giro", nome: "giro_p", unidade: "rad/s", escala: 2, escalaTexto: "÷2 rad/s",
    titulo: "rotação em rolamento (p)", ajuda: "giroscópio: quão depressa o drone roda à volta do eixo frente-trás",
    amigavel: { unidade: "°/s", fator: GRAUS_POR_RAD, casas: 1, faixa: 60 } },
  { indice: 1, grupo: "giro", nome: "giro_q", unidade: "rad/s", escala: 2, escalaTexto: "÷2 rad/s",
    titulo: "rotação em arfagem (q)", ajuda: "giroscópio: quão depressa o drone roda à volta do eixo esquerda-direita",
    amigavel: { unidade: "°/s", fator: GRAUS_POR_RAD, casas: 1, faixa: 60 } },
  { indice: 2, grupo: "giro", nome: "giro_r", unidade: "rad/s", escala: 2, escalaTexto: "÷2 rad/s",
    titulo: "rotação em guinada (r)", ajuda: "giroscópio: quão depressa o drone roda sobre si mesmo (vertical)",
    amigavel: { unidade: "°/s", fator: GRAUS_POR_RAD, casas: 1, faixa: 60 } },
  { indice: 3, grupo: "acc", nome: "acc_x", unidade: "m/s²", escala: GRAVIDADE, escalaTexto: "÷9,81 m/s²",
    titulo: "aceleração frente-trás", ajuda: "acelerómetro (força específica) ao longo do eixo da frente, em g",
    amigavel: { unidade: "g", fator: 1 / GRAVIDADE, casas: 2, faixa: 0.5 } },
  { indice: 4, grupo: "acc", nome: "acc_y", unidade: "m/s²", escala: GRAVIDADE, escalaTexto: "÷9,81 m/s²",
    titulo: "aceleração esquerda-direita", ajuda: "acelerómetro ao longo do eixo da esquerda, em g",
    amigavel: { unidade: "g", fator: 1 / GRAVIDADE, casas: 2, faixa: 0.5 } },
  { indice: 5, grupo: "acc", nome: "acc_z", unidade: "m/s²", escala: GRAVIDADE, escalaTexto: "÷9,81 m/s²",
    titulo: "aceleração vertical", ajuda: "acelerómetro no eixo vertical do corpo: ≈ 1 g a pairar (o empuxo segura o peso)",
    amigavel: { unidade: "g", fator: 1 / GRAVIDADE, casas: 2, faixa: 2 } },
  { indice: 6, grupo: "atitude", nome: "roll_est", unidade: "rad", escala: 1, escalaTexto: "1:1 rad",
    titulo: "inclinação lateral (rolamento)", ajuda: "estimada a bordo (filtro complementar giro + acelerómetro); + = inclinado para a direita (asa direita em baixo)",
    amigavel: { unidade: "°", fator: GRAUS_POR_RAD, casas: 1, faixa: 20 } },
  { indice: 7, grupo: "atitude", nome: "pitch_est", unidade: "rad", escala: 1, escalaTexto: "1:1 rad",
    titulo: "inclinação frente-trás (arfagem)", ajuda: "estimada a bordo; + = nariz para BAIXO (eixos do simulador: x frente, y esquerda, z cima)",
    amigavel: { unidade: "°", fator: GRAUS_POR_RAD, casas: 1, faixa: 20 } },
  { indice: 8, grupo: "rumo", nome: "Δψ/π", unidade: "rad", escala: Math.PI, escalaTexto: "÷π",
    titulo: "rumo desde o arranque", ajuda: "quanto o nariz rodou desde que armou (giroscópio integrado; sem bússola, deriva devagar)",
    amigavel: { unidade: "°", fator: GRAUS_POR_RAD, casas: 1, faixa: 45 } },
  { indice: 9, grupo: "vertical", nome: "h_est − alvo", unidade: "m", escala: 1, escalaTexto: "÷1 m",
    titulo: "altura em relação ao alvo", ajuda: "altura estimada (sensor ToF + acelerómetro) menos o alvo de 1 m; − = abaixo",
    amigavel: { unidade: "cm", fator: 100, casas: 1, faixa: 50 } },
  { indice: 10, grupo: "vertical", nome: "vz_est", unidade: "m/s", escala: 1, escalaTexto: "÷1 m/s",
    titulo: "velocidade vertical", ajuda: "estimada a bordo; + = a subir",
    amigavel: { unidade: "cm/s", fator: 100, casas: 1, faixa: 100 } },
  { indice: 11, grupo: "fluxo", nome: "vx_fluxo", unidade: "m/s", escala: 1, escalaTexto: "÷1 m/s",
    titulo: "velocidade para a frente", ajuda: "do fluxo ótico (câmara a olhar para o chão) + giroscópio, no referencial do nariz",
    amigavel: { unidade: "cm/s", fator: 100, casas: 1, faixa: 100 } },
  { indice: 12, grupo: "fluxo", nome: "vy_fluxo", unidade: "m/s", escala: 1, escalaTexto: "÷1 m/s",
    titulo: "velocidade para a esquerda", ajuda: "do fluxo ótico, no referencial do nariz; + = para a esquerda",
    amigavel: { unidade: "cm/s", fator: 100, casas: 1, faixa: 100 } },
  { indice: 13, grupo: "odometria", nome: "x_odo", unidade: "m", escala: 1, escalaTexto: "÷1 m",
    titulo: "posição estimada (frente)", ajuda: "odometria: soma das velocidades do fluxo desde o arranque — deriva com o tempo",
    amigavel: { unidade: "cm", fator: 100, casas: 1, faixa: 50 } },
  { indice: 14, grupo: "odometria", nome: "y_odo", unidade: "m", escala: 1, escalaTexto: "÷1 m",
    titulo: "posição estimada (esquerda)", ajuda: "odometria desde o arranque; + = para a esquerda",
    amigavel: { unidade: "cm", fator: 100, casas: 1, faixa: 50 } },
  { indice: 15, grupo: "validade", nome: "tof_ok", unidade: "0/1", escala: 1, escalaTexto: "0/1", flag: true,
    titulo: "sensor de altura (ToF) válido", ajuda: "o VL53L1X vê o chão dentro do alcance; sem ele a altura só vem do acelerómetro" },
  { indice: 16, grupo: "validade", nome: "fluxo_ok", unidade: "0/1", escala: 1, escalaTexto: "0/1", flag: true,
    titulo: "fluxo ótico válido", ajuda: "o PMW3901 tem textura/altura para medir; sem ele a velocidade horizontal decai para 0" },
  { indice: 17, grupo: "a_prev", nome: "a_prev·coletivo", unidade: "[-1,1]", escala: 1, escalaTexto: "1:1",
    titulo: "última ação · coletivo", ajuda: "o que a política pediu no passo anterior: −1 = sem empuxo, 0 = pairar, +1 = 2× o peso",
    amigavel: { unidade: "", fator: 1, casas: 2, faixa: 1 } },
  { indice: 18, grupo: "a_prev", nome: "a_prev·p", unidade: "[-1,1]", escala: 1, escalaTexto: "1:1",
    titulo: "última ação · taxa de rolamento", ajuda: "pedido ao controlador de voo, em fração do máximo",
    amigavel: { unidade: "", fator: 1, casas: 2, faixa: 1 } },
  { indice: 19, grupo: "a_prev", nome: "a_prev·q", unidade: "[-1,1]", escala: 1, escalaTexto: "1:1",
    titulo: "última ação · taxa de arfagem", ajuda: "pedido ao controlador de voo, em fração do máximo",
    amigavel: { unidade: "", fator: 1, casas: 2, faixa: 1 } },
  { indice: 20, grupo: "a_prev", nome: "a_prev·r", unidade: "[-1,1]", escala: 1, escalaTexto: "1:1",
    titulo: "última ação · taxa de guinada", ajuda: "pedido ao controlador de voo, em fração do máximo",
    amigavel: { unidade: "", fator: 1, casas: 2, faixa: 1 } },
]

/** Modo da ação na planta real: `ctbr` (por omissão do `env_real`) ou `motores` (4 aceleradores). */
export type ModoAcaoReal = "ctbr" | "motores"

/** `hardware.modo_acao` → modo; sem informação vale o padrão do `env_real` (`ctbr`). */
export function modoAcaoReal(bruto: string | null | undefined): ModoAcaoReal {
  return bruto === "motores" ? "motores" : "ctbr"
}

/** Rótulos da observação CERTOS para a planta (cf2: os 16 de sempre; real: os 21 do ator). */
export function rotulosObs(
  planta: Planta | null,
  modoAcao?: string | null
): RotuloObs[] {
  if (planta !== "real") return ROTULOS_OBS
  if (modoAcaoReal(modoAcao) === "ctbr") return ROTULOS_OBS_REAL
  // modo `motores`: a ação anterior são os 4 aceleradores, não coletivo + taxas
  return ROTULOS_OBS_REAL.map((r) =>
    r.grupo === "a_prev"
      ? {
          ...r,
          nome: `a_prev·r${r.indice - 16}`,
          titulo: `última ação · acelerador do motor ${r.indice - 16}`,
          ajuda: "acelerador pedido no passo anterior: −1 = 0 %, 0 = pairar, +1 = máximo",
        }
      : r
  )
}

/** Um canal da ação (o mesmo formato dos `ROTULOS_ACT` do cf2). */
export interface RotuloAct {
  indice: number
  nome: string
  canal: string
  unidade: string
}

/** Ação ctbr da planta real: coletivo de acelerador + taxas do corpo (o FC fecha a malha de taxa). */
export const ROTULOS_ACT_CTBR: readonly RotuloAct[] = [
  { indice: 0, nome: "a₀ · coletivo", canal: "acelerador", unidade: "[-1,1]" },
  { indice: 1, nome: "a₁ · taxa p", canal: "roll rate", unidade: "rad/s" },
  { indice: 2, nome: "a₂ · taxa q", canal: "pitch rate", unidade: "rad/s" },
  { indice: 3, nome: "a₃ · taxa r", canal: "yaw rate", unidade: "rad/s" },
]

/** Ação `motores` da planta real: um acelerador por rotor (sem FC). */
export const ROTULOS_ACT_MOTORES: readonly RotuloAct[] = [
  { indice: 0, nome: "a₀ · acelerador r1", canal: "motor 1", unidade: "[-1,1]" },
  { indice: 1, nome: "a₁ · acelerador r2", canal: "motor 2", unidade: "[-1,1]" },
  { indice: 2, nome: "a₂ · acelerador r3", canal: "motor 3", unidade: "[-1,1]" },
  { indice: 3, nome: "a₃ · acelerador r4", canal: "motor 4", unidade: "[-1,1]" },
]

/** Rótulos da ação CERTOS para a planta (cf2: empuxo + momentos; real: ctbr ou motores). */
export function rotulosAct(
  planta: Planta | null,
  modoAcao?: string | null
): readonly RotuloAct[] {
  if (planta !== "real") return ROTULOS_ACT
  return modoAcaoReal(modoAcao) === "motores"
    ? ROTULOS_ACT_MOTORES
    : ROTULOS_ACT_CTBR
}

/**
 * Setpoint de taxa (rad/s) que a ação ctbr pede ao FC: `clip(a, −1, 1) × TAXA_MAX` (o `env_real`
 * corta a ação a [−1, 1] antes de a aplicar). `eixo` 0 = p, 1 = q, 2 = r.
 */
export function setpointTaxa(
  a: number | null | undefined,
  eixo: 0 | 1 | 2,
  taxaMax: readonly [number, number, number] | null = null
): number | null {
  if (a === null || a === undefined || !Number.isFinite(a)) return null
  return Math.max(-1, Math.min(1, a)) * (taxaMax ?? TAXA_MAX_CTBR)[eixo]
}

/**
 * Empuxo pedido pelo COLETIVO como fração do PESO: o `DroneRealEnv` comanda u = u_pair(V)·√(1+a₀), linear
 * em empuxo — a₀ = −1 → 0, 0 → pairar (1× o peso), +1 → 2× o peso (`coletivoMaxPeso`).
 */
export function empuxoDoColetivo(
  a0: number | null | undefined,
  maxPeso: number | null = null
): number | null {
  if (a0 === null || a0 === undefined || !Number.isFinite(a0)) return null
  const m = maxPeso ?? COLETIVO_MAX_PESO
  return Math.max(0, 1 + Math.max(-1, Math.min(1, a0)) * (m - 1))
}

/**
 * Planta EM VIGOR: a da última linha da telemetria (é o que a física está mesmo a correr), senão a que
 * a API anunciar; `null` = ninguém diz (o site comporta-se como cf2).
 */
export function plantaEmVigor(
  linha: LinhaSim | null,
  ...anunciadas: (Planta | null | undefined)[]
): Planta | null {
  if (linha?.planta) return linha.planta
  for (const p of anunciadas) if (p) return p
  return null
}

/** Notação científica pt-PT curta (`1,234e-5`); não finito → "—". */
export function fmtExp(valor: number | null | undefined, casas = 3): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor))
    return "—"
  return valor.toExponential(casas).replace(".", ",")
}

/** Fração 0–1 → percentagem com casas fixas («99,29 %»); `null` → "—". */
export function fmtPct(fracao: number | null | undefined, casas = 1): string {
  if (fracao === null || fracao === undefined || !Number.isFinite(fracao))
    return "—"
  return `${fmt(fracao * 100, casas)} %`
}
