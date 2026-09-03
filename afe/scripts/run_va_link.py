#!/usr/bin/env python3
"""Single nominal link run of the VerilogA AFE prototype at 16 Gb/s.

Runs the end-to-end TB at the eye-center point (vref=128, pi=0.5),
reports BER and dumps key waveforms to output/va_link.json.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import AFE, NET_DIR, OUT_DIR, VA_FILES, final_value, make_sim, save_json, write_baked

TPL = NET_DIR / "tb_afe_va.scs"


def main():
    net = write_baked(TPL, OUT_DIR / "tb_afe_va_link.scs",
                      VC=128, PC=0.15, VOSA=0.004, VOSB=-0.003, AZR=0.05, NS=2, STOP=60e-9)
    sim = make_sim(timeout=1800)
    result = sim.run_simulation(
        net,
        {"include_files": VA_FILES},
    )
    print("ok:", result.ok)
    if not result.ok:
        print("errors:", result.errors)
        sys.exit(1)
    print("timings:", result.metadata.get("timings"))

    errs = final_value(result, "err_cnt")
    bits = final_value(result, "bit_cnt")
    lock = final_value(result, "lock")
    ber = (errs / bits) if bits else None
    print(f"err_cnt={errs} bit_cnt={bits} lock={lock} BER={ber}")

    out = {
        "ber": ber,
        "err_cnt": errs,
        "bit_cnt": bits,
        "lock": lock,
        "timings": result.metadata.get("timings"),
        "signals": {k: list(v) if hasattr(v, "__len__") else v
                    for k, v in result.data.items()},
    }
    save_json(out, OUT_DIR / "va_link.json")


if __name__ == "__main__":
    main()
