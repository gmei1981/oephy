#!/usr/bin/env python3
"""Run VCO pnoise testbenches (dual/single core) on server 21."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from virtuoso_bridge.spectre.runner import SpectreSimulator, spectre_mode_args

sim = SpectreSimulator.from_env(
    spectre_args=spectre_mode_args("aps"),  # pnoise: sign-off accuracy
    work_dir=str(ROOT / "sim" / "vco" / "out"),
    timeout=3600,
)
incs = [str(ROOT / "netlist" / "inc" / "vco_dual.scs")]
for name in ["vco_pnoise_dual", "vco_pnoise_single"]:
    net = ROOT / "sim" / "vco" / f"{name}.scs"
    print(f"== {name} ==")
    r = sim.run_simulation(str(net), {"include_files": incs})
    print("ok =", r.ok)
    if not r.ok:
        for e in r.errors[:6]:
            print("  -", e)
