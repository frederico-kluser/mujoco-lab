# objeto_propulsado — template de objeto com motores · propulsão · carga explosiva

Objeto de partida (2,4 kg) com **propulsão multi-eixo** (3 bocais: +X, +Y, +Z — "para todos os
locais"), um **motor** (volante de reação) e uma **carga explosiva** (separação da tampa por impulso
+ libertação do "parafuso"). Copia e adapta: é o ponto de partida testado da skill
`mujoco-propulsao-agent-skill`.

| ficheiro | o que é |
|---|---|
| `modelo.xml` | MJCF: corpo livre + 3 bocais (atuador por **site**, ctrl em N) + motor (hinge + `motor`, ctrl em N·m) + tampa presa por `weld` (equality) + IMU (acc/gyro) |
| `objeto_propulsao.py` | camada de API no padrão do laboratório: `carregar()` · `definir_*()` · `MODOS` · `ler_*()` · `Carga` (impulso físico por `mj_applyFT`) · `Ctrl` (escrita por NOME, seguro para atuadores multi-entrada) |
| `run.py` | **validação por fórmulas fechadas** (modelo fresco por checagem): hover, eixos, motor, impulso, torque fora do centro, separação — exit 0 = física são |
| `view.py` | janela com teclas de ação (pulsos de empuxo, detonar, reiniciar) |

## Arranque

```bash
uv run python run.py    # valida (exit 0) — faz SEMPRE isto antes de adaptar
uv run python view.py   # janela: W/S A/D Q/E empuxo · G detonar · R reiniciar · ESPAÇO pausa · ESC sai
```

## O que cada peça ensina (e onde está o detalhe)

- **Propulsão por site**: `<general site="bocal_x" gear="0 0 1">` — o eixo z do site é a direção da
  força (ctrl em N). Mais direções = mais `<site>` orientado + mais atuador. Empuxo de hélice/ESC real
  (kf·ω², corrente, bateria) → `references/motores-propulsao.md` e `lab/drone_rpi/propulsao.py`.
- **Motor**: `<motor joint="..." gear="1">` (torque direto). Motor DC de datasheet → atuador
  `dcmotor` (3.15). Volante de reação: o torque é INTERNO — o objeto contra-roda (ΣL ≈ 0, testado).
- **Carga explosiva**: impulso J (N·s) = força F = J/(N·Δt) durante N passos ANTES de cada `mj_step`
  (`mj_applyFT` → `qfrc_applied`) — nada de escrever `qvel`. Ação-reação na separação: +J na tampa,
  −J no objeto ⇒ momento total conservado. Detalhes e receitas → `references/explosivos-impulsao.md`.
- **Parafuso** (equality `weld`): solta-se com `data.eq_active[eid] = 0` no instante da detonação.
  CUIDADO: a equality é uma MOLA (solref): os corpos NÃO são rígidos de nascença e a força demora
  alguns ms a montar (não esperes `qacc` rígido no t=0).

## Armadilhas já resolvidas aqui (não voltes a cair nelas)

1. **Kinemática fresca antes do `mj_applyFT`**: `mj_kinematics` + `mj_comPos` (a `Carga` faz). Sem
   isto a 1.ª aplicação sai a zeros e o impulso não chega (medido: 9/10 do J).
2. **`mj_subtreeVel` para momentos**: `subtree_linvel/subtree_angmom` só são preenchidos por esta
   chamada (`flg_subtreevel` só REGISTA que foi chamado). O `run.py` tem o helper `momentos()`.
3. **freejoint 3.15**: `qvel[:3]` = linear no MUNDO, `qvel[3:]` = angular no CORPO (o inverso do que
   se adivinha).
4. **`qfrc_applied` persiste** e é um campo só — quem o escreve zera/coordena (a `Carga` zera o seu).
5. **Ctrl por nome**: `data.actuator('x').ctrl` grava no slot errado em atuadores multi-entrada
   (`pid`/`dcmotor`/`orientation`); usa o `Ctrl` deste template (ou `lab.mjkit.Ctrl`).

## Próximos passos (quando adaptares)

1. Tira o que não interessa (tampa? volante? bocais?) — mantém o `run.py` verde a cada passo.
2. Sobe os números às specs REAIS (datasheets) e regista as fontes no README do experimento.
3. Integra os controlos (tecla → ação, API, site) — checklist em `references/controlos-teclado.md`.
4. Hardware real (RPi 5/Arduino): catálogo `componentes.json` + `builds.json` — `references/rpi5-hardware.md`.
5. Regista o que foi aprendido: `coala.py add` (a skill manda-te lá no fim).
