/**
 * Observação (16 canais) e ação (4 canais) do passo atual.
 *
 * Composição (cascata, passo 3): `ProgressBar` do Motion UI para as barras (`tone` semântico por sinal,
 * `referenceTick` marca o limiar de hover no empuxo) + `Card`. Os rótulos e as escalas fixas vêm de
 * `env.py` (`ROTULOS_OBS`); a coluna "cru" DESFAZ a normalização em vez de mostrar só o número normalizado.
 */

import { ProgressBar } from "@/components/motion-ui/progress-bar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  derivarAct,
  FISICA_PADRAO,
  fmt,
  fmtSinal,
  ROTULOS_ACT,
  ROTULOS_OBS,
  type LinhaSim,
  type ResumoEstado,
} from "@/lib/sim"

const GRUPOS: Record<string, string> = {
  dp: "posição relativa (p − alvo)",
  rpy: "atitude (rpy)",
  v: "velocidade no corpo",
  ω: "velocidade angular",
  a_prev: "ação anterior",
}

interface TabelaObsProps {
  linha: LinhaSim | null
}

export function TabelaObs({ linha }: TabelaObsProps) {
  const obs = linha?.obs ?? []
  // barra RELATIVA: |obs| sobre o máximo do passo (com valores típicos ±0,05 uma barra absoluta
  // ficaria invisível); o número absoluto continua nas colunas obs/cru.
  const maximoAbs = obs.reduce((m, v) => Math.max(m, Math.abs(v)), 0)
  return (
    <Card data-testid="tabela-obs">
      <CardHeader className="gap-0.5">
        <CardTitle className="flex items-baseline justify-between gap-2 text-sm font-medium">
          <span>Observação · 16 canais</span>
          <span className="font-mono text-[0.7rem] text-muted-foreground">
            passo {linha ? fmt(linha.passo, 0) : "—"}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          obs normalizada por escalas fixas do `env.py`; «cru» devolve a unidade física e a barra é
          |obs| relativo ao canal mais ativo do passo
        </p>
      </CardHeader>
      <CardContent className="flex flex-col">
        <div className="grid grid-cols-[1.6rem_minmax(0,1fr)_4.2rem_6.4rem_3.6rem] items-center gap-x-2 border-b border-border pb-1 text-[0.65rem] tracking-wide text-muted-foreground uppercase">
          <span>#</span>
          <span>canal</span>
          <span className="text-right">obs</span>
          <span className="text-right">cru</span>
          <span className="text-right">|barra|</span>
        </div>
        {ROTULOS_OBS.map((rotulo) => {
          const valor = obs[rotulo.indice]
          const tem = typeof valor === "number"
          const cru = tem ? valor * rotulo.escala : null
          const forca = tem && maximoAbs > 0 ? Math.min(1, Math.abs(valor) / maximoAbs) : 0
          const primeiroDoGrupo =
            rotulo.indice === 0 || ROTULOS_OBS[rotulo.indice - 1].grupo !== rotulo.grupo
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
                  {tem ? `${fmtSinal(cru, 3)} ${rotulo.unidade}` : "—"}
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

interface PainelActProps {
  linha: LinhaSim | null
  resumo: ResumoEstado | null
}

export function PainelAct({ linha, resumo }: PainelActProps) {
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
