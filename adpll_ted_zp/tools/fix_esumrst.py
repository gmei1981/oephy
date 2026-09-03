#!/usr/bin/env python3
"""Fix Esumrst in adpll_top schematic: swap out- (MINUS) and in- (NC-) nets.

Bug found by deck review (set-based compare can't see +/- node swaps):
  schematic: MINUS->gnd!, NC-->VDC08  =>  CKRST = CKRSTI - 0.8
  reference (sim/pll_step2_main.scs): Esumrst (CKRST VDC08 CKRSTI 0)
  =>  CKRST = VDC08 + CKRSTI  (0.8 level shift, verified in tb_spd_x)
  With CKRST in [-1.6,-0.8] the NMOS reset switch MRST is hard off ->
  SPD ramp never resets -> dead loop.

Fix: geometry-scoped delete of the stub wire+label at each terminal
(net-wide delete is unsafe here: gnd! is everywhere, VDC08 also feeds
the pin stub), then relabel MINUS->VDC08, NC-->gnd!.
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

# 1. delete stub wire+label at MINUS (net gnd!) and NC- (net VDC08)
for iname, tname, net in (("Esumrst", "MINUS", "gnd!"),
                          ("Esumrst", "NC-", "VDC08")):
    sk = DEL_TMPL.format(open=OPEN, iname=iname, tname=tname, net=net)
    r = client.execute_skill(sk, timeout=120)
    print(f"delete {iname}.{tname} ({net}):", r.status, r.output)

# 2. relabel: MINUS -> VDC08, NC- -> gnd! (cv must be bound; same wrapper
#    pattern as rebuild_cmp_nets.py phase 2)
CV = "let((cv) cv = " + OPEN + " "
for iname, tname, net in (("Esumrst", "MINUS", "VDC08"),
                          ("Esumrst", "NC-", "gnd!")):
    sk = CV + label(iname, tname, net, cosmetic="clean", auto_rotation=True) + ")"
    r = client.execute_skill(sk, timeout=120)
    print(f"relabel {iname}.{tname} -> {net}:", r.status, r.output)

# 3. check + save
r = client.execute_skill(
    f'let((cv) cv = {OPEN} list(schCheck(cv) dbSave(cv) cv~>shapes~>objType))',
    timeout=120)
print("check+save:", r.status, r.output)
