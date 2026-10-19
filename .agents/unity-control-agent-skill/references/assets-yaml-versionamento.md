# Assets em texto (UnityYAML) — política VERDE/AMARELO/VERMELHO

> Fontes: dossiê [S35]–[S40]. O UnityYAML **não é YAML comum**: subconjunto proprietário (tags `tag:unity3d.com,2011`),
> um objeto serializado por documento `--- !u!<classID> &<fileID>`, referências `{fileID, guid, type}`.

## 1. Formato — o mínimo para não partir nada

- Cabeçalho de ficheiro: `%YAML 1.1` + `%TAG !u! tag:unity3d.com,2011:`; documento: `--- !u!<classID> &<fileID> <Classe>:`.
- classIDs: `1` GameObject · `4` Transform · `21` Material · `23` MeshRenderer · `33` MeshFilter ·
  `114` MonoBehaviour · `1001` PrefabInstance [S35].
- Referência interna: `{fileID: N}` · a outro asset: `{fileID: <id-no-alvo>, guid: <32 hex do .meta>, type: 3}`
  (`type: 2` recursos importados; `type: 0` builtins) · script: `m_Script: {fileID: 11500000, guid: …, type: 3}` [S35].
- Prefab instanciado: documento `!u!1001` com `m_Modifications` + `m_SourcePrefab`; herdados viram `stripped`.
- Floats podem sair em hex IEEE-754 (`0x3F800000(1)`): para editar à mão, **remover o hex e escrever decimal** [S35].
- `fileFormatVersion: 2` (primeira linha de `.meta`/`.asset`): **não alterar**.

## 2. A política

### 🟢 VERDE — texto livre (reviewável)

| Alvo | Regras |
|---|---|
| `Packages/manifest.json` | deps (registry / `file:` / git URL), `scopedRegistries`, `enableLockFile`, `resolutionStrategy`, `testables`; JSON válido; deixar o UPM resolver [S36] |
| `*.asmdef` / `*.asmref` | só campos do formato documentado; nunca `includePlatforms` + `excludePlatforms` juntos; `references` bate certo com `name` do alvo [S31] |
| `.gitignore` / `.gitattributes` | base oficial `github/gitignore Unity.gitignore` [S38]; regras de merge do Smart Merge [S37] |

### 🟡 AMARELO — só cirurgia em valores + verificação no Editor

| Alvo | Permite | Proíbe |
|---|---|---|
| cenas `.unity` / prefabs `.prefab` | mudar VALORES escalares existentes (`m_Name`, `m_IsActive`, `m_LocalPosition/Rotation/Scale`, `m_IsTrigger`, `m_Enabled`) | inserir/apagar/reordenar documentos; tocar em `&fileID`/classID/`guid`; mudar `m_Script`, `m_SourcePrefab`, `m_CorrespondingSourceObject`, `m_PrefabInstance`; formatadores YAML genéricos; adicionar componentes [S35] |
| `.mat` | floats/cores/toggles em `m_SavedProperties` | mudar referências de shader/textura sem guid verificado no `.meta` |
| `ProjectSettings/*.asset` | escalares triviais já presentes (ex.: `m_ProductName`) | `ProjectVersion.txt`; listas/IDs estruturados sem validação no Editor |
| `.meta` | mover/renomear asset **EM PAR** com o `.meta` (mesmo commit); criar `.meta` novo com guid novo e único | mudar guid de `.meta` versionado; apagar `.meta`; deixar asset novo sem `.meta` [S39] |

Após **qualquer** edição AMARELA: abrir no Editor e confirmar importação limpa + ausência de «Missing script»;
grep no diff para garantir que nenhum guid/fileID foi tocado.

### 🔴 VERMELHO — nunca à mão

guids de `.meta` versionados · `&fileID` e referências `{fileID, guid, type}` · `m_Script` · blocos
`PrefabInstance`/`stripped` (`!u!1001`) · `packages-lock.json` (versionar, nunca editar — o UPM recalcula a
resolução determinística [S40]) · `Library/`, `Temp/`, `obj/`, `Logs/`, `UserSettings/` · `ProjectVersion.txt` ·
assets binários.

**Regra transversal:** nunca editar um ficheiro com o Editor aberto a tê-lo carregado (o save do Editor
sobrescreve a edição).

## 3. Versionamento

- `Edit > Project Settings > Editor`: **Asset Serialization = Force Text** (padrão em projetos novos) e
  **Version Control = Visible Meta Files** [S38].
- Versionar: `Assets/` (com **todos** os `.meta` ao lado), `Packages/` (manifest + lock + embutidos),
  `ProjectSettings/`. Ignorar (base oficial [S38]): `Library/`, `Temp/`, `obj/`, `Build(s)/`, `Logs/`,
  `UserSettings/`, `*.csproj`, `*.sln*`, `.vs/`, `.gradle/`, `*.apk/aab/unitypackage`, …
- **Regra de ouro:** os três diretórios que definem o projeto são `Assets`, `Packages`, `ProjectSettings` — o
  resto o Editor regenera. NUNCA ignorar `.meta`.
- Pacotes embutidos (`<projeto>/Packages/<nome>/`) são descobertos automaticamente (entrada de manifest com o
  mesmo nome é ignorada) — código dentro deles é texto normal e editável [S36].
- Git URL UPM: `?path=/subpasta` vem **antes** de `#revisão` (a ordem inversa falha); revisão = tag/branch/commit;
  o lock file trava os commit hashes [S57].

## 4. Merge — UnityYAMLMerge (Smart Merge)

- Vem com o Editor (`Editor/Data/Tools/UnityYAMLMerge`; `mergespecfile.txt` + `mergerules.txt` com tolerâncias
  de floats — ex.: `m_LocalRotation`) [S37].
- Modos: `Edit > Project Settings > Version Control > Smart Merge`: Off | Premerge | Ask (padrão).
- Git mergetool oficial:
  ```ini
  [merge] tool = unityyamlmerge
  [mergetool "unityyamlmerge"] trustExitCode = false
      cmd = '<caminho>/UnityYAMLMerge merge -p "$BASE" "$REMOTE" "$LOCAL" "$MERGED"'
  ```
  (ordem: base, theirs, mine, merged) [S37]. *Merge driver* em `.gitattributes` exige config local por máquina
  (prática comunitária; a doc oficial cobre o *mergetool*).
- **Política do agente:** conflitos em `.unity`/`.prefab` nunca resolvidos «à mão» escolhendo blocos — correr
  UnityYAMLMerge; se falhar, resolver visualmente no Editor.

## 5. Checklist de mutação textual segura

1. Confirmar Force Text + Visible Meta Files.
2. Classificar o alvo: VERDE / AMARELO / VERMELHO (VERMELHO = usar Editor scripting).
3. Editar só linhas de valor; diff mínimo.
4. Validar JSON (manifest/asmdef) e indentação YAML (nunca correr formatadores genéricos).
5. `grep` do diff: nenhum `guid:`/`fileID`/`m_Script` tocado.
6. Abrir no Editor → importação limpa, sem «Missing script».
7. Commitar asset + `.meta` juntos; nunca commitar `Library/Temp/Logs/UserSettings`.
