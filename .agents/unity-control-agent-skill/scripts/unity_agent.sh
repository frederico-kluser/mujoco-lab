#!/usr/bin/env bash
# unity_agent.sh — wrapper do agente para controlar o Unity 6 em Linux (sem GUI).
# Base factual: pesquisas/2026-10-16-skill-controlo-unity6-linux-agente.md (dossiê verificado).
#
# Uso:
#   unity_agent.sh doctor                          diagnóstico: Editor, licença, projeto, lock, logs
#   unity_agent.sh metodo <Namespace.Classe.Metodo> [args…]   -executeMethod com exit code verificável
#   unity_agent.sh testar [filtro]                 editmode + playmode + gate por XML NUnit3
#   unity_agent.sh build <Metodo> [saída] [target] build programático via -executeMethod
#   unity_agent.sh logs [N]                        últimos N erros do Editor.log (Linux)
#
# Variáveis: UNITY_EDITOR (binário), UNITY_PROJECT (raiz do projeto), UNITY_TIMEOUT (s, omissão 1800).
set -u

COR_OK='\033[32m'; COR_AVISO='\033[33m'; COR_ERRO='\033[31m'; COR_FIM='\033[0m'
ok()   { printf "${COR_OK}[OK]${COR_FIM} %s\n" "$*"; }
aviso(){ printf "${COR_AVISO}[AVISO]${COR_FIM} %s\n" "$*"; }
erro() { printf "${COR_ERRO}[ERRO]${COR_FIM} %s\n" "$*" >&2; }

