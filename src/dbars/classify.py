"""Bar segments from Fourier/pattern-speed profiles, and the unbarred/single/double label.

A segment is a run of consecutive valid radial bins with A2/A0 > ``a2_threshold`` over which phi_2 stays within
``phase_tol_deg`` (max - min of the unwrapped phases). Bins are scanned outwards; when the next bin would push the
phase range over the tolerance, the segment ends and a new one may start at that bin. A double bar therefore gives
two segments, separated either by a dip in A2 or by the phase jump itself; a single-plateau test would reject it.

Labels (thresholds in the ``classify`` config section):
- ``unbarred``: no segment;
- ``single``: one bar (also two segments without a significant phase offset);
- ``double_candidate``: an inner segment (the strongest one ending inside the start of the outer bar, which is the
  longest segment), with a phase offset
  above ``phase_offset_min_deg`` and ``phase_offset_nsigma`` sigma;
- ``double_decoupled``: as above and |Omega_in - Omega_out| above ``omega_nsigma`` sigma and ``omega_rel_min`` x Omega_out.

Radii in kpc, angles in degrees in the outputs, Omega in km/s/kpc.
"""

from __future__ import annotations

import numpy as np

from .fourier import wrap_half_period

LABELS = ("unbarred", "single", "double_candidate", "double_decoupled")


def _circ_mean_phase(ph, w):
    """Weighted mean of m=2 phases [rad] (period pi)."""
    z = np.sum(w * np.exp(2j * ph))
    return 0.5 * np.angle(z)


def find_segments(r, edges, A2, phi2, valid, a2_threshold, phase_tol_deg, min_bins=3):
    """Bar segments: list of (i0, i1) inclusive bin index ranges (see module docstring).

    ``r`` [kpc] bin centres, ``edges`` [kpc], ``A2`` = A2/A0, ``phi2`` [rad], ``valid`` bool.
    """
    tol = np.radians(phase_tol_deg)
    good = np.asarray(valid, bool) & np.isfinite(A2) & (np.asarray(A2) > a2_threshold)
    segs = []
    i = 0
    n = len(r)
    while i < n:
        if not good[i]:
            i += 1
            continue
        ref = phi2[i]
        unw = [0.0]  # phases relative to the first bin, unwrapped with period pi
        j = i + 1
        while j < n and good[j]:
            d = float(wrap_half_period(phi2[j] - ref - unw[-1], 2)) + unw[-1]
            if max(unw + [d]) - min(unw + [d]) > tol:
                break
            unw.append(d)
            j += 1
        if j - i >= min_bins:
            segs.append((i, j - 1))
            i = j
        else:
            i += 1
    return segs


def segment_properties(seg, prof):
    """Start/end [kpc], peak A2, mean phi2 [deg] and error, mean Omega_p and error [km/s/kpc] of one segment."""
    i0, i1 = seg
    sl = slice(i0, i1 + 1)
    A2 = prof["A2"][sl]
    ph = prof["phi2"][sl]
    pe = np.where(np.isfinite(prof["phi2_err"][sl]) & (prof["phi2_err"][sl] > 0), prof["phi2_err"][sl], np.nan)
    w = 1.0 / pe ** 2 if np.all(np.isfinite(pe)) else np.ones_like(ph)
    mphi = _circ_mean_phase(ph, w)
    mphi_err = float(np.sqrt(1.0 / np.sum(w))) if np.all(np.isfinite(pe)) else np.nan
    om = prof["omega"][sl]
    oe = prof["omega_err"][sl]
    ov = prof["omega_valid"][sl] & np.isfinite(om) & np.isfinite(oe) & (oe > 0)
    if ov.any():
        wo = 1.0 / oe[ov] ** 2
        mom = float(np.sum(wo * om[ov]) / wo.sum())
        mom_err = float(np.sqrt(1.0 / wo.sum()) * np.sqrt(prof.get("omega_corr_bins", 1.0)))
    else:
        mom, mom_err = np.nan, np.nan
    return dict(i0=int(i0), i1=int(i1), r_start=float(prof["edges"][i0]), r_end=float(prof["edges"][i1 + 1]),
                a2_peak=float(np.nanmax(A2)), phi2_deg=float(np.degrees(mphi)),
                phi2_err_deg=float(np.degrees(mphi_err)), omega=mom, omega_err=mom_err, n_omega_bins=int(ov.sum()))


def _ellipse_match(bar, runs, lo, hi, pa_tol):
    """The first ellipse run that overlaps [lo, hi] x the bar length and has PA within ``pa_tol`` of phi_2."""
    L = bar["r_end"]
    for p in runs:
        overlap = p["a_end"] >= lo * L and p["a_start"] <= hi * L
        dpa = abs(float(np.degrees(wrap_half_period(np.radians(p["pa"] - bar["phi2_deg"]), 2))))
        if overlap and dpa <= pa_tol:
            return p
    return None


