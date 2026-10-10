/**
 * Rede neural 16 → 64 → 64 → 4 ao vivo (cf2). Na planta real as dimensões saem dos dados: 21 obs do
 * ator e as camadas escondidas com o tamanho que o runner publicar.
 *
 * CASCATA, PASSO 4 (código novo, justificado): o catálogo não tem visualizador de ativações —
 * `sparkline`/`progress-bar` são séries e barras, não grelhas por camada com cor por |a|. Fica um SVG
 * pequeno (148 rects) porque o contrato só traz ATIVAÇÕES (`h1`/`h2`), não pesos: desenhar ligações
 * seria inventar arestas que o backend não manda. Cor = tokens semânticos via `color-mix(var(--primary)
 * | var(--destructive), var(--background))`; movimento só em `opacity` (regra 8 da skill).
 */

import { memo } from "react"
import { motion } from "motion/react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useMotionUITransition, useMotionUITheme } from "@/components/motion-ui/ui-theme"
import {
  corAtivacao,
  fmt,
  N_ACT,
  N_H1,
  N_H2,
  N_OBS,
  temAtivacoes,
  type LinhaSim,
} from "@/lib/sim"

const LADO = 16
const ALTURA_NO = 11
const ESPACO = 4
const TOPO = 18

interface Camada {
  chave: string
  rotulo: string
  dimensao: number
  valores: number[]
  colunas: number
}

function metricas(valores: number[]) {
  if (valores.length === 0) return { max: 0, media: 0 }
  let max = 0
  let soma = 0
  for (const v of valores) {
    const a = Math.abs(v)
    if (a > max) max = a
    soma += a
  }
  return { max, media: soma / valores.length }
}

interface NosProps {
  camada: Camada
  x: number
  y: number
}

/** Uma camada: grelha de rects, cor por |a| (normalizada ao máximo da própria camada). */
const Nos = memo(function Nos({ camada, x, y }: NosProps) {
  const ui = useMotionUITransition("ui")
  const { max } = metricas(camada.valores)
  return (
    <g>
      {camada.valores.map((valor, i) => {
        const coluna = i % camada.colunas
        const linha = Math.floor(i / camada.colunas)
        const forca = max > 0 ? Math.min(1, Math.abs(valor) / max) : 0
        const cx = x + coluna * (LADO + ESPACO)
        const cy = y + linha * (ALTURA_NO + ESPACO)
        return (
          <motion.rect
            key={i}
            x={cx}
            y={cy}
            width={LADO}
            height={ALTURA_NO}
            rx={2}
            initial={false}
            animate={{ opacity: 0.18 + 0.82 * forca }}
            transition={{ ...ui }}
            style={{ fill: corAtivacao(valor, max || 1) }}
          >
            <title>{`${camada.rotulo}[${i}] = ${fmt(valor, 4)}`}</title>
          </motion.rect>
        )
      })}
    </g>
  )
})

interface RedeProps {
  linha: LinhaSim | null
  estadoCorrendo: boolean
}

