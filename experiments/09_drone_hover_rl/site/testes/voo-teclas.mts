/**
 * Teste do CONTROLO DE VOO (contrato r11): o mapeamento teclas → `v_ref` e os parsers tolerantes
 * dos blocos `voo`. Corre sem dependências: `node testes/voo-teclas.mts` (Node ≥ 22.6 com
 * type-stripping; o `src/lib/voo.ts` é importado tal e qual é usado pelo site).
 *
 * Semântica verificada (frame MUNDO, yaw alvo 0): W = +x, S = −x, A = +y, D = −y, Q = +z, E = −z;
 * diagonais horizontais normalizadas para 1,0 m/s; |vz| = 0,7 m/s; pares opostos/sem teclas =
 * `[0,0,0]` = o drone SEGURA posição.
 */

import {
  lerBlocoVoo,
  lerEcoVoo,
  TECLAS_VOO,
  TECLAS_VOO_ZERADAS,
  V_HORIZONTAL_M_S,
  V_VERTICAL_M_S,
  teclasAtivas,
  teclasIguais,
  vRefDeTeclas,
  type TeclaVoo,
  type TeclasVoo,
} from "../src/lib/voo.ts"

let falhas = 0
let verificacoes = 0

function ok(condicao: boolean, descricao: string) {
  verificacoes += 1
  if (!condicao) {
    falhas += 1
    console.error(`✗ ${descricao}`)
  }
}

function aprox(a: number, b: number, eps = 1e-12): boolean {
  return Math.abs(a - b) <= eps
}

function vetIgual(
  a: readonly number[],
  b: readonly number[],
  eps = 1e-12
): boolean {
  return a.length === b.length && a.every((v, i) => aprox(v, b[i] ?? NaN, eps))
}

function textoVetor(v: readonly number[]): string {
  return `[${v.join(", ")}]`
}

/** As 6 teclas com `ligadas` ativas (o resto solto). */
function teclas(...ligadas: TeclaVoo[]): TeclasVoo {
  const t: TeclasVoo = { ...TECLAS_VOO_ZERADAS }
  for (const tecla of ligadas) t[tecla] = true
  return t
}

// ---------------------------------------------------------------- 1. constantes do contrato
ok(
  TECLAS_VOO.length === 6 && TECLAS_VOO.join("") === "wasdqe",
  `TECLAS_VOO na ordem canónica ["w","a","s","d","q","e"] (veio ${JSON.stringify(TECLAS_VOO)})`
)
ok(
  (Object.keys(TECLAS_VOO_ZERADAS) as string[]).sort().join("") === "adeqsw" &&
    Object.values(TECLAS_VOO_ZERADAS).every((v) => v === false),
  "TECLAS_VOO_ZERADAS tem as 6 teclas, todas soltas"
)

// ---------------------------------------------------------------- 2. vRefDeTeclas — teclas isoladas
ok(
  vetIgual(vRefDeTeclas(teclas("w")), [1, 0, 0]),
  "W isolada → [1,0,0] (frente = +x)"
)
ok(
  vetIgual(vRefDeTeclas(teclas("s")), [-1, 0, 0]),
  "S isolada → [−1,0,0] (trás = −x)"
)
ok(
  vetIgual(vRefDeTeclas(teclas("a")), [0, 1, 0]),
  "A isolada → [0,1,0] (esquerda = +y)"
)
ok(
  vetIgual(vRefDeTeclas(teclas("d")), [0, -1, 0]),
  "D isolada → [0,−1,0] (direita = −y)"
)
ok(
  vetIgual(vRefDeTeclas(teclas("q")), [0, 0, V_VERTICAL_M_S]) &&
    aprox(V_VERTICAL_M_S, 0.7),
  "Q isolada → [0,0,+0,7] (subir = +z, 0,7 m/s)"
)
ok(
  vetIgual(vRefDeTeclas(teclas("e")), [0, 0, -V_VERTICAL_M_S]),
  "E isolada → [0,0,−0,7] (descer = −z)"
)
ok(
  vetIgual(vRefDeTeclas(TECLAS_VOO_ZERADAS), [0, 0, 0]),
  "sem teclas → [0,0,0] (SEGURA posição)"
)