# ---------- resolução de caminhos ----------
resolver_editor() {
  if [ -n "${UNITY_EDITOR:-}" ] && [ -x "$UNITY_EDITOR" ]; then return 0; fi
  local cand
  for cand in "$HOME"/Unity/Hub/Editor/*/Editor/Unity; do
    [ -x "$cand" ] && UNITY_EDITOR="$cand"
  done
  [ -n "${UNITY_EDITOR:-}" ] && [ -x "$UNITY_EDITOR" ]
}

resolver_projeto() {
  if [ -n "${UNITY_PROJECT:-}" ] && [ -d "$UNITY_PROJECT/Assets" ]; then return 0; fi
  local cand
  for cand in \
    experiments/09_drone_hover_rl/unity \
    unity \
    "$HOME"/Projects/MuJoCo/experiments/09_drone_hover_rl/unity
  do
    [ -d "$cand/Assets" ] && { UNITY_PROJECT="$(cd "$cand" && pwd)"; return 0; }
  done
  return 1
}

editor_log() { printf '%s' "$HOME/.config/unity3d/Editor.log"; }

# exit codes do test runner (superfície Editor) — ver dossiê [S5][S6]
explicar_exit_testes() {
  case "$1" in
    0) echo "0 = corrida concluída, todos os testes passaram" ;;
    2) echo "2 = corrida concluída, MAS houve testes falhados (mutação quebrou comportamento)" ;;
    3) echo "3 = run error — a corrida nem produziu veredicto (ex.: falha de compilação)" ;;
    4) echo "4 = plataforma de testes não instalada neste Editor" ;;
    *) echo "exit=$1 (ver log; a doc não define exit codes comuns por componente)" ;;
  esac
}

TIMEOUT="${UNITY_TIMEOUT:-1800}"

correr_editor() {
  # correr_editor <args…> — com timeout e captura de exit code
  timeout --foreground "$TIMEOUT" "$UNITY_EDITOR" "$@"
  local rc=$?
  if [ $rc -eq 124 ]; then
    erro "timeout após ${TIMEOUT}s — o Editor pendurou (hangs conhecidos: bee_backend / cleanup mono / -quit+async)"
    return 124
  fi
  return $rc
}

# ---------- doctor ----------
cmd_doctor() {
  echo "=== unity_agent doctor ==="
  if resolver_editor; then ok "Editor: $UNITY_EDITOR"; else erro "Editor Unity não encontrado (defina UNITY_EDITOR)"; return 1; fi
  local lic_ulf="$HOME/.local/share/unity3d/Unity/Unity_lic.ulf"
  local lic_ent
  lic_ent=$(ls "$HOME"/.config/unity3d/Unity/licenses/*.xml 2>/dev/null | head -1)
  if [ -f "$lic_ulf" ]; then ok "Licença .ulf: $lic_ulf"
  elif [ -n "$lic_ent" ]; then ok "Ficheiro de entitlement presente: $lic_ent (confirmar validade com um batch de 10 s: $UNITY_EDITOR -batchmode -quit -logFile -)"; else
    aviso "Sem .ulf em ~/.local/share/unity3d/Unity/ — Personal ativa-se por LOGIN no Unity Hub (o fluxo .alf→.ulf NÃO suporta Personal na Unity 6)"
  fi
  if resolver_projeto; then ok "Projeto: $UNITY_PROJECT"; else aviso "Projeto Unity não encontrado (defina UNITY_PROJECT)"; fi
  if [ -n "${UNITY_PROJECT:-}" ] && [ -f "$UNITY_PROJECT/Temp/UnityLockfile" ]; then
    aviso "Temp/UnityLockfile EXISTE — projeto pode estar aberto noutro Editor ou lock preso de crash"
    pgrep -a -f "Unity$|UnityShaderCompiler" | head -5 || aviso "sem processos Unity vivos → lock provavelmente preso; confirmar e apagar $UNITY_PROJECT/Temp/UnityLockfile"
  fi
  if command -v xvfb-run >/dev/null 2>&1; then ok "xvfb-run disponível (workaround do bug XAddExtension: xvfb-run -a SEM -nographics)"
  else aviso "xvfb-run não encontrado (pacote xvfb) — necessário só para output visual em batch"; fi
  if command -v unity >/dev/null 2>&1; then ok "unity CLI standalone: $(command -v unity) (sucessor do Hub CLI ≥3.18)"; else aviso "unity CLI standalone ausente (curl -fsSL https://unity.com/install.sh | bash)"; fi
  ok "Editor.log: $(editor_log) $( [ -f "$(editor_log)" ] && echo '(existe)' || echo '(aún não existe)')"
}

# ---------- metodo ----------
cmd_metodo() {
  [ $# -ge 1 ] || { erro "uso: unity_agent.sh metodo <Namespace.Classe.Metodo> [args…]"; return 2; }
  local metodo="$1"; shift
  resolver_editor || { erro "sem Editor"; return 1; }
  resolver_projeto || { erro "sem projeto (UNITY_PROJECT)"; return 1; }
  echo "→ $metodo em $UNITY_PROJECT (timeout ${TIMEOUT}s)"
  # -executeMethod exige método estático em assembly de Editor; exit code = EditorApplication.Exit(code)
  # do método (ou 1 se exceção) — nunca combinar -quit com -runTests.
  correr_editor -batchmode -nographics -quit -projectPath "$UNITY_PROJECT" \
    -executeMethod "$metodo" -logFile - "$@"
  local rc=$?
  echo "exit=$rc"; return $rc
}

# ---------- testar (gate por XML NUnit3) ----------
cmd_testar() {
  local filtro="${1:-}"
  resolver_editor || { erro "sem Editor"; return 1; }
  resolver_projeto || { erro "sem projeto (UNITY_PROJECT)"; return 1; }
  local out="$UNITY_PROJECT/../out/unity_agent"; mkdir -p "$out"
  local rc_total=0 plataforma rc xml
  for plataforma in editmode playmode; do
    xml="$out/${plataforma}-results.xml"
    echo "→ testes $plataforma (sem -quit: o test runner gere a saída)…"
    correr_editor -batchmode -projectPath "$UNITY_PROJECT" \
      -runTests -testPlatform "$plataforma" -testResults "$xml" \
      ${filtro:+-testFilter "$filtro"} -logFile "$out/${plataforma}.log"
    rc=$?; explicar_exit_testes "$rc"; [ $rc -ne 0 ] && rc_total=$rc
    # Gate por XML — o exit code é só sinal auxiliar (doc: não há definição comum de exit codes)
    python3 - "$xml" <<'PY'
import sys, xml.etree.ElementTree as ET
try:
    r = ET.parse(sys.argv[1]).getroot()
except Exception as e:
    print(f"[GATE] XML ilegível: {e}"); sys.exit(1)
total, count = int(r.get('total', 0)), int(r.get('testcasecount', 0))
ok = (r.get('result') == 'Passed' and int(r.get('failed', 0)) == 0
      and total > 0 and total == count)
print(f"[GATE] result={r.get('result')} total={total}/{count} failed={r.get('failed')} "
      f"{'VERDE' if ok else 'VERMELHO'}")
if not ok:
    for f in r.iter('failure'):
        msg = (f.findtext('message') or '').strip().splitlines()[:2]
        print("  falha:", " | ".join(msg))
    sys.exit(1)
PY
    [ $? -ne 0 ] && rc_total=1
  done
  [ $rc_total -eq 0 ] && ok "gate VERDE (ambas as corridas)" || erro "gate VERMELHO"
  return $rc_total
}

# ---------- build ----------
cmd_build() {
  [ $# -ge 1 ] || { erro "uso: unity_agent.sh build <Namespace.Classe.Metodo> [saída] [target]"; return 2; }
  local metodo="$1" saida="${2:-}" target="${3:-Linux64}"
  echo "→ build via $metodo (target=$target ${saida:+· saída=$saida})"
  # O método estático lê argumentos extras com Environment.GetCommandLineArgs e termina com
  # EditorApplication.Exit(0|1) inspecionando BuildReport.summary.result.
  cmd_metodo "$metodo" ${saida:+-buildSaida "$saida"} -buildTarget "$target"
}

# ---------- logs ----------
cmd_logs() {
  local n="${1:-30}" log
  log="$(editor_log)"
  [ -f "$log" ] || { erro "sem Editor.log em $log"; return 1; }
  echo "=== últimos erros/avisos de $log ==="
  grep -n -E "error CS|Exception|Failed|ERROR|Error:" "$log" | tail -n "$n" || ok "sem erros reconhecidos no log"
}

# ---------- despacho ----------
case "${1:-}" in
  doctor) shift; cmd_doctor "$@" ;;
  metodo) shift; cmd_metodo "$@" ;;
  testar) shift; cmd_testar "$@" ;;
  build)  shift; cmd_build "$@" ;;
  logs)   shift; cmd_logs "$@" ;;
  *) sed -n '2,14p' "$0"; exit 2 ;;
esac
