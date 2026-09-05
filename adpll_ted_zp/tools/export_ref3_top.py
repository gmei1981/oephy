#!/usr/bin/env python3
"""si export adpll_ref3_top + semantic compare vs sim/ref3/v3/main/main.scs.

Compare granularity: every instance in the exported subckt adpll_ref3_top body
vs the reference X/M/R instance lines of main.scs:
  - cell/model name equal
  - node list equal per instance (si orders by terminal; ref by subckt port)
  - params: ref value must equal export value, OR be absent from export while
    equal to the CDF default (tools/va_build/ref3_va.json) - si omits
    default-equal params.
Analog subckt bodies (ldo_05/vco_x_c_dac/dtc_10b_ss) are skipped here -
already verified standalone cell-by-cell.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CDSLIB = ROOT / "virtuoso_ws" / "cds.lib"
BRIDGE = "ref3sch"
RUN = "/tmp/si_ref3_top"
MAIN = ROOT / "sim" / "ref3" / "v3" / "main" / "main.scs"
VA_JSON = ROOT / "tools" / "va_build" / "ref3_va.json"


def run(*args, timeout=900, cwd=None):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                       cwd=cwd)
    return r.returncode, (r.stdout + r.stderr)


def ev(skill, timeout=300):
    return run("vlink", "evalstring", skill, "-i", BRIDGE, "-t", str(timeout))


def split_top_instances(text):
    """Split a spectre netlist into instance lines, honoring \\ continuations.

    Returns {name: (model, [nodes], {param: value})} for lines that are
    instances (X... or component with ( nodes ) model).
    """
    insts = {}
    lines = []
    buf = ""
    for raw in text.splitlines():
        if raw.rstrip().endswith("\\"):
            buf += raw.rstrip()[:-1] + " "
            continue
        line = (buf + raw).strip()
        buf = ""
        if line:
            lines.append(line)
    for line in lines:
        m = re.match(r"^(\S+)\s*\(([^)]*)\)\s*(\S+)(.*)$", line)
        if not m:
            continue
        name, nodes_s, model, rest = m.groups()
        nodes = nodes_s.split()
        params = dict(re.findall(r"(\w+)=([\w.+-]+(?:[a-zA-Z]+)?)", rest))
        insts[name] = (model, nodes, params)
    return insts


SUB_HEADER = re.compile(r"subckt\s+(\S+)\s+(.*?)\\\n(.*?)\(ends|\Z", re.S)


def subckt_ports(text, cell):
    """Port list of `cell`'s subckt header (joins \\ continuations first)."""
    flat = re.sub(r"\\\s*\n\s*", " ", text)
    m = re.search(rf"subckt\s+{cell}\s+([^\n]*)", flat)
    if not m:
        return None
    return re.findall(r"[A-Za-z_]\w*", m.group(1))


ENG = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
       "k": 1e3, "K": 1e3, "meg": 1e6, "G": 1e9, "T": 1e12}


