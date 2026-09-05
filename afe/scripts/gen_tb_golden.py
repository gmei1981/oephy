#!/usr/bin/env python3
"""Assemble golden TB netlist templates from the 5 TB si exports + verify
equivalence against the legacy netlists/*.scs templates.

Same contract as gen_golden_netlist.py: the schematic carries structure;
stimulus values and analysis directives are patched/appended here so run
scripts can bake __X__ placeholders exactly as before.

Per TB:
  0. join continuations; normalize MOS lines to bare l/nfin and cfmom to
     bare (CDF extras are t=0+-non-neutral / DC-neutral-only, measured
     2026-09-04); rhim emission kept (multi=(1) IV-proven neutral)
  1. patch top-level source skeletons (vsource/isource type=sine) to the
     legacy stimulus lines (values or placeholders)
  2. prepend header (lang + model includes; legacy `include "afe_x.scs"`
     is REPLACED by the exported subckt definitions)
  3. append directives verbatim from the legacy template (analysis,
     options, save, nodeset/ic, montecarlo block)

Verification (gate): for every X instance, net-by-port mapping must match
the legacy instance<->source-subckt mapping; subckt device sets must match
the tran/*.scs sources; top-level passive/MOS devices must match the
legacy template devices node-for-node.

Run anywhere (pure text processing): python3 scripts/gen_tb_golden.py
"""
import re
import sys
from pathlib import Path

AFE = Path(__file__).resolve().parents[1]
SRC_DIR = AFE / "output" / "n2s_tb_golden"
NET = AFE / "netlists"
TRAN = AFE / "tran"

MODELS_TT = ('include "/home/lib/tsmc_12nm_installed/pdk/models/'
             'toplevel.scs" section=top_tt')
MC_INCS = [
    'include "/home/lib/tsmc_12nm_installed/pdk/models/'
    'cln12ffcll_1d8_sp_v1d0_2p4_usage.scs" section=TTGlobalCorner_LocalMC_'
    'MOS_MOSCAP',
    'include "/home/lib/tsmc_12nm_installed/pdk/models/'
    'cln12ffcll_1d8_sp_v1d0_2p4_usage.scs" section=TTGlobalCorner_LocalMC_'
    'RES_BIP_DIO_DISRES',
    'include "/home/lib/tsmc_12nm_installed/pdk/models/'
    'cln12ffcll_1d8_sp_v1d0_2p4_usage.scs" section=TTGlobalCorner_LocalMC_'
    'MOM',
]

# cell -> (header lines below "simulator lang=spectre", first-directive
#          marker of the legacy template, source patches {instance: new line})
HEADERS = {
    "tb_bias_dc": ["__MODELS__"],
    "tb_noise_smoke": [MODELS_TT],
    "tb_afe_dac_dc": [MODELS_TT],
    "tb_afe_txron_mc": MC_INCS,
    "tb_afe_cmp_mc": MC_INCS,
}
DIRECTIVE_AT = {
    "tb_bias_dc": "simOpts options temp=",
    "tb_noise_smoke": "tran tran stop=",
    "tb_afe_dac_dc": "dc1 dc",
    "tb_afe_txron_mc": "mc1 montecarlo",
    "tb_afe_cmp_mc": "nodeset gp=",
}

