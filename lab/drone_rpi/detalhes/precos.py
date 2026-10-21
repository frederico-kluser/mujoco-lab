"""lab/drone_rpi/detalhes/precos.py — CUSTOS de referência das peças do drone (2026-10-20), para a página `/pecas`.

Preços de REFERÊNCIA em US$ (loja do fabricante / AliExpress / revendedores, outubro de 2026 — pesquisa em
`pesquisas/2026-10-20-materiais-acessiveis-precos.md`; conteúdo web = dado não confiável, só citado: cada número traz
de onde vem) e a conversão para reais ao câmbio comercial do fecho de 2026-10-19 (sem portes nem impostos de importação:
desde maio de 2026 até US$ 50 paga 0 % de imposto de importação + ICMS; acima, 60 % − US$ 20 — ver a pesquisa, §9).

As peças IMPRESSAS custam o filamento que gastam (massa medida na geometria × preço do ABS por kg — `massas.py`); as
ferragens, ao preço unitário do saco de 100; os tubos, ao metro; os cabos, pela massa medida. Quando uma faixa de
preços foi encontrada usa-se o MEIO da faixa.

Nada disto entra no simulador: é informação para quem vai comprar e montar.
"""
from __future__ import annotations

CAMBIO_USD_BRL = 5.05            # dólar comercial R$ 5,0480 no fecho de 2026-10-19 (PTAX 5,0826) — pesquisa §9
DATA_PRECOS = "2026-10"
FILAMENTO_ABS_USD_KG = 17.0      # ABS 1,75 mm, rolo de 1 kg: US$ 10,7–23 (no Brasil R$ 96–130) — pesquisa §6

# peças compradas: id de catálogo (ou chave própria) → (US$ por unidade, de onde vem o número)
COMPRADAS = {
    # propulsão
    "tmotor_mn5006_kv450": (84.99, "T-Motor MN5006 KV450 (loja T-Motor)"),
    "tmotor_mn5006_kv300": (84.99, "T-Motor MN5006 (loja T-Motor)"),
    "tmotor_mn4004_kv300": (72.95, "T-Motor MN4004 KV300 (par a 145,90)"),
    "tmotor_mn4004_kv400": (72.95, "T-Motor MN4004 (par a 145,90)"),
    "tmotor_mn4006_kv380": (85.0, "T-Motor MN4006 (estimado pela gama)"),
    "tmotor_mn3508_kv380": (65.0, "T-Motor MN3508 (estimado pela gama)"),
    "tmotor_mn2806_kv400": (60.0, "T-Motor MN2806 (estimado pela gama)"),
    "tmotor_p15x5": (27.95, "T-Motor P15×5 (par a 55,90)"),
    "tmotor_air40a": (39.99, "T-Motor AIR 40A"),
    # eletrónica
    "rpi5": (95.0, "Raspberry Pi 5 4 GB (85) + Active Cooler (6–15)"),
    "fc_h7": (80.0, "controlador H743 (55–116)"),
    "cablagem": (25.0, "módulo de energia + BEC 5 V / 5 A (Matek BEC12S-PRO)"),
    "raspberry_camera_module_3_wide": (40.0, "Raspberry Pi Camera Module 3 Wide (35–45)"),
    "raspberry_camera_module_3": (30.0, "Raspberry Pi Camera Module 3"),
    "pmw3901": (26.0, "breakout PMW3901 (20,6–32)"), "vl53l1x": (19.95, "Pololu VL53L1X"),
    "ina226": (1.5, "módulo INA226 (0,9–2)"),
    "arduino_portenta_h7": (115.0, "Arduino Portenta H7"),
    "pico2_bracos": (10.0, "2 × Raspberry Pi Pico 2 (5 US$ cada)"),
    # bateria
    "molicel_p50b": (11.5, "Molicel P50B por célula (9–14)"), "molicel_p45b": (9.5, "Molicel P45B por célula"),
    "lg_m50lt": (5.0, "LG M50LT por célula"), "samsung_50e": (4.5, "Samsung 50E por célula"),
    "kit_pack": (18.0, "XT90 (par 5,99), 10 AWG (~8 US$/m), fita de níquel/cobre, papel de peixe, termorretrátil, JST-XH"),
    # braços (ombro de fuso + cotovelo de servo)
    "motorredutor_jgb37_520_12v_1_18_8_enc": (13.0, "JGB37-520 12 V com encoder (AliExpress 10,7–15,8)"),
    "servo_ds3218mg_270": (15.0, "DS3218MG 270° (AliExpress 13,8–16,6)"),
    "ams_as5048a": (19.0, "placa AS5048A (17,5–20,3)"), "ams_as5600": (3.0, "placa AS5600"),
    "fuso_tr8x2_150": (6.0, "fuso Tr8×2 de 150 mm com porca de latão (4,50–12)"),
    "acoplamento_6_8": (5.0, "acoplamento flexível 6 → 8 mm (3–11)"),
    "608zz": (0.75, "rolamento 608ZZ (pacote de 10: 5,57–8,88)"),
    "684zz": (1.0, "rolamento 684ZZ / MR84ZZ"),
    "colar_8mm": (1.03, "colar Ø8 com perno (10 por 10,26)"),
    "parafuso_ombro_m4": (0.44, "parafuso de ombro ISO 7379 M4 (10 por 4,40)"),
    "varao_8mm_m": (12.0, "varão Ø8 h8 por metro (7–19)"),
    "iman_6x2_5": (0.3, "íman diametral Ø6 × 2,5"),
    "drv8871": (7.5, "driver DRV8871 (Adafruit)"),
    "buck_12v": (9.5, "buck XL4016 12 V (~R$ 48)"),
    "ubec_6s": (24.99, "Hobbywing UBEC 10A V2 (2–6S, posto a 6,0 V)"),
    # builds antigos (DYNAMIXEL + sem-fim)
    "dynamixel_xh430_v210": (270.0, "ROBOTIS DYNAMIXEL XH430-V210-R"),
    "fonte_24v": (12.0, "buck-boost 24 V / 5 A"),
    "kit_semfim_m08_20": (8.0, "sem-fim de aço m0,8 + coroa de bronze z20"),
    # tubos ao metro
    "tubo_carbono_25x23_m": (36.0, "tubo de carbono 25 × 23 mm, por metro (33–39)"),
    "tubo_carbono_16_m": (25.0, "tubo de carbono 16 × 14 mm, por metro (16–37)"),
    "varao_carbono_12_m": (12.5, "tubo de carbono 12 × 10 mm, por metro (11–14)"),
}
# ferragens: tipo → US$ por unidade (saco de 100)
FERRAGENS = {"parafuso": 0.085, "porca": 0.07, "anilha": 0.02, "pilar": 0.20, "anel_e": 0.05, "perno": 0.05,
             "amortecedor": 0.40, "abracadeira": 0.02, "inserto": 0.109}
