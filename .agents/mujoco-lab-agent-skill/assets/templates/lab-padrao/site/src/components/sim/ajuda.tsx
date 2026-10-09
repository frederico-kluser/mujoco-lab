/**
 * AJUDA — o «?» que explica CADA elemento visível desta página.
 *
 * O conteúdo vive aqui como ESTRUTURA DE DADOS (`SECOES_AJUDA`), separado do desenho: o template só percorre
 * as secções, portanto acrescentar uma explicação é acrescentar um objecto (sem tocar em JSX). Ao copiar o
 * template para outro robô, é AQUI que os textos se adaptam — o resto do ficheiro não muda.
 *
 * Cascata (motion-plus-ui): passo 2 — `sheet` (`Sheet` + `SheetBackdrop` + `SheetPanel` + `SheetClose`,
 * diálogo nativo com foco preso e arrasto para fechar) e `accordion` (`Accordion` + `AccordionItem` +
 * `AccordionTrigger` + `AccordionChevron` + `AccordionPanel`) para as secções; passo 3 — `Button` do shadcn
 * como gatilho fixo. Passo 4 só na LEGENDA (`definição`/`termo`) dos itens: o catálogo não tem lista de
 * definições, e é só texto com classes semânticas.
 *
 * As secções abrem TODAS por omissão: quem carrega no «?» quer ler, não descobrir onde clicar — e o
 * `AccordionPanel` só monta o painel quando está aberto, logo é isto que põe as explicações no DOM.
 */

import { useState } from "react"
import { HelpCircle } from "lucide-react"

import {
  Accordion,
  AccordionChevron,
  AccordionItem,
  AccordionPanel,
  AccordionTrigger,
} from "@/components/motion-ui/accordion"
import { Sheet, SheetBackdrop, SheetClose, SheetHandle, SheetPanel, useSheet } from "@/components/motion-ui/sheet"
import { Button } from "@/components/ui/button"
import { FOCUS_RING } from "@/components/sim/estilo"

/** Uma entrada da ajuda: o elemento tal como aparece no ecrã + o que ele é. */
export interface ItemAjuda {
  /** Nome do elemento, como está no ecrã. */
  rotulo: string
  /** O que é e para que serve (1–2 frases). */
  texto: string
}

export interface SeccaoAjuda {
  id: string
  titulo: string
  /** Onde está no ecrã (para o olho o encontrar depressa). */
  onde: string
  itens: ItemAjuda[]
}

