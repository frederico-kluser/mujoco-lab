# CLI headless do Unity 6 em Linux — receita verificada

> Fontes: dossiê `pesquisas/2026-10-16-skill-controlo-unity6-linux-agente.md` [S1]–[S15].
> Nota de atribuição (verificação adversarial): a tabela de exit codes **0/2/3/4** NÃO está na doc do Test
> Framework — vem de resposta de **staff Unity** no fórum [S5] + `Executer.cs` do pacote; a citação do lock
> após crash é de **fórum** [S7] (que se refere a `Temp/UnityLockFile`); «output logs turned off» aplica-se a
> `-nographics`, não a `-batchmode` em geral.

## 1. Receita canónica

```bash
"$UNITY" -batchmode -nographics -quit \
  -projectPath /caminho/projeto \
  [-buildTarget Linux64] \
  -executeMethod Namespace.Classe.Metodo \
  -logFile -            # '-' = stream para stdout; ficheiro = log completo
```

- `-batchmode`: sem interação; **exceção em script (ou falha de operação) → exit 1** [S1].
- `-nographics`: não inicializa device gráfico (máquinas sem GPU); **sem bake de GI** [S1]; os *output logs*
  ficam desligados **nesta modalidade** — `-logFile` é obrigatório na prática [S1]. Em `-batchmode` puro os
  *log files* CONTÊM o log completo [S1].
- `-quit`: fecha após o método. **NUNCA** combinar com `-runTests` (fecha antes dos testes terminarem) nem com
  código assíncrono pendente (fica pendurado) [S1][S10].
- `-executeMethod <Namespace.Classe.Metodo>`: método **ESTÁTICO** em assembly de Editor; argumentos extra via
  `Environment.GetCommandLineArgs()`; o exit code sai de `EditorApplication.Exit(code)` do próprio método (ou
  1 se exceção não apanhada) [S1][S4].
- `-activeBuildProfile <pathname>`: aplica os *defines* do Build Profile e recompila **antes** do método [S13].
- `-buildTarget`: a única forma de trocar alvo em batch (`SwitchActiveBuildTarget` não funciona; `WaitForEndOfFrame` nunca corre) [S1].

## 2. Exit codes — tabela POR SUPERFÍCIE

| Superfície | Código | Significado | Fonte |
|---|---|---|---|
| Editor `-batchmode` | 1 | exceção/falha de operação em script | doc oficial [S1] |
| Editor `-runTests` | 0 | corrida concluída, todos passaram | **staff Unity no fórum** [S5] |
| Editor `-runTests` | 2 | corrida concluída, testes falharam (mutação quebrou comportamento) | [S5] |
| Editor `-runTests` | 3 | *run error* — sem veredicto (ex.: falha de compilação) | [S5] |
| Editor `-runTests` | 4 | plataforma de testes não instalada | [S5] |
| `unity` CLI | 0 / 1 / 130 (docs) · 0 / 8 / 6 (`unity test`, repo skills) | sucesso / erro / cancelamento — **CONTESTADO**: o repo `Unity-Technologies/skills` documenta 0/8/6 para `unity test` mas as docs do `unity` CLI documentam 0/1/130 → validar localmente; nunca fiar em exit codes | docs `use-unity-cli` vs [S10] |

⚠ A doc do Test Framework diz apenas: «There is currently no common definition for exit codes reported by
individual Unity components under test» [S6] — **o gate fiável é o XML de resultados**, não o exit code.

## 3. Lock de projeto e recuperação pós-crash

- `Temp/UnityLockfile` (referido como `UnityLockFile` no fórum): lock exclusivo por instância; só **uma
  instância** de Editor por projeto (batch não abre projeto já aberto) [S1][S7].
- «In the case of a crash, the lock is never freed» (post de fórum KevinWelton/Unity, 2022 [S7] — **lore
  comunitário**, não doc oficial; a única garantia documentada é «não se abre em batch um projeto que um
  Editor já tem aberto» [S1]) → procedimento:
  1. confirmar que nenhuma instância real corre (`pgrep -a -f "Unity$|UnityShaderCompiler|JobProcess"`);
  2. matar processos zombie (tipicamente `UnityShaderCompiler`/`JobProcess`);
  3. apagar `Temp/UnityLockfile` (ou `Temp/` inteiro — é regenerável); 4. reabrir.
  ⚠ Apagar o lock com um Editor real aberto pode corromper o estado do projeto.

## 4. Logs em Linux

- `~/.config/unity3d/Editor.log` (+ `upm.log`, `Unity.Licensing.Client.log`) [S2].
- Ordem de diagnóstico: `Editor.log` → existência de `Temp/UnityLockfile` → processos Unity/ShaderCompiler →
  exit code + última linha do log («Exiting batchmode successfully now!» / «Application will terminate with
  return code N»).

## 5. Renderização em batch (o que dá e o que não dá)

- **Não há suporte oficial a *rendering* em batchmode** [S9]; `-nographics` não serve para output visual.
- Para output visual em Linux: `xvfb-run -a` **SEM** `-nographics` — workaround oficial do bug
  `XAddExtension`/segfault com cursor personalizado (reproduzido até 6000.6.0a5) [S8].
- GPU NVIDIA em batch (câmaras a produzir frames): Xvfb + NVIDIA Container Toolkit (ex.: base `nvidia/vulkan`),
  `-batchmode` sem `-nographics` — receita **comunitária** (testada em 2019.4; não oficial) [S13].

## 6. Hangs conhecidos e defesa

| Sintoma | Causa reportada | Defesa |
|---|---|---|
| nunca termina após build Android | stall no «cleanup mono» pós-IL2CPP [S15] | timeout no job + `-logFile -` |
| pendura com `-quit -batchmode` | falha de IPC do compilador (`bee_backend`) [S14] | timeout; reprocessar lock |
| pendura com `-quit` + código assíncrono | documentado [S1] | não usar `-quit` com async; preferir `Exit()` |
| testes nunca terminam | `-quit` combinado com `-runTests` [S1][S10] | nunca combinar |

Toda a invocação leva **timeout** (recomendação de CI [S11]; o wrapper `unity_agent.sh` usa `timeout` com
`UNITY_TIMEOUT`, omissão 1800 s).

## 7. Receita CI real (GameCI)

- Imagem `unityci/editor:ubuntu-<versão>-<módulo>-3` (um módulo por imagem; multi-módulo via
  `game-ci build-unity-image --recipe`), execução via `/entrypoint.sh`, workspace `/github/workspace` [S12].
- `unity-builder`: `-nographics` por omissão (`enableGpu: true` omite), `-quit` por omissão (`manualExit`
  suprime e exige `EditorApplication.Exit(0)` no fim do build method), extras via `customParameters` [S4].
- Variáveis de ambiente **não** atravessam o container: só via `GAME_CI_DOCKER_ENV` [S3].
- Segredos (`UNITY_LICENSE`, `UNITY_EMAIL`, `UNITY_PASSWORD`, `UNITY_SERIAL`) nunca em ficheiros versionados.
