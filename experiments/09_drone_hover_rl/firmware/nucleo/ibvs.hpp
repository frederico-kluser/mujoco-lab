// firmware/nucleo/ibvs.hpp — LEI IBVS («olhar para o círculo») + MÁQUINA DE ESTADOS DE PERDA. C++ float32, sem heap.
//
// O Seguidor recebe, a cada passo do laço externo (50–100 Hz), o instante, a atitude estimada AGORA e a última
// medida da câmara (Camera: u, v, raio, contador de frames, instante da captura), e devolve o COMANDO para a
// cascata de voo: velocidades NO REFERENCIAL DO RUMO (frente/esquerda/cima) e taxa de guinada (rad/s, + anti-horário):
//
//   erro de rumo        e_ψ  = α_prev − ψ        (azimute INERCIAL previsto do alvo agora − rumo atual; já desrodado de
//                                                 roll/pitch e do atraso da câmara — ver alvo.hpp)
//   elevação desrodada  e_ε  = ε_prev            (elevação inercial do alvo: não vê a inclinação do drone)
//   distância           D    = R_alvo·f/raio_px = R_alvo/ρ_prev
//
//   yaw_taxa = Kp·e_ψ + I(e_ψ) + Kff·(ω_los + τ_av·α_los)          ← PI + FEEDFORWARD da taxa de bearing do alvo
//                                                                    (estimada por α-β/KF; τ_av·α_los = avanço de
//                                                                    fase do lag do yaw, só no KF-CA)
//   v_z      = Kz·(D·sen e_ε) + Kffz·v_vertical_alvo                ← P no desvio vertical (m), não no ângulo
//   v_x      = Kd·(D − d*) + Kffd·v_radial_alvo        (só avante × max(0, cos e_ψ))   ← P na DISTÂNCIA
//   v_y      = 0
//   (a «compensação da própria rotação» do enunciado está na desrotação: ω_los = d(az_câmara)/dt + r_própria)
//   com zona morta suave, limite e slew (aceleração máxima) por canal e anti-windup do integral.
//
// MÁQUINA DE ESTADOS (tempos em segundos desde a última deteção ACEITE):
//   A_SEGUIR ──(t_sem > t_gap)──▶ EM_FALTA ──(t_sem > t_falta ≈ 0,3)──▶ PERDIDO ──(deteção aceite)──▶ REAQUISICAO
//        ▲          ◀──(deteção aceite)──┘                                              │ n_reaq aceites seguidas
//        └───────────────────────────────────────────────────────────────────────────────┘ (uma falha ⇒ PERDIDO)
//   EM_FALTA segue a PREVISÃO do filtro com v a decair para 0; PERDIDO: v = 0 e procura lenta de yaw (w_procura)
//   para o ÚLTIMO LADO onde o alvo foi visto (sinal de e_ψ); REAQUISICAO: só yaw suave, sem FF nem translação, e a
//   HISTERESE de n_reaq deteções seguidas antes de A_SEGUIR (uma pista saltada — 3 outliers seguidos — também passa
//   por aqui).
//
// Referências (ideias; o código é próprio): Chaumette & Hutchinson, «Visual servo control» I/II (IEEE RAM 2006/07) e
// Springer Handbook of Robotics cap. 24 — IBVS com taxa de feedforward do alvo; ArduPilot/PX4 — taxa de yaw
// limitada em velocidade e aceleração; ver pesquisas/2026-10-12-para-um-quadricoptero-grande-*.md (Q3, Q7).
#pragma once

#include <math.h>
#include <stdint.h>

#include "alvo.hpp"
#include "visao_tipos.hpp"

