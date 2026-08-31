#!/usr/bin/env python3
"""Fix vco_x schematic PARAMETERS to match reference scs (user authorized):

1. MN0/MN1: fingers 1 -> 16, nf 1 -> 16 (cross-coupled pair, nf=16)
2. CF0..CF11: nr 12 -> 192 (tank caps)

Wiring issues (CF0/CF6/CF9 shield floating, PLUS/MINUS swaps) are left for
manual GUI fix per user instruction.
"""
from virtuoso_bridge import VirtuosoClient

client = VirtuosoClient(host="127.0.0.1", port=65418)

CV = 'let((cv) cv = dbOpenCellViewByType("adpll_sch" "vco_x" "schematic" "schematic" "a") '

# 1. MOS fingers + nf -> 16
skill = CV + """
foreach(n '("MN0" "MN1")
  let((ii)
    ii = car(setof(i cv~>instances i~>name == n))
    dbReplaceProp(ii "fingers" "string" "16")
    dbReplaceProp(ii "nf" "string" "16")))
t)"""
r = client.execute_skill(skill, timeout=60)
print("MOS fingers/nf ->", r.status, r.output)

# verify
r = client.execute_skill(
    CV
    + 'mapcar(lambda((n) list(n car(setof(i cv~>instances i~>name==n))~>fingers '
    + 'car(setof(i cv~>instances i~>name==n))~>nf)) list("MN0" "MN1")))',
    timeout=30,
)
print("verify MOS:", r.output)

# 2. cfmom nr -> 192
skill = CV + """
foreach(n '("CF0" "CF1" "CF2" "CF3" "CF4" "CF5" "CF6" "CF7" "CF8" "CF9" "CF10" "CF11")
  let((ii)
    ii = car(setof(i cv~>instances i~>name == n))
    dbReplaceProp(ii "nr" "string" "192")))
t)"""
r = client.execute_skill(skill, timeout=60)
print("cfmom nr ->", r.status, r.output)

# verify
r = client.execute_skill(
    CV
    + 'mapcar(lambda((n) list(n car(setof(i cv~>instances i~>name==n))~>nr)) '
    + 'list("CF0" "CF6" "CF9" "CF11")))',
    timeout=30,
)
print("verify cfmom:", r.output)

# 3. schCheck + dbSave
r = client.execute_skill(CV + "schCheck(cv))", timeout=60)
print("schCheck ->", r.status, r.output)
r = client.execute_skill(CV + "dbSave(cv))", timeout=60)
print("dbSave ->", r.status, r.output)
