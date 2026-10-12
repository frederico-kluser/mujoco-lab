// firmware/nucleo/nucleo.hpp — a classe Nucleo: estimador + (cascata clássica + olhar) + laço de taxa + mistura,
// tudo `float`, sem heap.
//
// Uso no firmware (o ciclo de 500 Hz; a HAL fica em firmware/hal.hpp):
//
//     static nucleo::Nucleo g_nucleo;              // estado na instância estática — sem heap
//     g_nucleo.iniciar(kConfig);                   // uma vez (Config gerada de sitl.py: config_de_hardware)
//     g_nucleo.reiniciar(); g_nucleo.armar(true);  // ao armar
//     // (estimador clássico) calibra o giroscópio PARADO no chão ≥ 1 s antes de descolar:
//     g_nucleo.calibrar_chao(true); … 500 × passo() com o drone parado … g_nucleo.calibrar_chao(false);
//     g_nucleo.travar_referencias(true, 1.0f);     // trava x, y, ψ, altura e DESCOLA até 1 m (altura do sensor)
//     loop (500 Hz):  s = ler_sensores();  out = g_nucleo.passo(s, cmd, dt);  escrever(out.motor);
//
// ORDEM DO PASSO (cada passo consome UMA leitura de sensores, a mais recente):
//     1. estimador  (atitude, altura, velocidades, odometria)  ← leituras desta chamada
//        [estimador_classico = 1: EstimadorClassico (calibração no chão, portão do acelerómetro, altura 3.ª ordem);
//         0: EstimadorBordo (v1)]
//     2. referências ← Comando, em resolver_modo():
//          CTBR        coletivo (acelerador) + taxas diretos (v1; o caminho da atividade A não mudou)
//          VELOCIDADE  vx, vy, vz (referencial do RUMO) + yaw_taxa → cascata (1× por `cascata.decimacao` passos)
//          YAW_ALVO    idem com rumo absoluto (cmd.yaw)
//          OLHAR       Sensores::camera → Seguidor (IBVS) → vx, vz, yaw_taxa → cascata
//        a cascata produz (empuxo coletivo, taxas); o acelerador é u = u_pair(V_bat)·√coletivo (compensação de tensão)
//     3. laço de taxa (PID p,q,r) + mistura X + airmode → aceleradores dos 4 motores
//     4. saneamento: saída não finita ⇒ motores a 0 + reinício + kFlagFalhaNumerica
// Os passos 1–2 são `planear()` e os 3–4 `atuar()`; `passo()` = atuar(planear()). A divisão existe para o SITL poder
// pôr entre eles o atraso do comando (RPi→FC do simulador) sem tocar no firmware, e para um futuro M7/M4 separado.
// A 1.ª chamada depois de reiniciar() CALIBRA o estimador com a leitura recebida (roll/pitch do acelerómetro, altura
// do ToF) em vez de a integrar — o mesmo que EstimadorBordo.reiniciar(acc, d, ok). Quem calibra explicitamente
// (calibrar(s)) e logo a seguir chama passo() com a MESMA leitura (o SITL faz-o) não a vê integrada duas vezes.
#pragma once

#include <stdint.h>

#include "cascata.hpp"
#include "config.hpp"
#include "estimador.hpp"
#include "estimador_classico.hpp"
#include "ibvs.hpp"
#include "taxa.hpp"
#include "visao_tipos.hpp"

namespace nucleo {

class Nucleo {
public:
    // Copia e valida a Config (false = recusada: Config de outra versão, NaN, fc ≤ 0, …) e reinicia.
    bool iniciar(const Config& cfg);

    // Zera tudo (integrais, filtros, estimador, cascata, seguidor), desarma e marca o estimador para recalibrar.
    void reiniciar();

    // Arma/desarma o laço de taxa E a cascata. Desarmado: motores a 0. Armar zera o integral e as referências da
    // cascata (que travam em x, y, ψ, altura na 1.ª decisão em modo cascata, ou já com travar_referencias()).
    void armar(bool armado);
    bool armado() const { return taxa_.armado(); }

