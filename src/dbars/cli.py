"""Command-line plumbing shared by the scripts (argument parsing, config, output root, logging)."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config, output_root


def base_parser(description: str, snap: bool = True, galaxies: bool = False) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--config", required=True, help="YAML config (config/cluster.yaml, config/local_test.yaml)")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="override one config key, e.g. analysis.a2_threshold=0.2 (repeatable)")
    p.add_argument("--out", default=None, help="output root (default: $ASTRO_RUNDIR, else paths.outputs)")
    if snap:
        p.add_argument("--snap", type=int, required=True)
    if galaxies:
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--sids", help="comma-separated subhalo ids")
        g.add_argument("--chunk", help="i/n: chunk i of n of the catalog table (needs --table)")
        p.add_argument("--table", default=None, help="catalog table parquet (for --chunk); default <out>/catalog/snap<SNAP>.parquet")
        p.add_argument("--log-name", default=None, help="log file name under <out>/logs/ (default from the chunk)")
        p.add_argument("--overwrite", action="store_true", help="redo galaxies whose output exists")
    return p


def setup(args):
    """Load the config and resolve the output root; configure logging to stderr."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)
    cfg = load_config(args.config, args.set)
    return cfg, output_root(cfg, args.out)
