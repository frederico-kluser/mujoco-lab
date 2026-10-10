"""experiments/09_drone_hover_rl/train.py — treino PPO headless do "drone trava-se em (0, 0, 1) m com a
orientação fixa (yaw = 0), mesmo com vento" — contrato v2 do `env.HoverEnv`.

Ambiente: `env.HoverEnv` (Crazyflie 2 do menagerie; física 500 Hz, decisão 50 Hz, obs (16,) JÁ normalizada,
ação Box(-1,1)⁴ centrada no hover, RECOMPENSA v2 — com guinada e suavidade da ação —, vento REAL escrito em
`model.opt.wind`, episódio 10 s). Esta peça é só TREINO: não toca no env, não cria `mujoco.Renderer`/viewer,
não abre browser e não precisa de TensorBoard.

    uv run --group hover-rl python experiments/09_drone_hover_rl/train.py --timesteps 500000 --seed 0
    uv run --group hover-rl python experiments/09_drone_hover_rl/train.py --sem-painel --timesteps 5000
    uv run --group hover-rl python experiments/09_drone_hover_rl/train.py --sem-curriculo --vento-max 2
    uv run --group hover-rl python experiments/09_drone_hover_rl/train.py --vento-dinamico rajadas \
        --vento-dinamico-params '{"p": 0.02, "duracao": 10}'      # vento que muda a meio do voo
    uv run --group hover-rl python experiments/09_drone_hover_rl/train.py --vento-dinamico aleatoria \
        --vento-dinamico-params '{"p": 0.02, "duracao": 10}'      # rajadas de direção E força ao acaso
    uv run --group hover-rl python experiments/09_drone_hover_rl/train.py --vento-dinamico frente \
        --vento-dinamico-params '{"t_s": 2.0}' --sem-curriculo --vento-max 3
    uv run --group hover-rl python experiments/09_drone_hover_rl/train.py --retomar out/runs/seed2/best_model.zip \
        --timesteps 200000 --out-dir out/runs/seed2_yaw   # fine-tune a partir da política v1

VENTO EM CURRÍCULO DE DR (domain randomization; CoALA #7978/#7979 — "currículo 0→1→2→3 m/s, sobe quando
SR ≳ 80 %"). Os envs de TREINO nascem com `vento_aleatorio=(0, u_atual)` — vento POR EPISÓDIO (norma
U ~ U[0, u_atual] m/s, azimute U[0, 2π), elevação ±20°), reamostrado a cada reset. `--curriculo-vento`
(default `0,1,2,3`) dá os TETOS dos estágios; o teto sobe UM estágio por avaliação quando o `frac_xy_z`
medido nessa avaliação é ≥ `--avanco-frac` (default 0,5). A guarda "no máximo 1 estágio por avaliação" é
ESTRUTURAL: `avaliar()` é chamado uma vez por avaliação e sobe no máximo um degrau (com 4 estágios, uma
avaliação com 100 % no alvo leva a 0→1, nunca 0→3). O teto novo entra em todos os envs de treino com
`venv.env_method("definir_vento_aleatorio", 0.0, u_novo)` — funciona em `SubprocVecEnv` e atravessa o
`Monitor`. ATENÇÃO ao comportamento REAL do env: essa chamada AMOSTRA JÁ um vento do regime novo, logo os
episódios em curso sentem o teto novo IMEDIATAMENTE (não esperam pelo reset — medido: passo de decisão 4,
sem reset, vento 0,00 → 3,03 m/s ao subir o teto para 5, e o vetor amostrado devolvido é o que fica em
`opt.wind`); os resets seguintes é que reamostram dentro do teto. Por isso uma subida de estágio pode
aparecer a meio de um episódio. `--sem-curriculo` desliga tudo isto: teto FIXO `--vento-max` (default
3,0 m/s; intervalo [0, 10]; é IGNORADO quando o currículo está ligado — nesse caso avisa).

VENTO DINÂMICO (`--vento-dinamico rajadas|aleatoria|frente|dryden` + `--vento-dinamico-params '<json>'`, por
omissão DESLIGADO → nada muda): o treino anterior só tinha vento CONSTANTE por episódio (o currículo
`U ~ U[0, u]` reamostrado no reset) — faltava robustez a vento que MUDA a meio do voo
(frente/rajada/turbulência). Com a flag, só os envs de TREINO recebem `vento_dinamico=<config>` (o
`env.HoverEnv` valida a config com `valida_vento_dinamico`; modos, fórmulas e defaults completos no docstring
do `env.py`):
  · `rajadas` — a cada passo de decisão, com prob. `p` começa uma rajada `u ~ U[0, u_max]` (azimute aleatório,
    elevação ±20°) com envelope `sin(π·k/(N+1))` durante `duracao` passos, SOMADA ao vento base
    (ex.: `'{"p": 0.02, "duracao": 10}'`);
  · `aleatoria` — direção E força re-sorteadas a CADA rajada dentro das faixas DISPONÍVEIS POR INTEIRO
    (`u ~ U[0, 5]` m/s, azimute U[0, 360°) e elevação U[−90°, +90°]), com o mesmo `p`/`duracao` e o mesmo
    envelope `sin(π·k/(N+1))` de `rajadas`, mas aplicadas como MISTURA vectorial
    `w(k) = base + sin(π·k/(N+1))·(rajada − base)`: no pico o vento É a rajada sorteada e nas pontas fica
    junto do vento base (sem saltos; ‖w‖ ≤ max(‖base‖, 5) m/s). Só `p`/`duracao`
    contam: `u_max`/`sigma`/`L`/`v_min` são aceites e validados mas IGNORADOS (a amplitude não segue o teto do
    currículo — a não ser `u_max = 0`, que continua a ser modo INERTE, como em todos os modos);
  · `frente` — "wind front": a `t_s` segundos do episódio o vento muda em DEGRAU para `u ~ U[0,5; u_max]`
    (azimute aleatório), substituindo o vento base até ao fim (ex.: `'{"t_s": 2.0}'`) — é a frente de vento
    apanhada em voo, o cenário que o dono pediu ("aguenta uma frente de vento e sobe estabilizado");
  · `dryden` — turbulência OU de 1.ª ordem por passo sobre o vento base (ex.: `'{"sigma": 0.5, "L": 10.0}'`,
    `α = exp(−Δt·V/L)` com `Δt` = 0,02 s e `V = max(‖base‖, v_min)`).
REGRA DO TETO (uma só, sem ambiguidade): o `u_max` do modo dinâmico é SEMPRE o teto do CURRÍCULO em vigor
(o teto do estágio atual do `--curriculo-vento`, ou o `--vento-max` fixo com `--sem-curriculo`) e SOBE com o
estágio, porque é esse o vento que a política está a aprender a aguentar. Por isso `u_max` NÃO se põe no
`--vento-dinamico-params` (erro de argparse se vier): há uma única fonte de verdade para o teto do vento —
EXCEÇÃO: no modo `aleatoria` o `u_max` não limita a amplitude (o teto do modo é sempre 5 m/s), mas o teto do
currículo continua a valer para o VENTO BASE e o `u_max = 0` continua a deixar o modo inerte. Num
estágio de teto 0 m/s (o 1.º estágio do currículo padrão) o vento dinâmico fica INERTE (`u_max = 0` = ar
parado); a frente usa o piso de 0,5 m/s só quando o teto o permite (com teto < 0,5 vale o teto). Para ter
vento dinâmico desde o 1.º passo de decisão dê um currículo de teto não nulo desde o início:
`--curriculo-vento 3` (um só estágio) ou `--sem-curriculo --vento-max 3`. O JSON serve
para os parâmetros de cada modo (`p`, `duracao`, `t_s`, `sigma`, `L`, `v_min`); o que faltar fica com o
default do `env.py`. Ligar o vento dinâmico consome o `np_random` do env (sorteio das rajadas/frente/
turbulência), logo o stream dos estados iniciais muda em relação a um run SEM a flag — a reprodutibilidade
dada a seed mantém-se, mas os runs com e sem vento dinâmico não são comparáveis passo a passo. A AVALIAÇÃO e os ROLLOUTS DE MÉTRICAS continuam SEM VENTO (nem base nem dinâmico): a
régua de progresso e o `best_model` têm de continuar comparáveis entre estágios. O `u_vento` do JSONL é o teto
do currículo em vigor (13 campos, sem alterações). O arranque continua POUSADO e físico: o vento (base +
dinâmico) já atua no 1.º passo de decisão, logo a política aprende a levantar contra ele (ver `env.py`).

CRITÉRIO DE AVANÇO = `frac_xy_z` (fração de passos com ‖xy‖ < 0,05 m E |z − alvo| < 0,05 m), SEM guinada.
Foi mudado na ronda 3: com o critério antigo (`frac_no_alvo`, o bónus COMPLETO com yaw) a grelha ficava
inatingível — uma política que paira bem mas tem yaw mau mede ~0,10 e o DR de vento NUNCA ligava
(`u_vento = 0` até ao fim). O `frac_no_alvo` continua no JSONL (o dashboard usa-o) e agora age como
sinal de qualidade de guinada; o yaw fica para o fine-tune (`--retomar`).

A AVALIAÇÃO (`EvalCallback`) e os ROLLOUTS DE MÉTRICAS correm num `HoverEnv` SEM VENTO, semeados
(`seed+1000` no eval, `seed+10000` nas métricas) e determinísticos: a régua de progresso tem de ser
comparável entre estágios (com vento a subir por desenho, o retorno médio cairia só por causa do currículo)
e o critério de avanço mede "domina a tarefa" — o vento é dificuldade de TREINO, não da régua.
DECISÃO DE DESENHO (assumida, não é bug): como o critério (`frac_xy_z` ≥ `--avanco-frac`) é medido SEM vento
E SEM yaw, um estágio pode subir sem que a política domine o vento do estágio ATUAL nem a guinada. É
intencional — primeiro aprende-se a posição (xy, z), depois alarga-se a dificuldade, e o yaw fica para o
fine-tune; a robustez ao vento não é certificada por esta régua e mede-se à parte, com o teto fixo do
estágio (grelha 0/2/4/6/8/10 m/s, CoALA #7979), nunca com este `frac_xy_z`.

RETOMAR DE UM CHECKPOINT (`--retomar <best_model.zip|final.zip>`): `PPO.load` + `learn` — a política
CONTINUA a aprender em vez de começar de zero (é o caminho para o fine-tune das políticas v1, que pairam
500/500 e só falham yaw). Semântica REAL do SB3 2.9.0, medida nesta máquina com o `best_model.zip` do
seed2 (780 000 passos): os PESOS e o ESTADO DO ADAM são restaurados (a ação determinística é bit-a-bit a do
zip; o otimizador traz 13 tensores de momento) e `num_timesteps` volta com o valor guardado. NÃO é uma
continuação bit-a-bit: o ROLLOUT BUFFER não é guardado (é recriado a cada `learn`) e os `policy_kwargs`
(arquitetura, `log_std_init`) vêm OBRIGATORIAMENTE do checkpoint — o SB3 recusa `policy_kwargs` diferentes
dos guardados ("The specified policy kwargs do not equal the stored policy kwargs"), o que é correto (os
pesos só encaixam na mesma arquitetura). Pior: o `set_parameters` do load REPÕE o `lr` do checkpoint no
otimizador (medido: 3e-4, apesar de `learning_rate=1e-4` no load), pelo que esta peça FORÇA depois do load
o `--lr` e o L2 (`weight_decay`) do CLI nos `param_groups`. Com `--retomar`, `--timesteps` é o orçamento
ADICIONAL deste run: o `learn` recebe só `--timesteps` e a soma dos passos antigos é feita pelo SB3
(`_setup_learn` com `reset_num_timesteps=False` faz `total_timesteps += num_timesteps`) — com o DEFAULT
`reset_num_timesteps=True` o SB3 punha `num_timesteps = 0` e um total já somado por nós retreinava tudo de
zero (medido: 784 000 passos em vez de 4 000). O `fps`/
`elapsed_s` do JSONL contam só os passos DESTE run (o `t` continua a ser o cumulativo, para a curva do
dashboard seguir na mesma linha do tempo). O `--out-dir` deve ser NOVO: o run retomado escreve por cima
(não há cópia de segurança do original — o JSONL é truncado no início de cada run).

Receita (SB3 2.9.0 em CPU, `MlpPolicy` MLP [64, 64] tanh). Os DEFAULT desta peça são os que o smoke do I1-w
mostrou necessários com a recompensa v2 (os defaults do SB3 mal aprendem aqui): `--lr 1e-4`,
`--ent-coef 0,001`, `--log-std-init −0,5` (σ inicial ≈ 0,61; o 0,0 do SB3 explora demasiado numa ação de
4 canais com bónus estreito) · `n_steps 512` × `n_envs 8` = 4 096 passos por rollout (≈ 16× o batch) ·
`batch_size 256` · `n_epochs 10` · `gamma 0,99` · `gae_lambda 0,95` · `clip_range 0,2` · `vf_coef 0,5` ·
`max_grad_norm 0,5` · **L2** `weight_decay 1e-4` pelo `policy_kwargs["optimizer_kwargs"]` (aceite pelo SB3
2.9.0: `ActorCriticPolicy._build` faz `optimizer_class(self.parameters(), lr, **optimizer_kwargs)` — com o
Adam por omissão, `weight_decay` é exatamente o L2; o valor EFETIVO é impresso no início do treino; num
`--retomar` é forçado no otimizador depois do load) · `n_envs` cópias em `SubprocVecEnv` com `Monitor` por
env · `torch.set_num_threads(1)` (MLP minúscula com batch pequeno: o intra-op do torch só traz overhead —
medido nesta máquina, +15 % de débito com n_envs=4) · **SEM VecNormalize** (a obs já sai normalizada do env
→ o grafo ONNX do deploy fica puro; não adicionar).

Saída (tudo em `--out-dir`, por omissão `experiments/09_drone_hover_rl/out/runs/seed<seed>`):

    evaluations.npz   EvalCallback: 10 episódios determinísticos no HoverEnv ÚNICO sem vento (não vetorizado)
    best_model.zip    melhor retorno médio de avaliação (poupa já na 1.ª avaliação)
    final.zip         fim do treino
    ckpt/*.zip        CheckpointCallback a cada 100k passos de ambiente + 1 garantido no fim
    train_log.jsonl   UMA linha por avaliação, 13 campos (os 12 de sempre + `frac_xy_z`): t, mean_ret,
                      std_ret, mean_z, mean_dist_xy, frac_no_alvo, mean_yaw_err, frac_alvo_total,
                      frac_xy_z, u_vento, fps, elapsed_s, seed
                      (`frac_xy_z` = fração de passos com xy E z no alvo, SEM yaw — é o critério de avanço
                      do currículo; `frac_no_alvo` e `frac_alvo_total` = bónus COMPLETO xy+z+yaw, iguais
                      entre si no contrato v2 do env; `mean_yaw_err` = média de |yaw_err| em rad, alvo 0;
                      `u_vento` = teto de vento EM VIGOR a partir desta avaliação — já com o avanço)

Contagem (armadilha do SB3): `EvalCallback`/`CheckpointCallback` contam CHAMADAS do callback, e cada chamada
é UM passo do VEC (`n_calls = num_timesteps / n_envs`) — não um passo de ambiente. `--eval-freq` está em
passos do vec e é reduzido automaticamente em treinos curtos para garantir ≥4 avaliações (≥4 linhas no
`train_log.jsonl`), sem alterar a cadência pedida nos treinos longos.

Reprodutibilidade: `--seed` fixa o PPO, as `n_envs` cópias do env (`seed+i`), o env de AVALIAÇÃO (`seed+1 000`)
e o env das métricas (`seed+10 000`) → a mesma seed do CLI dá o mesmo `evaluations.npz` e a mesma telemetria
de avaliação (avanços de currículo incluídos, porque dependem só da política; só `fps`/`elapsed_s` do JSONL
variam, por serem wall-clock). `--timesteps`, `--n-envs` são inteiros ≥ 1, `--vento-max` está em [0, 10],
`--avanco-frac` em [0, 1] e `--curriculo-vento` é uma lista de tetos em [0, 10] ESTRITAMENTE crescente:
valores inválidos dão erro de argparse com `exit 2` (nunca um traceback do SubprocVecEnv).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import warnings
from collections.abc import Callable, Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
_PASTA = Path(__file__).resolve().parent
for _caminho in (str(_PASTA), str(_RAIZ)):          # `from env import HoverEnv` + `lab/`
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import numpy as np
import torch
from env import (  # ANTES de mujoco/gymnasium: lab.mjkit fixa MUJOCO_GL
    BONUS_XY,
    BONUS_YAW,
    BONUS_Z,
    HoverEnv,
    valida_vento_dinamico,
)
from env_real import DR as FAIXAS_DR
from env_real import MODOS_ACAO, OBS_ATOR_DIM, DroneRealEnv
from politica import PoliticaAssimetrica
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import (
    BaseCallback,
    CheckpointCallback,
    EvalCallback,
    StopTrainingOnRewardThreshold,
)
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv
from torch import nn

# ----------------------------------------------------------------------------------------------- constantes
PASTA_RUNS = Path("experiments/09_drone_hover_rl/out/runs")
ARQUIVO_LOG = "train_log.jsonl"
N_EVAL_EPISODES = 10        # episódios do EvalCallback (retorno médio)
N_EPISODIOS_METRICAS = 3    # rollouts determinísticos PRÓPRIOS (z / dist_xy / yaw_err / no_alvo)
CHECKPOINT_PASSOS = 100_000  # passos de AMBIENTE entre checkpoints (÷ n_envs → passos do vec)
MIN_AVALIACOES = 4          # garante ≥4 linhas no train_log.jsonl mesmo em treinos curtos
MIN_PASSOS_VEC = 64         # piso da cadência AUTOMÁTICA de avaliação (evita spam em pedidos minúsculos)

# currículo de vento (CoALA #7978/#7979): tetos crescentes, sobe quando a fração de tempo no alvo é alta
CURRICULO_PADRAO = "0,1,2,3"  # tetos de vento (m/s) por estágio — o currículo 0→1→2→3 m/s do #7979
VENTO_MAX_PADRAO = 3.0      # m/s — teto FIXO do `--sem-curriculo` (e topo do currículo padrão)
VENTO_MAX_LIMITE = 10.0     # m/s — acima disto o CF2 real perde posição (#7979): valor irreal, não aceitar
FRAC_AVANCO = 0.5           # `frac_xy_z` (xy+z no alvo, SEM yaw) que faz subir um estágio (ronda 3)

# hiperparâmetros do PPO (evidência do smoke do I1-w: os defaults do SB3 mal aprendem com a recompensa v2)
N_STEPS = 512               # passos por env e por rollout: 512 × n_envs(=8) = 4 096 ≈ 16× o batch
BATCH_SIZE = 256            # tem de dividir n_steps × n_envs (512 ≥ 256 → divide qualquer n_envs ≥ 1)
N_EPOCHS = 10
GAMMA = 0.99
GAE_LAMBDA = 0.95
CLIP_RANGE = 0.2
VF_COEF = 0.5
MAX_GRAD_NORM = 0.5
PESO_L2 = 1e-4              # weight_decay do Adam (#7978: o regularizador que mais vezes ajuda em PPO)


# ----------------------------------------------------------------------------------------------- CLI
def _inteiro_positivo(texto: str) -> int:
    """Tipo do argparse: inteiro ≥ 1 → erro CLARO e `exit 2` (nunca um traceback do SubprocVecEnv)."""
    try:
        valor = int(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{texto!r} não é um inteiro") from None
    if valor < 1:
        raise argparse.ArgumentTypeError(f"tem de ser ≥ 1 (recebido {valor})")
    return valor


def _vento_max(texto: str) -> float:
    """Tipo do argparse: teto de vento em m/s dentro de [0, 10] (acima de 10 o CF2 real não mantém posição)."""
    try:
        valor = float(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{texto!r} não é um número") from None
    if not 0.0 <= valor <= VENTO_MAX_LIMITE:  # também apanha NaN (comparação falsa)
        raise argparse.ArgumentTypeError(
            f"tem de estar em [0, {VENTO_MAX_LIMITE:g}] m/s (recebido {valor:g})")
    return valor


def _curriculo_vento(texto: str) -> tuple[float, ...]:
    """Tipo do argparse: `"0,1,2,3"` → tetos de vento (m/s) ≥ 0, ESTRITAMENTE crescentes e ≤ 10."""
    partes = [p.strip() for p in str(texto).split(",") if p.strip()]
    if not partes:
        raise argparse.ArgumentTypeError("lista vazia: dê pelo menos um teto (ex.: `0,1,2,3`)")
    try:
        valores = tuple(float(p) for p in partes)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{texto!r} não é uma lista de números separados por vírgulas") from None
    if any(not u >= 0.0 for u in valores):  # `not >=` apanha NaN
        raise argparse.ArgumentTypeError(f"todos os tetos têm de ser ≥ 0 m/s (recebido {texto!r})")
    if any(u > VENTO_MAX_LIMITE for u in valores):
        raise argparse.ArgumentTypeError(
            f"nenhum teto pode passar {VENTO_MAX_LIMITE:g} m/s (recebido {texto!r}): acima disso o CF2 "
            "real não mantém posição — é o mesmo limite físico do `--vento-max`")
    if any(seguinte <= atual for atual, seguinte in pairwise(valores)):
        raise argparse.ArgumentTypeError(
            f"os tetos têm de ser estritamente crescentes (recebido {texto!r}): "
            "um estágio repetido não muda o regime de vento")
    return valores


def _frac_avanco(texto: str) -> float:
    """Tipo do argparse: fração de avanço do currículo, em [0, 1] (0 = sobe sempre; 1 = só com 100 %)."""
    try:
        valor = float(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{texto!r} não é um número") from None
    if not 0.0 <= valor <= 1.0:  # também apanha NaN
        raise argparse.ArgumentTypeError(f"tem de estar em [0, 1] (recebido {valor:g})")
    return valor


def _json_dict(texto: str) -> dict:
    """Tipo do argparse do `--vento-dinamico-params`: um OBJECT JSON → `dict` (erro claro se não for).

    A validação de fundo (chaves/modos/faixas) é a do `env.valida_vento_dinamico`, feita logo a seguir em
    `ler_args` para o erro sair como erro de argparse (`exit 2`), nunca como traceback no arranque dos envs.
    """
    try:
        valor = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise argparse.ArgumentTypeError(
            f"{texto!r} não é JSON válido ({erro.msg}, posição {erro.pos}) — ex.: '{{\"p\": 0.02}}'") from None
    if not isinstance(valor, dict):
        raise argparse.ArgumentTypeError(
            f"tem de ser um OBJECT JSON de parâmetros, ex.: '{{\"p\": 0.02, \"duracao\": 10}}' "
            f"(recebido {valor!r})")
    return valor


class _MarcaVentoMaxExplicito(argparse.Action):
    """Ação do `--vento-max`: guarda o valor E marca que veio do utilizador.

    Sem esta marca não se distingue "o utilizador pediu 3,0 m/s" do default 3,0 — e o aviso de que o
    `--vento-max` é ignorado quando o currículo está ligado só deve sair quando ele foi mesmo pedido.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        setattr(namespace, f"{self.dest}_explicito", True)


