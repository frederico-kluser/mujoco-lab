/**
 * App.tsx — página única do site do template `lab-padrao`: cabeçalho · curvas · rede · RPi 5 · obs/ação ·
 * controlos (vento + vento dinâmico + REINICIAR/LOOP) · ajuda «?».
 *
 * Sem navegação. Quem manda é o `useSim()` (polling de `GET /api/sim` a ~2,9 Hz) e as ações fazem POST nos
 * endpoints do contrato. O site NUNCA reinicia sozinho: mostra «episódio terminado — clica REINICIAR» e espera.
 * Os controlos de vento (constante e dinâmico) escrevem no ficheiro de controlo e nunca reiniciam o episódio.
 */

import { useCallback } from "react"

import { Ajuda } from "@/components/sim/ajuda"
import { Cabecalho } from "@/components/sim/cabecalho"
import { Controlos } from "@/components/sim/controlos"
import { Curvas } from "@/components/sim/curvas"
import { PainelAct, TabelaObs } from "@/components/sim/observacoes"
import { PilhaAvisos, useAvisos } from "@/components/sim/avisos"
import { PainelRpi5 } from "@/components/sim/rpi5"
import { Rede } from "@/components/sim/rede"
import { Card, CardContent } from "@/components/ui/card"
import { useSim } from "@/hooks/use-sim"
import { fmt } from "@/lib/sim"

export default function App() {
  const sim = useSim()
  const { toasts, conteudo, notificar, fechar } = useAvisos()
  const ultima = sim.ultima

  const aviso = useCallback(
    (tom: "ok" | "erro" | "info", texto: string) => {
      notificar(texto, tom)
    },
    [notificar],
  )

  // Vetor do vento EM VIGOR: a API anuncia-o em `vento.vec`; em último recurso, na própria linha da
  // telemetria (`vento_vec`) — é o que a rosa dos ventos e o selo de modo mostram.
  const ventoVec = sim.vento?.vec ?? ultima?.vento_vec ?? null
  // O que a FÍSICA está a fazer: `vento.modo` da API, senão o `vento_modo` da linha, senão o modo pedido.
  const modoTelemetria = sim.vento?.modo ?? ultima?.vento_modo ?? sim.ventoDinamico.modo

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-3 p-4">
      <Cabecalho resumo={sim.resumo} estado={sim.estado} ep={sim.ep} passo={sim.passo} retorno={sim.retorno}
        ligacao={sim.ligacao} atualizadoEm={sim.atualizadoEm} />

      {sim.erro && (
        <Card className="border-rose-500/40 py-3">
          <CardContent className="px-4 text-sm text-rose-300">
            erro de ligação: {sim.erro} — confirma que o <code>sim_site.py</code> está a correr e recarrega a página.
          </CardContent>
        </Card>
      )}

      <Curvas linhas={sim.linhas} />

      <div className="grid gap-3 lg:grid-cols-[2fr_1fr]">
        <Rede linha={ultima} />
        <div className="flex flex-col gap-3">
          <PainelAct linha={ultima} />
          <TabelaObs linha={ultima} />
        </div>
      </div>

      {/* Computador de bordo: TODOS os projetos correm no Raspberry Pi 5 — o painel vem do deploy.py. */}
      <PainelRpi5 rpi5={sim.rpi5} ligado={sim.ligacao === "ligado"} />

      <Controlos vento={sim.vento} vec={ventoVec} dinamico={sim.ventoDinamico} modoTelemetria={modoTelemetria}
        estado={sim.estado} loop={sim.resumo?.loop ?? false}
        contadorReiniciar={sim.resumo?.contador_reiniciar ?? null}
        onVento={async (corpo, ativo) => {
          if (ativo) {
            await sim.aplicarVento(corpo)
          } else {
            await sim.pararVento({ ...corpo, ativo: false, vec: null, modo: null })
          }
        }}
        onVentoDinamico={sim.aplicarVentoDinamico}
        onReiniciar={sim.reiniciar} onLoop={sim.definirLoop} aviso={aviso} />

      <footer className="pb-6 text-center text-xs text-muted-foreground">
        {sim.linhas.length} amostras em memória · {sim.respostas} respostas do servidor · última t ={" "}
        {fmt(ultima?.t ?? null, 2)} s · ações: POST /api/vento · /api/vento-dinamico · /api/reiniciar ·
        /api/loop · padrão do laboratório <code>padrao-simulacao-clean-site</code>
      </footer>

      <Ajuda />
      <PilhaAvisos toasts={toasts} conteudo={conteudo} fechar={fechar} />
    </main>
  )
}
