#!/usr/bin/env python3
"""Generate top-level PLL netlist for the paper reproduction.

Usage:
  python3 scripts/gen_top.py step1 [--chan main|nearint] [--stop 300n] [--vco 1|2]
  python3 scripts/gen_top.py step2 [--stop 300n]
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sim"
OUT.mkdir(exist_ok=True)

# --- configs ---------------------------------------------------------------
CONFIG = {
    # name: (fref_xo, fvco, Nint2, frac2, lms_fref, decode_fref, Tres, VBSPD, vref0)
    # NOTE: VA 实际分频比 = Nint2 + frac2（CKFB = fVCO/(Nint2+frac2)），
    # 不是设计文档早期误写的 Nint2/2。CKFB 目标 = 2×fref（step1/近整数）或 fref（step2）。
    "step1_main":    (76.8e6, 6.2e9, 40, 0.364583, 153.6e6, 153.6e6, 330e-15, 0.48, 0.15),
    "step1_nearint": (76.8e6, 6451.3e6, 42, 0.000651, 153.6e6, 153.6e6, 330e-15, 0.48, 0.15),
    "step2_main":    (100e6, 8.0e9, 80, 0.0, 100e6, 100e6, 330e-15, 0.52, 0.15),
}

NBITS = 10
NSW = (1 << NBITS) - 1  # 1023


def mos(t):
    return f"{t} l=16n nfin=2 w=58n multi=1 nf={{nf}} sd=74n sa=90n sb=90n ploda1=16n " \
           "ploda2=0 ploda3=0 plodb1=16n plodb2=0 plodb3=0 nf_flag=1 smbt=1M smbb=1M " \
           "dinsaflag=0 ppitch=0 spot=103n spob=103n spotl1=103n spobl1=103n " \
           "spotl2=103n spobl2=103n spotr1=103n spobr1=103n spotr2=103n spobr2=103n"


from typing import Optional
def gen(name: str, stop: str, dual: bool, strobe: Optional[str] = None, save_dtc_probe: bool = False) -> Path:
    cfg = CONFIG[name]
    fref_xo, fvco, Nint2, frac2, lms_fref, dec_fref, Tres, vbspd, vref0 = cfg
    period_xo = 1.0 / fref_xo
    L = []
    A = L.append
    A(f"// pll_{name}.scs — generated paper-reproduction top-level")
    A(f"// fref={fref_xo/1e6:g}M XO, fvco={fvco/1e9:g}G, Nint2={Nint2}, frac2={frac2}, dual_core={dual}")
    A("simulator lang=spectre")
    A("")
    A('include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt')
    A('include "dtc_10b.scs"')
    A('include "vco_dual_8g.scs"' if name.startswith("step2") else 'include "vco_dual.scs"')
    A('include "spd_cmp_gm.scs"')
    A('ahdl_include "pll_mmd_edge.va"')
    A('ahdl_include "pll_lms.va"')
    A('ahdl_include "pll_dtc_decoder_10b.va"')
    A('ahdl_include "pll_hybrid_aux.va"')
    A("")
    A("Vvdd (VDD 0) vsource dc=0.8")
    A("Vvss (VSS 0) vsource dc=0")
    A(f"Vref (REF 0) vsource type=pulse val0=0 val1=0.8 period={period_xo:.6e} "
      f"width={period_xo/2:.6e} rise=10p fall=10p")
    A(f"Vbspd (VBSPD 0) vsource dc={vbspd}")
    A("Vbcmp (VBCMP 0) vsource dc=0.8")
    A("Vbgm  (VBGM 0) vsource dc=0.8")
    A("")
    if dual:
        vco_mod = "vco_dual_8g" if name.startswith("step2") else "vco_dual"
        A("Venv2 (EN2 0) vsource dc=0.8")
        A(f"Xvco (VDD VSS VCTRL OUTP OUTN EN2) {vco_mod}")
    else:
        A("// single-core: direct vco_x (no unpowered core-B floating nodes)")
        A("Xvco (VDD VSS VCTRL OUTP OUTN) vco_x")
    A("Xdtc (CK2X CKDTCD VDD VSS \\")
    for i in range(0, NSW, 16):
        row = " ".join(f"c{j}" for j in range(i, min(i + 16, NSW)))
        A("    " + row + " \\")
    A("    ) dtc_10b  // code ports wired directly to Xdec outputs (shared nodes)")
    A("Xspd (VBSPD CKRST CKFB VHOLD VRAMP VDD VSS) spd_x")
    A("Xcmp (VHOLD VREF VBCMP EBIT VDD VSS) cmp_x")
    A("Xgm  (VHOLD VREF VBGM VI VDD VSS) gm_x")
    A("")
    if name.startswith("step2"):
        A("Edbl (CK2X 0 REF 0) vcvs gain=1.0  // step2: 100M 参考不经倍频")
    else:
        A("Xdbl (REF CK2X) pll_doubler_edge")
    A("Einv (CKRSTI 0 CKDTCD 0) vcvs gain=-1.0")
    A("Vrstofs (VDC08 0) vsource dc=0.8")
    A("Esumrst (CKRST VDC08 CKRSTI 0) vcvs gain=1.0")
    A("")
    # VCO output buffering
    A("Minvbuf_n (NBUF1 BUFFIN VSS VSS) " + mos("nch_svt_mac").format(nf=4))
    A("Minvbuf_p (NBUF1 BUFFIN VDD VDD) " + mos("pch_svt_mac").format(nf=4))
    A("Minvbuf2_n (MMDIN NBUF1 VSS VSS) " + mos("nch_svt_mac").format(nf=4))
    A("Minvbuf2_p (MMDIN NBUF1 VDD VDD) " + mos("pch_svt_mac").format(nf=4))
    A("Rbuf (OUTP BUFFIN) resistor r=1k")
    A("")
    A(f"Xmmd (MMDIN CKFB SEL ALT EPSC ERR) pll_mmd_edge Nint2={Nint2}.0 frac2={frac2} vth=0.7")
    A("Xclkl (CKFB CLKLMS) pll_clk_lms")
    A(f"Xlms (CLKLMS EBIT SEL ALT EPSC KDTC VDCC RDCC VREF) pll_lms \\")
    if name.startswith("step2"):
        A("    mu_k=0.0 mu_v=0.0 mu_r=1e-13 mu_off=4.2e-13 K0=1.0 vdcc0=12e-12 rdcc0=-12e-12 ohat0=32e-12 \\")
    else:
        A("    mu_k=0.01 mu_v=5e-13 mu_r=1e-13 mu_off=4.2e-13 K0=1.0 vdcc0=12e-12 rdcc0=-12e-12 ohat0=32e-12 \\")
    A(f"    offset_s=32e-12 vref0={vref0} fref={lms_fref:.6e} m_slope=1e9 mode=1 tscale=1e-6 seed=121")
    A("Xdec (CKFB KDTC EPSC SEL ALT VDCC RDCC \\")
    for i in range(0, NSW, 16):
        row = " ".join(f"c{j}" for j in range(i, min(i + 16, NSW)))
        A("    " + row + " \\")
    A("    ) pll_dtc_decoder_10b \\")
    A(f"    fout={fvco:.6e} fref={dec_fref:.6e} frac2={frac2} Tres={Tres:.6e}")

    A("")
    A("Xci (VI 0) capacitor c=2p ic=0.55")
    A("// 预充电: 0-2ns 注入 550uA -> VI≈0.55V, 环路从近锁定状态启动")
    A("// (VCTRL=0 时 VCO f_min≈3.08G -> CKFB≈76M 与 2×fref 斜坡栅格近同步,")
    A("//  采样相位冻结在复位区 -> 谐波锁死, 无外力无法捕获)")
    A("Iinj (VI 0) isource type=pulse val0=0 val1=-550u delay=0 width=2n period=1m rise=10p fall=10p")
    A("Rf (VHOLD VHF) resistor r=5k")
    A("Cf (VHF 0) capacitor c=5p")
    A("Ep (VN1 0 VHF 0) vcvs gain=0.06")
    A("Esum (VCTRL VN1 VI 0) vcvs gain=1.0")
    A("")
    if strobe:
        A(f"plltran tran stop={stop} maxstep=2p errpreset=liberal method=gear2only skipdc=yes "
          f"ic=\"OUTP=0.6\" strobeperiod={strobe} strobeoutput=strobeonly")
    else:
        A(f"plltran tran stop={stop} maxstep=2p errpreset=liberal method=gear2only skipdc=yes ic=\"OUTP=0.6\"")
    if save_dtc_probe:
        A("save OUTP CKFB VCTRL VHOLD EBIT VRAMP CK2X CKDTCD REF Xdtc.VDLY")
    else:
        A("save OUTP CKFB VCTRL VI VHOLD EBIT MMDIN NBUF1 VREF VDCC RDCC KDTC VRAMP SEL EPSC CK2X CKDTCD CKRST")
    out = OUT / f"pll_{name}.scs"
    out.write_text("\n".join(L))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["step1", "step2"])
    ap.add_argument("--chan", default="main", choices=["main", "nearint"])
    ap.add_argument("--stop", default="300n")
    ap.add_argument("--single-core", action="store_true")
    ap.add_argument("--strobe", default=None)
    ap.add_argument("--dtcprobe", action="store_true")
    args = ap.parse_args()
    name = f"{args.step}_{args.chan}"
    out = gen(name, args.stop, not args.single_core, args.strobe, getattr(args, "dtcprobe", False))
    print(f"wrote {out}")
