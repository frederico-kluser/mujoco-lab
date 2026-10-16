/**
 * HUD — os instrumentos sobrepostos à vista (`pointer-events: none`: nunca tapam um clique).
 *
 * DISPOSIÇÃO (convenções das estações de solo — QGroundControl, DJI Pilot — e de fatores humanos):
 *  · barra de CIMA = estado e AVISOS: a pílula (A VOAR · NO CHÃO · CAIU · SEM LIGAÇÃO + MANUAL /
 *    A SEGUIR A BOLA), a fita de rumo e a bateria; os alertas grandes aparecem aqui, por baixo da fita;
 *  · VELOCIDADE à esquerda da mira, ALTITUDE à direita;
 *  · o CENTRO só leva a mira, o horizonte e o retículo da bola — nenhum texto (um HUD cheio ao centro
 *    atrasa a deteção do que acontece na cena);
 *  · em baixo à direita: o vento que a física leva AGORA e as teclas premidas.
 *
 * COR: seis cores com significado e nunca só cor — branco leitura · verde ● ativo · ciano = o que o
 * piloto manda (teclas cheias) · magenta = o alvo (a bola) · âmbar ▲ atenção · vermelho ■ perigo.
 *
 * DESEMPENHO: o React só desenha a ESTRUTURA (e o que muda devagar: estado, alertas, teclas). Tudo o
 * que mexe com a amostra de 50 Hz é escrito por refs dentro do `requestAnimationFrame` do HUD
 * (`useDesenhoHud`): `transform`/`opacity` em todos os quadros, `textContent` a ≤ 10 Hz. Nada mede o
 * DOM por quadro — a geometria (viewport, focal) vem das props e só muda no `resize`.
 *
 * Os instrumentos mostram `est` (o que os SENSORES de bordo dizem), sempre a amostra mais recente. O
 * horizonte e o retículo são CONFORMES — assentam na imagem: projetam-se com a focal da câmara e com
 * a amostra do instante em que o quadro foi captado (a câmara entrega ~116 ms depois). A diferença
 * que sobrar entre a linha e o horizonte da imagem é o erro real do estimador de bordo.
 */

import { useEffect, useMemo, useRef, type ReactNode, type RefObject } from "react"

import { COR_TOM, FormaTom, Marca, Tecla } from "@/components/cockpit/pecas"
import type { Vista } from "@/hooks/use-cockpit"
import { useDesenhoHud, useResumoHud } from "@/hooks/use-cockpit"
import {
  ESTADOS_VOO,
  FOVY_BORDO_OMISSAO,
  ROTULO_DE_ONDE,
  ROTULO_SEGUIDOR,
  TOM_SEGUIDOR,
  erroCentragem,
  fmtAutonomia,
  fmtHud,
  fmtRumo,
  LARGURA_FLANCO_HUD,
  flancoHud,
  focalNaVista,
  horizonteNaVista,
  instrumentos,
  limitar,
  projetarNaVista,
  ventoNoNariz,
  yawNoMundo,
  type EstadoPiloto,
  type EstadoTiro,
  type Par,
  type ResumoHud,
  type Tamanho,
  type TomEstado,
} from "@/lib/cockpit"
import { tiro as controloTiro } from "@/lib/cockpit-controlos"
import { hud as hudAoVivo, type QuadroHud } from "@/lib/hud-store"

// --------------------------------------------------------------------------------- escrita por refs

/** `textContent` só quando muda (não invalida o texto a cada quadro). */
function escrever(ref: RefObject<HTMLElement | null>, texto: string): void {
  const el = ref.current
  if (el !== null && el.textContent !== texto) el.textContent = texto
}

/**
 * O último valor escrito em cada elemento. Comparar com `el.style.transform` não serve: o browser
 * devolve o valor normalizado (`translate3d(1px, 0px, 0px)`), nunca igual ao texto que se escreveu —
 * e o estilo era reescrito em todos os quadros mesmo com o drone parado.
 */
const transformEscrito = new WeakMap<Element, string>()
const opacidadeEscrita = new WeakMap<Element, boolean>()

function transformar(
  ref: RefObject<HTMLElement | SVGElement | null>,
  valor: string
): void {
  const el = ref.current
  if (el === null || transformEscrito.get(el) === valor) return
  transformEscrito.set(el, valor)
  el.style.transform = valor
}

function mostrar(
  ref: RefObject<HTMLElement | SVGElement | null>,
  visivel: boolean
): void {
  const el = ref.current
  if (el === null || opacidadeEscrita.get(el) === visivel) return
  opacidadeEscrita.set(el, visivel)
  el.style.opacity = visivel ? "1" : "0"
}

// --------------------------------------------------------------------------------- fita de rumo

/** Píxeis por grau da fita. */
const PX_POR_GRAU = 4
/** A fita desenha de −60° a 420°: com ±52° visíveis dá a volta completa sem costuras. */
const FITA_MIN = -60
const FITA_MAX = 420

/**
 * A fita de rumo (estática): traços de 5 em 5°, maiores de 10 em 10 e número de 30 em 30. Os valores
 * CRESCEM PARA A ESQUERDA — rodar à esquerda (Z) aumenta o rumo, como o azimute do vento e da câmara.
 */
