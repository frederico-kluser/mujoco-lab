/**
 * Polling de `GET /api/sim` a ~2,9 Hz (contrato: 2–5 Hz, sem websockets) + o histórico local.
 *
 * O backend manda `linhas` (o histórico dele); aqui acumula-se por `ep:passo` para sobreviver tanto a um
 * servidor que só devolva a cauda como a um que devolva tudo outra vez. Episódio novo ⇒ histórico novo.
 */

import { useCallback, useEffect, useRef, useState } from "react"

import {
  buscarEstado,
  buscarSim,
  enviarBateria,
  enviarCamera,
  enviarLoop,
  enviarParar,
  enviarReiniciar,
  enviarVento,
  enviarVentoDinamico,
  type AcaoBateria,
  type RespostaBateria,
} from "@/lib/api"
import {
  definirLeitorEstadoDinamico,
  invalidarEnviosDinamicos,
  observarEstadoServidor,
  type EstadoDinamico,
} from "@/lib/paragem"
import {
  chaveLinha,
  fundirCamera,
  VENTO_DINAMICO_PARADO,
  type CameraEstado,
  type CorpoCamera,
  type CorpoVento,
  type CorpoVentoDinamico,
  type EstadoEpisodio,
  type LinhaSim,
  type Planta,
  type ResumoEstado,
  type Rpi5,
  type VentoDinamico,
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
  /** Modo dinâmico em vigor (`POST /api/vento-dinamico`); nunca reinicia o episódio. */
  ventoDinamico: VentoDinamico
  /** Painel do RPi 5 (`/api/sim` e, em reforço, `/api/state`); `null` = o backend não o publica. */
  rpi5: Rpi5 | null
  /**
   * CâMARA REAL da janela (`camera_atual`, em reforço a `camera` da telemetria); `null` = SEM DADOS
   * (sem janela, ou a API disse `null`) → o widget mostra «—». É isto que a esfera do pad segue
   * fora de arrasto — inclusive quando a câmara é mexida pelo RATO da própria janela 3D — e um
   * `null` explícito da API propaga (nunca se retém uma câmara que a API já desmentiu:
   * `fundirCamera`, DEF-2).
   */
  camera: CameraEstado | null
  /** Valores por omissão da câmara (`camera_padrao`) — o que o REPOR VISTA envia; `null` se não vier. */
  cameraPadrao: CameraEstado | null
  /**
   * Continuidade do BACKEND (`loop` do `/api/sim`, em reforço do `/api/state`): `true` = reinicia
   * sozinho ao terminar, `false` = para no fim. `null` quando nenhuma das respostas o diz — nesse caso
   * quem manda é o estado local otimista do `App`.
   */
  loop: boolean | null
  /**
   * Planta anunciada pela API (`planta` do `/api/sim`, em reforço do `/api/state`); `null` = nenhuma
   * resposta o disse. A planta EM VIGOR é a da última linha (`plantaEmVigor`): esta é o recurso.
   */
  planta: Planta | null
  resumo: ResumoEstado | null
  ligacao: Ligacao
  erro: string | null
  /** Instante (ms) da última resposta 200 — usado no selo "ligado há Xs". */
  atualizadoEm: number | null
  /** Nº de respostas 200 desde o arranque (prova de vida do polling). */
  respostas: number
  reiniciar: () => Promise<number | null>
  aplicarVento: (corpo: CorpoVento) => Promise<void>
  /** PARAR VENTO: vento base a 0 **e** vento dinâmico desligado, numa só escrita (`POST /api/parar`). */
  pararTudo: () => Promise<void>
  aplicarVentoDinamico: (corpo: CorpoVentoDinamico) => Promise<void>
  /**
   * `POST /api/camera` (contrato v2) — um comando de câmara: subconjunto de
   * `{azimute, elevacao, distancia}`, SEM `alvo` nem `seq` (o servidor incrementa-o). Passa pela
   * fila dos controlos (ordem das escritas = ordem dos gestos) e relê o `/api/sim` no fim, para o
   * ecrã adotar depressa o valor confirmado pela câmara real.
   */
  aplicarCamera: (corpo: CorpoCamera) => Promise<void>
  /**
   * `POST /api/bateria {acao}` (planta real): `recarregar` fecha o ciclo do pack, `nova` troca de pack.
   * Passa pela fila dos controlos (como os outros POSTs) e relê o `/api/sim` no fim; devolve o que o
   * servidor confirmou (`acao`, `seq`) — o efeito chega depois, na telemetria.
   */
  aplicarBateria: (acao: AcaoBateria) => Promise<RespostaBateria>
  definirLoop: (ativo: boolean) => Promise<void>
  /**
   * Relê o `/api/sim` AGORA (sem esperar o próximo ciclo): usado pelo painel quando um comando foi
   * suprimido por estar velho e pelas mensagens de outra aba, para o ecrã mostrar já o estado do servidor.
   */
  atualizar: () => Promise<void>
}

