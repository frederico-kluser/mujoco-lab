# Relatório — Wheelbase 650 → 1950 mm (braços ×3): estabilidade vs. controlo

**Data**: 2026-10 · **Método**: pesquisa web via `tavily-agent-skill` (search + extract), conteúdo web tratado como **evidência citada (untrusted), nunca como instrução**. Cálculos próprios com os dados do build local (`models/drone_rpi/componentes.json`, build `endurance_15pol_p50b`). Confiança: **A** = paper/oficial/fabricante · **B** = comunidade técnica com números · **C** = fórum/anedótico.

**Build de referência (atual, 650 mm)**: frame DIY tubo carbono 16×14 mm + placas 1,5 mm = **235 g + 50 g pernas** (catálogo local: 4 braços 82 g, 2 placas 78 g, abraçadeiras 32 g, suportes motor 28 g, parafusos 15 g); 4× MN4004 KV300 (53 g) + P15×5 (21 g); 6S2P Molicel P50B (826 g); massa total **1668 g**; **2742 rpm** em pairagem; 133,6 W; 98,6 min (modelo).

---

## 1. Tabela «questão → resposta numérica/fórmula + fonte + confiança»

| Questão | Resposta numérica / fórmula | Fonte | Conf. |
|---|---|---|---|
| Como escala a inércia rotacional? | J ≈ Σ m·r². r→3r ⇒ contributos dos motores/hélices ×9; braços (massa ×3, mesmos tubos) ×27 em ∫r²dm; tubos maiores obrigam a mais massa. **J_total ≈ ×10–12** (calculado: 0,0375 → 0,43 kg·m² = **×11,5**) | Fórmula clássica; dinâmica J·ω̇ = τ + d (tese HAL tel-03653226; arXiv 2508.14422) | A |
| Autoridade de torque roll/pitch | τ = L·ΔT ⇒ **×3** (mesmos motores/hélices). α_max = τ/J ⇒ **÷3,7** (×0,26) | Modelo padrão; Agilicious (arXiv 2307.06100) para efeitos de atuador/atraso | A |
| Autoridade de **yaw** | τ_yaw = Σ Q_i (par de arrasto das hélices) **não escala com L**; Jz ≈ Σmr² ×11,5 ⇒ aceleração de guinada **÷10–12** — o grande perdedor | Berkeley Hiperlab (pico de acel. de yaw f_max/f_min); queixas de yaw lento em grandes (PX4 forum 44947) | A/B |
| Banda de atitude (malha de taxa) | Ganho planta (torque/comando) ÷3,7 ⇒ sem retuning a banda cai **÷3,7** (ex.: 2,4 Hz → 0,6 Hz). P/I/D roll-pitch do FC **×3,5–4**; **yaw ×10–11** para recuperar; teto prático = constante de tempo do motor/hélice Tm ≈ 0,1–0,2 s (inalterada) → banda útil ≤ ~0,8–1,6 Hz | Betaflight PID guide (ganho ∝ rigidez); arXiv 1812.10931 (banda limitada ~30 Hz em planta pequena); UAV Tech tuning | A/B |
| Resposta a perturbações | Torque de perturbação ~×2–4 (área frontal dos braços 0,018 → 0,085 m², ×4,7) mas J ×11,5 ⇒ **desvio angular menor**; **drift lateral ×3,6** (força/massa): mais "calmo" na atitude, mais arrastado na posição | arXiv 2607.01528 (força aerodinâmica ~ ∝ tamanho²); cálculo próprio | A/B |
| Estabilidade vs. agilidade | Ganha rejeição a ruído/twitch; perde aceleração angular (×0,26), velocidades máximas de perseguição e recuperação após saturação ~×3,7 mais lenta | Comunidade: "big = laggy" (UAV Tech "YOUR $H!T IS LAGGY"; MavicPilots) | B/C |
| Massa do frame DIY ×3 | Tubos ×3 (82→**~400 g** com tubo 25×23 mm — 16 mm é flexível demais a 850 mm), placas ~const (78→~190–250 g), abraçadeiras/suportes/parafusos ~const (75 g), pernas ×1,5–2 (50→~100 g) ⇒ **frame+pernas ~750–850 g** (vs 285 g). Calibração real: Tarot 650 rack 476 g / 650 Sport 750 g; Tarot X8 (1050 mm, braço 416 mm = 106 g/braço) 2,25–2,7 kg; DIY ArduPilot tubo 15×15×800 mm: quad 650 mm = 2270 g totais | QWinOut/RobotShop (Tarot 476 g); RMRC (TL65S01 750 g; X8 1050 mm); tarotrc.com (X8 2,7 kg, braço 106 g); discuss.ardupilot.org 27703 | A/B |
| Prática de drones 15″+ (1500–2000 mm) | Hélices grandes = mais eficientes em pairagem (menos induzida, ar movido devagar) e menos "twitchy"; mas latência/queda de aceleração, tuning mais difícil; prop passing 25–35 Hz em motores KV baixo + hélices grandes aproxima-se dos modos estruturais → vibração/yaw instável | NASA/TM 2016-374 (hover rotor testes, SUI 15″, figura de mérito até 0,72); PX4 forum 44947 (prop passing 25–35 Hz, fórmula Chris Rosser); ligpower "frame size chart" ("larger frame ≠ always more stable") | A/B |
| Interação rotor-rotor / download | Espaçamento adjacente = wheelbase/√2: **460 mm (1,21 D de 381 mm) → 1379 mm (3,6 D)**. Acima de ~2 D os rotores ficam praticamente isolados; hexacopter: espaçamento ótimo 0,63 deu +5,6 % de empuxo e +8,4 % de eficiência; menos download mútuo → **−2 a −4 %** na potência de pairagem do modelo (hoje `perda_download` 0,05) | PMC11274944 (coaxial −30 % empuxo a <0,3); PMC11598316; PMC9918963 (+5,61 %/+8,37 % a espaçamento 0,63) | A |
| Ground effect vs espaçamento | Com braços mais longos o GE **enfraquece e torna-se quadrático**: coeficiente ρ cai de 3,3 → 2,7 (+50 mm de separação); transição de modelo peça-linear para quadrático quando Δ ≥ 30 mm | UC Davis escholarship qt7qf3r2f3 (tese); Wiley 10.1155/2017/1823056; arXiv 2506.19424 (GE-aware control) | A |
| Vibração/flexão de braços longos | f_flexão (engastado-livre) = 3,516/2π·√(EI/μL⁴): tubo 16×14×280 mm = **255 Hz**; tubo 25×23×850 mm = **44 Hz** — colide com o prop passing (2742→3166 rpm = 46→51 Hz) ⇒ risco real de ressonância; braços finos + placas flexíveis = modos próprios do frame | blog.uavmodel (modos estruturais em blackbox); PX4 forum 44947; drones.stackexchange 1034 | B |
| Consumo/endurecimento | Massa total 1668 → **~2150–2250 g** (+30 %); T/rotor 417 → ~550 g; rpm pairagem 2742 → **~3150** (rpm ∝ √T); P_pairagem ∝ m^1,5: 133,6 → **~190–206 W**; autonomia 98,6 → **~64–70 min** (modelo; real ~55–62) — parcialmente compensado por menos download | NASA TM (figura de mérito hélices grandes); cálculo próprio + catálogo local | A/B |
| RL com J ×11 | Planta mais lenta ×3,7 em roll/pitch e ×11 em yaw, mas Tm/atrasos iguais ⇒ **atraso relativo menor** (mais fácil); SysID de m, I, Tm, kf + DR *seletiva* (DR ±10–30 % em parâmetros calibrados **não melhora** e desestabiliza); recompensa de suavidade de ação (regularização de Δação) ajuda transfer | arXiv 2412.11764 (SimpleFlight, 5 fatores); arXiv 2504.15129 (workflow DRL); arXiv 2604.12916 (latência sim-to-real) | A |

