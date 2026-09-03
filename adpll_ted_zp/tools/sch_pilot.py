#!/usr/bin/env python3
"""Netlist -> topology roles + SVG schematic preview (small analog blocks).

Offline pilot for netlist-to-schematic conversion, written for the adpll_ted
12nm blocks. Deterministic: connectivity-based role classification, rail
inference from bulk ties, matched-column placement (PMOS top / NMOS bottom,
D-net mates share a column), label-style SVG rendering with drawn ties only
where terminals align (same-column vertical ties, same-row bus segments).

Usage: python3 tools/sch_pilot.py <netlist.scs> [--ast <ast.json>]
Writes <netlist>.preview.html next to the netlist.
"""
import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# palette (light figure card, consistent with report pages)
P_STROKE, P_FILL = "#2a78d6", "#eef4fc"
N_STROKE, N_FILL = "#eb6834", "#fdf3ee"
X_STROKE, X_FILL = "#1baf7a", "#effaf4"
INK, MUTED, RAIL = "#191817", "#6f6d67", "#8b887f"

BOX_W, BOX_H = 84, 44
COL_W, MARGIN = 150, 90
Y_RAIL_P, Y_RAIL_N = 46, 322
Y_TOP, Y_BOT, Y_MID = 110, 208, 160
H_CANVAS = 366


def load_ast(netlist, ast_path=None):
    if ast_path:
        return json.loads(Path(ast_path).read_text())
    tmp = "/tmp/sch_pilot_ast.json"
    p = subprocess.run(
        ["vlink", "netlist", "parse", str(netlist), "--json", "--output", tmp],
        capture_output=True, text=True,
    )
    if p.returncode:
        raise SystemExit(p.stderr.strip() or "vlink parse failed")
    return json.loads(Path(tmp).read_text())


def get_instances(ast):
    subs = ast.get("subckts", [])
    if len(subs) != 1:
        raise SystemExit(f"expect exactly one subckt, got {len(subs)}")
    sub = subs[0]
    ports = [str(p.get("normalized") or p.get("raw")).strip("()")
             for p in sub.get("pins", [])]
    out = []
    for i in sub.get("instances", []):
        nets = [str(n.get("normalized") or n.get("raw")) for n in i.get("nets", [])]
        params = {p["name"]: str(p.get("value", {}).get("raw", ""))
                  for p in i.get("params", [])}
        master = str(i.get("master", ""))
        pol = ("p" if master.startswith("pch") else
               "n" if master.startswith("nch") else "")
        out.append({"name": i["name"], "master": master, "nets": nets,
                    "params": params, "polarity": pol})
    return sub.get("name"), ports, out


def classify(insts, ports):
    mos = [i for i in insts if i["polarity"] in ("p", "n")]
    ports_set = set(ports)
    rails = {}
    for pol in ("p", "n"):
        ties = defaultdict(int)
        for i in mos:
            if i["polarity"] == pol and len(i["nets"]) >= 4:
                ties[i["nets"][3]] += 1
        if ties:
            rails[pol] = max(ties, key=ties.get)
    src_groups = defaultdict(list)
    for i in mos:
        if i["polarity"] == "n" and len(i["nets"]) >= 3:
            src_groups[i["nets"][2]].append(i["name"])
    pair_src = None
    for net, names in src_groups.items():
        if net != rails.get("n") and len(names) == 2:
            pair_src = net
    pair = set(src_groups.get(pair_src, [])) if pair_src else set()
    roles = {}
    for i in insts:
        pol, nets, name = i["polarity"], i["nets"], i["name"]
        if pol == "":
            roles[name] = "passive"
        elif name in pair:
            roles[name] = "diff-pair"
        elif pol == "n" and len(nets) >= 3 and nets[0] == pair_src:
            roles[name] = "tail"
        elif pol == "p" and len(nets) >= 2 and nets[0] == nets[1]:
            roles[name] = "diode-load"
        elif pol == "p" and len(nets) >= 2 and any(
                o["name"] != name and o["polarity"] == "p"
                and len(o["nets"]) >= 2 and o["nets"][0] == o["nets"][1]
                and o["nets"][0] == nets[1] for o in insts):
            roles[name] = "mirror-load"
        elif pol == "n" and len(nets) >= 1 and nets[0] in ports_set:
            roles[name] = "out-pull"
        elif pol == "p" and len(nets) >= 1 and nets[0] in ports_set:
            roles[name] = "out-push"
        else:
            roles[name] = "nch-other" if pol == "n" else "pch-other"
    return roles, rails, pair_src


