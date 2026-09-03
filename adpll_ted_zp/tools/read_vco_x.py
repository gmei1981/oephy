#!/usr/bin/env python3
"""Read the hand-drawn vco_x schematic from the local Virtuoso via bridge.

Dumps full topology (instances + all params + terminal nets + pins) to
tools/vco_x_sch_dump.json and prints a compact summary.
"""
import json
from pathlib import Path

from virtuoso_bridge import VirtuosoClient

ROOT = Path(__file__).resolve().parent.parent

client = VirtuosoClient(host="127.0.0.1", port=65418)

data = client.schematic.read(
    "adpll_sch", "vco_x", include_positions=False, param_filters=None
)

out = ROOT / "tools" / "vco_x_sch_dump.json"
out.write_text(json.dumps(data, indent=2, default=str))
print(f"dumped -> {out}")

# compact summary
print("\n== INSTANCES ==")
for inst in data.get("instances", []):
    name = inst.get("name")
    cell = inst.get("cell")
    terms = inst.get("terms", {})
    termstr = ", ".join(f"{t}={terms[t]}" for t in sorted(terms))
    print(f"  {name} [{cell}]  terms: {termstr}")
    params = inst.get("params", {})
    for k, v in params.items():
        print(f"      {k} = {v}")

print("\n== NETS ==")
for netname, net in sorted((data.get("nets") or {}).items()):
    conns = net.get("connections", [])
    print(f"  {netname}: {conns}")

print("\n== PINS ==")
for pinname, pin in sorted((data.get("pins") or {}).items()):
    print(f"  {pinname}: dir={pin.get('direction')}")
