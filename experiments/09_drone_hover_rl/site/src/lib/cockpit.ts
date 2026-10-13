/**
 * COCKPIT (contrato r13, `INTERFACE.md` §0) — a lógica PURA do ecrã único. Sem DOM, sem `fetch`, sem
 * React: é a camada que os testes de node exercitam (`testes/cockpit.mts`) e que os componentes de
 * `components/cockpit/` só desenham.
 *
 *  · HUD — o parser tolerante da amostra de `GET /api/hud` (SSE a 50 Hz), as leituras dos instrumentos
 *    (primeiro `est` = sensores de bordo; `real` só onde não há `est`) e o estado em linguagem de voo
 *    (A VOAR · NO CHÃO · CAIU · SEM LIGAÇÃO — nunca «episódio»);
 *  · PROJEÇÃO — onde cai na VISTA (um `<img>` com `object-fit: cover`) um ponto da câmara de bordo: o
 *    retículo sobre a bola (`bola.erro_tan`) e o horizonte dos sensores;
 *  · TECLAS — o mapa do teclado e o estado do piloto (WASD/QE + Z/C/X) reduzido ao corpo COMPLETO do
 *    `POST /api/voo` (`ativo: true` sempre: o cockpit não tem «armar»);
 *  · VENTO (três botões) e BOLA — validação e limites dos corpos de `POST /api/vento-simples` e
 *    `POST /api/bola`, a bússola onde se arrasta a direção e o vento visto do nariz;
 *  · ENVIO — «o último vence» com intervalo mínimo (sliders ≤ 10 Hz + envio final ao largar);
 *  · JANELAS — abrir/fechar/focar/mover, encaixe no viewport e o que se guarda em `localStorage`;
 *  · CÂMARA — arrastar a vista em 3.ª pessoa = orbitar (a convenção de sinais do rato do MuJoCo).
 *
 * Convenções medidas no runner (2026-10-12, planta real em modo clássico) e usadas aqui:
 *  · referencial do drone = frente +x, esquerda +y, cima +z; `roll` > 0 = asa DIREITA em baixo,
 *    `pitch` > 0 = nariz em BAIXO (carregar em W dá `est.pitch` ≈ +0,18 rad), `psi` cresce para a ESQUERDA;
 *  · `est.vx`/`est.vy` e `real.vx`/`real.vy` vêm no referencial do RUMO (avanço, esquerda); o `voo.v_ref`
 *    vem no MUNDO; o vento vem no MUNDO e «para onde sopra»;
 *  · `bola.valido` (há deteção) é independente de `bola.estado` (o que o seguidor faz com ela).
 */

import type { CorpoVoo } from "./api.ts"
import { YAW_TAXA_TECLA, vRefRumoParaMundo } from "./controlador.ts"
import {
  TECLAS_VOO,
  TECLAS_VOO_ZERADAS,
  teclasIguais,
  vRefDeTeclas,
  type TeclaVoo,
  type TeclasVoo,
} from "./voo.ts"

const GRAUS = 180 / Math.PI

export type Par = readonly [number, number]
export type Trio = readonly [number, number, number]

// --------------------------------------------------------------------------------- leituras tolerantes

function objetoSimples(bruto: unknown): Record<string, unknown> | null {
  return typeof bruto === "object" && bruto !== null && !Array.isArray(bruto)
    ? (bruto as Record<string, unknown>)
    : null
}

/** Número finito ou `null` — sem aceitar strings: o HUD é JSON do nosso runner, não um formulário. */
function finito(bruto: unknown): number | null {
  return typeof bruto === "number" && Number.isFinite(bruto) ? bruto : null
}

function lerPar(bruto: unknown): [number, number] | null {
  if (!Array.isArray(bruto) || bruto.length < 2) return null
  const a = finito(bruto[0])
  const b = finito(bruto[1])
  return a === null || b === null ? null : [a, b]
}

function lerTrio(bruto: unknown): [number, number, number] | null {
  if (!Array.isArray(bruto) || bruto.length < 3) return null
  const a = finito(bruto[0])
  const b = finito(bruto[1])
  const c = finito(bruto[2])
  return a === null || b === null || c === null ? null : [a, b, c]
}

export function limitar(valor: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, valor))
}

/** Ângulo em graus reduzido a [0, 360). */
export function reduzirGraus(graus: number): number {
  const r = graus % 360
  return r < 0 ? r + 360 : r === 0 ? 0 : r
}

// --------------------------------------------------------------------------------- amostra do HUD

export const FASES_VOO = ["a_voar", "no_chao", "caiu"] as const
export type FaseVoo = (typeof FASES_VOO)[number]

/** `est` — o que os SENSORES de bordo dizem (rad, m, m/s; `vx`/`vy` no referencial do rumo). */
export interface HudEstimador {
  roll: number
  pitch: number
  psi: number
  h: number
  vx: number
  vy: number
  vz: number
}

/** `real` — a verdade do simulador. No cf2 só vêm `z` e `yaw`: cada campo é opcional. */
export interface HudReal {
  x: number | null
  y: number | null
  z: number | null
  roll: number | null
  pitch: number | null
  yaw: number | null
  vx: number | null
  vy: number | null
  vz: number | null
}

export interface HudBateria {
  /** Carga 0..1. */
  soc: number | null
  v: number | null
  i: number | null
  p: number | null
  autonomiaMin: number | null
  /** `""` (sem alerta) · `tensao_baixa` · `critica` — tal como o runner o escreve. */
  alerta: string
}

export interface HudVoo {
  ativo: boolean
  teclas: TeclasVoo
  /** Velocidade comandada que o runner aplica (m/s, MUNDO). */
  vRef: [number, number, number] | null
}

export interface HudControlador {
  modo: "rl" | "classico" | null
  estado: string | null
  motivo: string | null
  seguiAlvo: boolean
  /** ψ desde o armar (rad) — o que a tecla X fixa. */
  rumo: number | null
  yawTaxa: number
  yawAlvo: number | null
}

/** O que o DETETOR de bordo vê da bola (não a verdade do simulador). */
export interface HudBola {
  seguir: boolean
  /** Há deteção neste quadro (independente do estado do seguidor). */
  valido: boolean
  /** 0 A_SEGUIR · 1 EM_FALTA · 2 PERDIDO · 3 REAQUISIÇÃO. */
  estado: number | null
  erroPx: [number, number] | null
  raioPx: number | null
  /** Resolução da câmara do detetor (px) — a escala de `erroPx`. */
  camara: [number, number] | null
  /** FoV vertical da câmara de bordo (graus). */
  fovy: number | null
  /** Erro de centragem ÷ distância focal (x para a direita, y para baixo). */
  erroTan: [number, number] | null
  raioTan: number | null
  dist: number | null
  vel: number | null
  alvoMundo: [number, number, number] | null
}

export interface AmostraHud {
  t: number
  passo: number
  ep: number
  pausado: boolean
  /** `null` = o runner mandou uma fase que este site não conhece (mostra-se «—», não se adivinha). */
  fase: FaseVoo | null
  /** Vento que a física leva AGORA (m/s, MUNDO, para onde sopra). */
  vento: [number, number, number] | null
  ventoModo: string | null
  rajada: boolean
  est: HudEstimador | null
  real: HudReal | null
  bateria: HudBateria | null
  /** Duty de cada motor, 0..1. */
  motores: number[] | null
  voo: HudVoo | null
  controlador: HudControlador | null
  /** `null` enquanto o modo bola nunca foi ligado. */
  bola: HudBola | null
  /** FoV vertical da câmara de bordo (graus), publicado SEMPRE; `null` = runner sem câmara ou antigo. */
  fovy: number | null
  /**
   * O vento que o drone SENTE a bordo (o observador de perturbação da cascata clássica convertido em m/s —
   * uma estimativa, o drone não tem anemómetro); `null` com a política RL, no cf2 ou num runner antigo.
   */
  ventoBordo: HudVentoBordo | null
}

export interface HudVentoBordo {
  /** Velocidade de vento equivalente (m/s); 0 = abaixo do piso do observador. */
  vel: number
  /** Para onde o ar empurra (graus, 0° = +x, 90° = +y — a convenção do vento do cockpit). */
  direcao: number
}

/** Abaixo disto a estimativa de bordo é ruído do observador (medido: 0,2–0,5 m/s em ar parado). */
export const VENTO_BORDO_CALMO_M_S = 0.6

function lerVentoBordo(bruto: unknown): HudVentoBordo | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const vel = finito(o.vel)
  const direcao = finito(o.direcao)
  return vel === null || direcao === null || vel < 0
    ? null
    : { vel, direcao: reduzirGraus(direcao) }
}

/** Texto do vento sentido a bordo para a janela Vento: `≈ 2,8 m/s para 087°`, `calmo` ou `—`. */
export function textoVentoBordo(vento: HudVentoBordo | null): string {
  if (vento === null) return "—"
  if (vento.vel < VENTO_BORDO_CALMO_M_S) return "calmo"
  return `≈ ${vento.vel.toFixed(1).replace(".", ",")} m/s para ${String(Math.round(reduzirGraus(vento.direcao)) % 360).padStart(3, "0")}°`
}

function lerEstimador(bruto: unknown): HudEstimador | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const roll = finito(o.roll)
  const pitch = finito(o.pitch)
  const psi = finito(o.psi)
  const h = finito(o.h)
  const vx = finito(o.vx)
  const vy = finito(o.vy)
  const vz = finito(o.vz)
  // Um estimador com um campo em falta não é um estimador: cai-se para `real` em vez de pôr um zero
  // inventado num instrumento.
  if (
    roll === null ||
    pitch === null ||
    psi === null ||
    h === null ||
    vx === null ||
    vy === null ||
    vz === null
  )
    return null
  return { roll, pitch, psi, h, vx, vy, vz }
}

