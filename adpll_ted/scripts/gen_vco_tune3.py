#!/usr/bin/env python3
"""VCO varactor staircase bank (batch 3) — paper-style staggered multi-cell bank.

5 cells per tank node, each moscap_rf with its own bulk offset:
  bulk_k = VCTRL - (0.2 + 0.1*k), k=0..4  -> transitions at VCTRL ~0.3..0.7
Total dC spread over 0.4V -> staircase KVCO.

Cell sizes (wr, nfin=12, lr=200n):
  S1: wr=110n -> dC~22fF total, KVCO~625M/V
  S2: wr=55n  -> dC~11fF total, KVCO~310M/V
  S3: wr=28n  -> dC~5.5fF total, KVCO~160M/V

Configs:
  S1x / S2x / S3x : vco_x single core, tank nr=192
  S2d             : vco_dual (EN2=0.8), tank nr=192
  S2n             : vco_dual, tank nr=179 (nearint 6.45G)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INC = ROOT / "netlist" / "inc"
OUT = ROOT / "sim" / "vcotune3"

VCTRLS = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
CELLS = {"S1": "110n", "S2": "55n", "S3": "28n"}
CONFIGS = {
    "S1x": ("vco_x", "192", "S1"),
    "S2x": ("vco_x", "192", "S2"),
    "S3x": ("vco_x", "192", "S3"),
    "S2d": ("vco_dual", "192", "S2"),
    "S2n": ("vco_dual", "179", "S2"),
}

TMPL = """// vcotune3 {tag}
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


def staircase(net: str, wr: str) -> str:
    """5-cell staggered bank on tank node `net`. Instance names unique per node."""
    lines = []
    for k in range(5):
        off = 0.2 + 0.1 * k
        lines.append(
            f"CV_{net}_{k} ({net} VB_{net}_{k} VB_{net}_{k}) moscap_rf wr={wr} nfin=12 lr=200n gr=2 br=2 multi=1")
        lines.append(f"E_{net}_{k} (VB_{net}_{k} VOF_{net}_{k} VCTRL 0) vcvs gain=1.0")
        lines.append(f"V_{net}_{k} (VOF_{net}_{k} 0) vsource dc=-{off:.1f}")
    return "\n".join(lines)


def main():
    src = (INC / "vco_dual.scs").read_text()
    vco_x_src = src.split("subckt vco_dual")[0]
    vco_dual_src = src.split("ends vco_x")[0] + "ends vco_x\n" + \
        "subckt vco_dual" + src.split("subckt vco_dual")[1]
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for cfg, (core, nr, size) in CONFIGS.items():
        wr = CELLS[size]
        base = vco_x_src if core == "vco_x" else vco_dual_src
        # remove original varactors
        import re
        v = re.sub(r"CV1 \(OUTN VCTRL VCTRL\) moscap_rf[^\n]*\n\s*[^\n]*\n", "", base)
        v = re.sub(r"CV0 \(OUTP VCTRL VCTRL\) moscap_rf[^\n]*\n\s*[^\n]*\n", "", v)
        # insert staircase before `ends vco_x`
        bank = staircase("OUTN", wr) + "\n" + staircase("OUTP", wr)
        v = v.replace("ends vco_x", bank + "\nends vco_x", 1)
        if nr != "192":
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
