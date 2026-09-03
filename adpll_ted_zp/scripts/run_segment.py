#!/usr/bin/env python3
"""Continue a loop run from a spectre .fc final-state file (segmented continuation).

Usage: python3 scripts/run_segment.py sim/out/<prev>.raw/.fc sim/pll_step1_main.scs --stop 200n
The .fc is uploaded as an include file (bare basename) and the netlist's tran line
is rewritten with readic="<fc_basename>" + skipdc=yes.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from virtuoso_bridge.spectre.runner import SpectreSimulator, spectre_mode_args

from run_bridge import VA_FILES, INC_FILES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fc", help="path to spectre.fc from a previous run")
    ap.add_argument("netlist")
    ap.add_argument("--stop", required=True)
    ap.add_argument("--maxstep", default="2p")
    ap.add_argument("--tran-noise", action="store_true")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--mode", default="ax")
    args = ap.parse_args()

    fc_src = Path(args.fc)
    # stage a copy with a stable basename
    staged = ROOT / "sim" / "out" / "cont.fc"
    staged.parent.mkdir(exist_ok=True)
    shutil.copy(fc_src, staged)

    net_src = Path(args.netlist)
    text = net_src.read_text()
    for va in VA_FILES:
        text = re.sub(r'ahdl_include\s+".*?%s"' % re.escape(va), 'ahdl_include "%s"' % va, text)
    noise_opts = (" tranNoise=yes noisefmax=50G noiseseed=7 noisetmin=1 binnum=16 noiseruns=1"
                  if args.tran_noise else "")
    text = re.sub(r'\sic="[^"]*"', "", text)
    text = re.sub(r"\sskipdc=\S+", "", text)
    text = re.sub(r"\sreadic=\S+", "", text)
    text = re.sub(
        r"(plltran\s+tran\s+stop=\S+\s+maxstep=\S+)",
        r"\1 readic=\"cont.fc\" skipdc=yes" + noise_opts,
        text,
        count=1,
    )
    net = ROOT / "sim" / "out" / ("cont_" + net_src.name)
    net.write_text(text)

    include_files = (
        [str(ROOT / "netlist" / "va" / va) for va in VA_FILES]
        + [str(ROOT / "netlist" / "inc" / inc) for inc in INC_FILES]
        + [str(staged)]
    )
    sim = SpectreSimulator.from_env(
        spectre_args=spectre_mode_args(args.mode),
        work_dir=str(ROOT / "sim" / "out"),
        timeout=args.timeout,
        keep_remote_files=True,
    )
    print(f"[segment] {net} stop={args.stop} from {fc_src}")
    result = sim.run_simulation(str(net), {"include_files": include_files})
    print("ok =", result.ok)
    if not result.ok:
        for e in result.errors[:8]:
            print("  -", e)
    else:
        print("signals:", sorted(result.data.keys())[:20])
        print("output_dir:", result.metadata.get("output_dir"))


if __name__ == "__main__":
    main()
