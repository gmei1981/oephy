import shutil
from pathlib import Path

ROOT = Path("/home/gmei/git/oephy/adpll_ted")
HEADER = """// smoke_tb_top — schematic top-level (tb_adpll_top si export), step2 config
// equivalence smoke vs sim/pll_step2_main.scs (reference flat deck)
simulator lang=spectre

include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt
ahdl_include "pll_mmd_edge.va"
ahdl_include "pll_lms.va"
ahdl_include "pll_dtc_decoder_10b.va"
ahdl_include "pll_hybrid_aux.va"
"""
FOOTER = """
plltran tran stop=300n maxstep=2p errpreset=liberal method=gear2only skipdc=yes ic="OUTP=0.6"
save Xpll.OUTP Xpll.CKFB Xpll.VCTRL Xpll.VI Xpll.VHOLD Xpll.EBIT Xpll.MMDIN Xpll.NBUF1 Xpll.VREF Xpll.VDCC Xpll.RDCC Xpll.KDTC Xpll.VRAMP Xpll.SEL Xpll.EPSC Xpll.CK2X Xpll.CKDTCD Xpll.CKRST
saveOptions options save=selected
"""

body = (ROOT / "tools" / "tb_adpll_top_sch_netlist.scs").read_text()
(ROOT / "sim" / "run_smoke_tb_top.scs").write_text(HEADER + body + FOOTER)
print("wrote sim/run_smoke_tb_top.scs")

# reference deck: ALWAYS from the current pll_step2_main.scs (never the
# stale sim/step2/smoke/top.scs staging — pre-方案A' 1027-port Xdtc)
ref = (ROOT / "sim" / "pll_step2_main.scs").read_text().rstrip()
ref += "\nsaveOptions options save=selected\n"
(ROOT / "sim" / "run_smoke_ref.scs").write_text(ref)
print("wrote sim/run_smoke_ref.scs (from pll_step2_main.scs)")
