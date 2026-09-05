#!/usr/bin/env python3
"""afe_bias netlist -> schematic pilot (workflow: references/netlist-to-schematic.md).

build : create lib afe_sch + schematic afe_bias (19 inst: 2 MOS + 1 res + 16 cap)
        + CDF params (Stage 2, readback-verified) + schCheck/dbSave
verify: Gate A (schCheck + screenshot), Gate B (schematic.read vs source parse),
        Gate C (export_netlist semantic compare vs tran/afe_bias.scs)

Run from a neutral cwd (e.g. /tmp) so the user-level bridge .env (local mode)
is picked up, NOT afe/.env (server-21 remote config):
  cd /tmp && /home/gmei/pi_project/.venv/bin/python <this> build|verify
"""
import re
import sys
from pathlib import Path

AFE = Path("/home/gmei/git/oephy/afe")
SRC = AFE / "tran" / "afe_bias.scs"
OUTDIR = AFE / "output" / "n2s_afe_bias"

LIB, CELL, PDK = "afe_sch", "afe_bias", "tsmcN12"
LIB_PATH = str(AFE / "virtuoso_ws" / LIB)
GRID = 1.5

from virtuoso_bridge import VirtuosoClient  # noqa: E402
from virtuoso_bridge.virtuoso.schematic import (  # noqa: E402
    schematic_create_inst_by_master_name as inst,
    schematic_create_pin as pin,
    schematic_label_instance_term as label_term,
)
from virtuoso_bridge.virtuoso.schematic.params import _run_batched_param_update  # noqa: E402

# ---------------------------------------------------------------- Stage 1: source parse
def parse_source():
    """Parse tran/afe_bias.scs -> ports, subparams, devices{name:(master,nets,req_params)}."""
    subparams = {}
    devices, ports = {}, None
    body = False
    for line in SRC.read_text().splitlines():
        line = line.split("//")[0].strip()
        if not line:
            continue
        m = re.match(r"subckt\s+\S+\s*\(([^)]*)\)", line)
        if m:
            ports = m.group(1).split()
            body = True
            continue
        if line.startswith("parameters"):
            for k, v in re.findall(r"(\w+)=(\S+)", line):
                subparams[k] = v
            continue
        if line.startswith("ends"):
            break
        if not body:
            continue
        m = re.match(r"(\S+)\s*\(([^)]*)\)\s+(\S+)(.*)", line)
        if not m:
            sys.exit(f"[parse] unhandled line: {line!r}")
        name, nodes, master, rest = m.groups()
        params = dict(re.findall(r"(\w+)=(\S+)", rest))
        for k in list(params):  # expand subckt parameters verbatim
            if params[k] in subparams:
                params[k] = subparams[params[k]]
        devices[name] = {"master": master, "nodes": nodes.split(), "params": params}
    return ports, subparams, devices


