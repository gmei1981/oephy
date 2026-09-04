#!/usr/bin/env python3
"""Assemble the tb_afe_tran top-level schematic (testbench as schematic).

Circuit = netlists/tb_afe_tran.scs template body:
  Xtb (afe_tb_tran symbol) + supplies w/ package parasitics (vsource/res/ind)
  + cfmom decaps + Xdac (afe_dac_r2r) + Xesd_rx/Xesd_tx (afe_pad_esd)
  + Xpc power clamp (nch_hia18_mac).
Directives (nodeset/ic/simOpts/tran/saveOptions/save) and all stimulus
values (source tails, RS/LS/AMPL/FN) are appended/patched at golden
assembly time (scripts/gen_golden_netlist.py).
Ground = net label "gnd!" (== template node 0).

Pre-step: bake ESD diode nf=100 (golden-run design point; source .scs
default nf_dio=50 was never used by any recorded run).

Run from /tmp: cd /tmp && .../python <this>
"""
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

# name -> (lib, master, col, row, {term: net})   col/row in grid units
SYMS = {
    "Xtb": (LIB, "afe_tb_tran", 0, 0,
            {"tx_pad": "tx_pad", "rx_in": "rx_in", "vref": "vref",
             "ck8": "ck8", "pclk": "pclk", "d_even": "d_even",
             "d_odd": "d_odd", "lock": "lock", "err_cnt": "err_cnt",
             "bit_cnt": "bit_cnt", "vdd": "vdd", "vccio": "vccio",
             "vss": "vss",
             **{f"codeb{k}": f"codeb{k}" for k in range(8)}}),
    "Vvdd":  ("analogLib", "vsource", -4.5, 4, {"PLUS": "vddsrc", "MINUS": GND}),
    "Vnvdd": ("analogLib", "vsource", -4.5, 2,
              {"PLUS": "vddsrc", "MINUS": "vddpkg"}),
    "Rvdd":  ("analogLib", "res", -4.5, 1, {"PLUS": "vddpkg", "MINUS": "vddi"}),
    "Lvdd":  ("analogLib", "ind", -4.5, 0, {"PLUS": "vddi", "MINUS": "vdd"}),
    "Vvccio": ("analogLib", "vsource", -3, 3,
               {"PLUS": "vcciosrc", "MINUS": GND}),
    "Rvccio": ("analogLib", "res", -3, 1,
               {"PLUS": "vcciosrc", "MINUS": "vcciopkg"}),
    "Lvccio": ("analogLib", "ind", -3, 0,
               {"PLUS": "vcciopkg", "MINUS": "vccio"}),
    "Rvss": ("analogLib", "res", -1.5, 1, {"PLUS": "vss", "MINUS": "vssext"}),
    "Lvss": ("analogLib", "ind", -1.5, 0, {"PLUS": "vssext", "MINUS": GND}),
    "Xdac": (LIB, "afe_dac_r2r", 0, -5,
             {"vref": "vref", "vccio": "vccio", "vdd": "vdd", "vss": "vss",
              **{f"b{k}": f"codeb{k}" for k in range(8)}}),
    "Xesd_rx": (LIB, "afe_pad_esd", 3, 1,
                {"pad": "rx_in", "vdd": "vdd", "vss": "vss"}),
    "Xesd_tx": (LIB, "afe_pad_esd", 3, -1,
                {"pad": "tx_pad", "vdd": "vdd", "vss": "vss"}),
}
# cfmom decap array: (name, plus_net, minus_net)
CFMOM = ([(f"Cdvdd{k}", "vdd", "vss") for k in range(1, 5)] +
         [(f"Cdvccio{k}", "vccio", "vss") for k in range(1, 5)] +
         [("Cdvref1", "vref", "vss"), ("Cdvref2", "vref", "vss")])
# Xpc power clamp: nch_hia18_mac (vdd vss vss vss) l=150n nfin=20
XPC = ("Xpc", "vdd", "vss", "vss", "vss")

PARAMS = {
    "Rvdd": {"r": "0.5"}, "Rvccio": {"r": "0.5"}, "Rvss": {"r": "0.5"},
    "Lvdd": {"l": "0.01n"}, "Lvccio": {"l": "0.01n"}, "Lvss": {"l": "0.01n"},
    "Xpc": {"l": "150n", "nFin": "20"},
}


