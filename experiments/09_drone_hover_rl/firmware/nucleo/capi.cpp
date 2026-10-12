// firmware/nucleo/capi.cpp — wrappers extern "C" do núcleo para o ctypes (SITL em Python).
//
// SÓ para o SITL: NÃO entra no firmware do Arduino (o .ino usa nucleo.hpp/.cpp diretamente). Mesmas
// regras do núcleo: float, sem heap (as instâncias vivem num pool ESTÁTICO), sem exceções, sem RTTI.
// As instâncias são referidas por um índice inteiro (o pool é por biblioteca carregada), por isso
// o Python pode ter várias em paralelo (voo de referência + sombra + malha fechada).
#include <stdint.h>

#include "nucleo.hpp"

namespace {

constexpr int32_t kMaxInstancias = 16;

nucleo::Nucleo g_pool[kMaxInstancias];
bool g_usada[kMaxInstancias];

nucleo::Nucleo* obter(int32_t id) {
    if (id < 0 || id >= kMaxInstancias || !g_usada[id]) return nullptr;
    return &g_pool[id];
}

// peças da interface 2 testáveis SOZINHAS (golden vectors do protótipo Python): a cascata e o estimador clássico
nucleo::Cascata g_cascatas[kMaxInstancias];
bool g_cascata_usada[kMaxInstancias];
nucleo::EstimadorClassico g_estimadores[kMaxInstancias];
bool g_estimador_usado[kMaxInstancias];

nucleo::Cascata* obter_cascata(int32_t id) {
    if (id < 0 || id >= kMaxInstancias || !g_cascata_usada[id]) return nullptr;
    return &g_cascatas[id];
}

nucleo::EstimadorClassico* obter_estimador(int32_t id) {
    if (id < 0 || id >= kMaxInstancias || !g_estimador_usado[id]) return nullptr;
    return &g_estimadores[id];
}

}  // namespace

