/**
 * Cabeçalho: título, selo do estado do episódio, contadores (ep/passos/retorno), modelo e ligação.
 *
 * Composição (cascata, passo 3): `Card` + `AnimatedNumber` (veio com o `stats-live-panel`) e `motion`
 * para a troca de estado. O `stats-live-panel` em si não serve aqui — é uma demo fechada que gera os
 * próprios números de engagement (`eventsBaseline`/`tickIntervalMs`) e não aceita telemetria.
 */

import { useEffect, useState } from "react"
import { motion } from "motion/react"

import { AnimatedNumber } from "@/components/motion-ui/animated-number"
import {
  StaggerReveal,
  StaggerRevealHeadline,
  StaggerRevealItem,
} from "@/components/motion-ui/stagger-reveal"
import { Card } from "@/components/ui/card"
import { useMotionUITransition } from "@/components/motion-ui/ui-theme"
import {
  fmt,
  fmtInteiro,
  fmtSinal,
  nomeModeloLegivel,
  type EstadoEpisodio,
  type MotivoFim,
} from "@/lib/sim"
import type { Ligacao } from "@/hooks/use-sim"

interface SeloEstadoProps {
  estado: EstadoEpisodio
  aCorrer: boolean
  /** Porque fechou o episódio (`fim` da telemetria): só a QUEDA é alarme; o fim por tempo é normal. */
  fim?: MotivoFim | null
}

/**
 * Selo do episódio em linguagem simples. Avaliação de UX de 2026-10-10: «episodio_terminado» a vermelho
 * aparecia ao fim de 10 s com o drone a pairar normalmente (sem reinício, a física continua) — agora o
 * fim por TEMPO é neutro («episódio concluído · continua a voar») e só a QUEDA fica vermelha. Sem o motivo
 * (runner antigo) fica neutro: não se dá um alarme que a telemetria não sustenta.
 */
function SeloEstado({ estado, aCorrer, fim = null }: SeloEstadoProps) {
  const ui = useMotionUITransition("ui")
  const terminado = estado === "episodio_terminado"
  const queda = terminado && fim === "queda"
  const texto = !terminado
    ? "a voar · episódio a correr"
    : queda
      ? "caiu ou capotou — REINICIAR para voltar a voar"
      : "episódio concluído · a física continua"
  return (
    <motion.span
      layout
      transition={{ ...ui }}
      data-testid="selo-estado"
      data-estado={estado}
      data-fim={fim ?? ""}
      title={`estado do runner: ${estado}${fim ? ` (fim por ${fim})` : ""}`}
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
        queda
          ? "bg-destructive/10 text-destructive"
          : terminado
            ? "bg-muted text-foreground"
            : "bg-primary/10 text-primary"
      }`}
    >
      <motion.span
        aria-hidden="true"
        className={`size-2 rounded-full ${queda ? "bg-destructive" : terminado ? "bg-muted-foreground" : "bg-primary"}`}
        animate={terminado || !aCorrer ? { opacity: 1 } : { opacity: [1, 0.25, 1] }}
        transition={
          terminado || !aCorrer
            ? { duration: 0.2 }
            : { duration: 1.6, repeat: Infinity, ease: "easeInOut" }
        }
      />
      {texto}
    </motion.span>
  )
}

interface CabecalhoProps {
  estado: EstadoEpisodio
  ep: number
  passo: number
  retorno: number
  modelo: string | null
  ligacao: Ligacao
  atualizadoEm: number | null
  /** Subtítulo alternativo (planta real: build, obs do ator, ação ctbr); sem ele fica o do Crazyflie 2. */
  subtitulo?: string
  /** Motivo do fim do episódio (`fim` da última linha). */
  fim?: MotivoFim | null
}

function Contador({
  rotulo,
  valor,
  decimais = 0,
  sufixo,
  destaque = false,
}: {
  rotulo: string
  valor: number
  decimais?: number
  sufixo?: string
  destaque?: boolean
}) {
  return (
    <div className="flex min-w-24 flex-col gap-0.5">
      <span className="text-[0.7rem] tracking-wide text-muted-foreground uppercase">{rotulo}</span>
      {destaque ? (
        <AnimatedNumber
          value={valor}
          format={{ minimumFractionDigits: decimais, maximumFractionDigits: decimais }}
          className="text-lg font-semibold tabular-nums"
          suffix={sufixo}
        />
      ) : (
        <span className="text-lg font-semibold tabular-nums">
          {decimais > 0 ? fmtSinal(valor, decimais) : fmtInteiro(valor)}
          {sufixo ?? ""}
        </span>
      )}
    </div>
  )
}

export function Cabecalho({
  estado,
  ep,
  passo,
  retorno,
  modelo,
  ligacao,
  atualizadoEm,
  subtitulo,
  fim = null,
}: CabecalhoProps) {
  // `modelo` já vem do `modelo_nome` do /api/state (pasta/ficheiro.zip); o caminho ABSOLUTO nunca entra
  // no DOM — este é um rótulo de painel, não um explorador de ficheiros, e a página pode ser partilhada.
  const modeloLegivel = nomeModeloLegivel(modelo)
  const ligado = ligacao === "ligado"
  // «última há X s»: o relógio anda num efeito (1 Hz) — ler `Date.now()` durante o render é impuro
  const [agora, setAgora] = useState<number | null>(null)
  useEffect(() => {
    const id = window.setInterval(() => setAgora(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  const idade =
    atualizadoEm === null || agora === null ? null : Math.max(0, (agora - atualizadoEm) / 1000)

  return (
    <Card className="gap-3 px-4" data-testid="cabecalho">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <StaggerReveal className="flex min-w-0 flex-col gap-1">
          <StaggerRevealHeadline className="text-lg font-semibold tracking-tight">
            Drone a pairar · política ao vivo
          </StaggerRevealHeadline>
          <StaggerRevealItem as="p" className="text-xs text-muted-foreground">
            {subtitulo ??
              "Crazyflie 2 (MuJoCo 3.15) · obs 16 → 64 → 64 → 4 ações · alvo z = 1,0 m"}
          </StaggerRevealItem>
        </StaggerReveal>
        <div className="flex flex-wrap items-center gap-2">
          <SeloEstado estado={estado} aCorrer={ligado} fim={fim} />
          <span
            data-testid="selo-ligacao"
            className={`inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[0.7rem] ${
              ligado ? "text-muted-foreground" : "text-destructive"
            }`}
          >
            <span
              aria-hidden="true"
              className={`size-1.5 rounded-full ${ligado ? "bg-primary" : "bg-destructive"}`}
            />
            {ligado
              ? `API ligada${idade !== null && idade >= 2 ? ` · última há ${fmt(idade, 0)} s` : ""}`
              : ligacao === "a_ligar"
                ? "à espera da API…"
                : "API em baixo"}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <Contador rotulo="episódio" valor={ep} destaque />
        <Contador rotulo="passos" valor={passo} destaque />
        <Contador rotulo="retorno" valor={retorno} decimais={2} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-[0.7rem] tracking-wide text-muted-foreground uppercase">modelo</span>
          <span
            data-testid="nome-modelo"
            className="font-mono text-xs whitespace-nowrap"
            title={modeloLegivel ?? "modelo não anunciado pelo /api/state"}
          >
            {modeloLegivel ?? "— (o /api/state não anunciou modelo)"}
          </span>
        </div>
      </div>
    </Card>
  )
}
