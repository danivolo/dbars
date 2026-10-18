"""Plain-h5py readers for the TNG group catalogs and offsets files (``illustris_python`` not needed).

Layout [memory: TNG data release docs + the user's paths; 00_check_data.py confirms on the cluster]:
``<base>/groups_<SNAP:03d>/fof_subhalo_tab_<SNAP:03d>.<CHUNK>.hdf5`` with groups ``Header`` (attributes Redshift,
Time, HubbleParam, NumFiles, Ngroups_ThisFile, Nsubgroups_ThisFile, ...), ``Group`` and ``Subhalo`` (datasets);
``<offsets>/offsets_<SNAP:03d>.hdf5`` with groups ``FileOffsets``, ``Group``, ``Subhalo`` and **no** ``Header``.

Fields are returned in raw catalog units. :func:`to_physical` converts the common ones:
masses 1e10 Msun/h -> Msun; lengths ckpc/h -> physical kpc (x a/h); SubhaloVel is already peculiar km/s;
SubhaloSFR Msun/yr; SubhaloBHMass 1e10 Msun/h. NOTE: units of fields not listed in ``UNITS`` are not converted.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

# field -> kind: "mass" (1e10 Msun/h), "length" (ckpc/h), "none"
UNITS = {
    "SubhaloMass": "mass", "SubhaloMassType": "mass", "SubhaloMassInRadType": "mass",
    "SubhaloMassInHalfRadType": "mass", "SubhaloBHMass": "mass", "Group_M_Crit200": "mass", "GroupMass": "mass",
    "GroupMassType": "mass",
    "SubhaloPos": "length", "SubhaloCM": "length", "SubhaloHalfmassRad": "length", "SubhaloHalfmassRadType": "length",
    "Group_R_Crit200": "length", "GroupPos": "length",
    "SubhaloVel": "none", "SubhaloSFR": "none", "SubhaloLenType": "none", "SubhaloGrNr": "none",
    "GroupFirstSub": "none", "GroupNsubs": "none", "SubhaloFlag": "none", "SubhaloVmax": "none",
}


def group_dir(base, snap: int) -> Path:
    return Path(base) / f"groups_{int(snap):03d}"


def chunk_path(base, snap: int, chunk: int) -> Path:
    return group_dir(base, snap) / f"fof_subhalo_tab_{int(snap):03d}.{int(chunk)}.hdf5"


def offsets_path(offsets_dir, snap: int) -> Path:
    return Path(offsets_dir) / f"offsets_{int(snap):03d}.hdf5"


def read_header(base, snap: int) -> dict:
    """Header attributes of chunk 0 of the group catalog (never from offsets files), plus ``a`` and ``z``."""
    with h5py.File(chunk_path(base, snap, 0), "r") as f:
        h = {k: (v.item() if hasattr(v, "item") and np.size(v) == 1 else np.asarray(v)) for k, v in f["Header"].attrs.items()}
    h["a"] = float(h["Time"])
    h["z"] = float(h["Redshift"])
    return h


def list_chunks(base, snap: int, num_files: int | None = None):
    """(present, missing) chunk indices; ``num_files`` defaults to the header's NumFiles."""
    if num_files is None:
        num_files = int(read_header(base, snap)["NumFiles"])
    present, missing = [], []
    for i in range(num_files):
        (present if chunk_path(base, snap, i).exists() else missing).append(i)
    return present, missing


def read_catalog(base, snap: int, subhalo_fields=(), group_fields=()) -> dict:
    """Concatenate the requested ``Subhalo``/``Group`` datasets over all chunks (raw units).

    Returns {"header": dict, "Subhalo": {field: array}, "Group": {field: array}}. Chunks without subhaloes or
    groups have no datasets and are skipped. Raises FileNotFoundError naming the first missing chunk.
    """
    hdr = read_header(base, snap)
    sub = {k: [] for k in subhalo_fields}
    grp = {k: [] for k in group_fields}
    for i in range(int(hdr["NumFiles"])):
        p = chunk_path(base, snap, i)
        if not p.exists():
            raise FileNotFoundError(p)
        with h5py.File(p, "r") as f:
            for name, want in (("Subhalo", sub), ("Group", grp)):
                if not want or name not in f:
                    continue
                for k in want:
                    if k in f[name]:
                        want[k].append(f[name][k][()])
    cat = dict(header=hdr, Subhalo={}, Group={})
    for name, want in (("Subhalo", sub), ("Group", grp)):
        for k, parts in want.items():
            if not parts:
                raise KeyError(f"field {name}/{k} not found in any chunk of snap {snap}")
            cat[name][k] = np.concatenate(parts)
    return cat


def to_physical(field: str, values, a: float, h: float):
    """Convert a catalog field from raw TNG units to Msun / physical kpc (see module docstring)."""
    kind = UNITS.get(field)
    v = np.asarray(values, np.float64)
    if kind == "mass":
        return v * 1e10 / h
    if kind == "length":
        return v * a / h
    if kind == "none":
        return v
    raise KeyError(f"no unit rule for {field}; add it to UNITS after checking the TNG docs")


def is_central(sid, subhalo_grnr, group_firstsub):
    """True where ``GroupFirstSub[SubhaloGrNr[sid]] == sid`` (vectorised over ``sid``)."""
    sid = np.asarray(sid)
    return np.asarray(group_firstsub)[np.asarray(subhalo_grnr)[sid]] == sid


def read_offsets(offsets_dir, snap: int) -> dict:
    """All datasets of the offsets file as {"Group/Name": array}. The file has no Header (not read)."""
    out = {}
    with h5py.File(offsets_path(offsets_dir, snap), "r") as f:
        def visit(name, obj):
            if isinstance(obj, h5py.Dataset):
                out[name] = obj[()]
        f.visititems(visit)
    return out


def chunk_of_subhalo(sid, file_offsets_subhalo):
    """Group-catalog chunk holding subhalo ``sid`` from ``FileOffsets/Subhalo`` (first subhalo index per chunk)."""
    return np.searchsorted(np.asarray(file_offsets_subhalo), np.asarray(sid), side="right") - 1
