/**
 * rede.tsx — visualizador das ATIVAÇÕES da política (código novo: o catálogo do Motion UI não tem
 * visualizador de rede; `sparkline` é série temporal e `progress-bar` é barra).
 *
 * Desenha as 4 camadas do MLP — entradas (`obs`), h1, h2 e saídas (`act`) — com a cor por |a| e o número
 * dentro do nó. SEM arestas: o contrato da telemetria traz ATIVAÇÕES, não pesos; desenhar ligações seria
 * inventar dados. Sem política carregada (`h1`/`h2` vazios) mostra «—» em vez de zeros.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { corAtivacao, corTextoAtivacao, fmt, rotuloAct, rotuloObs, type LinhaSim } from "@/lib/sim"

const LADO = 26
const ESPACO = 6

function Coluna({ valores, rotulos, titulo, x, largura }: {
  valores: number[]
  rotulos: (i: number) => string
  titulo: string
  x: number
  largura: number
}) {
  const maximo = Math.max(1e-9, ...valores.map((v) => Math.abs(v)))
  const altura = valores.length * (LADO + ESPACO)
  return (
    <g transform={`translate(${x} 18)`}>
      <text x={largura / 2} y={-4} textAnchor="middle" className="fill-muted-foreground text-[10px]">
        {titulo}
      </text>
      {valores.map((v, i) => (
        <g key={`${titulo}-${i}`} transform={`translate(0 ${i * (LADO + ESPACO)})`}>
          <rect width={largura} height={LADO} rx={6} fill={corAtivacao(v, maximo)} />
          <text x={4} y={LADO / 2 + 3} className="text-[9px]" fill={corTextoAtivacao(v, maximo)}>
            {rotulos(i)}
          </text>
          <text x={largura - 4} y={LADO / 2 + 3} textAnchor="end" className="text-[10px] tabular-nums"
            fill={corTextoAtivacao(v, maximo)}>
            {fmt(v, 2)}
          </text>
        </g>
      ))}
      <text x={largura / 2} y={altura + 12} textAnchor="middle" className="fill-muted-foreground text-[10px]">
        {valores.length} {valores.length === 1 ? "nó" : "nós"}
      </text>
    </g>
  )
}

export function Rede({ linha }: { linha: LinhaSim | null }) {
  const obs = linha?.obs ?? []
  const h1 = linha?.h1 ?? []
  const h2 = linha?.h2 ?? []
  const act = linha?.act ?? []
  const temRede = obs.length > 0 && (h1.length > 0 || h2.length > 0)
  const colunas = [obs, h1, h2, act].filter((c) => c.length > 0)
  const largura = 132
  const altura = Math.max(...colunas.map((c) => c.length), 1) * (LADO + ESPACO) + 60
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          rede da política — obs → h1 → h2 → act
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        {!temRede ? (
          <p className="text-sm text-muted-foreground">
            — sem ativações: o runner está com a <strong>ação nula</strong> (nenhuma política carregada).
            Treina (<code>train.py</code>) e arranca com <code>--model out/runs/&lt;ronda&gt;/best_model.zip</code>.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <svg width={colunas.length * (largura + 26)} height={altura} role="img"
              aria-label="ativações das camadas da política">
              <Coluna valores={obs} rotulos={rotuloObs} titulo="obs" x={0} largura={largura} />
              <Coluna valores={h1} rotulos={() => "h1"} titulo="h1" x={largura + 26} largura={largura} />
              {h2.length > 0 && (
                <Coluna valores={h2} rotulos={() => "h2"} titulo="h2" x={2 * (largura + 26)} largura={largura} />
              )}
              <Coluna valores={act} rotulos={rotuloAct} titulo="act" x={(h2.length > 0 ? 3 : 2) * (largura + 26)}
                largura={largura} />
            </svg>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
