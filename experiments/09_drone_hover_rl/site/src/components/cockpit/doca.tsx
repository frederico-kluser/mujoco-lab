/**
 * DOCA — a barra de ícones (em baixo, ao centro) que abre e fecha as janelas, mais o REINICIAR.
 *
 * Cada botão é um ícone COM O NOME por baixo e o número do atalho no canto: reconhece-se sem passar o
 * rato (a revisão de UX de 2026-10-12 mediu a doca só de ícones como o ponto menos óbvio do ecrã). Uma
 * janela ABERTA diz-se com forma — fundo cheio e uma barra por baixo —, não só com cor. Alvos de
 * 52 × 48 px; a doca inteira cabe entre a miniatura e o vento a 1280 px de largura.
 *
 * REINICIAR é de manter premido (o gesto `hold-to-confirm` do Motion UI): um clique acidental a meio
 * de um voo não devolve o drone ao chão. A tecla R faz o mesmo gesto — o `App` chama `iniciar`/
 * `cancelar` pelo `ref` — e o enchimento do botão mostra o progresso nos dois casos.
 */

import {
  useImperativeHandle,
  type KeyboardEvent as EventoTecla,
  type ReactNode,
  type Ref,
} from "react"
import { motion, useTransform } from "motion/react"
import {
  ChartLine,
  Cpu,
  Crosshair,
  Drone,
  Gauge,
  Keyboard,
  RotateCcw,
  Wind,
  Zap,
} from "lucide-react"

import { Atalho, FOCO } from "@/components/cockpit/pecas"
import { useHoldToConfirm } from "@/components/motion-ui/hold-to-confirm"
import { JANELAS, type IdJanela } from "@/lib/cockpit"

/** O ícone de cada janela (o mesmo na doca e na barra de título). */
export const ICONE_JANELA: Record<IdJanela, ReactNode> = {
  voo: <Drone />,
  bola: <Crosshair />,
  vento: <Wind />,
  instrumentos: <Gauge />,
  energia: <Zap />,
  graficos: <ChartLine />,
  sistema: <Cpu />,
  ajuda: <Keyboard />,
}

/** Segundos a manter para reiniciar (curto para não cansar, longo para não ser um toque). */
export const SEGUNDOS_REINICIAR = 0.9

/** O que o `App` usa para a tecla R conduzir o mesmo gesto do botão. */
export interface GestoReiniciar {
  iniciar: () => void
  cancelar: () => void
}

/** Evento mínimo para conduzir o gesto do `hold-to-confirm` pela tecla R (ele só olha para isto). */
function teclaEspaco(): EventoTecla<HTMLButtonElement> {
  return {
    key: " ",
    repeat: false,
    preventDefault: () => undefined,
  } as unknown as EventoTecla<HTMLButtonElement>
}

function BotaoReiniciar({
  onReiniciar,
  desativado,
  gesto,
}: {
  onReiniciar: () => void
  desativado: boolean
  gesto: Ref<GestoReiniciar>
}) {
  const { progress, reset, holdHandlers } = useHoldToConfirm({
    holdSeconds: SEGUNDOS_REINICIAR,
    onConfirm: () => {
      onReiniciar()
      // O gesto é de um disparo: rearma-se logo, para o próximo REINICIAR não precisar de remontar nada.
      window.setTimeout(reset, 350)
    },
  })
  useImperativeHandle(
    gesto,
    () => ({
      iniciar: () => holdHandlers.onKeyDown(teclaEspaco()),
      cancelar: () => holdHandlers.onKeyUp(teclaEspaco()),
    }),
    [holdHandlers]
  )
  const enchimento = useTransform(progress, [0, 1], [0, 1])
  return (
    <span className="group relative flex">
      <button
        type="button"
        data-testid="botao-reiniciar"
        disabled={desativado}
        aria-label="reiniciar: manter premido (ou manter a tecla R)"
        className={`relative flex h-12 items-center gap-2 overflow-hidden rounded-xl border border-hud-ambar/55 bg-hud-ambar/10 px-3 text-hud transition-colors select-none hover:bg-hud-ambar/20 disabled:cursor-not-allowed disabled:opacity-45 ${FOCO}`}
        {...holdHandlers}
      >
        <motion.span
          aria-hidden="true"
          data-testid="reiniciar-progresso"
          className="absolute inset-0 origin-left bg-hud-ambar/55"
          style={{ scaleX: enchimento }}
        />
        <RotateCcw className="relative size-4" aria-hidden="true" />
        <span className="relative text-[0.72rem] font-bold tracking-[0.12em]">
          REINICIAR
        </span>
        <span className="relative">
          <Atalho>R</Atalho>
        </span>
      </button>
      <Dica>manter premido · volta ao chão e descola</Dica>
    </span>
  )
}

/** Dica por cima do botão (rato ou foco). `pointer-events: none`: nunca tapa um clique. */
function Dica({ children }: { children: ReactNode }) {
  return (
    <span
      role="tooltip"
      className="vidro pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 rounded-lg px-2.5 py-1.5 text-[0.7rem] whitespace-nowrap text-hud opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100"
    >
      {children}
    </span>
  )
}

export interface DocaProps {
  abertas: readonly IdJanela[]
  onAlternar: (id: IdJanela) => void
  onReiniciar: () => void
  /** Sem ligação à API o REINICIAR não tem a quem pedir. */
  podeReiniciar: boolean
  gestoReiniciar: Ref<GestoReiniciar>
}

export function Doca({
  abertas,
  onAlternar,
  onReiniciar,
  podeReiniciar,
  gestoReiniciar,
}: DocaProps) {
  return (
    <nav
      aria-label="janelas do cockpit"
      data-testid="doca"
      className="vidro pointer-events-auto absolute bottom-3 left-1/2 z-20 flex -translate-x-1/2 items-center gap-1 rounded-2xl p-1.5"
    >
      {JANELAS.map((janela) => {
        const aberta = abertas.includes(janela.id)
        return (
          <span key={janela.id} className="group relative flex">
            <button
              type="button"
              data-testid={`doca-${janela.id}`}
              data-aberta={aberta ? "sim" : "nao"}
              aria-pressed={aberta}
              aria-label={`${janela.titulo} (tecla ${janela.tecla})`}
              onClick={() => onAlternar(janela.id)}
              className={`relative flex h-12 w-[3.25rem] flex-col items-center justify-center gap-0.5 rounded-xl transition-colors [&_svg]:size-[1.1rem] ${FOCO} ${
                aberta
                  ? "bg-white/20 text-hud"
                  : "text-hud/80 hover:bg-white/12 hover:text-hud"
              }`}
            >
              {ICONE_JANELA[janela.id]}
              <span
                data-testid={`doca-${janela.id}-rotulo`}
                className="text-[0.625rem] leading-none font-bold"
              >
                {janela.titulo}
              </span>
              <span
                aria-hidden="true"
                className="absolute top-0.5 right-1 font-etiqueta text-[0.625rem] font-bold text-hud/70"
              >
                {janela.tecla}
              </span>
              {aberta ? (
                <span
                  aria-hidden="true"
                  className="absolute bottom-0 left-1/2 h-0.5 w-5 -translate-x-1/2 rounded-full bg-hud"
                />
              ) : null}
            </button>
          </span>
        )
      })}
      <span aria-hidden="true" className="mx-1 h-6 w-px bg-white/18" />
      <BotaoReiniciar
        onReiniciar={onReiniciar}
        desativado={!podeReiniciar}
        gesto={gestoReiniciar}
      />
    </nav>
  )
}
