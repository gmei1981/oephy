#!/usr/bin/env python3
"""Verify VA symbol cellviews: terminals order + direction vs .va module decls.

Reads adpll_sch/{pll_mmd_edge,pll_clk_lms,pll_lms,pll_dtc_decoder_10b} symbol
views from the local Virtuoso bridge, parses the .va module declarations, and
compares pin-by-pin (order matters — wrong order silently misconnects nets).
"""
import re
import sys
from pathlib import Path

from virtuoso_bridge import VirtuosoClient

ROOT = Path(__file__).resolve().parent.parent
VA_DIR = ROOT / "netlist" / "va"

# cell -> (va file, module name in file)
MODULES = {
    "pll_mmd_edge": ("pll_mmd_edge.va", "pll_mmd_edge"),
    "pll_clk_lms": ("pll_hybrid_aux.va", "pll_clk_lms"),
    "pll_lms": ("pll_lms.va", "pll_lms"),
    "pll_dtc_decoder_10b": ("pll_dtc_decoder_10b.va", "pll_dtc_decoder_10b"),
}

DIR_MAP = {"inout": "inputOutput", "output": "output", "input": "input"}


def parse_va(fname, modname):
    """Return (ordered ports, port->declared direction) or (None, errmsg)."""
    text = (VA_DIR / fname).read_text()
    # strip // and /* */ comments (they may contain parens/quotes)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//.*", " ", text)
    m = re.search(r"module\s+%s\s*\((.*?)\)\s*;" % re.escape(modname), text, re.S)
    if not m:
        return None, f"module {modname} not found in {fname}"
    ports = [p.strip() for p in m.group(1).split(",") if p.strip()]
    body = text[m.end(): text.find("endmodule", m.end())]
    direction = {}
    for kind in ("inout", "output", "input"):
        for mm in re.finditer(r"\b%s\s+([^;]+);" % kind, body):
            for p in mm.group(1).split(","):
                p = p.strip()
                if p:
                    direction[p] = kind
    return ports, direction


def read_symbol_terminals(client, cell):
    """Return [(name, direction), ...] in terminal order, or (None, errmsg)."""
    open_expr = (f'dbOpenCellViewByType("adpll_sch" "{cell}" '
                 f'"symbol" "schematicSymbol" "r")')
    cv = client.execute_skill(open_expr)
    if not cv.output or cv.output.strip() in ("", "nil"):
        return None, f"symbol view missing or unreadable (output={cv.output!r})"
    r = client.execute_skill(
        'mapcar(lambda((tm) list(tm~>name tm~>direction)) '
        f'{open_expr}~>terminals)'
    )
    out = r.output or ""
    items = re.findall(r'\("([^"]+)"\s+"([^"]+)"\)', out)
    if not items:
        return None, f"could not parse terminals output: {out[:200]}"
    return items, None


def main():
    client = VirtuosoClient(host="127.0.0.1", port=65418)
    ok_all = True
    for cell, (fname, modname) in MODULES.items():
        print(f"\n{'='*20} {cell} {'='*20}")
        res = parse_va(fname, modname)
        if res[0] is None:
            print(f"  VA parse FAIL: {res[1]}")
            ok_all = False
            continue
        va_ports, vdir_map = res
        sym_terms, err2 = read_symbol_terminals(client, cell)
        if err2:
            print(f"  symbol read FAIL: {err2}")
            ok_all = False
            continue
        sym_ports = [t[0] for t in sym_terms]
        print(f"  VA  {len(va_ports):4d} ports")
        print(f"  SYM {len(sym_ports):4d} ports")
        n = min(len(va_ports), len(sym_ports))
        nbad = 0
        for i in range(max(len(va_ports), len(sym_ports))):
            if i >= len(va_ports) or i >= len(sym_ports):
                print(f"  MISMATCH #{i}: length differs "
                      f"(VA={len(va_ports)} SYM={len(sym_ports)})")
                nbad += 1
                continue
            v, s = va_ports[i], sym_ports[i]
            if v != s:
                print(f"  MISMATCH #{i}: VA={v} vs SYM={s}")
                nbad += 1
                continue
            vdir = vdir_map.get(v, "input")
            sdir = sym_terms[i][1]
            expect = DIR_MAP[vdir]
            if sdir != expect:
                print(f"  DIR MISMATCH #{i} {v}: VA={vdir} SYM={sdir} "
                      f"(expect {expect})")
                nbad += 1
        if nbad == 0:
            print(f"  OK — {n} pins, order + direction all match")
        else:
            ok_all = False
    print("\nRESULT:", "ALL PASS" if ok_all else "FAILURES FOUND")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
