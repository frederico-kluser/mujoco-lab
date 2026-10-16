/**
 * Painel de Controladores de Otimização Gráfica do MuJoCo + Leitura de FPS ao Vivo.
 *
 * Permite ligar/desligar em tempo real (`POST /api/graficos`) funcionalidades gráficas do renderizador
 * OpenGL/EGL do MuJoCo (`mjrOption` / `mjvOption`) para aumentar o FPS:
 *  · Sombras (`mjRND_SHADOW`);
 *  · Reflexos no chão (`mjRND_REFLECTION`);
 *  · Fios trifásicos dos motores, bobinas de cobre, portas RPi 5 e detalhes finos (`group 3`);
 *  · Hélices 3D rotativas (`group 1`);
 *  · Efeitos visuais: discos de hélice, fogo do cano e rastro balístico (`group 2`);
 *  · Nevoeiro 3D (`mjRND_FOG`);
 *  · Escala de resolução OpenGL (25 % a 100 %) e qualidade JPEG (30 a 95).
 */

import { useRef, useState } from "react"

import {
  Deslizador,
  Interruptor,
  Legenda,
  Leitura,
  Marca,
} from "@/components/cockpit/pecas"
import { useDesenhoHud } from "@/hooks/use-cockpit"
import { enviarGraficos, type OpcoesGraficosPayload } from "@/lib/api"
import { fmtHud } from "@/lib/cockpit"

interface EstadoLocalGraficos {
  sombras: boolean
  reflexos: boolean
  nevoeiro: boolean
  mostrarHelices: boolean
  mostrarEfeitos: boolean
  mostrarFiosDetalhes: boolean
  escalaResolucao: number
  qualidadeJpeg: number
}

const INICIAL: EstadoLocalGraficos = {
  sombras: true,
  reflexos: true,
  nevoeiro: false,
  mostrarHelices: true,
  mostrarEfeitos: true,
  mostrarFiosDetalhes: true,
  escalaResolucao: 1.0,
  qualidadeJpeg: 80,
}

