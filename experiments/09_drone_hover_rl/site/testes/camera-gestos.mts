/**
 * Testes do WIDGET «Câmara» v3 (vistas de cima e de lado + zoom logarítmico + vistas rápidas + REPOR VISTA)
 * contra o CÓDIGO DE PRODUÇÃO (`src/lib/camera-gestos.ts` — geometria e máquina de gestos):
 *
 *  1. GEOMETRIA provada contra a fórmula do MuJoCo `pos = alvo − d·f` (ver `src/lib/sim.ts`, ground truth
 *     3.15): o ícone da VISTA DE CIMA fica na direção real da câmara (frente para cima, esquerda à
 *     esquerda), ida e volta exata ponto↔azimute; a VISTA DE LADO sobe quando a câmara sobe, ida e volta
 *     dentro da faixa da UI e trava fora dela; o zoom é logarítmico e respeita os limites da planta;
 *  2. VISTAS RÁPIDAS: «atrás» põe a câmara ATRÁS do nariz (para qualquer rumo), «frente» à frente,
 *     «esquerda»/«direita» do lado certo, «de cima» a pique — e a descrição em português diz o mesmo;
 *  3. DEF-1: um gesto sob telemetria viva envia SEMPRE os valores do gesto (snapshot no fim do gesto e em
 *     cada envio) — a telemetria nunca sobrescreve valores durante o arrasto nem com envio pendente;
 *  4. DEF-2: `camera`/`camera_atual` a passar a `null` mostra «—» — `null`→valor→`null` termina em «—»;
 *  5. REPOR VISTA e vistas rápidas enviam SEMPRE; a coalescência manda 1 comando por mudança final; o
 *     zoom respeita os limites injetados.
 *
 * Corre sem dependências: `node testes/camera-gestos.mts` (Node ≥ 22.6 com type-stripping).
 */

