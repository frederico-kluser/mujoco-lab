// firmware/nucleo/cascata.hpp — CASCATA CLÁSSICA de voo (não-IA): port float32 do `CascataClassica`
// (experiments/09_drone_hover_rl/controlo_classico.py). MESMAS equações, MESMA ordem de operações; só `float`; sem heap.
// Decisão do dono (2026-10-12): estabilização, rotação (yaw livre) e movimentação são um algoritmo CLÁSSICO a correr
// num Arduino. Nada daqui é copiado: só as IDEIAS e as EQUAÇÕES publicadas (PX4 é BSD-3-Clause; ArduPilot, Betaflight,
// Crazyflie e MultiWii são GPLv3 e NÃO foram lidos ao nível do código).
//
//   cmd (referencial do RUMO: frente/esquerda/cima, yaw_taxa | yaw absoluto)       [estimativas de bordo + giroscópio]
//          │
//   conformador (acel./jerk-limitado + modelo de seguimento da malha de atitude)
//          │
//   posição (P, raiz quadrada) ──▶ velocidade (PI + FF de aceleração e de arrasto) ──▶ aceleração desejada
//          │
//   inclinação desejada + EMPUXO COLETIVO ÷ (cosφ·cosθ)   [anti-windup por retro-cálculo]
//          │
//   atitude (P) com PRIORIDADE DE INCLINAÇÃO (Brescianini) + PESO DE YAW + FF da taxa de inclinação
//          │
//   taxas p, q, r ──▶ [laço de taxa, 500 Hz — taxa.hpp: PID + mistura X + airmode]
//
// Uma chamada por decisão (50 Hz): `Cascata::passo(g, est, giro, cmd, dt, …)` → empuxo coletivo T/(m·g) (1,0 =
// pairagem) e taxas (p, q, r) [rad/s, corpo]. A conversão para acelerador (compensação de tensão) é do Nucleo.
//
// TODAS as constantes de projeto vêm da `ConfigCascata` (gerada por sitl.config_de_hardware a partir de
// `ganhos_de_hardware`): aqui só há guardas numéricas (divisões por ~0, singularidades) e a estrutura das fórmulas.
//
// FONTES (equações reimplementadas; nenhuma linha copiada):
//   [PX4]   Controller Diagrams — docs.px4.io/main/en/flight_stack/controller_diagrams (cascata posição P → velocidade
//           PID → aceleração → inclinação+empuxo → atitude P → taxa PID; o modo velocidade contorna a posição e trava-a
//           ao parar); parâmetros MC_YAW_WEIGHT, MPC_TILTMAX_AIR, MPC_ACC_HOR, MPC_JERK_*, MPC_TKO_SPEED.
//   [ARDU]  ArduPilot dev docs — «Copter Attitude Control» / «Position Control»: controlador raiz quadrada (aproximação
//           sem sobressinal sob limite de aceleração), compensação ANGLE_BOOST do empuxo, ATC_ACC_Y_MAX.
//   [BRE18] Brescianini & D'Andrea, «Tilt-Prioritized Quadrocopter Attitude Control», IEEE T-CST 28(2), 2018.
//   [FAE18] Faessler, Franchi & Scaramuzza, «Differential Flatness of Quadrotor Dynamics Subject to Rotor Drag…»,
//           RA-L 3(2), 2018 (aceleração desejada → orientação+empuxo; arrasto de rotor linear em v).
//   [AM08]  Åström & Murray, «Feedback Systems», 2008, §10.4 (windup; retro-cálculo).
//
// Unidades SI; +Z para cima; ângulos ZYX (yaw ψ, pitch θ, roll φ): θ > 0 inclina o empuxo para +x (acelera para a
// frente), φ < 0 inclina-o para +y (esquerda); ψ > 0 roda no sentido anti-horário visto de cima.
#pragma once

#include <math.h>
#include <stdint.h>

#include "config.hpp"

