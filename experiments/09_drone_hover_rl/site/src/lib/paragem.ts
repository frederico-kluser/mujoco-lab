/**
 * ÉPOCA DAS PARAGENS — a garantia de que um PARAR não é desfeito por um apply atrasado.
 *
 * O painel do vento dinâmico tem um live-apply com debounce (`controlos.tsx`, ≈300 ms): editar um campo
 * agenda um `POST /api/vento-dinamico {modo, ativo: true, params}` para daqui a 300 ms. Cancelar esse
 * temporizador só quando o `modoContinuo` muda (o que depende do POLLING, ~350 ms + o ida-e-volta do POST)
 * deixa uma janela em que o clique em PARAR já foi escrito no servidor e o apply agendado ainda sai — e o
 * servidor/runner honram-no: o modo volta a `rajadas` depois de parar.
 *
 * Este módulo é a peça ÚNICA das paragens, com as defesas que fecham a janela:
 *   1. **ÉPOCA**: um contador incrementado de forma SÍNCRONA no clique do PARAR (antes de qualquer
 *      `await`). Quem agenda um apply guarda a época do agendamento e compara-a na hora de disparar: época
 *      diferente = o apply é DESCARTADO, sem sequer chegar à rede. Não depende do polling nem de o React já
 *      ter re-renderizado o painel.
 *   2. **CANCELAMENTO**: os temporizadores do live-apply ficam registados aqui, por isso o PARAR
 *      CANCELA-OS (o callback nunca corre) em vez de só os invalidar à chegada.
 *   3. **BLOQUEIO**: depois de um PARAR, o painel não volta a agendar nenhum live-apply enquanto o estado
 *      do SERVIDOR não voltar ao painel (leitura fresca aplicada). É o que impede que uma edição feita na
 *      janela em que o painel ainda mostra o modo antigo (poll atrasado) ressuscite o modo que já foi
 *      parado no servidor. O bloqueio NÃO depende de um comando contínuo local: é a leitura do servidor —
 *      venha ela de um comando nosso, de outra aba ou de um `POST` cru de outro cliente — que o levanta.
 *   4. **REVALIDAÇÃO (multi-cliente)**: nenhuma dessas três defesas vê uma paragem feita por OUTRO cliente
 *      (um `POST /api/parar` cru, ou o botão de outra aba): a época é estado de módulo por *realm* e o
 *      poll do site chega sempre depois do debounce de 300 ms. Por isso, ao DISPARAR o debounce, o apply
 *      confirma no servidor (uma leitura barata de `/api/state`, registada pelo `useSim` em
 *      `definirLeitorEstadoDinamico`) que o modo que ia religar ainda está ativo. Se o servidor já estiver
 *      em `nenhum`/inativo — ou noutro modo — o apply é SUPRIMIDO e o painel é avisado (`aoSuprimir`): o
 *      ecrã passa a mostrar o estado do servidor em vez de mentir. É esta revalidação, e não o canal
 *      cross-tab, que é a garantia: o canal pode não existir (modo privado do browser) e nunca vê um
 *      `POST` cru.
 *   5. **CANAL CROSS-TAB** (complemento, `BroadcastChannel`): uma paragem feita noutra ABA da mesma origem
 *      chega aqui de imediato — cancela os temporizadores pendentes e força o painel a reler o servidor —
 *      em vez de esperar pelo poll. Um comando que LIGA um modo contínuo também é anunciado, para as
 *      outras abas adotarem o modo sem esperar 350 ms. Ausente o `BroadcastChannel`, tudo continua correto
 *      pela revalidação (só menos imediato).
 *
 * QUEM CHAMA `invalidarEnviosDinamicos`: **todos** os caminhos de paragem — o PARAR VENTO (`use-sim.ts`,
 * que também põe o vento base a 0) e, no `App.tsx`, qualquer comando que ponha o modo dinâmico em
 * `nenhum`/`ativo:false` (PARAR DINÂMICO, o toggle PARADO, a frente a desligar, …). A centralização no
 * funil dos comandos (`enviarVentoDinamico`) é o que garante que nenhum botão de paragem fica de fora.
 *
 * Complementa (não substitui) a fila de POSTs do `use-sim.ts`, que garante que o pedido de PARAR é sempre
 * a ÚLTIMA escrita no ficheiro de controlo: a época/timer matam o que ainda não saiu; a fila ordena o que
 * já saiu.
 */

/** Estado do vento dinâmico tal como o SERVIDOR o publica (`GET /api/state` e `GET /api/sim`). */
export interface EstadoDinamico {
  modo: string
  ativo: boolean
}

