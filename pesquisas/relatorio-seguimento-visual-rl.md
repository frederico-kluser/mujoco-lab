# Arquiteturas multi-IA / cascata para seguimento visual por RL — relatório de pesquisa

*Método: Tavily (`search` ×11, `extract` ×5). Web = evidência citada. Confiança: **A** = paper/oficial, **B** = comunidade, **C** = fórum.*

## Tabela evidência

| # | Pergunta | Resposta numérica / recomendação | URL | Conf. |
|---|---|---|---|---|
| 1 | Treinar externa sobre interior congelada? | Sim: **freeze inner, train outer** — atualizar só o nível alto é mais sample-efficient do que treinar ambos (ablação HRL quadrúpede) | [arxiv 2407.19142](https://arxiv.org/html/2407.19142v1) | A |
| 2 | End-to-end vs modular? | End-to-end pixels→comando: **~240 h GPU** (DreamerV3); modular ≪ e auditável | [Cardiff ORCA](https://orca.cardiff.ac.uk/id/eprint/172149/1/quadrotor_tracking__Copy_.pdf) | A |
| 3 | Estabilidade da pilha | Erro composto cresce com o horizonte em rollouts/model-based; mitigar com janela curta/multi-step | [OpenReview S1g_S0VYvr](https://openreview.net/forum?id=S1g_S0VYvr) | A |
| 4 | Observações do tracker | **12D**: v, ω, gravidade + z=[u,v,d] (centroide normalizado + profundidade). Sem propriocepção: sobrevivência **97,1%→4,4%**; profundidade dispensável (98,7% sem ela); erro de centro ≈**0,02** (2% do FOV) | [arxiv 2609.09234](https://arxiv.org/html/2609.09234v1) | A |
| 5 | Recompensas | r = λc·centro + λd·profundidade + λv·visível − λω·rotação − λh·altura; contínua e suave; TD3: aproximar + chegar estável | [arxiv 2609.09234](https://arxiv.org/html/2609.09234v1) · [MDPI Drones 8(11):628](https://www.mdpi.com/2504-446X/8/11/628) | A |
| 6 | Desempenho em alvo móvel | Erro de distância médio **0,6–1,5 m** (literatura UAV↔alvo); para *ponto* fixo esperar **0,1–0,3 m** com tracker centrado | [PMC9680462](https://pmc.ncbi.nlm.nih.gov/articles/PMC9680462) | A |
| 7 | Latência câmara→comando | Sensing **33 ms @ 30 Hz** + processing; baixa luz >100 ms → treinar COM latência 33–100 ms | [Scaramuzza, palestra](https://www.youtube.com/watch?v=vVataTRomsg) | B |
| 8 | Taxas de cascata | FC: rate **1000 Hz**, atitude **500 Hz**; externos (posição/visão) **25–50 Hz**; tracker embarcado **30 Hz** em Jetson TX2→Pixhawk | [ApplSci 10(15):5064](https://www.mdpi.com/2076-3417/10/15/5064) · [PX4 forum](https://discuss.px4.io/t/multicopter-control-architecture-design-choices/31815) | A/B |
| 9 | Deteção do ponto | Esfera brilhante: **threshold de cor + centróide/blob** chega (rápido, robusto); DL (YOLOv8) só ganha sob desfoque/occlusão, com custo CPU | [PMC7411990](https://pmc.ncbi.nlm.nih.gov/articles/PMC7411990) | A |
| 10 | Validação detector↔projeção | Reprojection error: **<0,5 px excelente, <1 px bom, >2 px mau** — gate de calibração câmara↔sim | [camcalib.io](https://www.camcalib.io/post/what-is-the-reprojection-error) · [PIX4D](https://support.pix4d.com/hc/en-us/articles/202559369) | B |
| 11 | Watchdog / fail-safe | PX4: offboard loss → `COM_OF_LOSS_T`; Betaflight: validação de sinal **100 ms** + estágios → replicar timeout **100–300 ms** | [PX4 Safety](https://docs.px4.io/main/en/config/safety) · [Betaflight Failsafe](https://betaflight.com/docs/wiki/guides/current/Failsafe) | A |
| 12 | CPU embarcado | Visão toda no companion (RPi 5); manter CPU do FC **<30 %** | [MEPSKing](https://www.mepsking.shop/blog/fpv-drone-flight-controllers-explained-f1-f3-f4-f7-h7-latest-version-2024.html) | C |

## RECOMENDAÇÃO PARA A NOSSA CASCATA

- **Arquitetura**: detector clássico (threshold da esfera brilhante → centróide + raio) → **tracker MLP 64–64** (sem CNN) → `v_ref` → política interior `--comandos` **congelada** → FC.
- **Obs (≈12D)**: [u,v] normalizado do centroide, raio/área (proxy de profundidade), flag *visível*, v_est, ω, gravidade do estimador — propriocepção obrigatória (ablação: sem ela 4,4% de sobrevivência).
- **Ação**: `v_ref=(vx,vy,vz)` (+ vyaw) saturado ±2 m/s / ±90°/s — dentro do envelope MEDIDO da interior.
- **Recompensa**: −2.0·‖e_centro‖ − 1.0·|d−d*| + 0.5·visível − 0.1·‖ω‖ − 0.05·‖Δv_ref‖ − grande penalidade por perder o alvo >0,5 s (contínua).
- **Treino**: PPO, **10–50 M passos**, latência de câmara injetada (33–100 ms), DR ±10 % nos ganhos da interior; avaliação 5 seeds × 200 episódios.
- **Taxas**: FC 500–1000 Hz · política de voo 50 Hz · tracker **25–30 Hz** (= fps da câmara emulada) · watchdog 100–300 ms.
- **Watchdog**: sem deteção → `v_ref=0` (pairar); 3 falhas seguidas → fallback da política interior/retorno; saturação sempre ativa; log de saúde.
- **Gate de validação**: reprojetar o ponto 3D conhecido e exigir **erro <1 px** antes de treinar.

## ARMADILHAS da cascata política-sobre-política

1. **Erro composto**: o exterior explora as falhas de seguimento da interior → limitar `v_ref` ao envelope medido e congelar a interior.
2. **Oscilação imagem↔comando** (banda tracker 25 Hz ≈ banda do laço externo). *Provar que não oscila*: FFT do erro de centro e de `v_ref` sem pico dominante; passo de 10 % no erro de pixel com sobressinal <1; atraso imagem→comando (correlação cruzada) ≤2 ciclos; ‖Δv_ref‖ limitado; survival ≥95 % em 5 seeds; avaliação COM latência real.
3. **Treinar com latência zero e voar com 33–100 ms** = instabilidade garantida.
4. **Recompensa mal escalada**: centrar sem manter distância (ou vice-versa) — normalizar erros e pesar λc/λd explicitamente.
5. **Atratores da interior** (capotar/sentar, medidos em `09_drone_hover_rl`) amplificados pelo exterior — incluir estados-limite no treino do exterior.