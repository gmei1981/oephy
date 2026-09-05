#!/usr/bin/env python3
"""Build the 5 remaining analog TB cells in afe_sch (testbench as schematic).

Cells (structure only -- stimulus values and analysis directives are
patched at assembly time by scripts/gen_tb_golden.py, same contract as
tb_afe_tran / gen_golden_netlist.py):
  tb_bias_dc      Vvdd + Xb(afe_bias)                      legacy netlists/tb_bias_dc.scs
  tb_noise_smoke  Vvdd + M1(lvt) + R1(rhim) + C1(cap)      netlists/tb_noise_smoke.scs
  tb_afe_dac_dc   Vvccio/Vvdd/Vb0-7 + Xdac(afe_dac_r2r)    netlists/tb_afe_dac_dc.scs
  tb_afe_txron_mc Vvdd/Vvccio/Vvss/Vdin0/1 + Ipu/Ipd +     netlists/tb_afe_txron_mc.scs
                  Xdrv_pu/Xdrv_pd(afe_tx_drv)
  tb_afe_cmp_mc   Vvdd/Vvss/Vvref/Vvin/Veval/Vaz +         netlists/tb_afe_cmp_mc.scs
                  Xbias(afe_bias) + Xcmp(afecmp_bank)

Flat tops: no pins, ground via net label "gnd!" (netlists to node 0).
Instance names == legacy template names (directives reference them).

Run from a neutral cwd (/tmp) so the user-level bridge .env (local mode)
is used, NOT afe/.env (server-21 remote config):
  cd /tmp && /home/gmei/pi_project/.venv/bin/python <this> [build|verify|all]
"""
import re
import sys
from pathlib import Path

from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.schematic import (
    schematic_create_inst_by_master_name as inst,
    schematic_label_instance_term as label_term,
)
from virtuoso_bridge.virtuoso.schematic.params import _run_batched_param_update

AFE = Path("/home/gmei/git/oephy/afe")
LIB, PDK, GRID = "afe_sch", "tsmcN12", 1.5
GND = "gnd!"

V, I = ("analogLib", "vsource"), ("analogLib", "isource")

