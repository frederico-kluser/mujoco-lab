/**
 * Painel do Raspberry Pi 5 — o "computador de bordo" do drone, com a imagem do dono e medidores AO VIVO.
 *
 * Todos os números vêm do backend (`rpi5` no `/api/sim` — ou, em reforço, no `/api/state`) e a procedência
 * é mostrada tal como ele a declara: **`proxy x86 calibrado`**, **`real`** ou **`sem benchmark`**. Com
 * `sem benchmark` (ou sem a chave) o painel NÃO inventa nada: mostra o estado, as características do alvo
 * que o backend anunciar e "—" nos medidores.
 *
 * IMAGEM: `src/assets/rpi5.webp` é a ilustração que o dono indicou
 * (`~/Imagens/Raspberry_Pi_B+_illustration.svg.webp`, 960×640 com alfa). É uma ilustração do
 * **Raspberry Pi Model B+ (2014)**, não do Pi 5 — por isso fica identificada como ilustração de
 * referência, com a atribuição (Lucasbosch, Wikimedia Commons, CC BY-SA 3.0), e é mostrada reduzida
 * (nunca ampliada, que num bitmap se nota).
 *
 * Semáforo de saúde (derivado, nunca inventado): ERROR quando o p99 passa o orçamento do ciclo,
 * WARN a partir de 70 % dele (pouca margem) e OK abaixo disso. Sem números ⇒ sem semáforo.
 *
 * Cascata: passo 3 — `Card` + `ProgressBar` (`@motion/progress-bar`, com `highlight`/`tone`) +
 * `AnimatedNumber`, mais a `<img>` do alvo. Passo 4 só no cartão de hardware e no semáforo (o catálogo
 * não tem cartão de especificações nem indicador de saúde ligado a telemetria), com classes semânticas.
 */

import type { ReactNode } from "react"
import { Cpu, HardDrive, MemoryStick, Radio, Timer } from "lucide-react"

import rpi5Url from "@/assets/rpi5.webp"
import { AnimatedNumber } from "@/components/motion-ui/animated-number"
import { ProgressBar } from "@/components/motion-ui/progress-bar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  budgetMs,
  fmt,
  fmtInteiro,
  fmtLatencia,
  pctDoBudget,
  type Rpi5,
  type TipoFonteRpi5,
} from "@/lib/sim"

/** Tom da barra quando o valor passa do orçamento (o `progress-bar` não sabe de limiares). */
const TOM_ALERTA = "color-mix(in srgb, var(--destructive) 72%, var(--card))"

/** Limiar de aviso: acima de 70 % do orçamento já há pouca margem para jitter. */
export const LIMIAR_AVISO_PCT = 70

/** Rótulo da procedência: o TEXTO é do backend (nunca reescrito); a cor vem do tipo classificado. */
const TOM_FONTE: Record<TipoFonteRpi5, string> = {
  real: "bg-primary/10 text-primary",
  proxy: "bg-secondary text-secondary-foreground",
  sem_benchmark: "bg-muted text-muted-foreground",
  outro: "bg-muted text-muted-foreground",
}

/** Texto de um número opcional (nunca "undefined"/"NaN" no DOM). */
function ouTraco(valor: string | null): string {
  return valor ?? "—"
}

type Saude = "ok" | "aviso" | "erro"

/** Saúde do tempo real a partir do p99 (e do pior caso) face ao orçamento do ciclo. */
export function saudeDoTempoReal(
  p99: number | null,
  max: number | null
): Saude | null {
  // O orçamento é de tempo real: conta o PIOR dos dois (a cauda p99 e o pior caso medido), não só a média.
  const valores = [p99, max].filter((v): v is number => v !== null)
  if (valores.length === 0) return null
  if (valores.some((v) => v > 100)) return "erro"
  return valores.some((v) => v > LIMIAR_AVISO_PCT) ? "aviso" : "ok"
}

const SELO_SAUDE: Record<
  Saude,
  { rotulo: string; classe: string; ponto: string }
> = {
  ok: {
    rotulo: "OK · dentro do orçamento",
    classe: "bg-primary/10 text-primary",
    ponto: "bg-primary",
  },
  aviso: {
    rotulo: "ATENÇÃO · pouca margem",
    classe: "bg-secondary text-secondary-foreground",
    ponto: "bg-muted-foreground",
  },
  erro: {
    rotulo: "ERRO · acima do orçamento",
    classe: "bg-destructive/10 text-destructive",
    ponto: "bg-destructive",
  },
}

