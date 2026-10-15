/**
 * PEÇAS do cockpit — os controlos pequenos que as janelas partilham: interruptor, deslizador, tecla e
 * a marca de estado. Regras comuns:
 *  · nenhum estado se diz SÓ com cor: um interruptor escreve LIGADO/DESLIGADO, uma tecla premida fica
 *    cheia (invertida), uma marca tem FORMA (● ativo · ○ normal · ▲ atenção · ■ perigo);
 *  · alvos de clique ≥ 32 px;
 *  · o teclado de voo nunca fica preso: um deslizador é um `input[type=range]` (não é campo de texto,
 *    logo o W continua a voar com o foco nele).
 */

import { useRef, type CSSProperties, type ReactNode } from "react"

import type { TomEstado } from "@/lib/cockpit"

export const FOCO =
  "outline-none focus-visible:ring-2 focus-visible:ring-hud-ciano focus-visible:ring-offset-2 focus-visible:ring-offset-black/60"

/** Cor de cada tom (as 6 cores com significado do HUD; ver `index.css`). */
export const COR_TOM: Record<TomEstado, string> = {
  normal: "text-hud",
  ativo: "text-hud-verde",
  atencao: "text-hud-ambar",
  perigo: "text-hud-vermelho",
}

/** A FORMA de cada tom — o estado lê-se sem a cor (daltonismo, ecrã ao sol). */
export function FormaTom({
  tom,
  className = "size-2.5",
}: {
  tom: TomEstado
  className?: string
}) {
  return (
    <svg
      viewBox="0 0 10 10"
      aria-hidden="true"
      className={`shrink-0 ${className}`}
      data-forma={tom}
    >
      {tom === "ativo" ? (
        <circle cx="5" cy="5" r="4" fill="currentColor" />
      ) : tom === "atencao" ? (
        <path d="M5 0.8 9.6 9.2H0.4Z" fill="currentColor" />
      ) : tom === "perigo" ? (
        <rect x="1" y="1" width="8" height="8" fill="currentColor" />
      ) : (
        <circle
          cx="5"
          cy="5"
          r="3.4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
        />
      )}
    </svg>
  )
}

/** Marca de estado: forma + texto na cor do tom. */
export function Marca({
  tom,
  children,
  testid,
  className = "",
}: {
  tom: TomEstado
  children: ReactNode
  testid?: string
  className?: string
}) {
  return (
    <span
      data-testid={testid}
      data-tom={tom}
      className={`inline-flex items-center gap-1.5 font-etiqueta text-xs font-bold tracking-wide ${COR_TOM[tom]} ${className}`}
    >
      <FormaTom tom={tom} />
      {children}
    </span>
  )
}

/** Uma tecla desenhada (`<kbd>`), para rótulos de atalho. */
export function Atalho({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-white/25 bg-white/10 px-1 font-etiqueta text-[0.65rem] leading-none font-bold text-hud">
      {children}
    </kbd>
  )
}

export interface InterruptorProps {
  ligado: boolean
  onMudar: (ligado: boolean) => void
  rotulo: string
  /** O que o interruptor faz, numa linha curta. */
  descricao?: string
  atalho?: string
  /** Palavras do estado (por omissão LIGADO/DESLIGADO). */
  estados?: readonly [desligado: string, ligado: string]
  desativado?: boolean
  testid?: string
}

/**
 * Interruptor GRANDE (a linha inteira é o alvo): rótulo à esquerda; à direita a calha e, por baixo, a
 * palavra do estado — o estado lê-se pela posição do botão e pela palavra, não só pela cor.
 * `role="switch"`: Espaço/Enter alternam.
 */
