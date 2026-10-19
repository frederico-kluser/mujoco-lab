# Editor scripting C# — padrão de mutação seguro

> Fontes: dossiê [S28]–[S34]. Regra-mãe: **mudança estrutural (objetos, componentes, prefabs, cenas) faz-se
> pelas Editor APIs** — referências `{fileID, guid, type}` partem em silêncio quando se edita YAML à mão.

## 1. Esqueleto de mutação headless (receita a)

```csharp
// Assets/Editor/Mutacao.cs  (pasta Editor OU asmdef includePlatforms: ["Editor"])
using System; using UnityEditor; using UnityEngine;

public static class Mutacao
{
    // -executeMethod exige método ESTÁTICO. Parâmetros: Environment.GetCommandLineArgs().
    public static void Corrida()
    {
        try
        {
            // ... mutações ...
            AssetDatabase.SaveAssets();
            EditorApplication.Exit(0);   // SUCESSO = Exit(0) explícito (a doc não define exit de sucesso sem isto)
        }
        catch (Exception e)
        {
            Debug.LogError("[Mutacao] falhou: " + e);
            EditorApplication.Exit(1);   // alternativa: exceção não apanhada → Unity sai com 1
        }
    }
}
```

```bash
"$UNITY" -batchmode -nographics -quit -projectPath <raiz> \
  -executeMethod Mutacao.Corrida -logFile -
```

Notas: `-executeMethod` aceita `Classe.Metodo` ou `Namespace.Classe.Metodo`; executa ao abrir o projeto;
`Application.isBatchMode` deteta batch; em batch `SwitchActiveBuildTarget` indisponível (usar `-buildTarget`)
e `WaitForEndOfFrame` nunca corre [S31][S34].

## 2. Estrutura de asmdef editor-only (receita d)

```json
{
  "name": "Projeto.EditorTools",
  "references": [ "Projeto.Runtime" ],
  "includePlatforms": [ "Editor" ],
  "excludePlatforms": [],
  "allowUnsafeCode": false, "overrideReferences": false, "precompiledReferences": [],
  "autoReferenced": true, "defineConstraints": [], "versionDefines": [], "noEngineReferences": false
}
```

- `includePlatforms: ["Editor"]` é **explícito** quando se usa asmdef (sem asmdef, a pasta `Editor/` já basta) —
  sem isso a assembly entra na build de player e falha com tipos `UnityEditor` [S31].
- Convenção oficial: `Editor/..Editor.asmdef` · `Runtime/..asmdef` · `Tests/Editor/..Editor.Tests.asmdef` [S31].
- Tudo o que o `-executeMethod` invoca tem de viver em assembly compilada para o Editor [S34].

## 3. Editar propriedades (receita c) — ordem importa

```csharp
// PREFERIDO (recomendação oficial): SerializedProperty
var so = new SerializedObject(componente);
so.Update();
so.FindProperty("velocidade").floatValue = 3.5f;
so.ApplyModifiedProperties();   // dirty + Undo + overrides de prefab

// Alternativa direta:
Undo.RecordObject(componente, "Ajustar velocidade");   // ANTES da mudança
componente.velocidade = 3.5f;
PrefabUtility.RecordPrefabInstancePropertyModifications(componente); // OBRIGATÓRIO em instâncias de prefab
```

- Citação literal (6000.6): «To correctly handle instances where `objectToUndo` is an instance of a Prefab,
  `PrefabUtility.RecordPrefabInstancePropertyModifications` must be called after `RecordObject`» [S29].
- `Undo.RecordObject` regista o diff no fim do frame; **não** cobre mudança de pai, `AddComponent` nem
  destruição → `Undo.SetTransformParent` / `Undo.RegisterCreatedObjectUndo` / `Undo.DestroyObjectImmediate` [S29].
- ScriptableObject: docs mandam `EditorUtility.SetDirty` **+** `Undo.RecordObject` [S34].
- Cena: gravar com `EditorSceneManager.SaveScene/SaveOpenScenes` [S33].

## 4. Prefabs (receita b) — o match é por NOMES

