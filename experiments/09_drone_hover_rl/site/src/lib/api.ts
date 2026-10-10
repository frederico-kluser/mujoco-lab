/**
 * Cliente HTTP do backend `sim_site.py` (mesma origem por omissão).
 *
 * O servidor serve `site/dist/` e a API no mesmo porto, logo os caminhos são relativos. Para testes e
 * para apontar o `dist/` estático a outro porto aceita-se `?api=http://host:porto` ou a variável global
 * `window.__SIM_API_BASE__` — nada disto muda o caminho de produção (por omissão: mesma origem).
 */

import {
  lerResumo,
  lerSim,
  numero,
  type CorpoCamera,
  type CorpoVento,
  type CorpoVentoDinamico,
  type RespostaSim,
  type ResumoEstado,
} from "./sim"

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

function url(caminho: string): string {
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
    resposta = await fetch(url(caminho), {
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
export async function enviarCamera(corpo: CorpoCamera): Promise<void> {
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
