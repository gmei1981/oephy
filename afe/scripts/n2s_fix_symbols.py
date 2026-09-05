"""Audit afe_sch for schematic cells missing a symbol view and build the
missing symbols manually (afe_tb pattern): ports from the tran source
subckt, inputs left / outputs+supplies right, 0.25 pitch, instance/drawing
selection box, pin/label names, term order = subckt declaration order.

Run from /tmp (local-mode bridge)."""
import re
import sys
from pathlib import Path

from virtuoso_bridge import VirtuosoClient
from virtuoso_bridge.virtuoso.symbol import (
    symbol_create_label,
    symbol_create_pin,
    symbol_create_selection_box,
    symbol_read_ports_skill,
    symbol_set_term_order,
)

AFE = Path("/home/gmei/git/oephy/afe")
LIB = "afe_sch"
TRAN = AFE / "tran"
# cells with schematic views that are NOT flat TB tops (those never get
# symbols) -- audit only the design/leaf cells
SKIP = {c for c in ("tb_bias_dc", "tb_noise_smoke", "tb_afe_dac_dc",
                    "tb_afe_txron_mc", "tb_afe_cmp_mc", "tb_sa_test",
                    "tb_afe_va", "tb_afe_tran")}


def subckt_ports(cell):
    for f in TRAN.glob("*.scs"):
        text = re.sub(r"\\\s*\n\s*", " ", f.read_text())
        m = re.search(rf"subckt\s+{cell}\s*\(([^)]*)\)", text)
        if m:
            return m.group(1).split(), f.name
    return None, None


def build_symbol(client, cell, ports, outs):
    """Supplies (vdd/vss) go on the BOTTOM edge, spread horizontally: their
    label stubs then point down away from all pins.  A pin vertically above
    another pin (old left-column layout) makes the edge-pin's stub cross
    the pin below -> DB-270004 net short (measured on tb_sa_test 9-5)."""
    sup = [p for p in ports if p in ("vdd", "vss")]
    left = [p for p in ports if p not in outs and p not in sup]
    right = [p for p in ports if p in outs and p not in sup]
    parts = []
    nl, nr = max(len(left), 1), max(len(right), 1)
    for i, p in enumerate(left):
        parts.append(symbol_create_pin(
            p, -1.5, 0.375 - 0.25 * i + (0.125 if nl % 2 == 0 else 0),
            direction="input",
            label_justification="centerRight", label_x=-1.6))
    for i, p in enumerate(right):
        parts.append(symbol_create_pin(
            p, 1.5, 0.25 - 0.5 * i if len(right) == 1
            else 0.375 - 0.25 * i + (0.125 if nr % 2 == 0 else 0),
            direction="output",
            label_justification="centerLeft", label_x=1.6))
    xs = (-0.75, 0.75, -0.25, 0.25)  # bottom spread for up to 4 supplies
    for i, p in enumerate(sup):
        parts.append(symbol_create_pin(
            p, xs[i % 4], -0.75, direction="inputOutput",
            label_justification="centerCenter", label_y=-0.9))
    parts.append(symbol_create_selection_box(-1.5, -0.75, 1.5, 0.75))
    parts.append(symbol_create_label(
        "pin", "label", 0.0, 0.9, cell, "centerCenter", "R0",
        "stick", 0.125))
    parts.append(symbol_set_term_order(ports))
    r = client.execute_skill(
        f'let((cv) cv=dbOpenCellViewByType("{LIB}" "{cell}" "symbol" '
        f'"schematicSymbol" "a") ' + " ".join(parts) + " dbSave(cv) )")
    ok = not (r.errors or [])
    print(f"[{cell}] symbol build {'OK' if ok else 'FAIL'} "
          f"{(r.errors or [])[:1]}")
    rb = client.execute_skill(symbol_read_ports_skill(LIB, cell))
    names = re.findall(r'"term" "(\w+)"', rb.output or "")
    print(f"[{cell}] readback {len(names)} terms: {names}")
    return ok and set(names) == set(ports)


OUT_PORTS = {"afecmp_bank": {"outp", "outn"}, "afe_dac_r2r": {"vref"},
             "afe_strongarm": {"qp", "qn"}, "afe_dlatch": {"q"},
             "afe_pad_esd": {"pad"}, "afe_tx_drv": {"pad"},
             "afe_bias": {"vbias"}}

client = VirtuosoClient.from_env()
cells = client.fetch(f'ddGetObj("{LIB}")~>cells', ["name"])
missing = []
for c in cells:
    name = c["name"]
    if name in SKIP:
        continue
    views = client.fetch(
        f'ddGetObj("{LIB}" "{name}")~>views', ["name"])
    vnames = {v["name"] for v in views}
    if "schematic" in vnames and "symbol" not in vnames:
        missing.append(name)
print("missing symbols:", missing)

# force relayout: symbols whose supplies sat vertically adjacent on an
# edge column (stub-crossing short risk, measured DB-270004 on tb_sa_test)
FORCE = {"afe_strongarm", "afe_dlatch"}
for cell in sorted(FORCE):
    client.execute_skill(
        f'ddDeleteObj(ddGetObj("{LIB}" "{cell}" "symbol"))')
    print(f"[{cell}] old symbol deleted (force relayout)")
missing = sorted(set(missing) | FORCE)

ok_all = True
for cell in missing:
    ports, src = subckt_ports(cell)
    if not ports:
        print(f"[{cell}] no subckt def found in tran/ -- SKIP")
        ok_all = False
        continue
    print(f"[{cell}] {len(ports)} ports from {src}: {ports}")
    ok_all &= build_symbol(client, cell, ports, OUT_PORTS.get(cell, set()))
print("=== fix symbols:", "ALL OK" if ok_all else "FAILURES", "===")
sys.exit(0 if ok_all else 1)