def row_rank(roles, i):
    r = roles[i["name"]]
    if r in ("diff-pair", "tail"):
        return 0
    if r in ("out-push", "out-pull"):
        return 2
    return 1


def assign_columns(insts, roles):
    tops = sorted([i for i in insts if i["polarity"] == "p"],
                  key=lambda i: row_rank(roles, i))
    bots = sorted([i for i in insts if i["polarity"] == "n"],
                  key=lambda i: row_rank(roles, i))
    pas = [i for i in insts if i["polarity"] == ""]
    cols = []          # dict(top,bot,pas)
    used_b, used_p = set(), set()
    for t in tops:
        mate = None
        for b in bots:
            if b["name"] not in used_b and b["nets"][0] == t["nets"][0]:
                mate = b
                break
        cols.append({"top": t, "bot": mate, "pas": None})
        if mate:
            used_b.add(mate["name"])
    for b in bots:
        if b["name"] not in used_b:
            cols.append({"top": None, "bot": b, "pas": None})
            used_b.add(b["name"])
    for p in pas:
        cols.append({"top": None, "bot": None, "pas": p})
    # column order: signal flow — diff-pair/tail first, output stage last
    def col_rank(col):
        ranks = []
        for key in ("top", "bot", "pas"):
            if col.get(key):
                ranks.append(row_rank(roles, col[key]))
        return min(ranks) if ranks else 9
    return sorted(cols, key=col_rank)


