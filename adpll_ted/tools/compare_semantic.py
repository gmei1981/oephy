#!/usr/bin/env python3
"""Order-sensitive semantic comparison of tb_adpll_top si export vs reference.

The 30/30 set-based compare (compare_tb_top.py) cannot see +/- terminal swaps
(found twice: Esumrst, Esum). This checker maps every instance's nodes to
MASTER TERMINAL NAMES using each deck's own subckt header, then compares
terminal->node dicts. Primitives and VA instances are compared as ordered
node lists (spectre conventions identical on both sides).

Usage:
  python tools/compare_semantic.py [export] [ref_top] [ref_incs...]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_spd_x import parse_netlist  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

EXPORT = ROOT / "tools" / "tb_adpll_top_sch_netlist.scs"
REF_TOP = ROOT / "sim" / "pll_step2_main.scs"
REF_INCS = [ROOT / "netlist" / "inc" / "dtc_10b.scs",
            ROOT / "netlist" / "inc" / "vco_dual_8g.scs",
            ROOT / "netlist" / "inc" / "spd_cmp_gm.scs"]

# model-name equivalence across decks (subckt level)
MODEL_ALIAS = {"vco_x_8g": "vco_x"}


def subckt_headers(text):
    """{name: [pins]} — handles both 'subckt n p1 p2' and 'subckt n (p1 p2)'."""
    out = {}
    text = re.sub(r"\\\s*\n", " ", text)
    for m in re.finditer(r"subckt\s+(\S+)\s*(\([^)]*\)|\S+.*)", text, re.I):
        name = m.group(1)
        rest = m.group(2).strip()
        if rest.startswith("("):
            pins = [p.strip() for p in rest.strip("()").split() if p.strip()]
        else:
            pins = rest.split()
        out[name] = pins
    return out


def load_ref():
    text = REF_TOP.read_text()
    for inc in REF_INCS:
        text += "\n" + inc.read_text()
    headers = subckt_headers(text)
    insts = parse_netlist(REF_TOP.read_text())
    return headers, insts


def load_sch():
    text = EXPORT.read_text()
    headers = subckt_headers(text)
    # tb-level instances come after the last 'ends'; inline the adpll_top body
    tb_part = text.split("ends adpll_top", 1)[1]
    m = re.search(r"subckt\s+adpll_top\s+[^\n]*\n(.*?)ends\s+adpll_top", text, re.S)
    body = m.group(1) if m else ""
    insts = parse_netlist(tb_part + "\n" + body)
    insts.pop("Xpll", None)
    return headers, insts


def semantic(model, nodes, headers):
    """terminal-name -> node dict for subckts; ordered list for primitives/VA."""
    if model in headers:
        pins = headers[model]
        if len(pins) != len(nodes):
            return ("PINCOUNT", f"{model}: {len(pins)} pins vs {len(nodes)} nodes")
        return ("MAP", dict(zip(pins, nodes)))
    return ("ORDER", nodes)


def main():
    ref_headers, ref = load_ref()
    sch_headers, sch = load_sch()

    print(f"ref instances: {len(ref)}, sch instances: {len(sch)}")
    print("only-in-ref:", sorted(set(ref) - set(sch)) or "无")
    print("only-in-sch:", sorted(set(sch) - set(ref)) or "无")

    bad = 0
    print("\nterminal-level comparison:")
    for name in sorted(set(ref) & set(sch)):
        r_model, r_nodes, _ = ref[name]
        s_model, s_nodes, _ = sch[name]
        r_model_a = MODEL_ALIAS.get(r_model, r_model)
        s_model_a = MODEL_ALIAS.get(s_model, s_model)
        if r_model_a != s_model_a:
            print(f"  {name}: MODEL MISMATCH {r_model} vs {s_model}")
            bad += 1
            continue
        r_sem = semantic(r_model_a, r_nodes, ref_headers)
        s_sem = semantic(s_model_a, s_nodes, sch_headers)
        if r_sem[0] != s_sem[0]:
            print(f"  {name}: KIND MISMATCH {r_sem} vs {s_sem}")
            bad += 1
            continue
        if r_sem[0] == "MAP":
            if r_sem[1] != s_sem[1]:
                # per-terminal diff
                for pin in sorted(set(r_sem[1]) | set(s_sem[1])):
                    if r_sem[1].get(pin) != s_sem[1].get(pin):
                        print(f"  {name}.{pin}: ref={r_sem[1].get(pin)} sch={s_sem[1].get(pin)}")
                bad += 1
        else:
            if r_sem[1] != s_sem[1]:
                print(f"  {name}: NODE ORDER {r_sem[1]} vs {s_sem[1]}")
                bad += 1
    print("\nOK: all terminals match" if not bad else f"\n{bad} instance(s) with mismatches")


if __name__ == "__main__":
    main()
