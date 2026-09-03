#!/usr/bin/env python3
"""ref3 ADPLL_ALG V2: open-loop calibration TBs (local spectre 20.1).

V2-1 tdc_sweep    — TDC transfer curve: CKFB edges at 20 programmed delays
                    (pwl, 10..485p in 25p steps; d>250p wraps negative through
                    the TDC fold) vs fixed CKR; phe pointwise + slope.
V2-2 mmd_selphase — sel 0->1 at 1us: CKFB rising-edge phase vs VCO rising
                    shifts by TVCO/2 = 62.5p.
V2-3 chain80_*    — dsm_fb(FCW=80) -> mmd_ps -> tdc+pfd open chain, CKR delay
                    0.7/0.8/0.9n static phe; sine 7.9G/8.1G phe ramp direction.
V2-4 kvco_ab_*    — pll_dac9b -> vco_x_c_dac VC1, Abank codes {0,128,256,384,
                    512} -> KVCO_A spot check (startup context from ref2 V2a).

Usage: python3 tools/run_ref3_v2.py [par]     # generate + run all (cached)
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "sim" / "ref3" / "v2"
VA = ROOT / "netlist" / "va"
INC = ROOT / "netlist" / "inc"
SPECTRE = "/opt/cadence/SPECTRE201/tools.lnx86/bin/spectre"
PDK = 'include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt'

VA_HDR = ['ahdl_include "constants.vams"', 'ahdl_include "disciplines.vams"']


def bits(prefix, value, n):
    return [f"V{prefix}{i} ({prefix.upper()}{i} 0) vsource dc={0.8 if (value >> i) & 1 else 0:g}"
            for i in range(n)]


def bus(prefix, n):
    return " ".join(f"{prefix.upper()}{i}" for i in range(n))


def va_tb(name, va_files, body, stop, save="*"):
    L = ["simulator lang=spectre"] + VA_HDR
    for f in va_files:
        L.append(f'ahdl_include "{f}"')
    L.append("")
    L += body
    L.append(f"tran tran stop={stop}")
    L.append(f"save {save}")
    L.append("")
    d = V2 / name
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.scs").write_text("\n".join(L) + "\n")
    files = [(VA / f, f) for f in va_files + ["constants.vams", "disciplines.vams"]]
    return name, "\n".join(L), files


def gen_tdc_sweep():
    # CKR: 100M pulse delay 2n (cross at 2n+5p); CKFB: pwl edges at
    # 2n + d_k + 10n*k, d_k = 10p + 25p*k (cross at +1p), rise/fall 2p
    pts = []
    for k in range(20):
        d = 10e-12 + 25e-12 * k
        tau = 2e-9 + d + 10e-9 * k
        pts += [f"{tau:.15g} 0", f"{tau + 2e-12:.15g} 0.8", f"{tau + 500e-12:.15g} 0"]
    wave = " ".join(pts)
    body = [
        "Vckr (CKR 0) vsource type=pulse val0=0 val1=0.8 period=10n width=5n delay=2n rise=10p fall=10p",
        f"Vckb (CKFB 0) vsource type=pwl wave=[ {wave} ]",
        "Xt (CKR CKFB " + " ".join([bus("oha", 16), bus("ohb", 16), bus("ca", 16),
                                    bus("cb", 16), bus("f", 16)]) + " ARB) pll_tdc_beh",
        "Xp (" + " ".join([bus("ca", 16), bus("cb", 16), bus("f", 16), "ARB",
                           bus("oha", 16), bus("ohb", 16)]) + " PHE TCODE) pll_pfd",
    ]
    return va_tb("tdc_sweep", ["pll_tdc_beh.va", "pll_pfd.va"], body, "220n")


def gen_selphase():
    body = [
        "Vvco (VCO 0) vsource type=sine freq=8G ampl=0.4 dc=0.4",
        'Vsel (SEL 0) vsource type=pwl wave=[0 0 0.999u 0 1.0u 0.8 2.5u 0.8]',
    ] + bits("p", 80, 13) + [
        "Xm (VCO " + bus("p", 13) + " SEL CKFB) pll_mmd_ps ninit=80",
    ]
    return va_tb("mmd_selphase", ["pll_mmd_ps.va"], body, "2.5u")


def gen_chain(delay, freq=None, tag=None):
    tag = tag or f"d{delay.replace('.', 'p')}"
    body = [
        "Vclk (REF 0) vsource type=pulse val0=0 val1=0.8 period=10n width=5n rise=200p fall=200p",
        f"Vckr (CKR 0) vsource type=pulse val0=0 val1=0.8 period=10n width=5n delay={delay} rise=10p fall=10p",
        f"Vvco (VCO 0) vsource type=sine freq={freq or '8G'} ampl=0.4 dc=0.4",
        "Vrc (RC 0) vsource dc=0",
        "Xd (REF RC " + bus("p", 13) + " QERR SEL) pll_dsm_fb FCW=80.0 dsm_fb_mode=0",
        "Xm (VCO " + bus("p", 13) + " SEL CKFB) pll_mmd_ps ninit=80",
        "Xt (CKR CKFB " + " ".join([bus("oha", 16), bus("ohb", 16), bus("ca", 16),
                                    bus("cb", 16), bus("f", 16)]) + " ARB) pll_tdc_beh",
        "Xp (" + " ".join([bus("ca", 16), bus("cb", 16), bus("f", 16), "ARB",
                           bus("oha", 16), bus("ohb", 16)]) + " PHE TCODE) pll_pfd",
    ]
    return va_tb(f"chain80_{tag}", ["pll_dsm_fb.va", "pll_mmd_ps.va", "pll_tdc_beh.va",
                                    "pll_pfd.va"], body, "220n")


def gen_kvco(code):
    L = [
        "// kvco_ab point (generated): Abank code -> dac9b -> VC1",
        "simulator lang=spectre",
        PDK,
    ] + VA_HDR + [
        'ahdl_include "pll_dac9b.va"',
        'include "vco_c_dac.scs"',
        "",
        "Vss (VSS 0) vsource dc=0",
        "Vvddc (VDDC 0) vsource type=pulse val0=0 val1=0.5 delay=0 rise=1n width=1m period=1m",
        "Vc2 (VC2 0) vsource dc=0",
    ] + bits("b", code, 9) + [
        "// both supply pins of vco_x_c_dac to the 0.5V node (VDD = tank supply)",
        "Xvco (VDDC VDDC VSS OUTP OUTN VC1 VC2) vco_x_c_dac",
        "Xdac (VC1 " + bus("b", 9) + ") pll_dac9b vmax=0.5",
        "",
        'tran tran stop=120n maxstep=2p errpreset=liberal method=gear2only skipdc=yes'
        ' ic="OUTP=0.45" ic="OUTN=0.0"',
        "save OUTP OUTN VDDC VC1",
        "saveOptions options save=selected",
        "",
    ]
    d = V2 / f"kvco_ab_{code}"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"kvco_ab_{code}.scs").write_text("\n".join(L) + "\n")
    files = [(INC / "vco_c_dac.scs", "vco_c_dac.scs"),
             (VA / "pll_dac9b.va", "pll_dac9b.va"),
             (VA / "constants.vams", "constants.vams"),
             (VA / "disciplines.vams", "disciplines.vams")]
    return f"kvco_ab_{code}", "\n".join(L), files


def gen_all():
    pts = [gen_tdc_sweep(), gen_selphase(),
           gen_chain("0.7n"), gen_chain("0.8n"), gen_chain("0.9n"),
           gen_chain("0.8n", freq="7.9G", tag="s79"),
           gen_chain("0.8n", freq="8.1G", tag="s81")]
    pts += [gen_kvco(c) for c in (0, 128, 256, 384, 511)]   # 9-bit: 512 overflows!
    return pts


def run_one(name, netlist, files):
    d = V2 / name
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.scs").write_text(netlist)
    for src, dst in files:
        shutil.copy(src, d / dst)
    log = d / f"{name}.log"
    if log.exists() and "spectre completes with 0 errors" in log.read_text():
        return "cached"
    subprocess.run([SPECTRE, "-64", f"{name}.scs", "-raw", f"{name}.raw",
                    "+log", f"{name}.log", "-format", "psfbin", "+mt=4"],
                   cwd=d, capture_output=True, text=True)
    txt = log.read_text() if log.exists() else ""
    return "PASS(0 errors)" if "spectre completes with 0 errors" in txt else "FAIL"


def main():
    par = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=par) as ex:
        futs = {ex.submit(run_one, *p): p[0] for p in gen_all()}
        for fu, n in futs.items():
            print(f"{n:18s} {fu.result()}", flush=True)


if __name__ == "__main__":
    main()
