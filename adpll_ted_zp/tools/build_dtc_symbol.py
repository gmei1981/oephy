#!/usr/bin/env python3
"""Build dtc_10b symbol via bridge (manual symbol API; native generator
uses dbFindOpenCellViewByName which IC618 lacks).

11 pins on the left edge, creation + termOrder = reference subckt header:
CK_IN CK_OUT VDD VSS CKFB KDTC EPSC SEL ALT VDCC RDCC
"""
import sys

from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.symbol import (
    symbol_create_instance_label,
    symbol_create_logical_label,
    symbol_create_pin,
    symbol_create_rect,
    symbol_create_selection_box,
    symbol_set_term_order,
)

client = VirtuosoClient(host="127.0.0.1", port=65418)

PINS = [
    ("CK_IN", "input"),
    ("CK_OUT", "output"),
    ("VDD", "inputOutput"),
    ("VSS", "inputOutput"),
    ("CKFB", "input"),
    ("KDTC", "input"),
    ("EPSC", "input"),
    ("SEL", "input"),
    ("ALT", "input"),
    ("VDCC", "input"),
    ("RDCC", "input"),
]

r = client.execute_skill("1+1", timeout=10)
if "SUCCESS" not in str(r.status) or not r.output:
    print("channel dead")
    sys.exit(2)

with client.symbol.create("adpll_sch", "dtc_10b", timeout=120) as sym:
    sym.add(symbol_create_rect("device", "drawing", -0.5, -1.5, 0.5, 1.5))
    for i, (name, direction) in enumerate(PINS):
        y = 1.25 - i * 0.25
        sym.add(symbol_create_pin(name, -0.5, y, direction=direction,
                                  label_x=-0.35, label_y=y))
    sym.add(symbol_create_instance_label(0.0, 0.5))
    sym.add(symbol_create_logical_label(0.0, 0.05))
    sym.add(symbol_create_selection_box(-0.75, -1.75, 0.75, 1.75))
    sym.add(symbol_set_term_order([p[0] for p in PINS]))

# verify: terminals + termOrder readback
r = client.execute_skill(
    'let((cv) cv = dbOpenCellViewByType("adpll_sch" "dtc_10b" "symbol" "schematicSymbol" "r") '
    'list(mapcar(lambda((tm) tm~>name) cv~>terminals) cv~>termOrder))', timeout=60)
print("terminals / termOrder:", r.status, r.output)
