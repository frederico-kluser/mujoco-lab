/**
 * controlos.tsx — TODOS os controlos do experimento (é o princípio do padrão: a janela não tem nenhum),
 * separados em DOIS blocos para o site os poder mostrar em sítios diferentes:
 *
 *  · `ControlosVento` — vento (perturbação) em TEMPO REAL: sliders de velocidade/azimute/elevação +
 *    APLICAR/PARAR (o POST escreve o ficheiro de controlo de forma atómica; o runner aplica-o no passo de
 *    decisão seguinte), VENTO DINÂMICO ao vivo (`POST /api/vento-dinamico`: rajadas contínuas, turbulência
 *    Dryden, frente e RAJADA AGORA) e a ROSA DOS VENTOS viva (`sim/rosa-ventos.tsx`: seta cheia = vetor em
 *    vigor da telemetria, tracejada = o que os sliders mandariam). Vive na secção «Vento».
 *  · `ControlosEpisodio` — REINICIAR (`hold-to-confirm`, manter 1 s: é o ÚNICO caminho de reinício; o
 *    backend conta os pedidos) e LOOP (`segmented-toggle`, desligado por omissão). São os controlos
 *    CRÍTICOS: ficam na barra fixa do topo (`compacto`) e vêem-se em QUALQUER secção.
 *
 * Cascata (motion-plus-ui): passo 2 — `hold-to-confirm`, `multi-state-button`, `segmented-toggle`; passo 3 —
 * `Slider`/`Card`/`Button`/`Input` (shadcn); passo 4 só na rosa dos ventos e no anel do REINICIAR (o catálogo
 * não tem mostrador polar nem indicador pulsante) — SVG/`motion` com classes semânticas.
 */

import { useEffect, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { Check, CircleStop, Gauge, Loader2, RotateCcw, TriangleAlert, Waves, Wind, Zap } from "lucide-react"

import { HoldToConfirmButton } from "@/components/motion-ui/hold-to-confirm"
import { MultiStateButton } from "@/components/motion-ui/multi-state-button"
import { SegmentedToggle, SegmentedToggleOption } from "@/components/motion-ui/segmented-toggle"
import { useMotionUITransition } from "@/components/motion-ui/ui-theme"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
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
  ativo: "bg-primary text-primary-foreground ring-2 ring-ring",   // ligado no servidor: clicar desliga
}

/** Passos de decisão por segundo (o mesmo 50 Hz do orçamento de latência do RPi 5). */
const PASSOS_POR_SEGUNDO = 50

function LinhaSlider({ id, rotulo, valor, min, max, passo, sufixo, casas = 1, onChange }: {
  id: string
  rotulo: string
  valor: number
  min: number
  max: number
  passo: number
  sufixo: string
  casas?: number
  onChange: (valor: number) => void
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-xs font-medium">{rotulo}</label>
        <span className="font-mono text-xs tabular-nums">{fmt(valor, casas)}{sufixo}</span>
      </div>
      <Slider id={id} min={min} max={max} step={passo} value={[valor]}
        onValueChange={(v) => onChange(Array.isArray(v) ? (v[0] ?? min) : v)} aria-label={rotulo} />
      <div className="flex justify-between font-mono text-[0.6rem] text-muted-foreground">
        <span>{fmt(min, 0)}</span>
        <span>{fmt(max, 0)}</span>
      </div>
    </div>
  )
}

/** Campo numérico curto dos parâmetros dinâmicos (o `Input` do shadcn, em tamanho de painel). */
function CampoNumerico({ id, rotulo, valor, min, max, passo, sufixo, dica, onChange }: {
  id: string
  rotulo: string
  valor: number
  min: number
  max: number
  passo: number
  sufixo?: string
  dica?: string
  onChange: (valor: number) => void
}) {
  return (
    <label htmlFor={id} className="flex flex-col gap-0.5">
      <span className="text-[0.65rem] text-muted-foreground">{rotulo}</span>
      <span className="flex items-center gap-1">
        <Input id={id} data-testid={`campo-${id}`} type="number" inputMode="decimal" min={min} max={max}
          step={passo} value={valor}
          onChange={(evento) => {
            const n = Number(evento.target.value)
            onChange(Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : min)
          }}
          className="h-7 w-16 rounded-md px-2 font-mono text-xs" />
        {sufixo ? <span className="text-[0.6rem] text-muted-foreground">{sufixo}</span> : null}
      </span>
      {dica ? <span className="text-[0.6rem] text-muted-foreground">{dica}</span> : null}
    </label>
  )
}

