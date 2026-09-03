#!/usr/bin/env python3
"""V1 waveform verdicts: psf-export key signals from each tb and check behavior.
Usage: python3 tools/check_ssbb_v1.py
"""
import re
import subprocess
from pathlib import Path

import numpy as np

V1 = Path(__file__).resolve().parent.parent / "sim" / "ssbb" / "v1"
FAIL = []


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


def check(name, cond, detail):
    if cond:
        print(f"  PASS {name}: {detail}")
    else:
        print(f"  FAIL {name}: {detail}")
        FAIL.append(name)


# --- bbpd aligned ---
t = get(V1 / "tb_bbpd_align" / "tb_bbpd_align.raw", "time")
dz = get(V1 / "tb_bbpd_align" / "tb_bbpd_align.raw", "BB_DZ")
bb = get(V1 / "tb_bbpd_align" / "tb_bbpd_align.raw", "BB")
m = t > 20e-9
check("bbpd_align dz duty", dz[m].mean() < 0.15, f"BB_DZ mean={dz[m].mean():.3f} (expect ~0)")
check("bbpd_align bb level", abs(bb[m].mean() - 0.8) < 0.05, f"BB mean={bb[m].mean():.3f} (expect 0.8)")

# --- bbpd late (300p: edge early by 200p -> bb=0, dz off) ---
t = get(V1 / "tb_bbpd_late" / "tb_bbpd_late.raw", "time")
dz = get(V1 / "tb_bbpd_late" / "tb_bbpd_late.raw", "BB_DZ")
bb = get(V1 / "tb_bbpd_late" / "tb_bbpd_late.raw", "BB")
m = t > 20e-9
check("bbpd_late dz off", dz[m].mean() > 0.75, f"BB_DZ mean={dz[m].mean():.3f} (expect ~0.8)")
check("bbpd_late bb level", bb[m].mean() < 0.05, f"BB mean={bb[m].mean():.3f} (expect 0)")

# --- dlf: CODE9 rise ~640ns (acc=32768+8n crosses 33280 at n=64), fall after 1us ---
t = get(V1 / "tb_dlf" / "tb_dlf.raw", "time")
c9 = get(V1 / "tb_dlf" / "tb_dlf.raw", "C9")
m = (t > 700e-9) & (t < 950e-9)
check("dlf code9 rise", c9[m].mean() > 0.7, f"C9 mean@700-950n={c9[m].mean():.3f} (expect 0.8)")
m = (t > 1.7e-6) & (t < 1.95e-6)
check("dlf code9 fall", c9[m].mean() < 0.1, f"C9 mean@1.7-1.95u={c9[m].mean():.3f} (expect 0)")

# --- dac staircase ---
t = get(V1 / "tb_dac" / "tb_dac.raw", "time")
o = get(V1 / "tb_dac" / "tb_dac.raw", "OUT")
for lo, hi, exp, lbl in [(30e-9, 90e-9, 0.0, "0-100n=0V"),
                         (120e-9, 190e-9, 0.332, "100-200n=0.332V"),
                         (220e-9, 290e-9, 0.496, "200-300n=0.496V")]:
    m = (t > lo) & (t < hi)
    v = o[m].mean()
    check(f"dac {lbl}", abs(v - exp) < 0.02, f"OUT mean={v:.3f} (expect {exp})")

# --- afc: with skipwins=2 + re-arm, high walks to the rail (0, was 1 when
# step exhaustion parked arbitrarily); low parks at 127; hit holds 64 + done ---
for tag, exp, lo in [("tb_afc_high", 0, 1.4e-6), ("tb_afc_low", 127, 1.4e-6)]:
    t = get(V1 / tag / f"{tag}.raw", "time")
    m = t > lo
    cv = 0
    for i in range(7):
        a = get(V1 / tag / f"{tag}.raw", f"A{i}")
        if a[m].mean() > 0.5:
            cv += 1 << i
    check(f"{tag} final code", cv == exp, f"code={cv} (expect {exp})")

t = get(V1 / "tb_afc_hit" / "tb_afc_hit.raw", "time")
ad = get(V1 / "tb_afc_hit" / "tb_afc_hit.raw", "AFC_DONE")
m = t > 1.2e-6
check("afc_hit done", ad[m].mean() > 0.7, f"AFC_DONE mean@>1.2u={ad[m].mean():.3f} (expect 0.8)")
# code should hold 64
cv = 0
for i in range(7):
    a = get(V1 / "tb_afc_hit" / "tb_afc_hit.raw", f"A{i}")
    if a[t > 1.2e-6].mean() > 0.5:
        cv += 1 << i
check("afc_hit code hold", cv == 64, f"code={cv} (expect 64)")

# --- div4: OUT period 500p ---
t = get(V1 / "tb_div4" / "tb_div4.raw", "time")
o = get(V1 / "tb_div4" / "tb_div4.raw", "OUT")
e = np.where(np.diff((o > 0.4).astype(int)) > 0)[0]
per = np.diff(t[e]).mean()
check("div4 period", abs(per - 500e-12) < 1e-12, f"period={per*1e12:.2f}ps (expect 500ps)")

# --- gs: kp 8 -> 4 -> 2 ---
t = get(V1 / "tb_gs" / "tb_gs.raw", "time")
kp = get(V1 / "tb_gs" / "tb_gs.raw", "KP")
m = (t > 250e-9) & (t < 300e-9)
check("gs final kp", abs(kp[m].mean() - 2.0) < 0.1, f"KP@250-300n={kp[m].mean():.2f} (expect 2)")

# --- frac_acc: CODE9 period 20n ---
t = get(V1 / "tb_frac_acc" / "tb_frac_acc.raw", "time")
c9 = get(V1 / "tb_frac_acc" / "tb_frac_acc.raw", "C9")
e = np.where(np.diff((c9 > 0.4).astype(int)) > 0)[0]
per = np.diff(t[e]).mean() if len(e) > 2 else float("nan")
check("frac_acc code9 period", abs(per - 20e-9) < 1e-9, f"period={per*1e9:.2f}ns (expect 20ns)")

# --- dtc: c0=1, c5=0, CK_OUT toggles at 100M ---
t = get(V1 / "tb_dtc" / "tb_dtc.raw", "time")
for sig, exp, lbl in [("Xdtc.c0", 0.8, "c0 on"), ("Xdtc.c5", 0.0, "c5 off")]:
    try:
        v = get(V1 / "tb_dtc" / "tb_dtc.raw", sig)
        m = t > 30e-9
        check(f"dtc {lbl}", abs(v[m].mean() - exp) < 0.1, f"{sig} mean={v[m].mean():.3f} (expect {exp})")
    except Exception as ex:
        check(f"dtc {lbl}", False, f"probe failed: {ex}")
o = get(V1 / "tb_dtc" / "tb_dtc.raw", "CK_OUT")
e = np.where(np.diff((o > 0.4).astype(int)) > 0)[0]
per = np.diff(t[e]).mean()
check("dtc ck_out period", abs(per - 10e-9) < 0.2e-9, f"period={per*1e9:.3f}ns (expect 10ns)")

print(f"\n{'ALL PASS' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")
