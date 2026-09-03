#!/usr/bin/env python3
"""Transistor-level AZ demonstration: slow drift with ping-pong AZ on vs off."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NET_DIR, OUT_DIR, TRAN_DIR, VA_FILES, final_value, make_sim, save_json, write_baked

TPL = NET_DIR / "tb_afe_tran.scs"
INC = VA_FILES + [str(TRAN_DIR / "afecmp_bank.scs"), str(TRAN_DIR / "afe_tx_drv.scs")]

# drift slope: 60 uA over 40 ns -> ~60 mV input-referred ramp at 1 mS gm
DRIFT = 2.5e-7   # A (constant: ~4.5 mV/ns -> 360 mV by 80 ns w/o AZ)

CASES = [
    ("az_on",  dict(AZEN=1, DRIFT=DRIFT)),
    ("az_off", dict(AZEN=0, DRIFT=DRIFT)),
]


def main():
    sim = make_sim(timeout=3600)
    tasks = []
    for name, kv in CASES:
        net = write_baked(TPL, OUT_DIR / f"tran_az_{name}.scs",
                          VC=142, PC=0.875, NS=2, STOP=80e-9, **kv)
        tasks.append((name, net))

    results = sim.run_parallel(
        [(n, {"include_files": INC}) for _, n in tasks],
        max_workers=2,
    )

    rows = []
    for (name, _), res in zip(tasks, results):
        if not res.ok:
            rows.append({"case": name, "ok": False, "errors": res.errors[:3]})
            continue
        errs = final_value(res, "err_cnt")
        bits = final_value(res, "bit_cnt")
        rows.append({"case": name, "ok": True, "errs": errs, "bits": bits,
                     "ber": (errs / bits) if bits else None})
        print(f"{name}: errs={errs} bits={bits} ber={(errs / bits) if bits else None}")

    save_json({"cases": rows, "drift_a_per_s": DRIFT}, OUT_DIR / "tran_az.json")


if __name__ == "__main__":
    main()