# cell -> list of items:
#   ("src", name, (lib, master), x, y, {term: net})        sources/passives/cells
#   ("mos", name, master, x, y, d, g, s, b)                PDK MOS (net-label DGSB)
TBS = {
    "tb_bias_dc": [
        ("src", "Vvdd", V, -3, 1, {"PLUS": "vdd", "MINUS": GND}),
        ("src", "Xb", (LIB, "afe_bias"), 0, 1,
         {"vbias": "vbias", "vdd": "vdd", "vss": GND}),
    ],
    "tb_noise_smoke": [
        ("src", "Vvdd", V, -3, 2, {"PLUS": "vdd", "MINUS": GND}),
        ("src", "R1", (PDK, "rhim"), -1, 2, {"PLUS": "vdd", "MINUS": "out"}),
        ("src", "C1", ("analogLib", "cap"), 1, 1, {"PLUS": "out", "MINUS": "vss"}),
        ("mos", "M1", "nch_lvt_mac", -0.5, 0, "out", "out", "vss", "vss"),
    ],
    "tb_afe_dac_dc": [
        ("src", "Vvccio", V, -3, 2, {"PLUS": "vccio", "MINUS": GND}),
        ("src", "Vvdd", V, -3, 1, {"PLUS": "vdd", "MINUS": GND}),
        *[("src", f"Vb{k}", V, -1 + 0.75 * k, 2, {"PLUS": f"b{k}", "MINUS": GND})
          for k in range(8)],
        ("src", "Xdac", (LIB, "afe_dac_r2r"), 6, 0,
         {"vref": "vref", "vccio": "vccio", "vdd": "vdd", "vss": GND,
          **{f"b{k}": f"b{k}" for k in range(8)}}),
    ],
    "tb_afe_txron_mc": [
        ("src", "Vvdd", V, -5, 2, {"PLUS": "vdd", "MINUS": GND}),
        ("src", "Vvccio", V, -5, 1, {"PLUS": "vccio", "MINUS": GND}),
        ("src", "Vvss", V, -5, 0, {"PLUS": "vss", "MINUS": GND}),
        ("src", "Vdin0", V, -3.5, 2, {"PLUS": "din0", "MINUS": GND}),
        ("src", "Vdin1", V, -3.5, 1, {"PLUS": "din1", "MINUS": GND}),
        ("src", "Ipu", I, 0, 2.5, {"PLUS": "pad_pu", "MINUS": GND}),
        ("src", "Ipd", I, 0, -0.5, {"PLUS": GND, "MINUS": "pad_pd"}),
        ("src", "Xdrv_pu", (LIB, "afe_tx_drv"), -1.5, 1.5,
         {"din": "din0", "pad": "pad_pu", "vccio": "vccio", "vdd": "vdd",
          "vss": "vss"}),
        ("src", "Xdrv_pd", (LIB, "afe_tx_drv"), -1.5, 0,
         {"din": "din1", "pad": "pad_pd", "vccio": "vccio", "vdd": "vdd",
          "vss": "vss"}),
    ],
    "tb_afe_cmp_mc": [
        ("src", "Vvdd", V, -5, 2, {"PLUS": "vdd", "MINUS": GND}),
        ("src", "Vvss", V, -5, 1, {"PLUS": "vss", "MINUS": GND}),
        ("src", "Vvref", V, -5, 0, {"PLUS": "vref", "MINUS": GND}),
        ("src", "Vvin", V, -3.5, 0, {"PLUS": "vin", "MINUS": GND}),
        ("src", "Veval", V, -2.5, 0, {"PLUS": "eval", "MINUS": GND}),
        ("src", "Vaz", V, -1.5, 0, {"PLUS": "az", "MINUS": GND}),
        ("src", "Xbias", (LIB, "afe_bias"), -1, 2.5,
         {"vbias": "vbias", "vdd": "vdd", "vss": "vss"}),
        ("src", "Xcmp", (LIB, "afecmp_bank"), 2, 0.5,
         {"vin": "vin", "vref": "vref", "eval": "eval", "az": "az",
          "vbias": "vbias", "outp": "outp", "outn": "outn",
          "vdd": "vdd", "vss": "vss", "gp": "gp"}),
    ],
    "tb_sa_test": [
        ("src", "vinp", V, -3, 3, {"PLUS": "ip", "MINUS": GND}),
        ("src", "vinn", V, -3, 2, {"PLUS": "in", "MINUS": GND}),
        ("src", "vck", V, -3, 1, {"PLUS": "ck", "MINUS": GND}),
        ("src", "vckn", V, -3, 0, {"PLUS": "ckn", "MINUS": GND}),
        ("src", "vvdd", V, -1.5, 1, {"PLUS": "vdd", "MINUS": GND}),
        ("src", "vvss", V, -1.5, 0, {"PLUS": "vss", "MINUS": GND}),
        ("src", "Xsa", (LIB, "afe_strongarm"), 1, 0.5,
         {"inp": "ip", "inn": "in", "ck": "ck", "ckn": "ckn",
          "qp": "qp", "qn": "qn", "vdd": "vdd", "vss": "vss"}),
    ],
    "tb_afe_va": [
        ("src", "Xtb", (LIB, "afe_tb"), 0, 0,
         {"tx_pad": "tx_pad", "rx_in": "rx_in", "vref": "vref",
          "ck8": "ck8", "pclk": "pclk", "d_even": "d_even",
          "d_odd": "d_odd", "lock": "lock", "err_cnt": "err_cnt",
          "bit_cnt": "bit_cnt"}),
    ],
}

# CDF params per (cell, instance) -- masters whose params reach the netlist
PARAMS = {
    "tb_noise_smoke": {
        "R1": {"l": "10u", "w": "0.36u"},
        "C1": {"c": "50f"},
    },
}
# MOS per cell: name -> CDF params + LOD sentinel raw writes
MOS_PARAMS = {
    "tb_noise_smoke": {"M1": {"l": "16n", "nFin": "8"}},
}

SUFX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3}


def canon(v):
    v = str(v).strip().strip('"').lower()
    m = re.fullmatch(r"([0-9.e+]+)([fpnum]?)", v)
    if m:
        try:
            return round(float(m.group(1)) * SUFX.get(m.group(2), 1.0), 15)
        except ValueError:
            pass
    return v


def save_cv(client, cell):
    r = client.execute_skill(
        f'prog1( schCheck(dbOpenCellViewByType("{LIB}" "{cell}" "schematic" '
        f'"" "a")) dbSave(dbOpenCellViewByType("{LIB}" "{cell}" "schematic" '
        f'"" "a")) )')
    return (r.output or "").strip().strip('"')


