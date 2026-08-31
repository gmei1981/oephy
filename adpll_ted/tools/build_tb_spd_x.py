#!/usr/bin/env python3
"""Build spd_x test environment in Virtuoso:
1. Generate spd_x symbol view from schematic (native TSG generator)
2. Create tb_spd_x schematic mirroring sim/local/spd_slope.scs:
   - VDD=0.8 (V0), VSS=0 (V1), VDC08=0.8 (V2), VBSPD=0.33 (V3)
   - CKDTC vpulse: v1=0 v2=0.8 per=6.5104n pw=3.255n tr=tf=20p (V4)
   - CKFB=0 (V5)
   - CKRSTI = -CKDTC (E1 vcvs egain=-1), CKRST = CKRSTI+0.8 (E2 vcvs egain=1)
   - XSPD: VBIAS<-VBSPD, CK_RST<-CKRST, CK_SMP<-CKFB, VDD/VSS; VHOLD/VRAMP 观测
"""
from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.symbol.generator import generate_symbol_from_schematic
from virtuoso_bridge.virtuoso.schematic.ops import (
    schematic_create_inst_by_master_name as inst,
    schematic_label_instance_term as label,
)

client = VirtuosoClient(host="127.0.0.1", port=65418)

# ---------- Step 1: symbol ----------
print("== symbol generation ==")
res = generate_symbol_from_schematic(
    client, "adpll_sch", "spd_x", sort_pins="geometric", overwrite=False
)
print("symbol action:", res.action)
print("terminals:", res.terminal_names)
print("pin order:", res.pin_order)

# ---------- Step 2: tb schematic ----------
print("== tb_spd_x build ==")
# clean rebuild
client.execute_skill('when(ddGetObj("adpll_sch" "tb_spd_x") ddDeleteObj(ddGetObj("adpll_sch" "tb_spd_x")))')

INST = [
    ("V0", "vdc",   (-2.5, 2.6)),
    ("V1", "vdc",   (-2.5, 1.9)),
    ("V2", "vdc",   (-2.5, 1.2)),
    ("V3", "vdc",   (-2.5, 0.5)),
    ("V4", "vpulse",(-2.5, -0.2)),
    ("V5", "vdc",   (-2.5, -0.9)),
    ("E1", "vcvs",  (-2.5, -1.6)),
    ("E2", "vcvs",  (-2.5, -2.3)),
]
PARAMS = {
    "V0": ('dbReplaceProp(car(setof(i cv~>instances i~>name == "V0")) "vdc" "string" "0.8")'),
    "V1": ('dbReplaceProp(car(setof(i cv~>instances i~>name == "V1")) "vdc" "string" "0")'),
    "V2": ('dbReplaceProp(car(setof(i cv~>instances i~>name == "V2")) "vdc" "string" "0.8")'),
    "V3": ('dbReplaceProp(car(setof(i cv~>instances i~>name == "V3")) "vdc" "string" "0.33")'),
    "V4": (
        'progn('
        'dbReplaceProp(car(setof(i cv~>instances i~>name == "V4")) "v1" "string" "0") '
        'dbReplaceProp(car(setof(i cv~>instances i~>name == "V4")) "v2" "string" "0.8") '
        'dbReplaceProp(car(setof(i cv~>instances i~>name == "V4")) "per" "string" "6.5104n") '
        'dbReplaceProp(car(setof(i cv~>instances i~>name == "V4")) "pw" "string" "3.255n") '
        'dbReplaceProp(car(setof(i cv~>instances i~>name == "V4")) "tr" "string" "20p") '
        'dbReplaceProp(car(setof(i cv~>instances i~>name == "V4")) "tf" "string" "20p") '
        'dbReplaceProp(car(setof(i cv~>instances i~>name == "V4")) "td" "string" "0"))'
    ),
    "V5": ('dbReplaceProp(car(setof(i cv~>instances i~>name == "V5")) "vdc" "string" "0")'),
    "E1": ('dbReplaceProp(car(setof(i cv~>instances i~>name == "E1")) "egain" "string" "-1")'),
    "E2": ('dbReplaceProp(car(setof(i cv~>instances i~>name == "E2")) "egain" "string" "1")'),
}
# terminal -> net mapping (mirrors spd_slope.scs connectivity)
CONN = [
    ("V0", "PLUS", "VDD"),   ("V0", "MINUS", "VSS"),
    ("V1", "PLUS", "VSS"),   ("V1", "MINUS", "VSS"),
    ("V2", "PLUS", "VDC08"), ("V2", "MINUS", "VSS"),
    ("V3", "PLUS", "VBSPD"), ("V3", "MINUS", "VSS"),
    ("V4", "PLUS", "CKDTC"), ("V4", "MINUS", "VSS"),
    ("V5", "PLUS", "CKFB"),  ("V5", "MINUS", "VSS"),
    ("E1", "PLUS", "CKRSTI"), ("E1", "MINUS", "VSS"),
    ("E1", "NC+", "CKDTC"),  ("E1", "NC-", "VSS"),
    ("E2", "PLUS", "CKRST"), ("E2", "MINUS", "VDC08"),
    ("E2", "NC+", "CKRSTI"), ("E2", "NC-", "VSS"),
    ("XSPD", "VDD", "VDD"),  ("XSPD", "VSS", "VSS"),
    ("XSPD", "VBIAS", "VBSPD"),
    ("XSPD", "CK_RST", "CKRST"),
    ("XSPD", "CK_SMP", "CKFB"),
    ("XSPD", "VHOLD", "VHOLD"),
    ("XSPD", "VRAMP", "VRAMP"),
]

with client.schematic.create("adpll_sch", "tb_spd_x") as sch:
    sch.add(inst("adpll_sch", "spd_x", "symbol", "XSPD", 2.0, 0.0, "R0"))
    for name, cell, (x, y) in INST:
        sch.add(inst("analogLib", cell, "symbol", name, x, y, "R0"))
    for name, sk in PARAMS.items():
        sch.add(sk)
    for iname, term, net in CONN:
        sch.add(label(iname, term, net, cosmetic="clean", auto_rotation=True, cv_expr="cv"))

print("tb_spd_x built (schCheck + dbSave on exit)")

# verify topology
data = client.schematic.read("adpll_sch", "tb_spd_x", include_positions=False)
print("\ninstances:", [(i["name"], i["cell"]) for i in data["instances"]])
print("\nnets:")
for netname, net in sorted((data.get("nets") or {}).items()):
    print(f"  {netname}: {net.get('connections', [])}")