```csharp
// CRIAR (não modifica a entrada; só dentro de Assets/, termina em .prefab)
bool ok; var root = PrefabUtility.SaveAsPrefabAsset(go, "Assets/Prefabs/Robo.prefab", out ok);
if (!ok) throw new Exception("SaveAsPrefabAsset falhou");

// ATUALIZAR prefab existente (padrão seguro):
var contents = PrefabUtility.LoadPrefabContents("Assets/Prefabs/Robo.prefab");
try {
    // modificar contents…
    if (PrefabUtility.SaveAsPrefabAsset(contents, "Assets/Prefabs/Robo.prefab") == null)
        throw new Exception("falha ao gravar prefab");
} finally { PrefabUtility.UnloadPrefabContents(contents); }
```

Armada que custou descobrir (documentada [S28]): ao gravar por cima, a Unity preserva referências
**correspondendo por NOMES de GameObjects** — «if there are multiple GameObjects with the same name in the
Prefab's hierarchy, you cannot predict which will be matched» → **garantir nomes únicos na hierarquia**;
filho de instância de prefab não pode ser entrada (só raiz; raiz de instância gera **variant** — fazer `Unpack`
para prefab novo); dentro de lote `StartAssetEditing` o `SaveAsPrefabAsset` retorna `null` mesmo com sucesso.
Cenas: `EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single)` → montar →
`SaveScene` [S33].

## 5. Lotes de assets (contador, não interruptor)

- `AssetDatabase.StartAssetEditing`/`StopAssetEditing`: citação literal (6000.6): «Unity supports nested
  calls… This is tracked with a **counter**» [S30] — pares iguais em `try/finally` (ou
  `using (new AssetEditingScope())`).
- A mais `Start` do que `Stop` → a importação automática **nunca recomeça** (exige reiniciar o Editor);
  a mais `Stop` → erro [S30].
- Depois do lote: `AssetDatabase.Refresh()` + `AssetDatabase.SaveAssets()`.

## 6. Domain reload e estado static (armadilha — VARIA com a versão!)

⚠ **A versão decide o default** (verificação adversarial confirmou a divergência entre as próprias docs):
- **6000.0 LTS (e 6000.3, o Editor desta máquina)**: `domain-reloading.html` (6000.0) — «**By default Unity
  reloads the domain on entering Play mode** to reset the application state» → statics **são** resetados por
  omissão [S32].
- **6000.6+ (novos projetos)**: `configurable-enter-play-mode` (6000.6) — «**Reload Scene only. This is the
  default option.**» e «By default Unity doesn't reload the scripting domain…»; OpenUPM: «Starting with Unity
  6.6, Fast Enter Play Mode is enabled by default for new projects» → statics **persistem** [S32].
- **Regra segura em qualquer versão**: escrever código que sobrevive aos dois mundos — reset explícito:
  ```csharp
  [InitializeOnEnterPlayMode]
  static void ResetStatics(EnterPlayModeOptions opts) { _cache = null; MeuEvento -= Handler; }
  ```
  desregistar sempre handlers estáticos; nunca guardar desfechos de mutações em statics (um *domain reload* por
  recompilação apaga-os): estado em disco/`AssetDatabase`; `AssemblyReloadEvents.beforeAssemblyReload` para
  descarregar [S32].
- Qualificações: campos `[NonSerialized]`/statics persistem com reload desligado; o snapshot da cena é
  restaurado ao sair de Play (o que «não resetam» se aplica a statics, não à cena).
- `[InitializeOnLoad]`: só bootstrap **idempotente** (corre após cada reload); trabalho real via
  `EditorApplication.delayCall` [S32].

## 7. Checklist de mutação

1. asmdef `includePlatforms:["Editor"]` + método estático + `try/catch` + `EditorApplication.Exit(0|1)`.
2. `SerializedObject.ApplyModifiedProperties` (ou `Undo.RecordObject` + `RecordPrefabInstancePropertyModifications`).
3. Prefabs: nomes únicos na hierarquia; `LoadPrefabContents` em `try/finally`; nunca dentro de lote de assets.
4. `StartAssetEditing`/`StopAssetEditing` em pares; `Refresh`+`SaveAssets` no fim.
5. Sem estado static entre fases; reset em `[InitializeOnEnterPlayMode]`.
6. Verificar depois: `unity_agent.sh testar` (gate XML) — a mutação só está feita com evidência.
