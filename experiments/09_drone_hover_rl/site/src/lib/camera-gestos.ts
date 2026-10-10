/**
 * WIDGET «CÂMARA» (vista 3.ª pessoa, v3 de 2026-10-10) — a GEOMETRIA das duas vistas do bloco, as VISTAS
 * RÁPIDAS e a MÁQUINA DE GESTOS (comandos ao vivo durante o arrasto + commit final, sem perder gestos).
 * Sem DOM nem React: o `camera.tsx` é só a camada de apresentação e os testes (`testes/camera-gestos.mts`)
 * exercitam ESTE código de produção.
 *
 * Porquê v3: o pad v2 (círculo com uma esfera, horizontal = azimute e vertical = elevação, linear) pedia
 * para ler a legenda — a esfera não ficava onde a câmara está (azimute 90° punha-a em cima de um braço).
 * Agora há duas vistas GEOMÉTRICAS, como num programa 3D:
 *
 *  · VISTA DE CIMA — o chão visto de cima, com a FRENTE do arranque (+x) para CIMA e a ESQUERDA (+y) para
 *    a esquerda (os eixos do drone e do estimador). O ícone da câmara está ONDE a câmara está à volta do
 *    drone; arrastar (ou clicar) noutro sítio põe-na lá — é o azimute. Com `pos = alvo − d·f(az, el)` a
 *    câmara fica na direção −(cos a, sin a) do drone ⇒ no ecrã (sx para a direita, sy para baixo):
 *    `sx = sin a`, `sy = cos a` (azimute 0° = câmara ATRÁS de um drone de rumo 0, a olhar para +x).
 *  · VISTA DE LADO — o plano vertical que contém o drone e a câmara: o ícone sobe/desce num arco à volta
 *    do drone; o ângulo acima do horizonte é `h = −elevação` (convenção MuJoCo: elevação NEGATIVA = câmara
 *    por cima). Faixa da UI: h ∈ [−30°, 89°] (por baixo do chão não se vê nada; −90 exato é singular).
 *  · DISTÂNCIA em escala LOGARÍTMICA (o detalhe perto do drone ganha trilho) com limites por planta: um
 *    drone de 650 mm não cabe a 0,1 m (a câmara ficava dentro das hélices).
 *  · VISTAS RÁPIDAS relativas ao RUMO do drone (atrás, frente, esquerda, direita, de cima, à altura) e
 *    PASSOS finos (setas: ±15° de órbita, ±10° de altura; ± de zoom ×1,25).
 *
 * MÁQUINA DE GESTOS — os 2 defeitos medidos do bloco v1 (sliders) continuam a ser requisito:
 *  · **DEF-1 (gestos perdidos)**: a telemetria (~350 ms) substituía os valores do gesto entre o
 *    `pointerup` e o envio agendado (150 ms) e o POST levava valores velhos. Os valores enviados são
 *    SEMPRE os do gesto: cada edição escreve um SNAPSHOT do corpo por enviar (fixado no fim do gesto e
 *    refrescado em cada envio a partir do estado do gesto) e a telemetria NUNCA escreve nos valores
 *    mostrados durante o arrasto nem enquanto houver envio pendente. O `terminarGesto` faz o COMMIT FINAL.
 *  · **DEF-2 (estados honestos)**: `camera`/`camera_atual` a passar a `null` (janela fechada) mostra
 *    SEMPRE «—» e desativa o controlo — nunca se retém o valor antigo.
 *
 * Resposta ao vivo: throttle com disparo agendado a `ATRASO_ENVIO_CAMERA_MS` ≈ 150 ms (coalescência — os
 * eventos entre disparos caem num só comando com o valor mostrado) + commit final ao largar; 1 comando por
 * mudança final de valor. As vistas rápidas e o REPOR VISTA enviam SEMPRE (comando explícito).
 *
 * Cada comando leva os TRÊS valores (azimute, elevação, distância) do estado mostrado — que fora de um gesto
 * é a câmara REAL. Medido em 2026-10-10: um comando só com ângulos era completado no servidor com a
 * distância do Crazyflie (0,27 m) no 1.º comando da sessão, e a câmara saltava para dentro do drone real; e
 * um zoom feito com o rato na janela era desfeito pelo comando seguinte do site. Com o corpo completo nem
 * uma coisa nem outra acontece (o contrato continua a aceitar subconjuntos).
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

/** `clamp` a um intervalo. */
export function limitar(valor: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, valor))
}

