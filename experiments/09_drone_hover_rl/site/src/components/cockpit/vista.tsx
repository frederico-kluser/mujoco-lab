/**
 * VISTA — o fundo permanente do cockpit: o stream MJPEG da câmara de bordo (1.ª pessoa,
 * `GET /api/fpv.mjpg`) ou da simulação (3.ª pessoa, `GET /api/simulacao.mjpg`) num `<img>` que cobre
 * o viewport (`object-fit: cover`). É o maior elemento do ecrã em todos os estados.
 *
 *  · A OUTRA vista vive numa MINIATURA em baixo à esquerda (a convenção das estações de solo): um
 *    clique nela troca as duas. É alimentada pelos `.jpg` (o último quadro) a ~4 fps e NÃO por um
 *    segundo MJPEG — o HTTP/1.1 só dá 6 ligações por origem e já há um stream e o SSE do HUD abertos.
 *  · Em 3.ª pessoa a própria vista é o comando da câmara: arrastar orbita, a roda aproxima/afasta e o
 *    duplo clique repõe (`POST /api/camera`, ≤ 20 envios/s + envio final — `lib/cockpit-controlos.ts`).
 *  · SEM IMAGEM diz-se, com o motivo e o que fazer — nunca um ecrã preto mudo. Um `<img>` MJPEG não
 *    avisa quando os quadros param, por isso a prova de vida é o estado do módulo no `/api/state`
 *    (`estado_velho`, `ligada`) e o `error` do próprio elemento (o stream religa sozinho).
 *  · Com a página escondida os streams FECHAM (o `<img>` desmonta) e reabrem ao voltar.
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as EventoPonteiro,
  type WheelEvent as EventoRoda,
} from "react"
import { ArrowLeftRight, PictureInPicture2, VideoOff, X } from "lucide-react"

import { Atalho, FOCO } from "@/components/cockpit/pecas"
import type { Vista as QualVista } from "@/hooks/use-cockpit"
import { urlApi } from "@/lib/api"
import { distanciaPorRoda, fmtHud, orbitarPorArrasto } from "@/lib/cockpit"
import { camera } from "@/lib/cockpit-controlos"
import type { CameraEstado, FpvEstado } from "@/lib/sim"

/** 1×1 transparente: trocar o `src` por isto é a forma fiável de o browser largar a ligação do stream. */
const VAZIO =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

const ROTAS: Record<QualVista, { stream: string; quadro: string }> = {
  fpv: { stream: "/api/fpv.mjpg", quadro: "/api/fpv.jpg" },
  terceira: { stream: "/api/simulacao.mjpg", quadro: "/api/simulacao.jpg" },
}

export const NOME_VISTA: Record<QualVista, string> = {
  fpv: "1.ª PESSOA",
  terceira: "3.ª PESSOA",
}

/** Período da miniatura (ms): ~4 quadros por segundo. */
const PERIODO_MINIATURA_MS = 250
/** Espera antes de reabrir um stream que deu erro. */
const RELIGAR_STREAM_MS = 2000

/**
 * O `<img>` do stream. Monta = abre a ligação; desmonta = fecha-a (o `key` de quem o usa muda com a
 * vista e com cada nova tentativa, logo o estado «já tem quadro / deu erro» nasce limpo de cada vez).
 */
function Stream({
  rota,
  onErro,
  onQuadro,
}: {
  rota: string
  onErro: () => void
  onQuadro: () => void
}) {
  const img = useRef<HTMLImageElement>(null)
  useEffect(() => {
    const el = img.current
    if (el === null) return
    el.src = urlApi(rota)
    // Nem todos os browsers disparam `load` no 1.º quadro de um multipart: confirma-se pela imagem.
    const sonda = window.setInterval(() => {
      if (el.naturalWidth > 1) {
        window.clearInterval(sonda)
        onQuadro()
      }
    }, 300)
    return () => {
      window.clearInterval(sonda)
      el.src = VAZIO
    }
  }, [rota, onQuadro])
  return (
    <img
      ref={img}
      alt=""
      draggable={false}
      data-testid="vista-imagem"
      onError={onErro}
      className="pointer-events-none absolute inset-0 size-full object-cover select-none"
    />
  )
}

