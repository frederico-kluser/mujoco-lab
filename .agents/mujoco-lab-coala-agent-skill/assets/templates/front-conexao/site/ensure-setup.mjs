#!/usr/bin/env node
/**
 * ensure-setup.mjs — deixa o site PRONTO A CONSTRUIR (idempotente). Corre a partir de `site/`:
 *
 *     source ~/.secrets          # MOTION_TOKEN (registry @motionplus; ver .npmrc)
 *     node ensure-setup.mjs      # este script
 *     npm run build              # gera dist/ que o sim_site.py serve
 *
 * O que faz, por ordem: confere node/npm e o token, cria o `package.json` mínimo se não existir (caso se
 * esteja a começar de raiz), corre `npm install` quando falta `node_modules/`, instala os componentes
 * `@motion`/shadcn que faltarem e diz o próximo passo. Não mexe em ficheiros já existentes.
 *
 * ★ ADAPTAR ao copiar o template: a lista COMPONENTES (os que o teu site usa) e, se quiseres, o mínimo de
 *   versões de node. Nada mais.
 */
import { execFileSync, spawnSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const AQUI = dirname(fileURLToPath(import.meta.url))
const NODE_MIN = 20
/** Componentes do registry @motion + primitivos shadcn que o site usa (ver src/components/**). */
const COMPONENTES = [
  "@motion/sparkline",
  "@motion/animated-number",
  "@motion/hold-to-confirm",
  "@motion/multi-state-button",
  "@motion/segmented-toggle",
  "@motion/progress-bar",
  "@motion/stagger-reveal",
  "@motion/toast-stack",
  "@motion/skeleton",
  "@motion/ui-theme",
  "button",
  "card",
  "slider",
]

const falhas = []
const ok = (msg) => console.log(`  ok    ${msg}`)
const aviso = (msg) => console.log(`  aviso ${msg}`)
const erro = (msg) => {
  falhas.push(msg)
  console.log(`  ERRO  ${msg}`)
}

function versao(cmd, args = ["--version"]) {
  try {
    return execFileSync(cmd, args, { encoding: "utf8" }).trim()
  } catch {
    return null
  }
}

console.log("ensure-setup: a verificar o ambiente do site…")
const vNode = versao("node")
const vNpm = versao("npm")
if (!vNode) erro("node não encontrado no PATH (instala Node ≥ 20)")
else if (Number(vNode.replace(/^v/, "").split(".")[0]) < NODE_MIN) erro(`node ${vNode} é antigo (preciso ≥ ${NODE_MIN})`)
else ok(`node ${vNode}`)
if (!vNpm) erro("npm não encontrado no PATH")
else ok(`npm ${vNpm}`)

// Token do registry @motionplus (o .npmrc referencia ${MOTION_TOKEN}).
const npmrc = join(AQUI, ".npmrc")
if (!existsSync(npmrc)) aviso(".npmrc não existe — sem ele o registry @motionplus não autentica")
else if (!process.env.MOTION_TOKEN) {
  aviso("MOTION_TOKEN não está no ambiente — corre `source ~/.secrets` ANTES deste script")
} else ok("MOTION_TOKEN presente")

// package.json mínimo (só quando se começa de raiz: com as fontes do template ele já existe).
const pkg = join(AQUI, "package.json")
if (!existsSync(pkg)) {
  erro("package.json não existe — cria o projeto com `npx shadcn@latest init -t vite -n site -b base -p nova --no-monorepo --no-rtl -y` e volta a correr isto")
} else {
  const nome = JSON.parse(readFileSync(pkg, "utf8")).name ?? "(sem nome)"
  ok(`package.json (${nome})`)
}

// Dependências: só instala se faltar node_modules/.
if (!falhas.length) {
  if (!existsSync(join(AQUI, "node_modules"))) {
    console.log("ensure-setup: npm install (primeira vez; pode demorar ~1 min)…")
    const r = spawnSync("npm", ["install", "--no-audit", "--fund=false"], { cwd: AQUI, stdio: "inherit" })
    if (r.status !== 0) erro("`npm install` falhou (vê a mensagem acima: token/registry/rede)")
    else ok("dependências instaladas")
  } else {
    ok("node_modules/ já existe")
  }
}

// Componentes em falta (o shadcn é idempotente mas ruidoso: só se corre quando falta algum ficheiro).
const DIR_COMPONENTES = join(AQUI, "src", "components", "motion-ui")
if (!falhas.length && !existsSync(DIR_COMPONENTES)) {
  console.log("ensure-setup: a instalar componentes do registry (shadcn add)…")
  const r = spawnSync("npx", ["--yes", "shadcn@latest", "add", ...COMPONENTES, "-y", "-o"], { cwd: AQUI, stdio: "inherit" })
  if (r.status !== 0) erro("`shadcn add` falhou — confirma `source ~/.secrets` (MOTION_TOKEN) e a rede")
  else ok("componentes instalados")
} else if (!falhas.length) {
  ok("componentes do registry já presentes (não mexi em nada)")
}

if (falhas.length) {
  console.log(`\nensure-setup: ${falhas.length} problema(s) — resolve e volta a correr.`)
  process.exit(1)
}
console.log("\nensure-setup: tudo pronto. Próximo passo:\n  npm run build     # tsc -b && vite build → dist/")
console.log("  (o `sim_site.py` serve o dist/ e a API na mesma origem)")
