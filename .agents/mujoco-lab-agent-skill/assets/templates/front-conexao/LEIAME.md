# LEIAME.md — `{{NOME_EXPERIMENTO}}`: o bundle `front-conexao` (front + códigos de conexão)

Esta pasta é **portátil**: serve para colar um painel web completo + a ponte de ficheiros num projeto
**qualquer** (não precisa de ser MuJoCo, nem do laboratório). O que ela traz:

```
site/            front React completo (secções, curvas, rede, vento dinâmico, painel RPi 5, ajuda «?»)
sim_view.py      RUNNER: janela MuJoCo limpa (opcional) + telemetria JSONL + leitura do controlo
sim_site.py      SERVIDOR: UM comando = runner + site (site/dist/) + API de 6 rotas
CONTRATOS.md     os contratos LITERAIS: ficheiro de controlo, telemetria 15+2 chaves e API de 6 rotas
LEIAME.md        este guia (o que o teu projeto tem de dar e como ligar)
```

Criado do template com:

```bash
python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py <nome> --template front-conexao
```

---

## 1. Como colar isto num projeto (4 passos)

```bash
# 1) COPIAR a pasta para o projeto (ou usar o `new_experiment.py --template front-conexao`)
cp -r assets/templates/front-conexao/{site,sim_view.py,sim_site.py,CONTRATOS.md} <projeto>/

# 2) SUBSTITUIR os marcadores de nome (os MESMOS do `lab-padrao`, com chaves duplas à volta):
#    NOME_EXPERIMENTO → nome curto do projeto   ·   NOME_PACOTE → nome do pacote do site
#    (o `new_experiment.py` já o faz; numa cópia manual, procura os dois marcadores e troca-os)
grep -rl "NOME_EXPERIMENTO\|NOME_PACOTE" <projeto> | xargs sed -i \
  -e 's/NOME_EXPERIMENTO/meu_projeto/g' -e 's/NOME_PACOTE/meu-projeto-site/g'

# 3) LIGAR o contrato: escrever o módulo do ambiente (env.py ou outro) com a interface do §2
#    e ajustar o rótulo/unidades das métricas em site/src/lib/config.ts

# 4) BUILDAR o site (uma vez) e arrancar TUDO com um comando
cd <projeto>/site && node ensure-setup.mjs && npm run build && cd ..
python3 <projeto>/sim_site.py            # janela limpa + site em http://127.0.0.1:8080
```

Sem janela (agentes/CI): `python3 sim_site.py --sem-janela --sem-browser --port 0`. O runner sozinho:
`python3 sim_view.py --sem-janela --max-segundos 3`.

---

## 2. O que o teu projeto tem de dar (curto — o resto está no `CONTRATOS.md`)

Um módulo Python (por omissão `env.py`, ao lado do `sim_view.py`; `--env-modulo NOME` escolhe outro):

```python
def novo_env(**kwargs): ...            # fábrica do ambiente (Gymnasium): reset() + step(a)   [obrigatório]
def acao_para_ctrl(acao): ...          # ação da política → comando FÍSICO (o `ctrl` da telemetria)
def definir_vento(vel, azimute, elevacao): ...   # perturbação em SI, ângulos em graus
def vento_polar(): ...                 # (velocidade m/s, azimute °)
vento_vec = (vx, vy, vz)               # opcional (a rosa dos ventos usa-o)
def definir_vento_dinamico(cfg): ...   # opcional (sem ela os modos dinâmicos ficam inertes e avisa uma vez)
def valida_vento_dinamico(cfg): ...    # opcional (sem ela a API valida estruturalmente)
theta, erro, omega                     # as 3 métricas do painel (em `info` do step, de preferência)
```

Nada disto é MuJoCo-específico: o runner só chama estas funções e escreve os dois ficheiros do contrato. Se o
teu simulador for outro (PyBullet, Gazebo, um processo remoto), basta que o módulo cumpra a interface.

**Adaptação do front**: o ÚNICO ficheiro a mexer é `site/src/lib/config.ts` (`METRICAS`, `ROTULOS_OBS`,
`ROTULOS_ACT`, `UNIDADE_CTRL`, `ROTULO_CTRL`, `NOME_EXPERIMENTO`, `VENTO_LIMITES`). Os componentes, as secções
e a ajuda «?» leem essa configuração — os textos da ajuda acompanham-na automaticamente.

---

## 3. O site: SECÇÕES (UX)

O painel organiza-se em **5 secções escolhíveis** com o seletor no topo — o dono pediu «não quero ver tudo ao
mesmo tempo, escolho o que ver para melhorar a monitoria enquanto o robô opera»:

| secção | tecla | o que mostra |
|---|---|---|
| **Operação** | `1` | cabeçalho (estado, política), **valores atuais** das 4 métricas e as **curvas grandes** |
| **Rede** | `2` | a política a decidir: rede (ativações por camada), observação e ação |
| **Vento** | `3` | sliders do vento, **rosa dos ventos viva** e o **vento dinâmico** (rajadas · Dryden · frente · rajada) |
| **Bordo** | `4` | o **computador de bordo** (Raspberry Pi 5): latências vs orçamento de 20 ms, semáforo, specs |
| **Tudo** | `5` | o layout completo (todas as secções de uma vez), como no painel original |

