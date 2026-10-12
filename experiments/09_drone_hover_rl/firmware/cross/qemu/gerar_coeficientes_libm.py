#!/usr/bin/env python3
"""Gera os COEFICIENTES da `libm_minima.cpp` (sinf, cosf, atan2f sem libm) — reprodutível: `python3 gerar_coeficientes_libm.py`.

Nada é copiado de nenhuma libm (glibc/newlib/musl/FreeBSD/Cephes): as formas são as da literatura — redução de argumento de Cody & Waite
(«Software Manual for the Elementary Functions», 1980: π/2 partido em 3 floats com poucos bits, para n·C exato) e aproximação POLINOMIAL por
interpolação de Chebyshev (quase minimax) de (sin√z − √z)/√z³, (cos√z − 1 + z/2)/z² e (atan√z − √z)/√z³ em z = r² (Trefethen, «Approximation
Theory and Approximation Practice», 2013). A função-alvo avalia-se em `numpy.longdouble` (80 bit), o sistema resolve-se em float64 e os coeficientes arredondam-se a float32.
"""
from __future__ import annotations

import sys
from decimal import Decimal, getcontext

import numpy as np

getcontext().prec = 60
PI = Decimal("3.14159265358979323846264338327950288419716939937510582097494")


def float32(x: Decimal) -> np.float32:
    return np.float32(float(x))


def parte_mantissa(x: Decimal, bits: int) -> np.float32:
    """`x` truncado a `bits` bits de mantissa (para que n·C seja exato em float32 para |n| pequeno)."""
    v = float(x)
    m, e = np.frexp(v)
    return np.float32(np.ldexp(np.floor(m * 2.0 ** bits) / 2.0 ** bits, e))


def cheb_nos(a: float, b: float, n: int) -> np.ndarray:
    k = np.arange(n)
    x = np.cos(np.pi * (k + 0.5) / n)[::-1]
    return 0.5 * (a + b) + 0.5 * (b - a) * x.astype(np.longdouble)


def ajusta(funcao, z_max: float, grau: int) -> np.ndarray:
    """Polinómio de grau `grau` em z ∈ [0, z_max] que interpola `funcao` nos nós de Chebyshev; devolve os coeficientes em float32 (c0..c_grau)."""
    z = np.array(cheb_nos(0.0, z_max, grau + 1), dtype=np.float64)
    y = np.array([funcao(np.longdouble(zz)) for zz in z], dtype=np.float64)
    # sistema de Vandermonde (quadrado, bem condicionado para grau ≤ 5) em float64: ≫ precisão que o float32 precisa
    return np.linalg.solve(np.vander(z, grau + 1, increasing=True), y)


def erro_max(funcao, c, z_max: float) -> float:
    z = np.linspace(0, z_max, 20001, dtype=np.longdouble)
    p = sum(np.longdouble(c[k]) * z ** k for k in range(len(c)))
    return float(np.max(np.abs(p - np.array([funcao(zz) for zz in z], dtype=np.longdouble))))


def main() -> int:
    ld = np.longdouble
    z_pi4 = float((np.longdouble(np.pi) / 4) ** 2)
    sin_f = lambda z: (np.sin(np.sqrt(z)) - np.sqrt(z)) / np.sqrt(z) ** 3 if z > 0 else -ld(1) / 6
    cos_f = lambda z: (np.cos(np.sqrt(z)) - 1 + z / 2) / z ** 2 if z > 0 else ld(1) / 24
    z_at = float(np.tan(np.longdouble(np.pi) / 8) ** 2)
    atan_f = lambda z: (np.arctan(np.sqrt(z)) - np.sqrt(z)) / np.sqrt(z) ** 3 if z > 0 else -ld(1) / 3
    saida = {}
    for nome, f, zmax, grau in (("sin", sin_f, z_pi4 * 1.02, 3), ("cos", cos_f, z_pi4 * 1.02, 3), ("atan", atan_f, z_at * 1.02, 5)):
        c = ajusta(f, zmax, grau)
        saida[nome] = [np.float32(v) for v in c]
        print(f"// {nome}: erro máximo da aproximação (longdouble, antes de arredondar) = {erro_max(f, c, zmax):.3e}")
    # Cody-Waite de π/2: C1 (10 bits), C2 e C3 (12 bits cada: n·C exato em float32 para |n| < 2^12) e C4 (o resto, 24 bits) — com
    # 3 partes o produto n·C3 já não era exato e o resto perto de um zero de sin/cos perdia até 6 ULP
    meio_pi = PI / 2
    c1 = parte_mantissa(meio_pi, 10)
    r1 = meio_pi - Decimal(float(c1))
    c2 = parte_mantissa(r1, 12)
    r2 = r1 - Decimal(float(c2))
    c3 = parte_mantissa(r2, 12)
    r3 = r2 - Decimal(float(c3))
    c4 = float32(r3)
    print(f"constexpr float kCW1 = {float(c1):.9g}f;   // π/2, 10 bits")
    print(f"constexpr float kCW2 = {float(c2):.9g}f;   // 12 bits")
    print(f"constexpr float kCW3 = {float(c3):.9g}f;   // 12 bits")
    print(f"constexpr float kCW4 = {float(c4):.9g}f;   // resto")
    pq = PI / 4
    hi = float32(pq)
    print(f"constexpr float kPiQuartoHi = {float(hi):.9g}f;   // π/4 = hi + lo")
    print(f"constexpr float kPiQuartoLo = {float(float32(pq - Decimal(float(hi)))):.9g}f;")
    print(f"constexpr float kDoisSobrePi = {float(np.float32(2 / np.pi)):.9g}f;")
    for nome, c in saida.items():
        print(f"constexpr float k{nome.capitalize()}[{len(c)}] = {{" + ", ".join(f"{float(v):.9g}f" for v in c) + "};")
    print(f"constexpr float kTanPi8 = {float(np.float32(np.tan(np.pi / 8))):.9g}f;")
    return 0


if __name__ == "__main__":
    sys.exit(main())
