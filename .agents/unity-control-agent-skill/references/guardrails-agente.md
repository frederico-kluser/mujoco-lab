# Guardrails do agente — a prática real (2024–2026)

> Fontes: dossiê [S60]–[S66]. Estes guardrails não são invenção: são o que a comunidade de «agentes a
> programar Unity» aprendeu à força — incluindo o anti-padrão novo («persuasive wrongness»).

## 1. Os 7 guardrails validados pela prática

1. **Git/branch ANTES de mutar; diff como artefato de revisão.**
   «An agent should not overwrite production state while it is still exploring. It should work on a branch,
   commit its changes, and let the product compare that branch to the base» [S60]. Tratar cada commit do agente
   como *untrusted* (hooks locais: secret scan, política de diff) [S60]. A própria Unity seguiu isto (Unity AI
   Beta: Git integrado + diff visual antes de aceitar).
2. **Mutar pelas Editor APIs, não por ficheiros.**
   «Safe mutation is not simply editing YAML. It is using Unity's actual editor APIs so references remain
   valid, Undo works, serialized data stays consistent» [S60] — e «A change that compiles can still be wrong
   because the problem is not compilation, it is integration» [S60]. (Textual só no nível VERDE/AMARELO de
   `assets-yaml-versionamento.md`.)
3. **Limitar o escopo.** Níveis de permissão (o modo Agent oficial: «Read-only / Write scripts only / Full
   autonomy») [S61]; *allowlists* para operações destrutivas; edits pequenos o suficiente para revistar; cena ou
   branch *scratch* antes de tocar conteúdo de produção [S60]. Anti-padrão clássico: pedir a Feature A e o
   agente partir B/C/D («Your Scope is Your Problem»).
4. **Verificar após CADA mutação — *definition of done*.**
   «You treat playmode runs, console inspection, and tests as part of the definition of done, not optional
   niceties» [S60]. Padrão concreto (`unity-agent-bridge`): editar `.cs` → `unity-agent-cli check` → exit 1 com
   o erro exato do compilador → o agente corrige sozinho até exit 0; o backend é desenhado para **sobreviver a
   domain reload falhado** (sintaxe inválida pode rebentar o reload e matar o tooling) [S62].
5. **Estado static/caches do Editor não são confiáveis entre sessões** — ver `editor-scripting.md` §6 (o default
   varia com a versão; escrever para os dois mundos) [S32][S64].
6. **Fronteira de confiança explícita.**
   «The host is probabilistic. The server and Unity are deterministic… **The model proposes. The tools execute.
   The environment returns evidence.** The model updates its plan based on evidence, not vibes» [S60] — IDs de
   correlação e resultados estruturados para auditar/reproduzir *tool calls*.
7. **Governança e trilho de auditoria.** Cada *tool call* rastreável; evidência antes de merge; o agente é «a
   powerful junior engineer who can move quickly, but still must earn trust» [S60]. O modo Plan oficial
   materializa: plano estruturado → aprovação humana → só depois mudanças [S61].

## 2. Anti-padrões (o que correu mal a gente real)

| Anti-padrão | O que faz | Defesa |
|---|---|---|
| **«Persuasive wrongness»** | mudança localmente coerente, globalmente nociva: «It can 'improve' your player controller and quietly destroy game feel. It can adjust physics settings and break determinism» — invisível para o compilador | playtesting/medição humana; testes de comportamento; nunca «compilou = está certo» [S60] |
| Gerar código e rezar | agente assume que funciona até colarem o erro | loop de verificação com exit codes (guardrail 4) [S62] |
| Brute-force em ficheiros | YAML/.meta/GUIDs partidos em silêncio | Editor APIs + política VERDE/AMARELO/VERMELHO [S60] |
| Estado static mutável | handlers duplicados, caches mortos entre Plays | reset explícito; sem singletons estáticos [S32][S64] |
| Atividade ≠ progresso | «Most bad agentic workflows… confuse activity for progress. Verification is how you distinguish the two» | gate por evidência a cada passo [S60] |
| Jogo inteiro num prompt | começar em grande sem superfície de validação | começar *read-only*, workflow «narrow, paranoid», expandir autonomia com confiança [S60] |

## 3. A IA embutida do Unity (o que substitui e o que não)

- **Unity AI** (6.2+): Assistant em modos **Ask** (read-only, contexto vivo do projeto), **Plan** (plano que só
  executa após aprovação) e **Agent** (executa fim-a-fim com níveis de permissão, Undo por passo, assets
  *AI-tagged*); Generators (sprites/texturas/materiais/animação/áudio/UI/3D); MCP Server + AI Gateway [S61][S63].
- **Não substitui**: revisão humana (beta — «features may change, be limited, or be discontinued»), decisões de
  *game feel*/arquitetura, bugs só visíveis em playtesting; a própria Unity manda tratar outputs dos Generators
  como *placeholder* («Credible enough to validate a mechanic, but intended to be replaced before ship») [S63].
  Comunidade: «side-kick and not a replacement» — e reviews independentes dizem «not ready for real work».
- **Não substitui os guardrails**: até a IA oficial tem permissões, Undo, prompt de aprovação e diff antes de
  aceitar [S61].
- **Unity CLI** (jul/2026): `eval` de código via Roslyn sem *domain reload*, agentes «bring your own» —
  superfície nova a acompanhar [S65].

## 4. O que a ciência mede

Existe trabalho académico (2026) que mede erros de compilação de C# Unity gerado por LLM em dezenas de
conceitos jogáveis — a **taxa de erro de compilação é métrica central** em pipelines LLM→Unity [S66]. Por isso
o gate desta skill trata exit 3 («nem compilou») como reprovação com diagnóstico próprio.

## 5. Roteiro de mutação do agente (resumo operacional)

1. `doctor` (ambiente) → 2. branch/git → 3. escolher canal (Editor API vs texto VERDE/AMARELO) →
4. mutação mínima → 5. **verificar** (`testar`/compilação/consola) → 6. repetir 4–5 → 7. diff + evidência no
relatório → 8. `coala.py add` do durável. Nunca saltar o passo 5.
