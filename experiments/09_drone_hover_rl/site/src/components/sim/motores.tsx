/**
 * Bloco «Motores e potência» da PLANTA REAL (secção «Bordo» e «Tudo»).
 *
 * Os 4 rotores em VISTA DE CIMA (frente para cima: r1 frente-esq · r4 frente-dir · r3 trás-esq · r2
 * trás-dir), cada um com rpm, duty do ESC, empuxo (N), corrente de fase (A), o sentido de rotação
 * (r1/r2 CW, r3/r4 CCW — diagonais iguais) e o fator aerodinâmico κ_T (efeito de solo × inflow × VRS);
 * o TETO atual de rotação/empuxo e quanto dele resta face à bateria cheia (`t_max_frac`: ω_max ∝ V, logo
 * o teto decai com a descarga); e o LEDGER de potência (motores · eletrónica = consumidores de 5 V +
 * perdas do BEC · total). Tudo de `motores`/`potencia`/`aero` da última linha; o que faltar fica «—».
 *
 * Cascata: passo 3 — `Card` + `ProgressBar` (com `referenceTick` no empuxo de pairagem m·g/4 quando o
 * `/api/state` anuncia a massa). Passo 4 só no arranjo 2×2 dos rotores (grelha com classes semânticas):
 * o catálogo não tem um diagrama de frame, e a posição de cada rotor é informação (não decoração).
 */

import { RotateCcw, RotateCw, Zap } from "lucide-react"

import { ProgressBar } from "@/components/motion-ui/progress-bar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ALTURA_SEM_SOLO_M,
  fmt,
  fmtInteiro,
  fmtPct,
  GRAVIDADE,
  modoAcaoReal,
  rotuloConsumidor,
  ROTORES_REAIS,
  ROTORES_VISTA_DE_CIMA,
  type AeroTelemetria,
  type Hardware,
  type MotoresTelemetria,
  type PotenciaTelemetria,
  type RotorReal,
} from "@/lib/sim"

/** Tom das barras quando passam do teto (o `progress-bar` não sabe de limiares). */
const TOM_ALERTA = "color-mix(in srgb, var(--destructive) 72%, var(--card))"

/** Watts com casas legíveis: ≥ 1 W com 2 casas, abaixo disso 3 (o IMU gasta 0,017 W). */
function fmtW(w: number | null | undefined): string {
  if (w === null || w === undefined || !Number.isFinite(w)) return "—"
  return `${fmt(w, Math.abs(w) >= 1 ? 2 : 3)} W`
}

/** Fração segura para uma barra (0 sem dados; nunca NaN). */
function fracao(valor: number | null, maximo: number | null): number {
  if (valor === null || maximo === null || maximo <= 0) return 0
  return Math.max(0, Math.min(1, valor / maximo))
}

interface TileRotorProps {
  rotor: RotorReal
  motores: MotoresTelemetria | null
  aero: AeroTelemetria | null
  /** Empuxo de pairagem POR ROTOR (m·g/4, N) — traço de referência; `null` sem a massa do build. */
  tPairagem: number | null
}