/** Evento do canal cross-tab: uma paragem (`paragem`) ou um comando que liga o modo (`comando`). */
export interface EventoVento {
  tipo: "paragem" | "comando"
}

/** Nome do canal `BroadcastChannel` (mesma origem: todas as abas do site). */
const CANAL_VENTO = "mujoco-09-vento-dinamico"

let epoca = 0

/** Temporizadores do live-apply pendentes (o PARAR cancela-os a todos). */
const pendentes = new Set<number>()

/** Houve um PARAR e o painel ainda não voltou a ver o estado do servidor. */
let bloqueado = false

/** Instante (`performance.now()`) do último PARAR local: só leituras EMITIDAS depois dele o levantam. */
let instanteParagem = Number.NEGATIVE_INFINITY

/** Último estado do servidor aplicado no painel (diagnóstico/estado honesto). */
let estadoServidor: EstadoDinamico | null = null

/** Leitor BARATO do estado do servidor (o `useSim` registra-o): é a revalidação do apply agendado. */
let leitor: (() => Promise<EstadoDinamico | null>) | null = null

/** Quem quer saber dos eventos cross-tab (o `App` relê o servidor e avisa o utilizador). */
const ouvintes = new Set<(evento: EventoVento) => void>()

let canal: BroadcastChannel | null = null

/** Canal cross-tab (tolerante: sem `BroadcastChannel` devolve `null` e nada disto é essencial). */
function obterCanal(): BroadcastChannel | null {
  if (canal !== null) return canal
  if (typeof BroadcastChannel !== "function") return null
  try {
    canal = new BroadcastChannel(CANAL_VENTO)
    canal.onmessage = (mensagem: MessageEvent) => {
      const evento = mensagem.data as EventoVento | null
      if (evento === null || typeof evento !== "object") return
      if (evento.tipo === "paragem") {
        // Paragem de OUTRA aba: mata já os applies pendentes desta (o poll chegaria tarde) e avisa quem
        // escuta. Não se reanuncia (senão as abas ficavam a repetir o evento umas às outras).
        invalidar(false)
        avisar(evento)
        return
      }
      if (evento.tipo === "comando") avisar(evento)
    }
    return canal
  } catch {
    canal = null // modo privado/sem suporte: a revalidação continua a garantir o principal
    return null
  }
}

function avisar(evento: EventoVento): void {
  for (const ouvinte of ouvintes) {
    try {
      ouvinte(evento)
    } catch {
      /* um ouvinte que rebenta não pode derrubar os outros nem o tratamento do evento */
    }
  }
}

/** Publica no canal cross-tab (silencioso quando não há canal). */
function publicar(evento: EventoVento): void {
  const alvo = obterCanal()
  if (alvo === null) return
  try {
    alvo.postMessage(evento)
  } catch {
    /* canal fechado a meio: a revalidação do apply cobre o caso */
  }
}

/** Época atual: cresce a cada PARAR. Quem agenda um apply guarda este valor e confere-o ao disparar. */
export function epocaDeParagem(): number {
  return epoca
}

/** Um PARAR bloqueou o live-apply? (o painel não agenda applies enquanto isto for verdade) */
export function enviosDinamicosBloqueados(): boolean {
  return bloqueado
}

/** Último estado do servidor que o painel aplicou (`null` = ainda não houve leitura). */
export function estadoDoServidor(): EstadoDinamico | null {
  return estadoServidor
}

/**
 * O `useSim` registra aqui a leitura BARATA do estado do vento dinâmico (`GET /api/state`).
 *
 * É o que permite ao apply agendado REVALIDAR contra o servidor antes de escrever: sem isso, uma paragem
 * feita por outro cliente (que este *realm* não vê) era desfeita pelo debounce. `null` desliga a
 * revalidação (o apply volta a sair como antes — nunca se deixa o painel sem caminho de envio).
 */
export function definirLeitorEstadoDinamico(
  novo: (() => Promise<EstadoDinamico | null>) | null
): void {
  leitor = novo
}

/**
 * Estado do servidor observado pelo painel (chamado pelo `useSim` a cada leitura FRESCA aplicada).
 *
 * `emitidoEm` é o instante (`performance.now()`) em que o PEDIDO saiu: uma resposta emitida ANTES do
 * clique de paragem pode trazer o estado velho (o servidor ainda não tinha escrito o PARAR) e por isso não
 * conta para levantar o bloqueio — só uma leitura pedida DEPOIS do clique diz o que o servidor ficou a
 * fazer. Levantar o bloqueio aqui é o que impede o painel de ficar preso depois de OUTRO cliente religar o
 * modo: a adoção do modo vindo do poll passa a valer também para o live-apply (antes só um comando
 * contínuo LOCAL o destrancava).
 */
