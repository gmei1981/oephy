#!/usr/bin/env python3
"""Assemble the afe_tb_tran structural schematic (replaces afe_tb_tran.va).

Contents (from va/afe_tb_tran.va):
  - 6 digital-behavioral VA leaf symbols (G1 G2 CK PP SMP CHK)
  - 4 transistor cell symbols (DRV BIAS BA BB)
  - 8 TG-mux MOS (nFin=4, l=16n, sa/sb=0)
  - channel: Rser/TL/Cxt/Crx (analogLib)
  - analog glue as analogLib primitives: Vpi(vdc), EazA/EazB(vcvs),
    Idr(idc), Vcb0-7(vdc) -- params patched at golden-assembly time
  - 18 pins in va module declaration order

Run from /tmp (local-mode bridge): cd /tmp && .../python <this> build
"""
import json
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

# name -> (lib, master, x, y, {term: net})
SYMS = {
    "G1":  ("afe_sch", "afe_prbs23_gen", 0, 10,
            {"vout": "din", "vdd": "vdd"}),
    "G2":  ("afe_sch", "afe_prbs23_gen", 0, 8.5,
            {"vout": "aggr", "vdd": "vdd"}),
    "CK":  ("afe_sch", "afe_clk_gen", 2, 10,
            {"ck8": "ck8", "pclk": "pclk", "pi_code": "pi_in", "vdd": "vdd"}),
    "PP":  ("afe_sch", "afe_pingpong", 2, 7,
            {"pclk": "pclk", "a_eval": "a_eval", "a_az": "a_az",
             "b_eval": "b_eval", "b_az": "b_az", "vdd": "vdd"}),
    "SMP": ("afe_sch", "afe_samp", 14.5, 10,
            {"act_p": "act_p", "act_n": "act_n", "ck8": "ck8",
             "d_even": "d_even", "d_odd": "d_odd", "vdd": "vdd"}),
    "CHK": ("afe_sch", "afe_ber_chk", 14.5, 7,
            {"d_even": "d_even", "d_odd": "d_odd", "ck8": "ck8",
             "lock": "lock", "err_cnt": "err_cnt", "bit_cnt": "bit_cnt",
             "vdd": "vdd"}),
    "DRV":  ("afe_sch", "afe_tx_drv", 4, 10,
             {"din": "din", "pad": "tx_pad", "vccio": "vccio",
              "vdd": "vdd", "vss": "vss"}),
    "BIAS": ("afe_sch", "afe_bias", 10, 10,
             {"vbias": "vbias", "vdd": "vdd", "vss": "vss"}),
    "BA": ("afe_sch", "afecmp_bank", 7.5, 10,
           {"vin": "rx_in", "vref": "vref", "eval": "a_eval",
            "az": "a_az_g", "vbias": "vbias", "outp": "cmp_a_p",
            "outn": "cmp_a_n", "vdd": "vdd", "vss": "vss", "gp": "gp_a"}),
    "BB": ("afe_sch", "afecmp_bank", 7.5, 7,
           {"vin": "rx_in", "vref": "vref", "eval": "b_eval",
            "az": "b_az_g", "vbias": "vbias", "outp": "cmp_b_p",
            "outn": "cmp_b_n", "vdd": "vdd", "vss": "vss", "gp": "gp_b"}),
    "Rser": ("analogLib", "res", 5.5, 11,
             {"PLUS": "tx_pad", "MINUS": "ntx"}),
    "TL": ("analogLib", "tline", 5.5, 9.5,
           {"IN+": "ntx", "IN-": "vss", "OUT+": "rx_in", "OUT-": "vss"}),
    "Cxt": ("analogLib", "cap", 5.5, 8, {"PLUS": "aggr", "MINUS": "rx_in"}),
    "Crx": ("analogLib", "cap", 5.5, 6.5, {"PLUS": "rx_in", "MINUS": "vss"}),
    "Vpi":  ("analogLib", "vdc", 0, 4, {"PLUS": "pi_in", "MINUS": "vss"}),
    "EazA": ("analogLib", "vcvs", 2, 4,
             {"PLUS": "a_az_g", "MINUS": "vss", "NC+": "a_az", "NC-": "vss"}),
    "EazB": ("analogLib", "vcvs", 3.5, 4,
             {"PLUS": "b_az_g", "MINUS": "vss", "NC+": "b_az", "NC-": "vss"}),
    "Idr":  ("analogLib", "idc", 5, 4, {"PLUS": "vss", "MINUS": "gp_a"}),
    **{f"Vcb{k}": ("analogLib", "vdc", 0.8 * k, 1.5,
                   {"PLUS": f"codeb{k}", "MINUS": "vss"}) for k in range(8)},
}

