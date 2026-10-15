/**
 * Janela AJUDA (tecla 8 ou `?`) — as teclas e como ler o HUD. Curta de propósito: o cockpit explica-se
 * a voar; isto é a cábula.
 */

import { Atalho, FormaTom, Legenda } from "@/components/cockpit/pecas"
import { ATALHOS, type TomEstado } from "@/lib/cockpit"

const SINAIS: readonly { tom: TomEstado; cor: string; texto: string }[] = [
  { tom: "ativo", cor: "text-hud-verde", texto: "ativo: a voar, a seguir a bola, vento ligado" },
  { tom: "atencao", cor: "text-hud-ambar", texto: "atenção: rajada, bateria fraca, sem ligação" },
  { tom: "perigo", cor: "text-hud-vermelho", texto: "perigo: caiu, bateria crítica" },
  { tom: "normal", cor: "text-hud", texto: "leitura normal" },
]

export function JanelaAjuda() {
  return (
    <div
      className="grid gap-x-5 gap-y-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]"
      data-testid="painel-ajuda"
    >
      <section className="flex flex-col gap-1.5 sm:row-span-2">
        <Legenda>teclas</Legenda>
        <ul className="flex flex-col">
          {ATALHOS.map((atalho) => (
            <li
              key={atalho.teclas.join("")}
              className="flex items-center gap-3 border-b border-white/8 py-1.5 last:border-0"
            >
              <span className="flex w-[4.75rem] shrink-0 items-center gap-1">
                {atalho.teclas.map((tecla) =>
                  tecla === "…" ? (
                    <span key={tecla} className="text-muted-foreground">
                      …
                    </span>
                  ) : (
                    <Atalho key={tecla}>{tecla}</Atalho>
                  )
                )}
              </span>
              <span className="text-[0.78rem] leading-snug text-hud">
                {atalho.faz}
              </span>
            </li>
          ))}
        </ul>
        <p className="text-[0.7rem] leading-snug text-muted-foreground">
          As teclas valem sempre, exceto com o cursor num campo de texto. Sem
          teclas o drone segura a posição; sair da página solta-as todas.
        </p>
      </section>

      <section className="flex flex-col gap-1.5">
        <Legenda>como ler o ecrã</Legenda>
        <ul className="flex flex-col gap-1 text-[0.76rem] leading-snug text-hud">
          <li>
            <strong>Vista</strong> — 1.ª pessoa (a câmara de bordo) ou 3.ª
            pessoa; a outra fica na miniatura. Em 3.ª pessoa arrasta-se a vista
            para orbitar, a roda aproxima e o duplo clique repõe.
          </li>
          <li>
            <strong>Instrumentos</strong> — o que os sensores de bordo dizem
            (não a verdade do simulador): velocidade à esquerda, altitude à
            direita, rumo em cima. O rumo conta desde a descolagem e cresce para
            a esquerda.
          </li>
          <li>
            <strong>Horizonte</strong> — a linha dos sensores sobre a imagem,
            desenhada com o atraso da câmara (~0,1 s) para assentar no que se
            vê; os números são sempre os de agora.
          </li>
          <li>
            <strong>Vento</strong> — a seta mostra para onde o vento empurra o
            drone, com o nariz para cima.
          </li>
          <li>
            <strong className="text-hud-magenta">Retículo magenta</strong> — onde
            o detetor de bordo vê a bola; a linha liga-o à mira.
          </li>
        </ul>
      </section>

      <section className="flex flex-col gap-1.5">
        <Legenda>sinais (forma + cor)</Legenda>
        <ul className="grid grid-cols-1 gap-1">
          {SINAIS.map((sinal) => (
            <li key={sinal.tom} className="flex items-center gap-2 text-[0.76rem] text-hud">
              <span className={sinal.cor}>
                <FormaTom tom={sinal.tom} className="size-3" />
              </span>
              {sinal.texto}
            </li>
          ))}
          <li className="flex items-center gap-2 text-[0.76rem] text-hud">
            <span className="flex size-3 items-center justify-center rounded-[3px] bg-hud-ciano" />
            tecla cheia: o que o piloto está a mandar agora
          </li>
        </ul>
      </section>
    </div>
  )
}