namespace nucleo {
namespace visao {

// Parâmetros por omissão para uma câmara largura×altura com FoV vertical `fovy_graus` (convenção do índice).
// Os ganhos são os da secção «Margens» do README (PM ≥ 45° com τ_yaw ∈ [0,3; 0,6] s e atraso até 166 ms).
inline ConfigSeguidor config_padrao(float largura, float altura, float fovy_graus, int32_t modelo = KF_CA) {
    ConfigSeguidor c = {};
    c.versao = kVersaoVisao;
    const float meio = 0.5f * fovy_graus * (kPi / 180.0f);
    c.f_px = 0.5f * altura * cosf(meio) / sinf(meio);
    c.cx = 0.5f * (largura - 1.0f);
    c.cy = 0.5f * (altura - 1.0f);
    c.inclinacao_cam = 0.0f;
    c.raio_alvo_m = 0.05f;
    c.dist_alvo_m = 1.5f;
    c.atraso_nominal_s = 0.116f;
    c.modelo = modelo;
    c.alfa = 0.5f;   // α-β, KF-CV e KF-CA afinados em círculo/oito de 0,3–0,8 m/s com 116 ms de atraso (README)
    c.beta = 0.2f;
    c.q_ang = modelo == KF_CA ? 0.01f : 0.002f;
    c.q_raio = modelo == KF_CA ? 1e-5f : 2e-6f;
    c.sigma_px = 0.3f;
    c.sigma_raio_px = 0.3f;
    c.gate_sigma = 5.0f;
    c.kp_yaw = 1.0f;
    c.ki_yaw = 0.1f;
    c.i_max_yaw = 0.3f;
    c.integra_ate = 0.1f;
    c.kff_yaw = 1.0f;
    c.tau_avanco_yaw = 0.3f;
    c.yaw_max = 0.8f;
    c.yaw_acel_max = 1.5f;
    c.zona_morta_yaw = 0.005f;
    c.kp_z = 0.8f;
    c.kff_z = 0.5f;
    c.vz_max = 0.7f;
    c.acel_z_max = 1.0f;
    c.zona_morta_z = 0.02f;
    c.kp_d = 0.8f;
    c.kff_d = 0.4f;
    c.vx_max = 1.0f;
    c.acel_x_max = 1.0f;
    c.zona_morta_d = 0.03f;
    c.t_gap_s = 0.1f;
    c.t_falta_s = 0.3f;
    c.n_reaq = 3;
    c.w_procura = 0.3f;
    c.t_procura_max_s = 30.0f;
    return c;
}

// Configuração utilizável? (versão, números finitos, limites e ganhos coerentes)
inline bool config_valida(const ConfigSeguidor& c) {
    using geo::finito;
    if (c.versao != kVersaoVisao) return false;
    bool ok = finito(c.f_px) && c.f_px > 1.0f && finito(c.cx) && finito(c.cy) && finito(c.inclinacao_cam);
    ok = ok && finito(c.raio_alvo_m) && c.raio_alvo_m > 0.0f && finito(c.dist_alvo_m) && c.dist_alvo_m > 0.0f;
    ok = ok && finito(c.atraso_nominal_s) && c.atraso_nominal_s >= 0.0f && c.atraso_nominal_s < 1.0f;
    ok = ok && c.modelo >= ALFA_BETA && c.modelo <= KF_CA;
    ok = ok && finito(c.alfa) && c.alfa > 0.0f && c.alfa <= 1.0f && finito(c.beta) && c.beta > 0.0f && c.beta <= 2.0f;
    ok = ok && finito(c.q_ang) && c.q_ang > 0.0f && finito(c.q_raio) && c.q_raio > 0.0f;
    ok = ok && finito(c.sigma_px) && c.sigma_px > 0.0f && finito(c.sigma_raio_px) && c.sigma_raio_px > 0.0f;
    ok = ok && finito(c.gate_sigma) && c.gate_sigma > 0.0f;
    ok = ok && finito(c.kp_yaw) && c.kp_yaw >= 0.0f && finito(c.ki_yaw) && c.ki_yaw >= 0.0f;
    ok = ok && finito(c.i_max_yaw) && c.i_max_yaw >= 0.0f && finito(c.integra_ate) && c.integra_ate >= 0.0f;
    ok = ok && finito(c.kff_yaw) && finito(c.tau_avanco_yaw);
    ok = ok && finito(c.yaw_max) && c.yaw_max > 0.0f && finito(c.yaw_acel_max) && c.yaw_acel_max > 0.0f;
    ok = ok && finito(c.zona_morta_yaw) && c.zona_morta_yaw >= 0.0f;
    ok = ok && finito(c.kp_z) && c.kp_z >= 0.0f && finito(c.kff_z) && finito(c.vz_max) && c.vz_max > 0.0f;
    ok = ok && finito(c.acel_z_max) && c.acel_z_max > 0.0f && finito(c.zona_morta_z) && c.zona_morta_z >= 0.0f;
    ok = ok && finito(c.kp_d) && c.kp_d >= 0.0f && finito(c.kff_d) && finito(c.vx_max) && c.vx_max > 0.0f;
    ok = ok && finito(c.acel_x_max) && c.acel_x_max > 0.0f && finito(c.zona_morta_d) && c.zona_morta_d >= 0.0f;
    ok = ok && finito(c.t_gap_s) && c.t_gap_s > 0.0f && finito(c.t_falta_s) && c.t_falta_s > c.t_gap_s;
    ok = ok && c.n_reaq >= 1 && finito(c.w_procura) && c.w_procura >= 0.0f && finito(c.t_procura_max_s);
    return ok;
}

namespace ibvs_detalhe {

constexpr float kRhoMin = 1e-4f;          // raio normalizado mínimo (distância máxima = R/ρ)
constexpr float kDtPassoMax = 0.25f;      // s — o dt do passo satura aqui (integrador e slew)
constexpr int32_t kIdadeMaxUs = 1000000;  // µs — Camera.t mais velho que isto é absurdo
constexpr float kRampaFF = 6.0f;          // medidas aceites para o feedforward chegar ao peso 1 (a partir da 3.ª)

// zona morta suave: 0 dentro de ±db, e − sinal(e)·db fora (contínua)
inline float suave(float e, float db) { return e > db ? e - db : (e < -db ? e + db : 0.0f); }

// aproxima `atual` de `alvo` no máximo `passo` (≥ 0)
inline float desliza(float atual, float alvo, float passo) {
    const float d = alvo - atual;
    return d > passo ? atual + passo : (d < -passo ? atual - passo : alvo);
}

}  // namespace ibvs_detalhe

class Seguidor {
public:
    // Valida e guarda a configuração e reinicia (false = recusada: o passo() devolve comando nulo + kFlagNaoIniciado).
    bool iniciar(const ConfigSeguidor& cfg) {
        pronto_ = false;
        if (!config_valida(cfg)) return false;
        c_ = cfg;
        ot_ = geo::otica_de(c_);
        pronto_ = true;
        reiniciar();
        return true;
    }

