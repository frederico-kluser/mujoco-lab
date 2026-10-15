// firmware/nucleo/alvo.hpp — ESTIMADOR DO ALVO: bearing inercial (azimute, elevação, raio) com compensação do
// atraso da câmara. C++ float32, sem heap, só sinf/cosf/atan2f/sqrtf.
//
// PROBLEMA. O detetor dá a posição do alvo na IMAGEM (u, v, raio) de um frame capturado há ≈ 116 ms (pipeline
// Pi) ou ≈ 20–40 ms (DCMI do Arduino) e o drone ROTACIONA (o yaw é o que centra o alvo), por isso o bearing em
// coordenadas da câmara mistura o movimento do alvo com o do próprio drone. A solução padrão (IBVS com yaw
// livre, ver pesquisas/…, Q7: «Kalman atrasado + IMU» [S87], «Smith» [S88]):
//   1. DESRODAR — guardar um histórico curto da atitude do corpo (roll, pitch, ψ do estimador de bordo) e,
//      quando chega um frame, converter o pixel do INSTANTE DA CAPTURA numa direção no referencial INERCIAL
//      (z para cima, alinhado ao rumo de arranque):  d_w = R(φ,θ,ψ)(t_captura)·d_corpo(u, v);
//      azimute  α = atan2(d_w.y, d_w.x)  e elevação  ε = atan2(d_w.z, √(d_w.x² + d_w.y²));  raio ρ = raio_px/f.
//      α e ε já não dependem da rotação do drone (nem de roll/pitch): só do movimento relativo do alvo.
//   2. FILTRAR no tempo da captura (o filtro corre «atrasado»: as medidas chegam por ordem de captura, sem
//      desfasamento entre medida e estado) — α-β, KF de velocidade constante (CV) ou de aceleração constante
//      (CA) por canal, com gate de inovação (recusa outliers; 3 recusas seguidas reiniciam o filtro).
//   3. PREVER para o instante ATUAL: x(t_agora) = F(t_agora − t_filtro)·x — a previsão é o que a lei IBVS usa, a
//      rotação própria dentro do atraso é EXATA (vem do histórico de atitude), só o movimento do alvo é
//      extrapolado. Dá também a taxa de bearing (feedforward do yaw) e a aceleração (KF-CA: avanço de fase).
// TRANSLAÇÃO PRÓPRIA (opcional, `ConfigSeguidor::comp_translacao`). O drone também ANDA (o modo «seguir a bola» usa v_x, v_y e
// v_z), e o bearing muda tanto por o alvo se mexer como por o drone se deslocar. Sem compensação essa parte fica no ruído de
// processo e — pior — a «velocidade do alvo» que a lei usa como feedforward tem de se reconstruir somando a velocidade própria
// de AGORA a uma taxa de bearing que o filtro só vê ATRASADA: a diferença de atrasos é um termo ∝ aceleração própria com sinal
// de realimentação POSITIVA (medido no simulador completo: v_z a oscilar a 0,87 Hz e o pitch a 0,5–0,7 Hz). Com a compensação
// o histórico guarda também a POSIÇÃO própria (odometria de bordo integrada pelo seguidor) e o estado do filtro é reposto
// GEOMETRICAMENTE sempre que o ponto de observação muda (`deslocar`): r' = D·d(α, ε) − Δp_próprio ⇒ (α', ε', ρ'). As taxas do
// filtro passam a ser SÓ do alvo (o feedforward sai limpo, sem somar a velocidade própria) e a previsão para «agora» desconta o
// que o drone andou durante o atraso da câmara. É a entrada conhecida do filtro de Kalman (Kalman 1960; Bar-Shalom, cap. 6).
//
// Convenções: referencial do corpo = frente x · esquerda y · cima z (FLU); rotação ZYX R = Rz(ψ)·Ry(θ)·Rx(φ)
// (a MESMA do estimador de bordo, estimador.hpp: pitch > 0 = nariz para baixo); câmara montada à frente com
// inclinação opcional (rad, + = para cima); píxeis em convenção do ÍNDICE. Azimute + anti-horário visto de cima.
//
// Referências (ideias/algoritmos; o código é próprio): Kalman 1960; Bar-Shalom «Estimation with Applications to
// Tracking and Navigation» (α-β, CV/CA, ruído de jerk branco); Larsen et al. 1998 (medidas atrasadas);
// Chaumette & Hutchinson 2006/2007 (IBVS).
#pragma once

