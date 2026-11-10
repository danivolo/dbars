#!/usr/bin/env python
"""Is the face-on frame right in the inner regions? Tilt of the stellar spin axis inside several radii, per galaxy.

For each ``--sids`` galaxy: re-centre and rotate face-on exactly as step 02 does, then print the angle [deg] between the
angular momentum inside 0.5, 1, 2, 5, 10 kpc and inside the frame radius (3 r_half) and the frame's z axis, plus
the 3D half-mass radius. Reads the particles (login node, a few seconds per galaxy); writes
``<out>/frame_check_snap<SNAP>.csv``. Usage: python scripts/05_frame_check.py --config config/cluster.yaml --snap 99 --out RUNDIR --sids 506151,467415
"""
import csv
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")

from dbars import frames, runio  # noqa: E402
from dbars.cli import base_parser, setup  # noqa: E402
from dbars.io import catalogs, particles  # noqa: E402

RADII = (0.5, 1.0, 2.0, 5.0, 10.0)


def main(argv=None):
    p = base_parser(__doc__.splitlines()[0])
    p.add_argument("--sids", required=True)
    args = p.parse_args(argv)
    cfg, root = setup(args)
    a = catalogs.read_header(cfg["paths"]["base"], args.snap)["a"]
    an = cfg["analysis"]
    rows = []
    for sid in [int(s) for s in args.sids.split(",") if s.strip()]:
        st = particles.load_stars(cfg, args.snap, sid, a=a)
        g = frames.to_galaxy_frame(st["pos"], st["vel"], st["mass"], rmin=an["shrink_sphere_final_kpc"],
                                   j_radius_rhalf=an["j_radius_rhalf"])
        radii = RADII + (g["j_radius"],)
        t = frames.tilt_profile(g["pos"], g["vel"], st["mass"], radii)
        rows.append(dict(sid=sid, r_half_3d=round(g["r_half"], 2), **{f"tilt<{r:.1f}kpc": round(x, 1) for r, x in zip(radii, t)}))
        print(rows[-1], flush=True)
    path = root / f"frame_check_snap{args.snap}.csv"
    runio.atomic_write_text(path, "")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}, key=lambda k: (k != "sid", k)))
        w.writeheader()
        w.writerows(rows)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
