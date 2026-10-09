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

/** `GET /api/state` — resumo do servidor (nome do modelo, constantes físicas, quando existirem). */
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
