#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/view.py — visualizador 3D com HUD KPI (8 linhas) da rede PPO do drone.

Abre o viewer PASSIVO do MuJoCo (`mujoco.viewer.launch_passive`) sobre o modelo do `env.py` e deixa a
política treinada pilotar: a cada passo de decisão (50 Hz = 10 passos de física a 500 Hz) lê a observação
(16, normalizada), pede a ação à rede (`predict(obs, deterministic=True)`), aplica-a pelo `env.step` e
desenha no ecrã o que a rede VÊ e o que ela MANDA — mais z(t) contra a linha do alvo, yaw_err(t) e os
4 canais de ação.

    uv run --group hover-rl python experiments/09_drone_hover_rl/view.py              # melhor de out/runs/*/
    uv run --group hover-rl python experiments/09_drone_hover_rl/view.py --model out/runs/x/best_model.zip
    uv run --group hover-rl python experiments/09_drone_hover_rl/view.py --sem-janela --passos 300
    uv run --group hover-rl python experiments/09_drone_hover_rl/view.py --rapido --segundos 6
    uv run --group hover-rl python experiments/09_drone_hover_rl/view.py --vento-inicial 3,90
    uv run --group hover-rl python experiments/09_drone_hover_rl/view.py --controlo out/controle_vento.json

HUD — 8 linhas KPI + 2 de rodapé (<=60 colunas, só ASCII; a fonte é monoespaçada, alinhar com f"{v:+8.3f}"):
  1  obs dp    [0:3] (p−p_alvo)/1 m .... + |v| em m/s ......... o que a rede VÊ
  2  obs rpy   [3:6] roll/pitch/pi + [yaw/pi] (o yaw vai entre [ ]) + |w| em rad/s
  3  acao      os 4 canais Box(-1,1) -> empuxo em N ........... o que a rede MANDA
  4  pos       z | alvo | dz | dxy (tudo em m)
  5  yaw_err   em GRAUS | wz em rad/s | |a_prev| (norma de obs[12:16])
  6  retorno   | ep | passo/max | t em s
  7  vento     vel (m/s) @ azimute (graus) elev (graus) | último episódio (auto-reset/manual)
  8  modelo
  9  rodapé    `episodio terminado (retorno X) - R para reiniciar` — SÓ com o episódio parado
 10  rodapé    legenda das teclas do vento (sempre)

  CAUSA RAIZ da sobreposição antiga (19 linhas ≈ 627 px): em `Handle.set_texts` o 1.º argumento é um
  `mjtFont` — 0 = mjFONT_NORMAL, 1 = mjFONT_SHADOW, 2 = mjFONT_BIG — e NÃO uma escala: `mjtFontScale` é
  outra enumeração (50, 100, …, 300) e passar `mjFONTSCALE_100` (= 100) não encolhe nada. A escala real
  vem do PPI do monitor, cortada a [100, 300]% (≈150% nesta máquina ≈ 33 px por linha → 10 linhas ≈ 330
  px). A única via de a encolher SEM C é o seletor `Font` do painel esquerdo → `show_left_ui=True`
  (escolha `Font: 50%` para um HUD ainda mais compacto). O overlay trunca a 500 caracteres por coluna em
  silêncio e só tem glifos ASCII 32-126; uma entrada por gridpos (duas entradas no mesmo gridpos
  sobrepõem-se) — este painel usa uma só, em mjGRID_TOPLEFT.

FIM DE EPISÓDIO — SEM LOOP AUTOMÁTICO: quando o episódio acaba (`terminated` OU `truncated`) a física PARA
(nada de `env.step`) e a janela fica VIVA à espera do dono: o rodapé passa a `episodio terminado (retorno
X) - R para reiniciar` e só a tecla R faz `env.reset` (mesmo seed/jitter/vento do início) e retoma.
`--loop` restaura o auto-reset antigo (com log por episódio e `--episodios N`). No `--sem-janela` não há
teclas: o 1.º episódio acabado imprime `episodio terminado (retorno X) - R para reiniciar (modo janela)` e o
processo sai com exit 0 (sem 2.º episódio); com `--loop` corre até `--passos`/`--episodios`.

VENTO AO VIVO (contrato v2 do `env.py`): `--controlo CAMINHO` (por omissão `out/controle_vento.json`) é
relido a cada 5 passos de decisão e só quando o mtime muda, e aplicado com
`env.definir_vento(vel, azimute, elevacao)`; `"ativo": false` → vento 0. Formato do ficheiro:
`{"vel": m/s, "azimute": graus, "elevacao": graus, "ativo": bool}` (azimute 0° → +x, 90° → +y).
`--vento-inicial vel,azim[,elev]` arranca com vento sem ficheiro nenhum (se o ficheiro existir, é ele que
manda, porque é relido no 1.º passo). O HUD mostra sempre o vento ATIVO (`info["vento_vel"]`/`vento_azim`)
e a elevação sempre que há vento — vê-se assim a 3.ª componente que o teclado preserva.

VENTO PELO TECLADO (tempo real, ao lado do ficheiro): `[`/`]` tiram/põem 0,5 m/s (cortado a [0, 5] m/s),
`,`/`.` rodam o azimute em ∓/±15° (com wrap para [0, 360)) e `v` põe o vento a zero. O valor de partida é o
vento ATIVO lido do próprio `env` (`env.vento_atual` → polar), não uma cópia nossa: o ficheiro e o teclado
mexem no mesmo sítio. A ELEVAÇÃO é preservada nas mudanças de força/azimute (e `v` seguido de `]` volta à
mesma direção). Cada toque aplica logo `env.definir_vento` e o HUD seguinte já o mostra — inclusive com o
episódio parado. Cuidado: `[`/`]` são também o `Cycle cameras` do viewer (tabela de ajuda do `_simulate`);
o adapter C++ (`docs/upstream/mujoco/python/mujoco/simulate.cc`, `UIAdapterWithPyCallback::OnKey`) trata a
tecla E chama o nosso callback, por isso o vento muda na mesma — a câmara é que roda com ele. As outras
teclas novas (`,` `.` `v` `R` = 44/46/86/82) não colidem com as do viewer (ESPAÇO, `+`/`-`, setas, Tab,
`[`/`]`, Esc, Page Up, F1-F5).

FIGURAS (3; `set_texts`/`set_figures` reenviados antes de CADA `sync()`): z(t) com a linha do alvo,
yaw_err(t) em rad com a linha do zero e os 4 canais de ação — em 2 colunas quando a janela é larga e
empilhadas numa coluna quando é estreita (o `MjvFigure` não tem subplots). Numa janela baixa demais para
as 3, mostram-se só as primeiras (prioridade z > yaw_err > ação) e nenhum rect sai do viewport.

Teclado (foco na janela): ESPAÇO pausa/retoma · R reinicia · `[` `]` `,` `.` `v` mexem no vento ·
Q ou Esc fecha.

ERROS SEM TRACEBACK: `--alvo-z` é validado AQUI contra a faixa que o `HoverEnv` aceita (`ALVO_Z_MIN` ..
`ALVO_Z_MAX`, hoje 0.10-2.90 m) — fora dela sai mensagem em stderr e exit 2, como nos restantes erros de
argumentos; o `HoverEnv` recusar o alvo (2.ª barreira) também é exit 2. Se a física divergir a meio (vento
absurdo no ficheiro de --controlo → `RuntimeError` de sanidade do `HoverEnv`) a mensagem diz para usar
`definir_vento` com um valor são e o processo sai com exit 1 (na janela, depois de fechar o viewer).

`--sem-janela`: o mesmo ciclo SEM viewer (nada de GLFW/GL — prova-se por `sys.modules`), com o painel KPI
impresso em texto, um rasto do estado a cada 20 passos e exit 0 — é o modo dos verificadores.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

