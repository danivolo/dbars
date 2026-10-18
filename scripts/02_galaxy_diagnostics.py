#!/usr/bin/env python
"""Per-galaxy diagnostics: re-centre, face-on, Fourier, Omega_p, ellipse fits, maps, first classification.

One file per galaxy, <out>/profiles/snap<SNAP>/sub_<SID>.h5, written atomically; finished galaxies are skipped
unless --overwrite. A failed galaxy is logged and skipped. Between galaxies the script stops cleanly (exit 0) if
<out>/output/stop exists and is newer than the job start (RESTARTABLE.md rule 1; the file is left for the other
tasks of the job). Last stdout line: ``done N/M failed K`` (N = galaxies of this
task with a profile file, M = galaxies in the task).
Usage: python scripts/02_galaxy_diagnostics.py --config config/cluster.yaml --snap 99 --sids 11,42 [--log-name c001]
"""
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import pandas as pd  # noqa: E402

from dbars import runio  # noqa: E402
from dbars.analysis import analyse_galaxy  # noqa: E402
from dbars.cli import base_parser, setup  # noqa: E402
from dbars.config import config_hash, softening_kpc  # noqa: E402
from dbars.io import catalogs, particles, profiles  # noqa: E402
from dbars.sample import ordered_sids  # noqa: E402


def task_sids(args, root):
    if args.sids:
        return [int(s) for s in args.sids.split(",") if s.strip()], args.log_name or f"diag_snap{args.snap}"
    i, n = runio.parse_chunk(args.chunk)
    table = args.table or root / "catalog" / f"snap{args.snap}.parquet"
    sids = runio.chunk_sids(ordered_sids(pd.read_parquet(table)), i, n)
    return sids, args.log_name or f"diag_snap{args.snap}_chunk{i:03d}of{n:03d}"


def main(argv=None):
    args = base_parser(__doc__.splitlines()[0], galaxies=True).parse_args(argv)
    cfg, root = setup(args)
    sids, log_name = task_sids(args, root)
    glog = runio.GalaxyLog(root, log_name)
    hdr = catalogs.read_header(cfg["paths"]["base"], args.snap)
    a = hdr["a"]
    soft = softening_kpc(cfg, a)
    meta = dict(snap=args.snap, a=a, softening_kpc=soft, config_hash=config_hash(cfg), git_commit=runio.git_commit(),
                config=cfg["_source"], created=time.strftime("%Y-%m-%dT%H:%M:%S"))
    seed0 = int(cfg.get("run", {}).get("seed", 0))
    rd = os.environ.get("ASTRO_RUNDIR")
    if rd and os.path.realpath(rd) != os.path.realpath(root):    # resume job writing into an earlier run directory
        runio.atomic_write_text(os.path.join(rd, "OUTPUT_ROOT"), f"{root}\n")
    n_ok = n_fail = 0
    stopped = False
    for sid in sids:
        if runio.stop_requested(root):
            glog.line(sid, "stop", 0.0, "stop file found: exiting before this galaxy")
            stopped = True
            break
        out = profiles.profile_path(root, args.snap, sid)
        if out.exists() and not args.overwrite:
            n_ok += 1
            glog.line(sid, "skip", 0.0, "exists")
            continue
        t0 = time.time()
        try:
            stars = particles.load_stars(cfg, args.snap, sid, a=a)
            res = analyse_galaxy(stars, cfg, soft, seed=seed0 + sid)
            profiles.write_result(out, res, dict(meta, sid=sid, n_wind=stars["n_wind"],
                                                 scale_factor_corrected=stars["scale_factor_corrected"]))
            n_ok += 1
            glog.line(sid, "ok", time.time() - t0, res["classification"]["label"])
        except Exception as e:  # a failed galaxy never stops the task
            n_fail += 1
            glog.line(sid, "fail", time.time() - t0, f"{type(e).__name__}: {e}")
    summary = f"done {n_ok}/{len(sids)} failed {n_fail}" + (" stopped" if stopped else "")
    with open(glog.path, "a") as f:
        f.write(summary + "\n")
    print(summary, file=sys.stderr)
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
