#!/usr/bin/env python3
"""Period-jitter / phase-noise analysis of a locked PLL transient (fine sampling).

Usage: python3 scripts/jitter_analyze.py <raw_dir> [--fout 6.2e9]
Measures:
  - mean VCO period & period jitter (cycle-to-cycle)
  - phase PSD from zero crossings (Welch) -> integrate to rms jitter
"""
import re
import sys
from pathlib import Path

import numpy as np


def load_tran(raw: Path):
    f = next(raw.glob("*.tran.tran"))
    txt = f.read_text(errors="replace")
    body = txt.split("VALUE", 1)[1]
    d = {}
    for l in body.split("\n"):
        m = re.match(r'^"([A-Za-z0-9_.<>\\]+)"\s+([0-9.eE+-]+)', l.strip())
        if m:
            d.setdefault(m.group(1), []).append(float(m.group(2)))
    n = min(len(v) for v in d.values())
    return {k: np.asarray(v[:n]) for k, v in d.items()}


def main():
    raw = Path(sys.argv[1])
    fout = float(sys.argv[sys.argv.index("--fout") + 1]) if "--fout" in sys.argv else 6.2e9
    d = load_tran(raw)
    t = d["time"]
    v = d["OUTP"]
    print(f"n={len(t)}, tmax={t.max()*1e6:.2f}us")
    # zero crossings (rising) after 10% settle
    m = t > 0.1 * t.max()
    tv, vv = t[m], v[m]
    cross = np.where((vv[:-1] < 0.4) & (vv[1:] >= 0.4))[0]
    tc = tv[cross]
    print(f"crossings: {len(tc)}, mean period = {np.mean(np.diff(tc))*1e12:.2f} ps "
          f"({1/np.mean(np.diff(tc))/1e9:.4f} GHz)")
    per = np.diff(tc)
    print(f"period jitter sigma = {per.std()*1e15:.1f} fs")
    # phase noise via Welch on the crossing-time sequence
    # 相位序列 phi_k = 2*pi*fout*(tc_k - k*T0), T0 = mean period
    T0 = per.mean()
    phi = 2 * np.pi * fout * (tc - tc[0] - np.arange(len(tc)) * T0)
    fs = 1.0 / T0
    nperseg = min(2 ** 12, len(phi) // 4)
    if nperseg >= 64:
        f, Pxx = welch_psd(phi, fs, nperseg)
        # L(f) = Pxx(f)/2 (SSB, rad^2/Hz)
        for f0 in [1e5, 1e6, 1e7]:
            i = int(np.argmin(np.abs(f - f0)))
            L = 10 * np.log10(Pxx[i] / 2.0)
            print(f"L({f0/1e6:g}M) = {L:7.1f} dBc/Hz")
        # integrate jitter 1M..50M (limited by data length)
        mask = (f >= 1e6) & (f <= min(5e7, fs / 2))
        jit = np.sqrt(np.sum(Pxx[mask] * (f[1] - f[0])) ) / (2 * np.pi * fout)
        print(f"rms jitter [1M..50M] = {jit*1e15:.1f} fs")
        # full band estimate limited by resolution
        mask2 = (f >= f[1]) & (f <= fs / 2)
        jit2 = np.sqrt(np.sum(Pxx[mask2] * (f[1] - f[0]))) / (2 * np.pi * fout)
        print(f"rms jitter [full-band] = {jit2*1e15:.1f} fs")


def welch_psd(x, fs, nperseg):
    """Simple Welch PSD."""
    n = len(x)
    noverlap = nperseg // 2
    nfft = nperseg
    win = np.hanning(nperseg)
    S = np.zeros(nfft // 2 + 1)
    cnt = 0
    for start in range(0, n - nperseg + 1, nperseg - noverlap):
        seg = x[start:start + nperseg]
        seg = seg - seg.mean()
        X = np.fft.rfft(seg * win, nfft)
        S += np.abs(X) ** 2
        cnt += 1
    S /= cnt * (win ** 2).sum() * fs
    f = np.fft.rfftfreq(nfft, 1 / fs)
    return f, S


if __name__ == "__main__":
    main()
