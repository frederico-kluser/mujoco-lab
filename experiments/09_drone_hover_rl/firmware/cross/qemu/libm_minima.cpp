// firmware/cross/qemu/libm_minima.cpp — sinf, cosf e atan2f SEM libm (só aritmética float32), para as imagens bare-metal do QEMU
// e para o host «mínimo» (shim/math.h). Ficam bit a bit IGUAIS no host x86-64 e no Cortex-M4/M7 (IEEE float32, sem FMA:
// compilar com -ffp-contract=off), que é o que o `qemu_alvo.py` precisa para comparar host ≡ alvo bit a bit.
//
// Algoritmos da literatura, REIMPLEMENTADOS (nenhum código de glibc/newlib/musl/FreeBSD/Cephes):
//   · redução de argumento de Cody & Waite, «Software Manual for the Elementary Functions», Prentice-Hall, 1980: n = arred(x·2/π),
//     r = (((x − n·C1) − n·C2) − n·C3) − n·C4 com π/2 = C1 + C2 + C3 + C4 e C1..C3 com poucos bits (n·C exato em float32);
//   · sin/cos em |r| ≤ π/4 por polinómios em r² (interpolação de Chebyshev, quase minimax; Trefethen, «Approximation Theory and
//     Approximation Practice», SIAM, 2013); atan em |u| ≤ tan(π/8) após a redução atan(t) = π/4 + atan((t−1)/(t+1)).
// Os coeficientes saem de `gerar_coeficientes_libm.py` (ao lado; reprodutível).
//
// DOMÍNIO: sin/cos para |x| < 1e5 rad (acima: devolvem NaN — uma redução de Payne–Hanek não cabe aqui; o núcleo só os chama com
// ângulos de atitude, |x| ≲ 4π); atan2f em todo o domínio, incl. ±0, ±inf e NaN (propaga NaN). Erro medido vs glibc em
// `qemu_alvo.py auto-teste` (≤ 2 ULP).
#include <stdint.h>

#include "shim/math.h"

namespace {

constexpr float kCW1 = 1.5703125f;           // π/2 = CW1 + CW2 + CW3 + CW4, com CW1..CW3 de poucos bits (n·C exato)
constexpr float kCW2 = 0.000483751297f;
constexpr float kCW3 = 7.54953362e-08f;
constexpr float kCW4 = 2.56334407e-12f;
constexpr float kDoisSobrePi = 0.636619747f;
constexpr float kSin[4] = {-0.166666672f, 0.00833333191f, -0.00019840039f, 2.72438115e-06f};
constexpr float kCos[4] = {0.0416666679f, -0.00138888881f, 2.48005599e-05f, -2.72958573e-07f};
constexpr float kAtan[6] = {-0.333333343f, 0.19999975f, -0.142840356f, 0.110692434f, -0.0860901326f, 0.0500812344f};
constexpr float kTanPi8 = 0.414213568f;
constexpr float kPi = 3.14159265358979323846f;
constexpr float kPiMeio = 1.57079632679489661923f;
constexpr float kPiQuartoHi = 0.785398185f;  // π/4 = hi + lo (a soma final do atan2 perde menos com os dois)
constexpr float kPiQuartoLo = -2.18556941e-08f;
constexpr float kDominioTrig = 1.0e5f;

inline uint32_t bits(float x) {
    uint32_t u;
    __builtin_memcpy(&u, &x, sizeof(u));
    return u;
}
inline float de_bits(uint32_t u) {
    float x;
    __builtin_memcpy(&x, &u, sizeof(x));
    return x;
}
inline float absf(float x) { return de_bits(bits(x) & 0x7FFFFFFFu); }
inline bool eh_nan(float x) { return x != x; }
inline bool eh_neg(float x) { return (bits(x) >> 31) != 0u; }

inline float sin_poli(float r) {  // |r| ≤ π/4
    const float z = r * r;
    return r + r * z * (kSin[0] + z * (kSin[1] + z * (kSin[2] + z * kSin[3])));
}
inline float cos_poli(float r) {
    const float z = r * r;
    return 1.0f - 0.5f * z + z * z * (kCos[0] + z * (kCos[1] + z * (kCos[2] + z * kCos[3])));
}

// x → (quadrante n mod 4, resto r em [−π/4, π/4])
inline int32_t reduz(float x, float* r) {
    const float k = x * kDoisSobrePi;
    const int32_t n = static_cast<int32_t>(k + (k < 0.0f ? -0.5f : 0.5f));  // arredonda ao inteiro mais próximo
    const float nf = static_cast<float>(n);
    *r = (((x - nf * kCW1) - nf * kCW2) - nf * kCW3) - nf * kCW4;
    return n & 3;
}

inline float atan_01(float t) {  // t ∈ [0, 1]
    const bool red = t > kTanPi8;
    const float u = red ? (t - 1.0f) / (t + 1.0f) : t;
    const float z = u * u;
    const float p = kAtan[0] + z * (kAtan[1] + z * (kAtan[2] + z * (kAtan[3] + z * (kAtan[4] + z * kAtan[5]))));
    const float a = u + u * z * p;
    return red ? (a + kPiQuartoLo) + kPiQuartoHi : a;
}

}  // namespace

extern "C" {

float nucleo_sinf(float x) {
    if (!(absf(x) < kDominioTrig)) return x - x;  // NaN para ±inf, NaN e fora do domínio
    float r;
    const int32_t q = reduz(x, &r);
    switch (q) {
        case 0: return sin_poli(r);
        case 1: return cos_poli(r);
        case 2: return -sin_poli(r);
        default: return -cos_poli(r);
    }
}

float nucleo_cosf(float x) {
    if (!(absf(x) < kDominioTrig)) return x - x;
    float r;
    const int32_t q = reduz(x, &r);
    switch (q) {
        case 0: return cos_poli(r);
        case 1: return -sin_poli(r);
        case 2: return -cos_poli(r);
        default: return sin_poli(r);
    }
}

float nucleo_atan2f(float y, float x) {
    if (eh_nan(y) || eh_nan(x)) return y + x;
    const float ay = absf(y);
    const float ax = absf(x);
    const bool y_neg = eh_neg(y);
    const bool x_neg = eh_neg(x);
    float a;
    if (ay == 0.0f && ax == 0.0f) {
        a = x_neg ? kPi : 0.0f;  // atan2(±0, +0) = ±0 ; atan2(±0, −0) = ±π
    } else {
        const bool y_inf = ay > 3.4028235e38f;
        const bool x_inf = ax > 3.4028235e38f;
        float t;
        bool troca;
        if (y_inf && x_inf) {
            t = 1.0f;
            troca = false;
        } else {
            troca = ay > ax;
            t = troca ? ax / ay : ay / ax;
        }
        a = atan_01(t);
        if (troca) a = kPiMeio - a;
        if (x_neg) a = kPi - a;
    }
    return y_neg ? -a : a;
}

}  // extern "C"
