#!/usr/bin/env python3
"""si batch export of dtc_10b schematic + compare vs netlist/inc/dtc_10b.scs.

Recipe (memory + batch-netlist-si.md):
  - simInitEnvWithArgs into a FRESH dir (no mkdir first; existing dir pops a
    modal dialog that blocks the SKILL channel)
  - si.env needs simViewList/simStopList/simNetlistHier appended
  - si -batch -cdslib <abs cds.lib> -command nl  (local IC618 binary)
"""
import subprocess
import sys
from pathlib import Path

from virtuoso_bridge import VirtuosoClient

ROOT = Path(__file__).resolve().parent.parent
RUN = "/tmp/si_dtc_10b"
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
    f'simInitEnvWithArgs("{RUN}" "adpll_sch" "dtc_10b" "schematic" "spectre" nil)',
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
    cwd=RUN, capture_output=True, text=True, timeout=600,
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
out = ROOT / "tools" / "dtc_10b_sch_netlist.scs"
out.write_text(netlist.read_text())
print(f"exported -> {out}")

# 4. compare vs reference
r = subprocess.run(
    [sys.executable, str(ROOT / "tools" / "compare_block.py"),
     str(ROOT / "netlist" / "inc" / "dtc_10b.scs"), str(out), "dtc_10b"],
    capture_output=True, text=True, timeout=300,
)
print(r.stdout)
if r.stderr:
    print("stderr:", r.stderr[-500:])
