/**
 * SELETOR DE CONTROLADOR (contrato r12) + «quem faz o quê» + alvos de bordo — funções PURAS.
 *
 * Nada aqui toca no DOM nem no `fetch`: é a camada testável em node (`testes/controlador.mts`) que
 * normaliza (sem adivinhar) o bloco `controlador` que vem do backend `sim_site.py`/`sim_view.py` e
 * prepara os dados dos painéis «Controlador», «Quem faz o quê» e «Alvos de bordo»:
 *
 *  · `POST /api/controlador` recebe `{"modo": "rl"|"classico"}` (só `modo`; o `seq` é do SERVIDOR);
 *  · o `/api/sim` e o `/api/state` publicam `"controlador"` = `{modo, pedido, estado, motivo, fonte,
 *    yaw_taxa, yaw_alvo, segui_alvo, v_ref_fonte, rumo, olhar}` — `modo` é o EM VIGOR (eco do runner),
 *    `pedido` o que foi pedido e `estado` a honestidade (`pronto` · `trocando` · `erro` + `motivo`);
 *  · `rumo` = ψ desde o armar (rad, frame do estimador de bordo) — é o que a tecla X manda como
 *    `yaw_alvo` e o que o painel mostra como «rumo atual»;
 *  · `olhar` = o alvo na imagem do IBVS (`erro_px` = offset face ao CENTRO da imagem, convenção ÍNDICE
 *    do detetor) — «alvo centrado» quer dizer `erro_px ≈ [0, 0]`.
 *
 * COCKPIT (r13, 2026-10-12): o seletor saiu do site (voa o que ganhou na medição — `POST
 * /api/controlador` continua a existir na API) e o mapa de teclas passou para `lib/cockpit.ts`
 * (`acaoDaTecla`): Z/C/X mantêm-se, mas SEGUIR A BOLA é a tecla **B** e a tecla **V** liga o VENTO.
 * `TECLAS_YAW`/`ROTULOS_TECLAS_YAW` abaixo ficam como o registo do contrato r12 (V = «olhar»).
 *
 * Semântica de yaw (teclas novas do painel de voo): Z = rodar à ESQUERDA (`yaw_taxa` +0,5 rad/s),
 * C = rodar à DIREITA (−0,5), X = FIXAR RUMO (`yaw_alvo` = `rumo` atual), V = SEGUIR/OLHAR (alterna
 * `segui_alvo`). Z/C voltam ao modo taxa (`yaw_alvo: null`). Os campos só VOAM no modo CLÁSSICO (a
 * política RL mantém o rumo fixo — contrato r11): o eco `controlador` mostra-os a zero no modo rl e o
 * painel diz-o.
 */

/** Quem pilota: a política RL (IA-1) ou a cascata clássica C++ do firmware. */
export type ModoControlador = "rl" | "classico"

/** Estado honesto da troca (`controlador.estado`). */
export type EstadoControlador = "pronto" | "trocando" | "erro" | "desconhecido"

/** Alvo na imagem do IBVS (`controlador.olhar`) — `null` quando o «olhar» nunca ligou. */
export interface OlharEstado {
  /** Deteção válida no último frame entregue ao núcleo. */
  valido: boolean
  /** Alvo nos píxeis (convenção ÍNDICE: o centro do píxel (0,0) é (0,0)); `null` sem deteção válida. */
  u_px: number | null
  v_px: number | null
  raio_px: number | null
  /** Offset face ao centro da imagem, em píxeis — «centrado» = `erro_px ≈ [0, 0]`; `null` sem deteção. */
  erro_px: [number, number] | null
  /** Estado do IBVS (0 = A_SEGUIR). */
  estado: number | null
  /** Posição do alvo MOCAP no mundo (m) — é ele que descreve o círculo do «olhar». */
  alvo_mundo: [number, number, number] | null
}