export function Interruptor({
  ligado,
  onMudar,
  rotulo,
  descricao,
  atalho,
  estados = ["DESLIGADO", "LIGADO"],
  desativado = false,
  testid,
}: InterruptorProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={ligado}
      disabled={desativado}
      data-testid={testid}
      data-ligado={ligado ? "sim" : "nao"}
      onClick={() => onMudar(!ligado)}
      className={`flex min-h-[3.25rem] w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${FOCO} ${
        ligado
          ? "border-hud-verde/60 bg-hud-verde/12"
          : "border-white/14 bg-white/5 hover:bg-white/10"
      }`}
    >
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="flex items-center gap-2 text-[0.82rem] font-bold tracking-wide whitespace-nowrap text-hud">
          {rotulo}
          {atalho ? <Atalho>{atalho}</Atalho> : null}
        </span>
        {descricao ? (
          <span className="text-[0.68rem] leading-snug text-muted-foreground">
            {descricao}
          </span>
        ) : null}
      </span>
      <span className="flex w-[4.5rem] shrink-0 flex-col items-center gap-1">
        <span
          aria-hidden="true"
          className={`relative h-6 w-11 rounded-full border transition-colors ${
            ligado
              ? "border-hud-verde bg-hud-verde/35"
              : "border-white/30 bg-black/40"
          }`}
        >
          <span
            className={`absolute top-0.5 left-0.5 size-[1.125rem] rounded-full transition-transform motion-reduce:transition-none ${
              ligado ? "translate-x-5 bg-hud-verde" : "bg-white/70"
            }`}
          />
        </span>
        <span
          className={`font-etiqueta text-[0.65rem] leading-none font-bold tracking-wide ${ligado ? "text-hud-verde" : "text-muted-foreground"}`}
        >
          {ligado ? estados[1] : estados[0]}
        </span>
      </span>
    </button>
  )
}

export interface DeslizadorProps {
  valor: number
  min: number
  max: number
  passo: number
  rotulo: string
  /** O valor por extenso (`2,0 m/s`). */
  texto: string
  /** A arrastar (envio limitado a ~10 Hz por quem recebe). */
  onArrastar: (valor: number) => void
  /** Fim do gesto: largou o rato, a tecla ou o foco (envio final). */
  onLargar: (valor: number) => void
  desativado?: boolean
  testid?: string
  /** Marcas por baixo da calha (ex.: `0`, `5 m/s`). */
  extremos?: readonly [string, string]
}

/** Deslizador com o valor por extenso; a parte preenchida vai na variável `--p` (ver `index.css`). */
export function Deslizador({
  valor,
  min,
  max,
  passo,
  rotulo,
  texto,
  onArrastar,
  onLargar,
  desativado = false,
  testid,
  extremos,
}: DeslizadorProps) {
  const fracao = max > min ? ((valor - min) / (max - min)) * 100 : 0
  /** Mexeu-se desde o último envio final? (um Tab ou um clique sem arrasto não reenviam o mesmo valor) */
  const porLargar = useRef(false)
  const largar = (alvo: EventTarget) => {
    if (!porLargar.current) return
    porLargar.current = false
    onLargar(Number((alvo as HTMLInputElement).value))
  }
  return (
    <label className="flex flex-col gap-0.5">
      <span className="flex items-baseline justify-between gap-2">
        <span className="text-[0.68rem] font-bold tracking-[0.12em] text-muted-foreground uppercase">
          {rotulo}
        </span>
        <span
          className="font-mono text-sm font-bold text-hud"
          data-testid={testid ? `${testid}-valor` : undefined}
        >
          {texto}
        </span>
      </span>
      <input
        type="range"
        className="deslizador"
        style={{ "--p": `${fracao}%` } as CSSProperties}
        min={min}
        max={max}
        step={passo}
        value={valor}
        disabled={desativado}
        data-testid={testid}
        aria-valuetext={texto}
        onChange={(evento) => {
          porLargar.current = true
          onArrastar(Number(evento.target.value))
        }}
        onPointerUp={(evento) => largar(evento.currentTarget)}
        onKeyUp={(evento) => largar(evento.currentTarget)}
        onBlur={(evento) => largar(evento.currentTarget)}
      />
      {extremos ? (
        <span className="flex justify-between font-mono text-[0.65rem] text-muted-foreground">
          <span>{extremos[0]}</span>
          <span>{extremos[1]}</span>
        </span>
      ) : null}
    </label>
  )
}

