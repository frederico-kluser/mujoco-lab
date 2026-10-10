/**
 * Teste da conversão posição↔alvo do widget «Câmara» (round-trip ≤ 1e-9) + consistência com a
 * CÂMARA REAL do MuJoCo 3.15 + leitura do contrato v2. Corre sem dependências:
 * `node testes/camera-roundtrip.mts` (Node ≥ 22.6 com type-stripping; o `src/lib/sim.ts` é
 * importado tal e qual é usado pelo site).
 *
 * A tabela `GROUND_TRUTH` foi medida com o MuJoCo 3.15.0 nesta máquina
 * (`mjv_updateScene` sobre um modelo com um geom; `MjvScene.camera[0/1]`):
 *  · `forward` = `MjvScene.camera[0].forward` — a direção de visão unitária REAL;
 *  · `mid` = (`camera[0].pos` + `camera[1].pos`)/2 — o `mjv_updateScene` constrói um par
 *    pseudo-estreoscópico a ±0,034·(up×f) dos dois lados da pose; a média é a pose da câmara.
 * Os valores são `float` (mjvGLCamera), daí a tolerância de 1e-6 na comparação com o ground truth
 * (o round-trip em puro JS/TS, esse sim, tem de fechar a 1e-9).
 */

import {
  alvoCamera,
  assinaturaCamera,
  cameraIgual,
  cameraReflete,
  CAMERA_UI_LIMITES,
  direcaoVisao,
  lerCamera,
  normalizarAzimute,
  posicaoCamera,
  type CameraEstado,
} from "../src/lib/sim.ts"

let falhas = 0
let verificacoes = 0

function ok(condicao: boolean, descricao: string) {
  verificacoes += 1
  if (!condicao) {
    falhas += 1
    console.error(`✗ ${descricao}`)
  }
}

function erroMax(
  a: readonly number[],
  b: readonly number[]
): number {
  let m = 0
  for (let i = 0; i < 3; i += 1) m = Math.max(m, Math.abs((a[i] ?? 0) - (b[i] ?? 0)))
  return m
}

// ---------------------------------------------------------------- 1. round-trip pos ↔ alvo
// Grelha larga: ângulos inteiros e fracionários, elevações extremas, distâncias do contrato
// (]0,20]) e alvos fora da faixa da UI (a conversão é matemática; as faixas são da UI/servidor).
const azimutes = [0, 1, 15, 45.5, 90, 123.456, 180, 200, 270, 359, 359.999]
const elevacoes = [-90, -89.999, -56.789, -45, -10, 0, 10, 30, 85, 89.999, 90]
const distancias = [0.001, 0.1, 1, 2.5, 7.3, 10, 19.999, 20]
const alvos: [number, number, number][] = [
  [0, 0, 0],
  [0, 0, 1],
  [1, 2, 3],
  [-5, 5, -5],
  [5, -5, 5],
  [100.5, -50.25, 25.125],
]

let piorRoundTrip = 0
for (const azimute of azimutes) {
  for (const elevacao of elevacoes) {
    for (const distancia of distancias) {
      for (const alvo of alvos) {
        // alvo → pos → alvo
        const pos = posicaoCamera(azimute, elevacao, distancia, alvo)
        const alvo2 = alvoCamera(azimute, elevacao, distancia, pos)
        // pos → alvo → pos
        const pos2 = posicaoCamera(azimute, elevacao, distancia, alvo2)
        const e1 = erroMax(alvo, alvo2)
        const e2 = erroMax(pos, pos2)
        piorRoundTrip = Math.max(piorRoundTrip, e1, e2)
      }
    }
  }
}
ok(
  piorRoundTrip <= 1e-9,
  `round-trip pos↔alvo: pior erro ${piorRoundTrip} (limite 1e-9)`
)

