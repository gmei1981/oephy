#!/usr/bin/env python3
"""Read vco_dual_8g + vco_x_8g schematics from the local Virtuoso via bridge.

Dumps both topologies (instances + params + terminal nets + pins) to
tools/vco_dual_8g_sch_dump.json and prints a compact summary for review.
"""
import json
from pathlib import Path

from virtuoso_bridge import VirtuosoClient

ROOT = Path(__file__).resolve().parent.parent

client = VirtuosoClient(host="127.0.0.1", port=65418)

out = {}
for cell in ("vco_x_8g", "vco_dual_8g"):
    data = client.schematic.read(
        "adpll_sch", cell, include_positions=False, param_filters=None
    )
    out[cell] = data
    print(f"\n{'='*20} {cell} {'='*20}")
    print("== INSTANCES ==")
    for inst in data.get("instances", []):
        name = inst.get("name")
        cellname = inst.get("cell")
        terms = inst.get("terms", {})
        termstr = ", ".join(f"{t}={terms[t]}" for t in sorted(terms))
        print(f"  {name} [{cellname}]  terms: {termstr}")
        params = inst.get("params", {})
        keep = {k: v for k, v in params.items()
                if k in ("l", "w", "nf", "fingers", "nfin", "nFin", "multi",
                         "nr", "wr", "lr", "r", "shield", "model")}
        for k, v in keep.items():
            print(f"      {k} = {v}")
    print("== PINS ==")
    for pinname, pin in sorted((data.get("pins") or {}).items()):
        print(f"  {pinname}: dir={pin.get('direction')}")
    print("== NETS ==")
    for netname, net in sorted((data.get("nets") or {}).items()):
        conns = net.get("connections", [])
        print(f"  {netname}: {conns}")

outpath = ROOT / "tools" / "vco_dual_8g_sch_dump.json"
outpath.write_text(json.dumps(out, indent=2, default=str))
print(f"\ndumped -> {outpath}")