#include <math.h>
#include <stdint.h>

#include "visao_tipos.hpp"

namespace nucleo {
namespace visao {

constexpr float kPi = 3.14159265358979323846f;
constexpr float kDoisPi = 6.28318530717958647692f;

namespace geo {

inline bool finito(float x) { return (x - x) == 0.0f; }  // falso para NaN e ±inf
inline float absf(float x) { return x < 0.0f ? -x : x; }
inline float limita(float x, float lo, float hi) { return x < lo ? lo : (x > hi ? hi : x); }

// ângulo → [−π, π]; não finito → 0; o laço é limitado (|a| ≲ 100π)
inline float envolve(float a) {
    if (!finito(a)) return 0.0f;
    int32_t guarda = 0;
    while (a > kPi && guarda < 64) {
        a -= kDoisPi;
        ++guarda;
    }
    while (a < -kPi && guarda < 128) {
        a += kDoisPi;
        ++guarda;
    }
    return limita(a, -kPi, kPi);
}

struct Vec3 {
    float x;
    float y;
    float z;
};

struct Rot {
    float m[9];  // por linhas: v_mundo = R·v_corpo
};

// R = Rz(yaw)·Ry(pitch)·Rx(roll)
inline Rot rot_zyx(float roll, float pitch, float yaw) {
    const float cr = cosf(roll);
    const float sr = sinf(roll);
    const float cp = cosf(pitch);
    const float sp = sinf(pitch);
    const float cy = cosf(yaw);
    const float sy = sinf(yaw);
    Rot r;
    r.m[0] = cy * cp;
    r.m[1] = cy * sp * sr - sy * cr;
    r.m[2] = cy * sp * cr + sy * sr;
    r.m[3] = sy * cp;
    r.m[4] = sy * sp * sr + cy * cr;
    r.m[5] = sy * sp * cr - cy * sr;
    r.m[6] = -sp;
    r.m[7] = cp * sr;
    r.m[8] = cp * cr;
    return r;
}

inline Vec3 aplica(const Rot& r, const Vec3& v) {
    Vec3 o;
    o.x = r.m[0] * v.x + r.m[1] * v.y + r.m[2] * v.z;
    o.y = r.m[3] * v.x + r.m[4] * v.y + r.m[5] * v.z;
    o.z = r.m[6] * v.x + r.m[7] * v.y + r.m[8] * v.z;
    return o;
}

inline Vec3 aplica_t(const Rot& r, const Vec3& v) {  // Rᵀ·v
    Vec3 o;
    o.x = r.m[0] * v.x + r.m[3] * v.y + r.m[6] * v.z;
    o.y = r.m[1] * v.x + r.m[4] * v.y + r.m[7] * v.z;
    o.z = r.m[2] * v.x + r.m[5] * v.y + r.m[8] * v.z;
    return o;
}

// Óptica da câmara (cache de sen/cos da inclinação)
struct Otica {
    float f;
    float cx;
    float cy;
    float ca;  // cos(inclinação)
    float sa;  // sen(inclinação)
};

inline Otica otica_de(const ConfigSeguidor& c) {
    Otica o;
    o.f = c.f_px;
    o.cx = c.cx;
    o.cy = c.cy;
    o.ca = cosf(c.inclinacao_cam);
    o.sa = sinf(c.inclinacao_cam);
    return o;
}

// direção unitária, no CORPO, do raio do píxel (u, v). Eixos da câmara no corpo: frente (ca,0,sa),
// direita (0,−1,0), baixo (sa,0,−ca)
inline Vec3 raio_no_corpo(const Otica& o, float u, float v) {
    const float xn = (u - o.cx) / o.f;
    const float yn = (v - o.cy) / o.f;
    Vec3 d;
    d.x = o.ca + yn * o.sa;
    d.y = -xn;
    d.z = o.sa - yn * o.ca;
    const float n = sqrtf(d.x * d.x + d.y * d.y + d.z * d.z);
    const float k = n > 1e-9f ? 1.0f / n : 0.0f;
    d.x *= k;
    d.y *= k;
    d.z *= k;
    return d;
}

// píxel → (azimute, elevação) INERCIAIS (z para cima), dada a atitude R do corpo
inline void pixel_para_angulos(const Otica& o, const Rot& r, float u, float v, float* az, float* el) {
    const Vec3 dw = aplica(r, raio_no_corpo(o, u, v));
    *az = atan2f(dw.y, dw.x);
    *el = atan2f(dw.z, sqrtf(dw.x * dw.x + dw.y * dw.y));
}

// (azimute, elevação) inerciais → píxel, dada a atitude R do corpo; false se o alvo estiver atrás do plano da câmara
inline bool angulos_para_pixel(const Otica& o, const Rot& r, float az, float el, float* u, float* v) {
    const float ce = cosf(el);
    Vec3 dw;
    dw.x = ce * cosf(az);
    dw.y = ce * sinf(az);
    dw.z = sinf(el);
    const Vec3 db = aplica_t(r, dw);
    const float zc = db.x * o.ca + db.z * o.sa;
    if (!(zc > 1e-3f)) return false;
    const float xc = -db.y;
    const float yc = db.x * o.sa - db.z * o.ca;
    *u = o.cx + o.f * xc / zc;
    *v = o.cy + o.f * yc / zc;
    return true;
}

}  // namespace geo

namespace alvo_detalhe {
constexpr int32_t kPassoHistMinUs = 4000;  // µs — o histórico guarda no máximo 1 amostra a cada 4 ms (chamar a 500 Hz não o esgota)
constexpr float kDtMax = 1.5f;      // s — medidas mais espaçadas que isto: o filtro recomeça
constexpr int32_t kDtMinUs = 2000;  // µs — medidas mais coladas que isto (2 ms) ignoram-se
constexpr float kDtPrevMax = 1.0f;  // s — a previsão satura aqui
constexpr int32_t kRecusasParaReiniciar = 3;
constexpr float kRhoMinDesloca = 1e-4f;   // raio normalizado mínimo para converter em distância (guarda numérica)
constexpr float kDistMinDesloca = 0.05f;  // m — alvo a menos disto do ponto de observação: a geometria degenera (guarda)
// σ da incerteza de MODELO do α-β para o gate (rad, rad, raio normalizado): ≈ taxa·T ≈ 0,5 rad/s × 0,04 s
inline float sigma_modelo_ab(int32_t canal) { return canal == 2 ? 0.004f : 0.03f; }
}  // namespace alvo_detalhe

// ------------------------------------------------------------------------------------ histórico de atitude
// Anel das últimas kN atitudes (t em µs; só diferenças, volta a 71 min) — empurra-se UMA por chamada do
// seguidor (50–250 Hz ⇒ 0,26–1,3 s de histórico; acima de 250 Hz decima-se). consultar(t) interpola linearmente (o rumo pela diferença
// envolvida); fora do intervalo devolve a amostra mais próxima e `fora = true`.
class HistoricoAtitude {
public:
    enum : int32_t { kN = 64 };

