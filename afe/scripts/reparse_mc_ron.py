#!/usr/bin/env python3
"""Local re-parse of TX driver Ron MC: the 2026-09-02 run simulated all 200
seeds server-side (logStatus mc1 PASS) but bridge extraction returned nothing
(the mc1-wrapped dc analysis `mc1_dc1` never reaches res.data). Raw psfascii
sits in output/mcron_<seed>__<hash>/mcron_<seed>.raw/mc1_dc1.dc — read
pad_pu/pad_pd straight from its VALUE section. No re-simulation."""
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR, save_json

NSEEDS = 200
# Ron test bench: 2 mA forced through each driver against 0.45/0 rails
VDD = 0.45
IFORCE = 2e-3

VAL_RE = re.compile(r'^"(pad_pu|pad_pd)"\s+"V"\s+([-+0-9.eE]+)\s*$',
                    re.MULTILINE)


def parse_dc(path: Path):
    vals = dict(VAL_RE.findall(path.read_text()))
    if len(vals) != 2:
        return None
    return float(vals["pad_pu"]), float(vals["pad_pd"])


def main():
    ron_pu, ron_pd, nfail = [], [], 0
    for seed in range(1, NSEEDS + 1):
        # bridge suffixes each upload dir with a hash; newest wins if several
        cands = sorted(OUT_DIR.glob(f"mcron_{seed}__*"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        raw = next((c / f"mcron_{seed}.raw" / "mc1_dc1.dc" for c in cands
                    if (c / f"mcron_{seed}.raw" / "mc1_dc1.dc").exists()),
                   None)
        got = parse_dc(raw) if raw else None
        if got is None:
            nfail += 1
            continue
        vpu, vpd = got
        ron_pu.append((VDD - vpu) / IFORCE)
        ron_pd.append(vpd / IFORCE)

    out = {
        "n_runs": len(ron_pu),
        "n_failed": nfail,
        "ron_pu_mean": float(np.mean(ron_pu)) if ron_pu else None,
        "ron_pu_std": float(np.std(ron_pu)) if ron_pu else None,
        "ron_pd_mean": float(np.mean(ron_pd)) if ron_pd else None,
        "ron_pd_std": float(np.std(ron_pd)) if ron_pd else None,
        "ron_pu": [float(v) for v in ron_pu],
        "ron_pd": [float(v) for v in ron_pd],
        "method": "local re-parse of output/mcron_*.raw/mc1_dc1.dc "
                  "(server sims 2026-09-02, all mc1 PASS)",
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
