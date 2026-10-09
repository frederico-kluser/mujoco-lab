#!/usr/bin/env bash
# install.sh — instala o comando global `mujoco` do MuJoCo Lab (symlink em ~/.local/bin).
# Idempotente: pode correr quantas vezes quiser — nada é duplicado nem destruído.
set -euo pipefail

RAIZ="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ALVO="$RAIZ/bin/mujoco"
DESTINO="$HOME/.local/bin"
LINK="$DESTINO/mujoco"

msg() { printf '%s\n' "$*"; }
erro() { printf 'Erro: %s — Solução: %s\n' "$1" "$2" >&2; exit "${3:-1}"; }

uso() {
  cat <<'EOF'
install.sh — instala o comando `mujoco` do MuJoCo Lab em ~/.local/bin

Uso:
  bash install.sh              instala tudo: dependências + site + symlink + prova
  bash install.sh --so-comando só cria o symlink (sem `uv sync` nem build do site)
  bash install.sh --sem-site   instala sem compilar o site do experimento
  bash install.sh --uninstall  remove APENAS o symlink ~/.local/bin/mujoco
  bash install.sh --help, -h   esta ajuda

O que faz (idempotente):
  1. confere `uv`, `node` e `npm` e diz exatamente o que falta;
  2. `uv sync --group hover-rl` e, se o site do experimento não tiver `dist/`,
     `npm install && npm run build` em experiments/<exp>/site (usa ~/.secrets se existir — MOTION_TOKEN);
  3. symlink ~/.local/bin/mujoco → <repo>/bin/mujoco (cria ~/.local/bin se preciso e, se essa pasta
     não estiver no PATH, diz a linha exata para o ~/.bashrc / ~/.zshrc);
  4. prova: corre `mujoco --help`;
  5. imprime "pronto — corre `mujoco`".

Exit codes: 0 = ok · 1 = erro · 2 = opção inválida.
EOF
}

SO_COMANDO=0
SEM_SITE=0
DESINSTALAR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --help | -h)
      uso
      exit 0
      ;;
    --uninstall)
      DESINSTALAR=1
      ;;
    --so-comando)
      SO_COMANDO=1
      ;;
    --sem-site)
      SEM_SITE=1
      ;;
    *)
      erro "opção desconhecida: $1" "vê as opções com \`bash install.sh --help\`" 2
      ;;
  esac
  shift
done

# --- desinstalar: remove só o symlink e sai --------------------------------
if [ "$DESINSTALAR" -eq 1 ]; then
  if [ -L "$LINK" ]; then
    destino_antigo="$(readlink "$LINK")"
    rm -f "$LINK"
    msg "removido o symlink $LINK (apontava para $destino_antigo)"
    msg "nada mais foi tocado."
  elif [ -e "$LINK" ]; then
    erro "$LINK existe mas não é um symlink (não vou apagar ficheiros teus)" \
      "move-o ou apaga-o à mão e corre \`bash install.sh --uninstall\` de novo"
  else
    msg "nada a remover: $LINK não existe."
  fi
  exit 0
fi

[ -f "$ALVO" ] || erro "não encontrei o comando em $ALVO" "corre este script da raiz do repositório MuJoCo Lab"

# --- 1. dependências --------------------------------------------------------
if [ "$SO_COMANDO" -eq 0 ]; then
  faltam=""
  for ferramenta in uv node npm; do
    command -v "$ferramenta" >/dev/null 2>&1 || faltam="$faltam $ferramenta"
  done
  if [ -n "$faltam" ]; then
    erro "faltam as ferramentas:$faltam" \
      "instala-as primeiro: uv → https://docs.astral.sh/uv/ (curl -LsSf https://astral.sh/uv/install.sh | sh) · node/npm → pacman -S nodejs npm (ou nvm)"
  fi
  msg "1/4 dependências ok (uv, node, npm)"
else
  msg "1/4 ignorado (--so-comando)"
fi

# --- 2. ambiente Python + build do site -------------------------------------
if [ "$SO_COMANDO" -eq 1 ]; then
  msg "2/4 ignorado (--so-comando)"
else
  msg "2/4 a sincronizar o ambiente (uv sync --group hover-rl)…"
  (cd "$RAIZ" && uv sync --group hover-rl)
  if [ "$SEM_SITE" -eq 1 ]; then
    msg "      site não compilado (--sem-site)"
  else
    if [ -f "$HOME/.secrets" ]; then
      set +u
      # shellcheck disable=SC1091
      . "$HOME/.secrets"
      set -u
      msg "      ~/.secrets carregado (MOTION_TOKEN para os pacotes Motion+ do site)"
    fi
    if [ -z "${MOTION_TOKEN:-}" ]; then
      msg "      nota: MOTION_TOKEN não definido (fica em ~/.secrets) — o npm install do site pode falhar nos pacotes Motion+"
    fi
    for site in "$RAIZ"/experiments/*/site; do
      [ -f "$site/package.json" ] || continue
      if [ -d "$site/dist" ]; then
        msg "      site já compilado: ${site#"$RAIZ"/}"
        continue
      fi
      msg "      a compilar: ${site#"$RAIZ"/} (npm install && npm run build)…"
      (cd "$site" && npm install && npm run build)
    done
  fi
fi

# --- 3. o comando global ----------------------------------------------------
mkdir -p "$DESTINO"
if [ -L "$LINK" ]; then
  atual="$(readlink "$LINK")"
  if [ "$atual" = "$ALVO" ]; then
    msg "3/4 symlink já instalado: $LINK → $ALVO"
  else
    ln -sfn "$ALVO" "$LINK"
    msg "3/4 symlink atualizado: $LINK → $ALVO (era: $atual)"
  fi
elif [ -e "$LINK" ]; then
  erro "$LINK já existe e não é um symlink — não vou destruir o teu ficheiro" \
    "move-o ou apaga-o à mão e corre \`bash install.sh\` de novo"
else
  ln -s "$ALVO" "$LINK"
  msg "3/4 symlink criado: $LINK → $ALVO"
fi

case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *)
    msg "      atenção: $HOME/.local/bin NÃO está no PATH — acrescenta esta linha ao ~/.bashrc ou ~/.zshrc:"
    msg '      export PATH="$HOME/.local/bin:$PATH"'
    ;;
esac

# --- 4. prova + recado final ------------------------------------------------
msg "4/4 prova: mujoco --help"
"$LINK" --help
msg ""
msg "pronto — corre \`mujoco\`"
