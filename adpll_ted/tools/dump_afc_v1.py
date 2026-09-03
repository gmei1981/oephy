#!/usr/bin/env python3
"""Dump AFC window-by-window trajectory: cnt at each window end + code evolution.
Usage: python3 tools/dump_afc_v1.py [tb_afc_low|tb_afc_hit|tb_afc_high]
"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

V1 = Path(__file__).resolve().parent.parent / "sim" / "ssbb" / "v1"


def get(rawdir, sig):
    f = next(Path(rawdir).glob("*.tran.tran"))
    r = subprocess.run(["psf", "-i", str(f), "-s", "-t", sig, "-f", "%.9e"],
                       capture_output=True, text=True)
    body = r.stdout.split("VALUE", 1)[1]
    v = []
    for l in body.split("\n"):
        m = re.match(r'^"([^"]+)"\s+([0-9.eE+-]+)', l.strip())
        if m and m.group(1) == sig:
            v.append(float(m.group(2)))
    return np.asarray(v)


def dump(tag):
    raw = V1 / tag / f"{tag}.raw"
    t = get(raw, "time")
    cnt = get(raw, "CNTOUT")
    ad = get(raw, "AFC_DONE")
    code_bits = []
    for i in range(7):
        code_bits.append(get(raw, f"A{i}"))
    n = min(len(t), len(cnt))
    # sample state at each REF window boundary (every 170ns: 16 periods + eval edge)
    print(f"== {tag} ==")
    print(f"time range: {t[-1]*1e9:.0f}ns, len(t)={len(t)}, len(cnt)={len(cnt)}")
    print(f"{'t(ns)':>8} {'cnt':>5} {'code':>5} {'done':>4}")
    last_code = None
    shown = 0
    for k in range(n):
        code = 0
        ok = True
        for i in range(7):
            if len(code_bits[i]) != len(t):
                ok = False
                break
            if code_bits[i][k] > 0.5:
                code += 1 << i
        if not ok:
            break
        if code != last_code or (k > 0 and t[k] - t[k-1] > 5e-9 and t[k] % 1e-7 < 2e-9):
            c = int(round(cnt[k] / 0.01))
            print(f"{t[k]*1e9:8.1f} {c:5d} {code:5d} {int(ad[k] > 0.5):4d}")
            last_code = code
            shown += 1
    # window-end cnt values: local maxima of CNTOUT before each reset
    print("window-end cnt sequence (local maxima):")
    cnts = []
    for k in range(1, n - 1):
        if cnt[k] >= cnt[k-1] and cnt[k] > cnt[k+1] and cnt[k] > 2.0:
            cnts.append(int(round(cnt[k] / 0.01)))
    print(cnts[:30])


if __name__ == "__main__":
    tags = sys.argv[1:] or ["tb_afc_low", "tb_afc_hit", "tb_afc_high"]
    for tag in tags:
        dump(tag)