    void zerar() {
        cab_ = 0;
        n_ = 0;
        for (int32_t i = 0; i < kN; ++i) {
            for (int32_t e = 0; e < 3; ++e) pos_[i][e] = 0.0f;
        }
    }

    int32_t tamanho() const { return n_; }

    // `pos` (opcional) = posição PRÓPRIA no referencial de arranque (m; odometria integrada pelo seguidor) nesse instante
    void empurrar(uint32_t t_us, float roll, float pitch, float psi, const float* pos = nullptr) {
        // só avança no tempo e com ≥ 4 ms entre amostras: o seguidor pode ser chamado a 50–500 Hz e o anel de 64 amostras
        // cobre sempre ≥ 256 ms (o atraso da câmara cabe)
        if (n_ > 0 && static_cast<int32_t>(t_us - t_[indice(0)]) < alvo_detalhe::kPassoHistMinUs) return;
        t_[cab_] = t_us;
        roll_[cab_] = roll;
        pitch_[cab_] = pitch;
        psi_[cab_] = psi;
        for (int32_t e = 0; e < 3; ++e) pos_[cab_][e] = pos != nullptr ? pos[e] : 0.0f;
        cab_ = (cab_ + 1) % kN;
        if (n_ < kN) ++n_;
    }

    // `pos` (opcional) recebe a posição própria interpolada no mesmo instante
    bool consultar(uint32_t t_us, float* roll, float* pitch, float* psi, bool* fora, float* pos = nullptr) const {
        if (n_ == 0) return false;
        for (int32_t k = 0; k < n_; ++k) {
            const int32_t i = indice(k);
            const int32_t d = static_cast<int32_t>(t_us - t_[i]);  // ≥ 0 ⇔ t_i ≤ t
            if (d < 0) continue;
            if (k == 0) {  // t igual ou depois da amostra mais recente
                *roll = roll_[i];
                *pitch = pitch_[i];
                *psi = psi_[i];
                if (pos != nullptr) {
                    for (int32_t e = 0; e < 3; ++e) pos[e] = pos_[i][e];
                }
                *fora = d > 20000;  // > 20 ms à frente da última amostra: extrapolação
                return true;
            }
            const int32_t j = indice(k - 1);  // a amostra seguinte (mais nova)
            const int32_t span = static_cast<int32_t>(t_[j] - t_[i]);
            const float f = span > 0 ? static_cast<float>(d) / static_cast<float>(span) : 0.0f;
            *roll = roll_[i] + f * (roll_[j] - roll_[i]);
            *pitch = pitch_[i] + f * (pitch_[j] - pitch_[i]);
            *psi = geo::envolve(psi_[i] + f * geo::envolve(psi_[j] - psi_[i]));
            if (pos != nullptr) {
                for (int32_t e = 0; e < 3; ++e) pos[e] = pos_[i][e] + f * (pos_[j][e] - pos_[i][e]);
            }
            *fora = false;
            return true;
        }
        const int32_t i = indice(n_ - 1);  // t anterior à amostra mais antiga
        *roll = roll_[i];
        *pitch = pitch_[i];
        *psi = psi_[i];
        if (pos != nullptr) {
            for (int32_t e = 0; e < 3; ++e) pos[e] = pos_[i][e];
        }
        *fora = true;
        return true;
    }

