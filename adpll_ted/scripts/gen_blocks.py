#!/usr/bin/env python3
"""Generate 10-bit DTC subckt, 10-bit decoder VA, dual-core VCO, and block includes.

All derived from netlist/base_hybrid.scs (proven UCIe 6.2G hybrid netlist).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "netlist" / "base_hybrid.scs"
INC = ROOT / "netlist" / "inc"
VA = ROOT / "netlist" / "va"
INC.mkdir(exist_ok=True)

MOS_TAIL = (
    " sd=74n sa=90n sb=90n ploda1=16n ploda2=0 ploda3=0 plodb1=16n \\\n"
    "        plodb2=0 plodb3=0 nf_flag=1 smbt=1M smbb=1M dinsaflag=0 ppitch=0 \\\n"
    "        spot=103n spob=103n spotl1=103n spobl1=103n spotl2=103n \\\n"
    "        spobl2=103n spotr1=103n spobr1=103n spotr2=103n spobr2=103n"
)


def extract_subckt(text: str, name: str) -> str:
    m = re.search(rf"^subckt {name} .*?^ends {name}", text, re.S | re.M)
    if not m:
        sys.exit(f"subckt {name} not found in base")
    return m.group(0)


def gen_dtc_10b(nbits: int = 10, nf: int = 2, cunit: float = 0.5e-15,
                rl: float = 2.3e-6, rw: float = 2e-6,
                out: Path = INC / "dtc_10b.scs") -> None:
    """DTC: RC core + switched-capacitor bank (paper Fig.11a) + inverter buffer.

    Unit = MOS switch (nf fingers) + CLSB cap to VSS (real cap, linear).
    Tres = ln2*(R0+Ron)*CLSB ~ 330 fs target.
    """
    nsw = (1 << nbits) - 1
    lines = [
        f"// dtc_10b.scs — {nbits}-bit RC DTC, switched-cap bank ({nsw} units), generated",
        f"// unit: NMOS switch nf={nf} + CLSB={cunit*1e15:g}fF; R0 rhim {rl*1e6:g}u x {rw*1e6:g}u",
        f"// paper: Tres = ln2*R*CLSB = 330 fs, full DR ~ {nsw*330e-3:.0f} ps",
        f"// reset: CK_IN low -> CKXB high -> MRST_D slams VDLY to VSS (prevents charge",
        f"// re-injection from UCAP caps during discharge = the edge-dropping bug)",
        f"subckt dtc_10b (CK_IN CK_OUT VDD VSS " + " ".join(f"CODE{i}" for i in range(nsw)) + ")",
        "",
        f"R0 (CK_IN VDLY) rhim l={rl:g} w={rw:g} multi=1",
        f"MNI (CKXB CK_IN VSS VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=1 {MOS_TAIL}",
        f"MPI (CKXB CK_IN VDD VDD) pch_svt_mac l=16n nfin=2 w=58n multi=1 nf=1 {MOS_TAIL}",
        f"MRST_D (VDLY CKXB VSS VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=2 {MOS_TAIL}",
        "",
    ]
    for i in range(nsw - 1, -1, -1):
        lines.append(
            f"U{i} (VDLY CODE{i} UCAP{i} VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf={nf} {MOS_TAIL}"
        )
        lines.append(f"C{i} (UCAP{i} VSS) capacitor c={cunit:g}")
    lines += [
        "",
        f"MN1 (CK_OUT VDLY VSS VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=8 {MOS_TAIL}",
        f"MP1 (CK_OUT VDLY VDD VDD) pch_svt_mac l=16n nfin=2 w=58n multi=1 nf=8 {MOS_TAIL}",
        "ends dtc_10b",
        "",
    ]
    out.write_text("\n".join(lines))
    print(f"wrote {out} ({nsw} switch+cap units, nf={nf}, CLSB={cunit*1e15:g}fF)")


def gen_decoder_10b(nbits: int = 10, out: Path = VA / "pll_dtc_decoder_10b.va") -> None:
    """Thermometer decoder VA with 2^n-1 outputs; code offset = 2^(n-1)-1."""
    nsw = (1 << nbits) - 1
    offset = (1 << (nbits - 1)) - 1  # 511
    L = []
    L.append(f"// pll_dtc_decoder_10b.va — {nbits}-bit thermometer decoder ({nsw} outputs), generated")
    L.append("// code = round((kdtc*QE_sec + sel*vdcc + alt*rdcc)/Tres); thermometer = code + %d" % offset)
    L.append("`include \"constants.vams\"")
    L.append("`include \"disciplines.vams\"")
    L.append("")
    # Port list must be multi-line: ahdlcmi rejects very long single lines.
    L.append("module pll_dtc_decoder_10b(ckfb, kdtc, epsc, sel, alt, vdcc, rdcc,")
    for i in range(0, nsw, 16):
        row = ", ".join(f"c{j}" for j in range(i, min(i + 16, nsw)))
        L.append(f"    {row}," if i + 16 < nsw else f"    {row});")
    L.append("inout ckfb, kdtc, epsc, sel, alt, vdcc, rdcc;")
    L.append("electrical ckfb, kdtc, epsc, sel, alt, vdcc, rdcc;")
    for i in range(nsw):
        L.append(f"inout c{i};")
        L.append(f"electrical c{i};")
    L.append("")
    L.append("parameter real fout = 6.2e9;")
    L.append("parameter real fref = 153.6e6;")
    L.append("parameter real frac2 = 0.729167;")
    L.append("parameter real Tres = 330e-15;")
    L.append("parameter real vth = 0.5;")
    L.append("")
    L.append("real tdel, code_tot;")
    L.append("integer code;")
    L.append("analog begin")
    L.append(f"    @(initial_step) begin code = 0; code_tot = {offset}.0; end")
    L.append("    @(cross(V(ckfb) - vth, +1)) begin")
    L.append("        tdel = V(kdtc)*(V(epsc) - (0.5 - frac2))*(0.5/fout)")
    L.append("             + V(sel)*V(vdcc)*1e-12 + V(alt)*V(rdcc)*1e-12;")
    L.append(f"        code = (tdel >= 0.0) ? floor(tdel/Tres + 0.5) : ceil(tdel/Tres - 0.5);")
    L.append(f"        if (code > {offset}) code = {offset};")
    L.append(f"        if (code < -{offset}) code = -{offset};")
    L.append(f"        code_tot = code + {offset}.0;")
    L.append("    end")
    for i in range(nsw):
        L.append(f"    V(c{i}) <+ transition((code_tot > {i}) ? 0.8 : 0.0, 0.0, 50p, 50p);")
    L.append("end")
    L.append("endmodule")
    L.append("")
    out.write_text("\n".join(L))
    print(f"wrote {out} ({nsw} outputs, offset={offset})")


def gen_vco_dual(out: Path = INC / "vco_dual.scs") -> None:
    """Dual-core LC VCO: two vco_x cores, outputs coupled via NMOS switches, core B enable.

    Paper: cores coupled by thick-oxide NMOS switches (10 ohm); core B power-down-able.
    12nm impl: SVT switches (large nf, ~tens of ohm); core B supply PMOS power switch.
    """
    base = BASE.read_text()
    vco = extract_subckt(base, "vco_x")
    L = []
    L.append("// vco_dual.scs — reconfigurable dual-core VCO (paper Fig.12/13), generated")
    L.append("// EN2=0.8: dual-core; EN2=0: core B powered down, coupling off (single-core)")
    L.append("// VDD feeds both cores via MPWRB; COUTP/COUTN are the shorted tank outputs")
    L.append("")
    L.append(vco)  # keep vco_x definition
    L.append("")
    L.append("subckt vco_dual (VDD VSS VCTRL OUTP OUTN EN2)")
    L.append("// internal inverter: EN2B = !EN2 (PMOS power switch needs inverted gate)")
    L.append(f"MNEN (EN2B EN2 VSS VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=2 {MOS_TAIL}")
    L.append(f"MPEN (EN2B EN2 VDD VDD) pch_svt_mac l=16n nfin=2 w=58n multi=1 nf=2 {MOS_TAIL}")
    L.append("// core B supply power switch (on when EN2 high)")
    L.append(f"MPWRB (VDDB EN2B VDD VDD) pch_svt_mac l=16n nfin=2 w=58n multi=1 nf=64 {MOS_TAIL}")
    L.append("// coupling switches A<->B (on in dual-core mode)")
    L.append(f"MSWP (OUTP EN2 OUTPB VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=64 {MOS_TAIL}")
    L.append(f"MSWN (OUTN EN2 OUTNB VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=64 {MOS_TAIL}")
    L.append("Xa (VDD VSS VCTRL OUTP OUTN) vco_x")
    L.append("Xb (VDDB VSS VCTRL OUTPB OUTNB) vco_x")
    L.append("ends vco_dual")
    L.append("")
    out.write_text("\n".join(L))
    print(f"wrote {out}")


def gen_analog_blocks(out: Path = INC / "spd_cmp_gm.scs") -> None:
    """spd_x (current-mirror biased ramp) / cmp_x / gm_x subckts."""
    base = BASE.read_text()
    L = ["// spd_cmp_gm.scs — SPD / comparator / GM subckts", ""]
    L.append(spd_x_mirror())
    L.append("")
    for name in ("cmp_x", "gm_x"):
        L.append(extract_subckt(base, name))
        L.append("")
    out.write_text("\n".join(L))
    print(f"wrote {out}")


def spd_x_mirror() -> str:
    """SPD with current-mirror biased ramp source.

    Iref = (VDD-|Vgs|)/RREF ~ 6.5uA (RREF=60k); MCS nf=1 mirrors Iref.
    Ramp slope ~ I/CR0 ~ 0.25 V/ns over the 3.25ns CKDTC-high window (0.8V swing).
    VBIAS pin is kept for top-level compatibility but unused.
    """
    return """subckt spd_x (VBIAS CK_RST CK_SMP VHOLD VRAMP VDD VSS)

