#!/usr/bin/env python3
"""V4/V5 full closed-loop verdicts (integer 100M/8G, fractional 8.05G).
Lock criteria (plan §5): fVCO target +-0.1%, BB mean ~0, BB_DZ sustained zero,
AFC done, coarse code in expected range, GS gear progression in longer runs.
Usage: python3 tools/check_ssbb_v4.py [rawdir] [lockwin_us] [ftarget_GHz] [afc_lo] [afc_hi]
       defaults: 0.9 8.0 88 104   (fractional: ... 8.05 109 125)
"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def get(d, sig):
    p = Path(d)
    hits = sorted(p.glob("*.tran.tran")) + sorted(p.glob("*.raw/*.tran.tran"))
    f = hits[0]
    r = subprocess.run(["psf", "-i", str(f), "-s", "-t", sig, "-f", "%.9e"],
                       capture_output=True, text=True)
    body = r.stdout.split("VALUE", 1)[1]
    v = []
    for l in body.split("\n"):
        m = re.match(r'^"([^"]+)"\s+([0-9.eE+-]+)', l.strip())
        if m and m.group(1) == sig:
            v.append(float(m.group(2)))
    return np.asarray(v)


def freq_from_edges(t, v, thr, tmin, tmax):
    idx = np.where((t > tmin) & (t < tmax))[0]
    above = v > thr
    edges = []
    for k in idx[1:]:
        if above[k] and not above[k - 1]:
            f = (thr - v[k - 1]) / (v[k] - v[k - 1])
            edges.append(t[k - 1] + f * (t[k] - t[k - 1]))
    if len(edges) < 30:
        return None, len(edges)
    return 1.0 / np.diff(edges).mean(), len(edges)


def main():
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if d is None:
        cands = sorted((ROOT / "sim" / "out").glob("*ssbb*"), key=lambda p: p.stat().st_mtime)
        if not cands:
            print("no sim/out/*ssbb* raw dir; pass one explicitly")
            return
        d = cands[-1]
    lock_start_us = float(sys.argv[2]) if len(sys.argv) > 2 else 0.9
    ftarget = float(sys.argv[3]) * 1e9 if len(sys.argv) > 3 else 8.0e9
    afc_lo = int(sys.argv[4]) if len(sys.argv) > 4 else 88
    afc_hi = int(sys.argv[5]) if len(sys.argv) > 5 else 104

    t = get(d, "time")
    tend = t[-1]
    print(f"raw={d}  sim end={tend*1e6:.2f}us  points={len(t)}")
    FAIL = []

    def check(name, cond, detail):
        print(f"  {'PASS' if cond else 'FAIL'} {name}: {detail}")
        if not cond:
            FAIL.append(name)

    # VDDC
    vd = get(d, "VDDC")
    n = min(len(t), len(vd)); m = t[:n] > 0.5e-6
    check("VDDC health", 0.48 < vd[:n][m].mean() < 0.56,
          f"mean={vd[:n][m].mean():.3f}V")

    # AFC
    bits = [get(d, f"A{i}") for i in range(7)]
    n = min(len(t), *[len(b) for b in bits])
    code = np.zeros(n, dtype=int)
    for i, b in enumerate(bits):
        code += (b[:n] > 0.5) * (1 << i)
    ad = get(d, "AFC_DONE"); nad = min(len(t), len(ad))
    done_t = None
    idx = np.where((ad[:nad][1:] > 0.5) & (ad[:nad][:-1] <= 0.5))[0]
    if len(idx):
        done_t = t[idx[0]]
    cE = int(np.median(code[t[:n] > tend - 0.2e-6]))
    check("afc code in range", afc_lo <= cE <= afc_hi,
          f"end code={cE} (expect {afc_lo}-{afc_hi})")
    check("afc done rises", done_t is not None,
          f"t={f'{done_t*1e6:.2f}us' if done_t is not None else 'never'} (expect ~0.8u)")

    # fVCO final
    dv = get(d, "DIV4")
    f4, ne = freq_from_edges(t, dv, 0.4, tend - 0.3e-6, tend)
    f = f4 * 4 if f4 else None
    check("fVCO target+-0.1%", f is not None and abs(f - ftarget) < ftarget * 1e-3,
          f"fVCO={f/1e9 if f else None:.5f}G edges={ne} target={ftarget/1e9}G")

    # BB lock behavior in lock window (after AFC done). Per-cycle sampling at
    # the DLF consumption point (just before each REF rising edge): BB is a
    # held level, so a raw time-average is skewed by unequal hold durations.
    # bb_v = +1/-1 as the DLF sees it.
    if done_t:
        ls = max(done_t + 0.1e-6, lock_start_us * 1e-6)
        bb = get(d, "BB"); dz = get(d, "BB_DZ")
        nb = min(len(t), len(bb), len(dz))
        t2, bb2, dz2 = t[:nb], bb[:nb], dz[:nb]
        k_lo = int(np.ceil(ls / 1e-8)) + 1
        k_hi = int(tend / 1e-8) - 1
        bs, zs = [], []
        for k in range(k_lo, k_hi):
            i = np.searchsorted(t2, k * 1e-8 - 1e-9)
            if i < nb - 1:
                bs.append(1.0 if bb2[i] > 0.4 else -1.0)
                zs.append(dz2[i] < 0.4)
        bmean = float(np.mean(bs)) if bs else 0.0
        dzfrac = float(np.mean(zs)) if zs else 0.0
        check("bb_v per-cycle mean (|.|<=0.35)", abs(bmean) <= 0.35,
              f"bb_v mean={bmean:+.3f} over [{k_lo*1e-8*1e6:.2f},{k_hi*1e-8*1e6:.2f}]us n={len(bs)}"
              " (small + = pulling residual)")
        check("bb_dz engaged >20%", dzfrac > 0.2,
              f"dz-low per-cycle fraction={dzfrac:.2f}")
    # VC1/VC2
    vc1 = get(d, "VC1"); vc2 = get(d, "VC2")
    n1 = min(len(t), len(vc1)); m1 = t[:n1] > tend - 0.2e-6
    check("VC1 ~code/256", abs(vc1[:n1][m1].mean() - cE / 256.0) < 0.01,
          f"VC1={vc1[:n1][m1].mean():.4f} vs {cE/256:.4f}")
    print(f"  info: VC2 end={vc2[len(vc2)-1] if len(vc2) else 'n/a'}V")

    # GS state
    kp = get(d, "KP"); ki = get(d, "KI")
    if len(kp):
        print(f"  info: KP end={kp[-1]} KI end={ki[-1]} (8/1=gear0, 4/0.5=gear1)")

    # DLF code end value: only C9/C15 are in the v4 save list — report those;
    # full 16-bit readback needs the A-bits (coarse) which are saved separately
    c9 = get(d, "C9"); c15 = get(d, "C15")
    if len(c9) and len(c15):
        nn = min(len(t), len(c9), len(c15))
        mE = t[:nn] > tend - 0.2e-6
        print(f"  info: C9(fine MSB)={c9[:nn][mE].mean():.2f} "
              f"C15(coarse MSB)={c15[:nn][mE].mean():.2f}")

    print(f"\n{'ALL PASS' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")


if __name__ == "__main__":
    main()
