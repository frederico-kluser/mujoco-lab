/**
 * Janela SISTEMA (tecla 7) — o que está por baixo do cockpit, para quem quer ver:
 *  · QUEM ESTÁ A VOAR: o controlador em vigor (sem seletor — voa o que ganhou na medição) e a pilha de
 *    bordo (`QuemFazOQue`);
 *  · os STREAMS: quadros por segundo MEDIDOS de cada vista, a latência da câmara (modelo), o ritmo do
 *    HUD e o que a página está a sondar;
 *  · as PEÇAS do build (`PainelHardware`);
 *  · só com a política RL a voar: a rede, as observações, a ação e o computador de bordo — é o único
 *    caso em que esta janela precisa do `GET /api/sim`.
 */

import { useEffect, useState, type ReactNode } from "react"

import { PainelOtimizacaoMuJoCo } from "@/components/cockpit/painel-otimizacao-mujoco"
import { Legenda, Marca } from "@/components/cockpit/pecas"
import { PainelHardware } from "@/components/sim/hardware"
import { QuemFazOQue } from "@/components/sim/quem-faz-o-que"
import { FOVY_BORDO_OMISSAO, fmtHud, type TomEstado } from "@/lib/cockpit"
import type { ControladorEstado, CustoIa } from "@/lib/controlador"
import { hud, type MedidasHud } from "@/lib/hud-store"
import type { FpvEstado, Hardware } from "@/lib/sim"

/** As medidas do HUD (ritmo, fonte, idade) lidas uma vez por segundo — só com esta janela aberta. */
function useMedidasHud(): MedidasHud {
  const [medidas, setMedidas] = useState<MedidasHud>(() => hud.medidas())
  useEffect(() => {
    const t = window.setInterval(() => setMedidas(hud.medidas()), 1000)
    return () => window.clearInterval(t)
  }, [])
  return medidas
}

function estadoModulo(modulo: FpvEstado | null): { texto: string; tom: TomEstado } {
  if (modulo === null) return { texto: "SEM MÓDULO", tom: "atencao" }
  if (modulo.ligada === false) return { texto: "DESLIGADA", tom: "atencao" }
  if (modulo.estadoVelho === true) return { texto: "PARADA", tom: "atencao" }
  return { texto: "A ENVIAR", tom: "ativo" }
}

function LinhaStream({
  nome,
  estado,
  valores,
  testid,
}: {
  nome: string
  estado: { texto: string; tom: TomEstado }
  valores: string
  testid: string
}) {
  return (
    <li
      data-testid={testid}
      className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 rounded-lg bg-white/5 px-3 py-2"
    >
      <span className="flex items-center gap-2.5 text-[0.78rem] text-hud">
        {nome}
        <Marca tom={estado.tom} className="!text-[0.65rem]">
          {estado.texto}
        </Marca>
      </span>
      <span className="font-mono text-[0.72rem] text-muted-foreground">
        {valores}
      </span>
    </li>
  )
}

/** `12,6 de 50 fps · 1920×1080` de um módulo de imagem (o que não vier fica «—»). */
function valoresModulo(modulo: FpvEstado | null, latencia: string): string {
  if (modulo === null) return "—"
  const fps = `${fmtHud(modulo.fpsMedido, 1)} de ${fmtHud(modulo.fpsNominal, 0)} fps`
  const res = modulo.saida === null ? "" : ` · ${modulo.saida[0]}×${modulo.saida[1]}`
  return `${fps}${res} · ${latencia}`
}

export interface JanelaSistemaProps {
  controlador: ControladorEstado | null
  multiIa: CustoIa | null
  hardware: Hardware | null
  fpv: FpvEstado | null
  simulacao: FpvEstado | null
  /** FoV vertical que o HUD publicou (`bola.fovy`); `null` = está a usar-se o de omissão. */
  fovyPublicado: number | null
  /** O `GET /api/sim` está a ser sondado agora? */
  simAtivo: boolean
  /** Os painéis da rede (só com a política RL a voar); `null` no modo clássico. */
  rede: ReactNode | null
}

