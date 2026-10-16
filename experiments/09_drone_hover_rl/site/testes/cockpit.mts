/**
 * Teste do COCKPIT (contrato r13, `INTERFACE.md` §0): a lógica pura de `src/lib/cockpit.ts` — o parser
 * do HUD, a projeção do retículo com `object-fit: cover`, o mapa de teclas (com yaw), os limites do
 * vento e da bola, o envio «o último vence» e a gestão das janelas. Corre sem dependências:
 * `node testes/cockpit.mts` (Node ≥ 22.6 com type-stripping; o módulo é importado tal como o site o usa).
 *
 * Os números «medidos» vêm do runner real (2026-10-12, planta real, modo clássico): a amostra do HUD,
 * a posição da bola num quadro de 1920×1080 (679, 560 px para `erro_tan` = [−0,34456; 0,02345] com
 * `fovy` = 67°) e os sinais de roll/pitch/yaw.
 *
 * MUTAÇÕES: no fim, o mesmo conjunto de verificações corre contra cópias ADULTERADAS do módulo (uma
 * linha trocada de cada vez). Cada mutante TEM de ser apanhado — um teste que não falha com o código
 * estragado não está a testar nada.
 */

import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { pathToFileURL } from "node:url"

import type { CorpoVoo } from "../src/lib/api.ts"
import * as real from "../src/lib/cockpit.ts"

type Modulo = typeof real

/** Uma verificação: o nome e se passou. */
interface Resultado {
  nome: string
  passou: boolean
}

function aprox(a: number, b: number, eps = 1e-9): boolean {
  return Math.abs(a - b) <= eps
}

/** Deixa assentar as promessas pendentes (os envios falsos resolvem em microtarefas). */
async function assentar(): Promise<void> {
  for (let i = 0; i < 8; i += 1) await Promise.resolve()
}

/** Relógio + agendador falsos: o tempo só anda quando o teste manda. */
function tempoFalso() {
  let agora = 0
  let proximo = 1
  const tarefas = new Map<number, { quando: number; tarefa: () => void }>()
  return {
    relogio: () => agora,
    agendar: (tarefa: () => void, ms: number): unknown => {
      const id = proximo
      proximo += 1
      tarefas.set(id, { quando: agora + ms, tarefa })
      return id
    },
    cancelar: (handle: unknown) => {
      tarefas.delete(handle as number)
    },
    /** Avança o relógio e dispara o que venceu (por ordem). */
    avancar(ms: number) {
      agora += ms
      for (;;) {
        const vencidas = [...tarefas.entries()]
          .filter(([, t]) => t.quando <= agora)
          .sort((a, b) => a[1].quando - b[1].quando)
        if (vencidas.length === 0) return
        const [id, t] = vencidas[0]
        tarefas.delete(id)
        t.tarefa()
      }
    },
  }
}

/** Um `enviar` falso: guarda os corpos e deixa o teste decidir quando (e como) cada POST responde. */
function envioFalso<T, R>(resposta: (valor: T) => R) {
  const enviados: T[] = []
  const pendentes: { ok: () => void; falha: (erro: unknown) => void }[] = []
  let emVoo = 0
  let maxEmVoo = 0
  return {
    enviados,
    get maxEmVoo() {
      return maxEmVoo
    },
    enviar: (valor: T): Promise<R> => {
      enviados.push(valor)
      emVoo += 1
      maxEmVoo = Math.max(maxEmVoo, emVoo)
      return new Promise<R>((resolver, rejeitar) => {
        pendentes.push({
          ok: () => {
            emVoo -= 1
            resolver(resposta(valor))
          },
          falha: (erro) => {
            emVoo -= 1
            rejeitar(erro)
          },
        })
      })
    },
    /** Responde ao POST mais antigo ainda em voo. */
    async responder(falha = false) {
      const p = pendentes.shift()
      if (p === undefined) return
      if (falha) p.falha(new Error("400"))
      else p.ok()
      await assentar()
    },
  }
}

/** Amostra REAL do `GET /api/hud` (runner em modo clássico, planta real), com o modo bola ligado. */
const AMOSTRA = {
  t: 13.06,
  passo: 603,
  ep: 1,
  fase: "a_voar",
  pausado: false,
  vento: [0.0, 0.0, 0.0],
  vento_modo: "nenhum",
  rajada: false,
  est: { roll: -0.0244, pitch: -0.0086, psi: 0.5542, h: 0.9649, vx: -0.0103, vy: -0.002, vz: 0.0235 },
  real: { x: 0.925, y: -1.059, z: 1.011, roll: 0.0008, pitch: -0.0028, yaw: 0.4183, vx: 0.011, vy: -0.002, vz: 0.032 },
  bateria: { soc: 0.997264, v: 24.668361, i: 8.859483, p: 218.548911, autonomia_min: 62.52, alerta: "" },
  voo: { ativo: true, teclas: { w: false, a: false, s: false, d: false, q: false, e: false }, v_ref: [0.0, 0.0, 0.0] },
  bola: {
    seguir: true, valido: true, estado: 0, erro_px: [-62.469, 4.251], raio_px: 6.457,
    erro_tan: [-0.34456, 0.02345], raio_tan: 0.03561, camara: [320, 240], fovy: 67.0, dist: 1.636,
    vel: 0.5, alvo_mundo: [2.147395, 0.027832, 1.007052],
  },
  controlador: { modo: "classico", estado: "pronto", motivo: null, segui_alvo: true, rumo: 0.554195, yaw_taxa: 0.0, yaw_alvo: null },
  motores: [0.435, 0.434, 0.556, 0.553],
}

/**
 * TODAS as verificações, contra um módulo dado (o real ou um mutante). Devolve a lista — quem chama
 * decide o que fazer com ela (contar, ou exigir que alguma falhe).
 */
