/**
 * Rosa dos ventos VIVA — bússola polar do vento em vigor.
 *
 * Duas setas, de propósito: a **cheia** é o VETOR EM VIGOR (`vento_vec` da telemetria, base + dinâmica) e
 * a **tracejada** é a direção da SELEÇÃO dos sliders (o que um APLICAR VENTO enviaria). Assim vê-se, sem
 * clicar, quando a física está a fazer algo diferente do que está nos sliders — que é exactamente o caso
 * das rajadas/frente/turbulência.
 *
 * Convenção (a mesma do `env.py`): azimute anti-horário a partir de +x ⇒ **E = 0°, N = 90°, O = 180°,
 * S = 270°**; `transform: rotate(-azimute)` porque no SVG o eixo y cresce para baixo.
 *
 * Cascata: passo 4 (código novo) — o catálogo não tem mostrador polar/bússola (`sparkline` é série
 * temporal e `progress-bar` é barra); é SVG com `transform`/`opacity` apenas (regra 8).
 */

import { motion } from "motion/react"
import { Zap } from "lucide-react"

import { useMotionUITransition } from "@/components/motion-ui/ui-theme"
import {
  direcaoDoVetor,
  fmt,
  fmtGraus,
  pontoCardeal,
  ROTULO_MODO,
  VENTO_LIMITES,
  type CorpoVento,
  type ModoVentoDinamico,
} from "@/lib/sim"

/** Norma (m/s) que enche a seta por completo na rosa. */
const VEL_MAX_ROSA = VENTO_LIMITES.vel[1]

/** Comprimento (unidades do viewBox) da seta para uma norma em m/s. */
export function comprimentoSeta(modulo: number): number {
  const forca = Math.max(0, Math.min(modulo, VEL_MAX_ROSA)) / VEL_MAX_ROSA
  return 9 + forca * 25
}

interface RosaDosVentosProps {
  /** Direção selecionada nos sliders (o que o APLICAR VENTO enviaria). */
  selecao: CorpoVento
  /** Vetor em vigor `[vx,vy,vz]`; `null` quando a telemetria ainda não o traz. */
  vec: [number, number, number] | null
  /** Modo dinâmico em vigor (telemetria `vento_modo`; senão o do `/api/sim`). */
  modo: ModoVentoDinamico
}

const CARDEAIS: {
  nome: string
  graus: number
  x: number
  y: number
  ancora: string
}[] = [
  { nome: "E", graus: 0, x: 31, y: 3.5, ancora: "start" },
  { nome: "N", graus: 90, x: 0, y: -31, ancora: "middle" },
  { nome: "O", graus: 180, x: -31, y: 3.5, ancora: "end" },
  { nome: "S", graus: 270, x: 0, y: 38, ancora: "middle" },
]

/** Marcas de 30 em 30° (referência visual de graus, sem números). */
const MARCAS = Array.from({ length: 12 }, (_, i) => (i * 30 * Math.PI) / 180)

