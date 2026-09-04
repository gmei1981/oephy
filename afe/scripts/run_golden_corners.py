#!/usr/bin/env python3
"""Golden (schematic-sourced) corner + temperature verification.

Mirrors run_tran_corners.py (5 corners @25C + tt @-40/125C; per config:
bias DC probe -> bake VBIC ic -> vref scan at pi 0.375/0.875, ns=2).

Bias probe keeps the legacy tb_bias_dc.scs + tran/afe_bias.scs include:
that cell was golden-probed bit-identical to the afe_sch schematic
(0.36272 V, 2026-09-04), so its per-corner equilibria are valid for the
golden netlist as well. The tran sweep itself runs the golden template
(si export of tb_afe_tran; only the 5 VA files are includes).

Usage: run_golden_corners.py [section:temp ...]   # subset re-run + merge
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NET_DIR, OUT_DIR, TRAN_DIR, VA_DIR, final_value, make_sim, save_json, write_baked
from run_golden_link import TPL, INC, VFS, gold_bake

TPL_BIAS = NET_DIR / "tb_bias_dc.scs"
INC_BIAS = [str(TRAN_DIR / "afe_bias.scs")]

VREF_CODES = list(range(90, 220, 10))  # 13 codes
SCAN_PIS = [0.375, 0.875]
NS = 2
CONFIGS = [
    ("top_tt", 25), ("top_ff", 25), ("top_ss", 25),
    ("top_sf", 25), ("top_fs", 25), ("top_tt", -40), ("top_tt", 125),
]
OUT_NAME = "golden_corners.json"


def parse_args_configs(argv):
    if not argv:
        return CONFIGS
    return [(a.rsplit(":", 1)[0], int(a.rsplit(":", 1)[1])) for a in argv]


def models_line(section):
    return ('include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" '
            f"section={section}")


def link_bake(out, vc, pc, section, temp, vbic):
    return write_baked(
        TPL, out,
        VC=vc, PC=pc, AZEN=1, DRIFT=0, NS=NS, STOP=30e-9,
        VREFV=vc / 255 * VFS, MODELS=models_line(section), TEMP=temp,
        RS=0.5, LS=0.01e-9, AMPL=0, FN=100e6, VBIC=vbic, NOISE_OPTS="",
        **gold_bake(vc, pc))


def probe_bias(sim, section, temp):
    nb = write_baked(TPL_BIAS, OUT_DIR / f"gbiasdc_{section}_{temp}.scs",
                     MODELS=models_line(section), TEMP=temp)
    t_bake = nb.stat().st_mtime
    r = sim.run_simulation(nb, {"include_files": INC_BIAS})
    if r.ok:
        for key in ("dc1_vbias", "vbias"):
            if r.data.get(key) is not None:
                return float(r.data[key])
    # key miss -> parse fresh raw (stale guard: raw older than bake is a
    # leftover from an earlier run)
    raw = OUT_DIR / f"gbiasdc_{section}_{temp}.raw" / "dc1.dc"
    if raw.exists() and raw.stat().st_mtime > t_bake:
        m = re.search(r'"vbias"\s+"V"\s+([-+0-9.eE]+)', raw.read_text())
        if m:
            return float(m.group(1))
    return None


def main():
    sim = make_sim(timeout=3600)
    configs = parse_args_configs(sys.argv[1:])
    summary = []

    for ci, (section, temp) in enumerate(configs):
        print(f"\n=== {section} @ {temp}C ===", flush=True)

        vbic = probe_bias(sim, section, temp)
        if vbic is None:
            print("  bias DC probe FAILED", flush=True)
            summary.append({"corner": section, "temp": temp, "ok": False,
                            "error": "bias probe failed"})
            continue
        print(f"  vbias equilibrium = {vbic:.3f} V", flush=True)

        tasks = [(link_bake(OUT_DIR / f"gcor_{section}_{temp}_v{vc}_p{int(pc*1000)}.scs",
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
                  f"{zero[0]/255*VFS*1000:.0f}-{zero[-1]/255*VFS*1000:.0f} mV",
                  flush=True)
        else:
            print("  NO zero-BER points", flush=True)
        summary.append({"corner": section, "temp": temp, "ok": bool(zero),
                        "vbias_v": vbic, "zero_ber_codes": zero, "points": rows})

        if ci < len(configs) - 1:
            time.sleep(30)  # SSH rate-limit guard between config batches

    out_path = OUT_DIR / OUT_NAME
    merged = {}
    if out_path.exists():  # subset re-run: keep configs not being re-run
        for s in json.load(open(out_path)).get("summary", []):
            merged[(s["corner"], s["temp"])] = s
    for s in summary:
        old = merged.get((s["corner"], s["temp"]))
        if old and old.get("ok") and not s.get("ok"):
            print(f"  [merge] keep previous {s['corner']}@{s['temp']} result"
                  " (this re-run failed)")
            continue
        merged[(s["corner"], s["temp"])] = s
    ordered = [merged[k] for k in CONFIGS if k in merged] + \
              [v for k, v in merged.items() if k not in CONFIGS]
    save_json({"configs": CONFIGS, "summary": ordered}, out_path)
    print("\n=== golden corner summary ===")
    for s in ordered:
        zc = s.get("zero_ber_codes") or []
        print(f"{s['corner']:6s} @ {s['temp']:4d}C: "
              + (f"zero-BER {zc[0]}-{zc[-1]} codes (vbias={s['vbias_v']:.3f})"
                 if zc else f"FAILED ({s.get('error','no zero-BER')})"))


if __name__ == "__main__":
    main()
