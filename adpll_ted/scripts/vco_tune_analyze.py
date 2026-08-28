#!/usr/bin/env python3
"""Analyze VCO tuning-curve batch results: fVCO vs VCTRL per tank variant/core.

Usage: python3 scripts/vco_tune_analyze.py <vcotune_dir>
Reads <dir>/<T?>/*.raw (psfascii), FFTs OUTP, prints tuning table.
"""
import re
import sys
from pathlib import Path

import numpy as np

from loop_analyze import load_tran


def f_est(d: dict) -> float:
    t, v = d["time"], d["OUTP"]
    m = t > 8e-9  # settled
    if m.sum() < 50:
        return float("nan")
    x = v[m] - v[m].mean()
    dt = np.median(np.diff(t))
    fft = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    fr = np.fft.rfftfreq(len(x), d=dt)
    return fr[np.argmax(fft)]


def main():
    root = Path(sys.argv[1])
    rows = []
    for d in sorted(root.glob("T*")):
        for f in sorted(d.glob("tune_*.raw")):
            if not f.is_dir():
                continue
            try:
                data = load_tran(f)
            except Exception:
                continue
            m = re.match(r"tune_(T\d)_(vco_\w+)_(\d+)", f.name)
            cfg, core, v10 = m.groups()
            v = int(v10) / 10
            rows.append((cfg, core, v, f_est(data)))
    hdr = "cfg/core " + " ".join(f"{v:.1f}V" for v in sorted({r[2] for r in rows}))
    print(hdr)
    for cfg in sorted({r[0] for r in rows}):
        for core in sorted({r[1] for r in rows}):
            vals = {r[2]: r[3] for r in rows if r[0] == cfg and r[1] == core}
            line = f"{cfg:3s} {core:9s} " + " ".join(
                f"{vals.get(v, float('nan'))/1e9:6.2f}G" for v in sorted(vals))
            print(line)


if __name__ == "__main__":
    main()
