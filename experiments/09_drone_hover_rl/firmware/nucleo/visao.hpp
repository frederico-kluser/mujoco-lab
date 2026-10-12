// firmware/nucleo/visao.hpp — DETETOR de círculo/blob brilhante num frame MONOCROMÁTICO (uint8), C++ float32, sem heap.
//
// O sensor da Portenta Vision Shield (HM0360 640×480 / HM01B0 320×320) é mono de 8 bit: o alvo distingue-se por
// BRILHO, não por cor (uma esfera branca/IR; ver README). O detetor é o «limiar + momentos» da pesquisa
// (pesquisas/2026-10-12-para-um-quadricoptero-grande-*.md, Q6): O(píxeis), SEM Hough, sem histograma:
//
//   1.ª passagem (só no modo adaptativo): máximo ROBUSTO da imagem (máx. de min(p[i], p[i+1]) — um píxel quente
//        isolado não conta) e fundo = média de uma grelha esparsa (1 em 8 colunas × 1 em 8 linhas, ≈ 1/64 dos
//        píxeis);   limiar = fundo + frac_max·(máx − fundo)   (frac_max = 0,5 → a meia-altura da borda do disco).
//        Contraste (máx − fundo) < max(contraste_min, k_ruido·σ̂) ⇒ «sem alvo»: σ̂ = ruído estimado nas diferenças da
//        grelha (rejeita frames só com ruído — o máximo de N amostras gaussianas ≈ 4,2σ — e vinheta).
//   2.ª passagem: varrimento por LINHAS em «runs» (píxeis consecutivos ≥ limiar) com etiquetagem de componentes
//        ligados (8-conectividade) em STREAMING: só há acumuladores para os componentes ATIVOS (≤ kMaxComp),
//        por isso um poste/barra que atravessa o frame inteiro não esgota a memória e vários blobs no mesmo
//        frame são avaliados SEPARADAMENTE (um distrator alongado deixa de esconder o alvo).
//        Por componente (inteiros exatos): n, Σx, Σy, Σx², Σy², Σxy (fechadas em forma por run — custo O(runs));
//        e, pesados pela intensidade acima do limiar (w = I − limiar + 1): Σw, Σw·x, Σw·y → CENTRÓIDE SUB-PÍXEL.
//   Gates: área ∈ [area_min, area_max]; não toca o bordo (alvo cortado pelo FOV ⇒ centróide enviesado);
//        CIRCULARIDADE = λ_min/λ_max dos momentos centrais (1 = disco, → 0 alongado); «cheio» = r_momentos/r_área
//        (≈ 1 num disco; ≫ 1 num anel ou numa dispersão). Escolhe o blob válido com mais massa Σw.
//   Convenção de píxeis: ÍNDICE — o centro do píxel (0,0) é (0,0). (A projeção do MuJoCo/`visao.projetar` usa a
//        convenção da BORDA: u_índice = u_borda − 0,5 — é essa a origem do «0,708 px» do gate do visao.py.)
//
// Janela de busca (ROI): roi_x0..roi_y1 limitam as DUAS passagens (modo de seguimento: ≈ janela à volta da
// posição prevista — custo O(janela) e distratores fora dela ignorados). Um blob cortado pela janela é recusado
// (M_JANELA): a janela é pequena demais, repete-se com a imagem inteira.
//
// Memória: o frame (W·H bytes: 76,8 kB em QVGA) é do chamador (DCMI/DMA); o Detetor guarda ≈ 5,7 kB de trabalho
// (instância estática .bss). Sem libm além de sqrtf. Sem alocação dinâmica. Uma só divisão inteira por variável (o fundo:
// `sdiv` por hardware no M4/M7 — o teste confere que não há __aeabi_idiv); inteiros de 64 bit só em somas/produtos.
//
// Kernels dos ciclos: -DNUCLEO_VISAO_NOINLINE (visao_tipos.hpp) separa-os em funções para o llvm-mca; sem a macro inlinam.
#pragma once

#include <math.h>
#include <stdint.h>

#include "visao_tipos.hpp"

