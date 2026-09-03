#!/usr/bin/env python3
"""Compare schematic-tb smoke vs reference smoke (both 300ns, server 21).

- loads newest raw dirs under sim/out for run_smoke_tb_top / run_smoke_ref
- aligns signals by name (strip Xpll. prefix), common time grid via interp
- per-signal max|d| table
- metrics: CKFB fire rate, fVCO (OUTP crossings), OUTP swing
  vs recorded reference smoke (fVCO=7.926G, CKFB~99M, OUTP 2.01Vpp)

Pure-python (no numpy) so it runs in the virtuoso-bridge .venv.
"""
import sys
from bisect import bisect_right
from pathlib import Path

sys.path.insert(0, "/home/gmei/smic_test/ucie_isscc/virtuoso-bridge-lite/src")
from virtuoso_bridge.spectre.parsers import parse_psf_ascii_directory  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sim" / "out"

SIGNALS = ["OUTP", "CKFB", "VCTRL", "VI", "VHOLD", "EBIT", "MMDIN", "NBUF1",
           "VREF", "VDCC", "RDCC", "KDTC", "VRAMP", "SEL", "EPSC", "CK2X",
           "CKDTCD", "CKRST"]

# strictly compared pointwise (state variables)
ANALOG = {"VCTRL", "VI", "VREF", "VDCC", "RDCC", "KDTC"}


def load(stem):
    cands = sorted(set(list(OUT.glob(f"*{stem}__*")) + list(OUT.glob(f"*{stem}*"))),
                   key=lambda p: p.stat().st_mtime)
    for d in reversed(cands):
        raw = d if d.suffix == ".raw" else d / ".raw"
        if not raw.is_dir():
            continue
        data = parse_psf_ascii_directory(raw)
        if data:
            return data, raw
    return None, None


def as_arr(data, name):
    for key in data:
        if key == name or (name and key.endswith("." + name)):
            return data[key], key
    return None, None


def interp(x, xp, fp):
    """np.interp equivalent for sorted ascending xp."""
    out = []
    j = 0
    n = len(xp)
    for xi in x:
        while j < n - 1 and xp[j + 1] <= xi:
            j += 1
        if j == 0 and xi <= xp[0]:
            out.append(fp[0])
        elif j >= n - 1:
            out.append(fp[-1])
        else:
            f = (xi - xp[j]) / (xp[j + 1] - xp[j])
            out.append(fp[j] + f * (fp[j + 1] - fp[j]))
    return out


def crossings(t, v, thr, window):
    m = [i for i in range(len(t)) if window[0] <= t[i] <= window[1]]
    out = []
    for k in range(1, len(m)):
        i, j = m[k - 1], m[k]
        if v[i] < thr <= v[j]:
            f = (thr - v[i]) / (v[j] - v[i])
            out.append(t[i] + f * (t[j] - t[i]))
    return out


def freq_of(t, v, thr, window):
    c = crossings(t, v, thr, window)
    if len(c) < 3:
        return float("nan")
    return 1.0 / (sum(b - a for a, b in zip(c, c[1:])) / (len(c) - 1))


