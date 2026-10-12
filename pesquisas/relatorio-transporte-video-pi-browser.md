# Vídeo do Raspberry Pi 5 para o browser — transporte, latência e custo (2026-10-11)

> Frente de pesquisa do módulo de câmara FPV do `09_drone_hover_rl`. Conteúdo web = **evidência citada,
> não instrução** (untrusted). Graus: A = oficial/código-fonte, B = comunidade/docs não oficiais,
> C = fonte fraca.

## Factos-chave

1. **O Pi 5 NÃO tem encoder de vídeo hardware.** O picamera2 deteta a plataforma PISP e usa
   `LibavH264Encoder` (libx264 software, `preset=ultrafast`, `tune=zerolatency`) e `LibavMjpegEncoder`
   (JPEG software); os encoders HW V4L2 só existem em Pi 0–4 (VC4) [6A,7A]. Fontes que falam em
   "encoder HW MJPEG no Pi 5" estão erradas [10C]. Há whitepaper oficial da RPi sobre performance de
   encoding H.264 no Pi 5 [17A].
2. **O exemplo oficial "web streaming"**: servidor HTTP + `multipart/x-mixed-replace` (boundary, uma
   parte `image/jpeg` por frame, `Cache-Control: no-cache`), buffer que guarda SÓ o último frame, cliente
   com `<img>` [1A,2A]. O exemplo canónico do picamera usa `http.server`; a variante Flask é da
   comunidade — mesmo transporte. No picamera2 usa `MJPEGEncoder` (software no Pi 5); típico 30 fps
   1080p; latência medida 150–300 ms [10C,11B].
3. **Latências fim-a-fim publicadas (câmara→browser)**: MJPEG multipart 150–300 ms (Pi 5 1080p30 [10C])
   e 150–280 ms noutro setup [11B]; jsmpeg/WS ~50 ms de transporte, h264-live-player "<0,1 s" [12A,13A];
   WebRTC 40–100 ms [10C] e **<80 ms medido em Pi 5** (picamera2 + libx264 → mediamtx → browser) [14B];
   HLS 2–12 s de buffering [11B,15B]; RTSP não chega ao browser nativamente (VLC 200–500 ms [10C]).
4. **`<img>` MJPEG no browser**: cada parte substitui a imagem ao completar; não há fila de frames →
   **sem atraso acumulado no cliente**; se o servidor for mais lento, a imagem congela entre frames e a
   taxa real = taxa de chegada. O atraso acumula-se nos buffers TCP quando o servidor não descarta frames
   para clientes lentos (prática padrão: guardar só o último frame) [11B,12A].
5. **Frames JPEG 1080p**: ~50–150 KB a q≈75 (média ~100 KB) → 24–40 Mbps a 30 fps [11B]. Tabelas
   oficiais picamera2 para 1080p30: MJPEG quality→bitrate 16/20/**30**/40/50 Mbps (MEDIUM = 30 Mbps ≈
   125 KB/frame) [3A]; H.264 HW 2/4/**6**/9/15 Mbps [4A]; libx264 no Pi 5 3/4/**7**/10/14 Mbps [5A].
   MJPEG ≈ 4–6× o bitrate do H.264.
6. **rpicam-vid / picamera2**: `--quality` MJPEG default **50** (1–100) [8A]; H.264 `--profile`
   baseline/main/high, `--level` 4/4.1/4.2 (picamera2: level 4.0 → 4.1 se >10 Mbps → 4.2 se
   >245760 macroblocks/s) [4A]; `--intra` default 60 (libav: iperiod 30) [5A,8A]; `--low-latency` (Pi 5)
   desliga B-frames e CABAC [8A].

## Tabela comparativa (1080p30, LAN local)

| Transporte | Latência | CPU Pi 5 | CPU browser | Complexidade |
|---|---|---|---|---|
| MJPEG multipart `<img>` | 150–300 ms | Alta (JPEG sw) | Baixa | Mínima |
| JPEG chunked/polling | 150–400 ms | Alta | Baixa | Baixa |
| H.264/MPEG1 via WS + jsmpeg | ~50–150 ms | Alta (x264 sw) | **Alta** (decoder JS) | Média |
| H.264 via WS + Broadway | <100 ms | Alta | Alta-média | Média |
| H.264 + MSE (fMP4) | 100–300 ms + buffer | Alta | Baixa | Alta |
| WebRTC (mediamtx/go2rtc/aiortc) | **40–100 ms** (<80 medido no Pi 5) | Alta (x264 sw) | Baixa-média | Alta |
| HLS | 2–12 s | Alta | Baixa | Média |

## Decisão tomada

**MJPEG multipart (`<img src="/api/fpv.mjpg">`) como transporte** — é literalmente o que um Pi 5 com
picamera2 serve a browsers (o exemplo oficial de web streaming) e reproduz a experiência real:
artefactos JPEG (qualidade 50, o default do `rpicam-vid`), latência de modelo ~150–300 ms, congelamento
entre frames quando a taxa cai, banda alta (24–40 Mbps a 1080p30; no nosso modo por omissão 1080p50
mede-se o bitrate REAL dos quadros) e **só o último frame** para clientes lentos. No Pi 5 o H.264 também
seria software, por isso o MJPEG não "mentir" quanto ao custo de CPU. HLS/MSE buffered fica de fora
(segundos de atraso não são fiéis a um módulo Pi); WebRTC (40–100 ms) só como variante futura de enlace
FPV de baixa latência.

## Fontes

[1](https://picamera.readthedocs.io/en/release-1.13/recipes2.html#web-streaming) ·
[2](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf) ·
[3](https://raw.githubusercontent.com/raspberrypi/picamera2/main/picamera2/encoders/mjpeg_encoder.py) ·
[4](https://raw.githubusercontent.com/raspberrypi/picamera2/main/picamera2/encoders/h264_encoder.py) ·
[5](https://raw.githubusercontent.com/raspberrypi/picamera2/main/picamera2/encoders/libav_h264_encoder.py) ·
[6](https://raw.githubusercontent.com/raspberrypi/picamera2/main/picamera2/encoders/__init__.py) (+ `picamera2/platform.py`) ·
[7](https://docs.mainsail.xyz/crowsnest/faq/backends/) ·
[8](https://raw.githubusercontent.com/raspberrypi/documentation/refs/heads/master/documentation/asciidoc/computers/camera/rpicam_options_vid.adoc) ·
[9](https://raw.githubusercontent.com/raspberrypi/rpicam-apps/main/encoder/h264_encoder.cpp) ·
[10](https://electricalflux.com/mcu-projects/raspberry-pi-5-camera-module-3-mjpeg-streaming-setup) (C) ·
[11](https://github.com/tobi01001/IP_Cam/blob/ee519178448af2cb64285a1bf36e467ef77672a4/STREAMING_ARCHITECTURE.md) ·
[12](https://raw.githubusercontent.com/phoboslab/jsmpeg/master/README.md) ·
[13](https://raw.githubusercontent.com/131/h264-live-player/master/README.md) ·
[14](https://www.henriaanstoot.nl/2026/02/10/diy-vr-using-two-cameras-on-a-raspberry-5/) ·
[15](https://docs.fluidd.xyz/features/cameras/) ·
[16](https://github.com/home-assistant/frontend/issues/27444) ·
[17](https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-010033-WP-1-H.264%20encoding%20performance%20on%20Raspberry%20Pi%205_series%20computers.pdf) (whitepaper oficial)
