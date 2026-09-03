#!/usr/bin/env python3
"""R-2R Vref DAC INL/DNL — 256 single-code DC runs (python-enumerated)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NET_DIR, OUT_DIR, TRAN_DIR, final_value, make_sim, save_json, write_baked

TPL = NET_DIR / "tb_afe_dac_dc.scs"
INC = [str(TRAN_DIR / "afe_dac_r2r.scs")]


def main():
    tasks = []
    for vc in range(256):
        bits = {f"B{k}": 0.8 if (vc >> k) & 1 else 0.0 for k in range(8)}
        net = write_baked(TPL, OUT_DIR / f"dacdc_v{vc}.scs", **bits)
        tasks.append((net, vc))

    sim = make_sim(timeout=3600)
    results = sim.run_parallel(
        [(n, {"include_files": INC}) for n, _ in tasks], max_workers=4)

    vref = [None] * 256
    nfail = 0
    for (net, vc), res in zip(tasks, results):
        if not res.ok:
            nfail += 1
            continue
        v = res.data.get("dc1_vref", res.data.get("vref"))
        if isinstance(v, (list, tuple)):
            v = float(v[-1]) if len(v) else None
        elif v is not None:
            v = float(v)
        vref[vc] = v

    if nfail:
        print(f"warning: {nfail} failed runs")
    if any(v is None for v in vref):
        print("FAILED: missing points", [i for i, v in enumerate(vref) if v is None][:8])
        sys.exit(1)

    lsb = vref[255] / 255.0
    dnl = [(vref[k + 1] - vref[k]) / lsb - 1.0 for k in range(255)]
    inl = [(vref[k] - k * lsb) / lsb for k in range(256)]
    out = {
        "vref": vref,
        "lsb_v": lsb,
        "fs_v": vref[255],
        "dnl_lsb": dnl,
        "inl_lsb": inl,
        "dnl_max": max(abs(d) for d in dnl),
        "inl_max": max(abs(i) for i in inl),
    }
    print(f"FS={vref[255]*1000:.1f}mV  LSB={lsb*1000:.3f}mV  "
          f"DNL_max={out['dnl_max']:.2f}LSB  INL_max={out['inl_max']:.2f}LSB  "
          f"({nfail} failed)")
    save_json(out, OUT_DIR / "dac_dnl.json")


if __name__ == "__main__":
    main()
