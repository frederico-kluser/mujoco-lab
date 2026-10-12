/* firmware/cross/qemu/shim/math.h — <math.h> do harness QEMU/host «sem libm»: as 4 funções que o núcleo usa passam a
 * `nucleo_*` (libm_minima.cpp, sem libm) e o sqrtf é a instrução da FPU (vsqrt.f32 / sqrtss, exatamente arredondada).
 *
 * SÓ para as imagens do `qemu_alvo.py` e o host «mínimo» (`-isystem shim`): a MESMA fonte do núcleo (que faz
 * `#include <math.h>` e chama sinf/cosf/atan2f/sqrtf) compila com este cabeçalho em vez do da libm. Os nomes são renomeados para
 * que o compilador não os trate como funções da biblioteca padrão (nada de constant-folding, nada de intrínsecos que variem
 * entre alvos) e para não colidirem com a glibc no host. NÃO é o <math.h> do firmware real (esse é o do newlib/Arduino; ver
 * ../math.h, o substituto mínimo da compilação cruzada).
 * Compilar com -fno-math-errno (o sqrtf é inline) e -ffp-contract=off.
 */
#ifndef NUCLEO_QEMU_SHIM_MATH_H
#define NUCLEO_QEMU_SHIM_MATH_H

#ifdef __cplusplus
extern "C" {
#endif

float nucleo_sinf(float x);
float nucleo_cosf(float x);
float nucleo_atan2f(float y, float x);

#ifdef __cplusplus
}
#endif

#define sinf nucleo_sinf
#define cosf nucleo_cosf
#define atan2f nucleo_atan2f
#define sqrtf nucleo_sqrtf

static inline float nucleo_sqrtf(float x) { return __builtin_sqrtf(x); }

#endif /* NUCLEO_QEMU_SHIM_MATH_H */
