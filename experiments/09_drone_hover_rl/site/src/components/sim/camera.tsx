/**
 * BLOCO «CÂMARA» v3 (2026-10-10) — comanda a câmara da JANELA 3D do MuJoCo a partir do site, como a câmara
 * de terceira pessoa de um jogo: o alvo segue SEMPRE o drone (o backend trata disso) e aqui escolhe-se de
 * ONDE se olha.
 *
 * Porquê v3 (avaliação de UX de 2026-10-10, `out/ux/`): o pad v2 era um círculo com o drone ao centro mas
 * o mapeamento era linear (horizontal = azimute, vertical = elevação) — a esfera não ficava onde a câmara
 * está e era preciso ler a legenda. Agora:
 *
 *  · VISTA DE CIMA — o drone com o NARIZ PARA CIMA (frente/trás/esquerda/direita do próprio drone) e o
 *    ícone da câmara ONDE ela está, com o cone de visão a apontar ao drone; arrastar (ou clicar) noutro
 *    ponto do círculo leva a câmara para lá (órbita/azimute). Com o rumo do drone (`verdade.yaw`) o
 *    desenho é relativo ao nariz; sem ele (cf2/runner antigo) é relativo ao rumo 0.
 *  · VISTA DE LADO — o ícone sobe e desce num arco à volta do drone (ângulo acima do horizonte); o chão é
 *    desenhado à escala (altura do drone ÷ distância) e o ícone fica vermelho se a câmara ficar abaixo dele.
 *  · ZOOM logarítmico com limites da planta (drone real 0,6–15 m; Crazyflie 0,1–5 m), botões −/+ e a roda
 *    do rato por cima das vistas; VISTAS RÁPIDAS de um clique (Atrás · Frente · Esquerda · Direita ·
 *    De cima · À altura) relativas ao nariz; REPOR VISTA = `camera_padrao`.
 *  · Teclado (com o foco numa vista): ← → orbitam ±15°, ↑ ↓ sobem/descem ±10°, + − aproximam/afastam,
 *    Home repõe a vista.
 *  · Leitura em português simples («atrás, à direita · 35° por cima · a 2,0 m»); números, fórmula e rotas
 *    nos «detalhes técnicos».
 *
 * Contrato v2 (inalterado, partilhado com `sim_site.py`/`sim_view.py`): `POST /api/camera` com um
 * SUBCONJUNTO de `{azimute, elevacao, distancia}` (sem `alvo` nem `seq`); telemetria `camera` =
 * `{azimute, elevacao, distancia, alvo}` ou `null` sem janela; `camera_padrao` sem `alvo`. A geometria e a
 * máquina de gestos (DEF-1: os valores enviados são sempre os do gesto; DEF-2: sem dados mostra «—» e
 * desativa) vivem em `lib/camera-gestos.ts`, testadas em `testes/camera-gestos.mts`.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
  type RefObject,
} from "react"
import {
  Camera,
  ChevronDown,
  ChevronUp,
  Minus,
  Plus,
  RotateCcw,
  RotateCw,
  Undo2,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Slider } from "@/components/ui/slider"
import type { TomAviso } from "@/components/sim/avisos"
import { FOCUS_RING } from "@/components/sim/estilo"
import {
  ALTURA_ANGULAR_UI,
  anguloVistaRapida,
  aplicarZoom,
  ATRASO_ENVIO_CAMERA_MS,
  alturaDeElevacao,
  azimuteDePontoTopo,
  descreverCamera,
  distanciaDeFracao,
  elevacaoDePontoLado,
  fracaoDeDistancia,
  limitesDistancia,
  MaquinaCamera,
  orbitar,
  pontoLadoDeElevacao,
  pontoTopoDeAzimute,
  VISTAS_RAPIDAS,
  type FaseEnvio,
} from "@/lib/camera-gestos"
import {
  fmt,
  normalizarAzimute,
  posicaoCamera,
  type CameraEstado,
  type CorpoCamera,
  type Planta,
} from "@/lib/sim"

/** Geometria das vistas (unidades do viewBox 200×200). */
const CENTRO = 100
const RAIO_DISCO = 92
const RAIO_CAMERA_TOPO = 62
const DRONE_LADO = { x: 132, y: 100 }
const RAIO_CAMERA_LADO = 74

const TEXTO_FASE: Record<FaseEnvio, string> = {
  repouso: "sincronizada com a janela 3D",
  a_enviar: "a enviar…",
  enviado: "a aplicar na janela 3D…",
  confirmado: "aplicada na janela 3D",
  erro: "falha no envio",
}

