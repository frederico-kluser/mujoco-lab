/**
 * JANELA flutuante do cockpit — vidro escuro translúcido sobre a vista (que continua a ver-se):
 *  · arrasta-se pela barra de título; fecha-se no × (ou `Esc` com ela à frente);
 *  · um clique em qualquer sítio dela trá-la para a frente;
 *  · fica SEMPRE dentro do viewport: a posição desenhada é a guardada passada por `encaixar` — ao
 *    redimensionar o browser (ou ao abrir num ecrã mais pequeno) a janela re-encaixa sozinha;
 *  · a altura nunca passa do espaço entre a barra de estado e a doca: o corpo das janelas de detalhe
 *    ganha scroll INTERNO (a página nunca faz scroll).
 *
 * Arrasto sem re-render: durante o gesto escreve-se o `transform` diretamente no elemento; só ao
 * largar é que a posição entra no estado (e no `localStorage`).
 */

import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as EventoPonteiro,
  type ReactNode,
} from "react"
import { X } from "lucide-react"

import { Atalho, FOCO } from "@/components/cockpit/pecas"
import {
  MARGEM_JANELA,
  alturaMaximaJanela,
  encaixar,
  type IdJanela,
  type Ponto,
  type Tamanho,
} from "@/lib/cockpit"

export interface JanelaProps {
  id: IdJanela
  titulo: string
  /** Atalho que a abre/fecha (mostrado na barra de título). */
  tecla: string
  icone: ReactNode
  largura: number
  /** Altura aproximada antes de se medir (só para o primeiro encaixe). */
  alturaPrevista: number
  /** Onde o dono a deixou (ou a posição inicial). */
  posicao: Ponto
  viewport: Tamanho
  /** Ordem de empilhamento (a maior fica à frente). */
  ordem: number
  emFoco: boolean
  onFocar: (id: IdJanela) => void
  onFechar: (id: IdJanela) => void
  onMover: (id: IdJanela, ponto: Ponto) => void
  children: ReactNode
}

function translacao(ponto: Ponto): string {
  return `translate3d(${ponto.x}px, ${ponto.y}px, 0)`
}

export function Janela({
  id,
  titulo,
  tecla,
  icone,
  largura,
  alturaPrevista,
  posicao,
  viewport,
  ordem,
  emFoco,
  onFocar,
  onFechar,
  onMover,
  children,
}: JanelaProps) {
  const raiz = useRef<HTMLElement>(null)
  const [medido, setMedido] = useState<Tamanho | null>(null)
  const larguraReal = Math.min(largura, viewport.largura - 2 * MARGEM_JANELA)
  const tamanho: Tamanho = medido ?? {
    largura: larguraReal,
    altura: Math.min(alturaPrevista, alturaMaximaJanela(viewport)),
  }
  const encaixada = encaixar(posicao, tamanho, viewport)

  // O tamanho REAL (o conteúdo decide a altura) — medido quando muda, nunca por quadro.
  useEffect(() => {
    const el = raiz.current
    if (el === null || typeof ResizeObserver === "undefined") return
    const observador = new ResizeObserver(() => {
      setMedido((anterior) => {
        const novo = { largura: el.offsetWidth, altura: el.offsetHeight }
        return anterior !== null &&
          anterior.largura === novo.largura &&
          anterior.altura === novo.altura
          ? anterior
          : novo
      })
    })
    observador.observe(el)
    return () => observador.disconnect()
  }, [])

  /** Gesto de arrasto em curso: de onde partiu o ponteiro e a janela, e onde vai. */
  const arrasto = useRef<{
    ponteiro: number
    x0: number
    y0: number
    origem: Ponto
    atual: Ponto
  } | null>(null)

  const aoBaixar = (evento: EventoPonteiro<HTMLElement>) => {
    if (evento.button !== 0) return
    // O × e qualquer controlo na barra não iniciam arrasto.
    if ((evento.target as HTMLElement).closest("button") !== null) return
    evento.currentTarget.setPointerCapture(evento.pointerId)
    arrasto.current = {
      ponteiro: evento.pointerId,
      x0: evento.clientX,
      y0: evento.clientY,
      origem: encaixada,
      atual: encaixada,
    }
  }

  const aoMover = (evento: EventoPonteiro<HTMLElement>) => {
    const a = arrasto.current
    if (a === null || a.ponteiro !== evento.pointerId) return
    a.atual = encaixar(
      {
        x: a.origem.x + evento.clientX - a.x0,
        y: a.origem.y + evento.clientY - a.y0,
      },
      tamanho,
      viewport
    )
    if (raiz.current !== null) raiz.current.style.transform = translacao(a.atual)
  }

  const aoLargar = (evento: EventoPonteiro<HTMLElement>) => {
    const a = arrasto.current
    if (a === null || a.ponteiro !== evento.pointerId) return
    arrasto.current = null
    onMover(id, a.atual)
  }

  return (
    <section
      ref={raiz}
      role="dialog"
      aria-label={titulo}
      data-testid={`janela-${id}`}
      data-foco={emFoco ? "sim" : "nao"}
      onPointerDownCapture={() => onFocar(id)}
      className="pointer-events-auto absolute top-0 left-0 will-change-transform"
      style={{
        width: larguraReal,
        zIndex: 30 + ordem,
        transform: translacao(encaixada),
      }}
    >
      <div
        className={`vidro janela-entra flex flex-col overflow-hidden rounded-2xl ${emFoco ? "border-white/30" : ""}`}
        style={{ maxHeight: alturaMaximaJanela(viewport) }}
      >
        <header
          data-testid={`janela-${id}-barra`}
          onPointerDown={aoBaixar}
          onPointerMove={aoMover}
          onPointerUp={aoLargar}
          onPointerCancel={aoLargar}
          className="flex h-10 shrink-0 cursor-grab touch-none items-center gap-2 border-b border-white/10 pr-1.5 pl-3 select-none active:cursor-grabbing"
        >
          <span className="text-hud [&_svg]:size-4" aria-hidden="true">
            {icone}
          </span>
          <h2 className="flex-1 truncate text-[0.8rem] font-bold tracking-[0.14em] text-hud uppercase">
            {titulo}
          </h2>
          <Atalho>{tecla}</Atalho>
          <button
            type="button"
            onClick={() => onFechar(id)}
            data-testid={`janela-${id}-fechar`}
            aria-label={`fechar a janela ${titulo}`}
            title="fechar (Esc)"
            className={`flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-white/12 hover:text-hud ${FOCO}`}
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>
        <div className="corpo-janela min-h-0 flex-1 overflow-x-hidden overflow-y-auto p-3">
          {children}
        </div>
      </div>
    </section>
  )
}
