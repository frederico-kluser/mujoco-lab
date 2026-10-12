/**
 * config.ts — ★ CONFIGURAÇÃO do exemplo do `lab-padrao` (haste com alvo de ângulo).
 *
 * O FRONT vive no bundle `assets/templates/front-conexao/site/` (uma só cópia, partilhada por todos os
 * projetos); este ficheiro é o OVERLAY do exemplo: o `new_experiment.py` copia o bundle e por cima este
 * `site/src/lib/config.ts`, que é o ÚNICO ficheiro do site que muda de projeto para projeto.
 *
 * Ao adaptar ao TEU robô: troca rótulos/unidades/casas das `METRICAS`, os `ROTULOS_OBS`/`ROTULOS_ACT`, o
 * `UNIDADE_CTRL` e o `NOME_EXPERIMENTO`. As CHAVES (`theta`, `erro`, `omega`, `vento_vel`) são do contrato da
 * telemetria (ver `CONTRATOS.md` do bundle) e não se mudam.
 */

// ─────────────────────────────────────────────────────────────────────────── CONFIGURAÇÃO (ADAPTAR)
/** Uma curva/painel do site: chave na telemetria → rótulo, unidade, cor e casas decimais. */
export interface Metrica {
  chave: "theta" | "erro" | "omega" | "vento_vel"
  rotulo: string
  curta: string
  unidade: string
  cor: string
  casas: number
  /** Linha de referência (2 pontos, desenhada no sparkline): `true` = usa o alvo do alvo do episódio. */
  referencia?: "alvo" | "zero"
}

/**
 * As 4 curvas do painel. Ao copiar o template para outro robô: troca `chave` pelas tuas 3–4 grandezas
 * (o `sim_view.py` publica-as em `amostra()`) e ajusta rótulo/unidade/casas.
 */
export const METRICAS: Metrica[] = [
  { chave: "theta", rotulo: "θ — ângulo da haste", curta: "θ", unidade: "°", cor: "#ffa24a", casas: 2, referencia: "alvo" },
  { chave: "erro", rotulo: "erro em relação ao alvo", curta: "erro", unidade: "°", cor: "#7dd3fc", casas: 2, referencia: "zero" },
  { chave: "omega", rotulo: "θ̇ — velocidade angular", curta: "θ̇", unidade: "°/s", cor: "#c4b5fd", casas: 1, referencia: "zero" },
  { chave: "vento_vel", rotulo: "vento (perturbação) em vigor", curta: "vento", unidade: "m/s", cor: "#86efac", casas: 2 },
]

/** Rótulo de cada entrada da observação (o nº real vem da telemetria; o que faltar cai em `obs[i]`). */
export const ROTULOS_OBS: string[] = ["cos θ", "sin θ", "θ̇/10", "erro/π"]
/** Rótulo de cada saída da ação (idem: o que faltar cai em `act[i]`). */
export const ROTULOS_ACT: string[] = ["Δτ (normalizado)"]
/** Unidade física do comando publicado em `ctrl` (o backend manda o comando REAL aplicado). */
export const UNIDADE_CTRL = "N·m"
/** Rótulo do comando físico (`ctrl`). */
export const ROTULO_CTRL = "τ aplicado"
/** Nome curto do robô/experimento, usado no título. */
export const NOME_EXPERIMENTO = "{{NOME_EXPERIMENTO}}"
/** Limites do vento aceites pela API (têm de bater com o `sim_site.py`). */
export const VENTO_LIMITES = { vel: [0, 5], azimute: [0, 360], elevacao: [-90, 90] } as const
// ─────────────────────────────────────────────────────────────────────── fim da CONFIGURAÇÃO
