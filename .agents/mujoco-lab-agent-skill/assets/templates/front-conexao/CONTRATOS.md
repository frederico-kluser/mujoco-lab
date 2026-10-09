# CONTRATOS.md — o que a ponte `front-conexao` promete (e o que o teu projeto tem de dar)

Este bundle é a **ponte entre um simulador e um site**: dois ficheiros JSON e seis rotas de API. Nada aqui
sabe do teu robô — o que ele dá entra pelo **módulo do ambiente** (`env.py` ou outro, `--env-modulo NOME`).
Estes contratos são **literais**: o site, o `deploy.py` e o `dashboard.py` do laboratório dependem deles.

---

## 1. O que o projeto tem de dar (a interface do "lado de lá")

Um módulo Python (por omissão `env.py`, ao lado do `sim_view.py`) que exporte:

| função / atributo | obrigatório | o que é |
|---|---|---|
| `novo_env(**kwargs)` | ✅ (ou a classe `EnvPadrao`) | fábrica do ambiente; recebe `seed=` e devolve um env **Gymnasium** com `reset()` e `step(a)` |
| `acao_para_ctrl(acao)` | ✅ | traduz a ação da política (`[-1,1]^M`) no **comando físico** que vai ao simulador — é o `ctrl` da telemetria |
| `definir_vento(vel, azimute, elevacao)` | ✅ | escreve o vento BASE (perturbação) na física, em unidades SI e ângulos em **graus** |
| `vento_polar()` | ✅ | devolve `(velocidade m/s, azimute °)` do vento em vigor |
| `vento_vec` | ➖ desejável | vector `(vx,vy,vz)` m/s do vento em vigor → aparece em `vento_vec` (a rosa dos ventos usa-o); sem ele deriva-se do polar |
| `vento_modo` | ➖ desejável | modo dinâmico em vigor (`"nenhum"`, `"rajadas"`, …) |
| `definir_vento_dinamico(cfg)` | ➖ opcional | liga/desliga a dinâmica a quente (`{"modo": "rajadas", "p": …, "u_max": …}`); **sem ela** os botões de vento dinâmico ficam inertes e o runner avisa uma vez |
| `valida_vento_dinamico(cfg)` | ➖ opcional | valida/normaliza a config do vento dinâmico; sem ela o `sim_site.py` valida estruturalmente |
| `theta`, `erro`, `omega` | ➖ desejável | as 3 métricas do painel — em `info` do `step` (preferido) ou como atributos; em falta valem `0.0` |
| `.model`, `.data`, `.passos` | ➖ desejável | o `sim_view.py` abre o viewer com `env.model`/`env.data` e publica `env.passos` (com fallback) |

Regras do laboratório que o env tem de respeitar: **simulador sempre físico** (tudo passa por `mj_step`; a
perturbação entra como força externa real, nada de teleporte/cinemática) e **sem janelas** nos scripts que não
são o runner (`MUJOCO_GL=egl` fixado pelo `lab/mjkit.py` antes de `import mujoco`).

---

## 2. Ficheiro de CONTROLO — `out/controle_vento.json` (o site escreve, o runner lê)

```json
{
  "vel": 3.5, "azimute": 135.0, "elevacao": 0.0, "ativo": true,
  "reiniciar": 4, "loop": false, "t": 1760000000.123,
  "dinamico": {"modo": "rajadas", "params": {"p": 0.02, "duracao": 10, "u_max": 3.0},
               "ativo": true, "seq": 7}
}
```

| campo | faixa / tipo | significado |
|---|---|---|
| `vel` | `[0, 5]` m/s | vento BASE (perturbação). `ativo: false` → ar parado |
| `azimute` | `[0, 360)` ° | direção no plano: 0° = +x = E, 90° = +y = N (anti-horário) |
| `elevacao` | `[−90, 90]` ° | componente vertical (positivo = vento a subir) |
| `ativo` | bool | `false` desliga o vento base (o dinâmico também fica inerte) |
| `reiniciar` | inteiro ≥ 0 | **CONTADOR**: qualquer valor novo = um pedido de REINICIAR (o runner compara com o último visto) |
| `loop` | bool | `true` liga o auto-reset no fim do episódio (o normal é `false`) |
| `dinamico` | objeto | vento ao vivo: `modo` ∈ `nenhum \| rajadas \| frente \| dryden \| rajada_agora`, `params`, `ativo`, `seq` |

**Escrita ATÓMICA obrigatória** (`tmp` no mesmo diretório + `os.replace`): o runner lê o ficheiro a CADA passo
de decisão (vigia `mtime_ns` + tamanho) e nunca pode apanhá-lo a meio. O bloco `dinamico` só atua quando a sua
**assinatura** (`modo`+`params`+`ativo`+`seq`) muda — é o `seq` que permite disparar duas rajadas iguais
seguidas. Nenhum controlo reinicia o episódio: `/api/reiniciar` é o único caminho e o `reset()` é explícito.

---

## 3. TELEMETRIA — `out/sim_telemetria.jsonl` (o runner escreve, o site lê)

1 linha JSON por amostra, **15 + 2 chaves, POR ESTA ORDEM**:

```
t, estado, ep, passo, retorno, theta, erro, omega, vento_vel, vento_azim,
vento_vec[], vento_modo, obs[], act[], ctrl[], h1[], h2[]
```

