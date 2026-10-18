"""Pattern speed Omega_p(R) of the m=2 wave from a single snapshot (continuity-equation method).

Dehnen, Semczuk & Schönrich (2023, MNRAS; arXiv:2211.00674), eq. (10) / (A4b) for m = 2.
With a radial window w(R) and c = sum_i m_i w(R_i) exp(2 i phi_i), the continuity equation gives the time
derivative of c from the current velocities alone:

    dc/dt = sum_i m_i [ w'(R_i) v_R,i + 2 i w(R_i) v_phi,i / R_i ] exp(2 i phi_i)

    Omega_p = Im(conj(c) dc/dt) / (2 |c|^2)          (= (C dS/dt - S dC/dt) / (2 (C^2 + S^2)), c = C + i S)

The real-valued form is the paper's eq. (A4b). The imaginary counterpart Re(conj(c) dc/dt)/|c|^2 = d ln|c| / dt
is the growth rate of the wave amplitude and is returned as ``growth``.

Units: R [kpc], v [km/s] -> Omega_p [km/s/kpc]. Sign convention: phi increases counter-clockwise in the face-on
frame (z along the stellar angular momentum, ``frames.face_on_rotation``), so Omega_p > 0 is a pattern rotating
in the same sense as the stars; a counter-rotating pattern has Omega_p < 0.

The term w' v_R accounts for particles entering and leaving the window; without it (a top-hat annulus) the
estimate is biased by 5-25 % (paper, Sect. 2.3). The windows here are smooth for that reason.
"""

from __future__ import annotations

import numpy as np


def gaussian_window(R, rc, sigma):
    """Gaussian window w(R) and its derivative dw/dR [1/kpc] centred on ``rc`` [kpc] with width ``sigma`` [kpc]."""
    x = (R - rc) / sigma
    w = np.exp(-0.5 * x * x)
    return w, -x / sigma * w


def dehnen_window(R, r0, r1, rm=None):
    """Smooth window of Dehnen et al. (2023, eq. 25) over the annulus [r0, r1] [kpc]; returns (W, dW/dR).

    W = (1 - Q)^2 (1 + 2Q), Q = (R^2 - Rm^2) / (Re^2 - Rm^2), Re = r0 inside Rm and r1 outside; W = 0 for Q >= 1.
    ``rm`` defaults to the geometric middle of the annulus (the paper uses the median radius of the bar particles).
    """
    if rm is None:
        rm = np.sqrt(r0 * r1)
    re = np.where(R < rm, r0, r1)
    den = re * re - rm * rm
    Q = (R * R - rm * rm) / den
    inside = (Q < 1) & (R >= r0) & (R <= r1)
    Qc = np.where(inside, Q, 1.0)
    W = np.where(inside, (1 - Qc) ** 2 * (1 + 2 * Qc), 0.0)
    dWdQ = np.where(inside, -6 * Qc * (1 - Qc), 0.0)
    return W, dWdQ * 2 * R / den


def _terms(mass, w, dw, phi, vR, vphi, R):
    """Per-particle real terms whose (weighted) sums give C, S, dC/dt, dS/dt and sum(m w)."""
    c2, s2 = np.cos(2 * phi), np.sin(2 * phi)
    rad = mass * dw * vR                   # flux term w' v_R
    rot = 2 * mass * w * vphi / R          # 2 w v_phi / R
    mw = mass * w
    # dc/dt = sum (rad + i rot) (c2 + i s2)
    return np.stack([mw * c2, mw * s2, rad * c2 - rot * s2, rad * s2 + rot * c2, mw], axis=-1)


def _reduce(sums):
    """(…, 5) sums -> (…, 3) = Omega_p, growth rate, A2w (eq. A4 of Dehnen et al. 2023 for m = 2)."""
    C, S, Cd, Sd, s0 = np.moveaxis(sums, -1, 0)
    n2 = C * C + S * S
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.stack([(C * Sd - S * Cd) / (2 * n2), (C * Cd + S * Sd) / n2, np.sqrt(n2) / s0], axis=-1)


def _estimate(T, n_bootstrap, rng):
    """Value and Poisson-bootstrap std of (Omega_p, growth, A2w) from the term matrix T (n, 5)."""
    val = _reduce(T.sum(0))
    if not n_bootstrap:
        return val, np.full(3, np.nan)
    B = rng.poisson(1.0, (n_bootstrap, T.shape[0])).astype(np.float64)
    return val, np.nanstd(_reduce(B @ T), axis=0, ddof=1)