function lerReal(bruto: unknown): HudReal | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  return {
    x: finito(o.x),
    y: finito(o.y),
    z: finito(o.z),
    roll: finito(o.roll),
    pitch: finito(o.pitch),
    yaw: finito(o.yaw),
    vx: finito(o.vx),
    vy: finito(o.vy),
    vz: finito(o.vz),
  }
}

function lerBateriaHud(bruto: unknown): HudBateria | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  return {
    soc: finito(o.soc),
    v: finito(o.v),
    i: finito(o.i),
    p: finito(o.p),
    autonomiaMin: finito(o.autonomia_min),
    alerta: typeof o.alerta === "string" ? o.alerta : "",
  }
}

function lerTeclasHud(bruto: unknown): TeclasVoo {
  const o = objetoSimples(bruto)
  const teclas: TeclasVoo = { ...TECLAS_VOO_ZERADAS }
  if (o === null) return teclas
  for (const tecla of TECLAS_VOO) teclas[tecla] = o[tecla] === true
  return teclas
}

function lerVooHud(bruto: unknown): HudVoo | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  return {
    ativo: o.ativo === true,
    teclas: lerTeclasHud(o.teclas),
    vRef: lerTrio(o.v_ref),
  }
}

function lerControladorHud(bruto: unknown): HudControlador | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  return {
    modo: o.modo === "rl" || o.modo === "classico" ? o.modo : null,
    estado: typeof o.estado === "string" ? o.estado : null,
    motivo: typeof o.motivo === "string" && o.motivo.length > 0 ? o.motivo : null,
    seguiAlvo: o.segui_alvo === true,
    rumo: finito(o.rumo),
    yawTaxa: finito(o.yaw_taxa) ?? 0,
    yawAlvo: finito(o.yaw_alvo),
  }
}

function lerBolaHud(bruto: unknown): HudBola | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const estado = finito(o.estado)
  return {
    seguir: o.seguir === true,
    valido: o.valido === true,
    estado: estado === null ? null : Math.trunc(estado),
    erroPx: lerPar(o.erro_px),
    raioPx: finito(o.raio_px),
    camara: lerPar(o.camara),
    fovy: finito(o.fovy),
    erroTan: lerPar(o.erro_tan),
    raioTan: finito(o.raio_tan),
    dist: finito(o.dist),
    vel: finito(o.vel),
    alvoMundo: lerTrio(o.alvo_mundo),
  }
}

/**
 * Uma amostra do HUD (o `data:` de um evento do SSE, já em objeto) → `AmostraHud`, ou `null` quando
 * não é uma amostra (sem `t` nem `passo`). Nunca lança e nunca inventa: o que não vier fica `null`.
 */
export function lerHud(bruto: unknown): AmostraHud | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const t = finito(o.t)
  const passo = finito(o.passo)
  if (t === null && passo === null) return null
  const motores = Array.isArray(o.motores)
    ? o.motores.map((m) => limitar(finito(m) ?? 0, 0, 1))
    : null
  return {
    t: t ?? 0,
    passo: passo ?? 0,
    ep: finito(o.ep) ?? 0,
    pausado: o.pausado === true,
    fase: (FASES_VOO as readonly unknown[]).includes(o.fase)
      ? (o.fase as FaseVoo)
      : null,
    vento: lerTrio(o.vento),
    ventoModo: typeof o.vento_modo === "string" ? o.vento_modo : null,
    rajada: o.rajada === true,
    est: lerEstimador(o.est),
    real: lerReal(o.real),
    bateria: lerBateriaHud(o.bateria),
    motores: motores !== null && motores.length > 0 ? motores : null,
    voo: lerVooHud(o.voo),
    controlador: lerControladorHud(o.controlador),
    bola: lerBolaHud(o.bola),
    fovy: finito(o.fovy),
    ventoBordo: lerVentoBordo(o.vento_bordo),
  }
}

/** O `data:` de um evento do SSE (texto) → amostra; lixo (JSON partido, comentário) = `null`. */
export function lerEventoHud(texto: string): AmostraHud | null {
  try {
    return lerHud(JSON.parse(texto))
  } catch {
    return null
  }
}

/** `GET /api/hud.json` → a última amostra e a idade que o SERVIDOR lhe dá (o fallback do SSE). */
export function lerHudJson(bruto: unknown): {
  hud: AmostraHud | null
  idadeS: number | null
  velho: boolean
} {
  const o = objetoSimples(bruto) ?? {}
  return {
    hud: lerHud(o.hud),
    idadeS: finito(o.idade_s),
    velho: o.velho === true,
  }
}

// --------------------------------------------------------------------------------- instrumentos

/** Rumo em graus [0, 360) a partir de ψ (rad): cresce para a ESQUERDA, como o azimute do vento. */
export function rumoEmGraus(psi: number): number {
  return reduzirGraus(psi * GRAUS)
}

export interface Instrumentos {
  /** rad; > 0 = asa direita em baixo. */
  roll: number | null
  /** rad; > 0 = nariz em baixo. */
  pitch: number | null
  /** graus [0, 360), desde o armar, a crescer para a esquerda. */
  rumo: number | null
  altitude: number | null
  vVertical: number | null
  /** Módulo da velocidade horizontal (m/s) e as componentes vistas do nariz. */
  vHorizontal: number | null
  vFrente: number | null
  vEsquerda: number | null
  /** De onde vêm os números: os sensores de bordo, ou (sem estimador) a verdade do simulador. */
  fonte: "sensores" | "simulador" | null
}

const SEM_INSTRUMENTOS: Instrumentos = {
  roll: null,
  pitch: null,
  rumo: null,
  altitude: null,
  vVertical: null,
  vHorizontal: null,
  vFrente: null,
  vEsquerda: null,
  fonte: null,
}

/**
 * As leituras dos instrumentos do HUD: `est` (o que um piloto real veria) e, só quando não há
 * estimador (cf2), os campos de `real` que existirem — o resto fica `null` e o instrumento mostra «—».
 */
export function instrumentos(hud: AmostraHud | null): Instrumentos {
  if (hud === null) return SEM_INSTRUMENTOS
  const e = hud.est
  if (e !== null) {
    return {
      roll: e.roll,
      pitch: e.pitch,
      rumo: rumoEmGraus(e.psi),
      altitude: e.h,
      vVertical: e.vz,
      vHorizontal: Math.hypot(e.vx, e.vy),
      vFrente: e.vx,
      vEsquerda: e.vy,
      fonte: "sensores",
    }
  }
  const r = hud.real
  if (r === null) return SEM_INSTRUMENTOS
  return {
    roll: r.roll,
    pitch: r.pitch,
    rumo: r.yaw === null ? null : rumoEmGraus(r.yaw),
    altitude: r.z,
    vVertical: r.vz,
    vHorizontal: r.vx === null || r.vy === null ? null : Math.hypot(r.vx, r.vy),
    vFrente: r.vx,
    vEsquerda: r.vy,
    fonte: "simulador",
  }
}

/** Yaw no MUNDO (rad) para rodar grandezas do mundo para o nariz: a verdade, senão o ψ de bordo. */
export function yawNoMundo(hud: AmostraHud | null): number | null {
  if (hud === null) return null
  return hud.real?.yaw ?? hud.est?.psi ?? null
}

/** Rumo que a tecla X fixa: o `controlador.rumo` do runner, senão o ψ do estimador. */
export function rumoParaFixar(hud: AmostraHud | null): number | null {
  if (hud === null) return null
  return hud.controlador?.rumo ?? hud.est?.psi ?? null
}

// --------------------------------------------------------------------------------- estado de voo

/** Uma amostra com mais do que isto está velha: o HUD passa a SEM LIGAÇÃO. */
export const IDADE_MAX_HUD_MS = 1000
/** No arranque espera-se isto pela primeira amostra antes de dizer SEM LIGAÇÃO. */
export const ESPERA_ARRANQUE_HUD_MS = 2500

export type LigacaoHud = "a_ligar" | "ligado" | "sem_ligacao"

/**
 * Há ligação ao runner? Só conta a FRESCURA da última amostra (venha do SSE ou do fallback
 * `hud.json`): o SSE pode estar aberto com o runner parado, e o inverso.
 */
export function ligacaoHud(entrada: {
  /** Idade da última amostra (ms); `null` = ainda não chegou nenhuma. */
  idadeMs: number | null
  /** Há quanto tempo o cockpit tenta ligar (ms). */
  desdeArranqueMs: number
}): LigacaoHud {
  if (entrada.idadeMs !== null)
    return entrada.idadeMs <= IDADE_MAX_HUD_MS ? "ligado" : "sem_ligacao"
  return entrada.desdeArranqueMs <= ESPERA_ARRANQUE_HUD_MS
    ? "a_ligar"
    : "sem_ligacao"
}

/**
 * Tom de um estado — sempre acompanhado de TEXTO e de uma FORMA (nunca só cor): `ativo` = verde ●,
 * `atencao` = âmbar ▲, `perigo` = vermelho ■, `normal` = branco ○.
 */
export type TomEstado = "normal" | "ativo" | "atencao" | "perigo"

export type IdEstadoVoo =
  | "a_voar"
  | "no_chao"
  | "caiu"
  | "em_pausa"
  | "a_ligar"
  | "sem_ligacao"
  | "desconhecido"

export interface EstadoDeVoo {
  id: IdEstadoVoo
  texto: string
  tom: TomEstado
  /** Quem manda no movimento: as teclas ou o seguidor da bola (`null` sem ligação). */
  modo: "manual" | "bola" | null
  textoModo: string | null
}

