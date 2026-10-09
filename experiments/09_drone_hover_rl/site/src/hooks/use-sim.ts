/**
 * Polling de `GET /api/sim` a ~2,9 Hz (contrato: 2–5 Hz, sem websockets) + o histórico local.
 *
 * O backend manda `linhas` (o histórico dele); aqui acumula-se por `ep:passo` para sobreviver tanto a um
 * servidor que só devolva a cauda como a um que devolva tudo outra vez. Episódio novo ⇒ histórico novo.
 */

import { useCallback, useEffect, useState } from "react"

import {
  buscarEstado,
  buscarSim,
  enviarLoop,
  enviarReiniciar,
  enviarVento,
} from "@/lib/api"
import {
  chaveLinha,
  type CorpoVento,
  type EstadoEpisodio,
  type LinhaSim,
  type ResumoEstado,
  type VentoEstado,
} from "@/lib/sim"

/** Período do polling em ms (≈2,9 Hz, dentro da janela 2–5 Hz do contrato). */
export const INTERVALO_POLLING_MS = 350
/** Pontos máximos guardados por curva (10 s de episódio a 50 Hz de decisão = 500). */
export const MAX_PONTOS = 600
/** Recarregar o resumo (`/api/state`) a cada N polls. */
const POLLS_POR_RESUMO = 40

export type Ligacao = "a_ligar" | "ligado" | "sem_ligacao"

export interface SimStream {
  linhas: LinhaSim[]
  ultima: LinhaSim | null
  estado: EstadoEpisodio
  ep: number
  passo: number
  retorno: number
  vento: VentoEstado
  resumo: ResumoEstado | null
  ligacao: Ligacao
  erro: string | null
  /** Instante (ms) da última resposta 200 — usado no selo "ligado há Xs". */
  atualizadoEm: number | null
  /** Nº de respostas 200 desde o arranque (prova de vida do polling). */
  respostas: number
  reiniciar: () => Promise<number | null>
  aplicarVento: (corpo: CorpoVento) => Promise<void>
  pararVento: (ventoAtual: VentoEstado) => Promise<void>
  definirLoop: (ativo: boolean) => Promise<void>
}

const VENTO_ZERO: VentoEstado = { vel: 0, azimute: 0, elevacao: 0, ativo: false }

export function useSim(): SimStream {
  const [linhas, setLinhas] = useState<LinhaSim[]>([])
  const [cabecalho, setCabecalho] = useState<{
    estado: EstadoEpisodio
    ep: number
    passo: number
    retorno: number
    vento: VentoEstado
  }>({ estado: "a_correr", ep: 0, passo: 0, retorno: 0, vento: VENTO_ZERO })
  const [resumo, setResumo] = useState<ResumoEstado | null>(null)
  const [ligacao, setLigacao] = useState<Ligacao>("a_ligar")
  const [erro, setErro] = useState<string | null>(null)
  const [atualizadoEm, setAtualizadoEm] = useState<number | null>(null)
  const [respostas, setRespostas] = useState(0)

  const aplicar = useCallback(    (dados: Awaited<ReturnType<typeof buscarSim>>) => {
      setCabecalho({
        estado: dados.estado,
        ep: dados.ep,
        passo: dados.passo,
        retorno: dados.retorno,
        vento: dados.vento,
      })
      if (dados.linhas.length === 0) return
      setLinhas((anteriores) => {
        const vistos = new Set(anteriores.map(chaveLinha))
        const novas = dados.linhas.filter((l) => !vistos.has(chaveLinha(l)))
        if (novas.length === 0) return anteriores
        const epNovo = novas[novas.length - 1].ep
        const epAntigo = anteriores.length > 0 ? anteriores[anteriores.length - 1].ep : epNovo
        const base = epNovo !== epAntigo ? [] : anteriores
        return [...base, ...novas].slice(-MAX_PONTOS)
      })
    },
    [],
  )

  /** Um fetch imediato (usado depois de cada ação para o ecrã não esperar o próximo ciclo). */
  const pollAgora = useCallback(async () => {
    const dados = await buscarSim()
    aplicar(dados)
    setLigacao("ligado")
    setErro(null)
    setAtualizadoEm(Date.now())
    setRespostas((n) => n + 1)
  }, [aplicar])

  useEffect(() => {
    let vivo = true
    let temporizador = 0
    const controlador = new AbortController()
    let ciclos = 0

    const carregarResumo = async () => {
      try {
        const dados = await buscarEstado(controlador.signal)
        if (vivo) setResumo(dados)
      } catch {
        /* o resumo é acessório: a falta dele não derruba a página */
      }
    }

    const ciclo = async () => {
      try {
        const dados = await buscarSim(controlador.signal)
        if (!vivo) return
        aplicar(dados)
        setLigacao("ligado")
        setErro(null)
        setAtualizadoEm(Date.now())
        setRespostas((n) => n + 1)
        if (ciclos % POLLS_POR_RESUMO === 0) void carregarResumo()
      } catch (falha) {
        if (!vivo || (falha instanceof DOMException && falha.name === "AbortError")) return
        setLigacao("sem_ligacao")
        setErro(falha instanceof Error ? falha.message : "falha desconhecida na API")
      } finally {
        ciclos += 1
        if (vivo) temporizador = window.setTimeout(ciclo, INTERVALO_POLLING_MS)
      }
    }

    void ciclo()
    return () => {
      vivo = false
      window.clearTimeout(temporizador)
      controlador.abort()
    }
  }, [aplicar])

  const reiniciar = useCallback(async () => {
    const contador = await enviarReiniciar()
    await pollAgora()
    return contador
  }, [pollAgora])

  const aplicarVento = useCallback(
    async (corpo: CorpoVento) => {
      await enviarVento(corpo)
      await pollAgora()
    },
    [pollAgora],
  )

  const pararVento = useCallback(
    async (ventoAtual: VentoEstado) => {
      // "PARAR VENTO" = velocidade 0 no MESMO azimute/elevação: o contrato do POST só tem
      // {vel,azimute,elevacao}, logo não se inventa uma chave extra que o backend possa recusar.
      await enviarVento({ vel: 0, azimute: ventoAtual.azimute, elevacao: ventoAtual.elevacao })
      await pollAgora()
    },
    [pollAgora],
  )

  const definirLoop = useCallback(
    async (ativo: boolean) => {
      await enviarLoop(ativo)
      await pollAgora()
    },
    [pollAgora],
  )

  return {
    linhas,
    ultima: linhas.length > 0 ? linhas[linhas.length - 1] : null,
    estado: cabecalho.estado,
    ep: cabecalho.ep,
    passo: cabecalho.passo,
    retorno: cabecalho.retorno,
    vento: cabecalho.vento,
    resumo,
    ligacao,
    erro,
    atualizadoEm,
    respostas,
    reiniciar,
    aplicarVento,
    pararVento,
    definirLoop,
  }
}
