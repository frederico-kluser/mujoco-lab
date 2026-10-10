/**
 * Bloco «Bateria» da PLANTA REAL (secção «Bordo» e «Tudo») + o indicador compacto da barra fixa.
 *
 * Tudo vem da chave `bateria` de cada linha da telemetria (o pack físico do `lab/drone_rpi`, que persiste
 * entre REINICIARs e entre sessões): SoC REAL e o SoC ESTIMADO pelo RPi (OCV em repouso no arranque +
 * contagem de Coulomb com a corrente MEDIDA pelo monitor — não conhece o desgaste, por isso diverge do real
 * quando o pack envelhece), tensão/corrente/potência, autonomia, SoH/ciclos, temperatura, R₀, alerta de
 * tensão e o selo REFORMAR (SoH ≤ 80 %). Estados honestos: o que não vier fica «—», nada é inventado.
 *
 * Comandos (`POST /api/bateria`, pela fila de controlos do `use-sim`): **RECARREGAR** (fecha o ciclo com
 * desgaste e volta a 100 %) é um `multi-state-button` como o APLICAR VENTO; **PACK NOVO** apaga o histórico
 * de desgaste do pack — é destrutivo, por isso usa o `hold-to-confirm` (manter 1 s), o mesmo padrão do
 * REINICIAR. O servidor só confirma o PEDIDO (`seq`); o efeito chega na telemetria (SoC, «último ciclo»).
 *
 * Cascata: passo 2 — `multi-state-button`, `hold-to-confirm`; passo 3 — `Card`, `ProgressBar`,
 * `AnimatedNumber`, `Button`; passo 4 SÓ na curva de descarga: o `sparkline` do catálogo escala com
 * `max(1, max−min)` (um SoC de 99,3→98,9 % sairia uma linha plana) e só leva uma série — aqui são duas
 * (real sólida, estimado tracejado: identidade por traço + legenda, nunca só por cor), com eixo único
 * em %, grelha hairline e leitura por cursor/teclado (as regras de marcas da skill de dataviz).
 */

