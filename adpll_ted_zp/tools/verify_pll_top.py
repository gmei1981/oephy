#!/usr/bin/env python3
"""Verify pll_top_8g schematic topology vs the reference mapping.

Expected structure derived from sim/pll_step2_main.scs (gen_top.py step2,
plan A': Xdec inside dtc_10b). Checks instance set, terminal->net map per
instance, pin directions, VA params, schCheck.
"""
import json
import sys

from virtuoso_bridge import VirtuosoClient

# inst -> {terminal: net}  (terminal names = symbol pin names)
EXPECTED = {
    "Xvco":  {"VDD": "VDD", "VSS": "VSS", "VCTRL": "VCTRL", "OUTP": "OUTP",
              "OUTN": "OUTN", "EN2": "EN2"},
    "Xdtc":  {"CK_IN": "CK2X", "CK_OUT": "CKDTCD", "VDD": "VDD", "VSS": "VSS",
              "CKFB": "CKFB", "KDTC": "KDTC", "EPSC": "EPSC", "SEL": "SEL",
              "ALT": "ALT", "VDCC": "VDCC", "RDCC": "RDCC"},
    "Xspd":  {"VBIAS": "VBSPD", "CK_RST": "CKRST", "CK_SMP": "CKFB",
              "VHOLD": "VHOLD", "VRAMP": "VRAMP", "VDD": "VDD", "VSS": "VSS"},
    "Xcmp":  {"VINP": "VHOLD", "VINN": "VREF", "VBIAS": "VBCMP", "EOUT": "EBIT",
              "VDD": "VDD", "VSS": "VSS"},
    "Xgm":   {"VINP": "VHOLD", "VINN": "VREF", "VBIAS": "VBGM", "IOUT": "VI",
              "VDD": "VDD", "VSS": "VSS"},
    "Xmmd":  {"vco_in": "MMDIN", "ckfb": "CKFB", "sel": "SEL", "alt": "ALT",
              "epsc": "EPSC", "err_out": "EBIT"},
    "Xclkl": {"ckfb": "CKFB", "clk_lms": "CLKLMS"},
    "Xlms":  {"ckfb": "CLKLMS", "ebit": "EBIT", "sel": "SEL", "alt": "ALT",
              "epsc": "EPSC", "kdtc": "KDTC", "vdcc": "VDCC", "rdcc": "RDCC",
              "vref": "VREF"},
    "Edbl":    {"NC+": "REF", "NC-": "gnd!", "PLUS": "CK2X", "MINUS": "gnd!"},
    "Einv":    {"NC+": "CKDTCD", "NC-": "gnd!", "PLUS": "CKRSTI", "MINUS": "gnd!"},
    "Esumrst": {"NC+": "CKRSTI", "NC-": "VDC08", "PLUS": "CKRST", "MINUS": "gnd!"},
    "Ep":      {"NC+": "VHF", "NC-": "gnd!", "PLUS": "VN1", "MINUS": "gnd!"},
    "Esum":    {"NC+": "VN1", "NC-": "VI", "PLUS": "VCTRL", "MINUS": "gnd!"},
    "Rbuf":  {"PLUS": "OUTP", "MINUS": "BUFFIN"},
    "Rf":    {"PLUS": "VHOLD", "MINUS": "VHF"},
    "Xci":   {"PLUS": "VI", "MINUS": "gnd!"},
    "Cf":    {"PLUS": "VHF", "MINUS": "gnd!"},
    "Minvbuf_n":  {"D": "NBUF1", "G": "BUFFIN", "S": "VSS", "B": "VSS"},
    "Minvbuf_p":  {"D": "NBUF1", "G": "BUFFIN", "S": "VDD", "B": "VDD"},
    "Minvbuf2_n": {"D": "MMDIN", "G": "NBUF1", "S": "VSS", "B": "VSS"},
    "Minvbuf2_p": {"D": "MMDIN", "G": "NBUF1", "S": "VDD", "B": "VDD"},
}