namespace nucleo {

namespace cascata_detalhe {

constexpr float kDoisPi = 6.28318530717958647692f;
// Guardas numéricas (NÃO são parâmetros de projeto): protegem divisões por ~0 e singularidades.
constexpr float kEps = 1e-9f;          // divisão por ~0 / comparações com zero
constexpr float kEpsComando = 1e-6f;   // |vx|+|vy| desprezável (o comando não pede movimento)
constexpr float kUmMaisMin = 1e-3f;    // 1 + n_bz mínimo (n̂ quase oposto ao eixo z do corpo)
constexpr float kModMin = 1e-6f;       // n̂ ∥ ĥ_d (inclinação de 90°): sem yaw definido
constexpr float kKvelMin = 1e-6f;      // K_vel mínimo no ganho de retro-cálculo
constexpr float kAngMax = 1.0e6f;      // |ângulo| máximo que a volta do rumo trata (rad)

// ângulo → (−π, π] (a mesma convenção do protótipo: fmod(a + π, 2π) ∈ (0, 2π]); sem libm.
inline float envolve_pi(float a) {
    if (!(absf(a) < kAngMax)) return 0.0f;  // não finito ou fora do alcance da conversão a inteiro
    float r = a + kPi;
    const int32_t voltas = static_cast<int32_t>(r * (1.0f / kDoisPi));  // trunca para zero
    r -= static_cast<float>(voltas) * kDoisPi;
    if (r <= 0.0f) r += kDoisPi;
    return r - kPi;
}

// CONTROLADOR RAIZ QUADRADA ([ARDU]): erro → «velocidade» desejada. Perto de zero é linear (v = k·e); longe, é a
// velocidade de que se TRAVA a `lim` constante até parar no erro zero (v² = 2·lim·d), sem sobressinal. Junção
// contínua e com derivada contínua em |e| = lim/k²:
//     |e| ≤ lim/k² :  v = k·e         |e| > lim/k² :  v = sinal(e)·√(2·lim·(|e| − lim/(2k²)))
inline float raiz_quadrada(float erro, float k, float lim) {
    if (lim <= 0.0f || k <= 0.0f) return 0.0f;
    const float e = absf(erro);
    const float kk = k * k;
    if (e <= lim / kk) return k * erro;
    const float v = sqrtf(2.0f * lim * (e - 0.5f * lim / kk));
    return erro > 0.0f ? v : -v;
}

}  // namespace cascata_detalhe

class Cascata {
public:
    // Saída de um passo da cascata (as taxas p, q, r em rad/s no corpo) e os bits kFlag* que levantou.
    struct Resultado {
        float coletivo;
        float taxas[3];
        int32_t flags;
    };

    // Guarda tan(tilt_max) (calculada uma vez: o protótipo recalcula-a a cada passo) e reinicia.
    void iniciar(const ConfigCascata& c) {
        const float co = cosf(c.tilt_max);
        tan_tilt_ = co > cascata_detalhe::kEps ? sinf(c.tilt_max) / co : 0.0f;
        reiniciar();
    }

    // Desarma e limpa todos os estados (incluindo as referências).
    void reiniciar() {
        armado_ = false;
        iniciado_ = false;
        p_sp_[0] = p_sp_[1] = 0.0f;
        z_sp_ = 0.0f;
        psi_sp_ = 0.0f;
        zerar_estados();
        ultimo_.coletivo = 0.0f;
        ultimo_.taxas[0] = ultimo_.taxas[1] = ultimo_.taxas[2] = 0.0f;
        ultimo_.flags = 0;
        zerar_diagnostico();
    }

    // Arma/desarma. Armar (a partir de desarmado) zera os integradores e conformadores; as referências (x, y, ψ,
    // altura) travam na 1.ª chamada de passo() (ou já, com travar()). Desarmada devolve (0, (0, 0, 0)): NEUTRO.
    void armar(bool armado) {
        if (armado && !armado_) {
            zerar_estados();
        } else if (!armado) {
            zerar_estados();
            iniciado_ = false;
        }
        armado_ = armado;
    }

    bool armada() const { return armado_; }

    // Trava as referências (x, y, ψ, altura) nas estimativas dadas; `tem_z_alvo` = «subir/descer até z_alvo» (DESCOLAR).
    void travar(const Saida& est, bool tem_z_alvo, float z_alvo) {
        p_sp_[0] = est.x;
        p_sp_[1] = est.y;
        psi_sp_ = est.psi;
        z_sp_ = est.h;
        tem_z_alvo_ = tem_z_alvo;
        z_alvo_ = tem_z_alvo ? z_alvo : 0.0f;
        iniciado_ = true;
    }

