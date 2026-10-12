// firmware/nucleo/estimador_classico.hpp — estimador MELHORADO (port float32 do EstimadorClassico,
// experiments/09_drone_hover_rl/controlo_classico.py). MESMAS equações; só `float`; sem heap. Entradas: SÓ as
// leituras MEDIDAS (giroscópio, acelerómetro, ToF, fluxo ótico) — nada de verdade do simulador.
//
// Face ao EstimadorBordo (estimador.hpp), três correções MEDIDAS no simulador (README «Estimador melhorado»):
//   1. CALIBRAÇÃO DO GIROSCÓPIO NO CHÃO: com o drone PARADO (motores em idle) acumulam-se giroscópio e acelerómetro
//      (`janela_calibracao(c, true)` … `false`); no fim b̂ = média do giroscópio e a atitude inicial sai da MÉDIA do
//      acelerómetro. O viés (σ = 3,5 mrad/s por voo no BMI088) entrava no RUMO e na velocidade do fluxo
//      (v = d·(q − Ω_y) = v + d·b: ~10 cm de deriva de odometria em 30 s). É o «gyro calibration» que PX4/ArduPilot
//      fazem ao ligar (ideia pública; código próprio);
//   2. PORTÃO DO ACELERÓMETRO: um multirrotor mede o EMPUXO (sempre ao longo de z_corpo) e não a gravidade quando
//      acelera: a correção «para o acelerómetro» puxava a inclinação para ZERO nas manobras. O ganho é escalado por
//      1/(1+(‖a_h‖/a_portão)²), com ‖a_h‖ a aceleração horizontal estimada da derivada filtrada da velocidade do
//      fluxo (v̂ − v̂_lenta)/τ;
//   3. ALTURA DE 3.ª ORDEM: observador (ĥ, v̂_z, viés do acelerómetro vertical) de polos triplos em −ω₀ — com o de
//      2.ª ordem o viés do acelerómetro (≈ 0,1 m/s²) dava um viés de v̂_z de ≈ 4 cm/s e a altura assentava 3–4 cm abaixo.
// O resto (cinemática de Euler ZYX, v̂_xy do fluxo no corpo, odometria) é igual ao EstimadorBordo.
//
// Fontes (ideias; código próprio): Mahony, Hamel & Pflimlin, «Nonlinear Complementary Filters on the Special
// Orthogonal Group», IEEE TAC 53(5), 2008 (filtro complementar; a parte I existe como opção, desligada: medido que
// não ajuda em voo); Åström & Murray, «Feedback Systems», 2008 (observador por colocação de polos).
//
// Constantes: TODAS vêm da Config (c.k_atitude, c.w_altura, c.est_cl…); só há guardas numéricas aqui.
#pragma once

#include <math.h>
#include <stdint.h>

#include "config.hpp"

namespace nucleo {

namespace estimador_classico_detalhe {
// guarda numérica da singularidade de Euler (|cosθ| ≤ 1e-3 ⇒ sem tan θ nem 1/cosθ) — não é um parâmetro de projeto
constexpr float kCosPitchMin = 1e-3f;
}  // namespace estimador_classico_detalhe

class EstimadorClassico {
public:
    // estado estimado (leitura) — os mesmos nomes que o EstimadorBordo
    float roll = 0.0f;
    float pitch = 0.0f;
    float psi = 0.0f;
    float h = 0.0f;
    float vz = 0.0f;
    float vx = 0.0f;
    float vy = 0.0f;
    float x = 0.0f;
    float y = 0.0f;

    // Estado inicial a partir de UMA leitura (≡ EstimadorClassico.reiniciar(acc, tof_d, tof_ok)): roll/pitch do
    // acelerómetro, altura do ToF (se válido), viés zero, o resto a zero; os contadores de amostras ficam
    // «desconhecidos» (-1) para a PRÓXIMA amostra contar como nova.
    void iniciar_com(const Sensores& s) {
        roll = atan2f(s.acc[1], s.acc[2]);
        pitch = atan2f(-s.acc[0], sqrtf(s.acc[1] * s.acc[1] + s.acc[2] * s.acc[2]));
        psi = 0.0f;
        atualiza_trig();
        h = s.tof_ok != 0 ? s.tof_d * cf_ * ct_ : 0.0f;
        vz = vx = vy = x = y = 0.0f;
        for (int i = 0; i < 3; ++i) bias_giro_[i] = 0.0f;
        bias_acc_ = 0.0f;
        b_pi_[0] = b_pi_[1] = 0.0f;
        calibrando_ = false;
        n_cal_ = 0;
        ultimo_tof_d_ = s.tof_d;
        ultimo_tof_ok_ = s.tof_ok != 0;
        n_tof_ = -1;
        n_fluxo_ = -1;
        a_h_ = 0.0f;
        v_lenta_[0] = v_lenta_[1] = 0.0f;
    }

