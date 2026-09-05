#!/usr/bin/env python3
"""A/B equivalence runs: legacy netlists/*.scs templates vs the schematic-
sourced golden TB netlists (output/n2s_tb_golden/golden_*.scs).

For each case both decks get identical bakes on the same platform
(server-21 spectre via common.make_sim); results compared against the
recorded baselines.  Golden decks are self-contained (exported subckt defs
replace the legacy include files).

Usage: run_tb_ab.py [bias|noise|dac|txron|cmp|all]
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (NET_DIR, OUT_DIR, TRAN_DIR, bake, make_sim,
                    save_json, write_baked)


def make_sim_local(timeout=3600):
    """Server-21 tunnel down -> local spectre 20.1 via the user-level
    bridge env (localhost).  A/B equivalence only needs both decks on the
    SAME platform; DC values are platform-independent anyway."""
    from virtuoso_bridge.spectre.runner import (
        SpectreSimulator,
        spectre_mode_args,
    )
    # common.py's import-time load_dotenv(afe/.env, override=True) injected
    # the server-21 VB_* vars into os.environ -- purge them, or from_env
    # keeps targeting the remote spectre path
    for k in [k for k in os.environ if k.startswith("VB_")]:
        del os.environ[k]
    os.chdir("/tmp")  # neutral cwd so from_env picks ~/.virtuoso-bridge/.env
    # plain mode: the local license file has SpectreBasic only (the full
    # "Spectre" seat rides on the network server, currently down); +preset=ax
    # stalls at "Waiting for available license". Both A/B decks share the
    # mode, so equivalence is unaffected.
    return SpectreSimulator.from_env(
        spectre_args=[],
        work_dir=OUT_DIR, timeout=timeout)

GOLD = OUT_DIR / "n2s_tb_golden"
MODELS_TT = ('include "/home/lib/tsmc_12nm_installed/pdk/models/'
             'toplevel.scs" section=top_tt')
NOISE_ON = "noise=yes noisefmax=64G"
VFS = 0.45

# case name -> (legacy_tpl, golden_tpl, bake kwargs, legacy includes)
CASES = {}


def case(name, cell, **bakekw):
    inc = {"tb_bias_dc": [str(TRAN_DIR / "afe_bias.scs")],
           "tb_afe_dac_dc": [str(TRAN_DIR / "afe_dac_r2r.scs")],
           "tb_afe_txron_mc": [str(TRAN_DIR / "afe_tx_drv.scs")],
           "tb_afe_cmp_mc": [str(TRAN_DIR / "afecmp_bank.scs"),
                             str(TRAN_DIR / "afe_bias.scs")],
           "tb_noise_smoke": [],
           "tb_sa_test": [str(TRAN_DIR / "afe_sampler.scs")],
           "tb_afe_va": None}[cell]  # None -> VA_FILES for both sides
    CASES[name] = (NET_DIR / f"{cell}.scs", GOLD / f"golden_{cell}.scs",
                   bakekw, inc)


case("bias_tt25", "tb_bias_dc", MODELS=MODELS_TT, TEMP=25)
case("noise_off", "tb_noise_smoke", NOISE_OPTS="")
case("noise_on", "tb_noise_smoke", NOISE_OPTS=NOISE_ON)
for code in (0, 128, 255):
    bits = {f"B{k}": (0.8 if (code >> k) & 1 else 0.0) for k in range(8)}
    case(f"dac_c{code}", "tb_afe_dac_dc", **bits)
case("txron_s1", "tb_afe_txron_mc", NRUNS=1, SEED=1)
case("cmp_on_s1", "tb_afe_cmp_mc", NRUNS=1, SEED=1, AZEN=0.8,
     EVALD="1.6n", PANODESET=0.225)
case("cmp_off_s1", "tb_afe_cmp_mc", NRUNS=1, SEED=1, AZEN=0,
     EVALD=0, PANODESET=0.10)
case("sa_test", "tb_sa_test")  # fixed stimulus, no placeholders
case("va_proto", "tb_afe_va", VC=142, PC=0.875, VOSA=0.004, VOSB=-0.003,
     AZR=0.05, NS=3, STOP=40e-9)


def trip_voltage(data):
    t = np.array(data["time"])
    d = np.array(data["outp"]) - np.array(data["outn"])
    vin = np.array(data["vin"])
    sel = np.where(t > 2e-9)[0]
    s = np.sign(d[sel])
    cross = np.where(s[1:] != s[:-1])[0]
    if len(cross) == 0:
        return None
    i = sel[cross[0]]
    if i + 1 >= len(d) or d[i + 1] == d[i]:
        return float(vin[i])
    f = (0.0 - d[i]) / (d[i + 1] - d[i])
    return float(vin[i] + f * (vin[i + 1] - vin[i]))


def metric(name, res):
    """Single scalar per case for the A/B compare."""
    if not res.ok or not res.data:
        return None
    d = res.data
    if name.startswith("bias"):
        return float(d["dc1_vbias"]) if "dc1_vbias" in d else None
    if name.startswith("noise"):
        t = np.array(d["time"])
        return float(np.array(d["out"])[t > 10e-9].std())
    if name.startswith("dac"):
        return float(d["dc1_vref"]) if "dc1_vref" in d else None
    if name.startswith("txron"):
        vpu, vpd = d.get("dc1_pad_pu"), d.get("dc1_pad_pd")
        if vpu is None or vpd is None:
            return None
        return (round((0.45 - float(vpu)) / 2e-3, 6),
                round(float(vpd) / 2e-3, 6))
    if name.startswith("cmp"):
        tv = trip_voltage(d)
        return tv if tv is not None else "nocross"  # az_off may not cross
    if name == "sa_test":
        return (round(float(np.array(d["qp"])[-1]), 9),
                round(float(np.array(d["qn"])[-1]), 9))
    if name == "va_proto":
        keys = ("err_cnt", "bit_cnt", "lock")
        if any(k not in d for k in keys):
            return None
        return tuple(round(float(np.array(d[k])[-1]), 6) for k in keys)
    return None


def ron_from_raw(name, side):
    """mc1-wrapped DC never reaches res.data (pitfall 16-3) -- re-parse
    pad_pu/pad_pd from the runner's newest raw dir."""
    import re as _re
    cands = sorted(OUT_DIR.glob(f"ab_{name}_{side}__*"),
                   key=lambda p: p.stat().st_mtime)
    for c in reversed(cands):
        f = c / f"ab_{name}_{side}.raw" / "mc1_dc1.dc"
        if f.exists():
            vals = dict(_re.findall(
                r'^"(pad_pu|pad_pd)"\s+"V"\s+([-+0-9.eE]+)',
                f.read_text(), _re.M))
            if len(vals) == 2:
                vpu, vpd = float(vals["pad_pu"]), float(vals["pad_pd"])
                return (round((0.45 - vpu) / 2e-3, 6),
                        round(vpd / 2e-3, 6))
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    local = "--local" in sys.argv
    which = args[0] if args else "all"
    names = list(CASES) if which == "all" else [which]
    sim = make_sim_local() if local else make_sim(timeout=3600)
    out = {}
    for name in names:
        tpl, gold, kw, inc = CASES[name]
        if inc is None:  # VA prototype: both decks ahdl_include the .va
            from common import VA_FILES
            inc = VA_FILES
        # golden decks are self-contained EXCEPT the VA prototype (its
        # header keeps the legacy relative ahdl_include lines)
        gld_inc = inc if name == "va_proto" else []
        jobs = [(write_baked(tpl, OUT_DIR / f"ab_{name}_leg.scs", **kw),
                 {"include_files": inc}),
                (write_baked(gold, OUT_DIR / f"ab_{name}_gld.scs", **kw),
                 {"include_files": gld_inc})]
        rleg, rgld = sim.run_parallel(jobs, max_workers=2)
        mleg, mgld = metric(name, rleg), metric(name, rgld)
        if name.startswith("txron"):  # mc1-DC: local raw re-parse fallback
            mleg = mleg if mleg else ron_from_raw(name, "leg")
            mgld = mgld if mgld else ron_from_raw(name, "gld")
        if isinstance(mleg, str):  # cmp "nocross" sentinel
            close = mleg == mgld
            detail = f"leg={mleg} gld={mgld}"
        elif isinstance(mleg, tuple):  # txron pair
            close = (mleg and mgld and
                     abs(mleg[0] - mgld[0]) < 1e-3 and
                     abs(mleg[1] - mgld[1]) < 1e-3)
            detail = f"leg={mleg} gld={mgld}"
        elif mleg is None or mgld is None:
            close, detail = False, f"leg={mleg} gld={mgld} " \
                f"err={(rleg.errors or rgld.errors or [])[:1]}"
        elif name == "noise_on":  # stochastic: same magnitude
            close = 0.5 < mleg / max(mgld, 1e-15) < 2
            detail = f"leg={mleg:.4f} gld={mgld:.4f} ratio={mleg/mgld:.3f}"
        else:
            denom = max(abs(mleg), 1e-12)
            close = abs(mleg - mgld) / denom < 1e-6
            detail = (f"leg={mleg:.9f} gld={mgld:.9f} "
                      f"reldiff={abs(mleg-mgld)/denom:.2e}")
        print(f"[{name}] {'MATCH' if close else 'DIFF '} {detail}")
        out[name] = {"legacy": mleg, "golden": mgld, "match": bool(close)}
        time.sleep(20)  # SSH rate-limit spacing between pairs
    jf = OUT_DIR / "tb_ab.json"
    if jf.exists():  # merge per-case invocations into one record
        try:
            prev = json.loads(jf.read_text())
            prev.update(out)
            out = prev
        except (ValueError, OSError):
            pass
    save_json(out, jf)
    bad = [k for k, v in out.items() if not v["match"]]
    print(f"\n=== A/B: {'ALL MATCH' if not bad else 'DIFF IN ' + str(bad)} ===")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