def omega_profile(R, phi, vR, vphi, mass, rc, sigma, n_bootstrap=100, seed=0, a2_min=0.05, snr_min=3.0,
                  min_particles=200, cut_sigma=3.0):
    """Omega_p at each radius ``rc`` [kpc] with a Gaussian window of width ``sigma`` [kpc] (scalar or per radius).

    Inputs are the face-on cylindrical coordinates (R [kpc], phi [rad], v_R, v_phi [km/s]) and masses [Msun].
    Returns a dict with ``r`` [kpc], ``omega`` and ``omega_err`` [km/s/kpc], ``growth`` and ``growth_err``
    [km/s/kpc = 1/(0.978 Gyr)], ``A2w`` (window-weighted A2/A0) and ``A2w_err``, ``neff`` (effective particle
    count in the window), and ``valid``: A2w >= ``a2_min``, A2w / A2w_err >= ``snr_min`` and neff >= ``min_particles``.
    Masked bins keep their values.
    """
    R, phi, vR, vphi, mass = (np.asarray(a, float) for a in (R, phi, vR, vphi, mass))
    rc = np.atleast_1d(np.asarray(rc, float))
    sig = np.broadcast_to(np.asarray(sigma, float), rc.shape)
    order = np.argsort(R)
    Rs = R[order]
    keys = ("omega", "growth", "A2w")
    res = {k: np.full(rc.size, np.nan) for k in keys}
    err = {k: np.full(rc.size, np.nan) for k in keys}
    neff = np.zeros(rc.size)
    windows = []
    for j, (r0, s) in enumerate(zip(rc, sig)):
        lo, hi = np.searchsorted(Rs, [max(r0 - cut_sigma * s, 1e-6), r0 + cut_sigma * s])
        idx = order[lo:hi]
        if idx.size < 10:
            continue
        w, dw = gaussian_window(R[idx], r0, s)
        m = mass[idx]
        T = _terms(m, w, dw, phi[idx], vR[idx], vphi[idx], R[idx])
        res["omega"][j], res["growth"][j], res["A2w"][j] = _reduce(T.sum(0))
        neff[j] = (m * w).sum() ** 2 / (m * m * w * w).sum()
        windows.append((j, idx, T))
    if n_bootstrap and windows:
        # one Poisson weight per particle and resampling, shared by all windows (drawn in blocks to bound memory)
        rng = np.random.default_rng(seed)
        boot = np.full((n_bootstrap, rc.size, 3), np.nan)
        block = max(1, min(n_bootstrap, int(2e7 // max(R.size, 1))))
        for k0 in range(0, n_bootstrap, block):
            B = rng.poisson(1.0, (min(block, n_bootstrap - k0), R.size)).astype(np.uint8)
            for j, idx, T in windows:
                boot[k0:k0 + B.shape[0], j] = _reduce(B[:, idx].astype(np.float64) @ T)
        e = np.nanstd(boot, axis=0, ddof=1)
        for i, k in enumerate(keys):
            err[k] = e[:, i]
    with np.errstate(invalid="ignore", divide="ignore"):
        valid = (res["A2w"] >= a2_min) & (res["A2w"] / err["A2w"] >= snr_min) & (neff >= min_particles)
    return dict(r=rc, sigma=np.array(sig), omega=res["omega"], omega_err=err["omega"], growth=res["growth"],
                growth_err=err["growth"], A2w=res["A2w"], A2w_err=err["A2w"], neff=neff, valid=valid)


def omega_annulus(R, phi, vR, vphi, mass, r0, r1, n_bootstrap=100, seed=0):
    """Omega_p [km/s/kpc] over one annulus [r0, r1] [kpc] with the Dehnen et al. (2023) eq. (25) window.

    Used for a whole bar segment. Returns dict(omega, omega_err, growth, growth_err, A2w, A2w_err, n).
    """
    R, phi, vR, vphi, mass = (np.asarray(a, float) for a in (R, phi, vR, vphi, mass))
    sel = (R >= r0) & (R <= r1)
    if sel.sum() < 10:
        return dict(omega=np.nan, omega_err=np.nan, growth=np.nan, growth_err=np.nan, A2w=np.nan,
                    A2w_err=np.nan, n=int(sel.sum()))
    Rr = R[sel]
    w, dw = dehnen_window(Rr, r0, r1)
    T = _terms(mass[sel], w, dw, phi[sel], vR[sel], vphi[sel], Rr)
    (om, gr, a2), e = _estimate(T, n_bootstrap, np.random.default_rng(seed))
    return dict(omega=om, omega_err=e[0], growth=gr, growth_err=e[1], A2w=a2, A2w_err=e[2], n=int(sel.sum()))
