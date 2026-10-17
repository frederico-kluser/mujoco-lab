# unity-control-agent-skill

Skill do projeto **mujoco-lab** para o agente de programação **controlar e modificar o Unity 6 em Linux**:
CLI headless, controlo ao vivo (MCP/pontes), mutação segura (Editor scripting + política YAML), validação sem
falsos positivos (gate XML), instalação/licença, builds e guardrails.

- **SKILL.md** — contrato, roteiro e regras de ouro.
- **scripts/unity_agent.sh** — `doctor` · `metodo` · `testar` (gate XML NUnit3) · `build` · `logs`.
- **references/** — 7 referências verificadas (CLI, MCP, Editor scripting, assets/YAML, testes, licença, build,
  guardrails).
- **Base factual**: `pesquisas/2026-10-16-skill-controlo-unity6-linux-agente.md` (pesquisa profunda
  `--deep-research`: 8 frentes em paralelo, 66 fontes, verificação adversarial 3×5). As citações `[S#]` das
  referências apontam para a secção 6 daquele dossiê.

Uso rápido: `bash .agents/unity-control-agent-skill/scripts/unity_agent.sh doctor`
