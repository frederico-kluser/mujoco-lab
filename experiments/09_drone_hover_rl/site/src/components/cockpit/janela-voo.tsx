/**
 * Janela VOO (tecla 1) — o mapa das teclas, a velocidade pedida e o rumo.
 *
 * Não há botão de armar: o controlo de voo vem ATIVO desde o arranque (`ativo: true` em todos os
 * `POST /api/voo`). As teclas são relativas ao NARIZ (W avança para onde o drone aponta) e funcionam
 * com a janela fechada — isto é só o mapa, que também se prime com o rato (manter = manter a tecla).
 *
 * O rumo é lido dos sensores de bordo (`est.psi`) por ref, no `requestAnimationFrame` do HUD.
 */

import { useRef } from "react"

import { FOCO, Legenda, Marca, Tecla } from "@/components/cockpit/pecas"
import { useDesenhoHud } from "@/hooks/use-cockpit"
import {
  fmtHud,
  fmtRumo,
  instrumentos,
  rumoEmGraus,
  rumoParaFixar,
  velocidadeNoNariz,
  type EstadoPiloto,
  type EstadoTiro,
} from "@/lib/cockpit"
import { piloto as controlo, tiro as controloTiro } from "@/lib/cockpit-controlos"
import { hud } from "@/lib/hud-store"
import type { TeclaVoo } from "@/lib/voo"

/** As 6 teclas de movimento pela ordem do teclado (Q W E / A S D) e o que fazem. */
const MOVIMENTO: readonly { tecla: TeclaVoo; rotulo: string; titulo: string }[] = [
  { tecla: "q", rotulo: "subir", titulo: "Q · subir (0,7 m/s)" },
  { tecla: "w", rotulo: "frente", titulo: "W · para a frente do nariz (1,0 m/s)" },
  { tecla: "e", rotulo: "descer", titulo: "E · descer (0,7 m/s)" },
  { tecla: "a", rotulo: "esquerda", titulo: "A · para a esquerda do nariz (1,0 m/s)" },
  { tecla: "s", rotulo: "trás", titulo: "S · para trás (1,0 m/s)" },
  { tecla: "d", rotulo: "direita", titulo: "D · para a direita do nariz (1,0 m/s)" },
]

export interface JanelaVooProps {
  piloto: EstadoPiloto
  tiro?: EstadoTiro
  /** A bola está a pilotar (as teclas de movimento ficam em espera). */
  aSeguirBola: boolean
  /** O runner aceita comandos de voo? (`false` = política sem modo de comando: as teclas não mandam) */
  aceitaComandos: boolean
  /** X sem rumo conhecido: o cockpit avisa em vez de fixar um rumo inventado. */
  onSemRumo: () => void
}

/** `+1,0` com sinal explícito (zero sem sinal). */
function comSinal(v: number): string {
  const t = fmtHud(v, 1)
  return v > 0.049 ? `+${t}` : t
}

