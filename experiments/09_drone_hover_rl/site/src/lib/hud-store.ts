/**
 * HUD AO VIVO — a última amostra de `GET /api/hud` (Server-Sent Events, 50 Hz) guardada FORA do React.
 *
 * Porquê fora do React: 50 amostras por segundo a passar por `setState` re-renderizavam o cockpit
 * inteiro 50 vezes por segundo. Aqui a amostra fica num objeto de módulo e quem desenha regista um
 * DESENHADOR, chamado dentro de UM `requestAnimationFrame` partilhado — os instrumentos escrevem
 * `transform`/`textContent` por refs e o React não sabe de nada. Para o React só sai o RESUMO lento
 * (`ResumoHud`: ligação, A VOAR/CAIU, seguidor, alerta de bateria), via `useSyncExternalStore`, e só
 * quando muda (segundos, não milissegundos).
 *
 * Ligação:
 *  · o `EventSource` religa sozinho (o servidor manda `retry: 1000`); se o browser o der por fechado
 *    (resposta de erro), reabre-se à mão;
 *  · FALLBACK: sempre que a última amostra tem mais de `LIMIAR_SONDAGEM_MS`, sonda-se
 *    `GET /api/hud.json` (5 Hz) — o HUD continua a mexer com o SSE em baixo (proxy que não deixa
 *    passar streams, por exemplo). A amostra traz a idade que o SERVIDOR lhe dá, logo um runner parado
 *    não passa por vivo;
 *  · a FRESCURA manda: amostra com mais de 1 s ⇒ SEM LIGAÇÃO, venha de onde vier;
 *  · página escondida (`document.hidden`) ⇒ fecha o SSE, pára a sondagem e o `requestAnimationFrame`;
 *    ao voltar reabre tudo (e mostra A LIGAR até chegar a primeira amostra nova).
 */

import { buscarHudJson, urlApi } from "./api.ts"
import {
  RESUMO_HUD_INICIAL,
  lerEventoHud,
  ligacaoHud,
  resumirHud,
  resumoIgual,
  type AmostraHud,
  type LigacaoHud,
  type ResumoHud,
} from "./cockpit.ts"

/** Os NÚMEROS reescrevem-se no máximo a este ritmo (10 Hz): a 50 Hz o último algarismo é ilegível. */
const PERIODO_TEXTO_MS = 100
/** Sem amostra nova há mais do que isto ⇒ o fallback sonda o `hud.json`. */
const LIMIAR_SONDAGEM_MS = 400
const PERIODO_SONDAGEM_MS = 200
/** Espera antes de reabrir um `EventSource` que o browser fechou de vez. */
const RELIGAR_SSE_MS = 2000
/** Amostras guardadas para desenhar «com atraso» (32 × 20 ms = 640 ms — cobre a latência da câmara). */
const MEMORIA_AMOSTRAS = 32

/** O que um desenhador recebe em cada quadro em que há alguma coisa nova para pôr no ecrã. */
export interface QuadroHud {
  /** A última amostra (mesmo velha: os instrumentos ficam no último valor, a pílula diz SEM LIGAÇÃO). */
  hud: AmostraHud | null
  ligacao: LigacaoHud
  /** Altura de reescrever os números (≤ 10 Hz); os `transform` desenham-se em todos os quadros. */
  texto: boolean
}

export type Desenhador = (quadro: QuadroHud) => void

/** De onde chegou a última amostra (janela Sistema: «estado dos streams»). */
export type FonteHud = "sse" | "sondagem" | null

export interface MedidasHud {
  /** Amostras por segundo, medidas no último segundo (0 sem amostras). */
  hz: number
  fonte: FonteHud
  /** Idade da última amostra (ms) ou `null` sem nenhuma. */
  idadeMs: number | null
}

class HudStore {
  private amostra: AmostraHud | null = null
  /** Instante (`performance.now()`) em que a amostra era fresca; `null` = sem amostra desde o (re)arranque. */
  private recebidaEm: number | null = null
  private contador = 0
  private desenhado = -1
  private arranque = 0
  private ligacaoDesenhada: LigacaoHud | null = null
  private ultimoTexto = 0
  private textoPorEscrever = false

  private fonte: EventSource | null = null
  private religar = 0
  private sondagem = 0
  private aSondar = false
  private quadro = 0
  private ativo = false
  private utilizadores = 0

  private readonly desenhadores = new Set<Desenhador>()
  private readonly ouvintes = new Set<() => void>()
  private resumo: ResumoHud = RESUMO_HUD_INICIAL