# Ordem intencional (por isso o I001 fica desligado nesta linha): o `mjkit` define MUJOCO_GL=egl ANTES de
# `import mujoco`, como manda o laboratório.
from lab import mjkit  # noqa: F401, I001
# ALVO_Z_MIN/ALVO_Z_MAX: a faixa que o `HoverEnv` aceita — o CLI valida-a aqui para dar erro claro (exit 2)
from env import ALVO_Z_MAX, ALVO_Z_MIN, HoverEnv  # (obs 16 normalizada, ação Box(-1,1)⁴)

import mujoco
import numpy as np

# ---------------------------------------------------------------------------------------------- constantes
JANELA_S = 10.0                 # s de histórico visível nas figuras (= 1 episódio de 10 s)
FIG_LARG, FIG_ALT = 400, 220    # px-alvo de cada figura (limitado pelo viewport)
FIG_LARG_MIN = 200              # px mínimo de largura (abaixo disto o gráfico não se lê)
FIG_MIN = 64                    # px mínimo "legível" de uma figura (decide QUANTAS cabem empilhadas)
FIG_MIN_ABS = 16                # px abaixo disto não vale a pena desenhar (janela minúscula → sem figuras)
FIG_Z_GAMA_MIN = 0.25           # m — gama Y mínima da figura z(t) (com alvo a 0 m não colapsa no chão)
MARGEM = 8                      # px entre figuras e entre figura e borda
PASSOS_OMISSAO = 300            # passos de decisão do modo `--sem-janela` (sem --loop para no 1.º episódio)
PASSOS_CONTROLO = 5             # de quantos em quantos passos de decisão se olha para o ficheiro do vento
PASSOS_RASTRO = 20              # de quantos em quantos passos o modo `--sem-janela` imprime o rasto
# Códigos GLFW (o `key_callback` do viewer entrega-os tal e qual; o adapter C++ chama o callback em TODA a
# tecla premida, DEPOIS de a tratar — ver `docs/upstream/mujoco/python/mujoco/simulate.cc`,
# `UIAdapterWithPyCallback::OnKey`). O viewer usa: ESPACO, + - , setas, Tab, `[` `]` (cycle cameras), Esc,
# Page Up e F1-F5 (tabela de ajuda do `_simulate`); as teclas deste HUD não colidem, excepto `[` `]`, que
# também rodam a câmara (o vento muda na mesma — o callback é sempre chamado).
TECLA_ESPACO, TECLA_Q, TECLA_R, TECLA_V, TECLA_ESC = 32, 81, 82, 86, 256
TECLA_ABRE_COLCHETE, TECLA_FECHA_COLCHETE = 91, 93       # [ ] = força do vento −/+ 0,5 m/s
TECLA_VIRGULA, TECLA_PONTO = 44, 46                      # , . = azimute do vento −/+ 15°
AJUSTE_FORCA, FORCA_MAX = 0.5, 5.0   # m/s por toque em `[`/`]` e teto do vento mexido pelo teclado
AJUSTE_AZIM = 15.0                   # graus por toque em `,`/`.`
LEGENDA_TECLAS = "teclas: [ ] forca  , . azim  v=parar  R=reiniciar"
HUD_LINHAS, HUD_COLUNAS = 8, 60   # teto do painel (receita CoALA #7980: 6-8 KPIs, <=60 colunas)
HUD_RODAPE = 2                    # linhas de rodapé no painel (estado + legenda das teclas), <=60 colunas
CONTROLO_OMISSAO = _AQUI / "out" / "controle_vento.json"
FONTE_HUD = mujoco.mjtFont.mjFONT_NORMAL      # 1.º arg de set_texts = mjtFont, NÃO escala (ver docstring)
GRID_HUD = mujoco.mjtGridPos.mjGRID_TOPLEFT   # uma única entrada por gridpos


def _relativo(caminho: Path) -> str:
    """Caminho relativo à raiz do laboratório quando possível (leitura mais curta no `--help`)."""
    try:
        return str(caminho.relative_to(_RAIZ))
    except ValueError:
        return str(caminho)


def _nome_curto(caminho: Path) -> str:
    """`pasta/ficheiro.zip` — o suficiente para identificar o modelo no painel."""
    return f"{caminho.parent.name}/{caminho.name}"