# ---------------------------------------------------------------- Stage 3/4: placement + labels
PLACE = [
    ("Mba", "nch_lvt_mac", 1, 0, "R0"),
    ("Mbb", "nch_lvt_mac", 2, 0, "R0"),
    ("Rb", "rhim", 1, 2, "R0"),
] + [("Cdec%d" % (i + 1), "cfmom_2t_p80", 3 + i % 4, i // 4, "R0") for i in range(16)]

# pin creation order == subckt port order (si emits header in creation order)
PINS = [("vbias", 0, "output"), ("vdd", 2, "input"), ("vss", -1, "input")]


def build(client):
    if LIB not in client.library.list():
        Path(LIB_PATH).parent.mkdir(parents=True, exist_ok=True)
        client.library.create(LIB, LIB_PATH)
        print(f"[lib] created {LIB} at {LIB_PATH}")
    else:
        print(f"[lib] reuse existing {LIB}")
    r = client.execute_skill(f'ddGetObj("{LIB}" "{CELL}")!=nil')
    if (r.output or "").strip().strip('"') in ("t", "True"):
        sys.exit(f"[abort] {LIB}/{CELL} already exists (rule: never overwrite)")

    with client.schematic.create(LIB, CELL) as sch:
        for name, master, col, row, orient in PLACE:
            sch.add(inst(PDK, master, "symbol", name, col * GRID, row * GRID, orient))
        for m in ("Mba", "Mbb"):  # diode-connected: D=G=vbias, S=B=vss
            sch.add_net_label_to_transistor(
                m, drain_net="vbias", gate_net="vbias", source_net="vss", body_net="vss")
        sch.add(label_term("Rb", "PLUS", "vdd"))    # terms verified: MINUS/PLUS
        sch.add(label_term("Rb", "MINUS", "vbias"))
        for i in range(16):
            n = "Cdec%d" % (i + 1)                 # terms verified: PLUS/MINUS
            sch.add(label_term(n, "PLUS", "vbias"))
            sch.add(label_term(n, "MINUS", "vss"))
        for pname, prow, pdir in PINS:
            sch.add(pin(pname, -1 * GRID, prow * GRID, "R0", direction=pdir))
    print(f"[build] placed {len(PLACE)} instances, {len(PINS)} pins")

    # Stage 2: params. Settled empirically during the pilot (three traps):
    #  - netlist name vs CDF name: the netlist's nfin is DERIVED; the editable
    #    master param is nFin -> callbacks recompute nfin=16 (and w) consistently
    #  - w is also derived from nFin (a raw w=464n write gets reverted by callbacks)
    #  - set_instance_params resolves its target from geGetEditCellView, which
    #    drifts in a shared GUI session -> call the explicit-cv batched updater
    client.open_window(LIB, CELL, view="schematic")  # for the user to watch
    for m in ("Mba", "Mbb"):
        _run_batched_param_update(client, LIB, CELL, m, {"l": "16n", "nFin": "16"})
        # si emits CDF-computed sa/sb=90n (LOD stress) which the validated
        # hand netlist omits -> +10.9 mV on vbias (golden probe, bisected to
        # sa/sb alone; sd/ploda/spot无辜, large values saturate at +5.2mV).
        # sa=0/sb=0 is the model's no-LOD sentinel == omitted, bit-identical.
        client.execute_skill(
            f'dbReplaceProp(car(setof(x dbOpenCellViewByType("{LIB}" "{CELL}" '
            f'"schematic" "" "a")~>instances x~>name=="{m}")) "sa" "string" "0")')
        client.execute_skill(
            f'dbReplaceProp(car(setof(x dbOpenCellViewByType("{LIB}" "{CELL}" '
            f'"schematic" "" "a")~>instances x~>name=="{m}")) "sb" "string" "0")')
    _run_batched_param_update(client, LIB, CELL, "Rb", {"l": "2.35u", "w": "0.36u"})

    # readback assert: the si netlister emits STORED props verbatim (no
    # recompute at netlist time), so what the CDF machinery stored is what
    # Gate C will compare against the source netlist
    raw = client.schematic.read(LIB, CELL, param_filters=None)
    for n in ("Mba", "Mbb", "Rb"):
        p = next(i["params"] for i in raw["instances"] if i["name"] == n)
        print(f"[params-readback] {n}: "
              + " ".join(f"{k}={p.get(k)}" for k in ("l", "w", "nfin")))
        if n.startswith("Mb") and canon(str(p.get("nfin"))) != canon("16"):
            sys.exit(f"[abort] {n}: nfin={p.get('nfin')} != 16 after set")
    print("[save] schCheck+dbSave ->", save_il(client))


def save_il(client):
    """schCheck + dbSave via explicit cellview; returns the schCheck result
    ('(0 0)' = 0 errors / 0 warnings). execute_skill returns the last form;
    load_il does not surface it."""
    r = client.execute_skill(
        f'prog1( schCheck(dbOpenCellViewByType("{LIB}" "{CELL}" "schematic" "" "a")) '
        f'dbSave(dbOpenCellViewByType("{LIB}" "{CELL}" "schematic" "" "a")) )')
    return (r.output or "").strip().strip('"')


# ---------------------------------------------------------------- compare helpers
SUFX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "x": 1e6}


def canon(v):
    v = v.strip().strip('"').lower()
    m = re.fullmatch(r"([-0-9.e+]+)([fpnumkx]?)", v)
    if m:
        try:
            return round(float(m.group(1)) * SUFX.get(m.group(2), 1.0), 12)
        except ValueError:
            pass
    return v


# terminal name order used by the si netlister for instance lines (alphabetical),
# used to map exported positional nets -> terminal names per master
SOURCE_TERM_ORDER = {  # netlist positional order per model (spectre model def)
    "nch_lvt_mac": ["d", "g", "s", "b"],
    "rhim": ["plus", "minus"],
    "cfmom_2t_p80": ["plus", "minus"],
}


def verify(client):
    ports, subparams, src = parse_source()
    ok = True

    # -- Gate A: schCheck + window screenshot
    res = save_il(client)
    print(f"[gateA] schCheck -> {res}")
    nums = [int(x) for x in re.findall(r"-?\d+", res)[:2]]
    if nums and nums != [0, 0]:
        print(f"[gateA] FAIL schCheck not clean: {res}")
        ok = False
    client.open_window(LIB, CELL, view="schematic")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    client.screenshot(output=str(OUTDIR), target="current")
    client.screenshot(output=str(OUTDIR), target="ciw")
    print(f"[gateA] screenshots -> {OUTDIR}")

    # -- Gate B: readback vs source
    data = client.schematic.read(LIB, CELL)
    rb = {i["name"]: i for i in data["instances"]}
    names_ok = set(rb) == set(src)
    if not names_ok:
        print(f"[gateB] FAIL instance names: sch={sorted(rb)} src={sorted(src)}")
        ok = False
    for name, sd in src.items():
        if name not in rb:
            continue
        ri = rb[name]
        if ri["cell"] != sd["master"]:
            print(f"[gateB] FAIL {name}: master {ri['cell']} != {sd['master']}")
            ok = False
        rb_nets = {t.lower(): n.lower().split("/")[-1] for t, n in (ri.get("terms") or {}).items()}
        src_nets = dict(zip(SOURCE_TERM_ORDER[sd["master"]], map(str.lower, sd["nodes"])))
        for term, net in src_nets.items():
            if rb_nets.get(term) != net:
                print(f"[gateB] FAIL {name}.{term}: {rb_nets.get(term)} != {net}")
                ok = False
    rb_pins = list(data.get("pins", {}))
    if set(rb_pins) != set(ports):
        print(f"[gateB] FAIL pins: {rb_pins} != {ports}")
        ok = False
    print(f"[gateB] {'PASS' if ok else 'FAIL'} ({len(rb)} inst, pins {rb_pins})")

    # raw param readback print (Stage 2 evidence)
    raw = client.schematic.read(LIB, CELL, param_filters=None)
    for n in ("Mba", "Rb"):
        p = next((i["params"] for i in raw["instances"] if i["name"] == n), {})
        keep = {k: v for k, v in p.items() if k in ("l", "w", "nfin", "nf", "fingers", "simM", "m")}
        print(f"[params-readback] {n}: {keep}")

    # -- Gate C: export netlist semantic compare
    exp = client.schematic.export_netlist(LIB, CELL, str(OUTDIR / "netlist"),
                                          simulator="spectre")
    exp_dir = exp["output_dir"] if isinstance(exp, dict) else getattr(
        exp, "output_dir", str(exp))
    scs = Path(exp_dir) / "input.scs"
    text = re.sub(r"\\\s*\n\s*", " ", scs.read_text())  # join "\" continuations
    m = re.search(r"subckt\s+afe_bias\s*\(([^)]*)\)(.*?)ends", text, re.S)
    if m:
        exp_ports, body = m.group(1).split(), m.group(2)
        if exp_ports != ports:
            print(f"[gateC] NOTE port order {exp_ports} vs source {ports} "
                  f"(set-eq={set(exp_ports) == set(ports)})")
    else:
        # si netlisted the cell FLAT (top level, no subckt wrapper);
        # pins were already verified in Gate B.
        body = text
        print("[gateC] NOTE flat top-level export (no subckt wrapper)")
    exp_dev = {}
    for line in body.splitlines():
        line = line.split("//")[0].strip()
        mm = re.match(r"(\S+)\s*\(([^)]*)\)\s+(\S+)(.*)", line)
        if mm:
            exp_dev[mm.group(1)] = {"master": mm.group(3),
                                    "nodes": mm.group(2).split(),
                                    "params": dict(re.findall(r"(\w+)=(\S+)", mm.group(4)))}
    if set(exp_dev) != set(src):
        print(f"[gateC] FAIL device set: exp-only={set(exp_dev)-set(src)} "
              f"src-only={set(src)-set(exp_dev)}")
        ok = False
    for name, sd in src.items():
        if name not in exp_dev:
            continue
        ed = exp_dev[name]
        if ed["master"].lower() != sd["master"].lower():
            print(f"[gateC] FAIL {name}: master {ed['master']} != {sd['master']}")
            ok = False
            continue
        # Positional node-tuple comparison: spectre binds nodes to model
        # terminals by position and both netlists reference the same model,
        # so identical ordered tuples == identical connectivity. Order-
        # sensitive, hence catches the +/- terminal-swap class of bugs.
        if [n.lower() for n in ed["nodes"]] != [n.lower() for n in sd["nodes"]]:
            print(f"[gateC] FAIL {name}: nodes {ed['nodes']} != {sd['nodes']}")
            ok = False
        for k, v in sd["params"].items():
            ev = next((ed["params"][kk] for kk in (k, k.lower(), k.upper())
                       if kk in ed["params"]), None)
            if ev is None or canon(ev) != canon(v):
                print(f"[gateC] FAIL {name}: param {k}={ev} != {v}")
                ok = False
    extras = {n: len(ed["params"]) for n, ed in exp_dev.items()}
    print(f"[gateC] {'PASS' if ok else 'FAIL'} ({len(exp_dev)} devices, "
          f"extra CDF-default params per inst: {extras})")
    print(f"[gateC] exported netlist: {scs}")
    print(f"\n=== afe_bias pilot: {'ALL GATES PASS' if ok else 'FAILURES PRESENT'} ===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    client = VirtuosoClient.from_env()
    {"build": lambda: build(client), "verify": lambda: verify(client)}[cmd]()