VS_SRC = "vsource type=sine"
IS_SRC = "isource type=sine"
SRC_PATCHES = {
    "tb_bias_dc": {
        "Vvdd": f"Vvdd (vdd 0) vsource dc=0.8"},
    "tb_noise_smoke": {
        "Vvdd": "Vvdd (vdd 0) vsource dc=0.8"},
    "tb_afe_dac_dc": {
        "Vvccio": "Vvccio (vccio 0) vsource dc=0.45",
        "Vvdd": "Vvdd (vdd 0) vsource dc=0.8",
        **{f"Vb{k}": f"Vb{k} (b{k} 0) vsource dc=__B{k}__"
           for k in range(8)}},
    "tb_afe_txron_mc": {
        "Vvdd": "Vvdd (vdd 0) vsource dc=0.8",
        "Vvccio": "Vvccio (vccio 0) vsource dc=0.45",
        "Vvss": "Vvss (vss 0) vsource dc=0",
        "Vdin0": "Vdin0 (din0 0) vsource dc=0",
        "Vdin1": "Vdin1 (din1 0) vsource dc=0.8",
        "Ipu": "Ipu (pad_pu 0) isource dc=2m",
        "Ipd": "Ipd (0 pad_pd) isource dc=2m"},
    "tb_afe_cmp_mc": {
        "Vvdd": "Vvdd (vdd 0) vsource dc=0.8",
        "Vvss": "Vvss (vss 0) vsource dc=0",
        "Vvref": "Vvref (vref 0) vsource dc=0.225",
        "Vvin": "Vvin (vin 0) vsource type=pwl "
                "wave=[0 0.10 0.5n 0.10 60n 0.35]",
        "Veval": "Veval (eval 0) vsource type=pulse val0=0 val1=0.8 "
                 "delay=__EVALD__ rise=10p fall=10p width=100n period=200n",
        "Vaz": "Vaz (az 0) vsource type=pulse val0=0 val1=__AZEN__ "
               "delay=0 rise=10p fall=10p width=1.5n period=200n"},
}

# legacy template -> included source subckts (replaced by exported defs)
LEGACY_INCLUDES = {
    "tb_bias_dc": ["afe_bias.scs"],
    "tb_afe_cmp_mc": ["afecmp_bank.scs", "afe_bias.scs"],
    "tb_afe_txron_mc": ["afe_tx_drv.scs"],
    "tb_afe_dac_dc": ["afe_dac_r2r.scs"],
}


def sub1(pattern, repl, text, n=1, what=""):
    new, cnt = re.subn(pattern, repl, text, flags=re.M)
    assert cnt == n, f"{what or pattern}: matched {cnt} != {n}"
    return new


def decl_order(subckt):
    """Instance declaration order of a subckt in tran/<subckt>.scs."""
    text = re.sub(r"\\\s*\n\s*", " ", (TRAN / f"{subckt}.scs").read_text())
    m = re.search(rf"subckt\s+{subckt}\s*\(([^)]*)\)(.*?)ends", text, re.S)
    names = []
    for line in m.group(2).splitlines():
        mm = re.match(r"(\S+)\s*\(", line.split("//")[0].strip())
        if mm:
            names.append(mm.group(1))
    return names


def reorder_subckt(text, subckt, order):
    """Rewrite a golden subckt body from si alphabetical emission to the
    source declaration order (line-permutation only)."""
    m = re.search(rf"(subckt {subckt} [^\n]*\n)(.*?)(\nends {subckt})",
                  text, re.S)
    head, body, tail = m.groups()
    byname, others = {}, []
    for l in body.splitlines():
        if not l.strip():
            continue
        mm = re.match(r"\s*(\w+)\s*\(", l)
        if mm and mm.group(1) in order:
            byname[mm.group(1)] = l
        else:
            others.append(l)
    assert not others, f"{subckt} unplaced lines: {others}"
    assert set(byname) == set(order), \
        f"{subckt}: device set {set(byname) ^ set(order)}"
    return text[:m.start()] + head + "\n".join(byname[n] for n in order) \
        + tail + text[m.end():]


def reorder_toplevel(src, legacy):
    """Permute golden top-level instance lines to the legacy template
    declaration order (si emits them alphabetically).  Numerically neutral
    for ideal sources, but MC mismatch draws are consumed in element order:
    swapping e.g. Xdrv_pu/Xdrv_pd swaps their mismatch realizations.
    Comment banners stick to the instance line that follows them."""
    order = [m.group(1) for m in re.finditer(r"^([A-Za-z]\w*) \(", legacy, re.M)]
    ends = list(re.finditer(r"^ends \S+", src, re.M))
    cut = ends[-1].end() if ends else 0
    head, tail = src[:cut], src[cut:].splitlines()
    groups, pending = [], []
    for l in tail:
        if not l.strip():
            continue
        if re.match(r"^[A-Za-z]\w* \(", l):
            groups.append((pending, l))
            pending = []
        elif l.lstrip().startswith("//"):
            pending.append(l)
        else:
            raise AssertionError(f"unexpected top line: {l}")
    assert not pending, f"trailing comments: {pending}"
    byname = {re.match(r"^([A-Za-z]\w*) \(", line).group(1): (c, line)
              for c, line in groups}
    assert set(byname) == set(order), f"top set {set(byname) ^ set(order)}"
    out = "\n".join("\n".join(c + [line])
                    for n in order for c, line in [byname[n]])
    return head + "\n" + out + "\n"


