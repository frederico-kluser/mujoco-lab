# Instalação e configuração do MuJoCo no Linux (CachyOS/Arch) com uv
Como instalar, verificar e configurar o MuJoCo 3.15 nesta máquina (wheel via uv), escolher entre wheel/tarball/CMake/AUR e compilar C/C++ contra a `libmujoco`.

> Verificado em MuJoCo 3.15.0 (2026-10-07). Fontes: ficha `pesquisas/conhecimento/Q1.md` (F1–F43); `docs/upstream/mujoco/doc/{python.rst,programming/index.rst,programming/simulation.rst,changelog.rst}`, `docs/upstream/mujoco/{CMakeLists.txt,VERSIONING.md,python/setup.py,sample/cmake/FindOrFetch.cmake}`; `pyproject.toml` do projeto; `mujoco-3.15.0.dist-info/{METADATA,RECORD,WHEEL}` do `.venv`; testes locais (uv 0.12.7, CPython 3.10–3.14, gcc 16.2.1, CMake 4.4.4 do PyPI) em venvs descartáveis.

## Quando ler este arquivo
- Criar/recriar o `.venv`, trocar de Python, atualizar o MuJoCo ou instalar grupos opcionais (`viz`, `urdf`, `rl`, `gpu`).
- `import mujoco` quebrou, `MUJOCO_GL`/`PYOPENGL_PLATFORM` se comportam de forma estranha ou `MUJOCO_LOG.TXT` aparece onde não devia.
- Compilar C/C++ contra a `libmujoco` (gcc/CMake) ou escolher entre wheel, tarball, build CMake e AUR.
- Conferir o que o relatório do dono afirma em §3.1. (Renderização/viewer: `rendering-viewer.md`, mesma pasta.)

Legenda: ✔ testado aqui · ⚠ armadilha · Δ doc = a documentação diverge do medido · «não verificado» = sem como testar aqui (como verificar vem indicado).

## TL;DR para esta máquina
- **uv + wheel do PyPI** ✔: `cd /home/ondokai/Projects/MuJoCo && uv sync` (0,3 s com cache) cria `.venv` com CPython 3.13.15 (gerenciado pelo uv) e `mujoco 3.15.0`. Sem sudo, sem compilar, sem `LD_LIBRARY_PATH`.
- **Versão**: 3.15.0 (2026-10-05) é a última estável. O projeto fixa `mujoco>=3.15,<3.16`: em 3.15.y só há *MINOR_OR_PATCH* (API retrocompatível); 3.16 pode quebrar (`docs/upstream/mujoco/VERSIONING.md`).
- **Pythons**: `Requires-Python >=3.10`. ✔ Instalei e simulei em 3.10.21, 3.11.16, 3.12.14, 3.13.15 e 3.14.7 (wheels cp310–cp314; mesmo resultado, `z=0.0996`). cp315 ✔ existe no PyPI (`echo mujoco==3.15.0 | uv pip compile --no-python-downloads --no-deps --python-version 3.15 --only-binary :all: -` resolve; com 3.16 falha; não instalado); free-threaded cp314t/cp315t só pela ficha Q1 (não testados). O lab exige `>=3.12`.
- **PEP 668**: o Python do sistema (3.14.7; `/usr/lib/python3.14/EXTERNALLY-MANAGED`) recusa `pip install mujoco` ✔ (`error: externally-managed-environment`; `uv pip install --system` também). Sem `.python-version`, o uv escolhe o 3.13.15 gerenciado, não o 3.14.7 do sistema ✔.
- **Pacotes**: não há `mujoco` nos repositórios (`cachyos*`, `core`, `extra`, `multilib`): ✔ `pacman -Ss mujoco` vazio (DB local de 2026-08-28). Só AUR (`paru` 2.1.0 instalado). `cmake`, `ninja` e `glfw` **não estão instalados**; o wheel não precisa deles.
- **O wheel não é um SDK C/C++**: sem `libmujoco.so`, `.pc`, config CMake, `simulate` nem `mjpython` (ver abaixo). Para C/C++: gcc contra o wheel (✔ §C/C++), ou AUR/tarball/build.