    // Soma `d` a TODAS as posições guardadas (o seguidor recentra a odometria para o float32 não perder resolução)
    void transladar(const float d[3]) {
        for (int32_t i = 0; i < kN; ++i) {
            for (int32_t e = 0; e < 3; ++e) pos_[i][e] += d[e];
        }
    }

private:
    // k-ésima amostra mais recente (0 = a última empurrada)
    int32_t indice(int32_t k) const { return (cab_ - 1 - k + 2 * kN) % kN; }

    uint32_t t_[kN];
    float roll_[kN];
    float pitch_[kN];
    float psi_[kN];
    float pos_[kN][3];
    int32_t cab_;
    int32_t n_;
};

// ----------------------------------------------------------------------------------------- filtro do alvo
// Três canais independentes: 0 = azimute inercial α (envolvido em ±π) · 1 = elevação ε · 2 = raio normalizado
// ρ = raio_px/f (≈ R_alvo/distância). Por canal: estado [x, ẋ, ẍ] e covariância 3×3.
//   ALFA_BETA: x⁻ = x + ẋ·dt;  x += α·r;  ẋ += (β/dt)·r.
//   KF_CV / KF_CA: F = [[1,dt,dt²/2],[0,1,dt],[0,0,1]] e ruído de processo branco na ACELERAÇÃO (CV: a ≡ 0,
//        Q = q·[[dt³/3, dt²/2],[dt²/2, dt]]) ou no JERK (CA: Q = q·[[dt⁵/20, dt⁴/8, dt³/6],[dt⁴/8, dt³/3,
//        dt²/2],[dt³/6, dt²/2, dt]]); correção escalar H = [1 0 0] com a forma de Joseph (simétrica e positiva
//        em float32). O CV corre pelo mesmo caminho com a 3.ª linha/coluna de P e x[2] mantidas a zero.
class FiltroAlvo {
public:
    void configurar(int32_t modelo, float alfa, float beta, float q_ang, float q_raio, float sigma_ang,
                    float sigma_raio, float gate_sigma) {
        modelo_ = modelo;
        alfa_ = alfa;
        beta_ = beta;
        q_[0] = q_ang;
        q_[1] = q_ang;
        q_[2] = q_raio;
        r_[0] = sigma_ang * sigma_ang;
        r_[1] = sigma_ang * sigma_ang;
        r_[2] = sigma_raio * sigma_raio;
        gate_ = gate_sigma;
        raio_alvo_ = 0.0f;
        raio_cv_ = false;
        zerar();
    }