/** Bloco `controlador` (contrato r12) tal como o site o interpreta. */
export interface ControladorEstado {
  /** EM VIGOR (eco do runner). */
  modo: ModoControlador
  /** Último pedido (ficheiro/CLI/POST) — pode estar à frente do `modo` durante uma troca. */
  pedido: ModoControlador
  estado: EstadoControlador
  motivo: string | null
  /** Quem voa, por extenso (ex.: «política RL (PPO, IA-1)»). */
  fonte: string | null
  /** Taxa de guinada aplicada (rad/s; 0 no modo rl — a política mantém o rumo fixo). */
  yaw_taxa: number
  /** Rumo-alvo aplicado (rad desde o armar); `null` = sem alvo. */
  yaw_alvo: number | null
  /** «Olhar» (IBVS) aplicado. */
  segui_alvo: boolean
  /** De onde vem o `v_ref` («wasdqe …» | «olhar (IBVS)» | «seguimento (IA-2)»). */
  v_ref_fonte: string | null
  /** ψ desde o armar (rad) — o que a tecla X fixa; `null` sem estimador (cf2). */
  rumo: number | null
  olhar: OlharEstado | null
}

/** Teto do contrato r12 para `voo.yaw_taxa` (rad/s) — o mesmo do `sim_view.py`/`sim_site.py`. */
export const YAW_TAXA_MAX = 2.0

/** O que as teclas Z/C mandam (rad/s): ±0,5 — suave e fácil de travar. */
export const YAW_TAXA_TECLA = 0.5

/** As 4 teclas de yaw do painel, pela letra minúscula (`evento.key` normalizado). */
export const TECLAS_YAW = ["z", "c", "x", "v"] as const
export type TeclaYaw = (typeof TECLAS_YAW)[number]

/** Rótulo físico de cada tecla de yaw (o keycap mostra a ação, não a letra solta). */
export const ROTULOS_TECLAS_YAW: Record<
  TeclaYaw,
  { direcao: string; completo: string }
> = {
  z: { direcao: "rodar ←", completo: "Z · rodar à esquerda (yaw_taxa +0,5 rad/s)" },
  c: { direcao: "rodar →", completo: "C · rodar à direita (yaw_taxa −0,5 rad/s)" },
  x: { direcao: "fixar rumo", completo: "X · fixar o rumo atual (yaw_alvo = rumo)" },
  v: { direcao: "olhar", completo: "V · seguir o alvo com a câmara (olhar/IBVS)" },
}

// --------------------------------------------------------------------------------- leituras tolerantes

function objetoSimples(bruto: unknown): Record<string, unknown> | null {
  return typeof bruto === "object" && bruto !== null && !Array.isArray(bruto)
    ? (bruto as Record<string, unknown>)
    : null
}

function numeroFinito(bruto: unknown): number | null {
  const v = typeof bruto === "string" ? Number(bruto) : bruto
  return typeof v === "number" && Number.isFinite(v) ? v : null
}

function booleanoTolerante(bruto: unknown): boolean | null {
  if (typeof bruto === "boolean") return bruto
  if (bruto === 0 || bruto === 1) return bruto === 1
  return null
}

function textoOuNull(bruto: unknown): string | null {
  return typeof bruto === "string" && bruto.length > 0 ? bruto : null
}

function modoControlador(bruto: unknown, padrao: ModoControlador): ModoControlador {
  return bruto === "rl" || bruto === "classico" ? bruto : padrao
}

/** `[x,y]` finito, ou `null` (nunca `[0,0]` a fingir de vetor que não veio). */
function lerPar(bruto: unknown): [number, number] | null {
  if (!Array.isArray(bruto) || bruto.length < 2) return null
  const x = numeroFinito(bruto[0])
  const y = numeroFinito(bruto[1])
  return x === null || y === null ? null : [x, y]
}

/** `controlador.olhar` → `OlharEstado`, ou `null` (ausência/lixo = sem olhar — nada se inventa). */
export function lerOlhar(bruto: unknown): OlharEstado | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const valido = booleanoTolerante(o.valido)
  const erro = lerPar(o.erro_px)
  const u = numeroFinito(o.u_px)
  const v = numeroFinito(o.v_px)
  const raio = numeroFinito(o.raio_px)
  const estado = numeroFinito(o.estado)
  const alvo = lerVetor3(o.alvo_mundo)
  const algum =
    valido !== null || erro !== null || u !== null || v !== null || raio !== null || estado !== null ||
    alvo !== null
  if (!algum) return null
  return {
    valido: valido ?? false,
    u_px: u,
    v_px: v,
    raio_px: raio,
    erro_px: erro,
    estado: estado === null ? null : Math.trunc(estado),
    alvo_mundo: alvo,
  }
}

