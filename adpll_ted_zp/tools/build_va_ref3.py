#!/usr/bin/env python3
"""P1: build VA symbol+CDF cells for the 15 ref3 digital modules.

Parses sim/ref3/v3/main/pll_*.va (ports in module declaration order +
directions + parameters), then drives the local Virtuoso session via vlink:
loads tools/va_build/ref3_va.il, writes per-module gen_<cell>.il (symbol
geometry + CDF calls), loads each, and readback-verifies terminal order,
CDF pin order/params/simInfo against the .va declarations.

Usage: python3 tools/build_va_ref3.py [--only pll_lockdet ...] [--json]
Output: tools/va_build/ref3_va.json (ports/params per module, for P5 assembly).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VA_DIR = ROOT / "sim" / "ref3" / "v3" / "main"
IL_DIR = ROOT / "tools" / "va_build"
LIB = "adpll_sch"
BRIDGE = "ref3sch"

MODULES = [
    "pll_fsm", "pll_lockdet", "pll_dsm_fb", "pll_mmd_ps", "pll_divn",
    "pll_tdc_beh", "pll_pfd", "pll_afc6", "pll_fll", "pll_lpf",
    "pll_dac9b", "pll_dsm_dco", "pll_cal_kdtc", "pll_cal_dcodcc",
    "pll_dtc_code",
]

DIR_MAP = {"inout": "inputOutput", "output": "output", "input": "input"}


def run(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    out = (r.stdout + r.stderr)
    return r.returncode, out


def parse_va(modname):
    """Return (ports[(name,dir)], params[(name,type,def)]) or raises."""
    text = (VA_DIR / f"{modname}.va").read_text()
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//.*", " ", text)
    m = re.search(r"module\s+%s\s*\((.*?)\)\s*;" % re.escape(modname),
                  text, re.S)
    if not m:
        raise RuntimeError(f"module decl not found in {modname}.va")
    ports = [p.strip() for p in m.group(1).split(",") if p.strip()]
    body = text[m.end(): text.find("endmodule", m.end())]
    direction = {}
    for kind in ("inout", "output", "input"):
        for mm in re.finditer(r"\b%s\s+([^;]+);" % kind, body):
            for p in mm.group(1).split(","):
                p = p.strip()
                if p:
                    direction[p] = kind
    portspec = [(p, direction.get(p, "inout")) for p in ports]
    params = []
    for mm in re.finditer(r"\bparameter\s+(?:(real|integer)\s+)?([^;]+);", body):
        typ = {"real": "float", "integer": "int"}.get(mm.group(1), "float")
        for decl in mm.group(2).split(","):
            dm = re.match(r"\s*([A-Za-z_]\w*)\s*=\s*(.+?)\s*$", decl)
            if dm:
                params.append((dm.group(1), typ, dm.group(2).strip()))
    return portspec, params


def geom(portspec):
    """Assign pin positions; returns (ports-with-pos, body, selbox, inst, log).

    Vertical layout: inputs/inouts left edge, outputs right edge, pitch 0.25.
    Horizontal strip (any side > 60 pins): outputs bottom, inputs top —
    the convention already used by the existing pll_dtc_decoder_10b symbol.
    Port list order stays module-declaration order (termOrder == declaration).
    """
    ins = [i for i, (n, d) in enumerate(portspec)
           if d in ("input", "inout")]
    outs = [i for i, (n, d) in enumerate(portspec) if d == "output"]
    rows = []
    if max(len(ins), len(outs)) > 60:
        w = 0.125 * len(outs) + 0.6
        ki = ko = 0
        for idx, (n, d) in enumerate(portspec):
            if d == "output":
                x = 0.15 + ko * 0.125
                ko += 1
                rows.append((n, DIR_MAP[d], x, -0.45, "lowerLeft",
                             x - 0.02, -0.58))
            else:
                x = 0.15 + ki * 0.3
                ki += 1
                rows.append((n, DIR_MAP[d], x, 0.45, "upperLeft",
                             x - 0.02, 0.58))
        return rows, (0, -0.45, w, 0.45), (0, -0.75, w + 0.15, 0.75), \
            (1.0, 0.12), (1.0, -0.15)
    h = max(1.5, 0.25 * max(len(ins), len(outs)) + 0.5)
    ki = ko = 0
    for idx, (n, d) in enumerate(portspec):
        if d == "output":
            y = h / 2 - 0.25 - 0.25 * ko
            ko += 1
            rows.append((n, DIR_MAP[d], 0.5, y, "centerRight", 0.35, y))
        else:
            y = h / 2 - 0.25 - 0.25 * ki
            ki += 1
            rows.append((n, DIR_MAP[d], -0.5, y, "centerLeft", -0.35, y))
    return rows, (-0.5, -h / 2, 0.5, h / 2), (-0.9, -h / 2 - 0.3,
                                               0.9, h / 2 + 0.3), \
        (0.0, h / 4), (0.0, -h / 4)


def skl(items):
    """Python sequence -> SKILL list literal (strings quoted, floats %g)."""
    parts = []
    for it in items:
        if isinstance(it, str):
            parts.append('"%s"' % it)
        elif isinstance(it, float):
            parts.append("%g" % it)
        elif isinstance(it, (list, tuple)):
            parts.append(skl(it))
        else:
            parts.append(str(it))
    return "list(%s)" % " ".join(parts)


def stage_veriloga(mod):
    """Pre-stage a veriloga view dir (copy the known-good pll_lms pattern,
    swap in this module's source). netlist.oa stays stale until the VA
    editor save regenerates it (GUI step; the only proven mechanism)."""
    import shutil
    lib = ROOT / "virtuoso_ws" / "adpll_sch"
    src = lib / "pll_lms" / "veriloga"
    dst = lib / mod / "veriloga"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    shutil.copy(VA_DIR / f"{mod}.va", dst / "veriloga.va")
    bak = dst / "veriloga.va.bak"
    if bak.exists():
        bak.unlink()
    return (dst / "veriloga.va").stat().st_size


def build(mod):
    portspec, params = parse_va(mod)
    rows, body, selbox, inst, log = geom(portspec)
    port_names = [n for n, d in portspec]
    port_dirs = [DIR_MAP[d] for n, d in portspec]
    vsize = stage_veriloga(mod)
    lines = [
        f'; generated by build_va_ref3.py — {mod}',
        f'when(!ref3VaSym(\"{LIB}\" "{mod}" {skl(list(rows))} '
        f'{skl(list(body))} {skl(list(selbox))} {skl(list(inst))} '
        f'{skl(list(log))}) error("ref3VaSym {mod} failed"))',
        f'when(!ref3VaCdf(\"{LIB}\" "{mod}" {skl(port_names)} '
        f'{skl(port_dirs)} {skl([list(p) for p in params])}) '
        f'error("ref3VaCdf {mod} failed"))',
    ]
    il = IL_DIR / f"gen_{mod}.il"
    il.write_text("\n".join(lines) + "\n")
    rc, out = run("vlink", "load", str(il), "-i", BRIDGE)
    if rc != 0 or re.search(r"\*Error\*", out):
        return False, f"load failed: {out.strip()[-200:]}"
    # readback verify
    _, t = run("vlink", "evalstring", f'ref3VaRead(\"{LIB}\" "{mod}")',
               "-i", BRIDGE)
    terms = re.findall(r'"([^"]+)"', t.split("TERMS", 1)[-1]) \
        if "TERMS" in t else []
    _, c = run("vlink", "evalstring", f'ref3VaCdfRead(\"{LIB}\" "{mod}")',
               "-i", BRIDGE)
    # pins live on the symbol terminals now; CDF carries value params + simInfo
    pnames = [m[0] for m in
              re.findall(r'\("([^"]+)"\s+"string"\s+"([^"]*)"', c)] \
        if "PARAMS" in c else []
    ok = (terms == port_names
          and pnames == [p[0] for p in params]
          and "subcircuit" in c and "*Error*" not in t + c)
    detail = f"terms {len(terms)}/{len(port_names)} cdfparams " \
             f"{len(pnames)}/{len(params)} va={vsize}B"
    if not ok:
        detail += f" | raw terms={t.strip()[:120]} cdf={c.strip()[:160]}"
    return ok, detail, {"ports": portspec, "params": params}


def main():
    only = []
    args = sys.argv[1:]
    if "--only" in args:
        i = args.index("--only")
        only = args[i + 1:]
    mods = only or MODULES
    rc, out = run("vlink", "load", str(IL_DIR / "ref3_va.il"), "-i", BRIDGE)
    if rc != 0 or "*Error*" in out:
        print("ref3_va.il load failed:", out.strip()[-300:])
        return 1
    db, fails = {}, []
    for m in mods:
        res = build(m)
        db[m] = {"ports": res[2]["ports"], "params": res[2]["params"]} \
            if res[0] else None
        print(f"  {'PASS' if res[0] else 'FAIL'}  {m:16s} {res[1]}")
        if not res[0]:
            fails.append(m)
    if db and not fails:
        (IL_DIR / "ref3_va.json").write_text(json.dumps(db, indent=1))
    print("RESULT:", "ALL PASS" if not fails else f"FAILED: {fails}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