// ---------------------------------------------------------------- 2. direção de visão unitária
let piorNorma = 0
for (const azimute of azimutes) {
  for (const elevacao of elevacoes) {
    const f = direcaoVisao(azimute, elevacao)
    piorNorma = Math.max(piorNorma, Math.abs(Math.hypot(...f) - 1))
  }
}
ok(
  piorNorma <= 1e-12,
  `‖f(azim,elev)‖ = 1: pior desvio ${piorNorma}`
)

// ---------------------------------------------------------------- 3. ground truth do MuJoCo 3.15
interface CasoGroundTruth {
  azimute: number
  elevacao: number
  distancia: number
  alvo: [number, number, number]
  forward: [number, number, number]
  mid: [number, number, number]
}

const GROUND_TRUTH: CasoGroundTruth[] = [
  { azimute: 0, elevacao: -10, distancia: 2.5, alvo: [0, 0, 1],
    forward: [0.9848077297210693, 0.0, -0.1736481785774231],
    mid: [-2.462019443511963, 0.0, 1.4341204166412354] },
  { azimute: 90, elevacao: -15, distancia: 2.5, alvo: [0, 0, 1],
    forward: [5.914589533937914e-17, 0.9659258127212524, -0.258819043636322],
    mid: [0.0, -2.4148144721984863, 1.6470476388931274] },
  { azimute: 135, elevacao: -25, distancia: 3.0, alvo: [0.5, -0.5, 1.2],
    forward: [-0.6408563852310181, 0.6408563852310181, -0.4226182699203491],
    mid: [2.4225692749023438, -2.4225692749023438, 2.4678547382354736] },
  { azimute: 45.5, elevacao: 30, distancia: 7.3, alvo: [-4, 5, -2],
    forward: [0.60700523853302, 0.6176930069923401, 0.5],
    mid: [-8.43113899230957, 0.4908410310745239, -5.650000095367432] },
  { azimute: 200, elevacao: -89, distancia: 10.0, alvo: [5, -5, 5],
    forward: [-0.016399897634983063, -0.005969074554741383, -0.9998477101325989],
    mid: [5.163999080657959, -4.940309047698975, 14.9984769821167] },
  { azimute: 359.99, elevacao: 0, distancia: 0.1, alvo: [0, 0, 0],
    forward: [1.0, -0.00017453292093705386, 0.0],
    mid: [-0.09999999403953552, 1.7452985048294067e-05, 0.0] },
  { azimute: 123.456, elevacao: -56.789, distancia: 1.234, alvo: [1.1, 2.2, 3.3],
    forward: [-0.30195820331573486, 0.4569711983203888, -0.8366591930389404],
    mid: [1.47261643409729, 1.6360975503921509, 4.332437515258789] },
  { azimute: 270, elevacao: 85, distancia: 4.0, alvo: [-1, 0.5, -3],
    forward: [-1.601024950080881e-17, -0.08715574443340302, 0.9961947202682495],
    mid: [-1.0, 0.8486229777336121, -6.984778881072998] },
]

const TOL_GROUND_TRUTH = 1e-6 // os campos do mjvGLCamera são float32
let piorForward = 0
let piorMid = 0
for (const c of GROUND_TRUTH) {
  const f = direcaoVisao(c.azimute, c.elevacao)
  piorForward = Math.max(piorForward, erroMax(f, c.forward))
  const pos = posicaoCamera(c.azimute, c.elevacao, c.distancia, c.alvo)
  piorMid = Math.max(piorMid, erroMax(pos, c.mid))
}
ok(
  piorForward <= TOL_GROUND_TRUTH,
  `f(azim,elev) vs camera[0].forward do MuJoCo: pior erro ${piorForward} (tol ${TOL_GROUND_TRUTH})`
)
ok(
  piorMid <= TOL_GROUND_TRUTH,
  `pos = alvo − d·f vs pose real (meio do par estereoscópico): pior erro ${piorMid} (tol ${TOL_GROUND_TRUTH})`
)

