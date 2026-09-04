#!/usr/bin/env python3
"""Golden-flow ss-corner diagnostic: 8-phase pi scan over the baseline
window's vref codes.

The ss eye is phase-shifted in the golden flow (vhi latch artifact:
golden 0.765 vs baseline 0.954 -> tpi +9.7/+22.7 ps at pi 0.375/0.875,
which pushed both corner-scan phases out of the narrow ss eye). This scan
proves the eye still exists and measures its window at the shifted phase.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR, final_value, make_sim, save_json, write_baked
from run_golden_link import TPL, INC, VFS, gold_bake
from run_golden_corners import models_line

VREF_CODES = [90, 100, 110, 120, 130, 140]  # baseline ss window
PI_CODES = [0.0625, 0.1875, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0]
SECTION, TEMP, VBIC = "top_ss", 25, 0.3866


def main():
    tasks = []
    for pc in PI_CODES:
        for vc in VREF_CODES:
            net = write_baked(
                TPL, OUT_DIR / f"gssdiag_v{vc}_p{int(pc*1000)}.scs",
                VC=vc, PC=pc, AZEN=1, DRIFT=0, NS=2, STOP=30e-9,
                VREFV=vc / 255 * VFS, MODELS=models_line(SECTION), TEMP=TEMP,
                RS=0.5, LS=0.01e-9, AMPL=0, FN=100e6, VBIC=VBIC,
                NOISE_OPTS="", **gold_bake(vc, pc))
            tasks.append((net, vc, pc))

    sim = make_sim(timeout=1800)
    results = sim.run_parallel([(n, {"include_files": INC}) for n, _, _ in tasks],
                               max_workers=4)
    grid, nfail = [], 0
    for (net, vc, pc), res in zip(tasks, results):
        if not res.ok:
            nfail += 1
            grid.append({"vref_code": vc, "pi_ui": pc, "ber": None})
            continue
        errs = final_value(res, "err_cnt")
        bits = final_value(res, "bit_cnt")
        grid.append({"vref_code": vc, "pi_ui": pc,
                     "ber": (errs / bits) if bits else None})
    zero = sorted(set(p["vref_code"] for p in grid if p["ber"] == 0))
    pis = sorted(set(p["pi_ui"] for p in grid if p["ber"] == 0))
    print(f"done: {len(grid)} points, {nfail} failed")
    print(f"zero-BER codes: {zero}")
    print(f"zero-BER phases: {pis}")
    save_json({"points": grid, "zero_codes": zero, "zero_pis": pis,
               "section": SECTION, "temp": TEMP, "vbic": VBIC},
              OUT_DIR / "golden_ss_diag.json")


if __name__ == "__main__":
    main()
