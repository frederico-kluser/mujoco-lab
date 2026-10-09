/**
 * SITE do experimento 09 (drone a pairar com política RL) — organizado em SECÇÕES selecionáveis:
 * **Operação** (vigiar o voo) · **Rede** (política, obs, ações) · **Vento** (constante + dinâmico) ·
 * **Bordo** (RPi 5) · **Tudo** (layout completo). O dono escolhe o que ver em vez de ver tudo ao
 * mesmo tempo; a escolha fica guardada (`localStorage`) e há atalhos 1–5.
 *
 * O que NUNCA se esconde (barra fixa do topo, em qualquer secção): o estado crítico (episódio
 * terminado · API em baixo) e os controlos REINICIAR/LOOP.
 *
 * Semântica de episódio: NADA de auto-restart no cliente. Quando `estado=episodio_terminado` o ecrã diz
 * "clica REINICIAR"; se o LOOP estiver ligado quem reinicia é o BACKEND (o site só faz o POST).
 * Os controlos de vento (constante e dinâmico) escrevem no ficheiro de controlo e nunca reiniciam.
 *
 * Atualizações: o polling vive no `useSim` (topo da página) e os blocos escondem-se com `hidden` sem se
 * desmontarem — os widgets em movimento continuam a atualizar com a secção escondida e, ao voltar, os
 * valores já estão frescos.
 */

import { useCallback, useEffect, useRef, useState } from "react"

