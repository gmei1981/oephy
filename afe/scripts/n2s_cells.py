#!/usr/bin/env python3
"""Batch netlist -> schematic reconstruction for the remaining afe subckts.

Same mechanism as the proven pilot (n2s_afe_bias.py, all gates + golden
probe green); generalizations:
  - MOS masters all take CDF nFin (netlist nfin is derived) + raw sa=0/sb=0
    after the callback update (LOD-stress sentinel == omitted, see skill doc)
  - spectre built-ins map to analogLib: capacitor->cap (c), resistor->res (r)
  - source netlists may wrap parameter lines with "\" continuations

Run from a neutral cwd (/tmp) so the user-level bridge .env (local mode) is
used, NOT afe/.env (server-21 remote config):
  cd /tmp && /home/gmei/pi_project/.venv/bin/python <this> all [cell ...]
"""
import re
import sys
from pathlib import Path

from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.schematic import (
    schematic_create_inst_by_master_name as inst,
    schematic_create_pin as pin,
    schematic_label_instance_term as label_term,
)
from virtuoso_bridge.virtuoso.schematic.params import _run_batched_param_update

AFE = Path("/home/gmei/git/oephy/afe")
LIB, PDK, GRID = "afe_sch", "tsmcN12", 1.5

SRC_FILES = {
    "afe_pad_esd": "tran/afe_esd.scs",
    "afe_tx_drv": "tran/afe_tx_drv.scs",
    "afecmp_bank": "tran/afecmp_bank.scs",
    "afe_dac_r2r": "tran/afe_dac_r2r.scs",
    "afe_strongarm": "tran/afe_sampler.scs",
    "afe_dlatch": "tran/afe_sampler.scs",
}
ORDER = ["afe_pad_esd", "afe_tx_drv", "afe_strongarm", "afe_dlatch",
         "afecmp_bank", "afe_dac_r2r"]

MOS = {"nch_lvt_mac", "pch_svt_mac", "nch_svt_mac",
       "pch_ulvt_mac", "nch_ulvt_mac"}
DIODE = {"pdio_hia18_mac", "ndio_hia18_mac"}
BUILTIN = {"capacitor": ("analogLib", "cap", "c"),
           "resistor": ("analogLib", "res", "r")}
# pins that drive a net (all others default to "input")
OUT_PORTS = {"afecmp_bank": {"outp", "outn"},
             "afe_dac_r2r": {"vref"},
             "afe_strongarm": {"qp", "qn"},
             "afe_dlatch": {"q"},
             "afe_pad_esd": {"pad"},
             "afe_tx_drv": {"pad"}}

# ---------------------------------------------------------------- parsing
def parse_all(rel):
    """Parse every subckt in a source file -> {cell: {ports, devices}}."""
    text = re.sub(r"\\\s*\n\s*", " ", (AFE / rel).read_text())  # join continuations
    out, cur = {}, None
    for line in text.splitlines():
        line = line.split("//")[0].strip()
        if not line:
            continue
        m = re.match(r"subckt\s+(\S+)\s*\(([^)]*)\)", line)
        if m:
            cur = {"ports": m.group(2).split(), "subparams": {}, "devices": {}}
            out[m.group(1)] = cur
            continue
        if cur is None:
            continue
        if line.startswith("parameters"):
            for k, v in re.findall(r"(\w+)=(\S+)", line):
                cur["subparams"][k] = v
            continue
        if line.startswith("ends"):
            cur = None
            continue
        m = re.match(r"(\S+)\s*\(([^)]*)\)\s+(\S+)(.*)", line)
        if m:
            name, nodes, master, rest = m.groups()
            params = dict(re.findall(r"(\w+)=(\S+)", rest))
            for k in list(params):  # expand subckt parameters verbatim
                if params[k] in cur["subparams"]:
                    params[k] = cur["subparams"][params[k]]
            cur["devices"][name] = {"master": master, "nodes": nodes.split(),
                                    "params": params}
    return out


def master_of(m):
    if m in BUILTIN:
        al, cell, _ = BUILTIN[m]
        return al, cell
    return PDK, m


