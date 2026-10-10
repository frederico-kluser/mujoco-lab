/**
 * RESUMO DE BORDO (planta real, secção «Operação») — os sinais vitais do voo num relance: bateria (SoC real
 * e estimado, tensão por célula, corrente, potência, autonomia até à reserva, alerta) e motores (rotação
 * média, quanto do teto de empuxo está a ser usado, brownout).
 *
 * Avaliação de UX de 2026-10-10: estes números só existiam por extenso na secção «Bordo» — a vigiar o voo
 * via-se apenas o selo pequeno do SoC na barra. O detalhe completo (curva de descarga, SoH, ciclos,
 * RECARREGAR/PACK NOVO, motor a motor, ledger) continua no «Bordo»: o botão leva lá.
 */

import { ArrowRight, Zap } from "lucide-react"

import { ProgressBar } from "@/components/motion-ui/progress-bar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ALERTA, alertaAtivo, IconeBateria } from "@/components/sim/bateria"
import {
  fmt,
  fmtPct,
  type BateriaTelemetria,
  type MotoresTelemetria,
  type PotenciaTelemetria,
} from "@/lib/sim"

/** Minutos → «1 h 32 min» / «45 min»; `null` → «—». */
export function fmtMinutos(min: number | null | undefined): string {
  if (min === null || min === undefined || !Number.isFinite(min)) return "—"
  const total = Math.max(0, Math.round(min))
  const h = Math.floor(total / 60)
  const m = total % 60
  return h > 0 ? `${h} h ${String(m).padStart(2, "0")} min` : `${m} min`
}

function Numero({
  rotulo,
  valor,
  detalhe,
  testid,
}: {
  rotulo: string
  valor: string
  detalhe?: string
  testid?: string
}) {
  return (
    <div className="flex min-w-0 flex-col" data-testid={testid}>
      <span className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
        {rotulo}
      </span>
      <span className="truncate font-mono text-sm font-medium tabular-nums">
        {valor}
      </span>
      {detalhe ? (
        <span className="truncate text-[0.65rem] text-muted-foreground">
          {detalhe}
        </span>
      ) : null}
    </div>
  )
}

export interface ResumoBordoProps {
  bateria: BateriaTelemetria | null
  motores: MotoresTelemetria | null
  potencia: PotenciaTelemetria | null
  /** Leva o dono à secção «Bordo» (detalhe completo). */
  onVerDetalhe?: () => void
}

export function ResumoBordo({
  bateria,
  motores,
  potencia,
  onVerDetalhe,
}: ResumoBordoProps) {
  const alerta = alertaAtivo(bateria)
  const soc = bateria?.soc ?? null
  const rpms = (motores?.rpm ?? []).filter((v): v is number => v !== null)
  const rpmMedio =
    rpms.length > 0 ? rpms.reduce((a, b) => a + b, 0) / rpms.length : null
  const empuxos = (motores?.empuxoN ?? []).filter(
    (v): v is number => v !== null
  )
  const usoTeto =
    motores?.tMaxN && motores.tMaxN > 0 && empuxos.length === 4
      ? empuxos.reduce((a, b) => a + b, 0) / (4 * motores.tMaxN)
      : null
  return (
    <Card className="gap-3" data-testid="resumo-bordo">
      <CardHeader className="gap-1">
        <CardTitle className="flex items-center justify-between gap-2 text-sm font-medium">
          <span className="flex items-center gap-1.5">
            <IconeBateria bateria={bateria} className="size-4" />
            Bateria e motores
          </span>
          {alerta ? (
            <span
              className={`rounded-full px-2 py-0.5 text-[0.65rem] ${ALERTA[alerta].classe}`}
            >
              {ALERTA[alerta].rotulo}
            </span>
          ) : bateria?.reformar ? (
            <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[0.65rem] text-destructive">
              REFORMAR
            </span>
          ) : null}
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          {alerta
            ? ALERTA[alerta].detalhe
            : "o pack persiste entre episódios (pousar não carrega)"}
          {bateria?.packId ? ` · ${bateria.packId}` : ""}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-end justify-between gap-3">
          <div className="flex flex-col">
            <span className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              carga (SoC)
            </span>
            <span
              className="text-3xl font-semibold tabular-nums"
              data-testid="resumo-soc"
            >
              {fmtPct(soc, 1)}
            </span>
            <span className="text-[0.65rem] text-muted-foreground">
              o RPi estima {fmtPct(bateria?.socEstimado ?? null, 1)}
            </span>
          </div>
          <div className="flex flex-col items-end text-right">
            <span className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              autonomia
            </span>
            <span
              className="text-lg font-semibold tabular-nums"
              data-testid="resumo-autonomia"
            >
              {fmtMinutos(bateria?.autonomiaMin)}
            </span>
            <span className="text-[0.65rem] text-muted-foreground">
              até à reserva de pouso
            </span>
          </div>
        </div>
        <ProgressBar
          value={soc ?? 0}
          size="md"
          highlight={alerta === null}
          tone={alerta === null ? undefined : "var(--destructive)"}
          progressbar
          aria-label="carga da bateria"
        />
        <div className="grid grid-cols-3 gap-2">
          <Numero
            rotulo="tensão"
            valor={
              bateria?.v === null || bateria?.v === undefined
                ? "—"
                : `${fmt(bateria.v, 1)} V`
            }
            detalhe={
              bateria?.vCelula == null
                ? undefined
                : `${fmt(bateria.vCelula, 2)} V por célula`
            }
            testid="resumo-tensao"
          />
          <Numero
            rotulo="corrente"
            valor={bateria?.i == null ? "—" : `${fmt(bateria.i, 1)} A`}
            detalhe={
              bateria?.tempC == null ? undefined : `${fmt(bateria.tempC, 1)} °C`
            }
          />
          <Numero
            rotulo="potência"
            valor={
              potencia?.total == null
                ? bateria?.p == null
                  ? "—"
                  : `${fmt(bateria.p, 0)} W`
                : `${fmt(potencia.total, 0)} W`
            }
            detalhe={
              potencia?.motores == null || potencia?.eletronica == null
                ? undefined
                : `${fmt(potencia.motores, 0)} W motores · ${fmt(potencia.eletronica, 1)} W bordo`
            }
          />
        </div>
        <div className="grid grid-cols-3 gap-2 border-t border-border pt-2">
          <Numero
            rotulo="rotação média"
            valor={rpmMedio === null ? "—" : `${fmt(rpmMedio, 0)} rpm`}
            detalhe={
              motores?.omegaMaxRpm == null
                ? undefined
                : `máx. ${fmt(motores.omegaMaxRpm, 0)} rpm agora`
            }
          />
          <Numero
            rotulo="uso do empuxo"
            valor={usoTeto === null ? "—" : fmtPct(usoTeto, 0)}
            detalhe="do teto atual (cai com a bateria)"
          />
          <Numero
            rotulo="motores"
            valor={
              motores?.brownout
                ? "BROWNOUT"
                : motores?.armado === false
                  ? "desarmados"
                  : motores?.armado
                    ? "armados"
                    : "—"
            }
            detalhe={
              motores?.brownout ? "tensão abaixo do mínimo do ESC" : undefined
            }
          />
        </div>
        {onVerDetalhe ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="self-end text-xs"
            onClick={onVerDetalhe}
            data-testid="resumo-ver-bordo"
          >
            <Zap aria-hidden="true" />
            curva de descarga, SoH, recarregar e motor a motor
            <ArrowRight aria-hidden="true" />
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}