def num(v):
    """Numeric value of a spectre param string ('50p'->5e-11), else None."""
    if v is None:
        return None
    s = str(v)
    m = re.fullmatch(r"([+-]?[\d.]+)([fpnumkKG]|meg)?", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return None
    x = float(m.group(1))
    return x * ENG[m.group(2)] if m.group(2) else x


def param_eq(a, b):
    if str(a) == str(b):
        return True
    na, nb = num(a), num(b)
    return na is not None and nb is not None and abs(na - nb) <= 1e-15 * max(abs(na), abs(nb), 1.0)


def main():
    # 1. export
    ev(f'sh("rm -rf {RUN}")')
    rc, out = ev(f'simInitEnvWithArgs("{RUN}" "adpll_sch" "adpll_ref3_top" '
                 f'"schematic" "spectre" nil)', timeout=300)
    env_path = Path(RUN) / "si.env"
    if not env_path.exists():
        print("no si.env")
        sys.exit(1)
    env = env_path.read_text()
    if "simViewList" not in env:
        env_path.write_text(env + "\nsimViewList = '(\"spectre cmos_sch "
                             "schematic veriloga\")\nsimStopList = "
                             "'(\"spectre\")\nsimNetlistHier = t\n")
    rc, out = run("si", "-batch", "-cdslib", str(CDSLIB), "-command", "nl",
                  timeout=1200, cwd=RUN)
    if rc:
        print("si failed:", out[-500:])
        sys.exit(1)
    netlist = (Path(RUN) / "netlist").read_text()
    dst = ROOT / "tools" / "adpll_ref3_top_sch_netlist.scs"
    dst.write_text(netlist)
    print(f"exported -> {dst}")

    # 2. exported top-level instances = lines after the last 'ends'
    #    (si emits subckt defs for lower cells first, top instances at file tail)
    tail = netlist[netlist.rfind("ends"):]
    exp_all = split_top_instances(tail)
    exp = {k: v for k, v in exp_all.items() if not k.startswith("//")}

    # 3. reference: instance lines from main.scs (exclude sources/analyses)
    ref_text = MAIN.read_text()
    ref_all = split_top_instances(ref_text)
    drop = {k for k, (mo, _, _) in ref_all.items()
            if mo in ("vsource", "vpulse", "spectre") or k.startswith("V")}
    ref = {k: v for k, v in ref_all.items() if k not in drop}

    # port orders: analog cells from subckt headers (ref vs export may differ),
    # VA cells from module declaration order (both sides)
    va = json.loads(VA_JSON.read_text())
    va_ports = {cell: [p[0] for p in d["ports"]] for cell, d in va.items()}
    defaults = {cell: {p[0]: p[2] for p in d["params"]}
                for cell, d in va.items()}
    analog = {}
    for cell, fn in [("ldo_05", "ldo_05.scs"), ("vco_x_c_dac", "vco_c_dac.scs"),
                     ("dtc_10b_ss", "dtc_10b_ss.scs")]:
        analog[cell] = {
            "ref": subckt_ports((ROOT / "netlist" / "inc" / fn).read_text(), cell),
            "exp": subckt_ports(netlist, cell),
        }

    MOS_KEYS = {"nf", "r", "l", "w"}

    # 4. compare
    only_ref = set(ref) - set(exp)
    only_exp = set(exp) - set(ref)
    bad = 0
    for name in sorted(set(ref) & set(exp)):
        rm, rn, rp = ref[name]
        em, en, ep = exp[name]
        errs = []
        if rm != em:
            errs.append(f"model {rm} != {em}")
            continue
        if rm in analog:
            # name-based node compare through subckt port lists
            rp_order = analog[rm]["ref"] or []
            ep_order = analog[rm]["exp"] or []
            if len(rp_order) != len(rn) or len(ep_order) != len(en):
                errs.append(f"port/node count {len(rp_order)}/{len(rn)} "
                            f"vs {len(ep_order)}/{len(en)}")
            else:
                rmap = dict(zip(rp_order, rn))
                emap = dict(zip(ep_order, en))
                for p in rp_order:
                    if rmap.get(p) != emap.get(p):
                        errs.append(f"port {p}: ref {rmap.get(p)} "
                                    f"!= exp {emap.get(p)}")
        else:
            if rn != en:
                if len(rn) != len(en):
                    errs.append(f"node count {len(rn)} != {len(en)}")
                else:
                    diffs = [(a, b) for a, b in zip(rn, en) if a != b]
                    errs.append(f"nodes differ at {diffs[:5]}")
        # params: bidirectional default-normalized
        if rm in va_ports:
            cdf = defaults.get(rm, {})
            keys = set(rp) | set(ep)
            for k in keys:
                a, b = rp.get(k), ep.get(k)
                if a is not None and b is not None:
                    if not param_eq(a, b):
                        errs.append(f"param {k}: {a} != {b}")
                elif a is not None:      # in ref, missing in export
                    if k not in cdf or not param_eq(cdf[k], a):
                        errs.append(f"param {k}={a} missing in export")
                else:                    # in export, missing in ref
                    if k not in cdf or not param_eq(cdf[k], b):
                        errs.append(f"param {k}={b} extra in export")
        else:
            for k in MOS_KEYS & (set(rp) | set(ep)):
                a, b = rp.get(k), ep.get(k)
                if (a is None) != (b is None) or (a is not None and not param_eq(a, b)):
                    errs.append(f"param {k}: ref {a} != exp {b}")
        if errs:
            bad += 1
            print(f"  [BAD] {name}: {'; '.join(errs)}")
    for name in sorted(only_ref):
        print(f"  [MISSING] {name} only in reference")
    for name in sorted(only_exp):
        print(f"  [EXTRA] {name} only in export")

    print(f"\ninstances: ref={len(ref)} exp={len(exp)} bad={bad} "
          f"missing={len(only_ref)} extra={len(only_exp)}")
    ok = not bad and not only_ref and not only_exp
    print("ALL MATCH ✓" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