def classify_profiles(prof, cfg, softening_kpc, ellipse_runs=None):
    """Classify one galaxy.

    ``prof``: dict with r, edges [kpc], A2, phi2 [rad], phi2_err [rad], valid, omega, omega_err [km/s/kpc],
    omega_valid. ``cfg``: the full config (uses ``analysis`` and ``classify``). ``softening_kpc``: physical
    stellar softening at the snapshot. ``ellipse_runs``: list from :func:`dbars.ellipse.ellipse_bars` (or None).

    Returns a flat dict: label, n_segments, segments (list of dicts), and for the chosen bars: outer_/inner_
    r_start, r_end, a2_peak, phi2_deg, omega, omega_err; length_ratio, misalignment_deg (inner - outer, in
    (-90, 90]), phase_offset_sigma, inner_len_soft, inner_marginal, domega_sigma, ellipse_outer, ellipse_inner,
    ellipse_agrees (None when no ellipse fit is available).
    """
    an, cl = cfg["analysis"], cfg["classify"]
    prof = dict(prof)
    prof.setdefault("omega_corr_bins", cl["omega_corr_bins"])
    segs = find_segments(prof["r"], prof["edges"], prof["A2"], prof["phi2"], prof["valid"],
                         an["a2_threshold"], an["phase_tol_deg"], cl["min_segment_bins"])
    props = [segment_properties(s, prof) for s in segs]
    out = dict(label="unbarred", n_segments=len(props), segments=props)
    nan = float("nan")
    for k in ("outer", "inner"):
        for f in ("r_start", "r_end", "a2_peak", "phi2_deg", "omega", "omega_err"):
            out[f"{k}_{f}"] = nan
    out.update(length_ratio=nan, misalignment_deg=nan, phase_offset_sigma=nan, inner_len_soft=nan,
               inner_marginal=False, domega_sigma=nan, ellipse_outer=None, ellipse_inner=None, ellipse_agrees=None)
    if not props:
        return out
    outer = max(props, key=lambda p: p["r_end"] - p["r_start"])
    for f in ("r_start", "r_end", "a2_peak", "phi2_deg", "omega", "omega_err"):
        out[f"outer_{f}"] = outer[f]
    out["label"] = "single"
    inside = [p for p in props if p["r_end"] <= outer["r_start"] + 1e-9]
    lo, hi = cl["ellipse_match"]
    pat = cl["ellipse_pa_match_deg"]
    peaks = ellipse_runs
    if peaks is not None:
        out["ellipse_outer"] = _ellipse_match(outer, peaks, lo, hi, pat) is not None
    if inside:
        inner = max(inside, key=lambda p: p["a2_peak"])
        dphi = float(wrap_half_period(np.radians(inner["phi2_deg"] - outer["phi2_deg"]), 2))
        sig = np.hypot(np.radians(inner["phi2_err_deg"]), np.radians(outer["phi2_err_deg"]))
        nsig = abs(dphi) / sig if sig > 0 else np.inf
        if abs(np.degrees(dphi)) > cl["phase_offset_min_deg"] and nsig > cl["phase_offset_nsigma"]:
            for f in ("r_start", "r_end", "a2_peak", "phi2_deg", "omega", "omega_err"):
                out[f"inner_{f}"] = inner[f]
            out["label"] = "double_candidate"
            out["length_ratio"] = inner["r_end"] / outer["r_end"]
            out["misalignment_deg"] = float(np.degrees(dphi))
            out["phase_offset_sigma"] = float(nsig)
            out["inner_len_soft"] = inner["r_end"] / softening_kpc
            out["inner_marginal"] = bool(out["inner_len_soft"] < cl["inner_marginal_softenings"])
            dom = inner["omega"] - outer["omega"]
            sd = np.hypot(inner["omega_err"], outer["omega_err"])
            if np.isfinite(dom) and sd > 0:
                out["domega_sigma"] = float(abs(dom) / sd)
                if (out["domega_sigma"] > cl["omega_nsigma"]
                        and abs(dom) > cl["omega_rel_min"] * abs(outer["omega"])):
                    out["label"] = "double_decoupled"
            if peaks is not None:
                m_out = _ellipse_match(outer, peaks, lo, hi, pat)
                m_in = _ellipse_match(inner, [p for p in peaks if p is not m_out], lo, hi, pat)
                out["ellipse_inner"] = m_in is not None
    if peaks is not None:
        if out["label"].startswith("double"):
            out["ellipse_agrees"] = bool(out["ellipse_outer"] and out["ellipse_inner"])
        else:
            out["ellipse_agrees"] = bool(out["ellipse_outer"])
    return out
