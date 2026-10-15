/**
 * «QUEM FAZ O QUÊ» (secção «Operação» e «Tudo») — a tabela das quatro peças da pilha de bordo, por
 * modo, com as latências MEDIDAS (ou ditas «estimado») e o semáforo do orçamento.
 *
 * As quatro linhas (contrato r12, pedido do dono «ver no site quem faz o quê»):
 *  · FC — FC H7, NÃO-IA, 500 Hz (laço de taxa + mistura): determinístico nos dois modos;
 *  · Controlador — RL: a IA-1 (PPO, 50 Hz) com a latência medida no deploy; CLÁSSICO: a cascata C++
 *    do firmware (50 Hz) com os números ESTIMADOS (llvm-mca/QEMU — o README do firmware diz as
 *    ressalvas; só um DWT numa placa fecha);
 *  · Perceção — RL: a IA-2 «seguimento» (25 Hz, medida; pode não existir — diz-se); CLÁSSICO: o
 *    detetor + IBVS C++ (25–30 Hz, estimado) com a latência da câmara (21 ms DCMI / 116 ms Pi);
 *  · Estimador — o estimador de bordo clássico (500 Hz), NÃO-IA nos dois modos.
 *
 * Os dados vêm de `linhasQuemFazOQue` (`lib/controlador.ts`, puro e testado) — aqui só se desenha.
 */

import { Waypoints } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  linhasQuemFazOQue,
  type ControladorEstado,
  type CustoIa,
} from "@/lib/controlador"

export interface QuemFazOQueProps {
  /** Bloco `controlador` (r12) — decide as linhas dinâmicas (RL × clássico); `null` = sem bloco. */
  controlador: ControladorEstado | null
  /** Custo multi-IA do `rpi5.multi_ia` (`null` = sem cascata — as latências dizem «—»). */
  multiIa: CustoIa | null
}

/**
 * Semáforo do orçamento (o mesmo do painel RPi 5): OK · ATENCAO · ERRO. Sem medição (a cascata clássica
 * a voar, ou o histórico parado) NÃO se desenha: um selo «sem dados» ao lado do título lia-se como uma
 * avaria (revisão de UX de 2026-10-12).
 */
function Semaforo({ valor }: { valor: string | null }) {
  if (valor === null || valor === "sem dados") return null
  return (
    <span
      className="rounded-full bg-muted px-2 py-0.5 text-[0.68rem] tabular-nums"
      data-testid="quem-faz-o-que-semaforo"
      data-semaforo={valor}
    >
      {valor}
    </span>
  )
}

export function QuemFazOQue({ controlador, multiIa }: QuemFazOQueProps) {
  const linhas = linhasQuemFazOQue(controlador, multiIa)
  return (
    <Card className="gap-3" data-testid="quem-faz-o-que">
      <CardHeader className="gap-1">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm font-medium">
          <span className="flex items-center gap-1.5">
            <Waypoints className="size-4" aria-hidden="true" />
            Quem faz o quê (pilha de bordo)
          </span>
          <Semaforo valor={multiIa?.semaforo ?? null} />
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          as quatro peças do laço de bordo, por modo — o que é IA e o que é
          clássico, a taxa de cada um e a latência medida (ou estimada, sempre
          dito). O FC (500 Hz) e o estimador nunca são IA.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <ul className="flex flex-col gap-1.5">
          {linhas.map((linha) => (
            <li
              key={linha.id}
              data-testid={`quem-faz-o-que-${linha.id}`}
              data-origem={linha.origem}
              className="rounded-lg bg-muted/40 px-3 py-2 text-[0.72rem]"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                <span className="font-medium text-foreground">
                  {linha.papel}
                  <span className="ml-2 font-normal text-muted-foreground">
                    {linha.quem}
                  </span>
                </span>
                <span className="tabular-nums text-muted-foreground">
                  {linha.taxa} · {linha.latencia_texto}
                  {linha.origem === "estimado" ? (
                    <span className="ml-1 rounded bg-muted px-1 py-0.5 text-[0.62rem]">
                      estimado
                    </span>
                  ) : null}
                </span>
              </div>
              <p className="mt-0.5 text-[0.65rem] text-muted-foreground">
                {linha.nota}
              </p>
            </li>
          ))}
        </ul>
        <p className="text-[0.65rem] text-muted-foreground">
          orçamento: 20 ms por decisão (50 Hz) para as IAs — o semáforo compara o
          p99 da soma com o período; 2 ms por passo (500 Hz) para o FC. Números
          «estimado»: llvm-mca/QEMU sobre o código do firmware (ver
          firmware/README.md); «medido»: inferências reais no deploy.
        </p>
      </CardContent>
    </Card>
  )
}
