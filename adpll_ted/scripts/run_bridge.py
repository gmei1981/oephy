#!/usr/bin/env python3
"""Run a spectre netlist on server 21 via virtuoso-bridge.

Usage:
  python3 scripts/run_bridge.py sim/smoke.scs [--stop <stop_time>] [--maxstep <s>] [--timeout <s>]
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from virtuoso_bridge.spectre.runner import SpectreSimulator, spectre_mode_args

VA_FILES = [
    "pll_mmd_edge.va",
    "pll_lms.va",
    "pll_dtc_decoder_10b.va",
    "pll_hybrid_aux.va",
    "constants.vams",
    "disciplines.vams",
]

INC_FILES = [
    "dtc_10b.scs",
    "vco_dual.scs",
    "vco_dual_8g.scs",
    "vco_c.scs",
    "vco_c_nols.scs",
    "vco_c_novar.scs",
    "vco_c_svt.scs",
    "ldo_05.scs",
    "spd_cmp_gm.scs",
]


def prep_netlist(src: Path, stop: str, maxstep: str) -> Path:
    """Rewrite VA include paths to bare names and adjust tran stop/maxstep."""
    text = src.read_text()
    for va in VA_FILES:
        text = re.sub(r'ahdl_include\s+".*?%s"' % re.escape(va), 'ahdl_include "%s"' % va, text)
    if stop:
        text = re.sub(r"(plltran\s+tran\s+stop=)[0-9.eE+-]+u?n?p?m?", r"\g<1>%s " % stop, text)
    if maxstep:
        text = re.sub(r"(plltran\s+tran\s+stop=\S+\s+maxstep=)[0-9.eE+-]+[unmp]?", r"\g<1>%s" % maxstep, text)
    out = Path("sim") / ("run_" + src.name)
    out.write_text(text)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("--stop", default=None, help="override tran stop")
    ap.add_argument("--maxstep", default=None, help="override tran maxstep")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--mode", default="ax", choices=["spectre", "aps", "cx", "ax", "mx"])
    args = ap.parse_args()

    src = Path(args.netlist)
    net = prep_netlist(src, args.stop, args.maxstep)

    sim = SpectreSimulator.from_env(
        spectre_args=spectre_mode_args(args.mode),
        work_dir=str(ROOT / "sim" / "out"),
        timeout=args.timeout,
        keep_remote_files=True,
    )
    print(f"[bridge] run {net} (stop={args.stop or 'as-is'}, mode={args.mode}, timeout={args.timeout}s)")
    include_files = (
        [str(ROOT / "netlist" / "va" / va) for va in VA_FILES]
        + [str(ROOT / "netlist" / "inc" / inc) for inc in INC_FILES]
    )
    result = sim.run_simulation(
        str(net),
        {"include_files": include_files},
    )
    print(f"ok={result.ok}")
    if result.ok:
        print("signals:", sorted(result.data.keys())[:40])
        print("timings:", result.metadata.get("timings"))
        print("output_dir:", result.metadata.get("output_dir"))
    else:
        print("ERRORS:")
        for e in result.errors:
            print(" -", e)


if __name__ == "__main__":
    main()
