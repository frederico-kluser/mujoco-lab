# `front-conexao` — bundle portátil: front web + códigos de conexão (para colar em qualquer projeto)

Um **painel web completo** (secções Operação · Rede · Vento · Bordo · Tudo, vento dinâmico ao vivo, rosa dos
ventos, painel do Raspberry Pi 5, ajuda «?») e a **ponte de ficheiros** que o alimenta: o runner
(`sim_view.py`) e o servidor de um comando (`sim_site.py`, com API de 6 rotas). Não sabe nada do teu robô — o
que ele dá entra pelo módulo do ambiente (`env.py` ou outro, `--env-modulo NOME`).

```bash
# criar um projeto só com o front + conexão (e depois colar o teu modelo/env)
python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py so_front --template front-conexao
# ou usar o padrão completo do laboratório (env Gymnasium + treino + deploy), que monta este bundle por composição
python3 .agents/mujoco-lab-agent-skill/scripts/new_experiment.py meu_robo --template lab-padrao
```

* **`LEIAME.md`** — como colar num projeto em 4 passos, o que o projeto tem de dar, as SECÇÕES do site (teclas
  1–5, `localStorage`, barra crítica fixa) e a nota do computador de bordo (Raspberry Pi 5).
* **`CONTRATOS.md`** — os contratos **literais**: ficheiro de controlo atómico, telemetria JSONL (15 + 2
  chaves, por ordem), API de 6 rotas, sem auto-loop e painel RPi 5.
* **`site/src/lib/config.ts`** — o ÚNICO ficheiro do front a adaptar a cada projeto (métricas, rótulos,
  unidades). Os componentes e os textos da ajuda leem essa configuração.

O `lab-padrao` (template completo do laboratório) **reutiliza este bundle**: o `new_experiment.py` copia o
bundle e sobrepõe-lhe o overlay do exemplo — assim existe **uma só cópia** do front e dos scripts de conexão.