## Matriz de métodos de instalação (estado em 2026-10-07)
| Método | Comando | Prós | Contras | Estado |
|---|---|---|---|---|
| **Wheel PyPI** (Python) | `uv sync` · `uv pip install mujoco` | lib + bindings + plugins + headers + `mujoco.viewer` num pacote (30,2 MB); libs nativas só dependem da glibc | sem `simulate`, `.pc`, config CMake nem `libmujoco.so` | ✔ testado |
| **Tarball** GitHub Releases | `curl -LO https://github.com/google-deepmind/mujoco/releases/download/3.15.0/mujoco-3.15.0-linux-x86_64.tar.gz` · `tar xzf` | binários oficiais (flags afinadas, deps embutidas), `simulate`, samples, `model/`; sem instalador | atualização manual; conteúdo não verificado (nota 2) | não testado (31,9 MB; sha256 `319943b3…e497`, F21) |
| **Build CMake** do fonte (deps via FetchContent) | `sudo pacman -S cmake ninja` · `git clone https://github.com/google-deepmind/mujoco` · `cmake -S mujoco -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$HOME/.local/mujoco` · `cmake --build build` · `cmake --install build` | instala `lib/cmake/mujoco/mujocoConfig.cmake` (`mujoco::mujoco`); só a lib: `-DMUJOCO_BUILD_{EXAMPLES,SIMULATE,TESTS}=OFF -DMUJOCO_TEST_PYTHON_UTIL=OFF` (defaults ON, `docs/upstream/mujoco/CMakeLists.txt` l.43–47) | CMake ≥ 3.16, C++20, git e **rede**; compila devagar; sem `.pc` | não testado (sem fonte/rede) |
| AUR **`mujoco`** 3.15.0-1 (taotieren) | `paru -S mujoco` | prefixo `/usr`; mesma versão do wheel; atualizado em 2026-10-05 | compila do fonte (CMake+Ninja, rede); makedepends cmake, glfw, git, libx*, ninja, mold; arquivos instalados só inferidos (config em `/usr/lib/cmake/mujoco`, sem `.pc`) | não testado |
| AUR **`mujoco-bin`** 3.14.0-1 (elanglois) | `paru -S mujoco-bin` | sem compilar (reempacota o tarball oficial); Provides/Conflicts `mujoco` | **1 versão atrás** do wheel; headers em `/usr/mujoco`, não `/usr/include` (inferido: exigiria `-I/usr`) | não testado |
| AUR **`python-mujoco`** 3.3.7-1 (kidofcubes) | — | — | ⚠ *out-of-date* desde 2025-12-18; compila bindings 3.3.7 contra o `mujoco` do sistema; declara LGPL3 (upstream: Apache-2.0) | **evitar** (`mujoco-git`: órfão, 2.2.2) |

1. Δ doc: o README (3.15.0) diz que os wheels Linux miram `manylinux2014`; as tags reais são `manylinux_2_27`+`manylinux_2_28` ✔ (arquivo `WHEEL`; changelog 3.3.5): glibc ≥ 2.27 basta (símbolos medidos; aqui 2.44). MuJoCo exige CPU com AVX (doc `programming/index.rst`; ✔ avx/avx2 aqui).
2. Δ doc: `docs/upstream/mujoco/doc/programming/index.rst` ("Getting started") descreve o tarball como `bin doc include model sample`; a doc do Unity e o PKGBUILD do `mujoco-bin` citam `lib/` e `simulate/`. **Não verificado** se traz `lib/cmake/mujoco`: `tar tzf mujoco-3.15.0-linux-x86_64.tar.gz | grep -E 'cmake|\.pc$|libmujoco|simulate'`.
3. Estados do AUR: ficha Q1 (consulta de 2026-10-07; mudam rápido). Repositórios do CachyOS: só o DB local foi lido ✔; os `-v4` não estão configurados (CPU = x86-64-v3). Bindings do fonte (só para modificá-los): `bash make_sdist.sh` e `MUJOCO_PATH=… MUJOCO_PLUGIN_PATH=… pip install mujoco-x.y.z.tar.gz` (`docs/upstream/mujoco/doc/python.rst` l.775–849; não testado).
4. Headers e lib têm de ter a mesma versão: `if (mjVERSION_HEADER != mj_version())` (doc; ✔ `3015000`).
5. **Decisão rápida**: só Python → wheel via uv. C/C++ neste PC sem sudo → gcc ou prefixo CMake falso contra o wheel (mesma versão do `.venv`). C/C++ de produção ou `simulate` oficial → AUR `mujoco` (mesma versão do wheel) ou build CMake em prefixo próprio; tarball só depois do `tar tzf` acima.

