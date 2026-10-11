/**
 * CONTROLO DE VOO (contrato r11) — as teclas WASD/QE e o eco do runner, em funções PURAS.
 *
 * Nada aqui toca no DOM nem no `fetch`: é a camada testável em node (`testes/voo-teclas.mts`) que
 * traduz o estado das teclas em velocidade comandada e normaliza (sem adivinhar) os blocos `voo`
 * que vêm do backend `sim_site.py`/`sim_view.py`:
 *
 *  · `POST /api/voo` recebe `{"ativo": bool, "teclas": {w,a,s,d,q,e: bool}}` (as 6 teclas sempre
 *    presentes; o `seq` é carimbado pelo SERVIDOR, nunca se manda);
 *  · o `/api/sim` e o `/api/state` publicam `"voo": {"pedido": {bloco}|null, "eco": {eco}|null}`;
 *  · cada linha de telemetria ganhou `"voo"` (aditivo; `null` quando a política em uso NÃO tem
 *    modo comando) com o ECO do runner.
 *
 * Semântica de voo (frame MUNDO, yaw alvo 0): W = +x (frente), S = −x (trás), A = +y (esquerda),
 * D = −y (direita), Q = +z (subir), E = −z (descer). Diagonais horizontais normalizadas para
 * 1,0 m/s; velocidade vertical |vz| = 0,7 m/s; sem teclas `v_ref = [0,0,0]` = o drone SEGURA
 * posição. Leituras tolerantes: o que vier inválido nunca rebenta nem é inventado — `null` no
 * bloco inteiro ou defaults razoáveis nos campos em falta.
 */

/** Uma das 6 teclas de voo, pela letra minúscula (`evento.key` normalizado). */
export type TeclaVoo = "w" | "a" | "s" | "d" | "q" | "e"

/** Estado (pressionada ou não) das 6 teclas de voo — SEMPRE as 6 chaves, em booleanos. */
export type TeclasVoo = {
  w: boolean
  a: boolean
  s: boolean
  d: boolean
  q: boolean
  e: boolean
}

/**
 * Bloco `voo` do ficheiro de controlo (o que o site PEDIU): `seq` é do SERVIDOR (opcional aqui —
 * o corpo do `POST /api/voo` nunca o leva).
 */
export interface BlocoVoo {
  ativo: boolean
  teclas: TeclasVoo
  seq?: number | null
}

/**
 * Eco `voo` da telemetria (o que o runner está MESMO a aplicar) — contrato r11:
 * `{ativo, teclas, v_ref, p_ref, erro_xy, erro_z, erro_v, seguindo}`.
 */
export interface EcoVoo {
  ativo: boolean
  teclas: TeclasVoo
  /** Velocidade comandada (m/s, mundo). */
  v_ref: [number, number, number]
  /** Posição de referência que o modo comando segue (m, mundo). */
  p_ref: [number, number, number]
  /** Erro horizontal à referência (m). */
  erro_xy: number
  /** Erro vertical à referência (m). */
  erro_z: number
  /** Erro de velocidade ‖v − v_ref‖ (m/s). */
  erro_v: number
  /** O drone está a seguir a referência (posição E velocidade dentro do limite)? */
  seguindo: boolean
}

/** Ordem canónica das 6 teclas de voo (W/A/S/D/Q/E). */
export const TECLAS_VOO = ["w", "a", "s", "d", "q", "e"] as const

/** As 6 teclas todas soltas (o «estado zerado» de segurança: `v_ref = [0,0,0]`). */
export const TECLAS_VOO_ZERADAS: TeclasVoo = {
  w: false,
  a: false,
  s: false,
  d: false,
  q: false,
  e: false,
}

/** Velocidade horizontal de UMA tecla (m/s); diagonais normalizadas para este módulo. */
export const V_HORIZONTAL_M_S = 1

/** Velocidade vertical de Q/E (m/s, |vz|). */
export const V_VERTICAL_M_S = 0.7

/**
 * Teclas → velocidade comandada `v_ref` (m/s, frame MUNDO, yaw alvo 0) — contrato r11.
 *
 * W = +x (frente), S = −x (trás), A = +y (esquerda), D = −y (direita), Q = +z (subir),
 * E = −z (descer). O horizontal sai de `hipotenusa` dos eixos: uma tecla dá 1,0 m/s e uma DIAGONAL
 * (ex. W+A) é normalizada dividindo por ‖[vx,vy]‖ quando ‖·‖ > 1 — fica a 1,0 m/s, nunca √2. O
 * vertical é independente (|vz| = 0,7 m/s). Sem teclas — ou com pares opostos — `[0,0,0]` = o
 * drone SEGURA posição.
 */
export function vRefDeTeclas(teclas: TeclasVoo): [number, number, number] {
  const t = teclas ?? TECLAS_VOO_ZERADAS
  let vx = (t.w ? V_HORIZONTAL_M_S : 0) - (t.s ? V_HORIZONTAL_M_S : 0)
  let vy = (t.a ? V_HORIZONTAL_M_S : 0) - (t.d ? V_HORIZONTAL_M_S : 0)
  const vz = (t.q ? V_VERTICAL_M_S : 0) - (t.e ? V_VERTICAL_M_S : 0)
  const horizontal = Math.hypot(vx, vy)
  if (horizontal > 1) {
    vx /= horizontal
    vy /= horizontal
  }
  return [vx, vy, vz]
}

