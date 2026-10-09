/**
 * Bloco de controlos (coluna fixa à direita): vento constante, VENTO DINÂMICO, REINICIAR e LOOP.
 *
 * Cascata:
 *  · passo 2 — `hold-to-confirm` (REINICIAR), `multi-state-button` (APLICAR/PARAR VENTO, RAJADA AGORA,
 *    FRENTE AGORA), `segmented-toggle` (LOOP e o modo dinâmico contínuo)
 *  · passo 3 — `Slider` + `Card` + `Button` + `Input` (primitivos Base UI via shadcn)
 *  · passo 4 — SÓ a rosa dos ventos (`rosa-ventos.tsx`): o catálogo tem séries temporais (`sparkline`) e
 *    barras, não um mostrador polar; 30 linhas de SVG só com `transform`/`opacity` (regra 8).
 *
 * Regra de ouro deste painel: NENHUM destes controlos reinicia o episódio — todos escrevem o modo/vento e
 * a física muda no passo de decisão seguinte (`POST /api/vento`, `POST /api/vento-dinamico`).
 * `/api/reiniciar` é exclusivo do botão com hold de 1 s.
 */

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import {
  Check,
  CircleStop,
  Gauge,
  Loader2,
  RotateCcw,
  TriangleAlert,
  Waves,
  Wind,
  Zap,
} from "lucide-react"

import { HoldToConfirmButton } from "@/components/motion-ui/hold-to-confirm"
import { MultiStateButton } from "@/components/motion-ui/multi-state-button"
import {
  SegmentedToggle,
  SegmentedToggleOption,
} from "@/components/motion-ui/segmented-toggle"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import { useMotionUITransition } from "@/components/motion-ui/ui-theme"
import { RosaDosVentos } from "@/components/sim/rosa-ventos"
import {
  fmt,
  fmtGraus,
  fmtParams,
  PARAMS_DINAMICOS_PADRAO,
  ROTULO_MODO,
  VENTO_LIMITES,
  type CorpoVento,
  type CorpoVentoDinamico,
  type EstadoEpisodio,
  type ModoContinuo,
  type ModoVentoDinamico,
  type VentoDinamico,
  type VentoEstado,
} from "@/lib/sim"
import { FOCUS_RING } from "@/components/sim/estilo"

/** Estados visíveis dos botões de vento (chaves do `multi-state-button`). */
export type FaseVento = "pronto" | "a_enviar" | "ok" | "erro"

/** Qual dos botões dinâmicos está a caminho do servidor (os outros ficam em espera). */
export type AlvoDinamico = "modo" | "rajada" | "frente" | "parar"

/** Estados visíveis dos botões dinâmicos: as 4 fases + `ativo` (o interruptor está ligado no servidor). */
type EstadoBotao = FaseVento | "ativo"

const SUPERFICIE_VENTO: Record<EstadoBotao, string> = {
  pronto: "bg-primary text-primary-foreground",
  a_enviar: "bg-secondary text-secondary-foreground",
  ok: "bg-primary text-primary-foreground",
  erro: "bg-destructive/15 text-destructive",
  // modo em vigor no servidor (o botão é um interruptor: clicar outra vez desliga)
  ativo: "bg-primary text-primary-foreground ring-2 ring-ring",
}

/** Passos de decisão por segundo (o mesmo 50 Hz do contrato do RPi 5). */
const PASSOS_POR_SEGUNDO = 50

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

interface CampoNumericoProps {
  id: string
  rotulo: string
  valor: number
  min: number
  max: number
  passo: number
  sufixo?: string
  dica?: string
  onChange: (valor: number) => void
}

/** Campo numérico curto dos parâmetros dinâmicos (o `Input` do shadcn, em tamanho de painel). */
function CampoNumerico({
  id,
  rotulo,
  valor,
  min,
  max,
  passo,
  sufixo,
  dica,
  onChange,
}: CampoNumericoProps) {
  return (
    <label htmlFor={id} className="flex flex-col gap-0.5">
      <span className="text-[0.65rem] text-muted-foreground">{rotulo}</span>
      <span className="flex items-center gap-1">
        <Input
          id={id}
          data-testid={`campo-${id}`}
          type="number"
          inputMode="decimal"
          min={min}
          max={max}
          step={passo}
          value={valor}
          onChange={(evento) => {
            const n = Number(evento.target.value)
            onChange(Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : min)
          }}
          className="h-7 w-16 rounded-md px-2 font-mono text-xs"
        />
        {sufixo ? (
          <span className="text-[0.6rem] text-muted-foreground">{sufixo}</span>
        ) : null}
      </span>
      {dica ? (
        <span className="text-[0.6rem] text-muted-foreground">{dica}</span>
      ) : null}
    </label>
  )
}

