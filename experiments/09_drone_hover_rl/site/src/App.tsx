/**
 * COCKPIT do experimento 09 (contrato r13, `INTERFACE.md` §0) — um ecrã ÚNICO de 100svw × 100svh, sem
 * scroll de página em nenhuma resolução:
 *
 *  1. VISTA — o fundo permanente: a câmara de bordo (1.ª pessoa) ou a da simulação (3.ª pessoa); `F`
 *     troca e a outra fica na miniatura (`components/cockpit/vista.tsx`);
 *  2. HUD — os instrumentos sobrepostos, a 50 Hz por refs (`components/cockpit/hud.tsx`);
 *  3. DOCA — a barra de ícones que abre as janelas, com o REINICIAR de manter premido;
 *  4. JANELAS — flutuantes, arrastáveis, com a posição guardada: Voo · Bola · Vento (as principais) e
 *     Sensores · Energia · Gráficos · Sistema · Ajuda (o detalhe, a pedido).
 *
 * O que o dono pediu e onde está resolvido:
 *  · «sem scroll, sempre a visão» → a vista é o ecrã; tudo o resto sobrepõe-se ou abre-se a pedido;
 *  · «o modo de controlar já vem ativado» → não há armar: as teclas valem desde o arranque
 *    (`ativo: true` em todos os `POST /api/voo`) e os keycaps do HUD acendem no instante;
 *  · «não quero opções» → não há seletor de controlador nem de loop: voa o que ganhou na medição;
 *  · vento com três botões e o modo «seguir a bola» → as janelas Vento e Bola (teclas V e B).
 *
 * DESEMPENHO: com as janelas de detalhe fechadas a página mantém só o stream da vista, o SSE do HUD e
 * um `GET /api/state` por segundo. O `GET /api/sim` (200 linhas de telemetria por resposta) só é
 * sondado enquanto houver uma janela que viva do histórico (`precisaDeSim`).
 */

import { useCallback, useEffect, useRef, useState } from "react"

import { Doca, ICONE_JANELA, type GestoReiniciar } from "@/components/cockpit/doca"
import { Hud } from "@/components/cockpit/hud"
import { Janela } from "@/components/cockpit/janela"
import { JanelaAjuda } from "@/components/cockpit/janela-ajuda"
import { JanelaBola } from "@/components/cockpit/janela-bola"
import { JanelaEnergia } from "@/components/cockpit/janela-energia"
import { JanelaVento } from "@/components/cockpit/janela-vento"
import { JanelaVoo } from "@/components/cockpit/janela-voo"
import { Vista } from "@/components/cockpit/vista"
import {
  ACarregar,
  Curvas,
  JanelaSistema,
  PainelAct,
  PainelBateria,
  PainelMotores,
  PainelRpi5,
  PainelVoo,
  Rede,
  TabelaObs,
} from "@/components/cockpit/detalhe"
import { PilhaAvisos, useAvisos } from "@/components/sim/avisos"
import {
  useBola,
  useJanelas,
  usePaginaVisivel,
  usePiloto,
  useResumoHud,
  useTiro,
  useVento,
  useViewport,
  useVista,
} from "@/hooks/use-cockpit"
import { useSim } from "@/hooks/use-sim"
import {
  JANELAS,
  acaoDaTecla,
  atrasoDaImagem,
  eCampoDeTexto,
  posicaoInicial,
  precisaDeSim,
  rumoParaFixar,
  type IdJanela,
  type Par,
} from "@/lib/cockpit"
import {
  bola as controloBola,
  camera,
  carregarCameraEmVigor,
  definirApiLigada,
  definirPlantaDaCamera,
  ligarAvisos,
  piloto as controloPiloto,
  tiro as controloTiro,
  vento as controloVento,
} from "@/lib/cockpit-controlos"
import { hud } from "@/lib/hud-store"
import { ALVO_Z, plantaEmVigor } from "@/lib/sim"

/** Largura da janela Energia com o detalhe aberto (os painéis de bateria e motores lado a lado). */
const LARGURA_ENERGIA_DETALHE = 780

