/**
 * Painel de Presets Calibrados de Propulsão (Motor + Bateria + Ganhos IA/C++) (`POST /api/pecas`).
 *
 * Em vez de permitir combinações livres incompatíveis, apresenta 6 Presets Calibrados e Homologados:
 *  · Cada preset combina um motor real (tamanho D×H mm e cor 3D) com uma bateria real (tamanho da caixa,
 *    cor 3D, energia Wh e vazão máxima A) e recalibra imediatamente o controlador de voo e a IA TensorFlow;
 *  · Exibe em tempo real os Watts gastos (total + motores), a vazão de corrente (A / A_max), a massa e T/W,
 *    e a distância adaptativa ao alvo (`distAlvoDinamicaM` 2,15 m → 3,60 m quando a bola acelera).
 */

import { useRef, useState } from "react"

import { Legenda, Leitura, Marca } from "@/components/cockpit/pecas"
import { useDesenhoHud } from "@/hooks/use-cockpit"
import { enviarPecas } from "@/lib/api"
import { fmtHud } from "@/lib/cockpit"

export interface PresetPropulsao {
  id: string
  nome: string
  motorResumo: string
  bateriaResumo: string
  motorCorHex: string
  motorCorNome: string
  bateriaCorHex: string
  bateriaCorNome: string
}

export const PRESETS_CALIBRADOS: readonly PresetPropulsao[] = [
  {
    id: "endurance_p50b",
    nome: "1. Endurance Padrão",
    motorResumo: "MN4004 KV300 (44×19 mm · 300 W · Preto)",
    bateriaResumo: "6S2P P50B · 216 Wh · Vazão 120 A · 2968 g",
    motorCorHex: "#242730",
    motorCorNome: "Preto Anodizado",
    bateriaCorHex: "#8c1f1a",
    bateriaCorNome: "Vermelho Rubi",
  },
  {
    id: "tatico_silicio",
    nome: "2. Tático Ultra-Leve",
    motorResumo: "MN4004 KV300 (44×19 mm · 300 W · Preto)",
    bateriaResumo: "6S2P Amprius Si · 222 Wh · Vazão 80 A · 2529 g",
    motorCorHex: "#242730",
    motorCorNome: "Preto Anodizado",
    bateriaCorHex: "#9433d1",
    bateriaCorNome: "Roxo Tecnológico",
  },
  {
    id: "interceptor_lipo",
    nome: "3. Interceptor Alta Vazão",
    motorResumo: "MN4006 KV380 (44×21 mm · 380 W · Vermelho)",
    bateriaResumo: "6S1P LiPo 45C · 111 Wh · Vazão 225 A · 2912 g",
    motorCorHex: "#d9262e",
    motorCorNome: "Vermelho Competição",
    bateriaCorHex: "#ebb814",
    bateriaCorNome: "Amarelo Ouro",
  },
  {
    id: "heavy_6s3p",
    nome: "4. Heavy Long-Range",
    motorResumo: "MN4006 KV380 (44×21 mm · 380 W · Vermelho)",
    bateriaResumo: "6S3P P50B Mega · 324 Wh · Vazão 180 A · 3460 g",
    motorCorHex: "#d9262e",
    motorCorNome: "Vermelho Competição",
    bateriaCorHex: "#1f52c7",
    bateriaCorNome: "Azul Royal",
  },
  {
    id: "forca_bruta_5006",
    nome: "5. Força Bruta 650W",
    motorResumo: "MN5006 KV450 (56×22 mm · 650 W · Azul)",
    bateriaResumo: "6S2P P50B · 216 Wh · Vazão 120 A · 3180 g",
    motorCorHex: "#2470eb",
    motorCorNome: "Azul Cobalto",
    bateriaCorHex: "#8c1f1a",
    bateriaCorNome: "Vermelho Rubi",
  },
  {
    id: "agile_scout",
    nome: "6. Agile Scout Compacto",
    motorResumo: "MN3508 KV380 (42×27 mm · 390 W · Dourado)",
    bateriaResumo: "6S1P P45B Leve · 97 Wh · Vazão 45 A · 2723 g",
    motorCorHex: "#e0a324",
    motorCorNome: "Dourado Bronze",
    bateriaCorHex: "#1fad59",
    bateriaCorNome: "Verde Esmeralda",
  },
]

