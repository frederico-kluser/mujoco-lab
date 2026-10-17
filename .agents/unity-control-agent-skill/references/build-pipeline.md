# Build e pipeline de assets programático

> Fontes: dossiê [S53]–[S59] (+ [S36][S40]).

## 1. Build headless canónico

```csharp
// Assets/Editor/BuildScript.cs — método estático, termina com EditorApplication.Exit(0|1)
public static void Build()
{
    var o = new BuildPlayerOptions {
        scenes = new[] { "Assets/Scenas/Boot.unity", "Assets/Scenas/Level1.unity" },
        locationPathName = "Builds/Linux/jogo.x86_64",
        target = BuildTarget.Linux64, targetGroup = BuildTargetGroup.Standalone,
        options = BuildOptions.None
    };
    var r = BuildPipeline.BuildPlayer(o);
    if (r.summary.result == BuildResult.Succeeded) EditorApplication.Exit(0);
    else { Debug.LogError(r.summary); EditorApplication.Exit(1); }
}
```

```bash
"$UNITY" -batchmode -nographics -quit -projectPath <raiz> -buildTarget Linux64 \
  -executeMethod BuildScript.Build -logFile -
```

- `BuildPlayerOptions`: `scenes` (vazio = só a cena aberta), `locationPathName`, `target`, `targetGroup`,
  `subtarget`, `options`, `assetBundleManifestPath`, `extraScriptingDefines`, `previousBuildReportDirectories` [S54].
- ⚠ Citação literal (6000.6): «Calling this method will **invalidate any variables in the editor script that
  reference GameObjects**, so they will need to be reacquired after the call» [S53] — e mudanças de
  *scripting defines* só valem após *domain reload* (mudar defines sem reload antes do build não funciona).
- Overloads antigos (`EditorBuildSettingsScene[]…`) «still supported, but will be replaced» — usar
  `BuildPlayerOptions` / `BuildPlayerWithProfileOptions` [S53].

## 2. Build Profiles (Unity 6)

- Perfis são assets (`File > Build Profiles`): configurações por plataforma + Player Settings Overrides.
- API: `AssetDatabase.LoadAssetAtPath<BuildProfile>(caminho)` +
  `BuildPipeline.BuildPlayer(new BuildPlayerWithProfileOptions { buildProfile, locationPathName, options })`
  (citação: «When working with BuildProfile, use the overload of `BuildPipeline.BuildPlayer` that accepts
  `BuildPlayerWithProfileOptions` instead») [S53][S56]; `BuildProfile.SetActiveBuildProfile`/`GetActiveBuildProfile` [S56].
- CLI: `-activeBuildProfile <pathname>` — aplica os *defines* do perfil e recompila **antes** do
  `-executeMethod` («Unity applies the profile's scripting defines and triggers script compilation before
  invoking the method») — troca de plataforma numa só sessão batch [S13].

## 3. Addressables

```csharp
var settings = AddressableAssetSettingsObject.settings;      // ou LoadAssetAtPath
settings.activeProfileId = settings.profileSettings.GetProfileId("MeuPerfil");
settings.ActivePlayerDataBuilderIndex = settings.DataBuilders.IndexOf(builder); // ex.: BuildScriptPackedMode
AddressableAssetSettings.BuildPlayerContent(out AddressablesPlayerBuildResult result);
if (!string.IsNullOrEmpty(result.Error)) throw new Exception(result.Error);
```

- Citação: «To start a build from another script, call the `AddressableAssetSettings.BuildPlayerContent`
  method» [S55]. Com content build incluído no Player, `BuildPipeline.BuildPlayer` dispara os Addressables como
  pré-build [S55].
- ⚠ **Domain reloads partem builds interativos**: mudanças de defines/plataforma → invocar a CLI em passos
  separados (ex.: `-executeMethod BatchBuild.ChangeSettings` numa chamada; `-executeMethod
  BatchBuild.BuildContentAndPlayer -buildTarget Android` noutra) [S55].

## 4. Pacotes UPM sem GUI

- `Packages/manifest.json`: `dependencies` (registry / `file:<pasta|.tgz>` / git URL), `scopedRegistries`,
  `enableLockFile`, `resolutionStrategy`, `testables`; **pacotes embutidos** (`<projeto>/Packages/<nome>/`) são
  descobertos automaticamente — entrada de manifest com o mesmo nome é ignorada [S36].
- Git URL: `<url>.git?path=/subpasta#revisão` — **`?path=` ANTES de `#revisão`** («the `path` query parameter
  always precedes the revision anchor. The reverse order fails»); revisão = tag/branch/commit; o
  `packages-lock.json` trava hashes de commit (versionar; nunca editar à mão) [S57][S40].

## 5. IL2CPP vs Mono

- «Project build times with IL2CPP can be **significantly longer** than with Mono» [S58]; mitigação: IL2CPP
  Code Generation = «Optimize for code size and build time» (menos performance).
- **Linux IL2CPP cross-compiler**: pacotes sysroot+toolchain que compilam Players Linux IL2CPP de qualquer
  Standalone («without needing to use the Linux Unity Editor or rely on Mono») [S58].
- Orientação oficial: Mono = iteração rápida, builds rápidos, única opção para APIs que exigem JIT; IL2CPP =
  arranque/performance mais previsíveis, conformidade de plataforma [S58].

## 6. Cache de import (Unity Accelerator)

- Proxy de cache de assets importados (Asset Database V2): installer ou Docker; porta predefinida **10080**;
  ativar por projeto (Project Settings → Editor → Cache Server) ou CLI `-EnableCacheServer -cacheServerEndpoint
  Address:Port` [S59].
- `ScriptedImporter` (derivar de `ScriptedImporter` + registar com `ScriptedImporterAttribute`; namespace
  `AssetImporters`) para formatos próprios; o atributo pode desativar a cache do importer — o que também
  desativa a verificação de consistência desse import («If you use `-consistencyCheckSourceMode cacheserver`,
  the consistency checker only checks asset imports that can be cached») [S59].

## 7. Notas de pipeline

- `BuildPlayerOptions.assetBundleManifestPath` liga um pipeline clássico de AssetBundles ao build [S54].
- Builds dev vs release: flags `BuildOptions` (Development, AllowDebugging, BuildScriptsOnly…) e/ou Player
  Settings Overrides dos Build Profiles — referência completa não extraída na pesquisa (ver dossiê §8).
