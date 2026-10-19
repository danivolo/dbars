"""Star-only subhalo cutouts from the TNG API -> the npz layout of the extraction, in physical units, with ParticleIDs.

The download itself is in ``scripts/fetch_cutouts.py`` (the user runs it; this package never calls the API).
Cutout file [memory: TNG API docs; checked on the first download by :func:`convert_cutout`, which fails on a missing field]:
``PartType4/{Coordinates [ckpc/h], Velocities [km/s / sqrt(a)], Masses [1e10 Msun/h], GFM_StellarFormationTime,
GFM_Metallicity, ParticleIDs}``, absolute box coordinates.

Conversion (a, h from the group-catalog header of the snapshot):
pos = wrap(Coordinates - SubhaloPos) * a / h  [physical kpc], vel = Velocities * sqrt(a) [km/s], mass = Masses * 1e10 / h [Msun].
Then, as the legacy extraction did: centre on the mass-weighted centre of the stars within 5 kpc, subtract the
mass-weighted mean velocity of all stars. The npz gets ``units = "physical"`` so the reader applies no further
scale-factor correction (the legacy files lack the key and are corrected, D10).
"""

from __future__ import annotations

import os
from pathlib import Path

import h5py
import numpy as np

STAR_FIELDS = ("Coordinates", "Velocities", "Masses", "GFM_StellarFormationTime", "GFM_Metallicity", "ParticleIDs")


def cutout_url(sim: str, snap: int, sid: int, fields=STAR_FIELDS) -> str:
    return (f"https://www.tng-project.org/api/{sim}/snapshots/{int(snap)}/subhalos/{int(sid)}/cutout.hdf5"
            f"?stars={','.join(fields)}")


def convert_cutout(path, sub_pos_ckpc_h, a: float, h: float, box_ckpc_h: float, r_com_kpc: float = 5.0) -> dict:
    """Read one cutout file and return the npz dict (physical kpc, km/s, Msun; see module docstring).

    ``sub_pos_ckpc_h``: SubhaloPos of the subhalo (raw catalog units). Raises KeyError on a missing field and
    ValueError on an empty cutout.
    """
    with h5py.File(path, "r") as f:
        g = f["PartType4"]
        raw = {k: g[k][()] for k in STAR_FIELDS}
    if len(raw["Masses"]) == 0:
        raise ValueError("cutout has no star particles")
    d = np.asarray(raw["Coordinates"], np.float64) - np.asarray(sub_pos_ckpc_h, np.float64)
    d = (d + 0.5 * box_ckpc_h) % box_ckpc_h - 0.5 * box_ckpc_h
    pos = d * a / h
    vel = np.asarray(raw["Velocities"], np.float64) * np.sqrt(a)
    mass = np.asarray(raw["Masses"], np.float64) * 1e10 / h
    core = np.einsum("ij,ij->i", pos, pos) < r_com_kpc ** 2
    sel = core if core.sum() > 20 else np.ones(len(mass), bool)
    com = (pos[sel] * mass[sel, None]).sum(0) / mass[sel].sum()
    pos -= com
    vel -= (vel * mass[:, None]).sum(0) / mass.sum()
    return dict(pos=pos, vel=vel, mass=mass, a_form=np.asarray(raw["GFM_StellarFormationTime"], np.float64),
                metallicity=np.asarray(raw["GFM_Metallicity"], np.float64),
                particle_ids=np.asarray(raw["ParticleIDs"], np.uint64), com_offset=com,
                cat_pos=np.asarray(sub_pos_ckpc_h, np.float64) * a / h, a=np.float64(a), h=np.float64(h),
                units=np.array("physical"))


def write_npz_atomic(path, data: dict) -> Path:
    """np.savez_compressed to a temporary name in the same directory, fsync, rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, **data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return path
