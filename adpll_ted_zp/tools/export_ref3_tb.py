#!/usr/bin/env python3
"""si export tb_ref3 + compose tbsmoke netlist (sim/ref3/v3/tbsmoke/).

Composition = exported hierarchical netlist + PDK include + 15 VA
ahdl_include lines + tran (300n, same options as reference smoke) +
hierarchical save (Xpll.* for internals, flat for tb-level REF/OUTP/OUTN).
Run spectre locally, then compare vs sim/ref3/v3/smoke reference run.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CDSLIB = ROOT / "virtuoso_ws" / "cds.lib"
BRIDGE = "ref3sch"
RUN = "/tmp/si_tb_ref3"
SMOKE = ROOT / "sim" / "ref3" / "v3" / "smoke"
TBSMOKE = ROOT / "sim" / "ref3" / "v3" / "tbsmoke"

PDK = "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs"
VA_FILES = ["constants.vams", "disciplines.vams", "pll_dsm_fb.va",
            "pll_mmd_ps.va", "pll_divn.va", "pll_tdc_beh.va", "pll_pfd.va",
            "pll_fll.va", "pll_afc6.va", "pll_fsm.va", "pll_lockdet.va",
            "pll_lpf.va", "pll_dsm_dco.va", "pll_cal_kdtc.va",
            "pll_cal_dcodcc.va", "pll_dac9b.va", "pll_dtc_code.va"]

# reference smoke saved: REF CKR CKFB CK16 CNTOUT PHE QERR SELF VC1 VC2 VDDC
#                       FSTATE FCTRL FQLK PHLK AFCD ENA ENF ENP OUTPB AB8 AB7 AB6 KDBG
TB_LEVEL = ["REF", "OUTP", "OUTN"]
XPLL = ["CKR", "CKFB", "CK16", "CNTOUT", "PHE", "QERR", "SELF", "VC1", "VC2",
        "VDDC", "FSTATE", "FCTRL", "FQLK", "PHLK", "AFCD", "ENA", "ENF",
        "ENP", "OUTPB", "AB8", "AB7", "AB6", "KDBG"]


def run(*args, timeout=900, cwd=None):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                       cwd=cwd)
    return r.returncode, (r.stdout + r.stderr)


def ev(skill, timeout=300):
    return run("vlink", "evalstring", skill, "-i", BRIDGE, "-t", str(timeout))


def main():
    # 1. si export tb_ref3
    ev(f'sh("rm -rf {RUN}")')
    rc, out = ev(f'simInitEnvWithArgs("{RUN}" "adpll_sch" "tb_ref3" '
                 f'"schematic" "spectre" nil)', timeout=300)
    env_path = Path(RUN) / "si.env"
    if not env_path.exists():
        print("no si.env:", out[-200:])
        sys.exit(1)
    env = env_path.read_text()
    if "simViewList" not in env:
        env_path.write_text(env + "\nsimViewList = '(\"spectre cmos_sch "
                             "schematic veriloga\")\nsimStopList = "
                             "'(\"spectre\")\nsimNetlistHier = t\n")
    rc, out = run("si", "-batch", "-cdslib", str(CDSLIB), "-command", "nl",
                  timeout=1200, cwd=RUN)
    if rc:
        print("si failed:", out[-500:])
        sys.exit(1)
    netlist = (Path(RUN) / "netlist").read_text()
    dst = ROOT / "tools" / "tb_ref3_sch_netlist.scs"
    dst.write_text(netlist)
    print(f"exported -> {dst}")

    # sanity: top-level Xpll + 8 sources present
    for tok in ["Xpll", "Vvdd", "Vref", "Vrstn", "Vrcomp"]:
        if not re.search(rf"^{tok} ", netlist, re.M):
            print(f"MISSING top instance {tok}")
            sys.exit(1)
    print("top instances present: Xpll + 8 sources")

    # 2. compose run dir
    if TBSMOKE.exists():
        shutil.rmtree(TBSMOKE)
    TBSMOKE.mkdir(parents=True)
    for f in VA_FILES:
        shutil.copy2(SMOKE / f, TBSMOKE / f)

    header = ["simulator lang=spectre", f'include "{PDK}" section=top_tt'] + \
             [f'ahdl_include "{f}"' for f in VA_FILES]
    save = " ".join(TB_LEVEL + [f"Xpll.{s}" for s in XPLL])
    tail = [
        'plltran tran stop=300n maxstep=2p errpreset=liberal '
        'method=gear2only skipdc=yes strobeperiod=50p '
        'ic="OUTP=0.45" ic="OUTN=0.0"',
        f"save {save}",
        "saveOptions options save=selected",
    ]
    scs = TBSMOKE / "tbsmoke.scs"
    scs.write_text("\n".join(header) + "\n\n" + netlist + "\n" +
                   "\n".join(tail) + "\n")
    print(f"composed -> {scs}")
    print("run: cd sim/ref3/v3/tbsmoke && spectre -64 tbsmoke.scs "
          "-raw tbsmoke.raw +log tbsmoke.log -format psfbin +mt=8")


if __name__ == "__main__":
    main()
