#!/usr/bin/env python3
"""Nominal transistor-level AFE link run (hybrid TB, TSMC 12FFC)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NET_DIR, OUT_DIR, TRAN_DIR, VA_FILES, final_value, make_sim, save_json, write_baked

TPL = NET_DIR / "tb_afe_tran.scs"
INC = VA_FILES + [str(TRAN_DIR / f) for f in
                  ("afecmp_bank.scs", "afe_tx_drv.scs", "afe_sampler.scs",
                   "afe_bias.scs", "afe_dac_r2r.scs", "afe_esd.scs")]

MODELS_TT = ('include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" '
             "section=top_tt")
VFS = 0.45


def main():
    net = write_baked(TPL, OUT_DIR / "tb_afe_tran_link.scs",
                      VC=142, PC=0.875, AZEN=1, DRIFT=0, NS=2, STOP=40e-9,
                      VREFV=142 / 255 * VFS, MODELS=MODELS_TT, TEMP=25,
                      RS=0.5, LS=0.01e-9, AMPL=0, FN=100e6, NFDIO=100, VBIC=0.362, NOISE_OPTS="")
    sim = make_sim(timeout=3600)
    result = sim.run_simulation(net, {"include_files": INC})
    print("ok:", result.ok)
    if not result.ok:
        print("errors:", result.errors)
        sys.exit(1)
    print("timings:", result.metadata.get("timings"))

    errs = final_value(result, "err_cnt")
    bits = final_value(result, "bit_cnt")
    lock = final_value(result, "lock")
    ber = (errs / bits) if bits else None

    def mean_pwr(sig):
        wf = result.data.get(sig)
        t = result.data.get("time")
        if wf is None or t is None:
            return None
        if isinstance(wf, float):
            return wf
        ys = [float(v) for v in wf]
        xs = [float(v) for v in t]
        if len(xs) < 2:
            return None
        t0, t1 = xs[0], xs[-1]
        if t1 <= t0:
            return None
        area = sum(0.5 * (ys[i] + ys[i + 1]) * (xs[i + 1] - xs[i])
                   for i in range(len(xs) - 1))
        return area / (t1 - t0)

    out = {
        "ber": ber, "err_cnt": errs, "bit_cnt": bits, "lock": lock,
        "pwr_BA": mean_pwr("Xtb.BA:pwr"),
        "pwr_BB": mean_pwr("Xtb.BB:pwr"),
        "pwr_DRV": mean_pwr("Xtb.DRV:pwr"),
        "timings": result.metadata.get("timings"),
        "signals": {k: list(v) if hasattr(v, "__len__") else v
                    for k, v in result.data.items()},
    }
    print(f"err_cnt={errs} bit_cnt={bits} lock={lock} BER={ber}")
    print(f"power: BA={out['pwr_BA']} BB={out['pwr_BB']} DRV={out['pwr_DRV']} (W)")
    save_json(out, OUT_DIR / "tran_link.json")


if __name__ == "__main__":
    main()