MIR (VBSPD_M VBSPD_M VDD VDD) pch_svt_mac l=16n nfin=2 w=58n multi=1 nf=1 %(mos)s
RREF (VBSPD_M VSS) rhim l=38u w=450n multi=1
MCS (VRAMP VBSPD_M VDD VDD) pch_svt_mac l=16n nfin=2 w=58n multi=1 nf=1 %(mos)s
MSMP (VRAMP CK_SMP VHOLD VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=8 %(mos)s
MRST (VRAMP CK_RST VSS VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=32 %(mos)s
CH (VHOLD VSS VSS) cfmom_wo_p80 dmflag=0 lr=1u multi=1 mxd_flag=0 nr=12 \
        n_mxa=2 shield=2 spm=3 stm=1 vapmod=2 grflag=1 gdis_t=185n \
        gdis_b=185n gdis_l=102n gdis_r=102n
CR0 (VRAMP VSS) capacitor c=30f
ends spd_x""" % {"mos": MOS_TAIL.replace("\\n", " ").replace("sd=74n", "sd=74n")}




def gen_vco_dual_8g(out: Path = INC / "vco_dual_8g.scs") -> None:
    """8-GHz VCO variant: same cores, inductors 2.49n -> 1.5n (f scales 1/sqrt(L): 6.2G -> 8.0G)."""
    base = BASE.read_text()
    vco = extract_subckt(base, "vco_x")
    vco = vco.replace("inductor l=2.49n r=2", "inductor l=1.5n r=2")
    L = []
    L.append("// vco_dual_8g.scs — 8GHz dual-core VCO (L=1.5n), generated for step2")
    L.append("")
    L.append(vco)
    L.append("")
    L.append("subckt vco_dual_8g (VDD VSS VCTRL OUTP OUTN EN2)")
    L.append(f"MNEN (EN2B EN2 VSS VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=2 {MOS_TAIL}")
    L.append(f"MPEN (EN2B EN2 VDD VDD) pch_svt_mac l=16n nfin=2 w=58n multi=1 nf=2 {MOS_TAIL}")
    L.append(f"MPWRB (VDDB EN2B VDD VDD) pch_svt_mac l=16n nfin=2 w=58n multi=1 nf=64 {MOS_TAIL}")
    L.append(f"MSWP (OUTP EN2 OUTPB VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=64 {MOS_TAIL}")
    L.append(f"MSWN (OUTN EN2 OUTNB VSS) nch_svt_mac l=16n nfin=2 w=58n multi=1 nf=64 {MOS_TAIL}")
    L.append("Xa (VDD VSS VCTRL OUTP OUTN) vco_x")
    L.append("Xb (VDDB VSS VCTRL OUTPB OUTNB) vco_x")
    L.append("ends vco_dual_8g")
    L.append("")
    out.write_text("\n".join(L))
    print(f"wrote {out}")


if __name__ == "__main__":
    gen_dtc_10b()
    gen_decoder_10b()
    gen_vco_dual()
    gen_vco_dual_8g()
    gen_analog_blocks()