import {
  useId,
  useMemo,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react"
import {
  BatteryFull,
  BatteryLow,
  BatteryMedium,
  BatteryWarning,
  Check,
  Loader2,
  PackagePlus,
  PlugZap,
  TriangleAlert,
} from "lucide-react"

import { AnimatedNumber } from "@/components/motion-ui/animated-number"
import { HoldToConfirmButton } from "@/components/motion-ui/hold-to-confirm"
import { MultiStateButton } from "@/components/motion-ui/multi-state-button"
import { ProgressBar } from "@/components/motion-ui/progress-bar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { TomAviso } from "@/components/sim/avisos"
import { FOCUS_RING } from "@/components/sim/estilo"
import type { AcaoBateria, RespostaBateria } from "@/lib/api"
import {
  fmt,
  fmtInteiro,
  fmtPct,
  fmtSinal,
  rotuloQuimica,
  type AlertaBateria,
  type BateriaTelemetria,
  type LinhaSim,
  type UltimoCicloBateria,
} from "@/lib/sim"

// ------------------------------------------------------------------------------ alerta · ícone

/** Texto e estilo de cada alerta (tokens do tema; «crítica» é a forma CHEIA, mais forte). */
const ALERTA: Record<
  Exclude<AlertaBateria, "nenhum">,
  { rotulo: string; detalhe: string; classe: string; anel: string }
> = {
  tensao_baixa: {
    rotulo: "TENSÃO BAIXA",
    detalhe: "abaixo da tensão de pouso da química — pousar",
    classe:
      "bg-destructive/10 font-medium text-destructive ring-1 ring-destructive/40",
    anel: "ring-1 ring-destructive/60",
  },
  critica: {
    rotulo: "CRÍTICA",
    detalhe: "abaixo da tensão de corte — risco de brownout",
    classe: "bg-destructive font-semibold text-background",
    anel: "ring-2 ring-destructive",
  },
}

/** Alerta ativo (ignora `nenhum` e o desconhecido). */
function alertaAtivo(
  bateria: BateriaTelemetria | null
): Exclude<AlertaBateria, "nenhum"> | null {
  const a = bateria?.alerta ?? null
  return a === "tensao_baixa" || a === "critica" ? a : null
}

/** Ícone pelo estado: aviso com alerta, senão cheio/médio/baixo pelo SoC real (componente ESTÁTICO). */
function IconeBateria({
  bateria,
  className,
}: {
  bateria: BateriaTelemetria | null
  className: string
}) {
  const soc = bateria?.soc ?? null
  if (alertaAtivo(bateria) !== null)
    return <BatteryWarning className={className} aria-hidden="true" />
  if (soc === null || (soc >= 0.33 && soc < 0.66))
    return <BatteryMedium className={className} aria-hidden="true" />
  return soc >= 0.66 ? (
    <BatteryFull className={className} aria-hidden="true" />
  ) : (
    <BatteryLow className={className} aria-hidden="true" />
  )
}

// ------------------------------------------------------------------------- indicador da barra

interface IndicadorBateriaProps {
  bateria: BateriaTelemetria | null
}

/**
 * Indicador COMPACTO para a barra fixa do topo (só na planta real): SoC % + alerta + REFORMAR. O SoC muda
 * a cada leitura, por isso o selo é `aria-live="off"` (a faixa é uma região viva: sem isto um leitor de
 * ecrã leria o SoC a cada 0,35 s); a MUDANÇA de alerta anuncia-se num texto só para leitores de ecrã.
 */
export function IndicadorBateria({ bateria }: IndicadorBateriaProps) {
  const alerta = alertaAtivo(bateria)
  const classe =
    alerta === null
      ? "bg-background/70 text-foreground ring-1 ring-border"
      : ALERTA[alerta].classe
  return (
    <>
      <span
        data-testid="indicador-bateria"
        data-alerta={alerta ?? "nenhum"}
        aria-live="off"
        title={`bateria (planta real): SoC real ${fmtPct(bateria?.soc ?? null, 2)} · estimado pelo RPi ${fmtPct(bateria?.socEstimado ?? null, 2)}${alerta ? ` · ${ALERTA[alerta].detalhe}` : ""} — detalhe no bloco «Bateria» (secção Bordo)`}
        className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[0.65rem] tabular-nums ${classe}`}
      >
        <IconeBateria bateria={bateria} className="size-3" />
        SoC {fmtPct(bateria?.soc ?? null, 1)}
        {alerta ? ` · ${ALERTA[alerta].rotulo}` : ""}
        {bateria?.reformar ? " · REFORMAR" : ""}
      </span>
      <span className="sr-only">
        {alerta ? `bateria: ${ALERTA[alerta].rotulo.toLowerCase()}` : ""}
      </span>
    </>
  )
}

// ------------------------------------------------------------------------- curva de descarga

interface PontoDescarga {
  t: number
  /** SoC em % (0–100); `null` = esta linha não trouxe o valor. */
  real: number | null
  estimado: number | null
}

/** Linhas da telemetria → pontos da curva (só as que trazem algum SoC). */
function pontosDescarga(linhas: LinhaSim[]): PontoDescarga[] {
  const pontos: PontoDescarga[] = []
  for (const l of linhas) {
    const b = l.bateria
    if (b === null) continue
    const real = b.soc === null ? null : b.soc * 100
    const estimado = b.socEstimado === null ? null : b.socEstimado * 100
    if (real === null && estimado === null) continue
    pontos.push({ t: l.t, real, estimado })
  }
  return pontos
}

/** Passos «redondos» do eixo (p.p.). */
const PASSOS_EIXO = [0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10, 20, 25, 50]
/** Amplitude mínima do eixo (p.p.): ruído de 0,01 % nunca enche a altura toda. */
const AMPLITUDE_MINIMA = 0.5

/** Eixo ÚNICO em % para as duas séries: limites redondos, amplitude mínima, dentro de [0, 100]. */
function eixoSoc(valores: number[]): { lo: number; hi: number; casas: number } {
  let lo = Math.min(...valores)
  let hi = Math.max(...valores)
  if (hi - lo < AMPLITUDE_MINIMA) {
    const centro = (hi + lo) / 2
    lo = centro - AMPLITUDE_MINIMA / 2
    hi = centro + AMPLITUDE_MINIMA / 2
  }
  const passo =
    PASSOS_EIXO.find(
      (p) => Math.ceil(hi / p - 1e-9) - Math.floor(lo / p + 1e-9) <= 4
    ) ?? 50
  lo = Math.max(0, Math.floor(lo / passo + 1e-9) * passo)
  hi = Math.min(100, Math.ceil(hi / passo - 1e-9) * passo)
  if (hi <= lo) hi = Math.min(100, lo + passo)
  if (hi <= lo) lo = hi - passo
  const casas =
    passo >= 1 ? (Number.isInteger(passo) ? 0 : 1) : passo === 0.25 ? 2 : 1
  return { lo, hi, casas }
}

/** Geometria do desenho (unidades do viewBox; o SVG estica na largura). */
const LARGURA = 600
const ALTURA = 84
const MARGEM_Y = 5

/** Caminho de uma série (quebra nos `null`: nunca se liga por cima de uma falha). */
function caminho(
  pontos: PontoDescarga[],
  serie: "real" | "estimado",
  x: (t: number) => number,
  y: (v: number) => number
): string {
  let d = ""
  let aberto = false
  for (const p of pontos) {
    const v = p[serie]
    if (v === null) {
      aberto = false
      continue
    }
    d += `${aberto ? "L" : "M"}${x(p.t).toFixed(2)} ${y(v).toFixed(2)} `
    aberto = true
  }
  return d.trim()
}

/** Duração em texto curto («42 s», «5 min 12 s», «1 h 02 min»). */
function fmtDuracao(segundos: number | null): string {
  if (segundos === null || !Number.isFinite(segundos) || segundos < 0)
    return "—"
  if (segundos < 60) return `${fmt(segundos, 0)} s`
  const minutos = Math.floor(segundos / 60)
  if (minutos < 60)
    return `${minutos} min ${String(Math.floor(segundos % 60)).padStart(2, "0")} s`
  return `${Math.floor(minutos / 60)} h ${String(minutos % 60).padStart(2, "0")} min`
}

interface CurvaDescargaProps {
  linhas: LinhaSim[]
}

/**
 * Curva de descarga: SoC real (traço sólido, `--primary`) e SoC estimado pelo RPi (tracejado,
 * `--muted-foreground`) ao longo das amostras do histórico local (até 600, desde o início do episódio).
 * Eixo único em %, auto-escalado com limites redondos e amplitude mínima de 0,5 p.p. (os limites estão
 * escritos ao lado — a escala nunca fica escondida). O cursor (rato) ou as setas (teclado, com foco no
 * gráfico) leem um instante; sem cursor a leitura é a da última amostra.
 */
function CurvaDescarga({ linhas }: CurvaDescargaProps) {
  const pontos = useMemo(() => pontosDescarga(linhas), [linhas])
  const [cursor, setCursor] = useState<number | null>(null)
  const idLeitura = useId()

  if (pontos.length < 2) {
    return (
      <p
        className="rounded-lg bg-muted/40 px-3 py-2 text-[0.65rem] text-muted-foreground"
        data-testid="curva-descarga-vazia"
      >
        curva de descarga: à espera de amostras com SoC (
        {fmtInteiro(pontos.length)} até agora) — o histórico começa em cada
        episódio
      </p>
    )
  }

  const valores = pontos.flatMap((p) =>
    [p.real, p.estimado].filter((v): v is number => v !== null)
  )
  const { lo, hi, casas } = eixoSoc(valores)
  const t0 = pontos[0].t
  const t1 = pontos[pontos.length - 1].t
  const dt = t1 - t0
  const x = (t: number) => (dt > 0 ? ((t - t0) / dt) * LARGURA : LARGURA)
  const y = (v: number) =>
    ALTURA - MARGEM_Y - ((v - lo) / (hi - lo)) * (ALTURA - 2 * MARGEM_Y)
  const dReal = caminho(pontos, "real", x, y)
  const dEstimado = caminho(pontos, "estimado", x, y)

  const indice =
    cursor === null ? pontos.length - 1 : Math.min(cursor, pontos.length - 1)
  const ponto = pontos[indice]
  const xPct = (x(ponto.t) / LARGURA) * 100
  const yReal = ponto.real === null ? null : (y(ponto.real) / ALTURA) * 100

  const primeiroReal = pontos.find((p) => p.real !== null)?.real ?? null
  const ultimoReal =
    [...pontos].reverse().find((p) => p.real !== null)?.real ?? null
  const resumo = `curva de descarga: SoC real de ${fmt(primeiroReal, 2)} % a ${fmt(ultimoReal, 2)} % em ${fmtDuracao(dt)} (${fmtInteiro(pontos.length)} amostras); eixo de ${fmt(lo, casas)} % a ${fmt(hi, casas)} %`

  /** Índice da amostra mais próxima de uma fração horizontal do gráfico. */
  const maisProximo = (fracao: number): number => {
    const alvo = t0 + Math.max(0, Math.min(1, fracao)) * dt
    let melhor = 0
    for (let i = 1; i < pontos.length; i += 1) {
      if (Math.abs(pontos[i].t - alvo) < Math.abs(pontos[melhor].t - alvo))
        melhor = i
    }
    return melhor
  }

  const aoMover = (evento: PointerEvent<HTMLDivElement>) => {
    const caixa = evento.currentTarget.getBoundingClientRect()
    if (caixa.width <= 0) return
    setCursor(maisProximo((evento.clientX - caixa.left) / caixa.width))
  }

  const aoTeclar = (evento: KeyboardEvent<HTMLDivElement>) => {
    const atual = cursor ?? pontos.length - 1
    const passo = evento.shiftKey ? 10 : 1
    // End/Escape devolvem a leitura à última amostra («agora»): cursor `null`.
    const novo: number | null | undefined =
      evento.key === "ArrowLeft"
        ? Math.max(0, atual - passo)
        : evento.key === "ArrowRight"
          ? Math.min(pontos.length - 1, atual + passo)
          : evento.key === "Home"
            ? 0
            : evento.key === "End" || evento.key === "Escape"
              ? null
              : undefined
    if (novo === undefined) return
    evento.preventDefault()
    setCursor(novo)
  }

  return (
    <figure className="flex flex-col gap-1.5" data-testid="curva-descarga">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-[0.65rem] text-muted-foreground">
        <span className="font-medium tracking-wide text-foreground uppercase">
          curva de descarga
        </span>
        <span className="flex items-center gap-3" aria-hidden="true">
          <span className="inline-flex items-center gap-1">
            <svg width="16" height="6" className="overflow-visible">
              <line
                x1="0"
                y1="3"
                x2="16"
                y2="3"
                strokeWidth="2"
                strokeLinecap="round"
                style={{ stroke: "var(--primary)" }}
              />
            </svg>
            real
          </span>
          <span className="inline-flex items-center gap-1">
            <svg width="16" height="6" className="overflow-visible">
              <line
                x1="0"
                y1="3"
                x2="16"
                y2="3"
                strokeWidth="2"
                strokeDasharray="4 3"
                style={{ stroke: "var(--muted-foreground)" }}
              />
            </svg>
            estimado (RPi)
          </span>
        </span>
      </figcaption>

      <p
        className="font-mono text-[0.65rem] text-muted-foreground tabular-nums"
        data-testid="curva-descarga-leitura"
        id={idLeitura}
      >
        {cursor === null ? "agora" : `t = ${fmt(ponto.t, 1)} s`} · real{" "}
        <span className="font-medium text-foreground">
          {fmt(ponto.real, 2)} %
        </span>{" "}
        · estimado{" "}
        <span className="font-medium text-foreground">
          {fmt(ponto.estimado, 2)} %
        </span>
      </p>

      <div className="flex items-stretch gap-2">
        <div
          role="img"
          aria-label={resumo}
          aria-describedby={idLeitura}
          tabIndex={0}
          onPointerMove={aoMover}
          onPointerDown={aoMover}
          onPointerLeave={() => setCursor(null)}
          onPointerCancel={() => setCursor(null)}
          onKeyDown={aoTeclar}
          onBlur={() => setCursor(null)}
          className={`relative h-[5.25rem] min-w-0 flex-1 cursor-crosshair rounded-md ${FOCUS_RING}`}
        >
          <svg
            viewBox={`0 0 ${LARGURA} ${ALTURA}`}
            preserveAspectRatio="none"
            className="absolute inset-0 size-full overflow-visible"
            aria-hidden="true"
          >
            {/* grelha hairline nos dois limites do eixo (recessiva, sólida) */}
            {[MARGEM_Y, ALTURA - MARGEM_Y].map((gy) => (
              <line
                key={gy}
                x1={0}
                x2={LARGURA}
                y1={gy}
                y2={gy}
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
                style={{ stroke: "var(--border)" }}
              />
            ))}
            {dEstimado ? (
              <path
                d={dEstimado}
                fill="none"
                strokeWidth={2}
                strokeDasharray="4 3"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
                style={{ stroke: "var(--muted-foreground)" }}
              />
            ) : null}
            {dReal ? (
              <path
                d={dReal}
                fill="none"
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
                style={{ stroke: "var(--primary)" }}
              />
            ) : null}
          </svg>
          {cursor !== null ? (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 w-px bg-foreground/40"
              style={{ left: `${xPct}%` }}
            />
          ) : null}
          {yReal !== null ? (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary ring-2 ring-card"
              style={{ left: `${xPct}%`, top: `${yReal}%` }}
            />
          ) : null}
        </div>
        <div
          className="flex w-12 shrink-0 flex-col justify-between py-0.5 text-right font-mono text-[0.6rem] text-muted-foreground tabular-nums"
          aria-hidden="true"
        >
          <span>{fmt(hi, casas)} %</span>
          <span>{fmt(lo, casas)} %</span>
        </div>
      </div>

      <div className="flex justify-between pr-14 font-mono text-[0.6rem] text-muted-foreground">
        <span>−{fmtDuracao(dt)}</span>
        <span>
          {fmtInteiro(pontos.length)} amostras · agora (t = {fmt(t1, 1)} s)
        </span>
      </div>
    </figure>
  )
}

// ---------------------------------------------------------------------------- métricas · ciclo

interface MetricaProps {
  rotulo: string
  valor: string
  detalhe?: string
  testid: string
  /** Realce de alerta no valor (texto `destructive`). */
  alerta?: boolean
}

function Metrica({
  rotulo,
  valor,
  detalhe,
  testid,
  alerta = false,
}: MetricaProps) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5" data-testid={testid}>
      <span className="text-[0.6rem] tracking-wide text-muted-foreground uppercase">
        {rotulo}
      </span>
      <span
        className={`font-mono text-sm tabular-nums ${alerta ? "text-destructive" : ""}`}
      >
        {valor}
      </span>
      {detalhe ? (
        <span className="text-[0.6rem] leading-tight text-muted-foreground">
          {detalhe}
        </span>
      ) : null}
    </div>
  )
}

/** Texto do último ciclo fechado (só o que o backend mandou — o resto não aparece). */
function textoCiclo(ciclo: UltimoCicloBateria): string {
  if (ciclo.acao === "nova")
    return `PACK NOVO instalado · SoH ${fmtPct(ciclo.soh, 2)} · 0 ciclos`
  const partes = [
    ciclo.acao === "recarregar"
      ? "RECARREGAR"
      : (ciclo.acao?.toUpperCase() ?? "ciclo"),
    ciclo.dod === null ? null : `DoD ${fmtPct(ciclo.dod, 2)}`,
    ciclo.ah === null ? null : `${fmt(ciclo.ah, 3)} Ah`,
    ciclo.wh === null ? null : `${fmt(ciclo.wh, 2)} Wh`,
    ciclo.cMedio === null ? null : `${fmt(ciclo.cMedio, 2)} C médio`,
    ciclo.tMedioC === null ? null : `${fmt(ciclo.tMedioC, 1)} °C médios`,
    ciclo.iPico === null ? null : `pico ${fmt(ciclo.iPico, 1)} A`,
    ciclo.vMin === null ? null : `V mín ${fmt(ciclo.vMin, 2)} V`,
    ciclo.duracaoS === null ? null : fmtDuracao(ciclo.duracaoS),
    ciclo.soh === null ? null : `SoH depois ${fmtPct(ciclo.soh, 4)}`,
  ]
  return partes.filter((p): p is string => p !== null).join(" · ")
}

// --------------------------------------------------------------------------------- comandos

type FaseComando = "pronto" | "a_enviar" | "ok" | "erro"

const SUPERFICIE: Record<FaseComando, string> = {
  pronto: "bg-primary text-primary-foreground",
  a_enviar: "bg-secondary text-secondary-foreground",
  ok: "bg-primary text-primary-foreground",
  erro: "bg-destructive/15 text-destructive",
}

/** Quanto tempo o botão mostra «aceite»/«falhou» antes de voltar a «pronto» (como o APLICAR VENTO). */
const MS_VOLTAR_A_PRONTO = 2000

interface MensagemComando {
  tom: "a_enviar" | "ok" | "erro"
  texto: string
}

// ------------------------------------------------------------------------------- o bloco

interface PainelBateriaProps {
  /** Histórico local das linhas (curva de descarga). */
  linhas: LinhaSim[]
  /** Última leitura (`bateria` da última linha); `null` = a telemetria ainda não a trouxe. */
  bateria: BateriaTelemetria | null
  /** `false` com a API em baixo: os valores são os da última leitura e os comandos ficam desativados. */
  ligado: boolean
  /** `POST /api/bateria` (pela fila do `use-sim`). */
  onComando: (acao: AcaoBateria) => Promise<RespostaBateria>
  onAviso: (texto: string, tom: TomAviso) => void
}

export function PainelBateria({
  linhas,
  bateria,
  ligado,
  onComando,
  onAviso,
}: PainelBateriaProps) {
  const [fase, setFase] = useState<Record<AcaoBateria, FaseComando>>({
    recarregar: "pronto",
    nova: "pronto",
  })
  const [mensagem, setMensagem] = useState<MensagemComando | null>(null)
  /** Muda a cada PACK NOVO confirmado: remonta o `hold-to-confirm` (é de um disparo — ver controlos.tsx). */
  const [geracao, setGeracao] = useState(0)
  const idAjudaComandos = useId()

  const emCurso = fase.recarregar === "a_enviar" || fase.nova === "a_enviar"
  const podeEnviar = ligado && !emCurso
  const alerta = alertaAtivo(bateria)

  const enviar = (acao: AcaoBateria) => {
    const nome = acao === "recarregar" ? "RECARREGAR" : "PACK NOVO"
    setFase((f) => ({ ...f, [acao]: "a_enviar" }))
    setMensagem({
      tom: "a_enviar",
      texto: `${nome}: a enviar POST /api/bateria {"acao": "${acao}"}…`,
    })
    onComando(acao)
      .then((resposta) => {
        const seq =
          resposta.seq === null ? "" : ` (seq ${fmtInteiro(resposta.seq)})`
        setFase((f) => ({ ...f, [acao]: "ok" }))
        setMensagem({
          tom: "ok",
          texto: `${nome}: pedido aceite${seq} — o runner aplica-o no passo de decisão seguinte; o efeito vê-se aqui na telemetria (SoC e «último ciclo fechado»)`,
        })
        onAviso(
          acao === "recarregar"
            ? `bateria: RECARREGAR aceite${seq} — o ciclo fecha com o desgaste e o pack volta a 100 %`
            : `bateria: PACK NOVO aceite${seq} — SoH 100 %, 0 ciclos`,
          "ok"
        )
      })
      .catch((erro: unknown) => {
        const motivo =
          erro instanceof Error ? erro.message : "falha desconhecida"
        setFase((f) => ({ ...f, [acao]: "erro" }))
        setMensagem({
          tom: "erro",
          texto: `${nome}: POST /api/bateria recusado — ${motivo}`,
        })
        onAviso(`POST /api/bateria recusado — ${motivo}`, "erro")
      })
      .finally(() => {
        window.setTimeout(
          () => setFase((f) => ({ ...f, [acao]: "pronto" })),
          MS_VOLTAR_A_PRONTO
        )
      })
  }

  const socPct = bateria?.soc == null ? null : bateria.soc * 100
  const estPct = bateria?.socEstimado == null ? null : bateria.socEstimado * 100
  const diferenca = socPct !== null && estPct !== null ? estPct - socPct : null
  const quimica = rotuloQuimica(bateria?.quimica ?? null)
  const arranjo =
    bateria?.s == null || bateria?.pParalelo == null
      ? null
      : `${fmt(bateria.s, 0)}S${fmt(bateria.pParalelo, 0)}P`
  const subtitulo = [
    bateria?.packId ? `pack ${bateria.packId}` : null,
    [quimica, arranjo].filter(Boolean).join(" ") || null,
    bateria?.capacidadeAh == null
      ? null
      : `${fmt(bateria.capacidadeAh, 1)} Ah nominais`,
  ]
    .filter((p): p is string => p !== null)
    .join(" · ")
  const vPouso = bateria?.vPousoCelula ?? null
  const vCorte = bateria?.vCorteCelula ?? null
  const ciclo = bateria?.ultimoCiclo ?? null

  return (
    <Card
      className={`gap-3 ${alerta ? ALERTA[alerta].anel : ""}`}
      data-testid="painel-bateria"
      data-alerta={alerta ?? "nenhum"}
    >
      <CardHeader className="gap-1">
        <CardTitle className="flex flex-wrap items-center gap-2 text-sm font-medium">
          <IconeBateria bateria={bateria} className="size-4" />
          Bateria
          <span className="text-[0.7rem] font-normal text-muted-foreground">
            planta real
          </span>
          <span className="ml-auto flex flex-wrap items-center gap-1.5">
            {alerta ? (
              <span
                data-testid="bateria-alerta"
                title={ALERTA[alerta].detalhe}
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.65rem] ${ALERTA[alerta].classe}`}
              >
                <TriangleAlert className="size-3" aria-hidden="true" />
                {ALERTA[alerta].rotulo}
              </span>
            ) : null}
            {bateria?.reformar ? (
              <span
                data-testid="bateria-reformar"
                title="SoH ≤ 80 %: fim de vida do pack (convenção da indústria) — trocar por um PACK NOVO"
                className="inline-flex items-center rounded-full bg-destructive/10 px-2 py-0.5 text-[0.65rem] font-semibold tracking-wide text-destructive ring-1 ring-destructive/40"
              >
                REFORMAR
              </span>
            ) : null}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          {subtitulo.length > 0
            ? subtitulo
            : "o pack ainda não se identificou na telemetria"}{" "}
          · persiste entre REINICIARs (pousar não carrega)
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        {bateria === null ? (
          <p
            className="rounded-lg bg-muted/50 px-3 py-2 text-[0.65rem] text-muted-foreground"
            data-testid="bateria-sem-dados"
          >
            a telemetria ainda não trouxe o bloco `bateria` — os valores ficam a
            «—» até chegar a primeira leitura.
          </p>
        ) : null}
        {!ligado ? (
          <p
            className="text-[0.65rem] text-destructive"
            data-testid="bateria-sem-ligacao"
          >
            API em baixo: os valores são os da última leitura e os comandos
            ficam desativados até voltar a resposta.
          </p>
        ) : null}
        {alerta ? (
          <p
            className={`rounded-lg px-3 py-2 text-xs ${ALERTA[alerta].classe}`}
            data-testid="bateria-alerta-texto"
          >
            {alerta === "critica"
              ? `tensão CRÍTICA: ${fmt(bateria?.vCelula ?? null, 3)} V/célula, abaixo do corte (${fmt(vCorte, 2)} V) — o brownout está iminente; RECARREGAR ou PACK NOVO`
              : `tensão BAIXA: ${fmt(bateria?.vCelula ?? null, 3)} V/célula, abaixo da tensão de pouso (${fmt(vPouso, 2)} V) — hora de pousar e RECARREGAR`}
          </p>
        ) : null}

        {/* SoC em destaque: o REAL (modelo) e o que o RPi ESTIMA, lado a lado */}
        <div className="flex flex-col gap-2 rounded-lg bg-muted/40 px-3 py-2.5">
          <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
            <div className="flex flex-col" data-testid="bateria-soc">
              <span className="text-[0.6rem] tracking-wide text-muted-foreground uppercase">
                SoC real
              </span>
              <span className="flex items-baseline gap-1">
                {socPct === null ? (
                  <span className="text-3xl font-semibold">—</span>
                ) : (
                  <AnimatedNumber
                    value={socPct}
                    locales="pt-PT"
                    format={{
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    }}
                    className="text-3xl font-semibold"
                  />
                )}
                <span className="text-sm text-muted-foreground">%</span>
              </span>
            </div>
            <div className="flex flex-col" data-testid="bateria-soc-estimado">
              <span className="text-[0.6rem] tracking-wide text-muted-foreground uppercase">
                SoC estimado (RPi)
              </span>
              <span className="flex items-baseline gap-1">
                <span className="text-xl font-semibold tabular-nums">
                  {fmt(estPct, 2)}
                </span>
                <span className="text-xs text-muted-foreground">%</span>
                <span
                  className="ml-1 font-mono text-[0.65rem] text-muted-foreground"
                  title="estimado − real, em pontos percentuais"
                >
                  Δ{" "}
                  {diferenca === null ? "—" : `${fmtSinal(diferenca, 2)} p.p.`}
                </span>
              </span>
            </div>
          </div>
          <ProgressBar
            value={(socPct ?? 0) / 100}
            referenceTick={estPct === null ? undefined : estPct / 100}
            highlight={alerta === null}
            tone="var(--destructive)"
            progressbar
            aria-label="estado de carga real da bateria"
          />
          <p className="text-[0.6rem] leading-snug text-muted-foreground">
            barra = SoC real · traço = estimado. Estimado = OCV em repouso no
            arranque + contagem de Coulomb com a corrente medida (monitor de
            bateria), sobre a capacidade nominal — o RPi não conhece o desgaste,
            por isso diverge do real quando o pack envelhece.
          </p>
        </div>

        <CurvaDescarga linhas={linhas} />

        <div className="grid grid-cols-2 gap-x-3 gap-y-2.5 border-t border-border pt-3 sm:grid-cols-3">
          <Metrica
            rotulo="tensão do pack"
            testid="bateria-tensao"
            valor={`${fmt(bateria?.v ?? null, 2)} V`}
            detalhe={`medida ${fmt(bateria?.vMedida ?? null, 2)} V (monitor)`}
          />
          <Metrica
            rotulo="por célula"
            testid="bateria-tensao-celula"
            valor={`${fmt(bateria?.vCelula ?? null, 3)} V`}
            alerta={alerta !== null}
            detalhe={`pouso ≤ ${fmt(vPouso, 2)} V · corte ≤ ${fmt(vCorte, 2)} V`}
          />
          <Metrica
            rotulo="corrente"
            testid="bateria-corrente"
            valor={`${fmt(bateria?.i ?? null, 2)} A`}
            detalhe={`medida ${fmt(bateria?.iMedida ?? null, 2)} A · média ${fmt(bateria?.iMedia ?? null, 2)} A`}
          />
          <Metrica
            rotulo="potência"
            testid="bateria-potencia"
            valor={`${fmt(bateria?.p ?? null, 1)} W`}
            detalhe="no pack (motores + eletrónica)"
          />
          <Metrica
            rotulo="autonomia restante"
            testid="bateria-autonomia"
            valor={
              bateria?.autonomiaMin == null
                ? "—"
                : `${fmt(bateria.autonomiaMin, 1)} min`
            }
            detalhe={
              bateria !== null && bateria.autonomiaMin === null
                ? "sem corrente média (motores parados)"
                : "até à reserva de pouso, com a corrente média"
            }
          />
          <Metrica
            rotulo="temperatura"
            testid="bateria-temperatura"
            valor={`${fmt(bateria?.tempC ?? null, 1)} °C`}
            detalhe="do pack (aquece com I²·R)"
          />
          <Metrica
            rotulo="SoH"
            testid="bateria-soh"
            valor={fmtPct(bateria?.soh ?? null, 2)}
            alerta={bateria?.reformar === true}
            detalhe="capacidade atual / nominal · reformar ≤ 80 %"
          />
          <Metrica
            rotulo="ciclos"
            testid="bateria-ciclos"
            valor={`${fmt(bateria?.ciclosEq ?? null, 2)} eq.`}
            detalhe={`${fmtInteiro(bateria?.nRecargas ?? null)} ${bateria?.nRecargas === 1 ? "recarga" : "recargas"}`}
          />
          <Metrica
            rotulo="R₀ interna"
            testid="bateria-r0"
            valor={`${fmt(bateria?.r0Mohm ?? null, 2)} mΩ`}
            detalhe="sobe no frio, no fim da descarga e com o desgaste"
          />
          <Metrica
            rotulo="desde a última recarga"
            testid="bateria-consumo"
            valor={`${fmt(bateria?.ahVoo ?? null, 3)} Ah`}
            detalhe={`${fmt(bateria?.whVoo ?? null, 2)} Wh`}
          />
        </div>

        <div className="flex flex-col gap-2 border-t border-border pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <MultiStateButton
              state={fase.recarregar}
              onClick={() => enviar("recarregar")}
              disabled={!podeEnviar}
              surfaceClassName={SUPERFICIE[fase.recarregar]}
              feedback={fase.recarregar === "erro" ? "shake" : "pop"}
              announce={
                fase.recarregar === "ok"
                  ? "recarga pedida"
                  : fase.recarregar === "erro"
                    ? "falha ao pedir a recarga"
                    : undefined
              }
              aria-label="recarregar a bateria (fecha o ciclo com desgaste e volta a 100 %)"
              icon={
                fase.recarregar === "a_enviar" ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : fase.recarregar === "ok" ? (
                  <Check className="size-4" />
                ) : fase.recarregar === "erro" ? (
                  <TriangleAlert className="size-4" />
                ) : (
                  <PlugZap className="size-4" />
                )
              }
              className={FOCUS_RING}
              pillClassName="rounded-full px-4 py-2 text-xs font-medium shadow-sm"
            >
              {fase.recarregar === "a_enviar"
                ? "A ENVIAR…"
                : fase.recarregar === "ok"
                  ? "RECARGA PEDIDA"
                  : fase.recarregar === "erro"
                    ? "FALHOU — TENTAR DE NOVO"
                    : "RECARREGAR"}
            </MultiStateButton>

            {podeEnviar ? (
              <HoldToConfirmButton
                key={geracao}
                holdSeconds={1}
                mode="callback"
                onConfirm={() => {
                  setGeracao((g) => g + 1)
                  enviar("nova")
                }}
                aria-describedby={idAjudaComandos}
                className="h-8! w-auto! px-4! text-xs!"
              >
                <PackagePlus className="size-3.5" aria-hidden="true" />
                PACK NOVO (manter 1 s)
              </HoldToConfirmButton>
            ) : (
              <Button
                type="button"
                variant="secondary"
                disabled
                className="h-8 rounded-full px-4 text-xs"
                data-testid="botao-pack-novo-inativo"
              >
                {fase.nova === "a_enviar" ? (
                  <Loader2
                    className="size-3.5 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <PackagePlus className="size-3.5" aria-hidden="true" />
                )}
                {fase.nova === "a_enviar"
                  ? "A ENVIAR…"
                  : "PACK NOVO (manter 1 s)"}
              </Button>
            )}
          </div>
          <p
            id={idAjudaComandos}
            className="text-[0.6rem] leading-snug text-muted-foreground"
          >
            RECARREGAR fecha o ciclo em curso (aplica o desgaste: SoH, ciclos,
            R₀) e põe o pack a 100 %. PACK NOVO troca por um pack novo (SoH 100
            %, 0 ciclos) e apaga o histórico de desgaste — por isso pede que se
            mantenha carregado ~1 s. Nenhum dos dois reinicia o episódio.
          </p>
          {mensagem !== null ? (
            <p
              role="status"
              data-testid="bateria-estado-pedido"
              data-tom={mensagem.tom}
              className={`rounded-md px-2 py-1 text-[0.65rem] ${
                mensagem.tom === "erro"
                  ? "border border-destructive/40 bg-destructive/10 text-destructive"
                  : "bg-muted/50 text-muted-foreground"
              }`}
            >
              {mensagem.texto}
            </p>
          ) : null}
          <p
            className="text-[0.65rem] text-muted-foreground"
            data-testid="bateria-ultimo-ciclo"
          >
            <span className="text-foreground">último ciclo fechado:</span>{" "}
            {ciclo === null
              ? "nenhum nesta sessão do runner (o RECARREGAR fecha o ciclo em curso)"
              : textoCiclo(ciclo)}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
