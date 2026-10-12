/**
 * Teste do SELETOR DE CONTROLADOR (contrato r12): o parser `lerControlador` (defensivo — nunca se
 * inventa uma troca), a rotação rumo↔mundo («W muda de eixo»), o corpo do `POST /api/controlador`,
 * os blocos `voo` com yaw/olhar, as constantes das teclas Z/C/X/V, as linhas do painel «Quem faz o
 * quê», os dois alvos de bordo e a PRESENÇA dos painéis novos no front. Corre sem dependências:
 * `node testes/controlador.mts` (Node ≥ 22.6 com type-stripping).
 *
 * O que se prova (é a fronteira site↔API do contrato r12):
 *  · `lerControlador` devolve `null` para AUSÊNCIA e para LIXO; tipos errados viram defaults honestos
 *    (nunca `NaN` no DOM); um bloco real parseia campo a campo — incluindo `trocando`/`erro` com o
 *    `motivo` (os estados honestos da troca) e o `olhar` (alvo na imagem);
 *  · `vRefRumoParaMundo` roda o WASDQE para o mundo: com rumo π/2 o avanço W vira +y (e a inversa
 *    `vRefMundoParaRumo` faz ida-e-volta exata) — é o «W muda de eixo» do modo clássico;
 *  · `lerBlocoVoo` aceita os campos novos (`yaw_alvo: null` é VALOR, não ausência) e um bloco r11
 *    continua válido;
 *  · `corpoControlador` manda SÓ `{modo}` (o `seq` é do servidor);
 *  · `linhasQuemFazOQue`: 4 linhas; o controlador muda com o modo (IA-1 medida × cascata C++
 *    estimada) e o FC/estimador são não-IA nos DOIS; `ALVOS_BORDO` tem os DOIS alvos com os números
 *    medidos do firmware (1438/3016 instruções, 2940 B de RAM, 21 ms DCMI vs 116 ms Pi);
 *  · os painéis novos EXISTEM no front (data-testid estáveis nos componentes certos).
 */

import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

import {
  ALVOS_BORDO,
  ROTULOS_TECLAS_YAW,
  TECLAS_YAW,
  YAW_TAXA_MAX,
  YAW_TAXA_TECLA,
  alvoDeslocamentoPx,
  corpoControlador,
  grausRumo,
  lerControlador,
  lerOlhar,
  linhasQuemFazOQue,
  vRefMundoParaRumo,
  vRefRumoParaMundo,
  type ControladorEstado,
} from "../src/lib/controlador.ts"
import { lerBlocoVoo, TECLAS_VOO_ZERADAS } from "../src/lib/voo.ts"

let n = 0
let falhas = 0

function ok(cond: boolean, nome: string, detalhe = ""): void {
  n += 1
  if (!cond) falhas += 1
  console.log(`        [${cond ? "OK  " : "FALHA"}] ${nome}${detalhe ? ` — ${detalhe}` : ""}`)
}

function aprox(a: number, b: number, eps = 1e-9): boolean {
  return Math.abs(a - b) <= eps
}

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..")

// ------------------------------------------------------------------ §1 ausência e lixo → null
ok(lerControlador(null) === null, "null → null")
ok(lerControlador(undefined) === null, "undefined → null")
ok(lerControlador({}) === null, "{} (sem chave conhecida) → null — nunca se inventa um controlador")
ok(lerControlador({ foo: 1 }) === null, "{foo: 1} → null")
ok(lerControlador([1, 2]) === null, "array → null")
ok(lerControlador("classico") === null, "string → null")

// ------------------------------------------------------------------ §2 tipos errados → defaults honestos
const sujo = lerControlador({ modo: 7, yaw_taxa: "nada", yaw_alvo: "agora", segui_alvo: "sim", rumo: NaN })
ok(
  sujo !== null && sujo.modo === "rl" && sujo.yaw_taxa === 0 && sujo.yaw_alvo === null &&
    sujo.segui_alvo === false && sujo.rumo === null && sujo.estado === "desconhecido",
  "tipos errados → defaults honestos (modo rl, yaw 0/null, sem NaN)",
  JSON.stringify(sujo)
)

