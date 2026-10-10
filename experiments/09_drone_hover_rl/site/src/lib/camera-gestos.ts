/**
 * WIDGET «CÂMARA» (vista 3.ª pessoa) — mapeamento do PAD (esfera ↔ ângulos) e MÁQUINA DE GESTOS
 * (comandos ao vivo durante o arrasto + commit final, sem perder gestos). Sem DOM nem React: o
 * `camera.tsx` é só a camada de apresentação sobre esta máquina, e os testes
 * (`testes/camera-gestos.mts`) exercitam ESTE código de produção.
 *
 * PAD (especificação do dono, 2026-10-09): um CÍRCULO com o glifo do DRONE ao centro e UMA ESFERA
 * arrastável — horizontal = azimute, vertical = elevação — mais um SLIDER de distância (0,1–10 m)
 * e o botão REPOR VISTA (envia o `camera_padrao`). Sem presets: o pad substitui-os.
 *
 * MAPEAMENTO esfera ↔ ângulos (coordenadas normalizadas `u` horizontal [direita +] e `w` vertical
 * [cima +], ambas em [−1,1]):
 *  · `u = azimute/180 − 1` — u=−1 ↔ azimute 0°, u=0 ↔ 180°, u→+1 ↔ 360° ≡ 0°: passar nas bordas
 *    laterais faz WRAP 360↔0 (a esfera sai por um lado e entra pelo outro);
 *  · `w = −elevacao/90` — a esfera em cima (w=+1) = elevação −90° = CÂMARA POR CIMA do alvo, a
 *    esfera em baixo (w=−1) = +90° = câmara por baixo. Arrastar para CIMA põe a câmara MAIS ALTA
 *    porque a elevação fica mais NEGATIVA: `pos = alvo − d·f`, `f = [cos e·cos a, cos e·sin a, sin e]`
 *    ⇒ `pos_z = alvo_z − d·sin(elev)` — quanto mais negativa a elevação, maior o `pos_z`. Os limites
 *    ±90 TRAVAM a esfera nas bordas superior/inferior (a elevação não passa de ±90).
 *  · desenho da esfera: `(u,w)` com o raio limitado a 1 (a esfera fica sempre dentro do círculo).
 *
 * MÁQUINA DE GESTOS — os 2 defeitos medidos do bloco anterior (sliders) entram aqui como requisito:
 *  · **DEF-1 (gestos perdidos)**: a telemetria (~350 ms) substituía os valores do gesto entre o
 *    `pointerup` e o envio agendado (150 ms) e o POST levava valores velhos. Agora os valores
 *    enviados são SEMPRE os do gesto: cada edição escreve um SNAPSHOT do corpo por enviar (fixado
 *    no fim do gesto e refrescado em cada envio a partir do estado do gesto) e a telemetria NUNCA
 *    escreve nos valores mostrados durante o arrasto nem enquanto houver envio pendente (snapshot
 *    por disparar ou envio por confirmar). O `terminarGesto` faz o COMMIT FINAL imediato.
 *  · **DEF-2 (estados honestos)**: `camera`/`camera_atual` a passar a `null` (janela fechada) mostra
 *    SEMPRE «—» e desativa o controlo — nunca se retém o valor antigo. O snapshot pendente
 *    sobrevive ao `null` (o envio leva sempre os valores finais do gesto).
 *
 * Resposta ao vivo: comandos ENQUANTO se arrasta (throttle com disparo agendado a
 * `ATRASO_ENVIO_CAMERA_MS` ≈ 150 ms, coalescência — os eventos entre disparos caem num só comando
 * com o valor que estiver a ser mostrado) + commit final ao largar. 1 comando por mudança final de
 * valor (um snapshot idêntico ao último corpo enviado não gera comando novo; o REPOR VISTA envia
 * sempre).
 */

import {
  cameraReflete,
  normalizarAzimute,
  type CameraEstado,
  type CorpoCamera,
} from "./sim.ts"

/** Debounce/throttle do envio (ms): os eventos de um gesto coalescem num comando por disparo. */
export const ATRASO_ENVIO_CAMERA_MS = 150
/**
 * Quanto tempo se espera pela confirmação da câmara real depois de enviar (ms): passado isto,
 * adota-se o que a câmara real diz (rato da janela, outro cliente) — nada de valores órfãos.
 */
export const CONFIRMACAO_CAMERA_MS = 1500

export type FaseEnvio = "repouso" | "a_enviar" | "enviado" | "confirmado" | "erro"

