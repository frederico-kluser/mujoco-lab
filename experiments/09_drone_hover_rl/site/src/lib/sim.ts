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
}

export interface RespostaSim {
  estado: EstadoEpisodio
  ep: number
  passo: number
  retorno: number
  vento: VentoEstado
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
  return typeof bruto === "object" && bruto !== null ? (bruto as Record<string, unknown>) : {}
}

function estado(bruto: unknown): EstadoEpisodio {
  return bruto === "episodio_terminado" ? "episodio_terminado" : "a_correr"
}

function lerVento(bruto: unknown): VentoEstado {
  const o = objeto(bruto)
  const vel = numero(o.vel) ?? 0
  const azimute = numero(o.azimute) ?? 0
  const elevacao = numero(o.elevacao) ?? 0
  return { vel, azimute, elevacao, ativo: o.ativo === true || vel > 0 }
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
    vento: lerVento(o.vento),
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
  const nome = primeiro("modelo_nome", "nome_modelo", "modelo", "model", "politica", "policy", "run")
  const momentos = primeiro("momento_max", "momentos_max")
  const listaMomentos = Array.isArray(momentos) ? momentos.map((m) => numero(m)) : []
  const momentoMax =
    listaMomentos.length === 3 && listaMomentos.every((m) => m !== null)
      ? ([listaMomentos[0], listaMomentos[1], listaMomentos[2]] as [number, number, number])
      : null
  return {
    modelo: typeof nome === "string" && nome.length > 0 ? nome : null,
    mg: numero(primeiro("mg", "peso")),
    thrustMax: numero(primeiro("thrust_max", "empuxo_max")),
    momentoMax,
    tauEscala: numero(primeiro("tau_escala")),
    np: numero(primeiro("np", "np_random")),
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
  return [horizontal * Math.cos(az), horizontal * Math.sin(az), vento.vel * Math.sin(el)]
}

// --------------------------------------------------------------------------------------- formatação

/** Número → texto pt-PT com casas fixas; `null`/não finito → "—". */
export function fmt(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—"
  return valor.toLocaleString("pt-PT", { minimumFractionDigits: casas, maximumFractionDigits: casas })
}

/** Igual a `fmt`, com sinal explícito (para deltas e momentos). */
export function fmtSinal(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—"
  const texto = fmt(Math.abs(valor), casas)
  return valor < 0 ? `−${texto}` : `+${texto}`
}

export function fmtGraus(valor: number | null | undefined, casas = 0): string {
  return `${fmt(valor, casas)}°`
}

/** Inteiro com separador de milhares pt-PT; não finito → "—". */
export function fmtInteiro(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—"
  return Math.round(valor).toLocaleString("pt-PT")
}

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
export function derivarAct(linha: LinhaSim | null, constantes = FISICA_PADRAO): DerivadosAct | null {
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
    a0 <= 0 ? constantes.mg * (1 + a0) : constantes.mg + (constantes.thrustMax - constantes.mg) * a0
  const momentos = [0, 1, 2].map(
    (i) => constantes.tauEscala * constantes.momentoMax[i] * (a[i + 1] ?? 0),
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
  { indice: 0, grupo: "dp", nome: "dp_x", unidade: "m", escala: 1, escalaTexto: "÷1 m" },
  { indice: 1, grupo: "dp", nome: "dp_y", unidade: "m", escala: 1, escalaTexto: "÷1 m" },
  { indice: 2, grupo: "dp", nome: "dp_z", unidade: "m", escala: 1, escalaTexto: "÷1 m" },
  { indice: 3, grupo: "rpy", nome: "roll/π", unidade: "rad", escala: Math.PI, escalaTexto: "÷π" },
  { indice: 4, grupo: "rpy", nome: "pitch/π", unidade: "rad", escala: Math.PI, escalaTexto: "÷π" },
  { indice: 5, grupo: "rpy", nome: "yaw/π", unidade: "rad", escala: Math.PI, escalaTexto: "÷π" },
  { indice: 6, grupo: "v", nome: "v_x", unidade: "m/s", escala: 1, escalaTexto: "÷1 m/s" },
  { indice: 7, grupo: "v", nome: "v_y", unidade: "m/s", escala: 1, escalaTexto: "÷1 m/s" },
  { indice: 8, grupo: "v", nome: "v_z", unidade: "m/s", escala: 1, escalaTexto: "÷1 m/s" },
  { indice: 9, grupo: "ω", nome: "ω_x", unidade: "rad/s", escala: 10, escalaTexto: "÷10 rad/s" },
  { indice: 10, grupo: "ω", nome: "ω_y", unidade: "rad/s", escala: 10, escalaTexto: "÷10 rad/s" },
  { indice: 11, grupo: "ω", nome: "ω_z", unidade: "rad/s", escala: 10, escalaTexto: "÷10 rad/s" },
  { indice: 12, grupo: "a_prev", nome: "a_prev·empuxo", unidade: "[-1,1]", escala: 1, escalaTexto: "1:1" },
  { indice: 13, grupo: "a_prev", nome: "a_prev·mx", unidade: "[-1,1]", escala: 1, escalaTexto: "1:1" },
  { indice: 14, grupo: "a_prev", nome: "a_prev·my", unidade: "[-1,1]", escala: 1, escalaTexto: "1:1" },
  { indice: 15, grupo: "a_prev", nome: "a_prev·mz", unidade: "[-1,1]", escala: 1, escalaTexto: "1:1" },
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
