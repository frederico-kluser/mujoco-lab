#!/usr/bin/env python3
"""net_probe.py — a REDE NEURAL a correr, com VENTO CONTROLADO AO VIVO, em JSONL (subprocesso sem janela).

Corre a política PPO do hover num `HoverEnv` headless e, a cada `--interval` segundos, escreve UMA linha
JSONL (append por ficheiro novo) com tudo o que a UI precisa para desenhar a MLP [16, 64, 64, 4] ao vivo:

    {"t": 0.204, "obs": [16 floats], "h1": [64], "h2": [64], "act": [4], "z": 1.02, "dist_xy": 0.01,
     "no_alvo": false, "yaw_err": -0.021, "vento_vel": 5.0, "vento_azim": 0.0}

COMO SÃO APANHADAS AS ATIVAÇÕES
  Forward hooks em CADA `nn.Linear` da política (`policy.mlp_extractor.policy_net` e `policy.action_net`),
  pela ordem de execução: `h1` = saída da 1.ª Linear (pré-tanh), `h2` = saída da 2.ª Linear (pré-tanh),
  `act` = saída da `action_net` = MÉDIA GAUSSIANA CRUA (a `DiagGaussianDistribution` do SB3 usa
  `squash_output=False`: NÃO há tanh na amostra, logo |act| pode passar de 1 — o corte à faixa do atuador
  é feito pelo env, em `HoverEnv.acao_para_ctrl`). Captura-se a PRIMEIRA amostra do batch (`out[0]`,
  `detach().cpu().numpy()`) — a política é alimentada com uma só obs.
  ALINHAMENTO (uma linha = um instante): `obs` é a obs QUE ENTROU no forward que produziu `h1`/`h2`/`act`
  dessa mesma linha, e `z`/`dist_xy`/`no_alvo`/`yaw_err` são medidos no mesmo instante dessa obs (o `info` do
  estado correspondente) — nunca a obs PÓS-step emparelhada com ativações do passo anterior. Invariante
  verificável linha a linha: `h1 == Linear_1(obs)` (a 1.ª camada é Linear pura, sem tanh antes dela).
  A topologia é FIXA [16, 64, 64, 4]; o script valida-a ao arrancar e avisa (stderr) se não bater certo.

VENTO AO VIVO (`--controlo`, o par do painel «VENTO» do dashboard)
  A CADA passo de decisão (N=1, para a reação ser imediata) olha-se para o mtime do ficheiro de controlo
  escrito pelo dashboard (`POST /api/vento`, escrita atómica tmp+rename):
      {"vel": 5.0, "azimute": 0.0, "elevacao": 0.0, "ativo": true, "t": 1234567.89}
  Quando o ficheiro MUDA, aplica-se `env.definir_vento(vel, azimute, elevacao)`; com `"ativo": false`
  aplica-se `definir_vento(0, 0, 0)` (vento PARADO). Convenção do env: azimute 0° → +x, 90° → +y, elevação
  positiva → +z; o vento é a física REAL do modelo de fluido (o `cf2.xml` traz ρ = 1,225 kg/m³), logo o
  drone DERIVA sem ser teleportado. O vento escrito vive em `model.opt.wind` e SOBREVIVE aos `reset` do
  episódio (o env reescreve-o no reset), por isso o empurrão é contínuo enquanto estiver ligado.
  Um ficheiro ilegível/fora do contrato NÃO derruba a sonda: avisa UMA vez (stderr) e mantém o vento em
  vigor. `--vento-inicial vel,azim[,elev]` aplica um vento antes do 1.º passo (ex.: `--vento-inicial 5,90`).

EPISÓDIOS (`--sem-loop` é o DEFAULT — o dono quer VER um episódio de cada vez)
  Sem loop, quando o episódio acaba (`terminated` OU `truncated`) a sonda NÃO avança mais a física: escreve
  UMA linha final igual às outras mas com `"evento": "fim_episodio"`, `"motivo": "terminado"|"truncado"` e
  `"episodio": <n>` (o `obs`/`h1`/`h2`/`act` dessa linha são um forward no estado final, logo o alinhamento
  da rede mantém-se válido) e fica EM ESPERA, com o drone parado no sítio onde acabou. Só retoma quando o
  contador de reinício mudar — ou quando o modo LOOP for ligado.
  Os dois campos de comando vivem no MESMO ficheiro de controlo do vento (opcionais):
      {"vel": 5.0, "azimute": 0.0, "elevacao": 0.0, "ativo": true, "reiniciar": 3, "loop": false}
  · `"reiniciar": <int ≥ 0>` — contador; quando MUDA, o episódio é reiniciado (`env.reset`), mesmo a meio.
    O 1.º contador que se vê é linha de base (não reinicia), exceto se for ≥ 1 sem nunca ter havido
    ficheiro: aí é um REINICIAR já pedido (senão o clique perdia-se enquanto a sonda esperava).
  · `"loop": <bool>` — `true` volta ao auto-reset antigo; `false` volta ao modo de espera (e, se estiver em
    espera, retoma já o episódio). `--loop`/`--sem-loop` dão o modo inicial (default `--sem-loop`).
  Ficheiro ESCRITO POR UMA VERSÃO ANTIGA (sem `reiniciar`/`loop`): os campos ausentes não mexem em nada —
  o modo inicial é o do CLI (sem-loop por omissão) e nunca há pedido de reinício; é o contrato do vento
  intacto, com a única diferença de o fim do episódio passar a esperar em vez de reiniciar sozinho.

RITMO DA SIMULAÇÃO (`--fator-tempo`, default 0 = o mais rápido possível)
  Sem travão a física corre MUITO acima do tempo real (medido: ~28–30× com uma política MLP em CPU — varia com
  a carga da máquina, já se mediu ~56× com a máquina livre), o que é
  ótimo para encher o JSONL depressa mas péssimo para VER o drone a corrigir. Com `--fator-tempo 1` a sonda
  trava o ciclo (dorme o necessário) para o tempo de SIMULAÇÃO avançar a F× o tempo de parede: é o que o
  dashboard pede para a «rede ao vivo» (`POST /api/net/start {fator_tempo: 1}`). 0 desliga o travão.
  O travão é POR EPISÓDIO: cada `env.reset` (reinício ou auto-reset) recomeça a contagem, para o tempo
  passado EM ESPERA (sem física a correr) não deixar o episódio seguinte sem travão nenhum.

    uv run --group hover-rl python experiments/09_drone_hover_rl/net_probe.py \
        --model experiments/09_drone_hover_rl/out/run_x/best_model.zip --out "$TMPDIR/net.jsonl" \
        --interval 0.2 --controlo experiments/09_drone_hover_rl/out/controle_vento.json

Sem viewer, sem render, sem rede: só física + inferência + ficheiros. Ctrl+C (ou SIGTERM) fecha o ficheiro
e sai com 0 — o dashboard lança-o e mata-o por SIGTERM (`POST /api/net/stop`).
"""
from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import time
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in _AQUI.parents if (p / "pyproject.toml").exists())
sys.path.insert(0, str(_RAIZ))
sys.path.insert(0, str(_AQUI))
from lab import mjkit  # noqa: F401, I001  (MUJOCO_GL=egl antes de `import mujoco`: ordem de import intencional)
from env import (  # (ambiente + geometria do vento + faixa válida do alvo)
    ALVO_TOL,
    ALVO_Z_MAX,
    ALVO_Z_MIN,
    HoverEnv,
    YAW_ALVO,
    atitude,
    azimute_graus,
    envolve_pi,
)