/** Texto e tom de cada estado (a pílula do HUD lê-os daqui a partir do resumo lento). */
export const ESTADOS_VOO: Record<IdEstadoVoo, { texto: string; tom: TomEstado }> = {
  a_voar: { texto: "A VOAR", tom: "ativo" },
  no_chao: { texto: "NO CHÃO", tom: "normal" },
  caiu: { texto: "CAIU", tom: "perigo" },
  em_pausa: { texto: "EM PAUSA", tom: "atencao" },
  a_ligar: { texto: "A LIGAR", tom: "normal" },
  sem_ligacao: { texto: "SEM LIGAÇÃO", tom: "atencao" },
  desconhecido: { texto: "—", tom: "normal" },
}

/** A pílula de estado em linguagem de voo (o que o piloto lê primeiro). */
export function estadoDeVoo(
  hud: AmostraHud | null,
  ligacao: LigacaoHud
): EstadoDeVoo {
  let id: IdEstadoVoo
  if (ligacao !== "ligado" || hud === null) {
    id = ligacao === "a_ligar" ? "a_ligar" : "sem_ligacao"
  } else if (hud.fase === "caiu") {
    // CAIU vence a pausa: é o estado que pede uma ação (manter R).
    id = "caiu"
  } else if (hud.pausado) {
    id = "em_pausa"
  } else {
    id = hud.fase ?? "desconhecido"
  }
  const ligado = id !== "a_ligar" && id !== "sem_ligacao"
  const bola = ligado && hud?.controlador?.seguiAlvo === true
  return {
    id,
    ...ESTADOS_VOO[id],
    modo: ligado ? (bola ? "bola" : "manual") : null,
    textoModo: ligado ? (bola ? "A SEGUIR A BOLA" : "MANUAL") : null,
  }
}

// --------------------------------------------------------------------------------- bola (seguidor)

export type EstadoSeguidor = "desligado" | "a_seguir" | "a_procura" | "perdida"

export const ROTULO_SEGUIDOR: Record<EstadoSeguidor, string> = {
  desligado: "DESLIGADO",
  a_seguir: "A SEGUIR",
  a_procura: "À PROCURA",
  perdida: "PERDIDA",
}

/** Perder a bola é ATENÇÃO, não perigo: o vermelho fica para o que ameaça o voo (queda, bateria). */
export const TOM_SEGUIDOR: Record<EstadoSeguidor, TomEstado> = {
  desligado: "normal",
  a_seguir: "ativo",
  a_procura: "atencao",
  perdida: "atencao",
}

/**
 * O estado do seguidor em três palavras. `estado` do núcleo: 0 A_SEGUIR · 1 EM_FALTA · 2 PERDIDO ·
 * 3 REAQUISIÇÃO — «em falta» e «reaquisição» são as duas faces de À PROCURA; e um A_SEGUIR sem deteção
 * neste quadro também não é «a seguir».
 */
export function estadoSeguidor(bola: HudBola | null): EstadoSeguidor {
  if (bola === null || !bola.seguir) return "desligado"
  if (bola.estado === 2) return "perdida"
  if (bola.estado === 0 && bola.valido) return "a_seguir"
  return "a_procura"
}

/** Erro de centragem da bola: o ângulo ao eixo da câmara (graus) e os píxeis do detetor. */
export function erroCentragem(
  bola: HudBola | null
): { graus: number; px: number | null } | null {
  if (bola === null || !bola.valido || bola.erroTan === null) return null
  return {
    graus: Math.atan(Math.hypot(bola.erroTan[0], bola.erroTan[1])) * GRAUS,
    px: bola.erroPx === null ? null : Math.hypot(bola.erroPx[0], bola.erroPx[1]),
  }
}

/** Bloco `bola` do `/api/state`: a velocidade da bola aleatória e a faixa que o slider pode usar. */
export interface BolaConfig {
  velocidade: number
  min: number
  max: number
}

export function lerBolaConfig(bruto: unknown): BolaConfig | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const velocidade = finito(o.velocidade)
  const min = finito(o.min)
  const max = finito(o.max)
  if (velocidade === null || min === null || max === null || !(max > min))
    return null
  return { velocidade: limitar(velocidade, min, max), min, max }
}

/** Passo do slider da bola (m/s). */
export const PASSO_BOLA = 0.05

/** Velocidade pedida → valor que o `POST /api/bola` aceita (dentro da faixa, no passo do slider). */
export function limitarVelocidadeBola(valor: number, cfg: BolaConfig): number {
  if (!Number.isFinite(valor)) return cfg.velocidade
  const noPasso = Math.round(valor / PASSO_BOLA) * PASSO_BOLA
  return Number(limitar(noPasso, cfg.min, cfg.max).toFixed(2))
}

// --------------------------------------------------------------------------------- resumo lento

export type AlertaBateriaHud = "nenhum" | "fraca" | "critica"

/** Alerta de bateria do runner (`""` · `tensao_baixa` · `critica`) nos três níveis do HUD. */
export function alertaBateria(bateria: HudBateria | null): AlertaBateriaHud {
  if (bateria === null) return "nenhum"
  if (bateria.alerta === "critica") return "critica"
  return bateria.alerta === "tensao_baixa" ? "fraca" : "nenhum"
}

/**
 * O que do HUD muda DEVAGAR (segundos, não milissegundos): é só isto que entra no estado do React.
 * Tudo o que mexe a 50 Hz desenha-se por refs num `requestAnimationFrame` (ver `lib/hud-store.ts`).
 */
export interface ResumoHud {
  ligacao: LigacaoHud
  estado: IdEstadoVoo
  modo: "manual" | "bola" | null
  seguidor: EstadoSeguidor
  /** O modo bola já foi ligado alguma vez nesta sessão do runner (há bloco `bola`). */
  temBola: boolean
  bateria: AlertaBateriaHud
  temBateria: boolean
  temEstimador: boolean
  /**
   * O runner aceita comandos de voo? `false` = a amostra vem sem bloco `voo` (uma política que não foi
   * treinada para obedecer às teclas): o cockpit di-lo em vez de as deixar premir em silêncio.
   */
  aceitaComandos: boolean
  controlador: "rl" | "classico" | null
  /** FoV vertical da câmara de bordo que o runner publicou (graus); `null` = ainda não o disse. */
  fovy: number | null
}

export const RESUMO_HUD_INICIAL: ResumoHud = {
  ligacao: "a_ligar",
  estado: "a_ligar",
  modo: null,
  seguidor: "desligado",
  temBola: false,
  bateria: "nenhum",
  temBateria: false,
  temEstimador: false,
  aceitaComandos: true,
  controlador: null,
  fovy: null,
}

export function resumirHud(
  hud: AmostraHud | null,
  ligacao: LigacaoHud
): ResumoHud {
  const estado = estadoDeVoo(hud, ligacao)
  const vivo = hud !== null && ligacao === "ligado"
  return {
    ligacao,
    estado: estado.id,
    modo: estado.modo,
    seguidor: vivo ? estadoSeguidor(hud.bola) : "desligado",
    temBola: hud?.bola != null,
    bateria: vivo ? alertaBateria(hud.bateria) : "nenhum",
    temBateria: hud?.bateria != null,
    temEstimador: hud?.est != null,
    // Sem amostra não se afirma que NÃO aceita: só uma amostra viva sem bloco `voo` o diz.
    aceitaComandos: !vivo || hud.voo !== null,
    controlador: hud?.controlador?.modo ?? null,
    fovy: hud?.fovy ?? hud?.bola?.fovy ?? null,
  }
}

export function resumoIgual(a: ResumoHud, b: ResumoHud): boolean {
  return (
    a.ligacao === b.ligacao &&
    a.estado === b.estado &&
    a.modo === b.modo &&
    a.seguidor === b.seguidor &&
    a.temBola === b.temBola &&
    a.bateria === b.bateria &&
    a.temBateria === b.temBateria &&
    a.temEstimador === b.temEstimador &&
    a.aceitaComandos === b.aceitaComandos &&
    a.controlador === b.controlador &&
    a.fovy === b.fovy
  )
}

// --------------------------------------------------------------------------------- projeção na vista

/**
 * FoV vertical da câmara de bordo (graus) quando o HUD ainda não o disse. O runner publica-o em todas as
 * amostras (`fovy`, e também em `bola.fovy`); este valor só entra antes da 1.ª amostra ou com um runner
 * antigo, e é o do módulo do build ativo (Pi Camera Module 3 Wide, modo de FoV completo: 67°). É uma
 * SUPOSIÇÃO declarada — a janela Sistema diz qual dos dois está em uso.
 */
export const FOVY_BORDO_OMISSAO = 67

/**
 * Fator de escala de um `<img>` com `object-fit: cover`: a imagem cobre a vista sem deformar, logo
 * escala pelo MAIOR dos dois rácios e o que sobra é cortado (centrado).
 */
export function escalaCover(imagem: Par, vista: Par): number {
  if (!(imagem[0] > 0) || !(imagem[1] > 0)) return 1
  return Math.max(vista[0] / imagem[0], vista[1] / imagem[1])
}

/**
 * Distância focal NA VISTA (px do ecrã por unidade de tangente): a focal do stream
 * (`(H/2)/tan(fovy/2)`, contrato §0.6) vezes a escala do `cover`.
 */
export function focalNaVista(fovyGraus: number, imagem: Par, vista: Par): number {
  const meio = (limitar(fovyGraus, 1, 179) / 2) * (Math.PI / 180)
  return (imagem[1] / 2 / Math.tan(meio)) * escalaCover(imagem, vista)
}

/**
 * Onde cai na vista (px, origem no canto superior esquerdo) um ponto da câmara de bordo dado em
 * tangentes ao eixo ótico (`bola.erro_tan`: x para a direita, y para baixo). O centro da imagem fica
 * no centro da vista (o `cover` corta por igual dos dois lados).
 */
