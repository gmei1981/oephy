#!/usr/bin/env python3
"""VCO varactor batch 5: regular-transistor varactors (NMOS/PMOS).

G=VCTRL (quiet DC), D=S=tank node, bulk at staggered DC biases.
Configs (vco_x, CF nr=192):
  N1: 1 NMOS nf=32, B=VSS(0)          -> transition ~0-0.35V
  N2: 1 NMOS nf=32, B=0.4             -> transition ~0.4-0.75V
  N3: 2 NMOS nf=32, B=0 and B=0.4     -> staircase 0-0.75V
  N4: 2 NMOS nf=32, B=0.2 and B=0.6
  P1: 1 PMOS nf=32, B=VDD(0.8)        -> transition ~0.35-0.8V
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INC = ROOT / "netlist" / "inc"
OUT = ROOT / "sim" / "vcotune5"

VCTRLS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

MOS_TAIL = (" sd=74n sa=90n sb=90n ploda1=16n ploda2=0 ploda3=0 plodb1=16n "
            "plodb2=0 plodb3=0 nf_flag=1 smbt=1M smbb=1M dinsaflag=0 ppitch=0 "
            "spot=103n spob=103n spotl1=103n spobl1=103n spotl2=103n "
            "spobl2=103n spotr1=103n spobr1=103n spotr2=103n spobr2=103n")

CONFIGS = {
    "N1": [("nch_svt_mac", "0")],
    "N2": [("nch_svt_mac", "0.4")],
    "N3": [("nch_svt_mac", "0"), ("nch_svt_mac", "0.4")],
    "N4": [("nch_svt_mac", "0.2"), ("nch_svt_mac", "0.6")],
    "P1": [("pch_svt_mac", "0.8")],
}

TMPL = """// vcotune5 {tag}
simulator lang=spectre
include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt
include "vco_x_tuned.scs"
Vvdd (VDD 0) vsource dc=0.8
Vvss (VSS 0) vsource dc=0
Vctrl (VCTRL 0) vsource dc={vctrl}
Xvco (VDD VSS VCTRL OUTP OUTN) vco_x
vctran tran stop=12n maxstep=1p errpreset=liberal method=gear2only
save OUTP
"""


def var_bank(net: str, cells) -> str:
    lines = []
    for k, (dev, vb) in enumerate(cells):
        bn = f"B_{net}_{k}"
        lines.append(f"MV_{net}_{k} ({net} VCTRL {net} {bn}) {dev} l=16n nfin=2 w=58n "
                     f"multi=1 nf=32{MOS_TAIL}")
        lines.append(f"Vb_{net}_{k} ({bn} 0) vsource dc={vb}")
    return "\n".join(lines)


def main():
    src = (INC / "vco_dual.scs").read_text()
    vco_x_src = src.split("subckt vco_dual")[0]
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for cfg, cells in CONFIGS.items():
        v = re.sub(r"CV1 \(OUTN VCTRL VCTRL\) moscap_rf[^\n]*\n\s*[^\n]*\n", "", vco_x_src)
        v = re.sub(r"CV0 \(OUTP VCTRL VCTRL\) moscap_rf[^\n]*\n\s*[^\n]*\n", "", v)
        bank = var_bank("OUTN", cells) + "\n" + var_bank("OUTP", cells)
        v = v.replace("ends vco_x", bank + "\nends vco_x", 1)
        d = OUT / cfg
        d.mkdir(exist_ok=True)
        (d / "vco_x_tuned.scs").write_text(v)
        for vt in VCTRLS:
            (d / f"tune_{cfg}_{int(vt * 10)}.scs").write_text(
                TMPL.format(tag=f"{cfg}_{int(vt * 10)}", vctrl=f"{vt}"))
            n += 1
    print(f"wrote {n} testbenches under {OUT}")


if __name__ == "__main__":
    main()
