/**
 * Bloco de controlos (coluna fixa à direita): vento ao vivo, REINICIAR e LOOP.
 *
 * Cascata:
 *  · passo 2 — `hold-to-confirm` (REINICIAR), `multi-state-button` (APLICAR/PARAR VENTO), `segmented-toggle` (LOOP)
 *  · passo 3 — `Slider` (primitivo Base UI via shadcn) + `Card` + `Button`
 *  · passo 4 — SÓ a rosa dos ventos (SVG polar): o catálogo tem séries temporais (`sparkline`) e barras,
 *    não um mostrador de azimute/elevação; 30 linhas de SVG com `transform: rotate` (regra 8).
 */

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { Check, CircleStop, Loader2, RotateCcw, TriangleAlert, Wind } from "lucide-react"

import { HoldToConfirmButton } from "@/components/motion-ui/hold-to-confirm"
import { MultiStateButton } from "@/components/motion-ui/multi-state-button"
import {
  SegmentedToggle,
  SegmentedToggleOption,
} from "@/components/motion-ui/segmented-toggle"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Slider } from "@/components/ui/slider"
import { useMotionUITransition } from "@/components/motion-ui/ui-theme"
import {
  fmt,
  fmtGraus,
  VENTO_LIMITES,
  ventoCartesiano,
  type CorpoVento,
  type EstadoEpisodio,
  type VentoEstado,
} from "@/lib/sim"
import { FOCUS_RING } from "@/components/sim/estilo"

/** Estados visíveis dos botões de vento (chaves do `multi-state-button`). */
export type FaseVento = "pronto" | "a_enviar" | "ok" | "erro"

const SUPERFICIE_VENTO: Record<FaseVento, string> = {
  pronto: "bg-primary text-primary-foreground",
  a_enviar: "bg-secondary text-secondary-foreground",
  ok: "bg-primary text-primary-foreground",
  erro: "bg-destructive/15 text-destructive",
}

interface LinhaSliderProps {
  id: string
  rotulo: string
  valor: number
  min: number
  max: number
  passo: number
  sufixo: string
  casas?: number
  onChange: (valor: number) => void
}

function LinhaSlider({
  id,
  rotulo,
  valor,
  min,
  max,
  passo,
  sufixo,
  casas = 1,
  onChange,
}: LinhaSliderProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-xs font-medium">
          {rotulo}
        </label>
        <span className="font-mono text-xs tabular-nums">
          {fmt(valor, casas)}
          {sufixo}
        </span>
      </div>
      <Slider
        id={id}
        min={min}
        max={max}
        step={passo}
        value={[valor]}
        onValueChange={(v) => onChange(Array.isArray(v) ? (v[0] ?? min) : v)}
        aria-label={rotulo}
      />
      <div className="flex justify-between font-mono text-[0.6rem] text-muted-foreground">
        <span>{fmt(min, 0)}</span>
        <span>{fmt(max, 0)}</span>
      </div>
    </div>
  )
}

interface RosaDosVentosProps {
  vento: CorpoVento
  ativo: boolean
}

/** Mostrador polar: seta a girar pelo azimute, comprimento pela velocidade (0–5 m/s). */
function RosaDosVentos({ vento, ativo }: RosaDosVentosProps) {
  const ui = useMotionUITransition("ui")
  const comprimento = 12 + (Math.min(vento.vel, VENTO_LIMITES.vel[1]) / VENTO_LIMITES.vel[1]) * 22
  const [x, y, z] = ventoCartesiano(vento)
  return (
    <div className="flex items-center gap-3">
      <svg
        viewBox="-44 -44 88 88"
        className="size-20 shrink-0"
        role="img"
        aria-label={`vento ${fmt(vento.vel, 2)} m/s a ${fmtGraus(vento.azimute)} de azimute`}
      >
        <circle r="40" className="fill-muted/30 stroke-border" strokeWidth="1" />
        <line x1="-40" y1="0" x2="40" y2="0" className="stroke-border" strokeWidth="1" />
        <line x1="0" y1="-40" x2="0" y2="40" className="stroke-border" strokeWidth="1" />
        <text x="34" y="-4" style={{ fontSize: 8 }} className="fill-muted-foreground">
          +x
        </text>
        <text x="-4" y="-32" style={{ fontSize: 8 }} className="fill-muted-foreground">
          +y
        </text>
        <motion.g
          initial={false}
          // azimute 90° → +y: no SVG o y cresce para BAIXO, logo o ângulo é negativo em ecrã
          animate={{ rotate: -vento.azimute }}
          transition={{ ...ui }}
        >
          <line
            x1="0"
            y1="0"
            x2={comprimento}
            y2="0"
            className={ativo ? "stroke-primary" : "stroke-muted-foreground"}
            strokeWidth="3"
            strokeLinecap="round"
          />
          <circle cx="0" cy="0" r="3" className="fill-primary" />
        </motion.g>
      </svg>
      <dl className="grid flex-1 grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[0.7rem]">
        <dt className="text-muted-foreground">vetor (mundo)</dt>
        <dd className="text-right tabular-nums">
          {fmt(x, 2)}, {fmt(y, 2)}, {fmt(z, 2)}
        </dd>
        <dt className="text-muted-foreground">elevação</dt>
        <dd className="text-right tabular-nums">{fmtGraus(vento.elevacao)}</dd>
        <dt className="text-muted-foreground">estado</dt>
        <dd className="text-right">{ativo ? "ativo" : "parado"}</dd>
      </dl>
    </div>
  )
}

