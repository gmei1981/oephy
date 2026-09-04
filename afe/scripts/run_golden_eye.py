#!/usr/bin/env python3
"""Golden (schematic-sourced) RX eye scan (Vref code x PI phase)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR, VA_DIR, final_value, make_sim, save_json, write_baked
from run_golden_link import TPL, INC, MODELS_TT, VFS, gold_bake

VREF_CODES = [90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210]
PI_CODES = [0.375, 0.5, 0.625, 0.75, 0.875, 1.0, 0.0625, 0.1875]


def main():
    tasks = []
    for vc in VREF_CODES:
        for pc in PI_CODES:
            net = write_baked(
                TPL, OUT_DIR / f"geye_v{vc}_p{int(pc*1000)}.scs",
                VC=vc, PC=pc, AZEN=1, DRIFT=0, NS=2, STOP=30e-9,
                VREFV=vc / 255 * VFS, MODELS=MODELS_TT, TEMP=25,
                RS=0.5, LS=0.01e-9, AMPL=0, FN=100e6, VBIC=0.362,
                NOISE_OPTS="", **gold_bake(vc, pc))
            tasks.append((net, vc, pc))

    sim = make_sim(timeout=1800)
    results = sim.run_parallel(
        [(n, {"include_files": INC}) for n, _, _ in tasks],
        max_workers=4,
    )

    grid = []
    nfail = 0
    for (net, vc, pc), res in zip(tasks, results):
        if not res.ok:
            nfail += 1
            grid.append({"vref_code": vc, "vref_v": vc / 255.0 * VFS,
                         "pi_ui": pc, "ber": None, "errs": None, "bits": None,
                         "errors": res.errors[:2] if res.errors else []})
            continue
        errs = final_value(res, "err_cnt")
        bits = final_value(res, "bit_cnt")
        grid.append({"vref_code": vc, "vref_v": vc / 255.0 * VFS,
                     "pi_ui": pc, "ber": (errs / bits) if bits else None,
                     "errs": errs, "bits": bits})

    print(f"done: {len(grid)} points, {nfail} failed")
    save_json({"points": grid, "vref_codes": VREF_CODES,
               "pi_codes": PI_CODES, "source": "schematic_golden"},
              OUT_DIR / "golden_eye.json")


if __name__ == "__main__":
    main()
