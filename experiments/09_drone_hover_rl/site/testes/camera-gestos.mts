/**
 * Testes do WIDGET «Câmara» (pad + slider de distância + REPOR VISTA) contra o CÓDIGO DE PRODUÇÃO
 * (`src/lib/camera-gestos.ts` — mapeamento esfera↔ângulos e a máquina de gestos):
 *
 *  1. MAPEAMENTO esfera↔ângulos: wrap 360↔0 nas bordas laterais, limites ±90 (a esfera trava nas
 *     bordas superior/inferior) e o SINAL da elevação — arrastar para cima põe a câmara MAIS ALTA,
 *     provado com a fórmula do MuJoCo `pos = alvo − d·f` (ver `src/lib/sim.ts`, ground truth 3.15);
 *  2. DEF-1: um gesto sob telemetria viva envia SEMPRE os valores do gesto (snapshot no fim do
 *     gesto e em cada envio a partir do estado do gesto) — a telemetria nunca sobrescreve valores
 *     durante o arrasto nem enquanto há envio pendente;
 *  3. DEF-2: `camera`/`camera_atual` a passar a `null` mostra «—» — `null`→valor→`null` termina em
 *     «—» (nunca se retém o valor antigo);
 *  4. REPOR VISTA envia o `camera_padrao` e a coalescência manda 1 comando por mudança final.
 *
 * Corre sem dependências: `node testes/camera-gestos.mts` (Node ≥ 22.6 com type-stripping).
 * A prova de NÃO-TAUTOLOGIA (mutação do código de produção numa cópia staged em "$TMPDIR") está
 * documentada no README do site.
 */

import {
  angulosDeEsfera,
  aplicarArrasto,
  esferaDeAngulos,
  esferaDesenho,
  MaquinaCamera,
  CONFIRMACAO_CAMERA_MS,
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

// ---------------------------------------------------------------- 1. mapeamento esfera ↔ ângulos
// ida e volta em grelha larga (o azimute normaliza-se; a elevação trava em ±90)
let piorIdaVolta = 0
for (const azimute of [0, 1, 45.5, 90, 180, 270, 359, 359.999]) {
  for (const elevacao of [-90, -45.5, -10, 0, 10, 44.4, 90]) {
    const e = esferaDeAngulos(azimute, elevacao)
    const a = angulosDeEsfera(e.u, e.w)
    piorIdaVolta = Math.max(
      piorIdaVolta,
      Math.abs(a.azimute - azimute),
      Math.abs(a.elevacao - elevacao)
    )
  }
}
ok(
  piorIdaVolta <= 1e-9,
  `ida e volta esfera↔ângulos exata: pior erro ${piorIdaVolta}`
)

// WRAP 360↔0 nas bordas laterais
ok(perto(esferaDeAngulos(0, 0).u, -1), "azimute 0° = esfera na borda ESQUERDA (u = −1)")
ok(
  esferaDeAngulos(359.999, 0).u > 0.999,
  "azimute quase 360° = esfera encostada à borda DIREITA"
)
ok(angulosDeEsfera(1, 0).azimute === 0, "u = +1 dá WRAP para azimute 0° (360 ≡ 0)")
ok(angulosDeEsfera(-1, 0).azimute === 0, "u = −1 é o mesmo azimute 0° (o wrap fecha o círculo)")
// arrastar para a DIREITA aumenta o azimute e passar na borda faz wrap 360→0
ok(
  aplicarArrasto({ azimute: 350, elevacao: 0 }, 0.1, 0).azimute === 8,
  "arrastar para a direita a partir de 350° dá WRAP 360→0 (350 + 18 = 368 ≡ 8)"
)
ok(
  aplicarArrasto({ azimute: 5, elevacao: 0 }, -0.1, 0).azimute === 347,
  "arrastar para a esquerda a partir de 5° dá WRAP 0→360 (5 − 18 ≡ 347)"
)

// LIMITES ±90: a esfera trava nas bordas superior/inferior
ok(perto(esferaDeAngulos(123, -90).w, 1), "elevação −90° = esfera na borda SUPERIOR (w = +1)")
ok(perto(esferaDeAngulos(123, 90).w, -1), "elevação +90° = esfera na borda INFERIOR (w = −1)")
ok(angulosDeEsfera(0, 5).elevacao === -90, "acima da borda superior a elevação TRAVA em −90°")
ok(angulosDeEsfera(0, -5).elevacao === 90, "abaixo da borda inferior a elevação TRAVA em +90°")
ok(
  aplicarArrasto({ azimute: 0, elevacao: -80 }, 0, 0.5).elevacao === -90,
  "arrastar para cima além do limite trava a elevação em −90°"
)
ok(
  aplicarArrasto({ azimute: 0, elevacao: 80 }, 0, -0.5).elevacao === 90,
  "arrastar para baixo além do limite trava a elevação em +90°"
)

// SINAL DA ELEVAÇÃO: arrastar para CIMA põe a câmara MAIS ALTA (prova com a fórmula)
const alvoMundo: [number, number, number] = [0, 0, 1]
const distanciaMundo = 2.5
const antes = { azimute: 30, elevacao: 10 }
const depois = aplicarArrasto(antes, 0, +0.2) // 0,2 do pad para CIMA (w sobe)
ok(
  depois.elevacao < antes.elevacao,
  "arrastar para cima DIMINUI a elevação (fica mais negativa)"
)
const zAntes = posicaoCamera(antes.azimute, antes.elevacao, distanciaMundo, alvoMundo)[2]
const zDepois = posicaoCamera(depois.azimute, depois.elevacao, distanciaMundo, alvoMundo)[2]
ok(
  zDepois > zAntes,
  `arrastar para cima põe a câmara MAIS ALTA: pos_z ${zAntes} → ${zDepois}`
)
// e os extremos da fórmula: elevação −90° = câmara POR CIMA do alvo; +90° = por baixo
ok(
  perto(posicaoCamera(0, -90, distanciaMundo, alvoMundo)[2], alvoMundo[2] + distanciaMundo),
  "elevação −90° ⇒ pos_z = alvo_z + d (câmara por cima)"
)
ok(
  perto(posicaoCamera(0, 90, distanciaMundo, alvoMundo)[2], alvoMundo[2] - distanciaMundo),
  "elevação +90° ⇒ pos_z = alvo_z − d (câmara por baixo)"
)

// o desenho da esfera fica SEMPRE dentro do círculo (raio ≤ 1)
for (const [u, w] of [[1, 1], [1, -1], [-1, 1], [0.9, 0.9], [0, 1]]) {
  const d = esferaDesenho(u, w)
  ok(Math.hypot(d.u, d.w) <= 1 + 1e-12, `esferaDesenho(${u},${w}) dentro do círculo`)
}

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

console.log(
  `camera-gestos: ${verificacoes - falhas}/${verificacoes} verificações · ida-e-volta máx ${piorIdaVolta.toExponential(3)}`
)
if (falhas > 0) process.exit(1)
