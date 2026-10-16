/**
 * Janela BOLA (tecla 2) — o modo SEGUIR A BOLA: a bola passa a mover-se ao acaso e o drone roda e
 * desloca-se para a manter no centro da câmara de bordo.
 *
 * Dois controlos: o interruptor grande (tecla B → `segui_alvo` no `POST /api/voo`) e a velocidade da
 * bola (`POST /api/bola`, na faixa que o `/api/state` anuncia). O resto é leitura AO VIVO do que o
 * DETETOR de bordo vê — não a verdade do simulador —, desenhada por refs no quadro do HUD:
 *  · o ALVO: um mostrador polar onde o ponto é a bola e o centro é o eixo da câmara (anéis a 5°, 20°
 *    e 40° de erro); bola no anel de dentro = centrada;
 *  · o erro de centragem (graus e px do detetor) e a distância à bola.
 */

import { useRef } from "react"

import {
  Deslizador,
  Interruptor,
  Legenda,
  Leitura,
  Marca,
} from "@/components/cockpit/pecas"
import { useDesenhoHud } from "@/hooks/use-cockpit"
import {
  PASSO_BOLA,
  ROTULO_SEGUIDOR,
  TOM_SEGUIDOR,
  erroCentragem,
  fmtHud,
  type EstadoBola,
  type EstadoSeguidor,
} from "@/lib/cockpit"
import { bola as controloBola, piloto } from "@/lib/cockpit-controlos"

/** Raio do mostrador (px) e o erro que o enche (graus) — a borda é ~meio campo do detetor. */
const RAIO_ALVO = 46
const ERRO_MAX_GRAUS = 40
const ANEIS_GRAUS = [5, 20, 40] as const

export interface JanelaBolaProps {
  /** O interruptor (estado local, otimista). */
  seguir: boolean
  /** O que o seguidor de bordo diz (resumo lento do HUD). */
  seguidor: EstadoSeguidor
  bola: EstadoBola
}