export function PainelTrocaPecas() {
  const [presetId, setPresetId] = useState("endurance_p50b")
  const rWatts = useRef<HTMLSpanElement>(null)
  const rVazao = useRef<HTMLSpanElement>(null)
  const rEstado = useRef<HTMLSpanElement>(null)
  const rDistAlvo = useRef<HTMLSpanElement>(null)
  const rSincronizado = useRef(false)

  useDesenhoHud(({ hud, texto }) => {
    const p = hud?.pecas ?? null
    if (p !== null && !rSincronizado.current) {
      rSincronizado.current = true
      if (p.presetId) setPresetId(p.presetId)
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
              p.podeAlcarVoo ? "CALIBRADO" : "NÃO ALÇA VOO"
            }`
      if (rEstado.current.textContent !== txtE) rEstado.current.textContent = txtE
    }
    if (rDistAlvo.current !== null) {
      const dDin = p?.distAlvoDinamicaM ?? 2.15
      const txtD = `${fmtHud(dDin, 2)} m`
      if (rDistAlvo.current.textContent !== txtD)
        rDistAlvo.current.textContent = txtD
    }
  })

  const selecionarPreset = (novoPreset: string) => {
    setPresetId(novoPreset)
    void enviarPecas({ preset_id: novoPreset }).catch(() => undefined)
  }

  return (
    <section
      data-testid="painel-troca-pecas"
      className="flex flex-col gap-3 rounded-xl border border-white/12 bg-black/45 p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-2">
        <div className="flex flex-col">
          <Legenda>presets calibrados · motor + bateria (sem combinação livre)</Legenda>
          <span className="text-[0.7rem] text-muted-foreground">
            Cada preset ajusta tamanho/cor 3D, peso, vazão (A), Watts e ganhos de estabilidade
          </span>
        </div>
        <Marca tom="ativo" testid="pecas-watts-badge">
          <span ref={rWatts} data-testid="pecas-watts-atuais">
            314,2 W
          </span>
        </Marca>
      </div>

      <div className="grid grid-cols-3 gap-2 rounded-lg bg-white/5 px-2.5 py-2">
        <Leitura
          rotulo="vazão de corrente (A)"
          refValor={rVazao}
          testid="pecas-vazao-atual"
        />
        <Leitura
          rotulo="massa · T/W · estado"
          refValor={rEstado}
          testid="pecas-estado-voo"
        />
        <Leitura
          rotulo="distância dinâmica alvo"
          refValor={rDistAlvo}
          testid="pecas-dist-alvo"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Legenda>escolher preset calibrado (motor ● + bateria ■ no 3D)</Legenda>
        <div className="grid grid-cols-2 gap-1.5" data-testid="lista-presets-pecas">
          {PRESETS_CALIBRADOS.map((pr) => {
            const ativo = pr.id === presetId
            return (
              <button
                key={pr.id}
                type="button"
                data-testid={`preset-pecas-${pr.id}`}
                aria-pressed={ativo}
                onClick={() => selecionarPreset(pr.id)}
                className={`flex flex-col items-start gap-0.5 rounded-lg border px-2.5 py-1.5 text-left transition ${
                  ativo
                    ? "border-emerald-400 bg-emerald-500/18 text-hud shadow-[0_0_10px_rgb(16_185_129/0.25)]"
                    : "border-white/12 bg-white/5 text-hud/85 hover:bg-white/12"
                }`}
              >
                <span className="flex items-center gap-1.5 text-[0.74rem] font-bold">
                  <span
                    className="inline-block size-3 shrink-0 rounded-full border border-white/40"
                    style={{ backgroundColor: pr.motorCorHex }}
                    title={`Motor: ${pr.motorCorNome}`}
                  />
                  <span
                    className="inline-block size-3 shrink-0 rounded-sm border border-white/40"
                    style={{ backgroundColor: pr.bateriaCorHex }}
                    title={`Bateria: ${pr.bateriaCorNome}`}
                  />
                  {pr.nome}
                </span>
                <span className="font-mono text-[0.61rem] text-hud/80">
                  {pr.motorResumo}
                </span>
                <span className="font-mono text-[0.60rem] text-muted-foreground">
                  {pr.bateriaResumo}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </section>
  )
}
