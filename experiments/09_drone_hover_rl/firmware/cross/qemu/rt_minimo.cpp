// firmware/cross/qemu/rt_minimo.cpp — runtime mínimo bare-metal: memcpy/memset/memmove/memcmp e os auxiliares __aeabi_mem* que o
// clang pede ao copiar/zerar structs (o núcleo devolve `Saida` por valor). Compilar com -ffreestanding (sem reconhecimento de idiomas:
// senão o compilador transformaria estes laços em chamadas a si próprios).
#include <stdint.h>

extern "C" {

void* memcpy(void* dst, const void* src, unsigned long n) {
    uint8_t* d = static_cast<uint8_t*>(dst);
    const uint8_t* s = static_cast<const uint8_t*>(src);
    while (n--) *d++ = *s++;
    return dst;
}

void* memmove(void* dst, const void* src, unsigned long n) {
    uint8_t* d = static_cast<uint8_t*>(dst);
    const uint8_t* s = static_cast<const uint8_t*>(src);
    if (d < s) {
        while (n--) *d++ = *s++;
    } else {
        d += n;
        s += n;
        while (n--) *--d = *--s;
    }
    return dst;
}

void* memset(void* dst, int c, unsigned long n) {
    uint8_t* d = static_cast<uint8_t*>(dst);
    while (n--) *d++ = static_cast<uint8_t>(c);
    return dst;
}

int memcmp(const void* a, const void* b, unsigned long n) {
    const uint8_t* x = static_cast<const uint8_t*>(a);
    const uint8_t* y = static_cast<const uint8_t*>(b);
    for (; n; --n, ++x, ++y) {
        if (*x != *y) return *x < *y ? -1 : 1;
    }
    return 0;
}

// ABI de runtime do ARM (EABI): a variante com alinhamento é a mesma coisa para os nossos fins
void __aeabi_memcpy(void* d, const void* s, unsigned long n) { memcpy(d, s, n); }
void __aeabi_memcpy4(void* d, const void* s, unsigned long n) { memcpy(d, s, n); }
void __aeabi_memcpy8(void* d, const void* s, unsigned long n) { memcpy(d, s, n); }
void __aeabi_memmove(void* d, const void* s, unsigned long n) { memmove(d, s, n); }
void __aeabi_memmove4(void* d, const void* s, unsigned long n) { memmove(d, s, n); }
void __aeabi_memmove8(void* d, const void* s, unsigned long n) { memmove(d, s, n); }
// atenção: __aeabi_memset tem os argumentos (dst, n, c) — n antes de c
void __aeabi_memset(void* d, unsigned long n, int c) { memset(d, c, n); }
void __aeabi_memset4(void* d, unsigned long n, int c) { memset(d, c, n); }
void __aeabi_memset8(void* d, unsigned long n, int c) { memset(d, c, n); }
void __aeabi_memclr(void* d, unsigned long n) { memset(d, 0, n); }
void __aeabi_memclr4(void* d, unsigned long n) { memset(d, 0, n); }
void __aeabi_memclr8(void* d, unsigned long n) { memset(d, 0, n); }

}  // extern "C"