import numpy as np
from stable_baselines3 import PPO

TOPO = (16, 64, 64, 4)          # topologia esperada da MLP (a UI desenha-a uma vez, fixa)
OUT_PADRAO = _AQUI / "out" / "net.jsonl"
CONTROLO_PADRAO = _AQUI / "out" / "controle_vento.json"   # o MESMO default do painel «VENTO» do dashboard
PRECISAO = 5                    # casas decimais nas ativações (o ficheiro a 5 Hz fica pequeno e legível)
INTERVALO_MIN = 0.02            # s — piso do `--interval` (evita rajadas de milhares de linhas por segundo)


# --------------------------------------------------------------------------------------- hooks
class Sonda:
    """Forward hooks nos `nn.Linear` da política, por ordem de execução (última = cabeça de ação)."""

    def __init__(self, politica) -> None:
        self.saidas: dict[int, np.ndarray] = {}
        self._handles = []
        lineares = self._lineares(politica)
        if len(lineares) < 3:
            raise SystemExit(f"net_probe: a política só tem {len(lineares)} camadas Linear "
                             "(esperava 2 escondidas + a cabeça) — a UI desenha [16,64,64,4]")
        for i, camada in enumerate(lineares):
            self._handles.append(camada.register_forward_hook(self._hook(i)))

    @staticmethod
    def _lineares(politica) -> list:
        """Todos os `nn.Linear` na ordem política: primeiro `policy_net`, depois `action_net`."""
        if not hasattr(politica, "mlp_extractor") or not hasattr(politica.mlp_extractor, "policy_net"):
            raise SystemExit("net_probe: a política não tem `mlp_extractor.policy_net` — só se sonda MlpPolicy")
        modulos = [m for m in politica.mlp_extractor.policy_net.modules() if m.__class__.__name__ == "Linear"]
        modulos += [m for m in politica.action_net.modules() if m.__class__.__name__ == "Linear"]
        return modulos

    def _hook(self, i: int):
        def guardar(_modulo, _entrada, saida):
            self.saidas[i] = np.asarray(saida.detach().cpu().numpy()[0])   # 1.ª amostra do batch
        return guardar

    def ultima(self) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        """(h1, h2, act) da última passagem completa; `None` se ainda não houve forward."""
        if len(self.saidas) < 3 or 2 not in self.saidas:
            return None
        ordem = sorted(self.saidas)
        return self.saidas[ordem[0]], self.saidas[ordem[1]], self.saidas[ordem[-1]]

    def fechar(self) -> None:
        for h in self._handles:
            h.remove()
        self._handles.clear()


