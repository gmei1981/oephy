#!/usr/bin/env python3
"""SS-BB-ADPLL V2: open-loop calibration runs (local spectre 20.1).

V2a  vco_tune  — vco_x_c_dac f(VC1,VC2) sweep. Startup context replicated from
                 Plan C (VDDC 1n ramp, OUTP/OUTN asymmetric ic, skipdc).
V2b  dtc_bbpd  — REF -> dtc_10b_ss(CODE) -> CKR -> pll_bbpd vs synthetic DIV4
                 (500p, aligned): BB flips at the 250ps fold point
                 (CODE ~757 @330fs/LSB), BB_DZ low near CODE 0 and the fold.

Usage:
  python3 tools/run_ssbb_v2.py vco_tune          # generate + run all points
  python3 tools/run_ssbb_v2.py dtc_bbpd
  python3 tools/run_ssbb_v2.py analyze           # verdicts from finished runs
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "sim" / "ssbb" / "v2"
VA = ROOT / "netlist" / "va"
INC = ROOT / "netlist" / "inc"
SPECTRE = "/opt/cadence/SPECTRE201/tools.lnx86/bin/spectre"

PDK = 'include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt'

# --- V2a: VC1 coarse sweep @VC2=0.25 + VC2 fine sweep @VC1 bases ---
VCO_PTS = ([(v, 0.25) for v in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)]
           + [(v1, v2) for v1 in (0.1, 0.3, 0.5) for v2 in (0.0, 0.25, 0.5)
              if not (v2 == 0.25)])   # dup vs first sweep

# --- V2b: CODE sweep, dense near fold ~757 (250ps/330fs) and dz near 0 ---
CODES = [0, 128, 256, 384, 512, 640, 704, 736, 768, 800, 896, 1023]


def vco_netlist(vc1, vc2):
    return "\n".join([
        "// vco_tune point (generated)",
        "simulator lang=spectre",
        PDK,
        'include "vco_c_dac.scs"',
        "",
        "Vvdd  (VDD 0)  vsource dc=0.8",
        "Vss   (VSS 0)  vsource dc=0",
        "Vvddc (VDDC 0) vsource type=pulse val0=0 val1=0.5 delay=0 rise=1n width=1m period=1m",
        f"Vc1 (VC1 0) vsource dc={vc1:g}",
        f"Vc2 (VC2 0) vsource dc={vc2:g}",
        "",
        "// vco_x_c_dac port 'VDD' is the TANK supply (Xa.VDD<-VDDC in the dual"
        " wrapper): tie BOTH supply pins to the 0.5V node. Port VDDC is unused"
        " inside (vestigial); tied to keep it off 0.8V.",
        "Xvco (VDDC VDDC VSS OUTP OUTN VC1 VC2) vco_x_c_dac",
        "",
        "tran tran stop=120n maxstep=2p errpreset=liberal method=gear2only skipdc=yes"
        ' ic="OUTP=0.45" ic="OUTN=0.0"',
        "save OUTP OUTN VDDC",
        "saveOptions options save=selected",
        "",
    ])


def dtc_netlist(code):
    return "\n".join([
        "// dtc_bbpd point (generated)",
        "simulator lang=spectre",
        PDK,
        # decoder VA must be defined BEFORE the dtc subckt (Xdec inside) is read
        'ahdl_include "pll_dtc_code.va"',
        'ahdl_include "pll_bbpd.va"',
        'include "dtc_10b_ss.scs"',
        "",
        "Vvdd (VDD 0) vsource dc=0.8",
        "Vref (REF 0) vsource type=pulse val0=0 val1=0.8 period=10n width=5n rise=10p fall=10p",
        "Vdiv (DIV4 0) vsource type=pulse val0=0 val1=0.8 period=500p width=250p"
        " rise=10p fall=10p",
        *[f"Vc{i} (CODE{i} 0) vsource dc={((code >> i) & 1) * 0.8:g}" for i in range(10)],
        "",
        "Xdtc (REF CKR VDD 0 " + " ".join(f"CODE{i}" for i in range(10)) + ") dtc_10b_ss",
        "Xbb (CKR DIV4 BB BB_DZ) pll_bbpd vth=0.4 Tdz=50p",
        "",
        "tran tran stop=120n maxstep=5p errpreset=liberal method=gear2only skipdc=yes",
        "save CKR BB BB_DZ",
        "saveOptions options save=selected",
        "",
    ])


def run_dir(name, netlist, extra_files):
    d = V2 / name
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.scs").write_text(netlist)
    for src, dst in extra_files:
        shutil.copy(src, d / dst)
    log = d / f"{name}.log"
    if log.exists():
        txt = log.read_text()
        if "spectre completes with 0 errors" in txt:
            return "cached"
    r = subprocess.run([SPECTRE, "-64", f"{name}.scs", "-raw", f"{name}.raw",
                        "+log", f"{name}.log", "-format", "psfbin", "+mt=4"],
                       cwd=d, capture_output=True, text=True)
    txt = log.read_text() if log.exists() else ""
    return "PASS(0 errors)" if "spectre completes with 0 errors" in txt else "FAIL"


def gen_all():
    pts = []
    for vc1, vc2 in VCO_PTS:
        pts.append((f"vco_{vc1:g}_{vc2:g}".replace(".", "p"), vco_netlist(vc1, vc2),
                    [(INC / "vco_c_dac.scs", "vco_c_dac.scs")]))
    for c in CODES:
        pts.append((f"dtc_c{c}", dtc_netlist(c),
                    [(INC / "dtc_10b_ss.scs", "dtc_10b_ss.scs"),
                     (VA / "pll_bbpd.va", "pll_bbpd.va"),
                     (VA / "pll_dtc_code.va", "pll_dtc_code.va"),
                     (VA / "constants.vams", "constants.vams"),
                     (VA / "disciplines.vams", "disciplines.vams")]))
    return pts


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


def measure_freq(d, tmin=70e-9):
    t = get(d, "time")
    v = get(d, "OUTP")
    n = min(len(t), len(v))
    t, v = t[:n], v[:n]
    m = t > tmin
    idx = np.where(m)[0]
    # rising crossings at 0.4V: the OUTP waveform has a ~0.29V secondary hump
    # each period (asymmetric halves at low VC1) — 0.25V double-counts it,
    # 0.4/0.5/0.6V verified single-edge per period
    above = v > 0.4
    edges = []
    for k in idx[1:]:
        if above[k] and not above[k - 1]:
            # linear interp
            f = (0.25 - v[k - 1]) / (v[k] - v[k - 1])
            edges.append(t[k - 1] + f * (t[k] - t[k - 1]))
    if len(edges) < 20:
        return None
    per = np.diff(edges).mean()
    return 1.0 / per


def analyze():
    print("== V2a vco_tune ==")
    rows = []
    for vc1, vc2 in VCO_PTS:
        name = f"vco_{vc1:g}_{vc2:g}".replace(".", "p")
        d = V2 / name
        try:
            f = measure_freq(d)
        except Exception as e:
            f = None
        rows.append((vc1, vc2, f))
        print(f"  VC1={vc1:.2f} VC2={vc2:.2f}  fVCO={'--' if f is None else f'{f/1e9:.4f} GHz'}")
    print("\n== V2b dtc_bbpd ==")
    for c in CODES:
        d = V2 / f"dtc_c{c}"
        try:
            t = get(d, "time")
            bb = get(d, "BB")
            dz = get(d, "BB_DZ")
            n = min(len(t), len(bb), len(dz))
            m = t[:n] > 60e-9
            print(f"  CODE={c:4d} (~{c*0.33:.0f}ps)  BB={bb[:n][m].mean():.2f}"
                  f"  BB_DZ={dz[:n][m].mean():.2f}")
        except Exception as e:
            print(f"  CODE={c:4d}  probe failed: {e}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    pts = gen_all()
    if mode in ("vco_tune", "dtc_bbpd"):
        key = "vco_" if mode == "vco_tune" else "dtc_"
        pts = [p for p in pts if p[0].startswith(key)]
    if mode == "analyze":
        analyze()
        return
    par = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    running = []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=par) as ex:
        futs = {ex.submit(run_dir, n, nl, ef): n for n, nl, ef in pts}
        for fu in futs:
            pass
        for fu, n in futs.items():
            print(f"{n:20s} {fu.result()}")


if __name__ == "__main__":
    main()
