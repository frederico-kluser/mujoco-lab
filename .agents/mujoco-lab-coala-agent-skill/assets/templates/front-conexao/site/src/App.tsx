/**
 * App.tsx — página única do site do padrão (`padrao-simulacao-clean-site`): barra fixa + SECÇÕES.
 *
 * O conteúdo está organizado em CINCO secções escolhíveis (Operação · Rede · Vento · Bordo · Tudo) com o
 * seletor no topo, atalhos de teclado 1–5 e a escolha guardada no `localStorage` (ver `seccoes.tsx`). Os
 * blocos escondem-se com o atributo `hidden` — nunca se desmontam, para os widgets continuarem a atualizar.
 *
 * A BARRA DO TOPO é fixa e mostra SEMPRE o crítico: o seletor de secções, o REINICIAR/LOOP (`ControlosEpisodio`
 * em modo compacto) e a faixa de estado (`BarraEstado`: episódio terminado · API em baixo). Um aviso crítico
 * nunca se esconde, seja qual for a secção.
 *
 * Sem navegação nem auto-restart: quem manda é o `useSim()` (polling de `GET /api/sim` a ~2,9 Hz) e as ações
 * fazem POST nos endpoints do contrato. O site NUNCA reinicia sozinho: mostra «episódio terminado — clica
 * REINICIAR» e espera (ou o LOOP, que é do backend). Os controlos de vento (constante e dinâmico) escrevem no
 * ficheiro de controlo e nunca reiniciam o episódio.
 */

import { useCallback, useState } from "react"

import { Ajuda } from "@/components/sim/ajuda"
import { Cabecalho } from "@/components/sim/cabecalho"
import { ControlosEpisodio, ControlosVento, type AlvoDinamico, type FaseVento } from "@/components/sim/controlos"
import { Curvas, ValoresAtuais } from "@/components/sim/curvas"
import { PainelAct, TabelaObs } from "@/components/sim/observacoes"
import { PilhaAvisos, useAvisos } from "@/components/sim/avisos"
import { PainelRpi5 } from "@/components/sim/rpi5"
import { Rede } from "@/components/sim/rede"
import { BarraEstado, BlocoSecao, SeletorSecoes, useSecao } from "@/components/sim/seccoes"
import { Skeleton, SkeletonReveal } from "@/components/motion-ui/skeleton"
import { useSim } from "@/hooks/use-sim"
import { fmt, type CorpoVento, type CorpoVentoDinamico } from "@/lib/sim"

