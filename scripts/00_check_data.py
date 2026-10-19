#!/usr/bin/env python
"""Report which catalog chunks, offsets files and npz files exist per snapshot (no particles are loaded).

Writes <out>/checks/snap<SNAP>.json and prints a short table to paste into the chat. Expected galaxies are the
catalog subhaloes with SubhaloMassType[4] >= selection.mstar_min (the extraction's M* > 1e10 cut [memory]).
Usage: python scripts/00_check_data.py --config config/cluster.yaml [--snap 99]   (default: all config snapshots)
"""
import json
import sys
from pathlib import Path

import numpy as np

from dbars.cli import base_parser, setup
from dbars.io import catalogs, particles
from dbars.runio import atomic_write_text


def check_snap(cfg, snap):
    base, offd = cfg["paths"]["base"], cfg["paths"]["offsets"]
    rep = dict(snap=snap, group_dir=str(catalogs.group_dir(base, snap)))
    try:
        hdr = catalogs.read_header(base, snap)
        rep.update(a=hdr["a"], z=hdr["z"], num_files=int(hdr["NumFiles"]))
        present, missing = catalogs.list_chunks(base, snap, int(hdr["NumFiles"]))
        rep.update(chunks_present=len(present), chunks_missing=missing[:50], n_chunks_missing=len(missing))
    except (OSError, KeyError) as e:
        rep.update(header_error=repr(e), chunks_present=0, n_chunks_missing=None)
        missing = None
    op = catalogs.offsets_path(offd, snap)
    rep["offsets_file"] = str(op)
    rep["offsets_exists"] = op.exists()
    dirs = particles.npz_dirs(cfg, snap)
    rep["npz_dirs"] = [str(d) for d in dirs]
    have = set()
    for d in dirs:
        n0 = len(have)
        if d.is_dir():
            for p in d.glob("subhalo_*_stars.npz"):
                try:
                    have.add(int(p.name.split("_")[1]))
                except ValueError:
                    pass
        rep[f"npz_new_in_{d.name}"] = len(have) - n0
    rep["npz_count"] = len(have)
    if missing == []:
        cat = catalogs.read_catalog(base, snap, ("SubhaloMassType",))
        ms = catalogs.to_physical("SubhaloMassType", cat["Subhalo"]["SubhaloMassType"], rep["a"],
                                  float(hdr.get("HubbleParam", cfg["sim"]["h"])))[:, 4]
        expected = set(np.flatnonzero(ms >= float(cfg["selection"]["mstar_min"])).tolist())
        rep["expected"] = len(expected)
        rep["missing_npz"] = len(expected - have)
        rep["missing_npz_sids"] = sorted(expected - have)[:50]
        rep["unexpected_npz"] = len(have - expected)
    rep["complete"] = bool(missing == [] and rep["offsets_exists"] and rep.get("missing_npz") == 0)
    return rep


def main(argv=None):
    p = base_parser(__doc__.splitlines()[0], snap=False)
    p.add_argument("--snap", type=int, action="append", help="snapshot (repeatable; default: config snapshots)")
    args = p.parse_args(argv)
    cfg, root = setup(args)
    snaps = args.snap or cfg["snapshots"]
    print(f"{'snap':>4} {'z':>6} {'chunks':>9} {'offsets':>7} {'npz':>5} {'expect':>6} {'miss':>5} {'extra':>5} complete")
    for s in snaps:
        r = check_snap(cfg, int(s))
        atomic_write_text(root / "checks" / f"snap{s}.json", json.dumps(r, indent=1, default=str))
        ch = f"{r['chunks_present']}/{r.get('num_files', '?')}"
        z = f"{r['z']:.4f}" if "z" in r else "?"
        print(f"{s:>4} {z:>6} {ch:>9} {str(r['offsets_exists']):>7} {r['npz_count']:>5} {r.get('expected', '?'):>6} "
              f"{r.get('missing_npz', '?'):>5} {r.get('unexpected_npz', '?'):>5} {r['complete']}")
        if "header_error" in r:
            print(f"     header: {r['header_error']}")
    print(f"reports in {root / 'checks'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
