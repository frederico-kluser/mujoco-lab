/**
 * Teste do contrato da PLANTA REAL no `src/lib/sim.ts` (o mesmo ficheiro que o site usa, importado tal e
 * qual): `node testes/planta-real.mts` (Node ≥ 22.6 com type-stripping, sem dependências).
 *
 * Prova que (1) uma linha cf2 (sem `planta`, ou `planta: "cf2"`) continua a dar EXATAMENTE a leitura de
 * sempre — 16 obs, 64+64 ativações, ctrl = wrench derivável — e nenhuma chave nova; (2) uma linha real
 * dá as 21 obs do ator, o `ctrl` por rotor e os blocos bateria/motores/potência/aero/estimador; (3) valores
 * ausentes ou inválidos viram `null` (nunca 0 inventado, nunca exceção), inclusive sob lixo aleatório.
 */

import {
  derivarAct,
  lerBateria,
  lerHardware,
  lerLinha,
  lerMotores,
  lerPotencia,
  lerResumo,
  lerSim,
  N_OBS,
  N_OBS_REAL,
  plantaEmVigor,
  rotuloConsumidor,
  rotulosAct,
  rotulosObs,
  ROTULOS_ACT,
  ROTULOS_OBS,
  setpointTaxa,
} from "../src/lib/sim.ts"

let falhas = 0
let verificacoes = 0

function ok(condicao: boolean, descricao: string) {
  verificacoes += 1
  if (!condicao) {
    falhas += 1
    console.error(`✗ ${descricao}`)
  }
}

const zeros = (n: number) => new Array<number>(n).fill(0)

// ------------------------------------------------------------------------- (1) cf2 intacto

const baseCf2 = {
  t: 1.2,
  estado: "a_correr",
  ep: 3,
  passo: 60,
  retorno: 12.5,
  z: 0.98,
  dist_xy: 0.01,
  yaw_err: 0.002,
  vento_vel: 1,
  vento_azim: 90,
  vento_vec: [0, 1, 0],
  vento_modo: "nenhum",
  obs: Array.from({ length: 16 }, (_, i) => i / 100),
  act: [0.1, -0.2, 0.3, -0.4],
  ctrl: [0.27, 0.0001, -0.0002, 0.00003],
  h1: zeros(64).map((_, i) => i),
  h2: zeros(64).map((_, i) => -i),
  camera: null,
}

for (const [rotulo, bruto] of [
  ["cf2 sem planta", baseCf2],
  ["cf2 explícito", { ...baseCf2, planta: "cf2" }],
] as const) {
  const l = lerLinha(bruto)
  ok(l !== null, `${rotulo}: linha lida`)
  if (l === null) continue
  ok(l.obs.length === N_OBS, `${rotulo}: 16 obs`)
  ok(l.h1.length === 64 && l.h2.length === 64, `${rotulo}: 64+64 ativações`)
  ok(
    l.bateria === null &&
      l.motores === null &&
      l.potencia === null &&
      l.aero === null &&
      l.estimador === null,
    `${rotulo}: nenhum bloco da planta real`
  )
  const d = derivarAct(l)
  ok(d !== null && d.doBackend && d.empuxo === 0.27, `${rotulo}: ctrl do backend = wrench do cf2`)
  ok(rotulosObs(l.planta) === ROTULOS_OBS, `${rotulo}: rótulos das 16 obs de sempre`)
  ok(rotulosAct(l.planta) === ROTULOS_ACT, `${rotulo}: rótulos da ação de sempre`)
}
{
  // cf2 com listas a mais/curtas: o parser de sempre corta/preenche a 16/64 (comportamento antigo)
  const l = lerLinha({ ...baseCf2, obs: zeros(21), h1: zeros(128), h2: [1] })
  ok(l !== null && l.obs.length === 16 && l.h1.length === 64 && l.h2.length === 64, "cf2: tamanhos fixos 16/64/64")
  ok(lerLinha({ estado: "a_correr" }) === null, "linha sem t nem passo é descartada (como sempre)")
}

// ------------------------------------------------------------------------ (2) planta real

const bateriaReal = {
  soc: 0.9929,
  soc_estimado: 0.9901,
  v: 16.508,
  v_celula: 4.127,
  i: 9.206,
  p: 151.97,
  temp_c: 25.1,
  soh: 1.0,
  ciclos_eq: 0.0,
  n_recargas: 0,
  r0_mohm: 20.95,
  ah_voo: 0.064,
  wh_voo: 1.06,
  alerta: "",
  reformar: false,
  autonomia_min: null,
  s: 4,
  p_paralelo: 2,
  quimica: "li-ion",
  capacidade_ah: 9.0,
  pack_id: "molicel_p45b_4s2p",
  v_pouso_celula: 3.0,
  v_corte_celula: 2.5,
  v_medida: 16.5075,
  i_medida: 8.991,
  i_media: 9.218,
  ultimo_ciclo: { acao: "recarregar", dod: 0.01, ah: 0.089, wh: 1.47, c_medio: 1.03, t_medio_c: 25.07, soh: 0.99999 },
}

