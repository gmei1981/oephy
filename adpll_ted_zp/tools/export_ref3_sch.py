#!/usr/bin/env python3
"""si batch export of ref3 analog schematic cells + compare vs references.

Cells -> reference subckt:
  ldo_05      netlist/inc/ldo_05.scs      (subckt ldo_05)
  vco_x_c_dac netlist/inc/vco_c_dac.scs   (subckt vco_x_c_dac)
  dtc_10b_ss  netlist/inc/dtc_10b_ss.scs  (subckt dtc_10b_ss)

Recipe: simInitEnvWithArgs into a FRESH dir via vlink (dialog pitfall),
patch si.env (simViewList/simStopList/simNetlistHier), local
`si -batch -cdslib <cds.lib> -command nl`, then tools/compare_block.py.

Usage: python3 tools/export_ref3_sch.py [ldo_05|vco_x_c_dac|dtc_10b_ss|all]
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CDSLIB = ROOT / "virtuoso_ws" / "cds.lib"
BRIDGE = "ref3sch"

CELLS = {
    "ldo_05": "ldo_05.scs",
    "vco_x_c_dac": "vco_c_dac.scs",
    "dtc_10b_ss": "dtc_10b_ss.scs",
}


def run(*args, timeout=900, cwd=None):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                       cwd=cwd)
    return r.returncode, (r.stdout + r.stderr)


def ev(skill, timeout=300):
    return run("vlink", "evalstring", skill, "-i", BRIDGE, "-t", str(timeout))


def export_cell(cell):
    rundir = f"/tmp/si_{cell}"
    print(f"[{cell}] export -> {rundir}")

    rc, out = ev(f'sh("rm -rf {rundir}")', timeout=60)
    rc, out = ev(
        f'simInitEnvWithArgs("{rundir}" "adpll_sch" "{cell}" "schematic" '
        f'"spectre" nil)', timeout=300)
    print(f"[{cell}] simInitEnvWithArgs -> {out.splitlines()[-1][:100] if out else '?'}")

    env_path = Path(rundir) / "si.env"
    if not env_path.exists():
        print(f"[{cell}] no si.env produced")
        return False
    env = env_path.read_text()
    extra = ("\nsimViewList = '(\"spectre cmos_sch schematic veriloga\")\n"
             "simStopList = '(\"spectre\")\nsimNetlistHier = t\n")
    if "simViewList" not in env:
        env_path.write_text(env + extra)
        print(f"[{cell}] si.env patched")

    rc, out = run("si", "-batch", "-cdslib", str(CDSLIB), "-command", "nl",
                  timeout=1200, cwd=rundir)
    print(f"[{cell}] si exit {rc}" + (f" {out[-400:]}" if rc else ""))
    if rc:
        return False

    netlist = Path(rundir) / "netlist"
    if not netlist.exists():
        print(f"[{cell}] no netlist produced")
        return False
    dst = ROOT / "tools" / f"{cell}_sch_netlist.scs"
    dst.write_text(netlist.read_text())
    print(f"[{cell}] exported -> {dst}")

    ref = ROOT / "netlist" / "inc" / CELLS[cell]
    rc, out = run(sys.executable, str(ROOT / "tools" / "compare_block.py"),
                  str(ref), str(dst), cell, timeout=600)
    print(out)
    return rc == 0


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    names = list(CELLS) if which == "all" else [which]
    ok = True
    for n in names:
        ok &= export_cell(n)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
