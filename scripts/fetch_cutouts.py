#!/usr/bin/env python
"""Download star-only subhalo cutouts from the TNG API and write them as npz (physical units, with ParticleIDs).

Run by the user on the cluster login node (inside tmux); this repository never calls the API by itself.
Galaxies: the snapshot's catalog table (mass window of the config, built from the group catalogs). By default only
those without any npz yet (legacy or cutout); ``--all`` fetches every one that has no cutout file yet (for
ParticleIDs). Output: ``paths.cutouts`` (``{snap}`` filled in), one ``subhalo_<SID>_stars.npz`` per galaxy, written
atomically; finished galaxies are skipped, so a rerun resumes. Log: ``<cutout dir>/fetch_snap<SNAP>.log``, one line per
galaxy, last line ``done N/M failed K``. The API key comes from ``$TNG_API_KEY`` (never from a file in this repo).
Usage: TNG_API_KEY=... python scripts/fetch_cutouts.py --config config/cluster.yaml --snap 98 [--all] [--workers 4]
"""
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dbars.cli import base_parser, setup
from dbars.io import catalogs, particles
from dbars.io.cutouts import convert_cutout, cutout_url, write_npz_atomic
from dbars.sample import load_table


def fetch(url, dest, key, retries=6, timeout=300):
    """Download ``url`` to ``dest`` (api-key header), with retries and back-off; returns ``dest``."""
    req = urllib.request.Request(url, headers={"api-key": key})
    last = None
    for k in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as fh:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    fh.write(b)
            return dest
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 404):
                break                                   # wrong key or no such subhalo: retrying will not help
            time.sleep(min(10 * 2 ** k, 300))
    raise RuntimeError(f"download failed: {last}")


def one(sid, snap, cfg, key, outdir, sub_pos, a, h):
    out = outdir / f"subhalo_{sid}_stars.npz"
    raw = outdir / ".download" / f"cutout_{snap}_{sid}.hdf5"
    raw.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    fetch(cutout_url(cfg["sim"]["name"], snap, sid), raw, key)
    data = convert_cutout(raw, sub_pos[sid], a, h, float(cfg["sim"]["box_ckpc_h"]))
    write_npz_atomic(out, data)
    raw.unlink()
    return sid, time.time() - t0, len(data["mass"]), out.stat().st_size


def main(argv=None):
    p = base_parser(__doc__.splitlines()[0])
    p.add_argument("--all", action="store_true", help="every galaxy of the table without a cutout file (default: only those without any npz)")
    p.add_argument("--sids", default=None, help="comma-separated subhalo ids instead of the table")
    p.add_argument("--workers", type=int, default=4, help="parallel downloads")
    p.add_argument("--max-galaxies", type=int, default=None)
    args = p.parse_args(argv)
    cfg, _ = setup(args)
    key = os.environ.get("TNG_API_KEY")
    if not key:
        sys.exit("set TNG_API_KEY in the environment")
    if not cfg["paths"].get("cutouts"):
        sys.exit("paths.cutouts is not set in the config")
    outdir = Path(str(cfg["paths"]["cutouts"]).format(snap=args.snap))
    outdir.mkdir(parents=True, exist_ok=True)
    hdr = catalogs.read_header(cfg["paths"]["base"], args.snap)
    a, h = hdr["a"], float(hdr.get("HubbleParam", cfg["sim"]["h"]))
    sub_pos = catalogs.read_catalog(cfg["paths"]["base"], args.snap, ("SubhaloPos",))["Subhalo"]["SubhaloPos"]

    if args.sids:
        todo = [int(s) for s in args.sids.split(",") if s.strip()]
    else:
        df = load_table(cfg, args.snap).sort_values("n_star", ascending=False)
        if args.all:
            todo = [int(s) for s in df["sid"]]
        else:
            todo = [int(s) for s in df.loc[~df["has_npz"], "sid"]]
    todo = [s for s in todo if not (outdir / f"subhalo_{s}_stars.npz").exists()]
    if args.max_galaxies:
        todo = todo[: args.max_galaxies]
    log = outdir / f"fetch_snap{args.snap}.log"
    print(f"snap {args.snap} (a = {a:.5f}): {len(todo)} galaxies to fetch -> {outdir}", flush=True)
    n_ok = n_fail = 0
    t_start = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex, open(log, "a") as lg:
        futs = {ex.submit(one, s, args.snap, cfg, key, outdir, sub_pos, a, h): s for s in todo}
        for i, f in enumerate(as_completed(futs), 1):
            sid = futs[f]
            try:
                _, dt, n, size = f.result()
                n_ok += 1
                line = f"sid={sid} status=ok t={dt:.1f}s n_star={n} bytes={size}"
            except Exception as e:
                n_fail += 1
                line = f"sid={sid} status=fail reason={type(e).__name__}: {e}"
            lg.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")
            lg.flush()
            if i % 20 == 0 or i == len(todo):
                el = time.time() - t_start
                print(f"  {i}/{len(todo)}  failed {n_fail}  elapsed {el / 60:.1f} min  eta {el / i * (len(todo) - i) / 60:.1f} min",
                      flush=True)
        summary = f"done {n_ok}/{len(todo)} failed {n_fail}"
        lg.write(summary + "\n")
    print(summary)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
