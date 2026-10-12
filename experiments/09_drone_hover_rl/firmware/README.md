# firmware/ — núcleo C++ portátil (Arduino / Cortex-M) + SITL contra o MuJoCo

O dono decidiu que estimador + estabilização + movimentação + olhar para o círculo correm num **Arduino**, com algoritmos
clássicos. Três atividades, no mesmo núcleo: **A** (base: laço de taxa + estimador, CTBR), **B** (a cascata clássica, o estimador
clássico e o OLHAR no núcleo, SITL fechado e prova no alvo Cortex-M — secção «Atividade B» abaixo) e **C** (visão → alvo → IBVS).
A secção «Interface» e as «Regras» abaixo descrevem a v1 (atividade A); a interface 2 (versão 2) acrescenta campos AO FIM dos structs.

```
firmware/
  nucleo/config.hpp     tipos POD: Config · Sensores · Comando · Saida (+ Modo, flags)   ← a interface
  nucleo/taxa.hpp       laço de taxa p,q,r + mistura X + airmode      (port de fc.py: ControladorFC.passo)
  nucleo/estimador.hpp  atitude · altura/v_z · v_xy do fluxo · odometria (port de estimador.py)
  nucleo/nucleo.hpp/.cpp  classe Nucleo: iniciar(cfg) · reiniciar() · armar(bool) · calibrar(s) · passo(s, cmd, dt)
  nucleo/capi.cpp       wrappers extern "C" para ctypes — SÓ para o SITL (não vai para o .ino)
  hal.hpp               HAL abstrata: o ÚNICO ficheiro que o .ino implementa (+ fw::ciclo)
  cross/math.h          <math.h> mínimo SÓ para o cross-check (sem sysroot ARM nesta máquina)
  cross/verifica_hal.cpp  só compila: confere que o hal.hpp é auto-suficiente e utilizável
  teste/estresse.cpp    driver de estresse (host, ASan+UBSan): entradas hostis, NaN/inf, invariantes
  --- atividade C («olhar para o círculo»; ver a secção no fim deste ficheiro) ---
  nucleo/visao_tipos.hpp  PODs da visão: Camera · ParamsDetetor · Deteccao · Atitude · ComandoVoo · ConfigSeguidor · SaidaSeguidor
  nucleo/visao.hpp      Detetor: limiar + momentos sobre um frame mono uint8 (componentes ligados em streaming)
  nucleo/alvo.hpp       estimador do alvo: α-β / KF-CV / KF-CA + histórico de atitude + compensação do atraso da câmara
  nucleo/ibvs.hpp       Seguidor: lei IBVS (yaw ← u, v_z ← v, v_x ← distância) + máquina de estados de perda
  nucleo/capi_visao.cpp wrappers extern "C" (ctypes) — SÓ para o SITL
  cross/verifica_visao.cpp  só compila: a cadeia detetor → Camera → Seguidor para o cross-check M4/M7
  teste/estresse_visao.cpp  estresse ASan+UBSan do detetor e do seguidor
../sitl.py              compila o núcleo → .so, config_de_hardware, DroneRealEnvNucleo (SITL / sombra)
../sitl_visao.py        ponte ctypes da atividade C + planta CINEMÁTICA do laço fechado (NÃO é o simulador completo)
../teste_nucleo.py      a prova (regras, host+cross, equivalência, shadow, malha fechada, estresse, mutações)
../teste_visao.py       a prova da atividade C (111 checagens: regras, host+cross, ciclos M7, detetor em frames EGL, estimador, IBVS, 13 mutações)
```

## Interface (`nucleo/config.hpp`)

| struct | campos |
|---|---|
| `Config` | `kp/ki/kd[3]`, `limite_i`, `fc_giro_hz`, `fc_d_hz`, `idle`, `mix[4][3]`, `u_pairagem`, `dt_nominal`, constantes do estimador, `versao` |
| `Sensores` | `giro[3]`, `acc[3]`, `tof_d`, `tof_ok`, `n_tof`, `fluxo[2]`, `fluxo_ok`, `n_fluxo`, `v_bat` (contadores `n_*` mudam quando há amostra nova) |
| `Comando` | `modo` (`CTBR` · `VELOCIDADE` · `OLHAR` · `YAW_ALVO`), `coletivo`, `taxas[3]` (CTBR), `vx vy vz yaw_taxa` (VELOCIDADE; referencial do RUMO) [v2: + `yaw`, `z_alvo`, `tem_z_alvo`] |
| `Saida` | `motor[4]` (acelerador [0,1]), estimativas `roll pitch psi h vz vx vy x y`, `giro_f[3]`, `u_eixos[3]`, `flags` |

Ordem de um passo: **estimador → (laços externos: `resolver_modo`) → laço de taxa + mistura → saneamento**. A 1.ª chamada
depois de `reiniciar()` calibra o estimador (roll/pitch do acelerómetro, altura do ToF). Modos reservados
caem em CTBR com `kFlagModoReservado`; saída não finita ⇒ motores a 0 + `kFlagFalhaNumerica`. Crescer a
interface = acrescentar campos **ao fim** dos structs e subir `kVersaoInterface` (o `sitl.py` gera as structs
de ctypes **lendo** o `config.hpp`, por isso o layout nunca diverge).

## Regras de firmware (auditadas por `teste_nucleo.py`)
Só `float` (nada de `double`; `-Wdouble-promotion`) · **sem heap** (new/malloc/`std::vector`/`std::string`) ·
**sem exceções/RTTI** · só `<stdint.h>`/`<math.h>` (`sinf cosf atan2f sqrtf`) · sem Arduino no núcleo (hardware
atrás de `hal.hpp`) · estado na instância (`static nucleo::Nucleo g;` → `.bss`, 2 940 B com a interface 2 [324 B na v1], sem construtor estático).
Compila em C++11/14/17/20 (o core Arduino mbed usa `gnu++14`) com g++ e clang++ e `-Wall -Wextra
-Wdouble-promotion -Werror`; o teste audita o texto (sem `double`, new, malloc, `std::`, literais sem `f`…) e o
objeto ARM (`llvm-nm`/`llvm-objdump`).

## Como compilar e usar
```bash
# SITL (host): .so em out/firmware/ (cache por hash das fontes) e voo com a política
uv run --group hover-rl python experiments/09_drone_hover_rl/sitl.py compilar
uv run --group hover-rl python experiments/09_drone_hover_rl/sitl.py voo --segundos 20          # C++ manda (SITL)
uv run --group hover-rl python experiments/09_drone_hover_rl/sitl.py voo --sombra               # Python voa, C++ compara
# Config da planta para o .ino (constexpr nucleo::Config kConfig)
uv run --group hover-rl python experiments/09_drone_hover_rl/sitl.py config --header minha_config.hpp
# cross-compile (Cortex-M4: Nano 33 BLE · Cortex-M7: H747/Portenta/Nicla/GIGA)
clang++ --target=thumbv7em-none-eabihf -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -ffreestanding -fno-exceptions -fno-rtti \
  -Os -std=c++17 -Wall -Wextra -Wdouble-promotion -Werror -I firmware -isystem firmware/cross -c firmware/nucleo/nucleo.cpp
#   (M7: -mcpu=cortex-m7 -mfpu=fpv5-d16)   —  na toolchain real o <math.h> é o do newlib; o cross/math.h não entra.
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_nucleo.py [--rapido]
```
No Arduino: copiar `nucleo/` (sem `capi.cpp`) e `hal.hpp` para o sketch, implementar `fw::Hal` e chamar
`fw::ciclo(hal, nuc, sens, cmd, t_ant)` a 500 Hz; `nuc.iniciar(kConfig); nuc.reiniciar(); nuc.armar(true);` ao armar.
Laços externos: ligados em `resolver_modo()` (`nucleo.cpp`) na atividade B (VELOCIDADE · YAW_ALVO · OLHAR); no SITL do modo `sitl`
`env.fc.preparar_comando = f(cmd, sens)` continua a deixar pôr `modo`/`vx vy vz yaw_taxa` sem tocar no `env_real.py` (o modo `cascata` usa `env.fc.definir_comando(dict)`).

## Tamanhos medidos da v1 (`clang -Os`, `llvm-size`; só `nucleo.o`, libm à parte) — a v2 está na tabela da atividade B
| alvo | text | data | bss | RAM da instância `Nucleo` |
|---|---|---|---|---|
| Cortex-M4 (`-mcpu=cortex-m4 -mfpu=fpv4-sp-d16`) | 3526 B (96 B de `.ARM.exidx`) | 0 | 0 | 324 B (.bss) |
| Cortex-M7 (`-mcpu=cortex-m7 -mfpu=fpv5-d16`) | 3412 B (96 B de `.ARM.exidx`) | 0 | 0 | 324 B (.bss) |