interface MedidorProps {
  rotulo: string
  /** Percentagem (0–100+); `null` ⇒ "—" e barra vazia (sem número inventado). */
  pct: number | null
  detalhe: string
  testid: string
}

/** Medidor em percentagem: barra do catálogo + valor animado + legenda do que foi medido. */
function Medidor({ rotulo, pct, detalhe, testid }: MedidorProps) {
  const alerta = pct !== null && pct > 100
  const cheio = pct === null ? 0 : Math.min(1, Math.max(0, pct / 100))
  return (
    <div className="flex flex-col gap-1" data-testid={testid}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[0.7rem] text-muted-foreground">{rotulo}</span>
        <span
          className={`font-mono text-xs tabular-nums ${alerta ? "text-destructive" : ""}`}
        >
          {pct === null ? (
            "—"
          ) : (
            <AnimatedNumber
              value={pct}
              format={{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}
              suffix=" %"
            />
          )}
        </span>
      </div>
      <ProgressBar
        value={cheio}
        size="md"
        highlight={!alerta}
        tone={TOM_ALERTA}
        progressbar
        aria-label={rotulo}
      />
      <p className="font-mono text-[0.6rem] leading-tight text-muted-foreground">
        {detalhe}
      </p>
    </div>
  )
}

interface EspecificacaoProps {
  icone: ReactNode
  rotulo: string
  valor: string
  /** Identificador estável para os testes (o rótulo tem espaços/acentos e não serve de `data-testid`). */
  testid: string
}

function Especificacao({ icone, rotulo, valor, testid }: EspecificacaoProps) {
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
        <span
          className="font-mono text-[0.7rem] break-words"
          data-testid={testid}
        >
          {valor}
        </span>
      </div>
    </div>
  )
}

interface PainelRpi5Props {
  rpi5: Rpi5 | null
  /** `false` quando a API está em baixo (os medidores ficam a "—" e diz-se porquê). */
  ligado: boolean
}

