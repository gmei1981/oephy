#!/usr/bin/env python3
"""Compare tb_adpll_top si export vs sim/pll_step2_main.scs (flat reference).

Normalizations:
- export is hierarchical (Xpll + subckt adpll_top): inline the adpll_top
  subckt body into the tb instance set, drop Xpll itself
- instance pin ORDER ignored (both sides internally consistent; compare
  sorted node lists)
- values canonicalized case-insensitively (r=1K == r=1k)
- benign extras dropped: type/edgetype on sources, delay=0 (ref),
  seed on Xmmd / vth on Xclkl/Xlms (VA defaults emitted by si)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_spd_x import parse_netlist, canon_val  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "sim" / "pll_step2_main.scs"
GEN = ROOT / "tools" / "tb_adpll_top_sch_netlist.scs"

DROP_PARAMS = {
    "Vvdd": {"type"}, "Vvss": {"type"}, "Vbspd": {"type"}, "Vbcmp": {"type"},
    "Vbgm": {"type"}, "Venv2": {"type"}, "Vrstofs": {"type"},
    "Vref": {"type"}, "Iinj": {"type", "edgetype"},
    "Xmmd": {"seed"}, "Xclkl": {"vth"}, "Xlms": {"vth"},
}
DROP_REF_PARAMS = {"Iinj": {"delay"}, "Xlms": {"seed"}}
INSTANCE_ORDER = {}  # nodes compared as sorted sets


def canon(v):
    """case-insensitive canonicalization (1K == 1k == 1000)."""
    return canon_val(v.lower() if isinstance(v, str) else v)


def subckt_body(text, name):
    # si style: "subckt name p1 p2 ..." (no parens around port list)
    m = re.search(rf"subckt\s+{name}\s+[^\n]*\n(.*?)ends\s+{name}", text, re.S)
    return m.group(1) if m else ""


def main():
    ref = parse_netlist(REF.read_text())
    gen_full = GEN.read_text()

    # export: tb-level instances come AFTER all subckts; inline the
    # adpll_top subckt body (its instances share the tb instance set)
    tb_part = gen_full.split("ends adpll_top", 1)[1]
    body = subckt_body(gen_full, "adpll_top")
    gen = parse_netlist(tb_part + "\n" + body)
    gen.pop("Xpll", None)  # hierarchy boundary instance, not in flat reference

    # normalize params: type/edgetype dropped from BOTH sides (si emits them
    # on sources where the reference omits them); delay=0 dropped ref-side
    for name, drop in DROP_PARAMS.items():
        for d in (ref, gen):
            if name in d:
                for k in drop:
                    d[name][2].pop(k, None)
    for name, drop in DROP_REF_PARAMS.items():
        if name in ref:
            for k in drop:
                ref[name][2].pop(k, None)
    # canonicalize both sides
    for d in (ref, gen):
        for name in d:
            model, nodes, params = d[name]
            d[name] = (model, sorted(nodes),
                       {k: canon(v) for k, v in params.items()})

    ref_names, gen_names = set(ref), set(gen)
    print(f"reference: {len(ref)} instances, export: {len(gen)}")
    print("only-in-ref:", sorted(ref_names - gen_names) or "无")
    print("only-in-sch:", sorted(gen_names - ref_names) or "无")

    all_ok = True
    print("\n逐项比对:")
    for name in sorted(ref_names & gen_names):
        r_model, r_nodes, r_params = ref[name]
        g_model, g_nodes, g_params = gen[name]
        probs = []
        if r_model != g_model:
            probs.append(f"model: {r_model} != {g_model}")
        if r_nodes != g_nodes:
            probs.append(f"nodes: {r_nodes} != {g_nodes}")
        for k in sorted(set(r_params) | set(g_params)):
            if r_params.get(k) != g_params.get(k):
                probs.append(f"param {k}: {r_params.get(k)!r} != {g_params.get(k)!r}")
        if probs:
            all_ok = False
            print(f"  [DIFF] {name} ({r_model})")
            for p in probs:
                print(f"         - {p}")
        else:
            print(f"  [OK] {name} ({r_model})")

    print("\n结论:", "全部一致 ✓" if all_ok else "存在差异 ✗")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
