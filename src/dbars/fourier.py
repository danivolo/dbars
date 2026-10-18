"""Azimuthal Fourier profiles A_m(R), phi_m(R) of a face-on particle distribution.

Input coordinates are cylindrical in the face-on frame (``frames.cylindrical``): R [kpc], phi [rad], masses [Msun].
Per annulus: a_m = sum m_i cos(m phi_i), b_m = sum m_i sin(m phi_i), A_m = sqrt(a_m^2 + b_m^2) / a_0,
phi_m = atan2(b_m, a_m) / m [rad], which is the angle of a density maximum of the m-wave, defined modulo 2 pi / m.
"""

from __future__ import annotations

import numpy as np

M_MAX = 4


def log_bins(rmin, rmax, n):
    """``n`` log-spaced annuli between ``rmin`` and ``rmax`` [kpc]: returns (edges[n+1], centres[n]) [kpc]."""
    edges = np.geomspace(rmin, rmax, n + 1)
    return edges, np.sqrt(edges[:-1] * edges[1:])


def wrap_half_period(dphi, m=2):
    """Wrap a phase difference [rad] of an m-fold pattern into (-pi/m, pi/m]."""
    p = 2 * np.pi / m
    return -((-np.asarray(dphi) + p / 2) % p - p / 2)


def _coeffs(ibin, nb, mass, cosm, sinm, w=None):
    mw = mass if w is None else mass * w
    a0 = np.bincount(ibin, mw, nb)
    a = np.stack([np.bincount(ibin, mw * cosm[k], nb) for k in range(M_MAX)])
    b = np.stack([np.bincount(ibin, mw * sinm[k], nb) for k in range(M_MAX)])
    return a0, a, b


def fourier_profile(R, phi, mass, edges, n_bootstrap=100, min_particles=200, seed=0):
    """Fourier amplitudes and phases in annuli.

    Parameters: R [kpc], phi [rad], mass [Msun] (arrays of equal length), ``edges`` [kpc] (n+1),
    ``n_bootstrap`` Poisson-bootstrap resamplings for the errors, ``min_particles`` per bin below which
    a bin is masked (values are still returned).

    Returns a dict with (n = number of bins, m = 1..4 along the first axis of 2-D arrays):
    ``r`` bin centres [kpc], ``edges`` [kpc], ``npart`` particles per bin, ``mass`` [Msun] per bin,
    ``A`` (4, n) = A_m/A_0, ``phase`` (4, n) = phi_m [rad], ``A2_err``, ``phi2_err`` [rad] (bootstrap std),
    ``valid`` (n,) bool (npart >= min_particles).
    """
    R, phi, mass = np.asarray(R, float), np.asarray(phi, float), np.asarray(mass, float)
    edges = np.asarray(edges, float)
    nb = len(edges) - 1
    sel = (R >= edges[0]) & (R < edges[-1])
    R, phi, mass = R[sel], phi[sel], mass[sel]
    ibin = np.clip(np.searchsorted(edges, R, side="right") - 1, 0, nb - 1)
    ms = np.arange(1, M_MAX + 1)[:, None]
    cosm, sinm = np.cos(ms * phi), np.sin(ms * phi)
    a0, a, b = _coeffs(ibin, nb, mass, cosm, sinm)
    with np.errstate(invalid="ignore", divide="ignore"):
        A = np.hypot(a, b) / a0
    phase = np.arctan2(b, a) / ms
    npart = np.bincount(ibin, minlength=nb)

    A2_err = np.full(nb, np.nan)
    phi2_err = np.full(nb, np.nan)
    if n_bootstrap and len(R):
        rng = np.random.default_rng(seed)
        A2b = np.empty((n_bootstrap, nb))
        ph2b = np.empty((n_bootstrap, nb))
        for k in range(n_bootstrap):
            w = rng.poisson(1.0, len(R)).astype(float)
            b0 = np.bincount(ibin, mass * w, nb)
            b2c = np.bincount(ibin, mass * w * cosm[1], nb)
            b2s = np.bincount(ibin, mass * w * sinm[1], nb)
            with np.errstate(invalid="ignore", divide="ignore"):
                A2b[k] = np.hypot(b2c, b2s) / b0
            ph2b[k] = np.arctan2(b2s, b2c) / 2
        A2_err = np.nanstd(A2b, axis=0, ddof=1)
        dph = wrap_half_period(ph2b - phase[1], 2)
        phi2_err = np.sqrt(np.nanmean(dph ** 2, axis=0))
    return dict(r=np.sqrt(edges[:-1] * edges[1:]), edges=edges, npart=npart, mass=a0, A=A, phase=phase,
                A2_err=A2_err, phi2_err=phi2_err, valid=npart >= min_particles)


def m2_residual_map(R, phi, mass, halfwidth, pixel, n_rings=None):
    """Face-on map of the relative m=2 density perturbation delta_2(x, y) (dimensionless).

    The m=2 coefficients are measured in thin rings (width ~ one pixel) and evaluated on the pixel grid:
    delta_2 = 2 (a_2 cos 2phi + b_2 sin 2phi) / a_0, i.e. Sigma = Sigma_0 (1 + delta_2 + other m).
    ``halfwidth``, ``pixel`` [kpc]. Returns (map[ny, nx], extent [x0, x1, y0, y1] in kpc). Map row = y.
    """
    n = int(np.ceil(2 * halfwidth / pixel))
    if n_rings is None:
        n_rings = max(int(np.ceil(halfwidth * np.sqrt(2) / pixel)), 2)
    redges = np.linspace(0, halfwidth * np.sqrt(2), n_rings + 1)
    sel = R < redges[-1]
    ib = np.clip(np.searchsorted(redges, R[sel], side="right") - 1, 0, n_rings - 1)
    m = mass[sel]
    a0 = np.bincount(ib, m, n_rings)
    a2 = np.bincount(ib, m * np.cos(2 * phi[sel]), n_rings)
    b2 = np.bincount(ib, m * np.sin(2 * phi[sel]), n_rings)
    xc = -halfwidth + (np.arange(n) + 0.5) * (2 * halfwidth / n)
    X, Y = np.meshgrid(xc, xc)
    Rp = np.hypot(X, Y)
    Pp = np.arctan2(Y, X)
    ip = np.clip(np.searchsorted(redges, Rp, side="right") - 1, 0, n_rings - 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        d = 2 * (a2[ip] * np.cos(2 * Pp) + b2[ip] * np.sin(2 * Pp)) / a0[ip]
    d[~np.isfinite(d)] = np.nan
    return d, [-halfwidth, halfwidth, -halfwidth, halfwidth]