const RAD = Math.PI / 180

/** Ângulo em graus para ]−180, 180]. */
function envolver(graus: number): number {
  const r = normalizarAzimute(graus + 180) - 180
  return r === -180 ? 180 : r
}

// ------------------------------------------------------------------------------ vista de cima

/**
 * Onde DESENHAR a câmara na vista de cima (vetor unitário no ecrã: `sx` para a direita, `sy` para baixo),
 * com a frente (+x) para cima e a esquerda (+y) para a esquerda. A câmara fica em −(cos a, sin a) do
 * drone (`pos = alvo − d·f`); mundo (wx, wy) → ecrã (−wy, −wx) ⇒ `(sin a, cos a)`.
 */
export function pontoTopoDeAzimute(azimute: number): { sx: number; sy: number } {
  const a = normalizarAzimute(azimute) * RAD
  return { sx: Math.sin(a), sy: Math.cos(a) }
}

/**
 * Azimute de um ponto da vista de cima (relativo ao drone, em px — qualquer escala): é o inverso exato de
 * `pontoTopoDeAzimute`. `null` muito perto do centro (a direção não está definida).
 */
export function azimuteDePontoTopo(sx: number, sy: number, minimo = 1e-6): number | null {
  if (Math.hypot(sx, sy) < minimo) return null
  return normalizarAzimute(Math.atan2(sx, sy) / RAD)
}

/**
 * Rotação (graus, sentido do SVG = horário) do glifo do drone desenhado de nariz para CIMA, para o nariz
 * apontar para o rumo `rumoGraus` na vista de cima: nariz no mundo (cos ψ, sin ψ) → ecrã (−sin ψ, −cos ψ)
 * ⇒ rodar `−ψ`.
 */
export function rotacaoGlifoTopo(rumoGraus: number): number {
  return -rumoGraus
}

// ------------------------------------------------------------------------------ vista de lado

/** Faixa do ângulo acima do horizonte na UI (graus): de 30° por baixo a quase a pique (89°). */
export const ALTURA_ANGULAR_UI = [-30, 89] as const

/** Ângulo da câmara ACIMA do horizonte (graus) a partir da elevação MuJoCo (negativa = por cima). */
export function alturaDeElevacao(elevacao: number): number {
  return -elevacao
}

/** Elevação MuJoCo a partir do ângulo acima do horizonte (inverso de `alturaDeElevacao`), na faixa da UI. */
export function elevacaoDeAltura(altura: number): number {
  return -limitar(altura, ALTURA_ANGULAR_UI[0], ALTURA_ANGULAR_UI[1])
}

/**
 * Onde DESENHAR a câmara na vista de lado (unitário; `sx` para a direita, `sy` para baixo), com a câmara do
 * lado ESQUERDO do drone a olhar para a direita: `(−cos h, −sin h)`.
 */
export function pontoLadoDeElevacao(elevacao: number): { sx: number; sy: number } {
  const h = alturaDeElevacao(elevacao) * RAD
  return { sx: -Math.cos(h), sy: -Math.sin(h) }
}

/**
 * Elevação a partir de um ponto da vista de lado (relativo ao drone, px): o ângulo acima do horizonte do
 * ponto visto do lado esquerdo, limitado à faixa da UI — passar para o outro lado do drone trava no topo
 * (ou no fundo). `null` muito perto do centro.
 */
