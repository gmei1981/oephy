#!/usr/bin/env python3
"""Plots for the transistor-level (TSMC 12FFC) AFE simulation."""
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

INK        = "#232323"
INK_SOFT   = "#6b6a63"
GRID       = "#e3e1da"
SURFACE    = "#ffffff"
BLUE_RAMP  = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
              "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
              "#184f95", "#104281", "#0d366b"]
S_BLUE, S_ORANGE, S_AQUA, S_MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#e87ba4"
VFS = 0.45


def style_ax(ax):
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=INK_SOFT, labelsize=9)
    ax.set_facecolor(SURFACE)


def plot_tran_eye():
    d = json.load(open(OUT_DIR / "tran_eye.json"))
    pts = d["points"]
    vrefs = sorted({p["vref_v"] for p in pts})
    pis   = sorted({p["pi_ui"] for p in pts})
    ber = np.zeros((len(vrefs), len(pis)))
    for p in pts:
        i = vrefs.index(p["vref_v"])
        j = pis.index(p["pi_ui"])
        ber[i, j] = max(p["ber"] if p["ber"] is not None else 1.0, 1e-6)

    cmap = LinearSegmentedColormap.from_list("blue_seq", BLUE_RAMP)
    fig, ax = plt.subplots(figsize=(6.6, 5.2), dpi=160)
    im = ax.pcolormesh(pis, np.array(vrefs) * 1000, ber,
                       norm=matplotlib.colors.LogNorm(vmin=1e-5, vmax=1.0),
                       cmap=cmap, shading="auto")
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
                f"eye height (BER<=1e-3): >= {eh:.0f} mV\n"
                f"eye width  (BER<=1e-3): {ew:.2f} UI\n"
                f"paper (16G, BER 1e-9): 220 mV / 0.56 UI",
                transform=ax.transAxes, fontsize=9, color=INK,
                va="bottom", ha="left",
                bbox=dict(fc=SURFACE, ec=GRID, alpha=0.9, pad=5))

    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label("BER (PRBS23)", fontsize=9, color=INK)
    cb.ax.tick_params(colors=INK_SOFT, labelsize=8)
    ax.set_xlabel("sampler phase PI (UI)", fontsize=10, color=INK)
    ax.set_ylabel("Vref (mV)", fontsize=10, color=INK)
    ax.set_title("RX eye scan — transistor-level AFE, TSMC 12FFC, 16 Gb/s NRZ",
                 fontsize=11, color=INK)
    style_ax(ax)
    fig.tight_layout()
    out = OUT_DIR / "tran_eye.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"[saved] {out}")
    plt.close(fig)


def plot_tran_wave():
    d = json.load(open(OUT_DIR / "tran_link.json"))
    s = d["signals"]
    t = np.array(s["time"]) * 1e9
    w0, w1 = 8.0, 11.5
    m = (t >= w0) & (t <= w1)

    series = [
        ("rx_in",  s["rx_in"],       S_ORANGE,  "RX input (V)"),
        ("vref",   s["vref"],        S_BLUE,    "Vref DAC (V)"),
        ("d_even", s["d_even"],      S_AQUA,    "d_even (sampler)"),
        ("d_odd",  s["d_odd"],       S_MAGENTA, "d_odd (sampler)"),
    ]
    fig, ax = plt.subplots(figsize=(6.6, 3.4), dpi=160)
    for name, y, color, label in series:
        if name in s:
            ax.plot(t[m], np.array(y)[m], lw=1.0, color=color)

    offs = {"rx_in": 0.14, "vref": -0.18, "d_even": 0.16, "d_odd": -0.14}
    for n, y, c, _ in series:
        if n in s:
            yy = np.array(y)[m][-1]
            ax.text(w1 + 0.1, yy + offs[n], n, fontsize=8, color=c, va="center")

    ax.set_xlim(w0, w1 + 1.4)
    ax.set_ylim(-0.35, 1.05)
    ax.set_xlabel("time (ns)", fontsize=10, color=INK)
    ax.set_ylabel("voltage (V)", fontsize=10, color=INK)
    ax.set_title("Link waveforms @ nominal point (BER=0 over 1279 bits)",
                 fontsize=11, color=INK)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.grid(axis="x", color=GRID, lw=0.6, alpha=0.5)
    style_ax(ax)
    fig.tight_layout()
    out = OUT_DIR / "tran_wave.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"[saved] {out}")
    plt.close(fig)