## O que o wheel contém — e o que não contém
`site-packages/mujoco` do `.venv` (somente leitura): RECORD com 300 entradas; 80 MiB em disco (`du`), 51 MiB só em `experimental/` (Studio/Filament).
| Item | No wheel? | Evidência |
|---|---|---|
| `mujoco/libmujoco.so.3.15.0` (6,3 MB) | ✔ sim | SONAME = nome do arquivo; NEEDED só `libdl libm libpthread libc librt` (sem libstdc++/GL); símbolos GLIBC ≤ 2.27 |
| 11 extensões pybind11 (`_structs _functions _specs _render _render_filament _rollout _simulate _callbacks _constants _enums _errors`) | ✔ | RUNPATH `$ORIGIN`: acham a lib sem `LD_LIBRARY_PATH` (✔ `env -i`) |
| 4 plugins `mujoco/plugin/lib{actuator,elasticity,sdf_plugin,sensor}.so` | ✔ | carregados no `import` (`mujoco.PLUGINS_DIR`, `PLUGIN_HANDLES`=4): `mujoco.pid`, `mujoco.elasticity.cable`, `mujoco.sdf.{bolt,bowl,gear,nut,torus}`, `mujoco.sensor.touch_grid` |
| 72 headers (`mujoco/include/mujoco/`: 16 na raiz + `experimental/` + `render/`) | ✔ | ⚠ `mujoco.HEADERS_DIR` = `…/include/mujoco`; o `-I` é o diretório **pai** |
| módulos Python: `mujoco.viewer` (`python -m mujoco.viewer`), `rendering`, `egl`/`glfw`/`osmesa`, `rollout`, `minimize`, `msh2obj`, `introspect`, `experimental.studio`, `sysid`, `usd` | ✔ | extras `mujoco[sysid]` (+8 pacotes no venv do lab) e `mujoco[usd]` (+`usd-core`) ✔ dry-run |
| dependências Python | ✔ | `absl-py`, `etils[epath]`, `glfw`, `numpy`, `pyopengl`, `websockets>=13` (`uv tree`); `libglfw.so` x11/wayland vem do pacote PyPI `glfw` |
| `libmujoco.so` (sem versão) | ✘ | `-lmujoco` falha: use `-l:libmujoco.so.3.15.0` |
| `mjpython` | ✘ só macOS | `docs/upstream/mujoco/python/setup.py`: `scripts=[mjpython.py] if Darwin else []`; sem `entry_points`; `.venv/bin` sem ele. Δ doc: `doc/python.rst` l.93–97 diz «instalado com o pacote» (só no macOS) |
| `simulate`, samples, `model/` | ✘ | nenhum executável no RECORD (só tarball/AUR) |
| `mujoco.pc` · `lib/cmake/mujoco/*.cmake` | ✘ | upstream nunca instala `.pc`; sem config, `find_package(mujoco)` falha (§C/C++) |