export interface ControlosCameraProps {
  /** CÂMARA REAL (`camera_atual`, com reforço da telemetria); `null` = sem dados → «—». */
  camera: CameraEstado | null
  /** Valores por omissão (`camera_padrao`) — o REPOR VISTA envia exatamente isto. */
  cameraPadrao: CameraEstado | null
  ligado: boolean
  /** Planta em vigor: escolhe os limites do zoom (drone real 0,6–15 m; cf2 0,1–5 m). */
  planta?: Planta | null
  /** Rumo ABSOLUTO do drone (graus; `verdade.yaw`) — orienta a vista de cima e as vistas rápidas. */
  rumoGraus?: number | null
  /** Altura do drone ao chão (m) — o chão da vista de lado fica à escala. */
  alturaDrone?: number | null
  /** Envio do comando (o `use-sim` faz `POST /api/camera` + releitura); rejeição = aviso. */
  onEnviar: (corpo: CorpoCamera) => Promise<void>
  onAviso: (texto: string, tom: TomAviso) => void
}

/** Ponto do evento em unidades do viewBox (0–200), relativo a `(ox, oy)`. */
function pontoNoSvg(
  evento: { clientX: number; clientY: number },
  svg: SVGSVGElement,
  ox: number,
  oy: number
): { sx: number; sy: number } {
  const r = svg.getBoundingClientRect()
  return {
    sx: ((evento.clientX - r.left) / r.width) * 200 - ox,
    sy: ((evento.clientY - r.top) / r.height) * 200 - oy,
  }
}

/** Ícone de câmara (corpo + lente) centrado em (x, y) e a olhar na direção `angulo` (graus, SVG). */
function IconeCamera({
  x,
  y,
  angulo,
  alerta = false,
}: {
  x: number
  y: number
  angulo: number
  alerta?: boolean
}) {
  return (
    <g
      transform={`translate(${x} ${y}) rotate(${angulo})`}
      className={
        alerta
          ? "fill-destructive stroke-background"
          : "fill-primary stroke-background"
      }
      strokeWidth="1.5"
    >
      <rect x="-9" y="-6.5" width="13" height="13" rx="2.5" />
      <path d="M4 -4.5 L10 -7.5 L10 7.5 L4 4.5 Z" />
    </g>
  )
}

interface VistaProps {
  rotulo: string
  dica: string
  testid: string
  ativo: boolean
  valorAgora: number | null
  valorMin: number
  valorMax: number
  valorTexto: string
  svgRef: RefObject<SVGSVGElement | null>
  onApontar: (evento: PointerEvent<SVGSVGElement>) => void
  onArrastar: (evento: PointerEvent<SVGSVGElement>) => void
  onLargar: (evento: PointerEvent<SVGSVGElement>) => void
  onTecla: (evento: KeyboardEvent<SVGSVGElement>) => void
  children: ReactNode
  rodape: ReactNode
}

/** Moldura comum das duas vistas: SVG acessível (slider), título curto e botões de passo por baixo. */
function Vista({
  rotulo,
  dica,
  testid,
  ativo,
  valorAgora,
  valorMin,
  valorMax,
  valorTexto,
  svgRef,
  onApontar,
  onArrastar,
  onLargar,
  onTecla,
  children,
  rodape,
}: VistaProps) {
  return (
    <figure className="flex min-w-0 flex-col items-center gap-1.5">
      <figcaption className="flex w-full items-baseline justify-between gap-2 px-1">
        <span className="text-xs font-medium">{rotulo}</span>
        <span className="text-[0.65rem] text-muted-foreground">{dica}</span>
      </figcaption>
      <svg
        ref={svgRef}
        viewBox="0 0 200 200"
        className={`aspect-square w-full max-w-[15rem] touch-none rounded-xl select-none ${FOCUS_RING} ${
          ativo ? "cursor-grab active:cursor-grabbing" : "opacity-45"
        }`}
        data-testid={testid}
        data-slider={testid}
        data-atalhos-livres=""
        role="slider"
        tabIndex={ativo ? 0 : -1}
        aria-label={`${rotulo}: ${dica}`}
        aria-disabled={!ativo}
        aria-valuemin={valorMin}
        aria-valuemax={valorMax}
        aria-valuenow={valorAgora ?? undefined}
        aria-valuetext={valorTexto}
        onPointerDown={onApontar}
        onPointerMove={onArrastar}
        onPointerUp={onLargar}
        onPointerCancel={onLargar}
        onKeyDown={onTecla}
      >
        {children}
      </svg>
      <div className="flex items-center gap-1">{rodape}</div>
    </figure>
  )
}

