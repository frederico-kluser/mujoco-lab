/**
 * BLOCO «CÂMARA» (secções «Operação» e «Tudo») — o widget de TERCEIRA-PESSOA do dono
 * (2026-10-09): um CÍRCULO com um glifo de DRONE ao centro e UMA ESFERA arrastável (horizontal =
 * azimute, vertical = elevação), um SLIDER de DISTÂNCIA (0,1–10 m) e o botão REPOR VISTA. Efeito
 * de jogo: a câmara ORBITA SEMPRE o drone — o backend trata do seguimento (alvo = drone+offset) e
 * o front só comanda ângulo + distância.
 *
 * Contrato v2 (partilhado com `sim_site.py`/`sim_view.py`):
 *  · `POST /api/camera` com um SUBCONJUNTO de `{azimute, elevacao, distancia}` — SEM `alvo` nem
 *    `seq` (o servidor incrementa o `seq`); `null`/campos desconhecidos são 400;
 *  · telemetria/API: `camera` = `{azimute, elevacao, distancia, alvo:[x,y,z]}` (câmara REAL) ou
 *    `null` sem viewer; `camera_padrao` = `{azimute, elevacao, distancia}`; `camera_atual` em
 *    `/api/sim` e `/api/state`;
 *  · **REPOR VISTA** = enviar o `camera_padrao`.
 *
 * MAPEAMENTO do pad (`lib/camera-gestos.ts`, com as fórmulas verificadas contra o MuJoCo 3.15):
 *  · horizontal: `u = azimute/180 − 1` — arrastar para a direita AUMENTA o azimute (a câmara
 *    orbita de +x para +y, anti-horário visto de cima); passar nas bordas faz WRAP 360↔0;
 *  · vertical: `w = −elevacao/90` — arrastar para CIMA põe a câmara MAIS ALTA (a elevação fica
 *    mais NEGATIVA: `pos = alvo − d·f` ⇒ `pos_z = alvo_z − d·sin(elev)`); os limites ±90 travam a
 *    esfera nas bordas superior/inferior.
 *  · a posição da esfera é SEMPRE função dos ângulos atuais (inclusive quando a câmara é mexida
 *    pelo rato da janela fora de arrasto) — estados honestos.
 *
 * GESTOS (máquina em `lib/camera-gestos.ts`, testada em `testes/camera-gestos.mts`): comandos ao
 * vivo ENQUANTO se arrasta (throttle de 150 ms com coalescência — 1 comando por mudança final de
 * valor) + commit final imediato ao largar. Os valores enviados são SEMPRE os do gesto (snapshot —
 * DEF-1) e a telemetria nunca os sobrescreve durante o arrasto nem com envio pendente; sem dados
 * (`camera`/`camera_atual` a `null`) o bloco mostra «—» e desativa-se SEMPRE (DEF-2).
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { Camera, RotateCcw, Send } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LinhaSlider } from "@/components/sim/controlos"
import type { TomAviso } from "@/components/sim/avisos"
import {
  ATRASO_ENVIO_CAMERA_MS,
  aplicarArrasto,
  esferaDeAngulos,
  esferaDesenho,
  MaquinaCamera,
  type FaseEnvio,
} from "@/lib/camera-gestos"
import {
  CAMERA_UI_LIMITES,
  fmt,
  posicaoCamera,
  type CameraEstado,
  type CorpoCamera,
} from "@/lib/sim"

/** Geometria do pad em unidades do SVG (viewBox 200×200): círculo de raio 88, esfera de raio 13. */
const RAIO_PAD = 88
const RAIO_ESFERA = 13
/** Meia-largura da viagem da esfera (unidades do pad): `u`/`w` = ±1 → ±VIAGEM a partir do centro. */
const VIAGEM = RAIO_PAD - RAIO_ESFERA

const TEXTO_FASE: Record<FaseEnvio, string> = {
  repouso: "pronto",
  a_enviar: "a enviar…",
  enviado: "enviado · a aguardar confirmação da câmara real",
  confirmado: "confirmado pela câmara real",
  erro: "falha no envio",
}

export interface ControlosCameraProps {
  /** CÂMARA REAL (`camera_atual`, com reforço da telemetria); `null` = sem dados → «—». */
  camera: CameraEstado | null
  /** Valores por omissão (`camera_padrao`) — o REPOR VISTA envia exatamente isto. */
  cameraPadrao: CameraEstado | null
  ligado: boolean
  /** Envio do comando (o `use-sim` faz `POST /api/camera` + releitura); rejeição = aviso. */
  onEnviar: (corpo: CorpoCamera) => Promise<void>
  onAviso: (texto: string, tom: TomAviso) => void
}