export function PainelRpi5({ rpi5, ligado }: PainelRpi5Props) {
  const espec = rpi5?.specs ?? null
  const infer = rpi5?.inferencia ?? null
  const uso = rpi5?.uso ?? null
  const hardware = rpi5?.hardware ?? null

  const orcamento = rpi5 === null ? null : budgetMs(rpi5)
  const p50 = infer?.p50Us ?? null
  const p99 = infer?.p99Us ?? null
  const pior = infer?.maxUs ?? null
  // A barra é "p50 vs ORÇAMENTO por decisão" (p50 ÷ 20 ms) — derivada dos µs medidos, que existem sempre
  // que há benchmark; o `uso.pct_budget` do backend é p50 × decisões/s reais e vai a 0 quando o episódio
  // está parado, o que faria a barra mentir sobre o custo de UMA decisão.
  const pctP50 = pctDoBudget(p50, orcamento) ?? uso?.pctBudget ?? null
  const pctP99 = pctDoBudget(p99, orcamento)
  const fonte = rpi5?.fonte ?? "sem benchmark"
  // Sem `inferencia.p50_us` não há benchmark nenhum (o `sim_site.py` manda `inferencia: null`): o painel
  // diz isso e não inventa tempos. A frase da fonte é a do backend, mostrada tal e qual.
  const semBenchmark = rpi5 === null || !rpi5.temBenchmark
  const saude =
    semBenchmark || infer?.cabe50hz === false
      ? semBenchmark
        ? null
        : "erro"
      : saudeDoTempoReal(pctP99, pctDoBudget(pior, orcamento))
  const hz = espec?.hz ?? uso?.decisoesS ?? null
  const ram =
    espec?.ramTexto ??
    (espec?.ramGb == null ? null : `${fmt(espec.ramGb, 0)} GB`)

  return (
    <Card className="gap-3" data-testid="painel-rpi5">
      <CardHeader className="gap-1">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Cpu className="size-4" aria-hidden="true" />
          Raspberry Pi 5
          <span className="text-[0.7rem] font-normal text-muted-foreground">
            computador de bordo
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          inferência da política no alvo · orçamento{" "}
          {orcamento === null ? "—" : `${fmt(orcamento, 0)} ms`}{" "}
          {hz === null ? "@ 50 Hz" : `@ ${fmt(hz, 0)} Hz`} · atualiza com o
          polling (2,9 Hz)
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start gap-3">
          <img
            src={rpi5Url}
            alt="Ilustração de referência de um Raspberry Pi (Model B+)"
            width={144}
            height={96}
            loading="lazy"
            decoding="async"
            data-testid="imagem-rpi5"
            className="h-20 w-auto max-w-36 shrink-0 rounded-lg border border-border/70 bg-muted/30 object-contain p-1 sm:h-24"
          />
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <span
                data-testid="fonte-rpi5"
                title={fonte}
                className={`inline-flex w-fit max-w-full items-center gap-1.5 rounded-full px-2 py-0.5 text-[0.65rem] font-medium ${TOM_FONTE[rpi5?.tipoFonte ?? "sem_benchmark"]}`}
              >
                <Radio className="size-3 shrink-0" aria-hidden="true" />
                <span className="truncate">fonte: {fonte}</span>
              </span>
              {saude === null ? null : (
                <span
                  data-testid="saude-rpi5"
                  title={`p99 ${pctP99 === null ? "—" : `${fmt(pctP99, 1)} %`} do orçamento · aviso acima de ${fmt(LIMIAR_AVISO_PCT, 0)} % (p99 ou pior caso) e erro acima de 100 %`}
                  className={`inline-flex w-fit items-center gap-1.5 rounded-full px-2 py-0.5 text-[0.65rem] font-medium ${SELO_SAUDE[saude].classe}`}
                >
                  <span
                    aria-hidden="true"
                    className={`size-1.5 rounded-full ${SELO_SAUDE[saude].ponto}`}
                  />
                  {SELO_SAUDE[saude].rotulo}
                </span>
              )}
            </div>
            <p className="text-[0.65rem] leading-tight text-muted-foreground">
              {semBenchmark
                ? "sem benchmark publicado pelo backend: mostra-se o estado e as características do alvo, sem inventar tempos."
                : `medições ${rpi5?.tipoFonte === "real" ? "feitas no próprio Pi 5" : "de um proxy x86 calibrado"} — inferência da rede 16→64→64→4.`}
            </p>
            {infer?.modeloCoincide === false ? (
              <p
                className="text-[0.65rem] text-destructive"
                data-testid="rpi5-modelo-diferente"
              >
                atenção: o benchmark mediu OUTRO .zip — os tempos são de outra
                política.
              </p>
            ) : null}
            {!ligado ? (
              <p
                className="text-[0.65rem] text-destructive"
                data-testid="rpi5-sem-ligacao"
              >
                API em baixo: os medidores ficam a "—" até voltar a resposta.
              </p>
            ) : null}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-4">
          <Especificacao
            icone={<Cpu className="size-3.5" />}
            rotulo="CPU"
            testid="spec-cpu"
            valor={ouTraco(espec?.cpu ?? null)}
          />
          <Especificacao
            icone={<MemoryStick className="size-3.5" />}
            rotulo="RAM"
            testid="spec-ram"
            valor={ouTraco(ram)}
          />
          <Especificacao
            icone={<HardDrive className="size-3.5" />}
            rotulo="SoC"
            testid="spec-soc"
            valor={ouTraco(espec?.soc ?? null)}
          />
          <Especificacao
            icone={<Timer className="size-3.5" />}
            rotulo="budget / decisão"
            testid="spec-budget"
            valor={`${orcamento === null ? "—" : `${fmt(orcamento, 0)} ms`}${hz === null ? "" : ` · ${fmt(hz, 0)} Hz`}`}
          />
        </div>

        <div className="flex flex-col gap-3 border-t border-border pt-3 sm:grid sm:grid-cols-3 sm:gap-4">
          <Medidor
            rotulo="p50 vs budget"
            pct={pctP50}
            testid="medidor-p50"
            detalhe={
              p50 === null || orcamento === null
                ? "p50 — (sem medição)"
                : `p50 ${fmtLatencia(p50)} de ${fmt(orcamento, 0)} ms por decisão`
            }
          />
          <Medidor
            rotulo="p99 vs budget"
            pct={pctP99}
            testid="medidor-p99"
            detalhe={
              p99 === null || orcamento === null
                ? "p99 — (sem medição)"
                : `p99 ${fmtLatencia(p99)}${pctP99 !== null && pctP99 > 100 ? " · acima do orçamento!" : ""}`
            }
          />
          <Medidor
            rotulo="CPU equivalente"
            pct={uso?.pctCpuEquivalente ?? null}
            testid="medidor-cpu"
            detalhe={`latência estimada ${
              uso?.latenciaEstimadaUs == null
                ? "—"
                : `${fmtLatencia(uso.latenciaEstimadaUs)}`
            } · ${uso?.decisoesS == null ? "—" : fmt(uso.decisoesS, 0)} decisões/s`}
          />
        </div>

        <dl className="grid grid-cols-3 gap-x-3 gap-y-1 font-mono text-[0.65rem] sm:max-w-md">
          <dt className="text-muted-foreground">modelo</dt>
          <dd
            className="col-span-2 text-right tabular-nums"
            data-testid="rpi5-modelo"
          >
            {infer?.modeloKb == null ? "—" : `${fmtInteiro(infer.modeloKb)} KB`}
          </dd>
          <dt className="text-muted-foreground">fator int8</dt>
          <dd
            className="col-span-2 text-right tabular-nums"
            data-testid="rpi5-int8"
          >
            {infer?.int8Fator == null ? "—" : `×${fmt(infer.int8Fator, 2)}`}
          </dd>
          <dt className="text-muted-foreground">pior caso</dt>
          <dd
            className="col-span-2 text-right tabular-nums"
            data-testid="rpi5-pior-caso"
          >
            {fmtLatencia(pior)}
          </dd>
          <dt className="text-muted-foreground">núcleos multi-IA</dt>
          <dd
            className="col-span-2 text-right tabular-nums"
            data-testid="rpi5-multi-ia"
          >
            {uso?.nucleosMultiIa == null ? "—" : fmt(uso.nucleosMultiIa, 2)}
          </dd>
          <dt className="text-muted-foreground">núcleos · NPU</dt>
          <dd className="col-span-2 text-right" data-testid="rpi5-nucleos">
            {`${espec?.nucleos == null ? "—" : fmt(espec.nucleos, 0)} · ${ouTraco(espec?.npu ?? null)}`}
          </dd>
          <dt className="text-muted-foreground">estado do hardware</dt>
          <dd className="col-span-2 text-right" data-testid="rpi5-hardware">
            {hardware?.throttled || hardware?.tempC != null
              ? [
                  hardware.throttled,
                  hardware.tempC == null
                    ? null
                    : `${fmt(hardware.tempC, 1)} °C`,
                ]
                  .filter((v): v is string => v !== null && v.length > 0)
                  .join(" · ")
              : "sem hardware"}
          </dd>
        </dl>

        <p
          className="border-t border-border/70 pt-2 text-[0.6rem] leading-snug text-muted-foreground"
          data-testid="rpi5-nota"
        >
          {uso?.gargalo
            ? `gargalo (segundo o backend): ${uso.gargalo}`
            : "nota: no Pi 5 o gargalo do tempo real costuma ser o jitter do SO (kernel normal tem picos de milissegundos; um kernel PREEMPT_RT reduz-os muito) — a inferência da rede é bem mais barata que isso."}
          {uso?.jitterMsStandard != null && uso?.jitterUsPreemptRt != null
            ? ` · jitter: ${fmt(uso.jitterMsStandard, 1)} ms (kernel standard) vs ${fmt(uso.jitterUsPreemptRt, 0)} µs (PREEMPT_RT).`
            : ""}
          {espec?.throttle ? ` · throttling: ${espec.throttle}.` : ""} O estado
          do hardware só aparece se o backend publicar `vcgencmd
          get_throttled`/temperatura; sem isso diz-se «sem hardware», sem
          inventar.
        </p>
        <p className="text-[0.6rem] leading-snug text-muted-foreground">
          imagem: ilustração de referência (Raspberry Pi Model B+, não Pi 5) —
          Lucasbosch, Wikimedia Commons, CC BY-SA 3.0.
        </p>
      </CardContent>
    </Card>
  )
}
