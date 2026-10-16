/**
 * Os CONTROLOS do cockpit ligados à API — uma instância de cada, de módulo (como o `hud`):
 * o PILOTO (`POST /api/voo`), o VENTO de três botões (`POST /api/vento-simples`), a BOLA
 * (`POST /api/bola`) e a CÂMARA da 3.ª pessoa (`POST /api/camera`).
 *
 * Vivem fora do React porque quem lhes mexe são eventos (teclado, ponteiro, a sondagem de 1 Hz) e
 * não renders: o teclado escreve no estado e o POST sai no mesmo instante, sem passar por um efeito.
 * Os componentes leem-nos com `useSyncExternalStore` (`hooks/use-cockpit.ts`). A lógica é toda de
 * `lib/cockpit.ts` (pura, testada); aqui só se liga ao `fetch` e aos avisos.
 */

import {
  enviarBola,
  enviarCamera,
  enviarTiro,
  enviarVentoSimples,
  enviarVoo,
  lerCameraEmVigor,
} from "./api.ts"
import { MaquinaCamera, limitesDistancia } from "./camera-gestos.ts"
import {
  ControloBola,
  ControloPiloto,
  ControloTiro,
  ControloVento,
  Emissor,
} from "./cockpit.ts"
import type { CameraEstado, CorpoCamera, Planta } from "./sim.ts"

type Avisador = (texto: string, tom: "ok" | "erro" | "info") => void

let avisador: Avisador | null = null
/** O `App` liga aqui os toasts; `null` ao desmontar. */
export function ligarAvisos(novo: Avisador | null): void {
  avisador = novo
}

/** O MESMO erro não se repete durante este tempo (arrastar com a API em baixo não empilha 20 toasts). */
const SILENCIO_ERRO_MS = 4000
const ultimoErro = new Map<string, number>()

function avisarErro(rota: string, erro: unknown): void {
  const motivo = erro instanceof Error ? erro.message : "falha desconhecida"
  const texto = `${rota} não foi aceite — ${motivo}`
  const agora = Date.now()
  if (agora - (ultimoErro.get(texto) ?? 0) < SILENCIO_ERRO_MS) return
  ultimoErro.set(texto, agora)
  avisador?.(texto, "erro")
}

export const piloto = new ControloPiloto({
  enviar: enviarVoo,
  aoFalhar: (erro) => avisarErro("POST /api/voo", erro),
})

export const vento = new ControloVento({
  enviar: enviarVentoSimples,
  aoFalhar: (erro) => avisarErro("POST /api/vento-simples", erro),
})

export const bola = new ControloBola({
  enviar: enviarBola,
  aoFalhar: (erro) => avisarErro("POST /api/bola", erro),
})

export const tiro = new ControloTiro({
  enviar: enviarTiro,
  aoFalhar: (erro) => avisarErro("POST /api/tiro", erro),
})

// --------------------------------------------------------------------------------- câmara (3.ª pessoa)

let planta: Planta | null = null
let apiLigada = false

/** A planta decide a faixa do zoom (um drone de 1,95 m não cabe a 0,1 m da câmara). */
export function definirPlantaDaCamera(nova: Planta | null): void {
  planta = nova
}

/** Sem API não se dispara envio nenhum (a máquina de gestos di-lo em vez de falhar 20×/s). */
export function definirApiLigada(ligada: boolean): void {
  apiLigada = ligada
}

interface EnvioCamera {
  corpo: CorpoCamera
  resolver: () => void
  rejeitar: (erro: unknown) => void
}

/**
 * Os comandos de câmara em «o último vence»: a máquina de gestos dispara até ~20 por segundo e o
 * servidor honra a última escrita — dois POSTs em voo podiam chegar trocados e a vista saltava para
 * trás. Um comando ultrapassado dá-se por entregue (o seguinte leva os valores mais recentes).
 */
const filaCamera = new Emissor<EnvioCamera, void>({
  enviar: async ({ corpo, resolver, rejeitar }) => {
    try {
      const confirmada = await enviarCamera(corpo)
      resolver()
      // Sem janela nativa a única confirmação é a resposta do próprio POST.
      if (confirmada !== null) camera.receberCamera(confirmada)
    } catch (erro) {
      rejeitar(erro)
    }
  },
  fundir: (pendente, novo) => {
    pendente.resolver()
    return novo
  },
})

/**
 * A câmara da SIMULAÇÃO (a vista em 3.ª pessoa): a máquina de gestos de `lib/camera-gestos.ts` — os
 * valores enviados são sempre os do gesto, com envio final ao largar — a ~20 envios/s no máximo.
 */
export const camera: MaquinaCamera = new MaquinaCamera({
  enviar: (corpo) =>
    new Promise<void>((resolver, rejeitar) => {
      filaCamera.largar({ corpo, resolver, rejeitar })
    }),
  aoMostrar: () => undefined,
  aoFase: () => undefined,
  aoAvisar: (texto) => {
    const agora = Date.now()
    if (agora - (ultimoErro.get(texto) ?? 0) < SILENCIO_ERRO_MS) return
    ultimoErro.set(texto, agora)
    avisador?.(texto, "erro")
  },
  ligado: () => apiLigada,
  atrasoMs: 50,
  limitesDistancia: () => limitesDistancia(planta),
})

let cameraPedida = false

/**
 * Lê UMA vez onde está a câmara da simulação (`POST /api/camera {}` — o «toque» do contrato v2).
 * Sem janela nativa o `/api/state` publica `camera_atual: null`, e sem este valor o primeiro arrasto
 * partia de uma pose inventada (a vista saltava). Se o toque falhar fica a pose de omissão
 * (`camera_padrao`) — é a que o runner aplica quando ninguém mexeu na câmara.
 */
export async function carregarCameraEmVigor(
  padrao: CameraEstado | null
): Promise<void> {
  if (cameraPedida) return
  cameraPedida = true
  try {
    const emVigor = (await lerCameraEmVigor()) ?? padrao
    if (emVigor !== null && camera.valores === null) camera.receberCamera(emVigor)
  } catch {
    if (padrao !== null && camera.valores === null) camera.receberCamera(padrao)
    cameraPedida = false // volta-se a tentar quando a API responder
  }
}
