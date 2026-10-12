/**
 * BLOCO «CÂMARA FPV» — o stream AO VIVO da câmara de bordo (MJPEG) + o que ela custa, sempre com a
 * separação honesta entre MODELO e MEDIDO:
 *
 *  · IMAGEM AO VIVO: `<img src="/api/fpv.mjpg">` (multipart/x-mixed-replace servido pelo
 *    `sim_site.py`; os headers `X-Fpv-Seq`/`X-Fpv-Captura-Ms` de cada parte não chegam ao `<img>`, o
 *    que é normal). SEM MÓDULO (`fpv: null`) o bloco diz «sem módulo de câmara» e nem mostra a
 *    imagem; com o módulo DESLIGADO a imagem fica parada no último quadro e a etiqueta diz-o.
 *  · ESTATÍSTICAS do estado do módulo (`fpv` do `/api/sim`): modo em vigor, resolução/MP de saída e
 *    do sensor, fps NOMINAL e MEDIDO, qualidade JPEG, bytes médios, bitrate, latência de MODELO com
 *    a faixa publicada e os quadros — tudo com «—» quando falta (nunca `undefined`/`NaN` no DOM).
 *  · CUSTO DO PI 5 por etapa = MODELO (faixas e fontes do `lab/camera_rpi.custo_cpu`; % de 1 núcleo
 *    A76), mais o `host_ms` MEDIDO nesta máquina (rotulado «medido no PC» — nunca misturado com o
 *    modelo).
 *  · CONTROLOS: LIGAR/DESLIGAR (`POST /api/fpv {ligada}`) e seletor de MODO (`POST /api/fpv {modo}`,
 *    só os modos EMULADOS — o HDR existe no hardware mas o backend recusa-o). Depois de cada POST o
 *    `use-sim` relê o `/api/sim` e o ecrã adota o estado confirmado; uma rejeição chega como aviso
 *    (padrão dos restantes controlos do site).
 */

import { useCallback, useState } from "react"
import { Video, VideoOff } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { TomAviso } from "@/components/sim/avisos"
import { FOCUS_RING } from "@/components/sim/estilo"
import { urlApi } from "@/lib/api"
import {
  fmt,
  fmtInteiro,
  MODOS_FPV,
  rotuloEtapaCustoFpv,
  type CorpoFpv,
  type FpvEtapaCusto,
  type FpvEstado,
  type SimulacaoEstado,
} from "@/lib/sim"

/** Texto de um valor opcional (nunca "undefined"/"NaN" no DOM). */
function ouTraco(valor: string | null): string {
  return valor ?? "—"
}

/** Número com unidade, ou «—» quando não há número (nada é inventado). */
function comUnidade(
  valor: number | null,
  unidade: string,
  casas = 2
): string {
  return valor === null ? "—" : `${fmt(valor, casas)} ${unidade}`
}

/** `[largura×altura]` como texto; `null` → «—». */
function resolucaoTexto(par: readonly [number, number] | null): string {
  return par === null
    ? "—"
    : `${fmtInteiro(par[0])}×${fmtInteiro(par[1])}`
}

/** Uma medição do estado do módulo (rótulo curto + valor monoespaçado). */
function Campo({
  rotulo,
  valor,
  testid,
}: {
  rotulo: string
  valor: string
  testid: string
}) {
  return (
    <div className="flex min-w-0 flex-col">
      <dt className="text-[0.6rem] tracking-wide text-muted-foreground uppercase">
        {rotulo}
      </dt>
      <dd
        className="truncate font-mono text-[0.75rem] tabular-nums"
        data-testid={testid}
      >
        {valor}
      </dd>
    </div>
  )
}

/**
 * Uma etapa do custo de CPU do Pi 5 (MODELO): «JPEG software 65 % (faixa 50–80)» com a fonte do
 * backend no `title`. Partilhado com o painel RPi 5 (secção «Câmara (módulo Pi)»).
 */
export function CustoEtapaFpv({
  etapa,
  testid,
}: {
  etapa: FpvEtapaCusto
  testid?: string
}) {
  return (
    <li
      className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5"
      data-testid={testid ?? `fpv-custo-etapa-${etapa.id}`}
      title={etapa.fonte ?? undefined}
    >
      <span className="text-[0.65rem] text-muted-foreground">
        {rotuloEtapaCustoFpv(etapa.id)}
      </span>
      <span className="font-mono text-[0.65rem] tabular-nums">
        {etapa.pct === null ? "—" : `${fmt(etapa.pct, 1)} %`} (faixa{" "}
        {ouTraco(etapa.faixa)})
        {etapa.dominio === null
          ? ""
          : ` · ${etapa.dominio === "saida" ? "saída" : etapa.dominio}`}
      </span>
    </li>
  )
}