/** Campos comandáveis do widget (o corpo v2 é um subconjunto de `{azimute, elevacao, distancia}`). */
export type CampoCamera = "azimute" | "elevacao" | "distancia"

// ------------------------------------------------------------------------------ pad ↔ ângulos

/** Posição NORMALIZADA da esfera no pad: `u` horizontal (direita +), `w` vertical (cima +). */
export interface Esfera {
  u: number
  w: number
}

/** `clamp` a um intervalo (a elevação trava em ±90 e a esfera nas bordas do pad). */
export function limitar(valor: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, valor))
}

/**
 * ÂNGULOS → posição da esfera (estados honestos: a posição é SEMPRE função dos ângulos atuais —
 * inclusive quando a câmara é mexida pelo rato da janela fora de arrasto).
 */
export function esferaDeAngulos(azimute: number, elevacao: number): Esfera {
  return {
    u: normalizarAzimute(azimute) / 180 - 1,
    w: -limitar(elevacao, -90, 90) / 90,
  }
}

/**
 * Posição da esfera → ÂNGULOS (inverso do anterior): o azimute dá WRAP 360↔0 nas bordas laterais
 * (`u=+1` ≡ `u=−1` ≡ azimute 0°) e a elevação TRAVA em ±90 nas bordas superior/inferior.
 */
export function angulosDeEsfera(
  u: number,
  w: number
): { azimute: number; elevacao: number } {
  return {
    azimute: normalizarAzimute((u + 1) * 180),
    elevacao: limitar(-w * 90, -90, 90),
  }
}

/**
 * Posição de DESENHO da esfera dentro do círculo: `(u,w)` com o raio limitado a 1. As posições dos
 * cantos do pad (|u| e |w| grandes) projetam-se na borda do círculo; nos eixos o mapeamento é exato.
 */
export function esferaDesenho(u: number, w: number): Esfera {
  const raio = Math.hypot(u, w)
  return raio > 1 ? { u: u / raio, w: w / raio } : { u, w }
}

/**
 * ARRASTO relativo da esfera (Δu, Δw em unidades do pad) sobre um estado de ângulos — os deltas
 * acumulam-se a partir do INÍCIO do gesto (sem deriva de passos intermédios). Arrastar para a
 * direita AUMENTA o azimute (a câmara orbita de +x para +y, anti-horário visto de cima); arrastar
 * para CIMA DIMINUI a elevação (mais negativa ⇒ câmara mais alta, ver o cabeçalho do módulo).
 */
export function aplicarArrasto(
  estado: { azimute: number; elevacao: number },
  du: number,
  dw: number
): { azimute: number; elevacao: number } {
  return {
    azimute: normalizarAzimute(estado.azimute + du * 180),
    elevacao: limitar(estado.elevacao - dw * 90, -90, 90),
  }
}

// ------------------------------------------------------------------------------ máquina de gestos

function copia(v: CameraEstado): CameraEstado {
  return {
    azimute: v.azimute,
    elevacao: v.elevacao,
    distancia: v.distancia,
    alvo: v.alvo === null ? null : [v.alvo[0], v.alvo[1], v.alvo[2]],
  }
}

function mesmoCorpo(a: CorpoCamera | null, b: CorpoCamera | null): boolean {
  if (a === null || b === null) return false
  return (
    a.azimute === b.azimute &&
    a.elevacao === b.elevacao &&
    a.distancia === b.distancia
  )
}

export interface MaquinaCameraOpcoes {
  /** `POST /api/camera` (o `use-sim` faz o POST + releitura); rejeição = aviso ao dono. */
  enviar: (corpo: CorpoCamera) => Promise<void>
  /** O painel mostra estes valores (`null` = «—», estado honesto). */
  aoMostrar: (valores: CameraEstado | null) => void
  aoFase: (fase: FaseEnvio, motivo: string | null) => void
  aoAvisar: (texto: string) => void
  /** Há ligação viva à API? (sem ligação não se dispara envio — como sempre). */
  ligado: () => boolean
  atrasoMs?: number
  confirmacaoMs?: number
  /** Relógio (ms) — injetável para os testes. */
  relogio?: () => number
  /** Agendador do throttle — injetável para os testes; devolve um handle para `cancelar`. */
  agendar?: (tarefa: () => void, ms: number) => unknown
  cancelar?: (handle: unknown) => void
}

/**
 * O estado do widget «Câmara» durante os gestos (pad + slider + REPOR VISTA). Ver o cabeçalho do
 * módulo para o contrato DEF-1/DEF-2; `camera.tsx` é só apresentação.
 */