import { Ajuda } from "@/components/sim/ajuda"
import {
  BarraEstado,
  BlocoSecao,
  SeletorSecoes,
  useSecao,
} from "@/components/sim/seccoes"
import { Cabecalho } from "@/components/sim/cabecalho"
import { Curvas, ValoresAtuais } from "@/components/sim/curvas"
import {
  ControlosEpisodio,
  ControlosVento,
  type AlvoDinamico,
  type FaseVento,
} from "@/components/sim/controlos"
import { PainelAct, TabelaObs } from "@/components/sim/observacoes"
import { PilhaAvisos, useAvisos } from "@/components/sim/avisos"
import { PainelRpi5 } from "@/components/sim/rpi5"
import { Rede } from "@/components/sim/rede"
import { Skeleton, SkeletonReveal } from "@/components/motion-ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"
import { useSim } from "@/hooks/use-sim"
import {
  ALVO_Z,
  fmt,
  fmtGraus,
  type CorpoVento,
  type CorpoVentoDinamico,
} from "@/lib/sim"

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
  const { seccao, escolher } = useSecao()
  const [faseVento, setFaseVento] = useState<FaseVento>("pronto")
  const [faseDinamico, setFaseDinamico] = useState<FaseVento>("pronto")
  const [dinamicoEmCurso, setDinamicoEmCurso] = useState<AlvoDinamico | null>(
    null
  )
  const [aReiniciar, setAReiniciar] = useState(false)
  /**
   * O LOOP é do BACKEND, não do browser: o valor mostrado vem do `loop` que a API publica (o
   * `sim_site.py` é CONTÍNUO por omissão). O estado local só cobre o instante entre o clique e a
   * resposta do POST — e volta atrás se o POST falhar. Sem isto o painel dizia «OFF» com o backend a
   * reiniciar sozinho, e a faixa vermelha pedia um REINICIAR que não era preciso.
   */
  const [loopOtimista, setLoopOtimista] = useState<boolean | null>(null)
  const loop = loopOtimista ?? sim.loop ?? false
  /** O próximo salto de episódio foi pedido por nós (REINICIAR)? Então não é o backend a fazê-lo. */
  const reinicioManual = useRef(false)
  /** Último episódio visto — para o aviso discreto de «episódio N+1» do modo contínuo. */
  const episodioAnterior = useRef<number | null>(null)

  const aplicarVento = useCallback(
    (corpo: CorpoVento) => {
      setFaseVento("a_enviar")
      void sim
        .aplicarVento(corpo)
        .then(() => {
          setFaseVento("ok")
          notificar(
            `vento aplicado: ${fmt(corpo.vel, 2)} m/s · azimute ${fmtGraus(corpo.azimute)} · elevação ${fmtGraus(corpo.elevacao)}`,
            "ok"
          )
          window.setTimeout(() => setFaseVento("pronto"), 1800)
        })
        .catch((erro: unknown) => {
          setFaseVento("erro")
          notificar(
            `POST /api/vento recusado — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
            "erro"
          )
          window.setTimeout(() => setFaseVento("pronto"), 2500)
        })
    },
    [notificar, sim]
  )

  const pararVento = useCallback(() => {
    void sim
      .pararVento(sim.vento)
      .then(() => notificar("vento parado (velocidade 0 m/s)", "ok"))
      .catch((erro: unknown) =>
        notificar(
          `não foi possível parar o vento — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
          "erro"
        )
      )
  }, [notificar, sim])

  /**
   * VENTO DINÂMICO (rajadas · turbulência · frente): só escreve o modo — o episódio NUNCA é reiniciado.
   * O `alvo` diz qual dos botões está a caminho do servidor, para os outros ficarem em espera.
   */
  const enviarVentoDinamico = useCallback(
    (corpo: CorpoVentoDinamico, alvo: AlvoDinamico, descricao: string) => {
      setDinamicoEmCurso(alvo)
      setFaseDinamico("a_enviar")
      void sim
        .aplicarVentoDinamico(corpo)
        .then(() => {
          setFaseDinamico("ok")
          notificar(`${descricao} — POST /api/vento-dinamico`, "ok")
        })
        .catch((erro: unknown) => {
          setFaseDinamico("erro")
          notificar(
            `POST /api/vento-dinamico recusado — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
            "erro"
          )
        })
        .finally(() => {
          setDinamicoEmCurso(null)
          window.setTimeout(() => setFaseDinamico("pronto"), 1600)
        })
    },
    [notificar, sim]
  )

  const reiniciar = useCallback(() => {
    reinicioManual.current = true
    setAReiniciar(true)
    void sim
      .reiniciar()
      .then((contador) => {
        notificar(
          contador === null
            ? "episódio reiniciado"
            : `episódio reiniciado (contador do servidor: ${fmt(contador, 0)})`,
          "ok"
        )
      })
      .catch((erro: unknown) =>
        notificar(
          `POST /api/reiniciar falhou — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
          "erro"
        )
      )
      .finally(() => setAReiniciar(false))
  }, [notificar, sim])

  const definirLoop = useCallback(
    (ativo: boolean) => {
      const anterior = loop
      setLoopOtimista(ativo)
      void sim
        .definirLoop(ativo)
        .then(() =>
          notificar(
            ativo
              ? "modo contínuo: o backend reinicia o episódio ao terminar"
              : "parar no fim do episódio: fica terminado até clicares REINICIAR",
            "info"
          )
        )
        .catch((erro: unknown) => {
          // O POST falhou: volta-se ao que o servidor dizia (nada de um toggle a mentir).
          setLoopOtimista(anterior)
          notificar(
            `POST /api/loop falhou — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
            "erro"
          )
        })
        .finally(() => setLoopOtimista(null))
    },
    [loop, notificar, sim]
  )

  /**
   * Aviso DISCRETO de episódio novo no modo contínuo: com `loop` ligado o backend vira o episódio
   * sozinho e o dono não quer ser interrompido — um toast de 5 s diz que avançou, sem faixa vermelha
   * nem pedido de REINICIAR. Um REINICIAR nosso já tem o seu próprio aviso, logo não se duplica.
   */
  useEffect(() => {
    const anterior = episodioAnterior.current
    episodioAnterior.current = sim.ep
    if (anterior === null || sim.ep === anterior) return
    if (reinicioManual.current) {
      reinicioManual.current = false
      return
    }
    if (loop) {
      notificar(
        `episódio ${fmt(sim.ep, 0)} · contínuo (o backend reiniciou ao terminar)`,
        "info"
      )
    }
  }, [sim.ep, loop, notificar])

  const semDados = sim.ligacao === "a_ligar" && sim.linhas.length === 0
  const vazio = sim.ligacao === "ligado" && sim.linhas.length === 0
  // Vetor do vento EM VIGOR: o `/api/sim` anuncia-o em `vento.vec` (contrato) ou em `vento_atual.vec`
  // (o `sim_site.py`); em último recurso, na própria linha da telemetria (`vento_vec`).
  const ventoVec = sim.vento.vec ?? sim.ultima?.vento_vec ?? null
  // O que a FÍSICA está a fazer: `vento_atual.modo` da API, senão o `vento_modo` da linha, senão o pedido.
  const modoTelemetria =
    sim.vento.modo ?? sim.ultima?.vento_modo ?? sim.ventoDinamico.modo

  // «Tudo» = layout completo (todas as secções visíveis); as outras secções mostram SÓ o seu bloco.
  const emTudo = seccao === "tudo"
  const ver = (id: "operacao" | "rede" | "vento" | "bordo"): boolean =>
    emTudo || seccao === id

  return (
    <div className="min-h-svh bg-background text-foreground">
      <a
        href="#controlos"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-card focus:px-3 focus:py-2 focus:text-sm"
      >
        saltar para os controlos
      </a>

      {/*
        BARRA FIXA (visível em QUALQUER secção): seletor de secções · REINICIAR · LOOP · estado
        crítico. Um aviso/estado crítico nunca se esconde.
      */}
      <header
        id="controlos"
        className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur"
      >
        <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-2 px-4 py-2">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <div className="flex items-center gap-2">
              <SeletorSecoes seccao={seccao} escolher={escolher} />
              <span
                data-testid="dica-atalhos"
                className="hidden text-[0.65rem] text-muted-foreground xl:inline"
              >
                teclas 1–5
              </span>
            </div>
            <ControlosEpisodio
              compacto
              estado={sim.estado}
              ep={sim.ep}
              ligado={sim.ligacao === "ligado"}
              loop={loop}
              aReiniciar={aReiniciar}
              onReiniciar={reiniciar}
              onLoop={definirLoop}
            />
          </div>
          <BarraEstado
            estado={sim.estado}
            ep={sim.ep}
            loop={loop}
            ligacao={sim.ligacao}
            erro={sim.erro}
          />
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 px-4 py-5">
        {vazio ? (
          <p
            className="rounded-xl bg-muted/50 px-4 py-3 text-xs text-muted-foreground"
            data-testid="estado-vazio"
          >
            o servidor responde mas ainda não publicou passos: as curvas e a
            rede ficam vazias até o episódio arrancar.
          </p>
        ) : null}

        <SkeletonReveal loading={semDados} skeleton={<Esqueleto />}>
          {/* SECÇÃO «OPERAÇÃO» — vigiar o voo: selo de estado + modelo, valores atuais e curvas grandes. */}
          <BlocoSecao id="operacao" visivel={ver("operacao")}>
            <Cabecalho
              estado={sim.estado}
              ep={sim.ep}
              passo={sim.passo}
              retorno={sim.retorno}
              modelo={sim.resumo?.modelo ?? null}
              ligacao={sim.ligacao}
              atualizadoEm={sim.atualizadoEm}
            />
            <ValoresAtuais linha={sim.ultima} />
            <Curvas linhas={sim.linhas} zAlvo={ALVO_Z} grande />
          </BlocoSecao>

          <div
            className={
              emTudo
                ? "grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_23rem]"
                : "flex flex-col gap-4"
            }
          >
            <main className="flex min-w-0 flex-col gap-4">
              {/* SECÇÃO «REDE» — a política a decidir: ativações, observação e ação. */}
              <BlocoSecao id="rede" visivel={ver("rede")}>
                <Rede
                  linha={sim.ultima}
                  estadoCorrendo={sim.estado === "a_correr"}
                />
                <div className="grid gap-4 xl:grid-cols-2">
                  <TabelaObs linha={sim.ultima} />
                  <PainelAct linha={sim.ultima} resumo={sim.resumo} />
                </div>
              </BlocoSecao>

              {/* SECÇÃO «BORDO» — o computador de bordo (Raspberry Pi 5). */}
              <BlocoSecao id="bordo" visivel={ver("bordo")}>
                <PainelRpi5 rpi5={sim.rpi5} ligado={sim.ligacao === "ligado"} />
              </BlocoSecao>
            </main>

            <aside
              className={
                emTudo
                  ? "flex flex-col gap-3 lg:sticky lg:top-[7.5rem] lg:max-h-[calc(100svh-8.5rem)] lg:overflow-y-auto"
                  : "flex flex-col gap-3"
              }
            >
              {/* SECÇÃO «VENTO» — vento constante (sliders + rosa), vento dinâmico e as ações. */}
              <BlocoSecao id="vento" visivel={ver("vento")}>
                <ControlosVento
                  vento={sim.vento}
                  vec={ventoVec}
                  dinamico={sim.ventoDinamico}
                  modoTelemetria={modoTelemetria}
                  estado={sim.estado}
                  loop={loop}
                  ligado={sim.ligacao === "ligado"}
                  faseVento={faseVento}
                  faseDinamico={faseDinamico}
                  emCurso={dinamicoEmCurso}
                  onAplicarVento={aplicarVento}
                  onPararVento={pararVento}
                  onVentoDinamico={enviarVentoDinamico}
                />
                <p className="px-1 text-[0.65rem] text-muted-foreground">
                  polling GET /api/sim a 2,9 Hz · {fmt(sim.linhas.length, 0)}{" "}
                  linhas no histórico local · ações: POST /api/vento ·
                  /api/vento-dinamico · /api/reiniciar · /api/loop
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

export default App
