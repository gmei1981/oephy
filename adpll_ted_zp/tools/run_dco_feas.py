#!/usr/bin/env python3
"""DCO feasibility campaign: can 12nm (CLN12FFCLL) make aF-class switchable cap steps?

Test A: cfmom_wo_p80 differential C vs nr / lr  (geometry granularity, ~aF/nr)
Test B: switched-cap unit dC_eff at 8 GHz       (bottom-plate parasitic collapse)
Test C: VCO-level switched bank df              (large-swing ground truth)

Usage: python3 tools/run_dco_feas.py a|b|c|all [--dry]
Results -> sim/dco_feas/<tag>/ + sim/dco_feas/results.json
"""
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import threading

# CDS 'psf' text exporter is not safe under concurrent invocation — serialize it
PSF_LOCK = threading.Lock()

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sim" / "dco_feas"
SPECTRE = "/home/gmei/bin/spectre"
PDK = 'include "/home/lib/tsmc_12nm_installed/pdk/models/toplevel.scs" section=top_tt'

CFMOM = ("cfmom_wo_p80 dmflag=0 lr={lr} multi=1 mxd_flag=0 nr={nr} n_mxa=2 shield=2 "
         "spm=3 stm=1 vapmod={vapmod} grflag=1 gdis_t=185n gdis_b=185n "
         "gdis_l=102n gdis_r=102n")
SW = ("nch_{vt}_mac l=16n nfin={nfin} w=58n multi=1 nf=1 sd=74n sa=90n sb=90n "
      "ploda1=16n ploda2=0 ploda3=0 plodb1=16n plodb2=0 plodb3=0 nf_flag=1 smbt=1M "
      "smbb=1M dinsaflag=0 ppitch=0 spot=103n spob=103n spotl1=103n spobl1=103n "
      "spotl2=103n spobl2=103n spotr1=103n spobr1=103n spotr2=103n spobr2=103n")


def get(rawdir, sig, retry=3):
    import time
    p = Path(rawdir)
    hits = []
    for _ in range(retry):
        hits = sorted(p.glob("*.tran.tran")) + sorted(p.glob("*.tran.*.tran"))
        if hits:
            break
        time.sleep(2)
    if not hits:
        raise RuntimeError(f"no tran psf in {rawdir}: {sorted(p.glob('*'))}")
    for _ in range(retry):
        with PSF_LOCK:
            r = subprocess.run(["psf", "-i", str(hits[0]), "-s", "-t", sig,
                                "-f", "%.9e"], capture_output=True, text=True)
        if "VALUE" in r.stdout:
            break
        time.sleep(1)
    body = r.stdout.split("VALUE", 1)[1]
    v = []
    for l in body.split("\n"):
        m = re.match(r'^"([^"]+)"\s+([0-9.eE+-]+)', l.strip())
        if m and m.group(1) == sig:
            v.append(float(m.group(2)))
    return np.asarray(v)


def fit_sine(t, v, f):
    """LSQ v ~ c0 + c1 sin(wt) + c2 cos(wt) over last 80% -> (amp, phase_deg)."""
    w = 2 * np.pi * f
    n0 = int(0.2 * len(t))
    tt, vv = t[n0:], v[n0:]
    A = np.column_stack([np.ones_like(tt), np.sin(w * tt), np.cos(w * tt)])
    c, *_ = np.linalg.lstsq(A, vv, rcond=None)
    amp = float(np.hypot(c[1], c[2]))
    ph = float(np.degrees(np.arctan2(c[2], c[1])))
    return amp, ph


def run_tag(tag, netlist):
    d = OUT / tag
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    nl = d / "main.scs"
    nl.write_text(netlist)
    r = subprocess.run([SPECTRE, str(nl), "-raw", str(d), "+log", str(d / "main.log"),
                        "-format", "psfbin"],
                       capture_output=True, text=True, cwd=d, timeout=1800)
    err = r.stdout.count("ERROR")
    return d, err


# ---------------- Test A: cfmom C(nr, lr) ----------------
# nr floor: internal nmos l = nr*0.1u >= lmin(vapmod)  -> vapmod=2: nr>=7, vapmod=1: nr>=5
A_NR = [7, 8, 9, 10, 12, 16, 20, 24, 32, 48, 64, 96, 128, 160, 174, 176, 192, 256]
A_LR_SWEEP = [0.7e-6, 0.85e-6, 1.5e-6, 2e-6]  # at nr=7
A_VM1 = [5]  # vapmod=1 odd-nr grid {5,7,9,...} at lr=0.5u (its lmin=0.5u)


