# Contribuir para o MuJoCo Lab

Obrigado pelo interesse! Este é um laboratório pessoal de experimentos físicos com
**MuJoCo 3.15** (robôs, drones, veículos). Contribuições focadas são bem-vindas.

## Instalar

```bash
bash install.sh          # cria o .venv via uv e instala as dependências
```

Alternativa manual: `uv sync` (Python 3.13+, `.venv` com mujoco 3.15, numpy, scipy,
matplotlib, imageio).

## Validar (obrigatório antes de um PR)

```bash
uv run pytest .agents/mujoco-lab-agent-skill/tests -q        # 30 testes da skill/conhecimento
uv run --group hover-rl python experiments/09_drone_hover_rl/run.py   # 146/146 checagens, exit 0
uv run ruff check .                                          # lint
```

Sempre **sem janelas** (vídeo/CI/agentes): `MUJOCO_GL=egl`. Nunca abrir o `mujoco.viewer`
em validação.

## Convenções

- **Python stdlib onde possível**; dependências novas só se inevitáveis (justificar no PR).
- Grupos `uv`: usar `uv run --group hover-rl` (e `viz`/`urdf`/`rl`/`dmc`/`gpu` conforme o
  tema) em vez de instalar pacotes fora do `uv`.
- **Temporários em `$TMPDIR`** — nunca `/tmp` literal nem ficheiros temporários na raiz.
- **Simulador sempre físico**: tudo passa por `mj_step` (gravidade, contactos, atuadores,
  sensores). Nada de cinemática, teleporte ou "apoios mágicos".
- Comandos: unidades SI, +Z para cima, acesso por nome (`data.body('x').xpos`), não por
  índices crus. Experimentos em `experiments/NN_nome/`, modelos em `models/`, API em `lab/`.
- **Commits em português**, estilo `tipo: resumo` (ex.: `feat: sensores de pé do Spot`,
  `fix: dampratio do contacto da esfera`).

## Memória CoALA (local, não versionada)

O projeto tem memória persistente CoALA/SQLite **local** em `memory/` (motor em
`.agents/mujoco-lab-agent-skill/scripts/coala.py`), **não versionada** — cada clone tem a
sua. Use `coala.py recall`/`add` para conhecimento durável; a base nunca entra no git.
Quem clona sem memória tem todo o conhecimento verificado em
`.agents/mujoco-lab-agent-skill/references/`.

## Segredos — regra absoluta

**Nunca commitar chaves de API ou tokens.** Isto inclui (sem limite a):
`OPENROUTER_API_KEY`, `MOTION_TOKEN`, `TAVILY_API_KEY`/`TAVILY_*`, tokens GitHub
(`ghp_`, `github_pat_`), `UXUI_API_KEY`, passwords e afins.

- Guardar credenciais em `~/.secrets` ou `.env` **fora do git** (`.env`, `*.pem` e
  semelhantes estão no `.gitignore` — não os remova de lá).
- Antes de um PR: `git diff --cached | grep -iE 'key|token|secret'` por via das dúvidas.
- Se uma chave for exposta por acidente: **rodar imediatamente** (revogar/rotar no
  serviço) e avisar o dono do repositório; histórico reescrito não desfaz a exposição.

## Pull Requests

- Descrever **o que muda** e **como foi validado** (comandos e resultados, ex.:
  `pytest … 30 passed`, `run.py … 146/146, exit 0`).
- Mudanças de física devem trazer os valores medidos vs teoria (tabela no README do
  experimento) e registo na memória CoALA.
- PRs pequenos e focados; `main` não recebe commits diretos — ramo efémero → PR.
