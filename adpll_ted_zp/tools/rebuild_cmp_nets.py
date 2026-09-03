#!/usr/bin/env python3
"""Rebuild cmp_x OUTN1/OUTP1 nets from scratch:
1. delete all wires + labels on OUTN1/OUTP1
2. re-label terminals with fresh stubs (labels bind nets by name)
3. schCheck + dbSave + read-back
"""
from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.schematic.ops import schematic_label_instance_term as label

client = VirtuosoClient(host="127.0.0.1", port=65418)
OPEN = 'dbOpenCellViewByType("adpll_sch" "cmp_x" "schematic" "schematic" "a")'
CV = "let((cv) cv = " + OPEN + " "

# 1. delete wires and labels on both nets
phase1 = CV + """
foreach(n '("OUTN1" "OUTP1")
  let((nt)
    nt = car(setof(x cv~>nets x~>name == n))
    when(nt
      foreach(s setof(sh cv~>shapes sh~>objType == "line" && sh~>net == nt)
        dbDeleteObject(s))
      foreach(s setof(sh cv~>shapes sh~>objType == "label" && sh~>net == nt)
        dbDeleteObject(s)))))
t)"""
r = client.execute_skill(phase1, timeout=60)
print("phase1 delete:", r.status, r.output)

# 2. re-label: OUTN1 = {MN1.D, MP1.D(==G), MP2.G}; OUTP1 = {MN2.D, MN3.G, MP3.G, MP2.D}
labels = [
    ("MN1", "D", "OUTN1"),
    ("MP1", "D", "OUTN1"),
    ("MP2", "G", "OUTN1"),
    ("MN2", "D", "OUTP1"),
    ("MN3", "G", "OUTP1"),
    ("MP3", "G", "OUTP1"),
    ("MP2", "D", "OUTP1"),
]
lab_skill = " ".join(
    label(iname, term, net, cosmetic="clean", auto_rotation=True, cv_expr="cv")
    for iname, term, net in labels
)
r = client.execute_skill(CV + lab_skill + ")", timeout=120)
print("phase2 labels:", r.status)

# 3. check + save
r = client.execute_skill(CV + "list(schCheck(cv) dbSave(cv)))", timeout=120)
print("phase3 check+save:", r.output)

# 4. read-back
data = client.schematic.read("adpll_sch", "cmp_x", include_positions=False, param_filters=None)
print("\n== read-back ==")
for netname in ("OUTN1", "OUTP1", "TAILN"):
    net = (data.get("nets") or {}).get(netname)
    print(f"  {netname}: {net.get('connections', []) if net else 'MISSING'}")