/** `[x,y,z]` finito, ou `null` (nunca `[0,0,0]` a fingir de vetor que não veio). */
function lerVetor3(bruto: unknown): [number, number, number] | null {
  if (!Array.isArray(bruto) || bruto.length < 3) return null
  const x = numeroFinito(bruto[0])
  const y = numeroFinito(bruto[1])
  const z = numeroFinito(bruto[2])
  return x === null || y === null || z === null ? null : [x, y, z]
}

/**
 * Qualquer bloco `controlador` do backend → `ControladorEstado`, ou `null`.
 *
 * `null` quando a entrada NÃO é um objeto ou não tem NADA reconhecível dentro (um backend sem o
 * bloco chega aqui como `null`, honesto); campos em falta dentro de um bloco reconhecível saem com
 * defaults razoáveis (`estado: "desconhecido"`, yaw a zero, `rumo: null`). Nunca lança.
 */
export function lerControlador(bruto: unknown): ControladorEstado | null {
  const o = objetoSimples(bruto)
  if (o === null) return null
  const modo = o.modo
  const pedido = o.pedido
  const estado = o.estado
  const fonte = textoOuNull(o.fonte)
  const yawTaxa = numeroFinito(o.yaw_taxa)
  const yawAlvo = numeroFinito(o.yaw_alvo)
  const segui = booleanoTolerante(o.segui_alvo)
  const vRefFonte = textoOuNull(o.v_ref_fonte)
  const rumo = numeroFinito(o.rumo)
  const motivo = textoOuNull(o.motivo)
  const olhar = lerOlhar(o.olhar)
  const algum =
    modo !== undefined ||
    pedido !== undefined ||
    estado !== undefined ||
    fonte !== null ||
    yawTaxa !== null ||
    yawAlvo !== null ||
    segui !== null ||
    rumo !== null ||
    olhar !== null
  if (!algum) return null
  const estados: EstadoControlador[] = ["pronto", "trocando", "erro"]
  return {
    modo: modoControlador(modo, "rl"),
    pedido: modoControlador(pedido, modoControlador(modo, "rl")),
    estado:
      typeof estado === "string" && (estados as string[]).includes(estado)
        ? (estado as EstadoControlador)
        : "desconhecido",
    motivo,
    fonte,
    yaw_taxa: yawTaxa ?? 0,
    yaw_alvo: yawAlvo,
    segui_alvo: segui ?? false,
    v_ref_fonte: vRefFonte,
    rumo,
    olhar,
  }
}

/** Corpo do `POST /api/controlador` (só `modo` — o `seq` é do servidor, nunca se manda). */
export function corpoControlador(modo: ModoControlador): { modo: ModoControlador } {
  return { modo: modo === "classico" ? "classico" : "rl" }
}

// --------------------------------------------------------------------------------- rumo ↔ mundo

/**
 * `v_ref` no referencial do RUMO → frame MUNDO (rotação `Rz(rumo)`), em m/s.
 *
 * Em modo CLÁSSICO o WASDQE é relativo ao nariz: com `rumo = π/2`, W (avanço, +vx no rumo) é +y no
 * mundo — é o «W muda de eixo» do contrato r12. A inversa é `vRefMundoParaRumo`.
 */
export function vRefRumoParaMundo(
  v: readonly [number, number, number],
  rumo: number
): [number, number, number] {
  const [vx, vy, vz] = v
  const c = Math.cos(rumo)
  const s = Math.sin(rumo)
  return [vx * c - vy * s, vx * s + vy * c, vz]
}

/** Inversa de `vRefRumoParaMundo` (o painel mostra o avanço/lateral no rumo a partir do eco). */
export function vRefMundoParaRumo(
  v: readonly [number, number, number],
  rumo: number
): [number, number, number] {
  const [vx, vy, vz] = v
  const c = Math.cos(-rumo)
  const s = Math.sin(-rumo)
  return [vx * c - vy * s, vx * s + vy * c, vz]
}

/** `123,4°` de um rumo em rad (ou `—` sem rumo na telemetria). */
export function grausRumo(rumo: number | null): string {
  if (rumo === null) return "—"
  const g = ((rumo * 180) / Math.PI) % 360
  return `${(g < 0 ? g + 360 : g).toFixed(1)}°`
}

/** Distância do alvo ao centro da imagem (px), ou `null` sem deteção — «centrado» = perto de 0. */
export function alvoDeslocamentoPx(olhar: OlharEstado | null): number | null {
  if (olhar === null || olhar.erro_px === null) return null
  return Math.hypot(olhar.erro_px[0], olhar.erro_px[1])
}