const real = lerLinha({
  ...baseCf2,
  planta: "real",
  obs: Array.from({ length: 21 }, (_, i) => i / 10),
  ctrl: [3.2, 3.3, 3.1, 3.25],
  h1: zeros(128).map((_, i) => i),
  bateria: bateriaReal,
  motores: {
    rpm: [4512, 4498, 4530, 4501],
    duty: [0.42, 0.41, 0.43, 0.42],
    empuxo_n: [3.2, 3.3, 3.1, 3.25],
    i_fase: [9.8, 9.7, 9.9, 9.6],
    omega_max_rpm: 8835.7,
    t_max_n: 25.22,
    t_max_frac: 0.972,
    armado: true,
    brownout: false,
  },
  potencia: {
    motores: 145.47,
    eletronica: 6.5,
    bec_perdas: 0.78,
    total: 151.97,
    consumidores_5v: { rpi5: 5.0, fc_h7: 0.6, cablagem: 0.0, sensor_imu: 0.017, mau: "x" },
  },
  aero: { kappa_t: [1, 1.01, 0.99, 1], altura_rotores: [50, 50, 50, 50] },
  estimador: { roll: 0.01, pitch: -0.02, psi: 0.1, h: 1.0, vz: 0, vx: 0, vy: 0, x: 0, y: 0 },
})
ok(real !== null && real.planta === "real", "real: planta lida")
if (real !== null) {
  ok(real.obs.length === N_OBS_REAL && real.obs[20] === 2, "real: 21 obs do ator")
  ok(real.h1.length === 128 && real.h2.length === 64, "real: ativações com o tamanho publicado (128) e 64 por omissão")
  ok(derivarAct(real) === null, "real: nada derivado do HoverEnv (derivarAct = null)")
  ok(real.ctrl !== null && real.ctrl[2] === 3.1, "real: ctrl = empuxo por rotor, tal e qual")
  const b = real.bateria
  ok(b !== null && b.soc === 0.9929 && b.socEstimado === 0.9901 && b.packId === "molicel_p45b_4s2p", "real: bateria lida")
  ok(b !== null && b.alerta === "nenhum" && b.reformar === false && b.autonomiaMin === null, "real: alerta '' = nenhum; autonomia null fica null")
  ok(b?.ultimoCiclo?.acao === "recarregar" && b.ultimoCiclo.iPico === null, "real: último ciclo (campos ausentes = null)")
  ok(real.motores?.armado === true && real.motores.tMaxFrac === 0.972 && real.motores.rpm[3] === 4501, "real: motores lidos")
  ok(
    real.potencia !== null &&
      real.potencia.consumidores5v.length === 4 &&
      real.potencia.consumidores5v.every((c) => c.id !== "mau"),
    "real: consumidores 5 V só com valores finitos"
  )
  ok(real.aero?.alturaRotores[0] === 50 && real.estimador?.psi === 0.1, "real: aero e estimador lidos")
  ok(plantaEmVigor(real, "cf2") === "real", "planta em vigor: a da linha vence a da API")
}
ok(plantaEmVigor(lerLinha(baseCf2), null, "real") === "real", "planta em vigor: sem planta na linha vale a da API")
ok(plantaEmVigor(null) === null, "planta em vigor: ninguém diz ⇒ null")

const obsReal = rotulosObs("real")
ok(obsReal.length === 21, "rótulos reais: 21 canais")
ok(obsReal.every((r, i) => r.indice === i), "rótulos reais: índices 0..20 por ordem")
ok(obsReal[15].flag === true && obsReal[16].flag === true && !obsReal[14].flag, "rótulos reais: ToF/fluxo válidos são flags")
ok(Math.abs(obsReal[3].escala - 9.81) < 1e-12 && obsReal[0].escala === 2 && Math.abs(obsReal[8].escala - Math.PI) < 1e-12, "rótulos reais: escalas ÷2, ÷9,81, ÷π")
ok(rotulosObs("real", "motores")[17].nome === "a_prev·r1", "rótulos reais (motores): ação anterior = aceleradores")
ok(rotulosAct("real")[1].nome.includes("taxa p") && rotulosAct("real", "motores")[0].nome.includes("acelerador r1"), "rótulos da ação: ctbr e motores")
ok(setpointTaxa(0.5, 0) === 1.25 && setpointTaxa(3, 2) === 1.5 && setpointTaxa(-9, 1) === -2.5 && setpointTaxa(null, 0) === null, "setpoint de taxa = clip(a) × TAXA_MAX")
ok(rotuloConsumidor("fc_h7").includes("H7") && rotuloConsumidor("novo_x") === "novo_x", "consumidores: prefixo fc_ e chave nova tal como vem")

