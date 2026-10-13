/**
 * Janela VENTO (tecla 3) — os TRÊS botões que o dono pediu: LIGADO · INTENSIDADE · ALEATORIEDADE.
 * Mais a direção, que se arrasta numa bússola, e a leitura do vento que a física leva AGORA.
 *
 * Tudo é `POST /api/vento-simples` com só o campo que mudou: os interruptores e o fim de um arrasto
 * saem logo; a meio do arrasto (slider ou bússola) sai no máximo um por 100 ms. Não há modos,
 * parâmetros nem «aplicar» — a aleatoriedade (turbulência + rajadas + direção a variar) escala com a
 * intensidade e é o backend que a gera (`vento_natural.py`).
 *
 * BÚSSOLA (vista de cima, MUNDO): a frente da descolagem fica para CIMA. A seta é para onde o vento
 * SOPRA (o pedido); o ponto na borda é para onde sopra agora de facto (com aleatoriedade, deambula);
 * o triângulo ao centro é o nariz do drone, ao vivo.
 */

import {
  useRef,
  type KeyboardEvent as EventoTecla,
  type PointerEvent as EventoPonteiro,
} from "react"

import {
  Deslizador,
  FOCO,
  FormaTom,
  Interruptor,
  Legenda,
} from "@/components/cockpit/pecas"
import { useDesenhoHud } from "@/hooks/use-cockpit"
import {
  VENTO_CALMO_M_S,
  VENTO_SIMPLES_LIMITES,
  direcaoDePontoBussola,
  fmtHud,
  fmtRumo,
  pontoBussola,
  reduzirGraus,
  yawNoMundo,
  textoVentoBordo,
  type EstadoVento,
} from "@/lib/cockpit"
import { vento as controlo } from "@/lib/cockpit-controlos"

/** Raio da bússola no `viewBox` (px). */
const RAIO = 44
/** Passo das setas do teclado na bússola (graus). */
const PASSO_TECLADO = 15

export interface JanelaVentoProps {
  vento: EstadoVento
}