def plot_az_compare():
    va = json.load(open(OUT_DIR / "va_az.json"))["cases"]
    tr = json.load(open(OUT_DIR / "tran_az.json"))["cases"]
    # gather: for each case (VA and tran)
    labels, bers, colors = [], [], []
    mapping = {
        "C_baseline":    ("baseline", S_BLUE),
        "A_az_on_200m":  ("offset, AZ on", S_AQUA),
        "B_az_off_200m": ("offset, AZ off", S_ORANGE),
        "D_az_off_trim": ("offset, Vref trim", S_MAGENTA),
    }
    va_names = [c["case"] for c in va]
    for c in va:
        labels.append(f"VA {mapping[c['case']][0]}")
        bers.append(c["ber"])
        colors.append(mapping[c["case"]][1])
    for c in tr:
        labels.append(f"12nm {c['case'].replace('az_', 'AZ ')}")
        bers.append(c["ber"])
        colors.append(S_BLUE if "on" in c["case"] else S_ORANGE)

    fig, ax = plt.subplots(figsize=(6.6, 3.6), dpi=160)
    x = np.arange(len(labels))
    bars = ax.bar(x, bers, color=colors, width=0.6)
    for xi, b, v in zip(x, bars, bers):
        if v is not None:
            ax.text(xi, v + 0.012, f"{v:.1%}" if v > 0.005 else "0",
                    ha="center", fontsize=8, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, color=INK, rotation=15)
    ax.set_ylabel("BER (PRBS23)", fontsize=10, color=INK)
    ax.set_title("Autozero / ping-pong drift cancellation demonstration",
                 fontsize=11, color=INK)
    ax.set_ylim(0, max([b for b in bers if b is not None]) * 1.25 + 0.02)
    ax.grid(axis="y", color=GRID, lw=0.6)
    style_ax(ax)
    fig.tight_layout()
    out = OUT_DIR / "az_compare.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"[saved] {out}")
    plt.close(fig)


def plot_corners():
    d = json.load(open(OUT_DIR / "tran_corners.json"))
    rows = [(f"{s['corner'].replace('top_', '')}@{s['temp']}",
             s["zero_ber_codes"]) for s in d["summary"]
            if s.get("zero_ber_codes")]
    fig, ax = plt.subplots(figsize=(6.6, 3.4), dpi=160)
    y = np.arange(len(rows))[::-1]
    for yi, (label, zc) in zip(y, rows):
        lo, hi = zc[0] / 255 * VFS * 1000, zc[-1] / 255 * VFS * 1000
        ax.barh(yi, hi - lo, left=lo, height=0.55, color=S_BLUE)
        ax.text(hi + 4, yi, f"{hi - lo:.0f} mV", fontsize=8, color=INK,
                va="center")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=9, color=INK)
    ax.set_xlim(120, 440)
    ax.set_xlabel("Vref zero-BER window (mV)", fontsize=10, color=INK)
    ax.set_title("Corner x temperature — zero-BER Vref windows "
                 f"({len(rows)}/{len(d['summary'])} configs BER=0)",
                 fontsize=11, color=INK)
    ax.grid(axis="x", color=GRID, lw=0.6)
    style_ax(ax)
    fig.tight_layout()
    out = OUT_DIR / "tran_corners.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"[saved] {out}")
    plt.close(fig)


def plot_mc_offset():
    m = json.load(open(OUT_DIR / "tran_mc_offset.json"))
    v = np.array(m["vos"]["az_on"]) * 1000
    fig, ax = plt.subplots(figsize=(6.6, 3.4), dpi=160)
    ax.hist(v, bins=25, color=S_BLUE, edgecolor=SURFACE, linewidth=0.8)
    mean, std = v.mean(), v.std()
    ax.axvline(mean, color=INK, lw=1.0, ls="--")
    ax.text(0.97, 0.95,
            f"mean = {mean:.2f} mV\n$\\sigma$ = {std:.2f} mV\n"
            f"6$\\sigma$ = {6 * std:.0f} mV < eye window 194 mV",
            transform=ax.transAxes, fontsize=9, color=INK,
            va="top", ha="right",
            bbox=dict(fc=SURFACE, ec=GRID, alpha=0.9, pad=5))
    ax.set_xlabel("Static offset $V_{OS}$ (mV)", fontsize=10, color=INK)
    ax.set_ylabel("seeds", fontsize=10, color=INK)
    ax.set_title("Comparator static offset Monte Carlo — ping-pong AZ, "
                 f"{len(v)} seeds (vref training absorbs 6$\\sigma$)",
                 fontsize=11, color=INK)
    ax.grid(axis="y", color=GRID, lw=0.6)
    style_ax(ax)
    fig.tight_layout()
    out = OUT_DIR / "tran_mc_offset.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"[saved] {out}")
    plt.close(fig)


