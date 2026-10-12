/**
 * Controlos de VENTO (`ControlosVento`, secção «Vento») e de EPISÓDIO (`ControlosEpisodio`, barra fixa).
 *
 * `ControlosVento` = vento constante (sliders + rosa + APLICAR/PARAR) e VENTO DINÂMICO.
 * `ControlosEpisodio` = REINICIAR (hold de 1 s) + LOOP — vive na barra fixa do topo para estar acessível
 * de QUALQUER secção (a monitoria em voo não pode depender de scroll até à coluna lateral).
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
import {
  agendarEnvioDinamico,
  enviosDinamicosBloqueados,
} from "@/lib/paragem"
import { RosaDosVentos } from "@/components/sim/rosa-ventos"
import {
  fmt,
  fmtGraus,
  fmtParams,
  PARAMS_DINAMICOS_PADRAO,
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
export type AlvoDinamico =
  | "modo"
  | "params"
  | "rajada"
  | "frente"
  | "parar"

/** Estados visíveis dos botões dinâmicos: as 4 fases + `ativo` (o interruptor está ligado no servidor). */
type EstadoBotao = FaseVento | "ativo"

const SUPERFICIE_VENTO: Record<EstadoBotao, string> = {
  pronto: "bg-primary text-primary-foreground",
  a_enviar: "bg-secondary text-secondary-foreground",
  ok: "bg-primary text-primary-foreground",
  erro: "bg-destructive/15 text-destructive",
  // modo ativo no servidor (o botão é um interruptor: clicar outra vez desliga)
  ativo: "bg-primary text-primary-foreground ring-2 ring-ring",
}

/** Passos de decisão por segundo (o mesmo 50 Hz do contrato do RPi 5). */
const PASSOS_POR_SEGUNDO = 50

// <rajadas-ux:puro>
// REGIÃO PURA do painel dinâmico (léxico + estado + rajada) — sem React nem JSX, para
// `site/testes/rajadas-ux.mts` a extrair e executar tal e qual (Node type-stripping). Não mover nem
// misturar com código de UI: os testes ancoram nos marcadores acima/abaixo.
//
// Avaliação de UX em `pesquisas/ux-rajadas-avaliacao.json` (achados 1–5): o estado do sistema passa a
// ser a PRIMEIRA coisa do painel, com um léxico ÚNICO (achado 3) — os mesmos rótulos do segmented
// toggle, da faixa de estado e dos botões instantâneos; os nomes técnicos (`rajada_agora`, `aleatoria`)
// ficam só nos `title`/tooltip.

/** LÉXICO ÚNICO do painel dinâmico: os rótulos EXATOS usados em toggle, faixa de estado e botões. */
export const ROTULOS_MODO_ESTADO = {
  parado: "PARADO",
  rajadas: "RAJADAS",
  aleatoria: "ALEATÓRIA",
  dryden: "DRYDEN",
  rajada_agora: "RAJADA AGORA",
  frente: "FRENTE AGORA",
} as const

/** Os 3 estados EXAUSTIVOS da faixa: nada a acontecer · modo armado · rajada a bater agora. */
export type EstadoFaixa = "parado" | "a_correr" | "rajada"

/** Limiar de deteção de rajada em curso (m/s): |‖vento_vec‖ − vel_base| acima disto há envelope ≠ 0. */
export const LIMIAR_RAJADA_M_S = 0.05

/**
 * Intensidade da rajada que está a bater AGORA (m/s): `|‖vento_vec‖ − vel_base|`, com o vento real da
 * telemetria (`total`) e o vento BASE comandado (`base`). `0` quando não há rajada visível.
 *
 * Limite honesto (dito, não escondido): é uma diferença de MÓDULOS — uma rajada quase perpendicular ao
 * vento base subestima o envelope (a soma vetorial tem módulo perto do base); nas geometrias normais
 * (proa/cauda) mede o que o operador quer saber. Sem dados de telemetria (`total === null`) o chamador
 * não deve usar este número — não há rajada a inventar.
 */
export function intensidadeRajada(total: number, base: number): number {
  return Math.abs(total - base)
}

/**
 * Mapeamento modo → estado da faixa (parado · a_correr · rajada), SEMPRE a partir do que a física faz:
 * `modoTelemetria` é o `vento_modo` real da última amostra e `intensidade` o desvio medido em m/s.
 *
 * Regras (as 3 primeiras são o que o operador pergunta — «está a rolar ou só armado?»):
 *  1. `rajada_agora` na telemetria → `rajada` / RAJADA AGORA (o instantâneo está a bater);
 *  2. intensidade > 0,05 m/s → `rajada` / o MODO de origem (RAJADAS · ALEATÓRIA · DRYDEN quando há modo
 *     contínuo — é o que responde a «está no modo aleatório ou não?» —, RAJADA AGORA caso contrário);
 *  3. modo contínuo armado → `a_correr` / o rótulo do toggle (RAJADAS · ALEATÓRIA · DRYDEN);
 *  4. `frente` na telemetria (degrau mantido) → `a_correr` / FRENTE AGORA;
 *  5. caso contrário → `parado` / PARADO.
 */