// --------------------------------------------------------------------------------- «quem faz o quê»

/** Uma linha do painel «Quem faz o quê» (papel · quem · taxa · latência · orçamento). */
export interface LinhaQuemFaz {
  id: "fc" | "controlador" | "percecao" | "estimador"
  papel: string
  quem: string
  taxa: string
  /** Latência medida (µs) quando existe; `null` = sem medição (mostra-se `estimado` ou «—»). */
  latencia_us: number | null
  latencia_texto: string
  /** `medida` · `estimado` · `—` — a origem do número, sempre dita. */
  origem: "medida" | "estimado" | "fixo"
  nota: string
}

/** Custo multi-IA do `/api/state` (só o que o painel precisa — compatível com `lerMultiIa` de `sim.ts`). */
export interface CustoIa {
  ias: {
    nome: string | null
    p50Us: number | null
    p99Us: number | null
    estado?: string | null
  }[]
  semaforo: string | null
}

/**
 * As 4 linhas do painel «Quem faz o quê», dinâmicas por modo: no RL quem comanda é a IA-1 (50 Hz) e a
 * perceção é a IA-2 (25 Hz); no CLÁSSICO é a cascata C++ (50 Hz) e o detetor+IBVS (25–30 Hz) — os
 * números do clássico são ESTIMATIVAS do firmware (llvm-mca/QEMU; ver o README do firmware) e dizem-se
 * `estimado`. O FC (500 Hz) e o estimador de bordo são clássicos nos DOIS modos (não são IA).
 */
export function linhasQuemFazOQue(
  controlador: ControladorEstado | null,
  custo: CustoIa | null
): LinhaQuemFaz[] {
  const classico = controlador?.modo === "classico"
  const ia = (nome: string) => custo?.ias.find((i) => i.nome === nome) ?? null
  const iaVoo = ia("voo")
  const iaSeg = ia("seguimento")
  return [
    {
      id: "fc",
      papel: "FC · estabilidade",
      quem: "FC H7 (não-IA)",
      taxa: "500 Hz",
      latencia_us: 2000,
      latencia_texto: "2,0 ms de orçamento por passo",
      origem: "fixo",
      nota: "laço de taxa + mistura X + airmode — determinístico, nunca é IA",
    },
    {
      id: "controlador",
      papel: "Controlador",
      quem: classico ? "cascata clássica C++ (núcleo do firmware)" : "IA-1 · política RL (PPO)",
      taxa: classico ? "50 Hz (tick da cascata)" : "50 Hz",
      latencia_us: classico ? 10.1 : (iaVoo?.p99Us ?? iaVoo?.p50Us ?? null),
      latencia_texto: classico
        ? "10,1 µs (tick 50 Hz) · 4,3 µs/passo a 500 Hz @480 MHz"
        : iaVoo
          ? `p50 ${iaVoo.p50Us ?? "—"} µs · p99 ${iaVoo.p99Us ?? "—"} µs`
          : "—",
      origem: classico ? "estimado" : iaVoo ? "medida" : "fixo",
      nota: classico
        ? "estimativa estática (llvm-mca/QEMU sobre o objeto cross-compilado; 3016 instr com tick)"
        : "inferência medida no proxy x86 de 1 core A76 (deploy.py)",
    },
    {
      id: "percecao",
      papel: "Perceção",
      quem: classico ? "detetor + IBVS C++ (câMARA mono QVGA)" : "IA-2 · tracker «seguimento»",
      taxa: classico ? "25–30 Hz (taxa da câmara)" : "25 Hz",
      latencia_us: classico ? null : (iaSeg?.p99Us ?? iaSeg?.p50Us ?? null),
      latencia_texto: classico
        ? "≈22 µs/passo de detetor @480 MHz (estimado) · câmara 21 ms DCMI / 116 ms Pi"
        : iaSeg
          ? `p50 ${iaSeg.p50Us ?? "—"} µs · p99 ${iaSeg.p99Us ?? "—"} µs`
          : "sem IA-2 (estado honesto: não há tracker)",
      origem: classico ? "estimado" : iaSeg ? "medida" : "fixo",
      nota: classico
        ? "detetor de runs + momentos + IBVS do núcleo (usa_visao) — só sensores, sem IA"
        : "ponto na imagem → v_ref (a IA-2 pode não existir: o v_ref vem do WASDQE)",
    },
    {
      id: "estimador",
      papel: "Estimador",
      quem: "estimador de bordo clássico (não-IA)",
      taxa: "500 Hz",
      latencia_us: null,
      latencia_texto: "1 amostra (2 ms) como um FC real",
      origem: "fixo",
      nota: classico
        ? "Mahony + observador de altura do núcleo C++ (float32)"
        : "estimador de bordo da planta (sensores com erro)",
    },
  ]
}

