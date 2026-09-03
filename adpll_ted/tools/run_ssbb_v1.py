#!/usr/bin/env python3
"""SS-BB-ADPLL V1: VA module unit tests (local spectre 20.1).

Generates sim/ssbb/v1/<tb>/ run dirs (tb netlist + needed VA files), runs each
TB with -format psfbin, reports 0-error status. Waveform verdicts are done
separately via psf exports (see session).
Usage: python3 tools/run_ssbb_v1.py [tb_name ...]   # all if no args
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / "sim" / "ssbb" / "v1"
VA = ROOT / "netlist" / "va"
INC = ROOT / "netlist" / "inc"
SPECTRE = "/opt/cadence/SPECTRE201/tools.lnx86/bin/spectre"

CKP = "Vckr (CKR 0) vsource type=pulse val0=0 val1=0.8 period=10n width=5n rise=10p fall=10p"
REFP = "Vref (REF 0) vsource type=pulse val0=0 val1=0.8 period=10n width=5n rise=10p fall=10p"

def div4_src(name, period, delay):
    m = re.match(r"([0-9.]+)([a-z]*)", period)
    w = f"{float(m.group(1)) / 2:g}{m.group(2)}"
    return (f"{name} (DIV4 0) vsource type=pulse val0=0 val1=0.8 "
            f"period={period} width={w} delay={delay} rise=10p fall=10p")


def base(tb, va_files, extra_incs, body, stop):
    L = ["simulator lang=spectre"]
    L += extra_incs
    for f in va_files:
        L.append(f'ahdl_include "{f}"')
    L.append("")
    L += body
    L.append(f"simtr tran stop={stop}")
    L.append("save *")
    L.append("")
    (V1 / tb).mkdir(parents=True, exist_ok=True)
    (V1 / tb / f"{tb}.scs").write_text("\n".join(L) + "\n")
    for f in va_files:
        shutil.copy(VA / f, V1 / tb / f)


TESTS = {}

# --- bbpd: aligned (edge 30p after CKR -> dead zone ON, bb=0.8=speed up) ---
TESTS["tb_bbpd_align"] = dict(
    va=["pll_bbpd.va"], inc=[],
    body=[CKP, div4_src("Vdiv", "500p", "530p"),
          "Xbb (CKR DIV4 BB BB_DZ) pll_bbpd vth=0.4 Tdz=50p"],
    stop="200n")

# --- bbpd: late by 300p (dead zone OFF, bb=0=slow down) ---
TESTS["tb_bbpd_late"] = dict(
    va=["pll_bbpd.va"], inc=[],
    body=[CKP, div4_src("Vdiv", "500p", "300p"),
          "Xbb (CKR DIV4 BB BB_DZ) pll_bbpd vth=0.4 Tdz=50p"],
    stop="200n")

# --- dlf: bb high 100 cycles then low 100 cycles, kp=8 ki=8 ---
# (AFC_DONE=0.8: with the V4 slave semantics done=0 means "slaved to AFC",
#  and this TB exercises the free-running loop path)
TESTS["tb_dlf"] = dict(
    va=["pll_dlf.va"], inc=[],
    body=[CKP,
          "Vbb (BB 0) vsource type=pulse val0=0 val1=0.8 period=2u width=1u rise=10p fall=10p",
          "Vafcd (AFC_DONE 0) vsource dc=0.8",
          "Vkp (KP 0) vsource dc=8", "Vki (KI 0) vsource dc=8",
          "Va0 (A0 0) vsource dc=0", "Va1 (A1 0) vsource dc=0", "Va2 (A2 0) vsource dc=0",
          "Va3 (A3 0) vsource dc=0", "Va4 (A4 0) vsource dc=0", "Va5 (A5 0) vsource dc=0",
          "Va6 (A6 0) vsource dc=0",
          "Xdlf (CKR BB AFC_DONE A0 A1 A2 A3 A4 A5 A6 KP KI "
          + " ".join(f"C{i}" for i in range(16)) + ") pll_dlf"],
    stop="2u")

# --- dac: 0 -> 85/128 (0.332V) -> 127/128 (0.496V) staircase ---
_dac_bits = []
for i in range(7):
    if i in (0, 2, 4, 6):   # 1 in both 85 and 127 (stepped pwl: pwl interpolates linearly)
        p = "0 0 100.2n 0 100.21n 0.8 300n 0.8 300.01n 0"
    else:                    # 0 in 85, 1 in 127
        p = "0 0 200.2n 0 200.21n 0.8 300n 0.8 300.01n 0"
    _dac_bits.append(f"Vb{i} (B{i} 0) vsource type=pwl wave=[ {p} ]")
TESTS["tb_dac"] = dict(
    va=["pll_dac7.va"], inc=[],
    body=_dac_bits + ["Xdac (OUT " + " ".join(f"B{i}" for i in range(7)) + ") pll_dac7 vmax=0.5"],
    stop="300n")

# --- afc: 2.05G (code walks to 0), 1.95G (to 127), 2.0G (afc_done=1) ---
TESTS["tb_afc_high"] = dict(
    va=["pll_afc.va"], inc=[],
    body=[REFP, div4_src("Vdiv", "487.804878p", "25p"),
          "Xafc (REF DIV4 " + " ".join(f"A{i}" for i in range(7)) + " AFC_DONE CNTOUT) pll_afc target=320 K=16"],
    stop="1.5u")
TESTS["tb_afc_low"] = dict(
    va=["pll_afc.va"], inc=[],
    body=[REFP, div4_src("Vdiv", "512.820513p", "25p"),
          "Xafc (REF DIV4 " + " ".join(f"A{i}" for i in range(7)) + " AFC_DONE CNTOUT) pll_afc target=320 K=16"],
    stop="1.5u")
TESTS["tb_afc_hit"] = dict(
    va=["pll_afc.va"], inc=[],
    body=[REFP, div4_src("Vdiv", "500p", "25p"),
          "Xafc (REF DIV4 " + " ".join(f"A{i}" for i in range(7)) + " AFC_DONE CNTOUT) pll_afc target=320 K=16"],
    stop="1.5u")

# --- div4: 8G in -> 2G out ---
TESTS["tb_div4"] = dict(
    va=["pll_div4.va"], inc=[],
    body=["Vin (IN 0) vsource type=pulse val0=0 val1=0.8 period=125p width=62.5p delay=10p rise=10p fall=10p",
          "Xdiv (IN OUT) pll_div4 vth=0.4"],
    stop="2n")

# --- gs: bb alternates +-1, bb_dz=0, afc_done=1, W=8 -> kp 8->4->2 ---
TESTS["tb_gs"] = dict(
    va=["pll_gs.va"], inc=[],
    body=[REFP,
          "Vbb (BB 0) vsource type=pulse val0=0 val1=0.8 period=20n width=10n rise=10p fall=10p",
          "Vdz (BB_DZ 0) vsource dc=0",
          "Vafcd (AFC_DONE 0) vsource dc=0.8",
          "Xgs (REF BB BB_DZ AFC_DONE G0 G1 G2 KP KI) pll_gs W=8 THR=4"],
    stop="300n")

# --- frac_acc: FCW=512 -> CODE9 toggles at 20n ---
TESTS["tb_frac_acc"] = dict(
    va=["pll_frac_acc.va"], inc=[],
    body=[REFP,
          "Xacc (REF " + " ".join(f"C{i}" for i in range(10)) + ") pll_frac_acc FCW=512"],
    stop="100n")

# --- dtc_10b_ss: code=4 -> c0..c3 on, c5 off; CK_OUT delayed copy of CK_IN ---
TESTS["tb_dtc"] = dict(
    va=["pll_dtc_code.va"], inc=[],
    body=["Vvdd (VDD 0) vsource dc=0.8",
          "Vck (CK_IN 0) vsource type=pulse val0=0 val1=0.8 period=10n width=5n rise=10p fall=10p",
          "Vc2 (CODE2 0) vsource dc=0.8",
          "Vc0 (CODE0 0) vsource dc=0", "Vc1 (CODE1 0) vsource dc=0",
          "Vc3 (CODE3 0) vsource dc=0", "Vc4 (CODE4 0) vsource dc=0",
          "Vc5 (CODE5 0) vsource dc=0", "Vc6 (CODE6 0) vsource dc=0",
          "Vc7 (CODE7 0) vsource dc=0", "Vc8 (CODE8 0) vsource dc=0",
          "Vc9 (CODE9 0) vsource dc=0",
          "Xdtc (CK_IN CK_OUT VDD 0 CODE0 CODE1 CODE2 CODE3 CODE4 CODE5 CODE6 CODE7 CODE8 CODE9) dtc_10b_ss",
          "save CK_OUT Xdtc.c0 Xdtc.c5"],
    stop="100n")


def run_one(name, spec):
    base(name, spec["va"], spec["inc"], spec["body"], spec["stop"])
    d = V1 / name
    if spec["va"]:
        pass
    # dtc needs the scs + PDK models
    if name == "tb_dtc":
        shutil.copy(INC / "dtc_10b_ss.scs", d / "dtc_10b_ss.scs")
        with open(d / f"{name}.scs") as f:
            t = f.read()
        t = t.replace('simulator lang=spectre\n',
                      'simulator lang=spectre\ninclude "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt\ninclude "dtc_10b_ss.scs"\n')
        (d / f"{name}.scs").write_text(t)
    r = subprocess.run([SPECTRE, "-64", f"{name}.scs", "-raw", f"{name}.raw",
                        "+log", f"{name}.log", "-format", "psfbin", "+mt=4"],
                       cwd=d, capture_output=True, text=True)
    log = d / f"{name}.log"
    ok = "spectre completes with 0 errors" in (log.read_text() if log.exists() else "")
    err = "spectre completes with" in (log.read_text() if log.exists() else "")
    print(f"{name:16s} -> {'PASS(0 errors)' if ok else ('FAIL' if err else 'NO LOG')}")


def main():
    names = sys.argv[1:] or list(TESTS)
    for n in names:
        run_one(n, TESTS[n])


if __name__ == "__main__":
    main()
