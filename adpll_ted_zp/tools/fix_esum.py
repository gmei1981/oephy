#!/usr/bin/env python3
"""Fix Esum in adpll_top schematic: 3-terminal rotation on the vcvs.

Found by the 300ns smoke: sch VCTRL ends at -0.5476V (= VN1 - VI),
reference at +0.554V (= VN1 + VI).

  reference: Esum (VCTRL VN1 VI 0) vcvs gain=1.0   -> VCTRL = VN1 + VI
  schematic: Esum (VCTRL 0 VN1 VI) vcvs gain=1.0   -> VCTRL = VN1 - VI

Same bug class as Esumrst (set-based compare hides +/- swaps).
Fix: MINUS: gnd! -> VN1 ; NC+: VN1 -> VI ; NC-: VI -> gnd!.
"""
import sys
from pathlib import Path

from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.schematic.ops import schematic_label_instance_term as label

ROOT = Path(__file__).resolve().parent.parent

client = VirtuosoClient(host="127.0.0.1", port=65418)

OPEN = 'dbOpenCellViewByType("adpll_sch" "adpll_top" "schematic" "schematic" "a")'

DEL_TMPL = """
let((cv inst term pin fig bbox ctr)
  cv = {open}
  inst = car(setof(x cv~>instances x~>name == "{iname}"))
  term = car(setof(x inst~>master~>terminals x~>name == "{tname}"))
  pin = car(term~>pins)
  fig = when(pin car(pin~>figs))
  bbox = when(fig dbTransformBBox(fig~>bBox inst~>transform))
  ctr = when(bbox list((xCoord(car(bbox)) + xCoord(cadr(bbox))) / 2.0 (yCoord(car(bbox)) + yCoord(cadr(bbox))) / 2.0))
  when(ctr
    foreach(sh cv~>shapes
      when((sh~>objType == "line" || sh~>objType == "label")
        && sh~>net~>name == "{net}"
        && sh~>bBox
        && abs(((xCoord(car(sh~>bBox)) + xCoord(cadr(sh~>bBox))) / 2.0) - xCoord(ctr)) < 1.0
        && abs(((yCoord(car(sh~>bBox)) + yCoord(cadr(sh~>bBox))) / 2.0) - yCoord(ctr)) < 1.0
        dbDeleteObject(sh))))
  t)
"""

r = client.execute_skill("1+1", timeout=10)
if "SUCCESS" not in str(r.status) or not r.output:
    print("channel dead")
    sys.exit(2)

# 1. delete stub wire+label at the three terminals
for iname, tname, net in (("Esum", "MINUS", "gnd!"),
                          ("Esum", "NC+", "VN1"),
                          ("Esum", "NC-", "VI")):
    sk = DEL_TMPL.format(open=OPEN, iname=iname, tname=tname, net=net)
    r = client.execute_skill(sk, timeout=120)
    print(f"delete {iname}.{tname} ({net}):", r.status, r.output)

# 2. relabel: MINUS -> VN1, NC+ -> VI, NC- -> gnd!
CV = "let((cv) cv = " + OPEN + " "
for iname, tname, net in (("Esum", "MINUS", "VN1"),
                          ("Esum", "NC+", "VI"),
                          ("Esum", "NC-", "gnd!")):
    sk = CV + label(iname, tname, net, cosmetic="clean", auto_rotation=True) + ")"
    r = client.execute_skill(sk, timeout=120)
    print(f"relabel {iname}.{tname} -> {net}:", r.status, r.output)

# 3. check + save
r = client.execute_skill(f'let((cv) cv = {OPEN} list(schCheck(cv) dbSave(cv)))', timeout=120)
print("check+save:", r.status, r.output)
