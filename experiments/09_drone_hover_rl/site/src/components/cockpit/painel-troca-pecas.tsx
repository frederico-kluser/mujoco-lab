/**
 * Painel de Troca ao Vivo de Motores e Bateria (`POST /api/pecas`) + Leitura de Watts e Vazão (A).
 *
 * Permite trocar em tempo real os 4 motores e o pack de bateria do drone:
 *  · Cada motor tem cor 3D e dimensões físicas (diâmetro × altura, massa, KV, R_int, potência máxima)
 *    que atualizam imediatamente o modelo 3D no MuJoCo e a curva eletromecânica da propulsão;
 *  · Cada bateria tem cor 3D, dimensões da caixa, química, S×P, energia (Wh), vazão máxima de corrente (A)
 *    e resistência interna (R₀) que alteram imediatamente a tensão sob carga, os Watts gastos, a autonomia
 *    e a capacidade (ou impossibilidade) de alçar voo.
 */

import { useRef, useState } from "react"

import { Legenda, Leitura, Marca } from "@/components/cockpit/pecas"
import { useDesenhoHud } from "@/hooks/use-cockpit"
import { enviarPecas } from "@/lib/api"
import { fmtHud } from "@/lib/cockpit"

interface OpcaoMotor {
  id: string
  nome: string
  detalhe: string
  corHex: string
  corNome: string
}

interface OpcaoBateria {
  id: string
  nome: string
  detalhe: string
  corHex: string
  corNome: string
}

export const MOTORES_DISPONIVEIS: readonly OpcaoMotor[] = [
  {
    id: "tmotor_mn4004_kv300",
    nome: "MN4004 KV300",
    detalhe: "300 KV · 44×19 mm · 53 g · 300 W",
    corHex: "#242730",
    corNome: "Preto Anodizado",
  },
  {
    id: "tmotor_mn4004_kv400",
    nome: "MN4004 KV400",
    detalhe: "400 KV · 44×19 mm · 53 g · 300 W",
    corHex: "#b8c2d4",
    corNome: "Prata Titânio",
  },
  {
    id: "tmotor_mn4006_kv380",
    nome: "MN4006 KV380",
    detalhe: "380 KV · 44×21 mm · 68 g · 380 W",
    corHex: "#d9262e",
    corNome: "Vermelho Competição",
  },
  {
    id: "tmotor_mn5006_kv450",
    nome: "MN5006 KV450",
    detalhe: "450 KV · 56×22 mm · 126 g · 650 W",
    corHex: "#2470eb",
    corNome: "Azul Cobalto",
  },
  {
    id: "tmotor_mn3508_kv380",
    nome: "MN3508 KV380",
    detalhe: "380 KV · 42×27 mm · 103 g · 390 W",
    corHex: "#e0a324",
    corNome: "Dourado Bronze",
  },
  {
    id: "tmotor_mn2806_kv400",
    nome: "MN2806 KV400",
    detalhe: "400 KV · 35×18 mm · 46 g · 260 W",
    corHex: "#1eb86b",
    corNome: "Verde Esmeralda",
  },
]

export const BATERIAS_DISPONIVEIS: readonly OpcaoBateria[] = [
  {
    id: "molicel_p50b_6s2p",
    nome: "6S2P Molicel P50B",
    detalhe: "216 Wh · Vazão 120 A · 871 g · 142×70×44 mm",
    corHex: "#8c1f1a",
    corNome: "Vermelho Rubi",
  },
  {
    id: "molicel_p50b_6s3p",
    nome: "6S3P Molicel P50B Mega",
    detalhe: "324 Wh · Vazão 180 A · 1306 g · 146×105×46 mm",
    corHex: "#1f52c7",
    corNome: "Azul Royal",
  },
  {
    id: "lipo_6s1p_4500_alta_vazao",
    nome: "6S1P LiPo Alta Vazão",
    detalhe: "100 Wh · Vazão 225 A · 705 g · 152×50×52 mm",
    corHex: "#ebb814",
    corNome: "Amarelo Ouro",
  },
  {
    id: "amprius_si_6s2p",
    nome: "6S2P Amprius Silício",
    detalhe: "222 Wh · Vazão 80 A · 535 g · 132×60×36 mm",
    corHex: "#9433d1",
    corNome: "Roxo Tecnológico",
  },
  {
    id: "molicel_p45b_6s1p",
    nome: "6S1P Molicel P45B Leve",
    detalhe: "97 Wh · Vazão 45 A · 450 g · 128×44×24 mm",
    corHex: "#1fad59",
    corNome: "Verde Esmeralda",
  },
  {
    id: "lipo_4s1p_4500_baixa_tensao",
    nome: "4S1P LiPo 14,8 V Fraca",
    detalhe: "67 Wh · Vazão 150 A · 474 g · Tensão 4S",
    corHex: "#eb6b1a",
    corNome: "Laranja Âmbar",
  },
]

