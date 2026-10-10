/**
 * AJUDA — o «?» que explica CADA elemento visível desta página.
 *
 * O conteúdo vive aqui como ESTRUTURA DE DADOS (`SECOES_AJUDA`), separado do desenho: o template só
 * percorre as secções, portanto acrescentar uma explicação é acrescentar um objecto (sem tocar em JSX).
 *
 * Cascata (motion-plus-ui): passo 2 — `sheet` (`Sheet` + `SheetBackdrop` + `SheetPanel` + `SheetClose`,
 * diálogo nativo com foco preso e arrasto para fechar) e `accordion` (`Accordion` + `AccordionItem` +
 * `AccordionTrigger` + `AccordionChevron` + `AccordionPanel`) para as secções; passo 3 — `Button` do
 * shadcn como gatilho fixo. Passo 4 só na LEGENDA (`definição`/`termo`) dos itens: o catálogo não tem
 * lista de definições, e é só texto com classes semânticas.
 *
 * As secções abrem TODAS por omissão: quem carrega no «?» quer ler, não descobrir onde clicar — e o
 * `AccordionPanel` só monta o painel quando está aberto, logo é isto que põe as explicações no DOM.
 */

import { useState } from "react"
import { HelpCircle } from "lucide-react"

import {
  Accordion,
  AccordionChevron,
  AccordionItem,
  AccordionPanel,
  AccordionTrigger,
} from "@/components/motion-ui/accordion"
import {
  Sheet,
  SheetBackdrop,
  SheetClose,
  SheetHandle,
  SheetPanel,
  useSheet,
} from "@/components/motion-ui/sheet"
import { Button } from "@/components/ui/button"
import { FOCUS_RING } from "@/components/sim/estilo"
import type { Planta } from "@/lib/sim"

/** Uma entrada da ajuda: o elemento tal como aparece no ecrã + o que ele é. */
export interface ItemAjuda {
  /** Nome do elemento, como está no ecrã. */
  rotulo: string
  /** O que é e para que serve (1–2 frases). */
  texto: string
}

export interface SeccaoAjuda {
  id: string
  titulo: string
  /** Onde está no ecrã (para o olho o encontrar depressa). */
  onde: string
  itens: ItemAjuda[]
  /** Só aparece com a PLANTA REAL (os blocos que explica não existem no cf2). */
  soPlantaReal?: boolean
}

