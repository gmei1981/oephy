#!/usr/bin/env python3
"""Build tb_ref3 testbench schematic + adpll_ref3_top symbol.

tb_ref3 = Xpll (adpll_ref3_top) + 8 sources, mirroring the source section of
sim/ref3/v3/main/main.scs:
  Vvdd  vdc    VDD   0.8      Vvbg  vdc   VBG  0.5
  Vvss  vdc    VSS   0        Vvbl  vdc   VBL  0.62
  Vref  vpulse REF   100M 50% Vrstn vpulse RSTN (delay 20n)
  Vv1v  vdc    V1V   1.0      Vrcomp vdc  RCOMP 0
Source negative terminals all gnd! (label method). No pins - tb is top.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IL_DIR = ROOT / "tools" / "sch_build"
LIB = "adpll_sch"
BRIDGE = "ref3sch"
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
]

TOP_SYM_PORTS_L = [
    ("REF", "input"), ("RSTN", "input"), ("RCOMP", "input"),
    ("VDD", "inputOutput"), ("V1V", "inputOutput"), ("VBG", "input"),
    ("VBL", "input"), ("VSS", "inputOutput"),
]
TOP_SYM_PORTS_R = [("OUTP", "output"), ("OUTN", "output")]

SOURCES = [
    # (name, cell, x, y, {term: net}, {params})
    ("Vvdd", "vdc", 20, 6, {"PLUS": "VDD", "MINUS": "gnd!"}, {"vdc": "0.8"}),
    ("Vvss", "vdc", 20, 2, {"PLUS": "VSS", "MINUS": "gnd!"}, {"vdc": "0"}),
    ("Vref", "vpulse", 20, -2, {"PLUS": "REF", "MINUS": "gnd!"},
     {"v1": "0", "v2": "0.8", "per": "10n", "pw": "5n", "tr": "10p", "tf": "10p"}),
    ("Vv1v", "vdc", 20, -6, {"PLUS": "V1V", "MINUS": "gnd!"}, {"vdc": "1.0"}),
    ("Vvbg", "vdc", 28, 6, {"PLUS": "VBG", "MINUS": "gnd!"}, {"vdc": "0.5"}),
    ("Vvbl", "vdc", 28, 2, {"PLUS": "VBL", "MINUS": "gnd!"}, {"vdc": "0.62"}),
    ("Vrstn", "vpulse", 28, -2, {"PLUS": "RSTN", "MINUS": "gnd!"},
     {"v1": "0", "v2": "0.8", "per": "1m", "pw": "1m", "td": "20n",
      "tr": "10p", "tf": "10p"}),
    ("Vrcomp", "vdc", 28, -6, {"PLUS": "RCOMP", "MINUS": "gnd!"}, {"vdc": "0"}),
]


def sym_ports_spec(left, right):
    ports = []
    nl, nr = len(left), len(right)
    for i, (n, d) in enumerate(left):
        y = (nl - 1) * 0.125 + 0.25 - i * 0.25
        ports.append(f'list("{n}" "{d}" -0.5 {y} "centerLeft" -0.35 {y})')
    for i, (n, d) in enumerate(right):
        y = (nr - 1) * 0.125 + 0.25 - i * 0.25
        ports.append(f'list("{n}" "{d}" 0.5 {y} "centerRight" 0.35 {y})')
    return ports


def main():
    IL_DIR.mkdir(exist_ok=True)

    # 1. adpll_ref3_top symbol
    ports = " ".join(" " + p for p in
                     sym_ports_spec(TOP_SYM_PORTS_L, TOP_SYM_PORTS_R))
    nl = max(len(TOP_SYM_PORTS_L), len(TOP_SYM_PORTS_R))
    hh = (nl - 1) * 0.125 + 0.5
    sh = hh + 0.3
    sym_line = (
        f'when(!ref3VaSym("{LIB}" "adpll_ref3_top" list({ports}) '
        f'list(-0.5 {-hh} 0.5 {hh}) list(-0.9 {-sh} 0.9 {sh}) '
        f'list(0 {hh - 0.4375}) list(0 {-(hh - 0.4375)})) '
        f'error("sym adpll_ref3_top failed"))'
    )
    sym_path = IL_DIR / "build_ref3_topsym.il"
    sym_path.write_text(sym_line + "\n")

    # 2. tb_ref3 schematic IL
    H = [h.format(lib=LIB, cell="tb_ref3") for h in HEADER]
    P = [
        'Xpll = dbCreateInstByMasterName(cv "adpll_sch" "adpll_ref3_top" "symbol" "Xpll" 0:0 "R0")',
    ]
    for n, d in TOP_SYM_PORTS_L:
        P.append(f'rsStub(Xpll "{n}" "{n}" -0.35 0)')
    for n, d in TOP_SYM_PORTS_R:
        P.append(f'rsStub(Xpll "{n}" "{n}" 0.35 0)')
    P.append("")
    for name, cell, x, y, terms, params in SOURCES:
        P.append(f'{name} = dbCreateInstByMasterName(cv "analogLib" "{cell}" "symbol" "{name}" {x}:{y} "R0")')
        for k, v in params.items():
            P.append(f'rsProp({name} "{k}" "{v}")')
        for t, net in terms.items():
            dy = "0.35" if t == "PLUS" else "-0.35"
            P.append(f'rsStub({name} "{t}" "{net}" 0 {dy})')
        P.append("")
    P.append('printf("TB_BUILD_DONE instances=%d\\n" length(cv~>instances))')
    tb_path = IL_DIR / "build_ref3_tb.il"
    tb_path.write_text("\n".join(H + P) + "\n")

    def run(*args, timeout=600):
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr)

    def ev(skill, timeout=300):
        return run("vlink", "evalstring", skill, "-i", BRIDGE, "-t", str(timeout))

    # 3. execute
    rc, out = run("vlink", "load", str(VA_IL), "-i", BRIDGE, "-t", "300")
    print(f"[sym] load ref3_va.il -> {out.splitlines()[-1][:60] if out else '?'}")
    rc, out = run("vlink", "load", str(sym_path), "-i", BRIDGE, "-t", "300")
    print(f"[sym] build -> {out[-150:]}")
    rc, out = ev('when(ddGetObj("adpll_sch" "tb_ref3") '
                 'ddDeleteObj(ddGetObj("adpll_sch" "tb_ref3")))', timeout=120)
    rc, out = run("vlink", "load", str(tb_path), "-i", BRIDGE, "-t", "600")
    print(f"[tb] load -> {out[-150:]}")
    rc, out = ev('let((cv) cv = dbOpenCellViewByType("adpll_sch" "tb_ref3" '
                 '"schematic" "schematic" "a") schCheck(cv))', timeout=600)
    print(f"[tb] schCheck -> {out.splitlines()[-1][:150]}")
    rc, out = ev('let((cv) cv = dbOpenCellViewByType("adpll_sch" "tb_ref3" '
                 '"schematic" "schematic" "a") dbSave(cv))', timeout=300)
    rc, out = ev('let((cv) cv = dbOpenCellViewByType("adpll_sch" "tb_ref3" '
                 '"schematic" "schematic" "r") '
                 'list(length(cv~>instances) length(cv~>terminals)))',
                 timeout=300)
    print(f"[tb] verify (expect 9 inst / 0 terms) -> {out.splitlines()[-1][:80]}")


if __name__ == "__main__":
    main()
