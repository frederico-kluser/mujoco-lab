/**
 * PAINEL DE VOO da planta real — os sensores e o estimador de bordo em linguagem de instrumentos.
 *
 * Sem DOM nem React (os testes `testes/planta-real.mts` exercitam ESTE código): converte uma linha da
 * telemetria nos valores que um piloto lê — graus, °/s, cm, cm/s, g — e junta, quando o runner a publica,
 * a VERDADE do simulador nos mesmos referenciais, para o ecrã mostrar «o que o drone acha» ao lado de
 * «o que é» (o erro em xy da política vem quase todo do estimador: medido em 2026-10-10).
 *
 * Fontes, por ordem de confiança:
 *  · MEDIDO (sensores, com erro): giroscópio e acelerómetro = `obs[0:6]` × escala (`env_real.observacao`);
 *    validade do ToF e do fluxo = `obs[15]`, `obs[16]`;
 *  · ESTIMADO a bordo (o que o RPi calcula SÓ com os sensores): bloco `estimador` (altura ABSOLUTA ĥ,
 *    atitude, rumo desde o armar, velocidades no referencial do nariz, odometria no de arranque) — se não
 *    vier, cai para os canais do ator `obs[6:15]` (a altura vem relativa ao alvo, por isso soma-se o alvo);
 *  · VERDADE do simulador (`verdade`): só para comparar — a política nunca a vê.
 *
 * Eixos do simulador (os do estimador): x = frente, y = ESQUERDA, z = cima. Rolamento + = inclinado para
 * a direita; arfagem + = nariz para BAIXO (verificado no MuJoCo: rodar +10° em y baixa o nariz).
 * Estados honestos: o que não vier sai `null` e o ecrã mostra «—».
 */

import { ALVO_Z, GRAUS_POR_RAD, GRAVIDADE, type LinhaSim } from "./sim.ts"

/** Escala do giroscópio na observação do ator (`env_real.ESCALA_GIRO`: obs = ω / 2). */
export const ESCALA_GIRO_OBS = 2

/** Um valor estimado a bordo e o verdadeiro, na MESMA unidade amigável (`null` = não veio). */
export interface Par {
  estimado: number | null
  real: number | null
}

/** Tudo o que o painel de voo desenha, em unidades amigáveis. */
export interface PainelVooDados {
  /** Rolamento e arfagem (graus): estimados a bordo vs reais. */
  rolamento: Par
  arfagem: Par
  /** Rumo desde o arranque (graus, ]−180, 180]). */
  rumo: Par
  /** Rumo ABSOLUTO real (graus) — o das vistas rápidas da câmara; `null` sem verdade. */
  rumoAbsoluto: number | null
  /** Altura do CM (m) e o alvo (m). */
  altura: Par
  alvoAltura: number
  /** Velocidade vertical (cm/s, + = a subir). */
  vz: Par
  /** Velocidade horizontal no referencial do NARIZ (cm/s): frente, esquerda. */
  vFrente: Par
  vEsquerda: Par
  /** Posição no referencial de ARRANQUE (cm): frente (x), esquerda (y) — odometria vs verdade. */
  x: Par
  y: Par
  /** O alvo de posição nesse referencial (cm); `[0, 0]` sem verdade (o alvo da odometria é a origem). */
  alvoXy: [number, number]
  /** Distância do estimado ao real em xy (cm) — o ERRO DO ESTIMADOR; `null` sem os dois. */
  erroEstimadorXy: number | null
  /** Distância (cm) ao alvo: da posição estimada e da real. */
  distAlvo: Par
  /** Giroscópio MEDIDO (°/s): p, q, r — e os verdadeiros, se vierem. */
  giro: [Par, Par, Par]
  /** Acelerómetro MEDIDO (g): x, y, z e a norma. */
  acc: [number | null, number | null, number | null]
  accNorma: number | null
  /** Sensores válidos (`null` = a linha não o diz). */
  tofOk: boolean | null
  fluxoOk: boolean | null
  /** Há verdade do simulador nesta linha? (sem ela o painel só mostra o estimado) */
  temVerdade: boolean
  /** Há estimativas de bordo (bloco `estimador` ou canais do ator)? */
  temEstimador: boolean
}

function graus(rad: number | null | undefined): number | null {
  return rad === null || rad === undefined || !Number.isFinite(rad)
    ? null
    : rad * GRAUS_POR_RAD
}

function vezes(v: number | null | undefined, k: number): number | null {
  return v === null || v === undefined || !Number.isFinite(v) ? null : v * k
}

/** Ângulo em graus para ]−180, 180]. */
export function envolverGraus(g: number): number {
  const r = ((((g + 180) % 360) + 360) % 360) - 180
  return r === -180 ? 180 : r
}

/** Canal `i` da observação do ator (`null` se a linha não tiver obs reais). */
function canal(linha: LinhaSim, i: number): number | null {
  if (linha.planta !== "real") return null
  const v = linha.obs[i]
  return typeof v === "number" && Number.isFinite(v) ? v : null
}

/**
 * Uma linha da telemetria → os valores do painel de voo (graus, cm, cm/s, °/s, g). `null` na linha (sem
 * dados) dá tudo a `null`; o cf2 (sem bloco `estimador`/`verdade`) dá só o que a obs do cf2 não tem: nada.
 */
