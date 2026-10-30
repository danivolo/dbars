#!/usr/bin/env python
"""Write ``<out>/view.json`` (astro.view/1, FORMATS.md §1) from the step-02 logs of a run.

Reads only the new log lines (byte offsets kept in ``<out>/output/view_state.json``), writes view.json atomically
(tmp + rename). ``--once`` writes once and exits; otherwise loops every ``--interval`` seconds until every galaxy is
accounted for (needs the total; or until ``--max-minutes``), then writes the final file.
Meant to run as a sidecar on the login node or by hand; the analysis tasks never call it, so it cannot slow them.
Total galaxies: ``--total``, else the catalog table of the run (``<out>/catalog/snap<SNAP>.parquet``, galaxies with an
npz), else unknown. Usage: python scripts/write_view.py --config config/cluster.yaml --snap 99 --out RUNDIR [--once]
"""
import json
import sys
import time
from pathlib import Path

from dbars import runio, viewjson
from dbars.cli import base_parser, setup


def total_from_table(root, snap):
    p = Path(root) / "catalog" / f"snap{snap}.parquet"
    if not p.exists():
        return None
    import pandas as pd
    df = pd.read_parquet(p, columns=["has_npz"])
    return int(df["has_npz"].sum())


def step(args, root, state, total, final=False):
    n = viewjson.read_new(state, root / "logs", f"diag_snap{args.snap}*.log")
    ended = final or (total is not None and len(state["sids"]) >= total)
    view = viewjson.build(state, total, args.snap, run=Path(root).name, final=ended)
    runio.atomic_write_text(root / "view.json", json.dumps(view, allow_nan=False, indent=1) + "\n")
    runio.atomic_write_text(root / "output" / "view_state.json", json.dumps(state))
    return n, ended


def main(argv=None):
    p = base_parser(__doc__.splitlines()[0])
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=float, default=120.0, help="seconds between writes (1-5 min)")
    p.add_argument("--total", type=int, default=None)
    p.add_argument("--max-minutes", type=float, default=None)
    args = p.parse_args(argv)
    cfg, root = setup(args)
    root = Path(root)
    sp = root / "output" / "view_state.json"
    state = json.loads(sp.read_text()) if sp.exists() else viewjson.new_state()
    total = args.total or total_from_table(root, args.snap)
    t_end = time.time() + 60 * args.max_minutes if args.max_minutes else None
    while True:
        n, ended = step(args, root, state, total)
        print(f"{time.strftime('%H:%M:%S')} read {n} new lines, {len(state['sids'])} galaxies", flush=True)
        if args.once or ended or (t_end and time.time() > t_end):
            break
        time.sleep(args.interval)
    if not args.once and ended:
        step(args, root, state, total, final=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