## Receita com uv
✔ Executada numa **cópia descartável** do projeto (`pyproject.toml` + `uv.lock`); o `.venv` real não foi tocado. `uv` vem do pacman (0.12.7).
```bash
cd /home/ondokai/Projects/MuJoCo
uv sync        # Using CPython 3.13.15 / Creating virtual environment at: .venv / Installed 28 packages
uv run python -c "import mujoco; print(mujoco.__version__, mujoco.mj_version())"   # 3.15.0 3015000
.venv/bin/python .agents/mujoco-agent-skill/scripts/env_check.py                   # diagnóstico (EGL, GPU, grupos)
.venv/bin/python - <<'EOF'                                                          # qual libmujoco o processo carregou?
import mujoco
print(len(mujoco.PLUGIN_HANDLES), "plugins |", [l.split()[-1] for l in open("/proc/self/maps") if "libmujoco" in l][0])
EOF
```
| Objetivo | Comando | Observação |
|---|---|---|
| Reprodutível / CI | `uv sync --locked` | ✔ erro se o `uv.lock` estiver defasado; `--frozen` usa o lock sem checar |
| Sem rede | `uv sync --locked --offline` | ✔ usa o cache do uv (`uv cache dir`); falha se faltar alguma wheel |
| Recriar do zero | `rm -rf .venv && uv sync --locked` | |
| Grupos opcionais | `uv sync --group viz` · `--group urdf --group rl` · `--all-groups` | `default-groups=["dev"]`. Dry-run sobre o `dev`: viz +4 pacotes, urdf +12, rl +18, gpu +25 (`jax[cuda13]` + `nvidia-*-cu13`: pesado), todos +56 |
| Outro Python | `uv sync --python 3.14` | ✔ recria o `.venv` com o 3.14.7 do sistema; mujoco, numpy, scipy, matplotlib, imageio, pillow importam. Fixar: `uv python pin 3.13` (`.python-version`) |
| Atualizar | editar `mujoco>=3.15,<3.16` · `uv lock --upgrade-package mujoco && uv sync` | ✔ idempotente hoje (3.15.0 é a última) |
| cwd fora da raiz | `uv run --project /home/ondokai/Projects/MuJoCo python script.py` | ✔ preserva o cwd (evita `MUJOCO_LOG.TXT` na raiz) |
| Fora de projeto | `uv venv --python 3.13 && uv pip install mujoco` | ✔ `.venv` local, `import` ok |
| Projeto novo | `uv init --bare --python 3.13 && uv add "mujoco>=3.15,<3.16" numpy` | ✔ |
| Efêmero | `uv run --no-project --with mujoco python -c "import mujoco"` | ✔ |

⚠ `uv sync` é **exato**: remove tudo que não está nos grupos pedidos (✔ sumiram o `rerun-sdk` de `--group viz` e um `tqdm` de `uv pip install`). `uv run` não remove. Para manter: passe todos os `--group` juntos ou use `uv sync --inexact`.

## Variáveis de ambiente (efeito ✔ medido; lidas por grep no wheel)
| Variável | Lida por / quando | Efeito |
|---|---|---|
| `LD_LIBRARY_PATH` | loader | ✔ desnecessária (`env -i` + `import mujoco` ok; RUNPATH `$ORIGIN`). ⚠ mas **vence o RUNPATH**: uma cópia de `libmujoco.so.3.15.0` nela é a carregada (✔ `/proc/self/maps`). Em C serve de alternativa ao `-Wl,-rpath` |
| `MUJOCO_GL` | `mujoco/rendering/classic/gl_context.py` (no wheel), **só no `import mujoco`** | `egl` ✔ render offscreen na GPU; vazio/`glfw`/`glx`/`on`/`1` → GLFW (`GLContext` = `mujoco.glfw`; precisa de display; não testado: sem janelas); `osmesa` ✔ **quebra o import** (sem libOSMesa); `disable`/`off`/`0` ✔ import ok, `Renderer(...)` → `AttributeError`; valor inválido ✔ `RuntimeError`. Sem distinção de maiúsculas/espaços |
| `PYOPENGL_PLATFORM` | PyOpenGL; `mujoco.egl` | ✔ com `MUJOCO_GL=egl` o mujoco a define como `egl` se vazia; se ≠ `egl`, o `ImportError` é engolido e `mujoco.Renderer`/`GLContext` **somem** |
| `MUJOCO_EGL_DEVICE_ID` | `mujoco.egl`, 1º `Renderer` | ✔ índice do device EGL. Aqui: vazio/0 = RTX 4070 (driver 610.57.04), 1 = falha (`ImportError: Cannot initialize a EGL device display`), 2 = Mesa Intel RPL-S, 3 = llvmpipe (CPU). >3 → `RuntimeError`; não inteiro → `ValueError` |
| `MUJOCO_PLUGIN_PATH`, `MUJOCO_PATH` | só `docs/upstream/mujoco/python/setup.py` (build do sdist) | ✔ **sem efeito em runtime**, em Python e C: o `import` já carrega os plugins do wheel. Em C: `mj_loadAllPluginLibraries(dir, NULL)` (✔ 0 → 8 plugins) |
| `MUJOCO_LOG_TOPICS` | libmujoco, lida 1× na partida | ✔ lista (sem distinção de maiúsculas) de `time_stp`,`time_cmp`,`sleep` → bits 1/2/4 em `mujoco.MjLogConfig.get().topics`; inválido é ignorado; em C `time_cmp` imprime «INFO: compile time (ms)» |
| `MUJOCO_LOG` | — | ✔ **não existe**. O log padrão é `MUJOCO_LOG.TXT` no **cwd** (+ stderr), criado na 1ª mensagem; ver Armadilhas |
| `MUJOCO_GL_DEBUG` | string em libmujoco (sem doc) | saída idêntica no teste: não verificado |
| `PYGLFW_LIBRARY_VARIANT`, `XDG_SESSION_TYPE` | pyGLFW, no `import glfw` | ✔ sessão `wayland` (esta) → `glfw/wayland/libglfw.so`; `x11` → `glfw/x11/libglfw.so` |
| `MUJOCO_STUDIO_ASSETS_DIR`, `MUJOCO_WEB_VIEWER_DIST` | `experimental/studio` | lidas no código do wheel; não testado (viewer: outra referência) |
| `CMAKE_PREFIX_PATH`, `mujoco_DIR` | CMake `find_package` | prefixo / dir do `mujocoConfig.cmake` (✔ abaixo) |
| `UV_PROJECT_ENVIRONMENT` | uv | ✔ aponta o venv do projeto para outro caminho (usei para testar sem tocar o `.venv`) |

