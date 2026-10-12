// firmware/cross/qemu/testa_libm.cpp — mede o erro em ULP da libm_minima.cpp (sinf, cosf, atan2f SEM libm) contra a glibc do host.
// Compilar: g++ -O2 -ffp-contract=off -fno-math-errno testa_libm.cpp libm_minima.cpp -I . -o testa_libm   (a libm_minima usa shim/math.h)
// Grelha densa de 4 000 001 pontos em [-100, 100] rad para sin/cos e 4 000 000 pares aleatórios (±84 em passos de 1e-5) para atan2.
#include <stdio.h>
#include <math.h>  // glibc (o shim só vale para a libm_minima.cpp)
extern "C" { float nucleo_sinf(float); float nucleo_cosf(float); float nucleo_atan2f(float, float); }
#include <stdint.h>
#include <string.h>
static int32_t ordem(float x) { int32_t i; memcpy(&i, &x, 4); return i < 0 ? (int32_t)0x80000000u - i : i; }
static double ulp(float a, float b) { if (a == b) return 0; return (double)(ordem(a) > ordem(b) ? ordem(a) - ordem(b) : ordem(b) - ordem(a)); }
int main() {
    double ms = 0, mc = 0, ma = 0; float xs = 0, xc = 0, ya = 0, xa = 0;
    for (long i = -2000000; i <= 2000000; ++i) {
        float x = (float)i * (100.0f / 2000000.0f);
        double d = ulp(nucleo_sinf(x), sinf(x)); if (d > ms) { ms = d; xs = x; }
        d = ulp(nucleo_cosf(x), cosf(x)); if (d > mc) { mc = d; xc = x; }
    }
    uint64_t s = 88172645463325252ull;
    for (long i = 0; i < 4000000; ++i) {
        s ^= s << 13; s ^= s >> 7; s ^= s << 17;
        float y = ((int32_t)(s & 0xFFFFFF) - 8388608) * (1.0f / 100000.0f);
        float x = ((int32_t)((s >> 24) & 0xFFFFFF) - 8388608) * (1.0f / 100000.0f);
        double d = ulp(nucleo_atan2f(y, x), atan2f(y, x)); if (d > ma) { ma = d; ya = y; xa = x; }
    }
    printf("sin max ULP %.1f (x=%g) · cos %.1f (x=%g) · atan2 %.1f (y=%g x=%g)\n", ms, xs, mc, xc, ma, ya, xa);
}