export function observarEstadoServidor(
  din: EstadoDinamico | null,
  emitidoEm = Number.NEGATIVE_INFINITY
): void {
  if (din === null) return
  estadoServidor = din
  if (emitidoEm >= instanteParagem) bloqueado = false
}

/**
 * Agenda o apply do live-apply do painel e devolve o CANCELADOR (o `clearTimeout` do cleanup do efeito).
 *
 * O temporizador fica registado no módulo: `invalidarEnviosDinamicos` cancela-o, logo o callback não corre
 * depois de um PARAR. Se algum apply escapasse (ex.: já em voo), o callback confere na mesma a época e o
 * bloqueio antes de chamar a rede — defesa em profundidade.
 *
 * Com `opcoes.modo`, o apply é REVALIDADO contra o servidor antes de sair (defesa multi-cliente): se o
 * servidor já não tiver esse modo ativo, o comando é suprimido e `opcoes.aoSuprimir` diz ao utilizador que
 * a edição não foi aplicada (nada de um painel a mostrar um valor que o servidor não tem).
 */
export function agendarEnvioDinamico(
  disparar: () => void,
  atraso: number,
  opcoes?: { modo: string; aoSuprimir: (motivo: string) => void }
): () => void {
  const epocaDoAgendamento = epoca
  const id = window.setTimeout(() => {
    pendentes.delete(id)
    if (bloqueado || epoca !== epocaDoAgendamento) return // houve um PARAR: este apply morreu com ele
    if (opcoes === undefined || leitor === null) {
      disparar()
      return
    }
    void (async () => {
      let estado: EstadoDinamico | null
      try {
        estado = await leitor()
      } catch {
        estado = null // o servidor não confirmou: não se escreve às cegas
      }
      // Um PARAR durante a revalidação mata o apply na mesma (a época é conferida outra vez).
      if (epoca !== epocaDoAgendamento) return
      if (estado === null) {
        opcoes.aoSuprimir(
          "não consegui confirmar o estado do vento dinâmico no servidor"
        )
        return
      }
      if (!estado.ativo || estado.modo !== opcoes.modo) {
        opcoes.aoSuprimir(
          `o servidor já não tem ${opcoes.modo} ativo (modo em vigor: ${estado.modo}) — o parâmetro não foi enviado`
        )
        return
      }
      disparar()
    })()
  }, atraso)
  pendentes.add(id)
  return () => {
    pendentes.delete(id)
    window.clearTimeout(id)
  }
}

/**
 * Comando NOVO do utilizador que liga um modo contínuo: volta a armar o live-apply.
 *
 * Não mexe na época — a época só sobe com paragens, e o que estava agendado antes do PARAR já foi
 * cancelado (não pode voltar à vida por o painel ter sido rearmado).
 */
export function rearmarEnviosDinamicos(): void {
  bloqueado = false
}

/** Anuncia às outras abas que um modo contínuo foi ligado (elas releem o servidor sem esperar o poll). */
export function anunciarComandoDinamico(): void {
  publicar({ tipo: "comando" })
}

/**
 * Invalida TODOS os applies dinâmicos agendados/em voo e devolve a época nova.
 *
 * Chamado por TODOS os caminhos de paragem, de forma síncrona (no clique), antes de o pedido sair: a partir
 * daqui nenhum apply agendado antes da paragem é enviado e o painel não agenda nenhum novo até o estado do
 * SERVIDOR voltar ao painel. Anuncia também a paragem às outras abas (ver o canal cross-tab).
 */
export function invalidarEnviosDinamicos(): number {
  return invalidar(true)
}

/** Núcleo do PARAR: época + bloqueio + cancelamento. `anunciar` só é falso quando o evento vem do canal. */
function invalidar(anunciar: boolean): number {
  epoca += 1
  bloqueado = true
  instanteParagem = performance.now()
  for (const id of pendentes) window.clearTimeout(id)
  pendentes.clear()
  if (anunciar) publicar({ tipo: "paragem" })
  return epoca
}

/**
 * Escuta os eventos cross-tab (paragem/comando vinda de OUTRA aba). Devolve a função de cancelamento.
 *
 * O `App` usa isto para reler o servidor (e avisar, quando é uma paragem): é o que faz o painel de uma aba
 * refletir o que outra aba acabou de fazer sem esperar pelo polling.
 */
export function subscreverEventosVento(
  ouvinte: (evento: EventoVento) => void
): () => void {
  obterCanal() // garante o canal montado (e o `onmessage`) já no primeiro render
  ouvintes.add(ouvinte)
  return () => {
    ouvintes.delete(ouvinte)
  }
}
