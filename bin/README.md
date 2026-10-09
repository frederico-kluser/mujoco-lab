# `bin/` — comando `mujoco`

O seletor de experimentos do MuJoCo Lab, para o terminal. Só stdlib do Python 3 (não depende do
`.venv` para nada senão chamar `uv`).

## Instalar (uma vez)

```bash
bash install.sh                # deps + site + symlink ~/.local/bin/mujoco + prova
bash install.sh --so-comando   # só o symlink
bash install.sh --uninstall    # remove só o symlink
```

## Usar

```bash
mujoco                             # seletor interativo: experimento → ação
mujoco 09                          # nome parcial: 09 | drone_hover_rl | 09_drone_hover_rl
mujoco 09 --acao validar           # ação direta, sem perguntas
mujoco drone_hover_rl --acao web   # só a web do 09
mujoco --list                      # tabela: nome, tem site? tem train? tem run.py?
mujoco --versao | mujoco --help
```

Ações (`--acao`): `web` (simulação + web, predefinida com Enter) · `web-so` (só web, sem janela) ·
`janela` (view.py) · `treinar` (train.py) · `validar` (run.py) · `docs` (README/INTERFACE via
`less`/`cat`). Os números do menu são fixos (1–6); ações sem ficheiro no experimento não aparecem e
dão erro claro se escolhidas. Argumentos depois de `--` vão para o script do experimento.

## Como funciona

- Descobre os experimentos pelo glob `experiments/NN_*` (mais recente primeiro) — um experimento novo
  criado com `new_experiment.py --template lab-padrao|front-conexao` aparece sozinho e só oferece as
  ações para as quais tem ficheiros (`sim_site.py`, `view.py`, `train.py`, `run.py`, `README.md`/
  `INTERFACE.md`).
- Corre os scripts com `uv run --group hover-rl python <script>` a partir da raiz do repositório
  (descoberta pelo próprio ficheiro — funciona de qualquer diretório e através do symlink).
- Exit codes: `0` ok · `1` falha de execução **ou o exit code do script do experimento** · `2` uso
  inválido (experimento/ação inexistente) · `130` Ctrl+C (interrompido, limpo).

## Nota para o README raiz (a documentar pela peça do README)

- Instalação: `bash install.sh` (idempotente; `--so-comando`, `--sem-site`, `--uninstall`, `--help`).
- Uso do comando `mujoco` (seletor interativo + atalhos `mujoco 09 --acao …`, `mujoco --list`).
- O comando é só conveniência: os comandos `uv run --group hover-rl python experiments/…` continuam
  a ser a forma canónica de correr cada experimento.
