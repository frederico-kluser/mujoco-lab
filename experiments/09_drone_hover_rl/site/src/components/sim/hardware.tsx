/**
 * Bloco «Hardware (peças reais)» da PLANTA REAL (secção «Bordo» e «Tudo»).
 *
 * Mostra o `hardware` do `GET /api/state` — o resumo do `hardware.json` que o treino grava ao lado do
 * modelo: o build, as peças (motor, hélice, célula/pack, frame, ESC) e os números derivados (massa, T/W,
 * pairagem, g/W, autonomia estimada, kf/kq e a origem deles, DR). É informação ESTÁTICA do modelo em uso:
 * a política foi treinada com estas peças. Sem a chave (ou `null`) diz-se isso e os valores ficam «—».
 *
 * Cascata: passo 3 — `Card`; passo 4 só nas linhas de especificação (o catálogo não tem cartão de
 * especificações — o mesmo caso do `rpi5.tsx`), com classes semânticas.
 */

import type { ReactNode } from "react"
import { Battery, Boxes, Cog, Cpu, Fan, Frame, Package } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  fmt,
  fmtExp,
  fmtInteiro,
  modoAcaoReal,
  rotuloQuimica,
  type Hardware,
} from "@/lib/sim"

interface PecaProps {
  icone: ReactNode
  rotulo: string
  valor: string | null
  detalhe?: string | null
  testid: string
}

/** Uma peça do build: ícone + papel + nome do fabricante/modelo (e um detalhe opcional). */
function Peca({ icone, rotulo, valor, detalhe, testid }: PecaProps) {
  return (
    <div className="flex min-w-0 items-start gap-1.5">
      <span
        className="mt-0.5 shrink-0 text-muted-foreground"
        aria-hidden="true"
      >
        {icone}
      </span>
      <div className="flex min-w-0 flex-col">
        <span className="text-[0.6rem] tracking-wide text-muted-foreground uppercase">
          {rotulo}
        </span>
        <span className="text-xs break-words" data-testid={testid}>
          {valor ?? "—"}
        </span>
        {detalhe ? (
          <span className="font-mono text-[0.6rem] break-words text-muted-foreground">
            {detalhe}
          </span>
        ) : null}
      </div>
    </div>
  )
}

interface NumeroProps {
  rotulo: string
  valor: string
  testid: string
  dica?: string
}

function Numero({ rotulo, valor, testid, dica }: NumeroProps) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5" title={dica}>
      <dt className="text-[0.6rem] tracking-wide text-muted-foreground uppercase">
        {rotulo}
      </dt>
      <dd className="font-mono text-sm tabular-nums" data-testid={testid}>
        {valor}
      </dd>
    </div>
  )
}

/** Texto do pack do build (`4S2P · Li-ion · 9,0 Ah · 133 Wh · 812 g · 164 Wh/kg · R₀ 21 mΩ`). */
function textoPack(hardware: Hardware | null): string | null {
  const b = hardware?.bateria ?? null
  if (b === null) return null
  const partes = [
    b.s === null || b.p === null ? null : `${fmt(b.s, 0)}S${fmt(b.p, 0)}P`,
    rotuloQuimica(b.quimica),
    b.ah === null ? null : `${fmt(b.ah, 1)} Ah`,
    b.wh === null ? null : `${fmt(b.wh, 0)} Wh`,
    b.massaG === null ? null : `${fmtInteiro(b.massaG)} g`,
    b.whKg === null ? null : `${fmt(b.whKg, 0)} Wh/kg`,
    b.r0Mohm === null ? null : `R₀ ${fmt(b.r0Mohm, 1)} mΩ`,
  ].filter((p): p is string => p !== null)
  return partes.length > 0 ? partes.join(" · ") : null
}

interface PainelHardwareProps {
  /** `hardware` do `/api/state`; `null` = o servidor não o publicou (ou ainda não respondeu). */
  hardware: Hardware | null
}