/** Conteúdo da ajuda, secção a secção (PT-PT, curto). */
export const SECOES_AJUDA: SeccaoAjuda[] = [
  {
    id: "seccoes",
    titulo: "Seletor de secções (e escolha guardada)",
    onde: "barra fixa do topo — visível em qualquer secção",
    itens: [
      {
        rotulo: "o que é",
        texto:
          "A barra do topo tem 5 secções e só se vê UMA de cada vez: escolhes o que queres ver em vez de ver tudo ao mesmo tempo (menos ruído para vigiar o voo).",
      },
      {
        rotulo: "Operação (tecla 1)",
        texto:
          "o cockpit: cabeçalho (estado, contadores, modelo), valores atuais (altura, distância ao alvo, erro de rumo, vento), no drone real o «Painel de voo» (inclinação, rumo, altura, posição estimada vs real, giroscópio, acelerómetro, sensores) e o resumo «Bateria e motores», o bloco «Câmara» (vistas de cima e de lado, zoom, vistas rápidas) e as 4 curvas.",
      },
      {
        rotulo: "Rede (tecla 2)",
        texto:
          "ver a política a decidir: a rede com as ativações ao vivo (Crazyflie 16→64→64→4; drone real 21→128→128→4), as entradas da rede (no drone real com nomes simples e unidades do dia a dia) e a ação de 4 canais.",
      },
      {
        rotulo: "Vento (tecla 3)",
        texto:
          "comandar o vento: sliders do vento constante, rosa dos ventos, APLICAR/PARAR e o vento dinâmico (rajadas, aleatórias, Dryden, frente).",
      },
      {
        rotulo: "Bordo (tecla 4)",
        texto:
          "acompanhar o computador de bordo: painel do Raspberry Pi 5 (p50/p99 vs budget, semáforo, specs) e, no drone real, Bateria (curva de descarga, SoH, RECARREGAR/PACK NOVO), Motores e potência e Hardware.",
      },
      {
        rotulo: "Tudo (tecla 5)",
        texto:
          "layout completo: todas as secções de uma vez, com a coluna de controlos à direita (como o painel era antes do seletor).",
      },
      {
        rotulo: "atalhos 1–5",
        texto:
          "as teclas 1–5 saltam para a secção correspondente; as setas do teclado percorrem as abas. Os atalhos NÃO atuam enquanto escreves num campo nem com o rato/foco sobre um slider.",
      },
      {
        rotulo: "escolha guardada",
        texto:
          "a secção ativa fica guardada no navegador (localStorage) e reaparece quando reabres a página.",
      },
      {
        rotulo: "o que nunca se esconde",
        texto:
          "o estado crítico (API em baixo) e os controlos REINICIAR/CONTINUIDADE ficam sempre na barra do topo, em qualquer secção.",
      },
      {
        rotulo: "updates com a secção escondida",
        texto:
          "a telemetria continua a chegar (GET /api/sim) mesmo com a secção escondida: os widgets só não estão à vista; ao voltares, os valores estão frescos.",
      },
    ],
  },
  {
    id: "cabecalho",
    titulo: "Cabeçalho, selos e contadores",
    onde: "secção «Operação» (e «Tudo»)",
    itens: [
      {
        rotulo: "título e subtítulo",
        texto:
          "«Drone a pairar · política ao vivo»: Crazyflie 2 no MuJoCo 3.15, observação de 16 canais, rede 16→64→64→4 e alvo de altitude z = 1,0 m. Tudo o que se vê vem da telemetria real.",
      },
      {
        rotulo: "selo de estado",
        texto:
          "«a voar · episódio a correr» (ponto a pulsar) enquanto o episódio decorre; «episódio concluído · a física continua» (neutro) quando o episódio fechou por TEMPO — com o loop desligado o drone continua a voar com a política e o `passo`/`t` continuam a crescer; «caiu ou capotou» (vermelho) só quando o fim foi uma QUEDA (campo `fim` da telemetria). No modo contínuo o backend arranca logo o episódio seguinte; o site nunca reinicia sozinho — só o REINICIAR com hold faz POST /api/reiniciar.",
      },
      {
        rotulo: "selo de ligação",
        texto:
          "Estado do polling: «API ligada» é a última leitura com sucesso; passados 2 s sem resposta mostra há quanto tempo. Com o servidor em baixo fica «API em baixo» e aparece a faixa vermelha.",
      },
      {
        rotulo: "episódio · passos",
        texto:
          "Número do episódio e passos de decisão já publicados (a política decide a 50 Hz). O episódio novo zera os passos e o histórico.",
      },
      {
        rotulo: "retorno",
        texto:
          "Retorno acumulado do episódio — a soma das recompensas que a política está a tentar maximizar (subir ao alvo e ficar lá, sem bater no chão).",
      },
      {
        rotulo: "modelo",
        texto:
          "A política em uso, como «pasta/ficheiro.zip», lida do GET /api/state. Nunca se mostra o caminho absoluto: é um rótulo de painel, não um explorador de ficheiros.",
      },
    ],
  },
  {
    id: "curvas",
    titulo: "Curvas ao vivo",
    onde: "secção «Operação» (e «Tudo»), 4 gráficos",
    itens: [
      {
        rotulo: "altura",
        texto:
          "Altitude do drone (z, a verdade do simulador) ao longo do episódio, com a linha fina no alvo de 1,0 m. Abaixo do gráfico: mínimo, máximo e nº de pontos guardados.",
      },
      {
        rotulo: "erro de rumo",
        texto:
          "Quanto o nariz rodou face ao rumo do arranque (yaw_err), em GRAUS, com alvo 0°: diz se o drone está a rodar sobre si mesmo, o que acontece com vento lateral.",
      },
      {
        rotulo: "retorno",
        texto:
          "Retorno acumulado (a mesma soma do cabeçalho) em forma de curva: sobe enquanto a política se porta bem.",
      },
      {
        rotulo: "vento",
        texto:
          "Norma do vento aplicado em cada passo, em m/s (vento_vel). Com rajadas ou turbulência ligadas é aqui que se vê a dinâmica a mexer o vento.",
      },
      {
        rotulo: "valores atuais (cartões grandes)",
        texto:
          "Altura (m), distância ao alvo na horizontal (cm), erro de rumo (graus) e vento (m/s) do último passo — a verdade do simulador; o que o drone ACHA está no Painel de voo.",
      },
      {
        rotulo: "mín · máx · pts",
        texto:
          "Leituras da janela guardada no browser (600 pontos). O histórico é acumulado por ep:passo e reinicia quando muda o episódio.",
      },
    ],
  },
  {
    id: "camera",
    titulo: "Câmara da janela 3D",
    onde: "secção «Operação» (e «Tudo»), bloco «Câmara da janela 3D»",
    itens: [
      {
        rotulo: "o que é",
        texto:
          "Comanda a câmara da janela MuJoCo como a terceira pessoa de um jogo: o alvo é SEMPRE o drone (o backend segue-o a cada frame) e aqui escolhes de ONDE olhas. A linha «onde · altura · distância» diz em português onde a câmara está (ex.: «atrás, à direita · 35° por cima · 2,0 m»).",
      },
      {
        rotulo: "vista de cima",
        texto:
          "O drone visto de cima com o NARIZ PARA CIMA (frente/trás/esquerda/direita são as do drone) e o ícone da câmara ONDE ela está, com o cone de visão a apontar ao drone. Arrasta o ícone (ou clica noutro ponto do círculo) para rodar a câmara à volta do drone. ↺/↻ = ±15°.",
      },
      {
        rotulo: "vista de lado",
        texto:
          "O drone de perfil e a câmara num arco à volta dele: arrasta para cima/baixo para mudar a altura da câmara (de 30° por baixo a quase a pique). O chão está desenhado À ESCALA (altura do drone ÷ distância): se a câmara ficar abaixo dele o ícone fica vermelho e aparece um aviso. ▲/▼ = ±10°.",
      },
      {
        rotulo: "zoom",
        texto:
          "Slider LOGARÍTMICO (o detalhe perto do drone ganha trilho) com −/+ (×1,25) e a roda do rato por cima das vistas. Limites por planta: drone real 0,6–15 m (com 650 mm de frame, mais perto ficava dentro das hélices); Crazyflie 0,1–5 m.",
      },
      {
        rotulo: "vistas rápidas · repor vista",
        texto:
          "Um clique: Atrás (perseguição, a olhar para onde o nariz aponta), Frente, Esquerda, Direita, De cima (a pique, nariz para cima na imagem) e À altura (3/4 à frente, à altura do drone). São relativas ao rumo REAL do drone e mantêm o teu zoom. «Repor vista» volta à vista com que a janela abriu (camera_padrao).",
      },
      {
        rotulo: "teclado",
        texto:
          "Com o foco numa das vistas: ← → orbitam ±15°, ↑ ↓ sobem/descem ±10°, + e − aproximam/afastam, Home repõe a vista. As teclas 1–5 das secções não atuam com o foco numa vista.",
      },
      {
        rotulo: "estado e honestidade",
        texto:
          "O selo do bloco diz se a câmara está sincronizada com a janela, a enviar, a aplicar ou se falhou. Fora de um gesto o widget segue a CÂMARA REAL (inclusive quando a mexes com o rato da própria janela); durante o gesto a telemetria nunca o sobrescreve e os valores enviados são sempre os finais do gesto. Sem janela 3D (--sem-janela) o bloco diz porquê e desativa-se.",
      },
      {
        rotulo: "detalhes técnicos",
        texto:
          "Recolhidos no fim do bloco: azimute/elevação/distância exatos, alvo e posição da câmara, a convenção do MuJoCo (pos = alvo − d·f, f = [cos e·cos a, cos e·sin a, sin e]; elevação negativa = por cima) e o envio (POST /api/camera, 1 comando a cada 150 ms durante o gesto + o final).",
      },
    ],
  },
  {
    id: "painel-voo",
    titulo: "Painel de voo (drone real)",
    onde: "secção «Operação» (e «Tudo»), por baixo dos valores atuais",
    soPlantaReal: true,
    itens: [
      {
        rotulo: "estimado vs real",
        texto:
          "Ponto/ponteiro CHEIO = o que o drone ESTIMA a bordo, só com os sensores (é isto que a política vê); CONTORNO/tracejado = a verdade do simulador, só para comparar. A diferença é o erro do estimador.",
      },
      {
        rotulo: "inclinação (horizonte artificial)",
        texto:
          "Rolamento e arfagem estimados, em graus e por extenso («1,2° à direita», «0,4° nariz em baixo»). Convenção do simulador (x frente, y esquerda, z cima): arfagem positiva = nariz em BAIXO.",
      },
      {
        rotulo: "rumo",
        texto:
          "Quanto o nariz rodou desde o arranque. Sem bússola, o estimado integra o giroscópio e deriva devagar.",
      },
      {
        rotulo: "altura",
        texto:
          "Fita de 0 a 2 m com o alvo (tracejado): triângulo cheio = altura estimada (ToF + acelerómetro), contorno = real; por baixo a velocidade vertical em cm/s e se o sensor ToF está a ler.",
      },
      {
        rotulo: "posição (mapa visto de cima)",
        texto:
          "Desde o arranque, frente para cima (como a vista de cima da câmara): cruz = alvo, anéis a 5 e 10 cm, ponto cheio = posição que o RPi estima pela odometria do fluxo ótico, círculo = real, seta = velocidade estimada (1 s). O «erro do estimador» em cm é a distância entre os dois — é ele que limita a precisão em xy (a política segura a estimativa a 1–5 cm).",
      },
      {
        rotulo: "giroscópio · acelerómetro · sensores",
        texto:
          "Barras centradas no zero com escala física fixa (±60 °/s; ±0,5 g e 1 ± 1 g na vertical — a pairar o acelerómetro mede ≈ 1 g para cima); o círculo é o valor real. Os selos dizem se o ToF e o fluxo ótico estão a ler.",
      },
    ],
  },
  {
    id: "resumo-bordo",
    titulo: "Bateria e motores (resumo)",
    onde: "secção «Operação» (e «Tudo»), ao lado da Câmara",
    soPlantaReal: true,
    itens: [
      {
        rotulo: "o que mostra",
        texto:
          "Carga real (e a que o RPi estima), autonomia até à reserva de pouso, tensão (e por célula), corrente, potência (motores + bordo), rotação média dos motores, quanto do teto de empuxo está a ser usado e o estado dos ESC — com o alerta de tensão em destaque. O botão leva ao detalhe completo na secção «Bordo».",
      },
    ],
  },
  {
    id: "rede",
    titulo: "Rede da política · ativações",
    onde: "secção «Rede» (e «Tudo»), coluna principal",
    itens: [
      {
        rotulo: "entradas → escondidas → saídas",
        texto:
          "A rede da política: Crazyflie 16 → 64 → 64 → 4; drone real 21 → 128 → 128 → 4 (só o ATOR — o crítico do treino não vai para o drone). As grelhas mostram as ATIVAÇÕES de cada camada neste instante.",
      },
      {
        rotulo: "cor = |a| / máx da camada",
        texto:
          "Cor pela magnitude relativa ao máximo da própria camada: primary = ativação positiva, destructive = negativa (tokens shadcn, sem cores inventadas).",
      },
      {
        rotulo: "sem arestas",
        texto:
          "Não se desenham ligações entre neurónios porque o backend publica ativações, não pesos — desenhar arestas seria inventar dados.",
      },
    ],
  },
  {
    id: "obs",
    titulo: "Observação · 16 canais (Crazyflie 2)",
    onde: "secção «Rede» (e «Tudo»), sob a rede",
    itens: [
      {
        rotulo: "dp · dp_x, dp_y, dp_z",
        texto:
          "Posição relativa ao alvo (p − p_alvo), em metros: quanto o drone está desviado em cada eixo. Estes três canais entram ÷1 m.",
      },
      {
        rotulo: "rpy · roll/π, pitch/π, yaw/π",
        texto:
          "Atitude do drone (roll, pitch, yaw) em radianos, normalizada por π. O yaw é o erro de guinada, com alvo 0.",
      },
      {
        rotulo: "v · v_x, v_y, v_z",
        texto:
          "Velocidade linear do corpo em m/s, eixo a eixo. O v_z diz se está a subir ou a cair.",
      },
      {
        rotulo: "ω · ω_x, ω_y, ω_z",
        texto:
          "Velocidade angular (giroscópio) em rad/s, normalizada ÷10 rad/s: quão depressa está a rodar.",
      },
      {
        rotulo: "a_prev · empuxo, mx, my, mz",
        texto:
          "A AÇÃO do passo anterior em [-1,1] nos 4 canais: dá à política memória do que acabou de mandar (evita oscilar).",
      },
      {
        rotulo: "colunas obs / cru / barra",
        texto:
          "«obs» é o valor normalizado que a rede vê; «cru» devolve a unidade física (obs × escala fixa do env.py); a barra é |obs| face ao canal mais ativo do passo.",
      },
    ],
  },
  {
    id: "acao",
    titulo: "Ação · 4 canais",
    onde: "secção «Rede» (e «Tudo»), ao lado da observação",
    itens: [
      {
        rotulo: "a₀ · empuxo (N)",
        texto:
          "Empuxo pedido pelos motores: metade inferior do sinal vai de 0 a mg (peso), a superior de mg a thrust_max — é assim que o env.py traduz a ação em Newtons.",
      },
      {
        rotulo: "a₁, a₂, a₃ · momentos",
        texto:
          "Momentos de roll, pitch e yaw em N·m (ação × tau_escala × momento_max). É o que faz o drone inclinar e rodar.",
      },
      {
        rotulo: "«ctrl do backend» / «derivado da ação»",
        texto:
          "Se a telemetria trouxer o comando físico, mostra-se o do backend; se não, deriva-se localmente com as constantes do env.py (mg, thrust_max, momento_max).",
      },
    ],
  },
  {
    id: "vento",
    titulo: "Vento constante (sliders)",
    onde: "secção «Vento» (e «Tudo»), painel Controlos de vento",
    itens: [
      {
        rotulo: "força (0–5 m/s)",
        texto:
          "Velocidade do vento. 0 = ar parado. Escreve-se na física pelo POST /api/vento, sem parar a simulação.",
      },
      {
        rotulo: "azimute (0–360°)",
        texto:
          "Direção horizontal: 0° = +x = E, 90° = +y = N (anti-horário). É a direção PARA ONDE o vento aponta no plano.",
      },
      {
        rotulo: "elevação (−90…90°)",
        texto:
          "Componente vertical: positivo = vento a subir, negativo = a descer (rajadas verticais).",
      },
      {
        rotulo: "APLICAR VENTO",
        texto:
          "Envia os três valores (POST /api/vento) e escreve o ficheiro de controlo que o runner lê. O botão mostra o estado: pronto → a enviar → aplicado/erro, com aviso no canto.",
      },
      {
        rotulo: "PARAR VENTO",
        texto:
          "Para TUDO num só pedido (POST /api/parar): põe a força a 0 m/s (mantendo a direção guardada) e desliga o vento dinâmico no mesmo instante — nenhuma rajada (one-shot ou de um modo contínuo) fica a atuar depois do clique e o vento aplicado passa a ser exatamente o vento base comandado, 0 m/s.",
      },
    ],
  },
  {
    id: "dinamico",
    titulo: "Vento dinâmico (rajadas · aleatórias · turbulência · frente)",
    onde: "secção «Vento» (e «Tudo»), caixa «vento dinâmico»",
    itens: [
      {
        rotulo: "selo ativo/inativo e «modo em vigor»",
        texto:
          "O que o servidor está mesmo a fazer: modo, parâmetros e se está ligado. Vem do vento_dinamico do /api/sim e da última linha da telemetria (vento_modo).",
      },
      {
        rotulo: "PARADO · RAJADAS · ALEATÓRIA · DRYDEN",
        texto:
          "Modos contínuos. RAJADAS: com probabilidade p começa uma rajada de rajadas até u_max que SOMA ao vento base durante «duração» passos. ALEATÓRIA: cada rajada sorteia direção E força de novo dentro das faixas disponíveis (0–5 m/s, azimute 0–360°, elevação ±90°), sem teto u_max, e é MISTURADA com o vento base pelo envelope — no pico do envelope o vento é a rajada sorteada e nas pontas fica junto do base (o módulo nunca passa 5 m/s). DRYDEN: turbulência que passeia em torno do vento base. PARADO desliga tudo.",
      },
      {
        rotulo: "p · duração · u_max",
        texto:
          "Parâmetros das rajadas (valores por omissão do treino: p = 0,02, duração = 10 passos = 0,2 s, u_max = 3,0 m/s). u_max é o teto do modo e u_max = 0 torna-o inerte. Em ALEATÓRIA só p e duração contam: o u_max é aceite mas ignorado (a amplitude sai sempre de U[0, 5] m/s).",
      },
      {
        rotulo: "sigma · L · v_min",
        texto:
          "Parâmetros da turbulência Dryden: intensidade (σ), escala de comprimento (L) e o piso de velocidade v_min que evita congelar a turbulência quando o vento base é nulo.",
      },
      {
        rotulo: "RAJADA AGORA",
        texto:
          "Uma rajada única, imediata, com a duração em passos que estiver no campo e a força/azimute/elevação dos sliders. O botão fica «RAJADA EM CURSO» enquanto ela dura.",
      },
      {
        rotulo: "FRENTE AGORA",
        texto:
          "Degrau de vento imediato: substitui o vento base pelos valores dos sliders (vento que muda de repente a meio do voo) e vê-se logo na telemetria (`vento_vec`/`vento_vel`). Clicar outra vez desliga — o botão fica «FRENTE EM VIGOR» enquanto está ativa.",
      },
      {
        rotulo: "PARAR DINÂMICO",
        texto:
          'Envia {modo: "nenhum", ativo: false}: para TUDO o que seja dinâmica — corta a rajada one-shot em curso, desliga o modo contínuo e limpa o estado do modo no simulador (rajada/turbulência/frente) — e deixa o vento no vento base em vigor. Para parar o vento base também, usa o PARAR VENTO. Nenhum destes botões reinicia o episódio.',
      },
    ],
  },
  {
    id: "rosa",
    titulo: "Rosa dos ventos",
    onde: "secção «Vento» (e «Tudo»), sob os sliders",
    itens: [
      {
        rotulo: "seta sólida = vento em vigor",
        texto:
          "Vetor que está mesmo aplicado na física (vento base + dinâmica), lido de vento_vec na telemetria. O comprimento é a norma (0–5 m/s) e o ângulo é o azimute.",
      },
      {
        rotulo: "seta tracejada = seleção",
        texto:
          "Direção que os sliders mandariam se carregasses em APLICAR VENTO — serve para comparar com o que a física está a fazer.",
      },
      {
        rotulo: "N · E · S · O e graus",
        texto:
          "Bússola com a convenção do simulador: E = 0°, N = 90°, O = 180°, S = 270° (azimute anti-horário a partir de +x). As marcas de 30° dão a escala.",
      },
      {
        rotulo: "anel a pulsar",
        texto:
          "Aparece quando há dinâmica ativa: cheio/a pulsar depressa com rajadas, tracejado com turbulência ou frente. O centro também mostra a componente vertical (elevação).",
      },
    ],
  },
  {
    id: "rpi5",
    titulo: "Raspberry Pi 5 (computador de bordo)",
    onde: "secção «Bordo» (e «Tudo»), coluna principal",
    itens: [
      {
        rotulo: "imagem e fonte",
        texto:
          "A placa em que a política voaria a bordo — é uma ILUSTRAÇÃO de referência (Raspberry Pi Model B+, não um Pi 5: Lucasbosch, Wikimedia Commons, CC BY-SA 3.0). O selo «fonte» diz de onde vêm os números: «real» (medidos no Pi 5), «proxy x86 calibrado» (estimados a partir de um PC x86) ou «sem benchmark» — neste caso não se inventa nenhum tempo.",
      },
      {
        rotulo: "semáforo OK / ATENÇÃO / ERRO",
        texto:
          "Saúde do tempo real derivada do p99: OK até 70 % do orçamento, ATENÇÃO acima disso (pouca margem) e ERRO quando o p99 passa os 100 %. Sem números não há semáforo.",
      },
      {
        rotulo: "p50 / p99 vs budget",
        texto:
          "Latência típica (p50) e de cauda (p99) da inferência comparadas com o orçamento por decisão (20 ms a 50 Hz). Acima de 100 % a barra fica vermelha: a política não caberia no tempo real.",
      },
      {
        rotulo: "CPU equivalente",
        texto:
          "Percentagem do CPU do alvo que a inferência ocupa, com a latência estimada e as decisões por segundo a que isso corresponde.",
      },
      {
        rotulo: "modelo · fator int8 · pior caso · núcleos multi-IA",
        texto:
          "Tamanho da política em KB, ganho da quantização int8 face ao fp32, o pior caso medido e quantos núcleos seriam precisos para correr várias políticas em paralelo — todos calculados pelo backend.",
      },
      {
        rotulo: "estado do hardware",
        texto:
          "Temperatura e `vcgencmd get_throttled` quando o backend os publicar; sem Pi 5 ligado diz «sem hardware» (o site nunca inventa leituras do sistema).",
      },
      {
        rotulo: "nota do jitter do SO",
        texto:
          "A inferência desta rede é muito mais barata que o orçamento; quem costuma estourá-lo é o jitter do sistema operativo (escalonamento), muito menor num kernel PREEMPT_RT. É por isso que o painel mostra a cauda (p99/pior caso) e não só a média.",
      },
      {
        rotulo: "specs do alvo",
        texto:
          "CPU, RAM, orçamento por decisão e núcleos/NPU do alvo, como o backend os anuncia. Tudo isto atualiza com o polling (2,9 Hz), sem recarregar a página.",
      },
    ],
  },
  {
    id: "planta-real",
    titulo: "Planta real · observação e ação",
    onde: "secções «Operação», «Rede» e barra fixa — só com a planta real",
    soPlantaReal: true,
    itens: [
      {
        rotulo: "o que muda",
        texto:
          "Com a planta REAL (o drone do dono: peças reais, bateria, motores BLDC, sensores com erro) a política só vê o que existe a bordo. O subtítulo do cabeçalho diz o build; a rede e as tabelas mudam de rótulos sozinhas (com o Crazyflie fica tudo como antes).",
      },
      {
        rotulo: "entradas da rede · 21 canais",
        texto:
          "Cada canal com um nome simples, o valor numa unidade do dia a dia (°/s, g, °, cm, cm/s, sim/não), o número normalizado que entra na rede e uma barra CENTRADA no zero com a escala física do canal (vermelha = fora da faixa): rotação medida (giroscópio), aceleração medida (g), inclinação e rumo estimados, altura em relação ao alvo e velocidade vertical, velocidade pelo fluxo ótico, posição pela odometria, ToF/fluxo válidos e a última ação. Passa o rato numa linha para a explicação.",
      },
      {
        rotulo: "ação ctbr · ctrl por rotor",
        texto:
          "a₀ = coletivo LINEAR EM EMPUXO (−1 = sem empuxo, 0 = pairar, +1 = 2× o peso; a tensão medida da bateria é compensada) e a₁..₃ = taxas p, q, r até ±2/2/1 rad/s (±115/115/57 °/s, os valores do env_real publicados pelo backend) que o FC dedicado fecha a 500 Hz; a coluna «pedido» mostra o empuxo pedido (× o peso) e os setpoints de taxa. O ctrl publicado é o EMPUXO de cada rotor (N), com a barra face ao teto atual e o traço da pairagem (m·g/4).",
      },
      {
        rotulo: "selo de bateria na barra fixa",
        texto:
          "SoC % do pack em qualquer secção; fica vermelho com TENSÃO BAIXA e cheio com CRÍTICA, e diz REFORMAR quando o SoH chega a 80 %.",
      },
    ],
  },
  {
    id: "bateria",
    titulo: "Bateria (planta real)",
    onde: "secção «Bordo» (e «Tudo»)",
    soPlantaReal: true,
    itens: [
      {
        rotulo: "SoC real · SoC estimado (RPi)",
        texto:
          "O real é o do modelo do pack; o estimado é o que o RPi saberia: OCV em repouso no arranque + contagem de Coulomb com a corrente medida pelo monitor, sobre a capacidade nominal. Não conhece o desgaste, por isso diverge do real quando o pack envelhece. Na barra, o traço é o estimado.",
      },
      {
        rotulo: "curva de descarga",
        texto:
          "SoC real (linha) e estimado (tracejado) nas amostras guardadas no browser (até 600, desde o início do episódio). O eixo ajusta-se aos dados com limites redondos escritos ao lado; passa o rato (ou foca e usa as setas) para ler um instante.",
      },
      {
        rotulo: "tensão · corrente · potência · autonomia",
        texto:
          "Tensão do pack e por célula (com os limites de pouso e de corte da química), corrente e potência reais (e o que o monitor mede), autonomia restante até à reserva de pouso com a corrente média («—» com os motores parados).",
      },
      {
        rotulo: "SoH · ciclos · R₀ · temperatura",
        texto:
          "SoH = capacidade atual / nominal (REFORMAR a 80 %), ciclos equivalentes e recargas, resistência interna efetiva (sobe no frio, no fim da descarga e com o desgaste) e a temperatura do pack.",
      },
      {
        rotulo: "TENSÃO BAIXA · CRÍTICA",
        texto:
          "TENSÃO BAIXA = abaixo da tensão de pouso da química (pousar); CRÍTICA = abaixo do corte (brownout iminente) — em vermelho cheio, no bloco e na barra fixa.",
      },
      {
        rotulo: "RECARREGAR · PACK NOVO",
        texto:
          "POST /api/bateria. RECARREGAR fecha o ciclo em curso (aplica o desgaste) e põe o pack a 100 %; PACK NOVO (manter 1 s) troca por um pack novo e apaga o histórico de desgaste. O servidor confirma o pedido (seq) e o efeito chega na telemetria — o «último ciclo fechado» mostra o resumo. Nenhum dos dois reinicia o episódio.",
      },
    ],
  },
  {
    id: "motores",
    titulo: "Motores e potência (planta real)",
    onde: "secção «Bordo» (e «Tudo»)",
    soPlantaReal: true,
    itens: [
      {
        rotulo: "os 4 rotores (vista de cima)",
        texto:
          "Frente para cima: r1 frente-esq, r4 frente-dir, r3 trás-esq, r2 trás-dir. Cada um com rpm, duty do ESC, empuxo (N, barra face ao teto atual, traço = pairagem), corrente de fase (A) e o sentido de rotação visto de cima — r1/r2 CW, r3/r4 CCW (diagonais iguais).",
      },
      {
        rotulo: "teto de empuxo vs bateria cheia",
        texto:
          "ω_max e T_max por rotor com a tensão ATUAL. O teto de rotação/empuxo decai com a tensão da bateria (ω_max ∝ V, T_max = kf·ω_max²): a barra diz quanto dele resta face à bateria cheia.",
      },
      {
        rotulo: "κ_T · ao chão",
        texto:
          "Fator de empuxo de cada rotor = efeito de solo × inflow × VRS (1 = ar livre, > 1 perto do chão) e a altura do rotor ao chão («sem chão» quando não há chão no raio).",
      },
      {
        rotulo: "ledger de potência",
        texto:
          "motores + eletrónica = total do pack; a eletrónica são os consumidores de 5 V (RPi 5, FC, sensores…) mais as perdas do BEC.",
      },
      {
        rotulo: "ESC ARMADO · BROWNOUT",
        texto:
          "Estado dos ESC; BROWNOUT = a tensão caiu abaixo do limite do BEC/ESC, os motores desligam e o drone cai pela física.",
      },
    ],
  },
  {
    id: "hardware",
    titulo: "Hardware (peças reais)",
    onde: "secção «Bordo» (e «Tudo»)",
    soPlantaReal: true,
    itens: [
      {
        rotulo: "build e peças",
        texto:
          "O hardware.json do modelo em uso (GET /api/state): build, motor, hélice, célula/pack, frame e ESC — as peças com que a política foi treinada.",
      },
      {
        rotulo: "números do build",
        texto:
          "massa total, T/W com a bateria cheia, ω_max, potência e g/W a pairar, autonomia estimada de bancada e o kf/kq (com a origem: tabela do fabricante ou coeficientes da hélice).",
      },
      {
        rotulo: "trocar de peças",
        texto:
          "O catálogo está em models/drone_rpi/componentes.json e as montagens em builds.json; troca-se com experiments/09_drone_hover_rl/hardware.py usar <build>. Outro build pede um treino novo.",
      },
    ],
  },
  {
    id: "episodio",
    titulo: "REINICIAR · CONTINUIDADE · estados e avisos",
    onde: "barra fixa do topo (REINICIAR · CONTINUIDADE) + faixa de estado",
    itens: [
      {
        rotulo: "REINICIAR (manter 1 s)",
        texto:
          "Único controlo que reinicia: está na barra fixa do topo (em qualquer secção); mantém o botão carregado ~1 s (o preenchimento confirma, para não reiniciar por engano) e envia POST /api/reiniciar. O drone volta a assentar no chão pela física. É o ÚNICO reset que existe — com «sem reinício» a simulação continua sozinha e o REINICIAR só serve para começar outro episódio; com «contínuo» o backend vira o episódio sozinho e ele não é preciso.",
      },
      {
        rotulo: "CONTINUIDADE · CONTÍNUO / SEM REINÍCIO",
        texto:
          "Está na barra fixa do topo (em qualquer secção) e mostra o que o BACKEND está a fazer (campo `loop` da API), não uma preferência do browser. CONTÍNUO = ao terminar, o backend reinicia sozinho e arranca já o episódio seguinte; SEM REINÍCIO = no fim do episódio a física CONTINUA no estado em que ficou (se caiu, fica onde a física o deixou; se pairava, continua a pairar) — nunca reinicia sozinha e nunca congela: só um REINICIAR recomeça. O padrão do laboratório é SEM REINÍCIO, e o arranque é autoritativo (corrige o `loop` do ficheiro de controlo; `--com-loop` liga o CONTÍNUO). Depois do arranque, só este toggle o muda. O site limita-se a fazer POST /api/loop.",
      },
      {
        rotulo: "faixa de estado do episódio",
        texto:
          "Em «contínuo» diz «episódio a correr · modo contínuo» e, na transição, «episódio N terminado · o backend arranca já o seguinte» numa linha NEUTRA (sem pedir nada). Em «sem reinício» diz «episódio N concluído · sem reinício: o drone continua a voar com a política (REINICIAR = episódio novo)» — também NEUTRA, porque nada é exigido: o `passo`/`t` continuam a subir na telemetria; se o fim foi uma queda, a frase di-lo. O que exige ação — API em baixo — fica sempre vermelho, em qualquer secção.",
      },
      {
        rotulo: "aviso de episódio novo",
        texto:
          "No modo contínuo aparece um toast discreto «episódio N · contínuo» quando o backend vira o episódio (não bloqueia nada nem pede clique); um REINICIAR teu já tem o seu próprio aviso e não é duplicado.",
      },
      {
        rotulo: "avisos (toasts)",
        texto:
          "No fundo do ecrã: confirmações e erros das ações (vento aplicado, rajada enviada, continuidade, reinício) e os 400 do servidor com o motivo. Erros ficam 8 s e sucesso 5 s.",
      },
      {
        rotulo: "esqueleto e «sem passos»",
        texto:
          "Antes da primeira leitura aparecem blocos cinzentos (skeleton); se o servidor responder mas ainda não houver passos, avisa-se que as curvas e a rede ficam vazias até o episódio arrancar.",
      },
      {
        rotulo: "como os dados chegam",
        texto:
          "GET /api/sim a cada 350 ms (~2,9 Hz) traz o estado, o vento e as linhas novas; os controlos escrevem por POST (vento, vento dinâmico, parar, reiniciar, loop, câmara e bateria). Não há websockets nem recarregamento da página — e com uma secção escondida os updates CONTINUAM (o seletor só esconde a renderização); ao voltares, os valores estão frescos.",
      },
    ],
  },
]

