/**
 * controlos.tsx — TODOS os controlos do experimento (é o princípio do padrão: a janela não tem nenhum).
 *
 *  · vento (perturbação) em TEMPO REAL: sliders de velocidade/azimute/elevação + APLICAR/PARAR (o POST escreve
 *    o ficheiro de controlo de forma atómica; o runner aplica-o no passo de decisão seguinte);
 *  · REINICIAR — `hold-to-confirm` (manter 1 s): é o ÚNICO caminho de reinício; o backend conta os pedidos;
 *  · LOOP — `segmented-toggle` (desligado por omissão: sem ciclo automático);
 *  · rosa dos ventos (SVG de 30 linhas, também ausente do catálogo) — azimute/elevação em vigor.
 */

import { useEffect, useRef, useState } from "react"
import { motion } from "motion/react"
import { Check, CircleStop, Loader2, RotateCcw, TriangleAlert, Wind } from "lucide-react"

import { HoldToConfirmButton } from "@/components/motion-ui/hold-to-confirm"
import { MultiStateButton } from "@/components/motion-ui/multi-state-button"
import { SegmentedToggle, SegmentedToggleOption } from "@/components/motion-ui/segmented-toggle"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Slider } from "@/components/ui/slider"
import { VENTO_LIMITES, fmt, type CorpoVento, type VentoEstado } from "@/lib/sim"
import { FOCUS_RING } from "@/components/sim/estilo"

export type FaseVento = "pronto" | "a_enviar" | "ok" | "erro"

/** Rosa dos ventos: direção/elevação em vigor (azimute 0° = +X, anti-horário visto de cima). */
export function RosaDosVentos({ vento }: { vento: VentoEstado | null }) {
  const azimute = vento?.azimute ?? 0
  const elevacao = vento?.elevacao ?? 0
  const raio = 34
  const escala = (vento?.vel ?? 0) / VENTO_LIMITES.vel[1]
  return (
    <svg width={96} height={96} viewBox="-48 -48 96 96" role="img" aria-label="rosa dos ventos">
      <circle r={raio} className="fill-transparent stroke-border" strokeWidth={1} />
      <line x1={-raio} y1={0} x2={raio} y2={0} className="stroke-border" strokeDasharray="2 3" />
      <line x1={0} y1={-raio} x2={0} y2={raio} className="stroke-border" strokeDasharray="2 3" />
      <text x={raio + 1} y={4} className="fill-muted-foreground text-[8px]">+X</text>
      <text x={-4} y={-raio - 2} className="fill-muted-foreground text-[8px]">+Y</text>
      <motion.g animate={{ rotate: -azimute }} transition={{ type: "spring", stiffness: 60, damping: 14 }}>
        <line x1={0} y1={0} x2={raio * (0.35 + 0.65 * escala)} y2={0} stroke="#86efac" strokeWidth={3}
          strokeLinecap="round" />
        <circle cx={raio * (0.35 + 0.65 * escala)} cy={0} r={3} fill="#86efac" />
      </motion.g>
      <text x={0} y={raio + 10} textAnchor="middle" className="fill-muted-foreground text-[8px]">
        az {fmt(azimute, 0)}° · elev {fmt(elevacao, 0)}°
      </text>
    </svg>
  )
}