* **Persistência**: a secção ativa fica no `localStorage` (`{{NOME_EXPERIMENTO}}:seccao`) e volta a ser a mesma
  quando reabres a página; sem storage (modo privado) a escolha vive na sessão.
* **Atalhos `1`–`5`**: as setas do teclado percorrem as abas; os atalhos não disparam com Ctrl/Alt/Meta, nem
  enquanto escreves num campo, nem com o rato/foco **sobre um slider** (guarda com `pointerover`+`pointerdown`:
  as teclas 1–5 continuam a escrever números e um arrasto de slider não salta de secção).
* **Esconder ≠ desmontar**: cada bloco esconde-se com o atributo `hidden` (regra `[data-seccao][hidden]` no
  `index.css`), portanto os widgets **continuam a atualizar** com a secção escondida e voltam com valores
  frescos — a rede e as curvas não «recomeçam» quando trocas de aba.
* **Barra crítica fixa**: o seletor, o **REINICIAR/LOOP** e a faixa de estado (episódio terminado · API em
  baixo · LOOP ligado) estão numa barra `sticky` e vêem-se em QUALQUER secção — um aviso crítico nunca se
  esconde numa aba que não estás a ver.

O resto do front é o padrão: uma página, sem navegação, polling `GET /api/sim` a ~2,9 Hz (sem websockets),
estados honestos («—» quando não há dados, 400/404/500 da API) e **nenhum auto-restart** — o REINICIAR (manter
1 s) é o único caminho e o `reset()` é sempre explícito no backend.

---

## 4. Computador de bordo: Raspberry Pi 5 (obrigatório em todos os projetos)

Todos estes projetos correm num **Raspberry Pi 5** a bordo, e o painel mostra-o sempre:

| grandeza | valor |
|---|---|
| CPU | 4× **Cortex-A76 @ 2,4 GHz** (512 kB de L2 por núcleo + 2 MB de L3) |
| SoC / RAM | **BCM2712** · **LPDDR4X-4267** (1–16 GB conforme a variante) |
| Alimentação / térmico | **5 V / 5 A** (27 W) · *throttle* aos **80 → 85 °C** |
| Orçamento de decisão | **50 Hz = 20 ms** por passo |

**A lição (medida): o gargalo é o JITTER DO SO, não a inferência.** Num kernel normal o pior caso de
escalonamento é da ordem de **9,4 ms** (metade do período de 20 ms); com **PREEMPT_RT** desce a **≤225 µs**.
Uma MLP pequena custa **~5 µs** de p50 (medido com o `deploy.py`; no x86 o int8 chegou a ser **mais lento** —
só compensa com SDOT, 1,83× no A76). Por isso o painel mostra **p99/pior caso** e um semáforo
OK/ATENÇÃO/ERRO, não a média.

Os números do painel vêm do relatório do `deploy.py` (formato do laboratório; `--benchmark CAMINHO.json`
aponta a outro). Num projeto que não use o `deploy.py`, basta escrever um JSON com esse formato — ou deixar
«sem benchmark», que é honesto e não inventa tempos. A imagem da placa é uma **ilustração de referência**
(Raspberry Pi Model B+ de 2014, Lucasbosch/Wikimedia Commons, **CC BY-SA 3.0**), com a atribuição à vista.

---

## 5. Ficheiros, limites e armadilhas

| ficheiro | o que é |
|---|---|
| `sim_view.py` | runner: importa o módulo do projeto **dentro do `main()`** (o `--help` funciona sem `env.py`), lê o controlo a cada passo de decisão, escreve a telemetria e (se não for `--sem-janela`) abre a janela 100 % limpa |
| `sim_site.py` | servidor: arranca o runner como subprocesso, serve `site/dist/` + a API de 6 rotas, monta o painel RPi 5, imprime o URL e abre o browser (`--sem-browser` desliga) |
| `site/` | front React/TypeScript (motion-plus-ui): `src/lib/config.ts` é a ★ configuração; `src/components/sim/**` é o padrão |
| `CONTRATOS.md` | os contratos literais (§2 controlo, §3 telemetria, §4 API, §5 sem auto-loop, §6 RPi 5) |

Limites conhecidos: o runner é **um** por servidor (`sim_site.py` arranca-o e mata-o ao fechar); o site faz
polling (2–5 Hz é o contrato — não abuses); a telemetria é um JSONL append (trunca com
`sim_view.py --truncar-telemetria`); os modos dinâmicos só existem se o projeto os implementar.

Referência viva do bundle já ligado a um robô: `assets/templates/lab-padrao` (haste com alvo de ângulo) e o
experimento completo `experiments/09_drone_hover_rl`.