import {
  ALTURA_ANGULAR_UI,
  alturaDeElevacao,
  anguloVistaRapida,
  aplicarZoom,
  azimuteDePontoTopo,
  CONFIRMACAO_CAMERA_MS,
  descreverCamera,
  distanciaDeFracao,
  elevacaoDePontoLado,
  fracaoDeDistancia,
  limitesDistancia,
  MaquinaCamera,
  orbitar,
  pontoLadoDeElevacao,
  pontoTopoDeAzimute,
  rotacaoGlifoTopo,
  VISTAS_RAPIDAS,
  type FaseEnvio,
} from "../src/lib/camera-gestos.ts"
import {
  posicaoCamera,
  type CameraEstado,
  type CorpoCamera,
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

function perto(a: number, b: number, eps = 1e-9): boolean {
  return Math.abs(a - b) <= eps
}

const alvoMundo: [number, number, number] = [0.3, -0.2, 1]

// ---------------------------------------------------------------- 1a. vista de cima ↔ fórmula do MuJoCo
// mundo (x frente, y esquerda) → ecrã (sx direita, sy baixo): sx = −wy, sy = −wx
let piorTopo = 0
let piorIdaVoltaTopo = 0
for (const azimute of [0, 1, 30, 45.5, 90, 135, 180, 225, 270, 315, 359.9]) {
  for (const elevacao of [-80, -45, -10, 0, 20]) {
    const pos = posicaoCamera(azimute, elevacao, 2.5, alvoMundo)
    const wx = pos[0] - alvoMundo[0]
    const wy = pos[1] - alvoMundo[1]
    const n = Math.hypot(wx, wy)
    const esperado = { sx: -wy / n, sy: -wx / n }
    const p = pontoTopoDeAzimute(azimute)
    piorTopo = Math.max(piorTopo, Math.abs(p.sx - esperado.sx), Math.abs(p.sy - esperado.sy))
    const volta = azimuteDePontoTopo(p.sx * 37, p.sy * 37) ?? NaN
    const d = Math.abs(volta - azimute)
    piorIdaVoltaTopo = Math.max(piorIdaVoltaTopo, Math.min(d, 360 - d))
  }
}
ok(piorTopo <= 1e-9, `vista de cima: o ícone está na direção REAL da câmara (pior erro ${piorTopo})`)
ok(piorIdaVoltaTopo <= 1e-9, `vista de cima: ponto↔azimute ida e volta exata (pior ${piorIdaVoltaTopo}°)`)
ok(perto(pontoTopoDeAzimute(0).sy, 1) && perto(pontoTopoDeAzimute(0).sx, 0), "azimute 0° (olha para +x) = câmara em BAIXO na vista de cima (atrás de um drone de rumo 0)")
ok(perto(pontoTopoDeAzimute(90).sx, 1), "azimute 90° (olha para +y, a esquerda) = câmara à DIREITA")
ok(azimuteDePontoTopo(0.1, 0.1, 1) === null, "vista de cima: muito perto do centro não há direção (null)")
ok(rotacaoGlifoTopo(30) === -30, "glifo do drone: rumo + (nariz para a esquerda) roda −ψ no SVG")

// ---------------------------------------------------------------- 1b. vista de lado ↔ fórmula do MuJoCo
let piorLado = 0
for (const elevacao of [-89, -60, -30, -5, 0, 10, 30]) {
  const pos = posicaoCamera(0, elevacao, 2, alvoMundo)
  const subida = (pos[2] - alvoMundo[2]) / 2 // sin(h)
  const p = pontoLadoDeElevacao(elevacao)
  piorLado = Math.max(piorLado, Math.abs(-p.sy - subida))
  const volta = elevacaoDePontoLado(p.sx * 50, p.sy * 50) ?? NaN
  piorLado = Math.max(piorLado, Math.abs(volta - elevacao))
}
ok(piorLado <= 1e-9, `vista de lado: subir no ecrã = câmara mais ALTA (pos_z) e ida e volta exata (pior ${piorLado})`)
ok(alturaDeElevacao(-45) === 45, "altura acima do horizonte = −elevação (MuJoCo: negativa = por cima)")
ok(elevacaoDePontoLado(10, -50) === -ALTURA_ANGULAR_UI[1], "vista de lado: passar por cima do drone trava a pique (89°)")
ok(elevacaoDePontoLado(10, 50) === -ALTURA_ANGULAR_UI[0], "vista de lado: passar por baixo trava em −30° (abaixo do horizonte)")
ok(elevacaoDePontoLado(-50, 200) === -ALTURA_ANGULAR_UI[0], "vista de lado: muito abaixo trava em −30°")

// ---------------------------------------------------------------- 1c. zoom logarítmico e passos
const lim = limitesDistancia("real")
ok(lim[0] === 0.6 && lim[1] === 15 && limitesDistancia("cf2")[1] === 5 && limitesDistancia(null)[0] === 0.1, "limites de distância por planta")
let piorZoom = 0
for (const d of [0.6, 1, 2, 3.7, 15]) piorZoom = Math.max(piorZoom, Math.abs(distanciaDeFracao(fracaoDeDistancia(d, lim), lim) - d))
ok(piorZoom <= 1e-9, "zoom: fração↔distância ida e volta exata")
ok(perto(distanciaDeFracao(0.5, lim), Math.sqrt(0.6 * 15)), "zoom LOGARÍTMICO: o meio do trilho é a média geométrica")
ok(fracaoDeDistancia(100, lim) === 1 && fracaoDeDistancia(0.01, lim) === 0 && fracaoDeDistancia(-1, lim) === 0, "zoom: fora dos limites trava")
ok(perto(aplicarZoom(2, 1, lim), 1.6) && perto(aplicarZoom(2, -1, lim), 2.5) && aplicarZoom(0.7, 5, lim) === 0.6, "zoom ±: ×1,25 por passo, travado")
const o = orbitar(350, -20, 1, 1)
ok(o.azimute === 5 && o.elevacao === -30, "passos: +15° de órbita com wrap e +10° de altura")
ok(orbitar(0, -85, 0, 1).elevacao === -89 && orbitar(0, 25, 0, -1).elevacao === 30, "passos: a altura trava na faixa da UI")

// ---------------------------------------------------------------- 2. vistas rápidas (para vários rumos)
for (const rumo of [0, 37, -120, 200]) {
  const nariz = [Math.cos((rumo * Math.PI) / 180), Math.sin((rumo * Math.PI) / 180)]
  const esquerda = [-nariz[1], nariz[0]]
  const relativa = (v: "atras" | "frente" | "esquerda" | "direita") => {
    const a = anguloVistaRapida(v, rumo)
    const pos = posicaoCamera(a.azimute, a.elevacao, 3, [0, 0, 1])
    return { frente: pos[0] * nariz[0] + pos[1] * nariz[1], lado: pos[0] * esquerda[0] + pos[1] * esquerda[1], a }
  }
  const at = relativa("atras")
  const fr = relativa("frente")
  const es = relativa("esquerda")
  const di = relativa("direita")
  ok(at.frente < -2 && Math.abs(at.lado) < 1e-9, `rumo ${rumo}°: «Atrás» põe a câmara ATRÁS do nariz`)
  ok(fr.frente > 2 && Math.abs(fr.lado) < 1e-9, `rumo ${rumo}°: «Frente» à frente`)
  ok(es.lado > 2 && Math.abs(es.frente) < 1e-9, `rumo ${rumo}°: «Esquerda» do lado esquerdo do drone`)
  ok(di.lado < -2 && Math.abs(di.frente) < 1e-9, `rumo ${rumo}°: «Direita» do lado direito`)
  ok(
    descreverCamera(at.a.azimute, at.a.elevacao, rumo).lado === "atrás" &&
      descreverCamera(fr.a.azimute, fr.a.elevacao, rumo).lado === "à frente" &&
      descreverCamera(es.a.azimute, es.a.elevacao, rumo).lado === "à esquerda" &&
      descreverCamera(di.a.azimute, di.a.elevacao, rumo).lado === "à direita",
    `rumo ${rumo}°: a descrição em português diz onde a câmara está`
  )
}
ok(anguloVistaRapida("cima", 10).elevacao === -89 && VISTAS_RAPIDAS.length === 6, "«De cima» a pique; 6 vistas rápidas")
ok(
  descreverCamera(0, -45, 0).altura === "45° por cima" && descreverCamera(0, -80, 0).altura.startsWith("quase a pique") &&
    descreverCamera(0, 0, 0).altura === "à altura do drone" && descreverCamera(0, 20, 0).altura === "20° por baixo",
  "descrição da altura da câmara"
)
ok(descreverCamera(45, -30, 0).lado === "atrás, à direita" && descreverCamera(-135, -30, 0).lado === "à frente, à esquerda", "descrição das diagonais")

// ---------------------------------------------------------------- máquina de gestos (rig com relógio/agendador injetáveis)
interface Rig {
  maquina: MaquinaCamera
  envios: CorpoCamera[]
  mostrado: () => CameraEstado | null
  avancar: (ms: number) => void
}

function criarRig(ligado = true): Rig {
  const envios: CorpoCamera[] = []
  let mostrado: CameraEstado | null = null
  let agora = 0
  let fila: { quando: number; tarefa: () => void }[] = []
  const maquina = new MaquinaCamera({
    enviar: (corpo) => {
      envios.push({ ...corpo })
      return Promise.resolve()
    },
    aoMostrar: (v) => {
      mostrado = v
    },
    aoFase: (_f: FaseEnvio) => {},
    aoAvisar: () => {},
    ligado: () => ligado,
    relogio: () => agora,
    agendar: (tarefa, ms) => {
      const handle = { quando: agora + ms, tarefa }
      fila.push(handle)
      return handle
    },
    cancelar: (handle) => {
      fila = fila.filter((x) => x !== handle)
    },
  })
  const avancar = (ms: number) => {
    const limite = agora + ms
    for (;;) {
      const prontos = fila.filter((x) => x.quando <= limite)
      if (prontos.length === 0) break
      prontos.sort((x, y) => x.quando - y)
      for (const p of prontos) {
        fila = fila.filter((x) => x !== p)
        agora = p.quando
        p.tarefa()
      }
    }
    agora = limite
  }
  return { maquina, envios, mostrado: () => mostrado, avancar }
}

const camAntigo: CameraEstado = {
  azimute: 10,
  elevacao: -5,
  distancia: 2,
  alvo: [0, 0, 1],
}

// ---------------------------------------------------------------- 2. DEF-1 — os valores enviados são os do GESTO
{
  // cenário medido: um poll da telemetria entre a edição e o envio agendado (debounce 150 ms)
  const rig = criarRig()
  rig.maquina.receberCamera(camAntigo)
  rig.maquina.editarDistancia(3.3) // agenda o envio
  rig.maquina.receberCamera(camAntigo) // ← o poll que roubava os gestos (DEF-1)
  ok(
    rig.mostrado()?.distancia === 3.3,
    "DEF-1: a telemetria não sobrescreve os valores do gesto com envio pendente"
  )
  rig.avancar(150)
  ok(
    rig.envios.length === 1 && rig.envios[0].distancia === 3.3,
    `DEF-1: o POST leva os valores do gesto (3.3), não os da telemetria — enviados ${JSON.stringify(rig.envios)}`
  )
}

{
  // arrasto do pad com telemetria viva: coalescência durante o arrasto + commit final ao largar
  const rig = criarRig()
  rig.maquina.receberCamera(camAntigo)
  rig.maquina.comecarArrasto()
  rig.maquina.editarAngulos(200, -30)
  rig.avancar(50)
  rig.maquina.editarAngulos(210, -35)
  rig.maquina.receberCamera(camAntigo) // poll durante o arrasto — ignorado
  ok(
    rig.mostrado()?.azimute === 210,
    "DEF-1: durante o arrasto o mostrador segue o gesto, não a telemetria"
  )
  rig.avancar(100) // 150 ms desde o primeiro evento: dispara UM comando coalescido
  ok(
    rig.envios.length === 1 && rig.envios[0].azimute === 210 && rig.envios[0].elevacao === -35,
    `coalescência: 2 movimentos → 1 comando com o valor mais recente (${JSON.stringify(rig.envios)})`
  )
  rig.maquina.editarAngulos(220, -40)
  rig.maquina.terminarGesto() // COMMIT FINAL imediato, com os valores finais do gesto
  ok(
    rig.envios.length === 2 && rig.envios[1].azimute === 220 && rig.envios[1].elevacao === -40,
    "DEF-1: o commit final ao largar envia os valores FINAIS do gesto"
  )
  rig.maquina.receberCamera(camAntigo) // envio ainda por confirmar — não puxa para trás
  ok(
    rig.mostrado()?.azimute === 220 && rig.mostrado()?.elevacao === -40,
    "DEF-1: com envio por confirmar a telemetria antiga não sobrescreve o gesto"
  )
  rig.maquina.receberCamera({
    azimute: 220,
    elevacao: -40,
    distancia: camAntigo.distancia,
    alvo: camAntigo.alvo,
  }) // a câmara real confirma → adota-se
  ok(
    rig.mostrado()?.azimute === 220,
    "confirmada pela câmara real, a telemetria volta a ser adotada"
  )
}

// ------------------------------------------------- 2b. REGRESSÃO M5 — telemetria a meio do arrasto
// A guarda `if (this._arrastando) return` de `receberCamera` é a ÚNICA proteção quando não há
// snapshot por disparar (comando ao vivo já despachado e janela de confirmação expirada): sem ela,
// uma câmara externa/rato da janela a meio do arrasto escreve nos valores do gesto — e um passo do
// arrasto que coincida com os valores da amostra torna-se um no-op que engole o commit do largar.
{
  const camExterno: CameraEstado = {
    azimute: 55,
    elevacao: 20,
    distancia: 9,
    alvo: [0, 0, 1],
  }

  // (a) arrasto longo: comando ao vivo + confirmação expirada + amostra externa no meio
  const rig = criarRig()
  rig.maquina.receberCamera(camAntigo) // adota (10, −5, 2)
  rig.maquina.comecarArrasto()
  rig.maquina.editarAngulos(200, -30) // gesto arrasta para (200, −30)
  rig.avancar(150) // dispara o comando ao vivo coalescido
  ok(
    rig.envios.length === 1 && rig.envios[0].azimute === 200 && rig.envios[0].elevacao === -30,
    "M5: o comando ao vivo do arrasto leva os valores do gesto"
  )
  rig.avancar(CONFIRMACAO_CAMERA_MS + 1) // sem confirmação da câmara real: a janela expira
  rig.maquina.receberCamera(camExterno) // câmara externa chega a meio do arrasto — tem de ser ignorada
  ok(
    rig.mostrado()?.azimute === 200 &&
      rig.mostrado()?.elevacao === -30 &&
      rig.mostrado()?.distancia === camAntigo.distancia,
    `M5: a câmara externa a meio do arrasto não altera os valores do gesto (${JSON.stringify(rig.mostrado())})`
  )
  rig.maquina.editarAngulos(210, -35) // o arrasto continua a partir dos valores do GESTO
  rig.maquina.terminarGesto() // COMMIT FINAL
  ok(
    rig.envios.length === 2 && rig.envios[1].azimute === 210 && rig.envios[1].elevacao === -35,
    `M5: ao largar o comando leva os valores do gesto (210, −35), não os da câmara externa (${JSON.stringify(rig.envios)})`
  )

  // (b) o arrasto termina EXATAMENTE nos valores da amostra externa: o commit tem de sair à mesma
  const rig2 = criarRig()
  rig2.maquina.receberCamera(camAntigo)
  rig2.maquina.comecarArrasto()
  rig2.maquina.editarAngulos(200, -30)
  rig2.avancar(150) // comando ao vivo {200, −30}
  rig2.avancar(CONFIRMACAO_CAMERA_MS + 1)
  rig2.maquina.receberCamera(camExterno) // ignorada durante o arrasto
  rig2.maquina.editarAngulos(camExterno.azimute, camExterno.elevacao) // passo final do gesto
  rig2.maquina.terminarGesto()
  ok(
    rig2.envios.length === 2 &&
      rig2.envios[1].azimute === camExterno.azimute &&
      rig2.envios[1].elevacao === camExterno.elevacao,
    `M5: o largar regista/envia o passo final do gesto mesmo quando coincide com a amostra (${JSON.stringify(rig2.envios)})`
  )
}

{
  // REPOR VISTA = enviar o camera_padrao ({azimute, elevacao, distancia}) — imediato e sem alvo
  const rig = criarRig()
  rig.maquina.receberCamera(camAntigo)
  rig.maquina.reporVista({ azimute: 0, elevacao: -25, distancia: 4, alvo: null })
  ok(
    rig.envios.length === 1 &&
      rig.envios[0].azimute === 0 &&
      rig.envios[0].elevacao === -25 &&
      rig.envios[0].distancia === 4 &&
      !("alvo" in rig.envios[0]),
    `REPOR VISTA envia o camera_padrao no corpo v2 (${JSON.stringify(rig.envios[0])})`
  )
  // o REPOR VISTA é um comando explícito: envia SEMPRE, mesmo sem mudança posterior
  rig.maquina.reporVista({ azimute: 0, elevacao: -25, distancia: 4, alvo: null })
  ok(rig.envios.length === 2, "REPOR VISTA envia sempre (não passa pela coalescência)")
}

{
  // sem ligação: nada se envia e o estado é honesto
  const rig = criarRig(false)
  rig.maquina.receberCamera(camAntigo)
  rig.maquina.editarDistancia(5)
  rig.avancar(150)
  ok(rig.envios.length === 0, "sem ligação à API não se dispara envio")
}

// ---------------------------------------------------------------- 3. DEF-2 — null ⇒ «—», sempre
{
  const rig = criarRig()
  rig.maquina.receberCamera(camAntigo)
  ok(rig.mostrado() !== null, "DEF-2: com dados o widget mostra valores")
  rig.maquina.receberCamera(null) // janela fechada
  ok(
    rig.mostrado() === null && rig.maquina.semDados,
    "DEF-2: camera a null ⇒ «—» (semDados), não o valor antigo"
  )
  rig.maquina.receberCamera(camAntigo)
  ok(rig.mostrado() !== null, "DEF-2: voltou a haver dados")
  rig.maquina.receberCamera(null)
  ok(
    rig.mostrado() === null && rig.maquina.semDados,
    "DEF-2: null→valor→null termina em «—»"
  )
}

{
  // DEF-1 + DEF-2 juntos: um `null` a meio não rouba os valores do gesto ao envio
  const rig = criarRig()
  rig.maquina.receberCamera(camAntigo)
  rig.maquina.editarDistancia(7.5) // snapshot {distancia: 7.5}
  rig.maquina.receberCamera(null) // DEF-2: «—» no mostrador
  ok(rig.mostrado() === null, "DEF-2: o mostrador mostra «—» com envio pendente")
  rig.avancar(150)
  ok(
    rig.envios.length === 1 && rig.envios[0].distancia === 7.5,
    "DEF-1: o envio leva os valores do gesto mesmo com «—» no mostrador"
  )
}

// ---------------------------------------------------------------- 5. vistas rápidas (irPara) e limites
{
  const envios: CorpoCamera[] = []
  let mostrado: CameraEstado | null = null
  const m = new MaquinaCamera({
    enviar: (corpo) => {
      envios.push(corpo)
      return Promise.resolve()
    },
    aoMostrar: (v) => {
      mostrado = v
    },
    aoFase: () => undefined,
    aoAvisar: () => undefined,
    ligado: () => true,
    limitesDistancia: () => [0.6, 15],
    agendar: () => 1,
    cancelar: () => undefined,
  })
  m.receberCamera({ azimute: 10, elevacao: -5, distancia: 2, alvo: [0, 0, 1] })
  m.irPara({ azimute: 200, elevacao: -20 })
  ok(
    envios.length === 1 && envios[0].azimute === 200 && envios[0].elevacao === -20 && envios[0].distancia === 2,
    "irPara: envia JÁ a vista com o corpo COMPLETO, mantendo a distância atual (o zoom é do dono)"
  )
  m.irPara({ azimute: 200, elevacao: -20 })
  ok(envios.length === 2, "irPara: um clique repetido volta a enviar (comando explícito, sem coalescência)")
  ok(mostrado !== null && (mostrado as CameraEstado).azimute === 200, "irPara: o widget mostra a vista pedida")
  m.editarDistancia(0.1)
  ok((mostrado as CameraEstado | null)?.distancia === 0.6, "editarDistancia: trava no limite injetado da planta (0,6 m)")
}
{
  // corpo COMPLETO (medido em 2026-10-10: um comando só com ângulos era completado no servidor com a
  // distância do Crazyflie, 0,27 m, e a câmara do drone real saltava para dentro dele)
  const envios: CorpoCamera[] = []
  let agendado: (() => void) | null = null
  const m = new MaquinaCamera({
    enviar: (corpo) => {
      envios.push(corpo)
      return Promise.resolve()
    },
    aoMostrar: () => undefined,
    aoFase: () => undefined,
    aoAvisar: () => undefined,
    ligado: () => true,
    agendar: (tarefa) => {
      agendado = tarefa
      return 1
    },
    cancelar: () => {
      agendado = null
    },
  })
  m.receberCamera({ azimute: 90, elevacao: -45, distancia: 1.95, alvo: [0, 0, 1] })
  m.comecarArrasto()
  m.editarAngulos(120, -30)
  m.terminarGesto()
  ok(
    envios.length === 1 && envios[0].azimute === 120 && envios[0].elevacao === -30 && envios[0].distancia === 1.95,
    `gesto de ângulos envia o corpo COMPLETO com a distância REAL mostrada (${JSON.stringify(envios[0])})`
  )
  m.receberCamera({ azimute: 120, elevacao: -30, distancia: 1.95, alvo: [0, 0, 1] }) // confirma
  m.receberCamera({ azimute: 120, elevacao: -30, distancia: 4.2, alvo: [0, 0, 1] }) // zoom com o rato da janela
  m.editarAngulos(130, -30)
  ;(agendado as (() => void) | null)?.()
  ok(
    envios.length === 2 && envios[1].distancia === 4.2,
    `um zoom feito com o rato na janela NÃO é desfeito pelo comando seguinte do site (${JSON.stringify(envios[1])})`
  )
}

console.log(
  `camera-gestos: ${verificacoes - falhas}/${verificacoes} verificações · vista de cima vs MuJoCo máx ${piorTopo.toExponential(3)} · vista de lado máx ${piorLado.toExponential(3)}`
)
if (falhas > 0) process.exit(1)
