// firmware/nucleo/ibvs_ganhos.hpp — os GANHOS AFINADOS da lei «seguir a bola» (ibvs.hpp, versão 2). C++ float32.
//
// GERADO por experiments/09_drone_hover_rl/treinar_bola.py --promover — NÃO EDITAR À MÃO (regenerar com o treino).
// É a única fonte dos números que `visao::config_padrao` põe na lei por omissão (a que o runner da interface usa);
// os limites de guinada/velocidade continuam a vir da planta (sitl.config_de_hardware) e não daqui.
//
// proveniência: treinar_bola.py 2026-10-12T20:32:34 · sep-CMA-ES (Ros & Hansen 2008), 12 gerações × 12 candidatos · sementes de afinação 8100–8111 · validação: custo 4.599 → 4.112, centragem RMS 2.47° → 2.32°
#pragma once

namespace nucleo {
namespace visao {
namespace ganhos {

constexpr float kSigmaPx = 0.304124f;  // px — σ da medida de u, v no filtro do alvo
constexpr float kQAng = 0.0939098f;    // rad²·s⁻⁵ — PSD do jerk dos ângulos (KF-CA)
constexpr float kQRaioCv = 2e-06f;     // s⁻³ — PSD da aceleração do raio normalizado (canal do raio em CV)
constexpr float kKpZ = 2.20382f;       // 1/s — P do desvio vertical
constexpr float kKffZ = 0.617225f;     // feedforward da velocidade vertical do alvo
constexpr float kAcelZMax = 1.5f;      // m/s² — slew de v_z
constexpr float kKpD = 0.771434f;      // 1/s — P da distância
constexpr float kKffD = 0.525232f;     // feedforward da velocidade radial do alvo
constexpr float kAcelXMax = 1.11233f;  // m/s² — slew de v_x
constexpr float kZonaMortaD = 0.03f;   // m — zona morta da distância
constexpr float kKpY = 1.32085f;       // 1/s — P do desvio lateral
constexpr float kKffY = 0.453968f;     // fração da velocidade tangencial do alvo que a translação lateral leva (o resto: guinada)
constexpr float kAcelYMax = 3.77003f;  // m/s² — slew de v_y
constexpr float kInclZ = 1.0f;         // [0,1] — canal vertical na IMAGEM (compensa a inclinação do corpo)
constexpr float kTauIncl = 0.15f;      // s — PT1 da parcela de inclinação

}  // namespace ganhos
}  // namespace visao
}  // namespace nucleo