# name -> (master, x, y, drain, gate, source, body)
MOS = {
    "MtgAp": ("nch_svt_mac", 11.5, 11, "cmp_a_p", "a_eval", "act_p", "vss"),
    "MtgAn": ("nch_svt_mac", 11.5, 10, "cmp_a_n", "a_eval", "act_n", "vss"),
    "MtgBp": ("nch_svt_mac", 12.5, 11, "cmp_b_p", "b_eval", "act_p", "vss"),
    "MtgBn": ("nch_svt_mac", 12.5, 10, "cmp_b_n", "b_eval", "act_n", "vss"),
    "MpgAp": ("pch_svt_mac", 11.5, 8.5, "cmp_a_p", "b_eval", "act_p", "vdd"),
    "MpgAn": ("pch_svt_mac", 11.5, 7.5, "cmp_a_n", "b_eval", "act_n", "vdd"),
    "MpgBp": ("pch_svt_mac", 12.5, 8.5, "cmp_b_p", "a_eval", "act_p", "vdd"),
    "MpgBn": ("pch_svt_mac", 12.5, 7.5, "cmp_b_n", "a_eval", "act_n", "vdd"),
}

PINS = [("tx_pad", "output"), ("rx_in", "output"), ("vref", "inputOutput"),
        ("ck8", "output"), ("pclk", "output"), ("d_even", "output"),
        ("d_odd", "output"), ("lock", "output"), ("err_cnt", "output"),
        ("bit_cnt", "output"), ("vdd", "inputOutput"),
        ("vccio", "inputOutput"), ("vss", "inputOutput")] + \
       [(f"codeb{k}", "output") for k in range(8)]

PARAMS = {  # CDF-path params per instance
    "Rser": {"r": "1.5"}, "Cxt": {"c": "8f"}, "Crx": {"c": "50f"},
    **{m: {"l": "16n", "nFin": "4"} for m in MOS},
}


def build(client):
    r = client.execute_skill(f'ddGetObj("{LIB}" "afe_tb_tran")!=nil')
    if (r.output or "").strip().strip('"') in ("t", "True"):
        sys.exit("[abort] afe_tb_tran already exists")

    items = list(SYMS.items())
    items += [(n, None) for n in MOS]
    CHUNK = 12
    for ci in range(0, len(items), CHUNK):
        editor = client.schematic.create if ci == 0 else client.schematic.modify
        with editor(LIB, "afe_tb_tran") as sch:
            for name, spec in items[ci:ci + CHUNK]:
                if spec is None:  # MOS
                    m, x, y, d, g, s, b = MOS[name]
                    sch.add(inst(PDK, m, "symbol", name,
                                 x * GRID, y * GRID, "R0"))
                    sch.add_net_label_to_transistor(
                        name, drain_net=d, gate_net=g, source_net=s, body_net=b)
                else:
                    lib2, master, x, y, terms = spec
                    sch.add(inst(lib2, master, "symbol", name,
                                 x * GRID, y * GRID, "R0"))
                    for t, net in terms.items():
                        sch.add(label_term(name, t, net))
                if ci + CHUNK >= len(items) and name == items[-1][0]:
                    for i, (pname, pdir) in enumerate(PINS):
                        sch.add(pin(pname, -1.5 * GRID, i * GRID, "R0",
                                    direction=pdir))
    n = len(SYMS) + len(MOS)
    print(f"placed {n} instances, {len(PINS)} pins")


def params_and_verify(client):
    client.open_window(LIB, "afe_tb_tran", view="schematic")
    for name, kv in PARAMS.items():
        _run_batched_param_update(client, LIB, "afe_tb_tran", name, kv)
        if name in MOS:
            for prop in ("sa", "sb"):
                client.execute_skill(
                    f'dbReplaceProp(car(setof(x dbOpenCellViewByType("{LIB}" '
                    f'"afe_tb_tran" "schematic" "" "a")~>instances '
                    f'x~>name=="{name}")) "{prop}" "string" "0")')
    res = client.execute_skill(
        f'prog1( schCheck(dbOpenCellViewByType("{LIB}" "afe_tb_tran" '
        f'"schematic" "" "a")) '
        f'dbSave(dbOpenCellViewByType("{LIB}" "afe_tb_tran" "schematic" "" "a")) )')
    print("schCheck+save:", (res.output or "").strip()[:40])

    raw = client.schematic.read(LIB, "afe_tb_tran", param_filters=None)
    rb = {i["name"]: i for i in raw["instances"]}
    want = set(SYMS) | set(MOS)
    assert set(rb) == want, f"gateB names {set(rb) ^ want}"
    for name in MOS:
        got = rb[name]["params"]
        assert str(got.get("nfin")) == "4", f"{name} nfin={got.get('nfin')}"
    for name, kv in (("Rser", "1.5"), ("Cxt", "8f"), ("Crx", "50f")):
        got = str(rb[name]["params"])
        assert re.search(rf"\b{re.escape(kv.rstrip('f'))}", got), \
            f"{name} params {got}"
    assert set(raw.get("pins", {})) == {p for p, _ in PINS}
    print(f"gateB PASS ({len(rb)} inst, {len(PINS)} pins)")
    (AFE / "output" / "n2s_top_manifest.json").write_text(json.dumps(
        {"syms": {k: v[4] for k, v in SYMS.items()},
         "mos": {k: v[3:] for k, v in MOS.items()},
         "pins": PINS}, indent=1))
    print("manifest saved -> output/n2s_top_manifest.json")


if __name__ == "__main__":
    client = VirtuosoClient.from_env()
    build(client)
    params_and_verify(client)