/** Mostrador polar com N/E/S/O + graus, seta do vetor em vigor e seta da seleção. */
export function RosaDosVentos({ selecao, vec, modo }: RosaDosVentosProps) {
  const ui = useMotionUITransition("ui")
  const daTelemetria = vec !== null
  const efetivo = direcaoDoVetor(vec ?? [0, 0, 0])
  const ativo = daTelemetria ? efetivo.modulo > 0 : selecao.vel > 0
  const dinamico = modo !== "nenhum"
  const rajada =
    dinamico &&
    (modo === "rajada_agora" || modo === "rajadas" || modo === "aleatoria")

  return (
    <div className="flex flex-col gap-2" data-testid="rosa-vento">
      <div className="flex items-center gap-3">
        <svg
          viewBox="-48 -48 96 96"
          className="size-24 shrink-0"
          role="img"
          aria-label={
            daTelemetria
              ? `vento em vigor ${fmt(efetivo.modulo, 2)} m/s a ${fmtGraus(efetivo.azimute)} de azimute (${pontoCardeal(efetivo.azimute)}), elevação ${fmtGraus(efetivo.elevacao)}`
              : "sem vetor de vento na telemetria: mostra-se a direção da seleção"
          }
          data-testid="bussola"
        >
          <circle
            r="40"
            className="fill-muted/30 stroke-border"
            strokeWidth="1"
          />

          {/* marcas de 30° — os eixos N/S e E/O ficam por conta das linhas abaixo */}
          {MARCAS.map((angulo) => (
            <line
              key={angulo}
              x1={Math.cos(angulo) * 36}
              y1={-Math.sin(angulo) * 36}
              x2={Math.cos(angulo) * 40}
              y2={-Math.sin(angulo) * 40}
              className="stroke-border"
              strokeWidth="1"
            />
          ))}
          <line
            x1="-40"
            y1="0"
            x2="40"
            y2="0"
            className="stroke-border"
            strokeWidth="1"
          />
          <line
            x1="0"
            y1="-40"
            x2="0"
            y2="40"
            className="stroke-border"
            strokeWidth="1"
          />

          {CARDEAIS.map((c) => (
            <text
              key={c.nome}
              x={c.x}
              y={c.y}
              textAnchor={c.ancora as "start" | "middle" | "end"}
              style={{ fontSize: 7.5 }}
              className="fill-muted-foreground"
            >
              {c.nome} {c.graus}°
            </text>
          ))}

          {/* anel que pulsa enquanto há dinâmica ativa (rajadas/frente/turbulência) */}
          {dinamico ? (
            <motion.circle
              r="44"
              className={
                rajada
                  ? "fill-none stroke-primary"
                  : "fill-none stroke-destructive"
              }
              strokeWidth="1.5"
              strokeDasharray={rajada ? undefined : "3 4"}
              style={{ transformOrigin: "0px 0px" }}
              animate={{
                opacity: [0.15, 0.8, 0.15],
                scale: [0.98, 1.04, 0.98],
              }}
              transition={{
                duration: rajada ? 1.1 : 2,
                repeat: Infinity,
                ease: "easeInOut",
              }}
              data-testid="anel-dinamico"
            />
          ) : null}

          {/* seta da SELEÇÃO (sliders) — tracejada, por baixo da seta em vigor */}
          <motion.g
            initial={false}
            animate={{
              rotate: -selecao.azimute,
              opacity: selecao.vel > 0 ? 0.55 : 0.2,
            }}
            transition={{ ...ui }}
          >
            <line
              x1="0"
              y1="0"
              x2={comprimentoSeta(selecao.vel)}
              y2="0"
              className="stroke-muted-foreground"
              strokeWidth="2"
              strokeDasharray="4 3"
              strokeLinecap="round"
            />
          </motion.g>

          {/* seta do VETOR EM VIGOR — cheia, com a ponta na direção do escoamento */}
          {daTelemetria ? (
            <motion.g
              initial={false}
              animate={{ rotate: -efetivo.azimute }}
              transition={{ ...ui }}
            >
              <line
                x1="0"
                y1="0"
                x2={comprimentoSeta(efetivo.horizontal)}
                y2="0"
                className={ativo ? "stroke-primary" : "stroke-muted-foreground"}
                strokeWidth="3"
                strokeLinecap="round"
                data-testid="seta-vento"
              />
              {efetivo.horizontal > 0 ? (
                <polygon
                  points={`${comprimentoSeta(efetivo.horizontal) + 5},0 ${comprimentoSeta(efetivo.horizontal) - 3},-3.6 ${comprimentoSeta(efetivo.horizontal) - 3},3.6`}
                  className={ativo ? "fill-primary" : "fill-muted-foreground"}
                />
              ) : null}
            </motion.g>
          ) : (
            <motion.g
              initial={false}
              animate={{ rotate: -selecao.azimute }}
              transition={{ ...ui }}
            >
              <line
                x1="0"
                y1="0"
                x2={comprimentoSeta(selecao.vel)}
                y2="0"
                className={ativo ? "stroke-primary" : "stroke-muted-foreground"}
                strokeWidth="3"
                strokeLinecap="round"
                data-testid="seta-vento"
              />
            </motion.g>
          )}

          {/* elevação: seta vertical no centro (a rosa é o plano horizontal) */}
          {daTelemetria && Math.abs(efetivo.elevacao) > 0.5 ? (
            <line
              x1="0"
              y1="0"
              x2="0"
              y2={efetivo.elevacao > 0 ? -13 : 13}
              className="stroke-primary"
              strokeWidth="1.5"
              strokeDasharray="2 2"
            />
          ) : null}
          <circle cx="0" cy="0" r="2.6" className="fill-primary" />
        </svg>

        <dl className="grid flex-1 grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[0.7rem]">
          <dt className="text-muted-foreground">em vigor</dt>
          <dd className="text-right tabular-nums" data-testid="vento-em-vigor">
            {daTelemetria ? `${fmt(efetivo.modulo, 2)} m/s` : "— (sem vetor)"}
          </dd>
          <dt className="text-muted-foreground">rumo</dt>
          <dd className="text-right tabular-nums">
            {daTelemetria
              ? `${fmtGraus(efetivo.azimute)} ${pontoCardeal(efetivo.azimute)}`
              : "—"}
          </dd>
          <dt className="text-muted-foreground">elevação</dt>
          <dd className="text-right tabular-nums">
            {daTelemetria
              ? fmtGraus(efetivo.elevacao)
              : fmtGraus(selecao.elevacao)}
          </dd>
          <dt className="text-muted-foreground">seleção</dt>
          <dd className="text-right tabular-nums">
            {fmt(selecao.vel, 2)} m/s · {fmtGraus(selecao.azimute)}
          </dd>
          <dt className="text-muted-foreground">modo</dt>
          <dd
            className={`flex items-center justify-end gap-1 text-right ${dinamico ? "text-primary" : ""}`}
            data-testid="modo-vento"
          >
            {dinamico ? <Zap className="size-3" aria-hidden="true" /> : null}
            {ROTULO_MODO[modo]}
          </dd>
        </dl>
      </div>

      <p className="font-mono text-[0.6rem] leading-tight text-muted-foreground">
        sólida = vento em vigor (base + dinâmica) · tracejada = seleção dos
        sliders · E 0° · N 90° · O 180° · S 270° (azimute anti-horário a partir
        de +x)
      </p>
    </div>
  )
}
