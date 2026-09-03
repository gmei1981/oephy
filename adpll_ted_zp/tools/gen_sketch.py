#!/usr/bin/env python3
"""Emit a SKILL script that draws an analog subckt schematic in Virtuoso.

Reads the vlink AST JSON (instances + params) and reuses sch_pilot's role
classification + column assignment.  Net planning is done here in Python from
the AST connectivity; the SKILL only collects terminal coordinates at runtime
(keyed "instName.termName") and routes the planned chains with L-segments.

Usage: python3 tools/gen_sketch.py <cell> --ast <ast.json> --out <draw.il>
"""
import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sch_pilot import classify, assign_columns, get_instances  # noqa: E402

COL_PITCH = 4.0
Y_TOP, Y_BOT = 0.0, -4.0
Y_RAIL_P, Y_RAIL_N = 2.5, -6.5
X_PIN_L, X_PIN_R = -3.0, 18.0
PIN_XY = {"VINP": (X_PIN_L, 0.5), "VINN": (X_PIN_L, -1.5), "VBIAS": (X_PIN_L, -3.5),
          "EOUT": (X_PIN_R, -1.5), "VDD": (7.0, Y_RAIL_P), "VSS": (7.0, Y_RAIL_N)}

_SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3,
           "M": 1e6, "G": 1e9}

SET_PROPS = ("l", "w", "nf", "nfin", "multi", "sd", "sa", "sb",
             "ploda1", "ploda2", "ploda3", "plodb1", "plodb2", "plodb3",
             "nf_flag", "smbt", "smbb", "dinsaflag", "ppitch", "spot", "spob",
             "spotl1", "spobl1", "spotl2", "spobl2", "spotr1", "spobr1",
             "spotr2", "spobr2")


def val(raw):
    s = str(raw).strip()
    m = re.match(r"([+-]?[0-9.]+)([a-zA-Z]*)$", s)
    if not m:
        raise ValueError(f"bad value {s!r}")
    num, suf = float(m.group(1)), m.group(2)
    return num * (_SUFFIX[suf] if suf in _SUFFIX else 1.0)


def fnum(x):
    return f"{x:.9g}"


def plan_nets(insts, ports, placed):
    """net -> ordered anchor specs: (ref) where ref is ('i', name, term) or ('p', x, y)"""
    nets = OrderedDict()
    for i in insts:
        for idx, term in enumerate(("D", "G", "S")):
            if idx < len(i["nets"]):
                nets.setdefault(i["nets"][idx], []).append(("i", i["name"], term))
    # pins (creation coords; pin figure anchors there)
    for p in ports:
        if p in PIN_XY and p in nets:
            nets[p].append(("p",) + PIN_XY[p])
    # order anchors by planned x (pin coords known; inst coords from placement)
    def xof(a):
        if a[0] == "p":
            return a[1]
        return placed[a[1]][0]
    for n in nets:
        nets[n].sort(key=xof)
    return nets