export function JanelaSistema({
  controlador,
  multiIa,
  hardware,
  fpv,
  simulacao,
  fovyPublicado,
  simAtivo,
  rede,
}: JanelaSistemaProps) {
  const medidas = useMedidasHud()
  const hudVivo = medidas.idadeMs !== null && medidas.idadeMs <= 1000
  const quem =
    controlador === null
      ? null
      : (controlador.fonte ??
        (controlador.modo === "classico"
          ? "cascata clássica C++"
          : "política RL"))

  return (
    <div className="flex flex-col gap-4" data-testid="painel-sistema">
      <PainelOtimizacaoMuJoCo />

      <section className="flex flex-col gap-2">
        <Legenda>quem está a voar</Legenda>
        <p
          data-testid="sistema-quem-voa"
          data-modo={controlador?.modo ?? ""}
          className="rounded-lg bg-white/5 px-3 py-2 text-sm text-hud"
        >
          {quem === null ? (
            "À espera do simulador."
          ) : (
            <>
              <strong>{quem}</strong>
              <span className="text-muted-foreground">
                {" "}
                — escolhido no arranque: voa o controlador que ganhou na medição
                (não há seletor).
              </span>
            </>
          )}
          {controlador !== null && controlador.estado !== "pronto" ? (
            <span className="mt-1 block text-[0.72rem] text-hud-ambar" data-testid="sistema-controlador-estado">
              estado: {controlador.estado}
              {controlador.motivo ? ` — ${controlador.motivo}` : ""}
            </span>
          ) : null}
        </p>
        <QuemFazOQue controlador={controlador} multiIa={multiIa} />
      </section>

      <section className="flex flex-col gap-2">
        <Legenda>streams · medido agora</Legenda>
        <ul className="flex flex-col gap-1.5" data-testid="sistema-streams">
          <LinhaStream
            testid="stream-fpv"
            nome="Câmara de bordo (1.ª pessoa)"
            estado={estadoModulo(fpv)}
            valores={valoresModulo(
              fpv,
              fpv?.latencia?.totalMs == null
                ? "latência —"
                : `latência ${fmtHud(fpv.latencia.totalMs, 0)} ms (modelo da câmara)`
            )}
          />
          <LinhaStream
            testid="stream-simulacao"
            nome="Simulação (3.ª pessoa)"
            estado={estadoModulo(simulacao)}
            valores={valoresModulo(simulacao, "entrega imediata")}
          />
          <LinhaStream
            testid="stream-hud"
            nome="HUD (instrumentos)"
            estado={
              hudVivo
                ? { texto: "AO VIVO", tom: "ativo" }
                : { texto: "SEM DADOS", tom: "atencao" }
            }
            valores={`${fmtHud(medidas.hz, 0)} Hz · ${
              medidas.fonte === "sse"
                ? "SSE"
                : medidas.fonte === "sondagem"
                  ? "sondagem (SSE em baixo)"
                  : "—"
            } · amostra há ${medidas.idadeMs === null ? "—" : fmtHud(medidas.idadeMs, 0)} ms`}
          />
          <LinhaStream
            testid="stream-api"
            nome="Sondagem da API"
            estado={
              simAtivo
                ? { texto: "COM HISTÓRICO", tom: "normal" }
                : { texto: "LEVE", tom: "ativo" }
            }
            valores={
              simAtivo
                ? "/api/state 1×/s · /api/sim ~3×/s (janela de detalhe aberta)"
                : "/api/state 1×/s · /api/sim parado"
            }
          />
        </ul>
        <p className="text-[0.68rem] leading-snug text-muted-foreground" data-testid="sistema-fovy">
          Campo de visão vertical da câmara de bordo usado pelo HUD (horizonte e
          retículo):{" "}
          <strong className="font-mono text-hud">
            {fmtHud(fovyPublicado ?? FOVY_BORDO_OMISSAO, 1)}°
          </strong>{" "}
          {fovyPublicado === null
            ? "— valor de omissão do módulo (o simulador ainda não o publicou)."
            : "— publicado pelo simulador."}
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <Legenda>peças do drone</Legenda>
        <PainelHardware hardware={hardware} />
      </section>

      {rede !== null ? (
        <section className="flex flex-col gap-3" data-testid="sistema-rede">
          <Legenda>política RL · a rede a decidir</Legenda>
          {rede}
        </section>
      ) : null}
    </div>
  )
}