export function estadoFaixa(entrada: {
  modoContinuo: "nenhum" | "rajadas" | "aleatoria" | "dryden"
  modoTelemetria: string
  intensidade: number
}): { estado: EstadoFaixa; modo: string; intensidade: number } {
  const { modoContinuo, modoTelemetria, intensidade } = entrada
  const rotuloContinuo =
    modoContinuo === "nenhum"
      ? null
      : (ROTULOS_MODO_ESTADO[modoContinuo] as string)
  if (modoTelemetria === "rajada_agora") {
    return { estado: "rajada", modo: ROTULOS_MODO_ESTADO.rajada_agora, intensidade }
  }
  if (intensidade > LIMIAR_RAJADA_M_S) {
    return {
      estado: "rajada",
      modo: rotuloContinuo ??
        (modoTelemetria === "frente"
          ? ROTULOS_MODO_ESTADO.frente
          : ROTULOS_MODO_ESTADO.rajada_agora),
      intensidade,
    }
  }
  if (rotuloContinuo) return { estado: "a_correr", modo: rotuloContinuo, intensidade }
  if (modoTelemetria === "frente") {
    return { estado: "a_correr", modo: ROTULOS_MODO_ESTADO.frente, intensidade }
  }
  return { estado: "parado", modo: ROTULOS_MODO_ESTADO.parado, intensidade }
}
// </rajadas-ux:puro>

/**
 * Params do modo ativo em LINGUAGEM NATURAL (achado 5 — chunking): uma linha com unidades, sem o
 * monoespaço de `params {p: 0.40, duracao: 25, u_max: 3.0}`. Os valores são os do SERVIDOR tal e qual —
 * casas suficientes para o valor ser exacto (p tem passo 0,005; segundos = passos/50) e nunca mais.
 * Sem params em vigor (modo nunca ligado) a linha diz-o em vez de mostrar zeros inventados.
 */
function resumoParamsDinamicos(
  modo: ModoVentoDinamico,
  params: Record<string, number>
): string {
  const seg = (passos: number) =>
    // segundos a 1 casa quando o valor cabe (0,5 s), a 2 quando o passo o exige (0,52 s)
    `${fmt(passos / PASSOS_POR_SEGUNDO, (passos / PASSOS_POR_SEGUNDO) * 10 === Math.round((passos / PASSOS_POR_SEGUNDO) * 10) ? 1 : 2)} s`
  const dur = (passos: number) => `${seg(passos)} (${Math.round(passos)} passos)`
  const p = (v: number) => fmt(v, v * 100 === Math.round(v * 100) ? 2 : 3)
  if (modo === "rajadas" && params.p !== undefined && params.duracao !== undefined)
    return `p ${p(params.p)} por passo · rajadas de ${dur(params.duracao)}${params.u_max !== undefined ? ` até ${fmt(params.u_max, 1)} m/s` : ""}`
  if (modo === "aleatoria" && params.p !== undefined && params.duracao !== undefined)
    return `p ${p(params.p)} por passo · rajadas de ${dur(params.duracao)} · direção e força sorteadas`
  if (modo === "dryden" && params.sigma !== undefined)
    return `turbulência σ ${fmt(params.sigma, 2)} · L ${fmt(params.L, 1)} m · v_min ${fmt(params.v_min, 1)} m/s`
  if (modo === "frente" && params.vel !== undefined)
    return `degrau para ${fmt(params.vel, 2)} m/s · ${fmtGraus(params.azimute)} · ${fmtGraus(params.elevacao)}`
  if (modo === "rajada_agora" && params.u !== undefined)
    return `rajada de ${fmt(params.u, 2)} m/s${params.duracao !== undefined ? ` por ${dur(params.duracao)}` : ""}`
  if (Object.keys(params).length === 0)
    return `${ROTULOS_MODO_ESTADO.parado} · sem parâmetros em vigor — escolhe um modo para os aplicar`
  return fmtParams(params) // fallback cru (params que o painel não conhece): nunca se escondem
}

interface LinhaSliderProps {
  id: string
  rotulo: string
  /**
   * `null` = SEM DADOS: o valor mostra «—» e o slider fica desativado (estado honesto — nunca se
   * finge um número). Os painéis de vento passam sempre números.
   */
  valor: number | null
  min: number
  max: number
  passo: number
  sufixo: string
  casas?: number
  /** Casas decimais dos extremos (min/max) por baixo do trilho; por omissão 0 (como sempre). */
  casasExtremos?: number
  /** `data-testid` do contentor da linha (provas de DOM); sem valor não escreve atributo nenhum. */
  testeId?: string
  onChange: (valor: number) => void
}

