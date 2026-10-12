// firmware/teste/estresse_cascata.cpp — ESTRESSE da INTERFACE 2 (cascata, estimador clássico, IBVS) só para o host (ASan + UBSan).
//
// O estresse.cpp da atividade A martela o caminho CTBR; este martela os modos VELOCIDADE / YAW_ALVO / OLHAR e a calibração no chão:
// entradas hostis (NaN, ±inf, ±1e30), dt inválido, relógio do MCU a saltar/voltar, câmara com valores absurdos, mudanças de modo,
// armar/desarmar/reiniciar/calibrar_chao/travar_referencias em momentos aleatórios, e o passo partido (planear + atuar).
// INVARIANTES do firmware (sempre): motores finitos em [0,1] (≥ idle se armado sem falha; 0 desarmado); as 9 estimativas finitas;
// coletivo/acelerador/taxas_ref/v_ref/yaw_taxa_ref finitos e limitados (taxas_ref ≤ taxa_rp_max/taxa_yaw_max, acelerador ∈ [0,1]);
// a saída do seguidor finita; v_ref dentro de ±max. Uso: estresse_cascata <config.bin> <passos>   (config.bin = nucleo::Config
// com usa_cascata = 1, usa_visao = 1 e estimador_classico = 1)
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "nucleo/nucleo.hpp"