interface DinamicoProps {
  dinamico: VentoDinamico
  /** Modo que a TELEMETRIA reporta na última linha (é o que a física está a fazer). */
  modoTelemetria: ModoVentoDinamico
  ligado: boolean
  fase: FaseVento
  emCurso: AlvoDinamico | null
  /** Força/azimute/elevação dos sliders — a rajada e a frente usam-nos como estão. */
  selecao: CorpoVento
  onEnviar: (
    corpo: CorpoVentoDinamico,
    alvo: AlvoDinamico,
    descricao: string
  ) => void
}

/**
 * Sub-painel do vento dinâmico (ronda 10): um modo CONTÍNUO (rajadas ou turbulência Dryden), dois
 * instantâneos (RAJADA AGORA, FRENTE AGORA) e o reset `{"modo":"nenhum","ativo":false}`.
 */
function Dinamico({
  dinamico,
  modoTelemetria,
  ligado,
  fase,
  emCurso,
  selecao,
  onEnviar,
}: DinamicoProps) {
  const ui = useMotionUITransition("ui")
  const [p, setP] = useState<number>(PARAMS_DINAMICOS_PADRAO.rajadas.p)
  const [duracaoRajadas, setDuracaoRajadas] = useState<number>(
    PARAMS_DINAMICOS_PADRAO.rajadas.duracao
  )
  const [uMax, setUMax] = useState<number>(
    PARAMS_DINAMICOS_PADRAO.rajadas.u_max
  )
  const [sigma, setSigma] = useState<number>(
    PARAMS_DINAMICOS_PADRAO.dryden.sigma
  )
  const [comprimento, setComprimento] = useState<number>(
    PARAMS_DINAMICOS_PADRAO.dryden.L
  )
  const [vMin, setVMin] = useState<number>(PARAMS_DINAMICOS_PADRAO.dryden.v_min)
  const [duracaoRajada, setDuracaoRajada] = useState<number>(
    PARAMS_DINAMICOS_PADRAO.rajada_agora.duracao
  )

  const modoContinuo: ModoContinuo =
    dinamico.ativo &&
    (dinamico.modo === "rajadas" || dinamico.modo === "dryden")
      ? dinamico.modo
      : "nenhum"
  const rajadaEmCurso = dinamico.ativo && modoTelemetria === "rajada_agora"
  const frenteAtiva = dinamico.ativo && dinamico.modo === "frente"
  const ocupado = emCurso !== null
  const desativado = !ligado || ocupado

  const paramsRajadas = { p, duracao: Math.round(duracaoRajadas), u_max: uMax }
  const paramsDryden = { sigma, L: comprimento, v_min: vMin }

  const trocarModo = (alvo: ModoContinuo) => {
    if (alvo === modoContinuo) return
    if (alvo === "nenhum") {
      onEnviar(
        { modo: "nenhum", ativo: false },
        "modo",
        "vento dinâmico desligado"
      )
      return
    }
    if (alvo === "rajadas") {
      onEnviar(
        { modo: "rajadas", ativo: true, params: paramsRajadas },
        "modo",
        `rajadas contínuas ligadas (p=${fmt(p, 3)}, duração=${Math.round(duracaoRajadas)} passos, u_max=${fmt(uMax, 1)} m/s)`
      )
      return
    }
    onEnviar(
      { modo: "dryden", ativo: true, params: paramsDryden },
      "modo",
      `turbulência Dryden ligada (σ=${fmt(sigma, 2)}, L=${fmt(comprimento, 1)}, v_min=${fmt(vMin, 1)} m/s)`
    )
  }

  return (
    <section
      aria-label="Vento dinâmico"
      data-testid="painel-dinamico"
      className="flex flex-col gap-3 rounded-lg border border-border/70 bg-muted/20 p-3"
    >
      <div className="flex items-center gap-1.5">
        <Zap className="size-3.5" aria-hidden="true" />
        <h4 className="text-[0.7rem] tracking-wide uppercase">
          vento dinâmico
        </h4>
        <span
          data-testid="estado-dinamico"
          className={`ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[0.6rem] ${
            dinamico.ativo
              ? "bg-primary/10 text-primary"
              : "bg-muted text-muted-foreground"
          }`}
        >
          <motion.span
            aria-hidden="true"
            className={`size-1.5 rounded-full ${dinamico.ativo ? "bg-primary" : "bg-muted-foreground"}`}
            animate={
              dinamico.ativo ? { opacity: [1, 0.25, 1] } : { opacity: 1 }
            }
            transition={
              dinamico.ativo
                ? { duration: 1.4, repeat: Infinity, ease: "easeInOut" }
                : { duration: 0.2 }
            }
          />
          {dinamico.ativo ? "ativo" : "inativo"}
        </span>
      </div>

      <p className="text-[0.65rem] text-muted-foreground">
        modo em vigor:{" "}
        <span className="text-foreground">{ROTULO_MODO[dinamico.modo]}</span>
        {dinamico.ativo ? "" : " · sem dinâmica"} · params{" "}
        <span className="font-mono">{fmtParams(dinamico.params)}</span> · a
        física muda no passo seguinte,{" "}
        <span className="text-foreground">sem reiniciar o episódio</span>
      </p>

      <SegmentedToggle
        value={modoContinuo}
        onChange={(v) => trocarModo(v as ModoContinuo)}
        ariaLabel="modo dinâmico contínuo"
        className="w-full"
      >
        <SegmentedToggleOption value="nenhum">PARADO</SegmentedToggleOption>
        <SegmentedToggleOption value="rajadas">RAJADAS</SegmentedToggleOption>
        <SegmentedToggleOption value="dryden">DRYDEN</SegmentedToggleOption>
      </SegmentedToggle>

      <AnimatePresence initial={false} mode="wait">
        {modoContinuo === "rajadas" ? (
          <motion.div
            key="rajadas"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ ...ui }}
            className="flex flex-wrap gap-3"
            data-testid="params-rajadas"
          >
            <CampoNumerico
              id="rajadas-p"
              rotulo="p (probabilidade)"
              valor={p}
              min={0}
              max={1}
              passo={0.005}
              onChange={setP}
            />
            <CampoNumerico
              id="rajadas-duracao"
              rotulo="duração"
              valor={duracaoRajadas}
              min={1}
              max={200}
              passo={1}
              sufixo="passos"
              dica={`${fmt(duracaoRajadas / PASSOS_POR_SEGUNDO, 2)} s @ 50 Hz`}
              onChange={setDuracaoRajadas}
            />
            <CampoNumerico
              id="rajadas-umax"
              rotulo="u_max"
              valor={uMax}
              min={0}
              max={5}
              passo={0.1}
              sufixo="m/s"
              onChange={setUMax}
            />
          </motion.div>
        ) : modoContinuo === "dryden" ? (
          <motion.div
            key="dryden"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ ...ui }}
            className="flex flex-wrap gap-3"
            data-testid="params-dryden"
          >
            <CampoNumerico
              id="dryden-sigma"
              rotulo="sigma"
              valor={sigma}
              min={0.05}
              max={3}
              passo={0.05}
              onChange={setSigma}
            />
            <CampoNumerico
              id="dryden-L"
              rotulo="L"
              valor={comprimento}
              min={0.5}
              max={40}
              passo={0.5}
              sufixo="m"
              onChange={setComprimento}
            />
            <CampoNumerico
              id="dryden-vmin"
              rotulo="v_min"
              valor={vMin}
              min={0.1}
              max={5}
              passo={0.1}
              sufixo="m/s"
              onChange={setVMin}
            />
          </motion.div>
        ) : (
          <motion.p
            key="parado"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ ...ui }}
            className="text-[0.65rem] text-muted-foreground"
          >
            RAJADAS = rajadas que <span className="text-foreground">somam</span>{" "}
            ao vento base · DRYDEN = turbulência que passeia em torno dele. Os
            params ficam editáveis no modo escolhido.
          </motion.p>
        )}
      </AnimatePresence>

      <div className="flex flex-wrap items-center gap-2">
        <MultiStateButton
          state={
            emCurso === "rajada" ? fase : rajadaEmCurso ? "ativo" : "pronto"
          }
          onClick={() =>
            onEnviar(
              {
                modo: "rajada_agora",
                ativo: true,
                params: {
                  duracao: Math.round(duracaoRajada),
                  u: selecao.vel,
                  azimute: selecao.azimute,
                  elevacao: selecao.elevacao,
                },
              },
              "rajada",
              `rajada agora: ${fmt(selecao.vel, 2)} m/s · ${fmtGraus(selecao.azimute)} · ${Math.round(duracaoRajada)} passos`
            )
          }
          disabled={desativado}
          surfaceClassName={
            SUPERFICIE_VENTO[
              emCurso === "rajada" ? fase : rajadaEmCurso ? "ativo" : "pronto"
            ]
          }
          feedback={fase === "erro" && emCurso === null ? "shake" : "pop"}
          announce={rajadaEmCurso ? "rajada em curso" : undefined}
          aria-label="rajada agora"
          icon={
            emCurso === "rajada" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Zap className="size-4" />
            )
          }
          className={FOCUS_RING}
          pillClassName="rounded-full px-4 py-2 text-xs font-medium shadow-sm"
        >
          {emCurso === "rajada"
            ? "A ENVIAR…"
            : rajadaEmCurso
              ? "RAJADA EM CURSO"
              : "RAJADA AGORA"}
        </MultiStateButton>

        <MultiStateButton
          state={emCurso === "frente" ? fase : frenteAtiva ? "ativo" : "pronto"}
          onClick={() =>
            frenteAtiva
              ? onEnviar(
                  { modo: "nenhum", ativo: false },
                  "frente",
                  "frente desligada"
                )
              : onEnviar(
                  {
                    modo: "frente",
                    ativo: true,
                    params: {
                      vel: selecao.vel,
                      azimute: selecao.azimute,
                      elevacao: selecao.elevacao,
                    },
                  },
                  "frente",
                  `frente agora: degrau para ${fmt(selecao.vel, 2)} m/s · ${fmtGraus(selecao.azimute)}`
                )
          }
          disabled={desativado}
          surfaceClassName={
            SUPERFICIE_VENTO[
              emCurso === "frente" ? fase : frenteAtiva ? "ativo" : "pronto"
            ]
          }
          feedback="pop"
          announce={frenteAtiva ? "frente em vigor" : undefined}
          aria-label="frente agora"
          icon={
            emCurso === "frente" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Waves className="size-4" />
            )
          }
          className={FOCUS_RING}
          pillClassName="rounded-full px-4 py-2 text-xs font-medium shadow-sm"
        >
          {emCurso === "frente"
            ? "A ENVIAR…"
            : frenteAtiva
              ? "FRENTE EM VIGOR"
              : "FRENTE AGORA"}
        </MultiStateButton>

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 rounded-full px-3 text-xs"
          onClick={() =>
            onEnviar(
              { modo: "nenhum", ativo: false },
              "parar",
              "vento dinâmico parado"
            )
          }
          disabled={desativado}
          data-testid="botao-parar-dinamico"
        >
          <CircleStop className="size-3.5" aria-hidden="true" />
          PARAR DINÂMICO
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <CampoNumerico
          id="rajada-duracao"
          rotulo="duração da rajada"
          valor={duracaoRajada}
          min={1}
          max={500}
          passo={1}
          sufixo="passos"
          dica={`${fmt(duracaoRajada / PASSOS_POR_SEGUNDO, 2)} s · env: u=força, azimute, elevação dos sliders`}
          onChange={setDuracaoRajada}
        />
        <p className="flex items-center gap-1 pb-1 font-mono text-[0.6rem] text-muted-foreground">
          <Gauge className="size-3" aria-hidden="true" />
          última linha: modo={modoTelemetria}
        </p>
      </div>
    </section>
  )
}