// ---------------------------------------------------------------- 4. leitura e comparação (contrato v2)
const bruto = { azimute: 370, elevacao: -10, distancia: 2.5, alvo: [0, 0, 1] }
const lido = lerCamera(bruto)
ok(lido !== null && lido.azimute === 10, "lerCamera normaliza o azimute mod 360")
ok(lerCamera({ azimute: 0, elevacao: 0 }) === null, "lerCamera recusa objeto incompleto")
ok(
  lerCamera({ azimute: 0, elevacao: 0, distancia: 0, alvo: [0, 0, 0] }) === null,
  "lerCamera recusa distância nula"
)
ok(
  lerCamera({ azimute: NaN, elevacao: 0, distancia: 1, alvo: [0, 0, 0] }) === null,
  "lerCamera recusa valores não finitos"
)
// contrato v2: `camera_padrao` = {azimute, elevacao, distancia} SEM `alvo` → alvo null (honesto)
const padrao = lerCamera({ azimute: 0, elevacao: -25, distancia: 4 })
ok(
  padrao !== null && padrao.alvo === null,
  "lerCamera aceita camera_padrao sem alvo (v2) e devolve alvo: null"
)
const a: CameraEstado = { azimute: 359.9999999, elevacao: 0, distancia: 1, alvo: [0, 0, 0] }
const b: CameraEstado = { azimute: 0, elevacao: 0, distancia: 1, alvo: [0, 0, 0] }
ok(cameraIgual(a, b, 1e-6), "cameraIgual trata o azimute como circular")
ok(
  !cameraIgual(
    { azimute: 0, elevacao: 0, distancia: 1, alvo: [0, 0, 0] },
    { azimute: 0, elevacao: 0, distancia: 1, alvo: null }
  ),
  "cameraIgual distingue alvo null de alvo presente"
)
ok(normalizarAzimute(-90) === 270, "normalizarAzimute devolve [0,360)")

// ---------------------------------------------------------------- 5. contrato v2 do comando
ok(
  assinaturaCamera({ azimute: 360, elevacao: 0, distancia: 1 }) ===
    assinaturaCamera({ azimute: 0, elevacao: 0, distancia: 1 }),
  "assinaturaCamera normaliza o azimute"
)
ok(
  assinaturaCamera({ distancia: 2 }) !== assinaturaCamera({ distancia: 2, azimute: 10 }),
  "assinaturaCamera distingue subconjuntos de campos"
)
const cam: CameraEstado = { azimute: 12, elevacao: -30, distancia: 3, alvo: [0, 0, 1] }
ok(cameraReflete(cam, { distancia: 3 }), "cameraReflete: subconjunto {distancia} confirmado")
ok(cameraReflete(cam, { azimute: 12, elevacao: -30 }), "cameraReflete: ângulos confirmados")
ok(!cameraReflete(cam, { azimute: 13 }), "cameraReflete rejeita azimute diferente")
ok(!cameraReflete(cam, { elevacao: 30 }), "cameraReflete rejeita elevação trocada de sinal")
ok(
  cameraReflete({ ...cam, azimute: 0 }, { azimute: 360 }),
  "cameraReflete trata o azimute como circular (360 ≡ 0)"
)

// faixas da UI dentro do contrato (a UI nunca manda fora disto; o backend aceita ]0,20] na distância)
ok(
  CAMERA_UI_LIMITES.distancia[0] > 0 &&
    CAMERA_UI_LIMITES.distancia[1] <= 20 &&
    CAMERA_UI_LIMITES.elevacao[0] === -90 &&
    CAMERA_UI_LIMITES.elevacao[1] === 90,
  "faixas da UI dentro do contrato v2"
)

console.log(
  `camera-roundtrip: ${verificacoes - falhas}/${verificacoes} verificações · ` +
    `round-trip máx ${piorRoundTrip.toExponential(3)} · forward máx ${piorForward.toExponential(3)} · ` +
    `pose real máx ${piorMid.toExponential(3)}`
)
if (falhas > 0) process.exit(1)