export function Controlos({ vento, loop, contadorReiniciar, onVento, onReiniciar, onLoop, aviso }: {
  vento: VentoEstado | null
  loop: boolean
  contadorReiniciar: number | null
  onVento: (corpo: CorpoVento, ativo: boolean) => Promise<void>
  onReiniciar: () => Promise<number | null>
  onLoop: (ativo: boolean) => Promise<void>
  aviso: (tom: "ok" | "erro" | "info", texto: string) => void
}) {
  const [vel, setVel] = useState(0)
  const [azimute, setAzimute] = useState(0)
  const [elevacao, setElevacao] = useState(0)
  const [fase, setFase] = useState<FaseVento>("pronto")
  const [geracao, setGeracao] = useState(0)
  const primeira = useRef(true)

  // O servidor é a fonte da verdade do vento em vigor: sincroniza os sliders com o que ele reporta.
  useEffect(() => {
    if (!vento) return
    if (!primeira.current) return
    primeira.current = false
    setVel(vento.vel)
    setAzimute(vento.azimute)
    setElevacao(vento.elevacao)
  }, [vento])

  async function aplicar(ativo: boolean) {
    setFase("a_enviar")
    try {
      await onVento({ vel, azimute, elevacao }, ativo)
      setFase("ok")
      aviso("ok", ativo ? `vento aplicado: ${fmt(vel, 1)} m/s @ ${fmt(azimute, 0)}°` : "vento parado (0 m/s)")
      setTimeout(() => setFase("pronto"), 1200)
    } catch (erro) {
      setFase("erro")
      aviso("erro", erro instanceof Error ? erro.message : "falha ao enviar o vento")
      setTimeout(() => setFase("pronto"), 2000)
    }
  }

  async function reiniciar() {
    try {
      const contador = await onReiniciar()
      setGeracao((g) => g + 1)
      aviso("ok", `REINICIAR enviado${contador === null ? "" : ` (pedido nº ${contador})`}`)
    } catch (erro) {
      aviso("erro", erro instanceof Error ? erro.message : "falha no REINICIAR")
    }
  }

  const rotuloFase = { pronto: "APLICAR VENTO", a_enviar: "A ENVIAR…", ok: "APLICADO", erro: "ERRO" }[fase]
  const iconeFase = { pronto: <Wind className="size-4" />, a_enviar: <Loader2 className="size-4 animate-spin" />,
    ok: <Check className="size-4" />, erro: <TriangleAlert className="size-4" /> }[fase]

  return (
    <Card className="gap-3 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-sm font-medium text-muted-foreground">controlos (vento · reiniciar · loop)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 px-4">
        <div className="flex items-start gap-3">
          <RosaDosVentos vento={vento} />
          <div className="flex-1 space-y-3">
            <label className="block space-y-1">
              <span className="flex justify-between text-xs text-muted-foreground">
                <span>velocidade do vento</span><span className="tabular-nums">{fmt(vel, 1)} m/s</span>
              </span>
              <Slider value={[vel]} min={VENTO_LIMITES.vel[0]} max={VENTO_LIMITES.vel[1]} step={0.1}
                onValueChange={(v) => setVel(Array.isArray(v) ? v[0] : v)} aria-label="velocidade do vento" />
            </label>
            <label className="block space-y-1">
              <span className="flex justify-between text-xs text-muted-foreground">
                <span>azimute</span><span className="tabular-nums">{fmt(azimute, 0)}°</span>
              </span>
              <Slider value={[azimute]} min={VENTO_LIMITES.azimute[0]} max={VENTO_LIMITES.azimute[1]} step={1}
                onValueChange={(v) => setAzimute(Array.isArray(v) ? v[0] : v)} aria-label="azimute do vento" />
            </label>
            <label className="block space-y-1">
              <span className="flex justify-between text-xs text-muted-foreground">
                <span>elevação</span><span className="tabular-nums">{fmt(elevacao, 0)}°</span>
              </span>
              <Slider value={[elevacao]} min={VENTO_LIMITES.elevacao[0]} max={VENTO_LIMITES.elevacao[1]} step={1}
                onValueChange={(v) => setElevacao(Array.isArray(v) ? v[0] : v)} aria-label="elevação do vento" />
            </label>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <MultiStateButton state={fase} icon={iconeFase} onClick={() => void aplicar(true)} feedback="pop"
            widthMorph={false} disabled={fase === "a_enviar"}>
            {rotuloFase}
          </MultiStateButton>
          <Button variant="outline" onClick={() => void aplicar(false)} className={FOCUS_RING}>
            <CircleStop className="size-4" /> PARAR VENTO
          </Button>
        </div>

        <div className="space-y-2 border-t border-border/50 pt-3">
          <div className="flex flex-wrap items-center gap-2">
            {/* `key={geracao}`: o `hold-to-confirm` instalado é de UM disparo (o `done` só volta com `reset()`,
                que ele não expõe em mode="callback") — remontar por `key` volta a armar o botão. */}
            <HoldToConfirmButton key={geracao} holdSeconds={1} mode="callback" onConfirm={() => void reiniciar()}>
              <RotateCcw className="size-4" /> REINICIAR (manter 1 s)
            </HoldToConfirmButton>
            <span className="text-xs text-muted-foreground">
              pedidos de reinício: {contadorReiniciar === null ? "—" : contadorReiniciar}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <SegmentedToggle value={loop ? "on" : "off"} onChange={(v) => void onLoop(v === "on")} ariaLabel="LOOP">
              <SegmentedToggleOption value="off">LOOP OFF</SegmentedToggleOption>
              <SegmentedToggleOption value="on">LOOP ON</SegmentedToggleOption>
            </SegmentedToggle>
            <span className="text-xs text-muted-foreground">
              {loop ? "o backend reinicia sozinho no fim do episódio" : "sem ciclo automático: espera pelo REINICIAR"}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