def fix_esd_nf(client):
    """Bake the golden-run ESD design point (nf=100) into afe_pad_esd."""
    raw = client.schematic.read(LIB, "afe_pad_esd", param_filters=None)
    diodes = [i for i in raw["instances"] if "hia18" in i["cell"]]
    changed = 0
    for d in diodes:
        cur = str((d.get("params") or {}).get("nf", ""))
        if cur != "100":
            client.execute_skill(
                f'dbReplaceProp(car(setof(x dbOpenCellViewByType("{LIB}" '
                f'"afe_pad_esd" "schematic" "" "a")~>instances '
                f'x~>name=="{d["name"]}")) "nf" "string" "100")')
            changed += 1
    client.execute_skill(
        f'prog1( schCheck(dbOpenCellViewByType("{LIB}" "afe_pad_esd" "schematic" "" "a")) dbSave(dbOpenCellViewByType("{LIB}" "afe_pad_esd" "schematic" "" "a")) )')
    print(f"esd nf=100 baked ({changed} updated, {len(diodes)-changed} already)")


                                       # adjacent stubs on dense symbols (Xtb/Xdac)


def build(client):
    r = client.execute_skill(f'ddGetObj("{LIB}" "tb_afe_tran")!=nil')
    if (r.output or "").strip().strip('"') in ("t", "True"):
        sys.exit("[abort] tb_afe_tran already exists")

    items = list(SYMS.items()) + [("Xpc", None)] + \
            [(n, None) for n, _, _ in CFMOM]
    # encode placement for cfmom/Xpc inline
    PLACE = {}
    for i, (n, p, m) in enumerate(CFMOM):
        PLACE[n] = (PDK, "cfmom_2t_p80", -5.5 + 0.5 * i, -2.5,
                    {"PLUS": p, "MINUS": m})
    PLACE["Xpc"] = (PDK, "nch_hia18_mac", 4.5, 0, None)

    CHUNK = 14
    for ci in range(0, len(items), CHUNK):
        editor = client.schematic.create if ci == 0 else client.schematic.modify
        with editor(LIB, "tb_afe_tran") as sch:
            for name, spec in items[ci:ci + CHUNK]:
                if name == "Xpc":
                    lib2, master, x, y, _ = PLACE[name]
                    sch.add(inst(lib2, master, "symbol", name,
                                 x * GRID, y * GRID, "R0"))
                    sch.add_net_label_to_transistor(
                        name, drain_net="vdd", gate_net="vss",
                        source_net="vss", body_net="vss")
                elif name in PLACE:
                    lib2, master, x, y, terms = PLACE[name]
                    sch.add(inst(lib2, master, "symbol", name,
                                 x * GRID, y * GRID, "R0"))
                    for t, net in terms.items():
                        sch.add(label_term(name, t, net))
                else:
                    lib2, master, x, y, terms = spec
                    sch.add(inst(lib2, master, "symbol", name,
                                 x * GRID, y * GRID, "R0"))
                    for t, net in terms.items():
                        sch.add(label_term(name, t, net))
    print(f"placed {len(items)} instances")


def params_and_verify(client):
    client.open_window(LIB, "tb_afe_tran", view="schematic")
    for name, kv in PARAMS.items():
        _run_batched_param_update(client, LIB, "tb_afe_tran", name, kv)
        if name == "Xpc":
            for prop in ("sa", "sb"):
                client.execute_skill(
                    f'dbReplaceProp(car(setof(x dbOpenCellViewByType("{LIB}" '
                    f'"tb_afe_tran" "schematic" "" "a")~>instances '
                    f'x~>name=="Xpc")) "{prop}" "string" "0")')
    res = client.execute_skill(
        f'prog1( schCheck(dbOpenCellViewByType("{LIB}" "tb_afe_tran" '
        f'"schematic" "" "a")) '
        f'dbSave(dbOpenCellViewByType("{LIB}" "tb_afe_tran" "schematic" "" "a")) )')
    print("schCheck+save:", (res.output or "").strip()[:40])

    raw = client.schematic.read(LIB, "tb_afe_tran", param_filters=None)
    rb = {i["name"]: i for i in raw["instances"]}
    want = set(SYMS) | set(PLACE := {**{n: 1 for n, _, _ in CFMOM}, "Xpc": 1})
    assert set(rb) == want, f"gateB names diff {set(rb) ^ want}"
    SUFX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3}

    def canon(v):
        v = str(v).strip().lower()
        import re as _re
        m = _re.fullmatch(r"([0-9.e+]+)([fpnum]?)", v)
        return round(float(m.group(1)) * SUFX.get(m.group(2), 1.0), 15) if m else v

    for name in ("Rvdd", "Rvccio", "Rvss"):
        assert canon(rb[name]["params"].get("r")) == 0.5, name
    for name in ("Lvdd", "Lvccio", "Lvss"):
        assert canon(rb[name]["params"].get("l")) == 1e-11, name
    assert str(rb["Xpc"]["params"].get("nfin")) == "20", "Xpc nfin"
    print(f"gateB PASS ({len(rb)} inst)")
    print("NOTE: no pins (flat top); ground via 'gnd!' net labels")


if __name__ == "__main__":
    client = VirtuosoClient.from_env()
    fix_esd_nf(client)
    build(client)
    params_and_verify(client)