    // Calibra explicitamente o estimador com esta leitura (o 1.º passo() também o faz sozinho). A leitura
    // fica "consumida": se o passo() SEGUINTE trouxer exatamente a mesma leitura não a integra de novo
    // (idempotente); uma leitura diferente é integrada normalmente.
    void calibrar(const Sensores& s);

    // Estimador clássico: abre/fecha a janela de calibração com o drone PARADO no chão (os passos() acumulam o
    // giroscópio e o acelerómetro em vez de integrar; a cascata fica neutra e os motores em idle se armado). Ao
    // fechar: viés do giroscópio, atitude e altura iniciais da média. Sem efeito com estimador_classico = 0.
    void calibrar_chao(bool ativa);

    // Trava as referências da cascata (x, y, ψ, altura) nas estimativas ATUAIS; com `com_z_alvo`, «sobe/desce até
    // z_alvo» (descolar; altura do sensor de baixo, m). Chamar depois da calibração, antes da 1.ª decisão.
    void travar_referencias(bool com_z_alvo, float z_alvo);

    // Um passo do laço (dt em segundos; dt inválido → dt_nominal da Config) = atuar(planear()).
    Saida passo(const Sensores& s, const Comando& c, float dt);

    // Passos 1–2: estimador + laços externos → referências do laço de taxa (preenche em `o` as estimativas e o
    // diagnóstico da cascata/seguidor).
    ReferenciasTaxa planear(const Sensores& s, const Comando& c, float dt, Saida& o);

    // Passos 3–4: laço de taxa + mistura + airmode + saneamento → motores (completa `o`).
    void atuar(const ReferenciasTaxa& ref, const Sensores& s, float dt, Saida& o);

    // Estimativas atuais (motores a 0) — por exemplo logo a seguir a calibrar().
    Saida estimativas() const;

    const Config& config() const { return cfg_; }

private:
    void preencher_estimativas(Saida& o) const;
    float dt_valido(float dt) const;
    float acelerador_de_pairagem(float v_bat) const;
    float acelerador_de_coletivo(float coletivo, float v_bat) const;
    ReferenciasTaxa resolver_modo(const Sensores& s, const Comando& c, float dt, Saida& o, int32_t& flags);

    // Inicializadores constantes e TODOS a zero: seguro também como variável local (pronto_ = false), e uma
    // instância global/estática fica em .bss — sem construtor dinâmico, sem atexit, sem imagem em flash.
    Config cfg_ = {};
    EstimadorBordo est_ = {};
    EstimadorClassico est_cl_ = {};
    ControladorTaxa taxa_ = {};
    Cascata cascata_ = {};
    visao::Seguidor seguidor_ = {};
    visao::SaidaSeguidor saida_seguidor_ = {};
    ReferenciasTaxa ref_ = {};          // referências vigentes (mantidas entre as decisões da cascata)
    Comando cmd_ef_ = {};               // comando EFETIVO da última decisão (o do IBVS em OLHAR)
    Sensores amostra_calibracao_ = {};  // a leitura com que se calibrou (para a idempotência acima)
    float coletivo_ = 0.0f;             // T/(m·g) da última decisão
    float acum_dt_ = 0.0f;              // s — tempo decorrido desde a última decisão da cascata
    int32_t flags_decisao_ = 0;         // flags da última decisão da cascata
    int32_t cont_cascata_ = 0;          // passos desde a última decisão (0 ⇒ a próxima chamada decide)
    int32_t modo_ant_ = 0;              // modo do passo anterior (o IBVS reinicia ao ENTRAR em OLHAR)
    bool tem_modo_ant_ = false;         // (tudo a zero: a instância fica em .bss, sem imagem em flash)
    bool tem_decisao_ = false;          // já houve uma decisão desde o armar (a 1.ª usa decimacao·dt)
    bool pronto_ = false;
    bool calibrado_ = false;
    bool dedupe_pendente_ = false;      // o próximo passo() pode trazer a leitura de calibração repetida
};

}  // namespace nucleo
