#!/usr/bin/env python3
"""AZ comparator residual offset Monte Carlo: 200 enumerated single-run jobs
x (AZ on / AZ off).

Spectre's mc1 psfascii layout was not parseable by the bridge (the MC parent
writes one merged tran file whose per-run sweeps the bridge does not read),
so each run is a separate mc1 job (numruns=1, own seed) producing a normal
tran.tran.tran — the established parse path.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NET_DIR, OUT_DIR, TRAN_DIR, final_value, make_sim, save_json, write_baked

TPL = NET_DIR / "tb_afe_cmp_mc.scs"
INC = [str(TRAN_DIR / "afecmp_bank.scs"), str(TRAN_DIR / "afe_bias.scs")]

VREF = 0.225
NSEEDS = 200


def trip_voltage(data):
    """Input voltage at the (outp-outn) zero crossing after t=2ns."""
    t = np.array(data["time"])
    d = np.array(data["outp"]) - np.array(data["outn"])
    vin = np.array(data["vin"])
    sel = np.where(t > 2e-9)[0]
    if len(sel) == 0:
        return None
    s = np.sign(d[sel])
    cross = np.where(s[1:] != s[:-1])[0]
    if len(cross) == 0:
        return None
    i = sel[cross[0]]
    if i + 1 >= len(d):
        return float(vin[i])
    if d[i + 1] == d[i]:
        return float(vin[i])
    f = (0.0 - d[i]) / (d[i + 1] - d[i])
    return float(vin[i] + f * (vin[i + 1] - vin[i]))


def main():
    # NOTE: this AZ architecture cancels SLOW DRIFT (periodic re-anchor of the
    # floating gates), NOT static VT mismatch — the gates are pinned to vbias
    # during AZ and the pair offset is never sensed/stored. The measured
    # "az_on" residual is therefore the comparator's static input-referred
    # offset, which the per-lane vref training absorbs (measured: mean -2 mV,
    # std 25 mV; 6-sigma 148 mV < eye window 176 mV). The "az_off" case is
    # not well-defined for a cap-coupled input (its threshold is the pA
    # initial value, not vref) and is not measured.
    out = {"n_seeds": NSEEDS, "n_runs": {}, "vos_mean": {}, "vos_std": {}, "vos": {}}
    sim = make_sim(timeout=3600)

    for az_en in (True,):
        label = "az_on" if az_en else "az_off"
        tasks = []
        for seed in range(1, NSEEDS + 1):
            net = write_baked(TPL, OUT_DIR / f"mc_{label}_{seed}.scs",
                              AZEN=0.8, NRUNS=1, SEED=seed,
                              EVALD=1.6e-9, PANODESET=0.225)
            tasks.append((net, seed))

        print(f"MC {label}: {NSEEDS} runs ...")
        results = sim.run_parallel(
            [(n, {"include_files": INC}) for n, _ in tasks], max_workers=4)
        vos, nfail = [], 0
        for (net, seed), res in zip(tasks, results):
            if not res.ok or not res.data:
                nfail += 1
                continue
            v = trip_voltage(res.data)
            if v is not None:
                vos.append(v - VREF)
        arr = np.array(vos)
        out["n_runs"][label] = len(vos)
        out["vos_mean"][label] = float(arr.mean()) if len(arr) else None
        out["vos_std"][label] = float(arr.std()) if len(arr) else None
        out["vos"][label] = [float(v) for v in vos]
        print(f"  {label}: trips={len(vos)}/{NSEEDS} (fail {nfail})  "
              f"mean={arr.mean()*1000:.2f} mV  std={arr.std()*1000:.2f} mV")

    save_json(out, OUT_DIR / "tran_mc_offset.json")
    a, b = out["vos_std"].get("az_off"), out["vos_std"].get("az_on")
    if a and b:
        print(f"\nAZ suppression: {a*1000:.1f} mV -> {b*1000:.1f} mV ({a/b:.1f}x)")


if __name__ == "__main__":
    main()
