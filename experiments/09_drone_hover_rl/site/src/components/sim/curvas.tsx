/**
 * Curvas ao vivo (altura, erro de rumo, retorno e vento) — `Sparkline` do Motion UI + `AnimatedNumber`.
 * Desde a avaliação de UX de 2026-10-10 os títulos dizem o que medem em português (o nome do campo da
 * telemetria fica na nota) e o rumo aparece em GRAUS (a telemetria continua em rad: é só ecrã).
 *
 * A linha do ALVO é a `grid` do próprio `Sparkline`: a posição vertical sai da MESMA matemática de
 * `buildSparkPath` (`range = max(1, max−min)`), replicada em `yDoValor` para o traço cair exactamente
 * sobre o valor de referência e não num sítio plausível.
 */

import { AnimatedNumber } from "@/components/motion-ui/animated-number"
import { Sparkline } from "@/components/motion-ui/sparkline"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { fmt, fmtInteiro, GRAUS_POR_RAD, type LinhaSim } from "@/lib/sim"

/** rad → graus (só ecrã). */
const GRAUS = GRAUS_POR_RAD

const LARGURA = 320
const ALTURA = 72
const PAD_Y = 10

/** Tamanho «grande» (secção Operação: vigiar o voo sem colar o nariz ao ecrã). */
const LARGURA_GRANDE = 620
const ALTURA_GRANDE = 132

/** y (viewBox) de um valor, com a mesma escala que o `Sparkline` usa para o histórico. */
export function yDoValor(
  historico: number[],
  valor: number,
  altura: number = ALTURA,
  padY: number = PAD_Y
): number | null {
  if (historico.length === 0) return null
  const maximo = Math.max(...historico)
  const minimo = Math.min(...historico)
  const intervalo = Math.max(1, maximo - minimo)
  const normalizado = (valor - minimo) / intervalo
  return altura - padY - normalizado * (altura - padY * 2)
}

interface CurvaProps {
  /** Identificador estável (testes de DOM: `curva-<id>`). */
  id: string
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
  /** Curva maior (secção Operação / Tudo em ecrã largo). */
  grande?: boolean
}

function Curva({
  id,
  titulo,
  nota,
  historico,
  valorAtual,
  unidade,
  casas = 3,
  alvo,
  alvoTexto,
  tickKey,
  grande = false,
}: CurvaProps) {
  const largura = grande ? LARGURA_GRANDE : LARGURA
  const altura = grande ? ALTURA_GRANDE : ALTURA
  const yAlvo = alvo === undefined ? null : yDoValor(historico, alvo, altura, PAD_Y)
  const minimo = historico.length > 0 ? Math.min(...historico) : null
  const maximo = historico.length > 0 ? Math.max(...historico) : null

  return (
    <Card size="sm" className="gap-2" data-testid={`curva-${id}`}>
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
          width={largura}
          height={altura}
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
  /** Curvas maiores (secção Operação — a monitoria em voo). */
  grande?: boolean
}

export function Curvas({ linhas, zAlvo, grande = false }: CurvasProps) {
  const z = linhas.map((l) => l.z)
  const yawErr = linhas.map((l) => l.yaw_err * GRAUS)
  const retorno = linhas.map((l) => l.retorno)
  const vento = linhas.map((l) => l.vento_vel)
  const ultima = linhas.length > 0 ? linhas[linhas.length - 1] : null
  const tickKey = ultima?.passo ?? 0

  return (
    <section aria-label="Curvas ao vivo" className="grid gap-3 sm:grid-cols-2">
      <Curva
        id="z"
        titulo="altura"
        nota={`z(t) · linha fina = alvo ${fmt(zAlvo, 1)} m`}
        historico={z}
        valorAtual={ultima?.z ?? 0}
        unidade="m"
        casas={3}
        alvo={zAlvo}
        alvoTexto={`alvo ${fmt(zAlvo, 1)} m ·`}
        tickKey={tickKey}
        grande={grande}
      />
      <Curva
        id="yaw-err"
        titulo="erro de rumo"
        nota="yaw_err(t) em graus · alvo 0°"
        historico={yawErr}
        valorAtual={(ultima?.yaw_err ?? 0) * GRAUS}
        unidade="°"
        casas={1}
        tickKey={tickKey}
        grande={grande}
      />
      <Curva
        id="retorno"
        titulo="retorno"
        nota="recompensa acumulada do episódio"
        historico={retorno}
        valorAtual={ultima?.retorno ?? 0}
        unidade=""
        casas={2}
        tickKey={tickKey}
        grande={grande}
      />
      <Curva
        id="vento"
        titulo="vento"
        nota="vento_vel(t) · velocidade do vento aplicado"
        historico={vento}
        valorAtual={ultima?.vento_vel ?? 0}
        unidade="m/s"
        casas={2}
        tickKey={tickKey}
        grande={grande}
      />
    </section>
  )
}

interface ValorAtualProps {
  id: string
  rotulo: string
  descricao: string
  valor: number
  unidade: string
  casas: number
}

function ValorAtual({
  id,
  rotulo,
  descricao,
  valor,
  unidade,
  casas,
}: ValorAtualProps) {
  return (
    <Card size="sm" className="gap-1" data-testid={`valor-${id}`} data-valor-atual={valor}>
      <CardContent className="gap-1">
        <span className="text-[0.7rem] tracking-wide text-muted-foreground uppercase">
          {rotulo}
        </span>
        <span className="flex items-baseline gap-1.5">
          <AnimatedNumber
            value={valor}
            format={{
              minimumFractionDigits: casas,
              maximumFractionDigits: casas,
            }}
            className="text-2xl font-semibold tabular-nums"
          />
          <span className="text-xs text-muted-foreground">{unidade}</span>
        </span>
        <span className="text-[0.65rem] text-muted-foreground">{descricao}</span>
      </CardContent>
    </Card>
  )
}

interface ValoresAtuaisProps {
  linha: LinhaSim | null
}

/**
 * Valores ATUAIS do voo (altura · distância ao alvo · erro de rumo · vento) em números grandes — o
 * essencial para vigiar o drone em operação sem procurar nas curvas. São os valores REAIS do simulador
 * (o que o drone acha está no Painel de voo); só a unidade de ecrã muda (cm e graus).
 */
export function ValoresAtuais({ linha }: ValoresAtuaisProps) {
  return (
    <section
      aria-label="Valores atuais do voo"
      data-testid="valores-atuais"
      className="grid grid-cols-2 gap-3 lg:grid-cols-4"
    >
      <ValorAtual
        id="z"
        rotulo="altura"
        descricao="z do drone · alvo 1,0 m"
        valor={linha?.z ?? 0}
        unidade="m"
        casas={3}
      />
      <ValorAtual
        id="dist-xy"
        rotulo="distância ao alvo"
        descricao="dist_xy · na horizontal"
        valor={(linha?.dist_xy ?? 0) * 100}
        unidade="cm"
        casas={1}
      />
      <ValorAtual
        id="yaw-err"
        rotulo="erro de rumo"
        descricao="yaw_err · nariz vs. o do arranque"
        valor={(linha?.yaw_err ?? 0) * GRAUS}
        unidade="°"
        casas={1}
      />
      <ValorAtual
        id="vento-vel"
        rotulo="vento"
        descricao="vento_vel · aplicado agora"
        valor={linha?.vento_vel ?? 0}
        unidade="m/s"
        casas={2}
      />
    </section>
  )
}
