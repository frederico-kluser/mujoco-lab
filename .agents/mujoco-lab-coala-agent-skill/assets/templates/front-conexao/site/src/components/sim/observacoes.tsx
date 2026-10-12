/**
 * observacoes.tsx — tabela da OBSERVAÇÃO (obs[i], o valor cru da telemetria) e painel da AÇÃO (act + `ctrl`).
 *
 * O `ctrl` é o comando FÍSICO que o backend aplicou (`ctrl = acao_para_ctrl(act)` nos passos com ação), com a
 * unidade de `UNIDADE_CTRL`: é o número que interessa a quem olha para o robô, não a ação normalizada da rede.
 * Onde não há dados mostra «—» (nenhum número é inventado).
 */

import { ProgressBar } from "@/components/motion-ui/progress-bar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ROTULO_CTRL, UNIDADE_CTRL, fmt, fmtSinal, rotuloAct, rotuloObs, type LinhaSim } from "@/lib/sim"

/** `true` quando a linha tem o comando físico (passos com AÇÃO aplicada; nas linhas de evento não há ação). */
function temCtrl(linha: LinhaSim | null): boolean {
  return !!linha && linha.ctrl.length > 0 && linha.passo > 0
}

export function TabelaObs({ linha }: { linha: LinhaSim | null }) {
  const obs = linha?.obs ?? []
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          observação — {obs.length > 0 ? `${obs.length} entradas` : "sem dados"}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        {obs.length === 0 ? (
          <p className="text-sm text-muted-foreground">— sem observação (espera pela primeira amostra)</p>
        ) : (
          <div className="space-y-1.5">
            {obs.map((v, i) => (
              <div key={`obs-${i}`} className="flex items-center gap-3">
                <span className="w-24 shrink-0 truncate text-xs text-muted-foreground" title={rotuloObs(i)}>
                  {rotuloObs(i)}
                </span>
                <span className="w-16 shrink-0 text-right text-xs tabular-nums">{fmtSinal(v, 3)}</span>
                <ProgressBar className="flex-1" value={Math.min(1, Math.abs(v))} referenceTick={1} size="sm"
                  tone={v >= 0 ? "var(--chart-1, #ffa24a)" : "var(--chart-2, #7dd3fc)"} />
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function PainelAct({ linha }: { linha: LinhaSim | null }) {
  const act = linha?.act ?? []
  const ctrl = linha?.ctrl ?? []
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          ação — {act.length > 0 ? `${act.length} saída${act.length > 1 ? "s" : ""}` : "sem dados"}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4">
        {act.length === 0 ? (
          <p className="text-sm text-muted-foreground">— sem ação (linha de evento: nenhuma ação aplicada)</p>
        ) : (
          <div className="space-y-2">
            {act.map((v, i) => (
              <div key={`act-${i}`} className="space-y-1">
                <div className="flex items-baseline justify-between text-xs">
                  <span className="text-muted-foreground">{rotuloAct(i)}</span>
                  <span className="tabular-nums">{fmtSinal(v, 3)}</span>
                </div>
                <ProgressBar value={Math.min(1, Math.abs(v))} size="sm" referenceTick={1}
                  tone="var(--chart-3, #c4b5fd)" />
              </div>
            ))}
            <div className="mt-3 flex items-baseline justify-between border-t border-border/50 pt-2 text-sm">
              <span className="text-muted-foreground">{ROTULO_CTRL}</span>
              <span className="tabular-nums">
                {temCtrl(linha) ? `${fmt(ctrl[0], 3)} ${UNIDADE_CTRL}` : "—"}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
