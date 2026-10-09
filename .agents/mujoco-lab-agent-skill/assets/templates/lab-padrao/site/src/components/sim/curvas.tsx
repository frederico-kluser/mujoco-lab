/**
 * curvas.tsx — as 4 curvas do painel (`METRICAS` em `lib/sim.ts`) com `sparkline` + `animated-number`.
 *
 * Cada painel: valor atual (número animado), unidade, a linha de referência (alvo do episódio em θ, zero nas
 * outras) e o histórico da sessão. O eixo x é o tempo; a janela é dos últimos `MAX_PONTOS` pontos.
 */

import { AnimatedNumber } from "@/components/motion-ui/animated-number"
import { Sparkline } from "@/components/motion-ui/sparkline"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { METRICAS, alvoGraus, fmt, valorMetrica, type LinhaSim, type Metrica } from "@/lib/sim"

const LARGURA = 320
const ALTURA = 72
const PAD_Y = 10

/** y (viewBox) de um valor, com a MESMA escala que o `Sparkline` usa para o histórico (para a referência). */
export function yDoValor(historico: number[], valor: number): number | null {
  if (historico.length === 0) return null
  const maximo = Math.max(...historico, valor)
  const minimo = Math.min(...historico, valor)
  const intervalo = Math.max(1e-9, maximo - minimo)
  const normalizado = (valor - minimo) / intervalo
  return ALTURA - PAD_Y - normalizado * (ALTURA - 2 * PAD_Y)
}

function Painel({ metrica, historico, valor, referencia }: {
  metrica: Metrica
  historico: number[]
  valor: number | null
  referencia: number | null
}) {
  const y = referencia !== null ? yDoValor(historico, referencia) : null
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4">
        <CardTitle className="flex items-baseline justify-between gap-2 text-sm font-medium">
          <span className="text-muted-foreground">{metrica.rotulo}</span>
          <span className="flex items-baseline gap-1 tabular-nums">
            <span className="text-2xl font-semibold" style={{ color: metrica.cor }}>
              {valor === null ? "—" : <AnimatedNumber value={valor} format={{ minimumFractionDigits: metrica.casas, maximumFractionDigits: metrica.casas }} />}
            </span>
            <span className="text-xs text-muted-foreground">{metrica.unidade}</span>
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        {historico.length > 1 ? (
          <Sparkline history={historico} width={LARGURA} height={ALTURA} padY={PAD_Y} tone="primary" area dot
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

export function Curvas({ linhas }: { linhas: LinhaSim[] }) {
  const ultima = linhas.length > 0 ? linhas[linhas.length - 1] : null
  const alvo = alvoGraus(ultima)
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {METRICAS.map((m) => {
        const historico = linhas
          .map((l) => valorMetrica(l, m))
          .filter((v): v is number => v !== null)
        const valor = ultima ? valorMetrica(ultima, m) : null
        const referencia = m.referencia === "alvo" ? alvo : m.referencia === "zero" ? 0 : null
        return <Painel key={m.chave} metrica={m} historico={historico} valor={valor} referencia={referencia} />
      })}
    </div>
  )
}