def nl_a(nr, lr, vapmod=2, f=2e9, iamp=100e-9):
    return f"""// cfmom C extraction nr={nr} lr={lr} vapmod={vapmod}
simulator lang=spectre
{PDK}
Vta (ta 0) vsource dc=0
Ra (ta a) resistor r=10Meg
Vb (b 0) vsource dc=0
Vp (p 0) vsource dc=0
X1 (a b p) {CFMOM.format(nr=nr, lr=f"{lr*1e6:.4g}u", vapmod=vapmod)}
I1 (0 a) isource type=sine freq={f:.4g} ampl={iamp*1e9:.4g}n
tran tran stop=8n maxstep=5p errpreset=liberal method=gear2only
save a
saveOptions options save=selected
"""


def test_a(dry=False):
    pts = [(nr, 1e-6, 2) for nr in A_NR] + [(7, lr, 2) for lr in A_LR_SWEEP] \
        + [(nr, 0.5e-6, 1) for nr in A_VM1]
    res = []
    for nr, lr, vm in pts:
        tag = f"a_vm{vm}_nr{nr}_lr{lr*1e6:.4g}u"
        if dry:
            continue
        d, err = run_tag(tag, nl_a(nr, lr, vapmod=vm))
        t, v = get(d, "time"), get(d, "a")
        amp, ph = fit_sine(t, v, 2e9)
        C = 100e-9 / (2 * np.pi * 2e9 * amp)
        res.append({"vapmod": vm, "nr": nr, "lr_u": lr * 1e6, "C_fF": C * 1e15,
                    "phase_deg": ph, "err": err})
        print(f"  A {tag}: C={C*1e15:.4f} fF  ph={ph:.1f}  err={err}")
    return res


# ---------------- Test B: switched unit dC_eff ----------------
def nl_b(nr, mode, vt="svt", nfin=1, f=8e9, iamp=100e-9, vapmod=2, lr="1u"):
    """mode: direct (x hard-grounded) | on | off | bare (no Cu, switch on t)"""
    cu = (f"X1 (t x p) {CFMOM.format(nr=nr, lr=lr, vapmod=vapmod)}\n"
          if mode != "bare" else "")
    if mode == "direct":
        conn = "Vx (x 0) vsource dc=0\n"
    elif mode == "bare":
        conn = (f"Ven (en 0) vsource dc=0.8\n"
                f"Msw (t en 0 0) {SW.format(vt=vt, nfin=nfin)}\n")
        return f"""// bare switch parasitic {vt} nfin={nfin} f={f:.3g}
simulator lang=spectre
{PDK}
Vtt (tt 0) vsource dc=0.5
Rt (tt t) resistor r=10Meg
{conn}I1 (0 t) isource type=sine freq={f:.4g} ampl={iamp*1e9:.4g}n
tran tran stop=6n maxstep=2p errpreset=liberal method=gear2only
save t
saveOptions options save=selected
"""
    else:
        conn = (f"Ven (en 0) vsource dc={0.8 if mode == 'on' else 0.0}\n"
                f"Msw (x en 0 0) {SW.format(vt=vt, nfin=nfin)}\n")
    return f"""// switched unit dC_eff nr={nr} mode={mode} {vt} nfin={nfin} f={f:.3g}
simulator lang=spectre
{PDK}
Vtt (tt 0) vsource dc=0.5
Rt (tt t) resistor r=10Meg
Vp (p 0) vsource dc=0
Rxb (x 0) resistor r=100Meg
{cu}{conn}I1 (0 t) isource type=sine freq={f:.4g} ampl={iamp*1e9:.4g}n
tran tran stop=6n maxstep=2p errpreset=liberal method=gear2only
save t
saveOptions options save=selected
"""


