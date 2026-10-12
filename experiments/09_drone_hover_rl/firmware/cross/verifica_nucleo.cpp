// firmware/cross/verifica_nucleo.cpp — só compila (nunca corre): instancia o NÚCLEO COMPLETO e a cadeia de visão (frame mono → detetor →
// Camera → Sensores → Nucleo em OLHAR → motores) com os flags do firmware, para o teste_cascata_nucleo.py medir tamanho/RAM e auditar os
// símbolos do objeto cross-compilado (Cortex-M4/M7). As instâncias são GLOBAIS: têm de cair em .bss (sem imagem em flash).
#include "../nucleo/nucleo.hpp"
#include "../nucleo/visao.hpp"

namespace {

nucleo::Nucleo g_nucleo;
nucleo::visao::Detetor g_detetor;
bool g_iniciado;

}  // namespace

// um ciclo de 500 Hz do firmware completo; `frame` (largura×altura, uint8) só é processado quando `n_frame` mudou
nucleo::Saida verifica_nucleo(const uint8_t* frame, int32_t largura, int32_t altura, int32_t n_frame, uint32_t t_captura_us,
                              nucleo::Sensores& s, const nucleo::Comando& cmd, float dt, const nucleo::Config& cfg) {
    if (!g_iniciado) g_iniciado = g_nucleo.iniciar(cfg);
    if (frame != nullptr && n_frame != s.camera.n) {
        const nucleo::visao::ParamsDetetor params = nucleo::visao::params_padrao(largura, altura);
        const nucleo::visao::Deteccao d = g_detetor.detetar(frame, largura, altura, 0, params);
        s.camera = nucleo::visao::camera_de(d, n_frame, t_captura_us);
    }
    return g_nucleo.passo(s, cmd, dt);
}