export function elevacaoDePontoLado(sx: number, sy: number, minimo = 1e-6): number | null {
  if (Math.hypot(sx, sy) < minimo) return null
  const h = Math.atan2(-sy, -sx) / RAD // ]−180, 180]: 0 = à esquerda, 90 = por cima
  const travado = h > 90 ? ALTURA_ANGULAR_UI[1] : h < -90 ? ALTURA_ANGULAR_UI[0] : h
  return elevacaoDeAltura(travado)
}

// ------------------------------------------------------------------------------ distância (log)

/** Limites de distância da UI por planta (m): o drone real tem 650 mm de frame e hélices de 15″. */
export function limitesDistancia(planta: "real" | "cf2" | null): readonly [number, number] {
  return planta === "real" ? [0.6, 15] : [0.1, 5]
}

/** Fração do trilho (0–1, LOGARÍTMICA) → distância (m). */
export function distanciaDeFracao(fracao: number, limites: readonly [number, number]): number {
  const [a, b] = limites
  return a * Math.pow(b / a, limitar(fracao, 0, 1))
}

/** Distância (m) → fração do trilho (0–1, logarítmica), travada aos limites. */
export function fracaoDeDistancia(distancia: number, limites: readonly [number, number]): number {
  const [a, b] = limites
  if (!(distancia > 0)) return 0
  return limitar(Math.log(distancia / a) / Math.log(b / a), 0, 1)
}

/** Fator de zoom de um passo (botões −/+ e teclas): ×1,25 por passo. */
export const PASSO_ZOOM = 1.25

/** Distância depois de `passos` de zoom (+ = aproximar), travada aos limites. */
export function aplicarZoom(
  distancia: number,
  passos: number,
  limites: readonly [number, number]
): number {
  return limitar(distancia / Math.pow(PASSO_ZOOM, passos), limites[0], limites[1])
}

// ------------------------------------------------------------------------------ passos e vistas rápidas

/** Passos finos: órbita ±15°, altura ±10°. */
export const PASSO_ORBITA = 15
export const PASSO_ALTURA = 10

/** Ângulos depois de um passo de órbita (+ = a câmara roda no sentido anti-horário visto de cima). */
export function orbitar(
  azimute: number,
  elevacao: number,
  passosOrbita: number,
  passosAltura: number
): { azimute: number; elevacao: number } {
  return {
    azimute: normalizarAzimute(azimute + passosOrbita * PASSO_ORBITA),
    elevacao: elevacaoDeAltura(alturaDeElevacao(elevacao) + passosAltura * PASSO_ALTURA),
  }
}

export type VistaRapida = "atras" | "frente" | "esquerda" | "direita" | "cima" | "altura"

/** As vistas rápidas, pela ordem dos botões (rótulo curto + o que faz). */
export const VISTAS_RAPIDAS: readonly { id: VistaRapida; rotulo: string; dica: string }[] = [
  { id: "atras", rotulo: "Atrás", dica: "atrás do drone, a olhar para onde o nariz aponta (perseguição)" },
  { id: "frente", rotulo: "Frente", dica: "à frente do drone, a olhar para o nariz" },
  { id: "esquerda", rotulo: "Esquerda", dica: "do lado esquerdo do drone" },
  { id: "direita", rotulo: "Direita", dica: "do lado direito do drone" },
  { id: "cima", rotulo: "De cima", dica: "a pique, com o nariz para cima na imagem" },
  { id: "altura", rotulo: "À altura", dica: "3/4 à frente, à altura do drone (vista de cinema)" },
]

/**
 * Ângulos de uma vista rápida para um drone de rumo `rumoGraus` (absoluto, mundo). A câmara olha na
 * direção do azimute e fica do lado OPOSTO: «atrás» = azimute igual ao rumo; «direita» = olha para a
 * esquerda do drone (rumo + 90°) ⇒ está do lado direito. A distância não muda (o zoom é do dono).
 */
export function anguloVistaRapida(
  vista: VistaRapida,
  rumoGraus: number
): { azimute: number; elevacao: number } {
  const ang = (deltaAzimute: number, elevacao: number) => ({
    azimute: normalizarAzimute(rumoGraus + deltaAzimute),
    elevacao,
  })
  switch (vista) {
    case "atras":
      return ang(0, -20)
    case "frente":
      return ang(180, -15)
    case "esquerda":
      return ang(-90, -15)
    case "direita":
      return ang(90, -15)
    case "cima":
      return ang(0, -89)
    case "altura":
      return ang(150, -3)
  }
}