def ler_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Argumentos da linha de comandos (PT-PT, com os valores medidos/validados por omissão)."""
    p = argparse.ArgumentParser(
        description="Treino PPO headless do hover — planta REAL do dono (peças do catálogo, observação só de "
                    "sensores, crítico assimétrico, DR) ou o Crazyflie 2 histórico — com currículo de vento "
                    "(experiments/09_drone_hover_rl).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--timesteps", type=_inteiro_positivo, default=500_000,
                   help="passos de AMBIENTE a treinar (≥ 1)")
    p.add_argument("--n-envs", type=_inteiro_positivo, default=8,
                   help="envs em SubprocVecEnv (≥ 1, ≤ núcleos lógicos)")
    p.add_argument("--seed", type=int, default=0, help="semente do PPO e dos envs (seed+i)")
    p.add_argument("--out-dir", type=str, default=None,
                   help=f"pasta de saída (por omissão <raiz>/{PASTA_RUNS}/seed<seed>)")
    p.add_argument("--curriculo-vento", type=_curriculo_vento, default=_curriculo_vento(CURRICULO_PADRAO),
                   help=f"tetos de vento (m/s) por estágio do currículo de DR, em [0, {VENTO_MAX_LIMITE:g}] "
                        "e estritamente crescentes (avança 1 estágio por avaliação quando "
                        "frac_no_alvo ≥ 0,8)")
    p.set_defaults(vento_max_explicito=False)   # marcado pela ação quando o utilizador dá --vento-max
    p.add_argument("--vento-max", type=_vento_max, default=VENTO_MAX_PADRAO,
                   action=_MarcaVentoMaxExplicito,
                   help=f"teto de vento fixo (m/s, em [0, {VENTO_MAX_LIMITE:g}]) usado com --sem-curriculo; "
                        "IGNORADO se o currículo estiver ligado (aí os tetos vêm do --curriculo-vento)")
    p.add_argument("--sem-curriculo", action="store_true",
                   help="desliga o currículo: os envs ficam com o teto FIXO --vento-max")
    p.add_argument("--vento-dinamico", choices=("rajadas", "aleatoria", "frente", "dryden"), default=None,
                   help="vento DINÂMICO nos envs de TREINO (o vento base continua a ser o do currículo): "
                        "`rajadas` = rajadas com envelope sin(π·k/(N+1)) SOMADAS ao vento base; "
                        "`aleatoria` = mesmo p/duração/envelope, mas com direção E força re-sorteadas a cada "
                        "rajada em TODA a faixa disponível "
                        "(U[0,5] m/s, azimute [0,360), elevação ±90°) e aplicadas como MISTURA com o base "
                        "(no pico o vento é a rajada; aqui o `u_max` do currículo NÃO limita a amplitude); "
                        "`frente` = degrau de vento a meio do "
                        "episódio (wind front); `dryden` = turbulência OU de 1.ª ordem. Nos modos em que o "
                        "`u_max` conta, ele SEGUE "
                        "o teto do currículo (estágio 0 = 0 m/s = modo inerte: para vento dinâmico desde o "
                        "início use `--curriculo-vento 3` ou `--sem-curriculo --vento-max 3`). Por omissão "
                        "desligado (só o vento constante/por episódio de antes)")
    p.add_argument("--vento-dinamico-params", type=_json_dict, default=None, metavar="JSON",
                   help="parâmetros do modo dinâmico em JSON (ex.: '{\"p\": 0.02, \"duracao\": 10}' para "
                        "rajadas/aleatoria, '{\"t_s\": 2.0}' para a frente, '{\"sigma\": 0.5, \"L\": 10.0}' "
                        "para dryden). "
                        "O que faltar usa o default do env.py; `modo` e `u_max` NÃO entram aqui (o modo vem do "
                        "--vento-dinamico e o teto SEGUE o currículo)")
    p.add_argument("--avanco-frac", type=_frac_avanco, default=FRAC_AVANCO,
                   help="fração de passos com xy+z no alvo (SEM yaw) que faz subir um estágio do currículo")
    p.add_argument("--retomar", type=str, default=None, metavar="CHECKPOINT",
                   help="continua a partir de um best_model.zip/final.zip do SB3 (PPO.load + learn): os "
                        "pesos e o Adam são restaurados, o rollout buffer não; --timesteps passa a ser o "
                        "orçamento ADICIONAL e usa-se um --out-dir NOVO para não escrever por cima")
    p.add_argument("--log-std-init", type=float, default=None,
                   help="desvio-padrão inicial do log da ação (σ = exp(valor); o SB3 usa 0,0); por omissão −0,5 "
                        "no cf2 e −1,0 na planta real (σ ≈ 0,37: menos ruído de exploração num drone de 1,7 kg)")
    p.add_argument("--ent-coef", type=float, default=0.001, help="coeficiente de entropia (evita colapso)")
    p.add_argument("--lr", type=float, default=1e-4, help="learning rate do PPO")
    p.add_argument("--sucesso", type=float, default=None,
                   help="limiar de retorno médio (StopTrainingOnRewardThreshold); por omissão 450 no cf2 (~500 = "
                        "hover perfeito na v2b) e 700 na planta real (~750 = pairagem perfeita na v3-real)")
    p.add_argument("--eval-freq", type=int, default=5000,
                   help="passos do VEC entre avaliações (n_calls = timesteps/n_envs)")
    p.add_argument("--sem-painel", action="store_true",
                   help="sem rich: só linhas de log (CI/verificadores); o rich nunca é importado")
    p.add_argument("--planta", choices=("real", "cf2"), default="real",
                   help="`real` = o drone do dono (peças do catálogo models/drone_rpi, observação SÓ de sensores, "
                        "crítico assimétrico, domain randomization); `cf2` = o HoverEnv histórico do Crazyflie")
    p.add_argument("--build", type=str, default=None,
                   help="build do catálogo (models/drone_rpi/builds.json); por omissão o ATIVO")
    p.add_argument("--modo-acao", choices=MODOS_ACAO, default="ctbr",
                   help="planta real: `ctbr` = coletivo + taxas para o FC dedicado; `motores` = 4 aceleradores")
    p.add_argument("--sem-dr", action="store_true",
                   help="planta real: desliga a domain randomization dos parâmetros físicos (só vento)")
    p.add_argument("--net-arch", type=str, default=None,
                   help="camadas ocultas do ator e do crítico, ex. '128,128' (por omissão: 128,128 na planta "
                        "real, 64,64 no cf2)")
    args = p.parse_args(argv)
    if args.sucesso is None:
        args.sucesso = 700.0 if args.planta == "real" else 450.0
    if args.log_std_init is None:
        args.log_std_init = -1.0 if args.planta == "real" else -0.5
    if args.net_arch is None:
        args.net_arch = "128,128" if args.planta == "real" else "64,64"
    try:
        args.camadas = [int(x) for x in str(args.net_arch).split(",") if x.strip()]
        if not args.camadas or min(args.camadas) < 1:
            raise ValueError
    except ValueError:
        p.error(f"--net-arch: lista de inteiros ≥ 1 separados por vírgulas (recebido {args.net_arch!r})")
    if args.planta == "real":
        try:
            from lab import drone_rpi as _dr
            _dr.hardware(args.build)
        except (KeyError, ValueError) as erro:
            p.error(f"--build: {erro}")
    args.vento_dinamico_cfg = _resolve_vento_dinamico(p, args)
    return args


def _resolve_vento_dinamico(p: argparse.ArgumentParser, args: argparse.Namespace) -> dict | None:
    """Config VALIDADA do vento dinâmico a partir de `--vento-dinamico` + `--vento-dinamico-params`.

    Erros de utilização saem por `p.error` (`exit 2`, como os outros valores inválidos do CLI), não como
    traceback: `--vento-dinamico-params` sem `--vento-dinamico`, JSON com `modo` (vem do flag) ou com `u_max`
    (o teto SEGUE o currículo — ver o docstring do módulo) e parâmetros inválidos (`p` fora de [0,1],
    `duracao` não inteira, `sigma`/`L` ≤ 0, …), validados pelo próprio `env.valida_vento_dinamico`.
    Devolve o dict normalizado (com os defaults do modo) ou `None` (vento dinâmico desligado).
    """
    params = args.vento_dinamico_params
    if args.vento_dinamico is None:
        if params is not None:
            p.error("--vento-dinamico-params só faz sentido com --vento-dinamico "
                    "rajadas|aleatoria|frente|dryden")
        return None
    if params is not None:
        if "modo" in params:
            p.error("--vento-dinamico-params: não incluas `modo` — o modo vem de --vento-dinamico")
        if "u_max" in params:
            p.error("--vento-dinamico-params: não incluas `u_max` — o teto do vento dinâmico SEGUE o "
                    "currículo (--curriculo-vento no estágio atual, ou --vento-max com --sem-curriculo)")
    try:
        return valida_vento_dinamico({"modo": args.vento_dinamico, **(params or {})})
    except ValueError as erro:
        p.error(f"--vento-dinamico-params: {erro}")
        return None      # inalcançável (p.error levanta SystemExit) — mantém o tipo de retorno claro


def resolver_saida(args: argparse.Namespace) -> Path:
    """Pasta de saída: `--out-dir` tal e qual (relativo ao cwd) ou `<raiz>/…/runs/seed<seed>`."""
    if args.out_dir:
        destino = Path(args.out_dir).expanduser()
        return destino if destino.is_absolute() else Path.cwd() / destino
    return _RAIZ / PASTA_RUNS / f"seed{args.seed}"


# ----------------------------------------------------------------------------------------------- currículo
class CurriculoVento:
    """Currículo de vento (DR): tetos crescentes e avanço de UM estágio quando a fração xy+z é alta.

    `avaliar(frac_xy_z)` é chamado UMA vez por avaliação e recebe a fração de passos com ‖xy‖ e |z − alvo|
    dentro da tolerância do bónus, SEM guinada (ronda 3: com o bónus completo — que inclui yaw — a grelha
    ficava inatingível e o DR nunca ligava). Se a fração chega a `frac_avanco` e ainda há estágio seguinte,
    sobe exatamente um degrau e devolve o teto novo; senão devolve `None`. A guarda de "no máximo 1 estágio
    por avaliação" é estrutural (uma chamada ⇒ no máximo um degrau), não uma condição que se possa esquecer.
    `u_vento` é sempre o teto EM VIGOR (o topo do estágio atual).
    """

    def __init__(self, estagios: Sequence[float], frac_avanco: float = FRAC_AVANCO):
        if len(estagios) < 1:
            raise ValueError("o currículo precisa de ≥ 1 estágio (lista de tetos de vento)")
        self.estagios = tuple(float(u) for u in estagios)
        self.frac_avanco = float(frac_avanco)
        self.estagio = 0

    @property
    def u_vento(self) -> float:
        """Teto de vento atual (m/s) — o `u_max` do `vento_aleatorio=(0, u_max)` dos envs de treino."""
        return self.estagios[self.estagio]

    @property
    def n_estagios(self) -> int:
        """Número de estágios do currículo (1 = teto fixo, sem avanços)."""
        return len(self.estagios)

    @property
    def no_topo(self) -> bool:
        """True quando já está no último estágio (nada mais a subir)."""
        return self.estagio >= self.n_estagios - 1

    def avaliar(self, frac_xy_z: float) -> float | None:
        """Avalia o critério de avanço (`frac_xy_z`); devolve o teto NOVO se subiu, senão `None`."""
        if self.no_topo or float(frac_xy_z) < self.frac_avanco:
            return None
        self.estagio += 1
        return self.u_vento


def config_dinamica(cfg: dict | None, u_teto: float) -> dict | None:
    """Config COMPLETA do vento dinâmico para os envs, com `u_max` = teto do currículo em vigor.

    É a REGRA DO TETO do treino (uma só, ver o docstring do módulo): o modo dinâmico nunca impõe o seu
    próprio teto — usa o do estágio atual do currículo (ou o `--vento-max` fixo do `--sem-curriculo`). Com
    teto 0 m/s (`u_max = 0`) o modo fica inerte: o `env` aceita-o de propósito (estágio 0 = ar parado).
    EXCEÇÃO: o modo `aleatoria` recebe o `u_max` como todos os outros, mas ignora-o na amostragem (o teto do
    modo é sempre 5 m/s); o `u_max = 0` continua a deixá-lo inerte, para o estágio 0 seguir a ser ar parado.
    """
    if cfg is None:
        return None
    return {**cfg, "u_max": float(u_teto)}


def aplicar_teto_vento(venv: SubprocVecEnv, u_novo: float, din_cfg: dict | None = None) -> None:
    """Muda o teto do currículo em TODOS os envs de treino (`env_method` funciona em `SubprocVecEnv`).

    `definir_vento_aleatorio(0, u_novo)` liga o regime `U ~ U[0, u_novo]` em cada env e AMOSTRA JÁ um vento
    novo desse regime: o episódio em curso sente o teto novo IMEDIATAMENTE (não espera pelo reset — medido
    no env: passo 4, sem reset, vento 0,00 → 3,03 m/s ao subir o teto para 5); o `Monitor` de cada env
    reencaminha a chamada para o `HoverEnv` embrulhado.

    Com vento dinâmico (`din_cfg`), o teto do modo SEGUE o estágio: `definir_vento_dinamico` recebe a config
    com o `u_max` novo. Como o modo não muda, o env conserva o estado da dinâmica (rajada em curso, frente já
    aplicada, turbulência) e só reamostra a frente se ela ainda não tiver chegado — logo o `u_max` novo vale
    já a partir do passo de decisão seguinte. No modo `aleatoria` o `u_max` novo não limita a amplitude (só
    o teto 0 o torna inerte), mas o vento BASE continua a seguir o teto do currículo.
    """
    venv.env_method("definir_vento_aleatorio", 0.0, float(u_novo))
    if din_cfg is not None:
        venv.env_method("definir_vento_dinamico", config_dinamica(din_cfg, u_novo))


def descricao_vento(sem_curriculo: bool, curriculo: CurriculoVento) -> str:
    """Uma linha legível do regime de vento em vigor (cabeçalho do treino).

    Distingue os TRÊS regimes, sem os confundir: teto fixo com `--sem-curriculo`, currículo de UM estágio
    (o DR `U ~ U[0, u]` está LIGADO, só não há avanços — não é "sem currículo") e currículo com vários
    estágios. Em todos eles a randomização POR EPISÓDIO existe: o que `--sem-curriculo` desliga são os
    AVANÇOS de estágio, não o DR.
    """
    dr = f"DR por episódio: U ~ U[0, {curriculo.u_vento:g}] m/s em todos os envs, reamostrado em cada reset"
    if sem_curriculo:
        return (f"vento · SEM currículo: teto FIXO {curriculo.u_vento:g} m/s, sem avanços de estágio · {dr} "
                "(`--sem-curriculo` desliga os avanços, NÃO a randomização)")
    if curriculo.n_estagios == 1:
        return (f"vento · currículo com 1 estágio (teto {curriculo.u_vento:g} m/s, sem avanços) · {dr} — "
                "o DR está LIGADO (não é o regime `--sem-curriculo`)")
    tetos = ", ".join(f"{u:g}" for u in curriculo.estagios)
    return (f"vento · currículo de DR com {curriculo.n_estagios} estágios, tetos [{tetos}] m/s · "
            f"sobe 1 estágio por avaliação quando frac_xy_z (xy+z, SEM yaw) ≥ {curriculo.frac_avanco:g}")


def descricao_vento_dinamico(cfg: dict | None, u_teto: float) -> str:
    """Uma linha legível do vento DINÂMICO em vigor (ou a dizer que está desligado).

    `cfg` é a config (sem `u_max` de treino — o teto mostrado é o do currículo em vigor) e `u_teto` o teto
    atual, para o cabeçalho do treino dizer exatamente com que rajada/frente/turbulência a política treina.
    """
    if cfg is None:
        return ("vento dinâmico · DESLIGADO (só o vento base por episódio, como no treino anterior; "
                "`--vento-dinamico rajadas|aleatoria|frente|dryden` liga rajadas/frentes/turbulência a meio "
                "do voo)")
    if cfg["modo"] == "rajadas":
        return (f"vento dinâmico · RAJADAS: p={cfg['p']:g}/passo de decisão, duração {cfg['duracao']} passos, "
                f"envelope sin(π·k/(N+1)) e amplitude u ~ U[0, {u_teto:g}] m/s (azimute aleatório, elevação "
                f"±20°) SOMADA ao vento base; u_max SEGUE o teto do currículo ({u_teto:g} m/s)")
    if cfg["modo"] == "aleatoria":
        return (f"vento dinâmico · RAJADAS ALEATÓRIAS: p={cfg['p']:g}/passo de decisão, duração "
                f"{cfg['duracao']} passos e, a CADA rajada, direção E força re-sorteadas dentro das faixas "
                f"disponíveis (u ~ U[0, 5] m/s, azimute [0, 360), elevação ±90°), aplicadas como MISTURA com "
                f"o vento base pelo envelope sin(π·k/(N+1)) — no pico o vento é a rajada sorteada e nas "
                f"pontas fica junto do base; o u_max do currículo ({u_teto:g} m/s) NÃO limita a amplitude "
                f"(só o teto 0 o torna inerte)")
    if cfg["modo"] == "frente":
        return (f"vento dinâmico · FRENTE: degrau a t_s={cfg['t_s']:g} s do episódio para "
                f"u ~ U[min(0,5; {u_teto:g}); {u_teto:g}] m/s com azimute aleatório (substitui o vento base "
                f"até ao fim); u_max SEGUE o teto do currículo ({u_teto:g} m/s)")
    return (f"vento dinâmico · DRYDEN: turbulência OU de 1.ª ordem (σ={cfg['sigma']:g} m/s, L={cfg['L']:g} m, "
            f"v_min={cfg['v_min']:g} m/s, α = exp(−0,02·V/L)) sobre o vento base, saturada em norma a "
            f"u_max = {u_teto:g} m/s (teto do currículo)")


# ----------------------------------------------------------------------------------------------- envs
def _fabrica_env(semente: int, pasta: str, raiz: str, u_teto: float,
                 din_cfg: dict | None = None, planta: str = "cf2", build: str | None = None,
                 modo_acao: str = "ctbr", aleatorizar: bool = True) -> Callable[[], Any]:
    """Fábrica picklável (cloudpickle) de UM env com `Monitor`, vento `U ~ U[0, u_teto]` e vento dinâmico.

    `din_cfg` é a config JÁ completa (com `u_max` = teto do currículo, via `config_dinamica`) ou `None`
    (treino sem vento dinâmico — o default, que não toca no caminho do env). `planta="real"` cria o
    `DroneRealEnv` (peças do build, observação só de sensores, DR física se `aleatorizar`).
    """

    def _init():
        # o subprocesso (forkserver/spawn) tem de achar `env`/`lab`: repõe o sys.path antes do import tardio
        for caminho in (pasta, raiz):
            if caminho not in sys.path:
                sys.path.insert(0, caminho)
        if planta == "real":
            from env_real import (
                DroneRealEnv as _Real,  # import DENTRO do subprocesso (mujoco por processo)
            )

            ambiente = _Real(build=build, modo_acao=modo_acao, aleatorizar=aleatorizar,
                             vento_aleatorio=(0.0, float(u_teto)), vento_dinamico=din_cfg)
        else:
            from env import (
                HoverEnv as _HoverEnv,  # import DENTRO do subprocesso (mujoco por processo)
            )

            ambiente = _HoverEnv(vento_aleatorio=(0.0, float(u_teto)),  # currículo de vento no 1.º estágio
                                 vento_dinamico=din_cfg)                # vento que muda a meio do voo (ou None)
        ambiente.reset(seed=semente)  # fixa o stream do np_random (jitter do reset) antes do 1.º reset do vec
        return Monitor(ambiente)

    return _init


def criar_envs_treino(n_envs: int, seed: int, u_teto: float,
                      din_cfg: dict | None = None, args: argparse.Namespace | None = None) -> SubprocVecEnv:
    """`n_envs` cópias do env (vento até `u_teto` + dinâmico `din_cfg`) em processos separados."""
    planta = getattr(args, "planta", "cf2")
    extra = {} if planta != "real" else {"planta": "real", "build": args.build, "modo_acao": args.modo_acao,
                                         "aleatorizar": not args.sem_dr}
    fabricas = [_fabrica_env(seed + i, str(_PASTA), str(_RAIZ), u_teto, din_cfg, **extra) for i in range(n_envs)]
    return SubprocVecEnv(fabricas)


def criar_env_avaliacao(args: argparse.Namespace) -> HoverEnv:
    """Env de AVALIAÇÃO/MÉTRICAS: sem vento e, na planta real, com os parâmetros NOMINAIS (sem DR) e a
    bateria cheia — a régua tem de ser comparável entre avaliações."""
    if getattr(args, "planta", "cf2") == "real":
        return DroneRealEnv(build=args.build, modo_acao=args.modo_acao, aleatorizar=False)
    return HoverEnv()


def gravar_hardware(args: argparse.Namespace, out_dir: Path) -> dict | None:
    """`hardware.json` ao lado do modelo: o build (peças + config), os derivados e a DR — os dados das peças
    REAIS com que a política foi treinada (o deploy e o site leem-no; trocar de peças = treinar de novo)."""
    if getattr(args, "planta", "cf2") != "real":
        return None
    from lab import drone_rpi as _dr
    hw = _dr.hardware(args.build)
    builds = _dr.carregar_builds()
    resumo = hw.resumo()
    resumo["autonomia"].pop("serie", None)
    dados = {
        "planta": "real", "build": hw.nome, "config_build": builds["builds"].get(hw.nome, hw.dados),
        "pecas": {"motor": hw.motor.dados, "helice": hw.helice.dados, "celula": hw.bateria.celula.dados,
                  "frame": hw.frame.dados, "esc": hw.esc.dados,
                  "eletronica": [c.dados for c in hw.consumidores], "sensores": hw.sensores},
        "derivados": resumo, "modo_acao": args.modo_acao, "obs_ator_dim": OBS_ATOR_DIM,
        "domain_randomization": None if args.sem_dr else FAIXAS_DR,
    }
    with (out_dir / "hardware.json").open("w", encoding="utf-8") as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2, default=float)
    return dados


def calcular_eval_freq(pedido: int, timesteps: int, n_envs: int) -> int:
    """Passos do VEC entre avaliações: o pedido, mas com ≥`MIN_AVALIACOES` avaliações no orçamento dado.

    O piso `MIN_PASSOS_VEC` só limita a cadência AUTOMÁTICA (um `--eval-freq` explícito é respeitado tal e
    qual): sem ele, um `--timesteps 1` dispararia uma avaliação por chamada (1024 avaliações de 10 episódios).
    Como o `learn()` faz sempre pelo menos um rollout (`n_calls ≥ n_steps = 512`), continua a haver ≥4
    avaliações em qualquer run válido — e é nessas avaliações que o currículo de vento pode avançar.
    """
    teto = max(MIN_PASSOS_VEC, timesteps // max(1, n_envs) // MIN_AVALIACOES)
    return max(1, min(pedido, teto))


# ----------------------------------------------------------------------------------------------- painel
def _fmt(valor: float | None, casas: int = 2, sufixo: str = "") -> str:
    """Formata um número para o painel; `None`/NaN → travessão."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "—"
    return f"{valor:,.{casas}f}{sufixo}".replace(",", " ")