    // Com KF_CA, o canal do RAIO (2) passa a velocidade constante (o `q_raio` configurado é então o do CV). Os ângulos
    // medem-se a ~0,1° e aguentam o CA; o raio de um blob pequeno tem ~5 % de ruído e o CA só lhe acrescenta ressonância.
    void raio_em_cv(bool ligado) { raio_cv_ = ligado; }

    // Liga a compensação da translação própria: `raio_alvo_m` > 0 converte o raio normalizado em distância (D = R/ρ);
    // 0 desliga (o `pos` de medir()/prever() é ignorado e o filtro é EXATAMENTE o de sempre).
    void compensar_translacao(float raio_alvo_m) { raio_alvo_ = raio_alvo_m > 0.0f ? raio_alvo_m : 0.0f; }

    void zerar() {
        init_ = false;
        t_ = 0u;
        n_aceites_ = 0;
        rej_seg_ = 0;
        for (int32_t e = 0; e < 3; ++e) ref_[e] = 0.0f;
        for (int32_t c = 0; c < 3; ++c) {
            for (int32_t i = 0; i < 3; ++i) {
                x_[c][i] = 0.0f;
                for (int32_t j = 0; j < 3; ++j) p_[c][i][j] = 0.0f;
            }
        }
    }

    bool inicializado() const { return init_; }
    int32_t n_aceites() const { return n_aceites_; }
    uint32_t t_us() const { return t_; }

    // Resultado de medir(): 0 aceite · 1 recusada pelo gate · 2 ignorada (instante não posterior ao do filtro)
    //                       · 3 filtro (re)iniciado com esta medida
    // `pos` (só com compensar_translacao) = posição PRÓPRIA no instante da captura: o estado propagado é reposto para esse
    // ponto de observação antes da inovação.
    NUCLEO_VISAO_KERNEL int32_t medir(uint32_t t_us, float az, float el, float rho, const float* pos = nullptr) {
        if (!(geo::finito(az) && geo::finito(el) && geo::finito(rho))) return 2;
        const bool comp = raio_alvo_ > 0.0f && pos != nullptr && geo::finito(pos[0]) && geo::finito(pos[1]) &&
                          geo::finito(pos[2]);
        if (!init_) {
            iniciar_com(t_us, az, el, rho);
            if (comp) fixar_ref(pos);
            return 3;
        }
        const int32_t dt_us = static_cast<int32_t>(t_us - t_);
        if (dt_us < alvo_detalhe::kDtMinUs) return 2;  // repetida/fora de ordem/colada à anterior: o α-β dividiria por dt
        const float dt = static_cast<float>(dt_us) * 1e-6f;
        if (dt > alvo_detalhe::kDtMax) {  // medidas demasiado espaçadas: a previsão não vale — recomeça
            iniciar_com(t_us, az, el, rho);
            if (comp) fixar_ref(pos);
            return 3;
        }
        const float z[3] = {az, el, rho};
        // inovação e gate (com a covariância PROPAGADA); só depois se atualiza
        float xp[3][3];
        float pp[3][3][3];
        for (int32_t c = 0; c < 3; ++c) propagar(c, dt, xp[c], pp[c]);
        if (comp) {  // o drone andou entre as duas capturas: o mesmo alvo visto do NOVO ponto de observação
            const float d[3] = {pos[0] - ref_[0], pos[1] - ref_[1], pos[2] - ref_[2]};
            deslocar(d, &xp[0][0], &xp[1][0], &xp[2][0]);
            fixar_ref(pos);
        }
        bool aceita = true;
        for (int32_t c = 0; c < 3; ++c) {
            float y = z[c] - xp[c][0];
            if (c == 0) y = geo::envolve(y);
            const float s = pp[c][0][0] + r_[c];
            if (modelo_ != ALFA_BETA && y * y > gate_ * gate_ * s) aceita = false;
            if (modelo_ == ALFA_BETA) {
                const float sm = alvo_detalhe::sigma_modelo_ab(c);
                if (geo::absf(y) > gate_ * sqrtf(r_[c] + sm * sm)) aceita = false;
            }
        }
        if (!aceita) {
            // o estado fica propagado até t_us; conta recusas seguidas
            for (int32_t c = 0; c < 3; ++c) copiar(c, xp[c], pp[c]);
            t_ = t_us;
            ++rej_seg_;
            if (rej_seg_ >= alvo_detalhe::kRecusasParaReiniciar) {
                iniciar_com(t_us, az, el, rho);
                if (comp) fixar_ref(pos);
                return 3;
            }
            return 1;
        }
        rej_seg_ = 0;
        for (int32_t c = 0; c < 3; ++c) {
            atualizar_canal(c, dt, z[c], xp[c], pp[c]);
        }
        t_ = t_us;
        ++n_aceites_;
        return 0;
    }