namespace nucleo {
namespace visao {

constexpr int32_t kLadoMax = 1000;       // W, H ≤ 1000: as somas de quadrados por run cabem em int32
constexpr int32_t kMaxRunsLinha = 80;    // runs guardados por linha (a seguir, deitam-se fora e flag `excesso`)
constexpr int32_t kMaxComp = 48;         // componentes ativos em simultâneo

namespace detalhe {

inline bool finito(float x) { return (x - x) == 0.0f; }  // falso para NaN e ±inf
inline int32_t limita_i(int32_t x, int32_t lo, int32_t hi) { return x < lo ? lo : (x > hi ? hi : x); }

// int64 → float sem a chamada de biblioteca __aeabi_l2f (nos alvos Cortex-M)
inline float a_float(int64_t v) {
    const bool neg = v < 0;
    const uint64_t m = neg ? static_cast<uint64_t>(-v) : static_cast<uint64_t>(v);
    const float f = static_cast<float>(static_cast<uint32_t>(m >> 32)) * 4294967296.0f +
                    static_cast<float>(static_cast<uint32_t>(m & 0xFFFFFFFFu));
    return neg ? -f : f;
}

// Σ_{i=0..k} i² (k ≤ 999 ⇒ cabe em int32); s2(−1) = 0
inline int32_t soma_quadrados(int32_t k) { return k * (k + 1) * (2 * k + 1) / 6; }

// ---------------------------------------------------------------------------------------------- kernels
// máximo de min(p[i], p[i+1]) numa linha de n ≥ 1 píxeis: um píxel quente isolado não conta. Dois acumuladores
// independentes (menos cadeia de dependência por píxel no M7 dual-issue).
NUCLEO_VISAO_KERNEL inline int32_t k_max_robusto(const uint8_t* p, int32_t n) {
    int32_t m0 = 0;
    int32_t m1 = 0;
    int32_t a = p[0];
    int32_t i = 1;
    for (; i + 1 < n; i += 2) {
        const int32_t b = p[i];
        const int32_t c = p[i + 1];
        const int32_t mn0 = a < b ? a : b;
        const int32_t mn1 = b < c ? b : c;
        if (mn0 > m0) m0 = mn0;
        if (mn1 > m1) m1 = mn1;
        a = c;
    }
    if (i < n) {
        const int32_t b = p[i];
        const int32_t mn = a < b ? a : b;
        if (mn > m0) m0 = mn;
    }
    return m0 > m1 ? m0 : m1;
}

// soma de 1 em cada 8 píxeis (grelha esparsa do fundo) e soma das |diferenças| entre amostras consecutivas (o ruído)
NUCLEO_VISAO_KERNEL inline int32_t k_soma_grelha(const uint8_t* p, int32_t n, int32_t* soma_dif) {
    int32_t s = 0;
    int32_t d = 0;
    int32_t ant = p[0];
    for (int32_t i = 0; i < n; i += 8) {
        const int32_t v = p[i];
        s += v;
        d += v > ant ? v - ant : ant - v;
        ant = v;
    }
    *soma_dif = d;
    return s;
}

// índice do 1.º píxel ≥ thr em [x, x1) (ou x1); 2 píxeis por iteração
NUCLEO_VISAO_KERNEL inline int32_t k_saltar(const uint8_t* p, int32_t x, int32_t x1, int32_t thr) {
    while (x + 1 < x1) {
        if (static_cast<int32_t>(p[x]) >= thr) return x;
        if (static_cast<int32_t>(p[x + 1]) >= thr) return x + 1;
        x += 2;
    }
    if (x < x1 && static_cast<int32_t>(p[x]) >= thr) return x;
    return x1;
}

// run de píxeis consecutivos ≥ thr a partir de x (p[x] ≥ thr à entrada): Σw e Σw·x com w = valor − thr + 1;
// devolve o índice do 1.º píxel depois do run
NUCLEO_VISAO_KERNEL inline int32_t k_run(const uint8_t* p, int32_t x, int32_t x1, int32_t thr, int32_t* sw,
                                          int32_t* swx) {
    int32_t s = 0;
    int32_t sx = 0;
    do {
        const int32_t w = static_cast<int32_t>(p[x]) - thr + 1;
        s += w;
        sx += w * x;
        ++x;
    } while (x < x1 && static_cast<int32_t>(p[x]) >= thr);
    *sw = s;
    *swx = sx;
    return x;
}

}  // namespace detalhe

// Parâmetros por omissão para um frame W×H (alvo ≈ esfera de 5 cm entre 0,7 e 4 m com f ≈ 0,7·W px).
inline ParamsDetetor params_padrao(int32_t largura, int32_t altura) {
    ParamsDetetor p = {};
    p.frac_max = 0.5f;
    p.contraste_min = 40;
    p.paso_max = 1;
    p.area_min = 6.0f;
    p.area_max = 0.06f * static_cast<float>(largura) * static_cast<float>(altura);
    p.circ_min = 0.6f;
    p.cheio_min = 0.8f;
    p.cheio_max = 1.3f;
    p.margem_borda = 1;
    p.k_ruido = 8.0f;
    return p;
}

// Constrói a medida de câmara (o que o núcleo de voo consome) a partir da deteção, do contador de frames e do
// instante da captura (µs).
inline Camera camera_de(const Deteccao& d, int32_t n, uint32_t t_us) {
    Camera c = {};
    c.valido = d.valido;
    c.u = d.u;
    c.v = d.v;
    c.raio = d.raio_px;
    c.n = n;
    c.t = t_us;
    return c;
}

class Detetor {
public:
    // Deteta o disco mais «forte» do frame (W×H, linha a linha, sem padding). limiar > 0 = limiar FIXO (1..255,
    // salta a 1.ª passagem); limiar ≤ 0 = adaptativo (p.frac_max). Nunca lê fora do frame nem da janela.
    Deteccao detetar(const uint8_t* frame, int32_t largura, int32_t altura, int32_t limiar,
                     const ParamsDetetor& p) {
        Deteccao d = {};
        d.motivo = M_PARAMETROS;
        if (frame == nullptr || largura < 2 || altura < 2 || largura > kLadoMax || altura > kLadoMax) return d;
        if (!detalhe::finito(p.frac_max) || !detalhe::finito(p.area_min) || !detalhe::finito(p.area_max) ||
            !detalhe::finito(p.circ_min) || !detalhe::finito(p.cheio_min) || !detalhe::finito(p.cheio_max)) {
            return d;
        }
        w_ = largura;
        h_ = altura;
        p_ = p;
        const bool janela = p.roi_x1 > 0 && p.roi_y1 > 0;
        rx0_ = janela ? detalhe::limita_i(p.roi_x0, 0, largura) : 0;
        ry0_ = janela ? detalhe::limita_i(p.roi_y0, 0, altura) : 0;
        rx1_ = janela ? detalhe::limita_i(p.roi_x1, 0, largura) : largura;
        ry1_ = janela ? detalhe::limita_i(p.roi_y1, 0, altura) : altura;
        if (rx1_ - rx0_ < 2 || ry1_ - ry0_ < 2) return d;
        const int32_t nx = rx1_ - rx0_;

        // ---- 1.ª passagem: limiar
        int32_t thr = 0;
        if (limiar > 0) {
            thr = detalhe::limita_i(limiar, 1, 255);
        } else {
            const int32_t paso = p.paso_max < 1 ? 1 : p.paso_max;
            int32_t vmax = 0;
            for (int32_t y = ry0_; y < ry1_; y += paso) {
                const int32_t m = detalhe::k_max_robusto(frame + y * largura + rx0_, nx);
                if (m > vmax) vmax = m;
            }
            int32_t soma = 0;
            int32_t soma_dif = 0;
            int32_t cont = 0;
            int32_t n_dif = 0;
            for (int32_t y = ry0_; y < ry1_; y += 8) {
                int32_t dif = 0;
                soma += detalhe::k_soma_grelha(frame + y * largura + rx0_, nx, &dif);
                soma_dif += dif;
                const int32_t ns = (nx + 7) / 8;
                cont += ns;
                n_dif += ns - 1;
            }
            const int32_t fundo = cont > 0 ? soma / cont : 0;
            // σ̂ do ruído: E|X − Y| = 2σ/√π para amostras independentes de N(μ, σ²) ⇒ σ̂ = (Σ|Δ|/n)·0,8862
            const float ruido = n_dif > 0 ? static_cast<float>(soma_dif) / static_cast<float>(n_dif) * 0.88622692545275801365f : 0.0f;
            d.vmax = vmax;
            d.fundo = fundo;
            d.ruido = ruido;
            float minimo = static_cast<float>(p.contraste_min);
            if (detalhe::finito(p.k_ruido) && p.k_ruido * ruido > minimo) minimo = p.k_ruido * ruido;
            if (static_cast<float>(vmax - fundo) < minimo || vmax < 2) {
                d.motivo = M_SEM_ALVO;
                return d;
            }
            const float frac = p.frac_max < 0.0f ? 0.0f : (p.frac_max > 1.0f ? 1.0f : p.frac_max);
            thr = fundo + static_cast<int32_t>(frac * static_cast<float>(vmax - fundo) + 0.5f);
            thr = detalhe::limita_i(thr, fundo + 1, vmax);
            thr = detalhe::limita_i(thr, 1, 255);
        }
        d.limiar = thr;

        // ---- 2.ª passagem: runs + componentes ligados em streaming
        comecar();
        for (int32_t y = ry0_; y < ry1_; ++y) {
            const uint8_t* linha = frame + y * largura;
            n_cur_ = 0;
            pp_ = 0;
            int32_t x = rx0_;
            while (x < rx1_) {
                x = detalhe::k_saltar(linha, x, rx1_, thr);
                if (x >= rx1_) break;
                const int32_t xa = x;
                int32_t sw = 0;
                int32_t swx = 0;
                x = detalhe::k_run(linha, x, rx1_, thr, &sw, &swx);
                novo_run(y, xa, x - 1, sw, swx);
            }
            fim_de_linha(y);
        }
        for (int32_t c = 0; c < kMaxComp; ++c) {
            if (comp_[c].viva == 1) {
                avaliar(c);
                comp_[c].viva = 0;
            }
        }

        // ---- resultado
        d.n_blobs = n_blobs_;
        d.excesso = excesso_;
        if (tem_melhor_) {
            d.valido = 1;
            d.motivo = M_OK;
            d.u = melhor_u_;
            d.v = melhor_v_;
            d.raio_px = melhor_raio_;
            d.circularidade = melhor_circ_;
            d.area = melhor_area_;
            d.cheio = melhor_cheio_;
        } else {
            d.motivo = n_blobs_ > 0 ? pior_motivo_ : M_SEM_BLOB;
        }
        return d;
    }

private:
    struct Run {
        int32_t x0;
        int32_t x1;
        int32_t comp;
    };

