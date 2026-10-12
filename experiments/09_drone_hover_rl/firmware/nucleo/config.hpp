// firmware/nucleo/config.hpp — a INTERFACE do núcleo: tipos POD (Config, Sensores, Comando, Saida).
//
// REGRAS DE FIRMWARE (inegociáveis; o teste_nucleo.py audita-as no código e no objeto compilado):
//   · só `float` (nada de `double`; -Wdouble-promotion ligado) e inteiros de <stdint.h>;
//   · SEM alocação dinâmica (new/malloc/std::vector/std::string), SEM exceções, SEM RTTI;
//   · só <stdint.h> e <math.h> (sinf, cosf, atan2f, sqrtf);
//   · SEM dependências Arduino: o hardware fica atrás da HAL (firmware/hal.hpp);
//   · estado em membros da classe (a instância é global/estática no .ino — sem heap).
//
// FORMATO DESTE FICHEIRO (o sitl.py gera as structs de ctypes LENDO estes `struct` — uma só fonte da
// verdade): dentro de um `struct` só linhas `tipo nome;` ou `tipo nome[N];` ou `tipo nome[N][M];`
// (uma declaração por linha), com tipo ∈ {float, int32_t, uint32_t, <enum com tipo fixo declarado aqui>,
// <outro struct já declarado aqui ou em visao_tipos.hpp, com ou sem `visao::`>}. Todos os campos têm 4 bytes
// ⇒ sem padding e o layout é idêntico em x86-64 e em Cortex-M.
// Crescer a interface: ACRESCENTAR campos ao FIM de cada struct e subir kVersaoInterface.
//
// INTERFACE 2 (atividade B — cascata clássica + olhar): ao FIM de cada struct da v1 acrescentou-se
//   · Config   — estimador clássico, cascata (espelho de `GanhosCascata` de controlo_classico.py), seguidor IBVS e
//                a compensação de tensão da bateria; TUDO calculado OFFLINE da planta por sitl.config_de_hardware;
//   · Sensores — relógio do MCU e a Camera do detetor (atividade C);
//   · Comando  — rumo-alvo, altura-alvo (descolar);
//   · Saida    — empuxo/taxas pedidos, velocidade efetiva, estado do IBVS, saturações e diagnóstico da cascata.
// Com `estimador_classico = 0` e `usa_cascata = 0` o núcleo comporta-se EXATAMENTE como na v1 (CTBR).
#pragma once

#include <stdint.h>

#include "visao_tipos.hpp"