## C/C++: `find_package`, pkg-config e compilar contra o wheel
**Caminho oficial**: o upstream instala `lib/cmake/mujoco/{mujocoConfig,mujocoConfigVersion,mujocoTargets}.cmake` (`docs/upstream/mujoco/CMakeLists.txt` l.326–353; `NAMESPACE mujoco::`) e **nenhum `.pc`**. Os samples usam `find_package(mujoco REQUIRED)` e `target_link_libraries(x mujoco::mujoco)`; no código, `#include <mujoco/mujoco.h>`. Fora de `/usr`: `-DCMAKE_PREFIX_PATH=<prefixo>` ou `-Dmujoco_DIR=<prefixo>/lib/cmake/mujoco`. Use `PRIVATE` (não `PUBLIC`) em executáveis.

**`pkg_search_module(MUJOCO mujoco)` não funciona**: o `cmake/` do upstream só tem módulos `.cmake` e `mujocoConfig.cmake.in` (sem `.pc.in`) e `dist/` não tem `.pc` (F24/F25; nem o `CMakeLists.txt` espelhado nem a doc citam pkg-config ✔ grep). ✔ `pkg-config --exists mujoco` → exit 1; no CMake 4.4.4 dá `MUJOCO_FOUND=''` e o `target_link_libraries(hello PUBLIC mujoco::mujoco)` seguinte falha («Target "hello" links to: mujoco::mujoco but the target was not found»); com `REQUIRED`: «None of the required 'mujoco' found». Sem config instalado, `find_package(mujoco CONFIG REQUIRED)` também falha («Could not find a package configuration file provided by "mujoco"… set "mujoco_DIR"»).

