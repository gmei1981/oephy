#!/usr/bin/env python3
"""Analyze strobed loop tran data: lock trajectory, calibration convergence, freq error.

Usage: python3 scripts/loop_analyze.py <raw_dir>
"""
import re
import sys
from pathlib import Path

import numpy as np


def load_tran(raw: Path) -> dict[str, np.ndarray]:
    f = next(raw.glob("*.tran.tran"))
    txt = f.read_text(errors="replace")
    body = txt.split("VALUE", 1)[1]
    d: dict[str, list] = {}
    for l in body.split("\n"):
        m = re.match(r'^"([A-Za-z0-9_.<>\\]+)"\s+([0-9.eE+-]+)', l.strip())
        if m:
            d.setdefault(m.group(1), []).append(float(m.group(2)))
    n = min(len(v) for v in d.values())
    return {k: np.asarray(v[:n]) for k, v in d.items()}


def main():
    raw = Path(sys.argv[1])
    d = load_tran(raw)
    t = d["time"]
    print(f"n={len(t)}  tmax={t.max()*1e6:.2f} us")

    # CKFB fire rate (level changes) per 0.5us window
    cf = d["CKFB"]
    fire = np.where(np.diff(cf > 0.4))[0]
    print("\nCKFB fire rate (MHz) per 0.5us:")
    for t0 in np.arange(0, t.max() - 0.4e-6, 0.5e-6):
        w = (t[fire] >= t0) & (t[fire] < t0 + 0.5e-6)
        nf = w.sum()
        print(f"  {t0*1e6:5.1f}us: {nf/(0.5e-6)/1e6:8.2f}  ", end="")
        if (t0 * 1e6) % 2 == 1:
            print()
    print()

    # per-window means
    keys = ["VCTRL", "VHOLD", "VREF", "KDTC", "VDCC", "RDCC"]
    win = 0.3e-6
    print("window means:")
    print("  t(us)   " + " ".join(f"{k:>9}" for k in keys))
    for t0 in np.arange(0, t.max() - win, win):
        m = (t >= t0) & (t < t0 + win)
        row = f"  {t0*1e6:6.1f} "
        for k in keys:
            row += f"{d[k][m].mean():9.4g} "
        print(row)

    # EPSC slope in last window = residual freq error (TVCO units per CKFB cycle)
    e = d["EPSC"]
    m = t >= t.max() - 0.5e-6
    if m.sum() > 50:
        k = np.polyfit(t[m], e[m], 1)
        ferr = k[0] * (1 / 162.3e-12)  # d(TVCO)/dt -> Hz
        print(f"\nlast-window EPSC slope = {k[0]:.3g} TVCO/s  -> freq error ~ {ferr/1e6:.2f} MHz")
        print(f"VCTRL last = {d['VCTRL'][m].mean():.4f}, VHOLD last = {d['VHOLD'][m].mean():.4f}, "
              f"VREF last = {d['VREF'][m].mean():.4f}")


if __name__ == "__main__":
    main()
