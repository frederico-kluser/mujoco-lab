/**
 * Teste da FONTE «Simulação» do bloco «Câmara FPV»: o parser `lerSimulacao` (defensivo — é o MESMO
 * formato de estado do FPV, é o mesmo `lab/camera_rpi.ModuloCamera`) e a honestidade do custo:
 * a vista da simulação NÃO é hardware de bordo e por isso `custo_pi5` vem `null` + `nota_fonte` a
 * dizer isso. Corre sem dependências: `node testes/simulacao.mts`.
 */

import { lerFpv, lerSimulacao, type SimulacaoEstado } from "../src/lib/sim.ts"

let n = 0
let falhas = 0

function ok(cond: boolean, nome: string, detalhe = ""): void {
  n += 1
  if (!cond) falhas += 1
  console.log(`        [${cond ? "OK  " : "FALHA"}] ${nome}${detalhe ? ` — ${detalhe}` : ""}`)
}

// --------------------------------------------------------- 1) defensivo (espelha o lerFpv)
ok(lerSimulacao(null) === null, "lerSimulacao(null) → null")
ok(lerSimulacao(undefined) === null, "lerSimulacao(undefined) → null")
ok(lerSimulacao({}) === null, "lerSimulacao({}) → null")
ok(lerSimulacao({ foo: 1 }) === null, "lerSimulacao({foo:1}) → null (sem chaves conhecidas não inventa)")
ok(lerSimulacao([1, 2]) === null, "lerSimulacao(array) → null")

// ------------------------------------------- 2) estado real da vista da simulação (fonte simulacao)
const bruto = {
  fonte: "simulacao",
  nota_fonte: "vista da simulação — não é hardware de bordo; só custa CPU ao host",
  ligada: true,
  modo: "1080p50",
  modo_rotulo: "1080p50 (FOV completo)",
  saida: [1920, 1080],
  sensor: [2304, 1296],
  fps_nominal: 50,
  fps_medido: 49.5,
  bytes_medio: 34000,
  bitrate_mbps: 13.5,
  quadros: 1234,
  latencia_modelada_ms: { total_ms: 116 },
  custo_pi5: null, // NUNCA custo de Pi para uma vista do simulador
  host_ms: { render: 2.5, isp: 0.1, jpeg: 3.0, total: 5.6 },
  idade_estado_s: 0.2,
  estado_velho: false,
}
const e = lerSimulacao(bruto) as SimulacaoEstado
ok(e !== null, "estado real da simulação parseia")
ok(e.fonte === "simulacao", "fonte = simulacao", `fonte=${e.fonte}`)
ok(e.notaFonte !== null && e.notaFonte.includes("não é hardware de bordo"),
   "notaFonte presente e honesta", e.notaFonte ?? "null")
ok(e.custoPi5 === null, "custo_pi5 null → custoPi5 null (a vista da simulação não tem custo de Pi)")
ok(e.hostMs !== null && e.hostMs.totalMs === 5.6, "host_ms medido presente (totalMs 5,6 ms)")
ok(e.fpsMedido === 49.5 && e.fpsNominal === 50, "fps nominal/medido parseados")
ok(e.estadoVelho === false && e.idadeEstadoS === 0.2, "frescura parseada (não velho, 0,2 s)")

// ----------------------------------------------- 3) o mesmo parser serve para as duas fontes
ok(JSON.stringify(lerFpv(bruto)) === JSON.stringify(e),
   "lerSimulacao == lerFpv para o mesmo payload (formato partilhado)")

// ------------------------------------------------------- 4) custo presente (fonte camera) intacto
const fpv = lerSimulacao({
  fonte: "camera", nota_fonte: null, ligada: true, modo: "1080p50",
  custo_pi5: { total_nucleos: 0.94 },
}) as SimulacaoEstado
ok(fpv.custoPi5 !== null && fpv.custoPi5.totalNucleos === 0.94,
   "fonte camera mantém o custo do Pi (0,94 núcleo) — só a simulação o anula")

console.log(`\nsimulacao-parser: ${n - falhas}/${n} verificações`)
if (falhas > 0) {
  console.log("FALHOU")
  process.exit(1)
}
console.log("ok")
