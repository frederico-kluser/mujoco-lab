/**
 * Curvas ao vivo (z, yaw_err, retorno e vento_vel) — `Sparkline` do Motion UI + `AnimatedNumber`.
 *
 * A linha do ALVO é a `grid` do próprio `Sparkline`: a posição vertical sai da MESMA matemática de
 * `buildSparkPath` (`range = max(1, max−min)`), replicada em `yDoValor` para o traço cair exactamente
 * sobre o valor de referência e não num sítio plausível.
 */

import { AnimatedNumber } from "@/components/motion-ui/animated-number"
import { Sparkline } from "@/components/motion-ui/sparkline"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { fmt, fmtInteiro, type LinhaSim } from "@/lib/sim"

const LARGURA = 320
const ALTURA = 72
const PAD_Y = 10

/** y (viewBox) de um valor, com a mesma escala que o `Sparkline` usa para o histórico. */
export function yDoValor(historico: number[], valor: number): number | null {
  if (historico.length === 0) return null
  const maximo = Math.max(...historico)
  const minimo = Math.min(...historico)
  const intervalo = Math.max(1, maximo - minimo)
  const normalizado = (valor - minimo) / intervalo
  return ALTURA - PAD_Y - normalizado * (ALTURA - PAD_Y * 2)
}

interface CurvaProps {
  titulo: string
  nota?: string
  historico: number[]
  valorAtual: number
  unidade: string
  casas?: number
  /** Valor de referência desenhado como linha fina dentro do gráfico. */
  alvo?: number
  alvoTexto?: string
  tickKey: number
}

function Curva({
  titulo,
  nota,
  historico,
  valorAtual,
  unidade,
  casas = 3,
  alvo,
  alvoTexto,
  tickKey,
}: CurvaProps) {
  const yAlvo = alvo === undefined ? null : yDoValor(historico, alvo)
  const minimo = historico.length > 0 ? Math.min(...historico) : null
  const maximo = historico.length > 0 ? Math.max(...historico) : null

  return (
    <Card size="sm" className="gap-2" data-testid={`curva-${titulo}`}>
      <CardHeader className="gap-0.5">
        <CardTitle className="flex items-baseline justify-between gap-2 text-xs font-medium">
          <span>{titulo}</span>
          <span className="font-mono text-sm tabular-nums">
            <AnimatedNumber
              value={valorAtual}
              format={{ minimumFractionDigits: casas, maximumFractionDigits: casas }}
            />
            <span className="ml-1 text-[0.65rem] text-muted-foreground">{unidade}</span>
          </span>
        </CardTitle>
        {nota ? <p className="text-[0.65rem] text-muted-foreground">{nota}</p> : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        <Sparkline
          history={historico}
          width={LARGURA}
          height={ALTURA}
          padY={PAD_Y}
          tone="primary"
          area
          dot
          tickKey={tickKey}
          grid={yAlvo === null ? undefined : [yAlvo]}
          label={`${titulo} ao longo do episódio`}
        />
        <div className="flex items-center justify-between font-mono text-[0.65rem] text-muted-foreground">
          <span>
            mín {fmt(minimo, casas)} · máx {fmt(maximo, casas)}
          </span>
          <span>
            {alvoTexto ?? ""} {fmtInteiro(historico.length)} pts
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

interface CurvasProps {
  linhas: LinhaSim[]
  zAlvo: number
}

export function Curvas({ linhas, zAlvo }: CurvasProps) {
  const z = linhas.map((l) => l.z)
  const yawErr = linhas.map((l) => l.yaw_err)
  const retorno = linhas.map((l) => l.retorno)
  const vento = linhas.map((l) => l.vento_vel)
  const ultima = linhas.length > 0 ? linhas[linhas.length - 1] : null
  const tickKey = ultima?.passo ?? 0

  return (
    <section aria-label="Curvas ao vivo" className="grid gap-3 sm:grid-cols-2">
      <Curva
        titulo="z(t)"
        nota={`altitude · linha fina = alvo ${fmt(zAlvo, 1)} m`}
        historico={z}
        valorAtual={ultima?.z ?? 0}
        unidade="m"
        casas={3}
        alvo={zAlvo}
        alvoTexto={`alvo ${fmt(zAlvo, 1)} m ·`}
        tickKey={tickKey}
      />
      <Curva
        titulo="yaw_err(t)"
        nota="erro de guinada (rad) · alvo 0"
        historico={yawErr}
        valorAtual={ultima?.yaw_err ?? 0}
        unidade="rad"
        casas={3}
        tickKey={tickKey}
      />
      <Curva
        titulo="retorno(t)"
        nota="retorno acumulado do episódio"
        historico={retorno}
        valorAtual={ultima?.retorno ?? 0}
        unidade=""
        casas={2}
        tickKey={tickKey}
      />
      <Curva
        titulo="vento_vel(t)"
        nota="velocidade do vento aplicado (m/s)"
        historico={vento}
        valorAtual={ultima?.vento_vel ?? 0}
        unidade="m/s"
        casas={2}
        tickKey={tickKey}
      />
    </section>
  )
}