    // Tudo a zero (estimador corrompido ou reinício): a atitude volta a ser calibrada na leitura seguinte.
    void zerar() {
        roll = pitch = psi = h = vz = vx = vy = x = y = 0.0f;
        atualiza_trig();
        for (int i = 0; i < 3; ++i) bias_giro_[i] = 0.0f;
        bias_acc_ = 0.0f;
        b_pi_[0] = b_pi_[1] = 0.0f;
        calibrando_ = false;
        n_cal_ = 0;
        ultimo_tof_d_ = 0.0f;
        ultimo_tof_ok_ = false;
        n_tof_ = -1;
        n_fluxo_ = -1;
        a_h_ = 0.0f;
        v_lenta_[0] = v_lenta_[1] = 0.0f;
    }

    // `true` abre a janela de calibração (drone PARADO no chão: os passos acumulam em vez de integrar); `false`
    // fecha-a e aplica b̂ (se cal_giro) e a atitude/altura iniciais da média. Sem amostras, não muda nada.
    void janela_calibracao(const Config& c, bool ativa) {
        if (ativa) {
            calibrando_ = true;
            n_cal_ = 0;
            return;
        }
        if (calibrando_ && n_cal_ > 0) {
            const float n = static_cast<float>(n_cal_);
            float media_g[3];
            float media_a[3];
            for (int i = 0; i < 3; ++i) {
                media_g[i] = base_giro_[i] + soma_giro_[i] / n;
                media_a[i] = base_acc_[i] + soma_acc_[i] / n;
            }
            if (c.est_cl.cal_giro != 0) {
                for (int i = 0; i < 3; ++i) bias_giro_[i] = media_g[i];
            }
            roll = atan2f(media_a[1], media_a[2]);
            pitch = atan2f(-media_a[0], sqrtf(media_a[1] * media_a[1] + media_a[2] * media_a[2]));
            atualiza_trig();
            if (ultimo_tof_ok_) h = ultimo_tof_d_ * cf_ * ct_;
            psi = 0.0f;
            vz = vx = vy = x = y = 0.0f;
        }
        calibrando_ = false;
    }

    bool calibrando() const { return calibrando_; }
    float bias_giro(int e) const { return bias_giro_[e]; }
    float bias_acc() const { return bias_acc_; }
    float a_horizontal() const { return a_h_; }

    // Um passo com as leituras atuais (`n_tof`/`n_fluxo` = contadores de amostras, para detetar novas).
    void passo(const Config& c, const Sensores& s, float dt) {
        const ConfigEstimadorClassico& e = c.est_cl;
        if (calibrando_) {
            acumular(s);
            return;
        }
        const float p = s.giro[0] - bias_giro_[0] - b_pi_[0];
        const float q = s.giro[1] - bias_giro_[1] - b_pi_[1];
        const float r = s.giro[2] - bias_giro_[2];
        const float ax = s.acc[0];
        const float ay = s.acc[1];
        const float az = s.acc[2];
        const bool tof_ok = s.tof_ok != 0;
        const bool fluxo_ok = s.fluxo_ok != 0;

        // atitude: cinemática ZYX + correção do acelerómetro com portão (sen/cos do estado atual em cache)
        const bool ct_ok = absf(ct_) > estimador_classico_detalhe::kCosPitchMin;
        const float tt = ct_ok ? st_ / ct_ : 0.0f;
        const float qs_rc = q * sf_ + r * cf_;
        const float droll = p + qs_rc * tt;
        const float dpitch = q * cf_ - r * sf_;
        const float dpsi = ct_ok ? qs_rc / ct_ : 0.0f;
        float k = c.k_atitude;
        if (e.portao_acc != 0) {
            const float rel = a_h_ / e.a_portao;
            k = k / (1.0f + rel * rel);
        }
        const float hip = sqrtf(ay * ay + az * az);
        const float roll_a = atan2f(ay, az);
        const float pitch_a = atan2f(-ax, hip);
        const float e_roll = envolve(roll_a - roll);
        const float e_pitch = pitch_a - pitch;
        if (e.ki_mahony > 0.0f) {  // parte INTEGRAL de Mahony (viés de p, q), com o mesmo portão
            const float ki = e.ki_mahony * k / c.k_atitude;
            b_pi_[0] = limita(b_pi_[0] - ki * e_roll * dt, -e.lim_bias_pi, e.lim_bias_pi);
            b_pi_[1] = limita(b_pi_[1] - ki * e_pitch * dt, -e.lim_bias_pi, e.lim_bias_pi);
        }
        roll += dt * (droll + k * e_roll);
        pitch += dt * (dpitch + k * e_pitch);
        psi = envolve(psi + dt * dpsi);

        // altura e velocidade vertical (observador de 3.ª ordem, ou de 2.ª se bias_acc_z = 0)
        atualiza_trig();
        const float a_z = -st_ * ax + sf_ * ct_ * ay + cf_ * ct_ * az - c.gravidade - bias_acc_;
        vz += a_z * dt;
        h += vz * dt;
        if (s.n_tof != n_tof_) {
            n_tof_ = s.n_tof;
            if (tof_ok) {
                const float periodo = dt > c.periodo_tof_min ? dt : c.periodo_tof_min;
                const float erro = s.tof_d * cf_ * ct_ - h;
                const float w = c.w_altura;
                if (e.bias_acc_z != 0) {  // polos triplos em −ω₀: (s + ω₀)³ ⇒ ganhos 3ω₀, 3ω₀², ω₀³
                    float k_h = 3.0f * w * periodo;
                    if (k_h > 1.0f) k_h = 1.0f;
                    h += k_h * erro;
                    vz += 3.0f * w * w * periodo * erro;
                    bias_acc_ = limita(bias_acc_ - w * w * w * periodo * erro, -e.lim_bias_acc, e.lim_bias_acc);
                } else {  // 2.ª ordem do EstimadorBordo (ζ da Config)
                    float k_h = 2.0f * c.zeta_altura * w * periodo;
                    if (k_h > 1.0f) k_h = 1.0f;
                    h += k_h * erro;
                    vz += w * w * periodo * erro;
                }
            }
        }

        // velocidade horizontal pelo fluxo (com a distância medida pelo ToF, mesmo site)
        if (s.n_fluxo != n_fluxo_) {
            n_fluxo_ = s.n_fluxo;
            if (fluxo_ok && tof_ok) {
                const float vx_m = s.tof_d * (q - s.fluxo[1]);
                const float vy_m = -s.tof_d * (s.fluxo[0] + p);
                vx += c.alfa_fluxo * (vx_m - vx);
                vy += c.alfa_fluxo * (vy_m - vy);
            }
        }
        if (!(fluxo_ok && tof_ok)) {
            vx *= c.decai_fluxo;
            vy *= c.decai_fluxo;
        }
        if (e.portao_acc != 0) {  // ‖a_h‖ ≈ ‖v̂ − v̂_lenta‖/τ (derivada suave: v̂_lenta = PT1 de constante τ)
            const float a_l = dt / (e.tau_acc_portao + dt);
            v_lenta_[0] += a_l * (vx - v_lenta_[0]);
            v_lenta_[1] += a_l * (vy - v_lenta_[1]);
            const float dvx = vx - v_lenta_[0];
            const float dvy = vy - v_lenta_[1];
            a_h_ = sqrtf(dvx * dvx + dvy * dvy) / e.tau_acc_portao;
        }
        const float cpsi = cosf(psi);
        const float spsi = sinf(psi);
        x += dt * (cpsi * vx - spsi * vy);
        y += dt * (spsi * vx + cpsi * vy);
    }

private:
    // ângulo → [-π, π). Válido para |a| ≤ 3π (as entradas são sempre ≈ ±π): sem fmod/floor (libm).
    static float envolve(float a) {
        if (a > kPi) return a - 2.0f * kPi;
        if (a < -kPi) return a + 2.0f * kPi;
        return a;
    }

