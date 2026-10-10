/**
 * SECÇÕES selecionáveis do painel + barra de estado crítico persistente.
 *
 * Pedido do dono: «eu não quero ter de ver tudo ao mesmo tempo, eu escolho o que ver, para melhorar a
 * monitoria enquanto o drone opera». Daí o seletor de secções (Operação · Rede · Vento · Bordo · Tudo)
 * no topo do conteúdo, com a escolha guardada no `localStorage` e atalhos de teclado 1–5.
 *
 * Cascata (motion-plus-ui): `motion-ui.mjs search "tabs"` → **`smooth-tabs`** (pílula deslizante com
 * `layoutId` + navegação por setas com foco nômade) para o seletor — instalado com
 * `motion-ui.mjs add smooth-tabs`. Os PAINÉIS não usam o `SmoothTabsPanels` (crossfade que monta/desmonta
 * os widgets) porque a monitoria exige que os updates continuem vivos e que o estado dos sliders não se
 * perca na troca: cada bloco esconde-se com o atributo `hidden` (`BlocoSecao`), o que a aceitação prevê
 * («ausentes do DOM ou hidden») e mantém os widgets a atualizar com a secção escondida.
 *
 * NUNCA se esconde o crítico: `BarraEstado` (episódio terminado · API em baixo) e os controlos
 * REINICIAR/LOOP ficam visíveis em QUALQUER secção (barra fixa do topo, ver `App.tsx`).
 */

import { useCallback, useEffect, useState, type ReactNode } from "react"
import { motion } from "motion/react"

import {
  SmoothTabs,
  SmoothTabsList,
  SmoothTabsTab,
} from "@/components/motion-ui/smooth-tabs"
import { useMotionUITransition } from "@/components/motion-ui/ui-theme"
import { fmt, type EstadoEpisodio, type MotivoFim } from "@/lib/sim"
import type { Ligacao } from "@/hooks/use-sim"

/** Identificador estável de cada secção (também é o valor guardado no `localStorage`). */
export type IdSecao = "operacao" | "rede" | "vento" | "bordo" | "tudo"

export interface MetaSecao {
  id: IdSecao
  /** Rótulo da aba (PT-PT, como o resto do painel). */
  rotulo: string
  /** Atalho de teclado (1–5), documentado na ajuda e visível na aba. */
  tecla: string
  /** Uma linha sobre o que a secção serve (vai para a ajuda "?"). */
  paraQueServe: string
}

/** As 5 secções, pela ordem das abas (e das teclas 1–5). */
export const SECOES: MetaSecao[] = [
  {
    id: "operacao",
    rotulo: "Operação",
    tecla: "1",
    paraQueServe:
      "vigiar o voo e enquadrar a cena: cabeçalho (estado, modelo), valores atuais (altura, distância ao alvo, erro de rumo, vento), o Painel de voo (inclinação, rumo, altura, posição estimada vs real, giroscópio, acelerómetro) e o resumo da bateria (drone real), o bloco Câmara (vistas de cima e de lado, zoom e vistas rápidas da janela 3D) e as 4 curvas",
  },
  {
    id: "rede",
    rotulo: "Rede",
    tecla: "2",
    paraQueServe:
      "ver a política a decidir: a rede com as ativações ao vivo (cf2 16→64→64→4; drone real 21→128→128→4), as entradas da rede com nomes simples e unidades do dia a dia, e a ação de 4 canais",
  },
  {
    id: "vento",
    rotulo: "Vento",
    tecla: "3",
    paraQueServe:
      "comandar o vento: sliders do vento constante, rosa dos ventos e vento dinâmico (rajadas, aleatórias, Dryden, frente)",
  },
  {
    id: "bordo",
    rotulo: "Bordo",
    tecla: "4",
    paraQueServe:
      "acompanhar o computador de bordo: painel do Raspberry Pi 5 (latências, semáforo, specs) e, só na planta real, os blocos Bateria, Motores e potência e Hardware (peças reais)",
  },
  {
    id: "tudo",
    rotulo: "Tudo",
    tecla: "5",
    paraQueServe:
      "layout completo: todas as secções de uma vez, como o painel original",
  },
]

/** Chave do `localStorage` onde a secção ativa fica guardada entre sessões. */
export const CHAVE_SECCAO = "09_drone_hover_rl:seccao"

/** Seletores de um slider (Base UI: thumb `role="slider"`/`aria-valuenow`; raiz `data-slot="slider"`). */
const SELETOR_SLIDER =
  '[role="slider"], [data-slider], [data-slot="slider"], [aria-valuenow]'

/**
 * O alvo é (ou está dentro de) um slider? Serve para os atalhos 1–5 não saltarem de secção. Exceção: os
 * controlos marcados com `data-atalhos-livres` (as vistas da Câmara — são sliders para leitores de ecrã mas
 * não usam dígitos), onde as teclas 1–5 continuam a mudar de secção depois de um arrasto.
 */