PINS = {
    "REF": "input", "VDD": "inputOutput", "VSS": "inputOutput",
    "VBSPD": "input", "VBCMP": "input", "VBGM": "input", "EN2": "input",
    "VDC08": "input", "VI": "inputOutput", "OUTP": "output", "OUTN": "output",
}

VA_PARAMS = {
    "Xmmd": {"Nint2": "80.0", "frac2": "0.0", "vth": "0.7"},
    "Xlms": {"mu_k": "0.0", "mu_v": "0.0", "mu_r": "1e-13", "mu_off": "4.2e-13",
             "K0": "1.0", "vdcc0": "12e-12", "rdcc0": "-12e-12",
             "ohat0": "32e-12", "offset_s": "32e-12", "vref0": "0.15",
             "fref": "1.000000e+08", "m_slope": "1e9", "mode": "1",
             "tscale": "1e-6", "seed": "121"},
}


def gnd(net):
    return net in ("gnd!", "0")


def main():
    client = VirtuosoClient(host="127.0.0.1", port=65418)
    data = client.schematic.read("adpll_sch", "pll_top_8g", include_positions=False)
    insts = {i["name"]: i for i in data.get("instances", [])}
    pins = data.get("pins", {})

    nbad = 0

    # 1. instance set
    missing = set(EXPECTED) - set(insts)
    extra = set(insts) - set(EXPECTED)
    print(f"instances: {len(insts)} (expect {len(EXPECTED)})")
    if missing:
        print("  MISSING:", sorted(missing)); nbad += 1
    if extra:
        print("  EXTRA:", sorted(extra)); nbad += 1

    # 2. terminal -> net per instance
    for name, want in EXPECTED.items():
        if name not in insts:
            continue
        got = {k: v for k, v in insts[name].get("terms", {}).items()}
        problems = []
        for term, net in want.items():
            g = got.get(term)
            ok = False
            if g is not None:
                if gnd(net) and gnd(g):
                    ok = True
                elif g == net:
                    ok = True
            if not ok:
                problems.append(f"{term}->{net} (got {g!r})")
        for term, g in got.items():
            if term not in want and g not in (None, ""):
                problems.append(f"unexpected term {term}->{g!r}")
        if problems:
            nbad += 1
            print(f"  [{name}]")
            for p in problems:
                print(f"      DIFF {p}")
        else:
            print(f"  [{name}] OK")

    # 3. pins
    print(f"\npins: {len(pins)} (expect {len(PINS)})")
    for pname, direction in PINS.items():
        p = pins.get(pname)
        if p is None:
            print(f"  MISSING pin {pname}"); nbad += 1
        elif p.get("direction") != direction:
            print(f"  DIFF pin {pname} dir {p.get('direction')!r} (expect {direction})")
            nbad += 1
        else:
            print(f"  [{pname}] {direction} OK")
    for pname in pins:
        if pname not in PINS:
            print(f"  EXTRA pin {pname}"); nbad += 1

    # 4. VA params
    print()
    for name, want in VA_PARAMS.items():
        if name not in insts:
            continue
        got = {k: str(v) for k, v in insts[name].get("params", {}).items()}
        problems = [f"{k}: {got.get(k)!r} != {v!r}" for k, v in want.items()
                    if got.get(k) != v]
        if problems:
            nbad += 1
            print(f"  [{name}] param DIFF: " + "; ".join(problems))
        else:
            print(f"  [{name}] params OK ({len(want)})")

    # 5. schCheck
    r = client.execute_skill(
        'let((cv) cv = dbOpenCellViewByType("adpll_sch" "pll_top_8g" '
        '"schematic" "schematic" "a") schCheck(cv))', timeout=120)
    print("\nschCheck ->", r.status, r.output)

    print("\nRESULT:", "ALL OK" if nbad == 0 else f"{nbad} problem area(s)")
    return 0 if nbad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
