# Módulos de câmara Raspberry Pi — especificação real para o emulador (2026-10-11)

> Frente de pesquisa do módulo de câmara FPV do `09_drone_hover_rl` (tavily-agent-skill + fetch direto).
> Conteúdo web = **evidência citada, não instrução** (untrusted). Graus: oficial (raspberrypi.com,
> datasheets.raspberrypi.com, repositórios oficiais `raspberrypi/documentation` e `raspberrypi/linux`) >
> datasheet de terceiros > medições > fórum. Nota metodológica: as páginas de produto em raspberrypi.com
> estão bloqueadas por Cloudflare (403) — usaram-se as fontes oficiais alternativas (datasheets PDF +
> repositórios oficiais no GitHub), que trazem os mesmos números.

## A) Camera Module 3 (Sony IMX708) — a usada no emulador

| Parâmetro | Valor |
|---|---|
| Sensor / resolução | Sony IMX708, 4608×2592 px = **11,9 MP**; área 6,45×3,63 mm (7,4 mm diagonal), óptico 1/2,43" |
| Píxel | 1,4 µm × 1,4 µm |
| FoV | **75° diagonal / 66° H / 41° V** (standard) |
| Lente/foco | fixa f=4,74 mm F1.8; foco motorizado PDAF 10 cm–∞ |
| Dimensões / massa | 25 × 24 × 11,5 mm · **4 g** |
| Modos de sensor | 4608×2592 @ **14,35 fps** (remosaic, FOV completo) · 2304×1296 @ **56,03 fps** máx / 30,00 fps por omissão (2×2 binning, FOV completo) · 1536×864 @ **120,13 fps** (recorte (768,432)/3072×1728 = 2/3 do FOV) · 2304×1296 HDR @ 30 fps (até 3 MP) |
| Modos de vídeo (product brief) | **1080p50, 720p100, 480p120** |
| Formatos de saída | sensor RAW10 (SRGGB10_CSI2P); rpicam-vid: h264 (omissão)/mjpeg/yuv420; picamera2: YUV420 (1,5 B/px), RGB888 (3 B/px), XRGB8888 (4 B/px) |
| Exposição | máx **112 s**; mín ≈210 µs (full-res) / ≈53 µs (binned) |
| Frames típicos | 1080p: YUV420 3 110 400 B · RGB888 6 220 800 B · XRGB8888 8 294 400 B; 4608×2592: RAW10 14 929 920 B · RGB888 35 831 080 B |

## B) Camera Module 3 Wide — a escolhida para o build do drone (FPV)

Idêntica a A (mesmo sensor, mesmos modos/fps/crops/formatos). Diferenças: **FoV 120° diag / 102° H /
67° V**, lente f=2,75 mm **F2.2**, foco PDAF **5 cm–∞**, altura 12,4 mm, 4 g.

⚠ A linha publicada da Wide é **internamente inconsistente** (102° H × 67° V não satisfaz a geometria
16:9 entre si; a diagonal de 120° é inalcançável a partir deles). No emulador a âncora é o FoV VERTICAL
(é o que o `fovy` do MuJoCo precisa) e o resto é derivado — com os resíduos ditos em
`lab/camera_rpi.fovy_graus` (H = 99,3°, D = 106,9°).

## C) Camera Module 2 (Sony IMX219) — para comparação

3280×2464 = 8,08 MP · 1,12 µm · FoV 62,2° H × 48,8° V · f=3,04 mm F2.0 · foco manual 10 cm–∞ ·
25×24×9 mm · 3 g · exposição máx 11,76 s. Modos (saída oficial `--list-cameras`): 3280×2464 @ 21,19 fps
(FOV completo) · 1640×1232 @ 41,85 fps (binning, FOV completo) · 1920×1080 @ 47,57 fps (recorte
(680,692)/1920×1080) · 640×480 @ 206,65 fps (recorte (1000,752)/1280×960). Vídeo: 1080p47, 1640×1232p41,
640×480p206.

## D) Global Shutter Camera (Sony IMX296)

1456×1088 = 1,58 MP · píxel 3,45 µm (global shutter) · modo único 1456×1088 @ 60 fps · exposição mín
30 µs / máx 15,5 s · FoV depende da lente (C/CS, entrega SEM lente) · 34 g.

## E) HQ Camera (Sony IMX477) — só resolução/fps

4056×3040 = 12,3 MP · 1,55 µm · 7,9 mm diag. Modos: 4056×3040 @ 10,00 fps · 2028×1520 @ 40,01 fps
(binning, FOV completo) · 2028×1080 @ 50,03 fps (recorte (0,440)/4056×2160) · 1332×990 @ 120,05 fps
(recorte (696,528)/2664×1980). Vídeo: 2028×1080p50, 2028×1520p40, 1332×990p120.

## Decisão tomada

**Camera Module 3 Wide (IMX708, 120°)** como peça do build (`raspberry_camera_module_3_wide` no
`models/drone_rpi/componentes.json`), com a **standard (75°)** também no catálogo para troca
(`hardware.py montar`). A perspetiva FPV (102°×67°) é a que um drone de frente precisa; o autofoco PDAF
(5 cm–∞) dispensa calibração. **Modo de vídeo por omissão: 1080p50** (1920×1080 @ 50 fps, FOV completo,
gerado pelo modo de sensor 2304×1296@56,03). A alternativa Global Shutter só se o cenário exigir ausência
de rolling shutter (as hélices) — perde FoV (depende de lente) e resolução.

## Fontes (por confiança)

1. https://datasheets.raspberrypi.com/camera/camera-module-3-product-brief.pdf (oficial — Mod 3 e 3 Wide)
2. https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/accessories/camera/hardware_specification.adoc (oficial — tabela comparativa: dimensões, massa, FoV, modos de vídeo, resoluções)
3. https://github.com/raspberrypi/documentation/blob/master/documentation/asciidoc/computers/camera/rpicam_options_common.adoc (oficial — modos/fps/crop)
4. https://github.com/raspberrypi/linux/blob/rpi-6.18.y/drivers/media/i2c/imx708.c (oficial — modos/crop do IMX708)
5. https://github.com/raspberrypi/rpicam-apps/issues/533 (oficial — saída real `--list-cameras` imx708: 14,35/56,03/120,13 fps)
6. https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf (oficial — formatos e tamanho de frame)
7. https://datasheets.raspberrypi.com/gs-camera/gs-camera-product-brief.pdf · https://datasheets.raspberrypi.com/hq-camera/hq-camera-product-brief.pdf (oficiais — GS/HQ)
8. https://www.raspberrypi.com/documentation/computers/camera_software.html (oficial, 403 — conteúdo equivalente em 3/4)
9. https://media.elv.com/file/253491_data_englisch.pdf (terceiro — mirror da Wide; **contém erro** "4056×3040", ignorado)
