#!/usr/bin/env python3
"""Generate si.env for vco_x batch netlist export.

Pitfall (troubleshooting.md): simInitEnvWithArgs pops a modal dialog if the
run dir already exists -> SKILL channel blocks. Use a fresh unique dir and do
NOT pre-create it.
"""
import sys

from virtuoso_bridge import VirtuosoClient

client = VirtuosoClient(host="127.0.0.1", port=65418)

# 1. Probe channel liveness + dismiss any lingering modal dialog
r = client.execute_skill("1+1", timeout=10)
print("probe ->", r.status, r.output)
if r.status.value != "SUCCESS" or not r.output:
    print("channel dead -> run: hiFormDone(hiGetCurrentForm()) once, then rerun")
    sys.exit(2)

r = client.execute_skill("hiFormDone(hiGetCurrentForm())", timeout=10)
print("dismiss-current-form ->", r.status, r.output)

# 2. simInitEnvWithArgs into a fresh non-existent dir (no mkdir first!)
run_dir = "/tmp/si_vco_x2"
r = client.execute_skill('sh("rm -rf ' + run_dir + '")', timeout=30)
print("rm -rf ->", r.status, r.output)

r = client.execute_skill(
    f'simInitEnvWithArgs("{run_dir}" "adpll_sch" "vco_x" "schematic" "spectre" nil)',
    timeout=120,
)
print("simInitEnvWithArgs ->", r.status, r.output)
