#!/usr/bin/env python3
"""Generate nearint loop-fix variants for parallel server testing.

Variants (all derived from sim/pll_step1_nearint.scs):
  A_base   : baseline, stop=4u (equilibrium discovery)
  B_ulvt   : gm_x input pair MN1/MN2 -> nch_ulvt_mac, stop=2u
  B2_lvt   : gm_x input pair MN1/MN2 -> nch_lvt_mac,  stop=2u
  C_prechg : Iinj precharge 550u -> 600u (VI~0.60V, near lock VCTRL), stop=2u
  D_mirror : gm_x MP2 mirror length 72n -> 16n (pull-up 4.5x), stop=2u

Each variant dir is self-contained (netlist + inc + va) for a flat remote upload.
"""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sim" / "pll_step1_nearint.scs"
INC = ROOT / "netlist" / "inc"
VA = ROOT / "netlist" / "va"
OUT = ROOT / "sim" / "var"

VARIANTS = {
    "A_base":   {"stop": "4u", "gm_dev": None, "mp2_l": None, "iinj": None},
    "B_ulvt":   {"stop": "2u", "gm_dev": "nch_ulvt_mac", "mp2_l": None, "iinj": None},
    "B2_lvt":   {"stop": "2u", "gm_dev": "nch_lvt_mac", "mp2_l": None, "iinj": None},
    "C_prechg": {"stop": "2u", "gm_dev": None, "mp2_l": None, "iinj": "600u"},
    "D_mirror": {"stop": "2u", "gm_dev": None, "mp2_l": "16n", "iinj": None},
}


def edit_netlist(text: str, cfg: dict) -> str:
    # tran line: set stop, add 100ps strobe (shrink output 40x)
    text = re.sub(r"(plltran\s+tran\s+stop=)\S+(\s+maxstep=\S+)",
                  r"\g<1>%s\g<2>" % cfg["stop"], text)
    if "strobeperiod" not in text:
        text = re.sub(r'(ic="OUTP=0\.6")', r'\1 strobeperiod=100p strobeoutput=strobeonly', text)
    if cfg["iinj"]:
        text = re.sub(r"val1=-550u", f"val1=-{cfg['iinj']}", text)
    return text


def edit_gm(text: str, dev: str | None, mp2_l: str | None) -> str:
    if dev is None and mp2_l is None:
        return text
    lines = text.split("\n")
    # only inside subckt gm_x (first lines until `ends gm_x`), not cmp_x
    out, in_gm = [], False
    for ln in lines:
        if ln.startswith("subckt gm_x"):
            in_gm = True
        if in_gm and ln.startswith("ends gm_x"):
            in_gm = False
        if in_gm:
            if dev and re.match(r"^M(N1|N2) \(", ln):
                ln = re.sub(r"nch_svt_mac", dev, ln)
            if mp2_l and ln.startswith("MP2 ("):
                ln = re.sub(r"l=72n", f"l={mp2_l}", ln)
        out.append(ln)
    return "\n".join(out)


def main():
    base = SRC.read_text()
    gm_src = (INC / "spd_cmp_gm.scs").read_text()
    for name, cfg in VARIANTS.items():
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        (d / f"nearint_{name}.scs").write_text(edit_netlist(base, cfg))
        (d / "spd_cmp_gm.scs").write_text(edit_gm(gm_src, cfg["gm_dev"], cfg["mp2_l"]))
        for f in ["dtc_10b.scs", "vco_dual.scs"]:
            shutil.copy(INC / f, d / f)
        for f in ["pll_mmd_edge.va", "pll_lms.va", "pll_dtc_decoder_10b.va",
                  "pll_hybrid_aux.va", "constants.vams", "disciplines.vams"]:
            shutil.copy(VA / f, d / f)
        print(f"wrote {d}/  ({cfg['stop']}, gm_dev={cfg['gm_dev']}, mp2_l={cfg['mp2_l']}, iinj={cfg['iinj']})")


if __name__ == "__main__":
    main()
