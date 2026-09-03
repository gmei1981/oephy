#!/usr/bin/env python3
"""Analyze vcotune2 (varactor connection variants): fVCO vs VCTRL per variant."""
import re
import sys
from pathlib import Path

import numpy as np

from loop_analyze import load_tran


def main():
    root = Path(sys.argv[1])
    for d in sorted(root.glob("R*")):
        vals = {}
        for f in sorted(d.glob("tune_*.raw")):
            if not f.is_dir():
                continue
            m = re.search(r"_(\d+)\.raw$", f.name)
            if not m:
                continue
            v = int(m.group(1)) / 10
            try:
                data = load_tran(f)
            except Exception as e:
                print(f"  [{f.name} load failed: {e}]")
                continue
            t, x = data["time"], data["OUTP"]
            mm = t > 8e-9
            if mm.sum() < 50:
                print(f"  [{f.name}: too few settled points]")
                continue
            xx = x[mm] - x[mm].mean()
            dt = np.median(np.diff(t))
            fft = np.abs(np.fft.rfft(xx * np.hanning(len(xx))))
            fr = np.fft.rfftfreq(len(xx), d=dt)
            vals[v] = fr[np.argmax(fft)] / 1e9
        line = "  ".join(f"{v:.1f}V:{vals[v]:6.2f}G" for v in sorted(vals))
        print(f"{d.name:10s}  {line}")


if __name__ == "__main__":
    main()
