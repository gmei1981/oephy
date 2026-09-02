#!/usr/bin/env python3
"""Repair Ep stubs in adpll_top: restore PLUS->VN1, MINUS->gnd!.

Collateral of fix_esum.py's geometry-scoped delete (radius 1.0 caught Ep's
adjacent stubs): Ep.PLUS/MINUS wires became anonymous net7/net8.
net7/net8 exist ONLY on Ep's terminals in this cellview (verified via
schematic.read), so net-wide deletion is safe. Then relabel.
"""
import sys
from pathlib import Path

from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.schematic.ops import schematic_label_instance_term as label

ROOT = Path(__file__).resolve().parent.parent

client = VirtuosoClient(host="127.0.0.1", port=65418)
OPEN = 'dbOpenCellViewByType("adpll_sch" "adpll_top" "schematic" "schematic" "a")'

r = client.execute_skill("1+1", timeout=10)
if "SUCCESS" not in str(r.status) or not r.output:
    print("channel dead")
    sys.exit(2)

# 1. net-wide delete of the two anonymous nets (rebuild_cmp_nets.py pattern)
phase1 = f"""let((cv)
  cv = {OPEN}
  foreach(n '("net7" "net8")
    let((nt)
      nt = car(setof(x cv~>nets x~>name == n))
      when(nt
        foreach(s setof(sh cv~>shapes sh~>objType == "line" && sh~>net == nt)
          dbDeleteObject(s))
        foreach(s setof(sh cv~>shapes sh~>objType == "label" && sh~>net == nt)
          dbDeleteObject(s)))))
  t)"""
r = client.execute_skill(phase1, timeout=120)
print("delete net7/net8:", r.status, r.output)

# 2. relabel Ep.PLUS -> VN1, Ep.MINUS -> gnd!
CV = "let((cv) cv = " + OPEN + " "
for iname, tname, net in (("Ep", "PLUS", "VN1"),
                          ("Ep", "MINUS", "gnd!")):
    sk = CV + label(iname, tname, net, cosmetic="clean", auto_rotation=True) + ")"
    r = client.execute_skill(sk, timeout=120)
    print(f"relabel {iname}.{tname} -> {net}:", r.status, r.output)

# 3. check + save
r = client.execute_skill(f'let((cv) cv = {OPEN} list(schCheck(cv) dbSave(cv)))', timeout=120)
print("check+save:", r.status, r.output)
