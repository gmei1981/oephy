#!/usr/bin/env python3
"""Generate paper figures (SVG) for the reproduction report.

fig1_lock.svg    CKFB calibration-error trajectory over 10us (fine runs, 3 channels)
fig2_calib.svg   LMS calibration trajectories (5us strobed, 2x2 small multiples)
fig3_spurs.svg   VCO phase-demod spur spectra (3 panels: main / nearint / step2)
fig4_pn.svg      VCO phase noise single vs dual core (from pn_extract.npz)

Palette: validated categorical slots 1-3 (blue/orange/aqua) on white figure cards.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fine_analyze import stream_parse, edges, welch_psd
from loop_analyze import load_tran

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "figures"
OUT.mkdir(exist_ok=True)

# validated palette (light, on white figure card)
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"   # main / nearint / step2
INK, SEC, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
FIG_BG = "#ffffff"
RED_REF = "#e34948"

plt.rcParams.update({
    "figure.facecolor": FIG_BG, "axes.facecolor": FIG_BG,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": SEC, "ytick.color": SEC,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "font.size": 9.5, "axes.titlesize": 10.5, "axes.labelsize": 9.5,
    "legend.frameon": False, "lines.linewidth": 1.7,
    "savefig.bbox": "tight", "svg.fonttype": "none",
})

CHANNELS = [
    {"name": "Main (nr=195)",    "color": S1,
     "dir": ROOT / "sim" / "out" / "cal_main_nr195_fine",
     "fref": 153.6e6, "frac": 0.364583, "fvco": 6.2e9, "target": 153.6},
    {"name": "Near-int (nr=172)", "color": S2,
     "dir": ROOT / "sim" / "out" / "cal_nearint_nr172_fine",
     "fref": 153.6e6, "frac": 0.000651, "fvco": 6.4512e9, "target": 153.6},
    {"name": "Step2 (nr=188)",   "color": S3,
     "dir": ROOT / "sim" / "out" / "step2_fine_nr188_10u",
     "fref": 100.0e6, "frac": 0.0, "fvco": 8.0e9, "target": 100.0},
]


def fine_freq_traj(chan, win=1e-6):
    d = chan["dir"]
    t, ck, op, vc = stream_parse(d / "plltran.tran.tran")
    te = edges(t, ck)
    te = te[te > 0.3 * t.max()]
    bins = np.arange(0.3 * t.max(), t.max(), win)
    f = np.array([np.sum((te >= b) & (te < b + win)) / win for b in bins]) / 1e6
    err = (f / chan["target"] - 1) * 100
    return bins * 1e6, err, te, t, op


def vco_phase_psd(chan, nperseg_min=8192):
    t, ck, op, vc = stream_parse(chan["dir"] / "plltran.tran.tran")
    th = (op.min() + op.max()) / 2
    to = edges(t, op, th)
    to = to[to > 0.3 * t.max()]
    fv = 1.0 / np.diff(to).mean()
    phiv = 2 * np.pi * (to[1:] - to[0] - np.arange(len(to) - 1) / fv) * fv
    npv = min(2 ** 16, max(nperseg_min, len(phiv) // 4))
    f, P = welch_psd(phiv, fv, npv)
    L = 10 * np.log10(P / 2.0)
    # downsample log-spaced for SVG size
    m = f > 0
    f, L = f[m], L[m]
    if len(f) > 400:
        idx = np.unique(np.logspace(np.log10(f.min() + 1), np.log10(f.max()), 400).astype(int))
        idx = idx[idx < len(f)]
        f, L = f[idx], L[idx]
    return f, L, phiv, fv


def fig1():
    fig, ax = plt.subplots(figsize=(7.0, 2.6))
    for ch in CHANNELS:
        bins, err, *_ = fine_freq_traj(ch)
        ax.plot(bins, err, color=ch["color"], label=ch["name"])
    ax.axhline(0, color=AXIS, lw=1.0)
    ax.set_xlabel("time (µs)")
    ax.set_ylabel("CKFB freq error (%)")
    ax.legend(loc="lower left", fontsize=8.5)
    ax.set_ylim(-0.6, 0.6)
    fig.savefig(OUT / "fig1_lock.svg")
    plt.close(fig)
    print("fig1_lock.svg done")


def fig2():
    cal = [
        ("Main (nr=195)", S1, "sim/out/cal_main_nr195_5u"),
        ("Near-int (nr=172)", S2, "sim/out/cal_nearint_nr172_5u"),
    ]
    keys = [("VDCC", "ps"), ("RDCC", "ps"), ("KDTC", ""), ("VREF", "V")]
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.6), sharex=True)
    for ax, (k, unit) in zip(axes.flat, keys):
        for name, color, raw in cal:
            d = load_tran(Path(raw))
            t, v = d["time"], d[k]
            win = 0.3e-6
            tt, vm = [], []
            for t0 in np.arange(0, t.max() - win, win):
                m = (t >= t0) & (t < t0 + win)
                tt.append(t0 * 1e6)
                vm.append(v[m].mean())
            ax.plot(tt, vm, color=color, label=name)
        ax.set_ylabel(f"{k} ({unit})" if unit else k)
        ax.set_xlim(0, 5)
    axes[1, 0].set_xlabel("time (µs)")
    axes[1, 1].set_xlabel("time (µs)")
    axes[0, 0].legend(fontsize=8)
    fig.savefig(OUT / "fig2_calib.svg")
    plt.close(fig)
    print("fig2_calib.svg done")


def fig3():
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 2.9))
    annots = [
        # (freq, text, dy)
        [(56.0e6, "frac −72.9 dBc", 1), (153.6e6, "ref −59.5", 1)],
        [(100e3, "frac >0 dBc", 1), (200e3, "2·frac >0 dBc", 1)],
        [(100e6, "ref −63.4", 1)],
    ]
    for ax, ch, ann in zip(axes, CHANNELS, annots):
        f, L, *_ = vco_phase_psd(ch)
        ax.semilogx(f / 1e6, L, color=ch["color"], lw=1.5)
        for f0, txt, dy in ann:
            ax.axvline(f0 / 1e6, color=MUTED, lw=0.7, ls=":")
            ax.annotate(txt, (f0 / 1e6, dy), xytext=(0.012, 0.86),
                        textcoords="axes fraction", fontsize=7.5, color=SEC)
        ax.set_xlabel("offset (MHz)")
        ax.set_title(ch["name"], fontsize=9.5)
        ax.set_xlim(1e-2, 1e4)
    axes[0].set_ylabel("L(f) (dBc/Hz)")
    fig.savefig(OUT / "fig3_spurs.svg")
    plt.close(fig)
    print("fig3_spurs.svg done")


def fig4():
    fig, ax = plt.subplots(figsize=(6.0, 2.8))
    for name, color, npz in [("single-core", S1, "vco_pnoise_single"), ("dual-core", S3, "vco_pnoise_dual")]:
        d = np.load(ROOT / "sim" / "vco" / "out" / f"{npz}.raw" / "pn_extract.npz")
        f, L = d["freqs"], d["L"]
        ax.loglog(f, 10 ** (L / 10), color=color, label=name)
        ax.annotate(f"{L[np.argmin(np.abs(f - 1e5))]:.1f} dBc/Hz @100k",
                    (1e5, 10 ** (L[np.argmin(np.abs(f - 1e5))] / 10)),
                    xytext=(2.2e4, 6e-9), fontsize=7.5, color=color)
    # paper reference line -92 dBc/Hz @100k, f^-2
    fp = np.logspace(4, 7, 100)
    ax.loglog(fp, 10 ** (-92 / 10) * (fp / 1e5) ** -2, color=RED_REF, lw=1.2, ls="--",
              label="paper −92 @100k (f⁻²)")
    ax.set_xlabel("offset (Hz)")
    ax.set_ylabel("L(f) (dBc/Hz)")
    ax.legend(fontsize=8)
    ax.set_xlim(1e4, 1e8)
    fig.savefig(OUT / "fig4_pn.svg")
    plt.close(fig)
    print("fig4_pn.svg done")


if __name__ == "__main__":
    fig1()
    fig4()
    fig2()
    fig3()
    print("ALL DONE")