export interface TeclaProps {
  letra: string
  /** O que a tecla faz, por baixo da letra (`frente`, `subir`). */
  rotulo?: string
  premida: boolean
  /** Sem estes dois a tecla é só um desenho (o HUD); com eles prime-se com o rato/toque. */
  onPremir?: () => void
  onLargar?: () => void
  /** Escurecida: a tecla existe mas agora não manda (a bola está a pilotar). */
  apagada?: boolean
  testid?: string
  titulo?: string
  tamanho?: "hud" | "janela"
}

/**
 * Uma tecla. Premida = CHEIA (fundo ciano, letra escura) e afundada 1 px — a diferença é de forma e de
 * contraste, não só de cor. Na janela Voo prime-se também com o rato (manter = manter a tecla).
 */
export function Tecla({
  letra,
  rotulo,
  premida,
  onPremir,
  onLargar,
  apagada = false,
  testid,
  titulo,
  tamanho = "janela",
}: TeclaProps) {
  const interativa = onPremir !== undefined
  const classes = `flex flex-col items-center justify-center rounded-lg border font-etiqueta leading-none select-none ${
    tamanho === "hud" ? "size-9 text-sm" : "h-11 w-full text-[0.95rem]"
  } ${
    premida
      ? "translate-y-px border-hud-ciano bg-hud-ciano font-bold text-black shadow-[0_0_14px_rgb(88_214_255/0.55)]"
      : "border-white/35 bg-black/45 font-bold text-hud"
  } ${apagada && !premida ? "opacity-40" : ""}`
  const conteudo = (
    <>
      <span>{letra}</span>
      {rotulo ? (
        <span
          className={`mt-1 font-sans text-[0.65rem] font-normal tracking-wide ${premida ? "text-black/80" : "text-muted-foreground"}`}
        >
          {rotulo}
        </span>
      ) : null}
    </>
  )
  if (!interativa) {
    return (
      <span
        data-testid={testid}
        data-estado={premida ? "ativa" : "inativa"}
        className={classes}
      >
        {conteudo}
      </span>
    )
  }
  return (
    <button
      type="button"
      data-testid={testid}
      data-estado={premida ? "ativa" : "inativa"}
      aria-pressed={premida}
      title={titulo}
      className={`${classes} touch-none ${FOCO} ${premida ? "" : "hover:bg-white/12"}`}
      onPointerDown={(evento) => {
        evento.currentTarget.setPointerCapture?.(evento.pointerId)
        onPremir()
      }}
      onPointerUp={onLargar}
      onPointerCancel={onLargar}
      onLostPointerCapture={onLargar}
      // Teclado: Espaço/Enter fazem de «manter» enquanto estiverem em baixo.
      onKeyDown={(evento) => {
        if ((evento.key === " " || evento.key === "Enter") && !evento.repeat) {
          evento.preventDefault()
          onPremir()
        }
      }}
      onKeyUp={(evento) => {
        if (evento.key === " " || evento.key === "Enter") onLargar?.()
      }}
      onBlur={onLargar}
    >
      {conteudo}
    </button>
  )
}

/** Título pequeno de um bloco dentro de uma janela. */
export function Legenda({ children }: { children: ReactNode }) {
  return (
    <span className="text-[0.68rem] font-bold tracking-[0.12em] text-muted-foreground uppercase">
      {children}
    </span>
  )
}

/** Uma leitura (rótulo + valor em Mono); o valor pode ser escrito por ref pelo desenhador do HUD. */
export function Leitura({
  rotulo,
  children,
  refValor,
  testid,
  className = "",
}: {
  rotulo: string
  children?: ReactNode
  refValor?: React.Ref<HTMLSpanElement>
  testid?: string
  className?: string
}) {
  return (
    <div className={`flex min-w-0 flex-col gap-0.5 ${className}`}>
      <Legenda>{rotulo}</Legenda>
      <span
        ref={refValor}
        data-testid={testid}
        className="font-mono text-sm font-bold text-hud"
      >
        {children ?? "—"}
      </span>
    </div>
  )
}