    void atualiza_trig() {
        sf_ = sinf(roll);
        cf_ = cosf(roll);
        st_ = sinf(pitch);
        ct_ = cosf(pitch);
    }

    // Soma dos DESVIOS à 1.ª amostra (a média é base + soma/n): a soma de 500+ valores ≈ 9,8 m/s² perde bits em float32.
    void acumular(const Sensores& s) {
        if (n_cal_ == 0) {
            for (int i = 0; i < 3; ++i) {
                base_giro_[i] = s.giro[i];
                base_acc_[i] = s.acc[i];
                soma_giro_[i] = 0.0f;
                soma_acc_[i] = 0.0f;
            }
        }
        for (int i = 0; i < 3; ++i) {
            soma_giro_[i] += s.giro[i] - base_giro_[i];
            soma_acc_[i] += s.acc[i] - base_acc_[i];
        }
        ++n_cal_;
        ultimo_tof_d_ = s.tof_d;
        ultimo_tof_ok_ = s.tof_ok != 0;
    }

    // Tudo a ZERO: a instância fica em .bss (sem imagem de arranque em flash). Os valores certos (cos = 1,
    // contadores = -1) põem-se em zerar()/iniciar_com() — chame um deles antes de usar o estimador sozinho.
    float sf_ = 0.0f;   // sen/cos de roll e pitch do estado atual (cache)
    float cf_ = 0.0f;
    float st_ = 0.0f;
    float ct_ = 0.0f;
    float bias_giro_[3] = {};
    float bias_acc_ = 0.0f;   // m/s² — viés do acelerómetro na VERTICAL (3.º estado do observador de altura)
    float b_pi_[2] = {};      // rad/s — viés residual de p, q do integral de Mahony
    float base_giro_[3] = {};
    float base_acc_[3] = {};
    float soma_giro_[3] = {};
    float soma_acc_[3] = {};
    float ultimo_tof_d_ = 0.0f;
    float a_h_ = 0.0f;        // m/s² — aceleração horizontal estimada (portão)
    float v_lenta_[2] = {};
    int32_t n_cal_ = 0;
    int32_t n_tof_ = 0;
    int32_t n_fluxo_ = 0;
    bool calibrando_ = false;
    bool ultimo_tof_ok_ = false;
};

}  // namespace nucleo