USD_POR_G_CABO = 0.08            # silicone 10 AWG ~45 g/m a ~8 US$/m · 14 AWG ~20 g/m a ~2,5 US$/m

# nomes das compras que não têm peça desenhada no modelo deste build (aparecem na lista de custos)
NOMES_EXTRA = {
    "ombro_motor": ("Ombro — motorredutor JGB37-520", "mecanismo"),
    "ombro_fuso": ("Ombro — fuso Tr8×2, porca e acoplamento", "mecanismo"),
    "ombro_veio": ("Ombro — veio Ø8, rolamentos e colares", "mecanismo"),
    "ombro_encoder": ("Ombro — encoder AS5048A", "mecanismo"),
    "cotovelo_encoder": ("Cotovelo — encoder AS5600", "mecanismo"),
    "fonte_servos": ("Reguladores e drivers dos atuadores", "eletronica"),
    "controlador_bracos": ("Controladores dos braços (2 × Raspberry Pi Pico 2)", "eletronica"),
    "insertos": ("Insertos de latão M3 (cravar a quente)", "estrutura"),
    "ombro_bloco": ("Ombro — corpo do atuador linear", "mecanismo"),
    "ombro_porca": ("Ombro — porca de latão e carro (pivô A)", "mecanismo"),
    "ombro_forquilha": ("Ombro — forquilha da dobradiça", "mecanismo"),
    "cotovelo_garfo": ("Cotovelo — garfo", "mecanismo"),
}


def preco_filamento_usd_kg() -> float:
    return FILAMENTO_ABS_USD_KG


