#!/usr/bin/env python3
"""Analytic integrated jitter: open-loop VCO PN curve high-passed by the loop.

Usage: python3 scripts/jitter_analytic.py <pn_extract.npz> [--fc 1.2e6] [--fout 6.2e9] [--paper]
  --paper: benchmark with paper VCO PN (-92 dBc/Hz @100k @6G, f^-2) to validate the口径
Integrates SSB L(f)*|H_hp|^2 from 10k to 100M, |H_hp|^2 = f^2/(f^2+fc^2).
"""
import argparse
import sys

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz", nargs="?")
    ap.add_argument("--fc", type=float, default=1.2e6)
    ap.add_argument("--fout", type=float, default=6.2e9)
    ap.add_argument("--paper", action="store_true")
    args = ap.parse_args()

    fmin, fmax = 10e3, 100e6
    if args.paper:
        f = np.logspace(np.log10(fmin), np.log10(fmax), 201)
        L = -92.0 - 20 * np.log10(f / 1e5)  # dBc/Hz, f^-2 from -92@100k
    else:
        d = np.load(args.npz)
        f, L = d["freqs"], d["L"]
    fc = args.fc
    H = f**2 / (f**2 + fc**2)
    Llin = 10 ** (L / 10) * H

    # trapezoidal integration on the actual curve
    idx = np.argsort(f)
    f, Llin = f[idx], Llin[idx]
    m = (f >= fmin) & (f <= fmax)
    integ = np.trapz(Llin[m], f[m])  # rad^2 (SSB -> total phase variance = 2*integ)
    jit = np.sqrt(2 * integ) / (2 * np.pi * args.fout)

    # also report contributions split at fc, plus sensitivity at 100kHz (LMS-type loop)
    below = np.trapz(Llin[m & (f < fc)], f[m & (f < fc)])
    above = np.trapz(Llin[m & (f >= fc)], f[m & (f >= fc)])
    print(f"fc={fc/1e6:.2f} MHz, fout={args.fout/1e9:.3f} GHz, L(100k)={np.interp(1e5, f, L):.1f} dBc/Hz")
    print(f"  integral [10k-100M] = {integ:.3e} rad^2  -> rms jitter = {jit*1e15:.1f} fs"
          f"  (phase variance conserved at any output; paper: 83.4 fs dual-core)")
    print(f"  below fc: {below:.3e} ({100*below/integ:.1f}%)   above fc: {above:.3e} ({100*above/integ:.1f}%)")
    if args.fc != 100e3:
        H2 = f**2 / (f**2 + (100e3)**2)
        L2 = 10 ** (L / 10) * H2
        integ2 = np.trapz(L2[m], f[m])
        print(f"  sensitivity fc=100k (LMS-loop口径): {np.sqrt(2*integ2)/(2*np.pi*args.fout)*1e15:.1f} fs")


if __name__ == "__main__":
    main()
