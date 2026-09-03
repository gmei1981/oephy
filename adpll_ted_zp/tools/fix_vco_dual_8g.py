#!/usr/bin/env python3
"""Fix vco_dual_8g schematic MOS parameters to match reference scs:

1. MNEN/MPEN (inverter): fingers/nf 1 -> 2
2. MPWRB/MSWP/MSWN (switches): fingers/nf 1 -> 64

Wiring issues (MSWP/MSWN D/S crossed) are left for manual GUI fix
per established division of labor.
"""
from virtuoso_bridge import VirtuosoClient

client = VirtuosoClient(host="127.0.0.1", port=65418)

CV = 'let((cv) cv = dbOpenCellViewByType("adpll_sch" "vco_dual_8g" "schematic" "schematic" "a") '

fixes = {"MNEN": "2", "MPEN": "2", "MPWRB": "64", "MSWP": "64", "MSWN": "64"}
skill = CV + """
foreach(spec list('("MNEN" "2") '("MPEN" "2") '("MPWRB" "64") '("MSWP" "64") '("MSWN" "64"))
  let((ii)
    ii = car(setof(i cv~>instances i~>name == car(spec)))
    dbReplaceProp(ii "fingers" "string" cadr(spec))
    dbReplaceProp(ii "nf" "string" cadr(spec))))
t)"""
r = client.execute_skill(skill, timeout=60)
print("nf/fingers fix ->", r.status, r.output)

# verify
r = client.execute_skill(
    CV
    + 'mapcar(lambda((n) list(n car(setof(i cv~>instances i~>name==n))~>fingers '
    + 'car(setof(i cv~>instances i~>name==n))~>nf)) '
    + 'list("MNEN" "MPEN" "MPWRB" "MSWP" "MSWN")))',
    timeout=30,
)
print("verify:", r.output)

# schCheck + dbSave
r = client.execute_skill(CV + "schCheck(cv))", timeout=60)
print("schCheck ->", r.status, r.output)
r = client.execute_skill(CV + "dbSave(cv))", timeout=60)
print("dbSave ->", r.status, r.output)
