#!/usr/bin/env python3
"""Regenerate netlist/inc/dtc_10b.scs for plan A' (decoder inside DTC).

Old: subckt dtc_10b (CK_IN CK_OUT VDD VSS CODE0..CODE1022), decoder was a
top-level Xdec instance with 1023 shared c<i> nets.
New: decoder instance Xdec moved INSIDE dtc_10b; subckt ports are the 11
external signals (CK_IN CK_OUT VDD VSS CKFB KDTC EPSC SEL ALT VDCC RDCC);
internal switch-gate nets renamed CODE<i> -> c<i> (VA port names).

Decoder params hardcoded to step2 (8G) values:
fout=8.000000e+09 fref=1.000000e+08 frac2=0.0 Tres=3.300000e-16
(step1 reuse would need these edited — 8G schematic project assumption).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "netlist" / "inc" / "dtc_10b.scs"

NSW = 1023

def mos(model, nf):
    return (f"{model} l=16n nfin=2 w=58n multi=1 nf={nf}  sd=74n sa=90n sb=90n "
            "ploda1=16n ploda2=0 ploda3=0 plodb1=16n \\\n"
            "        plodb2=0 plodb3=0 nf_flag=1 smbt=1M smbb=1M dinsaflag=0 ppitch=0 \\\n"
            "        spot=103n spob=103n spotl1=103n spobl1=103n spotl2=103n \\\n"
            "        spobl2=103n spotr1=103n spobr1=103n spotr2=103n spobr2=103n")


def xdec_line():
    L = ["Xdec (CKFB KDTC EPSC SEL ALT VDCC RDCC \\"]
    for i in range(0, NSW, 16):
        row = " ".join(f"c{j}" for j in range(i, min(i + 16, NSW)))
        L.append("    " + row + " \\")
    L.append("    ) pll_dtc_decoder_10b \\")
    L.append("    fout=8.000000e+09 fref=1.000000e+08 frac2=0.0 Tres=3.300000e-16 vth=0.5")
    return "\n".join(L)


def main():
    lines = [
        "// dtc_10b.scs — 10-bit RC DTC, switched-cap bank (1023 units) — plan A'",
        "// decoder (pll_dtc_decoder_10b) moved INSIDE the DTC block:",
        "//   subckt ports = 11 external signals; 1023 switch gates are internal c<i> nets",
        "// unit: NMOS switch nf=2 + CLSB=0.5fF; R0 rhim 2.3u x 2u",
        "// paper: Tres = ln2*R*CLSB = 330 fs, full DR ~ 338 ps",
        "// reset: CK_IN low -> CKXB high -> MRST_D slams VDLY to VSS (prevents charge",
        "// re-injection from UCAP caps during discharge = the edge-dropping bug)",
        "// decoder params: step2 8G (fout=8e9 fref=100M frac2=0 Tres=330fs)",
        "subckt dtc_10b (CK_IN CK_OUT VDD VSS CKFB KDTC EPSC SEL ALT VDCC RDCC)",
        "",
        xdec_line(),
        "",
        "R0 (CK_IN VDLY) rhim l=2.3e-06 w=2e-06 multi=1",
        "MNI (CKXB CK_IN VSS VSS) " + mos("nch_svt_mac", 1),
        "MPI (CKXB CK_IN VDD VDD) " + mos("pch_svt_mac", 1),
        "MRST_D (VDLY CKXB VSS VSS) " + mos("nch_svt_mac", 2),
        "",
    ]
    for i in range(NSW - 1, -1, -1):
        lines.append(f"U{i} (VDLY c{i} UCAP{i} VSS) " + mos("nch_svt_mac", 2))
        lines.append(f"C{i} (UCAP{i} VSS) capacitor c=5e-16")
    lines.append("")
    lines.append("MN1 (CK_OUT VDLY VSS VSS) " + mos("nch_svt_mac", 8))
    lines.append("MP1 (CK_OUT VDLY VDD VDD) " + mos("pch_svt_mac", 8))
    lines.append("ends dtc_10b")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