/**
 * Onde está a câmara em relação ao drone, em português simples: «atrás, à direita · 45° por cima».
 * `rel` = azimute − rumo: 0 = atrás, ±180 = à frente, +90 = à direita (olha para a esquerda do drone).
 */
export function descreverCamera(
  azimute: number,
  elevacao: number,
  rumoGraus: number
): { lado: string; altura: string } {
  const rel = envolver(azimute - rumoGraus)
  const a = Math.abs(rel)
  const lado =
    a <= 22.5
      ? "atrás"
      : a > 157.5
        ? "à frente"
        : a <= 67.5
          ? `atrás, ${rel > 0 ? "à direita" : "à esquerda"}`
          : a <= 112.5
            ? rel > 0
              ? "à direita"
              : "à esquerda"
            : `à frente, ${rel > 0 ? "à direita" : "à esquerda"}`
  const h = alturaDeElevacao(elevacao)
  const g = `${Math.round(Math.abs(h))}°`
  const altura =
    h >= 75
      ? `quase a pique (${g} por cima)`
      : h >= 10
        ? `${g} por cima`
        : h > -10
          ? "à altura do drone"
          : `${g} por baixo`
  return { lado, altura }
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

/** O corpo COMPLETO do comando a partir de um estado mostrado (os 3 valores; nunca o `alvo`). */
function corpoCompleto(v: CameraEstado): CorpoCamera {
  return { azimute: v.azimute, elevacao: v.elevacao, distancia: v.distancia }
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
  /** Faixa da distância na UI (m); por omissão 0,1–10 (o widget passa a da planta: `limitesDistancia`). */
  limitesDistancia?: () => readonly [number, number]
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
    this.opcoes = { ...opcoes }
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

  /**
   * Troca as ligações ao exterior (envio, aviso, «há ligação?», limites do zoom) — o componente chama isto
   * num efeito sempre que as props mudam; o estado do gesto (snapshot, confirmação) não se perde.
   */
  religar(
    ligacoes: Partial<Pick<MaquinaCameraOpcoes, "enviar" | "aoAvisar" | "ligado" | "limitesDistancia">>
  ): void {
    Object.assign(this.opcoes, ligacoes)
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

  /** Passo de um gesto nas vistas (ou de um passo fino): ângulos novos, já convertidos pela geometria. */
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
    this._registar(corpoCompleto(novos))
  }

  /** Passo do slider/roda/botões de distância (faixa da UI da planta; a do contrato é ]0,20]). */
  editarDistancia(distancia: number): void {
    const base = this._valores
    if (base === null) return
    const [min, max] = this.opcoes.limitesDistancia?.() ?? [0.1, 10]
    const novos = { ...copia(base), distancia: limitar(distancia, min, max) }
    if (novos.distancia === base.distancia) return
    this._mostrar(novos)
    this._registar(corpoCompleto(novos))
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
   * Comando EXPLÍCITO (vistas rápidas): mostra e envia JÁ a pose pedida (o que o `corpo` não traz — em
   * regra a distância — fica como está) — como o REPOR VISTA, não passa pela coalescência (o dono pediu
   * esta vista; um clique repetido volta a mandá-la).
   */
  irPara(corpo: CorpoCamera): void {
    const base = this._valores
    if (base === null) return
    const novos: CameraEstado = {
      azimute: normalizarAzimute(corpo.azimute ?? base.azimute),
      elevacao: limitar(corpo.elevacao ?? base.elevacao, -90, 90),
      distancia: corpo.distancia ?? base.distancia,
      alvo: base.alvo === null ? null : [base.alvo[0], base.alvo[1], base.alvo[2]],
    }
    this._mostrar(novos)
    this._snapshot = corpoCompleto(novos)
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
