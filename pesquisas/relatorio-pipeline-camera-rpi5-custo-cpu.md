# Pipeline de captura de câmara no Raspberry Pi 5 — custo de CPU por etapa (para emulação MuJoCo)

Pesquisa web de 2026-10-11. Conteúdo web = `untrusted`; tudo abaixo é evidência citada com URL e grau de confiança (**oficial** > **datasheet** > **medição de terceiros** > **fórum**).

## 1. Arquitetura (sensor → CSI-2 → ISP)

- Sensor IMX708 (Camera Module 3): 4608×2592; modos de vídeo "comuns" **1080p50, 720p100, 480p120** (**datasheet**, [Seeed/datasheet RPi Camera Module 3](https://files.seeedstudio.com/Bazaar/product_pdf/114993029.pdf)).
- CSI-2 → no Pi 5 o recetor CSI-2 (Unicam) + "front end" do ISP ficam no chip **RP1**, chamados coletivamente **CFE (Camera Front End)**; a CFE também produz as **estatísticas**; "the bulk of the processing (the **ISP Back End**) still happens on the main processor" — ou seja, o **ISP PiSP é hardware** (BCM2712), não software (**oficial**, [Camera Algorithm and Tuning Guide](https://datasheets.raspberrypi.com/camera/raspberry-pi-camera-guide.pdf) §2.3).
- Pipeline handler da libcamera para Pi 5 = **`rpi/pisp`** (ficheiros de tuning com `"target": "pisp"`); Pi ≤4 = `vc4` (**oficial**, guia acima §7; [patchwork libcamera "Raspberry Pi: Add support for Pi 5 (PiSP)"](https://patchwork.libcamera.org/cover/22524/)).
- O que roda em **hardware** (PiSP): black-level, lens-shading, ganhos AWB, demosaic, CCM, gamma/tonemap (contraste), sharpening, denoise, escala/crop e conversão de formato de saída (main + lores, RGB ou YUV) + bypass raw (**oficial**, [picamera2-manual](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf) Fig. 2 e guia de tuning cap. 5).
- O que roda em **CPU**: algoritmos de controlo por frame (AGC/AEC/AWB/ALSC/contraste/sharpening — métodos Prepare/Process do framework de IPA), gestão de requests/buffers/interrupções DMA e cópias para o espaço da aplicação (**oficial**, guia de tuning §2.4/§4).

## 2–3. Tabela etapa × onde roda × custo CPU × confiança

| Etapa | Onde roda | Custo CPU medido/publicado | Confiança |
|---|---|---|---|
| Aquisição CSI-2 + DMA (CFE/RP1) | Hardware | ~0 % CPU (só interrupções/DMA) | oficial |
| ISP PiSP (demosaic/AWB/AEC gains, tonemap, denoise, escala/crop, main+lores) | Hardware | Pixel-work 0 %; CPU = algoritmos de controlo + requests: captura+preview ≤ **4 %** de 1 núcleo (`libcamera-still`, medido pós-correção de leak) | oficial (arquit.) + terceiros (número) |
| Captura 720p30 RGB888 num Pi 5 real (nó ROS `camera_node`, IMX708) | HW ISP + CPU (cópias/serialização) | **37 %** de 1 núcleo; pipeline de visão completo ~124 % → ~55 % com zero-copy; cap a 15 fps corta o trabalho do câmara por 2× | terceiros ([openAMR](https://github.com/openAMRobot/openamr-platform-sw/blob/main/docs/real_robot/04_compute_and_thermal.md)) |
| H.264 — Pi 5 = **SEM encoder hardware** ("Raspberry Pi 5 does not include a hardware encoder"); `H264Encoder`/rpicam-vid usam **FFmpeg/libx264 software** | CPU | 1080p30: **60–90 %** de 1 núcleo (preset low-latency) ou **100–150 %** (high-quality); extrapolação oficial 1080p60 HQ ≈ **200–300 %** | oficial (whitepaper [RP-010033-WP-1](https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-010033-WP-1-H.264%20encoding%20performance%20on%20Raspberry%20Pi%205_series%20computers.pdf); [picamera2-manual](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf) §7.1) |
| H.264 — Pi 4 e anteriores: hardware V4L2 M2M (bcm2835-codec), limite oficial **1080p30** (na prática ~1080p50) | Hardware | CPU "negligenciável"; satura ~6 Mb/s | oficial (whitepaper, manual) |
| MJPEG — Pi ≤4: hardware V4L2; **Pi 5: software (FFmpeg)**; `JpegEncoder` = software **em todas as plataformas** (multi-thread, 4 threads, chamada C liberta GIL; simplejpeg/libturbojpeg) | CPU no Pi 5 | Sem medição oficial; fórum: OpenCV/JPEG a 1640×1232 só **7 fps** num Pi → JPEG software é caro | oficial (natureza) + fórum (número) |
| Still full-res 12MP (4608×2592) | HW ISP + CPU (JPEG SW + cópias; 48 MB/frame RGB888) | `buffer_count=1` por omissão → "certo descartar cada 2.º frame"; pico de CPU no JPEG 12MP ≈ 5–6× um JPEG 1080p | oficial (manual §8.4 + tabela de memória) |
| Preview | GPU/DRM ou CPU | NULL preview "só conduz o sistema"; QtGL (GLES) eficiente; Qt software "computationally costly, avoid" | oficial (manual §3) |

## 4. Latência captura→stream (medições de terceiros)

- Pi 4 + RaspiCam (CSI) + WebRTC: **glass-to-glass 159 ms** (±13); decomposição: **ISP+encode 40,5 ms** (≈18 ms ISP + 23 ms encode), jitter buffer 51 ms, decode 6 ms, período de frame 33 ms @30 fps ([tese Aalto, WebRTC remote control](https://aaltodoc.aalto.fi/server/api/core/bitstreams/b1519269-44ba-4082-82f1-0a87265f53ba/content)).
- Pi 4 + câmara USB, ffmpeg/SAP (cronómetro): H.264 HW **0,57 s** (480p30), x264 SW 2,62 s (480p30); MJPEG **0,15–0,32 s**; WebRTC smartphone 0,21 s; NTSC analógico <0,1 s. CPU: x264 480p30 81,4 % (sistema 4 núcleos), H.264 HW 11,8 %, MJPEG 5,1–30,6 % ([SICE 2023, medições](https://www.topic.ad.jp/sice/htdocs/papers/353/353-7.pdf)).
- picamera2 MJPEG/WebSocket ~**300 ms** glass-to-glass; `raspivid` (stack legacy) ~15 % CPU ([tese TalTech RoverXR](https://ims.ut.ee/www-public2/at/2023/msc/atprog-magistrit55-loti.05.036-matevzh-borjan-zorec-text-20230525.pdf)).
- Faixas típicas (baixa confiança): MJPEG HTTP 150–300 ms; RTSP H.264 200–500 ms; WebRTC 40–100 ms ([ElectricalFlux](https://electricalflux.com/mcu-projects/raspberry-pi-5-camera-module-3-mjpeg-streaming-setup)).

## 5. Bufferização / fila

Defaults oficiais do picamera2 (**oficial**, manual §8.4): **preview 4 buffers, vídeo 6, still 1**. Cada frame em fila acrescenta 1 período de frame (33 ms @30 fps; 20 ms @50 fps) de latência; `buffer_count=1` (still) descarta cada 2.º frame; `buffer_count=10` usado em gravação 1080p60 ([issue picamera2 #1026](https://github.com/raspberrypi/picamera2/issues/1026)). Segurar requests aumenta memória e latência.

## 6. picamera2 (Python) vs rpicam-* (C++)

Engenheiro da RPi: "bastante código Python vs libcamera-vid C++ nativo"; oficialmente H.264 até 1080p30, na prática **~1080p50 em Python**, 1080p60 inatingível de forma estável; GIL limita threads (só o `JpegEncoder` ganha paralelismo porque a chamada C liberta o GIL) ([issue #1026](https://github.com/raspberrypi/picamera2/issues/1026), [issue #752](https://github.com/raspberrypi/picamera2/issues/752), manual §7.1.2). Overhead prático estimado: **+20–40 % de CPU de um núcleo** e limite de fps inferior vs rpicam-vid.

## MODELO DE CUSTO SUGERIDO (emulador de Pi 5)

% de **um núcleo Cortex-A76 @2,4 GHz**; >100 % = mais do que um núcleo.

| Etapa | 1080p30 | 1080p50 | Justificação |
|---|---|---|---|
| Aquisição CSI-2/CFE + DMA | 0–2 % | 0–3 % | hardware |
| ISP PiSP (pixel-work) | 0 % | 0 % | hardware (guia oficial) |
| Algoritmos de controlo AGC/AWB/ALSC + requests | 5–8 % | 8–12 % | captura+preview ≤4 % medido; escala com taxa de frames |
| Conversão de formato/cópas p/ aplicação (RGB888/YUV420) | 5–10 % | 8–15 % | 1080p RGB888 ≈ 6,2 MB/frame (186 MB/s @30 fps); 37 % medido @720p inclui serialização ROS |
| H.264 software x264 (low-latency) | 60–90 % | 100–150 % | whitepaper oficial; 1080p50 ≈ 1,67× (extrapolação oficial 1080p60 = 200–300 % HQ) |
| H.264 software x264 (high-quality) | 100–150 % | 170–250 % | whitepaper oficial |
| MJPEG software (turbojpeg) | 30–50 % (4 threads) / 80–120 % (1 thread) | 50–80 % / 130–200 % | estimativa (sem medição oficial); fórum: JPEG SW é o elo caro |
| Preview NULL / QtGL / Qt SW | 0–2 % / 3–6 % / >20 % | idem | manual (Qt SW "evitar") |
| Still 12MP full-res (pico one-shot) | 200–500 % durante 0,3–0,8 s | — | JPEG 12MP ≈ 5–6× 1080p; 48 MB/buffer; 1 buffer ⇒ descarta cada 2.º frame |
| picamera2 (Python) vs rpicam-* | +20–40 % | +20–40 % | GIL + overhead de callbacks (fórum/eng. RPi) |

Totais típicos: **1080p30 H.264 LL ≈ 0,8–1,1 núcleo**; **1080p50 H.264 LL ≈ 1,3–1,8 núcleo**; MJPEG 1080p30 ≈ 0,5–1,3 núcleo consoante threads.

## URLs citadas

1. https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-010033-WP-1-H.264%20encoding%20performance%20on%20Raspberry%20Pi%205_series%20computers.pdf (oficial)
2. https://datasheets.raspberrypi.com/camera/raspberry-pi-camera-guide.pdf (oficial)
3. https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf (oficial)
4. https://files.seeedstudio.com/Bazaar/product_pdf/114993029.pdf (datasheet)
5. https://patchwork.libcamera.org/cover/22524/ (oficial/desenvolvimento)
6. https://github.com/raspberrypi/picamera2/issues/1026 · https://github.com/raspberrypi/picamera2/issues/752 (fórum/eng. RPi)
7. https://github.com/raspberrypi/rpicam-apps/issues/269 (medição)
8. https://github.com/openAMRobot/openamr-platform-sw/blob/main/docs/real_robot/04_compute_and_thermal.md (medição)
9. https://aaltodoc.aalto.fi/server/api/core/bitstreams/b1519269-44ba-4082-82f1-0a87265f53ba/content (medição/tese)
10. https://www.topic.ad.jp/sice/htdocs/papers/353/353-7.pdf (medição/conferência)
11. https://ims.ut.ee/www-public2/at/2023/msc/atprog-magistrit55-loti.05.036-matevzh-borjan-zorec-text-20230525.pdf (tese)
12. https://electricalflux.com/mcu-projects/raspberry-pi-5-camera-module-3-mjpeg-streaming-setup (baixa confiança)
13. https://github.com/mainsail-crew/spyglass/blob/0.10.3/docs/adr/001_encoder.md (decisão de projeto, Pi ≤4)