    // Previsão (sem alterar o estado) para o instante t_us (≥ t do filtro; antes disso devolve o estado atual):
    // posição, taxa e aceleração dos 3 canais. O azimute sai envolvido. `proprio` (só com compensar_translacao) = posição
    // PRÓPRIA em t_us: a previsão desconta o que o drone andou desde a última captura (as taxas são só do alvo).
    NUCLEO_VISAO_KERNEL void prever(uint32_t t_us, float pos[3], float vel[3], float acc[3],
                                    const float* proprio = nullptr) const {
        int32_t d = static_cast<int32_t>(t_us - t_);
        if (d < 0) d = 0;
        float dt = static_cast<float>(d) * 1e-6f;
        if (dt > alvo_detalhe::kDtPrevMax) dt = alvo_detalhe::kDtPrevMax;
        for (int32_t c = 0; c < 3; ++c) {
            const float* x = x_[c];
            pos[c] = x[0] + x[1] * dt + 0.5f * x[2] * dt * dt;
            vel[c] = x[1] + x[2] * dt;
            acc[c] = x[2];
        }
        if (raio_alvo_ > 0.0f && proprio != nullptr && geo::finito(proprio[0]) && geo::finito(proprio[1]) &&
            geo::finito(proprio[2])) {
            const float dp[3] = {proprio[0] - ref_[0], proprio[1] - ref_[1], proprio[2] - ref_[2]};
            deslocar(dp, &pos[0], &pos[1], &pos[2]);
        }
        pos[0] = geo::envolve(pos[0]);
    }

    // Soma `d` ao ponto de observação guardado (o seguidor recentra a odometria)
    void transladar_ref(const float d[3]) {
        for (int32_t e = 0; e < 3; ++e) ref_[e] += d[e];
    }

    int32_t modelo() const { return modelo_; }

    // o modelo efetivo do canal c (o raio pode ir em CV com os ângulos em CA)
    int32_t modelo_do_canal(int32_t c) const { return (c == 2 && raio_cv_ && modelo_ == KF_CA) ? KF_CV : modelo_; }

    // estado e covariância atuais (diagnóstico/testes)
    float estado(int32_t canal, int32_t i) const { return x_[canal][i]; }
    float cov(int32_t canal, int32_t i, int32_t j) const { return p_[canal][i][j]; }

    bool saudavel() const {
        for (int32_t c = 0; c < 3; ++c) {
            for (int32_t i = 0; i < 3; ++i) {
                if (!geo::finito(x_[c][i])) return false;
                for (int32_t j = 0; j < 3; ++j) {
                    if (!geo::finito(p_[c][i][j])) return false;
                }
            }
        }
        return true;
    }

private:
    void fixar_ref(const float pos[3]) {
        for (int32_t e = 0; e < 3; ++e) ref_[e] = pos[e];
    }

