#!/usr/bin/env python3
"""train.py — treino PPO (Stable-Baselines3) HEADLESS do template `lab-padrao`, com currículo e DR.

    uv run --group hover-rl python <exp>/train.py                        # currículo completo, sem janela nenhuma
    uv run --group hover-rl python <exp>/train.py --timesteps 20000 --nome rascunho
    uv run --group hover-rl python <exp>/train.py --retomar out/runs/rascunho/final.zip --timesteps 100000
    uv run --group hover-rl python <exp>/train.py --sem-painel --sem-dr   # linhas simples, sem domain randomization

O que este ficheiro tem (é o padrão de treino do laboratório):
  · PPO do SB3 sobre o `env.py` (`novo_env()`), tudo em CPU e SEM janela (nenhum import de `mujoco.viewer`);
  · CURRÍCULO — fases (alvo mais exigente e vento base maior) aplicadas por callback, recalculando o trim;
  · DR (domain randomization) — vento aleatório por episódio, para a política não decorar ar parado;
  · `--retomar` — continua de um `.zip` (`reset_num_timesteps=False` mantém os contadores do SB3);
  · TELEMETRIA JSONL — `out/runs/<nome>/treino.jsonl` (1 linha por relatório: passos, retorno médio, fase…);
  · checkpoints periódicos + `best_model.zip` (melhor retorno de avaliação) + `final.zip` no fim;
  · painel `rich` OPCIONAL (`--sem-painel` para linhas simples) — nada aqui abre janelas.

Artefactos (é o que o `sim_site.py`/`deploy.py` procuram): `out/runs/<nome>/final.zip`, `best_model.zip`,
`treino.jsonl`, `resumo_treino.json`, `checkpoints/ppo_<passos>.zip`.

ADAPTAR: as FASES do currículo e os pesos da recompensa (`env.py`). O que NÃO muda: telemetria JSONL,
checkpoints + `best_model.zip`, `--retomar` e o treino headless.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]

import env as env_mod
import gymnasium as gym
import numpy as np

RUNS = _AQUI / "out" / "runs"

# ----------------------------------------------------------------------------------------------- currículo
# (passos acumulados em que a fase COMEÇA, alvo em graus, vento base máximo m/s, modo dinâmico de vento)
FASES = [
    (0, 30.0, 0.0, None),
    (40_000, 45.0, 1.5, None),
    (90_000, 60.0, 3.0, {"modo": "rajadas", "u_max": 2.5}),
    (160_000, 60.0, 5.0, {"modo": "frente", "u_max": 4.0, "t_s": 1.5}),
]


def configuracao_padrao() -> dict:
    """Hiperparâmetros do PPO (rede pequena: obs e ações minúsculas — treina em segundos por 10 k passos)."""
    return {"learning_rate": 3e-4, "n_steps": 1024, "batch_size": 256, "n_epochs": 10, "gamma": 0.99,
            "gae_lambda": 0.95, "clip_range": 0.2, "ent_coef": 0.002, "vf_coef": 0.5, "max_grad_norm": 0.5,
            "policy_kwargs": {"net_arch": [64, 64]}, "verbose": 0}


class VentoAleatorio(gym.Wrapper):
    """DR: a cada episódio sorteia um vento base (vel, azimute) e, opcionalmente, um alvo diferente.

    `gymnasium.Wrapper` (e não uma classe solta): o SB3 exige um `gymnasium.Env` de verdade — com uma classe
    só "duck-typed" ele recusa em `_patch_env` com "not a Gymnasium environment". Toda a API PRÓPRIA do env
    (`definir_vento`, `definir_alvo`, `passos_max`…) tem de ser usada em `unwrapped`: o `Wrapper` do gymnasium
    NÃO delega atributos próprios.
    """

    def __init__(self, env, vel_max: float, alvos: tuple[float, ...] = (), freq: int = 1, seed: int = 0) -> None:
        super().__init__(env)
        self.vel_max = float(vel_max)
        self.alvos = tuple(alvos)
        self.freq = max(1, int(freq))
        self.rng = np.random.default_rng(seed)
        self.episodio = 0

    def reset(self, **kwargs):
        self.episodio += 1
        # ⚠ ARMADILHA do gymnasium: `Wrapper.__getattr__` NÃO delega atributos próprios do env (ao contrário do
        # que se esperaria): `Monitor(...).definir_vento` dá AttributeError. Tudo o que é do NOSSO env passa por
        # `unwrapped` — só `reset`/`step` (API do Gymnasium) é que se chamam no wrapper.
        base = self.env.unwrapped
        if self.vel_max > 0 and self.episodio % self.freq == 0:
            base.definir_vento(float(self.rng.uniform(0.0, self.vel_max)), float(self.rng.uniform(0.0, 360.0)), 0.0)
        else:
            base.definir_vento(0.0, 0.0, 0.0)
        if self.alvos and self.episodio % self.freq == 0:
            base.definir_alvo(float(self.rng.choice(self.alvos)))
        return self.env.reset(**kwargs)

    def step(self, acao):
        return self.env.step(acao)


def encontrar_modelo_mais_recente(pasta: Path = RUNS) -> Path | None:
    """`best_model.zip` mais recente em `out/runs/*/`, senão o `final.zip` mais recente (política a usar)."""
    runs = sorted(p for p in pasta.glob("*") if p.is_dir())
    for nome in ("best_model.zip", "final.zip"):
        candidatos = [p / nome for p in runs if (p / nome).exists()]
        if candidatos:
            return max(candidatos, key=lambda p: p.stat().st_mtime)
    return None


def avaliar(modelo, env, episodios: int, seed: int = 10_000) -> dict:
    """Avaliação determinística (sem exploração) num env PRÓPRIO: retorno médio e |erro| médio em graus.

    Usa um env SEPARADO do treino (senão a avaliação deixa o `Monitor` do treino a meio de um episódio e o
    `VecEnv` rebenta com "Tried to step environment that needs reset"). Sem vento e com jitter desligado:
    é uma medição reprodutível, comparável entre rondas.
    """
    retornos, erros, comprimentos = [], [], []
    for i in range(episodios):
        obs, _ = env.reset(seed=seed + i)
        feito = False
        retorno, erro_soma, passos = 0.0, 0.0, 0
        while not feito:
            acao, _ = modelo.predict(obs, deterministic=True)
            obs, r, terminado, truncado, info = env.step(acao)
            retorno += float(r)
            erro_soma += abs(float(info["erro"]))
            passos += 1
            feito = bool(terminado or truncado) or passos >= env.unwrapped.passos_max
        retornos.append(round(retorno, 3))
        erros.append(np.degrees(erro_soma / max(passos, 1)))
        comprimentos.append(passos)
    env.reset(seed=seed)          # deixa o env de avaliação num estado "pronto" (higiene entre chamadas)
    return {"retorno_medio": float(np.mean(retornos)), "erro_medio_graus": float(np.mean(erros)),
            "comprimento_medio": float(np.mean(comprimentos)), "retornos": retornos}


class Painel:
    """Painel `rich` OPCIONAL: barra de progresso + linha de estado. Sem `rich`, degrada para texto simples."""

    def __init__(self, total: int, ligado: bool) -> None:
        self.total = int(total)
        self.progresso = None
        self.tarefa = None
        if not ligado:
            return
        try:
            from rich.progress import (
                BarColumn,
                Progress,
                TextColumn,
                TimeElapsedColumn,
                TimeRemainingColumn,
            )
        except ImportError:
            print("[treino] aviso: rich não instalado — sigo com linhas de texto", flush=True)
            return
        self.progresso = Progress(TextColumn("[bold cyan]{task.description}"), BarColumn(),
                                  TextColumn("{task.completed}/{task.total}"), TimeElapsedColumn(),
                                  TextColumn("·"), TimeRemainingColumn())
        self.progresso.start()
        self.tarefa = self.progresso.add_task("PPO", total=self.total)

    def passo(self, passos: int, descricao: str) -> None:
        if self.progresso is not None and self.tarefa is not None:
            self.progresso.update(self.tarefa, completed=min(passos, self.total), description=descricao)

    def fechar(self) -> None:
        if self.progresso is not None:
            self.progresso.stop()


def treinar(args) -> int:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.monitor import Monitor

    pasta = RUNS / args.nome
    (pasta / "checkpoints").mkdir(parents=True, exist_ok=True)
    env = Monitor(env_mod.novo_env(theta_alvo_graus=args.alvo, seed=args.seed))
    base = env.unwrapped            # ⚠ o gym.Wrapper só delega LEITURAS: escrever tem de ser no env de dentro
    # O alvo só é sorteado (DR de alvo) quando há currículo E DR; sem eles o alvo é o de `--alvo`.
    alvos_dr = () if (args.sem_curriculo or args.sem_dr) else (30.0, 45.0, 60.0)
    dr = VentoAleatorio(env, vel_max=0.0 if args.sem_dr else args.vento_dr, alvos=alvos_dr, seed=args.seed + 7)

    fases = FASES if not args.sem_curriculo else [(0, args.alvo, 0.0 if args.sem_dr else args.vento_dr, None)]
    cfg = configuracao_padrao() | {"seed": args.seed, "device": "cpu"}

    if args.retomar:
        print(f"[treino] a retomar de {args.retomar}", flush=True)
        reutilizaveis = {k: v for k, v in cfg.items() if k in ("learning_rate", "n_steps", "batch_size",
                                                              "n_epochs", "gamma", "gae_lambda", "clip_range",
                                                              "ent_coef", "vf_coef", "max_grad_norm", "verbose")}
        modelo = PPO.load(args.retomar, env=dr, device="cpu", **reutilizaveis)
        passos_iniciais = int(modelo.num_timesteps)
    else:
        modelo = PPO("MlpPolicy", dr, **cfg)
        passos_iniciais = 0

    telemetria = (pasta / "treino.jsonl").open("a", encoding="utf-8")
    melhor = {"retorno_medio": -np.inf, "erro_medio_graus": float("nan")}
    inicio = time.perf_counter()
    painel = Painel(passos_iniciais + args.timesteps, ligado=not args.sem_painel)

    class Relator(BaseCallback):
        """Relatórios periódicos: currículo, telemetria JSONL, avaliação, `best_model.zip` e checkpoints."""

        def __init__(self) -> None:
            super().__init__()
            self.t0 = time.perf_counter()
            self.fase = -1
            self.proximo_relatorio = int(args.relatorio_cada)
            self.proxima_avaliacao = int(args.avaliar_cada) if args.avaliar_cada else None
            self.proximo_checkpoint = int(args.salvar_cada) if args.salvar_cada else None
            self.env_aval = None      # env PRÓPRIO da avaliação (criado na 1.ª vez, isolado do treino)

        # ------------------------------------------------------------------ currículo
        def _aplica_fase(self, indice: int) -> None:
            """Muda alvo + vento dinâmico da fase (recalcula o trim) e anuncia a transição."""
            _limiar, alvo, vento_max, dinamico = fases[indice]
            base.definir_alvo(alvo)
            base.vento = np.zeros(3)
            base.vento_dinamico = dict(dinamico) if dinamico else None
            dr.vel_max = float(vento_max)
            print(f"[treino] fase {indice + 1}/{len(fases)}: alvo {alvo:.0f}° · vento base ≤ {vento_max:.1f} m/s · "
                  f"dinâmico {dinamico or '—'} (trim {base.trim:.2f} N·m)", flush=True)

        def _fase_atual(self) -> int:
            acumulado = passos_iniciais + int(self.num_timesteps)
            indice = 0
            for i, (limiar, *_resto) in enumerate(fases):
                if acumulado >= limiar:
                    indice = i
            return indice

        # ------------------------------------------------------------------ ciclo
        def _on_step(self) -> bool:
            if self._fase_atual() != self.fase:
                self.fase = self._fase_atual()
                self._aplica_fase(self.fase)
            passos = passos_iniciais + int(self.num_timesteps)
            if passos >= self.proximo_relatorio:
                self._relatorio(passos)
                self.proximo_relatorio = passos + int(args.relatorio_cada)
            return True

        def _relatorio(self, passos: int) -> None:
            """Uma linha de telemetria + (quando toca) avaliação, `best_model.zip` e checkpoint."""
            linha: dict = {"passos": passos, "fase": self.fase + 1, "alvo_graus": round(float(np.degrees(base.theta_alvo)), 2),
                           "vento_max": float(dr.vel_max), "tempo_s": round(time.perf_counter() - self.t0, 2),
                           "fps": round(float(self.num_timesteps) / max(1e-9, time.perf_counter() - self.t0), 1)}
            # ⚠ Duas armadilhas aqui: (1) o `VecEnv.get_attr` NÃO chega ao `Monitor` através do meu wrapper
            # (o `get_wrapper_attr` do gymnasium não atravessa wrappers aninhados com atributos próprios);
            # (2) esta versão do SB3 não tem `Monitor.episode` — os episódios ficam em `episode_returns` /
            # `episode_lengths` (ou nos getters `get_episode_rewards()`/`get_episode_lengths()`).
            retornos = list(env.get_episode_rewards())[-20:]
            comprimentos = list(env.get_episode_lengths())[-20:]
            if retornos:
                linha["retorno_medio"] = round(float(np.mean(retornos)), 3)
            if comprimentos:
                linha["comprimento_medio"] = round(float(np.mean(comprimentos)), 1)
            if self.proxima_avaliacao is not None and passos >= self.proxima_avaliacao:
                self.proxima_avaliacao = passos + int(args.avaliar_cada)
                self.env_aval = self.env_aval or Monitor(env_mod.novo_env(theta_alvo_graus=args.alvo, jitter=False,
                                                                         seed=args.seed + 11))
                self.env_aval.unwrapped.definir_alvo(float(np.degrees(base.theta_alvo)))   # segue o currículo
                self.env_aval.unwrapped.definir_vento(0.0, 0.0, 0.0)                       # avaliação sem vento
                aval = avaliar(self.model, self.env_aval, episodios=args.episodios_avaliacao, seed=10_000 + passos)
                linha |= {k: round(v, 4) for k, v in aval.items() if k != "retornos"}
                if aval["retorno_medio"] > melhor["retorno_medio"]:
                    melhor.update({"retorno_medio": aval["retorno_medio"], "erro_medio_graus": aval["erro_medio_graus"]})
                    self.model.save(pasta / "best_model.zip")
                    linha["melhor_retorno"] = round(aval["retorno_medio"], 3)
                    print(f"[treino] novo best_model.zip: retorno {aval['retorno_medio']:.2f} · "
                          f"erro médio {aval['erro_medio_graus']:.3f}°", flush=True)
            if self.proximo_checkpoint is not None and passos >= self.proximo_checkpoint:
                self.proximo_checkpoint = passos + int(args.salvar_cada)
                self.model.save(pasta / "checkpoints" / f"ppo_{passos:08d}.zip")
            telemetria.write(json.dumps(linha, ensure_ascii=False) + "\n")
            telemetria.flush()
            resumo = " · ".join(f"{k}={v}" for k, v in linha.items() if k != "tempo_s")
            print(f"[treino] {resumo}", flush=True)
            painel.passo(passos, f"PPO fase {self.fase + 1}/{len(fases)} · {linha.get('retorno_medio', '—')}")

    total = passos_iniciais + int(args.timesteps)
    print(f"[treino] PPO até {total} passos · {pasta} · obs {env_mod.N_OBS} → ação {env_mod.N_ACT} · "
          f"{len(fases)} fases · DR {'ON' if not args.sem_dr else 'OFF'}", flush=True)
    try:
        modelo.learn(total_timesteps=total, callback=Relator(), reset_num_timesteps=not args.retomar,
                     progress_bar=False)
    except KeyboardInterrupt:
        print("[treino] interrompido pelo utilizador: guardo o que existe", flush=True)
    painel.fechar()
    env_aval = Monitor(env_mod.novo_env(theta_alvo_graus=float(np.degrees(base.theta_alvo)), jitter=False,
                                        seed=args.seed + 12))
    env_aval.unwrapped.definir_vento(0.0, 0.0, 0.0)
    aval_final = avaliar(modelo, env_aval, episodios=args.episodios_avaliacao, seed=20_000)
    modelo.save(pasta / "final.zip")
    if aval_final["retorno_medio"] > melhor["retorno_medio"]:
        melhor.update({"retorno_medio": aval_final["retorno_medio"], "erro_medio_graus": aval_final["erro_medio_graus"]})
        modelo.save(pasta / "best_model.zip")
    resumo = {"nome": args.nome, "passos_totais": int(modelo.num_timesteps), "fases": len(fases),
              "retorno_final": round(aval_final["retorno_medio"], 4),
              "erro_medio_graus_final": round(aval_final["erro_medio_graus"], 4),
              "melhor_retorno": round(float(melhor["retorno_medio"]), 4) if np.isfinite(melhor["retorno_medio"]) else None,
              "parede_s": round(time.perf_counter() - inicio, 2), "modelo": str(pasta / "final.zip"),
              "melhor_modelo": str(pasta / "best_model.zip")}
    (pasta / "resumo_treino.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    telemetria.close()
    print(f"[treino] fim: {resumo['passos_totais']} passos em {resumo['parede_s']:.1f} s · "
          f"retorno final {resumo['retorno_final']} · erro médio {resumo['erro_medio_graus_final']}°")
    print(f"[treino] artefactos: {pasta}/final.zip · best_model.zip · treino.jsonl · resumo_treino.json")
    print(f"[treino] próximo passo:  uv run --group hover-rl python {_AQUI.name}/sim_site.py "
          f"--model {pasta.relative_to(_AQUI)}/best_model.zip")
    return 0


def analisar_argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Treino PPO do template lab-padrao (headless, com currículo e DR).",
                               formatter_class=argparse.RawDescriptionHelpFormatter,
                               epilog="Artefactos: out/runs/<nome>/{final.zip,best_model.zip,treino.jsonl,checkpoints/}")
    p.add_argument("--timesteps", type=int, default=200_000, help="passos de treino a somar (padrão 200 000)")
    p.add_argument("--nome", default="base", help="nome da ronda (pasta em out/runs/)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--alvo", type=float, default=env_mod.ALVO_GRAUS, help="ângulo-alvo quando o currículo está desligado")
    p.add_argument("--retomar", type=Path, default=None, metavar="CAMINHO.zip", help="continua de um modelo guardado")
    p.add_argument("--sem-curriculo", action="store_true", help="treina logo no alvo final (uma fase)")
    p.add_argument("--sem-dr", action="store_true", help="desliga o vento aleatório por episódio (sem DR)")
    p.add_argument("--vento-dr", type=float, default=3.0, metavar="V", help="vento base máximo do DR (m/s)")
    p.add_argument("--relatorio-cada", type=int, default=2_000, help="passos entre relatórios/telemetria")
    p.add_argument("--salvar-cada", type=int, default=20_000, help="passos entre checkpoints (0 = nunca)")
    p.add_argument("--avaliar-cada", type=int, default=20_000, help="passos entre avaliações (0 = nunca)")
    p.add_argument("--episodios-avaliacao", type=int, default=8, help="episódios por avaliação")
    p.add_argument("--sem-painel", action="store_true", help="sem painel rich (só linhas de texto)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = analisar_argumentos(argv)
    if args.timesteps <= 0:
        print("Erro: --timesteps tem de ser > 0 — Solução: ex. --timesteps 20000", file=sys.stderr)
        return 2
    return treinar(args)


if __name__ == "__main__":
    sys.exit(main())
