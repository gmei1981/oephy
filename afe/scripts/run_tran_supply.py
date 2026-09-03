#!/usr/bin/env python3
"""Supply integrity: injected VDD sine noise sweep (ampl x freq) with the
package model, plus bond-wire inductance sweep at zero injection (the 1 nH
case oscillates — documented PDN instability)."""
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
    tasks = []
    # injection sweep at quiet-package LS
    for ampl in (0.0, 20e-3, 50e-3, 100e-3):
        for fn in (100e6, 400e6):
            net = write_baked(TPL, OUT_DIR / f"sup_a{int(ampl*1e3)}m_f{int(fn/1e6)}m.scs",
                              VC=142, PC=0.875, AZEN=1, DRIFT=0, NS=2, STOP=40e-9,
                              VREFV=142 / 255 * VFS, MODELS=MODELS_TT, TEMP=25,
                              RS=0.5, LS=0.01e-9, AMPL=ampl, FN=fn, NFDIO=100,
                              VBIC=0.362, NOISE_OPTS="")
            tasks.append((net, f"inj_{ampl*1e3:.0f}m@{fn/1e6:.0f}M"))
    # bond-wire inductance sweep, no injection
    for ls in (0.1e-9, 1e-9):
        net = write_baked(TPL, OUT_DIR / f"sup_ls{int(ls*1e9)}n.scs",
                          VC=142, PC=0.875, AZEN=1, DRIFT=0, NS=2, STOP=40e-9,
                          VREFV=142 / 255 * VFS, MODELS=MODELS_TT, TEMP=25,
                          RS=0.5, LS=ls, AMPL=0, FN=100e6, NFDIO=100,
                          VBIC=0.362, NOISE_OPTS="")
        tasks.append((net, f"ls_{ls*1e9:.1f}n"))

    sim = make_sim(timeout=1800)
    results = sim.run_parallel(
        [(n, {"include_files": INC}) for n, _ in tasks], max_workers=4)

    rows = []
    for (net, label), res in zip(tasks, results):
        if not res.ok:
            rows.append({"case": label, "ok": False, "errors": res.errors[:2]})
            print(f"{label:12s}: FAILED {res.errors[:1]}")
            continue
        errs = final_value(res, "err_cnt")
        bits = final_value(res, "bit_cnt")
        ber = (errs / bits) if bits else None
        import numpy as np
        vss = np.array(res.data["vss"])
        m = np.array(res.data["time"]) > 5e-9
        rows.append({"case": label, "ok": True, "ber": ber, "errs": errs,
                     "bits": bits, "vss_pk": float(np.abs(vss[m]).max())})
        print(f"{label:12s}: errs={errs:.0f} BER={ber} vss_pk={rows[-1]['vss_pk']:.3f}")

    save_json({"points": rows}, OUT_DIR / "tran_supply.json")


if __name__ == "__main__":
    main()
