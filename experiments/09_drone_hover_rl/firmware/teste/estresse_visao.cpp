// firmware/teste/estresse_visao.cpp — ESTRESSE da atividade C (detetor + seguidor) com ASan+UBSan.
// Só testes no host (usa malloc/stdio): NÃO é firmware. Compila com `-fsanitize=address,undefined`.
//
//   · Detetor: frames de tamanho EXATO (um byte a mais lido = ASan) com ruído, constantes, píxeis quentes,
//     riscas, tabuleiros, discos, janelas (ROI) fora de limites, parâmetros hostis (NaN/inf/negativos);
//   · Seguidor: Configs válidas e inválidas, relógio com saltos/voltas/repetições, atitude NaN/inf/enorme,
//     Camera com lixo (u,v NaN/enormes, raio ≤ 0, n aleatório, t absurdo).
// Invariantes: saídas finitas; Deteccao coerente (u,v dentro do frame, gates cumpridos); estado ∈ [0,3]; comando
// dentro dos limites da Config. Imprime «violações N · deteções válidas M · passos do seguidor K · …» e sai 0 se N = 0.
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "../nucleo/alvo.hpp"
#include "../nucleo/ibvs.hpp"
#include "../nucleo/visao.hpp"

using namespace nucleo::visao;

namespace {

uint64_t g_estado = 88172645463325252ull;
uint32_t rnd() {
    g_estado ^= g_estado << 13;
    g_estado ^= g_estado >> 7;
    g_estado ^= g_estado << 17;
    return static_cast<uint32_t>(g_estado >> 11);
}
float unif(float a, float b) { return a + (b - a) * (static_cast<float>(rnd() & 0xFFFFFF) / 16777215.0f); }
int32_t inteiro(int32_t a, int32_t b) { return a + static_cast<int32_t>(rnd() % static_cast<uint32_t>(b - a + 1)); }

long g_violacoes = 0;
void viola(const char* o) {
    if (g_violacoes < 20) fprintf(stderr, "VIOLAÇÃO: %s\n", o);
    ++g_violacoes;
}
bool fin(float x) { return (x - x) == 0.0f; }
float fabsf_(float x) { return x < 0.0f ? -x : x; }

float hostil() {  // um float «difícil»
    switch (rnd() % 12) {
        case 0: return NAN;
        case 1: return INFINITY;
        case 2: return -INFINITY;
        case 3: return 1e30f;
        case 4: return -1e30f;
        case 5: return 0.0f;
        case 6: return -0.0f;
        case 7: return 1e-30f;
        case 8: return unif(-10.0f, 10.0f);
        case 9: return unif(-4000.0f, 4000.0f);
        case 10: return static_cast<float>(inteiro(-3, 3));
        default: return unif(-1.0f, 1.0f);
    }
}

// ----------------------------------------------------------------------------------------- detetor
long g_validas = 0;
long g_frames = 0;

void fabrica_frame(uint8_t* f, int32_t w, int32_t h) {
    const int32_t padrao = inteiro(0, 7);
    const int32_t n = w * h;
    for (int32_t i = 0; i < n; ++i) f[i] = 0;
    switch (padrao) {
        case 0:  // ruído branco
            for (int32_t i = 0; i < n; ++i) f[i] = static_cast<uint8_t>(rnd());
            break;
        case 1:  // tudo a 255
            for (int32_t i = 0; i < n; ++i) f[i] = 255;
            break;
        case 2: {  // um píxel quente (ou vários) num fundo escuro
            for (int32_t i = 0; i < n; ++i) f[i] = static_cast<uint8_t>(20 + (rnd() & 7));
            const int32_t k = inteiro(1, 6);
            for (int32_t j = 0; j < k; ++j) f[inteiro(0, n - 1)] = 255;
            break;
        }
        case 3:  // riscas verticais/horizontais
            for (int32_t y = 0; y < h; ++y)
                for (int32_t x = 0; x < w; ++x) f[y * w + x] = ((x / 3 + y / 5) & 1) != 0 ? 230 : 15;
            break;
        case 4:  // tabuleiro de 1 píxel (máximo de runs por linha)
            for (int32_t y = 0; y < h; ++y)
                for (int32_t x = 0; x < w; ++x) f[y * w + x] = ((x + y) & 1) != 0 ? 255 : 0;
            break;
        default: {  // vários discos (alguns cortados pelo bordo) com ruído
            for (int32_t i = 0; i < n; ++i) f[i] = static_cast<uint8_t>(10 + (rnd() & 15));
            const int32_t k = inteiro(1, 5);
            for (int32_t j = 0; j < k; ++j) {
                const float cx = unif(-5.0f, static_cast<float>(w) + 5.0f);
                const float cy = unif(-5.0f, static_cast<float>(h) + 5.0f);
                const float r = unif(1.0f, 40.0f);
                const float ar = (rnd() & 1) != 0 ? unif(1.0f, 6.0f) : 1.0f;  // alongado?
                for (int32_t y = 0; y < h; ++y)
                    for (int32_t x = 0; x < w; ++x) {
                        const float dx = (static_cast<float>(x) - cx) / ar;
                        const float dy = static_cast<float>(y) - cy;
                        if (dx * dx + dy * dy <= r * r) f[y * w + x] = static_cast<uint8_t>(inteiro(180, 255));
                    }
            }
            break;
        }
    }
}

void testa_detetor(long iteracoes) {
    static Detetor det;
    for (long it = 0; it < iteracoes; ++it) {
        const bool tamanho_mau = (rnd() % 20) == 0;
        int32_t w = tamanho_mau ? inteiro(-2, 1200) : inteiro(2, 360);
        int32_t h = tamanho_mau ? inteiro(-2, 1200) : inteiro(2, 260);
        const bool ok_tam = w >= 2 && h >= 2 && w <= kLadoMax && h <= kLadoMax;
        const int32_t n = ok_tam ? w * h : 1;
        uint8_t* f = static_cast<uint8_t*>(malloc(static_cast<size_t>(n)));  // tamanho EXATO: ler a mais = ASan
        if (f == nullptr) return;
        if (ok_tam) fabrica_frame(f, w, h);
        ParamsDetetor p = params_padrao(w, h);
        if ((rnd() & 3) == 0) {  // parâmetros hostis
            p.frac_max = hostil();
            p.contraste_min = inteiro(-50, 400);
            p.paso_max = inteiro(-3, 20);
            p.area_min = hostil();
            p.area_max = hostil();
            p.circ_min = hostil();
            p.cheio_min = hostil();
            p.cheio_max = hostil();
            p.margem_borda = inteiro(-3, 50);
        }
        if ((rnd() & 3) == 0) {  // janela (muitas vezes fora de limites)
            p.roi_x0 = inteiro(-50, w + 50);
            p.roi_y0 = inteiro(-50, h + 50);
            p.roi_x1 = inteiro(-50, w + 50);
            p.roi_y1 = inteiro(-50, h + 50);
        }
        const int32_t limiar = (rnd() & 1) != 0 ? 0 : inteiro(-5, 300);
        const Deteccao d = det.detetar(ok_tam ? f : nullptr, w, h, limiar, p);
        ++g_frames;
        if (!(d.motivo >= M_OK && d.motivo <= M_PARAMETROS)) viola("motivo fora do enum");
        if ((d.valido != 0) != (d.motivo == M_OK)) viola("valido ≠ (motivo == OK)");
        if (d.valido != 0) {
            ++g_validas;
            if (!(fin(d.u) && fin(d.v) && fin(d.raio_px) && fin(d.circularidade) && fin(d.area) && fin(d.cheio))) {
                viola("deteção válida com campo não finito");
            } else {
                if (d.u < -0.5f || d.u > static_cast<float>(w) - 0.5f || d.v < -0.5f || d.v > static_cast<float>(h) - 0.5f)
                    viola("centróide fora do frame");
                if (!(d.raio_px > 0.0f) || d.area < 1.0f || d.area > static_cast<float>(w) * static_cast<float>(h))
                    viola("área/raio absurdos");
                if (d.circularidade < -1e-3f || d.circularidade > 1.0f + 1e-3f) viola("circularidade fora de [0,1]");
                if (d.area < p.area_min || d.area > p.area_max) viola("válida com área fora dos gates");
                if (d.circularidade < p.circ_min - 1e-4f) viola("válida com circularidade abaixo do gate");
            }
        }
        if (!ok_tam && d.valido != 0) viola("válida num frame/tamanho inválido");
        free(f);
    }
}

// ----------------------------------------------------------------------------------------- seguidor
long g_passos = 0;
long g_estados[4] = {0, 0, 0, 0};
long g_falhas_numericas = 0;
long g_recusadas = 0;

ConfigSeguidor config_aleatoria() {
    ConfigSeguidor c = config_padrao(320.0f, 240.0f, 55.4f, inteiro(0, 2));
    if ((rnd() % 3) == 0) c = config_versao1(c);  // um terço dos cenários: a lei da versão 1 (v_y = 0, sem compensações)
    if ((rnd() % 4) == 0) {  // perturba e às vezes estraga
        float* campos[] = {&c.f_px, &c.raio_alvo_m, &c.dist_alvo_m, &c.kp_yaw, &c.ki_yaw, &c.yaw_max, &c.vx_max,
                           &c.vz_max, &c.t_gap_s, &c.t_falta_s, &c.q_ang, &c.sigma_px, &c.gate_sigma, &c.kff_yaw,
                           &c.w_procura, &c.zona_morta_yaw, &c.alfa, &c.beta, &c.kp_y, &c.kff_y, &c.vy_max,
                           &c.acel_y_max, &c.zona_morta_y, &c.k_incl_z, &c.tau_incl_s, &c.q_raio};
        const int32_t k = inteiro(0, static_cast<int32_t>(sizeof(campos) / sizeof(campos[0])) - 1);
        *campos[k] = hostil();
    }
    if ((rnd() % 16) == 0) c.versao = static_cast<uint32_t>(rnd());
    if ((rnd() % 16) == 0) c.modelo = inteiro(-2, 5);
    if ((rnd() % 16) == 0) c.n_reaq = inteiro(-2, 9);
    if ((rnd() % 16) == 0) c.comp_translacao = inteiro(-1, 2);
    if ((rnd() % 16) == 0) c.raio_cv = inteiro(-1, 2);
    return c;
}

void testa_seguidor(long cenarios, long passos_por_cenario) {
    static Seguidor seg;
    for (long ce = 0; ce < cenarios; ++ce) {
        ConfigSeguidor cfg = config_aleatoria();
        // de 40 em 40 cenários: um σ «válido» (finito, > 0) cujo quadrado transborda o float32 — a covariância nasce
        // infinita e o seguidor TEM de o apanhar (kFlagFalhaNumerica) em vez de mandar lixo
        if ((ce % 40) == 13) cfg.sigma_px = 1e30f;
        const bool ok = seg.iniciar(cfg);
        if (ok != config_valida(cfg)) viola("iniciar() ≠ config_valida()");
        if (!ok) ++g_recusadas;
        uint32_t t = (rnd() & 1) != 0 ? rnd() : 0xFFFFF000u;  // às vezes perto da volta de 2³²
        Camera cam = {};
        Atitude att = {};
        const bool bem_comportado = (ce % 2) == 0;   // metade dos cenários: câmara e relógio plausíveis
        uint32_t t_cam = t;
        float u_s = 160.0f;
        float v_s = 120.0f;
        for (long k = 0; k < passos_por_cenario; ++k) {
            const uint32_t modo_t = rnd() % 32;
            if (bem_comportado) t += 10000u;              // 100 Hz certinhos
            else if (modo_t == 0) t = rnd();                       // salto qualquer
            else if (modo_t == 1) t -= static_cast<uint32_t>(inteiro(1, 100000));  // volta atrás
            else if (modo_t != 2) t += static_cast<uint32_t>(inteiro(1, 30000));   // avança 1–30 ms
            const uint32_t raro = bem_comportado ? 400u : 24u;   // no cenário bem comportado a atitude quase nunca é lixo
            att.roll = (rnd() % raro) == 0 ? hostil() : unif(-0.5f, 0.5f);
            att.pitch = (rnd() % raro) == 0 ? hostil() : unif(-0.5f, 0.5f);
            att.psi = (rnd() % raro) == 0 ? hostil() : unif(-7.0f, 7.0f);
            att.vx = (rnd() % raro) == 0 ? hostil() : unif(-1.0f, 1.0f);
            att.vy = (rnd() % raro) == 0 ? hostil() : unif(-1.0f, 1.0f);
            att.vz = (rnd() % raro) == 0 ? hostil() : unif(-1.0f, 1.0f);
            if (bem_comportado) {  // câmara plausível (alcança A_SEGUIR/EM_FALTA): 25 Hz, atraso 116 ms, falhas curtas
                if (t - t_cam >= 40000u && t - t_cam < 1000000u) {
                    t_cam = t;
                    cam.n += 1;
                    const bool falha = (rnd() % 10) < (static_cast<uint32_t>(ce) % 3u == 0u ? 6u : 1u);
                    cam.valido = falha ? 0 : 1;
                    u_s += unif(-2.0f, 2.0f);
                    v_s += unif(-1.5f, 1.5f);
                    u_s = u_s < 20.0f ? 20.0f : (u_s > 300.0f ? 300.0f : u_s);
                    v_s = v_s < 20.0f ? 20.0f : (v_s > 220.0f ? 220.0f : v_s);
                    cam.u = u_s;
                    cam.v = v_s;
                    cam.raio = 8.0f + unif(-0.5f, 0.5f);
                    cam.t = t - 116000u;
                }
            } else if ((rnd() % 3) == 0) {  // frame novo com lixo
                cam.n = static_cast<int32_t>((rnd() % 8) == 0 ? rnd() : static_cast<uint32_t>(cam.n) + 1u);
                cam.valido = (rnd() % 8) == 0 ? 0 : static_cast<int32_t>(rnd() % 3);
                cam.u = (rnd() % 16) == 0 ? hostil() : unif(0.0f, 320.0f);
                cam.v = (rnd() % 16) == 0 ? hostil() : unif(0.0f, 240.0f);
                cam.raio = (rnd() % 16) == 0 ? hostil() : unif(0.0f, 30.0f);
                const uint32_t tm = rnd() % 8;
                cam.t = tm == 0 ? rnd() : (tm == 1 ? t + 5000000u : t - static_cast<uint32_t>(inteiro(0, 300000)));
            }
            const SaidaSeguidor o = seg.passo(t, att, cam);
            ++g_passos;
            if (o.estado >= 0 && o.estado <= 3) ++g_estados[o.estado];
            else viola("estado fora de [0,3]");
            if ((o.flags & kFlagFalhaNumerica) != 0) ++g_falhas_numericas;
            const float campos[] = {o.vx, o.vy, o.vz, o.yaw_taxa, o.e_psi, o.e_elev, o.dist, o.taxa_bearing,
                                    o.acel_bearing, o.az_pred, o.el_pred, o.u_pred, o.v_pred, o.raio_pred, o.t_sem_det_s,
                                    o.e_h_cam, o.e_v_cam, o.v_alvo_rad, o.v_alvo_tan, o.v_alvo_vert};
            for (size_t j = 0; j < sizeof(campos) / sizeof(campos[0]); ++j) {
                if (!fin(campos[j])) {
                    viola("saída não finita");
                    break;
                }
            }
            if (ok) {
                const ConfigSeguidor& c = seg.config();
                if (fabsf_(o.vx) > c.vx_max + 1e-4f || fabsf_(o.vy) > c.vy_max + 1e-4f || fabsf_(o.vz) > c.vz_max + 1e-4f ||
                    fabsf_(o.yaw_taxa) > c.yaw_max + 1e-4f) {
                    viola("comando acima dos limites da Config");
                }
                if (c.kp_y == 0.0f && c.kff_y == 0.0f && o.vy != 0.0f) viola("lei da versão 1 com vy ≠ 0");
            } else if (o.vx != 0.0f || o.vy != 0.0f || o.vz != 0.0f || o.yaw_taxa != 0.0f ||
                       (o.flags & kFlagNaoIniciado) == 0) {
                viola("seguidor não iniciado devia dar comando nulo + kFlagNaoIniciado");
            }
        }
    }
}

}  // namespace

int main(int argc, char** argv) {
    const long n_det = argc > 1 ? atol(argv[1]) : 20000;
    const long n_seg = argc > 2 ? atol(argv[2]) : 400;
    testa_detetor(n_det);
    testa_seguidor(n_seg, 2500);
    printf("violações %ld · frames %ld · deteções válidas %ld · passos do seguidor %ld · estados %ld/%ld/%ld/%ld · "
           "falhas numéricas sinalizadas %ld · configs recusadas %ld\n",
           g_violacoes, g_frames, g_validas, g_passos, g_estados[0], g_estados[1], g_estados[2], g_estados[3],
           g_falhas_numericas, g_recusadas);
    return g_violacoes == 0 ? 0 : 1;
}