**Compilar e rodar um C mínimo contra a lib/headers do wheel** (✔ gcc 16.2.1 sem warnings com `-Wall -Wextra`; `g++ -std=c++17` e `clang` também):
```bash
W=$(mktemp -d) && cd "$W"                       # diretório descartável, fora da raiz (MUJOCO_LOG.TXT, build/…)
PY=/home/ondokai/Projects/MuJoCo/.venv/bin/python
cat > hello.c <<'EOF'
#include <stdio.h>
#include <mujoco/mujoco.h>

int main(void) {
  if (mjVERSION_HEADER != mj_version()) return 2;        // headers ≠ biblioteca
  const char* xml = "<mujoco><worldbody><geom type='plane' size='1 1 .1'/>"
      "<body pos='0 0 1'><freejoint/><geom size='.1'/></body></worldbody></mujoco>";
  char err[1024] = "";
  mjSpec* spec = mj_parseXMLString(xml, NULL, err, sizeof err);
  mjModel* m = spec ? mj_compile(spec, NULL) : NULL;
  if (!m) { fprintf(stderr, "erro: %s\n", spec ? mjs_getError(spec) : err); return 1; }
  mjData* d = mj_makeData(m);
  for (int i = 0; i < 500; i++) mj_step(m, d);             // 1 s (timestep padrão 2 ms)
  printf("MuJoCo %s | t=%.3f z=%.4f nq=%lld\n", mj_versionString(), d->time, d->qpos[2], (long long)m->nq);
  mj_deleteData(d); mj_deleteModel(m); mj_deleteSpec(spec);
  return 0;
}
EOF
SP=$("$PY" -c 'import mujoco, os; print(os.path.dirname(mujoco.__file__))')
gcc -Wall -Wextra -O2 hello.c -o hello -I"$SP/include" -L"$SP" -l:libmujoco.so.3.15.0 -Wl,-rpath,"$SP" -lm
env -i ./hello          # sem LD_LIBRARY_PATH: o RUNPATH resolve a lib → «MuJoCo 3.15.0 | t=1.000 z=0.0996 nq=7»
```
⚠ `mjModel.nq/nv/nbody…` são `mjtSize` (`int64_t`) desde a 3.5.0: `printf("%d")` gera `-Wformat`; use `%lld` + cast. Link: `-l:libmujoco.so.3.15.0` (sem `-lmujoco`), `-I` = `$SP/include`, `-Wl,-rpath` (ou `LD_LIBRARY_PATH`).

**`find_package` + `mujoco::mujoco` sobre o wheel** (atalho **não oficial**, ✔ CMake 4.4.4; `cmake`/`ninja` não estão instalados aqui: `sudo pacman -S cmake ninja`, ou `uv pip install cmake ninja` num venv). Cria um «prefixo» falso com symlinks para o wheel; o `CMakeLists.txt` é o mesmo que usaria com AUR/tarball/build (refaça o bloco ao atualizar o mujoco). Continua no shell e diretório do bloco anterior (`$W`, `$PY`, `hello.c`):
```bash
cd "$W"
cat > CMakeLists.txt <<'CML'
cmake_minimum_required(VERSION 3.16)
project(hello C)
find_package(mujoco CONFIG REQUIRED)
add_executable(hello hello.c)
target_link_libraries(hello PRIVATE mujoco::mujoco)
CML
SP=$("$PY" -c 'import mujoco, os; print(os.path.dirname(mujoco.__file__))')
P=$PWD/build/mujoco-wheel                       # "prefixo" falso: só symlinks para o wheel
mkdir -p "$P/lib/cmake/mujoco" "$P/include"
ln -sfn "$SP/include/mujoco" "$P/include/mujoco"
ln -sf "$SP/libmujoco.so.3.15.0" "$P/lib/libmujoco.so.3.15.0"
cat > "$P/lib/cmake/mujoco/mujocoConfig.cmake" <<'CFG'
get_filename_component(_p "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
if(NOT TARGET mujoco::mujoco)
  add_library(mujoco::mujoco SHARED IMPORTED)
  set_target_properties(mujoco::mujoco PROPERTIES
    IMPORTED_LOCATION "${_p}/lib/libmujoco.so.3.15.0" IMPORTED_SONAME libmujoco.so.3.15.0
    INTERFACE_INCLUDE_DIRECTORIES "${_p}/include")
endif()
CFG
cmake -S . -B build -DCMAKE_PREFIX_PATH="$P" && cmake --build build && env -i ./build/hello
```
Também ✔ com `-Dmujoco_DIR="$P/lib/cmake/mujoco"`. O config oficial ainda faz `find_dependency(OpenGL)` (F23); o atalho não precisa (a lib não liga GL).

