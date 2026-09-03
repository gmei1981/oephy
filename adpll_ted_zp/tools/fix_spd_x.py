#!/usr/bin/env python3
"""Fix spd_x schematic to match reference scs:
1. RREF l: 25u -> 38u (already done via dbReplaceProp in-session; redo idempotently)
2. Rename internal bias net net11 -> VBSPD_M by labeling RREF.PLUS
3. schCheck + dbSave
"""
from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.schematic.ops import schematic_label_instance_term

client = VirtuosoClient(host="127.0.0.1", port=65418)

CV_BIND = "let((cv) cv = geGetEditCellView() "

# 1. RREF l=38u (idempotent; already set in a previous step)
r = client.execute_skill(
    CV_BIND
    + "dbReplaceProp(car(setof(i cv~>instances i~>name == \"RREF\")) \"l\" \"string\" \"38u\") "
    + "car(setof(i cv~>instances i~>name == \"RREF\"))~>l)",
    timeout=30,
)
print("RREF l ->", r.output)

# 2. Label RREF.PLUS as VBSPD_M (renames the whole net)
label_skill = schematic_label_instance_term(
    "RREF", "PLUS", "VBSPD_M", cosmetic="clean", auto_rotation=True, cv_expr="cv"
)
r = client.execute_skill(CV_BIND + label_skill + ")", timeout=30)
print("label status:", r.status, r.output)

# 3. Verify net rename
r = client.execute_skill(
    CV_BIND
    + "list(length(setof(x cv~>nets x~>name == \"VBSPD_M\")) "
    + "length(setof(x cv~>nets x~>name == \"net11\"))) )",
    timeout=30,
)
print("nets [VBSPD_M, net11] ->", r.output)

# 4. Check & save
r = client.execute_skill(CV_BIND + "schCheck(cv))", timeout=60)
print("schCheck ->", r.output)
r = client.execute_skill(CV_BIND + "dbSave(cv))", timeout=60)
print("dbSave ->", r.output)
