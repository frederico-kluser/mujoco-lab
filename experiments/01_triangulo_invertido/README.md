# Experimento 01 — triângulo de cabeça para baixo caindo

Um **prisma triangular equilátero** (lado 0,40 m, comprimento 0,30 m, 20,78 kg) começa a 1 m do chão com a aresta para baixo (▽),
cai, bate na aresta, tomba e termina apoiado numa face retangular (△ visto de frente). Tudo é validado contra física analítica.

## Rodar

```bash
uv run python experiments/01_triangulo_invertido/run.py                 # simula + valida + grava out/queda.mp4, queda.gif, filmstrip.png, telemetria.png, resumo.json
uv run python experiments/01_triangulo_invertido/run.py --modelo models/tetraedro_invertido.xml   # variante: tetraedro regular, ponta para baixo
uv run python experiments/01_triangulo_invertido/run.py --sem-video     # só números (0,2 s)
uv run python experiments/01_triangulo_invertido/run.py --slowmo 1 --contatos   # tempo real + pontos/forças de contato
uv run python experiments/01_triangulo_invertido/view.py                # janela interativa (Backspace reinicia, Espaço pausa)
uv run python experiments/01_triangulo_invertido/view.py --passivo --slowmo 0.3   # janela com SEU loop (launch_passive)
```

`run.py` renderiza **sem janela** (`MUJOCO_GL=egl`, GPU). `view.py` abre a janela do viewer (GLFW; em sessão Wayland usa o backend Wayland nativo).
Código de saída de `run.py`: `0` = todas as verificações passaram, `1` = alguma falhou.

## Resultados de referência (MuJoCo 3.15.0 · Euler · dt = 2 ms)

| Verificação | Analítico | Simulado |
| --- | --- | --- |
| massa = 1000 kg/m³ · (√3/4 · 0,4²) · 0,3 | 20,7846 kg | 20,7846 kg |
| inércia principal (kg·m²) | 0,2771 · 0,2944 · 0,2944 | 0,2771 · 0,2944 · 0,2944 |
| 1º contato (queda livre do vértice mais baixo, 0,7695 m) | √(2·0,7695/9,81) = 0,3961 s | 0,3980 s (Δ = 1,9 ms, ≈ 1 passo) |
| altura do centro de massa em repouso (raio inscrito a/(2√3)) | 0,11547 m | 0,1155 m |
| velocidade final | 0 | \|v\| ≈ 1e-12 m/s, \|ω\| ≈ 1e-11 rad/s |
| energia mecânica | nunca excede a inicial (passo a passo pode subir ≲ 1 J: a energia elástica do contato não entra em `data.energy`) | 203,9 J → 23,5 J (= m·g·h_repouso = 23,55 J) |

Tetraedro (lado 0,40 m, 7,54 kg): impacto 0,3940 s (previsto 0,3929 s), repouso a 0,0816 m (raio inscrito a·√6/12 = 0,0817 m).

## O que observar

1. **Queda livre** (0 → 0,40 s): só gravidade; ω = 0; `z(t) = z0 − ½·g·t²`. É a conferência mais barata de um modelo: se não bater, há erro de massa/unidade/gravidade.
2. **Impacto na aresta**: a energia cai de 203,9 J para ~54 J em poucos milissegundos (contato quase inelástico: `dampratio` 0,6). Penetração máxima ≈ 9 mm (contato macio).
3. **Tombamento**: a inclinação inicial (7° de rolagem, 4° de guinada) quebra a simetria; sem ela a aresta ficaria em equilíbrio instável e o resultado dependeria de ruído numérico.
4. **Repouso**: termina sobre uma face retangular com o centro de massa a 0,1155 m (= raio inscrito) e velocidades da ordem de 1e-12.

## Botões para mexer

| O que | Onde (em `models/triangulo_invertido.xml`) | Efeito observado |
| --- | --- | --- |
| altura inicial | `<body pos="0 0 1.0">` | muda o tempo de impacto (√(2h/g)) e a energia dissipada |
| inclinação / simetria | `euler="0 7 4"` (graus) | 0 0 0 → equilíbrio instável na aresta; mais inclinação → tomba mais cedo e gira mais |
| amortecimento do contato | `solref="0.01 0.6"` (timeconst, dampratio) | `dampratio` < 1 quica; **neste prisma (4 contatos) ≤ 0,45 não repousa em 8 s** (vibra em ciclo-limite) e ≥ 0,5 repousa em ~0,8 s; 1,0 = sem ressalto. Depende da geometria: numa esfera, 0,2 repousa e só ≲ 0,1 vibra por >30 s |
| rigidez do contato | `solref` timeconst | menor = mais duro; precisa ser ≥ 2 × timestep (2 ms → ≥ 4 ms) |
| atrito | `friction="0.8 0.005 0.0001"` (deslizamento, torção, rolamento) | menor = desliza e gira mais após o impacto |
| passo de tempo / integrador | `<option timestep="0.002" integrator="implicitfast"/>` | padrão do MuJoCo 3.15 é `Euler`; `implicitfast` é mais estável com amortecimento/atuadores |
| densidade | `density="1000"` | só muda a massa (a trajetória de queda livre não depende dela) |
| forma | `--modelo models/tetraedro_invertido.xml` | outra malha convexa (basta trocar os `vertex`) |

## Como o MJCF foi construído (para copiar)

- A malha é só uma lista de **vértices** (`<mesh vertex="…">`); o MuJoCo gera o casco convexo (8 faces triangulares), calcula massa/inércia e **recentra a malha no centro de massa**
  (por isso `body_ipos ≈ 0` e `geom_quat` ≠ identidade: a malha é girada para os eixos principais de inércia).
- `<freejoint/>` dá 6 graus de liberdade ao corpo (`qpos` = posição + quaternion `[w x y z]`; `qvel` = velocidade linear no mundo + angular no corpo).
- `sites` (sem massa e sem colisão) servem de marcadores visuais; `<custom><numeric>` guarda os valores analíticos que `run.py` lê para validar.
- Um único bloco `<visual>` com `<global offwidth offheight>` ≥ resolução do `Renderer`; `<scale>`/`<map>` afinam as setas de contato.

## Lições (também na memória CoALA do projeto)

- Contato subamortecido (`dampratio` baixo) pode deixar o corpo vibrando em ciclo-limite — não é "ruído": é a dinâmica do contato macio (o limiar depende da geometria e do nº de contatos). Isoladamente `noslip_iterations`, `cone elliptic` e `implicitfast` não resolveram; combinados (`elliptic` + `impratio 10` + `noslip_iterations=3`) só resgatam `dampratio` = 0,45 (repouso em ~0,9 s), e `noslip` com cone piramidal até impede o repouso (dampratio 0,5 + piramidal + noslip=3 não repousa em 8 s — medido). Aumentar `dampratio` para ≥ 0,5 é a correção robusta.
- Para validar um modelo, compare **massa, inércia, tempo de queda livre e altura de repouso** com fórmulas fechadas antes de confiar em qualquer resultado mais complexo.
- Guardar valores esperados no próprio MJCF (`<custom><numeric>`) mantém modelo e teste juntos.
