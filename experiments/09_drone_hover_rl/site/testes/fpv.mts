/**
 * Teste do BLOCO «Câmara FPV» do site: o parser `lerFpv` (defensivo — nunca inventa um estado), os
 * modos emulados (só os reais; o HDR não aparece) e os rótulos do custo por etapa. Corre sem
 * dependências: `node testes/fpv.mts` (Node ≥ 22.6 com type-stripping).
 *
 * O que se prova (é a fronteira site↔API do módulo de câmara):
 *  · `lerFpv` devolve `null` para AUSÊNCIA e para LIXO (`null`, `{}`, `{foo: 1}`, arrays, strings) —
 *    um payload sem nenhuma chave conhecida nunca vira um «módulo existe mas tudo null»;
 *  · números não finitos (`NaN`/`Infinity`) e tipos errados viram `null` campo a campo (nada de
 *    `undefined`/`NaN` no DOM);
 *  · um estado real parseia campo a campo (incl. `estadoVelho`/`idadeEstadoS` — a frescura que impede
 *    um estado de sessão anterior de parecer atual);
 *  · `MODOS_FPV` são os 6 modos EMULADOS do backend (`lab/camera_rpi.MODOS` com `emulado: true`) e o
 *    HDR (existe no hardware, não é emulado) NÃO está na lista.
 */

import { lerFpv, MODOS_FPV, rotuloEtapaCustoFpv, type FpvEstado } from "../src/lib/sim.ts"

let n = 0
let falhas = 0

function ok(cond: boolean, nome: string, detalhe = ""): void {
  n += 1
  if (!cond) falhas += 1
  console.log(`        [${cond ? "OK  " : "FALHA"}] ${nome}${detalhe ? ` — ${detalhe}` : ""}`)
}

// ---------------------------------------------------------------------------- 1) ausência e lixo
ok(lerFpv(null) === null, "lerFpv(null) → null")
ok(lerFpv(undefined) === null, "lerFpv(undefined) → null")
ok(lerFpv({}) === null, "lerFpv({}) → null (objeto vazio não é estado)")
ok(lerFpv({ foo: 1 }) === null, "lerFpv({foo:1}) → null (sem chaves conhecidas NÃO inventa estado)")
ok(lerFpv([1, 2, 3]) === null, "lerFpv([1,2,3]) → null")
ok(lerFpv("1080p50") === null, "lerFpv(string) → null")
ok(lerFpv(42) === null, "lerFpv(número) → null")

// ------------------------------------------------------- 2) não finitos e tipos errados → null
const parcial = lerFpv({
  ligada: true,
  modo: "1080p50",
  saida: [1920, 1080],
  fps_nominal: 50,
  fps_medido: Number.NaN,
  bitrate_mbps: Number.POSITIVE_INFINITY,
  quadros: "muitos",
  estado_velho: true,
  idade_estado_s: 2.5,
})
ok(parcial !== null, "estado parcial válido parseia (com chaves conhecidas)")
const e = parcial as FpvEstado
ok(e.fpsMedido === null, "fps_medido NaN → null (nunca NaN no DOM)", `fpsMedido=${e.fpsMedido}`)
ok(e.bitrateMbps === null, "bitrate Infinity → null", `bitrate=${e.bitrateMbps}`)
ok(e.quadros === null, "quadros string → null", `quadros=${e.quadros}`)
ok(e.saida !== null && e.saida[0] === 1920 && e.saida[1] === 1080, "par [1920,1080] parseado")
ok(e.fpsNominal === 50, "fps nominal 50 parseado")
ok(e.estadoVelho === true, "estado_velho: true → true (frescura)", `estadoVelho=${e.estadoVelho}`)
ok(lerFpv({ ligada: true, modo: "1080p50", estado_velho: 1 })?.estadoVelho === null,
   "estado_velho não-booleano → null (parser estrito, como o resto do site)")
ok(e.idadeEstadoS === 2.5, "idade_estado_s parseada")

const lixoCampos = lerFpv({ ligada: true, modo: "720p100", saida: [Number.NaN, 720], sensor: [1536] })
ok(lixoCampos !== null && lixoCampos.saida === null && lixoCampos.sensor === null,
   "par/quadra incompletos ou não finitos → null (nada é adivinhado)")

// --------------------------------------------------------------- 3) modos emulados do backend
const ids = MODOS_FPV.map((m) => m.id)
const esperados = ["1080p50", "720p100", "480p120", "2304x1296p56", "1536x864p120", "4608x2592p14"]
ok(JSON.stringify([...ids].sort()) === JSON.stringify([...esperados].sort()),
   "MODOS_FPV = os 6 modos EMULADOS do lab/camera_rpi", ids.join(","))
ok(!ids.includes("2304x1296p30hdr" as never), "o modo HDR NÃO aparece (existe no hardware, não emulado)")
ok(MODOS_FPV.every((m) => m.rotulo.length > 0), "todos os modos têm rótulo legível")

// ------------------------------------------------------------- 4) rótulos do custo por etapa
ok(rotuloEtapaCustoFpv("codificacao_jpeg").toLowerCase().includes("jpeg"),
   "rótulo da etapa de codificação menciona JPEG")
ok(rotuloEtapaCustoFpv("etapa_inventada") === "etapa_inventada",
   "etapa desconhecida mostra-se tal e qual (nunca se esconde)")

console.log(`\nfpv-parser: ${n - falhas}/${n} verificações`)
if (falhas > 0) {
  console.log("FALHOU")
  process.exit(1)
}
console.log("ok")
