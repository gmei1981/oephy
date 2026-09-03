#!/usr/bin/env python3
"""Extract VCO PN (dBc/Hz) from PSS+pnoise raw dir.

L(f) = 10log10(S_v(f)) - 10log10(A_d^2/2), A_d = differential peak amplitude from td.pss.

Usage: python3 scripts/pn_extract.py <raw_dir> [offset_freq ...]
"""
import re
import sys
from pathlib import Path

import numpy as np


def parse_psf_ascii(path: Path) -> dict:
    """Minimal PSF ascii parser for the pss/pnoise files here."""
    txt = path.read_text(errors="replace")
    head, _, body = txt.partition("VALUE")
    out = {"header": head, "body": body}
    return out


def pnoise_pn(raw: Path) -> tuple[np.ndarray, np.ndarray]:
    """Return (freq_offsets, L_dBc) from pllpnoise.pnoise."""
    txt = (raw / "pllpnoise.pnoise").read_text(errors="replace")
    body = txt.split("VALUE", 1)[1]
    chunks = re.split(r'^"relative frequency"', body, flags=re.M)[1:]
    freqs, tots = [], []
    for c in chunks:
        m = re.match(r"\s*([0-9.eE+-]+)", c)
        freqs.append(float(m.group(1)))
        # total output noise appears as '"out" value' at the end of the chunk (V/sqrt(Hz))
        mo = re.search(r'"out"\s+([0-9.eE+-]+)', c)
        v = float(mo.group(1)) if mo else np.nan
        tots.append(v * v)  # S_v in V^2/Hz
    return np.asarray(freqs), np.asarray(tots)


def pss_differential_amplitude(raw: Path) -> float:
    """Differential peak amplitude from pllpss.td.pss (OUTP-OUTN over one cycle)."""
    txt = (raw / "pllpss.td.pss").read_text(errors="replace")
    body = txt.split("VALUE", 1)[1]
    # value lines: '"name" [ "unit" ] value' — name = first quoted token, value = last float
    name_re = re.compile(r'^"([A-Za-z0-9_.<>\\]+)"')
    val_re = re.compile(r'([0-9.eE+-]+)\s*$')
    t, outp, outn = [], [], []
    for l in body.split("\n"):
        l = l.strip()
        nm = name_re.match(l)
        if not nm:
            continue
        m = val_re.search(l)
        if not m:
            continue
        v = float(m.group(1))
        if nm.group(1) == "time":
            t.append(v)
        elif nm.group(1) == "OUTP":
            outp.append(v)
        elif nm.group(1) == "OUTN":
            outn.append(v)
    if not outp or not outn:
        raise KeyError("OUTP/OUTN not found in td.pss")
    vd = np.asarray(outp) - np.asarray(outn)
    return float(np.max(vd) - np.min(vd)) / 2.0  # peak amplitude


def main():
    raw = Path(sys.argv[1])
    freqs, sv = pnoise_pn(raw)
    A = pss_differential_amplitude(raw)
    L = 10 * np.log10(sv) - 10 * np.log10(A * A / 2.0)
    print(f"fundamental amplitude A_d = {A:.3f} V")
    targets = [float(x) for x in sys.argv[2:]] or [10e3, 100e3, 1e6, 10e6]
    for f0 in targets:
        idx = int(np.argmin(np.abs(freqs - f0)))
        print(f"L({f0/1e3:g} kHz) = {L[idx]:8.1f} dBc/Hz")
    np.savez(raw / "pn_extract.npz", freqs=freqs, L=L, A=A)
    print("saved", raw / "pn_extract.npz")


if __name__ == "__main__":
    main()