def parse_devices(text):
    """name -> (master, nodes, params-dict) for every instance line."""
    text = re.sub(r"\\\s*\n\s*", " ", text)
    out = {}
    for line in text.splitlines():
        line = line.split("//")[0].strip()
        m = re.match(r"(\S+)\s*\(([^)]*)\)\s+(\S+)(.*)", line)
        if m and not line.startswith(("subckt", "ends")):
            out[m.group(1)] = (m.group(3), m.group(2).split(),
                               dict(re.findall(r"(\w+)=(\S+)", m.group(4))))
    return out


def gen(cell):
    src = (SRC_DIR / f"{cell}_si.scs").read_text()
    src = re.sub(r"\\\s*\n\s*", " ", src)

    # 0. device-emission normalization (measured-neutral golden rewrites)
    nmos = len(re.findall(r"[np]ch_\w+_mac ", src))
    src = re.sub(r"^(\s*[A-Za-z]\w* \([^)]*\) [np]ch_\w+_mac )"
                 r"l=([\d.]+)n nfin=(\d+) .*$",
                 lambda m: f"{m.group(1)}l={float(m.group(2)):g}n "
                           f"nfin={m.group(3)}", src, flags=re.M)
    ncf = len(re.findall(r"cfmom_2t_p80 [^\n]+", src))
    src = re.sub(r"(cfmom_2t_p80) [^\n]+", r"\1", src)

    # 1. top-level source patches (exactly-once per instance)
    for name, line in SRC_PATCHES[cell].items():
        pat = (rf"^{name} \([^)]*\) vsource type=sine\s*$" if
               line.split(") ")[1].startswith("vsource") else
               rf"^{name} \([^)]*\) isource type=sine\s*$")
        src = sub1(pat, line, src, 1, name)

    # 1.5 MC TBs: spectre montecarlo mismatch draws are consumed in netlist
    # element order, so si's alphabetical subckt emission re-assigns the
    # per-seed realization vs the legacy include flow.  Emit subckt bodies
    # in tran/*.scs source declaration order -> per-seed bit-compatibility
    # (proven 2026-09-05: az_on seed1 trip 0.181138941 both sides exact).
    # Top-level instance lines go to legacy declaration order for the same
    # reason (instance PAIR order swaps realizations: Xdrv_pu/Xdrv_pd).
    if cell in ("tb_afe_txron_mc", "tb_afe_cmp_mc"):
        for sub in list(re.findall(r"^subckt (\S+)", src, re.M)):
            src = reorder_subckt(src, sub, decl_order(sub))
            print(f"[{cell}] reordered subckt {sub} to source order")
    legacy_tpl = (NET / f"{cell}.scs").read_text()
    src = reorder_toplevel(src, legacy_tpl)

    # 2. header
    header = [f"// UCIe-AP RX AFE golden TB ({cell}) -- si export assembled "
              "by scripts/gen_tb_golden.py", "simulator lang=spectre", ""]
    header += HEADERS[cell] + [""]

    # 3. directives verbatim from the legacy template
    legacy = (NET / f"{cell}.scs").read_text()
    idx = legacy.index(DIRECTIVE_AT[cell])
    directives = ("\n// ---- directives (verbatim from "
                  f"{cell}.scs) ----\n" + legacy[idx:])

    body = "\n".join(l for l in src.splitlines() if l.strip())
    out = SRC_DIR / f"golden_{cell}.scs"
    out.write_text("\n".join(header) + body + "\n" + directives)
    print(f"[{cell}] wrote {out.name} "
          f"({len(out.read_text().splitlines())} lines, "
          f"normalized {nmos} MOS / {ncf} cfmom)")