    struct Comp {
        int32_t pai;     // union-find: índice do componente (ele próprio se for raiz)
        int32_t viva;    // 0 livre · 1 ativa · 2 alias (fundida noutra, liberta no fim da linha)
        int32_t ult_y;   // última linha com um run
        int32_t n;
        int32_t sx;
        int32_t sy;
        int64_t sxx;
        int64_t syy;
        int64_t sxy;
        float sw;
        float swx;
        float swy;
        int32_t borda;
        int32_t janela;
    };

    void comecar() {
        n_prev_ = 0;
        n_cur_ = 0;
        n_alias_ = 0;
        pp_ = 0;
        n_blobs_ = 0;
        excesso_ = 0;
        tem_melhor_ = false;
        melhor_peso_ = 0.0f;
        pior_motivo_ = M_SEM_BLOB;
        pior_peso_ = -1.0f;
        for (int32_t c = 0; c < kMaxComp; ++c) comp_[c].viva = 0;
    }

    int32_t encontrar(int32_t i) {
        while (comp_[i].pai != i) {
            comp_[i].pai = comp_[comp_[i].pai].pai;
            i = comp_[i].pai;
        }
        return i;
    }

    int32_t nova_comp() {
        for (int32_t c = 0; c < kMaxComp; ++c) {
            if (comp_[c].viva == 0) {
                Comp& k = comp_[c];
                k.pai = c;
                k.viva = 1;
                k.ult_y = -1;
                k.n = 0;
                k.sx = 0;
                k.sy = 0;
                k.sxx = 0;
                k.syy = 0;
                k.sxy = 0;
                k.sw = 0.0f;
                k.swx = 0.0f;
                k.swy = 0.0f;
                k.borda = 0;
                k.janela = 0;
                return c;
            }
        }
        return -1;
    }