def render_svg(sub_name, ports, insts, roles, rails, cols):
    W = MARGIN + len(cols) * COL_W + 60
    els = []
    els.append(f'<svg viewBox="0 0 {W} {H_CANVAS}" '
               'xmlns="http://www.w3.org/2000/svg" role="img">')

    def xc(k):
        return MARGIN + k * COL_W + COL_W / 2

    # rails
    for y, name in ((Y_RAIL_P, rails.get("p")), (Y_RAIL_N, rails.get("n"))):
        if not name:
            continue
        els.append(f'<line x1="{MARGIN-40}" y1="{y}" x2="{W-40}" y2="{y}" '
                   f'stroke="{RAIL}" stroke-width="2"/>')
        els.append(f'<text x="{MARGIN-40}" y="{y-8}" font-size="11" fill="{MUTED}" '
                   f'font-family="monospace">{name}</text>')

    # port legend
    els.append(f'<text x="10" y="20" font-size="12" font-weight="700" fill="{INK}" '
               f'font-family="monospace">{sub_name}</text>')
    for k, p in enumerate(ports):
        els.append(f'<text x="10" y="{36+k*13}" font-size="9.5" fill="{MUTED}" '
                   f'font-family="monospace">● {p}</text>')

    def box(cx, y, i, stroke, fill):
        x = cx - BOX_W / 2
        els.append(f'<rect x="{x:.0f}" y="{y}" width="{BOX_W}" height="{BOX_H}" '
                   f'fill="{fill}" stroke="{stroke}" stroke-width="1.6" rx="3"/>')
        els.append(f'<text x="{cx}" y="{y+20}" font-size="11.5" font-weight="600" '
                   f'text-anchor="middle" fill="{INK}" font-family="monospace">'
                   f'{i["name"]}</text>')
        els.append(f'<text x="{cx}" y="{y+34}" font-size="8.5" text-anchor="middle" '
                   f'fill="{MUTED}" font-family="monospace">'
                   f'{roles[i["name"]]}</text>')
        size = " ".join(f'{k}={i["params"][k]}' for k in ("l", "w", "nf")
                        if k in i["params"])
        els.append(f'<text x="{cx}" y="{y+44+10}" font-size="8.5" text-anchor="middle" '
                   f'fill="{MUTED}" font-family="monospace">{size}</text>')

    def term(cx, y, side):
        """side: D -> up stub, S -> down stub, G -> left stub. returns stub end"""
        if side == "D":
            els.append(f'<line x1="{cx}" y1="{y}" x2="{cx}" y2="{y-16}" '
                       f'stroke="{INK}" stroke-width="1.2"/>')
            return cx, y - 16
        if side == "S":
            els.append(f'<line x1="{cx}" y1="{y+BOX_H}" x2="{cx}" y2="{y+BOX_H+16}" '
                       f'stroke="{INK}" stroke-width="1.2"/>')
            return cx, y + BOX_H + 16
        els.append(f'<line x1="{cx-BOX_W/2}" y1="{y+BOX_H/2}" '
                   f'x2="{cx-BOX_W/2-16}" y2="{y+BOX_H/2}" '
                   f'stroke="{INK}" stroke-width="1.2"/>')
        return cx - BOX_W / 2 - 16, y + BOX_H / 2

    def label(x, y, text, anchor="start", dy=0):
        els.append(f'<text x="{x:.0f}" y="{y+dy:.0f}" font-size="9" '
                   f'fill="{INK}" text-anchor="{anchor}" font-family="monospace">'
                   f'{text}</text>')

    # devices
    placed = {}   # name -> (cx, y)
    for k, col in enumerate(cols):
        cx = xc(k)
        for key, y in (("top", Y_TOP), ("bot", Y_BOT), ("pas", Y_MID)):
            i = col.get(key)
            if not i:
                continue
            stroke, fill = (P_STROKE, P_FILL) if i["polarity"] == "p" else \
                           (N_STROKE, N_FILL) if i["polarity"] == "n" else \
                           (X_STROKE, X_FILL)
            box(cx, y, i, stroke, fill)
            placed[i["name"]] = (cx, y)
            # terminals + labels
            nets = i["nets"]
            for side, idx, tlabel in (("D", 0, "D"), ("G", 1, "G"), ("S", 2, "S")):
                if len(nets) <= idx:
                    continue
                net = nets[idx]
                if net in rails.values():
                    ry = Y_RAIL_P if net == rails.get("p") else Y_RAIL_N
                    els.append(f'<line x1="{cx}" y1="{ry}" x2="{cx}" '
                               f'y2="{y if side=="D" else y+BOX_H if side=="S" else y+BOX_H/2}" '
                               f'stroke="{INK}" stroke-width="1.2"/>')
                    continue
                ex, ey = term(cx, y, side)
                if side == "D":
                    label(ex + 3, ey - 2, net)
                elif side == "S":
                    label(ex + 3, ey + 4, net)
                else:
                    label(ex - 4, ey + 4, net, anchor="end")

    # same-column vertical ties (top.D net == bottom.D net)
    for k, col in enumerate(cols):
        t, b = col.get("top"), col.get("bot")
        if t and b and t["nets"][0] == b["nets"][0]:
            cx = xc(k)
            els.append(f'<line x1="{cx}" y1="{Y_TOP-16}" x2="{cx}" '
                       f'y2="{Y_BOT+BOX_H+16}" stroke="{INK}" stroke-width="1.2"/>')
            label(cx + 3, Y_TOP - 20, t["nets"][0])
    # same-row horizontal ties (adjacent S terminals on shared net)
    for k in range(len(cols) - 1):
        b1, b2 = cols[k].get("bot"), cols[k + 1].get("bot")
        if b1 and b2 and len(b1["nets"]) > 2 and b1["nets"][2] == b2["nets"][2]:
            net = b1["nets"][2]
            if net in rails.values():
                continue
            x1, x2 = xc(k), xc(k + 1)
            y = Y_BOT + BOX_H + 16
            els.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" '
                       f'stroke="{INK}" stroke-width="1.2"/>')
            label((x1 + x2) / 2, y - 4, net, anchor="middle")

    els.append("</svg>")
    return "\n".join(els), W


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("--ast")
    args = ap.parse_args()
    net_path = Path(args.netlist)
    ast = load_ast(net_path, args.ast)
    sub_name, ports, insts = get_instances(ast)
    roles, rails, pair_src = classify(insts, ports)
    cols = assign_columns(insts, roles)
    svg, width = render_svg(sub_name, ports, insts, roles, rails, cols)
    out = net_path.with_suffix(".preview.html")
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>{sub_name} 原理图预览</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{margin:24px;background:#f5f4f1;font-family:sans-serif}}
.card{{background:#fff;border:1px solid #e2e0d9;border-radius:6px;padding:16px;
max-width:{width + 80}px;overflow-x:auto}}
h1{{font-size:15px;color:#191817;margin:0 0 4px}}
p{{font-size:12px;color:#6f6d67;margin:0 0 12px}}
svg{{max-width:100%;height:auto;display:block}}</style></head>
<body><div class="card"><h1>subckt {sub_name} — 原理图预览（自动重建草案）</h1>
<p>PMOS 上排（蓝）· NMOS 下排（橙）· 无源中间（绿）；同名标注 = 同一网络；实线 = 直接连接。</p>
{svg}</div></body></html>"""
    out.write_text(html)
    print(f"# subckt {sub_name}  ({len(insts)} instances, ports: {', '.join(ports)})")
    print()
    for i in insts:
        p = i["params"]
        size = " ".join(f"{k}={p[k]}" for k in ("l", "w", "nf") if k in p)
        print(f"  {i['name']:6s} {i['master']:12s} {roles[i['name']]:14s} {size}")
    print()
    print(f"preview written: {out}")


if __name__ == "__main__":
    main()
