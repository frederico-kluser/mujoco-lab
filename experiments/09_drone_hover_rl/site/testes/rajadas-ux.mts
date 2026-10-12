/**
 * Teste da UX do painel de RAJADAS DE VENTO («Vento dinâmico») — remediações dos achados 1–5 de
 * `pesquisas/ux-rajadas-avaliacao.json`. Corre sem dependências: `node testes/rajadas-ux.mts`
 * (Node ≥ 22.6 com type-stripping).
 *
 * O que se prova:
 *  1. LÉXICO ÚNICO (achado 3): os rótulos são EXATAMENTE os esperados (auditados à letra) e os do
 *     segmented toggle são os MESMOS objetos (`ROTULOS_MODO_ESTADO.*`) que a faixa de estado usa —
 *     verificado por contrato de FONTES (o toggle e a faixa referenciam a mesma constante);
 *  2. MODO → ESTADO (achado 1): os 3 estados exaustivos (`parado`/`a_correr`/`rajada`) a partir do que a
 *     física faz (`modoTelemetria` + intensidade), com os limiares certos (0,05 m/s é exclusivo);
 *  3. INTENSIDADE da rajada (achado 1): `intensidadeRajada(total, base) = |total − base|`;
 *  4. SALVAGUARDA/estilo (achados 2+4): a faixa é sticky com `data-estado`/`data-modo`, o painel tem
 *     `data-ativo`, há progresso dos instantâneos (`dinamico-progresso`) e as frases divergentes do
 *     achado 3 ("inativo", "sem dinâmica", "rajadas aleatórias", "FRENTE EM VIGOR", "modo em vigor")
 *     já não existem no painel.
 *
 * A região pura de `controlos.tsx` (marcadores `// <rajadas-ux:puro>` … `// </rajadas-ux:puro>`) é
 * extraída para um `.mts` temporário e IMPORTADA tal e qual — o teste corre o código REAL, não uma
 * reimplementação (e falha alto se os marcadores desaparecerem).
 */

import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { pathToFileURL } from "node:url"

const FONTE = new URL("../src/components/sim/controlos.tsx", import.meta.url)
const fonte = readFileSync(FONTE, "utf8")

let n = 0
let falhas = 0

function ok(cond: boolean, nome: string, detalhe = ""): void {
  n += 1
  if (!cond) falhas += 1
  console.log(`        [${cond ? "OK  " : "FALHA"}] ${nome}${detalhe ? ` — ${detalhe}` : ""}`)
}

// ---------------------------------------------------------- carrega a região PURA (código real)
const INICIO = "// <rajadas-ux:puro>"
const FIM = "// </rajadas-ux:puro>"
const i0 = fonte.indexOf(INICIO)
const i1 = fonte.indexOf(FIM)
ok(i0 >= 0 && i1 > i0, "a região pura está marcada em controlos.tsx (extrator não pode ficar cego)")
const puro = fonte.slice(i0 + INICIO.length, i1)
ok(!puro.includes("<"), "a região pura não tem JSX (Node importa-a sem transformação)")

const dir = mkdtempSync(join(tmpdir(), "rajadas-ux-"))
const caminho = join(dir, "puro.mts")
writeFileSync(caminho, puro, "utf8")
const m = (await import(pathToFileURL(caminho).href)) as {
  ROTULOS_MODO_ESTADO: Record<string, string>
  LIMIAR_RAJADA_M_S: number
  intensidadeRajada: (total: number, base: number) => number
  estadoFaixa: (e: {
    modoContinuo: string
    modoTelemetria: string
    intensidade: number
  }) => { estado: string; modo: string; intensidade: number }
}
const { ROTULOS_MODO_ESTADO: L, estadoFaixa, intensidadeRajada } = m

// --------------------------------------------------------------- 1) léxico único (achado 3)
ok(L.parado === "PARADO", "rótulo PARADO exato", L.parado)
ok(L.rajadas === "RAJADAS", "rótulo RAJADAS exato (o do toggle)", L.rajadas)
ok(L.aleatoria === "ALEATÓRIA", "rótulo ALEATÓRIA exato (o do toggle)", L.aleatoria)
ok(L.dryden === "DRYDEN", "rótulo DRYDEN exato (o do toggle)", L.dryden)
ok(L.rajada_agora === "RAJADA AGORA", "rótulo RAJADA AGORA exato", L.rajada_agora)
ok(L.frente === "FRENTE AGORA", "rótulo FRENTE AGORA exato", L.frente)

// Contrato de fontes: as opções do toggle são as MESMAS constantes que a faixa de estado usa
for (const [valor, chave] of [
  ["nenhum", "parado"],
  ["rajadas", "rajadas"],
  ["aleatoria", "aleatoria"],
  ["dryden", "dryden"],
] as const) {
  const re = new RegExp(
    `<SegmentedToggleOption value="${valor}"[^>]*>\\s*\\{ROTULOS_MODO_ESTADO\\.${chave}\\}\\s*</SegmentedToggleOption>`
  )
  ok(re.test(fonte), `toggle ${valor} usa ROTULOS_MODO_ESTADO.${chave} (mesmo rótulo da faixa)`)
}
ok(fonte.includes("data-testid=\"dinamico-faixa-estado\""),
   "a faixa de estado existe no painel (testid dinamico-faixa-estado)")
ok(fonte.includes("data-estado={faixa.estado}") && fonte.includes("data-modo={faixa.modo}"),
   "a faixa expõe data-estado e data-modo (estados testáveis)")
ok(fonte.includes("`A CORRER — ${faixa.modo}`") && fonte.includes("RAJADA EM CURSO +"),
   "os textos da faixa usam o léxico (A CORRER — MODO · RAJADA EM CURSO +X,X m/s)")

