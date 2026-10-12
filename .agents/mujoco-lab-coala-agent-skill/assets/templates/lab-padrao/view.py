#!/usr/bin/env python3
"""view.py — vista 3D COM HUD (bancada de depuração) + modo `--sem-janela` (validação sem janelas).

Irmão "de bancada" do `sim_view.py`:

  · `view.py`            → janela COM HUD (texto + 2 gráficos: θ(t) com a linha do alvo e erro(t)), teclado e
                          REPL no terminal. Serve para OLHAR enquanto se depura. NÃO é o padrão do dono: o
                          padrão (`sim_view.py` + `sim_site.py`) tem a janela 100 % limpa e tudo no site.
  · `view.py --sem-janela` → corre o mesmo controlador SEM abrir janela nenhuma (nenhum import de
                          `mujoco.viewer`), imprime a tabela de desempenho e escreve `out/vista_resumo.json`.

    uv run --group hover-rl python <exp>/view.py                        # janela com HUD (ESPAÇO pausa · R reinicia · Q sai)
    uv run --group hover-rl python <exp>/view.py --sem-janela --segundos 5 --vento 3
    uv run --group hover-rl python <exp>/view.py --model out/runs/base/best_model.zip

Teclado: ESPAÇO pausa/retoma · R reinicia · V vento ±1 m/s · X vento = 0 · A/Z alvo ±10° · Q/Esc fecha.
REPL (com janela, no terminal): `vento 3 45` · `alvo 60` · `reset` · `politica CAMINHO.zip` · `sair`.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
sys.path[:0] = [str(_RAIZ), str(_AQUI)]


import env as env_mod
import mujoco
import numpy as np

AQUI = _AQUI
FONTE_HUD = mujoco.mjtFont.mjFONT_NORMAL        # 1.º arg de `set_texts` é um mjtFont (NÃO uma escala)
GRID_HUD = mujoco.mjtGridPos.mjGRID_TOPLEFT
MARGEM, FIG_LARG, FIG_ALT = 10, 420, 140
JANELA_S = 6.0                                  # segundos visíveis nas curvas do HUD


# ----------------------------------------------------------------------------------------------- controlo
def acao_do_controlador(env, politica) -> np.ndarray:
    """Ação a aplicar: a da política (se houver) ou a ação nula (= `ctrl = τ_trim`, o equilíbrio no alvo)."""
    if politica is None:
        return np.zeros(env_mod.N_ACT, dtype=np.float32)
    acao, _ = politica.predict(env.observacao(), deterministic=True)
    return np.asarray(acao, dtype=np.float32).reshape(-1)[: env_mod.N_ACT]


def carregar_politica(caminho: Path | None):
    """Carrega a política PPO (SB3) ou devolve `None`. Import local: o modo `--sem-janela` não exige SB3."""
    if caminho is None:
        return None
    from stable_baselines3 import PPO

    return PPO.load(caminho, device="cpu")


def sem_janela(env, politica, args) -> int:
    """Modo de VALIDAÇÃO: nenhuma janela, nenhum import de `mujoco.viewer` — física, métricas e JSON."""
    linhas = []
    info: dict = {}
    for ep in range(1, args.episodios + 1):
        env.reset(seed=args.seed + ep)
        env.definir_alvo(args.alvo)
        env.definir_vento(args.vento, args.vento_azimute, 0.0)
        retorno, erro_soma, passos, fim = 0.0, 0.0, 0, False
        while not fim and passos < env.passos_max and (args.segundos <= 0 or env.data.time < args.segundos):
            _obs, r, terminado, truncado, info = env.step(acao_do_controlador(env, politica))
            retorno += float(r)
            erro_soma += abs(float(info["erro"]))
            passos += 1
            fim = bool(terminado or truncado)
        linhas.append({"ep": ep, "passos": passos, "retorno": round(retorno, 4),
                       "t_s": round(float(env.data.time), 4),
                       "theta_graus": round(float(np.degrees(info["theta"])), 4),
                       "erro_graus": round(float(np.degrees(info["erro"])), 4),
                       "erro_medio_graus": round(float(np.degrees(erro_soma / max(passos, 1))), 4),
                       "ctrl_Nm": round(float(info["ctrl"]), 4), "vento_vel": round(float(info["vento_vel"]), 3),
                       "terminou": bool(terminado and passos < env.passos_max), "nan_detetados": env.nan_detetados})
        print(f"[vista] ep {ep}: {passos} passos · retorno {retorno:+.3f} · erro médio "
              f"{linhas[-1]['erro_medio_graus']:.3f}° · θ={np.degrees(info['theta']):+.2f}° "
              f"(alvo {args.alvo:.1f}°, vento {linhas[-1]['vento_vel']:.2f} m/s)", flush=True)
    resumo = {"politica": str(args.model) if args.model else "ação nula (ctrl = τ_trim)", "alvo_graus": args.alvo,
              "vento_m_s": args.vento, "episodios": linhas,
              "erro_medio_graus": round(float(np.mean([x["erro_medio_graus"] for x in linhas])), 4),
              "retorno_medio": round(float(np.mean([x["retorno"] for x in linhas])), 4), "sem_janela": True,
              "nota": "modo sem janela: nenhum import de mujoco.viewer/glfw (validação em CI/agente)"}
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "vista_resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[vista] resumo: {saida / 'vista_resumo.json'}")
    return 0


# ----------------------------------------------------------------------------------------------- HUD (janela)
class Serie:
    """Uma linha do `MjvFigure` com o ringbuffer do PRÓPRIO (mjMAXLINEPNT pontos): ao encher, desliza."""

    def __init__(self, fig: mujoco.MjvFigure, linha: int, nome: str, cor) -> None:
        self.fig, self.linha = fig, linha
        fig.linename[linha] = nome
        fig.linergb[linha] = cor
        fig.linepnt[linha] = 0
        self.vazio = True

    def acrescentar(self, x: float, y: float) -> None:
        """Junta o ponto (x, y) — `linedata` guarda pares (x, y) intercalados."""
        n = int(self.fig.linepnt[self.linha])
        if n >= mujoco.mjMAXLINEPNT:
            dados = self.fig.linedata[self.linha]
            dados[:-2] = dados[2:].copy()
            n = mujoco.mjMAXLINEPNT - 1
        self.fig.linedata[self.linha, 2 * n] = x
        self.fig.linedata[self.linha, 2 * n + 1] = y
        self.fig.linepnt[self.linha] = n + 1

    def definir(self, pontos) -> None:
        """Substitui a linha por uma sequência curta e FIXA de pontos (linhas de referência: alvo e zero)."""
        self.fig.linepnt[self.linha] = len(pontos)
        for i, (x, y) in enumerate(pontos):
            self.fig.linedata[self.linha, 2 * i] = x
            self.fig.linedata[self.linha, 2 * i + 1] = y

    def limpar(self) -> None:
        self.fig.linepnt[self.linha] = 0


def nova_figura(titulo: str, y0: float, y1: float) -> mujoco.MjvFigure:
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


class HUD:
    """HUD de bancada: painel de texto + 2 figuras (θ(t) com o alvo e erro(t) com o zero)."""

    def __init__(self, env, politica_nome: str) -> None:
        self.env = env
        self.politica_nome = politica_nome
        self.fig_theta = nova_figura("theta (graus)", 0.0, 90.0)
        self.fig_erro = nova_figura("erro (graus)", -45.0, 45.0)
        self.s_theta = Serie(self.fig_theta, 0, "theta", (0.96, 0.64, 0.29))
        self.s_alvo = Serie(self.fig_theta, 1, "alvo", (0.49, 0.83, 0.99))
        self.s_erro = Serie(self.fig_erro, 0, "erro", (0.55, 0.9, 0.62))
        self.s_zero = Serie(self.fig_erro, 1, "zero", (0.49, 0.83, 0.99))
        self.t_max = 0.0

    def amostra(self) -> None:
        """Uma amostra nas curvas e reajuste das janelas (x = últimos JANELA_S segundos)."""
        env = self.env
        t, theta, erro = float(env.data.time), float(np.degrees(env.theta)), float(np.degrees(env.erro))
        self.t_max = max(self.t_max, t)
        self.s_theta.acrescentar(t, theta)
        self.s_erro.acrescentar(t, erro)
        x0, x1 = max(0.0, t - JANELA_S), max(JANELA_S, t)
        for fig in (self.fig_theta, self.fig_erro):
            fig.range[0][:] = (x0, x1)
        alvo_graus = float(np.degrees(self.env.theta_alvo))
        self.fig_theta.range[1][:] = (-10.0, max(90.0, 1.15 * abs(alvo_graus)))
        self.fig_erro.range[1][:] = (-45.0, 45.0)
        self.s_alvo.definir(((x0, np.degrees(env.theta_alvo)), (x1, np.degrees(env.theta_alvo))))
        self.s_zero.definir(((x0, 0.0), (x1, 0.0)))

    def limpar(self) -> None:
        for serie in (self.s_theta, self.s_alvo, self.s_erro, self.s_zero):
            serie.limpar()

    def textos(self) -> str:
        """Painel multi-linha (`set_texts` aceita `\\n`) — uma única entrada em mjGRID_TOPLEFT."""
        env = self.env
        vel, azim = env.vento_polar()
        return "\n".join([
            f"t {env.data.time:6.2f} s · ep {env.episodios} · passo {env.passos}",
            f"theta {np.degrees(env.theta):+7.2f}° · alvo {np.degrees(env.theta_alvo):+7.2f}° · erro {np.degrees(env.erro):+6.2f}°",
            f"omega {env.omega:+7.3f} rad/s · ctrl {float(np.asarray(env.data.ctrl)[0]):+7.3f} N·m · trim {env.trim:+7.3f}",
            f"vento {vel:5.2f} m/s @ {azim:5.1f}° · retorno {env.retorno:+8.2f}",
            f"política: {self.politica_nome}",
        ])

    def rects(self, viewport):
        """Rectângulos das 2 figuras QUE CABEM no viewport (coluna à direita, empilhadas de baixo para cima)."""
        if viewport.height < 2 * MARGEM + 60:
            return []
        largura = min(FIG_LARG, max(160, viewport.width // 3))
        altura = min(FIG_ALT, max(60, (viewport.height - 3 * MARGEM) // 2))
        rects = []
        for i, fig in enumerate((self.fig_erro, self.fig_theta)):     # erro em baixo, theta por cima
            topo = MARGEM + i * (altura + MARGEM)
            rects.append((mujoco.MjrRect(max(0, viewport.width - largura - MARGEM),
                                         max(0, min(topo, viewport.height - altura - MARGEM)), largura, altura), fig))
        return rects


class Teclado:
    """Teclado da bancada (chamado na thread do GLFW): só mexe em FLAGS — quem aplica é o ciclo principal."""

    def __init__(self, env) -> None:
        self.env = env
        self.pausado = False
        self.reiniciar = False
        self.fechar = False
        self.pedidos: list[tuple[str, float, float]] = []

    def ao_teclar(self, codigo: int) -> None:
        c = chr(codigo) if 0 <= codigo < 0x110000 else ""
        vel, azim = self.env.vento_polar()
        if c in ("Q", "q") or codigo == 256:
            self.fechar = True
        elif codigo == 32:
            self.pausado = not self.pausado
        elif c in ("R", "r"):
            self.reiniciar = True
        elif c in ("V", "v"):
            self.pedidos.append(("vento", 0.0 if vel >= 5.0 else min(5.0, vel + 1.0), azim))
        elif c in ("X", "x"):
            self.pedidos.append(("vento", 0.0, azim))
        elif c in ("A", "a"):
            self.pedidos.append(("alvo", np.degrees(self.env.theta_alvo) + 10.0, 0.0))
        elif c in ("Z", "z"):
            self.pedidos.append(("alvo", max(0.0, np.degrees(self.env.theta_alvo) - 10.0), 0.0))

    def aplicar(self) -> None:
        """Aplica os pedidos do teclado/REPL no ciclo principal (nunca de dentro do callback)."""
        while self.pedidos:
            ordem, a, b = self.pedidos.pop(0)
            if ordem == "vento":
                self.env.definir_vento(a, b, 0.0)
                print(f"[vista] vento = {a:.1f} m/s @ {b:.0f}°", flush=True)
            elif ordem == "alvo":
                self.env.definir_alvo(a)
                print(f"[vista] alvo = {a:.1f}° (trim {self.env.trim:.3f} N·m)", flush=True)


class Repl:
    """REPL simples no terminal (thread daemon): `vento V AZ` · `alvo G` · `reset` · `sair`."""

    def __init__(self, teclado: Teclado) -> None:
        self.teclado = teclado
        self.parar = False

    def arrancar(self) -> None:
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        while not self.parar:
            try:
                linha = input()
            except (EOFError, KeyboardInterrupt):
                self.teclado.fechar = True
                return
            partes = linha.split()
            if not partes:
                continue
            ordem = partes[0].lower()
            try:
                if ordem in ("sair", "q", "quit"):
                    self.teclado.fechar = True
                    return
                if ordem == "reset":
                    self.teclado.reiniciar = True
                elif ordem == "vento" and len(partes) >= 2:
                    self.teclado.pedidos.append(("vento", float(partes[1]), float(partes[2]) if len(partes) > 2 else 0.0))
                elif ordem == "alvo" and len(partes) >= 2:
                    self.teclado.pedidos.append(("alvo", float(partes[1]), 0.0))
                else:
                    print("[vista] comandos: vento V [AZ] · alvo G · reset · sair", flush=True)
            except ValueError:
                print("[vista] valor inválido (usa números: `vento 3 45`)", flush=True)


def com_janela(env, politica, args) -> int:
    """Janela (launch_passive) com HUD, teclado e REPL. Aqui a física corre a tempo real (1 passo de decisão)."""
    import mujoco.viewer as mjviewer

    teclas = Teclado(env)
    hud = HUD(env, str(args.model) if args.model else "ação nula (ctrl = τ_trim)")
    env.reset(seed=args.seed)
    env.definir_alvo(args.alvo)
    env.definir_vento(args.vento, args.vento_azimute, 0.0)
    print("[vista] ESPAÇO pausa · R reinicia · V vento ±1 · X vento=0 · A/Z alvo ±10° · Q sai · "
          "REPL: `vento 3 45` · `alvo 60` · `reset` · `sair`", flush=True)
    Repl(teclas).arrancar()
    with mjviewer.launch_passive(env.model, env.data, key_callback=teclas.ao_teclar) as viewer:
        t0 = time.perf_counter()
        proximo_log = 0.0
        while viewer.is_running() and not teclas.fechar:
            inicio = time.perf_counter()
            teclas.aplicar()
            if teclas.reiniciar:
                teclas.reiniciar = False
                env.reset(seed=args.seed)
                hud.limpar()
            if not teclas.pausado:
                env.step(acao_do_controlador(env, politica))
                hud.amostra()
            with viewer.lock():
                viewer.set_texts([(FONTE_HUD, GRID_HUD, hud.textos(), "")])
                viewer.set_figures(hud.rects(viewer.viewport) if viewer.viewport is not None else [])
                viewer.sync()
            if env.data.time >= proximo_log:
                proximo_log = env.data.time + 1.0
                print(f"[vista] t={env.data.time:6.2f}s θ={np.degrees(env.theta):+7.2f}° "
                      f"erro={np.degrees(env.erro):+6.2f}° vento={env.vento_polar()[0]:.2f} m/s", flush=True)
            if args.segundos > 0 and (time.perf_counter() - t0) > args.segundos:
                print(f"[vista] --segundos {args.segundos} atingido: fecho", flush=True)
                break
            restante = env.model.opt.timestep * env.decimacao - (time.perf_counter() - inicio)
            if restante > 0:
                time.sleep(restante)
    return 0


def analisar_argumentos(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Vista 3D do template lab-padrao: HUD de bancada ou --sem-janela.",
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="Padrão do laboratório (janela limpa + site): use `sim_site.py`.")
    p.add_argument("--model", type=Path, default=None, metavar="CAMINHO.zip", help="política PPO a pilotar")
    p.add_argument("--sem-janela", action="store_true", help="NÃO abre janela: corre e escreve out/vista_resumo.json")
    p.add_argument("--segundos", type=float, default=0.0, metavar="S", help="fecha ao fim de S s de simulação (0 = sem limite)")
    p.add_argument("--episodios", type=int, default=2, help="episódios do modo --sem-janela")
    p.add_argument("--alvo", type=float, default=env_mod.ALVO_GRAUS, help="ângulo-alvo em graus")
    p.add_argument("--vento", type=float, default=0.0, help="vento em m/s (0–5)")
    p.add_argument("--vento-azimute", type=float, default=0.0, help="azimute do vento em graus")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--saida", type=Path, default=AQUI / "out", help="pasta de saída do resumo")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = analisar_argumentos(argv)
    env = env_mod.novo_env(theta_alvo_graus=args.alvo, seed=args.seed)
    politica = carregar_politica(args.model)
    if args.sem_janela:
        return sem_janela(env, politica, args)
    return com_janela(env, politica, args)


if __name__ == "__main__":
    sys.exit(main())