export function lerPainelVoo(linha: LinhaSim | null): PainelVooDados {
  const est = linha?.estimador ?? null
  const ver = linha?.verdade ?? null
  const alvoZ = ver?.alvoZ ?? ALVO_Z

  const obs = (i: number) => (linha === null ? null : canal(linha, i))
  // estimador: o bloco `estimador` manda; os canais do ator são o recurso (mesmas grandezas)
  const rollEst = est?.roll ?? obs(6)
  const pitchEst = est?.pitch ?? obs(7)
  const psiEst = est?.psi ?? vezes(obs(8), Math.PI)
  const hRel = obs(9)
  const hEst = est?.h ?? (hRel === null ? null : hRel + alvoZ)
  const vzEst = est?.vz ?? obs(10)
  const vxEst = est?.vx ?? obs(11)
  const vyEst = est?.vy ?? obs(12)
  const xEst = est?.x ?? obs(13)
  const yEst = est?.y ?? obs(14)

  const alvoXy: [number, number] =
    ver?.alvoXy === null || ver?.alvoXy === undefined
      ? [0, 0]
      : [ver.alvoXy[0] * 100, ver.alvoXy[1] * 100]

  const x: Par = { estimado: vezes(xEst, 100), real: vezes(ver?.x, 100) }
  const y: Par = { estimado: vezes(yEst, 100), real: vezes(ver?.y, 100) }
  const erroEstimadorXy =
    x.estimado === null ||
    y.estimado === null ||
    x.real === null ||
    y.real === null
      ? null
      : Math.hypot(x.estimado - x.real, y.estimado - y.real)
  const distancia = (px: number | null, py: number | null) =>
    px === null || py === null
      ? null
      : Math.hypot(px - alvoXy[0], py - alvoXy[1])

  const giroMedido = [0, 1, 2].map((i) =>
    vezes(obs(i), ESCALA_GIRO_OBS * GRAUS_POR_RAD)
  )
  const giroReal = [ver?.p ?? null, ver?.q ?? null, ver?.r ?? null].map((v) =>
    graus(v)
  )
  // acelerómetro: obs = a / g ⇒ em g é a própria obs
  const acc: [number | null, number | null, number | null] = [
    obs(3),
    obs(4),
    obs(5),
  ]
  const accNorma = acc.every((v) => v !== null)
    ? Math.hypot(acc[0] as number, acc[1] as number, acc[2] as number)
    : null
  const tof = obs(15)
  const fluxo = obs(16)

  const psiReal = graus(ver?.psi)
  return {
    rolamento: { estimado: graus(rollEst), real: graus(ver?.roll) },
    arfagem: { estimado: graus(pitchEst), real: graus(ver?.pitch) },
    rumo: {
      estimado: psiEst === null ? null : envolverGraus(psiEst * GRAUS_POR_RAD),
      real: psiReal === null ? null : envolverGraus(psiReal),
    },
    rumoAbsoluto: graus(ver?.yaw),
    altura: { estimado: hEst, real: ver?.z ?? null },
    alvoAltura: alvoZ,
    vz: { estimado: vezes(vzEst, 100), real: vezes(ver?.vz, 100) },
    vFrente: { estimado: vezes(vxEst, 100), real: vezes(ver?.vx, 100) },
    vEsquerda: { estimado: vezes(vyEst, 100), real: vezes(ver?.vy, 100) },
    x,
    y,
    alvoXy,
    erroEstimadorXy,
    distAlvo: {
      estimado: distancia(x.estimado, y.estimado),
      real: distancia(x.real, y.real),
    },
    giro: [0, 1, 2].map((i) => ({
      estimado: giroMedido[i],
      real: giroReal[i],
    })) as [Par, Par, Par],
    acc,
    accNorma,
    tofOk: tof === null ? null : tof >= 0.5,
    fluxoOk: fluxo === null ? null : fluxo >= 0.5,
    temVerdade: ver !== null,
    temEstimador: est !== null || (linha !== null && linha.planta === "real"),
  }
}

/** Aceleração (m/s²) → g (para textos: «1,00 g»). */
export function emG(ms2: number | null): number | null {
  return ms2 === null ? null : ms2 / GRAVIDADE
}

/**
 * Meia-largura do mapa de posição (cm): o menor de 10/20/50/100/200 que contém todos os pontos com 20 %
 * de folga — o mapa aproxima-se quando o drone está bem parado e afasta-se quando deriva.
 */
export function escalaMapaCm(pontos: (number | null)[]): number {
  const maximo = pontos.reduce<number>(
    (m, v) =>
      v === null || !Number.isFinite(v) ? m : Math.max(m, Math.abs(v)),
    0
  )
  for (const e of [10, 20, 50, 100, 200]) if (maximo * 1.2 <= e) return e
  return 500
}

/**
 * Rodar um vetor do referencial do NARIZ para o de ARRANQUE (o da odometria): v_arranque = R(ψ)·v_nariz,
 * com ψ = rumo desde o arranque (graus). Serve para desenhar a seta da velocidade no mapa de posição.
 */
export function doNarizParaArranque(
  frente: number,
  esquerda: number,
  rumoGraus: number
): [number, number] {
  const r = rumoGraus / GRAUS_POR_RAD
  const c = Math.cos(r)
  const s = Math.sin(r)
  return [c * frente - s * esquerda, s * frente + c * esquerda]
}

/** Texto curto de um ângulo de inclinação: «1,2° à direita», «0,4° nariz em baixo», «nivelado». */
export function textoInclinacao(
  graus: number | null,
  eixo: "rolamento" | "arfagem",
  limiarNivel = 0.5
): string {
  if (graus === null) return "—"
  const a = Math.abs(graus)
  if (a < limiarNivel) return "nivelado"
  const v = a.toFixed(1).replace(".", ",")
  if (eixo === "rolamento")
    return `${v}° ${graus > 0 ? "à direita" : "à esquerda"}`
  return `${v}° nariz ${graus > 0 ? "em baixo" : "em cima"}`
}