// ----------------------------------------------- 2) modo → estado (achado 1: parado/a_correr/rajada)
const casos: Array<
  [string, { modoContinuo: string; modoTelemetria: string; intensidade: number }, string, string]
> = [
  ["nada a acontecer", { modoContinuo: "nenhum", modoTelemetria: "nenhum", intensidade: 0 }, "parado", "PARADO"],
  ["rajadas armadas (silencioso)", { modoContinuo: "rajadas", modoTelemetria: "rajadas", intensidade: 0 }, "a_correr", "RAJADAS"],
  ["aleatória armada (silenciosa)", { modoContinuo: "aleatoria", modoTelemetria: "aleatoria", intensidade: 0 }, "a_correr", "ALEATÓRIA"],
  ["dryden armado (sem desvio)", { modoContinuo: "dryden", modoTelemetria: "dryden", intensidade: 0 }, "a_correr", "DRYDEN"],
  ["instantâneo na física", { modoContinuo: "nenhum", modoTelemetria: "rajada_agora", intensidade: 1.2 }, "rajada", "RAJADA AGORA"],
  ["rajada do modo aleatório a bater", { modoContinuo: "aleatoria", modoTelemetria: "aleatoria", intensidade: 0.8 }, "rajada", "ALEATÓRIA"],
  ["rajada do modo rajadas a bater", { modoContinuo: "rajadas", modoTelemetria: "rajadas", intensidade: 0.3 }, "rajada", "RAJADAS"],
  ["desvio sem modo (rajada perdida?)", { modoContinuo: "nenhum", modoTelemetria: "nenhum", intensidade: 0.3 }, "rajada", "RAJADA AGORA"],
  ["frente (degrau mantido)", { modoContinuo: "nenhum", modoTelemetria: "frente", intensidade: 0 }, "a_correr", "FRENTE AGORA"],
]
for (const [nome, entrada, estado, modo] of casos) {
  const r = estadoFaixa(entrada)
  ok(r.estado === estado && r.modo === modo,
     `mapeamento: ${nome} → ${estado}/${modo}`,
     `obtido ${r.estado}/${r.modo}`)
}
const limiarBaixo = estadoFaixa({ modoContinuo: "rajadas", modoTelemetria: "rajadas", intensidade: 0.05 })
const limiarAlto = estadoFaixa({ modoContinuo: "rajadas", modoTelemetria: "rajadas", intensidade: 0.051 })
ok(limiarBaixo.estado === "a_correr" && limiarAlto.estado === "rajada",
   "limiar 0,05 m/s é EXCLUSIVO (0,05 = armado; 0,051 = rajada)",
   `${limiarBaixo.estado} vs ${limiarAlto.estado} · LIMIAR=${m.LIMIAR_RAJADA_M_S}`)
ok(estadoFaixa({ modoContinuo: "nenhum", modoTelemetria: "nenhum", intensidade: 0 }).intensidade === 0,
   "a intensidade atravessa o mapeamento (nada é recalculado)")

// ------------------------------------------------- 3) intensidade da rajada (achado 1)
ok(Math.abs(intensidadeRajada(1.2, 1.0) - 0.2) < 1e-12, "intensidadeRajada(1,2; 1,0) = 0,2 m/s")
ok(Math.abs(intensidadeRajada(0.4, 1.0) - 0.6) < 1e-12, "intensidadeRajada(0,4; 1,0) = 0,6 (módulo, sem sinal)")
ok(intensidadeRajada(2.0, 2.0) === 0, "intensidadeRajada(2,0; 2,0) = 0 (sem rajada visível)")
ok(Math.abs(intensidadeRajada(1.0, 1.7) - intensidadeRajada(1.7, 1.0)) < 1e-12,
   "intensidadeRajada é simétrica |total − base|")

// ------------------------------- 4) salvaguarda/estilo (achados 2+4) + auditoria de strings (3)
ok(fonte.includes("sticky top-0"), "a faixa é STICKY no topo do painel (achado 4: anti-esquecimento)")
ok(/data-ativo=\{ativo \? "sim" : "nao"\}/.test(fonte), "o painel expõe data-ativo (sim/nao)")
ok(fonte.includes("data-testid=\"dinamico-progresso\""), "há bloco de progresso dos instantâneos")
ok(fonte.includes("duração comandada"), "o progresso rotula a duração como COMANDADA (não finge medição)")
ok(fonte.includes("data-testid=\"dinamico-params-resumo\""), "os params têm resumo legível (achado 5)")
ok(fonte.includes("aplica-se sem reiniciar o episódio"), "a nota única do achado 5 existe")
const divergentes = ["inativo", "sem dinâmica", "rajadas aleatórias", "FRENTE EM VIGOR", "modo em vigor"]
for (const frase of divergentes) {
  ok(!fonte.includes(frase), `auditoria de strings: «${frase}» já NÃO aparece no painel`)
}
ok(/ventoAgora\.total === null\s*\? "RAJADA EM CURSO"/.test(fonte),
   "sem vento real na telemetria a rajada mostra «RAJADA EM CURSO» SEM número (nada é inventado)")
ok(/por passo · rajadas de /.test(fonte) && /passos\) até /.test(fonte),
   "chunking: «p … por passo · rajadas de X s (N passos) até Y m/s» (unidades naturais)")

rmSync(dir, { recursive: true, force: true })
console.log(`\nrajadas-ux: ${n - falhas}/${n} verificações`)
if (falhas > 0) {
  console.log("FALHOU")
  process.exit(1)
}
console.log("ok")
