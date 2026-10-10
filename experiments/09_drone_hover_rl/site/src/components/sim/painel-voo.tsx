/**
 * PAINEL DE VOO (planta real, secção «Operação» e «Tudo») — os sensores e o estimador de bordo lidos como
 * instrumentos de cockpit, em vez de 21 números normalizados.
 *
 * Avaliação de UX de 2026-10-10 (`out/ux/`): a tabela da observação obrigava a converter rad, rad/s e m/s²
 * de cabeça. Aqui cada grandeza aparece onde um piloto a procura, nas unidades em que pensa:
 *
 *  · HORIZONTE ARTIFICIAL — rolamento e arfagem ESTIMADOS a bordo (graus); o real do simulador por baixo;
 *  · RUMO — quanto o nariz rodou desde o arranque (sem bússola, o estimado deriva devagar);
 *  · ALTURA — fita com o alvo de 1 m, a altura estimada (ToF + acelerómetro) e a real, e a velocidade vertical;
 *  · POSIÇÃO — mapa visto de cima (frente para cima, como a vista de cima da câmara) com o alvo, a posição
 *    que o RPi ESTIMA (odometria do fluxo ótico) e a REAL, ligadas pelo ERRO DO ESTIMADOR em cm — é este erro
 *    que limita a precisão em xy (achado de 2026-10-10: a política segura a estimativa a 1–5 cm);
 *  · GIROSCÓPIO (°/s) e ACELERÓMETRO (g) medidos, em barras centradas com escala física fixa;
 *  · SENSORES — ToF e fluxo ótico válidos ou sem leitura.
 *
 * Identidade estimado vs real por FORMA (cheio vs contorno) e traço, nunca só por cor (tema monocromático).
 * Tudo vem de `lib/sensores.ts` (testado); o que não vier fica «—».
 */

import type { ReactNode } from "react"
import { Gauge } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  doNarizParaArranque,
  escalaMapaCm,
  lerPainelVoo,
  textoInclinacao,
  type Par,
  type PainelVooDados,
} from "@/lib/sensores"
import { fmt, fmtSinal, type LinhaSim } from "@/lib/sim"

// ------------------------------------------------------------------------------ peças comuns

function Instrumento({
  titulo,
  subtitulo,
  testid,
  children,
  rodape,
}: {
  titulo: string
  subtitulo: string
  testid: string
  children: ReactNode
  rodape: ReactNode
}) {
  return (
    <section
      className="flex min-w-0 flex-col items-center gap-2 rounded-xl bg-muted/30 px-3 py-3"
      data-testid={testid}
      aria-label={titulo}
    >
      <header className="flex w-full flex-col gap-0.5">
        <h3 className="text-xs font-medium">{titulo}</h3>
        <p className="text-[0.65rem] leading-snug text-muted-foreground">
          {subtitulo}
        </p>
      </header>
      {children}
      <div className="flex w-full flex-col gap-0.5 text-[0.7rem]">{rodape}</div>
    </section>
  )
}

/** Linha «estimado · real» com a unidade; o real vem mais discreto. */
function LinhaPar({
  rotulo,
  par,
  unidade,
  casas = 1,
  sinal = true,
  testid,
}: {
  rotulo: string
  par: Par
  unidade: string
  casas?: number
  sinal?: boolean
  testid?: string
}) {
  const f = sinal ? fmtSinal : fmt
  return (
    <div
      className="flex items-baseline justify-between gap-2"
      data-testid={testid}
    >
      <span className="text-muted-foreground">{rotulo}</span>
      <span className="font-mono tabular-nums">
        <span className="font-medium text-foreground">
          {f(par.estimado, casas)}
          {par.estimado === null ? "" : ` ${unidade}`}
        </span>
        {par.real === null ? null : (
          <span
            className="ml-1.5 text-muted-foreground"
            title="valor real do simulador (só para comparar)"
          >
            real {f(par.real, casas)}
          </span>
        )}
      </span>
    </div>
  )
}

