/**
 * Janela BRAÇOS (tecla 9) — os braços articulados ao vivo (HUD 50 Hz, escrito por refs: o React não
 * re-renderiza a cada amostra). O cockpit voa POR OMISSÃO o build com braços (`articulado_15pol_mn5006`); num build
 * rígido (`--build politica`/outro) diz isso e não inventa nada.
 *
 *  · ESTADO DA MIRA: com «seguir a bola» (B) a mira inclina o CORPO (a arma) para a altura da bola e os
 *    motores ficam de nível; mostra o pitch do corpo (medido → pedido), a inclinação dos motores face ao
 *    corpo (τ) e a elevação a que é preciso apontar — «fora do alcance» acima do envelope validado (±35°);
 *  · ESQUEMA LATERAL: o corpo e os dois braços do lado direito (frente-dir e trás-dir) em perfil — nariz à
 *    direita —, com as
 *    DUAS dobradiças de cada braço — ombro na placa e cotovelo na base do mastro — a rodar com os ângulos
 *    medidos pelos encoders;
 *  · OS 8 SERVOS: ângulo medido e alvo, velocidade, corrente, potência na bateria, CURSO (quanto já rodou,
 *    Σ|Δq|) e a energia gasta desde o arranque — e os totais (os mesmos watts que a janela Energia soma).
 */

import { useRef } from "react"

import { Legenda, Leitura, Marca } from "@/components/cockpit/pecas"
import { useDesenhoHud } from "@/hooks/use-cockpit"
import { fmtHud, textoPitchCorpo, type HudBracos } from "@/lib/cockpit"

/** Os 4 braços pela ordem da vista de cima (frente para cima) e os índices das juntas de cada um. */
const BRACOS = [
  { nome: "frente-esq", ombro: 0, cotovelo: 4 },
  { nome: "frente-dir", ombro: 3, cotovelo: 7 },
  { nome: "trás-esq", ombro: 2, cotovelo: 6 },
  { nome: "trás-dir", ombro: 1, cotovelo: 5 },
] as const

/** Colunas da tabela dos servos (o desenhador escreve cada célula pela chave). */
const COLUNAS = ["angulo", "alvo", "velocidade", "corrente", "potencia", "curso", "energia"] as const
type Coluna = (typeof COLUNAS)[number]
const CABECALHO: Record<Coluna, string> = {
  angulo: "ângulo",
  alvo: "alvo",
  velocidade: "°/s",
  corrente: "A",
  potencia: "W",
  curso: "rodou",
  energia: "mWh",
}

// Esquema lateral (px): o perfil a ESCALA real — 1 m = 200 px, centro do corpo no meio.
const ESCALA = 200
const CX = 190
const CY = 70

function celula(bracos: HudBracos, junta: number, coluna: Coluna): string {
  const j = bracos.juntas[junta]
  if (j === undefined) return "—"
  switch (coluna) {
    case "angulo":
      return j.angulo === null ? "—" : `${fmtHud(j.angulo, 1)}°`
    case "alvo":
      return j.alvo === null ? "—" : `${fmtHud(j.alvo, 1)}°`
    case "velocidade":
      return fmtHud(j.velocidade, 0)
    case "corrente":
      return fmtHud(j.corrente, 3)
    case "potencia":
      return fmtHud(j.potencia, 2)
    case "curso":
      return j.curso === null ? "—" : `${fmtHud(j.curso, 0)}°`
    case "energia":
      return j.energiaWh === null ? "—" : fmtHud(j.energiaWh * 1000, 1)
  }
}

export interface JanelaBracosProps {
  /** O build que voa tem braços articulados? (resumo do HUD) */
  temBracos: boolean
}

