/**
 * Teste do BLOCO «Multi-IA» do site: o parser `lerMultiIa` (defensivo — nunca inventa uma IA) e os
 * contratos que o painel RPi 5 mostra. Corre sem dependências: `node testes/multi-ia.mts` (Node ≥ 22.6
 * com type-stripping).
 *
 * O que se prova (é a fronteira site↔API do mecanismo multi-IA):
 *  · `lerMultiIa` devolve `null` para AUSÊNCIA e para LIXO (`null`, `{}`, `{foo: 1}`, arrays, strings)
 *    — um payload sem nenhuma chave conhecida nunca vira um «mecanismo existe mas tudo null»;
 *  · números não finitos e tipos errados viram `null` campo a campo (nada de `NaN` no DOM);
 *  · um estado real (o do `multi_ia.CascataMultiIA.estado()`, depois do `_custo_multi_ia` do
 *    `sim_site.py`) parseia campo a campo — IAs com nome/papel/taxa/p50/p99/estado, semáforo, fonte
 *    do `v_ref` e a nota do FC («não é IA»);
 *  · o caso de UMA SÓ IA (sem a IA-2 «seguimento») parseia tal e qual — o painel mostra-o honestamente;
 *  · `ias` que não seja lista vira `[]` (nunca se inventa uma IA) e o `fc` ausente vira `null`.
 */

import { lerMultiIa, type MultiIaCusto } from "../src/lib/sim.ts"

let n = 0
let falhas = 0

function ok(cond: boolean, nome: string, detalhe = ""): void {
  n += 1
  if (!cond) falhas += 1
  console.log(`        [${cond ? "OK  " : "FALHA"}] ${nome}${detalhe ? ` — ${detalhe}` : ""}`)
}

// ------------------------------------------------------------------ §1 ausência e lixo → null
ok(lerMultiIa(null) === null, "null → null")
ok(lerMultiIa(undefined) === null, "undefined → null")
ok(lerMultiIa({}) === null, "{} (sem chave conhecida) → null — nunca se inventa um mecanismo")
ok(lerMultiIa({ foo: 1 }) === null, "{foo: 1} (chave desconhecida) → null")
ok(lerMultiIa([1, 2, 3]) === null, "array → null")
ok(lerMultiIa("multi") === null, "string → null")
ok(lerMultiIa(42) === null, "número → null")

// ------------------------------------------------- §2 tipos errados/números não finitos → null
const sujo = lerMultiIa({
  ias: "não é lista",
  semaforo: 7,
  p50_us: Number.NaN,
  p99_us: Number.POSITIVE_INFINITY,
  periodo_us: "vinte",
  fc: "não é objeto",
})
ok(sujo !== null, "payload com chave conhecida mas campos podres: parseia (sem rebentar)")
ok(Array.isArray(sujo?.ias) && sujo?.ias.length === 0, "`ias` que não seja lista → [] (nunca se inventa uma IA)")
ok(sujo?.p50Us === null && sujo?.p99Us === null, "p50/p99 não finitos → null")
ok(sujo?.semaforo === null && sujo?.periodoUs === null, "semaforo errado e periodo não numérico → null")
ok(sujo?.fc === null, "`fc` que não seja objeto → null")

// -------------------------------------------------- §3 um estado real da cascata (duas IAs)
const real = {
  ias: [
    {
      nome: "voo", papel: "v_ref → ação (50 Hz)", taxa_hz: 50, ativo: true, estado: "a_correr",
      n_inferencias: 1234, latencia: { p50_us: 412.5, p99_us: 690.2, max_us: 900.0, n: 1234 },
      ultima_obs: [0.1, 0.2], ultima_acao: [0.0, 0.0, 0.1, 0.0],
    },
    {
      nome: "seguimento", papel: "ponto na imagem → v_ref (25 Hz)", taxa_hz: 25, ativo: true,
      estado: "a_correr", n_inferencias: 617, latencia: { p50_us: 180.0, p99_us: 260.0, max_us: 300.0, n: 617 },
      ultima_obs: null, ultima_acao: null,
    },
  ],
  v_ref_fonte: "seguimento",
  aviso: null,
  fc: { papel: "estabilidade (PID de taxa)", taxa_hz: 500, ia: false, nota: "FC H7 determinístico" },
  latencia_total_us: { p50_us: 592.5, p99_us: 950.2 },
  periodo_us: 20000,
  semaforo: "OK",
  p50_us: 592.5, p99_us: 950.2, fracao_p99: 0.0475, pct_p99: 4.75,
  nota: "soma das latências das IAs vs o período de 20 ms",
}
const dois: MultiIaCusto | null = lerMultiIa(real)
ok(dois !== null, "estado real (2 IAs) parseia")
ok(dois?.ias.length === 2, "as 2 IAs vêm na lista", `n=${dois?.ias.length}`)
ok(dois?.ias[0]?.nome === "voo" && dois?.ias[0]?.taxaHz === 50, "IA-1: nome e taxa (50 Hz)")
ok(dois?.ias[0]?.p50Us === 412.5 && dois?.ias[0]?.p99Us === 690.2, "IA-1: latências p50/p99 do bloco `latencia`")
ok(dois?.ias[1]?.nome === "seguimento" && dois?.ias[1]?.taxaHz === 25, "IA-2: nome e taxa (25 Hz)")
ok(dois?.semaforo === "OK" && dois?.pctP99 === 4.75, "semáforo e % do período do orçamento de 50 Hz")
ok(dois?.vRefFonte === "seguimento", "fonte do v_ref = seguimento (o tracker manda)")
ok(dois?.fc?.ia === false && (dois?.fc?.nota ?? "").includes("determinístico"),
   "o FC vem marcado como NÃO-IA (a estabilidade não é das redes)")

// --------------------------------------------- §4 o caso honesto: SÓ a IA-1 (sem seguimento)
const soUma = lerMultiIa({
  ias: [{ nome: "voo", papel: "v_ref → ação (50 Hz)", taxa_hz: 50, ativo: true, estado: "a_correr",
          n_inferencias: 10, latencia: { p50_us: 400, p99_us: 500 } }],
  v_ref_fonte: "wasdqe", semaforo: "OK", p50_us: 400, p99_us: 500, periodo_us: 20000,
  fc: { papel: "estabilidade (PID de taxa)", taxa_hz: 500, ia: false, nota: "não é IA" },
})
ok(soUma?.ias.length === 1, "SÓ a IA-1 parseia tal e qual (o painel diz que só há uma)")
ok(soUma?.vRefFonte === "wasdqe", "sem tracker: a fonte do v_ref é o WASDQE do site")

// ------------------------------------------------------- §5 estados e avisos nunca se perdem
const comAviso = lerMultiIa({
  ias: [], semaforo: "ERRO", p99_us: 17000, periodo_us: 20000, pct_p99: 85.0,
  aviso: "IA-1 «voo» sem inferência — ação NEUTRA (pairagem + taxas zero; o FC mantém o drone)",
  v_ref_fonte: "wasdqe",
})
ok(comAviso?.semaforo === "ERRO" && (comAviso?.aviso ?? "").includes("NEUTRA"),
   "o aviso de fail-safe (ação neutra + FC mantém) chega ao site sem se perder")
const estados = new Set((dois?.ias ?? []).map((ia) => ia.estado))
ok(estados.has("a_correr"), "estados das IAs vêm por extenso (o painel mostra-os)")

console.log(`\n[site] ${n - falhas}/${n} verificações`)
if (falhas > 0) {
  console.log("[site] FALHAS:", falhas)
  process.exit(1)
}