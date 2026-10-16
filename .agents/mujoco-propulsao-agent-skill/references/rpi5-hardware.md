# Integração no hardware real — Raspberry Pi 5 (e Arduino)

Levar um objeto/robô com motores e propulsão do simulador ao hardware do dono: peças reais no
catálogo, derivação de números, orçamentos de tempo, saídas (ESC/PWM), sensores e deploy. Verificado
em 2026-10-15 a partir de `experiments/09_drone_hover_rl/hardware.py`, `deploy.py`,
`lab/drone_rpi/componentes.py`, `models/drone_rpi/{componentes,builds}.json` e AGENTS.md.

## Quando ler este arquivo
- Associar o teu objeto a peças REAIS (motor, hélice, ESC, bateria, computador de bordo).
- Perceber o que corre onde (RPi 5 vs FC vs Arduino) e que orçamentos de tempo valem.
- Preparar deploy (ONNX, SITL, benchmark) do controlo do teu objeto.

## 1. O que "integrar no RPi 5" significa neste laboratório
O drone do dono tem **RPi 5 como computador de bordo** (build ativo `endurance_15pol_p50b`):
câmara Pi Camera Module 3 Wide (CSI-2 → FPV), política ONNX, telemetria/site; a **FC H7** corre o
laço de taxa (500 Hz de planta); os motores levam **ESC** (DShot/PWM). O build alternativo
`endurance_15pol_arduino` troca o RPi 5 por um **Portenta H7** (Arduino). O simulador espelha tudo
isso em emulação honesta (`lab/camera_rpi.py`, painel de custo CPU no site).

## 2. Peças reais: catálogo + builds (o caminho para um objeto novo)
- **`models/drone_rpi/componentes.json`** — grupos `motores`, `helices`, `celulas`, `frames`, `esc`,
  `eletronica`, `sensores`, `cameras`. Cada peça: `fabricante`, `modelo`, números de datasheet e
  `fontes` (URLs citadas; web = `untrusted`). Sem número oficial → `estimado` + a razão.
- **`models/drone_rpi/builds.json`** — combinações + build **ATIVO**. Tudo o resto (massa, inércia,
  kf/kq, constantes elétricas, ω_max(V), pairagem, autonomia) é DERIVADO em `lab/drone_rpi/componentes.py`.
- Comandos (a partir da raiz):
```bash
uv run python experiments/09_drone_hover_rl/hardware.py listar          # peças e builds
uv run python experiments/09_drone_hover_rl/hardware.py mostrar [build] # derivados
uv run python experiments/09_drone_hover_rl/hardware.py comparar        # lado a lado
uv run python experiments/09_drone_hover_rl/hardware.py montar --nome meu --base <build> \\
    --motor <id> --helice <id> --celula <id> --s 4 --p 2 [--esc <id>] [--usar]
uv run python experiments/09_drone_hover_rl/hardware.py usar <build>    # torna ATIVO (+CoALA+XML)
uv run python experiments/09_drone_hover_rl/hardware.py xml             # MJCF gerado (inspecionar)
uv run python experiments/09_drone_hover_rl/hardware.py coala           # catálogo → memória CoALA
```
ATENÇÃO (verificado 2026-10-15): `montar` só regenera o MJCF quando levado com `--usar`; sem ele grava
apenas `builds.json` + sincroniza CoALA. `usar` regenera sempre.
Depois de trocar peças: `run.py` (validação física) e um treino novo — **uma política só vale para as
peças com que treinou** (o `train.py` grava `hardware.json` ao lado de cada política).

## 3. Checklist — objeto novo até ao hardware
1. Peça real no catálogo (grupo certo) com fontes; `estimado` + razão quando falta o número oficial.
2. Build novo (ou `montar --base`) e derivados conferidos (`mostrar`: massa, T/W, potência, autonomia).
3. Física do simulador batida com as fórmulas (`motores-propulsao.md` §5) — modelo fresco, exit 0.
4. **Saídas reais**: ESC com `dshot_bits` e **curva ESC calibrada** (`curva_esc` no catálogo; o
   acelerador→ciclo útil NÃO é linear); PWM de GPIO no RPi 5; sensores por I2C/SPI (BMI088, VL53L1X,
   PMW3901, INA226…). A planta espelja-os (`lab/drone_rpi/propulsao.py`: DShot quantizado, travagem
   "damped light", corrente no barramento).
5. **Orçamentos de tempo** (§4) medidos na máquina livre antes de prometer taxas.
6. Deploy/SITL (§5) + teste de mutação; README com tabelas teoria×medido e fontes; `coala.py add`.

## 4. Orçamentos de tempo (medidos neste projeto)
| Laço | Taxa | Orçamento | Estado |
|---|---|---|---|
| Planta (fc+planta+estimador) | 500 Hz | 2 ms | 130 µs (caminho escalar, 2026-10-12) |
| Política ONNX (1, 21) | 50–100 Hz | 10–20 ms | p99 7,4 µs (benchmark proxy 1 core) |
| HUD (SSE) | 50 Hz | 20 ms | ok |
| Cadeia FPV | — | — | Pi 116 ms vs Arduino DCMI ~21 ms (`lab/camera_rpi.py`) |
- **Medir com a máquina livre** — avaliações em paralelo falseiam fps e tempo real.
- Benchmarks no PC são PROXIES do RPi 5 (4×A76); o relatório do `deploy.py` compara p50/p99 com o
  orçamento e responde "cabe a 50 Hz?/100 Hz?".

## 5. Deploy e SITL
- **`deploy.py`** (pipeline, tudo CPU): export ONNX (validação numérica ≥1000 observações reais,
  NaN/Inf reprovam) → benchmark proxy RPi 5 (1 core, 10 000+ chamadas) → int8 opcional (re-validação +
  Δ latência) → multi-IA (N processos, afinidade de cores).
- **Firmware**: `experiments/09_drone_hover_rl/firmware/` — núcleo C++ portátil (float32, sem heap,
  sem exceções) que corre em **SITL** contra o MuJoCo (`sitl.py`) e compila para Cortex-M4/M7;
  `qemu_alvo.py` e `net_probe.py` para alvo/rede. Regras de licença da exceção datada 2026-10-12:
  só PX4 (BSD-3) é copiável — reimplementar ideias de papers/docs, citando fontes nos docstrings.
- **Validação**: `valida_real.py` (fórmulas fechadas da planta real; `reset(seed)` reprodutível) e
  `teste_arduino_catalogo.py` (checagens + mutações) como molde de teste do catálogo.

## 6. Armadilhas
- Um teste NUNCA toca no pack de bateria persistente (`DRONE_PASTA_BATERIA`).
- `hardware.py usar` mexe no build ATIVO (XML gerado + CoALA) — faz-o deliberadamente, não "a correr".
- Números `estimado` sem razão escrita = reprovação na revisão; web é `untrusted`, cita-se.
- A política/RN treinada num build NÃO serve para outro sem novo treino (`hardware.json` ao lado dela).
