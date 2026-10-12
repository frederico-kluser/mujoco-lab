// firmware/cross/verifica_hal.cpp — só compila (nunca corre): confere que hal.hpp é auto-suficiente, que
// uma HAL concreta consegue implementar a interface e que fw::ciclo() compila com os flags do firmware.
#include "../hal.hpp"

namespace {

class HalDeTeste : public fw::Hal {
public:
    uint32_t micros() override { return 0u; }
    bool ler_imu(float giro[3], float acc[3]) override {
        for (int i = 0; i < 3; ++i) {
            giro[i] = 0.0f;
            acc[i] = 0.0f;
        }
        return true;
    }
    bool ler_tof(float* distancia, bool* valido) override {
        *distancia = 1.0f;
        *valido = true;
        return false;
    }
    bool ler_fluxo(float fluxo[2], bool* valido) override {
        fluxo[0] = 0.0f;
        fluxo[1] = 0.0f;
        *valido = true;
        return false;
    }
    float ler_tensao() override { return 22.2f; }
    void escrever_motores(const float u[4]) override { ultimo_ = u[0]; }

private:
    float ultimo_;
};

}  // namespace

float verifica_hal(nucleo::Nucleo& n, nucleo::Sensores& s, const nucleo::Comando& cmd) {
    HalDeTeste hal;
    uint32_t t_ant = hal.micros();
    const nucleo::Saida o = fw::ciclo(hal, n, s, cmd, t_ant);
    return o.motor[0];
}
