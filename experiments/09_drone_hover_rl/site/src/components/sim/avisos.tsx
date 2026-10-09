/**
 * Avisos (toasts) das ações: `toast-stack` do Motion UI (`useToastStack` + `ToastStack` + `Toast`).
 * A fila é headless — quem agenda a saída é este wrapper (5 s para sucesso, 8 s para erro).
 */

import { useCallback, useEffect, useRef, useState } from "react"

import { Toast, ToastStack, useToastStack } from "@/components/motion-ui/toast-stack"

export type TomAviso = "ok" | "erro" | "info"

export interface Aviso {
  id: number
  texto: string
  tom: TomAviso
}

const DURACAO_MS: Record<TomAviso, number> = { ok: 5000, erro: 8000, info: 5000 }

const TOM_CLASSE: Record<TomAviso, string> = {
  ok: "text-primary",
  erro: "text-destructive",
  info: "text-muted-foreground",
}

export function useAvisos() {
  const { toasts, add, dismiss } = useToastStack()
  const [conteudo, setConteudo] = useState<Aviso[]>([])
  const temporizadores = useRef<number[]>([])

  useEffect(
    () => () => {
      for (const t of temporizadores.current) window.clearTimeout(t)
      temporizadores.current = []
    },
    [],
  )

  const notificar = useCallback(
    (texto: string, tom: TomAviso = "info") => {
      const id = add()
      setConteudo((anteriores) => [{ id, texto, tom }, ...anteriores].slice(0, 6))
      const temporizador = window.setTimeout(() => {
        dismiss(id)
        setConteudo((anteriores) => anteriores.filter((a) => a.id !== id))
      }, DURACAO_MS[tom])
      temporizadores.current.push(temporizador)
      return id
    },
    [add, dismiss],
  )

  const fechar = useCallback(
    (id: number) => {
      dismiss(id)
      setConteudo((anteriores) => anteriores.filter((a) => a.id !== id))
    },
    [dismiss],
  )

  return { toasts, conteudo, notificar, fechar }
}

interface PilhaAvisosProps {
  toasts: number[]
  conteudo: Aviso[]
  fechar: (id: number) => void
}

export function PilhaAvisos({ toasts, conteudo, fechar }: PilhaAvisosProps) {
  const porId = new Map(conteudo.map((a) => [a.id, a]))
  return (
    <ToastStack maxVisible={4}>
      {toasts
        .filter((id) => porId.has(id))
        .map((id) => {
          const aviso = porId.get(id)!
          return (
            <Toast key={id}>
              <div className="flex items-start gap-2 rounded-xl border border-border bg-card px-3 py-2.5 text-xs shadow-sm">
                <span className={`mt-0.5 font-medium ${TOM_CLASSE[aviso.tom]}`} aria-hidden="true">
                  {aviso.tom === "ok" ? "✓" : aviso.tom === "erro" ? "!" : "·"}
                </span>
                <p className="min-w-0 flex-1 break-words">{aviso.texto}</p>
                <button
                  type="button"
                  onClick={() => fechar(id)}
                  className="shrink-0 rounded px-1 text-muted-foreground hover:text-foreground"
                  aria-label="fechar aviso"
                >
                  ×
                </button>
              </div>
            </Toast>
          )
        })}
    </ToastStack>
  )
}
