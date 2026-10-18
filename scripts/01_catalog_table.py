#!/usr/bin/env python
"""Build the per-snapshot catalog table (selection window, central flag, masses, SFR, r_half, npz path).

Catalogs only, single process. Writes <out>/catalog/snap<SNAP>.parquet and prints a one-line summary.
Usage: python scripts/01_catalog_table.py --config config/cluster.yaml --snap 99
"""
import os
import sys

from dbars.cli import base_parser, setup
from dbars.sample import load_table


def main(argv=None):
    args = base_parser(__doc__.splitlines()[0]).parse_args(argv)
    cfg, root = setup(args)
    df = load_table(cfg, args.snap)
    path = root / "catalog" / f"snap{args.snap}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    print(f"snap {args.snap}: {len(df)} galaxies in the mass window, {int(df['central'].sum())} centrals, "
          f"{int(df['has_npz'].sum())} with npz -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
