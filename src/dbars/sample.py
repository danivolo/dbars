"""Catalog-level sample: one table per snapshot with the galaxies inside the stellar-mass window.

Columns: sid, central, group_m200c [Msun], mstar, mgas [Msun], sfr [Msun/yr], ssfr [1/yr], rhalf_star [kpc],
mbh [Msun], n_star, npz_path ('' if absent), has_npz. Physical units (TNG raw units converted with a and h from
the group-catalog header). M* is SubhaloMassType[4] (all bound stars and wind particles). NOTE: the extraction's
1e10 Msun cut may have used another M* definition; 00_check_data.py compares the two sets.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .io import catalogs

SUB_FIELDS = ("SubhaloMassType", "SubhaloLenType", "SubhaloHalfmassRadType", "SubhaloSFR", "SubhaloGrNr",
              "SubhaloBHMass")
GRP_FIELDS = ("GroupFirstSub", "Group_M_Crit200")


def build_table(cat: dict, cfg: dict, snap: int, npz_dir=None) -> pd.DataFrame:
    """Selection table from a catalog dict of :func:`dbars.io.catalogs.read_catalog` (fields above)."""
    h = float(cat["header"].get("HubbleParam", cfg["sim"]["h"]))
    a = float(cat["header"]["a"])
    S, G = cat["Subhalo"], cat["Group"]
    mtype = catalogs.to_physical("SubhaloMassType", S["SubhaloMassType"], a, h)
    mstar = mtype[:, 4]
    sel = cfg["selection"]
    idx = np.flatnonzero((mstar >= float(sel["mstar_min"])) & (mstar <= float(sel["mstar_max"])))
    grnr = np.asarray(S["SubhaloGrNr"])
    central = catalogs.is_central(idx, grnr, G["GroupFirstSub"])
    if sel.get("centrals_only"):
        idx, central = idx[central], central[central]
    sfr = np.asarray(S["SubhaloSFR"], float)[idx]
    df = pd.DataFrame(dict(
        sid=idx.astype(np.int64),
        central=central.astype(bool),
        group_m200c=catalogs.to_physical("Group_M_Crit200", G["Group_M_Crit200"], a, h)[grnr[idx]],
        mstar=mstar[idx],
        mgas=mtype[idx, 0],
        sfr=sfr,
        ssfr=sfr / mstar[idx],
        rhalf_star=catalogs.to_physical("SubhaloHalfmassRadType", S["SubhaloHalfmassRadType"], a, h)[idx, 4],
        mbh=catalogs.to_physical("SubhaloBHMass", S["SubhaloBHMass"], a, h)[idx],
        n_star=np.asarray(S["SubhaloLenType"])[idx, 4].astype(np.int64),
    ))
    df.insert(0, "snap", int(snap))
    paths = []
    for sid in df["sid"]:
        p = Path(npz_dir) / f"subhalo_{int(sid)}_stars.npz" if npz_dir else None
        paths.append(str(p) if p is not None and p.exists() else "")
    df["npz_path"] = paths
    df["has_npz"] = df["npz_path"] != ""
    return df.reset_index(drop=True)


def load_table(cfg: dict, snap: int) -> pd.DataFrame:
    """Read the catalogs through the config and build the table."""
    cat = catalogs.read_catalog(cfg["paths"]["base"], snap, SUB_FIELDS, GRP_FIELDS)
    npz_dir = cfg["paths"].get("stars_npz", {}).get(int(snap))
    return build_table(cat, cfg, snap, npz_dir)


def ordered_sids(df: pd.DataFrame, require_npz: bool = True):
    """Subhalo ids sorted by cost (star-particle count, descending; ties by sid). With ``require_npz`` only the
    galaxies whose npz exists. This order defines chunks (``runio.chunk_sids``) and the task file."""
    d = df[df["has_npz"]] if require_npz else df
    d = d.sort_values(["n_star", "sid"], ascending=[False, True])
    return [int(s) for s in d["sid"]]