export class MaquinaCamera {
  private readonly opcoes: MaquinaCameraOpcoes
  private readonly atrasoMs: number
  private readonly confirmacaoMs: number
  private readonly relogio: () => number
  private readonly agendar: (tarefa: () => void, ms: number) => unknown
  private readonly cancelar: (handle: unknown) => void

  /** Valores mostrados no widget (`null` = «—», DEF-2). */
  private _valores: CameraEstado | null = null
  private _arrastando = false
  /**
   * SNAPSHOT do corpo por enviar, com os valores do GESTO (DEF-1): nasce em cada edição (a partir
   * do estado do gesto), é atualizado durante o arrasto e fixado no commit final (`terminarGesto`).
   * É SEMPRE este corpo que o envio leva — nunca o estado mostrado no instante do disparo, que um
   * poll da telemetria podia já ter trocado. Sobrevive a um `null` da telemetria (o envio leva os
   * valores finais do gesto mesmo que o painel já mostre «—»).
   */
  private _snapshot: CorpoCamera | null = null
  /** Comando enviado e ainda por confirmar pela câmara real (o corpo enviado, para comparar). */
  private _confirmacao: { corpo: CorpoCamera; desde: number } | null = null
  /** Último corpo DISPACHADO (coalescência: um snapshot igual não gera comando novo). */
  private _ultimoCorpo: CorpoCamera | null = null
  private _temporizador: unknown = null
  private _faseAtual: FaseEnvio = "repouso"
  private _motivo: string | null = null

  constructor(opcoes: MaquinaCameraOpcoes) {
    this.opcoes = opcoes
    this.atrasoMs = opcoes.atrasoMs ?? ATRASO_ENVIO_CAMERA_MS
    this.confirmacaoMs = opcoes.confirmacaoMs ?? CONFIRMACAO_CAMERA_MS
    this.relogio = opcoes.relogio ?? (() => Date.now())
    this.agendar =
      opcoes.agendar ??
      ((tarefa, ms) =>
        setTimeout(tarefa, ms) as unknown as ReturnType<typeof setTimeout>)
    this.cancelar =
      opcoes.cancelar ??
      ((h) => clearTimeout(h as ReturnType<typeof setTimeout>))
  }

  get valores(): CameraEstado | null {
    return this._valores
  }
  get semDados(): boolean {
    return this._valores === null
  }
  get emArrasto(): boolean {
    return this._arrastando
  }
  get fase(): FaseEnvio {
    return this._faseAtual
  }
  get motivo(): string | null {
    return this._motivo
  }

  /** Arrasto do pad em curso (a telemetria NÃO manda: estado otimista do gesto). */
  comecarArrasto(): void {
    this._arrastando = true
  }

  /**
   * Fim do gesto (pointerup/pointercancel): COMMIT FINAL imediato — o snapshot leva já os valores
   * finais do gesto (é a janela que o DEF-1 explorava: entre o largar e um envio agendado).
   */
  terminarGesto(): void {
    if (!this._arrastando) return
    this._arrastando = false
    if (this._snapshot !== null) this._enviarAgora()
  }

  /** Passo do arrasto do pad: ângulos novos (já convertidos do gesto pelo `aplicarArrasto`). */
  editarAngulos(azimute: number, elevacao: number): void {
    const base = this._valores
    if (base === null) return
    const novos: CameraEstado = {
      azimute: normalizarAzimute(azimute),
      elevacao: limitar(elevacao, -90, 90),
      distancia: base.distancia,
      alvo: base.alvo === null ? null : [base.alvo[0], base.alvo[1], base.alvo[2]],
    }
    if (novos.azimute === base.azimute && novos.elevacao === base.elevacao) return
    this._mostrar(novos)
    this._registar({ azimute: novos.azimute, elevacao: novos.elevacao })
  }

  /** Passo do slider de distância (0,1–10 m na UI; a faixa do contrato é ]0,20]). */
  editarDistancia(distancia: number): void {
    const base = this._valores
    if (base === null) return
    const novos = { ...copia(base), distancia: limitar(distancia, 0.1, 10) }
    if (novos.distancia === base.distancia) return
    this._mostrar(novos)
    this._registar({ distancia: novos.distancia })
  }