# --------------------------------------------------------------------------------------- vento ao vivo
def _numero_do_registo(dados: dict, campo: str, predefinido: float) -> float:
    """Campo numérico finito do ficheiro de controlo (ValueError descritivo se não o for)."""
    v = dados.get(campo, predefinido)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
        raise ValueError(f"`{campo}` tem de ser um número finito (recebido {v!r})")
    return float(v)


def _ler_registo(dados) -> tuple[float, float, float, bool, int | None, bool | None]:
    """Ficheiro de controlo completo → (vel, azimute, elevação, ativo, reiniciar, loop).

    Levanta `ValueError` se o conteúdo não respeitar o contrato (não é objeto JSON, campo não numérico,
    `vel` negativa, `ativo`/`loop` não booleanos, `reiniciar` não inteiro ≥ 0) — quem chama avisa e mantém o
    vento anterior. Os defaults são os do contrato: `azimute`/`elevacao` ausentes valem 0° e `ativo` ausente
    vale `True` (vento ligado). `reiniciar`/`loop` são OPCIONAIS: ausentes valem `None` = «não mexe» (nem
    pedido de reinício, nem mudança de modo) — é o que faz um ficheiro escrito por uma versão antiga
    comportar-se como antes (sem-loop por omissão).

    Normalização (um ficheiro escrito à mão não passa pelas faixas da UI, que só valem no `POST /api/vento`):
    o `azimute` é reduzido a [0, 360) e a `elevacao` é cortada a [−90, 90] — o mesmo que o `HoverEnv` faria
    com o azimute, mas explícito, para o `vento_azim` gravado no JSONL ser sempre o que a física aplicou.
    """
    if not isinstance(dados, dict):
        raise ValueError("o ficheiro não é um objeto JSON")  # noqa: TRY004  (conteúdo inválido, não um tipo errado)
    vel = _numero_do_registo(dados, "vel", 0.0)
    azimute = _numero_do_registo(dados, "azimute", 0.0) % 360.0
    elevacao = min(90.0, max(-90.0, _numero_do_registo(dados, "elevacao", 0.0)))
    if vel < 0.0:
        raise ValueError(f"`vel` tem de ser ≥ 0 m/s (recebido {vel!r})")
    ativo = dados.get("ativo", True)
    if isinstance(ativo, bool):
        pass
    elif isinstance(ativo, int) and ativo in (0, 1):        # tolera 0/1 escrito à mão
        ativo = bool(ativo)
    else:
        raise ValueError(f"`ativo` tem de ser booleano (recebido {ativo!r})")
    reiniciar = dados.get("reiniciar", None)
    if reiniciar is not None:
        if isinstance(reiniciar, bool) or not isinstance(reiniciar, int) or reiniciar < 0:
            raise ValueError(f"`reiniciar` tem de ser um inteiro ≥ 0 (recebido {reiniciar!r})")
        reiniciar = int(reiniciar)
    loop = dados.get("loop", None)
    if loop is not None:
        if isinstance(loop, bool):
            pass
        elif isinstance(loop, int) and loop in (0, 1):      # tolera 0/1 escrito à mão
            loop = bool(loop)
        else:
            raise ValueError(f"`loop` tem de ser booleano (recebido {loop!r})")
    return vel, azimute, elevacao, ativo, reiniciar, loop


def ler_registo_vento(dados) -> tuple[float, float, float, bool]:
    """`{vel, azimute, elevacao, ativo}` do ficheiro de controlo → (vel, azimute, elevação, ativo).

    Só o vento (contrato v2, inalterado); os campos de comando `reiniciar`/`loop` são validados na mesma
    leitura mas devolvidos por `ler_comandos_do_registo`.
    """
    vel, azimute, elevacao, ativo, _reiniciar, _loop = _ler_registo(dados)
    return vel, azimute, elevacao, ativo


def ler_comandos_do_registo(dados) -> tuple[int | None, bool | None]:
    """`(reiniciar, loop)` do ficheiro de controlo — `None` em cada campo ausente (não mexe em nada)."""
    _vel, _azimute, _elevacao, _ativo, reiniciar, loop = _ler_registo(dados)
    return reiniciar, loop