# ---------------------------------------------------------------------------------------------- modelo
def modelo_por_omissao() -> Path:
    """`best_model.zip` mais recente em `out/runs/*/`; na falta dele, o `final.zip` mais recente."""
    for nome in ("best_model.zip", "final.zip"):
        pasta = _AQUI / "out" / "runs"
        candidatos = sorted(pasta.glob(f"*/{nome}"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidatos:
            return candidatos[0]
    raise SystemExit(
        f"[view] nenhum modelo em {_AQUI / 'out' / 'runs'}/*/{{best_model.zip,final.zip}} — treine primeiro "
        "(train.py) ou indique o ficheiro com --model CAMINHO"
    )


def carregar_politica(caminho: Path):
    """Carrega a PPO do Stable-Baselines3 em CPU; erro claro se o ficheiro não for um zip de PPO."""
    from stable_baselines3 import PPO
    try:
        return PPO.load(str(caminho), device="cpu")
    except Exception as erro:
        raise SystemExit(f"[view] não consegui carregar {caminho} como PPO do Stable-Baselines3: {erro}") from erro


# ---------------------------------------------------------------------------------------------- erros e falhas
def _erro_cli(mensagem: str, codigo: int = 2) -> None:
    """Erro de linha de comandos: mensagem curta em `stderr` e saída com código 2, sem traceback."""
    print(f"[view] {mensagem}", file=sys.stderr)
    raise SystemExit(codigo)


def _texto_divergencia(erro: RuntimeError) -> str:
    """Sanidade do `HoverEnv` (estado divergiu): mensagem curta e accionável em vez do traceback."""
    return (f"{erro}\n"
            f"[view] dica: vento absurdo faz o estado divergir — use definir_vento com um valor sao "
            f"(vel finita e >= 0 em m/s, azimute/elevacao em graus) no ficheiro de --controlo, ou "
            f"valores sanos em --vento-inicial, e volte a correr")


def alvo_z_valido(texto: str) -> float:
    """Valida o `--alvo-z` AQUI (o `HoverEnv` recusa fora da faixa): erro claro, sem traceback."""
    try:
        valor = float(str(texto).strip())
    except ValueError as erro:
        raise argparse.ArgumentTypeError(f"esperado um número em metros — recebido {texto!r}") from erro
    if not math.isfinite(valor):
        raise argparse.ArgumentTypeError(f"o alvo-z tem de ser finito — recebido {texto!r}")
    if not (ALVO_Z_MIN <= valor <= ALVO_Z_MAX):
        raise argparse.ArgumentTypeError(
            f"o alvo-z tem de estar em [{ALVO_Z_MIN:.2f}, {ALVO_Z_MAX:.2f}] m — recebido {valor:g}"
        )
    return valor


# ---------------------------------------------------------------------------------------------- vento ao vivo
def vento_inicial(texto: str) -> tuple[float, float, float]:
    """`"vel,azim"` (ou `"vel,azim,elev"`) em m/s e GRAUS → `(vel, azimute, elevacao)` para o `--vento-inicial`."""
    partes = [p.strip() for p in str(texto).split(",")]
    if len(partes) not in (2, 3):
        raise argparse.ArgumentTypeError(
            f"esperado vel,azim (ou vel,azim,elev) em m/s e graus — recebido {texto!r}")
    try:
        valores = [float(p) for p in partes]
    except ValueError as erro:
        raise argparse.ArgumentTypeError(f"valores não numéricos em {texto!r}: {erro}") from erro
    if not all(math.isfinite(v) for v in valores):
        raise argparse.ArgumentTypeError(f"valores têm de ser finitos — recebido {texto!r}")
    if valores[0] < 0.0:
        raise argparse.ArgumentTypeError(f"a velocidade do vento tem de ser ≥ 0 m/s — recebido {valores[0]}")
    return (valores[0], valores[1], valores[2] if len(valores) == 3 else 0.0)


@dataclass
class EstadoVento:
    """Vento aplicado ao ambiente (o que o HUD/log mostram) — em m/s e GRAUS."""

    vel: float = 0.0
    azimute: float = 0.0
    elevacao: float = 0.0
    ativo: bool = False
    fonte: str = "nenhum"

    def descricao(self) -> str:
        """Texto ASCII de uma linha: `4.00 m/s @ 90.0 deg (elev +0.0 deg)` (+ `[desligado]` se fora)."""
        texto = f"{self.vel:.2f} m/s @ {self.azimute:.1f} deg"
        if self.elevacao:
            texto += f" (elev {self.elevacao:+.1f} deg)"
        if not self.ativo:
            texto += " [desligado]"
        return texto


class ControloVento:
    """Vento ao vivo por ficheiro JSON: relê-o a cada `passos_controle` decisões (gate no mtime) e aplica-o.

    O ficheiro tem `{"vel", "azimute", "elevacao", "ativo"}` (vel em m/s, ângulos em graus). Com
    `"ativo": false` o vento vai a ZERO (`definir_vento(0, 0, 0)`); com `ativo: true` é
    `env.definir_vento(vel, azimute, elevacao)`. Ficheiro ausente → não se mexe no vento. Ficheiro inválido
    → aviso em stdout (uma vez por TEXTO de aviso, não por versão do ficheiro) e mantém-se o vento
    anterior: o loop nunca morre por isto.
    """

    def __init__(self, caminho: Path, inicial: tuple[float, float, float] | None = None,
                 passos_controle: int = PASSOS_CONTROLO):
        self.caminho = Path(caminho)
        self.passos_controle = max(1, int(passos_controle))
        self.inicial = inicial
        self.estado = EstadoVento()
        self._mtime: int | None = None
        self._lido = False
        self._avisos: set[str] = set()

    def aplicar_inicial(self, env: HoverEnv) -> EstadoVento:
        """Aplica o `--vento-inicial` (se houver) ANTES do 1.º reset; devolve o estado resultante."""
        if self.inicial is not None:
            vel, azimute, elevacao = self.inicial
            env.definir_vento(vel, azimute, elevacao)
            self.estado = EstadoVento(vel, azimute, elevacao, ativo=vel > 0.0, fonte="--vento-inicial")
        return self.estado

    def talvez_aplicar(self, env: HoverEnv, indice: int) -> EstadoVento | None:
        """Se for passo de leitura e o mtime tiver mudado, aplica o vento do ficheiro; devolve o novo estado.

        Devolve `None` quando não há nada a fazer (fora do passo de leitura, ficheiro ausente, mtime igual
        ou ficheiro inválido) — é o que permite ao loop só imprimir quando o vento muda mesmo.
        """
        if indice % self.passos_controle:
            return None
        mtime = self._mtime_do_ficheiro()
        if mtime is None or (self._lido and mtime == self._mtime):
            return None
        self._mtime, self._lido = mtime, True
        novo = self._ler_ficheiro()
        if novo is None:
            return None
        if novo.ativo:
            aplicar = (novo.vel, novo.azimute, novo.elevacao)
        else:
            aplicar = (0.0, 0.0, 0.0)                 # "ativo": false → vento a ZERO
        try:
            env.definir_vento(*aplicar)
        except ValueError as erro:                    # o env recusou: avisa e MANTÉM o vento anterior
            self._aviso(f"{self.caminho}: o env recusou o vento {novo.descricao()}: {erro}")
            return None
        self.estado = novo
        return novo

    def _mtime_do_ficheiro(self) -> int | None:
        """mtime (ns) do ficheiro de controlo, ou `None` se ele não existir/não for acessível."""
        try:
            return self.caminho.stat().st_mtime_ns
        except OSError:
            return None

    def _ler_ficheiro(self) -> EstadoVento | None:
        """Lê e valida o JSON de controlo; avisa (stdout, uma vez por texto) e devolve `None` se estiver mal."""
        try:
            bruto = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erro:
            self._aviso(f"não consegui ler {self.caminho}: {erro}")
            return None
        if not isinstance(bruto, dict):
            self._aviso(f'{self.caminho}: esperado um objeto JSON {{"vel", "azimute", "elevacao", "ativo"}}')
            return None
        try:
            vel = float(bruto.get("vel", 0.0))
            azimute = float(bruto.get("azimute", 0.0))
            elevacao = float(bruto.get("elevacao", 0.0))
            ativo = bool(bruto.get("ativo", True))
        except (TypeError, ValueError) as erro:
            self._aviso(f"{self.caminho}: valores inválidos: {erro}")
            return None
        if not all(math.isfinite(v) for v in (vel, azimute, elevacao)) or vel < 0.0:
            self._aviso(f"{self.caminho}: precisa vel ≥ 0 m/s e valores finitos (recebido {bruto!r})")
            return None
        return EstadoVento(vel, azimute, elevacao, ativo, fonte=self.caminho.name)

    def _aviso(self, mensagem: str) -> None:
        """Aviso em stdout, uma vez por texto (evita inundar a 50 Hz); stderr fica limpo para os testes."""
        if mensagem not in self._avisos:
            self._avisos.add(mensagem)
            print(f"[view] aviso: {mensagem}")


def _polar_do_vetor(w) -> tuple[float, float, float]:
    """`(vel, azimute, elevação)` em m/s e GRAUS do vector de vento CARTESIANO de `env.vento_atual`.

    É a inversa da convenção do `env.definir_vento` (azimute 0° → +x, 90° → +y; elevação positiva → +z),
    reimplementada aqui para o view.py não depender de um helper privado do `env.py`.
    """
    v = np.asarray(w, dtype=float).reshape(3)
    vel = float(np.linalg.norm(v))
    if vel == 0.0:
        return 0.0, 0.0, 0.0
    # 9 casas bastam (o HUD mostra 1) e limpam o ruído do arctan2/arcsin: sem isto, um azimute que devia
    # ser 0 sai 359.99999999999994 do `% 360` e o HUD pisca entre 0,0 e 360,0 graus.
    elevacao = round(float(np.degrees(np.arcsin(np.clip(v[2] / vel, -1.0, 1.0)))), 9)
    azimute = round(float(np.degrees(np.arctan2(v[1], v[0]))), 9) % 360.0
    return vel, azimute, elevacao


def ajustar_vento(env: HoverEnv, controlo: ControloVento | None, *, passos_forca: int = 0,
                  passos_azim: int = 0, parar: bool = False) -> EstadoVento | None:
    """Vento pelo TECLADO, em tempo real: `[`/`]` = ∓/+0,5 m/s (clamp [0, 5]), `,`/`.` = ∓/+15° (wrap 360°).

    Lê o vento ATIVO do próprio `env` (não de uma cópia nossa: o ficheiro de controlo e o `--vento-inicial`
    também lhe mexem), aplica-o com `env.definir_vento` e devolve o novo `EstadoVento` — ou `None` quando não
    há nada a fazer. A ELEVAÇÃO é preservada nas mudanças de força/azimute; com o vento a zero a direção vem
    do último estado conhecido, para `v` seguido de `]` voltar à mesma direção. `parar=True` (`v`) põe a
    força a zero. Nada aqui avança a física: pode ser usado com o episódio terminado.
    """
    if not (passos_forca or passos_azim or parar):
        return None
    vel, azimute, elevacao = _polar_do_vetor(env.vento_atual)
    if vel == 0.0 and controlo is not None:      # vento parado: a direção (com elevação) é a última usada
        azimute, elevacao = float(controlo.estado.azimute), float(controlo.estado.elevacao)
    if parar:
        vel = 0.0
    else:
        vel = min(FORCA_MAX, max(0.0, vel + AJUSTE_FORCA * passos_forca))
        azimute = (azimute + AJUSTE_AZIM * passos_azim) % 360.0
    env.definir_vento(vel, azimute, elevacao)
    novo = EstadoVento(vel, azimute, elevacao, ativo=vel > 0.0, fonte="teclado")
    if controlo is not None:
        controlo.estado = novo
    return novo


# ---------------------------------------------------------------------------------------------- passo de decisão
@dataclass
class Passo:
    """Resultado de um passo de decisão (tudo o que o HUD e as figuras consomem)."""

    obs: np.ndarray
    acao: np.ndarray
    empuxo: float
    momentos: np.ndarray
    recompensa: float
    terminado: bool
    truncado: bool
    info: dict
    vento_log: str = ""
    vento_elev: float = 0.0     # elevação (graus) do vento ATIVO — o `info` do contrato não a traz


def _trava(viewer):
    """Lock do viewer quando há janela; contexto vazio no modo `--sem-janela`."""
    return contextlib.nullcontext() if viewer is None else viewer.lock()


def passo(env: HoverEnv, politica, obs, viewer=None, controlo: ControloVento | None = None,
          indice: int = 0) -> Passo:
    """Um passo de decisão: vento ao vivo → rede → ação → `env.step` (tudo sob o lock do viewer).

    O vento é escrito em `model.opt.wind` DENTRO do lock (a thread do viewer lê o modelo) e antes do
    `env.step`, para o passo de física já levar com o vento novo.
    """
    vento_log, vento_elev = "", 0.0
    with _trava(viewer):
        if controlo is not None:
            novo = controlo.talvez_aplicar(env, indice)
            if novo is not None:
                vento_log = novo.descricao()
            vento_elev = float(controlo.estado.elevacao)
        acao, _ = politica.predict(obs, deterministic=True)
        acao = np.asarray(acao, dtype=float).reshape(4)
        empuxo, momentos = env.acao_para_ctrl(acao)
        obs, r, terminado, truncado, info = env.step(acao)
    return Passo(obs, acao, float(empuxo), momentos, float(r), bool(terminado), bool(truncado), info,
                 vento_log, vento_elev)


def reiniciar(env: HoverEnv, args, hud: HUD, figs: Figuras, viewer=None) -> np.ndarray:
    """Reset do ambiente (com o assentamento físico do `env.reset`) + curvas limpas; devolve a obs inicial.

    É o que a tecla R (e o auto-reset do `--loop`) chama: repõe o drone pousado com o jitter/vento do início
    e limpa o aviso de "episodio terminado" do painel.
    """
    with _trava(viewer):
        obs, _ = env.reset(seed=args.seed + hud.episodio - 1)
    hud.retorno = 0.0
    hud.reiniciado()
    figs.limpar()
    return obs


# ---------------------------------------------------------------------------------------------- HUD (texto)
def _encurta(texto: str, limite: int) -> str:
    """Encurta `texto` a `limite` colunas, marcando o corte com `..` (o fim é o que identifica o ficheiro)."""
    return texto if len(texto) <= limite else ".." + texto[-(limite - 2):]


def _junta(principal: str, extra: str) -> str:
    """Junta `extra` a `principal` com `' | '` só se couber em `HUD_COLUNAS` (senão trunca o extra)."""
    if not extra:
        return principal
    sobra = HUD_COLUNAS - len(principal) - 3
    return principal if sobra <= 0 else f"{principal} | {extra[:sobra]}"


def _vento_texto(info: dict, elevacao: float = 0.0, alinhado: bool = True) -> str:
    """Vento ATIVO numa linha: `4.00 m/s @ 90.0 deg`, mais `elev +89.0` sempre que há vento.

    A velocidade e o azimute vêm do `info` do contrato; a elevação (que ele não traz) aparece com o vento
    ATIVO — inclusive `elev  +0.0`, para a linha mostrar sempre o vento que está mesmo a ser aplicado (é a
    3.ª componente que o teclado preserva ao mexer na força/azimute). Com o vento a zero ela fica escondida:
    não se mostra uma componente que já não empurra nada.
    `alinhado=True` (painel/rasto) usa campos de largura fixa, para as colunas não dançarem entre frames.
    """
    if alinhado:
        texto = f"{info['vento_vel']:5.2f} m/s @ {info['vento_azim']:5.1f} deg"
    else:
        texto = f"{info['vento_vel']:.2f} m/s @ {info['vento_azim']:.1f} deg"
    if info["vento_vel"] > 0.0:
        texto += f" elev{elevacao:+6.1f}"
    return texto


class HUD:
    """Painel de 8 linhas KPI (ASCII, <=60 colunas) + rodapé (estado/teclas): o que a rede vê/manda, o
    estado, o vento e o modelo."""

    def __init__(self, nome_modelo: str):
        self.nome = _encurta(nome_modelo, HUD_COLUNAS - len("modelo  "))
        self.episodio = 1
        self.completos = 0
        self.retorno = 0.0
        self.ultimo = ""
        self.terminado: float | None = None    # retorno do episódio que acabou e ficou À ESPERA do R

    def fechar_episodio(self, env: HoverEnv, motivo: str) -> None:
        """Guarda o resumo do episódio que acabou (entra na linha 7 do painel) e abre a contagem do seguinte."""
        self.ultimo = f"ult ep {self.episodio:2d} {self.retorno:+7.2f} ({motivo})"
        self.terminado = self.retorno
        self.completos += 1
        self.episodio += 1
        self.retorno = 0.0

    def reiniciado(self) -> None:
        """O R (ou um auto-reset em `--loop`) recomeçou: o painel deixa de dizer que está parado."""
        self.terminado = None

    def linhas(self, env: HoverEnv, p: Passo) -> list[str]:
        """As 8 linhas KPI, já alinhadas (ver o layout no docstring do módulo)."""
        o = np.asarray(p.obs, dtype=float)
        a = np.asarray(p.acao, dtype=float)
        info = p.info
        # ω vem da própria observação (obs[9:12] = ω/10 rad·s⁻¹) — é literalmente o que a rede vê
        omega = 10.0 * o[9:12]
        return [
            f"obs dp  {o[0]:+8.3f}{o[1]:+8.3f}{o[2]:+8.3f} | |v| {info['v']:5.2f}",
            f"obs rpy {o[3]:+8.3f}{o[4]:+8.3f} [yaw{o[5]:+8.3f}] | |w| {float(np.linalg.norm(omega)):5.2f}",
            f"acao    {a[0]:+8.3f}{a[1]:+8.3f}{a[2]:+8.3f}{a[3]:+8.3f} -> {p.empuxo:5.3f} N",
            (f"pos     z {info['z']:6.3f} | alvo {env.alvo_z:5.3f} | dz {info['z'] - env.alvo_z:+6.3f} "
             f"| dxy {info['dist_xy']:5.3f} m"),
            (f"yaw_err {math.degrees(float(info['yaw_err'])):+7.2f} deg | wz {float(omega[2]):+7.3f} r/s "
             f"| |a_prev| {float(np.linalg.norm(o[12:16])):5.2f}"),
            (f"retorno {self.retorno:+8.2f} | ep {self.episodio:2d} | passo {env.passos:4d}/"
             f"{env.max_passos:4d} | t {env.data.time:5.2f} s"),
            _junta(f"vento   {_vento_texto(info, p.vento_elev)}", self.ultimo),
            f"modelo  {self.nome}",
        ]

    def rodape(self, env: HoverEnv | None = None, p: Passo | None = None) -> list[str]:
        """0-2 linhas de rodapé: o aviso de episódio terminado (quando está parado) e a legenda das teclas.

        `env`/`p` existem para assinatura simétrica à de `linhas`; nada aqui depende do estado da simulação.
        """
        linhas = []
        if self.terminado is not None:
            linhas.append(_encurta(f"episodio terminado (retorno {self.terminado:+.3f}) - R para reiniciar",
                                   HUD_COLUNAS))
        linhas.append(LEGENDA_TECLAS)
        return linhas[:HUD_RODAPE]

    def texto(self, env: HoverEnv, p: Passo) -> str:
        """Painel multi-linha (`set_texts` aceita `\\n`) — uma única entrada em mjGRID_TOPLEFT."""
        return "\n".join(self.linhas(env, p) + self.rodape(env, p))


# ---------------------------------------------------------------------------------------------- figuras
class Serie:
    """Uma linha do `MjvFigure` com o ringbuffer do próprio: ao encher (mjMAXLINEPNT), desliza 1 amostra."""

    def __init__(self, fig: mujoco.MjvFigure, linha: int, nome: str, cor):
        self.fig, self.linha = fig, linha
        fig.linename[linha] = nome
        fig.linergb[linha] = cor
        fig.linepnt[linha] = 0

    def acrescentar(self, x: float, y: float) -> None:
        """Junta o ponto (x, y); `linedata` guarda pares (x, y) intercalados."""
        n = int(self.fig.linepnt[self.linha])
        if n >= mujoco.mjMAXLINEPNT:
            dados = self.fig.linedata[self.linha]
            dados[:-2] = dados[2:].copy()          # desliza o histórico (buffer fixo do MjvFigure)
            n = mujoco.mjMAXLINEPNT - 1
        self.fig.linedata[self.linha, 2 * n] = x
        self.fig.linedata[self.linha, 2 * n + 1] = y
        self.fig.linepnt[self.linha] = n + 1

    def definir(self, pontos) -> None:
        """Substitui a linha por uma sequência curta e fixa de pontos (usado pelas linhas de referência)."""
        self.fig.linepnt[self.linha] = len(pontos)
        for i, (x, y) in enumerate(pontos):
            self.fig.linedata[self.linha, 2 * i] = x
            self.fig.linedata[self.linha, 2 * i + 1] = y

    def limpar(self) -> None:
        """Esvazia a linha (novo episódio → curvas limpas)."""
        self.fig.linepnt[self.linha] = 0


class Figuras:
    """3 figuras: z(t)+alvo, yaw_err(t)+zero e os 4 canais de ação (2 colunas quando a janela é larga)."""

    def __init__(self, alvo_z: float):
        self.alvo_z = float(alvo_z)
        self.z_max = 0.0
        self.yaw_max = 0.0

        self.fig_z = self._nova("z (m) - altura do CM", 0.0, 1.25)
        self.serie_z = Serie(self.fig_z, 0, "z", (0.25, 0.85, 1.0))
        self.serie_alvo = Serie(self.fig_z, 1, "alvo", (1.0, 0.45, 0.15))

        self.fig_yaw = self._nova("yaw_err (rad) - alvo 0", -0.15, 0.15)
        self.serie_yaw = Serie(self.fig_yaw, 0, "yaw_err", (0.95, 0.75, 0.25))
        self.serie_zero = Serie(self.fig_yaw, 1, "zero", (0.55, 0.55, 0.55))

        self.fig_acao = self._nova("acao (4 canais, Box(-1,1))", -1.05, 1.05)
        self.series_acao = [
            Serie(self.fig_acao, i, nome, cor) for i, (nome, cor) in enumerate((
                ("empuxo", (1.0, 0.9, 0.25)), ("mx", (1.0, 0.4, 0.4)),
                ("my", (0.45, 1.0, 0.45)), ("mz", (0.55, 0.65, 1.0)),
            ))
        ]

    @staticmethod
    def _nova(titulo: str, y0: float, y1: float) -> mujoco.MjvFigure:
        """`MjvFigure` com janelas explícitas (`flg_extend=0`), legenda e gama y inicial (o x é o tempo)."""
        fig = mujoco.MjvFigure()
        mujoco.mjv_defaultFigure(fig)
        fig.flg_extend = 0
        fig.flg_legend = 1
        fig.title = titulo
        fig.xlabel = "t (s)"
        fig.xformat, fig.yformat = "%.1f", "%.2f"
        fig.gridsize[0], fig.gridsize[1] = 5, 4
        fig.range[1][:] = (y0, y1)
        return fig

    def amostrar(self, t: float, z: float, yaw_err: float, acao) -> None:
        """Acrescenta uma amostra às curvas e reajusta as janelas (x = últimos `JANELA_S` segundos)."""
        self.z_max = max(self.z_max, float(z))
        self.yaw_max = max(self.yaw_max, abs(float(yaw_err)))
        self.serie_z.acrescentar(t, float(z))
        self.serie_yaw.acrescentar(t, float(yaw_err))
        for i, serie in enumerate(self.series_acao):
            serie.acrescentar(t, float(acao[i]))
        x0, x1 = max(0.0, t - JANELA_S), max(JANELA_S, t)
        for fig in (self.fig_z, self.fig_yaw, self.fig_acao):
            fig.range[0][:] = (x0, x1)
        # a gama Y tem de conter o alvo (--alvo-z pode ser > 1) e a altura máxima atingida
        self.fig_z.range[1][:] = (0.0, max(FIG_Z_GAMA_MIN, 1.15 * max(self.z_max, self.alvo_z)))
        escala_yaw = max(0.15, 1.15 * self.yaw_max)
        self.fig_yaw.range[1][:] = (-escala_yaw, escala_yaw)
        self.serie_alvo.definir(((x0, self.alvo_z), (x1, self.alvo_z)))   # linha do alvo: 2 pontos
        self.serie_zero.definir(((x0, 0.0), (x1, 0.0)))                  # linha do yaw alvo = 0 rad

    def limpar(self) -> None:
        """Limpa as curvas e os máximos (começo de episódio)."""
        self.z_max = 0.0
        self.yaw_max = 0.0
        for serie in (self.serie_z, self.serie_alvo, self.serie_yaw, self.serie_zero, *self.series_acao):
            serie.limpar()

    def rects(self, viewport):
        """Rectângulos das figuras QUE CABEM no viewport (2 colunas (2+1) se largo, senão empilhadas).

        Numa janela baixa demais para as 3 figuras mostram-se só as primeiras — prioridade z > yaw_err >
        ação — e, em último recurso, os rects são clavados ao viewport: nenhuma figura sai do ecrã (o
        `MjvFigure` sem espaço é ilegível, mas uma figura fora do rect não se vê de todo).
        """
        figuras = (self.fig_z, self.fig_yaw, self.fig_acao)
        # largura: ~1/3 do viewport, entre FIG_LARG_MIN e FIG_LARG, sempre dentro do viewport
        largura = min(FIG_LARG, max(FIG_LARG_MIN, viewport.width // 3),
                      max(FIG_MIN_ABS, viewport.width - 2 * MARGEM))
        colunas = 2 if viewport.width >= 2 * largura + 3 * MARGEM else 1
        # quantas linhas de FIG_MIN px (mínimo legível) cabem? é isso que decide quantas figuras se mostram
        por_coluna = max(1, (viewport.height - MARGEM) // (FIG_MIN + MARGEM))
        cabe_uma = viewport.height >= 2 * MARGEM + FIG_MIN_ABS
        mostrar = figuras[:max(1, min(len(figuras), colunas * por_coluna))] if cabe_uma else ()
        linhas = max(1, -(-len(mostrar) // colunas))          # teto da divisão: 2 com 2 colunas
        # altura por linha: o que sobra; numa janela baixa demais desce até FIG_MIN_ABS (e nunca sai do ecrã)
        altura = min(FIG_ALT, max(FIG_MIN_ABS, (viewport.height - MARGEM * (linhas + 1)) // linhas))
        rects = []
        for i, fig in enumerate(mostrar):
            coluna, linha = divmod(i, linhas)                # coluna 0 = a mais à direita, linha 0 em baixo
            topo = MARGEM + linha * (altura + MARGEM)
            rects.append((mujoco.MjrRect(max(0, viewport.width - (coluna + 1) * (largura + MARGEM)),
                                         max(0, min(topo, viewport.height - altura - MARGEM)),
                                         largura, altura), fig))
        return rects


# ---------------------------------------------------------------------------------------------- teclado
class Teclas:
    """Estado partilhado com o `key_callback` do viewer (chamado na thread do GLFW).

    O callback só mexe em flags/contadores: quem aplica as ações é o ciclo principal (`consumir_vento`,
    `reiniciar`), para o `env` nunca ser tocado de dentro do callback.
    """

    def __init__(self):
        self.pausa = False
        self.fechar = False
        self.reiniciar = False
        self.passos_forca = 0        # toques pendentes em `[` (−1) / `]` (+1)
        self.passos_azim = 0         # toques pendentes em `,` (−1) / `.` (+1)
        self.parar_vento = False     # `v`: vento para zero

    def ao_teclar(self, tecla: int) -> None:
        """ESPAÇO pausa/retoma · R reinicia · `[`/`]` força · `,`/`.` azimute · V para o vento · Q/Esc fecha."""
        if tecla == TECLA_ESPACO:
            self.pausa = not self.pausa
        elif tecla in (TECLA_Q, TECLA_ESC):
            self.fechar = True
        elif tecla == TECLA_R:
            self.reiniciar = True
        elif tecla == TECLA_ABRE_COLCHETE:
            self.passos_forca -= 1
        elif tecla == TECLA_FECHA_COLCHETE:
            self.passos_forca += 1
        elif tecla == TECLA_VIRGULA:
            self.passos_azim -= 1
        elif tecla == TECLA_PONTO:
            self.passos_azim += 1
        elif tecla == TECLA_V:
            self.parar_vento = True

    def consumir_vento(self) -> dict:
        """Zera (e devolve) os ajustes de vento pendentes, prontos para `ajustar_vento(**ajuste)`.

        Guarda o SINAL e o número de toques (não um booleano): dois `]` seguidos valem +1,0 m/s.
        """
        ajuste = {"passos_forca": self.passos_forca, "passos_azim": self.passos_azim,
                  "parar": self.parar_vento}
        self.passos_forca = self.passos_azim = 0
        self.parar_vento = False
        return ajuste


# ---------------------------------------------------------------------------------------------- loops
def esperar_fecho(viewer, limite: float = 2.0) -> float:
    """Espera que a thread do viewer termine antes de o processo sair; devolve os segundos esperados.

    Medido nesta máquina (mujoco 3.15, KDE Wayland): fechar a janela e sair logo a seguir faz correr o
    `glfw.terminate()` do `atexit` (thread principal) AO MESMO TEMPO que a thread do viewer destroi o
    contexto GLFW — SIGSEGV intermitente no fim do processo (não no ciclo). Esperar que o `Handle` perca a
    referência ao simulador (a thread acabou de destruí-lo) elimina a corrida; o limite garante que isto
    nunca pendura.
    """
    t0 = time.perf_counter()
    while viewer.m is not None and time.perf_counter() - t0 < limite:
        time.sleep(0.05)
    return time.perf_counter() - t0


def _cabecalho(controlo: ControloVento, caminho: Path, args=None) -> None:
    """Linhas de arranque comuns aos dois modos (modelo, vento, fim de episódio e como encolher a fonte)."""
    print(f"[view] modelo: {caminho}")
    print(f"[view] HUD: {HUD_LINHAS} linhas KPI + rodape (estado/teclas) em mjGRID_TOPLEFT (mjFONT_NORMAL) - a "
          "escala da fonte vem do PPI do monitor (100-300%); para a encolher use o painel esquerdo "
          "(show_left_ui) > Font: 50%")
    print(f"[view] vento ao vivo: {_relativo(controlo.caminho)} "
          f"(relido a cada {controlo.passos_controle} passos de decisao, por mtime)")
    if controlo.estado.fonte != "nenhum":
        print(f"[view] vento inicial: {controlo.estado.descricao()} ({controlo.estado.fonte})")
    print("[view] teclas do vento (janela): [ ] forca -/+0.5 m/s (clamp 0-5) | , . azimute -/+15 deg (wrap "
          "360) | v vento a zero | R reinicia | ESPACO pausa | Q/Esc fecha")
    if args is not None:
        print("[view] fim de episodio: " + ("--loop: auto-reset e continua" if args.loop else
                                            "PARA a fisica e espera R na janela (manual; sem auto-reset)"))


def correr_com_janela(env: HoverEnv, politica, caminho: Path, args, controlo: ControloVento) -> int:
    """Ciclo principal com viewer passivo: passo → HUD/figuras → `sync()`, a 50 Hz (ou solto em --rapido).

    Fim de episódio: por omissão a física PARA e a janela fica à espera do R (reinício manual); com `--loop`
    faz o auto-reset antigo. As teclas do vento (`[` `]` `,` `.` `v`) são aplicadas a cada volta, mesmo com a
    física parada ou em pausa — mudam o `model.opt.wind` e o HUD no instante seguinte.
    """
    from mujoco import viewer as mjviewer  # import tardio: o modo --sem-janela não carrega GLFW/GL

    hud = HUD(_nome_curto(caminho))
    figs, teclas = Figuras(env.alvo_z), Teclas()
    _cabecalho(controlo, caminho, args)
    print("[view] teclado: ESPACO pausa/retoma | R reinicia | [ ] forca -/+0.5 m/s | , . azim -/+15 deg | "
          "v vento a zero | Q ou Esc fecha")
    print("[view] fim de episodio: " + ("--loop: auto-reset e continua" if args.loop else
                                         "PARA a fisica e espera a tecla R (reinicio manual)"))
    viewer, divergencia = None, None
    try:
        with mjviewer.launch_passive(env.model, env.data, key_callback=teclas.ao_teclar,
                                     show_left_ui=True, show_right_ui=False) as viewer:
            obs = reiniciar(env, args, hud, figs, viewer=viewer)
            proximo = t_ini = time.perf_counter()
            indice, ultimo, parado = 0, None, False
            while viewer.is_running() and not teclas.fechar:
                if args.segundos > 0 and time.perf_counter() - t_ini >= args.segundos:
                    break
                novo = ajustar_vento(env, controlo, **teclas.consumir_vento())   # vento pelo teclado
                if novo is not None:
                    print(f"[view] vento (teclado) -> {novo.descricao()}")
                if teclas.reiniciar:                    # R: reinício manual (a qualquer momento)
                    teclas.reiniciar = False
                    print("[view] R: reinicio manual"
                          + (" (episodio terminado)" if parado else f" (a meio do passo {indice})"))
                    obs = reiniciar(env, args, hud, figs, viewer=viewer)
                    parado, indice = False, 0
                    proximo = time.perf_counter()
                    continue                            # este instante é do reset: não dá passo nenhum
                if teclas.pausa or parado:              # pausa/terminado: janela viva, física parada
                    if parado and controlo is not None:
                        # com a física parada o ficheiro do vento continua a ser relido (indice 0 passa o
                        # gate dos 5 passos; o mtime evita repetições) — o HUD reage sem avançar nada
                        novo_arq = controlo.talvez_aplicar(env, 0)
                        if novo_arq is not None:
                            print(f"[view] vento -> {novo_arq.descricao()}")
                    if ultimo is not None:
                        viewer.set_texts([(FONTE_HUD, GRID_HUD, hud.texto(env, ultimo), "")])
                        viewer.set_figures(figs.rects(viewer.viewport))
                    viewer.sync()
                    time.sleep(0.01)
                    continue
                try:
                    p = passo(env, politica, obs, viewer=viewer, controlo=controlo, indice=indice)
                except RuntimeError as erro:        # sanidade da física: vento absurdo faz divergir
                    divergencia = _texto_divergencia(erro)
                    break
                indice += 1
                ultimo = p
                obs = p.obs
                hud.retorno += p.recompensa
                if p.vento_log:
                    print(f"[view] vento -> {p.vento_log}")
                figs.amostrar(env.data.time, p.info["z"], p.info["yaw_err"], p.acao)
                viewer.set_texts([(FONTE_HUD, GRID_HUD, hud.texto(env, p), "")])
                viewer.set_figures(figs.rects(viewer.viewport))
                viewer.sync()
                if p.terminado or p.truncado:           # fim do episódio
                    hud.fechar_episodio(env, "caiu/capotou" if p.terminado else "tempo")
                    if args.loop:                       # --loop: auto-reset com log (comportamento antigo)
                        if args.episodios and hud.completos >= args.episodios:
                            print(f"[view] {hud.ultimo} -> fim do --loop (--episodios {args.episodios})")
                            break
                        print(f"[view] {hud.ultimo} -> auto-reset (--loop)")
                        obs = reiniciar(env, args, hud, figs, viewer=viewer)
                        proximo = time.perf_counter()
                    else:                               # por omissão: PARA e espera o R
                        parado = True
                        print(f"[view] {hud.ultimo} -> PARADO: a fisica nao avanca, R reinicia")
                        viewer.set_texts([(FONTE_HUD, GRID_HUD, hud.texto(env, p), "")])
                        viewer.set_figures(figs.rects(viewer.viewport))
                        viewer.sync()
                if not args.rapido:                     # tempo real: 1 passo de decisão por dt_decisao
                    proximo += env.dt_decisao
                    resto = proximo - time.perf_counter()
                    if resto > 0:
                        time.sleep(resto)
                    else:
                        proximo = time.perf_counter()
    except KeyboardInterrupt:
        pass                                            # Ctrl+C: sai limpo (o `with` já fechou a janela)
    if viewer is not None:
        esperar_fecho(viewer)                           # evita a corrida do glfw.terminate() no fim
    if divergencia is not None:
        _erro_cli(divergencia, 1)                       # divergiu: mensagem clara e accionável, exit 1
    return 0


def correr_sem_janela(env: HoverEnv, politica, caminho: Path, args, controlo: ControloVento) -> int:
    """Mesmo ciclo sem viewer/GL: passos de decisão, rasto, painel KPI impresso e exit 0.

    Por omissão para no FIM DO 1.º EPISÓDIO (equivalente ao modo janela sem `--loop`, onde a física espera
    pelo R): imprime `episodio terminado (retorno X) - R para reiniciar (modo janela)` e sai com exit 0, sem
    começar um 2.º episódio. Com `--loop` faz o auto-reset antigo e corre até `--passos`/`--episodios`.

    Imprime o painel entre dois marcadores (`--- painel KPI ...` / `--- fim do painel`) para que o número
    de linhas KPI seja contável sem ambiguidade; nada aqui importa `mujoco.viewer` nem `glfw`.
    """
    hud = HUD(_nome_curto(caminho))
    _cabecalho(controlo, caminho, args)
    obs, info0 = env.reset(seed=args.seed)
    print(f"[view] sem-janela: ate {args.passos} passos de decisao = {args.passos * env.dt_decisao:.2f} s de "
          f"simulacao ({1.0 / env.dt_decisao:.0f} Hz de decisao, {1.0 / env.dt:.0f} Hz de fisica), sem viewer")
    obs0 = np.asarray(obs, dtype=float)               # dp inicial do EPISÓDIO (obs[0:3] = (p − p_alvo)/1 m)
    dxy_ini = float(info0["dist_xy"])                 # baseline da deriva: reposta em cada auto-reset
    ep_base = hud.episodio                            # episódio a que a baseline pertence
    pendente = None                                   # baseline do reset que ainda não teve passo nenhum
    p = None
    parado = False
    for i in range(args.passos):
        if pendente is not None:                      # o reset anterior só agora "começa" um episódio novo
            obs0, dxy_ini = pendente
            ep_base = hud.episodio
            pendente = None
        try:
            p = passo(env, politica, obs, controlo=controlo, indice=i)
        except RuntimeError as erro:                  # sanidade da física: vento absurdo faz divergir
            _erro_cli(_texto_divergencia(erro), 1)
        obs = p.obs
        hud.retorno += p.recompensa
        if p.vento_log:
            print(f"[view] passo {i:4d}: vento -> {p.vento_log}")
        if i % PASSOS_RASTRO == 0 or i == args.passos - 1:
            print(f"[view] rasto   {i:4d} | t {env.data.time:5.2f} s | z {p.info['z']:5.3f} m | "
                  f"x {p.obs[0]:+7.4f} y {p.obs[1]:+7.4f} m | dxy {p.info['dist_xy']:6.3f} m | "
                  f"yaw_err {math.degrees(p.info['yaw_err']):+6.2f} deg | "
                  f"vento {_vento_texto(p.info, p.vento_elev)}")
        if p.terminado or p.truncado:
            hud.fechar_episodio(env, "caiu/capotou" if p.terminado else "tempo")
            if not args.loop:                         # por omissão: acaba aqui (sem 2.º episódio)
                parado = True
                print(f"[view] episodio terminado (retorno {hud.terminado:+.3f}) - R para reiniciar "
                      f"(modo janela)")
                print(f"[view] {hud.ultimo} no passo {i}: sem --loop o modo --sem-janela para aqui (exit 0)")
                break
            if args.episodios and hud.completos >= args.episodios:
                print(f"[view] {hud.ultimo} -> fim do --loop (--episodios {args.episodios}): sem auto-reset")
                break
            print(f"[view] {hud.ultimo} -> auto-reset com assentamento fisico (--loop, "
                  f"seed {args.seed + hud.episodio - 1})")
            obs, info_reset = env.reset(seed=args.seed + hud.episodio - 1)
            hud.reiniciado()                          # o reset já não espera pelo R
            pendente = (np.asarray(obs, dtype=float), float(info_reset["dist_xy"]))
    if p is None:
        return 0
    linhas = hud.linhas(env, p)
    print(f"[view] --- painel KPI ({len(linhas)} linhas, ASCII, colunas <= {HUD_COLUNAS}) ---")
    for linha in linhas:
        print(linha)
    print(f"[view] --- fim do painel ({len(linhas)} linhas) ---")
    for linha in hud.rodape(env, p):
        print(f"[view] {linha}")
    print(f"[view] painel: {len(linhas)} linhas (max {HUD_LINHAS}) | largura max "
          f"{max(len(ln) for ln in linhas)} col (max {HUD_COLUNAS}) | ASCII "
          f"{all(ln.isascii() for ln in linhas)} | entradas em gridpos: 1 (mjGRID_TOPLEFT)")
    print(f"[view] obs  = [{', '.join(f'{v:+.4f}' for v in p.obs)}]")
    print(f"[view] acao = [{', '.join(f'{v:+.4f}' for v in p.acao)}]")
    print(f"[view] z = {p.info['z']:.4f} m | alvo = {env.alvo_z:.4f} m | dist_xy = {p.info['dist_xy']:.4f} m"
          f" | |v| = {p.info['v']:.4f} m/s | no_alvo = {'sim' if p.info['no_alvo'] else 'nao'}")
    print(f"[view] yaw_err = {math.degrees(p.info['yaw_err']):+.2f} deg ({p.info['yaw_err']:+.4f} rad)")
    print(f"[view] ctrl = empuxo {p.empuxo:.4f} N, momentos "
          f"[{', '.join(f'{v:+.2e}' for v in p.momentos)}] N.m")
    print(f"[view] vento ativo = {_vento_texto(p.info, p.vento_elev, alinhado=False)} "
          f"| fonte = {controlo.estado.fonte}")
    # Deriva: deslocamento em xy desde o reset DESTE episódio e a sua projeção no azimute do vento
    # (evidência física de que é o vento a empurrar; com vento nulo a projeção é 0 por definição).
    desloc = np.asarray(p.obs[:2], dtype=float) - obs0[:2]
    azim = math.radians(float(p.info["vento_azim"]))
    projecao = float(desloc @ np.array([math.cos(azim), math.sin(azim)]))
    print(f"[view] deriva (ep {ep_base}, desde o reset): dist_xy {dxy_ini:.4f} -> "
          f"{p.info['dist_xy']:.4f} m (variacao {p.info['dist_xy'] - dxy_ini:+.4f} m) | "
          f"xy {desloc[0]:+.4f}, {desloc[1]:+.4f} m | "
          f"projecao no azimute {p.info['vento_azim']:.1f} deg = {projecao:+.4f} m")
    print(f"[view] episodios completos: {hud.completos} | retorno do episodio atual: {hud.retorno:+.3f}"
          + (f" | {hud.ultimo}" if hud.ultimo else ""))
    print("[view] estado: " + (f"PARADO no fim do episodio (retorno {hud.terminado:+.3f}) - so a tecla R "
                              f"reinicia, e so na janela" if parado else
                              f"a correr ({args.passos} passos pedidos, sem fim de episodio"
                              + ("" if args.loop else "; use --loop para correr varios episodios") + ")"))
    return 0


# ---------------------------------------------------------------------------------------------- CLI
def analisar_argumentos(argv=None) -> argparse.Namespace:
    """Argumentos da linha de comandos (o modelo por omissão é descoberto em `out/runs/*/`)."""
    p = argparse.ArgumentParser(
        description="Visualizador 3D com HUD KPI (8 linhas) da rede (PPO) do drone que sobe a 1 m, "
                    "estabiliza e leva com vento ao vivo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Teclado (foco na janela): ESPACO pausa/retoma · R reinicia · Q ou Esc fecha.\n"
            "Vento em tempo real: [ ] forca -/+0.5 m/s (clamp 0-5) · , . azimute -/+15 graus (wrap 360) ·\n"
            "v vento a zero (a elevacao do vento e preservada nas mudancas de forca/azimute).\n"
            "\n"
            "Fim de episodio: SEM --loop a fisica PARA e a janela fica a espera do R (reinicio manual);\n"
            "com --loop faz o auto-reset antigo. No --sem-janela o fim do episodio imprime o aviso e sai\n"
            "com exit 0 (sem 2.º episodio).\n"
            "\n"
            "HUD: 8 linhas KPI + 2 de rodape (estado/teclas), <=60 colunas, so ASCII, em mjGRID_TOPLEFT; o\n"
            "1.º argumento de set_texts e um mjtFont (normal/shadow/big), NAO uma escala — a escala vem do\n"
            "PPI do monitor (100-300%). Para encolher a fonte use o painel esquerdo (show_left_ui=True) >\n"
            "Rendering > Font: 50%.\n"
            "\n"
            "Vento ao vivo: escreva {vel, azimute, elevacao, ativo} no ficheiro de --controlo (ele e relido\n"
            "por mtime a cada 5 passos de decisao) ou arranque ja com vento por --vento-inicial vel,azim.\n"
            "\n"
            "Figuras: z(t)+alvo, yaw_err(t) em rad + zero e os 4 canais de acao."
        ),
    )
    p.add_argument("--model", type=Path, default=None,
                   help="modelo do Stable-Baselines3 (.zip); por omissão, o best_model.zip mais recente de "
                        "out/runs/*/ (na falta dele, o final.zip)")
    p.add_argument("--sem-janela", action="store_true",
                   help="corre o loop sem viewer/GL (validação headless): imprime o painel KPI em texto, um "
                        "rasto do estado e obs/ação/z — nenhum import de mujoco.viewer/glfw")
    ritmo = p.add_mutually_exclusive_group()
    ritmo.add_argument("--tempo-real", dest="rapido", action="store_false",
                       help="1 passo de decisão por dt_decisao = 0,02 s (PADRÃO)")
    ritmo.add_argument("--rapido", dest="rapido", action="store_true",
                       help="corre solto, sem espera (física o mais depressa possível)")
    p.set_defaults(rapido=False)
    p.add_argument("--loop", action="store_true",
                   help="auto-reset no fim de cada episódio (comportamento antigo). SEM esta flag o fim do "
                        "episódio PARA a física e a janela fica à espera da tecla R (reinício manual); no "
                        "--sem-janela sai com exit 0 no fim do 1.º episódio")
    p.add_argument("--episodios", type=int, default=0,
                   help="com --loop, para ao fim de N episódios (0 = até Ctrl+C/--passos; padrão: 0)")
    p.add_argument("--passos", type=int, default=PASSOS_OMISSAO,
                   help=f"teto de passos de decisão do modo --sem-janela; sem --loop ele para no fim do 1.º "
                        f"episódio (padrão: {PASSOS_OMISSAO})")
    p.add_argument("--segundos", type=float, default=0.0,
                   help="fecha a janela ao fim de S segundos de relógio (0 = sem limite; padrão: 0)")
    p.add_argument("--alvo-z", type=alvo_z_valido, default=1.0, metavar="M",
                   help="altura-alvo em m, passada ao HoverEnv; a faixa aceite é "
                        f"[{ALVO_Z_MIN:.2f}, {ALVO_Z_MAX:.2f}] m (validada aqui: erro claro e exit 2, "
                        "sem traceback; padrão: 1.0)")
    p.add_argument("--seed", type=int, default=0,
                   help="semente do reset — o episódio N usa seed + N - 1 (padrão: 0)")
    p.add_argument("--controlo", type=Path, default=CONTROLO_OMISSAO, metavar="CAMINHO",
                   help="ficheiro JSON de vento ao vivo, relido a cada 5 passos de decisão (por mtime): "
                        '{"vel": m/s, "azimute": graus, "elevacao": graus, "ativo": bool} — com '
                        f'"ativo": false o vento vai a zero; padrão: {_relativo(CONTROLO_OMISSAO)}')
    p.add_argument("--vento-inicial", type=vento_inicial, default=None, metavar="VEL,AZIM[,ELEV]",
                   help="arranca com vento sem ficheiro nenhum: velocidade em m/s e azimute em graus "
                        "(0° = +x, 90° = +y); o ficheiro de --controlo, se existir, passa a mandar")
    return p.parse_args(argv)


def main(argv=None) -> int:
    """Carrega o modelo e a política e entra no ciclo escolhido; devolve o código de saída."""
    args = analisar_argumentos(argv)
    caminho = args.model if args.model is not None else modelo_por_omissao()
    if not caminho.is_file():
        raise SystemExit(f"[view] modelo inexistente: {caminho}")
    try:
        env = HoverEnv(alvo_z=args.alvo_z)        # 2.ª barreira: o --alvo-z já foi validado no CLI
    except ValueError as erro:
        _erro_cli(f"o HoverEnv recusou alvo_z={args.alvo_z:g}: {erro}")
    politica = carregar_politica(caminho)
    controlo = ControloVento(args.controlo, args.vento_inicial)
    controlo.aplicar_inicial(env)                 # --vento-inicial: vale já para o 1.º reset
    if args.sem_janela:
        return correr_sem_janela(env, politica, caminho, args, controlo)
    return correr_com_janela(env, politica, caminho, args, controlo)


if __name__ == "__main__":
    sys.exit(main())
