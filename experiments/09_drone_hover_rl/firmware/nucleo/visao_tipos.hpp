// firmware/nucleo/visao_tipos.hpp — a INTERFACE da atividade C («olhar para o círculo»): tipos POD.
//
// Quem os usa:
//   · visao.hpp   Detetor        — frame mono uint8 → Deteccao (limiar + momentos)       [corre no M7 / MCU de visão]
//   · alvo.hpp    FiltroAlvo     — α-β / KF-CV / KF-CA do bearing do alvo + histórico de atitude + atraso
//   · ibvs.hpp    Seguidor       — lei IBVS (yaw + v_y ← u, v_z ← v, v_x ← distância) + máquina de estados de perda
//   · capi_visao.cpp             — wrappers extern "C" para o SITL (ctypes) — NÃO entra no .ino
//
// MESMAS REGRAS do núcleo (config.hpp): só `float` + inteiros de <stdint.h>, sem heap/exceções/RTTI, só
// <math.h> (sinf cosf atan2f sqrtf). Compila em C++11/14/17/20.
//
// FORMATO (o sitl_visao.py gera as structs de ctypes LENDO estes `struct` — uma só fonte da verdade): dentro de
// um `struct` só linhas `tipo nome;` ou `tipo nome[N];` (uma por linha), tipo ∈ {float, int32_t, uint32_t,
// <enum com tipo fixo declarado aqui>}. Todos os campos têm 4 bytes ⇒ sem padding, layout idêntico em x86-64 e
// em Cortex-M. Crescer a interface: ACRESCENTAR campos ao FIM e subir kVersaoVisao.
//
// Namespace próprio (nucleo::visao): não colide com nucleo::Comando/Sensores/Saida do núcleo de voo.
#pragma once

#include <stdint.h>

// -DNUCLEO_VISAO_NOINLINE separa as funções de trabalho (kernels) para o llvm-mca; sem a macro inlinam normalmente.
#ifdef NUCLEO_VISAO_NOINLINE
#define NUCLEO_VISAO_KERNEL __attribute__((noinline))
#else
#define NUCLEO_VISAO_KERNEL
#endif