export function PainelTrocaPecas() {
  const [motorId, setMotorId] = useState("tmotor_mn4004_kv300")
  const [bateriaId, setBateriaId] = useState("molicel_p50b_6s2p")
  const rWatts = useRef<HTMLSpanElement>(null)
  const rVazao = useRef<HTMLSpanElement>(null)
  const rEstado = useRef<HTMLSpanElement>(null)
  const rSincronizado = useRef(false)

  useDesenhoHud(({ hud, texto }) => {
    const p = hud?.pecas ?? null
    if (p !== null && !rSincronizado.current) {
      rSincronizado.current = true
      if (p.motorId) setMotorId(p.motorId)
      if (p.bateriaId) setBateriaId(p.bateriaId)
    }
    if (!texto) return
    if (rWatts.current !== null) {
      const wTot = p?.wattsTotal ?? hud?.bateria?.p ?? null
      const wMot = p?.wattsMotores ?? null
      const txtW =
        wTot == null
          ? "—"
          : `${fmtHud(wTot, 1)} W${wMot == null ? "" : ` (mot ${fmtHud(wMot, 0)} W)`}`
      if (rWatts.current.textContent !== txtW) rWatts.current.textContent = txtW
    }
    if (rVazao.current !== null) {
      const iAt = p?.vazaoAtualA ?? hud?.bateria?.i ?? null
      const iMax = p?.vazaoMaxA ?? 120
      const pct = p?.vazaoPct ?? (iAt != null ? (100 * iAt) / iMax : null)
      const txtV =
        iAt == null
          ? "—"
          : `${fmtHud(iAt, 1)} / ${fmtHud(iMax, 0)} A (${fmtHud(pct, 0)} %)`
      if (rVazao.current.textContent !== txtV) rVazao.current.textContent = txtV
    }
    if (rEstado.current !== null) {
      const txtE =
        p === null
          ? "—"
          : `${fmtHud(p.massaTotalG, 0)} g · T/W ${fmtHud(p.tWOge, 2)} · ${
              p.podeAlcarVoo ? "ALÇA VOO" : "NÃO ALÇA VOO"
            }`
      if (rEstado.current.textContent !== txtE) rEstado.current.textContent = txtE
    }
  })

  const selecionarMotor = (novoMotor: string) => {
    setMotorId(novoMotor)
    void enviarPecas({ motor_id: novoMotor, bateria_id: bateriaId }).catch(
      () => undefined
    )
  }

  const selecionarBateria = (novaBateria: string) => {
    setBateriaId(novaBateria)
    void enviarPecas({ motor_id: motorId, bateria_id: novaBateria }).catch(
      () => undefined
    )
  }

  return (
    <section
      data-testid="painel-troca-pecas"
      className="flex flex-col gap-3 rounded-xl border border-white/12 bg-black/45 p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-2">
        <div className="flex flex-col">
          <Legenda>motores & bateria · troca ao vivo (cores/tamanhos 3D)</Legenda>
          <span className="text-[0.7rem] text-muted-foreground">
            Altera tamanho e cor no 3D, KV, potência, vazão (A) e Watts gastos
          </span>
        </div>
        <Marca tom="ativo" testid="pecas-watts-badge">
          <span ref={rWatts} data-testid="pecas-watts-atuais">
            314,2 W
          </span>
        </Marca>
      </div>

      <div className="grid grid-cols-2 gap-2 rounded-lg bg-white/5 px-2.5 py-2">
        <Leitura
          rotulo="vazão de corrente (A)"
          refValor={rVazao}
          testid="pecas-vazao-atual"
        />
        <Leitura
          rotulo="massa · T/W · voo"
          refValor={rEstado}
          testid="pecas-estado-voo"
        />
      </div>

      {/* Seletor de Motores */}
      <div className="flex flex-col gap-1.5">
        <Legenda>escolher motores (×4 no drone — muda tamanho e cor 3D)</Legenda>
        <div className="grid grid-cols-2 gap-1.5" data-testid="lista-motores">
          {MOTORES_DISPONIVEIS.map((m) => {
            const ativo = m.id === motorId
            return (
              <button
                key={m.id}
                type="button"
                data-testid={`peca-motor-${m.id}`}
                aria-pressed={ativo}
                onClick={() => selecionarMotor(m.id)}
                className={`flex flex-col items-start gap-0.5 rounded-lg border px-2.5 py-1.5 text-left transition ${
                  ativo
                    ? "border-emerald-400 bg-emerald-500/18 text-hud shadow-[0_0_10px_rgb(16_185_129/0.25)]"
                    : "border-white/12 bg-white/5 text-hud/85 hover:bg-white/12"
                }`}
              >
                <span className="flex items-center gap-1.5 text-[0.74rem] font-bold">
                  <span
                    className="inline-block size-3 shrink-0 rounded-full border border-white/40"
                    style={{ backgroundColor: m.corHex }}
                    title={m.corNome}
                  />
                  {m.nome}
                </span>
                <span className="font-mono text-[0.62rem] text-muted-foreground">
                  {m.detalhe}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Seletor de Baterias */}
      <div className="flex flex-col gap-1.5">
        <Legenda>escolher bateria (muda tamanho/cor 3D, Wh e vazão A)</Legenda>
        <div className="grid grid-cols-2 gap-1.5" data-testid="lista-baterias">
          {BATERIAS_DISPONIVEIS.map((b) => {
            const ativa = b.id === bateriaId
            return (
              <button
                key={b.id}
                type="button"
                data-testid={`peca-bateria-${b.id}`}
                aria-pressed={ativa}
                onClick={() => selecionarBateria(b.id)}
                className={`flex flex-col items-start gap-0.5 rounded-lg border px-2.5 py-1.5 text-left transition ${
                  ativa
                    ? "border-sky-400 bg-sky-500/18 text-hud shadow-[0_0_10px_rgb(56_189_248/0.25)]"
                    : "border-white/12 bg-white/5 text-hud/85 hover:bg-white/12"
                }`}
              >
                <span className="flex items-center gap-1.5 text-[0.74rem] font-bold">
                  <span
                    className="inline-block size-3 shrink-0 rounded-sm border border-white/40"
                    style={{ backgroundColor: b.corHex }}
                    title={b.corNome}
                  />
                  {b.nome}
                </span>
                <span className="font-mono text-[0.62rem] text-muted-foreground">
                  {b.detalhe}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </section>
  )
}
