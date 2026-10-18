"""Per-galaxy 3x3 diagnostic figure (a pipeline product, written next to the profiles, not via astroplot.save).

Panels: face-on density (full, inner zoom), m=2 residual; mean v_R, sigma_z, edge-on; A2/A0 and phi_2(R);
Omega_p(R); ellipticity and PA. Detected bar segments are overlaid as ellipses (semi-major axis = segment end,
angle = mean phi_2, axis ratio from the matching isophote run or 0.4). Units: kpc, km/s, km/s/kpc, degrees.
The caller runs ``astroplot.init()`` once (shared look); nothing here sets rcParams.
"""

from __future__ import annotations

import numpy as np
from matplotlib.patches import Ellipse
from matplotlib.ticker import NullFormatter

from astroplot import fig_grid, palette

C_OUT = palette.ROLE["new"]     # outer bar
C_IN = palette.ROLE["alt"]      # inner bar
C_AUX = palette.ROLE["aux"]


def _img(ax, m, ext, cmap, log=False, sym=False, label=""):
    m = np.asarray(m, float)
    if log:
        pos = m[m > 0]
        lo = np.percentile(pos, 5) if pos.size else 1.0
        m = np.log10(np.maximum(m, lo))
        label = f"log {label}"
    kw = {}
    if sym:
        v = np.nanpercentile(np.abs(m), 98) if np.isfinite(m).any() else 1.0
        kw = dict(vmin=-v, vmax=v)
    im = ax.imshow(m, origin="lower", extent=ext, cmap=cmap, interpolation="nearest", **kw)
    cb = ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    cb.set_label(label)
    ax.set_xlabel("x [kpc]")
    ax.set_ylabel("y [kpc]")
    return im


def _bars(cls):
    out = []
    for k, c in (("outer", C_OUT), ("inner", C_IN)):
        L, ph = cls.get(f"{k}_r_end"), cls.get(f"{k}_phi2_deg")
        if L is not None and ph is not None and np.isfinite(L) and np.isfinite(ph):
            out.append((k, L, ph, c))
    return out


def _overlay(ax, cls, runs):
    for k, L, ph, c in _bars(cls):
        q = 0.4
        for r in runs or []:
            if r["a_start"] <= L <= 1.5 * r["a_end"]:
                q = max(1 - r["eps_max"], 0.1)
                break
        ax.add_patch(Ellipse((0, 0), 2 * L, 2 * L * q, angle=ph, fill=False, ec=c, lw=1.5))


def _shade(ax, cls):
    for k, L, ph, c in _bars(cls):
        ax.axvspan(cls[f"{k}_r_start"], L, color=c, alpha=0.12, lw=0)


def diagnostic_figure(res: dict, title: str = ""):
    """3x3 figure from a profile-file dict (:func:`dbars.io.profiles.read_result`). Returns the figure."""
    fig, ax = fig_grid(3, 3, panel=(5.2, 4.4))
    mp, cls, prof = res["maps"], res["classification"], res["profile"]
    runs = res.get("ellipse_runs")

    _img(ax[0, 0], *mp["density"], "magma", log=True, label=r"$\Sigma$ [M$_\odot$/kpc$^2$]")
    _overlay(ax[0, 0], cls, runs)
    _img(ax[0, 1], *mp["density_zoom"], "magma", log=True, label=r"$\Sigma$ [M$_\odot$/kpc$^2$]")
    _overlay(ax[0, 1], cls, runs)
    _img(ax[0, 2], *mp["m2_residual"], "RdBu_r", sym=True, label=r"$\delta_2$")
    _overlay(ax[0, 2], cls, runs)
    _img(ax[1, 0], *mp["vR"], "RdBu_r", sym=True, label=r"$\bar v_R$ [km/s]")
    _img(ax[1, 1], *mp["sigma_z"], "viridis", label=r"$\sigma_z$ [km/s]")
    _img(ax[1, 2], *mp["edge_on"], "magma", log=True, label=r"$\Sigma$ [M$_\odot$/kpc$^2$]")
    ax[1, 2].set_ylabel("z [kpc]")
    ax[1, 2].set_aspect("auto")

    r = prof["r"]
    v = prof["valid"].astype(bool)
    a = ax[2, 0]
    a.errorbar(r[v], prof["A2"][v], yerr=prof["A2_err"][v], color=palette.ROLE["ref"], fmt="o-", ms=3)
    a.set_xscale("log")
    a.set_xlabel("R [kpc]")
    a.set_ylabel(r"$A_2/A_0$")
    _shade(a, cls)
    b = a.twinx()
    b.errorbar(r[v], np.degrees(prof["phi2"][v]), yerr=np.degrees(prof["phi2_err"][v]), color=C_AUX, fmt="s",
               ms=3)
    b.set_ylim(-90, 90)
    b.set_ylabel(r"$\phi_2$ [deg]")

    a = ax[2, 1]
    ov = prof["omega_valid"].astype(bool)
    a.errorbar(r[ov], prof["omega"][ov], yerr=prof["omega_err"][ov], color=palette.ROLE["ref"], fmt="o", ms=3)
    a.plot(r[~ov], prof["omega"][~ov], ".", color=C_AUX)
    for k, L, ph, c in _bars(cls):
        so = res.get("segment_omega", {}).get(k)
        if so and np.isfinite(so.get("omega", np.nan)):
            a.hlines(so["omega"], cls[f"{k}_r_start"], L, color=c, lw=2)
    a.set_xscale("log")
    a.set_xlabel("R [kpc]")
    a.set_ylabel(r"$\Omega_p$ [km/s/kpc]")
    fin = prof["omega"][ov]
    if fin.size:
        lo, hi = np.nanpercentile(fin, [2, 98])
        pad = 0.15 * (hi - lo + 1)
        a.set_ylim(min(lo - pad, 0), hi + pad)
    _shade(a, cls)

    a = ax[2, 2]
    el = res.get("ellipse")
    if el is not None and len(el.get("sma", [])):
        a.set_xscale("log")
        a.plot(el["sma"], el["eps"], "o-", color=palette.ROLE["ref"], ms=3)
        b = a.twinx()
        b.plot(el["sma"], el["pa"], "s", color=C_AUX, ms=3)
        b.set_ylim(-90, 90)
        b.set_ylabel("PA [deg]")
    else:
        a.text(0.5, 0.5, "no isophote fit", transform=a.transAxes, ha="center")
    a.set_xlabel("a [kpc]")
    a.set_ylabel(r"$\epsilon$")
    _shade(a, cls)

    for a in ax[2]:
        if a.get_xscale() == "log":
            a.xaxis.set_minor_formatter(NullFormatter())
    txt = title or ""
    txt += f"  {cls.get('label', '?')}"
    if np.isfinite(cls.get("misalignment_deg", np.nan) or np.nan):
        txt += (f"  ratio={cls['length_ratio']:.2f}  dphi={cls['misalignment_deg']:.0f} deg"
                f"  L_in={cls['inner_len_soft']:.1f} eps_soft")
    fig.text(0.01, 0.995, txt, va="top", ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    return fig