namespace nucleo {
namespace visao {

// VERSÃO 2 (modo «seguir a bola», 2026-10-12): ao FIM de ConfigSeguidor — translação lateral (v_y), compensação da translação
// própria no filtro do alvo e da inclinação do corpo no canal vertical; ao FIM de SaidaSeguidor — o erro NA IMAGEM e a
// velocidade estimada do alvo (para o HUD). Com os campos novos a 0 a lei é EXATAMENTE a da versão 1.
constexpr uint32_t kVersaoVisao = 2u;

// Estado da máquina de perda do seguidor.
enum Estado : int32_t {
    A_SEGUIR = 0,     // deteções a chegar: lei IBVS completa com a previsão do alvo
    EM_FALTA = 1,     // sem deteção há ≤ t_falta_s: segue a PREVISÃO (v decai para 0)
    PERDIDO = 2,      // sem deteção há > t_falta_s: v = 0 e procura lenta de yaw para o último lado
    REAQUISICAO = 3   // viu o alvo outra vez: confirma n_reaq deteções seguidas (histerese) antes de A_SEGUIR
};

// Modelo do estimador do alvo (por canal: azimute, elevação, raio normalizado).
enum ModeloAlvo : int32_t {
    ALFA_BETA = 0,    // ganhos fixos α, β (posição + taxa)
    KF_CV = 1,        // Kalman de velocidade constante (aceleração branca)
    KF_CA = 2         // Kalman de aceleração constante (jerk branco) — dá também a aceleração (avanço de fase)
};

// Porque é que o detetor recusou (Deteccao::motivo).
enum Motivo : int32_t {
    M_OK = 0,
    M_SEM_ALVO = 1,        // contraste (máx − fundo) abaixo de contraste_min: nada brilha
    M_SEM_BLOB = 2,        // nenhum píxel acima do limiar
    M_AREA = 3,            // área fora de [area_min, area_max]
    M_CIRCULARIDADE = 4,   // alongado (razão dos valores próprios < circ_min)
    M_CHEIO = 5,           // r_momentos/r_área fora de [cheio_min, cheio_max] (anel, dispersão, ...)
    M_BORDA = 6,           // toca o bordo da imagem (alvo parcialmente fora do FOV: centróide enviesado)
    M_JANELA = 7,          // cortado pela janela de busca (ROI): a janela é pequena demais
    M_PARAMETROS = 8       // frame/janela/parâmetros inválidos
};

// Bits de SaidaSeguidor::flags.
constexpr int32_t kFlagNaoIniciado = 1;       // passo() sem iniciar() válido: comando nulo
constexpr int32_t kFlagEntradaInvalida = 2;   // atitude/tempo não finitos: entrada ignorada
constexpr int32_t kFlagFalhaNumerica = 4;     // estado/saída não finitos: filtro reposto, comando nulo
constexpr int32_t kFlagHistoricoCurto = 8;    // a captura é mais antiga que o histórico de atitude (usa a mais antiga)
constexpr int32_t kFlagTempoInvalido = 16;    // Camera.t absurdo: usou-se t_agora − atraso_nominal_s
constexpr int32_t kFlagOutlier = 32;          // a medida deste frame foi recusada pelo gate de inovação
constexpr int32_t kFlagReinicioFiltro = 64;   // o filtro foi reiniciado com esta medida
constexpr int32_t kFlagProcuraEsgotada = 128; // PERDIDO há > t_procura_max_s: a procura parou (supervisor decide)
constexpr int32_t kFlagSaturouYaw = 256;      // yaw_taxa no limite (yaw_max ou slew)
constexpr int32_t kFlagSaturouLateral = 512;  // v_y no limite (vy_max ou slew)

// ----------------------------------------------------------------------------------------- medida da câmara
// O QUE O DETETOR ENTREGA AO NÚCLEO DE VOO (por frame). É a struct que o núcleo terá de aceitar (ver README):
// no Portenta H7 o M7 (visão) preenche-a e o M4 (voo) lê-a — memória partilhada/RPC — ou o mesmo MCU chama
// Seguidor::passo(). Convenção de píxeis: ÍNDICE (o centro do píxel (0,0) é (0,0); eixo óptico em ((W−1)/2, (H−1)/2)).
struct Camera {
    int32_t valido;        // 1 = deteção válida neste frame; 0 = nada/rejeitada (u, v, raio ignorados)
    float u;               // px — centróide pesado pela intensidade (sub-píxel), + para a DIREITA
    float v;               // px — + para BAIXO
    float raio;            // px — raio equivalente √(área/π)
    int32_t n;             // contador de frames processados: muda a cada frame NOVO (válido ou não)
    uint32_t t;            // µs — instante da CAPTURA (relógio monotónico do MCU; só se usam diferenças, volta a 71 min)
};

// Parâmetros do detetor (por modo de câmara: dependem da resolução e do tamanho do alvo).
struct ParamsDetetor {
    float frac_max;        // limiar adaptativo = fundo + frac_max·(máx − fundo)   (0,5 = a meia-altura da borda)
    int32_t contraste_min; // (máx robusto − fundo) mínimo para haver alvo (níveis de cinzento)
    int32_t paso_max;      // a 1.ª passagem (máx) lê 1 linha em cada paso_max (1 = todas)
    float area_min;        // px
    float area_max;        // px
    float circ_min;        // λ_min/λ_max dos momentos centrais ≥ circ_min (1 = disco; ~0 = linha)
    float cheio_min;       // r_momentos/r_área ≥ cheio_min
    float cheio_max;       // r_momentos/r_área ≤ cheio_max
    int32_t margem_borda;  // blob a < margem_borda px do bordo da imagem é recusado (0 = não verifica)
    int32_t roi_x0;        // janela de busca [x0,x1)×[y0,y1) em px; roi_x1 ≤ 0 ou roi_y1 ≤ 0 = imagem inteira
    int32_t roi_y0;
    int32_t roi_x1;
    int32_t roi_y1;
    float k_ruido;         // exige (máx − fundo) ≥ k_ruido·σ̂, com σ̂ = ruído estimado nas diferenças da grelha (0 = desliga)
};

// Resultado da deteção num frame.
struct Deteccao {
    int32_t valido;        // 1 = há um disco que passa todos os gates
    float u;               // px (índice) — centróide pesado pela intensidade
    float v;               // px
    float raio_px;         // √(área/π)
    float circularidade;   // λ_min/λ_max ∈ [0,1]
    float area;            // px — nº de píxeis acima do limiar no blob
    float cheio;           // r_momentos/r_área (≈ 1 num disco)
    int32_t motivo;        // Motivo (M_OK se válido)
    int32_t limiar;        // limiar usado (0–255)
    int32_t vmax;          // máximo robusto da 1.ª passagem (0 com limiar fixo)
    int32_t fundo;         // nível de fundo estimado (0 com limiar fixo)
    int32_t n_blobs;       // blobs avaliados
    int32_t excesso;       // 1 = houve componentes/runs deitados fora por falta de capacidade (cena muito suja)
    float ruido;           // σ̂ — ruído estimado (níveis de cinzento; 0 com limiar fixo)
};

// ----------------------------------------------------------------------------------------- estimativas e comando
// O que o seguidor lê do estimador de bordo (nucleo::Saida): atitude e velocidade no corpo, NO INSTANTE ATUAL.
struct Atitude {
    float roll;            // rad
    float pitch;           // rad (+ = nariz para baixo, convenção ZYX do estimador)
    float psi;             // rad — rumo desde o armar (deriva com o viés do giro)
    float vx;              // m/s — frente, no corpo
    float vy;              // m/s — esquerda
    float vz;              // m/s — cima
};

// O COMANDO DE SAÍDA que o núcleo de voo terá de aceitar (cascata B0): velocidades NO REFERENCIAL DO RUMO
// (só yaw: x = frente, y = esquerda, z = cima) e taxa de guinada. nucleo::Comando já tem os 4 campos reservados.
struct ComandoVoo {
    float vx;              // m/s — frente (|v_xy| ≤ 1)
    float vy;              // m/s — esquerda (0 na lei da versão 1; a translação lateral do «seguir a bola» na 2)
    float vz;              // m/s — cima (|v_z| ≤ 0,7)
    float yaw_taxa;        // rad/s — + anti-horário visto de cima
};

// Parâmetros do seguidor (estimador + lei + máquina de estados). Os defaults vêm de config_padrao() (ibvs.hpp).
struct ConfigSeguidor {
    uint32_t versao;       // = kVersaoVisao
    // --- câmara e alvo
    float f_px;            // focal em px: f = (altura/2)/tan(fovy/2)
    float cx;              // ponto principal (convenção do índice): (W−1)/2
    float cy;              // (H−1)/2
    float inclinacao_cam;  // rad — + = câmara inclinada para CIMA relativamente ao eixo x do corpo
    float raio_alvo_m;     // R_alvo (m) — raio físico da esfera
    float dist_alvo_m;     // d* (m) — distância a manter
    float atraso_nominal_s;// s — atraso captura→chegada, só usado se Camera.t for absurdo
    // --- estimador do alvo
    int32_t modelo;        // ModeloAlvo
    float alfa;            // α-β
    float beta;
    float q_ang;           // KF: PSD do ruído de processo dos ângulos (rad²·s⁻³ no CV · rad²·s⁻⁵ no CA)
    float q_raio;          // idem do raio normalizado (raio/f)
    float sigma_px;        // σ da medida de u, v (px)
    float sigma_raio_px;   // σ da medida do raio (px)
    float gate_sigma;      // recusa a medida se |inovação| > gate_sigma·σ_inovação
    // --- yaw
    float kp_yaw;          // 1/s
    float ki_yaw;          // 1/s²
    float i_max_yaw;       // rad/s — limite do integral (anti-windup)
    float integra_ate;     // rad — o integral só trabalha com |e_ψ| < integra_ate (sem windup em transitórios grandes)
    float kff_yaw;         // ganho do feedforward da taxa de bearing do alvo (1 = compensa a taxa estimada)
    float tau_avanco_yaw;  // s — avanço de fase: FF = ω_los + tau·α_los (só o KF-CA tem α)
    float yaw_max;         // rad/s
    float yaw_acel_max;    // rad/s² (slew)
    float zona_morta_yaw;  // rad
    // --- vertical
    float kp_z;            // 1/s — v_z = kp_z·(D·sen ε) + kff_z·v_vertical_alvo
    float kff_z;           // feedforward da velocidade vertical estimada do alvo
    float vz_max;          // m/s
    float acel_z_max;      // m/s²
    float zona_morta_z;    // m
    // --- distância
    float kp_d;            // 1/s — v_x = kp_d·(D − d*) + kff_d·v_radial_alvo
    float kff_d;           // feedforward da velocidade radial estimada do alvo
    float vx_max;          // m/s
    float acel_x_max;      // m/s²
    float zona_morta_d;    // m
    // --- máquina de estados
    float t_gap_s;         // s sem deteção aceite para passar de A_SEGUIR a EM_FALTA
    float t_falta_s;       // s sem deteção aceite para passar a PERDIDO (≈ 0,3)
    int32_t n_reaq;        // deteções aceites seguidas para REAQUISICAO → A_SEGUIR
    float w_procura;       // rad/s — taxa da procura de yaw em PERDIDO
    float t_procura_max_s; // s — depois disto a procura pára (flag) — 0 = sem limite
    // --- versão 2: «seguir a bola» (tudo a 0 = a lei da versão 1)
    int32_t comp_translacao; // 1 = o filtro do alvo desconta a translação PRÓPRIA (odometria de bordo): as taxas são só do alvo
    float kp_y;            // 1/s — v_y = kp_y·(desvio lateral do alvo, m) + kff_y·v_tangencial_alvo
    float kff_y;           // feedforward da velocidade tangencial estimada do alvo (1 = o drone acompanha-o de lado)
    float vy_max;          // m/s
    float acel_y_max;      // m/s²
    float zona_morta_y;    // m
    float k_incl_z;        // [0,1] — 0: v_z anula a elevação INERCIAL (drone à altura do alvo) · 1: anula o erro vertical NA IMAGEM
    float tau_incl_s;      // s — PT1 da parcela de inclinação do corpo no canal vertical (0 = sem filtro)
    int32_t raio_cv;       // 1 = com KF_CA, o canal do RAIO usa velocidade constante (q_raio passa a ser o do CV): o raio de um
                           //     blob de ~6 px não dá para estimar aceleração — o CA só punha a distância a oscilar
};

// O que o seguidor devolve: comando + estado + diagnóstico (todas as grandezas finitas).
struct SaidaSeguidor {
    float vx;              // m/s  ┐
    float vy;              // m/s  │ ComandoVoo (referencial do rumo)
    float vz;              // m/s  │
    float yaw_taxa;        // rad/s┘
    int32_t estado;        // Estado
    int32_t flags;         // bits kFlag*
    float e_psi;           // rad — erro de rumo previsto AGORA (azimute inercial do alvo − ψ), + = alvo à esquerda
    float e_elev;          // rad — elevação inercial prevista do alvo (desrodada de roll/pitch)
    float dist;            // m — distância prevista R·f/raio
    float taxa_bearing;    // rad/s — taxa do azimute inercial do alvo (o feedforward do yaw)
    float acel_bearing;    // rad/s² — aceleração do azimute (só KF-CA)
    float az_pred;         // rad — azimute inercial previsto agora
    float el_pred;         // rad — elevação inercial prevista agora
    float u_pred;          // px — onde o alvo deve estar na imagem agora (previsto; para a janela de busca)
    float v_pred;          // px
    float raio_pred;       // px
    float t_sem_det_s;     // s desde a última deteção aceite
    int32_t n_aceites;     // medidas aceites desde o último reinício do filtro
    int32_t n_rejeitadas;  // medidas válidas recusadas pelo gate (total)
    int32_t procura;       // 1 = a procurar (PERDIDO a rodar)
    // --- versão 2: o que o dono vê e o que a lei antecipa (para o HUD)
    float e_h_cam;         // rad — erro HORIZONTAL previsto NA IMAGEM agora (+ = alvo à direita do centro); 0 sem previsão
    float e_v_cam;         // rad — erro VERTICAL previsto na imagem (+ = alvo acima do centro): inclui a inclinação do corpo
    float v_alvo_rad;      // m/s — velocidade estimada do alvo ao longo da linha de vista (+ = afasta-se)
    float v_alvo_tan;      // m/s — idem, tangencial (+ = para a esquerda da linha de vista)
    float v_alvo_vert;     // m/s — idem, vertical (+ = sobe)
};

}  // namespace visao
}  // namespace nucleo