export function JanelaVoo({
  piloto,
  tiro,
  aSeguirBola,
  aceitaComandos,
  onSemRumo,
}: JanelaVooProps) {
  const rRumo = useRef<HTMLSpanElement>(null)
  const rTiros = useRef<HTMLSpanElement>(null)
  const rSoco = useRef<HTMLSpanElement>(null)
  const rDirecaoSoco = useRef<HTMLSpanElement>(null)
  useDesenhoHud(({ hud: amostra, texto }) => {
    if (!texto) return
    if (rRumo.current !== null) {
      const valor = fmtRumo(instrumentos(amostra).rumo)
      if (rRumo.current.textContent !== valor) rRumo.current.textContent = valor
    }
    const t = amostra?.tiro ?? null
    if (rTiros.current !== null) {
      const txt = t === null ? "0 tiros" : `${t.tiros} tiros (${t.municao ?? 15}/${t.capacidade ?? 15})`
      if (rTiros.current.textContent !== txt) rTiros.current.textContent = txt
    }
    if (rSoco.current !== null && t !== null) {
      const txt = `J=${fmtHud(t.impulsoNs, 2)} N·s · F=${fmtHud(t.forcaPicoN, 1)} N · Δv=−${fmtHud(t.deltaVTeoricoMS, 2)} m/s · Δω=${fmtHud(t.deltaOmegaPitchRadS, 2)} rad/s`
      if (rSoco.current.textContent !== txt) rSoco.current.textContent = txt
    }
    if (rDirecaoSoco.current !== null && t !== null && t.azimuteSocoGraus !== null) {
      const txt = `−x̂ nariz (${fmtRumo(t.azimuteSocoGraus)}° mundo)`
      if (rDirecaoSoco.current.textContent !== txt) rDirecaoSoco.current.textContent = txt
    }
  })

  const [frente, esquerda, cima] = velocidadeNoNariz(piloto)
  const fixo = piloto.yaw_alvo !== null
  const fixar = () => {
    if (!controlo.fixarRumo(rumoParaFixar(hud.ultima()))) onSemRumo()
  }

  return (
    <div className="flex flex-col gap-3" data-testid="controlo-voo">
      {!aceitaComandos ? (
        <p
          data-testid="voo-indisponivel"
          className="rounded-lg border border-hud-ambar/55 bg-hud-ambar/10 px-2.5 py-1.5 text-[0.72rem] leading-snug text-hud"
        >
          A política que está a voar não foi treinada para obedecer a comandos:
          as teclas são enviadas mas o drone não as segue.
        </p>
      ) : aSeguirBola ? (
        <p
          data-testid="voo-bola-manda"
          className="rounded-lg border border-hud-magenta/50 bg-hud-magenta/10 px-2.5 py-1.5 text-[0.72rem] leading-snug text-hud"
        >
          A bola está a pilotar: o drone roda e desloca-se sozinho para a manter
          ao centro. <strong>B</strong> devolve o controlo às teclas.
        </p>
      ) : null}

      <div className="grid grid-cols-3 gap-1.5">
        {MOVIMENTO.map(({ tecla, rotulo, titulo }) => (
          <Tecla
            key={tecla}
            letra={tecla.toUpperCase()}
            rotulo={rotulo}
            titulo={titulo}
            premida={piloto.teclas[tecla]}
            apagada={aSeguirBola}
            testid={`voo-tecla-${tecla}`}
            onPremir={() => controlo.premir(tecla)}
            onLargar={() => controlo.largar(tecla)}
          />
        ))}
      </div>
      <p className="text-[0.68rem] leading-snug text-muted-foreground">
        Relativas ao nariz. Sem teclas o drone segura a posição.
      </p>

      <div className="flex flex-col gap-1">
        <Legenda>velocidade pedida</Legenda>
        <p
          data-testid="voo-vref"
          className="flex justify-between gap-2 font-mono text-[0.78rem] text-hud"
        >
          <span>
            frente <strong>{comSinal(frente)}</strong>
          </span>
          <span>
            esq. <strong>{comSinal(esquerda)}</strong>
          </span>
          <span>
            subir <strong>{comSinal(cima)}</strong>
          </span>
          <span className="text-muted-foreground">m/s</span>
        </p>
      </div>

      <div className="flex flex-col gap-1.5 border-t border-white/10 pt-2.5">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-baseline gap-2">
            <Legenda>rumo</Legenda>
            <span className="font-mono text-base font-bold text-hud">
              <span ref={rRumo} data-testid="voo-rumo">
                —
              </span>
              °
            </span>
          </span>
          {fixo ? (
            <span className="flex items-center gap-2">
              <Marca tom="ativo" testid="voo-rumo-fixo">
                FIXO A {fmtRumo(rumoEmGraus(piloto.yaw_alvo ?? 0))}°
              </Marca>
              <button
                type="button"
                data-testid="voo-rumo-soltar"
                onClick={() => controlo.soltarRumo()}
                className={`flex h-8 items-center rounded-lg border border-white/25 px-2 text-[0.68rem] font-bold tracking-wide text-hud hover:bg-white/12 ${FOCO}`}
              >
                SOLTAR
              </button>
            </span>
          ) : (
            <Marca tom="normal" testid="voo-rumo-livre">
              LIVRE
            </Marca>
          )}
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          <Tecla
            letra="Z"
            rotulo="rodar ⟲"
            titulo="Z · rodar para a esquerda (manter)"
            premida={piloto.z}
            apagada={aSeguirBola}
            testid="voo-tecla-z"
            onPremir={() => controlo.premir("z")}
            onLargar={() => controlo.largar("z")}
          />
          <Tecla
            letra="X"
            rotulo="fixar rumo"
            titulo="X · fixar o rumo atual"
            premida={fixo}
            apagada={aSeguirBola}
            testid="voo-tecla-x"
            onPremir={fixar}
            onLargar={() => undefined}
          />
          <Tecla
            letra="C"
            rotulo="rodar ⟳"
            titulo="C · rodar para a direita (manter)"
            premida={piloto.c}
            apagada={aSeguirBola}
            testid="voo-tecla-c"
            onPremir={() => controlo.premir("c")}
            onLargar={() => controlo.largar("c")}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5 border-t border-white/10 pt-2.5" data-testid="voo-arma">
        <div className="flex items-center justify-between gap-2">
          <Legenda>arma no topo · Glock 25 (.380)</Legenda>
          <span
            ref={rTiros}
            data-testid="voo-tiro-contagem"
            className="font-mono text-[0.72rem] font-bold text-hud"
          >
            0 tiros (15/15)
          </span>
        </div>
        <Tecla
          letra="ESPAÇO · TIRO"
          rotulo="disparar (+x̂ nariz · soco −x̂)"
          titulo="ESPAÇO · Disparar Glock 25 .380 Auto fixa no topo do drone"
          premida={Boolean(tiro?.gatilho)}
          testid="voo-tecla-espaco"
          onPremir={() => controloTiro.premir()}
          onLargar={() => controloTiro.largar()}
        />
        <p className="font-mono text-[0.68rem] leading-snug text-hud" data-testid="voo-tiro-soco">
          <span ref={rSoco}>J=1,92 N·s · F=95,8 N · Δv=−0,65 m/s · Δω=−1,09 rad/s</span>
        </p>
        <p className="flex justify-between font-mono text-[0.65rem] text-muted-foreground">
          <span>direção do soco:</span>
          <strong ref={rDirecaoSoco} data-testid="voo-tiro-direcao" className="text-hud">
            −x̂ nariz (180° mundo)
          </strong>
        </p>
      </div>
    </div>
  )
}
