#!/usr/bin/env python3
"""Build adpll_ref3_top schematic (P3) + symbols for the 3 analog cells (P2b).

Hierarchy mirrors sim/ref3/v3/main/main.scs:
  analog core: Xldo(ldo_05) Xvco(vco_x_c_dac) Xdtc(dtc_10b_ss) Rbuf + 2 inv
  digital VA : Xfsm Xlock Xdsmf Xmmd Xdivn Xtdc Xpfd Xafc Xfll Xlpf
               Xdacab Xdsmd Xdacfb Xcalk Xcald  (ports from va_build/ref3_va.json)
Top pins: REF RSTN RCOMP VDD V1V VBG VBL VSS OUTP OUTN (OUTP/OUTN exposed for
ic= + probing; all other nets internal).

Symbol side rule (both VA symbols and our 3 new ones): non-output pins left
edge (x=-0.5), outputs right edge (x=+0.5); parent stubs go left/right.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IL_DIR = ROOT / "tools" / "sch_build"
LIB = "adpll_sch"
BRIDGE = "ref3sch"
VA_JSON = ROOT / "tools" / "va_build" / "ref3_va.json"
VA_IL = ROOT / "tools" / "va_build" / "ref3_va.il"

HEADER = [
    "cv = dbOpenCellViewByType(\"{lib}\" \"{cell}\" \"schematic\" \"schematic\" \"a\")",
    "",
    "procedure(rsProp(inst prop val)",
    "  if(dbFindProp(inst prop)",
    "    dbReplaceProp(inst prop \"string\" val)",
    "    dbCreateProp(inst prop \"string\" val)))",
    "",
    "procedure(rsTermCtr(inst termName)",
    "  let((term pin fig bb)",
    "    term = car(setof(tt inst~>master~>terminals tt~>name == termName))",
    "    pin = when(term car(term~>pins))",
    "    fig = when(pin car(pin~>figs))",
    "    bb = when(fig fig~>bBox)",
    "    when(bb",
    "      dbTransformPoint(",
    "        list((xCoord(car(bb)) + xCoord(cadr(bb))) / 2.0",
    "             (yCoord(car(bb)) + yCoord(cadr(bb))) / 2.0)",
    "        inst~>transform))))",
    "",
    "procedure(rsStub(inst termName netName dx dy)",
    "  let((ctr end mid)",
    "    ctr = rsTermCtr(inst termName)",
    "    when(ctr",
    "      end = list(xCoord(ctr) + dx yCoord(ctr) + dy)",
    "      mid = list((xCoord(ctr) + xCoord(end)) / 2.0",
    "                 (yCoord(ctr) + yCoord(end)) / 2.0)",
    "      schCreateWire(cv \"route\" \"full\" list(ctr end) 0 0 0 nil nil)",
    "      schCreateWireLabel(cv nil mid netName \"centerCenter\" \"R0\" \"stick\" 0.0625 nil))))",
    "",
    "procedure(rsPinAt(pinName dir x y)",
    "  let((master)",
    "    master = dbOpenCellViewByType(\"basic\"",
    "      cond((dir == \"input\" \"ipin\") (dir == \"output\" \"opin\") (t \"iopin\"))",
    "      \"symbol\")",
    "    schCreatePin(cv master pinName dir nil x:y \"R0\")",
    "    schCreateWire(cv \"route\" \"full\" list(x:y x+0.5:y) 0 0 0 nil nil)",
    "    schCreateWireLabel(cv nil x+0.25:y pinName \"centerCenter\" \"R0\" \"stick\" 0.0625 nil)))",
]

# ------------------------------------------------------------------ symbols --
def sym_ports(left, right):
    """left/right = [(name, dir)] -> ref3VaSym port spec lists."""
    ports = []
    nl, nr = len(left), len(right)
    for i, (n, d) in enumerate(left):
        y = (nl - 1) * 0.125 + 0.25 - i * 0.25
        ports.append(f'list("{n}" "{d}" -0.5 {y} "centerLeft" -0.35 {y})')
    for i, (n, d) in enumerate(right):
        y = (nr - 1) * 0.125 + 0.25 - i * 0.25
        ports.append(f'list("{n}" "{d}" 0.5 {y} "centerRight" 0.35 {y})')
    return ports


def sym_il(cell, left, right):
    nl, nr = max(len(left), 1), max(len(right), 1)
    n = max(nl, nr)
    hh = (n - 1) * 0.125 + 0.5          # body half-height
    sh = hh + 0.3                        # selBox half-height
    ports = " ".join(" " + p for p in sym_ports(left, right))
    return (
        f'when(!ref3VaSym("{LIB}" "{cell}" list({ports}) '
        f'list(-0.5 {-hh} 0.5 {hh}) list(-0.9 {-sh} 0.9 {sh}) '
        f'list(0 {hh - 0.4375}) list(0 {-(hh - 0.4375)})) '
        f'error("sym {cell} failed"))'
    )

ANALOG_SYMS = {
    "ldo_05": (
        [("VDD", "inputOutput"), ("VIN", "inputOutput"), ("VBG", "input"),
         ("VBL", "input"), ("VSS", "inputOutput")],
        [("VOUT", "output")],
    ),
    "vco_x_c_dac": (
        [("VDD", "inputOutput"), ("VDDC", "inputOutput"), ("VSS", "inputOutput"),
         ("VC1", "input"), ("VC2", "input")],
        [("OUTP", "output"), ("OUTN", "output")],
    ),
    "dtc_10b_ss": (
        [("CK_IN", "input"), ("VDD", "inputOutput"), ("VSS", "inputOutput")]
        + [(f"CODE{i}", "input") for i in range(10)],
        [("CK_OUT", "output")],
    ),
}

# analog cell pin lists = subckt header order (for parent node mapping)
ANALOG_PORTS = {
    "ldo_05": ["VDD", "VIN", "VBG", "VBL", "VOUT", "VSS"],
    "vco_x_c_dac": ["VDD", "VDDC", "VSS", "OUTP", "OUTN", "VC1", "VC2"],
    "dtc_10b_ss": ["CK_IN", "CK_OUT", "VDD", "VSS"] + [f"CODE{i}" for i in range(10)],
}
ANALOG_DIRS = {
    "ldo_05": ["inputOutput", "inputOutput", "input", "input", "output", "inputOutput"],
    "vco_x_c_dac": ["inputOutput", "inputOutput", "inputOutput", "output", "output",
                    "input", "input"],
    "dtc_10b_ss": ["input", "output", "inputOutput", "inputOutput"] + ["input"] * 10,
}

# -------------------------------------------------------------------- top ----
# (instName, cell, x, y, {params})  — VA cells from main.scs lines 45-75
TOP_INSTS = [
    ("Xfsm",   "pll_fsm",       60,  20, {"idle_wait": "4"}),
    ("Xlock",  "pll_lockdet",   48,  20, {"lock_thr": "0.02"}),
    ("Xdsmf",  "pll_dsm_fb",    72,  20, {"FCW": "80.0", "dsm_fb_mode": "0"}),
    ("Xmmd",   "pll_mmd_ps",    84,  20, {"ninit": "80"}),
    ("Xdivn",  "pll_divn",      96,  20, {"N": "8"}),
    ("Xtdc",   "pll_tdc_beh",    0,  20, {}),
    ("Xpfd",   "pll_pfd",       12,  20, {}),
    ("Xafc",   "pll_afc6",      24,  20, {"FCW": "80.0", "thr": "7", "D": "16"}),
    ("Xfll",   "pll_fll",       36,  20, {"FCW": "80.0", "thr": "8", "D": "16",
                                          "ftol": "4"}),
    ("Xlpf",   "pll_lpf",        0,  -2, {}),
    ("Xdacab", "pll_dac9b",     12,  -2, {"vmax": "0.5"}),
    ("Xdsmd",  "pll_dsm_dco",   24,  -2, {"dsm_dco_mode": "0"}),
    ("Xdacfb", "pll_dac9b",     36,  -2, {"vmax": "0.5"}),
    ("Xcalk",  "pll_cal_kdtc",  48,  -2, {}),
    ("Xcald",  "pll_cal_dcodcc", 60, -2, {}),
    ("Xdtc",   "dtc_10b_ss",     0, -24, {}),
    ("Xvco",   "vco_x_c_dac",   12, -24, {}),
    ("Xldo",   "ldo_05",        24, -24, {}),
]

# instance node lists from sim/ref3/v3/main/main.scs (module/port order)
def _rng(p, n):
    return [f"{p}{i}" for i in range(n)]

NODES = {
    "Xfsm":   ["REF", "RSTN", "AFCD", "FQLK", "PHLK", "ST0", "ST1", "ST2",
               "ENA", "ENF", "ENP", "FSTATE"],
    "Xlock":  ["REF", "PHE", "PHLK"],
    "Xdsmf":  ["REF", "RCOMP"] + _rng("P", 13) + ["QERR", "SELF"],
    "Xmmd":   ["OUTPB"] + _rng("P", 13) + ["SELF", "CKFB"],
    "Xdivn":  ["OUTPB", "CK16"],
    "Xtdc":   ["CKR", "CKFB"] + _rng("OHA", 16) + _rng("OHB", 16)
              + _rng("CA", 16) + _rng("CB", 16) + _rng("FT", 16) + ["ARB"],
    "Xpfd":   _rng("CA", 16) + _rng("CB", 16) + _rng("FT", 16) + ["ARB"]
              + _rng("OHA", 16) + _rng("OHB", 16) + ["PHE", "TCODE"],
    "Xafc":   ["REF", "CK16", "ENA"] + _rng("PB", 6) + ["AFCD", "CNTOUT"],
    "Xfll":   ["REF", "CK16", "ENF", "FCTRL", "FQLK"],
    "Xlpf":   ["REF", "PHE", "FCTRL", "ENA", "ENF", "ENP", "PHLK"] + _rng("PB", 6)
              + _rng("AB", 9) + _rng("FR", 26),
    "Xdacab": ["VC1"] + _rng("AB", 9),
    "Xdsmd":  ["REF"] + _rng("FR", 26) + _rng("FC", 4),
    "Xdacfb": ["VC2"] + _rng("FC", 4) + ["VSS"] * 5,
    "Xcalk":  ["REF", "PHE", "QERR", "DCOMP", "ENP"] + _rng("DT", 10) + ["KDBG"],
    "Xcald":  ["REF", "PHE", "SELF", "ENP", "DCOMP", "DDBG"],
    "Xdtc":   ["REF", "CKR", "VDD", "VSS"] + _rng("DT", 10),
    "Xvco":   ["VDDC", "VDDC", "VSS", "OUTP", "OUTN", "VC1", "VC2"],
    "Xldo":   ["VDD", "V1V", "VBG", "VBL", "VDDC", "VSS"],
}

# buffers (from main.scs lines 79-84): Rbuf + two inverters
BUFFERS = [
    # (name, lib, cell/model, x, y, nf, terms D G S B or PLUS MINUS, netlist props)
    ("Rbuf", "analogLib", "res", 36, -24, None,
     {"PLUS": "OUTP", "MINUS": "BUFFIN"}, {"r": "1k"}),
    ("Minvb1_n", "tsmcN12", "nch_svt_mac", 48, -26, 4,
     {"D": "NBUF1", "G": "BUFFIN", "S": "VSS", "B": "VSS"}, {}),
    ("Minvb1_p", "tsmcN12", "pch_svt_mac", 48, -22, 4,
     {"D": "NBUF1", "G": "BUFFIN", "S": "VDD", "B": "VDD"}, {}),
    ("Minvb2_n", "tsmcN12", "nch_svt_mac", 60, -26, 4,
     {"D": "OUTPB", "G": "NBUF1", "S": "VSS", "B": "VSS"}, {}),
    ("Minvb2_p", "tsmcN12", "pch_svt_mac", 60, -22, 4,
     {"D": "OUTPB", "G": "NBUF1", "S": "VDD", "B": "VDD"}, {}),
]

TOP_PINS = [
    ("REF", "input"), ("RSTN", "input"), ("RCOMP", "input"),
    ("VDD", "inputOutput"), ("V1V", "inputOutput"), ("VBG", "input"),
    ("VBL", "input"), ("VSS", "inputOutput"),
    ("OUTP", "output"), ("OUTN", "output"),
]


def il_top(va):
    H = [h.format(lib=LIB, cell="adpll_ref3_top") for h in HEADER]
    P = []
    for name, cell, x, y, params in TOP_INSTS:
        ports = (ANALOG_PORTS[cell] if cell in ANALOG_PORTS
                 else [p[0] for p in va[cell]["ports"]])
        dirs = (ANALOG_DIRS[cell] if cell in ANALOG_DIRS
                else [p[1] for p in va[cell]["ports"]])
        nodes = NODES[name]
        assert len(ports) == len(nodes), f"{name}: {len(ports)} ports vs {len(nodes)} nodes"
        P.append(f'{name} = dbCreateInstByMasterName(cv "{LIB}" "{cell}" "symbol" "{name}" {x}:{y} "R0")')
        for k, v in params.items():
            P.append(f'rsProp({name} "{k}" "{v}")')
        for pn, d, net in zip(ports, dirs, nodes):
            dx = "0.35" if d == "output" else "-0.35"
            P.append(f'rsStub({name} "{pn}" "{net}" {dx} 0)')
        P.append("")
    for name, lib, cell, x, y, nf, terms, props in BUFFERS:
        P.append(f'{name} = dbCreateInstByMasterName(cv "{lib}" "{cell}" "symbol" "{name}" {x}:{y} "R0")')
        for k, v in props.items():
            P.append(f'rsProp({name} "{k}" "{v}")')
        if nf:
            P.append(f'rsProp({name} "fingers" "{nf}") rsProp({name} "nf" "{nf}")')
        for t, net in terms.items():
            if t in ("D", "G", "S", "B"):
                dx, dy = {"D": ("0", "0.25" if cell.startswith("nch") else "-0.25"),
                          "S": ("0", "-0.25" if cell.startswith("nch") else "0.25"),
                          "G": ("-0.25", "0"), "B": ("0.25", "0")}[t]
                P.append(f'rsStub({name} "{t}" "{net}" {dx} {dy})')
            else:
                dy = "0.25" if t == "PLUS" else "-0.25"
                P.append(f'rsStub({name} "{t}" "{net}" 0 {dy})')
        P.append("")
    for i, (pn, d) in enumerate(TOP_PINS):
        P.append(f'rsPinAt("{pn}" "{d}" -8.0 {20.0 - 2.0 * i})')
    P.append("")
    P.append('printf("TOP_BUILD_DONE instances=%d\\n" length(cv~>instances))')
    return H + P


# ---------------------------------------------------------------- execute ---
def run(*args, timeout=900):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)


def ev(skill, timeout=300):
    return run("vlink", "evalstring", skill, "-i", BRIDGE, "-t", str(timeout))


def main():
    va = json.loads(VA_JSON.read_text())
    IL_DIR.mkdir(exist_ok=True)

    # 1. symbols for the 3 analog cells (needs ref3_va.il loaded first)
    sym_lines = [sym_il(c, l, r) for c, (l, r) in ANALOG_SYMS.items()]
    sym_il_path = IL_DIR / "build_ref3_syms.il"
    sym_il_path.write_text("\n".join(sym_lines) + "\n")
    print(f"[syms] {sym_il_path}")
    rc, out = run("vlink", "load", str(VA_IL), "-i", BRIDGE, "-t", "300")
    print(f"[syms] load ref3_va.il -> {out.splitlines()[-1][:80] if out else '?'}")
    rc, out = run("vlink", "load", str(sym_il_path), "-i", BRIDGE, "-t", "300")
    print(f"[syms] build -> {out[-300:]}")

    # 2. top schematic
    il = IL_DIR / "build_ref3_top.il"
    il.write_text("\n".join(il_top(va)) + "\n")
    print(f"[top] {il}")
    rc, out = ev('when(ddGetObj("adpll_sch" "adpll_ref3_top") '
                 'ddDeleteObj(ddGetObj("adpll_sch" "adpll_ref3_top")))', timeout=120)
    rc, out = run("vlink", "load", str(il), "-i", BRIDGE, "-t", "900")
    print(f"[top] load -> {out[-300:]}")
    rc, out = ev('let((cv) cv = dbOpenCellViewByType("adpll_sch" "adpll_ref3_top" '
                 '"schematic" "schematic" "a") schCheck(cv))', timeout=600)
    print(f"[top] schCheck -> {out.splitlines()[-1][:200]}")
    rc, out = ev('let((cv) cv = dbOpenCellViewByType("adpll_sch" "adpll_ref3_top" '
                 '"schematic" "schematic" "a") dbSave(cv))', timeout=600)
    rc, out = ev('let((cv) cv = dbOpenCellViewByType("adpll_sch" "adpll_ref3_top" '
                 '"schematic" "schematic" "r") '
                 'list(length(cv~>instances) length(cv~>terminals)))', timeout=300)
    print(f"[top] verify (expect 33 inst / 10 terms) -> {out.splitlines()[-1][:100]}")


if __name__ == "__main__":
    main()
