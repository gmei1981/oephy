#!/usr/bin/env python3
"""ref3 V1 waveform verdicts: psf-export key signals from each tb and check.
Usage: python3 tools/check_ref3_v1.py
"""
import re
import subprocess
from pathlib import Path

import numpy as np

V1 = Path(__file__).resolve().parent.parent / "sim" / "ref3" / "v1"
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


def bus(rawdir, prefix, n):
    cols = [get(rawdir, f"{prefix.upper()}{i}") for i in range(n)]
    ln = min(len(c) for c in cols)
    val = np.zeros(ln)
    for i, c in enumerate(cols):
        val += (c[:ln] > 0.4) * (1 << i)
    return val


def check(name, cond, detail):
    if cond:
        print(f"  PASS {name}: {detail}")
    else:
        print(f"  FAIL {name}: {detail}")
        FAIL.append(name)


def period(t, x, vth=0.4):
    e = np.where(np.diff((x > vth).astype(int)) > 0)[0]
    return np.diff(t[e]).mean() if len(e) > 2 else float("nan")


# --- dsm_fb mode0: ratio alternates 80/81, mean 80.5; q_err mean -0.25; sel 50% ---
d = V1 / "tb_dsmfb_m0" / "tb_dsmfb_m0.raw"
t = get(d, "time"); m = t > 50e-9
r = bus(d, "p", 13)
check("dsmfb_m0 ratio mean", abs(r[m].mean() - 80.5) < 0.05, f"mean={r[m].mean():.3f} (expect 80.5)")
check("dsmfb_m0 ratio range", (r[m].min() >= 80) and (r[m].max() <= 81),
      f"min={r[m].min():.0f} max={r[m].max():.0f} (expect 80..81)")
q = get(d, "QERR")
check("dsmfb_m0 q_err mean", abs(q[m].mean() + 0.25) < 0.05, f"QERR mean={q[m].mean():.3f} (expect -0.25)")
s = get(d, "SEL")
check("dsmfb_m0 sel duty", abs(s[m].mean() - 0.4) < 0.08, f"SEL mean={s[m].mean():.3f} (expect ~0.4)")

# --- dsm_fb mode1: mean 80.25, bounded 79..82 ---
d = V1 / "tb_dsmfb_m1" / "tb_dsmfb_m1.raw"
t = get(d, "time"); m = t > 50e-9
r = bus(d, "p", 13)
check("dsmfb_m1 ratio mean", abs(r[m].mean() - 80.25) < 0.05, f"mean={r[m].mean():.3f} (expect 80.25)")
check("dsmfb_m1 ratio range", (r[m].min() >= 79) and (r[m].max() <= 82),
      f"min={r[m].min():.0f} max={r[m].max():.0f} (expect 79..82)")

# --- mmd_ps: periods ---
for tag, exp in [("r80", 10e-9), ("r16", 2e-9), ("r255", 31.875e-9), ("sel", 10e-9)]:
    d = V1 / f"tb_mmd_{tag}" / f"tb_mmd_{tag}.raw"
    t = get(d, "time"); c = get(d, "CKFB")
    p = period(t, c)
    check(f"mmd_{tag} period", abs(p - exp) < 0.005 * exp,
          f"period={p * 1e9:.4f}ns (expect {exp * 1e9:g}ns)")

# --- tdc+pfd: phe (cycles) and tcode ---
for tag, field, arb in [("p100", 51, 0.8), ("p240", 118, 0.8), ("n100", 51, 0.0)]:
    d = V1 / f"tb_tdcpfd_{tag}" / f"tb_tdcpfd_{tag}.raw"
    t = get(d, "time"); m = t > 100e-9
    phe = get(d, "PHE"); tc = get(d, "TCODE"); ar = get(d, "ARB")
    sgn = 1.0 if tag != "n100" else -1.0
    exp_phe = sgn * field / 64.0
    check(f"tdcpfd_{tag} phe", abs(phe[m].mean() - exp_phe) < 2.0 / 64,
          f"phe={phe[m].mean():.4f} (expect {exp_phe:.4f})")
    exp_tc = (256 + field) if sgn > 0 else field
    check(f"tdcpfd_{tag} tcode", abs(tc[m].mean() - exp_tc) < 0.6,
          f"tcode={tc[m].mean():.1f} (expect {exp_tc})")
    check(f"tdcpfd_{tag} arb", abs(ar[m].mean() - arb) < 0.1,
          f"arb={ar[m].mean():.2f} (expect {arb})")

# --- fll: hit (window 1 = 513 CLK edges, ends at 5121.1ns -> 2561 CK16 edges
#     counted vs 2560 expected: err=+1 <= ftol -> locks at window 1) ---
d = V1 / "tb_fll_hit" / "tb_fll_hit.raw"
t = get(d, "time"); m = t > 10.5e-6
fq = get(d, "FQLK"); fc = get(d, "FCTRL")
check("fll_hit freq_lock", fq[m].mean() > 0.7, f"FQLK mean@>10.5u={fq[m].mean():.3f} (expect 0.8)")
check("fll_hit fctrl", abs(fc[m].mean() + 1.0 / 128) < 0.005,
      f"FCTRL={fc[m].mean():.4f} (expect {-1.0 / 128:.4f})")

# --- fll_dir: 502M tap -> fctrl negative ramp, never locks ---
d = V1 / "tb_fll_dir" / "tb_fll_dir.raw"
t = get(d, "time"); m = t > 6.8e-6
fc = get(d, "FCTRL"); fq = get(d, "FQLK")
check("fll_dir fctrl sign", (-0.2 < fc[m].mean() < -0.05),
      f"FCTRL={fc[m].mean():.4f} (expect ~-0.10..-0.15)")
