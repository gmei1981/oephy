#!/usr/bin/env python3
"""Compare tb_ref3 smoke run vs reference smoke run (schematic equivalence).

Reference: sim/ref3/v3/smoke/smoke.raw  (flat names, 4.5us)
tb run:     sim/ref3/v3/tbsmoke/tbsmoke.raw (Xpll.* hierarchical + flat REF)
Common window = [0, min(t_end)] on the 50p strobe grid.

Criteria (old compare_smoke philosophy):
  analog state  VC1 VC2 VDDC          : pointwise max|d| < 2 mV
  slow digital  PHE FCTRL QERR SELF   : max|d| < 0.02 (phe in LSB units)
  counters      CNTOUT AB8 AB7 AB6 KDBG: max|d| < 0.5 (exact int levels)
  fast digital  FSTATE FQLK PHLK AFCD ENA ENF ENP CKR CKFB CK16 OUTPB
    : mismatch fraction (|d| > 0.05) < 8% (edge-bin jitter allowance)
    + final value equal + fire rate (CK16 crossings) within 0.2%
"""
import re
import subprocess
import sys
from bisect import bisect_left, bisect_right
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "sim" / "ref3" / "v3" / "smoke" / "main.raw"
TB = ROOT / "sim" / "ref3" / "v3" / "tbsmoke" / "tbsmoke.raw"


def tran_file(rawdir):
    p = Path(rawdir)
    hits = sorted(p.glob("*.tran.tran")) + sorted(p.glob("*.raw/*.tran.tran"))
    if not hits:
        raise FileNotFoundError(f"no psf tran file under {p}")
    return hits[0]

ANALOG = ["VC1", "VC2", "VDDC"]
SLOW = ["PHE", "FCTRL", "QERR", "SELF"]
CNT = ["CNTOUT", "AB8", "AB7", "AB6", "KDBG"]
FAST = ["FSTATE", "FQLK", "PHLK", "AFCD", "ENA", "ENF", "ENP",
        "CKR", "CKFB", "CK16", "OUTPB"]


def psf_get(rawdir, sig, cands=None):
    f = tran_file(rawdir)
    names = cands or [sig]
    for nm in names:
        r = subprocess.run(["psf", "-i", str(f), "-s", "-t", nm, "-f", "%.9e"],
                           capture_output=True, text=True)
        if "VALUE" not in r.stdout:
            continue
        v, tt = [], []
        for l in r.stdout.split("VALUE", 1)[1].split("\n"):
            m = re.match(r'^"([^"]+)"\s+([0-9.eE+-]+)', l.strip())
            if m:
                tt.append(float(m.group(2)) if m.group(1) == "time"
                          or "time" in m.group(1) else None)
                # psf -s -t prints sweep+value interleaved; collect by name
        # simpler: parse named traces directly
        vv = []
        for l in r.stdout.split("VALUE", 1)[1].split("\n"):
            m = re.match(r'^"([^"]+)"\s+([0-9.eE+-]+)', l.strip())
            if m and m.group(1) == nm:
                vv.append(float(m.group(2)))
        if vv:
            return nm, vv
    return None, None


def psf_time(rawdir):
    f = tran_file(rawdir)
    r = subprocess.run(["psf", "-i", str(f), "-s", "-t", "time", "-f", "%.9e"],
                       capture_output=True, text=True)
    tt = []
    if "VALUE" in r.stdout:
        for l in r.stdout.split("VALUE", 1)[1].split("\n"):
            m = re.match(r'^"([^"]+)"\s+([0-9.eE+-]+)', l.strip())
            if m and "time" in m.group(1).lower():
                tt.append(float(m.group(2)))
    return tt


def interp(x, xp, fp):
    out = []
    j = 0
    n = len(xp)
    for xi in x:
        while j < n - 1 and xp[j + 1] <= xi:
            j += 1
        if j <= 0 and xi <= xp[0]:
            out.append(fp[0])
        elif j >= n - 1:
            out.append(fp[-1])
        else:
            t = (xi - xp[j]) / (xp[j + 1] - xp[j])
            out.append(fp[j] + t * (fp[j + 1] - fp[j]))
    return out


def crossings(t, v, thr=0.4):
    xs = []
    for i in range(1, len(v)):
        if v[i - 1] < thr <= v[i]:
            t0 = t[i - 1] + (thr - v[i - 1]) / (v[i] - v[i - 1]) * (t[i] - t[i - 1])
            xs.append(t0)
    return xs


