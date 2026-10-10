/**
 * SITE do experimento 09 (drone a pairar com política RL) — organizado em SECÇÕES selecionáveis:
 * **Operação** (vigiar o voo) · **Rede** (política, obs, ações) · **Vento** (constante + dinâmico) ·
 * **Bordo** (RPi 5 e, só na planta REAL, Bateria · Motores e potência · Hardware) · **Tudo** (layout
 * completo). O dono escolhe o que ver em vez de ver tudo ao
 * mesmo tempo; a escolha fica guardada (`localStorage`) e há atalhos 1–5.
 *
 * O que NUNCA se esconde (barra fixa do topo, em qualquer secção): o estado crítico (API em baixo) e os
 * controlos REINICIAR/LOOP.
 *
 * Semântica de episódio: NADA de auto-restart no cliente. Quando `estado=episodio_terminado` com o loop
 * desligado («sem reinício») a faixa diz que a física CONTINUA no estado em que ficou e que o REINICIAR
 * (só por clique com hold) é a forma de começar outro episódio; com o LOOP ligado quem reinicia é o
 * BACKEND (o site só faz o POST).
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
import { ControlosCamera } from "@/components/sim/camera"
import { Curvas, ValoresAtuais } from "@/components/sim/curvas"
import {
  ControlosEpisodio,
  ControlosVento,
  type AlvoDinamico,
  type FaseVento,
} from "@/components/sim/controlos"
import { PainelAct, TabelaObs } from "@/components/sim/observacoes"
import { PilhaAvisos, useAvisos } from "@/components/sim/avisos"
import { IndicadorBateria, PainelBateria } from "@/components/sim/bateria"
import { PainelHardware } from "@/components/sim/hardware"
import { PainelMotores } from "@/components/sim/motores"
import { PainelRpi5 } from "@/components/sim/rpi5"
import { Rede } from "@/components/sim/rede"
import { Skeleton, SkeletonReveal } from "@/components/motion-ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"
import { useSim } from "@/hooks/use-sim"
import type { AcaoBateria } from "@/lib/api"
import {
  anunciarComandoDinamico,
  epocaDeParagem,
  invalidarEnviosDinamicos,
  rearmarEnviosDinamicos,
  subscreverEventosVento,
} from "@/lib/paragem"
import {
  ALVO_Z,
  MODOS_CONTINUOS,
  fmt,
  fmtGraus,
  modoAcaoReal,
  plantaEmVigor,
  type CorpoCamera,
  type CorpoVento,
  type CorpoVentoDinamico,
  type Hardware,
} from "@/lib/sim"

/** Subtítulo do cabeçalho na PLANTA REAL (o do cf2 fica o de sempre, dentro do `Cabecalho`). */
function subtituloReal(hardware: Hardware | null): string {
  const build = hardware?.build ? ` · build ${hardware.build}` : ""
  const acao =
    modoAcaoReal(hardware?.modoAcao) === "motores"
      ? "4 aceleradores"
      : "4 ações ctbr (coletivo + taxas)"
  return `Drone real${build} (MuJoCo 3.15) · obs 21 do ator (sensores + estimador de bordo) → ${acao} · alvo z = 1,0 m`
}

/**
 * O corpo do comando é uma PARAGEM? `{modo:"nenhum"}` ou `{ativo:false}` — é o contrato que o painel usa
 * para desligar a dinâmica (PARAR DINÂMICO, o toggle PARADO e a frente a desligar mandam os dois campos).
 */
function ehParagem(corpo: CorpoVentoDinamico): boolean {
  return corpo.modo === "nenhum" || corpo.ativo === false
}

