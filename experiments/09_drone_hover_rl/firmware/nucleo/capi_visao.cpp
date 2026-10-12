// firmware/nucleo/capi_visao.cpp — wrappers extern "C" da atividade C (visão + alvo + IBVS) para o ctypes.
//
// SÓ para o SITL/testes: NÃO entra no firmware do Arduino (o .ino usa visao.hpp/alvo.hpp/ibvs.hpp diretamente).
// Mesmas regras do núcleo: float, sem heap (as instâncias vivem em pools ESTÁTICOS), sem exceções, sem RTTI. As
// instâncias referem-se por um índice inteiro; o Python pode ter várias em paralelo.
#include <stdint.h>

#include "alvo.hpp"
#include "ibvs.hpp"
#include "visao.hpp"
#include "visao_tipos.hpp"

namespace {

using nucleo::visao::Detetor;
using nucleo::visao::Seguidor;

constexpr int32_t kMaxInstancias = 16;

Detetor g_detetores[kMaxInstancias];
bool g_det_usado[kMaxInstancias];
Seguidor g_seguidores[kMaxInstancias];
bool g_seg_usado[kMaxInstancias];

Detetor* obter_detetor(int32_t id) {
    if (id < 0 || id >= kMaxInstancias || !g_det_usado[id]) return nullptr;
    return &g_detetores[id];
}

Seguidor* obter_seguidor(int32_t id) {
    if (id < 0 || id >= kMaxInstancias || !g_seg_usado[id]) return nullptr;
    return &g_seguidores[id];
}

}  // namespace

extern "C" {

uint32_t visao_versao(void) { return nucleo::visao::kVersaoVisao; }

// tamanhos (bytes) das structs — o Python confere-os contra o layout lido do visao_tipos.hpp
uint32_t visao_tamanho_camera(void) { return static_cast<uint32_t>(sizeof(nucleo::visao::Camera)); }
uint32_t visao_tamanho_params_detetor(void) { return static_cast<uint32_t>(sizeof(nucleo::visao::ParamsDetetor)); }
uint32_t visao_tamanho_deteccao(void) { return static_cast<uint32_t>(sizeof(nucleo::visao::Deteccao)); }
uint32_t visao_tamanho_detetor(void) { return static_cast<uint32_t>(sizeof(Detetor)); }
uint32_t visao_tamanho_atitude(void) { return static_cast<uint32_t>(sizeof(nucleo::visao::Atitude)); }
uint32_t visao_tamanho_config_seguidor(void) {
    return static_cast<uint32_t>(sizeof(nucleo::visao::ConfigSeguidor));
}
uint32_t visao_tamanho_saida_seguidor(void) {
    return static_cast<uint32_t>(sizeof(nucleo::visao::SaidaSeguidor));
}
uint32_t visao_tamanho_seguidor(void) { return static_cast<uint32_t>(sizeof(Seguidor)); }

// ------------------------------------------------------------------------------------------ detetor
int32_t detetor_criar(void) {
    for (int32_t i = 0; i < kMaxInstancias; ++i) {
        if (!g_det_usado[i]) {
            g_det_usado[i] = true;
            return i;
        }
    }
    return -1;
}

void detetor_liberar(int32_t id) {
    if (id >= 0 && id < kMaxInstancias) g_det_usado[id] = false;
}

void detetor_params_padrao(int32_t largura, int32_t altura, nucleo::visao::ParamsDetetor* out) {
    if (out != nullptr) *out = nucleo::visao::params_padrao(largura, altura);
}

// Deteta no frame (largura×altura, uint8, linha a linha). limiar > 0 = fixo; ≤ 0 = adaptativo.
void detetor_detetar(int32_t id, const uint8_t* frame, int32_t largura, int32_t altura, int32_t limiar,
                     const nucleo::visao::ParamsDetetor* p, nucleo::visao::Deteccao* out) {
    Detetor* d = obter_detetor(id);
    if (d == nullptr || p == nullptr || out == nullptr) return;
    *out = d->detetar(frame, largura, altura, limiar, *p);
}

// Janela de busca do próximo frame a partir da previsão do seguidor (preenche só os campos roi_* de `p`)
void visao_janela_de_previsao(const nucleo::visao::SaidaSeguidor* s, nucleo::visao::ParamsDetetor* p) {
    if (s != nullptr && p != nullptr) nucleo::visao::janela_de_previsao(*s, p);
}

// ------------------------------------------------------------------------------------------ seguidor
int32_t seguidor_criar(void) {
    for (int32_t i = 0; i < kMaxInstancias; ++i) {
        if (!g_seg_usado[i]) {
            g_seg_usado[i] = true;
            return i;
        }
    }
    return -1;
}

void seguidor_liberar(int32_t id) {
    if (id >= 0 && id < kMaxInstancias) g_seg_usado[id] = false;
}

// Configuração por omissão para uma câmara largura×altura com FoV vertical em graus (modelo: 0 α-β · 1 KF-CV · 2 KF-CA)
void seguidor_config_padrao(int32_t largura, int32_t altura, float fovy_graus, int32_t modelo,
                            nucleo::visao::ConfigSeguidor* out) {
    if (out != nullptr) {
        *out = nucleo::visao::config_padrao(static_cast<float>(largura), static_cast<float>(altura), fovy_graus,
                                            modelo);
    }
}

// 1 = Config aceite, 0 = recusada, -1 = instância inválida
int32_t seguidor_iniciar(int32_t id, const nucleo::visao::ConfigSeguidor* cfg) {
    Seguidor* s = obter_seguidor(id);
    if (s == nullptr || cfg == nullptr) return -1;
    return s->iniciar(*cfg) ? 1 : 0;
}

void seguidor_reiniciar(int32_t id) {
    Seguidor* s = obter_seguidor(id);
    if (s != nullptr) s->reiniciar();
}

int32_t seguidor_estado(int32_t id) {
    const Seguidor* s = obter_seguidor(id);
    return s != nullptr ? s->estado() : -1;
}

void seguidor_passo(int32_t id, uint32_t t_us, const nucleo::visao::Atitude* att, const nucleo::visao::Camera* cam,
                    nucleo::visao::SaidaSeguidor* out) {
    Seguidor* s = obter_seguidor(id);
    if (s == nullptr || att == nullptr || cam == nullptr || out == nullptr) return;
    *out = s->passo(t_us, *att, *cam);
}

}  // extern "C"