/** Conteúdo da ajuda, secção a secção (PT-PT, curto). ADAPTAR ao teu robô: só os textos. */
export const SECOES_AJUDA: SeccaoAjuda[] = [
  {
    id: "cabecalho",
    titulo: "Cabeçalho, selos e contadores",
    onde: "topo da página",
    itens: [
      {
        rotulo: "título e subtítulo",
        texto:
          "«Haste com alvo de ângulo · política ao vivo»: junta hinge com atuador de torque no MuJoCo 3.15, observação de 4 canais, MLP 4→64→64→1 e alvo de 60°. Tudo o que se vê vem da telemetria real.",
      },
      {
        rotulo: "selo de estado",
        texto:
          "«a correr» (ponto a pulsar) enquanto o episódio decorre; «episodio_terminado» quando acabou (erro além do envelope de 80°, teto de passos, etc.). O site nunca reinicia sozinho.",
      },
      {
        rotulo: "selo de ligação",
        texto:
          "Estado do polling: «API ligada» é a última leitura com sucesso; passados 2 s sem resposta mostra há quanto tempo. Com o servidor em baixo fica «API em baixo» e aparece a faixa vermelha.",
      },
      {
        rotulo: "episódio · passos",
        texto:
          "Número do episódio e passos de decisão já publicados (a política decide a 50 Hz). O episódio novo zera os passos e o histórico.",
      },
      {
        rotulo: "retorno",
        texto:
          "Retorno acumulado do episódio — a soma das recompensas que a política está a tentar maximizar (chegar ao alvo e ficar dentro da tolerância de 3°).",
      },
      {
        rotulo: "modelo",
        texto:
          "A política em uso, como «pasta/ficheiro.zip», lida do GET /api/state. Nunca se mostra o caminho absoluto: é um rótulo de painel, não um explorador de ficheiros.",
      },
    ],
  },
  {
    id: "curvas",
    titulo: "Curvas ao vivo",
    onde: "coluna principal, 4 gráficos",
    itens: [
      {
        rotulo: "θ(t)",
        texto:
          "Ângulo da haste ao longo do episódio, em graus, com a linha fina no alvo do episódio (deduzido da telemetria: erro = θ − alvo). Abaixo do gráfico: mínimo, máximo e nº de pontos guardados.",
      },
      {
        rotulo: "erro(t)",
        texto:
          "Erro em relação ao alvo (θ − θ_alvo), em graus, com a linha no zero: é a grandeza que a recompensa castiga e a que decide a terminação.",
      },
      {
        rotulo: "θ̇(t)",
        texto:
          "Velocidade angular, em °/s: mostra se a haste está a oscilar (o vento a empurrar e o controlo a repor) ou parada no alvo.",
      },
      {
        rotulo: "vento(t)",
        texto:
          "Norma do vento aplicado em cada passo, em m/s. Com rajadas, frente ou turbulência ligadas é aqui que se vê a dinâmica a mexer o vento.",
      },
      {
        rotulo: "mín · máx · pts",
        texto:
          "Leituras da janela guardada no browser (600 pontos). O histórico é acumulado por ep:passo e reinicia quando muda o episódio.",
      },
    ],
  },
  {
    id: "rede",
    titulo: "Rede da política · ativações",
    onde: "coluna principal, sob as curvas",
    itens: [
      {
        rotulo: "4 → 64 → 64 → 1",
        texto:
          "A rede: 4 entradas (observação), duas camadas escondidas de 64 e 1 saída (ação). As grelhas mostram as ATIVAÇÕES de cada camada neste instante.",
      },
      {
        rotulo: "cor = |a| / máx da camada",
        texto:
          "Cor pela magnitude relativa ao máximo da própria camada: primary = ativação positiva, destructive = negativa (tokens shadcn, sem cores inventadas).",
      },
      {
        rotulo: "sem arestas",
        texto:
          "Não se desenham ligações entre neurónios porque o backend publica ativações, não pesos — desenhar arestas seria inventar dados.",
      },
    ],
  },
  {
    id: "obs",
    titulo: "Observação · 4 canais",
    onde: "coluna principal, canto inferior esquerdo",
    itens: [
      {
        rotulo: "cos θ · sin θ",
        texto:
          "O ângulo da haste em forma contínua (sem saltos no ±180°): é a codificação que a política usa para saber onde está.",
      },
      {
        rotulo: "θ̇/10",
        texto: "Velocidade angular normalizada por 10 rad/s: quão depressa a haste está a rodar.",
      },
      {
        rotulo: "erro/π",
        texto:
          "Erro em relação ao alvo normalizado por π (sempre em [−1, 1]): é o canal que a recompensa transforma em penalidade.",
      },
      {
        rotulo: "colunas obs / cru / barra",
        texto:
          "«obs» é o valor normalizado que a rede vê; «cru» devolve a unidade física (obs × escala fixa do env.py); a barra é |obs| face ao canal mais ativo do passo.",
      },
    ],
  },
  {
    id: "acao",
    titulo: "Ação · 1 canal",
    onde: "coluna principal, canto inferior direito",
    itens: [
      {
        rotulo: "a₀ · Δτ normalizado",
        texto:
          "A ação é um DESVIO em torno do torque de equilíbrio, em [−1, 1] — não o esforço absoluto. O env.py traduz: ctrl = trim + a·15 N·m.",
      },
      {
        rotulo: "τ aplicado (N·m)",
        texto:
          "O torque físico que o atuador recebeu, publicado em ctrl pelo backend (o trim de 60° vale ≈20,2 N·m). Se a telemetria não trouxer ctrl, deriva-se localmente com as constantes do env.py.",
      },
    ],
  },
  {
    id: "vento",
    titulo: "Vento constante (sliders)",
    onde: "painel Controlos, secção «vento»",
    itens: [
      {
        rotulo: "força (0–5 m/s)",
        texto:
          "Velocidade do vento. 0 = ar parado. Escreve-se na física pelo POST /api/vento, sem parar a simulação.",
      },
      {
        rotulo: "azimute (0–360°)",
        texto:
          "Direção horizontal: 0° = +x = E, 90° = +y = N (anti-horário). É a direção PARA ONDE o vento aponta no plano.",
      },
      {
        rotulo: "elevação (−90…90°)",
        texto: "Componente vertical: positivo = vento a subir, negativo = a descer (rajadas verticais).",
      },
      {
        rotulo: "APLICAR VENTO",
        texto:
          "Envia os três valores (POST /api/vento) e escreve o ficheiro de controlo que o runner lê. O botão mostra o estado: pronto → a enviar → aplicado/erro, com aviso no canto.",
      },
      {
        rotulo: "PARAR VENTO",
        texto: "Põe a força a 0 m/s mantendo a direção guardada — o vento para imediatamente (POST /api/vento).",
      },
    ],
  },
  {
    id: "dinamico",
    titulo: "Vento dinâmico (rajadas · turbulência · frente)",
    onde: "painel Controlos, caixa «vento dinâmico»",
    itens: [
      {
        rotulo: "selo ativo/inativo e «modo em vigor»",
        texto:
          "O que o servidor está mesmo a fazer: modo, parâmetros e se está ligado. Vem do vento_dinamico do /api/sim e da última linha da telemetria (vento_modo).",
      },
      {
        rotulo: "PARADO · RAJADAS · DRYDEN",
        texto:
          "Modos contínuos. RAJADAS: com probabilidade p começa uma rajada até u_max que SOMA ao vento base durante «duração» passos. DRYDEN: turbulência que passeia em torno do vento base. PARADO desliga tudo.",
      },
      {
        rotulo: "p · duração · u_max",
        texto:
          "Parâmetros das rajadas (valores por omissão do treino: p = 0,02, duração = 10 passos = 0,2 s, u_max = 3,0 m/s). u_max é o teto do modo e u_max = 0 torna-o inerte.",
      },
      {
        rotulo: "sigma · L · v_min",
        texto:
          "Parâmetros da turbulência Dryden: intensidade (σ), escala de comprimento (L) e o piso de velocidade v_min, que evita congelar a turbulência quando o vento base é nulo.",
      },
      {
        rotulo: "RAJADA AGORA",
        texto:
          "Uma rajada única, imediata, com a duração em passos que estiver no campo e a força/azimute/elevação dos sliders. O botão fica «RAJADA EM CURSO» enquanto ela dura.",
      },
      {
        rotulo: "FRENTE AGORA",
        texto:
          "Degrau de vento imediato: substitui o vento base pelos valores dos sliders (vento que muda de repente a meio do episódio) e vê-se logo na telemetria (vento_vec/vento_vel). Clicar outra vez desliga — o botão fica «FRENTE EM VIGOR» enquanto está ativa.",
      },
      {
        rotulo: "PARAR DINÂMICO",
        texto:
          'Envia {modo: "nenhum", ativo: false}: desliga o modo dinâmico e deixa só o vento base. Nenhum destes botões reinicia o episódio.',
      },
    ],
  },
  {
    id: "rosa",
    titulo: "Rosa dos ventos",
    onde: "painel Controlos, sob os sliders",
    itens: [
      {
        rotulo: "seta sólida = vento em vigor",
        texto:
          "Vetor que está mesmo aplicado na física (vento base + dinâmica), lido de vento_vec na telemetria. O comprimento é a norma (0–5 m/s) e o ângulo é o azimute.",
      },
      {
        rotulo: "seta tracejada = seleção",
        texto:
          "Direção que os sliders mandariam se carregasses em APLICAR VENTO — serve para comparar com o que a física está a fazer.",
      },
      {
        rotulo: "N · E · S · O e graus",
        texto:
          "Bússola com a convenção do simulador: E = 0°, N = 90°, O = 180°, S = 270° (azimute anti-horário a partir de +x). As marcas de 30° dão a escala.",
      },
      {
        rotulo: "anel a pulsar",
        texto:
          "Aparece quando há dinâmica ativa: cheio/a pulsar depressa com rajadas, tracejado com turbulência ou frente. O centro também mostra a componente vertical (elevação).",
      },
    ],
  },
  {
    id: "rpi5",
    titulo: "Raspberry Pi 5 (computador de bordo)",
    onde: "coluna principal, sob a rede da política",
    itens: [
      {
        rotulo: "imagem e fonte",
        texto:
          "A placa em que a política correria a bordo em TODOS os projetos do laboratório — é uma ILUSTRAÇÃO de referência (Raspberry Pi Model B+, não um Pi 5: Lucasbosch, Wikimedia Commons, CC BY-SA 3.0). O selo «fonte» diz de onde vêm os números: «real» (medidos no Pi 5), «proxy x86 calibrado» (estimados a partir de um PC x86, como o deploy.py faz por omissão) ou «sem benchmark» — neste caso não se inventa nenhum tempo.",
      },
      {
        rotulo: "semáforo OK / ATENÇÃO / ERRO",
        texto:
          "Saúde do tempo real derivada do p99: OK até 70 % do orçamento, ATENÇÃO acima disso (pouca margem) e ERRO quando o p99 passa os 100 %. Sem números não há semáforo.",
      },
      {
        rotulo: "p50 / p99 vs budget",
        texto:
          "Latência típica (p50) e de cauda (p99) da inferência comparadas com o orçamento por decisão (20 ms a 50 Hz). Acima de 100 % a barra fica vermelha: a política não caberia no tempo real.",
      },
      {
        rotulo: "CPU equivalente",
        texto:
          "Percentagem do CPU do alvo que a inferência ocupa, com a latência estimada e as decisões por segundo a que isso corresponde.",
      },
      {
        rotulo: "modelo · fator int8 · pior caso · núcleos multi-IA",
        texto:
          "Tamanho da política em KB, ganho (ou perda) da quantização int8 face ao fp32 medido nesta máquina, o pior caso e quantos núcleos seriam precisos para correr várias políticas em paralelo — tudo calculado pelo backend a partir do relatório do deploy.py.",
      },
      {
        rotulo: "estado do hardware",
        texto:
          "Temperatura e `vcgencmd get_throttled` quando o backend os publicar; sem Pi 5 ligado diz «sem hardware» (o site nunca inventa leituras do sistema).",
      },
      {
        rotulo: "nota do jitter do SO",
        texto:
          "A inferência desta MLP é muito mais barata que o orçamento (dezenas de microssegundos); quem costuma estourá-lo é o jitter do sistema operativo — 9,4 ms de pior caso num kernel normal contra 20 ms de período, e ≤225 µs com um kernel PREEMPT_RT. É por isso que o painel mostra a cauda (p99/pior caso) e não só a média.",
      },
      {
        rotulo: "specs do alvo",
        texto:
          "SoC (BCM2712), CPU (4× Cortex-A76 @ 2,4 GHz, 512 kB de L2 por núcleo + 2 MB de L3), RAM (LPDDR4X-4267), orçamento por decisão e núcleos do alvo, como o backend os anuncia. Tudo isto atualiza com o polling (2,9 Hz), sem recarregar a página.",
      },
    ],
  },
  {
    id: "episodio",
    titulo: "REINICIAR · LOOP · estados e avisos",
    onde: "painel Controlos, fundo",
    itens: [
      {
        rotulo: "REINICIAR (manter 1 s)",
        texto:
          "Único controlo que reinicia: mantém o botão carregado ~1 s (o preenchimento confirma, para não reiniciar por engano) e envia POST /api/reiniciar. A haste volta ao alvo com um jitter de ±5° e velocidade nula.",
      },
      {
        rotulo: "LOOP",
        texto:
          "Desligado por omissão. Ligado, é o BACKEND que reinicia ao terminar o episódio; o site limita-se a fazer o POST /api/loop. Desligado, o episódio fica terminado até carregares em REINICIAR.",
      },
      {
        rotulo: "faixa de estado do episódio",
        texto:
          "«episódio a correr · sem auto-restart» ou «LOOP ligado»; quando termina, fica vermelha a pedir REINICIAR e o cartão ganha um anel de aviso.",
      },
      {
        rotulo: "avisos (toasts)",
        texto:
          "No fundo do ecrã: confirmações e erros das ações (vento aplicado, rajada enviada, LOOP, reinício) e os 400 do servidor com o motivo. Erros ficam 8 s e sucesso 5 s.",
      },
      {
        rotulo: "esqueleto e «sem passos»",
        texto:
          "Antes da primeira leitura aparecem blocos cinzentos (skeleton); se o servidor responder mas ainda não houver passos, avisa-se que as curvas e a rede ficam vazias até o episódio arrancar.",
      },
      {
        rotulo: "como os dados chegam",
        texto:
          "GET /api/sim a cada 350 ms (~2,9 Hz) traz o estado, o vento e as linhas novas; os controlos escrevem por POST. Não há websockets nem recarregamento da página.",
      },
    ],
  },
]