    // funde duas raízes (a de menor índice fica); devolve a raiz
    int32_t unir(int32_t a, int32_t b) {
        if (a == b) return a;
        const int32_t r = a < b ? a : b;
        const int32_t o = a < b ? b : a;
        Comp& R = comp_[r];
        const Comp& O = comp_[o];
        R.n += O.n;
        R.sx += O.sx;
        R.sy += O.sy;
        R.sxx += O.sxx;
        R.syy += O.syy;
        R.sxy += O.sxy;
        R.sw += O.sw;
        R.swx += O.swx;
        R.swy += O.swy;
        R.borda |= O.borda;
        R.janela |= O.janela;
        if (O.ult_y > R.ult_y) R.ult_y = O.ult_y;
        comp_[o].pai = r;
        comp_[o].viva = 2;
        alias_[n_alias_++] = o;  // libertados no fim da linha (≤ kMaxComp: cada componente funde-se uma só vez)
        return r;
    }

    NUCLEO_VISAO_KERNEL void novo_run(int32_t y, int32_t xa, int32_t xb, int32_t sw, int32_t swx) {
        if (n_cur_ >= kMaxRunsLinha) {
            excesso_ = 1;
            return;
        }
        // 8-conectividade: junta os componentes dos runs da linha anterior que tocam [xa−1, xb+1]
        while (pp_ < n_prev_ && prev_[pp_].x1 + 1 < xa) ++pp_;
        int32_t raiz = -1;
        for (int32_t q = pp_; q < n_prev_ && prev_[q].x0 <= xb + 1; ++q) {
            const int32_t c = encontrar(prev_[q].comp);
            raiz = raiz < 0 ? c : unir(raiz, c);
        }
        if (raiz < 0) {
            raiz = nova_comp();
            if (raiz < 0) {  // sem capacidade: deita fora este run
                excesso_ = 1;
                return;
            }
        }
        Comp& k = comp_[raiz];
        const int32_t len = xb - xa + 1;
        const int32_t sxr = (xa + xb) * len / 2;
        k.n += len;
        k.sx += sxr;
        k.sy += y * len;
        k.sxx += static_cast<int64_t>(detalhe::soma_quadrados(xb) - detalhe::soma_quadrados(xa - 1));
        k.syy += static_cast<int64_t>(y * y * len);
        k.sxy += static_cast<int64_t>(y * sxr);
        k.sw += static_cast<float>(sw);
        k.swx += static_cast<float>(swx);
        k.swy += static_cast<float>(y) * static_cast<float>(sw);
        k.ult_y = y;
        const int32_t m = p_.margem_borda;
        if (m > 0 && (xa < m || xb >= w_ - m || y < m || y >= h_ - m)) k.borda = 1;
        if ((rx0_ > 0 && xa == rx0_) || (rx1_ < w_ && xb == rx1_ - 1) || (ry0_ > 0 && y == ry0_) ||
            (ry1_ < h_ && y == ry1_ - 1)) {
            k.janela = 1;
        }
        cur_[n_cur_].x0 = xa;
        cur_[n_cur_].x1 = xb;
        cur_[n_cur_].comp = raiz;
        ++n_cur_;
    }

