#!/usr/bin/env python3
"""Single-pass psfascii stream parser: extract named signals from a huge
text-format .tran.tran without repeated psf CLI invocations.

Usage (library): from parse_psfascii import extract -> dict[str, np.ndarray]
"""
import re
import sys
from pathlib import Path

import numpy as np

LINE = re.compile(r'^"([A-Za-z0-9_.]+)"\s+([-0-9.eE+]+)\s*$')


def extract(fname, sigs):
    want = set(sigs)
    out = {s: [] for s in sigs}
    seen = set()
    n = 0
    with open(fname, errors="replace") as f:
        inval = False
        for line in f:
            if not inval:
                if line.startswith("VALUE"):
                    inval = True
                continue
            if line.startswith("END"):
                break
            m = LINE.match(line)
            if m:
                nm = m.group(1)
                if nm in want:
                    out[nm].append(float(m.group(2)))
                    if nm not in seen:
                        seen.add(nm)
                        print(f"  first {nm} at line {n}", file=sys.stderr)
            n += 1
    return {k: np.asarray(v) for k, v in out.items()}


if __name__ == "__main__":
    f = sys.argv[1]
    sigs = sys.argv[2:]
    d = extract(f, sigs)
    np.savez(Path(f).with_suffix(".npz"), **d)
    for k, v in d.items():
        print(f"{k}: n={len(v)} last={v[-1] if len(v) else 'n/a'}")