// ------------------------------------------------------------- (3) ausente/inválido → null

const b2 = lerBateria({ soc: "abc", v: {}, alerta: "outra-coisa", reformar: "sim", ultimo_ciclo: [], quimica: 7 })
ok(
  b2 !== null &&
    b2.soc === null &&
    b2.v === null &&
    b2.alerta === null &&
    b2.reformar === null &&
    b2.ultimoCiclo === null &&
    b2.quimica === null,
  "bateria inválida: tudo null (nada inventado)"
)
ok(lerBateria({ alerta: "critica" })?.alerta === "critica" && lerBateria({ alerta: "tensao_baixa" })?.alerta === "tensao_baixa", "alertas reconhecidos")
ok(lerBateria(null) === null && lerBateria({}) === null && lerBateria([1, 2]) === null && lerBateria("x") === null, "bateria ausente/vazia/lista ⇒ null")
const m2 = lerMotores({ rpm: [1, "x"], duty: "nada", armado: 1 })
ok(
  m2 !== null && m2.rpm[0] === 1 && m2.rpm[1] === null && m2.rpm.length === 4 && m2.duty.every((d) => d === null) && m2.armado === null,
  "motores parciais: null por rotor em falta (nunca 0 fingido)"
)
ok(lerPotencia({ consumidores_5v: "x" })?.consumidores5v.length === 0, "potência sem consumidores ⇒ lista vazia")
ok(lerHardware(null) === null && lerHardware({ build: "b", kf: "1e-5", dr: true })?.kf === 1e-5, "hardware: null fica null; números em texto são lidos")

const sim = lerSim({ planta: "real", linhas: [{ ...baseCf2, planta: "real" }, "lixo", null] })
ok(sim.planta === "real" && sim.linhas.length === 1, "/api/sim: planta lida e linhas inválidas descartadas")
ok(lerSim({}).planta === null, "/api/sim sem planta ⇒ null")
const resumo = lerResumo({ planta: "real", hardware: { build: "endurance_12pol", modo_acao: "ctbr", massa_total_g: 1316, bateria: { s: 4, p: 2 } } })
ok(resumo.planta === "real" && resumo.hardware?.massaTotalG === 1316 && resumo.hardware.bateria?.s === 4, "/api/state: planta + hardware")
ok(lerResumo({ planta: "cf2", hardware: null }).hardware === null, "/api/state cf2: hardware null")

// lixo aleatório (determinístico): nenhum parser pode rebentar
let semente = 12345
const aleatorio = () => {
  semente = (semente * 1103515245 + 12345) % 2147483648
  return semente / 2147483648
}
const valoresLixo: unknown[] = [null, undefined, 0, -1, 1e308, "", "12", "abc", true, false, [], {}, [1, "x", null], { a: 1 }, NaN]
const lixo = (): unknown => valoresLixo[Math.floor(aleatorio() * valoresLixo.length)]
const chaves = ["planta", "obs", "ctrl", "h1", "bateria", "motores", "potencia", "aero", "estimador", "t", "passo"]
let rebentou = 0
for (let i = 0; i < 2000; i += 1) {
  const bruto: Record<string, unknown> = { t: aleatorio() > 0.1 ? i : lixo() }
  for (const k of chaves) if (aleatorio() > 0.4) bruto[k] = lixo()
  bruto.bateria = aleatorio() > 0.5 ? Object.fromEntries(Object.keys(bateriaReal).map((k) => [k, lixo()])) : bruto.bateria
  try {
    const l = lerLinha(bruto)
    if (l !== null) {
      for (const v of [...l.obs, ...l.act, ...(l.ctrl ?? [])]) if (!Number.isFinite(v)) throw new Error("não finito")
      const b = l.bateria
      if (b !== null) for (const v of Object.values(b)) if (typeof v === "number" && !Number.isFinite(v)) throw new Error("NaN")
    }
    lerResumo({ hardware: lixo(), planta: lixo() })
    lerSim({ linhas: [bruto], planta: lixo() })
  } catch (erro) {
    rebentou += 1
    if (rebentou < 3) console.error(erro)
  }
}
ok(rebentou === 0, `lixo aleatório: 2000 linhas sem exceções nem NaN (${rebentou} falhas)`)

console.log(`planta-real: ${verificacoes - falhas}/${verificacoes} verificações`)
if (falhas > 0) process.exit(1)
