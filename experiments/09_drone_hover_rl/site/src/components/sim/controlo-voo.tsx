/**
 * CONTROLO DE VOO (secção «Operação» e «Tudo», DUAS as plantas) — as teclas WASD/QE a comandar o
 * drone pelo backend `sim_site.py` (contrato r11). Nada de overlays na janela 3D: todo o controlo
 * vive no site.
 *
 * Semântica de voo (frame MUNDO, yaw alvo 0): W = +x (frente), S = −x (trás), A = +y (esquerda),
 * D = −y (direita), Q = +z (subir), E = −z (descer); diagonais horizontais normalizadas para
 * 1,0 m/s, |vz| = 0,7 m/s e sem teclas `v_ref = [0,0,0]` = o drone SEGURA posição. Cada mudança de
 * estado manda o estado COMPLETO das 6 teclas em `POST /api/voo` (o `seq` é do servidor).
 *
 * Como se pilota (decisões de UX deste painel):
 *  · ARMAR/DESARMAR primeiro — só ARMADO é que as teclas são captadas (e só aí o `preventDefault`
 *    acontece); ao DESARMAR envia-se `{"ativo": false, "teclas": <tudo false>}` = tudo solto;
 *  · ESTADO OTIMISTA: os keycaps acendem/apagam IMEDIATAMENTE com o estado local (o teclado nunca
 *    espera pela rede) e cada mudança dispara um `POST /api/voo` assíncrono com política de
 *    «O ÚLTIMO VENCE»: havendo um POST em curso guarda-se só o estado MAIS RECENTE e envia-se
 *    quando o anterior terminar — as teclas intermédias nunca entram em fila;
 *  · falhas de envio → toast (`onAviso`) e re-sincronização com o eco do servidor (quem manda no
 *    ecrã é o que a simulação está mesmo a aplicar);
 *  · SEGURANÇA: `blur` da janela solta TUDO (e envia o estado zerado se alguma tecla estivesse
 *    pressionada); sair do painel (unmount) desarma; perder o modo comando (eco `voo: null` com
 *    telemetria a chegar) desarma e desativa os controlos;
 *  · RATO/TOQUE: os keycaps também funcionam com pointerdown/pointerup/pointerleave (para quem não
 *    tem teclado) com a MESMA semântica de tecla pressionada;
 *  · HONESTIDADE MULTI-CLIENTE: o que os keycaps mostram é o estado LOCAL (otimista); quando o eco
 *    da telemetria divergir (latência ou outro cliente), o painel mostra o estado do SERVIDOR.
 *
 * Estados honestos de disponibilidade (nada é inventado):
 *  · `eco === null` + amostras de telemetria > 0 → «modo comando indisponível: esta política não
 *    foi treinada com `--comandos`» e controlos desativados (`voo-indisponivel`);
 *  · sem amostras ainda → «à espera da simulação».
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as EventoApontador,
} from "react"
import { Keyboard } from "lucide-react"

import type { TomAviso } from "@/components/sim/avisos"
import { FOCUS_RING } from "@/components/sim/estilo"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { enviarVoo } from "@/lib/api"
import { fmt, fmtSinal } from "@/lib/sim"
import {
  TECLAS_VOO,
  TECLAS_VOO_ZERADAS,
  V_HORIZONTAL_M_S,
  V_VERTICAL_M_S,
  teclasAtivas,
  teclasIguais,
  vRefDeTeclas,
  type EcoVoo,
  type TeclaVoo,
  type TeclasVoo,
} from "@/lib/voo"

/** Rótulo físico de cada tecla: direção + eixo do mundo (contrato r11). */
const ROTULOS_TECLAS: Record<
  TeclaVoo,
  { direcao: string; eixo: string; completo: string }
> = {
  w: { direcao: "frente", eixo: "+x", completo: "W · +x frente" },
  a: { direcao: "esquerda", eixo: "+y", completo: "A · +y esquerda" },
  s: { direcao: "trás", eixo: "−x", completo: "S · −x trás" },
  d: { direcao: "direita", eixo: "−y", completo: "D · −y direita" },
  q: { direcao: "subir", eixo: "+z", completo: "Q · +z subir" },
  e: { direcao: "descer", eixo: "−z", completo: "E · −z descer" },
}

