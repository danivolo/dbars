"""Face-on and edge-on maps from particles (face-on frame: z along the stellar angular momentum).

Positions physical kpc, velocities km/s, masses Msun. Maps are arrays indexed [row = y (or z), column = x],
with ``extent = [x0, x1, y0, y1]`` in kpc (matplotlib ``imshow(..., origin="lower", extent=extent)``).
"""

from __future__ import annotations

import numpy as np


def _grid(halfwidth, pixel, halfheight=None):
    hh = halfwidth if halfheight is None else halfheight
    nx = max(int(np.ceil(2 * halfwidth / pixel)), 1)
    ny = max(int(np.ceil(2 * hh / pixel)), 1)
    return np.linspace(-halfwidth, halfwidth, nx + 1), np.linspace(-hh, hh, ny + 1)


def surface_density(x, y, mass, halfwidth, pixel, halfheight=None):
    """Projected mass density [Msun/kpc^2] on a (2 halfwidth) x (2 halfheight) kpc grid of ``pixel`` kpc."""
    ex, ey = _grid(halfwidth, pixel, halfheight)
    H, _, _ = np.histogram2d(y, x, bins=[ey, ex], weights=mass)
    return H / ((ex[1] - ex[0]) * (ey[1] - ey[0])), [ex[0], ex[-1], ey[0], ey[-1]]


def mean_map(x, y, value, mass, halfwidth, pixel, min_mass=0.0):
    """Mass-weighted mean of ``value`` per pixel (units of ``value``); NaN where the pixel mass <= min_mass."""
    ex, ey = _grid(halfwidth, pixel)
    M, _, _ = np.histogram2d(y, x, bins=[ey, ex], weights=mass)
    V, _, _ = np.histogram2d(y, x, bins=[ey, ex], weights=mass * value)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = V / M
    out[M <= min_mass] = np.nan
    return out, [ex[0], ex[-1], ey[0], ey[-1]]


def dispersion_map(x, y, value, mass, halfwidth, pixel, min_count=10):
    """Mass-weighted dispersion of ``value`` per pixel (units of ``value``); NaN with fewer than min_count particles."""
    ex, ey = _grid(halfwidth, pixel)
    N, _, _ = np.histogram2d(y, x, bins=[ey, ex])
    M, _, _ = np.histogram2d(y, x, bins=[ey, ex], weights=mass)
    V, _, _ = np.histogram2d(y, x, bins=[ey, ex], weights=mass * value)
    V2, _, _ = np.histogram2d(y, x, bins=[ey, ex], weights=mass * value * value)
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = V / M
        out = np.sqrt(np.maximum(V2 / M - mu * mu, 0.0))
    out[N < min_count] = np.nan
    return out, [ex[0], ex[-1], ey[0], ey[-1]]


def galaxy_maps(pos, vel, mass, vR, halfwidth=10.0, pixel=0.1, zoom_halfwidth=2.0, edge_halfheight=3.0,
                kin_pixel=None):
    """The map set stored per galaxy and drawn in the diagnostic figure.

    Returns a dict of (map float32, extent) pairs: ``density`` (face-on, Msun/kpc^2), ``density_zoom``
    (inner ``zoom_halfwidth`` kpc at pixel/2), ``vR`` (mean radial velocity, km/s), ``sigma_z`` (km/s),
    ``edge_on`` (x-z projection, Msun/kpc^2). ``kin_pixel`` [kpc] defaults to 2 x pixel for the kinematic maps.
    """
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
    kp = kin_pixel or 2 * pixel
    out = {}
    out["density"] = surface_density(x, y, mass, halfwidth, pixel)
    out["density_zoom"] = surface_density(x, y, mass, zoom_halfwidth, pixel / 2)
    out["vR"] = mean_map(x, y, vR, mass, halfwidth, kp)
    out["sigma_z"] = dispersion_map(x, y, vel[:, 2], mass, halfwidth, kp)
    out["edge_on"] = surface_density(x, z, mass, halfwidth, pixel, halfheight=edge_halfheight)
    return {k: (np.asarray(m, np.float32), e) for k, (m, e) in out.items()}
