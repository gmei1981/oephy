#!/usr/bin/env python3
"""DTC Tres / INL measurement.

1. generate per-code testbenches (dtc_codeN.scs)
2. run them in parallel on server 21 via bridge
3. parse CK_IN -> CK_OUT delay per code, fit Tres, compute INL

Usage: python3 scripts/dtc_meas.py [--codes 0,64,128,...,960]
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NSW = 1023
TB_TMPL = """// dtc_code{code}.scs — DTC delay vs code (thermometer pattern of first {code} gates on)
simulator lang=spectre
include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt
include "dtc_10b.scs"

Vvdd (VDD 0) vsource dc=0.8
Vvss (VSS 0) vsource dc=0
Vin (CKIN 0) vsource type=pulse val0=0 val1=0.8 period=6.510417n width=3.25n rise=10p fall=10p
{gates}
Xdtc (CKIN CKOUT VDD VSS {cports}) dtc_10b
Rload (CKOUT 0) resistor r=1e6

plltran tran stop=40n maxstep=2p errpreset=liberal method=gear2only skipdc=yes
save CKIN CKOUT
"""


def gen_tb(code: int, outdir: Path) -> Path:
    gates = "\n".join(
        f"Vg{i} (c{i} 0) vsource dc={0.8 if i < code else 0.0}" for i in range(NSW)
    )
    cports = " ".join(f"c{i}" for i in range(NSW))
    tb = outdir / f"dtc_code{code}.scs"
    tb.write_text(TB_TMPL.format(code=code, gates=gates, cports=cports))
    return tb


def run_codes(codes, max_workers=4):
    from virtuoso_bridge.spectre.runner import SpectreSimulator, spectre_mode_args
    outdir = ROOT / "sim" / "dtc"
    outdir.mkdir(exist_ok=True)
    sim = SpectreSimulator.from_env(
        spectre_args=spectre_mode_args("ax"),
        work_dir=str(outdir),
        timeout=1800,
    )
    incs = [str(ROOT / "netlist" / "inc" / "dtc_10b.scs")]
    tbs = [gen_tb(c, outdir) for c in codes]
    results = sim.run_parallel(
        [(str(tb), {"include_files": incs}) for tb in tbs],
        max_workers=max_workers,
    )
    for tb, res in zip(tbs, results):
        print(tb.name, "ok=", res.ok if res is not None else None)


def parse_delay(tb_dir: Path, code: int):
    """Measure CKIN rising -> CKOUT falling delay (DTC output inverted)."""
    import re
    import numpy as np

    def get_trace(name):
        f = next(tb_dir.glob("*.raw/*.tran.tran")) if list(tb_dir.glob("*.raw/*.tran.tran")) else None
        if f is None:
            return None
        txt = f.read_text(errors="replace")
        body = txt.split("VALUE", 1)[1]
        vals = []
        for l in body.split("\n"):
            m = re.match(r'^"%s"\s+([0-9.eE+-]+)' % name, l.strip())
            if m:
                vals.append(float(m.group(1)))
        return np.asarray(vals)

    t = get_trace("time")
    vin = get_trace("CKIN")
    vout = get_trace("CKOUT")
    if t is None or len(t) == 0:
        return None
    mask = t > 10e-9
    ci = np.where((vin[mask][:-1] < 0.4) & (vin[mask][1:] >= 0.4))[0]
    cf = np.where((vout[mask][:-1] >= 0.4) & (vout[mask][1:] < 0.4))[0]
    if len(ci) < 2 or len(cf) < 2:
        return None
    n = min(len(ci), len(cf)) - 1
    delays = [t[mask][cf[k]] - t[mask][ci[k]] for k in range(n)]
    return float(np.median(delays))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="0,32,64,96,128,160,192,224,256,320,384,448,512,576,640,704,768,832,896,960")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--parse-only", action="store_true")
    args = ap.parse_args()
    codes = [int(x) for x in args.codes.split(",")]
    if not args.parse_only:
        run_codes(codes, args.workers)
    else:
        import numpy as np
        outdir = ROOT / "sim" / "dtc"
        rows = []
        for c in codes:
            d = parse_delay(outdir / f"dtc_code{c}__run0" if not (outdir / f"dtc_code{c}.raw").exists() else outdir / f"dtc_code{c}.raw", c)
            # try both naming conventions
            if d is None:
                for cand in outdir.glob(f"dtc_code{c}*"):
                    if cand.is_dir():
                        d = parse_delay(cand, c)
                        if d is not None:
                            break
            if d is None:
                print(f"code {c}: NO DATA")
                continue
            rows.append((c, d))
        print(f"{'code':>6} {'delay_ps':>10}")
        for c, d in rows:
            print(f"{c:>6} {d*1e12:>10.2f}")
        if len(rows) >= 3:
            cs = np.array([r[0] for r in rows], dtype=float)
            ds = np.array([r[1] for r in rows], dtype=float)
            k = np.polyfit(cs, ds, 1)
            print(f"Tres = {k[0]*1e15:.2f} fs, offset = {k[1]*1e12:.1f} ps")
            print(f"INL (max dev from fit) = {np.max(np.abs(ds - np.polyval(k, cs)))*1e15:.1f} fs")
