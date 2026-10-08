# Memória CoALA local do MuJoCo Lab (não versionada)

Esta pasta guarda só a **configuração** da memória do laboratório: [`ingest.json`](ingest.json) (o que é ingerido, com a proveniência de cada fonte) e [`coala.json`](coala.json) (manifesto).
O banco SQLite (`memory/coala.sqlite`), o motor (`scripts/coala.py`) e o `SKILL.md` da memória **não são publicados**: o motor é uma cópia de uma skill privada do autor.

Para recriar a memória em outra máquina:

1. instale a skill `coala-agent-skill` (que cria `.agents/<projeto>-agent-skill/` com o motor, o schema e o banco);
2. copie este `ingest.json` por cima do gerado pelo instalador;
3. `python3 .agents/mujoco-lab-agent-skill/scripts/coala.py ingest` e depois `... doctor`.

Sem a memória, nada quebra: todo o conhecimento verificado está versionado em [`../mujoco-agent-skill/references/`](../mujoco-agent-skill/references/) e em [`../../pesquisas/`](../../pesquisas/).
A skill de controle do MuJoCo é ingerida pelo symlink `docs/skill` (o motor exclui `.agents/**` por padrão).