async function verificar(m: Modulo): Promise<Resultado[]> {
  const r: Resultado[] = []
  const ok = (passou: boolean, nome: string) => {
    r.push({ nome, passou: passou === true })
  }

  // ------------------------------------------------------------------ 1. parser do HUD
  const hud = m.lerHud(AMOSTRA)
  ok(hud !== null && hud.t === 13.06 && hud.passo === 603 && hud.fase === "a_voar",
    "lerHud: amostra real → t, passo e fase")
  ok(hud?.est?.psi === 0.5542 && hud.est.h === 0.9649 && hud.real?.yaw === 0.4183,
    "lerHud: `est` (sensores) e `real` (simulador) lidos em separado")
  ok(hud?.bateria?.soc === 0.997264 && hud.bateria.autonomiaMin === 62.52 && hud.bateria.alerta === "",
    "lerHud: bateria (soc, autonomia_min → autonomiaMin, alerta)")
  ok(hud?.bola?.erroTan?.[0] === -0.34456 && hud.bola.fovy === 67 && hud.bola.camara?.[0] === 320,
    "lerHud: bloco bola (erro_tan, fovy, camara)")
  ok(hud?.controlador?.seguiAlvo === true && hud.controlador.rumo === 0.554195 && hud.controlador.modo === "classico",
    "lerHud: controlador (segui_alvo, rumo, modo)")
  ok(hud?.motores?.length === 4 && hud.voo?.ativo === true && hud.voo.vRef?.length === 3,
    "lerHud: motores ×4 e eco do voo")
  ok(hud?.fovy === null && m.lerHud({ ...AMOSTRA, fovy: 54.5 })?.fovy === 54.5,
    "lerHud: `fovy` de topo (publicado sempre) — ausente num runner antigo dá null")
  ok(m.resumirHud(m.lerHud({ ...AMOSTRA, fovy: 54.5, bola: null }), "ligado").fovy === 54.5 &&
      m.resumirHud(hud, "ligado").fovy === 67,
    "resumo: o fovy de topo vale sem modo bola; sem ele vale o de `bola.fovy`")
  const comBordo = m.lerHud({ ...AMOSTRA, vento_bordo: { acc: [0.02, 1.08], vel: 2.82, direcao: 87.0 } })
  ok(hud?.ventoBordo === null && comBordo?.ventoBordo?.vel === 2.82 && comBordo.ventoBordo.direcao === 87,
    "lerHud: `vento_bordo` (o vento que o drone sente) — ausente dá null")
  ok(m.textoVentoBordo(comBordo?.ventoBordo ?? null) === "≈ 2,8 m/s para 087°" &&
      m.textoVentoBordo({ vel: 0.41, direcao: 289 }) === "calmo" && m.textoVentoBordo(null) === "—" &&
      m.textoVentoBordo({ vel: 4.94, direcao: 359.7 }) === "≈ 4,9 m/s para 000°",
    "vento de bordo: texto com «≈», `calmo` abaixo do ruído do observador (0,6 m/s) e «—» sem estimativa")
  ok(m.lerHud({ ...AMOSTRA, vento_bordo: { vel: -1, direcao: 0 } })?.ventoBordo === null &&
      m.lerHud({ ...AMOSTRA, vento_bordo: "x" })?.ventoBordo === null,
    "vento de bordo: lixo (velocidade negativa, não-objeto) dá null")
  ok(m.lerHud(null) === null && m.lerHud("x") === null && m.lerHud([]) === null && m.lerHud({}) === null,
    "lerHud: o que não é amostra dá null (nunca lança)")
  ok(m.lerHud({ ...AMOSTRA, fase: "episodio_terminado" })?.fase === null,
    "lerHud: fase desconhecida fica null (não se adivinha «a voar»)")
  ok(m.lerHud({ ...AMOSTRA, est: { roll: 0, pitch: 0, psi: 0 } })?.est === null,
    "lerHud: estimador incompleto não conta como estimador")
  ok(m.lerHud({ ...AMOSTRA, bola: null })?.bola === null && m.lerHud({ t: 1 })?.bateria === null,
    "lerHud: blocos ausentes ficam null")
  ok(m.lerHud({ ...AMOSTRA, motores: [1.4, -0.2, "x", 0.5] })?.motores?.join() === "1,0,0,0.5",
    "lerHud: duty dos motores limitado a 0..1")
  ok(m.lerEventoHud(JSON.stringify(AMOSTRA))?.passo === 603 && m.lerEventoHud("{partido") === null && m.lerEventoHud("") === null,
    "lerEventoHud: JSON do SSE → amostra; lixo → null")
  const hj = m.lerHudJson({ hud: AMOSTRA, idade_s: 0.005, velho: false })
  ok(hj.hud?.passo === 603 && hj.idadeS === 0.005 && hj.velho === false && m.lerHudJson({ hud: null }).hud === null,
    "lerHudJson: amostra + idade do servidor")

  // ------------------------------------------------------------------ 2. instrumentos
  const ins = m.instrumentos(hud)
  ok(ins.fonte === "sensores" && ins.altitude === 0.9649 && ins.vVertical === 0.0235 && ins.roll === -0.0244,
    "instrumentos: com estimador mandam os SENSORES (h, vz, roll de `est`)")
  ok(aprox(ins.rumo ?? NaN, (0.5542 * 180) / Math.PI, 1e-9) && aprox(ins.vHorizontal ?? NaN, Math.hypot(0.0103, 0.002), 1e-12),
    "instrumentos: rumo em graus e velocidade horizontal = ‖(vx, vy)‖")
  const cf2 = m.instrumentos(m.lerHud({ t: 1, passo: 1, fase: "a_voar", real: { z: 1.02, yaw: -0.1 } }))
  ok(cf2.fonte === "simulador" && cf2.altitude === 1.02 && cf2.vHorizontal === null && cf2.roll === null,
    "instrumentos: sem estimador (cf2) usa `real` e o que falta fica null")
  ok(aprox(cf2.rumo ?? NaN, 360 - (0.1 * 180) / Math.PI, 1e-9), "instrumentos: rumo negativo reduz-se a [0, 360)")
  ok(m.instrumentos(null).fonte === null && m.instrumentos(null).altitude === null, "instrumentos: sem amostra é tudo null")
  ok(m.yawNoMundo(hud) === 0.4183 && m.rumoParaFixar(hud) === 0.554195,
    "yawNoMundo usa a verdade; rumoParaFixar usa o rumo do controlador")

  // ------------------------------------------------------------------ 3. estado em linguagem de voo
  ok(m.ligacaoHud({ idadeMs: 20, desdeArranqueMs: 5000 }) === "ligado", "ligação: amostra fresca = ligado")
  ok(m.ligacaoHud({ idadeMs: 1000, desdeArranqueMs: 5000 }) === "ligado" &&
    m.ligacaoHud({ idadeMs: 1001, desdeArranqueMs: 5000 }) === "sem_ligacao",
    "ligação: amostra com mais de 1 s = SEM LIGAÇÃO (o limite é 1000 ms)")
  ok(m.ligacaoHud({ idadeMs: null, desdeArranqueMs: 100 }) === "a_ligar" &&
    m.ligacaoHud({ idadeMs: null, desdeArranqueMs: 60_000 }) === "sem_ligacao",
    "ligação: no arranque espera-se; passado o prazo é SEM LIGAÇÃO")
  const fase = (f: string, extra: object = {}) => m.estadoDeVoo(m.lerHud({ ...AMOSTRA, fase: f, bola: null, controlador: { modo: "classico", segui_alvo: false }, ...extra }), "ligado")
  ok(fase("a_voar").texto === "A VOAR" && fase("a_voar").tom === "ativo" && fase("a_voar").textoModo === "MANUAL",
    "estado: a_voar → «A VOAR» + «MANUAL»")
  ok(fase("no_chao").texto === "NO CHÃO" && fase("caiu").texto === "CAIU" && fase("caiu").tom === "perigo",
    "estado: no_chao → «NO CHÃO», caiu → «CAIU» (perigo)")
  ok(fase("a_voar", { pausado: true }).texto === "EM PAUSA" && fase("caiu", { pausado: true }).texto === "CAIU",
    "estado: pausa diz-se; CAIU vence a pausa")
  ok(m.estadoDeVoo(hud, "ligado").textoModo === "A SEGUIR A BOLA" && m.estadoDeVoo(hud, "ligado").modo === "bola",
    "estado: com segui_alvo o modo é «A SEGUIR A BOLA»")
  const sem = m.estadoDeVoo(hud, "sem_ligacao")
  ok(sem.texto === "SEM LIGAÇÃO" && sem.modo === null && sem.tom === "atencao" && m.estadoDeVoo(null, "a_ligar").texto === "A LIGAR",
    "estado: sem ligação não se afirma fase nem modo")
  ok(!/epis[oó]dio/i.test(JSON.stringify(["a_voar", "no_chao", "caiu"].map((f) => fase(f)))),
    "estado: nunca aparece «episódio»")

  // ------------------------------------------------------------------ 4. seguidor da bola
  const bola = (extra: object) => m.lerHud({ ...AMOSTRA, bola: { ...AMOSTRA.bola, ...extra } })?.bola ?? null
  ok(m.estadoSeguidor(bola({})) === "a_seguir" && m.ROTULO_SEGUIDOR.a_seguir === "A SEGUIR", "seguidor: estado 0 com deteção = A SEGUIR")
  ok(m.estadoSeguidor(bola({ estado: 1 })) === "a_procura" && m.estadoSeguidor(bola({ estado: 3 })) === "a_procura" &&
    m.ROTULO_SEGUIDOR.a_procura === "À PROCURA",
    "seguidor: em falta (1) e reaquisição (3) = À PROCURA")
  ok(m.estadoSeguidor(bola({ estado: 2 })) === "perdida" && m.ROTULO_SEGUIDOR.perdida === "PERDIDA",
    "seguidor: estado 2 = PERDIDA mesmo com deteção válida (medido no arranque do modo)")
  ok(m.estadoSeguidor(bola({ valido: false })) === "a_procura" && m.estadoSeguidor(bola({ seguir: false })) === "desligado" &&
    m.estadoSeguidor(null) === "desligado",
    "seguidor: sem deteção não é «a seguir»; modo desligado = DESLIGADO")
  const erro = m.erroCentragem(bola({}))
  ok(erro !== null && aprox(erro.graus, (Math.atan(Math.hypot(0.34456, 0.02345)) * 180) / Math.PI, 1e-9) &&
    aprox(erro.px ?? NaN, Math.hypot(62.469, 4.251), 1e-9),
    "erro de centragem: ângulo ao eixo (19,05°) e píxeis do detetor (62,6 px)")
  ok(m.erroCentragem(bola({ valido: false })) === null && m.erroCentragem(null) === null, "erro de centragem: sem deteção não há erro")

  // ------------------------------------------------------------------ 5. projeção com object-fit: cover
  const IMG: [number, number] = [1920, 1080]
  ok(m.escalaCover(IMG, [1920, 1080]) === 1 && aprox(m.escalaCover(IMG, [1366, 768]), 1366 / 1920),
    "cover: 16:9 em 16:9 escala pela largura (=altura)")
  ok(aprox(m.escalaCover(IMG, [1024, 768]), 768 / 1080) && aprox(m.escalaCover(IMG, [2560, 1080]), 2560 / 1920),
    "cover: vista mais estreita escala pela ALTURA (corta os lados); mais larga pela LARGURA (corta cima/baixo)")
  const f1080 = m.focalNaVista(67, IMG, [1920, 1080])
  ok(aprox(f1080, 540 / Math.tan((33.5 * Math.PI) / 180), 1e-9), "focal: (H/2)/tan(fovy/2) = 815,8 px a 1080p")
  const p = m.projetarNaVista([-0.34456, 0.02345], f1080, [1920, 1080])
  ok(Math.abs(p.x - 679) < 1.5 && Math.abs(p.y - 560) < 1.5 && p.visivel,
    `retículo: cai sobre a bola MEDIDA no quadro real (679, 560) — deu (${p.x.toFixed(1)}, ${p.y.toFixed(1)})`)
  const p43 = m.projetarNaVista([-0.34456, 0.02345], m.focalNaVista(67, IMG, [1024, 768]), [1024, 768])
  ok(aprox(p43.x, 512 - 0.34456 * f1080 * (768 / 1080), 1e-6) && aprox(p43.y, 384 + 0.02345 * f1080 * (768 / 1080), 1e-6),
    "retículo: numa vista 4:3 a escala é a da ALTURA (com `contain` ficava a 75 % da distância certa)")
  const pLargo = m.projetarNaVista([0.5, 0], m.focalNaVista(67, IMG, [2560, 1080]), [2560, 1080])
  ok(aprox(pLargo.x, 1280 + 0.5 * f1080 * (2560 / 1920), 1e-6), "retículo: numa vista ultralarga a escala é a da LARGURA")
  const centro = m.projetarNaVista([0, 0], f1080, [1366, 768])
  ok(centro.x === 683 && centro.y === 384, "retículo: erro zero = centro exato da vista")
  ok(!m.projetarNaVista([2, 0], f1080, [1920, 1080]).visivel, "retículo: fora da vista diz-se (visivel = false)")
  const hz = m.horizonteNaVista(0, (10 * Math.PI) / 180, f1080)
  ok(aprox(hz.deslocamentoPx, -Math.tan((10 * Math.PI) / 180) * f1080, 1e-9) && hz.rotacaoGraus === 0,
    "horizonte: nariz 10° em BAIXO (pitch > 0) sobe a linha 143,9 px")
  ok(m.horizonteNaVista(0.2, 0, f1080).rotacaoGraus < 0 && m.horizonteNaVista(-0.2, 0, f1080).rotacaoGraus > 0,
    "horizonte: asa direita em baixo (roll > 0) roda a linha no sentido anti-horário")
  ok(Number.isFinite(m.horizonteNaVista(0, Math.PI / 2, f1080).deslocamentoPx), "horizonte: a pique não rebenta (tangente limitada)")
  ok(m.atrasoDaImagem(116, 50) === 126 && m.atrasoDaImagem(116, 12.5) === 156 && m.atrasoDaImagem(116, 1) === 216,
    "atraso da imagem: latência do módulo + meio período do stream (travado em 100 ms abaixo de 5 fps)")
  ok(m.atrasoDaImagem(null, null) === 0 && m.atrasoDaImagem(116, null) === 116 && m.atrasoDaImagem(NaN, 0) === 0,
    "atraso da imagem: o que o backend não publica não se inventa (0)")

  // ------------------------------------------------------------------ 6. vento
  ok(JSON.stringify(m.corpoVentoSimples({ intensidade: 7 })) === '{"intensidade":5}' &&
    JSON.stringify(m.corpoVentoSimples({ intensidade: -3 })) === '{"intensidade":0}',
    "vento: intensidade limitada a 0–5 m/s")
  ok(m.corpoVentoSimples({ intensidade: 2.34 })?.intensidade === 2.3 && m.corpoVentoSimples({ intensidade: 0.05 })?.intensidade === 0.1,
    "vento: intensidade no passo de 0,1 m/s")
  ok(m.corpoVentoSimples({ direcao: -90 })?.direcao === 270 && m.corpoVentoSimples({ direcao: 361.4 })?.direcao === 1 &&
    m.corpoVentoSimples({ direcao: 360 })?.direcao === 0,
    "vento: direção reduzida a [0, 360) ao grau")
  ok(m.corpoVentoSimples({ ligado: "sim", aleatorio: 1 }) === null && m.corpoVentoSimples({ intensidade: NaN }) === null &&
    m.corpoVentoSimples({}) === null,
    "vento: booleanos estritos e NaN ficam de fora; corpo vazio = nada para enviar")
  ok(JSON.stringify(m.corpoVentoSimples({ ligado: true, modo: "dryden", seq: 3 } as never)) === '{"ligado":true}',
    "vento: só as 4 chaves do contrato chegam ao corpo (o servidor recusa as outras)")
  ok(m.lerVentoSimples({ ligado: false, intensidade: 2, aleatorio: false, direcao: 0 })?.intensidade === 2 &&
    m.lerVentoSimples({ ligado: 1, intensidade: 2, aleatorio: false, direcao: 0 }) === null && m.lerVentoSimples(null) === null,
    "lerVentoSimples: bloco válido; malformado/ausente = null")
  const b0 = m.pontoBussola(0)
  const b90 = m.pontoBussola(90)
  ok(aprox(b0.sx, 0) && aprox(b0.sy, -1) && aprox(b90.sx, -1) && aprox(b90.sy, 0, 1e-12),
    "bússola: 0° (+x, frente) aponta para CIMA e 90° (+y) para a ESQUERDA")
  ok([0, 45, 90, 180, 270, 359].every((d) => {
    const pt = m.pontoBussola(d)
    return m.direcaoDePontoBussola(pt.sx * 50, pt.sy * 50) === d
  }), "bússola: arrastar para um ponto dá a direção desse ponto (ida e volta)")
  ok(m.direcaoDePontoBussola(1, 1) === null, "bússola: no centro a direção não está definida")
  const frente = m.ventoNoNariz([-2, 0, 0], 0)
  ok(frente.de === "frente" && aprox(frente.angulo ?? NaN, 180) && frente.vel === 2 && m.ROTULO_DE_ONDE.frente === "DE FRENTE",
    "vento no nariz: a soprar para −x com o nariz em +x é vento DE FRENTE (empurra para trás)")
  ok(m.ventoNoNariz([-2, 0, 0], Math.PI).de === "cauda" && m.ventoNoNariz([0, 2, 0], 0).de === "direita" &&
    aprox(m.ventoNoNariz([0, 2, 0], 0).angulo ?? NaN, 90) && m.ventoNoNariz([0, -2, 0], 0).de === "esquerda",
    "vento no nariz: roda com o yaw; a soprar para +y (esquerda) vem DA DIREITA")
  ok(m.ventoNoNariz([0.01, 0, 0], 0).angulo === null && m.ventoNoNariz(null, 0).vel === 0 && m.ventoNoNariz([3, 4, 0], null).vel === 5,
    "vento no nariz: calmo não tem direção; sem yaw fica só o módulo")

  // ------------------------------------------------------------------ 7. bola
  const cfg = m.lerBolaConfig({ velocidade: 0.5, min: 0.1, max: 0.8 })
  ok(cfg !== null && cfg.velocidade === 0.5 && m.lerBolaConfig({ velocidade: 0.5 }) === null && m.lerBolaConfig({ velocidade: 0.5, min: 1, max: 1 }) === null,
    "lerBolaConfig: precisa da faixa (sem min/max não há slider)")
  ok(cfg !== null && m.limitarVelocidadeBola(2, cfg) === 0.8 && m.limitarVelocidadeBola(0, cfg) === 0.1 &&
    m.limitarVelocidadeBola(0.33, cfg) === 0.35 && m.limitarVelocidadeBola(NaN, cfg) === 0.5,
    "bola: velocidade dentro de [min, max], no passo de 0,05; NaN mantém a atual")

  // ------------------------------------------------------------------ 8. mapa de teclas
  const a = (k: string, mods = {}) => JSON.stringify(m.acaoDaTecla(k, mods))
  ok(a("w") === '{"tipo":"voo","tecla":"w"}' && a("W") === a("w") && a("e") === '{"tipo":"voo","tecla":"e"}',
    "teclas: W/A/S/D/Q/E são de voo, com ou sem maiúscula")
  ok(a("z") === '{"tipo":"rodar","tecla":"z"}' && a("c") === '{"tipo":"rodar","tecla":"c"}' && a("x") === '{"tipo":"fixar_rumo"}',
    "teclas: Z/C rodam, X fixa o rumo")
  ok(a("b") === '{"tipo":"bola"}' && a("v") === '{"tipo":"vento"}' && a("f") === '{"tipo":"vista"}' && a("r") === '{"tipo":"reiniciar"}',
    "teclas: B bola · V vento · F vista · R reiniciar")
  ok(a("1") === '{"tipo":"janela","indice":0}' && a("8") === '{"tipo":"janela","indice":7}' && a("9") === "null" && a("0") === "null",
    "teclas: 1–8 abrem as janelas (9 e 0 não são do cockpit)")
  ok(a("Escape") === '{"tipo":"fechar"}' && a("?") === '{"tipo":"ajuda"}' && a("Enter") === "null" && a("g") === "null",
    "teclas: Esc fecha, ? abre a ajuda; o resto não é interceptado")
  ok(a(" ") === '{"tipo":"tiro"}' && a("Spacebar") === '{"tipo":"tiro"}' && a(" ", { ctrl: true }) === "null",
    "teclas: ESPAÇO dispara a Glock 25 (tipo: tiro), exceto com Ctrl/Meta/Alt")
  {
    const enviadosTiro: boolean[] = []
    const ct = new m.ControloTiro({ enviar: async (g) => { enviadosTiro.push(g) } })
    ct.premir()
    ct.premir() // auto-repeat ignorado
    ok(ct.obter().gatilho === true && ct.obter().disparos === 1 && enviadosTiro.join(",") === "true",
      "tiro: premir SPACE acende o gatilho e dispara 1× (auto-repeat não repete)")
    ct.largar()
    ct.largar()
    ok(ct.obter().gatilho === false && ct.obter().disparos === 1 && enviadosTiro.join(",") === "true,false",
      "tiro: largar SPACE solta o gatilho sem disparar outro tiro")
    const hudTiro = m.lerHud({
      ...AMOSTRA,
      tiro: {
        id: "glock_g25",
        tiros: 3,
        acertos_bola: 3,
        erros_bola: 0,
        auto_atirar: true,
        ultimo_tiro: { resultado: "acertou_bola" },
        mira: {
          no_alvo: true,
          vai_acertar_certeza: true,
          erro_bola_m: 0.011,
          raio_colisao_m: 0.0545,
          tempo_voo_ms: 6.4,
          distancia_bola_m: 1.9,
          ponto_impacto_tan: [-0.01, -0.078],
        },
        gatilho: true,
        em_recuo: true,
        fogo_cano_ativo: true,
        projetil_visivel: true,
        caminho_visivel: true,
        distancia_projetil_m: 18.4,
        tempo_caminho_s: 0.062,
        alcance_render_m: 50.0,
        duracao_caminho_s: 1.0,
        impulso_ns: 1.9162,
        delta_v_teorico_m_s: 0.6457,
        direcao_soco: [-1, 0, 0],
        azimute_soco_graus: 180,
      },
      carga: {
        massa_sem_carga_g: 2182.6,
        massa_total_g: 2967.6,
        carga_atual_g: 785.0,
        carga_max_voo_seguro_g: 1467.0,
        carga_max_descolagem_oge_g: 2745.0,
        carga_max_descolagem_ige_g: 3253.0,
        t_w_efetivo_oge: 1.66,
        t_w_efetivo_ige: 1.84,
        pode_alcar_voo: true,
        pode_pairar_oge: true,
        pode_voar_seguro: true,
        estado_voo: "voo_seguro",
        vento_max_m_s: 10.8,
      },
    })
    ok(
      hudTiro?.tiro?.id === "glock_g25" &&
        hudTiro.tiro.tiros === 3 &&
        hudTiro.tiro.acertosBola === 3 &&
        hudTiro.tiro.errosBola === 0 &&
        hudTiro.tiro.autoAtirar === true &&
        hudTiro.tiro.ultimoResultado === "acertou_bola" &&
        hudTiro.tiro.mira?.noAlvo === true &&
        hudTiro.tiro.mira.vaiAcertarCerteza === true &&
        hudTiro.tiro.mira.mensagem === "NO ALVO" &&
        aprox(hudTiro.tiro.mira.erroBolaM ?? 0, 0.011) &&
        aprox(hudTiro.tiro.mira.pontoImpactoTan?.[1] ?? 0, -0.078) &&
        hudTiro.tiro.gatilho &&
        hudTiro.tiro.emRecuo &&
        hudTiro.tiro.fogoCanoAtivo &&
        hudTiro.tiro.projetilVisivel &&
        hudTiro.tiro.caminhoVisivel &&
        aprox(hudTiro.tiro.distanciaProjetilM ?? 0, 18.4) &&
        aprox(hudTiro.tiro.alcanceRenderM ?? 0, 50.0) &&
        aprox(hudTiro.tiro.duracaoCaminhoS ?? 0, 1.0) &&
        aprox(hudTiro.tiro.impulsoNs ?? 0, 1.9162) &&
        hudTiro.carga?.podeAlcarVoo === true &&
        hudTiro.carga.estadoVoo === "voo_seguro" &&
        aprox(hudTiro.carga.cargaMaxDescolagemOgeG ?? 0, 2745.0),
      "lerHud: blocos `tiro` (mira balística NO ALVO, acertos na bola, fogo do cano, projétil 50 m, caminho 1 s) e `carga` lidos"
    )
    const bolaZero = m.lerBolaConfig({ velocidade: 0.0, min: 0.0, max: 0.8, auto_atirar: true })
    ok(
      bolaZero !== null && bolaZero.velocidade === 0.0 && bolaZero.min === 0.0 && bolaZero.autoAtirar === true,
      "lerBolaConfig: aceita velocidade 0,0 m/s (bola parada) e `auto_atirar: true`"
    )
    const hudGraf = m.lerHud({
      ...AMOSTRA,
      graficos: {
        sombras: false,
        reflexos: false,
        nevoeiro: true,
        mostrar_helices: true,
        mostrar_efeitos: true,
        mostrar_fios_detalhes: false,
        escala_resolucao: 0.5,
        qualidade_jpeg: 65,
        fps_atual: 59.8,
        fps_simulacao: 59.8,
        fps_fpv: 49.9,
        fps_fisica: 50.0,
        ms_render_sim: 1.8,
        ms_render_fpv: 1.4,
      },
    })
    ok(
      hudGraf?.graficos !== null &&
        hudGraf?.graficos.sombras === false &&
        hudGraf.graficos.reflexos === false &&
        hudGraf.graficos.nevoeiro === true &&
        hudGraf.graficos.mostrarFiosDetalhes === false &&
        aprox(hudGraf.graficos.escalaResolucao, 0.5) &&
        hudGraf.graficos.qualidadeJpeg === 65 &&
        aprox(hudGraf.graficos.fpsAtual ?? 0, 59.8) &&
        aprox(hudGraf.graficos.fpsSimulacao ?? 0, 59.8),
      "lerHud: bloco `graficos` (otimização gráfica do MuJoCo e FPS atual) lido"
    )
    const hudPecas = m.lerHud({
      ...AMOSTRA,
      pecas: {
        motor_id: "tmotor_mn5006_kv450",
        motor_modelo: "T-Motor Antigravity MN5006 KV450",
        motor_kv: 450,
        motor_massa_g: 126,
        motor_cor_nome: "Azul Cobalto",
        motor_cor_hex: "#2470eb",
        bateria_id: "lipo_6s1p_4500_alta_vazao",
        bateria_wh: 99.9,
        bateria_cor_nome: "Amarelo Ouro",
        bateria_cor_hex: "#ebb814",
        vazao_atual_a: 18.4,
        vazao_max_a: 225.0,
        vazao_pct: 8.2,
        watts_total: 412.5,
        watts_motores: 406.0,
        pode_alcar_voo: true,
        estado_voo: "voo_seguro",
      },
    })
    ok(
      hudPecas?.pecas !== null &&
        hudPecas?.pecas.motorId === "tmotor_mn5006_kv450" &&
        hudPecas.pecas.motorKv === 450 &&
        hudPecas.pecas.motorCorHex === "#2470eb" &&
        hudPecas.pecas.bateriaId === "lipo_6s1p_4500_alta_vazao" &&
        aprox(hudPecas.pecas.vazaoMaxA ?? 0, 225.0) &&
        aprox(hudPecas.pecas.wattsTotal ?? 0, 412.5) &&
        hudPecas.pecas.podeAlcarVoo === true,
      "lerHud: bloco `pecas` (troca de motor/bateria, cores 3D, vazão A e Watts gastos) lido"
    )
  }
  ok(a("w", { ctrl: true }) === "null" && a("r", { meta: true }) === "null" && a("f", { alt: true }) === "null",
    "teclas: com Ctrl/Meta/Alt nunca se rouba o atalho do browser")
  ok(m.eCampoDeTexto({ tagName: "INPUT", type: "text" }) && m.eCampoDeTexto({ tagName: "INPUT", type: null }) &&
    m.eCampoDeTexto({ tagName: "TEXTAREA" }) && m.eCampoDeTexto({ tagName: "DIV", isContentEditable: true }),
    "foco: input de texto, textarea e contenteditable largam o teclado de voo")
  ok(!m.eCampoDeTexto({ tagName: "INPUT", type: "range" }) && !m.eCampoDeTexto({ tagName: "BUTTON" }) &&
    !m.eCampoDeTexto({ tagName: "INPUT", type: "checkbox" }) && !m.eCampoDeTexto(null),
    "foco: slider, botão e checkbox NÃO largam (arrastar o vento não pode desligar o W)")

  // ------------------------------------------------------------------ 9. estado do piloto → corpo do POST
  let pl = m.premirTecla(m.PILOTO_INICIAL, "w")
  let corpo = m.corpoVooDoPiloto(pl)
  ok(corpo.ativo === true && corpo.teclas.w === true && corpo.teclas.a === false && Object.keys(corpo.teclas).length === 6,
    "corpo: W premido → `ativo: true` e as 6 teclas presentes, só `w` a true")
  corpo = m.corpoVooDoPiloto(m.largarTecla(pl, "w"))
  ok(corpo.ativo === true && Object.values(corpo.teclas).every((v) => v === false) && corpo.yaw_taxa === 0,
    "corpo: largar manda tudo a false (e continua `ativo: true` — não há desarmar)")
  ok(m.premirTecla(pl, "w") === pl, "tecla repetida (auto-repeat) não muda o estado")
  ok(m.taxaGuinada(m.premirTecla(m.PILOTO_INICIAL, "z")) === 0.5 && m.taxaGuinada(m.premirTecla(m.PILOTO_INICIAL, "c")) === -0.5,
    "yaw: Z = +0,5 rad/s (esquerda, ψ cresce — medido), C = −0,5")
  ok(m.taxaGuinada(m.premirTecla(m.premirTecla(m.PILOTO_INICIAL, "z"), "c")) === 0 &&
    m.taxaGuinada(m.largarTecla(m.premirTecla(m.premirTecla(m.PILOTO_INICIAL, "z"), "c"), "z")) === -0.5,
    "yaw: Z+C anulam-se; largar uma volta a rodar para o lado da outra")
  pl = m.fixarRumo(m.PILOTO_INICIAL, 1.2)
  ok(pl.yaw_alvo === 1.2 && m.corpoVooDoPiloto(pl).yaw_alvo === 1.2 && m.fixarRumo(m.PILOTO_INICIAL, null) === m.PILOTO_INICIAL,
    "yaw: X fixa o rumo dado; sem rumo conhecido o estado não muda")
  ok(m.premirTecla(pl, "z").yaw_alvo === null && m.soltarRumo(pl).yaw_alvo === null,
    "yaw: Z/C soltam o rumo fixado (volta-se ao modo taxa)")
  const cheio = m.definirSeguirBola(m.fixarRumo(m.premirTecla(m.premirTecla(m.PILOTO_INICIAL, "w"), "z"), 0.3), true)
  const solto = m.soltarTeclas(cheio)
  ok(!m.temTeclasPremidas(solto) && solto.yaw_alvo === 0.3 && solto.segui_alvo === true && m.taxaGuinada(solto) === 0,
    "blur: solta TODAS as teclas (movimento e rodar) mas mantém os modos")
  const diag = m.velocidadeNoNariz(m.premirTecla(m.premirTecla(m.PILOTO_INICIAL, "w"), "a"))
  ok(aprox(Math.hypot(diag[0], diag[1]), 1, 1e-12) && diag[0] > 0 && diag[1] > 0, "velocidade: a diagonal W+A fica a 1,0 m/s")
  const mundo = m.velocidadeNoMundo(m.premirTecla(m.PILOTO_INICIAL, "w"), Math.PI / 2)
  ok(aprox(mundo[0], 0, 1e-12) && aprox(mundo[1], 1, 1e-12), "velocidade: W com o nariz a 90° é +y no mundo (relativo ao nariz)")

  // ------------------------------------------------------------------ 10. ControloPiloto (teclado → POST)
  {
    const tempo = tempoFalso()
    const rede = envioFalso<CorpoVoo, null>(() => null)
    const piloto = new m.ControloPiloto({ enviar: rede.enviar, ...tempo })
    let avisos = 0
    piloto.subscrever(() => { avisos += 1 })
    piloto.premir("w")
    ok(rede.enviados.length === 1 && rede.enviados[0].ativo === true && rede.enviados[0].teclas.w === true && piloto.obter().teclas.w,
      "piloto: W logo após abrir (sem clicar em nada) envia `ativo: true` + `teclas.w: true`")
    piloto.premir("w")
    ok(rede.enviados.length === 1 && avisos === 1, "piloto: o auto-repeat da tecla não envia nem re-desenha")
    piloto.premir("a")
    piloto.largar("a")
    piloto.largar("w")
    ok(rede.enviados.length === 1, "piloto: com um POST em voo os estados seguintes esperam (nunca dois em voo)")
    await rede.responder()
    ok(rede.enviados.length === 2 && Object.values(rede.enviados[1].teclas).every((v) => v === false),
      "piloto: «o último vence» — os intermédios saltam-se e sai o estado final (tudo a false)")
    await rede.responder()
    ok(rede.maxEmVoo === 1, "piloto: nunca houve dois POSTs em voo")
    piloto.premir("z")
    await rede.responder()
    ok(rede.enviados[2].yaw_taxa === 0.5 && rede.enviados[2].yaw_alvo === null, "piloto: Z manda yaw_taxa +0,5")
    piloto.premir("q")
    await rede.responder()
    piloto.soltarTudo()
    await rede.responder()
    const ultimo = rede.enviados[rede.enviados.length - 1]
    ok(ultimo.yaw_taxa === 0 && Object.values(ultimo.teclas).every((v) => v === false) && ultimo.ativo === true,
      "piloto: perder o foco manda tudo solto (incluindo o rodar)")
    const antes = rede.enviados.length
    piloto.soltarTudo()
    ok(rede.enviados.length === antes, "piloto: soltar sem teclas premidas não envia nada")
    ok(piloto.fixarRumo(null) === false && rede.enviados.length === antes, "piloto: X sem rumo conhecido não envia")
    ok(piloto.alternarBola() === true && rede.enviados[rede.enviados.length - 1].segui_alvo === true, "piloto: B liga `segui_alvo`")
    await rede.responder()
    // adoção do servidor
    piloto.adotarServidor({ ativo: true, yaw_alvo: null, segui_alvo: false })
    ok(piloto.obter().segui_alvo === true, "piloto: dentro da carência o retrato (velho) do servidor não desfaz o B")
    tempo.avancar(m.CARENCIA_ADOCAO_MS + 1)
    piloto.adotarServidor({ ativo: true, yaw_alvo: 0.7, segui_alvo: false })
    ok(piloto.obter().segui_alvo === false && piloto.obter().yaw_alvo === 0.7, "piloto: passada a carência adota os MODOS do servidor")
    const n = rede.enviados.length
    piloto.adotarServidor({ ativo: true, yaw_alvo: 0.7, segui_alvo: false })
    ok(rede.enviados.length === n, "piloto: adotar não gera envio")
    piloto.adotarServidor({ ativo: false, yaw_alvo: 0.7, segui_alvo: false })
    ok(rede.enviados.length === n + 1 && rede.enviados[n].ativo === true, "piloto: se o servidor diz `ativo: false`, o cockpit volta a armar")
    await rede.responder()
  }

  // ------------------------------------------------------------------ 11. Emissor (intervalo + envio final)
  {
    const tempo = tempoFalso()
    const rede = envioFalso<number, null>(() => null)
    const em = new m.Emissor<number, null>({ enviar: rede.enviar, intervaloMs: 100, ...tempo })
    em.pedir(1)
    await rede.responder()
    for (const v of [2, 3, 4, 5]) { tempo.avancar(10); em.pedir(v) }
    ok(rede.enviados.join() === "1", "emissor: dentro do intervalo não sai mais nenhum (≤ 10 Hz)")
    tempo.avancar(60)
    ok(rede.enviados.join() === "1,5", "emissor: ao fim do intervalo sai SÓ o mais recente")
    await rede.responder()
    em.pedir(6)
    em.largar(7)
    ok(rede.enviados.join() === "1,5,7", "emissor: `largar` é o envio final — sai já, sem esperar o intervalo")
    await rede.responder()
    em.largar()
    ok(rede.enviados.length === 3 && !em.ocupado, "emissor: `largar` sem nada pendente não reenvia")
    em.pedir(8)
    tempo.avancar(200)
    em.pedir(9)
    await rede.responder(true)
    ok(rede.enviados.join() === "1,5,7,8" , "emissor: um POST em voo segura o seguinte")
    tempo.avancar(200)
    ok(rede.enviados.join() === "1,5,7,8,9", "emissor: uma falha não trava a fila")
    await rede.responder()
    ok(rede.maxEmVoo === 1, "emissor: nunca dois POSTs em voo")
    const falhas: unknown[] = []
    const em2 = new m.Emissor<Record<string, number>, null>({
      enviar: () => Promise.reject(new Error("x")), fundir: (x, y) => ({ ...x, ...y }), aoFalhar: (e) => falhas.push(e), ...tempo,
    })
    em2.largar({ a: 1 })
    await assentar()
    ok(falhas.length === 1, "emissor: a falha chega a `aoFalhar`")
    const rede3 = envioFalso<Record<string, number>, null>(() => null)
    const em3 = new m.Emissor<Record<string, number>, null>({ enviar: rede3.enviar, fundir: (x, y) => ({ ...x, ...y }), ...tempo })
    em3.largar({ a: 1 })
    em3.largar({ b: 2 })
    em3.largar({ a: 3 })
    await rede3.responder()
    ok(JSON.stringify(rede3.enviados) === '[{"a":1},{"b":2,"a":3}]', "emissor: corpos parciais FUNDEM-SE enquanto esperam")
    await rede3.responder()
    // `igual`: largar o valor que o servidor acabou de confirmar não reenvia; depois de uma falha, sim.
    const rede4 = envioFalso<number, null>(() => null)
    const em4 = new m.Emissor<number, null>({ enviar: rede4.enviar, igual: (x, y) => x === y, ...tempo })
    em4.largar(5)
    await rede4.responder()
    em4.largar(5)
    ok(rede4.enviados.join() === "5", "emissor: largar o valor já confirmado não gera um POST repetido")
    em4.largar(6)
    await rede4.responder(true)
    em4.largar(6)
    ok(rede4.enviados.join() === "5,6,6", "emissor: depois de uma FALHA o mesmo valor volta a sair")
    await rede4.responder()
  }

  // ------------------------------------------------------------------ 12. ControloVento / ControloBola
  {
    const tempo = tempoFalso()
    // Servidor falso com MEMÓRIA, como o real: cada POST parcial funde-se no bloco guardado.
    let noServidor: real.VentoSimples = { ligado: false, intensidade: 3, aleatorio: true, direcao: 90 }
    const rede = envioFalso<Partial<real.VentoSimples>, real.VentoSimples | null>((c) => (noServidor = { ...noServidor, ...c }))
    let erros = 0
    const vento = new m.ControloVento({ enviar: rede.enviar, aoFalhar: () => { erros += 1 }, ...tempo })
    ok(vento.obter().conhecido === false && vento.obter().ligado === false, "vento: antes do servidor mostra o padrão (desligado)")
    vento.adotarServidor({ ...noServidor })
    ok(vento.obter().conhecido && vento.obter().intensidade === 3 && vento.obter().direcao === 90, "vento: adota o bloco do /api/state")
    ok(vento.alternar() === true && JSON.stringify(rede.enviados[0]) === '{"ligado":true}' && vento.obter().ligado,
      "vento: V liga e manda SÓ `{ligado: true}`")
    await rede.responder()
    vento.ajustar({ intensidade: 9 }, false)
    ok(vento.obter().intensidade === 5, "vento: o painel nunca mostra mais do que o teto (5 m/s)")
    for (const v of [4.8, 4.6, 4.4]) { tempo.avancar(10); vento.ajustar({ intensidade: v }, false) }
    ok(rede.enviados.length === 1, "vento: a arrastar não sai mais de um POST por 100 ms")
    vento.ajustar({ intensidade: 4.2 }, true)
    ok(rede.enviados.length === 2 && rede.enviados[1].intensidade === 4.2, "vento: ao largar sai o valor final")
    vento.adotarServidor({ ligado: false, intensidade: 1, aleatorio: false, direcao: 0 })
    ok(vento.obter().intensidade === 4.2 && vento.obter().ligado, "vento: com envio a caminho o servidor não sobrepõe o gesto")
    await rede.responder()
    ok(vento.obter().intensidade === 4.2 && vento.obter().ligado && vento.obter().aleatorio && vento.obter().direcao === 90,
      "vento: a resposta do POST (o bloco confirmado) é adotada quando já não há nada a caminho")
    vento.ajustar({ aleatorio: false }, true)
    ok(vento.obter().aleatorio === false, "vento: o interruptor muda no instante (otimista)")
    await rede.responder(true)
    // O último que o servidor disse foi a resposta do POST anterior, não o retrato de 1 Hz que chegou
    // a meio do envio.
    ok(erros === 1 && vento.obter().aleatorio === true && vento.obter().intensidade === 4.2,
      "vento: um POST recusado avisa e o painel volta ao ÚLTIMO que o servidor confirmou")
    const n = rede.enviados.length
    vento.ajustar({ intensidade: "forte" }, true)
    ok(rede.enviados.length === n, "vento: alteração inválida não se envia")

    const redeB = envioFalso<number, number | null>((v) => v)
    const bola = new m.ControloBola({ enviar: redeB.enviar, ...tempo })
    bola.ajustar(0.4, true)
    ok(redeB.enviados.length === 0 && bola.obter() === null, "bola: sem a faixa do servidor não há slider nem envio")
    bola.adotarServidor({ velocidade: 0.5, min: 0.1, max: 0.8 })
    bola.ajustar(3, true)
    ok(redeB.enviados.join() === "0.8" && bola.obter()?.velocidade === 0.8, "bola: POST /api/bola com a velocidade limitada à faixa")
    await redeB.responder()
    bola.ajustar(0.3, false)
    tempo.avancar(10)
    bola.ajustar(0.2, false)
    tempo.avancar(200)
    ok(redeB.enviados.join() === "0.8,0.2", "bola: a arrastar sai só o valor mais recente")
    await redeB.responder()
  }

  // ------------------------------------------------------------------ 13. janelas
  let j = m.JANELAS_FECHADAS
  ok(m.janelaEmFoco(j) === null && m.JANELAS.length === 8 && m.JANELAS.map((x) => x.tecla).join("") === "12345678",
    "janelas: 8 janelas com os atalhos 1–8; tudo fechado por omissão")
  ok(m.JANELAS.filter((x) => x.principal).map((x) => x.id).join() === "voo,bola,vento", "janelas: as principais são Voo, Bola e Vento")
  j = m.alternarJanela(j, "voo")
  j = m.alternarJanela(j, "vento")
  ok(j.abertas.join() === "voo,vento" && m.janelaEmFoco(j) === "vento", "janelas: abrir põe à frente (a última é a do foco)")
  j = m.focarJanela(j, "voo")
  ok(j.abertas.join() === "vento,voo" && m.focarJanela(j, "voo") === j, "janelas: focar traz para a frente; focar a da frente não muda nada")
  ok(m.alternarJanela(j, "vento").abertas.join() === "voo", "janelas: alternar uma aberta fecha-a (mesmo sem estar à frente)")
  ok(m.fecharEmFoco(j).abertas.join() === "vento" && m.fecharEmFoco(m.JANELAS_FECHADAS) === m.JANELAS_FECHADAS,
    "janelas: Esc fecha a da frente; sem janelas não faz nada")
  j = m.moverJanela(j, "voo", { x: 40, y: 50 })
  ok(j.posicoes.voo?.x === 40 && m.fecharJanela(j, "voo").posicoes.voo?.y === 50, "janelas: a posição guarda-se e sobrevive a fechar")
  const VP = { largura: 1366, altura: 768 }
  const T = { largura: 300, altura: 400 }
  ok(JSON.stringify(m.encaixar({ x: 100, y: 100 }, T, VP)) === '{"x":100,"y":100}', "encaixar: dentro do viewport não mexe")
  ok(JSON.stringify(m.encaixar({ x: 5000, y: 5000 }, T, VP)) === `{"x":${1366 - 300 - 8},"y":${768 - 400 - 8}}`,
    "encaixar: para lá da direita/baixo encosta à margem")
  ok(JSON.stringify(m.encaixar({ x: -50, y: -50 }, T, VP)) === '{"x":8,"y":8}', "encaixar: para lá da esquerda/cima encosta à margem")
  ok(JSON.stringify(m.encaixar({ x: 300, y: 300 }, { largura: 2000, altura: 2000 }, VP)) === '{"x":8,"y":8}',
    "encaixar: janela maior do que o viewport mantém a barra de título visível")
  for (const vp of [{ largura: 1920, altura: 1080 }, { largura: 1366, altura: 768 }, { largura: 1280, altura: 720 }]) {
    const caixas = (["voo", "bola", "vento"] as const).map((id) => {
      const meta = m.metaJanela(id)
      const pos = m.posicaoInicial(id, vp)
      return { id, x0: pos.x, y0: pos.y, x1: pos.x + meta.largura, y1: pos.y + Math.min(meta.alturaPrevista, vp.altura) }
    })
    ok(caixas.every((c) => c.x0 >= 0 && c.y0 >= 0 && c.x1 <= vp.largura && c.y1 <= vp.altura),
      `janelas: Voo, Bola e Vento abrem DENTRO do viewport a ${vp.largura}×${vp.altura}`)
    type Caixa = { x0: number; y0: number; x1: number; y1: number }
    const sobrepoe = (p: Caixa, q: Caixa) => p.x0 < q.x1 && q.x0 < p.x1 && p.y0 < q.y1 && q.y0 < p.y1
    const [voo, bola, vento] = caixas
    ok(!sobrepoe(voo, bola) && !sobrepoe(bola, vento),
      `janelas: a Bola não se sobrepõe ao Voo nem ao Vento ao abrir a ${vp.largura}×${vp.altura}`)
    // Voo + Vento só cabem empilhados com altura para os dois; senão o Vento abre em CASCATA sobre o Voo,
    // com a barra de título do Voo (40 px) inteira à vista por cima — nunca tapado de todo.
    const empilhados = !sobrepoe(voo, vento)
    const cascata = vento.x0 === voo.x0 + m.CASCATA_JANELAS.x && vento.y0 === voo.y0 + m.CASCATA_JANELAS.y && m.CASCATA_JANELAS.y >= 40
    ok(vp.altura >= 1080 ? empilhados : cascata,
      `janelas: Voo e Vento ${vp.altura >= 1080 ? "empilhados" : "em cascata (barra do Voo à vista)"} a ${vp.largura}×${vp.altura}`)
    const zonas = m.zonasInstrumentos(vp)
    const tapadas = zonas.filter((z) => caixas.some((c) => sobrepoe(c, z))).map((z) => z.id)
    ok(zonas.length === 3 && tapadas.length === 0,
      `janelas: nenhuma das três tapa a velocidade, a altitude ou a mira do HUD a ${vp.largura}×${vp.altura} (tapadas: ${tapadas.join(",") || "nenhuma"})`)
  }
  ok(m.flancoHud(1280) === 333 && m.flancoHud(1920) === 499 && m.flancoHud(800) === 332 && m.flancoHud(4000) === 520,
    "HUD: o flanco das leituras escala com a largura, entre 332 e 520 px")
  const guardado = m.serializarJanelas(j)
  const lido = m.lerJanelas(guardado)
  ok(lido.abertas.join() === j.abertas.join() && lido.posicoes.voo?.x === 40, "janelas: guardar e ler (localStorage) é ida e volta")
  ok(m.lerJanelas(null) === m.JANELAS_FECHADAS && m.lerJanelas("{partido").abertas.length === 0 && m.lerJanelas("[1,2]").abertas.length === 0,
    "janelas: nada guardado / JSON partido = tudo fechado (não rebenta)")
  const sujo = m.lerJanelas(JSON.stringify({ abertas: ["voo", "controlador", "voo", 7, "bola"], posicoes: { voo: { x: "a", y: 2 }, bola: { x: 1, y: 2 }, xpto: { x: 1, y: 1 } } }))
  ok(sujo.abertas.join() === "voo,bola" && sujo.posicoes.voo === undefined && sujo.posicoes.bola?.x === 1 && Object.keys(sujo.posicoes).length === 1,
    "janelas: ids desconhecidos, repetidos e posições sem números caem fora")
  const ctx = { energiaDetalhe: false, rl: false }
  ok(!m.precisaDeSim([], ctx) && !m.precisaDeSim(["voo", "bola", "vento", "ajuda", "energia", "sistema"], ctx),
    "sondagem: com tudo fechado — ou só Voo/Bola/Vento/Ajuda/Energia compacta/Sistema clássico — NÃO se sonda o /api/sim")
  ok(m.precisaDeSim(["instrumentos"], ctx) && m.precisaDeSim(["voo", "graficos"], ctx), "sondagem: Sensores e Gráficos precisam do /api/sim")
  ok(m.precisaDeSim(["energia"], { energiaDetalhe: true, rl: false }) && m.precisaDeSim(["sistema"], { energiaDetalhe: false, rl: true }) &&
    !m.precisaDeSim(["voo"], { energiaDetalhe: true, rl: true }),
    "sondagem: Energia só com o detalhe aberto; Sistema só com a política RL a voar")

  // ------------------------------------------------------------------ 14. câmara em 3.ª pessoa
  const o0 = { azimute: 90, elevacao: -45 }
  ok(m.orbitarPorArrasto(o0, 108, 0, 1080).azimute === 72 && m.orbitarPorArrasto(o0, -108, 0, 1080).azimute === 108,
    "orbitar: arrastar para a direita DIMINUI o azimute (a cena segue o dedo, como o rato do MuJoCo)")
  ok(m.orbitarPorArrasto(o0, 0, 108, 1080).elevacao === -63 && m.orbitarPorArrasto(o0, 0, -108, 1080).elevacao === -27,
    "orbitar: arrastar para baixo DIMINUI a elevação (a câmara sobe)")
  ok(m.orbitarPorArrasto(o0, 0, 9999, 1080).elevacao === -89 && m.orbitarPorArrasto(o0, 0, -9999, 1080).elevacao === 30 &&
    m.orbitarPorArrasto({ azimute: 10, elevacao: 0 }, 108, 0, 1080).azimute === 352,
    "orbitar: elevação limitada a [−89°, 30°] e azimute reduzido a [0, 360)")
  ok(m.distanciaPorRoda(5, -100, [0.6, 15]) < 5 && m.distanciaPorRoda(5, 100, [0.6, 15]) > 5 &&
    m.distanciaPorRoda(5, 99999, [0.6, 15]) <= 15 && m.distanciaPorRoda(0.7, -99999, [0.6, 15]) === 0.6,
    "roda: para a frente aproxima, para trás afasta, sempre dentro dos limites da planta")

  // ------------------------------------------------------------------ 15. texto dos instrumentos
  ok(m.fmtHud(1.25, 2) === "1,25" && m.fmtHud(null) === "—" && m.fmtHud(NaN) === "—" && m.fmtHud(-0.04, 1) === "0,0" && m.fmtHud(-1.5, 1) === "−1,5",
    "fmtHud: vírgula decimal, «—» sem valor, zero sem sinal e menos tipográfico")
  ok(m.fmtRumo(7.4) === "007" && m.fmtRumo(359.6) === "000" && m.fmtRumo(-10) === "350" && m.fmtRumo(null) === "—",
    "fmtRumo: três algarismos, 360 = 000")
  ok(m.fmtAutonomia(62.4) === "62 min" && m.fmtAutonomia(125) === "2 h 05" && m.fmtAutonomia(null) === "—", "fmtAutonomia: minutos / horas")
  ok(m.ATALHOS.some((x) => x.teclas.includes("B")) && m.ATALHOS.some((x) => x.teclas.includes("Esc")) && m.ATALHOS.length >= 10,
    "ajuda: a lista de atalhos cobre o contrato §0.3")

  // ------------------------------------------------------------------ 16. resumo lento (o que entra no React)
  const res = m.resumirHud(hud, "ligado")
  ok(res.estado === "a_voar" && res.modo === "bola" && res.seguidor === "a_seguir" && res.temBola && res.temBateria && res.controlador === "classico",
    "resumo: estado, modo, seguidor e o que existe (bola, bateria, estimador)")
  ok(m.resumoIgual(res, m.resumirHud(m.lerHud({ ...AMOSTRA, t: 99, passo: 9999, est: { ...AMOSTRA.est, h: 3 } }), "ligado")),
    "resumo: NÃO muda com o que mexe a 50 Hz (t, passo, altitude) — o React não re-renderiza por amostra")
  ok(!m.resumoIgual(res, m.resumirHud(m.lerHud({ ...AMOSTRA, fase: "caiu" }), "ligado")) &&
    m.resumirHud(m.lerHud({ ...AMOSTRA, bateria: { ...AMOSTRA.bateria, alerta: "tensao_baixa" } }), "ligado").bateria === "fraca" &&
    m.resumirHud(m.lerHud({ ...AMOSTRA, bateria: { ...AMOSTRA.bateria, alerta: "critica" } }), "ligado").bateria === "critica",
    "resumo: muda com a fase e com o alerta de bateria")
  ok(m.resumirHud(hud, "sem_ligacao").seguidor === "desligado" && m.resumirHud(hud, "sem_ligacao").bateria === "nenhum",
    "resumo: sem ligação não se afirma seguidor nem alerta (a amostra é velha)")
  ok(res.aceitaComandos === true && m.resumirHud(m.lerHud({ ...AMOSTRA, voo: null }), "ligado").aceitaComandos === false &&
    m.resumirHud(null, "a_ligar").aceitaComandos === true,
    "resumo: uma amostra viva SEM bloco `voo` = a política não obedece às teclas (diz-se; sem amostra não se afirma)")

  return r
}

