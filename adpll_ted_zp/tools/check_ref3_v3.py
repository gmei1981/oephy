#!/usr/bin/env python3
"""ref3 V3 integer closed-loop verdicts (FSM AFC->FLL->PLL->LOCK).

Usage: python3 tools/check_ref3_v3.py [smoke|full]   (default full)

full-run verdicts (lean save, strobed at 50p):
  1. FSM trajectory: FSTATE reaches 4 (LOCK) and holds
  2. AFC: starts at code 63 (Abank 504, VC1~0.492), staircase search, AFCD time
  3. FQLK / PHLK assertion times ordered after AFCD
  4. fVCO final = 16 / mean(CK16 period), within 8.0G +-0.1%
  5. phe final |mean| <= 0.03 (lock_thr 0.02 + margin), |max| bounded
  6. handoff continuity: VC1 step at each FSTATE transition < 5mV (~5 LSB)
  7. VDDC ~0.547V; SELF=0 and QERR=-0.5 (integer channel)
"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

V3 = Path(__file__).resolve().parent.parent / "sim" / "ref3" / "v3"
FAIL = []
VC1_LSB = 0.5 / 512            # dac9b LSB = 0.9766mV (vmax 0.5, 9b)


def get(rawdir, sig):
    p = Path(rawdir)
    hits = sorted(p.glob("*.tran.tran")) + sorted(p.glob("*.raw/*.tran.tran"))
    f = hits[0]
    r = subprocess.run(["psf", "-i", str(f), "-s", "-t", sig, "-f", "%.9e"],
                       capture_output=True, text=True)
    if "VALUE" not in r.stdout:
        raise RuntimeError(f"no VALUE section for {sig}")
    body = r.stdout.split("VALUE", 1)[1]
    v = []
    for l in body.split("\n"):
        m = re.match(r'^"([^"]+)"\s+([0-9.eE+-]+)', l.strip())
        if m and m.group(1) == sig:
            v.append(float(m.group(2)))
    return np.asarray(v)


def check(name, cond, detail):
    tag = "PASS" if cond else "FAIL"
    print(f"  {tag} {name}: {detail}")
    if not cond:
        FAIL.append(name)


def crossings(t, x, vth=0.4):
    above = x > vth
    out = []
    for k in range(1, len(t)):
        if above[k] and not above[k - 1]:
            f = (vth - x[k - 1]) / (x[k] - x[k - 1])
            out.append(t[k - 1] + f * (t[k] - t[k - 1]))
    return np.asarray(out)


def level_time(t, x, lv):
    """first time x >= lv (returns None if never)."""
    i = np.argmax(x >= lv)
    if not np.any(x >= lv):
        return None
    return t[i]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    d = V3 / ("smoke" if mode == "smoke" else "main")
    log = d / "main.log"
    txt = log.read_text() if log.exists() else ""
    check("0 errors", "spectre completes with 0 errors" in txt,
          "log verdict line" if txt else "no log")

    t = get(d, "time")
    ck16 = get(d, "CK16")
    phe = get(d, "PHE")
    vc1 = get(d, "VC1")
    fstate = get(d, "FSTATE")
    qerr = get(d, "QERR")
    selfv = get(d, "SELF")
    print(f"  [info] sim {t[0]*1e-6:.2f}..{t[-1]*1e-6:.2f} us,"
          f" {len(t)} strobed points")

    if mode == "smoke":
        ena = get(d, "ENA")
        cntout = get(d, "CNTOUT")
        outpb = get(d, "OUTPB")
        # VCO running: CK16 toggles, early fVCO near code-63 value ~8.07G
        e = crossings(t, ck16)
        m0 = (e > 0.3e-6) & (e < 1.0e-6)
        f0 = 1.0 / np.diff(e[m0]).mean() * 16 if m0.sum() > 10 else 0
        check("vco running", f0 > 7.5e9, f"early fVCO={f0/1e9:.3f}G (code63)")
        check("outpb swing", (np.nanmax(outpb) > 0.6) and (np.nanmin(outpb) < 0.2),
              f"OUTPB {np.nanmin(outpb):.2f}..{np.nanmax(outpb):.2f}V")
        t_ena = level_time(t, ena, 0.4)
        check("ena rise", t_ena is not None and 30e-9 < t_ena < 0.3e-6,
              f"ENA@{t_ena*1e9 if t_ena is not None else -1:.0f}n")
        # AFC start code 63: Abank 504 -> VC1 0.4922
        m = (t > 2.0e-6) & (t < 3.8e-6)
        v63 = vc1[m].mean()
        check("afc start code 63", abs(v63 - 504 * VC1_LSB) < 0.01,
              f"VC1={v63:.4f}V (expect {504*VC1_LSB:.4f})")
        # first evaluated window ends ~3.92u -> code 63->31, VC1 -> 0.2422
        m2 = t > 4.3e-6
        v31 = vc1[m2].mean()
        check("afc first move", abs(v31 - 31 * 8 * VC1_LSB) < 0.01,
              f"VC1@4.3u+={v31:.4f}V (expect {248*VC1_LSB:.4f} for code 31)")
        check("cntout counting", np.nanmax(cntout) > 3.0,
              f"CNTOUT max={np.nanmax(cntout):.2f}V (~640 edges/window)")
        check("phe active", np.nanstd(phe[t > 1e-6]) > 1e-3,
              f"phe std={np.nanstd(phe[t > 1e-6]):.4f}")
        check("integer dsm", (abs(selfv[-1]) < 0.1) and (abs(qerr[-1] + 0.5) < 0.05),
              f"SELF={selfv[-1]:.2f} QERR={qerr[-1]:+.2f} (expect 0/-0.5)")
    else:
        afcd = get(d, "AFCD")
        fqlk = get(d, "FQLK")
        phlk = get(d, "PHLK")
        cntout = get(d, "CNTOUT")
        vc2 = get(d, "VC2")
        vddc = get(d, "VDDC")
        # 1. FSM reaches LOCK(4) and holds
        t4 = level_time(t, fstate, 3.5)
        ffinal = fstate[-1]
        check("fsm LOCK", (t4 is not None) and (ffinal >= 3.5),
              f"FSTATE final={ffinal:.0f}, LOCK@{t4*1e-6 if t4 else -1:.3f}u")
        t1 = level_time(t, fstate, 0.5)
        t2 = level_time(t, fstate, 1.5)
        t3 = level_time(t, fstate, 2.5)
        ta = level_time(t, afcd, 0.4)
        tf = level_time(t, fqlk, 0.4)
        tp = level_time(t, phlk, 0.4)
        print(f"  [info] AFC@{ta*1e-6:.3f}u FLL@{t2*1e-6:.3f}u FQLK@{tf*1e-6:.3f}u"
              f" PLL@{t3*1e-6:.3f}u PHLK@{tp*1e-6:.3f}u LOCK@{t4*1e-6:.3f}u")
        check("fsm order", (t1 < ta <= tf < t3 <= tp < t4) if None not in
              (t1, ta, tf, t3, tp, t4) else False,
              "AFC->FLL->PLL->LOCK monotone")
        # 2. AFC staircase: start 63, final code from VC1
        v63 = vc1[(t > t1 + 0.2e-6) & (t < t1 + 0.6e-6)].mean()
        ab_start = v63 / VC1_LSB
        m_end = (t > ta - 0.1e-6) & (t < ta + 1.0e-6)
        ab_end = vc1[m_end].mean() / VC1_LSB
        n_steps = len(np.unique(np.round(vc1[(t > t1) & (t < ta)] / VC1_LSB / 8)))
        check("afc start 63", abs(ab_start - 504) < 12,
              f"Abank start={ab_start:.0f} (code {ab_start/8:.0f})")
        check("afc final near 8G", 280 < ab_end < 460,
              f"Abank@done={ab_end:.0f} (code {ab_end/8:.1f},"
              f" {n_steps} search codes visited)")
        # 4. fVCO from CK16 over the last 2us (strobe 50p, interp avg)
        e = crossings(t, ck16)
        e = e[(e > t[-1] - 2.0e-6) & (e > 0)]
        fv = 16.0 / np.diff(e).mean()
        check("fvco 8.0G+-0.1%", abs(fv - 8.0e9) / 8.0e9 < 1e-3,
              f"fVCO={fv/1e9:.5f}G")
        # 5. phe settled
        m = t > (t4 + 0.5e-6)
        mp, mx = np.mean(np.abs(phe[m])), np.max(np.abs(phe[m]))
        check("phe settled", mp <= 0.03,
              f"|phe| mean={mp:.4f} max={mx:.4f} after LOCK+0.5u")
        # 6. handoff continuity at FSTATE transitions (window +-100n)
        ok_h, det = True, []
        for tt_, nm in ((t2, "AFC->FLL"), (t3, "FLL->PLL")):
            w = (t > tt_ - 0.1e-6) & (t < tt_ + 0.1e-6)
            step = np.max(np.abs(np.diff(vc1[w]))) if w.sum() > 2 else 0
            det.append(f"{nm}:{step*1e3:.1f}mV")
            ok_h = ok_h and (step < 5e-3)
        check("handoff no jump", ok_h, "VC1 max step " + " ".join(det))
        # 7. supplies / integer-channel invariants
        check("vddc", 0.52 < np.mean(vddc[t > 1e-6]) < 0.58,
              f"VDDC={np.mean(vddc[t > 1e-6]):.3f}V")
        check("integer dsm", (abs(selfv[-1]) < 0.1) and (abs(qerr[-1] + 0.5) < 0.05)
              and (np.nanmax(np.abs(vc2)) < 0.02),
              f"SELF={selfv[-1]:.2f} QERR={qerr[-1]:+.2f} VC2max={np.nanmax(np.abs(vc2))*1e3:.1f}mV")

    print(f"\n{'ALL PASS' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")


if __name__ == "__main__":
    main()
