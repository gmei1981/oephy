#!/usr/bin/env python3
"""Corner + temperature verification: 5 corners x 25C + tt at -40/125C.

Per config: (0) DC probe of the replica bias -> bake the equilibrium as the
ic start point (the bias settles in ~us, far beyond the tran window);
(1) vref scan at two sampling phases (pi 0.375/0.875, ns=2) — the corner
device speeds shift both the pipeline delay and the eye window, and the
zero-BER union over the two phases is the robust corner metric.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NET_DIR, OUT_DIR, TRAN_DIR, VA_FILES, final_value, make_sim, save_json, write_baked

TPL = NET_DIR / "tb_afe_tran.scs"
TPL_BIAS = NET_DIR / "tb_bias_dc.scs"
INC = VA_FILES + [str(TRAN_DIR / f) for f in
                  ("afecmp_bank.scs", "afe_tx_drv.scs", "afe_sampler.scs",
                   "afe_bias.scs", "afe_dac_r2r.scs", "afe_esd.scs")]
INC_BIAS = [str(TRAN_DIR / "afe_bias.scs")]

VFS = 0.45
VREF_CODES = list(range(90, 220, 10))  # 13 codes
SCAN_PIS = [0.375, 0.875]
NS = 2
CONFIGS = [
    ("top_tt", 25), ("top_ff", 25), ("top_ss", 25),
    ("top_sf", 25), ("top_fs", 25), ("top_tt", -40), ("top_tt", 125),
]


def parse_args_configs(argv):
    """Optional subset re-run: `run_tran_corners.py top_sf:25 top_tt:125`.
    Results are merged into the existing tran_corners.json (today's good
    configs are kept, only the listed ones are re-run)."""
    if not argv:
        return CONFIGS
    return [(a.rsplit(":", 1)[0], int(a.rsplit(":", 1)[1])) for a in argv]


def models_line(section):
    return ('include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" '
            f"section={section}")


def link_bake(out, vc, pc, section, temp, vbic):
    return write_baked(TPL, out,
                       VC=vc, PC=pc, AZEN=1, DRIFT=0, NS=NS, STOP=30e-9,
                       VREFV=vc / 255 * VFS, MODELS=models_line(section), TEMP=temp,
                       RS=0.5, LS=0.01e-9, AMPL=0, FN=100e6, NFDIO=100, VBIC=vbic,
                       NOISE_OPTS="")


def main():
    sim = make_sim(timeout=3600)
    configs = parse_args_configs(sys.argv[1:])
    summary = []

    for section, temp in configs:
        print(f"\n=== {section} @ {temp}C ===")

        # phase 0: bias equilibrium
        nb = write_baked(TPL_BIAS, OUT_DIR / f"biasdc_{section}_{temp}.scs",
                         MODELS=models_line(section), TEMP=temp)
        t_bake = nb.stat().st_mtime
        r = sim.run_simulation(nb, {"include_files": INC_BIAS})
        vbic = None
        if r.ok:
            for key in ("dc1_vbias", "vbias"):  # bridge key varies
                if r.data.get(key) is not None:
                    vbic = float(r.data[key])
                    break
        if vbic is None:
            # key miss -> parse the raw downloaded just now; stale guard:
            # a raw older than the bake is a leftover from an earlier run
            # (this bit us on 9-3: top_sf read a 9-2 stale raw -> 0.504V)
            raw = OUT_DIR / f"biasdc_{section}_{temp}.raw" / "dc1.dc"
            if raw.exists() and raw.stat().st_mtime > t_bake:
                m = re.search(r'"vbias"\s+"V"\s+([-+0-9.eE]+)',
                              raw.read_text())
                if m:
                    vbic = float(m.group(1))
        if vbic is None:
            print("  bias DC probe FAILED:", r.errors[:1])
            summary.append({"corner": section, "temp": temp, "ok": False,
                            "error": "bias probe failed"})
            continue
        vbic = float(vbic)
        print(f"  vbias equilibrium = {vbic:.3f} V")

        # phase 1: vref x pi scan
        tasks = [(link_bake(OUT_DIR / f"cor_{section}_{temp}_v{vc}_p{int(pc*1000)}.scs",
                            vc, pc, section, temp, vbic), vc, pc)
                 for pc in SCAN_PIS for vc in VREF_CODES]
        results = sim.run_parallel([(n[0], {"include_files": INC}) for n in tasks],
                                   max_workers=4)
        rows = []
        for (net, vc, pc), res in zip(tasks, results):
            if not res.ok:
                rows.append({"vref_code": vc, "pi": pc, "ber": None,
                             "errors": res.errors[:1]})
                continue
            errs = final_value(res, "err_cnt")
            bits = final_value(res, "bit_cnt")
            rows.append({"vref_code": vc, "pi": pc,
                         "ber": (errs / bits) if bits else None})
        zero = sorted(set(x["vref_code"] for x in rows if x["ber"] == 0))
        if zero:
            print(f"  zero-BER window: {zero[0]}-{zero[-1]} codes = "
                  f"{zero[0]/255*VFS*1000:.0f}-{zero[-1]/255*VFS*1000:.0f} mV")
        else:
            print("  NO zero-BER points")
        summary.append({"corner": section, "temp": temp, "ok": bool(zero),
                        "vbias_v": vbic, "zero_ber_codes": zero, "points": rows})

    out_path = OUT_DIR / "tran_corners.json"
    merged = {}
    if out_path.exists():  # subset re-run: keep configs not being re-run
        for s in json.load(open(out_path)).get("summary", []):
            merged[(s["corner"], s["temp"])] = s
    for s in summary:
        old = merged.get((s["corner"], s["temp"]))
        if old and old.get("ok") and not s.get("ok"):
            print(f"  [merge] keep previous {s['corner']}@{s['temp']} result"
                  " (this re-run failed)")
            continue  # a failed re-run must not clobber good data
        merged[(s["corner"], s["temp"])] = s
    ordered = [merged[k] for k in CONFIGS if k in merged] + \
              [v for k, v in merged.items() if k not in CONFIGS]
    save_json({"configs": CONFIGS, "summary": ordered}, out_path)
    print("\n=== corner summary ===")
    for s in ordered:
        zc = s.get("zero_ber_codes") or []
        print(f"{s['corner']:6s} @ {s['temp']:4d}C: "
              + (f"zero-BER {zc[0]}-{zc[-1]} codes (vbias={s['vbias_v']:.3f})"
                 if zc else f"FAILED ({s.get('error','no zero-BER')})"))


if __name__ == "__main__":
    main()
