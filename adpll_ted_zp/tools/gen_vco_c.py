#!/usr/bin/env python3
"""Generate netlist/inc/vco_c.scs — Plan C (paper-faithful) 8GHz dual-core VCO.

Paper (JSSC 2021 Sec.IV, Fig.12) elements:
- thin-oxide (ulvt) NMOS cross-coupled core at 0.5V supply (from on-chip LDO)
- tail inductor Ls: high-Z at 2*fosc (optional, parameterizable)
- discrete tuning: 12x cfmom bank (nr=188)
- VAR_I 3-bit: KVCO_I steps ~20MHz/V (nfin 2/2/4 per side -> ~17/34/69 MHz/V)
- VAR_P 5-bit: KVCO_P steps ~8.6MHz/V (nfin 1/2/4/8/16 per side; the paper's
  0.5MHz/V step is unreachable with this PDK varactor -> documented deviation)
- VAR_T PTAT: skipped (fixed-temperature comparison)
- dual core: NMOS coupling switches (EN2), core B supply switch on 0.5V rail

KEY MEASUREMENT (2026-09-02, local, 0.5V core, direct moscap nfin=12):
  KVCO = 206MHz/V, monotonic over VCTRL 0.15-0.53V, NO rectification pump
  (VI stable). The series-cap cell (v1) was REJECTED: it amplified the
  moscap_rf model's non-conservative pump ~80x (8uA into the control node,
  swamping the GM) and gave uncontrollable slope.
  Sizing: per-nfin ~8.6MHz/V; VAR_I 2/2/4 nfin ~ 17/34/69 MHz/V (~paper 20/40/80).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "netlist" / "inc" / "vco_c.scs"

NCH = ("nch_ulvt_mac l=16n nfin=2 w=58n multi=1 sd=74n sa=90n sb=90n "
       "ploda1=16n ploda2=0 ploda3=0 plodb1=16n plodb2=0 plodb3=0 nf_flag=1 "
       "smbt=1M smbb=1M dinsaflag=0 ppitch=0 spot=103n spob=103n "
       "spotl1=103n spobl1=103n spotl2=103n spobl2=103n spotr1=103n "
       "spobr1=103n spotr2=103n spobr2=103n")
PCH = ("pch_svt_mac l=16n nfin=2 w=58n multi=1 sd=74n sa=90n sb=90n "
       "ploda1=16n ploda2=0 ploda3=0 plodb1=16n plodb2=0 plodb3=0 nf_flag=1 "
       "smbt=1M smbb=1M dinsaflag=0 ppitch=0 spot=103n spob=103n "
       "spotl1=103n spobl1=103n spotl2=103n spobl2=103n spotr1=103n "
       "spobr1=103n spotr2=103n spobr2=103n")
# VAR bank enable switch: NMOS ulvt, gate=en (0.8V domain, HIGH=on).
# Vgs=en-Vctrl>Vth conducts across the whole 0.1-0.3V control range; the
# old PMOS bulk-side switch (cb>|Vth| required) cut off for VI<0.25 ->
# I path disconnected at low control voltage (wp2/wp4 root cause).
# NOTE: enable polarity flipped vs old design: EN=0.8 -> on, EN=0 -> off.
PCH_SW = PCH.replace("pch_svt_mac", "pch_ulvt_mac")
MOSCAP = ("moscap_rf wr=538n lr=200n gr=2 br=2 multi=1 "
          "sobn=470n sobs=470n sobw=684n sobe=684n")

# bank spec: (enable pin, nfin per unit cell, cells per side in group)
VAR_I_GROUPS = [("ENI0", 2, 1), ("ENI1", 2, 1), ("ENI2", 4, 1)]
VAR_P_GROUPS = [("ENP0", 1, 1), ("ENP1", 1, 2), ("ENP2", 1, 4),
                ("ENP3", 1, 8), ("ENP4", 1, 16)]
LS_L = "2n"  # tail inductor; set "0" + short to disable (paper: high-Z at 2fosc)


def mos(name, d, g, s, b, nf, model="nch"):
    m = NCH if model == "nch" else (PCH_SW if model == "pchsw" else PCH)
    return f"{name} ({d} {g} {s} {b}) {m} nf={nf}"


def cfmom(name, plus, minus, shield, nr):
    return (f"{name} ({plus} {minus} {shield}) cfmom_wo_p80 dmflag=0 lr=1u "
            f"multi=1 mxd_flag=0 nr={nr} n_mxa=2 shield=2 spm=3 stm=1 "
            f"vapmod=2 grflag=1 gdis_t=185n gdis_b=185n gdis_l=102n gdis_r=102n")


def var_cell(prefix, tank, vctrl, en, nfin):
    """direct moscap (nfin) + NMOS enable (gate=en, HIGH=on, 0.8V domain);
    off-state bulk -> VDD via 1G bleeder."""
    cb = f"{prefix}_cb"
    lines = [
        f"{prefix}_mv ({tank} {cb} {cb}) {MOSCAP} nfin={nfin}",
        mos(f"{prefix}_sw", cb, en, vctrl, "VSS", 2, model="nch"),
        f"{prefix}_rb ({cb} VDD 0) resistor r=1G",
    ]
    return lines


def gen_vco_x():
    L = []
    L.append("// vco_x_c — Plan C core: 0.5V supply, Ls tail inductor, VAR banks")
    L.append("subckt vco_x_c (VDD VSS VCTRL_P VCTRL_I OUTP OUTN ENI0 ENI1 ENI2 \\")
    L.append("    ENP0 ENP1 ENP2 ENP3 ENP4)")
    L.append(mos("MN1", "OUTP", "OUTN", "TAIL", "VSS", 16, model="nch"))
    L.append(mos("MN0", "OUTN", "OUTP", "TAIL", "VSS", 16, model="nch"))
    L.append(f"Ls (TAIL VSS) inductor l={LS_L} r=1")
    L.append("L1 (VDD OUTN) inductor l=1.5n r=2")
    L.append("L0 (VDD OUTP) inductor l=1.5n r=2")
    L.append("Cbyp (VDD VSS) capacitor c=10p")
    for i in range(12):
        plus = "OUTP" if i in (0, 6) else "OUTN"
        minus = "OUTN" if i in (0, 6) else f"net{i:02d}"
        L.append(cfmom(f"CF{i}", plus, minus, "VSS", 174))
    for en, nfin, cells in VAR_I_GROUPS:
        for c in range(cells):
            for side, tank in (("p", "OUTP"), ("n", "OUTN")):
                L += var_cell(f"VI{en[-1]}{c}{side}", tank, "VCTRL_I", en, nfin)
    for en, nfin, cells in VAR_P_GROUPS:
        for c in range(cells):
            for side, tank in (("p", "OUTP"), ("n", "OUTN")):
                L += var_cell(f"VP{en[-1]}{c}{side}", tank, "VCTRL_P", en, nfin)
    L.append("ends vco_x_c")
    return L


def gen_vco_dual():
    L = []
    L.append("// vco_dual_8g_c — Plan C dual core: 0.5V cores + 0.8V enable logic")
    L.append("subckt vco_dual_8g_c (VDD VDDC VSS VCTRL_P VCTRL_I OUTP OUTN EN2 \\")
    L.append("    ENI0 ENI1 ENI2 ENP0 ENP1 ENP2 ENP3 ENP4)")
    L.append(mos("MNEN", "EN2B", "EN2", "VSS", "VSS", 2, model="nch"))
    L.append(mos("MPEN", "EN2B", "EN2", "VDD", "VDD", 2, model="pch"))
    L.append(mos("MPWRB", "VDDB", "EN2B", "VDDC", "VDDC", 64, model="pch"))
    L.append(mos("MSWP", "OUTP", "EN2", "OUTPB", "VSS", 64, model="nch"))
    L.append(mos("MSWN", "OUTN", "EN2", "OUTNB", "VSS", 64, model="nch"))
    L.append("Xa (VDDC VSS VCTRL_P VCTRL_I OUTP OUTN ENI0 ENI1 ENI2 \\")
    L.append("    ENP0 ENP1 ENP2 ENP3 ENP4) vco_x_c")
    L.append("Xb (VDDB VSS VCTRL_P VCTRL_I OUTPB OUTNB ENI0 ENI1 ENI2 \\")
    L.append("    ENP0 ENP1 ENP2 ENP3 ENP4) vco_x_c")
    L.append("ends vco_dual_8g_c")
    return L


def main():
    lines = [
        "// vco_c.scs — generated by tools/gen_vco_c.py (Plan C, paper Sec.IV)",
        "// core supply VDDC=0.5V from LDO (ldo_05.scs); logic/enables on VDD=0.8V",
        "// EN=0.8 -> bank group enabled (NMOS gate switch on); EN=0 -> disabled",
        "// varactor = direct moscap_rf (series-cap cell REJECTED: model pump)",
        "",
    ]
    lines += gen_vco_x()
    lines.append("")
    lines += gen_vco_dual()
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
