"""Shared setup for AFE simulations via virtuoso-bridge -> 21 server."""
import json
import os
import sys
from pathlib import Path

AFE = Path(__file__).resolve().parents[1]
os.chdir(AFE)  # make resolve_env_path pick up afe/.env

from dotenv import load_dotenv  # noqa: E402

load_dotenv(AFE / ".env", override=True)

from virtuoso_bridge.spectre.runner import (  # noqa: E402
    SpectreSimulator,
    spectre_mode_args,
)

VA_DIR = AFE / "va"
TRAN_DIR = AFE / "tran"
NET_DIR = AFE / "netlists"
OUT_DIR = AFE / "output"

VA_FILES = sorted(str(p) for p in VA_DIR.glob("*.va"))


def make_sim(timeout=1200, work_dir=None):
    return SpectreSimulator.from_env(
        spectre_args=spectre_mode_args("ax"),
        work_dir=Path(work_dir) if work_dir else OUT_DIR,
        timeout=timeout,
    )


def bake(template: str, **kv) -> str:
    s = template
    for k, v in kv.items():
        s = s.replace(f"__{k}__", v if isinstance(v, str) else f"{v:g}")
    return s


def write_baked(template_path: Path, out_path: Path, **kv):
    text = template_path.read_text()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(bake(text, **kv))
    return out_path


def final_value(result, sig):
    """Last value of a saved waveform (works for scalar-ish saves)."""
    if not result.ok:
        return None
    wf = result.data.get(sig)
    if wf is None:
        return None
    arr = wf if hasattr(wf, "__len__") else [wf]
    if len(arr) == 0:
        return None
    try:
        return float(arr[-1][1]) if isinstance(arr[-1], (list, tuple)) else float(arr[-1])
    except (TypeError, IndexError):
        return None


def save_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=float))
    print(f"[saved] {path}")
