# Testes e validação dirigidos pelo agente — sem falsos positivos

> Fontes: dossiê [S41]–[S46] + [S5][S6]. Ciclo obrigatório: **mutar → testar → verificar** — a mutação só está
> feita com evidência (exit code + XML).

## 1. As duas corridas + gate por XML

```bash
# EditMode (unidades rápidas) — SEM -quit (o test runner gere a saída!)
"$UNITY" -batchmode -projectPath <raiz> -runTests -testPlatform editmode \
  -testResults out/editmode-results.xml -logFile out/editmode.log
# PlayMode (runtime/física)
"$UNITY" -batchmode -projectPath <raiz> -runTests -testPlatform playmode \
  -testResults out/playmode-results.xml -logFile out/playmode.log
```

- ⚠ Sem `-testPlatform` os testes correm **só em EditMode** (armadilha de falso positivo) [S41].
- `-testPlatform` aceita `EditMode` | `PlayMode` | qualquer `BuildTarget` (corre num player; `-playerHeartbeatTimeout`, omissão 600 s) [S41].
- Filtros: `testFilter` (nomes `;`, regex, negação `!`, parametrizados `Classe.Metodo(p1,p2)`), `testCategory`
  (com negação), `assemblyNames`; UTF 2.0: `testNames`, `requiresPlayMode`, `assemblyType` [S41].
- `-runSynchronously`: só EditMode; **filtra** `[UnityTest]` multi-frame (outro risco de «0 testes») [S41].

**Gate por XML NUnit3** (raiz `<test-run>`), robusto para além do exit code:

```python
ok = (r.get('result') == 'Passed' and int(r.get('failed', 0)) == 0
      and int(r.get('total', 0)) > 0 and r.get('total') == r.get('testcasecount'))
```

Condições anti-falso-positivo: `total>0` (a mutação não pode fazer testes desaparecerem), `total==testcasecount`
(nenhum filtrado/abortado), `failed==0`, `result=='Passed'`. Listar `message`+`stack-trace` de cada `<failure>`
no relatório [S45]. Atenção: parsers NUnit2 antigos falham no XML do Unity (é NUnit 3) [S45].

## 2. Exit codes (superfície Editor) — atribuição honesta

0=passou · 2=testes falharam · 3=*run error* (ex.: compilação) · 4=plataforma não instalada — **fonte: staff
Unity em fórum (2019/2020) + `Executer.cs` do pacote**, não a doc [S5]. A frase «There is currently no common
definition for exit codes reported by individual **Unity components under test**» [S6][S41] refere-se aos
componentes sob teste, **não** ao exit code do processo do runner (esse é definido) — o gate por XML é
**robustez** (defesa contra variações/versões), não correção de um vazio documental.

## 3. Física determinística em PlayMode

Citações literais de `Physics.Simulate` (6000.6) [S42]:
- «if you pass framerate-dependent step values (such as `Time.deltaTime`) to the physics engine, your
  simulation will be **non-deterministic** because of the unpredictable fluctuations in framerate»;
- «Using step values **greater than 0.03** is likely to produce inaccurate results».

Padrão:

```csharp
[UnityTest] public IEnumerator Queda_deterministica()
{
    var modoAnterior = Physics.simulationMode;
    Physics.simulationMode = SimulationMode.Script;      // controlo manual do passo
    try {
        for (int i = 0; i < 50; i++)
            Physics.Simulate(Time.fixedDeltaTime);       // PASSO FIXO — nunca Time.deltaTime
        Assert.AreNotEqual(y0, go.transform.position.y); // asserts após nº FIXO de passos
    } finally { Physics.simulationMode = modoAnterior; }  // não vazar estado
    yield return null;
}
```

Alternativa com simulação automática: `yield return new WaitForFixedUpdate()` antes das asserções [S46].
`Physics.Simulate` **não** dispara `FixedUpdate` [S42].

## 4. Flakiness — caçar, não mascarar

| Flag | Efeito | Uso |
|---|---|---|
| `-repeat N` | repete os que passam até falharem | **caçar** flakes e reportar o teste instável |
| `-randomOrderSeed <n>` | ordem aleatória reprodutível | detetar dependência de ordem |
| `-retry N` | repete os que falham até passarem | último recurso — **mascara**; registar que houve retries |

Mais defesas: `Random.InitState` nos testes; estado físico isolado em `[UnitySetUp]/[UnityTearDown]` (repor
`Physics.simulationMode`, cena/objetos); asserts nunca por tempo de parede.

## 5. Code Coverage (pacote `com.unity.testtools.codecoverage`)

```bash
"$UNITY" -projectPath <raiz> -batchmode -testPlatform editmode -runTests -testResults out/e.xml \
  -debugCodeOptimization -enableCodeCoverage -coverageResultsPath out/cov -coverageHistoryPath out/cov-hist \
  -coverageOptions "generateAdditionalMetrics;generateHtmlReport;assemblyFilters:+Projeto.*;pathFilters:-**/Tests/**"
```

- Relatório combinado EditMode+PlayMode = **3 corridas**: (1) editmode com `…;dontClear`, (2) playmode com
  `…;dontClear`, (3) sem `-runTests`, só gerar relatório (`generateHtmlReport;…`) + `-quit` [S43].
- Citação literal: «`dontClear` | Add this to allow coverage results to be accumulated after every code
  coverage session» [S43]. `-debugCodeOptimization` garante *Code optimization = Debug* (senão a cobertura pode
  não corresponder ao código-fonte) [S43].

## 6. Regressão visual (Graphics Test Framework, `com.unity.testframework.graphics`)

- `ImageAssert.AreEqual(imagem, camera[, threshold])` — o overload com `Camera` captura automaticamente; o 3.º
  parâmetro define thresholds **por-pixel e global** (tolerância a diferenças de hardware/driver) [S44].
- Casos automáticos: `[UseGraphicsTestCases]` + `IPrebuildSetup` → `SetupGraphicsTestCases.Setup()`;
  por código: `[UnityTest, Category("Graphics")] [CodeBasedGraphicsTest("Assets/ReferenceImages", "Assets/ActualImages")]`.
- Baseline: correr → `TestResults.xml` traz imagens **codificadas** → `Tests → Extract images from
  TestResults.xml` → aprovar → `ReferenceImages` (hierarquia ColorSpace/Platform/GraphicsAPI;
  `ReferenceImagesBase` como fallback) [S44].
- ⚠ Nunca `-nographics` em testes de imagem; ambiente fixo (mesma plataforma/GraphicsAPI, resolução fixa);
  ao corrigir bug real, aprovar nova baseline.

## 7. Checklist sem falsos positivos

1. Gate corre **AMBAS** as corridas (editmode + playmode).
2. Falhar se `total==0` ou `total!=testcasecount`.
3. Distinguir exit 2 (quebrou comportamento) de exit 3 (nem compilou) — reprovações com diagnósticos diferentes.
4. Parse do XML NUnit3 (result + contadores + `<failure>`), não só exit code.
5. Física: `Physics.Simulate(passo fixo)` + asserts após nº fixo de passos + teardown.
6. Flakes: `-repeat` para detetar, `-randomOrderSeed` para ordem, `-retry` documentado se usado.
7. Visual: thresholds calibrados, baseline por plataforma/GraphicsAPI, captura só com renderização ativa.