/** Ids de todas as secções — abrem de início, para o texto estar todo à vista (e no DOM). */
export const SECOES_AJUDA_ABERTAS: string[] = SECOES_AJUDA.map((s) => s.id)

interface AjudaProps {
  /** Id do título (ligado ao `aria-labelledby` do painel). */
  idTitulo?: string
}

/**
 * Botão «?» fixo no canto inferior direito. É um filho do `Sheet` que não é backdrop nem painel (page
 * part), logo pode usar o `useSheet()` do catálogo para abrir a folha — sem gatilho escondido nem CSS a
 * forçar posição dentro do `SheetTrigger`.
 */
function GatilhoAjuda() {
  const { setOpen } = useSheet()
  return (
    <Button
      type="button"
      size="icon-lg"
      aria-label="ajuda: explicar cada elemento desta página"
      aria-haspopup="dialog"
      data-testid="botao-ajuda"
      className={`fixed right-4 bottom-4 z-40 rounded-full shadow-lg ${FOCUS_RING}`}
      onClick={() => setOpen(true)}
    >
      <HelpCircle className="size-5" aria-hidden="true" />
    </Button>
  )
}

/**
 * A ajuda abre já aberta com `?ajuda=1` no URL (link partilhável e prova de DOM nos testes, como o `?api=`
 * que aponta o `dist/` a outro porto). Sem parâmetro, começa fechada.
 */
