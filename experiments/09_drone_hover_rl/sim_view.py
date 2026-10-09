#!/usr/bin/env python3
"""experiments/09_drone_hover_rl/sim_view.py — runner da simulação: janela MuJoCo LIMPA + telemetria JSONL.

Uma janela e mais nada: `mujoco.viewer.launch_passive` com `show_left_ui=False, show_right_ui=False` e ZERO
overlay (nunca se chama `set_texts`/`set_figures`; `clear_texts()` no arranque garante o ecrã limpo). Toda a
informação — métricas, vento, reiniciar, loop — vive no SITE (`sim_site.py` + `site/dist/`), que fala com
este processo por DOIS FICHEIROS:

  · CONTROLO (o site escreve, sempre atómico tmp+os.replace)
      out/controle_vento.json = {"vel": 0..5, "azimute": 0..360, "elevacao": -90..90, "ativo": bool,
                                 "reiniciar": int, "loop": bool, "t": float}
    Lido a CADA passo de decisão (assinatura mtime_ns+tamanho: um ficheiro reescrito é sempre visto):
      - vento → `env.definir_vento(vel, azimute, elevacao)` (com `ativo: false` → vento 0);
      - `reiniciar` → contador; quando MUDA é um REINICIAR (1.º contador visto é linha de base; um contador
        ≥ 1 que apareça sem ficheiro prévio é um REINICIAR já pedido — mesma regra do net_probe/dashboard);
      - `loop` → `true` liga o auto-reset no fim do episódio, `false` volta à espera (campo ausente = não mexe).
  · TELEMETRIA (escrita AQUI, ~10 Hz = 1 linha JSON por amostra; 1 Hz com o episódio parado)
      out/sim_telemetria.jsonl = {"t","estado","ep","passo","retorno","z","dist_xy","yaw_err","vento_vel",
                                  "vento_azim","obs":[16],"act":[4],"ctrl":[4],"h1":[64],"h2":[64]}
    `t` = tempo de SIMULAÇÃO do episódio (s, volta a 0 em cada reset); `estado` = "a_correr" |
    "episodio_terminado"; `obs`/`act`/`ctrl` na MESMA linha que `h1`/`h2` (ativações da MLP por forward hooks
    nos `nn.Linear`, a mesma técnica do net_probe: `h1` = saída da 1.ª Linear, `h2` = da 2.ª); `act` é a ação
    de política (Box(-1,1)⁴) e `ctrl` o comando FÍSICO que ela produziu (`data.ctrl` = [empuxo N, mx, my, mz
    N·m], via `env.acao_para_ctrl`/`aplicar_acao`) — o site mostra o `ctrl` do backend sem o derivar da ação.
    Coerência (ver `amostra`): `ctrl == acao_para_ctrl(act)` nas linhas com `passo > 0` (ação aplicada); nas
    linhas de arranque/reinício (`passo == 0`, `t == 0`) valem `act == ctrl == [0,0,0,0]`, porque o `reset`
    zera o `data.ctrl` e não houve ação nenhuma (não se inventa ali um `ctrl` que o simulador não aplicou).
    Cada linha é escrita com `flush` para o site a ver sem esperar; no fim do episódio escreve-se LOGO uma
    linha de evento (não se espera pelos 0,1 s).

SEM AUTO-LOOP POR OMISSÃO: quando o episódio termina (`terminated` OU `truncated`) a física PARA (nenhum
`env.step` a partir daí) e o estado passa a "episodio_terminado"; só um REINICIAR do site (ou `--loop`, ou
`loop: true` no controlo) arranca o episódio seguinte. Com o episódio parado o processo continua vivo: lê o
controlo, mantém a janela a responder e escreve um batimento por segundo na telemetria.

    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_view.py                    # janela limpa
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_view.py --fator-tempo 0.5  # metade da velocidade
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_view.py --sem-janela --max-segundos 20
    uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py                    # 1 comando: janela + site

Teclado (foco na janela): ESPAÇO pausa/retoma · Q ou Esc fecha. Não há mais teclas: o vento e o REINICIAR
são do site (é o que mantém a janela 100% limpa).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_AQUI = Path(__file__).resolve().parent
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

# Ordem intencional (por isso o I001 fica desligado nesta linha): o `mjkit` define MUJOCO_GL=egl ANTES de
# `import mujoco`. O viewer (GLFW) não depende disso — ver o cabeçalho do `lab/mjkit.py`.
from lab import mjkit  # noqa: F401, I001
from env import HoverEnv

import numpy as np

# ---------------------------------------------------------------------------------------------- constantes
CONTROLO_OMISSAO = _AQUI / "out" / "controle_vento.json"
TELEMETRIA_OMISSAO = _AQUI / "out" / "sim_telemetria.jsonl"
FATOR_TEMPO_OMISSAO = 1.0        # 1 = tempo real; 0 = sem travão (o mais rápido possível); 2 = 2x mais rápido
PERIODO_AMOSTRA = 0.1            # s — cadência da telemetria a correr (~10 Hz)
PERIODO_PARADO = 1.0             # s — cadência com o episódio terminado (batimento, o estado não muda)
PERIODO_OCIO = 0.02              # s — ritmo do ciclo quando não há física (pausa/parado): 1 passo de decisão
VEL_MAX, AZIM_MAX, ELEV_MAX = 5.0, 360.0, 90.0      # faixas do contrato do controlo
PRECISAO = 6                     # casas decimais na telemetria (linhas pequenas e legíveis)
TECLA_ESPACO, TECLA_Q, TECLA_ESC = 32, 81, 256      # códigos GLFW entregues pelo viewer


# ---------------------------------------------------------------------------------------------- controlo
@dataclass
class Registo:
    """Conteúdo validado do ficheiro de controlo (vento + comandos de episódio)."""

    vel: float = 0.0
    azimute: float = 0.0
    elevacao: float = 0.0
    ativo: bool = True
    reiniciar: int | None = None     # None = campo ausente: não mexe no contador
    loop: bool | None = None         # None = campo ausente: não mexe no modo


def _numero(dados: dict, campo: str, predefinido: float) -> float:
    """Campo numérico finito do registo (`ValueError` descritivo se não o for)."""
    valor = dados.get(campo, predefinido)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(float(valor)):
        raise ValueError(f"`{campo}` tem de ser um número finito (recebido {valor!r})")
    return float(valor)


def _booleano(dados: dict, campo: str) -> bool | None:
    """Campo booleano opcional do registo (tolera 0/1 escrito à mão); `None` se ausente."""
    valor = dados.get(campo)
    if valor is None:
        return None
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, int) and valor in (0, 1):
        return bool(valor)
    raise ValueError(f"`{campo}` tem de ser booleano (recebido {valor!r})")


def ler_registo(dados) -> Registo:
    """Ficheiro de controlo → `Registo` validado (mesmas regras do net_probe/dashboard).

    `vel` ∈ [0, 5] e finita; `azimute` reduzido a [0, 360); `elevacao` cortada a [-90, 90]; `ativo` booleano
    (predefinido `True`, como no contrato v2); `reiniciar` inteiro ≥ 0 e `loop` booleano, ambos OPCIONAIS
    (`None` = «não mexe»). Fora disto é `ValueError` e o vento anterior fica em vigor.
    """
    if not isinstance(dados, dict):
        raise ValueError("o ficheiro não é um objeto JSON")  # noqa: TRY004  (conteúdo, não um tipo errado)
    vel = _numero(dados, "vel", 0.0)
    if not 0.0 <= vel <= VEL_MAX:
        raise ValueError(f"`vel` tem de estar em [0, {VEL_MAX}] m/s (recebido {vel!r})")
    azimute = _numero(dados, "azimute", 0.0) % AZIM_MAX
    elevacao = min(ELEV_MAX, max(-ELEV_MAX, _numero(dados, "elevacao", 0.0)))
    ativo = _booleano(dados, "ativo")
    reiniciar = dados.get("reiniciar")
    if reiniciar is not None:
        if isinstance(reiniciar, bool) or not isinstance(reiniciar, int) or reiniciar < 0:
            raise ValueError(f"`reiniciar` tem de ser um inteiro ≥ 0 (recebido {reiniciar!r})")
        reiniciar = int(reiniciar)
    return Registo(vel, azimute, elevacao, True if ativo is None else ativo, reiniciar,
                   _booleano(dados, "loop"))


class Controlo:
    """Vigia o ficheiro de controlo (assinatura mtime_ns+tamanho) e tradu-lo em vento + comandos.

    Verificado a CADA passo de decisão: uma escrita atómica do site chega à física no passo seguinte. Sem
    ficheiro, mantém-se o vento em vigor (o arranque é em ar parado). Um ficheiro inválido é ignorado com um
    aviso (uma vez por texto) — o ciclo nunca morre por causa do controlo.
    """

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self.reiniciar: int | None = None       # último contador visto (None = ainda nenhum)
        self.loop: bool | None = None           # último modo pedido (None = nunca pedido)
        self.pedido_reinicio = False            # há um REINICIAR por consumir
        self.n_ventos = 0
        self.n_reinicios = 0
        self.ultimo: Registo | None = None
        self._assinatura: tuple[int, int] | None = None
        self._avisos: set[str] = set()
        self._le_contador_inicial()

    def _le_contador_inicial(self) -> None:
        """Linha de base do contador (sem aplicar vento nenhum): o que o ficheiro já tiver no arranque."""
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            registo = ler_registo(dados)
        except (OSError, ValueError):
            return                                  # sem ficheiro (ou inválido): a linha de base fica None
        self.reiniciar, self.loop = registo.reiniciar, registo.loop

    def _assinatura_do_ficheiro(self) -> tuple[int, int] | None:
        """(mtime_ns, tamanho) do ficheiro — `None` se não existe (ou desapareceu)."""
        try:
            st = self.caminho.stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def verifica(self, env: HoverEnv) -> Registo | None:
        """Um passo de decisão: aplica o vento se o ficheiro mudou; devolve o registo aplicado (ou `None`).

        Os comandos (`reiniciar`/`loop`) são lidos na mesma passagem e ficam no próprio objecto; um contador
        novo levanta `pedido_reinicio` (consumido com `consumir_reinicio()`).
        """
        assinatura = self._assinatura_do_ficheiro()
        if assinatura == self._assinatura:
            return None
        self._assinatura = assinatura                # marca já: um ficheiro inválido não é relido sempre
        if assinatura is None:
            return None                              # sem ficheiro: mantém o vento em vigor
        try:
            registo = ler_registo(json.loads(self.caminho.read_text(encoding="utf-8")))
        except (OSError, ValueError) as erro:
            self._aviso(f"controlo ignorado ({erro}) — mantenho o vento anterior")
            return None
        self._actualiza_comandos(registo)
        self._aplica(env, registo)
        return registo

    def _actualiza_comandos(self, registo: Registo) -> None:
        """Regra do contador: 1.º visto = linha de base; ≥ 1 sem ficheiro prévio = REINICIAR já pedido."""
        if registo.loop is not None:
            self.loop = bool(registo.loop)
        if registo.reiniciar is None:
            return
        if self.reiniciar is None:
            if registo.reiniciar > 0:                # o ficheiro nasceu já com um REINICIAR pedido
                self.pedido_reinicio = True
                print(f"[sim] REINICIAR pedido (contador {registo.reiniciar}, sem linha de base)", flush=True)
        elif registo.reiniciar != self.reiniciar:
            self.pedido_reinicio = True
            print(f"[sim] REINICIAR pedido (contador {self.reiniciar} -> {registo.reiniciar})", flush=True)
        self.reiniciar = int(registo.reiniciar)

    def _aplica(self, env: HoverEnv, registo: Registo) -> None:
        """`ativo` → `definir_vento(vel, azimute, elevacao)`; inativo → `definir_vento(0, 0, 0)`."""
        if registo.ativo:
            env.definir_vento(registo.vel, registo.azimute, registo.elevacao)
        else:
            env.definir_vento(0.0, 0.0, 0.0)
        self.n_ventos += 1
        self.ultimo = registo
        print(f"[sim] vento -> {registo.vel:.2f} m/s @ {registo.azimute:.1f} deg"
              + (f" (elev {registo.elevacao:+.1f} deg)" if registo.elevacao else "")
              + ("" if registo.ativo else " [desligado]"), flush=True)

    def consumir_reinicio(self) -> bool:
        """`True` uma única vez por cada REINICIAR pedido (o pedido é limpo ao consumir)."""
        if not self.pedido_reinicio:
            return False
        self.pedido_reinicio = False
        self.n_reinicios += 1
        return True

    def _aviso(self, mensagem: str) -> None:
        """Aviso em stdout, uma vez por texto (um ficheiro inválido não inunda o terminal a 50 Hz)."""
        if mensagem not in self._avisos:
            self._avisos.add(mensagem)
            print(f"[sim] aviso: {mensagem}", flush=True)


# ---------------------------------------------------------------------------------------------- hooks MLP
class Sonda:
    """Forward hooks nos `nn.Linear` da política: `h1`/`h2` = 1.ª/2.ª camada escondida (pré-tanh).

    Mesma técnica (e mesma ordem) do `net_probe.py`: `mlp_extractor.policy_net` primeiro, `action_net` no fim.
    """

    def __init__(self, politica) -> None:
        self.saidas: dict[int, np.ndarray] = {}
        self._handles = []
        lineares = self._lineares(politica)
        if len(lineares) < 2:
            raise SystemExit(f"[sim] a política só tem {len(lineares)} camadas Linear (esperava 2 escondidas "
                             "+ a cabeça de ação) — a telemetria desenha h1/h2 da MLP [16, 64, 64, 4]")
        for i, camada in enumerate(lineares):
            self._handles.append(camada.register_forward_hook(self._hook(i)))

    @staticmethod
    def _lineares(politica) -> list:
        """Todos os `nn.Linear` na ordem política: primeiro `policy_net`, depois `action_net`."""
        if not hasattr(politica, "mlp_extractor") or not hasattr(politica.mlp_extractor, "policy_net"):
            raise SystemExit("[sim] a política não tem `mlp_extractor.policy_net` — só se sonda MlpPolicy")
        modulos = [m for m in politica.mlp_extractor.policy_net.modules() if m.__class__.__name__ == "Linear"]
        modulos += [m for m in politica.action_net.modules() if m.__class__.__name__ == "Linear"]
        return modulos

    def _hook(self, i: int):
        def guardar(_modulo, _entrada, saida):
            self.saidas[i] = np.asarray(saida.detach().cpu().numpy()[0])   # 1.ª amostra do batch
        return guardar

    def escondidas(self) -> tuple[np.ndarray, np.ndarray]:
        """`(h1, h2)` da última passagem; zeros (16→64) se ainda não houve forward."""
        ordem = sorted(self.saidas)
        if len(ordem) < 2:
            return np.zeros(64), np.zeros(64)
        return self.saidas[ordem[0]], self.saidas[ordem[1]]

    def limpar(self) -> None:
        """Esquece as ativações (chamado no reset: a 1.ª linha do episódio não mostra o forward anterior)."""
        self.saidas.clear()

    def fechar(self) -> None:
        for handle in self._handles:
            handle.remove()
        self._handles.clear()


# ---------------------------------------------------------------------------------------------- telemetria
class Telemetria:
    """Escritor JSONL da telemetria: 1 linha por amostra, ~10 Hz (1 Hz com o episódio parado) + eventos.

    Abre em modo `"a"` (cada arranque continua o ficheiro: o site vê o histórico todo) e escreve com `flush`
    para não haver atraso de buffer. `talvez_amostra` decide pelo relógio; `evento` escreve sempre (é o que
    marca o fim de um episódio sem esperar pelos 0,1 s).
    """

    def __init__(self, caminho: Path, truncar: bool = False) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._ficheiro = self.caminho.open("w" if truncar else "a", encoding="utf-8")
        self.n_linhas = 0
        self._t_ultima = 0.0

    def escrever(self, amostra: dict) -> None:
        """Uma linha JSON (chaves por ordem fixa) já com `flush`."""
        self._ficheiro.write(json.dumps(amostra, separators=(",", ":")) + "\n")
        self._ficheiro.flush()
        self.n_linhas += 1
        self._t_ultima = time.perf_counter()

    def talvez_amostra(self, amostra: dict, periodo: float = PERIODO_AMOSTRA) -> bool:
        """Escreve se já passou `periodo` desde a última linha; devolve se escreveu."""
        agora = time.perf_counter()
        if agora - self._t_ultima < periodo:
            return False
        self.escrever(amostra)
        return True

    def fechar(self) -> None:
        try:
            self._ficheiro.close()
        except OSError:
            pass


def _lista(vetor, n: int) -> list[float]:
    """Vector → lista JSON de `n` floats arredondados (zeros se o vector não tiver o tamanho esperado)."""
    a = np.asarray(vetor if vetor is not None else np.zeros(n), dtype=float).reshape(-1)
    if a.size != n:
        a = np.zeros(n)
    return [round(float(v), PRECISAO) for v in a]


def _vento_polar(env: HoverEnv) -> tuple[float, float]:
    """`(vel, azimute)` em m/s e graus do vento ATIVO (`env.vento_atual`; azimute 0° → +x, 90° → +y)."""
    v = np.asarray(env.vento_atual, dtype=float).reshape(3)
    vel = float(np.linalg.norm(v))
    if vel == 0.0:
        return 0.0, 0.0
    return vel, round(float(np.degrees(np.arctan2(v[1], v[0]))), PRECISAO) % AZIM_MAX


# ---------------------------------------------------------------------------------------------- teclado
class Teclas:
    """Estado do `key_callback` do viewer: ESPAÇO pausa/retoma, Q/Esc fecha (nada mais — sem HUD)."""

    def __init__(self) -> None:
        self.pausa = False
        self.fechar = False

    def ao_teclar(self, tecla: int) -> None:
        if tecla == TECLA_ESPACO:
            self.pausa = not self.pausa
        elif tecla in (TECLA_Q, TECLA_ESC):
            self.fechar = True


# ---------------------------------------------------------------------------------------------- ciclo
@dataclass
class Estado:
    """Estado do rollout que a telemetria publica (uma linha por amostra)."""

    ep: int = 1
    retorno: float = 0.0
    completos: int = 0               # episódios já terminados nesta sessão
    congelado: bool = False          # episódio terminado: a física está PARADA à espera de REINICIAR
    pausado: bool = False
    loop: bool = False
    obs: np.ndarray | None = None
    acao: np.ndarray | None = None
    h1: np.ndarray | None = None
    h2: np.ndarray | None = None
    info: dict | None = None


def amostra(env: HoverEnv, est: Estado) -> dict:
    """Uma linha de telemetria com as chaves (e a ordem) do contrato.

    `ctrl` é o comando FÍSICO que a ação produziu — `data.ctrl` = [empuxo N, mx, my, mz N·m], escrito pelo
    `env.aplicar_acao` — para o site não ter de o derivar da ação e o poder rotular "ctrl do backend".
    Aditivo: as chaves antigas ficam na mesma ordem.

    INVARIANTE (a única que se promete): `ctrl == acao_para_ctrl(act)` nas linhas com AÇÃO APLICADA, ou seja
    `passo > 0` — são as que saem de um `env.step`, e o `data.ctrl` é exactamente o comando que a física usou.
    Nas linhas de ARRANQUE (a 1.ª do processo) e de REINÍCIO (episódio novo, `--loop`), que têm `passo == 0`
    e `t == 0`, vale `act == ctrl == [0, 0, 0, 0]`: o `env.reset()` zera o `data.ctrl` e ainda NÃO houve ação
    nenhuma. Aí a identidade NÃO se aplica — e não se inventa um `ctrl` que o simulador não aplicou: zeros é
    "nenhuma ação" (verdadeiro), enquanto `acao_para_ctrl([0,0,0,0])` = `[mg, 0, 0, 0]` = "ação nula" (o
    hover com 0,26487 N), que é outra coisa. Para separar as duas, basta `passo > 0`.
    """
    info = est.info if est.info else {}
    vento_vel, vento_azim = _vento_polar(env)
    return {
        "t": round(float(env.data.time), PRECISAO),
        "estado": "episodio_terminado" if est.congelado else "a_correr",
        "ep": int(est.ep),
        "passo": int(env.passos),
        "retorno": round(float(est.retorno), PRECISAO),
        "z": round(float(info.get("z", 0.0)), PRECISAO),
        "dist_xy": round(float(info.get("dist_xy", 0.0)), PRECISAO),
        "yaw_err": round(float(info.get("yaw_err", 0.0)), PRECISAO),
        "vento_vel": round(vento_vel, PRECISAO),
        "vento_azim": round(vento_azim, PRECISAO),
        "obs": _lista(est.obs, 16),
        "act": _lista(est.acao, 4),
        "ctrl": _lista(env.data.ctrl, 4),
        "h1": _lista(est.h1, 64),
        "h2": _lista(est.h2, 64),
    }


def _reiniciar(env: HoverEnv, est: Estado, sonda: Sonda, seed: int, ep: int | None = None) -> None:
    """`env.reset` (+ limpeza dos hooks) e volta ao estado "a correr"; `ep` só muda quando é episódio novo."""
    est.obs, est.info = env.reset(seed=seed)
    est.acao = np.zeros(4)
    est.h1, est.h2 = np.zeros(64), np.zeros(64)
    est.retorno = 0.0
    est.congelado = False
    sonda.limpar()
    if ep is not None:
        est.ep = ep


def correr(env: HoverEnv, politica, controlo: Controlo, telemetria: Telemetria, sonda: Sonda, args,
          viewer=None, teclas: Teclas | None = None) -> int:
    """Ciclo principal (serve a janela e o modo `--sem-janela`): passos de decisão a 50 Hz com o ritmo de
    `--fator-tempo`, leitura do controlo em cada passo, telemetria a ~10 Hz e PARAGEM no fim do episódio.

    Devolve 0. `viewer=None` → sem janela (nenhum import de GLFW/GL é feito aqui). Um `viewer` falso (testes)
    só precisa de `sync()`, `is_running()`, `lock()`, `m` e `viewport` — nunca se lhe toca no texto/figuras.
    """
    est = Estado(loop=bool(args.loop), congelado=False)
    _reiniciar(env, est, sonda, args.seed, ep=1)
    telemetria.escrever(amostra(env, est))               # linha de evento do arranque
    print(f"[sim] rollout: ep 1 comecou (seed {args.seed}, vento {_vento_polar(env)[0]:.2f} m/s); "
          f"sem --loop a fisica PARA no fim do episodio e so um REINICIAR a retoma", flush=True)
    proximo = time.perf_counter()
    t_ini = proximo
    terminar = False

    def parar(*_args):
        nonlocal terminar
        terminar = True

    for sinal in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sinal, parar)
        except ValueError:                               # não estamos na main thread: sem sinais
            pass

    while not terminar:
        if teclas is not None:
            if teclas.fechar:
                break
            est.pausado = bool(teclas.pausa)
        if viewer is not None and not viewer.is_running():
            break

        # 1) controlo do site: vento + REINICIAR + modo loop (a cada passo de decisão, como o dashboard)
        registo = controlo.verifica(env)
        if registo is not None and registo.loop is not None:
            est.loop = bool(registo.loop)
            print(f"[sim] loop {'ligado' if est.loop else 'desligado'} pelo controlo", flush=True)
        if controlo.consumir_reinicio():
            novo_ep = est.ep + 1 if (env.passos > 0 or est.congelado) else est.ep
            _reiniciar(env, est, sonda, args.seed + novo_ep - 1, ep=novo_ep)
            telemetria.escrever(amostra(env, est))       # evento: episódio novo, passo 0
            print(f"[sim] REINICIAR: ep {est.ep} comecou (passo 0, retorno 0)", flush=True)

        # 2) com o episódio terminado (ou em pausa) não há física: janela viva + batimento na telemetria
        if est.congelado or est.pausado:
            if viewer is not None:
                viewer.sync()
            telemetria.talvez_amostra(amostra(env, est),
                                      PERIODO_PARADO if est.congelado else PERIODO_AMOSTRA)
            if args.max_segundos and time.perf_counter() - t_ini >= args.max_segundos:
                print("[sim] --max-segundos atingido", flush=True)
                break
            time.sleep(PERIODO_OCIO)
            proximo = time.perf_counter()
            continue

        # 3) passo de decisão: rede -> ação -> física (10 passos de física a 500 Hz)
        try:
            acao, _estado = politica.predict(est.obs, deterministic=True)
            est.acao = np.asarray(acao, dtype=float).reshape(4)
            est.h1, est.h2 = sonda.escondidas()
            est.obs, recompensa, terminado, truncado, est.info = env.step(est.acao)
        except RuntimeError as erro:                     # sanidade do HoverEnv: estado divergiu
            print(f"[sim] a simulacao divergiu ({erro}) — use definir_vento com um valor sao pelo site",
                  file=sys.stderr, flush=True)
            return 1
        est.retorno += float(recompensa)
        telemetria.talvez_amostra(amostra(env, est))
        if terminado or truncado:
            motivo = "caiu/capotou" if terminado else "tempo"
            est.completos += 1
            fim = f"ep {est.ep} terminou ({motivo}, retorno {est.retorno:+.3f})"
            if args.max_episodios and est.completos >= args.max_episodios:
                print(f"[sim] {fim} -> --max-episodios {args.max_episodios} atingido (nao arranca outro)",
                      flush=True)
                break
            if est.loop:                                 # auto-reset pedido (--loop ou loop:true)
                print(f"[sim] {fim} -> auto-reset (--loop)", flush=True)
                _reiniciar(env, est, sonda, args.seed + est.ep, ep=est.ep + 1)
                telemetria.escrever(amostra(env, est))
            else:
                est.congelado = True                     # SEM auto-loop: a física PARA aqui
                telemetria.escrever(amostra(env, est))   # evento imediato (não espera pelos 0,1 s)
                print(f"[sim] {fim} - episodio_terminado: a fisica esta PARADA, reinicie pelo site",
                      flush=True)
        if viewer is not None:
            viewer.sync()

        # 4) ritmo: 1 passo de decisão por dt_decisao/fator_tempo (0 = sem travão, o mais rápido possível)
        if args.fator_tempo > 0.0:
            proximo += env.dt_decisao / args.fator_tempo
            resto = proximo - time.perf_counter()
            if resto > 0:
                time.sleep(resto)
            else:
                proximo = time.perf_counter()
        if args.max_segundos and time.perf_counter() - t_ini >= args.max_segundos:
            print("[sim] --max-segundos atingido", flush=True)
            break
    print(f"[sim] fim: {telemetria.n_linhas} linhas de telemetria em {telemetria.caminho}", flush=True)
    return 0


def esperar_fecho(viewer, limite: float = 2.0) -> float:
    """Espera que a thread do viewer termine antes de o processo sair; devolve os segundos esperados.

    Medido nesta máquina (mujoco 3.15, KDE Wayland): sair logo a seguir a fechar a janela corre o
    `glfw.terminate()` do `atexit` AO MESMO TEMPO que a thread do viewer destroi o contexto GLFW — SIGSEGV
    intermitente no FIM do processo. Esperar que o `Handle` perca a referência ao simulador elimina a
    corrida; o limite garante que isto nunca pendura.
    """
    t0 = time.perf_counter()
    while getattr(viewer, "m", None) is not None and time.perf_counter() - t0 < limite:
        time.sleep(0.05)
    return time.perf_counter() - t0


def correr_com_janela(env: HoverEnv, politica, controlo: Controlo, telemetria: Telemetria, sonda: Sonda,
                      args) -> int:
    """Abre a janela LIMPA (`show_left_ui=False`, `show_right_ui=False`, zero overlay) e corre o ciclo."""
    from mujoco import viewer as mjviewer  # import tardio: o modo --sem-janela não carrega GLFW/GL

    teclas = Teclas()
    viewer = None
    try:
        with mjviewer.launch_passive(env.model, env.data, key_callback=teclas.ao_teclar,
                                     show_left_ui=False, show_right_ui=False) as viewer:
            viewer.clear_texts()                         # garante zero overlay (nunca se usa set_texts)
            return correr(env, politica, controlo, telemetria, sonda, args, viewer=viewer, teclas=teclas)
    except KeyboardInterrupt:
        return 0
    finally:
        if viewer is not None:
            esperar_fecho(viewer)


# ---------------------------------------------------------------------------------------------- CLI
def _fator_de_tempo(texto: str) -> float:
    """`--fator-tempo` → float finito ≥ 0 (0 = sem travão, 1 = tempo real)."""
    try:
        valor = float(str(texto).strip())
    except ValueError as erro:
        raise argparse.ArgumentTypeError(f"esperado um número (recebido {texto!r})") from erro
    if not math.isfinite(valor) or valor < 0.0:
        raise argparse.ArgumentTypeError(f"tem de ser finito e ≥ 0 (recebido {texto!r}; 0 = sem travão)")
    return valor


def _mais_recente(caminhos) -> Path | None:
    """Ficheiro mais recente de `caminhos` (empate desfeito pelo nome, para ser determinístico)."""
    ficheiros = [p for p in caminhos if p.is_file()]
    return max(ficheiros, key=lambda p: (p.stat().st_mtime_ns, str(p))) if ficheiros else None


def _modelo_validado(out: Path) -> tuple[Path, str] | None:
    """Modelo da ÚLTIMA validação COM SUCESSO em `out/avaliacao_vento/*.json` que ainda exista em disco.

    Os relatórios do `avaliar_vento.py`/`avaliar_denso.py` gravam
    `{"modelo": ..., "n_pass": ..., "n_total": ..., "satisfatorio": bool}` (o `modelo` é relativo à raiz do
    laboratório). Só contam os `satisfatorio: true` (ou `n_pass == n_total`): uma validação que correu MAL
    não promove ninguém. É a melhor pista que existe em disco sobre qual política voa bem — foi o que o dono
    validou (ex.: `vento_r9_polir_vento3/final.zip`, 16/16).
    """
    registos = sorted((out / "avaliacao_vento").glob("*.json"),
                      key=lambda p: p.stat().st_mtime_ns, reverse=True)
    for registo in registos:
        try:
            dados = json.loads(registo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(dados, dict) or not isinstance(dados.get("modelo"), str) or not dados["modelo"]:
            continue
        n_pass, n_total, ok = dados.get("n_pass"), dados.get("n_total"), dados.get("satisfatorio")
        if ok is None:
            ok = (isinstance(n_pass, int) and isinstance(n_total, int) and n_total > 0
                  and n_pass == n_total)
        if not ok:
            continue
        caminho = Path(dados["modelo"])
        if not caminho.is_absolute():
            caminho = _RAIZ / caminho       # os relatórios gravam caminhos relativos à raiz do laboratório
        if caminho.is_file():
            resumo = f"{n_pass}/{n_total}" if isinstance(n_pass, int) and isinstance(n_total, int) else "ok"
            return caminho, f"validacao mais recente ({registo.name}: {resumo})"
    return None


def modelo_por_omissao() -> tuple[Path, str]:
    """`(caminho, motivo)` do modelo por omissão — a ordem de preferência é a MESMA do `sim_site.py`.

    1. o modelo da ÚLTIMA validação com sucesso em `out/avaliacao_vento/*.json` que exista em disco
       (é a política validada pelo dono — ex.: `vento_r9_polir_vento3/final.zip`, 16/16);
    2. `out/vento_*/final.zip` mais recente SEM `_seed` no nome (os "polir/curr" treinados com vento);
    3. `out/vento_*_seed*/final.zip` mais recente (as séries com sementes);
    4. `out/runs/*/final.zip` mais recente;
    5. um `best_model.zip` qualquer (`out/vento_*/` ou `out/runs/*/`) — último recurso;
    6. `SystemExit` com mensagem clara se não houver nada.

    Nunca se escolhe um `best_model.zip` de `out/runs/*/` enquanto existir um `final.zip` de `out/vento_*/`
    (era isso que punha a política fraca antiga a voar e o drone a "sumir" logo no arranque).
    """
    out = _AQUI / "out"
    validado = _modelo_validado(out)
    if validado is not None:
        return validado
    vento = sorted(out.glob("vento_*/final.zip"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    candidato = _mais_recente(p for p in vento if "_seed" not in p.parent.name)
    if candidato is not None:
        return candidato, "vento_*/final.zip mais recente (sem _seed)"
    candidato = _mais_recente(vento)
    if candidato is not None:
        return candidato, "vento_*_seed*/final.zip mais recente"
    candidato = _mais_recente((out / "runs").glob("*/final.zip"))
    if candidato is not None:
        return candidato, "runs/*/final.zip mais recente"
    candidato = _mais_recente(list((out / "runs").glob("*/best_model.zip"))
                              + list(out.glob("vento_*/best_model.zip")))
    if candidato is not None:
        return candidato, "best_model.zip mais recente (ultimo recurso)"
    raise SystemExit(f"[sim] nenhum modelo em {out} (avaliacao_vento/*.json, vento_*/final.zip, "
                     "runs/*/final.zip, best_model.zip) — treine primeiro (train.py) ou indique --model "
                     "CAMINHO")


def carregar_politica(caminho: Path):
    """PPO do Stable-Baselines3 em CPU; `SystemExit` com mensagem clara se o ficheiro não for um zip de PPO."""
    from stable_baselines3 import PPO
    try:
        return PPO.load(str(caminho), device="cpu")
    except Exception as erro:
        raise SystemExit(f"[sim] não consegui carregar {caminho} como PPO do Stable-Baselines3: {erro}") from erro


def analisar_argumentos(argv=None) -> argparse.Namespace:
    """Argumentos do runner (o modelo por omissão é descoberto em `out/runs/*/`)."""
    p = argparse.ArgumentParser(
        description="Runner da simulação do hover: janela MuJoCo 100% limpa (sem HUD nem figuras) + "
                    "telemetria JSONL para o site; o vento e o REINICIAR chegam pelo ficheiro de controlo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Teclado (foco na janela): ESPACO pausa/retoma · Q ou Esc fecha.\n"
            "\n"
            "Ficheiros: --controlo {\"vel\",\"azimute\",\"elevacao\",\"ativo\",\"reiniciar\",\"loop\",\"t\"} (lido a\n"
            "cada passo de decisão) e --telemetria JSONL a ~10 Hz (1 Hz com o episódio parado).\n"
            "\n"
            "Sem auto-loop por omissão: no fim do episódio a física PARA e só um REINICIAR (site) ou\n"
            "--loop/loop:true a retoma."
        ),
    )
    p.add_argument("--model", type=Path, default=None,
                   help="modelo do Stable-Baselines3 (.zip); por omissão, por ordem: o modelo da última "
                        "validação com sucesso (out/avaliacao_vento/*.json) -> vento_*/final.zip mais recente "
                        "(sem _seed) -> vento_*_seed*/final.zip -> runs/*/final.zip -> best_model.zip")
    p.add_argument("--sem-janela", action="store_true",
                   help="rollout SEM viewer (nenhum import de mujoco.viewer/glfw): escreve a telemetria e o "
                        "vento/REINICIAR funcionam na mesma — é o modo dos testes")
    p.add_argument("--controlo", type=Path, default=CONTROLO_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro JSON de controlo (vento + reiniciar + loop); padrão: {CONTROLO_OMISSAO}")
    p.add_argument("--telemetria", type=Path, default=TELEMETRIA_OMISSAO, metavar="CAMINHO",
                   help=f"ficheiro JSONL de telemetria (~10 Hz); padrão: {TELEMETRIA_OMISSAO}")
    p.add_argument("--fator-tempo", type=_fator_de_tempo, default=FATOR_TEMPO_OMISSAO, metavar="F",
                   help="ritmo do rollout: 1 = tempo real (PADRÃO), 2 = 2x mais rápido, 0.5 = metade, "
                        "0 = sem travão (o mais rápido possível)")
    p.add_argument("--loop", action="store_true",
                   help="auto-reset no fim de cada episódio (por omissão a física PARA e espera um "
                        "REINICIAR; o campo `loop` do controlo liga/desliga isto a quente)")
    p.add_argument("--seed", type=int, default=0,
                   help="semente do reset — o episódio N usa seed + N - 1 (padrão: 0)")
    p.add_argument("--max-segundos", type=float, default=0.0, metavar="S",
                   help="sai (exit 0) ao fim de S segundos de relógio; 0 = sem limite (padrão: 0)")
    p.add_argument("--max-episodios", type=int, default=0, metavar="N",
                   help="sai (exit 0) quando o episódio N acabar; 0 = sem limite (padrão: 0)")
    p.add_argument("--truncar-telemetria", action="store_true",
                   help="começa a telemetria do zero (por omissão o ficheiro é continuado, em modo append)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    """Carrega o modelo e a política e entra no ciclo (janela limpa ou `--sem-janela`)."""
    args = analisar_argumentos(argv)
    if args.model is not None:
        caminho, motivo = args.model, "explicito (--model)"
    else:
        caminho, motivo = modelo_por_omissao()          # diz SEMPRE qual escolheu e porquê
    if not caminho.is_file():
        raise SystemExit(f"[sim] modelo inexistente: {caminho}")
    env = HoverEnv()
    politica = carregar_politica(caminho)
    controlo = Controlo(args.controlo)
    telemetria = Telemetria(args.telemetria, truncar=args.truncar_telemetria)
    sonda = Sonda(politica.policy)
    modo = "--sem-janela (sem viewer)" if args.sem_janela else (
        "janela limpa (show_left_ui=False, show_right_ui=False, sem set_texts/set_figures)")
    ritmo = f"{args.fator_tempo:g}x o tempo real" if args.fator_tempo > 0 else "sem travao (o mais rapido)"
    print(f"[sim] modelo: {caminho} ({motivo})")
    print(f"[sim] controlo: {_relativo(args.controlo)} | telemetria: {_relativo(args.telemetria)}")
    print(f"[sim] modo: {modo} | ritmo: {ritmo} | "
          f"loop: {'ligado' if args.loop else 'desligado (espera REINICIAR)'}", flush=True)
    try:
        if args.sem_janela:
            return correr(env, politica, controlo, telemetria, sonda, args)
        return correr_com_janela(env, politica, controlo, telemetria, sonda, args)
    finally:
        sonda.fechar()
        telemetria.fechar()


def _relativo(caminho: Path) -> str:
    """Caminho relativo à raiz do laboratório quando possível (leitura mais curta nos logs)."""
    try:
        return str(Path(caminho).relative_to(_RAIZ))
    except ValueError:
        return str(caminho)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # `stdout` fechou do outro lado (ex.: `| head`): sair sem traceback e sem o aviso de flush
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
