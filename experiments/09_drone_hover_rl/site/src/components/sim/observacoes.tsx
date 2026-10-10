/**
 * Observação (16 canais) e ação (4 canais) do passo atual.
 *
 * Composição (cascata, passo 3): `ProgressBar` do Motion UI para as barras (`tone` semântico por sinal,
 * `referenceTick` marca o limiar de hover no empuxo) + `Card`. Os rótulos e as escalas fixas vêm de
 * `env.py` (`ROTULOS_OBS`); a coluna "cru" DESFAZ a normalização em vez de mostrar só o número normalizado.
 *
 * PLANTA REAL (`planta: "real"`): a observação é a do ATOR (21 canais do `env_real.py`: giro e
 * acelerómetro medidos, estimador de bordo, validade dos sensores e ação anterior), a ação é ctbr
 * (coletivo + taxas p, q, r) e o `ctrl` é o EMPUXO de cada rotor — nada se deriva do `HoverEnv`.
 * Desde a avaliação de UX de 2026-10-10 a tabela real mostra cada canal com um NOME SIMPLES, o valor numa
 * unidade amigável (°, °/s, cm, cm/s, g, sim/não) e uma barra CENTRADA no zero com a escala física do
 * canal (antes: nomes de código, rad e m/s², e uma barra relativa ao canal mais ativo — o acc_z ≈ 1 g
 * achatava todas as outras); o valor normalizado que a rede recebe fica numa coluna secundária. As taxas e
 * a semântica do coletivo vêm do `hardware` do `/api/state` (o backend lê-as do próprio `env_real`).
 */

import { ProgressBar } from "@/components/motion-ui/progress-bar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  COLETIVO_MAX_PESO,
  derivarAct,
  empuxoDoColetivo,
  FISICA_PADRAO,
  fmt,
  fmtSinal,
  GRAVIDADE,
  modoAcaoReal,
  ROTORES_REAIS,
  ROTULOS_ACT,
  rotulosAct,
  rotulosObs,
  setpointTaxa,
  TAXA_MAX_CTBR,
  type Hardware,
  type RotuloObs,
  type LinhaSim,
  type Planta,
  type ResumoEstado,
} from "@/lib/sim"

const GRUPOS: Record<string, string> = {
  dp: "posição relativa (p − alvo)",
  rpy: "atitude (rpy)",
  v: "velocidade no corpo",
  ω: "velocidade angular",
  a_prev: "ação anterior",
  // planta real (ator): só sensores + estimador de bordo + ação anterior
  giro: "giroscópio medido (p, q, r)",
  acc: "acelerómetro medido",
  atitude: "atitude estimada (bordo)",
  rumo: "rumo desde o armar (estimado)",
  vertical: "altura e velocidade vertical estimadas",
  fluxo: "velocidade no corpo (fluxo ótico)",
  odometria: "odometria x̂, ŷ (estimada)",
  validade: "validade dos sensores",
}

interface TabelaObsProps {
  linha: LinhaSim | null
  /** Planta anunciada pela API (recurso quando a linha não diz a sua); cf2/ausente = 16 canais. */
  planta?: Planta | null
  /** `hardware.modo_acao` (planta real): rótulos da ação anterior (ctbr ou motores). */
  modoAcao?: string | null
}

/** Barra centrada no zero (fração em [−1, 1] da faixa física do canal). */
function BarraCentro({ fracao, saturada }: { fracao: number | null; saturada: boolean }) {
  const f = fracao === null ? 0 : Math.max(-1, Math.min(1, fracao))
  return (
    <span className="relative block h-1.5 w-16 rounded-full bg-muted" aria-hidden="true">
      <span className="absolute top-[-2px] left-1/2 h-2.5 w-px bg-foreground/40" />
      <span
        className={`absolute top-0 h-1.5 rounded-full ${saturada ? "bg-destructive/80" : "bg-foreground/70"}`}
        style={{ left: `${50 + Math.min(0, f) * 50}%`, width: `${Math.abs(f) * 50}%` }}
      />
    </span>
  )
}

