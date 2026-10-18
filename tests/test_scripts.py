"""Scripts 00-04 and make_tasks on synthetic data: stop/resume, task coverage, end-to-end smoke test."""
import importlib.util
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from conftest import REPO, write_synthetic_sample

from dbars.io.profiles import read_result


def script(name):
    spec = importlib.util.spec_from_file_location(f"script_{name}", REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CFG = str(REPO / "config/local_test.yaml")
KINDS = {3: "double", 5: "single", 8: "disc"}


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    root = tmp_path_factory.mktemp("synth")
    truths = write_synthetic_sample(root, 99, KINDS, n_part=60_000)
    return root, truths


@pytest.fixture
def env(synth, tmp_path, monkeypatch):
    root, _ = synth
    monkeypatch.setenv("DBARS_SYNTH_DIR", str(root))
    run = tmp_path / "run"
    monkeypatch.setenv("ASTRO_RUNDIR", str(run))
    return run


def _same_results(a: Path, b: Path):
    ra, rb = read_result(a), read_result(b)
    for k in ra["profile"]:
        assert np.array_equal(ra["profile"][k], rb["profile"][k], equal_nan=True), k
    for k in ra["maps"]:
        assert np.array_equal(ra["maps"][k][0], rb["maps"][k][0], equal_nan=True), k
    assert ra["classification"]["label"] == rb["classification"]["label"]


def test_stop_and_resume(env, tmp_path, monkeypatch):
    sids = ",".join(map(str, KINDS))
    s02 = script("02_galaxy_diagnostics")
    ref = tmp_path / "ref"
    assert s02.main(["--config", CFG, "--snap", "99", "--sids", sids, "--out", str(ref), "--set",
                     "analysis.n_bootstrap=5"]) == 0

    cut = tmp_path / "cut"
    orig = s02.analyse_galaxy
    calls = []

    def stop_after_first(*a, **k):        # `astro stop` arriving while the first galaxy is processed
        calls.append(1)
        if len(calls) == 1:
            (cut / "output").mkdir(parents=True, exist_ok=True)
            (cut / "output" / "stop").touch()
        return orig(*a, **k)

    monkeypatch.setattr(s02, "analyse_galaxy", stop_after_first)
    args = ["--config", CFG, "--snap", "99", "--sids", sids, "--out", str(cut), "--set", "analysis.n_bootstrap=5",
            "--log-name", "t"]
    assert s02.main(args) == 0
    assert len(calls) == 1 and (cut / "output" / "stop").exists()      # left for the other tasks of the job
    assert len(list((cut / "profiles/snap99").glob("*.h5"))) == 1
    assert (cut / "logs/t.log").read_text().strip().endswith("done 1/3 failed 0 stopped")
    monkeypatch.setattr(s02, "analyse_galaxy", orig)
    assert s02.main(args) == 0                                          # still stopped: same job
    assert len(list((cut / "profiles/snap99").glob("*.h5"))) == 1
    (cut / "STATUS").write_text("start=" + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() + 2)) + "\n")
    monkeypatch.setenv("ASTRO_RUNDIR", str(cut))                         # the resume job starts after the stop: stale
    assert s02.main(args) == 0
    log = (cut / "logs/t.log").read_text()
    assert "status=skip" in log and log.strip().endswith("done 3/3 failed 0")
    for sid in KINDS:
        _same_results(ref / f"profiles/snap99/sub_{sid}.h5", cut / f"profiles/snap99/sub_{sid}.h5")
    assert not list((cut / "profiles/snap99").glob(".*tmp*"))


def test_failed_galaxy_is_logged_not_fatal(env, tmp_path):
    s02 = script("02_galaxy_diagnostics")
    out = tmp_path / "o"
    assert s02.main(["--config", CFG, "--snap", "99", "--sids", "3,999", "--out", str(out), "--log-name", "f",
                     "--set", "analysis.n_bootstrap=3"]) == 0
    log = (out / "logs/f.log").read_text()
    assert "sid=999 status=fail" in log and log.strip().endswith("done 1/2 failed 1")


def test_make_tasks_covers_each_once():
    mt = script("make_tasks")
    rng = np.random.default_rng(0)
    n = 113
    df = pd.DataFrame(dict(sid=np.arange(n) * 7, n_star=rng.integers(10_000, 3_000_000, n), has_npz=True))
    df.loc[5, "has_npz"] = False
    lines, chunks, costs = mt.make_lines(df, 99, per_chunk=20)
    assert len(lines) == int(np.ceil((n - 1) / 20))
    got = [int(s) for ln in lines for s in ln.split("--sids ")[1].split()[0].split(",")]
    assert sorted(got) == sorted(df.loc[df["has_npz"], "sid"].tolist())        # every galaxy exactly once
    assert costs == sorted(costs, reverse=True)                                  # longest chunk first
    assert all(ln.startswith("$HOME/astro/envs/bars/bin/python $WORKDIR/scripts/02_galaxy_diagnostics.py") for ln in lines)
    assert all("--config $WORKDIR/config/cluster.yaml --snap 99" in ln for ln in lines)


def test_smoke_end_to_end(env, synth, capsys):
    """00-04 on three synthetic galaxies with config/local_test.yaml and ASTRO_RUNDIR set."""
    root, truths = synth
    t0 = time.time()
    assert script("00_check_data").main(["--config", CFG]) == 0
    assert "True" in capsys.readouterr().out.splitlines()[1]           # snap 99 complete
    assert script("01_catalog_table").main(["--config", CFG, "--snap", "99"]) == 0
    table = pd.read_parquet(env / "catalog/snap99.parquet")
    assert sorted(table["sid"]) == sorted(KINDS) and table["has_npz"].all()
    assert script("02_galaxy_diagnostics").main(["--config", CFG, "--snap", "99", "--chunk", "1/1"]) == 0
    assert script("03_classify").main(["--config", CFG, "--snap", "99"]) == 0
    cls = pd.read_parquet(env / "classification_snap99.parquet").set_index("sid")
    assert cls.loc[3, "label"] == "double_decoupled"
    assert cls.loc[5, "label"] == "single"
    assert cls.loc[8, "label"] == "unbarred"
    assert "mstar" in cls.columns
    assert script("04_plot_candidates").main(["--config", CFG, "--snap", "99", "--control-frac", "1.0"]) == 0
    figs = env / "figures/snap99"
    assert (figs / "sub_3.png").stat().st_size > 10_000 and (figs / "index.html").exists()
    dt = time.time() - t0
    print(f"smoke test: {dt:.0f} s wall")
