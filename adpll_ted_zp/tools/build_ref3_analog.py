#!/usr/bin/env python3
"""Build the 3 ref3 transistor-level schematic cells via vlink label-stub method.

Cells (reference netlists in netlist/inc/):
  ldo_05      9 inst, 6 pins  (VDD VIN VBG VBL VOUT VSS)         <- ldo_05.scs
  vco_x_c_dac 22 inst, 7 pins (VDD VDDC VSS OUTP OUTN VC1 VC2)   <- vco_c_dac.scs
  dtc_10b_ss  2053 inst, 14 pins (CK_IN CK_OUT VDD VSS CODE0-9) <- dtc_10b_ss.scs
              (delay line identical to dtc_10b; Xdec = pll_dtc_code)

Method = build_dtc_10b.py label naming: instances + short wire stubs with
net-name labels + pins with stub labels, no drawn routes. Loaded via
`vlink load -i ref3sch`; schCheck + dbSave + readback verify via evalstring.

Usage: python3 tools/build_ref3_analog.py [ldo_05|vco_x_c_dac|dtc_10b_ss|all]
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IL_DIR = ROOT / "tools" / "sch_build"
LIB = "adpll_sch"
BRIDGE = "ref3sch"

# ---------------------------------------------------------------- helpers ---
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

MOS = ("dbCreateInstByMasterName(cv \"{mlib}\" \"{model}\" \"symbol\" \"{name}\" {x}:{y} \"R0\")")


def mos(name, model, x, y, nf, lib="tsmcN12"):
    return [
        f"{name} = " + MOS.format(mlib=lib, model=model, name=name, x=x, y=y),
        f'rsProp({name} "fingers" "{nf}") rsProp({name} "nf" "{nf}")',
    ]


def inst(lib, cell, name, x, y, props):
    lines = [
        f'{name} = dbCreateInstByMasterName(cv "{lib}" "{cell}" "symbol" "{name}" {x}:{y} "R0")'
    ]
    for k, v in props:
        lines.append(f'rsProp({name} "{k}" "{v}")')
    return lines


# ------------------------------------------------------------------ ldo_05 ---
def il_ldo_05():
    H = [h.format(lib=LIB, cell="ldo_05") for h in HEADER]
    P = [
        "; ---- 5T OTA + pass + RC ----",
        *mos("MN1", "nch_ulvt_mac", 6, 8, 4),
        *mos("MN2", "nch_ulvt_mac", 10, 8, 4),
        *mos("MTAIL", "nch_ulvt_mac", 8, 4, 1),
        *mos("MP1", "pch_svt_mac", 6, 13, 2),
        *mos("MP2", "pch_svt_mac", 10, 13, 2),
        *mos("MPASS", "pch_svt_mac", 15, 9, 256),
        *inst("analogLib", "res", "RLPF", 18, 12, [("r", "2k")]),
        *inst("analogLib", "cap", "CLPF", 18, 5, [("c", "2p")]),
        *inst("analogLib", "cap", "COUT", 21, 9, [("c", "20p")]),
        "",
        "rsStub(MN1 \"D\" \"VDN\" 0.25 0) rsStub(MN1 \"G\" \"VOUT\" -0.25 0)",
        "rsStub(MN1 \"S\" \"TAIL\" 0 -0.25) rsStub(MN1 \"B\" \"VSS\" 0.25 0)",
        "rsStub(MN2 \"D\" \"VDP\" 0.25 0) rsStub(MN2 \"G\" \"VBG\" -0.25 0)",
        "rsStub(MN2 \"S\" \"TAIL\" 0 -0.25) rsStub(MN2 \"B\" \"VSS\" 0.25 0)",
        "rsStub(MTAIL \"D\" \"TAIL\" 0 0.25) rsStub(MTAIL \"G\" \"VBL\" -0.25 0)",
        "rsStub(MTAIL \"S\" \"VSS\" 0 -0.25) rsStub(MTAIL \"B\" \"VSS\" 0.25 0)",
        "rsStub(MP1 \"D\" \"VDN\" 0 -0.25) rsStub(MP1 \"G\" \"VDN\" -0.25 0)",
        "rsStub(MP1 \"S\" \"VDD\" 0 0.25) rsStub(MP1 \"B\" \"VDD\" 0.25 0)",
        "rsStub(MP2 \"D\" \"VDP\" 0 -0.25) rsStub(MP2 \"G\" \"VDN\" -0.25 0)",
        "rsStub(MP2 \"S\" \"VDD\" 0 0.25) rsStub(MP2 \"B\" \"VDD\" 0.25 0)",
        "rsStub(MPASS \"D\" \"VOUT\" 0 -0.25) rsStub(MPASS \"G\" \"VGATE\" -0.25 0)",
        "rsStub(MPASS \"S\" \"VIN\" 0 0.25) rsStub(MPASS \"B\" \"VIN\" 0.25 0)",
        "rsStub(RLPF \"PLUS\" \"VDP\" 0 0.25) rsStub(RLPF \"MINUS\" \"VGATE\" 0 -0.25)",
        "rsStub(CLPF \"PLUS\" \"VGATE\" 0 0.25) rsStub(CLPF \"MINUS\" \"VSS\" 0 -0.25)",
        "rsStub(COUT \"PLUS\" \"VOUT\" 0 0.25) rsStub(COUT \"MINUS\" \"VSS\" 0 -0.25)",
        "",
        "; pins in subckt header order: VDD VIN VBG VBL VOUT VSS",
        'rsPinAt("VDD" "inputOutput" 1.0 18.0)',
        'rsPinAt("VIN" "inputOutput" 1.0 16.0)',
        'rsPinAt("VBG" "input" 1.0 14.0)',
        'rsPinAt("VBL" "input" 1.0 12.0)',
        'rsPinAt("VOUT" "output" 1.0 10.0)',
        'rsPinAt("VSS" "inputOutput" 1.0 8.0)',
        "",
        'printf("LDO_BUILD_DONE instances=%d\\n" length(cv~>instances))',
    ]
    return H + P


# ------------------------------------------------------------ vco_x_c_dac ---
def il_vco_x_c_dac():
    H = [h.format(lib=LIB, cell="vco_x_c_dac") for h in HEADER]
    cf_terms = ["OUTP OUTN", "OUTN net01", "OUTN net02", "OUTN net03",
                "OUTN net04", "OUTN net05", "OUTP OUTN", "OUTN net07",
                "OUTN net08", "OUTN net09", "OUTN net10", "OUTN net11"]
    P = ["; ---- cross-coupled pair + tank ----",
         *mos("MN0", "nch_ulvt_mac", 6, 10, 16),
         *mos("MN1", "nch_ulvt_mac", 10, 10, 16),
         *inst("analogLib", "ind", "Ls", 8, 5, [("l", "2n"), ("r", "1")]),
         *inst("analogLib", "ind", "L0", 4, 15, [("l", "1.5n"), ("r", "2")]),
         *inst("analogLib", "ind", "L1", 10, 15, [("l", "1.5n"), ("r", "2")]),
         *inst("analogLib", "cap", "Cbyp", 2, 9, [("c", "10p")]),
         ]
    for i in range(12):
        plus, minus = cf_terms[i].split()
        x = 4 + i * 2.5
        P += inst("tsmcN12", "cfmom_wo_p80", f"CF{i}", x, 2, [("nr", "174")])
        P += [f'rsStub(CF{i} "PLUS" "{plus}" 0 0.25)',
              f'rsStub(CF{i} "MINUS" "{minus}" 0 -0.25)',
              f'rsStub(CF{i} "BULK" "VSS" 0.25 0)']
    P += [
        *inst("tsmcN12", "moscap_rf", "C1p_mv", 19, 14, [("wr", "538n"), ("nfin", "24"), ("lr", "200n")]),
        *inst("tsmcN12", "moscap_rf", "C1n_mv", 23, 14, [("wr", "538n"), ("nfin", "24"), ("lr", "200n")]),
        *inst("tsmcN12", "moscap_rf", "C2p_mv", 19, 11, [("wr", "538n"), ("nfin", "2"), ("lr", "200n")]),
        *inst("tsmcN12", "moscap_rf", "C2n_mv", 23, 11, [("wr", "538n"), ("nfin", "2"), ("lr", "200n")]),
        "",
        "rsStub(MN0 \"D\" \"OUTN\" 0 0.25) rsStub(MN0 \"G\" \"OUTP\" -0.25 0)",
        "rsStub(MN0 \"S\" \"TAIL\" 0 -0.25) rsStub(MN0 \"B\" \"VSS\" 0.25 0)",
        "rsStub(MN1 \"D\" \"OUTP\" 0 0.25) rsStub(MN1 \"G\" \"OUTN\" -0.25 0)",
        "rsStub(MN1 \"S\" \"TAIL\" 0 -0.25) rsStub(MN1 \"B\" \"VSS\" 0.25 0)",
        "rsStub(Ls \"PLUS\" \"TAIL\" 0 0.25) rsStub(Ls \"MINUS\" \"VSS\" 0 -0.25)",
        "rsStub(L0 \"PLUS\" \"VDD\" 0 0.25) rsStub(L0 \"MINUS\" \"OUTP\" 0 -0.25)",
        "rsStub(L1 \"PLUS\" \"VDD\" 0 0.25) rsStub(L1 \"MINUS\" \"OUTN\" 0 -0.25)",
        "rsStub(Cbyp \"PLUS\" \"VDD\" 0 0.25) rsStub(Cbyp \"MINUS\" \"VSS\" 0 -0.25)",
        "",
        "rsStub(C1p_mv \"GATE\" \"OUTP\" -0.25 0) rsStub(C1p_mv \"BULK\" \"VC1\" 0 -0.25)",
        "rsStub(C1p_mv \"GNODE\" \"VC1\" 0.25 0)",
        "rsStub(C1n_mv \"GATE\" \"OUTN\" 0 0.25) rsStub(C1n_mv \"BULK\" \"VC1\" 0 -0.25)",
        "rsStub(C1n_mv \"GNODE\" \"VC1\" 0.25 0)",
        "rsStub(C2p_mv \"GATE\" \"OUTP\" -0.25 0) rsStub(C2p_mv \"BULK\" \"VC2\" 0 -0.25)",
        "rsStub(C2p_mv \"GNODE\" \"VC2\" 0.25 0)",
        "rsStub(C2n_mv \"GATE\" \"OUTN\" 0 0.25) rsStub(C2n_mv \"BULK\" \"VC2\" 0 -0.25)",
        "rsStub(C2n_mv \"GNODE\" \"VC2\" 0.25 0)",
        "",
        "; pins in subckt header order: VDD VDDC VSS OUTP OUTN VC1 VC2",
        "; (VDDC port is vestigial in reference netlist - stays unconnected inside)",
        'rsPinAt("VDD" "inputOutput" 1.0 20.0)',
        'rsPinAt("VDDC" "inputOutput" 1.0 18.0)',
        'rsPinAt("VSS" "inputOutput" 1.0 16.0)',
        'rsPinAt("OUTP" "output" 1.0 14.0)',
        'rsPinAt("OUTN" "output" 1.0 12.0)',
        'rsPinAt("VC1" "input" 1.0 10.0)',
        'rsPinAt("VC2" "input" 1.0 8.0)',
        "",
        'printf("VCO_BUILD_DONE instances=%d\\n" length(cv~>instances))',
    ]
    return H + P


# ------------------------------------------------------------- dtc_10b_ss ---
def il_dtc_10b_ss():
    H = [h.format(lib=LIB, cell="dtc_10b_ss") for h in HEADER]
    P = [
        "; ---- decoder VA inside DTC (10b passthrough) ----",
        "; pll_dtc_code symbol is a ~310-wide horizontal bar (1033 pins, 0.3 pitch);",
        "; keep its pin row clear of the grid top-row D stubs (y ends 26.44)",
        'xdec = dbCreateInstByMasterName(cv "adpll_sch" "pll_dtc_code" "symbol" "Xdec" 4:32 "R0")',
        'rsProp(xdec "vth" "0.5")',
        "",
        "; ---- peripherals (identical to dtc_10b) ----",
        *inst("tsmcN12", "rhim", "R0", 10, 20, [("l", "2.3e-06"), ("w", "2e-06")]),
        *mos("MNI", "nch_svt_mac", 14, 20, 1),
        *mos("MPI", "pch_svt_mac", 16, 20, 1),
        *mos("MRST_D", "nch_svt_mac", 18, 20, 2),
        *mos("MN1", "nch_svt_mac", 22, 20, 8),
        *mos("MP1", "pch_svt_mac", 24, 20, 8),
        "",
        "rsStub(R0 \"PLUS\" \"CK_IN\" -0.25 0)",
        "rsStub(R0 \"MINUS\" \"VDLY\" 0.25 0)",
        "rsStub(MNI \"G\" \"CK_IN\" -0.25 0) rsStub(MNI \"D\" \"CKXB\" 0 0.25)",
        "rsStub(MNI \"S\" \"VSS\" 0 -0.25) rsStub(MNI \"B\" \"VSS\" 0.25 0)",
        "rsStub(MPI \"G\" \"CK_IN\" -0.25 0) rsStub(MPI \"D\" \"CKXB\" 0 -0.25)",
        "rsStub(MPI \"S\" \"VDD\" 0 0.25) rsStub(MPI \"B\" \"VDD\" 0.25 0)",
        "rsStub(MRST_D \"G\" \"CKXB\" -0.25 0) rsStub(MRST_D \"D\" \"VDLY\" 0 0.25)",
        "rsStub(MRST_D \"S\" \"VSS\" 0 -0.25) rsStub(MRST_D \"B\" \"VSS\" 0.25 0)",
        "rsStub(MN1 \"G\" \"VDLY\" -0.25 0) rsStub(MN1 \"D\" \"CK_OUT\" 0 0.25)",
        "rsStub(MN1 \"S\" \"VSS\" 0 -0.25) rsStub(MN1 \"B\" \"VSS\" 0.25 0)",
        "rsStub(MP1 \"G\" \"VDLY\" -0.25 0) rsStub(MP1 \"D\" \"CK_OUT\" 0 -0.25)",
        "rsStub(MP1 \"S\" \"VDD\" 0 0.25) rsStub(MP1 \"B\" \"VDD\" 0.25 0)",
        "",
        "; ---- 33x31 grid: 1023 switch+cap pairs ----",
        "for(row 0 32",
        "  for(col 0 30",
        "    let((i x y uname cname ui ci)",
        "      i = row*31 + col",
        "      x = 150.0 + col*2.5",
        "      y = 26.0 - row*2.0",
        "      uname = sprintf(nil \"U%d\" i)",
        "      cname = sprintf(nil \"C%d\" i)",
        "      ui = dbCreateInstByMasterName(cv \"tsmcN12\" \"nch_svt_mac\" \"symbol\" uname x:y \"R0\")",
        "      rsProp(ui \"fingers\" \"2\") rsProp(ui \"nf\" \"2\")",
        "      ci = dbCreateInstByMasterName(cv \"analogLib\" \"cap\" \"symbol\" cname x+1.2:y \"R0\")",
        "      rsProp(ci \"c\" \"5e-16\")",
        "      rsStub(ui \"G\" sprintf(nil \"c%d\" i) -0.25 0)",
        "      rsStub(ui \"D\" \"VDLY\" 0 0.25)",
        "      rsStub(ui \"S\" sprintf(nil \"UCAP%d\" i) 0 -0.25)",
        "      rsStub(ui \"B\" \"VSS\" 0.25 0)",
        "      rsStub(ci \"PLUS\" sprintf(nil \"UCAP%d\" i) 0 0.25)",
        "      rsStub(ci \"MINUS\" \"VSS\" 0 -0.25))))",
        "",
        "; ---- Xdec pin stubs: code<i> -> CODE<i>, c<i> stays ----",
        "foreach(tname xdec~>master~>terminals~>name",
        "  let((net)",
        "    net = cond(",
        '      (tname == "code0" "CODE0")',
        '      (tname == "code1" "CODE1")',
        '      (tname == "code2" "CODE2")',
        '      (tname == "code3" "CODE3")',
        '      (tname == "code4" "CODE4")',
        '      (tname == "code5" "CODE5")',
        '      (tname == "code6" "CODE6")',
        '      (tname == "code7" "CODE7")',
        '      (tname == "code8" "CODE8")',
        '      (tname == "code9" "CODE9")',
        "      (t tname))",
        "    rsStub(xdec tname net 0 0.3)))",
        "",
        "; ---- 14 pins in subckt header order ----",
        'rsPinAt("CK_IN" "input" 1.0 18.0)',
        'rsPinAt("CK_OUT" "output" 1.0 16.0)',
        'rsPinAt("VDD" "inputOutput" 1.0 14.0)',
        'rsPinAt("VSS" "inputOutput" 1.0 12.0)',
        'rsPinAt("CODE0" "input" 1.0 10.0)',
        'rsPinAt("CODE1" "input" 1.0 8.0)',
        'rsPinAt("CODE2" "input" 1.0 6.0)',
        'rsPinAt("CODE3" "input" 1.0 4.0)',
        'rsPinAt("CODE4" "input" 1.0 2.0)',
        'rsPinAt("CODE5" "input" 1.0 0.0)',
        'rsPinAt("CODE6" "input" 1.0 -2.0)',
        'rsPinAt("CODE7" "input" 1.0 -4.0)',
        'rsPinAt("CODE8" "input" 1.0 -6.0)',
        'rsPinAt("CODE9" "input" 1.0 -8.0)',
        "",
        'printf("DTCSS_BUILD_DONE instances=%d\\n" length(cv~>instances))',
    ]
    return H + P


# ---------------------------------------------------------------- execute ---
def run(*args, timeout=900):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr).strip()
    return r.returncode, out


def ev(skill, timeout=300):
    return run("vlink", "evalstring", skill, "-i", BRIDGE, "-t", str(timeout))


def build_cell(cell, il_lines, expect_inst, timeout=900):
    IL_DIR.mkdir(exist_ok=True)
    il = IL_DIR / f"build_{cell}.il"
    il.write_text("\n".join(il_lines) + "\n")
    print(f"[{cell}] il written: {il}")

    rc, out = ev("1+1", timeout=15)
    print(f"[{cell}] probe -> {out[:80]}")
    if "2" not in out:
        print(f"[{cell}] channel dead")
        return False

    rc, out = ev(
        f'when(ddGetObj("{LIB}" "{cell}") '
        f'ddDeleteObj(ddGetObj("{LIB}" "{cell}")))', timeout=120)
    print(f"[{cell}] delete-old -> {out[:80]}")

    rc, out = run("vlink", "load", str(il), "-i", BRIDGE, "-t", str(timeout))
    print(f"[{cell}] load -> {out[:200]}")

    rc, out = ev(
        f'let((cv) cv = dbOpenCellViewByType("{LIB}" "{cell}" '
        f'"schematic" "schematic" "a") schCheck(cv))', timeout=600)
    print(f"[{cell}] schCheck -> {out[:200]}")

    rc, out = ev(
        f'let((cv) cv = dbOpenCellViewByType("{LIB}" "{cell}" '
        f'"schematic" "schematic" "a") dbSave(cv))', timeout=600)
    print(f"[{cell}] dbSave -> {out[:80]}")

    rc, out = ev(
        f'let((cv) cv = dbOpenCellViewByType("{LIB}" "{cell}" '
        f'"schematic" "schematic" "r") '
        f'list(length(cv~>instances) length(cv~>terminals)))', timeout=300)
    ok = f"{expect_inst}" in out
    print(f"[{cell}] verify inst/term -> {out[:120]} expect {expect_inst} -> {'OK' if ok else 'MISMATCH'}")
    return ok


CELLS = {
    # expected instance count includes pins (ipin/opin are instances too)
    "ldo_05": (il_ldo_05, 15),
    "vco_x_c_dac": (il_vco_x_c_dac, 29),
    "dtc_10b_ss": (il_dtc_10b_ss, 2067),
}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    names = list(CELLS) if which == "all" else [which]
    ok_all = True
    for n in names:
        fn, expect = CELLS[n]
        ok_all &= build_cell(n, fn(), expect,
                             timeout=1800 if n == "dtc_10b_ss" else 900)
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