| chave | o que é |
|---|---|
| `t` | tempo de **simulação** do episódio (s); volta a 0 em cada reset |
| `estado` | `"a_correr"` \| `"pausado"` \| `"episodio_terminado"` |
| `ep`, `passo` | nº do episódio e passos de decisão já publicados |
| `retorno` | retorno acumulado do episódio |
| `theta`, `erro`, `omega` | as 3 métricas do painel (o site converte para as unidades de `lib/config.ts`) |
| `vento_vel`, `vento_azim` | norma (m/s) e azimute (°) do vento em vigor |
| `vento_vec` | vector `[vx, vy, vz]` (m/s) do vento que a FÍSICA leva (base + dinâmica) |
| `vento_modo` | modo dinâmico em vigor (`"nenhum"` quando não há) |
| `obs[]` | observação normalizada que a política viu (N entradas — o site desenha as que vierem) |
| `act[]` | ação da política (`[-1,1]^M`) |
| `ctrl[]` | comando FÍSICO aplicado (`acao_para_ctrl(act)`) |
| `h1[]`, `h2[]` | ativações das duas camadas escondidas da MLP (vazio sem política) |

**Cadência**: **0,1 s de tempo SIMULADO** a correr (determinística: o mesmo rollout dá sempre o mesmo
ficheiro, corra a 1× ou sem travão) e **1 Hz de tempo de PAREDE** com o episódio parado (prova de vida).
Cada linha é escrita com `flush`; os eventos (arranque, reinício, fim de episódio) escrevem logo, sem esperar.

**Invariante**: nas linhas com ação aplicada (`passo > 0`) vale `ctrl == acao_para_ctrl(act)`. Nas linhas de
arranque/reinício (`passo == 0`) vale `act == ctrl == []` — é "nenhuma ação", não um comando inventado.

---

## 4. API — 6 rotas (`sim_site.py`, mesmo porto do site, só stdlib)

| rota | pedido | resposta |
|---|---|---|
| `GET /api/sim` | — | `{estado, ep, passo, retorno, vento:{vel,azimute,elevacao,ativo,vec,modo}, vento_dinamico:{modo,params,ativo}, vento_atual:{vec,vel,azimute,elevacao,modo,fonte}, rpi5:{…}, linhas:[…], modelo_nome, sim_vivo, loop}` |
| `GET /api/state` | — | o mesmo **sem** `linhas`, mais `contador_reiniciar`, `n_linhas`, `modelo`, `modelo_motivo`, `pid`, `porta`, `idade_telemetria_s` e o painel `rpi5` completo |
| `POST /api/vento` | `{vel?, azimute?, elevacao?, ativo?}` | 200 · **400** fora da faixa (o corpo é mesclado com o controlo em vigor) |
| `POST /api/vento-dinamico` | `{modo, params?, ativo?}` | 200 · **400** em modo/params inválidos — **nunca** reinicia o episódio |
| `POST /api/reiniciar` | — | `{contador: n}` (incrementa o contador do controlo) |
| `POST /api/loop` | `{ativo: bool}` | `{loop: bool}` |

Estados honestos: **400** (valor/faixa/tipo inválido) · **404** (rota, asset ou path traversal) · **500**.
Sem websockets: o site faz polling a `GET /api/sim` a ~2,9 Hz (350 ms). Quando não há dados, o site mostra
«—» — **nunca** números inventados.

Detalhe do `POST /api/vento-dinamico` (os formatos são contrato):

* `rajadas` → `{"p": 0.02, "duracao": 10, "u_max": 3.0}` — rajadas com envelope `sin(π·k/(N+1))` que **somam**
  ao vento base; `dryden` → `{"sigma": 0.5, "L": 10, "v_min": 1.0}` — turbulência OU de 1.ª ordem saturada em
  norma a `u_max`. Ambos validados pelo `valida_vento_dinamico` do projeto (ou estruturalmente);
  `u_max = 0` é um modo **inerte**;
* `frente` aceita **dois** formatos: `{"vel", "azimute", "elevacao"}` = **degrau imediato** do vento base (o
  que o site manda quando mexes nos sliders) e `{"u_max", "t_s"}` = degrau em curso do env ao instante `t_s`;
* `rajada_agora` → `{"u", "azimute", "elevacao", "duracao"}` — rajada **dirigida** única, aplicada pelo RUNNER
  sobre o vento base (o env não tem rajadas dirigidas);
* `nenhum` (ou `ativo: false`) desliga a dinâmica e volta ao vento base.

---

## 5. Sem auto-loop (o contrato que mais se esquece)

No fim do episódio (`terminated` OU `truncated`) a física **CONGELA**: não se dá mais nenhum `mj_step` e a
telemetria passa a `episodio_terminado` (batimento de 1 Hz). Só duas coisas recomeçam: o **REINICIAR** do
site (`reiniciar` = contador) ou o **LOOP** ligado — em ambos os casos o `reset()` é explícito. O site NUNCA
reinicia sozinho; o crítico (episódio terminado · API em baixo) fica sempre visível na barra do topo.

---

## 6. Painel do computador de bordo (Raspberry Pi 5) — obrigatório em todos os projetos

O site mostra sempre o painel do **RPi 5**: specs do alvo (BCM2712, 4× Cortex-A76 @ 2,4 GHz, LPDDR4X-4267,
5 V/5 A, *throttle* 80→85 °C), orçamento de **50 Hz = 20 ms**, p50/p99 medidos, fator int8, multi-IA e
semáforo OK/ATENÇÃO/ERRO. Os números vêm do relatório do `deploy.py` (`out/deploy_report.json` ou
`out/deploy/deploy.json`; `--benchmark CAMINHO.json` aponta a outro) — sem relatório diz «sem benchmark» e
**não inventa tempos**. O gargalo a 50 Hz é o **jitter do SO** (≈9,4 ms de pior caso num kernel normal;
≤225 µs com PREEMPT_RT), não a inferência.
