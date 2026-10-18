import pytest

from dbars.config import ConfigError, config_hash, load_config, output_root, softening_kpc


def test_default_loads(repo):
    cfg = load_config(repo / "config/default.yaml")
    assert cfg["analysis"]["n_rbins"] == 40
    assert cfg["snapshots"] == [99, 98]


def test_cluster_includes_default(repo, monkeypatch):
    monkeypatch.setenv("HOME", "/home/someone")
    cfg = load_config(repo / "config/cluster.yaml")
    assert cfg["analysis"]["a2_threshold"] == 0.15
    assert cfg["paths"]["stars_npz"][99] == "/home/someone/bars/extracted_galaxies"


def test_env_expansion_and_default(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("DBARS_SYNTH_DIR", str(tmp_path))
    cfg = load_config(repo / "config/local_test.yaml")
    assert cfg["paths"]["stars_npz"][99] == f"{tmp_path}/stars_snap99"
    monkeypatch.delenv("DBARS_SYNTH_DIR")
    cfg = load_config(repo / "config/local_test.yaml")
    assert cfg["paths"]["base"].endswith("scratch/bars/synthetic/output")


def test_unset_env_without_default_fails(tmp_path, repo):
    p = tmp_path / "c.yaml"
    p.write_text(f"include: {repo}/config/default.yaml\npaths:\n  outputs: ${{SURELY_NOT_SET_XYZ}}\n")
    with pytest.raises(ConfigError):
        load_config(p)


def test_overrides(repo):
    cfg = load_config(repo / "config/default.yaml", ["analysis.a2_threshold=0.2", "snapshots=[99]"])
    assert cfg["analysis"]["a2_threshold"] == 0.2
    assert cfg["snapshots"] == [99]
    with pytest.raises(ConfigError):
        load_config(repo / "config/default.yaml", ["selection.mstar_min=1e12"])


def test_output_root_order(repo, monkeypatch, tmp_path):
    cfg = load_config(repo / "config/cluster.yaml")
    monkeypatch.delenv("ASTRO_RUNDIR", raising=False)
    assert str(output_root(cfg)).endswith("astro/runs/bars/manual")
    monkeypatch.setenv("ASTRO_RUNDIR", str(tmp_path / "rd"))
    assert output_root(cfg) == tmp_path / "rd"
    assert output_root(cfg, tmp_path / "x") == tmp_path / "x"


def test_hash_ignores_paths(repo):
    a = load_config(repo / "config/cluster.yaml")
    b = load_config(repo / "config/local_test.yaml")
    assert config_hash(a) != config_hash(b)  # n_bootstrap and snapshots differ
    c = load_config(repo / "config/cluster.yaml", ["paths.outputs=/elsewhere"])
    assert config_hash(a) == config_hash(c)


def test_softening(repo):
    cfg = load_config(repo / "config/default.yaml")
    assert softening_kpc(cfg, 1.0) == pytest.approx(0.288)
    assert softening_kpc(cfg, 1 / 3) == pytest.approx(0.575 / 3)