export function projetarNaVista(
  tan: Par,
  focal: number,
  vista: Par
): { x: number; y: number; visivel: boolean } {
  const x = vista[0] / 2 + tan[0] * focal
  const y = vista[1] / 2 + tan[1] * focal
  return {
    x,
    y,
    visivel: x >= 0 && x <= vista[0] && y >= 0 && y <= vista[1],
  }
}

/**
 * Há quanto tempo foi captado o quadro que está no ecrã (ms) — é com a amostra DESSE instante que se
 * desenham o horizonte e o retículo, para assentarem na imagem. Duas parcelas, ambas publicadas pelo
 * backend: a latência do módulo de câmara (`fpv.latencia_modelada_ms`, ~116 ms: cada quadro só é
 * entregue esse tempo depois de captado) e, em média, meio período do stream (`fpv.fps_medido`: o
 * quadro à vista tem entre 0 e 1 período de idade). O que o browser e a rede acrescentam não se mede.
 */
export function atrasoDaImagem(
  latenciaMs: number | null | undefined,
  fpsMedido: number | null | undefined
): number {
  const latencia =
    typeof latenciaMs === "number" && Number.isFinite(latenciaMs) && latenciaMs > 0
      ? latenciaMs
      : 0
  // Abaixo de 5 fps o «meio período» deixava de ser uma média útil: trava-se em 100 ms.
  const meioPeriodo =
    typeof fpsMedido === "number" && Number.isFinite(fpsMedido) && fpsMedido > 0
      ? 500 / Math.max(fpsMedido, 5)
      : 0
  return latencia + meioPeriodo
}

/** Inclinação máxima que o horizonte desenha (a tangente rebenta a 90°). */
const PITCH_MAX_HORIZONTE = (80 * Math.PI) / 180

/**
 * O horizonte dos SENSORES sobre a imagem da câmara de bordo (que olha para +x, solidária com o corpo):
 * o roll é uma rotação da imagem à volta do centro e o pitch desloca a linha ao longo da vertical já
 * rodada. Sinais (CSS: y para baixo, rotação positiva = horária):
 *  · nariz em baixo (`pitch` > 0) ⇒ o horizonte SOBE (deslocamento negativo);
 *  · asa direita em baixo (`roll` > 0) ⇒ o chão sobe do lado direito ⇒ a linha roda no sentido
 *    ANTI-horário (rotação negativa).
 * Aplica-se como `rotate(rotacao) translateY(deslocamento)`.
 */
export function horizonteNaVista(
  roll: number,
  pitch: number,
  focal: number
): { rotacaoGraus: number; deslocamentoPx: number } {
  const p = limitar(pitch, -PITCH_MAX_HORIZONTE, PITCH_MAX_HORIZONTE)
  return {
    rotacaoGraus: -roll * GRAUS,
    deslocamentoPx: -Math.tan(p) * focal,
  }
}

// --------------------------------------------------------------------------------- vento

/** Bloco `vento_simples` (os três botões + a direção). */
export interface VentoSimples {
  ligado: boolean
  /** Velocidade média (m/s). */
  intensidade: number
  /** `true` = a mesma média + turbulência + rajadas + direção a deambular. */
  aleatorio: boolean
  /** Para onde sopra (graus; 0° = +x, 90° = +y). */
  direcao: number
}

export const VENTO_SIMPLES_LIMITES = {
  intensidade: [0, 5] as const,
  /** Passo do slider (m/s). */
  passo: 0.1,
}

/** O que o backend assume quando o bloco ainda não existe (`VENTO_SIMPLES_PADRAO` do `sim_site.py`). */
export const VENTO_SIMPLES_PADRAO: VentoSimples = {
  ligado: false,
  intensidade: 2,
  aleatorio: false,
  direcao: 0,
}

/** Bloco `vento_simples` do `/api/state` → `VentoSimples`, ou `null` (não existe / malformado). */
export function lerVentoSimples(bruto: unknown): VentoSimples | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const intensidade = finito(o.intensidade)
  const direcao = finito(o.direcao)
  if (
    typeof o.ligado !== "boolean" ||
    typeof o.aleatorio !== "boolean" ||
    intensidade === null ||
    direcao === null
  )
    return null
  return {
    ligado: o.ligado,
    intensidade: limitar(
      intensidade,
      VENTO_SIMPLES_LIMITES.intensidade[0],
      VENTO_SIMPLES_LIMITES.intensidade[1]
    ),
    aleatorio: o.aleatorio,
    direcao: reduzirGraus(direcao),
  }
}

/**
 * Corpo do `POST /api/vento-simples` a partir de uma alteração do painel: só as chaves do contrato,
 * booleanos estritos, intensidade dentro de 0–5 m/s (no passo do slider) e direção em [0, 360) ao
 * grau. O que vier inválido (NaN, tipo errado) fica de FORA — o servidor recusa chaves desconhecidas e
 * um corpo vazio, por isso `null` = nada para enviar.
 */
export function corpoVentoSimples(
  alteracao: Partial<Record<keyof VentoSimples, unknown>>
): Partial<VentoSimples> | null {
  const corpo: Partial<VentoSimples> = {}
  if (typeof alteracao.ligado === "boolean") corpo.ligado = alteracao.ligado
  if (typeof alteracao.aleatorio === "boolean")
    corpo.aleatorio = alteracao.aleatorio
  const intensidade = finito(alteracao.intensidade)
  if (intensidade !== null) {
    const [min, max] = VENTO_SIMPLES_LIMITES.intensidade
    const passo = VENTO_SIMPLES_LIMITES.passo
    corpo.intensidade = Number(
      limitar(Math.round(intensidade / passo) * passo, min, max).toFixed(1)
    )
  }
  const direcao = finito(alteracao.direcao)
  if (direcao !== null) corpo.direcao = reduzirGraus(Math.round(direcao))
  return Object.keys(corpo).length > 0 ? corpo : null
}

/**
 * BÚSSOLA do vento (vista de cima, MUNDO): a frente da descolagem (+x, 0°) fica para CIMA e a
 * esquerda (+y, 90°) para a ESQUERDA — os mesmos eixos da vista de cima da câmara. Devolve onde
 * desenhar a ponta da seta «para onde sopra» (unitário; `sx` para a direita, `sy` para baixo).
 */
export function pontoBussola(direcaoGraus: number): { sx: number; sy: number } {
  const d = (direcaoGraus * Math.PI) / 180
  // mundo (wx, wy) → ecrã (−wy, −wx)
  return { sx: -Math.sin(d), sy: -Math.cos(d) }
}

/** Inverso de `pontoBussola`: a direção de um ponto arrastado (px relativos ao centro) ou `null` no centro. */
export function direcaoDePontoBussola(
  sx: number,
  sy: number,
  minimo = 4
): number | null {
  if (Math.hypot(sx, sy) < minimo) return null
  return reduzirGraus(Math.round(Math.atan2(-sx, -sy) * GRAUS))
}

/** Abaixo disto o vento é «calmo»: a seta não tem direção que valha a pena mostrar. */
export const VENTO_CALMO_M_S = 0.05

export type DeOndeVemVento = "frente" | "cauda" | "esquerda" | "direita"

export const ROTULO_DE_ONDE: Record<DeOndeVemVento, string> = {
  frente: "DE FRENTE",
  cauda: "DE CAUDA",
  esquerda: "DA ESQUERDA",
  direita: "DA DIREITA",
}

export interface VentoNoNariz {
  /** Módulo do vento (m/s, os três eixos). */
  vel: number
  /**
   * Para onde o vento EMPURRA, visto de cima com o nariz para cima (graus, sentido anti-horário):
   * 0 = para a frente (vento de cauda), 90 = para a esquerda, 180 = para trás (vento de frente).
   * `null` com o vento calmo.
   */
  angulo: number | null
  de: DeOndeVemVento | null
}

/** O vento do mundo visto do NARIZ (roda-se o vetor por −yaw). */
export function ventoNoNariz(vento: Trio | null, yaw: number | null): VentoNoNariz {
  if (vento === null) return { vel: 0, angulo: null, de: null }
  const vel = Math.hypot(vento[0], vento[1], vento[2])
  const horizontal = Math.hypot(vento[0], vento[1])
  if (horizontal < VENTO_CALMO_M_S || yaw === null)
    return { vel, angulo: null, de: null }
  const c = Math.cos(yaw)
  const s = Math.sin(yaw)
  const frente = c * vento[0] + s * vento[1]
  const esquerda = -s * vento[0] + c * vento[1]
  const de: DeOndeVemVento =
    Math.abs(frente) >= Math.abs(esquerda)
      ? frente < 0
        ? "frente"
        : "cauda"
      : esquerda > 0
        ? "direita"
        : "esquerda"
  return { vel, angulo: reduzirGraus(Math.atan2(esquerda, frente) * GRAUS), de }
}

// --------------------------------------------------------------------------------- teclas e piloto

/** Teclas de rodar (manter): Z = esquerda, C = direita. */
export const TECLAS_RODAR = ["z", "c"] as const
export type TeclaRodar = (typeof TECLAS_RODAR)[number]

/** O que uma tecla faz no cockpit (`INTERFACE.md` §0.3). */
export type AcaoTecla =
  | { tipo: "voo"; tecla: TeclaVoo }
  | { tipo: "rodar"; tecla: TeclaRodar }
  | { tipo: "fixar_rumo" }
  | { tipo: "bola" }
  | { tipo: "vento" }
  | { tipo: "vista" }
  | { tipo: "reiniciar" }
  | { tipo: "janela"; indice: number }
  | { tipo: "ajuda" }
  | { tipo: "fechar" }