  private origem: FonteHud = null
  /** Anel das últimas amostras com o instante de chegada (ver `deHa`). */
  private readonly anel: ({ hud: AmostraHud; em: number } | null)[] =
    new Array<{ hud: AmostraHud; em: number } | null>(MEMORIA_AMOSTRAS).fill(null)
  private cabeca = 0
  private amostrasNaJanela = 0
  private inicioJanela = 0
  private hz = 0

  // ------------------------------------------------------------------ API para o React

  /** `useSyncExternalStore`: o resumo LENTO (identidade estável enquanto nada muda). */
  readonly subscrever = (ouvinte: () => void): (() => void) => {
    this.ouvintes.add(ouvinte)
    const largar = this.reter()
    return () => {
      this.ouvintes.delete(ouvinte)
      largar()
    }
  }

  readonly obterResumo = (): ResumoHud => this.resumo

  /**
   * Regista um desenhador no `requestAnimationFrame` partilhado. É chamado JÁ com o que houver (uma
   * janela acabada de abrir não espera pela amostra seguinte) e depois em cada quadro com novidade.
   */
  desenhar(desenhador: Desenhador): () => void {
    this.desenhadores.add(desenhador)
    const largar = this.reter()
    desenhador({
      hud: this.amostra,
      ligacao: this.ligacaoAgora(performance.now()),
      texto: true,
    })
    return () => {
      this.desenhadores.delete(desenhador)
      largar()
    }
  }

  /** A última amostra, para handlers de eventos (tecla X = fixar o rumo ATUAL). Não é reativo. */
  ultima(): AmostraHud | null {
    return this.amostra
  }

  /**
   * A amostra que era a atual há `ms` milissegundos. Os símbolos que assentam NA IMAGEM (horizonte,
   * retículo da bola) desenham-se com a atitude do instante em que o quadro foi captado: a câmara de
   * bordo entrega cada quadro ~116 ms depois (latência do módulo), e com os sensores «de agora» sobre
   * uma imagem «de há bocado» o horizonte descolava do horizonte sempre que o drone inclina.
   * Sem amostra tão antiga devolve a mais antiga que houver; com `ms` ≤ 0, a última.
   */
  deHa(ms: number): AmostraHud | null {
    if (!(ms > 0)) return this.amostra
    const limite = performance.now() - ms
    let maisAntiga: AmostraHud | null = null
    for (let i = 1; i <= MEMORIA_AMOSTRAS; i += 1) {
      const entrada =
        this.anel[(this.cabeca - i + 2 * MEMORIA_AMOSTRAS) % MEMORIA_AMOSTRAS]
      if (entrada === null) break
      if (entrada.em <= limite) return entrada.hud
      maisAntiga = entrada.hud
    }
    return maisAntiga ?? this.amostra
  }

  medidas(): MedidasHud {
    const agora = performance.now()
    return {
      hz: agora - this.inicioJanela > 2000 ? 0 : this.hz,
      fonte: this.origem,
      idadeMs: this.recebidaEm === null ? null : agora - this.recebidaEm,
    }
  }

  // ------------------------------------------------------------------ ciclo de vida

  private reter(): () => void {
    this.utilizadores += 1
    if (this.utilizadores === 1) {
      document.addEventListener("visibilitychange", this.aoMudarVisibilidade)
      if (!document.hidden) this.arrancar()
    }
    let largado = false
    return () => {
      if (largado) return
      largado = true
      this.utilizadores -= 1
      if (this.utilizadores === 0) {
        document.removeEventListener(
          "visibilitychange",
          this.aoMudarVisibilidade
        )
        this.parar()
      }
    }
  }

  private readonly aoMudarVisibilidade = (): void => {
    if (document.hidden) this.parar()
    else if (this.utilizadores > 0) this.arrancar()
  }

  private arrancar(): void {
    if (this.ativo) return
    this.ativo = true
    const agora = performance.now()
    this.arranque = agora
    // A amostra que ficou de antes já não prova ligação nenhuma: A LIGAR até chegar uma nova.
    this.recebidaEm = null
    this.anel.fill(null)
    this.inicioJanela = agora
    this.amostrasNaJanela = 0
    this.abrirSse()
    this.sondagem = window.setInterval(this.sondar, PERIODO_SONDAGEM_MS)
    this.quadro = requestAnimationFrame(this.aoQuadro)
  }

