/**
 * cabecalho.tsx — estado do episódio, contadores, modelo em uso e ligação ao backend.
 *
 * Usa `stagger-reveal` (entrada do título) e `animated-number` (contadores). O nome do modelo é mostrado
 * como `pasta/ficheiro.zip` (nunca o caminho absoluto): é um rótulo de painel, não um explorador de ficheiros.
 */

import { AnimatedNumber } from "@/components/motion-ui/animated-number"
import { StaggerReveal, StaggerRevealHeadline, StaggerRevealItem } from "@/components/motion-ui/stagger-reveal"
import { Card } from "@/components/ui/card"
import type { Ligacao } from "@/hooks/use-sim"
import { NOME_EXPERIMENTO, fmt, fmtInteiro, nomeModeloLegivel, type ResumoEstado } from "@/lib/sim"

const COR_LIGACAO: Record<Ligacao, string> = {
  a_ligar: "text-muted-foreground",
  ligado: "text-emerald-400",
  sem_ligacao: "text-rose-400",
}

const TEXTO_LIGACAO: Record<Ligacao, string> = {
  a_ligar: "a ligar…",
  ligado: "ligado",
  sem_ligacao: "sem ligação",
}

const TEXTO_ESTADO: Record<string, string> = {
  a_correr: "a correr",
  pausado: "em pausa",
  episodio_terminado: "episódio terminado — clica REINICIAR",
  sem_dados: "sem dados",
}

function Contador({ rotulo, valor, casas = 0 }: { rotulo: string; valor: number | null; casas?: number }) {
  return (
    <StaggerRevealItem className="flex flex-col">
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{rotulo}</span>
      <span className="text-lg font-semibold tabular-nums">
        {valor === null ? "—" : casas > 0
          ? <AnimatedNumber value={valor} format={{ minimumFractionDigits: casas, maximumFractionDigits: casas }} />
          : <AnimatedNumber value={valor} format={{ maximumFractionDigits: 0 }} />}
      </span>
    </StaggerRevealItem>
  )
}

export function Cabecalho({ resumo, estado, ep, passo, retorno, ligacao, atualizadoEm }: {
  resumo: ResumoEstado | null
  estado: string
  ep: number | null
  passo: number | null
  retorno: number | null
  ligacao: Ligacao
  atualizadoEm: number | null
}) {
  const modelo = nomeModeloLegivel(resumo?.modelo_nome ?? null) ?? "trim (sem política)"
  const idade = atualizadoEm === null ? null : Math.max(0, (Date.now() - atualizadoEm) / 1000)
  return (
    <Card className="gap-3 py-4">
      <StaggerReveal className="px-4">
        <StaggerRevealHeadline as="h1" className="text-xl font-semibold">
          {`${NOME_EXPERIMENTO} — padrão janela limpa + site`}
        </StaggerRevealHeadline>
        <div className="mt-3 flex flex-wrap items-end gap-x-8 gap-y-3">
          <Contador rotulo="episódio" valor={ep} />
          <Contador rotulo="passo" valor={passo} />
          <Contador rotulo="retorno" valor={retorno} casas={1} />
          <Contador rotulo="reinícios" valor={resumo?.contador_reiniciar ?? null} />
          <Contador rotulo="amostras" valor={resumo?.n_linhas ?? null} />
          <StaggerRevealItem className="flex flex-col">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">estado</span>
            <span className="text-sm font-medium">{TEXTO_ESTADO[estado] ?? estado}</span>
          </StaggerRevealItem>
          <StaggerRevealItem className="flex flex-col">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">política</span>
            <span className="max-w-[22rem] truncate text-sm font-medium" title={resumo?.modelo_nome ?? undefined}>
              {modelo}
            </span>
          </StaggerRevealItem>
          <StaggerRevealItem className="flex flex-col">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">ligação</span>
            <span className={`text-sm font-medium ${COR_LIGACAO[ligacao]}`}>
              {TEXTO_LIGACAO[ligacao]}
              {ligacao === "ligado" && idade !== null ? ` · ${fmt(idade, 0)} s` : ""}
            </span>
          </StaggerRevealItem>
          <StaggerRevealItem className="flex flex-col">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">LOOP</span>
            <span className="text-sm font-medium">{resumo?.loop === null || resumo?.loop === undefined ? "—" : resumo.loop ? "ligado" : "desligado"}</span>
          </StaggerRevealItem>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          A janela do MuJoCo mostra <strong>só a simulação</strong>; todas as métricas e controlos estão aqui.
          O site <strong>nunca reinicia sozinho</strong>: no fim do episódio a física congela até clicares REINICIAR
          (ou ligares o LOOP). Passo {fmtInteiro(passo)} · amostras no ficheiro de telemetria: {fmtInteiro(resumo?.n_linhas ?? null)}
        </p>
      </StaggerReveal>
    </Card>
  )
}
