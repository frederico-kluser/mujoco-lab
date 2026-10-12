// firmware/nucleo/taxa.hpp — laço de TAXA + mistura X + airmode (port float32 do ControladorFC.passo,
// experiments/09_drone_hover_rl/fc.py). MESMAS equações; só `float`; sem heap.
//
// Por eixo (p, q, r): PID de taxa com D sobre a MEDIDA, PT1 no giroscópio (fc_giro_hz) e no termo D
// (fc_d_hz), anti-windup por limite do integral:
//     giro_f += a_giro·(giro − giro_f)          erro = sp − giro_f
//     d_f    += a_d·((giro_f − giro_f_ant)/dt − d_f)
//     I       = clamp(I + ki·erro·dt, ±limite_i)
//     u_eixo  = kp·erro + I − kd·d_f
// Mistura X com airmode (como o Betaflight): dif = mix·u_eixos; se a amplitude do diferencial não cabe em
// [idle, 1] escala-se; u = coletivo + dif; se o máximo passa de 1 desloca-se tudo para baixo, se o mínimo
// fica abaixo de idle desloca-se para cima; corte final a [idle, 1]. Desarmado: tudo a 0 (e o estado
// não avança — como o ControladorFC).
#pragma once

#include <stdint.h>

#include "config.hpp"

namespace nucleo {

class ControladorTaxa {
public:
    void reiniciar() {
        for (int e = 0; e < 3; ++e) {
            integral_[e] = 0.0f;
            giro_f_[e] = 0.0f;
            d_f_[e] = 0.0f;
            giro_ant_[e] = 0.0f;
        }
        armado_ = false;
        dt_cache_ = 0.0f;
        a_giro_ = 0.0f;
        a_d_ = 0.0f;
    }

    void armar(bool armado) {
        if (armado && !armado_) {
            for (int e = 0; e < 3; ++e) integral_[e] = 0.0f;
        }
        armado_ = armado;
    }

    bool armado() const { return armado_; }
    float giro_f(int e) const { return giro_f_[e]; }

    // Um ciclo do FC: coletivo [0,1] + taxas-alvo (rad/s) + giroscópio medido → acelerador por motor.
    // Devolve os bits kFlag* deste passo. `u_eixos` recebe a saída do PID (antes da mistura).
    int32_t passo(const Config& c, float coletivo, const float sp[3], const float giro[3], float dt,
                  float u[4], float u_eixos[3]) {
        for (int i = 0; i < 4; ++i) u[i] = 0.0f;
        for (int e = 0; e < 3; ++e) u_eixos[e] = 0.0f;
        if (!armado_) return 0;
        int32_t flags = kFlagArmado;

        if (dt != dt_cache_) {  // coeficientes PT1 só se recalculam quando o dt muda
            dt_cache_ = dt;
            a_giro_ = alfa_pt1(c.fc_giro_hz, dt);
            a_d_ = alfa_pt1(c.fc_d_hz, dt);
        }

        for (int e = 0; e < 3; ++e) {
            giro_f_[e] += a_giro_ * (giro[e] - giro_f_[e]);
            const float erro = sp[e] - giro_f_[e];
            const float deriv = (giro_f_[e] - giro_ant_[e]) / dt;
            giro_ant_[e] = giro_f_[e];
            d_f_[e] += a_d_ * (deriv - d_f_[e]);
            integral_[e] = limita(integral_[e] + c.ki[e] * erro * dt, -c.limite_i, c.limite_i);
            u_eixos[e] = c.kp[e] * erro + integral_[e] - c.kd[e] * d_f_[e];
        }

        // mistura: diferencial por motor
        float dif[4];
        float dmax = 0.0f;
        float dmin = 0.0f;
        for (int i = 0; i < 4; ++i) {
            dif[i] = c.mix[i][0] * u_eixos[0] + c.mix[i][1] * u_eixos[1] + c.mix[i][2] * u_eixos[2];
            if (i == 0 || dif[i] > dmax) dmax = dif[i];
            if (i == 0 || dif[i] < dmin) dmin = dif[i];
        }
        const float col = limita(coletivo, 0.0f, 1.0f);
        const float span = dmax - dmin;
        const float faixa = 1.0f - c.idle;
        if (span > faixa) {  // o diferencial não cabe: escala-o
            const float k = faixa / span;
            for (int i = 0; i < 4; ++i) dif[i] *= k;
            flags |= kFlagDifEscalado;
        }
        float umax = 0.0f;
        float umin = 0.0f;
        for (int i = 0; i < 4; ++i) {
            u[i] = col + dif[i];
            if (i == 0 || u[i] > umax) umax = u[i];
        }
        if (umax > 1.0f) {  // airmode: desloca o coletivo para baixo
            const float d = umax - 1.0f;
            for (int i = 0; i < 4; ++i) u[i] -= d;
            flags |= kFlagAirmodeBaixo;
        }
        for (int i = 0; i < 4; ++i) {
            if (i == 0 || u[i] < umin) umin = u[i];
        }
        if (umin < c.idle) {  // ... ou para cima (nunca abaixo do idle)
            const float d = c.idle - umin;
            for (int i = 0; i < 4; ++i) u[i] += d;
            flags |= kFlagAirmodeAlto;
        }
        for (int i = 0; i < 4; ++i) u[i] = limita(u[i], c.idle, 1.0f);
        return flags;
    }

private:
    // PT1: alfa = dt/(rc+dt), rc = 1/(2π·fc)
    static float alfa_pt1(float fc_hz, float dt) {
        const float rc = 1.0f / (2.0f * kPi * fc_hz);
        return dt / (rc + dt);
    }

    float integral_[3] = {};
    float giro_f_[3] = {};
    float d_f_[3] = {};
    float giro_ant_[3] = {};
    bool armado_ = false;
    float dt_cache_ = 0.0f;
    float a_giro_ = 0.0f;
    float a_d_ = 0.0f;
};

}  // namespace nucleo