    // Zera tudo: filtro, histórico, integral, comandos; o estado é PERDIDO (procura) até ver o alvo.
    void reiniciar() {
        hist_.zerar();
        filtro_.configurar(c_.modelo, c_.alfa, c_.beta, c_.q_ang, c_.q_raio, c_.sigma_px / c_.f_px,
                           c_.sigma_raio_px / c_.f_px, c_.gate_sigma);
        estado_ = PERDIDO;
        tem_t_ = false;
        tem_n_ = false;
        tem_det_ = false;
        tem_att_ = false;
        t_ant_ = 0u;
        t_ult_det_ = 0u;
        t_perdido_ = 0u;
        n_ant_ = 0;
        cont_reaq_ = 0;
        lado_ = 1.0f;
        i_yaw_ = 0.0f;
        cmd_vx_ = 0.0f;
        cmd_vz_ = 0.0f;
        cmd_yaw_ = 0.0f;
        n_rej_total_ = 0;
        att_ant_ = Atitude();
        att_ant_.roll = 0.0f;
        att_ant_.pitch = 0.0f;
        att_ant_.psi = 0.0f;
        att_ant_.vx = 0.0f;
        att_ant_.vy = 0.0f;
        att_ant_.vz = 0.0f;
    }

    int32_t estado() const { return estado_; }
    const ConfigSeguidor& config() const { return c_; }
    const FiltroAlvo& filtro() const { return filtro_; }

