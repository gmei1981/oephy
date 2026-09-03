#!/usr/bin/env python3
"""Direct moscap C-V measurement: gate at 0.8V DC (tank DC), bulk swept.

C measured via 1GHz small-signal current into the gate:
  C = |I| / (2*pi*f * |Vg_1GHz|),  |Vg| via FFT at 1GHz.
Sweep VB -1.0..1.4 step 0.05 (49 pts), devices: moscap_rf and moscap_rf_nw.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sim" / "cvdirect"

TMPL = """// cvdirect {tag}
simulator lang=spectre
include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt
Vg (g0 0) vsource dc=0.8
Rser (g0 g) resistor r=1M
Vb (b 0) vsource dc={vb}
X1 (g b b) {dev} wr=538n nfin=12 lr=200n gr=2 br=2 multi=1
I1 (0 g) isource type=sine freq=1e9 ampl=1u
cvtran tran stop=4n maxstep=1p errpreset=liberal method=gear2only
save g
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for dev in ("moscap_rf", "moscap_rf_nw"):
        d = OUT / dev
        d.mkdir(exist_ok=True)
        for vb in [round(-1.0 + 0.05 * i, 3) for i in range(49)]:
            tag = f"{dev}_{int(vb * 100):+04d}"
            (d / f"cv_{tag}.scs").write_text(TMPL.format(tag=tag, vb=f"{vb}", dev=dev))
            n += 1
    print(f"wrote {n} testbenches under {OUT}")


if __name__ == "__main__":
    main()
