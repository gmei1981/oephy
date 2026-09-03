#!/usr/bin/env python3
"""RX eye scan of the VerilogA AFE prototype (paper: Fig. 36.3.4 method).

Sweeps Vref DAC code x sampler PI phase, counts PRBS23 errors per point
(BER resolution ~1e-3 with 60 ns runs), writes output/va_eye.json.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import AFE, NET_DIR, OUT_DIR, VA_FILES, final_value, make_sim, save_json, write_baked

TPL = NET_DIR / "tb_afe_va.scs"

VREF_CODES = [int(round(c)) for c in [i * (255.0 / 12.0) for i in range(13)]]  # 13 pts, 0..255
PI_CODES = [i / 8.0 for i in range(9)]  # 9 points, 0..1 UI

VFS = 0.45  # Vref DAC full-scale


def main():
    tasks = []
    tpl = TPL.read_text()
    for vc in VREF_CODES:
        for pc in PI_CODES:
            net = write_baked(TPL, OUT_DIR / f"eye_tmp_v{vc}_p{int(pc * 1000)}.scs",
                              VC=vc, PC=pc, VOSA=0.004, VOSB=-0.003, AZR=0.05, NS=2, STOP=80e-9)
            tasks.append((net, vc, pc))

    sim = make_sim(timeout=1800)
    results = sim.run_parallel(
        [(n, {"include_files": VA_FILES}) for n, _, _ in tasks],
        max_workers=8,
    )

    grid = []
    nfail = 0
    for (net, vc, pc), res in zip(tasks, results):
        if not res.ok:
            nfail += 1
            grid.append({"vref_code": vc, "vref_v": vc / 255.0 * VFS, "pi_ui": pc,
                         "ber": None, "errs": None, "bits": None,
                         "errors": res.errors[:3] if res.errors else []})
            continue
        errs = final_value(res, "err_cnt")
        bits = final_value(res, "bit_cnt")
        ber = (errs / bits) if bits else None
        grid.append({"vref_code": vc, "vref_v": vc / 255.0 * VFS, "pi_ui": pc,
                     "ber": ber, "errs": errs, "bits": bits})

    print(f"done: {len(grid)} points, {nfail} failed")
    save_json({"points": grid, "vref_codes": VREF_CODES, "pi_codes": PI_CODES},
              OUT_DIR / "va_eye.json")


if __name__ == "__main__":
    main()