namespace nucleo {

constexpr uint32_t kVersaoInterface = 2u;

// Modo de comando. CTBR = o que a política manda ao FC (laço interno direto); VELOCIDADE / YAW_ALVO / OLHAR
// ligam a cascata clássica (velocidade → inclinação+empuxo → atitude → taxas), em resolver_modo().
enum Modo : int32_t {
    CTBR = 0,        // coletivo [0,1] (acelerador) + taxas p,q,r (rad/s) — laço interno direto
    VELOCIDADE = 1,  // vx,vy,vz (m/s) no REFERENCIAL DO RUMO (frente/esquerda/cima) + yaw_taxa (rad/s); v = 0 segura a posição
    OLHAR = 2,       // olhar para o círculo: usa Sensores::camera + IBVS (atividade C) que gera vx, vz e yaw_taxa
    YAW_ALVO = 3     // como VELOCIDADE mas o rumo é absoluto (Comando::yaw, desde o armar) em vez de uma taxa
};

// Bits de Saida::flags.
constexpr int32_t kFlagArmado = 1;          // o laço de taxa está armado
constexpr int32_t kFlagDifEscalado = 2;     // o diferencial não cabia em [idle,1]: foi escalado
constexpr int32_t kFlagAirmodeBaixo = 4;    // airmode: coletivo deslocado para BAIXO (um motor > 1)
constexpr int32_t kFlagAirmodeAlto = 8;     // airmode: coletivo deslocado para CIMA (um motor < idle)
constexpr int32_t kFlagModoReservado = 16;  // modo sem laço disponível (inexistente, ou cascata/visão não configuradas): CTBR
constexpr int32_t kFlagFalhaNumerica = 32;  // saída não finita: motores a 0, estado reiniciado
constexpr int32_t kFlagNaoIniciado = 64;    // passo() sem iniciar() válido: motores a 0
constexpr int32_t kFlagSatInclinacao = 128;   // a inclinação pedida passou de tilt_max: aceleração horizontal escalada
constexpr int32_t kFlagSatYawTaxa = 256;      // o pedido de yaw passou do teto de taxa (taxa_yaw_max)
constexpr int32_t kFlagSatYawAcel = 512;      // o yaw está limitado em aceleração (acel_yaw_max)
constexpr int32_t kFlagSatColetivo = 1024;    // o empuxo coletivo foi cortado a [coletivo_min, coletivo_max]
constexpr int32_t kFlagCalibrando = 2048;     // janela de calibração no chão aberta (estimador clássico)
constexpr int32_t kFlagFalhaCascata = 4096;   // entrada da cascata não finita: manteve-se a última saída boa
constexpr int32_t kFlagSatTaxaRP = 8192;      // taxa p/q cortada a taxa_rp_max

// Estimador clássico (estimador_classico.hpp): calibração do giroscópio no chão, portão do acelerómetro,
// observador de altura de 3.ª ordem. Espelha as opções do EstimadorClassico de controlo_classico.py.
struct ConfigEstimadorClassico {
    int32_t cal_giro;        // 1 = tira o viés do giroscópio (média da janela de calibração parado no chão)
    int32_t portao_acc;      // 1 = o ganho do acelerómetro cai com 1/(1+(‖a_h‖/a_portao)²) ao acelerar
    float a_portao;          // m/s² — aceleração horizontal a que o ganho do acelerómetro cai a metade
    float tau_acc_portao;    // s — PT1 que dá a aceleração horizontal estimada ao portão
    int32_t bias_acc_z;      // 1 = observador de altura de 3.ª ordem (estima o viés do acelerómetro vertical)
    float ki_mahony;         // /s² — parte integral de Mahony sobre roll/pitch (0 = desligada: medido que não ajuda)
    float lim_bias_acc;      // m/s² — |viés do acelerómetro vertical| ≤
    float lim_bias_pi;       // rad/s — |viés de p,q do integral de Mahony| ≤
};

// Cascata clássica (cascata.hpp). Espelha `GanhosCascata` (controlo_classico.py): MESMOS nomes e unidades.
// Calculada OFFLINE da planta por `ganhos_de_hardware` → sitl.config_de_hardware. NADA aqui é «afinado» no C++.
struct ConfigCascata {
    int32_t decimacao;       // o laço externo corre 1× por `decimacao` passos do núcleo (10 ⇒ 50 Hz com 500 Hz)
    // --- atitude (prioridade de inclinação) e yaw
    float k_att;             // s⁻¹ — P de inclinação (roll/pitch)
    float k_yaw;             // s⁻¹ — P de yaw a «cheio» (o efetivo é peso_yaw·k_yaw)
    float peso_yaw;          // (0, 1] — como MC_YAW_WEIGHT
    float taxa_rp_max;       // rad/s — teto das taxas p, q
    float taxa_yaw_max;      // rad/s — teto da taxa de yaw (equilíbrio com o arrasto)
    float acel_yaw_max;      // rad/s² — teto da aceleração de yaw
    float u_yaw_por_taxa;    // (acelerador diferencial)/(rad/s) de yaw em equilíbrio (identificado no simulador)
    float alfa_yaw;          // rad/s² por unidade de acelerador diferencial (yaw)
    float u_pairagem;        // acelerador de pairagem nominal
    float avanco_yaw_max;    // rad — avanço máximo da referência de rumo sobre o rumo medido
    // --- velocidade horizontal (saída = aceleração) e posição
    float k_vel;             // s⁻¹
    float ki_vel;            // s⁻²
    float kd_vel;            // s (D sobre a medida filtrada; 0 = desligado)
    float tau_d_vel;         // s — filtro do termo D
    float k_pos;             // s⁻¹
    float avanco_pos_max;    // m — avanço máximo da referência de posição sobre a medida
    float vel_corr_pos_max;  // m/s — teto da correção de velocidade pelo erro de posição
    float acc_pos;           // m/s² — aceleração da aproximação raiz-quadrada
    // --- vertical
    float k_pz;              // s⁻¹
    float k_vz;              // s⁻¹
    float ki_vz;             // s⁻²
    float vel_corr_z_max;    // m/s
    // --- limites
    float tilt_max;          // rad
    float coletivo_min;      // T/(m·g)
    float coletivo_max;      // T/(m·g)
    float vel_xy_max;        // m/s
    float vel_z_max;         // m/s
    float vel_goto_z;        // m/s — velocidade máxima de «ir até z_alvo» (descolar)
    float altura_min;        // m (do SENSOR de baixo) — piso de altitude em voo
    float altura_max;        // m (do SENSOR de baixo) — teto de altitude
    // --- conformador dos comandos (acelera/jerk-limitado), no referencial do rumo
    float acc_cmd_xy;        // m/s²
    float jerk_cmd_xy;       // m/s³
    float k_conf;            // s⁻¹
    float k_conf_z;          // s⁻¹
    float tau_modelo_z;      // s (0 = sem modelo vertical)
    float acc_cmd_z;         // m/s²
    float jerk_cmd_z;        // m/s³
    int32_t ref_posicao_trava;  // 1 = «trava» (p_sp = p̂ em movimento, trava ao parar: PX4); 0 = «integrada»
    float tau_modelo;        // s — atraso do modelo de seguimento da malha de atitude
    float k_ff_acc;          // escala do feed-forward da aceleração conformada
    float k_arrasto;         // s⁻¹ — feed-forward do arrasto linear
    float aw_ganho;          // anti-windup por retro-cálculo: k_aw = aw_ganho/K_vel
    int32_t ff_atitude;      // 1 = feed-forward da taxa de inclinação (n̂ × dn̂/dt)
    float tau_ff;            // s — filtro da derivada de n̂
    int32_t comp_yaw_empuxo; // 1 = pré-compensa o empuxo extra do diferencial de yaw
    float comp_yaw_acel;     // peso do termo de aceleração de yaw nessa compensação
    float g;                 // m/s²
    // --- constantes que o protótipo Python tem como literais (aqui também vêm da Config, nunca do código)
    float lim_i_vel;         // m/s² — |integral da velocidade horizontal| ≤
    float lim_i_z;           // fração de g — |integral vertical| ≤ lim_i_z·g
    float tol_alvo_z;        // m — «chegou» à altura-alvo
    float tol_alvo_vz;       // m/s — e a velocidade vertical conformada já é desprezável
    float v_trava;           // m/s — |v_sp horizontal| acima disto = em movimento (a referência de posição segue a medida)
    float fz_min_frac;       // fração de g — a força específica vertical desejada nunca desce disto (empuxo ≥ 0)
    float cos_incl_min;      // cosφ·cosθ abaixo disto: sem correção do corpo para o rumo (quase de cabeça para baixo)
};

// O que o laço de planeamento (estimador + laços externos) entrega ao laço de taxa. Fica na interface para o
// SITL poder pôr um atraso entre os dois (o RPi→FC do simulador) sem tocar no firmware.
struct ReferenciasTaxa {
    float acelerador;        // [0,1] acelerador coletivo (já com a compensação de tensão no modo cascata)
    float taxas[3];          // rad/s — setpoints de p, q, r
    int32_t flags;           // bits kFlag* levantados no planeamento
};

// Parâmetros do núcleo. Calculados OFFLINE da planta (sitl.py: config_de_hardware) e gravados no .ino.
struct Config {
    uint32_t versao;         // = kVersaoInterface (iniciar() recusa uma Config de outra versão)
    float dt_nominal;        // s — período nominal do laço (usado se o dt do passo for inválido)

