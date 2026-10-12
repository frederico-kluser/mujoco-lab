// firmware/cross/qemu/driver_replay.cpp — o DRIVER de repetição do núcleo: corre a MESMA fonte do firmware (nucleo/*.hpp) sobre um
// ficheiro de registos GRAVADOS de um voo e escreve as saídas, no host (stdio) ou BARE-METAL no QEMU (semihosting, sem libc).
// O `qemu_alvo.py` compila-o três vezes (host com libm própria, Cortex-M4, Cortex-M7) e compara as saídas BIT A BIT.
//
// FORMATO (tudo little-endian, campos de 4 bytes; os tamanhos vêm do compilador, por isso o driver é genérico face ao crescimento
// das structs Config/Sensores/Comando/Saida da interface do núcleo):
//   config.bin   — os bytes crus de uma `nucleo::Config`
//   entrada.bin  — cabeçalho {u32 magia = 0x3143554E ("NUC1"), u32 versao_interface, u32 sizeof(Config), u32 sizeof(Sensores),
//                  u32 sizeof(Comando), u32 sizeof(Saida), u32 n_registos} + n × Registo
//   Registo      — {i32 op; f32 dt; i32 semente; f32 extra[4]; Sensores s; Comando c}
//   saida.bin    — um bloco por registo: `Saida` crua (ops 0–7) ou `Deteccao` crua (op 8)
// OPS: 0 passo(s, c, dt) · 1 reiniciar · 2 armar(true) · 3 armar(false) · 4 calibrar(s) · 5 calibrar_chao(true) ·
//      6 calibrar_chao(false) · 7 travar_referencias(extra[0] != 0, extra[1]) · 8 detetar: o driver SINTETIZA no alvo (PRNG xorshift
//      em inteiros) um frame mono 320×240 com um disco brilhante em (extra[0], extra[1]) de raio extra[2] (px) e ruído de `semente`,
//      e corre `visao::Detetor::detetar` — prova que o detetor também corre igual. Ops 1–7 devolvem `estimativas()`.
//      PARA ACRESCENTAR UMA OP: novo enumerador + um `case` no switch de `processa()` (e documentar aqui).
// Os marcadores `marcador_inicio/fim(k)` (noinline) delimitam cada passo no traço de instruções do QEMU.
#include <stdint.h>

#include "nucleo/nucleo.hpp"
#include "nucleo/visao.hpp"

#ifndef NUCLEO_ALVO_BARE
#include <stdio.h>
#endif

