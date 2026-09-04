#!/usr/bin/env python3
"""Assemble the golden TB netlist template from the tb_afe_tran si export.

Every transform asserts exactly-once matching (or expected count); the run
scripts bake __PLACEHOLDER__ values per point, same as the legacy template.

Transforms:
  1. drop the 5 VA stub subckt defs (keep their port orders for step 2)
  2. rewrite the 6 VA leaf instance lines: nodes re-ordered from stub-header
     (alphabetical) order to .va module declaration order + params appended
  3. patch analog glue (TL z0/td, Vpi/Vcb/Idr dc, Eaz gain) to placeholders
  4. patch top-level stimulus (Vvdd/Vnvdd/Vvccio tails, R/L values)
  5. prepend lang/models/ahdl includes; append directives verbatim from the
     legacy template (nodeset/ic/simOpts/tran/saveOptions/save)

Run from anywhere (pure text processing):
  python3 scripts/gen_golden_netlist.py
"""
import re
import sys
from pathlib import Path

AFE = Path(__file__).resolve().parents[1]
SRC = AFE / "output" / "n2s_top" / "tb_afe_tran_si.scs"
TPL = AFE / "netlists" / "tb_afe_tran.scs"          # legacy: directives source
OUT = AFE / "output" / "n2s_top" / "golden_tb_template.scs"

VA_MODULES = {  # module -> (instance, params-after-netlist-name)
    "afe_prbs23_gen": ("fbit=16e9",),
    "afe_clk_gen": ("tpclk_ph=17.5p",),
    "afe_pingpong": (),
    "afe_samp": (),
    "afe_ber_chk": (),
}
VA_PARAMS = {
    "G1": "fbit=16e9 seed=3",
    "G2": "fbit=16e9 seed=19",
    "CK": "tpclk_ph=17.5p",
    "PP": "",
    "SMP": "",
    "CHK": "n_shift=__NS__ start_bit=200",
}


def module_ports(name):
    text = (AFE / "va" / f"{name}.va").read_text()
    m = re.search(r"module\s+\w+\s*\(([^)]*)\)", text)
    return [p.strip() for p in m.group(1).replace("\n", " ").split(",")]


def sub1(pattern, repl, text, n=1, what=""):
    new, cnt = re.subn(pattern, repl, text)
    assert cnt == n, f"{what or pattern}: matched {cnt} != {n}"
    return new


