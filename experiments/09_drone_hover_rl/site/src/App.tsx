/**
 * SITE do experimento 09 (drone a pairar com política RL) — monta tudo:
 * cabeçalho · curvas · rede 16→64→64→4 · obs/ações · controlos (vento, REINICIAR, LOOP).
 *
 * Semântica de episódio: NADA de auto-restart no cliente. Quando `estado=episodio_terminado` o ecrã diz
 * "clica REINICIAR"; se o LOOP estiver ligado quem reinicia é o BACKEND (o site só faz o POST).
 */

import { useCallback, useState } from "react"

import { Cabecalho } from "@/components/sim/cabecalho"
import { Curvas } from "@/components/sim/curvas"
import { Controlos, type FaseVento } from "@/components/sim/controlos"
import { PainelAct, TabelaObs } from "@/components/sim/observacoes"
import { PilhaAvisos, useAvisos } from "@/components/sim/avisos"
import { Rede } from "@/components/sim/rede"
import { Skeleton, SkeletonReveal } from "@/components/motion-ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"
import { useSim } from "@/hooks/use-sim"
import { ALVO_Z, fmt, fmtGraus, type CorpoVento } from "@/lib/sim"

function Esqueleto() {
  return (
    <div className="flex flex-col gap-3" data-testid="esqueleto">
      <div className="grid gap-3 sm:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} size="sm">
            <CardContent className="flex flex-col gap-3">
              <Skeleton className="h-3 w-24 rounded-full" />
              <Skeleton className="h-16 w-full rounded-lg" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardContent className="flex flex-col gap-3">
          <Skeleton className="h-3 w-52 rounded-full" />
          <Skeleton className="h-40 w-full rounded-lg" />
        </CardContent>
      </Card>
    </div>
  )
}

export function App() {
  const sim = useSim()
  const { toasts, conteudo, notificar, fechar } = useAvisos()
  const [faseVento, setFaseVento] = useState<FaseVento>("pronto")
  const [aReiniciar, setAReiniciar] = useState(false)
  const [loop, setLoop] = useState(false)

  const aplicarVento = useCallback(
    (corpo: CorpoVento) => {
      setFaseVento("a_enviar")
      void sim
        .aplicarVento(corpo)
        .then(() => {
          setFaseVento("ok")
          notificar(
            `vento aplicado: ${fmt(corpo.vel, 2)} m/s · azimute ${fmtGraus(corpo.azimute)} · elevação ${fmtGraus(corpo.elevacao)}`,
            "ok",
          )
          window.setTimeout(() => setFaseVento("pronto"), 1800)
        })
        .catch((erro: unknown) => {
          setFaseVento("erro")
          notificar(
            `POST /api/vento recusado — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
            "erro",
          )
          window.setTimeout(() => setFaseVento("pronto"), 2500)
        })
    },
    [notificar, sim],
  )

  const pararVento = useCallback(() => {
    void sim
      .pararVento(sim.vento)
      .then(() => notificar("vento parado (velocidade 0 m/s)", "ok"))
      .catch((erro: unknown) =>
        notificar(
          `não foi possível parar o vento — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
          "erro",
        ),
      )
  }, [notificar, sim])

  const reiniciar = useCallback(() => {
    setAReiniciar(true)
    void sim
      .reiniciar()
      .then((contador) => {
        notificar(
          contador === null
            ? "episódio reiniciado"
            : `episódio reiniciado (contador do servidor: ${fmt(contador, 0)})`,
          "ok",
        )
      })
      .catch((erro: unknown) =>
        notificar(
          `POST /api/reiniciar falhou — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
          "erro",
        ),
      )
      .finally(() => setAReiniciar(false))
  }, [notificar, sim])

  const definirLoop = useCallback(
    (ativo: boolean) => {
      setLoop(ativo)
      void sim
        .definirLoop(ativo)
        .then(() =>
          notificar(
            ativo
              ? "LOOP ligado: o backend reinicia o episódio ao terminar"
              : "LOOP desligado: o episódio fica terminado até clicares REINICIAR",
            "info",
          ),
        )
        .catch((erro: unknown) => {
          setLoop(!ativo)
          notificar(
            `POST /api/loop falhou — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
            "erro",
          )
        })
    },
    [notificar, sim],
  )

  const semDados = sim.ligacao === "a_ligar" && sim.linhas.length === 0
  const vazio = sim.ligacao === "ligado" && sim.linhas.length === 0

  return (
    <div className="min-h-svh bg-background text-foreground">
      <a
        href="#controlos"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-card focus:px-3 focus:py-2 focus:text-sm"
      >
        saltar para os controlos
      </a>

      <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 px-4 py-5">
        <Cabecalho
          estado={sim.estado}
          ep={sim.ep}
          passo={sim.passo}
          retorno={sim.retorno}
          modelo={sim.resumo?.modelo ?? null}
          ligacao={sim.ligacao}
          erro={sim.erro}
          atualizadoEm={sim.atualizadoEm}
        />

        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_23rem]">
          <main className="flex min-w-0 flex-col gap-4">
            {vazio ? (
              <p
                className="rounded-xl bg-muted/50 px-4 py-3 text-xs text-muted-foreground"
                data-testid="estado-vazio"
              >
                o servidor responde mas ainda não publicou passos: as curvas e a rede ficam vazias até o
                episódio arrancar.
              </p>
            ) : null}

            <SkeletonReveal loading={semDados} skeleton={<Esqueleto />}>
              <div className="flex flex-col gap-4">
                <Curvas linhas={sim.linhas} zAlvo={ALVO_Z} />
                <Rede linha={sim.ultima} estadoCorrendo={sim.estado === "a_correr"} />
                <div className="grid gap-4 xl:grid-cols-2">
                  <TabelaObs linha={sim.ultima} />
                  <PainelAct linha={sim.ultima} resumo={sim.resumo} />
                </div>
              </div>
            </SkeletonReveal>
          </main>

          <aside
            id="controlos"
            className="flex flex-col gap-3 lg:sticky lg:top-4 lg:max-h-[calc(100svh-2rem)] lg:overflow-y-auto"
          >
            <Controlos
              vento={sim.vento}
              estado={sim.estado}
              ep={sim.ep}
              ligado={sim.ligacao === "ligado"}
              loop={loop}
              faseVento={faseVento}
              aReiniciar={aReiniciar}
              onAplicarVento={aplicarVento}
              onPararVento={pararVento}
              onReiniciar={reiniciar}
              onLoop={definirLoop}
            />
            <p className="px-1 text-[0.65rem] text-muted-foreground">
              polling GET /api/sim a 2,9 Hz · {fmt(sim.linhas.length, 0)} linhas no histórico local ·
              ações: POST /api/vento · /api/reiniciar · /api/loop
            </p>
          </aside>
        </div>
      </div>

      <PilhaAvisos toasts={toasts} conteudo={conteudo} fechar={fechar} />
    </div>
  )
}

export default App