const VENTO_ZERO: VentoEstado = {
  vel: 0,
  azimute: 0,
  elevacao: 0,
  ativo: false,
  vec: null,
  modo: null,
}

export function useSim(): SimStream {
  const [linhas, setLinhas] = useState<LinhaSim[]>([])
  const [cabecalho, setCabecalho] = useState<{
    estado: EstadoEpisodio
    ep: number
    passo: number
    retorno: number
    vento: VentoEstado
    ventoDinamico: VentoDinamico
    rpi5: Rpi5 | null
    loop: boolean | null
    camera: CameraEstado | null
    cameraPadrao: CameraEstado | null
    planta: Planta | null
  }>({
    estado: "a_correr",
    ep: 0,
    passo: 0,
    retorno: 0,
    vento: VENTO_ZERO,
    ventoDinamico: VENTO_DINAMICO_PARADO,
    rpi5: null,
    // `null` = a API ainda não disse nada (primeiro render). O `App` trata a ausência como SEM REINÍCIO
    // (`?? false`), o MESMO default do backend — nunca como CONTÍNUO, que faria o toggle contrariar o
    // runner no arranque.
    loop: null,
    // Câmara: `null` = sem dados (sem janela ou backend ainda sem o bloco `camera`) → o bloco «Câmara»
    // mostra «—», honestamente, em vez de fingir uma pose.
    camera: null,
    cameraPadrao: null,
    // Planta: `null` até alguma resposta a anunciar (o site comporta-se como cf2 até lá).
    planta: null,
  })
  const [resumo, setResumo] = useState<ResumoEstado | null>(null)
  const [ligacao, setLigacao] = useState<Ligacao>("a_ligar")
  const [erro, setErro] = useState<string | null>(null)
  const [atualizadoEm, setAtualizadoEm] = useState<number | null>(null)
  const [respostas, setRespostas] = useState(0)

  /** Nº de ordem de cada leitura do `/api/sim` (emitido no PEDIDO) e da última aplicada. */
  const leituraEmitida = useRef(0)
  const leituraAplicada = useRef(0)

  /**
   * `GET /api/sim` com o Nº DE ORDEM da leitura e o instante em que o pedido SAIU.
   *
   * O nº de ordem é emitido no pedido (não na resposta): quem chega atrasado — o `/api/sim` que já estava
   * em voo quando o PARAR aconteceu, ou uma resposta atrasada da prova — não passa à frente de uma leitura
   * mais recente. O instante de emissão é o que o módulo das paragens usa para saber se a leitura é
   * posterior ao clique de paragem.
   */
  const lerSimFresco = useCallback(async (sinal?: AbortSignal) => {
    const leitura = (leituraEmitida.current += 1)
    const emitidoEm = performance.now()
    const dados = await buscarSim(sinal)
    return { leitura, emitidoEm, dados }
  }, [])

  const aplicar = useCallback(
    (
      dados: Awaited<ReturnType<typeof buscarSim>>,
      leitura: number,
      emitidoEm: number
    ) => {
      // Resposta VELHA (chegou depois de uma leitura mais recente já aplicada): descartada por inteiro. É o
      // que impede um poll atrasado (o `/api/sim` de antes do PARAR, ainda em voo) de reacender o painel
      // com o estado antigo — o ecrã fica com a leitura MAIS RECENTE, como o laboratório exige.
      if (leitura < leituraAplicada.current) return
      leituraAplicada.current = leitura
      // O estado do servidor vai para o módulo das paragens: é ele que diz se o bloqueio do live-apply já
      // pode ser levantado (adoção do modo vindo do poll — inclusive de OUTRO cliente).
      observarEstadoServidor(dados.ventoDinamico, emitidoEm)
      setCabecalho((anterior) => ({
        estado: dados.estado,
        ep: dados.ep,
        passo: dados.passo,
        retorno: dados.retorno,
        vento: dados.vento,
        ventoDinamico: dados.ventoDinamico,
        // `/api/sim` é a fonte principal do rpi5; se esta versão do backend ainda não o trouxer, mantém-se
        // o que o `/api/state` tiver dito (nunca se apaga um painel que já estava a mostrar números).
        rpi5: dados.rpi5 ?? anterior.rpi5,
        // Igual ao rpi5: um backend que ainda não publique `loop` no `/api/sim` não apaga o que o
        // `/api/state` (ou o próprio POST /api/loop) já disse.
        loop: dados.loop ?? anterior.loop,
        // CâMARA: fusão HONESTA (`fundirCamera`) — `camera_atual` é a fonte principal (câmara REAL,
        // `null` sem janela) e a `camera` da telemetria é o reforço. Um `null` explícito PROPAGA
        // (o painel mostra «—», estados honestos: DEF-2); o anterior só se retém quando a resposta
        // não publica câmara nenhuma (backend antigo — «o que não veio não apaga»).
        camera: fundirCamera(
          anterior.camera,
          dados.cameraAtual,
          dados.camera,
          dados.cameraPublicada
        ),
        cameraPadrao: dados.cameraPadrao ?? anterior.cameraPadrao,
        // Como o rpi5: um backend que ainda não publique `planta` não apaga o que já se sabia.
        planta: dados.planta ?? anterior.planta,
      }))
      if (dados.linhas.length === 0) return
      setLinhas((anteriores) => {
        const vistos = new Set(anteriores.map(chaveLinha))
        const novas = dados.linhas.filter((l) => !vistos.has(chaveLinha(l)))
        if (novas.length === 0) return anteriores
        const epNovo = novas[novas.length - 1].ep
        const epAntigo =
          anteriores.length > 0 ? anteriores[anteriores.length - 1].ep : epNovo
        const base = epNovo !== epAntigo ? [] : anteriores
        return [...base, ...novas].slice(-MAX_PONTOS)
      })
    },
    []
  )

  /** Um fetch imediato (usado depois de cada ação para o ecrã não esperar o próximo ciclo). */
  const pollAgora = useCallback(async () => {
    const { leitura, emitidoEm, dados } = await lerSimFresco()
    aplicar(dados, leitura, emitidoEm)
    setLigacao("ligado")
    setErro(null)
    setAtualizadoEm(Date.now())
    setRespostas((n) => n + 1)
  }, [aplicar, lerSimFresco])

  /**
   * Leitura BARATA do estado do vento dinâmico (`GET /api/state`, sem as amostras da telemetria).
   *
   * É a REVALIDAÇÃO do apply agendado do painel: ao disparar o debounce, o front confirma aqui que o modo
   * que ia religar ainda está ativo no servidor. Uma paragem feita por OUTRO cliente (POST cru, outra aba)
   * aparece aqui de imediato — o polling de 350 ms do site chegaria sempre depois do debounce de 300 ms.
   */
  const lerEstadoDinamico = useCallback(async (): Promise<EstadoDinamico> => {
    const resumo = await buscarEstado()
    return { modo: resumo.ventoDinamico.modo, ativo: resumo.ventoDinamico.ativo }
  }, [])

  useEffect(() => {
    definirLeitorEstadoDinamico(lerEstadoDinamico)
    return () => definirLeitorEstadoDinamico(null)
  }, [lerEstadoDinamico])

  /**
   * FILA dos POSTs de controlo: um de cada vez, pela ordem em que foram pedidos.
   *
   * O servidor escreve o ficheiro de controlo em modo «o último ganha» — se um `POST /api/vento-dinamico`
   * já em voo chegar depois do `POST /api/parar`, o modo dinâmico volta a ligar-se e o PARAR perde. Com a
   * fila, o PARAR só sai depois de tudo o que foi pedido antes dele ter assentado: a ordem dos cliques é a
   * ordem das escritas no servidor. Uma falha de um pedido não trava os seguintes: a tarefa seguinte corre
   * de qualquer maneira (`then(tarefa, tarefa)`) e a cauda da fila absorve a rejeição (quem pediu recebe-a
   * no `proximo` que lhe é devolvido).
   */
  const fila = useRef<Promise<unknown>>(Promise.resolve())
  const encadear = useCallback(<T,>(tarefa: () => Promise<T>): Promise<T> => {
    const proximo = fila.current.then(tarefa, tarefa)
    fila.current = proximo.catch(() => undefined)
    return proximo
  }, [])

  useEffect(() => {
    let vivo = true
    let temporizador = 0
    const controlador = new AbortController()
    let ciclos = 0

    const carregarResumo = async () => {
      try {
        const dados = await buscarEstado(controlador.signal)
        if (!vivo) return
        setResumo(dados)
        // O `rpi5` pode vir só no `/api/state` (o `/api/sim` é a fonte principal): aproveita-se o que
        // existir, sem apagar números já mostrados quando este resumo não os traz.
        if (dados.rpi5 !== null) {
          setCabecalho((anterior) => ({ ...anterior, rpi5: dados.rpi5 }))
        }
        if (dados.loop !== null) {
          setCabecalho((anterior) => ({ ...anterior, loop: dados.loop }))
        }
        // Planta (reforço do `/api/sim`): só escreve quando o resumo a anuncia.
        if (dados.planta !== null) {
          setCabecalho((anterior) => ({ ...anterior, planta: dados.planta }))
        }
        // Câmara (reforço do `/api/sim`, como o rpi5): o `/api/state` também publica
        // `camera_atual`/`camera_padrao` — a MESMA fusão honesta do `/api/sim` (o `null` explícito
        // propaga para «—»; só respostas sem câmara nenhuma retêm o anterior).
        setCabecalho((anterior) => ({
          ...anterior,
          camera: fundirCamera(
            anterior.camera,
            dados.cameraAtual,
            dados.camera,
            dados.cameraPublicada
          ),
        }))
        if (dados.cameraPadrao !== null) {
          setCabecalho((anterior) => ({
            ...anterior,
            cameraPadrao: dados.cameraPadrao,
          }))
        }
      } catch {
        /* o resumo é acessório: a falta dele não derruba a página */
      }
    }

    const ciclo = async () => {
      try {
        const { leitura, emitidoEm, dados } = await lerSimFresco(controlador.signal)
        if (!vivo) return
        aplicar(dados, leitura, emitidoEm)
        setLigacao("ligado")
        setErro(null)
        setAtualizadoEm(Date.now())
        setRespostas((n) => n + 1)
        if (ciclos % POLLS_POR_RESUMO === 0) void carregarResumo()
      } catch (falha) {
        if (
          !vivo ||
          (falha instanceof DOMException && falha.name === "AbortError")
        )
          return
        setLigacao("sem_ligacao")
        setErro(
          falha instanceof Error ? falha.message : "falha desconhecida na API"
        )
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
  }, [aplicar, lerSimFresco])

  const reiniciar = useCallback(async () => {
    const contador = await encadear(() => enviarReiniciar())
    await pollAgora()
    return contador
  }, [encadear, pollAgora])

  const aplicarVento = useCallback(
    async (corpo: CorpoVento) => {
      await encadear(() => enviarVento(corpo))
      await pollAgora()
    },
    [encadear, pollAgora]
  )

  const pararTudo = useCallback(async () => {
    // "PARAR VENTO" = vento 0 **e** dinâmica desligada. É UM pedido (`POST /api/parar`): o servidor faz as
    // duas coisas na MESMA escrita atómica do controlo, logo não há instante em que as rajadas do modo
    // contínuo (ou uma rajada one-shot a meio) fiquem a atuar depois do PARAR.
    //
    // E é o ÚLTIMO pedido: (a) a época sobe JÁ (síncrona, antes de qualquer await), o que mata os applies
    // agendados pelo debounce do painel; (b) a fila garante que este POST só sai depois de qualquer POST
    // dinâmico que já esteja em voo ter assentado — sem isto, um apply que saiu milissegundos antes do
    // clique podia chegar ao servidor DEPOIS da paragem e reativar o modo (o servidor honra o último).
    invalidarEnviosDinamicos()
    await encadear(() => enviarParar())
    await pollAgora()
  }, [encadear, pollAgora])

  const definirLoop = useCallback(
    async (ativo: boolean) => {
      await encadear(() => enviarLoop(ativo))
      await pollAgora()
    },
    [encadear, pollAgora]
  )

  /** Última linha do histórico (valor atual das curvas e do mostrador de vento). */
  const ultima = linhas.length > 0 ? linhas[linhas.length - 1] : null

  /**
   * `POST /api/vento-dinamico` — só escreve o modo; o episódio continua a correr.
   *
   * O payload é SEMPRE o do contrato (`frente` incluído: `{vel,azimute,elevacao}` = degrau imediato);
   * um 400 do servidor chega ao utilizador como aviso, não se reescreve o pedido noutro formato.
   * Passa pela fila (como o PARAR) para a ordem dos pedidos ser a ordem das escritas no controlo.
   */
  const aplicarVentoDinamico = useCallback(
    async (corpo: CorpoVentoDinamico) => {
      await encadear(() => enviarVentoDinamico(corpo))
      await pollAgora()
    },
    [encadear, pollAgora]
  )

  /**
   * `POST /api/camera` (contrato v2) — comando de câmara SEM `alvo` nem `seq` (o `seq` é do
   * servidor). Os comandos do widget (throttle + commit final no bloco «Câmara») passam aqui só
   * pela ORDEM das escritas (fila, como os restantes controlos) e por uma releitura imediata do
   * `/api/sim`, para o ecrã adotar o valor confirmado sem esperar o próximo ciclo do polling.
   */
  const aplicarCamera = useCallback(
    async (corpo: CorpoCamera) => {
      await encadear(() => enviarCamera(corpo))
      await pollAgora()
    },
    [encadear, pollAgora]
  )

  /**
   * `POST /api/bateria` (planta real) — pela fila, como os restantes controlos (a ordem dos cliques é a
   * ordem das escritas no controlo), e com releitura imediata do `/api/sim`. Uma falha da releitura não
   * desmente o POST que já foi aceite: o resultado do servidor devolve-se na mesma.
   */
  const aplicarBateria = useCallback(
    async (acao: AcaoBateria) => {
      const resposta = await encadear(() => enviarBateria(acao))
      await pollAgora().catch(() => undefined)
      return resposta
    },
    [encadear, pollAgora]
  )

  return {
    linhas,
    ultima,
    estado: cabecalho.estado,
    ep: cabecalho.ep,
    passo: cabecalho.passo,
    retorno: cabecalho.retorno,
    vento: cabecalho.vento,
    ventoDinamico: cabecalho.ventoDinamico,
    rpi5: cabecalho.rpi5,
    camera: cabecalho.camera,
    cameraPadrao: cabecalho.cameraPadrao,
    loop: cabecalho.loop ?? resumo?.loop ?? null,
    planta: cabecalho.planta ?? resumo?.planta ?? null,
    resumo,
    ligacao,
    erro,
    atualizadoEm,
    respostas,
    reiniciar,
    aplicarVento,
    pararTudo,
    aplicarVentoDinamico,
    aplicarCamera,
    aplicarBateria,
    definirLoop,
    atualizar: pollAgora,
  }
}