    // Um passo do laço externo. `t_us` = agora (µs, relógio do MCU); `att` = atitude/velocidade estimadas AGORA;
    // `cam` = a última medida da câmara (repetida entre frames: só conta se `cam.n` mudou).
    NUCLEO_VISAO_KERNEL SaidaSeguidor passo(uint32_t t_us, const Atitude& att, const Camera& cam) {
        using geo::finito;
        SaidaSeguidor o = {};
        o.estado = estado_;
        if (!pronto_) {
            o.estado = PERDIDO;
            o.flags = kFlagNaoIniciado;
            return o;
        }
        int32_t flags = 0;

        // ---- atitude de entrada (a última boa se vier NaN/inf)
        Atitude a = att;
        if (!(finito(a.roll) && finito(a.pitch) && finito(a.psi))) {
            flags |= kFlagEntradaInvalida;
            if (!tem_att_) {
                o.flags = flags;
                return o;
            }
            a = att_ant_;
        }
        if (!finito(a.vx)) a.vx = 0.0f;
        if (!finito(a.vy)) a.vy = 0.0f;
        if (!finito(a.vz)) a.vz = 0.0f;
        att_ant_ = a;
        tem_att_ = true;

        // ---- tempo
        float dt = 0.0f;
        if (!tem_t_) {
            tem_t_ = true;
            t_ant_ = t_us;
            t_perdido_ = t_us;
        } else {
            const int32_t d_us = static_cast<int32_t>(t_us - t_ant_);
            if (d_us > 0) {
                dt = static_cast<float>(d_us) * 1e-6f;
                if (dt > ibvs_detalhe::kDtPassoMax) dt = ibvs_detalhe::kDtPassoMax;
                t_ant_ = t_us;
            }
        }
        hist_.empurrar(t_us, a.roll, a.pitch, a.psi);

        // ---- medida nova da câmara → filtro (no INSTANTE DA CAPTURA, desrodada pela atitude desse instante)
        bool aceite = false;
        bool reinicio = false;
        const bool nova = !tem_n_ || cam.n != n_ant_;
        if (nova) {
            tem_n_ = true;
            n_ant_ = cam.n;
            // píxeis plausíveis: a menos de 20 focais do eixo (câmara com FoV < 175°) e raio positivo e limitado
            const float lim = 20.0f * c_.f_px;
            const bool ok = cam.valido != 0 && finito(cam.u) && finito(cam.v) && finito(cam.raio) && cam.raio > 0.25f &&
                            cam.raio < lim && geo::absf(cam.u - c_.cx) < lim && geo::absf(cam.v - c_.cy) < lim;
            if (ok) {
                uint32_t t_cap = cam.t;
                const int32_t idade = static_cast<int32_t>(t_us - cam.t);
                if (idade < 0 || idade > ibvs_detalhe::kIdadeMaxUs) {
                    t_cap = t_us - static_cast<uint32_t>(c_.atraso_nominal_s * 1e6f);
                    flags |= kFlagTempoInvalido;
                }
                float rc = 0.0f;
                float pc = 0.0f;
                float yc = 0.0f;
                bool fora = false;
                if (hist_.consultar(t_cap, &rc, &pc, &yc, &fora)) {
                    if (fora) flags |= kFlagHistoricoCurto;
                    float az = 0.0f;
                    float el = 0.0f;
                    geo::pixel_para_angulos(ot_, geo::rot_zyx(rc, pc, yc), cam.u, cam.v, &az, &el);
                    if (estado_ == PERDIDO) filtro_.zerar();  // recomeça a pista
                    const int32_t r = filtro_.medir(t_cap, az, el, cam.raio / c_.f_px);
                    if (r == 0 || r == 3) {
                        aceite = true;
                        reinicio = r == 3;
                        t_ult_det_ = t_us;
                        tem_det_ = true;
                    } else if (r == 1) {
                        flags |= kFlagOutlier;
                        ++n_rej_total_;
                    }
                    if (reinicio) flags |= kFlagReinicioFiltro;
                }
            }
        }

        // ---- máquina de estados
        float t_sem = tem_det_ ? static_cast<float>(static_cast<int32_t>(t_us - t_ult_det_)) * 1e-6f : 1e9f;
        if (t_sem < 0.0f) t_sem = 0.0f;
        atualizar_estado(t_us, aceite, reinicio, nova, t_sem);

        // ---- previsão do alvo AGORA e erros
        float e_psi = 0.0f;
        float e_el = 0.0f;
        float dist = 0.0f;
        float w_los = 0.0f;
        float a_los = 0.0f;
        float v_rad = 0.0f;
        float v_vert = 0.0f;
        bool tem_pred = false;
        if (estado_ != PERDIDO && filtro_.inicializado()) {
            float pos[3];
            float vel[3];
            float acc[3];
            filtro_.prever(t_us, pos, vel, acc);
            const float rho = pos[2] > ibvs_detalhe::kRhoMin ? pos[2] : ibvs_detalhe::kRhoMin;
            e_psi = geo::envolve(pos[0] - a.psi);
            e_el = pos[1];
            dist = c_.raio_alvo_m / rho;                      // = R·f/raio_px
            w_los = vel[0];
            a_los = acc[0];
            const float d_dot = -c_.raio_alvo_m * vel[2] / (rho * rho);   // Ḋ
            v_rad = d_dot + a.vx;                                          // Ḋ + v_x própria = velocidade radial do alvo
            v_vert = d_dot * sinf(e_el) + dist * cosf(e_el) * vel[1] + a.vz;   // ż relativo + v_z própria
            tem_pred = true;
            o.az_pred = pos[0];
            o.el_pred = pos[1];
            float up = 0.0f;
            float vp = 0.0f;
            if (geo::angulos_para_pixel(ot_, geo::rot_zyx(a.roll, a.pitch, a.psi), pos[0], pos[1], &up, &vp)) {
                o.u_pred = up;
                o.v_pred = vp;
                o.raio_pred = rho * c_.f_px;
            }
            if (geo::absf(e_psi) > 0.02f) lado_ = e_psi > 0.0f ? 1.0f : -1.0f;  // último lado visto
        }

        // ---- lei de controlo por estado
        float yaw_alvo = 0.0f;
        float vx_alvo = 0.0f;
        float vz_alvo = 0.0f;
        int32_t procura = 0;
        if (estado_ == A_SEGUIR || estado_ == EM_FALTA) {
            float fator = 1.0f;  // EM_FALTA: a translação decai linearmente para 0 até ao fim da janela de previsão
            if (estado_ == EM_FALTA) {
                const float faixa = c_.t_falta_s - c_.t_gap_s;
                fator = geo::limita((c_.t_falta_s - t_sem) / faixa, 0.0f, 1.0f);
            }
            const float peso_ff = geo::limita(static_cast<float>(filtro_.n_aceites() - 2) / ibvs_detalhe::kRampaFF,
                                              0.0f, 1.0f);
            const float e = ibvs_detalhe::suave(e_psi, c_.zona_morta_yaw);
            const float ff = c_.kff_yaw * (w_los + c_.tau_avanco_yaw * a_los) * peso_ff;
            const float bruto = c_.kp_yaw * e + ff + i_yaw_;
            yaw_alvo = bruto;
            if (dt > 0.0f) {  // anti-windup: não integra contra uma saturação nem em transitórios grandes
                const bool satura = (bruto > c_.yaw_max && e > 0.0f) || (bruto < -c_.yaw_max && e < 0.0f);
                if (!satura && geo::absf(e) < c_.integra_ate) {
                    i_yaw_ = geo::limita(i_yaw_ + c_.ki_yaw * e * dt, -c_.i_max_yaw, c_.i_max_yaw);
                }
            }
            const float dz = dist * sinf(e_el);  // desvio vertical (m)
            vz_alvo = fator * (c_.kp_z * ibvs_detalhe::suave(dz, c_.zona_morta_z) + c_.kff_z * v_vert * peso_ff);
            const float ed = dist - c_.dist_alvo_m;
            vx_alvo = fator * (c_.kp_d * ibvs_detalhe::suave(ed, c_.zona_morta_d) + c_.kff_d * v_rad * peso_ff);
            if (vx_alvo > 0.0f) {  // não persegue um alvo que está de lado
                const float ce = cosf(e_psi);
                vx_alvo *= ce > 0.0f ? ce : 0.0f;
            }
        } else if (estado_ == REAQUISICAO) {
            i_yaw_ = 0.0f;
            yaw_alvo = 0.6f * c_.kp_yaw * ibvs_detalhe::suave(e_psi, c_.zona_morta_yaw);
        } else {  // PERDIDO: v = 0 e procura lenta para o último lado
            i_yaw_ = 0.0f;
            const float t_p = static_cast<float>(static_cast<int32_t>(t_us - t_perdido_)) * 1e-6f;
            if (c_.t_procura_max_s > 0.0f && t_p > c_.t_procura_max_s) {
                flags |= kFlagProcuraEsgotada;
            } else {
                yaw_alvo = lado_ * c_.w_procura;
                procura = 1;
            }
        }

        // ---- limites e slew
        if (geo::absf(yaw_alvo) > c_.yaw_max) flags |= kFlagSaturouYaw;
        yaw_alvo = geo::limita(yaw_alvo, -c_.yaw_max, c_.yaw_max);
        vx_alvo = geo::limita(vx_alvo, -c_.vx_max, c_.vx_max);
        vz_alvo = geo::limita(vz_alvo, -c_.vz_max, c_.vz_max);
        if (dt > 0.0f) {
            const float yaw_ant = cmd_yaw_;
            cmd_yaw_ = ibvs_detalhe::desliza(cmd_yaw_, yaw_alvo, c_.yaw_acel_max * dt);
            if (geo::absf(cmd_yaw_ - yaw_ant) >= c_.yaw_acel_max * dt * 0.999f) flags |= kFlagSaturouYaw;
            cmd_vx_ = ibvs_detalhe::desliza(cmd_vx_, vx_alvo, c_.acel_x_max * dt);
            cmd_vz_ = ibvs_detalhe::desliza(cmd_vz_, vz_alvo, c_.acel_z_max * dt);
        }

        // ---- saneamento: nada de NaN para a cascata
        bool bom = finito(cmd_vx_) && finito(cmd_vz_) && finito(cmd_yaw_) && finito(i_yaw_) && filtro_.saudavel();
        if (!bom) {
            filtro_.zerar();
            estado_ = PERDIDO;
            tem_det_ = false;
            cmd_vx_ = 0.0f;
            cmd_vz_ = 0.0f;
            cmd_yaw_ = 0.0f;
            i_yaw_ = 0.0f;
            cont_reaq_ = 0;
            flags |= kFlagFalhaNumerica;
            tem_pred = false;
            procura = 0;
        }

        o.vx = cmd_vx_;
        o.vy = 0.0f;
        o.vz = cmd_vz_;
        o.yaw_taxa = cmd_yaw_;
        o.estado = estado_;
        o.flags = flags;
        if (tem_pred && bom) {
            o.e_psi = e_psi;
            o.e_elev = e_el;
            o.dist = dist;
            o.taxa_bearing = w_los;
            o.acel_bearing = a_los;
        } else {
            o.az_pred = 0.0f;
            o.el_pred = 0.0f;
            o.u_pred = 0.0f;
            o.v_pred = 0.0f;
            o.raio_pred = 0.0f;
        }
        o.t_sem_det_s = t_sem > 1e8f ? -1.0f : t_sem;
        o.n_aceites = filtro_.inicializado() ? filtro_.n_aceites() : 0;
        o.n_rejeitadas = n_rej_total_;
        o.procura = procura;
        return o;
    }

private:
    void atualizar_estado(uint32_t t_us, bool aceite, bool reinicio, bool nova, float t_sem) {
        const int32_t antes = estado_;
        if (estado_ == A_SEGUIR || estado_ == EM_FALTA) {
            if (reinicio) {  // a pista saltou (3 outliers seguidos): confirma antes de confiar
                estado_ = REAQUISICAO;
                cont_reaq_ = 1;
                i_yaw_ = 0.0f;
            } else if (t_sem > c_.t_falta_s) {
                estado_ = PERDIDO;
            } else if (t_sem > c_.t_gap_s) {
                estado_ = EM_FALTA;
            } else {
                estado_ = A_SEGUIR;
            }
        } else if (estado_ == PERDIDO) {
            if (aceite) {
                estado_ = REAQUISICAO;
                cont_reaq_ = 1;
            }
        } else {  // REAQUISICAO
            if (reinicio) {
                cont_reaq_ = 1;
            } else if (aceite) {
                ++cont_reaq_;
            } else if (nova || t_sem > c_.t_gap_s) {  // falha durante a confirmação
                estado_ = PERDIDO;
            }
        }
        if (estado_ == REAQUISICAO && cont_reaq_ >= c_.n_reaq) estado_ = A_SEGUIR;
        if (estado_ == PERDIDO && antes != PERDIDO) {
            t_perdido_ = t_us;
            cont_reaq_ = 0;
            i_yaw_ = 0.0f;
        }
    }