export interface PainelFpvProps {
  /** Estado do módulo FPV (`fpv` do `/api/sim`); `null` = SEM MÓDULO → o bloco diz-o, sem inventar. */
  fpv: FpvEstado | null
  /**
   * Estado do módulo da FONTE `simulacao` (`simulacao` do `/api/sim`) — a vista 3ª-pessoa da
   * simulação, TROCÁVEL com a FPV pelo seletor de fonte. `null` = sem módulo.
   */
  simulacao: SimulacaoEstado | null
  /** `false` quando a API está em baixo (avisa-se e os controlos ficam desativados). */
  ligado: boolean
  /** Envio do comando (o `use-sim` faz `POST /api/fpv` + releitura do `/api/sim`); rejeição = aviso. */
  onEnviar: (corpo: CorpoFpv) => Promise<void>
  onAviso: (texto: string, tom: TomAviso) => void
}

type FaseEnvio = "repouso" | "a_enviar" | "erro"

export function PainelFpv({
  fpv,
  simulacao,
  ligado,
  onEnviar,
  onAviso,
}: PainelFpvProps) {
  const [fase, setFase] = useState<FaseEnvio>("repouso")
  /** FONTE da imagem: a FPV (módulo de bordo) ou a vista 3ª-pessoa da SIMULAÇÃO — trocam o `<img>`. */
  const [fonte, setFonte] = useState<"fpv" | "simulacao">("fpv")
  /** O módulo SELECIONADO: as estatísticas, os fallbacks e o custo são todos os dele. */
  const estado = fonte === "fpv" ? fpv : simulacao
  const urlStream = fonte === "fpv" ? "/api/fpv.mjpg" : "/api/simulacao.mjpg"
  /**
   * Modo pedido pelo utilizador e ainda não confirmado pelo estado do módulo. Mostra-se até o
   * servidor o confirmar (aí `estado.modo` muda e o otimista desfaz-se — derivação em render, como o
   * rumo do bloco «Câmara»); uma rejeição volta já ao estado do servidor. Quem manda é o servidor.
   */
  const [modoPedido, setModoPedido] = useState<{
    id: string
    base: string | null
  } | null>(null)
  if (
    modoPedido !== null &&
    (estado?.modo !== modoPedido.base || modoPedido.id === estado?.modo)
  ) {
    setModoPedido(null)
  }

  const sem = estado === null
  const aEnviar = fase === "a_enviar"
  const ligadaModulo = estado?.ligada === true
  const desligada = estado !== null && !ligadaModulo
  const estadoVelho = estado?.estadoVelho === true
  // Medições VIVAS (fps medido, bytes, bitrate, quadros): só fazem sentido com o módulo ligado e o
  // estado fresco — desligado/velho mostram «—» em vez de números congelados com aspeto de atuais.
  const medicoesVivas = ligadaModulo && !estadoVelho
  const [streamErro, setStreamErro] = useState(false)

  const enviar = useCallback(
    (corpo: CorpoFpv, descricao: string) => {
      setFase("a_enviar")
      void onEnviar(corpo)
        .then(() => {
          setFase("repouso")
          onAviso(`${descricao} — POST /api/fpv`, "ok")
        })
        .catch((erro: unknown) => {
          setFase("erro")
          setModoPedido(null)
          onAviso(
            `POST /api/fpv recusado — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
            "erro"
          )
        })
    },
    [onAviso, onEnviar]
  )

  const modoMostrado = modoPedido?.id ?? estado?.modo ?? ""
  /** O seletor oferece os modos EMULADOS; um modo desconhecido do backend acrescenta-se como opção. */
  const modoDesconhecido =
    modoMostrado !== "" && !MODOS_FPV.some((m) => m.id === modoMostrado)
  const etapas = estado?.custoPi5?.etapas ?? []
  const latencia = estado?.latencia ?? null
  const host = estado?.hostMs ?? null
  const h264 = estado?.custoPi5?.comparacaoH264 ?? null

  return (
    <Card className="gap-3" data-testid="painel-fpv">
      <CardHeader className="gap-1">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm font-medium">
          <span className="flex items-center gap-1.5">
            <Video className="size-4" aria-hidden="true" />
            Câmara FPV
            <span className="text-[0.7rem] font-normal text-muted-foreground">
              stream ao vivo da câmara de bordo
            </span>
          </span>
          <span
            data-testid="fpv-estado"
            data-estado={
              sem ? "sem_modulo" : ligadaModulo ? "ligada" : "desligada"
            }
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[0.7rem] font-normal ${
              sem
                ? "bg-muted text-muted-foreground"
                : ligadaModulo
                  ? "bg-primary/10 text-foreground"
                  : "bg-secondary text-secondary-foreground"
            }`}
          >
            <span
              aria-hidden="true"
              className={`size-1.5 rounded-full ${
                sem
                  ? "bg-muted-foreground/50"
                  : ligadaModulo
                    ? "bg-primary"
                    : "bg-muted-foreground"
              }`}
            />
            {sem
              ? "sem módulo"
              : ligadaModulo
                ? "módulo ligado"
                : "módulo desligado"}
          </span>
          {estado !== null && estado.idadeEstadoS !== null ? (
            <span
              data-testid="fpv-idade-estado"
              data-velho={estadoVelho ? "sim" : "nao"}
              className={`text-[0.65rem] ${estadoVelho ? "text-destructive" : "text-muted-foreground"}`}
            >
              {estadoVelho
                ? `estado há ${fmt(estado.idadeEstadoS, 1)} s (velho — runner parado?)`
                : `estado há ${fmt(estado.idadeEstadoS, 1)} s`}
            </span>
          ) : null}
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          imagem MJPEG direta do módulo de câmara (emulado no MuJoCo com os
          modos reais da Pi Camera) + o que ela custa: latência de modelo, bytes
          reais e o CPU do Pi 5 — MODELO com faixas, sempre separado do medido
          nesta máquina
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        {!ligado ? (
          <p
            className="text-[0.65rem] text-destructive"
            data-testid="fpv-sem-ligacao"
          >
            API em baixo: os controlos ficam desativados e o painel mantém a
            ÚLTIMA leitura conhecida, marcada como velha (nada é inventado nem
            atualizado em falso).
          </p>
        ) : null}

        {sem ? (
          <p
            className="rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground"
            data-testid="fpv-sem-modulo"
          >
            sem módulo de câmara: o runner corre sem o módulo FPV (ou ainda não
            publicou estado) — não há stream nem números e nada se inventa;
            quando o módulo existir o bloco ativa-se sozinho.
          </p>
        ) : (
          <>
            {/* SELETOR DE FONTE — a FPV (módulo de bordo, à frente do drone) ou a vista 3ª-pessoa da
                SIMULAÇÃO: troca só o `src` do <img> (e as estatísticas passam a ser do módulo
                selecionado). O bloco `fpv` do controlo manda nos DOIS (mesmo modo/ligação). */}
            <div
              className="flex items-center gap-2"
              role="group"
              aria-label="fonte da imagem"
              data-testid="fpv-fonte"
            >
              <button
                type="button"
                onClick={() => setFonte("fpv")}
                disabled={!ligado}
                aria-pressed={fonte === "fpv"}
                data-testid="fpv-fonte-fpv"
                className={`rounded-full px-3 py-1 text-[0.7rem] transition-colors disabled:opacity-50 ${
                  fonte === "fpv"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/70"
                }`}
              >
                FPV (bordo)
              </button>
              <button
                type="button"
                onClick={() => setFonte("simulacao")}
                disabled={!ligado}
                aria-pressed={fonte === "simulacao"}
                data-testid="fpv-fonte-simulacao"
                className={`rounded-full px-3 py-1 text-[0.7rem] transition-colors disabled:opacity-50 ${
                  fonte === "simulacao"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/70"
                }`}
              >
                Simulação (3.ª pessoa)
              </button>
              {fonte === "simulacao" ? (
                <span
                  className="text-[0.65rem] text-muted-foreground"
                  data-testid="fpv-fonte-nota"
                >
                  {estado?.notaFonte ??
                    "vista da simulação — não é hardware de bordo"}
                </span>
              ) : null}
            </div>

            {/* IMAGEM AO VIVO — o <img> pinta cada parte JPEG do multipart tal como ela chega. */}
            <figure className="flex flex-col gap-1.5">
              <img
                src={urlApi(urlStream)}
                alt="stream ao vivo da câmara FPV do drone (último quadro recebido)"
                loading="lazy"
                decoding="async"
                onError={() => setStreamErro(true)}
                onLoad={() => setStreamErro(false)}
                data-testid="fpv-imagem"
                className="aspect-video w-full rounded-lg border border-border/70 bg-muted/30 object-contain"
              />
              {streamErro ? (
                <p
                  className="rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground"
                  data-testid="fpv-stream-erro"
                >
                  stream indisponível — o servidor não está a entregar o
                  stream da fonte selecionada (runner parado ou rede em baixo);
                  a imagem não mostra nada em vez de fingir que corre.
                </p>
              ) : null}
              {desligada ? (
                <figcaption
                  className="text-[0.7rem] text-muted-foreground"
                  data-testid="fpv-desligada"
                >
                  módulo desligado — a imagem fica parada no último quadro;
                  LIGAR retoma o stream.
                </figcaption>
              ) : null}
            </figure>

            {/* CONTROLOS — ligar/desligar e o modo (só os EMULADOS; o HDR o backend recusa). */}
            <div
              className="flex flex-wrap items-center gap-2"
              data-testid="fpv-controlos"
            >
              <Button
                type="button"
                variant={desligada ? "default" : "destructive"}
                size="sm"
                disabled={!ligado || aEnviar}
                data-testid="fpv-ligar"
                title={
                  desligada
                    ? "ligar o módulo de câmara (POST /api/fpv {ligada: true})"
                    : "desligar o módulo de câmara (POST /api/fpv {ligada: false})"
                }
                onClick={() =>
                  enviar(
                    { ligada: desligada },
                    desligada ? "câmara FPV ligada" : "câmara FPV desligada"
                  )
                }
              >
                {desligada ? (
                  <Video aria-hidden="true" />
                ) : (
                  <VideoOff aria-hidden="true" />
                )}
                {desligada ? "LIGAR" : "DESLIGAR"}
              </Button>
              <label className="flex items-center gap-1.5 text-[0.7rem] text-muted-foreground">
                modo
                <select
                  data-testid="fpv-modo"
                  value={modoMostrado}
                  disabled={!ligado || aEnviar}
                  className={`rounded-lg border border-border bg-muted/40 px-2 py-1 text-[0.75rem] text-foreground ${FOCUS_RING}`}
                  onChange={(evento) => {
                    const id = evento.target.value
                    if (id === "" || id === estado?.modo) return
                    setModoPedido({ id, base: estado?.modo ?? null })
                    enviar(
                      { modo: id },
                      `modo ${id} pedido (o módulo aplica-o no ciclo seguinte)`
                    )
                  }}
                >
                  {modoDesconhecido ? (
                    <option value={modoMostrado}>
                      {ouTraco(estado?.modoRotulo ?? modoMostrado)}
                    </option>
                  ) : null}
                  {MODOS_FPV.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.rotulo}
                    </option>
                  ))}
                </select>
              </label>
              <span
                data-testid="fpv-envio"
                data-fase={fase}
                className="text-[0.65rem] text-muted-foreground"
              >
                {aEnviar
                  ? "a enviar…"
                  : fase === "erro"
                    ? "o último envio foi recusado"
                    : ""}
              </span>
            </div>

            {/* ESTATÍSTICAS do módulo — o que falta fica «—». */}
            <dl
              className="grid grid-cols-2 gap-2 rounded-xl bg-muted/40 px-3 py-2 sm:grid-cols-4"
              data-testid="fpv-estatisticas"
            >
              <Campo
                rotulo="modo em vigor"
                testid="fpv-modo-valor"
                valor={ouTraco(estado.modoRotulo ?? estado.modo)}
              />
              <Campo
                rotulo="resolução de saída"
                testid="fpv-saida"
                valor={resolucaoTexto(estado.saida)}
              />
              <Campo
                rotulo="MP · sensor"
                testid="fpv-mp-sensor"
                valor={comUnidade(estado.mpSensor, "MP")}
              />
              <Campo
                rotulo="MP · saída"
                testid="fpv-mp-saida"
                valor={comUnidade(estado.mpSaida, "MP")}
              />
              <Campo
                rotulo="fps nominal"
                testid="fpv-fps-nominal"
                valor={comUnidade(estado.fpsNominal, "fps")}
              />
              <Campo
                rotulo="fps medido"
                testid="fpv-fps-medido"
                valor={medicoesVivas ? comUnidade(estado.fpsMedido, "fps") : "—"}
              />
              <Campo
                rotulo="qualidade JPEG"
                testid="fpv-jpeg-qualidade"
                valor={comUnidade(estado.jpegQualidade, "%", 0)}
              />
              <Campo
                rotulo="bytes médios"
                testid="fpv-bytes-medio"
                valor={
                  medicoesVivas && estado.bytesMedio !== null
                    ? `${fmtInteiro(estado.bytesMedio)} B`
                    : "—"
                }
              />
              <Campo
                rotulo="bitrate"
                testid="fpv-bitrate"
                valor={medicoesVivas ? comUnidade(estado.bitrateMbps, "Mbps") : "—"}
              />
              <Campo
                rotulo="latência de modelo"
                testid="fpv-latencia"
                valor={comUnidade(latencia?.totalMs ?? null, "ms", 1)}
              />
              <Campo
                rotulo="faixa publicada"
                testid="fpv-latencia-faixa"
                valor={
                  latencia?.faixaPublicadaMs == null
                    ? "—"
                    : `${fmt(latencia.faixaPublicadaMs[0], 0)}–${fmt(latencia.faixaPublicadaMs[1], 0)} ms`
                }
              />
              <Campo
                rotulo="quadros"
                testid="fpv-quadros"
                valor={
                  medicoesVivas && estado.quadros !== null ? fmtInteiro(estado.quadros) : "—"
                }
              />
            </dl>

            {/* CUSTO NO PI 5 — MODELO por etapa (com faixas e fontes) + total em núcleos. */}
            <div
              className="flex flex-col gap-1.5 rounded-xl bg-muted/30 px-3 py-2"
              data-testid="fpv-custo"
            >
              <p className="text-[0.65rem] text-muted-foreground">
                custo no Pi 5 — MODELO (faixas das medições publicadas; % de 1
                núcleo Cortex-A76 @ 2,4 GHz; o Pi 5 não tem encoder JPEG
                hardware — o JPEG é software)
              </p>
              <ul className="flex flex-col gap-0.5">
                {etapas.length === 0 ? (
                  <li
                    className="font-mono text-[0.65rem] text-muted-foreground"
                    data-testid="fpv-custo-sem-etapas"
                  >
                    {estado.notaFonte ?? "— (sem modelo de custo publicado)"}
                  </li>
                ) : (
                  etapas.map((etapa) => (
                    <CustoEtapaFpv key={etapa.id} etapa={etapa} />
                  ))
                )}
              </ul>
              <p
                className="font-mono text-[0.65rem] tabular-nums"
                data-testid="fpv-custo-total"
              >
                total{" "}
                {estado.custoPi5?.totalPctNucleo == null
                  ? "—"
                  : `${fmt(estado.custoPi5.totalPctNucleo, 1)} %`}{" "}
                de 1 núcleo A76 ={" "}
                {comUnidade(estado.custoPi5?.totalNucleos ?? null, "núcleos", 3)}
              </p>
              <p
                className="font-mono text-[0.65rem] tabular-nums text-muted-foreground"
                data-testid="fpv-taxa"
              >
                taxa de píxeis: sensor{" "}
                {comUnidade(estado.custoPi5?.taxaMpS.sensor ?? null, "MP/s", 1)} ·
                saída{" "}
                {comUnidade(estado.custoPi5?.taxaMpS.saida ?? null, "MP/s", 1)}
                {h264?.rotulo ? ` · ${h264.rotulo}` : ""}
              </p>
            </div>

            {/* MEDIDO NESTA MÁQUINA — nunca misturado com o modelo do Pi. */}
            <p
              className="border-t border-border/70 pt-2 font-mono text-[0.65rem] leading-snug text-muted-foreground"
              data-testid="fpv-host"
            >
              <span className="font-medium text-foreground">medido no PC</span>{" "}
              (custo REAL deste pipeline nesta máquina, não é o Pi): render{" "}
              <span data-testid="fpv-host-render">
                {comUnidade(host?.renderMs ?? null, "ms")}
              </span>{" "}
              · isp{" "}
              <span data-testid="fpv-host-isp">
                {comUnidade(host?.ispMs ?? null, "ms")}
              </span>{" "}
              · jpeg{" "}
              <span data-testid="fpv-host-jpeg">
                {comUnidade(host?.jpegMs ?? null, "ms")}
              </span>{" "}
              · total{" "}
              <span data-testid="fpv-host-total">
                {comUnidade(host?.totalMs ?? null, "ms")}
              </span>
            </p>
            <p className="text-[0.6rem] leading-snug text-muted-foreground">
              honestidade: a latência e o custo do Pi 5 são MODELO (somas de
              estágios e âncoras com faixas — ver a ajuda «?»), o fps medido, os
              bytes e o «medido no PC» são MEDIÇÕES reais do que está a correr;
              a faixa publicada (150–300 ms para MJPEG 1080p em Pi) é da
              comunidade/documentação e vem tal e qual.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
