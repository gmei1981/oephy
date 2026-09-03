#!/usr/bin/env python3
"""ref3 V2 open-loop calibration verdicts.
Usage: python3 tools/check_ref3_v2.py
"""
import re
import subprocess
from pathlib import Path

import numpy as np

V2 = Path(__file__).resolve().parent.parent / "sim" / "ref3" / "v2"
FAIL = []
FBIN = 31.25e-12 / 16          # 1.953125p (cbin=TCKV/4, fbin=cbin/16)
TCKV = 125e-12


def get(rawdir, sig):
    p = Path(rawdir)
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


def check(name, cond, detail):
    if cond:
        print(f"  PASS {name}: {detail}")
    else:
        print(f"  FAIL {name}: {detail}")
        FAIL.append(name)


def crossings(t, x, vth=0.4):
    above = x > vth
    out = []
    for k in range(1, len(t)):
        if above[k] and not above[k - 1]:
            f = (vth - x[k - 1]) / (x[k] - x[k - 1])
            out.append(t[k - 1] + f * (t[k] - t[k - 1]))
    return np.asarray(out)


def sample_at(t, y, tq):
    i = np.clip(np.searchsorted(t, tq), 0, len(t) - 1)
    return y[i]


# ============ V2-1: TDC transfer sweep ============
d = V2 / "tdc_sweep"
t = get(d, "time"); phe = get(d, "PHE"); tc = get(d, "TCODE")
ds, mes, exp = [], [], []
for k in range(20):
    dk = 10e-12 + 25e-12 * k
    tau = 2e-9 + dk + 10e-9 * k
    dtw = dk - 4e-12                    # CKR cross +5p, CKFB cross +1p
    if dtw > 250e-12:
        dtw -= 500e-12
    field = int(np.round(abs(dtw) / FBIN))
    sgn = 1.0 if dtw >= 0 else -1.0
    p = sample_at(t, phe, tau + 30e-12)  # after the CKFB edge settles
    ds.append(dtw / 1e-12); mes.append(p); exp.append(sgn * field / 64.0)
ds = np.asarray(ds); mes = np.asarray(mes); exp = np.asarray(exp)
ok = np.abs(mes - exp) < 2.0 / 64
check("tdc_sweep pointwise", ok.sum() >= 18, f"{ok.sum()}/20 within 2 LSB")
# slope from the monotonic middle region (exclude wrap-adjacent points)
mid = np.abs(ds) < 200
A = np.vstack([ds[mid], np.ones(mid.sum())]).T
slope, _ = np.linalg.lstsq(A, mes[mid], rcond=None)[0]
exp_slope = 1e-12 / FBIN / 64                 # phe per ps (1ps = 0.512 LSB /64)
check("tdc_sweep slope", abs(slope - exp_slope) / exp_slope < 0.05,
      f"slope={slope:.5f}/ps (expect {exp_slope:.5f}, bin={1/slope:.3f}ps)")
check("tdc_sweep fold", (mes[2] > 0) and (mes[17] < 0),
      f"phe(d=56p)={mes[2]:+.3f}>0 phe(d=431p)={mes[17]:+.3f}<0 (fold at +250p)")

# ============ V2-2: mmd sel half-period phase shift ============
d = V2 / "mmd_selphase"
t = get(d, "time"); c = get(d, "CKFB"); v = get(d, "VCO"); sel = get(d, "SEL")
ce = crossings(t, c)
ve = crossings(t, v)
ph = []
for e in ce:
    j = np.searchsorted(ve, e)
    if 0 < j < len(ve):
        ph.append((e - ve[j - 1]) % TCKV)
ph = np.asarray(ph)
te = ce[:len(ph)]
m0 = te < 0.8e-6
m1 = te > 1.2e-6
p0 = ph[m0].mean() if m0.sum() else float("nan")
p1 = ph[m1].mean() if m1.sum() else float("nan")
dph = (p1 - p0) % TCKV
check("selphase shift", abs(dph - TCKV / 2) < 8e-12,
      f"phase {p0*1e12:.2f}p -> {p1*1e12:.2f}p, shift {dph*1e12:.2f}p (expect 62.5p)")
check("selphase sel level", sel[-1] > 0.7, f"SEL final={sel[-1]:.2f}")