/** Duas leituras de teclas dizem o mesmo? (comparação das 6 chaves). */
export function teclasIguais(a: TeclasVoo, b: TeclasVoo): boolean {
  return TECLAS_VOO.every((tecla) => Boolean(a[tecla]) === Boolean(b[tecla]))
}

/** Teclas pressionadas, pela ordem canónica (`["w","a"]` com W e A ativas). */
export function teclasAtivas(teclas: TeclasVoo): TeclaVoo[] {
  return TECLAS_VOO.filter((tecla) => Boolean(teclas[tecla]))
}

// --------------------------------------------------------------------------------- leituras tolerantes

/** Objeto simples (não lista, não `null`) ou `null` — o resto da leitura nunca rebenta. */
function objetoSimples(bruto: unknown): Record<string, unknown> | null {
  return typeof bruto === "object" && bruto !== null && !Array.isArray(bruto)
    ? (bruto as Record<string, unknown>)
    : null
}

/** Número finito ou `null` (aceita a forma string, como o `numero` do contrato de simulação). */
function numeroFinito(bruto: unknown): number | null {
  const v = typeof bruto === "string" ? Number(bruto) : bruto
  return typeof v === "number" && Number.isFinite(v) ? v : null
}

/** Booleano «a sério», ou 0/1 como o servidor tolera; o resto é campo em falta (`null`). */
function booleanoTolerante(bruto: unknown): boolean | null {
  if (typeof bruto === "boolean") return bruto
  if (bruto === 0 || bruto === 1) return bruto === 1
  return null
}

/** As 6 teclas a partir de um objeto JSON (as chaves desconhecidas ignoram-se; o que falta = solta). */
function lerTeclas(bruto: unknown): TeclasVoo | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const teclas = { ...TECLAS_VOO_ZERADAS }
  let alguma = false
  for (const tecla of TECLAS_VOO) {
    const valor = booleanoTolerante(o[tecla])
    if (valor !== null) {
      teclas[tecla] = valor
      alguma = true
    }
  }
  return alguma ? teclas : null
}

/** `[x,y,z]` finito, ou `null` (nunca `[0,0,0]` a fingir de vetor que não veio). */
function lerVetor3(bruto: unknown): [number, number, number] | null {
  if (!Array.isArray(bruto) || bruto.length < 3) return null
  const x = numeroFinito(bruto[0])
  const y = numeroFinito(bruto[1])
  const z = numeroFinito(bruto[2])
  return x === null || y === null || z === null ? null : [x, y, z]
}

/**
 * Qualquer bloco `{ativo, teclas, seq}` do backend → `BlocoVoo`, ou `null`.
 *
 * `null` quando a entrada NÃO é um objeto ou quando não tem NADA reconhecível dentro (tudo
 * inválido → `null`); campos em falta dentro de um bloco reconhecível saem com defaults razoáveis
 * (`ativo: false`, teclas soltas, `seq: null`). Nunca lança.
 */
export function lerBlocoVoo(bruto: unknown): BlocoVoo | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const ativo = booleanoTolerante(o.ativo)
  const teclas = lerTeclas(o.teclas)
  const seq = numeroFinito(o.seq)
  if (ativo === null && teclas === null && seq === null) return null
  return {
    ativo: ativo ?? false,
    teclas: teclas ?? { ...TECLAS_VOO_ZERADAS },
    seq,
  }
}

/**
 * O eco `voo` de uma linha da telemetria → `EcoVoo`, ou `null`.
 *
 * `null` quando a entrada não é objeto ou não tem campo nenhum reconhecível (é assim que uma
 * política SEM modo comando chega ao site: `"voo": null` na linha → `null`, honesto); o que
 * faltar dentro de um eco reconhecível sai com defaults razoáveis (zeros, teclas soltas,
 * `seguindo: false`). Nunca lança.
 */
export function lerEcoVoo(bruto: unknown): EcoVoo | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const ativo = booleanoTolerante(o.ativo)
  const teclas = lerTeclas(o.teclas)
  const vRef = lerVetor3(o.v_ref)
  const pRef = lerVetor3(o.p_ref)
  const erroXy = numeroFinito(o.erro_xy)
  const erroZ = numeroFinito(o.erro_z)
  const erroV = numeroFinito(o.erro_v)
  const seguindo = booleanoTolerante(o.seguindo)
  const algum =
    ativo !== null ||
    teclas !== null ||
    vRef !== null ||
    pRef !== null ||
    erroXy !== null ||
    erroZ !== null ||
    erroV !== null ||
    seguindo !== null
  if (!algum) return null
  return {
    ativo: ativo ?? false,
    teclas: teclas ?? { ...TECLAS_VOO_ZERADAS },
    v_ref: vRef ?? [0, 0, 0],
    p_ref: pRef ?? [0, 0, 0],
    erro_xy: erroXy ?? 0,
    erro_z: erroZ ?? 0,
    erro_v: erroV ?? 0,
    seguindo: seguindo ?? false,
  }
}
