#!/usr/bin/env python3
"""VCO staircase batch 4: 4 cells x 0.3V offset spacing (wider than C-V step).

Cells: wr=110n nfin=12, bulk offsets -0.3/-0.6/-0.9/-1.2
       -> first-step transitions ~VCTRL 0.25-0.7 (offset shift ~0.5x)
Configs:
  B4x192 : vco_x   CF nr=192
  B4d192 : vco_dual CF nr=192
  B4d160 : vco_dual CF nr=160
  B4d144 : vco_dual CF nr=144
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INC = ROOT / "netlist" / "inc"
OUT = ROOT / "sim" / "vcotune4"

VCTRLS = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
OFFSETS = ["0.3", "0.6", "0.9", "1.2"]
CONFIGS = {
    "B4x192": ("vco_x", "192"),
    "B4d192": ("vco_dual", "192"),
    "B4d160": ("vco_dual", "160"),
    "B4d144": ("vco_dual", "144"),
}

TMPL = """// vcotune4 {tag}
simulator lang=spectre
include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt
include "vco_tuned.scs"
Vvdd (VDD 0) vsource dc=0.8
Vvss (VSS 0) vsource dc=0
Vctrl (VCTRL 0) vsource dc={vctrl}
{en2}
Xvco (VDD VSS VCTRL OUTP OUTN{en2port}) {core}
vctran tran stop=12n maxstep=1p errpreset=liberal method=gear2only
save OUTP
"""


def staircase(net: str) -> str:
    lines = []
    for k, off in enumerate(OFFSETS):
        lines.append(
            f"CV_{net}_{k} ({net} VB_{net}_{k} VB_{net}_{k}) moscap_rf wr=110n nfin=12 lr=200n gr=2 br=2 multi=1")
        lines.append(f"E_{net}_{k} (VB_{net}_{k} VOF_{net}_{k} VCTRL 0) vcvs gain=1.0")
        lines.append(f"V_{net}_{k} (VOF_{net}_{k} 0) vsource dc=-{off}")
    return "\n".join(lines)


def main():
    src = (INC / "vco_dual.scs").read_text()
    vco_x_src = src.split("subckt vco_dual")[0]
    vco_dual_src = (src.split("ends vco_x")[0] + "ends vco_x\n" +
                    "subckt vco_dual" + src.split("subckt vco_dual")[1])
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for cfg, (core, nr) in CONFIGS.items():
        base = vco_x_src if core == "vco_x" else vco_dual_src
        v = re.sub(r"CV1 \(OUTN VCTRL VCTRL\) moscap_rf[^\n]*\n\s*[^\n]*\n", "", base)
        v = re.sub(r"CV0 \(OUTP VCTRL VCTRL\) moscap_rf[^\n]*\n\s*[^\n]*\n", "", v)
        bank = staircase("OUTN") + "\n" + staircase("OUTP")
        v = v.replace("ends vco_x", bank + "\nends vco_x", 1)
        v = v.replace("nr=192", f"nr={nr}")
        d = OUT / cfg
        d.mkdir(exist_ok=True)
        (d / "vco_tuned.scs").write_text(v)
        en2 = 'Venv2 (EN2 0) vsource dc=0.8' if core == "vco_dual" else ""
        en2port = " EN2" if core == "vco_dual" else ""
        for vt in VCTRLS:
            (d / f"tune_{cfg}_{int(vt * 10)}.scs").write_text(
                TMPL.format(tag=f"{cfg}_{int(vt * 10)}", vctrl=f"{vt}",
                            en2=en2, en2port=en2port, core=core))
            n += 1
    print(f"wrote {n} testbenches under {OUT}")


if __name__ == "__main__":
    main()
