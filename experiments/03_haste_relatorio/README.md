# Experimento 03 — o exemplo do relatório (haste articulada + motor), corrigido e validado

O §4.2 do relatório técnico do usuário traz um exemplo de controle (uma haste articulada numa base, acionada por um motor com torque senoidal). Este experimento o **reproduz, corrige e valida**.
O código completo corrigido, com a tabela linha a linha das diferenças, está em `.agents/mujoco-lab-agent-skill/references/relatorio-auditoria.md` (§ "Código do relatório, corrigido").

## O bug do modelo original

`<body name="haste_articulada" pos="0 0.2 0">` com o geom cilíndrico (raio 0,05) faz a haste **penetrar 5 cm na caixa**: como a base está soldada ao mundo (sem junta), o MuJoCo **não** aplica o filtro de colisão pai-filho
(`overview.rst`, «Surprising Collisions»). O contato é permanente e trava a junta: |θ|máx = 0,005 rad mesmo com 15 N·m. Correção: `pos="0 0.26 0"` (ou `<contact><exclude body1="base_robotica" body2="haste_articulada"/></contact>`).

## Rodar

```bash
uv run python experiments/03_haste_relatorio/run.py              # corrigido + contraprova + pêndulo forçado; vídeo/GIF/gráficos em out/
uv run python experiments/03_haste_relatorio/run.py --sem-video  # só números (CI)
uv run python experiments/03_haste_relatorio/view.py             # janela interativa (só a pedido)
```

## Resultados (MuJoCo 3.15.0)

| Checagem | Resultado |
| --- | --- |
| `model.actuator("nome_errado")` | `KeyError` (com `mj_name2id` seria `-1` e `ctrl[-1]` escreveria no último atuador, sem erro) |
| `ctrl` → torque (gear = 1) | `qfrc_actuator = ctrl` (2,5 N·m) após `mj_forward` |
| Modelo **corrigido** | 0 passos com contato haste×caixa; \|θ\|máx = **2,241 rad (128°)** — a haste, invertida (CM 0,40 m acima do pivô; m·g·d = 24,7 N·m > 15 N·m), cai e repousa no chão |
| Modelo **original** (contraprova) | contato em 1201/1201 passos, penetração 50 mm, \|θ\|máx = **0,0051 rad** |
| **Pêndulo forçado** (`model_pendulo.xml`: haste pendurada, amortecimento c = 0,5, pivô a 1 m do chão) | θ(t) do MuJoCo × EDO não linear `I·θ'' + c·θ' + m·g·d·sinθ = T·sin(ωt)` (scipy, rtol 1e-10): RMS = **0,54 mrad** em 10 s; \|θ\|máx 1,069 rad nos dois (I = 1,3443 kg·m², m·g·d = 24,66 N·m, ω_n = 4,28 rad/s) |

Arquivos: `model.xml` (corrigido) · `model_original.xml` (com o bug, só contraprova) · `model_pendulo.xml` (variante estável validada) · `run.py` · `view.py` · `out/` (haste.mp4/gif/sheet, pendulo.mp4/gif/sheet, telemetria.png, resumo.json).

## Lições

- Sempre procure contato entre geoms vizinhos quando uma junta "não se mexe": `data.ncon` e `inspect_model.py` (penetração máxima / contatos) denunciam o problema; o filtro pai-filho só vale com juntas.
- Use acesso por nome (`model.actuator("x")`, `KeyError` explícito) e `actuator_ctrladr` para o slot em `data.ctrl`; `mj_name2id` devolve `-1` sem erro.
- Valide com uma solução independente (aqui, a EDO do pêndulo forçado): `I` e `m·g·d` foram lidos do próprio modelo compilado (`mj_fullM`, `body_mass`, `xipos`).