    // Fim da linha y: normaliza as referências da linha atual para raízes, liberta os alias e finaliza os
    // componentes da linha ANTERIOR que não receberam run nesta (custo O(runs da linha), não O(kMaxComp)).
    NUCLEO_VISAO_KERNEL void fim_de_linha(int32_t y) {
        for (int32_t i = 0; i < n_cur_; ++i) cur_[i].comp = encontrar(cur_[i].comp);
        for (int32_t i = 0; i < n_alias_; ++i) comp_[alias_[i]].viva = 0;
        n_alias_ = 0;
        for (int32_t i = 0; i < n_prev_; ++i) {
            const int32_t c = prev_[i].comp;  // raiz (normalizada no fim da linha anterior) e ainda não finalizada?
            if (comp_[c].viva == 1 && comp_[c].ult_y < y) {
                avaliar(c);
                comp_[c].viva = 0;
            }
        }
        for (int32_t i = 0; i < n_cur_; ++i) prev_[i] = cur_[i];
        n_prev_ = n_cur_;
    }

    // Métricas e gates de um componente acabado; guarda o melhor (maior massa Σw entre os que passam tudo).
    NUCLEO_VISAO_KERNEL void avaliar(int32_t c) {
        const Comp& k = comp_[c];
        ++n_blobs_;
        const float n = static_cast<float>(k.n);
        const float raio = sqrtf(n * 0.31830988618379067154f);  // √(n/π)
        // momentos centrais EXATOS em inteiros: n²·μ20 = n·Σx² − (Σx)²
        const int64_t c20 = static_cast<int64_t>(k.n) * k.sxx - static_cast<int64_t>(k.sx) * k.sx;
        const int64_t c02 = static_cast<int64_t>(k.n) * k.syy - static_cast<int64_t>(k.sy) * k.sy;
        const int64_t c11 = static_cast<int64_t>(k.n) * k.sxy - static_cast<int64_t>(k.sx) * k.sy;
        const float inv_n2 = 1.0f / (n * n);
        float mu20 = detalhe::a_float(c20) * inv_n2 - 1.0f / 12.0f;  // − variância do próprio píxel (1/12)
        float mu02 = detalhe::a_float(c02) * inv_n2 - 1.0f / 12.0f;
        const float mu11 = detalhe::a_float(c11) * inv_n2;
        if (mu20 < 0.0f) mu20 = 0.0f;
        if (mu02 < 0.0f) mu02 = 0.0f;
        const float media = 0.5f * (mu20 + mu02);
        const float dif = 0.5f * (mu20 - mu02);
        const float raiz = sqrtf(dif * dif + mu11 * mu11);
        const float lmax = media + raiz;
        float lmin = media - raiz;
        if (lmin < 0.0f) lmin = 0.0f;
        const float circ = lmax > 1e-6f ? lmin / lmax : 0.0f;
        const float cheio = raio > 1e-6f ? sqrtf(2.0f * (lmax + lmin)) / raio : 0.0f;

        int32_t motivo = M_OK;
        if (n < p_.area_min || n > p_.area_max) {
            motivo = M_AREA;
        } else if (k.borda != 0) {
            motivo = M_BORDA;
        } else if (k.janela != 0) {
            motivo = M_JANELA;
        } else if (circ < p_.circ_min) {
            motivo = M_CIRCULARIDADE;
        } else if (cheio < p_.cheio_min || cheio > p_.cheio_max) {
            motivo = M_CHEIO;
        }
        const float peso = k.sw;
        if (motivo == M_OK) {
            if (!tem_melhor_ || peso > melhor_peso_) {
                tem_melhor_ = true;
                melhor_peso_ = peso;
                melhor_u_ = k.sw > 0.0f ? k.swx / k.sw : 0.0f;
                melhor_v_ = k.sw > 0.0f ? k.swy / k.sw : 0.0f;
                melhor_raio_ = raio;
                melhor_circ_ = circ;
                melhor_area_ = n;
                melhor_cheio_ = cheio;
            }
        } else if (peso > pior_peso_) {  // o blob dominante que falhou diz porquê
            pior_peso_ = peso;
            pior_motivo_ = motivo;
        }
    }

    // estado de trabalho (ver detetar(): tudo é reposto a cada chamada)
    ParamsDetetor p_;
    int32_t w_;
    int32_t h_;
    int32_t rx0_;
    int32_t ry0_;
    int32_t rx1_;
    int32_t ry1_;
    int32_t n_prev_;
    int32_t n_cur_;
    int32_t n_alias_;
    int32_t pp_;
    int32_t n_blobs_;
    int32_t excesso_;
    bool tem_melhor_;
    float melhor_peso_;
    float melhor_u_;
    float melhor_v_;
    float melhor_raio_;
    float melhor_circ_;
    float melhor_area_;
    float melhor_cheio_;
    int32_t pior_motivo_;
    float pior_peso_;
    int32_t alias_[kMaxComp];
    Run prev_[kMaxRunsLinha];
    Run cur_[kMaxRunsLinha];
    Comp comp_[kMaxComp];
};

}  // namespace visao
}  // namespace nucleo
