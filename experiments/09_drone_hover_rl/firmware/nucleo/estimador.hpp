// firmware/nucleo/estimador.hpp — estimador de bordo (port float32 do EstimadorBordo,
// experiments/09_drone_hover_rl/estimador.py). MESMAS equações; só `float`; sem heap. Entradas: SÓ as
// leituras MEDIDAS (giroscópio, acelerómetro, ToF, fluxo ótico) — nada de verdade do simulador.
//
//   · ATITUDE (roll φ, pitch θ): filtro complementar — integra as taxas medidas (cinemática de Euler ZYX)
//     e puxa devagar (k_atitude) para a inclinação do acelerómetro φ_a = atan2(a_y, a_z),
//     θ_a = atan2(−a_x, √(a_y²+a_z²)).
//   · RUMO ψ desde o armar: integração da taxa de guinada (sem magnetómetro → deriva com o bias do giro).
//   · ALTURA ĥ e v̂_z: predição com a aceleração vertical (R̂·a − g) e correção a cada amostra NOVA do ToF
//     (ĥ_ToF = d·cosφ̂·cosθ̂) com ganhos de observador de 2.ª ordem (w_altura, zeta_altura).
//   · VELOCIDADE HORIZONTAL (corpo) pelo fluxo: v_x = d·(q − Ω_y), v_y = −d·(Ω_x + p), com PT1;
//     sem fluxo/ToF válidos decai (decai_fluxo por passo).
//   · ODOMETRIA (x̂, ŷ) no frame de arranque: integra R_z(ψ)·v̂_xy (deriva, como a de qualquer drone sem GPS).
//
// Otimização sem mudar nenhum número: o sen/cos de roll e pitch ao FIM de um passo são exatamente os do
// INÍCIO do seguinte (o estado não muda entre passos) — ficam em cache (4 chamadas de libm a menos).
#pragma once

#include <math.h>
#include <stdint.h>

#include "config.hpp"

namespace nucleo {

class EstimadorBordo {
public:
    // estado estimado (leitura)
    float roll = 0.0f;
    float pitch = 0.0f;
    float psi = 0.0f;
    float h = 0.0f;
    float vz = 0.0f;
    float vx = 0.0f;
    float vy = 0.0f;
    float x = 0.0f;
    float y = 0.0f;

    // Calibra a partir de uma leitura em repouso (como EstimadorBordo.reiniciar): roll/pitch do
    // acelerómetro, altura do ToF (se válido), o resto a zero; o contador de amostras fica "desconhecido"
    // (-1) para que a PRÓXIMA amostra conte como nova.
    void calibrar(const Sensores& s) {
        const float ax = s.acc[0];
        const float ay = s.acc[1];
        const float az = s.acc[2];
        roll = atan2f(ay, az);
        pitch = atan2f(-ax, sqrtf(ay * ay + az * az));
        psi = 0.0f;
        atualiza_trig();
        h = s.tof_ok != 0 ? s.tof_d * cf_ * ct_ : 0.0f;
        vz = 0.0f;
        vx = 0.0f;
        vy = 0.0f;
        x = 0.0f;
        y = 0.0f;
        n_tof_ = -1;
        n_fluxo_ = -1;
    }

    void zerar() {
        roll = pitch = psi = h = vz = vx = vy = x = y = 0.0f;
        atualiza_trig();
        n_tof_ = -1;
        n_fluxo_ = -1;
    }

    // Um passo com as leituras atuais (`n_tof`/`n_fluxo` = contadores de amostras, para detetar novas).
    void passo(const Config& c, const Sensores& s, float dt) {
        const float p = s.giro[0];
        const float q = s.giro[1];
        const float r = s.giro[2];
        const float ax = s.acc[0];
        const float ay = s.acc[1];
        const float az = s.acc[2];
        const bool tof_ok = s.tof_ok != 0;
        const bool fluxo_ok = s.fluxo_ok != 0;

        // atitude: cinemática ZYX + correção do acelerómetro (sen/cos do estado atual em cache)
        const bool ct_ok = absf(ct_) > 1e-3f;
        const float tt = ct_ok ? st_ / ct_ : 0.0f;
        const float qs_rc = q * sf_ + r * cf_;
        const float droll = p + qs_rc * tt;
        const float dpitch = q * cf_ - r * sf_;
        const float dpsi = ct_ok ? qs_rc / ct_ : 0.0f;
        const float hip = sqrtf(ay * ay + az * az);
        const float roll_a = atan2f(ay, az);
        const float pitch_a = atan2f(-ax, hip);
        roll += dt * (droll + c.k_atitude * envolve(roll_a - roll));
        pitch += dt * (dpitch + c.k_atitude * (pitch_a - pitch));
        psi = envolve(psi + dt * dpsi);

        // altura e velocidade vertical
        atualiza_trig();
        const float a_z = -st_ * ax + sf_ * ct_ * ay + cf_ * ct_ * az - c.gravidade;
        vz += a_z * dt;
        h += vz * dt;
        if (s.n_tof != n_tof_) {
            n_tof_ = s.n_tof;
            if (tof_ok) {
                const float periodo = dt > c.periodo_tof_min ? dt : c.periodo_tof_min;
                float k_h = 2.0f * c.zeta_altura * c.w_altura * periodo;
                if (k_h > 1.0f) k_h = 1.0f;
                const float k_v = c.w_altura * c.w_altura * periodo;
                const float e = s.tof_d * cf_ * ct_ - h;
                h += k_h * e;
                vz += k_v * e;
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

    // Tudo a ZERO: a instância fica em .bss (sem imagem de arranque em flash). Os valores certos (cos = 1,
    // contadores = -1) põem-se em zerar()/calibrar() — chame um deles antes de usar o estimador sozinho.
    float sf_ = 0.0f;   // sen/cos de roll e pitch do estado atual (cache)
    float cf_ = 0.0f;
    float st_ = 0.0f;
    float ct_ = 0.0f;
    int32_t n_tof_ = 0;
    int32_t n_fluxo_ = 0;
};

}  // namespace nucleo