  /**
   * REPOR VISTA = enviar o `camera_padrao` (contrato v2: `{azimute, elevacao, distancia}`) — um
   * comando explícito, SEMPRE enviado (não passa pela coalescência).
   */
  reporVista(cameraPadrao: CameraEstado | null): void {
    if (cameraPadrao === null) return
    const corpo: CorpoCamera = {
      azimute: cameraPadrao.azimute,
      elevacao: cameraPadrao.elevacao,
      distancia: cameraPadrao.distancia,
    }
    this._mostrar(copia(cameraPadrao))
    this._snapshot = corpo
    this._enviarAgora(true)
  }

  /**
   * ADOÇÃO da câmara real (uma amostra da telemetria). DEF-1: enquanto houver arrasto ou envio
   * pendente (snapshot por disparar / envio por confirmar) a amostra NÃO escreve nos valores.
   * DEF-2: `null` = sem dados ⇒ «—» SEMPRE fora de arrasto (e o controlo desativa-se) — nunca se
   * retém o valor antigo.
   */
  receberCamera(cam: CameraEstado | null): void {
    if (cam === null) {
      if (this._arrastando) return
      this._confirmacao = null
      this._faseExcetoErro("repouso")
      this._mostrar(null)
      return
    }
    if (this._arrastando) return
    if (this._snapshot !== null) return
    const pendente = this._confirmacao
    if (pendente !== null) {
      const confirmado = cameraReflete(cam, pendente.corpo)
      const expirou = this.relogio() - pendente.desde > this.confirmacaoMs
      if (!confirmado && !expirou) return
      this._confirmacao = null
      if (confirmado) {
        this._definirFase("confirmado", null)
      } else {
        // expirou sem confirmação: quem manda é a câmara real (rato da janela, outro cliente…)
        this._faseExcetoErro("repouso")
      }
    }
    this._mostrar(copia(cam))
  }

  /** Cancela um envio agendado (fim do componente). */
  cancelarEnvio(): void {
    if (this._temporizador !== null) {
      this.cancelar(this._temporizador)
      this._temporizador = null
    }
    this._snapshot = null
  }

  // ------------------------------------------------------------------------------ internos

  private _mostrar(valores: CameraEstado | null): void {
    this._valores = valores
    this.opcoes.aoMostrar(valores)
  }

  /**
   * Regista os campos do gesto no SNAPSHOT (DEF-1) e agenda o throttle: um disparo a
   * `atrasoMs` coalesce os eventos intermédios (1 comando por mudança final de valor).
   */
  private _registar(corpo: CorpoCamera): void {
    this._snapshot = { ...this._snapshot, ...corpo }
    if (this._temporizador !== null) return
    this._temporizador = this.agendar(() => {
      this._temporizador = null
      this._enviarAgora()
    }, this.atrasoMs)
  }

  /** DISPACHA o comando do snapshot (com os valores do GESTO — nunca os da telemetria). */
  private _enviarAgora(forcar = false): void {
    const corpo = this._snapshot
    this._snapshot = null
    if (this._temporizador !== null) {
      this.cancelar(this._temporizador)
      this._temporizador = null
    }
    if (corpo === null) return
    // Coalescência: um snapshot idêntico ao último corpo enviado não gera comando novo.
    if (!forcar && mesmoCorpo(corpo, this._ultimoCorpo)) return
    if (!this.opcoes.ligado()) {
      this._definirFase("erro", "sem ligação à API da simulação")
      return
    }
    this._ultimoCorpo = corpo
    this._confirmacao = { corpo, desde: this.relogio() }
    this._definirFase("a_enviar", null)
    this.opcoes.enviar(corpo).then(
      () => {
        // A confirmação final é a câmara REAL (efeito da telemetria); isto só marca «no caminho».
        this._faseSe("a_enviar", "enviado")
      },
      (erro: unknown) => {
        if (this._confirmacao?.corpo === corpo) this._confirmacao = null
        // envio falhado não conta para a coalescência (um gesto igual tem de voltar a mandar)
        if (this._ultimoCorpo === corpo) this._ultimoCorpo = null
        const texto = erro instanceof Error ? erro.message : "falha desconhecida"
        this._definirFase("erro", texto)
        this.opcoes.aoAvisar(`POST /api/camera recusado — ${texto}`)
      }
    )
  }

  private _definirFase(nova: FaseEnvio, motivo: string | null = null): void {
    this._faseAtual = nova
    this._motivo = motivo
    this.opcoes.aoFase(nova, motivo)
  }
  private _faseSe(condicao: FaseEnvio, nova: FaseEnvio): void {
    if (this._faseAtual === condicao) this._definirFase(nova)
  }
  private _faseExcetoErro(nova: FaseEnvio): void {
    if (this._faseAtual !== "erro") this._definirFase(nova)
  }
}