// ====================================================================== o módulo real
const base = await verificar(real)
const falhadas = base.filter((x) => !x.passou)
for (const f of falhadas) console.error(`✗ ${f.nome}`)

// ====================================================================== mutações
/**
 * Cada mutante troca UMA linha do `cockpit.ts` (o texto de `de` tem de existir exatamente uma vez —
 * se o código mudar e a mutação deixar de se aplicar, o teste falha alto em vez de passar às cegas).
 */
const MUTACOES: { nome: string; de: string; para: string }[] = [
  {
    nome: "cover trocado por contain (Math.max → Math.min)",
    de: "return Math.max(vista[0] / imagem[0], vista[1] / imagem[1])",
    para: "return Math.min(vista[0] / imagem[0], vista[1] / imagem[1])",
  },
  {
    nome: "o corpo do voo deixa de ir armado (ativo: true → false)",
    de: "    ativo: true,\n    teclas: { ...piloto.teclas },",
    para: "    ativo: false,\n    teclas: { ...piloto.teclas },",
  },
  {
    nome: "Z e C trocados (sinal da taxa de guinada)",
    de: "return (piloto.z ? YAW_TAXA_TECLA : 0) - (piloto.c ? YAW_TAXA_TECLA : 0)",
    para: "return (piloto.c ? YAW_TAXA_TECLA : 0) - (piloto.z ? YAW_TAXA_TECLA : 0)",
  },
  {
    nome: "o horizonte desce quando o nariz desce (sinal do pitch)",
    de: "deslocamentoPx: -Math.tan(p) * focal,",
    para: "deslocamentoPx: Math.tan(p) * focal,",
  },
  {
    nome: "a amostra velha passa por viva (limite de 1 s → 100 s)",
    de: "export const IDADE_MAX_HUD_MS = 1000",
    para: "export const IDADE_MAX_HUD_MS = 100000",
  },
  {
    nome: "a janela Voo passa a obrigar a sondar o /api/sim",
    de: '      id === "instrumentos" ||\n      id === "graficos" ||',
    para: '      id === "instrumentos" ||\n      id === "voo" ||\n      id === "graficos" ||',
  },
  {
    nome: "a intensidade do vento deixa de ter teto",
    de: "limitar(Math.round(intensidade / passo) * passo, min, max).toFixed(1)",
    para: "(Math.round(intensidade / passo) * passo).toFixed(1)",
  },
  {
    nome: "o emissor deixa de esperar pelo POST em voo",
    de: "    if (this.emEnvio || this.pendente === null) return\n    const espera",
    para: "    if (this.pendente === null) return\n    const espera",
  },
  {
    nome: "as janelas deixam de encaixar no viewport",
    de: "    x: Math.round(limitar(ponto.x, margem, maxX)),",
    para: "    x: Math.round(ponto.x),",
  },
  {
    nome: "a tecla ESPAÇO deixa de disparar o tiro",
    de: '  if (key === " " || key === "Spacebar") return { tipo: "tiro" }',
    para: '  if (key === "Spacebar") return { tipo: "tiro" }',
  },
]