export function PainelHardware({ hardware }: PainelHardwareProps) {
  const h = hardware
  const modo = h?.modoAcao == null ? null : modoAcaoReal(h.modoAcao)
  const subtitulo = [
    h?.build ? `build ${h.build}` : null,
    modo === null
      ? null
      : modo === "ctbr"
        ? "ação ctbr (FC dedicado)"
        : "ação motores (sem FC)",
    h?.dr == null
      ? null
      : h.dr
        ? "treinada com domain randomization"
        : "treinada sem domain randomization",
  ]
    .filter((p): p is string => p !== null)
    .join(" · ")

  return (
    <Card className="gap-3" data-testid="painel-hardware">
      <CardHeader className="gap-1">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Boxes className="size-4" aria-hidden="true" />
          Hardware (peças reais)
          <span className="text-[0.7rem] font-normal text-muted-foreground">
            planta real
          </span>
        </CardTitle>
        <p
          className="text-[0.7rem] text-muted-foreground"
          data-testid="hardware-build"
        >
          {h === null
            ? "o /api/state não publicou o bloco `hardware` (o modelo em uso não tem `hardware.json` ao lado)"
            : subtitulo || "build sem identificação no `hardware.json`"}
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        <div className="grid grid-cols-1 gap-x-4 gap-y-2.5 sm:grid-cols-2 xl:grid-cols-3">
          <Peca
            icone={<Cog className="size-3.5" />}
            rotulo="motor"
            valor={h?.motor ?? null}
            testid="hardware-motor"
          />
          <Peca
            icone={<Fan className="size-3.5" />}
            rotulo="hélice"
            valor={h?.helice ?? null}
            testid="hardware-helice"
          />
          <Peca
            icone={<Battery className="size-3.5" />}
            rotulo="célula · pack"
            valor={h?.celula ?? null}
            detalhe={textoPack(h)}
            testid="hardware-celula"
          />
          <Peca
            icone={<Frame className="size-3.5" />}
            rotulo="frame"
            valor={h?.frame ?? null}
            testid="hardware-frame"
          />
          <Peca
            icone={<Cpu className="size-3.5" />}
            rotulo="ESC"
            valor={h?.esc ?? null}
            testid="hardware-esc"
          />
          <Peca
            icone={<Package className="size-3.5" />}
            rotulo="pack (id)"
            valor={h?.bateria?.id ?? null}
            testid="hardware-pack-id"
          />
        </div>

        <dl className="grid grid-cols-2 gap-x-3 gap-y-2.5 border-t border-border pt-3 sm:grid-cols-3 xl:grid-cols-4">
          <Numero
            rotulo="massa total"
            testid="hardware-massa"
            valor={
              h?.massaTotalG == null ? "—" : `${fmtInteiro(h.massaTotalG)} g`
            }
          />
          <Numero
            rotulo="T/W (cheia)"
            testid="hardware-tw"
            valor={h?.tW == null ? "—" : fmt(h.tW, 2)}
            dica="empuxo máximo dos 4 rotores com a bateria cheia ÷ peso"
          />
          <Numero
            rotulo="ω_max (cheia)"
            testid="hardware-omega-max"
            valor={
              h?.omegaMaxRpm == null ? "—" : `${fmtInteiro(h.omegaMaxRpm)} rpm`
            }
          />
          <Numero
            rotulo="pairagem"
            testid="hardware-pairagem"
            valor={h?.pPairagemW == null ? "—" : `${fmt(h.pPairagemW, 1)} W`}
            dica="potência elétrica total a pairar com a tensão nominal"
          />
          <Numero
            rotulo="eficiência"
            testid="hardware-g-por-w"
            valor={h?.gPorW == null ? "—" : `${fmt(h.gPorW, 2)} g/W`}
            dica="gramas levantadas por watt, a pairar"
          />
          <Numero
            rotulo="autonomia estimada"
            testid="hardware-autonomia"
            valor={
              h?.autonomiaMin == null ? "—" : `${fmt(h.autonomiaMin, 1)} min`
            }
            dica="estimativa do build (bancada), não a autonomia restante do voo"
          />
          <Numero
            rotulo="kf"
            testid="hardware-kf"
            valor={h?.kf == null ? "—" : `${fmtExp(h.kf, 3)} N/(rad/s)²`}
            dica="T = kf·ω² por rotor"
          />
          <Numero
            rotulo="kq"
            testid="hardware-kq"
            valor={h?.kq == null ? "—" : `${fmtExp(h.kq, 3)} N·m/(rad/s)²`}
            dica="binário de reação Q = kq·ω² por rotor"
          />
        </dl>
        <p
          className="font-mono text-[0.6rem] break-words text-muted-foreground"
          data-testid="hardware-origem-kf"
        >
          origem do kf/kq: {h?.origemKfKq ?? "—"}
        </p>

        <p
          className="border-t border-border/70 pt-2 text-[0.6rem] leading-snug text-muted-foreground"
          data-testid="hardware-nota"
        >
          as peças vêm do catálogo `models/drone_rpi/componentes.json` e das
          montagens `models/drone_rpi/builds.json`; troca-se de build com
          `experiments/09_drone_hover_rl/hardware.py usar &lt;build&gt;`. A
          política em uso foi treinada com ESTAS peças (o `hardware.json` ao
          lado do modelo) — outro build pede um treino novo.
        </p>
      </CardContent>
    </Card>
  )
}