    // --- laço de taxa, por eixo (p, q, r): u_eixo = kp·erro + I − kd·d(giro_f)/dt   [fração de acelerador]
    float kp[3];
    float ki[3];
    float kd[3];
    float limite_i;          // anti-windup: |I| ≤ limite_i (fração de acelerador)
    float fc_giro_hz;        // PT1 no giroscópio
    float fc_d_hz;           // PT1 no termo D
    float idle;              // acelerador mínimo com o FC armado
    float mix[4][3];         // mistura X: motor_i = coletivo + Σ_eixo mix[i][eixo]·u_eixo
    float u_pairagem;        // acelerador de pairagem NOMINAL (informativo; usado pelos laços externos)

    // --- estimador de bordo
    float gravidade;         // m/s²
    float k_atitude;         // 1/s — peso do acelerómetro no filtro complementar
    float w_altura;          // rad/s — banda do observador de altura
    float zeta_altura;       // amortecimento do observador de altura
    float periodo_tof_min;   // s — período mínimo assumido entre amostras do ToF (1/30)
    float alfa_fluxo;        // PT1 da velocidade do fluxo, por amostra nova
    float decai_fluxo;       // decaimento por passo sem fluxo/ToF válidos

    // --- interface 2 (atividade B). Com estimador_classico = 0 e usa_cascata = 0 tudo isto é ignorado (v1).
    int32_t estimador_classico;  // 0 = EstimadorBordo (v1) · 1 = EstimadorClassico (calibração no chão, portão, altura 3.ª ordem)
    ConfigEstimadorClassico est_cl;
    int32_t usa_cascata;     // 1 = `cascata` válida: VELOCIDADE / YAW_ALVO / OLHAR disponíveis
    ConfigCascata cascata;
    int32_t usa_visao;       // 1 = `seguidor` válido: OLHAR disponível
    visao::ConfigSeguidor seguidor;
    // compensação de tensão da bateria: u_pair(V) = ESC⁻¹(upv_k / V) — o ciclo útil que sustenta a pairagem é
    // duty = upv_k/V (K = K_e·ω + R·I em regime) e o ESC mapeia acelerador → duty por uma curva linear por troços
    // (esc_d[i] → esc_u[i], i < n_esc, crescente). O acelerador do modo cascata é u = u_pair(V)·√(empuxo coletivo).
    float upv_k;             // V — K do ciclo útil de pairagem
    int32_t n_esc;           // nº de nós da curva do ESC (2..16)
    float esc_d[16];         // ciclo útil nos nós da curva
    float esc_u[16];         // acelerador nos mesmos nós
    float v_bat_valida_min;  // V — monitor abaixo disto = inválido ⇒ usa o u_pairagem nominal
};

// Leituras MEDIDAS (com erro) dos sensores, como o FC as vê.
struct Sensores {
    float giro[3];           // rad/s, frame do corpo
    float acc[3];            // m/s² (força específica; +g em z em repouso)
    float tof_d;             // m — distância medida pelo ToF (ao longo do eixo do sensor)
    int32_t tof_ok;          // 1 = leitura válida
    int32_t n_tof;           // contador de amostras do ToF (muda quando há amostra NOVA)
    float fluxo[2];          // rad/s — fluxo ótico (Ωx, Ωy)
    int32_t fluxo_ok;        // 1 = leitura válida
    int32_t n_fluxo;         // contador de amostras do fluxo
    float v_bat;             // V — tensão da bateria (monitor); usada pela compensação de tensão do modo cascata
    uint32_t t_us;           // µs — relógio monotónico do MCU neste passo (a MESMA base de camera.t; só diferenças)
    visao::Camera camera;    // última medida do detetor (atividade C): só conta quando camera.n muda
};

// O que se pede ao núcleo neste passo.
struct Comando {
    Modo modo;               // CTBR · VELOCIDADE · OLHAR · YAW_ALVO
    float coletivo;          // [0,1] acelerador coletivo (CTBR)
    float taxas[3];          // rad/s — setpoints de p, q, r (CTBR)
    float vx;                // m/s — frente, NO REFERENCIAL DO RUMO (VELOCIDADE / YAW_ALVO)
    float vy;                // m/s — esquerda
    float vz;                // m/s — cima
    float yaw_taxa;          // rad/s — + anti-horário visto de cima (VELOCIDADE)
    float yaw;               // rad — rumo absoluto desde o armar (YAW_ALVO)
    float z_alvo;            // m — altura (do sensor de baixo) a atingir, p.ex. DESCOLAR; só conta se tem_z_alvo
    int32_t tem_z_alvo;      // 1 = z_alvo válido neste comando
};

// O que o núcleo devolve: acelerador por motor + estimativas + diagnóstico.
struct Saida {
    float motor[4];          // acelerador por motor [0,1]: r1 frente-esq, r2 trás-dir, r3 trás-esq, r4 frente-dir
    float roll;              // rad
    float pitch;             // rad
    float psi;               // rad — rumo desde o armar (integrado, sem magnetómetro)
    float h;                 // m — altura (ToF + acelerómetro)
    float vz;                // m/s
    float vx;                // m/s — no corpo (fluxo)
    float vy;                // m/s
    float x;                 // m — odometria no frame de arranque
    float y;                 // m
    float giro_f[3];         // rad/s — giroscópio filtrado (diagnóstico)
    float u_eixos[3];        // saída do PID por eixo antes da mistura (diagnóstico)
    int32_t flags;           // bits kFlag*
    // --- interface 2: a cascata e o olhar
    float coletivo;          // T/(m·g) pedido pela cascata (1,0 = pairagem; 0 fora do modo cascata)
    float acelerador;        // acelerador coletivo [0,1] entregue ao laço de taxa
    float taxas_ref[3];      // rad/s — p, q, r pedidos ao laço de taxa
    float v_ref[3];          // m/s — velocidade EFETIVA recebida pela cascata (referencial do rumo): o comando ou o IBVS
    float yaw_taxa_ref;      // rad/s — taxa de yaw efetiva recebida pela cascata
    visao::SaidaSeguidor seguidor;  // estado do IBVS (A_SEGUIR…), erros, previsão — só em OLHAR
    // diagnóstico da cascata (espelha `CascataClassica.dados` do protótipo Python)
    float a_des[3];          // m/s² — aceleração desejada (mundo)
    float n_des[3];          // direção desejada do empuxo
    float e_tilt[2];         // rad — erro de inclinação (e_x, e_y)
    float gama;              // rad — erro de yaw (após a prioridade de inclinação)
    float v_h[2];            // m/s — velocidade medida no referencial do rumo
    float v_o[2];            // m/s — velocidade medida no referencial de arranque
    float v_sp_h[2];         // m/s — velocidade conformada (referencial do rumo)
    float p_sp[2];           // m — referência de posição
    float z_sp;              // m — referência de altura
    float psi_sp;            // rad — referência de rumo
    float r_ref;             // rad/s — taxa de yaw conformada
    float i_vel[2];          // m/s² — integrais da velocidade horizontal
    float i_z;               // m/s² — integral vertical
};

// --- utilitários numéricos básicos (sem libm: com -ffreestanding o compilador NÃO inlina fabsf/sqrtf)
constexpr float kPi = 3.14159265358979323846f;

inline bool e_finito(float x) { return (x - x) == 0.0f; }  // falso para NaN e ±inf
inline float absf(float x) { return x < 0.0f ? -x : x; }
inline float limita(float x, float lo, float hi) { return x < lo ? lo : (x > hi ? hi : x); }

// Config do estimador clássico utilizável?
inline bool config_est_cl_valida(const ConfigEstimadorClassico& e) {
    bool ok = e_finito(e.a_portao) && e.a_portao > 0.0f && e_finito(e.tau_acc_portao) && e.tau_acc_portao > 0.0f;
    ok = ok && e_finito(e.ki_mahony) && e.ki_mahony >= 0.0f;
    ok = ok && e_finito(e.lim_bias_acc) && e.lim_bias_acc >= 0.0f && e_finito(e.lim_bias_pi) && e.lim_bias_pi >= 0.0f;
    return ok;
}

// Config da cascata utilizável? (finitos, limites e ganhos coerentes)
inline bool config_cascata_valida(const ConfigCascata& c) {
    bool ok = c.decimacao >= 1 && c.decimacao <= 1000;
    ok = ok && e_finito(c.k_att) && c.k_att > 0.0f && e_finito(c.k_yaw) && c.k_yaw >= 0.0f;
    ok = ok && e_finito(c.peso_yaw) && c.peso_yaw > 0.0f && c.peso_yaw <= 1.0f;
    ok = ok && e_finito(c.taxa_rp_max) && c.taxa_rp_max > 0.0f;
    ok = ok && e_finito(c.taxa_yaw_max) && c.taxa_yaw_max > 0.0f && e_finito(c.acel_yaw_max) && c.acel_yaw_max > 0.0f;
    ok = ok && e_finito(c.u_yaw_por_taxa) && e_finito(c.alfa_yaw) && c.alfa_yaw > 0.0f;
    ok = ok && e_finito(c.u_pairagem) && c.u_pairagem > 0.0f && e_finito(c.avanco_yaw_max);
    ok = ok && e_finito(c.k_vel) && c.k_vel > 0.0f && e_finito(c.ki_vel) && c.ki_vel >= 0.0f;
    ok = ok && e_finito(c.kd_vel) && c.kd_vel >= 0.0f && e_finito(c.tau_d_vel) && c.tau_d_vel > 0.0f;
    ok = ok && e_finito(c.k_pos) && c.k_pos > 0.0f && e_finito(c.avanco_pos_max) && c.avanco_pos_max > 0.0f;
    ok = ok && e_finito(c.vel_corr_pos_max) && c.vel_corr_pos_max >= 0.0f && e_finito(c.acc_pos) && c.acc_pos > 0.0f;
    ok = ok && e_finito(c.k_pz) && c.k_pz > 0.0f && e_finito(c.k_vz) && c.k_vz > 0.0f;
    ok = ok && e_finito(c.ki_vz) && c.ki_vz >= 0.0f && e_finito(c.vel_corr_z_max) && c.vel_corr_z_max >= 0.0f;
    ok = ok && e_finito(c.tilt_max) && c.tilt_max > 0.0f && c.tilt_max < 1.5f;  // < ~86°: tan(tilt) finito
    ok = ok && e_finito(c.coletivo_min) && c.coletivo_min >= 0.0f && e_finito(c.coletivo_max);
    ok = ok && c.coletivo_max > c.coletivo_min;
    ok = ok && e_finito(c.vel_xy_max) && c.vel_xy_max > 0.0f && e_finito(c.vel_z_max) && c.vel_z_max > 0.0f;
    ok = ok && e_finito(c.vel_goto_z) && c.vel_goto_z > 0.0f;
    ok = ok && e_finito(c.altura_min) && e_finito(c.altura_max) && c.altura_max > c.altura_min;
    ok = ok && e_finito(c.acc_cmd_xy) && c.acc_cmd_xy > 0.0f && e_finito(c.jerk_cmd_xy) && c.jerk_cmd_xy > 0.0f;
    ok = ok && e_finito(c.k_conf) && c.k_conf > 0.0f && e_finito(c.k_conf_z) && c.k_conf_z > 0.0f;
    ok = ok && e_finito(c.tau_modelo_z) && c.tau_modelo_z >= 0.0f && e_finito(c.tau_modelo) && c.tau_modelo >= 0.0f;
    ok = ok && e_finito(c.acc_cmd_z) && c.acc_cmd_z > 0.0f && e_finito(c.jerk_cmd_z) && c.jerk_cmd_z > 0.0f;
    ok = ok && e_finito(c.k_ff_acc) && e_finito(c.k_arrasto) && e_finito(c.aw_ganho) && c.aw_ganho >= 0.0f;
    ok = ok && e_finito(c.tau_ff) && c.tau_ff > 0.0f && e_finito(c.comp_yaw_acel);
    ok = ok && e_finito(c.g) && c.g > 0.0f;
    ok = ok && e_finito(c.lim_i_vel) && c.lim_i_vel >= 0.0f && e_finito(c.lim_i_z) && c.lim_i_z >= 0.0f;
    ok = ok && e_finito(c.tol_alvo_z) && c.tol_alvo_z >= 0.0f && e_finito(c.tol_alvo_vz) && c.tol_alvo_vz >= 0.0f;
    ok = ok && e_finito(c.v_trava) && c.v_trava >= 0.0f;
    ok = ok && e_finito(c.fz_min_frac) && c.fz_min_frac > 0.0f && c.fz_min_frac < 1.0f;
    ok = ok && e_finito(c.cos_incl_min) && c.cos_incl_min > 0.0f && c.cos_incl_min < 1.0f;
    return ok;
}

// Config utilizável? (versão certa, números finitos, frequências/limites coerentes). A validade do `seguidor` é
// conferida por Nucleo::iniciar (o IBVS tem a sua própria validação em ibvs.hpp).
inline bool config_valida(const Config& c) {
    if (c.versao != kVersaoInterface) return false;
    bool ok = e_finito(c.dt_nominal) && c.dt_nominal > 0.0f;
    ok = ok && e_finito(c.limite_i) && c.limite_i >= 0.0f;
    ok = ok && e_finito(c.fc_giro_hz) && c.fc_giro_hz > 0.0f;
    ok = ok && e_finito(c.fc_d_hz) && c.fc_d_hz > 0.0f;
    ok = ok && e_finito(c.idle) && c.idle >= 0.0f && c.idle < 1.0f;
    ok = ok && e_finito(c.u_pairagem) && e_finito(c.gravidade) && c.gravidade > 0.0f;
    ok = ok && e_finito(c.k_atitude) && e_finito(c.w_altura) && e_finito(c.zeta_altura);
    ok = ok && e_finito(c.periodo_tof_min) && c.periodo_tof_min > 0.0f;
    ok = ok && e_finito(c.alfa_fluxo) && e_finito(c.decai_fluxo);
    for (int e = 0; e < 3; ++e) ok = ok && e_finito(c.kp[e]) && e_finito(c.ki[e]) && e_finito(c.kd[e]);
    for (int i = 0; i < 4; ++i)
        for (int e = 0; e < 3; ++e) ok = ok && e_finito(c.mix[i][e]);
    // interface 2
    ok = ok && (c.estimador_classico == 0 || c.estimador_classico == 1);
    ok = ok && (c.usa_cascata == 0 || c.usa_cascata == 1) && (c.usa_visao == 0 || c.usa_visao == 1);
    if (c.estimador_classico == 1) ok = ok && config_est_cl_valida(c.est_cl);
    if (c.usa_cascata == 1) {
        ok = ok && config_cascata_valida(c.cascata);
        ok = ok && e_finito(c.upv_k) && c.upv_k > 0.0f && c.n_esc >= 2 && c.n_esc <= 16;
        ok = ok && e_finito(c.v_bat_valida_min);
        for (int k = 0; ok && k < c.n_esc; ++k) {
            ok = ok && e_finito(c.esc_d[k]) && e_finito(c.esc_u[k]) && c.esc_d[k] >= 0.0f;
            if (k > 0) ok = ok && c.esc_d[k] > c.esc_d[k - 1] && c.esc_u[k] >= c.esc_u[k - 1];
        }
    }
    return ok;
}

}  // namespace nucleo