function TileRotor({ rotor, motores, aero, tPairagem }: TileRotorProps) {
  const i = rotor.indice
  const rpm = motores?.rpm[i] ?? null
  const duty = motores?.duty[i] ?? null
  const empuxo = motores?.empuxoN[i] ?? null
  const iFase = motores?.iFase[i] ?? null
  const tMax = motores?.tMaxN ?? null
  const kappa = aero?.kappaT[i] ?? null
  const altura = aero?.alturaRotores[i] ?? null
  const semChao = altura !== null && altura >= ALTURA_SEM_SOLO_M - 1e-6
  const Sentido = rotor.sentido === "CW" ? RotateCw : RotateCcw
  const noTeto = empuxo !== null && tMax !== null && empuxo >= tMax * 0.995

  return (
    <div
      data-testid={`rotor-${rotor.nome}`}
      className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-border/70 bg-muted/20 p-2.5"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-mono text-xs font-medium">
          {rotor.nome}{" "}
          <span className="font-normal text-muted-foreground">
            · {rotor.posicao}
          </span>
        </span>
        <span
          className="inline-flex shrink-0 items-center gap-1 font-mono text-[0.65rem] text-muted-foreground"
          title={`gira no sentido ${rotor.sentido === "CW" ? "horário" : "anti-horário"} visto de cima`}
          data-testid={`rotor-${rotor.nome}-sentido`}
        >
          <Sentido className="size-3.5" aria-hidden="true" />
          {rotor.sentido}
        </span>
      </div>

      <span className="flex items-baseline gap-1">
        <span className="font-mono text-lg font-semibold tabular-nums">
          {fmtInteiro(rpm)}
        </span>
        <span className="text-[0.65rem] text-muted-foreground">rpm</span>
      </span>

      <ProgressBar
        value={duty ?? 0}
        size="sm"
        highlight
        progressbar
        aria-label={`duty do ESC de ${rotor.nome}`}
        label={
          <span className="text-[0.65rem] text-muted-foreground">duty</span>
        }
        valueLabel={
          <span className="font-mono text-[0.65rem] tabular-nums">
            {fmtPct(duty, 1)}
          </span>
        }
      />
      <ProgressBar
        value={fracao(empuxo, tMax)}
        referenceTick={
          tPairagem === null || tMax === null || tMax <= 0
            ? undefined
            : Math.min(1, tPairagem / tMax)
        }
        size="sm"
        highlight={!noTeto}
        tone={TOM_ALERTA}
        progressbar
        aria-label={`empuxo de ${rotor.nome} face ao teto atual`}
        label={
          <span className="text-[0.65rem] text-muted-foreground">empuxo</span>
        }
        valueLabel={
          <span
            className={`font-mono text-[0.65rem] tabular-nums ${noTeto ? "text-destructive" : ""}`}
          >
            {fmt(empuxo, 2)} N
          </span>
        }
      />

      <dl className="grid grid-cols-3 gap-x-2 font-mono text-[0.6rem]">
        <dt className="text-muted-foreground">I fase</dt>
        <dt
          className="text-muted-foreground"
          title="κ_T = efeito de solo × inflow × VRS (1 = ar livre)"
        >
          κ_T
        </dt>
        <dt
          className="text-muted-foreground"
          title="altura do rotor ao chão (raio para baixo)"
        >
          ao chão
        </dt>
        <dd className="tabular-nums">{fmt(iFase, 1)} A</dd>
        <dd className="tabular-nums" data-testid={`rotor-${rotor.nome}-kappa`}>
          {fmt(kappa, 3)}
        </dd>
        <dd className="tabular-nums">
          {semChao ? "sem chão" : altura === null ? "—" : `${fmt(altura, 2)} m`}
        </dd>
      </dl>
    </div>
  )
}

interface LinhaLedgerProps {
  rotulo: string
  w: number | null
  total: number | null
  testid: string
  /** Linha de soma (sem barra, em destaque). */
  soma?: boolean
}

function LinhaLedger({
  rotulo,
  w,
  total,
  testid,
  soma = false,
}: LinhaLedgerProps) {
  const parte = w !== null && total !== null && total > 0 ? w / total : null
  return (
    <div
      className={`grid grid-cols-[minmax(0,1fr)_5.5rem_3.5rem] items-center gap-x-2 ${soma ? "border-t border-border pt-1.5 font-medium" : ""}`}
      data-testid={testid}
    >
      <span className="flex min-w-0 flex-col gap-1">
        <span className="truncate text-xs">{rotulo}</span>
        {soma ? null : <ProgressBar value={parte ?? 0} size="sm" highlight />}
      </span>
      <span className="text-right font-mono text-xs tabular-nums">
        {fmtW(w)}
      </span>
      <span className="text-right font-mono text-[0.65rem] text-muted-foreground tabular-nums">
        {soma ? "" : parte === null ? "—" : fmtPct(parte, 1)}
      </span>
    </div>
  )
}