/**
 * `evento.key` → ação, ou `null` (a tecla não é do cockpit). Com Ctrl/Meta/Alt nunca se intercepta:
 * Ctrl+W, Ctrl+R e companhia são do browser. A caixa não conta (CapsLock/Shift não desligam o voo).
 */
export function acaoDaTecla(
  key: string,
  modificadores: { ctrl?: boolean; meta?: boolean; alt?: boolean } = {}
): AcaoTecla | null {
  if (modificadores.ctrl || modificadores.meta || modificadores.alt) return null
  if (key === "Escape") return { tipo: "fechar" }
  if (key === "?") return { tipo: "ajuda" }
  const k = key.length === 1 ? key.toLowerCase() : key
  if ((TECLAS_VOO as readonly string[]).includes(k))
    return { tipo: "voo", tecla: k as TeclaVoo }
  if (k === "z" || k === "c") return { tipo: "rodar", tecla: k }
  if (k === "x") return { tipo: "fixar_rumo" }
  if (k === "b") return { tipo: "bola" }
  if (k === "v") return { tipo: "vento" }
  if (k === "f") return { tipo: "vista" }
  if (k === "r") return { tipo: "reiniciar" }
  if (k.length === 1 && k >= "1" && k <= "8")
    return { tipo: "janela", indice: Number(k) - 1 }
  return null
}

/** Tipos de `<input>` que NÃO são texto: com o foco neles as teclas de voo continuam a mandar. */
const INPUTS_SEM_TEXTO = new Set([
  "range",
  "checkbox",
  "radio",
  "button",
  "submit",
  "reset",
  "color",
  "file",
  "image",
])

/**
 * O foco está num campo onde se ESCREVE? Só aí o cockpit larga o teclado. Um slider (`input[range]`)
 * ou um botão com foco não contam: senão, depois de arrastar a intensidade do vento, o W deixava de
 * voar sem razão aparente.
 */
export function eCampoDeTexto(
  alvo: {
    tagName?: string
    type?: string | null
    isContentEditable?: boolean
  } | null
): boolean {
  if (alvo === null || typeof alvo.tagName !== "string") return false
  if (alvo.isContentEditable === true) return true
  const etiqueta = alvo.tagName.toLowerCase()
  if (etiqueta === "textarea" || etiqueta === "select") return true
  if (etiqueta !== "input") return false
  return !INPUTS_SEM_TEXTO.has((alvo.type ?? "text").toLowerCase())
}

/**
 * O que o piloto está a mandar AGORA — o estado LOCAL (otimista) de onde sai o corpo do
 * `POST /api/voo`. `z`/`c` guardam as teclas (a taxa de guinada deriva-se), para Z+C dar zero e largar
 * uma delas voltar a rodar para o lado da outra.
 */
export interface EstadoPiloto {
  teclas: TeclasVoo
  z: boolean
  c: boolean
  /** Rumo fixado (rad desde o armar) ou `null` = livre. */
  yaw_alvo: number | null
  /** SEGUIR A BOLA. */
  segui_alvo: boolean
}

export const PILOTO_INICIAL: EstadoPiloto = {
  teclas: { ...TECLAS_VOO_ZERADAS },
  z: false,
  c: false,
  yaw_alvo: null,
  segui_alvo: false,
}

/** Taxa de guinada das teclas (rad/s): Z = +0,5 (esquerda), C = −0,5 (direita), as duas = 0. */
export function taxaGuinada(piloto: EstadoPiloto): number {
  return (piloto.z ? YAW_TAXA_TECLA : 0) - (piloto.c ? YAW_TAXA_TECLA : 0)
}

/** Uma tecla de movimento ou de rodar PREMIDA. Z/C soltam o rumo fixado (volta-se ao modo taxa). */
export function premirTecla(
  piloto: EstadoPiloto,
  tecla: TeclaVoo | TeclaRodar
): EstadoPiloto {
  if (tecla === "z" || tecla === "c") {
    if (piloto[tecla] && piloto.yaw_alvo === null) return piloto
    return { ...piloto, [tecla]: true, yaw_alvo: null }
  }
  if (piloto.teclas[tecla]) return piloto
  return { ...piloto, teclas: { ...piloto.teclas, [tecla]: true } }
}

/** Uma tecla de movimento ou de rodar LARGADA. */
export function largarTecla(
  piloto: EstadoPiloto,
  tecla: TeclaVoo | TeclaRodar
): EstadoPiloto {
  if (tecla === "z" || tecla === "c") {
    return piloto[tecla] ? { ...piloto, [tecla]: false } : piloto
  }
  if (!piloto.teclas[tecla]) return piloto
  return { ...piloto, teclas: { ...piloto.teclas, [tecla]: false } }
}

/** X: fixa o rumo dado (o atual). Sem rumo conhecido não se inventa nenhum: o estado não muda. */
export function fixarRumo(piloto: EstadoPiloto, rumo: number | null): EstadoPiloto {
  if (rumo === null || !Number.isFinite(rumo)) return piloto
  return { ...piloto, yaw_alvo: rumo }
}

/** Solta o rumo fixado (o botão «soltar» da janela Voo). */
export function soltarRumo(piloto: EstadoPiloto): EstadoPiloto {
  return piloto.yaw_alvo === null ? piloto : { ...piloto, yaw_alvo: null }
}

/** B / interruptor SEGUIR A BOLA. */
export function definirSeguirBola(
  piloto: EstadoPiloto,
  seguir: boolean
): EstadoPiloto {
  return piloto.segui_alvo === seguir ? piloto : { ...piloto, segui_alvo: seguir }
}

/**
 * Perder o foco (ou esconder a página) solta TODAS as teclas — movimento e rodar. Os MODOS (rumo
 * fixado, seguir a bola) ficam: não são teclas premidas, são escolhas.
 */
export function soltarTeclas(piloto: EstadoPiloto): EstadoPiloto {
  if (!temTeclasPremidas(piloto)) return piloto
  return { ...piloto, teclas: { ...TECLAS_VOO_ZERADAS }, z: false, c: false }
}

export function temTeclasPremidas(piloto: EstadoPiloto): boolean {
  return piloto.z || piloto.c || TECLAS_VOO.some((t) => piloto.teclas[t])
}

/** O corpo que estes dois estados mandariam é o mesmo? (só se envia quando MUDA) */
export function pilotoIgual(a: EstadoPiloto, b: EstadoPiloto): boolean {
  return (
    teclasIguais(a.teclas, b.teclas) &&
    a.z === b.z &&
    a.c === b.c &&
    a.yaw_alvo === b.yaw_alvo &&
    a.segui_alvo === b.segui_alvo
  )
}

/**
 * O corpo COMPLETO do `POST /api/voo`: o estado inteiro em cada envio (não diferenças), com
 * `ativo: true` SEMPRE — no cockpit o controlo de voo já vem ligado e não há botão de armar.
 */
export function corpoVooDoPiloto(piloto: EstadoPiloto): CorpoVoo {
  return {
    ativo: true,
    teclas: { ...piloto.teclas },
    yaw_taxa: taxaGuinada(piloto),
    yaw_alvo: piloto.yaw_alvo,
    segui_alvo: piloto.segui_alvo,
  }
}

/** Velocidade que as teclas pedem, vista do NARIZ: `[frente, esquerda, cima]` em m/s. */
export function velocidadeNoNariz(piloto: EstadoPiloto): [number, number, number] {
  return vRefDeTeclas(piloto.teclas)
}

/** A mesma velocidade no MUNDO, para um drone com este rumo (W segue o nariz: a 90° é +y). */
export function velocidadeNoMundo(
  piloto: EstadoPiloto,
  rumo: number
): [number, number, number] {
  return vRefRumoParaMundo(vRefDeTeclas(piloto.teclas), rumo)
}

// --------------------------------------------------------------------------------- envio «o último vence»

export interface EmissorOpcoes<T, R> {
  enviar: (valor: T) => Promise<R>
  /** Intervalo mínimo entre envios (ms). 0 = sem limite (só nunca há dois POSTs em voo). */
  intervaloMs?: number
  /** Junta um pedido novo ao que ainda não saiu (corpos parciais). Por omissão o novo substitui. */
  fundir?: (pendente: T, novo: T) => T
  /**
   * Dois valores dizem o mesmo? Com isto, um `largar` do valor que o servidor ACABOU de confirmar não
   * se reenvia (largar o slider onde o último envio do arrasto o deixou).
   */
  igual?: (a: T, b: T) => boolean
  aoConfirmar?: (resposta: R, valor: T) => void
  aoFalhar?: (erro: unknown, valor: T) => void
  /** Relógio e agendador injetáveis (testes). */
  relogio?: () => number
  agendar?: (tarefa: () => void, ms: number) => unknown
  cancelar?: (handle: unknown) => void
}

/**
 * Envio «O ÚLTIMO VENCE» com intervalo mínimo — o que os controlos contínuos do cockpit usam (teclas,
 * sliders, bússola):
 *  · nunca há dois POSTs em voo: o seguinte só sai depois de o anterior assentar, logo a ordem das
 *    escritas no servidor é a ordem dos gestos;
 *  · enquanto um não sai, só fica o estado MAIS RECENTE (os intermédios não fazem fila);
 *  · `pedir` respeita `intervaloMs` (arrastar um slider manda no máximo ~10 Hz);
 *  · `largar` é o ENVIO FINAL: sai logo que possível, sem esperar o intervalo — o valor onde o gesto
 *    acabou chega sempre ao servidor.
 */
export class Emissor<T, R = unknown> {
  private readonly opcoes: EmissorOpcoes<T, R>
  private readonly intervaloMs: number
  private readonly relogio: () => number
  private readonly agendar: (tarefa: () => void, ms: number) => unknown
  private readonly cancelarAgendado: (handle: unknown) => void

