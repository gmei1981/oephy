#!/usr/bin/env python3
"""si batch export of tb_adpll_top schematic (same recipe as export_dtc_10b.py).

Export -> tools/tb_adpll_top_sch_netlist.scs, then compare vs saved export
(sanity: current schematic state == snapshot used for the 30/30 comparison).
"""
import subprocess
import sys
from pathlib import Path

from virtuoso_bridge import VirtuosoClient

ROOT = Path(__file__).resolve().parent.parent
RUN = "/tmp/si_tb_adpll_top"
CDSLIB = ROOT / "virtuoso_ws" / "cds.lib"

client = VirtuosoClient(host="127.0.0.1", port=65418)

r = client.execute_skill("1+1", timeout=10)
if "SUCCESS" not in str(r.status) or not r.output:
    print("channel dead")
    sys.exit(2)

# 1. fresh run dir via simInitEnvWithArgs (it creates the dir itself)
r = client.execute_skill(f'sh("rm -rf {RUN}")', timeout=30)
print("rm -rf ->", r.status, r.output)
r = client.execute_skill(
    f'simInitEnvWithArgs("{RUN}" "adpll_sch" "tb_adpll_top" "schematic" "spectre" nil)',
    timeout=120,
)
print("simInitEnvWithArgs ->", r.status, r.output)

# 2. append required si.env fields
env_path = Path(RUN) / "si.env"
env = env_path.read_text()
extra = """
simViewList = '("spectre cmos_sch schematic veriloga")
simStopList = '("spectre")
simNetlistHier = t
"""
if "simViewList" not in env:
    env_path.write_text(env + extra)
    print("si.env patched")
else:
    print("si.env already patched")

# 3. run si batch netlist (local)
r = subprocess.run(
    ["si", "-batch", "-cdslib", str(CDSLIB), "-command", "nl"],
    cwd=RUN, capture_output=True, text=True, timeout=900,
)
print("si exit:", r.returncode)
if r.returncode != 0:
    print("si stdout:", r.stdout[-800:])
    print("si stderr:", r.stderr[-800:])
    sys.exit(1)

netlist = Path(RUN) / "netlist"
if not netlist.exists():
    print("no netlist produced")
    sys.exit(1)
out = ROOT / "tools" / "tb_adpll_top_sch_netlist.scs"
old = out.read_text()  # snapshot used for the 30/30 comparison
new = netlist.read_text()
out.write_text(new)
print(f"exported -> {out}")

# 4. compare vs the saved snapshot used for the 30/30 verification
import difflib
if old == new:
    print("identical to saved snapshot")
else:
    diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm=""))
    print(f"DIFFERS from saved snapshot ({len(diff)} lines):")
    print("\n".join(diff[:80]))