  private parar(): void {
    if (!this.ativo) return
    this.ativo = false
    this.fecharSse()
    window.clearTimeout(this.religar)
    window.clearInterval(this.sondagem)
    cancelAnimationFrame(this.quadro)
  }

  // ------------------------------------------------------------------ SSE + fallback

  private abrirSse(): void {
    if (this.fonte !== null || typeof EventSource === "undefined") return
    const fonte = new EventSource(urlApi("/api/hud"))
    this.fonte = fonte
    fonte.onmessage = (evento: MessageEvent<string>) => {
      const hud = lerEventoHud(evento.data)
      if (hud !== null) this.receber(hud, performance.now(), "sse")
    }
    fonte.onerror = () => {
      // CONNECTING = o browser está a religar sozinho; CLOSED = desistiu (resposta de erro): reabre-se.
      if (fonte.readyState !== EventSource.CLOSED) return
      this.fecharSse()
      window.clearTimeout(this.religar)
      this.religar = window.setTimeout(() => {
        if (this.ativo) this.abrirSse()
      }, RELIGAR_SSE_MS)
    }
  }

  private fecharSse(): void {
    if (this.fonte === null) return
    this.fonte.onmessage = null
    this.fonte.onerror = null
    this.fonte.close()
    this.fonte = null
  }

  private readonly sondar = (): void => {
    if (this.aSondar) return
    const agora = performance.now()
    if (this.recebidaEm !== null && agora - this.recebidaEm < LIMIAR_SONDAGEM_MS)
      return
    this.aSondar = true
    buscarHudJson()
      .then(({ hud, idadeS }) => {
        if (hud === null || !this.ativo) return
        // A idade é a do SERVIDOR: um runner parado devolve a mesma amostra cada vez mais velha.
        const fresca = performance.now() - (idadeS ?? 0) * 1000
        if (this.recebidaEm !== null && fresca <= this.recebidaEm) return
        this.receber(hud, fresca, "sondagem")
      })
      .catch(() => undefined)
      .finally(() => {
        this.aSondar = false
      })
  }

  private receber(hud: AmostraHud, em: number, origem: FonteHud): void {
    this.amostra = hud
    this.recebidaEm = em
    this.origem = origem
    this.anel[this.cabeca] = { hud, em }
    this.cabeca = (this.cabeca + 1) % MEMORIA_AMOSTRAS
    this.contador += 1
    this.amostrasNaJanela += 1
    const agora = performance.now()
    if (agora - this.inicioJanela >= 1000) {
      this.hz = (this.amostrasNaJanela * 1000) / (agora - this.inicioJanela)
      this.amostrasNaJanela = 0
      this.inicioJanela = agora
    }
  }

  // ------------------------------------------------------------------ desenho

  private ligacaoAgora(agora: number): LigacaoHud {
    return ligacaoHud({
      idadeMs: this.recebidaEm === null ? null : agora - this.recebidaEm,
      desdeArranqueMs: agora - this.arranque,
    })
  }

  private readonly aoQuadro = (agora: number): void => {
    if (!this.ativo) return
    this.quadro = requestAnimationFrame(this.aoQuadro)
    const ligacao = this.ligacaoAgora(agora)
    const nova = this.contador !== this.desenhado
    const mudouLigacao = ligacao !== this.ligacaoDesenhada
    const horaDoTexto = agora - this.ultimoTexto >= PERIODO_TEXTO_MS
    // Sem amostra nova só se desenha para fechar contas: a ligação mudou, ou o último quadro ficou com
    // os números por escrever (a amostra final de uma paragem tem de chegar ao ecrã).
    if (!nova && !mudouLigacao && !(this.textoPorEscrever && horaDoTexto)) return
    const texto = horaDoTexto || mudouLigacao
    if (texto) this.ultimoTexto = agora
    this.textoPorEscrever = !texto
    this.desenhado = this.contador
    this.ligacaoDesenhada = ligacao
    const quadro: QuadroHud = { hud: this.amostra, ligacao, texto }
    for (const desenhador of this.desenhadores) desenhador(quadro)
    const resumo = resumirHud(this.amostra, ligacao)
    if (!resumoIgual(resumo, this.resumo)) {
      this.resumo = resumo
      for (const ouvinte of this.ouvintes) ouvinte()
    }
  }
}

/** O HUD do cockpit: uma ligação, um `requestAnimationFrame`, quantos desenhadores forem precisos. */
export const hud = new HudStore()