extern "C" {

uint32_t nucleo_versao(void) { return nucleo::kVersaoInterface; }

// tamanhos (bytes) das structs — o Python confere-os contra o layout lido dos cabeçalhos
uint32_t nucleo_tamanho_config(void) { return static_cast<uint32_t>(sizeof(nucleo::Config)); }
uint32_t nucleo_tamanho_sensores(void) { return static_cast<uint32_t>(sizeof(nucleo::Sensores)); }
uint32_t nucleo_tamanho_comando(void) { return static_cast<uint32_t>(sizeof(nucleo::Comando)); }
uint32_t nucleo_tamanho_saida(void) { return static_cast<uint32_t>(sizeof(nucleo::Saida)); }
uint32_t nucleo_tamanho_nucleo(void) { return static_cast<uint32_t>(sizeof(nucleo::Nucleo)); }
uint32_t nucleo_tamanho_referencias(void) { return static_cast<uint32_t>(sizeof(nucleo::ReferenciasTaxa)); }

// reserva uma instância (índice ≥ 0) ou devolve -1 se o pool está cheio
int32_t nucleo_criar(void) {
    for (int32_t i = 0; i < kMaxInstancias; ++i) {
        if (!g_usada[i]) {
            g_usada[i] = true;
            return i;
        }
    }
    return -1;
}

void nucleo_liberar(int32_t id) {
    if (id >= 0 && id < kMaxInstancias) g_usada[id] = false;
}

// 1 = Config aceite, 0 = recusada, -1 = instância inválida
int32_t nucleo_iniciar(int32_t id, const nucleo::Config* cfg) {
    nucleo::Nucleo* n = obter(id);
    if (n == nullptr || cfg == nullptr) return -1;
    return n->iniciar(*cfg) ? 1 : 0;
}

void nucleo_reiniciar(int32_t id) {
    nucleo::Nucleo* n = obter(id);
    if (n != nullptr) n->reiniciar();
}

void nucleo_armar(int32_t id, int32_t armado) {
    nucleo::Nucleo* n = obter(id);
    if (n != nullptr) n->armar(armado != 0);
}

void nucleo_calibrar(int32_t id, const nucleo::Sensores* s) {
    nucleo::Nucleo* n = obter(id);
    if (n != nullptr && s != nullptr) n->calibrar(*s);
}

// estimador clássico: janela de calibração no chão e referências da cascata (interface 2)
void nucleo_calibrar_chao(int32_t id, int32_t ativa) {
    nucleo::Nucleo* n = obter(id);
    if (n != nullptr) n->calibrar_chao(ativa != 0);
}

void nucleo_travar_referencias(int32_t id, int32_t com_z_alvo, float z_alvo) {
    nucleo::Nucleo* n = obter(id);
    if (n != nullptr) n->travar_referencias(com_z_alvo != 0, z_alvo);
}

// passo em duas metades (o SITL põe o atraso do comando entre elas): planear = estimador + laços externos;
// atuar = laço de taxa + mistura + saneamento (completa a Saida que planear começou)
void nucleo_planear(int32_t id, const nucleo::Sensores* s, const nucleo::Comando* c, float dt,
                    nucleo::ReferenciasTaxa* ref, nucleo::Saida* out) {
    nucleo::Nucleo* n = obter(id);
    if (n == nullptr || s == nullptr || c == nullptr || ref == nullptr || out == nullptr) return;
    *out = nucleo::Saida();
    *ref = n->planear(*s, *c, dt, *out);
}

void nucleo_atuar(int32_t id, const nucleo::ReferenciasTaxa* ref, const nucleo::Sensores* s, float dt,
                  nucleo::Saida* io) {
    nucleo::Nucleo* n = obter(id);
    if (n == nullptr || ref == nullptr || s == nullptr || io == nullptr) return;
    n->atuar(*ref, *s, dt, *io);
}

void nucleo_estimativas(int32_t id, nucleo::Saida* out) {
    nucleo::Nucleo* n = obter(id);
    if (n != nullptr && out != nullptr) *out = n->estimativas();
}

void nucleo_passo(int32_t id, const nucleo::Sensores* s, const nucleo::Comando* c, float dt,
                  nucleo::Saida* out) {
    nucleo::Nucleo* n = obter(id);
    if (n == nullptr || s == nullptr || c == nullptr || out == nullptr) return;
    *out = n->passo(*s, *c, dt);
}

// ------------------------------------------------------------------------------------------ cascata SOZINHA
int32_t cascata_criar(void) {
    for (int32_t i = 0; i < kMaxInstancias; ++i) {
        if (!g_cascata_usada[i]) {
            g_cascata_usada[i] = true;
            return i;
        }
    }
    return -1;
}

void cascata_liberar(int32_t id) {
    if (id >= 0 && id < kMaxInstancias) g_cascata_usada[id] = false;
}

void cascata_iniciar(int32_t id, const nucleo::ConfigCascata* cfg) {
    nucleo::Cascata* c = obter_cascata(id);
    if (c != nullptr && cfg != nullptr) c->iniciar(*cfg);
}

void cascata_armar(int32_t id, int32_t armado) {
    nucleo::Cascata* c = obter_cascata(id);
    if (c != nullptr) c->armar(armado != 0);
}

void cascata_travar(int32_t id, const nucleo::Saida* est, int32_t com_z_alvo, float z_alvo) {
    nucleo::Cascata* c = obter_cascata(id);
    if (c != nullptr && est != nullptr) c->travar(*est, com_z_alvo != 0, z_alvo);
}

// `res` = {coletivo, p, q, r}; `diag` recebe o diagnóstico da decisão (a_des, n_des, e_tilt, gama, p_sp, …)
void cascata_passo(int32_t id, const nucleo::ConfigCascata* cfg, const nucleo::Saida* est, const float* giro,
                   const nucleo::Comando* cmd, float dt, float* res, int32_t* flags, nucleo::Saida* diag) {
    nucleo::Cascata* c = obter_cascata(id);
    if (c == nullptr || cfg == nullptr || est == nullptr || giro == nullptr || cmd == nullptr || res == nullptr ||
        flags == nullptr || diag == nullptr) {
        return;
    }
    const nucleo::Cascata::Resultado r = c->passo(*cfg, *est, giro, *cmd, dt);
    res[0] = r.coletivo;
    for (int e = 0; e < 3; ++e) res[1 + e] = r.taxas[e];
    *flags = r.flags;
    c->diagnostico(*diag);
}

// ------------------------------------------------------------------------------------- estimador clássico SOZINHO
int32_t estcl_criar(void) {
    for (int32_t i = 0; i < kMaxInstancias; ++i) {
        if (!g_estimador_usado[i]) {
            g_estimador_usado[i] = true;
            return i;
        }
    }
    return -1;
}

void estcl_liberar(int32_t id) {
    if (id >= 0 && id < kMaxInstancias) g_estimador_usado[id] = false;
}

void estcl_zerar(int32_t id) {
    nucleo::EstimadorClassico* e = obter_estimador(id);
    if (e != nullptr) e->zerar();
}

void estcl_iniciar_com(int32_t id, const nucleo::Sensores* s) {
    nucleo::EstimadorClassico* e = obter_estimador(id);
    if (e != nullptr && s != nullptr) e->iniciar_com(*s);
}

void estcl_janela(int32_t id, const nucleo::Config* cfg, int32_t ativa) {
    nucleo::EstimadorClassico* e = obter_estimador(id);
    if (e != nullptr && cfg != nullptr) e->janela_calibracao(*cfg, ativa != 0);
}

// um passo; `out` recebe só as 9 estimativas (roll … y) e o viés do giroscópio em giro_f (diagnóstico)
void estcl_passo(int32_t id, const nucleo::Config* cfg, const nucleo::Sensores* s, float dt, nucleo::Saida* out) {
    nucleo::EstimadorClassico* e = obter_estimador(id);
    if (e == nullptr || cfg == nullptr || s == nullptr || out == nullptr) return;
    e->passo(*cfg, *s, dt);
    out->roll = e->roll;
    out->pitch = e->pitch;
    out->psi = e->psi;
    out->h = e->h;
    out->vz = e->vz;
    out->vx = e->vx;
    out->vy = e->vy;
    out->x = e->x;
    out->y = e->y;
    for (int k = 0; k < 3; ++k) out->giro_f[k] = e->bias_giro(k);
    out->v_ref[0] = e->bias_acc();
    out->v_ref[1] = e->a_horizontal();
    out->flags = e->calibrando() ? nucleo::kFlagCalibrando : 0;
}

}  // extern "C"
