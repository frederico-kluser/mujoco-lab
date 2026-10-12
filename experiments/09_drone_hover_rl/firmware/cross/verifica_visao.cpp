// firmware/cross/verifica_visao.cpp — só compila (nunca corre): instancia a cadeia de visão COMPLETA (detetor →
// Camera → Seguidor → janela de busca) com os flags do firmware, para o teste_visao.py medir tamanho/RAM e
// auditar os símbolos do objeto cross-compilado (Cortex-M4/M7). As instâncias são GLOBAIS: têm de cair em .bss.
#include "../nucleo/alvo.hpp"
#include "../nucleo/ibvs.hpp"
#include "../nucleo/visao.hpp"

namespace {

nucleo::visao::Detetor g_detetor;
nucleo::visao::Seguidor g_seguidor;
bool g_iniciado;

}  // namespace

// um ciclo de visão: frame mono → deteção → Camera → passo do seguidor → janela do próximo frame
nucleo::visao::SaidaSeguidor verifica_visao(const uint8_t* frame, int32_t largura, int32_t altura, uint32_t t_us,
                                            int32_t n, const nucleo::visao::Atitude& att,
                                            nucleo::visao::ParamsDetetor& params,
                                            const nucleo::visao::ConfigSeguidor& cfg) {
    if (!g_iniciado) g_iniciado = g_seguidor.iniciar(cfg);
    const nucleo::visao::Deteccao d = g_detetor.detetar(frame, largura, altura, 0, params);
    const nucleo::visao::Camera cam = nucleo::visao::camera_de(d, n, t_us);
    const nucleo::visao::SaidaSeguidor s = g_seguidor.passo(t_us, att, cam);
    nucleo::visao::janela_de_previsao(s, &params);
    return s;
}
