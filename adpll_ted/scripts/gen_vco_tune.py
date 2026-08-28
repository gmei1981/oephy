#!/usr/bin/env python3
"""Generate standalone VCO tuning-curve testbenches (server batch).

Tank variants (vco_x / vco_dual from vco_dual.scs):
  T0: as-is (CF nr=192)
  T1: CF nr=160
  T2: CF nr=144
  T3: varactor wr 538n -> 320n (CF unchanged)

Each netlist: VCTRL hardcoded, tran 12ns maxstep=1p, saves OUTP; f measured by FFT.
"""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INC = ROOT / "netlist" / "inc"
OUT = ROOT / "sim" / "vcotune"

VCTRLS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def tank_variant(src: str, cfg: str) -> str:
    if cfg == "T0":
        return src
    if cfg in ("T1", "T2"):
        nr = {"T1": "160", "T2": "144"}[cfg]
        return re.sub(r"nr=192", f"nr={nr}", src)
    if cfg == "T3":
        return re.sub(r"wr=538n", "wr=320n", src)
    raise ValueError(cfg)


def main():
    gm_src = (INC / "vco_dual.scs").read_text()
    tmpl = """// vcotune {tag}
simulator lang=spectre
include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt
include "vco_dual_tuned.scs"
Vvdd (VDD 0) vsource dc=0.8
Vvss (VSS 0) vsource dc=0
Vctrl (VCTRL 0) vsource dc={vctrl}
Venv2 (EN2 0) vsource dc=0.8
Xvco (VDD VSS VCTRL OUTP OUTN{en2}) {core}
vctran tran stop=12n maxstep=1p errpreset=liberal method=gear2only
save OUTP
"""
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for cfg in ("T0", "T1", "T2", "T3"):
        vco = tank_variant(gm_src, cfg)
        d = OUT / cfg
        d.mkdir(exist_ok=True)
        (d / "vco_dual_tuned.scs").write_text(vco)
        for core in ("vco_x", "vco_dual"):
            en2 = "" if core == "vco_x" else " EN2"
            for v in VCTRLS:
                tag = f"{cfg}_{core}_{int(v*10)}"
                (d / f"tune_{tag}.scs").write_text(
                    tmpl.format(tag=tag, vctrl=f"{v}", core=core, en2=en2))
                n += 1
    print(f"wrote {n} testbenches under {OUT}")


if __name__ == "__main__":
    main()