function emSlider(alvo: EventTarget | null): boolean {
  if (!(alvo instanceof Element)) return false
  const slider = alvo.closest(SELETOR_SLIDER)
  return slider !== null && !slider.hasAttribute("data-atalhos-livres")
}

function lerSecaoGuardada(): IdSecao {
  try {
    const bruta = window.localStorage.getItem(CHAVE_SECCAO)
    const encontrada = SECOES.find((s) => s.id === bruta)
    if (encontrada !== undefined) return encontrada.id
  } catch {
    /* storage bloqueado (modo privado): segue-se a secção por omissão */
  }
  return "operacao"
}

export interface UseSecaoResultado {
  seccao: IdSecao
  escolher: (id: IdSecao) => void
}

/**
 * Estado da secção ativa: lê/grava no `localStorage` e responde aos atalhos 1–5.
 *
 * Prevenção de erro: os atalhos NÃO atuam enquanto se escreve num campo (input/textarea/select ou
 * conteúdo editável) nem com alvo/foco/rato sobre um SLIDER (Base UI: thumb `role="slider"`/
 * `aria-valuenow`, raiz `data-slot="slider"`) — as teclas 1–5 têm de continuar a escrever números e a
 * não saltar de secção a meio de um arrasto de slider.
 */
export function useSecao(): UseSecaoResultado {
  const [seccao, setSecao] = useState<IdSecao>(lerSecaoGuardada)

  useEffect(() => {
    try {
      window.localStorage.setItem(CHAVE_SECCAO, seccao)
    } catch {
      /* sem storage persistente: a escolha vive só na sessão */
    }
  }, [seccao])

  useEffect(() => {
    /** O rato está por cima de um slider? (os sliders Base UI nem sempre recebem foco). */
    let sobreSlider = false
    const aoApontar = (evento: Event) => {
      sobreSlider = emSlider(evento.target)
    }
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.ctrlKey || evento.metaKey || evento.altKey || evento.repeat)
        return
      const alvo = evento.target
      if (alvo instanceof HTMLElement) {
        const etiqueta = alvo.tagName.toLowerCase()
        if (
          etiqueta === "input" ||
          etiqueta === "textarea" ||
          etiqueta === "select" ||
          alvo.isContentEditable
        )
          return
      }
      // slider: no alvo, no foco real (pode não ser o alvo) ou sob o rato — nunca saltar de secção
      if (emSlider(alvo) || emSlider(document.activeElement) || sobreSlider)
        return
      const indice = "12345".indexOf(evento.key)
      if (indice === -1) return
      evento.preventDefault()
      setSecao(SECOES[indice].id)
    }
    window.addEventListener("pointerover", aoApontar)
    window.addEventListener("pointerdown", aoApontar, true)
    window.addEventListener("keydown", aoTeclar)
    return () => {
      window.removeEventListener("pointerover", aoApontar)
      window.removeEventListener("pointerdown", aoApontar, true)
      window.removeEventListener("keydown", aoTeclar)
    }
  }, [])

  const escolher = useCallback((id: IdSecao) => setSecao(id), [])
  return { seccao, escolher }
}

interface SeletorSecoesProps {
  seccao: IdSecao
  escolher: (id: IdSecao) => void
}

/** Abas do seletor (`smooth-tabs`: pílula deslizante, setas + Enter no teclado, atalhos 1–5 à parte). */
export function SeletorSecoes({ seccao, escolher }: SeletorSecoesProps) {
  return (
    <SmoothTabs
      value={seccao}
      onValueChange={(valor) => escolher(valor as IdSecao)}
    >
      <SmoothTabsList
        ariaLabel="secções do painel (atalhos 1–5)"
        className="gap-0.5 border-border/60 bg-card/80"
      >
        {SECOES.map((s) => (
          <SmoothTabsTab
            key={s.id}
            value={s.id}
            className="flex-none px-2.5 py-1.5 text-xs sm:px-3.5 sm:py-2 sm:text-sm"
          >
            <span className="flex items-center gap-1.5">
              {s.rotulo}
              <kbd
                aria-hidden="true"
                className="hidden rounded border border-border/70 bg-muted/60 px-1 font-mono text-[0.6rem] text-muted-foreground sm:inline"
              >
                {s.tecla}
              </kbd>
            </span>
          </SmoothTabsTab>
        ))}
      </SmoothTabsList>
    </SmoothTabs>
  )
}

interface BlocoSecaoProps {
  /** A que secção pertence o bloco (vai para `data-seccao`, usado pelas provas de DOM). */
  id: IdSecao
  /** `false` esconde o bloco com o atributo `hidden` — sem desmontar, para os updates continuarem. */
  visivel: boolean
  children: ReactNode
}

/**
 * Contentor de um bloco de secção. Escondido com `hidden` (nunca desmontado): os widgets em movimento
 * continuam a atualizar com a secção escondida e voltam a mostrar-se com os valores já frescos.
 */