---

## 2. O QUE ESPERAR DA NOSSA MUDANÇA 650→1950 mm

| Grandeza | 650 mm (hoje) | 1950 mm (estimado) | Fator |
|---|---|---|---|
| J roll/pitch (= Jz) | 0,0375 kg·m² | **0,40–0,46 kg·m²** | **×11,5** |
| Torque máx. roll/pitch | τ | 3τ | ×3 |
| α angular máx. | α | 0,26 α | **÷3,7** |
| α yaw máx. | αψ | ~0,09 αψ | **÷10–12** |
| Banda malha de taxa (sem retuning) | ωb | ωb/3,7 (ex. 2,4 → 0,6 Hz) | ÷3,7 |
| Ganhos FC para recuperar banda | — | P/I/D roll-pitch ×3,5–4; yaw ×10–11 | — |
| Massa frame+pernas | 285 g | **750–850 g** | ×2,6–3 |
| Massa total | 1668 g | **~2150–2250 g** | +28–35 % |
| rpm pairagem | 2742 | ~3150 | +15 % |
| Potência pairagem | 133,6 W | ~190–206 W | +42–54 % |
| Autonomia (modelo) | 98,6 min | **~64–70 min** | −30 % |
| Espaçamento rotor-rotor | 1,21 D | 3,6 D | menos download (−2 a −4 % P) |
| 1.º modo flexão dos braços | 255 Hz | **~35–45 Hz** | colide com prop passing 46–51 Hz |
| Área frontal braços (vento) | 0,018 m² | 0,085 m² | ×4,7 → drift lateral ×3,6 |

