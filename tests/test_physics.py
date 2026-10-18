"""Frames, Fourier and pattern speeds on synthetic galaxies with known answers."""
import numpy as np
import pytest
from conftest import galaxy

from dbars import fourier, frames, patternspeed
from dbars.fourier import wrap_half_period


def _clean(d):
    k = d["a_form"] > 0
    return d["pos"][k], d["vel"][k], d["mass"][k]


def _intrinsic(kind, **kw):
    """Untilted, unshifted galaxy: phases are in the generator's frame."""
    d, t = galaxy(kind, tilt=False, centre_offset_kpc=(0, 0, 0), vel_offset_kms=(0, 0, 0), n_wind=0, **kw)
    pos, vel, mass = _clean(d)
    return frames.cylindrical(pos, vel), mass, t


@pytest.fixture(scope="module")
def double_frame():
    d, t = galaxy("double")
    pos, vel, mass = _clean(d)
    return frames.to_galaxy_frame(pos, vel, mass), t


def test_shrinking_sphere_recovers_offset(double_frame):
    g, t = double_frame
    assert np.linalg.norm(g["centre"] - t.centre) < 0.020          # kpc


def test_face_on_recovers_spin_axis(double_frame):
    g, t = double_frame
    axis = g["rotation"].T @ np.array([0, 0, 1.0])                   # +z of the face-on frame, in the input frame
    ang = np.degrees(np.arccos(np.clip(axis @ t.spin_axis, -1, 1)))
    assert ang < 1.0


def test_rotation_to_z_is_proper_and_handles_antiparallel():
    for a in ([0, 0, 1], [0, 0, -1], [1, 0, 0], [0.3, -0.2, -0.9]):
        M = frames.rotation_to_z(a)
        assert np.allclose(M @ M.T, np.eye(3)) and np.isclose(np.linalg.det(M), 1.0)
        assert np.allclose(M @ (np.array(a) / np.linalg.norm(a)), [0, 0, 1])


def test_cylindrical_velocities():
    pos = np.array([[1.0, 0, 0], [0, 2.0, 0]])
    vel = np.array([[0, 5.0, 0], [-3.0, 0, 1.0]])                    # both rotate towards +phi
    R, phi, z, vR, vphi, vz = frames.cylindrical(pos, vel)
    assert np.allclose(R, [1, 2]) and np.allclose(vphi, [5, 3]) and np.allclose(vR, 0) and np.allclose(vz, [0, 1])


def _bar_bins(r, lo, hi):
    return (r > lo) & (r < hi)


def test_fourier_phases_double():
    (R, phi, z, vR, vphi, vz), mass, t = _intrinsic("double")
    edges, rc = fourier.log_bins(0.25, 16.0, 40)
    f = fourier.fourier_profile(R, phi, mass, edges, n_bootstrap=30)
    p = t.params
    for lo, hi, theta in ((0.3, 0.65, p["theta_in"]), (1.5, 3.2, p["theta_out"])):
        b = _bar_bins(rc, lo, hi) & f["valid"]
        d = wrap_half_period(f["phase"][1][b] - theta, 2)
        assert np.all(np.abs(d) < 3 * f["phi2_err"][b] + np.radians(2.0)), np.degrees(d)
        assert np.all(np.abs(f["A"][1][b] - p["eps_in" if hi < 1 else "eps_out"] / 2) < 0.06)


def test_fourier_axisymmetric_disc():
    (R, phi, z, vR, vphi, vz), mass, t = _intrinsic("disc")
    edges, rc = fourier.log_bins(0.25, 16.0, 40)
    f = fourier.fourier_profile(R, phi, mass, edges, n_bootstrap=30)
    A2 = f["A"][1][f["valid"]]
    assert np.median(A2) < 0.03 and A2.max() < 0.08


def test_m2_residual_map_amplitude():
    (R, phi, z, vR, vphi, vz), mass, t = _intrinsic("single")
    m, ext = fourier.m2_residual_map(R, phi, mass, 4.0, 0.2)
    assert ext == [-4, 4, -4, 4]
    # inside the bar delta_2 = eps cos 2(phi - theta): peak ~ eps = 0.7
    assert 0.5 < np.nanpercentile(m, 99) < 0.9


@pytest.mark.parametrize("kind", ["double", "single"])
def test_pattern_speeds(kind):
    (R, phi, z, vR, vphi, vz), mass, t = _intrinsic(kind)
    p = t.params
    edges, rc = fourier.log_bins(0.25, 16.0, 40)
    om = patternspeed.omega_profile(R, phi, vR, vphi, mass, rc, rc * np.diff(np.log(edges)), n_bootstrap=30)
    regions = [(1.5, 3.2, p["omega_out"])] + ([(0.3, 0.65, p["omega_in"])] if p["eps_in"] > 0 else [])
    for lo, hi, true in regions:
        b = _bar_bins(rc, lo, hi) & om["valid"]
        assert b.sum() >= 3
        assert np.all(np.abs(om["omega"][b] / true - 1) < 0.10), om["omega"][b]
        assert np.all(om["omega_err"][b] > 0)


def test_pattern_speed_sign_convention():
    """Omega_p > 0 for a pattern rotating with the stars (towards +phi); reversing all velocities flips the sign
    in the same frame, and the face-on rotation (z along L) makes it positive again."""
    (R, phi, z, vR, vphi, vz), mass, t = _intrinsic("single")
    o = patternspeed.omega_annulus(R, phi, vR, vphi, mass, 1.0, 3.2, n_bootstrap=0)
    assert o["omega"] > 0
    assert abs(o["omega"] / t.params["omega_out"] - 1) < 0.1
    o_rev = patternspeed.omega_annulus(R, phi, -vR, -vphi, mass, 1.0, 3.2, n_bootstrap=0)
    assert np.isclose(o_rev["omega"], -o["omega"])
    d, _ = galaxy("single", tilt=False, centre_offset_kpc=(0, 0, 0), vel_offset_kms=(0, 0, 0), n_wind=0)
    pos, vel, m = _clean(d)
    g = frames.to_galaxy_frame(pos, -vel, m)
    Rg, phig, _, vRg, vphig, _ = frames.cylindrical(g["pos"], g["vel"])
    assert patternspeed.omega_annulus(Rg, phig, vRg, vphig, m, 1.0, 3.2, n_bootstrap=0)["omega"] > 0


def test_dehnen_window_smooth():
    R = np.linspace(0.5, 3.0, 2001)
    W, dW = patternspeed.dehnen_window(R, 1.0, 2.0)
    assert W.max() == pytest.approx(1.0, abs=1e-3) and W[0] == 0 and W[-1] == 0
    num = np.gradient(W, R)
    assert np.allclose(num[5:-5], dW[5:-5], atol=0.02)
