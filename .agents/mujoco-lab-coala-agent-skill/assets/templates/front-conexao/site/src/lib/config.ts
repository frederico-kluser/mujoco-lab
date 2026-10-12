/**
 * config.ts — ★ CONFIGURAÇÃO do site (o ÚNICO ficheiro que se adapta a cada robô).
 *
 * O resto do front (`sim.ts` + componentes) é o PADRÃO e não se muda: fala em `METRICAS`, `ROTULOS_OBS`,
 * `ROTULOS_ACT` e `UNIDADE_CTRL`, e desenha N entradas e M saídas conforme a telemetria.
 *
 * O contrato da telemetria fixa as chaves `theta`, `erro`, `omega` e `vento_vel` (15 + 2 chaves, ver
 * `CONTRATOS.md`): os valores por omissão abaixo servem para QUALQUER projeto que cumpra o contrato e
 * ficam legíveis até os trocares pelos rótulos/unidades do teu robô (é o que o `lab-padrao` faz).
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
 * As 4 curvas/painéis do site. ADAPTAR: `rotulo`/`curta`/`unidade`/`casas`/`cor` às grandezas do teu robô
 * (as CHAVES são do contrato da telemetria e não se mudam: `theta`, `erro`, `omega`, `vento_vel`).
 * `referencia: "alvo"` desenha a linha do alvo do episódio (deduzido de `theta − erro`) e `"zero"` a linha
 * do zero. O exemplo preenchido (haste com alvo de ângulo) está em `assets/templates/lab-padrao/site/`.
 */
export const METRICAS: Metrica[] = [
  { chave: "theta", rotulo: "theta — grandeza principal", curta: "theta", unidade: "u", cor: "#ffa24a", casas: 2, referencia: "alvo" },
  { chave: "erro", rotulo: "erro em relação ao alvo", curta: "erro", unidade: "u", cor: "#7dd3fc", casas: 2, referencia: "zero" },
  { chave: "omega", rotulo: "omega — velocidade", curta: "omega", unidade: "u/s", cor: "#c4b5fd", casas: 1, referencia: "zero" },
  { chave: "vento_vel", rotulo: "vento (perturbação) em vigor", curta: "vento", unidade: "m/s", cor: "#86efac", casas: 2 },
]

/** Rótulo de cada entrada da observação (o nº real vem da telemetria; o que faltar cai em `obs[i]`). */
export const ROTULOS_OBS: string[] = ["obs[0]", "obs[1]", "obs[2]", "obs[3]"]
/** Rótulo de cada saída da ação (idem: o que faltar cai em `act[i]`). */
export const ROTULOS_ACT: string[] = ["act[0]"]
/** Unidade física do comando publicado em `ctrl` (`""` = sem unidade; o teu robô põe N·m, N, rad…). */
export const UNIDADE_CTRL = ""
/** Rótulo do comando físico (`ctrl`) que o painel da ação mostra. */
export const ROTULO_CTRL = "comando aplicado"
/** Nome curto do robô/experimento, usado no título. */
export const NOME_EXPERIMENTO = "{{NOME_EXPERIMENTO}}"
/** Limites do vento aceites pela API (têm de bater com o `sim_site.py`). */
export const VENTO_LIMITES = { vel: [0, 5], azimute: [0, 360], elevacao: [-90, 90] } as const
// ─────────────────────────────────────────────────────────────────────── fim da CONFIGURAÇÃO