  private pendente: { valor: T } | null = null
  private emEnvio = false
  private urgente = false
  private ultimoEnvio = Number.NEGATIVE_INFINITY
  private temporizador: unknown = null
  /** O último valor que o servidor aceitou (uma falha apaga-o: o seguinte tem de sair). */
  private confirmado: { valor: T } | null = null

  constructor(opcoes: EmissorOpcoes<T, R>) {
    this.opcoes = opcoes
    this.intervaloMs = opcoes.intervaloMs ?? 0
    this.relogio = opcoes.relogio ?? (() => Date.now())
    this.agendar =
      opcoes.agendar ?? ((tarefa, ms) => setTimeout(tarefa, ms) as unknown)
    this.cancelarAgendado =
      opcoes.cancelar ??
      ((handle) => clearTimeout(handle as ReturnType<typeof setTimeout>))
  }

  /** Há um envio em voo ou por sair? (enquanto houver, o ecrã não adota o valor do servidor) */
  get ocupado(): boolean {
    return this.emEnvio || this.pendente !== null
  }

  pedir(valor: T): void {
    this.guardar(valor)
    this.bombear()
  }

  largar(valor?: T): void {
    if (
      valor !== undefined &&
      !this.ocupado &&
      this.confirmado !== null &&
      this.opcoes.igual?.(this.confirmado.valor, valor) === true
    )
      return
    if (valor !== undefined) this.guardar(valor)
    if (this.pendente === null) return
    this.urgente = true
    this.bombear()
  }

  /** Esquece o que ainda não saiu (fim do componente). */
  cancelar(): void {
    this.pendente = null
    this.urgente = false
    if (this.temporizador !== null) {
      this.cancelarAgendado(this.temporizador)
      this.temporizador = null
    }
  }

  private guardar(valor: T): void {
    this.pendente = {
      valor:
        this.pendente !== null && this.opcoes.fundir
          ? this.opcoes.fundir(this.pendente.valor, valor)
          : valor,
    }
  }

  private bombear(): void {
    if (this.emEnvio || this.pendente === null) return
    const espera = this.urgente
      ? 0
      : this.ultimoEnvio + this.intervaloMs - this.relogio()
    if (espera > 0) {
      if (this.temporizador === null) {
        this.temporizador = this.agendar(() => {
          this.temporizador = null
          this.bombear()
        }, espera)
      }
      return
    }
    if (this.temporizador !== null) {
      this.cancelarAgendado(this.temporizador)
      this.temporizador = null
    }
    const { valor } = this.pendente
    this.pendente = null
    this.urgente = false
    this.emEnvio = true
    this.ultimoEnvio = this.relogio()
    // `emEnvio` baixa ANTES de avisar: quem ouve a resposta pergunta `ocupado` para saber se ainda há
    // mais alguma coisa a caminho (e só então adota o que o servidor confirmou).
    this.opcoes
      .enviar(valor)
      .then(
        (resposta) => {
          this.emEnvio = false
          this.confirmado = { valor }
          this.opcoes.aoConfirmar?.(resposta, valor)
        },
        (erro: unknown) => {
          this.emEnvio = false
          this.confirmado = null
          this.opcoes.aoFalhar?.(erro, valor)
        }
      )
      .finally(() => this.bombear())
  }
}

// --------------------------------------------------------------------------------- janelas

export const IDS_JANELA = [
  "voo",
  "bola",
  "vento",
  "instrumentos",
  "energia",
  "graficos",
  "sistema",
  "ajuda",
] as const
export type IdJanela = (typeof IDS_JANELA)[number]

export interface MetaJanela {
  id: IdJanela
  titulo: string
  /** Atalho (`1`…`8`). */
  tecla: string
  /** Largura (px); a janela nunca passa do viewport. */
  largura: number
  /** Altura aproximada (px) — só para escolher a posição inicial. */
  alturaPrevista: number
  /** As três principais cabem sem scroll interno a 1366×768; as outras podem ter scroll interno. */
  principal: boolean
}

/** As janelas da doca, pela ordem dos atalhos 1–8. */
export const JANELAS: readonly MetaJanela[] = [
  { id: "voo", titulo: "Voo", tecla: "1", largura: 300, alturaPrevista: 352, principal: true },
  { id: "bola", titulo: "Bola", tecla: "2", largura: 300, alturaPrevista: 440, principal: true },
  { id: "vento", titulo: "Vento", tecla: "3", largura: 300, alturaPrevista: 400, principal: true },
  { id: "instrumentos", titulo: "Sensores", tecla: "4", largura: 820, alturaPrevista: 640, principal: false },
  { id: "energia", titulo: "Energia", tecla: "5", largura: 340, alturaPrevista: 330, principal: false },
  { id: "graficos", titulo: "Gráficos", tecla: "6", largura: 720, alturaPrevista: 520, principal: false },
  { id: "sistema", titulo: "Sistema", tecla: "7", largura: 760, alturaPrevista: 560, principal: false },
  { id: "ajuda", titulo: "Ajuda", tecla: "8", largura: 700, alturaPrevista: 500, principal: false },
]

export function metaJanela(id: IdJanela): MetaJanela {
  return JANELAS.find((j) => j.id === id) ?? JANELAS[0]
}

export interface Ponto {
  x: number
  y: number
}

export interface Tamanho {
  largura: number
  altura: number
}

/**
 * O que se guarda das janelas: quais estão abertas — pela ordem de empilhamento, a ÚLTIMA é a da
 * frente (a que o `Esc` fecha) — e onde o dono deixou cada uma (as fechadas lembram-se do sítio).
 */
export interface EstadoJanelas {
  abertas: IdJanela[]
  posicoes: Partial<Record<IdJanela, Ponto>>
}

export const JANELAS_FECHADAS: EstadoJanelas = { abertas: [], posicoes: {} }

export function janelaAberta(estado: EstadoJanelas, id: IdJanela): boolean {
  return estado.abertas.includes(id)
}

/** A janela da frente (a que recebe o `Esc`), ou `null` com tudo fechado. */
export function janelaEmFoco(estado: EstadoJanelas): IdJanela | null {
  return estado.abertas.length > 0
    ? estado.abertas[estado.abertas.length - 1]
    : null
}

/** Traz a janela para a frente (abre-a se estiver fechada). */
export function focarJanela(estado: EstadoJanelas, id: IdJanela): EstadoJanelas {
  if (janelaEmFoco(estado) === id) return estado
  return {
    ...estado,
    abertas: [...estado.abertas.filter((j) => j !== id), id],
  }
}

export function fecharJanela(estado: EstadoJanelas, id: IdJanela): EstadoJanelas {
  if (!janelaAberta(estado, id)) return estado
  return { ...estado, abertas: estado.abertas.filter((j) => j !== id) }
}

/** O botão da doca e as teclas 1–8: fechada abre à frente; aberta fecha. */
export function alternarJanela(
  estado: EstadoJanelas,
  id: IdJanela
): EstadoJanelas {
  return janelaAberta(estado, id)
    ? fecharJanela(estado, id)
    : focarJanela(estado, id)
}

/** `Esc`: fecha a janela da frente. */
export function fecharEmFoco(estado: EstadoJanelas): EstadoJanelas {
  const id = janelaEmFoco(estado)
  return id === null ? estado : fecharJanela(estado, id)
}

export function moverJanela(
  estado: EstadoJanelas,
  id: IdJanela,
  ponto: Ponto
): EstadoJanelas {
  const atual = estado.posicoes[id]
  if (atual !== undefined && atual.x === ponto.x && atual.y === ponto.y)
    return estado
  return { ...estado, posicoes: { ...estado.posicoes, [id]: ponto } }
}

/** Margem mínima entre uma janela e a borda do viewport (px). */
export const MARGEM_JANELA = 8

/**
 * Altura máxima de uma janela (px): do fim da barra de estado até ao cimo da doca. Uma janela mais
 * comprida ganha scroll INTERNO em vez de tapar a doca (por onde se fecham e abrem as outras).
 */
export function alturaMaximaJanela(viewport: Tamanho): number {
  return Math.max(240, viewport.altura - 140)
}

/**
 * Mantém a janela DENTRO do viewport (arrastar, redimensionar o browser, posição guardada num ecrã
 * maior). Uma janela maior do que o viewport encosta ao canto superior esquerdo: a barra de título —
 * por onde se arrasta e fecha — nunca fica de fora.
 */
export function encaixar(
  ponto: Ponto,
  tamanho: Tamanho,
  viewport: Tamanho,
  margem = MARGEM_JANELA
): Ponto {
  const maxX = Math.max(margem, viewport.largura - tamanho.largura - margem)
  const maxY = Math.max(margem, viewport.altura - tamanho.altura - margem)
  return {
    x: Math.round(limitar(ponto.x, margem, maxX)),
    y: Math.round(limitar(ponto.y, margem, maxY)),
  }
}

/** Por baixo da barra de estado do HUD (px). */
const TOPO_JANELAS = 64
const FOLGA_JANELAS = 12
/** Faixa de baixo ocupada pela miniatura, a doca e as teclas (px) — as janelas abrem por cima dela. */
const RESERVA_BAIXO = 216

/**
 * Onde uma janela abre pela 1.ª vez: as de VOO encostam à esquerda, a BOLA à direita, e o centro — a
 * mira e o horizonte — fica livre. O Vento vai para baixo do Voo quando o ecrã tem altura para os
 * dois; num ecrã baixo (768) abre ao lado da Bola. As janelas de detalhe abrem ao centro, em cascata
 * horizontal; a Energia (compacta) fica ao lado da coluna da Bola.
 */
