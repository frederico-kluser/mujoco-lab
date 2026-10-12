/**
 * SELETOR DE CONTROLADOR (contrato r12, secção «Operação» e «Tudo») — RL (IA-1) × CLÁSSICO (cascata
 * C++ do firmware), trocável AO VIVO pelo `POST /api/controlador`.
 *
 * Decisões de UX (honestidade acima de tudo):
 *  · o toggle segmentado manda `{"modo"}` e mostra o MODO EM VIGOR (eco do runner), não o clicado:
 *    durante a troca o painel diz «a trocar…» (`controlador.estado = "trocando"`) com o MOTIVO
 *    («o episódio reinicia — calibração do giroscópio») e desativa o seletor;
 *  · um pedido RECUSADO (`estado: "erro"`, ex. clássico com planta cf2) mostra o motivo e NUNCA
 *    finge que trocou;
 *  · a `fonte` (quem voa) e o `v_ref_fonte` (de onde vem a velocidade comandada) estão sempre à
 *    vista — é o resumo do painel «Quem faz o quê» ao lado.
 */

import { useCallback } from "react"
import { Cpu } from "lucide-react"

import type { TomAviso } from "@/components/sim/avisos"
import { FOCUS_RING } from "@/components/sim/estilo"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  corpoControlador,
  type ControladorEstado,
  type ModoControlador,
} from "@/lib/controlador"

export interface ControladorProps {
  /** Bloco `controlador` do `/api/sim`/`/api/state` (r12); `null` = backend sem o bloco. */
  controlador: ControladorEstado | null
  /** `POST /api/controlador` (pela fila dos controlos + releitura do `/api/sim`). */
  definirControlador: (modo: ModoControlador) => Promise<void>
  /** O polling está a receber respostas (para o aviso de «API em baixo»). */
  ligado: boolean
  onAviso: (texto: string, tom: TomAviso) => void
}

/** Texto do estado honesto da troca (`pronto` · `trocando` · `erro` · `desconhecido`). */
export function textoEstadoControlador(estado: string | null): string {
  switch (estado) {
    case "pronto":
      return "pronto"
    case "trocando":
      return "a trocar…"
    case "erro":
      return "pedido recusado"
    default:
      return "—"
  }
}

