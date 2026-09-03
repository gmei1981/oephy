#!/usr/bin/env python3
"""Plots for the VerilogA AFE prototype: eye heatmap + nominal waveforms."""
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR

# Palette: light mode (validated reference palette)
INK        = "#232323"   # primary text
INK_SOFT   = "#6b6a63"   # secondary text
GRID       = "#e3e1da"   # recessive grid
SURFACE    = "#ffffff"
BLUE_RAMP  = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
              "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
              "#184f95", "#104281", "#0d366b"]   # sequential blue, light->dark
S_BLUE, S_ORANGE, S_AQUA, S_MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#e87ba4"

VFS = 0.45


def style_ax(ax):
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=INK_SOFT, labelsize=9)
    ax.set_facecolor(SURFACE)


def plot_eye():
    d = json.load(open(OUT_DIR / "va_eye.json"))
    pts = d["points"]
    vrefs = sorted({p["vref_v"] for p in pts})
    pis   = sorted({p["pi_ui"] for p in pts})
    ber = np.zeros((len(vrefs), len(pis)))
    for p in pts:
        i = vrefs.index(p["vref_v"])
        j = pis.index(p["pi_ui"])
        b = p["ber"] if p["ber"] is not None else 1.0
        ber[i, j] = max(b, 1e-6)   # floor for log scale

    cmap = LinearSegmentedColormap.from_list("blue_seq", BLUE_RAMP)
    fig, ax = plt.subplots(figsize=(6.6, 5.2), dpi=160)
    im = ax.pcolormesh(pis, np.array(vrefs) * 1000, ber,
                       norm=matplotlib.colors.LogNorm(vmin=1e-5, vmax=1.0),
                       cmap=cmap, shading="auto")

    # BER=1e-3 contour (paper-style eye boundary)
    cs = ax.contour(pis, np.array(vrefs) * 1000, ber, levels=[1e-3],
                    colors=INK, linewidths=1.2, linestyles="--")
    ax.clabel(cs, fmt="BER 1e-3", fontsize=8, colors=INK)

    ok = ber <= 1e-3
    if ok.any():
        v_ok = np.array(vrefs) * 1000
        p_ok = np.array(pis)
        rows = np.any(ok, axis=1)
        cols = np.any(ok, axis=0)
        eh = v_ok[rows][-1] - v_ok[rows][0]
        ew = p_ok[cols][-1] - p_ok[cols][0]
        ax.text(0.03, 0.03,
                f"eye height (BER<=1e-3): {eh:.0f} mV\n"
                f"eye width  (BER<=1e-3): {ew:.2f} UI\n"
                f"paper (16G, BER 1e-9): 220 mV / 0.56 UI",
                transform=ax.transAxes, fontsize=9, color=INK,
                va="bottom", ha="left",
                bbox=dict(fc=SURFACE, ec=GRID, alpha=0.9, pad=5))

    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label("BER (PRBS23, 1280 bits/point)", fontsize=9, color=INK)
    cb.ax.tick_params(colors=INK_SOFT, labelsize=8)

    ax.set_xlabel("sampler phase PI (UI)", fontsize=10, color=INK)
    ax.set_ylabel("Vref (mV)", fontsize=10, color=INK)
    ax.set_title("RX eye scan — VerilogA prototype, 16 Gb/s NRZ "
                 "(ping-pong autozero AFE)", fontsize=11, color=INK)
    style_ax(ax)
    fig.tight_layout()
    out = OUT_DIR / "va_eye.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"[saved] {out}")
    plt.close(fig)


def plot_wave():
    d = json.load(open(OUT_DIR / "va_link.json"))
    s = d["signals"]
    t = np.array(s["time"])
    t_ns = t * 1e9
    w0, w1 = 8.0, 12.0          # 4 ns window after lock
    m = (t_ns >= w0) & (t_ns <= w1)

    series = [
        ("rx_in",   s["rx_in"],  S_ORANGE,  "RX input (V)"),
        ("vref",    s["vref"],   S_BLUE,    "Vref DAC (V)"),
        ("ck8",     s["ck8"],    S_MAGENTA, "ck8 — 8 GHz half-rate clock"),
        ("d_even",  s["d_even"], S_AQUA,    "d_even (sampler)"),
    ]

    fig, ax = plt.subplots(figsize=(6.6, 3.4), dpi=160)
    for name, y, color, label in series:
        ax.plot(t_ns[m], np.array(y)[m], lw=1.0, color=color, label=label)

    # direct labels at right edge
    ypos = {n: np.array(y)[m][-1] for n, y, _, _ in series}
    offs = {"rx_in": 0.10, "vref": -0.16, "ck8": 0.14, "d_even": -0.12}
    for n, y, c, _ in series:
        ax.text(w1 + 0.12, ypos[n] + offs[n], n, fontsize=8, color=c, va="center")

    ax.set_xlim(w0, w1 + 1.5)
    ax.set_ylim(-0.35, 1.0)
    ax.set_xlabel("time (ns)", fontsize=10, color=INK)
    ax.set_ylabel("voltage (V)", fontsize=10, color=INK)
    ax.set_title("Link waveforms @ nominal point (BER=0 over 959 bits)",
                 fontsize=11, color=INK)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.grid(axis="x", color=GRID, lw=0.6, alpha=0.5)
    style_ax(ax)
    fig.tight_layout()
    out = OUT_DIR / "va_wave.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"[saved] {out}")
    plt.close(fig)


if __name__ == "__main__":
    plot_eye()
    plot_wave()
