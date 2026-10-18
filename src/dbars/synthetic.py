"""Synthetic disc galaxies with zero, one or two m=2 bars and known pattern speeds.

The particle sets use the same npz layout as the real extraction (``pos``, ``vel``, ``mass``, ``a_form``,
``metallicity``, ``com_offset``, ``cat_pos``), so the reader and the scripts run on them unchanged.

Model (intrinsic frame, disc in the x-y plane, rotation towards +phi, i.e. L_z > 0):

- surface density: an exponential disc (scale ``rd_kpc``) plus an optional nuclear disc (scale ``rd_nuc_kpc``,
  mass fraction ``f_nuc``), so that an inner bar of ~1 kpc holds enough particles; vertical Gaussian of
  scale ``hz_kpc``;
- azimuthal modulation Sigma(R, phi) = Sigma_0(R) [1 + eps(R) cos 2(phi - theta(R))], so A2/A0 = eps/2;
  eps(R) is ``eps_in`` inside the inner bar (R < ``l_in``) and ``eps_out`` over the outer bar
  (``r_out_start`` < R < ``l_out``), with smooth tanh edges of width ``edge_kpc``; theta is ``theta_in`` /
  ``theta_out`` there;
- mean velocities: v_R = 0, v_phi = Omega(R) R, Omega = ``omega_in`` in the inner bar, ``omega_out`` in the outer
  bar, a smooth blend between, and a flat rotation curve ``vflat`` beyond the outer bar. Each pattern therefore
  rotates rigidly at its Omega (the continuity equation holds exactly), plus Gaussian dispersion ``sigma_kms``.

The galaxy is then rotated by a random proper rotation (``tilt``), shifted by ``centre_offset_kpc`` and
``vel_offset_kms``, and wind particles (``a_form <= 0``) are added uniformly in a sphere.

Inner-bar sizes 0.6-1 kpc and the pattern-speed ratio follow the double-bar simulations of
Du, Shen & Debattista (2015, arXiv:1503.02593) in order of magnitude [memory].
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class SynthParams:
    n_part: int = 200_000
    mass_total: float = 5.0e10          # Msun, all disc stars
    rd_kpc: float = 3.0                 # exponential scale length [kpc]
    rmax_kpc: float = 20.0              # truncation [kpc]
    f_nuc: float = 0.15                 # mass fraction in the nuclear disc
    rd_nuc_kpc: float = 0.4             # nuclear-disc scale length [kpc]
    hz_kpc: float = 0.2                 # vertical Gaussian scale [kpc]
    # bars (eps = 0 switches a bar off)
    eps_in: float = 0.0
    l_in: float = 0.8                   # inner-bar end [kpc]
    theta_in: float = 0.0               # inner-bar angle [rad], intrinsic frame
    omega_in: float = 150.0             # km/s/kpc
    eps_out: float = 0.0
    r_out_start: float = 1.3            # outer-bar inner edge [kpc] (the gap separates the bars)
    l_out: float = 3.5                  # outer-bar end [kpc]
    theta_out: float = 0.0              # rad
    omega_out: float = 40.0             # km/s/kpc
    edge_kpc: float = 0.08              # tanh edge width [kpc]
    vflat: float = 200.0                # km/s beyond the outer bar (and for the pure disc)
    sigma_kms: float = 10.0             # isotropic Gaussian dispersion [km/s]
    # frame
    tilt: bool = True                   # random proper rotation of the whole galaxy
    centre_offset_kpc: tuple = (0.12, -0.08, 0.05)
    vel_offset_kms: tuple = (15.0, -10.0, 5.0)
    n_wind: int = 2000
    wind_rmax_kpc: float = 30.0
    seed: int = 1


@dataclass
class SynthTruth:
    params: dict
    centre: np.ndarray                  # kpc, frame of the output positions
    bulk_vel: np.ndarray                # km/s
    rotation: np.ndarray                # 3x3: x_out = rotation @ x_intrinsic + centre
    spin_axis: np.ndarray               # unit vector (output frame) of the intrinsic +z
    extras: dict = field(default_factory=dict)


def _smooth_box(R, r0, r1, w):
    """1 inside (r0, r1), 0 outside, tanh edges of width w [kpc]; r0 <= 0 means no inner edge."""
    up = 1.0 if r0 <= 0 else 0.5 * (1 + np.tanh((R - r0) / w))
    return up * 0.5 * (1 - np.tanh((R - r1) / w))


def eps_theta_profile(R, p: SynthParams):
    """Modulation amplitude eps(R) and angle theta(R) [rad] for radii R [kpc]."""
    win = _smooth_box(R, 0.0, p.l_in, p.edge_kpc)
    wout = _smooth_box(R, p.r_out_start, p.l_out, p.edge_kpc)
    eps = p.eps_in * win + p.eps_out * wout
    if p.eps_in > 0 and p.eps_out > 0:
        theta = np.where(R < 0.5 * (p.l_in + p.r_out_start), p.theta_in, p.theta_out)
    else:
        theta = np.full_like(R, p.theta_in if p.eps_in > 0 else p.theta_out)
    return eps, theta


def omega_profile(R, p: SynthParams):
    """Mean angular velocity Omega(R) [km/s/kpc] for R [kpc] (rigid in each bar, flat curve beyond)."""
    R = np.maximum(R, 1e-3)
    om_flat = p.vflat / R
    if p.eps_in == 0 and p.eps_out == 0:
        return np.minimum(om_flat, p.vflat / 1.0)          # pure disc: solid body inside 1 kpc, flat outside
    if p.eps_out > 0:
        inner = p.omega_in if p.eps_in > 0 else p.omega_out
        rt = 0.5 * (p.l_in + p.r_out_start)
        wt = 0.15 * max(p.r_out_start - p.l_in, 0.1)
        s1 = 0.5 * (1 + np.tanh((R - rt) / wt))
        om = inner * (1 - s1) + p.omega_out * s1
        r_end = p.l_out
    else:
        om = np.full_like(R, p.omega_in)
        r_end = p.l_in
    s2 = 0.5 * (1 + np.tanh((R - (r_end + 3 * p.edge_kpc)) / 0.3))
    return om * (1 - s2) + om_flat * s2


def random_rotation(rng) -> np.ndarray:
    """Uniformly random proper rotation matrix (det = +1), from a random unit quaternion."""
    q = rng.normal(size=4)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def _sample_radii(rng, n, rd, rmax):
    """Radii [kpc] of an exponential surface density exp(-R/rd), truncated at rmax (R ~ Gamma(2, rd))."""
    out = np.empty(0)
    while out.size < n:
        r = rng.gamma(2.0, rd, size=int(1.2 * (n - out.size)) + 10)
        out = np.concatenate([out, r[r < rmax]])
    return out[:n]


def make_galaxy(params: SynthParams | None = None, **kw):
    """Generate one synthetic galaxy.

    Returns ``(data, truth)``: ``data`` is a dict with the npz keys (pos [kpc], vel [km/s], mass [Msun],
    a_form, metallicity, com_offset [kpc], cat_pos [kpc]); ``truth`` a :class:`SynthTruth`.
    Positions/velocities are physical kpc and km/s in an arbitrary (tilted, shifted) frame.
    """
    p = params or SynthParams()
    for k, v in kw.items():
        setattr(p, k, v)
    rng = np.random.default_rng(p.seed)
    n_nuc = int(round(p.f_nuc * p.n_part))
    R = np.concatenate([_sample_radii(rng, p.n_part - n_nuc, p.rd_kpc, p.rmax_kpc),
                        _sample_radii(rng, n_nuc, p.rd_nuc_kpc, p.rmax_kpc)])
    n = R.size
    # azimuths: rejection sampling of 1 + eps cos 2(phi - theta)
    eps, theta = eps_theta_profile(R, p)
    eps = np.clip(eps, 0.0, 0.99)
    phi = np.empty(n)
    todo = np.arange(n)
    while todo.size:
        trial = rng.uniform(0, 2 * np.pi, todo.size)
        acc = rng.uniform(0, 1, todo.size) * (1 + eps[todo]) < 1 + eps[todo] * np.cos(2 * (trial - theta[todo]))
        phi[todo[acc]] = trial[acc]
        todo = todo[~acc]
    z = rng.normal(0, p.hz_kpc, n)
    pos = np.column_stack([R * np.cos(phi), R * np.sin(phi), z])

    om = omega_profile(R, p)
    vphi = om * R + rng.normal(0, p.sigma_kms, n)
    vR = rng.normal(0, p.sigma_kms, n)
    vz = rng.normal(0, p.sigma_kms, n)
    vel = np.column_stack([vR * np.cos(phi) - vphi * np.sin(phi), vR * np.sin(phi) + vphi * np.cos(phi), vz])

    rot = random_rotation(rng) if p.tilt else np.eye(3)
    c = np.asarray(p.centre_offset_kpc, float)
    vb = np.asarray(p.vel_offset_kms, float)
    pos = pos @ rot.T + c
    vel = vel @ rot.T + vb
    mass = np.full(n, p.mass_total / n)
    a_form = rng.uniform(0.1, 1.0, n)
    met = rng.uniform(0.005, 0.03, n)

    if p.n_wind:
        u = rng.normal(size=(p.n_wind, 3))
        u /= np.linalg.norm(u, axis=1)[:, None]
        rw = p.wind_rmax_kpc * rng.uniform(0, 1, p.n_wind) ** (1 / 3)
        pos = np.vstack([pos, c + u * rw[:, None]])
        vel = np.vstack([vel, vb + rng.normal(0, 300.0, (p.n_wind, 3))])
        mass = np.concatenate([mass, np.full(p.n_wind, p.mass_total / n)])
        a_form = np.concatenate([a_form, -rng.uniform(0.0, 1.0, p.n_wind)])  # wind: a_form <= 0
        met = np.concatenate([met, rng.uniform(0.005, 0.03, p.n_wind)])

    data = dict(pos=pos, vel=vel, mass=mass, a_form=a_form, metallicity=met,
                com_offset=c.copy(), cat_pos=np.array([1000.0, 2000.0, 3000.0]))
    truth = SynthTruth(params=asdict(p), centre=c, bulk_vel=vb, rotation=rot, spin_axis=rot[:, 2].copy())
    return data, truth


def preset(kind: str, seed: int = 1, **kw) -> SynthParams:
    """Named configurations: 'disc', 'single', 'double', 'double_corot' (inner Omega = outer Omega)."""
    base = dict(seed=seed)
    if kind == "disc":
        pass
    elif kind == "single":
        base.update(eps_out=0.7, r_out_start=0.0, l_out=3.5, theta_out=0.6)
    elif kind == "double":
        base.update(eps_in=0.7, theta_in=1.4, omega_in=150.0, eps_out=0.7, theta_out=0.3, omega_out=40.0)
    elif kind == "double_corot":
        base.update(eps_in=0.7, theta_in=1.4, omega_in=40.0, eps_out=0.7, theta_out=0.3, omega_out=40.0)
    else:
        raise ValueError(f"unknown preset {kind!r}")
    base.update(kw)
    return SynthParams(**base)


def write_npz(path: str | Path, data: dict) -> Path:
    """Write a galaxy in the extraction's npz layout."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, **data)
    return path