export function BlocoSecao({ id, visivel, children }: BlocoSecaoProps) {
  return (
    <section
      data-seccao={id}
      hidden={visivel ? undefined : true}
      className="flex flex-col gap-4"
    >
      {children}
    </section>
  )
}

interface BarraEstadoProps {
  estado: EstadoEpisodio
  ep: number
  loop: boolean
  ligacao: Ligacao
  erro: string | null
  /** Porque fechou o episódio (`fim` da telemetria) — a queda diz-se; o fim por tempo é normal. */
  fim?: MotivoFim | null
  /**
   * Indicador extra no fim da faixa (planta real: SoC % + alerta da bateria — `IndicadorBateria`).
   * Sem ele (cf2) a faixa fica exatamente como sempre foi.
   */
  indicador?: ReactNode
}

/**
 * Faixa de estado SEMPRE visível (qualquer secção): neutra quando tudo corre bem, vermelha e com
 * `role="alert"` quando há crítico — e o crítico é só o que EXIGE ação: **API em baixo**.
 * **Episódio terminado com `loop:false`** (modo «sem reinício») é uma linha neutra: o episódio fechou
 * mas a física CONTINUA no estado em que ficou (não congela), portanto não há nada a exigir — o
 * REINICIAR é opcional e só serve para começar outro episódio. Com o backend CONTÍNUO o episódio a
 * terminar também é uma transição normal (o backend arranca já o seguinte).
 */
export function BarraEstado({
  estado,
  ep,
  loop,
  ligacao,
  erro,
  indicador,
  fim = null,
}: BarraEstadoProps) {
  const ui = useMotionUITransition("ui")
  const terminado = estado === "episodio_terminado"
  const semLigacao = ligacao === "sem_ligacao"
  /** Terminado E sem reinício automático: o episódio fechou e a física continua — o REINICIAR é opcional. */
  const semReinicio = terminado && !loop
  const critico = semLigacao
  // Com a API em baixo o estado do episódio é VELHO: o alerta fresco (ligação) tem prioridade.
  const testid = semLigacao
    ? "aviso-ligacao"
    : semReinicio
      ? "aviso-terminado"
      : terminado
        ? "aviso-transicao"
        : "aviso-a-correr"
  const texto = semLigacao
    ? `sem resposta do servidor da simulação — a tentar de novo a cada 0,35 s${erro ? ` · ${erro}` : ""}`
    : semReinicio
      ? fim === "queda"
        ? `episódio ${fmt(ep, 0)}: o drone caiu ou capotou · sem reinício: a física continua no estado em que ficou (REINICIAR = voltar a descolar)`
        : `episódio ${fmt(ep, 0)} concluído · sem reinício: o drone continua a voar com a política (REINICIAR = episódio novo)`
      : terminado
        ? `episódio ${fmt(ep, 0)} terminado · modo contínuo: o backend arranca já o seguinte`
        : ligacao === "a_ligar"
          ? "à espera da API…"
          : loop
            ? "episódio a correr · modo contínuo (o backend reinicia ao terminar)"
            : "episódio a correr · sem reinício (a física continua depois do fim)"

  const textoCurto = semLigacao
    ? "sem resposta do servidor — a tentar de novo"
    : terminado
      ? fim === "queda"
        ? `ep ${fmt(ep, 0)}: caiu · REINICIAR para voltar a voar`
        : `ep ${fmt(ep, 0)} concluído · ${loop ? "o seguinte arranca já" : "continua a voar"}`
      : ligacao === "a_ligar"
        ? "à espera da API…"
        : `ep ${fmt(ep, 0)} a correr · ${loop ? "contínuo" : "sem reinício"}`

  return (
    <motion.div
      layout
      transition={{ ...ui }}
      data-testid="aviso-critico"
      data-critico={critico ? "sim" : "nao"}
      role={critico ? "alert" : undefined}
      aria-live={critico ? "assertive" : "polite"}
      className={`flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg px-3 py-1.5 text-xs ${
        critico
          ? "bg-destructive/10 font-medium text-destructive"
          : "bg-muted/50 text-muted-foreground"
      }`}
    >
      <span
        aria-hidden="true"
        className={`size-2 shrink-0 rounded-full ${critico ? "bg-destructive" : "bg-primary"}`}
      />
      <span data-testid={testid}>
        {/* no telemóvel a barra fixa tem de ser curta: a frase longa fica para ecrãs ≥ sm */}
        <span className="hidden sm:inline">{texto}</span>
        <span className="sm:hidden">{textoCurto}</span>
      </span>
      <span
        className="ml-auto hidden font-mono text-[0.6rem] normal-case opacity-70 xl:inline"
        data-testid="estado-loop"
        title="estado técnico do runner (para depuração)"
      >
        loop={loop ? "true" : "false"} · estado={estado}
        {fim ? ` · fim=${fim}` : ""}
      </span>
      {indicador}
    </motion.div>
  )
}
