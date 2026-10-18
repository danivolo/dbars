"""Centring, face-on rotation and cylindrical coordinates.

All positions are physical kpc, velocities km/s, masses Msun. Angles in radians.
"""

from __future__ import annotations

import numpy as np


def shrinking_sphere(pos, mass, r0=10.0, rmin=0.5, shrink=0.8, nmin=500, centre0=None):
    """Shrinking-sphere centre (Power et al. 2003) [kpc].

    Start from ``centre0`` (default: the origin of ``pos``) with radius ``r0`` [kpc]; repeatedly replace the
    centre by the centre of mass of the particles inside the sphere and shrink the radius by ``shrink``,
    until the radius is below ``rmin`` [kpc] or fewer than ``nmin`` particles remain inside.
    Returns the centre (3,) in the frame of ``pos``.
    """
    pos = np.asarray(pos, float)
    mass = np.asarray(mass, float)
    c = np.zeros(3) if centre0 is None else np.asarray(centre0, float).copy()
    r = float(r0)
    while True:
        d = pos - c
        inside = np.einsum("ij,ij->i", d, d) < r * r
        if inside.sum() < nmin:
            break
        m = mass[inside]
        c = (pos[inside] * m[:, None]).sum(0) / m.sum()
        if r <= rmin:
            break
        r = max(r * shrink, rmin)
    return c


def bulk_velocity(pos, vel, mass, r):
    """Mass-weighted mean velocity [km/s] of particles within radius ``r`` [kpc] of the origin of ``pos``."""
    pos, vel, mass = np.asarray(pos, float), np.asarray(vel, float), np.asarray(mass, float)
    inside = np.einsum("ij,ij->i", pos, pos) < r * r
    if not inside.any():
        raise ValueError(f"no particles within {r} kpc")
    m = mass[inside]
    return (vel[inside] * m[:, None]).sum(0) / m.sum()


def half_mass_radius(pos, mass):
    """3D half-mass radius [kpc] about the origin of ``pos``."""
    r = np.sqrt(np.einsum("ij,ij->i", pos, pos))
    order = np.argsort(r)
    cm = np.cumsum(np.asarray(mass, float)[order])
    return float(r[order][np.searchsorted(cm, 0.5 * cm[-1])])


def rotation_to_z(axis):
    """Proper rotation matrix M (det +1) with M @ axis_hat = +z (Rodrigues; minimal rotation).

    The antiparallel case (axis ~ -z) uses a rotation by pi about x, so no reference vector can be collinear.
    """
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(a, z)
    s = np.linalg.norm(v)
    c = float(np.dot(a, z))
    if s < 1e-12:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * K + (1 - c) * (K @ K)


def angular_momentum(pos, vel, mass, r):
    """Total angular momentum [Msun kpc km/s] of particles within ``r`` [kpc] of the origin."""
    inside = np.einsum("ij,ij->i", pos, pos) < r * r
    return (np.cross(pos[inside], vel[inside]) * mass[inside, None]).sum(0)


def face_on_rotation(pos, vel, mass, r):
    """Rotation matrix that aligns the stellar angular momentum inside ``r`` [kpc] with +z.

    ``pos``/``vel`` must already be relative to the centre and bulk velocity. Apply as ``pos @ M.T``.
    """
    L = angular_momentum(pos, vel, mass, r)
    if not np.any(L):
        raise ValueError("zero angular momentum inside r")
    return rotation_to_z(L)


def cylindrical(pos, vel):
    """Cylindrical coordinates in the frame of ``pos`` (z axis = rotation axis).

    Returns R [kpc], phi [rad, in (-pi, pi], counter-clockwise from +x], z [kpc], v_R, v_phi, v_z [km/s].
    v_phi > 0 for rotation towards increasing phi (L_z > 0).
    """
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
    R = np.hypot(x, y)
    phi = np.arctan2(y, x)
    with np.errstate(invalid="ignore", divide="ignore"):
        cp = np.where(R > 0, x / R, 1.0)
        sp = np.where(R > 0, y / R, 0.0)
    vR = vel[:, 0] * cp + vel[:, 1] * sp
    vphi = -vel[:, 0] * sp + vel[:, 1] * cp
    return R, phi, z, vR, vphi, vel[:, 2]


def to_galaxy_frame(pos, vel, mass, r_shrink0=10.0, rmin=0.5, j_radius_rhalf=3.0, nmin=500):
    """Re-centre (shrinking sphere), remove bulk velocity and rotate face-on.

    The angular momentum and the bulk velocity use the stars within ``j_radius_rhalf`` x the 3D half-mass radius.
    Returns a dict with pos, vel (face-on frame), centre [kpc], bulk_vel [km/s], rotation (3x3),
    r_half [kpc] (3D, about the new centre) and j_radius.
    """
    c = shrinking_sphere(pos, mass, r0=r_shrink0, rmin=rmin, nmin=nmin)
    p = pos - c
    r_half = half_mass_radius(p, mass)
    jr = j_radius_rhalf * r_half
    vb = bulk_velocity(p, vel, mass, jr)
    v = vel - vb
    M = face_on_rotation(p, v, mass, jr)
    return dict(pos=p @ M.T, vel=v @ M.T, centre=c, bulk_vel=vb, rotation=M, r_half=r_half, j_radius=jr)
