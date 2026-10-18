"""Per-galaxy analysis chain: frame -> Fourier -> Omega_p -> ellipse -> maps -> classification.

Pure function of the cleaned star particles and the config (no file I/O); ``scripts/02_galaxy_diagnostics.py``
writes its result to ``profiles/snap<SNAP>/sub_<SID>.h5``.
"""

from __future__ import annotations

import numpy as np

from . import classify, ellipse, fourier, frames, maps, patternspeed


def analyse_galaxy(stars: dict, cfg: dict, softening_kpc: float, seed: int = 0, do_ellipse: bool = True) -> dict:
    """Run the full diagnostic chain on one galaxy.

    ``stars``: dict with pos [kpc], vel [km/s], mass [Msun] (wind particles already removed), physical units.
    ``softening_kpc``: physical stellar softening at this snapshot. Returns a dict with:
    ``frame`` (centre [kpc], bulk_vel [km/s], rotation 3x3, r_half [kpc]), ``profile`` (r, edges [kpc], A [4, n],
    phase [4, n] rad, A2, phi2, A2_err, phi2_err, npart, valid, omega, omega_err, growth, growth_err, A2w,
    omega_valid), ``ellipse`` (sma [kpc], eps, pa [deg], ...), ``ellipse_runs``, ``maps`` (name -> (map, extent)),
    ``m2_map``, ``classification`` (see :func:`dbars.classify.classify_profiles`) and ``segment_omega``
    (Omega_p over each chosen bar with the Dehnen et al. window).
    """
    an = cfg["analysis"]
    g = frames.to_galaxy_frame(stars["pos"], stars["vel"], stars["mass"], rmin=an["shrink_sphere_final_kpc"],
                               j_radius_rhalf=an["j_radius_rhalf"])
    pos, vel, mass = g["pos"], g["vel"], stars["mass"]
    R, phi, z, vR, vphi, vz = frames.cylindrical(pos, vel)

    rmax = an["rmax_rhalf"] * g["r_half"]
    edges, rc = fourier.log_bins(an["rmin_kpc"], rmax, an["n_rbins"])
    f = fourier.fourier_profile(R, phi, mass, edges, n_bootstrap=an["n_bootstrap"],
                                min_particles=an["min_particles_per_bin"], seed=seed)
    dln = np.diff(np.log(edges))
    om = patternspeed.omega_profile(R, phi, vR, vphi, mass, rc, an["omega_window_bins"] * rc * dln,
                                    n_bootstrap=an["n_bootstrap"], seed=seed + 1, a2_min=an["omega_a2_min"],
                                    snr_min=an["omega_a2_snr"], min_particles=an["min_particles_per_bin"])
    prof = dict(r=rc, edges=edges, A=f["A"], phase=f["phase"], A2=f["A"][1], phi2=f["phase"][1],
                A2_err=f["A2_err"], phi2_err=f["phi2_err"], npart=f["npart"], valid=f["valid"],
                omega=om["omega"], omega_err=om["omega_err"], growth=om["growth"], growth_err=om["growth_err"],
                A2w=om["A2w"], omega_valid=om["valid"])

    hw, pix = an["map_halfwidth_kpc"], an["map_pixel_kpc"]
    mp = maps.galaxy_maps(pos, vel, mass, vR, halfwidth=hw, pixel=pix, zoom_halfwidth=an["zoom_halfwidth_kpc"])
    m2, m2_ext = fourier.m2_residual_map(R, phi, mass, hw, 2 * pix)

    if do_ellipse:
        el = ellipse.fit_isophotes(mp["density"][0], pix, sma0=an["ellipse_sma0_kpc"],
                                   minsma=an["ellipse_minsma_kpc"], maxsma=an["ellipse_maxsma_kpc"],
                                   step=an["ellipse_step"])
        peaks = ellipse.ellipse_bars(el, eps_min=cfg["classify"]["ellipse_eps_min"],
                                     pa_tol_deg=cfg["classify"]["ellipse_pa_tol_deg"])
    else:
        el, peaks = None, None

    cls = classify.classify_profiles(prof, cfg, softening_kpc, ellipse_runs=peaks)
    seg_om = {}
    for k in ("outer", "inner"):
        r0, r1 = cls[f"{k}_r_start"], cls[f"{k}_r_end"]
        if np.isfinite(r0) and np.isfinite(r1) and r1 > r0:
            seg_om[k] = patternspeed.omega_annulus(R, phi, vR, vphi, mass, max(r0, 0.5 * an["rmin_kpc"]), r1,
                                                   n_bootstrap=an["n_bootstrap"], seed=seed + 2)
    return dict(frame=dict(centre=g["centre"], bulk_vel=g["bulk_vel"], rotation=g["rotation"], r_half=g["r_half"]),
                profile=prof, ellipse=el, ellipse_runs=peaks, maps=mp, m2_map=(m2.astype(np.float32), m2_ext),
                classification=cls, segment_omega=seg_om, n_stars=int(len(mass)))
