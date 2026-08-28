#!/usr/bin/env python3
"""Local segmented continuation: rewrite tran line with readic + writefinal, run local spectre.

Usage: python3 scripts/run_local_segment.py <base_netlist> <fc_file> <stop> [--maxstep 2p] [--raw NAME]
The fc must be a text .fc checkpoint (writefinal from a previous local run).
Produces <base>_cont.scs in the same dir; spectre runs with -raw <raw> in that dir.
"""
import argparse
import re
import shutil
import subprocess
from pathlib import Path

SPECTRE = "/home/gmei/bin/spectre"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("fc")
    ap.add_argument("stop")
    ap.add_argument("--maxstep", default="2p")
    ap.add_argument("--raw", default=None)
    args = ap.parse_args()

    net = Path(args.netlist).resolve()
    fc = Path(args.fc).resolve()
    stem = net.stem.replace("_cont", "")
    out = net.with_name(f"{stem}_cont.scs")
    rawname = args.raw or f"{stem}_cont.raw"

    text = net.read_text()
    # strip previous ic/readic/writefinal, then inject
    text = re.sub(r"\sic=\"[^\"]*\"", "", text)
    text = re.sub(r"\sskipdc=\S+", "", text)
    text = re.sub(r"\sreadic=\S+", "", text)
    text = re.sub(r"\swritefinal=\S+", "", text)
    # strip startup-only stimuli that would re-fire at t=0 of the continuation
    # (Iinj: 0-2ns VI precharge pulse; refiring pumps VI/VCTRL +0.55V -> wrong equilibrium)
    text = re.sub(r"^Iinj\b.*$", "", text, flags=re.M)
    m = re.search(r"(plltran\s+tran\s+stop=\S+\s+maxstep=\S+)", text)
    if not m:
        raise SystemExit("tran line pattern not found")
    ms = re.search(r"stop=(\S+)", m.group(1))
    mx = re.search(r"maxstep=(\S+)", m.group(1))
    new = (m.group(1).replace("stop=" + ms.group(1), "stop=" + args.stop)
           .replace("maxstep=" + mx.group(1), "maxstep=" + args.maxstep)
           + ' readic="%s" skipdc=yes writefinal="%s_next.fc"' % (fc.name, fc.stem))
    text = text.replace(m.group(1), new)
    out.write_text(text)

    # stage fc next to the netlist (spectre resolves readic relative to cwd)
    dst = out.parent / fc.name
    if fc.resolve() != dst.resolve():
        shutil.copy(fc, dst)

    cmd = [SPECTRE, out.name, "-format", "psfascii", "-raw", f"./{rawname}", "+log", f"./{rawname}.log", "+mt"]
    print(f"[local segment] {out.name}  stop={args.stop}  fc={fc.name}  raw={rawname}")
    subprocess.run(cmd, cwd=out.parent)


if __name__ == "__main__":
    main()