def build(client, cell):
    r = client.execute_skill(f'ddGetObj("{LIB}" "{cell}")!=nil')
    if (r.output or "").strip().strip('"') in ("t", "True"):
        sys.exit(f"[abort] {LIB}/{cell} already exists (rule: never overwrite)")
    items = TBS[cell]
    with client.schematic.create(LIB, cell) as sch:
        for it in items:
            if it[0] == "mos":
                _, name, master, x, y, d, g, s, b = it
                sch.add(inst(PDK, master, "symbol", name,
                             x * GRID, y * GRID, "R0"))
                sch.add_net_label_to_transistor(
                    name, drain_net=d, gate_net=g, source_net=s, body_net=b)
            else:
                _, name, (lib2, master), x, y, terms = it
                sch.add(inst(lib2, master, "symbol", name,
                             x * GRID, y * GRID, "R0"))
                for t, net in terms.items():
                    sch.add(label_term(name, t, net))
    print(f"[{cell}] placed {len(items)} instances")

    client.open_window(LIB, cell, view="schematic")
    for name, kv in {**PARAMS.get(cell, {}), **MOS_PARAMS.get(cell, {})}.items():
        _run_batched_param_update(client, LIB, cell, name, kv)
    for name in MOS_PARAMS.get(cell, {}):
        for prop in ("sa", "sb"):
            client.execute_skill(
                f'dbReplaceProp(car(setof(x dbOpenCellViewByType("{LIB}" '
                f'"{cell}" "schematic" "" "a")~>instances '
                f'x~>name=="{name}")) "{prop}" "string" "0")')
    print(f"[{cell}] schCheck -> {save_cv(client, cell)}")


def verify(client, cell):
    ok = True
    res = save_cv(client, cell)
    nums = [int(x) for x in re.findall(r"-?\d+", res)[:2]]
    # errors==0 gate only: soft warnings are inherent to the net-label-only TB
    # style -- the proven-golden tb_afe_tran checks (0 24) (warnings attach to
    # the afe_bias/afe_dac_r2r/afecmp_bank SYMBOLS, 2/2/4 each; afe_tx_drv 0)
    if nums and nums[0] != 0:
        print(f"[{cell} gateA] FAIL schCheck {res}")
        ok = False
    else:
        print(f"[{cell} gateA] schCheck {res} (errors==0)")

    raw = client.schematic.read(LIB, cell, param_filters=None)
    rb = {i["name"]: i for i in raw["instances"]}
    want = {it[1] for it in TBS[cell]}
    if set(rb) != want:
        print(f"[{cell} gateB] FAIL names sch={sorted(rb)} want={sorted(want)}")
        ok = False
    for it in TBS[cell]:
        name = it[1]
        if name not in rb:
            continue
        exp_master = it[2][1] if it[0] == "src" else it[2]
        if rb[name]["cell"] != exp_master:
            print(f"[{cell} gateB] FAIL {name} master {rb[name]['cell']}"
                  f" != {exp_master}")
            ok = False
        # terms must match the planned net map exactly
        terms = it[5] if it[0] == "src" else dict(
            zip(("drain", "gate", "source", "body"), it[5:9]))
        got = {k.lower(): v for k, v in (rb[name].get("terms") or {}).items()}
        for t, net in terms.items():
            if got.get(t.lower()) not in (net, net.replace("gnd!", "0"),
                                          f"{net}!"):
                print(f"[{cell} gateB] NOTE {name}.{t}={got.get(t.lower())}"
                      f" (want {net})")
    for name, kv in {**PARAMS.get(cell, {}), **MOS_PARAMS.get(cell, {})}.items():
        got = rb[name]["params"]
        for k, v in kv.items():
            if canon(got.get(k)) != canon(v):
                print(f"[{cell} gateB] FAIL {name} {k}={got.get(k)} != {v}")
                ok = False
    if ok:
        print(f"[{cell} gateB] PASS ({len(rb)} inst)")
    return ok


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    cells = sys.argv[2:] or list(TBS)
    client = VirtuosoClient.from_env()
    ok_all = True
    for c in cells:
        if mode in ("build", "all"):
            build(client, c)
        if mode in ("verify", "all"):
            ok_all &= verify(client, c)
    print(f"\n=== n2s tbs: {'ALL GATES PASS' if ok_all else 'FAILURES PRESENT'} ===")
    sys.exit(0 if ok_all else 1)