# ---------------------------------------------------------------- verify
def port_map(nodes, ports):
    return dict(zip(ports, nodes))


def verify(cell):
    ok = True
    gold = (SRC_DIR / f"golden_{cell}.scs").read_text()
    legacy = (NET / f"{cell}.scs").read_text()

    # subckt defs in golden: header ports + device set vs tran/*.scs source
    # (si emission: `subckt name p1 p2 ...` -- no parens around ports)
    for m in re.finditer(r"subckt (\S+)[^\n]*\n(.*?)\nends \S+", gold, re.S):
        sname, sbody = m.group(1), m.group(2)
        srcf = TRAN / f"{sname}.scs"
        s2 = re.search(rf"subckt\s+{sname}\s*\(([^)]*)\)(.*?)ends",
                       srcf.read_text(), re.S)
        gdev = parse_devices(sbody)
        sdev = parse_devices(s2.group(2))
        if set(gdev) != set(sdev):
            print(f"[{cell}] FAIL subckt {sname} devices "
                  f"{set(gdev) ^ set(sdev)}")
            ok = False
        for d in set(gdev) & set(sdev):
            if gdev[d][0] != sdev[d][0] or gdev[d][1] != sdev[d][1]:
                print(f"[{cell}] FAIL subckt {sname}/{d} "
                      f"{gdev[d][:2]} != {sdev[d][:2]}")
                ok = False
        print(f"[{cell}] subckt {sname}: {len(gdev)} devices vs source "
              f"{len(sdev)} {'OK' if set(gdev) == set(sdev) else 'DIFF'}")

    # top-level: golden devices vs legacy template devices
    gtop = parse_devices(strip_subckts(gold))
    ltop = parse_devices(legacy)
    # drop legacy includes (their subckts come as defs in golden)
    lsrc_ports = {}
    for inc in LEGACY_INCLUDES.get(cell, []):
        t = (TRAN / inc).read_text()
        for m in re.finditer(r"subckt\s+(\S+)\s*\(([^)]*)\)", t):
            lsrc_ports[m.group(1)] = m.group(2).split()

    for name, (gm, gn, _gp) in gtop.items():
        if name not in ltop:
            print(f"[{cell}] FAIL top {name} not in legacy")
            ok = False
            continue
        lm, ln, _lp = ltop[name]
        if gm != lm:
            print(f"[{cell}] FAIL top {name} master {gm} != {lm}")
            ok = False
            continue
        if gm in lsrc_ports:  # X instance: compare net-by-port
            gmap = port_map(gn, subckt_ports(gold, gm))
            lmap = port_map(ln, lsrc_ports[gm])
            # gnd! already emitted as 0 in golden; legacy uses 0 too
            for p in lmap:
                if gmap.get(p) != lmap[p]:
                    print(f"[{cell}] FAIL top {name}.{p} "
                          f"{gmap.get(p)} != {lmap[p]}")
                    ok = False
        else:  # source/passive/MOS: node tuple must be identical
            if gn != ln:
                print(f"[{cell}] FAIL top {name} nodes {gn} != {ln}")
                ok = False
    if set(gtop) != set(ltop):
        print(f"[{cell}] FAIL top device set {set(gtop) ^ set(ltop)}")
        ok = False
    print(f"[{cell}] gate: {'PASS' if ok else 'FAIL'} "
          f"({len(gtop)} top devices)")
    return ok


def subckt_ports(text, name):
    m = re.search(rf"subckt {name} ([^\n]*)\n", text)
    return m.group(1).split()


def strip_subckts(text):
    return re.sub(r"subckt \S+[^\n]*\n.*?\nends \S+\n", "", text, flags=re.S)


if __name__ == "__main__":
    cells = sys.argv[1:] or list(HEADERS)
    ok_all = True
    for c in cells:
        gen(c)
        ok_all &= verify(c)
    print(f"\n=== gen_tb_golden: "
          f"{'ALL PASS' if ok_all else 'FAILURES PRESENT'} ===")
    sys.exit(0 if ok_all else 1)