export function JanelaBola({ seguir, seguidor, bola }: JanelaBolaProps) {
  const rPonto = useRef<HTMLSpanElement>(null)
  const rPontoMira = useRef<HTMLSpanElement>(null)
  const rErro = useRef<HTMLSpanElement>(null)
  const rDistancia = useRef<HTMLSpanElement>(null)
  const rMiraEstado = useRef<HTMLSpanElement>(null)
  const rAcertos = useRef<HTMLSpanElement>(null)

  useDesenhoHud(({ hud, texto }) => {
    const b = hud?.bola ?? null
    const t = hud?.tiro ?? null
    const mira = t?.mira ?? null
    const erro = b !== null && b.seguir ? erroCentragem(b) : null
    const ponto = rPonto.current
    if (ponto !== null) {
      if (erro !== null && b !== null && b.erroTan !== null) {
        // Polar em ÂNGULO: a direção é a do erro na imagem, o raio é o ângulo ao eixo da câmara.
        const modulo = Math.hypot(b.erroTan[0], b.erroTan[1])
        const r = Math.min(1, erro.graus / ERRO_MAX_GRAUS) * RAIO_ALVO
        const k = modulo > 1e-9 ? r / modulo : 0
        ponto.style.transform = `translate3d(${(b.erroTan[0] * k).toFixed(1)}px,${(b.erroTan[1] * k).toFixed(1)}px,0)`
        ponto.style.opacity = "1"
      } else {
        ponto.style.opacity = "0"
      }
    }
    const pontoMira = rPontoMira.current
    if (pontoMira !== null) {
      if (mira !== null && mira.pontoImpactoTan !== null) {
        const modM = Math.hypot(mira.pontoImpactoTan[0], mira.pontoImpactoTan[1])
        const grausM = (Math.atan(modM) * 180) / Math.PI
        const rM = Math.min(1, grausM / ERRO_MAX_GRAUS) * RAIO_ALVO
        const kM = modM > 1e-9 ? rM / modM : 0
        pontoMira.style.transform = `translate3d(${(mira.pontoImpactoTan[0] * kM).toFixed(1)}px,${(mira.pontoImpactoTan[1] * kM).toFixed(1)}px,0)`
        pontoMira.style.opacity = "1"
      } else {
        pontoMira.style.opacity = "0"
      }
    }
    if (!texto) return
    const tErro =
      erro === null
        ? "—"
        : `${fmtHud(erro.graus, 1)}°${erro.px === null ? "" : ` · ${fmtHud(erro.px, 0)} px`}`
    if (rErro.current !== null && rErro.current.textContent !== tErro)
      rErro.current.textContent = tErro
    const tDist = b?.dist == null || !b.seguir ? "—" : `${fmtHud(b.dist, 2)} m`
    if (rDistancia.current !== null && rDistancia.current.textContent !== tDist)
      rDistancia.current.textContent = tDist
    if (rMiraEstado.current !== null) {
      const txtMira =
        mira === null
          ? "—"
          : `${mira.noAlvo ? "NO ALVO" : "FORA DO ALVO"}${
              mira.erroBolaM != null ? ` (${fmtHud(mira.erroBolaM * 100, 1)} cm)` : ""
            }`
      if (rMiraEstado.current.textContent !== txtMira)
        rMiraEstado.current.textContent = txtMira
    }
    if (rAcertos.current !== null) {
      const txtAc =
        t === null
          ? "0 / 0"
          : `${t.acertosBola} / ${t.tiros} (${
              t.ultimoResultado === "acertou_bola"
                ? "ACERTOU"
                : t.ultimoResultado === null
                  ? "—"
                  : "ERROU"
            })`
      if (rAcertos.current.textContent !== txtAc)
        rAcertos.current.textContent = txtAc
    }
  })

  return (
    <div className="flex flex-col gap-3" data-testid="painel-bola">
      <Interruptor
        rotulo="SEGUIR A BOLA"
        atalho="B"
        descricao="alinha a mira balística da Glock 25 na bola"
        ligado={seguir}
        onMudar={(ligado) => piloto.seguirBola(ligado)}
        testid="bola-seguir"
      />

      <Interruptor
        rotulo="AUTO SHOOT (ATIRAR NO ALVO)"
        descricao="dispara só quando o projétil vai literalmente acertar a bola na chegada"
        ligado={Boolean(bola?.autoAtirar)}
        onMudar={(ligado) => controloBola.alternarAutoAtirar(ligado)}
        testid="bola-auto-shoot"
      />

      {bola !== null ? (
        <Deslizador
          rotulo="velocidade da bola"
          texto={bola.velocidade === 0 ? "0,00 m/s (parada)" : `${fmtHud(bola.velocidade, 2)} m/s`}
          valor={bola.velocidade}
          min={bola.min}
          max={bola.max}
          passo={PASSO_BOLA}
          extremos={[`${fmtHud(bola.min, 1)} (parada)`, `${fmtHud(bola.max, 1)} m/s`]}
          onArrastar={(v) => controloBola.ajustar(v, false)}
          onLargar={(v) => controloBola.ajustar(v, true)}
          testid="bola-velocidade"
        />
      ) : (
        <p className="text-[0.7rem] text-muted-foreground" data-testid="bola-sem-faixa">
          À espera do simulador para saber a que velocidades a bola pode andar.
        </p>
      )}

      <div className="flex items-center gap-3 border-t border-white/10 pt-3">
        {/* O ALVO: centro = eixo da câmara; ponto magenta = bola; anel verde = onde o tiro vai pegar. */}
        <div
          data-testid="bola-alvo"
          className="relative size-[6.5rem] shrink-0"
          role="img"
          aria-label="alvo: posição da bola e ponto de impacto do tiro em relação ao centro da câmara"
        >
          <svg viewBox="-52 -52 104 104" className="size-full" aria-hidden="true">
            {ANEIS_GRAUS.map((graus) => (
              <circle
                key={graus}
                r={(graus / ERRO_MAX_GRAUS) * RAIO_ALVO}
                fill={graus === 5 ? "rgb(255 255 255 / 0.08)" : "none"}
                stroke="var(--hud)"
                strokeOpacity={graus === 40 ? 0.6 : 0.3}
                strokeWidth="1"
              />
            ))}
            <path
              d="M-50 0H-8M8 0H50M0 -50V-8M0 8V50"
              stroke="var(--hud)"
              strokeOpacity="0.3"
              strokeWidth="1"
            />
          </svg>
          <span className="absolute top-1/2 left-1/2 -mt-1.5 -ml-1.5 block size-3">
            <span
              ref={rPonto}
              className="block size-3 rounded-full border-2 border-black/70 bg-hud-magenta will-change-transform"
              style={{ opacity: 0 }}
            />
          </span>
          <span className="absolute top-1/2 left-1/2 -mt-2 -ml-2 block size-4">
            <span
              ref={rPontoMira}
              data-testid="bola-ponto-impacto"
              className="block size-4 rounded-full border-2 border-emerald-400 bg-emerald-400/20 will-change-transform"
              style={{ opacity: 0 }}
            />
          </span>
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <div className="flex flex-col gap-0.5">
            <Legenda>seguidor</Legenda>
            <Marca tom={TOM_SEGUIDOR[seguidor]} testid="bola-seguidor">
              {ROTULO_SEGUIDOR[seguidor]}
            </Marca>
          </div>
          <Leitura rotulo="mira do tiro" refValor={rMiraEstado} testid="bola-mira-estado" />
          <Leitura rotulo="tiros na bola" refValor={rAcertos} testid="bola-tiros-acertos" />
          <Leitura rotulo="erro ao centro" refValor={rErro} testid="bola-erro" />
          <Leitura rotulo="distância" refValor={rDistancia} testid="bola-distancia" />
        </div>
      </div>

      <p className="text-[0.68rem] leading-snug text-muted-foreground">
        No modo Seguir a Bola a IA de mira balística (treinada em GPU) alinha o ponto de impacto do cano da Glock 25 com o centro da bola (0 m/s parada a 0,8 m/s móvel). Com AUTO SHOOT ligado, dispara apenas quando o projétil vai literalmente acertar a bola na chegada.
      </p>
    </div>
  )
}