export function JanelaVento({ vento }: JanelaVentoProps) {
  const rAgoraVel = useRef<HTMLSpanElement>(null)
  const rAgoraDir = useRef<HTMLSpanElement>(null)
  const rAgoraPonto = useRef<SVGGElement>(null)
  const rNariz = useRef<SVGGElement>(null)
  const rRajada = useRef<HTMLSpanElement>(null)
  const rBordo = useRef<HTMLSpanElement>(null)

  useDesenhoHud(({ hud, texto }) => {
    const v = hud?.vento ?? null
    const horizontal = v === null ? 0 : Math.hypot(v[0], v[1])
    const direcao =
      v === null || horizontal < VENTO_CALMO_M_S
        ? null
        : reduzirGraus((Math.atan2(v[1], v[0]) * 180) / Math.PI)
    if (rAgoraPonto.current !== null) {
      // O grupo desenha o ponto no cimo (0°); a direção cresce para a esquerda ⇒ rotação negativa.
      rAgoraPonto.current.style.opacity = direcao === null ? "0" : "1"
      if (direcao !== null)
        rAgoraPonto.current.style.transform = `rotate(${(-direcao).toFixed(1)}deg)`
    }
    const yaw = yawNoMundo(hud)
    if (rNariz.current !== null && yaw !== null)
      rNariz.current.style.transform = `rotate(${((-yaw * 180) / Math.PI).toFixed(1)}deg)`
    if (rRajada.current !== null)
      rRajada.current.style.opacity = hud?.rajada === true ? "1" : "0"
    if (!texto) return
    const tVel =
      v === null ? "—" : `${fmtHud(Math.hypot(v[0], v[1], v[2]), 1)} m/s`
    if (rAgoraVel.current !== null && rAgoraVel.current.textContent !== tVel)
      rAgoraVel.current.textContent = tVel
    const tDir = direcao === null ? "sem vento" : `para ${fmtRumo(direcao)}°`
    if (rAgoraDir.current !== null && rAgoraDir.current.textContent !== tDir)
      rAgoraDir.current.textContent = tDir
    const tBordo = textoVentoBordo(hud?.ventoBordo ?? null)
    if (rBordo.current !== null && rBordo.current.textContent !== tBordo)
      rBordo.current.textContent = tBordo
  })

  // ------------------------------------------------------------- bússola: arrastar a direção
  const centro = useRef<{ x: number; y: number } | null>(null)
  const apontar = (evento: EventoPonteiro<HTMLDivElement>, final: boolean) => {
    const c = centro.current
    if (c === null) return
    const direcao = direcaoDePontoBussola(
      evento.clientX - c.x,
      evento.clientY - c.y
    )
    if (direcao !== null) controlo.ajustar({ direcao }, final)
    else if (final) controlo.ajustar({ direcao: vento.direcao }, true)
  }
  const aoBaixar = (evento: EventoPonteiro<HTMLDivElement>) => {
    if (evento.button !== 0) return
    // O centro mede-se UMA vez por gesto (a janela não se mexe a meio de um arrasto da bússola).
    const caixa = evento.currentTarget.getBoundingClientRect()
    centro.current = {
      x: caixa.left + caixa.width / 2,
      y: caixa.top + caixa.height / 2,
    }
    evento.currentTarget.setPointerCapture(evento.pointerId)
    apontar(evento, false)
  }
  const aoLargar = (evento: EventoPonteiro<HTMLDivElement>) => {
    if (centro.current === null) return
    apontar(evento, true)
    centro.current = null
  }
  const aoTeclar = (evento: EventoTecla<HTMLDivElement>) => {
    const passo =
      evento.key === "ArrowLeft" || evento.key === "ArrowUp"
        ? PASSO_TECLADO
        : evento.key === "ArrowRight" || evento.key === "ArrowDown"
          ? -PASSO_TECLADO
          : 0
    if (passo === 0) return
    evento.preventDefault()
    controlo.ajustar({ direcao: vento.direcao + passo }, true)
  }

  const ponta = pontoBussola(vento.direcao)
  const anguloSeta = -vento.direcao // CSS: horário positivo; a direção cresce para a esquerda

  return (
    <div className="flex flex-col gap-3" data-testid="painel-vento">
      <Interruptor
        rotulo="VENTO"
        atalho="V"
        ligado={vento.ligado}
        onMudar={(ligado) => controlo.ajustar({ ligado }, true)}
        testid="vento-ligado"
      />

      <Deslizador
        rotulo="intensidade"
        texto={`${fmtHud(vento.intensidade, 1)} m/s`}
        valor={vento.intensidade}
        min={VENTO_SIMPLES_LIMITES.intensidade[0]}
        max={VENTO_SIMPLES_LIMITES.intensidade[1]}
        passo={VENTO_SIMPLES_LIMITES.passo}
        extremos={["0", "5 m/s"]}
        onArrastar={(intensidade) => controlo.ajustar({ intensidade }, false)}
        onLargar={(intensidade) => controlo.ajustar({ intensidade }, true)}
        testid="vento-intensidade"
      />

      <Interruptor
        rotulo="ALEATORIEDADE"
        descricao="turbulência e rajadas"
        ligado={vento.aleatorio}
        estados={["DESLIGADA", "LIGADA"]}
        onMudar={(aleatorio) => controlo.ajustar({ aleatorio }, true)}
        testid="vento-aleatorio"
      />

      <div className="flex items-center gap-3 border-t border-white/10 pt-3">
        <div
          role="slider"
          tabIndex={0}
          aria-label="direção para onde o vento sopra (arrastar, ou setas)"
          title="arrasta a seta · cima = a frente da descolagem · triângulo = o nariz do drone · ponto branco = o vento de agora"
          aria-valuemin={0}
          aria-valuemax={359}
          aria-valuenow={Math.round(vento.direcao)}
          aria-valuetext={`sopra para ${fmtRumo(vento.direcao)} graus`}
          data-testid="vento-bussola"
          data-direcao={vento.direcao}
          onPointerDown={aoBaixar}
          onPointerMove={(evento) => apontar(evento, false)}
          onPointerUp={aoLargar}
          onPointerCancel={aoLargar}
          onKeyDown={aoTeclar}
          className={`relative size-[6.5rem] shrink-0 cursor-grab touch-none rounded-full active:cursor-grabbing ${FOCO}`}
        >
          <svg viewBox="-52 -52 104 104" className="size-full" aria-hidden="true">
            <circle r={RAIO} fill="rgb(0 0 0 / 0.35)" stroke="var(--hud)" strokeOpacity="0.55" />
            {/* Traços de 45 em 45°; o de cima (frente da descolagem) é maior. */}
            {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
              <line
                key={a}
                y1={-RAIO}
                y2={a === 0 ? -RAIO + 9 : -RAIO + 5}
                stroke="var(--hud)"
                strokeOpacity={a === 0 ? 0.95 : 0.45}
                strokeWidth={a === 0 ? 2 : 1}
                transform={`rotate(${a})`}
              />
            ))}
            {/* Para onde sopra AGORA (ao vivo). */}
            <g ref={rAgoraPonto} style={{ opacity: 0, transformOrigin: "0 0" }}>
              <circle cy={-RAIO} r="3.2" fill="var(--hud)" stroke="#000" strokeWidth="1" />
            </g>
            {/* O nariz do drone (ao vivo). */}
            <g ref={rNariz} style={{ transformOrigin: "0 0" }}>
              <path d="M0 -9 5.5 6H-5.5Z" fill="none" stroke="var(--hud)" strokeOpacity="0.8" strokeWidth="1.2" />
            </g>
            {/* A seta do PEDIDO: do centro para onde o vento sopra. */}
            <g transform={`rotate(${anguloSeta})`} opacity={vento.ligado ? 1 : 0.45}>
              <path
                d={`M0 ${RAIO - 14}V${-RAIO + 12}M-7 ${-RAIO + 21} 0 ${-RAIO + 11} 7 ${-RAIO + 21}`}
                fill="none"
                stroke="var(--hud-ciano)"
                strokeWidth="2.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </g>
            {/* Pega da seta (o que se arrasta). */}
            <circle
              cx={ponta.sx * (RAIO - 2)}
              cy={ponta.sy * (RAIO - 2)}
              r="5.5"
              fill="var(--hud-ciano)"
              stroke="#000"
              strokeWidth="1.2"
            />
          </svg>
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className="flex flex-col gap-0.5">
            <Legenda>sopra para</Legenda>
            <span className="flex items-baseline gap-2">
              <span className="font-mono text-sm font-bold text-hud" data-testid="vento-direcao">
                {fmtRumo(vento.direcao)}°
              </span>
              <span className="text-[0.65rem] text-muted-foreground">
                arrasta a seta
              </span>
            </span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="flex items-center gap-2">
              <Legenda>agora</Legenda>
              <span
                ref={rRajada}
                data-testid="vento-rajada"
                className="flex items-center gap-1 font-mono text-[0.65rem] font-bold tracking-wide text-hud-ambar"
                style={{ opacity: 0 }}
              >
                <FormaTom tom="atencao" className="size-2" />
                RAJADA
              </span>
            </span>
            <span className="font-mono text-sm font-bold text-hud">
              <span ref={rAgoraVel} data-testid="vento-agora-vel">
                —
              </span>
            </span>
            <span
              ref={rAgoraDir}
              data-testid="vento-agora-dir"
              className="font-mono text-[0.68rem] text-muted-foreground"
            >
              —
            </span>
          </div>
        </div>
      </div>

      {/* O que o DRONE estima a bordo (não tem anemómetro: sai da inclinação que precisa para se segurar). */}
      <div
        className="flex items-baseline justify-between gap-2 border-t border-white/10 pt-2.5"
        title="estimado a bordo pelo observador de perturbação do controlador — compara com o «agora», que é o vento real do simulador"
      >
        <Legenda>o drone sente</Legenda>
        <span
          ref={rBordo}
          data-testid="vento-bordo"
          className="font-mono text-[0.72rem] font-bold text-hud"
        >
          —
        </span>
      </div>
    </div>
  )
}