Símbolos indefinidos do núcleo: só `sinf cosf atan2f sqrtf` (libm) + `__aeabi_memclr4/memcpy4` (runtime). Nada de
`malloc`/`new`/`__cxa_*`/typeinfo/vtables/`atexit`, nenhuma instrução `.f64` nem `__aeabi_d*`. Sem
`-ffreestanding` (como no Arduino/gcc) o `sqrtf` vira `vsqrt.f32` inline (M4 3448 B · M7 3350 B).

## Ressalvas
- O cross-check usa **clang + `cross/math.h`** (sem sysroot ARM aqui): prova flags, símbolos e tamanho, **não** o
  link com a libm real nem o tempo por passo (sem hardware/simulador ARM). ≈ 9 chamadas de libm por passo
  (3 `sinf`, 3 `cosf`, 2 `atan2f`, 1 `sqrtf`).
- No laço de 500 Hz do firmware o estimador processa a leitura mais recente **no início** do passo (o Python
  processava-a no fim do anterior): mesma sequência de leituras, mas a política vê as estimativas com 1 amostra
  (2 ms) de atraso — é o que um FC real faz.
- float32 tem um piso de quantização no filtro complementar (≈ 6e-5·|θ| rad: 1,8e-5 rad a 0,3 rad, ≈ 9e-5 rad
  perto de 90°) — desprezável para voo, mas é a razão das tolerâncias do teste.

---

# Atividade B — a CASCATA clássica, o estimador clássico e o OLHAR no núcleo C++ (interface 2) + SITL fechado + prova no alvo

