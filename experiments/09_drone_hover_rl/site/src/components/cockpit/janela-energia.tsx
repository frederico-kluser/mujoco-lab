/**
 * Janela ENERGIA (tecla 5) — bateria e motores, em compacto: carga, tensão, corrente, potência,
 * autonomia e o esforço dos 4 motores (vista de cima, frente para cima), tudo do HUD (50 Hz, por
 * refs). RECARREGAR fecha o ciclo do pack (`POST /api/bateria`).
 *
 * O DETALHE (curva de descarga, saúde do pack, empuxo e corrente por motor, ledger de potência) são os
 * painéis de sempre — `PainelBateria` e `PainelMotores` — e vem RECOLHIDO: precisam do histórico do
 * `GET /api/sim`, que só é sondado enquanto o detalhe estiver aberto.
 */

import { useRef, type ReactNode } from "react"
import { BatteryCharging, ChevronDown, ChevronUp } from "lucide-react"

import { PainelTrocaPecas } from "@/components/cockpit/painel-troca-pecas"
import { FOCO, Legenda, Leitura } from "@/components/cockpit/pecas"
import { useDesenhoHud } from "@/hooks/use-cockpit"
import { fmtAutonomia, fmtHud, limitar } from "@/lib/cockpit"
import { ROTORES_REAIS, ROTORES_VISTA_DE_CIMA } from "@/lib/sim"

export interface JanelaEnergiaProps {
  /** A planta tem bateria modelada (drone real)? No cf2 não há nada para mostrar. */
  temBateria: boolean
  apiLigada: boolean
  aRecarregar: boolean
  onRecarregar: () => void
  detalheAberto: boolean
  onDetalhe: (aberto: boolean) => void
  /** Os painéis de detalhe (só montados com o detalhe aberto). */
  detalhe: ReactNode
}

