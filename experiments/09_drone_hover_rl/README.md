# 09 · Crazyflie 2 (Bitcraze) — hover a 1 m por RL (PPO → ONNX → deploy)

Política de **aprendizagem por reforço** que faz o quadricóptero **Crazyflie 2** da Bitcraze subir do
chão e estabilizar a **1 m**. Usa o modelo **pronto** do
[mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/main/bitcraze_crazyflie_2)
vendorizado em `models/bitcraze_crazyflie_2/` (MIT, **intocado**) com a camada de sensores/controles
`lab/crazyflie.py`. Aqui junta-se tudo o que um projeto do laboratório precisa: **ambiente Gymnasium**,
**treino PPO**, **UI web local**, **viewer com HUD da rede** e o **caminho de deploy** (ONNX →
validação numérica → benchmark → multi-IA).

O simulador é **sempre físico**: o drone arranca **pousado no chão, com os motores desligados**, e sobe
por empuxo comandado — sem teleporte, sem cinemática, sem corpo congelado. O `reset` larga-o a 1 dm do
chão (keyframe `hover` do lab) e deixa a **física** assentá-lo antes do episódio começar.

**Estado atual (v2b, 2026-10-08):** depois da primeira campanha (hover simples), o dono pediu mais:
o drone **para de girar**, fica **preso em (x, y, z) = (0, 0, 1) m com a orientação fixa** (yaw = 0) e
**corrige sob vento** — vento esse que é escolhido **pela interface** (força + direção). Isso mudou a
recompensa (`v2b`), acrescentou vento físico ao ambiente e um currículo de *domain randomization* ao
treino. Resumo em [Vento e orientação fixa](#vento-e-orientação-fixa-v2b) e
[Resultados v2b](#resultados-v2b-verificado).

- `env.py` — o **ambiente** (contrato que as outras peças importam).
- `train.py` · `view.py` · `dashboard.py` · `net_probe.py` · `deploy.py` — treino, visualização, UI, sonda
  da rede e deploy.
- `run.py` — validação do ambiente por **fórmulas fechadas**, 146/146 checagens, exit 0/1.
- `helices_render.py` — prova **visual** (offscreen/EGL) da animação das hélices: 2 imagens em `out/`.

## COCKPIT (contrato r13, 2026-10-12) — pilotar num ecrã só, vento de 3 botões, seguir a bola

Pedido do dono (2026-10-12): *«está tudo confuso; quero algo que não tenha scroll, eu tenha sempre a visão
primeira pessoa ou terceira, e chamo os controles como janelas que posso abrir»*, *«o modo de controlar já
vem ativado»*, *«não quero opções, quero o melhor»*, vento com *«ligar, definir a intensidade e a
aleatoriedade»*, um modo em que *«a bola se movimenta aleatoriamente»* e o drone a mantém centrada na câmara,
e treino sem interface / reprodução na interface. O contrato completo está no `INTERFACE.md` §0.

```bash
# REPRODUZIR — o cockpit (um comando; abre o site, sem janela nativa; voa o controlador que ganhou na medição)
uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py
#   --com-janela  abre também a janela nativa do MuJoCo · --controlador rl|classico  só para medir/testar

# TREINAR / AFINAR / MEDIR — sem interface (headless)
uv run --group hover-rl python experiments/09_drone_hover_rl/treinar_bola.py                 # afina os ganhos do seguidor da bola
uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_bola.py                 # bola: lei antiga × nova × tracker de IA
uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_vento.py                # vento: cascata nova × fase 1 × política RL
uv run --group hover-rl python experiments/09_drone_hover_rl/train.py --planta real ...      # PPO (ver «Como correr»)
uv run --group hover-rl python experiments/09_drone_hover_rl/bench_treino.py tudo            # o treino está otimizado? mede e prova
uv run --group hover-rl python experiments/09_drone_hover_rl/ab_treino.py --help             # A/B de hiperparâmetros (mesmas sementes)

# PROVAR
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_cockpit.py                # 5 secções + 7 mutações
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_bola.py                   # 38 checagens + 7 mutações
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_vento_classico.py         # 35 checagens + 5 mutações
(cd experiments/09_drone_hover_rl/site && npm run build && npm run test:cockpit)             # 175 verificações + 9 mutações
```

**O ecrã** — a vista (câmara de bordo ou 3.ª pessoa, `F` troca; a outra fica na miniatura) é o fundo
permanente a 100 % do viewport; por cima, um HUD a 50 Hz (estado em linguagem de voo, rumo, velocidade,
altitude, bateria, vento, teclas premidas, retículo da bola); em baixo, uma doca de 8 ícones com nome que
abrem janelas flutuantes (Voo · Bola · Vento · Sensores · Energia · Gráficos · Sistema · Ajuda) e o REINICIAR
de manter premido. Teclas sempre ativas: `WASD` + `QE` (relativas ao nariz), `ZXC` (rodar / fixar rumo), `B`
seguir a bola, `V` vento, `F` vista, `R` (manter) reiniciar, `1`–`8` janelas, `Esc` fecha.

| medido a 1920×1080 (Chromium) | página anterior | cockpit r13 |
|---|---|---|
| altura da página · scroll | 4784 px · 4,4 ecrãs | 1080 px · **sem scroll** (também a 1366×768 e 1280×720) |
| imagem da câmara | a 2929 px do topo | **o ecrã inteiro**, sempre |
| botões · palavras à vista | 51 · 2223 | **12 · 83** (o resto abre-se a pedido) |
| vento | 18 botões + 8 campos, 5 modos | **2 interruptores + 2 sliders** (ligar · intensidade · aleatoriedade · direção) |
| até a tecla W fazer efeito | «ARMAR CONTROLO» + tecla | **a tecla** (voo ativo desde o arranque) |
| quem pilota | seletor RL / Clássico | **sem seletor**: `--controlador auto` = o que ganhou na medição |
| avaliação `uxui-evaluator` | 29/100 «poor» | **84/100 «good»** (1 aviso + 3 sugestões na primeira entrega; **88/100** depois de corrigido o aviso dos ecrãs pequenos — `pesquisas/ux-cockpit-avaliacao-depois.json`) |

**Desempenho medido com a máquina livre** (2026-10-12, RTX 4070 Laptop + i9-14900HX, browser aberto a
1920×1080, tudo fechado):

| o quê | valor |
|---|---|
| simulação | **0,999× do tempo real** (física a 500 Hz, decisão a 50 Hz) |
| HUD (Server-Sent Events) | **50,0 amostras/s** · intervalo p50 19,9 ms, p99 41,9 ms |
| stream da câmara de bordo · da 3.ª pessoa | **49,7 fps · 49,6 fps**, os dois a 1920×1080 |
| pintura do browser · heap de JS | 60 fps · 5 MB |
| tecla → keycap aceso | 12–15 ms (um quadro) |
| tecla → eco do runner (`POST /api/voo` até o HUD o confirmar) | p50 10,5 ms · máx 32 ms |
| pedidos em 20 s | `/api/state` 20 (1/s) · miniatura 79 · `/api/sim` **0** (só com janelas de detalhe abertas) |
| custo | runner 116 % de um núcleo · servidor 12 % · GPU 30 %, 2,5 GB |

O que o tornou possível: o HUD deixou de vir por sondagem de JSON (um datagrama UDP por passo de decisão do
runner → SSE do servidor → refs no DOM, sem re-render do React); os dois streams deixaram de escrever
~200 ficheiros/s no SSD (pasta em memória em `$XDG_RUNTIME_DIR`); e o histórico pesado (`/api/sim`) só é pedido
enquanto uma janela que vive dele está aberta.

**Vento de 3 botões** (`vento_natural.py`, `POST /api/vento-simples`): ligar · intensidade 0–5 m/s ·
aleatoriedade (+ a direção, numa bússola). Com a aleatoriedade ligada o vento é a MESMA média mais
turbulência de forma Dryden (σ horizontal 0,20·W, vertical 0,10·W), rajadas «1 − cos» (0,3–0,7·W, 1–3 s,
cerca de uma a cada 8 s) e a direção a deambular (σ 15°), com teto de 2,5·W; liga e desliga em rampa (τ 0,6 s).
Medido: média vetorial = W, σ|v| ≈ 0,22·W, p95 ≈ 1,5·W. Em cada arranque o vento nasce DESLIGADO (as
preferências ficam). Achado e corrigido na revisão: se o bloco dos 3 botões saía do controlo com o vento a
soprar, o nível da rampa ficava congelado e reaparecia como «vento fantasma» (1,93 m/s medidos) quando o bloco
voltava — `VentoNatural.repor()` + duas verificações e uma mutação em `teste_cockpit.py`.

**Aguentar o vento — clássico ou IA?** (`avaliar_vento.py`, `teste_vento_classico.py`). A cascata clássica
da fase 1 (sem vento) perdia para a política RL assim que o vento apertava: a 5 m/s constantes derivava 3,7 m.
Ganhou quatro peças, todas clássicas e todas no núcleo C++ que vai para o Arduino: um **observador de
perturbação** no laço de velocidade horizontal (estima o que o modelo «empuxo − arrasto» não explica e
anula-o; banda = a da malha de taxa), o **atraso da medida no modelo** (para uma manobra não parecer vento),
a **velocidade do fluxo ótico sem a rotação do corpo** e, desde 2026-10-13, um **laço vertical duas vezes mais
rígido** (`k_vz = 1/(2·τ_motor)`, integral `k_vz²/10`, modelo de seguimento `τ_motor + dt/2`; margens: fase
50,7°, ganho 15,8 dB). Tentado e rejeitado por medição: observador pelo acelerómetro (pairagem em ar parado
5,1 → 6,8 cm), observador vertical (segura a altitude mas troca-a por 1,6–1,8 m de deriva), banda mais larga
(mais inclinação em ar parado), antecipação do amortecimento vertical e `k_pz` maior (sobressinal de subida
19–33 %).

Pairar 30 s a 1 m, 12 sementes (5000–5011), vento já a soprar na descolagem, código commitado. Desvio
horizontal em cm (mediana / p95) · |Δz| máx. em cm. **0 quedas da cascata em 25 regimes × 12 sementes.**

| vento | **cascata nova** | cascata fase 1 | política RL |
|---|---|---|---|
| constante de lado, 1 m/s | **3,1 / 4,2** · 1,7 | 4,1 / 9,1 · 1,5 | 13,9 / 17,9 · 3,5 |
| constante, 3 m/s | **7,1 / 11,2** · 1,7 | 7,8 / 30,0 · 1,5 | 20,5 / 24,0 · 3,5 |
| constante, 5 m/s | **11,8 / 20,1** · 1,7 | 366 / 374 · 1,5 | 35,2 / 38,5 · 3,8 |
| aleatório (o do cockpit), 1 m/s | **3,2 / 5,7** · **2,0** | 13,8 / 23,6 · 2,4 | 15,1 / 19,7 · 3,6 |
| aleatório, 2 m/s | **5,7 / 11,4** · **3,2** | 31,5 / 55,3 · 4,9 | 19,8 / 26,2 · 3,6 |
| aleatório, 3 m/s | **10,1 / 21,2** · 6,5 | 64,7 / 117 · 8,9 | 26,4 / 37,4 · **4,6** |
| aleatório, 4 m/s | **19,2 / 45,9** · 13,5 | 266 / 363 · 14,1 | 37,0 / 55,2 · 13,2 |
| aleatório, 5 m/s | **38,8** / 114,5 · **24,8** | 951 / 1149 · 20,0 | 67,6 / **102,3** · 36,0 |
| ar descendente −30°, 4 m/s | **4,8 / 7,3** · 14,3 | 200 / 233 · 28,3 | 18,1 / 21,4 · **11,6** |
| ar descendente −30°, 5 m/s | **2,5 / 4,8** · 49,3 | 1101 / 1455 · 78,0 | 27,1 / 30,1 · **18,2** |

Degrau de vento de 3 m/s: pico 20,8 cm e volta em 3,0 s (fase 1: 151 cm e 13,5 s; RL: 25 cm e nunca volta);
de 5 m/s: 42,7 cm e 6,3 s (fase 1 e RL não voltam). Sem vento não regride: pairar 2,3 cm (fase 1 3,1; RL
12,7), sobressinal do degrau de comando 3,2 % (9,4 %; 18 %), seguimento 29,4 cm RMS (36,8; 30,5). No
seguimento com vento aleatório de 5 m/s a RL cai 3 vezes em 12; a cascata, nenhuma. **Verificação
independente** do observador em 6 sementes novas (7401–7406, antes da vertical nova): calmo 2,2 cm (fase 1
4,6 · RL 9,4); constante 5 m/s 13,1 / 21,6 (316 / 322 · 27,8 / 29,7); aleatório 3 m/s 10,3 / 19,3 (58,5 / 130 ·
19,2 / 29,3); degrau de 3 m/s pico 20,7 cm e 3,1 s (151 cm · RL 22 cm sem voltar); 0 quedas.

**A vertical nova e como foi decidida.** O laço vertical é o que fechou o último sítio onde a cascata perdia
— a altitude com rajadas: |Δz| a 3 / 4 / 5 m/s aleatório **11,5 / 23,9 / 40,6 → 6,5 / 13,5 / 24,8 cm** (pior
semente 33,6 / 75,0 / 88,7 → 19,5 / 44,9 / 82,3), ar descendente de 4 m/s 26,9 → 14,3 cm, sem custo horizontal
nem de esforço dos motores. A decisão teve dois tempos, e fica dita: (1) o candidato foi escolhido nas
sementes de calibração e medido uma vez nas de avaliação contra critérios fixados **antes** de medir — falhou
três por pouco (6,5 cm para um alvo de 6; +0,5 cm de desvio num regime de 18; sobressinal do degrau de subida
12,2 % para um limite de 12) e **não** foi adotado; (2) foi medido de novo em sementes que ninguém tinha usado
(7401–7406), sem e **com randomização de domínio**, contra critérios de adoção também fixados antes: −42 a
−46 % de |Δz| (com DR 9,9 / 18,3 / 38,0 → 5,5 / 10,5 / 21,9 cm), 0 quedas, o mesmo desvio horizontal, o mesmo
esforço (`du_rms` e potência +0,1 %), sobressinal de subida 11,1 → 10,6 % — e passou. Adotou-se **contra o
critério inicial**; reverte-se com `de_planta(razao_vz=4, razao_integral_z=4, tau_modelo_z=0,
coletivo_teto=1.8)` (a variante `cascata_vz_antiga` do `avaliar_vento.py`).

**Decisão (por medição): clássico, sem IA** — ganha ou empata com a política na posição em todos os regimes
horizontais e, na altitude com rajadas, ganha a 1, 2 e 5 m/s e empata a 4. Onde ainda perde, e fica dito:
|Δz| a **3 m/s aleatório** (6,5 contra 4,6 cm), o **ar descendente** (14,3 contra 11,6 cm a 4 m/s; 49,3 contra
18,2 a 5) e, a 5 m/s aleatório, a pior semente desvia mais na horizontal (3,3 contra 2,4 m). **Envelope**
(critério: pior semente com desvio ≤ 0,5 m e |Δz| ≤ 0,3 m): vento constante até 5 m/s; **aleatório até 3 m/s**
(com a vertical nova os três limites cumprem-se; antes só a 2); ar descendente até 4 m/s. A 4–5 m/s aleatório
**não cai**, mas a pior semente desvia 1,1–3,3 m e perde 45–82 cm de altitude. O slider vai até 5 m/s (o
máximo medido) para se ver o envelope inteiro.

**O drone sente o vento** — a única ideia que a pesquisa encontrou para copiar dos drones comerciais (a DJI
não publica a lei de controlo, mas estima e mostra o vento a bordo): o observador de perturbação dá a
aceleração que o ar impõe e o runner converte-a em m/s (`vento_sentido`; HUD `vento_bordo`). A janela Vento
mostra «o drone sente ≈ … m/s para …°» ao lado do vento real do simulador. Medido ao vivo: 2,82 m/s para 87°
com 3,0 m/s reais para 90°; 4,94 para 201° com 5,0 para 200°; 1,66 para 350° com 1,5 para 0°; em ar parado
0,2–0,5 m/s (o site diz «calmo» abaixo de 0,6).

**Seguir a bola** (tecla `B`; `avaliar_bola.py`, `treinar_bola.py`, `teste_bola.py`). A bola passa a
mover-se ao acaso — velocidade de Ornstein–Uhlenbeck com teto (o slider, 0,1–0,8 m/s), suavizada (aceleração
finita), que muda de rumo em ~2,5 s, com paredes suaves na arena e **reprodutível pela semente** — e o
seguidor visual do núcleo de firmware (detetor + IBVS em C++, o mesmo que vai para o Arduino) roda e desloca
o drone para a manter no centro da câmara de bordo. «Treinar» aqui é **afinar os ganhos sem interface**
(`treinar_bola.py`, busca em sementes de afinação que a avaliação nunca usa); «reproduzir» é a tecla `B` no
cockpit. A lei antiga errava sobretudo na vertical; a nova (IBVS v2) desconta a translação própria no filtro
do alvo, acrescenta translação lateral em paralelo com a guinada e um canal vertical no erro da imagem.

| erro de centragem, graus (mediana / p95) | lei antiga | **lei nova** | tracker de IA (PPO) |
|---|---|---|---|
| câmara Pi (116 ms) · bola a 0,3 m/s | 3,48 / 8,73 | **1,01 / 2,32** | 13,68 / 25,78 |
| câmara Pi (116 ms) · 0,5 m/s | 4,30 / 9,28 | **1,64 / 4,00** | 21,92 / 44,53 (bola no campo 89,9 %) |
| câmara Pi (116 ms) · 0,8 m/s | 6,15 / 15,15 | **3,26 / 10,30** | 29,69 / 59,39 (77,0 % · **3/12 quedas**) |
| câmara Arduino (21 ms) · 0,3 m/s | 2,85 / 6,58 | **0,85 / 2,17** | 10,26 / 37,25 (**3/12 quedas**) |
| câmara Arduino (21 ms) · 0,5 m/s | 3,23 / 7,38 | **1,21 / 3,26** | 14,04 / 28,47 (**6/12 quedas**) |
| câmara Arduino (21 ms) · 0,8 m/s | 4,32 / 11,45 | **2,28 / 6,15** | 18,18 / 81,23 (**5/12 quedas**) |

12 sementes de avaliação (6200–6211), 30 s de medida depois de 4 s de aquisição, câmara renderizada + detetor
C++, sem vento; bola no campo de visão 100 % do tempo e **0 quedas** com a lei nova. **Verificação
independente** em 6 sementes que ninguém tinha usado (7301–7306): 116 ms · 0,5 m/s 4,22/9,98 → 2,11/4,94;
116 ms · 0,8 m/s 5,92/13,40 → 4,06/10,99; 21 ms · 0,5 m/s 3,69/7,80 → 1,48/3,18; 21 ms · 0,8 m/s 4,87/11,16 →
2,58/6,88 — a lei nova ganha em 23 dos 24 pares, 0 quedas. **Decisão (por medição): clássico** — o tracker de
IA erra 8–14× mais e cai (até 6 quedas em 12); não se treinou uma política nova porque não há margem que o
justifique. Acima de 0,8 m/s a câmara de 116 ms começa a perder a bola (a 1,0 m/s: 97,7 % no campo), por isso
o slider acaba aí. A lei antiga continua no código (`visao::config_versao1`), para comparar.

**Seguir a bola COM vento** (`avaliar_bola.py --variantes depois --ventos 0,2,3 --json out/bola/avaliacao_vento.json`;
o vento aleatório do cockpit a soprar de lado durante todo o episódio, 12 sementes, 144 episódios, **0 quedas e
a bola 100 % do tempo no campo em todas as células**). Erro de centragem, graus (mediana / p95):

| câmara · bola | sem vento | vento 2 m/s | vento 3 m/s |
|---|---|---|---|
| Pi (116 ms) · 0,5 m/s | 1,63 / 3,99 | 1,89 / 4,69 | 2,58 / 6,75 |
| Pi (116 ms) · 0,8 m/s | 3,23 / 10,16 | 3,20 / 8,77 | 3,70 / 9,82 |
| Arduino (21 ms) · 0,5 m/s | 1,21 / 3,26 | 1,60 / 3,92 | 2,14 / 5,33 |
| Arduino (21 ms) · 0,8 m/s | 2,25 / 6,14 | 2,46 / 6,67 | 2,97 / 7,62 |

O vento custa cerca de 1° a 3 m/s com a bola lenta e quase nada com a bola rápida (aí quem limita é a bola);
o que cresce é o erro vertical. `teste_bola.py` passou a exigir isto (vento de 3 m/s: sem quedas, 100 % no
campo, RMS < 6°).

**Treino — está otimizado?** (`bench_treino.py`). O perfil mostrou que 80 % de cada passo do ambiente era o
modelo Python da planta (NumPy em escalares a 500 Hz), não a física do MuJoCo. Reescrito em escalares, com a
trajetória **idêntica bit a bit** ao commit anterior — provado por dois caminhos: `bench_treino.py identidade`
(13 cenários × 5 sementes × 2000 passos = 130 000 passos, 24 campos comparados por bytes) e uma segunda prova
independente (4 cenários × 3 sementes novas × 1500 passos, hash de observação, recompensa, `qpos`, `qvel` e
carga: 12/12 iguais).

| passos de treino por segundo (update incluído, máquina livre) | 1 env | 4 | 8 | 16 | 24 |
|---|---|---|---|---|---|
| antes | 278 | 918 | 1345 | 2294 | 2935 |
| **depois** | **524** | **1736** | **2417** | **3578** | 3405 |

O padrão do `--n-envs` deixou de ser 8 fixo: sai da máquina (16 aqui — rende +48 % sobre 8, e 24 já perde,
porque o `SubprocVecEnv` é síncrono e os núcleos E marcam o passo). Somando as duas coisas, um treino com os
padrões passa de 1345 para **3578 passos/s (2,7×)**. O rollout fica fixo em 4096 passos para qualquer
`n_envs`. GPU: não acelera uma MLP 64×64 em PPO (o gargalo é a simulação em CPU); migrar a planta para
MJX/Warp obrigaria a reescrever o modelo elétrico, a bateria e os sensores — não compensa. Revisão dos
hiperparâmetros (medido num treino de 160 k passos): a avaliação gastava 30–46 % do relógio (`--eval-envs N`
passa a corrê-la em paralelo), `approx_kl` ≈ 0,004 e `clip_fraction` ≈ 2 % dizem que `lr 1e-4` dá passos
pequenos no arranque do zero. **A/B corrido** (`ab_treino.py`, novo; `train.py` ganhou `--target-kl`): do
zero não mede nada — com `lr 1e-4` e com `lr 3e-4` os dois braços caem no atrator «sentar no chão» (retorno
≈ 331 com z ≈ 0,115 m ao fim de 240–560 k passos) —, por isso mediu-se na receita real, o **arranque a quente**
(`--retomar` da política do frame antigo; 1,5 M passos, 16 ambientes, sementes 0 e 1 — a terceira foi
interrompida): retorno médio ao longo do treino **582,8** com o `lr 1e-4` atual, 571,2 com `lr 3e-4` e 530,3
com `lr 3e-4` + `target_kl 0,02` (pior nas duas sementes). Aqui a `approx_kl` do treino atual já é 0,010 com
11 % de amostras cortadas: o passo não é pequeno. **Os hiperparâmetros ficam** — o gargalo era o débito, não o
otimizador (evidência de 2 sementes; normalização da recompensa não testada).
Achado e **corrigido** (2026-10-13): `reset(seed)` não era reprodutível entre instâncias — o ruído do VRS
avançava no construtor com um gerador sem semente e atravessava os episódios; agora recomeça do zero em cada
voo (`valida_real.py` F6).

**Passagem final** (2026-10-13, máquina livre, uma suíte de cada vez, estado do dono desviado com
`DRONE_PASTA_BATERIA`): **20 de 20 com exit 0.**

| suíte | resultado | | suíte | resultado |
|---|---|---|---|---|
| `run.py` (inclui `valida_real.py`) | 296/296 | | `teste_nucleo.py` | 97/97 |
| `teste_cockpit.py` (com integração ao vivo) | 5/5 secções · §4 26/26 · 7 mutações | | `teste_cascata_nucleo.py` | 73/73 |
| `teste_controlador.py` | 6/6 secções | | `teste_vento_classico.py` | 34 + 5 mutações |
| `teste_controle_voo.py --navegador` | tudo OK | | `teste_controlo_classico.py` | tudo OK |
| `teste_parar_vento.py` · com `--http --navegador` | 20/20 · 23/23 | | `teste_bola.py` | 37/37 |
| `teste_arranque_loop.py` | 72/72 | | `teste_visao.py` | 111/111 |
| `teste_multi_ia.py` | 35/35 | | `teste_seguimento.py` | 5/5 |
| `teste_camera.py` | 50/50 | | `bench_treino.py identidade --rapido` | idêntico |
| `teste_fpv.py` | 91/91 | | `pytest` da skill | 37 passed |
| `teste_arduino_catalogo.py` | 46/46 | | site: build · lint · typecheck · 7 suítes | limpos · cockpit 171/171 + 9 mutações |

As suítes antigas foram adaptadas ao cockpit (o que provava botões que deixaram de existir — ARMAR, seletor de
controlador, PARAR VENTO, seletor de continuidade — foi retirado e substituído por provas do cockpit; as que
precisam da política a voar passam `--controlador rl` explícito). Essa revisão apanhou dois defeitos reais,
ambos corrigidos: o «vento fantasma» (acima) e o runner a **morrer ao 1.º passo com políticas do cf2**, por
carregar a IA-2 de seguimento da planta real (`'HoverEnv' object has no attribute 'estimador'` — o site ficava
de pé com o simulador morto). Não corrido: `teste_fpv.py --mutacao`, `teste_parar_vento.py --legado`.

**Pendências fechadas em 2026-10-13** (as que a primeira entrega deixou abertas):
- *ecrãs pequenos* — a 1366×768 e 1280×720 a terceira janela (Vento) abre em **cascata** por cima do Voo, em
  vez de tapar a leitura de altitude: as janelas sobrepõem-se uma à outra, nunca aos instrumentos do HUD
  (`zonasInstrumentos` em `site/src/lib/cockpit.ts`; medido nas três resoluções: 0 instrumentos tapados);
- *browsers* — além do Chromium do Playwright, verificado nos browsers instalados nesta máquina, **Google
  Chrome 153 e Brave 152**: sem scroll, as duas câmaras a 1920×1080, HUD a ~49 Hz, teclas a acender, 0 erros
  de consola. Firefox e Safari não estão instalados aqui e **não** foram testados;
- *bola com vento* — avaliada em lote (tabela acima);
- *bateria* — o pack persistente do dono foi recarregado (estava a 20 %, gasto por corridas de teste) e as três
  suítes que ainda arrancavam o simulador sem o desviar (`teste_controlador.py`, `teste_camera.py`,
  `teste_fpv.py`) passaram a usar um pack descartável: nenhum teste toca em `out/bateria/`;
- *reprodutibilidade* — `reset(seed)` passou a dar a MESMA trajetória em qualquer instância e processo: a
  flutuação do VRS, o único estado da planta que nenhum reinício repunha, recomeça do zero em cada voo
  (`valida_real.py` F6, com contraprova; a prova de identidade do treino desliga-o para comparar com o código
  antigo).

- *altitude com rajadas* — a vertical nova (acima): −43 % de perda de altitude a 3 m/s aleatório;
- *hiperparâmetros do treino* — A/B corrido (acima): ficam os atuais;
- *worktrees* dos subagentes — removidos (o conteúdo está todo no ramo).

**Limites que ficam**: a estimativa de vento a bordo usa um ajuste de uma só semente; Firefox/Safari por
testar; o A/B do treino tem 2 sementes; a 3 m/s aleatório e no ar descendente a política RL ainda segura
melhor a altitude; a pesquisa foi feita no modo normal (o modo profundo do Tavily só com a flag
`--deep-research`).

## Planta REAL — o drone do dono, com peças reais (2026-10-10)

O `plano-drone-real.md` (raiz) está implementado: além do Crazyflie histórico (`env.py`, intocado), o v09 tem
o **drone que o dono vai construir**, gerado das **peças reais** do catálogo `models/drone_rpi/` e com a
política a ver **só o que o hardware mede**. Peças trocáveis sem código (`hardware.py`), os dados das peças
gravados ao lado de cada política (`hardware.json`), e tudo validado por fórmulas fechadas.

```bash
uv run python experiments/09_drone_hover_rl/hardware.py comparar            # builds com peças reais
uv run python experiments/09_drone_hover_rl/hardware.py usar <build>        # trocar motores/bateria/hélices
uv run --group hover-rl python experiments/09_drone_hover_rl/valida_real.py # 96 checagens (também no run.py)
uv run --group hover-rl python experiments/09_drone_hover_rl/train.py --planta real --n-envs 12 \
    --timesteps 6000000 --out-dir experiments/09_drone_hover_rl/out/real_<nome>   # PPO, DR, crítico assimétrico
uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py   # escolhe a política out/real_* sozinho
uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --model experiments/09_drone_hover_rl/out/real_<nome>/best_model.zip
```

**Build ativo** `endurance_15pol_p50b`: T-Motor MN4004 KV300 + P15×5 CF, 6S2P Molicel P50B (216 Wh), ESC T-Motor
AIR 40A, **frame DIY 1950 mm (wheelbase ×3, 2026-10-11)**, RPi 5 + FC H7, BMI088 + VL53L1X + PMW3901 +
INA226 + **câmara Pi Camera Module 3 Wide (FPV, à frente)** → **2183 g · 198,1 W em pairagem (11,0 g/W) ·
T/W 2,6 · 65,8 min de pairagem no modelo** (pesquisa: 2150–2250 g · 190–206 W · 64–70 min · T/W 2,5–2,7 —
os números do modelo batem todos). Efeitos do ×3 e riscos (J ×10,9, guinada ÷10–12, FC com retuning
automático, flexão dos braços vs prop passing): `models/drone_rpi/README.md`. Detalhe, alternativas e
fontes: idem.

| Peça do simulador | Ficheiro | O que faz (tudo pelo `mj_step` a 500 Hz) |
|---|---|---|
| Catálogo → física | `lab/drone_rpi/componentes.py`, `modelo.py` | massa/inércia das peças (MJCF gerado por MjSpec, CM na origem), kf/kq da tabela do fabricante (+7,5 % de realismo), curva do ESC, ω_max(V), pairagem, autonomia |
| Motores + ESC | `lab/drone_rpi/propulsao.py` | modelo elétrico DC (I = (d·V − K_e·ω)/R, Q₀(ω), J·ω̇), travagem ativa, DShot11; empuxo e reação por rotor |
| Bateria | `lab/drone_rpi/bateria.py` | Thevenin 1-RC, SoC por Coulomb, R₀(T, SoC, SoH), térmica, desgaste persistente (SoH/ciclos/“reformar”) |
| Ar | `lab/drone_rpi/aero.py` | efeito de solo (Sanchez-Cuevas), inflow BEMT (ajustado à APC 15×5.5MR), VRS, arrasto de rotor, download do frame, giroscópico — tudo desligável (`FlagsAero.base()` = bit-idêntico a T = kf·ω²) |
| Sensores | `lab/drone_rpi/sensores.py` | IMU (bias/deriva/ruído/escala/saturação/LSB/atraso/vibração), ToF ao chão, fluxo ótico (com a parte rotacional), barómetro, monitor V/I |
| Passo de física | `lab/drone_rpi/planta.py` | `mj_step1` → cinemática dos rotores (raio ao solo, ar relativo) → κ_T/κ_Q → **Newton bateria↔ESC** → rotores → forças → `mj_step2` → bateria → sensores |
| FC dedicado | `fc.py` | malha de taxa a 500 Hz (PID com ganhos calculados da planta, D na medida, PT1), mistura X, airmode, idle |
| Estimador de bordo | `estimador.py` | o que o RPi 5 calcula SÓ com sensores: atitude (complementar), rumo, altura/v_z (ToF + acc), v_xy (fluxo), odometria |
| Ambiente | `env_real.py` | `DroneRealEnv` (herda o vento base/dinâmico do `HoverEnv`), DR por episódio, pack que persiste em `options={"manter_bateria": True}` |
| Política | `politica.py` | ator-crítico ASSIMÉTRICO: o ator só vê `obs[:21]`; o crítico vê também o privilegiado |

**Contrato do `DroneRealEnv`.** Ação `Box(-1,1,(4,))` em `ctbr` (padrão): coletivo LINEAR EM EMPUXO à volta da
pairagem (u = u_pair(V)·√(1+a₀): −1 → 0, 0 → pairagem, +1 → 2× o peso) + taxas p, q, r até ±[2; 2; 1] rad/s, com o
atraso de comando do RPi (8 ms, FIFO por passo de física); `motores` = 4 aceleradores (RPi sozinho). O u_pair é
calculado à tensão MEDIDA da bateria (INA226) — a compensação de tensão do Betaflight (`vbat_sag_compensation`):
a política não vê a bateria, mas o seu "0" é pairar a qualquer SoC (medido: voa igual a 100/50/25 % de SoC).
Observação (42,) = **ator (21)**: giro/2, acc/9,81, roll̂, pitcĥ, Δψ̂/π, ĥ − alvo, v̂_z, v̂_x, v̂_y, x̂, ŷ,
ToF válido, fluxo válido, ação anterior — **sem nenhum dado privilegiado** — + **crítico (21)**: p − p_alvo,
v, (roll, pitch, yaw_err)/π, ω, ω_rotor/ω_max, SoC, V/V_nom, vento. **Recompensa v3-real** (xyz privilegiado é
permitido): r = 1 − 0,35·tanh(‖xy‖) − 0,35·tanh(|Δz|/0,5) − 0,1·tanh(|ψ−ψ₀|/0,5) − 0,1·tanh(‖v‖) −
0,05·tanh(‖ω‖/2) − 0,05·min(‖Δa‖, 1) + 0,5·bónus − 50·𝟙[terminou] — limitada, com estar vivo SEMPRE ≥ 0: a v2b do
cf2 (penalidades ilimitadas, −100 no fim) ensinou a política real a "cair cedo" quando derivava (1.º treino:
z médio a 0,56 m aos 0,8 M passos); com a v3-real a mesma configuração paira a 1 m. DR por episódio: massa ±5 %, inércia ±10 %,
CM ±4 mm, kf ±8 % (+±2 % por motor), kq ±10 %, J −20/+25 %, R −10/+15 %, KV ±3 %, I₀ ±20 %, η, SoC₀ 30–100 %,
SoH 80–100 %, R da bateria ×0,8–1,3, 5–35 °C, atraso 0–12 ms, ruído dos sensores ×0,5–2, arrasto de rotor
0,20–0,45 s⁻¹, efeito de solo ×0,7–1,3, VRS ×0,5–1,5.

**Validação** (`valida_real.py`, chamado pelo `run.py`): 96/96 — catálogo (massa = Σ peças em todos os builds,
modelo vs tabela do fabricante: rpm ≤ 1 %, corrente ≤ 5 % no build ativo), motor (regime = quadrática exata,
balanço de potência, τ = 57,4 ms medido vs 57,6 ms linearizado, travagem ativa 159 ms vs roda livre 2,4 s,
DShot, atraso de 4 passos), bateria (Coulomb e RC exatos, OCV, ×2,25 de R a 0 °C, sag ×1,5 no fim de vida,
desgaste por ciclo, persistência, ledger e Newton exatos), ar (+20 % de empuxo a 0,5·D e +5 % a 1,75·D,
a = −d·v, BEMT vs APC ±0,011, VRS 25 % a v_h = 3,8 m/s, base bit-idêntica), sensores (σ do giro 0,00263 vs
0,00260, atraso, ToF = h/cos θ, fluxo e a sua inversão), contrato (ator invariante a xy; recompensa não;
`check_env`), FC (mistura desacoplada, t90 = 206 ms ≈ 3,6·τ) e autonomia (analítica 99,0 min vs bancada
97,4 min; meta de 60 min cumprida).

**Treino da política do drone real (2026-10-10).** PPO + crítico assimétrico, MLP 128×128 tanh, 16 ambientes com
DR, currículo de vento 0→1→2→3 m/s (avança quando ≥ 50 % dos passos têm xy E z dentro de 5 cm), recompensa
v3-real: `out/real_endurance15/` (1,5 M passos, ~23 min a ~1100 passos/s) e *fine-tune* com rajadas dinâmicas
sobre o vento base até 3 m/s em `out/real_endurance15_rajadas/` (`--retomar`, +1 M passos). Curva do treino
principal (avaliação determinística em ar parado, bateria cheia, 10 episódios):

| passos | retorno (máx. ≈ 750) | z médio | ‖xy‖ médio | xy+z ≤ 5 cm | vento de treino |
|---|---|---|---|---|---|
| 64 k | 311 | 0,89 m | 0,89 m | 0 % | 0 |
| 256 k | 451 | 0,97 m | 0,12 m | 11 % | 0 |
| 448 k | 595 | 0,96 m | 0,037 m | 71 % | 0 → 1 m/s |
| 576 k | 607 | 0,96 m | 0,029 m | 86 % | 1 → 2 m/s |
| 704 k | 645 | 0,97 m | 0,029 m | 83 % | 2 → 3 m/s |
| 1,0–1,5 M | 560–650 | 0,96–0,98 m | 0,03–0,06 m | 33–91 % | 3 m/s |

**Política final** = o *fine-tune* `out/real_endurance15_rajadas/final.zip` (2,51 M passos) — a que o site carrega
por omissão e a que o `deploy.py` exportou. Grelha de condições (`avaliar_real.py`, 5 episódios por condição com as
MESMAS seeds 5000–5004, 2.ª metade de cada episódio de 10 s — já depois de descolar; vento com uma direção diferente
por episódio):

| condição | vivo | \|Δz\| | ‖xy‖ | ≤ 5 cm | ≤ 10 cm | \|ψ − ψ₀\| | potência | autonomia mostrada |
|---|---|---|---|---|---|---|---|---|
| nominal, bateria cheia, ar parado | 100 % | 1,1 cm | 6,6 cm | 32 % | 83 % | 0,027 rad | 130,1 W | 103 min |
| SoC 50 % / SoC 25 % (tensão baixa) | 100 % | 1,1 cm | 6,6 cm | 32 / 33 % | 84 % | 0,027 rad | 130,1 W | 41 / 14,5 min |
| vento 2 m/s | 100 % | 1,2 cm | 6,1 cm | 37 % | 89 % | 0,026 rad | 131,7 W | 102 min |
| vento 3 m/s | 100 % | 1,3 cm | 6,0 cm | 40 % | 86 % | 0,027 rad | 134,0 W | 100 min |
| vento 3 m/s + rajadas (até +3 m/s) | 100 % | 1,3 cm | 6,3 cm | 35 % | 92 % | 0,030 rad | 134,2 W | 100 min |
| frente de vento 3 m/s aos 5 s | 100 % | 1,8 cm | 7,0 cm | 18 % | 93 % | 0,027 rad | 134,3 W | 100 min |
| DR (peças/bateria/sensores sorteados) | 100 % | 1,8 cm | 9,2 cm | 40 % | 52 % | 0,029 rad | 129,4 W | 70 min (SoC₀ 30–100 %) |
| DR + vento 2 m/s | 100 % | 1,9 cm | 9,1 cm | 40 % | 50 % | 0,030 rad | 131,0 W | 69 min |

Comparação na MESMA grelha (\|Δz\| nominal / sob DR; ‖xy‖ nominal / sob DR): checkpoint de 1,5 M 1,9 / 3,7 cm e
6,6 / 9,6 cm · `best_model` do *fine-tune* 1,4 / 3,1 cm e 6,3 / 9,5 cm · **`final` 1,1 / 1,8 cm e 6,6 / 9,2 cm**. O
*fine-tune* com rajadas melhorou sobretudo a altura (metade do erro sob DR); em xy as três empatam — com só 3
episódios o checkpoint de 1,5 M parecia melhor (4,9 cm, 100 % ≤ 10 cm): era amostragem de seeds.

**O ‖xy‖ é limitado pelo ESTIMADOR de bordo, não pela política** (medido episódio a episódio, mesmas seeds): a
política segura a posição que o RPi ESTIMA (fluxo ótico + odometria) a 1–5,5 cm do alvo, mas essa estimativa está
2–11 cm ao lado da verdade (deriva da odometria por fluxo; maior com o ruído dos sensores ×1,4–2 do DR) — o erro
verdadeiro é quase todo erro do estimador. Por isso o DR é bimodal: 2 de 5 episódios seguram < 5 cm e 3 de 5 ficam
com um desvio de 11–16 cm em que a estimativa está a 1–5,5 cm do alvo (os 40 % ≤ 5 cm e 52 % ≤ 10 cm). Para
melhorar o xy no drone real o caminho é o estimador (fusão fluxo + acelerómetro num Kalman, calibração da escala do
fluxo, ou uma referência absoluta — marcador visual, UWB, RTK), não mais treino.

A potência em pairagem medida no voo (130 W) bate com o modelo do catálogo (133 W, fora do efeito de solo: a 1 m
os rotores estão a z/D ≈ 2,7 e o efeito de solo dá +2,3 % de empuxo, ≈ −3 % de potência à mesma tração) e a
autonomia mostrada pelo site é a que o pack daria a essa potência, com 10 % de reserva no Li-ion. Na pairagem nominal as médias da política ficam dentro de [−1, 1]
(coletivo −0,026 ± 0,076, taxas ≈ 0); só a descolagem satura o coletivo (+1 = 2× o peso) durante ~1 s — no site,
com o pack cheio, o pico foi 66,5 A (74 % dos 90 A do 6S2P P50B; 16,6 A por ESC de 40 A) e a tensão mínima
21,9 V (3,65 V/célula).

**Deploy da política final** (`deploy.py --model out/real_endurance15_rajadas/final.zip`): ONNX de entrada (1, 21)
→ saída (1, 4) — só o ATOR, o crítico privilegiado não vai para o RPi —, 94,6 kB, opset 17; max\|Δ\| 4,8·10⁻⁶ face
ao PyTorch (limiar 10⁻⁵; em estados fora da distribuição as médias chegam a \|μ\| ≈ 10 e o arredondamento
float32 cresce com elas — o clip a [−1, 1] fica no env/RPi); p50 6,9 µs · p99 7,4 µs num core (proxy do A76) e
4 IAs em paralelo a 50 Hz sem perdas (p99 agregado 422 µs). `policy.onnx` e `deploy_report.json` ficam ao lado do
modelo — o painel RPi 5 do site lê esse relatório (e diz que o modelo medido é o que está a correr).
<!-- resultados-finais -->

## Como correr

```bash
uv sync --group hover-rl                                   # stable-baselines3 + torch (CPU) + onnx/onnxruntime + rich/plotext

# 1) validar o ambiente (não treina nada): 146 checagens, exit 0
uv run --group hover-rl python experiments/09_drone_hover_rl/run.py

# 2) treinar (headless, ~11,5 min por seed nesta máquina, n_envs 4)
uv run --group hover-rl python experiments/09_drone_hover_rl/train.py \
    --timesteps 1000000 --n-envs 4 --seed 0 --sem-painel \
    --out-dir experiments/09_drone_hover_rl/out/runs/seed0

# 2b) receita v2b que passou o critério (fine-tune com vento em currículo, ~5 min)
uv run --group hover-rl python experiments/09_drone_hover_rl/train.py \
    --retomar experiments/09_drone_hover_rl/out/runs/seed2/best_model.zip \
    --timesteps 1000000 --n-envs 8 --seed 2 --sem-painel \
    --curriculo-vento 0,1,2,3 --lr 1e-4 --ent-coef 0.005 \
    --out-dir experiments/09_drone_hover_rl/out/vento_r9_curr_lr1e4_seed2

# 2c) receita do CAMPEÃO (ronda 10): vento DINÂMICO em 3 fine-tunes encadeados (~11 min no total)
#     rajadas (1 M) → frente (600 k) → turbulência dryden (600 k); sempre com vento ativo no currículo
uv run --group hover-rl python experiments/09_drone_hover_rl/train.py \
    --retomar experiments/09_drone_hover_rl/out/vento_r9_polir_vento3/final.zip \
    --timesteps 1000000 --n-envs 8 --seed 0 --sem-painel --curriculo-vento 1,2,3 \
    --lr 1e-4 --ent-coef 0.005 --log-std-init -0.5 \
    --vento-dinamico rajadas --vento-dinamico-params '{"p": 0.02, "duracao": 10}' \
    --out-dir experiments/09_drone_hover_rl/out/vento_r10_ft_raj_1M
#   os dois passos seguintes repetem o comando com --retomar o best_model.zip da etapa anterior:
#     --vento-dinamico frente --vento-dinamico-params '{"t_s": 2.0}' --timesteps 600000     → out/vento_r10_ft_frente_600k
#     --vento-dinamico dryden --vento-dinamico-params '{"sigma": 0.5, "L": 10}' --timesteps 600000
#                                                                        → out/vento_r10_ft_dryden_600k  ← CAMPEÃO

# 2d) receita do CONTROLE DE VOO (contrato r11, `--comandos`) — WASDQE, seguimento + rajadas corrigidas
#     ETAPA 0 (obrigatória): TRANSFERIR uma política que já voa para a observação de comando (16→19 no
#     cf2, 42→48 na planta real) — as entradas novas (`v_ref`) ficam a zero e a validação exige AÇÕES
#     IDÊNTICAS em estados sem comando. PORQUÊ: treinar o modo comando do zero cai no atrator «sentar no
#     chão» (medido 2026-10-10: a política desliga os motores e colhe r≈0,7/passo; com perfis de comando
#     desde o início, pior ainda — e o cf2 nem no modo clássico aprende a voar de raiz: a campanha v2b
#     precisou de 20 treinos/25 M passos). Arrancar de quem já voa resolve-o (o fine-tune só tem de
#     aprender o SEGUIMENTO).
uv run --group hover-rl python experiments/09_drone_hover_rl/transferir_politica.py \
    --de experiments/09_drone_hover_rl/out/vento_r10_ft_dryden_600k/best_model.zip \
    --para experiments/09_drone_hover_rl/out/voo_cf2_transferida --planta cf2
#     ETAPA 1: fine-tune de SEGUIMENTO com perfis de comando aleatórios + rajadas de vento (o `--comandos`
#     SEM `--sem-perfis-comando` sorteia os perfis: 1.º segmento hover 1–2 s e depois segmentos 0,5–2 s com
#     velocidades de 0,3 a 1,0 m/s em direções aleatórias, ±0,7 m/s na vertical; a recompensa é de
#     seguimento LIMITADA — erros `p − p_ref` e `v − v_ref`, `tanh` — com o bónus a exigir posição E
#     velocidade; `--sucesso` por omissão sobe para 720 em modo comando: o 450 do hover parava o treino
#     a meio do seguimento)
uv run --group hover-rl python experiments/09_drone_hover_rl/train.py \
    --planta cf2 --comandos --retomar experiments/09_drone_hover_rl/out/voo_cf2_transferida/final.zip \
    --sem-curriculo --vento-max 3 --vento-dinamico rajadas \
    --vento-dinamico-params '{"p": 0.03, "duracao": 12}' --timesteps 3000000 --n-envs 10 \
    --sem-painel --seed 0 --out-dir experiments/09_drone_hover_rl/out/voo_cf2_r1
#     a planta real é igual com --planta real e o --de out/real_endurance15_rajadas/final.zip (a
#     transferência copia também o hardware.json) → out/real_voo_r1; `--sem-perfis-comando` é o ESTÁGIO 0
#     (pairagem na obs de comando) para casos de raiz — ver o help do train.py
#     PROVA: teste_controle_voo.py (§1 peças, §2 seguimento — inclui a SIMETRIA proa/cauda, o núcleo do
#     pedido do dono —, §3 servidor+eco, §4 navegador com os keycaps ao vivo)
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controle_voo.py --navegador

# 3) ver a política: janela 3D + HUD (ESPAÇO pausa · Q/Esc fecha) ou o mesmo ciclo sem janela
uv run --group hover-rl python experiments/09_drone_hover_rl/view.py                 # melhor de out/runs/*/
uv run --group hover-rl python experiments/09_drone_hover_rl/view.py --sem-janela --passos 300
uv run --group hover-rl python experiments/09_drone_hover_rl/view.py \
    --model experiments/09_drone_hover_rl/out/vento_r9_polir_vento3/final.zip --rapido

# 3b) vento ao vivo no viewer (sem passar pela UI): ficheiro de controlo ou flag
uv run --group hover-rl python experiments/09_drone_hover_rl/view.py \
    --model experiments/09_drone_hover_rl/out/vento_r9_polir_vento3/final.zip --vento-inicial 2,90

# 3c) PADRÃO do laboratório (CoALA `padrao-simulacao-clean-site`): janela CLEAN + site com TODAS as
#     métricas e controlos, num só comando; o LOOP arranca DESLIGADO («SEM REINÍCIO», padrão desde
#     2026-10-09): no fim do episódio a física continua no estado em que ficou — só o REINICIAR do site
#     recomeça. `--com-loop` liga o CONTÍNUO (auto-reset no fim do episódio) já no arranque
#     (ver §«Continuidade do episódio»)
uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py --sem-browser
#     sem --model, usa a política da última validação com sucesso (hoje o campeão r10 — ver §Resultados)

# 4) UI web local ("clicar para treinar" + rede ao vivo + painel de VENTO) — stdlib, offline, anuncia o URL
uv run --group hover-rl python experiments/09_drone_hover_rl/dashboard.py --port 8765 --out "$TMPDIR/runs"
#    no painel "5 · Vento ao vivo": força (0–5 m/s), azimute (0–360°), elevação (−90..90) → APLICAR/PARAR

# 5) a rede a correr em JSONL (usada pela UI) e o pipeline de deploy
uv run --group hover-rl python experiments/09_drone_hover_rl/net_probe.py \
    --model experiments/09_drone_hover_rl/out/vento_r9_polir_vento3/final.zip \
    --out "$TMPDIR/net.jsonl" --interval 0.05 --vento-inicial 3,45
uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --model out/vento_r9_polir_vento3/final.zip
uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --int8 --skip-multi
uv run --group hover-rl python experiments/09_drone_hover_rl/deploy.py --nproc 4 --duracao 10
```

### Correr com controlo clássico (seletor de controlador, contrato r12, 2026-10-12)

O simulador tem DOIS caminhos de controlo, trocáveis **ao vivo** (sem reiniciar o site): a política RL
(IA-1, o de sempre) e a **cascata clássica C++ do firmware** (`firmware/nucleo/`, via ctypes — o MESMO
código que voa no Arduino). O arranque escolhe com `--controlador` (padrão **`rl`**, para não mudar o
comportamento atual) e o site troca depois (`POST /api/controlador`, cartão «Controlador»):

```bash
# arranque já em modo clássico (a cascata C++ pilota: yaw livre, WASDQE relativo ao rumo, olhar IBVS)
uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py --controlador classico

# arranque normal (rl) e troca ao vivo pelo site ou por curl:
uv run --group hover-rl python experiments/09_drone_hover_rl/sim_site.py
curl -X POST http://127.0.0.1:8080/api/controlador -d '{"modo": "classico"}' -H 'Content-Type: application/json'

# prova completa do seletor + yaw + olhar (6 secções, 71 checagens + 2 mutações)
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controlador.py
```

O que muda em modo clássico: **yaw livre** (teclas Z/C rodam ±0,5 rad/s, X fixa o rumo atual, V liga o
«olhar» — o IBVS do núcleo segue o alvo que passa a descrever o círculo); **WASDQE relativo ao RUMO**
(W = avanço no nariz, A/D laterais ao rumo — o painel mostra o avanço/lateral vs o rumo atual); a
**perceção** é o detetor + IBVS C++ (25–30 Hz) em vez da IA-2. A TROCA reinicia o episódio (calibração do
giroscópio no chão) e o estado é honesto: `/api/state` mostra `controlador.estado = "trocando"` + `motivo`
enquanto o eco não apanha o pedido, e `"erro"` + motivo quando a troca é recusada (planta cf2 — a cascata
é do hardware do dono). Decisão documentada: preferiu-se o C++ via ctypes mas SEM trocar de env em runtime
(o viewer 3D e os módulos FPV ficam ligados aos `model`/`data` do arranque e não há API para os religar) —
o núcleo instala-se no env em uso com os MESMOS adaptadores do `sitl.DroneRealEnvNucleo(modo_nucleo=
"cascata")`; o protótipo Python (`controlo_classico.py`) não é o que voa no runner. Ver `INTERFACE.md` §4.7.

Flags principais (todas as peças têm `--help`):

| peça | o que faz | flags que importam |
|---|---|---|
| `train.py` | PPO headless (SB3) sobre `HoverEnv`; grava `best_model.zip`, `final.zip`, `ckpt/`, `evaluations.npz` e `train_log.jsonl` (**13 campos** por avaliação) | `--timesteps` · `--n-envs` · `--seed` · `--out-dir` · `--sem-painel` · `--eval-freq` · `--sucesso` · `--lr` · `--ent-coef` · `--log-std-init` · **`--curriculo-vento`** · `--vento-max` · `--sem-curriculo` · **`--avanco-frac`** · **`--retomar`** · **`--vento-dinamico`** · **`--vento-dinamico-params`** |
| `view.py` | viewer **passivo** do MuJoCo + HUD ASCII de **8 linhas** (obs resumidas, ações + comando físico, z/alvo/dz/dxy, **yaw_err/ω_z**, vento, retorno) e **3 figuras** (z(t) com linha do alvo, yaw_err, ações) | `--model` · `--sem-janela` · `--passos` · `--segundos` · `--episodios` · `--rapido`/`--tempo-real` · `--alvo-z` · `--seed` · **`--controlo`** · **`--vento-inicial`** |
| `dashboard.py` | servidor HTTP local (só stdlib) que **nunca treina no processo**: faz `Popen`/`SIGTERM` do `train.py` e do `net_probe.py`; API JSON + página única embutida com **painel de vento** | `--host` · `--port` · `--out` · `--net-out` · `--vento-out` · `--train-py` · `--verboso` |
| `net_probe.py` | a MLP [16, 64, 64, 4] a correr, com *forward hooks* nas `nn.Linear`: 1 linha JSONL por instante (`obs`, `h1`, `h2`, `act`, `z`, `dist_xy`, `no_alvo`, **`yaw_err`, `vento_vel`, `vento_azim`**) | `--model` (obrigatório) · `--out` · `--interval` · `--alvo-z` · **`--controlo`** · **`--vento-inicial`** · **`--fator-tempo`** |
| `deploy.py` | exporta o gráfico da política para **ONNX**, valida-o contra o PyTorch, mede latência (proxy de 1 core) e corre N processos a 50 Hz | `--model` · `--int8` · `--nproc` · `--duracao` · `--pinned` · `--threads` · `--threads-contraste` · `--skip-multi` · `--out` |
| `run.py` | valida o **ambiente** (ação→`ctrl`, recompensa, física, obs, Gymnasium, contrato do modelo, **robustez**) em condições isoladas | sem argumentos (e sem `--help`): corre tudo e sai com 0/1 |

## Arquitetura

| ficheiro | papel | não faz |
|---|---|---|
| `env.py` | `HoverEnv`: física, observação, ação, recompensa v2b, vento (`opt.wind`), terminação, `reset` com jitter e assentamento | treino, viewer, ONNX, render |
| `train.py` | PPO `MlpPolicy` MLP [64, 64] tanh, `SubprocVecEnv` com `Monitor`, currículo de vento (DR), avaliação e *checkpoints*; `--retomar` para fine-tune | tocar no `env.py`, abrir browser |
| `view.py` | viewer passivo + HUD ASCII de 8 linhas, 3 figuras (`launch_passive`, 50 Hz), vento ao vivo por ficheiro | treinar |
| `dashboard.py` | UI web local: botão treinar/parar, curvas, rede ao vivo, **painel de vento**, cauda do stdout | treinar no processo do servidor |
| `net_probe.py` | sonda da rede em JSONL (hooks nos `nn.Linear`) + vento ao vivo | render, rede, viewer |
| `sim_view.py` | runner da **janela limpa** + telemetria JSONL: lê vento/`reiniciar`/`loop` do ficheiro de controlo; CONTÍNUO reinicia no fim do episódio e SEM REINÍCIO deixa a física continuar (só o REINICIAR recomeça) | treinar, HUD, abrir browser |
| `sim_site.py` | **um comando**: arranca o `sim_view.py` + servidor local que serve o site (`site/dist/`) e a API (`/api/sim`, `/api/vento`, `/api/vento-dinamico`, `/api/reiniciar`, `/api/loop`) | treinar, mexer na física |
| `deploy.py` | ONNX → validação → benchmark → int8 → multi-IA → relatório JSON | tocar nas outras peças |
| `run.py` | validação por fórmulas fechadas + robustez (exit 0/1) | treinar |

### Observação (16,) — já normalizada por escalas fixas

`Box(-inf, inf, (16,))`, float32. **Não há `VecNormalize`** (decisão de design): a observação sai
normalizada do ambiente, logo o gráfico ONNX do deploy fica **puro** — sem estatísticas de corrida
agarradas ao wrapper.

| índice | conteúdo | escala |
|---|---|---|
| `[0:3]` | `p − p_alvo` (`p` = sensor `posicao`, o **CM do corpo**; `p_alvo = [0, 0, alvo_z]`) | ÷ 1 m |
| `[3:6]` | `roll, pitch, yaw` do sensor `body_quat` (quaternion MuJoCo `[w x y z]`, ZYX intrínseco) | ÷ π |
| `[6:9]` | velocidade no **frame do corpo** (`R(quat)ᵀ · v_mundo`) | ÷ 1 m·s⁻¹ |
| `[9:12]` | velocidade angular do sensor `body_gyro` (frame do corpo) | ÷ 10 rad·s⁻¹ |
| `[12:16]` | **ação anterior** | já em `[-1, 1]` |

`ruido_obs > 0` soma ruído gaussiano σ = `ruido_obs` (treino com ruído de sensor); o padrão é 0.

### Ação (4,) — centrada no hover

`Box(-1, 1, (4,))` = `[empuxo, momento x, momento y, momento z]`, com **a = 0 igual ao hover** (não é uma
faixa de empuxo de 0 a máximo: a metade da caixa acima e abaixo do hover é assimétrica de propósito):

```
a₀ ≤ 0:  empuxo  = mg · (1 + a₀)                        (a₀ = −1 → 0 N; a₀ = 0 → mg)
a₀ > 0:  empuxo  = mg + (thrust_max − mg) · a₀          (a₀ = +1 → thrust_max)
momentos_i = tau_escala · momento_max_i · a_i           (tau_escala = 0,1 → 10 % da autoridade máxima)
```

Tudo cortado às faixas físicas dos canais. `data.ctrl` fica em **unidades físicas, 1:1** com os 4 canais
(`nu = nactuator = 4`): `[0]` empuxo em N, `[1:4]` momentos em N·m. O `cf2.xml` em disco **nunca é
tocado** — a faixa do empuxo e o gear dos momentos são ajustados só na cópia em memória do ambiente.

`thrust_realista=True` (padrão) usa `thrust_max = 0,589 N` (4 × 15 gf do datasheet CF2.1 → **T/W ≈ 2,22**)
em vez dos `0,35 N` do modelo do menagerie, que o próprio README classifica de *"arbitrary and need to be
further tuned"* (T/W = 1,32). Com o valor do upstream o drone mal sai do chão;
`thrust_realista=False` reproduz esse caso e é o que a checagem 1 do `run.py` cobre.

Faixas dos momentos (geometria dos rotores, `lab/crazyflie.py`): braço 0,0325 m, `T_rotor_max = 0,0875 N`
→ `momento_max = (5,69e-3, 5,69e-3, 2,80e-3) N·m` (roll, pitch, yaw).

### Recompensa v2b — fixação de posição **e** orientação (2026-10-08)

Por passo de **decisão**. A v1 era a equação **literal** do MuJoCo-Drones-Gym ([arXiv 2606.08039],
preprint); a v2b mantém a estrutura e ajusta os pesos depois de a campanha de re-treino ter mostrado um
**atrator de *chatter*** nos momentos (ver [Lição da campanha](#lição-da-campanha-r1r9)):

```
r = −1,0·‖xy‖ − 1,0·|z − alvo_z| − 0,2·|yaw_err| − 0,05·‖v‖ − 0,05·‖ω_xy‖
    − 0,1·|ω_z| − 0,05·‖Δa‖
    + 1,0 · 𝟙[ ‖xy‖ < 0,05 ∧ |z − alvo_z| < 0,05 ∧ |yaw_err| < 0,10 ]     (bónus "no alvo", 5 cm / 0,1 rad)
    − 100 · 𝟙[ terminou ]
```

- `‖xy‖ = √(x² + y²)` — **prender o drone no mesmo ponto** (peso 1,0, dez vezes a v1);
- `yaw_err` = yaw (ZYX do `body_quat` `[w x y z]`) **envolvido em [−π, π]**, alvo **0 rad** — é o
  "não girar" / "apontar sempre para o mesmo lado" (peso 0,2);
- `ω_xy` = 2 primeiros componentes da velocidade angular no corpo; `|ω_z|` com peso **0,1** (freio do giro);
- `Δa` = ação atual − ação anterior (**0,05**): penalidade de *taxa de ação*, o remédio padrão para
  *chatter*;
- o bónus é **estrito** nos três limiares (0,05 m / 0,05 m / 0,10 rad) e a terminação vale **−100** exatos.

Episódio de **10 s = 500 passos de decisão** (truncagem — truncar **não** é terminar). Terminação:
`z < 0,005 m` (caiu — o piso impede `z < 0`), `max(|φ|, |θ|) > π/2` (capotou) ou `z > Z_TETO (30 m desde 2026-10-11; eram 3 m)` (subiu demais).

### Vento e orientação fixa (v2b)

O vento é **físico**: o `cf2.xml` já traz `density="1.225"` / `viscosity="1.8e-5"`, logo o **arrasto aerodinâmico por inércia**
já existe; o que faltava era o **vento**. Ele entra como o mecanismo oficial do MuJoCo — o vetor
**velocidade do ar** (`model.opt.wind`, frame mundo, m/s) subtraído à velocidade do corpo no cálculo do
fluido. É física a sério (`mj_step`), não uma força somada à mão; o chão é estático e imune.

| API | unidades | notas |
|---|---|---|
| `HoverEnv(vento=(vx, vy, vz))` | **cartesiano** (m/s) | vetor mundo fixo no episódio |
| `HoverEnv(vento_aleatorio=(u_min, u_max))` | m/s | **domain randomization**: por episódio, norma U[u_min, u_max], azimute U[0, 360°), elevação U[−20°, +20°]; semeado por `np_random` (reprodutível com a seed) |
| `definir_vento(vel, azimute_graus, elevacao_graus=0)` | **polar** | `vel` em m/s; reescreve `opt.wind` **já** (o episódio em curso sente logo) |
| `definir_vento_aleatorio(u_min, u_max)` | m/s | muda o teto do DR (usado pelo currículo do treino) |

Guardas: valores não finitos (NaN/inf) → `ValueError` com mensagem clara; ação não finita → `ValueError`
sem corromper o estado; divergência numérica → `RuntimeError` (com a explicação de que um `reset()`
sozinho não chega se a causa for o vento absurdo — usar `definir_vento` com valor são).

Magnitudes de referência para o Crazyflie 2 (m = 27 g, W = 0,265 N): a 3 m/s o arrasto inercial vale
≈10 % do peso; a 5 m/s ≈29 %; o CF2 real começa a perder posição por volta de **3 m/s**. O envelope
validado desta política é **≤3 m/s sustentado** (ver resultados).

### Vento dinâmico (r10) — rajadas · rajadas aleatórias · frente · turbulência

O vento por episódio (`vento`/`vento_aleatorio`) só muda **entre** episódios. A ronda 10 acrescentou
`vento_dinamico=dict`, que faz o vento mudar **dentro** do episódio, a cada passo de decisão (50 Hz),
sempre pelo mesmo mecanismo físico (`opt.wind`). A config é validada por `env.valida_vento_dinamico()`
(modos, chaves e faixas; erro claro) e o treino expõe-na por `--vento-dinamico` +
`--vento-dinamico-params '<json>'` — **só os envs de TREINO** a recebem (a avaliação fica no contrato v2b):

| modo | chaves (default) | o que faz a cada passo de decisão |
|---|---|---|
| `rajadas` | `p` 0,02 · `duracao` 10 passos (0,2 s) · `u_max` 3,0 m/s | com probabilidade `p` sorteia uma rajada (norma U[0, `u_max`], azimute novo, elevação ±20°) que **soma** ao vento base durante `duracao` passos; uma rajada em curso não é interrompida por outra |
| `aleatoria` | `p` 0,02 · `duracao` 10 passos (0,2 s) | rajadas com o mesmo `p`/`duracao`/envelope de `rajadas`, mas cada uma re-sorteia **direção E força dentro das faixas disponíveis por inteiro**: norma U[0, 5] m/s, azimute U[0, 360°) e elevação U[−90°, +90°] (o `VENTO_ELEV_MAX` = 20° **não** se aplica aqui). Aplicação por **mistura vectorial** com o vento base, `w(k) = base + sin(π·k/(N+1))·(rajada − base)`: **no pico do envelope o vento É o vector sorteado** e nas pontas fica junto do base (entrada/saída suave), com `‖w‖ ≤ max(‖base‖, 5) m/s` — uma soma, com base forte, daria direções dominadas pelo base e normas até 10 m/s. Cada rajada tem o seu próprio vector — nada vaza para a seguinte. `u_max`/`sigma`/`L`/`v_min` são aceites (e validados, se vierem) mas **ignorados**: a amplitude não segue o teto do currículo (só `u_max = 0` continua a deixar o modo inerte, como em todos os modos) |
| `frente` | `t_s` 2,0 s · `u_max` 3,0 m/s | no instante `t_s` chega uma **frente** — norma U[0,5 m/s, `u_max`], azimute novo — que **substitui** o vento base até ao fim do episódio (degrau dentro do passo, sem transiente artificial; `t_s = 0` = frente logo no 1.º passo e `t_s` tem de cair dentro do episódio) |
| `dryden` | `sigma` 0,5 · `L` 10,0 · `u_max` 3,0 m/s | **turbulência** OU de 1.ª ordem (filtro de Dryden discreto por passo): o vento passeia em torno do base, saturado em ±`u_max` |

`u_max` é o teto do **modo** (o teto do vento por episódio continua a ser o do currículo/`--vento-max`), e
**`u_max = 0` é inerte em todos os modos**: sem rajadas, sem frente e sem turbulência — e, importante,
**não consome `np_random`**, logo um estágio sem vento é indistinguível do contrato v2b (era a guarda que
faltava aos modos não-`rajadas`). O `info["vento_atual"]` passou a reportar o vetor **em vigor**
(base + dinâmica).
Estes modos são do **treino/avaliação** e do **vento ao vivo** do site (a caixa «vento dinâmico» tem o
seletor PARADO/RAJADAS/**ALEATÓRIA**/DRYDEN, que escreve o modo sem reiniciar o episódio); os sliders
aplicam sempre vento **constante em tempo real** (`INTERFACE.md` §3.5).

### PARAR — nenhuma rajada sobrevive ao clique (2026-10-09)

O dono relatou «podemos mandar rajadas mas na hora de parar só paramos a última». Mecanismo **medido**
(não suposto): só existe **um** slot de rajada dirigida (`Controlo.rajada` — cada `RAJADA AGORA` substitui a
anterior, logo nunca houve rajadas simultâneas nesse slot); o que continuava a atuar depois do PARAR eram
(i) as rajadas dos **modos contínuos** (`rajadas`/`aleatoria`/`dryden`, geradas pelo próprio env) e (ii) a
rajada one-shot a meio do envelope — porque o botão **PARAR VENTO** escrevia só `POST /api/vento {vel: 0}`
(o vento *constante*) e **não tocava no bloco `dinamico`**: o runner continuava a escrever o envelope em
`model.opt.wind` e a telemetria continuava a mostrar `vento_modo = rajadas|rajada_agora|…`. Havia ainda
dois resíduos: o `definir_vento_dinamico(None)` do env não limpava `_rajada_k/_rajada_n/_rajada_vec/_turb/
_frente_vec`, e o restauro do vento base usava o registo **anterior** do controlo (um PARAR que também mexe
no vento — o do PARAR VENTO — escrevia a base velha em `opt.wind`).

Correção: `Controlo._para_dinamica` (caminho único do PARAR DINÂMICO **e** do PARAR VENTO) corta o slot da
rajada, reescreve em `opt.wind` o vento base do controlo **em vigor** e desliga o modo do env;
`env.definir_vento_dinamico(None)` passa a limpar o estado do modo e a escrever sempre o vento base; a troca
de modo larga a rajada por `cancelar_rajada` (com restauro) e o `_aplica` fixa o registo em vigor **antes**
do bloco dinâmico; e o novo **`POST /api/parar`** faz o PARAR VENTO numa só escrita atómica (vento base a 0
**+** dinâmica desligada), usado pelo botão do site.

Prova repetível (`teste_parar_vento.py`): **15/15 verificações** sem flags — todos os cenários/ciclos do
PARAR (one-shot e modos contínuos, com o PARAR a chegar no início/meio/fim do ciclo da rajada) no ciclo
REAL do `sim_view.correr`, mais a prova de concorrência in-process —; **16/16** com `--http` (ponta a ponta
pelo servidor real + ~100 pares de POSTs concorrentes) e **18/18** com `--http --navegador` (front real num
Chrome headless, janelas 0/50/100/300/600/1000 ms × 3 caminhos de paragem + controlo, e os cenários
multi-cliente). Com as fontes de antes (`--legado REV`, ou `--fontes DIR`) só passavam **3** verificações,
com as falhas exatamente nos cenários do PARAR VENTO (vento a oscilar 1,8–5,0 m/s com
`vento_modo` ainda `rajada_agora`/`rajadas`/`dryden`) e nos resíduos do env.



O ficheiro `experiments/09_drone_hover_rl/out/controle_vento.json`
(`{"vel", "azimute", "elevacao", "ativo", "t"}`) é o contrato comum:

- **`dashboard.py`** — painel **«5 · Vento ao vivo»**: sliders de força (0–5 m/s), azimute (0–360°) e
  elevação (−90..90) + botões **APLICAR VENTO**/**PARAR VENTO** e atalhos ±x/±y; `POST /api/vento`
  (400 fora de faixa/não numérico) escreve o ficheiro **atomicamente** (`tmp` + `os.replace`);
  `GET /api/vento` devolve o estado;
- **`net_probe.py`** — vigia o ficheiro a **cada passo de decisão** (gate por `mtime_ns`+tamanho) e chama
  `definir_vento`; a linha JSONL ganha `yaw_err`, `vento_vel`, `vento_azim`;
- **`view.py`** — lê o mesmo ficheiro a cada ~5 passos e mostra o vento no HUD (o modo janela é para o
  dono usar; `--vento-inicial v,az[,elev]` dispensa o ficheiro).

`--fator-tempo` na sonda: `0` = sem travão (≈28–30× o tempo real, medido), `1` = tempo real (a "rede ao
vivo" deixa de ser um borrão), `2` = 2× — a UI usa 1×.

### Continuidade do episódio — LOOP, REINICIAR e o ficheiro de controlo (ronda 11)

O `sim_view.py` (runner da janela limpa) e o `sim_site.py` (site + API) partilham o ficheiro
`out/controle_vento.json`. Desde a ronda 11 o campo `loop` é **sticky e autoritativo**, e desde
2026-10-09 o **padrão é SEM REINÍCIO (`false`)** — o arranque corrige o ficheiro e, depois dele, só o
`POST /api/loop` muda o modo:

| situação | o que acontece |
|---|---|
| `loop: false` ou nada (PADRÃO desde 2026-10-09) − **SEM REINÍCIO** | **nunca reinicia sozinha e nunca congela**: no fim do episódio a física **continua** a integrar (`mj_step` a 50 Hz) no estado em que ficou — se caiu, fica onde a física o deixou; se pairava, continua a pairar — com a telemetria a ~10 Hz, `passo`/`t` a crescer para lá dos 500/10 s e `retorno` congelado no valor com que o episódio fechou. **Só o REINICIAR recomeça** |
| `loop: true` / `--com-loop` − **CONTÍNUO** | no fim do episódio (`terminated`/`truncated`, 500 passos = 10 s) o runner faz `env.reset()` e **arranca já o episódio seguinte** (ep+1, passo 0); a transição é discreta e o vento/modo dinâmico atravessam-na |
| REINICIAR (site, `POST /api/reiniciar`) | incrementa o contador `reiniciar` no ficheiro → `env.reset()` no passo de decisão seguinte. É o **único reset** e vale em qualquer estado (a correr, terminado sem reinício, ou a meio) |
| LOOP do site (`POST /api/loop`) | única forma de mudar `loop` **depois do arranque** (liga/desliga a quente, sem reiniciar nada por si) |
| `--com-loop` / `--sem-loop` no arranque | **autoritativos**: o arranque CORRIGE o `loop` do ficheiro — sem flag (ou `--sem-loop`) um `loop: true` velho passa a `false`; com `--com-loop` (alias antigo `--loop`) um `loop: false` velho passa a `true` — preservando vento, dinâmica e o contador `reiniciar`. As duas flags juntas são recusadas (`exit 2`) |

Escritas **parciais** no controlo (ex.: `POST /api/vento`, `/api/vento-dinamico`, que não trazem `loop`
nem `reiniciar`) fazem merge sobre o que o ficheiro já tem: **não** re-ligam o loop nem mexem no contador
de reinícios. `--max-segundos` e `--max-episodios` continuam a terminar o processo (são flags explícitas,
não auto-loop). Contrato e detalhes de UI: `INTERFACE.md` §4.1 e §3.5.

### Decimação e física

`dt = 0,002 s` (**500 Hz**, integrador **RK4**) × `decimation = 10` → **50 Hz** de decisão (0,02 s por
`step()`). Um passo de política são 10 passos de física; `data.time` avança exatamente 0,02 s por
`step()` (checagem 6 do `run.py`).

### `reset` — sem teleporte

`mj_resetDataKeyframe` (keyframe `hover` do lab, `z = 0,1 m`) + `ctrl = 0` (**motores desligados**;
o keyframe do lab traz `ctrl = peso`, aqui é zerado), jitter determinístico `xy ± 2 cm` e `yaw ± 5°`,
e **assentamento físico**: a queda de ~9 cm até ao chão corre em `mj_step` até 10 passos consecutivos
com `z < 5 cm` e `‖v‖ < 1 mm/s` (teto de 1 s). O drone começa o episódio **pousado** (z ≈ 0,0125 m).

Com vento, o assentamento corre **em ar parado** (`opt.wind = 0`) e o vento do episódio entra **logo
depois** — decisão de desenho: o estado inicial é sempre uma pose pousada estável, e a política tem de
**descolar e recuperar** contra o vento que chega (é isso que o treino com DR ensina).

### Hélices — animação VISUAL (2026-10-09, fora do `mj_step`)

As 4 hélices **giram na janela 3D** com a velocidade e o sentido do rotor que está a ser comandado. É
**só apresentação**: a animação corre no runner (`sim_view.py` chama `cf.Helices.atualizar(...)` antes de
cada `viewer.sync()`) e escreve apenas `model.geom_pos`/`model.geom_quat` de 4 geoms **visuais**, mais um
`mj_kinematics` para o renderer ver já este frame. Nada toca em `qpos/qvel/ctrl` nem em `mj_step`.

- **Adaptação em runtime (upstream intacto):** a malha `cf2_0` do menagerie (as 4 hélices **fundidas**
  numa só) é fatiada por **quadrante do sinal de (x, y)**. O OBJ **não** tem as hélices como ilhas
  separadas — é um *vertex soup* (medido: 3372 vértices para só **1592 coordenadas únicas**, 3168 faces e
  **176 ilhas** de aresta, a maior com 130 vértices) —, mas **nenhuma das 3168 faces cruza os eixos
  x = 0 / y = 0** em coordenadas do ASSET (medido: 0 faces a cruzar), e é só isso que o corte pelo sinal
  exige: cada quadrante leva exactamente 843 vértices, 792 faces e 44 ilhas, os mesmos do OBJ. Daí saem 4
  malhas com 4 geoms novos `helice_1..4` (`contype = conaffinity = 0`, `density = 0`, grupo 2, material
  `propeller_plastic`); o geom original é apagado do spec. `models/bitcraze_crazyflie_2/` fica **intocado**.
- **Massa e inércia não mudam:** o corpo `cf2` tem `<inertial>` explícito e o compilador tem
  `inertiafromgeom="false"`, logo os geoms visuais não pesam — `m = 0,027 kg` e `diaginertia =
  2,3951e-5/2,3951e-5/3,2347e-5` iguais ao upstream, ao bit.
- **Eixo de rotação medido na própria malha:** as tampas do motor (as únicas faces perfeitamente planas
  e de secção quadrada, Ø 3,99 mm) dão o eixo; eles ficam a **0,7–1,2 mm** dos `POS_ROTORES` (±32,5 mm)
  — a malha do menagerie está ligeiramente descentrada da origem do corpo, por isso medir é mais fiel.
- **Lei de rotação:** `|ω_i| = ESCALA_VISUAL·√t_i` com `t_i` = empuxo de cada rotor (N) recuperado do
  wrench comandado pelo **mixer inverso** de `comandar_rotores`; o sinal é o de `GIRO` (**+1 = anti-horário
  visto de cima**), pelo que as **diagonais 1-4 e 2-3 giram no mesmo sentido e as vizinhas no oposto** —
  coerente com o sinal do momento de guinada do modelo.
- **ESCALA VISUAL (documentada):** `ESCALA_VISUAL = 2π·3/√T_ROTOR_MAX = **63,72 rad/s·N^(−1/2)**`, isto é
  **3 rev/s com um rotor no empuxo máximo** (0,0875 N) e ≈ 2,6 rev/s em hover — cerca de **1/100 da
  rotação real** (hélices CF2 a ~15 000 rpm ≈ 250 rev/s): a rotação verdadeira seria ilegível a 50 Hz
  (aliasing). A proporcionalidade entre rotores e os sentidos são **exatos**; só a escala é visual.
- **Motores desligados:** as hélices **abrandam** com 1.ª ordem (`ABRANDAMENTO_S = 0,35 s`) e, abaixo de
  `LIMIAR_PARAGEM = 0,01 rad/s`, **param exactamente** (ω = 0, ângulo congelado) — sem rodar para sempre.
- **REINICIAR não parte nada:** o estado da animação é só ângulo/velocidade, os geoms são re-resolvidos
  por **nome** se o modelo mudar e o `ctrl = 0` do `reset` trava as hélices até um comando novo.
- **Neutralidade provada (`run.py` §10, 13 checagens novas):** 500 passos de decisão (queda, repouso
  **com contactos** — até 24 por passo —, um `reset` a meio e comandos aleatórios) dão
  `qpos/qvel/ctrl/sensordata/energy/contactos` **idênticos ao bit** (max|Δ| = 0) com a animação **ligada**,
  **desligada** e com o modelo **upstream** do RL. O RL e o deploy não mudam: `cf.carregar()` e
  `HoverEnv()` continuam sem hélices por omissão (`HoverEnv(helices=True)` é opt-in, usado só pelo runner).
- **§10 à prova de regressão:** a checagem de rotação compara com um **θ derivado do COMANDO**
  (`ESCALA_VISUAL·√t_i` + avanço de 1.ª ordem), não com o θ lido do modelo — com θ = 0 ela era **vácia**
  (`Rz(0) = I` e os vértices em repouso batiam certo) e uma animação parada ou um ângulo errado (×1,5)
  passavam; se a adaptação faltar, o §10 **interrompe-se com uma FALHA limpa** (exit 1) em vez de rebentar
  com `ValueError` de broadcast.
- **Prova visual (2 imagens, offscreen EGL):**

  ```bash
  MUJOCO_GL=egl uv run --group hover-rl python experiments/09_drone_hover_rl/helices_render.py
  # → out/helices_1.png (passo 30, t = 0,60 s, θ = [5,415 −5,114 −5,114 5,415] rad)
  #   out/helices_2.png (passo 37, t = 0,74 s, θ = [7,434 −7,021 −7,021 7,434] rad)
  #   --sem-helices grava o par de controlo (out/helices_*_sem.png): modelo upstream, hélices paradas
  ```
- **Na janela:** `--sem-helices` desliga a animação (mesma física) e é a única forma de a desligar. O site
  **mostra** as hélices: o `sim_site.py` lança o `sim_view.py` (`comando_do_runner`, `sim_site.py:1117`)
  **sem** essa flag e é o `sim_view.py` que faz `HoverEnv(helices=not args.sem_helices)`. Quem fica **sem**
  hélices é o `view.py` (viewer com HUD, `HoverEnv()` em `view.py:994` → `cf.Helices` inerte) e, por
  omissão, o RL/deploy (`cf.carregar()` e `HoverEnv()`). Para animar também o `view.py`, ele passa a
  `HoverEnv(helices=True)` e acrescenta `cf.Helices(env.model).atualizar(env.model, env.data, dt)`
  antes do `sync()` (não foi feito: fora do âmbito desta peça).

### Câmara da janela 3D — TERCEIRA-PESSOA contínua, comandada pelo site (v2, 2026-10-10)

A janela mostra SÓ o 3D e a **câmara** é comandada pelo site (bloco «Câmara», `INTERFACE.md` §3.5) — tal
como o vento, é **só apresentação**: nunca toca na física, no episódio nem em nenhum comando. Em v2 a
câmara é **terceira-pessoa de jogo**: o alvo segue SEMPRE o drone e o site só comanda ângulo + distância.

**Widget v3 (2026-10-10, avaliação de UX em `out/ux/`)** — o contrato abaixo não mudou; mudou o comando: em
vez do pad v2 (círculo com uma esfera de mapeamento linear, que não ficava onde a câmara está), duas vistas
geométricas — **de cima** (nariz do drone para cima, ícone da câmara onde ela está, arrastar = orbitar) e
**de lado** (arco à volta do drone com o chão à escala, arrastar = subir/descer) —, zoom **logarítmico** com
limites por planta (drone real 0,6–15 m), roda do rato, setas/+/−/Home, **vistas rápidas** relativas ao nariz
(Atrás, Frente, Esquerda, Direita, De cima, À altura) e a leitura «atrás, à direita · 35° por cima · 1,95 m».
Duas correções medidas no ecrã real: o 1.º comando só com ângulos punha a câmara do drone real a **0,27 m**
(o servidor completava a distância com a do Crazyflie — agora usa o `camera_padrao` do modelo em uso) e um
zoom feito com o rato na janela era desfeito pelo comando seguinte do site (agora o site manda sempre os 3
valores do estado mostrado, que fora de um gesto é a câmara real). Geometria provada contra o MuJoCo em
`site/testes/camera-gestos.mts` (67/67).

- **Contrato:** bloco `"camera"` do `out/controle_vento.json` = `{"azimute","elevacao","distancia",
  "seq"}` — **SEM `alvo`** (faixas: azimute finito normalizado mod 360, elevacao [−90,90]°, distancia
  ]0,20] m; `seq` incrementado a CADA comando pelo servidor, como o `dinamico.seq`) +
  **`POST /api/camera`** (8.ª rota; corpo = subconjunto de `{azimute, elevacao, distancia}` + alias
  `distandia`; sem `seq` obrigatório — o `seq` do corpo é **ignorado** e o servidor carimba sempre o
  seu; merge parcial que nunca toca em
  `loop`/`reiniciar`/vento) + `camera_padrao`/`camera_atual` em `GET /api/state` e `GET /api/sim`.
- **Alvo SEMPRE no drone (`seguir_drone`, a cada frame):** `viewer.cam.lookat =
  body(CAM_CORPO).xpos + CAM_OFFSET` — COLA EXACTA a 1e-9, sem suavização (sem lag). `CAM_CORPO = "cf2"`
  (corpo do drone por nome) e `CAM_OFFSET = (0, 0, 0)` m (somado elemento a elemento a `xpos`; mudá-lo só
  muda o ponto olhado — a física nunca é tocada). Prova escrita a escrita no `teste_camera.py` §2.
- **Aplicação no runner:** os 3 valores de orbitar/zoom aplicam-se UMA VEZ por mudança de assinatura
  (`seq`+valores) nos atributos do `viewer.cam` — nunca a cada frame e nunca no `lookat`; entre comandos
  **o rato do viewer continua livre** (ângulos/distância sobrevivem até ao próximo comando) mas o **PAN é
  sobreposto** pelo seguimento (o alvo não sai do drone); sem viewer (`--sem-janela`) ignora sem erro.
- **Telemetria:** a 19.ª chave `"camera"` traz a câmara **REAL** (`{azimute, elevacao, distancia, alvo}`
  com `alvo` = `lookat` real = drone+offset), ou `null` sem viewer — é dela que sai o `camera_atual`
  (honestidade: sem dados não se inventa).
- **Default explícito:** `CAM_PADRAO` (constante = os 3 valores de `mjv_defaultFreeCamera(model)` deste
  modelo, **sem `alvo`**; azimute guardado mod 360, 340 ≡ −20 = a mesma pose) é aplicado no arranque e
  publicado como `camera_padrao`; **REPOR VISTA** = enviar os valores de `camera_padrao` como um comando
  normal.
- **Convenção de sinais** (a peça do front copia-a tal e qual, `INTERFACE.md` §4.4):
  `pos = alvo − d·f(azim,elev)` · `alvo = pos + d·f` com
  `f = [cos(elev)·cos(azim), cos(elev)·sin(azim), sin(elev)]` (graus→rad; azim 0° = +x, 90° = +y; elev
  positivo põe a câmara abaixo do alvo a olhar para cima; em v2 `alvo` = drone+offset). Confirmada
  empiricamente contra a pose real da câmara (`MjvScene.camera`, média dos 2 olhos estéreo): desvio máximo
  5,7e-8 m em 6 poses.
- **Validação exata do `POST /api/camera` (v2):** campo **presente** com valor `null` → **400** (`null`
  não é «ausente» — só a ausência completa do campo mantém o valor em vigor); **chave desconhecida**
  (incl. o `alvo` do contrato v1) → **400**; fora de faixa → 400; `distancia`+`distandia` juntos → 400
  (ambíguo). **Decisão documentada:** `{}` e `{"seq": n}` são **aceites com 200** — o subconjunto vazio é
  um «toque» que mantém os valores e carimba `seq` novo, e o `seq` do corpo é um aviso do cliente
  **IGNORADO** (o servidor carimba sempre o seu; deixa reenviar um bloco lido tal e qual). Assimetria
  intencional: no **ficheiro**, chaves desconhecidas (ex. `alvo` de ficheiros v1) são ignoradas em
  silêncio pelo runner (ficheiros velhos não rebentam); no **HTTP** rebentam com 400.
- **Robustez do backend (mini-reparo 2026-10-09, achados de verificação independente)**: o servidor usa
  `FILA_LIGACOES = 64` (`request_queue_size` do `ThreadingHTTPServer`, não o 5 do stdlib): num burst frio
  de 40 ligações simultâneas o código de antes deixava POSTs por servir (medido: 26–39 de 40 por ronda,
  `ConnectionResetError`/sem resposta, as que passavam demoravam segundos) e o de agora serve e aplica
  120/120 em 3 rondas (0,03 s/ronda), sem resets e sem JSON partido.

Prova repetível (`teste_camera.py`, **50/50** — §1 peças do contrato v2 e convenção de sinais (17) · §2
ciclo real com viewer falso instrumentado: seguimento provado escrita a escrita com o drone a MOVER-SE
pela física (REINICIAR + empuxo), rato preservado, PAN sobreposto, telemetria (15) · §3 servidor real na
porta **8561** (13): **burst frio de 40 ligações × 3 rondas**, 8 rotas, 400s (chaves desconhecidas, `null`,
faixas, alias) e a decisão `{}`/`seq` · §4 não-tautologia por mutação (5): seguimento removido, posição
velha, assinatura sem `seq`, validação de desconhecidas removida e validação de `null` removida fazem o
§1/§2 FALHAR):

```bash
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_camera.py   # 50/50, exit 0
```

### Módulo de câmara FPV — a câmara que o drone VÊ (2026-10-11)

Não confundir com a câmara da JANELA 3D (secção acima, apresentação): esta é o **módulo de câmara real
emulado**, montado **na frente do drone** (`<camera fpv>`, a olhar para +x) e transmitido para o site — a
mesma experiência de um módulo de câmara Raspberry Pi ligado ao RPi 5 por CSI-2.

**A peça (real, no catálogo)**: `models/drone_rpi/componentes.json` → `cameras` tem os dois módulos
oficiais, com fontes e grau de confiança: **Raspberry Pi Camera Module 3** (Sony IMX708, 11,9 MP
4608×2592, píxel 1,4 µm, FoV 75° diag/66°H×41°V, f=4,74 mm F1.8, 25×24×11,5 mm, 4 g) e a **Wide**
(FoV 120° diag/102°H×67°V, f=2,75 mm F2.2, foco PDAF 5 cm–∞, 25×24×12,4 mm, 4 g). A **Wide** é a do
build ativo (`builds.json` → `camera`), montada no nariz com **massa real** (entra no orçamento: +4 g,
ΔCM ≈ +0,27 mm — provado em `valida_real.py` A3a–A3d); troca-se com `hardware.py montar/usar`, como
qualquer peça. Fontes: `pesquisas/relatorio-modulos-camera-rpi.md` (tabela oficial + driver `imx708.c`).

**O emulador (`lab/camera_rpi.py`)** reproduz a experiência do hardware real — e só o que é real:

| o que | como é no módulo real | como está aqui |
|---|---|---|
| modos de sensor | 4608×2592@14,35 · 2304×1296@56,03 (binning, FOV completo) · 1536×864@120,13 (recorte 3072×1728 = 2/3 do FOV) | **os mesmos**, com os mesmos crops → o FoV de cada modo é o da janela real |
| modos de vídeo | 1080p50 · 720p100 · 480p120 (product brief) | **os mesmos** (+ os modos nativos do sensor), por omissão **1080p50** |
| megapixels | sensor 11,9 MP; saída 2,1 MP (1080p) | **os mesmos** (o site mostra MP de sensor e de saída) |
| ótica | FoV publicado 102°H×67°V (Wide) | `fovy` = FoV VERTICAL publicado × recorte do modo (fórmula fechada provada; os resíduos da tabela publicada — internamente inconsistente — estão ditos em `fovy_graus`) |
| JPEG | `rpicam-vid --quality` default **50** | **qualidade 50**, bytes reais → bitrate real |
| latência | MJPEG 1080p publicado 150–300 ms | modelo de estágios **cumprido na entrega** (116 ms a 1080p50; o mesmo modelo a 1080p30 dá 163 ms, dentro da faixa) |
| CPU no Pi 5 | JPEG é **SOFTWARE** (o Pi 5 não tem encoder hardware) | modelo por etapa com faixas/fontes (0,94 núcleo A76 a 1080p50) **+ o medido neste PC**, sempre separados |

O que **não** é reproduzido (dito, nunca fingido): o merge HDR do modo 2304×1296p30 (existe na tabela,
recusa-se com erro), o autofoco PDAF, a distorção da lente, o ruído de sensor e o rolling shutter.

**O pipeline** (`ModuloCamera`): thread própria que captura ao ritmo do modo ao **relógio de parede** (o
cristal do sensor corre em tempo real — a pausa e o `--fator-tempo` não o mudam); o estado do simulador
chega por `apontar(data)` a cada passo de decisão (cópia de ~5 µs, na thread do simulador); cada quadro é
renderizado na **proporção da janela de recorte** do modo (é assim que o FoV fica correto sem redimensionar
nada — a única fatia posterior é o 4:3 do 480p120) e codificado em JPEG; e cada quadro só fica disponível
`latencia_modelada()` ms depois da captura — a latência real do pipeline, reproduzida.

**O stream** (padrão do exemplo *web streaming* do picamera2): o runner escreve `out/fpv/quadro.jpg` +
`out/fpv/estado.json` (atómico, só o ÚLTIMO quadro) e o `sim_site.py` serve-o em
**`GET /api/fpv.mjpg`** (`multipart/x-mixed-replace`, partes `image/jpeg`, `Cache-Control: no-cache` —
clientes lentos perdem frames em vez de acumular atraso) mais `GET /api/fpv.jpg`, `GET /api/fpv/estado`
e **`POST /api/fpv`** `{ligada?, modo?}` (bloco `fpv` do controlo, `seq` do servidor). O site mostra a
imagem ao vivo e as métricas; o painel RPi 5 ganha o custo da câmara por etapa.

**Medido nesta máquina** (render + ISP + JPEG, sem a simulação a correr):

| modo | saída | fps nominal | host ms/quadro | JPEG q50 | latência modelo | CPU Pi 5 (modelo) |
|---|---|---|---|---|---|---|
| `480p120` | 640×480 | 120,00 | 1,2 | 6 KB | 56 ms | 0,45 núcleo |
| `720p100` | 1280×720 | 100,00 | 2,6 | 15 KB | 68 ms | 0,84 núcleo |
| **`1080p50`** (omissão) | 1920×1080 | 50,00 | 5,7 | 34 KB | 116 ms | 0,94 núcleo |
| `2304x1296p56` | 2304×1296 | 56,03 | 8,4 | 48 KB | 118 ms | 1,43 núcleos |
| `1536x864p120` | 1536×864 | 120,13 | 3,6 | 21 KB | 67 ms | 1,36 núcleos |
| `4608x2592p14` (11,9 MP) | 4608×2592 | 14,35 | 41,9 | 187 KB | 399 ms | 1,46 núcleos |

Todos os modos sustentam os seus fps nominais neste PC (o 11,9 MP@14,35 fps leva 42 ms dos 70 ms do
período); a cadência medida no runner é 48,2–49,9 fps a 1080p50 (nominal 50) e o teste exige ±10 %. Os
`host ms/quadro` da tabela são do pipeline **sozinho**; com o runner a correr (simulação + política ao
mesmo tempo) o `host_ms` da telemetria sobe (≈17 ms a 1080p50 nesta máquina) — é o medido, e vai sempre
rotulado como tal.
O custo do Pi 5 é MODELO (faixas e fontes de `pesquisas/relatorio-pipeline-camera-rpi5-custo-cpu.md`:
aquisição CSI 0–3 % + controlo do ISP 8–12 % + cópias 8–15 % + **JPEG software 50–80 %** + transporte,
todos % de 1 núcleo A76; a comparação com H.264 x264 software — whitepaper oficial RP-010033-WP-1 —
vai no resultado e no painel, como nota); o `host_ms` publicado é o MEDIDO neste PC e nunca se mistura
com o modelo.

**Validação**: `teste_fpv.py` — **78/78 checagens** (§1 especificação catálogo×emulador + fórmulas do
FoV + modelos de CPU/latência · §2 JPEG por modo + qualidade + latência cumprida + validação do controlo
· §3 cadência real em thread ±10 % · §4 runner e servidor reais: stream MJPEG **que avança** (partes
distintas), POST, estado **velho marcado como velho**, painel RPi 5 e os valores do MODELO do Pi 5
separados do MEDIDO no host por número, não só por rótulo) e **4/4 mutações** (§5: cada mutação textual
nas fontes FALHA a checagem certa — o teste não é tautológico). Mais as suites existentes, todas verdes
depois da integração (`teste_camera.py` 50/50, `teste_parar_vento.py` 15/15, `teste_controle_voo.py`
TUDO OK, `teste_arranque_loop.py` 68/68, `run.py` 287/287, pytest da skill 37/37) e as do site
(`test:fpv` 22/22, `test:camera` 20/20+75/75, `test:planta` 72/72, `test:voo` 53/53, build+lint).

### Câmara da SIMULAÇÃO — a segunda vista, trocável com a FPV (2026-10-11)

Além da FPV (a câmara do módulo, à frente do drone), o módulo emulado tem uma **segunda fonte de
imagem**: a «Câmara da Simulação» — a vista 3.ª-pessoa da simulação a correr (o que a janela mostraria),
renderizada pelo MESMO pipeline (mesmos modos/fps/JPEG/latência) e transmitida em
**`GET /api/simulacao.mjpg`**. O site tem um seletor de fonte no bloco «Câmara FPV»
(**FPV (bordo) | Simulação (3.ª pessoa)**) que troca a imagem — é isto que permite **testar e fazer tudo
pelo site, sem janela**: o widget de câmara do site (orbitar/zoom) comanda a vista da simulação mesmo sem
viewer, e os dois streams correm ao mesmo tempo (`out/fpv/quadro.jpg` e `out/fpv/quadro_sim.jpg`).

HONESTIDADE: a vista da simulação **não é hardware de bordo** — o seu `custo_pi5` é `null` (não há CPU de
Raspberry Pi a contabilizar para uma vista do simulador; só o `host_ms` medido) e o painel RPi 5 mantém o
custo da câmara FPV apenas. O FoV desta fonte é o global do MuJoCo (45° — a câmara livre não tem FoV de
modo; documentado no `lab/camera_rpi.py`). Com os DOIS streams a 1080p50 o host satura: **27–46 fps por stream** (50 nominais) a PC carregado, ~43 a PC livre — é um orçamento de HOST, não do módulo: a fidelidade ±10 % da taxa nominal prova-se com o módulo isolado (§3 do teste, com retentativas sob carga) e, para ver os dois a 50 fps, corre o `sim_site` sem mais nada a competir por CPU/GPU.

### Rajadas de vento — estado SEMPRE visível (remediação UX, 2026-10-11)

A avaliação `uxui-evaluator` do painel de vento dinâmico (`pesquisas/ux-rajadas-avaliacao.json`, score
61/fair) apontou que não ficava claro quando as rajadas corriam nem em que modo; as remediações ficaram
aplicadas no painel (`controlos.tsx`, teste `site/testes/rajadas-ux.mts` 43/43):

- **faixa de estado sticky** com 3 estados exaustivos: `PARADO` · `A CORRER — RAJADAS|ALEATÓRIA|DRYDEN` ·
  `RAJADA EM CURSO +X,X m/s` (derivada da física: |‖vento_vec‖ − base| > 0,05 m/s) — durante a rajada
  mostra-se o MODO de origem (responde a «está no modo aleatório ou não»);
- **progresso dos instantâneos** (RAJADA/FRENTE AGORA) com a **duração comandada** rotulada como tal;
- **léxico único** (`ROTULOS_MODO_ESTADO`) em toggle/faixa/botões/toasts — zero divergências de rótulo;
- **salvaguarda anti-esquecimento**: com dinâmica ativa, o selo `selo-rajadas-ativas` vive na **barra
  crítica global** (visível em qualquer secção; clique abre o painel);
- params em 2 linhas com unidades naturais («p 0,40 por passo · rajadas de 0,5 s (25 passos) até 3,0 m/s»).

## Computador de bordo Arduino (2026-10-12)

O dono decidiu que TUDO corre num **Arduino** (estimador + estabilização + movimento + olhar para um círculo, com
algoritmos clássicos). A pesquisa (`pesquisas/2026-10-12-para-um-quadricoptero-grande-*.md`, Q5/Q6) concluiu que a
Pi Camera Module 3 (CSI-2) **não existe em Arduino**; só as 3 placas STM32H747 (Portenta H7, Nicla Vision, GIGA R1)
têm M7 480 MHz + M4 240 MHz, 2 MB flash e 1 MB RAM. O catálogo ganhou as peças REAIS e um build novo
**`endurance_15pol_arduino`** (o p50b com o computador trocado; **o build ativo continua o p50b**).

| peça (`componentes.json`) | números das fichas oficiais | estimado (e porquê) |
|---|---|---|
| `arduino_portenta_h7` (`eletronica`) | STM32H747XI: M7 480 MHz (FPU **dupla**, L1 16+16 kB) + M4 240 MHz (FPU simples), 2 MB flash, 1 MB RAM, 8 MB SDRAM, 16 MB QSPI, 10 PWM (HD) + 7 (MKR), DCMI 8 bit a 80 MHz, JPEG por hardware, 66,04×25,40 mm; **sem IMU**; pico 230 mA a 5 V = 1,15 W | massa **10 g** (a loja diz 0,2 kg, a Mouser 158,8 g: são massas de EXPEDIÇÃO; a shield de igual pegada pesa 8 g); consumo 0,66 W em repouso e 1,0 W a processar = **medido por terceiros** (MDPI 2025, não em voo) |
| `portenta_vision_shield_hm0360` / `_hm01b0` (`cameras`) | Rev 2 HM0360 640×480 3,6 µm 1/6″ (VGA 60 fps; QVGA 60 por binning) · Rev 1 HM01B0 320×320 1/11″ (matriz inteira ≤ 51 fps, **QVGA 60 só na janela 320×240**, binning 120 fps) · **mono 8 bit**, DVP paralelo → DCMI (sem CSI-2, sem ISP), 8 g | **FoV/lente**: a Arduino não os publica → módulos de referência da Himax (HM0360 70,1°×55,4°, f 1,56 mm; HM01B0 87°×87°, f 0,66 mm) |
| `arduino_nicla_vision`, `arduino_giga_r1` (para comparação) | Nicla: GC2145 2 MP **RGB** (f 2,2 mm, f/2,2, 80°), LSM6DSOX, 105 mA na captura, 2 g · GIGA: +8 MB SDRAM, PWM 13 na ficha vs 12 na loja, conector Arducam 20 pinos, OV7675 RGB a **15 fps** | GIGA: massa 37 g (pegada do Mega 2560, 37 g oficiais) e consumo por analogia |

**Build novo vs p50b** (modelo, `hardware.py comparar`): **2137 g** (−46 g: sai RPi 5 52 g + FC 8 g + Pi Camera 4 g,
entram Portenta 10 g + shield 8 g) · eletrónica 5 V **1,3 W** (era 6,5 W) · pairagem **186,7 W** (era 198,1 W; −5,7 %) ·
11,44 g/W (11,02) · T/W 2,67 (2,62) · **autonomia 70,0 min** (65,8 min; +4,2 min). Mesmo frame 1950 mm, MN4004 KV300 +
P15×5, 6S2P P50B, ESC e sensores (o BMI088 externo fica: o Portenta não tem IMU).

**Emulador de câmara** (`lab/camera_rpi.py`, só no que foi preciso — a Pi Camera fica EXATAMENTE como era): cada módulo
tem os **seus modos** (`MODULOS[id]["modos"]`; o IMX708 mantém `MODOS`) e `ModuloCamera` recusa os do outro mundo;
`Modo.mono` converte o render para **luma BT.601 de 8 bit** (1 canal) e `Modo.sensor_altura_px` dá o FoV certo por
janela; a **latência** é a do caminho DCMI (1 período + 3 ms + 1 ms ≈ **20,7 ms** a QVGA60, contra 116 ms do MJPEG da
Pi; os 2 termos finais são ASSUMIDOS); `custo_pi5: None` (não há Pi) e o modo por omissão é o da biblioteca Camera da
Arduino (**QVGA30**). Prova: `teste_arduino_catalogo.py` (**46 checagens** + **6 de mutação**: controlo + 5 mutações em
cópias, cada uma falha a checagem certa); nada regride: `run.py` 296/296 (era 287), `valida_real.py` 150/150 (era 141:
+9 checagens A do build novo), `teste_fpv.py` 91/91 (era 87: +4 do «travão da duplicação» para as 2 câmaras novas);
os dois testes que já estavam vermelhos antes (defeito do TESTE, não do código) foram reparados depois:
`teste_camera.py` 50/50 (a telemetria tinha as 19 chaves do contrato intactas; o teste lia «depois só aditivas» com uma
lista fechada a que faltava `multi_ia`) e o `test_efeito_de_solo` do pytest da skill, 37/37 (o limiar «≥ 1,15 a 0,5·D» era
do frame de 650 mm: com 1950 mm os rotores ficam a 3,6 D e o ganho é ×1,0739, o da conta fechada de Sanchez-Cuevas 2017).

**Ressalvas** (ditas, não escondidas): (1) o **FoV das shields é ESTIMADO** — medir com um alvo angular em hardware;
(2) numa câmara **mono** o marcador magenta (luma 0,41–0,51) distingue-se só por brilho — um alvo branco/IR é melhor e o
detetor por cor do `visao.py` tem de passar a limiar de brilho; (3) a ficha da shield diz «320×320 QVGA 60 FPS»
mas os 60 fps são da janela 320×240; (4) `atraso_comando_ms` fica em 8 ms (conservador; o laço M4 a 500 Hz sugere
2–4 ms — a medir); (5) `sim_view.py`/`sim_site.py` ainda passam `OMISSAO_MODO` (1080p50) ao módulo: com este build
ativo o stream FPV ficaria desligado (ValueError tratado) até usarem `cam_rpi.modo_omissao(modulo)`; (6) nenhuma medida
em placa: voo do Portenta, jitter do Mbed OS, DShot/PWM por timer e ciclos reais do M7 continuam por provar.

<!-- BEGIN:cascata-classica (gerado por avaliar_classico.py + controlo_classico.py; números em out/classico/*.json) -->
## Cascata clássica — protótipo de referência (2026-10-12)

> **Decisão do dono (2026-10-12)**: estabilização, rotação (yaw livre) e movimentação passam a ser um algoritmo **clássico**
> (não-IA), reimplementado a partir de papers/documentação (só o PX4 é BSD-3; ArduPilot/Betaflight/Crazyflie/MultiWii são
> GPLv3 — nenhuma linha copiada, fontes nos docstrings). Este é o **protótipo de REFERÊNCIA em Python** que a atividade A
> (firmware C++, `firmware/`) vai portar; **fase 1: SEM VENTO**. Pesquisa de base:
> `pesquisas/2026-10-12-para-um-quadricoptero-grande-*.md` (§1, Q2.1, Q3, Q4). A decisão clássico-vs-RL sai **daqui, da
> medição no simulador** (a literatura não compara nada em ~2 kg/15″).

| ficheiro | o que é |
|---|---|
| `controlo_classico.py` | `CascataClassica` (float64, escalares, equações explícitas), `GanhosCascata` (`@dataclass`) derivada da planta por `ganhos_de_hardware(env)`, `margens_cascata`, `EstimadorClassico` (substituto direto do `EstimadorBordo`), funções puras (`raiz_quadrada`, `direcao_empuxo`, `erro_atitude`, `velocidade_no_rumo`, `cmd_para_acao`, `acelerador_de_coletivo`) |
| `avaliar_classico.py` | a medição cascata **vs** a RL `out/real_1950_voo_final/final.zip` no `DroneRealEnv` (mesma planta, sementes, planos, DR e ruído) → `out/classico/avaliacao.json`; `--calibrar` / `--calibrar-yaw` = as varreduras de ganhos e de yaw nas sementes de calibração → `out/classico/calibracao*.json` |
| `teste_controlo_classico.py` | **38 checagens** (§1 25 fórmulas fechadas · §2 8 malha fechada no simulador · §3 5 incl. **4 mutações** apanhadas: sinal do yaw, falta do ÷cosφcosθ, prioridade de inclinação perdida, anti-windup desligado) + exit code |

```bash
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_controlo_classico.py [--rapido]   # 38 checagens, ~30 s
uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_classico.py [--rapido]          # ~3 min (8–10 processos) → out/classico/avaliacao.json
uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_classico.py --calibrar         # ~7 min → out/classico/calibracao.json
uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_classico.py --calibrar-yaw    # ~1 min → out/classico/calibracao_yaw.json
```

### Arquitetura e interface (a que a atividade A porta)

```
cmd {vx,vy,vz,yaw_taxa,modo[,yaw,z_alvo]} (referencial do RUMO: W=+vx frente, A=+vy esquerda, Q=+vz cima)
  └▶ conformador (acel./jerk-limitado + modelo de seguimento) ─▶ posição (P, raiz quadrada) ─▶ velocidade (PI(D), saída = ACELERAÇÃO,
     FF de aceleração e de arrasto) ─▶ inclinação desejada + EMPUXO COLETIVO ÷(cosφ·cosθ) ─▶ atitude (P) com PRIORIDADE DE INCLINAÇÃO
     + peso de yaw + FF da taxa de inclinação ─▶ taxas p,q,r ─▶ [FC 500 Hz = fc.py: laço de taxa + mistura X + airmode — NÃO é daqui]
```

`coletivo, taxas_sp = CascataClassica(ganhos).passo(est, giro, cmd, dt)` — `est` (atributos ou chaves `roll pitch psi h vz vx vy x y`, o
mesmo do `estimador.py` e da struct `Saida` do núcleo C++), `giro` (taxas medidas), `cmd`, `dt`; devolve o **empuxo coletivo normalizado
pelo peso** (T/(m·g), 1,0 = pairagem) e as taxas (rad/s, corpo). A conversão para a ação do env é **à parte** (`cmd_para_acao`:
a₀ = c − 1, a₁₂₃ = taxas/[2,2,1]) e para o acelerador do firmware também (`acelerador_de_coletivo`: u = u_pair(V)·√c — a
**compensação de tensão** da bateria vive no `u_pair`, a mesma conta do `DroneRealEnv._comando`). Modos: `velocidade` (v = 0 **segura a
posição**, como o PX4; `yaw_taxa = 0` **mantém o rumo**) e `yaw_alvo` (rumo absoluto). `armar(False)` = **neutro** (coletivo 0, taxas 0,
integradores a zero). Referências travadas ao armar (x, y, ψ, altura); `z_alvo` = descolar (os Q/E a meio movem o alvo). Piso de
altitude = o do contrato r11 (0,25 m do CM) e teto = 90 % do alcance do ToF (3,24 m: acima o drone perde a altura).

### Ganhos e limites DERIVADOS da planta (`ganhos_de_hardware(env)`)

A malha de taxa do `fc.py` (PID + PT1 de 90/60 Hz + motor de 1.ª ordem τ_m = 55,8 ms + atraso de comando 8 ms + meia retenção da
decisão + giroscópio) tem **cruzamento de ganho ωc = 8,43 rad/s (1,34 Hz)** — o «≈ 8,2 rad/s» da pesquisa, agora calculado da
planta (`resposta_malha_taxa`). Cada laço externo vê o interno em malha fechada; as **margens de fase** abaixo são da resposta real
(`margens_cascata`), confirmadas pelos degraus medidos.

| laço | ganho (fórmula fechada) | valor | PM / GM |
|---|---|---|---|
| taxa (fc.py) | ωc (cruzamento de L) | 8,43 rad/s | 43° / 17 dB |
| atitude | K_att = ωc/**2,5** | 3,37 s⁻¹ | 62° / 7,5 dB |
| velocidade horizontal | K_vel = K_att/**4**, K_i = K_vel²/**2**, K_d = 0 | 0,84 s⁻¹, 0,356 s⁻² | 50° / 17 dB |
| posição | K_pos = K_vel/**2,5** (raiz quadrada, a = 1 m/s²) | 0,337 s⁻¹ | 69° / 14 dB |
| velocidade vertical | K_vz = 1/(4·τ_m), K_iz = K_vz²/4 | 4,48 s⁻¹, 5,0 s⁻² | 57° / 22 dB |
| altura | K_pz = K_vz/4 | 1,12 s⁻¹ | 79° / 18 dB |

**Porque não «razão 4» em tudo** (a regra da pesquisa, sem fonte primária): a PM do laço de atitude é 62° a 2,5 e só 48° a 2,0 —
2,5 é o primeiro ponto com PM ≥ 60°; a de posição é 69° a 2,5 (57° a 2,0); a de velocidade fica em 4 (62° com K_i = K²/4) e o
integral usa 2 (PM 50°) — nas sementes de calibração, face ao integral 4: hover 7,2 → 5,1 cm e seguimento com DR 0,419 → 0,359 m, sem mais sobressinal. A
varredura (tabela de calibração, abaixo) mostra o ponto de partida da pesquisa (4/4/4/4) a dar **hover de 35 cm** e seguimento de 0,50 m: está
longe do ótimo desta planta. Os pontos de partida «K_att ≈ 2–4, K_vel ≈ 0,5–1, K_pos ≈ 0,12–0,25» da pesquisa ficam confirmados
(K_att 3,37, K_vel 0,84; K_pos 0,337 fica ligeiramente acima).

Limites e conformadores (todos por fórmula): inclinação **30°** = min(30°, acos(1,3/1,8)) (a_xy,máx = g·tan 30° = 5,66 m/s²; os comandos
usam g·tan 17° = 3,00 m/s², jerk = a·ω_att/2 = 8,0 m/s³, ω_att = √(K_att·ωc) = 5,3 rad/s); coletivo ∈ [0,3; 1,8];
conformador vertical a = ½(c_max − 1)g = 3,92 m/s², jerk = a/(2τ_m) = 35,1 m/s³; modelo de seguimento τ = 1/ωc = 0,119 s (a
realimentação compara com a referência atrasada pela malha de atitude, senão conta o atraso duas vezes e dá 20 % de sobressinal);
FF de arrasto k = d_rotor = 0,30 s⁻¹ (`aero.d_xy`); anti-windup por retro-cálculo (k_aw = 2/K_vel); empuxo coletivo
÷(cosφ·cosθ) (compensação de inclinação).

### Limites de yaw IDENTIFICADOS no simulador (`identificar_yaw`, planta nominal, semente de calibração)

| grandeza | fórmula (arrasto de rotor) | **medido** |
|---|---|---|
| amortecimento de yaw c_yaw (N·m·s/rad) | d·m·r² = 0,30·2,18·0,975² = 0,622 | **0,487** (−22 %: o integral do PID de yaw do FC em regime, 0,1…0,5 rad/s, dá u/r = 0,438 acelerador/(rad/s), linear até 0,5) |
| taxa terminal com a mistura saturada | — | **0,95 rad/s** (54 °/s) — mas com 45 % de passos saturados e **perda do controlo de altitude** (o diferencial de yaw acrescenta empuxo ∝ d²: o coletivo, já no mínimo, não compensa; num ensaio longo à parte subiu 9 m em 8 s) |
| aceleração inicial de yaw (saturada) | α_z·0,47 = 1,12 rad/s² | 0,81 rad/s² (47 °/s², média dos 1.ºs 0,5 s: o rotor demora a rodar) |
| **limite adotado**: quota f_yaw = 0,6 da folga min(1−u_pair, u_pair−idle) = 0,370 | a = α_z·0,222 | **0,53 rad/s² (30 °/s²) e 0,51 rad/s (29 °/s)**, sem saturar a mistura |

O ArduPilot sugere `ATC_ACC_Y_MAX` 200/100/90 °/s² para hélices de 10/20/30″ (≈ 150 °/s² a 15″): este frame faz **30 °/s²** (÷5; J_zz = 0,467 kg·m²,
autoridade de yaw ÷10–12) — o ponto de partida da pesquisa não serve aqui. A quota 0,6 é onde a mistura ainda não satura (varredura nas sementes de
calibração, `avaliar_classico.py --calibrar-yaw`): a 0,8 satura 5 % dos passos e a altitude perde 25 cm num degrau de 90°; a 1,0 satura 11 %, o roll
sobe de 0,3° para 1,1° e a altitude perde **120 cm** (a «contra-prova» do teste repete-o: sem limites de yaw a mistura satura 99,7 % dos passos e o
roll/pitch deixa de seguir — a prioridade de inclinação só se mantém porque os limites derivados do frame impedem o yaw de saturar a mistura, que o `fc.py` escala em bloco). O
diferencial de yaw acrescenta empuxo T ∝ u²: Σ(u₀ ± d)² = 4u₀² + 4d² ⇒ a pré-compensação **só do equilíbrio**, c − (d/u_pair)², reduz \|Δz\| de 14 para 8 cm;
incluir o termo de aceleração de yaw **piora** (23 cm: o empuxo chega depois do comando) — fica desligado (`comp_yaw_acel = 0`).

| yaw — configuração (sementes de calibração) | degrau 90°: subida 10–90 % (s) | assent. 5 % (s) | \|Δz\| máx. (cm) | roll pico (°) | mistura saturada (%) | arco 0,5 rad/s: \|Δz\| (cm) / ⟨v⟩ (m/s) / saturada (%) |
|---|---|---|---|---|---|---|
| base (f_yaw 0,6 · peso 0,7 · compensação de equilíbrio) | 2,51 | 3,54 | 8,2 | 0,26 | 0,0 | 6,7 / 1,111 / 0,2 |
| f_yaw 0,8 | 1,99 | 2,88 | 24,7 | 0,31 | 4,6 | 10,1 / 1,115 / 1,5 |
| f_yaw 1,0 (toda a folga) | 1,70 | 2,55 | 120,4 | 1,09 | 11,1 | 15,6 / 1,113 / 2,9 |
| peso de yaw 0,4 (PX4) | 2,62 | 3,86 | 8,0 | 0,25 | 0,0 | 6,5 / 1,111 / 0,2 |
| peso de yaw 1,0 | 2,49 | 3,48 | 8,3 | 0,26 | 0,0 | 6,9 / 1,112 / 0,2 |
| sem pré-compensação do empuxo de yaw | 2,51 | 3,54 | 14,0 | 0,26 | 0,0 | 12,0 / 1,113 / 0,1 |
| pré-compensação com o termo de aceleração | 2,52 | 3,54 | 23,0 | 0,29 | 0,1 | 20,9 / 1,106 / 0,2 |
| u/r da fórmula (arrasto de rotor, 0,56) em vez do identificado | 3,15 | 4,19 | 8,6 | 0,27 | 0,0 | 7,6 / 1,059 / 0,0 |


### Estimador melhorado — o que realmente limitava o hover (`EstimadorClassico`)

O `EstimadorBordo` integra o giroscópio **sem tirar o viés** (σ = 3,5 mrad/s por voo no BMI088): o viés entra no **rumo** (deriva) e na
**velocidade do fluxo**, v = d·(q − Ω_y) = v + d·b — 3,5 mm/s a 1 m de altura = **~10 cm de deriva de odometria em 30 s**. A RL e a cascata com o
estimador de bordo têm exatamente esse erro (tabela: «deriva da odometria» 9,3 vs 9,6 cm). Três correções, todas **medidas** nas sementes de
calibração (tabela de calibração):
1. **calibração do giroscópio no chão** (1,0 s parado, motores em idle, antes de armar — o «gyro calibration» de PX4/ArduPilot; fora do relógio do
   episódio): hover 11,1 → 5,1 cm (a maior das três; deriva de rumo ÷3);
2. **portão do acelerómetro**: um multirrotor mede o empuxo (sempre ao longo de z_corpo) e não a gravidade quando acelera — a correção
   «para o acelerómetro» puxa a inclinação para zero durante as manobras (medido: a 23° de inclinação o erro de atitude era de 2,5°). O ganho é escalado por 1/(1+(‖a_h‖/0,15)²):
   sobressinal do degrau 17,6 → 9,1 %, ‖v−v_ref‖ 0,511 → 0,480 m/s;
3. **observador de altura de 3.ª ordem** (ĥ, v̂_z, viés do acelerómetro vertical): no de 2.ª ordem o viés do acelerómetro (σ 0,05 m/s² + 0,5 % de escala ≈ 0,1 m/s²)
   dá um viés de v̂_z = 0,35·b ≈ +4 cm/s (medido: v̂_z ≈ +0,04 m/s em hover) e o laço segurava a altura 3–4 cm abaixo do alvo; hover \|Δz\| RMS 2,4 → 0,6 cm.
**Mahony PI** (parte integral do filtro complementar, viés de p/q estimado do erro do acelerómetro): **medido, não ajuda** — k_i = 0,02 /s²:
hover 4,8 cm (base 5,1) e seguimento 0,292 m (base 0,291); 0,1: seguimento pior (0,304 m); 0,5: instável (hover 18,0 cm, seguimento 0,437 m) — o erro que o PI integra
é falso durante as manobras (o acelerómetro não vê a inclinação), exatamente o argumento físico acima. A calibração no chão é o equivalente robusto.

### Resultados MEDIDOS — cascata vs RL, SEM VENTO

**Protocolo (igual para as duas)**: `DroneRealEnv` com o build do `hardware.json` da política (`endurance_15pol_p50b`), `env.step` a 50 Hz com
10 passos de física de 2 ms, **12 sementes de avaliação 5000…5011** (⇒ os mesmos planos WASDQE, o mesmo ruído dos sensores e, com DR, as mesmas
peças sorteadas); a RL em ação determinística (`avaliar_real.py` é o modelo). Os ganhos da cascata foram afinados em **sementes de calibração 9000…9007
que não entram aqui**. A RL recebe `p_ref`/`v_ref` na observação; a cascata só o `v_ref` como comando no referencial do rumo (e a altura de descolagem).
Variantes da cascata: **estimador de bordo** (o MESMO que a RL vê, sem calibração — a comparação «mesma informação») · **estimador melhorado** · e
**melhorado + `p_ref`** (a referência de posição integra a velocidade comandada, como a RL faz; o modo por omissão, `velocidade`, é o do PX4 e não a
persegue). Médias ± desvio sobre as sementes; «(n/12)» = nas quantas a métrica existe (o assentamento pode não acontecer na janela de 8 s). Métricas
de erro de seguimento são do referencial do mundo (o do env); o env sorteia ainda um rumo inicial ±5° que nenhum controlador conhece — a mesma
métrica no referencial de arranque dá o mesmo valor ±1 % (campos `*_arranque` no JSON).

#### Sem domain randomization

**Hover 30 s** (12 sementes, janela t ∈ [10, 30] s; quedas: rl 0/12, cascata_bordo 0/12, cascata_melhorado 0/12)

| | RL | cascata · est. de bordo | cascata · est. melhorado |
|---|---|---|---|
| ‖xy‖ RMS (cm) | 13,0 ± 5,5 | 10,4 ± 5,0 | 3,9 ± 0,8 |
| ‖xy‖ máx. (cm) | 17,5 ± 6,9 | 14,9 ± 5,4 | 7,1 ± 1,3 |
| \|Δz\| RMS (cm) | 2,0 ± 1,0 | 2,5 ± 1,6 | 0,6 ± 0,1 |
| roll RMS (°) | 0,31 ± 0,02 | 0,08 ± 0,01 | 0,08 ± 0,01 |
| pitch RMS (°) | 0,50 ± 0,04 | 0,08 ± 0,01 | 0,08 ± 0,01 |
| deriva de rumo (°, módulo) | 2,6 ± 2,3 | 3,0 ± 2,8 | 0,8 ± 0,5 |
| esforço: RMS de Δu por passo de 2 ms | 0,0787 ± 0,0004 | 0,0780 ± 0,0004 | 0,0780 ± 0,0005 |
| potência média (W) | 215,5 ± 0,5 | 214,0 ± 0,6 | 214,0 ± 0,6 |
| estimador: deriva da odometria RMS (cm) | 9,3 ± 4,7 | 9,6 ± 4,5 | 1,9 ± 0,7 |
| estimador: erro de atitude RMS (°) | 0,76 ± 0,31 | 0,77 ± 0,31 | 0,42 ± 0,21 |

**Seguimento de planos WASDQE aleatórios** (12 sementes × 10 s, janela t ≥ 4 s; quedas: rl 0/12, cascata_bordo 0/12, cascata_melhorado 0/12, cascata_melhorado_ref 0/12)

| | RL | cascata · est. de bordo | cascata · est. melhorado | cascata · melhorado + `p_ref` |
|---|---|---|---|---|
| ‖v − v_ref‖ RMS (m/s) | 0,368 ± 0,068 | 0,408 ± 0,113 | 0,357 ± 0,093 | 0,361 ± 0,092 |
| ‖xy − p_ref‖ RMS (m) | 0,235 ± 0,078 | 0,404 ± 0,148 | 0,297 ± 0,127 | 0,262 ± 0,090 |
| \|z − z_ref\| RMS (m) | 0,042 ± 0,020 | 0,049 ± 0,032 | 0,036 ± 0,029 | 0,036 ± 0,029 |
| ‖xy − p_ref‖ média da 2.ª metade (m) — a métrica do `avaliar_real.py` | 0,213 ± 0,089 | 0,392 ± 0,138 | 0,263 ± 0,122 | 0,217 ± 0,079 |

Menor erro que a RL, nas sementes comuns (mesmos planos): `hover_xy_rms cascata_bordo<rl` 11/12; `hover_xy_rms cascata_melhorado<rl` 11/12; `seguimento_v_rms cascata_melhorado<rl` 7/12; `seguimento_xy_rms cascata_melhorado<rl` 3/12; `seguimento_z_rms cascata_melhorado<rl` 7/12; `seguimento_v_rms cascata_melhorado_ref<rl` 6/12; `seguimento_xy_rms cascata_melhorado_ref<rl` 4/12; `seguimento_z_rms cascata_melhorado_ref<rl` 7/12.

**Degrau 0 → 1 m/s à frente (W)** (12 sementes; «(n/12)» = nas quantas o assentamento acontece dentro da janela)

| | RL | cascata · est. de bordo | cascata · est. melhorado | cascata · melhorado + `p_ref` |
|---|---|---|---|---|
| subida 10–90 % (s) | 0,36 ± 0,02 | 0,34 ± 0,01 | 0,35 ± 0,01 | 0,35 ± 0,01 |
| sobressinal (%) | 18,0 ± 2,0 | 19,0 ± 4,5 | 9,4 ± 2,1 | 9,9 ± 1,7 |
| assentamento 2 % (s) | 7,41 ± 0,61 (8/12) | 7,88 ± 0,00 (1/12) | 5,27 ± 1,18 (6/12) | 6,64 ± 0,72 (6/12) |
| assentamento 5 % (s) | 4,39 ± 1,94 | 7,08 ± 1,29 (6/12) | 3,42 ± 2,18 (11/12) | 3,32 ± 2,41 (11/12) |
| erro de regime (m/s) | -0,007 ± 0,009 | -0,085 ± 0,032 | -0,025 ± 0,033 | -0,025 ± 0,030 |
| afundamento após o pico (%) | 6,9 ± 1,2 | 10,0 ± 3,3 | 3,4 ± 3,0 | 4,4 ± 2,8 |

**Degrau 0 → 0,7 m/s a subir (Q; a partir de 0,5 m de altura para ficar no alcance do ToF, janela de 3,6 s)** (12 sementes; «(n/12)» = nas quantas o assentamento acontece dentro da janela)

| | RL | cascata · est. de bordo | cascata · est. melhorado | cascata · melhorado + `p_ref` |
|---|---|---|---|---|
| subida 10–90 % (s) | 0,22 ± 0,03 | 0,25 ± 0,01 | 0,26 ± 0,02 | 0,26 ± 0,02 |
| sobressinal (%) | 15,2 ± 4,1 | 9,2 ± 1,6 | 9,6 ± 2,3 | 9,6 ± 2,3 |
| assentamento 2 % (s) | 3,55 ± 0,04 (5/12) | 3,43 ± 0,05 (2/12) | 3,41 ± 0,16 (3/12) | 3,41 ± 0,16 (3/12) |
| assentamento 5 % (s) | 3,50 ± 0,06 (6/12) | 2,98 ± 0,24 (8/12) | 2,83 ± 0,83 (8/12) | 2,83 ± 0,83 (8/12) |
| erro de regime (m/s) | -0,001 ± 0,010 | 0,024 ± 0,007 | 0,015 ± 0,005 | 0,015 ± 0,005 |
| afundamento após o pico (%) | 13,3 ± 3,4 | 1,9 ± 1,7 | 2,4 ± 2,3 | 2,4 ± 2,3 |

**Degrau 0 → −1 m/s lateral (D)** (12 sementes; «(n/12)» = nas quantas o assentamento acontece dentro da janela)

| | RL | cascata · est. de bordo | cascata · est. melhorado | cascata · melhorado + `p_ref` |
|---|---|---|---|---|
| subida 10–90 % (s) | 0,34 ± 0,02 | 0,35 ± 0,01 | 0,35 ± 0,01 | 0,35 ± 0,01 |
| sobressinal (%) | 33,4 ± 2,0 | 15,4 ± 2,0 | 7,1 ± 1,1 | 8,0 ± 1,0 |
| assentamento 2 % (s) | 6,88 ± 1,10 (9/12) | — | 7,14 ± 0,00 (1/12) | 7,25 ± 0,08 (3/12) |
| assentamento 5 % (s) | 3,05 ± 1,66 | — | 1,17 ± 0,27 (6/12) | 4,20 ± 2,89 (11/12) |
| erro de regime (m/s) | 0,008 ± 0,007 | -0,105 ± 0,013 | -0,046 ± 0,014 | -0,040 ± 0,013 |
| afundamento após o pico (%) | 19,1 ± 1,9 | 12,1 ± 1,4 | 5,8 ± 1,3 | 5,5 ± 1,5 |

**Yaw** (só a cascata + estimador melhorado; a RL não roda; 12 sementes)

| teste | medido |
|---|---|
| degrau de rumo de 90° (`yaw_alvo`) | subida 10–90 % (s) 2,51 ± 0,02 · sobressinal (%) 0,17 ± 0,50 · assentamento 2 % / 5 % (s) 3,82 ± 0,06 / 3,53 ± 0,02 · erro final (°) 0,03 ± 0,52 · \|Δz\| máx. (cm) 8,6 ± 0,4 · roll/pitch pico (°) 0,25 ± 0,05 / 0,26 ± 0,07 · mistura saturada (% dos passos) 0,07 ± 0,03 |
| taxa de 0,5 rad/s (`yaw_taxa`) | taxa média (rad/s) 0,500 ± 0,002 · erro RMS (rad/s) 0,003 ± 0,001 · \|Δz\| máx. (cm) 8,5 ± 0,4 · mistura saturada (%) 0,10 ± 0,05 |
| avançar a 1 m/s e rodar 0,3 rad/s (arco) | raio ajustado (m) 3,31 ± 0,14 vs esperado 3,33 · desvio ao círculo RMS (cm) 1,7 ± 0,5 · ⟨v⟩ (m/s) 1,015 ± 0,034 · \|Δz\| máx. (cm) 3,2 ± 0,6 · roll pico (°) 5,2 ± 0,1 · mistura saturada (%) 0,00 ± 0,01 |
| avançar a 1 m/s e rodar 0,5 rad/s (arco) | raio ajustado (m) 2,21 ± 0,05 vs esperado 2,00 · desvio ao círculo RMS (cm) 3,7 ± 1,1 · ⟨v⟩ (m/s) 1,135 ± 0,021 · \|Δz\| máx. (cm) 7,2 ± 0,6 · roll pico (°) 8,9 ± 0,1 · mistura saturada (%) 0,20 ± 0,06 |


#### Com domain randomization ligado (massa, inércia, kf, motores, bateria, sensores, arrasto e atraso sorteados por episódio)

**Hover 30 s** (12 sementes, janela t ∈ [10, 30] s; quedas: rl 0/12, cascata_bordo 0/12, cascata_melhorado 0/12)

| | RL | cascata · est. de bordo | cascata · est. melhorado |
|---|---|---|---|
| ‖xy‖ RMS (cm) | 18,7 ± 9,5 | 16,9 ± 8,8 | 5,8 ± 2,0 |
| ‖xy‖ máx. (cm) | 25,8 ± 12,8 | 23,0 ± 10,7 | 9,7 ± 2,7 |
| \|Δz\| RMS (cm) | 2,1 ± 0,9 | 3,4 ± 1,4 | 0,6 ± 0,1 |
| roll RMS (°) | 0,39 ± 0,10 | 0,10 ± 0,02 | 0,10 ± 0,02 |
| pitch RMS (°) | 0,58 ± 0,08 | 0,10 ± 0,02 | 0,10 ± 0,02 |
| deriva de rumo (°, módulo) | 3,8 ± 3,5 | 4,0 ± 3,6 | 0,6 ± 0,4 |
| esforço: RMS de Δu por passo de 2 ms | 0,0811 ± 0,0040 | 0,0802 ± 0,0040 | 0,0801 ± 0,0040 |
| potência média (W) | 212,8 ± 22,9 | 211,2 ± 23,0 | 211,2 ± 23,0 |
| estimador: deriva da odometria RMS (cm) | 13,8 ± 8,4 | 14,2 ± 8,5 | 3,1 ± 1,5 |
| estimador: erro de atitude RMS (°) | 0,81 ± 0,49 | 0,82 ± 0,49 | 0,49 ± 0,23 |

**Seguimento de planos WASDQE aleatórios** (12 sementes × 10 s, janela t ≥ 4 s; quedas: rl 1/12, cascata_bordo 0/12, cascata_melhorado 0/12, cascata_melhorado_ref 0/12; médias SEM a(s) semente(s) [5007], onde alguma variante caiu)

| | RL | cascata · est. de bordo | cascata · est. melhorado | cascata · melhorado + `p_ref` |
|---|---|---|---|---|
| ‖v − v_ref‖ RMS (m/s) | 0,435 ± 0,210 | 0,463 ± 0,199 | 0,419 ± 0,182 | 0,420 ± 0,182 |
| ‖xy − p_ref‖ RMS (m) | 0,223 ± 0,061 | 0,406 ± 0,156 | 0,300 ± 0,146 | 0,248 ± 0,114 |
| \|z − z_ref\| RMS (m) | 0,043 ± 0,022 | 0,057 ± 0,032 | 0,047 ± 0,034 | 0,047 ± 0,034 |
| ‖xy − p_ref‖ média da 2.ª metade (m) — a métrica do `avaliar_real.py` | 0,204 ± 0,066 | 0,379 ± 0,177 | 0,280 ± 0,156 | 0,222 ± 0,117 |

Menor erro que a RL, nas sementes comuns (mesmos planos): `hover_xy_rms cascata_bordo<rl` 10/12; `hover_xy_rms cascata_melhorado<rl` 12/12; `seguimento_v_rms cascata_melhorado<rl` 6/11; `seguimento_xy_rms cascata_melhorado<rl` 4/11; `seguimento_z_rms cascata_melhorado<rl` 4/11; `seguimento_v_rms cascata_melhorado_ref<rl` 5/11; `seguimento_xy_rms cascata_melhorado_ref<rl` 4/11; `seguimento_z_rms cascata_melhorado_ref<rl` 4/11.

**Degrau 0 → 1 m/s à frente (W)** (12 sementes; «(n/12)» = nas quantas o assentamento acontece dentro da janela)

| | RL | cascata · est. de bordo | cascata · est. melhorado | cascata · melhorado + `p_ref` |
|---|---|---|---|---|
| subida 10–90 % (s) | 0,38 ± 0,02 | 0,35 ± 0,03 | 0,35 ± 0,03 | 0,35 ± 0,03 |
| sobressinal (%) | 17,8 ± 3,6 | 19,9 ± 4,5 | 12,5 ± 6,0 | 13,3 ± 5,5 |
| assentamento 2 % (s) | 7,12 ± 0,52 (7/12) | 6,44 ± 0,00 (1/12) | 5,68 ± 0,49 (5/12) | 5,97 ± 1,50 (7/12) |
| assentamento 5 % (s) | 3,43 ± 2,23 (11/12) | 6,09 ± 1,47 (3/12) | 4,29 ± 1,88 (9/12) | 3,42 ± 2,38 (11/12) |
| erro de regime (m/s) | -0,001 ± 0,012 | -0,086 ± 0,041 | -0,033 ± 0,038 | -0,034 ± 0,031 |
| afundamento após o pico (%) | 5,8 ± 1,7 | 10,1 ± 4,2 | 5,0 ± 3,7 | 5,8 ± 3,9 |

**Degrau 0 → 0,7 m/s a subir (Q; a partir de 0,5 m de altura para ficar no alcance do ToF, janela de 3,6 s)** (12 sementes; «(n/12)» = nas quantas o assentamento acontece dentro da janela)

| | RL | cascata · est. de bordo | cascata · est. melhorado | cascata · melhorado + `p_ref` |
|---|---|---|---|---|
| subida 10–90 % (s) | 0,21 ± 0,04 | 0,26 ± 0,04 | 0,24 ± 0,03 | 0,24 ± 0,03 |
| sobressinal (%) | 14,7 ± 3,9 | 9,5 ± 1,9 | 11,8 ± 1,9 | 11,8 ± 1,9 |
| assentamento 2 % (s) | — | 3,36 ± 0,19 (3/12) | 3,53 ± 0,01 (3/12) | 3,53 ± 0,01 (3/12) |
| assentamento 5 % (s) | 3,38 ± 0,29 (7/12) | 3,04 ± 0,41 (8/12) | 3,06 ± 0,46 (6/12) | 3,06 ± 0,46 (6/12) |
| erro de regime (m/s) | 0,003 ± 0,011 | 0,029 ± 0,010 | 0,021 ± 0,010 | 0,021 ± 0,010 |
| afundamento após o pico (%) | 12,0 ± 6,0 | 1,4 ± 2,3 | 2,2 ± 1,6 | 2,2 ± 1,6 |

**Degrau 0 → −1 m/s lateral (D)** (12 sementes; «(n/12)» = nas quantas o assentamento acontece dentro da janela)

| | RL | cascata · est. de bordo | cascata · est. melhorado | cascata · melhorado + `p_ref` |
|---|---|---|---|---|
| subida 10–90 % (s) | 0,34 ± 0,02 | 0,35 ± 0,03 | 0,35 ± 0,03 | 0,35 ± 0,03 |
| sobressinal (%) | 34,2 ± 3,7 | 18,7 ± 4,9 | 11,6 ± 4,5 | 12,1 ± 3,8 |
| assentamento 2 % (s) | 7,28 ± 0,64 (8/12) | 7,76 ± 0,06 (3/12) | 5,26 ± 2,07 (7/12) | 6,00 ± 1,26 (7/12) |
| assentamento 5 % (s) | 2,98 ± 1,50 | 7,06 ± 1,17 (9/12) | 2,12 ± 1,45 (10/12) | 2,70 ± 2,23 |
| erro de regime (m/s) | 0,009 ± 0,009 | -0,066 ± 0,022 | -0,015 ± 0,025 | -0,011 ± 0,023 |
| afundamento após o pico (%) | 20,0 ± 2,1 | 8,4 ± 2,3 | 4,1 ± 3,1 | 4,2 ± 2,9 |

**Yaw** (só a cascata + estimador melhorado; a RL não roda; 12 sementes)

| teste | medido |
|---|---|
| degrau de rumo de 90° (`yaw_alvo`) | subida 10–90 % (s) 2,54 ± 0,04 · sobressinal (%) -0,09 ± 0,63 · assentamento 2 % / 5 % (s) 3,87 ± 0,10 / 3,58 ± 0,06 · erro final (°) -0,25 ± 0,66 · \|Δz\| máx. (cm) 9,2 ± 3,5 · roll/pitch pico (°) 0,40 ± 0,11 / 0,48 ± 0,14 · mistura saturada (% dos passos) 1,20 ± 1,95 |
| taxa de 0,5 rad/s (`yaw_taxa`) | taxa média (rad/s) 0,499 ± 0,005 · erro RMS (rad/s) 0,005 ± 0,003 · \|Δz\| máx. (cm) 9,1 ± 3,5 · mistura saturada (%) 2,83 ± 4,79 |
| avançar a 1 m/s e rodar 0,3 rad/s (arco) | raio ajustado (m) 3,33 ± 0,15 vs esperado 3,33 · desvio ao círculo RMS (cm) 1,8 ± 0,6 · ⟨v⟩ (m/s) 1,013 ± 0,035 · \|Δz\| máx. (cm) 2,7 ± 0,9 · roll pico (°) 5,3 ± 0,9 · mistura saturada (%) 0,14 ± 0,25 |
| avançar a 1 m/s e rodar 0,5 rad/s (arco) | raio ajustado (m) 2,16 ± 0,09 vs esperado 2,00 · desvio ao círculo RMS (cm) 4,3 ± 1,7 · ⟨v⟩ (m/s) 1,112 ± 0,034 · \|Δz\| máx. (cm) 9,0 ± 7,3 · roll pico (°) 9,2 ± 2,0 · mistura saturada (%) 3,77 ± 5,85 |


### Onde a cascata PERDE (medido)

1. **Seguimento de posição**: ‖xy−p_ref‖ RMS 0,235 m (RL) vs 0,297 (cascata, modo PX4) e 0,262 (com `p_ref`); a RL tem menor erro em **9** das 12
   sementes (com `p_ref`: 8). Com DR a diferença mantém-se (0,223 vs 0,300/0,248). A RL antecipa e persegue o `p_ref` que vê na observação.
2. **Erro de regime dos degraus**: a cascata fica 2,5 % (frente), 4,6 % (lateral) abaixo da velocidade pedida ao fim de 8 s (RL: 0,7 % / +0,8 %) — o
   integral (K_i = 0,356) é lento a absorver o arrasto/viés de atitude; o assentamento a 2 % só acontece em metade das sementes (a RL também em 8/12).
3. **Sem a calibração do giroscópio no chão a vantagem desaparece**: com o estimador de bordo (o mesmo que a RL vê) a cascata só ganha à RL ~20 % no hover (10,4 vs 13,0 cm) e **perde** no seguimento (0,404 vs 0,235 m).
4. **Subida vertical**: 10–90 % em 0,26 s vs 0,22 s da RL.
5. **Yaw é caro**: 90° em 2,5 s (10–90 %), 3,8 s a 2 %; a 0,5 rad/s a altitude oscila ~9 cm (empuxo ∝ d²); num arco apertado (1 m/s, 0,5 rad/s) a
   velocidade excede em 13 % e o roll chega a 9°. Limites 5× abaixo do ArduPilot a 15″ (autoridade do frame).
6. **Rajadas/vento: NÃO medidas** (fase 2). Voo acima de 3,6 m: sem altura (ToF) — o contrato r11 deixa subir a 25 m.
Onde **ganha**: hover (‖xy‖ 3,9 vs 13,0 cm, 3,4×, melhor em 11/12 sementes; \|Δz\| 0,6 vs 2,0 cm; roll/pitch 0,08° vs 0,3–0,5°; deriva de rumo 0,8° vs 2,6°), sobressinal dos degraus
(7–10 % vs 15–33 %), sobrevivência com DR (0 quedas vs 1/12), e **só ela tem yaw**.

### O que limita o desempenho (MEDIDO ⇒ **medido**; ⇒ *inferido*)

- **Hover = o estimador, não o controlo** — **medido**: a posição verdadeira da RL deriva da estimada 9,3 cm RMS e a RL segura a estimada a 5,6 cm; a
  cascata+bordo 9,6/3,8 cm; com a calibração do giroscópio a deriva cai para 1,9 cm. Erro de atitude do estimador 0,76° (RL e bordo) vs 0,42°; erro da velocidade do fluxo
  ≈ 2 cm/s nas três (ruído do PMW3901, não se corrige com calibração).
- **Seguimento = largura de banda da atitude** — **medido** nas ablações: sem FF de aceleração ‖xy‖ 0,291 → 0,539 m (‖v‖ 0,480 → 0,611); sem FF de taxa de inclinação 0,366 m; sem modelo de seguimento o
  sobressinal sobe 9,1 → 20,0 %. A malha de taxa cruza a 8,4 rad/s (PM 43°) e a atitude fecha a ω_n = 5,3 rad/s; o degrau de velocidade da cascata e o da RL têm o
  mesmo 10–90 % (0,35 vs 0,36 s) — a diferença está no sobressinal (9 vs 18–33 %). ⇒ *Inferido*: 0,35 s é o limite da malha de atitude para esta planta sem ultrapassar muito.
- **Yaw = autoridade e empuxo** — **medido**: u/r = 0,438, folga de acelerador 0,37, empuxo ∝ d².
- **Ponto de partida «razão 4»** — **medido**: demasiado conservador para esta planta (hover 35 cm, seguimento 0,50 m).
- ⇒ *Inferido*: o avanço da RL no seguimento de `p_ref` vem de a política ter o `p_ref` na observação e de ter aprendido a antecipar o plano (não medido); a RL
  ter 0,3–0,5° de roll/pitch RMS (4–6× o da cascata) é o preço da sua ação ruidosa (o Δu por passo é igual: 0,078).

### Calibração (sementes 9000…9007 — NÃO são as de avaliação) e o que mudou depois

Cada linha muda UMA coisa face à base; hover 30 s × 8 sementes, seguimento 10 s × 8, degrau frente × 6; «nom/DR». Registo reproduzível: `avaliar_classico.py --calibrar`.

| configuração (uma coisa muda de cada vez) | hover ‖xy‖ nom/DR (cm) | \|Δz\| hover nom (cm) | seguimento ‖xy‖ nom/DR (m) | seguimento ‖v‖ nom/DR (m/s) | degrau: sobressinal nom/DR (%) | assentamento 5 % nom (s) |
|---|---|---|---|---|---|---|
| base (ganhos derivados + estimador melhorado) | 5,1 / 5,2 | 0,6 | 0,291 / 0,359 | 0,480 / 0,423 | 9,1 / 9,9 | 4,38 |
| estimador de bordo (sem calibração do giroscópio) | 11,1 / 9,1 | 2,3 | 0,414 / 0,429 | 0,516 / 0,471 | 18,4 / 16,4 | 7,21 |
| estimador melhorado SEM portão do acelerómetro | 5,1 / 5,2 | 0,6 | 0,293 / 0,360 | 0,511 / 0,469 | 17,6 / 16,5 | 6,67 |
| estimador melhorado SEM calibração do giroscópio | 11,1 / 9,2 | 0,6 | 0,512 / 0,504 | 0,485 / 0,428 | 9,6 / 10,0 | 4,84 |
| estimador melhorado com altura de 2,ª ordem (sem viés do acelerómetro) | 5,1 / 5,2 | 2,4 | 0,290 / 0,358 | 0,480 / 0,424 | 9,1 / 10,1 | 5,28 |
| estimador melhorado + parte I do Mahony (k_i = 0,02 /s²) | 4,8 / 4,9 | 0,6 | 0,292 / 0,365 | 0,480 / 0,423 | 9,2 / 10,0 | 4,55 |
| estimador melhorado + parte I do Mahony (k_i = 0,1 /s²) | 4,9 / 5,2 | 0,6 | 0,304 / 0,392 | 0,483 / 0,425 | 9,5 / 10,4 | 5,46 |
| estimador melhorado + parte I do Mahony (k_i = 0,5 /s²) | 18,0 / 18,4 | 0,6 | 0,437 / 0,523 | 0,508 / 0,443 | 19,2 / 15,6 | — |
| razão da atitude 2,0 (K_att = ωc/2) | 4,0 / 4,3 | 0,6 | 0,255 / 0,293 | 0,473 / 0,422 | 17,7 / 16,1 | 3,09 |
| razão da atitude 3,0 | 6,7 / 6,7 | 0,6 | 0,337 / 0,428 | 0,486 / 0,431 | 4,7 / 4,8 | 3,37 |
| razão da atitude 4,0 (pesquisa) | 12,7 / 11,9 | 0,6 | 0,444 / 0,559 | 0,499 / 0,453 | 5,5 / 1,5 | 2,83 |
| razões 4/4/4/4 (ponto de partida da pesquisa) | 34,5 / 28,8 | 0,6 | 0,497 / 0,630 | 0,500 / 0,457 | 5,8 / 1,7 | 4,03 |
| razão do integral 4 (K_i = K_v²/4) | 7,2 / 6,8 | 0,6 | 0,322 / 0,419 | 0,480 / 0,425 | 8,7 / 9,4 | 3,49 |
| razão da posição 4 (K_pos = K_v/4) | 6,3 / 6,1 | 0,6 | 0,293 / 0,359 | 0,480 / 0,423 | 9,2 / 9,8 | 3,23 |
| referência de posição integrada (p_ref) | 5,1 / 5,2 | 0,6 | 0,275 / 0,287 | 0,481 / 0,424 | 10,2 / 11,0 | 5,58 |
| sem feed-forward de aceleração | 5,1 / 5,2 | 0,6 | 0,539 / 0,558 | 0,611 / 0,588 | 17,1 / 15,2 | 6,22 |
| sem feed-forward de atitude (n̂ × dn̂/dt) | 5,5 / 5,6 | 0,6 | 0,366 / 0,457 | 0,559 / 0,522 | 13,8 / 12,5 | 6,75 |
| sem modelo de seguimento (τ_modelo = 0) | 5,1 / 5,2 | 0,6 | 0,275 / 0,348 | 0,495 / 0,435 | 20,0 / 19,5 | 6,08 |
| sem feed-forward de arrasto | 5,1 / 5,2 | 0,6 | 0,386 / 0,382 | 0,455 / 0,396 | 2,1 / 1,3 | 5,31 |


**Declaração de honestidade — o que foi corrigido depois de ver resultados da avaliação**: as sementes de avaliação não serviram para afinar ganhos, mas **serviram para
descobrir três falhas de lógica/segurança** que as sementes de calibração (planos mais comportados) não tinham mostrado — e por isso o leitor deve tratar as três correções como
«feitas com visibilidade da avaliação». A 1.ª avaliação completa (`out/classico/avaliacao_v1_sem_piso.json`) dava à cascata ‖xy−p_ref‖ 0,365/0,306 m e \|z−z_ref\| 0,084 m (nominal);
a distribuição por semente mostrou (i) **sem piso de altitude**: o `p_ref` do contrato r11 pára em 0,25 m e a cascata, que só recebe velocidades, aterrava (sem fluxo abaixo de 8 cm de
altura a odometria perdia-se: ‖xy‖ 0,97 m na semente 5007); (ii) um Q carregado enquanto descolava **cancelava o descolar** (a semente 5005 ficava 0,2 m abaixo do `p_ref`); depois de
corrigir (i) e (ii), a 2.ª corrida mostrou (iii) **sem teto**, um plano a subir saía do alcance do ToF (a semente 5007 com DR chegou a 7,7 m; a RL caiu nela). Correções: `altura_min`
(o piso do contrato), o alvo de descolagem que os Q/E movem, e o teto de 90 % do alcance do ToF; **verificadas primeiro nas sementes de calibração** (9003/9004/9007: \|z−z_ref\| 0,059/0,068/0,103
m) e só depois a avaliação completa foi repetida (os números desta secção são os da 3.ª corrida: z 0,084 → 0,036). Nenhum ganho foi mexido por causa do conjunto de avaliação.
**Reprodutibilidade**: a cascata com o estimador melhorado reproduz-se a 1e-10 entre corridas; a RL e a cascata com o estimador de bordo variam ≤ 0,4 % nos agregados entre corridas
(⇒ *inferido*: o estado inicial do ruído de VRS do env nasce de um gerador sem semente e a calibração de 1 s no chão deixa-o assentar; não investigado).

### Por fazer

- **Vento/rajadas (fase 2)**: a cascata não tem estimador de perturbação; candidatos INDI como malha interna (pesquisa Q1: 0,10 vs 0,34 m) ou o integral do vento. A RL foi treinada com rajadas — aqui não há vento, por isso não se mediu onde a cascata perde.
- ~~**Port para o núcleo C++**~~ **FEITO na atividade B (2026-10-12)** — `firmware/nucleo/{cascata,estimador_classico}.hpp` ligados em `resolver_modo()` (modos CTBR · VELOCIDADE · YAW_ALVO · OLHAR), SITL fechado com o MuJoCo
  (`sitl.py cascata`), `avaliar_nucleo.py` (C++ vs Python vs RL: o C++ iguala o Python a ≤ 0,3 % em 12 sementes; hover ‖xy‖ 3,9 cm vs RL 13,0), golden vectors \|Δ\| ≤ 5,4e-5 (3000 decisões), a MESMA fonte em QEMU Cortex-M4/M7 BIT A BIT ≡ host,
  ≈ 4,3 µs (passo de 500 Hz) / 10,1 µs (decisão a 50 Hz) estimados no M7 @ 480 MHz (0,2–0,5 % de 2 ms). Detalhe, números e ressalvas em `firmware/README.md` («Atividade B»); prova: `teste_cascata_nucleo.py`.
- Rumo absoluto (sem magnetómetro o yaw deriva ~0,6–0,8° em 30 s com a calibração); voo acima de 3,6 m (barómetro); ESKF com o fluxo para a inclinação; identificação online do arrasto; geométrico/INDI na 2.ª fase.

*Fontes*: PX4 Controller Diagrams e Parameter Reference (docs.px4.io); ArduPilot dev docs (Attitude/Position Control, ATC_ACC_Y_MAX); Brescianini & D'Andrea, IEEE T-CST 28(2), 2018; Faessler, Franchi & Scaramuzza, RA-L 3(2), 2018; Mahony, Hamel & Pflimlin, IEEE TAC 53(5), 2008; Åström & Murray, *Feedback Systems*, 2008; Åström & Hägglund, *PID Controllers*, 1995 — equações reimplementadas, nenhum código copiado.
<!-- END:cascata-classica -->

## Arquitetura MULTI-IA de bordo (2026-10-11)

O dono pediu várias IAs a correr em simultâneo, cada uma com o seu papel — e liberdade para decidir o
melhor arranjo («não se prenda só a uma se achar que não precisa»). A decisão, com a evidência deste
projeto:

| papel | quem cumpre | porquê |
|---|---|---|
| **estabilidade** | **FC H7 dedicado** (determinístico, `fc.py` modela a malha de taxa) | o hardware real TEM um FC dedicado («o Linux não serve de FC primário»); trocar uma malha de taxa verificável por uma IA seria menos seguro e não resolve nada que o FC não resolva — **não se treina IA de estabilidade** (decisão documentada, não esquecimento) |
| **controlo de comandos (WASDQE)** | **IA-1 «voo»** (PPO, já treinada) | `v_ref` → ação a 50 Hz; é o que transforma comandos em voo |
| **«ver o ponto e seguir»** | **IA-2 «seguimento»** (PPO nova) | observa o ponto-alvo NA IMAGEM da câmara FPV e produz `v_ref` — a IA-1 segue; é visão no circuito, coisa que nenhum sensor de bordo dá |

**Cascata** (e não rede única): ponto → detetor (projeção/detector clássico) → IA-2 (25 Hz) → `v_ref` →
IA-1 (50 Hz) → **FC** (500 Hz) → motores. As IAs são especializadas, auditáveis e substituíveis; a
interface entre elas é o MESMO contrato de `v_ref` do WASDQE (faixas ±1,0 m/s xy, ±0,7 m/s z), por isso
a IA-2 reutiliza o que a IA-1 já sabe seguir. **Watchdog/fail-safe**: sem IA-2 (ou a falhar) o `v_ref`
vem do teclado do site — nunca se fica sem controlo; a estabilidade nunca depende de uma IA.

**Números da pesquisa** (`pesquisas/relatorio-seguimento-visual-rl.md`, 11 buscas Tavily): *freeze inner,
train outer* é o padrão e mais eficiente em amostras que treinar tudo junto; **propriocepção é
obrigatória** na obs do tracker (sem ela a sobrevivência cai de 97,1 % → 4,4 %, arXiv 2609.09234); treinar
com **latência de câmara injetada** (33–100 ms — treinar a 0 e voar com latência real é instabilidade
garantida); deteção do ponto por threshold de cor + centróide chega (reprojection error <1 px = «bom»);
watchdog **100–300 ms** (sem deteção → `v_ref = 0` = pairar; 3 falhas → fallback para o teclado); taxas da
cascata na literatura: FC 500–1000 Hz · voo 50 Hz · tracker 25–30 Hz (= taxa da câmara).

Cada IA tem a sua taxa, latência medida e estado (a correr / sem política / erro) — o painel RPi 5 mostra
o **orçamento multi-IA** (soma das latências por período de 20 ms, semáforo) e o site mostra as IAs
individualmente. Os resultados do treino da IA-2 e a validação do detetor↔projeção ficam nas secções
seguintes.

### IA-2 «seguimento» — resultado do treino (2026-10-12)

Ponto-alvo (corpo mocap `ponto`, esfera emissiva — o modelo sem `com_alvo` é IDÊNTICO) → detetor
clássico (projeção↔detetor provada: **0,708 px** de erro médio, <1 px) → **tracker PPO (MLP 64-64, obs
17D** com propriocepção e latência de 116 ms injetada) → `v_ref` (±1,0/±0,7, contrato r11) → **IA-voo
congelada** (ONNX, 65 µs) → FC. Treino: 2 seeds × 1,5 M passos, currículo parado→0,3→0,8 m/s com gates
por estágio (60/80/550 px — pisos medidos 37–40 / 47,5 / 452 px).

**Avaliação com trajetórias nunca vistas** (círculo, oito, aleatório — seed 0 promovido
`out/real_1950_seguimento_final/`):

| trajetória | erro de seguimento | centragem | FOV | sobrevivência |
|---|---|---|---|---|
| círculo | **0,195 m** | 376 px | 95 % | 100 % |
| oito | 1,401 m | 219 px | 100 % | 100 % |
| aleatório | 0,674 m | 263 px | 97 % | 100 % |

Contexto honesto (revisão adversarial confirmou os números, 5 episódios/trajetória): a literatura
medida cita 0,6–1,5 m de erro de seguimento para alvos móveis — a **média das 3 trajetórias é 0,94 m**
(dentro da faixa). O tracker **segue BEM em trajetórias suaves** (círculo: 0,15 m de erro de DISTÂNCIA
mantida, p90 0,33) e **segue à distância nas agressivas** («oito», com inversões: 1,68 m, máx 2,71) —
são coisas diferentes e o relatório separa-as. ‖Δv_ref‖: médio 0,40–0,47 (ok) mas **máx 2,0–2,7 m/s**
(inversões quase totais do comando num passo — limite de variação é melhoria futura) e a FFT do v_ref
tem pico a **1,62 Hz** (24× a média, junto à banda do laço interior; sobressinal do teste de passo 0,55
< 1, amortecido — sem instabilidade provada, mas a assinatura está registada). ARMADILHA DE MÉTRICA
apontada pela revisão: o seed 1 reprovado tem erro de distância MELHOR que o promovido (0,64 vs 0,94 m)
— só o FOV (perder o alvo: 5 % vs 95–100 %) discrimina; por isso a nota de qualidade é **FOV ∧
distância**, nunca o erro de distância sozinho. A
centragem (220–375 px) tem piso do erro composto da IA interior — a 0,8 m/s medimos 452 px de piso COM
feedforward perfeito, por isso a centragem não é nota de qualidade nesse regime; o que conta é **não
perder o alvo de vista** (FOV 95–100 % ✓). O elo mais fraco é a **distância mantida** (0,5–1,9 m; a
recompensa de centrar domina a de distância — melhoria futura documentada).

**Cascata provada no runner** (as duas IAs em simultâneo, telemetria `multi_ia`): IA-voo a 50 Hz (p50
637 µs, p99 1180 µs) + IA-seguimento a 25 Hz (p50 325 µs, p99 639 µs) — `a_correr`, com contas e
watchdog (sem tracker → `sem_politica` + v_ref do WASDQE; NaN → falha + fallback; 3 falhas → `erro`).
A auto-descoberta do runner escolhe o tracker promovido e o picker de voo EXCLUI `*seguimento*` (sem
isso, a IA-2 era escolhida como política de voo — bug achado pela verificação fim-a-fim, corrigido).

### Clássico vs RL vs IA — a prova por medição (2026-10-12, sem vento)

Condições iguais (planta `endurance_15pol_p50b`, mesmas sementes de avaliação 5000–5011, 12 sementes; ganhos
afinados em sementes separadas). Fontes: `out/classico/avaliacao.json` (cascata Python vs RL) e
`out/nucleo/avaliacao.json` (cascata+visão C++ em SITL). A IA só fica onde a medição o exigir — e a
medição diz que **para esta missão (olhar para o círculo e seguir, sem vento) não é preciso nenhum retreino
de IA**: o clássico EMPATA no círculo a 0,6 m/s e VENCE em tudo o resto (hover 3,3×, «oito» 4–5×, yaw livre, 0 quedas).

| capacidade | clássico (cascata C++/Python) | RL / IA | vence |
|---|---|---|---|
| hover ‖xy‖ RMS (12 sementes) | **3,9 cm** (DR 5,8); 10,4 cm só com o estimador de bordo (a mesma informação da RL) | 13,0 cm (DR 18,7) | **clássico** (3,3× com calibração; 1,25× em igualdade de informação) |
| estabilidade de atitude (roll/pitch RMS) | **0,08°/0,08°** | 0,31°/0,50° | **clássico** |
| degrau 1 m/s (sobressinal / regime) | **9 %** / −2,5 % | 18 % / **−0,7 %** | empate (clássico amortecido; RL melhor em regime) |
| seguimento ‖v−v_ref‖ (planos WASDQE) | **0,357 m/s** | 0,368 m/s | empate |
| seguimento ‖xy−p_ref‖ | 0,297 m (0,262 com p_ref) | **0,235 m** | RL (9/12 sementes) |
| yaw livre (90° · manter rumo · arco) | 2,5 s sem sobressinal, |Δz| 8,6 cm, arco R=3,31 vs 3,33 | impossível (a RL foi treinada com yaw fixo) | **clássico** |
| **olhar para o círculo 0,6 m/s** (MESMO protocolo; erro de posição composto = √(dist²+(rumo·1,5 m)²)) | 0,216 m (câmara 21 ms DCMI) · 0,231 m (Pi 116 ms) · 100 % a seguir · yaw livre | tracker PPO: 0,212 m · FOV 96–100 % · yaw FIXO | **empate** no erro; o clássico ganha em yaw livre e em consistência |
| círculo 0,3–0,8 m/s (clássico, DCMI 21 ms) | composto 0,10 / 0,22 / 0,19 / 0,27 m; rumo RMS 0,44–5,2°; 84 % do tempo no limite do yaw a 0,8 | tracker só medido a 0,6 | clássico estável até 0,7; a 0,8 o yaw satura |
| **«oito» (inversões) 0,5–0,6 m/s** | **0,27–0,3 m composto** (0,49 m a 0,8) | tracker PPO: **1,39 m** | **clássico (4–5×)** |
| aleatório 0,6 m/s | (não medido — só círculo/oito) | tracker PPO: 0,67–1,21 m | — |
| queda no DR | 0/12 (cascata) | 1/12 (RL) | clássico |
| custo de bordo | 24,6 kB text · 2940 B de estado (+ frame QVGA 76,8 kB e detetor 5,7 kB só no modo OLHAR) · ~1438 instr/passo 500 Hz = 2060 ciclos ≈ **4,3 µs**/passo (10,1 µs no tick de 50 Hz; llvm-mca; instruções MEDIDAS em QEMU) | MLP 64×64 ONNX 7,4 µs (IA-1) + tracker 325 µs | clássico cabe no Arduino Portenta H7 |
| sem vento: melhorias futuras | vento/rajadas (INDI) por fazer | a RL corrige rajadas (já medido) | **IA útil na fase de vento** (única vantagem restante) |

**Notas de protocolo (honestidade).** O tracker PPO é avaliado por `avaliar_seguimento` a 0,6 m/s com erro de POSIÇÃO 3D; o clássico por `avaliar_nucleo` com erro radial + rumo — a matriz usa o composto √(dist²+(rumo·1,5 m)²) para as duas colunas serem comparáveis; as velocidades iguais (0,6 m/s) são as que contam para o empate no círculo. As métricas de FOV (tracker) e `frac_a_seguir` (clássico) são conceitos equivalentes (alvo visível/a seguir) mas não idênticos. **Sementes e latências não são iguais no «olhar»**: tracker PPO = `avaliar_seguimento` com seeds 9000+, 5 episódios, erro = média |d−d*| só em frames visíveis, pipeline Pi de 116 ms; clássico = `avaliar_nucleo` com seeds 7000–7002, RMS; as linhas do «olhar» DCMI 21 ms (build Arduino) são o cenário alvo. As sementes 5000–5011 (12) valem para hover/degraus/seguimento. Os números do tracker vêm da avaliação de 2026-10-12 (`avaliar_seguimento`; artefacto não guardado em out/ — nota para o futuro).

**Conclusão (medição, não opinião).** Estabilização, rotação, movimentação e «olhar para o círculo» ficam no
**clássico** (cascata estilo PX4 + detetor por momentos + IBVS, tudo C++ float32 no núcleo de firmware que
corre bit a bit igual em Cortex-M4/M7 — `teste_cascata_nucleo.py` 66/66 (--rapido 53), QEMU incluído). A IA **não é
necessária** para esta missão; a política RL fica como comparação e para a fase de vento (onde já ganhou
medidamente às rajadas). Se no futuro houver distratores/oclusão/reaquisição a alta velocidade, a pesquisa
diz que aí a perceção aprendida pode ganhar — mas **só com medição** (critério registado).

**Limites medidos do clássico** (honesto): o yaw é o gargalo (autoridade ÷5 do ArduPilot a 15″: ~29 °/s
sustentáveis): a 0,8 m/s o «oito» satura e o círculo passa 84 % do tempo no limite do yaw; a 0,5 m/s
tudo segue; com o teto do yaw a 0,8 rad/s (ensaio) o círculo a 0,8 m/s melhora de 7,2° para 5,4° de rumo
RMS. A latência da câmara importa: 21 ms (DCMI/Arduino) dá rumo RMS 0,44–0,9°; 116 ms (pipeline Pi) dá
1,0–3,0° às mesmas velocidades.

## Resultados medidos

Máquina: **i9-14900HX** (32 threads), CachyOS x86-64, Python 3.13.15, MuJoCo 3.15.0, torch 2.14.1+cpu,
Stable-Baselines3 2.9.0, gymnasium 1.4.0, onnx 1.23.2, onnxruntime 1.30.0, numpy 2.5.3.

### Treino — 3 seeds × 1 M passos (3 em paralelo, `loadavg` 17,81 no arranque)

Receita: PPO `MlpPolicy` MLP **[64, 64] tanh** · `lr 3e-4` · `n_steps 1024` · `batch 256` · `n_epochs 10`
· `gamma 0,99` · `gae_lambda 0,95` · `clip 0,2` · `ent_coef 0,01` · `vf_coef 0,5` · `max_grad_norm 0,5` ·
`n_envs 4` · `torch.set_num_threads(1)` · **sem VecNormalize**.

| seed | passos | avaliações | `mean_ret` final | `std_ret` | `mean_z` [m] | `dist_xy` [m] | no alvo | melhor `mean_ret` | passos/s | parede |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1 003 520 | 50 | **413,8** | 20,4 | 0,975 | 0,027 | 85,1 % | 431,4 | 1 454 | 690 s |
| 1 | 1 003 520 | 50 | **398,1** | 42,6 | 0,970 | 0,028 | 87,8 % | 431,6 | 1 446 | 693 s |
| 2 | 1 003 520 | 50 | **443,6** | 0,5 | 0,964 | 0,005 | 92,8 % | **444,4** | 1 461 | 684 s |

≈ **1 450 passos/s por seed** com as 3 em paralelo (12 processos de ambiente) → **1 M ≈ 11,5 min**.
O teto teórico de retorno é ≈ 500 (hover perfeito: bónus +1 por passo, penalidades ~0); o seed 2 fica a
`std_ret = 0,5` do seu próprio ótimo local.

⚠ Esta tabela é a corrida **v1** (recompensa original, sem vento). Os **defaults atuais** do `train.py` são
os da fase v2b — `n_envs 8`, `n_steps 512`, `lr 1e-4`, `ent_coef 0,001`, `log_std_init −0,5`,
`optimizer_kwargs weight_decay 1e-4` e `--curriculo-vento 0,1,2,3` — e a escala de `mean_ret` mudou
(v2b: ≈350 no hover perfeito, não ≈500). Ver [Resultados v2b](#resultados-v2b-verificado).

### Rollouts dos `best_model` (política determinística, 3 rollouts × 500 passos por seed)

Métrica calculada nos **últimos 5 s** (250 passos) de cada rollout; nenhum rollout terminou antes do fim.

| seed | z médio [m] | \|z − 1\| médio [m] | no alvo | terminações | passos | retorno |
|---|---|---|---|---|---|---|
| 0 | 1,011 | 0,011 | 100 % | **0** | 500/500 | 428,6 |
| 1 | 0,997 | 0,004 | 100 % | **0** | 500/500 | 435,4 |
| 2 | 0,999 | 0,001 | 100 % | **0** | 500/500 | 444,3 |

Duas medições independentes concordam dentro de ≈1,5 mm. **Critério do experimento cumprido 3/3**:
`z ≥ 0,90 m` ∧ `|z − 1| ≤ 0,10 m` (pior caso medido ≤ 1,2 cm, ~8× melhor que o limite) ∧ `no_alvo ≥ 0,5`
∧ **zero quedas**. Os `final.zip` também passam (`z` 0,994–1,011 m, 0 terminações), mas com
`no_alvo` 81–100 % — o `best_model` é visivelmente mais estável em regime.

### Resultados v2b (verificado)

**Política final: `out/vento_r9_polir_vento3/final.zip`** (sha256 `f8af4a05…`), treinada **com vento**
(U[0, 3] m/s, azimute aleatório) por fine-tune de 500 k passos a `lr 5e-5`, `ent 0` — 175 s, 2 743
passos/s. O envelope validado é **≤3 m/s sustentado**.

Grelha do critério — vento {0, 1, 2, 3} m/s × azimute {0°, 90°, 180°, 270°}, médias de **3 seeds** de
reset, métricas nos **últimos 5 s** de um rollout determinístico de 10 s:

| u (m/s) | azimutes | \|z − 1\| [m] | ‖xy‖ [m] | \|yaw_err\| [rad] | \|ω_z\| [rad/s] | terminações | veredicto |
|---|---|---|---|---|---|---|---|
| 0 | 0/90/180/270 | 0,0059 | 0,0048 | 0,0129 | 0,0001 | 0 | **PASS ×4** |
| 1 | 0 / 90 / 180 / 270 | 0,0056–0,0061 | 0,0083–0,0176 | 0,0111–0,0146 | ≤0,0001 | 0 | **PASS ×4** |
| 2 | 0 / 90 / 180 / 270 | 0,0045–0,0065 | 0,0454–0,0561 | 0,0057–0,0199 | ≤0,0001 | 0 | **PASS ×4** |
| 3 | 0 / 90 / 180 / 270 | 0,0023–0,0067 | 0,1013–0,1194 | 0,0028–0,0283 | ≤0,0003 | 0 | **PASS ×4** |

Limites do critério: `|z − 1| ≤ 0,05 m` · `‖xy‖ ≤ 0,10 m` (**≤0,15 m** a 3 m/s) · `|yaw_err| ≤ 0,10 rad` ·
`|ω_z| ≤ 0,30 rad/s` · **0 terminações**. Resultado: **16/16 PASS (100 %)** — as **12** condições ≤2 m/s
passam todas, e as 4 de 3 m/s também (o critério exigia no mínimo todas as ≤2 m/s e ≥14/16). Todos os rollouts correm **500/500 passos** (nunca
terminam antes do fim).

Confirmações independentes (agente de fecho, avaliador próprio, seeds 7001–7003 e 32 condições densas
com 0,5/1,5/2,5 × 8 azimutes + 3,0 × 8 azimutes): **16/16 PASS** e **32/32 PASS**, **0 terminações**,
métricas a bater ao 4.º decimal com a tabela acima. O treinador reporta ainda **56/56** na sua grelha densa
(7 velocidades × 8 azimutes × 3 seeds: 0 · 0,5 · 1 · 1,5 · 2 · 2,5 · 3 m/s), com os mesmos piores valores.

**Anti-*chatter*** (vento 2 m/s, medido): `|a|` médio por canal = **0,009–0,025** (≈**1,6 % da
autoridade**; máximos 0,12–0,25 nos momentos) e `‖Δa‖` médio = **0,0088**. A campanha falhada usava
74–90 % de autoridade em *chatter* de Nyquist (ver abaixo) — a diferença é o que separa "pairar 10 s" de
"capotar aos 1,3 s".

Outros números do run final (`out/vento_r9_polir_vento3/train_log.jsonl`, 13 campos): `mean_ret 350,0` ·
`mean_z 0,920` · `mean_dist_xy 0,0057` · `frac_no_alvo 0,802` · `mean_yaw_err 0,035` · `u_vento 3,0` a
2,16 M passos acumulados.

### Ronda 10 — vento dinâmico: campeão verificado

**Política final: `out/vento_r10_ft_dryden_600k/best_model.zip`** (sha256 `a72d381c…`), obtida por **3
fine-tunes encadeados** a partir da v2b (sempre com vento ATIVO no estágio — polir sem vento degrada, ver
a lição abaixo), trocando a dinâmica em cada etapa: rajadas → frente → dryden.

| run | pasta | dinâmica de treino | passos | wall | passos/s | melhor retorno |
|---|---|---|---|---|---|---|
| R1 | `out/vento_r10_ft_raj_1M` | `rajadas` p=0,02 d=10 | +1 003 520 | 307 s | 3 266 | 391,4 |
| R2a | `out/vento_r10_ft_frente_600k` | `frente` t_s=2,0 | +602 112 | 173 s | 3 486 | 399,5 |
| R2b | **`out/vento_r10_ft_dryden_600k`** | `dryden` σ=0,5 L=10 | +602 112 | 177 s | 3 400 | **408,7** |
| R3 (descartado) | `out/vento_r10_ft_raj_dur_250k` | `rajadas` p=0,05 d=25 | +253 952 | 78 s | 3 253 | 405,1 |

Todas com `--curriculo-vento 1,2,3 --lr 1e-4 --ent-coef 0.005 --log-std-init -0.5 --n-envs 8 --seed 0
--sem-painel` e `--retomar` do `best_model.zip` da etapa anterior (o currículo subiu 1→2→3 m/s nas duas
primeiras avaliações de cada run). O treino corre **só no terminal** (`--sem-painel`).

**Critério do dono — 57/57 PASS, 0 terminações.** 19 condições (16 constantes {0,1,2,3} m/s × {0,90,180,
270}° + 3 dinâmicas) × 3 seeds; a tabela é o **pior das 3 seeds**, últimos 5 s de um rollout
determinístico de 10 s:

| condição | ‖xy‖ sempre [m] | ‖xy‖ 5 s [m] | \|z−1\| 5 s [m] | \|yaw_err\| 5 s [rad] | \|ω_z\| 5 s [rad/s] | terminações |
|---|---|---|---|---|---|---|
| 0 m/s @4 azimutes | 0,018 | 0,007 | 0,001 | 0,012 | 0,000 | 0 |
| 1 m/s @4 azimutes | 0,015–0,022 | 0,005–0,016 | 0,001 | 0,011–0,013 | 0,000 | 0 |
| 2 m/s @4 azimutes | 0,039–0,056 | 0,034–0,046 | 0,000–0,001 | 0,009–0,015 | 0,000 | 0 |
| 3 m/s @4 azimutes | 0,084–0,108 | 0,084–0,096 | 0,000–0,002 | 0,005–0,020 | 0,000–0,001 | 0 |
| rajadas p=0,02 d=10 u≤3 | 0,046 | 0,008 | 0,001 | 0,012 | 0,007 | 0 |
| frente t_s=2 s u∈[0,5;3] | 0,074 | 0,073 | 0,002 | 0,006 | 0,000 | 0 |
| dryden σ=0,5 L=10 u≤3 | 0,018 | 0,008 | 0,011 | 0,011 | 0,001 | 0 |

Limites: sobe a 0,9–1,1 m em ≤4 s · ‖xy‖ ≤0,30 **sempre** · ‖xy‖ média ≤0,10 (≤0,15 a 3 m/s) · `|z−1|`
≤0,05 · `|yaw_err|` ≤0,15 · `|ω_z|` ≤0,30 nos últimos 5 s · **0 terminações**. O drone **sobe em 47–52
passos (0,94–1,04 s)**, entra na faixa [0,95, 1,05] em 59–66 passos e fica lá: a partir do 2.º segundo
`z ≥ 0,92 m` sempre, com `z` mínimo de TODO o episódio = 0,015 m (é o repouso no chão do 1.º passo, com os
motores desligados — o `reset` não teleporta). No pior caso a 3 m/s fica em 0,084–0,096 m de ‖xy‖, **abaixo
do limite estrito de 0,10** (não só do 0,15).

**Stress mais duro que o critério** (grelha densa 4 velocidades × 8 azimutes × 3 seeds + 24 dinâmicas
duras + 24 sequências vento+dinâmica): **144/144** — o único dos 4 candidatos **sem nenhuma falha**. Os
outros 3 fazem 143/144 (a falha única é `dryden σ=1,5` — 3× a σ de treino — com `|z−1|` = 0,055–0,059 m
>0,05 na média dos 5 s finais; nunca há queda, terminação nem deriva).

Escolha do campeão feita com os dados (§4 do relatório): maior margem no pior caso do stress (0,048 m de
`dz` contra 0,055–0,059 dos restantes), melhor rejeição das dinâmicas e o melhor retorno de treino (408,7).

Relatório completo: `out/RELATORIO_r10_vento_dinamico.md`; veredictos em JSON:
`out/avaliacao_vento/r10_*.json` (`r10_campeao.json` = 57/57, `r10_campeao_stress.json` = 144/144).

> **Honestidade dos dados:** `--sucesso 450` (paragem por retorno) **nunca dispara** com a recompensa v2/v2b
> — ela penaliza guinada e esforço, e o retorno satura abaixo disso; todas as runs terminam por **orçamento
> esgotado**. O `best_model` é escolhido pelo retorno médio do `EvalCallback` **sem vento**; por isso a
> certificação de robustez ao vento é o avaliador independente (§ acima), **não** o `train_log.jsonl`.
> Fora do envelope (>3 m/s constantes) não foi testado.

### Lição da campanha (r1–r9)

A primeira campanha de re-treino (7 rondas, **20 treinos**, ~**25 M passos**, 22 modelos avaliados) deu
**0/16** em todas as políticas. O bloqueio **não era o vento**:

1. **Atrator de *chatter* nos momentos**: as políticas v2 saturavam os canais de momento (|a₁|, |a₂|
   médios 0,74–0,90, ~70 trocas de sinal em 70 passos) e **capotavam aos ~1,3 s**; a política v1 (que
   paira 500/500) usa **1 %** dessa autoridade. A réplica exata da receita v1 sob a recompensa v2 caía no
   mesmo platô ⇒ o atrator vinha da **recompensa** (yaw forte + `Δa` fraco), não dos hiperparâmetros.
2. **Currículo com critério inatingível**: o avanço pedia `frac_no_alvo ≥ 0,8` com o yaw **incluído** no
   bónus; a política v1 — que paira bem — mede **0,10** ⇒ o DR de vento **nunca ligava** (`u_vento = 0`
   até ao fim). O critério passou a `frac_xy_z` (xy + z, **sem yaw**) com `--avanco-frac 0,5`.
3. **O bloqueio real era o yaw**: a base v1 já rejeitava o vento de posição, mas tinha o yaw livre
   (0,18 rad de *offset*). Um fine-tune de **160 k passos** baixou-o para 0,02 rad ⇒ 14/16.

As **três correções** que destravaram: `PESO_DELTA_A` 0,01 → **0,05**; avanço do currículo por
`frac_xy_z`; **`--retomar`** (fine-tune a partir dos checkpoints v1). Com elas: 16/16 de 1,08 M passos em
diante, replicado em 3 seeds independentes.

Achados operacionais: **`lr 3e-4` oscila** (16/16 ↔ 12/16 entre checkpoints, por yaw) enquanto
**`lr 1e-4`/`2e-4` é estável**; **polir SEM vento degrada** (16/16 → 13/16 em 200 k passos — a política
"esquece" a rejeição de vento), logo o vento tem de ficar no treino; e o `--retomar` do SB3 precisa de
`reset_num_timesteps=False` (senão o `learn()` reinicia o contador e retreina tudo de zero).

### Retreino da planta 1950 mm — primeiro resultado e AJUSTE (2026-10-11)

A pesquisa de suficiência (`pesquisas/relatorio-treino-rl-suficiencia.md`) recomendava 5–8 M passos de
hover e 8–12 M de controlo de voo para a planta nova (J ×11). O primeiro retreino seguiu-a à letra —
**2 seeds × 8 M passos `--comandos`** (`out/reprovado_real_1950_comando_s0/s1 (renomeados com prefixo `reprovado_` para o picker do site não os carregar)`) — e o resultado foi **NEGATIVO,
com um achado medido**:

- as políticas **colapsaram no atrator «sentar no chão»**: no teste de hover com `v_ref = 0` o drone fica
  a **z ≈ 0,13 m** (o alvo é 1 m) e comandos W não o descolam (um seed capota) — o MESMO atrator já
  documentado neste projeto para treino de comando a partir do zero (2026-10-10);
- o **currículo de vento nunca avançou** («estágio 1/4, teto 0 m/s»): o gate `frac_xy_z ≥ 0,5` (5 cm,
  alvo fixo) é inatingível quando a referência se MOVE — e, mais importante, a estagnação era
  SÍNTOMA do colapso (o drone sentado nunca cumpre o gate), não a causa;
- a avaliação `avaliar_real.py` media contra `env.alvo_z` (alvo FIXO) em modo comando — métrica errada
  para referência em movimento (corrigida: modo comando detetado pelo `_n_ator`, métricas de seguimento).

**O AJUSTE** (receita provada neste projeto + a pesquisa): **clássico → `transferir_politica.py` →
afinar em comando** — o treino de hover (obs clássica) voa rápido nesta planta (o FC fecha a malha de
taxa), a transferência carrega os pesos para a obs de comando e o fine-tune aprende o seguimento SEM
cair no atrator. Isto CONTRADIZ a recomendação genérica da pesquisa ("treinar de raiz" com a planta
nova) — a evidência medida deste laboratório vence: o atrator existe, está documentado e reproduziu-se
na planta 1950. **Prova decisiva do diagnóstico** (rollout medido): a política clássica da planta 650
(`out/real_endurance15_rajadas/final.zip`) voa a planta NOVA 1950 sem nada de novo — z médio 0,935 m,
assenta a 0,98–1,00 m, ‖xy‖ 0,015 m. Ou seja: **a planta é perfeitamente voável; o que falha é o
arranque do zero nesta dinâmica** (J ×11 + T/W 2,6 tornam a descoberta da descolagem muito mais cara em
exploração). O arranque do zero (2×3 M clássico) foi PARADO a ~1 M passos com o mesmo atrator e deu
lugar ao **warm-start** — `--retomar` da política que voa + fine-tune na planta nova (exatamente a
comparação «warm-start vs raiz» que a pesquisa mandava testar; aqui o warm-start ganhou por evidência).
A seguir: transferência para a obs de comando (`transferir_politica.py`) e fine-tune de comando — desta
vez a partir de uma política que VOА, que é o que evita o atrator «sentar no chão».

### Resultado do retreino 1950 (2026-10-11, pipeline completo)

| etapa | o que correu | resultado medido |
|---|---|---|
| hover **warm-start** (2 seeds × 3 M, `--retomar` da política 650 que voa) | currículo de vento + DR | **100 % de sobrevivência** no-distribuição **E OOD** · ‖xy‖ **7,5 cm** nominal / 12–14 cm OOD · frac_xy_z 81–91 % · currículo **4/4 (vento 3 m/s)** desde cedo |
| transferência (`transferir_politica.py`) | 42 → 48 dims, novas entradas a zero | validação **exata** (64 estados sem comando → ações idênticas, max|Δ| = 0) |
| **fine-tune comando** (2 seeds × 2 M, `--sem-curriculo --vento-max 3` + `--vento-dinamico rajadas`) | seguimento WASDQE com referência em movimento | **100 % de sobrevivência em TODAS as 14 condições** (incl. OOD: vento 5 m/s + rajadas) · ‖xy‖ 0,255/0,271 m nominal e 0,371/0,450 m OOD (rastreio da referência em movimento) · seed 0 promovido |

Política final: **`out/real_1950_voo_final/final.zip`** (seed 0 do fine-tune, com `avaliacao_real.json` ao
lado) — é a que o `sim_site.py` carrega sozinho. Os runs reprovados do arranque do zero ficaram como
evidência com o prefixo `reprovado_` (o picker do site não os escolhe).

NOTA de leitura: em MODO COMANDO as colunas «≤5 cm / ≤10 cm» do `avaliar_real` medem contra o alvo FIXO
(`env.alvo_z`) e são informativas apenas — a métrica que interessa é o **‖xy‖ de rastreio** da referência
em movimento (e a sobrevivência). Os runs de arranque do zero (`--comandos` sem transferência) caíram no
atrator «sentar no chão» — ver a secção anterior.

## Mecanismo MULTI-IA de bordo (2026-10-11) — `multi_ia.py`

Várias IAs a correr EM SIMULTÂNEO, cada uma no seu ritmo, com estado no site e orçamento de CPU no
painel RPi 5. A arquitetura decidida (ATIVIDADE B) — e a decisão mais importante é uma SUBTRAÇÃO:

| peça | papel | taxa | estado |
|---|---|---|---|
| **FC H7** (`fc.py`, determinístico — **NÃO é IA**) | ESTABILIDADE (PID de taxa) | 500 Hz | não se substitui por IA: o hardware real tem FC dedicado que fecha as taxas mesmo que a RPi 5 falhe |
| **IA-1 «voo»** (`out/real_1950_voo_final/final.zip`) | `v_ref` → ação `ctbr` | 50 Hz | `a_correr` |
| **IA-2 «seguimento»** (outra frente; slot pronto) | ponto na imagem → `v_ref` | 25 Hz (taxa da câmara) | `sem_politica` sem rede — o mecanismo corre MESMO ASSIM |
| site WASDQE (contrato r11) | `v_ref` de fallback | 50 Hz | nunca falta controlo |

```
câmara (25 Hz) → [IA-2 seguimento] ─v_ref─┐
                                          ├→ [IA-1 voo] (50 Hz) ─ação→ [FC H7 500 Hz] → motores
site WASDQE ────────────v_ref (fallback)──┘
```

**Watchdog/fail-safe** (testado em `teste_multi_ia.py`, 25/25): IA-2 ausente/`sem_politica`/em falha →
o `v_ref` vem do WASDQE do site (o bloco `voo` continua a funcionar); IA-1 a falhar → **ação neutra
`ctbr = [0,0,0,0]`** (pairagem + taxas zero) + aviso — o FC mantém o drone; estados por IA
(`a_correr`/`sem_politica`/`fallback`/`erro`, com `sem_politica` e `erro` pegajosos) sempre visíveis.

**Contrato público**: `acao = cascata.passo(t, obs)` e `estado = cascata.estado()` — a telemetria
publica a chave aditiva `"multi_ia"` (IAS com nome/papel/taxa/latências p50/p99/estado, fonte do
`v_ref`, aviso, e o FC marcado como não-IA) e `/api/state`/`/api/sim` levam-na ao site (MECANISMO
ESCOLHIDO: pela telemetria, como o `fpv` — sem ficheiro extra). O painel RPi 5 ganha `rpi5.multi_ia`
com o **semáforo** OK/ATENCAO/ERRO (p99 da soma das IAs contra o período de 20 ms; o FC não entra na
conta). No site: bloco «Multi-IA» (testids `multi-ia-*`) que diz honestamente quando só há UMA IA —
e que a estabilidade é do FC.

**Observação do tracker** (contrato do TREINO, `env_seguimento.py`): a obs da IA-2 vem SEMPRE do
builder do treino — `ObservacaoSeguimento` chama `env_seguimento._observacao` (OBS_DIM=17:
`[u_n, v_n, escala, flag, v_ref(3), erro_px(2), v̂/2, ω/2, roll/π, pitch/π]`) e a ação vira `v_ref`
com a **escala do treino** `a·(1, 1, 0,7)` (envelope r11 ±1,0/±0,7 m/s; o canal `v_ref` da obs é a
AÇÃO CRUA). Sem ponto em `env` (`ponto_alvo is None`) o caso é o `visivel: False` do treino. Fixos da
revisão crítica de 2026-10-12, todos provados no `teste_multi_ia.py` §5: (1) obs == builder do treino
(max|Δ| = 0); (2) escala do z exata (ação 0,2 → v_ref_z 0,14 m/s); (3) ações NaN/Inf nunca se propagam
(contam falha); (4) envelope do CONTRATO (±1,0/±0,7 — o clip ±2 era violável); (5) falhas
CONSECUTIVAS (o sucesso zera a contagem); (6) histerese de reengate (3 sucessos seguidos antes de o
tracker voltar a mandar — sem isto alterna-se tracker↔fallback: chattering). Auto-descoberta de
`out/real_1950_seguimento_*/final.zip` ou `--seguimento-model` (o env é criado com `com_alvo=True`
quando há tracker — o ponto-alvo do treino).


## Avaliação OOD — fora do currículo de treino (2026-10-11)

A pesquisa de suficiência do treino (`pesquisas/relatorio-treino-rl-suficiencia.md`) exige avaliação
**fora da distribuição de treino** — o currículo de vento vai a 3 m/s e as políticas só viram 0–3 m/s.
O `avaliar_real.py` ganhou o bloco **OOD** (`--apenas-ood` corre só ele; as condições marcadas `ood`):

| condição OOD | o que testa |
|---|---|
| vento 4 m/s · vento 5 m/s (teto do contrato) | generalização de vento além do currículo |
| vento 5 m/s + rajadas (até +3 m/s) | OOD + perturbação dinâmica |
| SoC 10 % (residual) + vento 3 m/s | tensão em queda + vento |
| DR + vento 4 m/s | massa ±15 % (via DR) + OOD |

Os **comandos extremos** (WASDQE aos limites) cobrem-se no `teste_controle_voo.py`; a **massa ±15 %**
cobre-se pelo DR (`aleatorizar=True` sorteia peças/massas).

**Políticas `--comandos` (obs 48) são detetadas automaticamente** (pelo `_n_ator` do ator, o mesmo
detector do `sim_view` — nunca por flag): o env passa a modo comando com perfis de referência aleatórios
e as métricas passam a ser de **SEGUIMENTO** da referência em movimento (o cabeçalho diz «MODO COMANDO»).
Sem a deteção, avaliar uma política `--comandos` rebentava no `predict` (obs 48 vs 42) — reparado em
2026-10-11 e provado com a `out/real_voo_r1/final.zip` (5/5 OOD, 100 % de sobrevivência, ‖xy‖ 0,34 m —
política da planta 650 avaliada na 1950, o que explica o rastreio fraco). O relatório passa a ter um **resumo por
grupo** (NO DISTRIBUIÇÃO vs OOD) — o veredito de generalização. Primeira prova do arreio (com a política
antiga, ainda da planta 650 mm): 100 % de sobrevivência nas 5 condições OOD, ‖xy‖ 0,20 m em médio, e a
degradação honesta no SoC 10 % (|Δz| 0,41 m) — números do `avaliar_real.py --apenas-ood`.

## IA nº 2 — SEGUIMENTO VISUAL («ver o ponto e seguir», 2026-10-12)

Cascata multi-IA (o dono autorizou e desenhou): **ponto-alvo → detetor → IA-seguimento (esta) → `v_ref`
→ IA-voo (`out/real_1950_voo_final/final.zip`, CONGELADA) → FC → física**. A estabilidade NÃO é IA — é o
FC (malha de taxa; o FC H7 no drone real).

| peça | ficheiro | o que é |
|---|---|---|
| ponto-alvo | `lab/drone_rpi/modelo.py` (`com_alvo=True`) | corpo mocap `ponto`, esfera emissiva, **sem massa/colisão** (cenário; sem `com_alvo` o modelo é IDÊNTICO — 287/287 e 141/141 confirmados) |
| trajetórias | `env_real.py` (`definir_trajetoria_ponto`) | `parado`/`aleatorio`/`circulo`/`oito` a **0,3–0,8 m/s**, começando à frente do drone, contínuas (sem teleports) |
| percepção | `visao.py` | **projeção exata** do ponto (`_cam_projection` do MuJoCo) no treino; detetor clássico (threshold da esfera brilhante) no deploy — a honestidade prova-se: render real → detetor → **erro médio 0,71 px · máx 0,98 px** vs projeção |
| tracker | `env_seguimento.py` | obs 17D (u,v norm · escala aparente · visível · v_ref · erro px · **propriocepção** v̂/ω/roll/pitch — sem ela a sobrevivência cai de 97 % para 4 % na literatura) com **latência de 116 ms injetada**; ação = `v_ref` ±1,0/±0,7 (contrato r11, saturador sempre ativo); recompensa: −‖(u,v)‖ −|d−1,5 m| −0,05‖Δv_ref‖ + sobrevivência **−5 por passo com o ponto fora do FOV**; episódios 10 s |
| treino | `train_seguimento.py` | PPO MLP 64-64, 2 seeds × 1,5 M passos, currículo **parado → 0,3 m/s → 0,8 m/s** (gate: FOV ≥95 % e centragem ≤30 px); piloto em **ONNX** no loop (65 µs vs 2 ms em torch — 67 → 313 passos/s medidos) |
| avaliação | `env_seguimento.avaliar_seguimento` | trajetórias **nunca vistas** (círculo, oito, aleatório): erro de seguimento (m), centragem (px), % FOV, ‖Δv_ref‖ (oscilação) |
| provas | `teste_seguimento.py` | 5/5: projeção×detetor <2 px · modelo sem `com_alvo` idêntico · mocap move-se por `data.mocap_pos` · v_ref saturado ao envelope · ações da IA-voo idênticas com tracker neutro |

## Limites de movimento

> ⚠ **Riscos conhecidos da planta 1950 mm** (revisão adversarial de 2026-10-11): (i) o τ_m do MODELO é
> 55,8 ms e o de uma hélice 15″ real anda nos 0,1–0,2 s — a simulação é 2–3× mais ágil que o hardware e a
> política pode parecer mais rápida do que será no ar; (ii) o acelerador de pairagem fica a 63 % (duty
> 56,4 %) — menos margem para rajadas; (iii) o gate do currículo de vento (≥50 % dos passos a ≤5 cm) pode
> ESTAGNAR nos degraus 2–3 m/s com o drift ×3,6 e T/W 2,62; (iv) a flexão dos braços (44 Hz vs prop
> passing 46–51 Hz) não está modelada (corpo rígido). — SEM caixa (2026-10-11, pedido do dono)

> «remova o limite do quanto posso me movimentar, quero poder andar por um espaço maior»

Os limites ANTIGOS eram uma **caixa de trabalho de 4 m em xy** (`VOO_XY_MAX = 4.0` — a referência
saturava e o `v_ref` zerava na borda), **teto de referência 2,75 m** (`VOO_Z_MAX`) e **terminação por
subida a 3 m** (`Z_TETO`). Agora: **xy = ±25 m** (a ARENA: o chão texturado da cena é 50×50 m — o limite
passa a ser o cenário, não uma caixa; o plano do MuJoCo é infinito, mas a cena visível tem 50×50 m),
**z de referência até 25 m** e **terminação por subida apenas a 30 m** (`Z_TETO` = o céu — só apanha um
voo absurdo). O **piso mantém-se** (`VOO_Z_MIN = 0.25` m: o chão é um limite REAL) e as **velocidades
não mudam** (`VOO_VEL` 1,0 m/s, `VOO_SUBIDA` 0,7 m/s — semântica do contrato, não espaço): com a planta
×3 a menos agilidade, o rastreio a altas velocidades pode degradar, mas o dono pediu LIBERDADE de
espaço e as políticas continuam a comandar as mesmas velocidades. Valido em `teste_controle_voo.py`
(parede/teto/piso provados pelas constantes: saturação em ±25 m e z ∈ [0,25; 25] m) e nos limiares de
`termina()` do `run.py` (teto = `Z_TETO`).

### Controle de voo (r11) — WASDQE com rajadas corrigidas (verificado, 2026-10-10)

**O pedido do dono**: «um controle de voo onde mudo a altitude e a direção — WASD para as direções, Q e E
para subir e descer — vendo no site quando ativo; ajustar o treinamento para isso; e durante a
movimentação corrigir as rajadas de vento para não ir mais lento nem a favor: respeitar a movimentação
proposta sem sofrer a influência do vento». Contrato completo em [INTERFACE.md §4.5](INTERFACE.md).

**O que foi construído**: modo comando no `env.py`/`env_real.py` (a referência `p_ref` integra o `v_ref`
comandado a 50 Hz; observação ganha o `v_ref` — cf2 16→19 dims, planta real 42→48 — e a recompensa passa
a erros de SEGUIMENTO limitados); `train.py --comandos` (perfis de comando aleatórios por episódio) +
`transferir_politica.py` (transfere políticas que já voam para a obs de comando — as entradas novas a
zero, validação: **ações idênticas**); bloco `"voo"` no ficheiro de controlo + `POST /api/voo` + eco `"voo"`
na telemetria; painel **CONTROLO DE VOO** no site (keycaps WASDQE que acendem ao vivo, armado/desarmado,
estado honesto); e a prova toda em `teste_controle_voo.py` (§1–§4).

**Receita de treino** (o `--comandos` do zero cai num atrator — ver «Achados» abaixo):

| etapa | comando | cf2 | planta real |
|---|---|---|---|
| 0 · transferir | `transferir_politica.py --de <política que voa> --para out/voo_*_transferida` | 16→19 dims | 42→48 dims (+ `hardware.json`) |
| 1 · seguir | `train.py --planta … --comandos --retomar out/voo_*_transferida/final.zip --sem-curriculo --vento-max 3 --vento-dinamico rajadas --vento-dinamico-params '{"p":0.03,"duracao":12}'` | `out/voo_cf2_r2/best_model.zip` | `out/real_voo_r1/best_model.zip` |

**Critérios medidos** (`teste_controle_voo.py` §2 — política determinística, guiões de 2,5 s de
descolagem + 3 s de comando; os limiares estão no cabeçalho do teste). Núcleo do pedido = a **SIMETRIA
proa/cauda**: o mesmo comando `vx = 1,0 m/s` com vento de **2 m/s contra** e **2 m/s a favor** tem de dar
velocidades médias **iguais** — nem mais lento nem a favor:

| critério (limiar) | cf2 (`out/voo_cf2_r2/final.zip`) | planta real (`out/real_voo_r1/final.zip`) |
|---|---|---|
| calmaria: ⟨v⟩ segue W (±0,15 cf2 / ±0,25 real) | **[1,001 · +0,010 · −0,001]** m/s | **[0,967 · −0,062 · −0,013]** m/s |
| **simetria proa vs cauda (≤ 0,20 m/s)** | **0,001 m/s** (1,001 / 1,000 / 1,001) | **0,004 m/s** (0,966 / 0,970 / 0,968) |
| vento constante não desvia ⟨vx⟩ (≤ 0,30) | 0,001 m/s | 0,004 m/s |
| rajadas p=0,15 u_max=3: RMS(vx−1) (≤ 0,45) + quedas | 0,27–0,32 m/s · **0 quedas** | 0,30–0,35 m/s · **0 quedas** |
| Q (subir) ⟨vz⟩ ≈ +0,7 (±0,25) | +0,684 m/s | +0,747 m/s |
| E (descer) ⟨vz⟩ ≈ −0,7 (±0,25) | −0,629 m/s | −0,722 m/s |
| paragem com vento de 2 m/s: \|v\| (≤ 0,25) + deriva (≤ 0,6 m) | 0,01 m/s · 0,19 m | 0,02 m/s · 0,26 m |
| baseline nulo FALHA os limiares (não-tautologia) | ✓ falha | ✓ falha |

Os valores são médias da janela estável de cada guião (2.ª metade; Q/E medem nos 0,2–1,2 s, antes de a
referência saturar na caixa z ∈ [0,25; 2,75]). O **teste de não-tautologia** corre os mesmos guiões com a
ação `[0,0,0,0]` (hover aberto, sem política) e exige que **falhem**: é a prova de que os limiares
separam mesmo «seguir» de «não seguir».

**Achados do treino (2026-10-10, medidos — não repetir os erros)**:

1. **Atrator da morte com recompensa linear**: a 1.ª versão do modo comando punia os erros de seguimento
   linearmente (v2b). Como a referência anda, os erros crescem a metros e cada passo custava −1…−3, ao
   passo que capotar custa −100 uma só vez — «terminar cedo ficava MELHOR do que voar» (o MESMO achado
   já documentado na v3-real da planta real). Medido: a política cf2 capotava aos 16 passos de propósito.
   **Correção**: recompensa LIMITADA (`tanh`, como a v3-real, pesos que somam 1, morte −50): cada passo
   vivo vale r ∈ [0, 1,5] e morrer nunca compensa;
2. **Atrator «sentar no chão»** com o modo comando do zero: mesmo com a recompensa limitada, a política
   descobre que desligar os motores e ficar no chão dá r≈0,7/passo SEM risco de queda — e não descola
   (medido: 840 k passos na planta real e 780 k no cf2, ambos sentados; com perfis de comando desde o
   início, ainda pior). **Correção**: arrancar SEMPRE de uma política que já voa — `transferir_politica.py`
   copia os pesos para a obs de comando (linhas do `v_ref` a zero; validação: ações idênticas em
   `n` estados sem comando) e o fine-tune só tem de aprender o SEGUIMENTO (resolveu em ~400 k passos);
   `--sem-perfis-comando` é o estágio 0 para quem quiser treinar pairagem em modo comando sem os perfis;
3. **`--sucesso 450` (o critério do hover) parava o treino de seguimento a meio** (disparou aos 400 k com
   `frac_xy_z` = 0,09): em modo comando o default passa a **720** (o teto é 1,5×500 = 750);
4. O **cf2 não aprende a voar de raiz** nem no modo clássico (confirmado: 400 k passos sem descolar — a
   campanha v2b precisou de 20 treinos/25 M passos); a planta real voa quase de imediato porque o FC
   dedicado fecha a malha de taxa (o clássico voava já aos 40 k passos).

**Estado honesto no site**: com uma política **clássica** (sem `--comandos`) o runner ignora o bloco `voo`
com aviso e o eco vem `null` — o painel diz «modo comando indisponível: esta política não foi treinada com
`--comandos» e desativa os controlos (testado em `teste_controle_voo.py` §3b).

### Deploy — ONNX, validação numérica e latência

Exportação com o *exporter legacy* (`torch.onnx.export(..., dynamo=False)`; `dynamo=True` exigiria
`onnxscript`, que não está instalado), entrada **estática `(1, 16)` float32**, opset **17**,
`do_constant_folding=True`, sem `dynamic_axes`.

| item | valor medido |
|---|---|
| ops do grafo | `Gemm` ×3 · `Tanh` ×2 · `Cast` ×1 · `Flatten` ×1 (**sem `Clip`**) |
| ficheiro | `policy.onnx`, 23 507 B, IR 8, `onnx.checker` OK |
| validação | `max\|Δ\|` grafo vs **média da gaussiana** = **5,72e-06** (limiar 1e-5), 1 024 obs **reais** |
| contraprova | `_predict(deterministic=True)` vs média: `max\|Δ\|` = **0** |
| corte fora do grafo | 2 508 de 4 096 valores com `\|média\| > 1` → quem corta é o `env`/`predict`, não o grafo |

O que se compara é a **ação determinística** (`get_distribution().mode()` = média da gaussiana,
`squash_output=False`), **não** uma amostra. O `max|Δ|` de 10,17 contra `model.predict` **não** é erro
numérico: o `predict` corta a ação a `[-1, 1]` e o grafo não.

### Benchmark proxy de 1 core (o alvo de RUN é um Raspberry Pi 5, 4×A76 — isto é um **proxy**)

| medição | p50 | p99 | max | veredicto |
|---|---|---|---|---|
| fp32, 1 thread | **4,67 µs** | 5,06 µs | 72,0 µs | cabe a 50 Hz (20 000 µs) **e** a 100 Hz (10 000 µs) |
| fp32, 4 threads (contraste) | 4,75 µs | 6,66 µs | 165,9 µs | idem |
| int8 (`quantize_dynamic`, QInt8) | 6,03 µs | 6,73 µs | 10,6 µs | idem — mas **0,24–0,77× a velocidade do fp32** |

int8 reduz o ficheiro para **0,494×** (11 622 B) com `max|Δ|` vs fp32 de **0,21** — e no x86 sai **mais
lento** (0,24–0,77× conforme a medição): a quantização dinâmica não encontra aqui os *kernels* que a
tornam vantajosa. 212 320 inferências/s num core (fp32).

### Multi-IA — 4 processos a 50 Hz, cada um com a sua sessão ORT

| item | valor |
|---|---|
| processos / iterações | 4 · **1 996** |
| p99 agregado | **241,5 µs** (p50 86,5 µs, max 464 µs) |
| perdas de deadline (20 ms) | **0** |
| *throughput* total | 195 inferências/s (`parede` 10,24 s) |
| `loadavg` antes / depois | 1,35 / 1,44 |

`--pinned` foi validado à parte com **16 processos** (um por core): **16/16 cores distintos**, todos os
índices no core esperado, p99 agregado 381,0 µs, **0 perdas em 192 iterações**.

## Validação

| prova | comando | resultado |
|---|---|---|
| ambiente por fórmulas fechadas | `run.py` | **243/243 [OK]** (re-medido 2026-10-10), 0 falhas · inclui o cf2 (146) e a planta real (97) |
| controle de voo (contrato r11) | `teste_controle_voo.py --navegador` | **§1** 36 peças (funções puras, envs, retro-compatibilidade) · **§2** seguimento nas 2 plantas (calmaria, **simetria proa/cauda**, rajadas, Q/E, paragem + não-tautologia) · **§3** servidor real (`POST /api/voo`, 400 por gralha, eco, merge, honestidade com política clássica) · **§4** navegador real (keycaps WASDQE a acender/apagar, `v_ref` ao instante, POST chega ao servidor) |
| animação visual das hélices | `run.py` §10 (13 checagens) + `helices_render.py` | hélices rodam ∝ √t_i com o sentido de `GIRO` e param com os motores desligados; **física idêntica AO BIT** (max\|Δ\| = 0) com a animação ligada/desligada e vs o modelo upstream · 2 imagens EGL em `out/helices_1.png` e `out/helices_2.png` |
| `HoverEnv` como `gym.Env` | `run.py` §5 | `check_env` do SB3, `reset(seed)` determinístico, `info` e truncagem corretos |
| robustez do ambiente | `run.py` §7 | não-finitos → `ValueError` (vento/ação/`alvo_z`), `alvo_z ∈ [0,10, 2,90] m`, divergência → `RuntimeError` |
| critério v2b (vento + orientação) | grelha 0–3 m/s × 4 azimutes × 3 seeds | **16/16 PASS, 0 terminações** — re-medido por um **agente independente** (16/16 e 32/32 na grelha densa própria) |
| câmara v2 (contrato, seguimento, servidor) | `teste_camera.py` | **50/50** — 17 peças do contrato v2 · 15 ciclo real com viewer falso · 13 servidor real · 5 não-tautologia |
| PARAR (nenhuma rajada sobrevive) | `teste_parar_vento.py` | **20/20** sem flags · **23/23** com `--http --navegador` (r13: +4 cenários dos 3 botões, +1 de autoridade; antes do cockpit 15/15 · 16/16 · 18/18) |
| arranque SEM REINÍCIO (loop/REINICIAR/controlo) | `teste_arranque_loop.py` | **72/72** (r13: §4 reescrito contra o cockpit; antes 68/68) |
| site — comandos/gestos de câmara | `npm run test:camera` (em `site/`) | **62/62** (20 round-trip + 42 gestos), mais a prova DOM/CDP **37/37** |
| suíte do laboratório | `uv run pytest .agents/mujoco-lab-coala-agent-skill/tests -q` | **30 passed** |
| integração das peças (treino/UI/sonda/deploy) | verificação adversarial em 4 peças (v1) + 4 peças (v2) + 3 rondas de reparação | **9 PASS / 1 FAIL** (o FAIL era o `runs()` do `dashboard.py`; reparado e re-verificado) · v2: contratos todos PASS após reparações e re-verificações pontuais |

Condições de medida dos µs: máquina ociosa (`loadavg` 1 min **1,35** antes do benchmark, 1,44 depois);
o `deploy.py` regista o `/proc/loadavg` antes/depois em todos os relatórios exatamente por isso.

## Limites e nits conhecidos

**Controle de voo (r11, 2026-10-10)** — o que o contrato NÃO cobre (honesto):

- **Só velocidade + altitude**: as teclas comandam `v_ref` (1,0 m/s horizontal, 0,7 m/s vertical); não há
  comandos de RUMO (o yaw é fixo em 0, como no hover) nem de posição direta. A caixa de trabalho é
  `xy ±4 m`, `z ∈ [0,25; 2,75]` m e na borda a referência PARA (o drone paira na parede, não continua);
- **não treinar `--comandos` do zero**: converge para o atrator «sentar no chão» (medido, ver
  §Resultados/achados) — a receita é `transferir_politica.py` + fine-tune; o `--sem-perfis-comando` só
  serve para o estágio 0 (pairagem na obs de comando);
- as políticas de comando seguem a **velocidade** proposta — a posição deriva se o piloto não corrigir
  (é controlo de velocidade, não de posição absoluta; ao soltar as teclas o drone segura a posição atual,
  não volta ao ponto de partida);
- a simetria proa/cauda foi medida com vento CONSTANTE de ±2 m/s e rajadas até 3 m/s (o envelope do
  treino); ventos acima disso não estão certificados.

**Planta real (2026-10-10)** — o que falta medir ou ainda não cobre:

- **SysID do hardware**: kf/kq/curva do ESC vêm das tabelas T-Motor (+7,5 % de realismo); J do rotor, R efetiva,
  download e arrasto de rotor são estimados (a DR cobre as faixas). Medir em banco (empuxo, binário, rpm, corrente
  a 6S) e o pack (capacidade a 1C, DCIR) — nenhuma alegação de baterias passou a verificação adversarial.
- **Massa do frame DIY** (235 g + 50 g de pernas) é estimada pela densidade do carbono: pesar e corrigir no catálogo.
- `view.py`, `dashboard.py`, `net_probe.py` e `helices_render.py` continuam a ser ferramentas do **cf2**
  (a planta real usa o site (`sim_site.py`), o `train.py`, o `deploy.py` e o `valida_real.py`); o `view.py`
  e o `net_probe.py` já abrem o env em **modo comando** quando a política carregada é `--comandos` (19 obs).
- O FC simulado faz a malha de TAXA (modo acro); modos de ângulo/altitude do firmware não são simulados — quem
  estabiliza atitude e posição é a política (a decisão do dono).
- Sem magnetómetro o rumo absoluto não é observável: a recompensa usa o rumo relativo ao do arranque.
- A autonomia de 99 min é de pairagem pura em ar parado; o caso real publicado mais próximo voou ~30 % abaixo
  da tabela — espere ~80–90 min.
- **O rumo real deriva com o bias do giroscópio** (medido no site com o painel de voo, 2026-10-10): a política
  segura o rumo ESTIMADO (giroscópio integrado, sem bússola) e o rumo VERDADEIRO afasta-se a ~0,35 °/s — +30°
  de erro do estimador ao fim de 80 s (bias residual sorteado ≈ 1,9σ dos 0,2 °/s do BMI088 no catálogo). Em
  voos longos o drone roda devagar sobre si mesmo; a cura é física: calibrar o bias do giroscópio em repouso
  antes de descolar e/ou um magnetómetro no build.
- **O xy (~6 cm nominal, ~9 cm sob DR) é limitado pelo estimador de bordo**, não pela política: ela segura a posição
  ESTIMADA a 1–5,5 cm, e a odometria por fluxo ótico deriva 2–11 cm da verdade em 10 s (medido; ver os
  resultados acima). Melhorar o estimador (Kalman fluxo + acelerómetro, escala do fluxo calibrada) ou dar-lhe uma
  referência absoluta vale mais do que treinar mais.
- **O treino corre em PyTorch (Stable-Baselines3)**, a stack do laboratório — não em TensorFlow. Os dados das peças
  entram no treino pelo ambiente (física gerada do catálogo, DR à volta dos valores das peças, `hardware.json` ao
  lado de cada política); o que vai para o RPi é um ONNX neutro (onnxruntime). Quem preferir TensorFlow Lite pode
  converter esse ONNX (ex.: `onnx2tf`) — não testado aqui.


- **Limite RPi 5 só na RUN, treino a poder máximo** — decisão do dono: o treino corre com os 32 threads
  disponíveis; o limite de 1 core é imposto **apenas** no *benchmark* (`--threads 1`, proxy do A76) e no
  `--pinned`.
- **A latência medida é de um proxy x86**, não do RPi 5. O ganho do int8 no alvo **não** está medido aqui:
  um estudo independente no Cortex-A76 reporta que a **quantização estática** (QOperator) corre
  1,25–2,70× mais rápido que o fp32, e que o determinante é *estática vs dinâmica* (mais de 4×) — este
  experimento usa `quantize_dynamic`, precisamente a variante que esse estudo aponta como perdedora em Arm
  ([Zenodo 22163336], conteúdo externo, não verificado nesta máquina).
- **Envelope de vento (medido)**: fiável até **3 m/s** (`‖xy‖ ≤ 0,12 m`); a **3,5 m/s** fica no fio do limite
  alargado (0,146 m contra 0,15 m), a **4 m/s** dá 0,189 m e a **5 m/s** 0,285 m — a degradação é **suave**
  (mais deriva, **zero quedas até 5 m/s** em 12 rollouts por velocidade). Altitude e orientação aguentam
  todo o envelope testado (`|z−1| ≤ 0,0045 m`, `|yaw_err| ≤ 0,03 rad`).
- **`--sucesso 450` não dispara com a recompensa v2b**: o `mean_ret` final do run que passou é **350,0**
  (a escala mudou com os pesos). Para paragem automática usar ≈ **330–345** (`--sucesso 340`).
- **A régua do currículo mede sem vento**: o avanço de estágio usa `frac_xy_z` medido nos rollouts de
  avaliação, que correm **sem vento** (régua estável entre estágios). Consequência assumida: um estágio
  pode subir sem que o vento desse estágio esteja dominado — a robustez ao vento mede-se à parte, com a
  grelha. Medido: `frac_xy_z` sobe a 0,80–0,92 logo na 1.ª avaliação e os estágios avançam 0→1→2→3.
- **`best_model.zip` é escolhido pelo retorno sem vento** (`EvalCallback` com env de avaliação em ar
  parado), logo pode **não** ser o melhor artefacto para vento — neste experimento o `final.zip` do run
  final é o artefacto validado. Selecionar por grelha dentro do `train.py` é trabalho futuro.
- **`alvo_z: true` é aceite** pela API do dashboard: `float(True)` dá `1,0` em Python (o `bool` é subclasse
  de `int`). A faixa é validada (`[0,10, 2,90] m`), o **tipo** não é estrito.
- **`plotext` 6.1.0** não expõe o `plot()/build()` clássico → o painel do `train.py` desenha a curva de
  retorno com uma *sparkline* própria em blocos Unicode, sem dependências.
- **SIGSEGV intermitente no fecho do viewer** (mujoco 3.15 + pyGLFW, KDE Wayland): fechar a janela e sair
  logo a seguir faz correr o `glfw.terminate()` do `atexit` ao mesmo tempo que a thread do viewer. Acontece
  **no fecho**, com o ciclo a devolver 0; mitigado em `view.py` com `esperar_fecho()` (espera que o handle
  perca a referência ao simulador, teto ~2 s).
- **`multiprocessing.Pool` reutiliza workers**: a afinidade de core tem de ser calculada no processo **pai**
  e passada ao filho (o filho só a aplica e confirma). Calcular o core dentro do filho herdaria a afinidade
  da tarefa anterior — é o que `mapear_nucleos` evita.
- **Contagem do SB3**: `EvalCallback`/`CheckpointCallback` contam **chamadas do callback**, e cada chamada é
  um passo do *vec* (`n_calls = timesteps / n_envs`), não um passo de ambiente. O `--eval-freq` está em
  passos do vec.
- **`--retomar` do SB3**: `learn()` tem `reset_num_timesteps=True` por omissão; usar `False` para a contagem
  acumular (senão o treino recomeça do zero). E o fine-tune **não** aplica `--log-std-init`/`policy_kwargs`
  (a arquitetura vem do checkpoint) — só `lr` e o L2 do CLI entram nos `param_groups`.
- **D2/D3 aceites (limites do desenho)**: uma **queda pousada não é morte** (o piso impede `z < 0` e o
  limiar de terminação é 0,005 m); e **ficar no chão é pior que terminar** — 500 passos parado acumulam
  ≈ **−493** contra ≈ **−101** de um episódio que termina cedo.
- **A política não é um controlador de voo certificado**: é robusta ao vento **dentro do envelope treinado**
  (≤3 m/s sustentado, elevação pequena). Não foi treinada com **atraso de atuador**, **ruído de IMU**
  (`ruido_obs` existe, padrão 0) nem **variação de massa/ganhos** — nada disso está garantido fora do
  simulado.

## Próximos passos

1. **Validar o modo janela com o dono** (`view.py`) — HUD de 8 linhas, 3 figuras e o `esperar_fecho()`
   foram exercitados **sem janela** por agentes; falta a confirmação visual no posto de trabalho
   (e o painel de vento do dashboard, que foi validado por DOM headless + CDP, não com olhos).
2. **Revalidar a latência no Raspberry Pi 5 real** — os 4,67 µs p50 são de um proxy x86; medir lá o fp32 e
   o int8 com a mesma sessão ORT de 1 thread.
3. **Decidir o int8 no alvo** — testar a quantização **estática** (QOperator) no RPi, que a evidência
   externa indica ser a variante que compensa em Cortex-A76, antes de adotar int8 por omissão.
4. **Estender o envelope e a robustez**: treinar com `--vento-max 4`–`5` (o `xy` a 3 m/s, 0,119 m, é o
   único termo perto do limite), e acrescentar **condições iniciais variáveis** (o `reset` atual é sempre a
   mesma pose pousada com jitter de ±2 cm) para uma medida de robustez estatisticamente mais forte.
5. **Selecionar o checkpoint por grelha dentro do `train.py`** (hoje o `best_model` é escolhido pelo retorno
   **sem** vento) e automatizar o avaliador da grelha como critério de fim do treino.
6. **Planta real — do simulador ao drone**: (a) SysID em banco dos motores/hélices/ESC e do pack (corrigir o
   catálogo com os valores medidos e re-treinar com o mesmo comando); (b) melhorar o estimador de bordo (é ele que
   limita o xy); (c) medir no RPi 5 real a latência do ator (1, 21) e o jitter do loop a 50 Hz com o FC por UART;
   (d) voo cativo (preso por um cabo) antes do primeiro voo livre.

## Fontes citadas (conteúdo web = `untrusted`, só citado)

- [mujoco_menagerie · bitcraze_crazyflie_2](https://github.com/google-deepmind/mujoco_menagerie/tree/main/bitcraze_crazyflie_2) — modelo MJCF (cópia local em `models/`, MIT) e a nota de que os `ctrlrange` são *"arbitrary and need to be further tuned"*.
- **MuJoCo-Drones-Gym: A GPU-Accelerated Multi-Drone Simulator for Control and Reinforcement Learning** — [arXiv 2606.08039](https://arxiv.org/pdf/2606.08039) · preprint · nível B · lida: trechos — origem da equação de recompensa usada literalmente.
- [INT8 configuration study on Raspberry Pi 5 (Arm Cortex-A76)](https://zenodo.org/records/22163336) · software · MIT · conteúdo externo — latências de modelos quantizados em ORT no A76; quantização estática vs dinâmica e níveis de otimização de grafo.
- [crazyflie_ros (whoenig)](https://github.com/whoenig/crazyflie_ros) — URDF de origem do modelo, via menagerie.
- [Datasheet Crazyflie 2.0 (Bitcraze)](https://www.bitcraze.io/documentation/hardware/crazyflie_2_0/crazyflie_2_0-datasheet.pdf) — 27 g; base do `thrust_max = 0,589 N` (4 × 15 gf → T/W ≈ 2,22).

Para o modelo, a camada `lab/crazyflie.py`, os sensores e as constantes físicas do Crazyflie 2, ver
[`models/bitcraze_crazyflie_2/`](../../models/bitcraze_crazyflie_2/) e
[`lab/crazyflie.py`](../../lab/crazyflie.py) (o antigo experimento `08_crazyflie_motores` foi removido
em 2026-10-08 — histórico no git).
