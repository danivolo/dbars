"""Shared fixtures. Test outputs go to pytest's tmp_path only.

The synthetic galaxies use 1e5 particles (generator default 2e5) to keep the suite fast on the shared laptop.
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from pathlib import Path

import h5py
import numpy as np
import pytest

from dbars import synthetic

REPO = Path(__file__).resolve().parents[1]
N_TEST = 100_000
H = 0.6774


@pytest.fixture
def repo() -> Path:
    return REPO


_CACHE = {}


def galaxy(kind, **kw):
    """Cached synthetic galaxy (data, truth) for a preset name and overrides."""
    key = (kind, tuple(sorted(kw.items())))
    if key not in _CACHE:
        kw.setdefault("n_part", N_TEST)
        _CACHE[key] = synthetic.make_galaxy(synthetic.preset(kind, **kw))
    return _CACHE[key]


def write_fake_catalog(root: Path, snap: int, galaxies: dict, a: float = 1.0, n_chunks: int = 2,
                       extra_small: int = 3):
    """Tiny TNG-like group catalog over ``n_chunks`` chunks plus an offsets file without Header.

    ``galaxies``: sid -> (mstar [Msun], n_star, rhalf [kpc]). Subhalo ids 0..max(sid)+extra_small; ids not in
    ``galaxies`` get a small stellar mass (outside the selection). Each subhalo is the central of its own group,
    except subhalo 1, which is a satellite of group 0.
    """
    nsub = max(galaxies) + 1 + extra_small
    mtype = np.zeros((nsub, 6))
    mtype[:, 4] = 1e8 * H / 1e10
    lent = np.zeros((nsub, 6), np.int64)
    rh = np.ones((nsub, 6)) * H / a
    for sid, (ms, n, r) in galaxies.items():
        mtype[sid, 4] = ms * H / 1e10
        mtype[sid, 0] = 0.3 * ms * H / 1e10
        lent[sid, 4] = n
        rh[sid, 4] = r * H / a
    grnr = np.arange(nsub)
    grnr[1] = 0
    ngrp = nsub
    first = np.arange(ngrp)
    first[1] = -1
    m200 = np.full(ngrp, 1e12 * H / 1e10)
    gdir = root / "output" / f"groups_{snap:03d}"
    gdir.mkdir(parents=True, exist_ok=True)
    sub_split = np.array_split(np.arange(nsub), n_chunks)
    grp_split = np.array_split(np.arange(ngrp), n_chunks)
    for c in range(n_chunks):
        si, gi = sub_split[c], grp_split[c]
        with h5py.File(gdir / f"fof_subhalo_tab_{snap:03d}.{c}.hdf5", "w") as f:
            hd = f.create_group("Header")
            hd.attrs.update(dict(Time=a, Redshift=1 / a - 1, HubbleParam=H, NumFiles=n_chunks,
                                 Nsubgroups_ThisFile=len(si), Ngroups_ThisFile=len(gi),
                                 Nsubgroups_Total=nsub, Ngroups_Total=ngrp))
            s = f.create_group("Subhalo")
            s["SubhaloMassType"] = mtype[si]
            s["SubhaloLenType"] = lent[si]
            s["SubhaloHalfmassRadType"] = rh[si]
            s["SubhaloSFR"] = np.full(len(si), 1.0)
            s["SubhaloGrNr"] = grnr[si]
            s["SubhaloBHMass"] = np.full(len(si), 1e8 * H / 1e10)
            g = f.create_group("Group")
            g["GroupFirstSub"] = first[gi]
            g["Group_M_Crit200"] = m200[gi]
    odir = root / "offsets"
    odir.mkdir(parents=True, exist_ok=True)
    with h5py.File(odir / f"offsets_{snap:03d}.hdf5", "w") as f:   # no Header group, like the real files
        f["FileOffsets/Subhalo"] = np.array([s[0] for s in sub_split])
        f["FileOffsets/Group"] = np.array([g[0] for g in grp_split])
        f["Subhalo/SnapByType"] = np.zeros((nsub, 6), np.int64)
        f["Group/SnapByType"] = np.zeros((ngrp, 6), np.int64)
    return root


def write_synthetic_sample(root: Path, snap: int, kinds: dict, n_part=60_000, a: float = 1.0):
    """Synthetic npz files ``stars_snap<snap>/subhalo_<sid>_stars.npz`` + matching fake catalog under ``root``.

    ``kinds``: sid -> preset name. Returns {sid: truth}.
    """
    truths, gal = {}, {}
    for sid, kind in kinds.items():
        data, truth = synthetic.make_galaxy(synthetic.preset(kind, seed=sid + 1, n_part=n_part))
        synthetic.write_npz(root / f"stars_snap{snap}" / f"subhalo_{sid}_stars.npz", data)
        truths[sid] = truth
        keep = data["a_form"] > 0
        gal[sid] = (float(data["mass"][keep].sum()), int(keep.sum()), 4.0)
    write_fake_catalog(root, snap, gal, a=a)
    return truths


def pytest_configure(config):
    """tmp_path must not live in /tmp (RAM-backed on this laptop): default basetemp under the scratch folder."""
    if not config.option.basetemp:
        base = Path(os.environ.get("DBARS_PYTEST_TMP", Path.home() / "astro/scratch/bars/pytest"))
        base.parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(base)