export function App() {
  const janelas = useJanelas()
  const vista = useVista()
  const viewport = useViewport()
  const visivel = usePaginaVisivel()
  const resumoHud = useResumoHud()
  const piloto = usePiloto()
  const tiro = useTiro()
  const vento = useVento()
  const bola = useBola()
  const { toasts, conteudo, notificar, fechar } = useAvisos()
  const [energiaDetalhe, setEnergiaDetalhe] = useState(false)
  const [aReiniciar, setAReiniciar] = useState(false)
  const [aRecarregar, setARecarregar] = useState(false)
  /** A vista tem imagem? (é ela que o diz; sem imagem o HUD não desenha o horizonte nem a mira) */
  const [comImagem, setComImagem] = useState(false)

  // Quem voa, visto pelo HUD (chega antes do `/api/state`): tudo o que não é a cascata clássica é a
  // política RL — é o único caso em que a janela Sistema precisa do histórico.
  const rl = resumoHud.ligacao === "ligado" && resumoHud.controlador !== "classico"
  const simAtivo = precisaDeSim(janelas.estado.abertas, { energiaDetalhe, rl })
  const sim = useSim({ ativo: simAtivo })

  const apiLigada = sim.ligacao === "ligado"
  const planta = plantaEmVigor(simAtivo ? sim.ultima : null, sim.planta)
  const real = planta === "real"
  const hardware = sim.resumo?.hardware ?? null
  const ultima = simAtivo ? sim.ultima : null
  const imagemBordo: Par | null = sim.fpv?.saida ?? null

  // ------------------------------------------------------------- ligações aos controlos de módulo
  useEffect(() => {
    ligarAvisos(notificar)
    return () => ligarAvisos(null)
  }, [notificar])

  useEffect(() => {
    definirApiLigada(apiLigada)
  }, [apiLigada])

  useEffect(() => {
    definirPlantaDaCamera(planta)
  }, [planta])

  // O que o servidor diz (1 Hz) entra nos controlos — que só o adotam sem gesto local a decorrer.
  const pedidoVoo = sim.voo?.pedido ?? null
  useEffect(() => {
    if (pedidoVoo === null) return
    controloPiloto.adotarServidor({
      ativo: pedidoVoo.ativo,
      yaw_alvo: pedidoVoo.yaw_alvo,
      segui_alvo: pedidoVoo.segui_alvo,
    })
  }, [pedidoVoo])
  useEffect(() => {
    controloVento.adotarServidor(sim.ventoSimples)
  }, [sim.ventoSimples])
  useEffect(() => {
    controloBola.adotarServidor(sim.bola)
  }, [sim.bola])

  // Câmara da 3.ª pessoa: com janela nativa a câmara real vem no resumo; sem ela lê-se uma vez.
  useEffect(() => {
    if (sim.camera !== null) camera.receberCamera(sim.camera)
    else if (apiLigada) void carregarCameraEmVigor(sim.cameraPadrao)
  }, [sim.camera, sim.cameraPadrao, apiLigada])

  // ------------------------------------------------------------- ações
  const { reiniciar: pedirReinicio, aplicarBateria, aplicarFpv } = sim

  const reiniciar = useCallback(() => {
    setAReiniciar(true)
    void pedirReinicio()
      .then(() => notificar("reiniciado — o drone volta ao chão e descola", "ok"))
      .catch((erro: unknown) =>
        notificar(
          `não foi possível reiniciar — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
          "erro"
        )
      )
      .finally(() => setAReiniciar(false))
  }, [notificar, pedirReinicio])

  const recarregar = useCallback(() => {
    setARecarregar(true)
    void aplicarBateria("recarregar")
      .then(() => notificar("bateria recarregada", "ok"))
      .catch((erro: unknown) =>
        notificar(
          `não foi possível recarregar — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
          "erro"
        )
      )
      .finally(() => setARecarregar(false))
  }, [aplicarBateria, notificar])

  const ligarCamara = useCallback(() => {
    void aplicarFpv({ ligada: true }).catch((erro: unknown) =>
      notificar(
        `não foi possível ligar a câmara — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
        "erro"
      )
    )
  }, [aplicarFpv, notificar])

  const semRumo = useCallback(
    () =>
      notificar(
        "ainda não há rumo dos sensores para fixar — espera pela primeira leitura",
        "info"
      ),
    [notificar]
  )

  // ------------------------------------------------------------- teclado (sempre ativo)
  const gestoReiniciar = useRef<GestoReiniciar>(null)
  const { alternar: alternarJanela, fecharDaFrente } = janelas
  const { trocar: trocarVista } = vista

  useEffect(() => {
    const modificadores = (evento: KeyboardEvent) => ({
      ctrl: evento.ctrlKey,
      meta: evento.metaKey,
      alt: evento.altKey,
    })

    const aoBaixar = (evento: KeyboardEvent) => {
      const acao = acaoDaTecla(evento.key, modificadores(evento))
      // Num campo de texto escreve-se: o cockpit não intercepta nada.
      if (acao === null || eCampoDeTexto(evento.target as HTMLElement | null)) return
      // Nenhuma tecla do cockpit rola a página, escreve ou aciona a pesquisa do browser.
      evento.preventDefault()
      if (evento.repeat) return // o auto-repeat não é uma tecla nova
      switch (acao.tipo) {
        case "voo":
        case "rodar":
          controloPiloto.premir(acao.tecla)
          break
        case "fixar_rumo":
          if (!controloPiloto.fixarRumo(rumoParaFixar(hud.ultima()))) semRumo()
          break
        case "tiro":
          controloTiro.premir()
          break
        case "bola":
          controloPiloto.alternarBola()
          break
        case "vento":
          controloVento.alternar()
          break
        case "vista":
          trocarVista()
          break
        case "reiniciar":
          gestoReiniciar.current?.iniciar()
          break
        case "janela": {
          const janela = JANELAS[acao.indice]
          if (janela !== undefined) alternarJanela(janela.id)
          break
        }
        case "ajuda":
          alternarJanela("ajuda")
          break
        case "fechar":
          fecharDaFrente()
          break
      }
    }

    const aoSubir = (evento: KeyboardEvent) => {
      // Largar solta SEMPRE (mesmo com modificadores ou num campo): uma tecla nunca fica presa.
      const acao = acaoDaTecla(evento.key)
      if (acao === null) return
      if (acao.tipo === "voo" || acao.tipo === "rodar")
        controloPiloto.largar(acao.tecla)
      else if (acao.tipo === "tiro") controloTiro.largar()
      else if (acao.tipo === "reiniciar") gestoReiniciar.current?.cancelar()
    }

    // Perder o foco (outra janela, outro separador) solta tudo: o `keyup` já não chega cá.
    const soltar = () => {
      controloPiloto.soltarTudo()
      controloTiro.largar()
      gestoReiniciar.current?.cancelar()
    }
    const aoEsconder = () => {
      if (document.hidden) soltar()
    }

    window.addEventListener("keydown", aoBaixar)
    window.addEventListener("keyup", aoSubir)
    window.addEventListener("blur", soltar)
    document.addEventListener("visibilitychange", aoEsconder)
    return () => {
      window.removeEventListener("keydown", aoBaixar)
      window.removeEventListener("keyup", aoSubir)
      window.removeEventListener("blur", soltar)
      document.removeEventListener("visibilitychange", aoEsconder)
    }
  }, [alternarJanela, fecharDaFrente, semRumo, trocarVista])

  // ------------------------------------------------------------- o conteúdo de cada janela
  const conteudoDaJanela = (id: IdJanela) => {
    switch (id) {
      case "voo":
        return (
          <JanelaVoo
            piloto={piloto}
            tiro={tiro}
            aSeguirBola={resumoHud.modo === "bola"}
            aceitaComandos={resumoHud.aceitaComandos}
            onSemRumo={semRumo}
          />
        )
      case "bola":
        return (
          <JanelaBola
            seguir={piloto.segui_alvo}
            seguidor={resumoHud.seguidor}
            bola={bola}
          />
        )
      case "vento":
        return <JanelaVento vento={vento} />
      case "instrumentos":
        return real || planta === null ? (
          <PainelVoo linha={ultima} />
        ) : (
          <p className="text-sm text-muted-foreground" data-testid="instrumentos-sem-estimador">
            Esta planta (o Crazyflie de referência) não tem sensores de bordo
            modelados: não há leituras de sensores para comparar com a verdade.
          </p>
        )
      case "energia":
        return (
          <JanelaEnergia
            temBateria={resumoHud.temBateria || real}
            apiLigada={apiLigada}
            aRecarregar={aRecarregar}
            onRecarregar={recarregar}
            detalheAberto={energiaDetalhe}
            onDetalhe={setEnergiaDetalhe}
            detalhe={
              <div className="grid items-start gap-3 lg:grid-cols-2">
                <PainelBateria
                  linhas={sim.linhas}
                  bateria={ultima?.bateria ?? null}
                  ligado={apiLigada}
                  onComando={aplicarBateria}
                  onAviso={notificar}
                />
                <PainelMotores
                  motores={ultima?.motores ?? null}
                  potencia={ultima?.potencia ?? null}
                  aero={ultima?.aero ?? null}
                  hardware={hardware}
                  ligado={apiLigada}
                />
              </div>
            }
          />
        )
      case "graficos":
        return <Curvas linhas={sim.linhas} zAlvo={ALVO_Z} grande />
      case "sistema":
        return (
          <JanelaSistema
            controlador={sim.controlador}
            multiIa={sim.rpi5?.multiIa ?? null}
            hardware={hardware}
            fpv={sim.fpv}
            simulacao={sim.simulacao}
            fovyPublicado={resumoHud.fovy}
            simAtivo={simAtivo}
            rede={
              rl ? (
                <>
                  <Rede linha={ultima} estadoCorrendo={sim.estado === "a_correr"} />
                  <div className="grid gap-3 xl:grid-cols-2">
                    <TabelaObs
                      linha={ultima}
                      planta={planta}
                      modoAcao={hardware?.modoAcao ?? null}
                    />
                    <PainelAct
                      linha={ultima}
                      resumo={sim.resumo}
                      planta={planta}
                      hardware={hardware}
                    />
                  </div>
                  <PainelRpi5
                    rpi5={sim.rpi5}
                    ligado={apiLigada}
                    dimsRede={
                      ultima === null || ultima.h1.length === 0
                        ? null
                        : `${ultima.obs.length}→${ultima.h1.length}→${ultima.h2.length}→${ultima.act.length}`
                    }
                  />
                </>
              ) : null
            }
          />
        )
      case "ajuda":
        return <JanelaAjuda />
    }
  }

  const emFoco =
    janelas.estado.abertas.length > 0
      ? janelas.estado.abertas[janelas.estado.abertas.length - 1]
      : null

  return (
    <div
      data-testid="cockpit"
      className="fixed inset-0 h-svh w-svw overflow-hidden bg-background font-sans text-foreground"
    >
      <Vista
        vista={vista.vista}
        miniaturaAberta={vista.miniatura}
        visivel={visivel}
        apiLigada={apiLigada || sim.ligacao === "a_ligar"}
        estadoConhecido={sim.resumo !== null}
        fpv={sim.fpv}
        simulacao={sim.simulacao}
        cameraPadrao={sim.cameraPadrao}
        onTrocar={vista.trocar}
        onMiniatura={vista.definirMiniatura}
        onLigarCamara={ligarCamara}
        onImagem={setComImagem}
      />

      <Hud
        vista={vista.vista}
        comImagem={comImagem}
        piloto={piloto}
        tiro={tiro}
        viewport={viewport}
        imagemBordo={imagemBordo}
        atrasoImagemMs={atrasoDaImagem(
          sim.fpv?.latencia?.totalMs,
          sim.fpv?.fpsMedido
        )}
      />

      <Doca
        abertas={janelas.estado.abertas}
        onAlternar={janelas.alternar}
        onReiniciar={reiniciar}
        podeReiniciar={apiLigada && !aReiniciar}
        gestoReiniciar={gestoReiniciar}
      />

      {/* As janelas: a ordem no DOM é FIXA (a da doca) e quem está à frente decide-se pelo z-index —
          reordenar nós a meio de um `pointerdown` cancelava o arrasto que esse clique ia começar. */}
      <div className="pointer-events-none absolute inset-0 z-30">
        {JANELAS.filter((j) => janelas.estado.abertas.includes(j.id)).map((j) => (
          <Janela
            key={j.id}
            id={j.id}
            titulo={j.titulo}
            tecla={j.tecla}
            icone={ICONE_JANELA[j.id]}
            largura={
              j.id === "energia" && energiaDetalhe
                ? LARGURA_ENERGIA_DETALHE
                : j.largura
            }
            alturaPrevista={j.alturaPrevista}
            posicao={
              janelas.estado.posicoes[j.id] ?? posicaoInicial(j.id, viewport)
            }
            viewport={viewport}
            ordem={janelas.estado.abertas.indexOf(j.id)}
            emFoco={emFoco === j.id}
            onFocar={janelas.focar}
            onFechar={janelas.fechar}
            onMover={janelas.mover}
          >
            <ACarregar>{conteudoDaJanela(j.id)}</ACarregar>
          </Janela>
        ))}
      </div>

      <PilhaAvisos
        toasts={toasts}
        conteudo={conteudo}
        fechar={fechar}
        className="!bottom-[4.75rem] !z-[60]"
      />
    </div>
  )
}

export default App