const fonte = readFileSync(new URL("../src/lib/cockpit.ts", import.meta.url), "utf8")
const pastaLib = new URL("../src/lib/", import.meta.url)
const pasta = mkdtempSync(join(tmpdir(), "cockpit-mutantes-"))
let apanhadas = 0
const naoApanhadas: string[] = []
try {
  for (const [i, mutacao] of MUTACOES.entries()) {
    const ocorrencias = fonte.split(mutacao.de).length - 1
    if (ocorrencias !== 1) {
      naoApanhadas.push(`${mutacao.nome} — o alvo aparece ${ocorrencias}× no cockpit.ts (a mutação já não se aplica)`)
      continue
    }
    // A cópia vive fora de `src/lib/`: os imports relativos passam a apontar para os ficheiros reais.
    const mutante = fonte
      .replace(mutacao.de, mutacao.para)
      .replace(/from "\.\/([a-z-]+\.ts)"/g, (_t, f: string) => `from "${new URL(f, pastaLib).href}"`)
    const caminho = join(pasta, `mutante-${i}.mts`)
    writeFileSync(caminho, mutante, "utf8")
    const modulo = (await import(pathToFileURL(caminho).href)) as Modulo
    const resultado = await verificar(modulo)
    if (resultado.some((x) => !x.passou)) apanhadas += 1
    else naoApanhadas.push(`${mutacao.nome} — NENHUMA verificação falhou`)
  }
} finally {
  rmSync(pasta, { recursive: true, force: true })
}
for (const m of naoApanhadas) console.error(`✗ mutação não apanhada: ${m}`)

const total = base.length + MUTACOES.length
const falhas = falhadas.length + naoApanhadas.length
console.log(
  `cockpit: ${total - falhas}/${total} verificações ` +
    `(${base.length - falhadas.length}/${base.length} do módulo · ${apanhadas}/${MUTACOES.length} mutações apanhadas) · ` +
    (falhas === 0 ? "TUDO OK" : `${falhas} FALHAS`)
)
if (falhas > 0) process.exit(1)
