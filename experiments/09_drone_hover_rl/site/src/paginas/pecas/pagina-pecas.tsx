/**
 * PÁGINA DAS PEÇAS 3D (`/pecas`) — cada peça do drone que o cockpit voa, em 3D, com a ficha real (medidas, como
 * funciona, PORQUE é necessária ao projeto, fontes), as ferragens que a prendem (contadas no modelo), os PASSOS DE
 * MONTAGEM pela ordem da bancada e — nas peças impressas em ABS — o modelo para imprimir (STL) com massa, tempo e custo.
 *
 *  · à esquerda (em baixo no telemóvel): PEÇAS por categoria → a ficha da peça · MONTAGEM passo a passo ·
 *    FERRAGENS (todos os parafusos, porcas, anilhas e pilares, com quantidades e binários de aperto) ·
 *    IMPRIMIR E CUSTOS (as peças impressas com o STL de cada uma e o custo de referência de tudo, R$ e US$);
 *  · à direita: o VISOR (arrastar orbita, roda aproxima, clicar escolhe uma peça) com: drone inteiro / só a peça,
 *    vista explodida, os ombros e cotovelos (mexem como no MuJoCo — o sem-fim roda a redução real × o ombro) e as
 *    hélices a girar.
 *
 * Os dados são os do simulador (`GET /api/pecas3d`): nada aqui é desenhado à mão. A página é a do DRONE — não mostra
 * nem descreve nenhuma carga útil.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Download,
  Expand,
  Focus,
  Layers,
  Loader2,
  RotateCw,
  Settings2,
  Wrench,
} from "lucide-react"

import {
  carregarPecas,
  num,
  preco,
  urlStl,
  type DadosPecas,
  type FichaPeca,
  type PecaImpressa,
} from "@/paginas/pecas/dados"
import { Visor3D, type ModoVisor } from "@/paginas/pecas/visor"

type Aba = "pecas" | "montagem" | "ferragens" | "custos"

/** Câmbio de reserva se o servidor não mandar o seu (nunca acontece com o `sim_site.py` atual). */
const CAMBIO_RESERVA = 5.4

const FOCO =
  "outline-none focus-visible:ring-2 focus-visible:ring-hud-ciano focus-visible:ring-offset-2 focus-visible:ring-offset-black"

function Etiqueta({ children }: { children: ReactNode }) {
  return (
    <span className="font-etiqueta text-[0.66rem] tracking-[0.14em] text-muted-foreground uppercase">
      {children}
    </span>
  )
}

function Botao({
  ativo,
  onClick,
  children,
  titulo,
  desativado,
  testid,
}: {
  ativo?: boolean
  onClick: () => void
  children: ReactNode
  titulo?: string
  desativado?: boolean
  testid?: string
}) {
  return (
    <button
      type="button"
      title={titulo}
      aria-pressed={ativo}
      disabled={desativado}
      onClick={onClick}
      data-testid={testid}
      className={`${FOCO} inline-flex min-h-8 items-center gap-1.5 rounded-md border px-2.5 text-[0.78rem] transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
        ativo
          ? "border-hud-ciano/70 bg-hud-ciano/15 text-hud-ciano"
          : "border-white/12 bg-white/[0.04] text-hud hover:bg-white/[0.09]"
      }`}
    >
      {children}
    </button>
  )
}

function Deslizador({
  rotulo,
  valor,
  min,
  max,
  passo,
  unidade,
  onChange,
  testid,
}: {
  rotulo: string
  valor: number
  min: number
  max: number
  passo: number
  unidade: string
  onChange: (v: number) => void
  testid?: string
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="flex items-baseline justify-between gap-3">
        <Etiqueta>{rotulo}</Etiqueta>
        <span className="font-mono text-[0.76rem] text-hud">
          {num(valor, unidade === "%" ? 0 : 0)}
          {unidade}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={passo}
        value={valor}
        data-testid={testid}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--hud-ciano)]"
      />
    </label>
  )
}

/** Um ficheiro para imprimir: as cópias iguais de uma peça partilham o mesmo STL. */
interface FicheiroImpresso {
  arquivo: string
  rep: PecaImpressa
  instancias: number[]
}

function ficheirosImpressos(
  dados: DadosPecas,
  filtro: (v: PecaImpressa) => boolean = () => true
): FicheiroImpresso[] {
  const por = new Map<string, FicheiroImpresso>()
  for (const v of Object.values(dados.impressas ?? {})) {
    if (!filtro(v)) continue
    const arq = v.arquivo ?? `${v.peca}_${v.inst}.stl`
    const f = por.get(arq)
    if (f) f.instancias.push(v.inst)
    else por.set(arq, { arquivo: arq, rep: v, instancias: [v.inst] })
  }
  return [...por.values()].sort(
    (a, b) =>
      a.rep.peca.localeCompare(b.rep.peca) || a.arquivo.localeCompare(b.arquivo)
  )
}