    ConfigSeguidor c_;
    geo::Otica ot_;
    HistoricoAtitude hist_;
    FiltroAlvo filtro_;
    Atitude att_ant_;
    bool pronto_;
    bool tem_t_;
    bool tem_n_;
    bool tem_det_;
    bool tem_att_;
    int32_t estado_;
    int32_t n_ant_;
    int32_t cont_reaq_;
    int32_t n_rej_total_;
    uint32_t t_ant_;
    uint32_t t_ult_det_;
    uint32_t t_perdido_;
    float lado_;
    float i_yaw_;
    float cmd_vx_;
    float cmd_vz_;
    float cmd_yaw_;
};

// Janela de busca para o PRÓXIMO frame a partir da previsão do seguidor: um quadrado centrado em (u_pred, v_pred)
// com meia-largura 3·raio_pred + 12 px (cobre a incerteza da previsão); sem previsão (PERDIDO/REAQUISICAO ou fora
// do campo) fica a imagem inteira. Preenche só os campos roi_* de `p`.
inline void janela_de_previsao(const SaidaSeguidor& s, ParamsDetetor* p) {
    p->roi_x0 = 0;
    p->roi_y0 = 0;
    p->roi_x1 = 0;
    p->roi_y1 = 0;
    if ((s.estado != A_SEGUIR && s.estado != EM_FALTA) || !(s.raio_pred > 0.0f)) return;
    if (!(geo::finito(s.u_pred) && geo::finito(s.v_pred) && geo::finito(s.raio_pred))) return;
    const float meia = geo::limita(3.0f * s.raio_pred + 12.0f, 12.0f, 2000.0f);
    const float uc = geo::limita(s.u_pred, -4000.0f, 4000.0f);
    const float vc = geo::limita(s.v_pred, -4000.0f, 4000.0f);
    p->roi_x0 = static_cast<int32_t>(uc - meia);
    p->roi_y0 = static_cast<int32_t>(vc - meia);
    p->roi_x1 = static_cast<int32_t>(uc + meia) + 1;
    p->roi_y1 = static_cast<int32_t>(vc + meia) + 1;
    if (p->roi_x1 <= 0 || p->roi_y1 <= 0) {  // fora do campo: imagem inteira
        p->roi_x0 = 0;
        p->roi_y0 = 0;
        p->roi_x1 = 0;
        p->roi_y1 = 0;
    }
}

}  // namespace visao
}  // namespace nucleo
