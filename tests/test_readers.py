"""Catalog, offsets and npz readers on tiny fake files."""
import logging

import numpy as np
import pytest
from conftest import H, write_fake_catalog

from dbars import sample, synthetic
from dbars.config import load_config
from dbars.io import catalogs, particles


@pytest.fixture
def fake(tmp_path):
    gal = {2: (2e10, 1000, 3.0), 4: (5e10, 4000, 5.0), 5: (5e11, 9000, 8.0)}   # sid 5 above mstar_max
    write_fake_catalog(tmp_path, 99, gal, a=1.0)
    return tmp_path, gal


def test_header_from_group_file(fake):
    root, _ = fake
    h = catalogs.read_header(root / "output", 99)
    assert h["a"] == 1.0 and h["NumFiles"] == 2 and h["HubbleParam"] == pytest.approx(H)


def test_read_catalog_concatenates_chunks(fake):
    root, gal = fake
    cat = catalogs.read_catalog(root / "output", 99, sample.SUB_FIELDS, sample.GRP_FIELDS)
    nsub = max(gal) + 1 + 3
    assert cat["Subhalo"]["SubhaloMassType"].shape == (nsub, 6)
    assert catalogs.list_chunks(root / "output", 99) == ([0, 1], [])
    ms = catalogs.to_physical("SubhaloMassType", cat["Subhalo"]["SubhaloMassType"], 1.0, H)[:, 4]
    assert ms[4] == pytest.approx(5e10)
    assert catalogs.is_central(np.array([0, 1, 2]), cat["Subhalo"]["SubhaloGrNr"], cat["Group"]["GroupFirstSub"]).tolist() == [True, False, True]


def test_missing_chunk_reported(fake):
    root, _ = fake
    (root / "output/groups_099/fof_subhalo_tab_099.1.hdf5").unlink()
    assert catalogs.list_chunks(root / "output", 99) == ([0], [1])
    with pytest.raises(FileNotFoundError):
        catalogs.read_catalog(root / "output", 99, ("SubhaloMassType",))


def test_offsets_without_header(fake):
    root, _ = fake
    off = catalogs.read_offsets(root / "offsets", 99)
    assert "FileOffsets/Subhalo" in off and not any(k.startswith("Header") for k in off)
    assert catalogs.chunk_of_subhalo([0, 4, 5, 8], off["FileOffsets/Subhalo"]).tolist() == [0, 0, 1, 1]


def test_to_physical_lengths_and_unknown():
    assert catalogs.to_physical("SubhaloPos", [H], 0.5, H)[0] == pytest.approx(0.5)
    with pytest.raises(KeyError):
        catalogs.to_physical("SomethingNew", [1.0], 1.0, H)


def test_sample_table(fake, repo):
    root, gal = fake
    cfg = load_config(repo / "config/default.yaml")
    cat = catalogs.read_catalog(root / "output", 99, sample.SUB_FIELDS, sample.GRP_FIELDS)
    df = sample.build_table(cat, cfg, 99, npz_dir=root / "nowhere")
    assert df["sid"].tolist() == [2, 4]
    assert np.allclose(df["mstar"], [2e10, 5e10]) and np.allclose(df["rhalf_star"], [3.0, 5.0])
    assert df["central"].tolist() == [True, True] and not df["has_npz"].any()
    assert np.allclose(df["ssfr"], 1.0 / df["mstar"])


def test_npz_reader_drops_wind_and_warns(tmp_path, caplog):
    data, _ = synthetic.make_galaxy(synthetic.preset("disc", n_part=2000, n_wind=100))
    p = synthetic.write_npz(tmp_path / "subhalo_7_stars.npz", data)
    s = particles.load_stars_file(p, 99, 7, a=1.0)
    assert s["n_wind"] == 100 and len(s["mass"]) == 2000 and np.all(s["a_form"] > 0)
    assert s["pos"].dtype == np.float64 and s["sid"] == 7
    particles._WARNED.discard(42)
    with caplog.at_level(logging.WARNING):
        s1 = particles.load_stars_file(p, 42, 7, a=0.9)
        particles.load_stars_file(p, 42, 7, a=0.9)
    assert sum("extraction used a = 1" in r.message for r in caplog.records) == 1
    assert not s1["scale_factor_corrected"] and np.allclose(s1["pos"], s["pos"])
    s2 = particles.load_stars_file(p, 42, 7, a=0.9, correct_scale_factor=True)
    assert np.allclose(s2["pos"], 0.9 * s["pos"]) and np.allclose(s2["vel"], np.sqrt(0.9) * s["vel"])
