#!/usr/bin/env python
"""3x3 diagnostic figures for every double_candidate / double_decoupled galaxy plus a random control sample of
the others, and an HTML contact sheet for visual inspection.

Reads <out>/classification_snap<SNAP>.parquet and the profile files. Writes <out>/figures/snap<SNAP>/sub_<SID>.png
(skipped if present unless --overwrite) and <out>/figures/snap<SNAP>/index.html.
Usage: python scripts/04_plot_candidates.py --config config/cluster.yaml --snap 99 [--control-frac 0.05]
"""
import html
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import astroplot  # noqa: E402
from dbars.cli import base_parser, setup  # noqa: E402
from dbars.io.profiles import profile_path, read_result  # noqa: E402
from dbars.plotting import diagnostic_figure  # noqa: E402

COLS = ("sid", "label", "mstar", "outer_r_end", "inner_r_end", "length_ratio", "misalignment_deg",
        "inner_len_soft", "inner_marginal", "inner_omega", "outer_omega", "domega_sigma", "ellipse_agrees")


def pick(df, frac, seed):
    dbl = df[df["label"].str.startswith("double")]
    rest = df[~df["label"].str.startswith("double")]
    n = int(np.ceil(frac * len(rest))) if len(rest) and frac > 0 else 0
    ctrl = rest.sample(n=n, random_state=seed) if n else rest.iloc[:0]
    return pd.concat([dbl.assign(role="candidate"), ctrl.assign(role="control")])


def _fmt(v):
    if isinstance(v, (float, np.floating)):
        return "" if not np.isfinite(v) else (f"{v:.3g}" if abs(v) < 1e4 else f"{v:.2e}")
    return html.escape(str(v))


def contact_sheet(sel, figdir, snap):
    cols = [c for c in COLS if c in sel.columns]
    rows = []
    for _, r in sel.iterrows():
        img = f"sub_{int(r['sid'])}.png"
        cells = "".join(f"<td>{_fmt(r[c])}</td>" for c in cols)
        rows.append(f"<tr class='{r['role']}'><td><a href='{img}'><img src='{img}' width='360'></a></td>"
                    f"<td>{r['role']}</td>{cells}</tr>")
    head = "".join(f"<th>{c}</th>" for c in ["figure", "role"] + cols)
    page = (f"<!doctype html><meta charset='utf-8'><title>bars snap {snap} candidates</title>"
            "<style>body{font-family:sans-serif}td,th{padding:2px 6px;border-bottom:1px solid #ccc;font-size:13px}"
            "tr.control{background:#f3f3f3}</style>"
            f"<h1>snap {snap}: {int((sel['role'] == 'candidate').sum())} candidates, "
            f"{int((sel['role'] == 'control').sum())} controls</h1><table><tr>{head}</tr>{''.join(rows)}</table>")
    path = figdir / "index.html"
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    tmp.write_text(page)
    os.replace(tmp, path)
    return path


def main(argv=None):
    p = base_parser(__doc__.splitlines()[0])
    p.add_argument("--control-frac", type=float, default=0.05)
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args(argv)
    cfg, root = setup(args)
    df = pd.read_parquet(root / f"classification_snap{args.snap}.parquet")
    sel = pick(df, args.control_frac, int(cfg.get("run", {}).get("seed", 0)) + args.snap)
    figdir = root / "figures" / f"snap{args.snap}"
    figdir.mkdir(parents=True, exist_ok=True)
    astroplot.init()
    n_new = n_fail = 0
    for _, r in sel.iterrows():
        sid = int(r["sid"])
        png = figdir / f"sub_{sid}.png"
        if png.exists() and not args.overwrite:
            continue
        try:
            res = read_result(profile_path(root, args.snap, sid))
            res["classification"] = {**res["classification"], **{k: r[k] for k in COLS if k in r and k != "sid"}}
            fig = diagnostic_figure(res, title=f"snap {args.snap} sub {sid} ({r['role']})")
            tmp = png.with_name(f".{png.stem}.tmp{os.getpid()}.png")
            fig.savefig(tmp, dpi=80)  # pipeline product, one per galaxy: not astroplot.save (brief, "Figures")
            plt.close(fig)
            os.replace(tmp, png)
            n_new += 1
        except Exception as e:
            n_fail += 1
            print(f"sub {sid}: {type(e).__name__}: {e}", file=sys.stderr)
    page = contact_sheet(sel, figdir, args.snap)
    print(f"snap {args.snap}: {len(sel)} figures ({n_new} new, {n_fail} failed) -> {page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