export interface ControloVooProps {
  /**
   * Eco do runner (`voo` do `/api/sim`, em reforço do `voo` da última linha); `null` = sem eco —
   * política sem modo comando (ou ainda sem telemetria).
   */
  eco: EcoVoo | null
  /** Nº de amostras de telemetria publicadas (`amostras` do `/api/state`); 0 = ainda sem simulação. */
  amostras: number
  /** O polling está a receber respostas (para o aviso de «API em baixo»). */
  ligado: boolean
  onAviso: (texto: string, tom: TomAviso) => void
}

/** O que o utilizador está a mandar AGORA (estado local otimista — espelhado numa ref para eventos). */
interface EstadoVoo {
  ativo: boolean
  teclas: TeclasVoo
}

interface KeycapProps {
  tecla: TeclaVoo
  ligada: boolean
  podeUsar: boolean
  onBaixar: (tecla: TeclaVoo) => void
  onSoltar: (tecla: TeclaVoo) => void
}

/**
 * Um keycap de voo: a letra grande + o rótulo físico (`frente`, `+x`). Ativo = INVERTIDO (fundo
 * cheio, texto em contraste, borda grossa e anel) — nunca só uma diferença de cor — e afundado
 * (`translate-y-px`), como uma tecla pressionada. Funciona com rato/toque (`pointerdown`/`up`/
 * `leave`/`cancel`) com a mesma semântica da tecla pressionada.
 */
function Keycap({ tecla, ligada, podeUsar, onBaixar, onSoltar }: KeycapProps) {
  const { direcao, eixo, completo } = ROTULOS_TECLAS[tecla]
  const soltar = () => onSoltar(tecla)
  return (
    <div className="flex min-w-0 flex-col items-center gap-1">
      <button
        type="button"
        data-testid={`tecla-${tecla}`}
        data-estado={ligada ? "ativa" : "inativa"}
        disabled={!podeUsar}
        aria-label={`tecla ${completo}`}
        aria-pressed={ligada}
        title={completo}
        className={`flex size-12 items-center justify-center rounded-xl text-base font-semibold transition-all select-none ${FOCUS_RING} ${
          ligada
            ? "translate-y-px border-2 border-foreground bg-foreground text-background ring-2 ring-foreground/40"
            : "border border-border bg-muted/60 text-muted-foreground hover:border-foreground/40 hover:text-foreground"
        }`}
        onPointerDown={(evento: EventoApontador<HTMLButtonElement>) => {
          if (!podeUsar) return
          evento.preventDefault()
          onBaixar(tecla)
        }}
        onPointerUp={soltar}
        onPointerLeave={soltar}
        onPointerCancel={soltar}
        onContextMenu={(evento) => evento.preventDefault()}
      >
        {tecla.toUpperCase()}
      </button>
      <span className="text-center text-[0.65rem] leading-tight text-muted-foreground">
        {direcao}
        <span className="ml-1 font-mono text-foreground/70">{eixo}</span>
      </span>
    </div>
  )
}

/** Texto curto das teclas pressionadas (`"W Q"` ou `"nenhuma tecla"`). */
function textoTeclas(teclas: TeclasVoo): string {
  const ativas = teclasAtivas(teclas)
  return ativas.length > 0
    ? ativas.map((t) => t.toUpperCase()).join(" ")
    : "nenhuma tecla"
}

/** `+1,00 x · +0,00 y · +0,00 z m/s` (o v_ref em m/s, mundo). */
function textoVRef(v: [number, number, number]): string {
  return `${fmtSinal(v[0], 2)} x · ${fmtSinal(v[1], 2)} y · ${fmtSinal(v[2], 2)} z m/s`
}