export function Rede({ linha, estadoCorrendo }: RedeProps) {
  const ui = useMotionUITransition("ui")
  const { motionMode } = useMotionUITheme()
  const comAtivacoes = temAtivacoes(linha)

  // Dimensões pelos DADOS: cf2 = 16 → 64 → 64 → 4 (o parser fixa-as); planta real = 21 obs do ator e as
  // camadas com o tamanho que o runner publicar (o ator real pode ser 128-128).
  const nObs = linha?.obs.length ?? N_OBS
  const nH1 = linha?.h1.length ?? N_H1
  const nH2 = linha?.h2.length ?? N_H2
  const camadas: Camada[] = [
    { chave: "obs", rotulo: "obs", dimensao: nObs, valores: linha?.obs ?? [], colunas: 2 },
    { chave: "h1", rotulo: "h1", dimensao: nH1, valores: linha?.h1 ?? [], colunas: 8 },
    { chave: "h2", rotulo: "h2", dimensao: nH2, valores: linha?.h2 ?? [], colunas: 8 },
    { chave: "act", rotulo: "act", dimensao: N_ACT, valores: linha?.act ?? [], colunas: 1 },
  ]

  const espacoCamada = 52
  const larguras = camadas.map((c) => c.colunas * LADO + (c.colunas - 1) * ESPACO)
  const alturas = camadas.map((c) => {
    const linhas = Math.ceil(c.dimensao / c.colunas)
    return linhas * ALTURA_NO + (linhas - 1) * ESPACO
  })
  const alturaMax = Math.max(...alturas)
  const larguraTotal =
    larguras.reduce((soma, l) => soma + l, 0) + espacoCamada * (camadas.length - 1) + 24
  const alturaTotal = TOPO + alturaMax + 26

  let cursor = 12
  const posicoes = camadas.map((_camada, i) => {
    const x = cursor
    cursor += larguras[i] + espacoCamada
    return { x, y: TOPO + (alturaMax - alturas[i]) / 2 }
  })

  const resumo = camadas
    .filter((c) => c.chave === "h1" || c.chave === "h2")
    .map((c) => ({ rotulo: c.rotulo, ...metricas(c.valores) }))

  return (
    <Card data-testid="painel-rede">
      <CardHeader className="gap-0.5">
        <CardTitle className="flex flex-wrap items-baseline justify-between gap-2 text-sm font-medium">
          <span>Rede da política · ativações ao vivo</span>
          <span className="font-mono text-[0.7rem] text-muted-foreground">
            {`${nObs} → ${nH1} → ${nH2} → ${N_ACT} · cor = |a| / máx da camada`}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          {comAtivacoes
            ? "primary = ativação positiva · destructive = negativa (tokens shadcn, sem hex)"
            : "o stream ainda não traz h1/h2 — as ativações aparecem quando o backend as publicar"}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <motion.div
          animate={{ opacity: estadoCorrendo ? 1 : 0.45 }}
          transition={{ ...ui }}
          className="overflow-x-auto"
        >
          <svg
            viewBox={`0 0 ${larguraTotal} ${alturaTotal}`}
            className="max-h-[300px] w-full min-w-[340px]"
            role="img"
            aria-label={`Ativações da rede por camada: ${nObs} observações, ${nH1}, ${nH2} e ${N_ACT} ações`}
            data-testid="svg-rede"
          >
            <text x={6} y={11} className="fill-muted-foreground" style={{ fontSize: 9 }}>
              entrada
            </text>
            {camadas.map((camada, i) => (
              <g key={camada.chave}>
                <rect
                  x={posicoes[i].x - 4}
                  y={posicoes[i].y - 4}
                  width={larguras[i] + 8}
                  height={alturas[i] + 8}
                  rx={6}
                  className="fill-muted/40 stroke-border"
                  strokeWidth={1}
                />
                <Nos camada={camada} x={posicoes[i].x} y={posicoes[i].y} />
                <text
                  x={posicoes[i].x + larguras[i] / 2}
                  y={TOPO + alturaMax + 16}
                  textAnchor="middle"
                  style={{ fontSize: 10 }}
                  className="fill-muted-foreground font-mono"
                >
                  {camada.rotulo} {camada.dimensao}
                </text>
                {i < camadas.length - 1 ? (
                  <motion.text
                    x={posicoes[i].x + larguras[i] + espacoCamada / 2}
                    y={alturaTotal / 2}
                    textAnchor="middle"
                    style={{ fontSize: 12 }}
                    className="fill-muted-foreground"
                    animate={
                      estadoCorrendo && motionMode === "full"
                        ? { opacity: [0.25, 1, 0.25] }
                        : { opacity: 0.5 }
                    }
                    transition={
                      estadoCorrendo && motionMode === "full"
                        ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" }
                        : { duration: 0.2 }
                    }
                  >
                    →
                  </motion.text>
                ) : null}
              </g>
            ))}
          </svg>
        </motion.div>

        <div
          className="grid gap-2 sm:grid-cols-2"
          data-testid="resumo-camadas"
        >
          {resumo.map((m) => (
            <div
              key={m.rotulo}
              className="flex items-baseline justify-between rounded-lg bg-muted/40 px-3 py-1.5 font-mono text-[0.7rem]"
            >
              <span className="text-muted-foreground">{m.rotulo}</span>
              <span>
                máx |a| {fmt(m.max, 3)} · média |a| {fmt(m.media, 3)}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