## Correções ao relatório do usuário (§3.1)
`docs/relatorio-tecnico-original.md` §3.1 · auditoria completa na ficha Q1.
| # | Afirmação do relatório | Veredito | Correção ✔ |
|---|---|---|---|
| 1 | O wheel da DeepMind traz os bindings **e** as bibliotecas C dinâmicas | **Correta** | Wheel cp313: 11 extensões, `libmujoco.so.3.15.0` (SONAME igual), 4 plugins, 72 headers; a doc diz que a cópia da lib vem no pacote. Ressalva: não é pacote de desenvolvimento (sem `libmujoco.so`, `.pc`, config CMake, `simulate`, `mjpython`) |
| 2 | O AUR oferece `python-mujoco` «empacotando os binários do sistema»; venv + wheel é a prática moderna | **Parcial** | Existe, mas 3.3.7-1, *out-of-date* desde 2025-12-18, e **não** empacota binários: compila bindings 3.3.7 contra o `mujoco` do sistema (LGPL3 declarado), incoerente com o AUR `mujoco` 3.15.0-1. Não há `mujoco` nos repos do Arch/CachyOS (✔ `pacman -Ss`). Certo: venv/uv + wheel (PEP 668 ✔) |
| 3 | CMake: `pkg_search_module(MUJOCO mujoco)` + `target_link_libraries(my_app PUBLIC mujoco::mujoco)` | **Parcial** | Mistura mecanismos: não há `.pc` (✔ falha, ver §C/C++) e `pkg_search_module` não cria `mujoco::mujoco`. Correto: `find_package(mujoco CONFIG REQUIRED)` + `target_link_libraries(app PRIVATE mujoco::mujoco)` (`PUBLIC` é desnecessário em executável) |
| 4 | O venv evita as antigas manipulações de `LD_LIBRARY_PATH` | **Parcial** | Conclusão certa, causa errada: quem dispensa é o RUNPATH `$ORIGIN` do wheel (✔ `env -i`) e o abandono do mujoco-py (*deprecated*, ≤ 2.1.0), que exigia `LD_LIBRARY_PATH=$HOME/.mujoco/mujoco210/bin`. O venv é isolamento + exigência do PEP 668. E `LD_LIBRARY_PATH` ainda **vence** o RUNPATH se tiver outra `libmujoco.so.3.15.0` |
| 5 | «Garantir gcc-libs, glibc, ninja, cmake e glfw»; CachyOS recompila para x86-64-v3 | **Parcial** | Wheel: basta a glibc (NEEDED ✔); o pacote PyPI `glfw` embute a `libglfw.so` (x11+wayland ✔). cmake/ninja/glfw só valem para build do fonte (e **não** estão instalados aqui). CachyOS recompila v3/v4/Zen4 só pacotes **de repositório** (✔ cmake/ninja/glfw vêm de `cachyos-extra-v3`), não o wheel nem o tarball |

## Aprofundar (docs locais)
- `docs/upstream/mujoco/doc/python.rst`: Installation (l.34), Building from source/sdist (l.775), extra `usd` (l.964). `docs/upstream/mujoco/doc/programming/index.rst`: Getting started (l.44), Building from source (l.92), Versions (l.196). `doc/overview.rst` **não** tem seção de instalação (✔ grep).
- `docs/upstream/mujoco/doc/programming/simulation.rst`: «Errors, warnings, logging» (l.893; `MUJOCO_LOG_TOPICS` l.1016). `docs/upstream/mujoco/CMakeLists.txt`: opções (l.43–51), install/export (l.313–361); `docs/upstream/mujoco/sample/cmake/FindOrFetch.cmake`.
- `docs/upstream/mujoco/doc/changelog.rst`: 3.15.0 (l.5), Python 3.15 em 3.13.0 (l.137), Python 3.14 em 3.8.0 (l.803), log unificado em 3.10.0 (l.593), `mjModel` 64-bit em 3.5.0 (l.1061). Busca: `docs_search.py --changelog <termo>`.
- Diagnóstico: `.agents/mujoco-agent-skill/scripts/env_check.py`. Lacunas abertas da ficha Q1: conteúdo do tarball oficial, arquivos instalados pelo AUR, repos CachyOS v4.

