/**
 * curvas.tsx — as curvas do painel (`METRICAS` em `lib/config.ts`) com `sparkline` + `animated-number`,
 * mais a faixa de VALORES ATUAIS (o essencial para vigiar a operação sem procurar nos gráficos).
 *
 * Cada painel: valor atual (número animado), unidade, a linha de referência (o alvo do episódio na métrica
 * marcada com `referencia: "alvo"`, o zero nas outras) e o histórico da sessão. O eixo x é o tempo; a janela
 * é dos últimos `MAX_PONTOS` pontos. Em modo `grande` (secção «Operação») os painéis são maiores.
 */

import { AnimatedNumber } from "@/components/motion-ui/animated-number"
import { Sparkline } from "@/components/motion-ui/sparkline"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { METRICAS, alvoGraus, fmt, valorMetrica, type LinhaSim, type Metrica } from "@/lib/sim"

const LARGURA = 320
const ALTURA = 72
/** Tamanho «grande» (secção Operação: vigiar a operação sem colar o nariz ao ecrã). */
const LARGURA_GRANDE = 620
const ALTURA_GRANDE = 132
const PAD_Y = 10

/** y (viewBox) de um valor, com a MESMA escala que o `Sparkline` usa para o histórico (para a referência). */
export function yDoValor(historico: number[], valor: number, altura: number = ALTURA): number | null {
  if (historico.length === 0) return null
  const maximo = Math.max(...historico, valor)
  const minimo = Math.min(...historico, valor)
  const intervalo = Math.max(1e-9, maximo - minimo)
  const normalizado = (valor - minimo) / intervalo
  return altura - PAD_Y - normalizado * (altura - 2 * PAD_Y)
}

function Painel({ metrica, historico, valor, referencia, grande }: {
  metrica: Metrica
  historico: number[]
  valor: number | null
  referencia: number | null
  grande: boolean
}) {
  const largura = grande ? LARGURA_GRANDE : LARGURA
  const altura = grande ? ALTURA_GRANDE : ALTURA
  const y = referencia === null ? null : yDoValor(historico, referencia, altura)
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4">
        <CardTitle className="flex items-baseline justify-between gap-2 text-sm font-medium">
          <span className="text-muted-foreground">{metrica.rotulo}</span>
          <span className="flex items-baseline gap-1 tabular-nums">
            <span className={grande ? "text-3xl font-semibold" : "text-2xl font-semibold"} style={{ color: metrica.cor }}>
              {valor === null ? "—" : <AnimatedNumber value={valor} format={{ minimumFractionDigits: metrica.casas, maximumFractionDigits: metrica.casas }} />}
            </span>
            <span className="text-xs text-muted-foreground">{metrica.unidade}</span>
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        {historico.length > 1 ? (
          <Sparkline history={historico} width={largura} height={altura} padY={PAD_Y} tone="primary" area dot
            grid={y === null ? [] : [y]} />
        ) : (
          <p className="text-sm text-muted-foreground">— sem dados (arranca o `sim_site.py`)</p>
        )}
        {referencia !== null && (
          <p className="mt-1 text-xs text-muted-foreground">
            referência {metrica.referencia === "alvo" ? "alvo" : "zero"}: {fmt(referencia, metrica.casas)} {metrica.unidade}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export function Curvas({ linhas, grande = false }: { linhas: LinhaSim[]; grande?: boolean }) {
  const ultima = linhas.length > 0 ? linhas[linhas.length - 1] : null
  const alvo = alvoGraus(ultima)
  return (
    <div className={`grid gap-3 ${grande ? "lg:grid-cols-2" : "md:grid-cols-2"}`} data-testid="curvas">
      {METRICAS.map((m) => {
        const historico = linhas
          .map((l) => valorMetrica(l, m))
          .filter((v): v is number => v !== null)
        const valor = ultima ? valorMetrica(ultima, m) : null
        const referencia = m.referencia === "alvo" ? alvo : m.referencia === "zero" ? 0 : null
        return (
          <Painel key={m.chave} metrica={m} historico={historico} valor={valor} referencia={referencia} grande={grande} />
        )
      })}
    </div>
  )
}

function ValorAtual({ metrica, valor }: { metrica: Metrica; valor: number | null }) {
  return (
    <Card size="sm" className="gap-1" data-testid={`valor-${metrica.chave}`} data-valor-atual={valor ?? undefined}>
      <CardContent className="gap-1">
        <span className="text-[0.7rem] tracking-wide text-muted-foreground uppercase">{metrica.curta}</span>
        <span className="flex items-baseline gap-1.5">
          {valor === null ? (
            <span className="text-2xl font-semibold">—</span>
          ) : (
            <AnimatedNumber value={valor} className="text-2xl font-semibold tabular-nums"
              format={{ minimumFractionDigits: metrica.casas, maximumFractionDigits: metrica.casas }} />
          )}
          <span className="text-xs text-muted-foreground">{metrica.unidade}</span>
        </span>
        <span className="text-[0.65rem] text-muted-foreground">{metrica.rotulo}</span>
      </CardContent>
    </Card>
  )
}

/**
 * Valores ATUAIS das métricas em números grandes — o essencial para vigiar a operação sem procurar nas
 * curvas (a MESMA telemetria e as MESMAS `METRICAS`, sem contas novas). «—» quando ainda não há amostras.
 */
export function ValoresAtuais({ linha }: { linha: LinhaSim | null }) {
  return (
    <section aria-label="Valores atuais" data-testid="valores-atuais" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {METRICAS.map((m) => (
        <ValorAtual key={m.chave} metrica={m} valor={linha ? valorMetrica(linha, m) : null} />
      ))}
    </section>
  )
}