export function PainelOtimizacaoMuJoCo() {
  const [cfg, setCfg] = useState<EstadoLocalGraficos>(INICIAL)
  const rFpsAtual = useRef<HTMLSpanElement>(null)
  const rFpsSim = useRef<HTMLSpanElement>(null)
  const rFpsFpv = useRef<HTMLSpanElement>(null)
  const rFpsFisica = useRef<HTMLSpanElement>(null)
  const rSincronizado = useRef(false)

  useDesenhoHud(({ hud, texto }) => {
    const g = hud?.graficos ?? null
    if (g !== null && !rSincronizado.current) {
      rSincronizado.current = true
      setCfg({
        sombras: g.sombras,
        reflexos: g.reflexos,
        nevoeiro: g.nevoeiro,
        mostrarHelices: g.mostrarHelices,
        mostrarEfeitos: g.mostrarEfeitos,
        mostrarFiosDetalhes: g.mostrarFiosDetalhes,
        escalaResolucao: g.escalaResolucao,
        qualidadeJpeg: g.qualidadeJpeg,
      })
    }
    if (!texto) return
    if (rFpsAtual.current !== null) {
      const txt = g?.fpsAtual != null ? `${fmtHud(g.fpsAtual, 1)} FPS` : "50,0 FPS"
      if (rFpsAtual.current.textContent !== txt) rFpsAtual.current.textContent = txt
    }
    if (rFpsSim.current !== null) {
      const txt =
        g !== null
          ? `${fmtHud(g.fpsSimulacao, 1)} fps (${fmtHud(g.msRenderSim, 1)} ms)`
          : "—"
      if (rFpsSim.current.textContent !== txt) rFpsSim.current.textContent = txt
    }
    if (rFpsFpv.current !== null) {
      const txt =
        g !== null
          ? `${fmtHud(g.fpsFpv, 1)} fps (${fmtHud(g.msRenderFpv, 1)} ms)`
          : "—"
      if (rFpsFpv.current.textContent !== txt) rFpsFpv.current.textContent = txt
    }
    if (rFpsFisica.current !== null) {
      const txt = g?.fpsFisica != null ? `${fmtHud(g.fpsFisica, 1)} Hz` : "50,0 Hz"
      if (rFpsFisica.current.textContent !== txt) rFpsFisica.current.textContent = txt
    }
  })

  const aplicar = (parcial: Partial<EstadoLocalGraficos>, payload: OpcoesGraficosPayload) => {
    setCfg((ant) => ({ ...ant, ...parcial }))
    void enviarGraficos(payload).catch(() => undefined)
  }

  const aplicarPreset = (modo: "max_fps" | "equilibrado" | "ultra") => {
    if (modo === "max_fps") {
      aplicar(
        {
          sombras: false,
          reflexos: false,
          nevoeiro: false,
          mostrarHelices: true,
          mostrarEfeitos: true,
          mostrarFiosDetalhes: false,
          escalaResolucao: 0.5,
          qualidadeJpeg: 65,
        },
        {
          sombras: false,
          reflexos: false,
          nevoeiro: false,
          mostrar_helices: true,
          mostrar_efeitos: true,
          mostrar_fios_detalhes: false,
          escala_resolucao: 0.5,
          qualidade_jpeg: 65,
        }
      )
    } else if (modo === "equilibrado") {
      aplicar(
        {
          sombras: true,
          reflexos: false,
          nevoeiro: false,
          mostrarHelices: true,
          mostrarEfeitos: true,
          mostrarFiosDetalhes: true,
          escalaResolucao: 0.75,
          qualidadeJpeg: 75,
        },
        {
          sombras: true,
          reflexos: false,
          nevoeiro: false,
          mostrar_helices: true,
          mostrar_efeitos: true,
          mostrar_fios_detalhes: true,
          escala_resolucao: 0.75,
          qualidade_jpeg: 75,
        }
      )
    } else {
      aplicar(
        {
          sombras: true,
          reflexos: true,
          nevoeiro: false,
          mostrarHelices: true,
          mostrarEfeitos: true,
          mostrarFiosDetalhes: true,
          escalaResolucao: 1.0,
          qualidadeJpeg: 85,
        },
        {
          sombras: true,
          reflexos: true,
          nevoeiro: false,
          mostrar_helices: true,
          mostrar_efeitos: true,
          mostrar_fios_detalhes: true,
          escala_resolucao: 1.0,
          qualidade_jpeg: 85,
        }
      )
    }
  }

  return (
    <section
      data-testid="painel-otimizacao-mujoco"
      className="flex flex-col gap-3 rounded-xl border border-white/12 bg-black/45 p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-2">
        <div className="flex flex-col">
          <Legenda>otimização gráfica do MuJoCo · FPS ao vivo</Legenda>
          <span className="text-[0.72rem] text-muted-foreground">
            Desligue sombras, reflexos ou detalhes 3D para aumentar o FPS
          </span>
        </div>
        <Marca tom="ativo" testid="mujoco-fps-atual">
          <span ref={rFpsAtual}>50,0 FPS</span>
        </Marca>
      </div>

      {/* Leituras de FPS e tempo de render por vista */}
      <div className="grid grid-cols-3 gap-2 rounded-lg bg-white/5 px-2.5 py-2">
        <Leitura
          rotulo="vista 3.ª pessoa"
          refValor={rFpsSim}
          testid="mujoco-fps-sim"
        />
        <Leitura
          rotulo="câmara FPV"
          refValor={rFpsFpv}
          testid="mujoco-fps-fpv"
        />
        <Leitura
          rotulo="física MuJoCo"
          refValor={rFpsFisica}
          testid="mujoco-fps-fisica"
        />
      </div>

      {/* Presets rápidos */}
      <div className="grid grid-cols-3 gap-1.5">
        <button
          type="button"
          data-testid="mujoco-preset-max-fps"
          onClick={() => aplicarPreset("max_fps")}
          className="rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-2 py-1.5 font-etiqueta text-[0.68rem] font-bold tracking-wider text-emerald-300 hover:bg-emerald-500/25"
        >
          ⚡ MÁXIMO FPS
        </button>
        <button
          type="button"
          data-testid="mujoco-preset-equilibrado"
          onClick={() => aplicarPreset("equilibrado")}
          className="rounded-lg border border-white/20 bg-white/8 px-2 py-1.5 font-etiqueta text-[0.68rem] font-bold tracking-wider text-hud hover:bg-white/15"
        >
          ⚖ EQUILIBRADO
        </button>
        <button
          type="button"
          data-testid="mujoco-preset-ultra"
          onClick={() => aplicarPreset("ultra")}
          className="rounded-lg border border-sky-400/40 bg-sky-400/15 px-2 py-1.5 font-etiqueta text-[0.68rem] font-bold tracking-wider text-sky-300 hover:bg-sky-400/25"
        >
          ✦ ULTRA 1080P
        </button>
      </div>

      {/* Interruptores de funcionalidades gráficas do MuJoCo */}
      <div className="grid gap-2 sm:grid-cols-2">
        <Interruptor
          rotulo="SOMBRAS 3D (mjRND_SHADOW)"
          descricao="sombras projetadas no chão e no drone"
          ligado={cfg.sombras}
          onMudar={(v) => aplicar({ sombras: v }, { sombras: v })}
          testid="mujoco-opt-sombras"
        />
        <Interruptor
          rotulo="REFLEXOS (mjRND_REFLECTION)"
          descricao="reflexo planar no chão quadriculado"
          ligado={cfg.reflexos}
          onMudar={(v) => aplicar({ reflexos: v }, { reflexos: v })}
          testid="mujoco-opt-reflexos"
        />
        <Interruptor
          rotulo="FIOS DOS MOTORES & DETALHES RPi 5"
          descricao="cabos trifásicos, bobinas de cobre, portas USB/RJ45 e treliças"
          ligado={cfg.mostrarFiosDetalhes}
          onMudar={(v) =>
            aplicar({ mostrarFiosDetalhes: v }, { mostrar_fios_detalhes: v })
          }
          testid="mujoco-opt-fios"
        />
        <Interruptor
          rotulo="HÉLICES 3D ROTATIVAS"
          descricao="pás de carbono em rotação CW/CCW por % de RPM"
          ligado={cfg.mostrarHelices}
          onMudar={(v) => aplicar({ mostrarHelices: v }, { mostrar_helices: v })}
          testid="mujoco-opt-helices"
        />
        <Interruptor
          rotulo="EFEITOS (DISCOS, FOGO & RASTRO)"
          descricao="discos translúcidos, fogo do cano e caminho de 1 s"
          ligado={cfg.mostrarEfeitos}
          onMudar={(v) => aplicar({ mostrarEfeitos: v }, { mostrar_efeitos: v })}
          testid="mujoco-opt-efeitos"
        />
        <Interruptor
          rotulo="NEVOEIRO 3D (mjRND_FOG)"
          descricao="atenuação atmosférica de profundidade"
          ligado={cfg.nevoeiro}
          onMudar={(v) => aplicar({ nevoeiro: v }, { nevoeiro: v })}
          testid="mujoco-opt-nevoeiro"
        />
      </div>

      {/* Sliders de escala de resolução e qualidade JPEG */}
      <div className="grid gap-3 pt-1 sm:grid-cols-2">
        <Deslizador
          rotulo="escala de resolução OpenGL"
          texto={`${Math.round(cfg.escalaResolucao * 100)} %`}
          valor={cfg.escalaResolucao}
          min={0.25}
          max={1.0}
          passo={0.05}
          extremos={["25 % (+FPS)", "100 % (1080p)"]}
          onArrastar={(v) => setCfg((ant) => ({ ...ant, escalaResolucao: v }))}
          onLargar={(v) =>
            aplicar({ escalaResolucao: v }, { escala_resolucao: v })
          }
          testid="mujoco-opt-escala"
        />
        <Deslizador
          rotulo="qualidade JPEG do stream"
          texto={`${cfg.qualidadeJpeg} %`}
          valor={cfg.qualidadeJpeg}
          min={30}
          max={95}
          passo={5}
          extremos={["30 % (rápido)", "95 % (nítido)"]}
          onArrastar={(v) =>
            setCfg((ant) => ({ ...ant, qualidadeJpeg: Math.round(v) }))
          }
          onLargar={(v) =>
            aplicar(
              { qualidadeJpeg: Math.round(v) },
              { qualidade_jpeg: Math.round(v) }
            )
          }
          testid="mujoco-opt-jpeg"
        />
      </div>
    </section>
  )
}