    // O MESMO alvo visto de um ponto de observação deslocado de `d` (m, referencial de arranque): com D = R/ρ,
    //   r = D·(cos ε·cos α, cos ε·sen α, sen ε) − d   ⇒   α' = atan2(r_y, r_x), ε' = atan2(r_z, ‖r_xy‖), ρ' = R/‖r‖.
    // Sem deslocamento, com ρ ≈ 0 ou com o alvo «em cima» do drone (‖r‖ ≈ 0) não mexe em nada.
    void deslocar(const float d[3], float* az, float* el, float* rho) const {
        if (d[0] == 0.0f && d[1] == 0.0f && d[2] == 0.0f) return;
        if (!(*rho > alvo_detalhe::kRhoMinDesloca)) return;
        const float dist = raio_alvo_ / *rho;
        const float ce = cosf(*el);
        const float rx = dist * ce * cosf(*az) - d[0];
        const float ry = dist * ce * sinf(*az) - d[1];
        const float rz = dist * sinf(*el) - d[2];
        const float rh = sqrtf(rx * rx + ry * ry);
        const float n = sqrtf(rx * rx + ry * ry + rz * rz);
        if (!(n > alvo_detalhe::kDistMinDesloca) || !geo::finito(n)) return;
        *az = atan2f(ry, rx);
        *el = atan2f(rz, rh);
        *rho = raio_alvo_ / n;
    }

    void iniciar_com(uint32_t t_us, float az, float el, float rho) {
        const float z[3] = {az, el, rho};
        // incerteza inicial da taxa e da aceleração (rad/s, rad/s²; ρ: 1/s)
        const float sv[3] = {1.0f, 1.0f, 0.1f};
        const float sa[3] = {3.0f, 3.0f, 0.3f};
        for (int32_t c = 0; c < 3; ++c) {
            x_[c][0] = z[c];
            x_[c][1] = 0.0f;
            x_[c][2] = 0.0f;
            for (int32_t i = 0; i < 3; ++i) {
                for (int32_t j = 0; j < 3; ++j) p_[c][i][j] = 0.0f;
            }
            p_[c][0][0] = r_[c];
            p_[c][1][1] = sv[c] * sv[c];
            if (modelo_do_canal(c) == KF_CA) p_[c][2][2] = sa[c] * sa[c];
        }
        x_[0][0] = geo::envolve(x_[0][0]);
        t_ = t_us;
        init_ = true;
        rej_seg_ = 0;
        n_aceites_ = 1;
    }

    void copiar(int32_t c, const float x[3], const float p[3][3]) {
        for (int32_t i = 0; i < 3; ++i) {
            x_[c][i] = x[i];
            for (int32_t j = 0; j < 3; ++j) p_[c][i][j] = p[i][j];
        }
        if (c == 0) x_[0][0] = geo::envolve(x_[0][0]);
    }

    // x⁻ = F·x e P⁻ = F·P·Fᵀ + Q para o canal c (sem tocar no estado)
    void propagar(int32_t c, float dt, float xo[3], float po[3][3]) const {
        const float* x = x_[c];
        const float dt2 = dt * dt;
        const int32_t modelo_c = modelo_do_canal(c);
        if (modelo_c == ALFA_BETA) {
            xo[0] = x[0] + x[1] * dt;
            xo[1] = x[1];
            xo[2] = 0.0f;
            for (int32_t i = 0; i < 3; ++i) {
                for (int32_t j = 0; j < 3; ++j) po[i][j] = 0.0f;
            }
            po[0][0] = r_[c];  // o α-β não propaga covariância: só para o gate
            return;
        }
        xo[0] = x[0] + x[1] * dt + 0.5f * x[2] * dt2;
        xo[1] = x[1] + x[2] * dt;
        xo[2] = x[2];
        const float f[3][3] = {{1.0f, dt, 0.5f * dt2}, {0.0f, 1.0f, dt}, {0.0f, 0.0f, 1.0f}};
        float fp[3][3];
        for (int32_t i = 0; i < 3; ++i) {
            for (int32_t j = 0; j < 3; ++j) {
                fp[i][j] = f[i][0] * p_[c][0][j] + f[i][1] * p_[c][1][j] + f[i][2] * p_[c][2][j];
            }
        }
        for (int32_t i = 0; i < 3; ++i) {
            for (int32_t j = 0; j < 3; ++j) {
                po[i][j] = fp[i][0] * f[j][0] + fp[i][1] * f[j][1] + fp[i][2] * f[j][2];
            }
        }
        const float q = q_[c];
        const float dt3 = dt2 * dt;
        if (modelo_c == KF_CA) {
            const float dt4 = dt3 * dt;
            const float dt5 = dt4 * dt;
            po[0][0] += q * dt5 / 20.0f;
            po[0][1] += q * dt4 / 8.0f;
            po[1][0] += q * dt4 / 8.0f;
            po[0][2] += q * dt3 / 6.0f;
            po[2][0] += q * dt3 / 6.0f;
            po[1][1] += q * dt3 / 3.0f;
            po[1][2] += q * dt2 / 2.0f;
            po[2][1] += q * dt2 / 2.0f;
            po[2][2] += q * dt;
        } else {  // CV: aceleração branca
            po[0][0] += q * dt3 / 3.0f;
            po[0][1] += q * dt2 / 2.0f;
            po[1][0] += q * dt2 / 2.0f;
            po[1][1] += q * dt;
        }
    }

