#!/usr/bin/env python3
"""ref3 ADPLL_ALG V1: VA module unit tests (local spectre 20.1).

Generates sim/ref3/v1/<tb>/ run dirs (tb netlist + needed VA files), runs each
TB with -format psfbin, reports 0-error status. Waveform verdicts via
tools/check_ref3_v1.py.
Usage: python3 tools/run_ref3_v1.py [tb_name ...]   # all if no args
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / "sim" / "ref3" / "v1"
VA = ROOT / "netlist" / "va"
SPECTRE = "/opt/cadence/SPECTRE201/tools.lnx86/bin/spectre"

CLK = "Vclk (CLK 0) vsource type=pulse val0=0 val1=0.8 period=10n width=5n delay=1n rise=200p fall=200p"


def dc(name, node, v):
    return f"V{name} ({node} 0) vsource dc={v}"


def pulse(name, node, period, width=None, delay="0", val1=0.8):
    if width is None:
        num = period.rstrip("pnum")
        unit = period[len(num):]
        width = f"{float(num) / 2:g}{unit}"
    return (f"V{name} ({node} 0) vsource type=pulse val0=0 val1={val1} "
            f"period={period} width={width} delay={delay} rise=10p fall=10p")


def pwl(name, node, pts):
    return f"V{name} ({node} 0) vsource type=pwl wave=[ {' '.join(str(p) for p in pts)} ]"


def bits(prefix, value, n):
    """dc sources for an n-bit code (tie LOW bits to 0V nodes)."""
    out = []
    for i in range(n):
        out.append(dc(f"{prefix}{i}", f"{prefix.upper()}{i}", 0.8 if (value >> i) & 1 else 0))
    return out


def bus(prefix, n):
    return " ".join(f"{prefix.upper()}{i}" for i in range(n))


def base(tb, va_files, body, stop):
    L = ["simulator lang=spectre"]
    L.append('ahdl_include "constants.vams"')
    L.append('ahdl_include "disciplines.vams"')
    for f in va_files:
        L.append(f'ahdl_include "{f}"')
    L.append("")
    L += body
    L.append(f"simtr tran stop={stop}")
    L.append("save *")
    L.append("")
    (V1 / tb).mkdir(parents=True, exist_ok=True)
    (V1 / tb / f"{tb}.scs").write_text("\n".join(L) + "\n")
    for f in va_files + ["constants.vams", "disciplines.vams"]:
        shutil.copy(VA / f, V1 / tb / f)


TESTS = {}

# ============ dsm_fb: FCW=80.5 mode0 (ratio alternates 80/81) ============
TESTS["tb_dsmfb_m0"] = dict(
    va=["pll_dsm_fb.va"],
    body=[CLK, dc("rc", "RC", 0),
          "Xd (CLK RC " + bus("p", 13) + " QERR SEL) pll_dsm_fb FCW=80.5 dsm_fb_mode=0"],
    stop="400n")

# ============ dsm_fb: FCW=80.25 mode1 (MASH1-1, ratio in [79,82]) ============
TESTS["tb_dsmfb_m1"] = dict(
    va=["pll_dsm_fb.va"],
    body=[CLK, dc("rc", "RC", 0),
          "Xd (CLK RC " + bus("p", 13) + " QERR SEL) pll_dsm_fb FCW=80.25 dsm_fb_mode=1"],
    stop="400n")

# ============ mmd_ps: static ratios + sel (8G sine in) ============
# NOTE: spectre sine takes the DC operating point via dc=, not offset=
VCO = "Vvco (VCO 0) vsource type=sine freq=8G ampl=0.4 dc=0.4"
for tag, ratio, selv in [("r80", 80, 0), ("r16", 16, 0), ("r255", 255, 0), ("sel", 80, 0.8)]:
    TESTS[f"tb_mmd_{tag}"] = dict(
        va=["pll_mmd_ps.va"],
        body=[VCO] + bits("p", ratio, 13) + [dc("sel", "SEL", selv),
              f"Xm (VCO {bus('p', 13)} SEL CKFB) pll_mmd_ps ninit={ratio}"],
        stop="150n" if ratio in (80, 255) else "60n")

# ============ tdc+pfd chain: dt = +100p / +240p / -100p ============
def tdc_tb(tag, ckr_delay, ckb_delay):
    return dict(
        va=["pll_tdc_beh.va", "pll_pfd.va"],
        body=[pulse("ckr", "CKR", "10n", "5n", ckr_delay),
              pulse("ckb", "CKFB", "10n", "5n", ckb_delay),
              "Xt (CKR CKFB " + bus("oha", 16) + " " + bus("ohb", 16) + " "
              + bus("ca", 16) + " " + bus("cb", 16) + " " + bus("f", 16)
              + " ARB) pll_tdc_beh",
              "Xp (" + bus("ca", 16) + " " + bus("cb", 16) + " " + bus("f", 16)
              + " ARB " + bus("oha", 16) + " " + bus("ohb", 16)
              + " PHE TCODE) pll_pfd"],
        stop="300n")

TESTS["tb_tdcpfd_p100"] = tdc_tb("p100", "2n", "2.1n")
TESTS["tb_tdcpfd_p240"] = tdc_tb("p240", "2n", "2.23n")   # dt=230p, clear of the 240p/122.88 bin edge
TESTS["tb_tdcpfd_n100"] = tdc_tb("n100", "2.1n", "2n")

# ============ fll: hit (500M tap) + direction (502M, ftol=0) ============
TESTS["tb_fll_hit"] = dict(
    va=["pll_fll.va"],
    body=[CLK, pulse("ck16", "CK16", "2n"), dc("en", "EN", 0.8),
          "Xf (CLK CK16 EN FCTRL FQLK) pll_fll FCW=80.0 thr=9 D=16"],
    stop="11u")
TESTS["tb_fll_dir"] = dict(
    va=["pll_fll.va"],
    body=[CLK, pulse("ck16", "CK16", "1.99203187n"), dc("en", "EN", 0.8),
          "Xf (CLK CK16 EN FCTRL FQLK) pll_fll FCW=80.0 thr=6 D=16 ftol=0"],
    stop="7u")

# ============ lpf: afc(20)->fll(+5)->pll(phe=+1) handoff staircase ============
TESTS["tb_lpf"] = dict(
    va=["pll_lpf.va"],
    body=[CLK,
          pwl("phe", "PHE", [0, 0, "1999.9n", 0, "2000n", 1.0, "3200n", 1.0]),
          pwl("fct", "FCTRL", [0, 0, "999.9n", 0, "1000n", 5, "3200n", 5]),
          pwl("ena", "ENA", [0, 0.8, "999.9n", 0.8, "1000n", 0, "3200n", 0]),
          pwl("enf", "ENF", [0, 0, "999.9n", 0, "1000n", 0.8, "1999.9n", 0.8, "2000n", 0, "3200n", 0]),
          pwl("enp", "ENP", [0, 0, "1999.9n", 0, "2000n", 0.8, "3200n", 0.8]),
          dc("plk", "PHLK", 0),
          dc("a2", "A2", 0.8), dc("a4", "A4", 0.8)] +
         [dc(f"a{i}", f"A{i}", 0) for i in (0, 1, 3, 5)] +
        ["Xl (CLK PHE FCTRL ENA ENF ENP PHLK " + bus("a", 6) + " "
         + bus("ab", 9) + " " + bus("fr", 26) + ") pll_lpf"],
    stop="3.2u")

# ============ dsm_dco: frac=0.5 (fr25 only) -> out alternates 8/9 ============
TESTS["tb_dsmdco"] = dict(
    va=["pll_dsm_dco.va"],
    body=[CLK, dc("fr25", "FR25", 0.8)] +
         [dc(f"fr{i}", f"FR{i}", 0) for i in range(25)] +
        ["Xd (CLK " + bus("fr", 26) + " " + bus("f", 4) + ") pll_dsm_dco dsm_dco_mode=0"],
    stop="400n")

# ============ afc6: hit (500M) / slow (490M -> park 63) / fast (510M -> park 0) ============
AFC_INST = ("Xa (CLK CK16 EN " + bus("p", 6) + " AFC_DONE CNTOUT) "
            "pll_afc6 FCW=80.0 thr=8 D=16")
TESTS["tb_afc6_hit"] = dict(
    va=["pll_afc6.va"], body=[CLK, pulse("ck16", "CK16", "2n"), dc("en", "EN", 0.8), AFC_INST],
    stop="11u")
TESTS["tb_afc6_slow"] = dict(
    va=["pll_afc6.va"],
    body=[CLK, pulse("ck16", "CK16", "2.0408163265n"), dc("en", "EN", 0.8), AFC_INST],
    stop="30u")
TESTS["tb_afc6_fast"] = dict(
    va=["pll_afc6.va"],
    body=[CLK, pulse("ck16", "CK16", "1.9607843137n"), dc("en", "EN", 0.8), AFC_INST],
    stop="30u")

# ============ cal_kdtc: phe = 0.1*q[k-1] delayed correlation -> +0.025/edge ============
# spectre pulse semantics: val1 during [delay, delay+width) FIRST, then val0.
# q: -0.25 [0,10n), +0.25 [10,20n); phe (delay=0): +0.1 [0,10n), -0.1 [10,20n)
# -> at CLK falling edges phe[k] = -0.1*q[k] = +0.1*q[k-1] (q alternates per
# edge), so phe[k]*qerr_d[k-1] = +0.025 every edge (edge-1 = 0: qerr_d init 0)
TESTS["tb_calk"] = dict(
    va=["pll_cal_kdtc.va"],
    body=[CLK, dc("dcomp", "DCOMP", 0), dc("en", "EN", 0.8),
          "Vq (Q 0) vsource type=pulse val0=0.25 val1=-0.25 period=20n width=10n rise=10p fall=10p",
          "Vphe (PHE 0) vsource type=pulse val0=-0.1 val1=0.1 period=20n width=10n rise=10p fall=10p",
          "Xk (CLK PHE Q DCOMP EN " + bus("d", 10) + " KDBG) pll_cal_kdtc"],
    stop="2.2u")

# ============ cal_refdcc: |sel_out| = 0.02 const -> +0.02/64 per edge ============
TESTS["tb_calr"] = dict(
    va=["pll_cal_refdcc.va"],
    body=[CLK, dc("en", "EN", 0.8),
          "Vphe (PHE 0) vsource type=pulse val0=-0.02 val1=0.02 period=20n width=10n rise=10p fall=10p",
          "Xr (CLK PHE EN RCOEF RSEL) pll_cal_refdcc"],
    stop="2.2u")

# ============ cal_dcodcc: sel 20n on/20n off, phe +0.02 on rise cycles ============
TESTS["tb_cald"] = dict(
    va=["pll_cal_dcodcc.va"],
    body=[CLK, dc("en", "EN", 0.8),
          "Vsel (SEL 0) vsource type=pulse val0=0 val1=0.8 period=40n width=20n rise=10p fall=10p",
          "Vphe (PHE 0) vsource type=pulse val0=0 val1=0.02 period=40n width=10n rise=10p fall=10p",
          "Xc (CLK PHE SEL EN DCOMP DDBG) pll_cal_dcodcc"],
    stop="2.2u")

# ============ lockdet: 0.005 -> lock @2.57us; 0.2 -> unlock @5.57us ============
TESTS["tb_lockdet"] = dict(
    va=["pll_lockdet.va"],
    body=[CLK,
          pwl("phe", "PHE", [0, 0.005, "2999.9n", 0.005, "3000n", 0.2, "5999.9n", 0.2, "6000n", 0.005, "6500n", 0.005]),
          "Xl (CLK PHE PHLK) pll_lockdet"],
    stop="6.5u")

# ============ fsm: full state trajectory incl. UNLOCK->FLL->PLL ============
TESTS["tb_fsm"] = dict(
    va=["pll_fsm.va"],
    body=[CLK,
          pwl("rstn", "RSTN", [0, 0, "19.9n", 0, "20n", 0.8, "2000n", 0.8]),
          pwl("afcd", "AFIN", [0, 0, "199.9n", 0, "200n", 0.8, "2000n", 0.8]),
          pwl("fqlk", "FQLK", [0, 0, "499.9n", 0, "500n", 0.8, "2000n", 0.8]),
          pwl("phlk", "PHLK", [0, 0, "799.9n", 0, "800n", 0.8, "1199.9n", 0.8, "1200n", 0, "1499.9n", 0, "1500n", 0.8, "2000n", 0.8]),
          "Xf (CLK RSTN AFIN FQLK PHLK ST0 ST1 ST2 ENA ENF ENP FSTATE) pll_fsm idle_wait=4"],
    stop="1.8u")

# ============ dac9b: code 384 -> 0.375V ============
TESTS["tb_dac9b"] = dict(
    va=["pll_dac9b.va"],
    body=bits("b", 384, 9) +
         ["Xd (OUT " + bus("b", 9) + ") pll_dac9b vmax=0.5"],
    stop="100n")


def run_one(name, spec):
    base(name, spec["va"], spec["body"], spec["stop"])
    d = V1 / name
    r = subprocess.run([SPECTRE, "-64", f"{name}.scs", "-raw", f"{name}.raw",
                        "+log", f"{name}.log", "-format", "psfbin", "+mt=4"],
                       cwd=d, capture_output=True, text=True)
    log = d / f"{name}.log"
    txt = log.read_text() if log.exists() else ""
    ok = "spectre completes with 0 errors" in txt
    done = "spectre completes with" in txt
    print(f"{name:18s} -> {'PASS(0 errors)' if ok else ('FAIL' if done else 'NO LOG')}")


def main():
    names = sys.argv[1:] or list(TESTS)
    for n in names:
        run_one(n, TESTS[n])


if __name__ == "__main__":
    main()
