# Dinâmica explosiva e impulso — receitas verificadas

Como modelar cargas explosivas, ejetores, separação de estágios e qualquer empurrão instantâneo
**sem violar a regra do laboratório** (tudo passa por `mj_step`; nada de escrever `qvel`/teleportar).
Verificado em 2026-10-15 com o template `assets/templates/objeto-propulsado/` (cada fórmula provada
no `run.py`, exit 0): impulso entregue exato, ação-reação conservada, torque fora do centro certo.

## Quando ler este arquivo
- Criar uma explosão, ejeção, "parafuso explosivo", separação de estágio ou pulso de propulsão.
- O `run.py` do teu objeto reprovar as checagens de impulso/momento.
- Perceber por que dois corpos "soldados" não se mexem como um só.

## 1. Física (o que a simulação tem de reproduzir)
- **Impulso** J = ∫F dt (N·s). Para um corpo livre: **Δp = J** e **Δv = J/m**.
- Aplicado fora do centro de massa: **ΔL = (p − CoM) × J** (ex.: força +x a y do CoM ⇒ ΔL_z = −y·J).
- **Ação-reação**: se a carga empurra dois corpos em sentidos opostos, o momento TOTAL não muda.
- Energia cinética injetada: E = J²/(2m) (para um corpo livre) — ordem de grandeza para sanidade.
- Sempre que medires em z, lembra-te da gravidade (Δp_z = J_z − m·g·T) — ou mede no plano horizontal.

## 2. Como entregar o impulso (3 mecanismos, todos físicos)

| Mecanismo | Como | Usa quando |
|---|---|---|
| **Força por passos** (`xfrc_applied`/`qfrc_applied`) | F = J/(N·Δt) durante N passos, ANTES de cada `mj_step` | regra geral (é o template) |
| **`mj_applyFT` num ponto** | força/torque no ponto (mundo) → `qfrc` (nv) | impulso fora do centro, torque de ejeção |
| **Atuador por site** | `<general site gear="0 0 1">` com ctrl = F | pulso longo/curvo (pode ser limitado por `forcerange`) |

A classe `Carga` do template usa `mj_applyFT` → `qfrc_applied` com F constante e **duração = N passos
inteiros** (J entregue = F·N·Δt = J por construção). Regras:
- **Duração 5–10 passos** (nunca 1 passo só) e ≥ 2·Δt — a mesma ordem do `solref[0]` (`refsafe`);
  um pulso de 1 passo com força gigante é o caminho mais rápido para `mjWARN_BADQACC` + autoreset.
- O ponto de aplicação guarda-se no **frame do corpo** (move e roda com ele) e recalcula-se por passo.
- `qfrc_applied`/`xfrc_applied` **persistem** entre passos e são campos únicos: quem escreve, zera ou
  coordena (o template tem a `Carga` como única escritora; vento próprio? coordena num só passo).

## 3. Separação explosiva (parafusos/ejetores)
```xml
<equality><weld name="parafuso" body1="objeto" body2="tampa" anchor="0 0 0.07"/></equality>
```
1. **Soltar**: `data.eq_active[eid] = 0` (com `eid = mj_name2id(m, mjOBJ_EQUALITY, "parafuso")`) no
   instante da detonação — a igualdade deixa de ser resolvida.
2. **Empurrar**: +J no corpo A e −J no corpo B no mesmo ponto (ação-reação) — `Carga.detonar_separacao`.
3. Verificar: p_A = +J, p_B = −J, p_total ≈ 0, e os corpos afastam-se.

**A igualdade é uma MOLA, não cola rígida** (solref): num `weld` os dois corpos começam em queda
livre independente e a força do constraint monta-se em ~`timeconst` (ms). Consequências medidas:
- No t=0 os corpos NÃO aceleram em conjunto (objeto +0,09 m/s², tampa −0,98 m/s² com hover na totalidade);
  o parafuso assenta por volta da pose definida (testado: 0,0696 ≈ 0,07 m após 2 s) — para um
  equilíbrio exato **solta a igualdade** (corpo rígido puro) ou espera o assentamento.
- Para um acoplamento mais rígido: `solref="0.004 1"` (= 2·Δt, o limite do `refsafe`) + `dampratio` 1.

## 4. Medir corretamente (momentos no MuJoCo 3.15)
- `subtree_linvel`/`subtree_angmom` só são preenchidos por **`mujoco.mj_subtreeVel(m, d)`**
  (`flg_subtreevel` apenas regista que foi chamado — não calcula nada por si).
- Momento linear total: `p = Σ_raízes body_subtreemass·subtree_linvel` (raízes = corpos filhos do mundo).
- Momento angular sobre o CoM do sistema: `L = Σ (subtree_angmom + (rᵢ − R)×Mᵢ·vᵢ)` — helper
  `momentos()` do `run.py` do template.
- freejoint 3.15: `qvel[:3]` linear MUNDO · `qvel[3:]` angular CORPO (não o contrário!).
- Antes de ler qualquer derivado (`xpos`, `xipos`, `qacc`): `mj_forward` (ou `mj_kinematics` +
  `mj_comPos` para só posições) — após `mj_step` ficam um passo atrás.
- E ao aplicar forças: kinemática fresca ANTES do `mj_applyFT`, senão a 1.ª aplicação sai a zeros
  (medido: 9/10 do impulso chega; o template faz `_atualizar_cinematica()`).

## 5. Segurança numérica (o que rebenta com explosões)
| Risco | Sintoma | Antídoto |
|---|---|---|
| Força enorme por 1 passo | `mjWARN_BADQACC` + autoreset silencioso | 5–10 passos; `F ≤ m·Δv_max/Δt` razoável |
| `solref[0] < 2·Δt` | peça ejetada sem aviso | `refsafe` ligado (padrão); respeita 2·Δt |
| Razão de massas grande (escombro:objeto) | instabilidade de contato | ≤ ~10:1; ou simula o escombro sem contacto |
| Penetração inicial entre corpos | "explosão" sem aviso | sem sobreposição inicial; margin/gap conscientes |
| `qfrc_applied` esquecido ligado | força fantasma para sempre | zera no fim da rajada (a `Carga.limpar` faz) |

## 6. Testes de aceitação (copiar para o run.py do teu objeto)
| Efeito | Fórmula fechada | Tolerância típica |
|---|---|---|
| Impulso no CoM | Δp = J · Δv = J/m | 1 % |
| Impulso fora do centro | ΔL_z = −y·J | 2 % |
| Separação (ação-reação) | p_A = +J, p_B = −J, Σp ≈ 0 | 1 % / 1e-3 absoluto |
| Motor (torque interno) | q̇ = τ·T/I_red, ΣL ≈ 0, contra-roda | 2 % |
| Pairagem | empuxo = m·g ⇒ qacc_z = 0 | 1e-6 (corpo rígido) |

Condições isoladas: modelo FRESH por checagem (`carregar()` de novo), sem histórico, sem contacto
não pretendido (verifica as folgas: a tampa do template tem 10 mm de folga e 20 ms de teste = 2 mm de queda).