/**
 * Sub-painel do VENTO DINÂMICO: um modo CONTÍNUO (rajadas ou turbulência Dryden), dois instantâneos
 * (RAJADA AGORA, FRENTE AGORA) e o PARAR DINÂMICO (`{"modo":"nenhum","ativo":false}`).
 *
 * Nada aqui reinicia o episódio: cada botão faz `POST /api/vento-dinamico` (o `onEnviar` de cima) e a física
 * muda no passo de decisão seguinte.
 */
function Dinamico({ dinamico, modoTelemetria, ligado, fase, emCurso, selecao, onEnviar }: {
  dinamico: VentoDinamico
  /** Modo que a TELEMETRIA reporta na última linha (é o que a física está a fazer). */
  modoTelemetria: ModoVentoDinamico
  ligado: boolean
  fase: FaseVento
  emCurso: AlvoDinamico | null
  /** Força/azimute/elevação dos sliders — a rajada e a frente usam-nos como estão. */
  selecao: CorpoVento
  onEnviar: (corpo: CorpoVentoDinamico, alvo: AlvoDinamico, descricao: string) => void
}) {
  const ui = useMotionUITransition("ui")
  const [p, setP] = useState<number>(PARAMS_DINAMICOS_PADRAO.rajadas.p)
  const [duracaoRajadas, setDuracaoRajadas] = useState<number>(PARAMS_DINAMICOS_PADRAO.rajadas.duracao)
  const [uMax, setUMax] = useState<number>(PARAMS_DINAMICOS_PADRAO.rajadas.u_max)
  const [sigma, setSigma] = useState<number>(PARAMS_DINAMICOS_PADRAO.dryden.sigma)
  const [comprimento, setComprimento] = useState<number>(PARAMS_DINAMICOS_PADRAO.dryden.L)
  const [vMin, setVMin] = useState<number>(PARAMS_DINAMICOS_PADRAO.dryden.v_min)
  const [duracaoRajada, setDuracaoRajada] = useState<number>(PARAMS_DINAMICOS_PADRAO.rajada_agora.duracao)

  const modoContinuo: ModoContinuo =
    dinamico.ativo && (dinamico.modo === "rajadas" || dinamico.modo === "dryden") ? dinamico.modo : "nenhum"
  const rajadaEmCurso = dinamico.ativo && modoTelemetria === "rajada_agora"
  const frenteAtiva = dinamico.ativo && dinamico.modo === "frente"
  const desativado = !ligado || emCurso !== null
  const paramsRajadas = { p, duracao: Math.round(duracaoRajadas), u_max: uMax }
  const paramsDryden = { sigma, L: comprimento, v_min: vMin }

  const trocarModo = (alvo: ModoContinuo) => {
    if (alvo === modoContinuo) return
    if (alvo === "nenhum") {
      onEnviar({ modo: "nenhum", ativo: false }, "modo", "vento dinâmico desligado")
      return
    }
    if (alvo === "rajadas") {
      onEnviar({ modo: "rajadas", ativo: true, params: paramsRajadas }, "modo",
        `rajadas contínuas ligadas (p=${fmt(p, 3)}, duração=${Math.round(duracaoRajadas)} passos, u_max=${fmt(uMax, 1)} m/s)`)
      return
    }
    onEnviar({ modo: "dryden", ativo: true, params: paramsDryden }, "modo",
      `turbulência Dryden ligada (σ=${fmt(sigma, 2)}, L=${fmt(comprimento, 1)}, v_min=${fmt(vMin, 1)} m/s)`)
  }

  return (
    <section aria-label="Vento dinâmico" data-testid="painel-dinamico"
      className="flex flex-col gap-3 rounded-lg border border-border/70 bg-muted/20 p-3">
      <div className="flex items-center gap-1.5">
        <Zap className="size-3.5" aria-hidden="true" />
        <h3 className="text-[0.7rem] tracking-wide uppercase">vento dinâmico</h3>
        <span data-testid="estado-dinamico"
          className={`ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[0.6rem] ${
            dinamico.ativo ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>
          <motion.span aria-hidden="true"
            className={`size-1.5 rounded-full ${dinamico.ativo ? "bg-primary" : "bg-muted-foreground"}`}
            animate={dinamico.ativo ? { opacity: [1, 0.25, 1] } : { opacity: 1 }}
            transition={dinamico.ativo ? { duration: 1.4, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }} />
          {dinamico.ativo ? "ativo" : "inativo"}
        </span>
      </div>

      <p className="text-[0.65rem] text-muted-foreground">
        modo em vigor: <span className="text-foreground">{ROTULO_MODO[modoTelemetria]}</span>
        {dinamico.ativo ? "" : " · sem dinâmica"} · params{" "}
        <span className="font-mono">{fmtParams(dinamico.params)}</span> · a física muda no passo seguinte,{" "}
        <span className="text-foreground">sem reiniciar o episódio</span>
      </p>

      <SegmentedToggle value={modoContinuo} onChange={(v) => trocarModo(v as ModoContinuo)}
        ariaLabel="modo dinâmico contínuo" className="w-full">
        <SegmentedToggleOption value="nenhum">PARADO</SegmentedToggleOption>
        <SegmentedToggleOption value="rajadas">RAJADAS</SegmentedToggleOption>
        <SegmentedToggleOption value="dryden">DRYDEN</SegmentedToggleOption>
      </SegmentedToggle>

      <AnimatePresence initial={false} mode="wait">
        {modoContinuo === "rajadas" ? (
          <motion.div key="rajadas" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }} transition={{ ...ui }} className="flex flex-wrap gap-3"
            data-testid="params-rajadas">
            <CampoNumerico id="rajadas-p" rotulo="p (probabilidade)" valor={p} min={0} max={1} passo={0.005}
              onChange={setP} />
            <CampoNumerico id="rajadas-duracao" rotulo="duração" valor={duracaoRajadas} min={1} max={200} passo={1}
              sufixo="passos" dica={`${fmt(duracaoRajadas / PASSOS_POR_SEGUNDO, 2)} s @ 50 Hz`}
              onChange={setDuracaoRajadas} />
            <CampoNumerico id="rajadas-umax" rotulo="u_max" valor={uMax} min={0} max={5} passo={0.1} sufixo="m/s"
              onChange={setUMax} />
          </motion.div>
        ) : modoContinuo === "dryden" ? (
          <motion.div key="dryden" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }} transition={{ ...ui }} className="flex flex-wrap gap-3"
            data-testid="params-dryden">
            <CampoNumerico id="dryden-sigma" rotulo="sigma" valor={sigma} min={0.05} max={3} passo={0.05}
              onChange={setSigma} />
            <CampoNumerico id="dryden-L" rotulo="L" valor={comprimento} min={0.5} max={40} passo={0.5} sufixo="m"
              onChange={setComprimento} />
            <CampoNumerico id="dryden-vmin" rotulo="v_min" valor={vMin} min={0.1} max={5} passo={0.1} sufixo="m/s"
              onChange={setVMin} />
          </motion.div>
        ) : (
          <motion.p key="parado" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }} transition={{ ...ui }} className="text-[0.65rem] text-muted-foreground">
            RAJADAS = rajadas que <span className="text-foreground">somam</span> ao vento base · DRYDEN =
            turbulência que passeia em torno dele. Os params ficam editáveis no modo escolhido.
          </motion.p>
        )}
      </AnimatePresence>

      <div className="flex flex-wrap items-center gap-2">
        <MultiStateButton
          state={emCurso === "rajada" ? fase : rajadaEmCurso ? "ativo" : "pronto"}
          onClick={() => onEnviar({
            modo: "rajada_agora", ativo: true,
            params: { duracao: Math.round(duracaoRajada), u: selecao.vel, azimute: selecao.azimute,
                      elevacao: selecao.elevacao },
          }, "rajada",
            `rajada agora: ${fmt(selecao.vel, 2)} m/s · ${fmtGraus(selecao.azimute)} · ${Math.round(duracaoRajada)} passos`)}
          disabled={desativado}
          surfaceClassName={SUPERFICIE_VENTO[emCurso === "rajada" ? fase : rajadaEmCurso ? "ativo" : "pronto"]}
          feedback={fase === "erro" && emCurso === null ? "shake" : "pop"}
          announce={rajadaEmCurso ? "rajada em curso" : undefined}
          aria-label="rajada agora"
          icon={emCurso === "rajada" ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" />}
          className={FOCUS_RING}
          pillClassName="rounded-full px-4 py-2 text-xs font-medium shadow-sm">
          {emCurso === "rajada" ? "A ENVIAR…" : rajadaEmCurso ? "RAJADA EM CURSO" : "RAJADA AGORA"}
        </MultiStateButton>

        <MultiStateButton
          state={emCurso === "frente" ? fase : frenteAtiva ? "ativo" : "pronto"}
          onClick={() =>
            frenteAtiva
              ? onEnviar({ modo: "nenhum", ativo: false }, "frente", "frente desligada")
              : onEnviar({ modo: "frente", ativo: true,
                           params: { vel: selecao.vel, azimute: selecao.azimute, elevacao: selecao.elevacao } },
                         "frente",
                         `frente agora: degrau para ${fmt(selecao.vel, 2)} m/s · ${fmtGraus(selecao.azimute)}`)}
          disabled={desativado}
          surfaceClassName={SUPERFICIE_VENTO[emCurso === "frente" ? fase : frenteAtiva ? "ativo" : "pronto"]}
          feedback="pop"
          announce={frenteAtiva ? "frente em vigor" : undefined}
          aria-label="frente agora"
          icon={emCurso === "frente" ? <Loader2 className="size-4 animate-spin" /> : <Waves className="size-4" />}
          className={FOCUS_RING}
          pillClassName="rounded-full px-4 py-2 text-xs font-medium shadow-sm">
          {emCurso === "frente" ? "A ENVIAR…" : frenteAtiva ? "FRENTE EM VIGOR" : "FRENTE AGORA"}
        </MultiStateButton>

        <Button type="button" variant="outline" size="sm"
          className="h-8 rounded-full px-3 text-xs"
          onClick={() => onEnviar({ modo: "nenhum", ativo: false }, "parar", "vento dinâmico parado")}
          disabled={desativado} data-testid="botao-parar-dinamico">
          <CircleStop className="size-3.5" aria-hidden="true" />
          PARAR DINÂMICO
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <CampoNumerico id="rajada-duracao" rotulo="duração da rajada" valor={duracaoRajada} min={1} max={500}
          passo={1} sufixo="passos"
          dica={`${fmt(duracaoRajada / PASSOS_POR_SEGUNDO, 2)} s · env: u=força, azimute, elevação dos sliders`}
          onChange={setDuracaoRajada} />
        <p className="flex items-center gap-1 pb-1 font-mono text-[0.6rem] text-muted-foreground">
          <Gauge className="size-3" aria-hidden="true" />
          última linha: modo={modoTelemetria}
        </p>
      </div>
    </section>
  )
}

export interface ControlosVentoProps {
  /** Vento BASE em vigor no backend (`/api/sim`): dá o ponto de partida aos sliders. */
  vento: VentoEstado | null
  /** Vetor do vento em vigor (telemetria `vento_vec`), ou `null`. */
  vec: [number, number, number] | null
  /** Modo/params do vento dinâmico em vigor no backend. */
  dinamico: VentoDinamico
  /** Modo reportado pela última linha de telemetria (o que a física está mesmo a fazer). */
  modoTelemetria: ModoVentoDinamico
  /** `false` = a API ainda não respondeu: os botões ficam em espera (nada de pedidos a fingir). */
  ligado: boolean
  faseVento: FaseVento
  faseDinamico: FaseVento
  emCurso: AlvoDinamico | null
  onAplicarVento: (corpo: CorpoVento) => void
  onPararVento: () => void
  onVentoDinamico: (corpo: CorpoVentoDinamico, alvo: AlvoDinamico, descricao: string) => void
}

/**
 * Secção «Vento»: sliders do vento constante + rosa dos ventos + o bloco do vento dinâmico.
 *
 * Nenhum destes controlos reinicia o episódio — todos escrevem o vento/modo no ficheiro de controlo
 * (`POST /api/vento`, `POST /api/vento-dinamico`) e a física muda no passo de decisão seguinte.
 */
export function ControlosVento({
  vento,
  vec,
  dinamico,
  modoTelemetria,
  ligado,
  faseVento,
  faseDinamico,
  emCurso,
  onAplicarVento,
  onPararVento,
  onVentoDinamico,
}: ControlosVentoProps) {
  const [vel, setVel] = useState(0)
  const [azimute, setAzimute] = useState(0)
  const [elevacao, setElevacao] = useState(0)
  const sincronizado = useRef(false)

  // Primeira leitura da API dá o ponto de partida aos sliders; depois o valor é do utilizador (o vento só
  // muda por POST, que é sempre um clique explícito).
  useEffect(() => {
    if (sincronizado.current || !ligado || !vento) return
    sincronizado.current = true
    setVel(vento.vel)
    setAzimute(vento.azimute)
    setElevacao(vento.elevacao)
  }, [ligado, vento])

  const selecao: CorpoVento = { vel, azimute, elevacao }
  const iconeFase = { pronto: <Wind className="size-4" aria-hidden="true" />,
    a_enviar: <Loader2 className="size-4 animate-spin" aria-hidden="true" />,
    ok: <Check className="size-4" aria-hidden="true" />,
    erro: <TriangleAlert className="size-4" aria-hidden="true" /> }[faseVento]

  return (
    <Card className="gap-4" data-testid="painel-controlos">
      <CardHeader className="gap-1">
        <CardTitle className="text-sm font-medium">Controlos</CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          vento físico em tempo real · o site nunca reinicia sozinho
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <section aria-label="Vento" className="flex flex-col gap-3">
          <h3 className="flex items-center gap-1.5 text-xs tracking-wide text-muted-foreground uppercase">
            <Wind className="size-3.5" aria-hidden="true" /> vento
            <span className="ml-auto font-mono text-[0.65rem] normal-case">
              agora {fmt(vento?.vel ?? null, 2)} m/s · {fmtGraus(vento?.azimute ?? null)}
            </span>
          </h3>

          <LinhaSlider id="vento-forca" rotulo="força" valor={vel} min={VENTO_LIMITES.vel[0]}
            max={VENTO_LIMITES.vel[1]} passo={0.1} sufixo=" m/s" onChange={setVel} />
          <LinhaSlider id="vento-azimute" rotulo="azimute" valor={azimute} min={VENTO_LIMITES.azimute[0]}
            max={VENTO_LIMITES.azimute[1]} passo={1} sufixo="°" casas={0} onChange={setAzimute} />
          <LinhaSlider id="vento-elevacao" rotulo="elevação" valor={elevacao} min={VENTO_LIMITES.elevacao[0]}
            max={VENTO_LIMITES.elevacao[1]} passo={1} sufixo="°" casas={0} onChange={setElevacao} />

          <RosaDosVentos selecao={selecao} vec={vec} modo={modoTelemetria} />

          <div className="flex flex-wrap items-center gap-2">
            <MultiStateButton state={faseVento} icon={iconeFase} onClick={() => onAplicarVento(selecao)}
              feedback="pop" widthMorph={false} disabled={faseVento === "a_enviar" || !ligado}
              aria-label="aplicar vento" className={FOCUS_RING}>
              {faseVento === "a_enviar" ? "A ENVIAR…" : faseVento === "ok" ? "VENTO APLICADO"
                : faseVento === "erro" ? "FALHOU — TENTAR DE NOVO" : "APLICAR VENTO"}
            </MultiStateButton>
            <Button variant="outline" onClick={onPararVento} className={FOCUS_RING} disabled={!ligado}
              data-testid="botao-parar-vento">
              <CircleStop className="size-4" aria-hidden="true" /> PARAR VENTO
            </Button>
          </div>
        </section>

        <Dinamico dinamico={dinamico} modoTelemetria={modoTelemetria} ligado={ligado} fase={faseDinamico}
          emCurso={emCurso} selecao={selecao} onEnviar={onVentoDinamico} />
      </CardContent>
    </Card>
  )
}

export interface ControlosEpisodioProps {
  estado: EstadoEpisodio
  ep: number | null
  ligado: boolean
  loop: boolean
  aReiniciar: boolean
  /**
   * Compacto = barra fixa do topo (botão curto, ajuda só para leitores de ecrã);
   * completo = coluna vertical com a explicação à vista.
   */
  compacto?: boolean
  onReiniciar: () => void
  onLoop: (ativo: boolean) => void
}

/**
 * REINICIAR (hold de 1 s) + LOOP — os controlos críticos do episódio, visíveis em QUALQUER secção (barra fixa
 * do topo em `App.tsx`). O site nunca reinicia sozinho: `/api/reiniciar` é exclusivo deste botão; com o LOOP
 * ligado quem reinicia no fim do episódio é o BACKEND.
 */
export function ControlosEpisodio({
  estado,
  ep,
  ligado,
  loop,
  aReiniciar,
  compacto = false,
  onReiniciar,
  onLoop,
}: ControlosEpisodioProps) {
  /** Muda a cada REINICIAR confirmado: remonta o botão de catálogo (ver comentário no `key`). */
  const [geracao, setGeracao] = useState(0)
  const terminado = estado === "episodio_terminado"

  return (
    <div data-testid="controlos-episodio" className={compacto ? "flex items-center gap-3" : "flex flex-col gap-2"}>
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
            // O `hold-to-confirm` do catálogo é de UM disparo (o `done` interno só volta com `reset()`, que
            // ele não expõe em `mode="callback"`) — remontar por `key` volta a armar o botão e repõe a
            // escala, sem tocar no source instalado (regra 6 da skill).
            setGeracao((g) => g + 1)
            onReiniciar()
          }}
          aria-describedby="reiniciar-ajuda"
          className={compacto ? "h-9! w-auto! px-4! text-xs!" : "h-14! w-full! text-base! font-semibold! tracking-wide"}
        >
          <RotateCcw className={compacto ? "size-3.5" : "size-5"} aria-hidden="true" />
          {aReiniciar ? "A REINICIAR…" : compacto ? "REINICIAR" : "REINICIAR (manter 1 s)"}
        </HoldToConfirmButton>
      </div>

      <div className={compacto ? "flex items-center gap-2" : "mt-2 flex items-center justify-between gap-3"}>
        <div className="flex flex-col">
          <span className="text-xs font-medium">LOOP</span>
          {compacto ? null : (
            <span className="text-[0.65rem] text-muted-foreground">off por omissão · auto-reset é do backend</span>
          )}
        </div>
        <SegmentedToggle value={loop ? "on" : "off"} onChange={(v) => onLoop(v === "on")}
          ariaLabel="LOOP de episódios" className="shrink-0">
          <SegmentedToggleOption value="off">OFF</SegmentedToggleOption>
          <SegmentedToggleOption value="on">ON</SegmentedToggleOption>
        </SegmentedToggle>
      </div>

      <p id="reiniciar-ajuda" className={compacto ? "sr-only" : "text-[0.65rem] text-muted-foreground"}>
        carrega e mantém ~1 s: o preenchimento confirma · POST /api/reiniciar
      </p>
      {compacto ? (
        <span className="sr-only">
          episódio {fmt(ep, 0)} · {terminado ? "terminado" : "a correr"} · ligação {ligado ? "ativa" : "inativa"}
        </span>
      ) : null}
    </div>
  )
}