def cdf_params_and_assert(dev):
    """netlist params -> (CDF params to write, readback assert (key, value))."""
    m, p = dev["master"], dev["params"]
    if m in MOS:
        return {"l": p["l"], "nFin": p["nfin"]}, ("nfin", p["nfin"])
    if m == "rhim":
        return {"l": p["l"], "w": p["w"]}, ("l", p["l"])
    if m in DIODE:
        # callbacks derive BOTH nf and nfin (batched writes revert). The model
        # takes nf as the finger count; omitted-nfin default == CDF default 12
        # (IV-bisected 2026-09-04: nfin=12 bit-identical to source, nfin=50
        # conducts 4.4x, w/l/multi neutral). Raw-write nf only, leave nfin.
        return {}, ("nf", p["nf"])
    if m in BUILTIN:
        _, _, key = BUILTIN[m]
        return {key: p[key]}, (key, p[key])
    raise ValueError(f"unknown master {m}")


# ---------------------------------------------------------------- placement
def plan(s, cell):
    if cell == "afe_pad_esd":
        return [("Xpd", 1, 1), ("Xnd", 2, 1)]
    if cell == "afe_tx_drv":
        p = [("Mp1", 1, 3), ("Mn1", 1, 0),
             ("Mp2a", 2, 3), ("Mp2b", 2, 4), ("Mp2c", 2, 5),
             ("Mn2a", 2, 0), ("Mn2b", 2, 1),
             ("Mp3a", 3, 3), ("Mp3b", 3, 4), ("Mp3c", 3, 5), ("Mp3d", 3, 6),
             ("Mn3a", 3, 0), ("Mn3b", 3, 1), ("Mn3c", 3, 2)]
        p += [(f"Mpu{i:02d}", 4 + i - 1, 7) for i in range(1, 9)]
        p += [(f"Mpu{i:02d}", 4 + i - 9, 8) for i in range(9, 17)]
        p += [(f"Mpd{i}", 4 + i - 1, -1) for i in range(1, 7)]
        return p
    if cell == "afecmp_bank":
        return [("C1", 0, 4), ("C2", 0, 5),
                ("RbpA", 0, 3), ("Rbgp", 0, 6), ("Rbgn", 0, 7),
                ("Msw", 1, 4), ("MazA", 1, 5), ("MazGp", 1, 6), ("MazGn", 1, 7),
                ("MNp", 2, 4), ("MNn", 3, 4), ("MLp", 2, 7), ("MLn", 3, 7),
                ("Mtail", 2, 0),
                ("MN2p", 5, 4), ("MN2n", 6, 4), ("ML2p", 5, 7), ("ML2n", 6, 7),
                ("Mtail2", 5, 0), ("Msh", 7, 4)]
    if cell == "afe_strongarm":
        return [("Mtail", 0, 0), ("Mtsr", 1, 0), ("MNip", 1, 2), ("MNin", 2, 2),
                ("MNxp", 1, 4), ("MNxn", 2, 4), ("MPxp", 1, 5), ("MPxn", 2, 5),
                ("MPprp", 1, 6), ("MPprn", 2, 6)]
    if cell == "afe_dlatch":
        return [("Mtgn", 0, 1), ("Mtgp", 0, 2), ("Mh1p", 1, 2), ("Mh1n", 1, 0),
                ("Mh2p", 2, 2), ("Mh2n", 2, 0)]
    if cell == "afe_dac_r2r":
        p = []
        for k in range(8):
            p += [(f"Minv{k}", k, 9), (f"Mdnv{k}", k, 10)]
        for k in range(7):
            p.append((f"Rs{k}", k, 5))
        for k in range(8):
            c = 2 * k
            p.append((f"Rarm{k}", k, 4))
            p += [(f"Mup{k}pa", c, 3), (f"Mup{k}pb", c + 1, 3),
                  (f"Mup{k}na", c, 2), (f"Mup{k}nb", c + 1, 2),
                  (f"Mdn{k}na", c, 1), (f"Mdn{k}nb", c + 1, 1),
                  (f"Mdn{k}pa", c, 0), (f"Mdn{k}pb", c + 1, 0)]
        p.append(("Rterm", 8, 5))
        return p
    raise ValueError(cell)


# ---------------------------------------------------------------- helpers
SUFX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
        "k": 1e3, "x": 1e6, "g": 1e9, "t": 1e12}


def canon(v):
    v = str(v).strip().strip('"').lower()
    m = re.fullmatch(r"([-0-9.e+]+)([fpnumkxgt]?)", v)
    if m:
        try:
            return round(float(m.group(1)) * SUFX.get(m.group(2), 1.0), 12)
        except ValueError:
            pass
    return v