function FitaRumo() {
  const marcas = useMemo(() => {
    const lista: ReactNode[] = []
    for (let v = FITA_MIN; v <= FITA_MAX; v += 5) {
      const x = (FITA_MAX - v) * PX_POR_GRAU
      const grande = v % 10 === 0
      lista.push(
        <line
          key={`t${v}`}
          x1={x}
          x2={x}
          y1={grande ? 12 : 16}
          y2={22}
          strokeWidth={grande ? 1.6 : 1.1}
        />
      )
      if (v % 30 === 0) {
        lista.push(
          <text key={`n${v}`} x={x} y={9} textAnchor="middle">
            {String(((v % 360) + 360) % 360).padStart(3, "0")}
          </text>
        )
      }
    }
    return lista
  }, [])
  return (
    <svg
      width={(FITA_MAX - FITA_MIN) * PX_POR_GRAU}
      height={24}
      aria-hidden="true"
      className="block overflow-visible [filter:drop-shadow(0_0_1.5px_#000)_drop-shadow(0_0_1px_#000)]"
    >
      <g
        stroke="var(--hud)"
        strokeLinecap="round"
        fill="var(--hud)"
        fontFamily="var(--font-mono)"
        fontSize={10}
        fontWeight={700}
        className="[&_text]:stroke-none"
      >
        {marcas}
      </g>
    </svg>
  )
}

// --------------------------------------------------------------------------------- alertas (barra de cima)

interface Alerta {
  tom: TomEstado
  titulo: string
  texto: string
}

/** O alerta mais grave em vigor (um de cada vez: dois avisos grandes a competir não se leem). */
function alertaEmVigor(resumo: ResumoHud): Alerta | null {
  if (resumo.estado === "caiu")
    return {
      tom: "perigo",
      titulo: "CAIU",
      texto: "manter R para reiniciar",
    }
  if (resumo.estado === "sem_ligacao")
    return {
      tom: "atencao",
      titulo: "SEM LIGAÇÃO",
      texto: "o simulador deixou de enviar dados — os instrumentos estão parados",
    }
  if (resumo.bateria === "critica")
    return {
      tom: "perigo",
      titulo: "BATERIA CRÍTICA",
      texto: "pousar já",
    }
  if (resumo.bateria === "fraca")
    return {
      tom: "atencao",
      titulo: "BATERIA FRACA",
      texto: "pousar em breve",
    }
  if (resumo.seguidor === "perdida")
    return {
      tom: "atencao",
      titulo: "BOLA PERDIDA",
      texto: "o detetor de bordo deixou de a ver",
    }
  return null
}

// --------------------------------------------------------------------------------- o HUD

export interface HudProps {
  vista: Vista
  /** A vista tem imagem? Sem ela não se desenha o que assenta na imagem (horizonte, mira, retículo). */
  comImagem: boolean
  piloto: EstadoPiloto
  tiro?: EstadoTiro
  viewport: Tamanho
  /** Resolução do stream da câmara de bordo (px) — a escala do `object-fit: cover`. */
  imagemBordo: Par | null
  /**
   * Há quanto tempo foi captado o quadro à vista (ms — `atrasoDaImagem`: latência do módulo + meio
   * período do stream): o horizonte e o retículo desenham-se com a amostra desse instante, para
   * assentarem na imagem que se está a ver.
   */
  atrasoImagemMs: number
}

const ESCADA: readonly { graus: number; meio: number }[] = [
  { graus: 10, meio: 70 },
  { graus: 20, meio: 48 },
  { graus: -10, meio: 70 },
  { graus: -20, meio: 48 },
]
/** Velocidade horizontal que põe o ponto da deriva na borda do mostrador (m/s). */
const DERIVA_MAX_M_S = 2
/** Velocidade vertical que enche a barra (m/s). */
const VERTICAL_MAX_M_S = 1.5