// ------------------------------------------------------------------ §3 bloco real, campo a campo
const real = lerControlador({
  modo: "classico",
  pedido: "classico",
  estado: "pronto",
  motivo: null,
  fonte: "cascata clássica C++ (núcleo do firmware, via ctypes)",
  yaw_taxa: 0.5,
  yaw_alvo: 1.25,
  segui_alvo: true,
  v_ref_fonte: "olhar (IBVS)",
  rumo: 0.75,
  olhar: { valido: true, u_px: 160, v_px: 120, raio_px: 6, erro_px: [0.5, -1.5], estado: 0 },
})
ok(
  real !== null && real.modo === "classico" && real.pedido === "classico" && real.estado === "pronto" &&
    real.yaw_taxa === 0.5 && aprox(real.yaw_alvo ?? 99, 1.25) && real.segui_alvo === true &&
    real.v_ref_fonte === "olhar (IBVS)" && aprox(real.rumo ?? 99, 0.75),
  "bloco real parseia campo a campo (modo/pedido/yaw/rumo/v_ref_fonte)",
  JSON.stringify({ modo: real?.modo, yaw: real?.yaw_taxa })
)
ok(
  real?.olhar !== null && real?.olhar !== undefined && real.olhar.valido && real.olhar.estado === 0 &&
    alvoDeslocamentoPx(real.olhar) !== null && aprox(alvoDeslocamentoPx(real.olhar)!, Math.hypot(0.5, 1.5)),
  "olhar parseia (deteção + erro_px) e `alvoDeslocamentoPx` é a distância ao centro"
)

// ------------------------------------------------------------------ §4 estados honestos da troca
const troca = lerControlador({ modo: "rl", pedido: "classico", estado: "trocando", motivo: "troca de controlador: episódio reiniciado (calibração do giroscópio no chão)" })
ok(
  troca !== null && troca.estado === "trocando" && troca.pedido === "classico" && troca.modo === "rl" &&
    (troca.motivo ?? "").includes("episódio reiniciado"),
  "`trocando` parseia com o motivo (o painel mostra-o — a troca nunca é silenciosa)"
)
const recusa = lerControlador({ modo: "rl", pedido: "classico", estado: "erro", motivo: "requer a planta real" })
ok(
  recusa !== null && recusa.estado === "erro" && recusa.motivo === "requer a planta real",
  "`erro` + motivo propaga-se (pedido recusado nunca vira troca fingida)"
)
ok(lerOlhar(null) === null && lerOlhar({}) === null && lerOlhar("x") === null,
  "lerOlhar: ausência/lixo → null (sem câMARA não há alvo)")

// ------------------------------------------------------------------ §5 rotação rumo ↔ mundo
const w90 = vRefRumoParaMundo([1, 0, 0], Math.PI / 2)
ok(aprox(w90[0], 0, 1e-12) && aprox(w90[1], 1) && aprox(w90[2], 0),
  "com yaw a 90°, W (avanço +1 no rumo) MUDA DE EIXO → +y no mundo", JSON.stringify(w90))
const w0 = vRefRumoParaMundo([1, 0, 0], 0)
ok(aprox(w0[0], 1) && aprox(w0[1], 0), "rumo 0 → identidade (W é +x no mundo)")
const l90 = vRefRumoParaMundo([0, 1, 0.7], Math.PI / 2)
ok(aprox(l90[0], -1, 1e-12) && aprox(l90[1], 0, 1e-12) && aprox(l90[2], 0.7),
  "lateral A a 90° vira −x (o vertical nunca muda)", JSON.stringify(l90))
const volta = vRefMundoParaRumo(vRefRumoParaMundo([0.6, -0.2, 0.3], 1.1), 1.1)
ok(aprox(volta[0], 0.6) && aprox(volta[1], -0.2) && aprox(volta[2], 0.3),
  "ida-e-volta rumo→mundo→rumo é exata")

// ------------------------------------------------------------------ §6 corpo do POST /api/controlador
ok(JSON.stringify(corpoControlador("classico")) === '{"modo":"classico"}' &&
  JSON.stringify(corpoControlador("rl")) === '{"modo":"rl"}',
  "corpoControlador manda SÓ {modo} (o `seq` é do servidor)")

