#!/usr/bin/env python3
"""Combined analysis of fine-sampling closed-loop runs (single streaming parse):
  1. CKFB rising edges -> mean freq (per window + tail), phase-error sequence
  2. Exact-DFT spur levels on CKFB phase seq: f_frac, 2*f_frac, f_ref(153.6M)
  3. Phase PSD (Welch) -> rms jitter [100k..max]
  4. OUTP zero crossings -> VCO mean freq, period jitter
  5. OUTP per-period phase demod (VCO-rate phase seq) -> spurs at f_frac/f_ref + jitter

Usage: python3 scripts/fine_analyze.py <raw_dir> [--fref 153.6e6] [--frac 0.000651] [--fvco 6.4512e9]
"""
import argparse
import sys
from pathlib import Path

import numpy as np


def stream_parse(path: Path):
    """Stream-parse the psfascii VALUE section into numpy arrays (low memory)."""
    t, ck, op, vc = [], [], [], []
    started = False
    with open(path, errors="replace") as f:
        for line in f:
            if not started:
                if line.startswith("VALUE"):
                    started = True
                continue
            if line.startswith('"time"'):
                t.append(float(line[6:].replace('"', '')))
            elif line.startswith('"CKFB"'):
                ck.append(float(line[6:].replace('"', '')))
            elif line.startswith('"OUTP"'):
                op.append(float(line[6:].replace('"', '')))
            elif line.startswith('"VCTRL"'):
                vc.append(float(line[6:].replace('"', '')))
    n = min(len(t), len(ck), len(op), len(vc))
    return (np.asarray(t[:n]), np.asarray(ck[:n]),
            np.asarray(op[:n]), np.asarray(vc[:n]))


def edges(t, x, th=0.4):
    """Rising-edge times with linear interpolation."""
    m = (x[:-1] < th) & (x[1:] >= th)
    i = np.where(m)[0]
    frac = (th - x[i]) / (x[i + 1] - x[i])
    return t[i] + frac * (t[i + 1] - t[i])


def tone_dbfs(phi, f0, fs):
    """Exact-DFT tone power in dBc: 10log10(theta_pk^2/4)."""
    k = np.arange(len(phi))
    c = np.sum(phi * np.exp(-2j * np.pi * f0 / fs * k))
    th_pk2 = 4.0 * np.abs(c) ** 2 / len(phi) ** 2
    if th_pk2 <= 0:
        return -np.inf
    return 10.0 * np.log10(th_pk2 / 4.0)


def welch_psd(x, fs, nperseg):
    n = len(x)
    noverlap = nperseg // 2
    win = np.hanning(nperseg)
    S = np.zeros(nperseg // 2 + 1)
    cnt = 0
    for start in range(0, n - nperseg + 1, nperseg - noverlap):
        seg = x[start:start + nperseg] - x[start:start + nperseg].mean()
        S += np.abs(np.fft.rfft(seg * win, nperseg)) ** 2
        cnt += 1
    S /= cnt * (win ** 2).sum() * fs
    return np.fft.rfftfreq(nperseg, 1 / fs), S


def jitter_from_psd(f, P, fmin, fmax):
    """Phase rms (rad) from phase PSD integrated over [fmin, fmax]."""
    m = (f >= fmin) & (f <= min(fmax, f[-1]))
    if m.sum() < 2:
        return np.nan
    return np.sqrt(np.trapz(P[m], f[m]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--fref", type=float, default=153.6e6)
    ap.add_argument("--frac", type=float, default=0.000651)
    ap.add_argument("--fvco", type=float, default=6.4512e9)
    args = ap.parse_args()

    raw = Path(args.raw)
    f = next(raw.glob("*.tran.tran"))
    print(f"parsing {f.name} ({f.stat().st_size/1e6:.0f} MB)...", flush=True)
    t, ck, op, vc = stream_parse(f)
    print(f"n_pts={len(t)}  tmax={t.max()*1e6:.2f}us", flush=True)

    # ---- CKFB ----
    te = edges(t, ck)
    te = te[te > 0.3 * t.max()]
    T0 = 1.0 / args.fref
    phi = 2 * np.pi * (te - te[0] - np.arange(len(te)) * T0) / T0
    print(f"\nCKFB edges: {len(te)}, mean f = {1/np.mean(np.diff(te))/1e6:.4f} MHz "
          f"(err {(1/np.mean(np.diff(te))/args.fref-1)*100:+.4f}%), "
          f"tail f = {1/np.mean(np.diff(te[len(te)//2:]))/1e6:.4f} MHz")
    fs = args.fref
    f_frac = args.frac * args.fref
    for name, f0 in [("f_frac", f_frac), ("2*f_frac", 2 * f_frac), ("f_ref", args.fref)]:
        print(f"  CKFB-phase spur @{name} ({f0/1e3:.1f} kHz): {tone_dbfs(phi, f0, fs):7.1f} dBc")
    nper = min(2 ** 14, max(256, len(phi) // 2))
    fw, Pw = welch_psd(phi, fs, nper)
    print(f"  CKFB-phase PSD: nperseg={nper}, res={fw[1]/1e3:.0f} kHz")
    ph_rms = jitter_from_psd(fw, Pw, 100e3, 100e6)
    print(f"  CKFB-phase rms jitter [100k-{fw[-1]/1e6:.0f}M] = "
          f"{ph_rms/(2*np.pi*args.fref)*1e15:.1f} fs (at ref grid)")

    # ---- OUTP ----
    th = (op.min() + op.max()) / 2
    to = edges(t, op, th)
    to = to[to > 0.3 * t.max()]
    per = np.diff(to)
    print(f"\nOUTP crossings: {len(to)}, mean period = {per.mean()*1e12:.2f} ps "
          f"-> fvco = {1/per.mean()/1e9:.4f} GHz, period jitter sigma = {per.std()*1e15:.1f} fs")

    # per-period phase demod at fvco rate
    fv = 1.0 / per.mean()
    phiv = 2 * np.pi * (to[1:] - to[0] - np.arange(len(to) - 1) / fv) * fv
    fsv = fv
    for name, f0 in [("f_frac", f_frac), ("f_ref", args.fref), ("2*f_ref", 2 * args.fref)]:
        print(f"  VCO-phase spur @{name}: {tone_dbfs(phiv, f0, fsv):7.1f} dBc")
    npv = min(2 ** 16, max(1024, len(phiv) // 4))
    fv2, Pv2 = welch_psd(phiv, fsv, npv)
    print(f"  VCO-phase PSD: nperseg={npv}, res={fv2[1]/1e3:.0f} kHz")
    jv = jitter_from_psd(fv2, Pv2, 100e3, 100e6)
    print(f"  VCO-phase rms jitter [100k-100M] = {jv/(2*np.pi*fv)*1e15:.1f} fs")
    # VCTRL stats
    m = t > 0.3 * t.max()
    print(f"\nVCTRL: mean(last70%)={vc[m].mean():.4f}, final={vc[-1]:.4f}, "
          f"pp={vc[m].max()-vc[m].min():.3f}")


if __name__ == "__main__":
    main()