/** O corpo do comando LIGA um modo contínuo (é o único caso em que o painel faz live-apply dos params)? */
function ligaModoContinuo(corpo: CorpoVentoDinamico): boolean {
  return (
    corpo.ativo === true &&
    corpo.modo !== "nenhum" &&
    (MODOS_CONTINUOS as readonly string[]).includes(corpo.modo)
  )
}

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
   * `sim_site.py` é SEM REINÍCIO por omissão — pedido do dono em 2026-10-09; só `--com-loop` arranca
   * CONTÍNUO). O estado local só cobre o instante entre o clique e a resposta do POST — e volta atrás se
   * o POST falhar. Sem isto o painel dizia «SEM REINÍCIO» com o backend a reiniciar sozinho, e a faixa
   * pedia um REINICIAR que não era preciso.
   */
  const [loopOtimista, setLoopOtimista] = useState<boolean | null>(null)
  /** Fallback quando a API ainda não disse nada: SEM REINÍCIO, o mesmo default do backend. */
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

  /**
   * PARAR VENTO: um só pedido (`POST /api/parar`) põe o vento base a 0 **e** desliga o vento dinâmico —
   * é o que garante que nenhuma rajada (one-shot ou de um modo contínuo) fica a atuar depois do PARAR.
   */
  const pararVento = useCallback(() => {
    void sim
      .pararTudo()
      .then(() =>
        notificar("vento parado (0 m/s e vento dinâmico desligado)", "ok")
      )
      .catch((erro: unknown) =>
        notificar(
          `não foi possível parar o vento — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
          "erro"
        )
      )
  }, [notificar, sim])

  /**
   * VENTO DINÂMICO (rajadas · aleatórias · turbulência · frente): só escreve o modo — o episódio NUNCA é
   * reiniciado. O `alvo` diz o que está a caminho do servidor (`modo`, `params` do live-apply, `rajada`,
   * `frente`), para os outros controlos ficarem em espera enquanto o POST não fecha.
   *
   * ESTE É O FUNIL DE TODOS OS COMANDOS DO PAINEL — e é aqui que a PARAGEM é centralizada: qualquer corpo
   * que ponha o modo dinâmico em `nenhum`/`ativo:false` (PARAR DINÂMICO, o toggle PARADO, a frente a
   * desligar, e qualquer botão futuro que faça o mesmo) invalida os applies agendados e cancela o debounce
   * do live-apply de forma SÍNCRONA, ANTES de o POST sair. Sem isto, o `setTimeout` de ~300 ms agendado por
   * uma edição anterior disparava depois do PARAR e reativava o modo (o servidor honra a última escrita).
   * O `PARAR VENTO` faz o mesmo dentro do `use-sim.pararTudo` (e ainda põe o vento base a 0).
   *
   * A época da paragem é lida no momento do envio: se uma paragem aconteceu entretanto, este apply perdeu
   * a corrida (foi escrito e logo sobreposto pelo PARAR, ou nem chegou a sair) e o painel não anuncia
   * sucesso nenhum — quem manda no ecrã é o estado do servidor, que o PARAR já refletiu. Como a
   * invalidação acontece ANTES desta leitura, uma paragem continua a anunciar-se normalmente.
   */
  const enviarVentoDinamico = useCallback(
    (corpo: CorpoVentoDinamico, alvo: AlvoDinamico, descricao: string) => {
      if (ehParagem(corpo)) invalidarEnviosDinamicos()
      else if (ligaModoContinuo(corpo)) {
        rearmarEnviosDinamicos()
        // As outras abas releem o servidor já (sem esperar o poll de 350 ms): o modo ligado aqui aparece lá.
        anunciarComandoDinamico()
      }
      const epocaDoEnvio = epocaDeParagem()
      setDinamicoEmCurso(alvo)
      setFaseDinamico("a_enviar")
      void sim
        .aplicarVentoDinamico(corpo)
        .then(() => {
          if (epocaDeParagem() !== epocaDoEnvio) return // houve um PARAR: este apply não conta
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

  /**
   * Relê o `/api/sim` JÁ (a identidade da função é estável: é a `pollAgora` do `useSim`).
   */
  const atualizarSim = sim.atualizar
  /**
   * Um apply do live-apply foi SUPRIMIDO por estar VELHO: outra aba/cliente parou o vento dinâmico depois
   * da edição e antes de o debounce de ~300 ms disparar. O painel tem de o DIZER (nada de um campo com um
   * valor que o servidor não tem) e volta a mostrar o estado do servidor — daí o aviso + a releitura já.
   */
  const applySuprimido = useCallback(
    (motivo: string) => {
      notificar(`edição não aplicada — ${motivo}`, "info")
      void atualizarSim()
    },
    [atualizarSim, notificar]
  )

  /**
   * Mensagens de OUTRA aba do site (mesma origem, `BroadcastChannel`): uma paragem lá é uma paragem aqui —
   * o painel desta aba relê o servidor de imediato (em vez de esperar o poll) e o dono é avisado. Um
   * comando que liga um modo também faz reler, para a adoção do modo ser imediata. Sem `BroadcastChannel`
   * nada disto corre e a garantia fica com a revalidação do apply (e o poll).
   */
  useEffect(
    () =>
      subscreverEventosVento((evento) => {
        if (evento.tipo === "paragem") {
          notificar(
            "vento dinâmico parado noutra aba/cliente — o painel reflete o servidor",
            "info"
          )
        }
        void atualizarSim()
      }),
    [atualizarSim, notificar]
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

  /**
   * `POST /api/camera` (contrato v2) — os comandos do widget «Câmara» (throttle + commit final
   * vivem no próprio bloco); aqui só se passa pela fila de escritas do `use-sim`, que mantém a
   * ordem dos controlos e relê o `/api/sim` para o ecrã adotar depressa o valor confirmado.
   */
  const enviarCamera = useCallback(
    (corpo: CorpoCamera) => sim.aplicarCamera(corpo),
    [sim]
  )

  /**
   * `POST /api/bateria` (planta real) — RECARREGAR/PACK NOVO do bloco «Bateria». O estado do pedido e os
   * avisos vivem no próprio bloco; aqui só se passa pela fila de escritas do `use-sim`.
   */
  const enviarComandoBateria = useCallback(
    (acao: AcaoBateria) => sim.aplicarBateria(acao),
    [sim]
  )

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
              : "sem reinício: a física continua no estado em que ficou; só o REINICIAR recomeça",
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

  // PLANTA em vigor: a da última linha (o que a física corre), senão a anunciada pela API. Só com
  // `"real"` aparecem os blocos Bateria/Motores/Hardware e os rótulos do ator; com cf2 nada muda.
  const planta = plantaEmVigor(sim.ultima, sim.planta)
  const real = planta === "real"
  const hardware = sim.resumo?.hardware ?? null

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
            indicador={
              real ? (
                <IndicadorBateria bateria={sim.ultima?.bateria ?? null} />
              ) : undefined
            }
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
          {/* SECÇÃO «OPERAÇÃO» — vigiar o voo: selo de estado + modelo, valores atuais, curvas e a
              câmara da janela 3D (bloco «Câmara»: também visível na secção «Tudo»). */}
          <BlocoSecao id="operacao" visivel={ver("operacao")}>
            <Cabecalho
              estado={sim.estado}
              ep={sim.ep}
              passo={sim.passo}
              retorno={sim.retorno}
              modelo={sim.resumo?.modelo ?? null}
              ligacao={sim.ligacao}
              atualizadoEm={sim.atualizadoEm}
              subtitulo={real ? subtituloReal(hardware) : undefined}
            />
            <ValoresAtuais linha={sim.ultima} />
            <Curvas linhas={sim.linhas} zAlvo={ALVO_Z} grande />
            <ControlosCamera
              camera={sim.camera}
              cameraPadrao={sim.cameraPadrao}
              ligado={sim.ligacao === "ligado"}
              onEnviar={enviarCamera}
              onAviso={notificar}
            />
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
                  <TabelaObs
                    linha={sim.ultima}
                    planta={planta}
                    modoAcao={hardware?.modoAcao ?? null}
                  />
                  <PainelAct
                    linha={sim.ultima}
                    resumo={sim.resumo}
                    planta={planta}
                    hardware={hardware}
                  />
                </div>
              </BlocoSecao>

              {/* SECÇÃO «BORDO» — o computador de bordo (Raspberry Pi 5) e, SÓ na planta real, a bateria,
                  os motores/potência e as peças do build (com cf2 estes blocos nem se montam). */}
              <BlocoSecao id="bordo" visivel={ver("bordo")}>
                {real ? (
                  <>
                    <div
                      className={`grid items-start gap-4 ${emTudo ? "2xl:grid-cols-2" : "xl:grid-cols-2"}`}
                    >
                      <PainelBateria
                        linhas={sim.linhas}
                        bateria={sim.ultima?.bateria ?? null}
                        ligado={sim.ligacao === "ligado"}
                        onComando={enviarComandoBateria}
                        onAviso={notificar}
                      />
                      <PainelMotores
                        motores={sim.ultima?.motores ?? null}
                        potencia={sim.ultima?.potencia ?? null}
                        aero={sim.ultima?.aero ?? null}
                        hardware={hardware}
                        ligado={sim.ligacao === "ligado"}
                      />
                    </div>
                    <PainelHardware hardware={hardware} />
                  </>
                ) : null}
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
                  onApplySuprimido={applySuprimido}
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

      <Ajuda planta={planta} />
      <PilhaAvisos toasts={toasts} conteudo={conteudo} fechar={fechar} />
    </div>
  )
}

export default App