/** Ids de todas as secções — abrem de início, para o texto estar todo à vista (e no DOM). */
export const SECOES_AJUDA_ABERTAS: string[] = SECOES_AJUDA.map((s) => s.id)

interface AjudaProps {
  /** Id do título (ligado ao `aria-labelledby` do painel). */
  idTitulo?: string
  /** Planta em vigor: as secções `soPlantaReal` só aparecem com `"real"` (no cf2 a ajuda fica igual). */
  planta?: Planta | null
}

/**
 * Botão «?» fixo no canto inferior direito. É um filho do `Sheet` que não é backdrop nem painel (page
 * part), logo pode usar o `useSheet()` do catálogo para abrir a folha — sem gatilho escondido nem CSS a
 * forçar posição dentro do `SheetTrigger`.
 */
function GatilhoAjuda() {
  const { setOpen } = useSheet()
  return (
    <Button
      type="button"
      size="icon-lg"
      aria-label="ajuda: explicar cada elemento desta página"
      aria-haspopup="dialog"
      data-testid="botao-ajuda"
      className={`fixed right-4 bottom-4 z-40 rounded-full shadow-lg ${FOCUS_RING}`}
      onClick={() => setOpen(true)}
    >
      <HelpCircle className="size-5" aria-hidden="true" />
    </Button>
  )
}