    // Uma decisão: estimativas (`est`: roll pitch psi h vz vx vy x y de uma Saida) + taxas medidas + comando + dt →
    // (empuxo coletivo T/(m·g), (p, q, r) [rad/s]). `cmd.modo` = YAW_ALVO usa `cmd.yaw`; qualquer outro, `cmd.yaw_taxa`.
    // Etapas: 1 velocidade medida no rumo/arranque · 2 yaw (conformador de taxa + referência de rumo) · 3 conformador
    // de velocidade e de altura (+ modelo de seguimento) · 4 referência de posição · 5 laço de posição (raiz
    // quadrada) e de velocidade (PI + FF) → aceleração · 6 laço de altura/velocidade vertical → a_z · 7 inclinação
    // desejada e coletivo (÷ cosφ·cosθ; anti-windup) · 8 atitude com prioridade de inclinação → taxas.
    Resultado passo(const ConfigCascata& g, const Saida& est, const float giro[3], const Comando& cmd, float dt) {
        using cascata_detalhe::envolve_pi;
        using cascata_detalhe::raiz_quadrada;
        // ---- entradas finitas (o protótipo levanta ValueError; o firmware mantém a última saída boa)
        const float e9[9] = {est.roll, est.pitch, est.psi, est.h, est.vz, est.vx, est.vy, est.x, est.y};
        bool ok = e_finito(dt) && dt > 0.0f;
        for (int i = 0; i < 9; ++i) ok = ok && e_finito(e9[i]);
        for (int i = 0; i < 3; ++i) ok = ok && e_finito(giro[i]);
        ok = ok && e_finito(cmd.vx) && e_finito(cmd.vy) && e_finito(cmd.vz) && e_finito(cmd.yaw_taxa);
        if (cmd.modo == YAW_ALVO) ok = ok && e_finito(cmd.yaw);
        if (cmd.tem_z_alvo != 0) ok = ok && e_finito(cmd.z_alvo);
        if (!ok) {
            Resultado r = ultimo_;
            r.flags = kFlagFalhaCascata;
            return r;
        }
        if (!armado_) {
            Resultado r;
            r.coletivo = 0.0f;
            r.taxas[0] = r.taxas[1] = r.taxas[2] = 0.0f;
            r.flags = 0;
            return r;
        }
        if (!iniciado_) travar(est, false, 0.0f);
        int32_t flags = 0;
        const float phi = est.roll;
        const float theta = est.pitch;
        const float psi = est.psi;
        const float h = est.h;
        const float vz = est.vz;
        const float vbx = est.vx;
        const float vby = est.vy;
        const float x = est.x;
        const float y = est.y;
        // sen/cos calculados UMA vez (o protótipo recalcula os mesmos valores em cada função)
        const float cs = cosf(psi);
        const float sn = sinf(psi);
        const float sf = sinf(phi);
        const float cf = cosf(phi);
        const float st = sinf(theta);
        const float ct = cosf(theta);

        // ---- 1. velocidade medida: corpo → referencial do rumo (H) → referencial de arranque (O)
        float vhx = vbx;
        float vhy = vby;
        const float den = ct * cf;
        if (!(den < g.cos_incl_min)) {  // (quase de cabeça para baixo: sem correção — nunca acontece em voo)
            const float vbz = (vz + st * vbx - ct * sf * vby) / den;
            vhx = ct * vbx + st * (sf * vby + cf * vbz);
            vhy = cf * vby - sf * vbz;
        }
        const float vox = cs * vhx - sn * vhy;
        const float voy = sn * vhx + cs * vhy;

        // ---- 2. YAW: conformador da taxa (limite de taxa e de aceleração) + referência de rumo
        float r_des;
        if (cmd.modo == YAW_ALVO) {
            const float e_psi = envolve_pi(cmd.yaw - psi_sp_);
            r_des = raiz_quadrada(e_psi, g.peso_yaw * g.k_yaw, g.acel_yaw_max);
        } else {
            r_des = cmd.yaw_taxa;
        }
        if (absf(r_des) > g.taxa_yaw_max) flags |= kFlagSatYawTaxa;
        r_des = limita(r_des, -g.taxa_yaw_max, g.taxa_yaw_max);
        const float r_ant = r_ref_;
        if (absf(r_des - r_ref_) > g.acel_yaw_max * dt) flags |= kFlagSatYawAcel;
        r_ref_ += limita(r_des - r_ref_, -g.acel_yaw_max * dt, g.acel_yaw_max * dt);
        const float e_av = envolve_pi(psi_sp_ - psi);
        float r_int;
        if ((e_av > g.avanco_yaw_max && r_ref_ > 0.0f) || (e_av < -g.avanco_yaw_max && r_ref_ < 0.0f)) {
            r_int = 0.0f;  // a referência já vai à frente do que a planta consegue: não avança
        } else {
            r_int = r_ref_;
        }
        psi_sp_ = envolve_pi(psi_sp_ + r_int * dt);

        // ---- 3. conformador de velocidade (referencial do rumo): v_cmd → (v_sp, a_sp)
        float vcx = cmd.vx;
        float vcy = cmd.vy;
        const float nv = sqrtf(vcx * vcx + vcy * vcy);
        if (nv > g.vel_xy_max) {
            vcx = vcx * g.vel_xy_max / nv;
            vcy = vcy * g.vel_xy_max / nv;
        }
        const float vc[2] = {vcx, vcy};
        for (int i = 0; i < 2; ++i) {
            const float a_des = limita(raiz_quadrada(vc[i] - v_sp_h_[i], g.k_conf, g.jerk_cmd_xy), -g.acc_cmd_xy,
                                       g.acc_cmd_xy);
            a_sp_h_[i] += limita(a_des - a_sp_h_[i], -g.jerk_cmd_xy * dt, g.jerk_cmd_xy * dt);
            v_sp_h_[i] += a_sp_h_[i] * dt;
        }
        // vertical: velocidade comandada (Q/E) e/ou «ir até z_alvo» (descolar). Com um z_alvo pendente os comandos de
        // velocidade MOVEM o alvo (o descolar não é cancelado por um Q carregado a meio: alvo = descolagem + ∫vz).
        if (cmd.tem_z_alvo != 0) {
            z_alvo_ = cmd.z_alvo;
            tem_z_alvo_ = true;
        }
        const float vcz_man = limita(cmd.vz, -g.vel_z_max, g.vel_z_max);
        float vcz;
        if (tem_z_alvo_) {
            z_alvo_ = limita(z_alvo_ + vcz_man * dt, g.altura_min, g.altura_max);
            vcz = limita(vcz_man + raiz_quadrada(z_alvo_ - z_sp_, g.k_pz, g.acc_cmd_z), -g.vel_goto_z, g.vel_goto_z);
            if (absf(z_alvo_ - z_sp_) < g.tol_alvo_z && absf(v_sp_z_) < g.tol_alvo_vz &&
                absf(vcz_man) < cascata_detalhe::kEps) {
                z_sp_ = z_alvo_;  // chegou: trava exatamente na altura pedida
                tem_z_alvo_ = false;
            }
        } else {
            vcz = vcz_man;
        }
        const float a_des_z = limita(raiz_quadrada(vcz - v_sp_z_, g.k_conf_z, g.jerk_cmd_z), -g.acc_cmd_z, g.acc_cmd_z);
        a_sp_z_ += limita(a_des_z - a_sp_z_, -g.jerk_cmd_z * dt, g.jerk_cmd_z * dt);
        v_sp_z_ += a_sp_z_ * dt;

        // modelo de seguimento: a planta (malha de atitude) ATRASA a resposta; a realimentação compara com a referência
        // atrasada para não «contar duas vezes» o atraso que o feed-forward já aceita (evita o sobressinal)
        if (g.tau_modelo > 0.0f) {
            const float am = dt / (g.tau_modelo + dt);
            v_mod_h_[0] += am * (v_sp_h_[0] - v_mod_h_[0]);
            v_mod_h_[1] += am * (v_sp_h_[1] - v_mod_h_[1]);
        }
        if (g.tau_modelo_z > 0.0f) {
            v_mod_z_ += (dt / (g.tau_modelo_z + dt)) * (v_sp_z_ - v_mod_z_);
        } else {
            v_mod_z_ = v_sp_z_;
        }
        if (g.tau_modelo <= 0.0f) {
            v_mod_h_[0] = v_sp_h_[0];
            v_mod_h_[1] = v_sp_h_[1];
        }

        // ---- 4. referência de posição («segura» quando v = 0)
        const float vsx = cs * v_mod_h_[0] - sn * v_mod_h_[1];
        const float vsy = sn * v_mod_h_[0] + cs * v_mod_h_[1];
        if (g.ref_posicao_trava != 0) {
            // estilo PX4 (modo Position): em movimento a referência acompanha a medida (laço de posição inativo);
            // ao parar, TRAVA onde ficou — o drone é depois «seguro» nesse ponto
            const float v_sp_norma = sqrtf(v_sp_h_[0] * v_sp_h_[0] + v_sp_h_[1] * v_sp_h_[1]);
            if ((absf(cmd.vx) + absf(cmd.vy) > cascata_detalhe::kEpsComando) || v_sp_norma > g.v_trava) {
                p_sp_[0] = x;
                p_sp_[1] = y;
            }
        } else {
            p_sp_[0] += vsx * dt;
            p_sp_[1] += vsy * dt;
        }
        z_sp_ += v_mod_z_ * dt;  // a altitude integra sempre (a resposta vertical é rápida e sem lead)
        if (z_sp_ < g.altura_min || z_sp_ > g.altura_max) {  // piso/teto de altitude em voo
            z_sp_ = limita(z_sp_, g.altura_min, g.altura_max);
            if ((z_sp_ <= g.altura_min) == (v_sp_z_ < 0.0f)) {
                v_sp_z_ = 0.0f;
                a_sp_z_ = 0.0f;
                v_mod_z_ = 0.0f;
            }
        }
        float ex = p_sp_[0] - x;
        float ey = p_sp_[1] - y;
        float dist = sqrtf(ex * ex + ey * ey);
        if (dist > g.avanco_pos_max) {  // referência demasiado à frente: não acumula
            const float k = g.avanco_pos_max / dist;
            p_sp_[0] = x + ex * k;
            p_sp_[1] = y + ey * k;
            ex *= k;
            ey *= k;
            dist = g.avanco_pos_max;
        }

        // ---- 5. laço de posição (P, com aproximação raiz-quadrada) + velocidade (PI(D)) → aceleração
        float ux = 0.0f;
        float uy = 0.0f;
        if (dist > cascata_detalhe::kEps) {
            const float v_corr = limita(raiz_quadrada(dist, g.k_pos, g.acc_pos), 0.0f, g.vel_corr_pos_max);
            ux = ex / dist * v_corr;
            uy = ey / dist * v_corr;
        }
        const float vdx = vsx + ux;
        const float vdy = vsy + uy;
        const float evx = vdx - vox;
        const float evy = vdy - voy;
        if (g.kd_vel > 0.0f) {
            if (!tem_v_ant_) {
                v_ant_[0] = vox;
                v_ant_[1] = voy;
                tem_v_ant_ = true;
            }
            const float alfa_d = dt / (g.tau_d_vel + dt);
            d_filt_[0] += alfa_d * ((vox - v_ant_[0]) / dt - d_filt_[0]);
            d_filt_[1] += alfa_d * ((voy - v_ant_[1]) / dt - d_filt_[1]);
            v_ant_[0] = vox;
            v_ant_[1] = voy;
        }
        // feed-forward: aceleração conformada + centrípeta (ω × v) da referência
        const float axh = g.k_ff_acc * a_sp_h_[0] - r_ref_ * v_sp_h_[1];
        const float ayh = g.k_ff_acc * a_sp_h_[1] + r_ref_ * v_sp_h_[0];
        float aff_x = cs * axh - sn * ayh;
        float aff_y = sn * axh + cs * ayh;
        // o empuxo vence o arrasto linear a = −d·v [FAE18] — na velocidade que o MODELO de seguimento prevê (a
        // verdadeira ainda não chegou à referência: usar v_sp ultrapassa o regime e dá sobressinal)
        aff_x += g.k_arrasto * vsx;
        aff_y += g.k_arrasto * vsy;
        const float ax = aff_x + g.k_vel * evx + i_vel_[0] - g.kd_vel * d_filt_[0];
        const float ay = aff_y + g.k_vel * evy + i_vel_[1] - g.kd_vel * d_filt_[1];

        // ---- 6. laço vertical: altura (P) → velocidade (PI) → aceleração
        const float ez = z_sp_ - h;
        const float v_corr_z = limita(raiz_quadrada(ez, g.k_pz, g.acc_cmd_z), -g.vel_corr_z_max, g.vel_corr_z_max);
        const float evz = v_mod_z_ + v_corr_z - vz;
        const float az = a_sp_z_ + g.k_vz * evz + i_z_;

        // ---- 7. inclinação desejada + empuxo coletivo (÷ cosφ·cosθ)
        // Aceleração desejada [m/s²] (mundo) → direção do empuxo n̂ e EMPUXO COLETIVO normalizado. Força específica
        // desejada F = a + g·ẑ; n̂ = F/‖F‖ (eixo z do corpo desejado) e T/(m·g) = ‖F‖/g = (g + a_z)/(g·n_z) com n_z =
        // cos da inclinação desejada: a «compensação 1/(cosφ·cosθ)» (a componente VERTICAL do empuxo fica m·(g + a_z)
        // por maior que seja a inclinação; PX4: collective_thrust = thrust_z / cos_ned_body; ArduPilot: ANGLE_BOOST).
        // LIMITE DE INCLINAÇÃO: se a pedida passa de tilt_max a aceleração horizontal escala para tan(tilt_max)·(g + a_z)
        // (a vertical tem PRIORIDADE).
        float fz = g.g + az;
        const float fz_min = g.fz_min_frac * g.g;
        if (!(fz > fz_min)) fz = fz_min;  // nunca apontar o empuxo para baixo (queda livre pedida)
        const float a_hor = sqrtf(ax * ax + ay * ay);
        const float lim_incl = fz * tan_tilt_;
        float nax = ax;
        float nay = ay;
        bool sat_incl = false;
        if (a_hor > lim_incl) {
            nax = ax * lim_incl / a_hor;
            nay = ay * lim_incl / a_hor;
            sat_incl = true;
        }
        const float mod = sqrtf(nax * nax + nay * nay + fz * fz);
        const float nx = nax / mod;
        const float ny = nay / mod;
        const float nz = fz / mod;
        float coletivo = mod / g.g;
        if (coletivo < g.coletivo_min || coletivo > g.coletivo_max) flags |= kFlagSatColetivo;
        coletivo = limita(coletivo, g.coletivo_min, g.coletivo_max);
        if (sat_incl) flags |= kFlagSatInclinacao;
        // o diferencial de yaw do FC acrescenta empuxo (T ∝ u²: Σ(u₀ ± d)² = 4u₀² + 4d²): pré-compensa-se
        // c_eff = c − (d/u_pair)², com d = acelerador diferencial estimado da referência de yaw (u/r·r + ṙ/α_z)
        if (g.comp_yaw_empuxo != 0) {
            const float d_yaw = g.u_yaw_por_taxa * absf(r_ref_) + g.comp_yaw_acel * absf(r_ref_ - r_ant) / dt / g.alfa_yaw;
            const float rel = d_yaw / g.u_pairagem;
            const float comp = coletivo - rel * rel;
            coletivo = comp > g.coletivo_min ? comp : g.coletivo_min;
        }
        // anti-windup (retro-cálculo na horizontal; integração condicional na vertical) [AM08][PX4]
        float ax_s = ax;
        float ay_s = ay;
        if (sat_incl && a_hor > cascata_detalhe::kEps) {
            const float lim = (g.g + az) * tan_tilt_;
            const float fator = lim / a_hor;
            ax_s = ax * fator;
            ay_s = ay * fator;
        }
        const float k_aw = g.aw_ganho / (g.k_vel > cascata_detalhe::kKvelMin ? g.k_vel : cascata_detalhe::kKvelMin);
        i_vel_[0] = limita(i_vel_[0] + g.ki_vel * dt * (evx + k_aw * (ax_s - ax)), -g.lim_i_vel, g.lim_i_vel);
        i_vel_[1] = limita(i_vel_[1] + g.ki_vel * dt * (evy + k_aw * (ay_s - ay)), -g.lim_i_vel, g.lim_i_vel);
        const bool sat_cima = coletivo >= g.coletivo_max - cascata_detalhe::kEps && evz > 0.0f;
        const bool sat_baixo = coletivo <= g.coletivo_min + cascata_detalhe::kEps && evz < 0.0f;
        if (!(sat_cima || sat_baixo)) {
            i_z_ = limita(i_z_ + g.ki_vz * dt * evz, -g.lim_i_z * g.g, g.lim_i_z * g.g);
        }

        // ---- 8. atitude com prioridade de inclinação → taxas
        // Erro de atitude [BRE18]: atitude desejada = eixo z do corpo = n̂ e eixo x tão perto de (cosψ_d, sinψ_d, 0)
        // quanto n̂ permite. q_e = q_red ⊗ q_yaw: primeiro a rotação MÍNIMA que alinha o eixo z (a INCLINAÇÃO, sem
        // componente z), depois γ em torno do z desejado (o YAW):  (e_x, e_y) = (−n_by, n_bx)/cos(α/2),
        // γ = atan2(ŷ_red·x_d, x̂_red·x_d), com n_b = Rᵀ·n̂. O erro de inclinação NÃO depende do yaw desejado: um erro de
        // yaw, por enorme que seja, não perturba p, q (é a «prioridade»).
        const float cps = cosf(psi_sp_);  // ĥ_d = (cosψ_d, sinψ_d, 0)
        const float sps = sinf(psi_sp_);
        const float xb[3] = {cs * ct, sn * ct, -st};  // colunas de R (corpo → mundo): ZYX
        const float yb[3] = {cs * st * sf - sn * cf, sn * st * sf + cs * cf, ct * sf};
        const float zb[3] = {cs * st * cf + sn * sf, sn * st * cf - cs * sf, ct * cf};
        const float nbx = xb[0] * nx + xb[1] * ny + xb[2] * nz;
        const float nby = yb[0] * nx + yb[1] * ny + yb[2] * nz;
        const float nbz = limita(zb[0] * nx + zb[1] * ny + zb[2] * nz, -1.0f, 1.0f);
        float um_mais = 1.0f + nbz;
        if (um_mais < cascata_detalhe::kUmMaisMin) um_mais = cascata_detalhe::kUmMaisMin;
        const float meio_cos = sqrtf(0.5f * um_mais);  // cos(α/2)
        const float e_x = -nby / meio_cos;
        const float e_y = nbx / meio_cos;
        float gama = 0.0f;
        const float yx0 = -nz * sps;  // y_d = normalize(n̂ × ĥ_d)
        const float yy0 = nz * cps;
        const float yz0 = nx * sps - ny * cps;
        const float mod_y = sqrtf(yx0 * yx0 + yy0 * yy0 + yz0 * yz0);
        if (!(mod_y < cascata_detalhe::kModMin)) {  // (n̂ ∥ ĥ_d: inclinação de 90°, sem yaw definido ⇒ γ = 0)
            const float yx = yx0 / mod_y;
            const float yy = yy0 / mod_y;
            const float yz = yz0 / mod_y;
            const float dx = yy * nz - yz * ny;  // x_d = y_d × n̂
            const float dy = yz * nx - yx * nz;
            const float dz = yx * ny - yy * nx;
            const float xdb0 = xb[0] * dx + xb[1] * dy + xb[2] * dz;  // x_d nos eixos do corpo
            const float xdb1 = yb[0] * dx + yb[1] * dy + yb[2] * dz;
            const float xdb2 = zb[0] * dx + zb[1] * dy + zb[2] * dz;
            const float xr0 = nbz + nby * nby / um_mais;
            const float xr1 = -nbx * nby / um_mais;
            const float xr2 = -nbx;
            const float yr0 = -nbx * nby / um_mais;
            const float yr1 = nbz + nbx * nbx / um_mais;
            const float yr2 = -nby;
            gama = atan2f(yr0 * xdb0 + yr1 * xdb1 + yr2 * xdb2, xr0 * xdb0 + xr1 * xdb1 + xr2 * xdb2);
        }
        // taxa de yaw do MUNDO (ψ̇ = r_ref) nos eixos do corpo: ω_b = Rᵀ·(ψ̇·ẑ) = ψ̇·(−sθ, sφ·cθ, cφ·cθ)
        float p_ff = -st * r_ref_;
        float q_ff = sf * ct * r_ref_;
        const float r_ff = cf * ct * r_ref_;
        // feed-forward da taxa de inclinação: n̂ roda com ω = n̂ × dn̂/dt (mundo); as componentes x, y do corpo são p, q
        const float n_des[3] = {nx, ny, nz};
        if (g.ff_atitude != 0 && tem_n_ant_) {
            const float alfa_f = dt / (g.tau_ff + dt);
            for (int i = 0; i < 3; ++i) dn_[i] += alfa_f * ((n_des[i] - n_ant_[i]) / dt - dn_[i]);
            const float wx = ny * dn_[2] - nz * dn_[1];
            const float wy = nz * dn_[0] - nx * dn_[2];
            const float wz = nx * dn_[1] - ny * dn_[0];
            p_ff += xb[0] * wx + xb[1] * wy + xb[2] * wz;
            q_ff += yb[0] * wx + yb[1] * wy + yb[2] * wz;
        }
        for (int i = 0; i < 3; ++i) n_ant_[i] = n_des[i];
        tem_n_ant_ = true;
        const float p_bruto = g.k_att * e_x + p_ff;
        const float q_bruto = g.k_att * e_y + q_ff;
        if (absf(p_bruto) > g.taxa_rp_max || absf(q_bruto) > g.taxa_rp_max) flags |= kFlagSatTaxaRP;
        Resultado r;
        r.coletivo = coletivo;
        r.taxas[0] = limita(p_bruto, -g.taxa_rp_max, g.taxa_rp_max);
        r.taxas[1] = limita(q_bruto, -g.taxa_rp_max, g.taxa_rp_max);
        r.taxas[2] = limita(r_ff + g.peso_yaw * g.k_yaw * gama, -g.taxa_yaw_max, g.taxa_yaw_max);
        r.flags = flags;
        if (!(e_finito(r.coletivo) && e_finito(r.taxas[0]) && e_finito(r.taxas[1]) && e_finito(r.taxas[2]))) {
            // entradas finitas mas gigantes (1e30…) estouraram a aritmética: a cascata recomeça (volta a travar as
            // referências na decisão seguinte) e mantém-se a última saída boa
            zerar_estados();
            iniciado_ = false;
            Resultado boa = ultimo_;
            boa.flags = kFlagFalhaCascata;
            return boa;
        }
        ultimo_ = r;

        // diagnóstico (o `dados` do protótipo; valores não finitos — entradas gigantes — saem como 0: a telemetria não leva inf/NaN)
        dg_a_des_[0] = e_finito(ax) ? ax : 0.0f;
        dg_a_des_[1] = e_finito(ay) ? ay : 0.0f;
        dg_a_des_[2] = e_finito(az) ? az : 0.0f;
        for (int i = 0; i < 3; ++i) dg_n_des_[i] = n_des[i];
        dg_e_tilt_[0] = e_x;
        dg_e_tilt_[1] = e_y;
        dg_gama_ = gama;
        dg_v_h_[0] = vhx;
        dg_v_h_[1] = vhy;
        dg_v_o_[0] = vox;
        dg_v_o_[1] = voy;
        return r;
    }