def save_cv(client, cell):
    r = client.execute_skill(
        f'prog1( schCheck(dbOpenCellViewByType("{LIB}" "{cell}" "schematic" "" "a")) '
        f'dbSave(dbOpenCellViewByType("{LIB}" "{cell}" "schematic" "" "a")) )')
    return (r.output or "").strip().strip('"')


# ---------------------------------------------------------------- build
def build_cell(client, cell):
    src = parse_all(SRC_FILES[cell])[cell]
    r = client.execute_skill(f'ddGetObj("{LIB}" "{cell}")!=nil')
    if (r.output or "").strip().strip('"') in ("t", "True"):
        sys.exit(f"[abort] {LIB}/{cell} already exists (rule: never overwrite)")

    devices, ports = src["devices"], src["ports"]
    p = plan(src, cell)
    assert set(x[0] for x in p) == set(devices), \
        f"{cell}: plan covers {len(p)} != {len(devices)} devices"

    # SKILL literal-stack limit: one giant batch overflows on large cells
    # (dac: 96 inst -> "Literal stack overflow"). Chunk the placement;
    # create() for the first chunk, modify() appends the rest. Pins go in
    # the LAST chunk (creation order == subckt port emission order).
    CHUNK = 24
    chunks = [p[i:i + CHUNK] for i in range(0, len(p), CHUNK)]
    for ci, chunk in enumerate(chunks):
        editor = client.schematic.create if ci == 0 else client.schematic.modify
        with editor(LIB, cell) as sch:
            for name, col, row in chunk:
                d = devices[name]
                lib2, master = master_of(d["master"])
                sch.add(inst(lib2, master, "symbol", name, col * GRID, row * GRID, "R0"))
                if d["master"] in MOS:  # source positional order is d g s b
                    n = d["nodes"]
                    sch.add_net_label_to_transistor(
                        name, drain_net=n[0], gate_net=n[1], source_net=n[2], body_net=n[3])
                else:  # rhim / diodes / analogLib: PLUS MINUS
                    sch.add(label_term(name, "PLUS", d["nodes"][0]))
                    sch.add(label_term(name, "MINUS", d["nodes"][1]))
            if ci == len(chunks) - 1:
                outs = OUT_PORTS.get(cell, set())
                for i, pname in enumerate(ports):
                    direction = "output" if pname in outs else "input"
                    sch.add(pin(pname, -1 * GRID, i * GRID, "R0", direction=direction))
    print(f"[{cell}] placed {len(p)} instances, {len(ports)} pins "
          f"({len(chunks)} chunks)")

    # params: callback-correct CDF writes + LOD sentinel first, then ONE
    # readback covering all instances (a per-device read inside the loop would
    # see stale props for devices not yet updated)
    client.open_window(LIB, cell, view="schematic")
    for name, _, _ in p:
        d = devices[name]
        cdfp, _ = cdf_params_and_assert(d)
        if cdfp:
            _run_batched_param_update(client, LIB, cell, name, cdfp)
        # deliberate raw writes (bypass callbacks; netlister emits verbatim):
        raws = []
        if d["master"] in MOS:
            raws = [("sa", "0"), ("sb", "0")]  # no-LOD sentinel == omitted
        elif d["master"] in DIODE:
            # nf: callback path reverts it -> raw write. nfin: placement
            # default (8) is NOT neutral; the model's omitted-nfin default 12
            # is (IV-verified: 8 -> 0.643x current, 12 -> bit-identical).
            raws = list(d["params"].items()) + [("nfin", "12")]
        for prop, val in raws:
            client.execute_skill(
                f'dbReplaceProp(car(setof(x dbOpenCellViewByType("{LIB}" "{cell}" '
                f'"schematic" "" "a")~>instances x~>name=="{name}")) '
                f'"{prop}" "string" "{val}")')
    raw = client.schematic.read(LIB, cell, param_filters=None)
    for name, _, _ in p:
        d = devices[name]
        _, (akey, aval) = cdf_params_and_assert(d)
        got = next((i["params"] for i in raw["instances"] if i["name"] == name), None)
        if got is None or canon(got.get(akey, "?")) != canon(aval):
            sys.exit(f"[abort] {cell}/{name}: {akey}={got and got.get(akey)} != {aval}")
    print(f"[{cell}] params verified on all {len(p)} instances "
          f"(schCheck -> {save_cv(client, cell)})")