export function ajudaAbertaPorLink(): boolean {
  const valor = new URLSearchParams(window.location.search).get("ajuda")
  return valor === "1" || valor === "true"
}

/** Botão «?» + folha de ajuda com todas as secções (abertas por omissão). */
export function Ajuda({ idTitulo = "ajuda-titulo" }: AjudaProps) {
  const [aberta] = useState(ajudaAbertaPorLink)
  return (
    <Sheet defaultOpen={aberta}>
      <GatilhoAjuda />

      <SheetBackdrop label="fechar a ajuda" />
      <SheetPanel labelledBy={idTitulo} className="max-h-[78svh] overflow-y-auto overscroll-contain lg:max-w-2xl">
        <SheetHandle />
        <div className="mb-2 flex items-start justify-between gap-3">
          <div className="flex flex-col gap-0.5">
            <h2 id={idTitulo} className="text-sm font-semibold" data-testid="titulo-ajuda">
              O que é cada elemento desta página
            </h2>
            <p className="text-[0.7rem] text-muted-foreground">
              haste com alvo de ângulo (MuJoCo + política RL) · clica numa secção para abrir ou fechar ·
              arrasta a folha para baixo para fechar
            </p>
          </div>
          <SheetClose label="fechar a ajuda" />
        </div>

        <Accordion multiple defaultValue={SECOES_AJUDA_ABERTAS} className="flex flex-col">
          {SECOES_AJUDA.map((seccao) => (
            <AccordionItem key={seccao.id} value={seccao.id} className="border-b border-border/60 last:border-b-0">
              <AccordionTrigger headingLevel={3} inset indicator={<AccordionChevron />}>
                <span className="flex min-w-0 flex-col gap-0.5 py-1 text-left">
                  <span className="text-xs font-medium" data-testid={`ajuda-seccao-${seccao.id}`}>
                    {seccao.titulo}
                  </span>
                  <span className="text-[0.65rem] text-muted-foreground">{seccao.onde}</span>
                </span>
              </AccordionTrigger>
              <AccordionPanel>
                <dl className="flex flex-col gap-2 pt-1 pb-3" data-testid={`ajuda-conteudo-${seccao.id}`}>
                  {seccao.itens.map((item) => (
                    <div key={item.rotulo} className="flex flex-col gap-0.5">
                      <dt className="font-mono text-[0.7rem] text-foreground">{item.rotulo}</dt>
                      <dd className="text-[0.7rem] leading-snug text-muted-foreground">{item.texto}</dd>
                    </div>
                  ))}
                </dl>
              </AccordionPanel>
            </AccordionItem>
          ))}
        </Accordion>
      </SheetPanel>
    </Sheet>
  )
}