class ControloVento:
    """Vigia o ficheiro de controlo (mtime) e escreve o vento no ambiente quando ele MUDA.

    A verificação corre a CADA passo de decisão (N=1): o clique em «APLICAR/PARAR VENTO» no dashboard chega
    à física no passo seguinte (0,02 s de simulação). O ficheiro é escrito pelo dashboard de forma atómica
    (tmp + `os.replace`), logo o mtime muda sempre; usa-se `(mtime_ns, tamanho)` para não perder uma mudança.

    Além do vento, o mesmo ficheiro transporta os COMANDOS DE EPISÓDIO (opcionais):
      · `"reiniciar": <int>` — contador; quando MUDA, o episódio em curso é reiniciado (`env.reset`). O 1.º
        contador que se vê é linha de base (não reinicia), EXCETO se for ≥ 1 sem nunca ter havido ficheiro —
        nesse caso é um REINICIAR já pedido (a sonda podia estar em espera e não pode perdê-lo).
      · `"loop": <bool>` — `true` volta ao auto-reset no fim do episódio; `false` volta ao modo de espera.
    Campos ausentes = «não mexe» (é o que faz um ficheiro sem estes campos manter o modo em vigor).
    """

    def __init__(self, caminho, env: HoverEnv, inicial: tuple[float, float, float] | None = None) -> None:
        self.caminho = Path(caminho)
        self.env = env
        self.n_aplicacoes = 0
        self.n_reinicios = 0
        self.ultimo: dict | None = None
        self.loop: bool | None = None                     # modo pedido pelo ficheiro (None = não mexe)
        self.reiniciar: int | None = None                 # último contador visto (None = ainda nenhum)
        self.pedido_reinicio = False                      # há um REINICIAR por consumir
        self._assinatura: tuple[int, int] | None = None
        self._aviso = ""
        self._le_contador_inicial()
        if inicial is not None:
            self._aplica(*inicial, ativo=True, origem="--vento-inicial")

    def _le_contador_inicial(self) -> None:
        """Linha de base do contador: o que o ficheiro já tiver (sem aplicar vento nenhum)."""
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            reiniciar, loop = ler_comandos_do_registo(dados)
        except (OSError, ValueError):
            return                                        # sem ficheiro (ou inválido): linha de base fica None
        self.reiniciar = reiniciar
        self.loop = loop

    def _assinatura_do_ficheiro(self) -> tuple[int, int] | None:
        """(mtime_ns, tamanho) do ficheiro — `None` se ainda não existe (ou desapareceu)."""
        try:
            st = self.caminho.stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def verifica(self) -> bool:
        """Um passo de decisão: `True` se o vento foi (re)aplicado agora.

        Os comandos (`reiniciar`/`loop`) são lidos na mesma passagem e ficam em `self.reiniciar`/`self.loop`;
        um contador novo levanta `self.pedido_reinicio` (consumido com `consumir_reinicio()`).
        """
        assinatura = self._assinatura_do_ficheiro()
        if assinatura == self._assinatura:
            return False
        self._assinatura = assinatura                    # marca já: um ficheiro inválido não é relido sempre
        if assinatura is None:
            return False                                 # sem ficheiro: mantém o vento em vigor
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            vel, azimute, elevacao, ativo, reiniciar, loop = _ler_registo(dados)
        except (OSError, ValueError) as erro:
            self._avisa(f"controlo de vento ignorado ({erro}) — mantenho o vento anterior")
            return False
        self._actualiza_comandos(reiniciar, loop)
        return self._aplica(vel, azimute, elevacao, ativo=ativo, origem=self.caminho.name)

    def _actualiza_comandos(self, reiniciar: int | None, loop: bool | None) -> None:
        """Aplica a regra do contador (1.º visto = linha de base; ≥ 1 sem ficheiro prévio = REINICIAR)."""
        if loop is not None:
            self.loop = bool(loop)
        if reiniciar is None:
            return
        if self.reiniciar is None:
            if reiniciar > 0:                             # ficheiro nasceu já com um REINICIAR pedido
                self.pedido_reinicio = True
                print(f"net_probe: REINICIAR pedido (contador {reiniciar}, sem linha de base)", flush=True)
        elif reiniciar != self.reiniciar:
            self.pedido_reinicio = True
            print(f"net_probe: REINICIAR pedido (contador {self.reiniciar} → {reiniciar})", flush=True)
        self.reiniciar = int(reiniciar)

    def consumir_reinicio(self) -> bool:
        """`True` uma única vez por cada REINICIAR pedido (o pedido é limpo ao consumir)."""
        if not self.pedido_reinicio:
            return False
        self.pedido_reinicio = False
        self.n_reinicios += 1
        return True

    def _aplica(self, vel: float, azimute: float, elevacao: float, ativo: bool = True, origem: str = "") -> bool:
        """`ativo` → `definir_vento(vel, azimute, elevação)`; inativo → `definir_vento(0, 0, 0)` (parado)."""
        if ativo:
            vento = self.env.definir_vento(float(vel), float(azimute), float(elevacao))
        else:
            vento = self.env.definir_vento(0.0, 0.0, 0.0)
        self.n_aplicacoes += 1
        self.ultimo = {"vel": float(vel), "azimute": float(azimute), "elevacao": float(elevacao),
                       "ativo": bool(ativo)}
        if ativo:
            print(f"net_probe: vento APLICADO {float(vel):.2f} m/s · azimute {float(azimute):.1f}° · "
                  f"elevação {float(elevacao):.1f}° → opt.wind={np.round(vento, 4).tolist()} ({origem})",
                  flush=True)
        else:
            print(f"net_probe: vento PARADO (ativo=false) → opt.wind={np.round(vento, 4).tolist()} ({origem})",
                  flush=True)
        return True

    def _avisa(self, texto: str) -> None:
        """Aviso sem spam: só quando a mensagem muda (o ficheiro é verificado a cada passo)."""
        if texto != self._aviso:
            self._aviso = texto
            print(f"net_probe: {texto}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------------------- utilidades
def _arredondado(x, casas: int = PRECISAO) -> list[float]:
    """numpy → lista de floats JSON-safe (float32→float Python e arredondado; NaN/inf → 0.0)."""
    v = np.asarray(x, dtype=np.float64).ravel()
    v = np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
    return [float(a) for a in np.round(v, casas)]


def _topologia(obs, h1, h2, act) -> tuple[int, ...]:
    return (int(np.size(obs)), int(np.size(h1)), int(np.size(h2)), int(np.size(act)))


def _info_do_instante(env, info: dict) -> dict:
    """`info` do estado a que `obs` corresponde, com todas as chaves que a linha usa.

    O `step` do env devolve `{z, dist_xy, v, no_alvo, yaw_err, vento_vel, vento_azim}`; se faltar alguma
    (versões antigas do env), mede-se no MESMO instante a partir dos sensores (mesma fórmula do env, com o seu
    `ALVO_TOL`) — a linha nunca fica com pares desfasados nem com chaves em falta.
    O vento é medido SEMPRE agora (`env.vento_atual`): o ficheiro de controlo pode tê-lo mudado neste passo de
    decisão, e o `vento_vel`/`vento_azim` do `info` anterior ficariam uma linha atrasados em relação ao vento
    que a ação desta linha vai enfrentar.
    """
    medido = dict(info)
    if not {"z", "dist_xy", "no_alvo", "yaw_err"} <= set(medido):
        pos = np.asarray(env.data.sensor("posicao").data, dtype=float)   # estado consistente (mj_forward feito)
        z = float(medido.get("z", pos[2]))
        d = float(np.hypot(pos[0], pos[1]))
        yaw = float(atitude(env.data.sensor("body_quat").data)[2])
        medido.setdefault("z", z)
        medido.setdefault("dist_xy", d)
        medido.setdefault("yaw_err", envolve_pi(yaw - YAW_ALVO))
        medido.setdefault("no_alvo", bool(abs(z - float(env.alvo_z)) < ALVO_TOL and d < ALVO_TOL))
    vento = env.vento_atual
    medido["vento_vel"] = float(np.linalg.norm(vento))
    medido["vento_azim"] = float(azimute_graus(vento))
    return medido


# --------------------------------------------------------------------------------------- CLI
def _vento_inicial(texto: str) -> tuple[float, float, float]:
    """`--vento-inicial vel,azim[,elev]` → (vel, azimute, elevação); erro de argparse se for inválido.

    Normaliza como o `ler_registo_vento`: azimute em [0, 360), elevação cortada a [−90, 90].
    """
    partes = [p.strip() for p in str(texto).split(",")]
    if len(partes) not in (2, 3):
        raise argparse.ArgumentTypeError(f"usa `vel,azim` ou `vel,azim,elev` (recebido {texto!r}; ex.: 5,90)")
    try:
        valores = [float(p) for p in partes]
    except ValueError:
        raise argparse.ArgumentTypeError(f"valores não numéricos em {texto!r} (ex.: 5,90)") from None
    if any(not math.isfinite(v) for v in valores):
        raise argparse.ArgumentTypeError("os valores de `--vento-inicial` têm de ser finitos")
    vel, azimute = valores[0], valores[1]
    if vel < 0.0:
        raise argparse.ArgumentTypeError(f"`vel` tem de ser ≥ 0 m/s (recebido {vel:g})")
    return vel, azimute % 360.0, min(90.0, max(-90.0, valores[2] if len(valores) == 3 else 0.0))


def _alvo_z(texto: str) -> float:
    """`--alvo-z` → float finito na faixa VÁLIDA do alvo do `HoverEnv` (erro de argparse = exit 2, sem traceback).

    O `HoverEnv` recusa `alvo_z` fora de [ALVO_Z_MIN, ALVO_Z_MAX] com `ValueError`; sem esta validação o
    `--alvo-z 3.5` morria lá dentro com traceback em vez de explicar o que está errado.
    """
    try:
        valor = float(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"`--alvo-z` tem de ser um número em metros (recebido {texto!r})") from None
    if not math.isfinite(valor):
        raise argparse.ArgumentTypeError(f"`--alvo-z` tem de ser finito (recebido {texto!r})")
    if not ALVO_Z_MIN <= valor <= ALVO_Z_MAX:
        raise argparse.ArgumentTypeError(
            f"`--alvo-z` tem de estar em [{ALVO_Z_MIN:g}, {ALVO_Z_MAX:g}] m (recebido {valor:g}): abaixo de "
            f"{ALVO_Z_MIN:g} m o bónus do alvo sairia de graça e acima de {ALVO_Z_MAX:g} m o alvo colaria ao "
            "teto de terminação do episódio"
        )
    return valor


def _fator_de_tempo(texto: str) -> float:
    """`--fator-tempo` → float finito ≥ 0 (0 = sem travão); erro de argparse se não o for."""
    try:
        valor = float(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"`--fator-tempo` tem de ser um número (recebido {texto!r})") from None
    if not math.isfinite(valor) or valor < 0.0:
        raise argparse.ArgumentTypeError(f"`--fator-tempo` tem de ser ≥ 0 (recebido {texto!r}; 0 = sem travão)")
    return valor


def argumentos(argv=None):
    p = argparse.ArgumentParser(
        description="Sonda a política PPO do hover: obs/ações + ativações das camadas Linear em JSONL, "
                    "com vento controlado ao vivo pelo ficheiro de controlo do dashboard.",
        epilog="Ctrl+C fecha o ficheiro e sai (SIGTERM também é tratado: o dashboard usa-o para parar).")
    p.add_argument("--model", required=True, help="caminho do .zip do PPO (ex.: best_model.zip)")
    p.add_argument("--out", default=str(OUT_PADRAO),
                   help=f"ficheiro JSONL de saída (default: {OUT_PADRAO}; é TRUNCADO ao arrancar)")
    p.add_argument("--interval", type=float, default=0.2,
                   help=f"segundos entre linhas (default: 0.2 = 5 Hz; clampado a ≥ {INTERVALO_MIN:g} s)")
    p.add_argument("--controlo", default=str(CONTROLO_PADRAO),
                   help="ficheiro JSON de controlo de vento (vel/azimute/elevacao/ativo) vigiado a CADA passo "
                        f"de decisão (default: {CONTROLO_PADRAO})")
    p.add_argument("--vento-inicial", type=_vento_inicial, default=None, metavar="VEL,AZIM[,ELEV]",
                   help="vento aplicado antes do 1.º passo (ex.: 5,90 = 5 m/s para +y; 3,0,15 = com elevação)")
    p.add_argument("--fator-tempo", type=_fator_de_tempo, default=0.0, metavar="F",
                   help="ritmo da simulação: 1 = TEMPO REAL (vê-se o drone a reagir e a corrigir), 2 = a dobro, "
                        "0 = o mais rápido possível (default; é o que enche o JSONL depressa nos testes)")
    p.add_argument("--alvo-z", type=_alvo_z, default=1.0,
                   help=f"altura-alvo do HoverEnv em m, dentro da faixa válida [{ALVO_Z_MIN:g}, {ALVO_Z_MAX:g}] "
                        "(default: 1.0)")
    p.add_argument("--max-segundos", type=float, default=0.0,
                   help="sai sozinho ao fim de N s (0 = infinito; útil em testes)")
    p.add_argument("--seed", type=int, default=0, help="seed do reset do ambiente (default: 0)")
    p.add_argument("--loop", dest="loop", action="store_true",
                   help="auto-reset no fim do episódio (comportamento antigo): a sonda nunca espera")
    p.add_argument("--sem-loop", dest="loop", action="store_false",
                   help="DEFAULT: no fim do episódio a sonda PARA (a física não avança), escreve a linha de "
                        "evento e fica em espera; retoma quando o contador `reiniciar` do ficheiro de controlo "
                        "mudar (botão «↻ REINICIAR» do painel) ou quando o campo `loop` passar a true")
    p.set_defaults(loop=False)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = argumentos(argv)
    modelo = Path(args.model).expanduser()
    if not modelo.is_file():
        print(f"net_probe: modelo não encontrado: {modelo}", file=sys.stderr)
        return 2
    intervalo = float(args.interval)
    if not math.isfinite(intervalo) or intervalo < INTERVALO_MIN:
        print(f"net_probe: --interval {args.interval:g} fora da faixa útil — a usar {INTERVALO_MIN:g} s "
              "(mínimo: evita rajadas de linhas; o teto prático é a velocidade da física)",
              file=sys.stderr, flush=True)
        intervalo = INTERVALO_MIN
    saida = Path(args.out).expanduser()
    saida.parent.mkdir(parents=True, exist_ok=True)
    controlo_caminho = Path(args.controlo).expanduser()

    parar = {"pedido": False}

    def _pedido(_sinal, _frame):
        parar["pedido"] = True

    signal.signal(signal.SIGINT, _pedido)
    signal.signal(signal.SIGTERM, _pedido)

    env = HoverEnv(alvo_z=float(args.alvo_z))
    try:
        agente = PPO.load(str(modelo), device="cpu")
        agente.policy.set_training_mode(False)
        sonda = Sonda(agente.policy)
        controlo = ControloVento(controlo_caminho, env, inicial=args.vento_inicial)
    except SystemExit:
        env.close()
        raise
    except Exception as erro:                     # noqa: BLE001  (erro de carga relatado e devolvido no exit code)
        env.close()
        print(f"net_probe: falhou a carregar a política de {modelo}: {erro}", file=sys.stderr)
        return 3

    obs, info = env.reset(seed=int(args.seed))
    fator = float(args.fator_tempo)
    print(f"net_probe: modelo={modelo} obs={np.size(obs)} out={saida} interval={intervalo:g}s", flush=True)
    print(f"net_probe: controlo de vento {controlo_caminho} "
          f"({'existe' if controlo_caminho.is_file() else 'ainda não existe — à espera do painel VENTO'})"
          f" · vento ativo = {np.round(env.vento_atual, 4).tolist()} m/s", flush=True)
    print(f"net_probe: ritmo {'o mais rápido possível (sem travão)' if fator <= 0 else f'{fator:g}× o tempo real'} "
          f"· passo de decisão {env.dt_decisao:g} s", flush=True)
    print(f"net_probe: episódios em {'LOOP (auto-reset no fim)' if args.loop else 'SEM LOOP (para no fim e espera pelo «↻ REINICIAR»)'}",
          flush=True)

    t0 = time.monotonic()
    ultimo = -intervalo                            # a 1.ª linha sai logo no 1.º passo
    n_linhas = 0
    n_passos = 0
    n_episodios = 0
    modo_loop = bool(args.loop)                     # default: SEM loop (espera pelo REINICIAR no fim)
    em_espera = False
    motivo_espera = ""
    topo_vista: tuple[int, ...] | None = None

    def _linha(obs_entrada, info_entrada, h1, h2, act, agora: float, **extra) -> dict:
        """Linha do JSONL: o par obs/h1/h2/act do MESMO forward + medições do mesmo instante."""
        return {"t": round(agora, 4), "obs": _arredondado(obs_entrada), "h1": _arredondado(h1),
                "h2": _arredondado(h2), "act": _arredondado(act),
                "z": round(float(info_entrada["z"]), 5),
                "dist_xy": round(float(info_entrada["dist_xy"]), 5),
                "no_alvo": bool(info_entrada["no_alvo"]),
                "yaw_err": round(float(info_entrada["yaw_err"]), 5),
                "vento_vel": round(float(info_entrada["vento_vel"]), 5),
                "vento_azim": round(float(info_entrada["vento_azim"]), 5), **extra}

    def _novo_episodio(motivo: str) -> None:
        """`env.reset` com uma seed derivada do que já correu (episódios diferentes, run reprodutível).

        Rebase do travão (`--fator-tempo`): o ritmo conta a partir do INÍCIO DESTE episódio. Sem isto, o tempo
        de SIMULAÇÃO acumulado (n_passos·dt) ficava atrás do relógio de parede durante a espera e o travão
        nunca mais dormia — o episódio reiniciado corria à velocidade máxima e passava num piscar de olhos.
        """
        nonlocal obs, info, em_espera, motivo_espera, ultimo, n_episodios, base_passos, base_tempo
        obs, info = env.reset(seed=int(args.seed) + n_linhas)
        n_episodios += 1
        em_espera, motivo_espera = False, ""
        ultimo = time.monotonic() - t0 - intervalo   # a 1.ª linha do episódio novo sai já
        base_passos, base_tempo = n_passos, time.monotonic()
        print(f"net_probe: episódio {n_episodios} a começar ({motivo})", flush=True)
    base_passos, base_tempo = 0, t0

    try:
        with open(saida, "w", encoding="utf-8") as f:
            while not parar["pedido"]:
                controlo.verifica()                # vento + comandos: ficheiro de controlo, a CADA passo (N=1)
                if controlo.loop is not None:      # o toggle «LOOP» da UI manda já (não espera pelo fim)
                    modo_loop = bool(controlo.loop)
                pedido_reinicio = controlo.consumir_reinicio()

                if em_espera:
                    # SEM LOOP e episódio terminado: a física NÃO avança (o JSONL fica como está, com a linha
                    # de evento no fim). Sai da espera com REINICIAR (contador novo) ou com o modo LOOP ligado.
                    if pedido_reinicio or modo_loop:
                        _novo_episodio("REINICIAR" if pedido_reinicio else "loop ligado")
                    else:
                        if args.max_segundos > 0 and (time.monotonic() - t0) >= float(args.max_segundos):
                            break
                        time.sleep(0.05)           # curto: o SIGTERM e o clique chegam depressa
                        continue
                elif pedido_reinicio:              # REINICIAR a meio do episódio: corta e recomeça
                    _novo_episodio("REINICIAR")

                # Instantâneo do MESMO estado: a obs que vai ENTRAR no forward e o `info` que lhe corresponde.
                # É este par que a linha grava, para `h1`/`h2`/`act` ficarem alinhados com `obs`/`z`/`dist_xy`.
                obs_entrada = np.array(obs, dtype=np.float32, copy=True)
                info_entrada = _info_do_instante(env, info)
                acao, _estado = agente.predict(obs_entrada, deterministic=True)  # o forward enche os hooks
                obs, _r, terminado, truncado, info = env.step(acao)
                n_passos += 1
                agora = time.monotonic() - t0
                if agora - ultimo >= intervalo:
                    ultimo = agora
                    captura = sonda.ultima()
                    if captura is not None:
                        h1, h2, act = captura
                        topo = _topologia(obs_entrada, h1, h2, act)
                        if topo != topo_vista:
                            topo_vista = topo
                            if topo != TOPO:
                                print(f"net_probe: aviso — topologia vista {topo} ≠ {TOPO}",
                                      file=sys.stderr, flush=True)
                        f.write(json.dumps(_linha(obs_entrada, info_entrada, h1, h2, act, agora),
                                           separators=(",", ":")) + "\n")
                        f.flush()
                        n_linhas += 1
                        if n_linhas % 25 == 0:
                            print(f"net_probe: {n_linhas} linhas · t={agora:.1f}s · "
                                  f"z={info_entrada['z']:.3f} m · dist_xy={info_entrada['dist_xy']:.3f} m · "
                                  f"vento={info_entrada['vento_vel']:.2f} m/s @ {info_entrada['vento_azim']:.0f}°",
                                  flush=True)
                if terminado or truncado:
                    # LINHA DE EVENTO: mesmo par obs→h1/h2/act (um forward no estado final) para o alinhamento
                    # da rede continuar válido, mais o evento e a razão do fim do episódio.
                    motivo = "terminado" if terminado else "truncado"
                    obs_final = np.array(obs, dtype=np.float32, copy=True)
                    info_final = _info_do_instante(env, info)
                    agente.predict(obs_final, deterministic=True)
                    captura = sonda.ultima()
                    h1, h2, act = captura if captura is not None else (obs_final, obs_final, obs_final)
                    f.write(json.dumps(_linha(obs_final, info_final, h1, h2, act, time.monotonic() - t0,
                                              evento="fim_episodio", motivo=motivo, episodio=n_episodios + 1),
                                       separators=(",", ":")) + "\n")
                    f.flush()
                    n_linhas += 1
                    if modo_loop:
                        _novo_episodio(f"loop, {motivo}")
                    else:
                        em_espera, motivo_espera = True, motivo
                        print(f"net_probe: EPISÓDIO TERMINADO ({motivo}) — em espera; clica «↻ REINICIAR» "
                              "no painel (ou liga «LOOP») para continuar", flush=True)
                if fator > 0.0:                # travão opcional: tempo de SIMULAÇÃO a F× o tempo de parede
                    atraso = ((n_passos - base_passos) * env.dt_decisao / fator
                              - (time.monotonic() - base_tempo))
                    if atraso > 0.0:
                        time.sleep(min(atraso, 0.05))   # curto: o SIGTERM não fica preso num sono longo
                if args.max_segundos > 0 and (time.monotonic() - t0) >= float(args.max_segundos):
                    break
    finally:
        sonda.fechar()
        env.close()
    print(f"net_probe: fim — {n_linhas} linhas em {time.monotonic() - t0:.1f}s → {saida} · "
          f"episódios={n_episodios} · reinícios={controlo.n_reinicios} · "
          f"aplicações de vento={controlo.n_aplicacoes}"
          f"{' · EM ESPERA (' + motivo_espera + ')' if em_espera else ''}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
