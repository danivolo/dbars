"""Per-galaxy result files ``profiles/snap<SNAP>/sub_<SID>.h5`` (atomic write, read back to dicts).

Layout: attrs (sid, snap, a, config_hash, git_commit, n_stars, n_wind, label, created); groups ``frame``
(centre [kpc], bulk_vel [km/s], rotation), ``profile`` (r, edges [kpc], A, phase [rad], A2, phi2, errors, omega,
omega_err [km/s/kpc], ...), ``ellipse`` (sma [kpc], eps, pa [deg]), ``maps/<name>`` (dataset + attr extent [kpc]),
``classification`` (scalar attrs; segments as a JSON attr), ``segment_omega/<inner|outer>`` (attrs).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import h5py
import numpy as np


def profile_path(root, snap: int, sid: int) -> Path:
    return Path(root) / "profiles" / f"snap{int(snap)}" / f"sub_{int(sid)}.h5"


def _attr(v):
    if v is None:
        return "None"
    if isinstance(v, (bool, np.bool_)):
        return np.bool_(v)
    return v


def _unattr(v):
    if isinstance(v, bytes):
        v = v.decode()
    if isinstance(v, str) and v == "None":
        return None
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.generic):
        return v.item()
    return v


def write_result(path, result: dict, meta: dict) -> Path:
    """Write :func:`dbars.analysis.analyse_galaxy` output plus ``meta`` attrs atomically (tmp file, fsync, rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    comp = dict(compression="gzip", compression_opts=4)
    try:
        with h5py.File(tmp, "w") as f:
            for k, v in meta.items():
                f.attrs[k] = _attr(v)
            f.attrs["label"] = result["classification"]["label"]
            f.attrs["n_stars"] = result["n_stars"]
            g = f.create_group("frame")
            for k, v in result["frame"].items():
                g[k] = np.asarray(v)
            g = f.create_group("profile")
            for k, v in result["profile"].items():
                g[k] = np.asarray(v)
            if result.get("ellipse") is not None:
                g = f.create_group("ellipse")
                for k, v in result["ellipse"].items():
                    g[k] = np.asarray(v, float)
                g.attrs["runs"] = json.dumps(result.get("ellipse_runs") or [])
            g = f.create_group("maps")
            allmaps = dict(result["maps"])
            allmaps["m2_residual"] = result["m2_map"]
            for k, (m, ext) in allmaps.items():
                d = g.create_dataset(k, data=np.asarray(m, np.float32), **comp)
                d.attrs["extent"] = np.asarray(ext, float)
            g = f.create_group("classification")
            for k, v in result["classification"].items():
                if k == "segments":
                    g.attrs[k] = json.dumps(v)
                else:
                    g.attrs[k] = _attr(v)
            g = f.create_group("segment_omega")
            for k, d in result.get("segment_omega", {}).items():
                s = g.create_group(k)
                for kk, vv in d.items():
                    s.attrs[kk] = vv
        fd = os.open(tmp, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return path


def read_result(path) -> dict:
    """Read a profile file back: dict with attrs, frame, profile, ellipse (or None), ellipse_runs, maps
    (name -> (map, extent)), classification (dict), segment_omega."""
    out = {}
    with h5py.File(path, "r") as f:
        out["attrs"] = {k: _unattr(v) for k, v in f.attrs.items()}
        out["frame"] = {k: f["frame"][k][()] for k in f["frame"]}
        out["profile"] = {k: f["profile"][k][()] for k in f["profile"]}
        if "ellipse" in f:
            out["ellipse"] = {k: f["ellipse"][k][()] for k in f["ellipse"]}
            out["ellipse_runs"] = json.loads(f["ellipse"].attrs["runs"])
        else:
            out["ellipse"], out["ellipse_runs"] = None, None
        out["maps"] = {k: (f["maps"][k][()], list(f["maps"][k].attrs["extent"])) for k in f["maps"]}
        c = {k: _unattr(v) for k, v in f["classification"].attrs.items()}
        c["segments"] = json.loads(c.get("segments", "[]"))
        out["classification"] = c
        out["segment_omega"] = {k: {kk: _unattr(vv) for kk, vv in f["segment_omega"][k].attrs.items()}
                                for k in f["segment_omega"]}
    return out