export function JanelaEnergia({
  temBateria,
  apiLigada,
  aRecarregar,
  onRecarregar,
  detalheAberto,
  onDetalhe,
  detalhe,
}: JanelaEnergiaProps) {
  const rPct = useRef<HTMLSpanElement>(null)
  const rNivel = useRef<HTMLSpanElement>(null)
  const rV = useRef<HTMLSpanElement>(null)
  const rI = useRef<HTMLSpanElement>(null)
  const rP = useRef<HTMLSpanElement>(null)
  const rAutonomia = useRef<HTMLSpanElement>(null)
  const rBarras = useRef<(HTMLSpanElement | null)[]>([])
  const rDuty = useRef<(HTMLSpanElement | null)[]>([])

  useDesenhoHud(({ hud, texto }) => {
    const b = hud?.bateria ?? null
    if (rNivel.current !== null && b?.soc != null)
      rNivel.current.style.transform = `scaleX(${limitar(b.soc, 0, 1).toFixed(3)})`
    const motores = hud?.motores ?? null
    for (let i = 0; i < 4; i += 1) {
      const barra = rBarras.current[i]
      if (barra != null)
        barra.style.transform = `scaleY(${(motores?.[i] ?? 0).toFixed(3)})`
    }
    if (!texto) return
    const escrever = (el: HTMLElement | null, t: string) => {
      if (el !== null && el.textContent !== t) el.textContent = t
    }
    escrever(rPct.current, b?.soc == null ? "—" : fmtHud(b.soc * 100, 1))
    escrever(rV.current, b?.v == null ? "—" : `${fmtHud(b.v, 2)} V`)
    escrever(rI.current, b?.i == null ? "—" : `${fmtHud(b.i, 1)} A`)
    escrever(rP.current, b?.p == null ? "—" : `${fmtHud(b.p, 0)} W`)
    escrever(rAutonomia.current, fmtAutonomia(b?.autonomiaMin))
    for (let i = 0; i < 4; i += 1) {
      const duty = motores?.[i]
      escrever(
        rDuty.current[i] ?? null,
        duty === undefined ? "—" : `${Math.round(duty * 100)} %`
      )
    }
  })

  if (!temBateria) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="energia-sem-bateria">
        Esta planta não tem bateria nem motores modelados (é o Crazyflie de
        referência). A energia aparece quando voa o drone real.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3" data-testid="painel-energia">
      <div className="flex flex-col gap-1.5">
        <div className="flex items-baseline justify-between">
          <Legenda>carga</Legenda>
          <span className="font-mono text-2xl leading-none font-bold text-hud">
            <span ref={rPct} data-testid="energia-carga">
              —
            </span>
            <span className="text-sm"> %</span>
          </span>
        </div>
        <span className="block h-2 overflow-hidden rounded-full bg-white/15">
          <span
            ref={rNivel}
            className="block size-full origin-left rounded-full bg-hud will-change-transform"
            style={{ transform: "scaleX(0)" }}
          />
        </span>
      </div>

      <div className="grid grid-cols-4 gap-2">
        <Leitura rotulo="tensão" refValor={rV} testid="energia-tensao" />
        <Leitura rotulo="corrente" refValor={rI} testid="energia-corrente" />
        <Leitura rotulo="potência" refValor={rP} testid="energia-potencia" />
        <Leitura rotulo="autonomia" refValor={rAutonomia} testid="energia-autonomia" />
      </div>

      <div className="flex items-end justify-between gap-3 border-t border-white/10 pt-3">
        <div className="flex flex-col gap-1">
          <Legenda>motores · esforço</Legenda>
          {/* Vista de cima, frente para cima: frente-esq · frente-dir / trás-esq · trás-dir. */}
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5" data-testid="energia-motores">
            {ROTORES_VISTA_DE_CIMA.map((indice) => {
              const rotor = ROTORES_REAIS[indice]
              return (
                <div key={rotor.nome} className="flex items-end gap-1.5" title={rotor.posicao}>
                  <span className="relative block h-9 w-2.5 overflow-hidden rounded-sm bg-white/15">
                    <span
                      ref={(el) => {
                        rBarras.current[indice] = el
                      }}
                      className="absolute inset-0 block origin-bottom bg-hud will-change-transform"
                      style={{ transform: "scaleY(0)" }}
                    />
                  </span>
                  <span className="flex flex-col leading-tight">
                    <span className="text-[0.65rem] text-muted-foreground">
                      {rotor.posicao}
                    </span>
                    <span
                      ref={(el) => {
                        rDuty.current[indice] = el
                      }}
                      className="font-mono text-[0.72rem] font-bold text-hud"
                    >
                      —
                    </span>
                  </span>
                </div>
              )
            })}
          </div>
        </div>
        <button
          type="button"
          data-testid="energia-recarregar"
          disabled={!apiLigada || aRecarregar}
          onClick={onRecarregar}
          title="fecha o ciclo do pack e volta a 100 % (conta o desgaste)"
          className={`flex h-10 shrink-0 items-center gap-2 rounded-xl border border-white/25 bg-white/8 px-3 text-[0.72rem] font-bold tracking-[0.1em] text-hud hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-45 ${FOCO}`}
        >
          <BatteryCharging className="size-4" aria-hidden="true" />
          {aRecarregar ? "A RECARREGAR…" : "RECARREGAR"}
        </button>
      </div>

      <button
        type="button"
        data-testid="energia-detalhe"
        aria-expanded={detalheAberto}
        onClick={() => onDetalhe(!detalheAberto)}
        className={`flex h-8 items-center justify-between rounded-lg px-2 text-[0.72rem] text-muted-foreground hover:bg-white/8 hover:text-hud ${FOCO}`}
      >
        <span>
          {detalheAberto
            ? "esconder o detalhe"
            : "ver o detalhe (descarga, saúde do pack, cada motor)"}
        </span>
        {detalheAberto ? (
          <ChevronUp className="size-4" aria-hidden="true" />
        ) : (
          <ChevronDown className="size-4" aria-hidden="true" />
        )}
      </button>

      <PainelTrocaPecas />

      {detalheAberto ? (
        <div className="flex flex-col gap-3" data-testid="energia-detalhe-paineis">
          {detalhe}
        </div>
      ) : null}
    </div>
  )
}