interface ControlosProps {
  vento: VentoEstado
  /** Vetor do vento em vigor (telemetria `vento_vec`), ou `null`. */
  vec: [number, number, number] | null
  dinamico: VentoDinamico
  /** Modo reportado pela última linha de telemetria (o que a física está mesmo a fazer). */
  modoTelemetria: ModoVentoDinamico
  estado: EstadoEpisodio
  ep: number
  ligado: boolean
  loop: boolean
  faseVento: FaseVento
  faseDinamico: FaseVento
  emCurso: AlvoDinamico | null
  aReiniciar: boolean
  onAplicarVento: (corpo: CorpoVento) => void
  onPararVento: () => void
  onVentoDinamico: (
    corpo: CorpoVentoDinamico,
    alvo: AlvoDinamico,
    descricao: string
  ) => void
  onReiniciar: () => void
  onLoop: (ativo: boolean) => void
}

export function Controlos({
  vento,
  vec,
  dinamico,
  modoTelemetria,
  estado,
  ep,
  ligado,
  loop,
  faseVento,
  faseDinamico,
  emCurso,
  aReiniciar,
  onAplicarVento,
  onPararVento,
  onVentoDinamico,
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

          <RosaDosVentos selecao={selecao} vec={vec} modo={modoTelemetria} />

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

        <Dinamico
          dinamico={dinamico}
          modoTelemetria={modoTelemetria}
          ligado={ligado}
          fase={faseDinamico}
          emCurso={emCurso}
          selecao={selecao}
          onEnviar={onVentoDinamico}
        />

        <section
          aria-label="Episódio"
          className="flex flex-col gap-2 border-t border-border pt-4"
        >
          <h3 className="text-xs tracking-wide text-muted-foreground uppercase">
            episódio
          </h3>
          <div className="relative">
            {terminado ? (
              <motion.span
                aria-hidden="true"
                className="pointer-events-none absolute -inset-1 rounded-full ring-2 ring-destructive"
                animate={{ opacity: [0.15, 0.7, 0.15] }}
                transition={{
                  duration: 1.6,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
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
          <p
            id="reiniciar-ajuda"
            className="text-[0.65rem] text-muted-foreground"
          >
            carrega e mantém ~1 s: o preenchimento confirma · POST
            /api/reiniciar
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
          <p
            className="font-mono text-[0.65rem] text-muted-foreground"
            data-testid="estado-loop"
          >
            loop={loop ? "true" : "false"} · estado={estado}
          </p>
        </section>
      </CardContent>
    </Card>
  )
}