export function JanelaBracos({ temBracos }: JanelaBracosProps) {
  const rEstado = useRef<HTMLSpanElement>(null)
  const rCorpo = useRef<HTMLSpanElement>(null)
  const rTau = useRef<HTMLSpanElement>(null)
  const rElevacao = useRef<HTMLSpanElement>(null)
  const rPotencia = useRef<HTMLSpanElement>(null)
  const rEnergia = useRef<HTMLSpanElement>(null)
  const rFracao = useRef<HTMLSpanElement>(null)
  const rCurso = useRef<HTMLSpanElement>(null)
  // esquema: corpo, braços do lado direito (frente-dir = junta 3, trás-dir = junta 1) e mastros, e os mostradores
  const rCorpoSvg = useRef<SVGGElement>(null)
  const rBraco = useRef<(SVGGElement | null)[]>([])
  const rMastro = useRef<(SVGGElement | null)[]>([])
  const rMostrador = useRef<(SVGLineElement | null)[]>([])
  const rCelulas = useRef<Record<string, HTMLSpanElement | null>>({})

  useDesenhoHud(({ hud, texto }) => {
    const b = hud?.bracos ?? null
    if (b === null) return
    // ---- esquema lateral (todos os quadros): corpo rodado pelo pitch; braço = corpo + ombro; mastro = braço + cotovelo
    const geo = b.geometria
    const theta = b.pitchCorpo ?? 0
    if (rCorpoSvg.current !== null)
      rCorpoSvg.current.setAttribute("transform", `rotate(${theta.toFixed(2)} ${CX} ${CY})`)
    if (geo !== null) {
      for (const k of [3, 1]) {
        const ux = geo.ux[k] ?? (k === 3 ? 0.707 : -0.707)
        const q1 = b.juntas[k]?.angulo ?? 0
        const q2 = b.juntas[k + 4]?.angulo ?? 0
        // o ombro está no corpo (roda com ele); o braço roda mais q1 em torno do ombro e o mastro mais q2 no cotovelo
        const t = (theta * Math.PI) / 180
        const xs = CX + ESCALA * geo.rS * ux * Math.cos(t)
        const ys = CY + ESCALA * geo.rS * ux * Math.sin(t)
        const braco = rBraco.current[k]
        if (braco != null) braco.setAttribute("transform", `translate(${xs.toFixed(1)} ${ys.toFixed(1)}) rotate(${(theta + q1).toFixed(2)})`)
        const mastro = rMastro.current[k]
        if (mastro != null) mastro.setAttribute("transform", `translate(${(ESCALA * geo.l1 * ux).toFixed(1)} 0) rotate(${q2.toFixed(2)})`)
      }
    }
    for (let i = 0; i < 8; i += 1) {
      const linha = rMostrador.current[i]
      const a = b.juntas[i]?.angulo
      if (linha != null && a != null) linha.setAttribute("transform", `rotate(${a.toFixed(1)} 11 11)`)
    }
    if (!texto) return
    const escrever = (el: HTMLElement | null | undefined, t: string) => {
      if (el != null && el.textContent !== t) el.textContent = t
    }
    const m = b.mira
    escrever(
      rEstado.current,
      !b.ligados
        ? "SERVOS SEM ENERGIA"
        : b.miraAtiva
          ? m?.foraAlcance
            ? "MIRA · FORA DO ALCANCE (±35°)"
            : m?.teclas
              ? "MIRA POR ARFAGEM · a pilotar"
              : "MIRA POR ARFAGEM ATIVA"
          : "em espera (B = seguir a bola)"
    )
    if (rEstado.current?.parentElement != null)
      rEstado.current.parentElement.dataset.tom = !b.ligados ? "perigo" : b.miraAtiva ? (m?.foraAlcance ? "atencao" : "ativo") : "normal"
    escrever(rCorpo.current, `${textoPitchCorpo(b.pitchCorpo)} → ${textoPitchCorpo(b.pitchAlvo)}`)
    escrever(rTau.current, b.inclinacaoMotores === null ? "—" : `${fmtHud(b.inclinacaoMotores, 1)}°`)
    escrever(rElevacao.current, m?.elevacao == null ? "—" : `${fmtHud(m.elevacao, 1)}°`)
    escrever(rPotencia.current, b.potenciaW === null ? "—" : `${fmtHud(b.potenciaW, 1)} W`)
    escrever(rEnergia.current, b.energiaWh === null ? "—" : `${fmtHud(b.energiaWh, 3)} Wh`)
    const total = hud?.potencia?.total ?? null
    escrever(
      rFracao.current,
      total === null || total <= 0 || b.potenciaW === null ? "—" : `${fmtHud((100 * b.potenciaW) / total, 1)} %`
    )
    const curso = b.juntas.reduce((acc, j) => acc + (j.curso ?? 0), 0)
    escrever(rCurso.current, `${fmtHud(curso, 0)}°`)
    for (let i = 0; i < 8; i += 1)
      for (const col of COLUNAS) escrever(rCelulas.current[`${i}:${col}`], celula(b, i, col))
  })

  if (!temBracos) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="bracos-sem-bracos">
        Este cockpit foi arrancado com um build de braços RÍGIDOS (<code className="font-mono text-hud">--build</code>).
        O drone com os braços articulados (8 servos, mira por arfagem) é o padrão: arranque com{" "}
        <code className="font-mono text-hud">mujoco 09</code> ou o <code className="font-mono text-hud">sim_site.py</code>{" "}
        sem <code className="font-mono text-hud">--build</code>.
      </p>
    )
  }

  const linhaJunta = (indice: number, rotulo: string) => (
    <tr key={indice} className="border-t border-white/8">
      <td className="py-0.5 pr-1">
        <span className="flex items-center gap-1">
          <svg viewBox="0 0 22 22" className="size-4 shrink-0" aria-hidden="true">
            <circle cx="11" cy="11" r="9" fill="none" stroke="currentColor" strokeOpacity="0.35" strokeWidth="2" />
            <line
              ref={(el) => {
                rMostrador.current[indice] = el
              }}
              x1="11"
              y1="11"
              x2="20"
              y2="11"
              stroke="rgb(248 113 113)"
              strokeWidth="2.4"
              strokeLinecap="round"
            />
          </svg>
          <span className="text-[0.66rem] text-muted-foreground">{rotulo}</span>
        </span>
      </td>
      {COLUNAS.map((col) => (
        <td key={col} className="py-0.5 text-right">
          <span
            ref={(el) => {
              rCelulas.current[`${indice}:${col}`] = el
            }}
            data-testid={`bracos-${indice}-${col}`}
            className="font-mono text-[0.7rem] font-bold text-hud"
          >
            —
          </span>
        </td>
      ))}
    </tr>
  )

  // perfil de um braço (origem no ombro, a apontar para +x do braço; o mastro sobe do cotovelo)
  const desenhoBraco = (k: 3 | 1, comprimento: number, mastro: number) => (
    <g
      ref={(el) => {
        rBraco.current[k] = el
      }}
    >
      <line x1="0" y1="0" x2={comprimento} y2="0" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      <circle cx="0" cy="0" r="5" fill="rgb(255 133 10)" stroke="black" strokeWidth="1" />
      <g
        ref={(el) => {
          rMastro.current[k] = el
        }}
      >
        <line x1="0" y1="0" x2="0" y2={-mastro} stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        <rect x="-7" y={-mastro - 6} width="14" height="7" rx="2" fill="currentColor" />
        <line x1="-38" y1={-mastro - 7} x2="38" y2={-mastro - 7} stroke="rgb(56 189 248)" strokeWidth="2" strokeOpacity="0.8" />
        <circle cx="0" cy="0" r="5" fill="rgb(255 133 10)" stroke="black" strokeWidth="1" />
      </g>
    </g>
  )

  return (
    <div className="flex flex-col gap-3" data-testid="painel-bracos">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Marca tom="normal" testid="bracos-estado">
          <span ref={rEstado}>—</span>
        </Marca>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Leitura rotulo="corpo (arma)" refValor={rCorpo} testid="bracos-pitch-corpo" className="col-span-3" />
        <Leitura rotulo="motores vs corpo" refValor={rTau} testid="bracos-tau" />
        <Leitura rotulo="elevação da bola" refValor={rElevacao} testid="bracos-elevacao" />
        <Leitura rotulo="servos agora" refValor={rPotencia} testid="bracos-potencia" />
      </div>

      <div className="rounded-lg bg-black/35 p-1" data-testid="bracos-esquema">
        <svg viewBox="0 0 380 120" className="w-full text-hud" role="img" aria-label="perfil dos braços: ombro e cotovelo">
          <line x1="0" y1="114" x2="380" y2="114" stroke="currentColor" strokeOpacity="0.2" strokeDasharray="4 4" />
          {desenhoBraco(3, ESCALA * 0.825 * 0.707, ESCALA * 0.2305)}
          {desenhoBraco(1, ESCALA * 0.825 * -0.707, ESCALA * 0.2305)}
          <g ref={rCorpoSvg}>
            <rect x={CX - 32} y={CY - 7} width="64" height="14" rx="3" fill="currentColor" fillOpacity="0.85" />
            <rect x={CX - 6} y={CY - 19} width="40" height="10" rx="2" fill="rgb(148 163 184)" />
            <line x1={CX + 34} y1={CY - 14} x2={CX + 120} y2={CY - 14} stroke="rgb(250 204 21)" strokeWidth="1" strokeDasharray="3 3" strokeOpacity="0.8" />
          </g>
          <text x="6" y="12" fontSize="9" fill="currentColor" fillOpacity="0.7">
            perfil do lado direito (nariz →) · ● laranja = dobradiça (ombro, cotovelo)
          </text>
        </svg>
      </div>

      <div className="flex flex-col gap-1">
        <Legenda>os 8 servos · DYNAMIXEL XH430-V210-R (ombro com sem-fim 20:1)</Legenda>
        <table className="w-full border-collapse" data-testid="bracos-tabela">
          <thead>
            <tr>
              <th className="text-left text-[0.6rem] font-bold text-muted-foreground">junta</th>
              {COLUNAS.map((col) => (
                <th key={col} className="text-right text-[0.6rem] font-bold text-muted-foreground">
                  {CABECALHO[col]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {BRACOS.flatMap((braco) => [
              linhaJunta(braco.ombro, `${braco.nome} · ombro`),
              linhaJunta(braco.cotovelo, `${braco.nome} · cotovelo`),
            ])}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-3 gap-2 border-t border-white/10 pt-2">
        <Leitura rotulo="energia gasta" refValor={rEnergia} testid="bracos-energia" />
        <Leitura rotulo="da potência total" refValor={rFracao} testid="bracos-fracao" />
        <Leitura rotulo="rodaram (8 juntas)" refValor={rCurso} testid="bracos-curso" />
      </div>
      <p className="text-[0.66rem] leading-snug text-muted-foreground">
        A energia sai da bateria a cada passo da física (a corrente dos servos entra no consumo total e na
        autonomia). Em espera cada servo puxa 40 mA a 24 V; o sem-fim do ombro segura o empuxo sem corrente.
      </p>
    </div>
  )
}
