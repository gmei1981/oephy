#!/usr/bin/env python3
"""tranNoise verification: smoke probe (is device noise actually on?) then
link runs with noise=yes at the eye center."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NET_DIR, OUT_DIR, TRAN_DIR, VA_FILES, final_value, make_sim, save_json, write_baked

TPL = NET_DIR / "tb_afe_tran.scs"
TPL_SMOKE = NET_DIR / "tb_noise_smoke.scs"
INC = VA_FILES + [str(TRAN_DIR / f) for f in
                  ("afecmp_bank.scs", "afe_tx_drv.scs", "afe_sampler.scs",
                   "afe_bias.scs", "afe_dac_r2r.scs", "afe_esd.scs")]
INC_SMOKE = []
MODELS_TT = ('include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" '
             "section=top_tt")
NOISE_ON = "noise=yes noisefmax=64G"
VFS = 0.45


def std_of(res, sig="out"):
    if not res.ok or not res.data:
        return None
    w = np.array(res.data[sig])
    t = np.array(res.data["time"])
    m = t > 10e-9
    return float(w[m].std())


def main():
    sim = make_sim(timeout=1800)
    out = {}

    # smoke probe
    stds = {}
    for label, opts in (("off", ""), ("on", NOISE_ON)):
        net = write_baked(TPL_SMOKE, OUT_DIR / f"nsmoke_{label}.scs", NOISE_OPTS=opts)
        r = sim.run_simulation(net, {"include_files": INC_SMOKE})
        stds[label] = std_of(r)
        print(f"smoke noise {label}: std={stds[label] if stds[label] is not None else 'FAIL'}")
    out["smoke_std"] = stds
    if stds["on"] and stds["off"] and stds["on"] / max(stds["off"], 1e-12) < 2:
        print("WARNING: device noise looks OFF (on/off std ratio < 2) — "
              "check fnoise include order")

    # link runs at the eye center
    for label, opts in (("off", ""), ("on_1", NOISE_ON), ("on_2", NOISE_ON)):
        net = write_baked(TPL, OUT_DIR / f"noise_link_{label}.scs",
                          VC=142, PC=0.875, AZEN=1, DRIFT=0, NS=2, STOP=40e-9,
                          VREFV=142 / 255 * VFS, MODELS=MODELS_TT, TEMP=25,
                          RS=0.5, LS=0.01e-9, AMPL=0, FN=100e6, NFDIO=100,
                          VBIC=0.362, NOISE_OPTS=opts)
        r = sim.run_simulation(net, {"include_files": INC})
        if not r.ok:
            print(f"link noise {label}: FAILED {r.errors[:1]}")
            continue
        errs = final_value(r, "err_cnt")
        bits = final_value(r, "bit_cnt")
        ber = (errs / bits) if bits else None
        out[label] = {"ber": ber, "errs": errs, "bits": bits}
        print(f"link noise {label}: errs={errs} bits={bits} BER={ber}")

    save_json(out, OUT_DIR / "tran_noise.json")


if __name__ == "__main__":
    main()