export function posicaoInicial(id: IdJanela, viewport: Tamanho): Ponto {
  const meta = metaJanela(id)
  const largura = Math.min(meta.largura, viewport.largura - 2 * MARGEM_JANELA)
  const direita = viewport.largura - FOLGA_JANELAS - largura
  let ponto: Ponto
  switch (id) {
    case "voo":
      ponto = { x: FOLGA_JANELAS, y: TOPO_JANELAS }
      break
    case "bola":
      ponto = { x: direita, y: TOPO_JANELAS }
      break
    case "vento": {
      const voo = metaJanela("voo")
      const cabeEmbaixo =
        viewport.altura >=
        TOPO_JANELAS +
          voo.alturaPrevista +
          FOLGA_JANELAS +
          meta.alturaPrevista +
          RESERVA_BAIXO
      ponto = cabeEmbaixo
        ? {
            x: FOLGA_JANELAS,
            y: TOPO_JANELAS + voo.alturaPrevista + FOLGA_JANELAS,
          }
        : {
            x: direita - metaJanela("bola").largura - FOLGA_JANELAS,
            y: TOPO_JANELAS,
          }
      break
    }
    case "energia":
      // Ao lado da coluna da Bola (não por cima dela), ainda fora do centro.
      ponto = {
        x: direita - metaJanela("bola").largura - FOLGA_JANELAS,
        y: TOPO_JANELAS,
      }
      break
    default: {
      // Detalhe: ao centro, em cascata só na horizontal — todas começam logo abaixo da barra de
      // estado, para a altura máxima (`alturaMaximaJanela`) acabar por cima da doca.
      const ordem = JANELAS.findIndex((j) => j.id === id)
      ponto = {
        x: (viewport.largura - largura) / 2 + (ordem - 5) * 28,
        y: TOPO_JANELAS,
      }
    }
  }
  return encaixar(
    ponto,
    {
      largura,
      altura: Math.min(meta.alturaPrevista, alturaMaximaJanela(viewport)),
    },
    viewport
  )
}

/** Chave do `localStorage` (versão no nome: um formato novo não tropeça no antigo). */
export const CHAVE_JANELAS = "09_drone_hover_rl:cockpit:janelas:v1"

export function serializarJanelas(estado: EstadoJanelas): string {
  return JSON.stringify({ abertas: estado.abertas, posicoes: estado.posicoes })
}

/**
 * O texto guardado → `EstadoJanelas`. Tolerante: JSON partido, ids que já não existem, repetidos e
 * posições sem números caem fora em vez de rebentar o arranque (o pior caso é abrir tudo fechado).
 */
export function lerJanelas(texto: string | null | undefined): EstadoJanelas {
  if (typeof texto !== "string" || texto.length === 0) return JANELAS_FECHADAS
  let bruto: unknown
  try {
    bruto = JSON.parse(texto)
  } catch {
    return JANELAS_FECHADAS
  }
  const o = objetoSimples(bruto)
  if (o === null) return JANELAS_FECHADAS
  const conhecida = (id: unknown): id is IdJanela =>
    (IDS_JANELA as readonly unknown[]).includes(id)
  const abertas: IdJanela[] = []
  for (const id of Array.isArray(o.abertas) ? o.abertas : []) {
    if (conhecida(id) && !abertas.includes(id)) abertas.push(id)
  }
  const posicoes: Partial<Record<IdJanela, Ponto>> = {}
  const guardadas = objetoSimples(o.posicoes) ?? {}
  for (const id of IDS_JANELA) {
    const p = objetoSimples(guardadas[id])
    const x = finito(p?.x)
    const y = finito(p?.y)
    if (x !== null && y !== null) posicoes[id] = { x, y }
  }
  return { abertas, posicoes }
}

/**
 * É preciso sondar o `GET /api/sim` (200 linhas de telemetria, centenas de kB por resposta)? Só
 * enquanto estiver aberta uma janela que vive do histórico: Sensores, Gráficos, Energia com o
 * detalhe aberto, ou Sistema com a política RL a voar (os painéis da rede). Com o resto — e com tudo
 * fechado — o cockpit vive do SSE do HUD e de um `/api/state` por segundo.
 */
export function precisaDeSim(
  abertas: readonly IdJanela[],
  contexto: { energiaDetalhe: boolean; rl: boolean }
): boolean {
  return abertas.some(
    (id) =>
      id === "instrumentos" ||
      id === "graficos" ||
      (id === "energia" && contexto.energiaDetalhe) ||
      (id === "sistema" && contexto.rl)
  )
}

// --------------------------------------------------------------------------------- câmara (3.ª pessoa)

/** Graus por altura de vista arrastada — o mesmo ganho do rato na janela do MuJoCo. */
export const GRAUS_POR_VISTA = 180
/** Faixa da elevação ao orbitar (graus MuJoCo: negativa = câmara por cima). */
export const ELEVACAO_ORBITA = [-89, 30] as const

/**
 * Arrastar a vista = ORBITAR, com a convenção do rato do MuJoCo (`mjv_moveCamera`): a cena segue o
 * dedo. Arrastar para a DIREITA diminui o azimute; arrastar para BAIXO diminui a elevação (a câmara
 * sobe e olha mais de cima). `dx`/`dy` são o deslocamento desde o INÍCIO do gesto, em px.
 */
export function orbitarPorArrasto(
  inicio: { azimute: number; elevacao: number },
  dx: number,
  dy: number,
  alturaVista: number
): { azimute: number; elevacao: number } {
  const ganho = GRAUS_POR_VISTA / Math.max(1, alturaVista)
  return {
    azimute: reduzirGraus(inicio.azimute - dx * ganho),
    elevacao: limitar(
      inicio.elevacao - dy * ganho,
      ELEVACAO_ORBITA[0],
      ELEVACAO_ORBITA[1]
    ),
  }
}

/** Roda do rato = distância: rodar para a frente (`deltaY` < 0) aproxima; exponencial, sem saltos. */
export function distanciaPorRoda(
  distancia: number,
  deltaY: number,
  limites: Par
): number {
  const fator = Math.exp(limitar(deltaY, -400, 400) * 0.0015)
  return limitar(distancia * fator, limites[0], limites[1])
}

// --------------------------------------------------------------------------------- texto dos instrumentos

/** Número para o HUD: vírgula decimal, casas fixas (não dança de largura) e «—» sem valor. */
export function fmtHud(valor: number | null | undefined, casas = 1): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—"
  const texto = valor.toFixed(casas).replace(".", ",")
  // «−0,0» é ruído num instrumento: zero não tem sinal.
  return /^-0(,0+)?$/.test(texto) ? texto.slice(1) : texto.replace("-", "−")
}

/** Rumo com três algarismos (`007`, `352`), como numa fita de rumo. */
export function fmtRumo(graus: number | null | undefined): string {
  if (graus === null || graus === undefined || !Number.isFinite(graus)) return "—"
  return String(Math.round(reduzirGraus(graus)) % 360).padStart(3, "0")
}