namespace {

uint64_t g_estado = 0x243F6A8885A308D3ull;

uint32_t proximo() {  // xorshift64*
    g_estado ^= g_estado >> 12;
    g_estado ^= g_estado << 25;
    g_estado ^= g_estado >> 27;
    return static_cast<uint32_t>((g_estado * 0x2545F4914F6CDD1Dull) >> 32);
}

float uniforme(float lo, float hi) { return lo + (hi - lo) * (static_cast<float>(proximo()) / 4294967296.0f); }

float hostil(float lo, float hi) {
    switch (proximo() % 300u) {
        case 0: return NAN;
        case 1: return INFINITY;
        case 2: return -INFINITY;
        case 3: return 1e30f;
        case 4: return -1e30f;
        case 5: return 3.0e38f;
        case 6: return -3.0e38f;
        case 7: return 1e-30f;
        default: return uniforme(lo, hi);
    }
}

int32_t incrementa(int32_t n) { return static_cast<int32_t>(static_cast<uint32_t>(n) + 1u); }

bool finito(float x) { return nucleo::e_finito(x); }

}  // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        fprintf(stderr, "uso: estresse_cascata <config.bin> <passos>\n");
        return 2;
    }
    static nucleo::Config cfg;
    FILE* f = fopen(argv[1], "rb");
    if (f == nullptr || fread(&cfg, 1, sizeof(cfg), f) != sizeof(cfg)) {
        fprintf(stderr, "estresse_cascata: config.bin ilegível ou de tamanho errado (esperado %zu B)\n", sizeof(cfg));
        return 2;
    }
    fclose(f);
    const long passos = atol(argv[2]);
    static nucleo::Nucleo n;
    if (!n.iniciar(cfg)) {
        fprintf(stderr, "estresse_cascata: o núcleo recusou a Config\n");
        return 3;
    }
    const nucleo::ConfigCascata& g = cfg.cascata;
    const float dts[8] = {0.002f, 0.002f, 0.002f, 0.001f, 0.0f, -1.0f, NAN, 10.0f};
    const nucleo::Modo modos[6] = {nucleo::CTBR, nucleo::VELOCIDADE, nucleo::VELOCIDADE, nucleo::YAW_ALVO, nucleo::OLHAR, nucleo::OLHAR};

    nucleo::Sensores s = {};
    nucleo::Comando c = {};
    uint32_t t_us = 0u;
    long violacoes = 0, falhas = 0, armados = 0, olhar = 0, decisoes = 0, estados[4] = {0, 0, 0, 0}, sat_yaw = 0;
    for (long k = 0; k < passos; ++k) {
        if (proximo() % 1499u == 0u) n.reiniciar();
        if (proximo() % 61u == 0u) n.armar(proximo() % 5u != 0u);
        if (proximo() % 997u == 0u) n.calibrar_chao(proximo() % 2u == 0u);
        if (proximo() % 811u == 0u) n.travar_referencias(proximo() % 2u == 0u, hostil(0.0f, 3.0f));
        if (proximo() % 5003u == 0u) n.calibrar(s);
        const bool pico = (proximo() % 40u) == 0u;
        for (int e = 0; e < 3; ++e) {
            s.giro[e] = pico ? hostil(-60.0f, 60.0f) : uniforme(-1.0f, 1.0f);
            s.acc[e] = pico ? hostil(-100.0f, 100.0f) : uniforme(-2.0f, 2.0f);
            c.taxas[e] = pico ? hostil(-100.0f, 100.0f) : uniforme(-2.0f, 2.0f);
        }
        s.acc[2] = pico ? hostil(-100.0f, 100.0f) : uniforme(8.0f, 11.0f);
        s.tof_d = pico ? hostil(-1.0f, 5.0f) : uniforme(0.2f, 3.5f);
        s.tof_ok = static_cast<int32_t>(proximo() % 8u != 0u);
        s.fluxo_ok = static_cast<int32_t>(proximo() % 8u != 0u);
        for (int e = 0; e < 2; ++e) s.fluxo[e] = pico ? hostil(-10.0f, 10.0f) : uniforme(-1.0f, 1.0f);
        if (proximo() % 3u == 0u) s.n_tof = incrementa(s.n_tof);
        if (proximo() % 2u == 0u) s.n_fluxo = incrementa(s.n_fluxo);
        s.v_bat = pico ? hostil(0.0f, 26.0f) : uniforme(17.0f, 26.0f);
        // relógio do MCU: avança 2 ms, às vezes salta ou VOLTA (o seguidor tem de aguentar)
        const uint32_t r = proximo() % 500u;
        t_us += r == 0u ? 5000000u : (r == 1u ? 0xFFFFF000u : 2000u);
        s.t_us = t_us;
        // câmara: frame novo a ~30 Hz, valores plausíveis ou absurdos
        if (proximo() % 17u == 0u) {
            s.camera.n = incrementa(s.camera.n);
            s.camera.valido = static_cast<int32_t>(proximo() % 6u != 0u);
            s.camera.u = pico ? hostil(-500.0f, 800.0f) : uniforme(20.0f, 300.0f);
            s.camera.v = pico ? hostil(-500.0f, 800.0f) : uniforme(20.0f, 220.0f);
            s.camera.raio = pico ? hostil(-5.0f, 50.0f) : uniforme(2.0f, 25.0f);
            s.camera.t = proximo() % 40u == 0u ? proximo() : t_us - 116000u;
        }
        const uint32_t m = proximo() % 40u;
        c.modo = static_cast<nucleo::Modo>(m < 36u ? modos[m % 6u] : static_cast<int32_t>(m * 13u));  // 36–39: inexistentes
        c.coletivo = pico ? hostil(-3.0f, 4.0f) : uniforme(-0.5f, 1.5f);
        c.vx = pico ? hostil(-3.0f, 3.0f) : uniforme(-1.5f, 1.5f);
        c.vy = pico ? hostil(-3.0f, 3.0f) : uniforme(-1.5f, 1.5f);
        c.vz = pico ? hostil(-3.0f, 3.0f) : uniforme(-1.0f, 1.0f);
        c.yaw_taxa = pico ? hostil(-5.0f, 5.0f) : uniforme(-2.0f, 2.0f);
        c.yaw = pico ? hostil(-100.0f, 100.0f) : uniforme(-6.0f, 6.0f);
        c.z_alvo = pico ? hostil(0.0f, 5.0f) : uniforme(0.0f, 4.0f);
        c.tem_z_alvo = static_cast<int32_t>(proximo() % 11u == 0u);

        const float dt = dts[proximo() % 8u];
        nucleo::Saida o;
        if (proximo() % 4u == 0u) {  // o passo partido (planear + atuar) tem de dar o mesmo tipo de garantias
            o = nucleo::Saida();
            const nucleo::ReferenciasTaxa ref = n.planear(s, c, dt, o);
            n.atuar(ref, s, dt, o);
        } else {
            o = n.passo(s, c, dt);
        }

        bool ruim = false;
        int motivo = 0;
#define VERIFICA(cond, cod) do { if (!(cond)) { ruim = true; if (motivo == 0) motivo = (cod); } } while (0)
        for (int i = 0; i < 4; ++i) VERIFICA(o.motor[i] >= 0.0f && o.motor[i] <= 1.0f, 1);
        const bool armado = (o.flags & nucleo::kFlagArmado) != 0;
        const bool falha = (o.flags & nucleo::kFlagFalhaNumerica) != 0;
        if (armado && !falha) {
            for (int i = 0; i < 4; ++i) VERIFICA(!(o.motor[i] < cfg.idle - 1e-6f), 2);
        }
        if (!armado) {
            for (int i = 0; i < 4; ++i) VERIFICA(o.motor[i] == 0.0f, 3);
        }
        const float est[9] = {o.roll, o.pitch, o.psi, o.h, o.vz, o.vx, o.vy, o.x, o.y};
        for (int i = 0; i < 9; ++i) VERIFICA(finito(est[i]), 4);
        // a interface 2: tudo finito e dentro dos limites que a Config impõe
        VERIFICA(finito(o.coletivo) && finito(o.acelerador) && o.acelerador >= 0.0f && o.acelerador <= 1.0f, 5);
        VERIFICA(o.coletivo >= 0.0f && o.coletivo <= g.coletivo_max + 1e-4f, 6);
        const bool cascata = (c.modo == nucleo::VELOCIDADE || c.modo == nucleo::YAW_ALVO || c.modo == nucleo::OLHAR) &&
                             (o.flags & nucleo::kFlagModoReservado) == 0;
        if (cascata) {  // (em CTBR as taxas são os setpoints crus do comando: o laço de taxa é que sanea)
            for (int i = 0; i < 2; ++i) VERIFICA(nucleo::absf(o.taxas_ref[i]) <= g.taxa_rp_max + 1e-4f, 7);
            VERIFICA(nucleo::absf(o.taxas_ref[2]) <= g.taxa_yaw_max + 1e-4f, 8);
            for (int i = 0; i < 3; ++i) VERIFICA(finito(o.v_ref[i]), 9);
            VERIFICA(finito(o.yaw_taxa_ref), 10);
        }
        const nucleo::visao::SaidaSeguidor& sg = o.seguidor;
        const float fs[8] = {sg.vx, sg.vy, sg.vz, sg.yaw_taxa, sg.e_psi, sg.e_elev, sg.dist, sg.taxa_bearing};
        for (int i = 0; i < 8; ++i) VERIFICA(finito(fs[i]), 11 + i);
        VERIFICA(sg.estado >= 0 && sg.estado <= 3, 20);
        if (c.modo == nucleo::OLHAR && (o.flags & nucleo::kFlagModoReservado) == 0) {
            VERIFICA(nucleo::absf(sg.yaw_taxa) <= cfg.seguidor.yaw_max + 1e-4f, 21);
            ++olhar;
            ++estados[sg.estado & 3];
        }
        for (int i = 0; i < 3; ++i) VERIFICA(finito(o.a_des[i]) && finito(o.n_des[i]), 22);
        if (ruim) {
            if (violacoes < 5) {
                fprintf(stderr, "estresse_cascata: violação %d no passo %ld (modo %d, flags %d) a_des %g %g %g n_des %g %g %g\n", motivo, k,
                        static_cast<int>(c.modo), o.flags, static_cast<double>(o.a_des[0]), static_cast<double>(o.a_des[1]),
                        static_cast<double>(o.a_des[2]), static_cast<double>(o.n_des[0]), static_cast<double>(o.n_des[1]),
                        static_cast<double>(o.n_des[2]));
            }
            ++violacoes;
        }
#undef VERIFICA
        if (falha) ++falhas;
        if (armado) ++armados;
        if ((o.flags & (nucleo::kFlagSatYawTaxa | nucleo::kFlagSatYawAcel)) != 0) ++sat_yaw;
        if (o.coletivo > 0.0f) ++decisoes;
    }
    printf("estresse_cascata: %ld passos · violações %ld · falhas numéricas sinalizadas %ld · passos armados %ld · "
           "passos com a cascata a mandar %ld · em OLHAR %ld (A_SEGUIR %ld EM_FALTA %ld PERDIDO %ld REAQUISICAO %ld) · yaw limitado %ld\n",
           passos, violacoes, falhas, armados, decisoes, olhar, estados[0], estados[1], estados[2], estados[3], sat_yaw);
    return violacoes == 0 ? 0 : 1;
}
