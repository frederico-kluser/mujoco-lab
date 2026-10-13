/**
 * Os PAINÉIS DE DETALHE (os de sempre, de `components/sim/`) carregados A PEDIDO: só entram no
 * browser quando a janela que os usa abre pela primeira vez. São a parte pesada do site (curvas,
 * bateria, rede, computador de bordo) e nada disto é preciso para voar — o cockpit arranca só com a
 * vista, o HUD e as três janelas principais.
 */

import { Suspense, lazy, type ReactNode } from "react"

export const PainelVoo = lazy(() =>
  import("@/components/sim/painel-voo").then((m) => ({ default: m.PainelVoo }))
)
export const Curvas = lazy(() =>
  import("@/components/sim/curvas").then((m) => ({ default: m.Curvas }))
)
export const PainelBateria = lazy(() =>
  import("@/components/sim/bateria").then((m) => ({ default: m.PainelBateria }))
)
export const PainelMotores = lazy(() =>
  import("@/components/sim/motores").then((m) => ({ default: m.PainelMotores }))
)
export const Rede = lazy(() =>
  import("@/components/sim/rede").then((m) => ({ default: m.Rede }))
)
export const TabelaObs = lazy(() =>
  import("@/components/sim/observacoes").then((m) => ({ default: m.TabelaObs }))
)
export const PainelAct = lazy(() =>
  import("@/components/sim/observacoes").then((m) => ({ default: m.PainelAct }))
)
export const PainelRpi5 = lazy(() =>
  import("@/components/sim/rpi5").then((m) => ({ default: m.PainelRpi5 }))
)
export const JanelaSistema = lazy(() =>
  import("@/components/cockpit/janela-sistema").then((m) => ({
    default: m.JanelaSistema,
  }))
)

/** Enquanto o painel chega (uma vez por sessão, uns milissegundos em rede local). */
export function ACarregar({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <p className="px-1 py-6 text-center text-sm text-muted-foreground" data-testid="a-carregar">
          a abrir…
        </p>
      }
    >
      {children}
    </Suspense>
  )
}
