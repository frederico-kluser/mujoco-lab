/**
 * Cliente HTTP do backend `sim_site.py` (mesma origem por omissão).
 *
 * O servidor serve `site/dist/` e a API no mesmo porto, logo os caminhos são relativos. Para testes e
 * para apontar o `dist/` estático a outro porto aceita-se `?api=http://host:porto` ou a variável global
 * `window.__SIM_API_BASE__` — nada disto muda o caminho de produção (por omissão: mesma origem).
 */

import {
  lerHudJson,
  lerVentoSimples,
  type AmostraHud,
  type VentoSimples,
} from "./cockpit.ts"
import {
  lerCamera,
  lerResumo,
  lerSim,
  numero,
  type CameraEstado,
  type CorpoCamera,
  type CorpoFpv,
  type CorpoVento,
  type CorpoVentoDinamico,
  type RespostaSim,
  type ResumoEstado,
} from "./sim"
import {
  lerBlocoVoo,
  TECLAS_VOO,
  TECLAS_VOO_ZERADAS,
  type BlocoVoo,
  type TeclasVoo,
} from "./voo.ts"

declare global {
  interface Window {
    __SIM_API_BASE__?: string
  }
}

export class ErroApi extends Error {
  estado: number | null

  constructor(mensagem: string, estado: number | null = null) {
    super(mensagem)
    this.name = "ErroApi"
    this.estado = estado
  }
}

function baseApi(): string {
  const daQuery = new URLSearchParams(window.location.search).get("api")
  const bruto = daQuery ?? window.__SIM_API_BASE__ ?? ""
  return bruto.replace(/\/+$/, "")
}

/**
 * URL completa de uma rota da API (mesma base do `fetch`) — para `<img src>` (ex.: o stream
 * `/api/fpv.mjpg`) respeitar o mesmo `?api=`/`window.__SIM_API_BASE__` dos pedidos JSON.
 */
export function urlApi(caminho: string): string {
  return `${baseApi()}${caminho}`
}

/** Mensagem curta e legível a partir de qualquer resposta/corpo de erro. */
async function mensagemDeErro(resposta: Response): Promise<string> {
  try {
    const texto = await resposta.text()
    if (texto.length > 0) {
      try {
        const json: unknown = JSON.parse(texto)
        if (typeof json === "object" && json !== null) {
          const o = json as Record<string, unknown>
          const detalhe = o.erro ?? o.erro_detalhe ?? o.message ?? o.detail
          if (typeof detalhe === "string") return detalhe
        }
      } catch {
        return texto.slice(0, 160)
      }
      return texto.slice(0, 160)
    }
  } catch {
    /* corpo ilegível: fica só o código */
  }
  return `HTTP ${resposta.status}`
}

