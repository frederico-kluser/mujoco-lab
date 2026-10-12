// firmware/hal.hpp — a FRONTEIRA DE HARDWARE do firmware: é o ÚNICO ficheiro que o .ino implementa.
//
// O núcleo (nucleo/) não sabe nada de Arduino: só vê `Sensores` e devolve `Saida`. Tudo o que toca em
// pinos, I²C/SPI, timers e ESC fica atrás desta interface abstrata. No .ino:
//
//     class HalNano33 : public fw::Hal { ... };           // BMI270/BMM150 do Nano 33 BLE, DShot por PWM, …
//     static HalNano33 hal;  static nucleo::Nucleo nuc;  static nucleo::Sensores sens;
//     void setup() { nuc.iniciar(kConfig); nuc.reiniciar(); nuc.armar(true); t_ant = hal.micros(); }
//     void loop()  { if (tick_500hz()) fw::ciclo(hal, nuc, sens, cmd, t_ant); }
//
// Regras: sem heap, sem exceções, sem RTTI; destrutor NÃO virtual (e protegido) — ninguém apaga através
// da base, por isso não há `operator delete` no firmware. Só <stdint.h> + o núcleo.
#pragma once

#include <stdint.h>

#include "nucleo/nucleo.hpp"

namespace fw {

class Hal {
public:
    // tempo monotónico em microssegundos (a volta de uint32_t, ~71 min, é segura em diferenças)
    virtual uint32_t micros() = 0;

    // IMU (≥ 500 Hz): preenche giroscópio (rad/s, corpo) e acelerómetro (m/s²); true = amostra NOVA
    virtual bool ler_imu(float giro[3], float acc[3]) = 0;
    // ToF (~30 Hz): distância (m) e validade; true = amostra NOVA
    virtual bool ler_tof(float* distancia, bool* valido) = 0;
    // fluxo ótico (~100 Hz): (Ωx, Ωy) em rad/s e validade; true = amostra NOVA
    virtual bool ler_fluxo(float fluxo[2], bool* valido) = 0;
    // tensão da bateria (V) — monitor INA226/ADC
    virtual float ler_tensao() = 0;

    // aceleradores [0,1] por motor (a HAL converte para DShot/PWM e trata o armar do ESC)
    virtual void escrever_motores(const float u[4]) = 0;

protected:
    ~Hal() = default;
};

// Lê tudo da HAL para `s`, mantendo a última leitura e os contadores de amostras NOVAS (n_tof, n_fluxo).
inline void atualizar_sensores(Hal& hal, nucleo::Sensores& s) {
    float g[3];
    float a[3];
    if (hal.ler_imu(g, a)) {
        for (int i = 0; i < 3; ++i) {
            s.giro[i] = g[i];
            s.acc[i] = a[i];
        }
    }
    float d = 0.0f;
    bool ok = false;
    if (hal.ler_tof(&d, &ok)) {
        s.tof_d = d;
        s.tof_ok = ok ? 1 : 0;
        s.n_tof = static_cast<int32_t>(static_cast<uint32_t>(s.n_tof) + 1u);  // volta sem UB
    }
    float f[2] = {0.0f, 0.0f};
    if (hal.ler_fluxo(f, &ok)) {
        s.fluxo[0] = f[0];
        s.fluxo[1] = f[1];
        s.fluxo_ok = ok ? 1 : 0;
        s.n_fluxo = static_cast<int32_t>(static_cast<uint32_t>(s.n_fluxo) + 1u);
    }
    s.v_bat = hal.ler_tensao();
}

// UM ciclo do FC: lê os sensores → núcleo → escreve os motores. `t_ant_us` guarda o instante do ciclo
// anterior (inicialize-o com hal.micros() antes do primeiro ciclo); o dt é medido no relógio da HAL.
inline nucleo::Saida ciclo(Hal& hal, nucleo::Nucleo& n, nucleo::Sensores& s, const nucleo::Comando& cmd,
                           uint32_t& t_ant_us) {
    atualizar_sensores(hal, s);
    const uint32_t agora = hal.micros();
    s.t_us = agora;  // o relógio do MCU: a mesma base de `s.camera.t` (a captura do frame), que o IBVS usa para compensar o atraso
    const float dt = static_cast<float>(agora - t_ant_us) * 1e-6f;
    t_ant_us = agora;
    const nucleo::Saida o = n.passo(s, cmd, dt);
    hal.escrever_motores(o.motor);
    return o;
}

}  // namespace fw