export function LinhaSlider({
  id,
  rotulo,
  valor,
  min,
  max,
  passo,
  sufixo,
  casas = 1,
  casasExtremos = 0,
  testeId,
  onChange,
}: LinhaSliderProps) {
  return (
    <div className="flex flex-col gap-1.5" data-testid={testeId}>
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-xs font-medium">
          {rotulo}
        </label>
        <span
          className="font-mono text-xs tabular-nums"
          data-testid={testeId ? `${testeId}-valor` : undefined}
        >
          {valor === null ? "—" : fmt(valor, casas)}
          {valor === null ? "" : sufixo}
        </span>
      </div>
      <Slider
        id={id}
        min={min}
        max={max}
        step={passo}
        value={[valor ?? min]}
        disabled={valor === null}
        onValueChange={(v) => onChange(Array.isArray(v) ? (v[0] ?? min) : v)}
        aria-label={rotulo}
      />
      <div className="flex justify-between font-mono text-[0.6rem] text-muted-foreground">
        <span>{fmt(min, casasExtremos)}</span>
        <span>{fmt(max, casasExtremos)}</span>
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

/** Debounce do live-apply dos params (ms): o servidor só vê a última edição de uma rajada de eventos. */
const ATRASO_PARAMS_MS = 300

/** Params que o POST leva, por modo contínuo — exatamente o mesmo contrato da troca de modo. */
function paramsDoModoContinuo(
  modo: Exclude<ModoContinuo, "nenhum">,
  v: {
    p: number
    duracao: number
    u_max: number
    sigma: number
    L: number
    v_min: number
  }
): Record<string, number> {
  if (modo === "rajadas")
    return { p: v.p, duracao: Math.round(v.duracao), u_max: v.u_max }
  if (modo === "aleatoria") return { p: v.p, duracao: Math.round(v.duracao) }
  return { sigma: v.sigma, L: v.L, v_min: v.v_min }
}

/** Assinatura estável de um envio (modo + params) — evita reenviar o que o servidor já tem. */
function assinaturaParams(
  modo: ModoContinuo,
  params: Record<string, number>
): string {
  return `${modo} ${JSON.stringify(params)}`
}

/** Texto curto dos params vivos, para o toast do live-apply. */
function descreverParams(
  modo: Exclude<ModoContinuo, "nenhum">,
  params: Record<string, number>
): string {
  if (modo === "rajadas")
    return `p=${fmt(params.p, 3)}, duração=${params.duracao} passos, u_max=${fmt(params.u_max, 1)} m/s`
  if (modo === "aleatoria")
    return `p=${fmt(params.p, 3)}, duração=${params.duracao} passos`
  return `σ=${fmt(params.sigma, 2)}, L=${fmt(params.L, 1)}, v_min=${fmt(params.v_min, 1)} m/s`
}

interface DinamicoProps {
  dinamico: VentoDinamico
  /** Modo que a TELEMETRIA reporta na última linha (é o que a física está a fazer). */
  modoTelemetria: ModoVentoDinamico
  /**
   * Vento REAL agora, para a faixa de estado distinguir «armado» de «a bater» (achados 1+2 da avaliação
   * de UX): `total` = ‖vento_vec‖ da telemetria (`null` sem telemetria — nunca se inventa rajada),
   * `base` = o vento base comandado e `modo` = o `vento_modo` real. Preenchido pelo `ControlosVento`.
   */
  ventoAgora: { total: number | null; base: number; modo: string }
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
  /**
   * Um apply do live-apply foi SUPRIMIDO por estar velho (o servidor já não tinha o modo ativo — paragem de
   * outro cliente/aba): o utilizador tem de saber que a edição não foi aplicada, e o painel volta a mostrar
   * o estado do servidor.
   */
  onApplySuprimido: (motivo: string, modo: string) => void
}

/**
 * Sub-painel do vento dinâmico (ronda 10): um modo CONTÍNUO (RAJADAS, ALEATÓRIA ou DRYDEN), dois instantâneos (RAJADA AGORA, FRENTE AGORA) e o reset `{"modo":"nenhum","ativo":false}`.
 * Com um modo contínuo ativo, editar os params reenvia-os (live-apply com debounce, sem reiniciar nada).
 */
function Dinamico({
  dinamico,
  modoTelemetria,
  ventoAgora,
  ligado,
  fase,
  emCurso,
  selecao,
  onEnviar,
  onApplySuprimido,
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
  /**
   * Motivo do último apply SUPRIMIDO por estar velho (outro cliente/aba parou o modo antes de o debounce
   * disparar). Fica À VISTA no painel: o dono tem de saber que a edição não chegou ao servidor, em vez de
   * ficar com um campo a mostrar um valor que a física não tem.
   */
  const [suprimido, setSuprimido] = useState<string | null>(null)

  const modoContinuo: ModoContinuo =
    dinamico.ativo &&
    (dinamico.modo === "rajadas" ||
      dinamico.modo === "aleatoria" ||
      dinamico.modo === "dryden")
      ? dinamico.modo
      : "nenhum"
  const rajadaEmCurso = dinamico.ativo && modoTelemetria === "rajada_agora"
  const frenteAtiva = dinamico.ativo && dinamico.modo === "frente"
  const ocupado = emCurso !== null
  const desativado = !ligado || ocupado

  // FAIXA DE ESTADO (avaliação `pesquisas/ux-rajadas-avaliacao.json`, achados 1+2): o estado vem SEMPRE
  // da física — `modoTelemetria` (o `vento_modo` real) e o desvio do vento real face ao base. Sem
  // telemetria (`total === null`) não há intensidade a mostrar e a rajada só se afirma se a telemetria
  // disser `rajada_agora`: nunca se inventa uma rajada que a física não tem.
  const intensidade =
    ventoAgora.total === null
      ? 0
      : intensidadeRajada(ventoAgora.total, ventoAgora.base)
  const faixa = estadoFaixa({
    modoContinuo,
    modoTelemetria: modoTelemetria || ventoAgora.modo,
    intensidade,
  })
  // Instantâneos em curso (comando a caminho ou já na física): é aí que o progresso da duração
  // COMANDADA aparece (não é medição — é o que foi pedido ao servidor).
  const rajadaInstantanea = rajadaEmCurso || emCurso === "rajada"
  const frenteInstantanea = frenteAtiva || emCurso === "frente"
  const duracaoRajadaS = Math.round(duracaoRajada) / PASSOS_POR_SEGUNDO
  const ativo = modoContinuo !== "nenhum" || rajadaEmCurso || frenteAtiva

  const paramsRajadas = { p, duracao: Math.round(duracaoRajadas), u_max: uMax }
  // `aleatoria` só leva p e duração: a força sai de U[0, 5] m/s e a direção de [0, 360) × ±90° no env.
  const paramsAleatoria = { p, duracao: Math.round(duracaoRajadas) }
  const paramsDryden = { sigma, L: comprimento, v_min: vMin }

  /** Assinatura do último envio de params (evita repetir o que já lá está e o eco da telemetria). */
  const paramsEnviados = useRef<string | null>(null)
  /** Adoção única dos params que o backend já tem (espelha o `sincronizado` dos sliders base). */
  const paramsAdotados = useRef(false)
  const enviarRef = useRef(onEnviar)
  useEffect(() => {
    enviarRef.current = onEnviar
  }, [onEnviar])

  /**
   * Regista um envio explícito (troca de modo): a partir daí os valores locais são a fonte de verdade —
   * o live-apply não repete o que acabou de ir e a adoção do eco do backend fica desligada.
   */
  const registarEnvio = (
    modo: Exclude<ModoContinuo, "nenhum">,
    params: Record<string, number>
  ) => {
    paramsEnviados.current = assinaturaParams(modo, params)
    paramsAdotados.current = true
  }

  /**
   * ADOÇÃO (uma vez) dos params vivos do backend: abrir a página com um modo a correr mostra o que a
   * física está a fazer, em vez de impor os defaults. A assinatura adotada fica registada, por isso a
   * adoção não dispara nenhum POST. As chaves que o backend não manda caem nos defaults do modo (nunca
   * nos valores locais) para este efeito não depender do que ele próprio escreve.
   */
  useEffect(() => {
    if (!dinamico.ativo || modoContinuo === "nenhum") return
    const vivos = dinamico.params
    if (Object.keys(vivos).length === 0) return
    // O guarda do `ref` fica imediatamente antes da escrita: é o padrão «semear do backend UMA vez».
    if (paramsAdotados.current) return
    paramsAdotados.current = true
    const v = {
      p: vivos.p ?? PARAMS_DINAMICOS_PADRAO.rajadas.p,
      duracao: vivos.duracao ?? PARAMS_DINAMICOS_PADRAO.rajadas.duracao,
      u_max: vivos.u_max ?? PARAMS_DINAMICOS_PADRAO.rajadas.u_max,
      sigma: vivos.sigma ?? PARAMS_DINAMICOS_PADRAO.dryden.sigma,
      L: vivos.L ?? PARAMS_DINAMICOS_PADRAO.dryden.L,
      v_min: vivos.v_min ?? PARAMS_DINAMICOS_PADRAO.dryden.v_min,
    }
    paramsEnviados.current = assinaturaParams(
      modoContinuo,
      paramsDoModoContinuo(modoContinuo, v)
    )
    setP(v.p)
    setDuracaoRajadas(v.duracao)
    setUMax(v.u_max)
    setSigma(v.sigma)
    setComprimento(v.L)
    setVMin(v.v_min)
  }, [dinamico, modoContinuo])

  /**
   * LIVE-APPLY dos params do modo CONTÍNUO ativo (rajadas · aleatórias · Dryden): editar um campo
   * reenvia o modo ativo com os valores atuais, com debounce — a física acompanha sem cliques. Só
   * corre com um modo ativo e ligação viva (com PARADO os valores ficam guardados e vão no POST da
   * troca de modo) e nunca repete a mesma assinatura, para o eco da telemetria não gerar um ciclo.
   *
   * O apply agendado passa pelo `agendarEnvioDinamico` (`lib/paragem.ts`): fica registado no módulo das
   * paragens, guarda a ÉPOCA do agendamento e confere-a ao disparar. Uma paragem LOCAL — PARAR VENTO,
   * PARAR DINÂMICO ou o toggle PARADO — incrementa a época de forma síncrona no clique, CANCELA este
   * temporizador e bloqueia o live-apply, logo o modo não pode voltar a ligar-se depois de parar.
   *
   * Uma paragem de OUTRO cliente (um `POST /api/parar` cru, o botão de outra aba) não mexe nesta época — é
   * estado de módulo por *realm*. Para essa, o apply é REVALIDADO contra o servidor ao disparar (leitura
   * barata de `/api/state`, registada pelo `useSim`): sem o modo ativo lá, o comando é suprimido e o
   * painel avisa (`onApplySuprimido`) em vez de ressuscitar o modo que outro cliente parou.
   *
   * O `clearTimeout` devolvido continua a fazer o seu trabalho quando o modo muda; o módulo cobre a janela
   * em que o polling ainda não voltou.
   */
  useEffect(() => {
    if (modoContinuo === "nenhum") {
      paramsEnviados.current = null
      return
    }
    if (!ligado) return
    // PARADO manda em tudo: com o live-apply bloqueado (houve uma paragem e ainda não veio nenhum comando
    // novo que ligue um modo contínuo) não se agenda NADA — nem se semeia a linha de base. Sem isto, uma
    // edição feita enquanto o painel ainda mostra o modo antigo (o poll atrasa ~350 ms) ressuscitava o
    // modo que já tinha sido parado no servidor.
    if (enviosDinamicosBloqueados()) return
    const params = paramsDoModoContinuo(modoContinuo, {
      p,
      duracao: duracaoRajadas,
      u_max: uMax,
      sigma,
      L: comprimento,
      v_min: vMin,
    })
    const assinatura = assinaturaParams(modoContinuo, params)
    // Sem linha de base conhecida (modo ligado por fora do painel) assume-se o que está à vista e não se
    // escreve nada: o painel só empurra params a partir de uma edição do utilizador.
    if (paramsEnviados.current === null) {
      paramsEnviados.current = assinatura
      return
    }
    if (paramsEnviados.current === assinatura) return
    return agendarEnvioDinamico(
      () => {
        paramsEnviados.current = assinatura
        setSuprimido(null) // o apply saiu: o aviso de «não aplicado» já não se aplica
        enviarRef.current(
          { modo: modoContinuo, ativo: true, params },
          "params",
          `${ROTULOS_MODO_ESTADO[modoContinuo]} em curso: parâmetros aplicados (${descreverParams(modoContinuo, params)})`
        )
      },
      ATRASO_PARAMS_MS,
      // REVALIDAÇÃO multi-cliente: ao disparar, o front confirma no servidor que este modo ainda está
      // ativo. Se OUTRO cliente (ou outra aba) parou o vento entretanto, o apply é suprimido em vez de
      // ressuscitar o modo — e o aviso fica no painel E no `onApplySuprimido` (nada de um painel a mostrar
      // um valor que o servidor não tem).
      {
        modo: modoContinuo,
        aoSuprimir: (motivo) => {
          setSuprimido(motivo)
          onApplySuprimido(motivo, modoContinuo)
        },
      }
    )
  }, [modoContinuo, ligado, p, duracaoRajadas, uMax, sigma, comprimento, vMin, onApplySuprimido])

  const trocarModo = (alvo: ModoContinuo) => {
    if (alvo === modoContinuo) return
    setSuprimido(null) // um comando novo do utilizador limpa o aviso do apply que ficou velho
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
        `${ROTULOS_MODO_ESTADO.rajadas} ligadas (${resumoParamsDinamicos("rajadas", paramsRajadas)})`
      )
      registarEnvio("rajadas", paramsRajadas)
      return
    }
    if (alvo === "aleatoria") {
      onEnviar(
        { modo: "aleatoria", ativo: true, params: paramsAleatoria },
        "modo",
        `${ROTULOS_MODO_ESTADO.aleatoria} ligadas (${resumoParamsDinamicos("aleatoria", paramsAleatoria)}; direção e força sorteadas a cada rajada: 0–5 m/s, 0–360°, ±90°, misturadas com o vento base pelo envelope)`
      )
      registarEnvio("aleatoria", paramsAleatoria)
      return
    }
    onEnviar(
      { modo: "dryden", ativo: true, params: paramsDryden },
      "modo",
      `${ROTULOS_MODO_ESTADO.dryden} ligada (${resumoParamsDinamicos("dryden", paramsDryden)})`
    )
    registarEnvio("dryden", paramsDryden)
  }

  return (
    <section
      aria-label="Vento dinâmico"
      data-testid="painel-dinamico"
      // `data-ativo` (achado 4): styling/estado de destaque quando há dinâmica a correr — é a
      // salvaguarda anti-esquecimento dentro do painel (o selo global na barra crítica vem depois).
      data-ativo={ativo ? "sim" : "nao"}
      className="flex flex-col gap-3 rounded-lg border border-border/70 bg-muted/20 p-3"
    >
      <div className="flex items-center gap-1.5">
        <Zap className="size-3.5" aria-hidden="true" />
        <h4 className="text-[0.7rem] tracking-wide uppercase">
          vento dinâmico
        </h4>
      </div>

      {/*
        FAIXA DE ESTADO (avaliação `pesquisas/ux-rajadas-avaliacao.json`, achados 1+2 = os críticos): o
        ESTADO do sistema é a primeira coisa do painel, sticky, em linguagem de operador e com os MESMOS
        rótulos do segmented toggle (achado 3 — léxico único). 3 estados EXAUSTIVOS:
          · PARADO (cinza, ponto parado) — sem modo contínuo e sem instantâneo;
          · A CORRER — <MODO> (primário, ponto pulsante) — modo ARMADO (as rajadas são sorteadas por p);
          · RAJADA EM CURSO +X,X m/s (âmbar) — há rajada a bater AGORA (telemetria: `rajada_agora` ou
            |‖vento_vec‖ − base| > 0,05 m/s), com o modo de origem ao lado.
        `sticky top-0` + fundo sólido (achado 4): com o modo ativo o estado não pode passar despercebido
        nem desaparecer com o scroll dentro do painel.
      */}
      <div
        data-testid="dinamico-faixa-estado"
        data-estado={faixa.estado}
        data-modo={faixa.modo}
        role="status"
        className={`sticky top-0 z-10 -mx-3 -mt-3 flex flex-wrap items-center gap-2 rounded-t-lg border-b px-3 py-2 text-[0.85rem] font-medium ${
          faixa.estado === "parado"
            ? "border-border/70 bg-background text-muted-foreground"
            : faixa.estado === "a_correr"
              ? "border-primary/40 bg-background text-primary"
              : "border-amber-500/50 bg-background text-amber-600 dark:text-amber-400"
        }`}
      >
        <motion.span
          aria-hidden="true"
          className={`size-2 shrink-0 rounded-full ${
            faixa.estado === "parado"
              ? "bg-muted-foreground"
              : faixa.estado === "a_correr"
                ? "bg-primary"
                : "bg-amber-500"
          }`}
          animate={
            faixa.estado === "parado"
              ? { opacity: 1 }
              : faixa.estado === "a_correr"
                ? { opacity: [1, 0.25, 1] }
                : { scale: [1, 1.35, 1] }
          }
          transition={
            faixa.estado === "parado"
              ? { duration: 0.2 }
              : faixa.estado === "a_correr"
                ? { duration: 1.4, repeat: Infinity, ease: "easeInOut" }
                : { duration: 0.7, repeat: Infinity, ease: "easeInOut" }
          }
        />
        <span data-testid="dinamico-faixa-texto">
          {faixa.estado === "parado"
            ? ROTULOS_MODO_ESTADO.parado
            : faixa.estado === "a_correr"
              ? `A CORRER — ${faixa.modo}`
              : ventoAgora.total === null
                ? "RAJADA EM CURSO"
                : `RAJADA EM CURSO +${fmt(faixa.intensidade, 1)} m/s`}
        </span>
        {/* O selo de modo (o antigo `estado-dinamico`) continua a existir: rótulo do modo ativo, com
            o nome técnico só no tooltip (achado 3). */}
        <span
          data-testid="estado-dinamico"
          title={`modo técnico: ${
            modoTelemetria || (faixa.estado === "parado" ? "nenhum" : dinamico.modo)
          }`}
          className={`ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[0.6rem] ${
            faixa.estado === "parado"
              ? "bg-muted text-muted-foreground"
              : faixa.estado === "a_correr"
                ? "bg-primary/10 text-primary"
                : "bg-amber-500/15 text-amber-600 dark:text-amber-400"
          }`}
        >
          {faixa.modo}
        </span>
      </div>

      {/*
        PROGRESSO dos instantâneos (achado 1): enquanto a rajada/frente estão a bater, o painel mostra o
        que está a acontecer e por quanto tempo — a DURAÇÃO COMANDADA (o valor pedido ao servidor,
        `duracaoRajada` passos a 50 Hz), rotulada como tal para nunca fingir que é uma medição.
      */}
      {rajadaInstantanea || frenteInstantanea ? (
        <div
          data-testid="dinamico-progresso"
          data-tipo={rajadaInstantanea ? "rajada" : "frente"}
          role="status"
          className="flex flex-col gap-1 rounded-md border border-border/70 bg-muted/30 px-2 py-1.5"
        >
          <div className="flex flex-wrap items-baseline gap-1.5 text-[0.75rem]">
            <span className="font-medium">
              {rajadaInstantanea
                ? `RAJADA AGORA · ~${fmt(duracaoRajadaS, 1)} s`
                : `${ROTULOS_MODO_ESTADO.frente} · degrau mantido até nova ordem`}
            </span>
            <span
              className="text-[0.65rem] text-muted-foreground"
              title={`o valor pedido ao servidor: ${Math.round(duracaoRajada)} passos de decisão a 50 Hz`}
            >
              duração comandada ({Math.round(duracaoRajada)} passos a 50 Hz)
            </span>
          </div>
          {rajadaInstantanea ? (
            <div
              aria-hidden="true"
              className="h-1 w-full overflow-hidden rounded-full bg-muted"
            >
              <motion.div
                key={`${faixa.modo}-${Math.round(duracaoRajada)}`}
                className="h-full rounded-full bg-amber-500"
                initial={{ width: "0%" }}
                animate={{ width: "100%" }}
                transition={{ duration: duracaoRajadaS, ease: "linear" }}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {/*
        PARAMS em 2 linhas com unidades naturais (achado 5): nada de `params {p: 0.40, ...}` em
        monoespaço — «p 0,40 por passo · rajadas de 0,5 s (25 passos) até 3,0 m/s» e a nota única. Os
        valores vêm do servidor tal e qual (sem arredondar para "ficar bonito": p a 2 casas e 3 quando o
        passo de 0,005 o exige; segundos a 1 casa e 2 idem) e o cru fica no `title`.
      */}
      <div
        data-testid="dinamico-params-resumo"
        title={`params em vigor: ${fmtParams(dinamico.params)}`}
        className="flex flex-col gap-0.5"
      >
        <p className="text-[0.7rem] text-muted-foreground">
          {resumoParamsDinamicos(dinamico.modo, dinamico.params)}
        </p>
        <p className="text-[0.65rem] text-muted-foreground">
          aplica-se sem reiniciar o episódio
        </p>
      </div>

      <SegmentedToggle
        value={modoContinuo}
        onChange={(v) => trocarModo(v as ModoContinuo)}
        ariaLabel="modo dinâmico contínuo"
        className="w-full"
      >
        {/* Rótulos = ROTULOS_MODO_ESTADO (léxico único do painel, achado 3): os MESMOS da faixa de
            estado; o nome técnico fica no `title`. */}
        <SegmentedToggleOption value="nenhum">
          {ROTULOS_MODO_ESTADO.parado}
        </SegmentedToggleOption>
        <SegmentedToggleOption value="rajadas">
          {ROTULOS_MODO_ESTADO.rajadas}
        </SegmentedToggleOption>
        <SegmentedToggleOption value="aleatoria">
          {ROTULOS_MODO_ESTADO.aleatoria}
        </SegmentedToggleOption>
        <SegmentedToggleOption value="dryden">
          {ROTULOS_MODO_ESTADO.dryden}
        </SegmentedToggleOption>
      </SegmentedToggle>

      <p className="text-[0.6rem] text-muted-foreground">
        com um modo ativo, editar um campo aplica-o automaticamente (≈300
        ms) — sem reiniciar o episódio; com PARADO os valores ficam guardados
        para a próxima ativação
      </p>

      {/*
        ESTADO HONESTO do apply: a edição foi suprimida por estar velha (o servidor já não tinha este modo
        ativo — paragem de outro cliente/aba). Sem isto o painel ficava com um campo a mostrar um valor que
        a física não tem, sem dizer nada.
      */}
      {suprimido !== null ? (
        <p
          data-testid="apply-suprimido"
          role="status"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1 text-[0.65rem] text-destructive"
        >
          edição não aplicada — {suprimido}
        </p>
      ) : null}

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
        ) : modoContinuo === "aleatoria" ? (
          <motion.div
            key="aleatoria"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ ...ui }}
            className="flex flex-wrap gap-3"
            data-testid="params-aleatoria"
          >
            <CampoNumerico
              id="aleatoria-p"
              rotulo="p (probabilidade)"
              valor={p}
              min={0}
              max={1}
              passo={0.005}
              onChange={setP}
            />
            <CampoNumerico
              id="aleatoria-duracao"
              rotulo="duração"
              valor={duracaoRajadas}
              min={1}
              max={200}
              passo={1}
              sufixo="passos"
              dica={`${fmt(duracaoRajadas / PASSOS_POR_SEGUNDO, 2)} s @ 50 Hz`}
              onChange={setDuracaoRajadas}
            />
            <p className="w-full text-[0.6rem] text-muted-foreground">
              cada rajada sorteia a direção e a força de novo: 0–5 m/s ·
              0–360° · ±90° — no pico do envelope o vento é a rajada sorteada e
              nas pontas fica junto do vento base (nunca passa 5 m/s); o u_max
              não limita este modo
            </p>
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
            ao vento base · ALEATÓRIA = direção e força sorteadas de novo a
            cada rajada (0–5 m/s, 0–360°, ±90°) e misturadas com o vento base
            pelo envelope (no pico o vento é a rajada sorteada) · DRYDEN =
            turbulência que passeia em torno dele. Os params ficam editáveis no
            modo escolhido.
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
          announce={rajadaEmCurso ? "RAJADA EM CURSO" : undefined}
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
              : ROTULOS_MODO_ESTADO.rajada_agora}
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
          announce={frenteAtiva ? "FRENTE AGORA ativa — clica para desligar" : undefined}
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
            : ROTULOS_MODO_ESTADO.frente}
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

interface ControlosVentoProps {
  vento: VentoEstado
  /** Vetor do vento em vigor (telemetria `vento_vec`), ou `null`. */
  vec: [number, number, number] | null
  dinamico: VentoDinamico
  /** Modo reportado pela última linha de telemetria (o que a física está mesmo a fazer). */
  modoTelemetria: ModoVentoDinamico
  estado: EstadoEpisodio
  /** Continuidade do backend: com `loop` ligado NÃO há «terminado» a exigir REINICIAR. */
  loop: boolean
  ligado: boolean
  faseVento: FaseVento
  faseDinamico: FaseVento
  emCurso: AlvoDinamico | null
  onAplicarVento: (corpo: CorpoVento) => void
  onPararVento: () => void
  onVentoDinamico: (
    corpo: CorpoVentoDinamico,
    alvo: AlvoDinamico,
    descricao: string
  ) => void
  /** Apply do live-apply suprimido por estar velho (paragem de outro cliente/aba): avisa o utilizador. */
  onApplySuprimido: (motivo: string, modo: string) => void
}

export function ControlosVento({
  vento,
  vec,
  dinamico,
  modoTelemetria,
  estado,
  loop,
  ligado,
  faseVento,
  faseDinamico,
  emCurso,
  onAplicarVento,
  onPararVento,
  onVentoDinamico,
  onApplySuprimido,
}: ControlosVentoProps) {
  const [forca, setForca] = useState(0)
  const [azimute, setAzimute] = useState(0)
  const [elevacao, setElevacao] = useState(0)
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

  // «Sem reinício» = o backend está com o loop desligado e o episódio fechou: a física CONTINUA no estado
  // em que ficou (não há nada de errado nem nada a exigir) — o cartão só leva uma marca discreta, sem
  // alarme vermelho. Com `loop` ligado o episódio seguinte arranca sozinho e não há marca nenhuma.
  const semReinicio = estado === "episodio_terminado" && !loop
  const selecao: CorpoVento = { vel: forca, azimute, elevacao }
  // Vento REAL agora, para a faixa de estado do `Dinamico` distinguir «armado» de «a bater»: `total` é
  // ‖vento_vec‖ da telemetria (`null` sem telemetria — não há rajada a inventar), `base` o vento base
  // comandado e `modo` o `vento_modo` real. Tudo já chegava a este componente (App.tsx intacto).
  const ventoAgora: { total: number | null; base: number; modo: string } = {
    total: vec === null ? null : Math.hypot(vec[0], vec[1], vec[2]),
    base: vento.vel,
    modo: modoTelemetria,
  }

  return (
    <Card
      className={`gap-4 ${semReinicio ? "ring-1 ring-border" : ""}`}
      data-testid="painel-controlos"
    >
      <CardHeader className="gap-1">
        <CardTitle className="text-sm font-medium">
          Controlos de vento
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          vento físico em tempo real · o site nunca reinicia sozinho
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
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
              title="põe o vento a 0 m/s e desliga o vento dinâmico (rajadas, rajada agora, frente e turbulência) no mesmo pedido"
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
          ventoAgora={ventoAgora}
          ligado={ligado}
          fase={faseDinamico}
          emCurso={emCurso}
          selecao={selecao}
          onEnviar={onVentoDinamico}
          onApplySuprimido={onApplySuprimido}
        />

        <p className="px-1 text-[0.65rem] text-muted-foreground">
          polling GET /api/sim a 2,9 Hz · ações: POST /api/vento ·
          /api/vento-dinamico
        </p>
      </CardContent>
    </Card>
  )
}

export interface ControlosEpisodioProps {
  estado: EstadoEpisodio
  ep: number
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
 * REINICIAR (hold de 1 s) + LOOP — os controlos críticos do episódio, visíveis em QUALQUER secção
 * (barra fixa do topo em `App.tsx`). O site nunca reinicia sozinho: `/api/reiniciar` é exclusivo deste
 * botão; com o LOOP ligado quem reinicia é o backend.
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
  /** Episódio fechado E sem reinício automático: a física CONTINUA (não congela) e nada é exigido — o
   *  REINICIAR é a única forma de começar outro episódio, mas não é uma emergência. */
  const semReinicio = estado === "episodio_terminado" && !loop

  return (
    <div
      data-testid="controlos-episodio"
      className={compacto ? "flex flex-wrap items-center gap-x-3 gap-y-2" : "flex flex-col gap-2"}
    >
      <div className="relative">
        {semReinicio ? (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute -inset-1 rounded-full ring-1 ring-border"
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
          className={
            compacto
              ? "h-9! w-auto! px-4! text-xs!"
              : "h-14! w-full! text-base! font-semibold! tracking-wide"
          }
        >
          <RotateCcw
            className={compacto ? "size-3.5" : "size-5"}
            aria-hidden="true"
          />
          {aReiniciar
            ? "A REINICIAR…"
            : compacto
              ? "REINICIAR"
              : "REINICIAR (manter 1 s)"}
        </HoldToConfirmButton>
      </div>

      <div
        className={
          compacto
            ? "flex items-center gap-2"
            : "mt-2 flex items-center justify-between gap-3"
        }
      >
        <div className={compacto ? "hidden flex-col sm:flex" : "flex flex-col"}>
          <span className="text-xs font-medium">CONTINUIDADE</span>
          {compacto ? null : (
            <span className="text-[0.65rem] text-muted-foreground">
              sem reinício por omissão · a física continua no fim do episódio e
              só o REINICIAR recomeça; CONTÍNUO reinicia sozinho (ep+1)
            </span>
          )}
        </div>
        <SegmentedToggle
          value={loop ? "continuo" : "sem_reinicio"}
          onChange={(v) => onLoop(v === "continuo")}
          ariaLabel="continuidade dos episódios (contínuo ou sem reinício)"
          className="shrink-0"
        >
          <SegmentedToggleOption
            value="sem_reinicio"
            className={compacto ? "px-3! py-1.5! text-xs! sm:px-4! sm:py-2! sm:text-sm!" : undefined}
          >
            SEM REINÍCIO
          </SegmentedToggleOption>
          <SegmentedToggleOption
            value="continuo"
            className={compacto ? "px-3! py-1.5! text-xs! sm:px-4! sm:py-2! sm:text-sm!" : undefined}
          >
            CONTÍNUO
          </SegmentedToggleOption>
        </SegmentedToggle>
      </div>

      <p
        id="reiniciar-ajuda"
        className={
          compacto ? "sr-only" : "text-[0.65rem] text-muted-foreground"
        }
      >
        carrega e mantém ~1 s: o preenchimento confirma · POST /api/reiniciar
      </p>
      {compacto ? (
        <span className="sr-only">
          episódio {fmt(ep, 0)} ·{" "}
          {estado === "episodio_terminado" ? "terminado" : "a correr"} ·
          {loop ? "modo contínuo" : "sem reinício (a física continua; só o REINICIAR recomeça)"} · ligação{" "}
          {ligado ? "ativa" : "inativa"}
        </span>
      ) : null}
    </div>
  )
}