check("fll_dir no lock", fq[m].mean() < 0.1, f"FQLK={fq[m].mean():.3f} (expect 0)")

# --- lpf: handoff staircase (afc 20 -> +5 -> pll integrate phe=+1) ---
d = V1 / "tb_lpf" / "tb_lpf.raw"
t = get(d, "time")
ab = bus(d, "ab", 9)
m = (t > 1.3e-6) & (t < 1.6e-6)
check("lpf fll phase ab=165", abs(ab[m].mean() - 165) < 0.5, f"AB={ab[m].mean():.1f} (expect 165)")
m = (t > 2.9e-6) & (t < 3.1e-6)
check("lpf pll phase ab~273", abs(ab[m].mean() - 273) < 3, f"AB={ab[m].mean():.1f} (expect ~273)")

# --- dsm_dco: frac 0.5 -> out alternates 8/9 ---
d = V1 / "tb_dsmdco" / "tb_dsmdco.raw"
t = get(d, "time"); m = t > 50e-9
f = bus(d, "f", 4)
check("dsmdco mean", abs(f[m].mean() - 8.5) < 0.15, f"F mean={f[m].mean():.3f} (expect 8.5)")
check("dsmdco range", (f[m].min() >= 8) and (f[m].max() <= 9),
      f"min={f[m].min():.0f} max={f[m].max():.0f} (expect 8..9)")

# --- afc6: hit holds 63 + done; slow parks 63; fast parks 0 ---
d = V1 / "tb_afc6_hit" / "tb_afc6_hit.raw"
t = get(d, "time"); m = t > 10.6e-6
ad = get(d, "AFC_DONE")
pb = bus(d, "p", 6)
check("afc6_hit done", ad[m].mean() > 0.7, f"AFC_DONE={ad[m].mean():.3f} (expect 0.8)")
check("afc6_hit code hold", abs(pb[m].mean() - 63) < 0.5, f"code={pb[m].mean():.1f} (expect 63)")
for tag, exp in [("slow", 63), ("fast", 0)]:
    d = V1 / f"tb_afc6_{tag}" / f"tb_afc6_{tag}.raw"
    t = get(d, "time"); m = t > 28e-6
    pb = bus(d, "p", 6)
    check(f"afc6_{tag} park", abs(pb[m].mean() - exp) < 0.5, f"code={pb[m].mean():.1f} (expect {exp})")

# --- cal_kdtc: +0.025/edge after edge-1 -> kdtc = 353.2 + 218*0.025 = 358.65 ---
d = V1 / "tb_calk" / "tb_calk.raw"
t = get(d, "time"); m = t > 2.1e-6
k = get(d, "KDBG")
check("calk kdtc", abs(k[m].mean() - 0.35865) < 0.003, f"KDBG={k[m].mean():.5f} (expect 0.35865)")

# --- cal_refdcc: 0.02/64 per edge, ~218 edges -> ~0.068 ---
d = V1 / "tb_calr" / "tb_calr.raw"
t = get(d, "time"); m = t > 2.1e-6
rc = get(d, "RCOEF")
check("calr coef ramp", abs(abs(rc[m].mean()) - 0.068) < 0.012,
      f"|RCOEF|={abs(rc[m].mean()):.4f} (expect ~0.068)")

# --- cal_dcodcc: +0.005 per 40n -> 55 periods -> 0.275 ---
d = V1 / "tb_cald" / "tb_cald.raw"
t = get(d, "time"); m = t > 2.1e-6
dd = get(d, "DDBG")
check("cald coef ramp", abs(dd[m].mean() - 0.275) < 0.04, f"DDBG={dd[m].mean():.4f} (expect ~0.275)")

# --- lockdet: lock @~2.57us, unlock @~5.57us ---
d = V1 / "tb_lockdet" / "tb_lockdet.raw"
t = get(d, "time"); pl = get(d, "PHLK")
for lo, hi, exp, lbl in [(2.7e-6, 2.95e-6, 0.8, "locked"),
                         (3.2e-6, 5.5e-6, 0.8, "hold"),
                         (5.8e-6, 6.4e-6, 0.0, "unlocked")]:
    m = (t > lo) & (t < hi)
    check(f"lockdet {lbl}", abs(pl[m].mean() - exp) < 0.1, f"PHLK={pl[m].mean():.3f} (expect {exp})")

# --- fsm: full trajectory (state 1 only spans 51-201n; 5 spans 1201-1211n) ---
d = V1 / "tb_fsm" / "tb_fsm.raw"
t = get(d, "time"); fs = get(d, "FSTATE")
for lo, hi, exp in [(0.06e-6, 0.19e-6, 1), (0.25e-6, 0.45e-6, 2), (0.55e-6, 0.79e-6, 3),
                    (0.85e-6, 1.19e-6, 4), (1.2055e-6, 1.2105e-6, 5), (1.3e-6, 1.45e-6, 3)]:
    m = (t > lo) & (t < hi)
    check(f"fsm state@{lo*1e6:.3f}u", abs(fs[m].mean() - exp) < 0.1,
          f"FSTATE={fs[m].mean():.2f} (expect {exp})")

# --- dac9b: code 384 -> 0.375V ---
d = V1 / "tb_dac9b" / "tb_dac9b.raw"
t = get(d, "time"); m = t > 20e-9
o = get(d, "OUT")
check("dac9b out", abs(o[m].mean() - 0.375) < 0.005, f"OUT={o[m].mean():.4f} (expect 0.375)")

print(f"\n{'ALL PASS' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")