/** Barra centrada no zero com escala física fixa (`faixa`) e marca do valor real (contorno). */
function BarraCentrada({
  rotulo,
  valor,
  real = null,
  faixa,
  unidade,
  casas = 1,
  centro = 0,
  testid,
}: {
  rotulo: string
  valor: number | null
  real?: number | null
  faixa: number
  unidade: string
  casas?: number
  /** Valor do centro da barra (ex.: 1 g no acelerómetro vertical). */
  centro?: number
  testid?: string
}) {
  const pos = (v: number) => Math.max(-1, Math.min(1, (v - centro) / faixa))
  const f = valor === null ? 0 : pos(valor)
  const saturado = valor !== null && Math.abs((valor - centro) / faixa) > 1
  return (
    <div className="flex flex-col gap-1" data-testid={testid}>
      <div className="flex items-baseline justify-between gap-2 text-[0.7rem]">
        <span className="text-muted-foreground">{rotulo}</span>
        <span className="font-mono tabular-nums">
          {fmtSinal(valor, casas)} {valor === null ? "" : unidade}
          {saturado ? " ⇥" : ""}
        </span>
      </div>
      <div
        className="relative h-2 w-full rounded-full bg-muted"
        aria-hidden="true"
      >
        <span className="absolute top-[-2px] left-1/2 h-3 w-px bg-foreground/40" />
        {valor === null ? null : (
          <span
            className="absolute top-0 h-2 rounded-full bg-foreground/70"
            style={{
              left: `${50 + Math.min(0, f) * 50}%`,
              width: `${Math.abs(f) * 50}%`,
            }}
          />
        )}
        {real === null ? null : (
          <span
            className="absolute top-[-3px] size-3.5 -translate-x-1/2 rounded-full border-2 border-foreground/70 bg-background/60"
            style={{ left: `${50 + pos(real) * 50}%` }}
            title={`real ${fmtSinal(real, casas)} ${unidade}`}
          />
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------------ instrumentos

/** Horizonte artificial: rolamento + = inclinado à direita (o horizonte roda ao contrário); arfagem + = nariz em
 *  baixo (o horizonte sobe). Escala: 30° de arfagem = raio. */
function Horizonte({ dados }: { dados: PainelVooDados }) {
  const roll = dados.rolamento.estimado ?? 0
  const pitch = dados.arfagem.estimado ?? 0
  const pxPorGrau = 60 / 30
  const desvio = -Math.max(-40, Math.min(40, pitch)) * pxPorGrau
  const sem =
    dados.rolamento.estimado === null || dados.arfagem.estimado === null
  return (
    <svg
      viewBox="0 0 140 140"
      className="w-full max-w-[9.5rem]"
      role="img"
      aria-label="horizonte artificial"
    >
      <defs>
        <clipPath id="clip-horizonte">
          <circle cx="70" cy="70" r="62" />
        </clipPath>
      </defs>
      <g clipPath="url(#clip-horizonte)" opacity={sem ? 0.35 : 1}>
        <g transform={`rotate(${-roll} 70 70) translate(0 ${desvio})`}>
          <rect
            x="-80"
            y="-130"
            width="300"
            height="200"
            className="fill-muted"
          />
          <rect
            x="-80"
            y="70"
            width="300"
            height="200"
            className="fill-muted-foreground/30"
          />
          <line
            x1="-80"
            y1="70"
            x2="220"
            y2="70"
            className="stroke-foreground/80"
            strokeWidth="1.5"
          />
          {[-20, -10, 10, 20].map((g) => (
            <g key={g}>
              <line
                x1={70 - (Math.abs(g) === 10 ? 16 : 24)}
                x2={70 + (Math.abs(g) === 10 ? 16 : 24)}
                y1={70 + g * pxPorGrau}
                y2={70 + g * pxPorGrau}
                className="stroke-foreground/50"
                strokeWidth="1"
              />
              <text
                x={70 + 30}
                y={70 + g * pxPorGrau + 3}
                className="fill-muted-foreground text-[8px]"
              >
                {Math.abs(g)}
              </text>
            </g>
          ))}
        </g>
      </g>
      <circle
        cx="70"
        cy="70"
        r="62"
        className="fill-none stroke-border"
        strokeWidth="2"
      />
      {/* símbolo fixo do drone */}
      <g
        className="stroke-foreground"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      >
        <path d="M38 70 L58 70 L64 77" />
        <path d="M102 70 L82 70 L76 77" />
      </g>
      <circle cx="70" cy="70" r="3" className="fill-foreground" />
    </svg>
  )
}

function Rumo({ dados }: { dados: PainelVooDados }) {
  const est = dados.rumo.estimado
  const real = dados.rumo.real
  // ângulo no ecrã: rumo + = nariz para a ESQUERDA (sentido anti-horário visto de cima) ⇒ ponteiro roda −ψ
  const ponta = (graus: number, r: number) => {
    const a = ((-graus - 90) * Math.PI) / 180
    return { x: 70 + r * Math.cos(a), y: 70 + r * Math.sin(a) }
  }
  const marcas = Array.from({ length: 12 }, (_, i) => i * 30)
  return (
    <svg
      viewBox="0 0 140 140"
      className="w-full max-w-[9.5rem]"
      role="img"
      aria-label="rumo desde o arranque"
    >
      <circle
        cx="70"
        cy="70"
        r="62"
        className="fill-muted stroke-border"
        strokeWidth="2"
      />
      {marcas.map((g) => {
        const a = ponta(g, 60)
        const b = ponta(g, g % 90 === 0 ? 50 : 54)
        return (
          <line
            key={g}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            className="stroke-foreground/40"
            strokeWidth="1"
          />
        )
      })}
      <g className="fill-muted-foreground text-[8px]" textAnchor="middle">
        <text x="70" y="24">
          0°
        </text>
        <text x="27" y="73">
          +90°
        </text>
        <text x="113" y="73">
          −90°
        </text>
        <text x="70" y="124">
          180°
        </text>
      </g>
      {real === null ? null : (
        <line
          x1="70"
          y1="70"
          x2={ponta(real, 44).x}
          y2={ponta(real, 44).y}
          className="stroke-foreground/50"
          strokeWidth="2"
          strokeDasharray="3 3"
        />
      )}
      {est === null ? null : (
        <>
          <line
            x1="70"
            y1="70"
            x2={ponta(est, 46).x}
            y2={ponta(est, 46).y}
            className="stroke-foreground"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <circle
            cx={ponta(est, 46).x}
            cy={ponta(est, 46).y}
            r="3.5"
            className="fill-foreground"
          />
        </>
      )}
      <circle cx="70" cy="70" r="4" className="fill-foreground" />
    </svg>
  )
}

function Altura({ dados }: { dados: PainelVooDados }) {
  const alvo = dados.alvoAltura
  const minimo = 0
  const maximo = Math.max(2, alvo * 2)
  const y = (h: number) =>
    128 -
    ((Math.max(minimo, Math.min(maximo, h)) - minimo) / (maximo - minimo)) * 116
  const est = dados.altura.estimado
  const real = dados.altura.real
  const marcas = [0, 0.5, 1, 1.5, 2].filter((m) => m <= maximo)
  return (
    <svg
      viewBox="0 0 140 140"
      className="w-full max-w-[9.5rem]"
      role="img"
      aria-label="fita de altura"
    >
      <rect
        x="52"
        y="10"
        width="36"
        height="120"
        rx="6"
        className="fill-muted stroke-border"
        strokeWidth="1.5"
      />
      <rect
        x="52"
        y={y(0)}
        width="36"
        height={130 - y(0)}
        className="fill-muted-foreground/20"
      />
      {marcas.map((m) => (
        <g key={m}>
          <line
            x1="52"
            x2="60"
            y1={y(m)}
            y2={y(m)}
            className="stroke-foreground/40"
            strokeWidth="1"
          />
          <text
            x="46"
            y={y(m) + 3}
            textAnchor="end"
            className="fill-muted-foreground text-[8px]"
          >
            {fmt(m, 1)} m
          </text>
        </g>
      ))}
      {/* alvo */}
      <line
        x1="48"
        x2="92"
        y1={y(alvo)}
        y2={y(alvo)}
        className="stroke-foreground/70"
        strokeWidth="1.5"
        strokeDasharray="4 3"
      />
      <text x="96" y={y(alvo) + 3} className="fill-muted-foreground text-[8px]">
        alvo
      </text>
      {/* estimado (cheio, à esquerda) e real (contorno, à direita) */}
      {est === null ? null : (
        <path
          d={`M52 ${y(est)} l-10 -6 l0 12 Z`}
          className="fill-foreground"
          data-testid="altura-estimada"
        />
      )}
      {real === null ? null : (
        <path
          d={`M88 ${y(real)} l10 -6 l0 12 Z`}
          className="fill-background stroke-foreground"
          strokeWidth="1.5"
        />
      )}
      {est === null ? null : (
        <line
          x1="54"
          x2="86"
          y1={y(est)}
          y2={y(est)}
          className="stroke-foreground"
          strokeWidth="2.5"
        />
      )}
    </svg>
  )
}

function Posicao({ dados }: { dados: PainelVooDados }) {
  const pontos = [
    dados.x.estimado,
    dados.y.estimado,
    dados.x.real,
    dados.y.real,
    dados.alvoXy[0],
    dados.alvoXy[1],
  ]
  const escala = escalaMapaCm(pontos)
  const k = 58 / escala
  // referencial de arranque (x frente, y esquerda) → ecrã com a frente para CIMA e a esquerda à esquerda
  const tela = (x: number, y: number) => ({ sx: 70 - y * k, sy: 70 - x * k })
  const alvo = tela(dados.alvoXy[0], dados.alvoXy[1])
  const est =
    dados.x.estimado === null || dados.y.estimado === null
      ? null
      : tela(dados.x.estimado, dados.y.estimado)
  const real =
    dados.x.real === null || dados.y.real === null
      ? null
      : tela(dados.x.real, dados.y.real)
  // seta da velocidade estimada: 1 s de deslocamento (cm/s → cm), rodada do nariz para o arranque
  const vel =
    est === null ||
    dados.vFrente.estimado === null ||
    dados.vEsquerda.estimado === null
      ? null
      : doNarizParaArranque(
          dados.vFrente.estimado,
          dados.vEsquerda.estimado,
          dados.rumo.estimado ?? 0
        )
  const anel = (raioCm: number) => (raioCm * k <= 64 ? raioCm * k : null)
  return (
    <svg
      viewBox="0 0 140 140"
      className="w-full max-w-[9.5rem]"
      role="img"
      aria-label="posição vista de cima"
    >
      <rect
        x="4"
        y="4"
        width="132"
        height="132"
        rx="10"
        className="fill-muted stroke-border"
        strokeWidth="1.5"
      />
      <line
        x1="70"
        y1="8"
        x2="70"
        y2="132"
        className="stroke-border"
        strokeWidth="1"
      />
      <line
        x1="8"
        y1="70"
        x2="132"
        y2="70"
        className="stroke-border"
        strokeWidth="1"
      />
      {[5, 10].map((r) =>
        anel(r) === null ? null : (
          <circle
            key={r}
            cx={alvo.sx}
            cy={alvo.sy}
            r={anel(r) as number}
            className="fill-none stroke-foreground/25"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        )
      )}
      <g className="fill-muted-foreground text-[8px]">
        <text x="70" y="15" textAnchor="middle">
          frente
        </text>
        <text x="9" y="67">
          esq.
        </text>
        <text x="131" y="132" textAnchor="end">
          ±{escala} cm
        </text>
      </g>
      {/* alvo */}
      <g className="stroke-foreground" strokeWidth="1.5">
        <line x1={alvo.sx - 6} x2={alvo.sx + 6} y1={alvo.sy} y2={alvo.sy} />
        <line x1={alvo.sx} x2={alvo.sx} y1={alvo.sy - 6} y2={alvo.sy + 6} />
      </g>
      {est !== null && real !== null ? (
        <line
          x1={est.sx}
          y1={est.sy}
          x2={real.sx}
          y2={real.sy}
          className="stroke-foreground/60"
          strokeWidth="1.2"
          strokeDasharray="2 2"
        />
      ) : null}
      {est !== null && vel !== null ? (
        <line
          x1={est.sx}
          y1={est.sy}
          x2={est.sx - vel[1] * k}
          y2={est.sy - vel[0] * k}
          className="stroke-foreground/70"
          strokeWidth="1.5"
          markerEnd="url(#seta-vel)"
        />
      ) : null}
      <defs>
        <marker
          id="seta-vel"
          viewBox="0 0 6 6"
          refX="5"
          refY="3"
          markerWidth="5"
          markerHeight="5"
          orient="auto"
        >
          <path d="M0 0 L6 3 L0 6 Z" className="fill-foreground/70" />
        </marker>
      </defs>
      {real !== null ? (
        <circle
          cx={real.sx}
          cy={real.sy}
          r="5"
          className="fill-background stroke-foreground"
          strokeWidth="1.8"
          data-testid="posicao-real"
        />
      ) : null}
      {est !== null ? (
        <circle
          cx={est.sx}
          cy={est.sy}
          r="4.5"
          className="fill-foreground"
          data-testid="posicao-estimada"
        />
      ) : null}
    </svg>
  )
}

// ------------------------------------------------------------------------------ painel

export interface PainelVooProps {
  linha: LinhaSim | null
}

/** Painel de voo da planta real (o cf2 não o monta: não tem estimador nem verdade separados). */
export function PainelVoo({ linha }: PainelVooProps) {
  const d = lerPainelVoo(linha)
  const erro = d.erroEstimadorXy
  return (
    <Card className="gap-3" data-testid="painel-voo">
      <CardHeader className="gap-1">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm font-medium">
          <span className="flex items-center gap-1.5">
            <Gauge className="size-4" aria-hidden="true" />
            Painel de voo · o que os sensores de bordo dizem
          </span>
          <span className="flex items-center gap-3 text-[0.7rem] font-normal text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <span
                aria-hidden="true"
                className="inline-block size-2.5 rounded-full bg-foreground"
              />
              estimado a bordo (o que o RPi sabe)
            </span>
            {d.temVerdade ? (
              <span className="inline-flex items-center gap-1">
                <span
                  aria-hidden="true"
                  className="inline-block size-2.5 rounded-full border-2 border-foreground"
                />
                real (simulador, só para comparar)
              </span>
            ) : null}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          a política só vê o estimado — calculado com o giroscópio, o
          acelerómetro, o sensor de altura (ToF) e o fluxo ótico; o real vem do
          simulador e mostra quanto o drone se engana
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 lg:grid-cols-4">
          <Instrumento
            titulo="Inclinação"
            subtitulo="horizonte artificial (atitude estimada)"
            testid="instrumento-atitude"
            rodape={
              <>
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">lateral</span>
                  <span className="font-medium" data-testid="texto-rolamento">
                    {textoInclinacao(d.rolamento.estimado, "rolamento")}
                  </span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">frente-trás</span>
                  <span className="font-medium" data-testid="texto-arfagem">
                    {textoInclinacao(d.arfagem.estimado, "arfagem")}
                  </span>
                </div>
                {d.temVerdade ? (
                  <div className="flex justify-between gap-2 text-muted-foreground">
                    <span>real</span>
                    <span className="font-mono tabular-nums">
                      {fmtSinal(d.rolamento.real, 1)}° ·{" "}
                      {fmtSinal(d.arfagem.real, 1)}°
                    </span>
                  </div>
                ) : null}
              </>
            }
          >
            <Horizonte dados={d} />
          </Instrumento>

          <Instrumento
            titulo="Rumo"
            subtitulo="quanto o nariz rodou desde o arranque"
            testid="instrumento-rumo"
            rodape={
              <LinhaPar
                rotulo="rumo"
                par={d.rumo}
                unidade="°"
                testid="texto-rumo"
              />
            }
          >
            <Rumo dados={d} />
          </Instrumento>

          <Instrumento
            titulo="Altura"
            subtitulo={`alvo ${fmt(d.alvoAltura, 1)} m · sensor ToF ${d.tofOk === null ? "—" : d.tofOk ? "a ler" : "sem leitura"}`}
            testid="instrumento-altura"
            rodape={
              <>
                <LinhaPar
                  rotulo="altura"
                  par={d.altura}
                  unidade="m"
                  casas={2}
                  sinal={false}
                  testid="texto-altura"
                />
                <LinhaPar
                  rotulo="vertical"
                  par={d.vz}
                  unidade="cm/s"
                  testid="texto-vz"
                />
              </>
            }
          >
            <Altura dados={d} />
          </Instrumento>

          <Instrumento
            titulo="Posição"
            subtitulo="vista de cima, desde o arranque (odometria do fluxo ótico)"
            testid="instrumento-posicao"
            rodape={
              <>
                <LinhaPar
                  rotulo="ao alvo"
                  par={d.distAlvo}
                  unidade="cm"
                  sinal={false}
                  testid="texto-dist-alvo"
                />
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">
                    erro do estimador
                  </span>
                  <span
                    className="font-mono font-medium tabular-nums"
                    data-testid="texto-erro-estimador"
                  >
                    {erro === null ? "—" : `${fmt(erro, 1)} cm`}
                  </span>
                </div>
              </>
            }
          >
            <Posicao dados={d} />
          </Instrumento>
        </div>

        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <section
            className="flex flex-col gap-2 rounded-xl bg-muted/30 px-3 py-3"
            data-testid="instrumento-giro"
            aria-label="giroscópio"
          >
            <h3 className="text-xs font-medium">
              Giroscópio{" "}
              <span className="font-normal text-muted-foreground">
                · rotação medida (°/s)
              </span>
            </h3>
            <BarraCentrada
              rotulo="rolamento (p)"
              valor={d.giro[0].estimado}
              real={d.giro[0].real}
              faixa={60}
              unidade="°/s"
            />
            <BarraCentrada
              rotulo="arfagem (q)"
              valor={d.giro[1].estimado}
              real={d.giro[1].real}
              faixa={60}
              unidade="°/s"
            />
            <BarraCentrada
              rotulo="guinada (r)"
              valor={d.giro[2].estimado}
              real={d.giro[2].real}
              faixa={60}
              unidade="°/s"
            />
          </section>
          <section
            className="flex flex-col gap-2 rounded-xl bg-muted/30 px-3 py-3"
            data-testid="instrumento-acc"
            aria-label="acelerómetro"
          >
            <h3 className="text-xs font-medium">
              Acelerómetro{" "}
              <span className="font-normal text-muted-foreground">
                · em g (a pairar: z ≈ 1 g)
              </span>
            </h3>
            <BarraCentrada
              rotulo="frente-trás (x)"
              valor={d.acc[0]}
              faixa={0.5}
              unidade="g"
              casas={2}
            />
            <BarraCentrada
              rotulo="esquerda-direita (y)"
              valor={d.acc[1]}
              faixa={0.5}
              unidade="g"
              casas={2}
            />
            <BarraCentrada
              rotulo="vertical (z) · centro 1 g"
              valor={d.acc[2]}
              faixa={1}
              centro={1}
              unidade="g"
              casas={2}
            />
          </section>
          <section
            className="flex min-w-44 flex-col gap-2 rounded-xl bg-muted/30 px-3 py-3"
            data-testid="instrumento-sensores"
            aria-label="estado dos sensores"
          >
            <h3 className="text-xs font-medium">Sensores</h3>
            {[
              {
                nome: "altura (ToF VL53L1X)",
                ok: d.tofOk,
                teste: "sensor-tof",
              },
              {
                nome: "fluxo ótico (PMW3901)",
                ok: d.fluxoOk,
                teste: "sensor-fluxo",
              },
            ].map((s) => (
              <div
                key={s.nome}
                className="flex items-center justify-between gap-2 text-[0.7rem]"
                data-testid={s.teste}
              >
                <span className="text-muted-foreground">{s.nome}</span>
                <span
                  className={`rounded-full px-2 py-0.5 font-medium ${
                    s.ok === null
                      ? "bg-muted text-muted-foreground"
                      : s.ok
                        ? "bg-primary/10 text-foreground"
                        : "bg-destructive/10 text-destructive"
                  }`}
                >
                  {s.ok === null ? "—" : s.ok ? "a ler" : "sem leitura"}
                </span>
              </div>
            ))}
            <div className="flex items-center justify-between gap-2 text-[0.7rem]">
              <span className="text-muted-foreground">|a| total</span>
              <span className="font-mono tabular-nums">
                {fmt(d.accNorma, 2)} g
              </span>
            </div>
            <p className="text-[0.65rem] leading-snug text-muted-foreground">
              sem ToF a altura vem só do acelerómetro (deriva); sem fluxo a
              velocidade horizontal decai para 0
            </p>
          </section>
        </div>
      </CardContent>
    </Card>
  )
}
