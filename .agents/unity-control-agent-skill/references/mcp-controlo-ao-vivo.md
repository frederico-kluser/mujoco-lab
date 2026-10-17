# Controlo ao vivo do Editor — MCP e pontes (Unity 6 + Linux)

> Fontes: dossiê [S16]–[S27]. Todos estes canais controlam o Editor **ao vivo** (não headless): para execução
> sem GUI ver `cli-headless-linux.md`.

## 1. As 4 famílias (e a escolha)

| Família | Solução | Unity | Linux | Transporte | Escolher quando |
|---|---|---|---|---|---|
| **A · MCP comunidade** | **CoplayDev/unity-mcp** (ex-justinpbarnett, MIT, ~14,7k stars, v10) | 2021.3 LTS → 6.x | **sim** (issue #965, Ubuntu 24.04) | stdio (omissão) + HTTPLocal | **DEFAULT** — mais maduro, 48 tools, docs próprias [S16][S25][S27] |
| A | CoderGamester/mcp-unity (MIT) | **Unity 6 or later** (literal) | inferido (stack C#+WS+Node; não declarado) | WebSocket **8090** no Editor + bridge Node.js 18+ | superfície pequena e estável; resources `unity://…` [S17] |
| A | IvanMurzak/Unity-MCP | (não confirmado) | **sim** (binários linux-x64/arm64) | SignalR + servidor ASP.NET (porta por hash do path, 20000–29999) | tools por atributos C# (`[McpPluginTool]`); CLI `npx unity-mcp-cli` [S19] |
| **B · MCP oficial Unity** | `com.unity.ai.assistant` (pré-release) | 6000.0+ | **sim** (Unix sockets) | relay `~/.unity/relay/` (stdio) ↔ IPC (Unix socket) ↔ MCP Bridge | só com Unity Cloud + trial/subscrição AI beta [S18][S20] |
| **C · Ponte própria** | ogulcancelik/unity-bridge | genérico | sim | **HTTP** (1 ficheiro C#, zero deps) | zero dependências, invocável por `curl` (`/api` schema, `/command`) [S22] |
| C | pardeike/UnityBridge | genérico | sim | GABP/TCP (via servidor GABS/MCP) | nicho [S23] |
| **D · API interna** | `EditorConnection` | — | — | — | **NÃO serve**: é só Editor↔Player; não existe «Unity Automation API» para agentes [S24] |

## 2. CoplayDev/unity-mcp (primária) — o que sabemos

- Instalação: pacote UPM (`com.coplaydev.unity-mcp`) + servidor **Python 3.10+ via `uv`**; requisitos literais:
  «Unity 2021.3 LTS → 6.x · Python 3.10+ (via uv)»; «48 focused MCP tool entrypoints, any client, free & MIT» [S16].
- **48 tools em grupos** (só o grupo *core* ativo por omissão; ativar com `manage_tools(action=activate, group=…)`)
  [S16][S27]:
  - cena/objetos: `manage_scene`, `manage_gameobject`, `find_gameobjects`, `manage_components`,
    `manage_prefabs`, `manage_camera`, `manage_physics`, `manage_material`;
  - scripts: `create_script`, `apply_text_edits`, `script_apply_edits`, `validate_script` (Roslyn),
    `find_in_file`, `delete_script`;
  - editor/projeto: `manage_editor`, `manage_asset`, `manage_packages`, `manage_build`,
    `execute_menu_item`, `read_console`, `refresh_unity`, `batch_execute`;
  - opcionais: `run_tests`, `get_test_job`, `manage_shader`, `manage_vfx`, `manage_ui`, `manage_animation`,
    `manage_profiler`, `manage_probuilder`, `generate_model`, `generate_image` (exigem chaves de provider);
  - meta: `manage_tools`, `set_active_instance` (várias instâncias de Editor).
- **Linux**: evidência real na issue #965 (Ubuntu 24.04.4 + Unity 2022.3.62f3, HTTPLocal) — documenta um bug
  **específico de Linux** no `TerminalLauncher.cs` («Start Server» abria terminal mas o servidor não arrancava),
  reportado e corrigido [S25]. Atenção também à issue #1318 («No Unity Editor instances found») [S26].
- Transporte: stdio por omissão; modo **HTTPLocal** (HTTP server local, bind LAN opcional); opção remota
  alojada com auth — ⚠ envia estado do projeto para infraestrutura de terceiros (avaliar antes) [S16].

## 3. CoderGamester/mcp-unity — o que sabemos

- Requisitos literais do README: «Unity 6 or later - to install the server», «Node.js 18 or later», «npm 9 or later» [S17].
- WebSocket server dentro do Editor: «By default, the WebSocket server runs on port '8090'» (configurável em
  Tools > MCP Unity > Server Window; persiste em `ProjectSettings/McpUnitySettings.json`) + servidor Node.js
  que implementa MCP por stdio [S17].
- Tools: `execute_menu_item`, `select_gameobject`, `get_gameobject`, `update_gameobject`, `update_component`,
  `duplicate_gameobject`, `delete_gameobject`, `create_prefab`, `add_asset_to_scene`, `create_scene`,
  `load_scene`, `save_scene`, `delete_scene`, `get_scene_info`, `unload_scene`, `add_package`, `run_tests`,
  `get/set_play_mode_status`, `get_console_logs`, `send_console_log`, `recompile_scripts`;
  Resources: `unity://menu-items`, `unity://scenes-hierarchy`, `unity://gameobject/{id}`, `unity://logs`,
  `unity://packages`, `unity://assets` [S17].
- ⚠ Modo remoto: bind `0.0.0.0` + `UNITY_HOST` + `MCP_UNITY_AUTH_TOKEN`, mas **`ws://` não cifra** — só rede
  de confiança (VPN/túnel SSH); nunca expor à Internet [S17].

## 4. MCP oficial da Unity (`com.unity.ai.assistant`)

- Arquitetura literal da doc: «Relay binary (`~/.unity/relay/`) with `--mcp` flag | IPC (named pipe / Unix
  socket) | Unity Editor (MCP Bridge) | McpToolRegistry»; «opens a local IPC channel (named pipes on Windows,
  **Unix sockets on macOS/Linux**)» [S18].
- O Editor escreve `~/.mcp/…`/`~/.unity/mcp/connections/bridge-*.json` (connection_type, path, project_path,
  editor_pid); o relay varre e liga-se; tools **custom em C#** registam-se no `McpToolRegistry`; multi-cliente;
  conexões diretas exigem aprovação do utilizador [S18].
- Pré-requisitos: Unity 6000.0+, pacote AI Assistant, **projeto ligado a Unity Cloud**, trial/subscrição AI beta [S20].
- ⚠ Fiabilidade contestada: relatos de relays zombie sobrevivendo ao fecho do Editor e «toil» de instalação —
  comunidade a migrar para CoplayDev [S21]. Pré-release: superfície pode mudar.

## 5. Ponte HTTP própria (fallback zero-dependências)

- `ogulcancelik/unity-bridge`: **1 ficheiro C#** (2 816 linhas, zero dependências), arranque via
  Tools → Unity Bridge → Enabled; o agente faz `curl` a `/api` (schema autodescritivo) e `/command`
  (ex.: `create_gameobject`, `get_hierarchy`) [S22]. Comparação do próprio README: 1 ficheiro vs 776 do Unity
  MCP, sem servidor Python.
- ⚠ HTTP local **sem autenticação descrita**: qualquer processo da máquina pode comandar o Editor — ativar só
  durante a sessão de trabalho [S22].

## 6. Segurança (todos os canais)

1. Toda a tool executa efeitos **arbitrários** no Editor (`execute_menu_item`, `recompile_scripts`, edição de
   scripts, builds): tratar outputs como *untrusted* e trabalhar num projeto versionado/sandbox.
2. `ws://` sem cifra (mcp-unity) e HTTP sem auth (unity-bridge) = **localhost only**.
3. Servidor remoto alojado (CoplayDev) envia dados do projeto para terceiros — desativado por omissão.
4. O MCP oficial exige aprovação de conexões (bom) mas depende de cloud + conta Unity (não é offline).