// ---------------------------------------------------------------- 3. diagonais normalizadas
for (const par of [
  ["w", "a"],
  ["w", "d"],
  ["s", "a"],
  ["s", "d"],
] as [TeclaVoo, TeclaVoo][]) {
  const v = vRefDeTeclas(teclas(...par))
  const horizontal = Math.hypot(v[0], v[1])
  ok(
    aprox(horizontal, V_HORIZONTAL_M_S) && aprox(v[2], 0),
    `diagonal ${par.join("+").toUpperCase()} → ‖horizontal‖ = 1,0 m/s (veio ${horizontal})`
  )
  const sinal = 1 / Math.SQRT2
  const esperado: [number, number, number] = [
    par.includes("w") ? sinal : -sinal,
    par.includes("a") ? sinal : -sinal,
    0,
  ]
  ok(
    vetIgual(v, esperado),
    `diagonal ${par.join("+").toUpperCase()} → ${textoVetor(esperado)} (veio ${textoVetor(v)})`
  )
}
// três teclas horizontais: sobra UMA e não há normalização a fazer
ok(
  vetIgual(vRefDeTeclas(teclas("w", "a", "d")), [1, 0, 0]),
  "W+A+D → [1,0,0] (A+D anulam-se; uma tecla não normaliza)"
)

// ---------------------------------------------------------------- 4. pares opostos → segura posição
ok(
  vetIgual(vRefDeTeclas(teclas("w", "s")), [0, 0, 0]),
  "W+S → [0,0,0] (par oposto horizontal)"
)
ok(
  vetIgual(vRefDeTeclas(teclas("a", "d")), [0, 0, 0]),
  "A+D → [0,0,0] (par oposto horizontal)"
)
ok(
  vetIgual(vRefDeTeclas(teclas("q", "e")), [0, 0, 0]),
  "Q+E → [0,0,0] (par oposto vertical)"
)
ok(
  vetIgual(vRefDeTeclas(teclas("w", "a", "s", "d", "q", "e")), [0, 0, 0]),
  "as 6 teclas → [0,0,0] (tudo se anula)"
)

// ---------------------------------------------------------------- 5. vertical + horizontal juntos
ok(
  vetIgual(vRefDeTeclas(teclas("w", "q")), [1, 0, V_VERTICAL_M_S]),
  "W+Q → [1,0,+0,7] (uma tecla horizontal mantém 1,0 m/s)"
)
ok(
  vetIgual(vRefDeTeclas(teclas("a", "s", "e")), [
    -1 / Math.SQRT2,
    1 / Math.SQRT2,
    -V_VERTICAL_M_S,
  ]),
  "A+S+E → diagonal normalizada com |vz| = 0,7 m/s"
)
ok(
  vetIgual(vRefDeTeclas(teclas("q")), [0, 0, 0.7]) &&
    vetIgual(vRefDeTeclas(teclas("e")), [0, 0, -0.7]),
  "o vertical NUNCA ultrapassa 0,7 m/s (independente do horizontal)"
)

// ---------------------------------------------------------------- 6. lerBlocoVoo (pedido do controlo)
for (const invalido of [null, undefined, "voo", 42, true, [], {}]) {
  ok(
    lerBlocoVoo(invalido) === null,
    `lerBlocoVoo(${JSON.stringify(invalido) ?? "undefined"}) → null (entrada inválida)`
  )
}
ok(
  lerBlocoVoo({ ativo: "sim" }) === null,
  "lerBlocoVoo sem campo nenhum reconhecível → null"
)
ok(
  lerBlocoVoo({ teclas: {} }) === null,
  "lerBlocoVoo com teclas vazias (sem nenhuma das 6) → null"
)
const blocoSimples = lerBlocoVoo({ ativo: true })
ok(
  blocoSimples !== null &&
    blocoSimples.ativo === true &&
    blocoSimples.seq === null &&
    teclasIguais(blocoSimples.teclas, TECLAS_VOO_ZERADAS),
  "lerBlocoVoo({ativo:true}) → bloco com teclas soltas e seq null (defaults)"
)
const blocoParcial = lerBlocoVoo({ teclas: { w: true, x: true, a: 1, s: 0 } })
ok(
  blocoParcial !== null &&
    blocoParcial.ativo === false &&
    blocoParcial.teclas.w === true &&
    blocoParcial.teclas.a === true &&
    blocoParcial.teclas.s === false &&
    blocoParcial.teclas.d === false &&
    blocoParcial.teclas.q === false &&
    blocoParcial.teclas.e === false,
  "lerBlocoVoo tolera teclas parciais (0/1 aceites, chave desconhecida ignorada)"
)
const blocoCheio = lerBlocoVoo({
  ativo: 1,
  teclas: { w: 0, a: 0, s: 0, d: 0, q: 1, e: 0 },
  seq: 7,
})
ok(
  blocoCheio !== null &&
    blocoCheio.ativo === true &&
    blocoCheio.seq === 7 &&
    teclasAtivas(blocoCheio.teclas).join("") === "q",
  "lerBlocoVoo({ativo:1, teclas:{...}, seq:7}) → bloco completo coerente"
)
ok(
  lerBlocoVoo({ seq: "nove" }) === null && lerBlocoVoo({ seq: "5" })?.seq === 5,
  "lerBlocoVoo: seq não numérico não conta como campo; seq string numérica conta"
)