def main():
    t_ref = psf_time(REF)
    t_tb = psf_time(TB)
    t_end = min(t_ref[-1], t_tb[-1])
    print(f"ref {t_ref[0]*1e6:.2f}..{t_ref[-1]*1e6:.2f}us  "
          f"tb {t_tb[0]*1e6:.2f}..{t_tb[-1]*1e6:.2f}us  common end "
          f"{t_end*1e6:.3f}us")
    grid = [x for x in t_ref if 0 <= x <= t_end]

    fails = []

    def fetch(sig):
        _, v = psf_get(REF, sig, [sig])
        if v is None:
            return None, None
        _, w = psf_get(TB, sig, [f"Xpll.{sig}", f"Xpll:{sig}", sig])
        return v, w

    for sig in ANALOG + SLOW + CNT:
        v, w = fetch(sig)
        if v is None or w is None:
            print(f"  [{sig}] MISSING ref={v is not None} tb={w is not None}")
            fails.append(sig)
            continue
        v_i = interp(grid, t_ref, v)
        w_i = interp(grid, t_tb, w)
        d = [abs(a - b) for a, b in zip(v_i, w_i)]
        if sig in SLOW:
            # per-cycle digital values: a sample that catches opposite sides
            # of a same transition in the two runs is a strobe-bin artifact,
            # not a value difference - exempt bins where either run is
            # mid-jump by >= half the observed diff
            d = [0.0 if (max(abs(v_i[i] - v_i[i - 1]),
                             abs(w_i[i] - w_i[i - 1])) >= 0.5 * d[i]) else d[i]
                 for i in range(len(d))]
        md = max(d)
        dv = abs(v_i[-1] - w_i[-1])
        lim = 0.002 if sig in ANALOG else (0.02 if sig in SLOW else 0.5)
        ok = md < lim
        tag = "OK " if ok else "FAIL"
        print(f"  [{tag}] {sig:8s} max|d|={md:.5f} final_d={dv:.5f} (lim {lim})")
        if not ok:
            fails.append(sig)

    for sig in FAST:
        v, w = fetch(sig)
        if v is None or w is None:
            print(f"  [{sig}] MISSING ref={v is not None} tb={w is not None}")
            fails.append(sig)
            continue
        v_i = interp(grid, t_ref, v)
        w_i = interp(grid, t_tb, w)
        mism = sum(1 for a, b in zip(v_i, w_i) if abs(a - b) > 0.05)
        frac = mism / len(v_i)
        fv_ok = abs(v_i[-1] - w_i[-1]) < 0.05
        ok = frac < 0.08 and fv_ok
        tag = "OK " if ok else "FAIL"
        print(f"  [{tag}] {sig:8s} mismatch {mism}/{len(v_i)} ({frac*100:.1f}%) "
              f"final ref={v_i[-1]:.3f} tb={w_i[-1]:.3f}")
        if not ok:
            fails.append(sig)

    # fire rate CK16 in a mid window (past AFC window-1 startup)
    _, ck_r = psf_get(REF, "CK16", ["CK16"])
    _, ck_t = psf_get(TB, "CK16", ["Xpll.CK16", "Xpll:CK16", "CK16"])
    if ck_r and ck_t:
        e_r = [x for x in crossings(t_ref, ck_r) if 0.15e-6 <= x <= t_end - 0.02e-6]
        e_t = [x for x in crossings(t_tb, ck_t) if 0.15e-6 <= x <= t_end - 0.02e-6]
        fr_r = len(e_r) / (e_r[-1] - e_r[0]) if len(e_r) > 10 else 0
        fr_t = len(e_t) / (e_t[-1] - e_t[0]) if len(e_t) > 10 else 0
        dev = abs(fr_r - fr_t) / fr_r if fr_r else 1
        fv_r, fv_t = fr_r * 16 / 1e9, fr_t * 16 / 1e9
        tag = "OK " if dev < 0.002 else "FAIL"
        print(f"  [{tag}] fVCO ref={fv_r:.4f}G tb={fv_t:.4f}G "
              f"(dev {dev*100:.3f}%, {len(e_r)}/{len(e_t)} edges)")
        if dev >= 0.002:
            fails.append("fVCO")

    print("\n" + ("ALL MATCH - schematic tb electrically equivalent"
                  if not fails else f"FAILURES: {fails}"))
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