## Armadilhas
| Sintoma | Causa | Correção |
|---|---|---|
| `error: externally-managed-environment` | `pip install` no Python do sistema (PEP 668) | `uv sync` / `uv venv`; nunca `pip` fora de venv |
| O venv saiu 3.13 (ou 3.14) e você queria o outro | uv prefere Python gerenciado; sem `.python-version` | `uv python pin 3.13` ou `uv sync --python 3.14` |
| Pacotes de `--group viz` / `uv pip install` sumiram | `uv sync` é exato | todos os `--group` na mesma chamada, ou `uv sync --inexact`; `uv run` não remove |
| Apareceu um Python que você não pediu em `uv python list` (ex.: `3.15.0rc1`) | `uv pip compile --python-version 3.15` **baixa** um CPython gerenciado se não houver ✔ (35 MiB em `~/.local/share/uv/python`) | `--no-python-downloads` ✔; desfazer: `uv python uninstall 3.15` ✔ |
| `RuntimeError: invalid value for environment variable MUJOCO_GL` no `import` | valor fora de `egl glfw glx osmesa on/off/disable…` | corrija ou `unset MUJOCO_GL` |
| `AttributeError: 'NoneType' object has no attribute 'glGetError'` no `import` | `MUJOCO_GL=osmesa` sem libOSMesa | `MUJOCO_GL=egl` (CPU: `MUJOCO_EGL_DEVICE_ID=3` = llvmpipe aqui) |
| `module 'mujoco' has no attribute 'Renderer'`, sem erro no `import` | `PYOPENGL_PLATFORM` ≠ `egl` com `MUJOCO_GL=egl` (`ImportError` engolido) ou `MUJOCO_GL=disable` | `unset PYOPENGL_PLATFORM`; veja `mujoco.GLContext.__module__` |
| `MUJOCO_GL=egl` no script, mas usa GLFW | `MUJOCO_GL` é lido só no `import mujoco` | defina **antes** do import ou `MUJOCO_GL=egl uv run …` |
| `ImportError: Cannot initialize a EGL device display` | `MUJOCO_EGL_DEVICE_ID` aponta para device inutilizável (aqui: 1) | use 0 (NVIDIA) ou remova a variável |
| `MUJOCO_LOG.TXT` na raiz do projeto | 1º aviso/erro grava no **cwd**; não há env var | cwd fora da raiz ou `cfg = mujoco.MjLogConfig.get(); cfg.logto_file = False; mujoco.MjLogConfig.set(cfg)` ✔ (stderr continua) |
| Python carrega outra `libmujoco` que a do wheel | `LD_LIBRARY_PATH` vence o RUNPATH `$ORIGIN` quando há arquivo de mesmo SONAME | `unset LD_LIBRARY_PATH`; confira com o bloco `/proc/self/maps` da Receita |
| `MUJOCO_PLUGIN_PATH` «não faz nada» | só vale no build do sdist | plugins do wheel já carregam no `import`; em C `mj_loadAllPluginLibraries` |
| `ld: não foi possível localizar -lmujoco` | o wheel só tem `libmujoco.so.3.15.0` | `-l:libmujoco.so.3.15.0` ou symlink `libmujoco.so` num diretório **seu** |
| `error while loading shared libraries: libmujoco.so.3.15.0` (exit 127) | binário sem RUNPATH | `-Wl,-rpath,"$SP"` (ou `LD_LIBRARY_PATH="$SP"`) |
| `fatal error: mujoco/mujoco.h: No such file` | `-I"$(…mujoco.HEADERS_DIR)"` já termina em `include/mujoco` | `-I"$SP/include"` |
| `-Wformat` / valor errado ao imprimir `m->nq` | `mjModel` usa `mjtSize` (int64) desde 3.5.0 | `%lld` + `(long long)` |
| `MUJOCO_FOUND=''` e «`mujoco::mujoco` … target was not found» | `pkg_search_module`: sem `.pc` | `find_package(mujoco CONFIG REQUIRED)` + AUR/tarball/build ou o atalho acima |
| Binário C quebra depois de `uv sync` trocar a versão do mujoco | o SONAME carrega a versão completa (`libmujoco.so.3.15.0`) | recompile e refaça o prefixo falso |
| `mjpython: command not found`, `simulate` ausente | `mjpython` é só macOS; `simulate` só no tarball/AUR | no Linux use `python`; `simulate` → tarball/AUR (conteúdo não verificado) |
