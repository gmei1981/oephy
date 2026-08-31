#!/usr/bin/env python3
"""Fix cmp_x schematic to match reference scs:

Diff found:
1. ALL 7 MOS: fingers=1 -> must be 2 (reference nf=2)
2. MP2.G connected to net19(OUTP1) -> must be OUTN1 (mirror gate)
3. MTAIL.B floating (net16) -> must be VSS
4. Internal net names net014/net10/net19 -> OUTN1/TAILN/OUTP1 (wire labels)
"""
from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.schematic.ops import schematic_label_instance_term as label

client = VirtuosoClient(host="127.0.0.1", port=65418)

OPEN = 'dbOpenCellViewByType("adpll_sch" "cmp_x" "schematic" "schematic" "a")'
CV = "let((cv) cv = " + OPEN + " "

# ---------- Phase 1: delete + recreate MP2 (fix gate) and MTAIL (fix bulk) ----------
phase1 = CV + """
mp2xy = car(setof(i cv~>instances i~>name == "MP2"))~>xy
mtailxy = car(setof(i cv~>instances i~>name == "MTAIL"))~>xy
dbDeleteObject(car(setof(i cv~>instances i~>name == "MP2")))
dbDeleteObject(car(setof(i cv~>instances i~>name == "MTAIL")))
dbCreateInst(cv dbOpenCellViewByType("tsmcN12" "pch_svt_mac" "symbol" "schematicSymbol" "r") "MP2" mp2xy "R0")
dbCreateInst(cv dbOpenCellViewByType("tsmcN12" "nch_svt_mac" "symbol" "schematicSymbol" "r") "MTAIL" mtailxy "R0")
t)"""
r = client.execute_skill(phase1, timeout=60)
print("phase1 recreate:", r.status, r.output)

# ---------- Phase 2: fingers=2 (+ nf=2) on all 7 MOS ----------
phase2 = CV + """
foreach(n '("MN1" "MN2" "MN3" "MTAIL" "MP1" "MP2" "MP3")
  let((ii)
    ii = car(setof(i cv~>instances i~>name == n))
    dbReplaceProp(ii "fingers" "string" "2")
    dbReplaceProp(ii "nf" "string" "2")))
t)"""
r = client.execute_skill(phase2, timeout=60)
print("phase2 fingers:", r.status, r.output)

# ---------- Phase 3: wire labels (rename nets + connect recreated terminals) ----------
labels = [
    ("MN1", "D", "OUTN1"),   # renames net014
    ("MN2", "S", "TAILN"),   # renames net10
    ("MN2", "D", "OUTP1"),   # renames net19
    ("MP2", "D", "OUTP1"),
    ("MP2", "G", "OUTN1"),   # mirror gate -> diode node
    ("MP2", "S", "VDD"),
    ("MP2", "B", "VDD"),
    ("MTAIL", "D", "TAILN"),
    ("MTAIL", "G", "VBIAS"),
    ("MTAIL", "S", "VSS"),
    ("MTAIL", "B", "VSS"),   # bulk -> VSS (was floating)
]
lab_skill = " ".join(
    label(iname, term, net, cosmetic="clean", auto_rotation=True, cv_expr="cv")
    for iname, term, net in labels
)
r = client.execute_skill(CV + lab_skill + ")", timeout=120)
print("phase3 labels:", r.status, r.output)

# ---------- Phase 4: check + save ----------
r = client.execute_skill(CV + "list(schCheck(cv) dbSave(cv)))", timeout=120)
print("phase4 check+save:", r.output)

# ---------- Phase 5: read-back verify ----------
data = client.schematic.read("adpll_sch", "cmp_x", include_positions=False, param_filters=None)
print("\n== after fix ==")
for inst in data["instances"]:
    p = inst.get("params", {})
    print(f"  {inst['name']} [{inst['cell']}] fingers={p.get('fingers')} nf={p.get('nf')} "
          f"nFin={p.get('nFin')} l={p.get('l')} w={p.get('w')} terms={inst.get('terms', {})}")
for netname, net in sorted((data.get("nets") or {}).items()):
    print(f"  {netname}: {net.get('connections', [])}")
