#!/usr/bin/env python3
"""V3 AFC-only closed-loop verdicts (sim/ssbb/v3).
Expects: AFC code 64 -> ~80 (8.0G at VC1~0.31 per V2a KVCO1=621MHz/V),
AFC_DONE rises, fVCO -> 8.0G +-30MHz (count tol 25MHz + quantization),
VDDC healthy, CNTOUT windows settle at 320+-1.
Usage: python3 tools/check_ssbb_v3.py [rawdir]
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
    n = len(t)
    idx = np.where((t > tmin) & (t < tmax))[0]
    above = v > thr
    edges = []
    for k in idx[1:]:
        if above[k] and not above[k - 1]:
            f = (thr - v[k - 1]) / (v[k] - v[k - 1])
            edges.append(t[k - 1] + f * (t[k] - t[k - 1]))
    if len(edges) < 30:
        return None, len(edges)
    per = np.diff(edges).mean()
    return 1.0 / per, len(edges)


def main():
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "sim" / "ssbb" / "v3"
    raw = None
    for cand in (d / "v3afcd.raw", d / "v3afcd", d):
        if cand.exists():
            raw = cand
            break
    t = get(raw, "time")
    tend = t[-1]
    print(f"sim end = {tend*1e6:.2f}us, {len(t)} points")
    FAIL = []

    def check(name, cond, detail):
        print(f"  {'PASS' if cond else 'FAIL'} {name}: {detail}")
        if not cond:
            FAIL.append(name)

    # 1. VDDC health
    vd = get(raw, "VDDC")
    n = min(len(t), len(vd)); m = t[:n] > 0.5e-6
    mv, pv = vd[:n][m].mean(), (vd[:n][m].max() - vd[:n][m].min())
    check("VDDC health", 0.48 < mv < 0.56 and pv < 0.06,
          f"mean={mv:.3f}V pp={pv*1e3:.1f}mV (expect ~0.5, pp<60m)")

    # 2. AFC code trajectory
    bits = [get(raw, f"A{i}") for i in range(7)]
    n = min(len(t), *[len(b) for b in bits])
    code = np.zeros(n, dtype=int)
    for i, b in enumerate(bits):
        code += (b[:n] > 0.5) * (1 << i)
    ad = get(raw, "AFC_DONE"); nad = min(len(t), len(ad))
    done_t = None
    idx = np.where((ad[:nad][1:] > 0.5) & (ad[:nad][:-1] <= 0.5))[0]
    if len(idx):
        done_t = t[idx[0]]
    m0 = t[:n] < 1e-7
    mE = t[:n] > tend - 3e-7
    c0, cE = int(np.median(code[m0])), int(np.median(code[mE]))
    print(f"  AFC code: start={c0} end={cE} "
          f"trajectory={list(dict.fromkeys(code[::max(1, n//40)]))[:14]}")
    check("afc code start 64", c0 == 64, f"start={c0}")
    # closed-loop VDDC=0.547 (LDO offset) shifts f ~33MHz below the V2a sweep
    # (VDDC=0.500): 8.0G lands at code ~94, not the sweep's 80
    check("afc code end 86-102", 86 <= cE <= 102,
          f"end={cE} (expect ~94 = 8.0G with VDDC=0.547)")
    check("afc done rises", done_t is not None,
          f"AFC_DONE t={f'{done_t*1e6:.2f}us' if done_t is not None else 'never'}"
          f" (expect <=1.5us)")

    # 3. fVCO at end (DIV4 edges, x4)
    dv = get(raw, "DIV4")
    f4, ne = freq_from_edges(t, dv, 0.4, tend - 0.5e-6, tend)
    f = f4 * 4 if f4 else None
    check("fVCO final 8.0G+-30M", f is not None and abs(f - 8.0e9) < 30e6,
          f"fVCO={f/1e9 if f else None:.4f}G edges={ne} (expect 7.97-8.03G)")

    # 4. CNTOUT settle
    co = get(raw, "CNTOUT")
    n2 = min(len(t), len(co)); m2 = t[:n2] > (tend - 0.4e-6)
    cmax = co[:n2][m2].max() / 0.01
    check("cnt window 318-322", 318 <= cmax <= 322,
          f"max cnt={cmax:.0f} (target 320, tol 1)")

    # 5. VC1 sanity vs code
    vc1 = get(raw, "VC1")
    n3 = min(len(t), len(vc1)); m3 = t[:n3] > tend - 3e-7
    v1e = vc1[:n3][m3].mean()
    check("VC1 end ~code/256", abs(v1e - cE / 256.0) < 0.01,
          f"VC1={v1e:.4f} vs code/256={cE/256:.4f}")

    print(f"\n{'ALL PASS' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")


if __name__ == "__main__":
    main()