Decisão do dono (2026-10-12): estabilização, rotação (yaw livre) e movimentação são algoritmos CLÁSSICOS e correm num Arduino; a IA só onde a
medição o exigir. A B0 (`../controlo_classico.py`) mediu a cascata em Python float64; a atividade C deu o detetor/IBVS em C++; **esta atividade
junta tudo no núcleo** (`float32`, sem heap/exceções/STL, só `<stdint.h>`/`<math.h>`), **fecha o laço com o MuJoCo** e **prova que o mesmo código
corre no Cortex-M4/M7**. Fase 1: SEM VENTO. Algoritmos da literatura REIMPLEMENTADOS (PX4 é BSD-3 mas nada foi copiado; ArduPilot/Betaflight/
Crazyflie/MultiWii são GPLv3 e não foram lidos ao nível do código): fontes nos cabeçalhos (`cascata.hpp`: PX4 Controller Diagrams, ArduPilot
dev docs, Brescianini & D'Andrea 2018, Faessler et al. 2018, Åström & Murray 2008; `estimador_classico.hpp`: Mahony et al. 2008).

```
firmware/nucleo/
  cascata.hpp             Cascata: posição P(√) → velocidade PI+FF → inclinação+empuxo ÷cosφcosθ → atitude (prioridade de inclinação) → taxas   [port de CascataClassica]
  estimador_classico.hpp  EstimadorClassico: calibração do giroscópio NO CHÃO + portão do acelerómetro + altura de 3.ª ordem               [port do EstimadorClassico]
  config.hpp              interface 2 (versão 2): ConfigCascata · ConfigEstimadorClassico · ReferenciasTaxa · +campos em Config/Sensores/Comando/Saida
  nucleo.hpp/.cpp         resolver_modo(): CTBR · VELOCIDADE · YAW_ALVO · OLHAR; planear() + atuar(); compensação de tensão; decimação 50/500 Hz
  capi.cpp                (SITL) + cascata_*/estcl_*: a cascata e o estimador clássico testáveis SOZINHOS (golden vectors)
firmware/cross/verifica_nucleo.cpp   a cadeia frame → detetor → Camera → Nucleo(OLHAR) → motores, só para compilar/medir em ARM
firmware/cross/qemu/     o harness bare-metal: arranque.S · mps2.ld · rt_minimo.cpp · libm_minima.cpp (sinf/cosf/atan2f próprios) · driver_replay.cpp · shim/math.h
firmware/teste/estresse_cascata.cpp   estresse ASan+UBSan da interface 2
../sitl.py               modo `cascata` (DroneRealEnvNucleo) · ../sitl_camera.py   frames mono QVGA renderizados (EGL) + detetor C++ + latência
../avaliar_nucleo.py     o protocolo da B0 com o C++ (C++ vs Python vs RL) · ../qemu_alvo.py   QEMU M4/M7 bit a bit, traço de instruções, ciclos
../teste_cascata_nucleo.py   a prova: 66 checagens (11 mutações da fonte C++ apanhadas, 71 s) (+ `teste_nucleo.py` 97/97 e `teste_visao.py` 111/111 continuam verdes)
```

## Interface 2 (`kVersaoInterface = 2`; acrescentada AO FIM dos structs; o caminho CTBR não mudou)

| struct | acrescentado |
|---|---|
| `Config` | `estimador_classico` + `ConfigEstimadorClassico est_cl` · `usa_cascata` + `ConfigCascata cascata` (55 campos = `GanhosCascata` + a decimação + 7 literais) · `usa_visao` + `visao::ConfigSeguidor seguidor` · compensação de tensão (`upv_k`, `n_esc`, `esc_d[16]`, `esc_u[16]`, `v_bat_valida_min`) |
| `Sensores` | `t_us` (relógio do MCU; `fw::ciclo` preenche-o) · `visao::Camera camera{valido,u,v,raio,n,t}` |
| `Comando` | `yaw` (rumo absoluto), `z_alvo` + `tem_z_alvo` (DESCOLAR); `Modo` ganhou `YAW_ALVO = 3` (`CTBR 0 · VELOCIDADE 1 · OLHAR 2` não mudaram) |
| `Saida` | `coletivo` (T/(m·g)), `acelerador`, `taxas_ref[3]`, `v_ref[3]` + `yaw_taxa_ref` (a velocidade EFETIVA que a cascata recebeu: o comando ou o IBVS), `visao::SaidaSeguidor seguidor` (estado A_SEGUIR/EM_FALTA/PERDIDO/REAQUISICAO…), diagnóstico da cascata (`a_des n_des e_tilt gama v_h v_o v_sp_h p_sp z_sp psi_sp r_ref i_vel i_z`) e flags novos (`kFlagSatInclinacao/SatYawTaxa/SatYawAcel/SatColetivo/SatTaxaRP/Calibrando/FalhaCascata`) |

O `sitl.py` gera as structs de ctypes LENDO os cabeçalhos (agora com structs ANINHADAS: `Camera`, `ConfigSeguidor`, `SaidaSeguidor`; o parser continua estrito —
um `double` ou um tipo desconhecido levanta erro). **Com `estimador_classico = 0` e `usa_cascata = 0` (a Config que `config_de_hardware(hw, model, dt)` dá) o núcleo
comporta-se exatamente como na v1** (VELOCIDADE/OLHAR caem em CTBR com `kFlagModoReservado`): `teste_nucleo.py` continua 97/97 sem ter sido editado.

## Como funciona

- **Modos** (`resolver_modo`): `CTBR` (v1) · `VELOCIDADE` — `vx vy vz` no REFERENCIAL DO RUMO (frente/esquerda/cima) + `yaw_taxa`; **v = 0 SEGURA a posição** (como o modo Position do PX4) ·
  `YAW_ALVO` — igual com o rumo absoluto `yaw` · `OLHAR` — `Sensores::camera` → `Seguidor` (IBVS, atividade C) → `vx, vz, yaw_taxa` → a mesma cascata (o IBVS reinicia ao ENTRAR em OLHAR).
- **Ordem do passo** (500 Hz): estimador → `resolver_modo` (a cascata decide 1× por `decimacao = 10` passos ⇒ 50 Hz, e as referências SEGURAM entre decisões) → laço de taxa + mistura +
  airmode → saneamento. `passo()` = `atuar(planear())`; a divisão existe para o SITL pôr entre os dois o atraso do comando da planta (o RPi→FC: 8 ms) sem tocar no firmware.
- **Calibração no chão** (estimador clássico): `calibrar_chao(true)` … 500 × `passo()` parado (motores em idle) … `calibrar_chao(false)` (viés do giroscópio, atitude e altura iniciais da média) →
  `travar_referencias(true, z_alvo)` (trava x, y, ψ e DESCOLA até `z_alvo`, altura do sensor de baixo).
- **Compensação de tensão da bateria**: o acelerador é `u = u_pair(V)·√(T/(m·g))` com `u_pair(V) = ESC⁻¹(K/V)` (a curva do ESC de 8 nós e o K do ciclo de pairagem vão na Config; ≡
  `DroneRealEnv.acelerador_pairagem` a 1e-7 de 14 a 26 V).
- **Config gerada, nunca à mão**: `sitl.config_de_hardware(hw, model, dt, env=…, estimador_classico=True, camera=…)` → `ganhos_de_hardware(env)` (planta → ganhos e limites; o teto de yaw
  0,508 rad/s e a aceleração 0,529 rad/s² são os IDENTIFICADOS no simulador) → `constexpr nucleo::Config kConfig` (`sitl.py config --cascata --header X.hpp`, 704 B, compila para M4). O
  teste audita que `cascata.hpp`/`estimador_classico.hpp` NÃO têm constantes de projeto escritas à mão (só 0, 1, 2, 3, 0,5 e guardas 1e-3/1e-6/1e-9) e que cada `gn.<campo>` do protótipo existe na Config.

## SITL fechado com o MuJoCo (`sitl.py`, modo `cascata`)

O C++ manda nos motores e vê SÓ os sensores medidos (IMU, ToF, fluxo, INA226 + a câmara): `DroneRealEnvNucleo(modo_nucleo="cascata")` troca o FC e o estimador por adaptadores e mantém o
`DroneRealEnv.step` (10 passos de física por decisão, planos WASDQE, DR…). A planta é a MESMA da B0 (build `endurance_15pol_p50b`, 2183 g, sem vento) e as sementes são as de avaliação
(5000…5011; as de calibração 9000… não entram). **Câmara**: frames mono QVGA 320×240 RENDERIZADOS com EGL a 30 Hz (a cena real do lab: câmara `fpv` à frente, esfera-marcador branca emissiva),
luma BT.601, detetor C++ (atividade C) e uma fila com a LATÊNCIA do caminho — 116 ms (Pi) ou 21 ms (DCMI do build `endurance_15pol_arduino`); `Camera.t` é o instante da captura.

```bash
uv run --group hover-rl python experiments/09_drone_hover_rl/sitl.py cascata --segundos 20             # voa a cascata C++ com o perfil WASDQE
uv run --group hover-rl python experiments/09_drone_hover_rl/sitl.py config --cascata --header k.hpp   # a Config completa para o .ino
uv run --group hover-rl python experiments/09_drone_hover_rl/avaliar_nucleo.py [--rapido|--so-olhar]   # ~7 min (20 processos) → out/nucleo/avaliacao.json
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_cascata_nucleo.py [--rapido]        # a prova (66 checagens, ~70 s)
uv run --group hover-rl python experiments/09_drone_hover_rl/qemu_alvo.py auto-teste                   # host ≡ QEMU M4 ≡ QEMU M7 num voo gravado
```

## Equivalência C++ ≡ Python (golden vectors e malha fechada)

| o quê | resultado MEDIDO |
|---|---|
| cascata, voo GRAVADO do protótipo (3000 decisões = 60 s: hover, W, A, Q/E, degrau de rumo 90°, taxa de yaw ACIMA do teto, arco, diagonal; 450 decisões com o yaw saturado) | \|Δ\| máx: coletivo **3,8e-5** · p 3,3e-5 · q 3,3e-5 · r **5,4e-5** (critério ≲ 1e-4); p99 5,3e-5 |
| a mesma com outra semente e com DR (ganhos DESSE sorteio) | 5,4e-5 / 3,5e-5 |
| cascata, 4000 decisões SINTÉTICAS violentas (inclinações ±45°, erros de velocidade ±4 m/s, vz ±4 m/s; saturam a inclinação 931×, as taxas p/q 3122×, o coletivo 1726×, o yaw 3288×) | \|Δ\| máx 1,1e-5 (rearmando as duas cascatas a cada 50 decisões: o teste «coletivo ≥ máx − 1e-9» é inoperante abaixo de 1,2e-7 em float32 e um ramo que vira deixa UM incremento de diferença no integrador) |
| estimador clássico, 30 000 passos de 500 Hz (calibração no chão; portão do acelerómetro ativo em 8825 passos) | roll 2e-7 · pitch 2e-7 · ψ 4e-6 · h 1e-6 · v_z 1e-5 · v_x,v_y 2e-7 · x,y 2e-5 |
| `passo()` ≡ `planear()`+`atuar()` | 600 passos BIT A BIT iguais na `Saida` inteira |
| malha fechada (12 sementes, sem vento, sem DR): C++ vs Python vivo | hover ‖xy‖ −0,1 % (por semente: \|Δ\| médio 0,2 %, máx 0,8 %) · seguimento ‖xy−p_ref‖ −0,1 % · degrau sobressinal 0,0 % · yaw 90° 0,0 % |

O Python vivo reproduz os números PUBLICADOS da B0 (`out/classico/avaliacao.json`) a todos os dígitos mostrados no nominal e no DR de hover. Duas honestidades: **(i)** no DR o C++ usa os ganhos da planta
NOMINAL (o firmware não conhece o sorteio) enquanto o Python da B0 re-deriva-os por episódio (`python_nominal` é a comparação limpa: idêntica ao C++ nas 5 métricas de hover); **(ii)** as médias da B0 só
contam as sementes em que NENHUMA variante caiu (no DR/seguimento a RL cai na 5007), por isso as colunas aqui excluem também essa semente.

**Tabela — SEM domain randomization, 12 sementes (5000…5011), sem vento: C++ vs Python vivo vs Python publicado (B0) vs RL (B0)**

| hover 30 s | nucleo_cpp | python_vivo | python_b0 | rl_b0 |
|---|---|---|---|---|
| ‖xy‖ RMS (cm) | 3,9±0,8 | 3,9±0,8 | 3,9±0,8 | 13,0±5,5 |
| ‖xy‖ máx. (cm) | 7,0±1,3 | 7,1±1,3 | 7,1±1,3 | 17,5±6,9 |
| \|Δz\| RMS (cm) | 0,6±0,1 | 0,6±0,1 | 0,6±0,1 | 2,0±1,0 |
| roll RMS (°) | 0,08±0,01 | 0,08±0,01 | 0,08±0,01 | 0,31±0,02 |
| pitch RMS (°) | 0,08±0,01 | 0,08±0,01 | 0,08±0,01 | 0,50±0,04 |
| deriva de rumo (°) | 0,8±0,5 | 0,8±0,5 | 0,8±0,5 | 2,6±2,3 |
| RMS Δu / 2 ms | 0,0780±0,0005 | 0,0780±0,0005 | 0,0780±0,0005 | 0,0787±0,0004 |
| potência (W) | 214,0±0,6 | 214,0±0,6 | 214,0±0,6 | 215,5±0,5 |

| seguimento | nucleo_cpp | python_vivo | python_b0 | rl_b0 |
|---|---|---|---|---|
| ‖v−v_ref‖ RMS (m/s) | 0,357±0,093 | 0,357±0,093 | 0,357±0,093 | 0,368±0,068 |
| ‖xy−p_ref‖ RMS (m) | 0,297±0,127 | 0,297±0,127 | 0,297±0,127 | 0,235±0,078 |
| \|z−z_ref\| RMS (m) | 0,036±0,029 | 0,036±0,029 | 0,036±0,029 | 0,042±0,020 |
| ‖xy−p_ref‖ 2.ª metade (m) | 0,263±0,123 | 0,263±0,122 | 0,263±0,122 | 0,213±0,089 |

| degrau frente | nucleo_cpp | python_vivo | python_b0 | rl_b0 |
|---|---|---|---|---|
| subida 10–90 % (s) | 0,35±0,01 | 0,35±0,01 | 0,35±0,01 | 0,36±0,02 |
| sobressinal (%) | 9,4±2,1 | 9,4±2,1 | 9,4±2,1 | 18,0±2,0 |
| assentamento 2 % (s) | 5,26±1,18 (6/12) | 5,27±1,18 (6/12) | 5,27±1,18 (6/12) | 7,41±0,61 (8/12) |
| assentamento 5 % (s) | 3,42±2,17 (11/12) | 3,42±2,18 (11/12) | 3,42±2,18 (11/12) | 4,39±1,94 |
| erro de regime (m/s) | -0,025±0,033 | -0,025±0,033 | -0,025±0,033 | -0,007±0,009 |

| degrau lateral | nucleo_cpp | python_vivo | python_b0 | rl_b0 |
|---|---|---|---|---|
| subida 10–90 % (s) | 0,35±0,01 | 0,35±0,01 | 0,35±0,01 | 0,34±0,02 |
| sobressinal (%) | 7,1±1,1 | 7,1±1,1 | 7,1±1,1 | 33,4±2,0 |
| assentamento 2 % (s) | 7,16±0,00 (1/12) | 7,14±0,00 (1/12) | 7,14±0,00 (1/12) | 6,88±1,10 (9/12) |
| assentamento 5 % (s) | 1,85±1,68 (7/12) | 1,17±0,27 (6/12) | 1,17±0,27 (6/12) | 3,05±1,66 |
| erro de regime (m/s) | -0,046±0,014 | -0,046±0,014 | -0,046±0,014 | 0,008±0,007 |


**Tabela — COM domain randomization (peças/bateria/sensores sorteados): o C++ (ganhos nominais) vs `python_nominal` (os mesmos ganhos) vs o Python da B0 e a RL**

| hover 30 s | nucleo_cpp | python_vivo | python_nominal | python_b0 | rl_b0 |
|---|---|---|---|---|---|
| ‖xy‖ RMS (cm) | 5,8±2,0 | 5,8±2,0 | 5,8±2,0 | 5,8±2,0 | 18,7±9,5 |
| ‖xy‖ máx. (cm) | 9,7±2,7 | 9,7±2,7 | 9,7±2,7 | 9,7±2,7 | 25,8±12,8 |
| \|Δz\| RMS (cm) | 0,6±0,1 | 0,6±0,1 | 0,6±0,1 | 0,6±0,1 | 2,1±0,9 |
| roll RMS (°) | 0,10±0,02 | 0,10±0,02 | 0,10±0,02 | 0,10±0,02 | 0,39±0,10 |
| pitch RMS (°) | 0,10±0,02 | 0,10±0,02 | 0,10±0,02 | 0,10±0,02 | 0,58±0,08 |
| deriva de rumo (°) | 0,6±0,4 | 0,6±0,4 | 0,6±0,4 | 0,6±0,4 | 3,8±3,5 |
| RMS Δu / 2 ms | 0,0801±0,0040 | 0,0801±0,0040 | 0,0801±0,0040 | 0,0801±0,0040 | 0,0811±0,0040 |
| potência (W) | 211,2±23,0 | 211,2±23,0 | 211,2±23,0 | 211,2±23,0 | 212,8±22,9 |

| seguimento | nucleo_cpp | python_vivo | python_nominal | python_b0 | rl_b0 |
|---|---|---|---|---|---|
| ‖v−v_ref‖ RMS (m/s) | 0,418±0,183 | 0,419±0,182 | 0,418±0,183 | 0,419±0,182 | 0,435±0,210 |
| ‖xy−p_ref‖ RMS (m) | 0,299±0,144 | 0,300±0,146 | 0,299±0,145 | 0,300±0,146 | 0,223±0,061 |
| \|z−z_ref\| RMS (m) | 0,047±0,034 | 0,047±0,034 | 0,047±0,034 | 0,047±0,034 | 0,043±0,022 |
| ‖xy−p_ref‖ 2.ª metade (m) | 0,278±0,153 | 0,280±0,156 | 0,278±0,153 | 0,280±0,156 | 0,204±0,066 |


**Leitura (honesta)**: o C++ **não é pior** que o Python em nenhuma métrica (igual a ≤ 0,3 %; a única diferença visível — o «assentamento a 5 %» do degrau lateral, 7 vs 6 sementes assentam — é uma métrica de LIMIAR: o erro de regime é −4,6 % contra uma banda de 5 %). Face à RL medida pela B0: a cascata ganha no hover (‖xy‖ 3,9 vs 13,0 cm; roll/pitch 4–6× menores) e nos degraus (sobressinal 9 % vs 18 %; lateral 7 % vs 33 %);
a RL é melhor no seguimento xy (0,235 vs 0,297 m) e no erro de regime dos degraus — a decisão «clássico vs RL» fica como na B0: clássico para estabilizar/rodar/mover, RL só onde a medição o exigir.

## OLHAR para o círculo, em malha fechada (frames renderizados + detetor C++ + IBVS + cascata)

**Tabela — OLHAR (3 sementes por linha; câmara mono QVGA 30 Hz renderizada; a verdade do simulador só serve para MEDIR)**

| caminho · trajetória | rumo RMS (°) | rumo máx (°) | \|D−d*\| RMS (m) | elevação RMS (°) | A_SEGUIR (%) | frames válidos (%) | yaw no limite (%) | taxa LOS máx / p95 (rad/s) | v_y de «lateral assist» p95 / máx (m/s) | quedas |
|---|---|---|---|---|---|---|---|---|---|---|
| pi_116ms:circulo:0,3 | 1,01 | 2,46 | 0,093 | 2,09 | 93,1 | 100,0 | 0,0 | 0,21 / 0,20 | 0,000 / 0,000 | 0/3 |
| pi_116ms:circulo:0,5 | 1,47 | 4,29 | 0,164 | 1,90 | 95,0 | 100,0 | 0,0 | 0,39 / 0,36 | 0,000 / 0,000 | 0/3 |
| pi_116ms:circulo:0,6 | 1,97 | 5,98 | 0,225 | 2,24 | 95,3 | 100,0 | 3,5 | 0,52 / 0,45 | 0,000 / 0,023 | 0/3 |
| pi_116ms:circulo:0,7 | 3,04 | 7,48 | 0,231 | 2,01 | 95,1 | 100,0 | 23,3 | 0,56 / 0,52 | 0,016 / 0,054 | 0/3 |
| pi_116ms:circulo:0,8 | 7,22 | 12,59 | 0,407 | 1,59 | 96,1 | 100,0 | 43,9 | 0,62 / 0,54 | 0,044 / 0,120 | 0/3 |
| pi_116ms:oito:0,3 | 0,84 | 1,68 | 0,187 | 1,90 | 94,9 | 100,0 | 0,0 | 0,21 / 0,19 | 0,000 / 0,000 | 0/3 |
| pi_116ms:oito:0,5 | 1,58 | 3,15 | 0,260 | 2,31 | 95,5 | 100,0 | 0,2 | 0,44 / 0,40 | 0,000 / 0,000 | 0/3 |
| pi_116ms:oito:0,8 | 54,19 | 125,04 | 0,650 | 2,73 | 63,2 | 77,1 | 5,9 | 1,72 / 1,19 | 0,349 / 0,503 | 0/3 |
| arduino_21ms:circulo:0,3 | 0,44 | 0,69 | 0,098 | 0,46 | 100,0 | 100,0 | 0,0 | 0,20 / 0,20 | 0,000 / 0,000 | 0/3 |
| arduino_21ms:circulo:0,5 | 0,49 | 1,11 | 0,176 | 0,48 | 99,9 | 100,0 | 0,0 | 0,35 / 0,34 | 0,000 / 0,000 | 0/3 |
| arduino_21ms:circulo:0,6 | 0,63 | 1,90 | 0,215 | 0,58 | 99,9 | 100,0 | 0,0 | 0,44 / 0,41 | 0,000 / 0,000 | 0/3 |
| arduino_21ms:circulo:0,7 | 0,91 | 2,22 | 0,190 | 0,65 | 100,0 | 100,0 | 0,9 | 0,52 / 0,48 | 0,000 / 0,017 | 0/3 |
| arduino_21ms:circulo:0,8 | 5,23 | 7,48 | 0,236 | 0,50 | 99,7 | 100,0 | 83,8 | 0,57 / 0,56 | 0,034 / 0,048 | 0/3 |
| arduino_21ms:oito:0,3 | 0,87 | 1,44 | 0,212 | 0,59 | 100,0 | 100,0 | 0,0 | 0,23 / 0,22 | 0,000 / 0,000 | 0/3 |
| arduino_21ms:oito:0,5 | 2,05 | 3,76 | 0,269 | 0,61 | 100,0 | 100,0 | 0,0 | 0,44 / 0,40 | 0,000 / 0,000 | 0/3 |
| arduino_21ms:oito:0,8 | 5,20 | 15,19 | 0,493 | 2,17 | 98,3 | 100,0 | 7,7 | 0,79 / 0,58 | 0,049 / 0,201 | 0/3 |
| sens_yaw_0,8:circulo:0,6 | 2,70 | 6,96 | 0,201 | 3,27 | 93,4 | 100,0 | 0,0 | 0,47 / 0,43 | 0,000 / 0,000 | 0/3 |
| sens_yaw_0,8:circulo:0,8 | 5,41 | 16,89 | 0,308 | 8,38 | 90,3 | 98,6 | 7,0 | 0,93 / 0,76 | 0,026 / 0,151 | 0/3 |
| sens_yaw_0,8:oito:0,5 | 1,88 | 3,65 | 0,243 | 2,29 | 95,2 | 100,0 | 0,0 | 0,44 / 0,40 | 0,000 / 0,000 | 0/3 |
| sens_yaw_0,8:oito:0,8 | 10,49 | 34,99 | 0,723 | 10,87 | 86,2 | 95,8 | 3,8 | 1,03 / 0,70 | 0,012 / 0,342 | 0/3 |

- **Medido, não afinado**: os ganhos do IBVS são os de `config_padrao` da atividade C, com `yaw_max`/`yaw_acel_max`/`vx_max`/`vz_max` IGUAIS aos da cascata (o IBVS não pode pedir mais yaw do que a planta tem).
  Sementes 7000–7002 (não são as de avaliação do protocolo; nada foi afinado nelas). O build Arduino teve o seu `u/r` de yaw identificado (0,4306; p50b 0,4379). 3 sementes por linha: números de ordem de grandeza, não estatística fina.
- **Autoridade de yaw (o achado-chave da atividade C, agora MEDIDO no simulador completo)**: com o teto de 0,508 rad/s e 0,529 rad/s², o círculo a ≤ 0,5 m/s segue-se a 0,4–1,5° RMS; a 0,6–0,7 m/s o yaw começa a bater no
  teto (3,5–23 % do tempo no caminho Pi de 116 ms; ≤ 1 % no DCMI de 21 ms, que antecipa melhor) e o erro sobe para 2–3° (0,6–0,9° no DCMI); a 0,8 m/s o yaw fica no teto durante 44 % (116 ms) e 84 % (21 ms) do tempo e o rumo RMS salta para 7,2° / 5,2°,
  **com o alvo sempre no campo (100 % de frames válidos)** — é a autoridade de yaw, não a visão nem a latência. O «oito» a 0,8 m/s perde o alvo no caminho Pi (54° RMS, 63 % em A_SEGUIR; taxa de linha de vista verdadeira até 1,7 rad/s, 3,4× o teto).
  Subir o teto para 0,8 rad/s e 1,5 rad/s² (linhas `sens_yaw_0.8`, HIPOTÉTICO: a mistura satura acima de 0,51) não resolve: a altura oscila (elevação RMS 8–11° em vez de 1,6–2°) e o rumo continua a 5,4° (círculo 0,8) / 10,5° (oito 0,8).
- **Opção «lateral assist» (SUGERIDA, NÃO implementada)**: quando o yaw satura, pôr `v_y ∝ velocidade tangencial do alvo` — `v_y ≈ D·(ω_los − ω_teto)` com `ω_los` a taxa de bearing que o `Seguidor` já estima (`taxa_bearing`) — em vez de deixar o erro de rumo
  crescer. A última coluna da tabela MEDE o que isso teria de fornecer (o excesso da taxa de linha de vista VERDADEIRA sobre o teto, vezes a distância): no círculo a 0,8 m/s só **p95 0,044 m/s, máx 0,12 m/s** (Pi) e 0,034 / 0,048 (DCMI) — 4–12 % do `vel_xy_max` = 1 m/s da cascata;
  no oito a 0,8 m/s 0,35 / 0,50 m/s (Pi). Ou seja, uma pequena velocidade lateral bastaria para o círculo; o IBVS hoje manda `vy = 0` e a cascata já aceita `vy` (referencial do rumo). A validar em simulação antes de adotar.
- **Achado de integração (por resolver)**: com o ruído REAL da atitude estimada pelo núcleo (≈ 0,4° lento, viés de pitch de ~2° no sorteio de sensores) o gate de inovação do filtro do alvo recusa 3 medidas seguidas cerca de 1× por segundo e o filtro REINICIA
  (`A_SEGUIR → REAQUISICAO → A_SEGUIR`, ≈ 5 % do tempo; por isso «A_SEGUIR» ≈ 95 %): o σ_px = 0,3 px do `config_padrao` foi afinado com ruído sintético (atitude 0,15°). Varrendo σ_px nas sementes de CALIBRAÇÃO (9000–9002; círculo 0,5 m/s): 0,3 → A_SEGUIR 95,0 %, rumo 1,40°, elevação 2,2°;
  0,7 → 95,1 %, 1,04°, 4,8°; 1,4 → 96,8 %, 1,11°, 5,8°; 2,5 → 98,7 %, 1,34°, 6,3° — menos reinícios à custa da elevação (o laço vertical fica lento). Fica por refinar (ruído colorido da atitude no KF; translação própria durante o atraso). Não foi mexido.
- **Teste de perda/reaquisição** (o alvo some atrás do drone 2,5 s): `PERDIDO` ≤ 1 s depois de sumir, de volta a `A_SEGUIR` a t = 12,7 s e o drone não cai.

## Prova no ALVO (Cortex-M4 / Cortex-M7) — o que é MEDIDO e o que é ESTIMADO

**Compilação cruzada** (`clang --target=thumbv7em-none-eabihf -ffreestanding -fno-exceptions -fno-rtti -Os -Wall -Wextra -Wdouble-promotion -Werror`; `llvm-size`/`llvm-nm`/`llvm-objdump`) — MEDIDO:

| alvo | `nucleo.o` text (-Os / -O2) | data · bss | RAM da instância `Nucleo` | cadeia completa (núcleo + detetor, ligados) |
|---|---|---|---|---|
| Cortex-M4 (`-mcpu=cortex-m4 -mfpu=fpv4-sp-d16`) | 25 718 B / 31 356 B | 0 · 0 | **2 940 B** (.bss; .data 0 B) | text 29 258 B |
| Cortex-M7 (`-mcpu=cortex-m7 -mfpu=fpv5-d16`) | 24 582 B / 29 664 B | 0 · 0 | **2 940 B** | text 28 172 B |

Símbolos indefinidos (núcleo e cadeia completa): SÓ `sinf cosf atan2f sqrtf` + `__aeabi_memclr4/memcpy4`; nenhum `malloc`/`new`/`__cxa_*`/typeinfo/vtables/`atexit`, 0 instruções `.f64`, sem `.init_array`/`.eh_frame`.
(Frame mono 320×240 = 76 800 B + `Detetor` 5 712 B ficam fora da instância do núcleo.)

**Execução em QEMU** (`qemu_alvo.py`; `mps2-an386` = M4, `mps2-an500` = M7; imagem bare-metal SEM libc/libm — arranque, mapa de memória, semihosting, runtime mínimo e `libm_minima.cpp`: sinf/cosf/atan2f
próprios por redução de Cody–Waite + polinómios de Chebyshev, **≤ 2 ULP vs glibc** em 4 M de pontos; `-ffp-contract=off`, sem `-ffast-math`) — MEDIDO:
- o MESMO código dá as MESMAS saídas **BIT A BIT** no host (libm própria), no Cortex-M4 e no Cortex-M7: voo SITL gravado de 7500 passos de 500 Hz (calibração no chão, VELOCIDADE, YAW_ALVO, taxa de yaw saturada) + 24 deteções
  sintéticas do detetor (2 163 072 B de saída, crc32 `911f5443`), e um voo em OLHAR (câmara renderizada + IBVS, 5500 passos). QEMU: 0,3–0,4 s por corrida.
- o comparador TEM DENTES: a mesma imagem M7 com `-ffp-contract=fast` (FMA) já NÃO é bit-exact (26 campos divergem); com a glibc em vez da libm própria os motores diferem 3,6e-7 (só libm).
- limite: o QEMU prova a EXATIDÃO e conta instruções (`-d exec`, uma instrução por bloco, filtrado ao núcleo/libm); **não mede tempo** (o `DWT->CYCCNT` não existe no QEMU).

**Custo por passo** — INSTRUÇÕES MEDIDAS (traço do QEMU, instruction-accurate, `-O2`, libm própria) · CICLOS ESTIMADOS (`llvm-mca` sobre a sequência EXATA executada; caches/flash ideais; NÃO medido em hardware):

| | instruções | ciclos (llvm-mca) | µs | % do período de 2 ms | chamadas de libm |
|---|---|---|---|---|---|
| M7 — passo normal de 500 Hz (estimador + taxa + mistura) | **1438** | 2060 | **4,3 µs @ 480 MHz** | 0,21 % | 3 sinf · 3 cosf · 2 atan2f |
| M7 — passo com DECISÃO da cascata (50 Hz) | **3016** | 4851 | **10,1 µs @ 480 MHz** | 0,51 % | 7 · 7 · 3 |
| M4 — passo normal | 1620 | 1860 (tabela ARM M4F: 2742) | 7,8 µs (11,4) @ 240 MHz | 0,39 % (0,57 %) | |
| M4 — passo com decisão | 3460 | 4198 (tabela: 5856) | 17,5 µs (24,4) @ 240 MHz | 0,87 % (1,22 %) | |

Leitura: o ciclo completo (estimador + cascata + taxa + mistura) ocupa ≈ 0,2–0,5 % de 2 ms no M7 e < 1,3 % no M4 — sobra margem de ≥ 80× (a pesquisa pedia ≥ 2×). **Ressalvas honestas**: ciclos são estimativa estática
(o modelo do M4 do LLVM e a tabela da ARM dão 1860 vs 2742; só um DWT numa placa fecha); a libm do newlib do Arduino custa mais por chamada do que a minha (≈ 8–17 chamadas por passo ⇒ +1 000–2 000 ciclos se
cada uma gastar ~150) — ainda < 1,5 % no M7; flash/SRAM/caches e a contenção com a câmara/DMA não estão modeladas; o harness não corre o `.ino` real nem a HAL.

## Por fazer / limites

- Nenhum hardware: tempo real, jitter, caches, DCMI+voo no mesmo MCU (a divisão M7 visão / M4 voo é inferência) por medir com DWT numa Portenta.
- O IBVS não compensa a translação do drone durante o atraso nem a parallax da câmara (11,5 cm à frente do CM), e o filtro do alvo reinicia ~1×/s com o ruído real da atitude (acima). A procura é só em yaw.
- Sem vento (fase 1); o estimador de altitude só vale até ≈ 4 m (fluxo+ToF).
- O C++ dispensa a RL nesta planta sem vento: a comparação com RL em vento/rajadas (onde a RL foi treinada) continua por medir.

---

# Atividade C — «olhar para o círculo» em clássico e em C++ de firmware (visão → alvo → IBVS)

Decisão do dono (2026-10-12): estabilização/rotação/movimento são algoritmos clássicos num Arduino e a IA só entra onde a
medição o exigir. Esta secção é a parte VISUAL: detetor de círculo sobre um frame **monocromático** (a Portenta Vision
Shield é mono de 8 bit: HM0360 640×480 / HM01B0 320×320), estimador do alvo com compensação do atraso da câmara, lei de
servo visual (IBVS) que gera comandos para a cascata de voo, e máquina de estados de perda. Tudo C++17 `float32`, sem
heap, só `sinf cosf atan2f sqrtf` (as MESMAS regras do núcleo; auditadas por `teste_visao.py` §0), em SITL e a compilar
para Cortex-M4/M7. Algoritmos da literatura (Kalman/α-β de Bar-Shalom, IBVS de Chaumette & Hutchinson, atraso por histórico
de atitude); **código próprio**, nenhuma linha de ArduPilot/Betaflight (GPLv3).

## O que o núcleo de voo terá de aceitar (o contrato)

`nucleo/visao_tipos.hpp` (namespace `nucleo::visao`, não colide com `nucleo::Comando/Sensores/Saida`). Os PODs são lidos
pelo `sitl_visao.py` para gerar as structs de ctypes (uma só fonte da verdade, `sizeof` conferido).

```cpp
struct Camera {            // ENTRADA — o que o detetor entrega ao núcleo, por frame
    int32_t valido;        // 1 = deteção válida; 0 = nada/rejeitada (u, v, raio ignorados)
    float   u, v;          // px, convenção do ÍNDICE (centro do píxel (0,0) = (0,0); eixo óptico em ((W−1)/2, (H−1)/2)); + direita / + baixo
    float   raio;          // px — raio equivalente √(área/π); distância = R_alvo·f/raio
    int32_t n;             // contador de frames: muda a cada frame NOVO (válido ou não)
    uint32_t t;            // µs — instante da CAPTURA no relógio do MCU (= fw::Hal::micros()); só diferenças (volta a 71 min)
};
struct ComandoVoo {        // SAÍDA — o que a cascata de voo (atividade B0) recebe
    float vx, vy, vz;      // m/s NO REFERENCIAL DO RUMO (só yaw): frente / esquerda / cima. |v_xy| ≤ 1, |v_z| ≤ 0,7; o IBVS manda vy = 0
    float yaw_taxa;        // rad/s, + anti-horário visto de cima (|·| ≤ yaw_max = 0,8, slew yaw_acel_max = 1,5 rad/s²)
};
struct Atitude { float roll, pitch, psi, vx, vy, vz; };   // ENTRADA — nucleo::Saida AGORA (ZYX do estimador; pitch > 0 = nariz para baixo)
```

- **Ligação ao núcleo** (FEITA na atividade B: `Sensores::camera`, modo `OLHAR` em `resolver_modo`; o texto abaixo é o contrato original): `nucleo::Comando` traz
  `vx vy vz yaw_taxa`. ⚠ o comentário de `config.hpp` diz «m/s, mundo» para `VELOCIDADE`; o IBVS emite no
  **referencial do rumo** — o modo `OLHAR` tem de o tratar assim (ou rodar por ψ). O `Camera` entra no `Sensores` como 6
  campos planos no fim (`cam_valido cam_u cam_v cam_raio cam_n cam_t`; o parser do `sitl.py` só aceita escalares) e sobe
  `kVersaoInterface`. Em `OLHAR`, a 50–500 Hz (o histórico de atitude decima a ≥ 4 ms; testado a 100 e a 500 Hz): `s = seguidor.passo(micros(), Atitude{…}, camera)` → `Comando{modo, s.vx, s.vy, s.vz, s.yaw_taxa}`.
- **Quem corre onde** (inferência a validar — nenhuma fonte prova visão+voo no mesmo MCU): M7 = frame → `Detetor::detetar` → `camera_de(d, n, t)`
  (25–60 Hz); M4 = `Seguidor::passo` + laços de velocidade/yaw. `t` é o instante da CAPTURA (DCMI VSYNC), não o da chegada.
- **Atraso**: o filtro usa `Camera.t` (qualquer atraso). O contrato do enunciado é 116 ms (pipeline Pi/JPEG); o caminho DCMI do Arduino
  modelado em `lab/camera_rpi.py` é ≈ 21 ms (QVGA60) – 37 ms (QVGA30, omissão da biblioteca Arduino). O teste cobre 21/66/116/166 ms.
- **Janela de busca**: `janela_de_previsao(saida, &params)` dá a janela do próximo frame (±3·raio+12 px à volta do alvo previsto) —
  o detetor passa a custar a janela, não o frame (o alvo real cai dentro em ≥ 99,5 % dos passos do círculo).

## 1. Detetor (`visao.hpp`) — limiar + momentos, O(píxeis), sem Hough

`Detetor::detetar(frame, W, H, limiar, params) → Deteccao{valido, u, v, raio_px, circularidade, area, cheio, motivo, …}`.
1.ª passagem (limiar adaptativo = fundo + 0,5·(máx − fundo); `limiar > 0` = fixo e salta-a): máx **robusto** (máx. de min de
vizinhos: um píxel quente isolado não conta), fundo e ruído σ̂ por uma grelha 8×8 esparsa (1/64 dos píxeis); contraste < max(40, 8·σ̂) ⇒ «sem alvo».
2.ª passagem: «runs» por linha + componentes ligados (8-conectividade) **em streaming** (≤ 48 ativos; um poste que atravessa o
frame não esgota a memória e um distrator já não esconde o alvo). Por componente, em inteiros exatos: n, Σx, Σy, Σx², Σy², Σxy;
centróide **pesado pela intensidade** (w = I − limiar + 1, sub-píxel); circularidade = λ_min/λ_max dos momentos centrais; «cheio» =
r_momentos/r_área; gates de área, bordo (alvo cortado ⇒ M_BORDA), circularidade e cheio; escolhe o blob válido de maior massa.

**Erro de localização medido** (frames RENDERIZADOS no MuJoCo — a cena real do lab, câmara `fpv` à frente do corpo, esfera de 5 cm
branca emissiva, luma BT.601, FoV 55,4° do HM0360; 80 poses entre 1 e 3 m; vs a projeção EXATA do centro):

| resolução | condição | válidos | média (px) | p95 | máx |
|---|---|---|---|---|---|
| 320×240 (f = 229 px) | limpo | 80/80 | 0,085 | 0,198 | 0,322 |
| 320×240 | ruído σ = 6 / 10 níveis | 80/80 | 0,086 / 0,089 | 0,19 | 0,35 |
| 320×240 | desfoque σ = 1 / 2 px | 80/80 | 0,086 / 0,110 | 0,23 / 0,31 | 0,36 |
| 320×240 | vinheta −60 % · ganho ×2 · píxeis quentes/mortos | 80/80 | 0,055 · 0,098 · 0,085 | ≤ 0,2 | ≤ 0,36 |
| 160×120 (f = 114 px) | limpo / ruído σ = 6 | 80/80 | 0,078 / 0,080 | 0,15 | 0,19 |
| 160×120 | desfoque σ = 2 px | 80/80 | 0,114 | 0,37 | 0,55 |

- **Os «0,708 px» do gate do `visao.py` são meio píxel de convenção**, não erro do detetor: a projeção do MuJoCo usa a convenção da
  BORDA, o detetor o ÍNDICE (u_índice = u_borda − 0,5): sem corrigir 0,703 px (= √(0,5²+0,5²)); corrigido 0,085 px. (O tracker RL
  usa `proj["u"]` como «u do detetor»: tem esse viés de 0,5 px — irrelevante a 1080p, não a 160×120.) Contra o centróide da
  SILHUETA exata (o que um detetor de blob pode ver) o erro é 0,046 px: o resto é viés de perspetiva do centro.
- **Raio mínimo detetável** (≥ 95 %): 2,5 px a 320×240 e a 160×120 ⇒ alcance de uma esfera de 5 cm = f·R/r_min ≈ **4,6 m** (QVGA) / **2,3 m**
  (QQVGA); a d* = 1,5 m o raio é 7,6 px / 3,8 px. ⚠ No HM01B0 QQVGA120 (FoV 70,9°, f = 84 px) a 1,5 m são só 2,8 px: no limite — usar QVGA ou um alvo maior.
- **Falsos positivos**: 0 em 80 frames da cena sem esfera, 180 de ruído puro (σ = 4/10/20) e 1 uniforme (o gate de contraste é relativo ao ruído).

**Custo** (frame com alvo r ≈ 9 px a 1,5 m): **host MEDIDO** (mediana de 200 chamadas, x86-64 a vários GHz — só ordem de grandeza) e
**Cortex-M7 ESTIMADO** (`llvm-mca -mcpu=cortex-m7` sobre o objeto cross-compilado `-Os`: 5,5 / 6,5 / 10 ciclos por píxel nos laços
máx / salto / run e 6,0 por amostra da grelha (1 píxel em 8), `novo_run` 378, `fim_de_linha` 177, `avaliar` 656 ciclos por chamada — limite superior; caches e SRAM ideais):

| | host (µs) | M7 `-Os` | M7 `-O2` | % do período a 30 Hz / 25 Hz (`-Os`) |
|---|---|---|---|---|
| QVGA 320×240 (76 800 B) | 52 | **2,05 ms** | 1,73 ms | 6,2 % / 5,1 % |
| QQVGA 160×120 (19 200 B) | 16 | **0,54 ms** | 0,48 ms | 1,6 % / 1,4 % |
| janela 81×81 (seguimento) | 10 | 0,22 ms | 0,21 ms | 0,7 % / 0,5 % |

Margem ×2 recomendada pela pesquisa [S107]: QVGA ≈ 4,1 ms. **Nenhuma fonte prova o fps no Portenta/Nicla** (só fóruns OpenMV e o fabricante
do H7: 40–80 fps a QVGA para algoritmos simples) — o número acima é estimativa estática; `DWT->CYCCNT` na placa fecha. RAM: `sizeof(Detetor)` = 5 712 B
(instância estática) + o frame. O objeto cross-compilado (detetor + seguidor): M7 text 13,3 kB · M4 13,6 kB · bss 7 208 B · data 0.

**Onde o detetor por momentos FALHA (reportado, não corrigido; `teste_visao.py` §4 afirma-o)**
| caso | resultado | proposta |
|---|---|---|
| alvo parcialmente fora do FOV | recusa (M_BORDA): o centróide do disco cortado erra até ~1 px (os mais cortados falham também a circularidade) | o seguidor prevê (EM_FALTA); se for preciso, ajustar o círculo aos arcos visíveis |
| brilho saturado: ganho ×2 ok; **×3 → 49 %** (o chão passa o limiar e funde-se com o alvo sobre ele) | falha parcial | AEC do sensor com janela no alvo (o `Deteccao.vmax/fundo` já dizem o estado de exposição); alvo IR + filtro passa-banda |
| **coluna morta / linha escura que parte o alvo** | 0/80 (duas metades alongadas) | mapa de píxeis defeituosos + interpolação no driver, ou ponte de 1–2 px nos runs |
| barra FUNDIDA com o alvo (mesmo blob) | recusa (em vez de centróide errado) | janela de busca / filtro com previsão |
| dois discos | ganha o de mais massa (a «lâmpada»); com a janela ganha o alvo | seguimento com janela (acima) |
| píxeis quentes isolados (até 1,3 %) | OK; defeitos isolados mortos OK | — |
| alvo magenta em câmara mono | luma 131/255: ainda detetável contra este fundo escuro, mas **só por brilho** | alvo branco/IR |

## 2. Estimador do alvo (`alvo.hpp`) — atraso e rotação própria

O bearing da câmara mistura o movimento do alvo com o do drone (que ROTACIONA). Solução: **histórico de atitude** (64 amostras) → o pixel do
instante da captura converte-se num bearing INERCIAL (azimute α, elevação ε, raio ρ = raio_px/f) com a atitude (φ, θ, ψ) desse instante
(`R = Rz(ψ)Ry(θ)Rx(φ)`, a do estimador de bordo); o filtro corre no TEMPO DA CAPTURA (α-β, KF-CV ou KF-CA por canal, forma de Joseph, gate de
inovação, 3 recusas seguidas reiniciam) e **prevê** para o instante atual: a rotação própria dentro do atraso é EXATA, só o alvo se extrapola.
Dá `taxa_bearing` (feedforward do yaw) e, no KF-CA, a aceleração (avanço de fase). Não compensa a TRANSLAÇÃO própria durante o atraso.

Erro de previsão do **rumo** (RMS, graus) com 116 ms e o drone a rodar ±0,63 rad/s (σ = 0,3 px; erro lento da atitude 0,15°); 2 sementes:
| alvo | α-β | KF-CV | KF-CA | «sem previsão» (desrodado, não extrapolado) | «sem desrodar» |
|---|---|---|---|---|---|
| círculo 0,3 / 0,5 / 0,8 m/s | 0,179 | 0,174 | 0,197 | 1,56 / 2,59 / 4,14 | 3,41 |
| oito 0,3 / 0,5 m/s | 0,183 / 0,231 | 0,179 / 0,234 | 0,197 / 0,204 | 0,50 / 1,11 | 3,41 |
| oito 0,8 m/s | 0,432 | 0,452 | 0,342 | 1,85 | 3,41 |

- O previsor é 2,5–21× melhor que «sem previsão» (o oito lento quase não tem atraso a compensar) e ≥ 7× melhor que «sem desrodar». Varrimento do atraso (KF-CA, círculo 0,8 + oito 0,5): 0,11° → 0,16° → 0,22° →
  0,28° para 21 / 66 / 116 / 166 ms, contra 0,90° → 3,59° sem previsão.
- **α-β vs KF-CA**: com a atitude EXATA o KF-CA ganha 23 % (0,153° vs 0,199°); com a atitude real (erro lento de 0,15°) os três **empatam** (0,331 / 0,330 / 0,347°): o piso é a atitude
  estimada, não o modelo do alvo. O KF-CA compensa em laço fechado (avanço de fase com a aceleração: oito 0,5 m/s 1,84° vs 5,2° do α-β). Ganhos afinados em
  grelha: α-β (0,5; 0,2) · KF-CV q = 0,002 · KF-CA q = 0,01 rad²/s⁵ (σ_px 0,1–0,6 dá o mesmo ótimo).
- Gate de inovação: com 5 % de deteções falsas o erro fica em 0,20° (sem gate: 6,9°). Deriva do rumo (viés do giroscópio 1,1°/s) cancela no erro de rumo.
- Custo no M7 (ESTIMATIVA do pior caso, llvm-mca de 30 funções do grafo de chamadas + libm assumida sinf/cosf 110, atan2f 220, sqrtf 30 ciclos): **≈ 22 µs por passo** (0,22 % do período a 100 Hz).

## 3. Lei IBVS e máquina de estados (`ibvs.hpp`)

```
e_ψ = α_prev − ψ ;  e_ε = ε_prev ;  D = R_alvo·f/raio_px        (tudo previsto AGORA e desrodado de roll/pitch)
yaw_taxa = Kp·e_ψ + I(e_ψ) + Kff·(ω_los + τ_av·α_los)            PI + FEEDFORWARD da taxa de bearing + avanço de fase (a «compensação da própria rotação» está na desrotação)
v_z      = Kz·(D·sen e_ε) + Kffz·v_vert_alvo ;   v_x = Kd·(D − d*) + Kffd·v_radial_alvo  (só avante × max(0, cos e_ψ)) ;   v_y = 0
```
Defaults (`config_padrao`): Kp = 1,0 /s · Ki = 0,1 /s² (integra só com |e_ψ| < 0,1 rad, clamp 0,3 rad/s) · Kff = 1 · τ_av = 0,3 s · yaw_max 0,8 rad/s · slew 1,5 rad/s² ·
Kz = 0,8 · Kffz = 0,5 · Kd = 0,8 · Kffd = 0,4 · v_max 1 / 0,7 m/s · slew 1 m/s² · zonas mortas suaves (0,29° · 2 cm · 3 cm).
**`yaw_max` = 0,8 rad/s, o lag τ_yaw 0,3–0,6 s e o slew de yaw são HIPÓTESES a confirmar quando a B0 publicar a identificação.**

Máquina de estados: `A_SEGUIR → EM_FALTA` (> 100 ms sem deteção aceite: segue a PREVISÃO, v decai a 0) `→ PERDIDO` (> 300 ms: v = 0 e procura lenta de yaw, 0,3 rad/s, para o
ÚLTIMO LADO visto; pára e levanta `kFlagProcuraEsgotada` ao fim de 30 s) `→ REAQUISICAO` (1.ª deteção) `→ A_SEGUIR` só após n_reaq = 3 deteções seguidas (histerese; uma falha volta a PERDIDO).
Medido: PERDIDO a 3,39 s para uma perda a 3,0 s (esperado 3,38), A_SEGUIR a 0,20 s do arranque, confirmação de 80 ms. Limite da procura: só em yaw — um alvo fora do campo VERTICAL não se reencontra.

**Margens de fase** (laço yaw_taxa → rumo = (Kp + Ki/s)·e^{−s(T+Ts/2)}/(s(τs+1)), atraso INTEIRO dentro do laço + ZOH de 20 ms — estrutura pessimista: o previsor/desrotação só ajudam):
| τ_yaw | T = 21 ms (DCMI) | 66 ms | 116 ms (Pi) | 166 ms |
|---|---|---|---|---|
| 0,30 s | 65,7° | 63,2° | 60,4° | 57,6° |
| 0,45 s | 59,0° | 56,6° | **54,0°** (GM 17,3 dB) | 51,3° |
| 0,60 s | 53,4° | 51,1° | 48,6° | **46,1°** (o pior canto) |

⇒ PM ≥ 45° em toda a grelha com Kp = 1,0, Ki = 0,1. O atraso ±50 ms muda a margem só ≈ 5° (ωc ≈ 0,93 rad/s × 100 ms): **o limite é o lag do yaw, não a câmara**. (Kp = 1,2, Ki = 0,1 daria 42,8° no pior canto; por
isso 1,0.) v_z e v_x (Kz = Kd = 0,8, τ_v 0,3–0,7 s): ≥ 55,8°.

**Laço fechado** (planta CINEMÁTICA do `sitl_visao.py`: yaw 2.ª ordem τ 0,45 s, v com lag 0,5 s e aceleração ≤ 2 m/s², inclinação consequência da aceleração; câmara 25 Hz com 116 ms e
σ = 0,3 px; atitude com erro 0,15°; o alvo segue as leis do `env_real.definir_trajetoria_ponto`, raio 1,5 m, o drone DENTRO do círculo; KF-CA + FF + avanço):

| alvo | rumo RMS / máx (°) | \|D−d*\| médio / máx (m) | no campo | A_SEGUIR | yaw máx (rad/s) |
|---|---|---|---|---|---|
| círculo 0,3 / 0,5 / 0,8 m/s | 0,50 / 1,1 · 0,49 / 1,1 · 0,43 / 1,2 | 0,028 · 0,030 · 0,028 / 0,07–0,15 | 100 % | 100 % | 0,31 · 0,46 · 0,70 |
| oito 0,3 m/s | 0,70 / 1,6 | 0,144 / 0,34 | 100 % | 100 % | 0,33 |
| oito 0,5 m/s | 1,84 / 4,6 | 0,206 / 0,49 | 100 % | 100 % | 0,67 |
| oito 0,8 m/s | 9,5 / 29 | 0,53 / 1,07 | 100 % | 97,9 % | **0,80 (satura)** |

- Alvo estático (6 posições, até ±27°): |e_ψ| < 2° em ≤ 2,3 s, < 0,6° no fim, vertical < 2 cm, |D−d*| ≈ 2 cm, sobre-elevação ≤ 10,3 %.
- **O feedforward é o que faz a diferença** — mas com honestidade: com o PI de margem ≥ 45° e SEM FF o círculo a 0,8 m/s erra 24,9° (58× pior que com FF). Um PI **forte** (Ki 0,5, integra
  sempre, clamp 1 rad/s) sem FF segue o CÍRCULO quase tão bem (0,54° / 1,13°) — a pesquisa tem razão: o integral anula o erro com taxa ≈ constante — **mas com PM = 31° (< 45°)**, e no
  «oito» (taxa que varia) o FF + avanço é 7× melhor (13,0° → 1,84°). O KF-CA ganha ao α-β 2,5–2,8× no oito em laço fechado (o avanço de fase precisa da aceleração). O FF vertical corta o desvio de 24 → 14 cm (alvo que sobe/desce ±0,5 m).
- Robusto: τ_yaw ∈ {0,3; 0,6} s × atraso ∈ {21; 166} ms em círculo 0,8 e oito 0,5 → sempre no campo, rumo RMS 0,42–2,96°. Com o pipeline DCMI do Arduino (21 ms) em vez dos 116 ms o erro de rumo só desce 4–16 % (círculo 0,8: 0,44° vs 0,43°; oito 0,5: 1,55° vs 1,84°): o previsor já absorve o atraso.
- **O oito a 0,8 m/s é o limite**: o alvo passa a 0,5 m com taxa de linha de vista ≈ 1,6 rad/s e o yaw satura em 0,8 rad/s; fica no campo mas com erro de ~9°. A autoridade de yaw (÷10–12) é o gargalo, não o algoritmo.
- **A autoridade de yaw é o gargalo do seguimento** (a B0 ainda a identifica: o `controlo_classico.py` em curso tem hoje `taxa_yaw_max` = 0,35 rad/s e `acel_yaw_max` = 0,45 rad/s²; a pesquisa dá 0,5–1 rad/s).
  Sensibilidade medida (rumo RMS em ° / % do tempo com o alvo no campo; só muda `yaw_max`/`yaw_acel_max`):

  | `yaw_max` / slew | círculo 0,3 m/s | círculo 0,5 m/s | círculo 0,8 m/s | oito 0,5 m/s |
  |---|---|---|---|---|
  | 0,35 rad/s / 0,45 rad/s² | 0,5° · 100 % | 4,7° · 100 % | **107° · 21 % (perde o alvo)** | 5,6° · 100 % |
  | 0,50 rad/s / 0,8 rad/s² | 0,6° · 100 % | 0,4° · 100 % | 21° · 100 % | 1,9° · 100 % |
  | 0,80 rad/s / 1,5 rad/s² (defeito) | 0,5° · 100 % | 0,5° · 100 % | 0,4° · 100 % | 1,8° · 100 % |

  Com o teto atual da B0 (0,35 rad/s) o IBVS só sustenta o círculo até ≈ 0,3 m/s; os 0,8 m/s pedem ≥ 0,7 rad/s. Antes de integrar: reler a identificação final da B0.
- Comparação com a referência: o tracker PPO tinha 0,94 m de erro de distância; aqui, na planta CINEMÁTICA, 0,03 m (círculo) / 0,14–0,21 m (oito 0,3–0,5) / 0,53 m (oito 0,8). **Não é uma comparação direta**: a planta é simples e a cascata real ainda não existe em C++.

## 4. Como correr

```bash
uv run --group hover-rl python experiments/09_drone_hover_rl/sitl_visao.py compilar   # .so em out/firmware/libvisao-<hash>.so
uv run --group hover-rl python experiments/09_drone_hover_rl/teste_visao.py           # 111 checagens (~35 s); --rapido salta as mutações
# cross-compile (como o núcleo): clang++ --target=thumbv7em-none-eabihf -mcpu=cortex-m7 -mfpu=fpv5-d16 -ffreestanding -fno-exceptions -fno-rtti -Os \
#   -std=c++17 -Wall -Wextra -Wdouble-promotion -Werror -I firmware -isystem firmware/cross -c firmware/cross/verifica_visao.cpp
```
`teste_visao.py`: §0 regras · §1 host (g++/clang++, C++11–20, `-Wshadow -Wconversion`, estresse ASan+UBSan: 20 000 frames hostis + 1 000 000 de passos do seguidor, 0 violações) ·
§2 cruzada M4/M7 (só `sinf cosf atan2f sqrtf` + `mem*`, sem heap/double/divisão de biblioteca) + ciclos M7 · §3 layout/Configs · §4 detetor em frames EGL · §5 estimador · §6 IBVS (margens,
laço fechado, estados, saneamento, determinismo, volta do relógio) · §7 **13/13 mutações da fonte C++ apanhadas** (sinal do yaw, atraso ignorado, gates de circularidade e «cheio»,
FF, desrotação de roll/pitch, sinal de v_z e da distância, gate de inovação, perda nunca declarada, sem histerese, sem slew, eixos do azimute trocados), cada uma pelo mecanismo certo.

## 5. Ressalvas (o que NÃO está provado)

- **Ciclos M7 = estimativa estática** (llvm-mca; caches/SRAM/flash ideais; libm assumida); nenhuma fonte prova o fps de visão no Portenta/Nicla; sem DWT numa placa fica por medir.
- **O laço do §6 é cinemático**: não é o simulador completo. A integração (atividade B) fechou o laço com o MuJoCo, com o `yaw_max`/τ_yaw reais da B0 (0,508 rad/s; 0,529 rad/s²) e as latências Pi (116 ms) e DCMI (21 ms): ver a secção «OLHAR» da atividade B — o rumo RMS sai 0,4–1,5° (≤ 0,5 m/s) em vez dos 0,43–0,50° cinemáticos (teto de yaw 0,8 rad/s), e a 0,8 m/s esbarra na autoridade de yaw.
- No laço cinemático a câmara é pinhole; na atividade B os frames são RENDERIZADOS (EGL) e passam pelo detetor C++ no laço (`sitl_camera.py`).
- Não se compensa a translação própria durante o atraso; a procura é só em yaw; um alvo parcialmente fora do campo é recusado, não estimado (tabela de falhas acima).
- Os ganhos (KF, IBVS) foram afinados com ruído sintético (σ_px 0,3; atitude 0,15° lenta) e leis de círculo/oito — voltar a afinar com o ruído do sensor real: **no laço fechado do simulador o gate recusa 3 medidas seguidas ~1×/s e o filtro reinicia (A_SEGUIR ≈ 95 %)** — ver o «achado de integração» da atividade B.
