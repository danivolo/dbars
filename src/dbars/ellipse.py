"""Isophote (ellipse) fits on face-on surface-density maps, and the double-bar signature in them.

A bar shows up as a local maximum of the ellipticity eps(a) with a roughly constant position angle across the
maximum; a double bar shows two such maxima at different PA (Erwin 2004, A&A 415, 941; arXiv:astro-ph/0310806).
Semi-major axes a in kpc, PA in degrees in (-90, 90], counter-clockwise from the +x axis of the face-on frame
(the same convention as the Fourier phase phi_2).
"""

from __future__ import annotations

import warnings

import numpy as np

_EMPTY = dict(sma=np.array([]), eps=np.array([]), pa=np.array([]), eps_err=np.array([]), pa_err=np.array([]))


def wrap_pa_deg(pa):
    """Wrap a position angle [deg] into (-90, 90]."""
    return -((-np.asarray(pa, float) + 90.0) % 180.0 - 90.0)


def fit_isophotes(image, pixel, sma0=1.0, minsma=0.2, maxsma=8.0, step=0.1, smooth_pix=2.0, maxgerr=1.0):
    """Fit ellipses with ``photutils.isophote`` to ``image`` (face-on map, row = y, centre = galaxy centre).

    ``pixel`` [kpc]; ``sma0``, ``minsma``, ``maxsma`` [kpc]; ``step`` is the geometric growth of a.
    The fit runs on log10 of the map smoothed by a Gaussian of ``smooth_pix`` pixels (the contours are the same; on
    linear maps the gradient test stopped most fits outside a nuclear component, see DECISIONS), with photutils
    ``maxgerr`` relaxed to 1.
    Returns a dict of arrays: sma [kpc], eps, pa [deg], eps_err, pa_err [deg]. On any failure the arrays are
    empty (fits fail often on noisy maps; callers treat empty as NaN profiles).
    """
    from photutils.isophote import Ellipse, EllipseGeometry
    from scipy.ndimage import gaussian_filter

    img = np.nan_to_num(np.asarray(image, float))
    if smooth_pix:
        img = gaussian_filter(img, smooth_pix)
    pos = img[img > 0]
    if pos.size < 10:
        return {k: v.copy() for k, v in _EMPTY.items()}
    img = np.log10(np.maximum(img, 0) + pos.min())
    ny, nx = img.shape
    x0, y0 = (nx - 1) / 2.0, (ny - 1) / 2.0
    maxsma_pix = min(maxsma / pixel, 0.95 * min(x0, y0))
    try:
        geom = EllipseGeometry(x0, y0, sma0 / pixel, 0.3, 0.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            iso = Ellipse(img, geom).fit_image(sma0=sma0 / pixel, minsma=max(minsma / pixel, 1.0),
                                               maxsma=maxsma_pix, step=step, fix_center=True,
                                               maxgerr=maxgerr)
    except Exception:
        return {k: v.copy() for k, v in _EMPTY.items()}
    if len(iso) == 0:
        return {k: v.copy() for k, v in _EMPTY.items()}
    sma = np.asarray(iso.sma) * pixel
    # stop codes 0 (converged), 1 (many flagged points), 2 (max iterations) are kept; 3/4/5/-1 are not
    ok = (sma > 0) & np.isin(np.asarray(iso.stop_code), (0, 1, 2))
    out = dict(sma=sma, eps=np.asarray(iso.eps), pa=wrap_pa_deg(np.degrees(np.asarray(iso.pa))),
               eps_err=np.asarray(iso.ellip_err), pa_err=np.degrees(np.asarray(iso.pa_err)))
    return {k: np.asarray(v, float)[ok] for k, v in out.items()}


def ellipse_bars(prof, eps_min=0.2, pa_tol_deg=10.0, min_points=3):
    """Bar-like runs in an isophote profile: consecutive isophotes with eps >= ``eps_min`` whose PA stays within
    ``pa_tol_deg`` (max - min, unwrapped with period 180 deg).

    ``prof`` from :func:`fit_isophotes`. Returns a list of dicts sorted by radius: a_start, a_end, a_epsmax [kpc],
    eps_max, pa [deg] (circular mean over the run). A double bar gives two runs with different PA (Erwin 2004).
    """
    a, e, pa = prof["sma"], prof["eps"], prof["pa"]
    out = []
    i, n = 0, len(a)
    while i < n:
        if not e[i] >= eps_min:
            i += 1
            continue
        unw = [0.0]
        j = i + 1
        while j < n and e[j] >= eps_min:
            d = float(wrap_pa_deg(pa[j] - pa[i] - unw[-1])) + unw[-1]
            if max(unw + [d]) - min(unw + [d]) > pa_tol_deg:
                break
            unw.append(d)
            j += 1
        if j - i >= min_points:
            sl = slice(i, j)
            k = i + int(np.argmax(e[sl]))
            mpa = 0.5 * np.degrees(np.angle(np.mean(np.exp(2j * np.radians(pa[sl])))))
            out.append(dict(a_start=float(a[i]), a_end=float(a[j - 1]), a_epsmax=float(a[k]), eps_max=float(e[k]),
                            pa=float(mpa)))
            i = j
        else:
            i += 1
    return out
