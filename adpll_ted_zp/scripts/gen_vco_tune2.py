#!/usr/bin/env python3
"""VCO varactor connection variants (batch 2) — find a real KVCO window.

Base vco_dual.scs, vco_x core only.  PDK port order: moscap_rf(gate bulk gnode).
Current: gate=OUTN (tank, 0.8V DC + swing), bulk=gnode=VCTRL
         -> C-V step at VCTRL~0.1, Cmin flat above (no tuning in 0.2-1.0V).

Variants:
  R1_swap   : gate=VCTRL (quiet), bulk/gnode=OUTN (tank)
  R2_off40  : bulk = VCTRL-0.4 (internal vcvs) -> step centered ~0.5V
  R2b_off20 : bulk = VCTRL-0.2
  R3_nw     : moscap_rf_nw device, same connection
  R4_nwswap : moscap_rf_nw, gate=VCTRL bulk=OUTN
  R5_nwoff  : moscap_rf_nw, bulk = VCTRL-0.4
  R6_series : current connection + 150fF series cap (stretch C-V)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INC = ROOT / "netlist" / "inc"
OUT = ROOT / "sim" / "vcotune2"

VCTRLS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

CFGS = {
    "R1_swap":   ("moscap_rf", "swap", None),
    "R2_off40":  ("moscap_rf", "offset", "-0.4"),
    "R2b_off20": ("moscap_rf", "offset", "-0.2"),
    "R3_nw":     ("moscap_rf_nw", "same", None),
    "R4_nwswap": ("moscap_rf_nw", "swap", None),
    "R5_nwoff":  ("moscap_rf_nw", "offset", "-0.4"),
    "R6_series": ("moscap_rf", "series", None),
}

TMPL = """// vcotune2 {tag}
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


def tune_core(src: str, cfg: str) -> str:
    dev, mode, off = CFGS[cfg]
    v = src
    v = v.replace("moscap_rf wr=", f"{dev} wr=")
    if mode == "swap":
        v = v.replace(f"CV1 (OUTN VCTRL VCTRL) {dev}", f"CV1 (VCTRL OUTN OUTN) {dev}")
        v = v.replace(f"CV0 (OUTP VCTRL VCTRL) {dev}", f"CV0 (VCTRL OUTP OUTP) {dev}")
    elif mode == "offset":
        v = v.replace(f"CV1 (OUTN VCTRL VCTRL) {dev}", f"CV1 (OUTN VB VB) {dev}")
        v = v.replace(f"CV0 (OUTP VCTRL VCTRL) {dev}", f"CV0 (OUTP VB VB) {dev}")
        v = v.replace("ends vco_x",
                      f"Eoff (VB VOFF VCTRL 0) vcvs gain=1.0\n"
                      f"Voff (VOFF 0) vsource dc={off}\nends vco_x")
    elif mode == "series":
        v = v.replace(f"CV1 (OUTN VCTRL VCTRL) {dev}", f"CV1 (VM1 VCTRL VCTRL) {dev}")
        v = v.replace(f"CV0 (OUTP VCTRL VCTRL) {dev}", f"CV0 (VM2 VCTRL VCTRL) {dev}")
        v = v.replace("ends vco_x",
                      "Cs1 (OUTN VM1) capacitor c=150f\n"
                      "Cs0 (OUTP VM2) capacitor c=150f\nends vco_x")
    return v


def main():
    src = (INC / "vco_dual.scs").read_text()
    vco_x = src.split("subckt vco_dual")[0]
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for cfg in CFGS:
        d = OUT / cfg
        d.mkdir(exist_ok=True)
        (d / "vco_x_tuned.scs").write_text(tune_core(vco_x, cfg))
        for vt in VCTRLS:
            (d / f"tune_{cfg}_{int(vt * 10)}.scs").write_text(
                TMPL.format(tag=f"{cfg}_{int(vt * 10)}", vctrl=f"{vt}"))
            n += 1
    print(f"wrote {n} testbenches under {OUT}")


if __name__ == "__main__":
    main()