export function ControloVoo({
  eco,
  amostras,
  ligado,
  onAviso,
}: ControloVooProps) {
  /** Estado LOCAL otimista (os keycaps seguem ESTE estado, sem esperar pela rede). */
  const [ativo, setAtivo] = useState(false)
  const [teclas, setTeclas] = useState<TeclasVoo>(TECLAS_VOO_ZERADAS)
  /** Espelho síncrono do estado local: os handlers de teclado/pointer leem-no sem depender do render. */
  const estadoRef = useRef<EstadoVoo>({
    ativo: false,
    teclas: TECLAS_VOO_ZERADAS,
  })
  /** Último eco visto (para a re-sincronização quando um envio falha). */
  const ecoRef = useRef<EcoVoo | null>(eco)
  useEffect(() => {
    ecoRef.current = eco
  }, [eco])

  // ------------------------------------------------- disponibilidade (estados honestos, nada inventado)
  const disponivel = eco !== null
  const indisponivel = eco === null && amostras > 0
  const aEspera = eco === null && amostras <= 0

  // ------------------------------------------------- envio «O ÚLTIMO VENCE» (nunca bloqueia o teclado)
  const pendente = useRef<EstadoVoo | null>(null)
  const emEnvio = useRef(false)
  const enfileirar = useCallback(
    (novo: EstadoVoo) => {
      pendente.current = novo
      if (emEnvio.current) return // já há um POST em curso: fica só o estado MAIS RECENTE
      emEnvio.current = true
      void (async () => {
        while (pendente.current !== null) {
          const alvo = pendente.current
          pendente.current = null // os estados intermédios descartam-se
          try {
            await enviarVoo(alvo)
          } catch (erro) {
            onAviso(
              `POST /api/voo falhou — ${erro instanceof Error ? erro.message : "falha desconhecida"}`,
              "erro"
            )
            // Re-sincronização com o eco: quem manda no ecrã é o que a simulação está a aplicar.
            const ecoAgora = ecoRef.current
            if (ecoAgora !== null) {
              estadoRef.current = {
                ativo: ecoAgora.ativo,
                teclas: { ...ecoAgora.teclas },
              }
              setAtivo(ecoAgora.ativo)
              setTeclas(estadoRef.current.teclas)
            }
          }
        }
        emEnvio.current = false
      })()
    },
    [onAviso]
  )

  /** Aplica um estado novo (local + envio assíncrono). Chamado por teclado, rato e botões. */
  const aplicar = useCallback(
    (novo: EstadoVoo) => {
      estadoRef.current = novo
      setAtivo(novo.ativo)
      setTeclas(novo.teclas)
      enfileirar(novo)
    },
    [enfileirar]
  )

  /** Pressiona/solta UMA tecla (só envia quando o estado muda de facto). */
  const mudarTecla = useCallback(
    (tecla: TeclaVoo, ligada: boolean) => {
      const atual = estadoRef.current
      if (atual.teclas[tecla] === ligada) return
      aplicar({
        ativo: atual.ativo,
        teclas: { ...atual.teclas, [tecla]: ligada },
      })
    },
    [aplicar]
  )

  // ------------------------------------------------- teclado (janela), só enquanto ARMADO
  useEffect(() => {
    if (!ativo || !disponivel) return
    /** Escrever num campo nunca se intercepta (input/textarea/select/contenteditable). */
    const emEdicao = (alvo: EventTarget | null): boolean => {
      if (!(alvo instanceof HTMLElement)) return false
      const etiqueta = alvo.tagName.toLowerCase()
      return (
        etiqueta === "input" ||
        etiqueta === "textarea" ||
        etiqueta === "select" ||
        alvo.isContentEditable
      )
    }
    const teclaDoEvento = (evento: KeyboardEvent): TeclaVoo | null => {
      // Modificadores ficam para os atalhos do browser (Ctrl+W e companhia nunca se roubam).
      if (evento.ctrlKey || evento.metaKey || evento.altKey) return null
      const k = evento.key.toLowerCase()
      return (TECLAS_VOO as readonly string[]).includes(k)
        ? (k as TeclaVoo)
        : null
    }
    const aoBaixar = (evento: KeyboardEvent) => {
      const tecla = teclaDoEvento(evento)
      if (tecla === null || emEdicao(evento.target)) return
      // Enquanto armado, as teclas de voo não rolam a página nem escrevem nada.
      evento.preventDefault()
      mudarTecla(tecla, true)
    }
    const aoSubir = (evento: KeyboardEvent) => {
      // O keyup SOLTA SEMPRE (mesmo vindo de um campo): uma tecla nunca fica presa se o foco
      // saltar para um input a meio da pressão.
      const tecla = teclaDoEvento(evento)
      if (tecla === null) return
      mudarTecla(tecla, false)
    }
    window.addEventListener("keydown", aoBaixar)
    window.addEventListener("keyup", aoSubir)
    return () => {
      window.removeEventListener("keydown", aoBaixar)
      window.removeEventListener("keyup", aoSubir)
    }
  }, [ativo, disponivel, mudarTecla])

  // ------------------------------------------------- segurança: blur, unmount e perda do modo comando
  useEffect(() => {
    const aoPerderFoco = () => {
      const atual = estadoRef.current
      if (!atual.ativo) return
      const alguma = TECLAS_VOO.some((tecla) => atual.teclas[tecla])
      // Soltar TUDO. Só se envia quando havia tecla pressionada (senão o estado já era o zerado).
      if (!alguma) return
      aplicar({ ativo: true, teclas: { ...TECLAS_VOO_ZERADAS } })
    }
    window.addEventListener("blur", aoPerderFoco)
    return () => window.removeEventListener("blur", aoPerderFoco)
  }, [aplicar])

  useEffect(
    () => () => {
      // Sair do painel com o controlo armado: desarma por segurança (não bloqueia a saída).
      if (!estadoRef.current.ativo) return
      void enviarVoo({
        ativo: false,
        teclas: { ...TECLAS_VOO_ZERADAS },
      }).catch(() => undefined)
    },
    []
  )

  useEffect(() => {
    // Perdeu-se o modo comando (outra política/runner) com o controlo armado: desarma e desativa.
    if (disponivel || !estadoRef.current.ativo) return
    aplicar({ ativo: false, teclas: { ...TECLAS_VOO_ZERADAS } })
  }, [aplicar, disponivel])

  // ------------------------------------------------- ARMAR / DESARMAR
  const alternar = useCallback(() => {
    const atual = estadoRef.current
    if (!atual.ativo) {
      aplicar({ ativo: true, teclas: { ...TECLAS_VOO_ZERADAS } })
      onAviso("controlo de voo ARMADO — W/A/S/D/Q/E comandam o drone", "info")
    } else {
      aplicar({ ativo: false, teclas: { ...TECLAS_VOO_ZERADAS } })
      onAviso("controlo de voo desarmado — teclas soltas", "info")
    }
  }, [aplicar, onAviso])

  // ------------------------------------------------- leitura de estado (do eco da telemetria)
  // COMANDO LOCAL (otimista) — o `v_ref` que o piloto está a mandar AGORA: como os keycaps, aparece
  // ao INSTANTE (`voo-vref`). O eco da telemetria atrasa 100–300 ms e lê-se à parte (`voo-vref-eco`).
  const vRefLocal: [number, number, number] = ativo
    ? vRefDeTeclas(teclas)
    : [0, 0, 0]
  const diverge =
    eco !== null && (eco.ativo !== ativo || !teclasIguais(eco.teclas, teclas))
  const seguindo = eco?.seguindo ?? null

  return (
    <Card className="gap-3" data-testid="controlo-voo">
      <CardHeader className="gap-1">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm font-medium">
          <span className="flex items-center gap-1.5">
            <Keyboard className="size-4" aria-hidden="true" />
            Controlo de voo · teclas WASD/QE
          </span>
          <span
            data-testid="voo-ativo"
            data-estado={ativo ? "armado" : "desarmado"}
            aria-live="polite"
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[0.7rem] font-normal ${
              ativo
                ? "border border-foreground bg-foreground text-background"
                : "border border-border bg-muted text-muted-foreground"
            }`}
          >
            <span
              aria-hidden="true"
              className={`size-1.5 rounded-full ${
                ativo ? "animate-pulse bg-background" : "bg-muted-foreground/50"
              }`}
            />
            {ativo ? "ARMADO" : "em espera"}
          </span>
        </CardTitle>
        <p className="text-[0.7rem] text-muted-foreground">
          arma o controlo e pilota o drone: W/S frente-trás, A/D
          esquerda-direita, Q/E subir-descer ({fmt(V_HORIZONTAL_M_S, 1)} m/s na
          horizontal, {fmt(V_VERTICAL_M_S, 1)} m/s na vertical) — sem teclas o
          drone SEGURA a posição
        </p>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {/* DISPONIBILIDADE honesta do modo comando */}
        <p
          data-testid="voo-indisponivel"
          data-estado={
            indisponivel ? "indisponivel" : aEspera ? "espera" : "pronto"
          }
          hidden={disponivel}
          className={
            disponivel
              ? "sr-only"
              : "rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground"
          }
        >
          {indisponivel
            ? "modo comando indisponível: esta política não foi treinada com --comandos"
            : "à espera da simulação: os controlos ativam-se quando a telemetria publicar o eco voo"}
        </p>

        {/* TECLAS — W em cima, ASD por baixo, o par vertical Q/E ao lado */}
        <div
          className="flex items-start justify-center gap-6"
          data-testid="voo-teclas"
        >
          <div className="flex flex-col items-center gap-1.5">
            <Keycap
              tecla="w"
              ligada={teclas.w}
              podeUsar={disponivel}
              onBaixar={(t) => mudarTecla(t, true)}
              onSoltar={(t) => mudarTecla(t, false)}
            />
            <div className="flex gap-1.5">
              <Keycap
                tecla="a"
                ligada={teclas.a}
                podeUsar={disponivel}
                onBaixar={(t) => mudarTecla(t, true)}
                onSoltar={(t) => mudarTecla(t, false)}
              />
              <Keycap
                tecla="s"
                ligada={teclas.s}
                podeUsar={disponivel}
                onBaixar={(t) => mudarTecla(t, true)}
                onSoltar={(t) => mudarTecla(t, false)}
              />
              <Keycap
                tecla="d"
                ligada={teclas.d}
                podeUsar={disponivel}
                onBaixar={(t) => mudarTecla(t, true)}
                onSoltar={(t) => mudarTecla(t, false)}
              />
            </div>
          </div>
          <div className="flex flex-col items-center gap-1.5">
            <Keycap
              tecla="q"
              ligada={teclas.q}
              podeUsar={disponivel}
              onBaixar={(t) => mudarTecla(t, true)}
              onSoltar={(t) => mudarTecla(t, false)}
            />
            <Keycap
              tecla="e"
              ligada={teclas.e}
              podeUsar={disponivel}
              onBaixar={(t) => mudarTecla(t, true)}
              onSoltar={(t) => mudarTecla(t, false)}
            />
          </div>
        </div>

        {/* ARMAR / DESARMAR */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant={ativo ? "destructive" : "default"}
            size="lg"
            className="rounded-full"
            data-testid="voo-ativar"
            disabled={!disponivel}
            title={
              ativo
                ? "desarmar o controlo de voo (solta as 6 teclas)"
                : "armar o controlo de voo (W/A/S/D/Q/E passam a comandar)"
            }
            onClick={alternar}
          >
            {ativo ? "DESARMAR" : "ARMAR CONTROLO"}
          </Button>
          <p className="text-[0.65rem] text-muted-foreground">
            {disponivel
              ? "só com ARMADO é que as teclas são captadas (também dá com rato/toque nos keycaps)"
              : "controlos desativados — sem modo comando"}
            {!ligado ? " · API em baixo: os comandos não chegam" : ""}
          </p>
        </div>

        {/* LEITURA — o comando LOCAL ao instante (`voo-vref`) + o que o runner está MESMO a aplicar
            (eco da telemetria: `voo-vref-eco`, `voo-pref`, `voo-erros`, `voo-seguindo`) */}
        <dl
          className="grid grid-cols-2 gap-2 rounded-xl bg-muted/40 px-3 py-2 sm:grid-cols-4"
          data-testid="voo-leitura"
        >
          <div className="flex min-w-0 flex-col">
            <dt className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              v_ref (comando)
            </dt>
            <dd
              className="truncate text-sm font-medium tabular-nums"
              data-testid="voo-vref"
            >
              {textoVRef(vRefLocal)}
            </dd>
            <dd
              className="truncate text-[0.65rem] text-muted-foreground tabular-nums"
              data-testid="voo-vref-eco"
            >
              eco: {eco === null ? "—" : textoVRef(eco.v_ref)}
            </dd>
          </div>
          <div className="flex min-w-0 flex-col">
            <dt className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              p_ref
            </dt>
            <dd
              className="truncate text-sm font-medium tabular-nums"
              data-testid="voo-pref"
            >
              {eco === null
                ? "—"
                : `[${fmt(eco.p_ref[0], 2)} · ${fmt(eco.p_ref[1], 2)} · ${fmt(eco.p_ref[2], 2)}] m`}
            </dd>
          </div>
          <div className="flex min-w-0 flex-col">
            <dt className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              erros
            </dt>
            <dd
              className="truncate text-sm font-medium tabular-nums"
              data-testid="voo-erros"
            >
              {eco === null
                ? "—"
                : `xy ${fmt(eco.erro_xy * 100, 1)} cm · z ${fmt(eco.erro_z * 100, 1)} cm · v ${fmt(eco.erro_v, 2)} m/s`}
            </dd>
          </div>
          <div className="flex min-w-0 flex-col">
            <dt className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
              seguimento
            </dt>
            <dd
              className={`truncate text-sm font-medium ${
                seguindo === true ? "text-foreground" : "text-muted-foreground"
              }`}
              data-testid="voo-seguindo"
              data-seguindo={seguindo === null ? "" : seguindo ? "sim" : "nao"}
            >
              {seguindo === null ? "—" : seguindo ? "A SEGUIR ✓" : "a corrigir"}
            </dd>
          </div>
        </dl>

        {/* HONESTIDADE MULTI-CLIENTE — o eco diverge do local (latência ou outro cliente) */}
        <p
          data-testid="voo-eco"
          data-diverge={diverge ? "sim" : "nao"}
          hidden={!diverge}
          className="rounded-lg border border-dashed border-foreground/30 px-3 py-2 text-[0.7rem] text-muted-foreground"
        >
          estado no servidor (eco):{" "}
          {eco === null ? "—" : textoTeclas(eco.teclas)} ·{" "}
          {eco?.ativo === true ? "armado" : "em espera"} — as teclas do servidor
          estão atrás do teu teclado ou são de OUTRO cliente; os keycaps mostram
          o teu estado local
        </p>

        {/* Valores crus para as provas de DOM (sem parse de vírgulas decimais). */}
        <output
          className="sr-only"
          data-testid="voo-raw"
          data-disponivel={disponivel ? "sim" : "nao"}
          data-ativo={ativo ? "sim" : "nao"}
          data-teclas={textoTeclas(teclas)}
          data-eco-ativo={eco?.ativo === true ? "sim" : "nao"}
          data-vx={eco === null ? "" : String(eco.v_ref[0])}
          data-vy={eco === null ? "" : String(eco.v_ref[1])}
          data-vz={eco === null ? "" : String(eco.v_ref[2])}
          data-erro-xy={eco === null ? "" : String(eco.erro_xy)}
          data-erro-z={eco === null ? "" : String(eco.erro_z)}
          data-erro-v={eco === null ? "" : String(eco.erro_v)}
          data-seguindo={seguindo === null ? "" : seguindo ? "sim" : "nao"}
        />

        <details className="group rounded-lg bg-muted/30 px-3 py-2 text-[0.65rem] text-muted-foreground">
          <summary
            className={`cursor-pointer text-xs font-medium text-foreground ${FOCUS_RING}`}
          >
            detalhes técnicos
          </summary>
          <div className="mt-2 flex flex-col gap-1.5">
            <p className="font-mono" data-testid="voo-mapa">
              {ROTULOS_TECLAS.w.completo} · {ROTULOS_TECLAS.a.completo} ·{" "}
              {ROTULOS_TECLAS.s.completo} · {ROTULOS_TECLAS.d.completo} ·{" "}
              {ROTULOS_TECLAS.q.completo} · {ROTULOS_TECLAS.e.completo}
            </p>
            <p>
              v_ref em m/s no frame MUNDO (yaw alvo 0): W = +x, S = −x, A = +y,
              D = −y, Q = +z, E = −z; diagonais horizontais normalizadas para{" "}
              {fmt(V_HORIZONTAL_M_S, 1)} m/s e |vz| = {fmt(V_VERTICAL_M_S, 1)}{" "}
              m/s. Envio: POST /api/voo com {"{ativo, teclas: {w,a,s,d,q,e}}"}{" "}
              (as 6 teclas sempre presentes, sem `seq` — o servidor carimba o
              dele) a cada mudança, com política de «o último vence»; o eco
              `voo` da telemetria traz{" "}
              {
                "{ativo, teclas, v_ref, p_ref, erro_xy, erro_z, erro_v, seguindo}"
              }{" "}
              e é ele que este painel lê. Fora do modo comando (política sem{" "}
              <code className="font-mono">--comandos</code>) o eco vem `null` e
              o painel desativa-se.
            </p>
          </div>
        </details>
      </CardContent>
    </Card>
  )
}