def test_b(dry=False):
    jobs = []
    for nr in [7, 8, 16, 32]:
        for mode in ["direct", "on", "off"]:
            jobs.append(dict(nr=nr, mode=mode, vt="svt", nfin=1, f=8e9))
    # smallest legal mom unit in the PDK menu: vapmod=1, nr=5, lr=0.5u (~0.69 fF)
    for mode in ["direct", "on", "off"]:
        jobs.append(dict(nr=5, mode=mode, vt="svt", nfin=1, f=8e9,
                         vapmod=1, lr="0.5u"))
    for vt, nfin in [("svt", 2), ("ulvt", 1)]:
        for mode in ["on", "off"]:
            jobs.append(dict(nr=7, mode=mode, vt=vt, nfin=nfin, f=8e9))
    for mode in ["on", "off"]:
        for vt, nfin in [("svt", 1), ("svt", 2), ("ulvt", 1)]:
            jobs.append(dict(nr=0, mode="bare", vt=vt, nfin=nfin, f=8e9))
    for f in [2e9, 5e9]:
        for j0 in [dict(nr=7, mode="on"), dict(nr=16, mode="on"),
                   dict(nr=7, mode="off")]:
            jobs.append(dict(j0, vt="svt", nfin=1, f=f))
    if dry:
        print(f"  B: {len(jobs)} runs"); return []

    def one(j):
        vm = j.get("vapmod", 2)
        tag = (f"b_vm{vm}_nr{j['nr']}_{j['mode']}_{j['vt']}{j['nfin']}_"
               f"f{j['f']:.0e}".replace("e+0", "e"))
        d, err = run_tag(tag, nl_b(**j))
        t, v = get(d, "time"), get(d, "t")
        amp, ph = fit_sine(t, v, j["f"])
        Y = 100e-9 / amp
        Cim = -Y * np.sin(np.radians(ph)) / (2 * np.pi * j["f"])  # Im(Y)/w
        G = Y * np.cos(np.radians(ph))
        return dict(j, tag=tag, C_fF=Cim * 1e15, G_uS=G * 1e6, phase_deg=ph, err=err)

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, jobs))
    for r in res:
        print(f"  B {r['tag']}: C_eff={r['C_fF']:.4f} fF ph={r['phase_deg']:.0f} "
              f"G={r['G_uS']:.2f}uS err={r['err']}")
    return res


# ---------------- Test C: VCO-level bank df ----------------
def nl_c(nr_per_unit, units, en, vapmod=2, lr="1u"):
    """vco_x_c_dac with VC1/VC2 fixed + units/side of cfmom switched to VSS."""
    bank = ""
    for k in range(units):
        bank += (f"XBp{k} (OUTP xbp{k} VSS) {CFMOM.format(nr=nr_per_unit, lr=lr, vapmod=vapmod)}\n"
                 f"XBn{k} (OUTN xbn{k} VSS) {CFMOM.format(nr=nr_per_unit, lr=lr, vapmod=vapmod)}\n"
                 f"XBpr{k} (xbp{k} 0) resistor r=100Meg\n"
                 f"XBnr{k} (xbn{k} 0) resistor r=100Meg\n"
                 f"MBp{k} (xbp{k} en 0 0) {SW.format(vt='svt', nfin=1)}\n"
                 f"MBn{k} (xbn{k} en 0 0) {SW.format(vt='svt', nfin=1)}\n")
    return f"""// VCO bank df: {units}x cfmom nr={nr_per_unit}(vm{vapmod},{lr})/side, en={en}
simulator lang=spectre
{PDK}
include "/home/gmei/git/oephy/adpll_ted_zp/netlist/inc/vco_c_dac.scs"
Vss (VSS 0) vsource dc=0
Vvddc (VDDC 0) vsource type=pulse val0=0 val1=0.5 delay=0 rise=1n width=1m period=1m
Vc1 (VC1 0) vsource dc=0.31
Vc2 (VC2 0) vsource dc=0
Ven (en 0) vsource dc={en}
Xvco (VDDC VDDC VSS OUTP OUTN VC1 VC2) vco_x_c_dac
{bank}
tran tran stop=120n maxstep=2p errpreset=liberal method=gear2only skipdc=yes \
    ic="OUTP=0.45" ic="OUTN=0.0"
save OUTP OUTN VDDC
saveOptions options save=selected
"""


def crossings(t, x, vth=0.4):
    above = x > vth
    out = []
    for k in range(1, len(t)):
        # degenerate-step guard: during the VDDC ramp consecutive samples can be
        # bit-identical -> interpolation fraction explodes to garbage times
        if above[k] and not above[k - 1] and abs(x[k] - x[k - 1]) > 1e-6:
            f_ = (vth - x[k - 1]) / (x[k] - x[k - 1])
            out.append(t[k - 1] + f_ * (t[k] - t[k - 1]))
    return np.asarray(out)