// ------------------------------------------------------------------ §7 bloco voo r12 (yaw/olhar)
const bloco = lerBlocoVoo({ ativo: true, teclas: { w: true }, yaw_taxa: -0.5, yaw_alvo: null, segui_alvo: true, seq: 3 })
ok(
  bloco !== null && bloco.yaw_taxa === -0.5 && bloco.yaw_alvo === null && bloco.segui_alvo === true,
  "lerBlocoVoo parseia os campos r12 (`yaw_alvo: null` é VALOR, não ausência)"
)
const r11 = lerBlocoVoo({ ativo: true, teclas: { w: true }, seq: 1 })
ok(
  r11 !== null && r11.yaw_taxa === 0 && r11.yaw_alvo === null && r11.segui_alvo === false &&
  JSON.stringify(r11.teclas) !== JSON.stringify(TECLAS_VOO_ZERADAS),
  "um bloco r11 continua válido (defaults 0/null/false nas chaves novas)"
)

// ------------------------------------------------------------------ §8 constantes das teclas de yaw
ok(TECLAS_YAW.join("") === "zcxv" && TECLAS_YAW.length === 4,
  "TECLAS_YAW = [z, c, x, v] (Z/C rodam, X fixa o rumo, V olhar)")
ok(aprox(YAW_TAXA_TECLA, 0.5) && aprox(YAW_TAXA_MAX, 2.0),
  "teclas mandam ±0,5 rad/s dentro do teto ±2 rad/s do contrato (as do backend)")
ok(TECLAS_YAW.every((t) => ROTULOS_TECLAS_YAW[t].direcao.length > 0 && ROTULOS_TECLAS_YAW[t].completo.includes(t.toUpperCase())),
  "cada tecla de yaw tem rótulo com a ação")

// ------------------------------------------------------------------ §9 «quem faz o quê» por modo
const rl = linhasQuemFazOQue(lerControlador({ modo: "rl", estado: "pronto", fonte: "política RL" }), {
  ias: [{ nome: "voo", p50Us: 7, p99Us: 9 }, { nome: "seguimento", p50Us: 11, p99Us: 14 }],
  semaforo: "OK",
})
ok(rl.length === 4 && rl.map((l) => l.id).join(",") === "fc,controlador,percecao,estimador",
  "4 linhas na ordem FC · controlador · perceção · estimador")
ok(rl[0].quem.includes("não-IA") && rl[3].quem.includes("não-IA"),
  "FC e estimador são NÃO-IA nos dois modos")
ok(rl[1].quem.includes("IA-1") && rl[1].origem === "medida" && rl[2].quem.includes("IA-2"),
  "modo RL: controlador = IA-1 e perceção = IA-2 (latências MEDIDAS)")
const cl = linhasQuemFazOQue(lerControlador({ modo: "classico", estado: "pronto", fonte: "cascata" }), null)
ok(cl[1].quem.includes("C++") && cl[1].origem === "estimado" && cl[2].quem.includes("IBVS") &&
  cl[2].origem === "estimado",
  "modo clássico: cascata C++ e detetor+IBVS, com os números ditos ESTIMADOS")

// ------------------------------------------------------------------ §10 alvos de bordo (os DOIS)
ok(ALVOS_BORDO.length === 2 && ALVOS_BORDO.map((a) => a.id).join(",") === "arduino,rpi5",
  "dois alvos de bordo: Arduino Portenta H7 + Vision Shield e RPi 5 + FC H7")
const ard = ALVOS_BORDO[0]
ok(ard.build === "endurance_15pol_arduino" && ard.passos[0].instrucoes === 1438 &&
  ard.passos[1].instrucoes === 3016 && ard.ram_bytes === 2940 && ard.text_bytes === 24582,
  "Arduino: 1438 instr/passo de 500 Hz = 3016 com tick · text 24 582 B · RAM 2 940 B (medidos)")
ok(ard.passos[0].us === 4.3 && ard.passos[1].us === 10.1 && ard.orcamento.periodo_ms === 2,
  "Arduino: 4,3/10,1 µs @480 MHz vs o orçamento de 2 ms por passo")
