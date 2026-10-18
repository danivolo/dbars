"""Reader for the extracted star particles (one ``subhalo_<SID>_stars.npz`` per galaxy).

npz layout (earlier extraction pipeline, [memory: from the user; to be checked against the legacy scripts]):
``pos`` (N, 3) physical kpc, ``vel`` (N, 3) km/s, ``mass`` Msun, ``a_form`` (formation scale factor; <= 0 marks
wind particles), ``metallicity``, ``com_offset`` [kpc], ``cat_pos``. Positions are centred on the mass-weighted
centre of the stars within 5 kpc, velocities on the mass-weighted mean of all stars.

Scale factor: the extraction converted units with a = 1. NOTE: assumed here that it applied pos_ckpc_h / h and
vel_raw * 1, so the exact physical values are pos * a and vel * sqrt(a) (TNG particle velocities are stored as
km/s / sqrt(a)). This is right only if that assumption holds; check the legacy extraction script before enabling
``particles.correct_scale_factor``. At snap 98 (a ~ 0.99) the change is ~1 % in R, ~0.5 % in v, ~0.5 % in Omega.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)
_WARNED: set = set()
KEYS = ("pos", "vel", "mass", "a_form", "metallicity")


def npz_path(cfg: dict, snap: int, sid: int) -> Path:
    """Path of the npz of subhalo ``sid`` at ``snap`` from ``paths.stars_npz`` (KeyError if the snapshot is absent)."""
    return Path(cfg["paths"]["stars_npz"][int(snap)]) / f"subhalo_{int(sid)}_stars.npz"


def clean(data: dict) -> dict:
    """Drop wind particles (a_form <= 0) and non-finite rows; float64 arrays. Returns a new dict."""
    a_form = np.asarray(data["a_form"], float)
    keep = a_form > 0
    for k in ("pos", "vel"):
        keep &= np.all(np.isfinite(np.asarray(data[k], float)), axis=1)
    keep &= np.isfinite(np.asarray(data["mass"], float)) & (np.asarray(data["mass"], float) > 0)
    out = {k: np.asarray(data[k], np.float64)[keep] for k in KEYS if k in data}
    out["n_wind"] = int((a_form <= 0).sum())
    out["n_dropped"] = int((~keep).sum())
    for k in ("com_offset", "cat_pos"):
        if k in data:
            out[k] = np.asarray(data[k], np.float64)
    return out


def load_stars_file(path, snap: int, sid: int, a: float | None = None, correct_scale_factor: bool = False) -> dict:
    """Read and clean one npz file. ``a``: scale factor of ``snap`` (from the group-catalog header).

    Returns a dict with pos [kpc], vel [km/s], mass [Msun], a_form, metallicity (wind dropped, float64),
    com_offset, cat_pos, snap, sid, a, n_wind, n_dropped and ``scale_factor_corrected`` (bool).
    Warns once per snapshot when a != 1 (the extraction assumed a = 1).
    """
    with np.load(path) as f:
        data = {k: f[k] for k in f.files}
    missing = [k for k in ("pos", "vel", "mass", "a_form") if k not in data]
    if missing:
        raise KeyError(f"{path}: missing {missing}")
    out = clean(data)
    out.update(snap=int(snap), sid=int(sid), a=a, scale_factor_corrected=False)
    if a is not None and abs(a - 1.0) > 1e-6:
        if snap not in _WARNED:
            _WARNED.add(snap)
            log.warning("snap %d: a = %.5f but the extraction used a = 1 (%s)", snap, a,
                        "correcting pos*a, vel*sqrt(a)" if correct_scale_factor else "NOT corrected")
        if correct_scale_factor:
            out["pos"] = out["pos"] * a
            out["vel"] = out["vel"] * np.sqrt(a)
            out["scale_factor_corrected"] = True
    return out


def load_stars(cfg: dict, snap: int, sid: int, a: float | None = None) -> dict:
    """:func:`load_stars_file` for the npz of ``sid`` at ``snap`` found through the config."""
    return load_stars_file(npz_path(cfg, snap, sid), snap, sid, a=a,
                           correct_scale_factor=bool(cfg.get("particles", {}).get("correct_scale_factor", False)))