/** A miniatura: o último quadro da OUTRA vista, pedido de novo quando o anterior já chegou. */
function Miniatura({ rota }: { rota: string }) {
  const img = useRef<HTMLImageElement>(null)
  const [temQuadro, setTemQuadro] = useState(false)
  useEffect(() => {
    let vivo = true
    let temporizador = 0
    let urlAnterior: string | null = null
    const controlador = new AbortController()
    const ciclo = async () => {
      try {
        const resposta = await fetch(urlApi(rota), {
          cache: "no-store",
          signal: controlador.signal,
        })
        if (!vivo) return
        if (resposta.ok) {
          const url = URL.createObjectURL(await resposta.blob())
          if (!vivo || img.current === null) {
            URL.revokeObjectURL(url)
            return
          }
          img.current.src = url
          if (urlAnterior !== null) URL.revokeObjectURL(urlAnterior)
          urlAnterior = url
          setTemQuadro(true)
        } else {
          setTemQuadro(false) // 404 = o módulo ainda não tem quadro nenhum
        }
      } catch {
        if (vivo) setTemQuadro(false)
      } finally {
        if (vivo) temporizador = window.setTimeout(ciclo, PERIODO_MINIATURA_MS)
      }
    }
    void ciclo()
    return () => {
      vivo = false
      window.clearTimeout(temporizador)
      controlador.abort()
      if (urlAnterior !== null) URL.revokeObjectURL(urlAnterior)
    }
  }, [rota])
  return (
    <>
      <img
        ref={img}
        alt=""
        draggable={false}
        data-testid="miniatura-imagem"
        className={`size-full object-cover ${temQuadro ? "" : "opacity-0"}`}
      />
      {temQuadro ? null : (
        <span className="absolute inset-0 flex items-center justify-center text-[0.65rem] text-muted-foreground">
          sem imagem
        </span>
      )}
    </>
  )
}

/** Porque é que não há imagem — e o que o dono pode fazer (se puder). */
interface MotivoSemImagem {
  titulo: string
  texto: string
  acao?: "ligar_camara"
}

function motivoSemImagem(entrada: {
  apiLigada: boolean
  /** O `/api/state` já respondeu? Antes disso não se sabe se há câmara: só se espera. */
  conhecido: boolean
  modulo: FpvEstado | null
  vista: QualVista
  erro: boolean
  temQuadro: boolean
}): MotivoSemImagem | null {
  const { apiLigada, conhecido, modulo, vista, erro, temQuadro } = entrada
  const aAbrir: MotivoSemImagem = {
    titulo: "A ABRIR A CÂMARA",
    texto: "À espera do primeiro quadro…",
  }
  if (!apiLigada)
    return {
      titulo: "SEM LIGAÇÃO AO SIMULADOR",
      texto:
        "O simulador não responde. A página volta a ligar sozinha quando ele arrancar.",
    }
  if (!conhecido) return temQuadro ? null : aAbrir
  if (modulo === null)
    return {
      titulo: "SEM CÂMARA",
      texto:
        vista === "fpv"
          ? "O simulador está a correr sem a câmara de bordo. Troca para a 3.ª pessoa (F) ou arranca-o sem --sem-fpv."
          : "O simulador não publica a vista da simulação.",
    }
  if (modulo.ligada === false)
    return {
      titulo: "CÂMARA DESLIGADA",
      texto: "A câmara foi desligada: não chegam quadros novos.",
      acao: "ligar_camara",
    }
  if (modulo.estadoVelho === true)
    return {
      titulo: "SEM IMAGEM",
      texto: `A câmara deixou de enviar quadros${
        modulo.idadeEstadoS === null
          ? ""
          : ` há ${fmtHud(modulo.idadeEstadoS, 0)} s`
      }. O simulador pode ter parado.`,
    }
  if (erro)
    return {
      titulo: "SEM IMAGEM",
      texto: "O stream caiu. A religar…",
    }
  return temQuadro ? null : aAbrir
}

export interface VistaProps {
  vista: QualVista
  miniaturaAberta: boolean
  /** A página está visível? (escondida ⇒ streams fechados) */
  visivel: boolean
  apiLigada: boolean
  /** O `/api/state` já respondeu (sabe-se que módulos de imagem existem)? */
  estadoConhecido: boolean
  /** Estado dos dois módulos de imagem (`fpv` e `simulacao` do `/api/state`). */
  fpv: FpvEstado | null
  simulacao: FpvEstado | null
  /** Para onde o duplo clique repõe a câmara da 3.ª pessoa. */
  cameraPadrao: CameraEstado | null
  onTrocar: () => void
  onMiniatura: (aberta: boolean) => void
  onLigarCamara: () => void
  /** Há imagem na vista? (sem ela o HUD esconde o que assenta na imagem: horizonte, mira, retículo) */
  onImagem: (tem: boolean) => void
}

