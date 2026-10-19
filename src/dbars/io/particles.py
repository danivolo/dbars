"""Reader for the extracted star particles (one ``subhalo_<SID>_stars.npz`` per galaxy).

npz layout (legacy `node_worker_stars.py` [verified: read in the script, 2026-10-19]):
``pos`` (N, 3) physical kpc, ``vel`` (N, 3) km/s, ``mass`` Msun, ``a_form`` (formation scale factor; <= 0 marks
wind particles), ``metallicity``, ``com_offset`` [kpc], ``cat_pos``. Positions are centred on the mass-weighted
centre of the stars within 5 kpc, velocities on the mass-weighted mean of all stars.

Scale factor: the extraction (legacy ``node_worker_stars.py``) stored ``Coordinates / h`` and the raw ``Velocities``
[verified: read in the script, 2026-10-19], so the physical values are pos * a [kpc] and vel * sqrt(a) [km/s]
(TNG stores particle velocities as km/s / sqrt(a)). ``particles.correct_scale_factor`` (default true) applies this;
no-op at snap 99. At snap 98 (a = 0.9906) the change is ~1 % in R, ~0.5 % in v, ~0.5 % in Omega.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)
_WARNED: set = set()
KEYS = ("pos", "vel", "mass", "a_form", "metallicity")


def npz_dirs(cfg: dict, snap: int) -> list:
    """Directories searched for the npz files of ``snap``, in order: ``paths.cutouts`` (template with ``{snap}``;
    downloaded star cutouts, physical units, with ParticleIDs), then ``paths.stars_npz[snap]`` (legacy extraction)."""
    p = cfg.get("paths", {})
    out = []
    if p.get("cutouts"):
        out.append(Path(str(p["cutouts"]).format(snap=int(snap))))
    legacy = p.get("stars_npz", {}).get(int(snap))
    if legacy:
        out.append(Path(legacy))
    return out


def npz_path(cfg: dict, snap: int, sid: int) -> Path:
    """Path of the npz of ``sid`` at ``snap``: the first of :func:`npz_dirs` that has it (else the first candidate)."""
    name = f"subhalo_{int(sid)}_stars.npz"
    dirs = npz_dirs(cfg, snap)
    if not dirs:
        raise KeyError(f"no npz directory configured for snap {snap}")
    for d in dirs:
        if (d / name).exists():
            return d / name
    return dirs[0] / name


def clean(data: dict) -> dict:
    """Drop wind particles (a_form <= 0) and non-finite rows; float64 arrays. Returns a new dict."""
    a_form = np.asarray(data["a_form"], float)
    keep = a_form > 0
    for k in ("pos", "vel"):
        keep &= np.all(np.isfinite(np.asarray(data[k], float)), axis=1)
    keep &= np.isfinite(np.asarray(data["mass"], float)) & (np.asarray(data["mass"], float) > 0)
    out = {k: np.asarray(data[k], np.float64)[keep] for k in KEYS if k in data}
    if "particle_ids" in data:
        out["particle_ids"] = np.asarray(data["particle_ids"])[keep]
    out["n_wind"] = int((a_form <= 0).sum())
    out["n_dropped"] = int((~keep).sum())
    for k in ("com_offset", "cat_pos"):
        if k in data:
            out[k] = np.asarray(data[k], np.float64)
    return out


def load_stars_file(path, snap: int, sid: int, a: float | None = None, correct_scale_factor: bool = False) -> dict:
    """Read and clean one npz file. ``a``: scale factor of ``snap`` (from the group-catalog header).

    Returns a dict with pos [kpc], vel [km/s], mass [Msun], a_form, metallicity (wind dropped, float64),
    particle_ids (cutout files only), com_offset, cat_pos, snap, sid, a, n_wind, n_dropped, ``source``
    ('legacy' or 'cutout') and ``scale_factor_corrected`` (True also for cutout files, converted at download).
    Warns once per snapshot when a != 1 (the extraction assumed a = 1).
    """
    with np.load(path) as f:
        data = {k: f[k] for k in f.files}
    missing = [k for k in ("pos", "vel", "mass", "a_form") if k not in data]
    if missing:
        raise KeyError(f"{path}: missing {missing}")
    out = clean(data)
    physical = "units" in data and str(data["units"]) == "physical"     # cutout files: already converted
    out.update(snap=int(snap), sid=int(sid), a=a, scale_factor_corrected=physical, source="cutout" if physical else "legacy")
    if a is not None and abs(a - 1.0) > 1e-6 and not physical:
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