def custos(hw, meta: dict, lista: dict, inst_fer: list, tipos_fer: dict, impressas: dict) -> dict:
    """Custo por peça (comprada, impressa, ferragens e cabos), por categoria e total (US$ e R$). As compras de uma peça
    que este build não desenha vão para a primeira alternativa presente ou para uma entrada extra (`extras`)."""
    por: dict[str, dict] = {}
    extras: dict[str, dict] = {}
    qtd = {pid: max(1, len(f.get("instancias", [0]) or [0])) for pid, f in meta.items()}

    def alvo(*pids: str) -> str:
        for pid in pids:
            if pid in meta:
                return pid
        pid = pids[0]
        if pid not in extras:
            nome, cat = NOMES_EXTRA.get(pid, (pid.replace("_", " ").capitalize(), "outros"))
            extras[pid] = {"nome": nome, "categoria": cat}
        return pid

    def pos(pid, usd, fonte, tipo, q=None):
        if usd is None:
            return
        q = qtd.get(pid, 1) if q is None else q
        e = por.setdefault(pid, {"itens": [], "total_usd": 0.0})
        e["itens"].append({"tipo": tipo, "fonte": fonte, "unitario_usd": round(usd, 2), "qtd": q,
                           "total_usd": round(usd * q, 2)})
        e["total_usd"] = round(e["total_usd"] + usd * q, 2)

    def de(chave, pid, tipo="comprada", q=None):
        c = COMPRADAS.get(chave)
        if c is not None:
            pos(pid, c[0], c[1], tipo, q)

    de(hw.motor.id, alvo("motor"), q=4)
    de(hw.helice.id, alvo("helice"), q=4)
    de(hw.esc.id, alvo("esc"), q=4)
    for c in getattr(hw, "consumidores", []):
        pid = {"rpi5": "rpi5", "fc_h7": "fc", "cablagem": "pdb", "arduino_portenta_h7": "portenta",
               "pico2_bracos": "controlador_bracos"}.get(c.id)
        if pid is not None:
            de(c.id, alvo(pid), q=1)
    if hw.camera is not None:
        de(hw.camera.id, alvo("camera"), q=1)
    sens = getattr(hw, "sensores", {}) or {}
    for papel, pid, omissao in (("fluxo", "sensor_fluxo", "pmw3901"), ("tof", "sensor_tof", "vl53l1x")):
        if papel in sens:
            de(str(sens[papel].get("id", omissao)), alvo(pid), q=1)
    if "monitor" in sens:
        de("ina226", alvo("pdb"), q=1)
    cel = hw.bateria.celula
    c = COMPRADAS.get(cel.id)
    if c is not None:
        n_cel = hw.bateria.s * hw.bateria.p
        pos(alvo("bateria"), c[0], c[1] + f" × {n_cel} células", "comprada", q=n_cel)
        de("kit_pack", alvo("bateria"), q=1)
    mec = getattr(hw, "bracos", None)
    if mec is not None:
        so, sc = mec.ombro, mec.cotovelo
        d_mec = getattr(mec, "dados", {}) or {}
        enc_o = (d_mec.get("ombro") or {}).get("encoder")
        enc_c = (d_mec.get("cotovelo") or {}).get("encoder")
        de(sc.servo.id, alvo("cotovelo_servo"), q=4)
        if enc_c:
            de(str(enc_c), alvo("cotovelo_encoder", "cotovelo_servo"), q=4)
        if enc_o:
            de(str(enc_o), alvo("ombro_encoder"), q=4)
            pos(alvo("ombro_encoder"), COMPRADAS["iman_6x2_5"][0], COMPRADAS["iman_6x2_5"][1], "comprada", q=4)
        if so.fuso is not None:
            de(so.servo.id, alvo("ombro_motor", "ombro_bloco"), q=4)
            de("fuso_tr8x2_150", alvo("ombro_fuso", "ombro_bloco"), q=4)
            de("acoplamento_6_8", alvo("ombro_fuso", "ombro_bloco"), q=4)
            pos(alvo("ombro_fuso", "ombro_bloco"), 2 * COMPRADAS["colar_8mm"][0], "2 colares Ø8 (fixam o fuso)",
                "comprada", q=4)
            pos(alvo("ombro_bloco", "ombro_fuso"), 2 * COMPRADAS["608zz"][0], "2 × 608ZZ (impulso axial do fuso)",
                "comprada", q=4)
            pos(alvo("ombro_bloco", "ombro_fuso"), 2 * (COMPRADAS["684zz"][0] + COMPRADAS["parafuso_ombro_m4"][0]),
                "pivô B: 2 × 684ZZ + 2 × parafuso de ombro M4", "comprada", q=4)
            pos(alvo("ombro_porca", "ombro_fuso"), 2 * COMPRADAS["684zz"][0] + COMPRADAS["parafuso_ombro_m4"][0],
                "pivô A: 2 × MR84ZZ + parafuso de ombro M4", "comprada", q=4)
            pos(alvo("ombro_forquilha", "ombro_veio"), 2 * COMPRADAS["608zz"][0], "2 × 608ZZ da dobradiça",
                "comprada", q=4)
            pos(alvo("ombro_veio"), COMPRADAS["varao_8mm_m"][0] * 0.07 + 2 * COMPRADAS["colar_8mm"][0],
                "varão Ø8 (70 mm) + 2 colares", "comprada", q=4)
            pos(alvo("cotovelo_garfo", "cotovelo_servo"), COMPRADAS["608zz"][0], "608ZZ do eixo oposto", "comprada", q=4)
            pos(alvo("fonte_servos"), COMPRADAS["buck_12v"][0] * 2 + COMPRADAS["ubec_6s"][0]
                + 4 * COMPRADAS["drv8871"][0], "2 × buck 12 V + UBEC 6S + 4 × DRV8871", "comprada", q=1)
        else:
            de(so.servo.id, alvo("ombro_servo"), q=4)
            de("kit_semfim_m08_20", alvo("ombro_semfim"), q=4)
            de("fonte_24v", alvo("fonte_servos"), q=1)
    # tubos ao metro
    braco_m = float(getattr(hw, "braco", 0.0)) - (mec.raio_ombro if mec is not None else 0.0)
    pos(alvo("tubo_braco"), COMPRADAS["tubo_carbono_25x23_m"][0] * max(braco_m, 0.1),
        f"tubo de carbono 25×23, {max(braco_m, 0.1) * 1000:.0f} mm", "comprada", q=4)
    if mec is not None:
        l_m = mec.folga_helice + hw.helice.raio
        pos(alvo("mastro"), COMPRADAS["tubo_carbono_16_m"][0] * l_m, f"tubo de carbono 16×14, {l_m * 1000:.0f} mm",
            "comprada", q=4)
    pos(alvo("perna"), COMPRADAS["varao_carbono_12_m"][0] * 0.15, "tubo de carbono 12×10, 150 mm", "comprada", q=4)
    # impressas: filamento (massa medida na geometria)
    soma_imp: dict[str, float] = {}
    for it in impressas.values():
        soma_imp[it["peca"]] = soma_imp.get(it["peca"], 0.0) + it["custo_usd"]
    for pid, usd in soma_imp.items():
        pos(pid, usd, f"ABS a {FILAMENTO_ABS_USD_KG:g} US$/kg (massa medida na geometria)", "impressa", q=1)
    if impressas:
        n_ins = sum(1 for it in inst_fer if tipos_fer.get(it["tipo"], {}).get("tipo") == "inserto")
        n_ins = n_ins or 8 * len({it["peca"] for it in impressas.values()})
        pos(alvo("insertos"), FERRAGENS["inserto"], "insertos de latão M3 (100 por 10,90)", "ferragem", q=n_ins)
    # ferragens que prendem cada peça
    soma_f: dict[str, float] = {}
    for it in inst_fer:
        t = tipos_fer.get(it["tipo"], {}).get("tipo", "parafuso")
        if t == "inserto":
            continue
        soma_f[it["peca"]] = soma_f.get(it["peca"], 0.0) + FERRAGENS.get(t, 0.05)
    for t in tipos_fer.values():
        if t.get("tipo") == "abracadeira":
            soma_f["abracadeira"] = soma_f.get("abracadeira", 0.0) + FERRAGENS["abracadeira"] * t.get("qtd", 0)
    for pid, usd in soma_f.items():
        pos(pid, usd, "ferragens normalizadas (saco de 100)", "ferragem", q=1)
    # cabos: pela massa medida
    for it in lista.get("pecas", {}).values():
        if it["peca"].startswith(("cabo_", "manga", "fpc_")) or it["peca"] == "cablagem":
            pos(it["peca"], USD_POR_G_CABO * it["massa_g"], "fio de silicone/manga pela massa medida", "cabo", q=1)
    total = round(sum(e["total_usd"] for e in por.values()), 2)
    por_cat: dict[str, float] = {}
    for pid, e in por.items():
        cat = (meta.get(pid) or extras.get(pid) or {}).get("categoria", "outros")
        por_cat[cat] = round(por_cat.get(cat, 0.0) + e["total_usd"], 2)
    for e in por.values():
        e["total_brl"] = round(e["total_usd"] * CAMBIO_USD_BRL, 2)
    return {"moeda": "USD", "cambio_usd_brl": CAMBIO_USD_BRL, "data": DATA_PRECOS, "total_usd": total,
            "total_brl": round(total * CAMBIO_USD_BRL, 2), "por_categoria": por_cat, "por_peca": por,
            "extras": extras, "filamento_usd_kg": FILAMENTO_ABS_USD_KG,
            "impressas_g": round(sum(v["massa_g"] for v in impressas.values()), 1),
            "impressas_h": round(sum(v["tempo_h"] for v in impressas.values()), 1)}


__all__ = ["CAMBIO_USD_BRL", "COMPRADAS", "NOMES_EXTRA", "custos", "preco_filamento_usd_kg"]