ok(ard.camera.latencia_ms === 21 && ALVOS_BORDO[1].camera.latencia_ms === 116,
  "latência da câmara: 21 ms (DCMI) no Arduino vs 116 ms (CSI-2) no Pi")

// ------------------------------------------------------------------ §11 painéis presentes no front
// `[testid, ficheiro, padrao]`: o testid literal OU o padrão dinâmico do componente (ex. os keycaps
// são `data-testid={`tecla-${tecla}`}` — o que importa é a FAMÍLIA existir no ficheiro certo; a
// semântica de cada letra já foi provada na §8).
const testeids: [string, string, string][] = [
  ["seletor-controlador", "controlador.tsx", 'data-testid="seletor-controlador"'],
  ["controlador-estado", "controlador.tsx", 'data-testid="controlador-estado"'],
  ["controlador-motivo", "controlador.tsx", 'data-testid="controlador-motivo"'],
  ["controlador-modo-rl", "controlador.tsx", 'data-testid="controlador-modo-rl"'],
  ["controlador-modo-classico", "controlador.tsx", 'data-testid="controlador-modo-classico"'],
  ["controlador-fonte", "controlador.tsx", 'data-testid="controlador-fonte"'],
  ["tecla-z", "controlo-voo.tsx", "data-testid={`tecla-${tecla}`}"],
  ["tecla-c", "controlo-voo.tsx", "data-testid={`tecla-${tecla}`}"],
  ["tecla-x", "controlo-voo.tsx", "data-testid={`tecla-${tecla}`}"],
  ["tecla-v", "controlo-voo.tsx", "data-testid={`tecla-${tecla}`}"],
  ["voo-rumo", "controlo-voo.tsx", 'data-testid="voo-rumo"'],
  ["voo-rumo-avanco", "controlo-voo.tsx", 'data-testid="voo-rumo-avanco"'],
  ["quem-faz-o-que", "quem-faz-o-que.tsx", 'data-testid="quem-faz-o-que"'],
  ["quem-faz-o-que-fc", "quem-faz-o-que.tsx", "data-testid={`quem-faz-o-que-${linha.id}`}"],
  ["quem-faz-o-que-controlador", "quem-faz-o-que.tsx", "data-testid={`quem-faz-o-que-${linha.id}`}"],
  ["quem-faz-o-que-percecao", "quem-faz-o-que.tsx", "data-testid={`quem-faz-o-que-${linha.id}`}"],
  ["quem-faz-o-que-estimador", "quem-faz-o-que.tsx", "data-testid={`quem-faz-o-que-${linha.id}`}"],
  ["bordo-alvos", "rpi5.tsx", 'data-testid="bordo-alvos"'],
  ["bordo-alvo-rpi5", "rpi5.tsx", "data-testid={`bordo-alvo-${alvo.id}`}"],
  ["bordo-alvo-arduino", "rpi5.tsx", "data-testid={`bordo-alvo-${alvo.id}`}"],
]
const fontes = new Map<string, string>()
for (const [, ficheiro] of testeids) {
  if (!fontes.has(ficheiro)) {
    fontes.set(ficheiro, readFileSync(join(RAIZ, "src", "components", "sim", ficheiro), "utf8"))
  }
}
for (const [testid, ficheiro, padrao] of testeids) {
  const texto = fontes.get(ficheiro) ?? ""
  ok(
    texto.includes(`data-testid="${testid}"`) || texto.includes(padrao),
    `data-testid="${testid}" presente em src/components/sim/${ficheiro}`
  )
}

// ------------------------------------------------------------------ §12 leituras de rumo
ok(grausRumo(null) === "—" && grausRumo(Math.PI / 2) === "90.0°",
  "grausRumo: «—» sem rumo e 90,0° a π/2")
ok(alvoDeslocamentoPx(null) === null && alvoDeslocamentoPx(lerOlhar({ valido: false })!) === null,
  "sem deteção não há deslocamento (null — nada se inventa)")

console.log(
  `        controlador: ${n - falhas}/${n} verificações · ` +
    (falhas === 0 ? "TUDO OK" : `${falhas} FALHAS`)
)
if (falhas > 0) process.exit(1)
