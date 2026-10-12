// firmware/teste/estresse.cpp — driver de ESTRESSE do núcleo, SÓ para o host (corre com ASan + UBSan).
//
// Não faz parte do firmware: usa <stdio.h>/<stdlib.h>. É compilado e executado pelo teste_nucleo.py contra
// a MESMA fonte do núcleo (nucleo/nucleo.cpp) com -fsanitize=address,undefined -fno-sanitize-recover=all.
// Dá ao núcleo milhões de entradas hostis — sensores aleatórios, extremos (±1e30), NaN/±inf, dt inválido,
// modos inexistentes, reinícios, armar/desarmar e calibrações em momentos aleatórios — e confere os
// INVARIANTES que o firmware tem de garantir sempre:
//   · cada motor é finito e está em [0, 1];
//   · armado e sem falha numérica ⇒ cada motor ∈ [idle, 1];
//   · as 9 estimativas são finitas (um estimador corrompido recalibra-se);
//   · desarmado ⇒ motores a 0.
// Uso: estresse <config.bin> <passos>      (config.bin = bytes de uma nucleo::Config válida)
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "nucleo/nucleo.hpp"

namespace {

uint64_t g_estado = 0x9E3779B97F4A7C15ull;

uint32_t proximo() {  // xorshift64*
    g_estado ^= g_estado >> 12;
    g_estado ^= g_estado << 25;
    g_estado ^= g_estado >> 27;
    return static_cast<uint32_t>((g_estado * 0x2545F4914F6CDD1Dull) >> 32);
}

float uniforme(float lo, float hi) {
    return lo + (hi - lo) * (static_cast<float>(proximo()) / 4294967296.0f);
}

// valor "hostil": NaN, ±inf, ±1e30 e ±1e38 (quase o máximo de float) com pequena probabilidade
float hostil(float lo, float hi) {
    switch (proximo() % 400u) {
        case 0: return NAN;
        case 1: return INFINITY;
        case 2: return -INFINITY;
        case 3: return 1e30f;
        case 4: return -1e30f;
        case 5: return 3.0e38f;
        case 6: return -3.0e38f;
        default: return uniforme(lo, hi);
    }
}

int32_t incrementa(int32_t n) { return static_cast<int32_t>(static_cast<uint32_t>(n) + 1u); }

}  // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        fprintf(stderr, "uso: estresse <config.bin> <passos>\n");
        return 2;
    }
    static nucleo::Config cfg;
    FILE* f = fopen(argv[1], "rb");
    if (f == nullptr || fread(&cfg, 1, sizeof(cfg), f) != sizeof(cfg)) {
        fprintf(stderr, "estresse: config.bin ilegível ou de tamanho errado (esperado %zu B)\n", sizeof(cfg));
        return 2;
    }
    fclose(f);
    const long passos = atol(argv[2]);

    static nucleo::Nucleo n;  // estático, como no firmware
    if (!n.iniciar(cfg)) {
        fprintf(stderr, "estresse: o núcleo recusou a Config\n");
        return 3;
    }
    const float dts[8] = {0.002f, 0.002f, 0.002f, 0.001f, 0.0f, -1.0f, NAN, 10.0f};

    nucleo::Sensores s = {};
    nucleo::Comando c = {};
    long violacoes = 0, falhas = 0, armados = 0, reservados = 0, desarmados = 0, calibracoes = 0;
    for (long k = 0; k < passos; ++k) {
        if (proximo() % 997u == 0u) n.reiniciar();
        if (proximo() % 53u == 0u) n.armar(proximo() % 4u != 0u);
        if (proximo() % 5003u == 0u) {
            n.calibrar(s);
            ++calibracoes;
        }
        const bool pico = (proximo() % 40u) == 0u;  // 2,5 % dos passos com entradas hostis
        for (int e = 0; e < 3; ++e) {
            s.giro[e] = pico ? hostil(-60.0f, 60.0f) : uniforme(-4.0f, 4.0f);
            s.acc[e] = pico ? hostil(-100.0f, 100.0f) : uniforme(-15.0f, 15.0f);
            c.taxas[e] = pico ? hostil(-100.0f, 100.0f) : uniforme(-2.0f, 2.0f);
        }
        s.acc[2] = pico ? hostil(-100.0f, 100.0f) : uniforme(5.0f, 12.0f);
        s.tof_d = pico ? hostil(-1.0f, 5.0f) : uniforme(0.0f, 4.0f);
        s.tof_ok = static_cast<int32_t>(proximo() & 1u);
        s.fluxo_ok = static_cast<int32_t>(proximo() & 1u);
        for (int e = 0; e < 2; ++e) s.fluxo[e] = pico ? hostil(-10.0f, 10.0f) : uniforme(-3.0f, 3.0f);
        if (proximo() % 3u == 0u) s.n_tof = incrementa(s.n_tof);
        if (proximo() % 2u == 0u) s.n_fluxo = incrementa(s.n_fluxo);
        s.v_bat = uniforme(0.0f, 26.0f);
        const uint32_t modo = proximo() % 8u;
        c.modo = static_cast<nucleo::Modo>(modo < 5u ? 0 : static_cast<int32_t>(modo * 11u));  // 0 = CTBR; resto inexistente
        c.coletivo = pico ? hostil(-3.0f, 4.0f) : uniforme(-0.5f, 1.5f);
        c.vx = c.vy = c.vz = c.yaw_taxa = uniforme(-1.0f, 1.0f);

        const nucleo::Saida o = n.passo(s, c, dts[proximo() % 8u]);

        bool ruim = false;
        for (int i = 0; i < 4; ++i) ruim = ruim || !(o.motor[i] >= 0.0f && o.motor[i] <= 1.0f);  // NaN também falha
        const bool armado = (o.flags & nucleo::kFlagArmado) != 0;
        const bool falha = (o.flags & nucleo::kFlagFalhaNumerica) != 0;
        if (armado && !falha) {
            for (int i = 0; i < 4; ++i) ruim = ruim || o.motor[i] < cfg.idle - 1e-6f;
        }
        if (!armado) {
            for (int i = 0; i < 4; ++i) ruim = ruim || o.motor[i] != 0.0f;
            ++desarmados;
        }
        const float est[9] = {o.roll, o.pitch, o.psi, o.h, o.vz, o.vx, o.vy, o.x, o.y};
        for (int i = 0; i < 9; ++i) ruim = ruim || !nucleo::e_finito(est[i]);
        if (ruim) {
            if (violacoes < 5) fprintf(stderr, "estresse: violação no passo %ld (flags %d)\n", k, o.flags);
            ++violacoes;
        }
        if (falha) ++falhas;
        if (armado) ++armados;
        if ((o.flags & nucleo::kFlagModoReservado) != 0) ++reservados;
    }
    printf("estresse: %ld passos · violações %ld · falhas numéricas sinalizadas %ld · passos armados %ld · "
           "desarmados %ld · modo reservado %ld · calibrações explícitas %ld\n",
           passos, violacoes, falhas, armados, desarmados, reservados, calibracoes);
    return violacoes == 0 ? 0 : 1;
}