interface ControlosProps {
  vento: VentoEstado
  estado: EstadoEpisodio
  ep: number
  ligado: boolean
  loop: boolean
  faseVento: FaseVento
  aReiniciar: boolean
  onAplicarVento: (corpo: CorpoVento) => void
  onPararVento: () => void
  onReiniciar: () => void
  onLoop: (ativo: boolean) => void
}

export function Controlos({
  vento,
  estado,
  ep,
  ligado,
  loop,
  faseVento,
  aReiniciar,
  onAplicarVento,
  onPararVento,
  onReiniciar,
  onLoop,
}: ControlosProps) {
  const ui = useMotionUITransition("ui")
  const [forca, setForca] = useState(0)
  const [azimute, setAzimute] = useState(0)
  const [elevacao, setElevacao] = useState(0)
  /** Muda a cada REINICIAR confirmado: remonta o botão de catálogo (ver comentário no `key`). */
  const [geracao, setGeracao] = useState(0)
  const sincronizado = useRef(false)

  // Primeira leitura da API dá o ponto de partida aos sliders; depois o valor é do utilizador
  // (o vento só muda por POST, que é sempre um clique explícito).
  useEffect(() => {
    if (sincronizado.current || !ligado) return
    sincronizado.current = true
    setForca(vento.vel)
    setAzimute(vento.azimute)
    setElevacao(vento.elevacao)
  }, [ligado, vento])

  const terminado = estado === "episodio_terminado"
  const selecao: CorpoVento = { vel: forca, azimute, elevacao }

  return (
    <Card
      className={`gap-4 ${terminado ? "ring-2 ring-destructive/40" : ""}`}
      data-testid="painel-controlos"
    >
      <CardHeader className="gap-1">
        <CardTitle className="text-sm font-medium">Controlos</CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          vento físico em tempo real · o site nunca reinicia sozinho
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <AnimatePresence initial={false} mode="wait">
          {terminado ? (
            <motion.p
              key="terminado"
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ ...ui }}
              data-testid="aviso-terminado"
              className="rounded-lg bg-destructive/10 px-3 py-2 text-xs font-medium text-destructive"
            >
              episódio {fmt(ep, 0)} terminado — clica REINICIAR
            </motion.p>
          ) : (
            <motion.p
              key="a-correr"
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ ...ui }}
              data-testid="aviso-a-correr"
              className="rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground"
            >
              {loop
                ? "episódio a correr · LOOP ligado (o backend reinicia ao terminar)"
                : "episódio a correr · sem auto-restart"}
            </motion.p>
          )}
        </AnimatePresence>

        <section aria-label="Vento" className="flex flex-col gap-4">
          <h3 className="flex items-center gap-1.5 text-xs tracking-wide text-muted-foreground uppercase">
            <Wind className="size-3.5" aria-hidden="true" /> vento
            <span className="ml-auto font-mono text-[0.65rem] normal-case">
              agora {fmt(vento.vel, 2)} m/s · {fmtGraus(vento.azimute)}
            </span>
          </h3>

          <LinhaSlider
            id="vento-forca"
            rotulo="força"
            valor={forca}
            min={VENTO_LIMITES.vel[0]}
            max={VENTO_LIMITES.vel[1]}
            passo={0.1}
            sufixo=" m/s"
            onChange={setForca}
          />
          <LinhaSlider
            id="vento-azimute"
            rotulo="azimute"
            valor={azimute}
            min={VENTO_LIMITES.azimute[0]}
            max={VENTO_LIMITES.azimute[1]}
            passo={1}
            sufixo="°"
            casas={0}
            onChange={setAzimute}
          />
          <LinhaSlider
            id="vento-elevacao"
            rotulo="elevação"
            valor={elevacao}
            min={VENTO_LIMITES.elevacao[0]}
            max={VENTO_LIMITES.elevacao[1]}
            passo={1}
            sufixo="°"
            casas={0}
            onChange={setElevacao}
          />

          <RosaDosVentos vento={selecao} ativo={forca > 0} />

          <div className="flex flex-wrap items-center gap-2">
            <MultiStateButton
              state={faseVento}
              onClick={() => onAplicarVento(selecao)}
              disabled={faseVento === "a_enviar" || !ligado}
              surfaceClassName={SUPERFICIE_VENTO[faseVento]}
              feedback={faseVento === "erro" ? "shake" : "pop"}
              announce={
                faseVento === "ok"
                  ? "vento aplicado"
                  : faseVento === "erro"
                    ? "falha ao aplicar o vento"
                    : undefined
              }
              aria-label="aplicar vento"
              className={FOCUS_RING}
              pillClassName="rounded-full px-5 py-3 text-sm font-medium shadow-sm"
            >
              {faseVento === "a_enviar" ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : faseVento === "ok" ? (
                <Check className="size-4" aria-hidden="true" />
              ) : faseVento === "erro" ? (
                <TriangleAlert className="size-4" aria-hidden="true" />
              ) : (
                <Wind className="size-4" aria-hidden="true" />
              )}
              {faseVento === "a_enviar"
                ? "A ENVIAR…"
                : faseVento === "ok"
                  ? "VENTO APLICADO"
                  : faseVento === "erro"
                    ? "FALHOU — TENTAR DE NOVO"
                    : "APLICAR VENTO"}
            </MultiStateButton>

            <Button
              type="button"
              variant="outline"
              size="lg"
              className="h-10 rounded-full px-5"
              onClick={onPararVento}
              disabled={!ligado}
              data-testid="botao-parar-vento"
            >
              <CircleStop className="size-4" aria-hidden="true" />
              PARAR VENTO
            </Button>
          </div>
        </section>

        <section
          aria-label="Episódio"
          className="flex flex-col gap-2 border-t border-border pt-4"
        >
          <h3 className="text-xs tracking-wide text-muted-foreground uppercase">episódio</h3>
          <div className="relative">
            {terminado ? (
              <motion.span
                aria-hidden="true"
                className="pointer-events-none absolute -inset-1 rounded-full ring-2 ring-destructive"
                animate={{ opacity: [0.15, 0.7, 0.15] }}
                transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
              />
            ) : null}
            <HoldToConfirmButton
              key={geracao}
              holdSeconds={1}
              mode="callback"
              onConfirm={() => {
                // O `hold-to-confirm` do catálogo é de UM disparo (o `done` interno só volta com `reset()`,
                // que o componente não expõe em `mode="callback"`) — remontar por `key` volta a armar o
                // botão e repõe a escala, sem tocar no source instalado (regra 6 da skill).
                setGeracao((g) => g + 1)
                onReiniciar()
              }}
              aria-describedby="reiniciar-ajuda"
              className="h-14! w-full! text-base! font-semibold! tracking-wide"
            >
              <RotateCcw className="size-5" aria-hidden="true" />
              {aReiniciar ? "A REINICIAR…" : "REINICIAR (manter 1 s)"}
            </HoldToConfirmButton>
          </div>
          <p id="reiniciar-ajuda" className="text-[0.65rem] text-muted-foreground">
            carrega e mantém ~1 s: o preenchimento confirma · POST /api/reiniciar
          </p>

          <div className="mt-2 flex items-center justify-between gap-3">
            <div className="flex flex-col">
              <span className="text-xs font-medium">LOOP</span>
              <span className="text-[0.65rem] text-muted-foreground">
                off por omissão · auto-reset é do backend
              </span>
            </div>
            <SegmentedToggle
              value={loop ? "on" : "off"}
              onChange={(v) => onLoop(v === "on")}
              ariaLabel="LOOP de episódios"
              className="shrink-0"
            >
              <SegmentedToggleOption value="off">OFF</SegmentedToggleOption>
              <SegmentedToggleOption value="on">ON</SegmentedToggleOption>
            </SegmentedToggle>
          </div>
          <p className="font-mono text-[0.65rem] text-muted-foreground" data-testid="estado-loop">
            loop={loop ? "true" : "false"} · estado={estado}
          </p>
        </section>
      </CardContent>
    </Card>
  )
}