interface PainelMotoresProps {
  motores: MotoresTelemetria | null
  potencia: PotenciaTelemetria | null
  aero: AeroTelemetria | null
  /** Peças do build (`/api/state`): a massa dá o traço de pairagem m·g/4 nas barras de empuxo. */
  hardware: Hardware | null
  /** `false` com a API em baixo (os valores ficam os da última leitura e diz-se porquê). */
  ligado: boolean
}

export function PainelMotores({
  motores,
  potencia,
  aero,
  hardware,
  ligado,
}: PainelMotoresProps) {
  const massaKg =
    hardware?.massaTotalG == null ? null : hardware.massaTotalG / 1000
  const tPairagem = massaKg === null ? null : (massaKg * GRAVIDADE) / 4
  const tMax = motores?.tMaxN ?? null
  const tMaxFrac = motores?.tMaxFrac ?? null
  const somaEmpuxo = motores?.empuxoN.every((t) => t !== null)
    ? motores.empuxoN.reduce<number>((s, t) => s + (t ?? 0), 0)
    : null
  const p = potencia
  const soma5v =
    p === null || p.consumidores5v.length === 0
      ? null
      : p.consumidores5v.reduce((s, c) => s + c.w, 0)

  return (
    <Card className="gap-3" data-testid="painel-motores">
      <CardHeader className="gap-1">
        <CardTitle className="flex flex-wrap items-center gap-2 text-sm font-medium">
          <Zap className="size-4" aria-hidden="true" />
          Motores e potência
          <span className="text-[0.7rem] font-normal text-muted-foreground">
            planta real
          </span>
          <span className="ml-auto flex flex-wrap items-center gap-1.5">
            {motores?.armado == null ? null : (
              <span
                data-testid="motores-armado"
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-[0.65rem] font-medium ${
                  motores.armado
                    ? "bg-primary/10 text-primary"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {motores.armado ? "ESC ARMADO" : "ESC DESARMADO"}
              </span>
            )}
            {motores?.brownout ? (
              <span
                data-testid="motores-brownout"
                role="status"
                title="a tensão do barramento caiu abaixo do limite: BEC/ESC desligaram e o drone cai"
                className="inline-flex items-center rounded-full bg-destructive px-2 py-0.5 text-[0.65rem] font-semibold text-background"
              >
                BROWNOUT
              </span>
            ) : null}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          {motores?.brownout
            ? "brownout: a tensão caiu abaixo do limite do BEC/ESC — os motores desligaram e o drone cai pela física"
            : motores?.brownout === false
              ? modoAcaoReal(hardware?.modoAcao) === "motores"
                ? "sem brownout · ação motores: a política comanda os 4 aceleradores diretamente (sem FC)"
                : "sem brownout · ação ctbr: o FC dedicado fecha a malha de taxa e mistura coletivo + taxas nos 4 ESCs a 500 Hz"
              : "à espera do bloco `motores` da telemetria"}
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        {!ligado ? (
          <p
            className="text-[0.65rem] text-destructive"
            data-testid="motores-sem-ligacao"
          >
            API em baixo: os valores são os da última leitura.
          </p>
        ) : null}

        {/* TETO de rotação/empuxo — decai com a tensão da bateria */}
        <div
          className="flex flex-col gap-1.5 rounded-lg bg-muted/40 px-3 py-2"
          data-testid="motores-teto"
        >
          <ProgressBar
            value={tMaxFrac ?? 0}
            highlight
            progressbar
            aria-label="teto de empuxo atual face ao da bateria cheia"
            label={
              <span className="text-xs">teto de empuxo vs bateria cheia</span>
            }
            valueLabel={
              <span className="font-mono text-sm tabular-nums">
                {fmtPct(tMaxFrac, 1)}
              </span>
            }
          />
          <p className="font-mono text-[0.65rem] text-muted-foreground tabular-nums">
            ω_max {fmtInteiro(motores?.omegaMaxRpm ?? null)} rpm · T_max{" "}
            {fmt(tMax, 2)} N por rotor (×4 ={" "}
            {tMax === null ? "—" : fmt(4 * tMax, 1)} N) · agora Σ{" "}
            {fmt(somaEmpuxo, 2)} N
            {massaKg === null
              ? ""
              : ` · peso m·g = ${fmt(massaKg * GRAVIDADE, 2)} N`}
          </p>
          <p className="text-[0.6rem] leading-snug text-muted-foreground">
            o teto de rotação/empuxo decai com a tensão da bateria: ω_max ∝ V
            (KV) e T_max = kf·ω_max², logo a descarga (e o desgaste, que sobe o
            R₀ e afunda a tensão sob carga) tira empuxo máximo ao drone.
          </p>
        </div>

        {/* os 4 rotores em VISTA DE CIMA, frente para cima */}
        <div className="flex flex-col gap-1">
          <p className="text-center text-[0.6rem] tracking-wide text-muted-foreground uppercase">
            ↑ frente · vista de cima
          </p>
          <div className="grid grid-cols-2 gap-2" data-testid="motores-rotores">
            {ROTORES_VISTA_DE_CIMA.map((i) => (
              <TileRotor
                key={ROTORES_REAIS[i].nome}
                rotor={ROTORES_REAIS[i]}
                motores={motores}
                aero={aero}
                tPairagem={tPairagem}
              />
            ))}
          </div>
          <p className="text-[0.6rem] leading-snug text-muted-foreground">
            barra do empuxo = fração do teto atual
            {tPairagem === null
              ? ""
              : ` · traço = pairagem (m·g/4 = ${fmt(tPairagem, 2)} N por rotor)`}{" "}
            · κ_T = efeito de solo × inflow × VRS (1 = ar livre; &gt; 1 perto do
            chão) · CW/CCW visto de cima, diagonais iguais.
          </p>
        </div>

        {/* LEDGER de potência */}
        <section
          aria-label="ledger de potência"
          className="flex flex-col gap-1.5 border-t border-border pt-3"
          data-testid="motores-ledger"
        >
          <h4 className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
            ledger de potência
          </h4>
          <LinhaLedger
            rotulo="motores"
            w={p?.motores ?? null}
            total={p?.total ?? null}
            testid="ledger-motores"
          />
          <LinhaLedger
            rotulo="eletrónica (5 V + perdas do BEC)"
            w={p?.eletronica ?? null}
            total={p?.total ?? null}
            testid="ledger-eletronica"
          />
          <div
            className="ml-3 flex flex-col gap-1 border-l border-border pl-3"
            data-testid="ledger-consumidores"
          >
            <span className="text-[0.6rem] text-muted-foreground">
              consumidores de 5 V (Σ {fmtW(soma5v)}) · perdas do BEC{" "}
              <span className="font-mono">{fmtW(p?.becPerdas ?? null)}</span>
            </span>
            {p === null || p.consumidores5v.length === 0 ? (
              <span className="text-[0.6rem] text-muted-foreground">—</span>
            ) : (
              <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-0.5 text-[0.65rem] sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto]">
                {p.consumidores5v.map((c) => (
                  <div key={c.id} className="contents">
                    <dt className="truncate" title={c.id}>
                      {rotuloConsumidor(c.id)}{" "}
                      <span className="font-mono text-muted-foreground">
                        {c.id}
                      </span>
                    </dt>
                    <dd className="text-right font-mono tabular-nums">
                      {fmtW(c.w)}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
          <LinhaLedger
            rotulo="total (pack)"
            w={p?.total ?? null}
            total={p?.total ?? null}
            testid="ledger-total"
            soma
          />
        </section>
      </CardContent>
    </Card>
  )
}