// --------------------------------------------------------------------------------- alvos de bordo

/** Um alvo possível do computador de bordo (painel «Alvos de bordo»). */
export interface AlvoBordo {
  id: "rpi5" | "arduino"
  nome: string
  build: string
  cpu: string
  memoria: string
  camera: { tipo: string; latencia_ms: number }
  /** Passos do firmware: instruções/ciclos/µs por passo (MEDIDO no QEMU + estimado com llvm-mca). */
  passos: { rotulo: string; instrucoes: number; ciclos: number; us: number }[]
  text_bytes: number | null
  ram_bytes: number | null
  orcamento: { periodo_ms: number; nota: string }
  origem: string
}

/**
 * Os DOIS alvos possíveis do computador de bordo (o painel mostra os dois lado a lado):
 * RPi 5 + FC H7 (build ATUAL `endurance_15pol_p50b`) e Arduino Portenta H7 + Vision Shield (build
 * `endurance_15pol_arduino` do catálogo). Os números do Arduino são os MEDIDOS no README do firmware
 * (`firmware/README.md`, tabela «Custo por passo») e em `out/nucleo/avaliacao.json` (2 940 B de
 * instância); a latência da câmara vem do `lab/camera_rpi` (Pi CSI-2 116 ms) e do DCMI (≈21 ms).
 */
export const ALVOS_BORDO: AlvoBordo[] = [
  {
    id: "arduino",
    nome: "Arduino Portenta H7 + Vision Shield",
    build: "endurance_15pol_arduino",
    cpu: "STM32H747XI: M7 480 MHz (FPU dupla) + M4 240 MHz",
    memoria: "2 MB flash · 1 MB RAM · 8 MB SDRAM",
    camera: { tipo: "DCMI · HM0360 mono 640×480 (Vision Shield)", latencia_ms: 21 },
    passos: [
      { rotulo: "M7 · passo normal de 500 Hz", instrucoes: 1438, ciclos: 2060, us: 4.3 },
      { rotulo: "M7 · passo com tick da cascata (50 Hz)", instrucoes: 3016, ciclos: 4851, us: 10.1 },
    ],
    text_bytes: 24582,   // nucleo.o -Os; a cadeia LIGADA (com o arranque e rt) = 28 172 B
    ram_bytes: 2940,
    orcamento: {
      periodo_ms: 2,
      nota: "0,21 % do orçamento de 2 ms por passo (0,51 % com tick) — margem ≥ 80×; M4 < 1,3 %",
    },
    origem: "instruções MEDIDAS (traço QEMU) + ciclos ESTIMADOS (llvm-mca); só um DWT numa placa fecha",
  },
  {
    id: "rpi5",
    nome: "RPi 5 + FC H7",
    build: "endurance_15pol_p50b (atual)",
    cpu: "Broadcom BCM2712: 4× Cortex-A76 @2,4 GHz (+ FC H7 dedicado a 500 Hz)",
    memoria: "LPDDR4X-4267, 1–16 GB (variante)",
    camera: { tipo: "CSI-2 · Pi Camera Module 3 Wide (IMX708)", latencia_ms: 116 },
    passos: [
      { rotulo: "IA-1 (PPO) por decisão @50 Hz", instrucoes: 0, ciclos: 0, us: 7.4 },
      { rotulo: "FC H7 · laço de taxa 500 Hz (não-IA)", instrucoes: 0, ciclos: 0, us: 2000 },
    ],
    text_bytes: null,
    ram_bytes: null,
    orcamento: {
      periodo_ms: 20,
      nota: "inferência < 1 % de 20 ms; o gargalo real é o jitter do SO (9,4 ms pior caso no kernel standard)",
    },
    origem: "inferência MEDIDA no proxy x86 de 1 core A76 (p50 6,9 µs · p99 7,4 µs; deploy.py) + specs do Product Brief",
  },
]
