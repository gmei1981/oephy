#!/usr/bin/env python3
"""Cal-run verdict: CKFB mean period/freq (edge-mean method) + loop state finals.

Usage: python3 scripts/cal_measure.py <raw_dir> [--tail 0.5]
  --tail: fraction of window used for the period mean (default last 50%).
Strobe data: CKFB edge times quantized to 100ps; mean over N edges -> ~0.02% freq precision.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

from loop_analyze import load_tran


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--tail", type=float, default=0.5)
    args = ap.parse_args()

    d = load_tran(Path(args.raw))
    t, ck = d["time"], d["CKFB"]
    # rising edges
    rise = np.where((ck[:-1] < 0.4) & (ck[1:] >= 0.4))[0]
    te = t[rise]
    tsel = te[te >= (1 - args.tail) * t.max()]
    per = np.diff(tsel)
    T = per.mean()
    f = 1 / T
    # per-window means in the selected tail
    m = t >= (1 - args.tail) * t.max()
    print(f"n_edges={len(tsel)}  tail span={ (tsel.max()-tsel.min())*1e6:.2f}us")
    print(f"CKFB mean period = {T*1e9:.4f} ns  ->  f = {f/1e6:.4f} MHz  "
          f"(period std = {per.std()*1e12:.1f} ps, N={len(per)})")
    print(f"  vs 153.6M: err = {(f/153.6e6-1)*100:+.4f}%   "
          f"sensitivity 0.37MHz per nr-step (nr DOWN -> f UP) -> nr_step = {(f-153.6e6)/0.37e6:+.2f}")
    for k in ["VCTRL", "VREF", "KDTC", "VDCC", "RDCC", "VHOLD"]:
        if k in d:
            print(f"  {k}: last={d[k][m].mean():.4g}   final={d[k][-1]:.4g}")


if __name__ == "__main__":
    main()