/** Esqueleto mostrado antes da primeira leitura da API (nada de números inventados). */
function Esqueleto() {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 lg:grid-cols-2">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

export default function App() {
  const sim = useSim()
  const { toasts, conteudo, notificar, fechar } = useAvisos()
  const { seccao, escolher } = useSecao()
  const [faseVento, setFaseVento] = useState<FaseVento>("pronto")
  const [faseDinamico, setFaseDinamico] = useState<FaseVento>("pronto")
  const [dinamicoEmCurso, setDinamicoEmCurso] = useState<AlvoDinamico | null>(null)
  const [aReiniciar, setAReiniciar] = useState(false)
  const [loop, setLoop] = useState(false)

  const aviso = useCallback(
    (tom: "ok" | "erro" | "info", texto: string) => {
      notificar(texto, tom)
    },
    [notificar],
  )

  const aplicarVento = useCallback(
    (corpo: CorpoVento) => {
      setFaseVento("a_enviar")
      void sim
        .aplicarVento(corpo)
        .then(() => {
          setFaseVento("ok")
          aviso("ok", `vento aplicado: ${fmt(corpo.vel, 2)} m/s · ${fmt(corpo.azimute, 0)}° · elev ${fmt(corpo.elevacao, 0)}°`)
          window.setTimeout(() => setFaseVento("pronto"), 1800)
        })
        .catch((erro: unknown) => {
          setFaseVento("erro")
          aviso("erro", `POST /api/vento recusado — ${erro instanceof Error ? erro.message : "falha desconhecida"}`)
          window.setTimeout(() => setFaseVento("pronto"), 2500)
        })
    },
    [aviso, sim],
  )

  const pararVento = useCallback(() => {
    setFaseVento("a_enviar")
    void sim
      .pararVento(sim.vento ?? { vel: 0, azimute: 0, elevacao: 0, ativo: false, vec: null, modo: null })
      .then(() => {
        setFaseVento("ok")
        aviso("ok", "vento parado (0 m/s no mesmo azimute)")
        window.setTimeout(() => setFaseVento("pronto"), 1800)
      })
      .catch((erro: unknown) => {
        setFaseVento("erro")
        aviso("erro", `não foi possível parar o vento — ${erro instanceof Error ? erro.message : "falha desconhecida"}`)
        window.setTimeout(() => setFaseVento("pronto"), 2500)
      })
  }, [aviso, sim])

  /**
   * VENTO DINÂMICO (rajadas · turbulência · frente · rajada única): só escreve o modo — o episódio NUNCA é
   * reiniciado. O `alvo` diz qual dos botões está a caminho do servidor, para os outros ficarem em espera.
   */
  const enviarVentoDinamico = useCallback(
    (corpo: CorpoVentoDinamico, alvo: AlvoDinamico, descricao: string) => {
      setDinamicoEmCurso(alvo)
      setFaseDinamico("a_enviar")
      void sim
        .aplicarVentoDinamico(corpo)
        .then(() => {
          setFaseDinamico("ok")
          aviso("ok", `${descricao} — POST /api/vento-dinamico`)
        })
        .catch((erro: unknown) => {
          setFaseDinamico("erro")
          aviso("erro", `POST /api/vento-dinamico recusado — ${erro instanceof Error ? erro.message : "falha desconhecida"}`)
        })
        .finally(() => {
          setDinamicoEmCurso(null)
          window.setTimeout(() => setFaseDinamico("pronto"), 1600)
        })
    },
    [aviso, sim],
  )

  const reiniciar = useCallback(() => {
    setAReiniciar(true)
    void sim
      .reiniciar()
      .then((contador) => {
        aviso("ok", contador === null ? "episódio reiniciado" : `episódio reiniciado (contador do servidor: ${fmt(contador, 0)})`)
      })
      .catch((erro: unknown) => {
        aviso("erro", `POST /api/reiniciar falhou — ${erro instanceof Error ? erro.message : "falha desconhecida"}`)
      })
      .finally(() => setAReiniciar(false))
  }, [aviso, sim])

  const definirLoop = useCallback(
    (ativo: boolean) => {
      setLoop(ativo)
      void sim
        .definirLoop(ativo)
        .then(() =>
          aviso(
            "info",
            ativo
              ? "LOOP ligado: o backend reinicia o episódio ao terminar"
              : "LOOP desligado: o episódio fica terminado até clicares REINICIAR",
          ),
        )
        .catch((erro: unknown) => {
          setLoop(!ativo)
          aviso("erro", `POST /api/loop falhou — ${erro instanceof Error ? erro.message : "falha desconhecida"}`)
        })
    },
    [aviso, sim],
  )

  const semDados = sim.ligacao === "a_ligar" && sim.linhas.length === 0
  const vazio = sim.ligacao === "ligado" && sim.linhas.length === 0
  // Vetor do vento EM VIGOR: a API anuncia-o em `vento.vec`; em último recurso, na linha da telemetria.
  const ventoVec = sim.vento?.vec ?? sim.ultima?.vento_vec ?? null
  // O que a FÍSICA está a fazer: `vento.modo` da API, senão o `vento_modo` da linha, senão o modo pedido.
  const modoTelemetria = sim.vento?.modo ?? sim.ultima?.vento_modo ?? sim.ventoDinamico.modo

  // «Tudo» = layout completo (todas as secções visíveis); as outras mostram SÓ o seu bloco.
  const emTudo = seccao === "tudo"
  const ver = (id: "operacao" | "rede" | "vento" | "bordo"): boolean => emTudo || seccao === id

  return (
    <div className="min-h-svh bg-background text-foreground">
      <a href="#seccoes"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-card focus:px-3 focus:py-2 focus:text-sm">
        saltar para as secções
      </a>

      {/*
        BARRA FIXA (visível em QUALQUER secção): seletor de secções · REINICIAR · LOOP · estado crítico.
        Um aviso/estado crítico nunca se esconde.
      */}
      <header id="seccoes" className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-2 px-4 py-2">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <div className="flex items-center gap-2">
              <SeletorSecoes seccao={seccao} escolher={escolher} />
              <span data-testid="dica-atalhos" className="hidden text-[0.65rem] text-muted-foreground xl:inline">
                teclas 1–5
              </span>
            </div>
            <ControlosEpisodio compacto estado={sim.estado} ep={sim.ep} ligado={sim.ligacao === "ligado"}
              loop={loop} aReiniciar={aReiniciar} onReiniciar={reiniciar} onLoop={definirLoop} />
          </div>
          {/* `ep ?? 0`: a barra só mostra o número quando o episódio TERMINOU (aí há dados); o `useSim` é que
            mantém o `null` para os contadores honestos do cabeçalho («—» sem dados). */}
          <BarraEstado estado={sim.estado} ep={sim.ep ?? 0} loop={loop} ligacao={sim.ligacao} erro={sim.erro} />
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 px-4 py-5">
        {vazio ? (
          <p className="rounded-xl bg-muted/50 px-4 py-3 text-xs text-muted-foreground" data-testid="estado-vazio">
            o servidor responde mas ainda não publicou passos: as curvas e a rede ficam vazias até o episódio arrancar.
          </p>
        ) : null}

        <SkeletonReveal loading={semDados} skeleton={<Esqueleto />}>
          {/* SECÇÃO «OPERAÇÃO» — vigiar a operação: cabeçalho, valores atuais e curvas grandes. */}
          <BlocoSecao id="operacao" visivel={ver("operacao")}>
            <Cabecalho resumo={sim.resumo} estado={sim.estado} ep={sim.ep} passo={sim.passo} retorno={sim.retorno}
              ligacao={sim.ligacao} atualizadoEm={sim.atualizadoEm} />
            <ValoresAtuais linha={sim.ultima} />
            <Curvas linhas={sim.linhas} grande />
          </BlocoSecao>

          <div className={emTudo ? "grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_23rem]" : "flex flex-col gap-4"}>
            <main className="flex min-w-0 flex-col gap-4">
              {/* SECÇÃO «REDE» — a política a decidir: ativações, observação e ação. */}
              <BlocoSecao id="rede" visivel={ver("rede")}>
                <Rede linha={sim.ultima} />
                <div className="grid gap-4 xl:grid-cols-2">
                  <TabelaObs linha={sim.ultima} />
                  <PainelAct linha={sim.ultima} />
                </div>
              </BlocoSecao>

              {/* SECÇÃO «BORDO» — o computador de bordo (Raspberry Pi 5). */}
              <BlocoSecao id="bordo" visivel={ver("bordo")}>
                <PainelRpi5 rpi5={sim.rpi5} ligado={sim.ligacao === "ligado"} />
              </BlocoSecao>
            </main>

            <aside className={emTudo
              ? "flex flex-col gap-3 lg:sticky lg:top-[7.5rem] lg:max-h-[calc(100svh-8.5rem)] lg:overflow-y-auto"
              : "flex flex-col gap-3"}>
              {/* SECÇÃO «VENTO» — vento constante (sliders + rosa), vento dinâmico e as ações. */}
              <BlocoSecao id="vento" visivel={ver("vento")}>
                <ControlosVento vento={sim.vento} vec={ventoVec} dinamico={sim.ventoDinamico}
                  modoTelemetria={modoTelemetria} ligado={sim.ligacao === "ligado"} faseVento={faseVento}
                  faseDinamico={faseDinamico} emCurso={dinamicoEmCurso} onAplicarVento={aplicarVento}
                  onPararVento={pararVento} onVentoDinamico={enviarVentoDinamico} />
                <p className="px-1 text-[0.65rem] text-muted-foreground">
                  polling GET /api/sim a 2,9 Hz · {fmt(sim.linhas.length, 0)} linhas no histórico local · ações:
                  POST /api/vento · /api/vento-dinamico · /api/reiniciar · /api/loop
                </p>
              </BlocoSecao>
            </aside>
          </div>
        </SkeletonReveal>
      </div>

      <Ajuda />
      <PilhaAvisos toasts={toasts} conteudo={conteudo} fechar={fechar} />
    </div>
  )
}
