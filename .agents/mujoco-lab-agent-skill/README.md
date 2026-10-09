# Skill única do MuJoCo Lab — memória CoALA + controle do MuJoCo

Esta é a **única** skill do projeto: a antiga `.agents/mujoco-agent-skill/` foi **apagada após a unificação**
(2026-10-08; histórico no git). Ela junta duas coisas que já viviam aqui ou foram movidas para cá:

| O que | Onde | Versionado? |
|---|---|---|
| Memória CoALA | `memory/coala.sqlite` (base) · `scripts/coala.py` (motor) · `ingest.json` · `coala.json` | **não** (base + motor são cópia vendorizada de skill privada do autor) |
| `SKILL.md` da skill única | `SKILL.md` | **não** (deriva do template privado; o instalador preserva-o por sha256) |
| Controle/conhecimento do MuJoCo | `references/*.md` (16) · `scripts/*.py` (9) · `assets/templates/` · `tests/` | **sim** |

Entrada para agentes: [`SKILL.md`](SKILL.md) (memória primeiro, MuJoCo depois). Caminhos canónicos:

```bash
uv run pytest .agents/mujoco-lab-agent-skill/tests -q                     # suíte da skill (29 testes)
python3 .agents/mujoco-lab-agent-skill/scripts/coala.py recall "<tarefa>" --budget 1500
python3 .agents/mujoco-lab-agent-skill/scripts/coala.py doctor            # SAUDÁVEL
```

Para recriar a memória em outra máquina:

1. instale a skill `coala-agent-skill` (que cria `.agents/<projeto>-agent-skill/` com o motor, o schema e o banco);
2. copie este `ingest.json` por cima do gerado pelo instalador;
3. `python3 .agents/mujoco-lab-agent-skill/scripts/coala.py ingest` e depois `... doctor`.

Sem a memória, nada quebra: todo o conhecimento verificado está versionado em [`references/`](references/) e em
[`../../pesquisas/`](../../pesquisas/). O material do projeto é ingerido pelo symlink `docs/skill`
(→ `.agents/mujoco-lab-agent-skill/`; o motor exclui `.agents/**` por padrão).

> **Reinstalar a memória**: use `coala-install.py install` **sem `--force`**. O `SKILL.md`, o `ingest.json` e o
> resto da skill são ficheiros personalizados; o instalador preserva qualquer ficheiro cujo sha256 não bate com
> o que ele escreveu (relata `conflito (personalizado, preservado)`). `--force` substituiria o `SKILL.md` único
> pelo template da memória.