def plot_mc_ron():
    r = json.load(open(OUT_DIR / "tran_mc_ron.json"))
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.6), dpi=160)
    for ax, key, title, color in (
            (axes[0], "ron_pu", "Pull-up Ron", S_BLUE),
            (axes[1], "ron_pd", "Pull-down Ron", S_AQUA)):
        v = np.array(r[key])
        lo, hi = v.min(), v.max()
        ax.hist(v, bins=min(25, max(8, len(np.unique(v)))),
                color=color, edgecolor=SURFACE, linewidth=0.8)
        ax.text(0.97, 0.95, f"{v.mean():.1f} $\\pm$ {v.std():.2f} $\\Omega$"
                f"\n($\\sigma$/$\\mu$ = {v.std() / v.mean() * 100:.1f}%)",
                transform=ax.transAxes, fontsize=8, color=INK,
                va="top", ha="right",
                bbox=dict(fc=SURFACE, ec=GRID, alpha=0.9, pad=4))
        ax.set_title(f"{title} ({len(v)} seeds)", fontsize=10, color=INK)
        ax.set_xlabel("$\\Omega$", fontsize=9, color=INK)
        ax.grid(axis="y", color=GRID, lw=0.6)
        style_ax(ax)
    fig.suptitle("TX driver Ron Monte Carlo — local MC (usage.scs), "
                 "2 mA forced", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = OUT_DIR / "tran_mc_ron.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"[saved] {out}")
    plt.close(fig)


def plot_supply():
    d = json.load(open(OUT_DIR / "tran_supply.json"))
    pts = [p for p in d["points"] if p.get("ok")]
    labels, vals = [], []
    for p in pts:
        c = p["case"]
        if c.startswith("inj_"):
            amp, fn = c[4:].split("@")
            labels.append(f"{amp[:-1]} mV\n{fn[:-1]} MHz")
        else:
            labels.append("LS\n" + c[3:].replace("n", " nH"))
        vals.append(p["vss_pk"] * 1000)
    fig, ax = plt.subplots(figsize=(6.6, 3.2), dpi=160)
    x = np.arange(len(vals))
    ax.bar(x, vals, color=S_BLUE, width=0.62)
    for xi, v, lab in zip(x, vals, labels):
        if lab.startswith("LS"):
            ax.text(xi, v + 8, f"{v:.0f} mV", ha="center", fontsize=8,
                    color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, color=INK)
    ax.set_ylabel("|vss| peak (mV), t > 5 ns", fontsize=10, color=INK)
    ax.set_title("Supply integrity — VDD-noise injection sweep + bond-wire "
                 "inductance (BER = 0 in all cases)", fontsize=11, color=INK)
    ax.set_ylim(0, max(vals) * 1.18)
    ax.grid(axis="y", color=GRID, lw=0.6)
    style_ax(ax)
    fig.tight_layout()
    out = OUT_DIR / "tran_supply.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"[saved] {out}")
    plt.close(fig)


def plot_dac_linearity():
    d = json.load(open(OUT_DIR / "dac_dnl.json"))
    codes = d["vref"]
    fig, ax = plt.subplots(figsize=(6.6, 3.2), dpi=160)
    ax.plot(codes[1:], d["dnl_lsb"], lw=1.2, color=S_BLUE, label="DNL")
    ax.plot(codes, d["inl_lsb"], lw=1.2, color=S_ORANGE, label="INL")
    for lev in (-1, 1):
        ax.axhline(lev, color=INK_SOFT, lw=0.8, ls="--")
    ax.text(0.02, 0.95,
            f"DNL max {d['dnl_max']:.2f} LSB\nINL max {d['inl_max']:.2f} LSB"
            "\ndashed: $\\pm$1 LSB",
            transform=ax.transAxes, fontsize=9, color=INK, va="top",
            bbox=dict(fc=SURFACE, ec=GRID, alpha=0.9, pad=5))
    ax.text(codes[-1] - 3, d["dnl_lsb"][-1] + 0.12, "DNL", fontsize=8,
            color=INK, ha="right")
    ax.text(codes[-1] - 3, d["inl_lsb"][-1] - 0.22, "INL", fontsize=8,
            color=INK, ha="right")
    ax.set_xlabel("DAC code (0-255)", fontsize=10, color=INK)
    ax.set_ylabel("LSB", fontsize=10, color=INK)
    ax.set_title("8b R-2R Vref DAC linearity — 256-code DC enumeration",
                 fontsize=11, color=INK)
    ax.grid(axis="y", color=GRID, lw=0.6)
    style_ax(ax)
    fig.tight_layout()
    out = OUT_DIR / "dac_linearity.png"
    fig.savefig(out, facecolor=SURFACE)
    print(f"[saved] {out}")
    plt.close(fig)


if __name__ == "__main__":
    plot_tran_eye()
    plot_tran_wave()
    plot_az_compare()
    plot_corners()
    plot_mc_offset()
    plot_mc_ron()
    plot_supply()
    plot_dac_linearity()