/**
 * A ajuda abre já aberta com `?ajuda=1` no URL (link partilhável e prova de DOM nos testes, como o
 * `?api=` que aponta o `dist/` a outro porto). Sem parâmetro, começa fechada.
 */
export function ajudaAbertaPorLink(): boolean {
  const valor = new URLSearchParams(window.location.search).get("ajuda")
  return valor === "1" || valor === "true"
}

/** Botão «?» + folha de ajuda com todas as secções (abertas por omissão). */
export function Ajuda({ idTitulo = "ajuda-titulo", planta = null }: AjudaProps) {
  const [aberta] = useState(ajudaAbertaPorLink)
  const real = planta === "real"
  const seccoes = SECOES_AJUDA.filter((s) => !s.soPlantaReal || real)
  // Abertas = exatamente as secções mostradas (no cf2 é a lista de sempre). O acordeão remonta quando a
  // planta muda (`key`), para as secções da planta real também nascerem abertas.
  const abertas = seccoes.map((s) => s.id)
  return (
    <Sheet defaultOpen={aberta}>
      <GatilhoAjuda />

      <SheetBackdrop label="fechar a ajuda" />
      <SheetPanel
        labelledBy={idTitulo}
        className="max-h-[78svh] overflow-y-auto overscroll-contain lg:max-w-2xl"
      >
        <SheetHandle />
        <div className="mb-2 flex items-start justify-between gap-3">
          <div className="flex flex-col gap-0.5">
            <h2
              id={idTitulo}
              className="text-sm font-semibold"
              data-testid="titulo-ajuda"
            >
              O que é cada elemento desta página
            </h2>
            <p className="text-[0.7rem] text-muted-foreground">
              simulação do drone a pairar (MuJoCo + política RL) · clica numa
              secção para abrir ou fechar · arrasta a folha para baixo para
              fechar
            </p>
          </div>
          <SheetClose label="fechar a ajuda" />
        </div>

        <Accordion
          key={real ? "real" : "cf2"}
          multiple
          defaultValue={abertas}
          className="flex flex-col"
        >
          {seccoes.map((seccao) => (
            <AccordionItem
              key={seccao.id}
              value={seccao.id}
              className="border-b border-border/60 last:border-b-0"
            >
              <AccordionTrigger
                headingLevel={3}
                inset
                indicator={<AccordionChevron />}
              >
                <span className="flex min-w-0 flex-col gap-0.5 py-1 text-left">
                  <span
                    className="text-xs font-medium"
                    data-testid={`ajuda-seccao-${seccao.id}`}
                  >
                    {seccao.titulo}
                  </span>
                  <span className="text-[0.65rem] text-muted-foreground">
                    {seccao.onde}
                  </span>
                </span>
              </AccordionTrigger>
              <AccordionPanel>
                <dl
                  className="flex flex-col gap-2 pt-1 pb-3"
                  data-testid={`ajuda-conteudo-${seccao.id}`}
                >
                  {seccao.itens.map((item) => (
                    <div key={item.rotulo} className="flex flex-col gap-0.5">
                      <dt className="font-mono text-[0.7rem] text-foreground">
                        {item.rotulo}
                      </dt>
                      <dd className="text-[0.7rem] leading-snug text-muted-foreground">
                        {item.texto}
                      </dd>
                    </div>
                  ))}
                </dl>
              </AccordionPanel>
            </AccordionItem>
          ))}
        </Accordion>
      </SheetPanel>
    </Sheet>
  )
}