async function pedirJson(
  caminho: string,
  init?: RequestInit
): Promise<unknown> {
  let resposta: Response
  try {
    resposta = await fetch(urlApi(caminho), {
      ...init,
      headers: { Accept: "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    })
  } catch (erro) {
    if (erro instanceof DOMException && erro.name === "AbortError") throw erro
    throw new ErroApi("sem ligação à API da simulação")
  }
  if (!resposta.ok)
    throw new ErroApi(await mensagemDeErro(resposta), resposta.status)
  try {
    return (await resposta.json()) as unknown
  } catch {
    throw new ErroApi("resposta da API não é JSON válido", resposta.status)
  }
}

/** `GET /api/sim` — estado do episódio + histórico de linhas (o stream que alimenta as curvas). */
export async function buscarSim(sinal?: AbortSignal): Promise<RespostaSim> {
  return lerSim(await pedirJson("/api/sim", { signal: sinal }))
}

/** `GET /api/state` — resumo do servidor (modelo, constantes físicas e, na planta real, o `hardware`). */
export async function buscarEstado(sinal?: AbortSignal): Promise<ResumoEstado> {
  return lerResumo(await pedirJson("/api/state", { signal: sinal }))
}

/** `POST /api/vento` {vel,azimute,elevacao} → 200 ou 400 (a mensagem do 400 chega ao utilizador). */
export async function enviarVento(corpo: CorpoVento): Promise<void> {
  const bruto = await pedirJson("/api/vento", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
}

/**
 * `POST /api/parar` → 200: **PARAR VENTO** numa só escrita atómica.
 *
 * O servidor põe o vento base a 0 **e** desliga o vento dinâmico no mesmo pedido (bloco `dinamico` em
 * `nenhum`, com `seq` novo). É isto que garante que depois de parar não fica nenhuma rajada ativa nem
 * pendente: um `POST /api/vento {vel: 0}` sozinho parava só o vento constante e as rajadas do modo
 * contínuo (ou a rajada one-shot a meio) continuavam a atuar.
 */
export async function enviarParar(): Promise<void> {
  const bruto = await pedirJson("/api/parar", { method: "POST" })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
}

/**
 * `POST /api/vento-dinamico` `{modo, params?, ativo?}` → 200 ou 400.
 *
 * É o ÚNICO caminho para ligar/desligar a dinâmica do vento: escreve o controlo e a física muda no passo
 * de decisão seguinte — **nunca** reinicia o episódio (`/api/reiniciar` é só do botão com hold).
 */
export async function enviarVentoDinamico(
  corpo: CorpoVentoDinamico
): Promise<void> {
  const bruto = await pedirJson("/api/vento-dinamico", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
}

/**
 * `POST /api/camera` (CONTRATO v2) — um SUBCONJUNTO de `{azimute, elevacao, distancia}`: só os
 * campos que o gesto manda mudar. **SEM** `alvo` (o alvo é do backend: drone+offset, que ele
 * segue) nem `seq` (o servidor incrementa-o no bloco `camera` do controlo) → 200 ou 400
 * (`null`, campos desconhecidos ou fora das faixas do contrato).
 *
 * O runner aplica o comando ao `viewer.cam` UMA VEZ por mudança de assinatura: o rato da janela 3D
 * continua livre entre comandos. Nenhum campo do controlo (`loop`, `reiniciar`, vento) é tocado.
 */
export async function enviarCamera(
  corpo: CorpoCamera
): Promise<CameraEstado | null> {
  const bruto = await pedirJson("/api/camera", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
  // O bloco confirmado (`{azimute, elevacao, distancia, seq}`) — sem janela nativa (`camera_atual:
  // null`) é a ÚNICA confirmação que existe de onde a câmara da simulação ficou.
  return lerCamera(o.camera)
}

/**
 * `POST /api/camera {}` — o «toque» do contrato v2: um corpo vazio mantém os valores e devolve o bloco
 * em vigor. O cockpit usa-o UMA vez ao arrancar para saber onde está a câmara da simulação, porque
 * sem janela nativa nem o `/api/sim` nem o `/api/state` a publicam (`camera_atual: null`).
 */
export async function lerCameraEmVigor(): Promise<CameraEstado | null> {
  return enviarCamera({})
}

/**
 * `POST /api/fpv` (módulo de câmara FPV) — um SUBCONJUNTO de `{ligada, modo}`: só os campos que se
 * quer mudar. **SEM** `seq` (o servidor incrementa-o a cada pedido; mandá-lo força re-aplicação,
 * que aqui não é preciso) → 200 `{"ok": true, "fpv": {ligada, modo, seq}}` ou 400 (`null`, chaves
 * desconhecidas, `modo` inexistente — ou não emulado, como o HDR). A mensagem do 400 chega ao
 * utilizador como `ErroApi`, como nos restantes POSTs.
 */
export async function enviarFpv(corpo: CorpoFpv): Promise<void> {
  const bruto = await pedirJson("/api/fpv", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
}

/** `POST /api/reiniciar` → `{contador: n}` (o backend conta os reinícios). */
export async function enviarReiniciar(): Promise<number | null> {
  const bruto = await pedirJson("/api/reiniciar", { method: "POST" })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  return numero(o.contador)
}

/** `POST /api/loop {"ativo":bool}` → 200 (o auto-reset é do backend; o site não reinicia sozinho). */
export async function enviarLoop(ativo: boolean): Promise<void> {
  await pedirJson("/api/loop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ativo }),
  })
}

/**
 * Corpo de `POST /api/voo` (contratos r11 + r12) — `{"ativo": bool, "teclas": {w,a,s,d,q,e: bool},
 * "yaw_taxa"?: number, "yaw_alvo"?: number|null, "segui_alvo"?: bool}`: as 6 teclas SEMPRE presentes e
 * **sem** `seq` (o servidor carimba o dele). Chaves desconhecidas (inclusive `seq` no corpo) são
 * recusadas pelo servidor com 400. Os campos de yaw são opcionais no contrato mas o site MANDA-OS
 * sempre que tem estado (o corpo é ESTADO completo — cada keydown/keyup manda tudo).
 */
export interface CorpoVoo {
  ativo: boolean
  teclas: TeclasVoo
  /** Taxa de guinada (rad/s, ∈ [−2, 2]); Z/C mandam ±0,5. */
  yaw_taxa?: number
  /** Rumo-alvo (rad desde o armar) ou `null` (sem alvo); X manda o `rumo` atual. */
  yaw_alvo?: number | null
  /** «Olhar»/IBVS (tecla V). */
  segui_alvo?: boolean
}

/**
 * `POST /api/voo` (contratos r11 + r12) — estado das teclas + yaw → 200 `{"ok": true, "voo": {bloco}}`
 * (o bloco confirmado, com o `seq` do servidor) ou 400 (a mensagem do `erro` chega ao utilizador
 * como `ErroApi`, como nos restantes POSTs). O corpo leva só `{"ativo", "teclas", "yaw_taxa",
 * "yaw_alvo", "segui_alvo"}` normalizados — nada mais entra, para nunca levar o servidor a devolver
 * «chaves desconhecidas».
 */
export async function enviarVoo(corpo: CorpoVoo): Promise<BlocoVoo> {
  const teclas: TeclasVoo = { ...TECLAS_VOO_ZERADAS }
  for (const tecla of TECLAS_VOO) teclas[tecla] = corpo.teclas[tecla] === true
  const yawTaxa = Number(corpo.yaw_taxa ?? 0)
  const yawAlvo =
    corpo.yaw_alvo === undefined || corpo.yaw_alvo === null
      ? null
      : Number(corpo.yaw_alvo)
  const bruto = await pedirJson("/api/voo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ativo: corpo.ativo === true,
      teclas,
      yaw_taxa: Number.isFinite(yawTaxa) ? yawTaxa : 0,
      yaw_alvo: yawAlvo !== null && Number.isFinite(yawAlvo) ? yawAlvo : null,
      segui_alvo: corpo.segui_alvo === true,
    }),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
  const bloco = lerBlocoVoo(o.voo)
  // Um 200 sem bloco `voo` é uma violação do contrato: diz-se alto (aviso + re-sincronização com
  // o eco) em vez de fingir que o servidor confirmou.
  if (bloco === null)
    throw new ErroApi("resposta do POST /api/voo sem bloco `voo`", 200)
  return bloco
}

/**
 * `POST /api/controlador {"modo": "rl"|"classico"}` (contrato r12) — o SELETOR de controlador → 200
 * `{"ok": true, "controlador": {"modo", "seq"}}` ou 400 (modo inválido, chaves desconhecidas). O
 * runner troca AO VIVO no passo de decisão seguinte — a troca reinicia o EPISÓDIO (calibração do
 * giroscópio) e o `/api/state` mostra `controlador.estado = "trocando"` + `motivo` enquanto o eco não
 * apanha o pedido. Só `modo` entra no corpo (o `seq` é do servidor).
 */
export async function enviarControlador(
  modo: "rl" | "classico"
): Promise<void> {
  const bruto = await pedirJson("/api/controlador", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modo: modo === "classico" ? "classico" : "rl" }),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
}

/** Comandos de bateria da planta real: fechar o ciclo do pack ou trocar por um pack novo. */
export type AcaoBateria = "recarregar" | "nova"

/** O que o servidor confirmou (`{"ok": true, "bateria": {"acao", "seq"}}`); `null` no que não vier. */
export interface RespostaBateria {
  acao: string | null
  /** Nº de ordem do comando no ficheiro de controlo (o servidor incrementa-o a cada pedido). */
  seq: number | null
}

/**
 * `POST /api/bateria {"acao": "recarregar" | "nova"}` → 200 `{ok, bateria: {acao, seq}}` ou 400 (a
 * mensagem chega ao utilizador). `recarregar` fecha o ciclo do pack (aplica o desgaste e volta a 100 %);
 * `nova` troca por um pack NOVO (SoH 100 %, 0 ciclos). O runner consome o comando no passo de decisão
 * seguinte — o efeito vê-se na telemetria (`bateria.soc`, `bateria.ultimo_ciclo`), não nesta resposta.
 */
export async function enviarBateria(
  acao: AcaoBateria
): Promise<RespostaBateria> {
  const bruto = await pedirJson("/api/bateria", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ acao }),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
  const bateria =
    typeof o.bateria === "object" && o.bateria !== null
      ? (o.bateria as Record<string, unknown>)
      : {}
  return {
    acao: typeof bateria.acao === "string" ? bateria.acao : null,
    seq: numero(bateria.seq),
  }
}

/**
 * `POST /api/vento-simples` (r13 — os três botões do vento) com um SUBCONJUNTO de `{ligado,
 * intensidade, aleatorio, direcao}` → o bloco confirmado (`seq` do servidor fica de fora), ou 400 com
 * o motivo. O corpo já vem validado por `corpoVentoSimples` (`lib/cockpit.ts`).
 */
export async function enviarVentoSimples(
  corpo: Partial<VentoSimples>
): Promise<VentoSimples | null> {
  const bruto = await pedirJson("/api/vento-simples", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
  return lerVentoSimples(o.vento_simples)
}

/** `POST /api/bola {"velocidade"}` (r13) → a velocidade confirmada (m/s), ou 400 com o motivo. */
export async function enviarBola(velocidade: number): Promise<number | null> {
  const bruto = await pedirJson("/api/bola", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ velocidade }),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
  const bola =
    typeof o.bola === "object" && o.bola !== null
      ? (o.bola as Record<string, unknown>)
      : {}
  return numero(bola.velocidade)
}

/** `POST /api/bola {"auto_atirar": bool}` → ativa/desativa o disparo automático quando no alvo. */
export async function enviarAutoAtirarBola(
  autoAtirar: boolean
): Promise<boolean | null> {
  const bruto = await pedirJson("/api/bola", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ auto_atirar: Boolean(autoAtirar) }),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
  const bola =
    typeof o.bola === "object" && o.bola !== null
      ? (o.bola as Record<string, unknown>)
      : {}
  return typeof bola.auto_atirar === "boolean" ? bola.auto_atirar : null
}

/** `POST /api/tiro {"gatilho": bool}` → dispara 1 tiro da Glock 25 no topo do drone (tecla SPACE). */
export async function enviarTiro(
  gatilho = true
): Promise<{ gatilho: boolean; disparos: number; seq: number } | null> {
  const bruto = await pedirJson("/api/tiro", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gatilho: Boolean(gatilho) }),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
  const t =
    typeof o.tiro === "object" && o.tiro !== null
      ? (o.tiro as Record<string, unknown>)
      : null
  if (t === null) return null
  return {
    gatilho: t.gatilho === true,
    disparos: numero(t.disparos) ?? 0,
    seq: numero(t.seq) ?? 0,
  }
}

/** `POST /api/carga {"carga_extra_g"}` → define carga útil extra acoplada ao drone (0..5000 g). */
export async function enviarCarga(
  cargaExtraG: number
): Promise<{ carga_extra_g: number; seq: number } | null> {
  const bruto = await pedirJson("/api/carga", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ carga_extra_g: Number(cargaExtraG) }),
  })
  const o =
    typeof bruto === "object" && bruto !== null
      ? (bruto as Record<string, unknown>)
      : {}
  if (o.erro !== undefined) throw new ErroApi(String(o.erro))
  const c =
    typeof o.carga === "object" && o.carga !== null
      ? (o.carga as Record<string, unknown>)
      : null
  if (c === null) return null
  return {
    carga_extra_g: numero(c.carga_extra_g) ?? 0,
    seq: numero(c.seq) ?? 0,
  }
}

/**
 * `GET /api/hud.json` — a última amostra do HUD com a idade que o servidor lhe dá. É o FALLBACK do
 * SSE (`GET /api/hud`): quando o `EventSource` cai, o HUD continua a mexer por sondagem.
 */
export async function buscarHudJson(
  sinal?: AbortSignal
): Promise<{ hud: AmostraHud | null; idadeS: number | null; velho: boolean }> {
  return lerHudJson(await pedirJson("/api/hud.json", { signal: sinal }))
}