    // Copia o estado de diagnóstico da última decisão para a Saida (o `dados` do protótipo Python).
    void diagnostico(Saida& o) const {
        for (int i = 0; i < 3; ++i) {
            o.a_des[i] = dg_a_des_[i];
            o.n_des[i] = dg_n_des_[i];
        }
        o.e_tilt[0] = dg_e_tilt_[0];
        o.e_tilt[1] = dg_e_tilt_[1];
        o.gama = dg_gama_;
        for (int i = 0; i < 2; ++i) {
            o.v_h[i] = dg_v_h_[i];
            o.v_o[i] = dg_v_o_[i];
            o.v_sp_h[i] = v_sp_h_[i];
            o.p_sp[i] = p_sp_[i];
            o.i_vel[i] = i_vel_[i];
        }
        o.z_sp = z_sp_;
        o.psi_sp = psi_sp_;
        o.r_ref = r_ref_;
        o.i_z = i_z_;
    }

private:
    void zerar_estados() {
        for (int i = 0; i < 2; ++i) {
            v_sp_h_[i] = 0.0f;
            a_sp_h_[i] = 0.0f;
            v_mod_h_[i] = 0.0f;
            i_vel_[i] = 0.0f;
            d_filt_[i] = 0.0f;
            v_ant_[i] = 0.0f;
        }
        v_mod_z_ = 0.0f;
        v_sp_z_ = 0.0f;
        a_sp_z_ = 0.0f;
        r_ref_ = 0.0f;
        i_z_ = 0.0f;
        tem_v_ant_ = false;
        tem_z_alvo_ = false;
        z_alvo_ = 0.0f;
        tem_n_ant_ = false;
        for (int i = 0; i < 3; ++i) {
            n_ant_[i] = 0.0f;
            dn_[i] = 0.0f;
        }
    }

