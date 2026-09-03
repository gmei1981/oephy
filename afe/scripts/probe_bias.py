#!/usr/bin/env python3
"""Standalone replica-bias DC probe (pitfall 20① in status.md): before any
P5 batch, confirm the bias equilibrium of the CURRENT tran/afe_bias.scs is
the 0.362 V design point. Also serves as an end-to-end tunnel/spectre
smoke test. Usage: probe_bias.py [section] [temp]   (default top_tt 25)"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NET_DIR, OUT_DIR, TRAN_DIR, make_sim, write_baked

MODELS_TT = ('include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" '
             "section={section}")
INC_BIAS = [str(TRAN_DIR / "afe_bias.scs")]
DESIGN_VBIC = 0.362


def main():
    section = sys.argv[1] if len(sys.argv) > 1 else "top_tt"
    temp = sys.argv[2] if len(sys.argv) > 2 else 25
    net = write_baked(NET_DIR / "tb_bias_dc.scs",
                      OUT_DIR / f"biasdc_chk_{section}_{temp}.scs",
                      MODELS=MODELS_TT.format(section=section), TEMP=temp)
    sim = make_sim(timeout=300)
    r = sim.run_simulation(net, {"include_files": INC_BIAS})
    if not r.ok:
        print(f"probe FAILED: {r.errors[:1]}")
        sys.exit(1)
    raw = OUT_DIR / f"biasdc_chk_{section}_{temp}.raw" / "dc1.dc"
    m = re.search(r'"vbias"\s+"V"\s+([-+0-9.eE]+)',
                  raw.read_text()) if raw.exists() else None
    if not m:
        print(f"probe ok but raw unparsable ({raw})")
        sys.exit(1)
    vbic = float(m.group(1))
    tag = "OK" if abs(vbic - DESIGN_VBIC) < 0.01 else "MISMATCH"
    print(f"[{section}@{temp}] vbias = {vbic:.4f} V "
          f"(design {DESIGN_VBIC}) -> {tag}")
    sys.exit(0 if tag == "OK" else 2)


if __name__ == "__main__":
    main()
