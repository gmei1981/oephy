#!/usr/bin/env python3
"""Generic block comparison: schematic-exported si netlist vs reference subckt.

Usage:
  python3 tools/compare_block.py <ref_scs> <gen_scs> <subckt_name>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_spd_x import parse_netlist  # noqa: E402


def main():
    ref_path, gen_path, subckt = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    ref = parse_netlist(ref_path.read_text())
    gen = parse_netlist(gen_path.read_text())

    # limit to the subckt body: parse_netlist already extracts the subckt if
    # named 'spd_x'; generalize by comparing whole-file sets (si output has
    # only the body of one cell; reference may hold several subckts).
    # Extract target subckt from reference if present:
    import re
    m = re.search(
        rf"subckt\s+{subckt}\s*\(([^)]*)\)(.*?)ends\s+{subckt}", ref_path.read_text(),
        re.S | re.I,
    )
    if m:
        ref = parse_netlist(m.group(0))

    ref_names, gen_names = set(ref), set(gen)
    print(f"=== {subckt} 器件清单 ===")
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
        for k in sorted(set(r_params) | set(g_params)):
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
