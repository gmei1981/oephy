#!/usr/bin/env python3
"""Fix gm_x schematic to match reference scs:

1. MP2 l=16n -> 72n (reference: GM mirror 1/4.5)
2. MTAIL.B / MN1.B / MN2.B floating -> VSS
3. internal net names: net13 -> OUTN, net15 -> TAILN
"""
from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.schematic.ops import schematic_label_instance_term as label

client = VirtuosoClient(host="127.0.0.1", port=65418)
OPEN = 'dbOpenCellViewByType("adpll_sch" "gm_x" "schematic" "schematic" "a")'
CV = "let((cv) cv = " + OPEN + " "

# 1. MP2 l=72n
r = client.execute_skill(
    CV + 'dbReplaceProp(car(setof(i cv~>instances i~>name == "MP2")) "l" "string" "72n") '
    'car(setof(i cv~>instances i~>name == "MP2"))~>l)', timeout=30)
print("MP2 l ->", r.output)

# 2+3. labels: bulk -> VSS, net renames
labels = [
    ("MTAIL", "B", "VSS"),
    ("MN1", "B", "VSS"),
    ("MN2", "B", "VSS"),
    ("MN1", "D", "OUTN"),
    ("MN2", "S", "TAILN"),
]
lab_skill = " ".join(
    label(iname, term, net, cosmetic="clean", auto_rotation=True, cv_expr="cv")
    for iname, term, net in labels
)
r = client.execute_skill(CV + lab_skill + ")", timeout=120)
print("labels:", r.status)

# check + save
r = client.execute_skill(CV + "list(schCheck(cv) dbSave(cv)))", timeout=120)
print("check+save:", r.output)

# read-back
data = client.schematic.read("adpll_sch", "gm_x", include_positions=False, param_filters=None)
print("\n== after fix ==")
for inst in data["instances"]:
    p = inst.get("params", {})
    print(f"  {inst['name']} l={p.get('l')} fingers={p.get('fingers')} terms={inst.get('terms', {})}")
for netname, net in sorted((data.get("nets") or {}).items()):
    print(f"  {netname}: {net.get('connections', [])}")