def test_c(dry=False):
    # (nr, units/side, vapmod, lr); vm1 nr5 lr0.5u = smallest legal unit (~0.69 fF)
    cfgs = [(7, 1, 2, "1u"), (16, 1, 2, "1u"), (5, 1, 1, "0.5u"), (7, 4, 2, "1u")]
    if dry:
        print(f"  C: {len(cfgs)*2} runs"); return []
    def run_one(args):
        nr, u, vm, lr, en = args
        tag = f"c_vm{vm}_nr{nr}x{u}_en{en:.1f}"
        d, err = run_tag(tag, nl_c(nr, u, en, vapmod=vm, lr=lr))
        t, v = get(d, "time"), get(d, "OUTP")
        m = t > 40e-9  # steady window only (skip VDDC ramp / startup)
        cr = crossings(t[m], v[m])
        per = np.diff(cr)
        per = per[(per > 50e-12) & (per < 200e-12)]
        f_GHz = float(1 / np.mean(per[-60:])) / 1e9 if len(per) else float("nan")
        return (nr, u, vm, en), dict(tag=tag, f_GHz=f_GHz, err=err, nper=len(per))

    jobs = [(nr, u, vm, lr, en) for nr, u, vm, lr in cfgs for en in (0.0, 0.8)]
    with ThreadPoolExecutor(8) as ex:
        pairs = list(ex.map(run_one, jobs))
    freq = dict(pairs)
    for _, r in pairs:
        print(f"  C {r['tag']}: fVCO={r['f_GHz']:.5f} GHz ({r['nper']} per) "
              f"err={r['err']}")
    res = []
    for nr, u, vm, lr in cfgs:
        f0 = freq[(nr, u, vm, 0.0)]["f_GHz"]
        f1 = freq[(nr, u, vm, 0.8)]["f_GHz"]
        res.append({"vapmod": vm, "nr": nr, "lr": lr, "units": u, "f0_GHz": f0,
                    "f1_GHz": f1, "df_MHz": (f0 - f1) * 1e3,
                    "df_per_unit_MHz": (f0 - f1) * 1e3 / u})
        print(f"  C vm{vm} nr={nr}({lr})x{u}/side: f {f0:.5f}->{f1:.5f} GHz, "
              f"df = {(f0-f1)*1e3:.3f} MHz ({(f0-f1)*1e3/u:.3f} MHz/unit)")
    return res


def test_c_parse():
    """Re-parse existing c_* raws (no spectre re-run)."""
    freq = {}
    for d in sorted(OUT.glob("c_vm*_en*")):
        if not list(d.glob("tran.tran.tran")):
            print(f"  skip {d.name}: no raw yet"); continue
        tag = d.name
        f_GHz = float("nan")
        p2p = float("nan")
        try:
            t, v = get(d, "time"), get(d, "OUTP")
            m = t > 40e-9
            vw = v[m]
            p2p = float(vw.max() - vw.min())
            per = np.diff(crossings(t[m], vw))
            per = per[(per > 50e-12) & (per < 200e-12)]
            if len(per):
                f_GHz = float(1 / np.mean(per[-60:])) / 1e9
        except Exception as e:
            print(f"  {tag}: parse error {e}")
        freq[tag] = (f_GHz, p2p)
        print(f"  C {tag}: fVCO={f_GHz:.5f} GHz  p2p={p2p:.3f} V")
    res = []
    for (vm, nr, u) in [(2, 7, 1), (2, 16, 1), (1, 5, 1), (2, 7, 4)]:
        k0, k1 = f"c_vm{vm}_nr{nr}x{u}_en0.0", f"c_vm{vm}_nr{nr}x{u}_en0.8"
        if k0 in freq and k1 in freq:
            f0, f1 = freq[k0][0], freq[k1][0]
            res.append({"vapmod": vm, "nr": nr, "units": u, "f0_GHz": f0,
                        "f1_GHz": f1, "df_MHz": (f0 - f1) * 1e3,
                        "df_per_unit_MHz": (f0 - f1) * 1e3 / u,
                        "p2p_off_V": freq[k0][1], "p2p_on_V": freq[k1][1]})
            print(f"  C vm{vm} nr={nr} x{u}/side: f {f0:.5f}->{f1:.5f} GHz, "
                  f"df = {(f0-f1)*1e3:.3f} MHz ({(f0-f1)*1e3/u:.3f} MHz/unit), "
                  f"p2p {freq[k0][1]:.2f}->{freq[k1][1]:.2f} V")
    return res


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    dry = "--dry" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    if not (OUT / "netlist").exists():
        (OUT / "netlist").symlink_to(ROOT / "netlist")
    all_res = {}
    if what in ("a", "all"):
        print("== Test A: cfmom C(nr,lr) ==")
        all_res["A"] = test_a(dry)
    if what in ("b", "all"):
        print("== Test B: switched unit dC_eff ==")
        all_res["B"] = test_b(dry)
    if what in ("c", "all"):
        print("== Test C: VCO bank df ==")
        all_res["C"] = test_c(dry)
    if what == "cparse":
        print("== Test C re-parse ==")
        all_res["C"] = test_c_parse()
    if not dry:
        old = {}
        if (OUT / "results.json").exists():
            old = json.loads((OUT / "results.json").read_text())
        old.update({k: v for k, v in all_res.items() if v})
        (OUT / "results.json").write_text(json.dumps(old, indent=1))


if __name__ == "__main__":
    main()
