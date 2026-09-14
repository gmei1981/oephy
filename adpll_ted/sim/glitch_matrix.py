#!/usr/bin/env python3
"""glitch_matrix.py — fbank 单元切换 glitch 扫参矩阵 (相位/边沿/尺寸/收敛)

在 vco_glitch_tb2 + glitch_dut 基础上生成变体、并发 spectre、统一提取。
输出: glitch_results.txt (每 run 一行) + glitch_summary.txt
"""
import subprocess, os, re, sys
import numpy as np

SIM = "/home/gmei/git/oephy/adpll_ted/sim"
SPEC = "/home/gmei/bin/spectre"
os.chdir(SIM)

# tag -> (tb sed pairs, dut sed pairs)
T = 124.9e-12   # baseline period
runs = {"base": ([], [])}                      # 已有 runD 结果, 跳过仿真
runs["conv"] = ([("maxstep=2p errpreset=liberal", "maxstep=1p errpreset=moderate")], [])
for m in range(1, 8):
    tsw = 60e-9 + m * T / 8
    runs[f"ph{m}"] = ([("TSW=60n", f"TSW={tsw*1e9:.6f}n")], [])
runs["tr20"]  = ([("TRISE=50p", "TRISE=20p")], [])
runs["tr200"] = ([("TRISE=50p", "TRISE=200p")], [])
runs["sz4"]   = ([], [("NFIN_U=2", "NFIN_U=4")])
runs["sz8"]   = ([], [("NFIN_U=2", "NFIN_U=8")])
runs["sw4"]   = ([], [("NF_SW=2", "NF_SW=4")])

def bake(tag, tb_sub, dut_sub):
    d = f"gs_{tag}"
    os.makedirs(d, exist_ok=True)
    tb = open("vco_glitch_tb2.scs").read()
    for a, b in tb_sub: tb = tb.replace(a, b)
    if dut_sub:
        dut = open("glitch_dut.scs").read()
        for a, b in dut_sub: dut = dut.replace(a, b)
        open(f"{d}/glitch_dut.scs", "w").write(dut)
        tb = tb.replace('include "glitch_dut.scs"', f'include "{d}/glitch_dut.scs"')
    open(f"tbx_{tag}.scs", "w").write(tb)
    return d

procs = {}
todo = [t for t in runs if t != "base"]
for tag in todo:
    tb_sub, dut_sub = runs[tag]
    d = bake(tag, tb_sub, dut_sub)
    lf = open(f"{d}/run.log", "w")
    procs[tag] = (d, subprocess.Popen(
        [SPEC, "-64", f"{SIM}/tbx_{tag}.scs", "+mt", "-format", "psfascii"],
        stdout=lf, stderr=subprocess.STDOUT, start_new_session=True))
print(f"launched {len(procs)} spectre runs", flush=True)
for tag, (d, p) in procs.items():
    p.wait()
print("all sims done", flush=True)

# ---------- extraction ----------
def extract(raw):
    cols, inv = {}, False
    for ln in open(raw):
        s = ln.strip()
        if s == "VALUE": inv = True; continue
        if s == "END": break
        if not inv or not s.startswith('"'): continue
        nm, _, rest = s[1:].partition('"')
        try: v = float(rest.split()[0])
        except (ValueError, IndexError): continue
        cols.setdefault(nm, []).append(v)
    t = np.array(cols["time"]); v = np.array(cols["OUTP"]); en = np.array(cols["EN"])
    vth = 0.5 * (v.min() + v.max())
    ix = np.where((v[:-1] < vth) & (v[1:] >= vth))[0]
    tc = t[ix] + (vth - v[ix]) / (v[ix+1] - v[ix]) * (t[ix+1] - t[ix])
    kc = np.arange(len(tc))
    t_on = t[np.argmax(en > 0.4)]
    t_off = t[np.argmax((en < 0.4) & (t > t_on))]
    def fit(a, b):
        m = (tc >= a) & (tc < b)
        p = np.polyfit(kc[m], tc[m], 1)
        r = (np.polyval(p, kc[m]) - tc[m]) * 1e15
        return p, np.sqrt(np.mean(r**2)), m.sum()
    p1, r1, _ = fit(t_on - 18e-9, t_on - 2e-9)
    p2, r2, _ = fit(t_on + 1.2e-9, t_off - 0.3e-9)
    p3, r3, _ = fit(t_off + 1.5e-9, min(t_off + 25e-9, t[-1] - 1e-9))
    f1, f2, f3 = [1 / p[0] for p in (p1, p2, p3)]
    k_on = np.searchsorted(tc, t_on) + 7
    k_off = np.searchsorted(tc, t_off) + 7
    kick_on = (np.polyval(p1, k_on) - np.polyval(p2, k_on)) * 1e15
    kick_off = (np.polyval(p2, k_off) - np.polyval(p3, k_off)) * 1e15
    i0 = np.searchsorted(tc, t_on)
    phase_deg = (t_on - tc[i0-1]) / (tc[i0] - tc[i0-1]) * 360
    return dict(f1=f1, dstep=f1-f2, f3f1=f3-f1, kon=kick_on, koff=kick_off,
                net=kick_on+kick_off, rms=max(r1, r3), ph=phase_deg)

raws = {"base": f"{SIM}/vco_glitch_tb2.raw/tran.tran.tran"}
for tag in todo:
    raws[tag] = f"{SIM}/tbx_{tag}.raw/tran.tran.tran"

with open("glitch_results.txt", "w") as fo:
    print(f"{'tag':6s} {'phDeg':>6s} {'f1(GHz)':>9s} {'dStep(MHz)':>10s} "
          f"{'kick_on':>9s} {'kick_off':>9s} {'net':>8s} {'rms(fs)':>8s} {'f3-f1(kHz)':>10s}", file=fo)
    for tag in list(raws):
        try:
            r = extract(raws[tag])
        except Exception as e:
            print(f"{tag:6s} EXTRACT-FAIL {e}", file=fo); continue
        print(f"{tag:6s} {r['ph']:6.0f} {r['f1']/1e9:9.5f} {r['dstep']/1e6:10.2f} "
              f"{r['kon']:9.0f} {r['koff']:9.0f} {r['net']:8.0f} {r['rms']:8.1f} {r['f3f1']/1e3:10.1f}", file=fo)
print(open("glitch_results.txt").read())
