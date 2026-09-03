#!/usr/bin/env python3
"""TX driver Ron Monte Carlo: 200 enumerated single-run DC jobs (same
fallback as run_tran_mc_offset.py: the mc1 psfascii layout is not bridge-
parseable). Each job: mc1 numruns=1 with its own seed -> normal dc parse."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NET_DIR, OUT_DIR, TRAN_DIR, make_sim, save_json, write_baked

TPL = NET_DIR / "tb_afe_txron_mc.scs"
INC = [str(TRAN_DIR / "afe_tx_drv.scs")]
NSEEDS = 200


def main():
    tasks = []
    for seed in range(1, NSEEDS + 1):
        # NRUNS/SEED placeholders: reuse the cmp MC template style
        from common import bake
        txt = TPL.read_text()
        txt = bake(txt, NRUNS=1, SEED=seed)
        net = OUT_DIR / f"mcron_{seed}.scs"
        net.write_text(txt)
        tasks.append((net, seed))

    sim = make_sim(timeout=3600)
    results = sim.run_parallel(
        [(n, {"include_files": INC}) for n, _ in tasks], max_workers=4)

    ron_pu, ron_pd, nfail = [], [], 0
    for (net, seed), res in zip(tasks, results):
        if not res.ok or not res.data:
            nfail += 1
            continue
        vpu = res.data.get("dc1_pad_pu")
        vpd = res.data.get("dc1_pad_pd")
        if vpu is None or vpd is None:
            nfail += 1
            continue
        ron_pu.append((0.45 - float(vpu)) / 2e-3)
        ron_pd.append(float(vpd) / 2e-3)

    out = {
        "n_runs": len(ron_pu),
        "n_failed": nfail,
        "ron_pu_mean": float(np.mean(ron_pu)) if ron_pu else None,
        "ron_pu_std": float(np.std(ron_pu)) if ron_pu else None,
        "ron_pd_mean": float(np.mean(ron_pd)) if ron_pd else None,
        "ron_pd_std": float(np.std(ron_pd)) if ron_pd else None,
        "ron_pu": [float(v) for v in ron_pu],
        "ron_pd": [float(v) for v in ron_pd],
    }
    if ron_pu:
        print(f"n={len(ron_pu)} (fail {nfail})  "
              f"Ron_pu: mean={out['ron_pu_mean']:.1f} std={out['ron_pu_std']:.1f} "
              f"({out['ron_pu_std']/out['ron_pu_mean']*100:.1f}%)")
        print(f"              Ron_pd: mean={out['ron_pd_mean']:.1f} std={out['ron_pd_std']:.1f} "
              f"({out['ron_pd_std']/out['ron_pd_mean']*100:.1f}%)")
    save_json(out, OUT_DIR / "tran_mc_ron.json")


if __name__ == "__main__":
    main()
