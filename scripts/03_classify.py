#!/usr/bin/env python
"""Classify all galaxies of a snapshot from their profile files (thresholds from the config, so they can be
re-tuned with --set without touching particles).

Writes <out>/classification_snap<SNAP>.parquet: one row per galaxy with the label, bar parameters and, when the
catalog table is available (<out>/catalog/snap<SNAP>.parquet or --table), the catalog columns.
Usage: python scripts/03_classify.py --config config/cluster.yaml --snap 99 [--profiles DIR] [--set classify.omega_nsigma=5]
"""
import os
import sys
from pathlib import Path

import pandas as pd

from dbars.classify import classify_profiles
from dbars.cli import base_parser, setup
from dbars.io.profiles import read_result

FLAT = ("label", "n_segments", "outer_r_start", "outer_r_end", "outer_a2_peak", "outer_phi2_deg", "outer_omega",
        "outer_omega_err", "inner_r_start", "inner_r_end", "inner_a2_peak", "inner_phi2_deg", "inner_omega",
        "inner_omega_err", "length_ratio", "misalignment_deg", "phase_offset_sigma", "inner_len_soft",
        "inner_marginal", "domega_sigma", "ellipse_outer", "ellipse_inner", "ellipse_agrees")


def main(argv=None):
    p = base_parser(__doc__.splitlines()[0])
    p.add_argument("--profiles", default=None, help="profile dir (default <out>/profiles/snap<SNAP>)")
    p.add_argument("--table", default=None, help="catalog table parquet to merge")
    args = p.parse_args(argv)
    cfg, root = setup(args)
    pdir = Path(args.profiles) if args.profiles else root / "profiles" / f"snap{args.snap}"
    rows, bad = [], 0
    for f in sorted(pdir.glob("sub_*.h5")):
        try:
            r = read_result(f)
            c = classify_profiles(r["profile"], cfg, float(r["attrs"]["softening_kpc"]), ellipse_runs=r["ellipse_runs"])
        except Exception as e:
            bad += 1
            print(f"{f.name}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        row = dict(sid=int(r["attrs"]["sid"]), snap=int(r["attrs"]["snap"]), r_half=float(r["frame"]["r_half"]),
                   n_stars=int(r["attrs"]["n_stars"]), config_hash_02=r["attrs"]["config_hash"],
                   label_02=r["attrs"]["label"])
        row.update({k: c[k] for k in FLAT})
        for k in ("inner", "outer"):
            so = r["segment_omega"].get(k, {})
            row[f"{k}_omega_window_02"] = so.get("omega", float("nan"))
            row[f"{k}_omega_window_err_02"] = so.get("omega_err", float("nan"))
        rows.append(row)
    df = pd.DataFrame(rows)
    table = Path(args.table) if args.table else root / "catalog" / f"snap{args.snap}.parquet"
    if len(df) and table.exists():
        cat = pd.read_parquet(table).drop(columns=["snap"], errors="ignore")
        df = df.merge(cat, on="sid", how="left")
    out = root / f"classification_snap{args.snap}.parquet"
    tmp = out.with_name(f".{out.name}.tmp{os.getpid()}")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(tmp, index=False)
    os.replace(tmp, out)
    counts = df["label"].value_counts().to_dict() if len(df) else {}
    print(f"snap {args.snap}: {len(df)} galaxies classified, {bad} unreadable: {counts} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