export function ControlosCamera({
  camera,
  cameraPadrao,
  ligado,
  onEnviar,
  onAviso,
}: ControlosCameraProps) {
  /** Valores mostrados no widget (`null` = «—», DEF-2). */
  const [valores, setValores] = useState<CameraEstado | null>(null)
  const [fase, setFase] = useState<FaseEnvio>("repouso")
  const [motivo, setMotivo] = useState<string | null>(null)

  // As props entram na máquina por ref (a máquina vive durante a sessão do bloco).
  const ligadoRef = useRef(ligado)
  const onEnviarRef = useRef(onEnviar)
  const onAvisoRef = useRef(onAviso)
  useEffect(() => {
    ligadoRef.current = ligado
    onEnviarRef.current = onEnviar
    onAvisoRef.current = onAviso
  }, [ligado, onEnviar, onAviso])

  const maquinaRef = useRef<MaquinaCamera | null>(null)
  if (maquinaRef.current === null) {
    maquinaRef.current = new MaquinaCamera({
      enviar: (corpo) => onEnviarRef.current(corpo),
      aoMostrar: (v) => setValores(v),
      aoFase: (f, m) => {
        setFase(f)
        setMotivo(m)
      },
      aoAvisar: (texto) => onAvisoRef.current(texto, "erro"),
      ligado: () => ligadoRef.current,
    })
  }
  const maquina = maquinaRef.current

  // Telemetria → máquina (adoção honesta: DEF-1 protege os gestos, DEF-2 o «—»).
  useEffect(() => {
    maquina.receberCamera(camera)
  }, [camera, maquina])
  useEffect(() => () => maquina.cancelarEnvio(), [maquina])

  // ---------------------------------------------------------------------------- gesto do pad
  const gesto = useRef<{
    x0: number
    y0: number
    az0: number
    el0: number
    pxPorU: number
  } | null>(null)

  const podeArrastar = !semDados(valores) && ligado

  const aoApontar = useCallback(
    (evento: React.PointerEvent<SVGSVGElement>) => {
      const base = valores
      if (base === null || !ligado) return // DEF-2: sem dados o controlo está desativado
      evento.preventDefault()
      evento.currentTarget.setPointerCapture(evento.pointerId)
      const rect = evento.currentTarget.getBoundingClientRect()
      gesto.current = {
        x0: evento.clientX,
        y0: evento.clientY,
        az0: base.azimute,
        el0: base.elevacao,
        pxPorU: (rect.width / 200) * VIAGEM,
      }
      maquina.comecarArrasto()
    },
    [ligado, maquina, valores]
  )

  const aoArrastar = useCallback(
    (evento: React.PointerEvent<SVGSVGElement>) => {
      const g = gesto.current
      if (g === null) return
      // Arrasto relativo ao INÍCIO do gesto (sem deriva): direita = azimute ↑, cima = elevação ↓.
      const du = (evento.clientX - g.x0) / g.pxPorU
      const dw = -(evento.clientY - g.y0) / g.pxPorU
      const { azimute, elevacao } = aplicarArrasto(
        { azimute: g.az0, elevacao: g.el0 },
        du,
        dw
      )
      maquina.editarAngulos(azimute, elevacao)
    },
    [maquina]
  )

  const aoLargar = useCallback(
    (evento: React.PointerEvent<SVGSVGElement>) => {
      if (gesto.current === null) return
      gesto.current = null
      if (evento.currentTarget.hasPointerCapture(evento.pointerId))
        evento.currentTarget.releasePointerCapture(evento.pointerId)
      // COMMIT FINAL imediato: os valores enviados são os finais do gesto (DEF-1).
      maquina.terminarGesto()
    },
    [maquina]
  )

  // Arrasto do slider de distância: começa no pointerdown da linha e termina no pointerup global.
  useEffect(() => {
    const aoLargarGesto = () => maquina.terminarGesto()
    window.addEventListener("pointerup", aoLargarGesto)
    window.addEventListener("pointercancel", aoLargarGesto)
    return () => {
      window.removeEventListener("pointerup", aoLargarGesto)
      window.removeEventListener("pointercancel", aoLargarGesto)
    }
  }, [maquina])

  /** REPOR VISTA = enviar o `camera_padrao` (contrato v2). */
  const reporVista = useCallback(() => {
    maquina.reporVista(cameraPadrao)
  }, [cameraPadrao, maquina])

  // ---------------------------------------------------------------------------- desenho
  const esfera = valores === null ? null : esferaDeAngulos(valores.azimute, valores.elevacao)
  const desenho = esfera === null ? null : esferaDesenho(esfera.u, esfera.w)
  const esferaCx = 100 + (desenho?.u ?? 0) * VIAGEM
  const esferaCy = 100 - (desenho?.w ?? 0) * VIAGEM
  const sem = valores === null
  const pos =
    valores === null || valores.alvo === null
      ? null
      : posicaoCamera(
          valores.azimute,
          valores.elevacao,
          valores.distancia,
          valores.alvo
        )

  return (
    <Card className="gap-4" data-testid="painel-camera">
      <CardHeader className="gap-1">
        <CardTitle className="flex items-center gap-1.5 text-sm font-medium">
          <Camera className="size-4" aria-hidden="true" />
          Câmara
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          vista 3.ª pessoa: a câmara orbita sempre o drone · arraste a esfera
          (horizontal = azimute, vertical = elevação) · o rato da janela 3D
          continua livre entre comandos
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {/* Estado honesto: a câmara REAL tal como o backend a publica, ou «—» sem dados. */}
        <p
          className="rounded-md bg-muted/40 px-2 py-1 font-mono text-[0.65rem] text-muted-foreground"
          data-testid="camera-real"
        >
          câmara real:{" "}
          {valores === null ? (
            "—"
          ) : (
            <>
              az {fmt(valores.azimute, 0)}° · el {fmt(valores.elevacao, 0)}° · d{" "}
              {fmt(valores.distancia, 1)} m
              {valores.alvo !== null ? (
                <>
                  {" "}
                  · alvo [{fmt(valores.alvo[0], 2)}, {fmt(valores.alvo[1], 2)},{" "}
                  {fmt(valores.alvo[2], 2)}]
                </>
              ) : null}
              {pos !== null ? (
                <>
                  {" "}
                  · pos [{fmt(pos[0], 2)}, {fmt(pos[1], 2)}, {fmt(pos[2], 2)}]
                </>
              ) : null}
            </>
          )}
        </p>

        {/*
          Valores crus para as provas de DOM (sem parse de vírgulas decimais): os atributos
          `data-*` são o estado exato do widget; `sem-dados` diz se o bloco está em «—».
        */}
        <output
          className="sr-only"
          data-testid="camera-raw"
          data-sem-dados={sem ? "sim" : "nao"}
          data-azimute={sem ? "" : String(valores.azimute)}
          data-elevacao={sem ? "" : String(valores.elevacao)}
          data-distancia={sem ? "" : String(valores.distancia)}
          data-u={esfera === null ? "" : String(esfera.u)}
          data-w={esfera === null ? "" : String(esfera.w)}
          data-desenho-u={desenho === null ? "" : String(desenho.u)}
          data-desenho-w={desenho === null ? "" : String(desenho.w)}
          data-alvo-x={valores?.alvo ? String(valores.alvo[0]) : ""}
          data-alvo-y={valores?.alvo ? String(valores.alvo[1]) : ""}
          data-alvo-z={valores?.alvo ? String(valores.alvo[2]) : ""}
        />

        {/* O PAD: círculo + drone ao centro + a esfera arrastável (azimute × elevação). */}
        <div className="flex flex-col items-center gap-2">
          <svg
            viewBox="0 0 200 200"
            className={`w-full max-w-[16rem] touch-none select-none ${podeArrastar ? "cursor-grab active:cursor-grabbing" : "opacity-50"}`}
            data-testid="camera-pad"
            data-slider="camera-pad"
            role="application"
            tabIndex={0}
            aria-label="pad da câmara: horizontal = azimute, vertical = elevação"
            aria-disabled={!podeArrastar}
            onPointerDown={aoApontar}
            onPointerMove={aoArrastar}
            onPointerUp={aoLargar}
            onPointerCancel={aoLargar}
          >
            <circle
              cx="100"
              cy="100"
              r={RAIO_PAD}
              className="fill-muted/50 stroke-border"
              strokeWidth="1.5"
            />
            {/* Guias dos eixos (o centro = azimute 180°, elevação 0°). */}
            <line x1={100 - VIAGEM} y1="100" x2={100 + VIAGEM} y2="100" className="stroke-border/70" strokeWidth="1" />
            <line x1="100" y1={100 - VIAGEM} x2="100" y2={100 + VIAGEM} className="stroke-border/70" strokeWidth="1" />

            {/* Glifo de DRONE (quadricóptero) ao centro — o alvo é sempre o drone. */}
            <g className="stroke-foreground/80" strokeWidth="3" strokeLinecap="round">
              <line x1="72" y1="72" x2="128" y2="128" />
              <line x1="128" y1="72" x2="72" y2="128" />
            </g>
            <g className="fill-muted stroke-foreground/80" strokeWidth="2">
              <circle cx="72" cy="72" r="9" />
              <circle cx="128" cy="72" r="9" />
              <circle cx="72" cy="128" r="9" />
              <circle cx="128" cy="128" r="9" />
            </g>
            <circle cx="100" cy="100" r="8" className="fill-foreground/80" />

            {/* A ESFERA arrastável — a posição reflete SEMPRE os ângulos atuais. */}
            <circle
              cx={esferaCx}
              cy={esferaCy}
              r={RAIO_ESFERA}
              className="fill-primary stroke-background"
              strokeWidth="2"
              data-testid="camera-esfera"
              data-cx={String(esferaCx)}
              data-cy={String(esferaCy)}
            />
          </svg>
          <p className="px-1 text-center text-[0.6rem] text-muted-foreground">
            esfera: ← → = azimute (0° olha para +x · wrap 360↔0 nas bordas) ·
            ↑ ↓ = elevação (cima = câmara mais alta; limites ±90°)
          </p>
        </div>

        {/* DISTÂNCIA (zoom) + REPOR VISTA. */}
        <div
          className="flex flex-col gap-3"
          onPointerDown={(evento) => {
            const alvo = evento.target
            if (
              alvo instanceof Element &&
              alvo.closest('[data-slot="slider"], [role="slider"]') !== null
            )
              maquina.comecarArrasto()
          }}
        >
          <LinhaSlider
            id="cam-distancia"
            testeId="camera-distancia"
            rotulo="distância"
            valor={sem ? null : valores.distancia}
            min={CAMERA_UI_LIMITES.distancia[0]}
            max={CAMERA_UI_LIMITES.distancia[1]}
            passo={0.1}
            sufixo=" m"
            casasExtremos={1}
            onChange={(v) => maquina.editarDistancia(v)}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 rounded-full px-3 text-xs"
            data-testid="camera-repor"
            disabled={sem || !ligado || cameraPadrao === null}
            title="reenvia os valores por omissão (camera_padrao) por POST /api/camera"
            onClick={reporVista}
          >
            <RotateCcw className="size-3.5" aria-hidden="true" />
            REPOR VISTA
          </Button>
          <p
            className="font-mono text-[0.6rem] text-muted-foreground"
            data-testid="camera-padrao"
          >
            {cameraPadrao === null ? (
              <>camera_padrao: —</>
            ) : (
              <>
                camera_padrao: az {fmt(cameraPadrao.azimute, 0)}° · el{" "}
                {fmt(cameraPadrao.elevacao, 0)}° · d{" "}
                {fmt(cameraPadrao.distancia, 1)} m
              </>
            )}
          </p>
        </div>

        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.65rem] text-muted-foreground">
          <span
            data-testid="camera-envio"
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[0.6rem] ${
              fase === "erro"
                ? "bg-destructive/15 text-destructive"
                : fase === "confirmado"
                  ? "bg-primary/10 text-primary"
                  : "bg-muted text-muted-foreground"
            }`}
          >
            <Send className="size-3" aria-hidden="true" />
            {fase === "erro" && motivo !== null
              ? `falha: ${motivo}`
              : TEXTO_FASE[fase]}
          </span>
          <span>
            comandos ao vivo enquanto se arrasta (throttle{" "}
            {ATRASO_ENVIO_CAMERA_MS} ms, coalescência) + commit final ao largar
            · POST /api/camera com {`{azimute, elevacao, distancia}`} (sem
            `alvo` nem `seq`)
          </span>
        </p>

        <p className="px-1 text-[0.6rem] text-muted-foreground">
          pos = alvo − d·f(azim,elev) · f = [cos e·cos a, cos e·sin a, sin e]
          (direção de visão unitária do MuJoCo; elevação NEGATIVA = câmara acima
          do alvo) · o alvo é o drone+offset e o backend faz o seguimento
        </p>
      </CardContent>
    </Card>
  )
}

/** `null` = sem dados («—» + controlo desativado, DEF-2). */
function semDados(valores: CameraEstado | null): boolean {
  return valores === null
}
