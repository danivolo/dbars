"""Star cutouts: unit conversion, periodic wrap, centring, atomic npz, reader, and the fetch script with a fake download."""
import importlib.util

import h5py
import numpy as np
import pytest
from conftest import H, REPO, write_fake_catalog

from dbars import synthetic
from dbars.io import particles
from dbars.io.cutouts import convert_cutout, write_npz_atomic

BOX = 35000.0


def fake_cutout(path, sub_pos, a, n=3000, seed=0, wind=50):
    """A synthetic galaxy written as a TNG cutout (raw units, absolute box coordinates) around sub_pos [ckpc/h]."""
    d, _ = synthetic.make_galaxy(synthetic.preset("disc", n_part=n, n_wind=wind, seed=seed, tilt=False,
                                                  centre_offset_kpc=(0, 0, 0), vel_offset_kms=(0, 0, 0)))
    with h5py.File(path, "w") as f:
        g = f.create_group("PartType4")
        g["Coordinates"] = (np.asarray(sub_pos) + d["pos"] * H / a) % BOX
        g["Velocities"] = d["vel"] / np.sqrt(a)
        g["Masses"] = d["mass"] * H / 1e10
        g["GFM_StellarFormationTime"] = d["a_form"]
        g["GFM_Metallicity"] = d["metallicity"]
        g["ParticleIDs"] = np.arange(len(d["mass"]), dtype=np.uint64) + 10**9
    return d


def test_convert_wraps_and_converts(tmp_path):
    a = 0.9
    sub_pos = np.array([BOX - 1.0, 5.0, 17000.0])          # galaxy straddles the box edge
    d = fake_cutout(tmp_path / "c.hdf5", sub_pos, a)
    out = convert_cutout(tmp_path / "c.hdf5", sub_pos, a, H, BOX)
    assert np.abs(out["pos"]).max() < 40.0                   # wrapped: no 35 Mpc jumps
    keep = d["a_form"] > 0
    assert np.allclose(out["mass"], d["mass"])
    # physical positions equal the generator's up to the centring shift
    assert np.allclose(out["pos"] + out["com_offset"], d["pos"], atol=1e-6)
    assert np.allclose((out["vel"] * out["mass"][:, None]).sum(0), 0, atol=1e-3 * out["mass"].sum())
    assert np.linalg.norm(out["com_offset"]) < 0.5 and str(out["units"]) == "physical"
    assert out["particle_ids"].dtype == np.uint64 and keep.sum() < len(keep)


def test_reader_no_double_correction(tmp_path):
    a = 0.9
    fake_cutout(tmp_path / "c.hdf5", [100.0, 100.0, 100.0], a)
    out = convert_cutout(tmp_path / "c.hdf5", [100.0, 100.0, 100.0], a, H, BOX)
    p = write_npz_atomic(tmp_path / "subhalo_5_stars.npz", out)
    assert not list(tmp_path.glob(".*tmp*"))
    s = particles.load_stars_file(p, 98, 5, a=a, correct_scale_factor=True)
    keep = out["a_form"] > 0
    assert np.allclose(s["pos"], out["pos"][keep]) and s["source"] == "cutout"
    assert np.array_equal(s["particle_ids"], out["particle_ids"][keep])


def test_missing_field_raises(tmp_path):
    with h5py.File(tmp_path / "bad.hdf5", "w") as f:
        f.create_group("PartType4")["Coordinates"] = np.zeros((3, 3))
    with pytest.raises(KeyError):
        convert_cutout(tmp_path / "bad.hdf5", [0, 0, 0], 1.0, H, BOX)


def test_fetch_script_with_fake_download(tmp_path, monkeypatch):
    root = tmp_path / "synth"
    write_fake_catalog(root, 98, {2: (2e10, 3000, 3.0), 4: (5e10, 3000, 4.0)}, a=0.99)
    legacy = root / "stars_snap98"
    legacy.mkdir(parents=True)
    monkeypatch.setenv("DBARS_SYNTH_DIR", str(root))
    monkeypatch.setenv("TNG_API_KEY", "dummy")
    spec = importlib.util.spec_from_file_location("fetch_cutouts", REPO / "scripts/fetch_cutouts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    urls = []

    def fake_fetch(url, dest, key):
        urls.append(url)
        sid = int(url.split("/subhalos/")[1].split("/")[0])
        fake_cutout(dest, np.array([100.0, 200.0, 300.0]) + sid, 0.99, seed=sid)
        return dest

    monkeypatch.setattr(mod, "fetch", fake_fetch)
    cfg = str(REPO / "config/local_test.yaml")
    leg = ["--set", f"paths.stars_npz.98={legacy}"]
    # galaxy 2 has a legacy npz: by default only 4 is fetched; --all then fetches 2
    synthetic.write_npz(legacy / "subhalo_2_stars.npz", synthetic.make_galaxy(synthetic.preset("disc", n_part=500))[0])
    assert mod.main(["--config", cfg, "--snap", "98", "--workers", "2"] + leg) == 0
    assert len(urls) == 1 and "/snapshots/98/subhalos/4/cutout.hdf5?stars=Coordinates," in urls[0] and "ParticleIDs" in urls[0]
    cut = root / "cutouts_snap98"
    assert (cut / "subhalo_4_stars.npz").exists() and not (cut / ".download/cutout_98_4.hdf5").exists()
    assert mod.main(["--config", cfg, "--snap", "98", "--all"] + leg) == 0
    assert len(urls) == 2 and (cut / "subhalo_2_stars.npz").exists()
    assert mod.main(["--config", cfg, "--snap", "98", "--all"] + leg) == 0 and len(urls) == 2   # resume: nothing left
    assert (cut / "fetch_snap98.log").read_text().strip().endswith("done 0/0 failed 0")
    # the reader now prefers the cutout file over the legacy one
    from dbars.config import load_config
    c = load_config(cfg, [f"paths.stars_npz.98={legacy}"])
    assert particles.npz_path(c, 98, 2) == cut / "subhalo_2_stars.npz"