# ---------------------------------------------------------------- verify
def verify_cell(client, cell, ok_all):
    src = parse_all(SRC_FILES[cell])[cell]
    devices, ports = src["devices"], src["ports"]
    ok = True

    res = save_cv(client, cell)
    nums = [int(x) for x in re.findall(r"-?\d+", res)[:2]]
    if nums and nums != [0, 0]:
        print(f"[{cell} gateA] FAIL schCheck {res}")
        ok = False
    else:
        print(f"[{cell} gateA] schCheck {res}")

    data = client.schematic.read(LIB, cell)
    rb = {i["name"]: i for i in data["instances"]}
    if set(rb) != set(devices):
        print(f"[{cell} gateB] FAIL names sch={sorted(rb)} src={sorted(devices)}")
        ok = False
    for name, d in devices.items():
        if name not in rb:
            continue
        if rb[name]["cell"] != master_of(d["master"])[1]:
            print(f"[{cell} gateB] FAIL {name} master {rb[name]['cell']}")
            ok = False
    if set(data.get("pins", {})) != set(ports):
        print(f"[{cell} gateB] FAIL pins {sorted(data.get('pins', {}))}")
        ok = False
    if ok:
        print(f"[{cell} gateB] PASS ({len(rb)} inst, {len(ports)} pins)")

    outdir = AFE / "output" / f"n2s_{cell}"
    outdir.mkdir(parents=True, exist_ok=True)
    exp = client.schematic.export_netlist(LIB, cell, str(outdir / "netlist"),
                                          simulator="spectre")
    exp_dir = exp["output_dir"] if isinstance(exp, dict) else getattr(
        exp, "output_dir", str(exp))
    text = re.sub(r"\\\s*\n\s*", " ", (Path(exp_dir) / "input.scs").read_text())
    m = re.search(rf"subckt\s+{cell}\s*\(([^)]*)\)(.*?)ends", text, re.S)
    if m:
        body = m.group(2)
        if m.group(1).split() != ports:
            print(f"[{cell} gateC] NOTE port order {m.group(1).split()} != {ports}")
    else:
        body = text  # flat top-level export
    exp_dev = {}
    for line in body.splitlines():
        line = line.split("//")[0].strip()
        mm = re.match(r"(\S+)\s*\(([^)]*)\)\s+(\S+)(.*)", line)
        if mm:
            exp_dev[mm.group(1)] = {"master": mm.group(3),
                                    "nodes": mm.group(2).split(),
                                    "params": dict(re.findall(r"(\w+)=(\S+)", mm.group(4)))}
    if set(exp_dev) != set(devices):
        print(f"[{cell} gateC] FAIL device set: "
              f"exp-only={set(exp_dev)-set(devices)} src-only={set(devices)-set(exp_dev)}")
        ok = False
    for name, d in devices.items():
        if name not in exp_dev:
            continue
        ed = exp_dev[name]
        if ed["master"].lower() != d["master"].lower():
            print(f"[{cell} gateC] FAIL {name} master {ed['master']} != {d['master']}")
            ok = False
            continue
        if [n.lower() for n in ed["nodes"]] != [n.lower() for n in d["nodes"]]:
            print(f"[{cell} gateC] FAIL {name} nodes {ed['nodes']} != {d['nodes']}")
            ok = False
        _, (akey, aval) = cdf_params_and_assert(d)
        for k, v in d["params"].items():  # every source param must match
            ev = next((ed["params"][kk] for kk in (k, k.lower(), k.upper())
                       if kk in ed["params"]), None)
            if ev is None or canon(ev) != canon(v):
                print(f"[{cell} gateC] FAIL {name} {k}={ev} != {v}")
                ok = False
    print(f"[{cell} gateC] {'PASS' if ok else 'FAIL'} ({len(exp_dev)} devices)")
    return ok


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    cells = sys.argv[2:] or ORDER
    client = VirtuosoClient.from_env()
    if LIB not in client.library.list():
        (AFE / "virtuoso_ws").mkdir(parents=True, exist_ok=True)
        client.library.create(LIB, str(AFE / "virtuoso_ws" / LIB))
    ok_all = True
    for c in cells:
        if mode in ("build", "all"):
            build_cell(client, c)
        if mode in ("verify", "all"):
            ok_all &= verify_cell(client, c, True)
    print(f"\n=== n2s batch: {'ALL GATES PASS' if ok_all else 'FAILURES PRESENT'} ===")
    sys.exit(0 if ok_all else 1)