    void zerar_diagnostico() {
        for (int i = 0; i < 3; ++i) {
            dg_a_des_[i] = 0.0f;
            dg_n_des_[i] = 0.0f;
        }
        dg_e_tilt_[0] = dg_e_tilt_[1] = 0.0f;
        dg_gama_ = 0.0f;
        for (int i = 0; i < 2; ++i) dg_v_h_[i] = dg_v_o_[i] = 0.0f;
    }

    // Tudo a ZERO (a instância fica em .bss); os valores certos põem-se em iniciar()/reiniciar().
    float tan_tilt_ = 0.0f;
    bool armado_ = false;
    bool iniciado_ = false;
    float p_sp_[2] = {};      // m — referência de posição (referencial de arranque)
    float z_sp_ = 0.0f;       // m — referência de altura
    float psi_sp_ = 0.0f;     // rad — referência de rumo
    float r_ref_ = 0.0f;      // rad/s — taxa de yaw conformada
    float v_sp_h_[2] = {};    // m/s — velocidade conformada no referencial do rumo
    float v_mod_h_[2] = {};   // m/s — a mesma, atrasada pelo modelo de seguimento da malha de atitude
    float v_mod_z_ = 0.0f;
    float a_sp_h_[2] = {};    // m/s²
    float v_sp_z_ = 0.0f;
    float a_sp_z_ = 0.0f;
    float i_vel_[2] = {};     // m/s² — integrais da velocidade horizontal (referencial de arranque)
    float i_z_ = 0.0f;        // m/s² — integral vertical (adapta o empuxo de pairagem: massa/kf)
    float d_filt_[2] = {};    // filtro do termo D
    float v_ant_[2] = {};
    bool tem_v_ant_ = false;
    float z_alvo_ = 0.0f;
    bool tem_z_alvo_ = false;
    float n_ant_[3] = {};     // direção do empuxo do passo anterior (feed-forward de taxa)
    float dn_[3] = {};
    bool tem_n_ant_ = false;
    Resultado ultimo_ = {};
    float dg_a_des_[3] = {};
    float dg_n_des_[3] = {};
    float dg_e_tilt_[2] = {};
    float dg_gama_ = 0.0f;
    float dg_v_h_[2] = {};
    float dg_v_o_[2] = {};
};

}  // namespace nucleo