/** Ligação de descarga com o aspeto dos botões (os STL vêm do servidor: `GET /api/pecas3d/stl`). */
function LigacaoStl({
  href,
  nome,
  children,
  titulo,
  testid,
}: {
  href: string
  nome: string
  children: ReactNode
  titulo?: string
  testid?: string
}) {
  return (
    <a
      href={href}
      download={nome}
      title={titulo}
      data-testid={testid}
      className={`${FOCO} inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-md border border-white/12 bg-white/[0.04] px-2.5 text-[0.78rem] text-hud transition-colors hover:bg-white/[0.09]`}
    >
      {children}
    </a>
  )
}

function avisosImpressao(v: PecaImpressa, mesa?: [number, number, number]) {
  const av: string[] = []
  if (v.fechada === false) av.push("malha aberta — confirme no fatiador")
  if (v.cabe_mesa === false)
    av.push(
      `não cabe numa mesa de ${mesa ? `${mesa[0]} × ${mesa[1]} × ${mesa[2]}` : "220 × 220 × 250"} mm`
    )
  return av
}

function contarFerragens(dados: DadosPecas, peca: string, inst: number | null) {
  const conta = new Map<string, number>()
  for (const it of dados.ferragens.instancias) {
    if (it.peca !== peca || (inst !== null && it.inst !== inst)) continue
    conta.set(it.tipo, (conta.get(it.tipo) ?? 0) + 1)
  }
  return [...conta.entries()].sort((a, b) => b[1] - a[1])
}