export function Vista({
  vista,
  miniaturaAberta,
  visivel,
  apiLigada,
  estadoConhecido,
  fpv,
  simulacao,
  cameraPadrao,
  onTrocar,
  onMiniatura,
  onLigarCamara,
  onImagem,
}: VistaProps) {
  const outra: QualVista = vista === "fpv" ? "terceira" : "fpv"
  const modulo = vista === "fpv" ? fpv : simulacao

  // ------------------------------------------------------------- stream: tentativas e prova de vida
  /** Cada erro do `<img>` abre uma tentativa nova (o `key` muda ⇒ o elemento é outro, limpo). */
  const [tentativa, setTentativa] = useState(0)
  /** De que stream (`vista:tentativa`) são o «tem quadro» e o «deu erro» — outro stream = estado limpo. */
  const chave = `${vista}:${tentativa}`
  const [estadoStream, setEstadoStream] = useState<{
    chave: string
    temQuadro: boolean
    erro: boolean
  }>({ chave, temQuadro: false, erro: false })
  const temQuadro = estadoStream.chave === chave && estadoStream.temQuadro
  const erro = estadoStream.chave === chave && estadoStream.erro

  const aoQuadro = useCallback(
    () => setEstadoStream({ chave, temQuadro: true, erro: false }),
    [chave]
  )
  const religar = useRef(0)
  const aoErro = useCallback(() => {
    setEstadoStream({ chave, temQuadro: false, erro: true })
    window.clearTimeout(religar.current)
    religar.current = window.setTimeout(
      () => setTentativa((n) => n + 1),
      RELIGAR_STREAM_MS
    )
  }, [chave])
  useEffect(() => () => window.clearTimeout(religar.current), [])

  const semImagem = motivoSemImagem({
    apiLigada,
    conhecido: estadoConhecido,
    modulo,
    vista,
    erro,
    temQuadro,
  })

  const temImagem = semImagem === null
  useEffect(() => {
    onImagem(temImagem)
  }, [onImagem, temImagem])

  // ------------------------------------------------------------- 3.ª pessoa: arrastar = orbitar
  const gesto = useRef<{
    ponteiro: number
    x0: number
    y0: number
    azimute: number
    elevacao: number
  } | null>(null)
  const [aOrbitar, setAOrbitar] = useState(false)
  const orbitavel = vista === "terceira"

  const aoBaixar = (evento: EventoPonteiro<HTMLDivElement>) => {
    if (!orbitavel || evento.button !== 0) return
    const valores = camera.valores
    if (valores === null) return // ainda não se sabe onde a câmara está: não se parte de uma pose inventada
    evento.currentTarget.setPointerCapture(evento.pointerId)
    gesto.current = {
      ponteiro: evento.pointerId,
      x0: evento.clientX,
      y0: evento.clientY,
      azimute: valores.azimute,
      elevacao: valores.elevacao,
    }
    camera.comecarArrasto()
    setAOrbitar(true)
  }

  const aoMover = (evento: EventoPonteiro<HTMLDivElement>) => {
    const g = gesto.current
    if (g === null || g.ponteiro !== evento.pointerId) return
    const novo = orbitarPorArrasto(
      g,
      evento.clientX - g.x0,
      evento.clientY - g.y0,
      evento.currentTarget.clientHeight
    )
    camera.editarAngulos(novo.azimute, novo.elevacao)
  }

  const aoLargar = (evento: EventoPonteiro<HTMLDivElement>) => {
    const g = gesto.current
    if (g === null || g.ponteiro !== evento.pointerId) return
    gesto.current = null
    camera.terminarGesto() // envio final com os valores onde o gesto acabou
    setAOrbitar(false)
  }

  const aoRodar = (evento: EventoRoda<HTMLDivElement>) => {
    if (!orbitavel) return
    const valores = camera.valores
    if (valores === null) return
    // A faixa é a da planta: a máquina de gestos corta o valor nos limites que conhece.
    camera.editarDistancia(
      distanciaPorRoda(valores.distancia, evento.deltaY, [0.05, 20])
    )
  }

  const aoDuploClique = () => {
    if (orbitavel) camera.reporVista(cameraPadrao)
  }

  return (
    <>
      <div
        data-testid="vista"
        data-vista={vista}
        data-imagem={semImagem === null ? "sim" : "nao"}
        onPointerDown={aoBaixar}
        onPointerMove={aoMover}
        onPointerUp={aoLargar}
        onPointerCancel={aoLargar}
        onWheel={aoRodar}
        onDoubleClick={aoDuploClique}
        className={`absolute inset-0 touch-none overflow-hidden bg-background ${
          orbitavel ? (aOrbitar ? "cursor-grabbing" : "cursor-grab") : ""
        }`}
      >
        {visivel ? (
          <Stream
            key={chave}
            rota={ROTAS[vista].stream}
            onErro={aoErro}
            onQuadro={aoQuadro}
          />
        ) : null}
        {semImagem !== null ? (
          <div
            data-testid="sem-imagem"
            className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background/88 px-6 text-center"
          >
            <VideoOff className="size-9 text-hud-ambar" aria-hidden="true" />
            <p className="font-etiqueta text-lg font-bold tracking-[0.18em] text-hud-ambar">
              {semImagem.titulo}
            </p>
            <p className="max-w-md text-sm text-muted-foreground">
              {semImagem.texto}
            </p>
            {semImagem.acao === "ligar_camara" ? (
              <button
                type="button"
                data-testid="ligar-camara"
                onClick={onLigarCamara}
                onPointerDown={(evento) => evento.stopPropagation()}
                className={`rounded-xl border border-hud-ciano/60 bg-hud-ciano/15 px-4 py-2 text-sm font-bold tracking-wide text-hud hover:bg-hud-ciano/25 ${FOCO}`}
              >
                LIGAR A CÂMARA
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* Miniatura + troca de vista: em baixo à esquerda. */}
      <div className="pointer-events-none absolute bottom-3 left-3 z-20 flex flex-col items-start gap-1.5">
        {miniaturaAberta ? (
          <div className="pointer-events-auto relative">
            <button
              type="button"
              data-testid="miniatura"
              onClick={onTrocar}
              aria-label={`trocar para a ${NOME_VISTA[outra].toLowerCase()} (tecla F)`}
              title={`ver em ${NOME_VISTA[outra].toLowerCase()} (F)`}
              className={`vidro relative block aspect-video w-[clamp(11.5rem,15vw,18rem)] overflow-hidden rounded-xl p-0 ${FOCO}`}
            >
              {visivel && apiLigada ? (
                <Miniatura key={outra} rota={ROTAS[outra].quadro} />
              ) : null}
              <span className="osd absolute bottom-1.5 left-2 text-[0.65rem] font-bold tracking-[0.14em]">
                {NOME_VISTA[outra]}
              </span>
            </button>
            <button
              type="button"
              data-testid="miniatura-fechar"
              onClick={() => onMiniatura(false)}
              aria-label="fechar a miniatura"
              title="fechar a miniatura"
              className={`absolute top-0 right-0 flex size-8 items-center justify-center rounded-tr-xl rounded-bl-xl bg-black/55 text-hud/80 hover:bg-black/80 hover:text-hud ${FOCO}`}
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </div>
        ) : null}
        <div className="pointer-events-auto flex items-center gap-1.5">
          <button
            type="button"
            data-testid="trocar-vista"
            onClick={onTrocar}
            aria-label={`vista em ${NOME_VISTA[vista].toLowerCase()}: trocar para a ${NOME_VISTA[outra].toLowerCase()} (tecla F)`}
            className={`vidro flex h-8 items-center gap-2 rounded-lg px-2.5 text-[0.68rem] font-bold tracking-[0.12em] text-hud hover:border-white/35 ${FOCO}`}
          >
            <ArrowLeftRight className="size-3.5" aria-hidden="true" />
            <span data-testid="vista-nome">{NOME_VISTA[vista]}</span>
            <Atalho>F</Atalho>
          </button>
          {miniaturaAberta ? null : (
            <button
              type="button"
              data-testid="miniatura-abrir"
              onClick={() => onMiniatura(true)}
              aria-label="mostrar a miniatura da outra vista"
              title="mostrar a miniatura da outra vista"
              className={`vidro flex size-8 items-center justify-center rounded-lg text-hud hover:border-white/35 ${FOCO}`}
            >
              <PictureInPicture2 className="size-3.5" aria-hidden="true" />
            </button>
          )}
          {orbitavel ? (
            <span className="osd text-[0.65rem]" data-testid="dica-orbitar">
              arrastar orbita · roda aproxima · duplo clique repõe
            </span>
          ) : null}
        </div>
      </div>
    </>
  )
}
