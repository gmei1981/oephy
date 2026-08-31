#!/usr/bin/env python3
"""Compare generated spd_x netlist (from hand-drawn schematic) vs reference.

Reference: netlist/inc/spd_cmp_gm.scs (subckt spd_x)
Generated: tools/spd_x_sch_netlist.scs (si -command nl output)

Normalizations:
- multi-line '\\' continuations joined
- subckt/ends wrapper and comments stripped from reference
- values canonicalized: SI suffixes (n/u/m/M/k) -> float, '(1)' -> '1',
  '16.0n' == '16n', strip quotes/whitespace
- instance order ignored (compared as dict keyed by instance name)
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "netlist" / "inc" / "spd_cmp_gm.scs"
GEN = ROOT / "tools" / "spd_x_sch_netlist.scs"

SI = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6, "G": 1e9}
NUM_RE = re.compile(r"^([+-]?[0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)([fpnumkMG])?$")


def canon_val(v: str) -> str:
    v = v.strip().strip('"').strip("'")
    if v.startswith("(") and v.endswith(")"):
        v = v[1:-1].strip()
    m = NUM_RE.match(v)
    if m:
        num = float(m.group(1))
        if m.group(2):
            num *= SI[m.group(2)]
        return f"{num:.9g}"
    return v


def canon_param(p: str):
    if "=" in p:
        k, v = p.split("=", 1)
        return k.strip(), canon_val(v)
    return p.strip(), ""


def parse_netlist(text: str) -> dict:
    """Return {inst_name: (model, [nodes], {param: canon_value})}."""
    # join continuations, drop comments
    lines = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith(("//", "*", "!")):
            continue
        lines.append(ln)
    text = "\n".join(lines)
    text = re.sub(r"\\\s*\n", " ", text)

    # strip subckt wrapper / ends
    m = re.search(r"subckt\s+spd_x\s*\(([^)]*)\)(.*?)ends\s+spd_x", text, re.S | re.I)
    body = m.group(2) if m else text

    out = {}
    stmt_re = re.compile(r"^(\S+)\s+\((.*?)\)\s+(\S+)\s*(.*)$")
    for stmt in body.split("\n"):
        stmt = stmt.strip()
        if not stmt:
            continue
        m = stmt_re.match(stmt)
        if not m:
            continue
        name, nodes_s, model, rest = m.groups()
        nodes = [n.strip() for n in nodes_s.split() if n.strip()]
        params = dict(canon_param(p) for p in rest.split() if "=" in p)
        out[name] = (model, nodes, params)
    return out


def main():
    ref = parse_netlist(REF.read_text())
    gen = parse_netlist(GEN.read_text())

    print("=== 器件清单 ===")
    ref_names, gen_names = set(ref), set(gen)
    print(f"reference: {sorted(ref_names)}")
    print(f"schematic: {sorted(gen_names)}")
    print(f"only-in-ref : {sorted(ref_names - gen_names) or '无'}")
    print(f"only-in-sch : {sorted(gen_names - ref_names) or '无'}")

    print("\n=== 连接 + 参数逐项比对 ===")
    all_ok = True
    for name in sorted(ref_names & gen_names):
        r_model, r_nodes, r_params = ref[name]
        g_model, g_nodes, g_params = gen[name]
        problems = []
        if r_model != g_model:
            problems.append(f"model: {r_model} != {g_model}")
        if r_nodes != g_nodes:
            problems.append(f"nodes: {r_nodes} != {g_nodes}")
        pkeys = set(r_params) | set(g_params)
        for k in sorted(pkeys):
            rv, gv = r_params.get(k), g_params.get(k)
            if rv != gv:
                problems.append(f"param {k}: {rv!r} != {gv!r}")
        status = "OK " if not problems else "DIFF"
        if problems:
            all_ok = False
        print(f"  [{status}] {name} ({r_model})")
        for p in problems:
            print(f"          - {p}")

    print("\n=== 结论 ===")
    print("全部一致 ✓" if all_ok else "存在差异，见上 ✗")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