    // correção escalar (H = [1 0 0]) a partir do estado/covariância propagados
    void atualizar_canal(int32_t c, float dt, float z, const float xp[3], const float pp[3][3]) {
        float y = z - xp[0];
        if (c == 0) y = geo::envolve(y);
        const int32_t modelo_c = modelo_do_canal(c);
        if (modelo_c == ALFA_BETA) {
            x_[c][0] = xp[0] + alfa_ * y;
            x_[c][1] = xp[1] + (beta_ / dt) * y;
            x_[c][2] = 0.0f;
            if (c == 0) x_[0][0] = geo::envolve(x_[0][0]);
            return;
        }
        const float s = pp[0][0] + r_[c];
        const float inv_s = 1.0f / s;
        float k[3];
        for (int32_t i = 0; i < 3; ++i) k[i] = pp[i][0] * inv_s;
        for (int32_t i = 0; i < 3; ++i) x_[c][i] = xp[i] + k[i] * y;
        // Joseph: P' = (I − K·H)·P·(I − K·H)ᵀ + K·R·Kᵀ, com A = I − K·e0ᵀ
        float a[3][3];
        float t[3][3];
        for (int32_t i = 0; i < 3; ++i) {
            for (int32_t j = 0; j < 3; ++j) a[i][j] = (i == j ? 1.0f : 0.0f) - (j == 0 ? k[i] : 0.0f);
        }
        for (int32_t i = 0; i < 3; ++i) {
            for (int32_t j = 0; j < 3; ++j) t[i][j] = a[i][0] * pp[0][j] + a[i][1] * pp[1][j] + a[i][2] * pp[2][j];
        }
        for (int32_t i = 0; i < 3; ++i) {
            for (int32_t j = 0; j < 3; ++j) {
                p_[c][i][j] = t[i][0] * a[j][0] + t[i][1] * a[j][1] + t[i][2] * a[j][2] + r_[c] * k[i] * k[j];
            }
        }
        for (int32_t i = 0; i < 3; ++i) {  // simetria exata e diagonal não negativa
            for (int32_t j = i + 1; j < 3; ++j) {
                const float m = 0.5f * (p_[c][i][j] + p_[c][j][i]);
                p_[c][i][j] = m;
                p_[c][j][i] = m;
            }
            if (p_[c][i][i] < 0.0f) p_[c][i][i] = 0.0f;
        }
        if (modelo_c == KF_CV) {  // a 3.ª componente fica a zero
            x_[c][2] = 0.0f;
            for (int32_t i = 0; i < 3; ++i) {
                p_[c][2][i] = 0.0f;
                p_[c][i][2] = 0.0f;
            }
        }
        if (c == 0) x_[0][0] = geo::envolve(x_[0][0]);
    }

    int32_t modelo_;
    float alfa_;
    float beta_;
    float q_[3];
    float r_[3];
    float gate_;
    float raio_alvo_;  // m — > 0 liga a compensação da translação própria (D = raio_alvo_/ρ)
    bool raio_cv_;     // o canal do raio em CV (com os ângulos em CA)
    float ref_[3];     // m — posição própria (ponto de observação) a que o estado se refere
    bool init_;
    uint32_t t_;
    int32_t n_aceites_;
    int32_t rej_seg_;
    float x_[3][3];
    float p_[3][3][3];
};

}  // namespace visao
}  // namespace nucleo
