/* firmware/cross/math.h — SUBSTITUTO MÍNIMO de <math.h>, SÓ para a verificação de compilação cruzada.
 *
 * O clang não traz libc para alvos bare-metal e esta máquina não tem o sysroot ARM (newlib), por isso o
 * `-isystem firmware/cross` do teste_nucleo.py injeta ESTE cabeçalho para o `#include <math.h>` do núcleo
 * resolver. Declara APENAS as funções em precisão simples que o núcleo usa, com os protótipos padrão do
 * C99 (idênticos aos do newlib/Arduino). Na toolchain real (Arduino IDE, arm-none-eabi-gcc) vale o
 * <math.h> verdadeiro e estas declarações NÃO são usadas. Se o núcleo passar a precisar de outra função,
 * a compilação cruzada falha aqui — acrescente-a conscientemente (e é uma dependência nova de libm).
 */
#ifndef NUCLEO_CROSS_MATH_H
#define NUCLEO_CROSS_MATH_H

#ifdef __cplusplus
extern "C" {
#endif

float sinf(float x);
float cosf(float x);
float atan2f(float y, float x);
float sqrtf(float x);

#ifdef __cplusplus
}
#endif

#endif /* NUCLEO_CROSS_MATH_H */