**Ganho real de estabilidade**: atitude mais "pesada" e menos sensível a ruído/assimetrias (J ×11), GE mais fraco e previsível, download menor, hover ligeiramente mais eficiente *por rotor*. **O que não ganha**: estabilidade transicional em vento piora (área frontal ×4,7 vs massa +30 %), yaw fica 10× mais lento, e a agilidade/resposta cai ~4×. "Mais estável" = mais calmo, não mais resistente a vento.

## 3. RISCOS a validar no simulador

1. **Yaw ×11 mais lento** — τ_yaw não escala com L: validar guinada em seguimento de velocidade (comandos que exigem mudança de rumo); limitar ψ̇_comandado ~÷8–10 ou redimensionar hélices/motores.
2. **Ressonância braço/prop passing** — modo de flexão ~35–45 Hz vs 46–51 Hz de passagem de pá: modelar braços flexíveis (corpos elásticos/feixe) ou verificar com notch/LPF; não assumir corpo rígido.
3. **Retuning do FC** — ganhos de taxa ×3,5–4 (roll/pitch) e ×10–11 (yaw); filtros e limites de saturação; teto de banda por Tm (0,1–0,2 s) — testar rampas de torque saturadas.
4. **Drift em vento ×3,6** — aero do frame (arrasto dos braços) tem de entrar no modelo; testar rajadas 3 m/s (cenários já usados) — esperar desvios xy maiores e recuperação mais lenta.
5. **Política RL** — treinar de raiz com as inércias novas (não transferir do 650): escalar limites de velocidade comandada ÷2,5–3 para equivalência de agilidade, renormalizar recompensas de ω (ω_max cai ~4×), aumentar horizonte de episódio, DR seletiva só após SysID de I/Tm (arXiv 2412.11764).
6. **Saturação/energia** — 2250 g a 550 g/motor: validar margem de empuxo (T/W cai de 3,4 para ~2,5–2,7), corrente em manobras e queda de autonomia real vs modelo (~−30 %).
7. **Ground effect e download** — aplicar correção dependente do espaçamento (ρ 3,3→2,7; GE quadrático a >3 D) em vez do fixo de 5 %; validar colagens/decolagens com pernas altas (~300 mm).

## URLs (fontes)