export function Hud({
  vista,
  comImagem,
  piloto,
  tiro,
  viewport,
  imagemBordo,
  atrasoImagemMs,
}: HudProps) {
  const resumo = useResumoHud()
  const emFpv = vista === "fpv" && comImagem

  // ------------------------------------------------------------- geometria (só muda no resize)
  const fovy = resumo.fovy ?? FOVY_BORDO_OMISSAO
  const vistaPx: Par = useMemo(
    () => [viewport.largura, viewport.altura],
    [viewport.largura, viewport.altura]
  )
  // Sem a resolução do stream assume-se a proporção da própria vista (escala neutra).
  const focal = focalNaVista(fovy, imagemBordo ?? vistaPx, vistaPx)
  const larguraFita = Math.round(
    limitar(viewport.largura * 0.3, 240, 380)
  )
  // As leituras dos flancos ficam fora da coluna onde as janelas abrem (300 px + margens) e o traço do
  // horizonte cabe entre as duas (a geometria vive em `lib/cockpit.ts`: é a que as janelas evitam).
  const flanco = flancoHud(viewport.largura)
  const horizonteMeio = limitar(
    viewport.largura / 2 - flanco - LARGURA_FLANCO_HUD,
    120,
    300
  )
  const geometria = useRef({
    focal,
    vista: vistaPx,
    larguraFita,
    emFpv,
    atrasoImagemMs,
  })
  useEffect(() => {
    geometria.current = {
      focal,
      vista: vistaPx,
      larguraFita,
      emFpv,
      atrasoImagemMs,
    }
  }, [focal, vistaPx, larguraFita, emFpv, atrasoImagemMs])

  // ------------------------------------------------------------- refs dos instrumentos
  const rFita = useRef<HTMLDivElement>(null)
  const rRumo = useRef<HTMLSpanElement>(null)
  const rVel = useRef<HTMLSpanElement>(null)
  const rDeriva = useRef<HTMLSpanElement>(null)
  const rAlt = useRef<HTMLSpanElement>(null)
  const rVz = useRef<HTMLSpanElement>(null)
  const rVzSeta = useRef<HTMLSpanElement>(null)
  const rVzBarra = useRef<HTMLSpanElement>(null)
  const rBatPct = useRef<HTMLSpanElement>(null)
  const rBatNivel = useRef<HTMLSpanElement>(null)
  const rBatV = useRef<HTMLSpanElement>(null)
  const rBatMin = useRef<HTMLSpanElement>(null)
  const rVentoSeta = useRef<SVGGElement>(null)
  const rVentoVel = useRef<HTMLSpanElement>(null)
  const rVentoDe = useRef<HTMLSpanElement>(null)
  const rRajada = useRef<HTMLSpanElement>(null)
  const rHorizonte = useRef<HTMLDivElement>(null)
  const rReticulo = useRef<HTMLDivElement>(null)
  /** Os 4 cantos do retículo (cima-esq, cima-dir, baixo-dir, baixo-esq): afastam-se com o tamanho da bola. */
  const rCanto0 = useRef<HTMLSpanElement>(null)
  const rCanto1 = useRef<HTMLSpanElement>(null)
  const rCanto2 = useRef<HTMLSpanElement>(null)
  const rCanto3 = useRef<HTMLSpanElement>(null)
  const rLinha = useRef<HTMLDivElement>(null)
  const rBolaTexto = useRef<HTMLSpanElement>(null)
  const rTiroContagem = useRef<HTMLSpanElement>(null)
  const rTiroSoco = useRef<HTMLSpanElement>(null)
  const rTiroRecuo = useRef<HTMLSpanElement>(null)
  const rMiraImpacto = useRef<HTMLDivElement>(null)
  const rMiraEstado = useRef<HTMLSpanElement>(null)
  const rTiroResultado = useRef<HTMLSpanElement>(null)
  const rFpsBadge = useRef<HTMLSpanElement>(null)

  useDesenhoHud((quadro: QuadroHud) => {
    const { hud, texto } = quadro
    const g = geometria.current
    const ins = instrumentos(hud)

    // ---- todos os quadros: só transform/opacity ------------------------------------------
    if (ins.rumo !== null) {
      transformar(
        rFita,
        `translate3d(${(g.larguraFita / 2 - (FITA_MAX - ins.rumo) * PX_POR_GRAU).toFixed(1)}px,0,0)`
      )
    }
    if (ins.vFrente !== null && ins.vEsquerda !== null) {
      // Deriva vista de cima com o nariz para cima: frente = cima, esquerda = esquerda.
      const k = 18 / DERIVA_MAX_M_S
      const dx = limitar(-ins.vEsquerda * k, -18, 18)
      const dy = limitar(-ins.vFrente * k, -18, 18)
      transformar(rDeriva, `translate3d(${dx.toFixed(1)}px,${dy.toFixed(1)}px,0)`)
    }
    if (ins.vVertical !== null) {
      const f = limitar(ins.vVertical / VERTICAL_MAX_M_S, -1, 1)
      // A barra cresce do meio: para cima a subir, para baixo a descer.
      transformar(rVzBarra, `scaleY(${f.toFixed(3)})`)
    }
    const bateria = hud?.bateria ?? null
    if (bateria?.soc != null) {
      transformar(rBatNivel, `scaleX(${limitar(bateria.soc, 0, 1).toFixed(3)})`)
    }
    const vento = ventoNoNariz(hud?.vento ?? null, yawNoMundo(hud))
    if (vento.angulo !== null) {
      // A seta desenha-se a apontar para CIMA (empurra para a frente); o ângulo cresce para a esquerda.
      transformar(rVentoSeta, `rotate(${(-vento.angulo).toFixed(1)}deg)`)
    }
    mostrar(rVentoSeta, vento.angulo !== null)
    mostrar(rRajada, hud?.rajada === true)
    mostrar(rTiroRecuo, hud?.tiro?.emRecuo === true)

    // Os símbolos que assentam na IMAGEM usam a amostra do instante em que o quadro foi captado.
    const naImagem = g.emFpv ? hudAoVivo.deHa(g.atrasoImagemMs) : null
    const atitude = instrumentos(naImagem)
    if (g.emFpv && atitude.roll !== null && atitude.pitch !== null) {
      const hz = horizonteNaVista(atitude.roll, atitude.pitch, g.focal)
      transformar(
        rHorizonte,
        `rotate(${hz.rotacaoGraus.toFixed(2)}deg) translate3d(0,${hz.deslocamentoPx.toFixed(1)}px,0)`
      )
      mostrar(rHorizonte, true)
    } else {
      mostrar(rHorizonte, false)
    }

    const bola = hud?.bola ?? null
    const bolaNaImagem = naImagem?.bola ?? null
    const alvo =
      bolaNaImagem !== null &&
      bolaNaImagem.seguir &&
      bolaNaImagem.valido &&
      bolaNaImagem.erroTan !== null
        ? projetarNaVista(bolaNaImagem.erroTan, g.focal, g.vista)
        : null
    if (alvo !== null && bolaNaImagem !== null) {
      // Fora da vista (ecrã muito largo corta em cima/baixo): o retículo encosta à borda.
      const x = limitar(alvo.x, 24, g.vista[0] - 24)
      const y = limitar(alvo.y, 24, g.vista[1] - 24)
      const meio = Math.max(16, (bolaNaImagem.raioTan ?? 0) * g.focal * 1.9)
      transformar(rReticulo, `translate3d(${x.toFixed(1)}px,${y.toFixed(1)}px,0)`)
      // O retículo cresce AFASTANDO os cantos (o traço fica sempre com a mesma espessura): um `scale`
      // engrossava-o com a bola perto.
      const m = meio.toFixed(1)
      transformar(rCanto0, `translate3d(-${m}px,-${m}px,0)`)
      transformar(rCanto1, `translate3d(${m}px,-${m}px,0)`)
      transformar(rCanto2, `translate3d(${m}px,${m}px,0)`)
      transformar(rCanto3, `translate3d(-${m}px,${m}px,0)`)
      const dx = x - g.vista[0] / 2
      const dy = y - g.vista[1] / 2
      const comprimento = Math.hypot(dx, dy) - meio - 14
      transformar(
        rLinha,
        `rotate(${((Math.atan2(dy, dx) * 180) / Math.PI).toFixed(2)}deg) translate3d(14px,0,0) scaleX(${Math.max(0, comprimento).toFixed(1)})`
      )
      mostrar(rLinha, comprimento > 4)
    } else {
      mostrar(rLinha, false)
    }
    mostrar(rReticulo, alvo !== null)

    // Marcador de ONDE O TIRO VAI PEGAR (mira balística da Glock 25 no visor FPS)
    const miraImagem = naImagem?.tiro?.mira ?? hud?.tiro?.mira ?? null
    const pontoImp =
      g.emFpv && miraImagem !== null && miraImagem.pontoImpactoTan !== null
        ? projetarNaVista(miraImagem.pontoImpactoTan, g.focal, g.vista)
        : null
    if (pontoImp !== null && miraImagem !== null) {
      const ix = limitar(pontoImp.x, 30, g.vista[0] - 30)
      const iy = limitar(pontoImp.y, 30, g.vista[1] - 30)
      transformar(rMiraImpacto, `translate3d(${ix.toFixed(1)}px,${iy.toFixed(1)}px,0)`)
      mostrar(rMiraImpacto, true)
    } else {
      mostrar(rMiraImpacto, false)
    }

    // ---- ≤ 10 Hz: os números ---------------------------------------------------------------
    if (!texto) return
    escrever(rRumo, fmtRumo(ins.rumo))
    escrever(rVel, fmtHud(ins.vHorizontal, 1))
    escrever(rAlt, fmtHud(ins.altitude, 2))
    escrever(rVz, fmtHud(ins.vVertical === null ? null : Math.abs(ins.vVertical), 1))
    escrever(
      rVzSeta,
      ins.vVertical === null || Math.abs(ins.vVertical) < 0.05
        ? "■"
        : ins.vVertical > 0
          ? "▲"
          : "▼"
    )
    escrever(
      rBatPct,
      bateria?.soc == null ? "—" : String(Math.round(bateria.soc * 100))
    )
    escrever(rBatV, fmtHud(bateria?.v, 1))
    escrever(rBatMin, fmtAutonomia(bateria?.autonomiaMin))
    escrever(rVentoVel, fmtHud(vento.vel, 1))
    escrever(
      rVentoDe,
      vento.de === null
        ? vento.vel < 0.05
          ? "SEM VENTO"
          : "—"
        : ROTULO_DE_ONDE[vento.de]
    )
    const erro = erroCentragem(bola)
    escrever(
      rBolaTexto,
      erro === null
        ? "sem deteção"
        : `erro ${fmtHud(erro.graus, 1)}°${erro.px === null ? "" : ` · ${fmtHud(erro.px, 0)} px`}${
            bola?.dist == null ? "" : ` · a ${fmtHud(bola.dist, 1)} m`
          }`
    )
    const tHud = hud?.tiro ?? null
    escrever(
      rTiroContagem,
      tHud === null ? "0" : `${tHud.tiros} (${tHud.acertosBola}✓)`
    )
    escrever(
      rTiroSoco,
      tHud === null || tHud.impulsoNs === null
        ? "1,92 N·s"
        : `${fmtHud(tHud.impulsoNs, 2)} N·s · −${fmtHud(tHud.deltaVTeoricoMS, 2)} m/s`
    )
    const mira = tHud?.mira ?? null
    if (rMiraEstado.current !== null) {
      const erroCm =
        mira?.erroBolaM != null ? ` (${fmtHud(mira.erroBolaM * 100, 1)} cm)` : ""
      const txtMira =
        mira === null
          ? "—"
          : mira.noAlvo
            ? `NO ALVO${erroCm}`
            : `FORA DO ALVO${erroCm}`
      if (rMiraEstado.current.textContent !== txtMira) {
        rMiraEstado.current.textContent = txtMira
        rMiraEstado.current.dataset.noAlvo = mira?.noAlvo ? "sim" : "nao"
      }
    }
    if (rTiroResultado.current !== null) {
      const resUlt = tHud?.ultimoResultado ?? null
      const txtRes =
        tHud === null || tHud.tiros === 0
          ? "pronto [SPACE]"
          : resUlt === "acertou_bola"
            ? `ACERTOU A BOLA! (${tHud.acertosBola}/${tHud.tiros})`
            : resUlt === "em_voo"
              ? `EM VOO… (${tHud.acertosBola}/${tHud.tiros})`
              : `ERROU A BOLA (${tHud.acertosBola}/${tHud.tiros})`
      if (rTiroResultado.current.textContent !== txtRes)
        rTiroResultado.current.textContent = txtRes
    }
    if (rFpsBadge.current !== null) {
      const fpsVal = hud?.graficos?.fpsAtual ?? null
      const txtFps = fpsVal != null ? `${fmtHud(fpsVal, 0)} FPS` : "50 FPS"
      if (rFpsBadge.current.textContent !== txtFps)
        rFpsBadge.current.textContent = txtFps
    }
  })

  // A pílula vem do resumo (lento): o texto e o tom por estado, sem tocar na amostra de 50 Hz.
  const pilula = ESTADOS_VOO[resumo.estado]
  const alerta = alertaEmVigor(resumo)
  const vivo = resumo.ligacao === "ligado"
  const aSeguir = resumo.modo === "bola"
  // As teclas mandam? Não quando a bola pilota, nem quando a política em uso não aceita comandos.
  const teclasEmEspera = aSeguir || !resumo.aceitaComandos

  return (
    <div
      data-testid="hud"
      data-vivo={vivo ? "sim" : "nao"}
      className="pointer-events-none absolute inset-0 z-10 overflow-hidden select-none"
    >
      {/* Véus em cima e em baixo: dão contraste ao texto sem caixas a tapar a vista. */}
      <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-black/60 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-36 bg-gradient-to-t from-black/55 to-transparent" />

      {/* ------------------------------------------------ barra de cima: estado · rumo · bateria */}
      <div className="absolute top-3 left-3 flex flex-col items-start gap-1.5">
        <div
          data-testid="hud-estado"
          data-estado={resumo.estado}
          data-modo={resumo.modo ?? ""}
          role="status"
          className={`vidro flex h-9 items-center gap-2.5 rounded-xl px-3 font-etiqueta text-[0.82rem] font-bold tracking-[0.14em] ${COR_TOM[pilula.tom]}`}
        >
          <FormaTom tom={pilula.tom} className="size-3" />
          <span data-testid="hud-fase">{pilula.texto}</span>
          {resumo.modo !== null ? (
            <>
              <span aria-hidden="true" className="h-4 w-px bg-white/25" />
              <span
                data-testid="hud-modo"
                className={aSeguir ? "text-hud-magenta" : "text-hud"}
              >
                {aSeguir ? "A SEGUIR A BOLA" : "MANUAL"}
              </span>
            </>
          ) : null}
          <span aria-hidden="true" className="h-4 w-px bg-white/25" />
          <span
            ref={rFpsBadge}
            data-testid="hud-fps-atual"
            className="font-mono text-[0.75rem] text-emerald-400"
          >
            50 FPS
          </span>
        </div>
        {aSeguir ? (
          <div
            data-testid="hud-bola"
            data-seguidor={resumo.seguidor}
            className="osd flex items-center gap-2 pl-1 text-[0.72rem]"
          >
            <Marca tom={TOM_SEGUIDOR[resumo.seguidor]} testid="hud-seguidor">
              {ROTULO_SEGUIDOR[resumo.seguidor]}
            </Marca>
            <span ref={rBolaTexto} data-testid="hud-bola-erro" />
          </div>
        ) : null}
      </div>

      <div
        className="absolute top-3 left-1/2 flex -translate-x-1/2 flex-col items-center"
        style={{ opacity: vivo ? 1 : 0.45 }}
      >
        <div
          className="relative h-6 overflow-hidden [mask-image:linear-gradient(to_right,transparent,#000_18%,#000_82%,transparent)]"
          style={{ width: larguraFita }}
        >
          <div ref={rFita} className="absolute top-0 left-0 will-change-transform">
            <FitaRumo />
          </div>
        </div>
        {/* O ponteiro fixo da fita e a leitura por baixo. */}
        <svg width="14" height="8" viewBox="0 0 14 8" aria-hidden="true" className="-mt-0.5">
          <path d="M7 0.5 12.5 7.5H1.5Z" fill="var(--hud)" stroke="#000" strokeWidth="1" />
        </svg>
        <div className="osd mt-0.5 flex items-baseline gap-1.5">
          <span className="text-[0.65rem] font-bold tracking-[0.18em] opacity-80">
            RUMO
          </span>
          <span className="text-lg leading-none font-bold">
            <span ref={rRumo} data-testid="hud-rumo">
              —
            </span>
            °
          </span>
        </div>
      </div>

      {resumo.temBateria ? (
        <div
          data-testid="hud-bateria"
          data-alerta={resumo.bateria}
          className={`osd absolute top-3 right-3 flex h-9 items-center gap-3 text-[0.8rem] ${
            resumo.bateria === "critica"
              ? "!text-hud-vermelho"
              : resumo.bateria === "fraca"
                ? "!text-hud-ambar"
                : ""
          }`}
          style={{ opacity: vivo ? 1 : 0.45 }}
        >
          {resumo.bateria !== "nenhum" ? (
            <span className="flex items-center gap-1 font-bold tracking-[0.12em]">
              <FormaTom tom={resumo.bateria === "critica" ? "perigo" : "atencao"} />
              {resumo.bateria === "critica" ? "CRÍTICA" : "FRACA"}
            </span>
          ) : null}
          <span className="flex items-center gap-1.5">
            {/* Pilha: contorno + nível (scaleX) + o borne. */}
            <span className="relative flex h-3.5 w-8 items-stretch rounded-[3px] border-[1.5px] border-current p-[1.5px] shadow-[0_0_2px_#000]">
              <span
                ref={rBatNivel}
                className="block w-full origin-left rounded-[1px] bg-current"
              />
              <span className="absolute top-1/2 -right-[4px] h-1.5 w-[2.5px] -translate-y-1/2 rounded-r-[1px] bg-current" />
            </span>
            <span className="text-base leading-none font-bold">
              <span ref={rBatPct} data-testid="hud-bateria-pct">
                —
              </span>
              <span className="text-[0.7rem]"> %</span>
            </span>
          </span>
          <span>
            <span ref={rBatV} data-testid="hud-bateria-v">
              —
            </span>{" "}
            V
          </span>
          <span ref={rBatMin} data-testid="hud-bateria-autonomia">
            —
          </span>
        </div>
      ) : null}

      {/* Alertas: grandes, por baixo da fita de rumo (zona de avisos), com forma + texto. */}
      {alerta !== null ? (
        <div
          role="alert"
          data-testid="hud-alerta"
          data-tom={alerta.tom}
          className={`vidro absolute top-[5.25rem] left-1/2 flex -translate-x-1/2 items-center gap-4 rounded-2xl border-2 px-6 py-3 whitespace-nowrap ${
            alerta.tom === "perigo"
              ? "border-hud-vermelho text-hud-vermelho"
              : "border-hud-ambar text-hud-ambar"
          }`}
        >
          <FormaTom tom={alerta.tom} className="alerta-pulsa size-6" />
          <span className="font-etiqueta text-[2rem] leading-none font-bold tracking-[0.14em]">
            {alerta.titulo}
          </span>
          <span className="text-base text-hud">{alerta.texto}</span>
        </div>
      ) : null}

      {/* ------------------------------------------------ flancos: velocidade (esq.) e altitude (dir.) */}
      <div
        data-testid="hud-velocidade"
        className="osd absolute top-1/2 flex -translate-y-1/2 items-center gap-3"
        style={{ left: flanco, opacity: vivo ? 1 : 0.45 }}
      >
        <div className="flex flex-col items-end">
          <span className="text-[0.65rem] font-bold tracking-[0.18em] opacity-80">
            VEL
          </span>
          <span className="text-[2rem] leading-none font-bold">
            <span ref={rVel} data-testid="hud-vel">
              —
            </span>
          </span>
          <span className="text-[0.65rem] opacity-80">m/s</span>
        </div>
        {/* Deriva: para onde o drone se desloca, visto de cima com o nariz para cima. */}
        <span
          className="relative block size-11 rounded-full border border-white/55 shadow-[0_0_2px_#000,inset_0_0_2px_#000]"
          title="para onde o drone se desloca (nariz para cima)"
        >
          <span className="absolute top-1/2 left-1/2 h-px w-2.5 -translate-x-1/2 bg-white/60" />
          <span className="absolute top-1/2 left-1/2 h-2.5 w-px -translate-y-1/2 bg-white/60" />
          <span className="absolute top-1/2 left-1/2 -mt-1 -ml-1 block size-2">
            <span
              ref={rDeriva}
              className="block size-2 rounded-full bg-hud shadow-[0_0_3px_#000] will-change-transform"
            />
          </span>
        </span>
      </div>

      <div
        data-testid="hud-altitude"
        className="osd absolute top-1/2 flex -translate-y-1/2 items-center gap-3"
        style={{ right: flanco, opacity: vivo ? 1 : 0.45 }}
      >
        {/* Velocidade vertical: barra que cresce do meio (para cima a subir). */}
        <span className="relative block h-11 w-1.5 rounded-full bg-white/20 shadow-[0_0_2px_#000]">
          <span className="absolute top-1/2 -left-0.5 h-px w-2.5 bg-white/70" />
          <span className="absolute top-0 left-0 block h-1/2 w-full">
            <span
              ref={rVzBarra}
              className="block size-full origin-bottom rounded-full bg-hud will-change-transform"
              style={{ transform: "scaleY(0)" }}
            />
          </span>
        </span>
        <div className="flex flex-col items-start">
          <span className="text-[0.65rem] font-bold tracking-[0.18em] opacity-80">
            ALT
          </span>
          <span className="text-[2rem] leading-none font-bold">
            <span ref={rAlt} data-testid="hud-alt">
              —
            </span>
            <span className="text-sm"> m</span>
          </span>
          <span className="flex items-baseline gap-1 text-[0.7rem]">
            <span ref={rVzSeta} className="text-[0.65rem]">
              ■
            </span>
            <span ref={rVz} data-testid="hud-vz">
              —
            </span>
            <span className="opacity-80">m/s</span>
          </span>
        </div>
      </div>

      {/* ------------------------------------------------ centro: mira + horizonte (só em 1.ª pessoa) */}
      {emFpv ? (
        <div className="absolute inset-0" style={{ opacity: vivo ? 1 : 0.45 }}>
          <div
            ref={rHorizonte}
            data-testid="hud-horizonte"
            className="absolute top-1/2 left-1/2 size-0 will-change-transform"
            style={{ opacity: 0 }}
          >
            <svg
              width="1"
              height="1"
              aria-hidden="true"
              className="absolute top-0 left-0 overflow-visible [filter:drop-shadow(0_0_1.5px_#000)_drop-shadow(0_0_1px_#000)]"
            >
              <g stroke="var(--hud)" strokeLinecap="round" fill="none">
                {/* O horizonte: aberto ao meio para não riscar a mira. */}
                <line x1={-horizonteMeio} x2={-64} y1={0} y2={0} strokeWidth={1.8} />
                <line x1={64} x2={horizonteMeio} y1={0} y2={0} strokeWidth={1.8} />
                {/* Escada de pitch: ±10° e ±20° (distinguem-se pelo comprimento; abaixo do horizonte
                    são tracejadas). Sem números — o centro não leva texto. */}
                {ESCADA.map(({ graus, meio }) => {
                  const y = -Math.tan((graus * Math.PI) / 180) * focal
                  return (
                    <g
                      key={graus}
                      strokeOpacity={0.75}
                      strokeDasharray={graus < 0 ? "7 6" : undefined}
                    >
                      <line x1={-meio} x2={-22} y1={y} y2={y} strokeWidth={1.3} />
                      <line x1={22} x2={meio} y1={y} y2={y} strokeWidth={1.3} />
                    </g>
                  )
                })}
              </g>
            </svg>
          </div>
          {/* A mira (o eixo da câmara): fixa no centro exato da vista. */}
          <svg
            data-testid="hud-mira"
            width="96"
            height="40"
            viewBox="-48 -20 96 40"
            aria-hidden="true"
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 overflow-visible [filter:drop-shadow(0_0_1.5px_#000)_drop-shadow(0_0_1px_#000)]"
          >
            <g stroke="var(--hud)" strokeWidth="2" strokeLinecap="round" fill="none">
              <path d="M-44 0H-16L-8 9 0 0 8 9 16 0H44" />
              <circle cx="0" cy="0" r="1.6" fill="var(--hud)" stroke="none" />
            </g>
          </svg>
          {/* Retículo SOBRE a bola (o que o detetor de bordo vê) + a linha até à mira. */}
          <div
            ref={rLinha}
            data-testid="hud-linha-bola"
            className="absolute top-1/2 left-1/2 h-[2px] w-px origin-left bg-hud-magenta shadow-[0_0_2px_#000] will-change-transform"
            style={{ opacity: 0 }}
          />
          <div
            ref={rReticulo}
            data-testid="hud-reticulo"
            className="absolute top-0 left-0 size-0 will-change-transform"
            style={{ opacity: 0 }}
          >
            {/* Cada canto é um «L» de 14 px com contorno escuro; a posição vem do desenhador. */}
            <span
              ref={rCanto0}
              className="absolute top-0 left-0 block size-3.5 border-t-[3px] border-l-[3px] border-hud-magenta shadow-[-1px_-1px_0_#000] will-change-transform"
            />
            <span
              ref={rCanto1}
              className="absolute top-0 -left-3.5 block size-3.5 border-t-[3px] border-r-[3px] border-hud-magenta shadow-[1px_-1px_0_#000] will-change-transform"
            />
            <span
              ref={rCanto2}
              className="absolute -top-3.5 -left-3.5 block size-3.5 border-r-[3px] border-b-[3px] border-hud-magenta shadow-[1px_1px_0_#000] will-change-transform"
            />
            <span
              ref={rCanto3}
              className="absolute -top-3.5 left-0 block size-3.5 border-b-[3px] border-l-[3px] border-hud-magenta shadow-[-1px_1px_0_#000] will-change-transform"
            />
          </div>
          {/* PONTO DE IMPACTO DO TIRO (mira balística da Glock 25 no visor FPS) + mensagem NO ALVO / FORA DO ALVO */}
          <div
            ref={rMiraImpacto}
            data-testid="hud-mira-impacto"
            className="absolute top-0 left-0 size-0 will-change-transform"
            style={{ opacity: 0 }}
          >
            <svg
              width="36"
              height="36"
              viewBox="-18 -18 36 36"
              aria-hidden="true"
              className="-translate-x-1/2 -translate-y-1/2 overflow-visible [filter:drop-shadow(0_0_2px_#000)]"
            >
              <circle
                cx="0"
                cy="0"
                r="10"
                fill="none"
                stroke="#22c55e"
                strokeWidth="2"
                strokeDasharray="4 2"
              />
              <path
                d="M-15 0H-5M5 0H15M0 -15V-5M0 5V15"
                stroke="#22c55e"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <circle cx="0" cy="0" r="2.5" fill="#22c55e" />
            </svg>
            <span
              ref={rMiraEstado}
              data-testid="hud-estado-mira"
              data-no-alvo="nao"
              className="absolute top-3 left-1/2 -translate-x-1/2 rounded bg-black/80 px-1.5 py-0.5 font-mono text-[0.65rem] font-bold tracking-wider whitespace-nowrap text-emerald-400 shadow"
            >
              FORA DO ALVO
            </span>
          </div>
        </div>
      ) : null}

      {/* ------------------------------------------------ em baixo à direita: vento agora + teclas */}
      <div
        className="absolute right-3 bottom-3 flex items-end gap-4"
        style={{ opacity: vivo ? 1 : 0.45 }}
      >
        <div data-testid="hud-vento" className="osd flex items-center gap-2.5 pb-0.5">
          <svg
            width="46"
            height="46"
            viewBox="-23 -23 46 46"
            aria-hidden="true"
            className="[filter:drop-shadow(0_0_1.5px_#000)]"
          >
            <circle r="21" fill="rgb(0 0 0 / 0.3)" stroke="var(--hud)" strokeOpacity="0.55" strokeWidth="1.2" />
            {/* O nariz do drone (referência fixa): para cima. */}
            <path d="M0 -21V-16" stroke="var(--hud)" strokeWidth="1.6" strokeLinecap="round" />
            <g ref={rVentoSeta} style={{ opacity: 0, transformOrigin: "0 0" }}>
              <path
                d="M0 13V-11M-6 -5 0 -12 6 -5"
                fill="none"
                stroke="var(--hud)"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </g>
          </svg>
          <div className="flex flex-col">
            <span className="flex items-center gap-2 text-[0.65rem] font-bold tracking-[0.18em]">
              <span className="opacity-80">VENTO</span>
              <span
                ref={rRajada}
                data-testid="hud-rajada"
                className="flex items-center gap-1 text-hud-ambar"
                style={{ opacity: 0 }}
              >
                <FormaTom tom="atencao" className="size-2" />
                RAJADA
              </span>
            </span>
            <span className="text-lg leading-none font-bold">
              <span ref={rVentoVel} data-testid="hud-vento-vel">
                —
              </span>
              <span className="text-[0.7rem]"> m/s</span>
            </span>
            <span ref={rVentoDe} data-testid="hud-vento-de" className="text-[0.65rem] opacity-90">
              —
            </span>
          </div>
        </div>

        <div className="flex flex-col items-end gap-1" data-testid="hud-teclas">
          {!resumo.aceitaComandos ? (
            <span className="osd flex items-center gap-1 text-[0.65rem] tracking-wide" data-testid="hud-sem-comandos">
              <span className="text-hud-ambar">
                <FormaTom tom="atencao" className="size-2" />
              </span>
              esta política não obedece às teclas
            </span>
          ) : aSeguir ? (
            <span className="osd text-[0.65rem] tracking-wide">
              a bola manda · B devolve as teclas
            </span>
          ) : null}
          <div className="grid grid-cols-3 gap-1">
            <Tecla tamanho="hud" letra="Q" premida={piloto.teclas.q} apagada={teclasEmEspera} testid="tecla-q" />
            <Tecla tamanho="hud" letra="W" premida={piloto.teclas.w} apagada={teclasEmEspera} testid="tecla-w" />
            <Tecla tamanho="hud" letra="E" premida={piloto.teclas.e} apagada={teclasEmEspera} testid="tecla-e" />
            <Tecla tamanho="hud" letra="A" premida={piloto.teclas.a} apagada={teclasEmEspera} testid="tecla-a" />
            <Tecla tamanho="hud" letra="S" premida={piloto.teclas.s} apagada={teclasEmEspera} testid="tecla-s" />
            <Tecla tamanho="hud" letra="D" premida={piloto.teclas.d} apagada={teclasEmEspera} testid="tecla-d" />
            <Tecla tamanho="hud" letra="Z" premida={piloto.z} apagada={teclasEmEspera} testid="tecla-z" />
            <Tecla tamanho="hud" letra="X" premida={piloto.yaw_alvo !== null} apagada={teclasEmEspera} testid="tecla-x" />
            <Tecla tamanho="hud" letra="C" premida={piloto.c} apagada={teclasEmEspera} testid="tecla-c" />
          </div>
          <div className="pointer-events-auto flex w-full flex-col gap-1 pt-0.5" data-testid="hud-tiro">
            <button
              type="button"
              data-testid="tecla-espaco"
              data-estado={tiro?.gatilho ? "ativa" : "inativa"}
              aria-pressed={Boolean(tiro?.gatilho)}
              title="ESPAÇO · Disparar Glock 25 .380 fixa no topo do drone (soco para trás)"
              onPointerDown={(e) => {
                e.currentTarget.setPointerCapture?.(e.pointerId)
                controloTiro.premir()
              }}
              onPointerUp={() => controloTiro.largar()}
              onPointerCancel={() => controloTiro.largar()}
              onLostPointerCapture={() => controloTiro.largar()}
              className={`flex h-8 w-full items-center justify-between rounded-lg border px-2 font-etiqueta text-[0.68rem] font-bold tracking-wider select-none ${
                tiro?.gatilho
                  ? "translate-y-px border-hud-vermelho bg-hud-vermelho text-black shadow-[0_0_14px_rgb(255_82_82/0.65)]"
                  : "border-hud-ambar/65 bg-black/55 text-hud hover:bg-white/12"
              }`}
            >
              <span>ESPAÇO · TIRO</span>
              <span className="font-mono text-[0.65rem]">
                #<span ref={rTiroContagem} data-testid="hud-tiro-contagem">0</span>
              </span>
            </button>
            <div className="osd flex items-center justify-between gap-1 text-[0.6rem] leading-none">
              <span ref={rTiroSoco} data-testid="hud-tiro-soco">
                1,92 N·s · −0,65 m/s
              </span>
              <span
                ref={rTiroRecuo}
                data-testid="hud-tiro-recuo"
                className="font-bold text-hud-vermelho"
                style={{ opacity: 0 }}
              >
                SOCO
              </span>
            </div>
            <div className="osd flex items-center justify-between gap-1 text-[0.6rem] leading-none">
              <span
                ref={rTiroResultado}
                data-testid="hud-tiro-resultado"
                className="font-mono font-bold text-emerald-400"
              >
                pronto [SPACE]
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