export function ControlosCamera({
  camera,
  cameraPadrao,
  ligado,
  planta = null,
  rumoGraus = null,
  alturaDrone = null,
  onEnviar,
  onAviso,
}: ControlosCameraProps) {
  /** Valores mostrados no widget (`null` = «—», DEF-2). */
  const [valores, setValores] = useState<CameraEstado | null>(null)
  const [fase, setFase] = useState<FaseEnvio>("repouso")
  const [motivo, setMotivo] = useState<string | null>(null)
  const limites = useMemo(() => limitesDistancia(planta), [planta])

  // A máquina é criada UMA vez (vive durante a sessão do bloco) e as props entram por `religar` num efeito
  // — nada de refs lidos durante o render; até ao primeiro efeito ela fica «sem ligação» (não envia).
  const [maquina] = useState(
    () =>
      new MaquinaCamera({
        enviar: () =>
          Promise.reject(new Error("o bloco ainda está a ligar-se")),
        aoMostrar: (v) => setValores(v),
        aoFase: (f, m) => {
          setFase(f)
          setMotivo(m)
        },
        aoAvisar: () => undefined,
        ligado: () => false,
      })
  )
  useEffect(() => {
    maquina.religar({
      enviar: onEnviar,
      aoAvisar: (texto) => onAviso(texto, "erro"),
      ligado: () => ligado,
      limitesDistancia: () => limites,
    })
  }, [maquina, onEnviar, onAviso, ligado, limites])

  // Telemetria → máquina (adoção honesta: DEF-1 protege os gestos, DEF-2 o «—»).
  useEffect(() => {
    maquina.receberCamera(camera)
  }, [camera, maquina])
  useEffect(() => () => maquina.cancelarEnvio(), [maquina])

  const sem = valores === null
  const ativo = !sem && ligado
  /** Rumo de referência das vistas: o do drone, ou 0 sem verdade (o desenho fica relativo ao arranque). */
  const rumo = rumoGraus ?? 0

  // ---------------------------------------------------------------------------- comandos
  const orbitarPassos = useCallback(
    (passosOrbita: number, passosAltura: number) => {
      const base = maquina.valores
      if (base === null || !ligado) return
      const novo = orbitar(
        base.azimute,
        base.elevacao,
        passosOrbita,
        passosAltura
      )
      maquina.editarAngulos(novo.azimute, novo.elevacao)
    },
    [ligado, maquina]
  )
  const zoomPassos = useCallback(
    (passos: number) => {
      const base = maquina.valores
      if (base === null || !ligado) return
      maquina.editarDistancia(aplicarZoom(base.distancia, passos, limites))
    },
    [ligado, limites, maquina]
  )
  const reporVista = useCallback(
    () => maquina.reporVista(cameraPadrao),
    [cameraPadrao, maquina]
  )

  // ---------------------------------------------------------------------------- gestos das vistas
  const topoRef = useRef<SVGSVGElement | null>(null)
  const ladoRef = useRef<SVGSVGElement | null>(null)
  const arrasto = useRef<"topo" | "lado" | null>(null)

  const aplicarPonto = useCallback(
    (
      qual: "topo" | "lado",
      evento: { clientX: number; clientY: number },
      svg: SVGSVGElement
    ) => {
      const base = maquina.valores
      if (base === null) return
      if (qual === "topo") {
        const { sx, sy } = pontoNoSvg(evento, svg, CENTRO, CENTRO)
        const relativo = azimuteDePontoTopo(sx, sy, 6)
        if (relativo === null) return
        maquina.editarAngulos(normalizarAzimute(relativo + rumo), base.elevacao)
      } else {
        const { sx, sy } = pontoNoSvg(evento, svg, DRONE_LADO.x, DRONE_LADO.y)
        const elevacao = elevacaoDePontoLado(sx, sy, 6)
        if (elevacao === null) return
        maquina.editarAngulos(base.azimute, elevacao)
      }
    },
    [maquina, rumo]
  )

  const aoApontar = useCallback(
    (qual: "topo" | "lado") => (evento: PointerEvent<SVGSVGElement>) => {
      if (maquina.valores === null || !ligado) return // DEF-2: sem dados está desativado
      evento.preventDefault()
      evento.currentTarget.setPointerCapture(evento.pointerId)
      evento.currentTarget.focus({ preventScroll: true })
      arrasto.current = qual
      maquina.comecarArrasto()
      aplicarPonto(qual, evento, evento.currentTarget)
    },
    [aplicarPonto, ligado, maquina]
  )
  const aoArrastar = useCallback(
    (qual: "topo" | "lado") => (evento: PointerEvent<SVGSVGElement>) => {
      if (arrasto.current !== qual) return
      aplicarPonto(qual, evento, evento.currentTarget)
    },
    [aplicarPonto]
  )
  const aoLargar = useCallback(
    (evento: PointerEvent<SVGSVGElement>) => {
      if (arrasto.current === null) return
      arrasto.current = null
      if (evento.currentTarget.hasPointerCapture(evento.pointerId))
        evento.currentTarget.releasePointerCapture(evento.pointerId)
      maquina.terminarGesto() // COMMIT FINAL: os valores enviados são os finais do gesto (DEF-1)
    },
    [maquina]
  )

  // Slider de distância: o gesto começa no pointerdown do trilho e termina no pointerup global.
  useEffect(() => {
    const aoLargarGesto = () => maquina.terminarGesto()
    window.addEventListener("pointerup", aoLargarGesto)
    window.addEventListener("pointercancel", aoLargarGesto)
    return () => {
      window.removeEventListener("pointerup", aoLargarGesto)
      window.removeEventListener("pointercancel", aoLargarGesto)
    }
  }, [maquina])

  // Roda do rato por cima das vistas = zoom (listener nativo NÃO passivo: o React regista a roda como
  // passiva e o `preventDefault` não impediria a página de rolar).
  useEffect(() => {
    const aoRodar = (evento: WheelEvent) => {
      if (maquina.valores === null || !ligado) return
      evento.preventDefault()
      const passos = Math.max(-3, Math.min(3, -evento.deltaY / 100))
      if (passos !== 0) zoomPassos(passos)
    }
    const alvos = [topoRef.current, ladoRef.current].filter(
      (x): x is SVGSVGElement => x !== null
    )
    for (const alvo of alvos)
      alvo.addEventListener("wheel", aoRodar, { passive: false })
    return () => {
      for (const alvo of alvos) alvo.removeEventListener("wheel", aoRodar)
    }
  }, [ligado, maquina, zoomPassos])

  const aoTeclar = useCallback(
    (evento: KeyboardEvent<SVGSVGElement>) => {
      const mapa: Record<string, () => void> = {
        ArrowLeft: () => orbitarPassos(+1, 0),
        ArrowRight: () => orbitarPassos(-1, 0),
        ArrowUp: () => orbitarPassos(0, +1),
        ArrowDown: () => orbitarPassos(0, -1),
        "+": () => zoomPassos(+1),
        "=": () => zoomPassos(+1),
        "-": () => zoomPassos(-1),
        Home: () => reporVista(),
      }
      const acao = mapa[evento.key]
      if (acao === undefined) return
      evento.preventDefault()
      evento.stopPropagation()
      acao()
    },
    [orbitarPassos, reporVista, zoomPassos]
  )

  // ---------------------------------------------------------------------------- desenho
  const relativo =
    valores === null ? null : normalizarAzimute(valores.azimute - rumo)
  const topo = relativo === null ? null : pontoTopoDeAzimute(relativo)
  const camTopo =
    topo === null
      ? null
      : {
          x: CENTRO + RAIO_CAMERA_TOPO * topo.sx,
          y: CENTRO + RAIO_CAMERA_TOPO * topo.sy,
        }
  const angTopo =
    topo === null ? 0 : (Math.atan2(-topo.sy, -topo.sx) * 180) / Math.PI
  const lado = valores === null ? null : pontoLadoDeElevacao(valores.elevacao)
  const camLado =
    lado === null
      ? null
      : {
          x: DRONE_LADO.x + RAIO_CAMERA_LADO * lado.sx,
          y: DRONE_LADO.y + RAIO_CAMERA_LADO * lado.sy,
        }
  const angLado =
    lado === null ? 0 : (Math.atan2(-lado.sy, -lado.sx) * 180) / Math.PI
  const alturaAng = valores === null ? null : alturaDeElevacao(valores.elevacao)
  // chão da vista de lado À ESCALA: o raio do arco vale a distância da câmara
  const chaoY =
    valores === null || alturaDrone === null || !(alturaDrone > 0)
      ? null
      : Math.min(
          196,
          DRONE_LADO.y + (RAIO_CAMERA_LADO * alturaDrone) / valores.distancia
        )
  const alturaCameraM =
    valores === null || alturaDrone === null || alturaAng === null
      ? null
      : alturaDrone + valores.distancia * Math.sin((alturaAng * Math.PI) / 180)
  const debaixoDoChao = alturaCameraM !== null && alturaCameraM < 0.05
  const descricao =
    valores === null
      ? null
      : descreverCamera(valores.azimute, valores.elevacao, rumo)
  const pos =
    valores === null || valores.alvo === null
      ? null
      : posicaoCamera(
          valores.azimute,
          valores.elevacao,
          valores.distancia,
          valores.alvo
        )
  // arco guia da vista de lado (de −30° a 89° acima do horizonte)
  const arco: string[] = []
  for (let h = ALTURA_ANGULAR_UI[0]; h <= ALTURA_ANGULAR_UI[1]; h += 4) {
    const r = (h * Math.PI) / 180
    arco.push(
      `${(DRONE_LADO.x - RAIO_CAMERA_LADO * Math.cos(r)).toFixed(2)},${(DRONE_LADO.y - RAIO_CAMERA_LADO * Math.sin(r)).toFixed(2)}`
    )
  }
  const cone = (() => {
    if (camTopo === null || topo === null) return null
    const ux = -topo.sx
    const uy = -topo.sy
    const bx = camTopo.x + 48 * ux
    const by = camTopo.y + 48 * uy
    return `${camTopo.x},${camTopo.y} ${bx - 18 * uy},${by + 18 * ux} ${bx + 18 * uy},${by - 18 * ux}`
  })()

  const pronto = fase === "confirmado" || fase === "repouso"

  return (
    <Card className="gap-3" data-testid="painel-camera">
      <CardHeader className="gap-1">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm font-medium">
          <span className="flex items-center gap-1.5">
            <Camera className="size-4" aria-hidden="true" />
            Câmara da janela 3D
          </span>
          <span
            data-testid="camera-envio"
            data-fase={sem ? "sem_dados" : fase}
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[0.7rem] font-normal ${
              sem
                ? "bg-muted text-muted-foreground"
                : fase === "erro"
                  ? "bg-destructive/10 text-destructive"
                  : pronto
                    ? "bg-primary/10 text-foreground"
                    : "bg-muted text-muted-foreground"
            }`}
          >
            <span
              aria-hidden="true"
              className={`size-1.5 rounded-full ${
                sem
                  ? "bg-muted-foreground/50"
                  : fase === "erro"
                    ? "bg-destructive"
                    : pronto
                      ? "bg-primary"
                      : "animate-pulse bg-muted-foreground"
              }`}
            />
            {sem
              ? "sem janela 3D"
              : fase === "erro" && motivo !== null
                ? `falhou: ${motivo}`
                : TEXTO_FASE[fase]}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          a câmara segue sempre o drone — escolhe de onde olhas: arrasta o ícone
          nas vistas, usa as vistas rápidas ou as setas (com o foco numa vista);
          a roda do rato aproxima/afasta
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {sem ? (
          <p
            className="rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground"
            data-testid="camera-sem-dados"
          >
            sem câmara para comandar: a janela 3D está fechada ou o simulador
            corre sem janela (<code className="font-mono">--sem-janela</code>).
            Abre o <code className="font-mono">sim_site.py</code> sem essa opção
            e o bloco ativa-se sozinho.
          </p>
        ) : null}

        {/* LEITURA — onde está a câmara, em português simples */}
        <dl
          className="grid grid-cols-3 gap-2 rounded-xl bg-muted/40 px-3 py-2"
          data-testid="camera-leitura"
        >
          <div className="flex min-w-0 flex-col">
            <dt className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              onde
            </dt>
            <dd
              className="truncate text-sm font-medium"
              data-testid="camera-onde"
            >
              {descricao?.lado ?? "—"}
            </dd>
          </div>
          <div className="flex min-w-0 flex-col">
            <dt className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              altura
            </dt>
            <dd
              className="truncate text-sm font-medium"
              data-testid="camera-altura"
            >
              {descricao?.altura ?? "—"}
            </dd>
          </div>
          <div className="flex min-w-0 flex-col">
            <dt className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              distância
            </dt>
            <dd
              className="text-sm font-medium tabular-nums"
              data-testid="camera-distancia-valor"
            >
              {valores === null
                ? "—"
                : `${fmt(valores.distancia, valores.distancia < 2 ? 2 : 1)} m`}
            </dd>
          </div>
        </dl>

        {/* AS DUAS VISTAS — de cima (órbita) e de lado (altura) */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Vista
            rotulo="Vista de cima"
            dica="arrasta = rodar à volta"
            testid="camera-topo"
            ativo={ativo}
            valorAgora={relativo === null ? null : Math.round(relativo)}
            valorMin={0}
            valorMax={359}
            valorTexto={
              descricao === null
                ? "sem dados"
                : `câmara ${descricao.lado} do drone`
            }
            svgRef={topoRef}
            onApontar={aoApontar("topo")}
            onArrastar={aoArrastar("topo")}
            onLargar={aoLargar}
            onTecla={aoTeclar}
            rodape={
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  disabled={!ativo}
                  title="rodar a câmara 15° no sentido anti-horário (tecla ←)"
                  aria-label="rodar a câmara 15° no sentido anti-horário"
                  data-testid="camera-orbitar-anti"
                  onClick={() => orbitarPassos(+1, 0)}
                >
                  <RotateCcw aria-hidden="true" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  disabled={!ativo}
                  title="rodar a câmara 15° no sentido horário (tecla →)"
                  aria-label="rodar a câmara 15° no sentido horário"
                  data-testid="camera-orbitar-horario"
                  onClick={() => orbitarPassos(-1, 0)}
                >
                  <RotateCw aria-hidden="true" />
                </Button>
              </>
            }
          >
            <circle
              cx={CENTRO}
              cy={CENTRO}
              r={RAIO_DISCO}
              className="fill-muted/50 stroke-border"
              strokeWidth="1.2"
            />
            <circle
              cx={CENTRO}
              cy={CENTRO}
              r={RAIO_CAMERA_TOPO}
              className="fill-none stroke-border"
              strokeWidth="1"
              strokeDasharray="3 4"
            />
            <circle
              cx={CENTRO}
              cy={CENTRO}
              r={36}
              className="fill-none stroke-border/70"
              strokeWidth="1"
              strokeDasharray="2 4"
            />
            <g className="fill-muted-foreground text-[8px]" textAnchor="middle">
              <text x={CENTRO} y={16}>
                frente
              </text>
              <text x={CENTRO} y={191}>
                trás
              </text>
              <text x={20} y={103}>
                esq.
              </text>
              <text x={180} y={103}>
                dir.
              </text>
            </g>
            {cone !== null ? (
              <polygon points={cone} className="fill-primary/10" />
            ) : null}
            {/* o DRONE com o nariz para cima (frente = topo da vista) */}
            <g
              className="stroke-foreground/80"
              strokeWidth="3"
              strokeLinecap="round"
            >
              <line
                x1={CENTRO - 17}
                y1={CENTRO - 17}
                x2={CENTRO + 17}
                y2={CENTRO + 17}
              />
              <line
                x1={CENTRO + 17}
                y1={CENTRO - 17}
                x2={CENTRO - 17}
                y2={CENTRO + 17}
              />
            </g>
            <g className="fill-muted stroke-foreground/70" strokeWidth="1.5">
              {[
                [-17, -17],
                [17, -17],
                [-17, 17],
                [17, 17],
              ].map(([dx, dy]) => (
                <circle
                  key={`${dx},${dy}`}
                  cx={CENTRO + dx}
                  cy={CENTRO + dy}
                  r={8}
                />
              ))}
            </g>
            <path
              d={`M${CENTRO} ${CENTRO - 30} L${CENTRO - 6} ${CENTRO - 21} L${CENTRO + 6} ${CENTRO - 21} Z`}
              className="fill-foreground/80"
            />
            <circle
              cx={CENTRO}
              cy={CENTRO}
              r={5}
              className="fill-foreground/80"
            />
            {camTopo !== null ? (
              <g
                data-testid="camera-icone-topo"
                data-x={camTopo.x.toFixed(3)}
                data-y={camTopo.y.toFixed(3)}
              >
                <IconeCamera x={camTopo.x} y={camTopo.y} angulo={angTopo} />
              </g>
            ) : null}
          </Vista>

          <Vista
            rotulo="Vista de lado"
            dica="arrasta = subir/descer"
            testid="camera-lado"
            ativo={ativo}
            valorAgora={alturaAng === null ? null : Math.round(alturaAng)}
            valorMin={ALTURA_ANGULAR_UI[0]}
            valorMax={ALTURA_ANGULAR_UI[1]}
            valorTexto={descricao === null ? "sem dados" : descricao.altura}
            svgRef={ladoRef}
            onApontar={aoApontar("lado")}
            onArrastar={aoArrastar("lado")}
            onLargar={aoLargar}
            onTecla={aoTeclar}
            rodape={
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  disabled={!ativo}
                  title="subir a câmara 10° (tecla ↑)"
                  aria-label="subir a câmara 10°"
                  data-testid="camera-subir"
                  onClick={() => orbitarPassos(0, +1)}
                >
                  <ChevronUp aria-hidden="true" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  disabled={!ativo}
                  title="descer a câmara 10° (tecla ↓)"
                  aria-label="descer a câmara 10°"
                  data-testid="camera-descer"
                  onClick={() => orbitarPassos(0, -1)}
                >
                  <ChevronDown aria-hidden="true" />
                </Button>
              </>
            }
          >
            <rect
              x="4"
              y="4"
              width="192"
              height="192"
              rx="14"
              className="fill-muted/50 stroke-border"
              strokeWidth="1.2"
            />
            {chaoY !== null ? (
              <g data-testid="camera-chao">
                <rect
                  x="4"
                  y={chaoY}
                  width="192"
                  height={Math.max(0, 196 - chaoY)}
                  className="fill-muted-foreground/15"
                />
                <line
                  x1="4"
                  y1={chaoY}
                  x2="196"
                  y2={chaoY}
                  className="stroke-muted-foreground/60"
                  strokeWidth="1.2"
                />
                <text
                  x="10"
                  y={Math.min(192, chaoY + 11)}
                  className="fill-muted-foreground text-[9px]"
                >
                  chão
                </text>
              </g>
            ) : null}
            <line
              x1="8"
              y1={DRONE_LADO.y}
              x2="192"
              y2={DRONE_LADO.y}
              className="stroke-border"
              strokeWidth="1"
              strokeDasharray="3 4"
            />
            <polyline
              points={arco.join(" ")}
              className="fill-none stroke-border"
              strokeWidth="1.2"
              strokeDasharray="3 4"
            />
            {camLado !== null ? (
              <line
                x1={camLado.x}
                y1={camLado.y}
                x2={DRONE_LADO.x}
                y2={DRONE_LADO.y}
                className={
                  debaixoDoChao ? "stroke-destructive/60" : "stroke-primary/30"
                }
                strokeWidth="2"
              />
            ) : null}
            {/* o DRONE de perfil (nariz para a direita) */}
            <g className="stroke-foreground/80" strokeLinecap="round">
              <line
                x1={DRONE_LADO.x - 20}
                y1={DRONE_LADO.y}
                x2={DRONE_LADO.x + 20}
                y2={DRONE_LADO.y}
                strokeWidth="3.5"
              />
              <line
                x1={DRONE_LADO.x - 20}
                y1={DRONE_LADO.y - 5}
                x2={DRONE_LADO.x - 20}
                y2={DRONE_LADO.y}
                strokeWidth="2"
              />
              <line
                x1={DRONE_LADO.x + 20}
                y1={DRONE_LADO.y - 5}
                x2={DRONE_LADO.x + 20}
                y2={DRONE_LADO.y}
                strokeWidth="2"
              />
            </g>
            <g className="fill-muted stroke-foreground/70" strokeWidth="1.2">
              <ellipse
                cx={DRONE_LADO.x - 20}
                cy={DRONE_LADO.y - 6}
                rx="12"
                ry="2.2"
              />
              <ellipse
                cx={DRONE_LADO.x + 20}
                cy={DRONE_LADO.y - 6}
                rx="12"
                ry="2.2"
              />
            </g>
            <rect
              x={DRONE_LADO.x - 7}
              y={DRONE_LADO.y - 2}
              width="14"
              height="7"
              rx="2"
              className="fill-foreground/80"
            />
            {camLado !== null ? (
              <g
                data-testid="camera-icone-lado"
                data-x={camLado.x.toFixed(3)}
                data-y={camLado.y.toFixed(3)}
              >
                <IconeCamera
                  x={camLado.x}
                  y={camLado.y}
                  angulo={angLado}
                  alerta={debaixoDoChao}
                />
              </g>
            ) : null}
          </Vista>
        </div>
        {debaixoDoChao ? (
          <p
            className="-mt-2 text-center text-[0.7rem] text-destructive"
            data-testid="camera-aviso-chao"
          >
            a câmara está abaixo do chão (a {fmt(alturaCameraM, 2)} m): sobe-a
            ou aproxima-a
          </p>
        ) : null}

        {/* ZOOM — logarítmico, com −/+ e a roda do rato por cima das vistas */}
        <div className="flex flex-col gap-1.5" data-testid="camera-distancia">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              disabled={!ativo}
              title="afastar (tecla −)"
              aria-label="afastar a câmara"
              data-testid="camera-afastar"
              onClick={() => zoomPassos(-1)}
            >
              <Minus aria-hidden="true" />
            </Button>
            <div
              className="min-w-0 flex-1"
              onPointerDown={() => {
                if (ativo) maquina.comecarArrasto()
              }}
            >
              <Slider
                min={0}
                max={1000}
                step={1}
                value={[
                  valores === null
                    ? 0
                    : Math.round(
                        fracaoDeDistancia(valores.distancia, limites) * 1000
                      ),
                ]}
                disabled={!ativo}
                aria-label="distância da câmara ao drone"
                onValueChange={(v) => {
                  const f = (Array.isArray(v) ? (v[0] ?? 0) : v) / 1000
                  maquina.editarDistancia(
                    Number(distanciaDeFracao(f, limites).toFixed(3))
                  )
                }}
              />
            </div>
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              disabled={!ativo}
              title="aproximar (tecla +)"
              aria-label="aproximar a câmara"
              data-testid="camera-aproximar"
              onClick={() => zoomPassos(+1)}
            >
              <Plus aria-hidden="true" />
            </Button>
          </div>
          <div className="flex justify-between px-10 font-mono text-[0.6rem] text-muted-foreground">
            <span>{fmt(limites[0], 1)} m</span>
            <span>escala logarítmica</span>
            <span>{fmt(limites[1], 0)} m</span>
          </div>
        </div>

        {/* VISTAS RÁPIDAS (relativas ao nariz) + REPOR VISTA */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
            vistas rápidas
            {rumoGraus === null
              ? " (relativas ao rumo 0)"
              : " (relativas ao nariz do drone)"}
          </span>
          <div className="flex flex-wrap gap-1.5" data-testid="camera-vistas">
            {VISTAS_RAPIDAS.map((v) => (
              <Button
                key={v.id}
                type="button"
                variant="outline"
                size="sm"
                className="rounded-full"
                disabled={!ativo}
                title={v.dica}
                data-testid={`camera-vista-${v.id}`}
                onClick={() => maquina.irPara(anguloVistaRapida(v.id, rumo))}
              >
                {v.rotulo}
              </Button>
            ))}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="rounded-full"
              data-testid="camera-repor"
              disabled={sem || !ligado || cameraPadrao === null}
              title="volta à vista com que a janela abriu (camera_padrao) — tecla Home"
              onClick={reporVista}
            >
              <Undo2 aria-hidden="true" />
              Repor vista
            </Button>
          </div>
        </div>

        {/* Valores crus para as provas de DOM (sem parse de vírgulas decimais). */}
        <output
          className="sr-only"
          data-testid="camera-raw"
          data-sem-dados={sem ? "sim" : "nao"}
          data-azimute={sem ? "" : String(valores.azimute)}
          data-elevacao={sem ? "" : String(valores.elevacao)}
          data-distancia={sem ? "" : String(valores.distancia)}
          data-rumo={String(rumo)}
          data-alvo-x={valores?.alvo ? String(valores.alvo[0]) : ""}
          data-alvo-y={valores?.alvo ? String(valores.alvo[1]) : ""}
          data-alvo-z={valores?.alvo ? String(valores.alvo[2]) : ""}
        />

        <details className="group rounded-lg bg-muted/30 px-3 py-2 text-[0.65rem] text-muted-foreground">
          <summary
            className={`cursor-pointer text-xs font-medium text-foreground ${FOCUS_RING}`}
          >
            detalhes técnicos
          </summary>
          <div className="mt-2 flex flex-col gap-1.5">
            <p className="font-mono" data-testid="camera-real">
              câmara real:{" "}
              {valores === null
                ? "—"
                : `azimute ${fmt(valores.azimute, 1)}° · elevação ${fmt(valores.elevacao, 1)}° · distância ${fmt(valores.distancia, 2)} m`}
              {valores?.alvo
                ? ` · alvo (drone) [${fmt(valores.alvo[0], 2)}, ${fmt(valores.alvo[1], 2)}, ${fmt(valores.alvo[2], 2)}]`
                : ""}
              {pos
                ? ` · posição [${fmt(pos[0], 2)}, ${fmt(pos[1], 2)}, ${fmt(pos[2], 2)}]`
                : ""}
            </p>
            <p className="font-mono" data-testid="camera-padrao">
              vista inicial (camera_padrao):{" "}
              {cameraPadrao === null
                ? "—"
                : `azimute ${fmt(cameraPadrao.azimute, 0)}° · elevação ${fmt(cameraPadrao.elevacao, 0)}° · ${fmt(cameraPadrao.distancia, 2)} m`}
              {rumoGraus === null
                ? ""
                : ` · rumo do drone ${fmt(rumoGraus, 1)}°`}
            </p>
            <p>
              convenção do MuJoCo: azimute 0° olha para +x (90° para +y);
              elevação NEGATIVA = câmara por cima; posição = alvo − d·f, f =
              [cos e·cos a, cos e·sin a, sin e]; o alvo é o drone e o backend
              segue-o a cada frame. Envio: POST /api/camera com{" "}
              {"{azimute, elevacao, distancia}"} (subconjunto), ao vivo durante
              o arrasto (1 comando a cada {ATRASO_ENVIO_CAMERA_MS} ms) e um
              comando final ao largar; o rato da janela 3D continua livre entre
              comandos.
            </p>
          </div>
        </details>
      </CardContent>
    </Card>
  )
}
