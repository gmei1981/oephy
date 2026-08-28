#!/usr/bin/env python3
"""Near-integer fractional spur analysis from CKFB edge phase sequence.

Phase of CKFB edges vs the ideal 153.6M grid -> Welch PSD -> spur levels.
Expected fractional spur at f_off = frac2*fref_dtc (100kHz for nearint).

Usage: python3 scripts/spur_analyze.py <raw_dir> [--fref 153.6e6] [--frac 0.000651]
"""
import sys
from pathlib import Path

import numpy as np

from loop_analyze import load_tran


def welch_psd(x, fs, nperseg):
    n = len(x)
    noverlap = nperseg // 2
    win = np.hanning(nperseg)
    S = np.zeros(nperseg // 2 + 1)
    cnt = 0
    for start in range(0, n - nperseg + 1, nperseg - noverlap):
        seg = x[start:start + nperseg] - x[start:start + nperseg].mean()
        X = np.fft.rfft(seg * win, nperseg)
        S += np.abs(X) ** 2
        cnt += 1
    S /= cnt * (win ** 2).sum() * fs
    return np.fft.rfftfreq(nperseg, 1 / fs), S


def main():
    raw = Path(sys.argv[1])
    fref = float(sys.argv[sys.argv.index("--fref") + 1]) if "--fref" in sys.argv else 153.6e6
    frac = float(sys.argv[sys.argv.index("--frac") + 1]) if "--frac" in sys.argv else 0.000651
    d = load_tran(raw)
    t = d["time"]
    ck = d["CKFB"]
    fire = np.where(np.diff(ck > 0.4))[0]
    te = t[fire]
    # keep after 30% settle
    te = te[te > 0.3 * t.max()]
    print(f"n_edges={len(te)}  span={ (te.max()-te.min())*1e6:.2f}us")
    # rising edges only (every other)
    te = te[::2]
    T0 = 1.0 / fref
    phi = 2 * np.pi * (te - te[0] - np.arange(len(te)) * T0) / T0  # rad (phase error in UI*2pi)
    fs = 1.0 / T0
    nperseg = min(2 ** 14, len(phi) // 2)
    f, P = welch_psd(phi, fs, nperseg)
    print(f"PSD resolution = {f[1]/1e3:.1f} kHz, nperseg={nperseg}")
    # phase PSD -> dBc (SSB) per Hz; spur at f_off
    f_off = frac * fref
    for f0 in (f_off, 2 * f_off, 1e6):
        i = int(np.argmin(np.abs(f - f0)))
        bin_noise = 10 * np.log10(P[i] / 2.0)
        print(f"  f={f0/1e3:8.1f}kHz: P_phi={P[i]:.3e} rad^2/Hz -> L={bin_noise:7.1f} dBc/Hz(bin)")
    # integrated rms jitter 10k-100M: CKFB phase -> VCO phase (x Ndiv), convert to seconds at fVCO
    ndiv = 42.000651 if frac else 42.0
    fvco = fref * ndiv
    mask = (f >= 10e3) & (f <= min(100e6, fs / 2))
    jit = np.sqrt(np.sum(P[mask] * (f[1] - f[0]))) * ndiv / (2 * np.pi * fvco)
    print(f"rms jitter [10k-100M] = {jit*1e15:.1f} fs (VCO phase)")
    # print top-5 bins in 10k-10M for spur hunting
    m = (f > 10e3) & (f < 10e6)
    idx = np.argsort(P[m])[::-1][:5]
    for i in idx:
        print(f"  peak: {f[m][i]/1e3:8.1f}kHz  L={10*np.log10(P[m][i]/2):7.1f} dBc/Hz(bin)")


if __name__ == "__main__":
    main()