def _sparkline(valores: list[float]) -> str:
    """Mini-curva em blocos unicode (sem dependências): a evolução do retorno por avaliação."""
    if not valores:
        return "—"
    blocos = "▁▂▃▄▅▆▇█"
    baixo, alto = min(valores), max(valores)
    if alto - baixo < 1e-9:
        return blocos[len(blocos) // 2] * len(valores)
    escala = (len(blocos) - 1) / (alto - baixo)
    return "".join(blocos[int((v - baixo) * escala)] for v in valores)


class PainelNulo:
    """Painel de `--sem-painel`: nenhuma dependência de UI, só linhas de texto (CI/verificadores)."""

    def atualizar(self, **_campos: Any) -> None:
        """Nada a atualizar (sem UI)."""

    def escrever(self, mensagem: str) -> None:
        """Escreve uma linha de log no stdout."""
        print(mensagem, flush=True)

    def parar(self) -> None:
        """Nada a fechar."""


class Painel:
    """Painel `rich.Live` (barra `rich.progress` + tabela de métricas) com refresh a ~2 Hz.

    Nunca faz render 3D nem abre browser: só terminal. O `rich` é importado AQUI (dentro do `__init__`)
    para que `--sem-painel` corra sem o pacote. A curva do retorno é desenhada com blocos unicode
    (a API do plotext 6.1.0 instalada não expõe o `plot()/build()` clássico). Além do retorno/z/dist/no_alvo
    mostra `yaw_err` (a guinada que a recompensa v2 penaliza) e o teto de vento com o estágio do currículo.
    """

    def __init__(self, total: int, titulo: str):
        from rich import box
        from rich.console import Console, Group
        from rich.live import Live
        from rich.progress import (
            BarColumn,
            Progress,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
            TimeRemainingColumn,
        )
        from rich.table import Table
        from rich.text import Text

        self._box, self._Group, self._Table, self._Text = box, Group, Table, Text
        self._console = Console()
        self._progress = Progress(
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TextColumn("[dim]{task.completed:,}/{task.total:,} passos[/]"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self._console,
        )
        self._tarefa = self._progress.add_task(titulo, total=total)
        self._campos: dict[str, Any] = {
            "total": total, "passos": 0, "fps": None, "mean_ret": None, "std_ret": None, "mean_z": None,
            "mean_dist_xy": None, "frac_no_alvo": None, "mean_yaw_err": None, "frac_alvo_total": None,
            "frac_xy_z": None, "u_vento": None, "estagio": None, "n_estagios": None, "avanco_frac": None,
            "elapsed_s": None, "melhor": None, "avaliacoes": 0, "sucesso": None, "curva": [],
        }
        self._live = Live(self._render(), console=self._console, refresh_per_second=2, transient=False)
        self._live.start()

    def atualizar(self, **campos: Any) -> None:
        """Atualiza os campos do painel e redesenha (chamado a ≤2 Hz pelo callback)."""
        self._campos.update(campos)
        self._progress.update(self._tarefa, completed=min(self._campos["passos"], self._campos["total"]))
        self._live.update(self._render())

    def escrever(self, mensagem: str) -> None:
        """Escreve uma linha acima da região do `Live` (não estraga o painel).

        `markup=False`: as mensagens são TEXTO SIMPLES e trazem prefixos entre parênteses retos
        (`[eval 3]`, `[currículo]`, `[aviso]`) que o markup do rich interpretaria como etiquetas de estilo
        e APAGARIA da linha — verificado: com o markup ligado as linhas de avaliação saíam sem prefixo.
        """
        self._console.print(mensagem, markup=False)

    def parar(self) -> None:
        """Fecha o `Live` (devolve o terminal ao estado normal)."""
        self._live.stop()

    # ------------------------------------------------------------------ interno
    def _texto_vento(self) -> str:
        """Teto de vento em vigor + estágio do currículo (`0.00 m/s · estágio 2/4`), ou travessão."""
        c = self._campos
        if c["u_vento"] is None:
            return "—"
        texto = f"{_fmt(c['u_vento'])} m/s"
        if c["estagio"] is not None and c["n_estagios"]:
            texto += f" · estágio {int(c['estagio']) + 1}/{int(c['n_estagios'])}"
        return texto

    def _render(self):
        """Constrói o renderable: barra de progresso + tabela de métricas + curva do retorno."""
        c = self._campos
        tabela = self._Table(box=self._box.SIMPLE_HEAVY, show_header=True, header_style="bold",
                             title="[bold]PPO · hover Crazyflie 2[/]", title_justify="left")
        tabela.add_column("métrica", style="cyan", no_wrap=True)
        tabela.add_column("valor", justify="right")
        tabela.add_column("métrica", style="cyan", no_wrap=True)
        tabela.add_column("valor", justify="right")
        tabela.add_row("passos (ambiente)", _fmt(float(c["passos"]), 0),
                       "retorno médio (eval)", _fmt(c["mean_ret"]) + f" ± {_fmt(c['std_ret'])}")
        tabela.add_row("fps (média acumulada)", _fmt(c["fps"], 0),
                       "melhor retorno", _fmt(c["melhor"]))
        tabela.add_row("z médio [m]", _fmt(c["mean_z"], 3),
                       "avaliações", str(c["avaliacoes"]))
        tabela.add_row("dist_xy médio [m]", _fmt(c["mean_dist_xy"], 3),
                       "limiar de sucesso", _fmt(c["sucesso"], 0))
        tabela.add_row("no alvo xy+z (avanço)",
                       _fmt(None if c["frac_xy_z"] is None else 100 * c["frac_xy_z"], 1, " %"),
                       "tempo [s]", _fmt(c["elapsed_s"], 1))
        tabela.add_row("no alvo (xy+z+yaw)",
                       _fmt(None if c["frac_no_alvo"] is None else 100 * c["frac_no_alvo"], 1, " %"),
                       "yaw_err médio [rad]", _fmt(c["mean_yaw_err"], 3))
        tabela.add_row("teto de vento [m/s]", self._texto_vento(),
                       "limiar de avanço", _fmt(None if c["avanco_frac"] is None
                                                else 100 * c["avanco_frac"], 0, " %"))
        curva = self._Text()
        curva.append("retorno por avaliação  ", style="dim")
        curva.append(_sparkline([float(v) for v in c["curva"]]), style="bold green")
        return self._Group(self._progress, tabela, curva)


# ----------------------------------------------------------------------------------------------- callback
class CallbackRegisto(BaseCallback):
    """Acrescenta UMA linha a `train_log.jsonl` por avaliação, avalia o currículo de vento e alimenta o painel.

    Corre DEPOIS do `EvalCallback` (a ordem da lista de callbacks é preservada pelo SB3): lê o
    `evaluations.npz` já fresco para `mean_ret`/`std_ret` e faz `n_episodios` rollouts determinísticos
    PRÓPRIOS num `HoverEnv` dedicado (sem vento) para medir `mean_z`/`mean_dist_xy`/`mean_yaw_err`/
    `frac_no_alvo`/`frac_alvo_total`/`frac_xy_z` — o `EvalCallback` só agrega retorno. Com o `frac_xy_z`
    medido (xy+z, SEM yaw), pede ao `CurriculoVento` o próximo estágio (no máximo um por avaliação) e, se
    ele subir, escreve o teto novo em todos os envs de treino. `fps` = passos de ambiente DESTE run / tempo
    decorrido desde o início (com `--retomar`, `passos_iniciais` desconta o que veio do checkpoint, para o
    `fps` e a barra de progresso não contarem 780 000 passos herdados).
    """

    def __init__(self, eval_cb: EvalCallback, caminho_log: Path, painel: Any, env_metrica: HoverEnv,
                 curriculo: CurriculoVento, venv: SubprocVecEnv | None = None,
                 n_episodios: int = N_EPISODIOS_METRICAS, seed: int = 0, sucesso: float = 450.0,
                 passos_iniciais: int = 0, din_cfg: dict | None = None, verbose: int = 0):
        super().__init__(verbose=verbose)
        self.eval_cb = eval_cb
        self.caminho_log = Path(caminho_log)
        self.painel = painel
        self.env_metrica = env_metrica
        self.curriculo = curriculo
        self.venv = venv
        self.n_episodios = int(n_episodios)
        self.seed = int(seed)
        self.sucesso = float(sucesso)
        self.passos_iniciais = int(passos_iniciais)
        self.din_cfg = din_cfg      # config do vento dinâmico (o `u_max` acompanha o estágio do currículo)
        self._evals_vistos = 0
        self._t0 = 0.0
        self._retornos: list[float] = []
        self._metricas: dict[str, float] = {}
        self._ultimo_refresh = 0.0
        self._p_media = 0.0

    def _on_training_start(self) -> None:
        self._t0 = time.perf_counter()
        self.painel.atualizar(sucesso=self.sucesso, u_vento=self.curriculo.u_vento,
                              estagio=self.curriculo.estagio, n_estagios=self.curriculo.n_estagios,
                              avanco_frac=self.curriculo.frac_avanco)
        self._atualizar_painel()

    def _on_step(self) -> bool:
        agora = time.perf_counter()
        if agora - self._ultimo_refresh >= 0.5:  # ~2 Hz
            self._atualizar_painel()
        if len(self.eval_cb.evaluations_timesteps) > self._evals_vistos:
            self._registar_avaliacao()
        return True

    # ------------------------------------------------------------------ interno
    def _registar_avaliacao(self) -> None:
        """Lê o `evaluations.npz`, mede as métricas em rollouts próprios, escreve a linha JSONL e avalia o
        currículo de vento (o `u_vento` registado é o teto EM VIGOR a partir desta avaliação).

        O avanço usa `frac_xy_z` (xy+z, SEM yaw) — o `frac_no_alvo` continua na linha só como sinal de
        guinada/qualidade (o dashboard usa-o) e NÃO decide nada.
        """
        self._evals_vistos = len(self.eval_cb.evaluations_timesteps)
        with np.load(self.caminho_log.parent / "evaluations.npz") as dados:
            timesteps = int(dados["timesteps"][-1])
            retornos = np.asarray(dados["results"][-1], dtype=float)
        z_medio, dist_medio, yaw_medio, frac_alvo, frac_total, frac_xy_z = self._rollouts_proprios()
        teto_antes = self.curriculo.u_vento
        novo_teto = self.curriculo.avaliar(frac_xy_z)
        if novo_teto is not None and self.venv is not None:
            aplicar_teto_vento(self.venv, novo_teto, self.din_cfg)   # o teto dinâmico segue o do currículo
        elapsed = time.perf_counter() - self._t0
        passos_run = max(0, timesteps - self.passos_iniciais)   # só o que este run treinou
        mean_ret = float(np.mean(retornos))
        self._retornos.append(mean_ret)
        linha = {
            "t": timesteps,
            "mean_ret": mean_ret,
            "std_ret": float(np.std(retornos)),
            "mean_z": float(z_medio),
            "mean_dist_xy": float(dist_medio),
            "frac_no_alvo": float(frac_alvo),
            "mean_yaw_err": float(yaw_medio),
            "frac_alvo_total": float(frac_total),
            "frac_xy_z": float(frac_xy_z),
            "u_vento": float(self.curriculo.u_vento),
            "fps": float(passos_run / elapsed) if elapsed > 0 else 0.0,
            "elapsed_s": float(elapsed),
            "seed": self.seed,
            "planta": "real" if isinstance(self.env_metrica, DroneRealEnv) else "cf2",
            "p_media_w": float(self._p_media),
        }
        with self.caminho_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
        self._metricas = {chave: linha[chave] for chave in
                          ("mean_ret", "std_ret", "mean_z", "mean_dist_xy", "frac_no_alvo",
                           "mean_yaw_err", "frac_alvo_total", "frac_xy_z", "u_vento")}
        self._metricas["estagio"] = self.curriculo.estagio
        self._metricas["n_estagios"] = self.curriculo.n_estagios
        self._atualizar_painel()
        vento_txt = (f"{teto_antes:g}→{novo_teto:g} m/s" if novo_teto is not None else f"{teto_antes:g} m/s")
        self.painel.escrever(
            f"[eval {self._evals_vistos}] t={timesteps} (+{passos_run} neste run) retorno={mean_ret:.1f}"
            f"±{linha['std_ret']:.1f} z={z_medio:.3f} m dist_xy={dist_medio:.3f} m "
            f"yaw_err={yaw_medio:.3f} rad xy+z={100 * frac_xy_z:.0f} % "
            f"no_alvo(com yaw)={100 * frac_alvo:.0f} % vento={vento_txt} fps={linha['fps']:.0f}"
            f" ({elapsed:.1f} s)"
        )
        if novo_teto is not None:
            extra_din = ("" if self.din_cfg is None else
                         f" · teto do vento dinâmico ({self.din_cfg['modo']}) também {novo_teto:g} m/s")
            self.painel.escrever(
                f"[currículo] frac_xy_z={100 * frac_xy_z:.0f} % ≥ {100 * self.curriculo.frac_avanco:.0f} %"
                f" (no_alvo com yaw = {100 * frac_alvo:.0f} %) → estágio "
                f"{self.curriculo.estagio + 1}/{self.curriculo.n_estagios} · teto de vento "
                f"{novo_teto:g} m/s (escrito nos envs de treino por env_method){extra_din}"
            )

    def _rollouts_proprios(self) -> tuple[float, float, float, float, float, float]:
        """`n_episodios` episódios determinísticos (`model.predict`) no env de métricas SEM VENTO.

        Devolve `(z médio, dist_xy médio, |yaw_err| médio, frac_no_alvo, frac_alvo_total, frac_xy_z)`, tudo
        por passo de decisão. `frac_no_alvo` usa o `info["no_alvo"]` do env (a bandeira do contrato — no v2
        do env ela JÁ é o bónus completo xy+z+yaw) e `frac_alvo_total` recalcula esse bónus explicitamente a
        partir das tolerâncias do `env` (`BONUS_XY`/`BONUS_Z`/`BONUS_YAW`); `frac_xy_z` é o MESMO bónus SEM a
        guinada — é o critério de avanço do currículo desde a ronda 3 (com yaw a grelha era inatingível:
        uma política que paira bem mede ~0,10 no bónus completo e o DR nunca ligava).
        """
        zs, dists, yaws, fracoes, totais, xyzs, potencias = [], [], [], [], [], [], []
        alvo_z = float(getattr(self.env_metrica, "alvo_z", 1.0))
        max_passos = int(getattr(self.env_metrica, "max_passos", 500))
        for _ in range(self.n_episodios):
            obs, _ = self.env_metrica.reset()
            z_ep = d_ep = yaw_ep = 0.0
            alvo_ep = total_ep = xyz_ep = passos = 0
            for _ in range(max_passos):
                acao, _ = self.model.predict(obs, deterministic=True)
                obs, _r, terminado, truncado, info = self.env_metrica.step(acao)
                dist_xy = float(info["dist_xy"])
                yaw_err = float(info["yaw_err"])
                no_xy_z = dist_xy < BONUS_XY and abs(float(info["z"]) - alvo_z) < BONUS_Z
                z_ep += float(info["z"])
                d_ep += dist_xy
                yaw_ep += abs(yaw_err)
                alvo_ep += int(bool(info["no_alvo"]))
                total_ep += int(no_xy_z and abs(yaw_err) < BONUS_YAW)
                xyz_ep += int(no_xy_z)
                if "p_total" in info:
                    potencias.append(float(info["p_total"]))
                passos += 1
                if terminado or truncado:
                    break
            passos = max(passos, 1)
            zs.append(z_ep / passos)
            dists.append(d_ep / passos)
            yaws.append(yaw_ep / passos)
            fracoes.append(alvo_ep / passos)
            totais.append(total_ep / passos)
            xyzs.append(xyz_ep / passos)
        self._p_media = float(np.mean(potencias)) if potencias else 0.0
        return (float(np.mean(zs)), float(np.mean(dists)), float(np.mean(yaws)),
                float(np.mean(fracoes)), float(np.mean(totais)), float(np.mean(xyzs)))

    def _atualizar_painel(self) -> None:
        """Refresca o painel: campos dinâmicos (passos/fps/tempo) + as últimas métricas de avaliação."""
        elapsed = time.perf_counter() - self._t0 if self._t0 else 0.0
        passos = int(self.num_timesteps) - self.passos_iniciais   # relativos a ESTE run (ver --retomar)
        campos: dict[str, Any] = {
            "passos": passos,
            "fps": (passos / elapsed) if elapsed > 0 else None,
            "elapsed_s": elapsed if self._t0 else None,
            "melhor": (None if self.eval_cb.best_mean_reward == -np.inf else self.eval_cb.best_mean_reward),
            "avaliacoes": self._evals_vistos,
            "curva": list(self._retornos),
            **self._metricas,          # métricas da última avaliação (inclui o `u_vento` que ela registou)
        }
        # O vento/estágio do painel são o estado ATUAL do currículo (pode ter subido desde a última
        # avaliação) → escrevem-se DEPOIS do unpack e sobrepõem o valor registado na linha JSONL.
        campos["u_vento"] = self.curriculo.u_vento
        campos["estagio"] = self.curriculo.estagio
        campos["n_estagios"] = self.curriculo.n_estagios
        campos["avanco_frac"] = self.curriculo.frac_avanco
        self.painel.atualizar(**campos)
        self._ultimo_refresh = time.perf_counter()


# ----------------------------------------------------------------------------------------------- treino
def construir_callbacks(args: argparse.Namespace, out_dir: Path, eval_freq: int, painel: Any,
                        env_metrica: HoverEnv, curriculo: CurriculoVento, venv: SubprocVecEnv,
                        passos_iniciais: int = 0, din_cfg: dict | None = None
                        ) -> tuple[list[BaseCallback], EvalCallback]:
    """EvalCallback (+ paragem por sucesso) · CheckpointCallback · CallbackRegisto, por esta ordem.

    `din_cfg` é a config do vento dinâmico dos envs de TREINO (parâmetros do modo): o `CallbackRegisto`
    reescreve-a com o `u_max` = teto novo quando o currículo sobe. A AVALIAÇÃO e as MÉTRICAS continuam SEM
    vento (nem base nem dinâmico) — a régua de progresso tem de ficar comparável entre estágios.
    """
    (out_dir / "ckpt").mkdir(parents=True, exist_ok=True)
    paragem = StopTrainingOnRewardThreshold(reward_threshold=args.sucesso, verbose=1)
    # O env de avaliação é semeado UMA vez, a partir da seed do run, e é SEM VENTO: a régua (retorno médio,
    # best_model) tem de ser comparável entre estágios do currículo — se o vento entrasse aqui, o retorno
    # caía sempre que o teto sobe e o critério de avanço ficava confundido com a dificuldade do treino.
    env_eval = criar_env_avaliacao(args)
    env_eval.reset(seed=args.seed + 1_000)
    eval_cb = EvalCallback(
        Monitor(env_eval),                   # env de avaliação ÚNICO (o EvalCallback embrulha-o em DummyVecEnv)
        callback_on_new_best=paragem,        # para o treino quando o retorno médio passa --sucesso
        n_eval_episodes=N_EVAL_EPISODES,
        eval_freq=eval_freq,
        log_path=str(out_dir),               # escreve evaluations.npz no out-dir
        best_model_save_path=str(out_dir),   # best_model.zip no out-dir
        deterministic=True,
        render=False,
        verbose=1,
        warn=True,
    )
    ckpt_cb = CheckpointCallback(
        save_freq=max(CHECKPOINT_PASSOS // max(1, args.n_envs), 1),
        save_path=str(out_dir / "ckpt"),
        save_vecnormalize=False,             # não há VecNormalize (a obs já sai normalizada do env)
        verbose=1,
    )
    registo_cb = CallbackRegisto(eval_cb, out_dir / ARQUIVO_LOG, painel, env_metrica, curriculo, venv,
                                 seed=args.seed, sucesso=args.sucesso, passos_iniciais=passos_iniciais,
                                 din_cfg=din_cfg)
    return [eval_cb, ckpt_cb, registo_cb], eval_cb


def resolver_checkpoint(texto: str) -> Path:
    """Resolve o `--retomar` (relativo ao cwd) — existe? é um ficheiro? (`.zip` do SB3)."""
    caminho = Path(texto).expanduser()
    if not caminho.is_absolute():
        caminho = Path.cwd() / caminho
    if not caminho.is_file():
        raise FileNotFoundError(f"--retomar: {caminho} não existe (dá o caminho de um best_model.zip "
                                "ou final.zip gravado pelo SB3)")
    return caminho


def criar_modelo(args: argparse.Namespace, venv: SubprocVecEnv,
                 painel: Any) -> tuple[PPO, int]:
    """Cria o PPO NOVO (receita desta peça) ou RETOMA de um checkpoint; devolve `(modelo, passos_iniciais)`.

    Retomar (`--retomar`): `PPO.load` com os hiperparâmetros do CLI e a política CONTINUA a aprender. O que
    o SB3 2.9.0 faz (medido nesta máquina com o `best_model.zip` do seed2, 780 000 passos):
      · os PESOS e o ESTADO DO ADAM são restaurados (ação determinística idêntica à do zip) e
        `num_timesteps` volta com o valor guardado;
      · o ROLLOUT BUFFER NÃO é guardado → é recriado; logo não é uma continuação bit-a-bit;
      · `policy_kwargs` não se podem sobrepor: o SB3 levanta ValueError se diferirem dos guardados (é o
        correto — os pesos só encaixam na arquitetura onde foram treinados), portanto a arquitetura E o
        `log_std_init` vêm do checkpoint, não do `--log-std-init` do CLI;
      · o `set_parameters` do load REPÕE o `lr` do checkpoint no otimizador (medido: 3e-4 apesar de o load
        receber `learning_rate=1e-4`) — por isso o `--lr` e o L2 (`weight_decay`) do CLI são FORÇADOS nos
        `param_groups` depois do load, para o CLI mandar no que manda.
    """
    comuns: dict[str, Any] = {
        "learning_rate": args.lr,
        "n_steps": N_STEPS,
        "batch_size": BATCH_SIZE,   # divide n_steps · n_envs (qualquer n_envs ≥ 1: N_STEPS ≥ BATCH_SIZE)
        "n_epochs": N_EPOCHS,
        "gamma": GAMMA,
        "gae_lambda": GAE_LAMBDA,
        "clip_range": CLIP_RANGE,
        "ent_coef": args.ent_coef,
        "vf_coef": VF_COEF,
        "max_grad_norm": MAX_GRAD_NORM,
        "seed": args.seed,
        "verbose": 0,               # o painel é nosso; sem TensorBoard (tensorboard_log fica None)
        "device": "cpu",
    }
    painel.escrever(
        f"PPO · n_steps={N_STEPS} × n_envs={args.n_envs} = {N_STEPS * args.n_envs} passos/rollout · "
        f"batch={BATCH_SIZE} · n_epochs={N_EPOCHS} · gamma={GAMMA:g} · gae={GAE_LAMBDA:g} · "
        f"clip={CLIP_RANGE:g} · vf={VF_COEF:g} · max_grad_norm={MAX_GRAD_NORM:g}"
    )
    if args.retomar is None:
        real = getattr(args, "planta", "cf2") == "real"
        camadas = list(getattr(args, "camadas", [64, 64]))
        extra_politica = {"n_ator": OBS_ATOR_DIM} if real else {}
        modelo = PPO(
            PoliticaAssimetrica if real else "MlpPolicy",
            venv,
            policy_kwargs={
                **extra_politica,
                "net_arch": {"pi": camadas, "vf": camadas},
                "activation_fn": nn.Tanh,
                "log_std_init": args.log_std_init,   # −0,5: o 0,0 do SB3 explora demasiado na recompensa v2
                # L2 pelo caminho OFICIAL do SB3 2.9.0: o `optimizer_kwargs` do `policy_kwargs` chega ao
                # `ActorCriticPolicy._build` (`optimizer_class(params, lr, **optimizer_kwargs)`), e com o
                # Adam por omissão `weight_decay` é exatamente o L2 (#7978: 1e-4–1e-3).
                "optimizer_kwargs": {"weight_decay": PESO_L2},
            },
            **comuns,
        )
        l2 = float(modelo.policy.optimizer.param_groups[0].get("weight_decay", 0.0))  # verificação do L2
        if l2 == PESO_L2:
            painel.escrever(f"L2 ativo no Adam (weight_decay) = {l2:g} [verificado no otimizador]")
        else:
            painel.escrever(f"[aviso] L2 pedido {PESO_L2:g} mas weight_decay efetivo = {l2:g} "
                            "(o SB3 não aplicou o optimizer_kwargs)")
        return modelo, 0

    caminho = resolver_checkpoint(args.retomar)
    modelo = PPO.load(str(caminho), env=venv, **comuns)   # sem policy_kwargs: o SB3 exige os do checkpoint
    passos_iniciais = int(modelo.num_timesteps)
    # o load repõe o lr (e o weight_decay) do checkpoint: força os do CLI no otimizador e no schedule
    modelo.learning_rate = float(args.lr)
    modelo._setup_lr_schedule()
    for grupo in modelo.policy.optimizer.param_groups:
        grupo["lr"] = float(args.lr)
        grupo["weight_decay"] = PESO_L2
    painel.escrever(
        f"[retomar] {caminho} · {passos_iniciais:,} passos já feitos · --timesteps {args.timesteps:,} "
        f"ADICIONAIS (o learn vai até {passos_iniciais + args.timesteps:,})"
    )
    painel.escrever(
        f"[retomar] pesos e Adam restaurados ({len(modelo.policy.optimizer.state)} tensores de momento); "
        f"rollout buffer NÃO é guardado → continuação, não bit-a-bit; policy_kwargs do checkpoint = "
        f"{modelo.policy_kwargs}; lr={args.lr:g} e L2={PESO_L2:g} FORÇADOS pelo CLI"
    )
    painel.escrever("[retomar] usa um --out-dir NOVO para não escrever por cima do run original "
                    "(o JSONL é truncado e o best_model pode ser substituído)")
    return modelo, passos_iniciais


def treinar(args: argparse.Namespace) -> int:
    """Corre o treino completo e devolve o código de saída (0 = sucesso)."""
    # MLP minúscula com batch pequeno: o paralelismo intra-op do torch só traz overhead (medido nesta
    # máquina com n_envs=4: 1 517 → 1 746 passos/s de treino puro ao fixar 1 thread).
    torch.set_num_threads(1)
    if args.retomar is not None:
        try:
            resolver_checkpoint(args.retomar)          # falha CEDO e com mensagem clara (antes dos envs)
        except FileNotFoundError as erro:
            print(f"erro: {erro}", flush=True)
            return 2
    out_dir = resolver_saida(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ARQUIVO_LOG).unlink(missing_ok=True)  # cada run escreve o seu próprio histórico
    eval_freq = calcular_eval_freq(args.eval_freq, args.timesteps, args.n_envs)
    estagios = (args.vento_max,) if args.sem_curriculo else tuple(args.curriculo_vento)
    curriculo = CurriculoVento(estagios, frac_avanco=args.avanco_frac)
    painel: Any = PainelNulo() if args.sem_painel else Painel(
        total=args.timesteps, titulo=f"PPO hover · seed {args.seed} · {args.n_envs} envs"
    )
    painel.escrever(
        f"treino PPO headless · timesteps={args.timesteps:,} n_envs={args.n_envs} seed={args.seed} "
        f"lr={args.lr:g} ent_coef={args.ent_coef:g} log_std_init={args.log_std_init:g} "
        f"sucesso={args.sucesso:g} eval_freq={eval_freq} (passos do vec) out={out_dir}"
    )
    painel.escrever(descricao_vento(args.sem_curriculo, curriculo))
    painel.escrever(descricao_vento_dinamico(args.vento_dinamico_cfg, curriculo.u_vento))
    if not args.sem_curriculo and getattr(args, "vento_max_explicito", False):
        painel.escrever(f"[AVISO] --vento-max {args.vento_max:g} ignorado com --curriculo-vento: os tetos "
                        "por estágio vêm do --curriculo-vento (use --sem-curriculo para o teto fixo)")
    if args.retomar is not None:
        painel.escrever(f"[retomar] a continuar de {resolver_checkpoint(args.retomar)}")

    din_cfg = config_dinamica(args.vento_dinamico_cfg, curriculo.u_vento)   # u_max = teto do estágio em vigor
    venv = criar_envs_treino(args.n_envs, args.seed, curriculo.u_vento, din_cfg, args=args)
    env_metrica = criar_env_avaliacao(args)
    env_metrica.reset(seed=args.seed + 10_000)  # stream de estados iniciais fixo → métricas comparáveis
    hw_json = gravar_hardware(args, out_dir)
    if hw_json is not None:
        d = hw_json["derivados"]
        painel.escrever(
            f"planta REAL · build '{hw_json['build']}' · {d['massa_total_g']:.0f} g · T/W {d['t_w_cheia']:.2f} · "
            f"pairagem {d['pairagem_v_nominal']['p_total']:.0f} W ({d['pairagem_v_nominal']['g_por_w']:.1f} g/W) · "
            f"autonomia estimada {d['autonomia_min']:.0f} min · ação {args.modo_acao} · "
            f"DR {'DESLIGADA' if args.sem_dr else 'ligada'} · ator vê {OBS_ATOR_DIM} entradas reais "
            f"(crítico assimétrico) · {out_dir / 'hardware.json'}")
    else:
        painel.escrever("planta cf2 · HoverEnv histórico do Crazyflie (observação privilegiada, 16 dims)")
    # O SB3 avisa que o env de TREINO (SubprocVecEnv) e o de AVALIAÇÃO (DummyVecEnv de 1 env) são de tipos
    # diferentes. É intencional e inócuo aqui: sem VecNormalize não há estatísticas para sincronizar.
    warnings.filterwarnings("ignore", message="Training and eval env are not of the same type")

    modelo, passos_iniciais = criar_modelo(args, venv, painel)
    callbacks, eval_cb = construir_callbacks(args, out_dir, eval_freq, painel, env_metrica, curriculo, venv,
                                             passos_iniciais=passos_iniciais, din_cfg=din_cfg)
    t0 = time.perf_counter()
    try:
        # `--timesteps` é o orçamento DESTE run (com --retomar é ADICIONAL ao que veio do checkpoint). Quem
        # soma os passos antigos é o SB3, e só se `reset_num_timesteps=False`: em `_setup_learn` o
        # `reset_num_timesteps=True` (o DEFAULT do `learn`) faz `num_timesteps = 0` e um `total_timesteps`
        # já somado por nós voltaria a treinar o run inteiro de zero (medido: 784 000 passos em vez de 4 000
        # num --retomar); com `False` o SB3 faz `total_timesteps += self.num_timesteps`. Sem retomar o
        # contador já é 0 e o default é o comportamento certo (nada muda em relação a antes).
        modelo.learn(total_timesteps=args.timesteps, callback=callbacks, progress_bar=False,
                     reset_num_timesteps=(passos_iniciais == 0))
        modelo.save(str(out_dir / "final"))          # → final.zip
        ckpt_final = out_dir / "ckpt" / f"rl_model_{modelo.num_timesteps}_steps.zip"
        modelo.save(str(ckpt_final.with_suffix("")))  # garante ≥1 checkpoint mesmo em treinos curtos
    finally:
        painel.parar()
        venv.close()
        env_metrica.close()
        eval_cb.eval_env.close()
    wall = time.perf_counter() - t0

    passos = int(modelo.num_timesteps)
    passos_run = max(0, passos - passos_iniciais)
    sucesso = bool(eval_cb.best_mean_reward >= args.sucesso)
    print(
        f"\nfim · {passos:,} passos acumulados (+{passos_run:,} neste run) em {wall:.1f} s "
        f"({passos_run / max(wall, 1e-9):.0f} passos/s) · "
        f"{len(eval_cb.evaluations_timesteps)} avaliações · melhor retorno médio "
        f"{eval_cb.best_mean_reward:.1f} · sucesso (≥{args.sucesso:g}): {'SIM' if sucesso else 'não'}",
        flush=True,
    )
    print(f"  vento: teto {curriculo.u_vento:g} m/s · estágio {curriculo.estagio + 1}/{curriculo.n_estagios}"
          f" (avanço com frac_xy_z ≥ {curriculo.frac_avanco:g}) · L2 (weight_decay)="
          f"{modelo.policy.optimizer.param_groups[0].get('weight_decay', 0.0):g} · "
          f"log_std_init={args.log_std_init:g}", flush=True)
    print("  vento dinâmico: " + ("DESLIGADO" if args.vento_dinamico_cfg is None else
          f"{args.vento_dinamico_cfg['modo']} (u_max = teto do currículo = {curriculo.u_vento:g} m/s)"),
          flush=True)
    print(f"  {out_dir / 'final.zip'}\n  {out_dir / 'best_model.zip'}\n  {out_dir / 'evaluations.npz'}"
          f"\n  {out_dir / ARQUIVO_LOG}\n  {out_dir / 'ckpt'}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada: `python experiments/09_drone_hover_rl/train.py [opções]`."""
    return treinar(ler_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
