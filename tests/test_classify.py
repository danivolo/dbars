"""Classifier labels on synthetic galaxies, and the ellipse signature."""
import numpy as np
import pytest
from conftest import galaxy

from dbars import analysis, classify, ellipse, frames, maps
from dbars.config import load_config


@pytest.fixture(scope="module")
def cfg():
    from conftest import REPO
    return load_config(REPO / "config/default.yaml", ["analysis.n_bootstrap=30"])


def _run(kind, cfg, **kw):
    d, t = galaxy(kind, **kw)
    k = d["a_form"] > 0
    stars = {x: d[x][k] for x in ("pos", "vel", "mass")}
    return analysis.analyse_galaxy(stars, cfg, 0.288, do_ellipse=False), t


@pytest.mark.parametrize("kind,label", [("disc", "unbarred"), ("single", "single"),
                                        ("double", "double_decoupled"), ("double_corot", "double_candidate")])
def test_labels(kind, label, cfg):
    r, t = _run(kind, cfg)
    assert r["classification"]["label"] == label, r["classification"]["segments"]


def test_double_parameters(cfg):
    r, t = _run("double", cfg)
    c = r["classification"]
    p = t.params
    true_mis = np.degrees(classify.wrap_half_period(p["theta_in"] - p["theta_out"], 2))
    assert abs(c["misalignment_deg"] - true_mis) < 5
    assert abs(c["inner_r_end"] - p["l_in"]) < 0.15 and abs(c["outer_r_end"] - p["l_out"]) < 0.4
    assert c["length_ratio"] == pytest.approx(c["inner_r_end"] / c["outer_r_end"])
    assert c["inner_len_soft"] == pytest.approx(c["inner_r_end"] / 0.288)
    assert abs(r["segment_omega"]["inner"]["omega"] / p["omega_in"] - 1) < 0.1
    assert abs(r["segment_omega"]["outer"]["omega"] / p["omega_out"] - 1) < 0.1


def test_marginal_flag(cfg):
    r, _ = _run("double", cfg)
    c = classify.classify_profiles(r["profile"], cfg, softening_kpc=0.5)   # 1.0 kpc = 2 softenings
    assert c["inner_marginal"]


def test_find_segments_phase_jump():
    r = np.arange(10.0)
    edges = np.arange(11.0) - 0.5
    A2 = np.full(10, 0.3)
    phi = np.radians([0, 1, -1, 0, 40, 41, 39, 40, 41, 40])
    segs = classify.find_segments(r, edges, A2, phi, np.ones(10, bool), 0.15, 10.0, 3)
    assert segs == [(0, 3), (4, 9)]
    # wrap-around at +-90 deg is one plateau
    phi = np.radians([88, 89, -89, -88, 89])
    assert classify.find_segments(r[:5], edges[:6], A2[:5], phi, np.ones(5, bool), 0.15, 10.0, 3) == [(0, 4)]


def test_ellipse_double_signature(cfg):
    """Isophote fits show two constant-PA runs at the two bar angles; the classifier reports agreement."""
    d, t = galaxy("double")
    k = d["a_form"] > 0
    g = frames.to_galaxy_frame(d["pos"][k], d["vel"][k], d["mass"][k])
    img, _ = maps.surface_density(g["pos"][:, 0], g["pos"][:, 1], d["mass"][k], 10.0, 0.1)
    prof = ellipse.fit_isophotes(img, 0.1)
    runs = ellipse.ellipse_bars(prof, 0.2, 10.0)
    assert len(runs) >= 2
    r, _ = _run("double", cfg)
    c = classify.classify_profiles(r["profile"], cfg, 0.288, ellipse_runs=runs)
    assert c["label"] == "double_decoupled" and c["ellipse_agrees"] is True


def test_ellipse_failure_returns_empty():
    prof = ellipse.fit_isophotes(np.zeros((50, 50)), 0.1)
    assert prof["sma"].size == 0 and ellipse.ellipse_bars(prof) == []


def test_outer_disc_segment_is_not_a_bar(cfg):
    """A bar plus an m=2 segment that starts beyond bar_start_max_rhalf * r_half must not become a 'double' (D22)."""
    r, _ = _run("single", cfg)
    prof = r["profile"]
    n = len(prof["r"])
    rr = prof["r"]
    A2, phi, valid = np.array(prof["A2"], float), np.array(prof["phi2"], float), np.ones(n, bool)
    far = rr > 3 * r["frame"]["r_half"]
    A2[far] = 0.5
    phi[far] = 1.2
    mod = dict(prof, A2=A2, phi2=phi, valid=valid)
    with_rule = classify.classify_profiles(mod, cfg, 0.288, r_half=r["frame"]["r_half"])
    no_rule = classify.classify_profiles(mod, dict(cfg, classify=dict(cfg["classify"], bar_start_max_rhalf=None)), 0.288)
    assert with_rule["label"] == "single" and with_rule["outer_r_start"] <= r["frame"]["r_half"]
    assert no_rule["n_segments"] > with_rule["n_segments"]


def test_marginal_inner_bar_is_not_a_double(cfg):
    r, _ = _run("double", cfg)
    ok = classify.classify_profiles(r["profile"], cfg, softening_kpc=0.288)
    small = classify.classify_profiles(r["profile"], cfg, softening_kpc=0.5)      # inner bar ~2 softenings
    assert ok["label"] == "double_decoupled" and small["label"] == "double_marginal" and small["inner_marginal"]


def test_decoupled_needs_omega_plateaus(cfg):
    r, _ = _run("double", cfg)
    prof = dict(r["profile"])
    c0 = classify.classify_profiles(prof, cfg, 0.288)
    ob = (prof["r"] > c0["outer_r_start"]) & (prof["r"] < c0["outer_r_end"])
    om = np.array(prof["omega"], float)
    om[ob] = om[ob].mean() * (1 + 0.8 * np.linspace(-1, 1, ob.sum()))      # Omega_p running through the outer bar
    c1 = classify.classify_profiles(dict(prof, omega=om), cfg, 0.288)
    assert c0["label"] == "double_decoupled" and c1["outer_omega_chi2"] > cfg["classify"]["omega_plateau_chi2"]
    assert c1["label"] == "double_candidate"


def test_tilted_core_is_not_a_double(cfg):
    r, _ = _run("double", cfg)
    assert r["frame"]["core_tilt_deg"] < 5          # the synthetic galaxy is a flat disc: frame axis = inner spin axis
    c0 = classify.classify_profiles(r["profile"], cfg, 0.288, core_tilt_deg=3.0)
    c1 = classify.classify_profiles(r["profile"], cfg, 0.288, core_tilt_deg=45.0)
    assert c0["label"] == "double_decoupled" and c1["label"] == "tilted_core" and c1["core_tilt_deg"] == 45.0