function FichaDaPeca({
  dados,
  id,
  ficha,
  inst,
  onInst,
  onPasso,
  onFechar,
  modo,
  onModo,
}: {
  dados: DadosPecas
  id: string
  ficha: FichaPeca
  inst: number | null
  onInst: (i: number | null) => void
  onPasso: (n: number) => void
  onFechar: () => void
  modo: ModoVisor
  onModo: (m: ModoVisor) => void
}) {
  const instancias = ficha.instancias ?? [0]
  const ferr = contarFerragens(dados, id, inst)
  const passo = dados.passos.find((p) => p.pecas.includes(id))
  const cat =
    dados.categorias.find((c) => c.id === ficha.categoria)?.nome ??
    ficha.categoria
  const cambio = dados.custos?.cambio_usd_brl ?? CAMBIO_RESERVA
  const ficheiros = ficheirosImpressos(
    dados,
    (v) => v.peca === id && (inst === null || v.inst === inst)
  )
  const par = dados.massas_parametros
  return (
    <div className="flex flex-col gap-4" data-testid="ficha-peca">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <Etiqueta>{cat}</Etiqueta>
          <h2
            className="text-[1.02rem] leading-snug font-bold text-hud"
            data-testid="ficha-nome"
          >
            {ficha.nome}
          </h2>
          {instancias.length > 1 && (
            <span className="text-[0.74rem] text-muted-foreground">
              {instancias.length} unidades no drone
            </span>
          )}
        </div>
        <Botao onClick={onFechar} titulo="Voltar à lista (Esc)">
          <ArrowLeft className="size-3.5" /> lista
        </Botao>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Botao
          ativo={modo === "drone"}
          onClick={() => onModo("drone")}
          testid="modo-drone"
        >
          <Layers className="size-3.5" /> no drone
        </Botao>
        <Botao
          ativo={modo === "peca"}
          onClick={() => {
            if (inst === null && instancias.length > 1) onInst(instancias[0]) // uma unidade, em grande
            onModo("peca")
          }}
          testid="modo-peca"
        >
          <Focus className="size-3.5" /> só a peça
        </Botao>
        {instancias.length > 1 &&
          [null, ...instancias].map((i) => (
            <Botao key={String(i)} ativo={inst === i} onClick={() => onInst(i)}>
              {i === null ? "todas" : `n.º ${i}`}
            </Botao>
          ))}
      </div>
      {ficha.resumo && (
        <p className="text-[0.82rem] leading-relaxed text-hud">
          {ficha.resumo}
        </p>
      )}
      {ficha.porque && (
        <section
          className="flex flex-col gap-1.5 rounded-md border border-hud-ciano/25 bg-hud-ciano/[0.06] p-3"
          data-testid="ficha-porque"
        >
          <Etiqueta>porque é necessária</Etiqueta>
          <p className="text-[0.8rem] leading-relaxed text-hud">
            {ficha.porque}
          </p>
        </section>
      )}
      {(ficha.massa_medida_g ?? 0) > 0 && (
        <p
          className="font-mono text-[0.74rem] text-muted-foreground"
          data-testid="ficha-massa"
        >
          massa medida no modelo: {num(ficha.massa_medida_g, 0)} g
          {instancias.length > 1 ? ` (as ${instancias.length} unidades)` : ""}
        </p>
      )}
      {ficheiros.length > 0 && (
        <section
          className="flex flex-col gap-1.5"
          data-testid="ficha-impressao"
        >
          <Etiqueta>imprimir em ABS</Etiqueta>
          <ul className="flex flex-col text-[0.76rem]">
            {ficheiros.map((f) => (
              <li
                key={f.arquivo}
                className="flex flex-col gap-1 border-b border-white/8 py-1.5 last:border-0"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-hud/90">
                    <span className="font-mono text-hud">{f.arquivo}</span>
                    {f.instancias.length > 1
                      ? ` · imprimir ${f.instancias.length}×`
                      : ""}
                    <br />
                    {num(f.rep.massa_g, 0)} g · {num(f.rep.tempo_h, 1)} h ·{" "}
                    {f.rep.dims_mm
                      ? `${f.rep.dims_mm.map((x) => num(x, 0)).join(" × ")} mm · `
                      : ""}
                    {preco(f.rep.custo_usd, cambio)} cada
                  </span>
                  <LigacaoStl
                    href={urlStl(dados.build, f.arquivo)}
                    nome={f.arquivo}
                    titulo="Descarregar o modelo para imprimir (STL em mm, já deitado na face de apoio)"
                    testid={`stl-${f.arquivo}`}
                  >
                    <Download className="size-3.5" /> STL
                  </LigacaoStl>
                </div>
                {avisosImpressao(f.rep, dados.impressao?.mesa_mm).map((a) => (
                  <span key={a} className="text-[0.7rem] text-hud-ambar">
                    ⚠ {a}
                  </span>
                ))}
              </li>
            ))}
          </ul>
          {ficheiros[0]?.rep.nota && (
            <p className="text-[0.72rem] leading-snug text-hud/80">
              {ficheiros[0].rep.nota}
            </p>
          )}
          <p className="text-[0.68rem] leading-snug text-muted-foreground">
            ABS ({num(par?.rho_abs_g_cm3 ?? 1.04, 2)} g/cm³), paredes de{" "}
            {num(par?.parede_mm ?? 1.2, 1)} mm e{" "}
            {num((par?.enchimento ?? 0.4) * 100, 0)} % de enchimento — a massa e
            o tempo saem da geometria, como num fatiador.
          </p>
        </section>
      )}
      {ficha.custo && (
        <section className="flex flex-col gap-1" data-testid="ficha-custo">
          <Etiqueta>custo de referência (todas as unidades)</Etiqueta>
          <p className="font-mono text-[0.82rem] text-hud">
            {preco(ficha.custo.total_usd, cambio)}
          </p>
          <ul className="flex flex-col text-[0.7rem] text-muted-foreground">
            {ficha.custo.itens.map((c, i) => (
              <li key={i}>
                {c.qtd > 1 ? `${c.qtd} × ` : ""}
                {c.fonte} — {preco(c.total_usd, cambio)}
              </li>
            ))}
          </ul>
        </section>
      )}
      {ficha.como_funciona && (
        <section className="flex flex-col gap-1.5">
          <Etiqueta>como funciona</Etiqueta>
          <p className="text-[0.8rem] leading-relaxed text-hud/90">
            {ficha.como_funciona}
          </p>
        </section>
      )}
      {ficha.specs.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <Etiqueta>especificações</Etiqueta>
          <table className="w-full text-[0.76rem]">
            <tbody>
              {ficha.specs.map(([k, v]) => (
                <tr key={k} className="border-b border-white/8 last:border-0">
                  <th className="py-1 pr-3 text-left font-normal text-muted-foreground">
                    {k}
                  </th>
                  <td className="py-1 text-right font-mono text-hud">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {ferr.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <Etiqueta>
            ferragens desta peça
            {inst !== null && instancias.length > 1 ? ` (n.º ${inst})` : ""}
          </Etiqueta>
          <ul className="flex flex-col gap-0.5 text-[0.76rem]">
            {ferr.map(([tipo, q]) => (
              <li
                key={tipo}
                className="flex justify-between gap-3 border-b border-white/8 py-1 last:border-0"
              >
                <span className="text-hud/90">
                  {dados.ferragens.tipos[tipo]?.descricao ?? tipo}
                </span>
                <span className="font-mono text-hud">×{q}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {passo && (
        <Botao onClick={() => onPasso(passo.n)}>
          <Wrench className="size-3.5" /> montagem: passo {passo.n} —{" "}
          {passo.titulo}
        </Botao>
      )}
      {ficha.fontes.length > 0 && (
        <section className="flex flex-col gap-1">
          <Etiqueta>fontes</Etiqueta>
          <ul className="flex flex-col gap-1 text-[0.7rem] break-all">
            {ficha.fontes.map((f) => (
              <li key={f}>
                {/^https?:/.test(f) ? (
                  <a
                    href={f}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-hud-ciano/90 underline-offset-2 hover:underline"
                  >
                    {f}
                  </a>
                ) : (
                  <span className="text-muted-foreground">{f}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

export default function PaginaPecas() {
  const [dados, setDados] = useState<DadosPecas | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [aba, setAba] = useState<Aba>("pecas")
  const [sel, setSel] = useState<{ peca: string; inst: number | null } | null>(
    null
  )
  const [modo, setModo] = useState<ModoVisor>("drone")
  const [explodir, setExplodir] = useState(0)
  const [ombro, setOmbro] = useState(0)
  const [cotovelo, setCotovelo] = useState(0)
  const [girar, setGirar] = useState(false)
  const [passo, setPasso] = useState<number | null>(null)
  const [ferragem, setFerragem] = useState<string | null>(null)
  const [controlos, setControlos] = useState(
    () => window.matchMedia("(min-width: 640px)").matches
  )
  const caixa = useRef<HTMLDivElement>(null)
  const visor = useRef<Visor3D | null>(null)

  useEffect(() => {
    document.title = "Peças 3D e montagem — drone"
    const ab = new AbortController()
    carregarPecas(ab.signal)
      .then(setDados)
      .catch((e: unknown) => {
        if (!ab.signal.aborted)
          setErro(e instanceof Error ? e.message : String(e))
      })
    return () => ab.abort()
  }, [])

  useEffect(() => {
    if (!dados || !caixa.current) return
    const v = new Visor3D(caixa.current, dados)
    v.aoEscolher = (peca, inst) => {
      setPasso(null)
      setFerragem(null)
      setSel(peca ? { peca, inst } : null)
      if (peca) setAba("pecas")
    }
    visor.current = v
    return () => {
      v.destruir()
      visor.current = null
    }
  }, [dados])

  // estado → visor
  useEffect(() => {
    visor.current?.selecionar(sel?.peca ?? null, sel?.inst ?? null)
  }, [sel])
  useEffect(() => {
    if (ferragem) return
    visor.current?.definirModo(sel ? modo : "drone")
  }, [modo, sel, ferragem])
  useEffect(() => visor.current?.definirExplodir(explodir / 100), [explodir])
  useEffect(
    () => visor.current?.definirJuntas(ombro, cotovelo),
    [ombro, cotovelo]
  )
  useEffect(() => visor.current?.definirGiroHelices(girar), [girar])
  useEffect(() => {
    const v = visor.current
    if (!v || !dados) return
    if (passo === null) {
      v.definirVisiveis(null)
      return
    }
    const ate = new Set(
      dados.passos.filter((p) => p.n <= passo).flatMap((p) => p.pecas)
    )
    const agora = new Set(dados.passos.find((p) => p.n === passo)?.pecas ?? [])
    v.definirVisiveis(ate, agora)
    v.enquadrar()
  }, [passo, dados])
  useEffect(() => {
    const v = visor.current
    if (!v) return
    if (ferragem) v.mostrarFerragem(ferragem)
    else v.definirModo(sel ? modo : "drone")
  }, [ferragem]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSel(null)
        setFerragem(null)
        setPasso(null)
        setModo("drone")
      }
    }
    window.addEventListener("keydown", tecla)
    return () => window.removeEventListener("keydown", tecla)
  }, [])

  const porCategoria = useMemo(() => {
    if (!dados) return []
    return dados.categorias
      .map((c) => ({
        ...c,
        pecas: Object.entries(dados.pecas)
          .filter(
            ([id, f]) =>
              f.categoria === c.id && id !== "outros" && id !== "ferragens"
          )
          .sort((a, b) => a[1].nome.localeCompare(b[1].nome, "pt")),
      }))
      .filter((c) => c.pecas.length > 0)
  }, [dados])

  const juntas = useMemo(() => {
    const lim = { ombro: [-40, 40], cotovelo: [-60, 60] }
    for (const c of dados?.corpos ?? []) {
      if (!c.junta?.limites_graus) continue
      if (c.junta.nome.startsWith("ombro")) lim.ombro = c.junta.limites_graus
      if (c.junta.nome.startsWith("cotovelo"))
        lim.cotovelo = c.junta.limites_graus
    }
    return { tem: (dados?.corpos ?? []).some((c) => c.junta), lim }
  }, [dados])

  const tiposFerragem = useMemo(
    () =>
      dados
        ? Object.entries(dados.ferragens.tipos).sort(
            (a, b) => b[1].qtd - a[1].qtd
          )
        : [],
    [dados]
  )
  const totalFerragens = tiposFerragem.reduce((s, [, t]) => s + t.qtd, 0)
  const passoAtual =
    dados && passo !== null
      ? dados.passos.find((p) => p.n === passo)
      : undefined

  const cambio = dados?.custos?.cambio_usd_brl ?? CAMBIO_RESERVA
  const ficheiros = useMemo(
    () => (dados ? ficheirosImpressos(dados) : []),
    [dados]
  )

  const escolherPasso = (n: number | null) => {
    setSel(null)
    setFerragem(null)
    setModo("drone")
    setExplodir(0)
    setPasso(n)
    if (n !== null) setAba("montagem")
  }

  return (
    <div
      className="dark flex h-svh w-full flex-col overflow-hidden bg-[#0c1016] text-hud"
      data-testid="pagina-pecas"
    >
      <header className="flex min-h-12 shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-b border-white/10 px-4 py-2">
        <a
          href="/"
          className={`${FOCO} inline-flex items-center gap-1.5 rounded text-[0.8rem] text-hud-ciano hover:underline`}
        >
          <ArrowLeft className="size-4" /> cockpit
        </a>
        <h1 className="text-[0.95rem] font-bold tracking-wide">
          Peças 3D e montagem
        </h1>
        {dados && (
          <span
            className="font-mono text-[0.72rem] text-muted-foreground"
            data-testid="resumo-build"
          >
            {dados.build} · {num(dados.massa_total_g, 0)} g ·{" "}
            {Object.keys(dados.pecas).length} peças · {totalFerragens} ferragens
            · {num(dados.estatisticas.triangulos / 1000, 0)} mil triângulos
          </span>
        )}
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <aside className="order-2 flex h-[46svh] min-h-0 shrink-0 flex-col border-t border-white/10 lg:order-1 lg:h-auto lg:w-[24rem] lg:border-t-0 lg:border-r">
          <nav
            className="flex shrink-0 gap-1 border-b border-white/10 px-3 py-2"
            aria-label="Secções"
          >
            {(
              [
                ["pecas", "Peças"],
                ["montagem", "Montagem"],
                ["ferragens", "Ferragens"],
                ["custos", "Imprimir e custos"],
              ] as const
            ).map(([id, nome]) => (
              <Botao
                key={id}
                ativo={aba === id}
                onClick={() => {
                  setAba(id)
                  if (id !== "montagem") setPasso(null) // fora da montagem vê-se o drone completo
                }}
                testid={`aba-${id}`}
              >
                {nome}
              </Botao>
            ))}
          </nav>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
            {!dados && !erro && (
              <p className="flex items-center gap-2 text-[0.8rem] text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> a gerar o drone a
                partir do simulador…
              </p>
            )}
            {erro && (
              <div
                className="flex flex-col gap-2 text-[0.8rem]"
                data-testid="erro-pecas"
              >
                <p className="text-hud-vermelho">
                  Não consegui ler as peças: {erro}
                </p>
                <p className="text-muted-foreground">
                  A página lê <code>/api/pecas3d</code> do servidor do cockpit (
                  <code>sim_site.py</code>). Arranque-o e recarregue.
                </p>
              </div>
            )}
            {dados && aba === "pecas" && sel && dados.pecas[sel.peca] && (
              <FichaDaPeca
                dados={dados}
                id={sel.peca}
                ficha={dados.pecas[sel.peca]}
                inst={sel.inst}
                onInst={(i) => setSel({ peca: sel.peca, inst: i })}
                onPasso={(n) => escolherPasso(n)}
                onFechar={() => {
                  setSel(null)
                  setModo("drone")
                }}
                modo={modo}
                onModo={setModo}
              />
            )}
            {dados && aba === "pecas" && !(sel && dados.pecas[sel.peca]) && (
              <div className="flex flex-col gap-4" data-testid="lista-pecas">
                <p className="text-[0.76rem] leading-relaxed text-muted-foreground">
                  Clique numa peça (aqui ou no 3D) para a ver sozinha, com as
                  medidas reais, como funciona e as ferragens que a prendem.
                </p>
                {porCategoria.map((c) => (
                  <section key={c.id} className="flex flex-col gap-1">
                    <Etiqueta>{c.nome}</Etiqueta>
                    <ul className="flex flex-col">
                      {c.pecas.map(([id, f]) => (
                        <li key={id}>
                          <button
                            type="button"
                            data-testid={`peca-${id}`}
                            onClick={() => {
                              setPasso(null)
                              setFerragem(null)
                              setSel({ peca: id, inst: null })
                            }}
                            className={`${FOCO} flex w-full items-baseline justify-between gap-3 rounded px-1.5 py-1.5 text-left text-[0.8rem] hover:bg-white/[0.06]`}
                          >
                            <span className="text-hud">{f.nome}</span>
                            {(f.quantidade ?? 1) > 1 && (
                              <span className="font-mono text-[0.72rem] text-muted-foreground">
                                ×{f.quantidade}
                              </span>
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
            )}
            {dados && aba === "montagem" && (
              <div className="flex flex-col gap-3" data-testid="montagem">
                {passoAtual ? (
                  <div
                    className="flex flex-col gap-3"
                    data-testid="passo-atual"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <Etiqueta>
                        passo {passoAtual.n} de {dados.passos.length}
                      </Etiqueta>
                      <div className="flex gap-1">
                        <Botao
                          onClick={() =>
                            escolherPasso(Math.max(1, passoAtual.n - 1))
                          }
                          desativado={passoAtual.n <= 1}
                          titulo="Passo anterior"
                        >
                          <ChevronLeft className="size-3.5" />
                        </Botao>
                        <Botao
                          onClick={() =>
                            escolherPasso(
                              Math.min(dados.passos.length, passoAtual.n + 1)
                            )
                          }
                          desativado={passoAtual.n >= dados.passos.length}
                          titulo="Passo seguinte"
                          testid="passo-seguinte"
                        >
                          <ChevronRight className="size-3.5" />
                        </Botao>
                      </div>
                    </div>
                    <h2 className="text-[1rem] font-bold text-hud">
                      {passoAtual.titulo}
                    </h2>
                    <p className="text-[0.8rem] leading-relaxed text-hud/90">
                      {passoAtual.texto}
                    </p>
                    <section className="flex flex-col gap-1">
                      <Etiqueta>peças deste passo (em destaque)</Etiqueta>
                      <ul className="flex flex-wrap gap-1.5">
                        {passoAtual.pecas.map((id) => (
                          <li key={id}>
                            <Botao
                              onClick={() => {
                                setPasso(null)
                                setSel({ peca: id, inst: null })
                                setAba("pecas")
                              }}
                            >
                              {dados.pecas[id]?.nome ?? id}
                            </Botao>
                          </li>
                        ))}
                      </ul>
                    </section>
                    {passoAtual.ferragens.length > 0 && (
                      <section className="flex flex-col gap-1">
                        <Etiqueta>ferragens do passo</Etiqueta>
                        <table className="w-full text-[0.75rem]">
                          <thead>
                            <tr className="text-muted-foreground">
                              <th className="py-1 text-left font-normal">
                                peça
                              </th>
                              <th className="py-1 text-right font-normal">
                                qtd.
                              </th>
                              <th className="py-1 pl-2 text-right font-normal">
                                aperto
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {passoAtual.ferragens.map((f) => (
                              <tr
                                key={f.tipo}
                                className="border-t border-white/8"
                              >
                                <td className="py-1 pr-2 text-hud/90">
                                  {f.descricao}
                                </td>
                                <td className="py-1 text-right font-mono text-hud">
                                  {f.qtd}
                                </td>
                                <td className="py-1 pl-2 text-right font-mono text-hud">
                                  {f.binario_nm
                                    ? `${num(f.binario_nm, 2)} N·m`
                                    : "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </section>
                    )}
                    <Botao onClick={() => escolherPasso(null)}>
                      ver o drone completo
                    </Botao>
                  </div>
                ) : (
                  <p className="text-[0.76rem] leading-relaxed text-muted-foreground">
                    A ordem real de uma bancada: cada passo mostra só o que já
                    está montado e destaca o que entra agora, com as ferragens
                    contadas no modelo e o binário de aperto.
                  </p>
                )}
                <ol className="flex flex-col">
                  {dados.passos.map((p) => (
                    <li key={p.id}>
                      <button
                        type="button"
                        data-testid={`passo-${p.n}`}
                        onClick={() => escolherPasso(p.n)}
                        className={`${FOCO} flex w-full items-baseline gap-2.5 rounded px-1.5 py-1.5 text-left text-[0.8rem] hover:bg-white/[0.06] ${
                          passo === p.n
                            ? "bg-hud-ciano/10 text-hud-ciano"
                            : "text-hud"
                        }`}
                      >
                        <span className="w-5 shrink-0 text-right font-mono text-[0.74rem] text-muted-foreground">
                          {p.n}
                        </span>
                        <span>{p.titulo}</span>
                      </button>
                    </li>
                  ))}
                </ol>
              </div>
            )}
            {dados && aba === "custos" && (
              <div className="flex flex-col gap-5" data-testid="custos">
                {dados.custos ? (
                  <section className="flex flex-col gap-1">
                    <Etiqueta>
                      custo de referência do drone ({dados.custos.data})
                    </Etiqueta>
                    <p
                      className="font-mono text-[1rem] font-bold text-hud"
                      data-testid="custo-total"
                    >
                      {preco(dados.custos.total_usd, cambio)}
                    </p>
                    <p className="text-[0.7rem] leading-snug text-muted-foreground">
                      Preços de loja em US$ convertidos a {num(cambio, 2)}{" "}
                      R$/US$ (sem portes nem impostos de importação). As peças
                      impressas custam o ABS que gastam (
                      {num(dados.custos.filamento_usd_kg, 0)} US$/kg):{" "}
                      {num(dados.custos.impressas_g, 0)} g e ~
                      {num(dados.custos.impressas_h, 0)} h de impressão ao todo.
                    </p>
                    <ul className="mt-1 flex flex-col text-[0.76rem]">
                      {Object.entries(dados.custos.por_categoria)
                        .sort((a, b) => b[1] - a[1])
                        .map(([cat, usd]) => (
                          <li
                            key={cat}
                            className="flex justify-between gap-2 border-b border-white/8 py-1 last:border-0"
                          >
                            <span className="text-hud/90">
                              {dados.categorias.find((c) => c.id === cat)
                                ?.nome ?? cat}
                            </span>
                            <span className="font-mono text-hud">
                              {preco(usd, cambio)}
                            </span>
                          </li>
                        ))}
                    </ul>
                  </section>
                ) : (
                  <p className="text-[0.76rem] text-muted-foreground">
                    Este servidor não mandou custos.
                  </p>
                )}
                <section className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <Etiqueta>peças para imprimir em ABS</Etiqueta>
                    {ficheiros.length > 0 && (
                      <LigacaoStl
                        href={urlStl(dados.build)}
                        nome={dados.impressao?.zip ?? "pecas_impressas.zip"}
                        titulo="Todos os STL e o LEIA-ME com as definições de impressão (ZIP)"
                        testid="stl-zip"
                      >
                        <Download className="size-3.5" /> todas (ZIP)
                      </LigacaoStl>
                    )}
                  </div>
                  {ficheiros.length === 0 ? (
                    <p className="text-[0.74rem] text-muted-foreground">
                      Este build não tem peças impressas (é a versão em
                      carbono/alumínio CNC). Abra a página com{" "}
                      <code>?build=articulado_15pol_abs</code> para a versão
                      impressa.
                    </p>
                  ) : (
                    <>
                      {dados.impressao?.definicoes && (
                        <p className="text-[0.7rem] leading-snug text-muted-foreground">
                          {dados.impressao.definicoes}.
                        </p>
                      )}
                      <table
                        className="w-full text-[0.74rem]"
                        data-testid="tabela-impressas"
                      >
                        <thead>
                          <tr className="text-muted-foreground">
                            <th className="py-1 text-left font-normal">peça</th>
                            <th className="py-1 pl-2 text-right font-normal">
                              qtd
                            </th>
                            <th className="py-1 pl-2 text-right font-normal">
                              g/un
                            </th>
                            <th className="py-1 pl-2 text-right font-normal">
                              h/un
                            </th>
                            <th className="py-1 pl-1 text-right font-normal">
                              STL
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {ficheiros.map((f) => (
                            <tr
                              key={f.arquivo}
                              className="border-t border-white/8"
                            >
                              <td className="py-1 pr-1">
                                <button
                                  type="button"
                                  className={`${FOCO} text-left text-hud/90 hover:text-hud-ciano`}
                                  onClick={() => {
                                    setPasso(null)
                                    setFerragem(null)
                                    setSel({ peca: f.rep.peca, inst: null })
                                    setAba("pecas")
                                  }}
                                >
                                  {dados.pecas[f.rep.peca]?.nome ?? f.rep.peca}
                                </button>
                                <span className="block font-mono text-[0.66rem] text-muted-foreground">
                                  {f.arquivo}
                                  {f.rep.dims_mm
                                    ? ` · ${f.rep.dims_mm.map((x) => num(x, 0)).join("×")} mm`
                                    : ""}
                                </span>
                                {avisosImpressao(
                                  f.rep,
                                  dados.impressao?.mesa_mm
                                ).map((a) => (
                                  <span
                                    key={a}
                                    className="block text-[0.66rem] text-hud-ambar"
                                  >
                                    ⚠ {a}
                                  </span>
                                ))}
                              </td>
                              <td className="py-1 pl-2 text-right font-mono text-hud">
                                {f.instancias.length}
                              </td>
                              <td className="py-1 pl-2 text-right font-mono text-hud">
                                {num(f.rep.massa_g, 0)}
                              </td>
                              <td className="py-1 pl-2 text-right font-mono text-hud">
                                {num(f.rep.tempo_h, 1)}
                              </td>
                              <td className="py-1 pl-1 text-right">
                                <LigacaoStl
                                  href={urlStl(dados.build, f.arquivo)}
                                  nome={f.arquivo}
                                  titulo="Descarregar o STL (mm)"
                                  testid={`stl-lista-${f.arquivo}`}
                                >
                                  <Download className="size-3.5" />
                                </LigacaoStl>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </>
                  )}
                </section>
                {dados.custos && (
                  <section className="flex flex-col gap-1">
                    <Etiqueta>custo por peça (todas as unidades)</Etiqueta>
                    <ul
                      className="flex flex-col text-[0.75rem]"
                      data-testid="custo-por-peca"
                    >
                      {Object.entries(dados.custos.por_peca)
                        .filter(([pid]) => dados.pecas[pid])
                        .sort((a, b) => b[1].total_usd - a[1].total_usd)
                        .map(([pid, c]) => (
                          <li
                            key={pid}
                            className="flex justify-between gap-2 border-b border-white/8 py-1 last:border-0"
                          >
                            <button
                              type="button"
                              className={`${FOCO} text-left text-hud/90 hover:text-hud-ciano`}
                              onClick={() => {
                                setPasso(null)
                                setFerragem(null)
                                setSel({ peca: pid, inst: null })
                                setAba("pecas")
                              }}
                            >
                              {dados.pecas[pid].nome}
                            </button>
                            <span className="shrink-0 font-mono text-hud">
                              {preco(c.total_usd, cambio)}
                            </span>
                          </li>
                        ))}
                    </ul>
                  </section>
                )}
              </div>
            )}
            {dados && aba === "ferragens" && (
              <div className="flex flex-col gap-3" data-testid="ferragens">
                <p className="text-[0.76rem] leading-relaxed text-muted-foreground">
                  {totalFerragens} ferragens no modelo, com a geometria das
                  normas (ISO 4762, ISO 7380, ISO 4032, ISO 10511, ISO 7089, DIN
                  6799, DIN 916). Clique num tipo para o ver inteiro; «no drone»
                  mostra onde estão.
                </p>
                {ferragem && (
                  <div className="flex flex-wrap gap-1.5">
                    <Botao
                      onClick={() => {
                        const t = ferragem
                        setFerragem(null)
                        setSel(null)
                        setModo("drone")
                        setTimeout(() => visor.current?.destacarFerragem(t), 0)
                      }}
                    >
                      <Layers className="size-3.5" /> no drone
                    </Botao>
                    <Botao
                      onClick={() => {
                        setFerragem(null)
                        visor.current?.destacarFerragem(null)
                      }}
                    >
                      fechar
                    </Botao>
                  </div>
                )}
                <table className="w-full text-[0.75rem]">
                  <thead>
                    <tr className="text-muted-foreground">
                      <th className="py-1 text-left font-normal">ferragem</th>
                      <th className="py-1 text-right font-normal">qtd.</th>
                      <th className="py-1 pl-2 text-right font-normal">
                        aperto
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {tiposFerragem.map(([ch, t]) => (
                      <tr
                        key={ch}
                        className={`border-t border-white/8 ${ferragem === ch ? "bg-hud-ciano/10" : ""}`}
                      >
                        <td className="py-1 pr-2">
                          <button
                            type="button"
                            className={`${FOCO} text-left text-hud/90 hover:text-hud-ciano disabled:cursor-default disabled:hover:text-hud/90`}
                            disabled={t.malhas.length === 0}
                            onClick={() => {
                              setPasso(null)
                              setFerragem(ch)
                            }}
                          >
                            {t.descricao}
                          </button>
                        </td>
                        <td className="py-1 text-right font-mono text-hud">
                          {t.qtd}
                        </td>
                        <td className="py-1 pl-2 text-right font-mono text-hud">
                          {t.binario_nm ? `${num(t.binario_nm, 2)} N·m` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </aside>

        <main className="relative order-1 min-h-0 flex-1 lg:order-2">
          <div ref={caixa} className="absolute inset-0" />
          {dados && (
            <div className="pointer-events-none absolute inset-x-2 top-2 flex justify-end sm:inset-x-3 sm:top-3">
              <div className="pointer-events-auto flex w-[min(17rem,100%)] flex-col gap-3 rounded-lg border border-white/12 bg-[#0c1016]/80 p-3 backdrop-blur-sm">
                <div className="flex flex-wrap gap-1.5">
                  <Botao
                    ativo={controlos}
                    onClick={() => setControlos((c) => !c)}
                    titulo="Mostrar/esconder os controlos do visor"
                    testid="controlos"
                  >
                    <Settings2 className="size-3.5" /> controlos
                  </Botao>
                  <Botao
                    onClick={() => visor.current?.enquadrar()}
                    titulo="Enquadrar o que se vê"
                  >
                    <Expand className="size-3.5" /> enquadrar
                  </Botao>
                  <Botao
                    ativo={girar}
                    onClick={() => setGirar((g) => !g)}
                    titulo="Hélices a girar (sentido real)"
                    testid="girar"
                  >
                    <RotateCw className="size-3.5" /> hélices
                  </Botao>
                </div>
                {controlos && (
                  <>
                    <Deslizador
                      rotulo="vista explodida"
                      valor={explodir}
                      min={0}
                      max={100}
                      passo={1}
                      unidade="%"
                      onChange={setExplodir}
                      testid="explodir"
                    />
                    {juntas.tem && (
                      <>
                        <Deslizador
                          rotulo="ombros"
                          valor={ombro}
                          min={juntas.lim.ombro[0]}
                          max={juntas.lim.ombro[1]}
                          passo={1}
                          unidade="°"
                          onChange={(v) => {
                            setExplodir(0)
                            setOmbro(v)
                          }}
                          testid="ombro"
                        />
                        <Deslizador
                          rotulo="cotovelos"
                          valor={cotovelo}
                          min={juntas.lim.cotovelo[0]}
                          max={juntas.lim.cotovelo[1]}
                          passo={1}
                          unidade="°"
                          onChange={(v) => {
                            setExplodir(0)
                            setCotovelo(v)
                          }}
                          testid="cotovelo"
                        />
                      </>
                    )}
                    <p className="text-[0.66rem] leading-snug text-muted-foreground">
                      arrastar orbita · roda aproxima · clique escolhe uma peça
                      · Esc limpa
                    </p>
                  </>
                )}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
