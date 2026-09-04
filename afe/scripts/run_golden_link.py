#!/usr/bin/env python3
"""Golden (schematic-sourced) AFE link run.

Netlist = output/n2s_top/golden_tb_template.scs (generated from the afe_sch
schematics); only the 5 digital-behavioral VA modules come as include files.
Everything else (cells + afe_tb_tran structure + TB) is si-exported.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_DIR, VA_DIR, final_value, make_sim, save_json, write_baked

TPL = OUT_DIR / "n2s_top" / "golden_tb_template.scs"
INC = [str(VA_DIR / f) for f in
       ("afe_ber_chk.va", "afe_clk_gen.va", "afe_pingpong.va",
        "afe_prbs23_gen.va", "afe_samp.va")]

MODELS_TT = ('include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" '
             "section=top_tt")
VFS = 0.45


def gold_bake(vc, pc, **kw):
    """Extra placeholders of the golden template (codeb bits + pi voltage)."""
    bits = {k: (0.8 if (vc >> k) & 1 else 0.0) for k in range(8)}
    d = {f"CB{k}": bits[k] for k in range(8)}
    d["PCV"] = pc * 0.8
    d.update(kw)
    return d


def main():
    net = write_baked(
        TPL, OUT_DIR / "golden_link.scs",
        VC=142, PC=0.875, AZEN=1, DRIFT=0, NS=2, STOP=40e-9,
        VREFV=142 / 255 * VFS, MODELS=MODELS_TT, TEMP=25,
        RS=0.5, LS=0.01e-9, AMPL=0, FN=100e6, VBIC=0.362, NOISE_OPTS="",
        **gold_bake(142, 0.875))
    sim = make_sim(timeout=3600)
    result = sim.run_simulation(net, {"include_files": INC})
    print("ok:", result.ok)
    if not result.ok:
        print("errors:", result.errors)
        sys.exit(1)

    errs = final_value(result, "err_cnt")
    bits = final_value(result, "bit_cnt")
    lock = final_value(result, "lock")
    vbias = final_value(result, "Xtb.vbias")
    ber = (errs / bits) if bits else None
    print(f"err_cnt={errs} bit_cnt={bits} lock={lock} BER={ber} "
          f"vbias_final={vbias}")

    def mean_pwr(sig):
        wf = result.data.get(sig)
        t = result.data.get("time")
        if wf is None or t is None:
            return None
        if isinstance(wf, float):
            return wf
        ys = [float(v) for v in wf]
        xs = [float(v) for v in t]
        if len(xs) < 2:
            return None
        t0, t1 = xs[0], xs[-1]
        if t1 <= t0:
            return None
        area = sum(0.5 * (ys[i] + ys[i + 1]) * (xs[i + 1] - xs[i])
                   for i in range(len(xs) - 1))
        return area / (t1 - t0)

    out = {
        "ber": ber, "err_cnt": errs, "bit_cnt": bits, "lock": lock,
        "vbias_final": vbias,
        "pwr_BA": mean_pwr("Xtb.BA:pwr"), "pwr_BB": mean_pwr("Xtb.BB:pwr"),
        "pwr_DRV": mean_pwr("Xtb.DRV:pwr"), "pwr_DAC": mean_pwr("Xdac:pwr"),
        "timings": result.metadata.get("timings"),
    }
    save_json(out, OUT_DIR / "golden_link.json")


if __name__ == "__main__":
    main()