namespace {

constexpr uint32_t kMagia = 0x3143554Eu;
constexpr int32_t kLargura = 320;
constexpr int32_t kAltura = 240;
constexpr uint32_t kBufSaida = 4096;

enum Op : int32_t {
    OP_PASSO = 0, OP_REINICIAR = 1, OP_ARMAR = 2, OP_DESARMAR = 3, OP_CALIBRAR = 4, OP_CALIBRAR_CHAO_ON = 5,
    OP_CALIBRAR_CHAO_OFF = 6, OP_TRAVAR = 7, OP_DETETAR = 8
};

struct Registo {
    int32_t op;
    float dt;
    int32_t semente;
    float extra[4];
    nucleo::Sensores s;
    nucleo::Comando c;
};

struct Cabecalho {
    uint32_t magia;
    uint32_t versao;
    uint32_t tam_config;
    uint32_t tam_sensores;
    uint32_t tam_comando;
    uint32_t tam_saida;
    uint32_t n_registos;
};

// estado ESTÁTICO (.bss), como no firmware: nada na pilha nem no heap
nucleo::Nucleo g_nucleo;
nucleo::Config g_config;
nucleo::visao::Detetor g_detetor;
uint8_t g_frame[kLargura * kAltura];
uint8_t g_buf_saida[kBufSaida];
uint32_t g_n_buf;
uint32_t g_crc = 0xFFFFFFFFu;
uint32_t g_bytes_saida;

#ifdef NUCLEO_ALVO_BARE
// ---------------------------------------------------------------------------------- E/S por semihosting ARM (bkpt 0xAB)
typedef int32_t Handle;

inline int32_t semi(int32_t op, const void* arg) {
    int32_t res;
    __asm__ volatile("mov r0, %1\n\tmov r1, %2\n\tbkpt 0xAB\n\tmov %0, r0" : "=r"(res) : "r"(op), "r"(arg) : "r0", "r1", "memory");
    return res;
}

uint32_t comprimento(const char* s) {
    uint32_t n = 0;
    while (s[n] != '\0') ++n;
    return n;
}

bool abrir(const char* nome, bool escrita, Handle* h) {
    const int32_t blk[3] = {static_cast<int32_t>(reinterpret_cast<uintptr_t>(nome)), escrita ? 5 : 1,
                            static_cast<int32_t>(comprimento(nome))};  // "wb" / "rb"
    *h = semi(0x01, blk);
    return *h >= 0;
}

bool ler(Handle h, void* buf, uint32_t n) {
    const int32_t blk[3] = {h, static_cast<int32_t>(reinterpret_cast<uintptr_t>(buf)), static_cast<int32_t>(n)};
    return semi(0x06, blk) == 0;  // devolve os bytes NÃO lidos
}

bool escrever(Handle h, const void* buf, uint32_t n) {
    const int32_t blk[3] = {h, static_cast<int32_t>(reinterpret_cast<uintptr_t>(buf)), static_cast<int32_t>(n)};
    return semi(0x05, blk) == 0;
}

void fechar(Handle h) {
    const int32_t blk[1] = {h};
    semi(0x02, blk);
}

void texto(const char* s) { semi(0x04, s); }

[[noreturn]] void sair(int32_t codigo) {
    const int32_t blk[2] = {0x20026, codigo};  // ADP_Stopped_ApplicationExit + código de saída (SYS_EXIT_EXTENDED)
    semi(0x20, blk);
    for (;;) {
    }
}
#else
// ---------------------------------------------------------------------------------- E/S por stdio (host)
typedef FILE* Handle;

bool abrir(const char* nome, bool escrita, Handle* h) {
    *h = fopen(nome, escrita ? "wb" : "rb");
    return *h != nullptr;
}
bool ler(Handle h, void* buf, uint32_t n) { return fread(buf, 1, n, h) == n; }
bool escrever(Handle h, const void* buf, uint32_t n) { return fwrite(buf, 1, n, h) == n; }
void fechar(Handle h) { fclose(h); }
void texto(const char* s) { fputs(s, stdout); }
#endif

void numero(uint32_t v, char* fim) {  // escreve `v` em decimal terminado em `fim` (o chamador reserva espaço)
    char* p = fim;
    *p = '\0';
    do {
        *--p = static_cast<char>('0' + v % 10u);
        v /= 10u;
    } while (v != 0u);
    texto(p);
}

void hexa(uint32_t v) {
    char b[9];
    for (int i = 7; i >= 0; --i) {
        b[i] = "0123456789abcdef"[v & 0xFu];
        v >>= 4;
    }
    b[8] = '\0';
    texto(b);
}

void crc_acumula(const uint8_t* p, uint32_t n) {
#ifdef NUCLEO_SEM_CRC  // imagens do traço de instruções: o CRC bit a bit (~15 k instruções por registo) só polui o traço
    (void)p;
    (void)n;
    return;
#else
    for (uint32_t i = 0; i < n; ++i) {
        g_crc ^= p[i];
        for (int b = 0; b < 8; ++b) g_crc = (g_crc >> 1) ^ (0xEDB88320u & (0u - (g_crc & 1u)));
    }
#endif
}

Handle g_saida;

bool descarrega() {
    if (g_n_buf == 0) return true;
    const bool ok = escrever(g_saida, g_buf_saida, g_n_buf);
    g_n_buf = 0;
    return ok;
}

bool emite(const void* dados, uint32_t n) {
    const uint8_t* p = static_cast<const uint8_t*>(dados);
    crc_acumula(p, n);
    g_bytes_saida += n;
    while (n > 0) {
        const uint32_t cabe = kBufSaida - g_n_buf;
        const uint32_t k = n < cabe ? n : cabe;
        for (uint32_t i = 0; i < k; ++i) g_buf_saida[g_n_buf + i] = p[i];
        g_n_buf += k;
        p += k;
        n -= k;
        if (g_n_buf == kBufSaida && !descarrega()) return false;
    }
    return true;
}

// marcadores do traço de instruções (o QEMU regista os PCs; cada passo fica entre estas duas funções)
extern "C" __attribute__((noinline)) void marcador_inicio(int32_t k) { __asm__ volatile("" : : "r"(k) : "memory"); }
extern "C" __attribute__((noinline)) void marcador_fim(int32_t k) { __asm__ volatile("" : : "r"(k) : "memory"); }

// frame mono 320×240: fundo 20 + ruído (0–7) e um disco de cobertura sub-píxel (borda linear de 1 px), em aritmética float
void sintetizar_frame(float u, float v, float raio, uint32_t semente) {
    uint32_t s = semente != 0u ? semente : 1u;
    for (int32_t y = 0; y < kAltura; ++y) {
        for (int32_t x = 0; x < kLargura; ++x) {
            s ^= s << 13;
            s ^= s >> 17;
            s ^= s << 5;
            const float dx = static_cast<float>(x) - u;
            const float dy = static_cast<float>(y) - v;
            float cob = raio + 0.5f - sqrtf(dx * dx + dy * dy);
            cob = cob < 0.0f ? 0.0f : (cob > 1.0f ? 1.0f : cob);
            const int32_t val = 20 + static_cast<int32_t>(s & 7u) + static_cast<int32_t>(cob * 215.0f);
            g_frame[y * kLargura + x] = static_cast<uint8_t>(val > 255 ? 255 : val);
        }
    }
}

bool processa(const Registo& r, int32_t k) {
    nucleo::Saida saida = {};
    switch (r.op) {
        case OP_PASSO:
            marcador_inicio(k);
            saida = g_nucleo.passo(r.s, r.c, r.dt);
            marcador_fim(k);
            break;
        case OP_REINICIAR: g_nucleo.reiniciar(); saida = g_nucleo.estimativas(); break;
        case OP_ARMAR: g_nucleo.armar(true); saida = g_nucleo.estimativas(); break;
        case OP_DESARMAR: g_nucleo.armar(false); saida = g_nucleo.estimativas(); break;
        case OP_CALIBRAR: g_nucleo.calibrar(r.s); saida = g_nucleo.estimativas(); break;
        case OP_CALIBRAR_CHAO_ON: g_nucleo.calibrar_chao(true); saida = g_nucleo.estimativas(); break;
        case OP_CALIBRAR_CHAO_OFF: g_nucleo.calibrar_chao(false); saida = g_nucleo.estimativas(); break;
        case OP_TRAVAR: g_nucleo.travar_referencias(r.extra[0] != 0.0f, r.extra[1]); saida = g_nucleo.estimativas(); break;
        case OP_DETETAR: {
            sintetizar_frame(r.extra[0], r.extra[1], r.extra[2], static_cast<uint32_t>(r.semente));
            const nucleo::visao::ParamsDetetor p = nucleo::visao::params_padrao(kLargura, kAltura);
            marcador_inicio(k);
            const nucleo::visao::Deteccao d = g_detetor.detetar(g_frame, kLargura, kAltura, 0, p);
            marcador_fim(k);
            return emite(&d, sizeof(d));
        }
        default: return false;
    }
    return emite(&saida, sizeof(saida));
}

int32_t executar() {
    Handle h_cfg, h_in;
    if (!abrir("config.bin", false, &h_cfg) || !ler(h_cfg, &g_config, sizeof(g_config))) {
        texto("ERRO: config.bin ilegivel ou de tamanho errado\n");
        return 2;
    }
    fechar(h_cfg);
    if (!abrir("entrada.bin", false, &h_in)) {
        texto("ERRO: entrada.bin\n");
        return 2;
    }
    Cabecalho cab;
    if (!ler(h_in, &cab, sizeof(cab)) || cab.magia != kMagia || cab.tam_config != sizeof(nucleo::Config) ||
        cab.tam_sensores != sizeof(nucleo::Sensores) || cab.tam_comando != sizeof(nucleo::Comando) ||
        cab.tam_saida != sizeof(nucleo::Saida) || cab.versao != nucleo::kVersaoInterface) {
        texto("ERRO: cabecalho de entrada.bin diverge das structs compiladas (layout/versao)\n");
        return 3;
    }
    if (!g_nucleo.iniciar(g_config)) {
        texto("ERRO: o nucleo recusou a Config\n");
        return 4;
    }
    if (!abrir("saida.bin", true, &g_saida)) {
        texto("ERRO: saida.bin\n");
        return 2;
    }
    uint32_t n_saidas = 0;
    static Registo reg;
    for (uint32_t i = 0; i < cab.n_registos; ++i) {
        if (!ler(h_in, &reg, sizeof(reg))) {
            texto("ERRO: entrada.bin truncado\n");
            return 5;
        }
        if (!processa(reg, static_cast<int32_t>(i))) {
            texto("ERRO: op desconhecida ou falha a escrever\n");
            return 6;
        }
        ++n_saidas;
    }
    if (!descarrega()) return 6;
    fechar(h_in);
    fechar(g_saida);
    char buf[16];
    texto("REPLAY registos=");
    numero(cab.n_registos, buf + 15);
    texto(" saidas=");
    numero(n_saidas, buf + 15);
    texto(" bytes=");
    numero(g_bytes_saida, buf + 15);
    texto(" crc32=");
    hexa(~g_crc);
    texto("\n");
    return 0;
}

}  // namespace

#ifdef NUCLEO_ALVO_BARE
extern "C" void alvo_principal(void) { sair(executar()); }

extern "C" void alvo_falha(int32_t n) {
    texto("FALHA de CPU (excecao ");
    char buf[16];
    numero(static_cast<uint32_t>(n), buf + 15);
    texto(")\n");
    sair(100 + n);
}
#else
int main() {
    const int32_t r = executar();
    fflush(stdout);
    return r == 0 ? 0 : 1;
}
#endif
