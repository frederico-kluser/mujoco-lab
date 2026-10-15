/**
 * Os hooks do COCKPIT: o que liga o React aos controlos de módulo (`lib/cockpit-controlos.ts`), ao HUD
 * ao vivo (`lib/hud-store.ts`) e ao que se guarda no browser (janelas, vista).
 *
 * Regra de desempenho: nada daqui re-renderiza a 50 Hz. O HUD entra no React só pelo RESUMO lento
 * (`useResumoHud`); o que mexe a cada amostra desenha-se por refs (`useDesenhoHud`).
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react"

import {
  CHAVE_JANELAS,
  alternarJanela,
  fecharEmFoco,
  fecharJanela,
  focarJanela,
  lerJanelas,
  moverJanela,
  serializarJanelas,
  type EstadoBola,
  type EstadoJanelas,
  type EstadoPiloto,
  type EstadoVento,
  type IdJanela,
  type Ponto,
  type ResumoHud,
  type Tamanho,
} from "@/lib/cockpit"
import { bola, piloto, vento } from "@/lib/cockpit-controlos"
import { hud, type Desenhador } from "@/lib/hud-store"

// --------------------------------------------------------------------------------- HUD

/** O resumo LENTO do HUD (ligação, fase, seguidor, alerta de bateria) — muda de segundos a segundos. */
export function useResumoHud(): ResumoHud {
  return useSyncExternalStore(hud.subscrever, hud.obterResumo)
}

/**
 * Regista um desenhador no `requestAnimationFrame` do HUD enquanto o componente estiver montado.
 * O desenhador escreve no DOM por refs (`transform`, `textContent`) — nunca chama `setState`.
 */
export function useDesenhoHud(desenhar: Desenhador): void {
  const atual = useRef(desenhar)
  useEffect(() => {
    atual.current = desenhar
  })
  useEffect(() => hud.desenhar((quadro) => atual.current(quadro)), [])
}

// --------------------------------------------------------------------------------- controlos

export function usePiloto(): EstadoPiloto {
  return useSyncExternalStore(piloto.subscrever, piloto.obter)
}

export function useVento(): EstadoVento {
  return useSyncExternalStore(vento.subscrever, vento.obter)
}

export function useBola(): EstadoBola {
  return useSyncExternalStore(bola.subscrever, bola.obter)
}

// --------------------------------------------------------------------------------- browser

/** `localStorage` pode não existir (modo privado, política do browser): lê-se e escreve-se sem rebentar. */
function lerGuardado(chave: string): string | null {
  try {
    return window.localStorage.getItem(chave)
  } catch {
    return null
  }
}

function guardar(chave: string, valor: string): void {
  try {
    window.localStorage.setItem(chave, valor)
  } catch {
    /* sem armazenamento: a preferência vale só para esta sessão */
  }
}

/** Tamanho do viewport (para encaixar as janelas e projetar o HUD) — só muda no `resize`. */
export function useViewport(): Tamanho {
  const [viewport, setViewport] = useState<Tamanho>(() => ({
    largura: window.innerWidth,
    altura: window.innerHeight,
  }))
  useEffect(() => {
    const medir = () =>
      setViewport({ largura: window.innerWidth, altura: window.innerHeight })
    window.addEventListener("resize", medir)
    return () => window.removeEventListener("resize", medir)
  }, [])
  return viewport
}

/** A página está visível? Com `document.hidden` o cockpit fecha os streams e o SSE. */
export function usePaginaVisivel(): boolean {
  return useSyncExternalStore(
    (ouvinte) => {
      document.addEventListener("visibilitychange", ouvinte)
      return () => document.removeEventListener("visibilitychange", ouvinte)
    },
    () => !document.hidden
  )
}

export interface GestorJanelas {
  estado: EstadoJanelas
  alternar: (id: IdJanela) => void
  fechar: (id: IdJanela) => void
  focar: (id: IdJanela) => void
  mover: (id: IdJanela, ponto: Ponto) => void
  /** `Esc`. */
  fecharDaFrente: () => void
}

/** As janelas flutuantes: abertas, ordem e posições — guardadas em `localStorage` a cada mudança. */
export function useJanelas(): GestorJanelas {
  const [estado, setEstado] = useState<EstadoJanelas>(() =>
    lerJanelas(lerGuardado(CHAVE_JANELAS))
  )
  useEffect(() => {
    guardar(CHAVE_JANELAS, serializarJanelas(estado))
  }, [estado])
  const alternar = useCallback(
    (id: IdJanela) => setEstado((e) => alternarJanela(e, id)),
    []
  )
  const fechar = useCallback(
    (id: IdJanela) => setEstado((e) => fecharJanela(e, id)),
    []
  )
  const focar = useCallback(
    (id: IdJanela) => setEstado((e) => focarJanela(e, id)),
    []
  )
  const mover = useCallback(
    (id: IdJanela, ponto: Ponto) => setEstado((e) => moverJanela(e, id, ponto)),
    []
  )
  const fecharDaFrente = useCallback(() => setEstado((e) => fecharEmFoco(e)), [])
  return { estado, alternar, fechar, focar, mover, fecharDaFrente }
}

/** Qual das duas vistas ocupa o ecrã: a câmara de bordo ou a da simulação. */
export type Vista = "fpv" | "terceira"

const CHAVE_VISTA = "09_drone_hover_rl:cockpit:vista:v1"

interface VistaGuardada {
  vista: Vista
  miniatura: boolean
}

function lerVistaGuardada(): VistaGuardada {
  try {
    const o = JSON.parse(lerGuardado(CHAVE_VISTA) ?? "null") as unknown
    if (typeof o === "object" && o !== null) {
      const g = o as Record<string, unknown>
      return {
        vista: g.vista === "terceira" ? "terceira" : "fpv",
        miniatura: g.miniatura !== false,
      }
    }
  } catch {
    /* preferência ilegível: fica a de origem */
  }
  return { vista: "fpv", miniatura: true }
}

export interface GestorVista extends VistaGuardada {
  trocar: () => void
  definirMiniatura: (aberta: boolean) => void
}

/** A vista escolhida (1.ª ↔ 3.ª pessoa) e a miniatura aberta/fechada, lembradas entre sessões. */
export function useVista(): GestorVista {
  const [estado, setEstado] = useState<VistaGuardada>(lerVistaGuardada)
  useEffect(() => {
    guardar(CHAVE_VISTA, JSON.stringify(estado))
  }, [estado])
  const trocar = useCallback(
    () =>
      setEstado((e) => ({
        ...e,
        vista: e.vista === "fpv" ? "terceira" : "fpv",
      })),
    []
  )
  const definirMiniatura = useCallback(
    (aberta: boolean) => setEstado((e) => ({ ...e, miniatura: aberta })),
    []
  )
  return { ...estado, trocar, definirMiniatura }
}