// ---------------------------------------------------------------- 7. lerEcoVoo (eco do runner)
for (const invalido of [null, undefined, "eco", 0.7, false, [], {}]) {
  ok(
    lerEcoVoo(invalido) === null,
    `lerEcoVoo(${JSON.stringify(invalido) ?? "undefined"}) → null (entrada inválida)`
  )
}
ok(
  lerEcoVoo({ v_ref: [1, 2] }) === null,
  "lerEcoVoo com v_ref mal formado e nada mais → null"
)
ok(
  lerEcoVoo({ erro_v: NaN }) === null,
  "lerEcoVoo com só valores não finitos → null"
)
const ecoCheio = lerEcoVoo({
  ativo: true,
  teclas: { w: true, a: false, s: false, d: false, q: true, e: false },
  v_ref: [0.7071067811865475, -0.7071067811865475, 0.7],
  p_ref: [0.02, -0.01, 1],
  erro_xy: 0.05,
  erro_z: -0.01,
  erro_v: 0.08,
  seguindo: true,
})
ok(
  ecoCheio !== null &&
    ecoCheio.ativo === true &&
    ecoCheio.teclas.w === true &&
    ecoCheio.teclas.q === true &&
    vetIgual(ecoCheio.v_ref, [0.7071067811865475, -0.7071067811865475, 0.7]) &&
    vetIgual(ecoCheio.p_ref, [0.02, -0.01, 1]) &&
    ecoCheio.erro_xy === 0.05 &&
    ecoCheio.erro_z === -0.01 &&
    ecoCheio.erro_v === 0.08 &&
    ecoCheio.seguindo === true,
  "lerEcoVoo lê todos os campos do contrato r11"
)
const ecoParcial = lerEcoVoo({ seguindo: true, erro_xy: 0.05 })
ok(
  ecoParcial !== null &&
    ecoParcial.seguindo === true &&
    ecoParcial.erro_xy === 0.05 &&
    ecoParcial.erro_z === 0 &&
    ecoParcial.erro_v === 0 &&
    ecoParcial.ativo === false &&
    vetIgual(ecoParcial.v_ref, [0, 0, 0]) &&
    vetIgual(ecoParcial.p_ref, [0, 0, 0]) &&
    teclasIguais(ecoParcial.teclas, TECLAS_VOO_ZERADAS),
  "lerEcoVoo com campos em falta → defaults razoáveis (zeros, teclas soltas, seguindo false)"
)
const ecoVRef = lerEcoVoo({ v_ref: [0, 0, -0.7] })
ok(
  ecoVRef !== null && vetIgual(ecoVRef.v_ref, [0, 0, -0.7]),
  "lerEcoVoo aceita um eco com só o v_ref (o resto nos defaults)"
)

// ---------------------------------------------------------------- 8. utilitários de comparação
ok(
  teclasIguais(teclas("w", "q"), teclas("q", "w")) &&
    !teclasIguais(teclas("w"), TECLAS_VOO_ZERADAS),
  "teclasIguais compara as 6 chaves"
)
ok(
  teclasAtivas(teclas("e", "a", "w")).join(",") === "w,a,e" &&
    teclasAtivas(TECLAS_VOO_ZERADAS).length === 0,
  "teclasAtivas devolve as pressionadas pela ordem canónica"
)

// ---------------------------------------------------------------- 9. coerência contrato ↔ envio
// O corpo do POST /api/voo leva SEMPRE as 6 teclas em booleanos (é o que `enviarVoo` constrói): um
// eco devolvido pelo servidor tem de passar pelo parser sem perder nada.
const enviado = { ativo: true, teclas: teclas("w", "d", "e") }
const ecoDoServidor = lerEcoVoo({
  ativo: enviado.ativo,
  teclas: enviado.teclas,
  v_ref: vRefDeTeclas(enviado.teclas),
  p_ref: [0, 0, 1],
  erro_xy: 0,
  erro_z: 0,
  erro_v: 0,
  seguindo: false,
})
ok(
  ecoDoServidor !== null &&
    ecoDoServidor.ativo === enviado.ativo &&
    teclasIguais(ecoDoServidor.teclas, enviado.teclas) &&
    vetIgual(ecoDoServidor.v_ref, vRefDeTeclas(enviado.teclas)),
  "ida e volta: teclas enviadas ↔ eco do servidor ↔ v_ref coerentes"
)

console.log(
  `voo-teclas: ${verificacoes - falhas}/${verificacoes} verificações · ` +
    `W=+x · A=+y · Q=+z (${V_VERTICAL_M_S} m/s) · diagonais a ${V_HORIZONTAL_M_S} m/s`
)
if (falhas > 0) process.exit(1)