def skill_ref(a):
    if a[0] == "i":
        return f'(arrayref pos "{a[1]}.{a[2]}")'
    return f'(list {fnum(a[1])} {fnum(a[2])})'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cell")
    ap.add_argument("--ast", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-pins", action="store_true",
                    help="skip pin figures; port nets carried by wire labels")
    ap.add_argument("--instances-only", action="store_true",
                    help="place instances only; skip pins/wires/labels")
    ap.add_argument("--export-dir", default="/home/gmei/git/oephy/adpll_ted/virtuoso_ws",
                    help="directory for the exported schematic PNG")
    args = ap.parse_args()

    ast = json.loads(Path(args.ast).read_text())
    sub_name, ports, insts = get_instances(ast)
    roles, rails, pair_src = classify(insts, ports)
    cols = assign_columns(insts, roles)
    placed = {}
    for k, col in enumerate(cols):
        for key, y in (("top", Y_TOP), ("bot", Y_BOT), ("pas", (Y_TOP + Y_BOT) / 2)):
            i = col.get(key)
            if i:
                placed[i["name"]] = (k * COL_PITCH, y)
    nets = plan_nets(insts, ports, placed)
    internal = [n for n in nets if n not in ports]

    L = []
    A = L.append
    A(f";; auto-generated schematic drawing script for {sub_name}")
    A(";")
    A('(let ((cv nil) (inst nil) (ip nil) (trm nil) (a1 nil) (a2 nil) (anch nil) (xm 0.0))')
    A('  (unless (ddGetObj "adpll_sch") (dbCreateLib "adpll_sch"))')
    A('  (setq cv (dbOpenCellViewByType "adpll_sch" "%s" "schematic" "schematic" "a"))'
      % sub_name)
    A("  ;; ---- instances ----")
    A("  (setq ih (makeTable 'ih nil))")
    for name, (x, y) in placed.items():
        i = next(i for i in insts if i["name"] == name)
        master = "nch_svt_mac" if i["polarity"] == "n" else "pch_svt_mac"
        A('  (setq inst (dbCreateInstByMasterName cv "tsmcN12" "%s" "symbol" "%s" '
          '%s:%s "R0"))' % (master, name, fnum(x), fnum(y)))
        A('  (setarray ih "%s" inst)' % name)
        for p in i["params"]:
            if p in SET_PROPS:
                try:
                    A(f'  (dbReplaceProp inst "{p}" "float" {fnum(val(i["params"][p]))})')
                except ValueError:
                    pass
    if args.instances_only:
        A("  ;; (instances only: wiring/pins deferred to GUI or follow-up round)")
        A("  (dbSave cv)")
        A('  (geOpen ?lib "adpll_sch" ?cell "%s" ?view "schematic" ?mode "r")' % sub_name)
        A('  (errset (hiExportImage (hiGetCurrentWindow) "%s/%s.png"))' % (args.export_dir, sub_name))
        A("  (sleep 3600)")
        A("  )")
        text = "\n".join(L) + "\n"
        balance = 0
        for ln in text.splitlines():
            if not ln.lstrip().startswith(";"):
                balance += ln.count("(") - ln.count(")")
        if balance != 0:
            raise SystemExit(f"paren imbalance in generated SKILL: {balance:+d}")
        Path(args.out).write_text(text)
        print(f"wrote {args.out}  ({len(placed)} instances, instances-only, paren balance OK)")
        return
    A("  ;; ---- pins ----")
    if args.no_pins:
        A("  ;; (no pins: port nets carried by labels at the pin coordinates)")
        for p in ports:
            if p in PIN_XY:
                A('  (schCreateWireLabel cv "draw" "%s" %s:%s "lowerLeft" "R0" "stick" 0.0625)'
                  % (p, fnum(PIN_XY[p][0]), fnum(PIN_XY[p][1])))
    else:
        A('  (schCreatePin cv "VINP" "input" "square" %s:0.5)' % fnum(X_PIN_L))
        A('  (schCreatePin cv "VINN" "input" "square" %s:-1.5)' % fnum(X_PIN_L))
        A('  (schCreatePin cv "VBIAS" "input" "square" %s:-3.5)' % fnum(X_PIN_L))
        A('  (schCreatePin cv "EOUT" "output" "square" %s:-1.5)' % fnum(X_PIN_R))
        A('  (schCreatePin cv "VDD" "inputOutput" "square" 7:%s)' % fnum(Y_RAIL_P))
        A('  (schCreatePin cv "VSS" "inputOutput" "square" 7:%s)' % fnum(Y_RAIL_N))
    A("  ;; ---- terminal anchors (keyed instName.termName) ----")
    A('  (setq pos (makeTable \'pos nil))')
    for name in placed:
        i = next(i for i in insts if i["name"] == name)
        for idx, term in enumerate(("D", "G", "S")):
            if idx >= len(i["nets"]):
                continue
            A('  (setq trm (dbGetInstTermByName (arrayref ih "%s") "%s"))' % (name, term))
            A('  (when trm (setq ip (car trm~>instPins)))')
            A('  (when (and ip ip~>fig)')
            A('    (setarray pos "%s.%s" (list (car ip~>fig~>xy) (cadr ip~>fig~>xy))))'
              % (name, term))
    A("  ;; ---- nets ----")
    for n, anchors in nets.items():
        if n in ("VDD", "VSS"):
            ry = Y_RAIL_P if n == "VDD" else Y_RAIL_N
            A(f'  ;; rail {n}: horizontal bus + stubs')
            A(f'  (setq anch (list {" ".join(skill_ref(a) for a in anchors)}))')
            A('  (setq anch (remq nil anch))')
            A('  (setq anch (sort anch (lambda (a b) (lessp (car a) (car b)))))')
            A('  (when anch')
            A('    (schCreateWire cv "draw" (list (car (car anch)):%s '
              '(car (car (last anch))):%s) 0.0625 0.0625 0.0)' % (fnum(ry), fnum(ry)))
            A('    (foreach p anch')
            A('      (schCreateWire cv "draw" (list (car p):(cadr p) (car p):%s) '
              '0.0625 0.0625 0.0)))' % fnum(ry))
        else:
            A(f'  ;; net {n}: chain L-route')
            A(f'  (setq anch (list {" ".join(skill_ref(a) for a in anchors)}))')
            A('  (setq anch (remq nil anch))')
            A('  (setq anch (sort anch (lambda (a b) (lessp (car a) (car b)))))')
            A('  (when (greaterp (length anch) 1)')
            A('    (setq a1 (car anch))')
            A('    (foreach a2 (cdr anch)')
            A('      (setq xm (car a2))')
            A('      (schCreateWire cv "draw" (list (car a1):(cadr a1) xm:(cadr a1)) '
              '0.0625 0.0625 0.0)')
            A('      (schCreateWire cv "draw" (list xm:(cadr a1) xm:(cadr a2)) '
              '0.0625 0.0625 0.0)')
            A('      (setq a1 a2)))')
            A('  (when (and anch (member "%s" \'("%s")))' % (n, '" "'.join(internal)))
            A('    (schCreateWireLabel cv "draw" "%s" (car (car anch)):(cadr (car anch)) '
              '"lowerLeft" "R0" "stick" 0.0625))' % n)
    A("  (dbSave cv)")
    A('  (geOpen ?lib "adpll_sch" ?cell "%s" ?view "schematic" ?mode "r")' % sub_name)
    A('  (hiExportImage (hiGetCurrentWindow) "/home/mei/adpll_sch_ws/%s.png")' % sub_name)
    A("  (sleep 3600)")
    A("  )")

    text = "\n".join(L) + "\n"
    # paren-balance sanity check (catches structural mistakes before uploading)
    balance = 0
    for ln in text.splitlines():
        if not ln.lstrip().startswith(";"):
            balance += ln.count("(") - ln.count(")")
    if balance != 0:
        raise SystemExit(f"paren imbalance in generated SKILL: {balance:+d}")
    Path(args.out).write_text(text)
    print(f"wrote {args.out}  ({len(placed)} instances, {len(nets)} nets, "
          f"internal: {', '.join(internal)}, paren balance OK)")


if __name__ == "__main__":
    main()
