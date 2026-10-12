// firmware/nucleo/nucleo.cpp — implementação da classe Nucleo (ver nucleo.hpp).
#include "nucleo.hpp"

namespace nucleo {

namespace {

// Mesma leitura? (giroscópio, acelerómetro, ToF, fluxo e contadores de amostras iguais)
bool mesma_amostra(const Sensores& a, const Sensores& b) {
    bool igual = a.tof_d == b.tof_d && a.tof_ok == b.tof_ok && a.n_tof == b.n_tof;
    igual = igual && a.fluxo_ok == b.fluxo_ok && a.n_fluxo == b.n_fluxo;
    for (int k = 0; k < 3; ++k) igual = igual && a.giro[k] == b.giro[k] && a.acc[k] == b.acc[k];
    for (int k = 0; k < 2; ++k) igual = igual && a.fluxo[k] == b.fluxo[k];
    return igual;
}

}  // namespace

bool Nucleo::iniciar(const Config& cfg) {
    pronto_ = false;
    if (!config_valida(cfg)) return false;
    if (cfg.usa_visao != 0 && !visao::config_valida(cfg.seguidor)) return false;
    cfg_ = cfg;
    if (cfg_.usa_cascata != 0) cascata_.iniciar(cfg_.cascata);
    if (cfg_.usa_visao != 0 && !seguidor_.iniciar(cfg_.seguidor)) return false;
    pronto_ = true;
    reiniciar();
    return true;
}

void Nucleo::reiniciar() {
    taxa_.reiniciar();
    est_.zerar();
    est_cl_.zerar();
    cascata_.reiniciar();
    if (cfg_.usa_visao != 0) seguidor_.reiniciar();
    saida_seguidor_ = visao::SaidaSeguidor();
    ref_ = ReferenciasTaxa();
    cmd_ef_ = Comando();
    coletivo_ = 0.0f;
    acum_dt_ = 0.0f;
    flags_decisao_ = 0;
    cont_cascata_ = 0;
    modo_ant_ = 0;
    tem_modo_ant_ = false;
    tem_decisao_ = false;
    calibrado_ = false;
    dedupe_pendente_ = false;
}

void Nucleo::armar(bool armado) {
    if (armado && !taxa_.armado()) {  // desarmado → armado: a cascata recomeça (zera integradores, trava na 1.ª decisão)
        cont_cascata_ = 0;
        acum_dt_ = 0.0f;
        tem_decisao_ = false;
    }
    taxa_.armar(armado);
    cascata_.armar(armado);
}

void Nucleo::calibrar(const Sensores& s) {
    if (cfg_.estimador_classico != 0) {
        est_cl_.iniciar_com(s);
    } else {
        est_.calibrar(s);
    }
    calibrado_ = true;
    amostra_calibracao_ = s;
    dedupe_pendente_ = true;
}

void Nucleo::calibrar_chao(bool ativa) {
    if (!pronto_ || cfg_.estimador_classico == 0) return;
    est_cl_.janela_calibracao(cfg_, ativa);
    if (ativa) {  // a janela define o estado inicial: não há auto-calibração por uma só leitura no 1.º passo
        calibrado_ = true;
        dedupe_pendente_ = false;
    }
}

void Nucleo::travar_referencias(bool com_z_alvo, float z_alvo) {
    if (!pronto_ || cfg_.usa_cascata == 0) return;
    const Saida e = estimativas();
    cascata_.travar(e, com_z_alvo, z_alvo);
    cont_cascata_ = 0;
    acum_dt_ = 0.0f;
    tem_decisao_ = false;
}

void Nucleo::preencher_estimativas(Saida& o) const {
    if (cfg_.estimador_classico != 0) {
        o.roll = est_cl_.roll;
        o.pitch = est_cl_.pitch;
        o.psi = est_cl_.psi;
        o.h = est_cl_.h;
        o.vz = est_cl_.vz;
        o.vx = est_cl_.vx;
        o.vy = est_cl_.vy;
        o.x = est_cl_.x;
        o.y = est_cl_.y;
    } else {
        o.roll = est_.roll;
        o.pitch = est_.pitch;
        o.psi = est_.psi;
        o.h = est_.h;
        o.vz = est_.vz;
        o.vx = est_.vx;
        o.vy = est_.vy;
        o.x = est_.x;
        o.y = est_.y;
    }
    for (int e = 0; e < 3; ++e) o.giro_f[e] = taxa_.giro_f(e);
}

Saida Nucleo::estimativas() const {
    Saida o = {};
    preencher_estimativas(o);
    if (taxa_.armado()) o.flags = kFlagArmado;
    return o;
}

float Nucleo::dt_valido(float dt) const {
    return (!e_finito(dt) || !(dt > 0.0f)) ? cfg_.dt_nominal : dt;
}

// Acelerador de pairagem À TENSÃO MEDIDA (compensação de tensão): u_pair(V) = ESC⁻¹(upv_k/V), a curva do ESC linear por
// troços com cortes nos extremos (np.interp). Monitor inválido (V ≤ v_bat_valida_min ou não finito) ⇒ o nominal.
// O «1,0» do coletivo continua a ser «pairar» de 100 % a 10 % de carga (a mesma conta do DroneRealEnv._comando;
// Betaflight: vbat_sag_compensation).
float Nucleo::acelerador_de_pairagem(float v_bat) const {
    if (!(e_finito(v_bat) && v_bat > cfg_.v_bat_valida_min)) return cfg_.cascata.u_pairagem;
    const int32_t n = cfg_.n_esc;
    float d = cfg_.upv_k / v_bat;
    if (d > cfg_.esc_d[n - 1]) d = cfg_.esc_d[n - 1];  // min(duty, duty_max)
    float u = cfg_.esc_u[0];
    if (d > cfg_.esc_d[0]) {
        int32_t k = 1;
        while (k < n - 1 && d > cfg_.esc_d[k]) ++k;
        const float f = (d - cfg_.esc_d[k - 1]) / (cfg_.esc_d[k] - cfg_.esc_d[k - 1]);
        u = cfg_.esc_u[k - 1] + f * (cfg_.esc_u[k] - cfg_.esc_u[k - 1]);
    }
    return u < 1.0f ? u : 1.0f;
}

// Empuxo coletivo T/(m·g) → acelerador [0,1]: u = u_pair(V)·√c (T ∝ ω² ∝ u²).
float Nucleo::acelerador_de_coletivo(float coletivo, float v_bat) const {
    const float u = acelerador_de_pairagem(v_bat) * sqrtf(coletivo > 0.0f ? coletivo : 0.0f);
    return limita(u, 0.0f, 1.0f);
}

// Comando → referências do laço de taxa (acelerador + taxas). PONTO DE LIGAÇÃO dos laços externos:
//   CTBR é a identidade (o comando JÁ É acelerador + taxas). VELOCIDADE / YAW_ALVO / OLHAR correm a cascata clássica
//   (cascata.hpp) 1× por `decimacao` chamadas (50 Hz com 500 Hz); em OLHAR o Seguidor (ibvs.hpp) gera antes a
//   velocidade e a taxa de yaw a partir de Sensores::camera. Entre decisões mantêm-se as referências (ZOH). Modo
//   inexistente — ou cascata/visão não configuradas (usa_cascata/usa_visao = 0) — cai em CTBR com kFlagModoReservado.
ReferenciasTaxa Nucleo::resolver_modo(const Sensores& s, const Comando& c, float dt, Saida& o, int32_t& flags) {
    ReferenciasTaxa r = {};
    const bool pede_cascata = c.modo == VELOCIDADE || c.modo == YAW_ALVO || c.modo == OLHAR;
    const bool disponivel = cfg_.usa_cascata != 0 && (c.modo != OLHAR || cfg_.usa_visao != 0);
    if (!pede_cascata || !disponivel) {
        r.acelerador = c.coletivo;
        for (int e = 0; e < 3; ++e) r.taxas[e] = c.taxas[e];
        if (c.modo != CTBR) flags |= kFlagModoReservado;
        o.acelerador = e_finito(r.acelerador) ? limita(r.acelerador, 0.0f, 1.0f) : 0.0f;  // diagnóstico: o que o laço de taxa usa
        for (int e = 0; e < 3; ++e) o.taxas_ref[e] = r.taxas[e];
        return r;
    }
    if (est_cl_.calibrando()) {  // parado no chão a calibrar: neutro (motores em idle se armado)
        o.coletivo = 0.0f;
        return r;
    }
    acum_dt_ += dt;
    if (cont_cascata_ == 0) {  // ---- uma decisão da cascata
        const float dt_c = tem_decisao_ ? acum_dt_ : static_cast<float>(cfg_.cascata.decimacao) * dt;
        acum_dt_ = 0.0f;
        tem_decisao_ = true;
        Comando ef = c;
        if (c.modo == OLHAR) {
            if (!tem_modo_ant_ || modo_ant_ != OLHAR) seguidor_.reiniciar();  // ao ENTRAR em OLHAR o filtro e a procura recomeçam
            visao::Atitude a;
            a.roll = o.roll;
            a.pitch = o.pitch;
            a.psi = o.psi;
            a.vx = o.vx;
            a.vy = o.vy;
            a.vz = o.vz;
            saida_seguidor_ = seguidor_.passo(s.t_us, a, s.camera);
            ef.modo = VELOCIDADE;
            ef.vx = saida_seguidor_.vx;
            ef.vy = saida_seguidor_.vy;
            ef.vz = saida_seguidor_.vz;
            ef.yaw_taxa = saida_seguidor_.yaw_taxa;
        }
        modo_ant_ = c.modo;
        tem_modo_ant_ = true;
        const Cascata::Resultado res = cascata_.passo(cfg_.cascata, o, s.giro, ef, dt_c);
        if ((res.flags & kFlagFalhaCascata) == 0) cmd_ef_ = ef;  // um comando recusado (não finito) não é «o efetivo»
        coletivo_ = res.coletivo;
        flags_decisao_ = res.flags;
        ref_.acelerador = acelerador_de_coletivo(res.coletivo, s.v_bat);
        for (int e = 0; e < 3; ++e) ref_.taxas[e] = res.taxas[e];
    }
    cont_cascata_ = (cont_cascata_ + 1 >= cfg_.cascata.decimacao) ? 0 : cont_cascata_ + 1;
    flags |= flags_decisao_;
    r = ref_;
    o.coletivo = coletivo_;
    o.acelerador = r.acelerador;
    for (int e = 0; e < 3; ++e) o.taxas_ref[e] = r.taxas[e];
    o.v_ref[0] = cmd_ef_.vx;
    o.v_ref[1] = cmd_ef_.vy;
    o.v_ref[2] = cmd_ef_.vz;
    o.yaw_taxa_ref = cmd_ef_.yaw_taxa;
    if (c.modo == OLHAR) o.seguidor = saida_seguidor_;
    cascata_.diagnostico(o);
    return r;
}

ReferenciasTaxa Nucleo::planear(const Sensores& s, const Comando& c, float dt, Saida& o) {
    if (!pronto_) {
        o.flags = kFlagNaoIniciado;
        return ReferenciasTaxa();
    }
    dt = dt_valido(dt);

    // 1. estimador (a 1.ª leitura depois de reiniciar() calibra-o em vez de ser integrada; a leitura de uma
    //    calibração explícita, repetida no passo seguinte, também não se integra duas vezes)
    bool consumida = dedupe_pendente_ && mesma_amostra(s, amostra_calibracao_);
    if (!calibrado_) {
        calibrar(s);
        consumida = true;
    }
    dedupe_pendente_ = false;
    if (!consumida) {
        if (cfg_.estimador_classico != 0) {
            est_cl_.passo(cfg_, s, dt);
        } else {
            est_.passo(cfg_, s, dt);
        }
    }
    preencher_estimativas(o);

    // 2. referências do laço de taxa (os laços externos ligam-se em resolver_modo)
    int32_t flags = 0;
    if (est_cl_.calibrando()) flags |= kFlagCalibrando;
    ReferenciasTaxa ref = resolver_modo(s, c, dt, o, flags);
    ref.flags = flags;
    return ref;
}

void Nucleo::atuar(const ReferenciasTaxa& ref, const Sensores& s, float dt, Saida& o) {
    if (!pronto_) {
        o.flags = kFlagNaoIniciado;
        return;
    }
    dt = dt_valido(dt);

    // 3. laço de taxa + mistura + airmode
    int32_t flags = ref.flags;
    flags |= taxa_.passo(cfg_, ref.acelerador, ref.taxas, s.giro, dt, o.motor, o.u_eixos);

    // 4. saneamento: nada de NaN para os ESC; um estimador corrompido recalibra-se no passo seguinte
    bool motores_ok = true;
    for (int i = 0; i < 4; ++i) motores_ok = motores_ok && e_finito(o.motor[i]);
    if (!motores_ok) {
        for (int i = 0; i < 4; ++i) o.motor[i] = 0.0f;
        taxa_.reiniciar();  // desarma e limpa o estado do PID
        flags = (flags & ~kFlagArmado) | kFlagFalhaNumerica;
    }
    bool est_ok;
    if (cfg_.estimador_classico != 0) {
        est_ok = e_finito(est_cl_.roll) && e_finito(est_cl_.pitch) && e_finito(est_cl_.psi) &&
                 e_finito(est_cl_.h) && e_finito(est_cl_.vz) && e_finito(est_cl_.vx) &&
                 e_finito(est_cl_.vy) && e_finito(est_cl_.x) && e_finito(est_cl_.y);
    } else {
        est_ok = e_finito(est_.roll) && e_finito(est_.pitch) && e_finito(est_.psi) &&
                 e_finito(est_.h) && e_finito(est_.vz) && e_finito(est_.vx) &&
                 e_finito(est_.vy) && e_finito(est_.x) && e_finito(est_.y);
    }
    if (!est_ok) {
        est_.zerar();
        est_cl_.zerar();
        calibrado_ = false;
        dedupe_pendente_ = false;
        flags |= kFlagFalhaNumerica;
    }

    preencher_estimativas(o);
    o.flags = flags;
}

Saida Nucleo::passo(const Sensores& s, const Comando& c, float dt) {
    Saida o = {};
    if (!pronto_) {
        o.flags = kFlagNaoIniciado;
        return o;
    }
    dt = dt_valido(dt);
    const ReferenciasTaxa ref = planear(s, c, dt, o);
    atuar(ref, s, dt, o);
    return o;
}

}  // namespace nucleo