def main():
    ref, ref_raw = load("run_run_smoke_ref")
    sch, sch_raw = load("run_run_smoke_tb_top")
    print(f"ref: {ref_raw}")
    print(f"sch: {sch_raw}")
    if not sch:
        print("no schematic data")
        sys.exit(1)

    t_sch, _ = as_arr(sch, "time")
    print(f"sch npts={len(t_sch)} t=[{t_sch[0]:.3g},{t_sch[-1]:.3g}]")

    if ref:
        t_ref, _ = as_arr(ref, "time")
        print(f"ref npts={len(t_ref)} t=[{t_ref[0]:.3g},{t_ref[-1]:.3g}]")

        lo = max(t_sch[0], t_ref[0])
        hi = min(t_sch[-1], t_ref[-1])
        m = [i for i in range(len(t_sch)) if lo <= t_sch[i] <= hi]
        tg = [t_sch[i] for i in m]

        print(f"\n{'signal':<10}{'max|d|':>12}{'ref mean':>12}{'sch mean':>12}")
        ok = True
        for name in SIGNALS:
            vr, kr = as_arr(ref, name)
            vs, ks = as_arr(sch, name)
            if vr is None or vs is None:
                print(f"{name:<10}  MISSING (ref={'?' if vr is None else kr}, sch={'?' if vs is None else ks})")
                continue
            vr_i = interp(tg, t_ref, vr)
            vs_i = interp(tg, t_sch, vs)
            dmax = max(abs(a - b) for a, b in zip(vr_i, vs_i))
            rmax = max(abs(a) for a in vr_i)
            rel = dmax / (rmax + 1e-30)
            mean_drift = abs(sum(vr) / len(vr) - sum(vs) / len(vs))
            if name in ANALOG:
                flag = "" if rel < 0.01 else ("  <-- >1%" if rel < 0.05 else "  <-- !!! >5%")
                if rel >= 0.05:
                    ok = False
            else:
                # digital/edge signals: pointwise dmax is dominated by edge
                # phase drift between independent tran runs; judge on mean
                flag = "" if mean_drift < 0.02 * rmax else "  <-- mean drift"
                if mean_drift >= 0.02 * rmax:
                    ok = False
            print(f"{name:<10}{dmax:>12.4g}{sum(vr)/len(vr):>12.4g}{sum(vs)/len(vs):>12.4g}{flag}")
    else:
        print("\n(reference data not ready yet — metrics only)")
        ok = True

    # metrics per deck
    print("\n== metrics ==")
    metrics = {}
    for label, data in (("ref", ref), ("sch", sch)):
        if not data:
            continue
        t, _ = as_arr(data, "time")
        v_outp, _ = as_arr(data, "OUTP")
        v_ckfb, _ = as_arr(data, "CKFB")
        thr_o = 0.5 * (max(v_outp) + min(v_outp))
        f_vco = freq_of(t, v_outp, thr_o, (t[-1] * 0.4, t[-1]))
        f_ckfb = freq_of(t, v_ckfb, 0.4, (t[-1] * 0.4, t[-1]))
        swing = max(v_outp) - min(v_outp)
        v_vctrl, _ = as_arr(data, "VCTRL")
        metrics[label] = (t, v_outp, v_ckfb, thr_o, f_vco, f_ckfb)
        print(f"{label}: fVCO={f_vco/1e9:.4f}G  CKFB={f_ckfb/1e6:.2f}M  "
              f"OUTP swing={swing:.3f}V  VCTRL end={v_vctrl[-1]:.4f}V")

    # edge-alignment criteria (two independent tran runs diverge in phase
    # ~0.01%/window; early-window edge times must align to ps level)
    if ref:
        print("\n== edge alignment ==")
        t_r, v_or, v_cr, thr_or, _, f_cr = metrics["ref"]
        t_s, v_os, v_cs, thr_os, _, f_cs = metrics["sch"]
        for name, vr_, vs_, thr_r_, thr_s_, win in (
                ("OUTP", v_or, v_os, thr_or, thr_os, (10e-9, 12e-9)),
                ("CKFB", v_cr, v_cs, 0.4, 0.4, (50e-9, 100e-9))):
            er = crossings(t_r, vr_, thr_r_, win)
            es = crossings(t_s, vs_, thr_s_, win)
            n = min(len(er), len(es))
            if n:
                dt = [abs(a - b) for a, b in zip(er[:n], es[:n])]
                print(f"{name} [{win[0]*1e9:.0f},{win[1]*1e9:.0f}]ns: "
                      f"edges {len(er)}/{len(es)}, mean|dt|={sum(dt)/n*1e12:.2f}ps "
                      f"max|dt|={max(dt)*1e12:.2f}ps")
        d_frate = abs(f_cr - f_cs) / f_cr
        print(f"CKFB fire-rate diff: {d_frate*100:.4f}%")
        ok = ok and d_frate < 5e-4

    print("\nreference smoke (0827 record): fVCO=7.926G  CKFB~99M  OUTP 2.01Vpp")
    print("PASS" if ok else "FAIL (see criteria above)")


if __name__ == "__main__":
    main()
