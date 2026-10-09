/**
 * controlos.tsx — TODOS os controlos do experimento (é o princípio do padrão: a janela não tem nenhum).
 *
 *  · vento (perturbação) em TEMPO REAL: sliders de velocidade/azimute/elevação + APLICAR/PARAR (o POST escreve
 *    o ficheiro de controlo de forma atómica; o runner aplica-o no passo de decisão seguinte);
 *  · VENTO DINÂMICO ao vivo (`POST /api/vento-dinamico`): rajadas contínuas, turbulência Dryden, frente
 *    (degrau imediato do vento base) e RAJADA AGORA (one-shot dirigido) — a física muda no passo seguinte
 *    SEM reiniciar o episódio;
 *  · ROSA DOS VENTOS viva (`sim/rosa-ventos.tsx`): seta cheia = vetor em vigor (telemetria), tracejada = o
 *    que os sliders mandariam;
 *  · REINICIAR — `hold-to-confirm` (manter 1 s): é o ÚNICO caminho de reinício; o backend conta os pedidos;
 *  · LOOP — `segmented-toggle` (desligado por omissão: sem ciclo automático).
 *
 * Cascata (motion-plus-ui): passo 2 — `hold-to-confirm`, `multi-state-button`, `segmented-toggle`; passo 3 —
 * `Slider`/`Card`/`Button`/`Input` (shadcn); passo 4 só na rosa dos ventos (o catálogo não tem mostrador
 * polar) e nos selos de estado, que são texto com classes semânticas.
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
type AlvoDinamico = "modo" | "rajada" | "frente" | "parar"

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

export function Controlos({ vento, vec, dinamico, modoTelemetria, estado, loop, contadorReiniciar, onVento,
                            onVentoDinamico, onReiniciar, onLoop, aviso }: {
  vento: VentoEstado | null
  /** Vetor do vento em vigor (telemetria `vento_vec`), ou `null`. */
  vec: [number, number, number] | null
  dinamico: VentoDinamico
  /** Modo reportado pela última linha de telemetria (o que a física está mesmo a fazer). */
  modoTelemetria: ModoVentoDinamico
  estado: EstadoEpisodio
  loop: boolean
  contadorReiniciar: number | null
  onVento: (corpo: CorpoVento, ativo: boolean) => Promise<void>
  onVentoDinamico: (corpo: CorpoVentoDinamico) => Promise<void>
  onReiniciar: () => Promise<number | null>
  onLoop: (ativo: boolean) => Promise<void>
  aviso: (tom: "ok" | "erro" | "info", texto: string) => void
}) {
  const ui = useMotionUITransition("ui")
  const [vel, setVel] = useState(0)
  const [azimute, setAzimute] = useState(0)
  const [elevacao, setElevacao] = useState(0)
  const [fase, setFase] = useState<FaseVento>("pronto")
  const [faseDinamico, setFaseDinamico] = useState<FaseVento>("pronto")
  const [emCurso, setEmCurso] = useState<AlvoDinamico | null>(null)
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

  /** VENTO DINÂMICO: só escreve o modo — o episódio NUNCA é reiniciado. */
  async function enviarDinamico(corpo: CorpoVentoDinamico, alvo: AlvoDinamico, descricao: string) {
    setEmCurso(alvo)
    setFaseDinamico("a_enviar")
    try {
      await onVentoDinamico(corpo)
      setFaseDinamico("ok")
      aviso("ok", `${descricao} — POST /api/vento-dinamico`)
    } catch (erro) {
      setFaseDinamico("erro")
      aviso("erro", `POST /api/vento-dinamico recusado — ${erro instanceof Error ? erro.message : "falha"}`)
    } finally {
      setEmCurso(null)
      setTimeout(() => setFaseDinamico("pronto"), 1600)
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

  const terminado = estado === "episodio_terminado"
  const selecao: CorpoVento = { vel, azimute, elevacao }
  const rotuloFase = { pronto: "APLICAR VENTO", a_enviar: "A ENVIAR…", ok: "APLICADO", erro: "ERRO" }[fase]
  const iconeFase = { pronto: <Wind className="size-4" />, a_enviar: <Loader2 className="size-4 animate-spin" />,
    ok: <Check className="size-4" />, erro: <TriangleAlert className="size-4" /> }[fase]

  return (
    <Card className={`gap-3 py-4 ${terminado ? "ring-2 ring-destructive/40" : ""}`} data-testid="painel-controlos">
      <CardHeader className="px-4">
        <CardTitle className="text-sm font-medium text-muted-foreground">controlos (vento · dinâmico · reiniciar · loop)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 px-4">
        <AnimatePresence initial={false} mode="wait">
          {terminado ? (
            <motion.p key="terminado" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }} transition={{ ...ui }} data-testid="aviso-terminado"
              className="rounded-lg bg-destructive/10 px-3 py-2 text-xs font-medium text-destructive">
              episódio terminado — clica REINICIAR
            </motion.p>
          ) : (
            <motion.p key="a-correr" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }} transition={{ ...ui }} data-testid="aviso-a-correr"
              className="rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
              {loop ? "episódio a correr · LOOP ligado (o backend reinicia ao terminar)"
                    : "episódio a correr · sem auto-restart"}
            </motion.p>
          )}
        </AnimatePresence>

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
            <MultiStateButton state={fase} icon={iconeFase} onClick={() => void aplicar(true)} feedback="pop"
              widthMorph={false} disabled={fase === "a_enviar" || estado === "sem_dados"} >
              {rotuloFase}
            </MultiStateButton>
            <Button variant="outline" onClick={() => void aplicar(false)} className={FOCUS_RING}>
              <CircleStop className="size-4" /> PARAR VENTO
            </Button>
          </div>
        </section>

        <Dinamico dinamico={dinamico} modoTelemetria={modoTelemetria} ligado={estado !== "sem_dados"}
          fase={faseDinamico} emCurso={emCurso} selecao={selecao}
          onEnviar={(corpo, alvo, descricao) => void enviarDinamico(corpo, alvo, descricao)} />

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
