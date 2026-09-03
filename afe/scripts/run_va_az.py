#!/usr/bin/env python3
"""Autozero (ping-pong drift cancellation) demonstration, VerilogA prototype.

Injects a large comparator offset (200 mV) and compares:
  A) AZ on  (az_resid=0.05 -> residual 10 mV):  link works at nominal Vref
  B) AZ off (az_resid=1.0  -> residual 200 mV): link fails at nominal Vref
  C) no offset baseline:                        link works
  D) AZ off but Vref shifted by +200 mV
     (link-training style static calibration):  link recovers
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NET_DIR, OUT_DIR, VA_FILES, final_value, make_sim, save_json, write_baked

TPL = NET_DIR / "tb_afe_va.scs"
VFS = 0.45

CASES = [
    ("C_baseline",    dict(VC=128, VOSA=0.0,   VOSB=0.0,   AZR=0.05)),
    ("A_az_on_200m",  dict(VC=128, VOSA=0.2,   VOSB=-0.2,  AZR=0.05)),
    ("B_az_off_200m", dict(VC=128, VOSA=0.2,   VOSB=-0.2,  AZR=1.0)),
    ("D_az_off_trim", dict(VC=int(round(128 + 0.2 / VFS * 255)), VOSA=0.2, VOSB=-0.2, AZR=1.0)),
]


def main():
    sim = make_sim(timeout=1800)
    tasks = []
    for name, kv in CASES:
        net = write_baked(TPL, OUT_DIR / f"az_tmp_{name}.scs",
                          PC=0.15, NS=2, STOP=60e-9, **kv)
        tasks.append((name, net))

    results = sim.run_parallel(
        [(n, {"include_files": VA_FILES}) for _, n in tasks],
        max_workers=4,
    )

    rows = []
    for (name, _), res in zip(tasks, results):
        if not res.ok:
            rows.append({"case": name, "ok": False, "errors": res.errors[:3]})
            continue
        errs = final_value(res, "err_cnt")
        bits = final_value(res, "bit_cnt")
        rows.append({"case": name, "ok": True,
                     "errs": errs, "bits": bits,
                     "ber": (errs / bits) if bits else None})
        print(f"{name}: errs={errs} bits={bits} ber={(errs / bits) if bits else None}")

    save_json({"cases": rows}, OUT_DIR / "va_az.json")


if __name__ == "__main__":
    main()