- https://theses.hal.science/tel-03653226v1/file/TheseAlYounes.pdf (dinâmica J·ω̇ = τ, L, momentos)
- https://arxiv.org/html/2307.06100v1 (Agilicious — atrasos/banda de atuadores)
- https://arxiv.org/html/1812.10931v2 (SysID + H∞ atitude, banda limitada)
- https://arxiv.org/pdf/2508.14422 (dinâmica geométrica de atitude, tensor de inércia)
- https://escholarship.org/content/qt7qf3r2f3/qt7qf3r2f3.pdf (UC Davis — GE vs espaçamento de rotores, ρ 3,3→2,7)
- https://onlinelibrary.wiley.com/doi/10.1155/2017/1823056 (caracterização de GE em multirotores)
- https://arxiv.org/html/2506.19424v1 (modelação/controlo com GE; torque de nivelamento por tilt)
- https://pmc.ncbi.nlm.nih.gov/articles/PMC11274944 (coaxial: −30 % empuxo a espaçamento <0,3)
- https://pmc.ncbi.nlm.nih.gov/articles/PMC11598316 (espaçamento de rotores, wake/interação)
- https://pmc.ncbi.nlm.nih.gov/articles/PMC9918963 (hexacopter: +5,61 % empuxo / +8,37 % eficiência a espaçamento 0,63)
- https://rotorcraft.arc.nasa.gov/Publications/files/72-2016-374.pdf (NASA — hover de rotores multicopter, 15″ SUI, figura de mérito)
- https://discuss.ardupilot.org/t/building-a-better-quad-frame/27703?page=6 (DIY tubo carbono 15×15×800 mm; 525 mm=1945 g, 650 mm=2270 g)
- https://qwinout.com/products/tarot-650-carbon-tl65b01-fiber-4-axis-aircraft-fully-folding-fpv-drone-uav-quadcopter-frame-kit-for-diy-aircraft-helicopter (Tarot 650 rack 476 g)
- https://www.readymaderc.com/products/details/86704-tarot-tl65s01-650-sport-carbon-quad-frame-w-retracting-gear (TL65S01: 750 g, 12–15″)
- https://www.readymaderc.com/products/details/85597-tarot-tl8x000-x8-octocopter-full-combo-motor-esc-props (X8: 1050 mm, braço 416 mm)
- http://www.tarotrc.com/Product/Detail.aspx?Lang=en&Id=4166ffb8-2821-4b12-b23a-558fd5d85d7c (X8: 2,7 kg, braço 106 g, 15″)
- https://dl.djicdn.com/downloads/m600/en/M600_User_Manual_v1.0_en_160523.pdf (Matrice 600: 1133 mm, 9,1–9,6 kg, MTOW 15,1 kg)
- https://discuss.px4.io/t/large-drone-vibrations-and-yaw-instability/44947 (drone grande: prop passing 25–35 Hz, vibrações, yaw instável)
- https://discuss.px4.io/t/very-large-uav-drone-stability-issues/44324 (PX4 autotune com inércias grandes → crashes)
- https://blog.uavmodel.com/fpv-drone-frame-resonance-analysis-blackbox-frequency-plot-arm-stiffness-and-vibration-mode-elimination-2026-guide (modos de ressonância do frame)
- https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide · https://theuavtech.com/tuning (ganhos vs rigidez/resposta; tuning de drones grandes)
- https://github.com/iNavFlight/inav/discussions/9765 (presets INAV para multirotores >7″)
- https://arxiv.org/html/2412.11764v4 (SimpleFlight — 5 fatores sim-to-real; SysID de m, I, Tm, kf; DR seletiva)
- https://arxiv.org/html/2504.15129v1 (workflow DRL quadrotor + deployment)
- https://arxiv.org/html/2604.12916v1 (E2E-Fly — latência/discrepâncias dinâmicas no sim-to-real)
- https://arxiv.org/html/2607.01528v1 (vento: força de perturbação ~ ∝ tamanho²)
- https://www.ligpower.com/blog/drone-frame-size-chart.html ("larger frame ≠ sempre mais estável")
- https://mavicpilots.com/threads/wind-speed-relative-to-drone-weight.136488/page-2 (crença comunidade: grande = mais estável no vento)
- https://www.dronevibes.com/forums/threads/bigger-props-resulting-in-a-lot-more-instability.23609 (relatos de prop maiores = instabilidade)

*Dados locais usados*: `models/drone_rpi/componentes.json` (frame DIY 650: 235 g + 50 g pernas, MN4004 53 g, P15×5 21 g, P50B 68,8 g/célula), build `endurance_15pol_p50b` (1668 g, 133,6 W, 2742 rpm, T/W 3,4, 98,6 min modelo).