/** Valor amigável de um canal real (ou «sim/não» nas flags); `null` sem dados. */
function valorAmigavel(rotulo: RotuloObs, valor: number | undefined): string {
  if (typeof valor !== "number") return "—"
  if (rotulo.flag) return valor >= 0.5 ? "sim" : "não"
  const a = rotulo.amigavel
  if (a === undefined) return `${fmtSinal(valor * rotulo.escala, 3)} ${rotulo.unidade}`
  return `${fmtSinal(valor * rotulo.escala * a.fator, a.casas)}${a.unidade ? ` ${a.unidade}` : ""}`
}

/**
 * Tabela da PLANTA REAL: nome simples + valor amigável + barra centrada com a escala física do canal; o
 * nome de código e o valor normalizado (o que entra na rede) ficam em segundo plano.
 */
function TabelaObsReal({ linha, rotulos }: { linha: LinhaSim | null; rotulos: RotuloObs[] }) {
  const obs = linha?.obs ?? []
  return (
    <Card data-testid="tabela-obs" data-planta="real">
      <CardHeader className="gap-0.5">
        <CardTitle className="flex items-baseline justify-between gap-2 text-sm font-medium">
          <span>{`Entradas da rede · ${rotulos.length} canais`}</span>
          <span className="font-mono text-[0.7rem] text-muted-foreground">
            passo {linha ? fmt(linha.passo, 0) : "—"}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          o que a política recebe a cada decisão: só o que existe a bordo (giroscópio e acelerómetro
          medidos, o que o RPi estima com eles + ToF + fluxo ótico, e a última ação) — nada de posição ou
          atitude exatas. «valor» está em unidades do dia a dia; «na rede» é o número normalizado que entra
          na rede; a barra vai de −faixa a +faixa do canal (vermelha = fora da faixa). A leitura em
          instrumentos está no «Painel de voo» (secção Operação).
        </p>
      </CardHeader>
      <CardContent className="flex flex-col">
        <div className="grid grid-cols-[1.4rem_minmax(0,1fr)_5.6rem_3.6rem_4.2rem] items-center gap-x-2 border-b border-border pb-1 text-[0.65rem] tracking-wide text-muted-foreground uppercase">
          <span>#</span>
          <span>entrada</span>
          <span className="text-right">valor</span>
          <span className="text-right">na rede</span>
          <span className="text-right">faixa</span>
        </div>
        {rotulos.map((rotulo) => {
          const valor = obs[rotulo.indice]
          const tem = typeof valor === "number"
          const a = rotulo.amigavel
          const fisico = tem && a !== undefined ? valor * rotulo.escala * a.fator : null
          const fracao = fisico === null || a === undefined ? null : fisico / a.faixa
          const primeiroDoGrupo =
            rotulo.indice === 0 || rotulos[rotulo.indice - 1].grupo !== rotulo.grupo
          return (
            <div key={rotulo.indice}>
              {primeiroDoGrupo ? (
                <p className="pt-2 pb-0.5 text-[0.65rem] text-muted-foreground">{GRUPOS[rotulo.grupo]}</p>
              ) : null}
              <div
                className="grid grid-cols-[1.4rem_minmax(0,1fr)_5.6rem_3.6rem_4.2rem] items-center gap-x-2 py-0.5"
                title={rotulo.ajuda}
                data-testid={`obs-${rotulo.indice}`}
              >
                <span className="font-mono text-[0.65rem] text-muted-foreground">{rotulo.indice}</span>
                <span className="flex min-w-0 flex-col leading-tight">
                  <span className="truncate text-xs">{rotulo.titulo ?? rotulo.nome}</span>
                  <span className="truncate font-mono text-[0.6rem] text-muted-foreground">{rotulo.nome}</span>
                </span>
                <span className="text-right font-mono text-xs font-medium whitespace-nowrap tabular-nums">
                  {rotulo.flag ? (
                    <span
                      className={`rounded-full px-1.5 py-0.5 font-sans text-[0.65rem] ${
                        !tem ? "" : valor >= 0.5 ? "bg-primary/10" : "bg-destructive/10 text-destructive"
                      }`}
                    >
                      {valorAmigavel(rotulo, valor)}
                    </span>
                  ) : (
                    valorAmigavel(rotulo, valor)
                  )}
                </span>
                <span className="text-right font-mono text-[0.65rem] text-muted-foreground tabular-nums">
                  {tem ? fmtSinal(valor, 3) : "—"}
                </span>
                <span className="flex justify-end" title={a ? `faixa da barra: ±${fmt(a.faixa, a.faixa < 1 ? 1 : 0)} ${a.unidade}` : undefined}>
                  {rotulo.flag ? null : (
                    <BarraCentro fracao={fracao} saturada={fracao !== null && Math.abs(fracao) > 1} />
                  )}
                </span>
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

export function TabelaObs({ linha, planta = null, modoAcao = null }: TabelaObsProps) {
  const plantaLinha = linha?.planta ?? planta
  const real = plantaLinha === "real"
  if (real) return <TabelaObsReal linha={linha} rotulos={rotulosObs(plantaLinha, modoAcao)} />
  const rotulos = rotulosObs(plantaLinha, modoAcao)
  const obs = linha?.obs ?? []
  // barra RELATIVA: |obs| sobre o máximo do passo (com valores típicos ±0,05 uma barra absoluta
  // ficaria invisível); o número absoluto continua nas colunas obs/cru.
  const maximoAbs = obs.reduce((m, v) => Math.max(m, Math.abs(v)), 0)
  return (
    <Card data-testid="tabela-obs">
      <CardHeader className="gap-0.5">
        <CardTitle className="flex items-baseline justify-between gap-2 text-sm font-medium">
          <span>{`Observação · ${rotulos.length} canais`}</span>
          <span className="font-mono text-[0.7rem] text-muted-foreground">
            passo {linha ? fmt(linha.passo, 0) : "—"}
          </span>
        </CardTitle>
        {real ? (
          <p className="text-[0.7rem] text-muted-foreground">
            obs do ATOR (planta real): só o que existe a bordo — giro e acelerómetro medidos, o
            estimador de bordo e a ação anterior (nada de xyz/atitude exatos), normalizada pelo
            `env_real.py`; «cru» devolve a unidade física e a barra é |obs| relativo ao canal mais
            ativo do passo
          </p>
        ) : (
          <p className="text-[0.7rem] text-muted-foreground">
            obs normalizada por escalas fixas do `env.py`; «cru» devolve a unidade física e a barra é
            |obs| relativo ao canal mais ativo do passo
          </p>
        )}
      </CardHeader>
      <CardContent className="flex flex-col">
        <div className="grid grid-cols-[1.6rem_minmax(0,1fr)_4.2rem_6.4rem_3.6rem] items-center gap-x-2 border-b border-border pb-1 text-[0.65rem] tracking-wide text-muted-foreground uppercase">
          <span>#</span>
          <span>canal</span>
          <span className="text-right">obs</span>
          <span className="text-right">cru</span>
          <span className="text-right">|barra|</span>
        </div>
        {rotulos.map((rotulo) => {
          const valor = obs[rotulo.indice]
          const tem = typeof valor === "number"
          const cru = tem ? valor * rotulo.escala : null
          const forca = tem && maximoAbs > 0 ? Math.min(1, Math.abs(valor) / maximoAbs) : 0
          const primeiroDoGrupo =
            rotulo.indice === 0 || rotulos[rotulo.indice - 1].grupo !== rotulo.grupo
          return (
            <div key={rotulo.indice}>
              {primeiroDoGrupo ? (
                <p className="pt-2 pb-0.5 text-[0.65rem] text-muted-foreground">
                  {GRUPOS[rotulo.grupo]}
                </p>
              ) : null}
              <div className="grid grid-cols-[1.6rem_minmax(0,1fr)_4.2rem_6.4rem_3.6rem] items-center gap-x-2 py-0.5">
                <span className="font-mono text-[0.7rem] text-muted-foreground">
                  {rotulo.indice}
                </span>
                <span className="truncate font-mono text-xs" title={`${rotulo.nome} (${rotulo.escalaTexto})`}>
                  {rotulo.nome}
                </span>
                <span className="text-right font-mono text-xs tabular-nums">
                  {tem ? fmtSinal(valor, 3) : "—"}
                </span>
                <span className="text-right font-mono text-xs whitespace-nowrap tabular-nums">
                  {!tem
                    ? "—"
                    : rotulo.flag
                      ? valor >= 0.5
                        ? "sim"
                        : "não"
                      : `${fmtSinal(cru, 3)} ${rotulo.unidade}`}
                </span>
                <span className="flex justify-end">
                  <ProgressBar
                    value={forca}
                    size="sm"
                    tone={tem && valor < 0 ? "var(--destructive)" : "var(--primary)"}
                    className="w-16"
                  />
                </span>
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

interface PainelActRealProps {
  linha: LinhaSim | null
  hardware: Hardware | null
}

/** Fração segura para uma barra (0 sem dados). */
function fracaoBarra(valor: number | null | undefined, maximo: number | null): number {
  if (valor === null || valor === undefined || maximo === null || maximo <= 0) return 0
  return Math.max(0, Math.min(1, valor / maximo))
}

/**
 * Ação na PLANTA REAL: a política manda ctbr (a₀ = coletivo de acelerador, a₁..₃ = taxas p, q, r que o
 * FC dedicado fecha a 500 Hz) — ou 4 aceleradores no modo `motores` — e o `ctrl` publicado é o EMPUXO
 * de cada rotor (N), lido tal e qual (o mesmo valor do `motores.empuxo_n`). Nada é derivado do `HoverEnv`;
 * o único derivado é o setpoint de taxa, `clip(a) × TAXA_MAX` do `env_real.py`, e está rotulado como tal.
 */
function PainelActReal({ linha, hardware }: PainelActRealProps) {
  const modo = modoAcaoReal(hardware?.modoAcao)
  const rotulos = rotulosAct("real", modo)
  const taxaMax = hardware?.taxaMax ?? TAXA_MAX_CTBR
  const maxPeso = hardware?.coletivoMaxPeso ?? COLETIVO_MAX_PESO
  const act = linha?.act ?? []
  const ctrl = linha?.ctrl ?? null
  const tMax = linha?.motores?.tMaxN ?? null
  const massaKg = hardware?.massaTotalG == null ? null : hardware.massaTotalG / 1000
  const tPairagem = massaKg === null ? null : (massaKg * GRAVIDADE) / 4
  const tick =
    tPairagem === null || tMax === null || tMax <= 0 ? undefined : Math.min(1, tPairagem / tMax)
  const soma = ctrl === null ? null : ctrl.reduce((s, t) => s + t, 0)

  return (
    <Card data-testid="painel-act" data-planta="real">
      <CardHeader className="gap-0.5">
        <CardTitle className="flex items-baseline justify-between gap-2 text-sm font-medium">
          <span>Ação · 4 canais</span>
          <span className="font-mono text-[0.7rem] text-muted-foreground">
            {ctrl ? "ctrl do backend · empuxo por rotor" : "sem ctrl na telemetria"}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          {modo === "ctbr"
            ? `política em [-1, 1] → ctbr: a₀ = coletivo LINEAR EM EMPUXO (−1 = sem empuxo, 0 = pairar, +1 = ${fmt(maxPeso, 0)}× o peso, com a tensão medida da bateria compensada) e a₁..₃ = taxas p, q, r até ±${fmt(taxaMax[0], 1)}/${fmt(taxaMax[1], 1)}/${fmt(taxaMax[2], 1)} rad/s (${fmt((taxaMax[0] * 180) / Math.PI, 0)}/${fmt((taxaMax[1] * 180) / Math.PI, 0)}/${fmt((taxaMax[2] * 180) / Math.PI, 0)} °/s), que o FC dedicado fecha a 500 Hz; o ctrl é o EMPUXO de cada rotor (N)`
            : "política em [-1, 1] → 4 aceleradores (um por rotor, sem FC; 0 = pairagem, −1 = 0 %, +1 = 100 %); o ctrl é o EMPUXO de cada rotor (N)"}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-col gap-2 rounded-lg bg-muted/40 px-3 py-2">
          {ROTORES_REAIS.map((rotor) => (
            <ProgressBar
              key={rotor.nome}
              value={fracaoBarra(ctrl?.[rotor.indice], tMax)}
              referenceTick={tick}
              size="sm"
              highlight
              progressbar
              aria-label={`empuxo de ${rotor.nome} em N`}
              label={
                <span className="font-mono text-xs">
                  ctrl[{rotor.indice}] · empuxo {rotor.nome}{" "}
                  <span className="text-muted-foreground">
                    ({rotor.posicao}, {rotor.sentido})
                  </span>
                </span>
              }
              valueLabel={
                <span className="font-mono text-xs tabular-nums">
                  {ctrl ? `${fmt(ctrl[rotor.indice], 3)} N` : "—"}
                </span>
              }
            />
          ))}
          <p className="text-[0.65rem] text-muted-foreground">
            barra = fração do teto atual por rotor (T_max {fmt(tMax, 2)} N, decai com a bateria)
            {tick === undefined ? "" : ` · traço = pairagem m·g/4 = ${fmt(tPairagem, 2)} N`} · Σ{" "}
            {fmt(soma, 2)} N
          </p>
        </div>

        <div className="grid grid-cols-[1.6rem_minmax(0,1fr)_4.6rem_8.6rem] items-center gap-x-2 border-t border-border pt-2 text-[0.65rem] tracking-wide text-muted-foreground uppercase">
          <span>#</span>
          <span>a bruta (política)</span>
          <span className="text-right">valor</span>
          <span className="text-right">pedido</span>
        </div>
        {rotulos.map((rotulo) => {
          const a = act[rotulo.indice]
          const tem = typeof a === "number"
          const taxa =
            modo === "ctbr" && rotulo.indice > 0
              ? setpointTaxa(tem ? a : null, (rotulo.indice - 1) as 0 | 1 | 2, taxaMax)
              : null
          const empuxo =
            modo === "ctbr" && rotulo.indice === 0 ? empuxoDoColetivo(tem ? a : null, maxPeso) : null
          return (
            <div
              key={rotulo.indice}
              className="grid grid-cols-[1.6rem_minmax(0,1fr)_4.6rem_8.6rem] items-center gap-x-2"
            >
              <span className="font-mono text-[0.7rem] text-muted-foreground">{rotulo.indice}</span>
              <span className="truncate font-mono text-xs" title={rotulo.canal}>
                {rotulo.nome}
              </span>
              <span className="text-right font-mono text-xs tabular-nums">
                {tem ? fmtSinal(a, 3) : "—"}
              </span>
              <span
                className="text-right font-mono text-[0.7rem] whitespace-nowrap text-muted-foreground tabular-nums"
                title={
                  taxa !== null
                    ? "setpoint de taxa = clip(a, −1, 1) × TAXA_MAX (env_real.py)"
                    : empuxo !== null
                      ? "empuxo total pedido = (1 + a₀) × peso (coletivo linear em empuxo, env_real.py)"
                      : undefined
                }
              >
                {taxa !== null
                  ? `${fmtSinal(taxa, 2)} rad/s · ${fmtSinal((taxa * 180) / Math.PI, 0)}°/s`
                  : empuxo !== null
                    ? `${fmt(empuxo, 2)}× o peso`
                    : rotulo.indice === 0 && modo === "ctbr"
                      ? "coletivo"
                      : "acelerador"}
              </span>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

interface PainelActProps {
  linha: LinhaSim | null
  resumo: ResumoEstado | null
  /** Planta anunciada pela API (recurso quando a linha não diz a sua); cf2/ausente = wrench do cf2. */
  planta?: Planta | null
  /** Peças do build (`/api/state`, planta real): modo da ação e a massa para o traço de pairagem. */
  hardware?: Hardware | null
}

export function PainelAct({ linha, resumo, planta = null, hardware = null }: PainelActProps) {
  // Planta real: ctbr + empuxo por rotor (painel próprio); cf2: o painel de sempre, sem mudanças.
  if ((linha?.planta ?? planta) === "real") {
    return <PainelActReal linha={linha} hardware={hardware} />
  }
  const constantes = {
    mg: resumo?.mg ?? FISICA_PADRAO.mg,
    thrustMax: resumo?.thrustMax ?? FISICA_PADRAO.thrustMax,
    momentoMax: resumo?.momentoMax ?? FISICA_PADRAO.momentoMax,
    tauEscala: resumo?.tauEscala ?? FISICA_PADRAO.tauEscala,
  }
  const derivado = derivarAct(linha, constantes)
  const act = linha?.act ?? []
  const fracaoEmpuxo = derivado ? Math.min(1, Math.max(0, derivado.empuxo / constantes.thrustMax)) : 0
  const fracaoHover = Math.min(1, Math.max(0, constantes.mg / constantes.thrustMax))

  return (
    <Card data-testid="painel-act">
      <CardHeader className="gap-0.5">
        <CardTitle className="flex items-baseline justify-between gap-2 text-sm font-medium">
          <span>Ação · 4 canais</span>
          <span className="font-mono text-[0.7rem] text-muted-foreground">
            {derivado?.doBackend ? "ctrl do backend" : "derivado da ação"}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          política em [-1, 1] → empuxo 0…{fmt(constantes.thrustMax, 3)} N e momentos ±
          {fmt(constantes.momentoMax[0] * 1000, 2)} mN·m (env.py; `mg` = {fmt(constantes.mg, 5)} N)
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5 rounded-lg bg-muted/40 px-3 py-2">
          <ProgressBar
            value={fracaoEmpuxo}
            referenceTick={fracaoHover}
            highlight
            progressbar
            aria-label="empuxo em N"
            label={<span className="font-mono text-xs">{ROTULOS_ACT[0].nome}</span>}
            valueLabel={
              <span className="font-mono text-sm tabular-nums">
                {derivado ? `${fmt(derivado.empuxo, 4)} N` : "—"}
              </span>
            }
          />
          <p className="text-[0.65rem] text-muted-foreground">
            traço fino = empuxo de hover (mg = {fmt(constantes.mg, 4)} N)
          </p>
        </div>

        {[1, 2, 3].map((i) => {
          const momento = derivado?.momentos[i - 1] ?? 0
          const maximo = constantes.momentoMax[i - 1]
          return (
            <ProgressBar
              key={i}
              value={Math.min(1, Math.abs(momento) / (maximo || 1))}
              size="sm"
              tone={momento < 0 ? "var(--destructive)" : "var(--primary)"}
              progressbar
              aria-label={`momento ${["x", "y", "z"][i - 1]}`}
              label={
                <span className="font-mono text-xs">
                  {ROTULOS_ACT[i].nome} <span className="text-muted-foreground">({ROTULOS_ACT[i].canal})</span>
                </span>
              }
              valueLabel={
                <span className="font-mono text-xs tabular-nums">
                  {fmtSinal(momento * 1000, 4)} mN·m
                </span>
              }
            />
          )
        })}

        <div className="grid grid-cols-[1.6rem_minmax(0,1fr)_5rem] items-center gap-x-2 border-t border-border pt-2 text-[0.65rem] tracking-wide text-muted-foreground uppercase">
          <span>#</span>
          <span>a bruta (política)</span>
          <span className="text-right">valor</span>
        </div>
        {ROTULOS_ACT.map((rotulo) => (
          <div
            key={rotulo.indice}
            className="grid grid-cols-[1.6rem_minmax(0,1fr)_5rem] items-center gap-x-2"
          >
            <span className="font-mono text-[0.7rem] text-muted-foreground">{rotulo.indice}</span>
            <span className="truncate font-mono text-xs">{rotulo.nome}</span>
            <span className="text-right font-mono text-xs tabular-nums">
              {typeof act[rotulo.indice] === "number" ? fmtSinal(act[rotulo.indice], 3) : "—"}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
