#!/usr/bin/env python3
"""Bake VCO tune variants: one (VI, VP) point per deck (spectre -param is broken).

Usage:
  python tools/gen_vco_c_tune.py VI=0.3 VP=0.35 [VI=0.4 VP=0.35 ...] -> sim/out_tune/*.scs
Also emits the run matrix JSON for the bridge batch.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sim" / "vco_c_tune.scs"
OUTDIR = ROOT / "sim" / "out_tune"
OUTDIR.mkdir(exist_ok=True)

base = SRC.read_text()
points = []
for arg in sys.argv[1:]:
    kv = dict(p.split("=", 1) for p in arg.replace(",", " ").split())
    vi = kv.get("VI", "0.35")
    vp = kv.get("VP", "0.35")
    deck = base.replace("parameters VI=0.35 VP=0.35",
                        f"parameters VI={vi} VP={vp}")
    fname = f"vco_c_tune_vi{vi.replace('.', 'p')}_vp{vp.replace('.', 'p')}.scs"
    (OUTDIR / fname).write_text(deck)
    points.append({"VI": float(vi), "VP": float(vp), "deck": fname})
    print("wrote", OUTDIR / fname)

(OUTDIR / "matrix.json").write_text(json.dumps(points, indent=2))
print(f"\n{len(points)} decks in {OUTDIR}, matrix.json written")