def main():
    src = SRC.read_text()
    src = re.sub(r"\\\s*\n\s*", " ", src)  # join continuations for matching
    stub_orders = {}

    # 0. device-emission normalization (golden-truth rewrites):
    #    - MOS (nch_/pch_*_mac): CDF extras (w/multi/nf/sd/sa/sb/ploda/...)
    #      are DC-probe-neutral but NOT t=0+-transient-neutral (measured:
    #      old-flow vdd rings up to 0.968 at the first step, extras-laden
    #      emission dips to 0.72 -> the VA latches a different vhi). Keep
    #      only l/nfin (values from the emission itself).
    #    - cfmom_2t_p80: the CDF param set was only ever DC-probed (caps
    #      are open circuits in DC) -> strip to bare.
    #    (hia18 diode lines keep their emission: IV-proven bit-exact)
    mos = re.findall(r"^(\s*[A-Za-z]\w* \([^)]*\) [np]ch_\w+_mac )"
                     r"l=([\d.]+)n nfin=(\d+) .*$", src, re.M)
    src = re.sub(r"^(\s*[A-Za-z]\w* \([^)]*\) [np]ch_\w+_mac )"
                 r"l=([\d.]+)n nfin=(\d+) .*$",
                 lambda m: f"{m.group(1)}l={float(m.group(2)):g}n "
                           f"nfin={m.group(3)}", src, flags=re.M)
    ncf = len(re.findall(r"cfmom_2t_p80 [^\n]+", src))
    src = re.sub(r"(cfmom_2t_p80) [^\n]+", r"\1", src)
    print(f"[golden] normalized {len(mos)} MOS lines, {ncf} cfmom lines "
          "to bare golden form")

    # 1. drop VA stub subckt defs (with their comment banners), remember
    #    their emitted port order
    for mod in VA_MODULES:
        m = re.search(
            rf"// Library name: [^\n]*\n// Cell name: {mod}\n// View name: "
            rf"[^\n]*\nsubckt {mod} ([^\n]+)\nends {mod}\n"
            rf"// End of subcircuit definition\.\n", src)
        assert m, f"stub def {mod} not found"
        stub_orders[mod] = m.group(1).split()
        src = src.replace(m.group(0), "")

    # 2. rewrite VA leaf instances (nodes -> module decl order + params)
    for inst, mod in (("G1", "afe_prbs23_gen"), ("G2", "afe_prbs23_gen"),
                      ("CK", "afe_clk_gen"), ("PP", "afe_pingpong"),
                      ("SMP", "afe_samp"), ("CHK", "afe_ber_chk")):
        m = re.search(rf"{inst} \(([^)]*)\) {mod}\n", src)
        assert m, f"instance {inst} not found"
        nets = m.group(1).split()
        hdr = stub_orders[mod]
        assert len(nets) == len(hdr), f"{inst}: {nets} vs {hdr}"
        by_port = dict(zip(hdr, nets))
        ordered = [by_port[p] for p in module_ports(mod)]
        params = VA_PARAMS[inst]
        line = f"{inst} ({' '.join(ordered)}) {mod}"
        if params:
            line += f" {params}"
        src = src.replace(m.group(0), line + "\n")

    # 3. glue patches (inside subckt afe_tb_tran)
    src = sub1(r"TL \(ntx vss rx_in vss\) tline z0=50 nl=0\.25\n",
               "TL (ntx vss rx_in vss) tline z0=30 td=9p\n", src, 1, "TL")
    src = sub1(r"Vpi \(pi_in vss\) vsource type=dc\n",
               "Vpi (pi_in 0) vsource dc=__PCV__\n", src, 1, "Vpi")
    for k in range(8):
        src = sub1(rf"Vcb{k} \(codeb{k} vss\) vsource type=dc\n",
                   f"Vcb{k} (codeb{k} 0) vsource dc=__CB{k}__\n",
                   src, 1, f"Vcb{k}")
    for inst, nodes in (("EazA", "a_az_g 0 a_az 0"),
                        ("EazB", "b_az_g 0 b_az 0")):
        src = sub1(rf"{inst} \([^)]*\) vcvs gain=1\.0\n",
                   f"{inst} ({nodes}) vcvs gain=__AZEN__\n", src, 1, inst)
    src = sub1(r"Idr \(vss gp_a\) isource type=dc\n",
               "Idr (0 gp_a) isource dc=__DRIFT__\n", src, 1, "Idr")

    # 4. top-level stimulus (Xpc/cfmom already normalized bare by step 0)
    src = sub1(r"Vvdd \(vddsrc 0\) vsource type=sine\n",
               "Vvdd (vddsrc 0) vsource dc=0.8\n", src, 1, "Vvdd")
    src = sub1(r"Vnvdd \(vddsrc vddpkg\) vsource type=sine\n",
               "Vnvdd (vddsrc vddpkg) vsource type=sine sinedc=0 "
               "ampl=__AMPL__ freq=__FN__\n", src, 1, "Vnvdd")
    src = sub1(r"Vvccio \(vcciosrc 0\) vsource type=sine\n",
               "Vvccio (vcciosrc 0) vsource dc=0.45\n", src, 1, "Vvccio")
    for name in ("Rvdd", "Rvccio", "Rvss"):
        src = sub1(rf"{name} \(([^)]*)\) resistor r=500\.0m\n",
                   rf"{name} (\1) resistor r=__RS__" + "\n", src, 1, name)
    for name in ("Lvdd", "Lvccio", "Lvss"):
        src = sub1(rf"{name} \(([^)]*)\) inductor l=10\.00p\n",
                   rf"{name} (\1) inductor l=__LS__" + "\n", src, 1, name)

    # 5a. header
    header = ["// UCIe-AP RX AFE golden netlist -- generated from the "
              "afe_sch schematics", "// (si export of tb_afe_tran) by "
              "scripts/gen_golden_netlist.py; run scripts bake __X__ values.",
              "simulator lang=spectre", "", "__MODELS__", ""]
    header += [f'ahdl_include "{m}.va"' for m in sorted(VA_MODULES)]
    header += [""]

    # 5b. directives verbatim from the legacy template
    legacy = TPL.read_text()
    idx = legacy.index("nodeset ")
    directives = "\n// ---- directives (verbatim from tb_afe_tran.scs) ----\n" \
                 + legacy[idx:]

    body = "\n".join(line for line in src.splitlines() if line.strip())
    OUT.write_text("\n".join(header) + body + "\n" + directives)
    print(f"[golden] wrote {OUT} "
          f"({len((OUT).read_text().splitlines())} lines)")


if __name__ == "__main__":
    main()
