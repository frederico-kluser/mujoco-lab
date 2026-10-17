# Instalação e licença do Unity 6 em Linux

> Fontes: dossiê [S47]–[S52]. Verificação adversarial confirmou as citações literais da ativação manual, da
> depreciação do Hub CLI e dos secrets do game-ci.

## 1. Versões — o `unity` CLI substituiu o Hub CLI

- Citação literal (docs Hub CLI): «**The Hub CLI is deprecated from version 3.18.0** of the Unity Hub. For new
  scripts and automation, use the Unity CLI.» [S48][S51]
- **`unity` CLI standalone** (experimental): `curl -fsSL https://unity.com/install.sh | bash` →
  `~/.local/bin/unity` (alternativas: repos `.deb`/`.rpm` oficiais, AppImage, `brew install --cask unity-cli`;
  glibc ≥ 2.34) [S48]:
  ```bash
  unity install lts              # ou: unity install 6000.3.22f1 [-m ios android webgl]
  unity install-modules -e 6000.3.22f1 -m android
  unity editors -i               # instalados
  unity projects create <nome> [--no-cloud]   # unity open ./Projeto · unity doctor · unity self-update
  ```
- Hub CLI legado (Hubs < 3.18) ainda funciona: `unityhub -- --headless help|editors|install-path|install|install-modules|exit`;
  instalar Editor e módulos em **comandos separados** é mais fiável (falhas perto dos 100% num só comando) [S51].
- No Linux **não há** `.deb`/AppImage oficial do Editor: instala-se via Hub/CLI; módulos só a Editores
  instalados por Hub/CLI (Editores manuais têm de ser reinstalados primeiro) [S48].

## 2. Licença — o ponto que custa descobrir

- **Ativação manual `.alf → .ulf` NÃO suporta Personal na Unity 6.** Citação literal (6000.3):
  «Manual activation supports two kinds of licenses: assigned seats on a Unity Enterprise or Unity Industry
  subscription, and legacy serial-based Unity Pro licenses. It doesn't support Unity Pro assigned seats,
  **Unity Personal**, or floating license subscriptions. To activate a license for Unity Personal, **log in to
  the Unity Hub**.» [S47]
- Fluxo manual (só Enterprise/Industry seats e serial Pro legado):
  1. `<Unity> -batchmode -createManualActivationFile -logfile` → cria `Unity_v<versão>.alf` no cwd;
  2. numa máquina com internet: `id.unity.com` → `license.unity3d.com/manual` → upload do `.alf` → download
     `.xml` (seat) ou `.ulf` (serial legado);
  3. `<Unity> -batchmode -manualLicenseFile <ficheiro> -logfile` (funciona offline) [S47].
- **Personal**: ativar **uma vez com GUI** (Unity Hub → Preferences → Licenses → Add → free personal license);
  o `.ulf` fica em `~/.local/share/unity3d/Unity/Unity_lic.ulf` (Linux) e pode ser copiado/reutilizado — é o
  padrão do game-ci [S50]. ⚠ Comunidade/game-ci: «Unity no longer supports manual activation of Personal
  licenses» — o fluxo `UNITY_LICENSE` de Personal pode exigir workaround na `license.unity3d.com` [S50].
- Licenças não são presas à versão nem ao SO (obter num SO, usar noutro) [S50].
- `unity auth login` abre **browser** (não serve para CI sem GUI); há *service accounts* [S48].

## 3. CI (GameCI)

| Tipo de licença | Secrets | Notas |
|---|---|---|
| Personal | `UNITY_LICENSE` (conteúdo do `.ulf`) + `UNITY_EMAIL` + `UNITY_PASSWORD` | ver caveat acima [S50] |
| Pro (serial) | `UNITY_SERIAL` + `UNITY_EMAIL` + `UNITY_PASSWORD` | ações `unity-activate` / `unity-return-license` [S50] |
| 2FA | `UNITY_TOTP_KEY` ou `EMAIL_PASSWORD` | `game-ci/unity-license-activate` (também converte `.alf`→`.ulf`) [S50] |
| Floating | input `unityLicensingServer: <url>` | Unity Licensing Server: pool HTTP; setup em `/opt/UnityLicensingServer`, clientes com `services-config.json` em `/usr/share/unity3d/config/` [S49] |

Imagens: `unityci/editor:<versão>-<módulo>-<n>` (um módulo por imagem; multi-módulo via
`game-ci build-unity-image --recipe`) [S3]. **Segredos nunca em ficheiros versionados** (regra do projeto:
`~/.secrets` / CI secrets).

## 4. Requisitos Linux (6000.x) — e a realidade desta máquina

- Oficiais: Ubuntu 22.04/24.04, x64+SSE2, GPU OpenGL 3.2+/Vulkan (NVIDIA proprietário ou AMD Mesa), Gnome
  X11/Wayland; Wayland com NVIDIA exige driver ≥ 550 (24.04) [S52].
- **Esta máquina** (CachyOS + KDE Wayland + RTX 4070): fora da configuração suportada (Ubuntu+Gnome) — funciona
  por extrapolação amplamente usada; em problemas de janela/OpenGL, XWayland/X11 é a via segura.
- Fallback gráfico sem GUI: `xvfb-run --auto-servernum --server-args='-screen 0 640x480x24' <Editor> …` [S8].

## 5. Procedimento desta máquina (checklist)

1. `bash scripts/unity_agent.sh doctor` — Editor 6000.3.22f1, entitlement presente, `Unity_lic.ulf`?
2. Sem `.ulf` e com Personal: abrir Hub (GUI KDE) → login → licença free → confirmar
   `~/.local/share/unity3d/Unity/Unity_lic.ulf`.
3. Versões novas: `unity install <v> -m <módulos>` (CLI já instalada em `~/.local/bin/unity`).
4. CI: copiar `.ulf` para secret `UNITY_LICENSE` (+`EMAIL`/`PASSWORD`) ou montar Licensing Server.
5. Builds não gráficos: `-batchmode -nographics -quit -executeMethod … -logFile -`.