# ============ V2-3a: static chain phe vs CKR delay ============
# NOTE: the mmd CKFB rising edge carries a fixed ~+20p offset vs the VCO edge
# (toggle + tt/2), so absolute phe has that offset; the discriminators are
# the fold sides and the same-side 100p step (d 0.8->0.9 = +0.8 phe).
phe_d = {}
for tag in ("d0p7n", "d0p8n", "d0p9n"):
    d = V2 / f"chain80_{tag}"
    t = get(d, "time"); p = get(d, "PHE")
    m = t > 120e-9
    phe_d[tag] = p[m].mean()
d89 = phe_d["d0p8n"] - phe_d["d0p9n"]
check("chain fold sides", (phe_d["d0p7n"] < -1.0) and (phe_d["d0p8n"] > 1.0),
      f"phe@0.7n={phe_d['d0p7n']:+.3f}<0 phe@0.8n={phe_d['d0p8n']:+.3f}>0 (dtw -200p/+200p)")
check("chain delay step", abs(d89 - 0.8) < 0.15,
      f"d(0.8-0.9)={d89:+.3f} (CKR +100p -> phe -{d89:.2f}, expect ~-0.8)")
off = phe_d["d0p8n"] * TCKV - 200e-12
print(f"  [chain] CKFB edge offset vs VCO edge ~{off*1e12:+.1f}p (info)")

# ============ V2-3b: frequency-error ramp (fold jump ~3, window = 4 phe) ====
for tag, fexp in (("s79", 7.9e9), ("s81", 8.1e9)):
    d = V2 / f"chain80_{tag}"
    t = get(d, "time"); p = get(d, "PHE")
    m = t > 60e-9
    tt, pp = t[m], p[m]
    dp = np.diff(pp)
    dp[dp < -2.5] += 4.0        # fold at dtw=+-250p = +-2 phe (500p window = 4)
    dp[dp > 2.5] -= 4.0
    uw = np.concatenate([[pp[0]], pp[0] + np.cumsum(dp)])
    A = np.vstack([tt, np.ones(len(tt))]).T
    sl, _ = np.linalg.lstsq(A, uw, rcond=None)[0]
    tckfb = 80.0 / fexp
    exp_sl = (tckfb - 10e-9) * 100e6 / TCKV    # phe per second
    check(f"chain {tag} ramp", abs(sl - exp_sl) / abs(exp_sl) < 0.15,
          f"slope={sl*1e9:+.4f}/ns (expect {exp_sl*1e9:+.4f}/ns, {fexp/1e9:g}G slow/fast)")

# ============ V2-4: KVCO_A (Abank code -> fVCO) ============
rows = []
for code in (0, 128, 256, 384, 511):
    d = V2 / f"kvco_ab_{code}"
    t = get(d, "time"); v = get(d, "OUTP")
    e = crossings(t[t > 70e-9], v[t > 70e-9])
    f = 1.0 / np.diff(e).mean() if len(e) > 20 else float("nan")
    rows.append((code, code * 0.5 / 512, f))
    print(f"  [kvco] Abank={code:3d} VC1={code*0.5/512:.3f}V f={f/1e9:.4f} GHz")
codes = np.array([r[0] for r in rows], dtype=float)
fs = np.array([r[2] for r in rows])
A = np.vstack([codes, np.ones(len(codes))]).T
kv, f0 = np.linalg.lstsq(A, fs, rcond=None)[0]      # Hz per Abank LSB
mono = np.all(np.diff(fs) > 0)
check("kvco monotonic", mono, "fVCO increasing with Abank")
check("kvco_A value", abs(kv - 621e6 * 0.5 / 512) / (621e6 * 0.5 / 512) < 0.15,
      f"KVCO_A={kv/1e6:.3f} MHz/LSB (expect ~{621e6*0.5/512/1e6:.3f} from 621MHz/V)")
code80 = (8.0e9 - f0) / kv
print(f"  [kvco] 8.0G at Abank~{code80:.0f} (f0={f0/1e9:.4f}G)")
check("kvco 8G reachable", 0 < code80 < 512, f"code for 8.0G = {code80:.0f} in 0..511")

print(f"\n{'ALL PASS' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")
