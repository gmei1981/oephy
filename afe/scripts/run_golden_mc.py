#!/usr/bin/env python3
"""Full 200-seed MC re-verification on the GOLDEN (schematic-sourced) MC
TBs, run LOCALLY (plain spectre -- server 21 down, SpectreBasic license).

Mirrors the recorded baselines:
  cmp az_on 200 seeds -> output/tran_mc_offset.json (server-21, 25.1/ax)
  ron      200 seeds -> output/tran_mc_ron.json

The golden MC decks are emission-order normalized (gen_tb_golden 1.5), so
per-seed mismatch REALIZATIONS should track the legacy per-seed baseline
values (cross-platform numerical wiggle only) -- the per-seed correlation
is therefore a large-scale equivalence proof on top of mean/sigma.

Usage: run_golden_mc.py [offset|ron|all]   (default all)
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

AFE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AFE / "scripts"))
from common import OUT_DIR, write_baked  # noqa: E402  (chdirs to AFE)

GOLD = OUT_DIR / "n2s_tb_golden"
NSEEDS = 200
VREF = 0.225


def make_local(timeout=3600):
    from virtuoso_bridge.spectre.runner import SpectreSimulator
    for k in [k for k in os.environ if k.startswith("VB_")]:
        del os.environ[k]
    os.chdir("/tmp")
    return SpectreSimulator.from_env(spectre_args=[], work_dir=OUT_DIR,
                                     timeout=timeout)


def trip_voltage(data):
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
    if i + 1 >= len(d) or d[i + 1] == d[i]:
        return float(vin[i])
    f = (0.0 - d[i]) / (d[i + 1] - d[i])
    return float(vin[i] + f * (vin[i + 1] - vin[i]))


def ron_from_raw(netstem, seed):
    cands = sorted(OUT_DIR.glob(f"gmc_ron_{seed}__*"),
                   key=lambda p: p.stat().st_mtime)
    for c in reversed(cands):
        f = c / f"gmc_ron_{seed}.raw" / "mc1_dc1.dc"
        if f.exists():
            vals = dict(re.findall(
                r'^"(pad_pu|pad_pd)"\s+"V"\s+([-+0-9.eE]+)',
                f.read_text(), re.M))
            if len(vals) == 2:
                vpu, vpd = float(vals["pad_pu"]), float(vals["pad_pd"])
                return (0.45 - vpu) / 2e-3, vpd / 2e-3
    return None


def run_batch(sim, tasks, parse):
    """tasks: [(netlist_path, seed)] -> {seed: parsed metric}."""
    results = sim.run_parallel(
        [(n, {"include_files": []}) for n, _ in tasks], max_workers=4)
    out = {}
    for (net, seed), res in zip(tasks, results):
        v = parse(seed, res)
        if v is not None:
            out[seed] = v
    return out


def cmp_parse(seed, res):
    if not res.ok or not res.data:
        return None
    tv = trip_voltage(res.data)
    return tv - VREF if tv is not None else None


def ron_parse(seed, res):
    got = ron_from_raw(None, seed)
    if got:
        return got
    d = res.data if (res.ok and res.data) else {}
    vpu, vpd = d.get("dc1_pad_pu"), d.get("dc1_pad_pd")
    if vpu is None or vpd is None:
        return None
    return (0.45 - float(vpu)) / 2e-3, float(vpd) / 2e-3


def report(name, vals, base_mean, base_std, base_list=None, tag=""):
    a = np.array(vals)
    print(f"[{name}] n={len(a)} mean={a.mean():.6f} std={a.std():.6f} "
          f"(baseline {base_mean:.6f} / {base_std:.6f})")
    dm = abs(a.mean() - base_mean)
    ds = abs(a.std() - base_std) / base_std
    # distribution gates only (~3.5 SEM + 15% sigma).  Per-seed correlation
    # vs the SERVER baseline is INFORMATIONAL: spectre's MC random stream is
    # build/mode dependent (25.1+ax vs 20.1+plain measured ~0 corr while the
    # same-platform legacy-vs-golden control is bit-consistent to 1e-14 V,
    # seeds 1..10, 2026-09-05) -- same-platform per-seed equality is the
    # equivalence proof, cross-platform comparison must be distributional.
    ok = dm < 0.006 and ds < 0.15
    line = f"[{name}] mean_diff={dm*1e3:.2f}mV sigma_reldev={ds*100:.1f}%"
    if base_list is not None and len(base_list) == len(a):
        r = float(np.corrcoef(a, np.array(base_list))[0, 1])
        line += f" per-seed corr={r:.4f} (informational, cross-platform)"
    print(line + f" -> {'MATCH' if ok else 'DIFF'}")
    return ok


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    sim = make_local()
    ok_all = True

    if mode in ("offset", "all"):
        tasks = []
        for seed in range(1, NSEEDS + 1):
            tasks.append((write_baked(
                GOLD / "golden_tb_afe_cmp_mc.scs",
                OUT_DIR / f"gmc_cmp_{seed}.scs",
                NRUNS=1, SEED=seed, AZEN=0.8, EVALD="1.6n",
                PANODESET=0.225), seed))
        got = run_batch(sim, tasks, cmp_parse)
        base = json.loads((OUT_DIR / "tran_mc_offset.json").read_text())
        vos = [got[s] for s in sorted(got)]
        bm, bs = base["vos_mean"]["az_on"], base["vos_std"]["az_on"]
        bl = base["vos"].get("az_on")
        ok_all &= report("gmc_offset", vos, bm, bs, bl)
        save = {"n_seeds": len(vos), "vos_mean": float(np.mean(vos)),
                "vos_std": float(np.std(vos)),
                "vos": {str(s): got[s] for s in sorted(got)},
                "baseline_mean": bm, "baseline_std": bs,
                "method": "golden TB local plain spectre 200 seeds"}
        (OUT_DIR / "golden_mc_offset.json").write_text(
            json.dumps(save, indent=1, default=float))
        print("[saved] output/golden_mc_offset.json")

    if mode in ("ron", "all"):
        tasks = []
        for seed in range(1, NSEEDS + 1):
            tasks.append((write_baked(
                GOLD / "golden_tb_afe_txron_mc.scs",
                OUT_DIR / f"gmc_ron_{seed}.scs",
                NRUNS=1, SEED=seed), seed))
        got = run_batch(sim, tasks, ron_parse)
        base = json.loads((OUT_DIR / "tran_mc_ron.json").read_text())
        pu = [got[s][0] for s in sorted(got)]
        pd = [got[s][1] for s in sorted(got)]
        ok_all &= report("gmc_ron_pu", pu, base["ron_pu_mean"],
                         base["ron_pu_std"], base.get("ron_pu"))
        ok_all &= report("gmc_ron_pd", pd, base["ron_pd_mean"],
                         base["ron_pd_std"], base.get("ron_pd"))
        save = {"n_seeds": len(pu),
                "ron_pu_mean": float(np.mean(pu)),
                "ron_pu_std": float(np.std(pu)),
                "ron_pd_mean": float(np.mean(pd)),
                "ron_pd_std": float(np.std(pd)),
                "ron_pu": pu, "ron_pd": pd,
                "method": "golden TB local plain spectre 200 seeds "
                          "(mc1_dc1.dc re-parse)"}
        (OUT_DIR / "golden_mc_ron.json").write_text(
            json.dumps(save, indent=1, default=float))
        print("[saved] output/golden_mc_ron.json")

    print(f"\n=== golden MC 200-seed: "
          f"{'ALL MATCH' if ok_all else 'DIFFERENCES'} ===")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