/** Autonomia em minutos (`62 min`, `1 h 05`); «—» sem estimativa. */
export function fmtAutonomia(minutos: number | null | undefined): string {
  if (minutos === null || minutos === undefined || !Number.isFinite(minutos))
    return "—"
  const m = Math.max(0, Math.round(minutos))
  return m < 100 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`
}

// --------------------------------------------------------------------------------- controlos (estado otimista)

/**
 * Depois de uma alteração LOCAL ignora-se o que o `/api/state` disser durante este tempo: a sondagem
 * de 1 Hz pode trazer um retrato tirado ANTES de o POST assentar, e o interruptor voltava atrás por
 * um instante.
 */
export const CARENCIA_ADOCAO_MS = 1500

/** Base dos controlos do cockpit: um valor, quem o observa (`useSyncExternalStore`) e o relógio. */
class Observavel<E> {
  protected valor: E
  private readonly ouvintes = new Set<() => void>()

  constructor(inicial: E) {
    this.valor = inicial
  }

  readonly subscrever = (ouvinte: () => void): (() => void) => {
    this.ouvintes.add(ouvinte)
    return () => {
      this.ouvintes.delete(ouvinte)
    }
  }

  readonly obter = (): E => this.valor

  protected publicar(novo: E): void {
    if (novo === this.valor) return
    this.valor = novo
    for (const ouvinte of this.ouvintes) ouvinte()
  }
}

export interface ControloOpcoes {
  aoFalhar?: (erro: unknown) => void
  relogio?: () => number
  agendar?: (tarefa: () => void, ms: number) => unknown
  cancelar?: (handle: unknown) => void
}

/** O que o servidor diz do pedido de voo (`voo.pedido` do `/api/state`), no que o cockpit adota. */
export interface PedidoVooServidor {
  ativo: boolean
  yaw_alvo: number | null
  segui_alvo: boolean
}

/**
 * O PILOTO — o estado local das teclas e dos modos, e o seu envio. Os keycaps seguem ESTE estado no
 * instante (o teclado nunca espera pela rede); cada mudança real manda o corpo COMPLETO do
 * `POST /api/voo` em «o último vence»; o que não muda não se envia.
 */
export class ControloPiloto extends Observavel<EstadoPiloto> {
  private readonly emissor: Emissor<CorpoVoo, unknown>
  private readonly relogio: () => number
  private ultimaMudanca = Number.NEGATIVE_INFINITY

  constructor(
    opcoes: ControloOpcoes & { enviar: (corpo: CorpoVoo) => Promise<unknown> }
  ) {
    super(PILOTO_INICIAL)
    this.relogio = opcoes.relogio ?? (() => Date.now())
    this.emissor = new Emissor<CorpoVoo, unknown>({
      enviar: opcoes.enviar,
      aoFalhar: opcoes.aoFalhar,
      relogio: opcoes.relogio,
      agendar: opcoes.agendar,
      cancelar: opcoes.cancelar,
    })
  }

  premir(tecla: TeclaVoo | TeclaRodar): void {
    this.aplicar(premirTecla(this.valor, tecla))
  }

  largar(tecla: TeclaVoo | TeclaRodar): void {
    this.aplicar(largarTecla(this.valor, tecla))
  }

  /** X — `false` quando não há rumo para fixar (o cockpit avisa em vez de inventar um). */
  fixarRumo(rumo: number | null): boolean {
    const novo = fixarRumo(this.valor, rumo)
    this.aplicar(novo)
    return novo.yaw_alvo !== null && novo.yaw_alvo === rumo
  }

  soltarRumo(): void {
    this.aplicar(soltarRumo(this.valor))
  }

  seguirBola(seguir: boolean): void {
    this.aplicar(definirSeguirBola(this.valor, seguir))
  }

  /** B — devolve o novo estado do modo. */
  alternarBola(): boolean {
    const seguir = !this.valor.segui_alvo
    this.seguirBola(seguir)
    return seguir
  }

  /** `blur` / página escondida: nenhuma tecla fica presa. */
  soltarTudo(): void {
    this.aplicar(soltarTeclas(this.valor))
  }

  /**
   * O `voo.pedido` do servidor: adotam-se os MODOS (`segui_alvo`, `yaw_alvo`) — é assim que recarregar
   * a página a meio de «seguir a bola» não desliga o modo na primeira tecla — e garante-se
   * `ativo: true` (se alguém desarmou por fora, o cockpit volta a armar). As teclas nunca se adotam:
   * são o teclado DESTE browser.
   */
  adotarServidor(pedido: PedidoVooServidor | null): void {
    if (pedido === null) return
    if (
      this.emissor.ocupado ||
      this.relogio() - this.ultimaMudanca < CARENCIA_ADOCAO_MS
    )
      return
    const adotado: EstadoPiloto = {
      ...this.valor,
      yaw_alvo: pedido.yaw_alvo,
      segui_alvo: pedido.segui_alvo,
    }
    if (!pilotoIgual(adotado, this.valor)) this.publicar(adotado)
    if (!pedido.ativo) this.emissor.largar(corpoVooDoPiloto(this.valor))
  }

  private aplicar(novo: EstadoPiloto): void {
    if (pilotoIgual(novo, this.valor)) return
    this.ultimaMudanca = this.relogio()
    this.publicar(novo)
    this.emissor.largar(corpoVooDoPiloto(novo))
  }
}

/** Estado do painel do vento: o bloco e se ele já veio do servidor (antes disso é o padrão). */
export interface EstadoVento extends VentoSimples {
  conhecido: boolean
}

/**
 * O VENTO de três botões. Cada gesto atualiza o painel no instante e manda SÓ o que mudou
 * (`POST /api/vento-simples` aceita subconjuntos): arrastar (`final: false`) sai no máximo a ~10 Hz;
 * largar/interruptores (`final: true`) saem logo.
 */
export class ControloVento extends Observavel<EstadoVento> {
  private readonly emissor: Emissor<Partial<VentoSimples>, VentoSimples | null>
  private readonly relogio: () => number
  private readonly aoFalhar?: (erro: unknown) => void
  private ultimaMudanca = Number.NEGATIVE_INFINITY
  /** O último bloco que o servidor disse (para onde se volta se um envio falhar). */
  private servidor: VentoSimples | null = null

  constructor(
    opcoes: ControloOpcoes & {
      enviar: (corpo: Partial<VentoSimples>) => Promise<VentoSimples | null>
      intervaloMs?: number
    }
  ) {
    super({ ...VENTO_SIMPLES_PADRAO, conhecido: false })
    this.relogio = opcoes.relogio ?? (() => Date.now())
    this.aoFalhar = opcoes.aoFalhar
    this.emissor = new Emissor<Partial<VentoSimples>, VentoSimples | null>({
      enviar: opcoes.enviar,
      intervaloMs: opcoes.intervaloMs ?? 100,
      fundir: (pendente, novo) => ({ ...pendente, ...novo }),
      igual: (a, b) => JSON.stringify(a) === JSON.stringify(b),
      aoConfirmar: (bloco) => {
        if (bloco === null) return
        this.servidor = bloco
        // Só se adota a confirmação quando não há mais nada a caminho (senão o slider dava um salto
        // atrás a meio do arrasto).
        if (!this.emissor.ocupado) this.publicar({ ...bloco, conhecido: true })
      },
      aoFalhar: (erro) => {
        if (this.servidor !== null && !this.emissor.ocupado)
          this.publicar({ ...this.servidor, conhecido: true })
        this.aoFalhar?.(erro)
      },
      relogio: opcoes.relogio,
      agendar: opcoes.agendar,
      cancelar: opcoes.cancelar,
    })
  }

  /** Uma alteração do painel. `final` = fim do gesto (largar o slider, um interruptor, a tecla V). */
  ajustar(alteracao: Partial<Record<keyof VentoSimples, unknown>>, final: boolean): void {
    const corpo = corpoVentoSimples(alteracao)
    if (corpo === null) return
    this.ultimaMudanca = this.relogio()
    this.publicar({ ...this.valor, ...corpo })
    if (final) this.emissor.largar(corpo)
    else this.emissor.pedir(corpo)
  }

  /** V — devolve o novo estado do interruptor. */
  alternar(): boolean {
    const ligado = !this.valor.ligado
    this.ajustar({ ligado }, true)
    return ligado
  }

  /** O bloco do `/api/state` (1 Hz): manda quando não há gesto local recente nem envio a caminho. */
  adotarServidor(bloco: VentoSimples | null): void {
    if (bloco === null) return
    this.servidor = bloco
    if (
      this.emissor.ocupado ||
      this.relogio() - this.ultimaMudanca < CARENCIA_ADOCAO_MS
    )
      return
    const v = this.valor
    if (
      v.conhecido &&
      v.ligado === bloco.ligado &&
      v.intensidade === bloco.intensidade &&
      v.aleatorio === bloco.aleatorio &&
      v.direcao === bloco.direcao
    )
      return
    this.publicar({ ...bloco, conhecido: true })
  }
}

/** Estado do slider da bola: a velocidade e a faixa (`null` enquanto o `/api/state` não a disser). */
export type EstadoBola = BolaConfig | null

/** A velocidade da BOLA aleatória (`POST /api/bola`), com a mesma política do vento. */
export class ControloBola extends Observavel<EstadoBola> {
  private readonly emissor: Emissor<number, number | null>
  private readonly relogio: () => number
  private readonly aoFalhar?: (erro: unknown) => void
  private ultimaMudanca = Number.NEGATIVE_INFINITY
  private servidor: BolaConfig | null = null

  constructor(
    opcoes: ControloOpcoes & {
      enviar: (velocidade: number) => Promise<number | null>
      intervaloMs?: number
    }
  ) {
    super(null)
    this.relogio = opcoes.relogio ?? (() => Date.now())
    this.aoFalhar = opcoes.aoFalhar
    this.emissor = new Emissor<number, number | null>({
      enviar: opcoes.enviar,
      intervaloMs: opcoes.intervaloMs ?? 100,
      igual: (a, b) => a === b,
      aoFalhar: (erro) => {
        if (this.servidor !== null && !this.emissor.ocupado)
          this.publicar(this.servidor)
        this.aoFalhar?.(erro)
      },
      relogio: opcoes.relogio,
      agendar: opcoes.agendar,
      cancelar: opcoes.cancelar,
    })
  }

  /** Sem faixa conhecida não há slider: nada se envia às cegas. */
  ajustar(velocidade: number, final: boolean): void {
    const cfg = this.valor
    if (cfg === null) return
    const v = limitarVelocidadeBola(velocidade, cfg)
    this.ultimaMudanca = this.relogio()
    if (v !== cfg.velocidade) this.publicar({ ...cfg, velocidade: v })
    if (final) this.emissor.largar(v)
    else this.emissor.pedir(v)
  }

  adotarServidor(cfg: BolaConfig | null): void {
    if (cfg === null) return
    this.servidor = cfg
    if (
      this.emissor.ocupado ||
      this.relogio() - this.ultimaMudanca < CARENCIA_ADOCAO_MS
    )
      return
    const v = this.valor
    if (
      v !== null &&
      v.velocidade === cfg.velocidade &&
      v.min === cfg.min &&
      v.max === cfg.max
    )
      return
    this.publicar(cfg)
  }
}

// --------------------------------------------------------------------------------- ajuda (as teclas)

/** As teclas do cockpit, como a janela Ajuda as lista (`INTERFACE.md` §0.3). */
export const ATALHOS: readonly { teclas: string[]; faz: string }[] = [
  { teclas: ["W", "S"], faz: "frente · trás, na direção do nariz (1,0 m/s)" },
  { teclas: ["A", "D"], faz: "esquerda · direita do nariz (1,0 m/s)" },
  { teclas: ["Q", "E"], faz: "subir · descer (0,7 m/s)" },
  { teclas: ["Z", "C"], faz: "rodar para a esquerda · direita (manter)" },
  { teclas: ["X"], faz: "fixar o rumo atual" },
  { teclas: ["B"], faz: "seguir a bola: liga · desliga" },
  { teclas: ["V"], faz: "vento: liga · desliga" },
  { teclas: ["F"], faz: "trocar a vista: 1.ª ↔ 3.ª pessoa" },
  { teclas: ["R"], faz: "manter premido: reiniciar (volta ao chão e descola)" },
  { teclas: ["1", "…", "8"], faz: "abrir · fechar as janelas da doca" },
  { teclas: ["Esc"], faz: "fechar a janela da frente" },
]
