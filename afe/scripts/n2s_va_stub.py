#!/usr/bin/env python3
"""Build the afe_tb VA leaf (stub schematic + symbol + disk veriloga view)
in afe_sch, completing the VA-leaf trio for the legacy tb_afe_va TB.

Same pattern as the 5 existing leaves (pitfall 25-1): the schematic is a
pins-only skeleton the si netlister can emit as an empty subckt; the real
module comes from the disk va/afe_tb.va via ahdl_include at assembly time.
The inert DM veriloga view is replicated at file level (master.tag+data.dm
copied from afe_ber_chk, veriloga.va replaced).

Run from /tmp (local-mode bridge):
  cd /tmp && /home/gmei/pi_project/.venv/bin/python <this>
"""
import re
import shutil
import sys
from pathlib import Path

from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.symbol import (
    symbol_create_label,
    symbol_create_pin,
    symbol_create_selection_box,
    symbol_read_ports_skill,
    symbol_set_term_order,
)
from virtuoso_bridge.virtuoso.schematic import schematic_create_pin as pin

AFE = Path("/home/gmei/git/oephy/afe")
LIB = "afe_sch"
CELL = "afe_tb"
VA = AFE / "va" / f"{CELL}.va"
GRID = 1.5


def module_ports(path):
    m = re.search(r"module\s+\w+\s*\(([^)]*)\)", path.read_text())
    return [p.strip() for p in m.group(1).replace("\n", " ").split(",")]


def main():
    client = VirtuosoClient.from_env()
    r = client.execute_skill(f'ddGetObj("{LIB}" "{CELL}")!=nil')
    if (r.output or "").strip().strip('"') in ("t", "True"):
        sys.exit(f"[abort] {LIB}/{CELL} already exists")

    ports = module_ports(VA)
    print(f"{CELL}: {len(ports)} module ports: {ports}")

    with client.schematic.create(LIB, CELL) as sch:
        for i, p in enumerate(ports):
            sch.add(pin(p, -1 * GRID, i * GRID, "R0", direction="output"))

    # manual symbol build (the native generate pipeline's SKILL helper is
    # not loaded in this session; leaf conventions: 0.25 pin pitch, pin/
    # drawing rects + pin/label names, instance/drawing selection box)
    left, right = ports[:5], ports[5:]
    parts = []
    for i, p in enumerate(left):
        parts.append(symbol_create_pin(
            p, -1.5, 0.5 - 0.25 * i, direction="output",
            label_justification="centerRight", label_x=-1.6))
    for i, p in enumerate(right):
        parts.append(symbol_create_pin(
            p, 1.5, 0.5 - 0.25 * i, direction="output",
            label_justification="centerLeft", label_x=1.6))
    parts.append(symbol_create_selection_box(-1.5, -0.75, 1.5, 0.75))
    parts.append(symbol_create_label(
        "pin", "label", 0.0, 0.9, CELL, "centerCenter", "R0", "stick",
        0.125))
    parts.append(symbol_set_term_order(ports))
    res = client.execute_skill(
        f'let((cv) cv=dbOpenCellViewByType("{LIB}" "{CELL}" "symbol" '
        f'"schematicSymbol" "a") ' + " ".join(parts) + " dbSave(cv) )")
    print("symbol build:", (res.output or "").strip()[:40],
          (res.errors or [])[:1])

    # inert DM veriloga view at file level (pattern copy from afe_ber_chk)
    src = AFE / "virtuoso_ws" / LIB / "afe_ber_chk" / "veriloga"
    dst = AFE / "virtuoso_ws" / LIB / CELL / "veriloga"
    dst.mkdir(parents=True, exist_ok=True)
    for f in ("master.tag", "data.dm"):
        shutil.copy2(src / f, dst / f)
    shutil.copy2(VA, dst / "veriloga.va")
    print(f"veriloga view: copied master.tag/data.dm + va -> {dst}")

    # readback: views + pins
    views = client.fetch(f'ddGetObj("{LIB}" "{CELL}")~>views', ["name"])
    data = client.schematic.read(LIB, CELL)
    print("views:", sorted(v["name"] for v in views))
    print("pins:", sorted(data.get("pins", {})))
    assert set(data.get("pins", {})) == set(ports)
    print(f"[{CELL}] stub trio complete (sch+sym+veriloga view)")


if __name__ == "__main__":
    main()
