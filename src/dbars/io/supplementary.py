"""Readers for TNG supplementary catalogues used as independent comparisons.

``morphs_kinematic_bars.hdf5`` (Zana et al. 2022, arXiv:2206.04693; MORDOR kinematic decomposition and bars, TNG50-1,
M* >~ 1e9 Msun, snapshots 6-99). Per ``Snapshot_<N>``: SubhaloID, Barred (bool), BarSize (2, N) [physical kpc],
BarStrength (2, N), QualityFlags (3, N), StellarMass [Msun]; -1 where no bar is found.
Row meaning from the TNG data specifications page, section (t) [verified: read there 2026-10-19; the page lists the two
estimates in this order but does not state the index mapping explicitly]:
BarSize = (R_Phi, R_peak), BarStrength = (A2max(R), A2max(<R)), QualityFlags = (k_rot, sigma_z/sigma_R, M_b1/M_b2).
NOTE: check the row order against the paper before relying on R_Phi vs R_peak individually.
"""

from __future__ import annotations

import h5py
import numpy as np
import pandas as pd


def read_zana_bars(path, snap: int) -> pd.DataFrame:
    """One row per subhalo of ``snap``: sid, zana_barred, zana_r_phi, zana_r_peak [kpc], zana_a2max, zana_a2max_cum,
    zana_krot, zana_sigz_sigR, zana_mb_ratio (NaN where the catalogue has -1)."""
    with h5py.File(path, "r") as f:
        g = f[f"Snapshot_{int(snap)}"]
        size = np.asarray(g["BarSize"][()], float)
        stren = np.asarray(g["BarStrength"][()], float)
        q = np.asarray(g["QualityFlags"][()], float)
        df = pd.DataFrame(dict(sid=np.asarray(g["SubhaloID"][()], np.int64), zana_barred=np.asarray(g["Barred"][()], bool),
                               zana_r_phi=size[0], zana_r_peak=size[1], zana_a2max=stren[0], zana_a2max_cum=stren[1],
                               zana_krot=q[0], zana_sigz_sigR=q[1], zana_mb_ratio=q[2]))
    num = [c for c in df.columns if c not in ("sid", "zana_barred")]
    df[num] = df[num].where(df[num] != -1.0)
    return df