export function ControladorCard({
  controlador,
  definirControlador,
  ligado,
  onAviso,
}: ControladorProps) {
  const modo: ModoControlador = controlador?.modo ?? "rl"
  const estado = controlador?.estado ?? "desconhecido"
  const trocando = estado === "trocando"
  const recusado = estado === "erro"

  const escolher = useCallback(
    (alvo: ModoControlador) => {
      if (alvo === modo || trocando) return
      void (async () => {
        try {
          await definirControlador(corpoControlador(alvo).modo)
          onAviso(
            alvo === "classico"
              ? "controlador CLÁSSICO pedido — o runner troca e o episódio reinicia (calibração do giroscópio)"
              : "controlador RL pedido — a política volta a pilotar (episódio novo)",
            "info"
          )
        } catch (erro) {
          onAviso(
            `POST /api/controlador falhou — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
            "erro"
          )
        }
      })()
    },
    [definirControlador, modo, onAviso, trocando]
  )

  return (
    <Card className="gap-3" data-testid="seletor-controlador">
      <CardHeader className="gap-1">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm font-medium">
          <span className="flex items-center gap-1.5">
            <Cpu className="size-4" aria-hidden="true" />
            Controlador · quem pilota
          </span>
          <span
            data-testid="controlador-estado"
            data-estado={estado}
            aria-live="polite"
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[0.7rem] font-normal ${
              recusado
                ? "border border-destructive bg-destructive/10 text-destructive"
                : trocando
                  ? "border border-foreground/40 bg-muted text-foreground"
                  : "border border-border bg-muted text-muted-foreground"
            }`}
          >
            <span
              aria-hidden="true"
              className={`size-1.5 rounded-full ${
                trocando ? "animate-pulse bg-foreground" : "bg-muted-foreground/50"
              }`}
            />
            {textoEstadoControlador(estado)}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          troca ao vivo entre a política RL (IA-1, contrato r11 — yaw fixo) e a
          cascata clássica C++ do firmware (yaw livre, WASDQE relativo ao rumo,
          «olhar» IBVS). A troca reinicia o episódio (calibração do giroscópio no
          chão) e nunca acontece em silêncio.
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        {/* TOGGLE segmentado — mostra o modo EM VIGOR (eco do runner), não o clicado */}
        <div
          className="grid grid-cols-2 gap-1 rounded-xl bg-muted/60 p-1"
          role="group"
          aria-label="seletor de controlador"
        >
          <button
            type="button"
            data-testid="controlador-modo-rl"
            data-ativo={modo === "rl" ? "sim" : "nao"}
            aria-pressed={modo === "rl"}
            disabled={trocando}
            title="política RL (IA-1): o de sempre, contrato r11 (yaw fixo)"
            onClick={() => escolher("rl")}
            className={`rounded-lg px-3 py-2 text-[0.75rem] font-medium transition-all ${FOCUS_RING} ${
              modo === "rl"
                ? "border border-foreground bg-foreground text-background"
                : "border border-transparent text-muted-foreground hover:text-foreground"
            } ${trocando ? "opacity-50" : ""}`}
          >
            RL (IA-1)
            <span className="block text-[0.62rem] font-normal opacity-80">
              política PPO · 50 Hz
            </span>
          </button>
          <button
            type="button"
            data-testid="controlador-modo-classico"
            data-ativo={modo === "classico" ? "sim" : "nao"}
            aria-pressed={modo === "classico"}
            disabled={trocando}
            title="cascata clássica C++ do firmware (via ctypes): yaw livre, olhar IBVS"
            onClick={() => escolher("classico")}
            className={`rounded-lg px-3 py-2 text-[0.75rem] font-medium transition-all ${FOCUS_RING} ${
              modo === "classico"
                ? "border border-foreground bg-foreground text-background"
                : "border border-transparent text-muted-foreground hover:text-foreground"
            } ${trocando ? "opacity-50" : ""}`}
          >
            CLÁSSICO (C++)
            <span className="block text-[0.62rem] font-normal opacity-80">
              cascata do firmware · 50 Hz
            </span>
          </button>
        </div>

        {/* ESTADO HONESTO — o motivo da troca/recusa, sempre que existe */}
        <p
          data-testid="controlador-motivo"
          data-motivo={controlador?.motivo ?? ""}
          className={`rounded-lg px-3 py-2 text-[0.7rem] ${
            recusado
              ? "border border-destructive/40 bg-destructive/10 text-destructive"
              : trocando
                ? "border border-dashed border-foreground/30 text-foreground"
                : "text-muted-foreground"
          }`}
        >
          {trocando || recusado
            ? (controlador?.motivo ?? "a trocar de controlador…")
            : "troca sem surpresas: o episódio atual termina na troca e o site diz-o sempre"}
          {!ligado ? " · API em baixo: o comando pode não chegar" : ""}
        </p>

        {/* QUEM FAZ O QUÊ (resumo) — a fonte completa está no painel ao lado */}
        <dl className="grid grid-cols-2 gap-2 rounded-xl bg-muted/40 px-3 py-2">
          <div className="flex min-w-0 flex-col">
            <dt className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              quem voa
            </dt>
            <dd
              className="truncate text-sm font-medium"
              data-testid="controlador-fonte"
            >
              {controlador?.fonte ?? "—"}
            </dd>
          </div>
          <div className="flex min-w-0 flex-col">
            <dt className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              v_ref em vigor
            </dt>
            <dd
              className="truncate text-sm font-medium"
              data-testid="controlador-vref-fonte"
            >
              {controlador?.v_ref_fonte ?? "—"}
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}
